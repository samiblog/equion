"""로컬 서버 — 화면(web/)과 앱 사이. 127.0.0.1에서만 듣는다.

보호 장치는 Lectern 0.69.1(`cd7fb26`)의 `lectern/server.py`에서 가져왔다(desk/THIRD-PARTY-NOTICES.md):

- 다른 도메인 이름으로 들어온 요청은 거절한다(DNS 리바인딩).
- 창 모드에서는 pywebview가 준 토큰(`X-Token`)이 있어야 `/api/`를 쓴다.
- POST는 JSON 본문만 받는다(다른 사이트의 폼이 사전 확인 없이 보내지 못하게).
- 터미널은 페이지에 실은 비밀값(`X-Term`)과 요청을 보낸 페이지(Origin)까지 확인한다 — 셸로 가는 길은 사용자의 키 입력과 단추뿐이다.
- 프로젝트 파일은 그 폴더 안의 것만 읽는다(`ProjectSession.resolve`). 화면은 파일을 고치지 않는다 — 고치는 것은 작업 프로세스의 명령뿐이다.

경로: `/api/state`·`/api/open`·`/api/example`·`/api/tabs/*`·`/api/settings`·`/api/events`(알림 긴 폴링) ·
프로젝트마다 `/api/p/<탭 id>/overview·est·check·candidates·ident·adopt·hs(·run·replay·view·series)·trace·diag·sim·data(·build·use·add·diff·preview·define)·series·analyses·an(·keep)·assembly·model/define·block/define·text(/check·/write)·scripts·script(/plan·/run·/new)·run/view·todo·reestimate·cancel·records·record·changes·change·tree·file·raw·view` · `/api/term/*`.
"""
from __future__ import annotations

import re
import shutil
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
                .replace("{{THEME}}", str(client.get("theme", "auto")))
                .replace("{{TERM_FOLLOW}}", "false" if client.get("term_follow") is False else "true"))
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
                "terminal": state.terminals.available, "can_pick": state.pick_folder is not None, "can_pick_file": state.pick_file is not None,
                "recent": state.config.get("recent") or [], "client": state.config.client(), "seq": state.feed.seq,
                "claude": shutil.which("claude") is not None}      # Claude Code 가 이 PC 에 있나 — 없으면 '맡기기·제안 받기'가 설치를 안내한다

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

    def documents() -> Path:
        """예제와 받은 묶음을 두는 곳 — 문서 폴더의 Equion(시험은 EQUION_DESK_DOCUMENTS 로 바꾼다)."""
        import os

        return Path(os.environ.get("EQUION_DESK_DOCUMENTS") or (Path.home() / "Documents")) / "Equion"

    @app.post("/api/example")
    def api_example() -> Any:
        """예제 프로젝트(가상 분기 모형)를 문서 폴더 아래에 새로 만들어 연다."""
        import subprocess

        from . import runtime

        base = documents()
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

    @app.post("/api/bundle/open")
    def api_bundle_open() -> Any:
        """{zip?} — 묶음(zip)을 문서 폴더의 Equion/<이름> 에 풀어 연다(`equion bundle open`). zip 이 없으면 파일 고르기(창 모드)."""
        import subprocess

        from . import runtime

        zip_path = text_arg(body(), "zip", 1024)
        if zip_path is None:
            if state.pick_file is None:
                abort(501, description=t("파일 고르기는 앱 창에서만 됩니다"))
            zip_path = state.pick_file("bundle")
            if not zip_path:
                return jsonify(id=None)
        if not zip_path.lower().endswith(".zip") or not Path(zip_path).is_file():
            abort(400, description=t("묶음(zip) 파일이 아닙니다: {name}", name=Path(zip_path).name))
        base = documents()
        base.mkdir(parents=True, exist_ok=True)
        stem = re.sub(r"[^A-Za-z0-9_\-]+", "_", Path(zip_path).stem).strip("_") or "bundle"
        dest, n = base / stem, 2
        while dest.exists():
            dest, n = base / f"{stem}_{n}", n + 1
        r = subprocess.run([runtime.python_exe(), "-I", "-X", "utf8", "-m", "equion", "bundle", "open", zip_path, str(dest)],
                           env=runtime.clean_env(), capture_output=True, text=True, encoding="utf-8",
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if r.returncode != 0:
            return jsonify(error=(r.stderr or r.stdout).strip().replace("equion: 오류: ", "")), 422
        return open_folder(str(dest))

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

    # ---- 프로젝트: 자료 작업대 · 분석 탭 -----------------------------------------------------------

    VINTAGE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_\-]{0,60}")
    SERIES = re.compile(r"[^\s:/\\]{1,80}")
    AN_RECORD = re.compile(r"an:[A-Za-z0-9][A-Za-z0-9_\-]{0,120}")

    def ask(pid: str, op: str, **args: Any) -> Any:
        """작업 프로세스에 묻는다(읽기 — 작업 줄에 올리지 않는다)."""
        try:
            return jsonify(session(pid).worker.call(op, **args)["result"])
        except WorkerError as exc:
            return worker_error(exc)

    @app.get("/api/p/<pid>/data")
    def api_data(pid: str) -> Any:
        """자료의 세 층 — 원자료와 틀 · 시리즈(만드는 법·구간·쓰는 식) · 회차 목록 · 지금 회차가 낡았는지. 계산하지 않는다."""
        return ask(pid, "data")

    @app.get("/api/p/<pid>/series")
    def api_series(pid: str) -> Any:
        """시리즈 하나 — 지금 회차의 값·값의 종류와 내력."""
        name = request.args.get("name", "")
        if not SERIES.fullmatch(name):
            abort(400)
        return ask(pid, "series", name=name)

    @app.get("/api/p/<pid>/data/diff")
    def api_data_diff(pid: str) -> Any:
        """두 회차의 차이(새 기간·개정)와 바뀐 시리즈를 쓰는 식·모형. `a`·`b`가 없으면 지금 회차와 그 앞."""
        a, b = request.args.get("a") or None, request.args.get("b") or None
        if any(v is not None and not VINTAGE.fullmatch(v) for v in (a, b)):
            abort(400)
        return ask(pid, "data_diff", a=a, b=b)

    @app.post("/api/p/<pid>/data/build")
    def api_data_build(pid: str) -> Any:
        """자료 만들기 — 새 회차(내용이 같으면 만들지 않는다). 지금 회차는 바뀌지 않는다."""
        body()
        return run(pid, "data_build", t("자료 만들기"))

    @app.post("/api/p/<pid>/data/use")
    def api_data_use(pid: str) -> Any:
        """{vintage} — 이 회차로 바꾸기(`equion.toml [data] vintage`). 바뀜 기록에 남는다."""
        vintage = pick(body(), "vintage", VINTAGE)
        if vintage is None:
            abort(400)
        return run(pid, "data_use", t("회차 바꾸기 {vintage}", vintage=vintage), vintage=vintage)

    @app.post("/api/p/<pid>/data/add")
    def api_data_add(pid: str) -> Any:
        """원자료 넣기 — `{inbox: 파일 이름}`이면 받은 상자(`DATA/raw/inbox/`)의 그 파일을, 없으면 파일 고르기 대화상자를 띄운다(창 모드).
        `source`를 주면 그 출처가 이 파일을 읽게 한다(틀이 맞을 때만). 화면이 아무 경로나 보내 복사시키지는 못한다."""
        data = body()
        s = session(pid)
        source = pick(data, "source", NAME)
        inbox = text_arg(data, "inbox", 200)
        from_inbox = False
        if inbox is not None:
            try:
                path = s.resolve(f"DATA/raw/inbox/{inbox}")
            except Outside:
                abort(403)
            if not path.is_file() or path.parent.name != "inbox":
                abort(404, description=t("받은 상자에 없는 파일입니다: {name}", name=inbox))
            chosen = str(path)
            from_inbox = True
        else:
            if state.pick_file is None:
                abort(501, description=t("파일 고르기는 앱 창에서만 됩니다 — 파일을 DATA/raw/inbox/ 에 놓으면 받은 상자에 뜹니다"))
            chosen = state.pick_file()
            if not chosen:
                return jsonify(result=None)
        return run(pid, "data_add", t("원자료 넣기 {name}", name=Path(chosen).name), path=chosen, source=source, inbox=from_inbox)

    FRAME_KEYS = ("sheet", "header_row", "unit_row", "time_col", "missing", "thousands", "freq", "time_axis", "time_row", "name_col", "unit_col")
    SERIES_KEYS = ("column", "unit", "desc", "convert", "denton", "seas", "scale", "fill")

    def raw_file(pid: str, data: dict[str, Any], inbox: bool = False) -> str:
        """원자료 파일 하나(프로젝트 기준 경로) — `DATA/raw/` 아래의 것만(inbox 면 받은 상자도). 화면이 다른 파일을 읽히지 못한다."""
        value = text_arg(data, "file", 400)
        if value is None:
            abort(400)
        s = session(pid)
        try:
            path = s.resolve(value)
        except Outside:
            abort(403)
        rel = path.relative_to(Path(s.root).resolve()).as_posix()
        folder = rel.rsplit("/", 1)[0] if "/" in rel else ""
        if not path.is_file() or folder.lower() not in ("data/raw", *(("data/raw/inbox",) if inbox else ())):
            abort(404, description=t("원자료 폴더(DATA/raw/)에 없는 파일입니다: {name}", name=value))
        return rel

    def frame_arg(data: dict[str, Any]) -> dict[str, Any] | None:
        """불러오기 틀 — 아는 키와 맞는 형식만. 없으면 None(그 출처의 틀로)."""
        raw = data.get("frame")
        if raw is None:
            return None
        if not isinstance(raw, dict):
            abort(400)
        out: dict[str, Any] = {}
        for key in FRAME_KEYS:
            if key not in raw:
                continue
            value = raw[key]
            if key == "missing":
                if not isinstance(value, list) or len(value) > 12 or any(not isinstance(x, str) or len(x) > 12 for x in value):
                    abort(400)
            elif key in ("unit_row", "time_row"):
                if value in (None, ""):
                    value = ""
                elif isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 1_000_000:
                    abort(400)
            elif key == "header_row":
                if value in (None, ""):
                    value = ""
                elif isinstance(value, list):
                    if not 0 < len(value) <= 6 or any(isinstance(x, bool) or not isinstance(x, int) or not 0 < x <= 1_000_000 for x in value):
                        abort(400)
                elif isinstance(value, str):
                    if not re.fullmatch(r"\d{1,7}(\s*[,\-:~]\s*\d{1,7}){0,5}", value.strip()):
                        abort(400, description=t("열 이름 줄은 줄 번호 — 여러 줄이면 3,4"))
                elif isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 1_000_000:
                    abort(400)
            elif key == "time_axis":
                if value in (None, ""):
                    value = ""
                elif value not in ("rows", "columns"):
                    abort(400)
            elif key == "name_col" and isinstance(value, list):
                if len(value) > 4 or any(not isinstance(x, str) or not re.fullmatch(r"[A-Za-z]{1,3}|\d{1,4}", x) for x in value):
                    abort(400)
            elif value is None:
                value = ""
            elif isinstance(value, bool) or not isinstance(value, (str, int)) or len(str(value)) > 80:
                abort(400)
            out[key] = value
        return out

    def series_arg(value: Any, many: bool = True) -> dict[str, Any] | None:
        """시리즈 정의들 `{이름: {column, unit, desc, convert, denton, seas, scale, fill}}`(many 가 아니면 그 안쪽 하나). 이름과 값의 검사는 패키지가 한다."""
        if value is None:
            return None
        items = value if many else {"_": value}
        if not isinstance(items, dict) or len(items) > 400:
            abort(400)
        out: dict[str, Any] = {}
        for name, spec in items.items():
            if not isinstance(name, str) or not 1 <= len(name) <= 80 or not isinstance(spec, dict):
                abort(400)
            clean: dict[str, Any] = {}
            for key in SERIES_KEYS:
                if key not in spec:
                    continue
                v = spec[key]
                if v is not None and (isinstance(v, bool) or not isinstance(v, (str, int, float)) or len(str(v)) > 200):
                    abort(400)
                clean[key] = v
            if not clean.get("column"):
                abort(400, description=t("어느 열을 읽을지 없습니다: {name}", name=name))
            out[name] = clean
        return out if many else out["_"]

    @app.post("/api/p/<pid>/data/preview")
    def api_data_preview(pid: str) -> Any:
        """{file, frame?, rows?, series?} — 원자료 미리보기(읽은 그대로의 줄 · 그 틀로 읽은 것 · 이 파일을 읽는 출처와 짝지은 시리즈).
        `series`(열 하나와 변환)를 주면 그 열을 만들어 본 값도. 아무것도 쓰지 않고 기록도 남기지 않는다."""
        data = body()
        rows = data.get("rows", 40)
        if isinstance(rows, bool) or not isinstance(rows, int) or not 1 <= rows <= 400:
            abort(400)
        return ask(pid, "data_preview", file=raw_file(pid, data, inbox=True), frame=frame_arg(data), rows=rows,
                   series=series_arg(data.get("series"), many=False))

    @app.post("/api/p/<pid>/data/define")
    def api_data_define(pid: str) -> Any:
        """{source, file, frame, desc?, series, replace?, dry?} — 정의 쓰기(`equion data define`): 출처(불러오기 틀)와 시리즈를 `series.toml`에.
        `dry` 면 쓰지 않고 무엇이 바뀌는지(차이)만. 쓰기 전에 패키지가 검사한다 — 문제가 있으면 아무것도 쓰지 않는다."""
        data = body()
        source = pick(data, "source", NAME)
        if source is None:
            abort(400)
        args = dict(source=source, file=raw_file(pid, data), frame=frame_arg(data), desc=text_arg(data, "desc", 200),
                    series=series_arg(data.get("series")), replace=data.get("replace") is True)
        if data.get("dry") is True:
            return ask(pid, "data_define", dry=True, **args)
        return run(pid, "data_define", t("정의 저장 {source}", source=source), **args)

    @app.get("/api/p/<pid>/analyses")
    def api_analyses(pid: str) -> Any:
        """분석 등록부 — 분석마다 대상 종류·옵션·만드는 것, 그리고 대상으로 고를 이름들. 화면의 폼이 여기서 나온다."""
        return ask(pid, "analyses")

    @app.post("/api/p/<pid>/an")
    def api_an(pid: str) -> Any:
        """{analysis, target, options?, smpl?, name?} — 등록부의 분석 하나를 돌려 기록(an:)을 남긴다. 옵션은 작업 프로세스가 등록부대로 가린다."""
        data = body()
        analysis, target = pick(data, "analysis", NAME), text_arg(data, "target", 400)
        options = data.get("options") or {}
        if analysis is None or target is None or not isinstance(options, dict) or len(options) > 30 or not all(
                isinstance(k, str) and len(k) <= 40 and (v is None or isinstance(v, (str, int, float, bool))) and len(str(v)) <= 200 for k, v in options.items()):
            abort(400)
        return run(pid, "an", t("분석 {analysis} {target}", analysis=analysis, target=target if len(target) <= 30 else target[:28] + "…"),
                   analysis=analysis, target=target, options=options, smpl=text_arg(data, "smpl", 60), name=pick(data, "name", NAME))

    @app.post("/api/p/<pid>/an/keep")
    def api_an_keep(pid: str) -> Any:
        """{record, name?, replace?} — 분석 기록을 남긴다: 만드는 분석은 정의로, 부품을 내는 분석은 식 후보로. 바뀜 기록에 남는다."""
        data = body()
        record = pick(data, "record", AN_RECORD)
        if record is None:
            abort(400)
        return run(pid, "an_keep", t("남기기 {record}", record=record), record=record, name=pick(data, "name", NAME), replace=data.get("replace") is True)

    # ---- 프로젝트: 모형 작업대(조립·과거 재현·원인 따라가기) · 흐름 화면 · 정의 고치기 ----------------------

    HS_RECORD = re.compile(r"hs:[A-Za-z0-9][A-Za-z0-9_\-]{0,120}")
    RUN_RECORD = re.compile(r"run:[A-Za-z0-9][A-Za-z0-9_\-.]{0,160}")
    EST_RECORD = re.compile(r"est:[A-Za-z0-9][A-Za-z0-9_\-]{0,120}")
    PERIOD = re.compile(r"[A-Za-z0-9+\-]{1,20}")
    MODES = frozenset({"dynamic", "static", "fit"})
    TEXT_LIMIT = 2_000_000

    def names_arg(data: dict[str, Any], key: str, pattern: Any, limit: int = 200) -> list[str] | None:
        """이름들의 목록 — 없으면 None(그 키는 그대로), 빈 목록이면 지운다는 뜻."""
        value = data.get(key)
        if value is None:
            return None
        if not isinstance(value, list) or len(value) > limit or any(not isinstance(x, str) or not pattern.fullmatch(x) for x in value):
            abort(400, description=t("받을 수 없는 값입니다: {key}", key=key))
        return value

    def definition_path(pid: str, data: dict[str, Any]) -> str:
        value = text_arg(data, "path", 400)
        if value is None:
            abort(400)
        s = session(pid)
        try:
            path = s.resolve(value)
        except Outside:
            abort(403)
        if not path.is_file():
            abort(404)
        return path.relative_to(Path(s.root).resolve()).as_posix()

    def script_path(pid: str, data: dict[str, Any]) -> str:
        rel = definition_path(pid, data)
        if not rel.lower().endswith(".eqs"):
            abort(400, description=t("스크립트(.eqs)가 아닙니다: {name}", name=rel))
        return rel

    def sets_arg(data: dict[str, Any]) -> dict[str, str] | None:
        raw = data.get("sets")
        if raw is None:
            return None
        if not isinstance(raw, dict) or len(raw) > 40 or any(not isinstance(k, str) or not NAME.fullmatch(k) or not isinstance(v, str) or len(v) > 200
                                                             for k, v in raw.items()):
            abort(400)
        return {k: v for k, v in raw.items() if v != ""} or None

    @app.get("/api/p/<pid>/assembly")
    def api_assembly(pid: str) -> Any:
        """조립 보기 — 모형의 블록·식, 내생·외생, 블록 사이의 연결, 풀이 블록, 문제. 계산하지 않는다."""
        model = request.args.get("model") or None
        if model is not None and not NAME.fullmatch(model):
            abort(400)
        return ask(pid, "assembly", model=model)

    @app.post("/api/p/<pid>/model/define")
    def api_model_define(pid: str) -> Any:
        """{name, blocks?, include?, exclude?, desc?, dry?} — 모형 정의 쓰기(`equion model define`). dry 면 쓰지 않고 차이만."""
        data = body()
        name = pick(data, "name", NAME)
        if name is None:
            abort(400)
        desc = data.get("desc")
        if desc is not None and (not isinstance(desc, str) or len(desc) > 200):
            abort(400)
        args = dict(name=name, blocks=names_arg(data, "blocks", NAME), include=names_arg(data, "include", NAME), exclude=names_arg(data, "exclude", PART),
                    desc=desc)
        if data.get("dry") is True:
            return ask(pid, "model_define", dry=True, **args)
        return run(pid, "model_define", t("모형 정의 {name}", name=name), **args)

    @app.post("/api/p/<pid>/block/define")
    def api_block_define(pid: str) -> Any:
        """{name, desc?, dry?} — 블록 더하기(`equion block define`): 빈 블록 파일을 함께 만든다. dry 면 쓰지 않고 차이만."""
        data = body()
        name = pick(data, "name", NAME)
        if name is None:
            abort(400)
        desc = text_arg(data, "desc", 200)
        if data.get("dry") is True:
            return ask(pid, "block_define", name=name, desc=desc, dry=True)
        return run(pid, "block_define", t("블록 정의 {name}", name=name), name=name, desc=desc)

    @app.post("/api/p/<pid>/text/check")
    def api_text_check(pid: str) -> Any:
        """{path, text} — 정의 파일의 글을 읽어만 본다(블록 파일은 줄마다 식 문법, TOML 은 문법과 설정). 쓰지 않는다. 바쁘면 기다리지 않는다."""
        data = body()
        text = data.get("text")
        if not isinstance(text, str) or len(text) > TEXT_LIMIT:
            abort(400)
        try:
            return jsonify(session(pid).worker.call("check_text", wait=False, path=definition_path(pid, data), text=text)["result"])
        except WorkerError as exc:
            if exc.kind == "busy":
                return jsonify(busy=True, problems=[])
            return worker_error(exc)

    @app.post("/api/p/<pid>/text/write")
    def api_text_write(pid: str) -> Any:
        """{path, text} — 정의 파일을 글로 고쳐 쓴다. 바뀜 기록이 지켜보는 정의 파일만(작업 프로세스가 가린다), 바뀜 기록에 'Desk'로 남는다."""
        data = body()
        text = data.get("text")
        if not isinstance(text, str) or len(text) > TEXT_LIMIT:
            abort(400)
        rel = definition_path(pid, data)
        return run(pid, "write_text", t("고침 {path}", path=rel), path=rel, text=text)

    @app.post("/api/p/<pid>/hs/run")
    def api_hs_run(pid: str) -> Any:
        """{target?, start?, end?, mode?, vs?, name?} — 과거 재현(`equion hs`): 모형이나 블록, 범위, 방식(dynamic·static·fit), 견줄 기록."""
        data = body()
        target, mode = pick(data, "target", NAME), pick(data, "mode", allowed=MODES)
        return run(pid, "hs", t("과거 재현 {model}", model=target or "").strip(), model=target, start=pick(data, "start", PERIOD), end=pick(data, "end", PERIOD),
                   mode=mode, vs=pick(data, "vs", HS_RECORD), name=pick(data, "name", NAME))

    @app.post("/api/p/<pid>/hs/replay")
    def api_hs_replay(pid: str) -> Any:
        """{record} — 그때 그대로 다시(`equion hs --replay`)."""
        record = pick(body(), "record", HS_RECORD)
        if record is None:
            abort(400)
        return run(pid, "hs_replay", t("그때 그대로 다시 {record}", record=record), record=record)

    @app.get("/api/p/<pid>/hs/view")
    def api_hs_view(pid: str) -> Any:
        """과거 재현 기록 하나 — 변수마다 적합도, 기간마다 풀이 상태, 어느 계수로 풀었나."""
        record = request.args.get("id", "")
        if not HS_RECORD.fullmatch(record):
            abort(400)
        return ask(pid, "hs_view", record=record)

    @app.get("/api/p/<pid>/hs/series")
    def api_hs_series(pid: str) -> Any:
        """과거 재현 기록의 변수들(`names=A,B`) — 풀린 값과 실측."""
        record, names = request.args.get("id", ""), [n for n in request.args.get("names", "").split(",") if n]
        if not HS_RECORD.fullmatch(record) or not names or len(names) > 40 or any(not SERIES.fullmatch(n) for n in names):
            abort(400)
        return ask(pid, "hs_series", record=record, names=names)

    @app.get("/api/p/<pid>/trace")
    def api_trace(pid: str) -> Any:
        """원인 따라가기 — 변수의 식이 쓰는 입력마다 이 과거 재현에서의 오차(내생)·실측(외생). 계산하지 않는다."""
        record, name = request.args.get("id", ""), request.args.get("name", "")
        if not HS_RECORD.fullmatch(record) or not SERIES.fullmatch(name):
            abort(400)
        return ask(pid, "trace", record=record, name=name)

    @app.get("/api/p/<pid>/scripts")
    def api_scripts(pid: str) -> Any:
        return ask(pid, "scripts")

    @app.post("/api/p/<pid>/script/plan")
    def api_script_plan(pid: str) -> Any:
        """{path, sets?, from?} — 미리보기(`equion run … --dry-run`): 단계마다 실행할 줄과 바꾸는 파일. 기록을 남기지 않는다."""
        data = body()
        return ask(pid, "script_plan", path=script_path(pid, data), sets=sets_arg(data), from_step=text_arg(data, "from", 120))

    @app.post("/api/p/<pid>/script/run")
    def api_script_run(pid: str) -> Any:
        """{path, sets?, from?} — 스크립트 실행(`equion run x.eqs`). 단계가 끝날 때마다 작업 줄에 알린다. 실행 기록(run:)을 남긴다."""
        data = body()
        rel = script_path(pid, data)
        return run(pid, "script_run", t("스크립트 {name}", name=rel.rsplit("/", 1)[-1]), path=rel, sets=sets_arg(data), from_step=text_arg(data, "from", 120))

    @app.get("/api/p/<pid>/run/view")
    def api_run_view(pid: str) -> Any:
        record = request.args.get("id", "")
        if not RUN_RECORD.fullmatch(record):
            abort(400)
        return ask(pid, "run_view", record=record)

    @app.post("/api/p/<pid>/script/new")
    def api_script_new(pid: str) -> Any:
        """{name, records, title?} — 작업 기록에서 스크립트 초안(`equion script new`): `FLOWS/<이름>.eqs`."""
        data = body()
        name = pick(data, "name", NAME)
        recs = data.get("records")
        if name is None or not isinstance(recs, list) or not 1 <= len(recs) <= 60 or any(not isinstance(r, str) or not re.fullmatch(r"[a-z]+:[A-Za-z0-9_\-.]{1,160}", r) for r in recs):
            abort(400)
        return run(pid, "script_new", t("스크립트 초안 {name}", name=name), name=name, records=recs, title=text_arg(data, "title", 120))

    @app.get("/api/p/<pid>/todo")
    def api_todo(pid: str) -> Any:
        """지금 회차가 아닌 자료로 계산한 것(채택한 계수·가장 최근의 과거 재현·전망) — 무엇이 낡았는지만, 다시 계산하지 않는다."""
        return ask(pid, "todo")

    @app.post("/api/p/<pid>/reestimate")
    def api_reestimate(pid: str) -> Any:
        """{name?} — 채택한 식을 지금 자료로 다시 추정(`equion est --adopted`): 기록만 남기고 옛 계수와 견줄 재료를 돌려준다.
        {parts: ["블록:목표=est:기록", …]} — 사람이 고른 식의 새 기록을 채택한다."""
        data = body()
        parts = data.get("parts")
        if parts is not None:
            if not isinstance(parts, list) or not 1 <= len(parts) <= 400 or any(
                    not isinstance(x, str) or not PART.fullmatch(x.partition("=")[0]) or not EST_RECORD.fullmatch(x.partition("=")[2]) for x in parts):
                abort(400)
            return run(pid, "reestimate", t("새 계수 채택 {n}개", n=len(parts)), parts=parts)
        name = pick(data, "name", NAME)
        return run(pid, "reestimate", t("다시 추정 {name}", name=name or "").strip(), name=name, adopt="never")

    # ---- 프로젝트: 전망 작업대 · 보기 · 보고서 · 엑셀 ---------------------------------------------------

    SIM_RECORD = re.compile(r"sim:[A-Za-z0-9][A-Za-z0-9_\-.]{0,120}")
    ANY_RECORD = re.compile(r"(?:est|hs|sim|an|data):[A-Za-z0-9][A-Za-z0-9_\-.]{0,160}")
    RANGE = re.compile(r"[A-Za-z0-9+\-]{0,20}:[A-Za-z0-9+\-]{0,20}")
    SHOWS = frozenset({"level", "qoq", "yoy", "annual", "diff"})
    NUMBER = re.compile(r"[-+0-9.,eE ]{0,40}")

    @app.get("/api/p/<pid>/forecast")
    def api_forecast(pid: str) -> Any:
        """전망 한눈에 — 모형과 전망 구간, 가정 표(외생 × 구간), 보정항 규칙, 시나리오, 전망 기록, 보기. 계산하지 않는다."""
        model = request.args.get("model") or None
        if model is not None and not NAME.fullmatch(model):
            abort(400)
        return ask(pid, "forecast", model=model)

    @app.post("/api/p/<pid>/assume")
    def api_assume(pid: str) -> Any:
        """{name, columns, rows: {기간: {변수: 글}}} — 가정 표를 쓴다(`ASSUMPTIONS/<이름>.csv`). 바뀜 기록에 'Desk'로 남는다."""
        data = body()
        name, rows = pick(data, "name", NAME), data.get("rows")
        columns = names_arg(data, "columns", SERIES, 400)
        if name is None or not columns or not isinstance(rows, dict) or len(rows) > 600:
            abort(400)
        for period, cells in rows.items():
            if not isinstance(period, str) or not PERIOD.fullmatch(period) or not isinstance(cells, dict) or len(cells) > 400:
                abort(400)
            for col, value in cells.items():
                if not isinstance(col, str) or not SERIES.fullmatch(col) or not isinstance(value, str) or not NUMBER.fullmatch(value):
                    abort(400, description=t("{period} {name}: 숫자가 아닙니다", period=str(period)[:20], name=str(col)[:40]))
        return run(pid, "assume", t("가정 표 {name}", name=name), name=name, columns=columns, rows=rows)

    @app.post("/api/p/<pid>/sim/run")
    def api_sim_run(pid: str) -> Any:
        """{scenarios?, model?, range?, vintage?, vs?} — 전망·시나리오(`equion sim`): 고른 것을 차례로(작업 하나). 기록(sim:)을 남긴다."""
        data = body()
        scenarios = names_arg(data, "scenarios", NAME, 12) or ["base"]
        return run(pid, "sim_run", t("전망 {scenario}", scenario=" · ".join(scenarios)), scenarios=scenarios, model=pick(data, "model", NAME),
                   range_=pick(data, "range", RANGE), vintage=pick(data, "vintage", VINTAGE), vs=pick(data, "vs", SIM_RECORD))

    @app.get("/api/p/<pid>/sim/view")
    def api_sim_view(pid: str) -> Any:
        """전망 기록 하나 — 수준·값의 종류·전기비·전년동기비·연간·기준선 대비."""
        record = request.args.get("id", "")
        if not SIM_RECORD.fullmatch(record):
            abort(400)
        return ask(pid, "sim_view", record=record)

    @app.get("/api/p/<pid>/views")
    def api_views(pid: str) -> Any:
        return ask(pid, "views")

    @app.post("/api/p/<pid>/view/define")
    def api_view_define(pid: str) -> Any:
        """{name, series, show?, title?} — 이 보기 저장(`equion view define`): `VIEWS/<이름>.toml`."""
        data = body()
        name, series = pick(data, "name", NAME), names_arg(data, "series", SERIES, 200)
        if name is None or not series:
            abort(400, description=t("보기 이름(영문·숫자·_)과 시리즈가 있어야 합니다"))
        return run(pid, "view_define", t("보기 {name}", name=name), name=name, series=series, show=pick(data, "show", allowed=SHOWS) or "level",
                   title=text_arg(data, "title", 120))

    @app.get("/api/p/<pid>/reports")
    def api_reports(pid: str) -> Any:
        return ask(pid, "reports")

    @app.post("/api/p/<pid>/report/new")
    def api_report_new(pid: str) -> Any:
        """{name, title?, from?} — 새 보고서(`equion report new`). from 은 지난 보고서(그 구역들을 새 기록으로 바꿔 낄 틀)."""
        data = body()
        name = pick(data, "name", NAME)
        if name is None:
            abort(400, description=t("보고서 이름이 있어야 합니다(영문·숫자·_·-)"))
        return run(pid, "report_new", t("새 보고서 {name}", name=name), name=name, title=text_arg(data, "title", 160), from_report=pick(data, "from", NAME))

    @app.post("/api/p/<pid>/report/add")
    def api_report_add(pid: str) -> Any:
        """{report, record, rows?, show?, annual?, digits?, title?, chart?, under?} — 보고서로 보내기(`equion report add`)."""
        data = body()
        report, record = pick(data, "report", NAME), pick(data, "record", ANY_RECORD)
        digits = data.get("digits")
        if report is None or record is None or (digits is not None and (not isinstance(digits, int) or isinstance(digits, bool) or not 0 <= digits <= 8)):
            abort(400)
        return run(pid, "report_add", t("보고서로 {report}", report=report), report=report, record=record, rows=names_arg(data, "rows", SERIES, 200),
                   show=pick(data, "show", allowed=SHOWS - {"annual"}) or "level", annual=data.get("annual") is True, digits=digits,
                   title=text_arg(data, "title", 160), chart=data.get("chart") is True, under=text_arg(data, "under", 160))

    @app.get("/api/p/<pid>/report/check")
    def api_report_check(pid: str) -> Any:
        """보고서 검사 — 구역마다 없는 기록 · 더 새 기록 · 낡음 · 손으로 고침. 고치지 않는다."""
        report = request.args.get("report", "")
        if not NAME.fullmatch(report):
            abort(400)
        return ask(pid, "report_check", report=report)

    @app.post("/api/p/<pid>/report/update")
    def api_report_update(pid: str) -> Any:
        """{report, region?, dry?, force?} — 새 기록으로 바꾸기(`equion report update`). dry 면 바꾸지 않고 구역마다의 차이만."""
        data = body()
        report, region = pick(data, "report", NAME), data.get("region")
        if report is None or (region is not None and (not isinstance(region, int) or isinstance(region, bool) or not 1 <= region <= 500)):
            abort(400)
        if data.get("dry") is True:
            return ask(pid, "report_update", report=report, region=region, dry=True, force=data.get("force") is True)
        return run(pid, "report_update", t("보고서 고침 {report}", report=report), report=report, region=region, force=data.get("force") is True)

    @app.post("/api/p/<pid>/export")
    def api_export(pid: str) -> Any:
        """{records, name} — 엑셀로(`equion export … --xlsx`): 값·값의 종류·출처 시트를 `exports/<이름>.xlsx`로."""
        data = body()
        name, records = pick(data, "name", NAME), names_arg(data, "records", ANY_RECORD, 40)
        if name is None or not records:
            abort(400, description=t("파일 이름(영문·숫자·_·-)과 기록이 있어야 합니다"))
        return run(pid, "export", t("엑셀로 {name}", name=name), name=name, records=records)

    @app.post("/api/p/<pid>/sim")
    def api_sim(pid: str) -> Any:
        data = body()
        scenario, model = text_arg(data, "scenario") or "base", text_arg(data, "model")
        return run(pid, "sim", t("전망 {scenario}", scenario=scenario), scenario=scenario, model=model)

    # ---- 프로젝트: 제안 · 되돌리기 · 고정과 메모 ---------------------------------------------------------

    PROP_ID = re.compile(r"prop:[A-Za-z0-9][A-Za-z0-9_\-]{0,60}")
    CHANGE = re.compile(r"h\d{1,8}")
    MARKED = re.compile(r"(?:est|hs|sim|an|run):[A-Za-z0-9][A-Za-z0-9_\-.]{0,160}")

    @app.get("/api/p/<pid>/proposals")
    def api_proposals(pid: str) -> Any:
        """제안 목록(만든 순) — 열림·적용·버림. 열린 제안은 만든 뒤 바뀐 파일(낡음)과 함께. 파일을 읽기만 한다."""
        return jsonify(proposals=session(pid).proposals())

    @app.get("/api/p/<pid>/proposal")
    def api_proposal(pid: str) -> Any:
        """제안 하나 — 지금 파일 대비 바뀔 내용의 차이, 까닭, 미리 계산한 기록."""
        rid = request.args.get("id", "")
        if not PROP_ID.fullmatch(rid):
            abort(400)
        return ask(pid, "proposal", name=rid[5:])

    @app.post("/api/p/<pid>/proposal/apply")
    def api_proposal_apply(pid: str) -> Any:
        """{id, force?} — 제안 적용(`equion propose apply`). 만든 뒤 파일이 바뀌었으면(낡음) force 일 때만."""
        data = body()
        rid = pick(data, "id", PROP_ID)
        if rid is None:
            abort(400)
        return run(pid, "proposal_apply", t("제안 적용 {name}", name=rid[5:]), name=rid[5:], force=data.get("force") is True)

    @app.post("/api/p/<pid>/proposal/drop")
    def api_proposal_drop(pid: str) -> Any:
        """{id, why?} — 제안 버림(`equion propose drop`). 파일은 그대로."""
        data = body()
        rid = pick(data, "id", PROP_ID)
        if rid is None:
            abort(400)
        return run(pid, "proposal_drop", t("제안 버림 {name}", name=rid[5:]), name=rid[5:], why=text_arg(data, "why", 300))

    @app.post("/api/p/<pid>/revert")
    def api_revert(pid: str) -> Any:
        """{change, files?} — 되돌리기(`equion history revert`): 그 바뀜 앞의 내용으로 다시 쓴다. files 를 주면 그 파일만."""
        data = body()
        change, files = pick(data, "change", CHANGE), data.get("files")
        if change is None:
            abort(400)
        if files is not None and (not isinstance(files, list) or not 1 <= len(files) <= 60 or any(
                not isinstance(f, str) or not 0 < len(f) <= 300 or "\\" in f or f.startswith("/") or ".." in f.split("/") for f in files)):
            abort(400)
        return run(pid, "revert", t("되돌리기 {change}", change=change), change=change, files=files)

    @app.post("/api/p/<pid>/mark")
    def api_mark(pid: str) -> Any:
        """{record, pinned?, memo?} — 기록에 고정·메모(`equion work pin·memo`). 기록은 그대로, marks.json 에만."""
        data = body()
        record, pinned, memo = pick(data, "record", MARKED), data.get("pinned"), data.get("memo")
        if record is None or (pinned is not None and not isinstance(pinned, bool)) or (memo is not None and (not isinstance(memo, str) or len(memo) > 500)):
            abort(400)
        return ask(pid, "mark", record=record, pinned=pinned, memo=memo)

    # ---- 프로젝트: 왼쪽 목록(변수·분석) · 묶음 · 식 더하기 · 명령 창 (DESK_V2) -----------------------------------

    @app.get("/api/p/<pid>/variables")
    def api_variables(pid: str) -> Any:
        """변수 탭 — 시리즈마다 이름·설명·구간·끝 값·종류·모형과의 관계, 묶음. 계산하지 않는다."""
        return ask(pid, "variables")

    @app.get("/api/p/<pid>/analysis-list")
    def api_analysis_list(pid: str) -> Any:
        """분석 탭 — 개별 식과 돌린 분석(대상별 가장 새 결과·낡음)."""
        return ask(pid, "analysis_list")

    @app.post("/api/p/<pid>/group/define")
    def api_group_define(pid: str) -> Any:
        """{name, series?, desc?, transform?, dry?} — 묶음 저장(`equion group define`). dry 면 쓰지 않고 차이만."""
        data = body()
        name = pick(data, "name", NAME)
        if name is None:
            abort(400, description=t("묶음 이름(영문으로 시작 — 영문·숫자·_)이 있어야 합니다"))
        series = names_arg(data, "series", SERIES, 200)
        args = dict(name=name, series=series, desc=text_arg(data, "desc", 200), transform=pick(data, "transform", NAME))
        if data.get("dry") is True:
            return ask(pid, "group_define", dry=True, **args)
        return run(pid, "group_define", t("묶음 {name}", name=name), **args)

    @app.post("/api/p/<pid>/group/remove")
    def api_group_remove(pid: str) -> Any:
        name = pick(body(), "name", NAME)
        if name is None:
            abort(400)
        return run(pid, "group_remove", t("묶음 지우기 {name}", name=name), name=name)

    @app.post("/api/p/<pid>/part/add")
    def api_part_add(pid: str) -> Any:
        """{block, text, desc?, from?, record?, create?, dry?} — 블록에 식 한 줄(`equion block add`) · 개별 식을 모형의 블록으로 옮기기(from)."""
        data = body()
        block, text = pick(data, "block", NAME), text_arg(data, "text", 2000)
        if block is None or not text or "\n" in text:
            abort(400, description=t("블록과 식 한 줄이 있어야 합니다"))
        args = dict(block=block, text=text, desc=text_arg(data, "desc", 200), from_part=pick(data, "from", PART),
                    record=pick(data, "record", EST_RECORD), create=data.get("create") is True)
        if data.get("dry") is True:
            return ask(pid, "part_add", dry=True, **args)
        return run(pid, "part_add", t("식 더하기 {block}", block=block), **args)

    @app.post("/api/p/<pid>/part/remove")
    def api_part_remove(pid: str) -> Any:
        part = pick(body(), "part", PART)
        if part is None:
            abort(400)
        return run(pid, "part_remove", t("식 빼기 {part}", part=part), part=part)

    @app.post("/api/p/<pid>/line")
    def api_line(pid: str) -> Any:
        """{line} — 명령 창의 한 줄(`equion …`과 같다). 작업 줄에 올라가고, 결과는 {line, code, out, records, changes, seconds, denied}."""
        data = body()
        text = data.get("line")
        if not isinstance(text, str) or not text.strip() or len(text) > 4000 or "\n" in text.strip():
            abort(400, description=t("명령 한 줄이 있어야 합니다"))
        label = text.strip()
        return run(pid, "line", t("명령 {line}", line=label if len(label) <= 60 else label[:59] + "…"), text=text.strip())

    @app.get("/api/p/<pid>/catalog")
    def api_catalog(pid: str) -> Any:
        """명령 창의 자동 완성 재료 — 명령·옵션과 프로젝트의 이름들."""
        return ask(pid, "catalog")

    # ---- 프로젝트: 후보 묶음 · 시나리오 폼 · 노트 · 같은 분석의 두 기록 (2차판) ------------------------------------------

    SHOCK = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,60}=[+\-0-9.eE]{1,30}%?(?:@[A-Za-z0-9+\-]{1,20}(?::[A-Za-z0-9+\-]{1,20})?)?")
    ADDF = re.compile(r"[^\s:=]{1,60}:[^\s:=]{1,60}=[+\-0-9.eE]{1,30}(?:@[A-Za-z0-9+\-]{1,20}(?::[A-Za-z0-9+\-]{1,20})?)?")
    AN_RECORD = re.compile(r"an:[A-Za-z0-9][A-Za-z0-9_\-.]{0,160}")
    NOTE_RECORD = re.compile(r"(?:an|est|hs|sim):[A-Za-z0-9][A-Za-z0-9_\-.]{0,160}")

    def note_path(pid: str, value: Any, must_exist: bool = True) -> str:
        """노트 경로 — 프로젝트 안의 .md(없어도 되면 must_exist=False)."""
        if not isinstance(value, str) or not value.strip() or len(value) > 300 or "\\" in value:
            abort(400)
        if not value.lower().endswith(".md"):
            abort(400, description=t("노트는 .md 파일입니다: {name}", name=value[:80]))
        s = session(pid)
        try:
            path = s.resolve(value)
        except Outside:
            abort(403)
        if must_exist and not path.is_file():
            abort(404)
        return path.relative_to(Path(s.root).resolve()).as_posix()

    @app.post("/api/p/<pid>/est-batch")
    def api_est_batch(pid: str) -> Any:
        """{part, texts, smpl?, sim?, cov?} — 후보 묶음: 식 여럿을 차례로 추정해 그 부품의 후보로(작업 하나 — 진행을 알린다)."""
        data = body()
        part, texts = pick(data, "part", PART), data.get("texts")
        if part is None or not isinstance(texts, list) or not 0 < len(texts) <= 64 or any(not isinstance(x, str) or not x.strip() or len(x) > 2000 or "\n" in x for x in texts):
            abort(400, description=t("부품과 식(1~64개, 한 줄씩)이 있어야 합니다"))
        return run(pid, "est_batch", t("후보 묶음 {part} — {n}개", part=part, n=len(texts)), part=part, texts=[x.strip() for x in texts],
                   smpl=text_arg(data, "smpl", 60), sim=data.get("sim") is True, cov=pick(data, "cov", allowed=COV))

    @app.get("/api/p/<pid>/scenario-info")
    def api_scenario_info(pid: str) -> Any:
        """시나리오 폼의 재료 — 시나리오들·가정 세트·보정항·모형·변수·식."""
        return ask(pid, "scenario_info")

    @app.post("/api/p/<pid>/scenario/define")
    def api_scenario_define(pid: str) -> Any:
        """{name, desc?, base?, addfactors?, model?, shocks?, addfactor?, dry?} — 시나리오 쓰기(`equion scenario define`). dry 면 차이만."""
        data = body()
        name = pick(data, "name", NAME)
        if name is None:
            abort(400, description=t("시나리오 이름(영문으로 시작 — 영문·숫자·_)이 있어야 합니다"))
        args = dict(name=name, desc=text_arg(data, "desc", 200), base=text_arg(data, "base", 60), addfactors=text_arg(data, "addfactors", 60),
                    model=text_arg(data, "model", 60), shocks=names_arg(data, "shocks", SHOCK, 60), addfactor=names_arg(data, "addfactor", ADDF, 60))
        for key in ("base", "addfactors", "model"):
            if args[key] and not NAME.fullmatch(args[key]):
                abort(400, description=t("받을 수 없는 값입니다: {key}", key=key))
        if data.get("dry") is True:
            return ask(pid, "scenario_define", dry=True, **args)
        return run(pid, "scenario_define", t("시나리오 {name}", name=name), **args)

    @app.post("/api/p/<pid>/scenario/remove")
    def api_scenario_remove(pid: str) -> Any:
        name = pick(body(), "name", NAME)
        if name is None:
            abort(400)
        return run(pid, "scenario_remove", t("시나리오 지우기 {name}", name=name), name=name)

    @app.get("/api/p/<pid>/notes")
    def api_notes(pid: str) -> Any:
        """노트 목록(notes/**/*.md)과 블록 상태의 수 — 실행하지 않는다."""
        return ask(pid, "notes")

    @app.get("/api/p/<pid>/note")
    def api_note(pid: str) -> Any:
        """노트 하나 — 글과 블록마다 상태·명령·기록."""
        return ask(pid, "note_view", path=note_path(pid, request.args.get("path")))

    @app.post("/api/p/<pid>/note/run")
    def api_note_run(pid: str) -> Any:
        """{path, block?, stale?, force?} — 노트의 블록을 실행(`equion note run`) — 블록마다 새 기록."""
        data = body()
        path = note_path(pid, data.get("path"))
        block = data.get("block")
        if block is not None and (not isinstance(block, int) or isinstance(block, bool) or not 0 < block < 1000):
            abort(400)
        label = t("노트 {path}", path=path) + (f" #{block}" if block else "")
        return run(pid, "note_run", label, path=path, block=block, stale=data.get("stale") is True, force=data.get("force") is True)

    @app.post("/api/p/<pid>/note/add")
    def api_note_add(pid: str) -> Any:
        """{note, lines?, record?, title?} — 노트 끝에 블록 하나(`equion note add`). 노트가 없으면 만든다."""
        data = body()
        note = note_path(pid, data.get("note"), must_exist=False)
        lines = data.get("lines")
        if lines is not None and (not isinstance(lines, list) or len(lines) > 80 or any(not isinstance(x, str) or not x.strip() or len(x) > 2000 or "\n" in x for x in lines)):
            abort(400)
        record = pick(data, "record", NOTE_RECORD)
        if not lines and not record:
            abort(400, description=t("더할 것이 없습니다 — 명령 줄 또는 기록"))
        return run(pid, "note_add", t("노트에 담기 {path}", path=note), note=note, lines=lines, record=record, title=text_arg(data, "title", 120))

    @app.get("/api/p/<pid>/an-history")
    def api_an_history(pid: str) -> Any:
        """같은 분석·같은 대상의 기록들 — 이전 기록과 비교."""
        record = request.args.get("id", "")
        if not AN_RECORD.fullmatch(record):
            abort(400)
        return ask(pid, "an_history", record=record)

    # ---- 프로젝트: 이정표 · 묶어 보내기 (D61) ----------------------------------------------------------------

    @app.get("/api/p/<pid>/milestones")
    def api_milestones(pid: str) -> Any:
        """이정표 목록 — 이름·메모·만든 때·자료 회차·정의 파일 수·고정한 기록."""
        return ask(pid, "milestones")

    @app.post("/api/p/<pid>/milestone/make")
    def api_milestone_make(pid: str) -> Any:
        """{name, note?} — 이정표 만들기(`equion milestone make`): 정의 파일 사본·자료 회차·고정한 기록."""
        data = body()
        name = pick(data, "name", NAME)
        if name is None:
            abort(400, description=t("이정표 이름(영문으로 시작 — 영문·숫자·_)이 있어야 합니다"))
        return run(pid, "milestone_make", t("이정표 {name}", name=name), name=name, note=text_arg(data, "note", 200))

    @app.get("/api/p/<pid>/milestone")
    def api_milestone(pid: str) -> Any:
        """이정표와 지금 — 파일마다 같음·고침·새로·지움과 차이."""
        name = request.args.get("name", "")
        if not NAME.fullmatch(name):
            abort(400)
        return ask(pid, "milestone_diff", name=name)

    @app.post("/api/p/<pid>/milestone/restore")
    def api_milestone_restore(pid: str) -> Any:
        """{name, files?} — 정의를 이정표 때로(`equion milestone restore`). 바뀜 기록에 남는다."""
        data = body()
        name = pick(data, "name", NAME)
        files = data.get("files")
        if name is None or (files is not None and (not isinstance(files, list) or len(files) > 200
                                                    or any(not isinstance(f, str) or not 0 < len(f) <= 300 or ".." in f for f in files))):
            abort(400)
        return run(pid, "milestone_restore", t("이정표로 되돌리기 {name}", name=name), name=name, files=files)

    @app.post("/api/p/<pid>/bundle")
    def api_bundle(pid: str) -> Any:
        """{raw?, records?} — 묶어 보내기(`equion bundle make`): exports/<프로젝트>_<날짜>.zip."""
        data = body()
        records = data.get("records", "keep")
        if records not in ("keep", "all", "none"):
            abort(400)
        return run(pid, "bundle", t("묶어 보내기"), raw=data.get("raw") is True, records=records)

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
        n = data.get("n", 0)
        if not isinstance(n, int) or isinstance(n, bool) or not 0 <= n < terminal.MAX_SLOTS:
            abort(400, description=t("터미널 번호는 0~{last}", last=terminal.MAX_SLOTS - 1))
        try:
            opened = state.terminals.open(s.id, s.root, None, cols, rows, n)
        except OSError as exc:
            return jsonify(error=t("셸을 시작하지 못했습니다 ({error})", error=exc)), 500
        return jsonify(id=opened.id, n=opened.slot, shell=terminal.shell_label(opened.exe), cwd=s.root)

    @app.get("/api/term/list")
    def api_term_list() -> Any:
        """그 프로젝트의 돌고 있는 셸들(번호 차례) — 화면을 다시 불러온 뒤 터미널 탭을 되살린다."""
        term_guard()
        s = state.session(request.args.get("p"))
        if s is None:
            abort(409, description=t("연 프로젝트가 없습니다"))
        return jsonify(terms=[{"id": x.id, "n": x.slot, "shell": terminal.shell_label(x.exe)} for x in state.terminals.of_project(s.id)],
                       max=terminal.MAX_SLOTS)

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
