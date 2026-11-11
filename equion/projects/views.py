"""보기(`VIEWS/*.toml`) — 어느 시리즈를 어떤 모양으로 볼지를 이름으로 적어 둔 정의(D46).

    # VIEWS/core.toml
    title = "핵심 지표"
    series = ["Y", "CN", "P"]
    show = "yoy"                  # level · qoq · yoy · annual · diff
    range = "2015Q1:last"         # 없으면 결과의 구간 그대로

보기는 결과를 만들지 않는다 — 과거 재현·전망·시나리오 어느 결과에나 같은 시리즈와 같은 모양을 다시 적용하는 데 쓴다(화면의 표·차트,
보고서로 보낼 때의 행). 정의 파일이라 바뀜 기록이 지켜본다.
"""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from .config import NAME_RE, ProjectError

FOLDER = "VIEWS"
SHOWS = ("level", "qoq", "yoy", "annual", "diff")
KEYS = ("title", "series", "show", "range")


@dataclass
class ViewSpec:
    """보기 하나."""

    name: str
    series: List[str]
    show: str = "level"
    title: str = ""
    range: Optional[str] = None
    file: str = ""

    def to_dict(self) -> dict:
        """사전."""
        return {"name": self.name, "title": self.title, "series": list(self.series), "show": self.show, "range": self.range, "file": self.file}


@dataclass
class ViewChange:
    """보기 쓰기 결과."""

    name: str
    file: str
    new: bool
    change: Optional[str] = None
    series: List[str] = field(default_factory=list)

    def text(self) -> str:
        """명령줄에 보이는 짧은 글."""
        head = f"[view define] {self.file}" + (" — 새 보기" if self.new else (" — 고침" if self.change else " — 바뀐 것이 없습니다"))
        return head + f"\n  시리즈   {', '.join(self.series)}" + (f"\n  바뀜 기록  {self.change}" if self.change else "")

    def to_dict(self) -> dict:
        """명령줄 --json과 같은 사전."""
        return {"name": self.name, "file": self.file, "new": self.new, "change": self.change, "series": self.series}


def _check(name: str, raw: dict, where: str) -> Tuple[Optional[ViewSpec], List[str]]:
    problems: List[str] = []
    for k in raw:
        if k not in KEYS:
            problems.append(f"{where}: 알 수 없는 키 {k} — {' · '.join(KEYS)}")
    series = raw.get("series")
    if not isinstance(series, list) or not series or any(not isinstance(x, str) or not x.strip() for x in series):
        problems.append(f"{where}: series = [\"Y\", \"CN\", …] — 시리즈 이름의 목록이 있어야 합니다")
        series = []
    show = raw.get("show", "level")
    if show not in SHOWS:
        problems.append(f"{where}: show = {show!r} — {' · '.join(SHOWS)}")
    rng = raw.get("range")
    if rng is not None and (not isinstance(rng, str) or ":" not in rng):
        problems.append(f"{where}: range = {rng!r} — \"시작:끝\" 꼴(예: 2015Q1:last)")
    if problems:
        return None, problems
    return ViewSpec(name, [str(x).strip() for x in series], show, str(raw.get("title", "")), rng), []


def load_views(root: str) -> List[ViewSpec]:
    """`VIEWS/*.toml`을 읽는다(이름순). 문제는 모아서 ProjectError."""
    folder = os.path.join(root, FOLDER)
    try:
        files = sorted(f for f in os.listdir(folder) if f.lower().endswith(".toml"))
    except OSError:
        return []
    out, problems = [], []
    for f in files:
        name, rel = os.path.splitext(f)[0], f"{FOLDER}/{f}"
        try:
            with open(os.path.join(folder, f), "rb") as fh:
                raw = tomllib.load(fh)
        except tomllib.TOMLDecodeError as e:
            problems.append(f"{rel} 문법 오류: {e}")
            continue
        spec, bad = _check(name, raw, rel)
        problems += bad
        if spec is not None:
            spec.file = rel
            out.append(spec)
    if problems:
        raise ProjectError(problems)
    return out


def view_text(root: str, name: str, series=None, show: str = None, title: str = None, range: str = None,
              known: List[str] = None) -> Tuple[str, bool, ViewSpec]:
    """보기를 더하거나 고친 **새 내용** — (글, 새 보기인지, 보기). 준 것만 바꾸고(빈 글은 그 키를 지움) 주석은 그대로(tomlkit), 파일은 쓰지 않는다.
    known을 주면 시리즈 이름이 그 안에 있는지 본다(대소문자 무시). 문제는 ProjectError."""
    import tomlkit
    if not NAME_RE.match(str(name)):
        raise ProjectError(f"보기 이름 {name!r} — 영문으로 시작하고 영문·숫자·_만(한글은 title로)")
    rel = f"{FOLDER}/{name}.toml"
    path = os.path.join(root, FOLDER, f"{name}.toml")
    new = not os.path.isfile(path)
    if new:
        doc = tomlkit.document()
    else:
        with open(path, encoding="utf-8") as f:
            doc = tomlkit.parse(f.read())
    if isinstance(series, str):
        series = [v for v in series.replace(",", " ").split() if v]
    for key, value in (("title", title), ("series", series), ("show", show), ("range", range)):
        if value is None:
            continue
        if value in ("", []):
            if key in doc:
                del doc[key]
        else:
            doc[key] = [str(v) for v in value] if key == "series" else str(value)
    text = tomlkit.dumps(doc)
    spec, problems = _check(name, tomllib.loads(text), rel)
    if spec is not None and known is not None:
        have = {str(k).upper() for k in known}
        missing = [s for s in spec.series if s.upper() not in have]
        if missing:
            problems.append(f"{rel}: 자료에 없는 시리즈 {', '.join(missing)}")
    if problems:
        raise ProjectError(problems)
    spec.file = rel
    return text, new, spec
