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
CHANGING = {"adopt", "propose", "history", "export", "note", "report", "new", "run", "convert"}


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


def allowed(tokens: List[str]) -> Optional[str]:
    """노트 블록의 명령 한 줄이 허용 목록에 있으면 None, 아니면 까닭."""
    if not tokens:
        return "빈 명령"
    first = tokens[0]
    second = tokens[1] if len(tokens) > 1 and not tokens[1].startswith("-") else None
    if (first, None) in COMMANDS:
        return None
    if (first, second) in COMMANDS:
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
