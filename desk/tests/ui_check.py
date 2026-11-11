"""Equion Desk 화면 점검 — 진짜 브라우저(Edge)로 화면을 몰아 D1·D2a·D2b-1 의 완료 기준을 확인한다.

    uv run --package equion-desk --group ui python desk/tests/ui_check.py            # 점검만
    uv run --package equion-desk --group ui python desk/tests/ui_check.py --shots 폴더   # 화면 그림도 남긴다(밝은·어두운 바탕)

서버를 브라우저 모드로 띄우고(`python -m equion_desk --browser`) PC에 있는 Edge 를 창 없이 몬다 — 브라우저를 따로 받지 않는다
(Edge 가 없으면 playwright 의 chromium 을 찾는다: `python -m playwright install chromium`). 설정 파일과 예제 프로젝트는 임시 폴더에 둔다.

확인하는 것: 첫 화면 → 프로젝트 열기 → 부품을 눌러도 계산하지 않는다 → 추정이 1초 안에 화면에(S1) → 식 작업대(치는 동안의 검사 ·
후보 목록 · 겹쳐 보기 · 기간 짚기 · **채택** · **이 후보로 과거 재현** · 항등식 검사 — D2a) → 자료 작업대(받은 상자 → **자료 만들기 → 견주기 →
이 회차로 바꾸기**)와 분석 탭(등록부의 폼 · 명령 줄 · **미리보기 → 정의로 남기기** — D2b-1) → **터미널에서 친 명령의 기록이
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
                page.wait_for_selector(f"{pane} table.series tr.row")
                page.wait_for_timeout(300)
                shot(page, "08-data-dark")
                page.click(f"{active} .side .row-item[data-key='analysis']")
                page.wait_for_selector(f"{pane} .an-form")
                check("Y6 자료 작업대와 분석 탭도 이어진다 — 보던 분석 기록과 폼이 그대로",
                      page.input_value(f"{pane} .an-target") == "CN" and page.locator(f"{pane} .an-out .result-head .rid").count() == 1)
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
