#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""바뀜 기록 (D33·K7) — 정의 파일이 바뀔 때마다 `work/history/<번호>/`에 전후 내용과 차이를 남긴다.

    work/history/
      state/          지난번에 본 정의 파일의 사본 — 바깥에서 고친 것(편집기·Claude의 직접 편집)을 알아보는 기준
      h0001/          change.json(때·누가·어떻게·파일마다 전후 해시) · before/<경로> · after/<경로> · diff.txt

누가: 명령(`adopt`·`data use`·`propose apply`·`history revert` — 명령 그대로)이 바꾸면 그 명령으로, 명령 밖에서 바뀐 것은 다음 명령 때
'바깥'으로 적는다. 되돌리기는 이전 내용으로 다시 쓰는 것이고 그것도 바뀜 기록에 남는다(지우지 않는다).
"""

import difflib
import glob
import hashlib
import json
import os
import shutil
from dataclasses import dataclass
from typing import Dict, List, Optional

from .store import WORK_DIR, dumps, move_into_place, now_iso

HIST_DIR = os.path.join(WORK_DIR, "history")
FORMAT = "equion-change"
FORMAT_VERSION = 1
PATTERNS = ("equion.toml", "EQUATIONS/*.txt", "EQUATIONS/*.toml", "DATA/series.toml", "DATA/derived.txt",
            "ASSUMPTIONS/*.csv", "ASSUMPTIONS/*.toml", "ADDFACTORS/*.csv", "ADDFACTORS/*.toml",
            "SCENARIOS/*.toml", "VIEWS/*.toml", "notes/*.md", "reports/*.md", "FLOWS/*.eqs")


def _sha(data: Optional[bytes]) -> Optional[str]:
    return None if data is None else hashlib.sha256(data).hexdigest()


def _read(path: str) -> Optional[bytes]:
    try:
        with open(path, "rb") as f:
            return f.read()
    except FileNotFoundError:
        return None


def _rel(root, p):
    return os.path.relpath(p, root).replace(os.sep, "/")


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
        return sorted(n for n in os.listdir(self.base)
                      if n.startswith("h") and n[1:].isdigit() and os.path.isfile(os.path.join(self.base, n, "change.json")))

    def _next(self) -> str:
        ids = self._ids()
        return f"h{(int(ids[-1][1:]) if ids else 0) + 1:04d}"

    # ---- 쓰기 ----------------------------------------------------------
    def _write(self, before: Dict[str, Optional[bytes]], after: Dict[str, Optional[bytes]], who: str, how: str,
               note: str = "", reverts: str = None) -> Optional[Change]:
        files, diffs = {}, []
        for rel in sorted(set(before) | set(after)):
            b, a = before.get(rel), after.get(rel)
            if b == a:
                continue
            op = "added" if b is None else ("removed" if a is None else "changed")
            files[rel] = {"op": op, "before": _sha(b), "after": _sha(a)}
            bt = (b or b"").decode("utf-8", "replace").splitlines(keepends=True)
            at = (a or b"").decode("utf-8", "replace").splitlines(keepends=True)
            diffs.append("".join(difflib.unified_diff(bt, at, f"a/{rel}", f"b/{rel}")))
        if not files:
            return None
        cid = self._next()
        os.makedirs(self.base, exist_ok=True)
        tmp = os.path.join(self.base, f".tmp-{cid}")
        shutil.rmtree(tmp, ignore_errors=True)
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
        move_into_place(tmp, os.path.join(self.base, cid))
        for rel in files:
            self._set_state(rel, after.get(rel))
        return ch

    def scan(self) -> Optional[Change]:
        """명령 밖에서 바뀐 정의 파일을 '바깥' 바뀜으로 적는다. 처음이면 지금 내용을 기준으로 삼고 아무것도 적지 않는다."""
        state = self._state()
        now = {rel: _read(os.path.join(self.root, rel)) for rel in set(tracked(self.root, self.extra)) | set(state)}
        now = {k: v for k, v in now.items() if v is not None or k in state}
        if not os.path.isdir(self._state_dir()):
            for rel, data in now.items():
                self._set_state(rel, data)
            os.makedirs(self._state_dir(), exist_ok=True)
            return None
        before = {rel: state.get(rel) for rel in set(state) | set(now)}
        after = {rel: now.get(rel) for rel in set(state) | set(now)}
        return self._write(before, after, "바깥", "명령 밖에서 고침(편집기·직접 편집)")

    def write_files(self, new: Dict[str, Optional[str]], who: str, how: str, note: str = "",
                    reverts: str = None) -> Optional[Change]:
        """정의 파일을 고치고 바뀜 기록을 남긴다 — new: {경로: 새 내용(None이면 지움)}. 먼저 바깥 바뀜을 따로 적는다."""
        self.scan()
        before, after = {}, {}
        for rel, text in new.items():
            rel = rel.replace(os.sep, "/")
            p = os.path.join(self.root, rel)
            before[rel] = _read(p)
            data = None if text is None else (text.encode("utf-8") if isinstance(text, str) else text)
            after[rel] = data
            if data is None:
                if os.path.exists(p):
                    os.remove(p)
            else:
                os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
                tmp = p + ".tmp-equion"
                with open(tmp, "wb") as f:
                    f.write(data)
                move_into_place(tmp, p)
        return self._write(before, after, who, how, note, reverts)

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

    def revert(self, cid: str, who: str, how: str = None, files: List[str] = None) -> Optional[Change]:
        """그 바뀜 앞의 내용으로 되돌린다(그 뒤에 같은 파일이 또 바뀌었어도 — 지금 내용과의 차이가 새 바뀜으로 남는다).
        files를 주면 그 바뀜이 고친 파일 가운데 그것만 되돌린다(파일 여럿을 고친 바뀜에서 하나만 물릴 때). 그 바뀜에 없는 파일이면 KeyError."""
        ch = self.get(cid)
        want = None
        if files:
            want = [str(f).replace(os.sep, "/") for f in files]
            missing = [f for f in want if f not in ch.files]
            if missing:
                raise KeyError(f"{cid}이(가) 고친 파일이 아닙니다: {', '.join(missing)} (고친 파일: {', '.join(ch.files)})")
        new = {}
        for rel, v in ch.files.items():
            if want is not None and rel not in want:
                continue
            b = _read(os.path.join(ch.path, "before", rel))
            new[rel] = None if v["op"] == "added" else b
        return self.write_files(new, who, how or f"history revert {cid}",
                                note=f"{cid} 되돌리기" + (f"({', '.join(want)}만)" if want is not None else ""), reverts=cid)
