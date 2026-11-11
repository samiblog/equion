"""작업 프로세스 — 프로젝트마다 띄워 둔 Python 하나가 `eqn.project`의 함수를 부른다(DECISIONS D40).

명령마다 새 프로세스를 띄우면 `import equion`만 1초를 넘는다. 띄워 둔 프로세스 안에서는 추정이 수십 밀리초다(성공 기준 S1).

- 앱(서버)과는 표준 입출력으로 한 줄에 JSON 하나씩 주고받는다. 요청 `{"id", "op", "args"}` → 응답 `{"id", "ok", "result" | "error",
  "seconds", "said"}`. `said`는 엔진이 화면에 쓴 줄('알아서 한 것' 등)이다 — 응답 줄과 섞이지 않게 따로 모은다.
- 한 번에 하나씩 한다(프로젝트의 기록 저장소가 그렇게 쓰인다). 기다리는 요청은 줄을 선다.
- 오래 걸리는 일(스크립트)은 하는 동안 `{"progress": {...}, "for": id}` 줄을 보낸다 — 앱이 작업 줄에 '3/7 …'로 보인다.
- 취소는 프로세스를 끝내고 다시 띄운다. 기록은 임시 폴더에 쓴 뒤 옮기므로(D33) 중간에 끝나도 깨진 기록이 남지 않는다.
- 프로세스는 격리 모드(`-I`)로 뜬다 — PC의 `PYTHONPATH`·사용자 site-packages를 읽지 않는다(D39).

이 파일은 양쪽에서 쓴다: 앱은 `Worker`(띄우고 부르는 쪽), 작업 프로세스는 `python -I -m equion_desk.worker <폴더>`(`serve`).
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import threading
import time
from typing import Any

from . import dataops, jobs, modelops, runtime
from .records import read_series

START_WAIT = 60.0     # 프로세스가 뜨고 equion을 불러올 때까지 기다리는 시간(초) — 느린 디스크·보안 프로그램
CALL_WAIT = 600.0     # 요청 하나를 기다리는 시간(초)


class WorkerError(RuntimeError):
    """작업 프로세스가 알린 오류. `kind`는 `input`(프로젝트·입력 오류 — 고칠 것은 사용자 쪽)·`internal`·`gone`(프로세스가 끝남)·`cancelled`."""

    def __init__(self, message: str, kind: str = "internal", detail: str = "") -> None:
        super().__init__(message)
        self.kind = kind
        self.detail = detail


# ---- 작업 프로세스 쪽 ---------------------------------------------------------------------------

class _Project:
    """작업 프로세스가 쥔 프로젝트. 정의 파일이 바뀌었으면 다음 요청 전에 다시 연다 — 화면이 옛 식으로 계산하지 않게."""

    def __init__(self, root: str) -> None:
        self.root = root
        self._stamp: Any = None
        self._project: Any = None

    def get(self) -> Any:
        import equion as eqn

        from .watch import definitions

        stamp = definitions(self.root)
        if self._project is None or stamp != self._stamp:
            self._project = eqn.project(self.root)
            self._stamp = stamp
        return self._project


def _part(p: Any, adopted: dict[str, str], project: Any = None) -> dict:
    out = {"id": p.id, "block": p.block, "target": p.target, "kind": p.kind, "text": p.text, "desc": p.desc, "where": p.where,
           "adopted": adopted.get(p.id)}
    if project is not None:
        try:
            out["models"] = list(project.used_by(p.id))       # 이 부품을 쓰는 모형 — '이 후보로 과거 재현'이 고른다
        except Exception:
            out["models"] = []
    return out


def _command(*words: str | None) -> str:
    """기록에 적는 명령 — 같은 일을 터미널에서 할 때 치는 글 그대로(`equion est demand:CN`)."""
    import shlex

    return shlex.join(["equion", *[w for w in words if w]])


def _names(root: str, folder: str, suffixes: tuple[str, ...]) -> list[str]:
    try:
        files = sorted(os.listdir(os.path.join(root, folder)))
    except OSError:
        return []
    return [os.path.splitext(f)[0] for f in files if f.lower().endswith(suffixes)]


def _ops(holder: _Project, notify: Any = None) -> dict[str, Any]:
    """요청 이름 → 하는 일. 화면이 부를 수 있는 것의 허용 목록이다 — 여기 없는 이름은 거절한다. notify(**정보)는 하는 동안의 진행 알림."""

    def ping() -> dict:
        import equion

        project = holder.get()
        return {"equion": equion.__version__, "python": sys.version.split()[0], "executable": sys.executable,
                "project": project.name, "root": str(project.root)}

    def parts() -> list[dict]:
        project = holder.get()
        adopted = project.adopted
        return [_part(p, adopted) for p in project.parts()]

    def overview() -> dict:
        """프로젝트 한눈에 — 블록과 부품·모형·자료 회차·시나리오. 계산은 하지 않는다(파일을 읽기만)."""
        import equion

        project = holder.get()
        cfg = project.config
        adopted = project.adopted
        by_block: dict[str, list[dict]] = {}
        for p in project.parts():
            by_block.setdefault(p.block, []).append(_part(p, adopted, project))
        vintage = None
        if cfg.series_file:
            vintage = next((v for v in project.data_list() if v.get("current")), None) or {"id": project.vintage}
        return {
            "project": project.name, "root": str(project.root), "equion": equion.__version__, "python": sys.version.split()[0],
            "executable": sys.executable, "freq": cfg.freq, "vintage": vintage, "data_file": cfg.data_file,
            "blocks": [{"name": b.name, "file": b.file, "desc": b.desc, "parts": by_block.get(b.name, [])} for b in cfg.blocks.values()],
            "models": [{"name": m.name, "desc": m.desc, "blocks": list(m.blocks), "include": list(m.include), "exclude": list(m.exclude)}
                       for m in cfg.models.values()],
            "hs": dict(cfg.hs or {}), "forecast": dict(cfg.forecast or {}), "criteria": bool(cfg.criteria),
            "scenarios": _names(project.root, "SCENARIOS", (".toml",)), "assumptions": _names(project.root, "ASSUMPTIONS", (".csv",)),
            "scripts": _names(project.root, "FLOWS", (".eqs",)), "warnings": list(cfg.warnings or []),
        }

    def est(target: str, method: str | None = None, smpl: str | None = None, sim: bool = False, cov: str | None = None,
            name: str | None = None, part: str | None = None) -> dict:
        """식 하나를 추정해 기록을 남긴다. target 은 부품(블록 파일의 그 줄) 또는 식 글자(part 의 후보)."""
        words = ["est", target, *(["--for", part] if part else []), *(["--smpl", smpl] if smpl else []), *(["--sim"] if sim else []),
                 *(["--cov", cov] if cov else []), *(["--method", method] if method and method != "auto" else []),
                 *(["--as", name] if name else [])]
        rec = holder.get().est(target, method=method, smpl=smpl, as_name=name, part=part, sim=bool(sim), cov=cov, who="desk",
                               command=_command(*words))
        out = rec.to_dict()
        out["series"] = read_series(os.path.join(holder.root, out.get("path", "")))
        return out

    def check(text: str, part: str | None = None) -> dict:
        """식 글자를 읽어만 본다(추정하지 않는다) — 치는 동안의 문법 검사(기획안 §2.4-1의 예외: 계산이 아니라 검사).

        `{ok, kind, target, variables, unknown}` 또는 `{ok: False, error}`. unknown 은 자료에 없는 변수 이름.
        """
        from equion.projects.parts import parse_line

        project = holder.get()
        text = (text or "").strip()
        if not text:
            return {"ok": False, "empty": True}
        data = project.workfile._data
        try:
            info = parse_line(text, data)
        except Exception as exc:        # 문법 오류·모르는 함수 — 까닭을 그대로 알린다
            return {"ok": False, "error": str(exc)}
        columns = {str(c).upper() for c in data.data.columns}
        names = sorted(str(v) for v in info["data_vars"])
        out = {"ok": True, "kind": info["kind"], "target": info["target"], "variables": names,
               "unknown": [v for v in names if v.upper() not in columns]}
        if part:
            try:
                out["part_target"] = project.part(part).target
            except Exception:           # 지워진 부품 — 검사는 식만으로
                pass
        return out

    def ident(part: str) -> dict:
        """항등식을 실측으로 검사한다(좌변·우변을 계산해 견준다). 기록은 남기지 않는다 — `equion ident 부품 --check` 와 같다."""
        found = holder.get().ident(part)
        out = found.to_dict()
        table = found.table
        if table is not None and len(table):
            cols = list(table.columns)
            out["series"] = {"period": [str(i) for i in table.index], "lhs": table[cols[0]].tolist(), "rhs": table[cols[1]].tolist(),
                             "diff": table[cols[2]].tolist()}
        out["command"] = _command("ident", part, "--check")
        return out

    def adopt(record: str, part: str | None = None) -> dict:
        """추정 기록을 부품의 채택 계수로 — 블록 파일의 그 줄과 채택표가 바뀌고 바뀜 기록에 남는다(D35)."""
        done = holder.get().adopt(record, part=part, who="desk", command=_command("adopt", record, *(["--part", part] if part else [])))
        return done.to_dict()

    def hs(model: str | None = None, start: str | None = None, end: str | None = None, mode: str | None = None, vs: str | None = None,
           name: str | None = None) -> dict:
        return modelops.hs_run(holder.get(), model, start, end, mode, vs, name)

    def hs_swap(part: str, record: str, model: str | None = None) -> dict:
        """'이 후보로 HS' — 부품을 추정 기록의 식·계수로 바꿔 끼워 모형을 풀고(파일은 그대로) 지금 파일로 푼 것과 견준다.

        견줄 기준은 지금 정의 파일·자료 그대로 푼 과거 재현 기록이다. 있으면 그것을 쓰고, 없으면 먼저 푼다(그것도 기록으로 남는다).
        """
        import json

        from equion.projects import records as R
        from equion.projects.config import ProjectError

        project = holder.get()
        users = project.used_by(part)
        default = (project.config.hs or {}).get("model")
        model = model or (default if default in users else (users[0] if users else None))
        if not model or model not in users:
            raise ProjectError(f"{part} 를 쓰는 모형이 없습니다" if not users else f"모형 {model} 은(는) {part} 를 쓰지 않습니다(쓰는 모형: {', '.join(users)})")
        files, data = R.definition_hashes(project), R.data_spec(project)
        base = None
        for rec in reversed(project.work.records("hs")):
            m = rec.meta
            if m.get("model") != model or m.get("swaps") or m.get("replay"):
                continue
            try:
                with open(rec.file("assembly.json"), encoding="utf-8") as f:
                    spec = json.load(f)
            except (OSError, ValueError):
                continue
            fresh = spec.get("files") == files and (spec.get("data") or {}).get("content_sha256") == data.get("content_sha256")
            if fresh and not spec.get("options"):
                base = rec.id
            break                        # 가장 최근의 기준 풀이만 본다 — 낡았으면 새로 푼다
        made = base is None
        if made:
            base = project.hs(model, record=True, who="desk", command=_command("hs", model)).id
        rec = project.hs(model, swap={part: record}, vs=base, record=True, who="desk",
                         command=_command("hs", model, "--swap", f"{part}={record}", "--vs", base))
        return {**rec.to_dict(), "baseline": base, "baseline_new": made}

    def an_diag(target: str) -> dict:
        """식 진단(계열상관·이분산·정규성·RESET·CUSUM) — 부품 또는 추정 기록. 분석 기록(an:)을 남긴다."""
        rec = holder.get().an("diag", target, who="desk", command=_command("an", "diag", target))
        return rec.to_dict() if hasattr(rec, "to_dict") else {**dict(rec.meta), "id": rec.id}

    def sim(scenario: str = "base", model: str | None = None) -> dict:
        rec = holder.get().sim(scenario, model=model, who="desk", command=_command("sim", scenario, *(["--model", model] if model else [])))
        return rec.to_dict()

    # ---- 자료 작업대 · 분석 탭(dataops.py) ---------------------------------------------------------

    def data() -> dict:
        return dataops.overview(holder.get())

    def series(name: str) -> dict:
        return dataops.series(holder.get(), name)

    def data_build() -> dict:
        return dataops.build(holder.get())

    def data_use(vintage: str) -> dict:
        return dataops.use(holder.get(), vintage)

    def data_diff(a: str | None = None, b: str | None = None) -> dict:
        return dataops.diff(holder.get(), a, b)

    def data_add(path: str, source: str | None = None, name: str | None = None, inbox: bool = False) -> dict:
        return dataops.add(holder.get(), path, source, name, inbox=inbox)

    def data_preview(file: str, frame: dict | None = None, rows: int = 40, series: dict | None = None) -> dict:
        return dataops.preview(holder.get(), file, frame, rows, series)

    def data_define(source: str, file: str, frame: dict | None = None, desc: str | None = None, series: dict | None = None,
                    replace: bool = False, dry: bool = False) -> dict:
        return dataops.define(holder.get(), source, file, frame, desc, series, replace, dry)

    def analyses() -> dict:
        return dataops.analyses(holder.get())

    def an(analysis: str, target: str, options: dict | None = None, smpl: str | None = None, name: str | None = None) -> dict:
        return dataops.run_analysis(holder.get(), analysis, target, options, smpl, name)

    def an_keep(record: str, name: str | None = None, replace: bool = False) -> dict:
        return dataops.keep(holder.get(), record, name, replace)

    # ---- 모형 작업대 · 흐름 화면(modelops.py) -------------------------------------------------------
    def assembly(model: str | None = None) -> dict:
        return modelops.assembly(holder.get(), model)

    def model_define(name: str, blocks: list | None = None, include: list | None = None, exclude: list | None = None, desc: str | None = None,
                     dry: bool = False) -> dict:
        return modelops.model_define(holder.get(), name, blocks, include, exclude, desc, dry)

    def block_define(name: str, desc: str | None = None, dry: bool = False) -> dict:
        return modelops.block_define(holder.get(), name, desc, dry)

    def check_text(path: str, text: str) -> dict:
        return modelops.check_text(holder.get(), path, text)

    def write_text(path: str, text: str) -> dict:
        return modelops.write_text(holder.get(), path, text)

    def hs_replay(record: str) -> dict:
        return modelops.hs_replay(holder.get(), record)

    def hs_view(record: str) -> dict:
        return modelops.hs_view(holder.get(), record)

    def hs_series(record: str, names: list) -> dict:
        return modelops.hs_series(holder.get(), record, names)

    def trace(record: str, name: str) -> dict:
        return modelops.trace(holder.get(), record, name)

    def scripts() -> dict:
        return modelops.scripts(holder.get())

    def script_plan(path: str, sets: dict | None = None, from_step: Any = None) -> dict:
        return modelops.script_plan(holder.get(), path, sets, from_step)

    def script_run(path: str, sets: dict | None = None, from_step: Any = None) -> dict:
        return modelops.script_run(holder.get(), path, sets, from_step, notify)

    def run_view(record: str) -> dict:
        return modelops.run_view(holder.get(), record)

    def script_new(name: str, records: list, title: str | None = None) -> dict:
        return modelops.script_new(holder.get(), name, records, title)

    def todo() -> dict:
        return modelops.todo(holder.get())

    def reestimate(name: str | None = None, adopt: str = "never", parts: list | None = None) -> dict:
        return modelops.reestimate(holder.get(), name, adopt, parts)

    def scan() -> dict | None:
        """명령 밖에서 고친 정의 파일을 '바깥' 바뀜으로 적는다(K7). 바뀐 것이 없으면 None."""
        change = holder.get().history.scan()
        return {"id": change.id, "files": list(change.files)} if change is not None else None

    return {"ping": ping, "parts": parts, "overview": overview, "est": est, "check": check, "ident": ident, "adopt": adopt,
            "hs": hs, "hs_swap": hs_swap, "an_diag": an_diag, "sim": sim, "scan": scan,
            "data": data, "series": series, "data_build": data_build, "data_use": data_use, "data_diff": data_diff, "data_add": data_add,
            "data_preview": data_preview, "data_define": data_define,
            "analyses": analyses, "an": an, "an_keep": an_keep,
            "assembly": assembly, "model_define": model_define, "block_define": block_define, "check_text": check_text, "write_text": write_text,
            "hs_replay": hs_replay, "hs_view": hs_view, "hs_series": hs_series, "trace": trace, "scripts": scripts, "script_plan": script_plan,
            "script_run": script_run, "run_view": run_view, "script_new": script_new, "todo": todo, "reestimate": reestimate}


def _plain(value: Any) -> Any:
    """JSON으로 보낼 수 있는 값으로(NaN·무한대는 null — 브라우저의 JSON은 그것을 읽지 못한다)."""
    if isinstance(value, float):
        return value if value == value and value not in (float("inf"), float("-inf")) else None
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if hasattr(value, "item"):          # numpy 값 하나
        return _plain(value.item())
    return str(value)


def serve(root: str) -> int:
    """작업 프로세스의 본체. 표준 입력의 요청을 차례로 하고 표준 출력에 응답을 쓴다. 입력이 닫히면 끝난다."""
    out = os.fdopen(os.dup(1), "w", encoding="utf-8", newline="\n")
    sys.stdout = io.StringIO()            # 엔진이 쓰는 글이 응답 줄에 섞이지 않게 — 요청마다 따로 모은다
    inp = io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8")

    def send(obj: dict) -> None:
        out.write(json.dumps(_plain(obj), ensure_ascii=False) + "\n")
        out.flush()

    began = time.perf_counter()
    try:
        from equion.projects.config import ProjectError      # equion 을 여기서 한 번 불러온다(1초 남짓)

        holder = _Project(root)
        holder.get()                      # 프로젝트가 아니면 여기서 알린다
        doing: dict[str, Any] = {"id": None}

        def notify(**info: Any) -> None:
            send({"progress": info, "for": doing["id"]})

        ops = _ops(holder, notify)
    except Exception as exc:  # 프로젝트가 아니거나 equion을 불러오지 못함 — 앱에 알리고 끝낸다
        send({"ready": False, "error": str(exc), "kind": "input"})
        return 3
    send({"ready": True, "seconds": time.perf_counter() - began, "pid": os.getpid()})

    for line in inp:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            rid, op, args = req.get("id"), req.get("op"), req.get("args") or {}
        except (ValueError, AttributeError):
            continue
        said = io.StringIO()
        began = time.perf_counter()
        doing["id"] = rid
        try:
            if op not in ops:
                raise WorkerError(f"모르는 요청: {op}", "input")
            with contextlib.redirect_stdout(said), contextlib.redirect_stderr(said):
                result = ops[op](**args)
            send({"id": rid, "ok": True, "result": result, "seconds": time.perf_counter() - began, "said": said.getvalue()})
        except (ProjectError, WorkerError, TypeError, ValueError, KeyError, OSError) as exc:
            kind = getattr(exc, "kind", "input")
            text = str(exc.args[0]) if isinstance(exc, KeyError) and exc.args else str(exc)   # KeyError의 글은 따옴표가 붙는다
            send({"id": rid, "ok": False, "error": text, "kind": kind, "seconds": time.perf_counter() - began,
                  "said": said.getvalue()})
        except Exception as exc:  # 예상 못 한 오류 — 프로세스는 살려 두고 무슨 일인지 알린다
            import traceback

            send({"id": rid, "ok": False, "error": f"{type(exc).__name__}: {exc}", "kind": "internal",
                  "detail": traceback.format_exc(), "seconds": time.perf_counter() - began, "said": said.getvalue()})
    return 0


# ---- 앱 쪽 ---------------------------------------------------------------------------------------

class Worker:
    """프로젝트 폴더 하나의 작업 프로세스. 처음 부를 때 뜨고, 끝나 있으면 다음 부름에서 다시 뜬다.

    예
        >>> w = Worker(folder)                      # doctest: +SKIP
        >>> w.call("est", target="demand:CN")["stats"]["r_squared"]   # doctest: +SKIP
        0.9999...
    """

    def __init__(self, root: str) -> None:
        self.root = os.path.abspath(root)
        self._lock = threading.Lock()         # 요청은 한 번에 하나
        self._proc: subprocess.Popen | None = None
        self._seq = 0
        self._cancelled = False
        self.started_seconds: float | None = None   # 뜨는 데 걸린 시간(프로세스 시작 + import + 프로젝트 열기)
        self.busy_op: str | None = None             # 지금 하는 일(없으면 None)
        self.busy_since: float | None = None        # 그 일을 시작한 때(time.monotonic)

    @property
    def alive(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def _start(self) -> None:
        began = time.perf_counter()
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)   # 창 모드에서 검은 콘솔 창이 깜빡이지 않게
        self._proc = subprocess.Popen(
            [runtime.python_exe(), "-I", "-X", "utf8", "-m", "equion_desk.worker", self.root],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            cwd=self.root, env=runtime.clean_env(), creationflags=flags,
        )
        jobs.adopt(self._proc)      # 앱이 끝나면(강제로 끝내도) 함께 끝난다
        hello = self._read(START_WAIT)
        if not hello.get("ready"):
            self.stop()
            raise WorkerError(hello.get("error") or "작업 프로세스가 뜨지 못했습니다", hello.get("kind", "gone"))
        self.started_seconds = time.perf_counter() - began

    def _read(self, timeout: float) -> dict:
        """응답 한 줄. 프로세스가 끝났으면 `gone`, 시간이 지나면 프로세스를 끝내고 알린다."""
        proc = self._proc
        assert proc is not None and proc.stdout is not None
        box: list[bytes] = []
        reader = threading.Thread(target=lambda: box.append(proc.stdout.readline()), daemon=True)
        reader.start()
        reader.join(timeout)
        if reader.is_alive():
            self.stop()
            raise WorkerError(f"작업 프로세스가 {timeout:.0f}초 안에 답하지 않아 끝냈습니다", "gone")
        if not box or not box[0]:
            raise WorkerError("취소했습니다" if self._cancelled else "작업 프로세스가 끝났습니다",
                              "cancelled" if self._cancelled else "gone")
        return json.loads(box[0].decode("utf-8"))

    def call(self, op: str, timeout: float = CALL_WAIT, wait: bool = True, progress: Any = None, **args: Any) -> dict:
        """요청 하나를 하고 `{"result", "seconds", "said", "round_trip"}`을 돌려준다.

        wait=False 면 다른 일을 하는 중일 때 줄을 서지 않고 바로 `busy` 오류를 낸다(치는 동안의 문법 검사처럼 기다릴 값이 없는 부름).
        progress(정보)를 주면 하는 동안 작업 프로세스가 알리는 진행(스크립트의 단계)을 받는다.

        오류
            WorkerError: 작업 프로세스가 오류를 알렸거나(`kind` input·internal), 끝났거나(gone), 취소됨(cancelled), 바쁨(busy)
        """
        if not self._lock.acquire(blocking=wait):
            raise WorkerError("다른 계산이 도는 중입니다", "busy")
        try:
            return self._call(op, timeout, args, progress)
        finally:
            self._lock.release()

    def _call(self, op: str, timeout: float, args: dict[str, Any], progress: Any = None) -> dict:
        self._cancelled = False
        if not self.alive:
            self._start()
        proc = self._proc
        assert proc is not None and proc.stdin is not None
        self._seq += 1
        rid = self._seq
        began = time.perf_counter()
        self.busy_op, self.busy_since = op, time.monotonic()
        try:
            proc.stdin.write((json.dumps({"id": rid, "op": op, "args": args}, ensure_ascii=False) + "\n").encode("utf-8"))
            proc.stdin.flush()
            while True:
                resp = self._read(timeout)
                if resp.get("id") == rid:
                    break
                if progress is not None and resp.get("for") == rid and isinstance(resp.get("progress"), dict):
                    try:
                        progress(resp["progress"])
                    except Exception:      # 알림을 받는 쪽의 문제로 계산을 끊지 않는다
                        pass
        except (OSError, ValueError) as exc:
            self.stop()
            raise WorkerError(f"작업 프로세스와 끊겼습니다: {exc}", "gone") from exc
        finally:
            self.busy_op = self.busy_since = None
        if not resp.get("ok"):
            raise WorkerError(resp.get("error", ""), resp.get("kind", "internal"), resp.get("detail", ""))
        return {"result": resp.get("result"), "seconds": resp.get("seconds"), "said": resp.get("said", ""),
                "round_trip": time.perf_counter() - began}

    def cancel(self) -> bool:
        """지금 하는 일을 그만둔다 — 프로세스를 끝낸다(다음 부름에서 다시 뜬다). 하던 일이 있었으면 True."""
        was = self.busy_op is not None
        self._cancelled = was
        self.stop()
        return was

    def stop(self) -> None:
        proc, self._proc = self._proc, None
        if proc is None:
            return
        with contextlib.suppress(OSError):
            proc.kill()
        with contextlib.suppress(Exception):
            proc.wait(5)
        for pipe in (proc.stdin, proc.stdout):
            with contextlib.suppress(Exception):
                if pipe:
                    pipe.close()


if __name__ == "__main__":
    sys.exit(serve(sys.argv[1] if len(sys.argv) > 1 else "."))
