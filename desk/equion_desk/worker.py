"""작업 프로세스 — 프로젝트마다 띄워 둔 Python 하나가 `eqn.project`의 함수를 부른다(DECISIONS D40).

명령마다 새 프로세스를 띄우면 `import equion`만 1초를 넘는다. 띄워 둔 프로세스 안에서는 추정이 수십 밀리초다(성공 기준 S1).

- 앱(서버)과는 표준 입출력으로 한 줄에 JSON 하나씩 주고받는다. 요청 `{"id", "op", "args"}` → 응답 `{"id", "ok", "result" | "error",
  "seconds", "said"}`. `said`는 엔진이 화면에 쓴 줄('알아서 한 것' 등)이다 — 응답 줄과 섞이지 않게 따로 모은다.
- 한 번에 하나씩 한다(프로젝트의 기록 저장소가 그렇게 쓰인다). 기다리는 요청은 줄을 선다.
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

from . import runtime

START_WAIT = 60.0     # 프로세스가 뜨고 equion을 불러올 때까지 기다리는 시간(초) — 느린 디스크·보안 프로그램
CALL_WAIT = 600.0     # 요청 하나를 기다리는 시간(초)


class WorkerError(RuntimeError):
    """작업 프로세스가 알린 오류. `kind`는 `input`(프로젝트·입력 오류 — 고칠 것은 사용자 쪽)·`internal`·`gone`(프로세스가 끝남)·`cancelled`."""

    def __init__(self, message: str, kind: str = "internal", detail: str = "") -> None:
        super().__init__(message)
        self.kind = kind
        self.detail = detail


# ---- 작업 프로세스 쪽 ---------------------------------------------------------------------------

def _series(path: str) -> dict[str, list]:
    """기록 폴더의 `series.csv`(기간·실측·적합·잔차) → 열마다 목록. 화면의 차트가 쓴다."""
    import csv

    out: dict[str, list] = {}
    file = os.path.join(path, "series.csv")
    if not os.path.isfile(file):
        return out
    with open(file, encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f))
    if not rows:
        return out
    for i, name in enumerate(rows[0]):
        col: list = []
        for row in rows[1:]:
            cell = row[i] if i < len(row) else ""
            if i == 0:
                col.append(cell)
            else:
                try:
                    col.append(float(cell))
                except ValueError:
                    col.append(None)
        out[name] = col
    return out


def _ops(project: Any) -> dict[str, Any]:
    """요청 이름 → 하는 일. 화면이 부를 수 있는 것의 허용 목록이다 — 여기 없는 이름은 거절한다."""

    def ping() -> dict:
        import equion

        return {"equion": equion.__version__, "python": sys.version.split()[0], "executable": sys.executable,
                "project": project.name, "root": str(project.root)}

    def parts() -> list[dict]:
        return [{"id": p.id, "block": p.block, "target": p.target, "kind": p.kind, "text": p.text, "desc": p.desc, "where": p.where} for p in project.parts()]

    def est(target: str, method: str | None = None, smpl: str | None = None) -> dict:
        rec = project.est(target, method=method, smpl=smpl, who="desk", command=f"est {target}")
        out = rec.to_dict()
        out["series"] = _series(out.get("path", ""))
        return out

    def hs(model: str | None = None) -> dict:
        rec = project.hs(model, record=True, who="desk", command=f"hs {model or ''}".strip())
        return rec.to_dict()

    def sim(scenario: str = "base") -> dict:
        rec = project.sim(scenario, who="desk", command=f"sim {scenario}")
        return rec.to_dict()

    return {"ping": ping, "parts": parts, "est": est, "hs": hs, "sim": sim}


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
        import equion as eqn
        from equion.projects.config import ProjectError

        project = eqn.project(root)
        ops = _ops(project)
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

    def call(self, op: str, timeout: float = CALL_WAIT, **args: Any) -> dict:
        """요청 하나를 하고 `{"result", "seconds", "said", "round_trip"}`을 돌려준다.

        오류
            WorkerError: 작업 프로세스가 오류를 알렸거나(`kind` input·internal), 끝났거나(gone), 취소됨(cancelled)
        """
        with self._lock:
            self._cancelled = False
            if not self.alive:
                self._start()
            proc = self._proc
            assert proc is not None and proc.stdin is not None
            self._seq += 1
            rid = self._seq
            began = time.perf_counter()
            self.busy_op = op
            try:
                proc.stdin.write((json.dumps({"id": rid, "op": op, "args": args}, ensure_ascii=False) + "\n").encode("utf-8"))
                proc.stdin.flush()
                while True:
                    resp = self._read(timeout)
                    if resp.get("id") == rid:
                        break
            except (OSError, ValueError) as exc:
                self.stop()
                raise WorkerError(f"작업 프로세스와 끊겼습니다: {exc}", "gone") from exc
            finally:
                self.busy_op = None
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
