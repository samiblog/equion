"""Equion Desk 시험 — 로컬 서버·작업 프로세스·터미널·프로젝트 탭·기록 읽기·감시·식 작업대·자료 작업대·분석(D0·D1·D2a·D2b). `uv run --package equion-desk pytest desk`.

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
        # 방금 고친 정의 파일을 감시가 알아채 '바깥 고침 적기'(scan)를 뒤에서 시킨다 — 그것이 끝나 조용해진 뒤에 본다
        session = state.session(pid)
        quiet_since, deadline = time.time(), time.time() + 20
        while time.time() < deadline and time.time() - quiet_since < 2.5:
            if session._scan_pending or w.busy_op is not None:
                quiet_since = time.time()
            time.sleep(0.05)
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
            out = subprocess.run(["tasklist", "/FI", f"PID eq {child}", "/NH"], capture_output=True, text=True, errors="replace").stdout or ""
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
        follows = s["term_follow"] is True and 'data-term-follow="true"' in c.get("/").text
        t2 = c.post("/api/settings", json={"term_follow": False}).json["client"]
        t3 = c.post("/api/settings", json={"term_follow": "dark"}).json["client"]
        check("F6-1 터미널 색 — 기본은 창의 바탕을 따르고, '늘 어둡게'(term_follow=false)는 첫 화면에 실려 온다. 형식이 틀리면 받지 않는다",
              follows and t2["term_follow"] is False and t3["term_follow"] is False and 'data-term-follow="false"' in c.get("/").text, str(t2))
        c.post("/api/settings", json={"term_follow": True})
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


def section_data(tmp: str) -> None:
    print("K. 자료 작업대·분석 — 세 층 한눈에·시리즈의 내력·받은 상자·만들기·견주기·바꾸기·등록부의 분석·남기기")
    from equion_desk.server import create_app

    folder = example(tmp, "data")
    state, pid = new_state(tmp, folder, "k.json")
    api = f"/api/p/{pid}"

    def read(*parts: str) -> str:
        with open(os.path.join(folder, *parts), encoding="utf-8") as f:
            return f.read()

    try:
        c = create_app(state).test_client()
        d = c.get(f"{api}/data").json
        first = d["current"]
        by = {s["name"]: s for s in d["series"]}
        check("K1 자료 한눈에 — 정의로 읽는 프로젝트, 지금 회차, 원자료 둘, 밀린 것 없음",
              d["mode"] == "defs" and first and [(v["id"], v["current"]) for v in d["vintages"]] == [(first, True)]
              and [s["name"] for s in d["sources"]] == ["na", "monthly"] and d["stale"] is None and d["pending"] is False
              and d["problems"] == [] and d["inbox"] == [] and d["span"] == ["1970Q1", "2019Q4"], str({k: d[k] for k in ("mode", "current", "stale", "pending", "problems", "span")}))
        na = d["sources"][0]
        check("K2 원자료 — 틀대로 읽은 구간·열·읽는 시리즈, 어느 파일을 어느 출처가 읽는지",
              na["file"] == "DATA/raw/toy_q.csv" and na["exists"] and na["freq"] == "Q" and na["rows"] == 200 and "CN" in na["series"] and "CNNSA" in na["columns"]
              and na["error"] is None and na["changed"] is False and "1970Q1" in na["note"]
              and [(f["file"], f["source"]) for f in d["raw"]] == [("DATA/raw/toy_m.csv", "monthly"), ("DATA/raw/toy_q.csv", "na")], str(na)[:300])
        check("K3 시리즈 — 만드는 법(열·변환·파생식)·구간·쓰는 식",
              by["CN"]["from"] == "na:CN" and "demand:CN" in by["CN"]["used_by"] and by["CNSA"]["how"].startswith("계절조정") and by["CNSA"]["column"] == "CNNSA"
              and by["RR"]["kind"] == "derived" and by["RR"]["from"] == "= R - PI" and by["RL"]["start"] == "1980Q1" and by["CN"]["n"] == 200
              and by["CN"]["missing"] == 0 and all(s["built"] for s in d["series"]) and by["IPQ"]["source"] == "monthly", str(by["CNSA"]))
        s = c.get(f"{api}/series?name=CNSA").json
        rr = c.get(f"{api}/series?name=RR").json
        check("K4 시리즈 하나 — 값과 내력(원자료 → 열 → 계절조정), 원자료 값과 겹쳐 보기, 파생식은 그 줄",
              len(s["period"]) == len(s["values"]) == 200 and [x["step"] for x in s["lineage"]] == ["원자료", "열", "계절조정"]
              and s["lineage"][0]["file"] == "DATA/raw/toy_q.csv" and s["raw"] and len(s["raw"]["values"]) == 200 and s["raw"]["values"][0] != s["values"][0]
              and rr["lineage"][0]["file"] == "DATA/derived.txt" and rr["lineage"][0]["text"] == "RR = R - PI" and not rr["raw"], str(s["lineage"]) + str(rr["lineage"]))
        check("K5 없는 시리즈·이름이 아닌 것은 거절", c.get(f"{api}/series?name=ZZ").status_code == 422 and c.get(f"{api}/series?name=a/b").status_code == 400)

        # 새 분기 자료가 받은 상자에 왔다 — 한 분기가 늘고 지난 분기의 값 하나가 고쳐졌다(개정). 틀이 다른 파일도 하나
        raw = os.path.join(folder, "DATA", "raw", "toy_q.csv")
        lines = read("DATA", "raw", "toy_q.csv").rstrip("\n").split("\n")
        cells = lines[-2].split(",")
        cells[1] = f"{float(cells[1]) * 1.02:.4f}"
        lines[-2] = ",".join(cells)
        lines.append(",".join(["2020Q1"] + [f"{float(v) * 1.01:.4f}" for v in lines[-1].split(",")[1:]]))
        inbox = os.path.join(folder, "DATA", "raw", "inbox")
        os.makedirs(inbox, exist_ok=True)
        with open(os.path.join(inbox, "toy_q_2026-12.csv"), "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(lines) + "\n")
        with open(os.path.join(inbox, "toy_q_bad.csv"), "w", encoding="utf-8", newline="\n") as f:
            f.write("period,CN,I\n2020Q1,1,2\n")
        d = c.get(f"{api}/data").json
        got = {os.path.basename(i["file"]): i for i in d["inbox"]}
        check("K6 받은 상자 — 이름으로 짝지은 원자료와 틀 검사(맞지 않는 파일은 까닭과 함께)",
              set(got) == {"toy_q_2026-12.csv", "toy_q_bad.csv"} and got["toy_q_2026-12.csv"]["source"] == "na" and got["toy_q_2026-12.csv"]["problems"] == []
              and got["toy_q_bad.csv"]["source"] == "na" and got["toy_q_bad.csv"]["problems"], str(d["inbox"])[:400])
        no_dialog = c.post(f"{api}/data/add", json={})
        outside = c.post(f"{api}/data/add", json={"inbox": "../../equion.toml", "source": "na"})
        missing = c.post(f"{api}/data/add", json={"inbox": "nope.csv", "source": "na"})
        check("K7 원자료 넣기 — 받은 상자의 파일만(바깥 경로·없는 파일은 거절), 파일 고르기는 창에서만",
              no_dialog.status_code == 501 and outside.status_code == 403 and missing.status_code == 404, f"{no_dialog.status_code} {outside.status_code} {missing.status_code}")
        before = read("DATA", "series.toml")
        refused = c.post(f"{api}/data/add", json={"inbox": "toy_q_bad.csv", "source": "na"}).json["result"]
        check("K8 틀이 맞지 않는 파일은 넣지 않는다 — 아무것도 바뀌지 않고 받은 상자에 그대로",
              refused["problems"] and refused["copied"] is False and refused["removed"] is False and os.path.isfile(os.path.join(inbox, "toy_q_bad.csv"))
              and read("DATA", "series.toml") == before and not os.path.exists(os.path.join(folder, "DATA", "raw", "toy_q_bad.csv")), str(refused))
        os.remove(os.path.join(inbox, "toy_q_bad.csv"))
        added = c.post(f"{api}/data/add", json={"inbox": "toy_q_2026-12.csv", "source": "na"}).json["result"]
        d = c.get(f"{api}/data").json
        check("K9 받은 파일을 넣는다 — DATA/raw/ 로 들어가 출처가 그 파일을 읽고, 받은 상자에서는 빠진다. 옛 파일은 남는다",
              added["file"] == "DATA/raw/toy_q_2026-12.csv" and added["copied"] and added["removed"] and added["previous"] == "DATA/raw/toy_q.csv"
              and not os.path.exists(os.path.join(inbox, "toy_q_2026-12.csv")) and os.path.isfile(raw) and d["inbox"] == []
              and d["sources"][0]["file"] == "DATA/raw/toy_q_2026-12.csv" and d["sources"][0]["changed"]
              and ("DATA/raw/toy_q.csv", None) in [(f["file"], f["source"]) for f in d["raw"]], str(added))
        check("K10 넣고 나면 무엇이 바뀌었는지와 함께 '자료 만들기'를 권한다(저절로 만들지 않는다)",
              d["stale"] == {"definitions": ["DATA/series.toml"], "sources": ["na"]} and d["pending"] is True and d["current"] == first, str(d["stale"]))
        built = c.post(f"{api}/data/build", json={}).json["result"]
        second = built["id"]
        d = c.get(f"{api}/data").json
        check("K11 자료 만들기 — 새 회차가 생기지만 지금 회차는 그대로(바꾸는 것은 따로), 차이를 함께 돌려준다",
              built["created"] and second != first and built["current"] == first and built["record"] == f"data:{second}" and built["span"] == ["1970Q1", "2020Q1"]
              and built["diff"]["a"] == first and built["diff"]["b"] == second and d["current"] == first and d["stale"] and d["pending"] is False
              and [v["id"] for v in d["vintages"]] == [first, second], str({k: built[k] for k in ("id", "created", "current", "span")}) + str(d["pending"]))
        df = c.get(f"{api}/data/diff?a={first}&b={second}").json
        row = next(r for r in df["rows"] if r["name"] == "CN")
        check("K12 견주기 — 새 값·고쳐진 값(개정)과 그것을 쓰는 식·모형",
              df["extended"] >= 10 and df["revised"] >= 1 and row["new"] == 1 and row["revised"] == 1 and row["first"] == row["last"] == "2019Q3"
              and abs(row["max_pct"] - 2.0) < 0.01 and "demand:CN" in df["impact"]["parts"] and "main" in df["impact"]["models"] and "IPQ" in df["unchanged"]
              and c.get(f"{api}/data/diff?a=nope&b={second}").status_code >= 400, str(row) + str(df["impact"]["parts"]))
        used = c.post(f"{api}/data/use", json={"vintage": second})
        d = c.get(f"{api}/data").json
        o = c.get(f"{api}/overview").json["overview"]
        check("K13 이 회차로 바꾸기 — equion.toml 의 회차가 바뀌고 개요·자료가 새 회차를 가리킨다",
              used.json["result"] == {"vintage": second, "previous": first} and d["current"] == second and d["stale"] is None and d["pending"] is False
              and d["span"] == ["1970Q1", "2020Q1"] and o["vintage"]["id"] == second and f'vintage = "{second}"' in read("equion.toml"), str(used.json) + str(o["vintage"]))
        again = c.post(f"{api}/data/build", json={}).json["result"]
        nope = c.post(f"{api}/data/use", json={"vintage": "nope"})
        check("K14 내용이 같으면 새로 만들지 않는다 · 없는 회차로는 바꾸지 못한다",
              again["created"] is False and again["id"] == second and nope.status_code >= 400 and "nope" in nope.json["error"], str(again)[:200])
        mark = d["fingerprint"]
        with open(os.path.join(folder, "DATA", "series.toml"), "a", encoding="utf-8", newline="\n") as f:
            f.write("\n# 값과 무관한 주석 한 줄\n")
        d = c.get(f"{api}/data").json
        noop = c.post(f"{api}/data/build", json={}).json["result"]
        check("K14-1 정의의 글만 바뀌면(값은 같다) 바뀌었다고 알리되 만들어도 새 회차가 생기지 않는다 — 화면이 기억할 지문이 그때의 정의를 가리킨다",
              d["stale"] == {"definitions": ["DATA/series.toml"], "sources": []} and d["pending"] is True and d["fingerprint"] and d["fingerprint"] != mark
              and noop["created"] is False and noop["id"] == second and c.get(f"{api}/data").json["fingerprint"] == d["fingerprint"], str(noop)[:200])

        a = c.get(f"{api}/analyses").json
        spec = {x["name"]: x for x in a["analyses"]}
        check("K15 분석 등록부 — 분석마다 대상·옵션·만드는 것, 대상으로 고를 이름들",
              {"summary", "unitroot", "coint", "diag", "seas", "genr", "ecm", "var", "system"} <= set(spec) and spec["seas"]["makes"] == "definition"
              and spec["ecm"]["makes"] == "candidate" and spec["summary"]["makes"] is None and spec["seas"]["targets"] == ["series"]
              and [x["name"] for x in spec["unitroot"]["options"]] == ["trend", "lags", "ic", "maxlag"] and spec["unitroot"]["options"][0]["choices"] == ["n", "c", "ct"]
              and all(x["label"] and x["group"] and x["help"] and x["target_labels"] for x in a["analyses"])
              and "CN" in a["names"]["series"] and a["names"]["group"] == ["core"] and "demand:CN" in a["names"]["part"] and "main" in a["names"]["model"]
              and "demand" in a["names"]["block"], str(a["names"]))
        u = c.post(f"{api}/an", json={"analysis": "unitroot", "target": "core", "options": {"trend": "ct", "ic": "bic"}}).json["result"]
        rec = c.get(f"{api}/record?id={u['id']}").json
        check("K16 분석 실행 — 기록(an:)이 남고, 명령 글에는 기본값과 다른 옵션만 적힌다",
              u["id"].startswith("an:unitroot_") and u["command"] == "equion an unitroot core --trend ct" and rec["meta"]["who"] == "desk"
              and rec["meta"]["options"]["trend"] == "ct" and rec["meta"]["data"]["id"] == second and "단위근" in rec["summary"], str(u)[:300])
        bad1 = c.post(f"{api}/an", json={"analysis": "nope", "target": "CN"})
        bad2 = c.post(f"{api}/an", json={"analysis": "unitroot", "target": "CN", "options": {"trend": "zz"}})
        bad3 = c.post(f"{api}/an", json={"analysis": "unitroot", "target": "  "})
        check("K17 없는 분석·받을 수 없는 옵션 값·빈 대상은 거절(까닭과 함께)",
              bad1.status_code >= 400 and "nope" in bad1.json["error"] and bad2.status_code >= 400 and "trend" in bad2.json["error"] and bad3.status_code >= 400,
              f"{bad1.status_code} {bad2.status_code} {bad3.status_code}")
        sa = c.post(f"{api}/an", json={"analysis": "seas", "target": "CN", "options": {"model": "multiplicative"}}).json["result"]
        before = read("DATA", "series.toml")
        kept = c.post(f"{api}/an/keep", json={"record": sa["id"], "name": "CN_SA"}).json["result"]
        d = c.get(f"{api}/data").json
        new = next(s for s in d["series"] if s["name"] == "CN_SA")
        check("K18 남기기(정의) — 미리 본 계절조정이 series.toml 에 적히고 바뀜 기록이 남는다. 값은 아직 없다 — 자료 만들기를 권한다",
              sa["command"] == "equion an seas CN --model multiplicative" and sa["makes"] == "definition" and kept["kind"] == "definition" and kept["change"]
              and "[series.CN_SA]" in read("DATA", "series.toml") and "[series.CN_SA]" not in before and new["built"] is False
              and d["stale"] == {"definitions": ["DATA/series.toml"], "sources": []} and d["pending"] is True, str(kept))
        dup = c.post(f"{api}/an/keep", json={"record": sa["id"], "name": "CN_SA"})
        check("K19 같은 이름으로 다시 남기지 못한다(까닭과 함께)", dup.status_code >= 400 and "CN_SA" in dup.json["error"], str(dup.json)[:200])
        g = c.post(f"{api}/an", json={"analysis": "genr", "target": "GAP = Y - CN - I"}).json["result"]
        kept_g = c.post(f"{api}/an/keep", json={"record": g["id"]}).json["result"]
        check("K20 파생 — 명령 글의 따옴표, 남기면 derived.txt 에 한 줄(어느 기록에서 왔는지와 함께)",
              g["command"] == "equion an genr 'GAP = Y - CN - I'" and kept_g["kind"] == "derived" and f"GAP = Y - CN - I   # {g['id']}" in read("DATA", "derived.txt"), str(kept_g))
        e = c.post(f"{api}/an", json={"analysis": "ecm", "target": "log(CN) log(Y)"}).json["result"]
        defs = read("DATA", "series.toml"), read("DATA", "derived.txt"), read("EQUATIONS", "demand.txt")
        kept_e = c.post(f"{api}/an/keep", json={"record": e["id"]}).json["result"]
        check("K21 남기기(식 후보) — 추정 기록(est:)이 생긴다, 정의 파일은 그대로",
              kept_e["kind"] == "candidate" and len(kept_e["records"]) == 1 and kept_e["records"][0].startswith("est:") and kept_e["change"] is None
              and c.get(f"{api}/record?id={kept_e['records'][0]}").status_code == 200
              and defs == (read("DATA", "series.toml"), read("DATA", "derived.txt"), read("EQUATIONS", "demand.txt")), str(kept_e))
        view = c.post(f"{api}/an/keep", json={"record": u["id"]})
        check("K22 보는 분석은 남길 것이 없다", view.status_code >= 400 and "남길 것이 없습니다" in view.json["error"], str(view.json)[:200])
        rebuilt = c.post(f"{api}/data/build", json={}).json["result"]
        c.post(f"{api}/data/use", json={"vintage": rebuilt["id"]})
        d = c.get(f"{api}/data").json
        by = {s["name"]: s for s in d["series"]}
        check("K23 남긴 정의로 자료를 다시 만들면 새 시리즈가 회차에 들어간다",
              rebuilt["created"] and d["current"] == rebuilt["id"] and by["CN_SA"]["built"] and by["CN_SA"]["n"] == 201 and by["GAP"]["built"] and d["stale"] is None,
              str(by.get("CN_SA")))
        jobs = [(x["state"], x.get("record")) for x in state.feed.read(0, 0)["events"] if x["type"] == "job" and x["state"] != "start"]
        check("K24 작업 줄 — 자료 만들기·분석은 기록 이름을 달고 끝난다(카드로 가는 길), 거절된 것은 오류로",
              ("done", f"data:{second}") in jobs and ("done", u["id"]) in jobs and any(st == "error" for st, _ in jobs), str(jobs)[:400])
    finally:
        state.close()

    # 자료 파일 하나를 그대로 읽는 프로젝트(정의·회차 없음)
    plain = example(tmp, "plain")
    path = os.path.join(plain, "equion.toml")
    with open(path, encoding="utf-8") as f:
        text = f.read()
    text = re.sub(r'(?m)^(series|derived|vintage) = .*\n', "", text).replace("[data]", '[data]\nfile = "DATA/raw/toy_q.csv"', 1)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    state, pid = new_state(tmp, plain, "k2.json")
    try:
        c = create_app(state).test_client()
        d = c.get(f"/api/p/{pid}/data").json
        refused = c.post(f"/api/p/{pid}/data/build", json={})
        check("K25 자료 파일 하나를 그대로 읽는 프로젝트 — 시리즈만 보이고(회차·원자료 없음) 자료 만들기는 까닭과 함께 거절",
              d["mode"] == "file" and d["vintages"] == [] and d["sources"] == [] and "CN" in [s["name"] for s in d["series"]] and d["span"] == ["1970Q1", "2019Q4"]
              and refused.status_code >= 400 and refused.json["error"], str({k: d.get(k) for k in ("mode", "span", "data_file")}) + str(refused.json)[:200])
    finally:
        state.close()


def section_import(tmp: str) -> None:
    print("L. 불러오기 — 원자료 미리보기·이 파일을 읽는 출처·정의 쓰기(무엇이 바뀌는지 먼저 → 저장)")
    from equion_desk.server import create_app

    folder = example(tmp, "imp")
    sf = os.path.join(folder, "DATA", "series.toml")

    def read(path: str = sf) -> str:
        with open(path, encoding="utf-8") as f:
            return f.read()

    # 제목 줄·단위 줄·결측 표시·천 단위가 있는 원자료(통계표 꼴)
    with open(os.path.join(folder, "DATA", "raw", "toy_q.csv"), encoding="utf-8") as f:
        rows = [ln.split(",") for ln in f.read().rstrip("\n").split("\n")[1:13]]
    cells = [[r[0][:4] + "년 " + r[0][5] + "/4분기", f'"1,{float(r[1]):.1f}"', r[2], r[4]] for r in rows]
    cells[2][1], cells[3][2] = "-", "…"
    with open(os.path.join(folder, "DATA", "raw", "kr.csv"), "w", encoding="utf-8", newline="\n") as f:
        f.write("표 1. 지출(가상)\n시점,민간소비,투자,GDP\n,십억원,십억원,십억원\n" + "\n".join(",".join(c) for c in cells) + "\n")
    os.makedirs(os.path.join(folder, "DATA", "raw", "inbox"), exist_ok=True)
    with open(os.path.join(folder, "DATA", "raw", "inbox", "later.csv"), "w", encoding="utf-8", newline="\n") as f:
        f.write("period,A1\n2000Q1,1\n2000Q2,2\n2000Q3,3\n2000Q4,4\n2001Q1,5\n")
    frame = {"sheet": "", "header_row": 2, "unit_row": 3, "time_col": "", "missing": ["-", "…"], "thousands": ",", "freq": ""}
    state, pid = new_state(tmp, folder, "l.json")
    api = f"/api/p/{pid}"
    try:
        c = create_app(state).test_client()
        v = c.post(f"{api}/data/preview", json={"file": "DATA/raw/toy_q.csv"}).json
        check("L1 이미 읽는 파일 — 그 출처의 틀로 읽고, 열마다 짝지은 시리즈(변환까지)와 이미 쓰는 이름을 함께 준다",
              v["ok"] and v["freq"] == "Q" and v["project_freq"] == "Q" and v["source"]["name"] == "na" and v["source"]["frame"]["header_row"] == 1
              and v["mapped"]["CN"]["name"] == "CN" and v["mapped"]["CNNSA"] == {**v["mapped"]["CNNSA"], "name": "CNSA", "seas": "stl:multiplicative"}
              and {"RR", "IPQ", "CN"} <= set(v["taken"]) and len(v["grid"]) == 40 and v["grid"][0][1] == "CN" and [s["name"] for s in v["sources"]] == ["na", "monthly"],
              str(v.get("source")) + str(v.get("mapped", {}).get("CNNSA")))
        raw = c.post(f"{api}/data/preview", json={"file": "DATA/raw/kr.csv", "rows": 6}).json
        ok = c.post(f"{api}/data/preview", json={"file": "DATA/raw/kr.csv", "frame": frame}).json
        check("L2 새 파일 — 틀이 맞지 않으면 읽은 그대로의 줄과 까닭, 틀을 맞추면 열·단위·결측으로 읽은 칸",
              raw["ok"] is False and raw["error"] and raw["source"] is None and len(raw["grid"]) == 6 and raw["grid"][0][0].startswith("표 1")
              and raw["grid"][1] == ["시점", "민간소비", "투자", "GDP"] and ok["ok"] and ok["span"] == ["1970Q1", "1972Q4"]
              and [(x["name"], x["unit"], x["missing"], x["name_ok"]) for x in ok["columns"]] == [("민간소비", "십억원", 1, False), ("투자", "십억원", 1, False), ("GDP", "십억원", 0, True)]
              and ok["time_col"] == 0 and ok["bad_cells"] == [], f"{raw.get('error')} {ok.get('columns')}")
        loose = c.post(f"{api}/data/preview", json={"file": "DATA/raw/kr.csv", "frame": {**frame, "thousands": "", "missing": []}}).json
        check("L3 틀을 짐작할 재료 — 숫자가 아닌 칸(천 단위 쉼표·결측 표시)을 칸 위치와 글자로 알린다",
              loose["ok"] and len(loose["bad_cells"]) == 13 and any("1,2" in x for x in loose["bad_cells"]) and any(x.endswith("'-'") for x in loose["bad_cells"]),
              str(loose.get("bad_cells"))[:200])
        one = c.post(f"{api}/data/preview", json={"file": "DATA/raw/toy_m.csv", "rows": 1, "series": {"column": "IP", "convert": "mean", "seas": "stl"}}).json
        bad = c.post(f"{api}/data/preview", json={"file": "DATA/raw/toy_m.csv", "series": {"column": "IP"}}).json
        check("L4 열 하나를 변환대로 만들어 본다(월 → 분기 평균 → 계절조정) — 변환이 빠지면 오류가 아니라 까닭을 돌려준다(표는 그대로)",
              one["series"]["freq"] == "Q" and one["series"]["source_freq"] == "M" and len(one["series"]["values"]) == 80 and len(one["series"]["raw"]) == 240
              and len(one["series"]["implicit"]) == 2 and one["series_error"] is None and bad["ok"] and bad["series"] is None and "convert" in bad["series_error"],
              str(one.get("series", {}).get("implicit")) + str(bad.get("series_error")))
        codes = [c.post(f"{api}/data/preview", json=j).status_code for j in (
            {"file": "equion.toml"}, {"file": "DATA/series.toml"}, {"file": "../x.csv"}, {"file": "DATA/raw/nope.csv"}, {},
            {"file": "DATA/raw/kr.csv", "rows": 100000}, {"file": "DATA/raw/kr.csv", "frame": {"header_row": "2;x"}},
            {"file": "DATA/raw/kr.csv", "frame": {"missing": "-"}}, {"file": "DATA/raw/kr.csv", "series": {"unit": "x"}})]
        inbox_ok = c.post(f"{api}/data/preview", json={"file": "DATA/raw/inbox/later.csv"}).json
        check("L5 원자료 폴더(DATA/raw/)의 파일만 — 다른 파일·바깥 경로·틀린 형식의 틀은 거절, 받은 상자의 파일은 미리 볼 수 있다",
              codes == [404, 404, 403, 404, 400, 400, 400, 400, 400] and inbox_ok["ok"] and inbox_ok["columns"][0]["name"] == "A1", str(codes))

        want = {"KCN": {"column": "민간소비", "unit": "십억원", "desc": "민간소비"}, "KGDP": {"column": "GDP"}}
        before, n_changes = read(), len(c.get(f"{api}/changes").json["changes"])
        plan = c.post(f"{api}/data/define", json={"source": "kr", "file": "DATA/raw/kr.csv", "frame": frame, "series": want, "dry": True}).json
        jobs = [e for e in state.feed.read(0, 0)["events"] if e["type"] == "job"]
        check("L6 저장하기 전에 — 무엇이 적히는지(차이)와 같은 일을 하는 명령. 아무것도 쓰지 않고 작업 줄에도 올리지 않는다",
              plan["new_source"] and plan["added"] == ["KCN", "KGDP"] and plan["same"] is False and plan["path"] == "DATA/series.toml"
              and "+[source.kr]" in plan["diff"] and '+from = "kr:민간소비"' in plan["diff"] and "+header_row = 2" in plan["diff"]
              and plan["command"].startswith("equion data define kr --file DATA/raw/kr.csv --header-row 2 --unit-row 3 --missing - --missing '…' --thousands , --series")
              and "--set 'KCN.unit=십억원'" in plan["command"] and read() == before and len(c.get(f"{api}/changes").json["changes"]) == n_changes and jobs == [],
              plan.get("command", "") + plan.get("diff", "")[:200])
        done = c.post(f"{api}/data/define", json={"source": "kr", "file": "DATA/raw/kr.csv", "frame": frame, "series": want}).json["result"]
        change = c.get(f"{api}/change?id={done['change']}").json
        d = c.get(f"{api}/data").json
        by = {x["name"]: x for x in d["series"]}
        check("L7 정의에 저장 — series.toml 에 출처(틀)와 시리즈가 적히고(주석은 그대로) 바뀜 기록에 'Desk · 명령 그대로'로 남는다",
              done["added"] == ["KCN", "KGDP"] and done["command"] == plan["command"] and "# 분기 거시 자료" in read() and "[series.KCN]" in read()
              and change["who"] == "desk" and change["how"] == plan["command"] and [f["path"] for f in change["files"]] == ["DATA/series.toml"]
              and by["KCN"]["built"] is False and by["KCN"]["source"] == "kr" and d["stale"]["definitions"] == ["DATA/series.toml"]
              and [s["name"] for s in d["sources"]] == ["na", "monthly", "kr"], str(done))
        built = c.post(f"{api}/data/build", json={}).json["result"]
        c.post(f"{api}/data/use", json={"vintage": built["id"]})
        s = c.get(f"{api}/series?name=KCN").json
        check("L8 이어서 자료를 만들면 새 시리즈가 회차에 — 천 단위는 숫자로, 결측 표시는 결측으로",
              built["created"] and abs(s["values"][0] - (1000 + round(float(rows[0][1]), 1))) < 1e-6 and s["values"][2] is None and len(s["period"]) == 12
              and [x["step"] for x in s["lineage"]][:2] == ["원자료", "열"], str(s["values"][:3]))
        again = c.post(f"{api}/data/preview", json={"file": "DATA/raw/kr.csv"}).json
        edit = c.post(f"{api}/data/define", json={"source": "kr", "file": "DATA/raw/kr.csv", "frame": frame, "series": {"KCN": {"column": "민간소비", "desc": "민간소비(실질)", "unit": ""},
                                                                                                             "KI": {"column": "투자"}}}).json["result"]
        same = c.post(f"{api}/data/define", json={"source": "kr", "file": "DATA/raw/kr.csv", "frame": frame, "series": {}, "dry": True}).json
        check("L9 다시 열면 저장한 틀과 짝지은 시리즈가 그대로 — 있는 시리즈는 고친 키만, 새 열은 더한다. 바뀐 것이 없으면 그렇게 알린다",
              again["ok"] and again["source"] == {"name": "kr", "frame": {**frame, "sheet": None, "unit_row": 3, "time_col": None, "thousands": ",", "freq": None,
                                                                "time_axis": "rows", "time_row": None, "name_col": None, "unit_col": None}}
              and again["mapped"]["민간소비"]["name"] == "KCN" and edit["changed"] == ["KCN"] and edit["added"] == ["KI"] and 'desc = "민간소비(실질)"' in read()
              and 'unit = "십억원"\ndesc = "민간소비(실질)"' not in read() and same["same"] is True, str(again.get("source")) + str(edit))
        text = read()
        r1 = c.post(f"{api}/data/define", json={"source": "kr", "file": "DATA/raw/kr.csv", "frame": frame, "series": {"KX": {"column": "없는열"}}})
        r2 = c.post(f"{api}/data/define", json={"source": "kr", "file": "DATA/raw/kr.csv", "frame": {**frame, "header_row": 1}, "series": {}})
        r3 = c.post(f"{api}/data/define", json={"source": "9x", "file": "DATA/raw/kr.csv", "series": {"A1": {"column": "GDP"}}})
        r4 = c.post(f"{api}/data/define", json={"source": "kr", "file": "DATA/raw/inbox/later.csv", "series": {"A1": {"column": "A1"}}})
        r5 = c.post(f"{api}/data/define", json={"source": "kr", "file": "DATA/raw/kr.csv", "frame": frame, "series": {"log": {"column": "GDP"}}})
        check("L10 문제가 있으면 아무것도 쓰지 않는다 — 없는 열·읽을 수 없게 되는 틀·이름·받은 상자의 파일(먼저 넣어야 한다)",
              r1.status_code == 422 and "없는열" in r1.json["error"] and r2.status_code == 422 and r3.status_code == 422 and r4.status_code == 404
              and r5.status_code == 422 and read() == text, f"{r1.status_code} {r2.status_code} {r3.status_code} {r4.status_code} {r5.status_code}")
        events = [(e["state"], e["label"]) for e in state.feed.read(0, 0)["events"] if e["type"] == "job" and e["state"] != "start"]
        check("L11 작업 줄 — 저장은 올리고(정의 저장 kr) 미리보기는 올리지 않는다", ("done", "정의 저장 kr") in events and not any("미리" in label for _s, label in events), str(events))
    finally:
        state.close()

    plain = os.path.join(tmp, "plain")
    state, pid = new_state(tmp, plain, "l2.json")
    try:
        c = create_app(state).test_client()
        v = c.post(f"/api/p/{pid}/data/preview", json={"file": "DATA/raw/toy_q.csv"}).json
        r = c.post(f"/api/p/{pid}/data/define", json={"source": "na", "file": "DATA/raw/toy_q.csv", "series": {"A1": {"column": "CN"}}})
        check("L12 자료 파일 하나를 그대로 읽는 프로젝트 — 미리보기는 되고(정의 없음) 정의 쓰기는 까닭과 함께 거절",
              v["ok"] and v["defs"] is False and v["source"] is None and r.status_code == 422 and "자료 정의" in r.json["error"], str(r.json)[:200])
    finally:
        state.close()


def section_model(tmp: str) -> None:
    print("N. 모형 작업대·흐름 화면 — 조립 보기·모형과 블록 정의·글로 고치기·과거 재현 보기·원인 따라가기·스크립트·회차 바꾼 뒤 할 일")
    from equion_desk.server import create_app

    folder = example(tmp, "model")

    def read(*parts: str) -> str:
        with open(os.path.join(folder, *parts), encoding="utf-8") as f:
            return f.read()

    state, pid = new_state(tmp, folder, "n.json")
    api = f"/api/p/{pid}"
    try:
        c = create_app(state).test_client()
        a = c.get(f"{api}/assembly?model=main").json
        r = a["report"]
        check("N1 조립 보기 — 구성·내생과 외생·블록 사이의 연결·풀이 순서·외생의 자료 끝·함께 쓰는 모형",
              a["model"] == "main" and a["spec"] == {"name": "main", "desc": "수요 + 물가 + 금융", "blocks": ["price", "finance"], "include": ["core"], "exclude": []}
              and r["ok"] and r["composition"] == "main = core(demand) + price + finance" and r["endogenous"] == ["CN", "I", "Y", "P", "RL", "M2"]
              and r["exogenous"] == ["G", "POIL", "R"] and ["demand", "Y", "price"] in r["links"] and any(b["type"] == "동시" and b["variables"] == ["CN", "Y"] for b in r["blocks"])
              and r["exogenous_data"]["G"]["last"] == "2019Q4" and r["used_by"]["demand"] == ["core", "main_fixrl"] and r["includes"] == {"core": ["demand"]}
              and r["parts"][0] == {**r["parts"][0], "id": "demand:CN", "block": "demand", "target": "CN", "adopted": None} and a["command"] == "equion assemble main", str(a["spec"]))
        fix = c.get(f"{api}/assembly?model=main_fixrl").json["report"]
        none = c.get(f"{api}/assembly?model=nope").json
        check("N2 뺀 식의 목표는 외생이 된다 · 없는 모형은 까닭과 함께", fix["excluded"] == ["finance:RL"] and "RL" in fix["exogenous"] and "RL" not in fix["endogenous"]
              and none["report"] is None and "nope" in none["error"] and c.get(f"{api}/assembly?model=a/b").status_code == 400)

        toml = read("equion.toml")
        plan = c.post(f"{api}/model/define", json={"name": "dp", "blocks": ["demand", "price"], "desc": "수요 + 물가", "dry": True}).json
        wrote_nothing = read("equion.toml") == toml          # 미리 보는 것만으로는 쓰지 않는다
        done = c.post(f"{api}/model/define", json={"name": "dp", "blocks": ["demand", "price"], "desc": "수요 + 물가"}).json["result"]
        change = c.get(f"{api}/change?id={done['change']}").json
        check("N3 새 모형 — 먼저 equion.toml 의 차이와 명령을 보이고(쓰지 않는다), 저장하면 바뀜 기록에 'Desk · 명령 그대로'",
              plan["new"] and plan["same"] is False and "+[model.dp]" in plan["diff"] and plan["command"] == "equion model define dp --blocks demand,price --desc '수요 + 물가'"
              and done["new"] and done["command"] == plan["command"] and change["who"] == "desk" and change["how"] == plan["command"]
              and '[model.dp]' in read("equion.toml") and "# 모형 안에 모형" in read("equion.toml") and wrote_nothing, plan.get("command", ""))
        check("N3-1 새 모형이 개요와 조립에 바로 보인다", "dp" in [m["name"] for m in c.get(f"{api}/overview").json["overview"]["models"]]
              and c.get(f"{api}/assembly?model=dp").json["report"]["ok"])
        edit = c.post(f"{api}/model/define", json={"name": "dp", "exclude": ["demand:I"]}).json["result"]
        codes = [c.post(f"{api}/model/define", json=j).status_code for j in ({"name": "x", "blocks": ["nope"]}, {"name": "x", "blocks": "demand"}, {"blocks": ["demand"]},
                                                                             {"name": "x", "exclude": ["demand"]}, {"name": "demand", "blocks": ["price"]})]
        check("N4 모형 고치기 — 준 키만(뺄 식) · 없는 블록·블록과 같은 이름은 까닭과 함께 거절, 꼴이 틀린 값은 받지 않는다",
              not edit["new"] and c.get(f"{api}/assembly?model=dp").json["report"]["excluded"] == ["demand:I"] and codes == [422, 400, 400, 400, 422], str(codes))
        bplan = c.post(f"{api}/block/define", json={"name": "labor", "desc": "노동", "dry": True}).json
        not_yet = not os.path.exists(os.path.join(folder, "EQUATIONS", "labor.txt")) and "labor" not in read("equion.toml")
        bdone = c.post(f"{api}/block/define", json={"name": "labor", "desc": "노동"}).json["result"]
        bchange = c.get(f"{api}/change?id={bdone['change']}").json
        check("N5 새 블록 — 먼저 무엇이 생기는지(새 파일·설정의 줄)를 보인다. 쓰지 않는다",
              bplan["new"] and bplan["files"] == ["EQUATIONS/labor.txt"] and "+labor = " in bplan["diff"] and not_yet, str(bplan)[:200])
        check("N5-1 저장하면 빈 블록 파일을 함께 만든다(바뀜 기록 하나에 두 파일)", bdone["files"] == ["EQUATIONS/labor.txt"] and read("EQUATIONS", "labor.txt").startswith("# 노동 블록")
              and sorted(f["path"] for f in bchange["files"]) == ["EQUATIONS/labor.txt", "equion.toml"] and bdone["command"] == "equion block define labor --desc '노동'"
              and "labor" in [b["name"] for b in c.get(f"{api}/overview").json["overview"]["blocks"]])

        text = read("EQUATIONS", "labor.txt")
        bad = c.post(f"{api}/text/check", json={"path": "EQUATIONS/labor.txt", "text": text + "N c Y LF   # 고용\nW c P (\nN c Y   # 겹침\n"}).json
        cfg = c.post(f"{api}/text/check", json={"path": "equion.toml", "text": read("equion.toml") + "\n[model.zz]\nblocks = ['nope']\n"}).json
        syn = c.post(f"{api}/text/check", json={"path": "SCENARIOS/oil20.toml", "text": "a = 1\nb = [1,\nc"}).json
        good = c.post(f"{api}/text/check", json={"path": "EQUATIONS/labor.txt", "text": text + "N c Y CN   # 고용(가상)\n"}).json
        check("N6 치는 동안의 검사 — 블록 파일은 줄마다(문법·겹친 목표), 설정은 검사까지, TOML 문법은 줄 번호와 함께. 쓰지 않는다",
              bad["kind"] == "block" and [(x["line"], "괄호" in x["text"] or "겹칩니다" in x["text"]) for x in bad["problems"]] == [(3, True), (4, True)]
              and cfg["kind"] == "toml" and "없는 블록 'nope'" in cfg["problems"][0]["text"] and syn["problems"][0]["line"] == 3 and good["problems"] == []
              and read("EQUATIONS", "labor.txt") == text, str(bad["problems"]) + str(syn["problems"]))
        w = c.post(f"{api}/text/write", json={"path": "EQUATIONS/labor.txt", "text": text + "N c Y CN   # 고용(가상)\r\n"})
        wchange = c.get(f"{api}/change?id={w.json['result']['change']}").json
        codes = [c.post(f"{api}/text/write", json=j).status_code for j in ({"path": "README.md", "text": "x"}, {"path": "../x.txt", "text": "x"}, {"path": "EQUATIONS/none.txt", "text": "x"},
                                                                          {"path": "EQUATIONS/labor.txt"}, {"path": "DATA/raw/toy_q.csv", "text": "x"})]
        same = c.post(f"{api}/text/write", json={"path": "EQUATIONS/labor.txt", "text": read("EQUATIONS", "labor.txt")}).json["result"]
        check("N7 글로 고쳐 저장 — 정의 파일만(다른 파일·바깥 경로·없는 파일·원자료는 거절), 줄바꿈은 LF 로, 바뀜 기록에 'Desk'",
              w.status_code == 200 and read("EQUATIONS", "labor.txt").endswith("N c Y CN   # 고용(가상)\n") and "\r" not in read("EQUATIONS", "labor.txt")
              and wchange["who"] == "desk" and wchange["how"] == "Desk 에서 고침" and codes == [422, 403, 404, 400, 422] and same["change"] is None, str(codes))
        parts = [p["id"] for b in c.get(f"{api}/overview").json["overview"]["blocks"] for p in b["parts"]]
        check("N8 고친 블록 파일의 식이 바로 부품이 된다", "labor:N" in parts)

        h = c.post(f"{api}/hs/run", json={"target": "main"}).json["result"]
        hb = c.post(f"{api}/hs/run", json={"target": "demand", "start": "2010Q1", "end": "2019Q4", "mode": "static"}).json["result"]
        check("N9 과거 재현 — 모형, 그리고 블록만(범위·방식) — 기록의 명령이 터미널에서 치는 글 그대로",
              h["id"].startswith("hs:") and h["command"] == "equion hs main" and h["range"] == ["2005Q1", "2019Q4"] and h["counts"]["ok"] == 60
              and hb["command"] == "equion hs demand --range 2010Q1:2019Q4 --mode static" and hb["target"] == "demand" and hb["mode"] == "static" and hb["range"] == ["2010Q1", "2019Q4"],
              str(hb.get("command")))
        v = c.get(f"{api}/hs/view?id={h['id']}").json
        names = [x["name"] for x in v["stats"]]
        check("N10 과거 재현 기록 보기 — 변수마다 적합도, 기간마다 풀이 상태, 어느 계수로 풀었나",
              sorted(names) == ["CN", "I", "M2", "P", "RL", "Y"] and all(x["rmspe"] is not None and x["n"] == 60 for x in v["stats"]) and len(v["status"]) == 60
              and v["status"][0] == {**v["status"][0], "period": "2005Q1", "status": "ok"} and v["parts"][0]["source"] == "estimated" and v["meta"]["counts"]["ok"] == 60
              and v["vintage"] and len(v["meta"]["implicit"]) >= 1 and c.get(f"{api}/hs/view?id=est:x").status_code == 400 and c.get(f"{api}/hs/view?id=hs:nope").status_code == 422,
              str(v["stats"][:1]))
        ser = c.get(f"{api}/hs/series?id={h['id']}&names=Y,P,ZZ").json
        check("N11 변수의 풀린 값과 실측 — 없는 이름은 건너뛴다", len(ser["period"]) == 60 and ser["period"][0] == "2005Q1" and sorted(ser["series"]) == ["P", "Y"]
              and len(ser["series"]["Y"]["solved"]) == len(ser["series"]["Y"]["actual"]) == 60 and ser["series"]["Y"]["solved"][0] != ser["series"]["Y"]["actual"][0]
              and c.get(f"{api}/hs/series?id={h['id']}&names=").status_code == 400)
        tp = c.get(f"{api}/trace?id={h['id']}&name=P").json
        ty = c.get(f"{api}/trace?id={h['id']}&name=Y").json
        tx = c.get(f"{api}/trace?id={h['id']}&name=POIL").json
        check("N12 원인 따라가기 — 식의 입력마다 내생이면 이 풀이에서의 오차, 외생이면 실측. 항등식은 입력에서, 외생 변수는 오차가 없다",
              tp["part"]["id"] == "price:P" and tp["part"]["kind"] == "equation" and tp["own"]["rmspe"] > 0 and tp["self_lag"]
              and [(x["name"], x["endogenous"], x["block"]) for x in tp["inputs"]] == [("Y", True, "demand"), ("POIL", False, None)] and tp["inputs"][0]["rmspe"] > 0
              and tp["inputs"][1]["rmspe"] is None and tp["solo"] is None and ty["part"]["kind"] == "identity" and [x["name"] for x in ty["inputs"]][-1] == "G"
              and ty["inputs"][0]["rmspe"] >= ty["inputs"][1]["rmspe"] and tx["part"] is None and "외생" in tx["note"], str(tp["inputs"]))
        c.post(f"{api}/est", json={"target": "price:P", "sim": True})
        solo = c.get(f"{api}/trace?id={h['id']}&name=P").json["solo"]
        check("N13 식만 따로 모의한 기록이 있으면 식 자체의 오차를 함께 보인다", solo and solo["record"].startswith("est:") and solo["rmspe"] > 0, str(solo))
        rp = c.post(f"{api}/hs/replay", json={"record": h["id"]}).json["result"]
        check("N14 그때 그대로 다시 — 같은 숫자인지 알린다", rp["replay"]["of"] == h["id"] and rp["replay"]["same"] is True and rp["command"] == f"equion hs --replay {h['id']}")

        sc = c.get(f"{api}/scripts").json["scripts"]
        plan = c.post(f"{api}/script/plan", json={"path": "FLOWS/monthly.eqs"}).json
        log_before = len(c.get(f"{api}/records").json["records"])
        check("N15 스크립트 미리보기 — 단계마다 실행할 줄·묶음 제목·바꾸는 파일, 매개변수. 기록을 남기지 않는다",
              sc == [{"path": "FLOWS/monthly.eqs", "name": "monthly", "last": None}] and plan["ok"] and len(plan["steps"]) == 11 and plan["params"] == {"scenarios": ["base", "oil20"]}
              and plan["steps"][0] == {**plan["steps"][0], "n": 1, "section": "자료", "kind": "cmd"} and "EQUATIONS/adopted.toml" in plan["steps"][2]["effects"]
              and plan["steps"][4]["kind"] == "expect" and len(c.get(f"{api}/records").json["records"]) == log_before
              and c.post(f"{api}/script/plan", json={"path": "equion.toml"}).status_code == 400 and c.post(f"{api}/script/plan", json={"path": "FLOWS/nope.eqs"}).status_code == 404,
              str(plan.get("problems")))
        seq = state.feed.read(0, 0)["seq"]
        run = c.post(f"{api}/script/run", json={"path": "FLOWS/monthly.eqs"}).json["result"]
        events = [e for e in state.feed.read(seq, 0)["events"] if e["type"] == "job" and e["op"] == "script_run"]
        lines = [e["line"] for e in events if e["state"] == "progress"]
        rv = c.get(f"{api}/run/view?id={run['id']}").json
        check("N16 스크립트 실행 — 단계가 끝날 때마다 알리고(작업 줄의 '3/11'), 실행 기록에 단계마다 상태와 남긴 기록",
              run["id"].startswith("run:monthly") and run["status"] in ("ok", "flag") and run["exit_code"] == 0 and len(lines) == 11 and lines[0].startswith("[1/11]")
              and lines[-1].startswith("[11/11]") and events[0]["state"] == "start" and events[-1]["state"] == "done" and events[-1]["record"] == run["id"]
              and len(rv["steps"]) == 11 and rv["steps"][2]["records"] and rv["steps"][2]["status"] in ("ok", "flag") and rv["meta"]["who"] == "desk"
              and rv["meta"]["command"] == "equion run FLOWS/monthly.eqs" and any(x.startswith("hs:") for x in rv["meta"]["records"]), str(lines[:2]) + run.get("status", ""))
        again = c.post(f"{api}/script/run", json={"path": "FLOWS/monthly.eqs", "from": "6", "sets": {"scenarios": "base"}}).json["result"]
        rv2 = c.get(f"{api}/run/view?id={again['id']}").json
        check("N17 '이 단계부터' · 값 바꿔 넣기 — 앞 단계는 건너뛰고, 명령 글에 --set·--from 이 적힌다",
              rv2["meta"]["command"] == "equion run FLOWS/monthly.eqs --set scenarios=base --from 6" and str(rv2["meta"]["from"]) == "6"
              and [x["status"] for x in rv2["steps"][:5]] == ["skip"] * 5 and rv2["steps"][5]["status"] in ("ok", "flag")
              and c.get(f"{api}/scripts").json["scripts"][0]["last"]["id"] == again["id"], str(rv2["meta"].get("command")) + str([x["status"] for x in rv2["steps"]]))
        new = c.post(f"{api}/script/new", json={"name": "from_desk", "records": [h["id"], hb["id"]], "title": "화면에서"}).json["result"]
        check("N18 기록을 골라 스크립트 초안으로 — FLOWS/이름.eqs 에 그 명령들이 차례로",
              new["path"] == "FLOWS/from_desk.eqs" and "hs main" in read("FLOWS", "from_desk.eqs") and "hs demand --range 2010Q1:2019Q4 --mode static" in read("FLOWS", "from_desk.eqs")
              and c.post(f"{api}/script/new", json={"name": "x", "records": []}).status_code == 400 and len(c.get(f"{api}/scripts").json["scripts"]) == 2)

        # 새 분기 자료로 회차를 바꾼 뒤 — 채택한 계수·과거 재현·전망이 옛 자료의 것이다
        first = c.get(f"{api}/data").json["current"]
        lines_ = read("DATA", "raw", "toy_q.csv").rstrip("\n").split("\n")
        lines_.append(",".join(["2020Q1"] + [f"{float(x) * 1.01:.4f}" for x in lines_[-1].split(",")[1:]]))
        os.makedirs(os.path.join(folder, "DATA", "raw", "inbox"), exist_ok=True)
        with open(os.path.join(folder, "DATA", "raw", "inbox", "toy_q_new.csv"), "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(lines_) + "\n")
        before = c.get(f"{api}/todo").json
        c.post(f"{api}/data/add", json={"inbox": "toy_q_new.csv", "source": "na"})
        built = c.post(f"{api}/data/build", json={}).json["result"]
        c.post(f"{api}/data/use", json={"vintage": built["id"]})
        todo = c.get(f"{api}/todo").json
        check("N19 회차 바꾼 뒤 할 일 — 옛 자료로 추정한 채택 계수, 옛 자료로 푼 과거 재현·전망을 알린다(다시 계산하지 않는다)",
              before["adopted"] == [] and before["hs"]["stale"] is False and todo["vintage"] == built["id"] and len(todo["adopted"]) >= 1
              and all(x["vintage"] == first and x["record"].startswith("est:") for x in todo["adopted"]) and todo["hs"]["stale"] and todo["hs"]["vintage"] == first
              and todo["sim"]["stale"] and todo["hs"]["model"] == "main", str(todo))
        adopted0 = read("EQUATIONS", "adopted.toml")
        re_ = c.post(f"{api}/reestimate", json={"name": "main"}).json["result"]
        row = next(x for x in re_["rows"] if x["old"])
        check("N20 다시 추정해 견주기 — 지금 자료로 새 기록만 남기고(채택표는 그대로) 옛 계수·새 계수와 적합도를 나란히",
              re_["policy"] == "never" and re_["change"] is None and read("EQUATIONS", "adopted.toml") == adopted0 and len(re_["rows"]) == 5
              and row["new"].startswith("est:") and row["old_fit"]["vintage"] == first and row["new_fit"]["vintage"] == built["id"] and row["new_fit"]["r2_adj"] is not None
              and set(row["old_coefs"]) == set(row["new_coefs"]) and row["max_change_pct"] is not None and row["old_fit"]["n"] + 1 == row["new_fit"]["n"], str(row)[:300])
        took = c.post(f"{api}/reestimate", json={"parts": [f"{row['part']}={row['new']}"]}).json["result"]
        todo2 = c.get(f"{api}/todo").json
        check("N21 고른 식만 새 계수로 채택 — 채택표가 바뀌고 할 일에서 빠진다",
              len(took["adopted"]) == 1 and f'"{row["part"]}" = "{row["new"]}"' in read("EQUATIONS", "adopted.toml") and len(todo2["adopted"]) == len(todo["adopted"]) - 1
              and c.post(f"{api}/reestimate", json={"parts": ["demand:CN"]}).status_code == 400 and c.post(f"{api}/reestimate", json={"parts": []}).status_code == 400, str(took)[:200])
    finally:
        state.close()


def section_forecast(tmp: str) -> None:
    print("O. 전망 작업대·보고서 — 가정 표·기준선과 시나리오 풀기·결과 보기·보기 저장·보고서로 보내기·새 기록으로 바꾸기·엑셀로")
    from equion_desk.server import create_app

    folder = example(tmp, "fc")

    def read(*parts: str) -> str:
        with open(os.path.join(folder, *parts), encoding="utf-8") as f:
            return f.read()

    state, pid = new_state(tmp, folder, "o.json")
    api = f"/api/p/{pid}"
    try:
        c = create_app(state).test_client()
        f = c.get(f"{api}/forecast").json
        check("O1 전망 한눈에 — 모형과 전망 구간, 외생마다 끝 실측, 가정 표(직접 적은 칸·빈칸), 보정항 규칙, 시나리오. 계산하지 않는다",
              f["model"] == "main" and f["range"] == ["2020Q1", "2021Q4"] and len(f["periods"]) == 8 and [x["name"] for x in f["exogenous"]] == ["G", "POIL", "R"]
              and [x["period"] for x in f["exogenous"][0]["last"]] == ["2019Q1", "2019Q2", "2019Q3", "2019Q4"]
              and f["assume"] == {**f["assume"], "name": "base", "file": "ASSUMPTIONS/base.csv", "exists": True, "fill": "last", "extra": []}
              and f["assume"]["values"]["2020Q1"]["G"] != "" and f["assume"]["values"]["2020Q1"]["R"] == ""
              and f["addfactors"]["eqs"]["demand:I"]["rule"] == "decay" and f["scenarios"][0]["name"] == "oil20" and f["scenarios"][0]["shocks"][0]["var"] == "POIL"
              and f["records"] == [] and f["views"] == [] and f["error"] is None, str(f)[:300])
        core = c.get(f"{api}/forecast?model=core").json
        check("O2 다른 모형 — 그 모형의 외생으로 가정 표를 짠다 · 없는 모형은 까닭을 돌려준다 · 이름 모양이 틀리면 400",
              core["model"] == "core" and [x["name"] for x in core["exogenous"]] == ["G", "R"] and c.get(f"{api}/forecast?model=nope").json["error"]
              and c.get(f"{api}/forecast?model=..%2Fx").status_code == 400, str([x["name"] for x in core["exogenous"]]))

        before = read("ASSUMPTIONS", "base.csv")
        r = c.post(f"{api}/assume", json={"name": "base", "columns": ["G", "POIL", "R"], "rows": {"2020Q1": {"G": "70.5", "R": "3.1"}, "2021Q4": {"POIL": ""}}})
        after = read("ASSUMPTIONS", "base.csv")
        rows = {ln.split(",")[0]: ln.split(",") for ln in after.strip().split("\n")}
        head = rows["period"]
        change = (r.json or {}).get("result", {}).get("change")
        hist = c.get(f"{api}/changes").json["changes"]
        check("O3 가정 표 쓰기 — 고친 칸만 바뀌고(빈칸은 채움에 맡긴다) 다른 줄은 그대로, 바뀜 기록에 'Desk'로",
              r.status_code == 200 and change and rows["2020Q1"][head.index("G")] == "70.5" and rows["2020Q1"][head.index("R")] == "3.1"
              and rows["2021Q4"][head.index("POIL")] == "" and head == ["period", "G", "POIL", "R"] and "2020Q3,70.187,63.787\n" in before and rows["2020Q3"] == ["2020Q3", "70.187", "63.787", ""]
              and any(x["id"] == change and x["who"] == "desk" for x in hist), after[:200])
        same = c.post(f"{api}/assume", json={"name": "base", "columns": ["G", "POIL", "R"], "rows": {"2020Q1": {"G": "70.5"}}})
        bad = [c.post(f"{api}/assume", json=j).status_code for j in (
            {"name": "base", "columns": ["G"], "rows": {"2020Q1": {"G": "abc"}}}, {"name": "../x", "columns": ["G"], "rows": {}},
            {"name": "base", "columns": ["G"], "rows": [1]}, {"name": "base", "columns": [], "rows": {}}, {"name": "base", "columns": ["G"], "rows": {"20 20": {"G": "1"}}})]
        check("O4 가정 표: 바뀐 것이 없으면 바뀜 기록도 없다 · 숫자가 아닌 칸·이름·모양이 틀리면 400(아무것도 쓰지 않는다)",
              same.json["result"]["change"] is None and bad == [400] * 5 and read("ASSUMPTIONS", "base.csv") == after, str(bad))

        since = state.feed.read(0, 0)["seq"]
        r = c.post(f"{api}/sim/run", json={"scenarios": ["base", "oil20"], "model": "main"})
        out = r.json["result"]
        events = wait_events(state, since, lambda e: e.get("type") == "job" and e.get("state") == "done" and e.get("op") == "sim_run")
        jobs = [e for e in events if e.get("type") == "job" and e.get("op") == "sim_run"]
        base, oil = out["ids"]
        check("O5 풀기 — 기준선과 시나리오를 차례로(작업 하나: 시작 → 1/2 → 2/2 → 끝), 기록 둘, 응답에 일의 이름(이어서 시킬 수 있게)",
              r.status_code == 200 and base.startswith("sim:") and base.endswith("_base") and oil.endswith("_oil20") and out["failed"] is None and r.json["job"]
              and [e["state"] for e in jobs] == ["start", "progress", "progress", "done"] and [e.get("line") for e in jobs if e["state"] == "progress"] == ["1/2 base", "2/2 oil20"]
              and jobs[-1]["record"] == oil and len({e["job"] for e in jobs}) == 1, str(out) + str([e.get("state") for e in jobs]))
        v, vb = c.get(f"{api}/sim/view?id={oil}").json, c.get(f"{api}/sim/view?id={base}").json
        i0 = v["period"].index("2020Q1")
        check("O6 전망 기록 보기 — 수준과 값의 종류(실측·해·가정·채움), 전기비·전년동기비·연간, 시나리오는 기준선 대비",
              v["names"][:6] == ["Y", "CN", "I", "P", "RL", "M2"] and set(v["names"][6:]) == {"G", "POIL", "R"} and len(v["period"]) == i0 + 8
              and v["flag"]["Y"][i0 - 1] == "실측" and v["flag"]["Y"][-1] == "해" and v["flag"]["G"][-1] == "가정" and v["flag"]["R"][i0] == "가정" and v["flag"]["R"][-1] == "채움"
              and vb["flag"]["POIL"][-1] == "채움" and abs(vb["level"]["POIL"][-1] - vb["level"]["POIL"][-2]) < 1e-9
              and abs(vb["level"]["G"][i0] - 70.5) < 1e-9 and abs(vb["level"]["R"][i0] - 3.1) < 1e-9 and abs(vb["level"]["R"][-1] - 3.1) < 1e-9
              and v["annual"]["years"] == ["2020", "2021"] and len(v["annual"]["growth"]["Y"]) == 2 and len(v["qoq"]["Y"]) == len(v["period"]) and v["yoy"]["P"][-1] is not None
              and vb["diff"] is None and v["diff"]["period"][0] == "2020Q1" and set(v["diff"]["pct"]) == {"Y", "CN", "I", "P", "RL", "M2"} and v["diff"]["pct"]["P"][-1] > 0
              and all(abs(a / b - 1.2) < 1e-9 for a, b in zip(v["level"]["POIL"][i0:], vb["level"]["POIL"][i0:]))
              and v["meta"]["scenario"] == "oil20" and v["meta"]["range"] == ["2020Q1", "2021Q4"] and v["vintage"], str(v["flag"]["R"][-3:]) + str(v["diff"]["pct"]["P"][:2]))
        r2 = c.post(f"{api}/sim/run", json={"scenarios": ["base"], "model": "main", "range": "2020Q1:2020Q4", "vs": base}).json["result"]
        v2 = c.get(f"{api}/sim/view?id={r2['id']}").json
        half = c.post(f"{api}/sim/run", json={"scenarios": ["base", "nope"], "model": "main"})
        none = c.post(f"{api}/sim/run", json={"scenarios": ["nope"], "model": "main"})
        check("O7 구간·견줄 지난 전망(--range · --vs) · 앞의 것이 풀린 뒤 하나가 실패하면 남긴 기록과 까닭을 함께 · 하나도 못 풀면 오류",
              v2["meta"]["range"] == ["2020Q1", "2020Q4"] and v2["meta"]["vs"]["id"] == base and "--range 2020Q1:2020Q4" in v2["meta"]["command"] and f"--vs {base}" in v2["meta"]["command"]
              and half.status_code == 200 and len(half.json["result"]["ids"]) == 1 and half.json["result"]["failed"] == "nope" and half.json["result"]["error"]
              and none.status_code == 422 and c.post(f"{api}/sim/run", json={"scenarios": ["base"], "range": "x"}).status_code == 400
              and c.get(f"{api}/sim/view?id=hs:x").status_code == 400 and c.get(f"{api}/sim/view?id=sim:nope").status_code == 422, str(v2["meta"]["command"]))
        c.post(f"{api}/assume", json={"name": "base", "columns": ["G", "POIL", "R"], "rows": {"2020Q3": {"G": ""}}})
        gap = c.post(f"{api}/sim/run", json={"scenarios": ["base"], "model": "main"})
        c.post(f"{api}/assume", json={"name": "base", "columns": ["G", "POIL", "R"], "rows": {"2020Q3": {"G": "70.187"}}})
        check("O7b 값 사이의 빈칸은 채우기 규칙이 채우지 않는다(마지막으로 적은 값 뒤만 채운다) — 풀지 않고 까닭(변수와 기간)을 돌려준다",
              gap.status_code == 422 and "G: 2020Q3" in gap.json["error"], str(gap.json)[:300])
        f2 = c.get(f"{api}/forecast").json
        check("O8 전망 한눈에: 푼 기록이 모형·시나리오·구간·연간 증가율과 함께", [x["id"] for x in f2["records"]][:2] == [base, oil]
              and f2["records"][1] == {**f2["records"][1], "scenario": "oil20", "model": "main", "range": ["2020Q1", "2021Q4"], "who": "desk"} and "2020" in f2["records"][0]["annual"]
              and f2["assume"]["values"]["2020Q1"]["G"] == "70.5", str(f2["records"][:1])[:300])

        r = c.post(f"{api}/view/define", json={"name": "core", "series": ["Y", "CN", "P"], "show": "yoy", "title": "핵심 지표"})
        views = c.get(f"{api}/views").json["views"]
        bad = [c.post(f"{api}/view/define", json=j).status_code for j in ({"name": "v2", "series": []}, {"name": "v2", "series": ["Y"], "show": "pct"},
                                                                         {"name": "../v", "series": ["Y"]}, {"name": "v2", "series": ["NOPE"]})]
        check("O9 이 보기 저장 — VIEWS/core.toml(시리즈·보이기·제목), 전망 한눈에에도 뜬다 · 빈 시리즈·모르는 보이기·이름은 400, 자료에 없는 시리즈는 422(쓰지 않는다)",
              r.status_code == 200 and r.json["result"]["file"] == "VIEWS/core.toml" and 'show = "yoy"' in read("VIEWS", "core.toml")
              and views == [{"name": "core", "title": "핵심 지표", "series": ["Y", "CN", "P"], "show": "yoy", "range": None, "file": "VIEWS/core.toml"}]
              and c.get(f"{api}/forecast").json["views"] == views and bad == [400, 400, 400, 422] and not os.path.exists(os.path.join(folder, "VIEWS", "v2.toml")), str(bad))

        base3 = half.json["result"]["ids"][0]          # 가장 새 기준선(보고서에는 이것을 보낸다 — 검사가 정상이어야 한다)
        r = c.post(f"{api}/report/new", json={"name": "fc", "title": "12월 전망"})
        a1 = c.post(f"{api}/report/add", json={"report": "fc", "record": oil, "rows": ["Y", "P"], "show": "yoy", "title": "성장과 물가", "digits": 1})
        a2 = c.post(f"{api}/report/add", json={"report": "fc", "record": base3, "annual": True, "chart": True, "under": "본문"})
        text = read("reports", "fc.md")
        listed = c.get(f"{api}/reports").json["reports"]
        bad = [c.post(f"{api}/report/add", json=j).status_code for j in ({"report": "../x", "record": oil}, {"report": "fc", "record": "nope"}, {"report": "fc", "record": oil, "digits": 99},
                                                                        {"report": "fc", "record": oil, "show": "annual"}, {"report": "none", "record": oil})]
        check("O10 보고서로 보내기 — 새 보고서(틀) → 기록의 표를 고른 모양으로 한 구역씩(어느 기록에서 왔는지 적힌다), 차트 자료는 옆 폴더로",
              r.status_code == 200 and a1.status_code == 200 and a2.status_code == 200 and text.startswith("# 12월 전망") and f"<!-- equion:report {oil} " in text and f"<!-- equion:report {base3} " in text
              and "성장과 물가" in text and a1.json["result"]["command"].startswith("equion report add fc sim:") and "--show yoy" in a1.json["result"]["command"] and "--chart" in a2.json["result"]["command"]
              and listed == [{**listed[0], "name": "fc", "path": "reports/fc.md", "title": "12월 전망", "regions": 2}] and os.path.isdir(os.path.join(folder, "reports", "fc_data"))
              and c.get(f"{api}/overview").json["overview"]["reports"] == 1 and bad == [400, 400, 400, 400, 422]
              and c.post(f"{api}/report/new", json={"name": "fc"}).status_code == 422 and c.post(f"{api}/report/new", json={"name": "a/b"}).status_code == 400, str(bad) + text[:160])
        ok = c.get(f"{api}/report/check?report=fc").json
        newer = c.post(f"{api}/sim/run", json={"scenarios": ["oil20"], "model": "main"}).json["result"]["id"]
        chk = c.get(f"{api}/report/check?report=fc").json
        dry = c.post(f"{api}/report/update", json={"report": "fc", "dry": True}).json
        untouched = read("reports", "fc.md") == text
        done = c.post(f"{api}/report/update", json={"report": "fc"}).json["result"]
        text2 = read("reports", "fc.md")
        check("O11 보고서 검사 → 새 기록으로 바꾸기 — 더 새 기록이 있는 구역을 알리고, 먼저 차이만 보이고(파일은 그대로), 바꾸면 그 구역만 바뀐다(글은 그대로)",
              [x["status"] for x in ok["items"]] == ["정상", "정상"] and chk["items"][0] == {**chk["items"][0], "record": oil, "to": newer, "status": "더 새 기록"} and chk["items"][1]["to"] is None
              and untouched and dry["action"] == "update --dry-run" and dry["change"] is None and dry["items"][0]["status"].startswith("바뀜") and dry["items"][0]["diff"]
              and dry["command"] == "equion report update fc" and done["change"] and f"<!-- equion:report {newer} " in text2 and f"<!-- equion:report {oil} " not in text2
              and text2.startswith("# 12월 전망") and [x["status"] for x in c.get(f"{api}/report/check?report=fc").json["items"]] == ["정상", "정상"], str(chk["items"][0]) + str(dry["items"][0]["status"]))
        lines = text2.split("\n")
        k = next(i for i, ln in enumerate(lines) if ln.startswith("| Y |"))
        lines[k] = "| Y | 손으로 | 고친 줄 |"
        with open(os.path.join(folder, "reports", "fc.md"), "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(lines))
        hand = c.get(f"{api}/report/check?report=fc").json["items"]
        kept = c.post(f"{api}/report/update", json={"report": "fc", "region": 1, "dry": True}).json["items"][0]
        plain = c.post(f"{api}/report/update", json={"report": "fc", "region": 1}).json["result"]
        still = "손으로 | 고친 줄" in read("reports", "fc.md")
        forced = c.post(f"{api}/report/update", json={"report": "fc", "region": 1, "force": True}).json["result"]
        check("O12 손으로 고친 구역 — 검사가 알리고, 고친 곳을 보이며 바꾸지 않는다 · 덮겠다고 할 때만(force) 다시 만든다 · 없는 구역·보고서",
              "손으로 고침" in hand[0]["status"] and kept["status"].startswith("손으로 고침") and "손으로" in kept["diff"] and plain["change"] is None and still
              and forced["change"] and "손으로 고친 것을 덮음" in forced["items"][0]["status"] and "손으로 | 고친 줄" not in read("reports", "fc.md")
              and c.post(f"{api}/report/update", json={"report": "fc", "region": 9}).status_code == 422 and c.post(f"{api}/report/update", json={"report": "fc", "region": 0}).status_code == 400
              and c.get(f"{api}/report/check?report=none").status_code == 422 and c.get(f"{api}/report/check?report=..%2Fx").status_code == 400, str(hand[0]) + str(plain)[:100])

        hs = c.post(f"{api}/hs/run", json={"target": "main"}).json["result"]["id"]
        x = c.post(f"{api}/export", json={"records": [newer, hs], "name": "fc_2026-12"})
        path = os.path.join(folder, "exports", "fc_2026-12.xlsx")
        bad = [c.post(f"{api}/export", json=j).status_code for j in ({"records": [newer], "name": "../x"}, {"records": [], "name": "a"}, {"records": ["nope"], "name": "a"},
                                                                    {"records": [newer]}, {"records": ["sim:nope"], "name": "a"})]
        check("O13 엑셀로 — 기록들의 값·값의 종류·출처 시트를 exports/ 에(같은 일을 하는 명령과 함께) · 이름·기록 모양이 틀리면 400, 없는 기록은 422",
              x.status_code == 200 and x.json["result"]["path"] == "exports/fc_2026-12.xlsx" and os.path.getsize(path) > 2000 and len(x.json["result"]["sheets"]) >= 4
              and x.json["result"]["command"] == f"equion export {newer} {hs} --xlsx exports/fc_2026-12.xlsx" and bad == [400, 400, 400, 400, 422], str(bad) + str(x.json)[:200])
        a3 = c.post(f"{api}/report/add", json={"report": "fc", "record": hs, "rows": ["Y"]})
        check("O14 과거 재현 기록도 보고서로 — 보고서 목록의 구역 수가 는다", a3.status_code == 200 and c.get(f"{api}/reports").json["reports"][0]["regions"] == 3, str(a3.json)[:200])
    finally:
        state.close()


def section_review(tmp: str) -> None:
    print("P. 제안·되돌리기·고정 — 제안이 생기는 순간 알림, 제안 보기·적용·버림(낡음), 바뀜 되돌리기(파일 하나만), 고정과 메모, equion desk show")
    from equion_desk.server import create_app

    folder = example(tmp, "review")

    def read(*parts: str) -> str:
        with open(os.path.join(folder, *parts), encoding="utf-8") as f:
            return f.read()

    equion(folder, "hs", "main")
    equion(folder, "est", "P c Y POIL P(-1) P(-2)", "--for", "price:P", "--as", "p_lag2", who="claude")
    equion(folder, "hs", "main", "--swap", "price:P=est:p_lag2", "--vs", "hs:hs_0001", who="claude")
    state, pid = new_state(tmp, folder, "p.json")
    api = f"/api/p/{pid}"
    try:
        c = create_app(state).test_client()
        c.get(f"{api}/overview")
        since = state.feed.read(0, 0)["seq"]
        check("P1 제안이 없으면 빈 목록 · 앱 상태에 Claude Code 가 있는지(claude 명령)",
              c.get(f"{api}/proposals").json == {"proposals": []} and isinstance(c.get("/api/state").json["claude"], bool))
        r = equion(folder, "propose", "new", "--title", "물가식에 시차 하나 더", "--why", "P(-2)가 유의하다(est:p_lag2)", "--part", "price:P=est:p_lag2",
                   "--preview", "hs:hs_0002", who="claude")
        events = wait_events(state, since, lambda e: e.get("type") == "proposal")
        ev = next((e for e in events if e.get("type") == "proposal"), {})
        listed = c.get(f"{api}/proposals").json["proposals"] or [{"stale": None, "parts": None}]
        check("P2 제안이 생기는 순간 알림 줄에(누가·제목·바꿀 파일) — 목록에도 열림으로, 아무것도 바뀌지 않았다",
              r.returncode == 0 and ev.get("new") is True and ev["proposal"] == {**ev["proposal"], "id": "prop:p1", "name": "p1", "status": "open", "who": "claude", "title": "물가식에 시차 하나 더"}
              and [f["path"] for f in ev["proposal"]["files"]] == ["EQUATIONS/price.txt", "EQUATIONS/adopted.toml"] and listed[0]["stale"] == []
              and listed[0]["parts"] == {"price:P": "est:p_lag2"} and "P(-2)" not in read("EQUATIONS", "price.txt"), str(ev)[:300] + (r.stdout + r.stderr)[-400:])
        one = c.get(f"{api}/proposal?id=prop:p1").json
        check("P3 제안 하나 — 지금 파일 대비 차이·까닭·식·미리 계산한 과거 재현의 전후 RMSPE·같은 일을 하는 명령. 없는 제안·이름 모양",
              "+P c Y POIL P(-1) P(-2)" in one["diff"] and one["why"].startswith("P(-2)") and one["previews"][0] == {**one["previews"][0], "id": "hs:hs_0002", "kind": "hs", "model": "main"}
              and one["previews"][0]["vs"]["id"] == "hs:hs_0001" and len(one["previews"][0]["vs"]["rmspe"]["P"]) == 2 and one["commands"]["apply"] == "equion propose apply p1"
              and c.get(f"{api}/proposal?id=prop:nope").status_code == 422 and c.get(f"{api}/proposal?id=p1").status_code == 400, one["diff"][:200])

        with open(os.path.join(folder, "EQUATIONS", "price.txt"), "a", encoding="utf-8", newline="\n") as f:
            f.write("# 제안 뒤에 사람이 적은 줄\n")
        stale = c.get(f"{api}/proposals").json["proposals"][0]
        refused = c.post(f"{api}/proposal/apply", json={"id": "prop:p1"})
        since = state.feed.read(0, 0)["seq"]
        forced = c.post(f"{api}/proposal/apply", json={"id": "prop:p1", "force": True})
        done = forced.json["result"]
        events = wait_events(state, since, lambda e: e.get("type") == "proposal" and (e.get("proposal") or {}).get("status") == "applied")
        change = (done.get("decided") or {}).get("change")
        hist = {x["id"]: x for x in c.get(f"{api}/changes").json["changes"]}
        check("P4 낡음 — 제안을 만든 뒤 그 파일이 바뀌면 알리고, 덮겠다고(force) 할 때만 적용한다. 적용은 바뀜 기록에 'Desk'로, 알림 줄에 상태가 바뀐다",
              stale["stale"] == ["EQUATIONS/price.txt"] and [f["stale"] for f in stale["files"]] == [True, False] and refused.status_code == 422 and "낡" in refused.json["error"]
              and forced.status_code == 200 and done["status"] == "applied" and change in hist and hist[change]["who"] == "desk" and len(hist[change]["files"]) == 2
              and "P c Y POIL P(-1) P(-2)" in read("EQUATIONS", "price.txt") and '"price:P" = "est:p_lag2"' in read("EQUATIONS", "adopted.toml")
              and any(e.get("type") == "proposal" and e.get("new") is False for e in events), str(refused.json)[:200] + str(done)[:200])

        one_file = c.post(f"{api}/revert", json={"change": change, "files": ["EQUATIONS/adopted.toml"]}).json["result"]
        kept = "P c Y POIL P(-1) P(-2)" in read("EQUATIONS", "price.txt")
        bad = [c.post(f"{api}/revert", json=j).status_code for j in ({"change": change, "files": ["equion.toml"]}, {"change": "h9999"}, {"change": "x1"},
                                                                    {"change": change, "files": ["../x"]}, {"change": change, "files": []})]
        whole = c.post(f"{api}/revert", json={"change": change}).json["result"]
        again = c.post(f"{api}/revert", json={"change": change}).json["result"]
        detail = c.get(f"{api}/change?id={whole['change']}").json
        check("P5 되돌리기 — 파일 하나만(다른 파일은 그대로) · 바뀜 전체 · 이미 같으면 바꾼 것 없음. 되돌린 것도 바뀜 기록에 남는다 · 그 바뀜에 없는 파일(422)·모양(400)",
              one_file["change"] and one_file["files"] == ["EQUATIONS/adopted.toml"] and one_file["command"] == f"equion history revert {change} --file EQUATIONS/adopted.toml" and kept
              and not os.path.exists(os.path.join(folder, "EQUATIONS", "adopted.toml")) and bad == [422, 422, 400, 400, 400]
              and whole["change"] and whole["files"] == ["EQUATIONS/price.txt"] and "P(-2)" not in read("EQUATIONS", "price.txt") and "사람이 적은 줄" in read("EQUATIONS", "price.txt")
              and again["change"] is None and detail["reverts"] == change and detail["who"] == "desk", str(one_file) + str(bad) + str(whole))

        equion(folder, "propose", "new", "--title", "버릴 제안", "--part", "demand:CN=CN c Y", who="claude")
        dropped = c.post(f"{api}/proposal/drop", json={"id": "prop:p2", "why": "시차를 빼면 설명이 안 된다"}).json["result"]
        rows = {x["id"]: x for x in c.get(f"{api}/proposals").json["proposals"]}
        check("P6 버림 — 파일은 그대로, 제안과 까닭은 남는다 · 이미 닫힌 제안은 다시 적용하지 못한다",
              dropped["status"] == "dropped" and rows["prop:p2"]["decided"]["note"] == "시차를 빼면 설명이 안 된다" and rows["prop:p1"]["status"] == "applied"
              and "CN c Y CN(-1)" in read("EQUATIONS", "demand.txt") and c.post(f"{api}/proposal/apply", json={"id": "prop:p2"}).status_code == 422
              and c.post(f"{api}/proposal/drop", json={"id": "p2"}).status_code == 400, str(dropped)[:200])

        m1 = c.post(f"{api}/mark", json={"record": "est:p_lag2", "pinned": True, "memo": "제안 p1 의 근거"}).json
        m2 = c.post(f"{api}/mark", json={"record": "est:p_lag2", "pinned": False}).json
        recs = {x["id"]: x for x in c.get(f"{api}/records").json["records"]}
        bad = [c.post(f"{api}/mark", json=j).status_code for j in ({"record": "est:nope", "pinned": True}, {"record": "prop:p1", "pinned": True}, {"record": "est:p_lag2", "pinned": "yes"},
                                                                  {"record": "est:p_lag2", "memo": "x" * 501})]
        check("P7 고정과 메모 — 기록은 그대로, marks.json 에만. 작업 기록 목록에 함께 온다 · 없는 기록(422)·모양(400)",
              m1 == {"record": "est:p_lag2", "pinned": True, "memo": "제안 p1 의 근거"} and m2["pinned"] is False and m2["memo"] == "제안 p1 의 근거"
              and recs["est:p_lag2"]["pinned"] is False and recs["est:p_lag2"]["memo"] == "제안 p1 의 근거" and "pinned" not in recs["hs:hs_0001"]
              and bad == [422, 400, 400, 400], str(m1) + str(bad))

        since = state.feed.read(0, 0)["seq"]
        shown = [equion(folder, "desk", "show", x, who="claude").returncode for x in ("prop:p1", "demand:CN", "est:nope")]
        events = wait_events(state, since, lambda e: e.get("type") == "show" and e.get("show") == "demand:CN")
        shows = [(e["show"], e["kind"], e["who"]) for e in events if e.get("type") == "show"]
        check("P8 equion desk show — 터미널·Claude 가 치면 알림 줄에 '이 화면을 열어 달라'가 온다(없는 이름은 오지 않는다). 다시 띄운 앱은 지난 요청을 다시 열지 않는다",
              shown == [0, 0, 3] and shows == [("prop:p1", "proposal", "claude"), ("demand:CN", "part", "claude")], str(shows))
    finally:
        state.close()
    state, pid = new_state(tmp, folder, "p2.json")
    try:
        c = create_app(state).test_client()
        c.get(f"/api/p/{pid}/overview")
        state.session(pid).watcher.check()
        got = state.feed.read(0, 0.3)["events"]
        check("P9 다시 띄우면 — 지난 요청·지난 제안으로 알림을 만들지 않는다(목록에는 그대로 있다)",
              not any(e.get("type") in ("show", "proposal") for e in got) and len(c.get(f"/api/p/{pid}/proposals").json["proposals"]) == 2, str([e.get("type") for e in got]))
    finally:
        state.close()


def section_side(tmp: str) -> None:
    print("Q. DESK_V2 — 변수 탭·분석 탭·묶음·식 더하기(개별 식·모형에 넣기)·명령 창·명령 목록·터미널 번호·오른쪽 나눔 설정")
    from equion_desk.server import create_app

    folder = example(tmp, "side")

    def read(*parts: str) -> str:
        with open(os.path.join(folder, *parts), encoding="utf-8") as f:
            return f.read()

    state, pid = new_state(tmp, folder, "q.json")
    api = f"/api/p/{pid}"
    try:
        c = create_app(state).test_client()
        c.get(f"{api}/overview")
        v = c.get(f"{api}/variables").json
        rows = {r["name"]: r for r in v["variables"]}
        check("Q1 변수 — 시리즈마다 설명·구간·끝 값·종류와 모형과의 관계(식이 있다 · 외생), 묶음",
              rows["CN"]["rel"] == "endo" and "demand:CN" in rows["CN"]["parts"] and rows["POIL"]["rel"] == "exo" and rows["CN"]["kind"] == "원자료"
              and rows["CN"]["first"] and rows["CN"]["value"] is not None and any(g["name"] == "core" for g in v["groups"]), str(rows.get("CN"))[:300])
        dry = c.post(f"{api}/group/define", json={"name": "trio", "series": ["Y", "CN", "I"], "desc": "셋", "dry": True}).json
        bad = c.post(f"{api}/group/define", json={"name": "bad", "series": ["Y", "NOPE"], "dry": True})
        check("Q2 묶음 미리보기 — 쓰지 않고 equion.toml 의 차이와 명령, 없는 시리즈는 거절",
              "+trio" in dry["diff"].replace(" ", "") and dry["new"] is True and "group define trio" in dry["command"] and "trio" not in read("equion.toml")
              and bad.status_code == 422 and "NOPE" in bad.json["error"], str(dry)[:300])
        r = c.post(f"{api}/group/define", json={"name": "trio", "series": ["Y", "CN", "I"], "desc": "셋"}).json
        groups = [g["name"] for g in c.get(f"{api}/variables").json["groups"]]
        r2 = c.post(f"{api}/group/remove", json={"name": "trio"}).json
        check("Q3 묶음 저장·지우기 — equion.toml 에 쓰고 바뀜 기록에 남는다(누가 Desk)",
              r["result"]["change"] and "trio" in groups and r2["result"]["change"] and "trio" not in read("equion.toml")
              and c.get(f"{api}/change?id={r['result']['change']}").json["who"] == "desk", str(r)[:300])
        lst = c.get(f"{api}/analysis-list").json
        check("Q4 분석 목록 — 처음엔 개별 식도 결과도 없다(예제의 블록은 모두 모형이 쓴다)", lst["singles"] == [] and lst["results"] == [] and lst["vintage"], str(lst)[:300])
        dry = c.post(f"{api}/part/add", json={"block": "single", "text": "IPQ c IPQ(-1)", "create": True, "dry": True}).json
        made = c.post(f"{api}/part/add", json={"block": "single", "text": "IPQ c IPQ(-1)", "create": True}).json["result"]
        lst = c.get(f"{api}/analysis-list").json
        check("Q5 새 개별 식 — 블록 single 을 만들고 한 줄(미리보기 → 쓰기), 분석 탭의 개별 식에 놓인다",
              dry["new_block"] is True and "+IPQ c IPQ(-1)" in dry["diff"] and made["part"] == "single:IPQ" and made["block_change"]
              and "IPQ c IPQ(-1)" in read("EQUATIONS", "single.txt") and [x["id"] for x in lst["singles"]] == ["single:IPQ"]
              and next(b for b in lst["blocks"] if b["name"] == "single")["used"] is False, str(made)[:300])
        moved_dry = c.post(f"{api}/part/add", json={"block": "price", "text": "IPQ c IPQ(-1)", "from": "single:IPQ", "dry": True}).json
        moved = c.post(f"{api}/part/add", json={"block": "price", "text": "IPQ c IPQ(-1)", "from": "single:IPQ"}).json["result"]
        check("Q6 모형에 넣기 — 개별 식을 모형이 쓰는 블록으로 옮긴다(원래 줄은 빠진다)",
              "-IPQ c IPQ(-1)" in moved_dry["diff"] and "+IPQ c IPQ(-1)" in moved_dry["diff"] and moved["part"] == "price:IPQ"
              and "IPQ" in read("EQUATIONS", "price.txt") and "IPQ" not in read("EQUATIONS", "single.txt")
              and c.get(f"{api}/analysis-list").json["singles"] == [], str(moved)[:300])
        gone = c.post(f"{api}/part/remove", json={"part": "price:IPQ"}).json["result"]
        bad = c.post(f"{api}/part/add", json={"block": "nope", "text": "X c Y"})
        two = c.post(f"{api}/part/add", json={"block": "single", "text": "X c Y\nZ c Y"})
        check("Q7 식 빼기 · 없는 블록(만들라고 하지 않으면)과 여러 줄은 거절", gone["change"] and "IPQ" not in read("EQUATIONS", "price.txt")
              and bad.status_code == 422 and two.status_code == 400, str(gone)[:200])
        one = c.post(f"{api}/line", json={"line": "an stats Y"}).json["result"]
        lst = c.get(f"{api}/analysis-list").json
        res = {(x["analysis"], x["target"]): x for x in lst["results"]}
        check("Q8 명령 한 줄 — 작업 프로세스가 명령줄 그대로 돌리고(누가 Desk) 새 기록을 돌려준다 · 분석 목록에 대상별로",
              one["code"] == 0 and one["records"] == ["an:stats_0001"] and ("stats", "Y") in res and res[("stats", "Y")]["scope"] == "one"
              and res[("stats", "Y")]["stale"] is False and json.load(open(os.path.join(folder, "work", "an", "stats_0001", "record.json"), encoding="utf-8"))["who"] == "desk", str(one)[:300])
        two = c.post(f"{api}/line", json={"line": "equion an corr 'Y CN'"}).json["result"]
        adopt = c.post(f"{api}/line", json={"line": "adopt est:nope"}).json["result"]
        py = c.post(f"{api}/line", json={"line": "run x.py"}).json["result"]
        empty = c.post(f"{api}/line", json={"line": "  "})
        lst = c.get(f"{api}/analysis-list").json
        check("Q9 여러 변수(따옴표) · 틀린 명령은 코드와 글 · Python 스크립트는 받지 않는다 · 빈 줄은 400",
              two["code"] == 0 and any(x["analysis"] == "corr" and x["scope"] == "many" for x in lst["results"]) and adopt["code"] != 0 and adopt["out"]
              and py["code"] == 3 and py["denied"] and empty.status_code == 400, str([two, adopt, py])[:400])
        cat = c.get(f"{api}/catalog").json
        cmds = {x["command"] for x in cat["commands"]}
        check("Q10 명령 목록 — 명령·옵션(명령줄 정의에서)과 프로젝트의 이름들(식·모형·묶음·시리즈·기록·회차)",
              {"est", "an corr", "group define", "block add"} <= cmds and "demand:CN" in cat["names"]["parts"] and "main" in cat["names"]["models"]
              and "CN" in cat["names"]["series"] and "an:stats_0001" in cat["names"]["records"] and cat["names"]["vintages"]
              and any(a["name"] == "corr" and a["count"] == "many" for a in cat["names"]["analyses"]), str(cat["names"])[:300])
        reg = c.get(f"{api}/analyses").json
        check("Q11 등록부에 받는 대상의 수(count) — 변수 메뉴가 고른 수에 맞는 분석만 보인다",
              {a["name"]: a["count"] for a in reg["analyses"]}.get("xcorr") == "two" and {a["name"]: a["count"] for a in reg["analyses"]}.get("acf") == "one")
        head = {"X-Term": state.term_secret}
        bad_n = c.post("/api/term/open", json={"p": pid, "cols": 80, "rows": 20, "n": 9}, headers=head)
        t0 = c.post("/api/term/open", json={"p": pid, "cols": 80, "rows": 20, "n": 0}, headers=head).json
        t1 = c.post("/api/term/open", json={"p": pid, "cols": 80, "rows": 20, "n": 1}, headers=head).json
        again = c.post("/api/term/open", json={"p": pid, "cols": 80, "rows": 20, "n": 1}, headers=head).json
        listed = c.get(f"/api/term/list?p={pid}", headers=head).json
        c.post("/api/term/close", json={"t": t1["id"]}, headers=head)
        after = c.get(f"/api/term/list?p={pid}", headers=head).json
        c.post("/api/term/close", json={"t": t0["id"]}, headers=head)
        check("Q12 터미널 번호 — 번호마다 셸 하나(이미 돌면 그것), 목록으로 되살린다, 번호는 0~4",
              bad_n.status_code == 400 and t0["n"] == 0 and t1["n"] == 1 and again["id"] == t1["id"] and [x["n"] for x in listed["terms"]] == [0, 1]
              and listed["max"] == 5 and [x["n"] for x in after["terms"]] == [0], str(listed))
        before = c.get("/api/state").json["client"]
        c.post("/api/settings", json={"right_split": 0.4, "cmd_top": True, "side_width": 900})
        c.post("/api/settings", json={"right_split": 0.95, "side_width": 5000})
        cl = c.get("/api/state").json["client"]
        check("Q13 화면 설정 — 오른쪽 나눔 비율·명령 창 자리를 기억한다(범위 밖은 받지 않는다), 왼쪽 폭은 넓게까지",
              before["right_split"] == 0.62 and before["cmd_top"] is False and cl["right_split"] == 0.4 and cl["cmd_top"] is True and cl["side_width"] == 900, str(cl))
    finally:
        state.close()


def section_forms(tmp: str) -> None:
    print("R. 2차판 폼과 노트 — 후보 묶음·시나리오 폼(미리보기·쓰기·거절·지우기)·노트(목록·보기·더하기·실행)·같은 분석의 두 기록")
    from equion_desk.server import create_app

    folder = example(tmp, "forms")

    def read(*parts: str) -> str:
        with open(os.path.join(folder, *parts), encoding="utf-8") as f:
            return f.read()

    state, pid = new_state(tmp, folder, "r.json")
    api = f"/api/p/{pid}"
    try:
        c = create_app(state).test_client()
        c.get(f"{api}/overview")
        r = c.post(f"{api}/est-batch", json={"part": "demand:I", "texts": ["I c Y", "I c Y I(-1)", "I c NOPE"], "sim": True}).json["result"]
        cand = c.get(f"{api}/candidates?part=demand:I").json
        too_many = c.post(f"{api}/est-batch", json={"part": "demand:I", "texts": ["I c Y"] * 65})
        check("R1 후보 묶음 — 식마다 그 부품의 후보로(누가 Desk), 틀린 식은 그 줄만 까닭과 함께, 64개까지",
              [m["text"] for m in r["made"]] == ["I c Y", "I c Y I(-1)"] and len(r["failed"]) == 1 and "NOPE" in r["failed"][0]["error"]
              and r["lines"][0] == "est 'I c Y' --for demand:I --sim" and too_many.status_code == 400
              and json.load(open(os.path.join(folder, "work", "est", "i_0001", "record.json"), encoding="utf-8"))["who"] == "desk", str(r)[:300] + str(cand)[:100])
        info = c.get(f"{api}/scenario-info").json
        dry = c.post(f"{api}/scenario/define", json={"name": "rr", "desc": "금리", "shocks": ["R=+1@start:start+3", "POIL=+10%"], "addfactor": ["demand:CN=-0.2"], "dry": True}).json
        check("R2 시나리오 폼의 재료와 미리보기 — 쓰지 않고 차이·명령(명령줄 꼴 그대로)",
              [x["name"] for x in info["scenarios"]] == ["oil20"] and "base" in info["assumptions"] and "main" in info["models"] and "POIL" in info["series"]
              and dry["new"] is True and '+var = "R"' in dry["diff"] and "--shock R=+1@start:start+3 --shock POIL=+10%" in dry["command"]
              and "--addfactor demand:CN=-0.2" in dry["command"] and not os.path.exists(os.path.join(folder, "SCENARIOS", "rr.toml")), str(dry)[:300])
        w = c.post(f"{api}/scenario/define", json={"name": "rr", "desc": "금리", "shocks": ["R=+1@start:start+3"]}).json["result"]
        bad = c.post(f"{api}/scenario/define", json={"name": "rr", "shocks": ["NOPE=+1"]})
        badform = c.post(f"{api}/scenario/define", json={"name": "rr", "shocks": ["R+1"]})
        nobase = c.post(f"{api}/scenario/define", json={"name": "base", "shocks": ["R=+1"]})
        check("R3 시나리오 쓰기(바뀜 기록 · 누가 Desk) · 자료에 없는 변수(422) · 틀린 꼴(400) · 이름 base(422)",
              w["new"] is True and w["change"] and 'to = "start+3"' in read("SCENARIOS", "rr.toml") and c.get(f"{api}/change?id={w['change']}").json["who"] == "desk"
              and bad.status_code == 422 and "NOPE" in bad.json["error"] and badform.status_code == 400 and nobase.status_code == 422, str(w))
        rm = c.post(f"{api}/scenario/remove", json={"name": "rr"}).json["result"]
        check("R4 시나리오 지우기 — 파일이 없어지고 바뀜 기록", rm["removed"] is True and rm["change"] and not os.path.exists(os.path.join(folder, "SCENARIOS", "rr.toml")))
        na = c.post(f"{api}/note/add", json={"note": "notes/cand.md", "lines": r["lines"][:2], "title": "후보"}).json["result"]
        lst = c.get(f"{api}/notes").json["notes"]
        view = c.get(f"{api}/note?path=notes/cand.md").json
        check("R5 노트에 담기(새 노트 · 블록 1) · 노트 목록(블록 상태의 수) · 노트 보기(블록마다 상태·명령)",
              na["new"] is True and na["block"] == 1 and {n["path"] for n in lst} == {"notes/cand.md", "notes/data_check.md"}
              and next(n for n in lst if n["path"] == "notes/cand.md")["counts"] == {"never": 1}
              and view["blocks"][0]["status"] == "never" and view["blocks"][0]["commands"] == r["lines"][:2] and view["text"].startswith("# 후보"), str(view)[:300])
        ran = c.post(f"{api}/note/run", json={"path": "notes/cand.md", "block": 1}).json["result"]
        after = c.get(f"{api}/note?path=notes/cand.md").json["blocks"][0]
        who = json.load(open(os.path.join(folder, "work", "est", ran["records"][0].split(":")[1], "record.json"), encoding="utf-8"))["who"]
        check("R6 노트 블록 실행 — 블록마다 새 기록(누가 Desk), 그 뒤 상태는 정상",
              ran["ok"] is True and len(ran["records"]) == 2 and after["status"] == "ok" and who == "desk", f"{ran} {who}")
        rec_add = c.post(f"{api}/note/add", json={"note": "notes/cand.md", "record": ran["records"][0]}).json["result"]
        denied = c.post(f"{api}/note/add", json={"note": "notes/cand.md", "lines": ["adopt est:i_0001"]})
        outside = c.post(f"{api}/note/add", json={"note": "../x.md", "lines": ["an stats Y"]})
        nomd = c.get(f"{api}/note?path=README.txt")
        check("R7 기록 담기(블록 2 · 결과 구역까지) · 노트가 부를 수 없는 명령(422) · 프로젝트 밖(403) · md 아님(400)",
              rec_add["block"] == 2 and rec_add["record"] == ran["records"][0] and denied.status_code == 422 and outside.status_code == 403 and nomd.status_code == 400)
        a1 = c.post(f"{api}/line", json={"line": "an unitroot Y"}).json["result"]["records"][0]
        a2 = c.post(f"{api}/line", json={"line": "an unitroot Y --smpl 1990Q1:last"}).json["result"]["records"][0]
        other = c.post(f"{api}/line", json={"line": "an unitroot CN"}).json["result"]["records"][0]
        hist = c.get(f"{api}/an-history?id={a2}").json
        first = c.get(f"{api}/an-history?id={a1}").json
        check("R8 같은 분석·같은 대상의 기록들 — 이전 기록(대상이 다른 것은 빼고), 처음 것은 이전이 없다",
              hist["previous"] == a1 and [x["id"] for x in hist["records"]] == [a1, a2] and other not in [x["id"] for x in hist["records"]]
              and first["previous"] is None and first["next"] == a2 and hist["records"][0]["lines"], str(hist)[:300])
    finally:
        state.close()


def section_data3(tmp: str) -> None:
    print("S. 자료 쪽 셋 — 요인 나누기(분석)·시점이 열로 가는 표와 여러 줄 머리(불러오기)·이정표·묶어 보내기·묶음 열기")
    from equion_desk.server import create_app

    folder = example(tmp, "data3")
    raw = os.path.join(folder, "DATA", "raw")
    with open(os.path.join(raw, "wide.csv"), "w", encoding="utf-8", newline="\n") as f:
        f.write("표 1\n항목,단위,2018 1/4,2018 2/4,2018 3/4,2018 4/4,2019 1/4\n제조업,십억원,100,101,103,104,105\n서비스업,십억원,200,202,-,205,207\n")
    with open(os.path.join(raw, "multi.csv"), "w", encoding="utf-8", newline="\n") as f:
        f.write("시점,국내총생산,,소비,\n,명목,실질,명목,실질\n2018Q1,10,9,6,5\n2018Q2,11,10,6.5,5.2\n2018Q3,12,11,7,5.4\n2018Q4,13,12,7.5,5.6\n")
    state, pid = new_state(tmp, folder, "s.json")
    api = f"/api/p/{pid}"
    docs = os.path.join(tmp, "docs3")
    os.environ["EQUION_DESK_DOCUMENTS"] = docs
    try:
        c = create_app(state).test_client()
        c.get(f"{api}/overview")
        a = c.post(f"{api}/line", json={"line": "sim --as a"}).json["result"]
        b = c.post(f"{api}/line", json={"line": "sim --as b"}).json["result"]
        sp = c.post(f"{api}/line", json={"line": "an split 'sim:a sim:b'"}).json["result"]
        reg = {x["name"]: x for x in c.get(f"{api}/analyses").json["analyses"]}
        check("S1 요인 나누기 — 분석으로 등록(대상 기록 둘), 명령 창으로 돌리면 기록 an: 이 남는다",
              a["code"] == 0 and b["code"] == 0 and sp["code"] == 0 and sp["records"] and sp["records"][0].startswith("an:split_")
              and reg["split"]["count"] == "two" and reg["split"]["targets"] == ["records"], str(sp)[:300])
        frame = {"time_axis": "columns", "time_row": 2, "name_col": "A", "missing": ["-"]}
        v = c.post(f"{api}/data/preview", json={"file": "DATA/raw/wide.csv", "frame": frame}).json
        check("S2 시점이 열로 가는 표 미리보기 — 줄마다 시리즈(자리 '3줄'), 앞의 글 열(단위)은 건너뛰고, 결측 칸은 원래 표의 자리",
              v["ok"] is True and v["axis"] == "columns" and [c_["name"] for c_ in v["columns"]] == ["제조업", "서비스업"]
              and v["columns"][0]["letter"] == "3줄" and v["missing_cells"] == ["E4 '-'"] and "B" in v["note"], str(v.get("error") or v.get("note")))
        v2 = c.post(f"{api}/data/preview", json={"file": "DATA/raw/multi.csv", "frame": {"header_row": "1,2"}}).json
        bad = c.post(f"{api}/data/preview", json={"file": "DATA/raw/multi.csv", "frame": {"header_row": "1;x"}})
        bad2 = c.post(f"{api}/data/preview", json={"file": "DATA/raw/wide.csv", "frame": {"time_axis": "diag"}})
        check("S3 여러 줄 머리('1,2' — 병합 칸을 이어 붙인 이름) · 틀린 머리줄·방향은 400",
              v2["ok"] is True and v2["columns"][1]["name"] == "국내총생산 실질" and bad.status_code == 400 and bad2.status_code == 400, str(v2.get("error")))
        d = c.post(f"{api}/data/define", json={"source": "wide", "file": "DATA/raw/wide.csv", "frame": frame,
                                               "series": {"MFG": {"column": "제조업"}}}).json["result"]
        with open(os.path.join(folder, "DATA", "series.toml"), encoding="utf-8") as f:
            text = f.read()
        check("S4 정의 쓰기 — 명령에 --time-axis columns --time-row 2 --name-col A, series.toml 에 그 틀",
              d["added"] == ["MFG"] and "--time-axis columns" in d["command"] and "--time-row 2" in d["command"] and 'time_axis = "columns"' in text, d.get("command", ""))
        m = c.post(f"{api}/milestone/make", json={"name": "fc1", "note": "확정"}).json["result"]
        lst = c.get(f"{api}/milestones").json["milestones"]
        with open(os.path.join(folder, "EQUATIONS", "price.txt"), "a", encoding="utf-8", newline="\n") as f:
            f.write("\n# 뒤에 더한 줄\n")
        df = c.get(f"{api}/milestone?name=fc1").json
        rs = c.post(f"{api}/milestone/restore", json={"name": "fc1"}).json["result"]
        df2 = c.get(f"{api}/milestone?name=fc1").json
        check("S5 이정표 — 만들기 · 목록 · 지금과(고친 파일·차이) · 되돌리기(바뀜 기록, 누가 Desk) 뒤에는 같다",
              m["name"] == "fc1" and m["files"] > 5 and [x["name"] for x in lst] == ["fc1"] and not df["same"]
              and any(f_["path"] == "EQUATIONS/price.txt" and f_["status"] == "changed" for f_ in df["files"]) and rs["change"]
              and c.get(f"{api}/change?id={rs['change']}").json["who"] == "desk" and df2["same"] is True, str(df)[:300])
        bd = c.post(f"{api}/bundle", json={"raw": False, "records": "keep"}).json["result"]
        zp = os.path.join(folder, *bd["path"].split("/"))
        check("S6 묶어 보내기 — exports/ 에 zip(원자료 넣지 않음, 명령 글)", os.path.isfile(zp) and bd["raw"] is False and bd["command"] == "equion bundle make", str(bd)[:200])
        opened = c.post("/api/bundle/open", json={"zip": zp})
        dest = os.path.join(docs, "Equion", os.path.splitext(os.path.basename(zp))[0])
        check("S7 묶음 열기 — 문서 폴더의 Equion 아래에 풀고 새 탭으로 연다(zip 이 아니면 400)",
              opened.status_code == 200 and len(opened.json["tabs"]) == 2 and os.path.isfile(os.path.join(dest, "equion.toml"))
              and c.post("/api/bundle/open", json={"zip": os.path.join(folder, "equion.toml")}).status_code == 400, str(opened.json)[:200])
    finally:
        os.environ.pop("EQUION_DESK_DOCUMENTS", None)
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
        section_data(tmp)
        section_import(tmp)
        section_model(tmp)
        section_forecast(tmp)
        section_review(tmp)
        section_side(tmp)
        section_forms(tmp)
        section_data3(tmp)
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
