#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_analysis.py — 분석 등록부·노트·보고서(D37 — 개발 계획 E4) 테스트.

실행: uv run python tests/test_analysis.py   (종료코드 = 실패 수)

  A. 등록부: 분석 목록·대상 종류·옵션 기본값·만드는 것·허용 목록(노트가 부를 수 있는 명령)
  B. 보는 분석: 요약·단위근·공적분(Johansen·Engle-Granger)·식 진단(Chow·CUSUM)·예측 평가(DM)·안정성·승수 — 엔진을 직접 부른 값과 같다
  C. 기록·카드: work/an/<이름>/ 표 CSV·차트 CSV·summary.md(명령 그대로·자료 회차·알아서 한 것), 표본(--smpl), 이름 겹침, 모르는 옵션
  D. 만드는 분석: 계절조정·파생 → an keep(정의 — series.toml·derived.txt, made_by) → data build → 새 회차에 그 시리즈
  E. 부품을 내는 분석: ECM·VAR·VECM·시스템 → an keep(식 후보 est: — 계수 그대로) → compare·hs --swap·adopt
  F. 노트: 블록 실행·결과 구역(펼친 md·차트 상대 경로)·허용 안 된 명령·다시 실행 = 새 기록·손으로 고친 구역(--force)·낡음(회차)·
     check·--stale·Python 블록(--block)·an --note
  G. 보고서: new·add(전망 연간·분기·기준선 대비·HS·추정·분석 표 #k·행 고르기·차트 자료 복사·제목 아래)·check·update(차이·
     손으로 고친 곳을 차이로 알린다·--force·--region --to·--dry-run)·new --from(바꿔 낄 기록 제안)
  H. 명령줄: an list·--help·<분석>·keep · note run·check · report new·add·check·update — 종료 코드·--json
  I. 분석 기획 자료의 시나리오(A1~A5)를 명령만으로
자료는 예제 프로젝트(예제 자료 toy_q·toy_m)와 코드로 만든 합성 표만 쓴다.
"""

import contextlib
import io
import json
import os
import re
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
from equion import registry as reg  # noqa: E402
from equion.cli import main as cli  # noqa: E402
from equion.projects import Project, ProjectError  # noqa: E402
from equion.work import RecordError  # noqa: E402

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


def main():
    t0 = time.time()
    tmp = tempfile.mkdtemp(prefix="eqn-an-")
    old_verbose = eqn.verbose()
    eqn.verbose(0)
    try:
        return _main(tmp, t0)
    finally:
        eqn.verbose(old_verbose)
        shutil.rmtree(tmp, ignore_errors=True)


def _main(tmp, t0):
    print("=" * 80)
    print("A. 등록부")
    print("=" * 80)
    names = [a.name for a in reg.analyses()]
    check("분석 22개(등록 순)", names == ["summary", "unitroot", "coint", "diag", "fcsteval", "stability", "multipliers",
                                     "seas", "genr", "ecm", "var", "vecm", "system", "stats", "hist", "acf", "corr", "xcorr",
                                     "granger", "fevd", "convert", "stochastic"], str(names))
    check("대상 수(count) — 우클릭 메뉴가 고른 수로 거른다", {a.name: a.count for a in reg.analyses() if a.count != "any"} ==
          {"coint": "many", "seas": "one", "ecm": "many", "var": "many", "vecm": "many", "hist": "one", "acf": "one", "corr": "many",
           "xcorr": "two", "granger": "many", "fevd": "many"})
    check("만드는 것", {a.name: a.makes for a in reg.analyses() if a.makes} ==
          {"seas": "definition", "genr": "derived", "ecm": "candidate", "var": "candidate", "vecm": "candidate",
           "system": "candidate"})
    check("대상 종류로 고르기", [a.name for a in reg.analyses("model")] == ["stability", "multipliers", "stochastic"])
    check("옵션 기본값", reg.get("unitroot").defaults() == {"trend": "c", "lags": None, "ic": "bic", "maxlag": None})
    check("없는 분석", raises(lambda: reg.get("nope"), KeyError, "있는 분석"))
    check("표(목록)", reg.table()[0]["분석"] == "summary" and set(reg.table()[0]) == {"분석", "이름", "갈래", "대상", "만드는 것", "결과"})
    check("허용 목록: 계산·보기 명령", all(reg.allowed(t.split()) is None for t in
                                    ("an unitroot core", "est demand:CN", "hs main", "sim base", "compare --target CN",
                                     "data diff", "work show est:x", "assemble main")))
    check("허용 목록: 파일을 바꾸는 명령은 안 된다", all(reg.allowed(t.split()) for t in
                                            ("adopt est:x", "data use d2026-11a", "data build", "propose apply p1",
                                             "history revert h0001", "run x.py", "nope")))

    print("=" * 80)
    print("B. 보는 분석 — 엔진과 같은 값")
    print("=" * 80)
    p, d = new_project(tmp, "an")
    wf = quiet(eqn.wfopen, os.path.join(d, "work", "data", p.vintage, "series.csv"), freq="Q")
    r = quiet(p.an, "unitroot", "dlog(Y) R", trend="c")
    t = r.table(1)
    a_ = quiet(wf.adf, "dlog(Y)", trend="c")
    k_ = quiet(wf.kpss, "R", trend="c")
    check("단위근: ADF·KPSS = 엔진", abs(t.loc["dlog(Y)", "ADF t"] - a_.statistic) < 1e-12 and abs(t.loc["R", "KPSS"] - k_.statistic) < 1e-12)
    check("단위근: 판단(정상·단위근)", t["판단"].tolist() == ["정상", "단위근"] and r.meta["sample"] == ["1970Q2", "2019Q4"])
    rg = quiet(p.an, "unitroot", "core")
    check("단위근: 묶음([group])", list(rg.table(1).index) == ["Y", "CN", "I"] and rg.meta["target_label"].startswith("묶음 core"))
    j = quiet(p.an, "coint", "RL R", lags=1)
    jw = quiet(wf.johansen, "RL R", det=0, lags=1)
    check("공적분 Johansen = 엔진", j.meta["result"]["rank_trace"] == jw.details["rank_trace"]
          and np.allclose(j.table(1).to_numpy(dtype=float), jw.table.to_numpy(dtype=float)))
    eg = quiet(p.an, "coint", "RL R", method="engle", lags=0)
    egw = quiet(wf.coint, "RL", "R")
    check("공적분 Engle-Granger = 엔진", abs(eg.meta["result"]["statistic"] - egw.statistic) < 1e-12)
    dg = quiet(p.an, "diag", "price:P", chow="2008Q3,2015Q1")
    eqw = quiet(wf.equation("chk").ls, "dlog(P) c dlog(Y) dlog(POIL)")
    cw = quiet(eqw.chow, "2008Q3")
    check("식 진단: 검정·Chow 둘·CUSUM", len(dg.meta["tables"]) == 3 and abs(float(str(dg.table(2).loc["통계량", "값"]).replace(",", "")) - cw.statistic) < 1e-3
          and os.path.isfile(dg.record.file("chart_1.csv")) and any(x.startswith("CUSUM") for x in dg.meta["lines"]))
    check("식 진단: 항등식은 거부", raises(lambda: p.an("diag", "demand:Y"), ProjectError, "항등식"))
    h1 = quiet(p.hs, "main", record=True, as_name="h1")
    h2 = quiet(p.hs, "main", record=True, swap={"demand:CN": "CN c Y"}, as_name="h2")
    fe = quiet(p.an, "fcsteval", "hs:h1 hs:h2", var="CN")
    f1 = pd.Series(h1.solved["CN"].to_numpy(), index=wf.data.index[140:200], name="hs:h1")
    f2 = pd.Series(h2.solved["CN"].to_numpy(), index=wf.data.index[140:200], name="hs:h2")
    fw = wf.forecast_eval("CN", f1, f2).data
    check("예측 평가 = 엔진(RMSE)·DM", np.allclose(fe.table(1)["RMSE"].to_numpy(), fw["RMSE"].to_numpy())
          and "dm" in fe.meta["result"] and len(fe.meta["tables"]) == 2)
    check("예측 평가: --var 없으면", raises(lambda: p.an("fcsteval", "hs:h1"), ProjectError, "--var"))
    st = quiet(p.an, "stability", "main")
    sw = quiet(p.model, "main").stability()
    check("안정성 = 엔진", abs(st.meta["result"]["max_modulus"] - sw.max_modulus) < 1e-12 and st.meta["result"]["verdict"] == sw.verdict)
    mu = quiet(p.an, "multipliers", "main", var="G", shock=1.0)
    muw = quiet(p.model, "main").multipliers("G", 1.0, "2005Q1", "2019Q4")
    check("충격 승수 = 엔진", np.allclose(mu.table(1)["Y"].to_numpy(), muw.level["Y"].to_numpy()))
    sm = quiet(p.an, "summary", "RL Y")
    check("요약: 처음·끝·값의 종류·단위", sm.table(1).loc["RL", "처음"] == "1980Q1" and sm.table(1).loc["Y", "값"] == 200
          and "actual" in sm.table(1).loc["Y", "값의 종류"] and sm.table(1).loc["Y", "단위"] == "조원(가상)")

    print("=" * 80)
    print("C. 기록·카드")
    print("=" * 80)
    m = r.meta
    check("기록: 이름·명령·옵션·자료", r.id == "an:unitroot_0001" and m["command"] == "an unitroot dlog(Y) R" and m["options"]["trend"] == "c"
          and m["data"]["kind"] == "vintage" and m["kind"] == "an")
    card = r.record.summary_md()
    check("카드: 머리(기록·명령·자료·표본·누가)·표·알아서 한 것", card.startswith("# 단위근 — dlog(Y) · R") and "| 명령 | `an unitroot dlog(Y) R` |" in card
          and "## 단위근 검정" in card and "## 알아서 한 것" in card)
    check("카드: 차트(같은 폴더 CSV)", '"url": "chart_1.csv"' in dg.record.summary_md())
    check("짧은 글", r.text().startswith("[an:unitroot_0001] 단위근 · dlog(Y) · R · 1970Q2~2019Q4 · 자료 data:")
          and "기록   an:unitroot_0001" in r.text())
    rs = quiet(p.an, "unitroot", "Y", smpl="last-39:last", as_name="u_short")
    check("--smpl(상대 기간)·--as", rs.id == "an:u_short" and rs.meta["sample"][0] == "2010Q1" and p.workfile._smpl is None)
    check("이름 겹침·모르는 옵션", raises(lambda: p.an("unitroot", "Y", as_name="u_short"), RecordError, "이미 있는 기록")
          and raises(lambda: p.an("unitroot", "Y", bogus=1), ProjectError, "모르는 옵션"))
    check("엔진 오류는 ProjectError(분석·대상과 함께)", raises(lambda: p.an("unitroot", "NOPE"), ProjectError, "단위근(NOPE)"))
    check("보는 분석은 남길 것이 없다", raises(lambda: p.keep(r.id), ProjectError, "보는 분석"))

    print("=" * 80)
    print("D. 만드는 분석 — 정의로")
    print("=" * 80)
    s1 = quiet(p.an, "seas", "CN", model="multiplicative", as_name="s1")
    sw_ = quiet(wf.seas, "CN", model="multiplicative", write=False)
    check("계절조정 = 엔진(미리보기 — 자료는 그대로)", np.allclose(s1.table(1)["조정"].to_numpy(), sw_.table["조정"].to_numpy())
          and "CNSA_X" not in p.workfile.series() and s1.meta["makes"]["kind"] == "definition")
    before = read(os.path.join(d, "DATA", "series.toml"))
    k1 = quiet(p.keep, "an:s1", as_name="CNSA_X")
    after = read(os.path.join(d, "DATA", "series.toml"))
    check("keep: series.toml에 새 시리즈(made_by·주석 그대로)", "[series.CNSA_X]" in after and 'made_by = "an:s1"' in after
          and after.startswith(before.split("\n")[0]) and "# 분기 거시 자료" in after and k1.change is not None)
    check("keep: 이름 겹침·--replace", raises(lambda: p.keep("an:s1", as_name="CN"), ProjectError, "이미 있는 시리즈"))
    g1 = quiet(p.an, "genr", "GAP = Y - CN - I - G", as_name="g1")
    check("파생 미리보기", np.allclose(g1.table(1)["GAP"].to_numpy(), 0, atol=1e-3) and g1.meta["makes"]["kind"] == "derived")
    k2 = quiet(p.keep, "an:g1")
    check("keep: derived.txt 한 줄", "GAP = Y - CN - I - G   # an:g1" in read(os.path.join(d, "DATA", "derived.txt")))
    check("파생: 이미 있는 이름·꼴", raises(lambda: p.an("genr", "Y = CN"), ProjectError, "이미 있는 시리즈")
          and raises(lambda: p.an("genr", "1x"), ProjectError, "이름 = 식"))
    br = quiet(p.data_build, use=True)
    check("data build → 새 회차에 계절조정·파생 시리즈", br.created and "CNSA_X" in p.workfile.series() and "GAP" in p.workfile.series()
          and np.allclose(p.workfile["CNSA_X"].to_numpy(), sw_.table["조정"].to_numpy()))
    check("계절조정은 정의된 시리즈만", raises(lambda: p.an("seas", "dlog(Y)"), ProjectError, "시리즈 하나"))
    s2 = quiet(p.an, "seas", "GAP", as_name="s2")
    check("파생 시리즈는 정의로 남기지 못한다", raises(lambda: p.keep("an:s2"), ProjectError, "derived.txt"))

    print("=" * 80)
    print("E. 부품을 내는 분석 — 식 후보로")
    print("=" * 80)
    q, dq = new_project(tmp, "cand")
    ec = quiet(q.an, "ecm", "CN Y", as_name="ec1")
    kc = quiet(q.keep, "an:ec1", as_name="cons_ecm1")
    rec = q.work.get("est:cons_ecm1")
    wq = quiet(eqn.wfopen, os.path.join(dq, "work", "data", q.vintage, "series.csv"), freq="Q")
    ew = quiet(wq.ecm, "e", "CN", ["Y"])
    check("ECM → 식 후보(단기식·계수 그대로·부품 묶기)", kc.records == ["est:cons_ecm1"] and rec.meta["part"] == "demand:CN"
          and np.allclose([c["coef"] for c in rec.meta["coefs"]], ew.shortrun.coefs.to_numpy())
          and any("ec1" in x for x in rec.meta["implicit"]))
    v = quiet(q.an, "var", "RL R", lags=2, as_name="v1")
    kv = quiet(q.keep, "an:v1")
    rv = q.work.get(kv.records[0])
    vw = quiet(wq.var, "vv", ["RL", "R"], lags=2)
    check("VAR → 식마다 후보(고정 계수 = 엔진)", len(kv.records) == 2 and rv.meta["method"] == "fixed" and rv.meta["part"] == "finance:RL"
          and np.allclose([c["coef"] for c in rv.meta["coefs"]], quiet(vw.make_equations)[0].coefs.to_numpy()))
    check("VAR 카드: 충격반응 차트", os.path.isfile(v.record.file("chart_1.csv")) and len(v.meta["tables"]) == 4)
    vc = quiet(q.an, "vecm", "RL R", as_name="vc1")
    check("VECM → 식 후보", len(quiet(q.keep, "an:vc1").records) == 2)
    sy = quiet(q.an, "system", "demand", method="sur", as_name="sy1")
    ks = quiet(q.keep, "an:sy1")
    check("시스템 추정(SUR) → 식마다 후보", [q.work.get(x).meta["part"] for x in ks.records] == ["demand:CN", "demand:I"])
    check("시스템: 블록만", raises(lambda: q.an("system", "main"), ProjectError, "블록"))
    hs_ = quiet(q.hs, "main", record=True, swap={"demand:CN": "est:cons_ecm1"})
    check("후보 → hs --swap(그 계수로)", hs_.counts()["ok"] == 60 and hs_.meta["swaps"] == {"demand:CN": "est:cons_ecm1"})
    cp = q.compare(part="demand:CN")
    check("후보 → compare(부품의 후보)", {"est:cons_ecm1", ks.records[0]} <= set(cp.table.index))

    print("=" * 80)
    print("F. 노트")
    print("=" * 80)
    nb = os.path.join(dq, "notes", "core.md")
    write(nb, "# core 묶음\n\n소비함수를 오차수정 꼴로 쓸 수 있는지 본다.\n\n```equion\nequion an unitroot core --trend ct\n```\n\n"
              "공적분을 본다.\n\n```equion\nan coint \"RL R\" --lags 2\n```\n\n```python\nprint(6 * 7)\n```\n")
    nr = quiet(q.note_run, "notes/core.md")
    txt = read(nb)
    check("실행: 블록마다 기록·결과 구역", [b.status for b in nr.blocks] == ["run", "run", "skip"] and txt.count("<!-- equion:out") == 2
          and "**단위근 — 묶음 core(Y · CN · I)**" in txt and "<!-- /equion:out -->" in txt)
    uid = nr.blocks[0].records[0]
    check("결과 구역: 명령 그대로·글은 그대로", f"| 명령 | `equion an unitroot core --trend ct` |" in txt
          and "공적분을 본다." in txt and txt.startswith("# core 묶음"))
    write(os.path.join(dq, "notes", "chart.md"), "```equion\nan diag demand:CN\n```\n")
    quiet(q.note_run, "notes/chart.md")
    ctext = read(os.path.join(dq, "notes", "chart.md"))
    check("결과 구역의 차트: 노트에서 본 상대 경로", re.search(r'"url": "\.\./work/an/diag_\d{4}/chart_1\.csv"', ctext) is not None)
    nr2 = quiet(q.note_run, "notes/core.md", block=1)
    txt2 = read(nb)
    check("다시 실행 = 새 기록(옛 기록은 남는다)", nr2.blocks[0].records[0] != uid and q.work.get(uid) and uid not in txt2
          and txt2.count("<!-- equion:out") == 2)
    nr3 = quiet(q.note_run, "notes/core.md", block=3)
    check("Python 블록은 --block으로만", nr3.blocks[0].status == "run" and "42" in read(nb))
    write(nb, read(nb).replace("| CN |", "| 민간소비 |", 1))
    ch = quiet(q.note_check, "notes/core.md")
    check("check: 손으로 고친 구역", ch.blocks[0].status == "edited" and ch.blocks[1].status == "ok", str([b.status for b in ch.blocks]))
    nr4 = quiet(q.note_run, "notes/core.md")
    check("손으로 고친 구역은 덮지 않는다", nr4.blocks[0].status == "edited" and "| 민간소비 |" in read(nb))
    quiet(q.note_run, "notes/core.md", block=1, force=True)
    check("--force면 덮는다", "| 민간소비 |" not in read(nb))
    new = pd.read_csv(os.path.join(dq, "DATA", "raw", "toy_q.csv"), index_col=0)
    new.loc["2020Q1"] = new.iloc[-1] * 1.004
    new.to_csv(os.path.join(tmp, "cand_new.csv"))
    quiet(q.data_add, os.path.join(tmp, "cand_new.csv"), source="na")
    quiet(q.data_build, use=True)
    ch2 = quiet(q.note_check, "notes/core.md")
    check("check: 회차가 바뀌면 낡음", [b.status for b in ch2.blocks[:2]] == ["stale", "stale"] and "자료 회차" in ch2.blocks[0].detail)
    nr5 = quiet(q.note_run, "notes/core.md", stale=True)
    check("--stale: 낡은 구역만 다시", [b.status for b in nr5.blocks] == ["run", "run", "skip"]
          and all(b.status == "ok" for b in quiet(q.note_check, "notes/core.md").blocks[:2]))
    write(os.path.join(dq, "notes", "bad.md"), "```equion\nan unitroot R\nadopt est:cons_ecm1\n```\n")
    nb_ = quiet(q.note_run, "notes/bad.md")
    check("허용 안 된 명령이 있으면 블록을 돌리지 않는다", nb_.blocks[0].status == "denied" and not nb_.ok
          and "<!-- equion:out" not in read(os.path.join(dq, "notes", "bad.md")) and "adopt" in nb_.blocks[0].detail)
    write(os.path.join(dq, "notes", "err.md"), "```equion\nan unitroot NOPE\n```\n")
    ne = quiet(q.note_run, "notes/err.md")
    check("명령 오류는 구역에 '오류'", ne.blocks[0].status == "error" and "**오류**(종료 코드 3)" in read(os.path.join(dq, "notes", "err.md")))
    write(os.path.join(dq, "notes", "txt.md"), "```equion\nassemble core\n```\n")
    quiet(q.note_run, "notes/txt.md")
    check("기록 없는 명령은 글 결과", "[assemble core]" in read(os.path.join(dq, "notes", "txt.md")))
    ra = quiet(q.an, "unitroot", "dlog(Y)", note="notes/new.md")
    nt = read(os.path.join(dq, "notes", "new.md"))
    check("an --note: 노트 끝에 블록과 구역(새 노트)", nt.startswith("# new") and "```equion\nan unitroot 'dlog(Y)'\n```" in nt
          and ra.id in nt)
    hist = q.history.list()
    check("노트를 고친 것은 바뀜 기록에", any(h.how.startswith("note run") and "notes/core.md" in h.files for h in hist))
    check("없는 노트·없는 블록", raises(lambda: q.note_run("notes/none.md"), ProjectError, "노트가 없습니다")
          and raises(lambda: q.note_run("notes/core.md", block=9), ProjectError, "블록 9"))

    print("=" * 80)
    print("G. 보고서")
    print("=" * 80)
    g, dg_ = new_project(tmp, "rep")
    b1 = quiet(g.sim, as_name="2026-10_base")
    o1 = quiet(g.sim, "oil20", as_name="2026-10_oil20")
    hh = quiet(g.hs, "main", record=True, as_name="hh")
    ee = quiet(g.est, "demand:CN", as_name="ee")
    uu = quiet(g.an, "unitroot", "core", as_name="uu")
    rn = quiet(g.report_new, "전망_10월", title="10월 전망")
    rp = os.path.join(dg_, "reports", "전망_10월.md")
    check("new: 틀(제목·날짜·회차·모형)", rn.report == "reports/전망_10월.md" and read(rp).startswith("# 10월 전망")
          and f"자료 회차 {g.vintage}" in read(rp) and "## 본문" in read(rp))
    check("new: 이미 있음", raises(lambda: g.report_new("전망_10월"), ProjectError, "이미 있는 보고서"))
    quiet(g.report_add, "전망_10월", "sim:2026-10_base", rows=["Y", "CN", "P"], show="yoy", annual=True, title="주요 지표 전망",
          under="## 본문", chart=True)
    t1 = read(rp)
    ann = b1.annual
    check("add: 전망 연간 증가율(소수 1자리)·제목 번호·출처", "**표 1. 주요 지표 전망** (연간 증가율, %)" in t1
          and f"| Y | {ann.loc['2020', 'Y_증가율']:.1f} | {ann.loc['2021', 'Y_증가율']:.1f} |" in t1
          and f"자료: Equion sim:2026-10_base(자료 회차 {g.vintage})" in t1)
    check("add: 제목 아래(## 본문)·보이지 않는 표시", t1.index("## 본문") < t1.index("<!-- equion:report sim:2026-10_base #1")
          and '"show": "yoy"' in t1)
    check("add: 차트 자료는 보고서 옆 폴더로", os.path.isfile(os.path.join(dg_, "reports", "전망_10월_data", "sim_2026-10_base_1.csv"))
          and '"url": "전망_10월_data/sim_2026-10_base_1.csv"' in t1)
    quiet(g.report_add, "전망_10월", "sim:2026-10_oil20", rows=["P"], show="diff")
    quiet(g.report_add, "전망_10월", "sim:2026-10_base", rows=["Y"], show="level", digits=2)
    quiet(g.report_add, "전망_10월", "hs:hh", rows=["Y", "CN"])
    quiet(g.report_add, "전망_10월", "est:ee")
    quiet(g.report_add, "전망_10월", "an:uu#1", rows=["Y"])
    t2 = read(rp)
    lv = b1.levels
    check("add: 기준선 대비 %·분기 수준(2자리)·HS·추정·분석 표", "(기준선 대비, %)" in t2 and f"| Y | {lv.loc['2020Q1', 'Y']:,.2f} |" in t2
          and "**표 4. 과거 재현 적합도" in t2 and "**표 5. 추정 — CN c Y CN(-1)**" in t2 and "**표 6. 단위근" in t2
          and t2.count("<!-- equion:report") == 6)
    check("add: 없는 행·기준선에 diff·없는 표 번호", raises(lambda: g.report_add("전망_10월", "hs:hh", rows=["ZZ"]), ProjectError, "없는 행")
          and raises(lambda: g.report_add("전망_10월", "sim:2026-10_base", show="diff"), ProjectError, "기준선")
          and raises(lambda: g.report_add("전망_10월", "an:uu#5"), ProjectError, "표는 1개"))
    c0 = quiet(g.report_check, "전망_10월")
    check("check: 정상(노트·보고서를 고쳐도 기록은 낡지 않는다)", all(it["status"] == "정상" for it in c0.items), str([i["status"] for i in c0.items]))
    write(rp, read(rp).replace("| Y | ", "| 실질 GDP | ", 1))
    b2 = quiet(g.sim, as_name="2026-11_base", range="next:12")
    c1 = quiet(g.report_check, "전망_10월")
    check("check: 더 새 기록·손으로 고침", "더 새 기록" in c1.items[0]["status"] and "손으로 고침" in c1.items[0]["status"]
          and c1.items[0]["to"] == "sim:2026-11_base" and c1.items[1]["status"] == "정상")
    u0 = quiet(g.report_update, "전망_10월", dry_run=True)
    check("update --dry-run: 바꾸지 않는다", read(rp).count("sim:2026-10_base #1") == 1 and u0.change is None)
    u1 = quiet(g.report_update, "전망_10월")
    it1 = u1.items[0]
    check("update: 손으로 고친 곳을 차이로 알리고 덮지 않는다", "손으로 고침" in it1["status"] and "-| Y |" in it1["diff"]
          and "+| 실질 GDP |" in it1["diff"] and "| 실질 GDP |" in read(rp), it1["diff"][:200])
    check("update: 다른 구역은 새 기록으로(같은 모양)", any(i["n"] == 3 and i["to"] == "sim:2026-11_base" and "바뀜" in i["status"]
                                                for i in u1.items) and "<!-- equion:report sim:2026-11_base #3" in read(rp))
    u2 = quiet(g.report_update, "전망_10월", region=1, force=True)
    t3 = read(rp)
    check("update --force: 덮고 차이(바뀐 숫자)", "| 실질 GDP |" not in t3 and "2022" in u2.items[0]["diff"]
          and "<!-- equion:report sim:2026-11_base #1" in t3 and os.path.isfile(os.path.join(dg_, "reports", "전망_10월_data",
                                                                                            "sim_2026-11_base_1.csv")))
    u3 = quiet(g.report_update, "전망_10월", region=1, to="sim:2026-10_base")
    check("update --region --to: 고른 기록으로", "<!-- equion:report sim:2026-10_base #1" in read(rp) and u3.items[0]["to"] == "sim:2026-10_base")
    check("update: --to는 --region과", raises(lambda: g.report_update("전망_10월", to="sim:2026-10_base"), ProjectError, "--region"))
    rn2 = quiet(g.report_new, "전망_11월", from_report="전망_10월")
    check("new --from: 복사·바꿔 낄 기록 제안", any(i["n"] == 1 and i["to"] == "sim:2026-11_base" for i in rn2.items)
          and read(os.path.join(dg_, "reports", "전망_11월.md")).count("<!-- equion:report") == 6
          and "전망_11월_data/" in read(os.path.join(dg_, "reports", "전망_11월.md")))
    shutil.rmtree(os.path.join(dg_, "work", "an", "uu"))
    c2 = quiet(g.report_check, "전망_10월")
    check("check: 없는 기록", any(i["status"] == "없는 기록" and i["record"] == "an:uu" for i in c2.items))
    check("보고서가 쓴 기록은 정리에서 빠진다", "hs:hh" not in run(["work", "clean"], dg_)[1])

    print("=" * 80)
    print("H. 명령줄")
    print("=" * 80)
    _, dc = new_project(tmp, "cli")
    code, out, _ = run(["an", "list"], dc)
    check("an list(0)", code == 0 and out.startswith("[an list] 분석 22") and "seas" in out)
    code, out, _ = run(["an", "list", "--for", "model", "--json"], dc)
    check("an list --for --json", code == 0 and [x["분석"] for x in json.loads(out)] == ["stability", "multipliers", "stochastic"])
    code, out, _ = run(["an", "unitroot", "--help"], dc)
    check("an <분석> --help: 등록부의 옵션·기본값·예", code == 0 and "--trend {n,c,ct}" in out and "(기본 c)" in out
          and "예: equion an unitroot core --trend ct" in out)
    code, out, _ = run(["an", "unitroot", "core", "--trend", "ct"], dc)
    check("an unitroot(0)", code == 0 and out.startswith("[an:unitroot_0001] 단위근 · 묶음 core"))
    code, out, _ = run(["an", "diag", "price:P", "--no-cusum", "--json"], dc)
    check("an --no-<옵션>(bool)·--json", code == 0 and json.loads(out)["options"]["cusum"] is False)
    code, out, _ = run(["an", "genr", "GAP = Y - CN - I - G", "--as", "g"], dc)
    code2, out2, _ = run(["an", "keep", "an:g"], dc)
    check("an genr → keep(0)", code == 0 and code2 == 0 and "derived.txt" in out2 and "equion data build" in out2)
    code, _, err = run(["an", "unitroot", "NOPE"], dc)
    check("an: 대상 오류(3)", code == 3 and "단위근(NOPE)" in err)
    code, _, err = run(["an", "nope", "x"], dc)
    check("an: 없는 분석(3)", code == 3)
    write(os.path.join(dc, "notes", "n.md"), "```equion\nan unitroot R\n```\n")
    code, out, _ = run(["note", "run", "notes/n.md"], dc)
    check("note run(0)", code == 0 and "실행" in out)
    code, out, _ = run(["note", "check", "notes/n.md", "--json"], dc)
    check("note check --json", code == 0 and json.loads(out)[0]["blocks"][0]["status"] == "ok")
    write(os.path.join(dc, "notes", "b.md"), "```equion\nadopt est:x\n```\n")
    code, _, _ = run(["note", "run", "notes/b.md"], dc)
    code2, _, _ = run(["note", "check", "notes/b.md"], dc)
    check("note: 허용 안 된 명령 — run 1 · check 3", code == 1 and code2 == 3)
    run(["sim", "--as", "b1"], dc)
    code, out, _ = run(["report", "new", "r1"], dc)
    code2, out2, _ = run(["report", "add", "r1", "sim:b1", "--rows", "Y,CN", "--show", "yoy", "--annual"], dc)
    code3, out3, _ = run(["report", "check", "r1"], dc)
    code4, out4, _ = run(["report", "update", "r1", "--dry-run"], dc)
    check("report new·add·check·update(0)", (code, code2, code3, code4) == (0, 0, 0, 0) and "#1 sim:b1  넣음" in out2
          and "정상" in out3 and "그대로" in out4)
    code, _, err = run(["report", "add", "none", "sim:b1"], dc)
    check("report: 없는 보고서(3)", code == 3 and "없는 보고서" in err)

    print("=" * 80)
    print("I. 분석 기획 자료의 시나리오(A1~A5)를 명령만으로")
    print("=" * 80)
    _, ds = new_project(tmp, "scen")
    code, out, _ = run(["an", "seas", "CN", "--model", "multiplicative", "--as", "seas_0004"], ds)
    code2, out2, _ = run(["an", "keep", "an:seas_0004", "--as", "CN_SA"], ds)
    code3, out3, _ = run(["data", "build", "--use"], ds)
    check("A1 계절조정 → 정의로 남기기 → 자료 만들기 → 이 회차로", (code, code2, code3) == (0, 0, 0)
          and "CN_SA" in quiet(Project.open, ds).workfile.series())
    write(os.path.join(ds, "notes", "core.md"), "# core 묶음 — 적분 차수와 공적분\n\n```equion\nequion an unitroot core --trend ct\n```\n\n"
                                                "```equion\nequion an coint \"RL R\" --lags 2\n```\n")
    code, out, _ = run(["note", "run", "notes/core.md"], ds)
    nt = read(os.path.join(ds, "notes", "core.md"))
    check("A2 단위근·공적분 노트", code == 0 and nt.count("<!-- equion:out an:") == 2)
    old_id = re.search(r"<!-- equion:out (an:coint_\d+)", nt)[1]
    blk = '```equion\nequion an coint "RL R" --lags 2\n```'
    write(os.path.join(ds, "notes", "core.md"), nt.replace(blk, blk.replace("--lags 2", "--lags 4")))   # 블록 줄만 고친다
    code, out, _ = run(["note", "run", "notes/core.md", "--block", "2"], ds)
    nt2 = read(os.path.join(ds, "notes", "core.md"))
    new_id = re.search(r"<!-- equion:out (an:coint_\d+)", nt2)[1]
    check("A3 옵션 바꿔 다시 — 새 기록(옛 것도 남는다)", code == 0 and new_id != old_id
          and quiet(Project.open, ds).work.get(old_id).meta["options"]["lags"] == 2
          and quiet(Project.open, ds).work.get(new_id).meta["options"]["lags"] == 4)
    code, out, _ = run(["an", "ecm", "log(CN) log(Y)", "--as", "ecm_0007"], ds)
    code2, out2, _ = run(["an", "keep", "an:ecm_0007", "--as", "cons_ecm1"], ds)
    code3, out3, _ = run(["compare", "--target", "CN", "--json"], ds)
    check("A4 ECM 후보 → 비교(채택은 하지 않음)", (code, code2, code3) == (0, 0, 0)
          and "est:cons_ecm1" in [r_["기록"] for r_ in json.loads(out3)["rows"]] and quiet(Project.open, ds).adopted == {})
    run(["report", "new", "2026-11_소비"], ds)
    code, out, _ = run(["report", "add", "2026-11_소비", new_id + "#1"], ds)
    code2, out2, _ = run(["report", "add", "2026-11_소비", "est:cons_ecm1"], ds)
    rt = read(os.path.join(ds, "reports", "2026-11_소비.md"))
    check("A5 보고서 — 결과만(명령 블록 없이)", code == 0 and code2 == 0 and "```equion" not in rt and rt.count("<!-- equion:report") == 2)

    print("=" * 80)
    print("J. 기초 분석·인과·변환·확률적 모의 (D50) — 통계 함수와 같은 값, 카드의 차트 종류")
    print("=" * 80)
    from equion import stats as S
    pj, dj = new_project(tmp, "an_basic")
    wj = quiet(eqn.wfopen, os.path.join(dj, "work", "data", pj.vintage, "series.csv"), freq="Q")
    st = quiet(pj.an, "stats", "core")
    ref = S.describe(pd.DataFrame({c: wj[c] for c in ("Y", "CN", "I")}))
    check("기술 통계: 묶음의 시리즈마다 = 통계 함수", list(st.table(1).index) == ["Y", "CN", "I"]
          and np.allclose(st.table(1)["평균"].to_numpy(), ref["평균"].to_numpy()) and np.allclose(st.table(1)["첨도"].to_numpy(), ref["첨도"].to_numpy())
          and st.meta["sample"] == ["1970Q1", "2019Q4"])
    ac = quiet(pj.an, "acf", "dlog(Y)", lags=8)
    cg = S.correlogram(wj.eval("dlog(Y)").dropna().to_numpy(), 8)
    md_ac = ac.record.summary_md()
    check("자기상관: 표 = 통계 함수, 막대 차트 둘(95% 한계 점선)", np.allclose(ac.table(1)["편자기상관"].to_numpy(), cg["편자기상관"].to_numpy())
          and ac.meta["charts"] == ["자기상관", "편자기상관"] and md_ac.count('"type": "bar"') == 2 and '"strokeDash"' in md_ac
          and abs(ac.meta["result"]["band"] - cg.attrs["band"]) < 1e-12, md_ac[-300:])
    ac2 = quiet(pj.an, "acf", "R")
    check("자기상관: 시차를 주지 않으면 분기 12 · 시리즈 둘이면 오류", ac2.meta["result"]["lags"] == 12
          and raises(lambda: pj.an("acf", "Y CN"), ProjectError, "하나"))
    co = quiet(pj.an, "corr", "dlog(CN) dlog(Y) R")
    cref = S.correlation(pd.DataFrame({x: wj.eval(x) if "(" in x else wj[x] for x in ("dlog(CN)", "dlog(Y)", "R")}))
    md_co = co.record.summary_md()
    check("상관: 행렬·p값 = 통계 함수, 색 격자 차트(긴 표 행·열·값)", np.allclose(co.table(1).to_numpy(dtype=float), cref.corr.to_numpy())
          and co.meta["tables"] == ["상관 행렬", "p값", "공분산", "쌍마다"] and '"type": "rect"' in md_co and '"blueorange"' in md_co
          and list(co.record.read_csv("chart_1.csv").columns) == ["행", "열", "값"] and co.meta["result"]["nobs"] == cref.nobs)
    c2 = quiet(pj.an, "corr", "dlog(CN) dlog(Y)", method="spearman")
    check("상관: 둘이면 산점도(최소제곱 직선)도 · 스피어먼 · 하나면 오류", c2.meta["charts"][1] == "dlog(CN) · dlog(Y)" and '"regression"' in c2.record.summary_md()
          and c2.meta["result"]["method"] == "spearman" and raises(lambda: pj.an("corr", "Y"), ProjectError, "둘 이상"))
    xc = quiet(pj.an, "xcorr", "dlog(CN) dlog(Y)", lags=4)
    xref = S.ccf(wj.eval("dlog(CN)").to_numpy(), wj.eval("dlog(Y)").to_numpy(), 4)
    check("교차상관: = 통계 함수(−4…4), 둘이 아니면 오류", np.allclose(xc.table(1)["상관"].to_numpy(), xref["상관"].to_numpy()) and len(xc.table(1)) == 9
          and raises(lambda: pj.an("xcorr", "Y CN I"), ProjectError, "둘"))
    gr = quiet(pj.an, "granger", "dlog(Y) dlog(CN)", lags=2)
    gref = S.granger_causality(wj.eval("dlog(CN)"), wj.eval("dlog(Y)"), 2)
    gt = gr.table(1)
    check("Granger: 쌍마다 = 통계 함수, p값 행렬, 기본 시차는 분기 4", abs(gt[(gt["원인"] == "dlog(Y)") & (gt["결과"] == "dlog(CN)")]["F"].iloc[0] - gref.statistic) < 1e-9
          and gr.meta["tables"] == ["Granger 인과", "p값(행 원인 → 열 결과)"] and quiet(pj.an, "granger", "core").meta["result"]["lags"] == 4)
    hi = quiet(pj.an, "hist", "dlog(Y)", bins=6)
    md_hi = hi.record.summary_md()
    check("히스토그램: 구간 6 · 도수 합 = 관측치 · 막대 + 정규 기대도수 선", len(hi.table(1)) == 6 and int(hi.table(1)["도수"].sum()) == 199
          and '"point": true' in md_hi and hi.meta["result"]["bins"] == 6)
    fv = quiet(pj.an, "fevd", "dlog(Y) R", lags=2, periods=6)
    fw = quiet(wj.var, "chkv", ["dlog(Y)", "R"], lags=2).fevd(6)
    check("분산분해: = VAR 객체(%) · 행 합 100", np.allclose(fv.table(1).to_numpy(dtype=float), (fw["dlog(Y)"] * 100).round(2).to_numpy())
          and np.allclose(fv.table(2).sum(axis=1).to_numpy(dtype=float), 100, atol=0.05))
    cv = quiet(pj.an, "convert", "Y", how="sum")
    from equion.data import transform as T
    aref = T.aggregate(wj["Y"], "Q", "A", "sum").dropna()
    check("주기 변환: 분기 → 연 합 = transform.aggregate, 연 라벨", list(cv.table(1).index[:2]) == ["1970", "1971"]
          and np.allclose(cv.table(1)["Y"].to_numpy(dtype=float), aref.to_numpy()) and raises(lambda: pj.an("convert", "Y", to="Q"), ProjectError, "이미"))
    sto = quiet(pj.an, "stochastic", "main", var="Y", reps=20, seed=3)
    sto2 = quiet(pj.an, "stochastic", "main", var="Y", reps=20, seed=3)
    check("확률적 모의: 평균·표준편차·분위수 표, 같은 씨앗이면 같은 값", list(sto.table(1).columns) == ["mean", "std", "p5", "p50", "p95"]
          and np.allclose(sto.table(1).to_numpy(dtype=float), sto2.table(1).to_numpy(dtype=float)) and sto.meta["sample"] == ["2005Q1", "2019Q4"])
    code, out, _ = run(["an", "corr", "core", "--method", "spearman"], dj)
    code2, out2, _ = run(["an", "list"], dj)
    check("명령줄: an corr · an list에 새 분석", code == 0 and "[an:corr_" in out and "상관" in out and code2 == 0
          and all(x in out2 for x in ("stats", "acf", "granger", "xcorr", "fevd", "stochastic")), out[:200])

    print("=" * 80)
    print("K. 노트에 블록 더하기 — note add (D57)")
    print("=" * 80)
    nf = os.path.join(dj, "notes", "inv.md")
    add = pj.note_add("notes/inv.md", lines=["equion est 'I c Y I(-1)' --for demand:I", "est 'I c Y' --for demand:I"], title="투자 후보",
                      who="tester", command="equion note add notes/inv.md …")
    txt = read(nf)
    check("새 노트: 제목과 ```equion 블록 하나(실행하지 않는다 — 결과 구역 없음) · 바뀜 기록",
          add.new and add.block == 1 and txt.startswith("# 투자 후보") and "```equion\nest 'I c Y I(-1)' --for demand:I\nest 'I c Y' --for demand:I\n```" in txt
          and "equion:out" not in txt and pj.history.get(add.change).who == "tester", txt)
    run1 = quiet(pj.note_run, "notes/inv.md")
    rec = run1.blocks[0].records[0]
    add2 = pj.note_add("notes/inv.md", record=rec)
    blocks = quiet(pj.note_check, "notes/inv.md").blocks
    check("기록 담기: 그 기록의 명령과 결과 구역(카드)까지 — 둘째 블록은 실행하지 않아도 정상",
          not add2.new and add2.block == 2 and add2.record == rec and [b.status for b in blocks] == ["ok", "ok"] and read(nf).count("<!-- equion:out") == 2,
          str([b.to_dict() for b in blocks]))
    check("거절: 노트가 부를 수 없는 명령(파일을 바꾸는 것) · 더할 것 없음 · md 아님 · 프로젝트 밖",
          raises(lambda: pj.note_add("notes/inv.md", lines=["adopt est:x"]), ProjectError, "노트에서 부를 수 없습니다")
          and raises(lambda: pj.note_add("notes/inv.md"), ProjectError, "더할 것이 없습니다")
          and raises(lambda: pj.note_add("notes/inv.txt", lines=["an stats Y"]), ProjectError, ".md")
          and raises(lambda: pj.note_add("../x.md", lines=["an stats Y"]), ProjectError, "프로젝트 밖"))
    code, out, _ = run(["note", "add", "notes/n2.md", "--line", "an stats Y", "--line", "an acf Y --lags 4", "--title", "점검"], dj)
    code2, out2, _ = run(["note", "add", "notes/n2.md", "--record", rec, "--json"], dj)
    code3, _, err3 = run(["note", "add", "notes/n2.md", "--line", "group remove core"], dj)
    check("명령줄: note add --line(거듭)·--title · --record --json · 허용 안 된 명령(3)",
          code == 0 and "새 노트 · 블록 1" in out and code2 == 0 and json.loads(out2)["block"] == 2 and code3 == 3 and "넣을 수 없는 명령" in err3, out + err3)
    print()
    print(f"결과: {len(PASS)}/{len(PASS) + len(FAIL)} 통과 ({time.time() - t0:.1f}초)")
    if FAIL:
        print("실패:", ", ".join(FAIL))
    return len(FAIL)


def test_suite():
    """pytest 진입점 — 이 파일의 검사 묶음 전체(하나라도 실패하면 실패). `python tests/test_analysis.py`와 같은 검사."""
    assert main() == 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(99)
