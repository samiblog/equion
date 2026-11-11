"""Equion Desk 시험 — 로컬 서버·작업 프로세스·터미널(D0-2·D0-3). `uv run --package equion-desk pytest desk`.

예제 프로젝트(`equion new p --template desk`)를 임시 폴더에 만들어, 화면이 부르는 길 그대로(서버 → 작업 프로세스 → `eqn.project`) 돈다.
터미널(E2~E4)은 의사 콘솔이 있는 Windows에서만 돈다.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
import time

RESULTS: list[tuple[str, bool, str]] = []
ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b\][^\x07]*\x07")


def check(name: str, ok: object, detail: str = "") -> None:
    RESULTS.append((name, bool(ok), detail))
    print(("  ✓ " if ok else "  ✗ ") + name + (f" — {detail}" if detail and not ok else ""))


def example(tmp: str) -> str:
    """예제 프로젝트를 tmp에 만든다."""
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable, "-m", "equion", "new", "p", "--template", "desk"], cwd=tmp, capture_output=True, text=True,
                       encoding="utf-8", env=env)
    assert r.returncode == 0, r.stdout + r.stderr
    return os.path.join(tmp, "p")


def section_server(folder: str) -> None:
    print("C. 로컬 서버 — 보호 장치와 화면 파일")
    from equion_desk.server import AppState, create_app

    state = AppState(folder, mode="browser")
    try:
        c = create_app(state).test_client()
        r = c.get("/")
        check("C1 첫 화면 — 자리 표시가 모두 채워지고 CSP가 붙는다",
              r.status_code == 200 and "{{" not in r.text and state.term_secret in r.text
              and "script-src 'self'" in r.headers.get("Content-Security-Policy", ""))
        r2 = c.get("/web/js/main.js")
        check("C2 스크립트는 text/javascript로 나간다(레지스트리와 무관)",
              r2.status_code == 200 and r2.headers["Content-Type"].startswith("text/javascript"))
        missing = [u for u in re.findall(r'(?:src|href)="(/web/[^"]+)"', r.text) if c.get(u).status_code != 200]
        check("C3 첫 화면이 가리키는 파일이 모두 있다", not missing, ", ".join(missing))
        imports = re.findall(r"from '\./([\w.]+)'", r2.text)
        check("C4 스크립트가 불러오는 모듈이 모두 있다", imports and all(c.get(f"/web/js/{m}").status_code == 200 for m in imports))
        check("C5 다른 도메인 이름으로 온 요청은 거절(DNS 리바인딩)", c.get("/api/state", headers={"Host": "evil.example"}).status_code == 403)
        check("C6 POST는 JSON 본문만", c.post("/api/est", data="target=x").status_code == 415)
        state.token = "tok"
        check("C7 창 모드 — 토큰이 없으면 /api/ 거절, 있으면 통과",
              c.get("/api/state").status_code == 403 and c.get("/api/state", headers={"X-Token": "tok"}).status_code == 200)
        state.token = None
        check("C8 터미널 — 비밀값이 없으면 거절", c.post("/api/term/open", json={"cols": 80, "rows": 24}).status_code in (403, 501))
        r = c.post("/api/term/open", json={"cols": 80, "rows": 24}, headers={"X-Term": state.term_secret, "Origin": "http://evil.example"})
        check("C9 터미널 — 다른 페이지(Origin)에서 온 요청은 거절", r.status_code in (403, 501))
        check("C10 화면 폴더 밖의 파일은 주지 않는다", c.get("/web/../server.py").status_code in (403, 404))
    finally:
        state.close()

    empty = AppState(None, mode="browser")
    c = create_app(empty).test_client()
    check("C11 프로젝트 없이 — 상태는 주고 계산은 거절(409)",
          c.get("/api/state").json["root"] is None and c.post("/api/est", json={"target": "x"}).status_code == 409)


def section_worker(folder: str) -> None:
    print("D. 작업 프로세스 — 추정·과거 재현·전망, 오류, 취소, 격리")
    from equion_desk.server import AppState, create_app
    from equion_desk.worker import Worker, WorkerError

    state = AppState(folder, mode="browser")
    try:
        c = create_app(state).test_client()
        r = c.get("/api/project")
        ids = [p["id"] for p in (r.json.get("parts") or [])]
        check("D1 프로젝트 — 부품 목록과 런타임", r.status_code == 200 and "demand:CN" in ids and r.json["info"]["executable"], str(r.json)[:200])
        times = []
        for _ in range(3):
            t = time.perf_counter()
            r = c.post("/api/est", json={"target": "demand:CN"})
            times.append(time.perf_counter() - t)
        rec = (r.json or {}).get("result") or {}
        check("D2 추정 — 계수·진단·시리즈가 온다",
              r.status_code == 200 and len(rec.get("coefs", [])) == 3 and rec.get("diagnostics")
              and len(rec["series"]["period"]) == rec["n"] == len(rec["series"]["resid"]), str(r.json)[:200])
        check("D3 추정 — 기록이 남고 '누가'는 desk",
              rec.get("who") == "desk" and os.path.isfile(os.path.join(rec.get("path", "-"), "record.json")))
        check("D4 추정 — 띄워 둔 프로세스에서 1초 안(S1)", min(times) < 1.0, " ".join(f"{v:.3f}" for v in times))
        check("D5 응답의 JSON에 NaN이 없다(브라우저가 읽지 못한다)", "NaN" not in r.get_data(as_text=True))
        r = c.post("/api/est", json={"target": "CN c Y CN(-1) CN(-2)"})
        check("D6 식 글자로 추정", r.status_code == 200 and len(r.json["result"]["coefs"]) == 4, str(r.json)[:200])
        r = c.post("/api/est", json={"target": "demand:ZZ"})
        check("D7 없는 부품 — 422와 까닭(프로세스는 살아 있다)",
              r.status_code == 422 and r.json["kind"] == "input" and "demand:ZZ" in r.json["error"]
              and not r.json["error"].startswith("'") and state.worker.alive, str(r.json)[:200])
        r = c.post("/api/hs", json={})
        check("D8 과거 재현 — 기록 hs:", r.status_code == 200 and r.json["result"]["id"].startswith("hs:"), str(r.json)[:200])
        r = c.post("/api/sim", json={})
        check("D9 전망 — 기록 sim:", r.status_code == 200 and r.json["result"]["id"].startswith("sim:"), str(r.json)[:200])
        pid = state.worker._proc.pid
        check("D10 취소 — 하던 일이 없으면 False, 프로세스는 끝난다",
              c.post("/api/cancel", json={}).json["cancelled"] is False and not state.worker.alive)
        r = c.post("/api/est", json={"target": "demand:CN"})
        check("D11 끝난 뒤 다음 부름에서 다시 뜬다", r.status_code == 200 and state.worker.alive and state.worker._proc.pid != pid)
    finally:
        state.close()

    w = Worker(os.path.dirname(folder))       # 프로젝트가 아닌 폴더
    try:
        w.call("ping")
        check("D12 프로젝트가 아닌 폴더 — 까닭을 알리고 끝난다", False)
    except WorkerError as exc:
        check("D12 프로젝트가 아닌 폴더 — 까닭을 알리고 끝난다", exc.kind == "input" and not w.alive, f"{exc.kind}: {exc}")
    finally:
        w.stop()

    # 격리(D39): PC의 PYTHONPATH에 같은 이름의 가짜 패키지가 있어도 런타임의 것을 쓴다
    fake = os.path.join(os.path.dirname(folder), "fake")
    os.makedirs(os.path.join(fake, "numpy"), exist_ok=True)
    with open(os.path.join(fake, "numpy", "__init__.py"), "w", encoding="utf-8") as f:
        f.write("raise ImportError('PYTHONPATH leaked')\n")
    old = os.environ.get("PYTHONPATH")
    os.environ["PYTHONPATH"] = fake
    w = Worker(folder)
    try:
        check("D13 격리 — PYTHONPATH의 가짜 numpy를 읽지 않는다", w.call("ping")["result"]["equion"])
    except WorkerError as exc:
        check("D13 격리 — PYTHONPATH의 가짜 numpy를 읽지 않는다", False, str(exc))
    finally:
        w.stop()
        if old is None:
            del os.environ["PYTHONPATH"]
        else:
            os.environ["PYTHONPATH"] = old


def section_terminal(folder: str) -> None:
    print("E. 터미널 — 런타임이 PATH 맨 앞, PC의 Python 설정은 지운다")
    from equion_desk import runtime

    ours = runtime.bin_dirs()
    env = runtime.clean_env({"PATH": os.pathsep.join(["/somewhere", ours[0]]), "PYTHONPATH": "x", "PythonHome": "y",
                             "CONDA_PREFIX": "z", "KEEP": "1"})
    first = env["PATH"].split(os.pathsep)
    check("E1 환경 — 런타임이 맨 앞(겹치지 않게), PYTHONPATH·PYTHONHOME·CONDA 지움, 나머지는 그대로",
          first[:len(ours)] == ours and first.count(ours[0]) == 1 and "/somewhere" in first
          and not any(k.upper() in runtime.FOREIGN for k in env) and env["KEEP"] == "1" and env["PYTHONNOUSERSITE"] == "1", str(env))
    from equion_desk.conpty import AVAILABLE

    if not AVAILABLE:
        print("  - E2~E4 건너뜀: 의사 콘솔(ConPTY)은 Windows에만 있다")
        return
    import importlib

    import equion
    from equion_desk import terminal
    from equion_desk.server import AppState, create_app

    old = os.environ.get("PYTHONPATH")
    os.environ["PYTHONPATH"] = os.path.join(os.path.dirname(folder), "fake")
    try:
        importlib.reload(terminal)            # 셸의 환경은 모듈을 불러올 때 정해진다 — 가짜 PYTHONPATH가 있는 채로 다시
    finally:
        if old is None:
            del os.environ["PYTHONPATH"]
        else:
            os.environ["PYTHONPATH"] = old
    state = AppState(folder, mode="browser")
    state.terminals = terminal.Terminals()
    try:
        c = create_app(state).test_client()
        head = {"X-Term": state.term_secret}
        r = c.post("/api/term/open", json={"cols": 200, "rows": 30}, headers=head)
        check("E2 셸이 프로젝트 폴더에서 뜬다", r.status_code == 200 and os.path.samefile(r.json["cwd"], folder), str(r.json))
        sid = r.json["id"]
        cmd = ("python -c \"import sys,equion,numpy;print('PY='+sys.executable);print('EQ='+equion.__version__)\"; "
               "echo \"PP=[$env:PYTHONPATH]\"; equion --version; echo mark-end\r")
        c.post("/api/term/input", json={"t": sid, "data": cmd}, headers=head)
        out, nxt, end = "", 0, time.time() + 40
        while time.time() < end and out.count("mark-end") < 2:
            got = c.post("/api/term/read", json={"want": {sid: nxt}}, headers=head).json["terms"][sid]
            out, nxt = out + got["data"], got["next"]
        text = ANSI.sub("", out)
        m = re.search(r"^PY=(\S+)", text, re.M)       # 줄 맨 앞 — 되비친 명령 줄의 것은 아니다
        check("E3 터미널의 python·equion이 앱의 런타임이다",
              bool(m) and os.path.normcase(os.path.dirname(m.group(1))) in [os.path.normcase(d) for d in ours]
              and f"EQ={equion.__version__}" in text, text[-600:])
        check("E4 터미널에 PC의 PYTHONPATH가 넘어가지 않는다", "PP=[]" in text, text[-300:])
        c.post("/api/term/close", json={"t": sid}, headers=head)
    finally:
        state.close()


def run() -> int:
    RESULTS.clear()
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        folder = example(tmp)
        section_server(folder)
        section_worker(folder)
        section_terminal(folder)
    bad = [n for n, ok, _ in RESULTS if not ok]
    print(f"\nEquion Desk 앱 시험 {len(RESULTS) - len(bad)}/{len(RESULTS)}")
    return len(bad)


def test_suite() -> None:
    assert run() == 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(1 if run() else 0)
