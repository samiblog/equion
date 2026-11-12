#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""노트 (D37) — `notes/*.md`의 ```` ```equion ```` 블록이 명령이고, 그 바로 아래가 결과 구역이다.

    ```equion
    an unitroot core --trend ct
    ```

    <!-- equion:out an:unitroot_0001 · 2026-11-09T10:12:00 · d2026-11a {"records": [...], "h": "…"} -->
    (기록 카드의 표·차트를 펼친 md — 차트는 기록 폴더의 CSV를 노트에서 본 상대 경로로)
    <!-- /equion:out -->

블록 줄 = 명령줄 그대로(앞의 `equion`은 써도 되고 빼도 된다). 블록이 부를 수 있는 것은 등록부의 계산·보기 명령뿐이다(파일을 바꾸는 명령은
터미널에서). 실행은 명령이 있을 때만(`equion note run`), 다시 실행하면 새 기록이고, 손으로 고친 구역은 덮어쓰지 않고 차이를 보인다(`--force`).
Python 블록은 `--block n`으로 고를 때만 돈다(터미널에서). `equion note check`는 실행하지 않고 낡은 구역·없는 기록·손으로 고친 구역을 알린다.
"""

import contextlib
import difflib
import hashlib
import io
import json
import os
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass, field
from typing import List, Optional

from .. import registry as reg
from ..work.store import RecordError, now_iso
from ..work.lock import locked, project_lock
from .config import ProjectError
from .records import FORECAST_ONLY, NOT_INPUT, _who, data_spec, definition_hashes, history_of, store_of

OUT_OPEN = re.compile(r"^<!-- equion:out (.*?)(\{.*\}) -->\s*$")
OUT_CLOSE = "<!-- /equion:out -->"
FENCE = re.compile(r"^(`{3,})\s*([\w-]*)\s*$")


def _h(body: str) -> str:
    return hashlib.sha256(body.strip().encode("utf-8")).hexdigest()[:12]


def read_text(path: str) -> str:
    """md 파일을 UTF-8(BOM 무관)로 읽는다(파일은 닫는다)."""
    with open(path, encoding="utf-8-sig") as f:
        return f.read()


@dataclass
class Block:
    """노트의 실행 블록 하나 — 언어·줄·결과 구역."""

    n: int                     # 1부터(실행 블록만 센다)
    lang: str                  # equion · python
    start: int                 # 여는 줄 번호(0부터)
    end: int                   # 닫는 줄
    code: List[str]
    region: Optional[tuple] = None      # (여는 줄, 닫는 줄, meta, body)

    @property
    def commands(self) -> List[str]:
        """명령 줄(빈 줄·# 주석 뺌)."""
        return [c.strip() for c in self.code if c.strip() and not c.strip().startswith("#")]


def parse(text: str) -> List[Block]:
    """노트 글 → 실행 블록 목록(```equion · ```python)과 각 블록의 결과 구역."""
    lines = text.split("\n")
    blocks, i, n = [], 0, 0
    while i < len(lines):
        m = FENCE.match(lines[i])
        if not m:
            i += 1
            continue
        fence, lang = m[1], m[2].lower()
        j = i + 1
        while j < len(lines) and not lines[j].startswith(fence):
            j += 1
        if lang in ("equion", "python"):
            n += 1
            b = Block(n, lang, i, j, lines[i + 1:j])
            k = j + 1
            while k < len(lines) and not lines[k].strip():
                k += 1
            if k < len(lines):
                om = OUT_OPEN.match(lines[k])
                if om:
                    e = k + 1
                    while e < len(lines) and lines[e].strip() != OUT_CLOSE:
                        e += 1
                    try:
                        meta = json.loads(om[2])
                    except json.JSONDecodeError:
                        meta = {}
                    if isinstance(meta, dict) and "v" not in meta:      # 옛 구역 — 여는 줄의 '· 회차' 칸에서
                        head = [x.strip() for x in om[1].split(" · ")]
                        if len(head) >= 3 and head[2] not in ("", "-"):
                            meta["v"] = head[2]
                    b.region = (k, e, meta, "\n".join(lines[k + 1:e]))
            blocks.append(b)
        i = j + 1
    return blocks


def card_for_note(rec, note_dir: str) -> str:
    """기록 카드(summary.md) → 노트에 펼칠 md — 제목은 굵게, 절 제목도 굵게, 차트 자료는 노트에서 본 상대 경로로."""
    text = rec.summary_md()
    rel = os.path.relpath(rec.path, note_dir).replace(os.sep, "/")
    out = []
    for line in text.split("\n"):
        if line.startswith("# "):
            out.append(f"**{line[2:].strip()}**")
        elif line.startswith("## "):
            out.append(f"**{line[3:].strip()}**")
        else:
            out.append(re.sub(r'"url": "([^"/]+\.csv)"', lambda m: f'"url": "{rel}/{m[1]}"', line))
    return "\n".join(out).strip()


def stale_reasons(p, rec) -> List[str]:
    """기록이 낡았나 — 계산에 쓴 자료(회차·해시)나 정의 파일이 지금과 다르면 그 까닭."""
    out = []
    d0, d1 = rec.meta.get("data") or {}, data_spec(p)
    if d0.get("kind") == "vintage" and d1.get("kind") == "vintage" and d0.get("id") != d1.get("id"):
        out.append(f"자료 회차 {d0.get('id')} → 지금 {d1.get('id')}")
    elif d0.get("kind") == "file" and d0.get("sha256") != d1.get("sha256"):
        out.append("자료 파일이 바뀜")
    files = None
    if os.path.isfile(rec.file("assembly.json")):
        files = rec.read_json("assembly.json").get("files")
    elif (rec.meta.get("inputs") or {}).get("files"):
        files = rec.meta["inputs"]["files"]
    if files:
        now = definition_hashes(p)
        skip = NOT_INPUT if rec.kind == "sim" else NOT_INPUT + FORECAST_ONLY       # 가정·보정항·시나리오는 전망만 읽는다
        ch = sorted(k for k in set(files) | set(now) if files.get(k) != now.get(k) and not k.startswith(skip))
        if ch:
            out.append("정의 파일이 바뀜: " + ", ".join(ch[:4]) + (" …" if len(ch) > 4 else ""))
    return out


@dataclass
class BlockStatus:
    """블록 하나의 상태 — run(실행함) · skip · error · stale · edited · missing · never · ok."""

    n: int
    lang: str
    status: str
    records: List[str] = field(default_factory=list)
    detail: str = ""

    def to_dict(self) -> dict:
        """사전."""
        return {"block": self.n, "lang": self.lang, "status": self.status, "records": self.records, "detail": self.detail}


STATUS_KO = {"run": "실행", "skip": "건너뜀", "error": "오류", "stale": "낡음", "edited": "손으로 고침",
             "missing": "없는 기록", "never": "실행 안 함", "ok": "정상", "denied": "허용 안 됨"}


@dataclass
class NoteResult:
    """노트 실행·검사 결과 — 블록마다 상태(`.blocks`)·바뀜 기록(`.change`)."""

    note: str
    action: str
    blocks: List[BlockStatus]
    change: Optional[str] = None

    @property
    def ok(self) -> bool:
        """오류·허용 안 됨이 없으면 참."""
        return not any(b.status in ("error", "denied") for b in self.blocks)

    def text(self) -> str:
        """명령줄에 보이는 짧은 글."""
        L = [f"[note {self.action}] {self.note}: 블록 {len(self.blocks)}"]
        for b in self.blocks:
            L.append(f"  {b.n:>2} {b.lang:<6} {STATUS_KO[b.status]:<6} " + " · ".join(b.records)
                     + (f"  — {b.detail}" if b.detail else ""))
        if self.change:
            L.append(f"  바뀜 기록  {self.change}")
        return "\n".join(L)

    def to_dict(self) -> dict:
        """명령줄 --json과 같은 사전."""
        return {"note": self.note, "action": self.action, "ok": self.ok, "blocks": [b.to_dict() for b in self.blocks],
                "change": self.change}


def _note_file(p, note: str) -> str:
    """노트 경로 → 절대 경로. 있는 노트는 지금 폴더에서 먼저 찾고(프로젝트 안일 때 — 노트 폴더에서 `note check x.md`), 없으면 프로젝트
    폴더 기준(새 노트도 이쪽). 프로젝트 밖이면 ProjectError."""
    from .config import project_path
    from .project import resolve_path
    return project_path(p.root, resolve_path(p.root, note), "노트")


def _note_path(p, note: str) -> str:
    path = _note_file(p, note)
    if not os.path.isfile(path):
        raise ProjectError(f"노트가 없습니다: {note}")
    return path


def _defs_hash(p) -> str:
    """기록 없는 블록(ident·assemble·data list…)의 낡음을 볼 정의 파일 해시 하나 — 가정·보정항·시나리오(전망만 읽는다)는 뺀다."""
    now = definition_hashes(p)
    keep = {k: v for k, v in sorted(now.items()) if not k.startswith(FORECAST_ONLY)}
    return hashlib.sha256(json.dumps(keep, sort_keys=True).encode("utf-8")).hexdigest()[:12]


def _region_text(ids, body, vintage, defs: str = None) -> List[str]:
    meta = {"records": ids, "h": _h(body), "v": vintage or None}
    if defs and not ids:
        meta["d"] = defs
    return [f"<!-- equion:out {' '.join(ids) or '-'} · {now_iso()} · {vintage or '-'} {json.dumps(meta, ensure_ascii=False)} -->",
            body, OUT_CLOSE]


def _why(line: str) -> Optional[str]:
    """명령 한 줄이 허용 목록 밖이면 그 까닭."""
    try:
        toks = shlex.split(line)
    except ValueError as e:
        return f"명령 줄을 읽을 수 없습니다 — {e}"
    return reg.allowed(toks[1:] if toks and toks[0] == "equion" else toks)


def _run_command(p, line: str):
    """명령 한 줄을 같은 프로세스에서 → (종료 코드, 출력, 오류, 새 기록 id들). 허용 목록 밖이면 (None, 까닭)."""
    from ..cli import main as cli
    toks = shlex.split(line)
    if toks and toks[0] == "equion":
        toks = toks[1:]
    why = reg.allowed(toks)
    if why:
        return None, "", why, []
    store = store_of(p)
    before = {d["id"] for d in store.log()}
    out, err = io.StringIO(), io.StringIO()
    old = os.getcwd()
    os.chdir(p.root)                       # 프로젝트 폴더에서 — 기록의 '명령'이 블록의 줄 그대로 남게
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli(toks)
    finally:
        os.chdir(old)
    new = [d["id"] for d in store.log() if d["id"] not in before]
    return code, out.getvalue(), err.getvalue(), new


def _body_for(p, note_dir, results) -> str:
    parts = []
    for line, code, out, err, ids in results:
        if code is None:
            parts.append(f"**허용 안 됨** `{line}` — {err}")
            continue
        if code != 0:
            parts.append(f"**오류**(종료 코드 {code}) `{line}`\n\n```text\n{(err or out).strip()}\n```")
            continue
        if ids:
            store = store_of(p)
            for rid in ids:
                parts.append(card_for_note(store.get(rid), note_dir))
        else:
            parts.append(f"```text\n{out.strip()}\n```")
    return "\n\n".join(parts)


def run_note(p, note: str, block: int = None, stale: bool = False, force: bool = False, who: str = None,
             command: str = None) -> NoteResult:
    """노트의 블록을 실행해 결과 구역을 채운다(블록마다 새 기록). 손으로 고친 구역은 force일 때만 덮는다."""
    path = _note_path(p, note)
    rel = os.path.relpath(path, p.root).replace(os.sep, "/")
    note_dir = os.path.dirname(path)
    text = read_text(path)
    blocks = parse(text)
    if block is not None and not any(b.n == block for b in blocks):
        raise ProjectError(f"{rel}에 블록 {block}이 없습니다(실행 블록 {len(blocks)}개)")
    lines = text.split("\n")
    edits, stats = [], []
    for b in blocks:
        if block is not None and b.n != block:
            continue
        if b.region is not None:
            k, e, meta, body = b.region
            if meta.get("h") and _h(body) != meta["h"] and not force:
                stats.append(BlockStatus(b.n, b.lang, "edited", meta.get("records", []),
                                         "결과 구역을 손으로 고쳤습니다 — 덮으려면 --force"))
                continue
            if stale and not _stale_block(p, meta):
                stats.append(BlockStatus(b.n, b.lang, "skip", meta.get("records", []), "낡지 않음"))
                continue
        if b.lang == "python":
            if block is None:
                stats.append(BlockStatus(b.n, b.lang, "skip", [], f"Python 블록은 고를 때만 — equion note run {rel} --block {b.n}"))
                continue
            if os.environ.get("EQUION_NO_PYTHON"):
                stats.append(BlockStatus(b.n, b.lang, "denied", [],
                                         f"Python 블록은 여기서 돌리지 않습니다 — 터미널에서 equion note run {rel} --block {b.n}"))
                continue
            r = subprocess.run([sys.executable, "-c", "\n".join(b.code)], cwd=p.root, capture_output=True, text=True,
                               encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL,
                               env=dict(os.environ, PYTHONIOENCODING="utf-8"))
            body = f"```text\n{(r.stdout + (r.stderr if r.returncode else '')).strip()}\n```"
            edits.append((b, _region_text([], body, p.vintage)))
            stats.append(BlockStatus(b.n, b.lang, "run" if r.returncode == 0 else "error", [],
                                     "" if r.returncode == 0 else f"종료 코드 {r.returncode}"))
            continue
        denied = [(line, why) for line in b.commands for why in [_why(line)] if why]
        if denied:                              # 블록에 허용 안 된 줄이 하나라도 있으면 블록을 돌리지 않는다
            stats.append(BlockStatus(b.n, b.lang, "denied", [], f"{denied[0][0]!r}: {denied[0][1]}"))
            continue
        results, bad = [], ""
        for line in b.commands:
            code, out, err, ids = _run_command(p, line)
            results.append((line, code, out, err, ids))
            if code is None:
                bad = "denied"
            elif code != 0 and not bad:
                bad = "error"
        ids = [i for r in results for i in r[4]]
        body = _body_for(p, note_dir, results)
        edits.append((b, _region_text(ids, body, p.vintage, None if ids else _defs_hash(p))))
        stats.append(BlockStatus(b.n, b.lang, bad or "run", ids,
                                 "; ".join(r[3].strip().splitlines()[-1] for r in results if r[1] not in (0,) and r[3].strip())[:200]))
    new = _apply_regions(text, edits)
    change = None
    if new != text:
        # 블록을 도는 동안은 잠그지 않는다(블록의 명령이 잠금을 쓴다) — 다 돌린 뒤 잠금 안에서 지금 노트에 결과 구역을 넣는다.
        # 그사이 노트가 바뀌었으면(다른 흐름의 note run · 편집기) 지금 내용의 같은 블록(번호·명령이 같은 것)에 넣는다
        with project_lock(p.root):
            cur = read_text(path)
            if cur != text:
                now_blocks = parse(cur)
                moved = [(b2, region) for b, region in edits for b2 in now_blocks if b2.n == b.n and b2.code == b.code]
                new = _apply_regions(cur, moved)
                if len(moved) != len(edits):
                    raise ProjectError(f"{rel}의 블록이 실행하는 사이 바뀌었습니다(다른 명령·편집기) — 결과 구역은 쓰지 않았습니다. "
                                       f"기록은 남았습니다({', '.join(i for s in stats for i in s.records) or '없음'}) — 다시 실행하세요")
            ch = None
            if new != cur:
                ch = history_of(p).write_files({rel: new}, _who(who), command or f"note run {rel}",
                                               note=f"블록 {', '.join(str(s.n) for s in stats if s.status in ('run', 'error', 'denied'))}")
        change = ch.id if ch else None
    return NoteResult(rel, "run", stats, change)


def _apply_regions(text: str, edits) -> str:
    """[(블록, 결과 구역 줄)] → 결과 구역을 넣은(있으면 바꾼) 노트 글. 뒤의 블록부터(앞의 줄 번호가 밀리지 않게)."""
    lines = text.split("\n")
    for b, region in sorted(edits, key=lambda x: -x[0].start):
        if b.region is not None:
            k, e, _, _ = b.region
            lines[k:e + 1] = region
        else:
            lines[b.end + 1:b.end + 1] = [""] + region
    return "\n".join(lines)


def region_state(p, meta, store=None):
    """결과 구역이 지금과 맞나 — (상태, 까닭): ok · stale(낡음) · missing(지워진 기록). `note check`와 `note run --stale`이 같이 쓴다.

    기록이 있는 블록은 그 기록이 계산에 쓴 자료(회차)·정의 파일이 지금과 같은지(stale_reasons). 기록이 없는 블록(ident·assemble·
    data list 등 — 글만 남는다)은 실행 때의 자료 회차와 정의 파일 해시를 지금과 견준다(그것을 적지 않은 옛 구역은 회차만)."""
    store = store or store_of(p)
    ids = meta.get("records") or []
    if ids:
        missing = [r for r in ids if not _exists(store, r)]
        if missing:
            return "missing", "지워진 기록: " + ", ".join(missing)
        why = [w for r in ids for w in stale_reasons(p, store.get(r))]
        return ("stale", "; ".join(dict.fromkeys(why))) if why else ("ok", "")
    why = []
    v0, v1 = meta.get("v"), p.vintage
    if v0 is None and v1 is not None:
        why.append("실행 때의 자료 회차를 모름 — 다시 실행해 확인")
    elif v1 is not None and v0 != v1:
        why.append(f"자료 회차 {v0} → 지금 {v1}")
    if meta.get("d") and meta["d"] != _defs_hash(p):
        why.append("정의 파일이 바뀜")
    return ("stale", "; ".join(why)) if why else ("ok", "")


def _stale_block(p, meta) -> bool:
    return region_state(p, meta)[0] != "ok"


def check_note(p, note: str) -> NoteResult:
    """실행하지 않고 블록마다 — 실행 안 함 · 없는 기록 · 낡음(자료·정의가 바뀜) · 손으로 고침 · 정상."""
    path = _note_path(p, note)
    rel = os.path.relpath(path, p.root).replace(os.sep, "/")
    text = read_text(path)
    store = store_of(p)
    stats = []
    for b in parse(text):
        if b.lang == "equion":
            denied = [(line, why) for line in b.commands for why in [_why(line)] if why]
            if denied:
                stats.append(BlockStatus(b.n, b.lang, "denied", [], f"{denied[0][0]!r}: {denied[0][1]}"))
                continue
        if b.region is None:
            stats.append(BlockStatus(b.n, b.lang, "never"))
            continue
        k, e, meta, body = b.region
        ids = meta.get("records") or []
        if meta.get("h") and _h(body) != meta["h"]:
            stats.append(BlockStatus(b.n, b.lang, "edited", ids, "결과 구역을 손으로 고쳤습니다"))
            continue
        state, why = region_state(p, meta, store)
        stats.append(BlockStatus(b.n, b.lang, state, ids, why))
    return NoteResult(rel, "check", stats)


def _exists(store, rid) -> bool:
    try:
        store.get(rid)
        return True
    except RecordError:
        return False


@locked
def append_block(p, note: str, cmd: str, rid: str, who: str = None):
    """노트 끝에 명령 블록과 그 결과 구역을 더한다(`an … --note`). 노트가 없으면 만든다."""
    path = _note_file(p, note)
    rel = os.path.relpath(path, p.root).replace(os.sep, "/")
    toks = shlex.split(cmd)
    clean = []
    skip = False
    for t in toks:
        if skip:
            skip = False
            continue
        if t == "--note":
            skip = True
            continue
        if t.startswith("--note="):
            continue
        clean.append(t)
    line = shlex.join(clean)
    cur = read_text(path) if os.path.isfile(path) else f"# {os.path.splitext(os.path.basename(path))[0]}\n"
    body = card_for_note(store_of(p).get(rid), os.path.dirname(path))
    region = "\n".join(_region_text([rid], body, p.vintage))
    new = cur.rstrip("\n") + f"\n\n```equion\n{line}\n```\n\n{region}\n"
    history_of(p).write_files({rel: new}, _who(who), f"an … --note {rel}", note=f"블록 + {rid}")


@dataclass
class NoteAdded:
    """노트에 블록을 더한 결과 — `.file` · `.new`(노트를 새로 만들었나) · `.block`(더한 블록 번호) · `.lines` · `.change`."""

    file: str
    new: bool
    block: int
    lines: List[str] = field(default_factory=list)
    change: Optional[str] = None
    record: Optional[str] = None

    def text(self) -> str:
        """명령줄에 보이는 짧은 글."""
        head = f"[note add] {self.file}" + (" — 새 노트" if self.new else "") + f" · 블록 {self.block}"
        body = "".join(f"\n  {line}" for line in self.lines)
        tail = f"\n  결과 구역  {self.record}" if self.record else f"\n  다음   equion note run {self.file} --block {self.block}"
        return head + body + tail + (f"\n  바뀜 기록  {self.change}" if self.change else "")

    def to_dict(self) -> dict:
        """명령줄 --json과 같은 사전."""
        return {"file": self.file, "new": self.new, "block": self.block, "lines": self.lines, "record": self.record, "change": self.change}


def _clean_line(line: str) -> str:
    """명령 한 줄 → 노트 블록의 줄(앞의 equion과 --note 빼기). 허용 목록 밖이면 ProjectError."""
    try:
        toks = shlex.split(str(line).strip())
    except ValueError as e:
        raise ProjectError(f"명령 줄을 읽을 수 없습니다: {line!r} — {e}") from None
    if toks and toks[0] == "equion":
        toks = toks[1:]
    clean, skip = [], False
    for t in toks:
        if skip:
            skip = False
            continue
        if t == "--note":
            skip = True
            continue
        if t.startswith("--note="):
            continue
        clean.append(t)
    if not clean:
        raise ProjectError("빈 명령 줄")
    why = reg.allowed(clean)
    if why:
        raise ProjectError(f"노트 블록에 넣을 수 없는 명령 {shlex.join(clean)!r}: {why}")
    return shlex.join(clean)


@locked
def add_block(p, note: str, lines=None, record: str = None, title: str = None, who: str = None, command: str = None) -> NoteAdded:
    """노트 끝에 ```equion 블록 하나 — lines는 실행하지 않고 블록만, record는 그 명령과 결과 구역(카드)까지. 노트가 없으면 만든다."""
    if not lines and not record:
        raise ProjectError("더할 것이 없습니다 — 명령 줄(lines) 또는 기록(record)")
    path = _note_file(p, note)
    if not path.lower().endswith(".md"):
        raise ProjectError(f"노트는 .md 파일 — {note!r}")
    rel = os.path.relpath(path, p.root).replace(os.sep, "/")
    new = not os.path.isfile(path)
    clean = [_clean_line(x) for x in (lines or []) if str(x).strip()]
    region = []
    if record:
        try:
            rec = store_of(p).get(record)
        except RecordError as e:
            raise ProjectError(str(e)) from None
        cmd = rec.meta.get("command")
        if not cmd:
            raise ProjectError(f"{record}에는 명령이 적혀 있지 않습니다 — 노트에 담을 수 없습니다")
        clean.append(_clean_line(cmd))
        region = _region_text([record], card_for_note(rec, os.path.dirname(path)), (rec.meta.get("data") or {}).get("id") or p.vintage)
    head = " ".join(str(title or "").replace("`", "'").split())[:120] or os.path.splitext(os.path.basename(path))[0]
    cur = read_text(path) if not new else f"# {head}\n"
    text = cur.rstrip("\n") + "\n\n```equion\n" + "\n".join(clean) + "\n```\n" + ("\n" + "\n".join(region) + "\n" if region else "")
    n = len(parse(text))
    ch = history_of(p).write_files({rel: text}, _who(who), command or f"note add {rel}",
                                   note=f"블록 {n}" + (f" + {record}" if record else "") + (" 새 노트" if new else ""))
    return NoteAdded(rel, new, n, clean, ch.id if ch else None, record)


def region_diff(old: str, new: str, label: str = "구역") -> str:
    """두 구역 본문의 차이(unified diff)."""
    a = [x + "\n" for x in old.strip().split("\n")]
    b = [x + "\n" for x in new.strip().split("\n")]
    return "".join(difflib.unified_diff(a, b, f"{label}(전)", f"{label}(후)"))
