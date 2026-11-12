"""Equion Desk 따라하기(docs/desk/)의 화면 그림을 만든다 — 예제 프로젝트로 설명서의 순서를 그대로 밟으며 찍는다.

    uv run --package equion-desk --group ui python desk/tests/guide_shots.py [--out docs/desk/img]

화면을 고치면 다시 돌려 그림을 새로 만든다(그림은 손으로 고치지 않는다 — 문서 출력과 같은 원칙). ui_check.py 와 같이 PC 의 Edge 를 몬다.
설명서의 PowerShell 줄(받은 원자료 · 새 통계표)은 그대로 터미널에 쳐서 돌린다 — 적힌 대로 따라 하면 되는지도 이것으로 확인한다.
이 PC 의 경로는 그림에 나오지 않게 '사용자'로 가린다. 설정·예제는 임시 폴더에 만든다(사용자 설정과 문서 폴더는 건드리지 않는다).
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
import time
import urllib.request

PORT = 8823
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SHOWN_BASE = r"C:\Users\user\Documents"               # 그림에 보이는 문서 폴더(이 PC 의 경로를 가린다)
W, H = 1600, 900

# 설명서(docs/desk/02-data.md)에 적힌 명령 — 바꾸면 설명서도 같이 바꾼다
INBOX_CMD = ("Copy-Item DATA\\raw\\toy_q.csv DATA\\raw\\inbox\\toy_q_2020Q1.csv; "
             "Add-Content DATA\\raw\\inbox\\toy_q_2020Q1.csv '2020Q1,466.4,95.7,69.8,632.0,3.19,4.74,192.4,62.5,3916.2,457.0'")
KR_ROWS = [("2017년 1/4분기", "1,201.5", "88.2"), ("2017년 2/4분기", "1,215.8", "90.1"), ("2017년 3/4분기", "1,228.0", "91.4"),
           ("2017년 4/4분기", "1,240.3", "92.0"), ("2018년 1/4분기", "1,251.9", "93.7"), ("2018년 2/4분기", "1,263.4", "-"),
           ("2018년 3/4분기", "1,277.6", "95.9"), ("2018년 4/4분기", "1,289.2", "96.4"), ("2019년 1/4분기", "1,298.5", "97.8"),
           ("2019년 2/4분기", "1,310.7", "98.3"), ("2019년 3/4분기", "1,322.4", "99.6"), ("2019년 4/4분기", "1,335.0", "100.2")]
KR_CMD = ("Set-Content DATA\\raw\\kr.csv -Encoding UTF8 -Value '표 1. 지출 항목별 국내총생산(가상)','시점,민간소비,설비투자',',십억원,십억원',"
          + ",".join(f"'{a},\"{b}\",{c}'" for a, b, c in KR_ROWS))

FAILED: list[str] = []


def log(msg: str) -> None:
    print(msg, flush=True)


def start_server(env: dict[str, str]) -> subprocess.Popen:
    server = subprocess.Popen([sys.executable, "-m", "equion_desk", "--browser", "--port", str(PORT)], env=env,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(150):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/state", timeout=1).read()
            return server
        except OSError:
            time.sleep(0.1)
    server.kill()
    raise RuntimeError("서버가 뜨지 않았습니다")


def run(out: str) -> int:
    from playwright.sync_api import sync_playwright

    # 설명서에 적힌 줄과 여기서 치는 줄이 같아야 한다 — 그래야 그림이 '적힌 대로 따라 하면 된다'는 확인이 된다
    with open(os.path.join(ROOT, "docs", "desk", "02-data.md"), encoding="utf-8") as f:
        guide = f.read()
    for cmd in (INBOX_CMD, KR_CMD):
        if cmd not in guide:
            FAILED.append(f"docs/desk/02-data.md 에 이 줄이 없습니다(스크립트와 설명서가 다름): {cmd[:60]}…")
    os.makedirs(out, exist_ok=True)
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        docs = os.path.join(tmp, "Documents")
        env = dict(os.environ, PYTHONIOENCODING="utf-8", EQUION_DESK_CONFIG_DIR=os.path.join(tmp, "cfg"), EQUION_DESK_DOCUMENTS=docs)
        for key in ("CLAUDECODE", "EQUION_WHO"):
            env.pop(key, None)
        folder = os.path.join(docs, "Equion", "example1")
        hide = [(docs, SHOWN_BASE), (docs.replace("\\", "/"), SHOWN_BASE.replace("\\", "/"))]
        server = start_server(env)
        active = ".project:not([hidden])"
        pane = f"{active} .pane:not([hidden])"
        try:
            with sync_playwright() as pw:
                try:
                    browser = pw.chromium.launch(channel="msedge", headless=True)
                except Exception:
                    browser = pw.chromium.launch(headless=True)
                page = browser.new_page(viewport={"width": W, "height": H}, color_scheme="light")
                errors: list[str] = []
                page.on("pageerror", lambda e: errors.append(str(e)))
                page.goto(f"http://127.0.0.1:{PORT}/")

                def mask() -> None:
                    page.evaluate("""(pairs) => {
                        const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
                        let n;
                        while ((n = walk.nextNode())) for (const [a, b] of pairs) if (n.nodeValue.includes(a)) n.nodeValue = n.nodeValue.split(a).join(b);
                        for (const el of document.querySelectorAll('input, textarea')) for (const [a, b] of pairs) if (el.value && el.value.includes(a)) el.value = el.value.split(a).join(b);
                    }""", hide)

                def shot(name: str, target: str | None = None, pad: int = 0) -> None:
                    page.wait_for_timeout(350)
                    mask()
                    path = os.path.join(out, f"{name}.png")
                    if target:
                        box = page.locator(target).first.bounding_box()
                        clip = {"x": max(0, box["x"] - pad), "y": max(0, box["y"] - pad),
                                "width": min(W, box["width"] + 2 * pad), "height": min(H, box["height"] + 2 * pad)}
                        page.screenshot(path=path, clip=clip)
                    else:
                        page.screenshot(path=path)
                    log(f"  · {name}.png")

                def step(title: str, fn) -> None:
                    log(title)
                    try:
                        fn()
                    except Exception as e:  # 한 단계가 실패해도 나머지는 찍는다
                        FAILED.append(f"{title}: {str(e).splitlines()[0][:200]}")
                        log(f"  ✗ {FAILED[-1]}")
                        try:
                            page.screenshot(path=os.path.join(out, f"_fail-{len(FAILED)}.png"))
                            page.keyboard.press("Escape")
                        except Exception:
                            pass

                def term_type(text: str) -> None:
                    """1번 터미널에 붙이고 Enter — 설명서에서 사람이 치는 것과 같다."""
                    page.evaluate("(t) => window.equionDesk.current.term.paste(t)", text)
                    page.wait_for_timeout(500)
                    page.click(f"{active} .term-body")
                    page.keyboard.press("Enter")

                def set_term(visible: bool) -> None:
                    if page.evaluate("() => window.equionDesk.settings.term_visible") != visible:
                        page.click("#btn-term")
                        page.wait_for_timeout(300)

                # ---- 1. 처음 열기 ---------------------------------------------------------------------------------
                def s_start():
                    page.wait_for_selector("#welcome .welcome-card")
                    shot("start-welcome")
                    page.click("#welcome .btn:has-text('예제 프로젝트 만들기')")
                    page.wait_for_selector(f"{active} .side-tabs", timeout=60000)
                    page.wait_for_selector("#status .dot.ok", timeout=60000)
                    page.wait_for_selector(f"{active} .term-body .xterm", timeout=30000)
                    page.wait_for_timeout(2500)
                    term_type(f"function prompt {{ 'PS {SHOWN_BASE}\\Equion\\example1> ' }}; Clear-Host")
                    page.wait_for_timeout(1500)
                    page.click(f"{active} .side-tabs [data-side='models']")
                    page.wait_for_selector(f"{active} .side .row-item[data-key='bench:demand:CN']")
                    shot("start-home")
                    page.click("#btn-settings")
                    page.wait_for_selector(".popover")
                    shot("start-settings", ".popover", 8)
                    page.keyboard.press("Escape")
                    if page.locator(".popover").count():
                        page.click("#btn-settings")
                step("1. 처음 열기", s_start)

                # ---- 2. 자료 --------------------------------------------------------------------------------------
                def s_data():
                    set_term(False)
                    page.click(f"{active} .side .wb[data-key='data']")
                    page.wait_for_selector(f"{pane} table.series tr.row")
                    shot("data-workbench")
                    page.click(f"{pane} table.series tr.row:has(b:text-is('CNSA'))")
                    page.wait_for_selector(f"{pane} .series-detail .fit svg")
                    shot("data-series")
                    page.click(f"{pane} table.series tr.row.open")
                    set_term(True)
                    term_type(INBOX_CMD)
                    page.wait_for_selector(f"{pane} .banner:has-text('받은 상자')", timeout=30000)
                    shot("data-inbox")
                    page.click(f"{pane} .banner .btn")
                    page.wait_for_selector(f"{pane} .inbox-item")
                    shot("data-inbox-item", f"{pane}", 0)
                    page.click(f"{pane} .inbox-item .btn.primary")
                    page.wait_for_selector(f"{pane} .banner.warn")
                    page.click(f"{pane} .banner.warn .btn")              # 자료 만들기
                    page.wait_for_selector(f"{pane} .diffbox table", timeout=60000)
                    page.wait_for_function("() => (document.querySelector('.project:not([hidden]) .pane:not([hidden]) .diffbox')?.innerText || '').includes('demand:')", timeout=20000)
                    set_term(False)
                    shot("data-vintages")
                    page.click(f"{pane} .vint:not(.now) [data-act='use']")
                    page.wait_for_selector(".dialog")
                    shot("data-use", ".dialog", 8)
                    page.click(".dialog .btn.primary")
                    page.wait_for_selector(f"{pane} .vint.now:not([data-vintage$='a'])", timeout=20000)
                step("2. 자료 — 받은 원자료 · 자료 만들기 · 회차 바꾸기", s_data)

                def s_import():
                    set_term(True)
                    term_type(KR_CMD)
                    page.click(f"{pane} .flow-card >> nth=0")
                    page.wait_for_selector(f"{pane} .unused-item:has-text('kr.csv')", timeout=30000)
                    page.click(f"{pane} .unused-item:has-text('kr.csv') .link")
                    page.wait_for_selector(f"{pane} .raw-grid")
                    page.wait_for_selector(f"{pane} [data-hint]")
                    set_term(False)
                    shot("import-raw")
                    for _ in range(6):
                        if not page.locator(f"{pane} [data-hint]").count():
                            break
                        page.click(f"{pane} [data-hint] >> nth=0")
                        page.wait_for_timeout(900)
                    page.wait_for_selector(f"{pane} .banner.ok")
                    kcn = f"{pane} .pick[data-column='민간소비']"
                    ki = f"{pane} .pick[data-column='설비투자']"
                    page.click(f"{kcn} input[type=checkbox]")
                    page.fill(f"{kcn} [data-key='name']", "KCN")
                    page.click(f"{ki} input[type=checkbox]")
                    page.fill(f"{ki} [data-key='name']", "KI")
                    page.select_option(f"{ki} [data-key='fill']", "linear")
                    page.click(f"{ki} [data-act='try']")
                    page.wait_for_selector(f"{pane} .try-chart .fit svg", timeout=20000)
                    shot("import-picks")
                    page.click(f"{pane} [data-act='store']")
                    page.wait_for_selector(".dialog .diff")
                    shot("import-save", ".dialog", 8)
                    page.click(".dialog .btn.primary")
                    page.wait_for_selector(f"{pane} .banner.ok:has-text('정의에 저장했습니다')", timeout=20000)
                step("2-1. 불러오기 — 새 통계표", s_import)

                # ---- 3. 변수와 분석 -----------------------------------------------------------------------------------
                def s_vars():
                    set_term(True)
                    page.click(f"{active} .side-tabs [data-side='vars']")
                    page.wait_for_selector(f"{active} .var-row[data-var='CN']")
                    page.click(f"{active} .var-row[data-var='Y']")
                    page.click(f"{active} .var-row[data-var='CN']", modifiers=["Control"])
                    page.click(f"{active} .var-row[data-var='I']", modifiers=["Control"])
                    page.click(f"{active} [data-act='var-menu']")
                    page.wait_for_selector(".var-menu")
                    shot("vars-menu")
                    page.click(".var-menu [data-act='an-corr']")
                    page.wait_for_selector(f"{pane} .an-out .of-record", timeout=30000)
                    set_term(False)
                    shot("vars-corr")
                    page.dblclick(f"{active} .var-row[data-var='CN']")
                    page.wait_for_selector(f"{pane} .var-view .var-chart svg", timeout=20000)
                    shot("vars-window")
                    page.click(f"{active} .side .wb[data-key='analysis']")
                    page.wait_for_selector(f"{pane} .an-form, {pane} .an-row")
                    if not page.locator(f"{pane} .an-row").count():
                        page.click(f"{pane} .btn:has-text('분석 모두 보기')")
                    page.wait_for_selector(f"{pane} .an-row")
                    page.click(f"{pane} .an-row[data-analysis='unitroot']")
                    page.click(f"{pane} .pick-row .pc:text-is('core')")
                    page.select_option(f"{pane} [data-opt='trend']", "ct")
                    page.keyboard.press("Control+Enter")
                    page.wait_for_selector(f"{pane} .an-out .doc h2", timeout=30000)
                    shot("analysis-unitroot")
                step("3. 변수와 분석", s_vars)

                # ---- 4. 식 고르기 --------------------------------------------------------------------------------------
                def s_bench():
                    set_term(False)
                    page.click(f"{active} .side-tabs [data-side='models']")
                    page.click(f"{active} .side .row-item[data-key='bench:demand:CN']")
                    page.wait_for_selector(f"{pane} .eq-box textarea")
                    page.click(f"{pane} .eq-box textarea")
                    page.keyboard.press("Control+Enter")
                    page.wait_for_selector(f"{pane} .fit svg path >> nth=2", timeout=30000)
                    shot("bench-estimate")
                    page.fill(f"{pane} .eq-box textarea", "CN c Y CN(-1) CN(-2)")
                    page.keyboard.press("Control+Enter")
                    page.wait_for_function("document.querySelector(\".project:not([hidden]) .pane:not([hidden]) table.grid\").tBodies[0].rows.length === 4", timeout=30000)
                    page.wait_for_function("document.querySelectorAll('.project:not([hidden]) .pane:not([hidden]) table.cand tbody tr').length >= 2", timeout=20000)
                    page.evaluate("() => document.querySelector('.project:not([hidden]) .pane:not([hidden]) table.cand')?.scrollIntoView({ block: 'center' })")
                    shot("bench-candidates")
                    rows = f"{pane} table.cand tbody tr"
                    page.click(f"{rows} >> nth=0 >> .check")
                    page.click(f"{rows} >> nth=1 >> .check")
                    page.click(f"{pane} .cand-tools .btn:has-text('겹쳐 보기')")
                    page.wait_for_selector(f"{pane} .ov-legend .ov-item")
                    page.evaluate("() => document.querySelector('.project:not([hidden]) .pane:not([hidden]) .ov-legend')?.scrollIntoView({ block: 'start' })")
                    shot("bench-overlay")
                    page.click(f"{pane} .cand-tools .btn:has-text('겹쳐 보기 닫기')")
                    page.wait_for_selector(f"{pane} .result-actions")
                    page.click(f"{rows}:has-text('CN(-2)') >> nth=0")
                    page.wait_for_timeout(500)
                    page.click(f"{pane} .result-actions .btn.primary")
                    page.wait_for_selector(".dialog .diff .dl.add")
                    shot("bench-adopt", ".dialog", 8)
                    page.click(".dialog-foot .btn.primary")
                    page.wait_for_selector(f"{pane} .view-head .tag.accent", timeout=20000)
                step("4. 식 고르기 — 추정 · 후보 · 겹쳐 보기 · 채택", s_bench)

                def s_batch():
                    page.click(f"{active} .side .row-item[data-key='bench:demand:I']")
                    page.click(f"{pane} [data-act='batch']")
                    page.wait_for_selector(f"{pane} .batch-form [data-slot='0']")
                    page.fill(f"{pane} [data-slot='0']", "Y | Y(-1)")
                    page.fill(f"{pane} [data-slot='1']", "(없음) | I(-1)")
                    page.wait_for_timeout(400)
                    shot("bench-batch")
                    page.click(f"{pane} [data-act='run-batch']")
                    page.wait_for_selector(f"{pane} .banner.ok", timeout=90000)
                    page.click(f"{pane} [data-act='batch-note']")
                    page.wait_for_selector(".dialog select")
                    page.click(".dialog .btn.primary")
                    page.wait_for_selector(f"{pane} .note-view .nb-bar", timeout=20000)
                    page.click(f"{pane} [data-act='run-block']")
                    page.wait_for_selector(f"{pane} .nb-bar .tag.ok", timeout=90000)
                    shot("note-view")
                step("4-1. 후보 묶음과 노트", s_batch)

                # ---- 5. 모형과 과거 재현 ------------------------------------------------------------------------------
                def s_model():
                    page.click(f"{active} .side .row-item[data-key='model:main']")
                    page.wait_for_selector(f"{pane} .block-row.asm", timeout=30000)
                    if page.locator(f"{pane} .flow-card").count():
                        page.click(f"{pane} .flow-card >> nth=0")
                        page.wait_for_selector(f"{pane} .block-row.asm")
                    shot("model-assembly")
                    page.click(f"{pane} .flow-card >> nth=1")
                    page.wait_for_selector(f"{pane} [data-act='solve']")
                    had = page.locator(f"{pane} .runs tr[data-run-id]").count()
                    page.click(f"{pane} [data-act='solve']")
                    page.wait_for_function(f"document.querySelectorAll('.project:not([hidden]) .pane:not([hidden]) .runs tr[data-run-id]').length > {had}", timeout=90000)
                    page.wait_for_selector(f"{pane} .fit-table tr.row")
                    page.click(f"{pane} .fit-table tr[data-var='P']")
                    page.wait_for_selector(f"{pane} .trace .trace-in")
                    page.wait_for_selector(f"{pane} .var-detail .fit svg path >> nth=1")
                    shot("model-hs")
                step("5. 모형 — 조립과 과거 재현", s_model)

                def s_flow():
                    page.click(f"{active} .side .row-item[data-key='flow:FLOWS/monthly.eqs']")
                    page.wait_for_selector(f"{pane} .step-row")
                    page.click(f"{pane} [data-act='run']")
                    page.wait_for_selector(f"{pane} .banner:has-text('run:monthly_')", timeout=180000)
                    shot("flow-run")
                step("5-1. 흐름 — 스크립트", s_flow)

                # ---- 6. 전망과 시나리오 ------------------------------------------------------------------------------
                def s_forecast():
                    page.click(f"{active} .side .wb[data-key='forecast']")
                    page.wait_for_selector(f"{pane} [data-act='solve']", timeout=30000)
                    if page.locator(f"{pane} [data-act='fold-assume']").count() and not page.locator(f"{pane} .asm-grid .cell").count():
                        page.click(f"{pane} [data-act='fold-assume']")
                    page.wait_for_selector(f"{pane} .asm-grid .cell", timeout=20000)
                    shot("fc-assume")
                    page.click(f"{active} .side-tabs [data-side='models']")
                    page.click(f"{active} [data-act='new-scenario']")
                    page.wait_for_selector(f"{pane} .sc-box [data-field='name']")
                    page.fill(f"{pane} [data-field='name']", "oil_rate")
                    page.fill(f"{pane} [data-field='desc']", "유가 20% 상승과 금리 0.5%p 인상")
                    page.fill(f"{pane} .sc-table [aria-label='변수']", "POIL")
                    page.fill(f"{pane} .sc-table [aria-label='크기']", "20")
                    page.click(f"{pane} [data-act='add-shock']")
                    page.fill(f"{pane} .sc-table tr[data-row='1'] [aria-label='변수']", "R")
                    page.fill(f"{pane} .sc-table tr[data-row='1'] [aria-label='크기']", "0.5")
                    page.click(f"{pane} .sc-table tr[data-row='1'] .segmented button >> nth=1")
                    page.wait_for_function("() => (document.querySelector('.project:not([hidden]) .pane:not([hidden]) .sc-preview .cmdline')?.textContent || '').includes('R=+0.5')", timeout=10000)
                    shot("fc-scenario")
                    page.click(f"{pane} [data-act='save-solve']")
                    page.wait_for_selector(f"{active} .tabbar .tab[aria-selected='true']:has-text('전망')", timeout=90000)
                    page.wait_for_selector(f"{pane} tr[data-sim].vs", timeout=90000)
                    page.wait_for_selector(f"{pane} [data-mode='diff']", timeout=30000)
                    if page.locator(f"{pane} .asm-grid .cell").count():
                        page.click(f"{pane} [data-act='fold-assume']")          # 가정 표를 접어 결과를 위로
                    page.click(f"{pane} [data-mode='annual']")
                    page.wait_for_timeout(400)
                    shot("fc-result")
                    page.click(f"{pane} [data-mode='diff']")
                    page.wait_for_timeout(300)
                    page.wait_for_selector(f"{pane} [data-act='split']", timeout=20000)
                    page.click(f"{pane} [data-act='split']")
                    page.wait_for_selector(f"{pane} .an-out .of-record", timeout=120000)
                    shot("fc-split")
                step("6. 전망과 시나리오", s_forecast)

                # ---- 7. 보고서 ----------------------------------------------------------------------------------------
                def s_report():
                    page.click(f"{active} .tabbar .tab:has-text('전망')")
                    page.wait_for_selector(f"{pane} [data-act='to-report']", timeout=20000)
                    page.click(f"{pane} [data-mode='level']")
                    page.click(f"{pane} [data-act='to-report']")
                    page.wait_for_selector(".dialog select[aria-label='보고서']")
                    page.fill(".dialog input[aria-label='표 제목']", "유가·금리 시나리오")
                    shot("report-send", ".dialog", 8)
                    page.click(".dialog-foot .btn.primary")
                    page.wait_for_selector(f"{pane} .region-row", timeout=30000)
                    page.wait_for_timeout(600)
                    shot("report-view")
                step("7. 보고서", s_report)

                # ---- 8. 기록과 되돌리기 ---------------------------------------------------------------------------------
                def s_records():
                    set_term(True)
                    page.click(f"{active} .side-tabs [data-side='records']")
                    page.wait_for_selector(f"{active} .side .row-item.rec", timeout=20000)
                    shot("records-list")
                    page.click(f"{active} .rec-sub [data-sub='changes']")
                    page.wait_for_selector(f"{active} .side .row-item.chg", timeout=10000)
                    page.click(f"{active} .side .row-item.chg:has-text('adopt') >> nth=0")
                    page.wait_for_selector(f"{pane} .split-view .detail .diff", timeout=20000)
                    set_term(False)
                    shot("records-change")
                    page.click(f"{pane} [data-act='revert']")
                    page.wait_for_selector(".dialog .cmd-note")
                    shot("records-revert", ".dialog", 8)
                    page.click(".dialog .btn:has-text('취소')")
                    set_term(True)
                    page.click(f"{active} .rec-sub [data-sub='milestones']")
                    page.click(f"{active} [data-act='new-milestone']")
                    page.wait_for_selector(".dialog input")
                    page.fill(".dialog input >> nth=0", "fc_2026_11")
                    page.fill(".dialog input >> nth=1", "11월 전망 확정")
                    shot("records-milestone-new", ".dialog", 8)
                    page.click(".dialog .btn.primary")
                    page.wait_for_selector(f"{pane} .milestone-view .banner.ok", timeout=30000)
                    set_term(False)
                    shot("records-milestone")
                step("8. 기록 · 되돌리기 · 이정표", s_records)

                # ---- 9. Claude 와 함께 ---------------------------------------------------------------------------------
                def s_claude():
                    set_term(True)
                    page.click(f"{active} .side-tabs [data-side='models']")
                    page.click(f"{active} .side .row-item[data-key='bench:demand:CN']")
                    page.wait_for_selector(f"{pane} [data-act='claude']")
                    page.click(f"{pane} [data-act='claude']")
                    page.wait_for_selector(".menu .menu-item")
                    shot("claude-menu")
                    page.keyboard.press("Escape")
                    cenv = dict(env, EQUION_WHO="claude")
                    r = subprocess.run([sys.executable, "-m", "equion", "propose", "new", "--title", "물가식에 시차 하나 더",
                                        "--why", "P(-2)를 넣으면 잔차의 자기상관이 줄어듭니다 — 과거 재현 RMSPE 도 함께 보세요",
                                        "--part", "price:P=P c Y POIL P(-1) P(-2)"], cwd=folder, env=cenv, capture_output=True, text=True, encoding="utf-8")
                    if r.returncode:
                        raise RuntimeError(r.stderr[-300:])
                    page.wait_for_selector(f"{active} .notice[data-key^='prop:']", timeout=30000)
                    shot("claude-notice")
                    page.click(f"{active} .notice[data-key^='prop:'] .btn.primary")
                    page.wait_for_selector(f"{pane} .split-view.proposals .diff .dl.add", timeout=20000)
                    shot("claude-proposal")
                step("9. Claude 와 함께", s_claude)

                # ---- 1-1. 명령 창 --------------------------------------------------------------------------------------
                def s_command():
                    set_term(True)
                    cmd = f"{active} .cmd-input"
                    page.click(cmd)
                    page.fill(cmd, "an unitroot Y --trend ct")
                    page.press(cmd, "Enter")
                    page.wait_for_selector(f"{active} .cmd-entry.ok", timeout=30000)
                    page.fill(cmd, "an gr")
                    page.wait_for_selector(f"{active} .cmd-suggest .cmd-sug", timeout=10000)
                    shot("start-command")
                    page.fill(cmd, "")
                step("1-1. 명령 창", s_command)

                if errors:
                    FAILED.append("화면 오류: " + "; ".join(errors[:3]))
                browser.close()
        finally:
            server.terminate()
            server.wait(10)
    for f in FAILED:
        log(f"✗ {f}")
    log("그림: 통과" if not FAILED else f"그림: 실패 {len(FAILED)}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default=os.path.join(ROOT, "docs", "desk", "img"), help="그림을 둘 폴더(기본 docs/desk/img)")
    sys.exit(run(ap.parse_args().out))
