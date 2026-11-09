#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Equion 스크립트(`.eqs`) 문법 (D36) — 한 줄이 `equion` 명령 하나다.

    # FLOWS/monthly.eqs — 월간 전망                  첫 주석 줄이 제목
    param scenarios = base oil20                     매개변수와 기본값(띄어 쓴 값은 목록) — 실행할 때 --set scenarios=base
    ## 자료                                           단계 묶음 제목
    data build --inbox ask --use                     등록부의 명령(앞의 equion은 써도 되고 빼도 된다)
    hs main --range 2005Q1:last
    expect hs Y.rmspe < 2% --flag                    확인 — 어긋나면 멈추거나(--stop, 기본) 표시하고 계속(--flag)
    sim {scenarios} --model main                     {이름} — 매개변수·내장 값(vintage·last·today·model·run)·앞 단계의 기록({hs}·{sim:base})
    run FLOWS/data.eqs                               다른 스크립트를 그 자리에 포함(레고)
    py scripts/extra.py                              Python 단계(명령줄에서만)

반복문·조건문·변수 계산·셸 명령은 없다 — 위에서 아래로 읽으면 무엇이 일어날지 다 보이고, 미리보기(`--dry-run`)가 정확하며, AI가 써도
등록부의 명령만 돈다(`equion.registry.allowed(..., where='script')`). 모자라면 Python(`equion script export --py`).
"""

import os
import re
import shlex
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from .. import registry as reg

FORMAT = "equion-script"
FORMAT_VERSION = 1
BUILTINS = {"vintage": "지금 자료 회차", "last": "자료의 마지막 기", "today": "오늘(YYYY-MM-DD)", "model": "기본 모형([hs] model)",
            "run": "이 실행 기록의 이름"}
RECORD_REFS = {"est": "추정", "hs": "과거 재현", "sim": "전망", "an": "분석"}    # {hs} — 이 실행의 앞 단계가 만든 기록
RESERVED = set(BUILTINS) | set(RECORD_REFS)
PLACE = re.compile(r"\{\{|\}\}|\{([A-Za-z_][A-Za-z0-9_]*)(?::([^{}\s]+))?\}")
PARAM = re.compile(r"^param\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$")
HEAD = re.compile(r"^##\s+(.+?)\s*$")
COND = re.compile(r"^([A-Za-z_][\w]*(?:\.[A-Za-z_]\w*)?(?:\[[\w\-]+\])?)\s*(<=|>=|==|!=|<|>)\s*(-?\d+(?:\.\d+)?(?:[eE]-?\d+)?)\s*(%?)$")
EXPECT_KINDS = ("hs", "sim", "est")


class ScriptError(ValueError):
    """스크립트 문법·검사 문제."""


@dataclass
class Step:
    """스크립트의 단계 하나 — 명령(cmd)·확인(expect)·Python(py)."""

    n: int
    kind: str
    text: str                    # 줄(주석·앞의 equion을 뺌, {…}는 그대로)
    section: str = ""
    where: str = ""              # 파일:줄
    stop: bool = True            # expect: --stop(기본) · --flag

    @property
    def tokens(self) -> List[str]:
        """줄의 낱말(shlex)."""
        return shlex.split(self.text)

    def to_dict(self) -> dict:
        """사전."""
        return {"n": self.n, "kind": self.kind, "text": self.text, "section": self.section, "where": self.where,
                "stop": self.stop}


@dataclass
class Script:
    """읽은 스크립트 — 매개변수 기본값·단계(포함한 스크립트를 펼친 뒤)·제목·문제."""

    path: str                                   # 프로젝트 기준
    title: str = ""
    params: Dict[str, List[str]] = field(default_factory=dict)
    steps: List[Step] = field(default_factory=list)
    sections: List[str] = field(default_factory=list)
    files: List[str] = field(default_factory=list)       # 이 스크립트와 포함한 스크립트
    py: List[str] = field(default_factory=list)          # Python 단계의 파일
    problems: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """문제가 없으면 참."""
        return not self.problems


def strip_comment(line: str) -> str:
    """줄 끝 주석을 뺀다 — `#`가 줄 처음이거나 앞이 빈칸일 때만(따옴표 안·`an:x#2`의 #는 그대로)."""
    q = None
    for i, ch in enumerate(line):
        if q:
            if ch == q:
                q = None
            continue
        if ch in "'\"":
            q = ch
        elif ch == "#" and (i == 0 or line[i - 1].isspace()):
            return line[:i].rstrip()
    return line


def read_text(path: str) -> str:
    """스크립트 파일(UTF-8, BOM 무관)."""
    with open(path, encoding="utf-8-sig") as f:
        return f.read()


def _rel(root, path):
    return os.path.relpath(path, root).replace(os.sep, "/")


def parse(root: str, path: str, _stack: tuple = (), _section: str = "") -> Script:
    """스크립트를 읽는다 — `run 다른.eqs`는 그 자리에 펼친다(매개변수는 하나의 이름 공간 — 먼저 적은 기본값이 이긴다).
    문제는 `.problems`에 모은다(첫 문제에서 멈추지 않는다). 경로는 프로젝트 폴더 기준."""
    full = path if os.path.isabs(path) else os.path.join(root, path)
    rel = _rel(root, full)
    sc = Script(rel, files=[rel])
    try:
        text = read_text(full)
    except FileNotFoundError:
        sc.problems.append(f"스크립트가 없습니다: {rel}")
        return sc
    section = _section
    for no, raw in enumerate(text.split("\n"), 1):
        where = f"{rel}:{no}"
        s = raw.strip()
        if not s:
            continue
        m = HEAD.match(s)
        if m:
            section = strip_comment(" " + m[1]).strip()
            sc.sections.append(section)
            continue
        if s.startswith("#"):
            if not sc.title and not sc.steps and not sc.params:
                sc.title = s.lstrip("#").strip()
            continue
        s = strip_comment(s).strip()
        if not s:
            continue
        try:
            toks = shlex.split(s)
        except ValueError as e:
            sc.problems.append(f"{where}: 줄을 읽을 수 없습니다 — {e}")
            continue
        if toks and toks[0] == "equion":
            toks = toks[1:]
            s = s.split(None, 1)[1] if len(s.split(None, 1)) > 1 else ""
        if not toks:
            continue
        head = toks[0]
        if head == "param":
            pm = PARAM.match(s)
            if not pm:
                sc.problems.append(f"{where}: param은 'param 이름 = 값 …' 꼴입니다")
                continue
            name = pm[1]
            if name in RESERVED:
                sc.problems.append(f"{where}: '{name}'는 내장 이름이라 param으로 쓸 수 없습니다({', '.join(sorted(RESERVED))})")
                continue
            if name in sc.params:
                sc.problems.append(f"{where}: param {name}을 두 번 적었습니다")
                continue
            try:
                sc.params[name] = shlex.split(pm[2])
            except ValueError as e:
                sc.problems.append(f"{where}: param 값을 읽을 수 없습니다 — {e}")
            continue
        if head == "run":
            if len(toks) != 2:
                sc.problems.append(f"{where}: 'run 다른.eqs' — 스크립트 이름 하나만(매개변수는 하나의 이름 공간이라 --set은 실행할 때)")
                continue
            target = toks[1]
            if not target.lower().endswith(".eqs"):
                sc.problems.append(f"{where}: run은 다른 스크립트(.eqs)를 포함합니다 — Python은 'py {target}'")
                continue
            tfull = os.path.normpath(os.path.join(root, target))
            trel = _rel(root, tfull)
            if trel in _stack or trel == rel:
                sc.problems.append(f"{where}: 스크립트가 돌고 돕니다: {' → '.join((*_stack, rel, trel))}")
                continue
            if not os.path.isfile(tfull):
                sc.problems.append(f"{where}: 포함할 스크립트가 없습니다: {trel}")
                continue
            sub = parse(root, tfull, (*_stack, rel), section)
            sc.problems += sub.problems
            for k, v in sub.params.items():
                sc.params.setdefault(k, v)
            sc.steps += sub.steps
            sc.sections += [x for x in sub.sections if x not in sc.sections]
            sc.files += [x for x in sub.files if x not in sc.files]
            sc.py += [x for x in sub.py if x not in sc.py]
            continue
        if head == "py":
            if len(toks) < 2 or not toks[1].lower().endswith(".py"):
                sc.problems.append(f"{where}: 'py 스크립트.py [--set 이름=값 …]'")
                continue
            if not os.path.isfile(os.path.join(root, toks[1])):
                sc.problems.append(f"{where}: Python 스크립트가 없습니다: {toks[1]}")
            sc.py.append(toks[1].replace(os.sep, "/"))
            sc.steps.append(Step(0, "py", s, section, where))
            continue
        if head == "expect":
            try:
                _, _, stop = parse_expect(toks[1:])
            except ScriptError as e:
                sc.problems.append(f"{where}: {e}")
                continue
            sc.steps.append(Step(0, "expect", s, section, where, stop))
            continue
        why = reg.allowed(toks, where="script")
        if why:
            sc.problems.append(f"{where}: {why}")
            continue
        sc.steps.append(Step(0, "cmd", s, section, where))
    if not _stack:
        for i, st in enumerate(sc.steps, 1):
            st.n = i
        _check_places(sc)
    return sc


def parse_expect(toks: List[str]):
    """`expect` 뒤 낱말 → (대상, (지표, 비교, 값), stop)."""
    flags = [t for t in toks if t in ("--stop", "--flag")]
    rest = [t for t in toks if t not in ("--stop", "--flag")]
    if len(flags) > 1:
        raise ScriptError("expect에는 --stop과 --flag 중 하나만")
    if len(rest) < 2:
        raise ScriptError("expect 대상 조건 [--stop·--flag] — 예: expect hs Y.rmspe < 2% --flag")
    target = rest[0]
    cond = " ".join(rest[1:])
    m = COND.match(cond)
    if not m:
        raise ScriptError(f"조건을 읽을 수 없습니다: {cond!r} — '지표 비교 값' 꼴(예: Y.rmspe < 2% · failed == 0 · Y.growth[2021] > 0)")
    if not (target in EXPECT_KINDS or ":" in target or PLACE.fullmatch(target)):
        raise ScriptError(f"expect 대상은 hs · sim · est(이 실행의 앞 단계 기록) 또는 기록 이름(hs:hs_0003 · {{sim:base}}): {target!r}")
    return target, (m[1], m[2], float(m[3])), flags != ["--flag"]


def places(text: str) -> List[tuple]:
    """줄의 {이름}·{이름:거르기} 목록."""
    return [(m[1], m[2]) for m in PLACE.finditer(text) if m[1]]


def _makes(step: Step) -> Optional[str]:
    """이 단계가 만드는 기록 종류(est·hs·sim·an) — 명령의 첫 낱말."""
    if step.kind != "cmd":
        return None
    first = step.text.split(None, 1)[0]
    if first in RECORD_REFS:
        return first
    return None


def _check_places(sc: Script):
    made = set()
    for st in sc.steps:
        for name, filt in places(st.text):
            if name in sc.params or name in BUILTINS:
                if filt:
                    sc.problems.append(f"{st.where}: {{{name}:{filt}}} — ':거르기'는 기록({', '.join(RECORD_REFS)})에만")
                continue
            if name in RECORD_REFS:
                if name not in made:
                    sc.problems.append(f"{st.where}: {{{name}}} — 앞 단계에 {RECORD_REFS[name]}({name})가 없습니다")
                continue
            sc.problems.append(f"{st.where}: 모르는 이름 {{{name}}} — param으로 적거나 내장 값({', '.join(BUILTINS)}) · "
                               f"앞 단계의 기록({', '.join('{' + k + '}' for k in RECORD_REFS)})")
        if st.kind == "expect":
            target = st.tokens[1]
            if target in EXPECT_KINDS and target not in made:
                sc.problems.append(f"{st.where}: expect {target} — 앞 단계에 {RECORD_REFS[target]}({target})가 없습니다")
        k = _makes(st)
        if k:
            made.add(k)


def _q(v: str) -> str:
    return shlex.quote(v) if (not v or any(c.isspace() or c in "'\"\\" for c in v)) else v


def resolve(text: str, values: Dict[str, object], refs: Callable[[str, Optional[str]], List[str]] = None,
            keep: set = ()) -> str:
    """{이름}을 값으로 — 목록은 띄어 쓰고(빈칸·따옴표가 든 값만 따옴표), {{·}}는 글자 그대로. keep의 이름은 그대로 둔다(미리보기)."""
    def one(m):
        tok = m[0]
        if tok == "{{":
            return "{"
        if tok == "}}":
            return "}"
        name, filt = m[1], m[2]
        if name in keep:
            return tok
        if name in RECORD_REFS and name not in values:
            if refs is None:
                return tok
            ids = refs(name, filt)
            return " ".join(_q(x) for x in ids)
        if name not in values:
            raise ScriptError(f"모르는 이름 {{{name}}}")
        v = values[name]
        if isinstance(v, (list, tuple)):
            return " ".join(_q(str(x)) for x in v)
        return _q(str(v))
    return PLACE.sub(one, text)
