"""로컬 서버 — 화면(web/)과 앱 사이. 127.0.0.1에서만 듣는다.

보호 장치는 Lectern 0.69.1(`cd7fb26`)의 `lectern/server.py`에서 가져왔다(desk/THIRD-PARTY-NOTICES.md):

- 다른 도메인 이름으로 들어온 요청은 거절한다(DNS 리바인딩).
- 창 모드에서는 pywebview가 준 토큰(`X-Token`)이 있어야 `/api/`를 쓴다.
- POST는 JSON 본문만 받는다(다른 사이트의 폼이 사전 확인 없이 보내지 못하게).
- 터미널은 페이지에 실은 비밀값(`X-Term`)과 요청을 보낸 페이지(Origin)까지 확인한다 — 셸로 가는 길은 사용자의 키 입력뿐이다.
"""
from __future__ import annotations

import secrets
from pathlib import Path
from typing import Any

from flask import Flask, Response, abort, jsonify, request, send_from_directory

from . import __version__, terminal
from .i18n import t
from .worker import Worker, WorkerError

ALLOWED_HOSTS = frozenset({"127.0.0.1", "localhost"})

# 형식이 틀리면 브라우저가 거부하는 파일들 — 레지스트리에 .js·.css가 text/plain으로 잡힌 PC가 있다(Lectern에서 확인)
FIXED_TYPES = {".js": "text/javascript", ".mjs": "text/javascript", ".css": "text/css", ".svg": "image/svg+xml"}

CSP = ("default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; "
       "connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")


def web_dir() -> Path:
    return Path(__file__).resolve().parent / "web"


class AppState:
    """앱 하나의 상태 — 연 프로젝트 폴더, 터미널들, 작업 프로세스. (D0: 프로젝트 하나. 탭은 D1에서)"""

    def __init__(self, root: str | None, mode: str = "app") -> None:
        self.root = str(Path(root).resolve()) if root else None
        self.mode = mode                       # 'app'(창) | 'browser'(개발용)
        self.token: str | None = None          # 창 모드에서 pywebview가 주는 값
        self.term_secret = secrets.token_hex(16)
        self.terminals = terminal.Terminals()
        self.worker = Worker(self.root) if self.root else None
        self.pick_folder: Any = None           # 창 모드에서 폴더 고르기 대화상자를 띄우는 함수(없으면 화면에서 고를 수 없다)
        self.on_open: Any = None               # 프로젝트를 열었을 때(창 제목을 바꾼다)

    def open(self, root: str) -> None:
        """프로젝트 폴더를 연다 — 하던 터미널·작업 프로세스는 끝낸다."""
        self.terminals.close_all()
        if self.worker:
            self.worker.stop()
        self.root = str(Path(root).resolve())
        self.worker = Worker(self.root)
        if self.on_open:
            self.on_open(self.root)

    def close(self) -> None:
        self.terminals.close_all()
        if self.worker:
            self.worker.stop()


def create_app(state: AppState) -> Flask:
    web = web_dir()
    app = Flask(__name__, static_folder=None)

    def body() -> dict[str, Any]:
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            abort(400)
        return data

    def worker() -> Worker:
        if state.worker is None:
            abort(409, description=t("연 프로젝트가 없습니다"))
        return state.worker

    @app.before_request
    def check_request() -> None:
        if request.host.rsplit(":", 1)[0] not in ALLOWED_HOSTS:
            abort(403)
        if state.token and request.path.startswith("/api/"):
            if request.headers.get("X-Token") != state.token:
                abort(403)
        if request.method == "POST" and request.path.startswith("/api/") and not request.is_json:
            abort(415, description=t("JSON 본문만 받습니다"))

    @app.after_request
    def common_headers(resp: Response) -> Response:
        resp.headers["Cache-Control"] = "no-cache"
        resp.headers["X-Content-Type-Options"] = "nosniff"
        return resp

    @app.get("/")
    def index() -> Response:
        html = (web / "index.html").read_text(encoding="utf-8")
        html = html.replace("{{MODE}}", state.mode).replace("{{VERSION}}", __version__).replace("{{TERM}}", state.term_secret)
        resp = Response(html, content_type="text/html; charset=utf-8")
        resp.headers["Content-Security-Policy"] = CSP
        resp.headers["Referrer-Policy"] = "no-referrer"
        return resp

    @app.get("/web/<path:rel>")
    def static_file(rel: str) -> Response:
        resp = send_from_directory(web, rel)
        fixed = FIXED_TYPES.get(Path(rel).suffix.lower())
        if fixed:
            resp.headers["Content-Type"] = f"{fixed}; charset=utf-8"
        return resp

    # ---- 프로젝트·작업 프로세스 ------------------------------------------------------------------

    @app.get("/api/state")
    def api_state() -> Any:
        w = state.worker
        return jsonify(version=__version__, mode=state.mode, root=state.root, terminal=state.terminals.available,
                       can_pick=state.pick_folder is not None,
                       worker={"alive": bool(w and w.alive), "busy": w.busy_op if w else None,
                               "started_seconds": w.started_seconds if w else None})

    @app.post("/api/open")
    def api_open() -> Any:
        """폴더 고르기 대화상자를 띄워 고른 프로젝트 폴더를 연다(창 모드). {root} — 고르지 않았으면 root는 null."""
        if state.pick_folder is None:
            abort(501, description=t("폴더 고르기는 앱 창에서만 됩니다 — 실행할 때 폴더를 주세요"))
        folder = state.pick_folder()
        if not folder:
            return jsonify(root=None)
        if not (Path(folder) / "equion.toml").is_file():
            return jsonify(error=t("Equion 프로젝트 폴더가 아닙니다(equion.toml이 없습니다): {path}", path=folder)), 422
        state.open(folder)
        return jsonify(root=state.root)

    @app.post("/api/example")
    def api_example() -> Any:
        """예제 프로젝트(가상 분기 모형)를 문서 폴더 아래에 새로 만들어 연다. {root}"""
        import subprocess

        from . import runtime

        base = Path.home() / "Documents" / "Equion"
        base.mkdir(parents=True, exist_ok=True)
        n = 1
        while (base / f"example{n}").exists():
            n += 1
        r = subprocess.run([runtime.python_exe(), "-I", "-X", "utf8", "-m", "equion", "new", f"example{n}", "--template", "desk"],
                           cwd=base, env=runtime.clean_env(), capture_output=True, text=True, encoding="utf-8",
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if r.returncode != 0:
            return jsonify(error=(r.stderr or r.stdout).strip()), 500
        state.open(str(base / f"example{n}"))
        return jsonify(root=state.root)

    def run(op: str, **args: Any) -> Any:
        """작업 프로세스에 일을 시키고 `{result, seconds, said, round_trip}`. 오류는 `{error, kind}`와 상태 코드로."""
        try:
            return jsonify(worker().call(op, **args))
        except WorkerError as exc:
            code = {"input": 422, "cancelled": 409, "gone": 503}.get(exc.kind, 500)
            return jsonify(error=str(exc), kind=exc.kind, detail=exc.detail), code

    @app.get("/api/project")
    def api_project() -> Any:
        """프로젝트 이름·판과 부품 목록 — 작업 프로세스를 띄운다(처음이면 여기서 뜬다)."""
        try:
            info = worker().call("ping")
            parts = worker().call("parts")
        except WorkerError as exc:
            return jsonify(error=str(exc), kind=exc.kind), 422 if exc.kind == "input" else 503
        return jsonify(info=info["result"], parts=parts["result"], started_seconds=worker().started_seconds)

    @app.post("/api/est")
    def api_est() -> Any:
        """{target, method?, smpl?} — 부품(`demand:CN`)이나 식 글자를 추정하고 기록을 남긴다."""
        data = body()
        target = data.get("target")
        if not isinstance(target, str) or not target.strip() or len(target) > 4000:
            abort(400)
        opts = {k: data[k] for k in ("method", "smpl") if isinstance(data.get(k), str) and data[k].strip()}
        return run("est", target=target.strip(), **opts)

    @app.post("/api/hs")
    def api_hs() -> Any:
        model = body().get("model")
        return run("hs", model=model if isinstance(model, str) and model else None)

    @app.post("/api/sim")
    def api_sim() -> Any:
        scenario = body().get("scenario")
        return run("sim", scenario=scenario if isinstance(scenario, str) and scenario else "base")

    @app.post("/api/cancel")
    def api_cancel() -> Any:
        return jsonify(cancelled=worker().cancel())

    # ---- 터미널 (Lectern D38·D69) ----------------------------------------------------------------

    def term_guard() -> None:
        if not state.terminals.available:
            abort(501, description=t("터미널은 Windows 10(1809) 이상에서만 쓸 수 있습니다"))
        if request.headers.get("X-Term") != state.term_secret:
            abort(403)
        origin = request.headers.get("Origin")
        if origin and origin != f"{request.scheme}://{request.host}":
            abort(403)

    def session_of(sid: Any) -> terminal.Session:
        session = state.terminals.get(sid)
        if session is None:
            abort(404, description=t("끝난 터미널입니다"))
        return session

    def term_size(data: dict[str, Any]) -> tuple[int, int]:
        cols, rows = data.get("cols", 80), data.get("rows", 24)
        if not all(isinstance(v, int) and not isinstance(v, bool) and 1 <= v <= 1000 for v in (cols, rows)):
            abort(400)
        return cols, rows

    @app.post("/api/term/open")
    def api_term_open() -> Any:
        """프로젝트 폴더에서 셸을 띄운다(이미 돌고 있으면 그것). {id, shell, cwd}"""
        term_guard()
        if not state.root:
            abort(409, description=t("연 프로젝트가 없습니다"))
        cols, rows = term_size(body())
        try:
            session = state.terminals.open("main", state.root, None, cols, rows, 0)
        except OSError as exc:
            return jsonify(error=t("셸을 시작하지 못했습니다 ({error})", error=exc)), 500
        return jsonify(id=session.id, shell=terminal.shell_label(session.exe), cwd=state.root)

    @app.post("/api/term/read")
    def api_term_read() -> Any:
        """{want: {셸 id: 받은 곳}} — 긴 폴링. {terms: {셸 id: {data, next, reset, alive, exit, stuck} | null}}"""
        term_guard()
        want = body().get("want")
        if not isinstance(want, dict) or not 0 < len(want) <= 16 or not all(
                isinstance(k, str) and isinstance(v, int) and not isinstance(v, bool) and v >= 0 for k, v in want.items()):
            abort(400)
        return jsonify(terms=state.terminals.read_many(want, terminal.READ_WAIT))

    @app.post("/api/term/input")
    def api_term_input() -> Any:
        term_guard()
        data = body()
        text = data.get("data")
        if not isinstance(text, str):
            abort(400)
        if len(text) > 65536:
            abort(413, description=t("한 번에 보낼 수 있는 글은 65536자까지입니다"))
        session_of(data.get("t")).write(text)
        return jsonify(ok=True)

    @app.post("/api/term/resize")
    def api_term_resize() -> Any:
        term_guard()
        data = body()
        session_of(data.get("t")).resize(*term_size(data))
        return jsonify(ok=True)

    @app.post("/api/term/close")
    def api_term_close() -> Any:
        term_guard()
        sid = body().get("t")
        if not isinstance(sid, str):
            abort(400)
        state.terminals.close(sid)
        return jsonify(ok=True)

    @app.errorhandler(400)
    @app.errorhandler(403)
    @app.errorhandler(404)
    @app.errorhandler(409)
    @app.errorhandler(413)
    @app.errorhandler(415)
    @app.errorhandler(422)
    @app.errorhandler(501)
    def json_error(err: Any) -> Any:
        if request.path.startswith("/api/"):
            return jsonify(error=getattr(err, "description", str(err))), err.code
        return err

    return app
