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
자료는 예제 자료 toy_q(예제 프로젝트의 DATA/data.csv)만 쓴다.
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
    files = ["equion.toml", "DATA/data.csv", "EQUATIONS/demand.txt", "EQUATIONS/price.txt",
             "EQUATIONS/finance.txt", "README.md", ".gitignore"]
    check("만들기: 예제 프로젝트 파일", all(os.path.isfile(os.path.join(d, f)) for f in files))
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
    df = pd.read_csv(os.path.join(pe, "DATA", "data.csv"))
    df.loc[df.index[-4:], "POIL"] = np.nan
    df.to_csv(os.path.join(pe, "DATA", "data.csv"), index=False)
    r = quiet(quiet(Project.open, pe).assemble, "main")
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

    wf = quiet(eqn.wfopen, os.path.join(d, "DATA", "data.csv"))
    mm = quiet(lambda: wf.model("chk").merge("CN c Y CN(-1)", "I c Y(-1) R", "dlog(P) c dlog(Y) dlog(POIL)",
                                             "RL c R RL(-1)", "log(M2) c log(P) log(Y) RL log(M2(-1))")
               .append("Y = CN + I + G"))
    quiet(mm.solve, "2005Q1", "2019Q4")
    pw = p.workfile
    diffs = [float(np.nanmax(np.abs(pw[f"{v}_0"].to_numpy(dtype=float) - wf[f"{v}_0"].to_numpy(dtype=float))))
             for v in ("CN", "I", "Y", "P", "RL", "M2")]
    check("HS: 워크파일 API로 직접 만든 모형과 같은 해", max(diffs) < 1e-9, f"최대 차이 {max(diffs):.2e}")

    rb = quiet(p.hs, "demand")
    wf2 = quiet(eqn.wfopen, os.path.join(d, "DATA", "data.csv"))
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

    print()
    print(f"결과: {len(PASS)}/{len(PASS) + len(FAIL)} 통과 ({time.time() - t0:.1f}초)")
    if FAIL:
        print("실패:", ", ".join(FAIL))
    return len(FAIL)


def test_suite():
    """pytest 진입점 — 이 파일의 검사 묶음 전체(하나라도 실패하면 실패). `python tests/test_project.py`와 같은 검사."""
    assert main() == 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(99)
