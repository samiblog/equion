#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""등록부 (D37) — 분석과 명령을 한 곳에 적는다: 이름·대상 종류·옵션(종류·기본값·설명)·결과·만드는 것.

명령줄 옵션(`equion an <분석> --help`), Desk의 옵션 폼, 도움말, Claude용 안내가 모두 여기서 나온다. 노트의 ```` ```equion ```` 블록과
스크립트가 부를 수 있는 명령의 **허용 목록**이기도 하다 — 방정식 파서의 허용 목록과 같은 생각이다(임의의 코드는 돌지 않는다).

분석의 계산은 `equion.projects.analyses`가 엔진(워크파일 API·`equion.stats`)으로 한다 — 여기에는 이름과 모양만 둔다.
"""

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

TARGET_KO = {"series": "시리즈", "group": "묶음", "expr": "식(log(Y) 등)", "part": "부품(블록:목표)", "est": "추정 기록",
             "model": "모형", "block": "블록", "records": "기록 여럿", "assign": "이름 = 식"}
MAKES_KO = {None: "—", "definition": "시리즈 정의(series.toml)", "derived": "파생식(derived.txt)",
            "candidate": "식 후보(est:)"}


@dataclass
class Opt:
    """분석의 옵션 하나 — 명령줄 `--이름`과 Desk 폼의 칸."""

    name: str
    type: str = "str"                 # str · int · float · bool · choice · list
    default: object = None
    choices: Tuple[str, ...] = ()
    help: str = ""
    metavar: Optional[str] = None


@dataclass
class Analysis:
    """분석 하나 — 이름·대상 종류·옵션·결과·만드는 것·계산 함수."""

    name: str
    label: str
    group: str
    targets: Tuple[str, ...]
    options: List[Opt] = field(default_factory=list)
    makes: Optional[str] = None
    results: str = ""
    help: str = ""
    example: str = ""
    run: Optional[Callable] = None     # run(project, target, **opts) → AnOut
    count: str = "any"                 # 대상이 시리즈·식 몇 개인가 — one · two · many(둘 이상) · any (Desk의 우클릭 메뉴가 고른 수로 거른다)

    def defaults(self) -> dict:
        """옵션 기본값."""
        return {o.name: o.default for o in self.options}


ANALYSES: Dict[str, Analysis] = {}

# 노트·스크립트가 부를 수 있는 명령 — (첫 낱말, 둘째 낱말 또는 None): 정의 파일을 바꾸는가
COMMANDS: Dict[Tuple[str, Optional[str]], dict] = {
    ("an", None): {"changes": False, "help": "분석(등록부의 분석만) — 기록 an:"},
    ("est", None): {"changes": False, "help": "식 추정 — 기록 est:"},
    ("hs", None): {"changes": False, "help": "과거 재현 — 기록 hs:"},
    ("sim", None): {"changes": False, "help": "전망·시나리오 — 기록 sim:"},
    ("compare", None): {"changes": False, "help": "기록 비교"},
    ("assemble", None): {"changes": False, "help": "조립 검사"},
    ("ident", None): {"changes": False, "help": "항등식 검사"},
    ("data", "list"): {"changes": False, "help": "자료 회차 목록"},
    ("data", "diff"): {"changes": False, "help": "회차 차이"},
    ("data", "impact"): {"changes": False, "help": "회차 영향"},
    ("work", "list"): {"changes": False, "help": "기록 목록"},
    ("work", "show"): {"changes": False, "help": "기록 하나"},
}
CHANGING = {"adopt", "propose", "history", "export", "note", "report", "new", "run", "convert", "script"}

# 스크립트(.eqs, D36)가 부를 수 있는 명령 — 노트의 명령에 더해 자료 만들기·채택·노트·보고서·내보내기(정의 파일을 바꾸는 줄은
# 실행 전 미리보기에 따로 보인다 — effects). 스크립트 안의 `run 다른.eqs`·`py x.py`는 명령이 아니라 스크립트 문법이다.
SCRIPT_COMMANDS: Dict[Tuple[str, Optional[str]], str] = {
    ("data", "build"): "자료 만들기(--inbox·--use)", ("data", "use"): "회차 바꾸기", ("data", "add"): "원자료 넣기",
    ("data", "inbox"): "받은 원자료 보기", ("adopt", None): "채택", ("note", "run"): "노트 실행", ("note", "check"): "노트 검사",
    ("report", "new"): "새 보고서", ("report", "add"): "보고서로 보내기", ("report", "check"): "보고서 검사",
    ("report", "update"): "보고서를 새 기록으로", ("export", None): "엑셀로 내보내기", ("work", "pin"): "기록 고정",
    ("work", "memo"): "기록 메모", ("check", None): "방정식 파일 검사",
}


def _opt(tokens: List[str], name: str) -> Optional[str]:
    for i, t in enumerate(tokens):
        if t == name and i + 1 < len(tokens):
            return tokens[i + 1]
        if t.startswith(name + "="):
            return t.split("=", 1)[1]
    return None


def _args(tokens: List[str]) -> List[str]:
    """선택지가 아닌 인자(값을 받는 선택지의 값은 뺀다 — 흔한 것만)."""
    takes = {"--as", "--range", "--model", "--smpl", "--vs", "--swap", "--rows", "--show", "--digits", "--title", "--under",
             "--key", "--from", "--to", "--region", "--xlsx", "--note", "--source", "--inbox", "--adopt", "--block", "-p",
             "--project", "--for", "--memo", "--vintage", "--mode", "--start", "--end"}
    out, skip = [], False
    for t in tokens:
        if skip:
            skip = False
            continue
        if t in takes:
            skip = True
            continue
        if t.startswith("-"):
            continue
        out.append(t)
    return out


def effects(tokens: List[str]) -> List[str]:
    """명령 한 줄이 바꾸는 정의 파일·폴더(기록 work/<종류>/ 말고) — 없으면 []. 스크립트 미리보기와 노트의 허용 목록이 쓴다."""
    if not tokens:
        return []
    first, rest = tokens[0], tokens[1:]
    second = rest[0] if rest and not rest[0].startswith("-") else None
    pos = _args(rest)
    if first == "data":
        if second == "build":
            out = []
            if _opt(rest, "--inbox") not in (None, "no"):
                out += ["DATA/raw/(받은 원자료)", "DATA/series.toml"]
            if "--use" in rest:
                out.append("equion.toml [data] vintage")
            return out
        if second == "use":
            return ["equion.toml [data] vintage"]
        if second == "add":
            return ["DATA/raw/"] + (["DATA/series.toml"] if _opt(rest, "--source") else [])
        return []
    if first == "est":
        return ["EQUATIONS/adopted.toml"] if ("--adopt" in rest or any(t.startswith("--adopt=") for t in rest)) else []
    if first == "adopt":
        return ["EQUATIONS/adopted.toml"]
    if first == "an" and second == "keep":
        return ["정의(DATA/series.toml·derived.txt) 또는 식 후보"]
    if first == "an" and _opt(rest, "--note"):
        return [_opt(rest, "--note")]
    if first == "note" and second == "run":
        return pos[1:2] or ["notes/"]
    if first == "report" and second in ("new", "add", "update"):
        if second == "update" and "--dry-run" in rest:
            return []
        return pos[1:2] or ["reports/"]
    if first == "export":
        return [(_opt(rest, "--xlsx") or "exports/") + "(내보내기)"]
    if first == "work" and second in ("pin", "memo", "unpin"):
        return ["work/marks.json"]
    if first in ("propose", "history"):
        return ["정의 파일"]
    return []


def register(a: Analysis) -> Analysis:
    """분석을 등록한다(이름이 겹치면 오류)."""
    if a.name in ANALYSES:
        raise ValueError(f"이미 등록된 분석: {a.name}")
    ANALYSES[a.name] = a
    return a


def analyses(for_kind: str = None) -> List[Analysis]:
    """등록된 분석(등록 순) — for_kind를 주면 그 대상 종류를 받는 것만."""
    _load()
    return [a for a in ANALYSES.values() if for_kind is None or for_kind in a.targets]


def get(name: str) -> Analysis:
    """분석 하나(이름).

    오류
        KeyError: 없는 분석(있는 분석 목록과 함께)
    """
    _load()
    if name not in ANALYSES:
        raise KeyError(f"없는 분석: {name} (있는 분석: {', '.join(ANALYSES)})")
    return ANALYSES[name]


def names_project(tok: str) -> bool:
    """낱말이 프로젝트를 고르는 선택지(`-p` · `-pX` · `--project` · `--project=X` · 줄인 `--proj`)인가."""
    t = str(tok)
    if t == "-p" or (t.startswith("-p") and not t.startswith("--")):
        return True
    head = t.split("=", 1)[0]
    return len(head) >= 4 and head.startswith("--p") and "--project".startswith(head)


def allowed(tokens: List[str], where: str = "note") -> Optional[str]:
    """명령 한 줄이 허용 목록에 있으면 None, 아니면 까닭.

    where='note'(노트의 블록): 계산·보기 명령만 — 정의 파일을 바꾸는 줄(`est --adopt`·`an keep` 등)은 안 된다.
    where='script'(스크립트 .eqs): 그에 더해 자료 만들기·채택·노트 실행·보고서·내보내기(SCRIPT_COMMANDS).
    """
    if not tokens:
        return "빈 명령"
    if any(names_project(t) for t in tokens[1:]):
        return (f"{'노트' if where == 'note' else '스크립트'}의 줄은 그 프로젝트에서만 돈다 — -p/--project 로 다른 프로젝트를 고를 수 없습니다"
                "(다른 프로젝트는 그 폴더의 노트·스크립트·터미널에서)")
    first = tokens[0]
    second = tokens[1] if len(tokens) > 1 and not tokens[1].startswith("-") else None
    known = ((first, None) in COMMANDS or (first, second) in COMMANDS)
    if where == "script":
        if known or (first, None) in SCRIPT_COMMANDS or (first, second) in SCRIPT_COMMANDS:
            return None
        if first == "run":
            return "스크립트 안에서 다른 스크립트는 `run 다른.eqs`(포함), Python은 `py x.py` 줄로"
        if first in CHANGING or first in ("data", "work", "new", "convert", "info"):
            names = sorted({' '.join(x for x in k if x) for k in (*COMMANDS, *SCRIPT_COMMANDS)})
            return f"'{' '.join(tokens[:2])}'는 스크립트에서 부를 수 없습니다 — 부를 수 있는 명령: {', '.join(names)}"
        return f"모르는 명령 '{first}' — 스크립트의 줄은 등록부의 명령만"
    if known:
        ch = effects(tokens)
        if ch:
            return (f"'{' '.join(tokens[:2])}'의 이 줄은 정의 파일을 바꿉니다({', '.join(ch)}) — 노트의 블록은 계산·보기만. "
                    "바꾸는 명령은 터미널이나 스크립트에서")
        return None
    if first in CHANGING or first == "data":
        return (f"'{' '.join(tokens[:2])}'는 노트에서 부를 수 없습니다 — 노트의 블록은 계산·보기 명령만"
                f"({', '.join(sorted({' '.join(x for x in k if x) for k in COMMANDS}))}). 파일을 바꾸는 명령은 터미널에서")
    return f"모르는 명령 '{first}' — 노트의 블록은 등록부의 명령만"


def table() -> List[dict]:
    """분석 목록 표(이름·갈래·대상·만드는 것·결과) — `equion an list`·Claude 안내가 쓴다."""
    return [{"분석": a.name, "이름": a.label, "갈래": a.group, "대상": " · ".join(TARGET_KO[t] for t in a.targets),
             "만드는 것": MAKES_KO[a.makes], "결과": a.results} for a in analyses()]


def _load():
    if not ANALYSES:
        from .projects import analyses as _impl  # noqa: F401 — 분석 구현이 register()로 등록한다
