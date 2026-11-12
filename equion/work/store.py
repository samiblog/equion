#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""작업 기록 저장소 (D33) — 계산할 때마다 `work/<종류>/<이름>/`에 기록 하나, `work/log.jsonl`에 한 줄.

    work/
      log.jsonl                 한 줄에 기록 하나: id · 시각 · 누가 · 명령 그대로 · 종류 · 대상 · 핵심 수치 · 경로
      marks.json                고정·메모(기록 자체는 고치지 않는다)
      est/<이름>/               record.json · coefs.csv · series.csv · summary.md
      hs/<이름>/                record.json · assembly.json(조립 명세) · stats.csv · solved.csv · status.csv · summary.md
      sim/<이름>/               record.json · assembly.json · levels.csv · growth.csv · diff.csv · summary.md
      an/<이름>/                record.json · 표 CSV · summary.md
      run/<이름>/               스크립트 실행(.eqs) — record.json(단계) · script.eqs(값을 바꿔 넣은 뒤) · src/ · defs/ · steps/ · summary.md

기록 이름은 `종류:이름`(`est:cons_c5` · `hs:hs_0003`). 기록은 고치지 않는다 — 다시 계산하면 새 기록이다. 쓰기는 임시 폴더에 다 쓴 뒤
한 번에 옮긴다(반쯤 쓴 기록이 남지 않게).

이름 정하기·기록 옮기기·log.jsonl에 줄 더하기는 프로젝트 잠금(lock.py) 안에서 한다 — 같은 명령을 여러 개 한꺼번에 돌려도
이름이 겹치지 않는다. 기록 폴더가 보이는 것과 log.jsonl의 줄은 함께다(log.jsonl을 열 수 없으면 기록도 옮기지 않는다).
"""

import json
import os
import re
import shutil
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Dict, List

import pandas as pd

from .lock import as_busy, locked, project_lock, tmp_dir

FORMAT = "equion-record"
FORMAT_VERSION = 1
WORK_DIR = "work"
KINDS = ("est", "hs", "sim", "an", "run")
KIND_KO = {"est": "추정", "hs": "과거 재현", "sim": "전망", "an": "분석", "run": "스크립트 실행", "data": "자료 회차"}
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_\-]*$")     # 기록 이름(sim:2026-11_base처럼 숫자로 시작해도 된다)
WHO_KO = {"terminal": "터미널", "claude": "Claude", "desk": "Desk", "python": "Python", "script": "스크립트"}


def move_into_place(tmp: str, final: str) -> None:
    """임시 폴더(또는 파일)를 제자리로 옮긴다 — 기록이 반쯤 쓰인 채 보이지 않게 하는 마지막 걸음.

    Windows에서는 방금 쓴 파일을 다른 프로그램(백신·색인·폴더 감시)이 잠깐 쥐고 있으면 옮기기가 거절된다(PermissionError).
    잠깐씩 기다리며 몇 번 다시 하고, 끝내 안 되면 그 오류를 그대로 낸다.
    """
    for wait in (0.02, 0.05, 0.1, 0.2, 0.4, 0.8, None):
        try:
            os.replace(tmp, final)
            return
        except PermissionError:
            if wait is None:
                raise
            time.sleep(wait)


class RecordError(ValueError):
    """기록 이름·찾기 문제(없는 기록·이미 있는 이름 등)."""


class AutoName(str):
    """저절로 정한 기록 이름(`next_name` 등) — 쓰기 전에 다른 명령이 그 이름을 먼저 쓰면 `WorkStore.write`가 `again()`으로 다음 이름을
    받아 기록의 이름(`id`·`path`·카드)을 바꿔 쓴다. 사람이 준 이름(`--as`)은 보통 글자(str)라 겹치면 그대로 RecordError."""

    def __new__(cls, value: str, again: Callable[[], str] = None):
        s = super().__new__(cls, value)
        s.again = again
        return s


def _renamed(kind: str, old: str, new: str, meta: dict, summary: str):
    """기록 이름을 old → new로 — meta의 글자 값과 카드에서 `종류:old`·`work/종류/old`만(앞뒤가 이름 글자면 건드리지 않는다)."""
    rx = re.compile(rf"(?<![A-Za-z0-9_\-])({re.escape(kind)}:|work/{re.escape(kind)}/){re.escape(old)}(?![A-Za-z0-9_\-])")

    def sub(v):
        if isinstance(v, str):
            return rx.sub(lambda m: m[1] + new, v)
        if isinstance(v, dict):
            return {k: sub(x) for k, x in v.items()}
        if isinstance(v, list):
            return [sub(x) for x in v]
        return v
    return sub(meta), sub(summary)


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

    def used_names(self, kind: str) -> set:
        """그 종류에서 한 번이라도 쓴 기록 이름 — 지금 있는 것과 log.jsonl에 남은 것(정리로 지운 기록도). 번호를 다시 쓰지 않게."""
        out = set(self.names(kind))
        p = os.path.join(self.base, "log.jsonl")
        if os.path.isfile(p):
            try:
                with open(p, encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()
            except OSError as e:
                raise as_busy(e, "work/log.jsonl", reading=True) from None
            for line in lines:
                try:
                    rid = json.loads(line).get("id", "")
                except (json.JSONDecodeError, AttributeError):
                    continue
                k, sep, n = str(rid).partition(":")
                if sep and k == kind:
                    out.add(n)
        return out

    def next_name(self, kind: str, prefix: str) -> str:
        """prefix_0001, prefix_0002 … — 같은 앞글자의 가장 큰 번호 다음. 정리(work clean)로 지운 기록의 번호도 다시 쓰지 않는다 —
        보고서·노트·바뀜 기록에 남은 이름이 다른 계산을 가리키지 않게. 돌려주는 이름은 AutoName(쓰기 전에 다른 명령이 먼저 쓰면
        write가 다음 번호로 바꾼다)."""
        rx = re.compile(rf"^{re.escape(prefix)}_(\d+)$")
        nums = [int(m[1]) for n in self.used_names(kind) for m in [rx.match(n)] if m]
        return AutoName(f"{prefix}_{(max(nums) if nums else 0) + 1:04d}", again=lambda: self.next_name(kind, prefix))

    @contextmanager
    def naming(self, kind: str, as_name: str = None, prefix: str = None):
        """새 기록 이름을 잡은 채로 — `with store.naming("est", as_name, "cn") as name: … store.write("est", name, …)`.

        프로젝트 잠금을 쥔 채 이름을 정하고(as_name, 없으면 prefix의 다음 번호) 검사한다. 블록 안에서 그 이름으로 기록을 쓴다
        — 같은 명령을 여러 개 한꺼번에 돌려도 이름이 겹치지 않는다. 계산은 블록 밖에서(잠금을 오래 쥐지 않게)."""
        with project_lock(self.root):
            name = as_name or self.next_name(kind, prefix)
            self.check_new(kind, name)
            yield name

    def check_new(self, kind: str, name: str):
        """새 기록 이름을 검사한다 — 글자가 틀리거나 이미 있으면 RecordError(기록은 고치지 않는다)."""
        if not NAME_RE.match(name or ""):
            raise RecordError(f"기록 이름은 영문·숫자로 시작하고 영문·숫자·_·-만: {name!r}")
        if self.exists(kind, name):
            raise RecordError(f"이미 있는 기록 {kind}:{name} — 기록은 고치지 않습니다(다른 이름으로 --as)")

    def _another(self, kind: str, name: "AutoName") -> str:
        """저절로 정한 이름이 먼저 쓰였다 — 다음 이름(again()이 준 것, 그것도 쓰였으면 끝 번호를 하나씩 올림)."""
        used = self.used_names(kind)

        def free(c):
            return c not in used and not os.path.lexists(os.path.join(self.dir(kind), c))
        cand = str(name.again()) if name.again is not None else str(name)
        if cand != str(name) and free(cand):
            return cand
        for _ in range(100000):
            m = re.match(r"^(.*)_(\d+)$", cand)
            cand = f"{m[1]}_{int(m[2]) + 1:0{len(m[2])}d}" if m else f"{cand}_2"
            if free(cand):
                return cand
        raise RecordError(f"새 기록 이름을 정하지 못했습니다({kind}:{name}…)")

    @staticmethod
    def _fill(tmp: str, out: Dict[str, object]):
        for fn, v in out.items():
            parts = fn.replace("\\", "/").split("/")
            if os.path.isabs(fn) or ".." in parts:
                raise RecordError(f"기록 안의 파일 이름이 기록 폴더 밖을 가리킵니다: {fn!r}")
            p = os.path.join(tmp, fn)
            if "/" in fn:                              # 하위 폴더(실행 기록의 defs/·src/·steps/)
                os.makedirs(os.path.dirname(p), exist_ok=True)
            if isinstance(v, bytes):
                with open(p, "wb") as f:
                    f.write(v)
                continue
            if isinstance(v, pd.DataFrame):
                v.to_csv(p, lineterminator="\n")
                continue
            text = dumps(v) if isinstance(v, (dict, list)) else str(v)
            with open(p, "w", encoding="utf-8", newline="\n") as f:
                f.write(text)

    # ---- 쓰기 ----------------------------------------------------------
    def write(self, kind: str, name: str, meta: dict, files: Dict[str, object], summary: str,
              log: dict = None) -> Record:
        """기록 하나를 쓴다 — files의 값은 글자·DataFrame(CSV)·dict(JSON). record.json·summary.md를 더하고 log.jsonl에 한 줄.

        임시 폴더(프로세스마다 다른 이름)에 다 쓴 뒤, 프로젝트 잠금 안에서 이름을 다시 확인하고 log.jsonl을 연 다음 기록을 옮기고
        줄을 더한다 — log.jsonl을 다른 프로그램이 쥐고 있으면 기록도 옮기지 않는다(FileBusy). 저절로 정한 이름(AutoName)을
        그사이 다른 명령이 먼저 썼으면 다음 이름으로 바꿔 쓴다. 사람이 준 이름이 이미 있으면 RecordError."""
        if not isinstance(name, AutoName):
            self.check_new(kind, name)
        elif not NAME_RE.match(name or ""):
            raise RecordError(f"기록 이름은 영문·숫자로 시작하고 영문·숫자·_·-만: {name!r}")
        d = self.dir(kind)
        meta = dict(meta)
        meta.setdefault("format", FORMAT)
        meta.setdefault("format_version", FORMAT_VERSION)
        meta["id"] = f"{kind}:{name}"
        meta["kind"] = kind
        meta.setdefault("created", now_iso())
        run = os.environ.get("EQUION_RUN")            # 스크립트 실행(run:…) 안에서 만든 기록이면 그 실행
        if run and kind != "run":
            meta.setdefault("run", run)
        try:
            os.makedirs(d, exist_ok=True)
        except OSError as e:
            raise as_busy(e, os.path.relpath(d, self.root).replace(os.sep, "/")) from None
        tmp = tmp_dir(d, name)
        try:
            try:
                os.makedirs(tmp)
                self._fill(tmp, dict(files))
            except OSError as e:
                raise as_busy(e, os.path.relpath(tmp, self.root).replace(os.sep, "/")) from None
            with project_lock(self.root):
                if isinstance(name, AutoName) and (self.exists(kind, name) or os.path.lexists(os.path.join(d, name))):
                    new = self._another(kind, name)
                    meta, summary = _renamed(kind, str(name), new, meta, summary)
                    name = new
                self.check_new(kind, name)
                final = os.path.join(d, name)
                rel = os.path.relpath(final, self.root).replace(os.sep, "/")
                if meta.get("path") and str(meta["path"]).replace(os.sep, "/").rstrip("/").startswith(f"work/{kind}/"):
                    meta["path"] = rel
                self._fill(tmp, {"record.json": meta, "summary.md": summary})
                line = {"id": meta["id"], "created": meta["created"], "who": meta.get("who"), "command": meta.get("command"),
                        "kind": kind, "target": meta.get("target"), "path": rel}
                if meta.get("run"):
                    line["run"] = meta["run"]
                line.update(log or {})
                text = json.dumps(_jsonable(line), ensure_ascii=False) + "\n"
                try:
                    os.makedirs(self.base, exist_ok=True)
                    lf = open(os.path.join(self.base, "log.jsonl"), "a", encoding="utf-8", newline="\n")
                except OSError as e:
                    raise as_busy(e, "work/log.jsonl") from None
                with lf:
                    try:
                        move_into_place(tmp, final)
                    except OSError as e:
                        raise as_busy(e, rel) from None
                    try:
                        lf.write(text)
                        lf.flush()
                    except OSError as e:               # 줄을 더하지 못했으면 기록도 거둔다(목록에 없는 기록이 남지 않게)
                        shutil.rmtree(final, ignore_errors=True)
                        raise as_busy(e, "work/log.jsonl") from None
        except BaseException:
            shutil.rmtree(tmp, ignore_errors=True)
            raise
        return Record(kind, str(name), final, meta)

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
        try:
            with open(p, encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except OSError as e:
            raise as_busy(e, "work/log.jsonl", reading=True) from None
        for line in lines:
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
        from .lock import write_bytes
        os.makedirs(self.base, exist_ok=True)
        write_bytes(self._marks_path(), dumps(m).encode("utf-8"), root=self.root)

    @locked
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

    @locked
    def remove(self, rid: str):
        """기록 폴더를 지운다(정리 — 사람이 고를 때만). log.jsonl의 줄은 남고 목록에서 빠진다."""
        k, n = self.split(rid)
        shutil.rmtree(os.path.join(self.dir(k), n))
        m = self.marks()
        if m.pop(rid, None) is not None:
            self._save_marks(m)
