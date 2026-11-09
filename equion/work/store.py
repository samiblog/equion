#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""작업 기록 저장소 (D33) — 계산할 때마다 `work/<종류>/<이름>/`에 기록 하나, `work/log.jsonl`에 한 줄.

    work/
      log.jsonl                 한 줄에 기록 하나: id · 시각 · 누가 · 명령 그대로 · 종류 · 대상 · 핵심 수치 · 경로
      marks.json                고정·메모(기록 자체는 고치지 않는다)
      est/<이름>/               record.json · coefs.csv · series.csv · summary.md
      hs/<이름>/                record.json · assembly.json(조립 명세) · stats.csv · solved.csv · status.csv · summary.md
      sim/<이름>/               record.json · assembly.json · levels.csv · growth.csv · diff.csv · summary.md

기록 이름은 `종류:이름`(`est:cons_c5` · `hs:hs_0003`). 기록은 고치지 않는다 — 다시 계산하면 새 기록이다. 쓰기는 임시 폴더에 다 쓴 뒤
한 번에 옮긴다(반쯤 쓴 기록이 남지 않게).
"""

import json
import os
import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd

FORMAT = "equion-record"
FORMAT_VERSION = 1
WORK_DIR = "work"
KINDS = ("est", "hs", "sim")
KIND_KO = {"est": "추정", "hs": "과거 재현", "sim": "전망", "data": "자료 회차"}
NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_\-]*$")
WHO_KO = {"terminal": "터미널", "claude": "Claude", "desk": "Desk", "python": "Python", "script": "스크립트"}


class RecordError(ValueError):
    """기록 이름·찾기 문제(없는 기록·이미 있는 이름 등)."""


def detect_who(default: str = "python") -> str:
    """누가 계산했나 — EQUION_WHO(Desk·스크립트가 정한다) · Claude Code 안(CLAUDECODE) · 그 밖은 default."""
    w = os.environ.get("EQUION_WHO", "").strip().lower()
    if w:
        return w
    if os.environ.get("CLAUDECODE"):
        return "claude"
    return default


def now_iso(now: datetime = None) -> str:
    return (now or datetime.now()).isoformat(timespec="seconds")


def _jsonable(o):
    """numpy·pandas 값을 JSON으로(NaN은 null)."""
    import numpy as np
    if isinstance(o, dict):
        return {str(k): _jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating, float)):
        f = float(o)
        return None if f != f or f in (float("inf"), float("-inf")) else f
    if isinstance(o, np.ndarray):
        return _jsonable(o.tolist())
    if isinstance(o, (np.bool_,)):
        return bool(o)
    return o


def dumps(o) -> str:
    return json.dumps(_jsonable(o), ensure_ascii=False, indent=2)


@dataclass
class Record:
    """작업 기록 하나(읽기 전용) — `.id`(`종류:이름`) · `.meta`(record.json) · `.path` · `.read_csv(이름)` · `.summary_md()`."""

    kind: str
    name: str
    path: str
    meta: dict = field(default_factory=dict)

    @property
    def id(self) -> str:
        """기록 이름 `종류:이름`."""
        return f"{self.kind}:{self.name}"

    def file(self, fname: str) -> str:
        """기록 폴더 안 파일의 경로."""
        return os.path.join(self.path, fname)

    def read_json(self, fname: str) -> dict:
        """기록 폴더의 JSON 파일."""
        with open(self.file(fname), encoding="utf-8") as f:
            return json.load(f)

    def read_csv(self, fname: str, index_col=0) -> pd.DataFrame:
        """기록 폴더의 CSV(첫 열이 기간 라벨)."""
        df = pd.read_csv(self.file(fname), index_col=index_col)
        if index_col is not None:
            df.index = df.index.astype(str)
        return df

    def summary_md(self) -> str:
        """사람이 읽는 카드(summary.md)."""
        with open(self.file("summary.md"), encoding="utf-8") as f:
            return f.read()

    def __repr__(self):
        return f"<기록 {self.id}>"


class WorkStore:
    """프로젝트의 `work/` — 기록 쓰기·찾기·목록·고정."""

    def __init__(self, root: str):
        self.root = root
        self.base = os.path.join(root, WORK_DIR)

    # ---- 이름 ----------------------------------------------------------
    @staticmethod
    def split(rid: str):
        """'est:cons_c5' → ('est', 'cons_c5')."""
        kind, sep, name = str(rid).strip().partition(":")
        if not sep or kind not in KINDS or not NAME_RE.match(name):
            raise RecordError(f"기록 이름은 종류:이름입니다(예: est:cons_c5 · hs:hs_0003) — {rid!r}")
        return kind, name

    def dir(self, kind: str) -> str:
        """그 종류의 기록 폴더(work/<종류>)."""
        return os.path.join(self.base, kind)

    def exists(self, kind: str, name: str) -> bool:
        """그 기록이 있으면 참."""
        return os.path.isfile(os.path.join(self.dir(kind), name, "record.json"))

    def names(self, kind: str) -> List[str]:
        """그 종류의 기록 이름(가나다순)."""
        d = self.dir(kind)
        if not os.path.isdir(d):
            return []
        return sorted(n for n in os.listdir(d) if os.path.isfile(os.path.join(d, n, "record.json")))

    def next_name(self, kind: str, prefix: str) -> str:
        """prefix_0001, prefix_0002 … — 같은 앞글자의 가장 큰 번호 다음."""
        rx = re.compile(rf"^{re.escape(prefix)}_(\d+)$")
        nums = [int(m[1]) for n in self.names(kind) for m in [rx.match(n)] if m]
        return f"{prefix}_{(max(nums) if nums else 0) + 1:04d}"

    def check_new(self, kind: str, name: str):
        """새 기록 이름을 검사한다 — 글자가 틀리거나 이미 있으면 RecordError(기록은 고치지 않는다)."""
        if not NAME_RE.match(name or ""):
            raise RecordError(f"기록 이름은 영문으로 시작하고 영문·숫자·_·-만: {name!r}")
        if self.exists(kind, name):
            raise RecordError(f"이미 있는 기록 {kind}:{name} — 기록은 고치지 않습니다(다른 이름으로 --as)")

    # ---- 쓰기 ----------------------------------------------------------
    def write(self, kind: str, name: str, meta: dict, files: Dict[str, object], summary: str,
              log: dict = None) -> Record:
        """기록 하나를 쓴다 — files의 값은 글자·DataFrame(CSV)·dict(JSON). record.json·summary.md를 더하고 log.jsonl에 한 줄."""
        self.check_new(kind, name)
        d = self.dir(kind)
        os.makedirs(d, exist_ok=True)
        tmp = os.path.join(d, f".tmp-{name}")
        shutil.rmtree(tmp, ignore_errors=True)
        os.makedirs(tmp)
        meta = dict(meta)
        meta.setdefault("format", FORMAT)
        meta.setdefault("format_version", FORMAT_VERSION)
        meta["id"] = f"{kind}:{name}"
        meta["kind"] = kind
        meta.setdefault("created", now_iso())
        out = dict(files)
        out["record.json"] = meta
        out["summary.md"] = summary
        for fn, v in out.items():
            p = os.path.join(tmp, fn)
            if isinstance(v, pd.DataFrame):
                v.to_csv(p, lineterminator="\n")
                continue
            text = dumps(v) if isinstance(v, (dict, list)) else str(v)
            with open(p, "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
        final = os.path.join(d, name)
        os.replace(tmp, final)
        line = {"id": meta["id"], "created": meta["created"], "who": meta.get("who"), "command": meta.get("command"),
                "kind": kind, "target": meta.get("target"), "path": os.path.relpath(final, self.root).replace(os.sep, "/")}
        line.update(log or {})
        os.makedirs(self.base, exist_ok=True)
        with open(os.path.join(self.base, "log.jsonl"), "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(_jsonable(line), ensure_ascii=False) + "\n")
        return Record(kind, name, final, meta)

    # ---- 읽기 ----------------------------------------------------------
    def get(self, rid: str, kind: str = None) -> Record:
        """기록 하나. kind를 주면 그 종류여야 한다."""
        k, n = self.split(rid)
        if kind and k != kind:
            raise RecordError(f"{rid}는 {KIND_KO.get(k, k)} 기록입니다 — {KIND_KO.get(kind, kind)} 기록({kind}:…)이어야 합니다")
        p = os.path.join(self.dir(k), n)
        if not os.path.isfile(os.path.join(p, "record.json")):
            have = self.names(k)[-8:]
            raise RecordError(f"없는 기록 {rid}" + (f" (최근: {', '.join(f'{k}:{x}' for x in have)})" if have else ""))
        with open(os.path.join(p, "record.json"), encoding="utf-8") as f:
            meta = json.load(f)
        return Record(k, n, p, meta)

    def log(self) -> List[dict]:
        """log.jsonl의 줄(지운 기록은 뺀다) — 만든 순."""
        p = os.path.join(self.base, "log.jsonl")
        if not os.path.isfile(p):
            return []
        out = []
        with open(p, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                try:
                    k, n = self.split(d.get("id", ""))
                except RecordError:
                    continue
                if self.exists(k, n):
                    out.append(d)
        return out

    def records(self, kind: str = None) -> List[Record]:
        """기록 목록(만든 순)."""
        out = []
        for d in self.log():
            k, n = self.split(d["id"])
            if kind and k != kind:
                continue
            try:
                out.append(self.get(d["id"]))
            except RecordError:
                continue
        return out

    # ---- 고정·메모·정리 -------------------------------------------------
    def _marks_path(self):
        return os.path.join(self.base, "marks.json")

    def marks(self) -> Dict[str, dict]:
        """{기록: {pinned, memo}}."""
        p = self._marks_path()
        if not os.path.isfile(p):
            return {}
        with open(p, encoding="utf-8") as f:
            return json.load(f)

    def _save_marks(self, m):
        os.makedirs(self.base, exist_ok=True)
        tmp = self._marks_path() + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            f.write(dumps(m))
        os.replace(tmp, self._marks_path())

    def mark(self, rid: str, pinned: bool = None, memo: str = None) -> dict:
        """고정(pinned)·메모 — 기록 자체는 그대로, marks.json에만."""
        self.get(rid)
        m = self.marks()
        e = m.get(rid, {})
        if pinned is not None:
            e["pinned"] = bool(pinned)
        if memo is not None:
            e["memo"] = memo
        m[rid] = e
        self._save_marks(m)
        return e

    def remove(self, rid: str):
        """기록 폴더를 지운다(정리 — 사람이 고를 때만). log.jsonl의 줄은 남고 목록에서 빠진다."""
        k, n = self.split(rid)
        shutil.rmtree(os.path.join(self.dir(k), n))
        m = self.marks()
        if m.pop(rid, None) is not None:
            self._save_marks(m)
