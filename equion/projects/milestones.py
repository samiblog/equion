"""이정표 (D61) — 중요한 때(예: "2026-11 전망 확정")의 정의 내용·자료 회차·고정한 기록을 이름으로 묶어 둔다.

    work/milestones/<이름>/
        milestone.json      이름 · 메모 · 만든 때 · 누가 · 자료 회차 · 정의 파일의 해시 · 고정한 기록
        defs/<경로>         그때의 정의 파일 사본(블록 파일 · equion.toml · 채택표 · 자료 정의 · 가정 · 보정항 · 시나리오 · 보기 · 스크립트 —
                            노트·보고서는 글이라 넣지 않는다)

`milestone_diff`는 지금과 견주고(파일마다 같음 · 고침 · 새로 · 지움과 차이), `milestone_restore`는 정의를 그때로 되돌린다 — 바뀜 기록 하나로 남아
그것도 되돌릴 수 있다. 자료 회차(equion.toml의 [data] vintage)는 견주지도 되돌리지도 않는다 — 회차는 따로 알리고 바꾸는 것은 `data use`. 계산 결과(기록)는 이정표에 사본을 두지 않는다 — 고정한 기록의 이름만 적고, 이정표의 기록은 정리(`work clean`)에서 빠진다.
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
from ..work.lock import locked
from .config import NAME_RE, ProjectError

FOLDER = os.path.join("work", "milestones")
MAX_NAME = 64
RESERVED = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}


def _safe_rel(rel) -> bool:
    """이정표가 적은 파일 경로가 프로젝트 안의 정의 자리인가(손으로 고친 milestone.json·조작한 묶음을 막는다)."""
    if not isinstance(rel, str) or not rel or len(rel) > 400 or "\\" in rel or ":" in rel or rel.startswith("/"):
        return False
    parts = rel.split("/")
    return all(seg not in ("", ".", "..") for seg in parts) and parts[0].lower() not in ("work", ".git")


def _with_vintage(data: Optional[bytes], vintage: Optional[str]) -> Optional[bytes]:
    """equion.toml의 [data] vintage만 주어진 값으로(없으면 줄을 뺀다) — 이정표는 회차를 견주지도 되돌리지도 않는다."""
    if data is None:
        return None
    try:
        import tomlkit
        doc = tomlkit.parse(_text(data))
    except Exception:  # noqa: BLE001 — 읽을 수 없는 equion.toml은 그대로 견준다
        return data
    sec = doc.get("data")
    if sec is None or not hasattr(sec, "get"):
        return data
    if vintage is None:
        if "vintage" in sec:
            del sec["vintage"]
    else:
        sec["vintage"] = vintage
    return tomlkit.dumps(doc).encode("utf-8")


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
    def defs_same(self) -> bool:
        """정의 파일이 그때와 같다(자료 회차는 견주지 않는다 — 되돌릴 것이 없다)."""
        return all(f["status"] == "same" for f in self.files)

    @property
    def same(self) -> bool:
        """정의도 자료 회차도 그때와 같다."""
        return self.defs_same and self.vintage == self.vintage_now

    def text(self) -> str:
        """명령줄에 보이는 짧은 글."""
        KO = {"changed": "고침", "added": "새로", "removed": "지움", "missing": "사본 없음"}
        moved = [f for f in self.files if f["status"] != "same"]
        L = [f"[milestone show] {self.name} 와 지금 — " + ("같습니다" if self.same else
                                                          "정의는 같습니다(자료 회차만 다름)" if self.defs_same else f"바뀐 파일 {len(moved)}")]
        if self.vintage != self.vintage_now:
            L.append(f"  자료 회차 {self.vintage} → 지금 {self.vintage_now}")
        for f in moved:
            L.append(f"  {KO[f['status']]:<3} {f['path']}" + (f"  +{f['plus']} −{f['minus']}" if f["status"] == "changed" else ""))
        if moved:
            L.append(f"  되돌리기  equion milestone restore {self.name}")
        return "\n".join(L)

    def to_dict(self) -> dict:
        """명령줄 --json과 같은 사전."""
        return {"name": self.name, "same": self.same, "defs_same": self.defs_same, "vintage": self.vintage, "vintage_now": self.vintage_now,
                "files": self.files, "diff": self.diff}


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
    from .records import definition_files
    return definition_files(p)


def load(p, name: str) -> Milestone:
    """이정표 하나를 읽는다. 없으면 ProjectError."""
    path = os.path.join(_root(p), str(name), "milestone.json")
    if not NAME_RE.match(str(name)) or not os.path.isfile(path):
        have = ", ".join(m.name for m in list_all(p)) or "없음"
        raise ProjectError(f"이정표가 없습니다: {name} (있는 것: {have})")
    rel = os.path.join(FOLDER, name, "milestone.json").replace(os.sep, "/")
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError) as e:
        raise ProjectError(f"이정표 {name}를 읽을 수 없습니다({rel}) — {e}") from None
    files = d.get("files") if isinstance(d, dict) else None
    if not isinstance(d, dict) or not isinstance(files or {}, dict) or not all(isinstance(v, str) for v in (files or {}).values()):
        raise ProjectError(f"이정표 {name}가 손상되었습니다({rel}) — 형식이 다릅니다")
    bad = [k for k in (files or {}) if not _safe_rel(k)]
    if bad:
        raise ProjectError(f"이정표 {name}가 손상되었습니다({rel}) — 프로젝트의 정의 자리가 아닌 경로: {', '.join(map(repr, bad[:3]))}")
    files = {k: v for k, v in (files or {}).items() if not k.startswith(("notes/", "reports/"))}   # 옛 이정표의 글은 견주지 않는다
    recs = d.get("records") if isinstance(d.get("records"), list) else []
    return Milestone(str(d.get("name") or name), str(d.get("note") or ""), str(d.get("created") or ""), str(d.get("who") or ""),
                     d.get("vintage") if isinstance(d.get("vintage"), str) else None, files, [str(r) for r in recs],
                     os.path.join(FOLDER, name).replace(os.sep, "/"))


def list_all(p) -> List[Milestone]:
    """이정표들(만든 때 순)."""
    base = _root(p)
    out = []
    if os.path.isdir(base):
        for n in os.listdir(base):
            if NAME_RE.match(n) and os.path.isfile(os.path.join(base, n, "milestone.json")):
                try:
                    out.append(load(p, n))
                except ProjectError:           # 손상된 이정표는 목록·정리·묶음을 막지 않는다(milestone show가 까닭을 알린다)
                    continue
    return sorted(out, key=lambda m: m.created)


@locked
def make(p, name: str, note: str = None, who: str = None) -> Milestone:
    """이정표를 만든다 — 정의 파일의 사본과 자료 회차·고정한 기록. 같은 이름은 거절한다."""
    from ..work.store import detect_who, move_into_place
    from .records import store_of
    if not NAME_RE.match(str(name)) or len(str(name)) > MAX_NAME or str(name).lower() in RESERVED:
        raise ProjectError(f"이정표 이름 {name!r} — 영문으로 시작하고 영문·숫자·_만, {MAX_NAME}자까지(예: fc_2026_11 — con·nul 같은 이름은 안 됨)")
    dest = os.path.join(_root(p), name)
    if os.path.exists(dest):
        raise ProjectError(f"이미 있는 이정표입니다: {name}")
    store = store_of(p)
    pinned = sorted(k for k, v in store.marks().items() if v.get("pinned"))
    files: Dict[str, str] = {}
    from ..work.lock import tmp_path
    tmp = tmp_path(dest)                          # 프로세스마다 다른 임시 이름
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
        if rel in m.files and old is None:
            rows.append({"path": rel, "status": "missing", "plus": 0, "minus": 0})      # 이정표에 사본이 없다 — 손상
            continue
        if rel == "equion.toml":
            cur = _with_vintage(cur, m.vintage)            # 회차 줄은 견주지 않는다
        if old is not None and cur is not None and (hashlib.sha256(cur).hexdigest() == m.files[rel] or cur == old):
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


@locked
def restore(p, name: str, files: List[str] = None, who: str = None, command: str = None):
    """정의를 이정표 때로 되돌린다 — 그때 있던 파일은 그때 내용으로, 그 뒤에 생긴 정의 파일은 지운다(files를 주면 그 파일만).
    바뀜 기록 하나로 남는다(그것도 되돌릴 수 있다). 바뀐 것이 없으면 None."""
    from .records import history_of
    from .config import project_path
    m = load(p, name)
    d = diff(p, name)
    moved = {f["path"]: f["status"] for f in d.files if f["status"] != "same"}
    if files is not None:
        files = [str(f).replace("\\", "/") for f in files]
        if not files:
            raise ProjectError("되돌릴 파일이 없습니다 — files를 빼면 모두")
        unknown = [f for f in files if f not in moved and f not in m.files]
        if unknown:
            raise ProjectError(f"이정표 {name}와 견줄 수 없는 파일: {', '.join(unknown)}")
        moved = {k: v for k, v in moved.items() if k in files}
    broken = [k for k, v in moved.items() if v == "missing"]
    if broken:
        raise ProjectError(f"이정표 {name}가 손상되었습니다 — 사본이 없는 파일(되돌리지 않음): {', '.join(broken[:5])}")
    if not moved:
        return None
    base = os.path.join(p.root, FOLDER, name, "defs")
    new: Dict[str, Optional[bytes]] = {}
    for rel, status in moved.items():
        project_path(p.root, rel, "이정표의 파일")         # 프로젝트 밖이면 거절(이중 확인)
        new[rel] = None if status == "added" else _read(os.path.join(base, *rel.split("/")))
        if rel == "equion.toml" and new[rel] is not None:
            new[rel] = _with_vintage(new[rel], p.vintage)      # 지금 회차는 그대로
    before = _source_files(p)
    ch = history_of(p).write_files(new, who or "python", command or f"milestone restore {name}",
                                    note=f"이정표 {name}로 — 파일 {len(new)}")
    if ch is not None:
        try:
            ch.notes = data_notes(p, name, before, ch.id)
        except Exception:  # noqa: BLE001 — 알림을 못 만들어도 되돌리기는 끝났다
            ch.notes = []
    return ch


def _source_files(p) -> Dict[str, str]:
    """자료 정의(series.toml)의 출처마다 지금 읽는 원자료 파일 {출처: 파일}. 자료 정의를 쓰지 않으면 {}."""
    import tomllib
    c = p.config
    if not getattr(c, "uses_vintages", False) or not c.series_file:
        return {}
    try:
        with open(os.path.join(p.root, c.series_file), "rb") as f:
            raw = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError):
        return {}
    return {k: str(v.get("file")) for k, v in (raw.get("source") or {}).items() if isinstance(v, dict)}


def data_notes(p, name: str, before: Optional[Dict[str, str]] = None, change: Optional[str] = None) -> List[str]:
    """이정표로 되돌린 뒤 자료에 대해 알릴 것 — 회차는 그대로(이정표 때 회차와 다르면 그 회차와 바꾸는 법), 자료 정의가 그때의 원자료를
    가리키게 되었으면 다음 자료 만들기가 무엇을 읽는지와 지금 원자료를 계속 쓰는 법."""
    m = load(p, name)
    out = []
    if m.vintage and m.vintage != p.vintage:
        out.append(f"자료 회차는 그대로 {p.vintage}입니다(이정표 때 {m.vintage}) — 이정표 때 자료로 계산하려면 equion data use {m.vintage}")
    if before is not None:
        after = _source_files(p)
        moved = [(k, before.get(k), after.get(k)) for k in dict.fromkeys([*before, *after]) if before.get(k) != after.get(k)]
        if moved:
            out.append("자료 정의도 그때로 — 원자료 " + " · ".join(f"[source.{k}] {a or '없음'} → {b or '없음'}" for k, a, b in moved)
                       + ". 다음 자료 만들기(equion data build — 월간 스크립트의 자료 단계)는 그때의 원자료를 읽습니다(지금 회차보다 짧으면 거절)"
                       + (f". 지금 원자료를 계속 쓰려면 equion history revert {change} --file {p.config.series_file}" if change else ""))
    return out
