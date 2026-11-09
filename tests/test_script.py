#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_script.py — Equion 스크립트(.eqs)·실행 기록·재연·받은 원자료(D36 — 개발 계획 E5) 테스트.

실행: uv run python tests/test_script.py   (종료코드 = 실패 수)

  A. 문법: 주석(줄 끝·따옴표 안·an:x#2)·## 제목·param(목록·내장 이름·두 번)·앞의 equion·run 포함(돌고 돎·없는 파일)·py·expect·
     허용 목록(스크립트가 부를 수 없는 명령)·{이름} 검사(모르는 이름·앞 단계에 없는 기록·거르기)
  B. 값 바꿔 넣기: 목록·따옴표·{{ }}·미리보기에서 그대로 둘 이름
  C. 등록부: 노트와 스크립트의 허용 목록 · 바꾸는 파일(effects) — 노트는 est --adopt·an keep을 못 부른다
  D. 받은 원자료(DATA/raw/inbox/): 짝짓기(이름·inbox 글롭·짝 없음·여럿)·틀 검사·넣기(복사·출처·받은 상자 비움·바뀜 기록)·
     하나라도 문제면 아무것도 넣지 않음 · data build --inbox · data inbox
  E. 실행: 단계·상태·기록(run:)·script.eqs·src/·defs/·steps/·summary.md · 단계의 기록에 run·누가 '스크립트' · --set · --from
  F. 확인(expect): 통과·--flag(계속)·--stop(종료 코드 2, 뒤 단계 안 함)·지표(HS·전망·추정)·모르는 지표(1)
  G. 실패: 단계 실패에서 멈춤(그 종료 코드)·Python 단계(기록·누가)·python=False
  H. 미리보기·검사: 기록을 남기지 않음·실행 때 정해지는 값·바꾸는 파일·선택지·모형·시나리오·노트·부품 검사
  I. 재연: 같음 · 정의를 바꾼 뒤에도 그때 그대로 · 프로젝트는 그대로 · 재연의 재연은 안 됨
  J. 초안·Python으로: script new(--from-records·--last — --as·-p 뺌) · export --py → 실행하면 같은 숫자
  K. 명령줄: run x.eqs·--dry-run·--json·--replay·check x.eqs·script new·export — 종료 코드, .py 선택지 거절
  L. 완료 기준: 예제 프로젝트에서 원자료 교체 → equion run FLOWS/monthly.eqs가 보고서까지 · 같은 회차로 다시 돌려도 글이 남음 · replay가 같은 결과
자료는 예제 프로젝트(예제 자료 toy_q·toy_m)와 그것을 코드로 바꾼 합성 표만 쓴다.
"""

import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import traceback

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import equion as eqn  # noqa: E402
from equion import registry as reg  # noqa: E402
from equion.cli import main as cli  # noqa: E402
from equion.projects import Project, ProjectError  # noqa: E402
from equion.script import ScriptError, parse, resolve  # noqa: E402
from equion.script.language import strip_comment  # noqa: E402
from equion.script.runner import compare_records  # noqa: E402

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  — {detail}" if detail else ""))


def quiet(fn, *a, **k):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return fn(*a, **k)


def raises(fn, exc=Exception, contains=None):
    try:
        quiet(fn)
    except exc as e:
        return contains is None or contains in str(e)
    return False


def write(path, text):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    return path


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def run(args, where=None):
    out, err = io.StringIO(), io.StringIO()
    old = os.getcwd()
    os.chdir(where or old)
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli(list(args))
    finally:
        os.chdir(old)
    return code, out.getvalue(), err.getvalue()


def new_project(base, name):
    d = os.path.join(base, name)
    return quiet(Project.create, d), d


def revised_toy_q(d, name="toy_q_2020Q1.csv", drop=None):
    """예제 자료 toy_q에 한 분기(2020Q1 = 마지막 값 × 1.01)를 더하고 2019Q3 소비를 0.2% 고친 합성 원자료를 받은 상자에."""
    df = pd.read_csv(os.path.join(d, "DATA", "raw", "toy_q.csv"), index_col=0)
    df.loc["2020Q1"] = df.iloc[-1] * 1.01
    df.loc["2019Q3", "CN"] *= 1.002
    if drop:
        df = df.drop(columns=[drop])
    path = os.path.join(d, "DATA", "raw", "inbox", name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    df.to_csv(path)
    return path


def hashes(d):
    import hashlib
    out = {}
    for r, ds, fs in os.walk(d):
        ds[:] = [x for x in ds if x != "work"]
        for f in fs:
            p = os.path.join(r, f)
            with open(p, "rb") as fh:
                out[os.path.relpath(p, d)] = hashlib.sha256(fh.read()).hexdigest()
    return out


def main():
    t0 = time.time()
    tmp = tempfile.mkdtemp(prefix="eqn-script-")
    old_verbose = eqn.verbose()
    eqn.verbose(0)
    try:
        return _main(tmp, t0)
    finally:
        eqn.verbose(old_verbose)
        shutil.rmtree(tmp, ignore_errors=True)


def _main(tmp, t0):
    p, d = new_project(tmp, "prj")

    # -----------------------------------------------------------------------
    print("\n== A. 문법 ==")
    check("A1 줄 끝 주석 · 따옴표 안의 # · an:x#2", strip_comment("hs main   # 과거 재현") == "hs main"
          and strip_comment('report new r --title "a # b"') == 'report new r --title "a # b"'
          and strip_comment("report add r an:unitroot_0001#2") == "report add r an:unitroot_0001#2")
    write(os.path.join(d, "FLOWS", "a.eqs"), "# 제목 줄\n# 둘째 주석\nparam xs = base oil20   # 목록\nparam one = 7\n\n"
          "## 자료\nequion assemble main\n## 과거 재현\nhs main --range 2010Q1:last\nexpect hs Y.rmspe < 9% --flag\n"
          "sim {xs}\n")
    sc = parse(d, "FLOWS/a.eqs")
    check("A2 제목·param(목록)·## 묶음·앞의 equion", sc.ok and sc.title == "제목 줄" and sc.params == {"xs": ["base", "oil20"], "one": ["7"]}
          and [s.kind for s in sc.steps] == ["cmd", "cmd", "expect", "cmd"] and sc.steps[0].text == "assemble main"
          and [s.section for s in sc.steps] == ["자료", "과거 재현", "과거 재현", "과거 재현"] and [s.n for s in sc.steps] == [1, 2, 3, 4],
          str(sc.problems))
    write(os.path.join(d, "FLOWS", "bad.eqs"), "param vintage = x\nparam a = 1\nparam a = 2\nparam b\nwork clean\nhistory revert h0001\n"
          "new x\nrun scripts/x.py\nfrobnicate 1\nassemble {nope}\nreport add r {hs}\nsim {a:b}\nexpect foo x < 1\nexpect hs Y.rmspe ~ 1\n"
          "run FLOWS/none.eqs\npy scripts/none.py\n")
    sc = parse(d, "FLOWS/bad.eqs")
    pr = "\n".join(sc.problems)
    check("A3 문제를 모은다(내장 이름·두 번·꼴·허용 목록·모르는 명령·{이름}·expect·없는 파일)",
          all(x in pr for x in ("내장 이름", "두 번", "'param 이름 = 값", "work clean", "history revert", "new x",
                                "Python은 'py", "모르는 명령 'frobnicate'", "모르는 이름 {nope}", "{hs} — 앞 단계에",
                                "{a:b}", "expect 대상은", "조건을 읽을 수 없습니다", "포함할 스크립트가 없습니다", "Python 스크립트가 없습니다"))
          and len(sc.problems) == 15 and all(re.match(r"^FLOWS/bad\.eqs:\d+: ", x) for x in sc.problems), f"{len(sc.problems)}개")
    write(os.path.join(d, "FLOWS", "inc1.eqs"), "param s = base\n## 자료\nassemble main\nrun FLOWS/inc2.eqs\n")
    write(os.path.join(d, "FLOWS", "inc2.eqs"), "param s = oil20\nparam t = 1\nhs main --range 2010Q1:last\n")
    sc = parse(d, "FLOWS/inc1.eqs")
    check("A4 run 포함 — 그 자리에 펼친다 · param은 먼저 적은 것", sc.ok and [s.text for s in sc.steps] == ["assemble main", "hs main --range 2010Q1:last"]
          and sc.params == {"s": ["base"], "t": ["1"]} and sc.files == ["FLOWS/inc1.eqs", "FLOWS/inc2.eqs"]
          and sc.steps[1].where == "FLOWS/inc2.eqs:3" and sc.steps[1].section == "자료")
    write(os.path.join(d, "FLOWS", "loop1.eqs"), "run FLOWS/loop2.eqs\n")
    write(os.path.join(d, "FLOWS", "loop2.eqs"), "run FLOWS/loop1.eqs\n")
    check("A5 돌고 도는 포함", any("돌고 돕니다" in x for x in parse(d, "FLOWS/loop1.eqs").problems))

    # -----------------------------------------------------------------------
    print("\n== B. 값 바꿔 넣기 ==")
    v = {"xs": ["base", "oil20"], "t": "월간 전망", "k": ["a b"], "vintage": "d2026-11a"}
    check("B1 목록은 띄어 쓰고 빈칸 든 값만 따옴표", resolve("sim {xs}", v) == "sim base oil20"
          and resolve("x {k}", v) == "x 'a b'" and resolve("r_{vintage}.md", v) == "r_d2026-11a.md")
    check("B2 {{ }}는 글자 그대로 · keep은 그대로 둔다", resolve("a {{x}} b", v) == "a {x} b"
          and resolve("r {vintage} {hs}", v, keep={"vintage", "hs"}) == "r {vintage} {hs}")
    check("B3 모르는 이름은 오류", raises(lambda: resolve("{zz}", v), ScriptError, "모르는 이름"))
    check("B4 기록 이름은 refs가", resolve("report add r {sim:base}", v, refs=lambda k, f: [f"{k}:x_{f}"]) == "report add r sim:x_base")

    # -----------------------------------------------------------------------
    print("\n== C. 등록부(허용 목록·바꾸는 파일) ==")
    check("C1 노트는 계산·보기만 — est --adopt·an keep·data build는 안 된다",
          reg.allowed(["est", "demand:CN"]) is None and reg.allowed(["hs", "main"]) is None
          and "정의 파일을 바꿉니다" in (reg.allowed(["est", "main", "--adopted", "--adopt", "if_pass"]) or "")
          and "정의 파일을 바꿉니다" in (reg.allowed(["an", "keep", "an:x"]) or "")
          and "노트에서 부를 수 없습니다" in (reg.allowed(["data", "build"]) or ""))
    check("C2 스크립트는 자료 만들기·채택·노트·보고서·내보내기까지", all(reg.allowed(t, "script") is None for t in (
        ["data", "build", "--use"], ["adopt", "demand:CN", "est:x"], ["note", "run", "n.md"], ["report", "update", "r"],
        ["export", "hs:x", "--xlsx", "a.xlsx"], ["est", "main", "--adopted", "--adopt", "if_pass"])))
    check("C3 스크립트도 정리·되돌리기·새 프로젝트는 안 된다", all(reg.allowed(t, "script") for t in (
        ["work", "clean"], ["history", "revert", "h1"], ["new", "x"], ["convert", "a", "b"], ["propose", "apply", "p1"])))
    check("C4 effects — 바꾸는 파일", reg.effects(["data", "build", "--inbox", "ask", "--use"]) ==
          ["DATA/raw/(받은 원자료)", "DATA/series.toml", "equion.toml [data] vintage"]
          and reg.effects(["est", "main", "--adopted"]) == [] and reg.effects(["est", "--adopt", "if_pass"]) == ["EQUATIONS/adopted.toml"]
          and reg.effects(["report", "update", "r.md", "--dry-run"]) == [] and reg.effects(["report", "add", "r.md", "sim:x"]) == ["r.md"]
          and reg.effects(["hs", "main"]) == [])

    # -----------------------------------------------------------------------
    print("\n== D. 받은 원자료 ==")
    q, dq = new_project(tmp, "inbox")
    check("D1 받은 상자가 비면 아무것도 없다", quiet(q.data_inbox) == [] and os.path.isdir(os.path.join(dq, "DATA", "raw", "inbox")))
    revised_toy_q(dq)
    items = quiet(q.data_inbox)
    check("D2 이름으로 짝짓기 + 틀 검사", [(x.source, x.status) for x in items] == [("na", "ready")] and "toy_q.csv" in items[0].how)
    write(os.path.join(dq, "DATA", "raw", "inbox", "mystery.csv"), "period,X\n2000Q1,1\n")
    code, out, _ = run(["data", "inbox", "-p", dq])
    check("D3 짝 없음 → data inbox 종료 코드 3, 까닭", code == 3 and "짝지을 출처가 없습니다" in out and "inbox = " in out)
    v0 = q.vintage
    raw0 = sorted(os.listdir(os.path.join(dq, "DATA", "raw")))
    check("D4 하나라도 문제면 아무것도 넣지 않는다(회차도)", raises(lambda: q.data_build(use=True, inbox="auto"), ProjectError, "아무것도 넣지 않음")
          and sorted(os.listdir(os.path.join(dq, "DATA", "raw"))) == raw0 and quiet(Project.open, dq).vintage == v0)
    os.remove(os.path.join(dq, "DATA", "raw", "inbox", "mystery.csv"))
    revised_toy_q(dq, "toy_q_bad.csv", drop="CN")
    items = quiet(q.data_inbox)
    check("D5 틀이 맞지 않음(쓰는 열이 없음)", [x.status for x in items] == ["ready", "bad"] and "CN" in " ".join(items[1].problems))
    os.remove(os.path.join(dq, "DATA", "raw", "inbox", "toy_q_bad.csv"))
    res = quiet(q.data_build, use=True, inbox="auto", who="terminal", command="equion data build --inbox auto --use")
    q = quiet(Project.open, dq)
    st = read(os.path.join(dq, "DATA", "series.toml"))
    check("D6 넣기 — DATA/raw/에 복사·출처가 그 파일을·받은 상자 비움·새 회차", res.created and res.inbox[0].status == "taken"
          and res.inbox[0].to == "DATA/raw/toy_q_2020Q1.csv" and 'file = "DATA/raw/toy_q_2020Q1.csv"' in st
          and os.listdir(os.path.join(dq, "DATA", "raw", "inbox")) == [] and q.vintage == res.id != v0
          and q.span("last:last")[1] == "2020Q1")
    chs = q.history.list()
    check("D7 바뀜 기록 — series.toml·equion.toml", any("DATA/series.toml" in c.files for c in chs)
          and any("equion.toml" in c.files for c in chs))
    write(os.path.join(dq, "DATA", "series.toml"), st.replace('[source.monthly]', '[source.monthly]\ninbox = "ind_*.csv"'))
    shutil.copy(os.path.join(dq, "DATA", "raw", "toy_m.csv"), os.path.join(dq, "DATA", "raw", "inbox", "ind_2026.csv"))
    check("D8 inbox 글롭으로 짝짓기", [(x.source, x.status) for x in quiet(q.data_inbox)] == [("monthly", "ready")])
    r2 = quiet(q.data_build, inbox="auto")
    check("D9 같은 내용의 파일이 이미 있으면 그 파일 · 회차 그대로", r2.inbox[0].status == "same" and not r2.created
          and r2.inbox[0].to == "DATA/raw/toy_m.csv")
    revised_toy_q(dq, "toy_q_x.csv")
    code, out, _ = run(["data", "build", "-p", dq])
    check("D10 --inbox 없이 만들면 받은 상자에 남은 파일을 알린다", code == 0 and "받은 상자(DATA/raw/inbox/)에 파일 1개" in out)
    os.remove(os.path.join(dq, "DATA", "raw", "inbox", "toy_q_x.csv"))

    # -----------------------------------------------------------------------
    print("\n== E. 실행 ==")
    lines = []
    r = quiet(p.run_script, "FLOWS/monthly.eqs", sets={"scenarios": "base"}, who="terminal",
              command="equion run FLOWS/monthly.eqs --set scenarios=base", echo=lines.append)
    rec = p.work.get(r.id)
    check("E1 단계 11 · 끝까지 · 종료 코드 0", r.exit_code == 0 and len(r.steps) == 11 and r.id == "run:monthly_0001"
          and all(s.status in ("ok", "flag") for s in r.steps) and len(lines) == 11 and lines[0].startswith("[1/11] data build"),
          str([(s.n, s.status, s.detail) for s in r.steps if s.status not in ("ok", "flag")]))
    check("E2 --set이 {scenarios}에 — 기준선만", r.steps[5].line == "sim base --model main"
          and [x for x in r.steps[5].records] == [x for x in r.steps[5].records if x.endswith("_base")])
    files = sorted(os.listdir(rec.path))
    check("E3 실행 기록 — record.json·script.eqs·src/·defs/·steps/·summary.md", files == ["defs", "record.json", "script.eqs", "src", "steps",
                                                                                         "summary.md"]
          and os.path.isfile(rec.file("src/FLOWS/monthly.eqs")) and os.path.isfile(rec.file("defs/equion.toml"))
          and os.path.isfile(rec.file("defs/EQUATIONS/demand.txt")) and os.path.isfile(rec.file("steps/04.txt")))
    se = read(rec.file("script.eqs"))
    check("E4 script.eqs = 값을 바꿔 넣은 뒤(기록 이름까지)", "sim base --model main" in se and "{" not in se.split("\n", 4)[-1]
          and re.search(r"report add reports/forecast_d\d{4}-\d\d\w\.md sim:\S+_base --key growth", se) is not None
          and "# param scenarios = base" in se)
    m = rec.meta
    hs_id = r.steps[3].records[0]
    hrec = p.work.get(hs_id)
    check("E5 단계의 기록 — 누가 '스크립트' · run = 이 실행 · log에도", hrec.meta["who"] == "script" and hrec.meta["run"] == r.id
          and hrec.meta["command"] == "equion hs main" and any(x.get("run") == r.id for x in p.work.log() if x["id"] == hs_id))
    chs = [c for c in p.history.list() if c.run == r.id]
    check("E6 바뀜 기록에도 이 실행(채택표·노트·보고서)", {f for c in chs for f in c.files} >=
          {"EQUATIONS/adopted.toml", "notes/data_check.md"} and all(c.who == "script" for c in chs))
    check("E7 record.json — 매개변수·자료 회차·판·상태·만든 기록", m["params"] == {"scenarios": ["base"]} and m["status"] in ("ok", "flag")
          and m["vintage"]["start"] == m["vintage"]["end"] == p.vintage and m["versions"]["equion"] == eqn.__version__
          and hs_id in m["records"] and m["origin"] == "eqs" and m["who"] == "terminal")
    sm = rec.summary_md()
    check("E8 카드 — 단계 표·이 결과를 만든 스크립트", "## 단계" in sm and "## 이 결과를 만든 스크립트" in sm and "`hs main`" in sm
          and "```" not in sm)
    est_flag = r.steps[2]
    check("E9 기준 미달 식은 ! 로 표시하고 계속", est_flag.status == "flag" and "기준 미달" in est_flag.detail)
    r2 = quiet(p.run_script, "FLOWS/monthly.eqs", sets={"scenarios": "base"}, from_step="과거 재현")
    check("E10 --from 제목 — 앞 단계 건너뜀 · 건너뛴 단계의 기록은 가장 새 기록", r2.exit_code == 0
          and [s.status for s in r2.steps[:3]] == ["skip"] * 3 and r2.steps[3].status == "ok"
          and r2.id == "run:monthly_0002")
    check("E11 모르는 --set은 실행하지 않는다", raises(lambda: p.run_script("FLOWS/monthly.eqs", sets={"nope": "1"}), ScriptError, "모르는 매개변수")
          and len(p.work.records("run")) == 2)

    # -----------------------------------------------------------------------
    print("\n== F. 확인(expect) ==")
    write(os.path.join(d, "FLOWS", "x1.eqs"), "hs main --range 2010Q1:last\nexpect hs Y.rmspe < 0.0001% --flag\n"
          "expect hs failed == 0\nsim\nexpect sim Y.growth[2020] > -50\nexpect sim Y.level[2021Q4] > 0\n")
    r = quiet(p.run_script, "FLOWS/x1.eqs")
    check("F1 --flag는 표시하고 계속 · 종료 코드 0", r.exit_code == 0 and [s.status for s in r.steps] == ["ok", "flag", "ok", "ok", "ok", "ok"]
          and "어긋남" in r.steps[1].detail and r.status == "flag")
    write(os.path.join(d, "FLOWS", "x2.eqs"), "hs main --range 2010Q1:last\nexpect hs Y.rmspe < 0.0001%\nsim\n")
    r = quiet(p.run_script, "FLOWS/x2.eqs")
    check("F2 --stop(기본)은 멈춘다 — 종료 코드 2, 뒤 단계 안 함", r.exit_code == 2 and [s.status for s in r.steps] == ["ok", "stop"]
          and r.status == "stop")
    write(os.path.join(d, "FLOWS", "x3.eqs"), "hs main --range 2010Q1:last\nexpect hs ZZ.rmspe < 1\n")
    r = quiet(p.run_script, "FLOWS/x3.eqs")
    check("F3 없는 변수의 지표는 스크립트 오류(1)", r.exit_code == 1 and r.steps[1].status == "error" and "ZZ" in r.steps[1].detail)
    write(os.path.join(d, "FLOWS", "x4.eqs"), "est demand:CN\nexpect est r2 > 0.5\nexpect est n == 1\nexpect est dw > 0\n")
    r = quiet(p.run_script, "FLOWS/x4.eqs")
    check("F4 추정 지표(r2·n·dw) — 기준 미달 식은 추정 단계에 !", r.exit_code == 0 and r.steps[0].status in ("ok", "flag")
          and all(s.status == "ok" for s in r.steps[1:]), str([s.detail for s in r.steps]))

    # -----------------------------------------------------------------------
    print("\n== G. 실패·Python 단계 ==")
    write(os.path.join(d, "FLOWS", "g1.eqs"), "assemble main\nhs nosuch\nsim\n")
    r = quiet(p.run_script, "FLOWS/g1.eqs")
    check("G1 단계가 실패하면 멈춘다 — 그 종료 코드(3)", r.exit_code == 3 and [s.status for s in r.steps] == ["ok", "error"]
          and "nosuch" in r.steps[1].detail and p.work.get(r.id).meta["status"] == "error")
    write(os.path.join(d, "scripts", "extra.py"), "import equion as eqn\np = eqn.project('.')\nr = p.est('demand:I')\n"
          "print('추정', r.id)\n")
    write(os.path.join(d, "FLOWS", "g2.eqs"), "py scripts/extra.py\n")
    r = quiet(p.run_script, "FLOWS/g2.eqs")
    est_i = r.steps[0].records
    check("G2 Python 단계 — 그 기록이 단계의 기록 · 누가 '스크립트' · run", r.exit_code == 0 and len(est_i) == 1
          and p.work.get(est_i[0]).meta["who"] == "script" and p.work.get(est_i[0]).meta["run"] == r.id, r.steps[0].detail)
    r = quiet(p.run_script, "FLOWS/g2.eqs", python=False)
    check("G3 python=False(Desk 앱)면 Python 단계는 허용 안 됨(3)", r.exit_code == 3 and r.steps[0].status == "denied"
          and "터미널에 붙여 넣어" in r.steps[0].detail)

    # -----------------------------------------------------------------------
    print("\n== H. 미리보기·검사 ==")
    n_log = len(p.work.log())
    pl = quiet(p.run_script, "FLOWS/monthly.eqs", dry_run=True)
    st = {s["n"]: s for s in pl.steps}
    check("H1 미리보기는 기록을 남기지 않는다", pl.ok and len(p.work.log()) == n_log and "기록을 남기지 않습니다" in pl.text())
    check("H2 회차를 바꾸는 단계 뒤의 {vintage}·기록 이름은 '실행 때 정해짐'", st[8]["later"] == ["{vintage}"]
          and st[9]["later"] == ["{sim:base}", "{vintage}"] and "{sim:base}" in st[9]["line"] and st[6]["line"] == "sim base oil20 --model main")
    check("H3 바꾸는 파일", st[1]["effects"][-1] == "equion.toml [data] vintage" and st[3]["effects"] == ["EQUATIONS/adopted.toml"]
          and st[4]["effects"] == [] and st[7]["effects"] == ["notes/data_check.md"])
    write(os.path.join(d, "FLOWS", "h.eqs"), "hs main --nonsense\nhs nomodel\nsim zz9 --model main\nnote run notes/none.md\n"
          "est demand:ZZ\nreport new r --from reports/none.md\nassemble main\n")
    c = quiet(p.check_script, "FLOWS/h.eqs")
    pr = "\n".join(c.problems)
    check("H4 검사 — 선택지·모형·시나리오·노트·부품·보고서", not c.ok and len(c.problems) == 6
          and all(x in pr for x in ("--nonsense", "nomodel", "zz9", "notes/none.md", "ZZ", "reports/none.md")), pr)
    check("H5 예제 스크립트는 문제 없음", quiet(p.check_script, "FLOWS/monthly.eqs").ok
          and quiet(p.check_script, "FLOWS/monthly.eqs", sets={"scenarios": "base zz"}).problems[0].endswith("(SCENARIOS/zz.toml)"))

    # -----------------------------------------------------------------------
    print("\n== I. 재연 ==")
    first = "run:monthly_0001"
    before = hashes(d)
    n_runs = len(p.work.records("run"))
    rp = quiet(p.replay_run, first)
    check("I1 그때 그대로 — 단계마다 같음", rp.same and rp.exit_code == 0 and len(rp.steps) == 11
          and all(s["verdict"] == "같음" for s in rp.steps), str([s for s in rp.steps if s["verdict"] != "같음"][:2]))
    check("I2 프로젝트는 그대로 · 새 실행 기록(replay_of)", hashes(d) == before and len(p.work.records("run")) == n_runs + 1
          and p.work.get(rp.id).meta["replay_of"] == first)
    demand = os.path.join(d, "EQUATIONS", "demand.txt")
    demand0 = read(demand)
    write(demand, demand0.replace("I c Y(-1) R", "I c Y R"))
    rp2 = quiet(p.replay_run, first)
    check("I3 정의를 바꾼 뒤에도 그때의 정의 사본으로 — 같음", rp2.same, str([s for s in rp2.steps if s["verdict"] != "같음"][:2]))
    check("I4 재연 기록은 다시 재연하지 않는다", raises(lambda: p.replay_run(rp.id), ScriptError, "재연 기록"))
    hs_now = quiet(quiet(Project.open, d).hs, "main", record=True)
    check("I5 정의가 바뀐 지금 다시 풀면 숫자가 다르다(비교 함수가 다름을 잡는다)",
          compare_records(p.work.get(hs_id), p.work.get(hs_now.id)) != [])
    write(demand, demand0)
    quiet(p.history.scan)

    # -----------------------------------------------------------------------
    print("\n== J. 초안·Python으로 ==")
    e1 = quiet(p.est, "demand:CN", as_name="cj1", command="equion est demand:CN -p prj --as cj1 --json")
    h1 = quiet(p.hs, "core", record=True, command="equion hs core --range 2010Q1:last -p prj")
    rel = quiet(p.new_script, "mine", records=[e1.id, h1.id])
    tx = read(os.path.join(d, rel))
    check("J1 script new — 기록의 명령(--as·-p·--json 뺌)·종류마다 제목", rel == "FLOWS/mine.eqs"
          and "est demand:CN   # ← est:cj1" in tx and "hs core --range 2010Q1:last   # ← " + h1.id in tx
          and "## 추정" in tx and "## 과거 재현" in tx and parse(d, rel).ok)
    check("J2 이미 있으면 --force 없이 안 쓴다 · --last", raises(lambda: p.new_script("mine"), ScriptError, "이미 있는 스크립트")
          and "hs core" in read(os.path.join(d, quiet(p.new_script, "last2", last=2))))
    check("J3 바뀜 기록에 남는다(FLOWS/*.eqs)", any("FLOWS/mine.eqs" in c.files for c in p.history.list()))
    write(os.path.join(d, "FLOWS", "px.eqs"), "# 작은 흐름\nparam sc = base\n## 과거 재현\nhs main --range 2010Q1:last\n"
          "expect hs Y.rmspe < 50% --flag\n## 전망\nsim {sc}\n")
    pyrel = quiet(p.export_script, "FLOWS/px.eqs")
    pysrc = read(os.path.join(d, pyrel))
    check("J4 export --py — eqn.script.session · 같은 줄", pyrel == "FLOWS/px.py" and "eqn.script.session(__file__" in pysrc
          and "s.cmd('hs main --range 2010Q1:last')" in pysrc and "s.expect_line('expect hs Y.rmspe < 50% --flag')" in pysrc
          and "P = eqn.params(sc='base')" in pysrc)
    r_eqs = quiet(p.run_script, "FLOWS/px.eqs")
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    pr_ = subprocess.run([sys.executable, pyrel], cwd=d, capture_output=True, text=True, encoding="utf-8", env=env)
    runs = p.work.records("run")
    py_run = runs[-1]
    same = (pr_.returncode == 0 and py_run.meta["origin"] == "python" and
            compare_records(p.work.get(r_eqs.steps[0].records[0]), p.work.get(py_run.meta["steps"][0]["records"][0])) == []
            and compare_records(p.work.get(r_eqs.steps[2].records[0]), p.work.get(py_run.meta["steps"][2]["records"][0])) == [])
    check("J5 내보낸 Python을 돌리면 같은 숫자 · 실행 기록(origin python)", same, (pr_.stdout + pr_.stderr)[-300:])
    check("J6 Python에서 연 실행은 재연하지 않는다", raises(lambda: p.replay_run(py_run.id), ScriptError, "Python에서"))
    check("J7 있으면 --force 없이 안 쓴다", raises(lambda: p.export_script("FLOWS/px.eqs"), ScriptError, "이미 있는 파일"))

    # -----------------------------------------------------------------------
    print("\n== K. 명령줄 ==")
    code, out, err = run(["run", "FLOWS/x2.eqs"], d)
    check("K1 run x.eqs — 단계 줄과 끝 줄 · expect --stop이면 2", code == 2 and "[1/3] hs main" in out and "[2/3] expect" in out
          and "종료 코드 2" in err)
    code, out, _ = run(["run", "FLOWS/px.eqs", "--dry-run", "--json"], d)
    check("K2 --dry-run --json", code == 0 and json.loads(out)["steps"][2]["line"] == "sim base")
    code, out, _ = run(["run", "FLOWS/px.eqs", "--set", "sc=oil20", "-q", "--json"], d)
    j = json.loads(out)
    check("K3 --set · -q · --json", code == 0 and j["steps"][2]["line"] == "sim oil20" and j["exit_code"] == 0)
    code, out, err = run(["run", "FLOWS/bad.eqs"], d)
    check("K4 문제가 있는 스크립트는 실행하지 않는다(3)", code == 3 and "실행하지 않았습니다" in err)
    code, out, err = run(["run", "FLOWS/px.eqs", "--watch"], d)
    code2, _, err2 = run(["run", "x.py", "--from", "2"], d)
    code3, _, err3 = run(["run"], d)
    check("K5 .eqs에 .py 선택지 · .py에 --from · 스크립트 없음 → 3", (code, code2, code3) == (3, 3, 3) and "--watch" in err
          and "--from" in err2 and "--replay" in err3)
    code, out, _ = run(["check", "FLOWS/monthly.eqs"], d)
    code2, out2, _ = run(["check", "FLOWS/h.eqs", "--json"], d)
    check("K6 check x.eqs — 0 · 문제면 3", code == 0 and "문제 없음" in out and code2 == 3 and len(json.loads(out2)["problems"]) == 6)
    code, out, _ = run(["run", "--replay", "run:x1_0001", "-p", d])
    check("K7 run --replay", code == 0 and "모두 같음" in out)
    code, out, _ = run(["script", "new", "cli1", "--from-records", e1.id], d)
    code2, out2, _ = run(["script", "export", "FLOWS/cli1.eqs", "--py", "--json"], d)
    check("K8 script new · export --py", code == 0 and "FLOWS/cli1.eqs" in out and code2 == 0 and json.loads(out2)["py"] == "FLOWS/cli1.py")
    code, _, err = run(["script", "new", "cli1"], d)
    check("K9 이미 있는 스크립트 → 3", code == 3 and "이미 있는 스크립트" in err)

    # -----------------------------------------------------------------------
    print("\n== L. 완료 기준 — 원자료 교체 → 스크립트 한 번 → 보고서 · 재연 ==")
    w, dw = new_project(tmp, "monthly")
    v0 = w.vintage
    revised_toy_q(dw)
    code, out, err = run(["run", "FLOWS/monthly.eqs"], dw)
    w = quiet(Project.open, dw)
    runs = w.work.records("run")
    m = runs[-1].meta
    rep = os.path.join(dw, "reports", f"forecast_{w.vintage}.md")
    check("L1 원자료 교체 → 새 회차 · 끝까지", code == 0 and w.vintage != v0 and m["vintage"] == {"start": v0, "end": w.vintage}
          and m["inbox"][0]["from"] == "toy_q_2020Q1.csv" and w.span("last:last")[1] == "2020Q1", err[-300:])
    rt = read(rep) if os.path.isfile(rep) else ""
    sim_base = [x for x in m["records"] if re.match(r"^sim:.*_base(_\d+)?$", x)][0]
    check("L2 보고서까지 — 구역 2(전망·과거 재현)·이번 회차·차트 자료 · 엑셀", rt.count("<!-- equion:report ") == 2
          and f"<!-- equion:report {sim_base} " in rt and f"자료 회차 {w.vintage}" in rt
          and os.path.isdir(os.path.join(dw, "reports", f"forecast_{w.vintage}_data"))
          and os.path.isfile(os.path.join(dw, "exports", f"forecast_{w.vintage}.xlsx")))
    write(rep, rt.replace("(글)", "이번 달은 소비가 이끈다."))
    code, out, err = run(["run", "FLOWS/monthly.eqs", "-q"], dw)
    rt2 = read(rep)
    w = quiet(Project.open, dw)
    m2 = w.work.records("run")[-1].meta
    sim2 = [x for x in m2["records"] if re.match(r"^sim:.*_base(_\d+)?$", x)][0]
    check("L3 같은 회차로 다시 — 글은 남고 구역은 그 자리에서 새 기록으로", code == 0 and "이번 달은 소비가 이끈다." in rt2
          and rt2.count("<!-- equion:report ") == 2 and f"<!-- equion:report {sim2} " in rt2 and sim2 != sim_base)
    first = runs[-1].id
    code, out, err = run(["run", "--replay", first, "-p", dw])
    check("L4 replay가 같은 결과(원자료 교체까지 그때 그대로)", code == 0 and "모두 같음" in out
          and "data:" in out, (out + err)[-600:])
    reg_md = "\n".join(x for x in rt2.split("\n") if x.startswith("<!-- equion:report"))
    write(rep, rt2.replace("| Y |", "| Y(고침) |", 1))
    code, out, err = run(["run", "FLOWS/monthly.eqs", "-q"], dw)
    check("L5 손으로 고친 구역은 덮지 않고 멈춘다(3) — 고친 곳과 함께", code == 3 and "손으로 고쳤습니다" in err
          and "Y(고침)" in read(rep) and bool(reg_md))

    print()
    print(f"결과: {len(PASS)}/{len(PASS) + len(FAIL)} 통과 ({time.time() - t0:.1f}초)")
    if FAIL:
        print("실패:", ", ".join(FAIL))
    return len(FAIL)


def test_suite():
    """pytest 진입점 — 이 파일의 검사 묶음 전체(하나라도 실패하면 실패). `python tests/test_script.py`와 같은 검사."""
    assert main() == 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(99)
