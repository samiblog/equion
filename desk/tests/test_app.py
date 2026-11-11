"""Equion Desk 시험 — 로컬 서버·작업 프로세스·터미널·프로젝트 탭·기록 읽기·감시·식 작업대(D0·D1·D2a). `uv run --package equion-desk pytest desk`.

예제 프로젝트(`equion new p --template desk`)를 임시 폴더에 만들어, 화면이 부르는 길 그대로(서버 → 작업 프로세스 → `eqn.project`) 돈다.
설정 파일은 임시 폴더에 둔다(사용자의 설정을 건드리지 않는다). 터미널(E2~E4)과 단일 인스턴스(I)는 Windows에서만 돈다.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time

RESULTS: list[tuple[str, bool, str]] = []
ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b\][^\x07]*\x07")


def check(name: str, ok: object, detail: str = "") -> None:
    RESULTS.append((name, bool(ok), detail))
    print(("  ✓ " if ok else "  ✗ ") + name + (f" — {detail}" if detail and not ok else ""))


def clean_env() -> dict[str, str]:
    """명령을 사람이 터미널에서 친 것처럼 — Claude Code 안에서 시험을 돌려도 '누가'가 terminal 이 되게."""
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    for key in ("CLAUDECODE", "EQUION_WHO"):
        env.pop(key, None)
    return env


def equion(folder: str, *args: str, who: str | None = None) -> subprocess.CompletedProcess:
    env = clean_env()
    if who:
        env["EQUION_WHO"] = who
    return subprocess.run([sys.executable, "-m", "equion", *args], cwd=folder, capture_output=True, text=True, encoding="utf-8", env=env)


def example(tmp: str, name: str = "p") -> str:
    """예제 프로젝트를 tmp에 만든다."""
    r = equion(tmp, "new", name, "--template", "desk")
    assert r.returncode == 0, r.stdout + r.stderr
    return os.path.join(tmp, name)


def new_state(tmp: str, folder: str | None = None, name: str = "config.json"):
    """시험용 앱 상태 — 설정 파일은 tmp 에. (state, 프로젝트 탭 id)"""
    from equion_desk.config import Config
    from equion_desk.projects import AppState

    state = AppState(Config(os.path.join(tmp, "cfg", name)), mode="browser")
    pid = state.open(folder).id if folder else None
    return state, pid


def wait_events(state, since: int, want, timeout: float = 12.0) -> list[dict]:
    """알림 줄에서 want(event) 가 참인 것이 올 때까지 모은다."""
    got: list[dict] = []
    end = time.time() + timeout
    while time.time() < end:
        out = state.feed.read(since, 0.5)
        got += out["events"]
        since = out["seq"]
        if any(want(e) for e in got):
            break
    return got


def section_server(tmp: str, folder: str) -> None:
    print("C. 로컬 서버 — 보호 장치와 화면 파일")
    from equion_desk.server import create_app

    state, pid = new_state(tmp, folder, "c.json")
    try:
        c = create_app(state).test_client()
        r = c.get("/")
        check("C1 첫 화면 — 자리 표시가 모두 채워지고 CSP가 붙는다",
              r.status_code == 200 and "{{" not in r.text and state.term_secret in r.text
              and "script-src 'self'" in r.headers.get("Content-Security-Policy", "") and "connect-src 'self'" in r.headers["Content-Security-Policy"])
        r2 = c.get("/web/js/main.js")
        check("C2 스크립트는 text/javascript로 나간다(레지스트리와 무관)",
              r2.status_code == 200 and r2.headers["Content-Type"].startswith("text/javascript"))
        missing = [u for u in re.findall(r'(?:src|href)="(/web/[^"]+)"', r.text) if c.get(u).status_code != 200]
        check("C3 첫 화면이 가리키는 파일이 모두 있다", not missing, ", ".join(missing))
        # 모듈이 불러오는 모듈을 따라가며 모두 있는지(없는 파일을 불러오면 화면이 통째로 뜨지 않는다)
        seen, todo, lost = set(), ["js/main.js"], []
        while todo:
            path = todo.pop()
            if path in seen:
                continue
            seen.add(path)
            got = c.get(f"/web/{path}")
            if got.status_code != 200:
                lost.append(path)
                continue
            base = os.path.dirname(path)
            for ref in re.findall(r"from '(\.{1,2}/[\w./-]+)'", got.text):
                todo.append(os.path.normpath(os.path.join(base, ref)).replace(os.sep, "/"))
        check("C4 스크립트가 불러오는 모듈이 모두 있다(따라가며)", len(seen) >= 12 and not lost, f"{len(seen)}개 · 없는 것 {lost}")
        check("C5 다른 도메인 이름으로 온 요청은 거절(DNS 리바인딩)", c.get("/api/state", headers={"Host": "evil.example"}).status_code == 403)
        check("C6 POST는 JSON 본문만", c.post(f"/api/p/{pid}/est", data="target=x").status_code == 415)
        state.token = "tok"
        check("C7 창 모드 — 토큰이 없으면 /api/ 거절, 있으면 통과",
              c.get("/api/state").status_code == 403 and c.get("/api/state", headers={"X-Token": "tok"}).status_code == 200)
        state.token = None
        check("C8 터미널 — 비밀값이 없으면 거절", c.post("/api/term/open", json={"p": pid, "cols": 80, "rows": 24}).status_code in (403, 501))
        r = c.post("/api/term/open", json={"p": pid, "cols": 80, "rows": 24}, headers={"X-Term": state.term_secret, "Origin": "http://evil.example"})
        check("C9 터미널 — 다른 페이지(Origin)에서 온 요청은 거절", r.status_code in (403, 501))
        check("C10 화면 폴더 밖의 파일은 주지 않는다", c.get("/web/../server.py").status_code in (403, 404))
        vendor = [u for u in ("vendor/vega/vega.min.js", "vendor/vega/vega-lite.min.js", "vendor/markdown-it/markdown-it.min.js",
                              "vendor/dompurify/purify.min.js", "img/icon.svg") if c.get(f"/web/{u}").status_code != 200]
        check("C15 문서·차트 라이브러리와 아이콘이 들어 있다", not vendor, ", ".join(vendor))
    finally:
        state.close()

    empty, _ = new_state(tmp, None, "c2.json")
    try:
        c = create_app(empty).test_client()
        st = c.get("/api/state").json
        check("C11 프로젝트 없이 — 상태는 주고(탭 없음) 없는 탭의 계산은 404",
              st["tabs"] == [] and st["active"] is None and c.post("/api/p/nope/est", json={"target": "x"}).status_code == 404)
        check("C12 폴더 고르기는 창에서만 — 브라우저 모드는 501", c.post("/api/open", json={}).status_code == 501)
        empty.pick_folder = lambda: os.path.dirname(folder)       # equion.toml이 없는 폴더를 골랐다
        r = c.post("/api/open", json={})
        check("C13 프로젝트가 아닌 폴더를 고르면 열지 않고 까닭을 알린다", r.status_code == 422 and "equion.toml" in r.json["error"] and not empty.sessions)
        empty.pick_folder = lambda: folder
        seen_titles = []
        empty.on_active = lambda s: seen_titles.append(s.name if s else None)
        r = c.post("/api/open", json={})
        check("C14 프로젝트 폴더를 고르면 탭으로 연다(창 제목을 바꾸게 알린다)",
              r.status_code == 200 and os.path.samefile(r.json["tabs"][0]["root"], folder) and r.json["active"] == r.json["id"] and seen_titles == ["p"])
    finally:
        empty.close()


def section_worker(tmp: str, folder: str) -> None:
    print("D. 작업 프로세스 — 개요·추정·과거 재현·전망, 오류, 취소, 격리")
    from equion_desk.server import create_app
    from equion_desk.worker import Worker, WorkerError

    state, pid = new_state(tmp, folder, "d.json")
    api = f"/api/p/{pid}"
    try:
        c = create_app(state).test_client()
        r = c.get(f"{api}/overview")
        o = (r.json or {}).get("overview") or {}
        ids = [p["id"] for b in o.get("blocks", []) for p in b["parts"]]
        check("D1 개요 — 블록과 부품·모형·자료 회차·런타임",
              r.status_code == 200 and "demand:CN" in ids and [m["name"] for m in o["models"]] == ["core", "main", "main_fixrl"]
              and o["vintage"]["id"] and o["vintage"]["span"] and o["executable"] and o["scenarios"] == ["oil20"], str(r.json)[:300])
        times = []
        for _ in range(3):
            t = time.perf_counter()
            r = c.post(f"{api}/est", json={"target": "demand:CN"})
            times.append(time.perf_counter() - t)
        rec = (r.json or {}).get("result") or {}
        check("D2 추정 — 계수·진단·시리즈가 온다",
              r.status_code == 200 and len(rec.get("coefs", [])) == 3 and rec.get("diagnostics")
              and len(rec["series"]["period"]) == rec["n"] == len(rec["series"]["resid"]), str(r.json)[:200])
        check("D3 추정 — 기록이 남고 '누가'는 desk, 명령은 터미널에서 치는 글 그대로",
              rec.get("who") == "desk" and rec.get("command") == "equion est demand:CN"
              and os.path.isfile(os.path.join(folder, rec.get("path", "-"), "record.json")), str({k: rec.get(k) for k in ("who", "command", "path")}))
        check("D4 추정 — 띄워 둔 프로세스에서 1초 안(S1)", min(times) < 1.0, " ".join(f"{v:.3f}" for v in times))
        check("D5 응답의 JSON에 NaN이 없다(브라우저가 읽지 못한다)", "NaN" not in r.get_data(as_text=True))
        check("D14 진단은 엔진이 낸 순서대로 온다(이름순으로 뒤섞지 않는다)", list(rec.get("diagnostics", {}))[:2] == ["lm", "white"], str(list(rec.get("diagnostics", {}))))
        r = c.post(f"{api}/est", json={"target": "CN c Y CN(-1) CN(-2)"})
        check("D6 식 글자로 추정", r.status_code == 200 and len(r.json["result"]["coefs"]) == 4, str(r.json)[:200])
        r = c.post(f"{api}/est", json={"target": "demand:ZZ"})
        w = state.sessions[pid].worker
        check("D7 없는 부품 — 422와 까닭(프로세스는 살아 있다)",
              r.status_code == 422 and r.json["kind"] == "input" and "demand:ZZ" in r.json["error"]
              and not r.json["error"].startswith("'") and w.alive, str(r.json)[:200])
        r = c.post(f"{api}/hs", json={})
        check("D8 과거 재현 — 기록 hs:", r.status_code == 200 and r.json["result"]["id"].startswith("hs:"), str(r.json)[:200])
        r = c.post(f"{api}/sim", json={"scenario": "base", "model": "main"})
        check("D9 전망 — 기록 sim:", r.status_code == 200 and r.json["result"]["id"].startswith("sim:"), str(r.json)[:200])
        jobs = [e for e in state.feed.read(0, 0)["events"] if e["type"] == "job"]
        check("D15 작업 줄 — 계산마다 시작과 끝(기록 이름)이 알림 줄에 남는다",
              [e["state"] for e in jobs[:2]] == ["start", "done"] and jobs[1]["record"].startswith("est:") and jobs[0]["job"] == jobs[1]["job"]
              and any(e["state"] == "error" for e in jobs), str([(e["state"], e.get("record")) for e in jobs]))
        # 정의 파일이 바뀌면 다음 요청은 새 식으로(작업 프로세스가 옛 프로젝트를 쥐고 있지 않다)
        eq_file = os.path.join(folder, "EQUATIONS", "demand.txt")
        with open(eq_file, encoding="utf-8") as f:
            original = f.read()
        with open(eq_file, "w", encoding="utf-8", newline="\n") as f:
            f.write(original.replace("CN c Y CN(-1)", "CN c Y CN(-1) CN(-2)"))
        r = c.post(f"{api}/est", json={"target": "demand:CN"})
        check("D16 블록 파일을 고친 뒤의 추정은 새 식으로 한다", r.status_code == 200 and len(r.json["result"]["coefs"]) == 4, str(r.json)[:200])
        with open(eq_file, "w", encoding="utf-8", newline="\n") as f:
            f.write(original)
        proc_id = w._proc.pid
        check("D10 취소 — 하던 일이 없으면 False, 프로세스는 끝난다",
              c.post(f"{api}/cancel", json={}).json["cancelled"] is False and not w.alive)
        r = c.post(f"{api}/est", json={"target": "demand:CN"})
        check("D11 끝난 뒤 다음 부름에서 다시 뜬다", r.status_code == 200 and w.alive and w._proc.pid != proc_id)
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

    if sys.platform == "win32":
        # 앱이 죽으면 작업 프로세스도 바로 끝난다(작업 개체) — 앱 노릇을 하는 프로세스를 띄워 강제로 끝내 본다
        code = ("import sys, time\nfrom equion_desk.worker import Worker\nw = Worker(sys.argv[1])\nw.call('ping')\n"
                "print(w._proc.pid, flush=True)\ntime.sleep(60)\n")
        host = subprocess.Popen([sys.executable, "-c", code, folder], stdout=subprocess.PIPE, text=True, env=clean_env())
        child = int(host.stdout.readline().strip() or 0)
        host.kill()
        host.wait(10)
        gone = False
        for _ in range(50):
            out = subprocess.run(["tasklist", "/FI", f"PID eq {child}", "/NH"], capture_output=True, text=True).stdout
            if str(child) not in out:
                gone = True
                break
            time.sleep(0.1)
        check("D17 앱을 강제로 끝내면 작업 프로세스도 바로 끝난다(작업 개체)", child and gone, f"pid {child}")
    else:
        print("  - D17 건너뜀: 작업 개체는 Windows에만 있다")


def section_terminal(tmp: str, folder: str) -> None:
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
        print("  - E2~E5 건너뜀: 의사 콘솔(ConPTY)은 Windows에만 있다")
        return
    import importlib

    import equion as eq
    from equion_desk import terminal
    from equion_desk.server import create_app

    old = {k: os.environ.get(k) for k in ("PYTHONPATH", "CLAUDECODE", "EQUION_WHO")}
    os.environ["PYTHONPATH"] = os.path.join(os.path.dirname(folder), "fake")
    os.environ.pop("CLAUDECODE", None)
    os.environ.pop("EQUION_WHO", None)
    try:
        importlib.reload(terminal)            # 셸의 환경은 모듈을 불러올 때 정해진다 — 가짜 PYTHONPATH가 있는 채로 다시
    finally:
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    state, pid = new_state(tmp, folder, "e.json")
    state.terminals = terminal.Terminals()
    try:
        c = create_app(state).test_client()
        head = {"X-Term": state.term_secret}
        r = c.post("/api/term/open", json={"p": pid, "cols": 200, "rows": 30}, headers=head)
        check("E2 셸이 프로젝트 폴더에서 뜬다", r.status_code == 200 and os.path.samefile(r.json["cwd"], folder), str(r.json))
        sid = r.json["id"]

        def run(cmd: str, mark: str, wait: float = 40.0, start: int = 0) -> tuple[str, int]:
            c.post("/api/term/input", json={"t": sid, "data": cmd + f"; echo {mark}\r"}, headers=head)
            out, nxt, end = "", start, time.time() + wait
            while time.time() < end and out.count(mark) < 2:
                got = c.post("/api/term/read", json={"want": {sid: nxt}}, headers=head).json["terms"][sid]
                out, nxt = out + got["data"], got["next"]
            return ANSI.sub("", out), nxt

        text, nxt = run("python -c \"import sys,equion,numpy;print('PY='+sys.executable);print('EQ='+equion.__version__)\"; "
                        "echo \"PP=[$env:PYTHONPATH]\"; equion --version", "mark-end")
        m = re.search(r"^PY=(\S+)", text, re.M)       # 줄 맨 앞 — 되비친 명령 줄의 것은 아니다
        check("E3 터미널의 python·equion이 앱의 런타임이다",
              bool(m) and os.path.normcase(os.path.dirname(m.group(1))) in [os.path.normcase(d) for d in ours]
              and f"EQ={eq.__version__}" in text, text[-600:])
        check("E4 터미널에 PC의 PYTHONPATH가 넘어가지 않는다", "PP=[]" in text, text[-300:])

        # D1 의 완료 기준: 터미널에서 친 명령의 기록이 알림 줄(→ 작업 기록 띠)에 뜨고 카드로 열린다
        since = state.feed.seq
        text, nxt = run("equion est demand:I", "mark-est", start=nxt)
        got = wait_events(state, since, lambda e: e["type"] == "record")
        recs = [e["record"] for e in got if e["type"] == "record"]
        card = c.get(f"/api/p/{pid}/record?id={recs[0]['id']}").json if recs else {}
        check("E5 터미널에서 친 명령의 기록이 알림 줄에 뜨고(누가: 터미널) 카드로 열린다",
              bool(recs) and recs[0]["id"].startswith("est:i_") and recs[0]["who"] == "terminal" and "## 계수" in card.get("summary", "")
              and card["series"]["period"], text[-400:] + str(got)[:300])
        c.post("/api/term/close", json={"t": sid}, headers=head)
    finally:
        state.close()


def section_tabs(tmp: str, folder: str) -> None:
    print("F. 프로젝트 탭·설정·지난 화면 — 닫았다 열면 이어진다")
    from equion_desk.config import MAX_TABS, Config
    from equion_desk.projects import AppState
    from equion_desk.server import create_app

    second = example(tmp, "q")
    path = os.path.join(tmp, "cfg", "f.json")
    state = AppState(Config(path), mode="browser")
    try:
        c = create_app(state).test_client()
        a = c.post("/api/open", json={"root": folder}).json
        b = c.post("/api/open", json={"root": second}).json
        check("F1 폴더를 주면 탭으로 열고 고른다 — 탭 둘, 뒤에 연 것이 고른 탭",
              [t["name"] for t in b["tabs"]] == ["p", "q"] and b["active"] == b["id"] != a["id"], str(b)[:200])
        again = c.post("/api/open", json={"root": folder}).json
        check("F2 이미 연 폴더를 또 열면 그 탭을 고른다(탭이 늘지 않는다)", len(again["tabs"]) == 2 and again["active"] == a["id"])
        check("F3 탭 알림 — 탭이 바뀔 때마다 알림 줄에", [e["type"] for e in state.feed.read(0, 0)["events"]].count("tabs") == 3)
        r = c.post(f"/api/p/{a['id']}/view", json={"view": {"tabs": [{"type": "bench", "part": "demand:CN", "draft": "CN c Y"}], "active": "bench:demand:CN"}})
        big = c.post(f"/api/p/{a['id']}/view", json={"view": {"x": "가" * 40000}})
        check("F4 화면 상태를 적고 다시 읽는다(너무 크면 413)",
              r.status_code == 200 and c.get(f"/api/p/{a['id']}/view").json["view"]["tabs"][0]["draft"] == "CN c Y" and big.status_code == 413)
        s = c.post("/api/settings", json={"theme": "dark", "font_scale": 110, "term_width": 520, "bogus": 1, "side_width": "넓게"}).json["client"]
        check("F5 설정 — 아는 이름·맞는 형식만 받는다", s["theme"] == "dark" and s["font_scale"] == 110 and s["term_width"] == 520
              and "bogus" not in s and s["side_width"] is None, str(s))
        check("F6 첫 화면에 바탕 설정이 실려 온다(흰 화면이 번쩍이지 않게)", 'data-theme-setting="dark"' in c.get("/").text)
        c.post("/api/tabs/active", json={"id": b["id"]})
    finally:
        state.close()

    # 다시 띄움 — 같은 설정 파일
    state = AppState(Config(path), mode="browser")
    try:
        state.restore()
        c = create_app(state).test_client()
        st = c.get("/api/state").json
        pid = st["tabs"][0]["id"]
        check("F7 다시 띄우면 탭·고른 탭·설정·화면 상태가 그대로다",
              [t["name"] for t in st["tabs"]] == ["p", "q"] and st["active"] == st["tabs"][1]["id"] and st["client"]["theme"] == "dark"
              and c.get(f"/api/p/{pid}/view").json["view"]["active"] == "bench:demand:CN" and len(st["recent"]) == 2, str(st)[:300])
        check("F8 되살린 탭은 화면이 부를 때까지 작업 프로세스를 띄우지 않는다", not any(s.worker.alive for s in state.sessions.values()))
        closed = c.post("/api/tabs/close", json={"id": pid}).json
        check("F9 탭을 닫으면 목록에서 빠지고 닫힌 탭의 요청은 404",
              [t["name"] for t in closed["tabs"]] == ["q"] and c.get(f"/api/p/{pid}/records").status_code == 404)
        for i in range(MAX_TABS):
            last = c.post("/api/open", json={"root": example(tmp, f"m{i}")})
        check(f"F10 탭은 {MAX_TABS}개까지 — 넘으면 까닭을 알린다(409)", last.status_code == 409 and len(state.sessions) == MAX_TABS, str(last.json))
    finally:
        state.close()
    with open(path, encoding="utf-8") as f:
        saved = json.load(f)
    check("F11 설정 파일은 사용자 폴더의 JSON 하나 — 프로젝트 폴더에는 쓰지 않는다",
          saved["version"] == 1 and len(saved["tabs"]) == MAX_TABS and not os.path.exists(os.path.join(folder, "config.json")))
    with open(path, "w", encoding="utf-8") as f:
        f.write("{ 깨진 파일")
    broken = Config(path)
    broken.update_client({"theme": "light"})
    check("F12 깨진 설정 파일 — 기본값으로 뜨고, 저장할 때 옛 파일을 옆에 남긴다",
          broken.client()["theme"] == "light" and os.path.isfile(path + ".bad") and Config(path).client()["theme"] == "light")


def section_reading(tmp: str, folder: str) -> None:
    print("G. 기록·카드·파일 읽기 — 프로젝트 폴더 안의 것만")
    from equion_desk.server import create_app

    outside = os.path.join(tmp, "outside.txt")
    with open(outside, "w", encoding="utf-8") as f:
        f.write("secret")
    with open(os.path.join(folder, "notes", "cp949.txt"), "wb") as f:
        f.write("한글 메모".encode("cp949"))
    with open(os.path.join(folder, "blob.bin"), "wb") as f:
        f.write(b"\0\1\2\3" * 100)
    equion(folder, "hs", "main")
    state, pid = new_state(tmp, folder, "g.json")
    api = f"/api/p/{pid}"
    try:
        c = create_app(state).test_client()
        recs = c.get(f"{api}/records").json["records"]
        kinds = {r["kind"] for r in recs}
        check("G1 작업 기록 — 로그의 줄이 만든 순으로(추정·과거 재현·전망)", {"est", "hs", "sim"} <= kinds and recs == sorted(recs, key=lambda r: r["created"]), str(kinds))
        hs = next(r for r in reversed(recs) if r["kind"] == "hs")
        card = c.get(f"{api}/record?id={hs['id']}").json
        check("G2 결과 카드 — summary.md(vega-lite 차트 포함)·record.json·파일 목록",
              card["kind"] == "hs" and "```vega-lite" in card["summary"] and card["meta"]["model"] == "main"
              and {"summary.md", "series.csv", "record.json"} <= {f["name"] for f in card["files"]}, str(card)[:200])
        check("G3 없는 기록·모양이 틀린 이름은 404(경로로 쓰지 않는다)",
              all(c.get(f"{api}/record?id={bad}").status_code == 404 for bad in ("est:nope", "est:../../x", "../x", "est:", "EST:cn_0001", "")))
        top = c.get(f"{api}/tree").json["entries"]
        names = [e["name"] for e in top]
        check("G4 파일 나무 — 폴더 먼저·이름순, .git 같은 것은 뺀다",
              names[:3] == ["ADDFACTORS", "ASSUMPTIONS", "DATA"] and "equion.toml" in names and all(e["dir"] for e in top[:names.index("work") + 1]), str(names))
        sub = c.get(f"{api}/tree?path=EQUATIONS").json["entries"]
        check("G5 아래 폴더는 펼칠 때 읽는다", {"demand.txt", "price.txt", "finance.txt"} <= {e["name"] for e in sub})
        f = c.get(f"{api}/file?path=EQUATIONS/demand.txt").json
        check("G6 글 파일 — 내용과 크기", f["kind"] == "text" and "CN c Y CN(-1)" in f["text"] and f["size"] > 0 and not f["truncated"])
        check("G7 cp949 글도 읽는다(무엇으로 읽었는지 알린다)",
              c.get(f"{api}/file?path=notes/cp949.txt").json == {**c.get(f"{api}/file?path=notes/cp949.txt").json, "text": "한글 메모", "encoding": "cp949"})
        check("G8 글이 아닌 파일은 내용을 주지 않는다", c.get(f"{api}/file?path=blob.bin").json["kind"] == "binary")
        bad = ["../outside.txt", "..\\outside.txt", outside, "/etc/passwd", "C:/Windows/win.ini", "EQUATIONS/../../outside.txt", "work/../../outside.txt"]
        codes = [c.get(f"{api}/file", query_string={"path": p}).status_code for p in bad]
        check("G9 폴더 밖의 파일은 읽지 않는다(.. · 절대 경로 · 드라이브)", all(code in (403, 404) for code in codes) and 200 not in codes, str(codes))
        check("G10 폴더 밖의 폴더도 보이지 않는다", c.get(f"{api}/tree", query_string={"path": ".."}).status_code == 403)
        check("G11 그림이 아닌 파일은 /raw 로 주지 않는다", c.get(f"{api}/raw?path=equion.toml").status_code in (403, 404))
        changes = c.get(f"{api}/changes").json["changes"]
        one = c.get(f"{api}/change?id={changes[-1]['id']}").json if changes else {}
        check("G12 바뀜 기록 — 목록(늘고 준 줄 수)과 차이", changes and one.get("diff", "").startswith("--- ") and one["plus"] >= 1
              and c.get(f"{api}/change?id=../x").status_code == 404, str(changes)[:200])
    finally:
        state.close()


def section_watch(tmp: str, folder: str) -> None:
    print("H. 감시 — 밖에서 생긴 기록과 바뀜이 알림 줄에")
    from equion_desk.server import create_app
    from equion_desk.watch import Feed

    feed = Feed()
    feed.add("a")
    got: list = []
    waiter = threading.Thread(target=lambda: got.append(feed.read(1, 5.0)))
    waiter.start()
    time.sleep(0.2)
    feed.add("b", x=1)
    waiter.join(3)
    check("H1 알림 줄 — 기다리던 읽기가 새 알림에 바로 깨어난다",
          got and [e["type"] for e in got[0]["events"]] == ["b"] and got[0]["seq"] == 2 and not got[0]["reset"])
    check("H2 알림 줄 — 받은 곳이 이 줄의 것이 아니면 reset(화면이 통째로 다시 읽는다)", feed.read(99, 0)["reset"] and not feed.read(2, 0)["events"])

    state, pid = new_state(tmp, folder, "h.json")
    session = state.sessions[pid]
    try:
        c = create_app(state).test_client()
        c.get(f"/api/p/{pid}/overview")
        time.sleep(1.2)                                   # 여는 순간의 바깥 고침 적기가 끝나게
        since = state.feed.seq
        r = equion(folder, "est", "demand:CN", who="claude")
        events = wait_events(state, since, lambda e: e["type"] == "record")
        recs = [e["record"] for e in events if e["type"] == "record"]
        check("H3 밖에서 돈 명령의 기록이 알림 줄에 — 누가(Claude)·명령·핵심 수치 그대로",
              r.returncode == 0 and recs and recs[0]["who"] == "claude" and recs[0]["command"].startswith("equion est")
              and recs[0]["metric"] and c.get(f"/api/events?since={since}&wait=0").json["events"], r.stdout[-200:] + str(events)[:200])
        since = state.feed.seq
        with open(os.path.join(folder, "EQUATIONS", "price.txt"), "a", encoding="utf-8", newline="\n") as f:
            f.write("\n# 밖에서 고친 줄\n")
        events = wait_events(state, since, lambda e: e["type"] == "change")
        kinds = [e["type"] for e in events]
        change = next((e["change"] for e in events if e["type"] == "change"), {})
        check("H4 정의 파일을 밖에서 고치면 — 정의 바뀜 알림, 그리고 '바깥' 바뀜 기록(전후 차이)",
              "defs" in kinds and change.get("who") == "바깥" and change["files"] == [{"path": "EQUATIONS/price.txt", "op": "changed"}]
              and change["plus"] == 2 and change["minus"] == 0, str(events)[:400])
        since = state.feed.seq
        r = equion(folder, "data", "use", session.overview()["result"]["vintage"]["id"])
        with open(os.path.join(folder, "notes", "새 메모.md"), "w", encoding="utf-8") as f:
            f.write("# 새 메모\n")
        events = wait_events(state, since, lambda e: e["type"] == "tree", timeout=8)
        check("H5 파일이 새로 생기면 파일 나무를 다시 읽으라는 알림", any(e["type"] == "tree" for e in events), str(events)[:200])
        check("H6 운영체제의 변경 알림을 쓰고 있다(못 쓰면 2초마다 견준다)", session.watcher.native in (True, False))
    finally:
        state.close()

    # 앱이 꺼져 있는 동안 바뀐 것 — 다음에 열 때 알린다(K7)
    with open(os.path.join(folder, "EQUATIONS", "finance.txt"), "a", encoding="utf-8", newline="\n") as f:
        f.write("\n# 꺼져 있는 동안 고친 줄\n")
    state, pid = new_state(tmp, folder, "h2.json")
    try:
        c = create_app(state).test_client()
        since = state.feed.seq
        c.get(f"/api/p/{pid}/overview")
        events = wait_events(state, since, lambda e: e["type"] == "offline")
        off = next((e for e in events if e["type"] == "offline"), {})
        check("H7 앱이 꺼져 있는 동안 바뀐 정의 파일을 열 때 알린다", "EQUATIONS/finance.txt" in off.get("files", []) and off.get("change", "").startswith("h"), str(events)[:300])
    finally:
        state.close()


def section_bench(tmp: str) -> None:
    print("J. 식 작업대 — 문법 검사·옵션 있는 추정·후보 목록·항등식·바꿔 끼운 과거 재현·채택")
    from equion_desk.server import create_app

    folder = example(tmp, "bench")
    state, pid = new_state(tmp, folder, "j.json")
    api = f"/api/p/{pid}"
    try:
        c = create_app(state).test_client()
        o = c.get(f"{api}/overview").json["overview"]
        cn = next(p for b in o["blocks"] for p in b["parts"] if p["id"] == "demand:CN")
        check("J1 개요의 부품에 그것을 쓰는 모형이 붙는다('이 후보로 과거 재현'이 고른다)", cn["models"] == ["core", "main", "main_fixrl"], str(cn))

        def chk(text: str, part: str | None = "demand:CN") -> dict:
            return c.post(f"{api}/check", json={"text": text, "part": part}).json

        ok, unknown, broken = chk("CN c Y CN(-1)"), chk("CN c Y ZZZ"), chk("CN c Y (")
        other, ident, empty, seas = chk("I c Y"), chk("Y = CN + I + G"), chk("  "), chk("log(CN) c log(Y) @seas @d(2009Q1)")
        check("J2 문법 검사 — 종류·목표·변수, 자료에 없는 변수, 읽을 수 없는 식의 까닭",
              ok == {"ok": True, "kind": "equation", "target": "CN", "variables": ["CN", "Y"], "unknown": [], "part_target": "CN"}
              and unknown["unknown"] == ["ZZZ"] and broken["ok"] is False and "괄호" in broken["error"], f"{ok} {unknown} {broken}")
        check("J3 문법 검사 — 목표가 다른 식·항등식·빈 칸·지시자(@seas·@d)를 가린다",
              other["target"] == "I" and other["part_target"] == "CN" and ident["kind"] == "identity" and empty == {"ok": False, "empty": True}
              and seas["ok"] and seas["unknown"] == [], f"{other} {ident} {empty} {seas}")
        check("J4 문법 검사는 계산이 아니다 — 기록을 남기지 않는다", not os.path.isdir(os.path.join(folder, "work", "est")))
        worker = state.sessions[pid].worker
        worker._lock.acquire()                # 다른 계산이 도는 중인 척
        try:
            began = time.perf_counter()
            busy = chk("CN c Y")
            took = time.perf_counter() - began
        finally:
            worker._lock.release()
        check("J5 다른 계산이 도는 중이면 문법 검사는 기다리지 않는다", busy == {"ok": None, "busy": True} and took < 0.5, f"{busy} {took:.2f}")

        r = c.post(f"{api}/est", json={"target": "demand:CN", "sim": True}).json["result"]
        check("J6 단독 모의와 함께 추정 — RMSPE 와 모의 시리즈가 온다",
              r["sim"]["rmspe"] > 0 and "CN_sim" in r["series"] and r["cov"] is None and r["command"] == "equion est demand:CN --sim", str(r.get("sim")))
        r2 = c.post(f"{api}/est", json={"target": "CN c Y CN(-1) CN(-2)", "part": "demand:CN", "sim": True, "cov": "hac", "smpl": "1990Q1:last",
                                         "name": "cn_lag2"}).json["result"]
        card = c.get(f"{api}/record?id=est:cn_lag2").json
        check("J7 식 글자·표본·표준오차·이름을 주어 추정 — 부품의 후보로 묶이고 기록이 표준오차의 종류를 말한다",
              r2["id"] == "est:cn_lag2" and r2["part"] == "demand:CN" and r2["sample"][0] == "1990Q1" and r2["cov"]["type"] == "hac"
              and "계수 공분산" in card["summary"] and "--for demand:CN --smpl 1990Q1:last --sim --cov hac --as cn_lag2" in r2["command"], str(r2.get("command")))
        bad = [c.post(f"{api}/est", json={"target": "CN c Y", **extra}).status_code
               for extra in ({"cov": "bogus"}, {"name": "../x"}, {"part": "no colon"}, {"method": "magic"})]
        dup = c.post(f"{api}/est", json={"target": "CN c Y CN(-1)", "part": "demand:CN", "name": "cn_lag2"})
        check("J8 받을 수 없는 옵션은 400, 이미 있는 이름은 까닭과 함께 422", bad == [400, 400, 400, 400] and dup.status_code == 422 and "cn_lag2" in dup.json["error"], f"{bad} {dup.json}")

        equion(folder, "est", "CN c Y", who="claude")
        cand = c.get(f"{api}/candidates?part=demand:CN").json
        rows = {x["id"]: x for x in cand["rows"]}
        first = rows.get("est:cn_0001", {})
        check("J9 후보 목록 — 사람·Claude 가 한 것이 한 목록에, 줄마다 적합·진단·기준·단독 모의·표준오차",
              list(rows) == ["est:cn_0001", "est:cn_lag2", "est:cn_0002"] and cand["adopted"] is None and first["stats"]["adj_r_squared"] > 0.99
              and first["diag"]["lm"] is not None and first["pass"] is False and first["reasons"] and first["sim"] > 0
              and rows["est:cn_lag2"]["cov"] == "hac" and rows["est:cn_0002"]["who"] == "claude" and rows["est:cn_0002"]["sim"] is None, str(cand)[:400])
        check("J10 후보 목록 — 없는 부품은 빈 목록, 모양이 틀린 이름은 400",
              c.get(f"{api}/candidates?part=demand:ZZ").json["rows"] == [] and c.get(f"{api}/candidates?part=nope").status_code == 400)

        before = len(c.get(f"{api}/records").json["records"])
        idt = c.post(f"{api}/ident", json={"part": "demand:Y"}).json["result"]
        check("J11 항등식을 실측으로 검사 — 맞는지·가장 큰 차이·기간별 차이(기록은 남기지 않는다)",
              idt["ok"] is True and idt["n"] == 200 and len(idt["series"]["diff"]) == 200 and idt["command"] == "equion ident demand:Y --check"
              and len(c.get(f"{api}/records").json["records"]) == before, str(idt)[:200])
        check("J12 추정식을 항등식 검사에 주면 까닭을 알린다(422)", c.post(f"{api}/ident", json={"part": "demand:CN"}).status_code == 422)

        with open(os.path.join(folder, "EQUATIONS", "demand.txt"), encoding="utf-8") as f:
            block = f.read()
        h1 = c.post(f"{api}/hs", json={"part": "demand:CN", "record": "est:cn_lag2"}).json["result"]
        h2 = c.post(f"{api}/hs", json={"part": "demand:CN", "record": "est:cn_0001"}).json["result"]
        with open(os.path.join(folder, "EQUATIONS", "demand.txt"), encoding="utf-8") as f:
            same = f.read() == block
        check("J13 이 후보로 과거 재현 — 지금 파일로 먼저 풀고(기준) 바꿔 끼워 풀어 변수마다 전후를 견준다. 파일은 그대로",
              h1["baseline_new"] is True and h1["swaps"] == {"demand:CN": "est:cn_lag2"} and h1["vs"]["id"] == h1["baseline"]
              and len(h1["vs"]["rmspe"]["CN"]) == 2 and f"--swap demand:CN=est:cn_lag2 --vs {h1['baseline']}" in h1["command"] and same, str(h1)[:300])
        check("J14 기준 풀이는 정의·자료가 그대로면 다시 풀지 않고 그것을 쓴다", h2["baseline_new"] is False and h2["baseline"] == h1["baseline"])
        check("J15 그 부품을 쓰지 않는 모형·모양이 틀린 요청은 거절",
              c.post(f"{api}/hs", json={"part": "price:P", "record": "est:cn_0001", "model": "core"}).status_code == 422
              and c.post(f"{api}/hs", json={"part": "demand:CN"}).status_code == 400)

        since = state.feed.seq
        done = c.post(f"{api}/adopt", json={"record": "est:cn_lag2", "part": "demand:CN"}).json["result"]
        with open(os.path.join(folder, "EQUATIONS", "demand.txt"), encoding="utf-8") as f:
            line = f.read().splitlines()[1]
        events = wait_events(state, since, lambda e: e["type"] == "change")
        change = next((e["change"] for e in events if e["type"] == "change"), {})
        cn = next(p for b in c.get(f"{api}/overview").json["overview"]["blocks"] for p in b["parts"] if p["id"] == "demand:CN")
        check("J16 채택 — 블록 파일의 그 줄과 채택표가 바뀌고(설명은 그대로) 바뀜 기록에 '누가 Desk · 명령 그대로'",
              done["line_changed"] and line.startswith("CN c Y CN(-1) CN(-2)") and "# 소비" in line and cn["adopted"] == "est:cn_lag2"
              and c.get(f"{api}/candidates?part=demand:CN").json["adopted"] == "est:cn_lag2"
              and change.get("who") == "desk" and change.get("how") == "equion adopt est:cn_lag2 --part demand:CN"
              and {f["path"] for f in change["files"]} == {"EQUATIONS/adopted.toml", "EQUATIONS/demand.txt"}, f"{done} {line} {change}")
        h3 = c.post(f"{api}/hs", json={"part": "demand:CN", "record": "est:cn_0001"}).json["result"]
        check("J17 채택한 뒤에는 정의가 바뀌었으므로 기준을 새로 푼다", h3["baseline_new"] is True and h3["baseline"] != h1["baseline"])
        check("J18 채택 — 없는 기록·항등식 부품은 까닭과 함께 거절(422)",
              c.post(f"{api}/adopt", json={"record": "est:nope"}).status_code == 422
              and c.post(f"{api}/adopt", json={"record": "est:cn_0001", "part": "demand:Y"}).status_code == 422)
        d = c.post(f"{api}/diag", json={"target": "est:cn_0001"})
        check("J19 진단 더 보기 — 분석 기록(an:)으로 남는다", d.status_code == 200 and d.json["result"]["id"].startswith("an:diag"), str(d.json)[:200])
    finally:
        state.close()


def section_instance(tmp: str, folder: str) -> None:
    print("I. 창은 하나 — 또 실행하면 폴더를 떠 있는 창에 넘긴다")
    from equion_desk import instance

    name = instance.pipe_name(__import__("pathlib").Path(tmp) / "cfg-i")
    other = instance.pipe_name(__import__("pathlib").Path(tmp) / "cfg-j")
    check("I1 파이프 이름 — 설정 폴더마다 다르고 사용자 이름을 품는다", name != other and name.startswith("\\\\.\\pipe\\EquionDesk-"))
    if sys.platform != "win32":
        check("I2 Windows 가 아니면 넘기지 않는다(이 실행이 창을 띄운다)", instance.forward(name, folder) is False and instance.listen(name) is None)
        return
    check("I2 떠 있는 창이 없으면 넘기지 않는다(이 실행이 창을 띄운다)", instance.forward(name, folder) is False)
    receiver = instance.listen(name)
    got: list = []
    receiver.start(got.append)
    first = instance.forward(name, folder)
    second = instance.forward(name, None)
    time.sleep(0.3)
    check("I3 떠 있는 창에 폴더를 넘긴다 — 폴더 없이 부르면 창만 앞으로", first and second and got == [folder, None], str(got))


def run() -> int:
    RESULTS.clear()
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        folder = example(tmp)
        section_server(tmp, folder)
        section_worker(tmp, folder)
        section_terminal(tmp, folder)
        section_tabs(tmp, folder)
        section_reading(tmp, folder)
        section_watch(tmp, folder)
        section_bench(tmp)
        section_instance(tmp, folder)
    bad = [n for n, ok, _ in RESULTS if not ok]
    print(f"\nEquion Desk 앱 시험 {len(RESULTS) - len(bad)}/{len(RESULTS)}")
    return len(bad)


def test_suite() -> None:
    assert run() == 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(1 if run() else 0)
