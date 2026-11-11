"""프로젝트 탭 — 연 프로젝트마다 작업 프로세스 하나·감시 하나, 그리고 그 폴더의 파일 읽기.

앱 프로세스는 `equion` 을 불러오지 않는다. 계산과 정의 읽기는 작업 프로세스(`worker.py`)에 시키고, 기록·카드·파일은 그대로 읽는다.
화면이 주는 경로는 프로젝트 폴더 안으로 푼 뒤에만 읽는다(`resolve`) — 폴더 밖(`..`·절대 경로·밖을 가리키는 링크)은 거절한다.
"""
from __future__ import annotations

import hashlib
import os
import secrets
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable

from . import records, terminal
from .config import MAX_TABS, Config
from .i18n import t
from .watch import IGNORED_DIRS, Feed, ProjectWatcher, history_ids, read_change
from .worker import Worker, WorkerError

TEXT_LIMIT = 2 * 1024 * 1024       # 화면에 보이는 글 파일의 크기
DIR_LIMIT = 2000                   # 폴더 하나에서 보이는 항목 수
IMAGE_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp"}
IMAGE_LIMIT = 16 * 1024 * 1024
SCAN_DELAY = 0.6                   # 정의 파일이 바뀐 뒤 바깥 고침을 적기까지 — 명령이 스스로 적을 틈을 준다
SCAN_RETRY = (0.5, 1.5, 4.0, None)  # 적지 못했을 때 다시 해 보기까지(초) — 마지막은 그만둔다


class TooManyTabs(Exception):
    pass


class NotAProject(Exception):
    pass


class Outside(Exception):
    """프로젝트 폴더 밖의 경로."""


def project_id(root: str) -> str:
    return hashlib.sha1(os.path.normcase(os.path.abspath(root)).encode("utf-8")).hexdigest()[:10]


class ProjectSession:
    """연 프로젝트 하나."""

    def __init__(self, root: str, feed: Feed) -> None:
        self.root = str(Path(root).resolve())
        self.id = project_id(self.root)
        self.name = os.path.basename(self.root) or self.root
        self.feed = feed
        self.worker = Worker(self.root)
        self.watcher = ProjectWatcher(self.root, self.id, feed, on_defs=self.scan_soon)
        self.started = False                 # 화면이 한 번이라도 개요를 받아 갔는지 — 그 전에는 작업 프로세스를 띄우지 않는다
        self._jobs = 0
        self._scan_lock = threading.Lock()
        self._scan_pending = False
        self._closed = False

    def close(self) -> None:
        self._closed = True
        self.watcher.stop()
        self.worker.stop()

    # ---- 계산(작업 프로세스) --------------------------------------------------------------------

    def run(self, op: str, label: str, **args: Any) -> dict[str, Any]:
        """작업 프로세스에 계산을 시킨다. 시작과 끝을 알림 줄에 넣어 작업 줄에 보이게 한다(기획안 §2.4-2)."""
        self._jobs += 1
        job = f"{self.id}-{self._jobs}"
        self.feed.add("job", p=self.id, job=job, state="start", op=op, label=label, who="desk")
        began = time.monotonic()
        try:
            out = self.worker.call(op, **args)
        except WorkerError as exc:
            self.feed.add("job", p=self.id, job=job, state="cancelled" if exc.kind == "cancelled" else "error", op=op, label=label,
                          error=str(exc), kind=exc.kind, seconds=time.monotonic() - began)
            raise
        result = out.get("result")
        rid = (result.get("record") or result.get("id")) if isinstance(result, dict) else None
        self.feed.add("job", p=self.id, job=job, state="done", op=op, label=label, seconds=time.monotonic() - began,
                      record=rid if records.split_id(rid) else None)        # 기록 이름 모양일 때만(화면이 그것으로 카드를 연다)
        self.watcher.poke()
        return out

    def overview(self) -> dict[str, Any]:
        out = self.worker.call("overview")
        if isinstance(out.get("result"), dict) and out["result"].get("project"):
            self.name = str(out["result"]["project"])
        first, self.started = not self.started, True
        if first:
            self.scan_soon(offline=True)     # 앱이 꺼져 있는 동안 바뀐 정의 파일(K7)
        return out

    def scan_soon(self, offline: bool = False) -> None:
        """조금 뒤에 바깥 고침을 바뀜 기록에 적게 한다(여러 번 불러도 한 번). 작업 프로세스가 아직 뜨지 않은 탭은 건너뛴다."""
        if not self.started or self._closed:
            return
        with self._scan_lock:
            if self._scan_pending:
                return
            self._scan_pending = True

        def work() -> None:
            time.sleep(SCAN_DELAY)
            with self._scan_lock:
                self._scan_pending = False
            if self._closed:
                return
            found = None
            for wait in SCAN_RETRY:
                try:
                    found = self.worker.call("scan").get("result")
                    break
                except WorkerError as exc:
                    # 방금 쓴 파일을 다른 프로그램(백신·색인)이 잠깐 쥐고 있으면 기록 폴더를 옮기지 못한다 — 조금 뒤에 다시
                    if self._closed or exc.kind == "cancelled":
                        return
                    print(f"equion-desk: scan: {exc.kind}: {exc}", file=sys.stderr, flush=True)
                    if wait is None:
                        return
                    time.sleep(wait)
            if found and offline:
                self.feed.add("offline", p=self.id, change=found.get("id"), files=found.get("files") or [])
            self.watcher.poke()

        threading.Thread(target=work, name=f"desk-scan-{self.id}", daemon=True).start()

    # ---- 파일 읽기 ------------------------------------------------------------------------------

    def resolve(self, rel: Any) -> Path:
        """프로젝트 기준 경로 → 실제 경로. 폴더 밖이면 `Outside`."""
        if not isinstance(rel, str) or "\0" in rel or len(rel) > 1024:
            raise Outside(rel)
        rel = rel.replace("\\", "/").strip("/")
        root = Path(self.root)
        if rel in ("", "."):
            return root
        if ":" in rel or rel.startswith("/") or any(part in ("..", "") for part in rel.split("/")):
            raise Outside(rel)
        path = (root / rel).resolve()
        if path != root and root not in path.parents:
            raise Outside(rel)
        return path

    def listdir(self, rel: str) -> list[dict[str, Any]]:
        """폴더 하나의 항목 — 폴더 먼저, 이름순. `.git`·`__pycache__` 같은 것은 뺀다."""
        base = self.resolve(rel)
        out = []
        with os.scandir(base) as it:
            for entry in it:
                if entry.name in IGNORED_DIRS or entry.name.endswith((".tmp", ".tmp-equion")):
                    continue
                try:
                    is_dir = entry.is_dir()
                    size = 0 if is_dir else entry.stat().st_size
                except OSError:
                    continue
                out.append({"name": entry.name, "dir": is_dir, "size": size})
        out.sort(key=lambda e: (not e["dir"], e["name"].casefold()))
        return out[:DIR_LIMIT]

    def read_file(self, rel: str) -> dict[str, Any]:
        """글 파일 하나. 그림은 `kind: image`(내용은 `/raw` 로), 글이 아니면 `kind: binary`. 큰 글은 앞부분만(`truncated`)."""
        path = self.resolve(rel)
        st = path.stat()
        info: dict[str, Any] = {"path": rel.replace("\\", "/").strip("/"), "name": path.name, "size": st.st_size, "mtime": st.st_mtime}
        if path.suffix.lower() in IMAGE_TYPES:
            return {**info, "kind": "image"}
        with open(path, "rb") as f:
            data = f.read(TEXT_LIMIT + 1)
        if b"\0" in data[:8192]:
            return {**info, "kind": "binary"}
        truncated = len(data) > TEXT_LIMIT
        data = data[:TEXT_LIMIT]
        for encoding in ("utf-8-sig", "cp949"):
            try:
                text = data.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            text, encoding = data.decode("utf-8", "replace"), "utf-8"
        return {**info, "kind": "text", "text": text, "truncated": truncated, "encoding": encoding}

    def raw_image(self, rel: str) -> tuple[bytes, str]:
        path = self.resolve(rel)
        kind = IMAGE_TYPES.get(path.suffix.lower())
        if kind is None or path.stat().st_size > IMAGE_LIMIT:
            raise Outside(rel)
        return path.read_bytes(), kind

    # ---- 기록 -----------------------------------------------------------------------------------

    def records(self, limit: int = 300) -> list[dict[str, Any]]:
        return records.read_log(self.root, limit)

    def record(self, rid: Any) -> dict[str, Any] | None:
        return records.read_record(self.root, rid)

    def candidates(self, part: Any) -> dict[str, Any]:
        return records.read_candidates(self.root, part)

    def changes(self, limit: int = 100) -> list[dict[str, Any]]:
        out = [read_change(self.root, cid) for cid in history_ids(self.root)[-limit:]]
        return [c for c in out if c]

    def change(self, cid: Any) -> dict[str, Any] | None:
        if not isinstance(cid, str) or not records.CHANGE_ID.match(cid):
            return None
        return read_change(self.root, cid, with_diff=True)


class AppState:
    """앱 하나의 상태 — 프로젝트 탭들, 터미널들, 알림 줄, 설정."""

    def __init__(self, config: Config | None = None, mode: str = "app") -> None:
        self.config = config if config is not None else Config()
        self.mode = mode                       # 'app'(창) | 'browser'(개발용)
        self.token: str | None = None          # 창 모드에서 pywebview 가 주는 값
        self.term_secret = secrets.token_hex(16)
        self.terminals = terminal.Terminals()
        self.feed = Feed()
        self.sessions: dict[str, ProjectSession] = {}     # 탭 순서대로
        self.active: str | None = None
        self.pick_folder: Callable[[], str | None] | None = None   # 창 모드의 폴더 고르기 대화상자
        self.pick_file: Callable[[], str | None] | None = None     # 창 모드의 파일 고르기 대화상자(원자료 넣기)
        self.on_active: Callable[[ProjectSession | None], None] | None = None   # 고른 탭이 바뀌었을 때(창 제목)
        self._lock = threading.RLock()

    # ---- 탭 -------------------------------------------------------------------------------------

    def session(self, pid: Any) -> ProjectSession | None:
        return self.sessions.get(pid) if isinstance(pid, str) else None

    def tabs(self) -> list[dict[str, Any]]:
        with self._lock:
            return [{"id": s.id, "root": s.root, "name": s.name} for s in self.sessions.values()]

    def open(self, root: str, activate: bool = True, announce: bool = True, recent: bool = True) -> ProjectSession:
        """폴더를 프로젝트 탭으로 연다(이미 열려 있으면 그 탭을 고른다).

        오류
            NotAProject: 폴더가 아니거나 `equion.toml` 이 없다
            TooManyTabs: 탭이 이미 `MAX_TABS` 개다
        """
        path = Path(os.path.abspath(os.path.expanduser(root)))
        if not path.is_dir():
            raise NotAProject(t("폴더가 아닙니다: {path}", path=root))
        if not (path / "equion.toml").is_file():
            raise NotAProject(t("Equion 프로젝트 폴더가 아닙니다(equion.toml이 없습니다): {path}", path=str(path)))
        with self._lock:
            pid = project_id(str(path.resolve()))
            session = self.sessions.get(pid)
            if session is None:
                if len(self.sessions) >= MAX_TABS:
                    raise TooManyTabs(t("프로젝트 탭은 {n}개까지 엽니다 — 하나를 닫고 다시 여세요", n=MAX_TABS))
                session = ProjectSession(str(path), self.feed)
                self.sessions[session.id] = session
            if activate or self.active is None:
                self.active = session.id
            if recent:
                self.config.add_recent(session.root)
            self._remember()
        if announce:
            self.feed.add("tabs", active=self.active)
        if self.on_active:
            self.on_active(self.session(self.active))
        return session

    def close_tab(self, pid: str) -> bool:
        with self._lock:
            session = self.sessions.pop(pid, None)
            if session is None:
                return False
            order = list(self.sessions)
            if self.active == pid:
                self.active = order[-1] if order else None
            self._remember()
        self.terminals.close_project(pid)
        session.close()
        self.feed.add("tabs", active=self.active)
        if self.on_active:
            self.on_active(self.session(self.active))
        return True

    def activate(self, pid: str) -> bool:
        with self._lock:
            if pid not in self.sessions:
                return False
            self.active = pid
            self._remember()
        if self.on_active:
            self.on_active(self.session(pid))
        return True

    def _remember(self) -> None:
        roots = [s.root for s in self.sessions.values()]
        order = list(self.sessions)
        self.config.set_tabs(roots, order.index(self.active) if self.active in order else 0)

    def restore(self) -> None:
        """지난 실행에 열어 둔 탭을 되살린다 — 없어진 폴더는 건너뛴다."""
        roots, active = self.config.get("tabs") or [], self.config.get("active") or 0
        opened: list[str] = []
        for root in roots:
            try:
                opened.append(self.open(root, activate=False, announce=False, recent=False).id)
            except (NotAProject, TooManyTabs, OSError):
                continue
        with self._lock:
            if opened:
                self.active = opened[min(active, len(opened) - 1)]
            self._remember()

    def notify(self, text: str, level: str = "info") -> None:
        """화면에 알릴 말(창 모드에서는 콘솔이 보이지 않는다)."""
        self.feed.add("notice", text=text, level=level)

    def close(self) -> None:
        self.terminals.close_all()
        with self._lock:
            sessions, self.sessions = list(self.sessions.values()), {}
        for session in sessions:
            session.close()
