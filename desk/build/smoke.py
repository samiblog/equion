"""설치본 기동 시험 — 설치 폴더의 런타임만으로 앱이 뜨고 계산하는지 본다(이 저장소의 .venv 는 쓰지 않는다).

    python desk/build/smoke.py "<설치 폴더>"             # 예: %LOCALAPPDATA%\\Programs\\EquionDesk
    python desk/build/smoke.py "<설치 폴더>" --window    # 창(pywebview)도 띄워 본다 — 화면이 있는 PC·실행기에서

하는 일: 런타임의 `python -I -m equion_desk --version` → 예제 프로젝트 만들기 → 서버를 브라우저 모드로 띄워 첫 화면과 화면 파일,
개요·추정·과거 재현·기록 읽기를 HTTP 로 → (`--window`) 창을 띄우고 두 번째 실행이 폴더를 넘기는지(창은 하나).
표준 라이브러리만 쓴다 — 어느 Python 으로 돌려도 되고, 시험받는 것은 설치 폴더의 런타임이다. CI(`desk-installer`)와 손으로 하는 설치 점검이 쓴다.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

PORT = 8795
FAILED: list[str] = []


def check(name: str, ok: object, detail: str = "") -> None:
    print(("  ✓ " if ok else "  ✗ ") + name + (f" — {detail}" if detail and not ok else ""), flush=True)
    if not ok:
        FAILED.append(name)


def http(path: str, body: dict | None = None) -> tuple[int, dict | str]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}", data=data, headers={"Content-Type": "application/json"} if data else {})
    try:
        with urllib.request.urlopen(req, timeout=120) as res:
            raw, code = res.read().decode("utf-8"), res.status
    except urllib.error.HTTPError as exc:
        raw, code = exc.read().decode("utf-8", "replace"), exc.code
    try:
        return code, json.loads(raw)
    except ValueError:
        return code, raw


def main() -> int:
    ap = argparse.ArgumentParser(description="Equion Desk 설치본 기동 시험")
    ap.add_argument("folder", help="설치 폴더(runtime/ 이 있는 곳)")
    ap.add_argument("--window", action="store_true", help="창도 띄워 본다")
    args = ap.parse_args()
    runtime = os.path.join(os.path.abspath(args.folder), "runtime")
    python = os.path.join(runtime, "python.exe" if os.name == "nt" else "bin/python3")
    if not os.path.isfile(python):
        print(f"런타임이 없습니다: {python}", file=sys.stderr)
        return 3
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        env = {k: v for k, v in os.environ.items() if k.upper() not in ("CLAUDECODE", "EQUION_WHO", "VIRTUAL_ENV")}
        # PC 의 Python 설정이 어지러워도 돈다(D39) — 일부러 틀린 값을 준다
        env.update(PYTHONPATH=os.path.join(tmp, "no-such"), PYTHONHOME=os.path.join(tmp, "no-such"), EQUION_DESK_CONFIG_DIR=os.path.join(tmp, "cfg"), PYTHONIOENCODING="utf-8")

        print("설치본 기동 시험 —", runtime)
        r = subprocess.run([python, "-I", "-X", "utf8", "-m", "equion_desk", "--version"], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
        check("1 런타임의 python -I -m equion_desk --version", r.returncode == 0 and "Equion Desk" in r.stdout, r.stdout + r.stderr)
        print("    " + r.stdout.strip())
        r = subprocess.run([python, "-I", "-X", "utf8", "-m", "equion", "new", "demo", "--template", "desk"], cwd=tmp, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", env=env)      # -I 는 PYTHONIOENCODING 도 읽지 않는다 — 글자는 -X utf8 로
        project = os.path.join(tmp, "demo")
        check("2 예제 프로젝트 만들기(equion new --template desk)", r.returncode == 0 and os.path.isfile(os.path.join(project, "equion.toml")), r.stdout + r.stderr)
        icon = os.path.join(runtime, "Lib", "site-packages", "equion_desk", "assets", "equion-desk.ico")
        check("3 아이콘이 런타임과 설치 폴더에 있다", os.path.isfile(icon) and (os.name != "nt" or os.path.isfile(os.path.join(args.folder, "equion-desk.ico"))))

        server = subprocess.Popen([python, "-I", "-m", "equion_desk", "--browser", "--port", str(PORT), project], env=env,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            state: dict = {}
            for _ in range(200):
                try:
                    code, state = http("/api/state")  # type: ignore[assignment]
                    break
                except OSError:
                    time.sleep(0.1)
            pid = (state.get("tabs") or [{}])[0].get("id")
            check("4 서버가 뜨고 프로젝트가 탭으로 열린다", bool(pid), str(state)[:200])
            code, page = http("/")
            refs = re.findall(r'(?:src|href)="(/web/[^"]+)"', page if isinstance(page, str) else "")
            missing = [u for u in refs if http(u)[0] != 200]
            check("5 첫 화면과 화면 파일(스크립트·스타일·라이브러리)이 모두 들어 있다", code == 200 and len(refs) >= 8 and not missing, f"{len(refs)}개, 없는 것 {missing}")
            began = time.time()
            code, ov = http(f"/api/p/{pid}/overview")
            o = ov.get("overview", {}) if isinstance(ov, dict) else {}
            inside = os.path.normcase(str(o.get("executable", ""))).startswith(os.path.normcase(runtime))
            check("6 작업 프로세스가 설치본의 런타임으로 뜬다(PC 의 PYTHONPATH·PYTHONHOME 을 읽지 않는다)", code == 200 and inside,
                  f"{o.get('executable')} · {str(ov)[:200]}")
            print(f"    작업 프로세스가 뜨기까지 {time.time() - began:.1f}초 · equion {o.get('equion')} · Python {o.get('python')}")
            times = []
            for _ in range(3):
                began = time.time()
                code, est = http(f"/api/p/{pid}/est", {"target": "demand:CN"})
                times.append(time.time() - began)
            rec = est.get("result", {}) if isinstance(est, dict) else {}
            check("7 추정 — 1초 안(S1)", code == 200 and len(rec.get("coefs", [])) == 3 and min(times) < 1.0, " ".join(f"{t:.3f}" for t in times) + f" {str(est)[:200]}")
            print("    추정 " + " · ".join(f"{t:.3f}초" for t in times))
            code, hs = http(f"/api/p/{pid}/hs", {})
            code2, sim = http(f"/api/p/{pid}/sim", {"scenario": "base"})
            check("8 과거 재현 · 전망", code == 200 and code2 == 200 and str(hs["result"]["id"]).startswith("hs:") and str(sim["result"]["id"]).startswith("sim:"), f"{str(hs)[:150]} {str(sim)[:150]}")  # type: ignore[index]
            code, card = http(f"/api/p/{pid}/record?id={rec.get('id', '')}")
            code2, events = http("/api/events?since=0&wait=3")
            kinds = [e.get("type") for e in events.get("events", [])] if isinstance(events, dict) else []
            check("9 결과 카드와 알림 줄(새 기록이 생기는 순간 띠에)", code == 200 and "## 계수" in card.get("summary", "") and "record" in kinds and "job" in kinds, str(kinds))  # type: ignore[union-attr]
            code, data = http(f"/api/p/{pid}/data")
            code2, one = http(f"/api/p/{pid}/series?name=CN")
            code3, an = http(f"/api/p/{pid}/an", {"analysis": "unitroot", "target": "core"})
            data, one, an = (x if isinstance(x, dict) else {} for x in (data, one, an))
            check("9-1 자료 작업대·분석 — 자료의 세 층(원자료·시리즈·회차), 시리즈 하나의 값, 분석 하나",
                  (code, code2, code3) == (200, 200, 200) and data.get("mode") == "defs" and bool(data.get("current")) and len(data.get("sources", [])) == 2
                  and len(data.get("series", [])) >= 10 and len(one.get("values", [])) >= 100 and str(an.get("result", {}).get("id", "")).startswith("an:"),
                  f"{code} {code2} {code3} {str(data)[:150]} {str(an)[:150]}")
        finally:
            server.terminate()
            try:
                server.wait(10)
            except subprocess.TimeoutExpired:
                server.kill()

        if args.window:
            # 창 모드: 뜨면 '창은 하나' 파이프가 열린다 — 두 번째 실행은 폴더를 넘기고 바로 끝나야 한다
            pythonw = os.path.join(runtime, "pythonw.exe")
            first = subprocess.Popen([pythonw, "-I", "-m", "equion_desk", project], env=env)
            # 떠 있는 창에 넘겨 보기만 한다(없으면 1 — 창을 띄우지 않는다). 앱의 두 번째 실행이 맨 먼저 하는 일과 같다
            probe = ("import sys\nfrom equion_desk import instance\nfrom equion_desk.config import Config\n"
                     "sys.exit(0 if instance.forward(instance.pipe_name(Config().path.parent), None) else 1)\n")
            try:
                forwarded = False
                for _ in range(60):
                    time.sleep(0.5)
                    if first.poll() is not None:
                        break
                    if subprocess.run([python, "-I", "-c", probe], env=env, capture_output=True, timeout=30).returncode == 0:
                        forwarded = True
                        break
                check("10 창이 뜨고, 또 실행하면 떠 있는 창에 넘긴다(창은 하나)", forwarded and first.poll() is None, f"첫 실행 종료 코드 {first.poll()}")
            finally:
                subprocess.run(["taskkill", "/PID", str(first.pid), "/T", "/F"], capture_output=True)
    print(f"\n설치본 기동 시험: {'통과' if not FAILED else '실패 — ' + ', '.join(FAILED)}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
