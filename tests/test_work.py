#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_work.py — 작업 명령·기록(D33·D35 — 개발 계획 E3) 테스트.

실행: uv run python tests/test_work.py   (종료코드 = 실패 수)

  A. 기록 저장소: 쓰기·찾기·목록·이름(겹침·글자)·고치지 않음·log.jsonl·고정·메모·지우기·누가
  B. 바뀜 기록: 처음 기준 · 바깥 고침 알아보기 · 명령이 고친 파일의 전후 · 되돌리기(그것도 기록)
  C. md 렌더러: 파이프 표(정수·글자 escape) · 머리 표 · vega-lite 블록 · 출력 객체 .md()
  D. 추정 기록(est): 부품·식 글자(후보 묶기·여럿·--for)·항등식 거부·표본·판단 기준(부호·진단·|t|)·단독 모의·TSLS·파일
  E. 채택(adopt): 블록 파일 줄(설명 유지)·채택표·바뀜 기록·모형이 채택 계수를 쓴다(다시 추정 없음)·글자 다름·기록 없음
  F. 비교(compare): 추정 후보 표·경고(종속변수·표본) · HS 기록 · 섞인 종류
  G. HS 기록: 조립 명세·워크파일 API로 직접 푼 것과 같은 해·바꿔 끼우기(기록 계수·식)·전후 비교·그때 그대로 다시(파일을
     바꾼 뒤에도 같다)·자료가 바뀌면 다시 돌리지 않는다
  H. 명령줄: est · adopt · compare · hs(--swap·--vs·--replay) · work · history — 종료 코드·--json
  I. 장면 2(소비함수 고르기 — 후보 비교와 채택)를 명령만으로
자료는 예제 프로젝트(예제 자료 toy_q·toy_m)와 코드로 만든 합성 표만 쓴다.
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
from equion.work import History, RecordError, WorkStore, detect_who  # noqa: E402

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


def new_project(base, name):
    d = os.path.join(base, name)
    return quiet(Project.create, d), d


def main():
    t0 = time.time()
    tmp = tempfile.mkdtemp(prefix="eqn-work-")
    old_verbose = eqn.verbose()
    eqn.verbose(0)
    old_who = os.environ.pop("EQUION_WHO", None)
    try:
        return _main(tmp, t0)
    finally:
        eqn.verbose(old_verbose)
        if old_who is not None:
            os.environ["EQUION_WHO"] = old_who
        shutil.rmtree(tmp, ignore_errors=True)


def _main(tmp, t0):
    print("=" * 80)
    print("A. 기록 저장소")
    print("=" * 80)
    st = WorkStore(os.path.join(tmp, "store"))
    r = st.write("est", "a_1", {"who": "python", "command": "x", "target": "CN"},
                 {"t.csv": pd.DataFrame({"v": [1, 2]}, index=pd.Index(["2001Q1", "2001Q2"], name="period")),
                  "x.json": {"k": np.float64(1.5), "n": np.nan}}, "# 카드\n", log={"metric": "m"})
    check("쓰기: 폴더·record.json·summary.md·파일", os.path.isfile(r.file("record.json")) and r.summary_md() == "# 카드\n"
          and r.read_csv("t.csv")["v"].tolist() == [1, 2] and r.read_json("x.json") == {"k": 1.5, "n": None})
    check("쓰기: 형식·이름·만든 때", r.meta["format"] == "equion-record" and r.meta["id"] == "est:a_1" and r.meta["created"])
    check("쓰기: 임시 폴더를 남기지 않는다", not [n for n in os.listdir(st.dir("est")) if n.startswith(".tmp")])
    check("고치지 않음: 같은 이름은 거부", raises(lambda: st.write("est", "a_1", {}, {}, ""), RecordError, "이미 있는 기록"))
    check("이름 글자", raises(lambda: st.write("est", "한글", {}, {}, ""), RecordError, "영문"))
    check("다음 이름", st.next_name("est", "a") == "a_0002" and st.next_name("hs", "hs") == "hs_0001")
    check("찾기·종류", st.get("est:a_1").meta["target"] == "CN" and raises(lambda: st.get("est:a_1", "hs"), RecordError, "추정 기록")
          and raises(lambda: st.get("est:none"), RecordError, "없는 기록") and raises(lambda: st.get("a_1"), RecordError, "종류:이름"))
    check("log.jsonl 한 줄", [d["id"] for d in st.log()] == ["est:a_1"] and st.log()[0]["metric"] == "m")
    st.mark("est:a_1", pinned=True)
    st.mark("est:a_1", memo="좋음")
    check("고정·메모(기록은 그대로)", st.marks()["est:a_1"] == {"pinned": True, "memo": "좋음"} and "pinned" not in r.read_json("record.json"))
    st.remove("est:a_1")
    check("지우기: 목록에서 빠진다", st.log() == [] and st.records() == [] and "est:a_1" not in st.marks())
    os.environ["EQUION_WHO"] = "desk"
    w1 = detect_who("terminal")
    del os.environ["EQUION_WHO"]
    old_cc = os.environ.pop("CLAUDECODE", None)
    w2 = detect_who("terminal")
    os.environ["CLAUDECODE"] = "1"
    w3 = detect_who("terminal")
    if old_cc is None:
        del os.environ["CLAUDECODE"]
    else:
        os.environ["CLAUDECODE"] = old_cc
    check("누가: EQUION_WHO · Claude Code · 기본", (w1, w2, w3) == ("desk", "terminal", "claude"))

    print("=" * 80)
    print("B. 바뀜 기록")
    print("=" * 80)
    hr = os.path.join(tmp, "hist")
    write(os.path.join(hr, "equion.toml"), "[project]\nname = \"h\"\n")
    write(os.path.join(hr, "EQUATIONS", "b.txt"), "CN c Y\n")
    h = History(hr)
    check("처음: 기준만 삼고 적지 않는다", h.scan() is None and h.list() == [])
    write(os.path.join(hr, "EQUATIONS", "b.txt"), "CN c Y CN(-1)\n")
    c = h.scan()
    check("바깥 고침을 알아본다(전후·차이)", c is not None and c.who == "바깥" and c.files["EQUATIONS/b.txt"]["op"] == "changed"
          and "+CN c Y CN(-1)" in c.diff and "-CN c Y" in c.diff)
    check("다시 보면 바뀐 것 없음", h.scan() is None)
    c2 = h.write_files({"EQUATIONS/b.txt": "CN c Y CN(-1) CN(-2)\n", "EQUATIONS/new.txt": "I c Y\n"}, "terminal",
                       "equion adopt est:x", note="메모")
    check("명령이 고친 파일: 고침·새로", c2.files["EQUATIONS/b.txt"]["op"] == "changed" and c2.files["EQUATIONS/new.txt"]["op"] == "added"
          and read(os.path.join(hr, "EQUATIONS", "b.txt")) == "CN c Y CN(-1) CN(-2)\n" and c2.how == "equion adopt est:x")
    check("전후 사본", read(os.path.join(c2.path, "before", "EQUATIONS", "b.txt")) == "CN c Y CN(-1)\n"
          and read(os.path.join(c2.path, "after", "EQUATIONS", "b.txt")) == "CN c Y CN(-1) CN(-2)\n")
    c3 = h.revert(c2.id, "terminal")
    check("되돌리기: 앞 내용으로·새 파일은 지움·기록에 남는다", read(os.path.join(hr, "EQUATIONS", "b.txt")) == "CN c Y CN(-1)\n"
          and not os.path.exists(os.path.join(hr, "EQUATIONS", "new.txt")) and c3.reverts == c2.id
          and [x.id for x in h.list()] == ["h0001", "h0002", "h0003"])
    check("같은 내용으로 쓰면 기록 없음", h.write_files({"EQUATIONS/b.txt": "CN c Y CN(-1)\n"}, "terminal", "x") is None)
    check("없는 바뀜", raises(lambda: h.get("h0999"), KeyError, "없는 바뀜"))
    check("글·사전", "바깥" in h.get("h0001").text() and h.get("h0002").to_dict()["note"] == "메모")

    print("=" * 80)
    print("C. md 렌더러")
    print("=" * 80)
    from equion.reporting import markdown as md
    t = md.table(pd.DataFrame({"n": [3, 4], "x": [0.5, 1.25], "s": ["a|b", "c\nd"]}, index=pd.Index(["r1", "r2"], name="행")))
    check("파이프 표: 정수·소수·escape", t.splitlines()[0] == "| 행 | n | x | s |" and "| r1 | 3 | 0.5000 | a\\|b |" in t
          and "c d" in t, t)
    check("빈 표", md.table(pd.DataFrame()) == "(없음)")
    check("머리 표는 빈 값을 뺀다", md.kv([("a", 1), ("b", None), ("c", "")]).count("\n") == 2)
    vl = md.vega_line("series.csv", "period", ["Y", "Y_실측"], "제목")
    spec = json.loads(vl.split("\n", 1)[1].rsplit("\n", 1)[0])
    check("vega-lite 블록(같은 폴더 CSV)", vl.startswith("```vega-lite\n") and spec["data"] == {"url": "series.csv"}
          and spec["transform"][0]["fold"] == ["Y", "Y_실측"])
    wf = quiet(eqn.datasets.load, "toy_q")
    o = quiet(wf.equation("eq_i").ls, "I c Y(-1) R").output().md()
    check("출력 객체 .md()", o.startswith("**방정식 eq_i**") and "| 변수 | 계수 |" in o and "유의수준" in o)

    print("=" * 80)
    print("D. 추정 기록")
    print("=" * 80)
    p, d = new_project(tmp, "demo")
    r1 = quiet(p.est, "demand:CN", as_name="cn_file", sim=True)
    m = r1.meta
    direct = quiet(wf.equation("chk").ls, "CN c Y CN(-1)")
    check("부품을 추정: 블록 파일의 그 줄", m["part"] == "demand:CN" and m["text"] == "CN c Y CN(-1)" and m["method"] == "ols")
    check("계수 = 워크파일 API로 직접 추정", np.allclose(r1.coefs.to_numpy(), direct.coefs.to_numpy(), rtol=1e-12, atol=0),
          str(r1.coefs.round(4).to_dict()))
    check("표본·관측치·알아서 한 것", m["sample"] == ["1970Q2", "2019Q4"] and m["n"] == 199
          and any("1970Q1 → 1970Q2" in x for x in m["implicit"]))
    check("진단 항목", set(m["diagnostics"]) >= {"lm", "white", "jb", "reset", "lb"})
    sim = m["sim"]
    rec_series = r1.record.read_csv("series.csv")
    v, a = rec_series["CN_sim"].dropna(), rec_series["CN"].dropna()
    man = 100 * np.sqrt(np.mean(((v - a.loc[v.index]) / a.loc[v.index]) ** 2))
    check("단독 모의: [hs] range·RMSPE = 직접 계산", (sim["start"], sim["end"]) == ("2005Q1", "2019Q4") and sim["n"] == 60
          and abs(sim["rmspe"] - man) < 1e-12, f"{sim['rmspe']:.6f} vs {man:.6f}")
    check("판단 기준: 진단(LM)으로 걸러짐", r1.passed is False and any(x.startswith("LM(2)") for x in m["criteria"]["reasons"]))
    check("기록 파일·카드", all(os.path.isfile(r1.record.file(f)) for f in
                            ("record.json", "coefs.csv", "series.csv", "summary.md"))
          and all(h_ in r1.record.summary_md() for h_ in ("# 추정 est:cn_file", "## 계수", "## 진단", "## 단독 모의",
                                                          "```vega-lite", "## 알아서 한 것")))
    r2 = quiet(p.est, "CN c Y(-1) CN(-1)", as_name="cn_alt")
    check("식 글자: 목표가 같은 부품의 후보로", r2.meta["part"] == "demand:CN" and r2.meta["sim"] is None)
    r3 = quiet(p.est, "I c Y(-1) R", as_name="inv_a")
    check("판단 기준: 기대 부호 통과(R −)", r3.passed is True and r3.meta["criteria"]["signs"][0]["ok"] is True)
    r4 = quiet(p.est, "I c Y(-1) R(-1) G", as_name="inv_b")
    check("판단 기준: 부호 항이 없으면 표시만", r4.meta["criteria"]["signs"][0]["ok"] is None)
    neg = quiet(p.est, "I c Y(-1) @trend", as_name="inv_trend")
    check("기록 이름 기본값·목표 소문자", quiet(p.est, "I c Y(-1)").id == "est:i_0001")
    write(p.config.path, read(p.config.path).replace('"demand:I" = { R = "-" }', '"demand:I" = { R = "+" }'))
    p._reset()
    r5 = quiet(p.est, "I c Y(-1) R", as_name="inv_sign")
    check("판단 기준: 부호가 반대면 걸러짐(까닭)", r5.passed is False and "R 부호" in r5.meta["criteria"]["reasons"])
    write(p.config.path, read(p.config.path).replace('"demand:I" = { R = "+" }', '"demand:I" = { R = "-" }')
          .replace('tests = ["lm", "reset"]', 'tests = ["lm", "reset"]\nt_min = 50.0'))
    p._reset()
    r6 = quiet(p.est, "I c Y(-1) R", as_name="inv_t")
    check("판단 기준: |t| 하한", r6.passed is False and any(x.startswith("R t") for x in r6.meta["criteria"]["reasons"]),
          str(r6.meta["criteria"]["reasons"]))
    write(p.config.path, read(p.config.path).replace("\nt_min = 50.0", ""))
    p._reset()
    r7 = quiet(p.est, "CN c Y CN(-1) @inst G R CN(-1) Y(-1)", as_name="cn_iv")
    check("TSLS(@inst): 추정법·알아서 한 것", r7.meta["method"] == "tsls" and "상수항을 도구변수에 넣음" in r7.meta["implicit"])
    r8 = quiet(p.est, "CN c Y CN(-1)", as_name="cn_short", smpl="last-39:last")
    check("표본: 상대 기간", r8.meta["sample"] == ["2010Q1", "2019Q4"] and r8.meta["n"] == 40 and p.workfile._smpl is None)
    check("항등식은 거부", raises(lambda: p.est("demand:Y"), ProjectError, "항등식") and raises(lambda: p.est("Z = CN + I"),
                                                                                         ProjectError, "항등식"))
    check("--for: 목표가 다르면 거부", raises(lambda: p.est("I c Y", part="demand:CN"), ProjectError, "목표가 CN"))
    check("이름 겹침은 거부", raises(lambda: p.est("CN c Y", as_name="cn_file"), RecordError, "이미 있는 기록"))
    check("추정할 수 없는 식", raises(lambda: p.est("CN c NOPE"), ProjectError, "추정할 수 없습니다"))
    check("글·사전(식 직렬화는 빼고)", r1.text().startswith("[est:cn_file] OLS CN · 1970Q2~2019Q4 · n=199")
          and "equation" not in r1.to_dict() and "기록   est:cn_file" in r1.text())
    check("명령·누가 기본", r1.meta["command"] == "est demand:CN" and r1.meta["who"] in ("python", "claude"))

    print("=" * 80)
    print("E. 채택")
    print("=" * 80)
    before_line = read(os.path.join(d, "EQUATIONS", "demand.txt"))
    ad = quiet(p.adopt, "est:cn_alt")
    after_line = read(os.path.join(d, "EQUATIONS", "demand.txt"))
    check("블록 파일: 그 줄만 바꾸고 설명은 그대로", ad.line_changed and "CN c Y(-1) CN(-1)   # 소비" in after_line
          and after_line.replace("CN c Y(-1) CN(-1)   # 소비", "") == before_line.replace("CN c Y CN(-1)            # 소비", ""),
          after_line.splitlines()[1])
    check("채택표", p.adopted == {"demand:CN": "est:cn_alt"} and read(os.path.join(d, "EQUATIONS", "adopted.toml")).startswith("# 채택표"))
    ch = p.history.get(ad.change)
    check("바뀜 기록(두 파일·명령)", set(ch.files) == {"EQUATIONS/demand.txt", "EQUATIONS/adopted.toml"} and ch.how == "adopt est:cn_alt")
    mo = quiet(p.model, "core")
    eqo = [e for e in mo.equations if e.target == "CN"][0]
    check("모형: 채택 계수를 그대로(다시 추정 없음)", np.array_equal(eqo.coefs.to_numpy(), r2.coefs.to_numpy())
          and any("채택 계수: demand:CN(est:cn_alt)" in n for n in p.notes))
    ad2 = quiet(p.adopt, "est:cn_file")
    check("다시 채택: 전 기록·줄 되돌림", ad2.previous == "est:cn_alt" and "CN c Y CN(-1)   # 소비" in read(os.path.join(d, "EQUATIONS", "demand.txt")))
    check("채택: 다른 목표·항등식·부품 모름", raises(lambda: p.adopt("est:inv_a", part="demand:CN"), ProjectError, "목표")
          and raises(lambda: p.adopt("est:cn_file", part="demand:Y"), ProjectError, "항등식"))
    write(os.path.join(d, "EQUATIONS", "demand.txt"),
          read(os.path.join(d, "EQUATIONS", "demand.txt")).replace("CN c Y CN(-1)   # 소비", "CN c Y   # 소비"))
    p._reset()
    quiet(p.model, "core")
    check("블록 파일과 채택 기록의 글자가 다르면 알리고 지금 자료로 추정",
          any("demand:CN: 채택 기록 est:cn_file의 식이 블록 파일과 다릅니다" in n for n in p.notes))
    p.history.scan()                       # 명령(est·hs·adopt·history list …)이 부를 때 바깥 고침을 적는다
    hist = p.history.list()
    check("바깥 고침도 바뀜 기록에", hist[-1].who == "바깥" and "EQUATIONS/demand.txt" in hist[-1].files, hist[-1].text())
    quiet(p.history.revert, hist[-1].id, "python")
    p._reset()
    check("되돌리기로 채택 글자로", p.part("demand:CN").text == "CN c Y CN(-1)")

    print("=" * 80)
    print("F. 비교")
    print("=" * 80)
    cp = p.compare(part="demand:CN")
    check("후보 표: 부품의 후보 전부·채택 표시", set(cp.table.index) >= {"est:cn_file", "est:cn_alt", "est:cn_iv", "est:cn_short"}
          and cp.table.loc["est:cn_file", "채택"] == "★" and "기준" in cp.table.columns)
    check("경고: 표본이 다름", any("표본이 달라" in w for w in cp.warnings))
    cp2 = p.compare("est:cn_file", "est:inv_a")
    check("경고: 종속변수가 다름", any("종속변수가 달라" in w for w in cp2.warnings))
    check("섞인 종류는 거부", raises(lambda: p.compare("est:cn_file", "hs:hs_0001"), Exception))
    check("견줄 기록 없음", raises(lambda: p.compare(target="NOPE"), ProjectError, "견줄 기록"))
    check("글·사전", "[compare] 추정 기록" in cp.text() and json.loads(json.dumps(cp.to_dict(), default=str))["kind"] == "est")

    print("=" * 80)
    print("G. HS 기록")
    print("=" * 80)
    q, dq = new_project(tmp, "hsp")
    h1 = quiet(q.hs, "main", record=True)
    asm = h1.record.read_json("assembly.json")
    check("HS 기록: 구간·상태·RMSPE", (h1.start, h1.end) == ("2005Q1", "2019Q4") and h1.counts()["ok"] == 60
          and list(h1.meta["rmspe"])[:2] == ["Y", "CN"])
    check("조립 명세: 식 글자·계수·자료 회차·정의 파일 해시", asm["format"] == "equion-assembly" and len(asm["parts"]) == 6
          and all(x.get("saved") for x in asm["parts"] if x["kind"] == "equation") and asm["data"]["kind"] == "vintage"
          and asm["data"]["id"] == q.vintage and "EQUATIONS/demand.txt" in asm["files"] and "equion.toml" in asm["files"])
    check("알아서 한 것: 구간 풀기·지금 자료로 추정", any("2005Q1:last → 2005Q1~2019Q4" in x for x in h1.meta["implicit"])
          and any("채택 기록 없이" in x for x in h1.meta["implicit"]))
    check("기록 파일", all(os.path.isfile(h1.record.file(f)) for f in
                       ("assembly.json", "stats.csv", "solved.csv", "status.csv", "series.csv", "summary.md")))
    vcsv = os.path.join(dq, "work", "data", q.vintage, "series.csv")
    wfd = quiet(eqn.wfopen, vcsv, freq="Q")
    mm = quiet(lambda: wfd.model("chk").merge("CN c Y CN(-1)", "I c Y(-1) R", "dlog(P) c dlog(Y) dlog(POIL)",
                                              "RL c R RL(-1)", "log(M2) c log(P) log(Y) RL log(M2(-1))")
               .append("Y = CN + I + G"))
    sol = quiet(mm.solve, "2005Q1", "2019Q4").values
    hv = h1.solved
    dmax = max(float(np.nanmax(np.abs(hv[v].to_numpy() - sol[v].to_numpy()))) for v in ("CN", "I", "Y", "P", "RL", "M2"))
    check("HS 기록의 해 = 워크파일 API로 직접 푼 해", dmax < 1e-9, f"{dmax:.2e}")
    rc = quiet(q.est, "CN c Y(-1) CN(-1)", as_name="c3")
    h2 = quiet(q.hs, "main", record=True, swap={"demand:CN": "est:c3"}, vs=h1.id)
    eqs = [x for x in h2.record.read_json("assembly.json")["parts"] if x["id"] == "demand:CN"][0]
    check("바꿔 끼우기(기록): 그 기록의 계수·출처", eqs["source"] == "swap:est:c3" and eqs["text"] == "CN c Y(-1) CN(-1)"
          and eqs["saved"]["regression_results"]["coefficients"] == rc.meta["equation"]["regression_results"]["coefficients"])
    check("바꿔 끼우기: 파일은 그대로", q.part("demand:CN").text == "CN c Y CN(-1)" and q.adopted == {})
    check("전후 비교(vs)", h2.meta["vs"]["id"] == h1.id and h2.meta["vs"]["rmspe"]["CN"][0] == h1.meta["rmspe"]["CN"]
          and h2.meta["vs"]["rmspe"]["CN"][1] == h2.meta["rmspe"]["CN"] and "비교   vs hs:hs_0001" in h2.text())
    h3 = quiet(q.hs, "main", record=True, swap={"demand:CN": "CN c Y"})
    e3 = [x for x in h3.record.read_json("assembly.json")["parts"] if x["id"] == "demand:CN"][0]
    check("바꿔 끼우기(식 글자): 지금 자료로 추정", e3["source"] == "swap" and h3.meta["swaps"] == {"demand:CN": '"CN c Y"'})
    hb = quiet(q.hs, "demand", record=True)
    check("블록 HS 기록", hb.meta["model"] == "demand" and hb.counts()["ok"] == 60 and set(hb.meta["rmspe"]) == {"CN", "I", "Y"})
    # 파일을 바꾼 뒤에도 그대로 다시
    quiet(q.adopt, "est:c3")
    write(os.path.join(dq, "EQUATIONS", "price.txt"), "P c P(-1) POIL\n")
    q._reset()
    rp = quiet(q.replay, h1.id)
    check("그때 그대로 다시: 파일을 바꾼 뒤에도 같은 결과", rp.meta["replay"]["same"] and rp.meta["replay"]["of"] == h1.id
          and rp.meta["replay"]["max_abs_diff"] < 1e-9 and rp.meta["vs"]["id"] == h1.id, str(rp.meta["replay"]))
    rp2 = quiet(q.replay, h2.id)
    check("그때 그대로 다시(바꿔 끼운 기록)", rp2.meta["replay"]["same"] and rp2.meta["swaps"] == {"demand:CN": "est:c3"})
    new = pd.read_csv(os.path.join(dq, "DATA", "raw", "toy_q.csv"), index_col=0)
    new.loc["2020Q1"] = new.iloc[-1] * 1.01
    new.to_csv(os.path.join(tmp, "toy_q_new.csv"))
    quiet(q.data_add, os.path.join(tmp, "toy_q_new.csv"), source="na")
    quiet(q.data_build, use=True)
    rp3 = quiet(q.replay, h1.id)
    check("그때 그대로 다시: 지금 회차가 달라도 기록의 회차로", rp3.meta["replay"]["same"] and rp3.meta["data"]["id"] == h1.meta["data"]["id"]
          and rp3.end == "2019Q4")
    fp = os.path.join(tmp, "filemode")
    os.makedirs(os.path.join(fp, "EQUATIONS"))
    shutil.copyfile(eqn.datasets.path("toy_q"), os.path.join(fp, "data.csv"))
    write(os.path.join(fp, "EQUATIONS", "b.txt"), "CN c Y CN(-1)\nI c Y(-1) R\nY = CN + I + G\n")
    write(os.path.join(fp, "equion.toml"), '[data]\nfile = "data.csv"\n[block]\nb = "EQUATIONS/b.txt"\n[model.m]\nblocks = ["b"]\n')
    f = quiet(Project.open, fp)
    hf = quiet(f.hs, "m", record=True, start="2010Q1", end="2019Q4")
    check("자료 파일 프로젝트: 해시를 남긴다", hf.meta["data"]["kind"] == "file" and len(hf.meta["data"]["sha256"]) == 64)
    write(os.path.join(fp, "data.csv"), read(os.path.join(fp, "data.csv")).replace("\n2019Q4,", "\n2019Q4,1"), )
    check("자료가 바뀌면 다시 돌리지 않는다", raises(lambda: f.replay(hf.id), ProjectError, "기록 때와 다릅니다"))
    check("HS 기록: 글·사전", h1.text().startswith("[hs:hs_0001] main dynamic 2005Q1~2019Q4 · 정상 60")
          and h1.to_dict()["counts"]["ok"] == 60)
    cph = q.compare(h1.id, h2.id)
    check("HS 기록 비교: 변수별 RMSPE", list(cph.table.columns) == [h1.id, h2.id] and "CN" in cph.table.index)

    print("=" * 80)
    print("H. 명령줄")
    print("=" * 80)
    _, dc = new_project(tmp, "clip")
    code, out, _ = run(["est", "demand:CN", "--as", "c1", "--sim"], dc)
    check("est(0)", code == 0 and out.startswith("[est:c1] OLS CN") and "단독 모의" in out and "열기" not in out)
    code, out, _ = run(["est", "CN c Y(-1) CN(-1)", "--as", "c3", "--json"], dc)
    j = json.loads(out)
    check("est --json", code == 0 and j["id"] == "est:c3" and j["part"] == "demand:CN" and "equation" not in j
          and j["command"] == "equion est 'CN c Y(-1) CN(-1)' --as c3 --json")
    code, _, err = run(["est", "demand:Y"], dc)
    check("est: 항등식(3)", code == 3 and "항등식" in err)
    code, _, err = run(["est", "CN c Y", "--as", "c1"], dc)
    check("est: 이름 겹침(3)", code == 3 and "이미 있는 기록" in err)
    code, out, _ = run(["compare", "--part", "demand:CN"], dc)
    check("compare(0)", code == 0 and "est:c1" in out and "est:c3" in out)
    code, out, _ = run(["hs"], dc)
    check("hs(0): 기본 모형", code == 0 and out.startswith("[hs:hs_0001] main dynamic"))
    code, out, _ = run(["hs", "--swap", "demand:CN=est:c3", "--vs", "hs:hs_0001"], dc)
    check("hs --swap --vs(0)", code == 0 and "바꿔 끼움  demand:CN ← est:c3" in out and "비교   vs hs:hs_0001" in out)
    code, _, err = run(["hs", "--swap", "demand:CN"], dc)
    check("hs --swap 꼴(3)", code == 3 and "부품=값" in err)
    code, _, err = run(["hs", "--swap", "demand:CN=est:none"], dc)
    check("hs --swap 없는 기록(3)", code == 3 and "없는 기록" in err)
    code, out, _ = run(["hs", "--replay", "hs:hs_0002", "--json"], dc)
    check("hs --replay --json", code == 0 and json.loads(out)["replay"]["same"] is True)
    code, _, err = run(["hs", "main", "--replay", "hs:hs_0002"], dc)
    check("hs --replay는 기록 하나만(3)", code == 3 and "--replay" in err)
    code, out, _ = run(["adopt", "est:c3"], dc)
    check("adopt(0)", code == 0 and "[adopt] demand:CN ← est:c3" in out)
    code, out, _ = run(["work", "list"], dc)
    check("work list: 채택·기준 표시", code == 0 and "★채택" in out and "est:c1" in out and "hs:hs_0003" in out)
    code, out, _ = run(["work", "list", "--kind", "hs", "--json"], dc)
    check("work list --kind --json", code == 0 and [x["id"] for x in json.loads(out)] == ["hs:hs_0001", "hs:hs_0002", "hs:hs_0003"])
    code, out, _ = run(["work", "show", "est:c3"], dc)
    check("work show", code == 0 and out.startswith("[est:c3]") and "카드   work/est/c3/summary.md" in out)
    code, out, _ = run(["work", "show", "hs:hs_0002", "--md"], dc)
    check("work show --md", code == 0 and out.startswith("# 과거 재현 hs:hs_0002"))
    code, _, _ = run(["work", "pin", "hs:hs_0002"], dc)
    code2, out, _ = run(["work", "clean"], dc)
    check("work clean: 미리보기·채택·고정·참조는 남김", code == 0 and code2 == 0 and "미리보기" in out and "hs:hs_0002" not in out
          and "est:c3" not in out and "  hs:hs_0001" not in out and "est:c1" in out, out)
    code, out, _ = run(["work", "clean", "--yes"], dc)
    check("work clean --yes", code == 0 and not os.path.isdir(os.path.join(dc, "work", "est", "c1"))
          and os.path.isdir(os.path.join(dc, "work", "est", "c3")))
    code, out, _ = run(["history", "list"], dc)
    check("history list", code == 0 and "equion adopt est:c3" in out and "data use" in out)
    hid = [ln.split("]")[0][1:] for ln in out.splitlines() if "equion adopt est:c3" in ln][0]
    code, out, _ = run(["history", "show", hid], dc)
    check("history show: 차이", code == 0 and "+CN c Y(-1) CN(-1)" in out)
    code, out, _ = run(["history", "revert", hid], dc)
    check("history revert", code == 0 and "되돌림" in out and quiet(Project.open, dc).adopted == {}
          and quiet(Project.open, dc).part("demand:CN").text == "CN c Y CN(-1)")
    code, _, err = run(["work", "show", "est:none"], dc)
    check("없는 기록(3)", code == 3 and "없는 기록" in err)
    code, _, err = run(["history", "show", "h0999"], dc)
    check("없는 바뀜(3)", code == 3 and "없는 바뀜" in err)
    code, _, _ = run(["work"], dc)
    check("work: 동작 없음(3)", code == 3)

    print("=" * 80)
    print("I. 장면 2 — 소비함수 고르기(명령만으로)")
    print("=" * 80)
    _, ds = new_project(tmp, "scene2")
    run(["est", "CN c Y CN(-1)", "--as", "cons_c1", "--sim"], ds)
    run(["est", "CN c Y CN(-1) CN(-2)", "--as", "cons_c2", "--sim"], ds)
    for k, spec in enumerate(["CN c Y(-1) CN(-1)", "log(CN) c log(Y) log(CN(-1))", "dlog(CN) c dlog(Y) log(CN(-1)/Y(-1))",
                              "CN c Y Y(-1) CN(-1)", "CN c Y R CN(-1)"], 3):
        run(["est", spec, "--as", f"cons_c{k}", "--sim"], ds)
    code, out, _ = run(["compare", "--part", "demand:CN", "--json"], ds)
    rows = json.loads(out)["rows"]
    passed = [r["기록"] for r in rows if r.get("기준") == "통과"]
    check("후보 일곱·기준으로 거름(까닭과 함께 남는다)", code == 0 and len(rows) == 7 and 0 < len(passed) < 7
          and all(r["기준"].startswith("걸러짐:") for r in rows if r["기록"] not in passed), str(passed))
    best = min((r for r in rows if r["기록"] in passed), key=lambda r: r["단독 RMSPE%"])["기록"]
    code, out, _ = run(["hs"], ds)
    code2, out2, _ = run(["hs", "--swap", f"demand:CN={best}", "--vs", "hs:hs_0001", "--json"], ds)
    hj = json.loads(out2)
    check("이 후보로 HS(파일은 그대로) — 전후 비교", code == 0 and code2 == 0 and hj["vs"]["id"] == "hs:hs_0001"
          and quiet(Project.open, ds).part("demand:CN").text == "CN c Y CN(-1)")
    code, out, _ = run(["adopt", best], ds)
    pr = quiet(Project.open, ds)
    check("채택: 블록 파일 1줄·채택표·바뀜 기록", code == 0 and pr.adopted == {"demand:CN": best}
          and pr.part("demand:CN").text == quiet(pr.work.get, best).meta["text"]
          and pr.history.list()[-1].how == f"equion adopt {best}")
    code, out, _ = run(["hs", "--vs", "hs:hs_0002"], ds)
    check("채택 뒤 HS = 바꿔 끼운 HS(같은 계수)", code == 0 and "RMSPE 그대로" in out, out.splitlines()[2] if out else "")
    code, out, _ = run(["work", "list", "--json"], ds)
    recs = json.loads(out)
    check("남는 것: 후보 기록 7·HS 기록 3·바뀜 기록", sum(r["id"].startswith("est:") for r in recs) == 7
          and sum(r["id"].startswith("hs:") for r in recs) == 3 and len(pr.history.list()) >= 2)

    print()
    print(f"결과: {len(PASS)}/{len(PASS) + len(FAIL)} 통과 ({time.time() - t0:.1f}초)")
    if FAIL:
        print("실패:", ", ".join(FAIL))
    return len(FAIL)


def test_suite():
    """pytest 진입점 — 이 파일의 검사 묶음 전체(하나라도 실패하면 실패). `python tests/test_work.py`와 같은 검사."""
    assert main() == 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(99)
