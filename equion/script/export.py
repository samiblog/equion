#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""스크립트 만들기 — 작업 기록에서 초안(`equion script new --from-records`), 같은 일을 하는 Python으로(`equion script export --py`)."""

import os
import re
import shlex
from datetime import date
from typing import List

from .. import registry as reg
from ..work.store import KIND_KO, WorkStore
from .language import Script, ScriptError, parse

FLOWS = "FLOWS"
HEAD_KO = {"data": "자료", "est": "추정", "hs": "과거 재현", "sim": "전망", "an": "분석", "note": "결과물", "report": "결과물",
           "export": "결과물"}
_DROP_VALUE = {"-p", "--project", "--as", "--note"}      # 다시 돌리면 겹치거나(이름) 곳이 다른 것
_DROP_FLAG = {"--json"}


def clean_command(cmd: str) -> str:
    """기록의 명령 → 스크립트 한 줄 — 앞의 equion·-p 폴더·--as 이름·--note·--json을 뺀다(다시 돌려도 이름이 겹치지 않게)."""
    toks = shlex.split(cmd or "")
    if toks and toks[0] == "equion":
        toks = toks[1:]
    out, skip = [], False
    for t in toks:
        if skip:
            skip = False
            continue
        if t in _DROP_VALUE:
            skip = True
            continue
        if any(t.startswith(x + "=") for x in _DROP_VALUE) or t in _DROP_FLAG:
            continue
        out.append(t)
    return shlex.join(out)


def draft(p, records: List[str] = None, last: int = None, title: str = None) -> str:
    """작업 기록의 명령으로 스크립트 초안(글) — 같은 종류가 이어지면 한 제목 아래. 부를 수 없는 명령은 주석으로 남긴다."""
    store = WorkStore(p.root)
    log = store.log()
    if records:
        want = list(dict.fromkeys(records))
        have = {d["id"]: d for d in log}
        missing = [r for r in want if r not in have]
        if missing:
            raise ScriptError(f"없는 기록: {', '.join(missing)}")
        rows = [have[r] for r in want]
    elif last:
        rows = [d for d in log if not d["id"].startswith("run:")][-int(last):]
    else:
        rows = []
    L = [f"# {title or '새 스크립트'} — equion script new가 만든 초안({date.today().isoformat()}) · 고쳐 쓰세요",
         "# 한 줄 = equion 명령 하나 · ## 제목 = 단계 묶음 · param 이름 = 값 · {이름} · expect … --flag(문법: docs/reference/formats.md)"]
    if not rows:
        L += ["", "## 자료", "data build --inbox ask --use", "assemble", "", "## 과거 재현", "hs", "", "## 전망", "sim"]
        return "\n".join(L) + "\n"
    head = None
    seen = set()
    for d in rows:
        if d["id"] in seen:
            continue
        seen.add(d["id"])
        line = clean_command(d.get("command") or "")
        kind = d["id"].split(":", 1)[0]
        h = HEAD_KO.get(line.split(" ", 1)[0] if line else kind, KIND_KO.get(kind, kind))
        if h != head:
            L += ["", f"## {h}"]
            head = h
        if not line:
            L.append(f"# {d['id']} — 명령이 적혀 있지 않습니다")
            continue
        why = reg.allowed(shlex.split(line), where="script")
        L.append(f"# (스크립트에서 부를 수 없음 — {why}) {line}" if why else f"{line}" + f"   # ← {d['id']}")
    return "\n".join(L) + "\n"


def new_script(p, name: str, records: List[str] = None, last: int = None, title: str = None, force: bool = False,
               who: str = None, command: str = None) -> str:
    """FLOWS/<이름>.eqs를 만든다(바뀜 기록에 남는다) → 프로젝트 기준 경로."""
    from ..projects.records import _who, history_of
    nm = name[:-4] if name.lower().endswith(".eqs") else name
    if not re.match(r"^[A-Za-z0-9가-힣][\w\-가-힣]*$", os.path.basename(nm)):
        raise ScriptError(f"스크립트 이름은 글자·숫자·_·-: {name!r}")
    rel = (nm if "/" in nm.replace(os.sep, "/") else f"{FLOWS}/{nm}") + ".eqs"
    from ..projects.config import inside
    path = os.path.normpath(os.path.join(p.root, rel))
    if not inside(p.root, path):
        raise ScriptError(f"스크립트는 프로젝트 안에 둡니다 — {name!r}는 프로젝트 밖입니다")
    rel = os.path.relpath(path, p.root)
    if os.path.exists(path) and not force:
        raise ScriptError(f"이미 있는 스크립트 {rel} — 덮으려면 --force")
    text = draft(p, records, last, title or nm)
    history_of(p).write_files({rel.replace(os.sep, "/"): text}, _who(who), command or f"script new {nm}",
                              note=f"스크립트 초안 — 기록 {len(records or [])}" + (f" · 최근 {last}" if last else ""))
    return rel.replace(os.sep, "/")


def to_python(sc: Script) -> str:
    """스크립트 → 같은 일을 하는 Python(eqn.script.session — 같은 명령·같은 기록·같은 실행 기록)."""
    q = repr
    params = ", ".join(f"{k}={q(' '.join(v))}" for k, v in sc.params.items())
    out = ["#!/usr/bin/env python3",
           "# -*- coding: utf-8 -*-",
           f'"""{sc.path}를 Python으로 — equion script export --py가 만들었다({date.today().isoformat()}).',
           "",
           "같은 단계를 같은 차례로 한다: s.cmd(…)는 그 명령 한 줄을 그대로(기록·바뀜 기록도 같다), s.expect(…)는 확인, s.py(…)는 Python",
           "단계. 끝나면 실행 기록 run:…이 남는다. 반복·조건·직접 계산을 더하려면 이 파일을 고쳐 쓴다 — 프로젝트 API는 s.p(eqn.project),",
           "앞 단계의 기록 이름은 s.records(\"hs\") · 기록은 eqn.project(...)의 저장소에서 읽는다.",
           "",
           f"    python {os.path.splitext(sc.path)[0]}.py" + ("   # 매개변수: equion run 이 파일 --set 이름=값" if sc.params else ""),
           '"""',
           "",
           "import equion as eqn",
           ""]
    if sc.title:
        out[3:3] = ["", sc.title]
    out.append(f"P = eqn.params({params})" + ("   # param — 목록은 띄어 쓴 글자" if params else ""))
    out += ["", f"with eqn.script.session(__file__, params=vars(P), script={q(sc.path)}) as s:"]
    sec = None
    body = 0
    for st in sc.steps:
        if st.section != sec:
            sec = st.section
            if sec:
                out.append(f"    s.section({q(sec)})")
        if st.kind == "cmd":
            out.append(f"    s.cmd({q(st.text)})")
        elif st.kind == "expect":
            out.append(f"    s.expect_line({q(st.text)})")
        else:
            out.append(f"    s.py({q(st.text)})")
        body += 1
    if not body:
        out.append("    pass")
    out.append("")
    out.append("print(s.result.text())")
    return "\n".join(out) + "\n"


def export_py(p, path: str, out: str = None, force: bool = False) -> str:
    """스크립트를 Python 파일로(기본: 같은 자리의 .py) → 프로젝트 기준 경로. 문제가 있는 스크립트는 ScriptError."""
    full = path if os.path.isabs(path) else os.path.join(p.root, path)
    sc = parse(p.root, full)
    if sc.problems:
        raise ScriptError("스크립트 문제 — 내보내지 않았습니다:\n" + "\n".join(f"  - {x}" for x in sc.problems))
    dst = out or os.path.splitext(full)[0] + ".py"
    dst = os.path.normpath(dst if os.path.isabs(dst) else os.path.join(p.root, dst))
    from ..projects.config import inside
    if not inside(p.root, dst):
        raise ScriptError(f"내보낼 파일은 프로젝트 안에 — {dst}는 프로젝트 밖입니다")
    if os.path.exists(dst) and not force:
        raise ScriptError(f"이미 있는 파일 {os.path.relpath(dst, p.root)} — 덮으려면 --force")
    os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
    with open(dst, "w", encoding="utf-8", newline="\n") as f:
        f.write(to_python(sc))
    return os.path.relpath(dst, p.root).replace(os.sep, "/")
