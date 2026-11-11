"""로컬 서버 — 화면(web/)과 앱 사이. 127.0.0.1에서만 듣는다.

보호 장치는 Lectern 0.69.1(`cd7fb26`)의 `lectern/server.py`에서 가져왔다(desk/THIRD-PARTY-NOTICES.md):

- 다른 도메인 이름으로 들어온 요청은 거절한다(DNS 리바인딩).
- 창 모드에서는 pywebview가 준 토큰(`X-Token`)이 있어야 `/api/`를 쓴다.
- POST는 JSON 본문만 받는다(다른 사이트의 폼이 사전 확인 없이 보내지 못하게).
- 터미널은 페이지에 실은 비밀값(`X-Term`)과 요청을 보낸 페이지(Origin)까지 확인한다 — 셸로 가는 길은 사용자의 키 입력과 단추뿐이다.
- 프로젝트 파일은 그 폴더 안의 것만 읽는다(`ProjectSession.resolve`). 화면은 파일을 고치지 않는다 — 고치는 것은 작업 프로세스의 명령뿐이다.

경로: `/api/state`·`/api/open`·`/api/example`·`/api/tabs/*`·`/api/settings`·`/api/events`(알림 긴 폴링) ·
프로젝트마다 `/api/p/<탭 id>/overview·est·check·candidates·ident·adopt·hs·diag·sim·cancel·records·record·changes·change·tree·file·raw·view` · `/api/term/*`.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from flask import Flask, Response, abort, jsonify, request, send_from_directory

from . import __version__, terminal
from .i18n import t
from .projects import AppState, NotAProject, Outside, ProjectSession, TooManyTabs
from .worker import WorkerError

__all__ = ["AppState", "create_app"]

ALLOWED_HOSTS = frozenset({"127.0.0.1", "localhost"})
EVENT_WAIT = 25.0      # 알림 긴 폴링이 기다리는 시간(초)

# 형식이 틀리면 브라우저가 거부하는 파일들 — 레지스트리에 .js·.css가 text/plain으로 잡힌 PC가 있다(Lectern에서 확인)
FIXED_TYPES = {".js": "text/javascript", ".mjs": "text/javascript", ".css": "text/css", ".svg": "image/svg+xml"}

# script-src 의 'unsafe-eval': 차트(Vega)가 식을 함수로 만들어 돌리고, pywebview 도 결과를 돌려줄 때 쓴다(Lectern D14).
# 문서의 글은 그리기 전에 정화한다(mdview.js — DOMPurify). 바깥 주소는 어디로도 나가지 않는다(connect-src 'self').
CSP = ("default-src 'none'; script-src 'self' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; "
       "font-src 'self'; connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")


def web_dir() -> Path:
    return Path(__file__).resolve().parent / "web"


def create_app(state: AppState) -> Flask:
    web = web_dir()
    app = Flask(__name__, static_folder=None)
    app.json.sort_keys = False      # 진단·계수는 엔진이 낸 순서대로 보인다

    def body() -> dict[str, Any]:
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            abort(400)
        return data

    def session(pid: str) -> ProjectSession:
        found = state.session(pid)
        if found is None:
            abort(404, description=t("닫힌 프로젝트 탭입니다"))
        return found

    def text_arg(data: dict[str, Any], key: str, limit: int = 200) -> str | None:
        value = data.get(key)
        if value is None or value == "":
            return None
        if not isinstance(value, str) or len(value) > limit:
            abort(400)
        return value.strip() or None

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
        client = state.config.client()
        html = (html.replace("{{MODE}}", state.mode).replace("{{VERSION}}", __version__).replace("{{TERM}}", state.term_secret)
                .replace("{{THEME}}", str(client.get("theme", "auto"))))
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

    # ---- 앱: 탭·설정·알림 ------------------------------------------------------------------------

    def app_state() -> dict[str, Any]:
        return {"version": __version__, "mode": state.mode, "tabs": state.tabs(), "active": state.active,
                "terminal": state.terminals.available, "can_pick": state.pick_folder is not None,
                "recent": state.config.get("recent") or [], "client": state.config.client(), "seq": state.feed.seq}

    @app.get("/api/state")
    def api_state() -> Any:
        return jsonify(app_state())

    def open_folder(folder: str) -> Any:
        try:
            opened = state.open(folder)
        except NotAProject as exc:
            return jsonify(error=str(exc)), 422
        except TooManyTabs as exc:
            return jsonify(error=str(exc)), 409
        return jsonify(id=opened.id, **app_state())

    @app.post("/api/open")
    def api_open() -> Any:
        """프로젝트 폴더를 탭으로 연다. `{root}` 가 없으면 폴더 고르기 대화상자를 띄운다(창 모드). 고르지 않았으면 `{id: null}`."""
        folder = text_arg(body(), "root", 1024)
        if folder is None:
            if state.pick_folder is None:
                abort(501, description=t("폴더 고르기는 앱 창에서만 됩니다 — 실행할 때 폴더를 주세요"))
            folder = state.pick_folder()
            if not folder:
                return jsonify(id=None)
        return open_folder(folder)

    @app.post("/api/example")
    def api_example() -> Any:
        """예제 프로젝트(가상 분기 모형)를 문서 폴더 아래에 새로 만들어 연다."""
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
        return open_folder(str(base / f"example{n}"))

    @app.post("/api/tabs/close")
    def api_tab_close() -> Any:
        pid = text_arg(body(), "id")
        if pid is None or not state.close_tab(pid):
            abort(404)
        return jsonify(app_state())

    @app.post("/api/tabs/active")
    def api_tab_active() -> Any:
        pid = text_arg(body(), "id")
        if pid is None or not state.activate(pid):
            abort(404)
        return jsonify(active=state.active)

    @app.post("/api/recent/forget")
    def api_recent_forget() -> Any:
        folder = text_arg(body(), "root", 1024)
        if folder:
            state.config.forget_recent(folder)
        return jsonify(recent=state.config.get("recent") or [])

    @app.post("/api/settings")
    def api_settings() -> Any:
        """화면 설정(테마·글자 크기·폭…)을 고친다 — 아는 이름·맞는 형식만 받는다."""
        return jsonify(client=state.config.update_client(body()))

    @app.get("/api/events")
    def api_events() -> Any:
        """알림 긴 폴링 — `since` 뒤의 알림(새 기록·바뀜·정의 바뀜·작업 줄·탭). 없으면 기다린다."""
        try:
            since = int(request.args.get("since", "0"))
            wait = min(float(request.args.get("wait", EVENT_WAIT)), EVENT_WAIT)
        except ValueError:
            abort(400)
        return jsonify(state.feed.read(since, max(0.0, wait)))

    # ---- 프로젝트: 개요·계산 ---------------------------------------------------------------------

    def worker_error(exc: WorkerError) -> Any:
        code = {"input": 422, "cancelled": 409, "gone": 503}.get(exc.kind, 500)
        return jsonify(error=str(exc), kind=exc.kind, detail=exc.detail), code

    @app.get("/api/p/<pid>/overview")
    def api_overview(pid: str) -> Any:
        """프로젝트 한눈에(블록과 부품·모형·자료 회차) — 작업 프로세스를 띄운다(처음이면 여기서 뜬다)."""
        s = session(pid)
        try:
            out = s.overview()
        except WorkerError as exc:
            return worker_error(exc)
        w = s.worker
        return jsonify(overview=out["result"], worker={"started_seconds": w.started_seconds, "watch": s.watcher.native})

    def run(pid: str, op: str, label: str, **args: Any) -> Any:
        """작업 프로세스에 일을 시키고 `{result, seconds, said, round_trip}`. 오류는 `{error, kind}`와 상태 코드로."""
        try:
            return jsonify(session(pid).run(op, label, **args))
        except WorkerError as exc:
            return worker_error(exc)

    COV = frozenset({"white", "hac", "hc0", "hc1", "hc2", "hc3"})
    METHODS = frozenset({"auto", "ls", "tsls"})
    NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_\-]{0,60}")
    PART = re.compile(r"[^\s:]{1,60}:[^\s:]{1,60}")
    RECORD = re.compile(r"est:[A-Za-z0-9][A-Za-z0-9_\-]{0,120}")

    def pick(data: dict[str, Any], key: str, pattern: Any = None, allowed: Any = None, limit: int = 200) -> str | None:
        """글 값 하나 — 모양(pattern)이나 허용 목록(allowed)에 맞아야 한다. 없으면 None, 틀리면 400."""
        value = text_arg(data, key, limit)
        if value is None:
            return None
        if (pattern is not None and not pattern.fullmatch(value)) or (allowed is not None and value not in allowed):
            abort(400, description=t("받을 수 없는 값입니다: {key}", key=key))
        return value

    @app.post("/api/p/<pid>/est")
    def api_est(pid: str) -> Any:
        """{target, part?, smpl?, sim?, cov?, method?, name?} — 부품(`demand:CN`)이나 식 글자를 추정하고 기록을 남긴다.

        식 글자에 part 를 주면 그 부품의 후보로 묶인다. sim 은 식 하나의 동태 모의, cov 는 계수 공분산(white·hac…), name 은 기록 이름.
        """
        data = body()
        target = text_arg(data, "target", 4000)
        if target is None:
            abort(400)
        opts = {"part": pick(data, "part", PART), "smpl": text_arg(data, "smpl", 60), "cov": pick(data, "cov", allowed=COV),
                "method": pick(data, "method", allowed=METHODS), "name": pick(data, "name", NAME), "sim": data.get("sim") is True}
        return run(pid, "est", t("추정 {target}", target=target if len(target) <= 40 else target[:38] + "…"), target=target,
                   **{k: v for k, v in opts.items() if v})

    @app.post("/api/p/<pid>/check")
    def api_check(pid: str) -> Any:
        """{text, part?} — 식 글자를 읽어만 본다(추정하지 않는다). 다른 계산이 도는 중이면 기다리지 않고 `{busy: true}`."""
        data = body()
        text = data.get("text")
        if not isinstance(text, str) or len(text) > 4000:
            abort(400)
        try:
            return jsonify(session(pid).worker.call("check", wait=False, text=text, part=pick(data, "part", PART))["result"])
        except WorkerError as exc:
            if exc.kind == "busy":
                return jsonify(ok=None, busy=True)
            return worker_error(exc)

    @app.get("/api/p/<pid>/candidates")
    def api_candidates(pid: str) -> Any:
        """부품의 후보 — 그 부품에 묶인 추정 기록들의 요약과 채택한 기록(파일을 읽기만 한다)."""
        part = request.args.get("part", "")
        if not PART.fullmatch(part):
            abort(400)
        return jsonify(session(pid).candidates(part))

    @app.post("/api/p/<pid>/ident")
    def api_ident(pid: str) -> Any:
        """{part} — 항등식을 실측으로 검사한다(기록은 남기지 않는다)."""
        part = pick(body(), "part", PART)
        if part is None:
            abort(400)
        return run(pid, "ident", t("항등식 검사 {part}", part=part), part=part)

    @app.post("/api/p/<pid>/adopt")
    def api_adopt(pid: str) -> Any:
        """{record, part?} — 추정 기록을 채택한다. 블록 파일의 그 줄과 채택표가 바뀌고 바뀜 기록에 남는다."""
        data = body()
        record = pick(data, "record", RECORD)
        if record is None:
            abort(400)
        return run(pid, "adopt", t("채택 {record}", record=record), record=record, part=pick(data, "part", PART))

    @app.post("/api/p/<pid>/hs")
    def api_hs(pid: str) -> Any:
        """{model?} 과거 재현. {part, record, model?} 면 '이 후보로' — 그 부품을 기록의 식·계수로 바꿔 끼워 풀고 지금 파일로 푼 것과 견준다."""
        data = body()
        model = pick(data, "model", NAME)
        record, part = pick(data, "record", RECORD), pick(data, "part", PART)
        if record or part:
            if not (record and part):
                abort(400)
            return run(pid, "hs_swap", t("이 후보로 과거 재현 {record}", record=record), part=part, record=record, model=model)
        return run(pid, "hs", t("과거 재현 {model}", model=model or "").strip(), model=model)

    @app.post("/api/p/<pid>/diag")
    def api_diag(pid: str) -> Any:
        """{target} — 식 진단(CUSUM 포함). 부품이나 추정 기록. 분석 기록(an:)을 남긴다."""
        data = body()
        target = pick(data, "target", RECORD) if str(data.get("target", "")).startswith("est:") else pick(data, "target", PART)
        if target is None:
            abort(400)
        return run(pid, "an_diag", t("식 진단 {target}", target=target), target=target)

    @app.post("/api/p/<pid>/sim")
    def api_sim(pid: str) -> Any:
        data = body()
        scenario, model = text_arg(data, "scenario") or "base", text_arg(data, "model")
        return run(pid, "sim", t("전망 {scenario}", scenario=scenario), scenario=scenario, model=model)

    @app.post("/api/p/<pid>/cancel")
    def api_cancel(pid: str) -> Any:
        return jsonify(cancelled=session(pid).worker.cancel())

    # ---- 프로젝트: 기록·바뀜·파일(읽기만) ---------------------------------------------------------

    @app.get("/api/p/<pid>/records")
    def api_records(pid: str) -> Any:
        """작업 기록(`work/log.jsonl`의 최근 줄, 만든 순)."""
        try:
            limit = max(1, min(int(request.args.get("limit", "300")), 2000))
        except ValueError:
            abort(400)
        return jsonify(records=session(pid).records(limit))

    @app.get("/api/p/<pid>/record")
    def api_record(pid: str) -> Any:
        """기록 하나 — `record.json`·카드 `summary.md`·파일 목록·(추정이면) 실측·적합 시리즈."""
        found = session(pid).record(request.args.get("id"))
        if found is None:
            abort(404, description=t("없는 기록입니다: {id}", id=request.args.get("id", "")))
        return jsonify(found)

    @app.get("/api/p/<pid>/changes")
    def api_changes(pid: str) -> Any:
        return jsonify(changes=session(pid).changes())

    @app.get("/api/p/<pid>/change")
    def api_change(pid: str) -> Any:
        found = session(pid).change(request.args.get("id"))
        if found is None:
            abort(404, description=t("없는 바뀜 기록입니다: {id}", id=request.args.get("id", "")))
        return jsonify(found)

    @app.get("/api/p/<pid>/tree")
    def api_tree(pid: str) -> Any:
        """폴더 하나의 항목(`path` — 프로젝트 기준, 비우면 맨 위)."""
        try:
            return jsonify(path=request.args.get("path", ""), entries=session(pid).listdir(request.args.get("path", "")))
        except Outside:
            abort(403)
        except (FileNotFoundError, NotADirectoryError):
            abort(404, description=t("없는 폴더입니다"))
        except OSError as exc:
            return jsonify(error=str(exc)), 500

    @app.get("/api/p/<pid>/file")
    def api_file(pid: str) -> Any:
        """글 파일 하나의 내용(읽기만)."""
        try:
            return jsonify(session(pid).read_file(request.args.get("path", "")))
        except Outside:
            abort(403)
        except (FileNotFoundError, IsADirectoryError, PermissionError):
            abort(404, description=t("없는 파일입니다: {path}", path=request.args.get("path", "")))
        except OSError as exc:
            return jsonify(error=str(exc)), 500

    @app.get("/api/p/<pid>/raw")
    def api_raw(pid: str) -> Any:
        """그림 파일(png·jpg·gif·webp)의 내용 — 문서 속 그림."""
        try:
            data, kind = session(pid).raw_image(request.args.get("path", ""))
        except Outside:
            abort(403)
        except OSError:
            abort(404)
        return Response(data, content_type=kind)

    @app.get("/api/p/<pid>/view")
    def api_view(pid: str) -> Any:
        """지난번 화면 상태(연 탭·고른 탭·쓰던 식) — 닫았다 열면 이어진다."""
        return jsonify(view=state.config.view(session(pid).root))

    @app.post("/api/p/<pid>/view")
    def api_view_save(pid: str) -> Any:
        view = body().get("view")
        if not isinstance(view, dict):
            abort(400)
        if not state.config.set_view(session(pid).root, view):
            abort(413, description=t("화면 상태가 너무 큽니다"))
        return jsonify(ok=True)

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
        found = state.terminals.get(sid)
        if found is None:
            abort(404, description=t("끝난 터미널입니다"))
        return found

    def term_size(data: dict[str, Any]) -> tuple[int, int]:
        cols, rows = data.get("cols", 80), data.get("rows", 24)
        if not all(isinstance(v, int) and not isinstance(v, bool) and 1 <= v <= 1000 for v in (cols, rows)):
            abort(400)
        return cols, rows

    @app.post("/api/term/open")
    def api_term_open() -> Any:
        """프로젝트 폴더에서 셸을 띄운다(이미 돌고 있으면 그것). `{p, cols, rows}` → `{id, shell, cwd}`"""
        term_guard()
        data = body()
        s = state.session(data.get("p"))
        if s is None:
            abort(409, description=t("연 프로젝트가 없습니다"))
        cols, rows = term_size(data)
        try:
            opened = state.terminals.open(s.id, s.root, None, cols, rows, 0)
        except OSError as exc:
            return jsonify(error=t("셸을 시작하지 못했습니다 ({error})", error=exc)), 500
        return jsonify(id=opened.id, shell=terminal.shell_label(opened.exe), cwd=s.root)

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
