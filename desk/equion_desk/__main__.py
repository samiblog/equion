"""`python -m equion_desk [폴더]` · `equion-desk [폴더]` — Equion Desk를 띄운다.

    equion-desk 폴더              창(pywebview — Edge WebView2)으로
    equion-desk --browser 폴더    개발용: 서버만 띄우고 일반 브라우저로 본다
    equion-desk --debug 폴더      창 + 개발자 도구
    equion-desk --version

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


def run_browser(state: Any, port: int) -> None:
    from .server import create_app

    server = HttpServer(create_app(state), port or 8766)
    print(f"Equion Desk (browser mode): http://127.0.0.1:{server.server_port}/  (Ctrl+C to stop)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


def run_window(state: Any, port: int, debug: bool, query: str = "") -> None:
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
    title = "Equion Desk" + (f" — {os.path.basename(state.root)}" if state.root else "")
    window = webview.create_window(title, f"http://127.0.0.1:{server.server_port}/{query}", width=WINDOW[0], height=WINDOW[1],
                                   min_size=MIN_WINDOW, text_select=True, zoomable=True)

    def pick_folder() -> str | None:
        dialog = getattr(getattr(webview, "FileDialog", None), "FOLDER", None) or webview.FOLDER_DIALOG
        chosen = window.create_file_dialog(dialog)
        return str(chosen[0]) if chosen else None

    state.pick_folder = pick_folder
    state.on_open = lambda root: window.set_title(f"Equion Desk — {os.path.basename(root)}")
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

    from .server import AppState

    folder = os.path.abspath(os.path.expanduser(args.folder)) if args.folder else None
    if folder and not os.path.isdir(folder):
        print(f"equion-desk: not a folder: {folder}", file=sys.stderr)
        return 3
    state = AppState(folder, mode="browser" if args.browser else "app")
    try:
        if args.browser:
            run_browser(state, args.port)
        else:
            from urllib.parse import urlencode

            run_window(state, args.port, args.debug, "?" + urlencode({"est": args.est}) if args.est else "")
    finally:
        state.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
