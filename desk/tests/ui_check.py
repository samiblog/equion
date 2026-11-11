"""Equion Desk 화면 점검 — 진짜 브라우저(Edge)로 화면을 몰아 D1 의 완료 기준을 확인한다.

    uv run --package equion-desk --group ui python desk/tests/ui_check.py            # 점검만
    uv run --package equion-desk --group ui python desk/tests/ui_check.py --shots 폴더   # 화면 그림도 남긴다(밝은·어두운 바탕)

서버를 브라우저 모드로 띄우고(`python -m equion_desk --browser`) PC에 있는 Edge 를 창 없이 몬다 — 브라우저를 따로 받지 않는다
(Edge 가 없으면 playwright 의 chromium 을 찾는다: `python -m playwright install chromium`). 설정 파일과 예제 프로젝트는 임시 폴더에 둔다.

확인하는 것: 첫 화면 → 프로젝트 열기 → 부품을 눌러도 계산하지 않는다 → 추정이 1초 안에 화면에(S1) → **터미널에서 친 명령의 기록이
띠에 뜨고 카드로 열린다** → 과거 재현과 작업 줄 → 밖에서 고친 정의 파일의 바뀜 알림과 차이 → **닫았다 열면 이어진다** → 어두운 바탕.
서버·작업 프로세스 시험은 `test_app.py`, 이 파일은 화면까지 이어 본다(pytest 가 모으지 않는다 — 브라우저가 있어야 한다).
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
import time
import urllib.request

RESULTS: list[tuple[str, bool, str]] = []
PORT = 8793


def check(name: str, ok: object, detail: str = "") -> None:
    RESULTS.append((name, bool(ok), detail))
    print(("  ✓ " if ok else "  ✗ ") + name + (f" — {detail}" if detail and not ok else ""), flush=True)


def clean_env(config_dir: str) -> dict[str, str]:
    env = dict(os.environ, PYTHONIOENCODING="utf-8", EQUION_DESK_CONFIG_DIR=config_dir)
    for key in ("CLAUDECODE", "EQUION_WHO"):
        env.pop(key, None)
    return env


def equion(folder: str, env: dict[str, str], *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "equion", *args], cwd=folder, capture_output=True, text=True, encoding="utf-8", env=env)


LOG: list = []      # 서버가 알린 글을 남길 파일(--shots 를 주었을 때)


def start_server(env: dict[str, str], *args: str) -> subprocess.Popen:
    server = subprocess.Popen([sys.executable, "-m", "equion_desk", "--browser", "--port", str(PORT), *args], env=env,
                              stdout=subprocess.DEVNULL, stderr=LOG[0] if LOG else subprocess.DEVNULL)
    for _ in range(150):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/state", timeout=1).read()
            return server
        except OSError:
            time.sleep(0.1)
    server.kill()
    raise RuntimeError("서버가 뜨지 않았습니다")


def launch(pw):
    try:
        return pw.chromium.launch(channel="msedge", headless=True)
    except Exception:  # Edge 가 없는 PC — playwright 가 받아 둔 chromium
        return pw.chromium.launch(headless=True)


def run(shots: str | None) -> int:
    from playwright.sync_api import TimeoutError as Timeout
    from playwright.sync_api import sync_playwright

    RESULTS.clear()
    LOG.clear()
    if shots:
        os.makedirs(shots, exist_ok=True)
        LOG.append(open(os.path.join(shots, "server.log"), "w", encoding="utf-8"))
    url = f"http://127.0.0.1:{PORT}/"
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        env = clean_env(os.path.join(tmp, "cfg"))
        assert equion(tmp, env, "new", "demo", "--template", "desk").returncode == 0
        folder = os.path.join(tmp, "demo")
        errors: list[str] = []

        def shot(page, name: str) -> None:
            if shots:
                os.makedirs(shots, exist_ok=True)
                page.screenshot(path=os.path.join(shots, f"{name}.png"))

        def open_page(browser, scheme: str = "light"):
            page = browser.new_page(viewport={"width": 1480, "height": 900}, color_scheme=scheme)
            page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
            page.on("console", lambda m: errors.append(f"console: {m.text}") if m.type == "error" else None)
            page.goto(url)
            return page

        active = ".project:not([hidden])"
        pane = f"{active} .pane:not([hidden])"
        with sync_playwright() as pw:
            browser = launch(pw)

            print("U. 화면 — 첫 화면과 프로젝트 열기")
            server = start_server(env)
            try:
                page = open_page(browser)
                page.wait_for_selector("#welcome .welcome-card")
                check("U1 프로젝트 없이 띄우면 첫 화면 — 폴더 열기·예제 만들기",
                      page.locator("#welcome .btn").count() == 2 and page.locator("#activity").is_hidden())
                shot(page, "01-welcome")
                page.close()
            finally:
                server.terminate()
                server.wait(10)

            server = start_server(env, folder)
            try:
                page = open_page(browser)
                page.wait_for_selector(f"{active} .side .row-item[data-key='bench:demand:CN']", timeout=30000)
                page.wait_for_selector("#status .dot.ok")
                parts = page.locator(f"{active} .side .row-item[data-key^='bench:']").count()
                check("U2 프로젝트를 열면 사이드바에 모형·블록·부품, 상태줄에 '작업 프로세스 준비됨'",
                      parts == 6 and page.locator(".ptab").count() == 1 and "demo" in page.title(), f"부품 {parts}")
                shot(page, "02-home")

                print("V. 식 작업대 — 누르는 것만으로는 계산하지 않고, 추정은 1초 안에")
                page.click(f"{active} .side .row-item[data-key='bench:demand:CN']")
                page.wait_for_selector(f"{pane} .eq-box textarea")
                page.wait_for_timeout(600)
                check("V1 부품을 누르면 식 작업대가 열리고 식이 놓인다 — 계산하지 않는다(기록 없음)",
                      page.input_value(f"{pane} .eq-box textarea") == "CN c Y CN(-1)" and page.locator("#strip .chip").count() == 0
                      and not os.path.isdir(os.path.join(folder, "work", "est")))
                page.click(f"{pane} .eq-box textarea")
                page.keyboard.press("Control+Enter")
                page.wait_for_selector(f"{pane} table.grid tbody tr")
                page.wait_for_selector(f"{pane} .fit svg path")
                timing = page.inner_text(f"{pane} .timing")
                took = float(timing.split("화면까지")[1].split("초")[0])
                check("V2 Ctrl+Enter 로 추정 — 계수표·진단·차트가 뜬다",
                      page.locator(f"{pane} table.grid").first.locator("tbody tr").count() == 3 and page.locator(f"{pane} .fit svg path").count() >= 3)
                check("V3 누른 뒤 화면까지 1초 안(성공 기준 S1)", took < 1.0, timing)
                page.wait_for_selector("#strip .chip")
                check("V4 기록이 생기는 순간 작업 기록 띠에 뜬다", "cn_0001" in page.inner_text("#strip .chip >> nth=0"))
                page.hover(f"{pane} .fit svg rect[fill='transparent']")
                check("V5 차트에 마우스를 올리면 그 기간의 값이 뜬다", page.locator(f"{pane} .fit .tip").is_visible())
                shot(page, "03-bench")
                page.fill(f"{pane} .eq-box textarea", "CN c Y CN(-1) CN(-2)")
                page.keyboard.press("Control+Enter")
                page.wait_for_function("document.querySelectorAll('#strip .chip').length >= 2")
                page.wait_for_function(f"document.querySelector(\"{pane} table.grid\").tBodies[0].rows.length === 4")
                check("V6 식을 고쳐 추정하면 후보로 기록된다(파일은 그대로)",
                      "CN c Y CN(-1)  " in open(os.path.join(folder, "EQUATIONS", "demand.txt"), encoding="utf-8").read().replace("\t", " "))

                print("W. 터미널에서 친 명령의 기록이 띠에 뜨고 카드로 열린다(D1 완료 기준)")
                typed = page.locator(f"{active} .term-body .xterm").count() > 0
                before = page.locator("#strip .chip").count()
                if typed:
                    page.click(f"{active} .term-body")
                    page.wait_for_timeout(1500)          # 셸이 뜰 때까지
                    page.keyboard.type("equion hs main")
                    page.keyboard.press("Enter")
                else:                                     # 의사 콘솔이 없는 OS — 터미널에서 친 것과 같은 명령을 밖에서 돌린다
                    equion(folder, env, "hs", "main")
                try:
                    page.wait_for_function(f"document.querySelectorAll('#strip .chip').length > {before}", timeout=60000)
                    chip = page.locator("#strip .chip").first
                    text = chip.inner_text()
                    ok = "hs_0001" in text and "터미널" in text and "unseen" in (chip.get_attribute("class") or "")
                except Timeout:
                    ok, text = False, page.inner_text(f"{active} .term-body")[-300:]
                check("W1 터미널에 'equion hs main' 을 치면 그 기록이 띠에 뜬다(누가: 터미널, 아직 보지 않음 표시)" + ("" if typed else " — 밖에서 돌림"), ok, text)
                page.locator("#strip .chip").first.click()
                page.wait_for_selector(f"{pane} .doc .chart svg", timeout=30000)
                check("W2 띠의 기록을 누르면 결과 카드가 열린다 — 표와 차트(vega-lite)",
                      page.locator(f"{pane} .doc table").count() >= 2 and page.locator(f"{pane} .doc .chart svg").count() >= 1
                      and page.locator(f"{pane} .doc .chart.failed").count() == 0 and "unseen" not in (page.locator("#strip .chip").first.get_attribute("class") or ""))
                page.wait_for_timeout(400)
                shot(page, "04-card")

                print("X. 작업 줄 · 바뀜 알림")
                page.click(f"{active} .tabbar .tab >> nth=0")
                page.click(f"{pane} .card >> nth=1 >> .foot .btn >> nth=1")        # 모형 main 의 '전망'
                page.wait_for_selector("#job .job")
                page.wait_for_selector("#job .job.done", timeout=60000)
                page.wait_for_selector(f"{active} .tabbar .tab[aria-selected='true'] .title:has-text('sim:')")
                check("X1 '전망' 단추 — 작업 줄에 도는 일과 끝난 일(기록 이름), 결과 카드가 열린다", "sim:" in page.inner_text("#job .job.done"))
                with open(os.path.join(folder, "EQUATIONS", "price.txt"), "a", encoding="utf-8", newline="\n") as f:
                    f.write("\n# 밖에서 고친 줄\n")
                page.wait_for_selector(f"{active} .notice[data-change]", timeout=20000)
                note = page.inner_text(f"{active} .notice[data-change]")
                check("X2 정의 파일을 밖에서 고치면 바뀜 알림이 뜬다(파일·늘고 준 줄 수)", "EQUATIONS/price.txt" in note and "+2" in note, note)
                shot(page, "05-notice")
                page.click(f"{active} .notice[data-change] .btn.primary")
                page.wait_for_selector(f"{pane} .diff .dl.add")
                check("X3 '차이 보기' — 바뀜 기록의 전후 차이", page.locator(f"{pane} .diff .dl.add").count() == 2 and page.locator(f"{active} .notice[data-change]").count() == 0)
                shot(page, "06-changes")
                page.click(f"{active} .side-tabs [data-side='files']")
                page.wait_for_selector(f"{active} .side .row-item:has-text('README.md')")
                page.click(f"{active} .side .row-item:has-text('README.md')")
                page.wait_for_selector(f"{pane} .doc h1")
                check("X4 파일 탭 — md 파일을 문서로 본다", page.locator(f"{pane} .doc h1").count() >= 1)

                print("Y. 닫았다 열면 이어진다(D1 완료 기준)")
                page.click(f"{active} .tabbar .tab:has-text('demand:CN')")
                page.fill(f"{pane} .eq-box textarea", "CN c Y CN(-1) G")
                tabs = page.locator(f"{active} .tabbar .tab").all_inner_texts()
                page.wait_for_timeout(900)               # 화면 상태를 적을 틈
                page.close()
            finally:
                server.terminate()
                server.wait(10)

            server = start_server(env)                    # 폴더를 주지 않고 다시 띄운다 — 지난 탭을 되살린다
            try:
                page = open_page(browser, "dark")
                page.wait_for_selector("#status .dot.ok", timeout=30000)
                page.wait_for_selector(f"{pane} .eq-box textarea")
                again = page.locator(f"{active} .tabbar .tab").all_inner_texts()
                check("Y1 다시 띄우면 프로젝트 탭·연 탭·고른 탭·쓰던 식이 그대로다",
                      again == tabs and page.input_value(f"{pane} .eq-box textarea") == "CN c Y CN(-1) G"
                      and "demand:CN" in page.inner_text(f"{active} .tabbar .tab[aria-selected='true']"), f"{tabs} → {again}")
                page.wait_for_selector(f"{pane} table.grid tbody tr")
                check("Y2 식 작업대는 보던 기록을 다시 보인다(다시 계산하지 않는다)", page.locator("#strip .chip").count() == 4)
                check("Y3 사이드바의 고른 탭(파일)도 그대로", page.locator(f"{active} .side-tabs [data-side='files']").get_attribute("aria-selected") == "true")
                check("Y4 어두운 바탕 — 운영체제 설정을 따른다", page.evaluate("document.documentElement.dataset.theme") == "dark")
                shot(page, "07-dark")
                page.click("#btn-settings")
                page.click(".popover .segmented button >> nth=1")
                check("Y5 설정에서 바탕을 바꾸면 바로 바뀐다", page.evaluate("document.documentElement.dataset.theme") == "light")
                page.close()
            finally:
                server.terminate()
                server.wait(10)
            browser.close()
        check("Z1 화면 오류가 없다(스크립트 오류·콘솔 오류)", not errors, " | ".join(errors[:5]))
    bad = [n for n, ok, _ in RESULTS if not ok]
    print(f"\nEquion Desk 화면 점검 {len(RESULTS) - len(bad)}/{len(RESULTS)}")
    return len(bad)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Equion Desk 화면 점검")
    ap.add_argument("--shots", metavar="폴더", help="화면 그림을 남길 폴더")
    sys.exit(1 if run(ap.parse_args().shots) else 0)
