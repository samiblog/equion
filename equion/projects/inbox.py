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

INBOX_DIR = os.path.join("DATA", "raw", "inbox")
RAW_EXT = (".csv", ".xlsx", ".xls")
_DATE_TAIL = re.compile(r"_\d{8}(_\d+)?$")
_PERIOD_TAIL = re.compile(r"(?:[_\-\s.]+[^_\-\s.]*\d[^_\-\s.]*)+$")      # 숫자가 든 끝 토막들(_2020Q1 · _2026-12 · -v2)


def family(stem: str) -> str:
    """파일 이름의 몸통 — 끝의 날짜·기간 토막을 뺀다('toy_q_2020Q1' → 'toy_q', '국민계정_2026-12' → '국민계정')."""
    s = _PERIOD_TAIL.sub("", _DATE_TAIL.sub("", stem))
    return s or stem
STATUS_KO = {"ready": "넣을 수 있음", "none": "짝 없음", "many": "짝이 여럿", "bad": "틀이 맞지 않음", "taken": "넣음",
             "same": "같은 파일이 이미 있음", "declined": "넣지 않음(답)"}


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
                "bad": f"→ [source.{self.source}] 틀이 맞지 않습니다: " + "; ".join(self.problems)}[self.status]
        return f"{os.path.basename(self.file)} {tail}"

    def to_dict(self) -> dict:
        """사전."""
        return {"file": self.file, "sha256": self.sha256, "status": self.status, "source": self.source, "how": self.how,
                "candidates": self.candidates, "problems": self.problems, "to": self.to, "previous": self.previous}


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


def plan(p) -> List[InboxItem]:
    """받은 상자의 파일마다 짝지을 출처와 틀 검사(아무것도 바꾸지 않는다 — 미리보기)."""
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
        out.append(item)
    return out


def take(p, mode: str = "auto", ask: Callable[[InboxItem], bool] = None, who: str = None,
         command: str = None) -> List[InboxItem]:
    """받은 파일을 넣는다 — 하나라도 짝이 없거나 틀이 맞지 않으면 아무것도 넣지 않고 ProjectError(까닭 모두).

    mode: 'auto'(짝이 하나이고 틀이 맞으면 넣는다) · 'ask'(ask(item)이 참인 것만 — ask가 없으면 auto)
    """
    if mode not in ("auto", "ask"):
        raise ProjectError(f"--inbox는 ask · auto · no입니다: {mode!r}")
    items = plan(p)
    bad = [x for x in items if not x.ok]
    if bad:
        raise ProjectError("받은 원자료를 넣지 못했습니다(아무것도 넣지 않음):\n" + "\n".join(f"  - {x.text()}" for x in bad))
    for x in items:
        if mode == "ask" and ask is not None and not ask(x):
            x.status = "declined"
            continue
        res = p.data_add(os.path.join(p.root, x.file), source=x.source, who=who,
                         command=command or f"data build --inbox {mode}")
        if res.problems:                       # plan에서 걸렀으니 여기 오면 안 된다
            raise ProjectError(f"{x.file}: " + "; ".join(res.problems))
        x.to = res.file
        x.status = "taken" if (res.copied or res.previous != res.file) else "same"
        os.remove(os.path.join(p.root, x.file))   # DATA/raw/에 받은 그대로 들어갔다 — 받은 상자에서는 뺀다
    return items
