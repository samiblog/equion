#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""바뀜 기록 (D33·K7) — 정의 파일이 바뀔 때마다 `work/history/<번호>/`에 전후 내용과 차이를 남긴다.

    work/history/
      state/          지난번에 본 정의 파일의 사본 — 바깥에서 고친 것(편집기·Claude의 직접 편집)을 알아보는 기준
      h0001/          change.json(때·누가·어떻게·파일마다 전후 해시) · before/<경로> · after/<경로> · diff.txt

누가: 명령(`adopt`·`data use`·`propose apply`·`history revert` — 명령 그대로)이 바꾸면 그 명령으로, 명령 밖에서 바뀐 것은 다음 명령 때
'바깥'으로 적는다. 되돌리기는 그 바뀜 **하나만** 물리는 것이고 그것도 바뀜 기록에 남는다(지우지 않는다). 그 뒤에 같은 파일이 또 바뀌었으면
그 바뀜의 차이만 지금 내용에서 거꾸로 적용한다 — 뒤의 바뀜이 같은 줄(또는 TOML의 같은 키)을 고쳤으면 겹침(`RevertConflict`)으로 멈추고
아무것도 쓰지 않는다. `force=True`면 뒤의 바뀜까지 버리고 그 파일을 그 바뀜 앞 내용으로 통째로 쓴다.

줄바꿈(LF·CRLF)만 다른 것은 같은 줄로 본다 — 견주기·합치기·차이는 줄바꿈을 맞춘 뒤에 하고, 쓸 때는 지금 파일의 줄바꿈을 따른다
(Windows의 편집기·git autocrlf가 줄바꿈만 바꾼 파일에서도 되돌리기가 된다).

번호 매기기·파일 바꾸기·기록 남기기는 프로젝트 잠금(`work/.lock` — lock.py) 안에서 한다. 파일 여럿을 바꾸는 일은 하나라도
바꾸지 못하면 이미 바꾼 것을 되돌리고(반쯤 바뀐 채 남지 않게) 그 파일 이름과 함께 알린다.
"""

import difflib
import glob
import hashlib
import json
import os
import shutil
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional

from .lock import FileBusy, as_busy, locked, read_bytes, replace_files, tmp_dir
from .store import WORK_DIR, dumps, move_into_place, now_iso

HIST_DIR = os.path.join(WORK_DIR, "history")
FORMAT = "equion-change"
FORMAT_VERSION = 1
PATTERNS = ("equion.toml", "EQUATIONS/*.txt", "EQUATIONS/*.toml", "DATA/series.toml", "DATA/derived.txt",
            "ASSUMPTIONS/*.csv", "ASSUMPTIONS/*.toml", "ADDFACTORS/*.csv", "ADDFACTORS/*.toml",
            "SCENARIOS/*.toml", "VIEWS/*.toml", "notes/*.md", "reports/*.md", "FLOWS/*.eqs")


def _sha(data: Optional[bytes]) -> Optional[str]:
    return None if data is None else hashlib.sha256(data).hexdigest()


def _read(path: str, root: str = None) -> Optional[bytes]:
    """파일 내용(없으면 None) — 다른 프로그램이 쥐고 있어 읽을 수 없으면 FileBusy."""
    return read_bytes(path, root)


def _rel(root, p):
    return os.path.relpath(p, root).replace(os.sep, "/")


# ---- 줄바꿈 ----------------------------------------------------------------
def _lf(data: Optional[bytes]) -> Optional[bytes]:
    return None if data is None else data.replace(b"\r\n", b"\n")


def _eol(data: Optional[bytes]) -> bytes:
    """그 내용의 줄바꿈 — CRLF가 더 많으면 CRLF, 아니면 LF."""
    if not data:
        return b"\n"
    crlf = data.count(b"\r\n")
    return b"\r\n" if crlf and crlf >= data.count(b"\n") - crlf else b"\n"


def _with_eol(data: Optional[bytes], eol: bytes) -> Optional[bytes]:
    if data is None:
        return None
    d = _lf(data)
    return d.replace(b"\n", b"\r\n") if eol == b"\r\n" else d


def _same(a: Optional[bytes], b: Optional[bytes]) -> bool:
    """줄바꿈을 맞추고 보면 같은 내용인가(둘 다 없음도 같음)."""
    if a is None or b is None:
        return a is None and b is None
    return a == b or _lf(a) == _lf(b)


def _follow_eol(data: bytes, old: Optional[bytes]) -> bytes:
    """새 내용을 지금 파일의 줄바꿈으로 — 지금 파일이 CRLF이고 새 내용이 LF뿐이면 CRLF로(명령이 쓴 줄만 LF가 되지 않게)."""
    if old is None or b"\r\n" in data or b"\n" not in data or _eol(old) != b"\r\n":
        return data
    return _with_eol(data, b"\r\n")


def _warn(msg: str) -> None:
    """표준오류에 경고 한 줄(--json의 표준출력을 더럽히지 않게)."""
    try:
        print(f"equion: 경고: {msg}", file=sys.stderr)
    except (OSError, ValueError):
        pass


class RevertConflict(ValueError):
    """되돌리기가 뒤의 바뀜과 겹친다 — `.change`(되돌리려던 바뀜) · `.files`({파일: [뒤의 바뀜 id]}). 아무것도 쓰지 않았다."""

    def __init__(self, message: str, change: str, files: Dict[str, List[str]]):
        super().__init__(message)
        self.change = change
        self.files = files


# ---- 되돌리기의 줄 단위 합치기(그 바뀜만 거꾸로) ----------------------------
_NONE = object()


def _lines(data: bytes) -> List[str]:
    return data.decode("utf-8", "surrogateescape").splitlines(keepends=True)


def _regions(base: List[str], other: List[str]):
    """base → other의 바뀐 구간 [(i1, i2, 새 줄들)] (base 기준 위치)."""
    sm = difflib.SequenceMatcher(None, base, other, autojunk=False)
    return [(i1, i2, other[j1:j2]) for tag, i1, i2, j1, j2 in sm.get_opcodes() if tag != "equal"]


def _clash(r, q) -> bool:
    """두 구간(서로 다른 쪽)이 겹치나 — 같은 줄을 고쳤거나, 같은 자리에 둘 다 넣었거나, 한쪽이 넣은 자리가 다른 쪽이 고친 줄 사이."""
    (a1, a2), (b1, b2) = r[:2], q[:2]
    if max(a1, b1) < min(a2, b2):
        return True
    if a1 == a2 and b1 == b2:
        return a1 == b1
    if a1 == a2:
        return b1 < a1 < b2
    if b1 == b2:
        return a1 < b1 < a2
    return False


def _apply(base: List[str], regs, g1: int, g2: int) -> List[str]:
    out, pos = [], g1
    for i1, i2, new in sorted(regs, key=lambda r: (r[0], r[1])):
        out += base[pos:i1] + list(new)
        pos = i2
    return out + base[pos:g2]


def merge_revert(after: bytes, before: bytes, now: bytes) -> Optional[bytes]:
    """바뀜(before → after)만 지금 내용(now)에서 거꾸로 적용한 내용 — 뒤의 바뀜과 겹치면 None.

    3방향 합치기: 바탕 = after, 한쪽 = now(뒤의 바뀜), 다른 쪽 = before(되돌리기). 두 쪽이 서로 다른 줄을 고쳤으면 둘 다 살리고,
    같은 줄을 고쳤으면(바로 옆 줄은 겹침이 아니다) 겹침이다. 줄바꿈(LF·CRLF)은 맞춘 뒤 견주고, 결과는 지금 내용(now)의 줄바꿈으로."""
    eol = _eol(now)
    out = _merge_lf(_lf(after), _lf(before), _lf(now))
    return None if out is None else _with_eol(out, eol)


def _merge_lf(after: bytes, before: bytes, now: bytes) -> Optional[bytes]:
    base, ours, theirs = _lines(after), _lines(now), _lines(before)
    regs = [("o", *r) for r in _regions(base, ours)] + [("t", *r) for r in _regions(base, theirs)]
    n = len(regs)
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for i in range(n):
        for j in range(i + 1, n):
            if regs[i][0] != regs[j][0] and _clash(regs[i][1:], regs[j][1:]):
                parent[find(i)] = find(j)
    groups: Dict[int, list] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(regs[i])
    units = []
    for g in groups.values():
        g1, g2 = min(r[1] for r in g), max(r[2] for r in g)
        sides = {r[0] for r in g}
        if len(sides) == 1:
            units += [(r[1], r[2], r[3]) for r in g]
            continue
        o = _apply(base, [r[1:] for r in g if r[0] == "o"], g1, g2)
        t = _apply(base, [r[1:] for r in g if r[0] == "t"], g1, g2)
        seg = base[g1:g2]
        if o == t or t == seg:
            units.append((g1, g2, o))
        elif o == seg:
            units.append((g1, g2, t))
        else:
            return None
    units.sort(key=lambda u: (u[0], u[1]))
    for u, v in zip(units, units[1:]):               # 한 쪽의 구간이 다른 묶음 안에 들어가면(드문 경우) 겹침으로 본다
        if v[0] < u[1]:
            return None
    out = "".join(_apply(base, units, 0, len(base)))
    return out.encode("utf-8", "surrogateescape")


def _flat(d, pre=()):
    out = {}
    for k, v in d.items():
        if isinstance(v, dict) and v:
            out.update(_flat(v, pre + (k,)))
        else:
            out[pre + (k,)] = v
    return out


def _toml_ok(after: bytes, before: bytes, now: bytes, merged: bytes) -> bool:
    """TOML 파일이면 키마다 뜻으로도 맞는지 — 되돌리기가 고친 키는 그 바뀜 앞 값, 아니면 지금 값. 줄로는 맞아도 표 머리가 빠져
    키가 다른 표로 붙는 것 같은 일을 막는다. 앞뒤 내용을 읽을 수 없으면(사람이 깨뜨린 파일) 줄 합치기를 그대로 믿는다."""
    import tomllib
    try:
        a, b, c = (_flat(tomllib.loads(x.decode("utf-8-sig"))) for x in (after, before, now))
    except (ValueError, UnicodeDecodeError):
        return True
    try:
        m = _flat(tomllib.loads(merged.decode("utf-8-sig")))
    except (ValueError, UnicodeDecodeError):
        return False
    for k in set(a) | set(b) | set(c) | set(m):
        va, vb, vc, vm = (x.get(k, _NONE) for x in (a, b, c, m))
        if va == vb:
            want = vc
        elif va == vc or vb == vc:
            want = vb
        else:
            return False
        if vm != want:
            return False
    return True


def tracked(root: str, extra: List[str] = ()) -> List[str]:
    """바뀜 기록을 남기는 정의 파일(프로젝트 기준 경로) — 블록 파일·equion.toml·자료 정의·가정·보정항·시나리오·보기."""
    out = set()
    for pat in PATTERNS:
        for p in glob.glob(os.path.join(root, pat)):
            if os.path.isfile(p):
                out.add(_rel(root, p))
    for e in extra:
        if os.path.isfile(os.path.join(root, e)):
            out.add(e.replace(os.sep, "/"))
    return sorted(out)


@dataclass
class Change:
    """바뀜 하나 — `.id`(h0003) · `.who` · `.how` · `.files`({경로: {before, after}}) · `.diff`."""

    id: str
    created: str
    who: str
    how: str
    note: str
    files: Dict[str, dict]
    diff: str = ""
    path: str = ""
    reverts: Optional[str] = None
    run: Optional[str] = None          # 스크립트 실행(run:…) 안에서 바뀌었으면 그 실행

    def text(self) -> str:
        """명령줄에 보이는 짧은 글."""
        verb = {"added": "새로", "removed": "지움", "changed": "고침"}
        from .store import WHO_KO
        fl = " · ".join(f"{p}({verb[v['op']]})" for p, v in self.files.items())
        return (f"[{self.id}] {self.created} · {WHO_KO.get(self.who, self.who)} · {self.how}"
                + (f" ({self.run})" if self.run else "") + f"\n  파일   {fl}"
                + (f"\n  메모   {self.note}" if self.note else ""))

    def to_dict(self) -> dict:
        """명령줄 --json과 같은 사전."""
        return {"id": self.id, "created": self.created, "who": self.who, "how": self.how, "note": self.note,
                "files": self.files, "reverts": self.reverts, "run": self.run, "diff": self.diff}


class History:
    """프로젝트의 바뀜 기록."""

    def __init__(self, root: str, extra: List[str] = ()):
        self.root = root
        self.base = os.path.join(root, HIST_DIR)
        self.extra = list(extra)
        self.skipped: List[str] = []        # 지난 scan이 읽지 못해 건너뛴 파일

    # ---- 상태(지난번에 본 내용) -----------------------------------------
    def _state_dir(self):
        return os.path.join(self.base, "state")

    def _state(self) -> Dict[str, bytes]:
        d = self._state_dir()
        out = {}
        if not os.path.isdir(d):
            return out
        for r, _, fs in os.walk(d):
            for fn in fs:
                p = os.path.join(r, fn)
                out[_rel(d, p)] = _read(p)
        return out

    def _set_state(self, rel: str, data: Optional[bytes]):
        p = os.path.join(self._state_dir(), rel)
        if data is None:
            if os.path.exists(p):
                os.remove(p)
            return
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as f:
            f.write(data)

    def _ids(self) -> List[str]:
        if not os.path.isdir(self.base):
            return []
        return sorted((n for n in os.listdir(self.base)
                       if n.startswith("h") and n[1:].isdigit() and os.path.isfile(os.path.join(self.base, n, "change.json"))),
                      key=lambda n: int(n[1:]))                # h10000이 h9999 뒤에 오게(글자 순이 아니라 번호 순)

    def _next(self) -> str:
        ids = self._ids()
        return f"h{(int(ids[-1][1:]) if ids else 0) + 1:04d}"

    # ---- 쓰기 ----------------------------------------------------------
    def _prepare(self, before: Dict[str, Optional[bytes]], after: Dict[str, Optional[bytes]], who: str, how: str,
                 note: str = "", reverts: str = None):
        """바뀜 기록을 임시 폴더에 다 쓴다 → (Change, 임시 폴더) · 바뀐 것이 없으면 None. 잠금 안에서 부른다(번호)."""
        files, diffs = {}, []
        for rel in sorted(set(before) | set(after)):
            b, a = before.get(rel), after.get(rel)
            if b == a:
                continue
            op = "added" if b is None else ("removed" if a is None else "changed")
            files[rel] = {"op": op, "before": _sha(b), "after": _sha(a)}
            bt = _lf(b or b"").decode("utf-8", "replace").splitlines(keepends=True)
            at = _lf(a or b"").decode("utf-8", "replace").splitlines(keepends=True)
            if b is not None and a is not None and bt == at:          # 줄바꿈만 바뀜 — 모든 줄이 바뀐 것처럼 보이지 않게
                names = {b"\n": "LF", b"\r\n": "CRLF"}
                diffs.append(f"--- a/{rel}\n+++ b/{rel}\n# 줄바꿈만 바뀜({names[_eol(b)]} → {names[_eol(a)]}) — 내용은 같습니다\n")
                continue
            diffs.append("".join(difflib.unified_diff(bt, at, f"a/{rel}", f"b/{rel}")))
        if not files:
            return None
        cid = self._next()
        os.makedirs(self.base, exist_ok=True)
        tmp = tmp_dir(self.base, cid)
        try:
            for side, src in (("before", before), ("after", after)):
                for rel in files:
                    data = src.get(rel)
                    if data is None:
                        continue
                    p = os.path.join(tmp, side, rel)
                    os.makedirs(os.path.dirname(p), exist_ok=True)
                    with open(p, "wb") as f:
                        f.write(data)
            os.makedirs(tmp, exist_ok=True)
            ch = Change(cid, now_iso(), who, how, note, files, "\n".join(diffs), os.path.join(self.base, cid), reverts,
                        os.environ.get("EQUION_RUN") if who != "바깥" else None)
            meta = {"format": FORMAT, "format_version": FORMAT_VERSION, **ch.to_dict()}
            meta.pop("diff")
            with open(os.path.join(tmp, "change.json"), "w", encoding="utf-8", newline="\n") as f:
                f.write(dumps(meta))
            with open(os.path.join(tmp, "diff.txt"), "w", encoding="utf-8", newline="\n") as f:
                f.write(ch.diff)
        except OSError as e:
            shutil.rmtree(tmp, ignore_errors=True)
            raise as_busy(e, _rel(self.root, tmp)) from None
        return ch, tmp

    def _commit(self, ch: Change, tmp: str, after: Dict[str, Optional[bytes]]):
        """임시 폴더의 바뀜 기록을 제자리로 옮기고 '지난번에 본 내용'을 고친다."""
        try:
            move_into_place(tmp, ch.path)
        except OSError as e:
            shutil.rmtree(tmp, ignore_errors=True)
            raise as_busy(e, _rel(self.root, ch.path)) from None
        for rel in ch.files:
            try:
                self._set_state(rel, after.get(rel))
            except OSError:
                pass                                  # 다음 명령이 '바깥' 바뀜으로 한 번 더 적을 뿐 — 기록은 남았다

    def _write(self, before: Dict[str, Optional[bytes]], after: Dict[str, Optional[bytes]], who: str, how: str,
               note: str = "", reverts: str = None) -> Optional[Change]:
        prep = self._prepare(before, after, who, how, note, reverts)
        if prep is None:
            return None
        ch, tmp = prep
        self._commit(ch, tmp, after)
        return ch

    @locked
    def scan(self) -> Optional[Change]:
        """명령 밖에서 바뀐 정의 파일을 '바깥' 바뀜으로 적는다. 처음이면 지금 내용을 기준으로 삼고 아무것도 적지 않는다.

        다른 프로그램이 쥐고 있어 읽을 수 없는 파일은 이번에는 건너뛰고(표준오류에 경고 — `.skipped`) 다음 명령 때 다시 본다
        — 계산만 하는 명령(hs·sim·est)이 그 파일 하나 때문에 멈추지 않게."""
        state = self._state()
        now, skipped = {}, []
        for rel in sorted(set(tracked(self.root, self.extra)) | set(state)):
            try:
                now[rel] = _read(os.path.join(self.root, rel), self.root)
            except FileBusy:
                skipped.append(rel)
        self.skipped = skipped
        for rel in skipped:
            _warn(f"다른 프로그램(엑셀·동기화·백신 등)이 {rel}을(를) 쥐고 있어 바뀜 기록 검사에서 이번에는 건너뜁니다(다음 명령 때 다시 봅니다)")
        now = {k: v for k, v in now.items() if v is not None or k in state}
        if not os.path.isdir(self._state_dir()):
            for rel, data in now.items():
                self._set_state(rel, data)
            os.makedirs(self._state_dir(), exist_ok=True)
            return None
        keys = (set(state) | set(now)) - set(skipped)
        before = {rel: state.get(rel) for rel in keys}
        after = {rel: now.get(rel) for rel in keys}
        return self._write(before, after, "바깥", "명령 밖에서 고침(편집기·직접 편집)")

    @locked
    def write_files(self, new: Dict[str, Optional[str]], who: str, how: str, note: str = "",
                    reverts: str = None) -> Optional[Change]:
        """정의 파일을 고치고 바뀜 기록을 남긴다 — new: {경로: 새 내용(None이면 지움)}. 먼저 바깥 바뀜을 따로 적는다.

        프로젝트 잠금 안에서: 바뀜 기록을 임시 폴더에 다 쓴 뒤 파일을 한 묶음으로 바꾸고(하나라도 바꾸지 못하면 이미 바꾼 것을
        되돌린다) 마지막에 바뀜 기록을 제자리로 옮긴다. 다른 프로그램이 파일을 쥐고 있으면 FileBusy(그 파일 이름 — 아무것도 바꾸지
        않음). 지금 파일이 CRLF면 새 내용도 CRLF로 쓴다(줄바꿈은 지금 파일을 따른다)."""
        self.scan()
        before, after = {}, {}
        for rel, text in new.items():
            rel = rel.replace(os.sep, "/")
            p = os.path.join(self.root, rel)
            b = _read(p, self.root)
            data = None if text is None else (text.encode("utf-8") if isinstance(text, str) else text)
            if data is not None:
                data = _follow_eol(data, b)
            before[rel], after[rel] = b, data
        prep = self._prepare(before, after, who, how, note, reverts)
        if prep is None:
            return None
        ch, tmp = prep
        paths = {rel: os.path.join(self.root, rel) for rel in ch.files}
        try:
            replace_files({paths[r]: after[r] for r in ch.files}, root=self.root,
                          before={paths[r]: before[r] for r in ch.files})
        except BaseException:
            shutil.rmtree(tmp, ignore_errors=True)
            raise
        try:
            self._commit(ch, tmp, after)
        except OSError:
            try:                                      # 기록을 남기지 못했으면 파일도 되돌린다(기록 없는 바뀜이 남지 않게)
                replace_files({paths[r]: before[r] for r in ch.files}, root=self.root,
                              before={paths[r]: after[r] for r in ch.files})
            except OSError:
                pass
            raise
        return ch

    # ---- 읽기·되돌리기 ---------------------------------------------------
    def list(self) -> List[Change]:
        """바뀜 기록(오래된 것부터)."""
        return [self.get(c) for c in self._ids()]

    def get(self, cid: str) -> Change:
        """바뀜 하나."""
        p = os.path.join(self.base, cid, "change.json")
        if not os.path.isfile(p):
            raise KeyError(f"없는 바뀜 기록 {cid} (있는 것: {', '.join(self._ids()[-8:]) or '없음'})")
        with open(p, encoding="utf-8") as f:
            m = json.load(f)
        diff = _read(os.path.join(self.base, cid, "diff.txt")) or b""
        return Change(m["id"], m["created"], m["who"], m["how"], m.get("note", ""), m["files"],
                      diff.decode("utf-8", "replace"), os.path.join(self.base, cid), m.get("reverts"), m.get("run"))

    def later(self, cid: str, rel: str = None) -> List[Change]:
        """그 바뀜 뒤의 바뀜(오래된 것부터) — rel을 주면 그 파일을 고친 것만."""
        ids = self._ids()
        after = ids[ids.index(cid) + 1:] if cid in ids else []
        out = [self.get(i) for i in after]
        return [c for c in out if rel is None or rel in c.files]

    @locked
    def revert(self, cid: str, who: str, how: str = None, files: List[str] = None, force: bool = False) -> Optional[Change]:
        """그 바뀜 **하나만** 되돌린다 — 그 뒤에 같은 파일이 또 바뀌었으면 그 바뀜의 차이만 지금 내용에서 거꾸로 적용한다(뒤의 바뀜은 그대로).

        뒤의 바뀜이 같은 줄(TOML이면 같은 키)을 고쳤거나 그 파일을 새로 만들었다·지웠으면 그 바뀜만 물릴 수 없다 — RevertConflict
        (ValueError, 아무것도 쓰지 않음, 메시지에 뒤의 바뀜 목록). force=True면 뒤의 바뀜까지 버리고 그 파일을 그 바뀜 앞 내용으로
        통째로 쓴다. 되돌리기도 바뀜 기록에 남는다(되돌리기의 되돌리기도 된다). files를 주면 그 바뀜이 고친 파일 가운데 그것만
        되돌린다(파일 여럿을 고친 바뀜에서 하나만 물릴 때). 그 바뀜에 없는 파일이면 KeyError."""
        self.scan()                                   # 명령 밖에서 고친 것도 '뒤의 바뀜'으로 먼저 적는다
        ch = self.get(cid)
        want = None
        if files:
            want = [str(f).replace(os.sep, "/") for f in files]
            missing = [f for f in want if f not in ch.files]
            if missing:
                raise KeyError(f"{cid}이(가) 고친 파일이 아닙니다: {', '.join(missing)} (고친 파일: {', '.join(ch.files)})")
        new, merged, whole, clash = {}, [], [], {}
        for rel, v in ch.files.items():
            if want is not None and rel not in want:
                continue
            b = None if v["op"] == "added" else _read(os.path.join(ch.path, "before", rel))
            a = None if v["op"] == "removed" else _read(os.path.join(ch.path, "after", rel))
            now = _read(os.path.join(self.root, rel), self.root)
            if now == a or now == b or force:          # 뒤에 그 파일이 안 바뀜 · 이미 되돌려짐 · 통째로
                new[rel] = b
                if force and not (_same(now, a) or _same(now, b)):
                    whole.append(rel)
                continue
            if _same(now, a):                          # 뒤에 줄바꿈만 바뀜 — 그 바뀜 앞 내용을 지금 줄바꿈으로
                new[rel] = _with_eol(b, _eol(now))
                continue
            if _same(now, b):                          # 이미 되돌려짐(줄바꿈만 다름)
                new[rel] = now
                continue
            out = None
            toml = rel.lower().endswith(".toml")
            # 새로 만든 파일은 TOML(채택표·시나리오 …)만 키로 가려 물린다 — 다른 파일은 뒤의 바뀜이 그 위에 쓴 글이라 겹침
            b0 = b if b is not None else (b"" if toml else None)
            if a is not None and b0 is not None and now is not None:
                out = merge_revert(a, b0, now)
                if out is not None and toml and not _toml_ok(a, b0, now, out):
                    out = None
            if out is None:
                clash[rel] = [c.id for c in self.later(cid, rel)]
                continue
            new[rel] = None if (b is None and not out.strip()) else out
            merged.append(rel)
        if clash:
            raise RevertConflict(self._clash_text(cid, ch, clash), cid, clash)
        note = f"{cid} 되돌리기" + (f"({', '.join(want)}만)" if want is not None else "")
        if merged:
            keep = sorted({c.id for rel in merged for c in self.later(cid, rel)})
            note += f" — 그 바뀜만 물림(뒤의 바뀜 {'·'.join(keep)}은(는) 그대로)"
        if whole:
            drop = sorted({c.id for rel in whole for c in self.later(cid, rel)})
            note += f" — --force: {', '.join(whole)}을(를) 통째로 그 앞 내용으로(뒤의 바뀜 {'·'.join(drop)}도 그 파일에서 함께 물림)"
        return self.write_files(new, who, how or f"history revert {cid}", note=note, reverts=cid)

    def _clash_text(self, cid: str, ch: Change, clash: Dict[str, List[str]]) -> str:
        L = [f"{cid}({ch.how})을(를) 되돌릴 수 없습니다 — 그 뒤의 바뀜이 같은 곳을 고쳐서 그 바뀜만 물리면 뒤의 바뀜과 겹칩니다. "
             "파일은 그대로 두었습니다."]
        for rel, ids in clash.items():
            bits = []
            for i in ids:
                c = self.get(i)
                bits.append(f"{i}({c.how if len(c.how) <= 60 else c.how[:57] + '…'})")
            L.append(f"  {rel}: 뒤의 바뀜 " + (" · ".join(bits) if bits else "(기록 없음)"))
        first = ", ".join(clash)
        L.append(f"  할 수 있는 것: 뒤의 바뀜을 먼저 되돌리거나(새것부터), 그 파일을 직접 고친다. 뒤의 바뀜까지 버리고 {first}을(를) "
                 f"{cid} 앞 내용으로 통째로 되돌리려면 --force(equion history revert {cid} --force)")
        return "\n".join(L)
