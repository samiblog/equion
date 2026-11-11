"""Equion Desk 화면 점검 — 진짜 브라우저(Edge)로 화면을 몰아 D1·D2·D3 의 완료 기준을 확인한다.

    uv run --package equion-desk --group ui python desk/tests/ui_check.py            # 점검만
    uv run --package equion-desk --group ui python desk/tests/ui_check.py --shots 폴더   # 화면 그림도 남긴다(밝은·어두운 바탕)

서버를 브라우저 모드로 띄우고(`python -m equion_desk --browser`) PC에 있는 Edge 를 창 없이 몬다 — 브라우저를 따로 받지 않는다
(Edge 가 없으면 playwright 의 chromium 을 찾는다: `python -m playwright install chromium`). 설정 파일과 예제 프로젝트는 임시 폴더에 둔다.

확인하는 것: 첫 화면 → 프로젝트 열기 → 부품을 눌러도 계산하지 않는다 → 추정이 1초 안에 화면에(S1) → 식 작업대(치는 동안의 검사 ·
후보 목록 · 겹쳐 보기 · 기간 짚기 · **채택** · **이 후보로 과거 재현** · 항등식 검사 — D2a) → 자료 작업대(받은 상자 → **자료 만들기 → 견주기 →
이 회차로 바꾸기**)와 분석 탭(등록부의 폼 · 명령 줄 · **미리보기 → 정의로 남기기** — D2b-1) → 불러오기(읽은 그대로의 표 · 틀을 권하는 단추 ·
열 ↔ 시리즈 · **무엇이 적히는지 보고 저장** — D2b-2) → 회차 바꾼 뒤 할 일 · 모형 작업대(조립 · 새 모형 · **과거 재현 · 원인 따라가기** ·
이 블록만 풀기) · 블록 파일 고치기 · 흐름 화면(**스크립트를 화면에서 실행** — D3) → **터미널에서 친 명령의 기록이
띠에 뜨고 카드로 열린다** → 전망과 작업 줄 → 밖에서 고친 정의 파일의 바뀜 알림과 차이 → **닫았다 열면 이어진다** → 어두운 바탕.
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

        leaks: list[str] = []

        def shot(page, name: str) -> None:
            # 화면에 값 대신 'null'·'undefined'·'NaN'·'[object …]' 이 찍혔는지도 여기서 본다(터미널의 글은 빼고)
            found = page.evaluate("""() => {
                const clone = document.body.cloneNode(true);
                clone.querySelectorAll('.term-body, script, style').forEach((n) => n.remove());
                return (clone.textContent.match(/(^|[^\\w.])(null|undefined|NaN|\\[object [A-Za-z]+\\])(?![\\w])/g) || []).slice(0, 5);
            }""")
            leaks.extend(f"{name}: {x.strip()}" for x in found)
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
                check("U1 프로젝트 없이 띄우면 첫 화면 — 폴더 열기·예제 만들기·도움말",
                      page.locator("#welcome .btn").count() == 3 and page.locator("#activity").is_hidden())
                shot(page, "01-welcome")
                page.click("#welcome [data-act=help]")
                page.wait_for_selector(".dialog.help .doc h1")
                helped = page.inner_text(".dialog.help .doc h1")
                page.keyboard.press("Escape")
                check("U1-1 첫 화면의 도움말 — 프로젝트가 없으면 상자로 뜨고 Esc 로 닫힌다", "Equion Desk 도움말" in helped and page.locator(".dialog.help").count() == 0)
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
                page.wait_for_selector(f"{pane} .fit svg path >> nth=2")       # 실측·적합·잔차 세 선이 다 그려질 때까지
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

                print("B. 식 작업대 — 치는 동안의 검사 · 후보 목록 · 겹쳐 보기 · 채택(D2a)")
                area = f"{pane} .eq-box textarea"
                run = f"{pane} .eq-run .btn.primary"
                rows = f"{pane} table.cand tbody tr"
                page.fill(area, "CN c Y (")
                page.wait_for_selector(f"{pane} .eq-status.bad")
                check("B1 치는 동안 문법을 검사한다 — 읽을 수 없는 식은 까닭을 보이고 추정을 막는다",
                      "괄호" in page.inner_text(f"{pane} .eq-status") and page.locator(run).is_disabled())
                page.fill(area, "CN c Y ZZZ")
                page.wait_for_selector(f"{pane} .eq-status.warn")
                unknown = page.inner_text(f"{pane} .eq-status")
                page.fill(area, "I c Y")
                page.wait_for_function("document.querySelector('.project:not([hidden]) .pane:not([hidden]) .eq-status').textContent.includes('목표')")
                check("B2 자료에 없는 변수와, 이 부품의 목표가 아닌 식을 알린다(추정하지 않고)",
                      "ZZZ" in unknown and "후보가 되지 않습니다" in page.inner_text(f"{pane} .eq-status") and page.locator(run).is_disabled()
                      and page.locator("#strip .chip").count() == 2)

                page.fill(area, "CN c Y CN(-1) CN(-2)")
                page.select_option(f"{pane} .eq-opts select", "hac")
                page.fill(f"{pane} .eq-opts input[aria-label='표본의 처음']", "1990Q1")
                page.keyboard.press("Enter")                       # 표본 칸에서 Enter 도 추정
                page.wait_for_selector(f"{pane} .result-head .tag:has-text('표준오차 HAC')")
                page.wait_for_function("document.querySelectorAll('.project:not([hidden]) .pane:not([hidden]) table.cand tbody tr').length === 3")   # 목록은 결과 바로 뒤에
                head = page.inner_text(f"{pane} .result-head")
                check("B3 표본·표준오차를 골라 추정 — 결과가 무엇으로 본 것인지 말한다", "1990Q1" in head and page.locator(rows).count() == 3, head)
                page.click(run)
                page.wait_for_selector(f"{pane} table.cand .times")
                page.wait_for_function("document.querySelectorAll('#strip .chip').length === 4")
                check("B4 같은 계산을 다시 하면 목록의 한 줄로 모인다(×2) — 기록은 둘 다 남는다",
                      page.locator(rows).count() == 3 and "×2" in page.inner_text(f"{pane} table.cand .times") and page.locator("#strip .chip").count() == 4)
                before = page.locator("#strip .chip").count()
                page.click(f"{rows}:has-text('cn_0001')")
                page.wait_for_selector(f"{pane} .result-head .rid:has-text('est:cn_0001')")
                check("B5 후보의 줄을 누르면 그 기록이 보인다 — 다시 계산하지 않는다", page.locator("#strip .chip").count() == before)
                page.click("#btn-term")                            # 터미널을 접어 넓게 — 덜 중요한 열까지 보인다
                page.wait_for_selector(f"{pane} table.cand th:has-text('AIC')")
                marks = page.locator(f"{pane} table.cand td.nc").count()
                why = page.locator(f"{pane} table.cand td.nc").first.get_attribute("title") or ""
                check("B6 표본이 다른 후보는 AIC·BIC 를 견줄 수 없다고 표시한다", marks >= 2 and "표본이 달라" in why, f"{marks} {why}")
                shot(page, "03b-candidates")

                page.click(f"{rows}:has-text('cn_0001') .check")
                page.click(f"{rows}:has-text('cn_0002') .check")
                page.click(f"{pane} .cand-tools .btn:has-text('겹쳐 보기')")
                page.wait_for_selector(f"{pane} .ov-legend .ov-item")
                page.wait_for_selector(f"{pane} .fit svg path")
                check("B7 겹쳐 보기 — 고른 후보의 적합을 한 축에, 계수와 통계를 나란히",
                      page.locator(f"{pane} .ov-legend .ov-item").count() == 2 and page.locator(f"{pane} .fit svg path").count() >= 3
                      and page.locator(f"{pane} table.ov-table thead th").count() == 3 and "CN(-2)" in page.inner_text(f"{pane} table.ov-table"))
                page.click(f"{pane} .segmented button:has-text('단독 모의')")
                page.wait_for_selector(f"{pane} .fit .legend .key:has-text('%')")
                check("B8 겹쳐 보기 — 단독 모의를 견준다(RMSPE 와 함께)", page.locator(f"{pane} .fit .legend .key").count() == 3)
                shot(page, "03c-overlay")
                page.click(f"{pane} .cand-tools .btn:has-text('겹쳐 보기 닫기')")
                page.wait_for_selector(f"{pane} .result-actions")

                page.wait_for_selector(f"{pane} .fit svg rect[fill='transparent']")
                hit = page.locator(f"{pane} .fit svg rect[fill='transparent']")
                box = hit.bounding_box()
                hit.click(position={"x": box["width"] * 0.8, "y": box["height"] * 0.7})      # 화면 밖이면 끌어와서 누른다
                page.wait_for_selector(f"{pane} .pinned:not([hidden])")
                page.click(f"{pane} .pinned .btn")
                check("B9 차트에서 기간을 짚어 그 기간의 더미를 식 칸에 넣는다(계산은 추정을 누를 때)",
                      "@d(" in page.input_value(area) and page.locator("#strip .chip").count() == before, page.input_value(area))

                page.click(f"{rows}:has-text('cn_0002')")
                page.wait_for_selector(f"{pane} .result-head .rid:has-text('est:cn_0002')")
                page.click(f"{pane} .result-actions .btn.primary")
                page.wait_for_selector(".dialog .diff .dl.add")
                said = page.inner_text(".dialog")
                shot(page, "03d-adopt")
                page.click(".dialog-foot .btn >> nth=0")           # 취소
                block = os.path.join(folder, "EQUATIONS", "demand.txt")
                kept = "CN c Y CN(-1)  " in open(block, encoding="utf-8").read().replace("\t", " ")
                check("B10 채택 — 무엇이 바뀌는지(블록 파일의 줄·채택표) 먼저 보인다. 취소하면 아무것도 바뀌지 않는다",
                      "- CN c Y CN(-1)" in said and "+ CN c Y CN(-1) CN(-2)" in said and "adopted.toml" in said and kept and page.locator(".dialog").count() == 0, said)
                page.click(f"{pane} .result-actions .btn.primary")
                page.click(".dialog-foot .btn.primary")
                page.wait_for_selector(f"{pane} .view-head .tag.accent:has-text('cn_0002')", timeout=20000)
                page.wait_for_selector(f"{rows}:has-text('cn_0002') .star")
                line = open(block, encoding="utf-8").read().splitlines()[1]
                check("B11 채택하면 블록 파일의 그 줄이 바뀌고(설명은 그대로) 화면에 ★ — 알림 카드는 띄우지 않는다(내가 한 일)",
                      line.startswith("CN c Y CN(-1) CN(-2)") and "#" in line and page.locator(f"{active} .notice[data-change]").count() == 0, line)

                page.click(f"{rows}:has-text('cn_0001')")
                page.wait_for_selector(f"{pane} .result-head .rid:has-text('est:cn_0001')")
                page.click(f"{pane} .result-actions .btn:has-text('이 후보로 과거 재현')")
                page.click(".menu .menu-item >> nth=0")            # 기본 모형(main)
                page.wait_for_selector(f"{pane} .vs .vs-cell", timeout=60000)
                check("B12 이 후보로 과거 재현 — 파일은 그대로 두고 끼워 풀어, 변수마다 전후를 먼저 보인다",
                      page.locator(f"{pane} .vs .vs-cell").count() >= 3 and "--swap demand:CN=est:cn_0001" in page.inner_text(f"{pane} .cmdline")
                      and open(block, encoding="utf-8").read().splitlines()[1] == line)
                shot(page, "03e-hs-swap")
                page.click(f"{pane} .banner .btn:has-text('식 작업대에서')")
                page.wait_for_selector(f"{pane} .result-head .rid:has-text('est:cn_0001')")
                check("B13 카드에서 그 후보의 식 작업대로 돌아간다 — 쓰던 식은 그대로", "@d(" in page.input_value(area))

                page.click("#btn-term")                            # 터미널 다시
                page.click(f"{active} .side .row-item[data-key='bench:demand:Y']")
                page.click(f"{pane} .ident-bar .btn")
                page.wait_for_selector(f"{pane} .tag.ok:has-text('실측과 맞습니다')")
                check("B14 항등식은 추정하지 않고 실측으로 검사한다", page.locator(f"{pane} .eq-box").count() == 0)

                print("A. 자료 작업대 · 분석(D2b)")
                first = page.inner_text("#status button.item b")
                # 정의의 글만 고쳤다(값은 같다) — 바뀌었다고 알리되, 만들어 보아 값이 같으면 같은 것을 다시 권하지 않는다
                with open(os.path.join(folder, "DATA", "series.toml"), "a", encoding="utf-8", newline="\n") as f:
                    f.write("\n# 값과 무관한 주석 한 줄\n")
                page.wait_for_selector(f"{active} .notice[data-change]", timeout=20000)
                page.click(f"{active} .notice[data-change] .icon-btn")
                page.click(f"{active} .side .row-item[data-key='data']")
                page.wait_for_selector(f"{pane} .banner.warn")
                told = page.inner_text(f"{pane} .banner.warn")
                page.click(f"{pane} .banner.warn .btn")            # 자료 만들기 — 값이 같아 새 회차가 생기지 않는다
                page.wait_for_selector(f"{pane} .banner.ok")
                page.click(f"{pane} .flow-card >> nth=2")
                check("A0 정의의 글만 고치면 '바뀐 것이 있습니다'(무엇이 바뀌었는지) → 만들어 보아 값이 같으면 회차는 그대로이고 다시 권하지 않는다",
                      "series.toml" in told and page.locator(f"{pane} .vint").count() == 1 and first in page.inner_text(f"{pane} .banner.ok")
                      and page.locator(f"{active} .side .row-item[data-key='data'] .dot").count() == 0, told)
                page.click(f"{pane} .flow-card >> nth=1")
                # 새 분기 자료가 받은 상자에 왔다 — 한 분기가 늘고 지난 분기의 값 하나가 고쳐졌다(개정)
                with open(os.path.join(folder, "DATA", "raw", "toy_q.csv"), encoding="utf-8") as f:
                    lines = f.read().rstrip("\n").split("\n")
                cells = lines[-2].split(",")
                cells[1] = f"{float(cells[1]) * 1.02:.4f}"
                lines[-2] = ",".join(cells)
                lines.append(",".join(["2020Q1"] + [f"{float(v) * 1.01:.4f}" for v in lines[-1].split(",")[1:]]))
                os.makedirs(os.path.join(folder, "DATA", "raw", "inbox"), exist_ok=True)
                with open(os.path.join(folder, "DATA", "raw", "inbox", "toy_q_2026-12.csv"), "w", encoding="utf-8", newline="\n") as f:
                    f.write("\n".join(lines) + "\n")
                page.wait_for_selector(f"{pane} .banner:has-text('받은 상자')", timeout=20000)      # 폴더가 바뀐 것을 알아채고 다시 읽는다
                page.wait_for_selector(f"{pane} table.series tr.row")
                check("A1 자료 작업대 — 세 층(원자료 → 시리즈 → 회차)과 지금 할 일 한 줄, 시리즈 목록",
                      page.locator(f"{pane} .flow-card").count() == 3 and page.locator(f"{pane} table.series tr.row").count() == 13
                      and "받은 상자에 새 파일 1개" in page.inner_text(f"{pane} .banner") and first in page.inner_text(f"{pane} .flow-card >> nth=2"))
                page.fill(f"{pane} .find", "금리")
                found = page.locator(f"{pane} table.series tr.row").all_inner_texts()
                check("A2 이름·설명으로 시리즈를 찾는다", 0 < len(found) < 13 and all("금리" in x for x in found), str(found))
                page.fill(f"{pane} .find", "")
                page.click(f"{pane} table.series tr.row:has(b:text-is('CNSA'))")
                page.wait_for_selector(f"{pane} .series-detail .fit svg")
                check("A3 시리즈를 누르면 내력(원자료 → 열 → 계절조정 → 시리즈)과 차트 — 원자료 값과 겹쳐 보인다",
                      page.locator(f"{pane} .lineage .stepchip").count() == 4 and page.locator(f"{pane} .series-detail .legend .key").count() == 2
                      and "계절조정" in page.inner_text(f"{pane} .lineage"), page.inner_text(f"{pane} .lineage"))
                page.wait_for_timeout(300)
                shot(page, "03a-data")
                page.click(f"{pane} .banner .btn")                 # 받은 상자 보기
                page.wait_for_selector(f"{pane} .inbox-item")
                check("A4 원자료 — 정의가 읽는 파일마다 틀(주기·구간·열)과 읽는 시리즈, 받은 상자의 파일과 짝지은 원자료",
                      page.locator(f"{pane} .source").count() == 2 and "1970Q1~2019Q4" in page.inner_text(f"{pane} .source >> nth=0")
                      and "na 의 새 파일" in page.inner_text(f"{pane} .inbox-item"), page.inner_text(f"{pane} .inbox-item"))
                page.click(f"{pane} .inbox-item .btn.primary")
                page.wait_for_selector(f"{pane} .banner.warn")
                check("A5 받은 파일을 넣으면 받은 상자가 비고 '자료 만들기'를 권한다(저절로 만들지 않는다)",
                      page.locator(f"{pane} .inbox-item").count() == 0 and "toy_q_2026-12.csv" in page.inner_text(f"{pane} .source >> nth=0")
                      and "원자료 na" in page.inner_text(f"{pane} .banner.warn") and first in page.inner_text("#status"))
                page.click(f"{pane} .banner.warn .btn")            # 자료 만들기
                page.wait_for_selector(f"{pane} .diffbox table")
                box = page.inner_text(f"{pane} .diffbox")
                check("A6 자료 만들기 — 새 회차가 생기고(지금 회차는 그대로) 달라진 값과 그것을 쓰는 식을 보인다",
                      page.locator(f"{pane} .vint").count() == 2 and "지금" in page.inner_text(f"{pane} .vint.now") and first in page.inner_text(f"{pane} .vint.now")
                      and "2020Q1" in box and "개정" in box and "demand:CN" in box and "준비돼" in page.inner_text(f"{pane} .banner"), box[:300])
                shot(page, "03b-vintages")
                second = page.get_attribute(f"{pane} .vint:not(.now)", "data-vintage")
                page.click(f"{pane} .vint [data-act='use']")
                page.wait_for_selector(".dialog")
                dialog = page.inner_text(".dialog")
                page.click(".dialog .btn.primary")
                page.wait_for_selector(f"{pane} .banner.ok")
                check("A7 이 회차로 바꾸기 — 설정의 어느 줄이 바뀌는지와 다시 추정·풀기는 따로임을 먼저 보이고, 바꾸면 상태줄의 회차가 바뀐다",
                      f'vintage = "{second}"' in dialog and "따로" in dialog and second in page.inner_text("#status")
                      and second in page.inner_text(f"{pane} .vint.now"), dialog[:300])
                page.click(f"{pane} .vint[data-vintage='{first}'] [data-act='use']")
                page.wait_for_selector(".dialog")
                page.click(".dialog .btn.primary")
                page.wait_for_selector(f"{pane} .vint.now[data-vintage='{first}']")
                check("A8 옛 회차로 되돌아갈 수 있다 — 새 회차는 그대로 남아 '준비돼 있다'고 알린다",
                      first in page.inner_text("#status") and "준비돼" in page.inner_text(f"{pane} .banner") and page.locator(f"{pane} .vint").count() == 2)

                page.click(f"{active} .side .row-item[data-key='analysis']")
                page.wait_for_selector(f"{pane} .an-row")
                check("A9 분석 — 등록부의 분석이 갈래마다 한 줄씩(무엇을 만드는 분석인지와 함께)",
                      page.locator(f"{pane} .an-row").count() >= 13 and page.locator(f"{pane} .an-row .tag").count() >= 5)
                page.click(f"{pane} .an-row[data-analysis='unitroot']")
                page.click(f"{pane} .pick-row .pc:text-is('core')")
                page.select_option(f"{pane} [data-opt='trend']", "ct")
                preview = page.inner_text(f"{pane} .an-form .cmdline .cmd")
                page.keyboard.press("Control+Enter")
                page.wait_for_selector(f"{pane} .an-out .doc h2")
                rid = page.inner_text(f"{pane} .an-out .result-head .rid")
                check("A10 대상과 옵션을 고르면 같은 일을 하는 명령이 그대로 보이고, 실행한 기록의 명령과 글자까지 같다",
                      preview == "equion an unitroot core --trend ct" and preview in page.text_content(f"{pane} .an-out .doc")
                      and rid.startswith("an:unitroot_") and "단위근" in page.inner_text(f"{pane} .an-out .doc"), preview)
                page.wait_for_timeout(300)
                shot(page, "03c-analysis")
                page.click(f"{active} .side .row-item[data-key='data']")
                page.click(f"{pane} .flow-card >> nth=1")
                if page.locator(f"{pane} table.series tr.row.open").count():
                    page.click(f"{pane} table.series tr.row.open")           # 펼쳐 둔 줄을 접는다
                page.click(f"{pane} table.series tr.row:has(b:text-is('CN'))")
                page.click(f"{pane} .detail-foot .btn:has-text('계절조정')")
                page.wait_for_selector(f"{pane} [data-act='keep']", timeout=30000)
                check("A11 시리즈의 '계절조정' — 분석 탭이 그 시리즈로 열려 미리보기를 돌린다(아직 아무것도 바뀌지 않는다)",
                      page.input_value(f"{pane} .an-target") == "CN" and "미리보기" in page.inner_text(f"{pane} .an-out .banner")
                      and "CN_SA" not in open(os.path.join(folder, "DATA", "series.toml"), encoding="utf-8").read())
                page.click(f"{pane} [data-act='keep']")
                page.wait_for_selector(".dialog")
                page.fill(".dialog input[type=text]", "CN_SA")
                line = page.inner_text(".dialog .diff")
                shot(page, "03d-keep")
                page.click(".dialog .btn.primary")
                page.wait_for_selector(f"{pane} .an-out .banner.ok")
                check("A12 정의로 남기기 — 어느 파일에 무엇이 적히는지 먼저 보이고, 남기면 series.toml 에 적힌다(알림 카드는 띄우지 않는다)",
                      "[series.CN_SA]" in line and "[series.CN_SA]" in open(os.path.join(folder, "DATA", "series.toml"), encoding="utf-8").read()
                      and page.locator(f"{active} .notice[data-change]").count() == 0, line)
                page.click(f"{pane} .an-out .banner.ok .btn")       # 자료 작업대로
                page.wait_for_selector(f"{pane} .banner.warn")
                page.wait_for_selector(f"{pane} table.series tr.row:has(b:text-is('CN_SA'))")
                check("A13 남긴 정의가 자료 작업대에 보인다 — 아직 회차에 없다고 표시하고 '자료 만들기'를 권한다",
                      "회차에 없음" in page.inner_text(f"{pane} table.series tr.row:has(b:text-is('CN_SA'))")
                      and "series.toml" in page.inner_text(f"{pane} .banner.warn") and page.locator(f"{pane} table.series tr.row").count() == 14)

                print("M. 불러오기(D2b-2)")
                # 통계표 꼴의 원자료가 DATA/raw/ 에 놓였다 — 표 위에 제목 줄, 열 이름 아래 단위 줄, 결측 표시(- …), 천 단위 쉼표, '1970년 1/4분기' 꼴의 시점
                with open(os.path.join(folder, "DATA", "raw", "toy_q.csv"), encoding="utf-8") as f:
                    table = [ln.split(",") for ln in f.read().rstrip("\n").split("\n")[1:]]
                cells = [[r[0][:4] + "년 " + r[0][5] + "/4분기", f'"1,{float(r[1]):.1f}"', f"{float(r[2]):.2f}", f'"{float(r[4]) * 10:,.1f}"'] for r in table]
                cells[2][1], cells[3][2] = "-", "…"
                with open(os.path.join(folder, "DATA", "raw", "kr.csv"), "w", encoding="utf-8", newline="\n") as f:
                    f.write("표 1. 지출 항목별 국내총생산(가상)\n시점,민간소비,설비투자,GDP\n,십억원,십억원,십억원\n" + "\n".join(",".join(c) for c in cells) + "\n")
                series_toml = os.path.join(folder, "DATA", "series.toml")
                page.click(f"{pane} .flow-card >> nth=0")
                page.wait_for_selector(f"{pane} .unused-item:has-text('kr.csv')", timeout=20000)       # 폴더가 바뀐 것을 알아채고 다시 읽는다
                page.click(f"{pane} .unused-item:has-text('kr.csv') .link")
                page.wait_for_selector(f"{pane} .raw-grid")
                page.wait_for_selector(f"{pane} [data-hint]")
                check("M1 읽지 않는 파일의 '불러오기' — 읽은 그대로의 줄과, 읽지 못한 까닭·해 볼 것(단추)",
                      "읽지 못했습니다" in page.inner_text(f"{pane} .banner.error") and "표 1." in page.inner_text(f"{pane} .raw-grid tbody tr >> nth=0")
                      and page.locator(f"{pane} .pick").count() == 0 and page.locator(f"{pane} [data-act='store']").count() == 0)
                for _ in range(6):                        # 권하는 단추를 차례로: 열 이름 줄 → 단위 줄 → 천 단위 → 결측 표시
                    if not page.locator(f"{pane} [data-hint]").count():
                        break
                    page.click(f"{pane} [data-hint] >> nth=0")
                    page.wait_for_timeout(900)
                page.wait_for_selector(f"{pane} .banner.ok")
                check("M2 권하는 단추를 차례로 누르면 틀이 맞는다(열 이름 줄·단위 줄·천 단위·결측 표시) — 표에 그 줄과 칸이 표시된다",
                      page.input_value(f"{pane} [data-frame='header_row']") == "2" and page.input_value(f"{pane} [data-frame='unit_row']") == "3"
                      and page.input_value(f"{pane} [data-frame='thousands']") == "," and sorted(page.input_value(f"{pane} [data-frame='missing']").split()) == ["-", "…"]
                      and page.locator(f"{pane} .raw-grid tr.hdr").count() == 1 and page.locator(f"{pane} .raw-grid td.miss").count() == 2
                      and page.locator(f"{pane} .pick").count() == 3 and "1970Q1~2019Q4" in page.inner_text(f"{pane} .banner.ok"), page.inner_text(f"{pane} .banner.ok"))
                kcn = f"{pane} .pick[data-column='민간소비']"
                page.click(f"{kcn} input[type=checkbox]")
                page.fill(f"{kcn} [data-key='name']", "소비")
                refused = "bad" in (page.get_attribute(f"{kcn} [data-key='name']", "class") or "")
                page.fill(f"{kcn} [data-key='name']", "KCN")
                page.click(f"{pane} .pick[data-column='GDP'] input[type=checkbox]")
                page.select_option(f"{kcn} [data-key='seas']", "stl:multiplicative")
                page.click(f"{kcn} [data-act='try']")
                page.wait_for_selector(f"{pane} .try-chart .banner.error")
                why = page.inner_text(f"{pane} .try-chart .banner.error")        # 결측 표시(-)가 가운데 있어 계절조정을 못 한다
                page.select_option(f"{kcn} [data-key='fill']", "linear")         # 고르면 미리보기를 다시 만든다
                page.wait_for_selector(f"{pane} .try-chart .fit svg")
                check("M3 열을 골라 이름을 준다 — 영문이 아닌 이름은 바로 알리고, 한글 열 이름은 설명에. 미리보기는 안 되는 까닭(안쪽 결측)을 알리고, 채움을 고르면 원자료와 만든 값을 겹쳐 보인다",
                      refused and page.input_value(f"{kcn} [data-key='desc']") == "민간소비" and page.input_value(f"{kcn} [data-key='unit']") == "십억원"
                      and page.input_value(f"{pane} .pick[data-column='GDP'] [data-key='name']") == "GDP" and "결측" in why
                      and page.locator(f"{pane} .try-chart .legend .key").count() == 2 and "계절조정" in page.inner_text(f"{pane} .try-chart .raw-cap"), why)
                page.wait_for_timeout(300)
                shot(page, "03e-import")
                before = open(series_toml, encoding="utf-8").read()
                page.click(f"{pane} [data-act='store']")
                page.wait_for_selector(".dialog .diff")
                dialog = page.inner_text(".dialog")
                check("M4 저장하기 전에 무엇이 적히는지(차이)와 같은 일을 하는 명령을 보인다 — 아직 아무것도 쓰지 않았다",
                      "+[source.kr]" in dialog and '+from = "kr:민간소비"' in dialog and "+header_row = 2" in dialog and "equion data define kr" in dialog
                      and "multiplicative" in dialog and '+fill = "linear"' in dialog and open(series_toml, encoding="utf-8").read() == before, dialog[:300])
                shot(page, "03f-import-save")
                page.click(".dialog .btn.primary")
                page.wait_for_selector(f"{pane} .banner.ok:has-text('정의에 저장했습니다')")
                page.wait_for_selector(f"{pane} .src-fixed")
                check("M5 저장하면 series.toml 에 적히고, 화면은 그 출처의 틀과 짝지은 열('정의에 있음')로 다시 열린다",
                      "[series.KCN]" in open(series_toml, encoding="utf-8").read() and page.locator(f"{pane} .pick .tag:has-text('정의에 있음')").count() == 2
                      and "kr" in page.inner_text(f"{pane} .src-fixed") and page.locator(f"{active} .notice[data-change]").count() == 0)
                page.click(f"{pane} .banner.ok .btn")              # 자료 작업대로
                page.wait_for_selector(f"{pane} table.series tr.row:has(b:text-is('KCN'))")
                check("M6 자료 작업대가 이어 받는다 — 새 시리즈는 '회차에 없음', '자료 만들기'를 권한다",
                      "회차에 없음" in page.inner_text(f"{pane} table.series tr.row:has(b:text-is('KCN'))") and page.locator(f"{pane} .banner.warn").count() == 1)

                print("S. 회차 바꾼 뒤 할 일 · 모형 작업대 · 흐름 화면 · 정의 고치기(D3)")
                page.click(f"{pane} .flow-card >> nth=2")
                page.click(f"{pane} .vint[data-vintage='{second}'] [data-act='use']")
                page.wait_for_selector(".dialog")
                page.click(".dialog .btn.primary")
                page.wait_for_selector(f"{pane} .todo .todo-row")
                todo = page.inner_text(f"{pane} .todo")
                page.click(f"{pane} [data-act='reest']")
                page.wait_for_selector(f"{pane} .reest-table tbody tr")
                check("S1 회차를 바꾸면 할 일이 뜬다 — 옛 자료로 추정한 채택 계수·옛 자료로 푼 과거 재현. '다시 추정해 견주기'는 기록만 남기고 옛·새를 나란히",
                      "채택한 식" in todo and "과거 재현" in todo and first in todo and page.locator(f"{pane} .reest-table tbody tr").count() == 5
                      and "→" in page.inner_text(f"{pane} .reest-table"), todo)
                had = f"{pane} .reest-table tbody tr:not(:has(.tag:has-text('채택 없음')))"
                page.check(f"{had} >> nth=0 >> input")
                page.click(f"{pane} [data-act='adopt-new']")
                page.wait_for_selector(".dialog .diff")
                dialog = page.inner_text(".dialog")
                shot(page, "03g-todo")
                page.click(".dialog .btn.primary")
                page.wait_for_selector(f"{pane} .reest", state="detached")
                check("S2 고른 식만 새 계수로 채택 — 채택표의 바뀔 줄을 보이고 나서",
                      '+ "demand:CN" = "est:' in dialog and "adopted.toml" in dialog and page.locator(f"{active} .notice[data-change]").count() == 0, dialog[:300])

                page.click(f"{active} .side .row-item[data-key='model:main']")
                page.wait_for_selector(f"{pane} .block-row.asm")
                check("S3 모형 작업대 — 조립: 블록과 식·블록 사이의 연결·풀이 순서·외생, 문제가 없으면 그렇게 말한다",
                      "조립에 문제가 없습니다" in page.inner_text(f"{pane} .banner.ok") and page.locator(f"{pane} .block-row.asm").count() == 3
                      and page.locator(f"{pane} .link-row").count() == 3 and page.locator(f"{pane} .solve.sim").count() == 1 and page.locator(f"{pane} .exo").count() == 3
                      and "core 에서" in page.inner_text(f"{pane} .block-row.asm >> nth=0"))
                shot(page, "03h-assembly")
                page.click(f"{pane} [data-act='new-model']")
                page.wait_for_selector(".dialog")
                page.fill(".dialog input[aria-label='모형 이름']", "dp")
                page.click(".dialog [data-pick='blocks:demand']")
                page.click(".dialog [data-pick='blocks:price']")
                page.click(".dialog .btn.primary")
                page.wait_for_selector(".dialog .diff")
                dialog = page.inner_text(".dialog")
                page.click(".dialog .btn.primary")
                page.wait_for_selector(f"{active} .tabbar .tab[aria-selected='true'] .title:has-text('dp')")
                page.wait_for_selector(f"{pane} .block-row.asm")
                check("S4 새 모형 — 블록을 고르고, equion.toml 에 적힐 줄과 명령을 본 뒤 저장하면 그 모형의 작업대가 열린다",
                      "+[model.dp]" in dialog and "equion model define dp --blocks demand,price" in dialog and page.locator(f"{pane} .block-row.asm").count() == 2
                      and page.locator(f"{active} .side .row-item[data-key='model:dp']").count() == 1
                      and "[model.dp]" in open(os.path.join(folder, "equion.toml"), encoding="utf-8").read(), dialog[:200])

                page.click(f"{active} .side .row-item[data-key='model:main']")
                page.click(f"{pane} .flow-card >> nth=1")
                page.wait_for_selector(f"{pane} [data-act='solve']")
                had_runs = page.locator(f"{pane} .runs tr[data-run-id]").count()
                page.click(f"{pane} [data-act='solve']")
                page.wait_for_function(f"document.querySelectorAll('.project:not([hidden]) .pane:not([hidden]) .runs tr[data-run-id]').length > {had_runs}", timeout=60000)
                page.wait_for_selector(f"{pane} .fit-table tr.row")
                check("S5 과거 재현 — 풀면 기록이 목록에 생기고, 기간마다의 풀이 상태와 변수마다의 오차가 보인다",
                      page.locator(f"{pane} .status-band .sq").count() >= 60 and page.locator(f"{pane} .fit-table tr.row").count() == 6
                      and "정상" in page.inner_text(f"{pane} .status-head") and page.inner_text(f"{pane} .an-form .cmdline .cmd") == "equion hs main")
                page.click(f"{pane} .fit-table tr[data-var='P']")
                page.wait_for_selector(f"{pane} .trace .trace-in")
                page.wait_for_selector(f"{pane} .var-detail .fit svg path >> nth=1")
                trace = page.inner_text(f"{pane} .trace")
                check("S6 변수를 누르면 실측과 해, 그리고 원인 따라가기 — 식의 입력마다 내생이면 이 풀이에서의 오차, 외생이면 실측",
                      "price:P" in trace and "POIL" in trace and "외생" in trace and page.locator(f"{pane} .trace-in.endo").count() == 1, trace[:300])
                page.wait_for_timeout(300)
                shot(page, "03i-hs")
                page.click(f"{pane} .trace-in.endo")               # 입력 Y 로 거슬러 올라간다
                page.wait_for_selector(f"{pane} .trace:has-text('demand:Y')")
                up = page.inner_text(f"{pane} .trace")
                page.click(f"{pane} .var-detail .raw-cap .link")   # 지나온 길로 돌아간다
                page.wait_for_selector(f"{pane} .trace:has-text('price:P')")
                check("S7 입력을 눌러 거슬러 올라가고, 지나온 길로 돌아온다", "항등식" in up and "CN" in up and "price:P" in page.inner_text(f"{pane} .trace"))
                had_runs = page.locator(f"{pane} .runs tr[data-run-id]").count()
                page.click(f"{pane} [data-act='block']")           # 블록 price 만 풀기 — 방금 보던 풀이와 견준다
                page.wait_for_selector(f"{pane} .fit-table th:has-text('달라짐')", timeout=60000)
                page.wait_for_selector(f"{pane} .runs tr.on:has-text('블록 price')", timeout=20000)
                check("S8 '이 블록만 풀기' — 나머지에 실측을 넣어 풀고 방금 보던 풀이와 전후를 견준다",
                      "블록 price" in page.inner_text(f"{pane} .run-view .result-head") and page.locator(f"{pane} .runs tr.vs").count() == 1
                      and page.locator(f"{pane} .fit-table tr.row").count() == 1 and "블록 price" in page.inner_text(f"{pane} .runs tr.on"),
                      page.inner_text(f"{pane} .run-view .result-head"))

                page.click(f"{pane} .flow-card >> nth=0")
                page.click(f"{pane} .block-row.asm:has(.bn:has-text('price')) .side-acts .btn")
                page.wait_for_selector(f"{pane} .edit-area")
                original = page.input_value(f"{pane} .edit-area")
                page.fill(f"{pane} .edit-area", original + "PX c P (\n")
                page.wait_for_selector(f"{pane} .edit-problems")
                problem = page.inner_text(f"{pane} .edit-problems")
                page.fill(f"{pane} .edit-area", original.rstrip("\n") + "\n# 화면에서 적은 메모\n")
                page.wait_for_selector(f"{pane} .edit-note .eq-status.ok")
                page.keyboard.press("Control+s")
                page.wait_for_selector(f"{pane} pre.code")
                check("S9 블록 파일을 화면에서 고친다 — 치는 동안 읽을 수 없는 줄을 알리고, Ctrl+S 로 저장하면 바뀜 기록에 남는다(알림 카드 없이)",
                      "괄호" in problem and "줄" in problem and "읽을 수 없는 곳 1" in problem, problem)
                check("S9-1 저장한 글이 파일에 있다", "# 화면에서 적은 메모" in open(os.path.join(folder, "EQUATIONS", "price.txt"), encoding="utf-8").read()
                      and page.locator(f"{active} .notice[data-change]").count() == 0 and "화면에서 적은 메모" in page.inner_text(f"{pane} pre.code"))

                page.click(f"{active} .side .row-item[data-key='flow:FLOWS/monthly.eqs']")
                page.wait_for_selector(f"{pane} .step-row")
                check("S10 흐름 화면 — 스크립트가 단계 줄로(묶음 제목·무엇을 바꾸는지). 여는 것만으로는 실행하지 않는다",
                      page.locator(f"{pane} .step-row").count() == 11 and page.locator(f"{pane} .step-sect").count() >= 4 and page.locator(f"{pane} .step-row .tag.warn").count() >= 3
                      and page.locator(f"{pane} .step-row .mark.ok").count() == 0 and "equion run FLOWS/monthly.eqs" == page.inner_text(f"{pane} .flow-form .cmdline .cmd"))
                page.click(f"{pane} [data-act='run']")
                page.wait_for_selector(f"{pane} .banner:has-text('run:monthly_0001')", timeout=120000)
                check("S11 실행 — 단계마다 끝난 모양과 남긴 기록. 이 화면에서 시킨 스크립트가 고친 것은 알림 카드를 쌓지 않는다",
                      page.locator(f"{pane} .step-row .mark.ok").count() >= 9 and page.locator(f"{pane} .step-row .mark.bad").count() == 0
                      and page.locator(f"{pane} .step-row .what .link").count() >= 5 and page.locator(f"{active} .notice[data-change]").count() == 0
                      and "run:monthly_0001" in page.inner_text("#job"), page.inner_text(f"{pane} .banner")[:200])
                page.wait_for_timeout(300)
                shot(page, "03j-flow")

                print("T. 전망 작업대 · 보고서(D4)")
                n_jobs = page.locator("#job .job").count()
                page.click(f"{active} .side .row-item[data-key='forecast']")
                page.wait_for_selector(f"{pane} .fc-table tbody tr")
                sims = page.locator(f"{pane} tr[data-sim]").count()
                check("T1 전망 작업대 — 푼 전망이 있으면 가정 표는 접고(한 줄 요약) 결과를 먼저 보인다. 여는 것만으로는 풀지 않는다",
                      sims >= 2 and page.locator(f"{pane} .asm-box.shut .asm-sum .pc-flat").count() == 3 and page.locator(f"{pane} .asm-grid").count() == 0
                      and page.inner_text(f"{pane} .an-form .cmdline .cmd") == "equion sim base --model main" and page.locator(f"{pane} .fc-legend .key").count() == 4
                      and page.locator(f"{pane} .fc-table td.f-sol").count() >= 8 and page.locator("#job .job").count() == n_jobs, page.inner_text(f"{pane} .asm-box"))
                page.click(f"{pane} [data-act='fold-assume']")
                page.wait_for_selector(f"{pane} .asm-grid .cell")
                cells = page.locator(f"{pane} .asm-grid .cell")
                n_cells = cells.count()
                cells.nth(8).fill("3.3")                       # 셋째 기간의 R — 첫째·둘째 기간은 비어 있다: 값 사이의 빈칸
                gap = page.locator(f"{pane} .asm-grid .cell.gap").count()
                said = page.inner_text(f"{pane} .asm-note.bad")
                cells.nth(2).fill("3.1")
                cells.nth(5).fill("3.2")
                check("T2 가정 표 — 외생 × 전망 구간의 칸에 적는다. 값 사이의 빈칸은 붉게 알리고(채우기는 마지막 값 뒤만), 적으면 '저장' 이 살아난다",
                      n_cells == 24 and gap == 2 and "값 사이의 빈칸" in said and page.locator(f"{pane} .asm-grid .cell.gap").count() == 0
                      and page.locator(f"{pane} .asm-grid .cell.typed").count() >= 3 and page.is_enabled(f"{pane} [data-act='save-assume']")
                      and page.is_visible(f"{pane} .asm-note:not(.bad)"), said)
                page.wait_for_timeout(250)
                shot(page, "03k-assume")
                page.click(f"{pane} [data-scenario='oil20']")
                cmd = page.inner_text(f"{pane} .an-form .cmdline .cmd")
                page.click(f"{pane} [data-act='solve']")
                page.wait_for_selector(f"{pane} .asm-box.shut", timeout=90000)
                page.wait_for_selector(f"{pane} tr[data-sim].vs", timeout=30000)       # 풀이가 끝난 뒤 새 기록을 읽어 견주기까지 — 가정 표가 접힌 것보다 조금 늦다
                page.wait_for_selector(f"{pane} [data-mode='diff']", timeout=30000)
                page.wait_for_selector("#job .job.done:has-text('sim:')", timeout=30000)        # 작업 줄의 '끝남'은 응답보다 조금 늦게 온다
                with open(os.path.join(folder, "ASSUMPTIONS", "base.csv"), encoding="utf-8") as f:
                    saved = f.read()
                check("T3 풀기 — 저장하지 않은 가정을 먼저 저장하고 기준선과 시나리오를 차례로(작업 하나). 함께 푼 것은 나란히 견주게 고른다",
                      cmd == "equion sim base oil20 --model main" and ",3.1" in saved and ",3.3" in saved and page.locator(f"{pane} tr[data-sim]").count() >= min(6, sims + 2)
                      and "oil20" in page.inner_text(f"{pane} tr[data-sim].on") and page.locator(f"{pane} tr[data-sim].vs").count() == 1
                      and "시나리오 oil20" in page.inner_text(f"{pane} .fc-result .result-head") and "sim:" in page.inner_text("#job .job.done"), cmd)
                page.click(f"{pane} [data-series='R']")
                asm = page.locator(f"{pane} .fc-table td.f-asm").count()
                fill = page.locator(f"{pane} .fc-table td.f-fill").count()
                page.click(f"{pane} [data-mode='annual']")
                head = page.locator(f"{pane} .fc-table thead th").all_inner_texts()
                page.click(f"{pane} [data-mode='diff']")
                page.wait_for_selector(f"{pane} .fc-table td .sub")
                diff_rows = page.locator(f"{pane} .fc-table tbody tr").count()
                page.click(f"{pane} [data-mode='level']")
                page.click(f"{pane} [data-col='P']")
                page.wait_for_selector(f"{pane} .var-detail svg path")
                check("T4 결과 — 값의 종류를 칸의 색으로(가정·채움·해), 연간은 고른 전망을 나란히, 기준선 대비, 열 이름을 누르면 실측에 이은 전망 차트(견주는 것과 함께)",
                      asm == 3 and fill == 5 and len(head) == 4 and "oil20" in head[2] and "base" in head[3] and diff_rows == 8
                      and page.locator(f"{pane} .var-detail .legend .key").count() == 3, f"{asm} {fill} {head}")
                page.wait_for_timeout(300)
                shot(page, "03l-forecast")
                page.click(f"{pane} [data-act='views']")
                page.click(".menu .menu-item:has-text('이 보기 저장')")
                page.wait_for_selector(".dialog")
                page.fill(".dialog input[aria-label='보기 이름']", "core")
                page.fill(".dialog input[aria-label='제목']", "핵심 지표")
                page.click(".dialog-foot .btn.primary")
                page.wait_for_selector("#flash:has-text('VIEWS/core.toml')")
                page.wait_for_timeout(700)
                page.click(f"{pane} [data-series='M2']")
                page.click(f"{pane} [data-act='views']")
                page.click(".menu .menu-item:has-text('핵심 지표')")
                page.wait_for_timeout(200)
                check("T5 보기 — 지금 고른 시리즈와 모양을 이름으로 저장하고(VIEWS/core.toml), 다시 고르면 같은 표로 돌아온다",
                      os.path.isfile(os.path.join(folder, "VIEWS", "core.toml")) and page.get_attribute(f"{pane} [data-series='M2']", "aria-pressed") == "true"
                      and page.get_attribute(f"{pane} [data-mode='level']", "aria-pressed") == "true" and page.locator(f"{active} .notice[data-change]").count() == 0)
                page.click(f"{pane} [data-act='to-report']")
                page.wait_for_selector(".dialog select[aria-label='보고서']")
                dialog = page.inner_text(".dialog")
                places = page.locator(".dialog select[aria-label='보낼 곳'] option").count()
                page.fill(".dialog input[aria-label='표 제목']", "유가 시나리오")
                page.click(".dialog-foot .btn.primary")
                page.wait_for_selector(f"{pane} .region-row >> nth=2", timeout=30000)
                rows = page.locator(f"{pane} .region-row").count()
                check("T6 보고서로 — 지금 보는 시리즈·모양 그대로 보고서의 한 구역으로. 보낸 뒤 보고서 탭이 열리고 구역 검사가 더 새 기록이 있는 구역을 알린다",
                      "보고서의 한 구역으로" in dialog and places >= 2 and rows == 3 and "보고서" in page.inner_text(f"{active} .tabbar .tab[aria-selected='true']")
                      and "유가 시나리오" in page.inner_text(f"{pane} .report-doc") and page.locator(f"{pane} .region-row:has(.tag.warn)").count() == 1
                      and page.locator(f"{pane} .region-row:has(.tag.ok)").count() == 2 and page.locator(f"{pane} [data-act='update']").count() == 1, page.inner_text(f"{pane} .region-box"))
                page.wait_for_timeout(250)
                shot(page, "03m-report")
                page.click(f"{pane} [data-act='update']")
                page.wait_for_selector(".dialog .region-plan .diff")
                plan = page.inner_text(".dialog")
                page.click(".dialog-foot .btn.primary")
                page.wait_for_selector(f"{pane} .region-row .tag.ok >> nth=2", timeout=30000)
                check("T7 새 기록으로 바꾸기 — 구역마다 무엇이 달라지는지 먼저 보이고, 바꾸면 그 구역만 새 기록으로(모두 정상)",
                      "equion report update" in plan and "구역 1개 바꾸기" in plan and page.locator(f"{pane} .region-row .tag.warn").count() == 0
                      and page.locator(f"{pane} [data-act='update']").count() == 0 and page.locator(f"{active} .notice[data-change]").count() == 0, plan[:300])
                page.click(f"{active} .tabbar .tab:has-text('전망')")
                page.click(f"{pane} [data-act='to-xlsx']")
                page.wait_for_selector(".dialog input[aria-label='파일 이름']")
                page.fill(".dialog input[aria-label='파일 이름']", "ui_check")
                page.click(".dialog-foot .btn.primary")
                page.wait_for_selector(f"{active} .notice:has-text('exports/ui_check.xlsx')", timeout=30000)
                check("T8 엑셀로 — 보는 전망과 견주는 전망을 한 권으로(값·값의 종류·출처), 같은 일을 하는 명령과 함께 알린다",
                      os.path.getsize(os.path.join(folder, "exports", "ui_check.xlsx")) > 2000 and "equion export sim:" in page.inner_text(f"{active} .notice:has-text('exports/ui_check.xlsx')"))
                page.click(f"{active} .notice:has-text('exports/ui_check.xlsx') .icon-btn")
                page.click(f"{pane} .fc-result .result-head .rid")
                page.wait_for_selector(f"{pane} .of-record")
                check("T9 전망 기록의 카드 — '전망 작업대에서'·'보고서로'·'엑셀로' 가 있다",
                      page.locator(f"{pane} .view-head .tools .btn:has-text('전망 작업대에서')").count() == 1 and page.locator(f"{pane} [data-act='to-report']").count() == 1
                      and page.locator(f"{pane} [data-act='to-xlsx']").count() == 1)

                print("R. 제안 · 되돌리기 · 고정과 메모 · Claude ▾ · 도움말(D5)")
                claude_env = {**env, "EQUION_WHO": "claude"}
                price = os.path.join(folder, "EQUATIONS", "price.txt")
                made = equion(folder, claude_env, "propose", "new", "--title", "물가식에 시차 하나 더", "--why", "P(-2)를 넣어 본다 — 화면 점검", "--part", "price:P=P c Y POIL P(-1) P(-2)")
                page.wait_for_selector(f"{active} .notice[data-key='prop:p1']", timeout=20000)
                note = page.inner_text(f"{active} .notice[data-key='prop:p1']")
                page.wait_for_selector(f"{active} .side .row-item[data-key='proposals'] .dot.prop", timeout=10000)
                dot = page.locator(f"{active} .side .row-item[data-key='proposals'] .dot.prop").count()
                page.click(f"{active} .notice[data-key='prop:p1'] .btn.primary")
                page.wait_for_selector(f"{pane} .split-view.proposals .diff .dl.add")
                check("R1 Claude 가 제안을 남기면 알림 카드와 사이드바의 점 — '제안 보기'가 제안 카드를 연다(바뀔 내용의 차이·까닭). 아직 아무것도 바뀌지 않았다",
                      made.returncode == 0 and "Claude 제안 p1" in note and "물가식에 시차 하나 더" in note and dot == 1
                      and "+P c Y POIL P(-1) P(-2)" in page.inner_text(f"{pane} .diff") and "화면 점검" in page.inner_text(f"{pane} .prop-why")
                      and page.locator(f"{active} .side .row-item[data-key='proposals'] .dot.prop").count() == 0
                      and page.locator(f"{active} .notice[data-key='prop:p1']").count() == 0 and "P(-2)" not in open(price, encoding="utf-8").read(), note + made.stderr[-200:])
                page.wait_for_timeout(250)
                shot(page, "03n-proposal")
                page.click(f"{pane} [data-act='apply']")
                page.wait_for_selector(".dialog .cmd-note")
                said = page.inner_text(".dialog")
                page.click(".dialog-foot .btn.primary")
                page.wait_for_selector(f"{pane} .split-view.proposals .banner.info .btn", timeout=30000)
                check("R2 적용 — 바꿀 파일과 같은 일을 하는 명령을 보이고 나서 쓴다. 제안은 '적용함'이 되고 바뀜 기록으로 가는 단추가 생긴다(알림 카드 없이)",
                      "equion propose apply p1" in said and "EQUATIONS/price.txt" in said and "적용함" in page.inner_text(f"{pane} .detail .view-head")
                      and "P c Y POIL P(-1) P(-2)" in open(price, encoding="utf-8").read() and page.locator(f"{active} .notice[data-change]").count() == 0
                      and page.locator(f"{pane} [data-act='apply']").count() == 0, said)
                page.click(f"{pane} .split-view.proposals .banner.info .btn")
                page.wait_for_selector(f"{pane} [data-act='revert']")
                page.click(f"{pane} [data-act='revert']")
                page.wait_for_selector(".dialog .cmd-note")
                said = page.inner_text(".dialog")
                page.click(".dialog-foot .btn.primary")
                page.wait_for_selector(f"{pane} .detail .view-head .sub:has-text('되돌림')", timeout=30000)
                check("R3 되돌리기 — 무엇이 돌아가는지와 명령을 보이고 나서. 파일은 앞 내용으로 돌아가고, 되돌린 것도 바뀜 기록에 새 줄로 남는다",
                      "equion history revert h" in said and "앞 내용으로" in said and "P(-2)" not in open(price, encoding="utf-8").read()
                      and "Desk" in page.inner_text(f"{pane} .detail .view-head") and page.locator(f"{active} .notice[data-change]").count() == 0, said)
                page.wait_for_timeout(250)
                shot(page, "03o-revert")
                page.click("#btn-records")
                page.wait_for_selector(f"{pane} .rec-row")
                page.click(f"{pane} .rec-row:has(.kind:has-text('전망')) >> nth=0")
                page.wait_for_selector(f"{pane} [data-act='pin']")
                page.click(f"{pane} [data-act='pin']")
                page.wait_for_selector(f"{pane} [data-act='pin'][aria-pressed='true']")
                page.fill(f"{pane} .memo-line input", "보고서에 쓴 전망")
                page.keyboard.press("Enter")
                page.click(f"{active} .tabbar .tab:has-text('작업 기록')")
                page.wait_for_selector(f"{pane} .rec-row .memo", timeout=15000)
                page.click(f"{pane} .filters [data-filter='pinned']")
                check("R4 고정과 메모 — 결과 카드에서 고정하고 메모를 적으면 작업 기록 목록에 보이고 '고정'으로 가려 본다",
                      page.locator(f"{pane} .rec-row").count() == 1 and page.locator(f"{pane} .rec-row .pinmark").count() == 1
                      and "보고서에 쓴 전망" in page.inner_text(f"{pane} .rec-row"), page.inner_text(f"{pane} .rec-list")[:200])
                page.click(f"{active} .side .row-item[data-key='bench:demand:CN']")
                page.wait_for_selector(f"{pane} [data-act='claude']")
                page.click(f"{pane} [data-act='claude']")
                page.wait_for_selector(".menu .menu-item")
                menu = page.inner_text(".menu")
                page.wait_for_timeout(200)
                shot(page, "03p-claude")
                page.keyboard.press("Escape")
                check("R5 Claude ▾ — 맡기기 · 제안 받기 · 이름만 보내기 · Equion 알려 주기(요청 글을 터미널에 붙인다 — Enter 는 직접)",
                      all(x in menu for x in ("맡기기", "제안 받기", "이름만 보내기", "Equion 알려 주기", "demand:CN")) and page.locator(".menu").count() == 0, menu)
                shown = equion(folder, claude_env, "desk", "show", "model:main")
                page.wait_for_selector(f"{active} .tabbar .tab[aria-selected='true']:has-text('main')", timeout=20000)
                page.wait_for_selector(f"{pane} .flow-card")
                check("R6 equion desk show — Claude 가 치면 그 화면이 앞으로 온다(화면 이동만)", shown.returncode == 0 and page.locator(f"{pane} .flow-card").count() == 3, shown.stderr[-200:])
                page.keyboard.press("F1")
                page.wait_for_selector(f"{pane} .view.help h1")
                check("R7 F1 — 도움말 탭(화면 · 핵심 고리 · 되돌리기 · Claude 와 함께 · 같은 일을 하는 명령 · 손버릇)",
                      "Equion Desk 도움말" in page.inner_text(f"{pane} .view.help h1") and page.locator(f"{pane} .view.help table").count() >= 3
                      and "도움말" in page.inner_text(f"{active} .tabbar .tab[aria-selected='true']"))
                page.wait_for_timeout(200)
                shot(page, "03q-help")
                page.click(f"{active} .tabbar .tab[aria-selected='true'] .x")

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
                    ok = "hs_000" in text and "터미널" in text and "unseen" in (chip.get_attribute("class") or "")
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
                page.click(f"{pane} .card >> nth=1 >> .foot .btn:has-text('전망')")        # 모형 main 의 '전망' — 전망 작업대를 연다
                page.wait_for_selector(f"{pane} [data-act='solve']")
                page.click(f"{pane} [data-scenario='oil20']")                                   # 기준선만
                page.click(f"{pane} [data-act='solve']")
                page.wait_for_selector("#job .job")
                page.wait_for_selector("#job .job.done:has-text('sim:')", timeout=60000)
                page.wait_for_selector(f"{pane} tr[data-sim].on:has-text('_base')", timeout=30000)
                check("X1 개요의 '전망' 단추는 전망 작업대를 열고, '풀기' — 작업 줄에 도는 일과 끝난 일(기록 이름), 푼 전망이 목록 맨 위에 보인다",
                      "sim:" in page.inner_text("#job .job.done") and "전망" in page.inner_text(f"{active} .tabbar .tab[aria-selected='true']")
                      and "_base" in page.inner_text(f"{pane} tr[data-sim].on"))
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
                chips = page.locator("#strip .chip").count()
                shown = page.inner_text(f"{pane} .result-head .rid")
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
                check("Y2 식 작업대는 보던 기록과 표준오차 고른 것을 다시 보인다(다시 계산하지 않는다)",
                      page.locator("#strip .chip").count() == chips and page.inner_text(f"{pane} .result-head .rid") == shown
                      and page.input_value(f"{pane} .eq-opts select") == "hac")
                check("Y3 사이드바의 고른 탭(파일)도 그대로", page.locator(f"{active} .side-tabs [data-side='files']").get_attribute("aria-selected") == "true")
                check("Y4 어두운 바탕 — 운영체제 설정을 따른다", page.evaluate("document.documentElement.dataset.theme") == "dark")
                shot(page, "07-dark")
                page.click(f"{active} .side-tabs [data-side='parts']")
                page.click(f"{active} .side .row-item[data-key='data']")
                page.wait_for_selector(f"{pane} .flow-card")
                kept = page.get_attribute(f"{pane} .flow-card >> nth=2", "aria-pressed")       # 지난번 보던 칸(회차)으로 열린다
                page.click(f"{pane} .flow-card >> nth=1")
                page.wait_for_selector(f"{pane} table.series tr.row")
                page.wait_for_timeout(300)
                shot(page, "08-data-dark")
                page.click(f"{active} .side .row-item[data-key='analysis']")
                page.wait_for_selector(f"{pane} .an-form")
                check("Y6 자료 작업대와 분석 탭도 이어진다 — 보던 분석 기록과 폼이 그대로",
                      kept == "true" and page.input_value(f"{pane} .an-target") == "CN" and page.locator(f"{pane} .an-out .result-head .rid").count() == 1)
                page.wait_for_timeout(300)
                shot(page, "09-analysis-dark")
                page.click(f"{active} .side-tabs [data-side='files']")
                page.click("#btn-settings")
                page.click(".popover .segmented button >> nth=1")
                check("Y5 설정에서 바탕을 바꾸면 바로 바뀐다", page.evaluate("document.documentElement.dataset.theme") == "light")
                page.close()
            finally:
                server.terminate()
                server.wait(10)
            browser.close()
        check("Z1 화면 오류가 없다(스크립트 오류·콘솔 오류)", not errors, " | ".join(errors[:5]))
        check("Z2 화면에 값 대신 'null'·'undefined'·'NaN' 이 찍힌 곳이 없다", not leaks, " | ".join(leaks[:6]))
    bad = [n for n, ok, _ in RESULTS if not ok]
    print(f"\nEquion Desk 화면 점검 {len(RESULTS) - len(bad)}/{len(RESULTS)}")
    return len(bad)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Equion Desk 화면 점검")
    ap.add_argument("--shots", metavar="폴더", help="화면 그림을 남길 폴더")
    sys.exit(1 if run(ap.parse_args().shots) else 0)
