#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""프로젝트 설정 `equion.toml` 읽기·검사 (D32).

    [project]                      이름·형식 판(선택)
    [data]  file = "…"             자료 파일 하나(첫 열이 날짜) — 또는 series · derived · freq · vintage(자료 정의·회차, D34)
    [block] 이름 = "파일" 또는 { file = "…", desc = "…" }      블록 = 방정식 파일 하나
    [model.이름] blocks · include · exclude · desc              조립 — 모형 안에 모형(include), 식 빼기(exclude)
    [group] 이름 = [시리즈…] 또는 { series = […], transform, desc }
    [hs]    model · range("S:E") · mode                         HS 기본값
    [criteria] alpha · tests · t_min · [criteria.signs]          판단 기준 — 추정 기록의 '기준'·est --adopt if_pass (D35)
    [forecast] model · range · assume · addfactors · fill · mode  전망 기본값 — equion sim (K4)

읽기는 표준 라이브러리 `tomllib`. 이름은 영문·숫자·`_`(첫 글자는 영문). 문제는 모아서 한꺼번에 알린다(ProjectError).
"""

import os
import re
import tomllib
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ..data.periods import normalize_freq

FORMAT = "equion-project"
FORMAT_VERSION = 1
CONFIG_NAME = "equion.toml"
NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
VID_RE = re.compile(r"^d\d{4}-\d{2}[a-z]+$")      # 자료 회차 이름(d2026-11a)
MODES = ("dynamic", "static", "fit")

# 나중 단계에서 쓰는 표(지금은 읽기만 하고 그대로 둔다 — 경고하지 않는다)
RESERVED_TABLES = ("estimate", "addfactors", "assume")
FILLS = ("last", "growth", "trend", "none")
TESTS = ("lm", "white", "bp", "lb", "arch", "jb", "reset")      # 기준에 넣을 수 있는 진단


class ProjectError(ValueError):
    """프로젝트 설정·부품·조립의 문제 — 여러 개를 모아 한꺼번에 알린다(.problems)."""

    def __init__(self, problems):
        self.problems = [problems] if isinstance(problems, str) else list(problems)
        super().__init__("\n".join(self.problems))


@dataclass
class BlockSpec:
    name: str
    file: str            # 프로젝트 폴더 기준 상대 경로(표시용)
    path: str            # 절대 경로
    desc: str = ""


@dataclass
class ModelSpec:
    name: str
    blocks: List[str] = field(default_factory=list)
    include: List[str] = field(default_factory=list)
    exclude: List[str] = field(default_factory=list)
    desc: str = ""


@dataclass
class GroupSpec:
    name: str
    series: List[str]
    transform: Optional[str] = None
    desc: str = ""


@dataclass
class ProjectConfig:
    root: str
    path: str
    name: str
    data_file: Optional[str]
    data_path: str
    blocks: Dict[str, BlockSpec]
    models: Dict[str, ModelSpec]
    groups: Dict[str, GroupSpec]
    hs: dict
    raw: dict
    warnings: List[str] = field(default_factory=list)
    series_file: Optional[str] = None      # 자료 정의(있으면 자료 회차를 쓴다)
    derived_file: Optional[str] = None
    freq: Optional[str] = None
    vintage: Optional[str] = None          # 지금 자료 회차
    criteria: dict = field(default_factory=dict)   # 판단 기준 {alpha, tests, t_min, signs: {부품: {항: '+'|'-'}}}
    forecast: dict = field(default_factory=dict)   # 전망 기본값 {model, range, assume, addfactors, fill, mode}

    @property
    def uses_vintages(self) -> bool:
        """자료 정의·회차를 쓰면 참(아니면 자료 파일 하나)."""
        return bool(self.series_file)

    def default_model(self) -> Optional[str]:
        """[hs] model, 없으면 모형이 하나일 때 그것."""
        m = self.hs.get("model")
        if m:
            return m
        return next(iter(self.models)) if len(self.models) == 1 else None


def find_config(path: str = ".") -> str:
    """폴더(또는 equion.toml 경로) → equion.toml 경로. 없으면 ProjectError."""
    p = os.path.abspath(path)
    if os.path.isdir(p):
        p = os.path.join(p, CONFIG_NAME)
    if not os.path.isfile(p):
        raise ProjectError(f"프로젝트 설정 파일이 없습니다: {p} — 프로젝트 폴더에서 실행하거나 경로를 주세요"
                           f"(새 프로젝트: equion new 폴더 --template desk)")
    return p


def _str_list(val, where: str, problems: List[str]) -> List[str]:
    if val is None:
        return []
    if isinstance(val, str):
        return [val]
    if isinstance(val, list) and all(isinstance(x, str) for x in val):
        return list(val)
    problems.append(f"{where}: 글자 목록이어야 합니다 — {val!r}")
    return []


def _check_name(name: str, what: str, problems: List[str]) -> bool:
    if not NAME_RE.match(name):
        problems.append(f"{what} 이름 '{name}': 영문으로 시작하고 영문·숫자·_만 씁니다(한글 이름은 desc로)")
        return False
    return True


def load_config(path: str = ".") -> ProjectConfig:
    """equion.toml을 읽고 검사해 ProjectConfig를 돌려준다. 문제가 있으면 모두 모아 ProjectError."""
    cfg_path = find_config(path)
    root = os.path.dirname(cfg_path)
    try:
        with open(cfg_path, "rb") as f:
            raw = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise ProjectError(f"{CONFIG_NAME} 문법 오류: {e}") from None
    problems: List[str] = []
    warnings: List[str] = []

    known = {"project", "data", "block", "model", "group", "hs", "criteria", "forecast", *RESERVED_TABLES}
    for k in raw:
        if k not in known:
            warnings.append(f"{CONFIG_NAME}: 알 수 없는 표 [{k}] — 쓰지 않습니다")

    # [project]
    proj = raw.get("project", {})
    if not isinstance(proj, dict):
        problems.append("[project]는 표여야 합니다")
        proj = {}
    name = str(proj.get("name") or os.path.basename(root))
    fmt = proj.get("format", FORMAT)
    if fmt != FORMAT:
        problems.append(f"[project] format = {fmt!r} — '{FORMAT}'이어야 합니다")
    ver = proj.get("format_version", FORMAT_VERSION)
    if not isinstance(ver, int) or ver < 1:
        problems.append(f"[project] format_version = {ver!r} — 1 이상의 정수")
    elif ver > FORMAT_VERSION:
        problems.append(f"이 프로젝트는 형식 판 {ver}입니다 — 이 equion은 {FORMAT_VERSION}까지 읽습니다(equion을 새 판으로)")

    # [data] — 자료 파일 하나(file) 또는 자료 정의·회차(series · derived · freq · vintage)
    data = raw.get("data", {})
    if not isinstance(data, dict):
        problems.append("[data]는 표여야 합니다")
        data = {}
    data_file, data_path = data.get("file"), ""
    series_file, derived_file, freq, vintage = data.get("series"), data.get("derived"), data.get("freq"), data.get("vintage")
    for k in data:
        if k not in ("file", "series", "derived", "freq", "vintage"):
            warnings.append(f"[data] {k}: 알 수 없는 키 — 쓰지 않습니다")
    if data_file and series_file:
        problems.append("[data] file과 series를 함께 쓸 수 없습니다 — 자료 파일 하나(file) 또는 자료 정의·회차(series)")
    elif series_file:
        if not os.path.isfile(os.path.join(root, series_file)):
            problems.append(f"[data] series = {series_file!r}: 자료 정의 파일이 없습니다")
        if derived_file and not os.path.isfile(os.path.join(root, derived_file)):
            problems.append(f"[data] derived = {derived_file!r}: 파생식 파일이 없습니다")
        if not freq:
            problems.append("[data] freq가 없습니다 — 자료 회차의 주기 \"Q\"·\"M\"·\"A\"")
        else:
            try:
                freq = normalize_freq(freq)
            except ValueError as e:
                problems.append(f"[data] freq: {e}")
        if vintage is not None and (not isinstance(vintage, str) or not VID_RE.match(vintage)):
            problems.append(f"[data] vintage = {vintage!r} — 회차 이름은 d연도-월과 글자(예: \"d2026-11a\") — "
                            "equion data list로 확인")
    elif not data_file:
        problems.append("[data] file이 없습니다 — 자료 파일(첫 열이 날짜인 csv·xlsx) 또는 자료 정의(series·freq)를 적으세요. "
                        "예: file = \"DATA/data.csv\"")
    else:
        data_path = os.path.normpath(os.path.join(root, data_file))
        if not os.path.isfile(data_path):
            problems.append(f"[data] file = {data_file!r}: 파일이 없습니다")

    # [block]
    blocks: Dict[str, BlockSpec] = {}
    for bname, val in (raw.get("block") or {}).items():
        if not _check_name(bname, "블록", problems):
            continue
        if isinstance(val, str):
            file, desc = val, ""
        elif isinstance(val, dict):
            file, desc = val.get("file"), str(val.get("desc", ""))
            for k in val:
                if k not in ("file", "desc"):
                    warnings.append(f"[block] {bname}.{k}: 알 수 없는 키")
        else:
            problems.append(f"[block] {bname}: 파일 경로 글자나 {{ file = …, desc = … }} 표여야 합니다")
            continue
        if not file:
            problems.append(f"[block] {bname}: file이 없습니다")
            continue
        bpath = os.path.normpath(os.path.join(root, file))
        if not os.path.isfile(bpath):
            problems.append(f"[block] {bname}: 방정식 파일이 없습니다 — {file}")
        blocks[bname] = BlockSpec(bname, file, bpath, desc)

    # [model.이름]
    models: Dict[str, ModelSpec] = {}
    mtab = raw.get("model") or {}
    if not isinstance(mtab, dict):
        problems.append("[model.이름] 꼴로 모형을 적습니다")
        mtab = {}
    for mname, val in mtab.items():
        if not _check_name(mname, "모형", problems):
            continue
        if not isinstance(val, dict):
            problems.append(f"[model.{mname}]은 표여야 합니다")
            continue
        for k in val:
            if k not in ("blocks", "include", "exclude", "desc"):
                warnings.append(f"[model.{mname}] {k}: 알 수 없는 키")
        spec = ModelSpec(mname, _str_list(val.get("blocks"), f"[model.{mname}] blocks", problems),
                         _str_list(val.get("include"), f"[model.{mname}] include", problems),
                         _str_list(val.get("exclude"), f"[model.{mname}] exclude", problems),
                         str(val.get("desc", "")))
        if not spec.blocks and not spec.include:
            problems.append(f"[model.{mname}]: blocks나 include가 있어야 합니다")
        models[mname] = spec
    for mname, spec in models.items():
        if mname in blocks:
            problems.append(f"'{mname}'이 블록이자 모형입니다 — 이름을 다르게(블록 HS와 모형 HS를 이름으로 가리킨다)")
        for b in spec.blocks:
            if b not in blocks:
                problems.append(f"[model.{mname}] blocks: 없는 블록 '{b}' (있는 블록: {', '.join(blocks) or '없음'})")
        for m in spec.include:
            if m not in models:
                problems.append(f"[model.{mname}] include: 없는 모형 '{m}' (있는 모형: {', '.join(models)})")
        for x in spec.exclude:
            if ":" not in x:
                problems.append(f"[model.{mname}] exclude: '{x}' — 블록:목표변수 꼴(예: finance:RL)")
    # include 순환
    def visit(m, stack):
        if m in stack:
            problems.append("모형 include가 돌고 돕니다: " + " → ".join(stack[stack.index(m):] + [m]))
            return
        for inc in models.get(m, ModelSpec(m)).include:
            if inc in models:
                visit(inc, stack + [m])
    for m in models:
        visit(m, [])

    # [group]
    groups: Dict[str, GroupSpec] = {}
    for gname, val in (raw.get("group") or {}).items():
        if not _check_name(gname, "묶음", problems):
            continue
        if isinstance(val, list):
            series, tr, desc = _str_list(val, f"[group] {gname}", problems), None, ""
        elif isinstance(val, dict):
            series = _str_list(val.get("series"), f"[group] {gname}.series", problems)
            tr, desc = val.get("transform"), str(val.get("desc", ""))
        else:
            problems.append(f"[group] {gname}: 시리즈 목록이나 {{ series = […] }} 표여야 합니다")
            continue
        if not series:
            problems.append(f"[group] {gname}: 시리즈가 없습니다")
        groups[gname] = GroupSpec(gname, series, tr, desc)

    # [hs]
    hs = raw.get("hs") or {}
    if not isinstance(hs, dict):
        problems.append("[hs]는 표여야 합니다")
        hs = {}
    if hs.get("model") and hs["model"] not in models and hs["model"] not in blocks:
        problems.append(f"[hs] model = {hs['model']!r}: 없는 모형·블록")
    if hs.get("mode") and hs["mode"] not in MODES:
        problems.append(f"[hs] mode = {hs['mode']!r} — {' · '.join(MODES)}")
    if hs.get("range") and (not isinstance(hs["range"], str) or ":" not in hs["range"]):
        problems.append(f"[hs] range = {hs.get('range')!r} — \"시작:끝\" 꼴(예: \"2005Q1:2019Q4\" · \"2005Q1:last\" · \"last-39:last\")")

    criteria = _criteria(raw.get("criteria"), problems)
    fc = raw.get("forecast") or {}
    if not isinstance(fc, dict):
        problems.append("[forecast]는 표여야 합니다")
        fc = {}
    for k in fc:
        if k not in ("model", "range", "assume", "addfactors", "fill", "mode"):
            problems.append(f"[forecast] {k}: 알 수 없는 키 — model · range · assume · addfactors · fill · mode")
    if fc.get("model") and fc["model"] not in models and fc["model"] not in blocks:
        problems.append(f"[forecast] model = {fc['model']!r}: 없는 모형·블록")
    if fc.get("mode") and fc["mode"] not in MODES:
        problems.append(f"[forecast] mode = {fc['mode']!r} — {' · '.join(MODES)}")
    if fc.get("fill") and fc["fill"] not in FILLS:
        problems.append(f"[forecast] fill = {fc['fill']!r} — {' · '.join(FILLS)}")
    if fc.get("range") and (not isinstance(fc["range"], str) or ":" not in fc["range"]):
        problems.append(f"[forecast] range = {fc.get('range')!r} — \"시작:끝\" 또는 \"next:N\"(예: \"next:8\")")
    for k in ("assume", "addfactors"):
        if fc.get(k) and not NAME_RE.match(str(fc[k])):
            problems.append(f"[forecast] {k} = {fc[k]!r} — 이름(ASSUMPTIONS/이름.csv · ADDFACTORS/이름.toml)")

    if problems:
        raise ProjectError([f"{CONFIG_NAME}: {p}" if not p.startswith(CONFIG_NAME) else p for p in problems])
    return ProjectConfig(root=root, path=cfg_path, name=name, data_file=data_file, data_path=data_path,
                         blocks=blocks, models=models, groups=groups, hs=dict(hs), raw=raw, warnings=warnings,
                         series_file=series_file, derived_file=derived_file, freq=freq, vintage=vintage,
                         criteria=criteria, forecast=dict(fc))


def _criteria(raw, problems: List[str]) -> dict:
    """[criteria] — alpha(진단 유의수준, 기본 0.05) · tests(기준에 넣는 진단) · t_min(계수 |t| 하한) · signs(기대 부호)."""
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        problems.append("[criteria]는 표여야 합니다")
        return {}
    out = {"alpha": 0.05, "tests": [], "t_min": None, "signs": {}}
    for k in raw:
        if k not in ("alpha", "tests", "t_min", "signs"):
            problems.append(f"[criteria] {k}: 알 수 없는 키 — alpha · tests · t_min · signs")
    a = raw.get("alpha", 0.05)
    if not isinstance(a, (int, float)) or not 0 < a < 1:
        problems.append(f"[criteria] alpha = {a!r} — 0과 1 사이(예: 0.05)")
    else:
        out["alpha"] = float(a)
    tests = raw.get("tests", [])
    if isinstance(tests, str):
        tests = [tests]
    bad = [t for t in tests if str(t).lower() not in TESTS] if isinstance(tests, list) else ["?"]
    if bad:
        problems.append(f"[criteria] tests: 모르는 검정 {', '.join(map(str, bad))} — {' · '.join(TESTS)}")
    else:
        out["tests"] = [str(t).lower() for t in tests]
    t = raw.get("t_min")
    if t is not None:
        if not isinstance(t, (int, float)) or t < 0:
            problems.append(f"[criteria] t_min = {t!r} — 0 이상의 수(예: 1.0)")
        else:
            out["t_min"] = float(t)
    signs = raw.get("signs") or {}
    if not isinstance(signs, dict):
        problems.append("[criteria.signs]는 표여야 합니다 — \"블록:목표\" = { 항 = \"+\" · \"-\" }")
        signs = {}
    for pid, terms in signs.items():
        if ":" not in pid:
            problems.append(f"[criteria.signs] {pid!r}: 부품 이름은 블록:목표(예: \"demand:CN\")")
            continue
        if not isinstance(terms, dict) or any(v not in ("+", "-") for v in terms.values()):
            problems.append(f"[criteria.signs] {pid}: {{ 항 = \"+\" 또는 \"-\" }} 꼴이어야 합니다")
            continue
        out["signs"][pid] = {str(k): v for k, v in terms.items()}
    return out
