#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`.eqs` 실행·미리보기·검사·재연 (D36).

    run_script(p, "FLOWS/monthly.eqs", sets={"scenarios": "base"})     실행 → 실행 기록 run:monthly_0001
    plan(p, "FLOWS/monthly.eqs")                                       미리보기(--dry-run) — 기록을 남기지 않는다
    check(p, "FLOWS/monthly.eqs")                                      검사 — 문법·명령·매개변수·부품·파일
    replay(p, "run:monthly_0001")                                      그때 그대로 다시(정의 사본·회차·받은 원자료·같은 스크립트) → 단계마다 같음·다름
"""

import os
import shlex
import shutil
import tempfile
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from .. import registry as reg
from ..work.store import RecordError, WorkStore, detect_who
from .language import BUILTINS, RECORD_REFS, Script, ScriptError, parse, places, resolve
from .session import EXIT_INPUT, EXIT_INTERRUPT, EXIT_OK, EXIT_SOLVE, MARK, STATUS_KO, ScriptStop, Session, snapshot


def _sets(script: Script, sets: Dict[str, object]) -> Dict[str, List[str]]:
    sets = dict(sets or {})
    bad = [k for k in sets if k not in script.params]
    if bad:
        raise ScriptError(f"모르는 매개변수 --set {', '.join(bad)} (이 스크립트의 param: {', '.join(script.params) or '없음'})")
    out = dict(script.params)
    for k, v in sets.items():
        out[k] = v if isinstance(v, (list, tuple)) else shlex.split(str(v))
    return out


def _from(script: Script, spec) -> Optional[int]:
    if spec in (None, ""):
        return None
    s = str(spec).strip()
    if s.isdigit():
        n = int(s)
        if not 1 <= n <= len(script.steps):
            raise ScriptError(f"--from {n}: 단계는 1~{len(script.steps)}")
        return n
    hit = [st.n for st in script.steps if st.section == s or st.section == s.lstrip("#").strip()]
    if not hit:
        raise ScriptError(f"--from {s!r}: 그런 단계 번호·제목이 없습니다(제목: {', '.join(script.sections) or '없음'})")
    return hit[0]


def load(p, path: str) -> Script:
    """스크립트를 읽어 문법·명령 허용 목록·{이름}을 검사한 Script(문제는 .problems)."""
    full = path if os.path.isabs(path) else os.path.join(p.root, path)
    if not os.path.isfile(full) and os.path.isfile(os.path.abspath(path)):
        full = os.path.abspath(path)
    if not full.lower().endswith(".eqs"):
        raise ScriptError(f"Equion 스크립트는 .eqs입니다: {path}")
    if not os.path.isfile(full):
        raise ScriptError(f"스크립트가 없습니다: {path}")
    return parse(p.root, full)


def _sources(p, sc: Script) -> Dict[str, bytes]:
    out = {}
    for rel in [*sc.files, *sc.py]:
        fp = os.path.join(p.root, rel)
        if os.path.isfile(fp):
            with open(fp, "rb") as f:
                out[rel] = f.read()
    return out


def run_script(p, path: str, sets: dict = None, from_step=None, fail_on: str = "failed", name: str = None, who: str = None,
               command: str = None, echo=None, verbosity: int = 1, python: bool = True, today: str = None,
               replay_of: str = None, sc: Script = None):
    """스크립트를 실행하고 실행 기록을 남긴다 → RunResult. 문법·검사 문제가 있으면 아무것도 하지 않고 ScriptError."""
    sc = sc or load(p, path)
    if sc.problems:
        raise ScriptError("스크립트 문제 — 실행하지 않았습니다:\n" + "\n".join(f"  - {x}" for x in sc.problems))
    params = _sets(sc, sets)
    start = _from(sc, from_step)
    s = Session(p.root, params=params, script=sc.path, name=name, who=who or detect_who("terminal"), command=command,
                fail_on=fail_on, echo=echo, verbosity=verbosity, python=python, from_step=start, today=today,
                total=len(sc.steps), sources=_sources(p, sc), title=sc.title, replay_of=replay_of, origin="eqs")
    code = EXIT_OK
    section = None
    try:
        for st in sc.steps:
            if st.section != section:
                section = st.section
                if section:
                    s.section(section)
            if st.kind == "cmd":
                s.cmd(st.text, where=st.where)
            elif st.kind == "expect":
                s.expect_line(st.text, where=st.where)
            else:
                s.py(st.text, where=st.where)
    except ScriptStop as e:
        code = e.code
    except KeyboardInterrupt:
        code = EXIT_INTERRUPT
    return s.close(code)


# ---------------------------------------------------------------------------
# 미리보기·검사
# ---------------------------------------------------------------------------
@dataclass
class Plan:
    """미리보기(--dry-run) — 단계마다 실행할 줄(알 수 있는 값은 바꿔 넣고, 실행 때 정해지는 것은 {…} 그대로)·바꾸는 파일."""

    script: str
    title: str
    params: Dict[str, List[str]]
    steps: List[dict]
    problems: List[str] = field(default_factory=list)
    python: List[int] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """문제가 없으면 참."""
        return not self.problems

    def text(self) -> str:
        """명령줄에 보이는 글."""
        L = [f"[미리보기] {self.script}" + (f" — {self.title}" if self.title else "") + f" · 단계 {len(self.steps)}"
             + " · 기록을 남기지 않습니다"]
        if self.params:
            L.append("  매개변수  " + " · ".join(f"{k} = {' '.join(v)}" for k, v in self.params.items()))
        sec = None
        for st in self.steps:
            if st["section"] != sec:
                sec = st["section"]
                if sec:
                    L.append(f"  ## {sec}")
            tag = {"cmd": "", "expect": "확인 ", "py": "Python "}[st["kind"]]
            L.append(f"  [{st['n']}] {tag}{st['line']}" + ("   (건너뜀)" if st.get("skip") else ""))
            if st["effects"]:
                L.append(f"       바꾸는 것  {', '.join(st['effects'])}")
            if st["later"]:
                L.append(f"       실행 때 정해짐  {', '.join(st['later'])}")
        if self.python:
            L.append(f"  Python 단계 {', '.join(map(str, self.python))} — 임의의 Python 코드가 돈다(명령줄에서만)")
        changing = [st["n"] for st in self.steps if st["effects"]]
        if changing:
            L.append(f"  파일을 바꾸는 단계  {', '.join(map(str, changing))}(정의 파일·노트·보고서는 바뀜 기록에 '스크립트'로 남는다)")
        if self.problems:
            L.append(f"  문제 {len(self.problems)}")
            L += [f"    - {x}" for x in self.problems]
        return "\n".join(L)

    def to_dict(self) -> dict:
        """사전."""
        return {"script": self.script, "title": self.title, "params": self.params, "steps": self.steps,
                "problems": self.problems, "python": self.python, "ok": self.ok}


def plan(p, path: str, sets: dict = None, from_step=None) -> Plan:
    """미리보기 — 실행하지 않고 단계마다 줄(바꿔 넣은 값)·바꾸는 정의 파일·실행 때 정해지는 값. 기록을 남기지 않는다."""
    sc = load(p, path)
    out = Plan(sc.path, sc.title, dict(sc.params), [], list(sc.problems))
    try:
        params = _sets(sc, sets)
        out.params = params
        start = _from(sc, from_step)
    except ScriptError as e:
        out.problems.append(str(e))
        params, start = dict(sc.params), None
    vals = dict(params)
    vals.update({"vintage": p.vintage or "-", "today": __import__("datetime").date.today().isoformat(),
                 "model": p.config.hs.get("model") or p.config.forecast.get("model") or "-", "run": "<이 실행>"})
    try:
        vals["last"] = p.span("last:last")[1]
    except Exception:  # noqa: BLE001
        vals["last"] = "-"
    dynamic = set(RECORD_REFS)                    # 앞 단계가 만드는 기록 — 실행 때 정해짐
    for st in sc.steps:
        later = sorted({n + (f":{f}" if f else "") for n, f in places(st.text) if n in dynamic})
        try:
            line = resolve(st.text, vals, keep=dynamic)
        except ScriptError as e:
            line, later = st.text, later + [str(e)]
        toks = []
        try:
            toks = shlex.split(line)
        except ValueError:
            pass
        eff = reg.effects(toks) if st.kind == "cmd" else []
        if st.kind == "cmd" and "equion.toml [data] vintage" in eff:
            dynamic |= {"vintage", "last"}       # 이 뒤로는 회차가 바뀔 수 있다
        out.steps.append({"n": st.n, "kind": st.kind, "section": st.section, "line": line, "source": st.text,
                          "where": st.where, "effects": eff, "later": [f"{{{x}}}" for x in later],
                          "skip": bool(start and st.n < start)})
        if st.kind == "py":
            out.python.append(st.n)
    out.problems += _deep_check(p, sc, params)
    return out


def _deep_check(p, sc: Script, params) -> List[str]:
    """명령의 선택지(argparse)·부품·모형·시나리오·노트 파일 — 실행 없이 볼 수 있는 것."""
    from ..cli.commands import build_parser
    import contextlib
    import io
    probs = []
    parser = build_parser()
    vals = dict(params)
    vals.update({k: "x" for k in BUILTINS})
    for st in sc.steps:
        if st.kind != "cmd":
            continue
        try:
            toks = shlex.split(resolve(st.text, vals, keep=set(RECORD_REFS)))
        except (ScriptError, ValueError):
            continue
        toks = [t if not (t.startswith("{") and t.endswith("}")) else "est:x" for t in toks]
        err = io.StringIO()
        try:
            with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
                args = parser.parse_args(toks)
        except SystemExit:
            msg = next((x for x in reversed(err.getvalue().splitlines()) if x.strip()), "선택지 오류")
            probs.append(f"{st.where}: {msg.replace('equion: 오류: ', '')}")
            continue
        probs += [f"{st.where}: {x}" for x in _names(p, args)]
    return probs


def _names(p, args) -> List[str]:
    out = []
    c = args.command
    models = set(p.models) | set(p.blocks)
    if c in ("hs", "assemble") and getattr(args, "model", None) and args.model not in models:
        out.append(f"없는 모형·블록 {args.model!r} (있는 것: {', '.join(p.models + p.blocks)})")
    if c == "sim":
        if getattr(args, "model", None) and args.model not in models:
            out.append(f"없는 모형 {args.model!r}")
        for sname in getattr(args, "scenarios", None) or []:
            if sname != "base" and not os.path.isfile(os.path.join(p.root, "SCENARIOS", f"{sname}.toml")):
                out.append(f"없는 시나리오 {sname!r} (SCENARIOS/{sname}.toml)")
    if c in ("est", "ident"):
        import re
        cands = [getattr(args, "part", None)]
        if c == "est" and not getattr(args, "adopted", False):
            cands.append(getattr(args, "target", None))
        for pid in cands:
            if pid and re.match(r"^[A-Za-z]\w*:[A-Za-z]\w*$", pid) and not pid.startswith(("est:", "hs:", "sim:", "an:")):
                try:
                    p.part(pid)
                except Exception as e:  # noqa: BLE001
                    out.append(str(e.args[0] if isinstance(e, KeyError) else e))
    if c == "note" and getattr(args, "note_command", None) == "run":
        if not os.path.isfile(os.path.join(p.root, args.note)):
            out.append(f"없는 노트 {args.note}")
    if c == "report" and getattr(args, "report_command", None) == "new" and getattr(args, "from_report", None):
        fr = args.from_report if args.from_report.endswith(".md") else args.from_report + ".md"
        if not (os.path.isfile(os.path.join(p.root, fr)) or os.path.isfile(os.path.join(p.root, "reports", fr))):
            out.append(f"없는 보고서 --from {args.from_report}")
    return out


@dataclass
class ScriptCheck:
    """검사 결과 — 문제(실행 전에 고칠 것)."""

    script: str
    steps: int
    problems: List[str]
    python: List[int]
    changing: List[int]

    @property
    def ok(self) -> bool:
        """문제가 없으면 참."""
        return not self.problems

    def text(self) -> str:
        """명령줄에 보이는 글."""
        L = [f"[check] {self.script}: 단계 {self.steps} · " + ("문제 없음" if self.ok else f"문제 {len(self.problems)}")]
        L += [f"  - {x}" for x in self.problems]
        if self.changing:
            L.append(f"  파일을 바꾸는 단계 {', '.join(map(str, self.changing))}")
        if self.python:
            L.append(f"  Python 단계 {', '.join(map(str, self.python))}(명령줄에서만)")
        return "\n".join(L)

    def to_dict(self) -> dict:
        """사전."""
        return {"script": self.script, "steps": self.steps, "ok": self.ok, "problems": self.problems,
                "python": self.python, "changing": self.changing}


def check(p, path: str, sets: dict = None) -> ScriptCheck:
    """실행 없이 검사 — 문법·명령(허용 목록)·선택지·{이름}·매개변수(--set)·부품·모형·시나리오·노트·포함한 파일."""
    pl = plan(p, path, sets=sets)
    return ScriptCheck(pl.script, len(pl.steps), pl.problems, pl.python, [s["n"] for s in pl.steps if s["effects"]])


# ---------------------------------------------------------------------------
# 재연
# ---------------------------------------------------------------------------
_SKIP_TOP = {"out", "exports", ".git", "__pycache__", ".venv"}
_SKIP_WORK = {"run", "history"}


def _sandbox(p, rec) -> str:
    """그때의 상태로 프로젝트를 복사한다 — 정의 사본(defs/)·받은 원자료(inbox)·기록과 회차는 지금 것(고치지 않으므로 그대로)."""
    from ..projects.inbox import INBOX_DIR
    from ..work.history import tracked
    from ..projects.records import history_of
    tmp = tempfile.mkdtemp(prefix="equion-replay-")
    dst = os.path.join(tmp, os.path.basename(p.root))

    def ignore(d, names):
        rel = os.path.relpath(d, p.root).replace(os.sep, "/")
        if rel == ".":
            return [n for n in names if n in _SKIP_TOP]
        if rel == "work":
            return [n for n in names if n in _SKIP_WORK]
        if rel == INBOX_DIR.replace(os.sep, "/"):
            return list(names)
        return []
    shutil.copytree(p.root, dst, ignore=ignore)
    for rel in tracked(dst, history_of(p).extra):
        os.remove(os.path.join(dst, rel))
    defs = os.path.join(rec.path, "defs")
    for r, _, fs in os.walk(defs):
        for fn in fs:
            src = os.path.join(r, fn)
            rel = os.path.relpath(src, defs)
            os.makedirs(os.path.dirname(os.path.join(dst, rel)) or dst, exist_ok=True)
            shutil.copyfile(src, os.path.join(dst, rel))
    src_dir = os.path.join(rec.path, "src")
    for r, _, fs in os.walk(src_dir):
        for fn in fs:
            src = os.path.join(r, fn)
            rel = os.path.relpath(src, src_dir)
            os.makedirs(os.path.dirname(os.path.join(dst, rel)) or dst, exist_ok=True)
            shutil.copyfile(src, os.path.join(dst, rel))
    inbox = os.path.join(dst, INBOX_DIR)
    os.makedirs(inbox, exist_ok=True)
    for it in rec.meta.get("inbox") or []:
        if not it.get("to"):
            continue
        shutil.copyfile(os.path.join(dst, it["to"]), os.path.join(inbox, it["from"]))
        if it.get("new"):
            os.remove(os.path.join(dst, it["to"]))       # 그 실행이 넣은 파일 — 다시 넣게
            side = os.path.join(dst, it["to"] + ".source.toml")
            if os.path.isfile(side):
                os.remove(side)
    return dst


def compare_records(a, b, rtol: float = 1e-7, atol: float = 1e-9) -> List[str]:
    """두 기록의 숫자 비교(같은 이름의 CSV마다, 허용오차) — 다른 곳 목록(같으면 [])."""
    out = []
    fa = sorted(f for f in os.listdir(a.path) if f.endswith(".csv"))
    fb = set(f for f in os.listdir(b.path) if f.endswith(".csv"))
    for f in fa:
        if f not in fb:
            out.append(f"{f} 없음")
            continue
        x, y = pd.read_csv(os.path.join(a.path, f)), pd.read_csv(os.path.join(b.path, f))
        if list(x.columns) != list(y.columns) or x.shape != y.shape:
            out.append(f"{f} 모양 {x.shape} → {y.shape}")
            continue
        for col in x.columns:
            xs, ys = x[col], y[col]
            if pd.api.types.is_numeric_dtype(xs) and pd.api.types.is_numeric_dtype(ys):
                xv, yv = xs.to_numpy(float), ys.to_numpy(float)
                ok = np.isclose(xv, yv, rtol=rtol, atol=atol, equal_nan=True)
                if not ok.all():
                    k = int(np.argmax(~ok))
                    out.append(f"{f} {col} {int((~ok).sum())}칸(첫 칸 {xv[k]:.6g} → {yv[k]:.6g})")
            elif not xs.astype(str).equals(ys.astype(str)):
                out.append(f"{f} {col} 글자가 다름")
    return out


def replay(p, rid: str, who: str = None, command: str = None, echo=None, verbosity: int = 1):
    """실행 기록을 그때 그대로 다시 — 정의 사본·받은 원자료·같은 스크립트(src/)·매개변수·오늘 날짜로, 프로젝트 사본에서 돌리고
    단계마다 기록의 숫자를 견준다(허용오차). 프로젝트는 바꾸지 않고, 견준 결과를 새 실행 기록(replay_of)으로 남긴다.
    다른 단계가 있으면 종료 코드 2."""
    from ..projects import Project
    store = WorkStore(p.root)
    rec = store.get(rid, "run")
    m = rec.meta
    if m.get("replay_of"):
        raise ScriptError(f"{rid}는 재연 기록입니다 — 원래 기록 {m['replay_of']}을 다시 하세요")
    if m.get("origin") != "eqs" or not m.get("script"):
        raise ScriptError(f"{rid}는 Python에서 연 실행이라 스크립트가 없습니다 — 그 Python 스크립트를 다시 돌리세요")
    box = _sandbox(p, rec)
    try:
        bp = Project.open(box)
        notes = []
        from .session import versions
        if (m.get("versions") or {}).get("equion") != versions()["equion"]:
            notes.append(f"판이 다릅니다: equion {m['versions'].get('equion')} → {versions()['equion']} — 허용오차로 견줌")
        old_ask = os.environ.get("EQUION_NO_ASK")
        os.environ["EQUION_NO_ASK"] = "1"           # 받은 원자료는 그 실행이 넣은 것만 받은 상자에 있다 — 묻지 않고 넣는다
        try:
            res = run_script(bp, m["script"], sets=m.get("params"), from_step=m.get("from"),
                             fail_on=m.get("fail_on", "failed"), who="script", command=f"(재연) {m.get('command')}", echo=None,
                             today=m.get("today"), python=True)
        finally:
            if old_ask is None:
                os.environ.pop("EQUION_NO_ASK", None)
            else:
                os.environ["EQUION_NO_ASK"] = old_ask
        bstore = WorkStore(box)
        steps = []
        same_all = True
        orig = m.get("steps") or []
        for i, o in enumerate(orig):
            n = res.steps[i] if i < len(res.steps) else None
            row = {"n": o["n"], "line": o["line"], "status": o["status"], "replay_status": n.status if n else "없음",
                   "verdict": "같음", "detail": ""}
            if n is None:
                row["verdict"], row["detail"] = "다름", "재연에서 이 단계까지 가지 못했습니다"
            elif (o["code"] or 0) != (n.code or 0) or o["status"] != n.status:
                row["verdict"], row["detail"] = "다름", f"상태 {o['status']} → {n.status}" + (f" — {n.detail}" if n.detail else "")
            elif o["kind"] == "cmd":
                diffs = []
                ro = [r for r in o["records"]]
                rn = [r for r in n.records]
                if len(ro) != len(rn):
                    diffs.append(f"기록 수 {len(ro)} → {len(rn)}")
                for a, b in zip(ro, rn):
                    if a.startswith("data:") or b.startswith("data:"):
                        if a != b:
                            diffs.append(f"자료 회차 {a} → {b}")
                        continue
                    try:
                        diffs += [f"{a}: {x}" for x in compare_records(store.get(a), bstore.get(b))]
                    except RecordError as e:
                        diffs.append(str(e))
                if diffs:
                    row["verdict"], row["detail"] = "다름", "; ".join(diffs[:6])
                else:
                    row["detail"] = ("숫자 같음 — " + " · ".join(ro[:3]) + (" …" if len(ro) > 3 else "")) if ro else "기록 없음 — 상태 같음"
            elif o["kind"] == "expect":
                row["detail"] = n.detail
            same_all &= row["verdict"] == "같음"
            steps.append(row)
    finally:
        shutil.rmtree(os.path.dirname(box), ignore_errors=True)
    return _write_replay(p, rec, steps, same_all, notes, who, command, echo, verbosity)


@dataclass
class ReplayResult:
    """재연 결과 — 단계마다 같음·다름(`.steps`) · `.same` · 새 실행 기록 `.id`."""

    id: str
    of: str
    steps: List[dict]
    same: bool
    notes: List[str]

    @property
    def exit_code(self) -> int:
        """같으면 0, 다르면 2."""
        return EXIT_OK if self.same else EXIT_SOLVE

    def text(self) -> str:
        """명령줄에 보이는 글."""
        L = [f"[run --replay] {self.of} — 단계 {len(self.steps)} · "
             + ("모두 같음" if self.same else f"다름 {sum(1 for s in self.steps if s['verdict'] != '같음')}")]
        for s in self.steps:
            L.append(f"  [{s['n']}] {'=' if s['verdict'] == '같음' else '≠'} {s['line']}" + (f"  — {s['detail']}" if s["detail"] else ""))
        L += [f"  {x}" for x in self.notes]
        L.append(f"기록  {self.id} · 종료 코드 {self.exit_code}")
        return "\n".join(L)

    def to_dict(self) -> dict:
        """사전."""
        return {"id": self.id, "of": self.of, "same": self.same, "steps": self.steps, "notes": self.notes,
                "exit_code": self.exit_code}


def _write_replay(p, rec, steps, same, notes, who, command, echo, verbosity) -> ReplayResult:
    from ..reporting import markdown as md
    from ..work.store import WHO_KO
    from .session import _stem, versions
    store = WorkStore(p.root)
    name = store.next_name("run", _stem(rec.meta.get("script")))
    meta = {"who": who or detect_who("terminal"), "command": command or f"equion run --replay {rec.id}", "project": p.name,
            "equion": versions()["equion"], "versions": versions(), "target": rec.meta.get("script"),
            "script": rec.meta.get("script"), "replay_of": rec.id, "params": rec.meta.get("params"),
            "status": "ok" if same else "error", "exit_code": EXIT_OK if same else EXIT_SOLVE, "same": same,
            "steps": steps, "notes": notes, "vintage": rec.meta.get("vintage"), "data": rec.meta.get("data")}
    rows = pd.DataFrame([{"단계": s["n"], "줄": f"`{s['line']}`", "": "=" if s["verdict"] == "같음" else "≠",
                          "견줌": s["detail"][:140]} for s in steps]).set_index("단계") if steps else pd.DataFrame()
    head = [("다시 한 것", rec.id), ("결과", "모두 같음" if same else "다른 단계가 있음"),
            ("누가", WHO_KO.get(meta["who"], meta["who"])), ("명령", f"`{meta['command']}`"),
            ("판", f"equion {meta['equion']} (그때 {(rec.meta.get('versions') or {}).get('equion')})")]
    sections = [("단계", md.table(rows) if len(rows) else "(없음)")]
    if notes:
        sections.append(("알릴 것", md.bullets(notes)))
    summary = md.card(f"재연 run:{name} ← {rec.id}", head, sections)
    store.write("run", name, meta, {}, summary,
                log={"metric": ("모두 같음" if same else "다름") + f" · {rec.id}", "status": meta["status"]})
    out = ReplayResult(f"run:{name}", rec.id, steps, same, notes)
    if echo and verbosity > 0:
        echo(out.text())
    return out
