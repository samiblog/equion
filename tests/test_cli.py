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

    shutil.rmtree(tmp, ignore_errors=True)
    print("\n" + "=" * 80)
    total = len(PASS) + len(FAIL)
    print(f"  RESULT: {len(PASS)} PASS / {len(FAIL)} FAIL  (total {total})  — {time.time() - t0:.1f}s")
    print("  " + ("[OK] ALL PASSED!" if not FAIL else "실패: " + ", ".join(FAIL)))
    print("=" * 80)
    return len(FAIL)


def test_suite():
    """pytest 진입점 — 이 파일의 검사 묶음 전체(하나라도 실패하면 실패). `python tests/test_cli.py`와 같은 검사."""
    assert main() == 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(99)
