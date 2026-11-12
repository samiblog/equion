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
  P. 고친 결함: 되돌리기는 그 바뀜만(뒤의 바뀜과 겹치면 멈춤·--force) · 정리는 번호를 다시 쓰지 않고 정의·채택표의 지난 판이
     가리키는 기록을 지킨다 · 다시 추정은 채택 기록대로(표본·공분산, 식이 다르면 알림) · 검정 없는 기준은 '판단 못 함' ·
     전망의 빈 값(연간 표는 변수마다) · 항등식 보정·구간 밖 충격은 입력 오류
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
    c4 = h.write_files({"EQUATIONS/b.txt": "CN c Y\n", "EQUATIONS/c.txt": "I c Y\n"}, "claude", "두 파일을 함께 고침")
    c5 = h.revert(c4.id, "desk", files=["EQUATIONS/c.txt"])
    check("되돌리기(파일 하나만): 고른 파일만 앞 내용으로 — 다른 파일은 그대로, 무엇을 물렸는지 메모에 남는다",
          not os.path.exists(os.path.join(hr, "EQUATIONS", "c.txt")) and read(os.path.join(hr, "EQUATIONS", "b.txt")) == "CN c Y\n"
          and list(c5.files) == ["EQUATIONS/c.txt"] and c5.reverts == c4.id and "EQUATIONS/c.txt만" in c5.note)
    n_hist = len(h.list())
    check("되돌리기(파일 하나만): 그 바뀜이 고친 파일이 아니면 KeyError — 아무것도 쓰지 않는다",
          raises(lambda: h.revert(c4.id, "desk", files=["EQUATIONS/zz.txt"]), KeyError, "고친 파일이 아닙니다") and len(h.list()) == n_hist
          and h.revert(c4.id, "desk", files=["EQUATIONS/c.txt"]) is None)

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
    rh = quiet(p.est, "demand:CN", as_name="cn_hac", cov="hac")
    from equion.projects.records import est_text
    check("계수 공분산: 보통이면 기록의 cov는 None, 견고한 것을 고르면 종류·이름·시차를 기록·카드·짧은 글에(계수는 같다)",
          m["cov"] is None and "계수 공분산" not in r1.record.summary_md() and "공분산" not in est_text(m)
          and rh.meta["cov"]["type"] == "hac" and "HAC" in rh.meta["cov"]["label"] and rh.meta["cov"]["lags"] >= 1
          and "| 계수 공분산 | HAC" in rh.record.summary_md() and "[공분산 HAC" in est_text(rh.meta)
          and np.allclose(rh.coefs.to_numpy(), r1.coefs.to_numpy(), rtol=1e-12, atol=0)
          and rh.meta["coefs"][1]["se"] != m["coefs"][1]["se"], str(rh.meta.get("cov")))
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
    pc = quiet(Project.open, dc)
    two = pc.history.write_files({"EQUATIONS/demand.txt": read(os.path.join(dc, "EQUATIONS", "demand.txt")) + "# 메모\n",
                                  "SCENARIOS/x1.toml": 'desc = "x"\n'}, "claude", "두 파일")
    code, out, _ = run(["history", "revert", two.id, "--file", "SCENARIOS/x1.toml", "--json"], dc)
    j = json.loads(out) if code == 0 else {}
    code2, _, err2 = run(["history", "revert", two.id, "--file", "equion.toml"], dc)
    check("history revert --file: 그 파일만 되돌린다(0) · 그 바뀜이 고친 파일이 아니면 3",
          list(j.get("files") or {}) == ["SCENARIOS/x1.toml"] and j.get("reverts") == two.id and not os.path.exists(os.path.join(dc, "SCENARIOS", "x1.toml"))
          and read(os.path.join(dc, "EQUATIONS", "demand.txt")).endswith("# 메모\n") and code2 == 3 and "고친 파일이 아닙니다" in err2, out[:200] + err2[:200])
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
    _fix_tests(tmp)
    _concurrency_tests(tmp)
    _fixf_tests(tmp)

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
    check("시나리오의 수준: 충격을 준 외생은 푼 그 경로(기준선의 가정 × 1.2)로 — 전망 앞과 다른 외생은 그대로",
          np.allclose(b_lv["POIL"].loc["2020Q1":], 1.2 * lv["POIL"].loc["2020Q1":]) and np.allclose(b_lv["POIL"].loc[:"2019Q4"], lv["POIL"].loc[:"2019Q4"])
          and np.allclose(b_lv["G"], lv["G"]) and list(o.record.read_csv("flags.csv")["POIL"].loc["2020Q1":].unique()) == ["가정"])
    from equion.projects.notes import stale_reasons
    fresh = stale_reasons(p, o.record)
    p.view_define("core_view", series=["Y", "P"], show="yoy")
    check("보기(VIEWS/)는 계산의 입력이 아니다 — 보기를 저장해도 기록이 낡지 않고 조립 명세에도 들지 않는다",
          fresh == [] and stale_reasons(p, o.record) == [] and not any(k.startswith("VIEWS/") for k in quiet(p.sim, "base", as_name="b_view").record.read_json("assembly.json")["files"]))
    hs_rec = p.work.get(quiet(p.hs, "main", record=True).id)
    af = os.path.join(d, "ASSUMPTIONS", "base.csv")
    kept = read(af)
    write(af, kept.replace("2020Q1,", "2020Q1,1", 1))
    s_hs, s_sim = stale_reasons(p, hs_rec), stale_reasons(p, o.record)
    write(af, kept)
    check("가정·보정항·시나리오는 전망만 읽는다 — 가정을 고치면 전망 기록은 낡고 과거 재현 기록은 낡지 않는다",
          s_hs == [] and len(s_sim) == 1 and "ASSUMPTIONS/base.csv" in s_sim[0] and stale_reasons(p, o.record) == [], str(s_hs) + str(s_sim))
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
    check("가정 세트·보정항: 이름을 적었는데([forecast] assume = \"base\") 파일이 없으면 'base'도 다른 이름처럼 오류 — 할 일과 함께(fixF)",
          raises(lambda: q.sim(as_name="noas"), ProjectError, "[forecast] assume"))
    cfgq = os.path.join(dq, "equion.toml")
    NL = chr(10)
    write(cfgq, NL.join(x for x in read(cfgq).split(NL) if not x.startswith(("assume ", "addfactors "))))
    q = quiet(Project.open, dq)
    rq = quiet(q.sim, as_name="plain")
    check("가정 세트를 적지 않고 base.csv도 없으면 가정 없이 — '알아서 한 것'에 그렇다고", any("가정 세트 없음" in x for x in rq.meta["implicit"]),
          str(rq.meta["implicit"])[:300])
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


def _fix_tests(tmp):
    print("=" * 80)
    print("P. 고친 결함 — 되돌리기·정리·다시 추정·판단 기준·전망")
    print("=" * 80)
    from equion.work.history import RevertConflict, merge_revert
    hr = os.path.join(tmp, "hist_merge")
    write(os.path.join(hr, "equion.toml"), '[project]\nname = "h"\n\n[data]\nvintage = "d1"\n\n[model.core]\nblocks = ["demand"]\n\n'
          '[model.main]\ninclude = ["core"]\n\n[group]\ncore = { series = ["Y"] }\n')
    h = History(hr)
    h.scan()

    def cfg():
        return read(os.path.join(hr, "equion.toml"))
    c1 = h.write_files({"equion.toml": cfg().replace("[group]", '[model.mx]\nblocks = ["demand", "price"]\n[group]')}, "terminal",
                       "equion model define mx")
    h.write_files({"equion.toml": cfg().replace('vintage = "d1"', 'vintage = "d2"')}, "terminal", "equion data use d2")
    c3 = h.write_files({"equion.toml": cfg().replace('core = { series = ["Y"] }', 'core = { series = ["Y"] }\ngx = { series = ["CN"] }')},
                       "terminal", "equion group define gx")
    r1 = h.revert(c1.id, "terminal")
    check("되돌리기는 그 바뀜만 — 뒤의 바뀜(회차 바꾸기·묶음)은 그대로, 메모에 그대로 둔 바뀜",
          "[model.mx]" not in cfg() and 'vintage = "d2"' in cfg() and "gx = " in cfg() and r1.reverts == c1.id
          and "그 바뀜만" in r1.note and c3.id in r1.note, cfg())
    r2 = h.revert(r1.id, "terminal")
    check("되돌리기의 되돌리기 — 그 바뀜이 다시 들어온다(뒤의 바뀜도 그대로)",
          r2.reverts == r1.id and "[model.mx]" in cfg() and 'vintage = "d2"' in cfg() and "gx = " in cfg(), cfg())
    c2 = [c for c in h.list() if c.how == "equion data use d2"][0]
    c4 = h.write_files({"equion.toml": cfg().replace('vintage = "d2"', 'vintage = "d3"')}, "terminal", "equion data use d3")
    n, before = len(h.list()), cfg()
    err = None
    try:
        h.revert(c2.id, "desk")
    except RevertConflict as e:
        err = e
    check("뒤의 바뀜이 같은 줄을 고쳤으면 멈춘다(ValueError) — 아무것도 쓰지 않고 뒤의 바뀜과 --force를 알린다",
          isinstance(err, ValueError) and err.change == c2.id and c4.id in err.files.get("equion.toml", [])
          and c4.id in str(err) and "--force" in str(err) and cfg() == before and len(h.list()) == n, str(err))
    r3 = h.revert(c2.id, "desk", force=True)
    check("force — 그 파일을 그 바뀜 앞 내용으로 통째로(뒤의 바뀜도 그 파일에서 함께 물림 — 메모에)",
          'vintage = "d1"' in cfg() and "gx = " not in cfg() and "--force" in r3.note and c4.id in r3.note, r3.note)
    c5 = h.write_files({"equion.toml": cfg().replace("[group]", '[model.my]\nblocks = ["price"]\n[group]')}, "terminal", "equion model define my")
    c6 = h.write_files({"equion.toml": cfg().replace('[model.my]\nblocks = ["price"]\n', '[model.my]\nblocks = ["price"]\ndesc = "x"\n')},
                       "terminal", "equion model define my --desc x")
    check("TOML은 키로도 본다 — 줄로는 물려지지만 뒤의 키가 다른 표에 붙게 되면 겹침",
          raises(lambda: h.revert(c5.id, "terminal"), RevertConflict, c6.id) and '[model.my]\nblocks = ["price"]\ndesc = "x"' in cfg())
    a = b"CN c Y\nI c Y\nY = CN + I\n"
    check("줄 합치기 — 바로 옆 줄을 고친 뒤의 바뀜은 겹침이 아니다 · 같은 줄을 고쳤으면 겹침",
          merge_revert(a, b"CN c Y CN(-1)\nI c Y\nY = CN + I\n", b"CN c Y\nI c Y R\nY = CN + I\n") == b"CN c Y CN(-1)\nI c Y R\nY = CN + I\n"
          and merge_revert(a, b"CN c Y CN(-1)\nI c Y\nY = CN + I\n", b"CN c Y Y(-1)\nI c Y\nY = CN + I\n") is None)

    p, d = new_project(tmp, "fixhist")
    quiet(p.est, "demand:CN", as_name="a1")
    ha = quiet(p.adopt, "est:a1").change
    quiet(p.est, "demand:I", as_name="i1")
    hi = quiet(p.adopt, "est:i1").change
    code, out, _ = run(["history", "revert", ha], d)
    check("채택표 — 처음 만든 채택(파일을 새로 만든 바뀜)을 되돌려도 뒤의 채택은 남는다(명령줄 0)",
          code == 0 and quiet(Project.open, d).adopted == {"demand:I": "est:i1"}, out)
    p = quiet(Project.open, d)
    quiet(p.est, "demand:I", as_name="i2")
    quiet(p.adopt, "est:i2")
    code, _, err = run(["history", "revert", hi], d)
    code2, out2, _ = run(["history", "revert", hi, "--force"], d)
    check("명령줄 — 겹치면 3(뒤의 바뀜·--force 안내, 그대로) · --force면 통째로(0)",
          code == 3 and "--force" in err and "adopt est:i2" in err and code2 == 0 and "--force" in out2
          and quiet(Project.open, d).adopted == {"demand:CN": "est:a1"}, err[:300])

    q, dq = new_project(tmp, "fixclean")
    quiet(q.est, "demand:CN")
    quiet(q.est, "demand:CN")
    quiet(q.an, "seas", "CN", model="multiplicative", as_name="s1")
    quiet(q.keep, "an:s1", as_name="CNSA_X")
    quiet(q.an, "genr", "GAP = Y - CN - I - G", as_name="g1")
    quiet(q.keep, "an:g1")
    quiet(q.an, "ecm", "CN Y", as_name="ec1")
    quiet(q.keep, "an:ec1", as_name="cons_ecm1")
    quiet(q.adopt, "est:cons_ecm1")
    quiet(q.an, "unitroot", "R", as_name="u1")
    quiet(q.est, "demand:I", as_name="ia")
    quiet(q.adopt, "est:ia")
    quiet(q.est, "demand:I", as_name="ib")
    quiet(q.adopt, "est:ib")
    code, out, _ = run(["work", "clean", "--json"], dq)
    gone = set(json.loads(out)["would_remove"]) if code == 0 else set()
    check("정리가 지키는 것 — 자료 정의의 made_by(an:s1)·파생식 주석(an:g1)·채택한 식을 낸 분석(an:ec1)·채택표의 지난 판(est:ia)",
          {"an:s1", "an:g1", "an:ec1", "est:ia", "est:ib", "est:cons_ecm1"}.isdisjoint(gone)
          and {"an:u1", "est:cn_0001", "est:cn_0002"} <= gone and q.work.get("est:cons_ecm1").meta.get("from") == "an:ec1", str(sorted(gone)))
    run(["work", "clean", "--yes"], dq)
    rn = quiet(quiet(Project.open, dq).est, "demand:CN")
    check("정리 뒤 새 기록은 지운 번호를 다시 쓰지 않는다(cn_0003)", rn.id == "est:cn_0003" and not q.work.exists("est", "cn_0001"), rn.id)

    k, dk = new_project(tmp, "fixreest")
    tsls = quiet(k.est, "CN c Y CN(-1) @inst CN(-1) G R", part="demand:CN", as_name="cn_tsls")
    nls = quiet(k.est, "CN = c(1) + c(2)*Y + c(3)*CN(-1)", part="demand:CN", as_name="cn_nls")
    ols = quiet(k.est, "demand:I", as_name="i_ols")
    check("판단 기준 — 기준의 검정(LM·RESET)을 이 추정법이 계산하지 않으면 '판단 못 함'(통과가 아니다) · c(n) 식은 기대 부호도 · OLS는 그대로",
          tsls.passed is None and tsls.meta["criteria"]["untested"] == ["LM(2)", "RESET"] and "판단 못 함" in tsls.text()
          and "TSLS에는 계산하지 않음" in tsls.text() and nls.passed is None and "Y 부호" in nls.meta["criteria"]["untested"]
          and "untested" not in ols.meta["criteria"] and ols.passed in (True, False), tsls.text())
    quiet(k.adopt, "est:cn_tsls")
    ism = quiet(k.est, "demand:I", smpl="1990Q1:last", cov="white", as_name="i_sm")
    quiet(k.adopt, "est:i_sm")
    rr = quiet(k.reestimate, "demand", adopt="if_pass")
    rc = next(x for x in rr.rows if x["part"] == "demand:CN")
    ri = next(x for x in rr.rows if x["part"] == "demand:I")
    ni = k.work.get(ri["new"]).meta
    check("if_pass — 판단 못 한 식은 채택하지 않고 표시(!) · 옛 계수 유지",
          not rc["adopted"] and rc["untested"] and rc["passed"] is None and "demand:CN" in rr.flagged
          and k.adopted["demand:CN"] == "est:cn_tsls" and "! demand:CN" in rr.text() and "기준 판단 못 함" in rr.text(), rr.text())
    check("다시 추정은 채택 기록대로(--smpl 1990Q1:last · --cov white) — 같은 자료면 계수 그대로",
          ni["smpl"] == "1990Q1:last" and ni["sample"][0] == "1990Q1" and (ni.get("cov") or {}).get("type") == ism.meta["cov"]["type"]
          and ri["max_change_pct"] is not None and ri["max_change_pct"] < 1e-6 and "채택 기록대로 표본 1990Q1:last" in rr.text(), rr.text())
    bf = os.path.join(dk, "EQUATIONS", "demand.txt")
    write(bf, read(bf).replace("CN c Y CN(-1) @inst CN(-1) G R", "CN c Y CN(-1) CN(-2)"))
    rm = quiet(quiet(Project.open, dk).reestimate, "demand", adopt="if_pass")
    rc2 = next(x for x in rm.rows if x["part"] == "demand:CN")
    check("채택 기록의 식이 블록 파일과 다르면 그렇다고 알리고 계수 변화를 견주지 않는다('옛 계수 유지'라 하지 않는다)",
          rc2.get("mismatch") and rc2["max_change_pct"] is None and "채택 기록의 식이 블록 파일과 다름" in rm.text()
          and ("옛 계수 유지" not in [ln for ln in rm.text().splitlines() if "demand:CN" in ln][0]), rm.text())

    s, ds = new_project(tmp, "fixsim")
    quiet(s.block_define, "badb")
    write(os.path.join(ds, "EQUATIONS", "badb.txt"), read(os.path.join(ds, "EQUATIONS", "badb.txt")) + "RL = exp(RL) + R\n")
    quiet(quiet(Project.open, ds).model_define, "bad", blocks=["demand", "badb"])
    s = quiet(Project.open, ds)
    sb = quiet(s.sim, model="bad", as_name="bad1")
    check("풀지 못한 변수 하나가 연간 표 전체를 비우지 않는다 — 그 변수만 빈칸, 실측이 없는데 '실측 대체'라 하지 않는다",
          sb.meta["unsolved"]["RL"]["n"] == 8 and sb.meta["annual"]["2021"]["Y"] is not None and sb.meta["annual"]["2021"]["RL"] is None
          and sb.flags["RL"].iloc[-1] == "결측" and not any("실측 대체 8기" in x for x in sb.meta["implicit"])
          and any("실측이 없어 빈 값: RL 8기" in x for x in sb.meta["implicit"]) and "! 풀지 못한 값  RL 8기" in sb.text(), sb.text())
    sn = quiet(s.sim, as_name="ok1")
    check("모두 푼 전망은 그대로 — 빈 값 없음(unsolved 없음)·연간 표가 다 찬다", "unsolved" not in sn.meta and len(sn.annual) == 2
          and sn.annual.notna().all().all())
    write(os.path.join(ds, "SCENARIOS", "idf.toml"), '[[addfactor]]\neq = "demand:Y"\nvalue = 5\n')
    write(os.path.join(ds, "SCENARIOS", "far.toml"), '[[shock]]\nvar = "POIL"\nfrom = "2030Q1"\nto = "2030Q4"\npct = 10\n')
    write(os.path.join(ds, "SCENARIOS", "half.toml"), '[[shock]]\nvar = "POIL"\nfrom = "2019Q1"\nto = "start+1"\npct = 10\n')
    code, _, err = run(["sim", "idf"], ds)
    code2, _, err2 = run(["sim", "far"], ds)
    code3, out3, _ = run(["sim", "half", "--json"], ds)
    check("손으로 쓴 시나리오 — 항등식에 식 보정·전망 구간 밖 충격은 풀기 전에 입력 오류(3), 일부만 밖이면 잘라 알린다(0)",
          code == 3 and "항등식" in err and "Traceback" not in err and code2 == 3 and "효과가 없습니다" in err2
          and code3 == 0 and any("전망 구간 밖은 뺌 → 2020Q1~2020Q2" in x for x in json.loads(out3)["implicit"]), err + err2)


def _parallel(cmds, proj, env_extra=None):
    """명령 여럿을 별도 프로세스(python -m equion)로 같은 순간에 → [(종료 코드, stdout, stderr)]."""
    import subprocess
    import threading
    env = dict(os.environ, PYTHONIOENCODING="utf-8", **(env_extra or {}))
    for k in ("CLAUDECODE", "EQUION_WHO", "EQUION_RUN"):
        env.pop(k, None)
    gate = threading.Barrier(len(cmds))
    out = [None] * len(cmds)

    def go(i):
        gate.wait()
        r = subprocess.run([sys.executable, "-m", "equion", *cmds[i], "-p", proj], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", env=env, cwd=ROOT)
        out[i] = (r.returncode, r.stdout, r.stderr)
    ts = [threading.Thread(target=go, args=(i,)) for i in range(len(cmds))]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    return out


class _Hold:
    """Windows에서 다른 프로그램처럼 파일을 쥔다 — share 'none'(독점) · 'read'(엑셀처럼 읽기만 허용)."""

    def __init__(self, path, share):
        import ctypes
        from ctypes import wintypes
        self.k = ctypes.WinDLL("kernel32", use_last_error=True)
        self.k.CreateFileW.restype = wintypes.HANDLE
        self.k.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD,
                                       wintypes.DWORD, wintypes.HANDLE]
        self.h = self.k.CreateFileW(path, 0x80000000 | 0x40000000, {"none": 0, "read": 1}[share], None, 3, 0x80, None)
        assert self.h not in (None, wintypes.HANDLE(-1).value), (path, ctypes.get_last_error())

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.k.CloseHandle(self.h)


def _leftovers(root):
    return [os.path.relpath(os.path.join(r, n), root) for r, ds, fs in os.walk(root) for n in ds + fs if ".tmp" in n]


def _concurrency_tests(tmp):
    print("=" * 80)
    print("Q. 같은 프로젝트를 한꺼번에 — 프로젝트 잠금 · 기록 이름 · 다른 프로그램이 쥔 파일 · 줄바꿈 · 전망 비교")
    print("=" * 80)
    from equion.work.lock import FileBusy, ProjectBusy, project_lock, replace_files
    p, d = new_project(tmp, "race")
    quiet(p.est, "CN c Y CN(-1) CN(-2)", part="demand:CN", as_name="cn2")
    quiet(p.est, "I c Y(-1) R I(-1)", part="demand:I", as_name="i2")
    quiet(p.est, "RL c R RL(-1) RL(-2)", part="finance:RL", as_name="rl2")
    h0 = [c.id for c in p.history.list()]
    res = _parallel([["adopt", "est:cn2"], ["adopt", "est:i2"], ["adopt", "est:rl2"]], d)
    dem, fin = read(os.path.join(d, "EQUATIONS", "demand.txt")), read(os.path.join(d, "EQUATIONS", "finance.txt"))
    adopted = Project.open(d).adopted
    h1 = [c.id for c in Project.open(d).history.list()]
    check("채택 셋을 같은 순간에(프로세스 셋) — 모두 0, 블록 파일의 줄·채택표 항목이 하나도 사라지지 않는다, 바뀜 기록 셋(번호가 겹치지 않음)",
          [r[0] for r in res] == [0, 0, 0] and "CN c Y CN(-1) CN(-2)" in dem and "I c Y(-1) R I(-1)" in dem
          and "RL c R RL(-1) RL(-2)" in fin and adopted == {"demand:CN": "est:cn2", "demand:I": "est:i2", "finance:RL": "est:rl2"}
          and len(h1) == len(h0) + 3 and len(set(h1)) == len(h1) and not _leftovers(d), [r[2][-300:] for r in res])
    cmds = [["est", "demand:CN"]] * 6 + [["sim", "base"]] * 2 + [["hs", "main"]] * 2
    res = _parallel(cmds, d)
    st = WorkStore(d)
    est = [n for n in st.names("est") if n.startswith("cn_")]
    ids = [x["id"] for x in st.log()]
    consistent = all(r.meta["id"] == r.id and r.meta.get("path") in (None, f"work/{r.kind}/{r.name}") and r.id in r.summary_md()
                     for r in st.records() if r.kind in ("est", "sim", "hs"))
    check("같은 추정 여섯·전망 둘·과거 재현 둘을 한꺼번에 — 모두 0, 이름이 모두 다르고(cn_0001~0006) log.jsonl 줄도 하나씩, 임시 폴더가 남지 않음",
          all(r[0] == 0 for r in res) and sorted(est) == [f"cn_{k:04d}" for k in range(1, 7)] and len(st.names("sim")) == 2
          and len(st.names("hs")) == 2 and len(ids) == len(set(ids)) and consistent and not _leftovers(d)
          and not any("Traceback" in r[2] for r in res), [r[2][-200:] for r in res if r[0]])
    with project_lock(d):
        res = _parallel([["adopt", "est:cn_0001"], ["work", "list"]], d, {"EQUION_LOCK_TIMEOUT": "1"})
        inner = quiet(Project.open(d).adopt, "est:cn_0002").part         # 같은 프로세스는 겹쳐 잡아도 된다(재진입)
    check("다른 명령이 잠금을 쥐고 있으면 기다리다 입력 오류(3) — 무엇이 막았는지 글로, 파일은 그대로 · 읽기만 하는 명령(work list)은 막지 않는다",
          res[0][0] == 3 and "다른 명령이 이 프로젝트를 고치는 중" in res[0][2] and "Traceback" not in res[0][2] and res[1][0] == 0
          and inner == "demand:CN", res[0][2][-300:])
    check("ProjectBusy·FileBusy는 입력 오류(ValueError) — 명령이 종료 코드 3으로 알린다", issubclass(ProjectBusy, ValueError)
          and issubclass(FileBusy, ValueError) and issubclass(FileBusy, PermissionError))
    # 파일 여럿을 한 묶음으로 — 하나를 바꾸지 못하면 이미 바꾼 것을 되돌린다
    fa, fb = write(os.path.join(tmp, "rb", "a.txt"), "a0\n"), write(os.path.join(tmp, "rb", "b.txt"), "b0\n")
    if os.name == "nt":
        with _Hold(fb, "read"):
            ok = raises(lambda: replace_files({fa: b"a1\n", fb: b"b1\n"}, root=os.path.join(tmp, "rb")), FileBusy, "b.txt")
        check("파일 여럿 바꾸기 — 둘째를 다른 프로그램이 쥐고 있으면 첫째도 전 내용으로 되돌리고 FileBusy(그 파일 이름), 임시 파일 없음",
              ok and read(fa) == "a0\n" and read(fb) == "b0\n" and not _leftovers(os.path.join(tmp, "rb")))
        _locked_file_tests(tmp)
    else:
        print("  (Windows가 아니라 다른 프로그램이 쥔 파일 시험은 건너뜀)")
    _eol_tests(tmp)
    code, out, err = run(["compare", "sim:" + st.names("sim")[0], "sim:" + st.names("sim")[1], "--json"], d)
    j = json.loads(out) if code == 0 else {}
    check("전망 기록 둘 견주기(compare sim:… sim:…) — 연간 증가율을 나란히·차이, 요인 나누기(an split) 안내", code == 0 and j.get("kind") == "sim"
          and any(r.get("연간 증가율%", "").startswith("Y ") for r in j["rows"]) and "차이" in j["rows"][0]
          and any("an split" in w for w in j["warnings"]), err[-300:])
    import warnings
    B, db = new_project(tmp, "bighs")
    eqs = "".join(f"Z{k:03d} = Y * {1 + k / 1000:.3f}\n" for k in range(120))
    write(os.path.join(db, "EQUATIONS", "big.txt"), eqs)
    with open(os.path.join(db, "DATA", "derived.txt"), "a", encoding="utf-8", newline="\n") as f:
        f.write(eqs)                                   # 실측도 있게 — 해·실측 표의 열이 120개를 넘는다
    cfg = os.path.join(db, "equion.toml")
    write(cfg, read(cfg).replace("[block]", '[block]\nbig = { file = "EQUATIONS/big.txt" }', 1) + '\n[model.bigm]\nblocks = ["demand", "big"]\n')
    B = quiet(Project.open, db)
    quiet(B.data_build, use=True)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        hb = quiet(B.hs, "bigm", record=True, as_name="big")
    perf = [w for w in caught if "PerformanceWarning" in w.category.__name__ and "records.py" in str(w.filename)]
    check("큰 모형(내생 120+)의 과거 재현 기록: records.py에서 PerformanceWarning이 나오지 않는다(해·실측 표를 한 번에)",
          not perf and "Z119_실측" in hb.record.read_csv("series.csv").columns, [str(w.message)[:80] for w in perf[:2]])


def _locked_file_tests(tmp):
    """다른 프로그램(엑셀·동기화·백신)이 정의 파일·log.jsonl을 쥐고 있을 때 — 반쯤 바뀐 채 남지 않고, 그 파일 이름과 함께 3."""
    from equion.work.lock import FileBusy
    p, d = new_project(tmp, "held")
    quiet(p.est, "CN c Y CN(-1) CN(-2)", part="demand:CN", as_name="cn2")
    quiet(p.est, "I c Y(-1) R I(-1)", part="demand:I", as_name="i2")
    quiet(p.adopt, "est:i2")
    dem, ado = os.path.join(d, "EQUATIONS", "demand.txt"), os.path.join(d, "EQUATIONS", "adopted.toml")
    n_hist = len(Project.open(d).history.list())
    env = {"EQUION_LOCK_TIMEOUT": "5"}
    d0, a0 = read(dem), read(ado)
    with _Hold(ado, "read"):
        r1 = _parallel([["adopt", "est:cn2"]], d, env)[0]
    check("채택표를 엑셀이 쥐고 있으면(읽기만 허용) 채택은 3 — 블록 파일도 그대로(되돌림), 바뀜 기록 없음, 임시 파일 없음, 까닭에 그 파일",
          r1[0] == 3 and "EQUATIONS/adopted.toml" in r1[2] and "다른 프로그램" in r1[2] and read(dem) == d0 and read(ado) == a0
          and len(Project.open(d).history.list()) == n_hist and not _leftovers(d), r1[2][-300:])
    with _Hold(dem, "none"):
        r2 = _parallel([["adopt", "est:cn2"]], d, env)[0]
    check("블록 파일을 독점으로 쥐고 있으면 채택은 '없는 부품'이 아니라 그 파일을 읽을 수 없다고(3)",
          r2[0] == 3 and "EQUATIONS/demand.txt" in r2[2] and "없는 부품" not in r2[2] and "Traceback" not in r2[2], r2[2][-300:])
    est0 = WorkStore(d).names("est")
    with _Hold(os.path.join(d, "work", "log.jsonl"), "read"):
        r3 = _parallel([["est", "demand:CN"]], d, env)[0]
    check("log.jsonl을 쥐고 있으면 추정은 3 — 기록 폴더도 남기지 않는다(목록에 없는 기록·잡힌 이름이 생기지 않게)",
          r3[0] == 3 and "work/log.jsonl" in r3[2] and WorkStore(d).names("est") == est0 and not _leftovers(d), r3[2][-300:])
    with _Hold(os.path.join(d, "ASSUMPTIONS", "base.csv"), "none"):
        r4 = _parallel([["hs", "main"]], d, env)[0]
    check("계산만 하는 명령(hs)은 바뀜 기록 검사가 읽지 못한 파일(가정 표)을 경고하고 건너뛴다 — 멈추지 않는다",
          r4[0] == 0 and "ASSUMPTIONS/base.csv" in r4[2] and "건너뜁니다" in r4[2] and "Traceback" not in r4[2], r4[2][-300:])
    rel = "ASSUMPTIONS/base.csv"
    old = read(os.path.join(d, rel))
    hist = Project.open(d).history
    with _Hold(os.path.join(d, rel), "read"):
        ok = raises(lambda: hist.write_files({rel: old.replace("1", "2", 1)}, "desk", "Desk 에서 고침(가정 표)"), FileBusy, rel)
    check("가정 표 저장(Desk가 쓰는 History.write_files) — 엑셀이 쥐고 있으면 FileBusy(읽을 수 있는 글), 임시 파일을 남기지 않는다",
          ok and read(os.path.join(d, rel)) == old and not _leftovers(d))


def _eol_tests(tmp):
    """줄바꿈(CRLF)만 바뀐 파일 — 차이는 '줄바꿈만', 되돌리기·채택이 지금 파일의 줄바꿈을 따른다."""
    p, d = new_project(tmp, "crlf")
    quiet(p.est, "CN c Y Y(-1) CN(-1)", part="demand:CN", as_name="c3")
    quiet(p.est, "I c Y(-1) R I(-1)", part="demand:I", as_name="i3")
    quiet(p.adopt, "est:c3")
    dem = os.path.join(d, "EQUATIONS", "demand.txt")
    with open(dem, "rb") as f:
        raw = f.read()
    with open(dem, "wb") as f:
        f.write(raw.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
    h = Project.open(d).history
    ch = h.scan()
    check("줄바꿈만 바뀐 파일 — 바깥 바뀜으로 적되 차이는 '줄바꿈만 바뀜'(모든 줄이 바뀐 것처럼 보이지 않게)",
          ch is not None and "줄바꿈만 바뀜(LF → CRLF)" in ch.diff and "+CN" not in ch.diff, ch.diff if ch else "")
    p2 = Project.open(d)
    a2 = quiet(p2.adopt, "est:i3")
    with open(dem, "rb") as f:
        b = f.read()
    diff = p2.history.get(a2.change).diff
    check("CRLF 블록 파일에 채택 — CRLF 그대로(명령이 고친 줄만 LF가 되지 않게), 차이는 고친 한 줄",
          b.count(b"\r\n") == b.count(b"\n") == 4 and diff.count("\n-I") == 1 and diff.count("\n+I") == 1 and "\n-CN" not in diff, diff)
    first = [c for c in p2.history.list() if c.how.startswith("adopt est:c3")][0]
    code, out, err = run(["history", "revert", first.id], d)
    with open(dem, "rb") as f:
        b = f.read()
    check("줄바꿈만 바뀐 뒤에도 앞의 채택을 되돌릴 수 있다 — 그 바뀜만(뒤의 채택은 그대로), 줄바꿈은 지금 파일(CRLF)대로",
          code == 0 and b"CN c Y CN(-1)" in b and b"I c Y(-1) R I(-1)" in b and b.count(b"\r\n") == b.count(b"\n"), err[-300:])


def _next_vintage(P, d, tmp, tag, factor=1.001):
    """원자료의 끝 값을 조금 고친 새 파일 → 새 회차(지금 회차로)."""
    import tomllib
    with open(os.path.join(d, "DATA", "series.toml"), "rb") as f:
        src = tomllib.load(f)["source"]["na"]["file"]
    raw = pd.read_csv(os.path.join(d, src), index_col=0)
    raw.loc[raw.index[-1], "Y"] *= factor
    f = os.path.join(tmp, f"{tag}.csv")
    raw.to_csv(f)
    quiet(P.data_add, f, source="na")
    quiet(P.data_build, use=True)
    return P.vintage


def _fixf_tests(tmp):
    print("=" * 80)
    print("Q. 보고서의 자료 회차 · 외생변수 행 · est에 이름 하나 · 선행변수(MCE) · 큰 모형의 경고 (fixF)")
    print("=" * 80)
    import re as _re
    import warnings
    P, d = new_project(tmp, "rep_vint")
    va = P.vintage
    vb = _next_vintage(P, d, tmp, "rv_b")
    quiet(P.sim, as_name="sb")
    quiet(P.hs, "main", record=True, as_name="hb")
    quiet(P.report_new, f"forecast_{vb}")
    rep = f"forecast_{vb}"
    quiet(P.report_add, rep, "sim:sb", rows=["Y", "G"], show="yoy", annual=True, key="growth")
    quiet(P.report_add, rep, "hs:hb", rows=["Y"], key="hs")
    quiet(P.data_use, va)                     # 옛 회차에 잠깐 다녀온다
    quiet(P.sim, as_name="sa")
    quiet(P.hs, "main", record=True, as_name="ha")
    quiet(P.data_use, vb)
    ck = quiet(P.report_check, rep)
    up = quiet(P.report_update, rep)
    body = read(os.path.join(d, "reports", f"{rep}.md"))
    check("보고서: 옛 회차에 다녀온 계산은 지금 회차 보고서의 '더 새 기록'이 아니다 — check 정상 · update 그대로(구역이 옛 회차 기록으로 바뀌지 않음)",
          all("더 새 기록" not in it["status"] for it in ck.items) and all(it["to"] == it["record"] for it in up.items)
          and _re.findall(r"data:(\S+)", " ".join(x for x in body.splitlines() if x.startswith("<!-- equion:report"))) == [vb, vb],
          str([(it["record"], it["status"]) for it in ck.items]))
    quiet(P.sim, as_name="sb2")                # 같은 회차에서 다시 — 이것은 바꿔 낀다
    up2 = quiet(P.report_update, rep, dry_run=True)
    check("보고서: 같은 회차에서 다시 한 전망은 '더 새 기록'(D66 그대로)", up2.items[0]["to"] == "sim:sb2", str([it["to"] for it in up2.items]))
    vc = _next_vintage(P, d, tmp, "rv_c", 1.002)
    quiet(P.sim, as_name="sc")
    quiet(P.hs, "main", record=True, as_name="hc")
    ck = quiet(P.report_check, rep)
    up = quiet(P.report_update, rep, dry_run=True)
    check("보고서: 몇 달 뒤 고쳐도 그 보고서 회차의 계산만 — 새 회차의 같은 계산은 '새 회차에 같은 계산'으로 알리고 --from을 권한다",
          all(it["to"] in ("sim:sb2", "hs:hb") for it in up.items) and all("새 회차에 같은 계산" in it["status"] for it in ck.items)
          and "--from" in ck.items[0]["detail"], str([(it["status"], it.get("detail", "")[:80]) for it in ck.items]))
    nr = quiet(P.report_new, f"forecast_{vc}", from_report=rep)
    up3 = quiet(P.report_update, f"forecast_{vc}")
    check("보고서: report new --from — 머리의 회차를 지금 회차로, update는 지금 회차의 기록으로",
          [it["to"] for it in up3.items] == ["sim:sc", "hs:hc"] and any(vc in x for x in nr.notes)
          and f"자료 회차 {vc}" in read(os.path.join(d, "reports", f"forecast_{vc}.md")), str([it["to"] for it in up3.items]))
    t = [x for x in body.split("**표 1.")[1].splitlines() if x.startswith("| G")]
    check("보고서: 전망의 외생변수(G) 행 — 연간 증가율도(수준에서 셈)", len(t) == 1 and _re.search(r"\d", t[0]) is not None, str(t))
    code, out, err = run(["report", "add", f"reports/{rep}.md", "sim:sb", "--rows", "Y,G", "--show", "yoy", "--title", "g"], d)
    code2, _, err2 = run(["report", "add", f"reports/{rep}.md", "sim:sb", "--rows", "Y,NOPE", "--show", "yoy"], d)
    quiet(P.sim, "oil20", as_name="oil")
    code3, _, err3 = run(["report", "add", f"reports/{rep}.md", "sim:oil", "--rows", "Y,POIL", "--show", "diff"], d)
    check("보고서: 외생 행의 전년동기비(0) · 없는 이름은 내생·외생 목록과 함께(3) · 외생의 기준선 대비는 알기 쉬운 글로(3) — 날것의 KeyError가 아니라",
          code == 0 and code2 == 3 and "NOPE" in err2 and "외생" in err2 and code3 == 3 and "외생변수" in err3
          and "_증가율" not in err2 + err3 and "_전년동기비" not in err2 + err3, (out[-200:], err2, err3))

    # est에 이름 하나
    c1, _, e1 = run(["est", "main"], d)
    c2, _, e2 = run(["est", "demand"], d)
    c3, _, e3 = run(["est", "CN"], d)
    check("est 모형·블록 이름 → --adopted를, 목표변수 → 부품(demand:CN)을 권한다(3) — '최소 2개 항'이 아니라",
          c1 == c2 == c3 == 3 and "--adopted" in e1 and "모형" in e1 and "블록" in e2 and "--adopted" in e2 and "demand:CN" in e3
          and "최소 2개" not in e1 + e2 + e3, e1 + e2 + e3)

    # 선행변수 — 명령줄의 MCE
    L, dl = new_project(tmp, "lead")
    write(os.path.join(dl, "EQUATIONS", "demand.txt"), "CN c Y CN(-1)\nI c Y(+1) R\nY = CN + I + G\n")
    code, out, err = run(["sim", "base", "--model", "core", "--json"], dl)
    r = json.loads(out)
    check("선행변수가 있는 전망: 정하지 않으면 Fair-Taylor MCE로 풀고(정상 8) '알아서 한 것'에 그렇다고 — 파이썬 API의 mce=True 처방은 보이지 않는다",
          code == 0 and r["counts"]["ok"] == 8 and r.get("mce") == "fair-taylor" and any("MCE" in x for x in r["implicit"])
          and "mce=True" not in out + err, (r.get("counts"), err[-200:]))
    code, out, _ = run(["sim", "base", "--model", "core", "--mce", "no", "--json"], dl)
    r2 = json.loads(out)
    check("--mce no: 선행 값을 고정 경로로 — 풀리지 않고 그 까닭을 '알아서 한 것'에", code == 0 and r2["counts"]["failed"] > 0
          and any("false" in x for x in r2["implicit"]), r2.get("counts"))
    code, out, err = run(["hs", "core", "--json"], dl)
    h = json.loads(out)
    code2, out2, _ = run(["hs", "core", "--mce", "stacked", "--json"], dl)
    h2 = json.loads(out2)
    asm = json.loads(read(os.path.join(dl, "work", "hs", h2["id"].split(":")[1], "assembly.json")))
    check("선행변수가 있는 과거 재현: 기본은 실측 선행 값(그렇다고 알림) · --mce stacked는 모형 일관 기대(조립 명세의 선택지 — --replay가 그대로)",
          code == code2 == 0 and any("실측" in x and "--mce" in x for x in h["implicit"]) and "mce=True" not in out + err
          and (asm.get("options") or {}).get("mce") is True and (asm.get("options") or {}).get("mce_method") == "stacked",
          (h["implicit"][-2:], asm.get("options")))
    cfg = os.path.join(dl, "equion.toml")
    write(cfg, read(cfg).replace('fill = "last"', 'fill = "last"\nmce = "stacked"', 1))
    code, out, _ = run(["sim", "base", "--model", "core", "--json"], dl)
    write(cfg, read(cfg).replace('mce = "stacked"', 'mce = "bogus"', 1))
    code2, _, err2 = run(["sim", "base", "--model", "core"], dl)
    check("[forecast] mce = \"stacked\"를 따른다 · 틀린 값은 equion.toml 문제(3)", code == 0 and json.loads(out).get("mce") == "stacked"
          and code2 == 3 and "mce" in err2 and "fair-taylor" in err2, err2[-200:])

    # 큰 모형 — 열을 하나씩 더하는 표의 PerformanceWarning이 전망에서 나오지 않는다
    B, db = new_project(tmp, "bigwarn")
    write(os.path.join(db, "EQUATIONS", "big.txt"), "".join(f"Z{k:03d} = Y * {1 + k / 1000:.3f}\n" for k in range(120)))
    cfg = os.path.join(db, "equion.toml")
    write(cfg, read(cfg).replace("[block]", '[block]\nbig = { file = "EQUATIONS/big.txt" }', 1) + '\n[model.bigm]\nblocks = ["demand", "big"]\n')
    B = quiet(Project.open, db)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        quiet(B.sim, model="bigm", as_name="big")
    perf = [w for w in caught if "PerformanceWarning" in w.category.__name__ and "sim.py" in str(w.filename)]
    check("큰 모형(내생 120+)의 전망: projects/sim.py에서 PerformanceWarning이 나오지 않는다(열을 모아 한 번에)", not perf,
          str([(w.filename, w.lineno) for w in perf[:3]]))


def test_suite():
    """pytest 진입점 — 이 파일의 검사 묶음 전체(하나라도 실패하면 실패). `python tests/test_work.py`와 같은 검사."""
    assert main() == 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(99)
