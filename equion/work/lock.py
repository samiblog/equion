#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""프로젝트 잠금과 안전한 쓰기 — 같은 프로젝트를 여러 명령이 한꺼번에 고쳐도 고친 것이 사라지지 않게.

같은 프로젝트에서 명령이 동시에 돈다: Claude Code가 명령 여럿을 나란히, Desk와 터미널, 흐름(.eqs)과 터미널. 정의 파일을
읽어 고쳐 쓰는 일(채택·블록 고치기 …), 바뀜 기록의 번호, 기록 이름 정하기, `work/log.jsonl`에 줄 더하기는 잠금
`work/.lock` 안에서만 한다(한 번에 하나 — 프로세스가 끝나면 운영체제가 저절로 푼다). 다른 명령이 쥐고 있으면 기다리고
(`EQUION_LOCK_TIMEOUT`초, 기본 30), 그래도 안 되면 `ProjectBusy`(입력 오류 — 종료 코드 3). 읽기만 하는 명령은 잠그지 않는다.

같은 프로세스 안에서는 겹쳐 잡아도 된다(재진입 — 바깥에서 잡았으면 안쪽은 그대로 지나간다).

다른 프로그램(엑셀·동기화·백신)이 파일을 쥐고 있어 읽거나 바꿀 수 없으면 `FileBusy`(그 파일 이름과 함께, 종료 코드 3).
여러 파일을 바꾸는 일은 임시 파일을 다 쓴 뒤 바꾸고, 하나라도 바꾸지 못하면 이미 바꾼 것을 되돌린다(반쯤 바뀐 채 남지 않게).
임시 이름은 프로세스마다 다르다(`<파일>.<pid>-<임의>.tmp-equion`).
"""

import functools
import os
import threading
import time
import uuid
from contextlib import contextmanager
from typing import Dict, Optional

LOCK_FILE = ".lock"                  # work/.lock
TIMEOUT_ENV = "EQUION_LOCK_TIMEOUT"
DEFAULT_TIMEOUT = 30.0


class ProjectBusy(ValueError):
    """다른 명령이 이 프로젝트를 고치는 중이라 기다렸지만 끝나지 않았다(입력 오류 — 종료 코드 3). 아무것도 바꾸지 않았다."""


class FileBusy(PermissionError, ValueError):
    """다른 프로그램이 쥐고 있어 그 파일을 읽거나 바꿀 수 없다 — `.rel`(프로젝트 기준 경로). 종료 코드 3.

    PermissionError이기도 하다(파일 오류를 OSError로 받던 곳은 그대로), ValueError이기도 하다(명령이 입력 오류로 알린다)."""

    def __init__(self, message: str, rel: str = None):
        super().__init__(message)
        self.rel = rel

    def __str__(self):
        return self.args[0] if self.args else ""


def timeout() -> float:
    """잠금을 기다리는 시간(초) — EQUION_LOCK_TIMEOUT, 기본 30."""
    try:
        return max(0.0, float(os.environ.get(TIMEOUT_ENV, DEFAULT_TIMEOUT)))
    except ValueError:
        return DEFAULT_TIMEOUT


def busy_message(rel: str, reading: bool = False, rolled_back: bool = True, extra: str = "") -> str:
    """다른 프로그램이 파일을 쥐고 있을 때의 글."""
    what = "읽을" if reading else "바꿀"
    tail = " 아무것도 바꾸지 않았습니다." if rolled_back else ""
    return (f"다른 프로그램(엑셀·동기화·백신 등)이 {rel}을(를) 쓰고 있어 {what} 수 없습니다 — 그 프로그램에서 닫거나 "
            f"동기화가 끝난 뒤 다시 하세요.{tail}{extra}")


def is_busy(e: BaseException) -> bool:
    """파일을 다른 프로그램이 쥐고 있어서 난 오류인가(접근 거부·공유 위반·잠금 위반)."""
    if isinstance(e, FileBusy):
        return True
    return isinstance(e, PermissionError) or getattr(e, "winerror", None) in (5, 32, 33)


def as_busy(e: OSError, rel: str, reading: bool = False, rolled_back: bool = True) -> OSError:
    """OSError → FileBusy(쥐고 있어서면) · 그대로(다른 까닭이면)."""
    if isinstance(e, FileBusy):
        return e
    if is_busy(e):
        return FileBusy(busy_message(rel, reading=reading, rolled_back=rolled_back), rel)
    return e


def _rel(root: Optional[str], path: str) -> str:
    if root:
        try:
            return os.path.relpath(path, root).replace(os.sep, "/")
        except ValueError:
            pass
    return path


# ---------------------------------------------------------------------------
# 잠금
# ---------------------------------------------------------------------------
class _Held:
    def __init__(self):
        self.rlock = threading.RLock()     # 같은 프로세스의 다른 스레드(Desk 작업 프로세스 등)
        self.depth = 0
        self.fh = None


_GUARD = threading.Lock()
_HELD: Dict[str, _Held] = {}


def _key(root: str) -> str:
    return os.path.normcase(os.path.realpath(os.path.abspath(root)))


def _try_lock(fh) -> bool:
    try:
        if os.name == "nt":
            import msvcrt
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError:
        return False


def _unlock(fh):
    try:
        if os.name == "nt":
            import msvcrt
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
    except OSError:
        pass
    finally:
        fh.close()


def _busy_project(root: str, waited: float) -> ProjectBusy:
    return ProjectBusy(f"다른 명령이 이 프로젝트를 고치는 중입니다(work/{LOCK_FILE}) — {waited:.0f}초 기다렸지만 끝나지 않았습니다. "
                       "그 명령(터미널·Desk·흐름·Claude)이 끝난 뒤 다시 하세요. 아무것도 바꾸지 않았습니다. "
                       f"(기다리는 시간: 환경 변수 {TIMEOUT_ENV})")


def _open_lock(root: str, deadline: float):
    d = os.path.join(root, "work")
    path = os.path.join(d, LOCK_FILE)
    delay = 0.005
    t0 = time.monotonic()
    while True:
        try:
            os.makedirs(d, exist_ok=True)
            fh = open(path, "a+b")
        except OSError as e:
            if not is_busy(e) or time.monotonic() >= deadline:
                raise as_busy(e, f"work/{LOCK_FILE}") from None
            time.sleep(delay)
            continue
        if _try_lock(fh):
            return fh
        fh.close()
        if time.monotonic() >= deadline:
            raise _busy_project(root, time.monotonic() - t0)
        time.sleep(delay)
        delay = min(delay * 1.6, 0.1)


@contextmanager
def project_lock(root: str, wait: float = None):
    """프로젝트 잠금 — `with project_lock(root) as first:`. first는 이 프로세스에서 처음 잡았으면 참(겹쳐 잡으면 거짓).

    기다리는 시간(wait, 기본 EQUION_LOCK_TIMEOUT·30초)이 지나도 다른 명령이 쥐고 있으면 ProjectBusy."""
    key = _key(root)
    with _GUARD:
        st = _HELD.setdefault(key, _Held())
    limit = timeout() if wait is None else wait
    t0 = time.monotonic()
    deadline = t0 + limit
    if not st.rlock.acquire(timeout=limit if limit > 0 else 0.001):
        raise _busy_project(root, time.monotonic() - t0)
    try:
        first = st.depth == 0
        if first:
            st.fh = _open_lock(root, deadline)
        st.depth += 1
        try:
            yield first
        finally:
            st.depth -= 1
            if st.depth == 0 and st.fh is not None:
                fh, st.fh = st.fh, None
                _unlock(fh)
    finally:
        st.rlock.release()


def locked(fn):
    """첫 인자(프로젝트 — `.root`가 있는 것)의 잠금을 쥐고 부른다. 처음 잡았으면 프로젝트가 읽어 둔 정의가 낡았는지 보고 다시 읽는다
    (`_fresh`) — 기다리는 사이에 다른 명령이 고친 것 위에 고치도록."""

    @functools.wraps(fn)
    def wrapper(p, *args, **kwargs):
        with project_lock(p.root) as first:
            if first and hasattr(p, "_fresh"):
                p._fresh()
            return fn(p, *args, **kwargs)
    return wrapper


# ---------------------------------------------------------------------------
# 안전한 쓰기
# ---------------------------------------------------------------------------
def tmp_path(path: str) -> str:
    """그 파일(또는 폴더) 옆의 임시 이름 — 프로세스마다 다르다(`.tmp-equion`으로 끝나 Desk의 감시·묶음이 건너뛴다)."""
    return f"{path}.{os.getpid()}-{uuid.uuid4().hex[:8]}.tmp-equion"


def tmp_dir(parent: str, name: str) -> str:
    """parent 안의 임시 폴더 이름 `.tmp-<이름>-<pid>-<임의>` — 기록·바뀜 기록을 다 쓴 뒤 한 번에 옮긴다."""
    return os.path.join(parent, f".tmp-{name}-{os.getpid()}-{uuid.uuid4().hex[:8]}")


def _retry(fn, *args):
    """Windows에서 방금 쓴 파일을 백신·색인·폴더 감시가 잠깐 쥐면 거절된다 — 잠깐씩 기다리며 몇 번 다시."""
    for wait in (0.02, 0.05, 0.1, 0.2, 0.4, 0.8, None):
        try:
            return fn(*args)
        except PermissionError:
            if wait is None:
                raise
            time.sleep(wait)


def read_bytes(path: str, root: str = None) -> Optional[bytes]:
    """파일 내용(없으면 None) — 다른 프로그램이 쥐고 있어 읽을 수 없으면 FileBusy."""
    try:
        with open(path, "rb") as f:
            return f.read()
    except FileNotFoundError:
        return None
    except OSError as e:
        raise as_busy(e, _rel(root, path), reading=True) from None


def write_bytes(path: str, data: bytes, root: str = None) -> None:
    """파일 하나를 안전하게 — 임시 파일에 다 쓴 뒤 바꾼다. 바꾸지 못하면 임시 파일을 지우고 FileBusy(파일은 그대로)."""
    replace_files({path: data}, root=root)


def replace_files(new: Dict[str, Optional[bytes]], root: str = None, before: Dict[str, Optional[bytes]] = None) -> None:
    """파일 여럿을 한 묶음으로 바꾼다 — {경로: 새 내용(None이면 지움)}.

    임시 파일을 모두 쓴 뒤 차례로 바꾸고, 하나라도 바꾸지 못하면(다른 프로그램이 쥐고 있음) 이미 바꾼 파일을 전 내용(before —
    주지 않으면 바꾸기 전에 읽은 것)으로 되돌린 다음 FileBusy. 반쯤 바뀐 채 남지 않는다."""
    if before is None:
        before = {p: read_bytes(p, root) for p in new}
    temps: Dict[str, str] = {}
    cur = None
    try:
        for p, data in new.items():
            if data is None:
                continue
            cur = p
            os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
            t = tmp_path(p)
            with open(t, "wb") as f:
                f.write(data)
            temps[p] = t
    except OSError as e:
        _drop(temps.values())
        raise as_busy(e, _rel(root, cur)) from None
    done = []
    try:
        for p, data in new.items():
            cur = p
            if data is None:
                if os.path.lexists(p):
                    _retry(os.remove, p)
            else:
                _retry(os.replace, temps[p], p)
                del temps[p]
            done.append(p)
    except OSError as e:
        failed = []
        for q in reversed(done):                     # 이미 바꾼 것을 되돌린다
            try:
                _restore(q, before.get(q))
            except OSError:
                failed.append(_rel(root, q))
        _drop(temps.values())
        if failed:
            extra = " 되돌리지 못한 파일: " + ", ".join(failed) + " — equion history list로 확인하세요."
            if is_busy(e):
                raise FileBusy(busy_message(_rel(root, cur), rolled_back=False, extra=extra), _rel(root, cur)) from None
            raise OSError(f"{_rel(root, cur)}: {e}.{extra}") from None
        raise as_busy(e, _rel(root, cur)) from None


def _restore(p: str, data: Optional[bytes]):
    if data is None:
        if os.path.lexists(p):
            _retry(os.remove, p)
        return
    t = tmp_path(p)
    with open(t, "wb") as f:
        f.write(data)
    try:
        _retry(os.replace, t, p)
    except OSError:
        _drop([t])
        raise


def _drop(paths):
    for t in list(paths):
        try:
            os.remove(t)
        except OSError:
            pass
