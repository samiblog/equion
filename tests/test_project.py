#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_project.py — 프로젝트(부품·조립 층, D32 — 개발 계획 E1) 테스트.

실행: uv run python tests/test_project.py   (종료코드 = 실패 수)

  A. 설정: 예제 프로젝트 만들기·열기, equion.toml 문제(모아서 알림)
  B. 부품: 블록 파일의 줄 → 부품(목표·종류·위치·설명), @def, 블록 안 목표 겹침, 문법 오류 위치
  C. 조립: 내생·외생·조립 글·연결·풀이 블록, exclude, 블록 하나, 겹친 목표·모르는 변수·외생 자료 끝, 쓰는 곳, 바꿔 끼우기
  D. 모형·HS: 워크파일 API로 직접 만든 모형과 같은 해, 블록 HS, 추정 재사용, 바꿔 끼운 HS
  E. 항등식 검사: 성립·어긋남·구간·추정식 거부
  F. 명령줄: new --template desk · assemble · ident
  G. 자료 정의·회차(D34, E2): 불러오기 틀(엑셀 머리줄·단위줄·시점 꼴·결측 표시·천 단위·괄호 음수·cp949), 정의 문제(모아서),
     만들기(값의 종류·주기 변환·배율·채움·계절조정·파생), 같은 내용, 이 회차로 바꾸기(주석 유지), 차이·영향, 원자료 넣기(틀 검사)
  H. 상대 기간(last·last-N·next:N)과 자료 회차 명령줄(equion data list·add·build·use·diff·impact)
자료는 예제 자료 toy_q·toy_m(예제 프로젝트의 DATA/raw/)과 코드로 만든 합성 표만 쓴다.
"""

import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import time
import traceback

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import equion as eqn  # noqa: E402
from equion.cli import main as cli  # noqa: E402
from equion.projects import Project, ProjectError  # noqa: E402

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  — {detail}" if detail else ""))


def quiet(fn, *a, **k):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a, **k)


def raises(fn, exc=Exception, contains=None):
    try:
        quiet(fn)
    except exc as e:
        return contains is None or contains in str(e)
    return False


def write(path, text, mode="w"):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, mode, encoding="utf-8", newline="\n") as f:
        f.write(text)
    return path


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def run(args, where=None):
    """CLI를 같은 프로세스에서 실행 → (종료 코드, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    old = os.getcwd()
    os.chdir(where or old)
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli(list(args))
    finally:
        os.chdir(old)
    return code, out.getvalue(), err.getvalue()


def new_project(base, name="demo"):
    d = os.path.join(base, name)
    return quiet(Project.create, d), d


def config_problem(base, name, toml, files=None):
    """equion.toml(과 파일들)을 쓰고 열어 ProjectError 메시지를 돌려준다(문제 없으면 None)."""
    d = os.path.join(base, name)
    os.makedirs(d, exist_ok=True)
    shutil.copyfile(eqn.datasets.path("toy_q"), os.path.join(d, "data.csv"))
    for rel, text in (files or {}).items():
        write(os.path.join(d, rel), text)
    write(os.path.join(d, "equion.toml"), toml)
    try:
        quiet(Project.open, d)
    except ProjectError as e:
        return e
    return None


def main():
    t0 = time.time()
    tmp = tempfile.mkdtemp(prefix="eqn-prj-")
    old_verbose = eqn.verbose()
    eqn.verbose(0)
    try:
        return _main(tmp, t0)
    finally:
        eqn.verbose(old_verbose)
        shutil.rmtree(tmp, ignore_errors=True)


def _main(tmp, t0):
    print("=" * 80)
    print("A. 설정")
    print("=" * 80)
    p, d = new_project(tmp)
    files = ["equion.toml", "DATA/series.toml", "DATA/derived.txt", "DATA/raw/toy_q.csv", "DATA/raw/toy_m.csv",
             "EQUATIONS/demand.txt", "EQUATIONS/price.txt", "EQUATIONS/finance.txt", "ADDFACTORS/base.toml",
             "SCENARIOS/oil20.toml", "ASSUMPTIONS/base.csv", "README.md", ".gitignore"]
    check("만들기: 예제 프로젝트 파일", all(os.path.isfile(os.path.join(d, f)) for f in files)
          and sorted(p.created_files) == sorted(files))
    check("만들기: 첫 자료 회차를 지금 회차로", p.vintage is not None and len(p.data_list()) == 1
          and os.path.isfile(os.path.join(d, "work", "data", p.vintage, "series.csv")), str(p.vintage))
    check("열기: 이름·블록·모형", p.name == "demo" and p.blocks == ["demand", "price", "finance"]
          and p.models == ["core", "main", "main_fixrl"], repr(p))
    check("eqn.project = Project.open", quiet(eqn.project, d).models == p.models)
    check("열기: equion.toml 경로도 받는다", quiet(eqn.project, os.path.join(d, "equion.toml")).name == "demo")
    check("만들기: 비어 있지 않은 폴더 거부", raises(lambda: Project.create(d), FileExistsError, "--force"))
    check("만들기: 모르는 template", raises(lambda: Project.create(os.path.join(tmp, "x"), template="nope"), ValueError))
    check("설정 없음", raises(lambda: Project.open(tmp), ProjectError, "설정 파일이 없습니다"))

    base_ok = '[data]\nfile = "data.csv"\n[block]\nb = "b.txt"\n[model.m]\nblocks = ["b"]\n'
    bfile = {"b.txt": "CN c Y CN(-1)\nI c Y(-1) R\nY = CN + I + G\n"}
    check("설정: 최소 프로젝트는 열린다", config_problem(tmp, "ok", base_ok, bfile) is None)
    e = config_problem(tmp, "syntax", "[data\nfile = 1\n")
    check("설정: TOML 문법 오류", e is not None and "문법 오류" in str(e))
    e = config_problem(tmp, "nodata", '[block]\nb = "b.txt"\n', bfile)
    check("설정: [data] file 없음", e is not None and "[data] file이 없습니다" in str(e))
    e = config_problem(tmp, "badname", '[data]\nfile = "data.csv"\n[block]\n"수요" = "b.txt"\n', bfile)
    check("설정: 블록 이름은 영문", e is not None and "영문으로 시작" in str(e))
    e = config_problem(tmp, "nofile", '[data]\nfile = "data.csv"\n[block]\nb = "없음.txt"\n')
    check("설정: 없는 블록 파일", e is not None and "방정식 파일이 없습니다" in str(e))
    e = config_problem(tmp, "noblock", base_ok + '[model.n]\nblocks = ["zz"]\n', bfile)
    check("설정: 모형이 없는 블록을 가리킴", e is not None and "없는 블록 'zz'" in str(e))
    e = config_problem(tmp, "cycle", base_ok + '[model.a]\ninclude = ["c"]\n[model.c]\ninclude = ["a"]\n', bfile)
    check("설정: include 순환", e is not None and "돌고 돕니다" in str(e))
    e = config_problem(tmp, "excl", base_ok + '[model.n]\nblocks = ["b"]\nexclude = ["CN"]\n', bfile)
    check("설정: exclude는 블록:목표", e is not None and "블록:목표변수 꼴" in str(e))
    e = config_problem(tmp, "clash", base_ok + '[model.b]\nblocks = ["b"]\n', bfile)
    check("설정: 블록과 모형 이름 겹침", e is not None and "블록이자 모형" in str(e))
    e = config_problem(tmp, "ver", '[project]\nformat_version = 99\n' + base_ok, bfile)
    check("설정: 새 형식 판", e is not None and "형식 판 99" in str(e))
    e = config_problem(tmp, "many", '[block]\n"한" = "b.txt"\n[model.m]\nblocks = ["q"]\n', bfile)
    check("설정: 문제를 모아 한꺼번에", e is not None and len(e.problems) >= 3, str(len(e.problems) if e else 0))
    sfile = dict(bfile, **{"s.toml": ""})
    e = config_problem(tmp, "both", '[data]\nfile = "data.csv"\nseries = "s.toml"\nfreq = "Q"\n[block]\nb = "b.txt"\n', sfile)
    check("설정: [data] file과 series를 함께", e is not None and "함께 쓸 수 없습니다" in str(e))
    e = config_problem(tmp, "nofreq", '[data]\nseries = "s.toml"\n[block]\nb = "b.txt"\n', sfile)
    check("설정: series에는 freq", e is not None and "[data] freq가 없습니다" in str(e))
    e = config_problem(tmp, "badvid", '[data]\nseries = "s.toml"\nfreq = "Q"\nvintage = "v1"\n[block]\nb = "b.txt"\n', sfile)
    check("설정: 회차 이름 글자", e is not None and "회차 이름" in str(e))
    q = quiet(Project.open, os.path.join(tmp, "ok"))
    write(os.path.join(tmp, "ok", "equion.toml"), base_ok + "[weird]\nx = 1\n")
    q = quiet(Project.open, os.path.join(tmp, "ok"))
    check("설정: 모르는 표는 경고만", any("[weird]" in w for w in q.config.warnings))

    print("=" * 80)
    print("B. 부품")
    print("=" * 80)
    parts = p.parts("demand")
    check("부품: 이름·종류", [x.id for x in parts] == ["demand:CN", "demand:I", "demand:Y"]
          and [x.kind for x in parts] == ["equation", "equation", "identity"])
    y = p.part("DEMAND:y")
    check("부품: 위치·설명·글자", y.where == "EQUATIONS/demand.txt:4" and y.desc == "국민소득(항등식)"
          and y.text == "Y = CN + I + G", f"{y.where} {y.desc!r}")
    check("부품: 같은 기 변수", y.current == {"Y", "CN", "I", "G"})
    check("부품: 목표가 식의 좌변 첫 변수", p.part("price:P").text.startswith("dlog(P)")
          and p.part("finance:M2").kind == "equation")
    check("부품: 없는 부품", raises(lambda: p.part("demand:ZZ"), KeyError, "있는 부품"))
    check("부품: 전부", len(p.parts()) == 6)

    pm = os.path.join(tmp, "macro")
    shutil.copytree(d, pm)
    write(os.path.join(pm, "EQUATIONS", "demand.txt"),
          "@def RR = R - 0.1\nCN c Y CN(-1)\nI c Y(-1) RR   # 투자 — 실질금리 매크로\nY = CN + I + G\n")
    pq = quiet(Project.open, pm)
    ii = pq.part("demand:I")
    check("부품: @def 매크로를 펼친다", "RR" not in ii.expr and "R - 0.1" in ii.expr and ii.line == 3
          and ii.text == "I c Y(-1) RR", ii.expr)
    write(os.path.join(pm, "EQUATIONS", "demand.txt"),
          "CN c Y CN(-1)\nCN c Y\nI c Y(-1) R\nY = CN + I + G\nZ c Y(-1\n")
    pq = quiet(Project.open, pm)
    r = quiet(pq.assemble, "core")
    check("부품: 블록 안 목표 겹침은 위치와 함께", not r.ok and any("demand.txt:2" in x and "demand.txt:1" in x
                                                          for x in r.problems), "; ".join(r.problems)[:200])
    check("부품: 문법 오류는 파일:줄", any(x.startswith("EQUATIONS/demand.txt:5") for x in r.problems))
    write(os.path.join(pm, "EQUATIONS", "demand.txt"),
          "CN = c(1) + c(2)*Y + c(3)*CN(-1)   # NLS\nI c Y(-1) R\nY = CN + I + G\n")
    pq = quiet(Project.open, pm)
    check("부품: NLS 식", pq.part("demand:CN").kind == "equation" and quiet(pq.assemble, "core").ok)

    print("=" * 80)
    print("C. 조립")
    print("=" * 80)
    r = quiet(p.assemble, "main")
    check("조립: 문제 없음", r.ok and not r.problems, "; ".join(r.problems))
    check("조립: 내생·외생", r.endogenous == ["CN", "I", "Y", "P", "RL", "M2"] and r.exogenous == ["G", "POIL", "R"])
    check("조립: 조립 글", r.composition == "main = core(demand) + price + finance", r.composition)
    check("조립: 블록 사이 연결", ("demand", "Y", "price") in r.links and ("price", "P", "finance") in r.links)
    sim = [b for b in r.blocks if b["size"] > 1]
    check("조립: 풀이 블록(동시 CN·Y)", len(sim) == 1 and set(sim[0]["variables"]) == {"CN", "Y"}
          and sum(b["size"] for b in r.blocks) == 6)
    check("조립: 외생 자료 끝", r.exo_info["G"]["last"] == "2019Q4" and r.exo_info["R"]["first"] == "1970Q1")
    check("조립: 식 수", r.n_equations == 5 and r.n_identities == 1)
    txt = r.text()
    check("조립: 글", "문제   없음" in txt and "내생 6" in txt and "동시 CN·Y" in txt, txt.splitlines()[0])
    check("조립: JSON으로", json.loads(json.dumps(r.to_dict()))["ok"] is True)
    check("조립: 표", list(r.output().data.columns) == ["부품", "종류", "위치", "식", "설명"])
    rx = quiet(p.assemble, "main_fixrl")
    check("조립: exclude — 뺀 식의 목표는 외생", rx.ok and rx.excluded == ["finance:RL"] and "RL" in rx.exogenous
          and "RL" not in rx.endogenous)
    check("조립: 기본 모형은 [hs] model", quiet(p.assemble).model == "main")
    rb = quiet(p.assemble, "demand")
    check("조립: 블록 하나", rb.ok and rb.endogenous == ["CN", "I", "Y"] and rb.exogenous == ["G", "R"])
    check("조립: 없는 모형", raises(lambda: p.assemble("nope"), KeyError, "없는 모형"))
    check("쓰는 곳: 블록·부품", p.used_by("demand") == ["core", "main", "main_fixrl"]
          and p.used_by("finance:RL") == ["main"] and p.used_by("price") == ["main", "main_fixrl"])

    pb = os.path.join(tmp, "bad")
    shutil.copytree(d, pb)
    write(os.path.join(pb, "EQUATIONS", "extra.txt"), "CN c Y\nU c LF\n")
    write(os.path.join(pb, "equion.toml"), read(os.path.join(pb, "equion.toml"))
          + '\n[block.extra]\nfile = "EQUATIONS/extra.txt"\n[model.bad]\nblocks = ["demand", "extra"]\n'
          + '[model.bad2]\ninclude = ["core"]\nexclude = ["demand:ZZ"]\n')
    pr = quiet(Project.open, pb)
    r = quiet(pr.assemble, "bad")
    check("조립: 겹친 목표(두 파일의 위치)", any("목표 겹침 CN" in x and "demand.txt:2" in x and "extra.txt:1" in x
                                         for x in r.problems), "; ".join(r.problems)[:200])
    check("조립: 모르는 변수(쓰는 식)", any("모르는 변수 LF" in x and "extra:U" in x for x in r.problems))
    check("조립: 문제가 있으면 풀이 블록 없음", not r.ok and r.blocks == [])
    check("조립: 없는 식을 exclude", any("demand:ZZ" in x for x in quiet(pr.assemble, "bad2").problems))
    check("모형: 조립 문제면 ProjectError", raises(lambda: pr.model("bad"), ProjectError, "조립할 수 없습니다"))

    pe = os.path.join(tmp, "early")
    shutil.copytree(d, pe)
    df = pd.read_csv(os.path.join(pe, "DATA", "raw", "toy_q.csv"))
    df.loc[df.index[-4:], "POIL"] = np.nan
    df.to_csv(os.path.join(pe, "DATA", "raw", "toy_q.csv"), index=False)
    pq = quiet(Project.open, pe)
    quiet(pq.data_build, use=True)
    r = quiet(pq.assemble, "main")
    check("조립: 일찍 끝나는 외생은 주의", r.ok and any("POIL(~2018Q4)" in w for w in r.warnings), "; ".join(r.warnings))

    rs = quiet(p.assemble, "main", swap={"demand:CN": "CN c Y"})
    check("바꿔 끼우기: 조립", rs.ok and next(x for x in rs.parts if x.id == "demand:CN").text == "CN c Y")
    rs = quiet(p.assemble, "main", swap={"demand:CN": "I c Y"})
    check("바꿔 끼우기: 목표가 다르면 문제", not rs.ok and any("목표가 I" in x for x in rs.problems))
    rs = quiet(p.assemble, "main", swap={"demand:ZZ": "CN c Y"})
    check("바꿔 끼우기: 없는 식", not rs.ok and any("demand:ZZ" in x for x in rs.problems))

    print("=" * 80)
    print("D. 모형·HS")
    print("=" * 80)
    m = quiet(p.model, "main")
    check("모형: 워크파일 모델 객체", m.endogenous == sorted(["CN", "I", "Y", "P", "RL", "M2"])
          and len(m.equations) == 5 and m.identities == ["Y = CN + I + G"])
    check("모형: 지금 자료로 추정했다고 적는다", p.notes and all(k in p.notes[-1] for k in
                                                      ("demand:CN", "demand:I", "price:P", "finance:RL", "finance:M2")))
    n_notes = len(p.notes)
    quiet(p.model, "core")
    check("모형: 같은 식은 다시 추정하지 않는다", len(p.notes) == n_notes)
    r = quiet(p.hs, "main")
    check("HS: [hs]의 구간·방식", (r.start, r.end) == ("2005Q1", "2019Q4") and r.counts()["ok"] == 60)

    vcsv = os.path.join(d, "work", "data", p.vintage, "series.csv")
    wf = quiet(eqn.wfopen, vcsv, freq="Q")
    mm = quiet(lambda: wf.model("chk").merge("CN c Y CN(-1)", "I c Y(-1) R", "dlog(P) c dlog(Y) dlog(POIL)",
                                             "RL c R RL(-1)", "log(M2) c log(P) log(Y) RL log(M2(-1))")
               .append("Y = CN + I + G"))
    quiet(mm.solve, "2005Q1", "2019Q4")
    pw = p.workfile
    diffs = [float(np.nanmax(np.abs(pw[f"{v}_0"].to_numpy(dtype=float) - wf[f"{v}_0"].to_numpy(dtype=float))))
             for v in ("CN", "I", "Y", "P", "RL", "M2")]
    check("HS: 워크파일 API로 직접 만든 모형과 같은 해", max(diffs) < 1e-9, f"최대 차이 {max(diffs):.2e}")

    rb = quiet(p.hs, "demand")
    wf2 = quiet(eqn.wfopen, vcsv, freq="Q")
    md = quiet(lambda: wf2.model("d").merge("CN c Y CN(-1)", "I c Y(-1) R").append("Y = CN + I + G"))
    quiet(md.solve, "2005Q1", "2019Q4")
    dd = float(np.nanmax(np.abs(p.workfile["Y_0"].to_numpy(dtype=float) - wf2["Y_0"].to_numpy(dtype=float))))
    check("블록 HS: 그 블록만 풀고 나머지는 실측", rb.counts()["ok"] == 60 and dd < 1e-9, f"{dd:.2e}")
    r = quiet(p.hs, "main", start="2010Q1", end="2012Q4", mode="static")
    check("HS: 구간·방식을 바꾼다", (r.start, r.end) == ("2010Q1", "2012Q4") and r.counts()["ok"] == 12)
    rx = quiet(p.hs, "main_fixrl")
    check("HS: exclude한 모형", rx.counts()["ok"] == 60 and "RL" not in rx.engine.get_endogenous_variables())
    before = read(os.path.join(d, "EQUATIONS", "demand.txt"))
    base_cn = p.workfile["CN_0"].copy()
    quiet(p.hs, "main")
    base_cn = p.workfile["CN_0"].copy()
    rs = quiet(p.hs, "main", swap={"demand:CN": "CN c Y"})
    changed = float(np.nanmax(np.abs(p.workfile["CN_0"].to_numpy(dtype=float) - base_cn.to_numpy(dtype=float))))
    check("HS: 바꿔 끼우면 해가 바뀌고 파일은 그대로", rs.counts()["ok"] == 60 and changed > 1e-6
          and read(os.path.join(d, "EQUATIONS", "demand.txt")) == before, f"{changed:.3g}")

    print("=" * 80)
    print("E. 항등식 검사")
    print("=" * 80)
    c = p.ident("demand:Y")
    check("항등식: 성립", c.ok and c.n == 200 and c.n_missing == 0 and c.max_abs < 1e-4, f"{c.max_abs:.2e}")
    c = p.ident("demand:Y", start="2010Q1", end="2019Q4")
    check("항등식: 구간", c.n == 40 and c.start == "2010Q1" and c.end == "2019Q4")
    check("항등식: 표", list(c.table.columns) == ["좌변", "우변", "차이", "차이%"] and len(c.table) == 40)
    check("항등식: 추정식은 거부", raises(lambda: p.ident("demand:CN"), ValueError, "추정식"))
    pw2 = os.path.join(tmp, "wrong")
    shutil.copytree(d, pw2)
    write(os.path.join(pw2, "EQUATIONS", "demand.txt"), "CN c Y CN(-1)\nI c Y(-1) R\nY = CN + I\n")
    cw = quiet(Project.open, pw2).ident("demand:Y")
    check("항등식: 어긋남(기간·크기)", not cw.ok and len(cw.mismatches) == 200 and cw.max_pct > 1, f"{cw.max_pct:.3g}")
    check("항등식: 글·JSON", "어긋남 200기" in cw.text() and json.loads(json.dumps(cw.to_dict()))["ok"] is False)

    print("=" * 80)
    print("F. 명령줄")
    print("=" * 80)
    code, out, _ = run(["new", os.path.join(tmp, "cli"), "--template", "desk"])
    check("new --template desk", code == 0 and os.path.isfile(os.path.join(tmp, "cli", "equion.toml"))
          and "equion assemble main" in out)
    code, _, err = run(["new", os.path.join(tmp, "cli2"), "--template", "desk", "--bare"])
    check("new --template desk --bare는 입력 오류(3)", code == 3 and "--bare" in err)
    cd = os.path.join(tmp, "cli")
    code, out, _ = run(["assemble"], cd)
    check("assemble: 기본 모형·문제 없음(0)", code == 0 and out.startswith("[assemble main]") and "문제   없음" in out
          and "열기" not in out, out.splitlines()[0] if out else "")
    code, out, _ = run(["assemble", "main_fixrl", "--json"], cd)
    check("assemble --json", code == 0 and json.loads(out)["excluded"] == ["finance:RL"])
    code, out, _ = run(["assemble", "-p", pb, "bad"])
    check("assemble: 조립 문제는 입력 오류(3)", code == 3 and "목표 겹침 CN" in out)
    code, _, err = run(["assemble", "nope"], cd)
    check("assemble: 없는 모형(3)", code == 3 and "없는 모형" in err)
    code, _, err = run(["assemble"], tmp)
    check("assemble: 프로젝트가 아님(3)", code == 3 and "설정 파일이 없습니다" in err)
    code, out, _ = run(["ident", "demand:Y"], cd)
    check("ident: 식·쓰는 곳", code == 0 and "쓰는 곳  core, main, main_fixrl" in out)
    code, out, _ = run(["ident", "demand:Y", "--check", "--range", "2010Q1:2019Q4"], cd)
    check("ident --check: 성립(0)", code == 0 and "성립" in out and "비교 40기" in out)
    code, out, _ = run(["ident", "demand:Y", "--check", "--json", "-p", pw2])
    check("ident --check --json: 어긋남도 0", code == 0 and json.loads(out)["ok"] is False)
    code, _, _ = run(["ident", "demand:Y", "--check", "--strict", "-p", pw2])
    check("ident --strict: 어긋나면 3", code == 3)
    code, _, err = run(["ident", "demand:CN"], cd)
    check("ident: 추정식은 3", code == 3 and "추정식" in err)
    check("명령 뒤 출력 수준을 되돌린다", eqn.verbose() == 0)
    eqn.verbose(1)
    run(["assemble"], cd)
    check("명령 뒤 출력 수준을 되돌린다(1)", eqn.verbose() == 1)
    eqn.verbose(0)

    newf, badf = _data_tests(tmp, p, d, q)
    _span_cli_tests(tmp, p, d, newf, badf)

    print()
    print(f"결과: {len(PASS)}/{len(PASS) + len(FAIL)} 통과 ({time.time() - t0:.1f}초)")
    if FAIL:
        print("실패:", ", ".join(FAIL))
    return len(FAIL)


def problems_of(fn):
    """fn이 낸 ProjectError의 문제 목록(없으면 [])."""
    try:
        quiet(fn)
    except ProjectError as e:
        return list(e.problems)
    return []


MINI_TOML = """\
[project]
name = "mini"
[data]                            # 자료 정의 — 주석 유지 검사
series = "DATA/series.toml"
derived = "DATA/derived.txt"
freq = "Q"
[block]
b = "EQUATIONS/b.txt"
[model.m]
blocks = ["b"]
"""

MINI_SERIES = """\
# 합성 표 — 주석은 data use·add 뒤에도 남아야 한다
[source.t]                        # 엑셀: 1줄 제목, 2줄 열 이름, 3줄 단위
file = "DATA/raw/table.xlsx"
sheet = "표"
header_row = 2
unit_row = 3
time_col = "A"
missing = ["–"]
thousands = ","

[source.m]                        # cp949 csv, '2001년 1월' 꼴
file = "DATA/raw/m.csv"

[source.a]
file = "DATA/raw/a.csv"

[series.X]
from = "t:X"

[series.Z]
from = "t:z"                      # 대소문자만 다름
scale = 10

[series.W]
from = "t:W"
fill = "linear"

[series.MQ]
from = "m:IP"
convert = "sum"

[series.AQ]
from = "a:GDP"
convert = "split"
unit = "조원"
"""


def make_mini(base):
    """합성 원자료(엑셀·cp949 csv·연간 csv)와 자료 정의로 된 작은 프로젝트."""
    import openpyxl
    root = os.path.join(base, "mini")
    os.makedirs(os.path.join(root, "DATA", "raw"))
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "표"
    ws.append(["가상 분기 표(예)"])
    ws.append(["시점", "X", "Z", "W"])
    ws.append([None, "조원", "%", None])
    for k, lab in enumerate(f"{y}년 {q}/4분기" for y in (2001, 2002, 2003) for q in (1, 2, 3, 4)):
        ws.append([lab, f"{1000 + 10 * k:,}", "(5)" if k == 2 else 1.0 + k,
                   "–" if k == 3 else ("x" if k == 4 else 100.0 + k)])
    wb.save(os.path.join(root, "DATA", "raw", "table.xlsx"))
    lines = ["시점,IP"] + [f"{y}년 {m}월,{12 * (y - 2001) + m}" for y in (2001, 2002, 2003) for m in range(1, 13)]
    with open(os.path.join(root, "DATA", "raw", "m.csv"), "w", encoding="cp949", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    write(os.path.join(root, "DATA", "raw", "a.csv"), "year,GDP\n2001,4\n2002,8\n2003,12\n")
    write(os.path.join(root, "DATA", "series.toml"), MINI_SERIES)
    write(os.path.join(root, "DATA", "derived.txt"), "XZ = X + Z        # 합\n")
    write(os.path.join(root, "EQUATIONS", "b.txt"), "X c Z MQ\n")
    write(os.path.join(root, "equion.toml"), MINI_TOML)
    return root


def _data_tests(tmp, p, d, q):
    import re
    import tomllib
    from equion.data import transform as tr
    from equion.data.source import SourceSpec, file_sha256, normalize_label, read_source
    from equion.projects.vintage import read_vintage
    print("=" * 80)
    print("G. 자료 정의·회차")
    print("=" * 80)
    got = [normalize_label(x) for x in ("2003.Q4", "2003 Q4", "2003년 4/4분기", "2003년 4분기", "2003년 10월",
                                        "2003.10", "2003-M7", "2003년", "2003Q4")]
    check("시점 꼴: 흔한 표기", got == ["2003Q4", "2003Q4", "2003Q4", "2003Q4", "2003-10", "2003-10", "2003-07", "2003",
                                   "2003Q4"], str(got))
    root = make_mini(tmp)
    pm = quiet(Project.open, root)
    check("회차 없음: 자료를 쓰면 알림", raises(lambda: pm.workfile, ProjectError, "equion data build"))
    xl = os.path.join(root, "DATA", "raw", "table.xlsx")
    t = read_source(SourceSpec("t", "DATA/raw/table.xlsx", xl, sheet="표", header_row=2, unit_row=3, time_col="A",
                               missing=["–"], thousands=","))
    check("틀: 엑셀 머리줄·단위줄·시점 꼴('2001년 1/4분기')", t.freq == "Q" and len(t.data) == 12
          and t.units == {"X": "조원", "Z": "%"} and t.data.index[0] == pd.Timestamp("2001-01-01"), str(t.units))
    check("틀: 천 단위 쉼표·괄호 음수", t.data["X"].iloc[1] == 1010 and t.data["Z"].iloc[2] == -5)
    check("틀: 결측 표시·숫자 아닌 칸(칸 위치)", t.missing_cells == ["D7 '–'"] and t.bad_cells == ["D8 'x'"],
          f"{t.missing_cells} {t.bad_cells}")
    check("틀: 열 이름은 대소문자 무시", t.column("z") == ("Z", True) and t.column("nope") == (None, False))
    tm = read_source(SourceSpec("m", "DATA/raw/m.csv", os.path.join(root, "DATA", "raw", "m.csv")))
    check("틀: cp949 csv·'2001년 1월' 꼴", tm.freq == "M" and len(tm.data) == 36 and tm.data["IP"].iloc[-1] == 36)
    check("틀: 시점 칸이 빈 줄(위치)", raises(lambda: read_source(SourceSpec("t", "t.xlsx", xl, sheet="표", header_row=2)),
                                       ValueError, "3줄의 시점 칸(A3)"))

    r = quiet(pm.data_build)
    vid = r.id
    check("만들기: 새 회차 — 지금 회차는 저절로 바뀌지 않는다", r.created and re.match(r"^d\d{4}-\d{2}a$", vid)
          and pm.vintage is None and r.n_series == 6 and r.span == ("2001Q1", "2003Q4"), repr(r))
    imp = " | ".join(r.implicit)
    check("만들기: 알아서 한 것", all(k in imp for k in ("대소문자만 다름", "결측 표시로 본 칸 1개", "숫자가 아닌 칸 1개",
                                                  "안쪽 결측 2칸을 선형으로 채움 (2001Q4부터)", "MQ: M → Q sum",
                                                  "AQ: A → Q split")), imp)
    df, fl, meta = read_vintage(root, vid)
    check("만들기: 배율·채움·주기 변환·파생 값",
          df.loc["2001Q3", "Z"] == -50 and df.loc["2001Q4", "W"] == 103 and df.loc["2002Q1", "W"] == 104
          and df.loc["2001Q1", "MQ"] == 6 and df.loc["2003Q4", "MQ"] == 105 and df.loc["2001Q1", "AQ"] == 1
          and np.allclose(df["XZ"], df["X"] + df["Z"]))
    check("만들기: 값의 종류(실측·변환·채움·파생)",
          fl.loc["2001Q1", "X"] == "actual" and fl.loc["2001Q1", "Z"] == "transformed" and fl.loc["2001Q4", "W"] == "filled"
          and fl.loc["2001Q3", "W"] == "actual" and fl.loc["2001Q1", "MQ"] == "transformed"
          and fl.loc["2001Q1", "XZ"] == "derived")
    check("만들기: 단위(단위줄·정의)", meta["series"]["X"]["unit"] == "조원" and meta["series"]["AQ"]["unit"] == "조원"
          and meta["series"]["XZ"]["expr"] == "X + Z")
    vdir = os.path.join(root, "work", "data", vid)
    with open(os.path.join(vdir, "build.json"), encoding="utf-8") as f:
        build = json.load(f)
    check("만들기: 기록(입력 해시·정의·equion 판)", build["format"] == "equion-data-vintage"
          and {s["name"]: s["sha256"] for s in build["sources"]}["t"] == file_sha256(xl)
          and "DATA/series.toml" in build["definitions"] and build["equion"] == eqn.__version__)
    check("만들기: summary.md", "| XZ | = X + Z |" in read(os.path.join(vdir, "summary.md")))
    check("만들기: 임시 폴더를 남기지 않는다", not [n for n in os.listdir(os.path.join(root, "work", "data"))
                                          if n.startswith(".tmp")])
    write(os.path.join(root, "DATA", "series.toml"), "# 주석만 더함\n", mode="a")
    r2 = quiet(pm.data_build)
    check("만들기: 같은 원자료·정의(주석만 다름)면 같은 회차", not r2.created and r2.id == vid and len(pm.data_list()) == 1)
    old = quiet(pm.data_use, vid)
    toml = read(os.path.join(root, "equion.toml"))
    check("바꾸기: equion.toml [data] vintage(주석 그대로)", old is None and pm.vintage == vid
          and f'vintage = "{vid}"' in toml and "# 자료 정의 — 주석 유지 검사" in toml)
    check("바꾸기: 회차 자료로 연다", {"X", "Z", "W", "MQ", "AQ", "XZ"} <= set(pm.workfile.series())
          and pm.data_list()[0]["current"])
    check("바꾸기: 없는 회차", raises(lambda: pm.data_use("d2001-01a"), ProjectError, "없습니다"))
    check("자료 파일 하나 프로젝트는 회차 없음", raises(lambda: q.data_build(), ProjectError, "자료 파일 하나"))

    pb = os.path.join(tmp, "minibad")
    shutil.copytree(root, pb)
    write(os.path.join(pb, "DATA", "series.toml"),
          '[source.t]\nfile = "DATA/raw/table.xlsx"\n[series.LOG]\nfrom = "t:X"\n[series.Q1]\nfrom = "zz:X"\n'
          '[series.Q2]\nfrom = "t:X"\nconvert = "avg"\n[series.Q3]\nfrom = "tX"\n[extra]\nx = 1\n')
    write(os.path.join(pb, "DATA", "derived.txt"), "XZ X + Z\nQ2 = X\n")
    pr = problems_of(quiet(Project.open, pb).data_build)
    want = (lambda x: "[series.LOG]" in x and "log()" in x, lambda x: "없는 원자료 'zz'" in x,
            lambda x: "convert = 'avg'" in x, lambda x: "[series.Q3]" in x and "원자료이름:열" in x,
            lambda x: "알 수 없는 표 [extra]" in x, lambda x: "derived.txt:1" in x and "'이름 = 식'" in x,
            lambda x: "derived.txt:2" in x and "겹칩니다" in x)
    check("정의 문제: 모아서 한꺼번에(위치와 함께)", all(any(w(x) for x in pr) for w in want), " | ".join(pr)[:300])
    write(os.path.join(pb, "DATA", "series.toml"),
          '[source.t]\nfile = "DATA/raw/table.xlsx"\nsheet = "표"\nheader_row = 2\nunit_row = 3\n'
          '[source.u]\nfile = "DATA/raw/table.xlsx"\nsheet = "표"\nheader_row = 2\n'
          '[source.m]\nfile = "DATA/raw/m.csv"\n'
          '[series.X]\nfrom = "t:NOPE"\n[series.Y2]\nfrom = "u:X"\n[series.MQ]\nfrom = "m:IP"\n')
    write(os.path.join(pb, "DATA", "derived.txt"), "BAD = X +\n")
    pr = problems_of(quiet(Project.open, pb).data_build)
    check("만들기 문제: 없는 열·틀·주기 변환", any("NOPE" in x and "열이 없습니다" in x and "있는 열" in x for x in pr)
          and any("[source.u]" in x and "A3" in x for x in pr) and any("[series.MQ]" in x and "convert =" in x for x in pr),
          " | ".join(pr)[:300])
    write(os.path.join(pb, "DATA", "series.toml"), '[source.t]\nfile = "DATA/raw/table.xlsx"\nsheet = "표"\n'
          'header_row = 2\nunit_row = 3\nthousands = ","\n[series.X]\nfrom = "t:X"\n')
    pr = problems_of(quiet(Project.open, pb).data_build)
    check("만들기 문제: 파생식 오류는 파일:줄", any(x.startswith("DATA/derived.txt:1") for x in pr), " | ".join(pr)[:200])

    # 예제 프로젝트의 회차 — 계절조정·주기 변환·파생을 직접 계산과 견준다
    vdf, vfl, _ = read_vintage(d, p.vintage)
    rawq = pd.read_csv(os.path.join(d, "DATA", "raw", "toy_q.csv"), index_col=0)
    y = rawq["CNNSA"].to_numpy(dtype=float)
    S = np.exp(tr.stl(np.log(y), 4)[0])
    check("만들기: 계절조정(STL 승법) = 직접 계산", np.allclose(vdf["CNSA"].to_numpy(), y / S, rtol=1e-12))
    rawm = pd.read_csv(os.path.join(d, "DATA", "raw", "toy_m.csv"), index_col=0)
    check("만들기: 월 → 분기 평균 = 직접 계산", abs(vdf.loc["2000Q1", "IPQ"] - rawm["IP"].iloc[:3].mean()) < 1e-12
          and vfl.loc["1999Q4", "IPQ"] == "missing" and vfl.loc["2000Q1", "IPQ"] == "transformed")
    pi = 100 * (vdf["P"] / vdf["P"].shift(4) - 1)
    check("만들기: 파생 PI·RR", np.allclose(vdf["PI"].iloc[4:], pi.iloc[4:]) and vfl.loc["1970Q1", "PI"] == "missing"
          and np.allclose(vdf["RR"].iloc[4:], (vdf["R"] - pi).iloc[4:]))
    check("만들기: 원자료 값은 그대로(실측)", np.array_equal(vdf["CN"].to_numpy(), rawq["CN"].to_numpy())
          and (vfl["CN"] == "actual").all())

    # 원자료 넣기 → 새 회차 → 차이·영향 → 바꾸기
    pu = os.path.join(tmp, "upd")
    shutil.copytree(d, pu)
    P = quiet(Project.open, pu)
    sfile = os.path.join(pu, "DATA", "series.toml")
    new = rawq.copy()
    new.loc[new.index[-4:], "CN"] *= 1.01
    new.loc["2020Q1"] = new.iloc[-1] * 1.005
    newf = os.path.join(tmp, "toy_q_new.csv")
    new.to_csv(newf)
    badf = os.path.join(tmp, "toy_q_bad.csv")
    new.drop(columns=["POIL"]).to_csv(badf)
    before = read(sfile)
    ra = quiet(P.data_add, badf, source="na")
    check("넣기: 틀이 맞지 않으면 아무것도 바꾸지 않는다", any("POIL" in x for x in ra.problems) and not ra.copied
          and read(sfile) == before and not os.path.exists(os.path.join(pu, "DATA", "raw", "toy_q_bad.csv"))
          and "넣지 않았습니다" in ra.text())
    ra = quiet(P.data_add, newf, source="na", as_name="toy_q.csv", note="2020Q1 추가")
    check("넣기: 같은 이름·다른 내용은 날짜를 붙여 나란히", ra.copied and re.match(r"^DATA/raw/toy_q_\d{8}\.csv$", ra.file)
          and read(os.path.join(pu, "DATA", "raw", "toy_q.csv")) == read(os.path.join(d, "DATA", "raw", "toy_q.csv")),
          ra.file)
    toml = read(sfile)
    check("넣기: 출처를 새 파일로(주석 그대로)", f'file = "{ra.file}"' in toml and "# 분기 거시 자료" in toml
          and ra.previous == "DATA/raw/toy_q.csv")
    with open(os.path.join(pu, ra.file + ".source.toml"), "rb") as f:
        side = tomllib.load(f)
    check("넣기: 옆 파일에 출처·해시·메모", side["sha256"] == ra.sha256 == file_sha256(newf) and side["note"] == "2020Q1 추가"
          and side["from"] == "toy_q_new.csv")
    rb = quiet(P.data_add, newf)
    check("넣기: 같은 내용은 다시 넣지 않는다(다른 이름이어도)", not rb.copied and rb.file == ra.file)
    check("넣기: csv·xlsx·xls만", raises(lambda: P.data_add(sfile), ProjectError, "csv·xlsx·xls"))
    check("넣기: 이름은 파일 이름 하나(폴더 밖으로 못 쓴다)",
          raises(lambda: P.data_add(newf, as_name="../out.csv"), ProjectError, "파일 이름 하나")
          and raises(lambda: P.data_add(newf, as_name=".hidden.csv"), ProjectError, "파일 이름 하나")
          and not os.path.exists(os.path.join(pu, "DATA", "out.csv")))
    check("넣기: 없는 출처", raises(lambda: P.data_add(newf, source="zz"), ProjectError, "없는 출처"))
    v0 = P.vintage
    rn = quiet(P.data_build)
    check("새 원자료: 새 회차, 지금 회차는 그대로", rn.created and rn.id != v0 and P.vintage == v0
          and rn.span == ("1970Q1", "2020Q1"))
    dd = P.data_diff()
    cn = dd.changes.loc["CN"]
    check("차이: 기본은 지금 → 가장 새 회차", (dd.a, dd.b) == (v0, rn.id))
    check("차이: 개정(기간·크기)과 새 값", cn["개정"] == 4 and cn["처음 개정"] == "2019Q1" and cn["끝 개정"] == "2019Q4"
          and abs(cn["최대 |차이%|"] - 1) < 1e-6 and cn["새 값"] == 1, str(cn.to_dict()))
    check("차이: 새 값만 있는 시리즈·그대로인 시리즈", dd.changes.loc["G", "개정"] == 0 and dd.changes.loc["G", "새 값"] == 1
          and dd.unchanged == ["IPQ"], str(dd.unchanged))
    check("차이: 글·JSON", "개정 4기(2019Q1~2019Q4)" in dd.text() and json.loads(json.dumps(dd.to_dict()))["b"] == rn.id)
    im = P.data_impact()
    check("영향: 바뀐 시리즈를 쓰는 식·모형", len(im.parts) == 6 and im.models == ["core", "main", "main_fixrl"]
          and im.uses["price:P"] == ["P", "POIL", "Y"])
    check("영향: 다시 계산하지 않는다", P.vintage == v0 and "저절로 하지 않는다" in im.text())
    quiet(P.data_use, rn.id)
    r = quiet(P.hs, "main")
    check("바꾸기 뒤 HS: 상대 구간(2005Q1:last)이 새 끝을 따른다", (r.start, r.end) == ("2005Q1", "2020Q1")
          and r.counts()["ok"] == 61, f"{r.start}~{r.end}")
    new2 = new.copy()
    new2.loc["2019Q4", "POIL"] *= 1.1
    new2f = os.path.join(tmp, "toy_q_new2.csv")
    new2.to_csv(new2f)
    quiet(P.data_add, new2f, source="na")
    rn2 = quiet(P.data_build)
    im = P.data_impact()
    check("영향: 유가만 바뀌면 물가 식과 그 모형만", (im.diff.a, im.diff.b) == (rn.id, rn2.id) and im.parts == ["price:P"]
          and im.models == ["main", "main_fixrl"] and im.diff.changed == ["POIL"], f"{im.parts} {im.models}")
    check("회차 목록: 만든 때 순·지금 회차", [v["id"] for v in P.data_list()] == [v0, rn.id, rn2.id]
          and [v["current"] for v in P.data_list()] == [False, True, False])
    return newf, badf


def _span_cli_tests(tmp, p, d, newf, badf):
    print("=" * 80)
    print("H. 상대 기간·자료 회차 명령줄")
    print("=" * 80)
    check("상대 기간: last·last-N·first+N·next:N", p.span("last-3:last") == ("2019Q1", "2019Q4")
          and p.span("next:4") == ("2020Q1", "2020Q4") and p.span("first:first+3") == ("1970Q1", "1970Q4")
          and p.span("2005Q1:last") == ("2005Q1", "2019Q4"))
    check("상대 기간: 시작이 끝보다 뒤", raises(lambda: p.span("last:first"), ValueError, "뒤입니다"))
    r = quiet(p.hs, "main", start="last-11", end="last")
    check("상대 기간: HS 구간", (r.start, r.end) == ("2017Q1", "2019Q4") and r.counts()["ok"] == 12)
    check("상대 기간: 항등식 검사 구간", p.ident("demand:Y", start="last-39").n == 40)

    cu = os.path.join(tmp, "clidata")
    shutil.copytree(d, cu)
    v0 = p.vintage
    code, out, _ = run(["new", os.path.join(tmp, "cli3"), "--template", "desk"])
    check("new --template desk: 첫 회차를 알린다", code == 0 and "자료 회차 d" in out and "지금 회차로" in out)
    code, out, _ = run(["data", "list"], cu)
    check("data list(0)", code == 0 and f"* {v0}" in out)
    code, out, _ = run(["data", "build"], cu)
    check("data build: 바뀐 것 없음(0)", code == 0 and "바뀐 것 없음" in out and "열기" not in out)
    code, out, _ = run(["data", "add", badf, "--source", "na"], cu)
    check("data add: 틀이 맞지 않으면 3", code == 3 and "넣지 않았습니다" in out)
    code, out, _ = run(["data", "add", newf, "--source", "na", "--note", "새 분기"], cu)
    check("data add --source(0)", code == 0 and "[source.na]" in out and "equion data build" in out)
    code, out, _ = run(["data", "build", "--json"], cu)
    j = json.loads(out) if code == 0 else {}
    check("data build --json: 새 회차·지금 회차 그대로", j.get("created") and j.get("current") == v0
          and j.get("span") == ["1970Q1", "2020Q1"])
    code, out, _ = run(["data", "build"], cu)
    check("data build: 다음 할 일(use)", code == 0 and f"equion data use {j.get('id')}" in out)
    code, out, _ = run(["data", "diff"], cu)
    check("data diff(0)", code == 0 and "개정 4기" in out)
    code, out, _ = run(["data", "impact", "--json"], cu)
    check("data impact --json", code == 0 and json.loads(out)["models"] == ["core", "main", "main_fixrl"])
    code, _, err = run(["data", "use", "d1999-01a"], cu)
    check("data use: 없는 회차(3)", code == 3 and "없습니다" in err)
    code, out, _ = run(["data", "use", j.get("id", "")], cu)
    check("data use(0)", code == 0 and f"지금 자료 회차 {j.get('id')} (전: {v0})" in out
          and quiet(Project.open, cu).vintage == j.get("id"))
    code, out, _ = run(["data", "diff", v0, j.get("id", ""), "--json"], cu)
    check("data diff A B --json", code == 0 and json.loads(out)["a"] == v0)
    code, _, _ = run(["data"], cu)
    check("data: 동작 없음(3)", code == 3)
    code, _, err = run(["data", "build", "-p", os.path.join(tmp, "ok")])
    check("data: 자료 파일 하나 프로젝트(3)", code == 3 and "자료 파일 하나" in err)


def test_suite():
    """pytest 진입점 — 이 파일의 검사 묶음 전체(하나라도 실패하면 실패). `python tests/test_project.py`와 같은 검사."""
    assert main() == 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(99)
