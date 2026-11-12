#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_cli.py — 명령줄(2단계) 테스트.

실행: uv run python tests/test_cli.py   (종료코드 = 실패 수)

  A. new · check: 프로젝트 뼈대, 방정식 파일 문법·구조·결측 입력 검사, 스크립트 문법 검사
  B. run: 보고서 폴더(report.html·manifest.json·run.log·표·그래프), 매개변수(--set·--params·--smpl),
     형식(--format), 종료 코드(0·1·2·3·sys.exit), --fail-on, -q·--log·-- 인자·--dry-run, 실행 뒤 상태 복원
  C. info: 실행 환경·데이터·워크파일·방정식 파일·보고서 폴더
  D. 프로세스: python -m equion, 설치된 equion 명령, --threads, --watch, -i
  H. 출력 인코딩(Windows 파이프 → UTF-8) · --json은 JSON 하나(명령마다) · 상대 경로 규칙 · 프로젝트 밖의 an list
자료는 `equion new`가 만드는 예시 자료와 패키지의 예제 자료(eqn.datasets.toy_q)만 쓴다.
"""

import contextlib
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import traceback

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import equion as eqn  # noqa: E402
from equion.cli import commands  # noqa: E402
from equion.cli import main as cli  # noqa: E402
from equion.workfile import output as _output  # noqa: E402
from equion.workfile import runtime as _runtime  # noqa: E402

PASS, FAIL = [], []
TOY_DATA = None          # main()에서 정한다(예제 자료 toy_q CSV)
TOY_EQS = None           # main()에서 쓴다(toy_q로 만든 시험 모델 — 추정식 6 + 항등식 1)


def _read(path):
    """파일 내용(닫으면서 읽는다 — ResourceWarning 없이)."""
    with open(path, encoding="utf-8") as f:
        return f.read()


VERSION = _read(os.path.join(ROOT, "VERSION")).strip()
# 자식 프로세스 출력은 UTF-8로 주고받는다(Windows 파이프 기본 인코딩과 무관하게 같은 검사)
ENV = {**os.environ, "PYTHONPATH": ROOT + os.pathsep + os.environ.get("PYTHONPATH", ""), "PYTHONIOENCODING": "utf-8"}



def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  — {detail}" if detail else ""))


@contextlib.contextmanager
def cwd(path):
    old = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old)


def run(args, where=None):
    """CLI를 같은 프로세스에서 실행 → (종료 코드, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with cwd(where or os.getcwd()), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli(list(args))
    return code, out.getvalue(), err.getvalue()


def proc(args, where=None, stdin=None, timeout=300, env=None):
    r = subprocess.run([sys.executable, "-m", "equion", *args], cwd=where or ROOT, env=env or ENV,
                       capture_output=True, text=True, encoding="utf-8", errors="replace", input=stdin, timeout=timeout)
    return r.returncode, r.stdout, r.stderr


def raises(fn, exc=Exception, contains=None):
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            fn()
    except exc as e:
        return contains is None or contains in str(e)
    return False


def quiet(fn, *a, **k):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a, **k)


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def write(path, text):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def main():
    t0 = time.time()
    tmp = tempfile.mkdtemp(prefix="eqn-cli-")
    global TOY_DATA, TOY_EQS
    TOY_DATA = eqn.datasets.path("toy_q")
    TOY_EQS = write(os.path.join(tmp, "toy_model.txt"),
                    "I c Y(-1) R\nCN c Y CN(-1)\ndlog(P) c dlog(Y) dlog(POIL)\nRL c R RL(-1)\n"
                    "log(M2) c log(P) log(Y) RL log(M2(-1))\ndlog(CNNSA) c dlog(CN) @seas\nY = CN + I + G\n")
    proj = os.path.join(tmp, "demo")

    print("=" * 80)
    print("A. new · check")
    print("=" * 80)
    code, out, _ = run(["new", proj])
    files = ["README.md", ".gitignore", "DATA/data.csv", "EQUATIONS/model.txt", "scripts/main.py"]
    check("new: 예시 프로젝트 생성", code == 0 and all(os.path.isfile(os.path.join(proj, f)) for f in files))
    code, _, err = run(["new", proj])
    check("new: 비어 있지 않은 폴더는 거부(3)", code == 3 and "--force" in err)
    code, _, _ = run(["new", os.path.join(tmp, "bare"), "--bare"])
    check("new --bare: 예시 데이터·방정식 없음", code == 0 and not os.listdir(os.path.join(tmp, "bare", "DATA"))
          and os.path.isfile(os.path.join(tmp, "bare", "scripts", "main.py")))

    code, out, _ = run(["check", "EQUATIONS/model.txt", "--data", "DATA/data.csv"], proj)
    check("check: 예시 모델 통과(경고는 시작 시차 결측 2)", code == 0 and out.count("[경고]") == 2
          and "동시 1 (최대 3변수)" in out, out.splitlines()[-1] if out else "")
    code, _, _ = run(["check", "EQUATIONS/model.txt", "--data", "DATA/data.csv", "--strict"], proj)
    check("check --strict: 경고도 실패(3)", code == 3)
    code, out, _ = run(["check", "EQUATIONS/model.txt", "--data", "DATA/data.csv", "--smpl", "2001Q1:2024Q4"], proj)
    check("check --smpl: 구간 안 결측 없음", code == 0 and "[경고]" not in out and "결측 입력: 없음" in out)
    code, out, _ = run(["check", "EQUATIONS/model.txt"], proj)
    check("check: 데이터 없이 문법·구조만(경고 1)", code == 0 and "--data" in out)

    bad = write(os.path.join(tmp, "bad.txt"),
                "# 주석\nlog(CONS) c log(CONS(-1)) log(GDP\nlog(INV) c log(GDP) foo(RATE)\nGDP = CONS + INV + GOV\n")
    code, out, _ = run(["check", bad, "--data", os.path.join(proj, "DATA/data.csv"), "--json"])
    rep = json.loads(out) if out.strip().startswith("{") else {}
    lines = sorted(i["line"] for i in rep.get("issues", []) if i["level"] == "error")
    check("check: 문법 오류를 줄 번호와 함께(2·3행)", code == 3 and lines == [2, 3], str(lines))
    dup = write(os.path.join(tmp, "dup.txt"), "log(CONS) c log(GDP)\nCONS = GDP - INV - GOV\nGDP = CONS + INV + GOV\n")
    code, out, _ = run(["check", dup, "--data", os.path.join(proj, "DATA/data.csv")])
    check("check: 목표변수 중복 → 구조 오류(3)", code == 3 and "같은 변수를 결정" in out)
    unk = write(os.path.join(tmp, "unk.txt"), "log(CONS) c log(GDP) NOSUCH\nGDP = CONS + INV + GOV\n")
    code, out, _ = run(["check", unk, "--data", os.path.join(proj, "DATA/data.csv")])
    check("check: 데이터에 없는 변수 → 구조 오류(3)", code == 3 and "NOSUCH" in out)
    code, out, _ = run(["check", TOY_EQS, "--data", TOY_DATA, "--smpl", "1981Q1:2019Q4"])
    check("check: 예제 자료 시험 모델(추정식 6·항등식 1, 동시 2 + 순차 5, 결측 없음)",
          code == 0 and "추정식 6 · NLS 0 · 항등식 1" in out and "동시 1 (최대 2변수) · 순차 5" in out
          and "결측 입력: 없음" in out)
    code, out, _ = run(["check", TOY_EQS, "--data", TOY_DATA, "--smpl", "1975Q1:2019Q4"])
    check("check: 1975Q1부터면 RL 식의 시차 결측 경고(RL 자료가 1980Q1부터 — 21기 = HS의 일부식 제외 21)",
          code == 0 and out.count("[경고]") == 1 and "RL 식의 입력이 21기 비어 있음(1975Q1~1980Q1)" in out)
    syn = write(os.path.join(tmp, "syn.py"), "import equion as eqn\nx = (1,\n")
    code, out, _ = run(["check", syn])
    check("check: 스크립트 문법 오류(3)", code == 3 and "문법 오류" in out)
    code, _, _ = run(["check", os.path.join(tmp, "nothing.txt")])
    check("check: 없는 파일(3)", code == 3)

    print("\n" + "=" * 80)
    print("B. run")
    print("=" * 80)
    code, out, err = run(["run", "scripts/main.py", "--run-id", "r1"], proj)
    d = os.path.join(proj, "out", "r1")
    need = ["report.html", "manifest.json", "run.log", "plotly.min.js", "tables/01_eq_cons.csv",
            "graphs/05_g_gdp.html", "graphs/05_g_gdp.csv"]
    check("run: 성공(0)·보고서 폴더 구성", code == 0 and all(os.path.isfile(os.path.join(d, f)) for f in need),
          err[-200:])
    man = load(os.path.join(d, "manifest.json"))
    check("manifest: 형식·상태·버전", man["format"] == "equion-run" and man["status"] == "ok"
          and man["exit_code"] == 0 and man["format_version"] == 2 and "engine" not in man["versions"]
          and man["versions"]["equion"] == VERSION)
    check("manifest: 입력 파일 해시", [i["path"] for i in man["inputs"]] == ["DATA/data.csv", "EQUATIONS/model.txt"]
          and man["inputs"][0]["sha256"] == sha(os.path.join(proj, "DATA/data.csv")))
    check("manifest: 풀이 3회(기준선·시나리오·전망)와 기간별 상태",
          [(s["scenario"], s["start"], s["end"]) for s in man["solves"]] ==
          [("baseline", "2005Q1", "2024Q4"), ("g_up", "2005Q1", "2024Q4"), ("baseline", "2025Q1", "2026Q4")]
          and len(man["solves"][0]["periods"]) == 80 and man["solves"][0]["counts"]["ok"] == 80)
    check("manifest: 매개변수 기본값 기록", man["params"]["resolved"]["g_shock"] == 0.02
          and man["params"]["overrides"] == {})
    check("manifest: 출력 7개와 파일 목록", len(man["outputs"]) == 7
          and man["outputs"][4]["files"] == ["graphs/05_g_gdp.csv", "graphs/05_g_gdp.html"])
    html = _read(os.path.join(d, "report.html"))
    check("report.html: 표·그래프·plotly 내장 참조", "방정식 eq_cons" in html and "plotly.min.js" in html
          and html.count("class='card'") >= 7 and "cdn.plot.ly" not in html)
    log = _read(os.path.join(d, "run.log"))
    check("run.log: 화면 출력 그대로", "merge model.txt" in log and "방정식 eq_cons" in log)
    check("out/LATEST = 실행 ID", _read(os.path.join(proj, "out", "LATEST")).strip() == "r1")
    check("실행 뒤 상태 복원(스풀·말하기 수준·매개변수·실행 기록)",
          not _output.spool.items and _output.verbose() == 1 and not _runtime._OVERRIDES
          and _runtime.current_run() is None and _output.spool.mode == "auto")
    eff1 = pd.read_csv(os.path.join(d, "graphs/06_g_effect.csv"), index_col=0).iloc[-1, 0]

    code, _, _ = run(["run", "scripts/main.py", "--run-id", "r2", "--set", "g_shock=0.05", "--format", "csv"], proj)
    d2 = os.path.join(proj, "out", "r2")
    man2 = load(os.path.join(d2, "manifest.json"))
    eff2 = pd.read_csv(os.path.join(d2, "graphs/06_g_effect.csv"), index_col=0).iloc[-1, 0]
    check("--set: 기본값 형으로 변환(float)·결과 반영", code == 0 and man2["params"]["resolved"]["g_shock"] == 0.05
          and eff2 > 2 * eff1, f"{eff1:.3f} → {eff2:.3f}")
    check("--format csv: report.html·그래프 html·plotly 없음", not os.path.exists(os.path.join(d2, "report.html"))
          and not os.path.exists(os.path.join(d2, "plotly.min.js")) and "report" not in man2["files"]
          and not os.path.exists(os.path.join(d2, "graphs/05_g_gdp.html")))

    pj = write(os.path.join(tmp, "p.json"), json.dumps({"g_shock": 0.03, "horizon": "2025Q4"}))
    code, _, _ = run(["run", "scripts/main.py", "--run-id", "r3", "--params", pj, "--set", "g_shock=0.04",
                      "--format", "json,xlsx"], proj)
    d3 = os.path.join(proj, "out", "r3")
    man3 = load(os.path.join(d3, "manifest.json"))
    check("--params JSON + --set 우선", code == 0 and man3["params"]["resolved"]["g_shock"] == 0.04
          and man3["params"]["resolved"]["horizon"] == "2025Q4" and man3["solves"][2]["end"] == "2025Q4")
    t = load(os.path.join(d3, "tables/01_eq_cons.json"))
    sheets = pd.ExcelFile(os.path.join(d3, "tables.xlsx")).sheet_names
    check("--format json,xlsx: 표 JSON(제목·열)·xlsx 시트", t["title"] == "방정식 eq_cons" and "계수" in t["columns"]
          and len(sheets) == 5 and sheets[0] == "01_eq_cons")

    s_smpl = write(os.path.join(proj, "scripts", "smpl.py"),
                   "import equion as eqn\np = eqn.params(smpl='2005Q1 2024Q4')\n"
                   "wf = eqn.wfopen('DATA/data.csv')\nprint('OPEN', wf.smpl())\nprint('PARAM', p.smpl)\n"
                   "m = wf.model('m').merge('EQUATIONS/model.txt')\nwf.smpl(p.smpl)\nm.solve()\n")
    code, out, _ = run(["run", s_smpl, "--no-report", "--smpl", "2010Q1:2024Q4"], proj)
    check("--smpl: 새 워크파일 표본 + smpl 매개변수 덮기", code == 0 and "OPEN ('2010Q1', '2024Q4')" in out
          and "PARAM 2010Q1 2024Q4" in out)
    check("--no-report: 보고서 폴더 없음", not os.path.exists(os.path.join(proj, "out", "smpl")) and
          sorted(os.listdir(os.path.join(proj, "out"))) == ["LATEST", "r1", "r2", "r3"])

    s_part = write(os.path.join(proj, "scripts", "part.py"),
                   "import equion as eqn\nwf = eqn.wfopen('DATA/data.csv')\n"
                   "m = wf.model('m').merge('EQUATIONS/model.txt')\nm.solve()\n")
    code, _, _ = run(["run", s_part, "--no-report"], proj)
    check("--fail-on 기본(failed): 일부식 제외는 성공(0)", code == 0)
    code, _, err = run(["run", s_part, "--run-id", "part", "--fail-on", "partial"], proj)
    mp = load(os.path.join(proj, "out", "part", "manifest.json"))
    check("--fail-on partial: 종료 코드 2·사유 기록", code == 2 and mp["status"] == "solve_failed"
          and "일부식 제외 1" in mp["fail_reasons"][0] and "풀이 실패 조건" in err)

    s_err = write(os.path.join(proj, "scripts", "err.py"), "import equion as eqn\nx = 1\nraise RuntimeError('일부러')\n")
    code, _, err = run(["run", s_err, "--run-id", "err"], proj)
    me = load(os.path.join(proj, "out", "err", "manifest.json"))
    check("스크립트 오류: 종료 코드 1·보고서에 오류", code == 1 and me["status"] == "error"
          and me["error"]["type"] == "RuntimeError" and "err.py" in err and "runner.py" not in err)
    s_in = write(os.path.join(proj, "scripts", "inerr.py"), "import equion as eqn\neqn.wfopen('DATA/none.xlsx')\n")
    code, _, _ = run(["run", s_in, "--no-report"], proj)
    check("입력 오류(파일 없음): 종료 코드 3", code == 3)
    s_eq = write(os.path.join(proj, "scripts", "eqerr.py"),
                 f"import equion as eqn\nwf = eqn.wfopen('DATA/data.csv')\nwf.model('m').merge({dup!r}).solve()\n")
    code, _, _ = run(["run", s_eq, "--no-report"], proj)
    check("입력 오류(모델 구조): 종료 코드 3", code == 3)
    s_exit = write(os.path.join(proj, "scripts", "ex.py"), "import sys\nsys.exit(4)\n")
    s_exit0 = write(os.path.join(proj, "scripts", "ex0.py"), "import sys\nprint('bye')\nsys.exit(0)\n")
    c4, _, _ = run(["run", s_exit, "--no-report"], proj)
    c0, _, _ = run(["run", s_exit0, "--no-report"], proj)
    check("sys.exit(n) → 종료 코드 n", c4 == 4 and c0 == 0)

    code, out, err = run(["run", "scripts/main.py", "-q", "--no-report"], proj)
    check("-q: 요약 줄만", code == 0 and "방정식 eq_cons" not in out and "[equion] 성공" in out)
    s_argv = write(os.path.join(proj, "scripts", "argv.py"),
                   "import sys\nimport equion as eqn\nprint('ARGV', sys.argv[1:])\neqn.show(eqn.params(a=1).__dict__)\n"
                   "import pandas as pd\neqn.show(pd.DataFrame({'x': [1, 2]}))\n")
    logf = os.path.join(tmp, "run.log")
    code, out, _ = run(["run", s_argv, "--run-id", "argv", "--log", logf, "--set", "zz=1", "--", "--foo", "bar"], proj)
    ma = load(os.path.join(proj, "out", "argv", "manifest.json"))
    check("-- 뒤 인자 → 스크립트 sys.argv", code == 0 and "ARGV ['--foo', 'bar']" in out
          and ma["script_args"] == ["--foo", "bar"])
    check("--log: 같은 로그를 파일로", _read(logf)
          == _read(os.path.join(proj, "out", "argv", "run.log")))
    check("쓰이지 않은 --set 알림", ma["params"]["unused"] == ["zz"] and "쓰이지 않은 --set: zz" in out)
    check("eqn.show(DataFrame) → 표로 수집", [o["kind"] for o in ma["outputs"]] == ["text", "table"])
    s_typ = write(os.path.join(proj, "scripts", "typed.py"),
                  "import equion as eqn\np = eqn.params(n=3, flag=False, ratio=0.5)\nprint('P', p.n, p.flag, p.ratio)\n")
    bad = {k: run(["run", s_typ, "--no-report", "--set", k], proj) for k in ("flag=maybe", "n=abc", "ratio=x")}
    check("--set 값이 매개변수의 형이 아님(참거짓에 maybe·정수에 abc) → 입력 오류 3, 이름·기본값을 알리고 '쓰이지 않은 --set'은 아님",
          all(c == 3 and "쓰이지 않은 --set" not in o for c, o, _ in bad.values())
          and "flag은(는) 참거짓" in bad["flag=maybe"][2] and "n은(는) 정수입니다(기본값 3)" in bad["n=abc"][2],
          str({k: v[0] for k, v in bad.items()}))
    c_no, o_no, _ = run(["run", s_typ, "--no-report", "--set", "flag=no", "--set", "n=7"], proj)
    check("--set 참거짓 no·정수는 그대로 읽는다", c_no == 0 and "P 7 False 0.5" in o_no)
    s_unk = write(os.path.join(proj, "scripts", "unknown_var.py"),
                  "import equion as eqn\nwf = eqn.wfopen('DATA/data.csv')\nwf.equation('e').ls('I c NOPE')\n")
    c_unk, _, e_unk = run(["run", s_unk, "--no-report"], proj)
    check("식이 쓴 변수가 자료에 없음 → 입력 오류 3(equion check·문법 오류와 같게)", c_unk == 3 and "NOPE" in e_unk, str(c_unk))

    s_w = write(os.path.join(proj, "scripts", "wr.py"),
                f"import equion as eqn\nwf = eqn.wfopen('DATA/data.csv')\nwf.write({os.path.join(tmp, 'w.csv')!r})\n"
                f"wf.save({os.path.join(tmp, 'demo_wf')!r})\n")
    code, _, _ = run(["run", s_w, "--run-id", "wr"], proj)
    mw = load(os.path.join(proj, "out", "wr", "manifest.json"))
    check("스크립트가 쓴 파일 기록", code == 0 and [x["kind"] for x in mw["written"]] == ["series", "workfile"])

    code, _, _ = run(["run", "scripts/main.py", "--run-id", "r1", "-q"], proj)
    check("--run-id 같은 이름: 이전 보고서를 비우고 다시 씀", code == 0
          and load(os.path.join(d, "manifest.json"))["started_at"] >= man["started_at"])
    os.makedirs(os.path.join(proj, "out", "keep"))
    write(os.path.join(proj, "out", "keep", "mine.txt"), "x")
    code, _, err = run(["run", "scripts/main.py", "--run-id", "keep", "-q"], proj)
    check("--run-id가 보고서 아닌 폴더면 지우지 않음(1)", code == 1
          and os.path.isfile(os.path.join(proj, "out", "keep", "mine.txt")) and "지우지 않음" in err)

    code, out, _ = run(["run", "scripts/main.py", "--dry-run"], proj)
    check("--dry-run: 실행하지 않음", code == 0 and "문법: 정상" in out and "merge" not in out)
    code, _, _ = run(["run", syn, "--dry-run"])
    check("--dry-run: 문법 오류면 1", code == 1)
    checks = [run(["run", "nothing.py"], proj)[0], run(["run", "scripts/main.py", "--set", "novalue"], proj)[0],
              run(["run", "scripts/main.py", "--format", "pdf"], proj)[0],
              run(["run", "scripts/main.py", "--smpl", "2000Q1"], proj)[0], run(["run", "--nope"], proj)[0],
              run(["check", "x.txt", "--", "a"], proj)[0]]
    check("입력·사용법 오류는 모두 3", checks == [3] * 6, str(checks))

    print("\n" + "=" * 80)
    print("C. info")
    print("=" * 80)
    code, out, _ = run(["info", "--json"])
    env = json.loads(out)
    check("info: 실행 환경", code == 0 and env["versions"]["equion"] == VERSION and "numpy" in env["versions"])
    code, out, _ = run(["info", "DATA/data.csv", "--json"], proj)
    di = json.loads(out)
    check("info: 데이터 파일", code == 0 and di["freq"] == "Q" and di["periods"] == 100 and di["series"] == 5
          and di["range"] == "2000Q1~2024Q4")
    code, out, _ = run(["info", os.path.join(tmp, "demo_wf.eqw"), "--json"])
    wi = json.loads(out)
    check("info: 워크파일(.eqw)", code == 0 and wi["kind"] == "workfile" and wi["series"] == 5)
    code, out, _ = run(["info", TOY_EQS, "--json"])
    ei = json.loads(out)
    check("info: 방정식 파일", code == 0 and (ei["estimated"], ei["identities"]) == (6, 1))
    code, out, _ = run(["info", os.path.join(proj, "out", "part")])
    check("info: 보고서 폴더", code == 0 and "실행 보고서" in out and "solve_failed" in out)
    code, _, _ = run(["info", os.path.join(tmp, "nothing.xlsx")])
    check("info: 없는 경로(3)", code == 3)

    print("\n" + "=" * 80)
    print("D. 프로세스 수준")
    print("=" * 80)
    code, out, _ = proc(["--version"])
    check("python -m equion --version — 공개 버전 하나", code == 0 and out.strip() == f"equion {VERSION}"
          and eqn.__version__ == VERSION)
    exe = os.path.join(os.path.dirname(sys.executable), "equion" + (".exe" if os.name == "nt" else ""))
    if os.path.exists(exe):
        r = subprocess.run([exe, "--version"], capture_output=True, text=True, encoding="utf-8", cwd=tmp)
        check("설치된 equion 명령(다른 폴더에서)", r.returncode == 0 and VERSION in r.stdout)
    else:
        check("설치된 equion 명령 — 설치되지 않아 건너뜀(uv sync로 설치)", True)
    code, out, err = proc(["check", TOY_EQS, "--data", TOY_DATA],
                          env={**ENV, "PYTHONIOENCODING": "cp1252"})
    check("한글을 못 쓰는 출력(cp1252 파이프 — 영문 Windows)에서도 멈추지 않음", code == 0 and "\\u" in out,
          err[-200:])
    s_thr = write(os.path.join(proj, "scripts", "thr.py"), "import os\nprint('THREADS', os.environ.get('OPENBLAS_NUM_THREADS'))\n")
    code, out, _ = proc(["run", "scripts/thr.py", "--threads", "1", "--run-id", "thr"], proj)
    mt = load(os.path.join(proj, "out", "thr", "manifest.json"))
    check("--threads: BLAS 스레드 환경변수로 다시 실행", code == 0 and "THREADS 1" in out
          and mt["threads"].get("OPENBLAS_NUM_THREADS") == "1")

    s_i = write(os.path.join(proj, "scripts", "inter.py"), "x = 41\n")
    code, out, _ = proc(["run", "scripts/inter.py", "-i", "--no-report"], proj, stdin="print('ANSWER', x + 1)\n")
    check("-i: 스크립트 변수로 대화창", code == 0 and "ANSWER 42" in out)

    s_watch = write(os.path.join(proj, "scripts", "watch.py"),
                    "import equion as eqn\nwf = eqn.wfopen('DATA/data.csv')\nprint('RUN')\n")
    shutil.rmtree(os.path.join(proj, "out"), ignore_errors=True)

    def touch():
        time.sleep(4)
        with open(os.path.join(proj, "DATA", "data.csv"), "a", encoding="utf-8") as f:
            f.write("")
        os.utime(os.path.join(proj, "DATA", "data.csv"))
    th = threading.Thread(target=touch)
    th.start()
    buf = io.StringIO()
    with cwd(proj), contextlib.redirect_stdout(buf):
        code = commands.watch(["run", "scripts/watch.py", "-q", "--watch", "--interval", "0.2"],
                              "scripts/watch.py", interval=0.2, max_runs=2)
    th.join()
    check("--watch: 하위 실행 인자 — --manifest-to는 스크립트 인자(--) 앞에",
          commands._with_manifest(["run", "a.py", "--", "x"], "m.json") == ["run", "a.py", "--manifest-to", "m.json", "--", "x"]
          and commands._with_manifest(["run", "a.py"], "m.json") == ["run", "a.py", "--manifest-to", "m.json"])
    reports = [x for x in os.listdir(os.path.join(proj, "out")) if x != "LATEST"]
    check("--watch: 입력 파일이 바뀌면 다시 실행(보고서 2개)", code == 0 and len(reports) == 2
          and f"바뀜: {os.path.join('DATA', 'data.csv')}" in buf.getvalue(), str(reports))   # 화면 메시지는 OS 구분자

    print("\n" + "=" * 80)
    print("F. 보안 — 비밀 값 가리기·--redact·레거시 pickle·convert")
    print("=" * 80)
    os.makedirs(os.path.join(proj, "out"), exist_ok=True)
    os.environ["EQUION_TEST_TOKEN"] = "envsecret-9f8e7d"
    s_sec = write(os.path.join(proj, "scripts", "sec.py"),
                  "import equion as eqn\nk = eqn.secret('EQUION_TEST_TOKEN')\np = eqn.params(api_key='x', n=1)\n"
                  "print('KEY', k, p.api_key)\nraise RuntimeError('실패 ' + k)\n")
    code, out, err = run(["run", s_sec, "--run-id", "sec", "--set", "api_key=SUPERSECRET123", "--format", "csv,html"], proj)
    d_sec = os.path.join(proj, "out", "sec")
    blob = "".join(_read(os.path.join(d_sec, f)) for f in ("manifest.json", "report.html", "run.log"))
    check("비밀 값(eqn.secret·이름이 key인 --set)은 manifest·report·run.log에 남지 않음", code == 1
          and "SUPERSECRET123" not in blob and "envsecret-9f8e7d" not in blob and "***" in blob)
    check("eqn.secret: 없는 환경변수 → 분명한 오류", raises(lambda: eqn.secret("EQUION_NO_SUCH_SECRET_X"), ValueError, "환경변수"))
    code, _, _ = run(["run", "scripts/main.py", "--run-id", "red", "--redact", "-q"], proj)
    mr = load(os.path.join(proj, "out", "red", "manifest.json"))
    check("--redact: 작업 폴더·실행 파일 경로 없음, 경로는 상대", code == 0 and mr.get("redacted") is True
          and "cwd" not in mr and "python_executable" not in mr["platform"]
          and all(not os.path.isabs(i["path"]) for i in mr["inputs"]))
    from equion.worktable import WorkTable
    import warnings as _w
    wt = quiet(lambda: WorkTable(name="old", freq="Q", register=False))
    quiet(lambda: wt.load_data(os.path.join(proj, "DATA", "data.csv")))
    quiet(lambda: wt.load_equations(os.path.join(proj, "EQUATIONS", "model.txt")))
    quiet(wt.estimate)
    with _w.catch_warnings(record=True) as caught:
        _w.simplefilter("always")
        pk = quiet(lambda: wt.save(os.path.join(tmp, "legacy.pkl"), fmt="pickle"))
    check("pickle 저장은 DeprecationWarning", any(issubclass(c.category, DeprecationWarning) for c in caught))
    check("레거시 pickle은 기본으로 열지 않음", raises(lambda: WorkTable.load(pk, register=False), ValueError, "allow_pickle"))
    code, _, err = run(["convert", pk, os.path.join(tmp, "conv")])
    check("convert: --allow-pickle 없이는 거부(3)", code == 3 and "--allow-pickle" in err)
    code, out, _ = run(["convert", pk, os.path.join(tmp, "conv"), "--allow-pickle"])
    wconv = eqn.wfopen(os.path.join(tmp, "conv"))
    check("convert --allow-pickle → 워크파일(.eqw), 다시 열림", code == 0 and os.path.isdir(os.path.join(tmp, "conv.eqw"))
          and len(wconv.objects().data) >= 3)
    code, _, _ = run(["convert", os.path.join(tmp, "conv.eqw"), os.path.join(tmp, "conv2")])
    check("convert: 워크파일 → 워크파일", code == 0 and os.path.isdir(os.path.join(tmp, "conv2.eqw")))

    print("=" * 80)
    print("G. 명령 한 줄 실행기(Desk의 명령 창 — D52)")
    print("=" * 80)
    from equion.cli.line import catalog, run_line
    lp = quiet(eqn.Project.create, os.path.join(tmp, "line_demo"))
    here = os.getcwd()
    r1 = run_line(lp.root, "est demand:CN")
    r2 = run_line(lp.root, "equion an unitroot Y --trend ct")
    r3 = run_line(lp.root, f"adopt {r1.records[0]}" if r1.records else "adopt est:nope")
    check("한 줄: 명령줄 그대로(앞의 equion은 빼도 된다) — 새 기록·새 바뀜 기록을 돌려주고 '누가'는 desk, 지금 폴더는 그대로",
          r1.code == 0 and r1.records == ["est:cn_0001"] and r2.code == 0 and r2.records == ["an:unitroot_0001"] and r2.line == "an unitroot Y --trend ct"
          and r3.code == 0 and r3.changes == ["h0002"] and r3.records == [] and os.getcwd() == here
          and load(os.path.join(lp.root, "work", "est", "cn_0001", "record.json"))["who"] == "desk", f"{r1.to_dict()}"[:300])
    r4 = run_line(lp.root, "an nope Y")
    r5 = run_line(lp.root, "run x.py")
    r6 = run_line(lp.root, "new other")
    r7 = run_line(lp.root, 'est "CN c Y (')
    r8 = run_line(lp.root, "work list --json")
    check("한 줄: 틀린 명령은 종료 코드 3과 글 · Python 스크립트·새 프로젝트는 받지 않는다 · 따옴표 · JSON 출력",
          r4.code == 3 and "사용법" in r4.out and r5.code == 3 and r5.denied and "터미널" in r5.denied and r6.denied
          and r7.code == 3 and "따옴표" in r7.out and r8.code == 0 and isinstance(json.loads(r8.out), list), r4.out[:120])
    other = quiet(eqn.Project.create, os.path.join(tmp, "line_other"))
    esc = [run_line(lp.root, x) for x in (f"est demand:CN -p {other.root}", f"est demand:CN --proj={other.root}", f"an stats Y -p{other.root}",
                                          "run FLOWS/monthly.eqs --threads 2", "run FLOWS/monthly.eqs --thr 2", "guide skill --install user",
                                          "guide skill --inst project")]
    check("한 줄: 다른 프로젝트(-p · --proj= · -pX) · 다시 띄우기(--threads · 줄인 --thr) · 스킬 설치는 받지 않는다 — 다른 프로젝트에 기록이 생기지 않는다(QA)",
          all(r.code == 3 and r.denied for r in esc) and not os.path.isdir(os.path.join(other.root, "work", "est")),
          str([(r.line, r.denied) for r in esc if not r.denied])[:300])
    cat = catalog()
    cmds = {c["command"]: c for c in cat}
    unit = cmds.get("an unitroot", {})
    check("명령 목록: 명령마다 도움말·인자·옵션(값을 받는지·고를 값) — 분석은 등록부에서, run은 받고 new는 받지 않는다",
          {"est", "hs", "sim", "an corr", "an granger", "group define", "block add", "history revert"} <= set(cmds)
          and any(o["flags"][0] == "--trend" and o["choices"] == ["n", "c", "ct"] and o["takes"] for o in unit.get("options", []))
          and any(o["flags"][0] == "--json" and not o["takes"] for o in unit.get("options", []))
          and unit["args"][0]["name"] == "target" and cmds["run"]["denied"] is None and cmds["new"]["denied"], str(unit)[:300])

    _encoding_json_paths(tmp)
    _busy_tests(tmp)
    shutil.rmtree(tmp, ignore_errors=True)
    print("\n" + "=" * 80)
    total = len(PASS) + len(FAIL)
    print(f"  RESULT: {len(PASS)} PASS / {len(FAIL)} FAIL  (total {total})  — {time.time() - t0:.1f}s")
    print("  " + ("[OK] ALL PASSED!" if not FAIL else "실패: " + ", ".join(FAIL)))
    print("=" * 80)
    return len(FAIL)


def _encoding_json_paths(tmp):
    print("=" * 80)
    print("H. 출력 인코딩 · --json은 JSON 하나 · 상대 경로 규칙")
    print("=" * 80)
    hp = quiet(eqn.Project.create, os.path.join(tmp, "enc_demo"))
    bare = {k: v for k, v in ENV.items() if k not in ("PYTHONIOENCODING", "PYTHONUTF8")}   # Claude Code의 셸처럼 아무것도 정하지 않음

    def raw(args, where, env):
        r = subprocess.run([sys.executable, "-m", "equion", *args], cwd=where, env=env, capture_output=True, stdin=subprocess.DEVNULL,
                           timeout=300)
        return r.returncode, r.stdout, r.stderr

    code, out, _ = raw(["guide"], hp.root, bare)
    try:
        text = out.decode("utf-8")
    except UnicodeDecodeError:
        text = ""
    check("인코딩: 파이프(인코딩을 정하지 않음)로 나가는 출력은 UTF-8 — equion guide의 '—'·한글이 그대로(\\u2014가 아니다)",
          code == 0 and text.startswith("# Equion — Claude를 위한 모형 작업 안내") and "\\u2014" not in text, repr(out[:60]))
    code, out, _ = raw(["est", "demand:ZZ", "--json"], hp.root, bare)
    try:
        msg = json.loads(out.decode("utf-8"))["error"]["message"]
    except (UnicodeDecodeError, ValueError, KeyError):
        msg = ""
    check("인코딩: --json 오류도 UTF-8 JSON — 한글 메시지가 그대로", code == 3 and "없는 부품" in msg, repr(out[:80]))
    code, out, _ = raw(["guide"], hp.root, {**bare, "PYTHONIOENCODING": "cp949"})
    check("인코딩: 사람이 정한 인코딩(PYTHONIOENCODING=cp949)은 그대로 — 그 인코딩에 없는 글자만 \\uXXXX",
          code == 0 and out.decode("cp949", errors="strict").startswith("# Equion \\u2014 Claude를 위한"), repr(out[:60]))

    # --json: 명령마다(성공·오류) 표준출력 전체가 JSON 하나 — 자료를 여는 요약 줄([이름] 열기 …)이 앞에 붙지 않는다
    cmds = [["scenario", "define", "s2", "--shock", "POIL=+10%"], ["scenario", "define", "bad", "--shock", "ZZ"], ["scenario", "list"],
            ["scenario", "show", "oil20"], ["scenario", "remove", "s2"], ["scenario", "remove", "nope"],
            ["block", "define", "extra"], ["block", "add", "extra", "G c Y"], ["block", "add", "extra", "G c Y"],
            ["block", "remove", "extra:G"], ["block", "remove", "demand:NOPE"], ["model", "define", "m2", "--blocks", "demand"],
            ["model", "define", "m3", "--blocks", "nope"], ["group", "list"], ["group", "define", "g2", "--series", "Y,CN"],
            ["group", "remove", "g2"], ["view", "list"], ["view", "define", "v1", "--series", "Y"], ["desk", "show", "model:main"],
            ["milestone", "make", "m1"], ["milestone", "list"], ["milestone", "show", "m1"], ["milestone", "restore", "m1"],
            ["milestone", "show", "nope"], ["bundle", "make", "--out", "exports/j.zip"],
            ["bundle", "open", os.path.join(tmp, "none.zip"), os.path.join(tmp, "enc_open")],
            ["assemble", "main"], ["ident", "demand:Y"], ["ident", "demand:Y", "--check"], ["data", "list"], ["data", "diff"],
            ["data", "inbox"], ["data", "preview", "DATA/raw/toy_q.csv"], ["data", "use", "nope"], ["data", "build"],
            ["est", "demand:CN"], ["work", "list"], ["history", "list"], ["propose", "list"], ["an", "list"], ["an", "stats", "Y"],
            ["note", "check", "notes/data_check.md"], ["note", "run", "notes/data_check.md"], ["report", "new", "r1"],
            ["report", "check", "r1"], ["check", "FLOWS/monthly.eqs"], ["run", "FLOWS/monthly.eqs", "--dry-run"],
            ["script", "export", "FLOWS/monthly.eqs", "--py", "--force"], ["hs", "--range"]]
    bad = []
    for c in cmds:
        code, out, err = run([*c, "--json"], hp.root)
        try:
            json.loads(out)
        except ValueError:
            bad.append(f"{' '.join(c)} → {code} {out[:70]!r}")
    check(f"--json: 명령 {len(cmds)}개(성공·오류)의 표준출력이 모두 JSON 하나(scenario define·block add·remove·milestone·bundle 포함)",
          not bad, "; ".join(bad[:4]))
    # 이정표 되돌리기 — 자료 회차가 이정표 때와 같으면 자료 알림을 만드는 길을 탄다(인자 둘인 함수에 요약 감추기를 단 것이 TypeError·1이던 것)
    run(["milestone", "make", "mr"], hp.root)
    run(["est", "CN c Y", "--for", "demand:CN", "--as", "mr_s"], hp.root)
    run(["adopt", "est:mr_s"], hp.root)
    code_r, out_r, err_r = run(["milestone", "restore", "mr"], hp.root)
    code_j, out_j, _ = run(["milestone", "restore", "mr", "--json"], hp.root)
    check("milestone restore — 되돌리고 종료 코드 0(글·--json 모두, 바꿀 것이 없을 때도)", code_r == 0 and "milestone restore" in out_r
          and code_j == 0 and json.loads(out_j)["change"] is None, f"{code_r} {err_r[-200:]} {code_j}")
    code, out, _ = run(["scenario", "define", "s3", "--shock", "POIL=+5%"], hp.root)
    check("요약 줄: 글 출력에도 자료를 여는 줄([이름] 열기 …)이 붙지 않는다(scenario define)", code == 0 and "열기" not in out
          and out.startswith("[scenario"), out[:120])

    # 상대 경로: 있는 파일은 지금 폴더에서 먼저, 없으면 프로젝트 폴더에서 · 만드는 파일은 프로젝트 폴더 기준
    code, out, err = run(["check", "EQUATIONS/demand.txt", "--data", f"work/data/{hp.vintage}/series.csv", "-p", hp.root], tmp)
    check("경로: check -p(다른 폴더에서) — 방정식 파일·자료를 프로젝트 폴더에서 찾는다", code == 0 and "통과" in out, (out + err)[-200:])
    code, out, err = run(["check", "demand.txt", "--data", f"../work/data/{hp.vintage}/series.csv"], os.path.join(hp.root, "EQUATIONS"))
    check("경로: check(프로젝트 하위 폴더에서) — 지금 폴더의 파일 그대로", code == 0 and "통과" in out, (out + err)[-200:])
    code, out, err = run(["check", "EQUATIONS/nope.txt", "-p", hp.root], tmp)
    code2, _, err2 = run(["check", "x.txt", "-p", os.path.join(tmp, "no_project_here")], tmp)
    check("경로: 어디에도 없는 파일은 준 경로로 말한다(3) · -p가 프로젝트가 아니면(3)", code == 3 and "nope.txt" in err
          and code2 == 3 and "찾지 못했습니다" in err2, err + err2)
    os.makedirs(os.path.join(hp.root, "DATA", "raw", "inbox"), exist_ok=True)
    shutil.copyfile(os.path.join(hp.root, "DATA", "raw", "toy_q.csv"), os.path.join(hp.root, "DATA", "raw", "inbox", "toy_q_2020Q1.csv"))
    code, out, err = run(["data", "add", "DATA/raw/inbox/toy_q_2020Q1.csv", "--source", "na", "-p", hp.root], tmp)
    check("경로: data add -p(다른 폴더에서) — data inbox가 알려 준 꼴(DATA/raw/inbox/…) 그대로", code == 0 and "[data add]" in out, (out + err)[-200:])
    code, out, err = run(["data", "preview", "toy_q.csv"], os.path.join(hp.root, "DATA", "raw"))
    code2, out2, _ = run(["note", "check", "data_check.md"], os.path.join(hp.root, "notes"))
    check("경로: 하위 폴더에서 data preview toy_q.csv(DATA/raw/) · note check data_check.md(notes/)", code == 0 and "[data preview]" in out
          and code2 == 0 and "notes/data_check.md" in out2, (out + err)[-200:])
    os.makedirs(os.path.join(tmp, "elsewhere"), exist_ok=True)
    code, out, err = run(["bundle", "make", "--out", "exports/b_rel.zip", "-p", hp.root], os.path.join(tmp, "elsewhere"))
    check("경로: bundle make --out 상대 경로는 프로젝트 폴더 기준(export --xlsx와 같다)", code == 0
          and os.path.isfile(os.path.join(hp.root, "exports", "b_rel.zip"))
          and not os.path.exists(os.path.join(tmp, "elsewhere", "exports")), (out + err)[-200:])
    code, out, err = run(["an", "list"], os.path.join(tmp, "elsewhere"))
    code2, out2, _ = run(["an", "list", "--json"], os.path.join(tmp, "elsewhere"))
    check("an list는 등록부만 본다 — 프로젝트 밖에서도(0)", code == 0 and "[an list]" in out and code2 == 0
          and any(r["분석"] == "unitroot" for r in json.loads(out2)), err[-200:])


def _busy_tests(tmp):
    print("=" * 80)
    print("I. 다른 프로그램이 쥔 파일·다른 명령이 고치는 중 — 트레이스백 대신 입력 오류(3)")
    print("=" * 80)
    from equion.cli import errors
    from equion.work.lock import FileBusy, ProjectBusy, project_lock
    e = PermissionError(13, "Permission denied", "C:/x/EQUATIONS/adopted.toml")
    check("오류 글: 접근 거부(PermissionError) · FileBusy · ProjectBusy는 사람이 읽는 글, 다른 오류는 None(버그는 트레이스백 그대로)",
          "adopted.toml" in (errors.busy_text(e) or "") and "다른 프로그램" in errors.busy_text(e)
          and errors.busy_text(FileBusy("가", "a.txt")) == "가" and errors.busy_text(ProjectBusy("나")) == "나"
          and errors.busy_text(ValueError("x")) is None and errors.busy_text(FileNotFoundError(2, "없음", "x")) is None)
    bd = os.path.join(tmp, "busy")
    quiet(eqn.Project.create, bd)
    env = dict(ENV, EQUION_LOCK_TIMEOUT="1")
    with project_lock(bd):
        code, out, err = proc(["adopt", "est:none", "-p", bd, "--json"], env=env)
    j = json.loads(out) if out.strip().startswith("{") else {}
    check("잠금을 다른 명령이 쥐고 있으면 --json도 오류 JSON 하나(종료 코드 3 · kind input)",
          code == 3 and j.get("error", {}).get("kind") == "input" and "고치는 중" in j["error"]["message"], (out + err)[-300:])
    if os.name != "nt":
        print("  (Windows가 아니라 쥔 파일 시험은 건너뜀)")
        return
    import ctypes
    from ctypes import wintypes
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.CreateFileW.restype = wintypes.HANDLE
    k.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD,
                              wintypes.HANDLE]
    h = k.CreateFileW(os.path.join(bd, "equion.toml"), 0x80000000 | 0x40000000, 0, None, 3, 0x80, None)
    try:
        code, out, err = proc(["assemble", "main", "-p", bd])
    finally:
        k.CloseHandle(h)
    check("equion.toml을 다른 프로그램이 독점으로 쥐고 있으면 — 트레이스백이 아니라 그 파일과 함께 입력 오류(3)",
          code == 3 and "equion.toml" in err and "Traceback" not in err, err[-300:])


def test_suite():
    """pytest 진입점 — 이 파일의 검사 묶음 전체(하나라도 실패하면 실패). `python tests/test_cli.py`와 같은 검사."""
    assert main() == 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(99)
