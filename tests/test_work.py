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
  J. 전망(sim): 가정 세트·채우기·보정항 규칙(last·decay·mean)·판단 값·시나리오(충격·보정)·기준선 대비·값의 종류·연간·
     --vs·--vintage·워크파일 API로 직접 푼 전망과 같은 해·문제(없는 시나리오·가정 기간·채우지 않음)
  K. 다시 추정(est --adopted): 정책 never · if_pass(걸린 식은 옛 계수) · all · 계수 변화
  L. 제안(propose): 만들기(파일은 그대로)·카드·낡음·적용(바뀜 기록)·버림(기록은 남는다)
  M. 내보내기(export --xlsx): 출처 시트·기록별 시트·자료 회차
  N. 장면 4(HS가 나빠졌다 — 원인 따라가기와 제안)를 명령만으로
  O. 장면 5(분기 전망 — 새 자료 회차로 기준선 다시)를 명령만으로
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
    la, lb = after_line.split("\n"), before_line.split("\n")
    check("블록 파일: 그 줄만 바꾸고 설명은 그 자리 그대로", ad.line_changed and la[1] == "CN c Y(-1) CN(-1)        # 소비"
          and la[:1] + la[2:] == lb[:1] + lb[2:] and la[1].index("#") == lb[1].index("#"), la[1])
    check("채택표", p.adopted == {"demand:CN": "est:cn_alt"} and read(os.path.join(d, "EQUATIONS", "adopted.toml")).startswith("# 채택표"))
    ch = p.history.get(ad.change)
    check("바뀜 기록(두 파일·명령)", set(ch.files) == {"EQUATIONS/demand.txt", "EQUATIONS/adopted.toml"} and ch.how == "adopt est:cn_alt")
    mo = quiet(p.model, "core")
    eqo = [e for e in mo.equations if e.target == "CN"][0]
    check("모형: 채택 계수를 그대로(다시 추정 없음)", np.array_equal(eqo.coefs.to_numpy(), r2.coefs.to_numpy())
          and any("채택 계수: demand:CN(est:cn_alt)" in n for n in p.notes))
    ad2 = quiet(p.adopt, "est:cn_file")
    check("다시 채택: 전 기록·줄이 처음 그대로", ad2.previous == "est:cn_alt" and read(os.path.join(d, "EQUATIONS", "demand.txt")) == before_line)
    check("채택: 다른 목표·항등식·부품 모름", raises(lambda: p.adopt("est:inv_a", part="demand:CN"), ProjectError, "목표")
          and raises(lambda: p.adopt("est:cn_file", part="demand:Y"), ProjectError, "항등식"))
    write(os.path.join(d, "EQUATIONS", "demand.txt"),
          read(os.path.join(d, "EQUATIONS", "demand.txt")).replace("CN c Y CN(-1)            # 소비", "CN c Y   # 소비"))
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

    _sim_tests(tmp)
    _scene_tests(tmp)

    print()
    print(f"결과: {len(PASS)}/{len(PASS) + len(FAIL)} 통과 ({time.time() - t0:.1f}초)")
    if FAIL:
        print("실패:", ", ".join(FAIL))
    return len(FAIL)


def _sim_tests(tmp):
    print("=" * 80)
    print("J. 전망(sim)")
    print("=" * 80)
    p, d = new_project(tmp, "simp")
    r = quiet(p.sim, as_name="b1")
    m = r.meta
    lv, fl = r.levels, r.flags
    check("구간: [forecast] range(next:8)", m["range"] == ["2020Q1", "2021Q4"] and r.counts()["ok"] == 8)
    a = pd.read_csv(os.path.join(d, "ASSUMPTIONS", "base.csv"), index_col=0)
    check("가정 세트: 값·값의 종류 '가정'", np.allclose(lv.loc["2020Q1":"2021Q4", "POIL"], a.loc["2020Q1":"2021Q4", "POIL"])
          and (fl.loc["2020Q1":"2021Q4", "G"] == "가정").all() and m["assume"]["cells"] == 16)
    check("채우기 규칙(last): 정책금리 '채움'", (fl.loc["2020Q1":"2021Q4", "R"] == "채움").all()
          and np.allclose(lv.loc["2020Q1":"2021Q4", "R"], lv.loc["2019Q4", "R"]) and m["assume"]["filled"] == {"R": 8})
    check("실측은 그대로 · 해는 '해'", (fl.loc["2019Q4"] == "실측").all() and (fl.loc["2020Q1", ["Y", "CN", "P"]] == "해").all())
    mo = quiet(p.model, "main")
    cn_eq = next(o for o in mo.equations if o.target == "CN")
    last = float(cn_eq.eq.residual_series().loc[pd.Timestamp("2019-10-01")])
    afc = r.record.read_csv("addfactors.csv")
    check("보정항 last = 전망 앞 마지막 잔차", abs(m["addfactors"]["eqs"]["demand:CN"]["value"] - last) < 1e-9
          and np.allclose(afc["demand:CN"], last), f"{last:.4f}")
    i_eq = next(o for o in mo.equations if o.target == "I")
    li = float(i_eq.eq.residual_series().loc[pd.Timestamp("2019-10-01")])
    check("보정항 decay(반감기 4)", np.allclose(afc["demand:I"].to_numpy(), [li * 0.5 ** ((k + 1) / 4) for k in range(8)]))
    check("보정항 없는 식은 0", (afc["price:P"] == 0).all() and m["addfactors"]["eqs"]["price:P"]["rule"] == "zero")
    ann = r.annual
    yv = lv["Y"].astype(float)
    g20 = 100 * (yv.loc["2020Q1":"2020Q4"].mean() / yv.loc["2019Q1":"2019Q4"].mean() - 1)
    check("연간 평균·증가율", list(ann.index) == ["2020", "2021"] and abs(ann.loc["2020", "Y_증가율"] - g20) < 1e-9)
    check("기록 파일·카드", all(os.path.isfile(r.record.file(f)) for f in ("assembly.json", "levels.csv", "flags.csv", "growth.csv",
                                                                     "annual.csv", "addfactors.csv", "summary.md"))
          and r.diff is None and "## 연간 평균과 증가율" in r.record.summary_md())
    check("전망 뒤 자료의 끝(last)은 그대로", p.span("last:last") == ("2019Q4", "2019Q4"))
    o = quiet(p.sim, "oil20", as_name="o1")
    dfo = o.diff
    check("시나리오: 기준선도 풀어 차이(P 높다·실물 그대로)", o.meta["vs_base"]["P"] > 0 and abs(o.meta["vs_base"]["Y"]) < 1e-9
          and (dfo["P_%"] > 0).all() and o.meta["scenario_def"]["shocks"][0]["var"] == "POIL")
    b_lv = o.levels
    check("시나리오의 기준선 = 기준선 기록", np.allclose(b_lv["P"].loc["2020Q1":] / (1 + dfo["P_%"] / 100), lv["P"].loc["2020Q1":]))
    write(os.path.join(d, "SCENARIOS", "cnaf.toml"),
          'desc = "소비 보정"\n[[addfactor]]\neq = "demand:CN"\nfrom = "start"\nto = "start+1"\nvalue = -2\n')
    c2 = quiet(p.sim, "cnaf", as_name="c1")
    dcn = c2.diff["CN_차이"]
    check("시나리오 보정항(start~start+1)", dcn.iloc[0] < -1 and dcn.iloc[1] < -1 and abs(dcn.iloc[2]) < abs(dcn.iloc[1]))
    vs = quiet(p.sim, as_name="b2", vs="sim:b1")
    check("--vs: 연간 증가율 전후(그대로)", vs.meta["vs"]["id"] == "sim:b1" and "연간 증가율 그대로" in vs.text())
    # 판단 값 · mean 규칙
    write(os.path.join(d, "ADDFACTORS", "base.toml"), read(os.path.join(d, "ADDFACTORS", "base.toml"))
          + '\n[eq."price:P"]\nrule = "mean"\nn = 4\n')
    txt = read(os.path.join(d, "ADDFACTORS", "base.toml")).replace('default = "zero"', 'default = "zero"\nvalues = "ADDFACTORS/base.csv"')
    write(os.path.join(d, "ADDFACTORS", "base.toml"), txt)
    write(os.path.join(d, "ADDFACTORS", "base.csv"), "period,demand:CN\n2020Q1,-0.2\n")
    j = quiet(p.sim, as_name="j1")
    afj = j.record.read_csv("addfactors.csv")
    p_eq = next(o_ for o_ in quiet(p.model, "main").equations if o_.target == "P")
    rs = p_eq.eq.residual_series()
    mean4 = float(rs.loc[:pd.Timestamp("2019-10-01")].dropna().iloc[-4:].mean())
    check("보정항 판단 값이 규칙 값을 덮는다 · mean(n=4)", afj.loc["2020Q1", "demand:CN"] == -0.2 and afj.loc["2020Q2", "demand:CN"] == last
          and np.allclose(afj["price:P"], mean4) and j.meta["addfactors"]["judgment"] == 1
          and "보정항 판단 값 1칸" in j.meta["implicit"])
    # 워크파일 API와 같은 해(가정·보정항 없이, 채우기 last)
    q, dq = new_project(tmp, "simq")
    os.remove(os.path.join(dq, "ASSUMPTIONS", "base.csv"))
    os.remove(os.path.join(dq, "ADDFACTORS", "base.toml"))
    rq = quiet(q.sim, as_name="plain")
    wfd = quiet(eqn.wfopen, os.path.join(dq, "work", "data", q.vintage, "series.csv"), freq="Q")
    mm = quiet(lambda: wfd.model("chk").merge("CN c Y CN(-1)", "I c Y(-1) R", "dlog(P) c dlog(Y) dlog(POIL)",
                                              "RL c R RL(-1)", "log(M2) c log(P) log(Y) RL log(M2(-1))")
               .append("Y = CN + I + G"))
    fr = quiet(mm.forecast, "2020Q1", "2021Q4", exog_fill="last").values
    dm = max(float(np.max(np.abs(rq.levels.loc["2020Q1":, v].to_numpy(dtype=float) - fr[v].to_numpy()))) for v in ("Y", "P", "M2"))
    check("전망 = 워크파일 API로 직접 푼 전망(가정·보정항 없음, last)", dm < 1e-9 and rq.meta["assume"]["file"] is None, f"{dm:.2e}")
    write(os.path.join(dq, "ASSUMPTIONS", "base.csv"), "period,POIL,ZZ\n2019Q4,1\n2020Q1,70\n")
    rw = quiet(q.sim, as_name="warn")
    check("가정: 모형에 없는 변수·전망 앞 기간은 쓰지 않고 알린다", any("ZZ" in x and "쓰지 않음" in x for x in rw.meta["implicit"])
          and any("전망 앞 기간" in x for x in rw.meta["implicit"]) and rw.levels.loc["2019Q4", "POIL"] != 1)
    write(os.path.join(dq, "ASSUMPTIONS", "base.csv"), "period,POIL\n2020Q9,70\n")
    check("가정: 기간으로 읽을 수 없으면 위치와 함께", raises(lambda: q.sim(), ProjectError, "ASSUMPTIONS/base.csv:2"))
    os.remove(os.path.join(dq, "ASSUMPTIONS", "base.csv"))
    write(q.config.path, read(q.config.path).replace('fill = "last"', 'fill = "none"'))
    q._reset()
    check("채우지 않으면(fill none) 빈 외생을 알린다", raises(lambda: q.sim(), ProjectError, "외생변수 값이 없습니다"))
    check("없는 시나리오", raises(lambda: q.sim("nope"), ProjectError, "시나리오가 없습니다"))
    check("이름 겹침", raises(lambda: p.sim(as_name="b1"), RecordError, "이미 있는 기록"))
    # --vintage
    new = pd.read_csv(os.path.join(d, "DATA", "raw", "toy_q.csv"), index_col=0)
    new.loc["2020Q1"] = new.iloc[-1] * 1.004
    new.to_csv(os.path.join(tmp, "simp_new.csv"))
    quiet(p.data_add, os.path.join(tmp, "simp_new.csv"), source="na")
    v_old = p.vintage
    quiet(p.data_build, use=True)
    rn = quiet(p.sim, as_name="n1")
    ro = quiet(p.sim, as_name="old1", vintage=v_old)
    check("새 회차: 구간이 따라 움직인다(next:8)", rn.meta["range"] == ["2020Q2", "2022Q1"])
    check("--vintage: 옛 회차로(지금 회차는 그대로)", ro.meta["range"] == ["2020Q1", "2021Q4"] and ro.meta["data"]["id"] == v_old
          and quiet(Project.open, d).vintage != v_old)
    code, out, _ = run(["sim", "base", "oil20", "--json"], d)
    js = json.loads(out)
    check("명령줄 sim 여럿(0)", code == 0 and [x["scenario"] for x in js] == ["base", "oil20"])
    code, _, err = run(["sim", "base", "oil20", "--as", "x"], d)
    check("명령줄 sim --as는 하나만(3)", code == 3 and "--as" in err)
    code, _, err = run(["sim", "nope"], d)
    check("명령줄 없는 시나리오(3)", code == 3 and "시나리오가 없습니다" in err)

    print("=" * 80)
    print("K. 다시 추정(est --adopted)")
    print("=" * 80)
    k, dk = new_project(tmp, "reest")
    r0 = quiet(k.reestimate, "main", adopt="never")
    check("never: 기록만(채택표 그대로)", len(r0.rows) == 5 and k.adopted == {} and r0.change is None
          and all(x["new"].startswith("est:") for x in r0.rows))
    r1 = quiet(k.reestimate, "main", adopt="if_pass")
    ok_parts = [x["part"] for x in r1.rows if x["passed"]]
    check("if_pass: 통과한 식만 채택·걸린 식은 표시", sorted(k.adopted) == sorted(ok_parts) and r1.flagged
          and set(r1.flagged).isdisjoint(k.adopted) and r1.change is not None)
    hist = k.history.get(r1.change)
    check("정책 채택은 바뀜 기록 하나(정책 이름)", list(hist.files) == ["EQUATIONS/adopted.toml"] and "정책 if_pass가 채택" in hist.note)
    new = pd.read_csv(os.path.join(dk, "DATA", "raw", "toy_q.csv"), index_col=0)
    new.loc[new.index[-8:], "I"] *= 1.03
    new.to_csv(os.path.join(tmp, "reest_new.csv"))
    quiet(k.data_add, os.path.join(tmp, "reest_new.csv"), source="na")
    quiet(k.data_build, use=True)
    r2 = quiet(k.reestimate, "demand", adopt="all")
    ri = next(x for x in r2.rows if x["part"] == "demand:I")
    check("all: 새 자료로 다시 추정·계수 변화", ri["adopted"] and ri["old"] == k.adopted.get("demand:I") is not None or
          (ri["max_change_pct"] is not None and ri["max_change_pct"] > 0), str(ri))
    check("all: 채택표가 새 기록으로", k.adopted["demand:I"] == ri["new"] and k.adopted["demand:CN"] == r2.rows[0]["new"])
    code, out, _ = run(["est", "--adopted", "--adopt", "if_pass"], dk)
    check("명령줄 est --adopted(0)", code == 0 and out.startswith("[est --adopted] main · 정책 if_pass: 식 5"))
    code, _, err = run(["est", "--adopted", "--as", "x"], dk)
    check("est --adopted에 --as는 거부(3)", code == 3 and "--adopted" in err)
    code, _, err = run(["est", "demand:CN", "--adopt", "all"], dk)
    check("--adopt는 --adopted와 함께(3)", code == 3 and "--adopted" in err)
    check("없는 정책", raises(lambda: k.reestimate(adopt="sometimes"), ProjectError, "never"))

    print("=" * 80)
    print("L. 제안(propose)")
    print("=" * 80)
    g, dg = new_project(tmp, "prop")
    before = read(os.path.join(dg, "EQUATIONS", "price.txt"))
    ec = quiet(g.est, "dlog(P) c dlog(Y) dlog(POIL) dlog(P(-1))", as_name="p_lag")
    hp = quiet(g.hs, "main", record=True, swap={"price:P": "est:p_lag"}, as_name="prev")
    pr = quiet(g.propose, title="물가에 시차", why="hs:prev", parts={"price:P": "est:p_lag"}, previews=["hs:prev"])
    check("만들기: 파일은 그대로·이름 p1·바꿀 파일", pr.id == "prop:p1" and read(os.path.join(dg, "EQUATIONS", "price.txt")) == before
          and set(pr.meta["files"]) == {"EQUATIONS/price.txt", "EQUATIONS/adopted.toml"} and pr.status == "open")
    check("카드·차이", os.path.isfile(os.path.join(pr.path, "proposal.md")) and "+dlog(P) c dlog(Y) dlog(POIL) dlog(P(-1))" in pr.diff()
          and "```diff" in read(os.path.join(pr.path, "proposal.md")))
    check("없는 미리 계산 기록·바꿀 것 없음", raises(lambda: g.propose(parts={"price:P": "est:p_lag"}, previews=["hs:none"]), RecordError)
          and raises(lambda: g.propose(), ProjectError, "바꿀 것이 없습니다"))
    p2 = quiet(g.propose, "p_stale", parts={"price:P": "dlog(P) c dlog(Y)"})
    write(os.path.join(dg, "EQUATIONS", "price.txt"), before + "# 주석 한 줄\n")
    check("낡음: 만든 뒤 바뀐 파일", p2.stale == ["EQUATIONS/price.txt"])
    check("낡은 제안은 적용하지 않는다", raises(lambda: g.apply_proposal("p_stale"), ProjectError, "낡았습니다"))
    write(os.path.join(dg, "EQUATIONS", "price.txt"), before)
    ap = quiet(g.apply_proposal, "p1")
    g2 = quiet(Project.open, dg)
    check("적용: 블록 파일·채택표·바뀜 기록", ap.status == "applied" and g2.part("price:P").text == "dlog(P) c dlog(Y) dlog(POIL) dlog(P(-1))"
          and g2.adopted == {"price:P": "est:p_lag"} and g2.history.get(ap.meta["decided"]["change"]).how == "propose apply p1")
    dp = quiet(g.drop_proposal, "p_stale", why="설명할 수 없다")
    check("버림: 상태·기록은 남는다", dp.status == "dropped" and os.path.isdir(dp.path) and len(g.proposals()) == 2)
    check("이미 정한 제안", raises(lambda: g.apply_proposal("p1"), ProjectError, "열린 제안만"))
    p3 = quiet(g.propose, parts={"price:P": "dlog(P) c dlog(Y)"})
    write(os.path.join(dg, "EQUATIONS", "price.txt"), "dlog(P) c dlog(Y) dlog(POIL)\n")
    ap3 = quiet(g.apply_proposal, p3.name, force=True)
    check("--force: 낡은 채로 적용(표시)", ap3.status == "applied" and "낡은 채로" in ap3.meta["decided"]["note"]
          and "price:P" not in quiet(Project.open, dg).adopted)
    code, out, _ = run(["propose", "list"], dg)
    check("명령줄 propose list", code == 0 and "prop:p1" in out and "적용" in out and "버림" in out)
    code, out, _ = run(["propose", "new", "--part", "demand:CN=CN c Y", "--title", "t"], dg)
    check("명령줄 propose new(0)", code == 0 and "[prop:p3]" in out and "카드" in out)
    code, out, _ = run(["propose", "show", "p3"], dg)
    check("명령줄 propose show: 차이", code == 0 and "+CN c Y                   # 소비" in out)
    code, _, err = run(["propose", "apply", "p99"], dg)
    check("명령줄 없는 제안(3)", code == 3 and "없는 제안" in err)
    code, _, err = run(["propose", "new", "--file", "../x.txt=" + os.path.join(dg, "equion.toml")], dg)
    check("--file은 프로젝트 안", code == 3 and "상대 경로" in err)

    print("=" * 80)
    print("M. 내보내기(export --xlsx)")
    print("=" * 80)
    out = g.export([hp.id, ec.id, "data:" + g.vintage], "exports/x.xlsx")
    import openpyxl
    wb = openpyxl.load_workbook(out["path"], read_only=True)
    names = wb.sheetnames
    prov = list(wb["출처"].iter_rows(values_only=True))
    check("시트: 출처·기록별·자료 회차", names[0] == "출처" and "prev_적합도" in names and "p_lag_계수" in names
          and f"{g.vintage}_값의종류" in names and [r_[0] for r_ in prov[1:]] == [hp.id, ec.id, "data:" + g.vintage])
    wb.close()
    check("엑셀 이름·없는 기록", raises(lambda: g.export([hp.id], "x.csv"), ProjectError, ".xlsx")
          and raises(lambda: g.export(["hs:none"], "y.xlsx"), RecordError))
    code, out_, _ = run(["export", hp.id, "--xlsx", "exports/y.xlsx"], dg)
    check("명령줄 export(0)", code == 0 and out_.startswith("[export] exports/y.xlsx") and os.path.isfile(os.path.join(dg, "exports", "y.xlsx")))


def _scene_tests(tmp):
    print("=" * 80)
    print("N. 장면 4 — HS가 나빠졌다(원인 따라가기와 제안)")
    print("=" * 80)
    _, d = new_project(tmp, "scene4")
    run(["hs", "--as", "ok"], d)
    write(os.path.join(d, "EQUATIONS", "price.txt"), "# 물가 블록\ndlog(P) c dlog(POIL)      # 물가 — 수요를 뺐다\n")
    code, out, _ = run(["hs", "--vs", "hs:ok", "--as", "bad", "--json"], d)
    j = json.loads(out)
    p_ok, p_bad = j["vs"]["rmspe"]["P"]
    check("HS가 나빠졌다(P RMSPE)·풀이 상태는 정상", code == 0 and p_bad > p_ok and j["counts"]["ok"] == 60, f"{p_ok:.2f} → {p_bad:.2f}")
    code, out, _ = run(["hs", "price", "--as", "price_only", "--json"], d)
    jb = json.loads(out)
    check("블록 HS: 물가 블록만 풀어도 어긋난다(블록 안의 문제)", code == 0 and jb["rmspe"]["P"] > p_ok * 0.9, f"{jb['rmspe']['P']:.2f}")
    run(["est", "dlog(P) c dlog(POIL) @step(2008Q3)", "--as", "pa"], d)
    run(["est", "dlog(P) c dlog(Y) dlog(POIL)", "--as", "pb"], d)
    code_a, out_a, _ = run(["hs", "--swap", "price:P=est:pa", "--vs", "hs:bad", "--as", "prev_a", "--json"], d)
    code_b, out_b, _ = run(["hs", "--swap", "price:P=est:pb", "--vs", "hs:bad", "--as", "prev_b", "--json"], d)
    ja, jb2 = json.loads(out_a), json.loads(out_b)
    check("두 후보를 바꿔 끼워 미리 HS", code_a == 0 and code_b == 0 and ja["vs"]["id"] == "hs:bad"
          and jb2["rmspe"]["P"] < p_bad and jb2["swaps"] == {"price:P": "est:pb"})
    run(["propose", "new", "p2", "--title", "2008년 더미", "--why", f"hs:prev_a — P RMSPE {p_bad:.2f}% → {ja['rmspe']['P']:.2f}%",
         "--part", "price:P=est:pa", "--preview", "hs:prev_a"], d)
    run(["propose", "new", "p3", "--title", "유가를 다시 넣기", "--why", f"hs:prev_b — P RMSPE {p_bad:.2f}% → {jb2['rmspe']['P']:.2f}%",
         "--part", "price:P=est:pb", "--preview", "hs:prev_b"], d)
    before = read(os.path.join(d, "EQUATIONS", "price.txt"))
    check("제안 둘 — 파일은 그대로", before.count("dlog(P) c dlog(POIL)      # 물가") == 1)
    code, out, _ = run(["propose", "apply", "p3"], d)
    code2, out2, _ = run(["propose", "drop", "p2", "--why", "2008년 더미의 경제적 뜻을 설명할 수 없다"], d)
    pr = quiet(Project.open, d)
    hist = pr.history.list()
    check("적용 1·버림 1 — 블록 파일 변경과 바뀜 기록", code == 0 and code2 == 0 and pr.part("price:P").text == "dlog(P) c dlog(Y) dlog(POIL)"
          and pr.adopted == {"price:P": "est:pb"} and any(h.who == "바깥" and "EQUATIONS/price.txt" in h.files for h in hist)
          and hist[-1].how == "equion propose apply p3" and "버림" in out2)
    code, out, _ = run(["hs", "--vs", "hs:prev_b"], d)
    check("적용 뒤 HS = 미리 계산한 HS", code == 0 and "RMSPE 그대로" in out)
    code, out, _ = run(["work", "clean"], d)
    check("정리: 제안이 미리 계산한 기록은 남김", code == 0 and "hs:prev_a" not in out and "hs:prev_b" not in out and "est:pa" not in out)

    print("=" * 80)
    print("O. 장면 5 — 분기 전망(새 자료 회차로 기준선 다시)")
    print("=" * 80)
    _, d = new_project(tmp, "scene5")
    code, out, _ = run(["sim", "--as", "2026-10_base"], d)
    check("지난달 기준선", code == 0 and "[sim:2026-10_base]" in out)
    raw = pd.read_csv(os.path.join(d, "DATA", "raw", "toy_q.csv"), index_col=0)
    raw.loc[raw.index[-4:], "CN"] *= 1.006
    raw.loc["2020Q1"] = raw.iloc[-1] * 1.005
    new = os.path.join(tmp, "na_2026-11.csv")
    raw.to_csv(new)
    c1, _, _ = run(["data", "add", new, "--source", "na"], d)
    c2, out2, _ = run(["data", "build", "--use", "--json"], d)
    c3, out3, _ = run(["data", "diff", "--json"], d)
    dj = json.loads(out3)
    cn = next(x for x in dj["changes"] if x["시리즈"] == "CN")
    check("새 원자료 → 새 회차·개정 4분기와 새 기간", c1 == c2 == c3 == 0 and cn["개정"] == 4 and cn["새 값"] == 1)
    code, out, _ = run(["work", "list"], d)
    check("지난달 기록에 '회차 다름'(다시 계산은 저절로 하지 않는다)", code == 0 and "회차 다름" in out)
    a = pd.read_csv(os.path.join(d, "ASSUMPTIONS", "base.csv"), index_col=0)
    a["POIL"] = a["POIL"] * 1.05
    a.to_csv(os.path.join(d, "ASSUMPTIONS", "base.csv"), lineterminator="\n")
    write(os.path.join(d, "ADDFACTORS", "base.toml"),
          read(os.path.join(d, "ADDFACTORS", "base.toml")).replace('default = "zero"', 'default = "zero"\nvalues = "ADDFACTORS/judge.csv"'))
    write(os.path.join(d, "ADDFACTORS", "judge.csv"), "period,demand:CN\n2020Q2,-0.2\n")
    code, out, _ = run(["sim", "--as", "2026-11_base", "--vs", "sim:2026-10_base", "--json"], d)
    s5 = json.loads(out)
    check("새 기준선: 구간·가정·채움·보정항 규칙 값·판단 값", code == 0 and s5["range"] == ["2020Q2", "2022Q1"]
          and s5["assume"]["filled"] == {"R": 8} and s5["addfactors"]["judgment"] == 1
          and any(x.startswith("보정항 규칙 값") for x in s5["implicit"]))
    check("회차 비교: 지난달과 연간 증가율", s5["vs"]["id"] == "sim:2026-10_base" and "2021" in s5["vs"]["growth"]
          and s5["vs"]["growth"]["2021"]["Y"][0] is not None)
    code, out, _ = run(["sim", "--vintage", s5["vs"] and json.loads(run(["data", "list", "--json"], d)[1])[0]["id"],
                        "--as", "split_data", "--json"], d)
    sd = json.loads(out)
    check("나눠 보기: 옛 회차로 같은 가정(지금 회차는 그대로)", code == 0 and sd["range"] == ["2020Q1", "2021Q4"]
          and quiet(Project.open, d).vintage == s5["data"]["id"])
    hs_ = quiet(Project.open, d).history.list()
    check("가정 CSV·보정항 변경은 바뀜 기록에('바깥')", any(h.who == "바깥" and "ASSUMPTIONS/base.csv" in h.files for h in hs_)
          and any("ADDFACTORS/base.toml" in h.files for h in hs_))
    code, out, _ = run(["export", "sim:2026-11_base", "sim:2026-10_base", "--xlsx", "exports/전망.xlsx"], d)
    check("엑셀로", code == 0 and os.path.isfile(os.path.join(d, "exports", "전망.xlsx")))
    code, out, _ = run(["work", "list", "--kind", "sim", "--json"], d)
    check("남는 것: 전망 기록 3", code == 0 and [x["id"] for x in json.loads(out)] == ["sim:2026-10_base", "sim:2026-11_base",
                                                                                   "sim:split_data"])


def test_suite():
    """pytest 진입점 — 이 파일의 검사 묶음 전체(하나라도 실패하면 실패). `python tests/test_work.py`와 같은 검사."""
    assert main() == 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(99)
