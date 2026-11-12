"""알림 줄(Feed)과 프로젝트 감시(ProjectWatcher) — 터미널에서 친 명령의 기록이 생기는 순간 화면에 뜨게 한다(기획안 §2.4-7).

화면은 긴 폴링 하나(`GET /api/events?since=N`)로 알림을 받는다. 알림의 종류:

- `record`  새 작업 기록(`work/log.jsonl`에 줄이 늘었다) — 누가·명령·핵심 수치 그대로
- `change`  새 바뀜 기록(`work/history/hNNNN/`) — 누가·어떻게·파일·늘고 준 줄 수
- `defs`    정의 파일(equion.toml·블록 파일·자료 정의·가정…)이 바뀌었다 — 화면은 부품 목록을 다시 읽는다(계산은 하지 않는다)
- `tree`    파일이 생기거나 없어졌다 — 파일 나무를 다시 읽는다
- `job`·`tabs`·`notice` 는 서버가 넣는다(작업 줄·프로젝트 탭·알릴 말)

감시는 두 겹이다. watchdog(운영체제의 변경 알림)이 깨우면 바로, 깨우지 않아도 `POLL` 초마다 **상태를 견줘서** 알림을 만든다 —
알림이 빠져도(네트워크 드라이브·보안 프로그램) 늦게라도 뜬다. 견주는 것은 로그 파일의 크기, 바뀜 기록의 번호, 정의 파일의 크기·시각뿐이라 싸다.
정의 파일은 크기·시각이 바뀐 것만 다시 읽어 **내용**을 견준다 — 동기화 프로그램·백신이 시각만 건드린 것으로는 알리지 않는다.
`defs`·`tree` 알림은 `QUIET` 초에 한 번까지만 낸다(잇달아 건드려도 화면이 쉴 새 없이 다시 읽지 않게 — 그 사이의 바뀜은 묶어서 한 번에).
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
import threading
import time
from typing import Any, Callable

from . import records

SHOW_KINDS = frozenset({"record", "proposal", "data", "part", "model", "file", "place"})
POLL = 2.0          # watchdog 이 깨우지 않아도 이만큼마다 견준다(초)
SETTLE = 0.25       # 깨운 뒤 잠깐 기다린다 — 명령 하나가 파일 여럿을 잇달아 쓴다
QUIET = 1.0         # defs·tree 알림 사이의 가장 짧은 틈(초) — 그 안의 바뀜은 묶어서 다음 알림에
MAX_EVENTS = 2000   # 들고 있는 알림 수
MAX_LINE = 256 * 1024

# 바뀜 기록을 남기는 정의 파일 — equion.work.history.PATTERNS 와 같아야 한다(시험 test_desk A가 지킨다).
# 앱 프로세스는 equion 을 불러오지 않는다(무겁다 — 계산은 작업 프로세스가 한다).
DEFINITIONS = ("equion.toml", "EQUATIONS/*.txt", "EQUATIONS/*.toml", "DATA/series.toml", "DATA/derived.txt",
               "ASSUMPTIONS/*.csv", "ASSUMPTIONS/*.toml", "ADDFACTORS/*.csv", "ADDFACTORS/*.toml",
               "SCENARIOS/*.toml", "VIEWS/*.toml", "notes/*.md", "reports/*.md", "FLOWS/*.eqs")
IGNORED_DIRS = frozenset({".git", "__pycache__", ".venv", "node_modules", ".ipynb_checkpoints"})
# 잠깐 생겼다 없어지는 남의 파일 — 오피스·LibreOffice 의 잠금 파일(~$x · .~lock.x#), 쓰는 중인 임시 파일. 정의 파일도 파일 나무의 바뀜도 아니다
TEMP_PREFIXES = ("~$", ".~")
TEMP_SUFFIXES = (".tmp", ".tmp-equion", ".part", ".crdownload")


def transient(name: str) -> bool:
    """잠깐 생겼다 없어지는 남의 파일인가(잠금·임시) — 알리지 않는다."""
    return name.startswith(TEMP_PREFIXES) or name.lower().endswith(TEMP_SUFFIXES)


class Feed:
    """알림 줄. `add` 로 넣고, 화면은 `read(받은 곳)` 으로 그 뒤의 것을 기다렸다 받는다."""

    def __init__(self) -> None:
        self._cond = threading.Condition()
        self._events: list[dict[str, Any]] = []
        self._seq = 0

    @property
    def seq(self) -> int:
        return self._seq

    def add(self, type_: str, /, **data: Any) -> int:
        with self._cond:
            self._seq += 1
            self._events.append({"seq": self._seq, "type": type_, **data})
            if len(self._events) > MAX_EVENTS:
                del self._events[: len(self._events) - MAX_EVENTS]
            self._cond.notify_all()
            return self._seq

    def read(self, since: int, timeout: float) -> dict[str, Any]:
        """`since` 뒤의 알림. 없으면 `timeout` 초까지 기다린다. `since` 가 이 줄의 것이 아니면(서버를 다시 띄움·너무 오래됨)
        `reset` 을 알린다 — 화면은 목록을 통째로 다시 읽는다."""
        deadline = time.monotonic() + timeout
        with self._cond:
            first = self._events[0]["seq"] if self._events else self._seq + 1
            if since > self._seq or since < first - 1:
                return {"seq": self._seq, "events": [], "reset": True}
            while self._seq <= since:
                left = deadline - time.monotonic()
                if left <= 0:
                    break
                self._cond.wait(left)
            return {"seq": self._seq, "events": [e for e in self._events if e["seq"] > since], "reset": False}


def definitions(root: str) -> dict[str, tuple[int, int]]:
    """정의 파일마다 (크기, 고친 시각 ns). 잠금·임시 파일(`~$x.txt`)은 뺀다."""
    out: dict[str, tuple[int, int]] = {}
    for pattern in DEFINITIONS:
        for path in glob.glob(os.path.join(root, pattern)):
            if transient(os.path.basename(path)):
                continue
            try:
                st = os.stat(path)
            except OSError:
                continue
            if os.path.isfile(path):
                out[os.path.relpath(path, root).replace(os.sep, "/")] = (st.st_size, st.st_mtime_ns)
    return out


class DefinitionState:
    """정의 파일마다 **내용의 지문** — (크기, 시각)이 바뀐 파일만 다시 읽어 해시한다(바뀌지 않은 것은 지난 지문 그대로라 싸다).
    시각만 바뀐 파일(동기화 프로그램·백신·`touch`)은 바뀌지 않은 것으로 본다. `scan()` → {경로: 지문}.

    예
        >>> state = DefinitionState(folder)          # doctest: +SKIP
        >>> state.scan() == state.scan()             # doctest: +SKIP
        True
    """

    def __init__(self, root: str) -> None:
        self.root = root
        self._stat: dict[str, tuple[int, int]] = {}
        self._hash: dict[str, str] = {}

    def scan(self) -> dict[str, str]:
        stat = definitions(self.root)
        if stat != self._stat:
            for rel, st in stat.items():
                if self._stat.get(rel) != st or rel not in self._hash:
                    self._hash[rel] = self._digest(rel) or f"stat:{st[0]}:{st[1]}"      # 읽지 못하면(잠김) 크기·시각으로 — 다음에 다시 본다
            for rel in set(self._hash) - set(stat):
                del self._hash[rel]
            self._stat = stat
        return dict(self._hash)

    def _digest(self, rel: str) -> str | None:
        try:
            with open(os.path.join(self.root, *rel.split("/")), "rb") as f:
                return hashlib.sha256(f.read()).hexdigest()
        except OSError:
            return None


def diff_counts(text: str) -> tuple[int, int]:
    """통합 차이(diff.txt)에서 늘어난 줄·줄어든 줄 수."""
    plus = minus = 0
    for line in text.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            plus += 1
        elif line.startswith("-") and not line.startswith("---"):
            minus += 1
    return plus, minus


def read_change(root: str, cid: str, with_diff: bool = False) -> dict[str, Any] | None:
    """바뀜 기록 하나(`work/history/<번호>/change.json` + 차이의 줄 수). 없거나 쓰는 중이면 None."""
    base = os.path.join(root, "work", "history", cid)
    try:
        with open(os.path.join(base, "change.json"), encoding="utf-8") as f:
            meta = json.load(f)
        with open(os.path.join(base, "diff.txt"), encoding="utf-8", errors="replace") as f:
            diff = f.read(MAX_LINE * 4)
    except (OSError, ValueError):
        return None
    if not isinstance(meta, dict):
        return None
    plus, minus = diff_counts(diff)
    files = meta.get("files") if isinstance(meta.get("files"), dict) else {}
    out = {"id": cid, "created": meta.get("created"), "who": meta.get("who"), "how": meta.get("how"), "note": meta.get("note") or "",
           "files": [{"path": p, "op": (v or {}).get("op")} for p, v in files.items()], "plus": plus, "minus": minus,
           "reverts": meta.get("reverts"), "run": meta.get("run")}
    if with_diff:
        out["diff"] = diff
    return out


def history_ids(root: str) -> list[str]:
    base = os.path.join(root, "work", "history")
    try:
        names = os.listdir(base)
    except OSError:
        return []
    return sorted(n for n in names if n[:1] == "h" and n[1:].isdigit() and os.path.isfile(os.path.join(base, n, "change.json")))


class ProjectWatcher:
    """프로젝트 폴더 하나를 지켜보다 알림 줄에 넣는다. `on_defs` 는 정의 파일이 바뀌었을 때 부른다(바깥 고침을 바뀜 기록에 적게)."""

    def __init__(self, root: str, pid: str, feed: Feed, on_defs: Callable[[], None] | None = None) -> None:
        self.root, self.pid, self.feed, self.on_defs = root, pid, feed, on_defs
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._tree_dirty = False
        self._log = os.path.join(root, "work", "log.jsonl")
        self._offset = self._log_size()
        self._known = set(history_ids(root))
        self._def_state = DefinitionState(root)
        self._defs = self._def_state.scan()
        self._last_burst = 0.0           # 마지막 defs·tree 알림을 낸 때(monotonic)
        self._held = False               # QUIET 안이라 미뤄 둔 견주기가 있다
        self._props = self._proposal_state()
        self._requests = os.path.join(root, *records.REQUESTS)
        self._req_offset = self._size(self._requests)
        self._observer: Any = None
        self._start_observer()
        self._thread = threading.Thread(target=self._loop, name=f"desk-watch-{pid}", daemon=True)
        self._thread.start()

    @property
    def native(self) -> bool:
        """운영체제의 변경 알림을 쓰고 있는지(아니면 견주기만 한다)."""
        return self._observer is not None

    def _log_size(self) -> int:
        return self._size(self._log)

    @staticmethod
    def _size(path: str) -> int:
        try:
            return os.path.getsize(path)
        except OSError:
            return 0

    def _proposal_state(self) -> dict[str, str]:
        """제안마다의 상태(open·applied·dropped) — 새 제안과 상태가 바뀐 것을 가린다."""
        out = {}
        for name in records.proposal_names(self.root):
            found = records.read_proposal(self.root, name)
            if found:
                out[name] = found["status"]
        return out

    def _start_observer(self) -> None:
        try:
            from watchdog.events import FileSystemEventHandler
            from watchdog.observers import Observer
        except ImportError:
            return
        watcher = self

        class Handler(FileSystemEventHandler):
            def on_any_event(self, event: Any) -> None:
                parts = os.path.relpath(os.fsdecode(event.src_path), watcher.root).split(os.sep)
                if IGNORED_DIRS.intersection(parts) or transient(parts[-1]):
                    return
                if event.event_type in ("created", "deleted", "moved"):
                    watcher._tree_dirty = True
                watcher._wake.set()

        try:
            observer = Observer()
            observer.schedule(Handler(), self.root, recursive=True)
            observer.daemon = True
            observer.start()
            self._observer = observer
        except Exception:      # 지켜보지 못하는 폴더(네트워크 드라이브 등) — 견주기만 한다
            self._observer = None

    def _loop(self) -> None:
        while not self._stop.is_set():
            wait = max(0.05, self._last_burst + QUIET - time.monotonic()) if self._held else POLL
            woke = self._wake.wait(min(wait, POLL))
            if self._stop.is_set():
                return
            if woke:
                time.sleep(SETTLE)
                self._wake.clear()
            try:
                self.check()
            except Exception:  # 감시가 죽으면 화면이 조용히 낡는다 — 다음 번에 다시 본다
                pass

    def poke(self) -> None:
        """지금 바로 견주게 깨운다(시험과, 앱이 방금 계산을 끝냈을 때)."""
        self._wake.set()

    def check(self) -> None:
        """지금 상태를 지난번과 견줘 알림을 만든다."""
        self._check_log()
        self._check_history()
        self._check_proposals()
        self._check_requests()
        # 정의·나무 알림은 QUIET 초에 한 번까지 — 그 안의 바뀜은 미뤄 두었다가 묶어서
        now = time.monotonic()
        if now - self._last_burst < QUIET:
            self._held = True
            return
        self._held = False
        sent = self._check_definitions()
        if self._tree_dirty:
            self._tree_dirty = False
            self.feed.add("tree", p=self.pid)
            sent = True
        if sent:
            self._last_burst = now

    def _check_log(self) -> None:
        size = self._log_size()
        if size < self._offset:          # 로그를 지우고 새로 씀
            self._offset = 0
        if size == self._offset:
            return
        try:
            with open(self._log, "rb") as f:
                f.seek(self._offset)
                chunk = f.read(size - self._offset)
        except OSError:
            return
        end = chunk.rfind(b"\n")
        if end < 0:
            return                       # 줄을 쓰는 중 — 다음에
        self._offset += end + 1
        for raw in chunk[:end].split(b"\n"):
            raw = raw.strip()
            if not raw or len(raw) > MAX_LINE:
                continue
            try:
                line = json.loads(raw.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                continue
            if isinstance(line, dict) and isinstance(line.get("id"), str):
                self.feed.add("record", p=self.pid, record=line)

    def _check_proposals(self) -> None:
        now = self._proposal_state()
        if now == self._props:
            return
        old, self._props = self._props, now
        for name, status in now.items():
            if old.get(name) != status:
                found = records.read_proposal(self.root, name)
                if found:
                    self.feed.add("proposal", p=self.pid, proposal=found, new=name not in old)
        if set(old) - set(now):          # 제안 폴더를 지웠다 — 목록을 다시 읽게
            self.feed.add("proposal", p=self.pid, proposal=None, new=False)

    def _check_requests(self) -> None:
        """`equion desk show <이름>` 이 덧붙인 줄 — 그 화면을 열어 달라는 요청(화면 이동만)."""
        size = self._size(self._requests)
        if size < self._req_offset:      # 커져서 지난 줄을 버리고 새로 썼다
            self._req_offset = 0
        if size == self._req_offset:
            return
        try:
            with open(self._requests, "rb") as f:
                f.seek(self._req_offset)
                chunk = f.read(size - self._req_offset)
        except OSError:
            return
        end = chunk.rfind(b"\n")
        if end < 0:
            return
        self._req_offset += end + 1
        for raw in chunk[:end].split(b"\n")[-8:]:       # 밀린 요청이 많아도 마지막 몇 개만 연다
            try:
                line = json.loads(raw.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                continue
            show = line.get("show") if isinstance(line, dict) else None
            if isinstance(show, str) and 0 < len(show) <= 300 and line.get("kind") in SHOW_KINDS:
                self.feed.add("show", p=self.pid, show=show, kind=line["kind"], who=str(line.get("who") or "")[:40])

    def _check_history(self) -> None:
        ids = history_ids(self.root)
        for cid in ids:
            if cid in self._known:
                continue
            change = read_change(self.root, cid)
            if change is None:
                continue                 # 쓰는 중 — 다음에
            self._known.add(cid)
            self.feed.add("change", p=self.pid, change=change)

    def _check_definitions(self) -> bool:
        """정의 파일의 내용이 바뀌었으면 `defs` 를 알린다(시각만 바뀐 것은 아니다). 알렸으면 True."""
        now = self._def_state.scan()
        if now == self._defs:
            return False
        changed = sorted(k for k in set(now) | set(self._defs) if now.get(k) != self._defs.get(k))
        self._defs = now
        self.feed.add("defs", p=self.pid, files=changed)
        if self.on_defs:
            self.on_defs()
        return True

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        observer, self._observer = self._observer, None
        if observer is not None:
            try:
                observer.stop()
                observer.join(2)
            except Exception:
                pass
