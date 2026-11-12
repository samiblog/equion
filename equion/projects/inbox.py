#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""받은 원자료 `DATA/raw/inbox/` (D34·D36) — 새 파일을 여기에 놓으면 `equion data build --inbox ask|auto`가 어느 출처를 바꾸는지
짝지어(틀 검사까지) `DATA/raw/`에 넣고 출처가 그 파일을 읽게 한 뒤 회차를 만든다.

짝짓기는 두 가지뿐이다(알아맞히지 않는다):

1. `series.toml`의 `[source.이름] inbox = "toy_q*.csv"`(파일 이름 글롭, 대소문자 무시) — 적었으면 이것만 본다.
2. 적지 않았으면 파일 이름이 그 출처가 지금 읽는 파일의 이름(끝의 날짜·기간 꼬리 `_20261109`·`_2020Q1`·`_2026-12` 뺌)으로 시작하는 것 —
   가장 긴 것. 그래서 `toy_q.csv` 다음 달 `toy_q_2020Q1.csv`, 그다음 달 `toy_q_2020Q2.csv`가 모두 같은 출처다.

짝이 없거나 여럿이면, 또는 그 출처의 불러오기 틀로 읽히지 않으면(쓰는 열이 없음·주기가 다름) 아무것도 넣지 않고 까닭을 알린다.
`ask`는 터미널이면 파일마다 묻고, 터미널이 아니면(스크립트를 Claude·자동화가 돌릴 때) 짝이 하나이고 틀이 맞는 것만 넣는다 — `auto`와 같다.
"""

import fnmatch
import os
import re
import tomllib
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from ..data.source import file_sha256
from .config import ProjectError
from ..work.lock import locked

INBOX_DIR = os.path.join("DATA", "raw", "inbox")
RAW_EXT = (".csv", ".xlsx", ".xls")
_DATE_TAIL = re.compile(r"_\d{8}(_\d+)?$")
_PERIOD_TAIL = re.compile(r"(?:[_\-\s.]+[^_\-\s.]*\d[^_\-\s.]*)+$")      # 숫자가 든 끝 토막들(_2020Q1 · _2026-12 · -v2)


def family(stem: str) -> str:
    """파일 이름의 몸통 — 끝의 날짜·기간 토막을 뺀다('toy_q_2020Q1' → 'toy_q', '국민계정_2026-12' → '국민계정')."""
    s = _PERIOD_TAIL.sub("", _DATE_TAIL.sub("", stem))
    return s or stem
STATUS_KO = {"ready": "넣을 수 있음", "none": "짝 없음", "many": "짝이 여럿", "bad": "틀이 맞지 않음", "taken": "넣음",
             "same": "같은 파일이 이미 있음", "declined": "넣지 않음(답)", "shorter": "기간이 줄어듦(--allow-shorter)"}


@dataclass
class InboxItem:
    """받은 파일 하나 — 짝지은 출처·어떻게 짝지었나·틀 검사·상태."""

    file: str                                  # DATA/raw/inbox/… (프로젝트 기준)
    sha256: str
    status: str                                # ready · none · many · bad · taken · same · declined
    source: Optional[str] = None
    how: str = ""
    candidates: List[str] = field(default_factory=list)
    problems: List[str] = field(default_factory=list)
    to: Optional[str] = None                   # 넣은 뒤 DATA/raw/…
    previous: Optional[str] = None             # 출처가 전에 읽던 파일
    notes: List[str] = field(default_factory=list)   # 사람이 볼 것 — 새 열(정의에 없음) · 짧아진 기간을 그래도 넣음

    @property
    def ok(self) -> bool:
        """넣을 수 있거나 넣었으면 참."""
        return self.status in ("ready", "taken", "same", "declined")

    def text(self) -> str:
        """한 줄."""
        tail = {"ready": f"→ [source.{self.source}] ({self.how}) · 틀 검사 통과",
                "taken": f"→ {self.to} · [source.{self.source}] {self.previous} → {self.to}",
                "same": f"→ {self.to} (같은 내용의 파일이 이미 있음) · [source.{self.source}]",
                "declined": f"→ [source.{self.source}] — 넣지 않았습니다(받은 상자에 그대로)",
                "none": "— 짝지을 출처가 없습니다: series.toml [source.이름]에 inbox = \"파일 이름 글롭\"을 적거나 "
                        f"equion data add {self.file} --source 이름",
                "many": f"— 짝이 여럿입니다({', '.join(self.candidates)}) — [source.이름] inbox = \"…\"로 정해 주세요",
                "bad": f"→ [source.{self.source}] 틀이 맞지 않습니다: " + "; ".join(self.problems),
                "shorter": f"→ [source.{self.source}] 넣지 않음 — " + "; ".join(self.problems)}[self.status]
        return f"{os.path.basename(self.file)} {tail}"

    def to_dict(self) -> dict:
        """사전."""
        return {"file": self.file, "sha256": self.sha256, "status": self.status, "source": self.source, "how": self.how,
                "candidates": self.candidates, "problems": self.problems, "to": self.to, "previous": self.previous,
                "notes": self.notes}


def inbox_files(root: str) -> List[str]:
    """받은 상자의 원자료 파일(프로젝트 기준 경로, 이름 순) — 숨은 파일·옆 파일(*.source.toml)은 뺀다."""
    d = os.path.join(root, INBOX_DIR)
    if not os.path.isdir(d):
        return []
    return [os.path.join(INBOX_DIR, n).replace(os.sep, "/") for n in sorted(os.listdir(d))
            if not n.startswith(".") and os.path.splitext(n)[1].lower() in RAW_EXT and os.path.isfile(os.path.join(d, n))]


def _rules(p) -> dict:
    """{출처: [inbox 글롭…]} — series.toml에 적은 것."""
    path = os.path.join(p.root, p.config.series_file)
    with open(path, "rb") as f:
        raw = tomllib.load(f)
    out = {}
    for name, v in (raw.get("source") or {}).items():
        pat = v.get("inbox") if isinstance(v, dict) else None
        if pat:
            out[name] = [pat] if isinstance(pat, str) else [str(x) for x in pat]
    return out


def _base_stems(p, spec) -> List[str]:
    stems = [family(os.path.splitext(os.path.basename(spec.file))[0])]
    side = spec.path + ".source.toml"
    if os.path.isfile(side):
        try:
            with open(side, "rb") as f:
                frm = tomllib.load(f).get("from")
            if frm:
                stems.append(family(os.path.splitext(os.path.basename(frm))[0]))
        except (OSError, tomllib.TOMLDecodeError):
            pass
    return [s.lower() for s in dict.fromkeys(stems) if s]


def match(p, defs, file: str):
    """받은 파일 하나 → (출처 또는 None, 어떻게, 후보들)."""
    name = os.path.basename(file)
    rules = _rules(p)
    if rules:
        hit = [s for s, pats in rules.items() if any(fnmatch.fnmatch(name.lower(), x.lower()) for x in pats)]
        if len(hit) == 1:
            return hit[0], f"inbox = {rules[hit[0]][0]!r}", hit
        if hit:
            return None, "", hit
    stem = os.path.splitext(name)[0].lower()
    best, cands = 0, []
    for s, spec in defs.sources.items():
        if s in rules:
            continue
        n = max((len(b) for b in _base_stems(p, spec) if stem.startswith(b)), default=0)
        if n > best:
            best, cands = n, [s]
        elif n and n == best:
            cands.append(s)
    if len(cands) == 1:
        return cands[0], f"이름이 {os.path.basename(defs.sources[cands[0]].file)}와 같은 앞부분", cands
    return None, "", cands


def _compare(defs, src: str, path: str):
    """받은 파일과 출처가 지금 읽는 파일을 그 틀로 견준다 → (짧아진 시리즈들, 새 열들). 읽을 수 없으면 ([], [])."""
    from dataclasses import replace
    from ..data.periods import format_period
    from ..data.source import read_source
    sp = defs.sources[src]
    if not os.path.isfile(sp.path) or os.path.normcase(os.path.abspath(sp.path)) == os.path.normcase(os.path.abspath(path)):
        return [], []
    try:
        new = read_source(replace(sp, file=os.path.basename(path), path=os.path.abspath(path)))
        old = read_source(sp)
    except ValueError:
        return [], []
    F = new.freq
    shorter = []
    for s in defs.series.values():
        if s.source != src:
            continue
        a, _ = old.column(s.column)
        b, _ = new.column(s.column)
        if a is None or b is None:
            continue
        x, y = old.data[a].dropna(), new.data[b].dropna()
        if not len(x):
            continue
        if not len(y):
            shorter.append(f"{s.column} 값 없음(지금 {format_period(x.index[0], F)}~{format_period(x.index[-1], F)})")
            continue
        if y.index[0] > x.index[0] or y.index[-1] < x.index[-1]:
            shorter.append(f"{s.column} {format_period(x.index[0], F)}~{format_period(x.index[-1], F)} → "
                           f"{format_period(y.index[0], F)}~{format_period(y.index[-1], F)}")
    used = {s.column.lower() for s in defs.series.values() if s.source == src}
    had = {str(c).lower() for c in old.data.columns}
    fresh = [str(c) for c in new.data.columns if str(c).lower() not in had and str(c).lower() not in used]
    return shorter, fresh


def plan(p, allow_shorter: bool = False) -> List[InboxItem]:
    """받은 상자의 파일마다 짝지을 출처와 틀 검사(아무것도 바꾸지 않는다 — 미리보기).

    틀 검사에 더해 출처가 지금 읽는 파일과 견준다 — 시리즈의 기간이 줄었으면(시작이 늦거나 끝이 이름: 지난 파일을 다시 받았거나 일부 기간만
    든 파일) 'shorter'(allow_shorter면 넣되 notes에 남긴다), 정의에 없는 새 열이 있으면 notes에 `equion data define`을 권한다."""
    from .config import NAME_RE
    defs = p._need_defs()
    out = []
    for rel in inbox_files(p.root):
        path = os.path.join(p.root, rel)
        src, how, cands = match(p, defs, rel)
        item = InboxItem(rel, file_sha256(path), "ready", src, how, cands, previous=defs.sources[src].file if src else None)
        if src is None:
            item.status = "many" if len(cands) > 1 else "none"
        else:
            item.problems = p._source_problems(defs, src, path)
            if item.problems:
                item.status = "bad"
                if any("새 파일에 없는 열" in x for x in item.problems):     # 이름이 바뀐 열인지 보이게
                    _, fresh = _compare(defs, src, path)
                    if fresh:
                        item.problems.append(f"새 파일에만 있는 열: {', '.join(fresh[:6])}{' …' if len(fresh) > 6 else ''}"
                                             " — 열 이름이 바뀌었으면 정의를 고치세요(equion data define … --replace)")
            else:
                shorter, fresh = _compare(defs, src, path)
                if shorter:
                    msg = (f"지금 파일 {os.path.basename(defs.sources[src].file)}보다 기간이 짧습니다: " + " · ".join(shorter[:4])
                           + (f" 외 {len(shorter) - 4}" if len(shorter) > 4 else ""))
                    if allow_shorter:
                        item.notes.append(f"! {msg} — --allow-shorter로 넣음")
                    else:
                        item.status = "shorter"
                        item.problems = [msg + " — 지난 파일을 다시 받았거나 일부 기간만 든 파일이 아닌지 확인하세요"
                                               "(그래도 넣으려면 --allow-shorter)"]
                if fresh:
                    eg = next((c for c in fresh if NAME_RE.match(c)), None)
                    item.notes.append(f"새 열 {len(fresh)}: {', '.join(fresh[:6])}{' …' if len(fresh) > 6 else ''} — 정의에 없어 읽지 않습니다"
                                      + (f"(쓰려면 equion data define {src} --series {eg}={eg})" if eg else
                                         f"(쓰려면 equion data define {src} --series 이름=열)"))
        out.append(item)
    return out


@locked
def take(p, mode: str = "auto", ask: Callable[[InboxItem], bool] = None, who: str = None,
         command: str = None, allow_shorter: bool = False, precheck: Callable[[List[InboxItem]], None] = None) -> List[InboxItem]:
    """받은 파일을 넣는다 — 하나라도 짝이 없거나 틀이 맞지 않으면 아무것도 넣지 않고 ProjectError(까닭 모두). 기간이 줄어든 파일만
    걸렸으면 ShorterError(사람이 확인할 일 — 스크립트는 '!'로 남기고 이어 간다).

    mode: 'auto'(짝이 하나이고 틀이 맞으면 넣는다) · 'ask'(ask(item)이 참인 것만 — ask가 없으면 auto)
    precheck: 넣기 바로 전에 넣을 파일들로 부르는 함수 — 예외를 내면 아무것도 넣지 않는다(자료 만들기가 회차 기간을 먼저 본다)
    """
    from .vintage import ShorterError
    if mode not in ("auto", "ask"):
        raise ProjectError(f"--inbox는 ask · auto · no입니다: {mode!r}")
    items = plan(p, allow_shorter=allow_shorter)
    bad = [x for x in items if not x.ok]
    if bad:
        head = "받은 원자료를 넣지 못했습니다(아무것도 넣지 않음):\n" + "\n".join(f"  - {x.text()}" for x in bad)
        if all(x.status == "shorter" for x in bad):
            raise ShorterError(head)
        raise ProjectError(head)
    for x in items:
        if mode == "ask" and ask is not None and not ask(x):
            x.status = "declined"
    if precheck is not None:
        precheck([x for x in items if x.status != "declined"])
    for x in items:
        if x.status == "declined":
            continue
        res = p.data_add(os.path.join(p.root, x.file), source=x.source, who=who,
                         command=command or f"data build --inbox {mode}")
        if res.problems:                       # plan에서 걸렀으니 여기 오면 안 된다
            raise ProjectError(f"{x.file}: " + "; ".join(res.problems))
        x.to = res.file
        x.status = "taken" if (res.copied or res.previous != res.file) else "same"
        os.remove(os.path.join(p.root, x.file))   # DATA/raw/에 받은 그대로 들어갔다 — 받은 상자에서는 뺀다
    return items


def data_build(p, use: bool = False, inbox: str = None, ask=None, who: str = None, command: str = None,
               allow_shorter: bool = False):
    """`Project.data_build`의 몸 — 받은 원자료 넣기 → 회차 만들기(지금 회차보다 짧으면 거절) → (use) 지금 회차 바꾸기.

    받은 파일을 넣기 전에, 넣을 파일로 읽은 자료가 지금 회차보다 짧지 않은지 먼저 본다 — 짧으면 아무것도 넣지 않고 ShorterError
    (allow_shorter면 만들고 `.warnings`에). 옛 회차로 돌아가면(같은 내용의 옛 회차) `.warnings`에 남긴다."""
    from dataclasses import replace
    from ..version import project_version
    from ..workfile.output import say
    from .vintage import (VINTAGE_DIR, ShorterError, build_vintage, move_notes, series_spans, shorter_message, shrink_notes,
                          vintage_frame)
    current = p.config.vintage if p.config.uses_vintages else None
    if current and not os.path.isfile(os.path.join(p.root, VINTAGE_DIR, current, "series.csv")):
        current = None                         # 지금 회차 폴더가 없다 — 견줄 것이 없다(data list가 알린다)

    def precheck(items):
        if not current or allow_shorter or not items:
            return
        defs = p._need_defs()
        srcs = dict(defs.sources)
        for x in items:
            srcs[x.source] = replace(srcs[x.source], file=x.file, path=os.path.abspath(os.path.join(p.root, x.file)))
        df, _, _, _ = vintage_frame(replace(defs, sources=srcs))
        notes = shrink_notes(p.root, current, series_spans(df, defs.freq), defs.freq)
        if notes:
            raise ShorterError(shorter_message(current, notes, "받은 원자료로 만들 자료"))

    taken = []
    if inbox and inbox != "no":
        taken = take(p, inbox, ask=ask, who=who, command=command, allow_shorter=allow_shorter, precheck=precheck)
    defs = p._need_defs()
    res = build_vintage(defs, project_version(), current=current, allow_shorter=allow_shorter)
    res.inbox = taken
    if not inbox or inbox == "no":
        res.waiting = len(inbox_files(p.root))
    say(f"[{p.name}] " + (f"자료 회차 {res.id}를 만들었습니다" if res.created else f"자료 회차 {res.id}와 같습니다"))
    if use and res.id != p.config.vintage:
        old = p.config.vintage
        p.data_use(res.id, who=who, command=command)
        if not res.warnings:                   # 짧은 자료·옛 회차는 이미 적었다
            res.warnings += move_notes(p.root, old, res.id)
    return res
