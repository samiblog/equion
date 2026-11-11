"""`python -m equion_desk [폴더]` · `equion-desk [폴더]` — Equion Desk를 띄운다.

    equion-desk 폴더              창(pywebview — Edge WebView2)으로
    equion-desk --browser 폴더    개발용: 서버만 띄우고 일반 브라우저로 본다
    equion-desk --debug 폴더      창 + 개발자 도구
    equion-desk --version

지난 실행에 열어 둔 프로젝트 탭들을 되살리고, 폴더를 주면 그 폴더를 탭으로 더해 고른다. 창이 이미 떠 있으면 새 창을 띄우지 않고
그 창에 폴더를 탭으로 넘긴다(`instance.py`). `--browser`·`--debug` 실행은 따로 뜬다(개발용).

서버(`HttpServer`)는 Lectern 0.69.1(`cd7fb26`)의 `app.py`에서 가져왔다(desk/THIRD-PARTY-NOTICES.md).
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import threading
from typing import Any

from . import __version__

HTTP_THREADS = 32                    # 터미널의 긴 폴링이 자리를 오래 쓴다
MEMORY_BUFFER = 64 * 1024 * 1024     # waitress는 이보다 큰 요청·응답을 임시 파일에 쓴다
WINDOW = (1360, 860)
MIN_WINDOW = (860, 520)


class HttpServer:
    """로컬 서버. 연결을 재사용한다(Lectern D82)."""

    def __init__(self, app: Any, port: int) -> None:
        from waitress.server import create_server

        self._server = create_server(app, host="127.0.0.1", port=port, threads=HTTP_THREADS, ident="EquionDesk",
                                     inbuf_overflow=MEMORY_BUFFER, outbuf_overflow=MEMORY_BUFFER)
        self.server_port = self._server.effective_port

    def serve_forever(self) -> None:
        self._server.run()
        self._server.task_dispatcher.shutdown(timeout=1)

    def shutdown(self) -> None:
        """연결을 모두 닫아 serve_forever를 끝낸다 — waitress의 이벤트 루프 안에서 닫는다."""
        server = self._server

        def close_all() -> None:
            for channel in list(server._map.values()):
                channel.close()

        server.trigger.pull_trigger(close_all)


def versions() -> str:
    import equion

    return f"Equion Desk {__version__} / equion {equion.__version__} / Python {sys.version.split()[0]}"


def window_size(saved: Any) -> tuple[int, int]:
    """설정의 창 크기. 형식이 틀렸으면 기본값, 최소 크기보다 작으면 최소 크기."""
    try:
        width, height = int(saved["width"]), int(saved["height"])
    except (TypeError, KeyError, ValueError):
        return WINDOW
    return max(width, MIN_WINDOW[0]), max(height, MIN_WINDOW[1])


def icon_path() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "equion-desk.ico")


def set_window_icon(window: Any) -> None:
    """창과 작업 표시줄의 아이콘 — 실행기가 바로 가기(pythonw.exe)라 그대로 두면 Python 아이콘이 보인다(D40)."""
    if sys.platform != "win32" or not os.path.isfile(icon_path()):
        return
    try:
        import ctypes

        user32 = ctypes.windll.user32
        user32.LoadImageW.restype = ctypes.c_void_p
        user32.SendMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p]
        hwnd = int(window.native.Handle.ToInt64())
        IMAGE_ICON, LR_LOADFROMFILE, WM_SETICON = 1, 0x10, 0x80
        for which, size in ((0, 16), (1, 32)):         # ICON_SMALL(제목줄) · ICON_BIG(작업 표시줄·Alt+Tab)
            scale = max(1, user32.GetDpiForWindow(hwnd) // 96) if hasattr(user32, "GetDpiForWindow") else 1
            handle = user32.LoadImageW(None, icon_path(), IMAGE_ICON, size * scale, size * scale, LR_LOADFROMFILE)
            if handle:
                user32.SendMessageW(hwnd, WM_SETICON, which, handle)
    except Exception:  # 아이콘을 못 달아도 앱은 돈다
        pass


def title_of(session: Any) -> str:
    return "Equion Desk" + (f" — {session.name}" if session is not None else "")


def open_folder(state: Any, folder: str) -> None:
    """실행 인자로 받은 폴더를 탭으로 연다. 열지 못하면 화면에 알린다(창 모드에서는 콘솔이 보이지 않는다)."""
    from .projects import NotAProject, TooManyTabs

    try:
        state.open(folder)
    except (NotAProject, TooManyTabs, OSError) as exc:
        print(f"equion-desk: {exc}", file=sys.stderr)
        state.notify(str(exc), "error")


def run_browser(state: Any, port: int) -> None:
    from .server import create_app

    server = HttpServer(create_app(state), port or 8766)
    print(f"Equion Desk (browser mode): http://127.0.0.1:{server.server_port}/  (Ctrl+C to stop)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


def run_window(state: Any, port: int, debug: bool, receiver: Any = None, query: str = "") -> None:
    import webview

    from .server import create_app

    state.token = getattr(webview, "token", None)
    server = HttpServer(create_app(state), port)
    threading.Thread(target=server.serve_forever, name="desk-http", daemon=True).start()
    if sys.platform == "win32":
        # 작업 표시줄에서 python이 아니라 이 앱으로 묶이게(바로 가기로 띄우는 실행기 — D40)
        import ctypes

        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Equion.Desk")
        except (AttributeError, OSError):
            pass
    width, height = window_size(state.config.get("window"))
    window = webview.create_window(title_of(state.session(state.active)), f"http://127.0.0.1:{server.server_port}/{query}",
                                   width=width, height=height, min_size=MIN_WINDOW, text_select=True, zoomable=True)

    def pick_folder() -> str | None:
        dialog = getattr(getattr(webview, "FileDialog", None), "FOLDER", None) or webview.FOLDER_DIALOG
        chosen = window.create_file_dialog(dialog)
        return str(chosen[0]) if chosen else None

    def set_title(session: Any) -> None:
        try:
            window.set_title(title_of(session))
        except Exception:  # 창이 아직 없거나 닫히는 중
            pass

    def pick_file() -> str | None:
        dialog = getattr(getattr(webview, "FileDialog", None), "OPEN", None) or webview.OPEN_DIALOG
        chosen = window.create_file_dialog(dialog, allow_multiple=False, file_types=("자료 파일 (*.csv;*.xlsx;*.xls)", "모든 파일 (*.*)"))
        return str(chosen[0]) if chosen else None

    state.pick_folder = pick_folder
    state.pick_file = pick_file
    state.on_active = set_title

    # 최소화·최대화한 채로 닫으면 그때 크기를 저장하지 않는다(다음에 아주 작거나 화면만 한 창이 되지 않게 — Lectern)
    shown = {"state": "normal"}
    window.events.minimized += lambda: shown.update(state="minimized")
    window.events.maximized += lambda: shown.update(state="maximized")
    window.events.restored += lambda: shown.update(state="normal")
    window.events.shown += lambda: set_window_icon(window)

    def on_closing() -> None:
        if shown["state"] == "normal":
            try:
                state.config.set_window(window.width, window.height)
            except Exception:  # 창 크기 저장 실패는 무시
                pass

    window.events.closing += on_closing

    def bring_forward(folder: str | None) -> None:
        """다음 실행(탐색기 우클릭 등)이 넘긴 폴더를 탭으로 열고 창을 앞으로. 화면은 알림 줄의 tabs 로 새 탭을 알아챈다."""
        if folder:
            open_folder(state, folder)
        if shown["state"] == "minimized":
            window.restore()
        window.show()

    if receiver:
        receiver.start(bring_forward)
    try:
        webview.start(debug=debug)
    finally:
        server.shutdown()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="equion-desk", description="Equion Desk")
    ap.add_argument("folder", nargs="?", help="열 프로젝트 폴더(equion.toml이 있는 곳)")
    ap.add_argument("--browser", action="store_true", help="창 없이 서버만(개발용)")
    ap.add_argument("--port", type=int, default=0, help="서버 포트(기본: 자동, --browser는 8766)")
    ap.add_argument("--debug", action="store_true", help="개발자 도구")
    ap.add_argument("--est", metavar="부품|식", help="열자마자 이것을 추정해 보인다(예: demand:CN)")
    ap.add_argument("--version", action="store_true", help="판을 알리고 끝낸다")
    args = ap.parse_args(argv)
    if args.version:
        print(versions())
        return 0
    if not (args.browser or args.debug):
        logging.getLogger("waitress").setLevel(logging.ERROR)

    from . import instance
    from .config import Config
    from .projects import AppState

    folder = os.path.abspath(os.path.expanduser(args.folder)) if args.folder else None
    if folder and not os.path.isdir(folder):
        print(f"equion-desk: not a folder: {folder}", file=sys.stderr)
        return 3
    config = Config()
    # 창은 하나, 프로젝트는 탭: 이미 떠 있으면 폴더를 그 창에 넘기고 끝낸다(--browser·--debug 는 따로 뜬다 — 개발용)
    receiver = None
    if not (args.browser or args.debug):
        pipe = instance.pipe_name(config.path.parent)
        if instance.forward(pipe, folder):
            return 0
        receiver = instance.listen(pipe)
    if config.load_error:
        print(f"equion-desk: {config.load_error}", file=sys.stderr)
    state = AppState(config, mode="browser" if args.browser else "app")
    state.restore()
    if folder:
        open_folder(state, folder)
    try:
        if args.browser:
            run_browser(state, args.port)
        else:
            from urllib.parse import urlencode

            run_window(state, args.port, args.debug, receiver, "?" + urlencode({"est": args.est}) if args.est else "")
    finally:
        state.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
