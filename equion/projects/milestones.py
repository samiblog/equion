"""이정표 (D61) — 중요한 때(예: "2026-11 전망 확정")의 정의 내용·자료 회차·고정한 기록을 이름으로 묶어 둔다.

    work/milestones/<이름>/
        milestone.json      이름 · 메모 · 만든 때 · 누가 · 자료 회차 · 정의 파일의 해시 · 고정한 기록
        defs/<경로>         그때의 정의 파일 사본(블록 파일 · equion.toml · 채택표 · 자료 정의 · 가정 · 보정항 · 시나리오 · 보기 · 노트 · 보고서 · 스크립트)

`milestone_diff`는 지금과 견주고(파일마다 같음 · 고침 · 새로 · 지움과 차이), `milestone_restore`는 정의를 그때로 되돌린다 — 바뀜 기록 하나로 남아
그것도 되돌릴 수 있다. 계산 결과(기록)는 이정표에 사본을 두지 않는다 — 고정한 기록의 이름만 적고, 이정표의 기록은 정리(`work clean`)에서 빠진다.
"""
from __future__ import annotations

import difflib
import hashlib
import json
import os
import shutil
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ..work.store import now_iso
from .config import NAME_RE, ProjectError

FOLDER = os.path.join("work", "milestones")


@dataclass
class Milestone:
    """이정표 하나 — `.name` · `.note` · `.created` · `.who` · `.vintage` · `.files`(경로 → 해시) · `.records`(고정한 기록)."""

    name: str
    note: str = ""
    created: str = ""
    who: str = ""
    vintage: Optional[str] = None
    files: Dict[str, str] = field(default_factory=dict)
    records: List[str] = field(default_factory=list)
    path: str = ""

    def text(self) -> str:
        """명령줄에 보이는 짧은 글."""
        return (f"[milestone] {self.name}" + (f" — {self.note}" if self.note else "") + f"\n  만든 때 {self.created} · {self.who}"
                + f"\n  자료 회차 {self.vintage or '(자료 파일)'} · 정의 파일 {len(self.files)} · 고정한 기록 {len(self.records)}"
                + f"\n  폴더   {self.path}")

    def to_dict(self) -> dict:
        """명령줄 --json과 같은 사전."""
        return {"name": self.name, "note": self.note, "created": self.created, "who": self.who, "vintage": self.vintage,
                "files": dict(self.files), "records": list(self.records), "path": self.path}


@dataclass
class MilestoneDiff:
    """이정표와 지금 — 파일마다 상태(same · changed · added(이정표 뒤에 생김) · removed(이정표 뒤에 지움))와 차이, 자료 회차."""

    name: str
    files: List[dict]
    vintage: Optional[str]
    vintage_now: Optional[str]
    diff: str

    @property
    def same(self) -> bool:
        """정의도 자료 회차도 그때와 같다."""
        return all(f["status"] == "same" for f in self.files) and self.vintage == self.vintage_now

    def text(self) -> str:
        """명령줄에 보이는 짧은 글."""
        KO = {"changed": "고침", "added": "새로", "removed": "지움"}
        moved = [f for f in self.files if f["status"] != "same"]
        L = [f"[milestone show] {self.name} 와 지금 — " + ("같습니다" if self.same else f"바뀐 파일 {len(moved)}")]
        if self.vintage != self.vintage_now:
            L.append(f"  자료 회차 {self.vintage} → 지금 {self.vintage_now}")
        for f in moved:
            L.append(f"  {KO[f['status']]:<3} {f['path']}" + (f"  +{f['plus']} −{f['minus']}" if f["status"] == "changed" else ""))
        if moved:
            L.append(f"  되돌리기  equion milestone restore {self.name}")
        return "\n".join(L)

    def to_dict(self) -> dict:
        """명령줄 --json과 같은 사전."""
        return {"name": self.name, "same": self.same, "vintage": self.vintage, "vintage_now": self.vintage_now, "files": self.files, "diff": self.diff}


def _root(p) -> str:
    return os.path.join(p.root, FOLDER)


def _read(path: str) -> Optional[bytes]:
    try:
        with open(path, "rb") as f:
            return f.read()
    except OSError:
        return None


def _text(data: Optional[bytes]) -> str:
    if data is None:
        return ""
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("cp949", errors="replace")


def _defs(p) -> List[str]:
    from ..work.history import tracked
    from .records import ADOPTED
    return tracked(p.root, [b.file for b in p.config.blocks.values()] + [ADOPTED])


def load(p, name: str) -> Milestone:
    """이정표 하나를 읽는다. 없으면 ProjectError."""
    path = os.path.join(_root(p), name, "milestone.json")
    if not NAME_RE.match(str(name)) or not os.path.isfile(path):
        have = ", ".join(m.name for m in list_all(p)) or "없음"
        raise ProjectError(f"이정표가 없습니다: {name} (있는 것: {have})")
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    return Milestone(d["name"], d.get("note", ""), d.get("created", ""), d.get("who", ""), d.get("vintage"), d.get("files") or {},
                     d.get("records") or [], os.path.join(FOLDER, name).replace(os.sep, "/"))


def list_all(p) -> List[Milestone]:
    """이정표들(만든 때 순)."""
    base = _root(p)
    out = []
    if os.path.isdir(base):
        for n in os.listdir(base):
            if NAME_RE.match(n) and os.path.isfile(os.path.join(base, n, "milestone.json")):
                out.append(load(p, n))
    return sorted(out, key=lambda m: m.created)


def make(p, name: str, note: str = None, who: str = None) -> Milestone:
    """이정표를 만든다 — 정의 파일의 사본과 자료 회차·고정한 기록. 같은 이름은 거절한다."""
    from ..work.store import detect_who, move_into_place
    from .records import store_of
    if not NAME_RE.match(str(name)):
        raise ProjectError(f"이정표 이름 {name!r} — 영문으로 시작하고 영문·숫자·_만(예: fc_2026_11)")
    dest = os.path.join(_root(p), name)
    if os.path.exists(dest):
        raise ProjectError(f"이미 있는 이정표입니다: {name}")
    store = store_of(p)
    pinned = sorted(k for k, v in store.marks().items() if v.get("pinned"))
    files: Dict[str, str] = {}
    tmp = dest + ".tmp-equion"
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(os.path.join(tmp, "defs"))
    for rel in _defs(p):
        data = _read(os.path.join(p.root, rel))
        if data is None:
            continue
        files[rel] = hashlib.sha256(data).hexdigest()
        target = os.path.join(tmp, "defs", *rel.split("/"))
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "wb") as f:
            f.write(data)
    m = Milestone(name, note or "", now_iso(), who or detect_who("python"), p.vintage, files, pinned,
                  os.path.join(FOLDER, name).replace(os.sep, "/"))
    with open(os.path.join(tmp, "milestone.json"), "w", encoding="utf-8") as f:
        json.dump({k: v for k, v in m.to_dict().items() if k != "path"}, f, ensure_ascii=False, indent=2)
    os.makedirs(_root(p), exist_ok=True)
    move_into_place(tmp, dest)
    return m


def diff(p, name: str) -> MilestoneDiff:
    """이정표와 지금 — 파일마다 상태와 차이(지금 → 이정표로 되돌리면 이렇게 바뀐다는 쪽이 아니라, 이정표 → 지금)."""
    m = load(p, name)
    base = os.path.join(p.root, FOLDER, name, "defs")
    now = set(_defs(p))
    rows, chunks = [], []
    for rel in sorted(set(m.files) | now):
        old = _read(os.path.join(base, *rel.split("/"))) if rel in m.files else None
        cur = _read(os.path.join(p.root, rel)) if rel in now else None
        if old is not None and cur is not None and hashlib.sha256(cur).hexdigest() == m.files[rel]:
            rows.append({"path": rel, "status": "same", "plus": 0, "minus": 0})
            continue
        status = "changed" if old is not None and cur is not None else ("added" if old is None else "removed")
        lines = list(difflib.unified_diff(_text(old).splitlines(keepends=True), _text(cur).splitlines(keepends=True),
                                          f"a/{rel}", f"b/{rel}"))
        plus = sum(1 for x in lines if x.startswith("+") and not x.startswith("+++"))
        minus = sum(1 for x in lines if x.startswith("-") and not x.startswith("---"))
        rows.append({"path": rel, "status": status, "plus": plus, "minus": minus})
        chunks.append("".join(lines))
    return MilestoneDiff(name, rows, m.vintage, p.vintage, "".join(chunks))


def restore(p, name: str, files: List[str] = None, who: str = None, command: str = None):
    """정의를 이정표 때로 되돌린다 — 그때 있던 파일은 그때 내용으로, 그 뒤에 생긴 정의 파일은 지운다(files를 주면 그 파일만).
    바뀜 기록 하나로 남는다(그것도 되돌릴 수 있다). 바뀐 것이 없으면 None."""
    from .records import history_of
    m = load(p, name)
    d = diff(p, name)
    moved = {f["path"]: f["status"] for f in d.files if f["status"] != "same"}
    if files:
        unknown = [f for f in files if f not in moved and f not in m.files]
        if unknown:
            raise ProjectError(f"이정표 {name}와 견줄 수 없는 파일: {', '.join(unknown)}")
        moved = {k: v for k, v in moved.items() if k in files}
    if not moved:
        return None
    base = os.path.join(p.root, FOLDER, name, "defs")
    new: Dict[str, Optional[bytes]] = {}
    for rel, status in moved.items():
        new[rel] = None if status == "added" else _read(os.path.join(base, *rel.split("/")))
    return history_of(p).write_files(new, who or "python", command or f"milestone restore {name}",
                                      note=f"이정표 {name}로 — 파일 {len(new)}")
