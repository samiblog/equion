#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_scenarios.py — 여러 상황(정상·경계·잘못된 입력·다른 주기·오용)을 상정한 시나리오 회귀 시험.

0.7.0 전 기능을 상황별로 두드려 찾은 결함과 그 고침을 고정한다. 한국 모델 자료 없이 합성 자료만 쓴다.
실행: uv run python tests/test_scenarios.py   (종료코드 = 실패 수)

  A. 자료 입력·워크파일: 빠진 기간·중복·정렬·기간 라벨 날짜, 예약 이름(C·LOG…), 분기 라벨 슬라이스, 다른 주기 표기, 페이지·read
  B. 추정: 선형 종속 경고, 완전 적합 진단 거부, 모순 Wald 제약, 작은 표본 검정, 가중치 형식
  C. 모델·시나리오: 풀이 옵션 검사, 조정항 대상, 빈 모델, 전망 시작 공백, 값 없는 기간 = 실패, 선행변수 경고,
     control·분해·승수·MCE, 결과 저장 폴더
  D. 시스템·VAR·VECM: 시차·중복·결정항·순위·예측 기간 검사, FIML 시작값, 실패한 재추정, 망가진 객체 건너뛰기
  E. 식 계산·변환·저장·출력: genr/eval 지시자, 쓰기 형식·폴더, 그래프 검사, 저장 경로, 전 객체 저장 왕복
  F. 명령줄: --run-id 경로, --format·--smpl·--interval 검사, .py만, 인코딩(coding 선언·cp949·BOM), 작업 폴더, 빈 식 파일
  G. 예제 자료: 4종의 모양·메타데이터, CSV = 만드는 코드, 참 계수 회복, 실제 Klein 파일 불러오기
  H. 기간 표기: 엔진 Model의 '2010Q1'·라벨 인덱스 시나리오 경로 저장 왕복이 pandas 시간 API 경고 없이(pandas 4 대비)
  I. 플랫폼에 따라 달라지지 않는 결과: 계열상관 LM 보조 회귀의 겹친 상수열, 켤레 근 순서, 0% 기여 변수 표시
  J. 예제 자료로 옮기며 찾은 결함: AR 오차의 단위근 오류 메시지, 시스템 Wald의 이미 넣은 제약(제약 하나)
"""

import contextlib
import io
import json
import logging
import os
import sys
import tempfile
import time
import traceback
import warnings

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import equion as eqn  # noqa: E402
from equion.cli.commands import main as cli  # noqa: E402
from equion.formula.parser import DSLError  # noqa: E402

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  — {detail}" if detail else ""))


def raises(fn, exc=Exception, contains=None):
    try:
        with contextlib.redirect_stdout(io.StringIO()), warnings.catch_warnings():
            warnings.simplefilter("ignore")
            fn()
    except exc as e:
        return contains is None or contains in str(e)
    except Exception:
        return False
    return False


def quiet(fn, *a, **k):
    with contextlib.redirect_stdout(io.StringIO()), warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return fn(*a, **k)


@contextlib.contextmanager
def logged():
    """'equion' 로거의 경고 이상을 모은다(→ 리스트)."""
    msgs = []

    class H(logging.Handler):
        def emit(self, record):
            msgs.append(record.getMessage())
    h = H(level=logging.WARNING)
    lg = logging.getLogger("equion")
    lg.addHandler(h)
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            yield msgs
    finally:
        lg.removeHandler(h)


@contextlib.contextmanager
def cwd(path):
    old = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old)


def run(args, where):
    out, err = io.StringIO(), io.StringIO()
    with cwd(where), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli(list(args))
    return code, out.getvalue(), err.getvalue()


def write(path, text, enc="utf-8"):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding=enc, newline="") as f:
        f.write(text)
    return path


def span(wf, name, a, b):
    """기간 라벨 구간의 값(pandas의 분기 문자열 해석에 기대지 않음 — pandas 4에서 사라짐)."""
    return wf.to_pandas([name], labels=True).loc[a:b, name]


def macro_wf(name="m", seed=3):
    """합성 분기 모델 자료: CN = 10 + 0.5·Y + 0.3·CN(-1), I = 5 + 0.15·Y(-1) − R, Y = CN + I + G, 물가 P."""
    rng = np.random.default_rng(seed)
    w = eqn.wfcreate(name, "Q", "1990Q1", "2019Q4")
    T = len(w.data)
    G = 20 + 0.2 * np.arange(T) + rng.normal(scale=1, size=T)
    R = 3 + np.cumsum(rng.normal(scale=0.1, size=T))
    C, I, Y, P = (np.zeros(T) for _ in range(4))
    C[0], I[0], P[0] = 150, 40, 100
    Y[0] = C[0] + I[0] + G[0]
    for t in range(1, T):
        e1, e2, e3 = rng.normal(scale=[0.5, 0.5, 0.002])
        I[t] = 5 + 0.15 * Y[t - 1] - R[t] + e2
        Y[t] = (10 + 0.3 * C[t - 1] + e1 + I[t] + G[t]) / 0.5
        C[t] = Y[t] - I[t] - G[t]
        P[t] = P[t - 1] * np.exp(0.005 + 0.3 * np.log(Y[t] / Y[t - 1]) + e3)
    for k, v in dict(G=G, R=R, CN=C, I=I, Y=Y, P=P).items():
        w[k] = v
    return w


def macro_model(w, name="mac"):
    eqs = [w.equation(n).ls(s) for n, s in (("eqc", "CN c Y CN(-1)"), ("eqi", "I c Y(-1) R"),
                                            ("eqp", "dlog(P) c dlog(Y)"))]
    return w.model(name).merge(*eqs).append("Y = CN + I + G")


def main():
    t0 = time.time()
    tmp = tempfile.mkdtemp(prefix="eqn-scen-")
    eqn.verbose(0)
    rng = np.random.default_rng(1)

    print("=" * 80)
    print("A. 자료 입력·워크파일")
    print("=" * 80)
    p = write(os.path.join(tmp, "gap.csv"), "date,X\n2000-01-01,1\n2000-04-01,2\n2000-10-01,4\n2001-01-01,5\n")
    w = quiet(eqn.wfopen, p)
    check("빠진 기간이 있는 분기 자료 → 빈 행으로 정규화(시차가 어긋나지 않음)",
          w.freq == "Q" and len(w.data) == 5 and np.isnan(w["X"].iloc[2]))
    p = write(os.path.join(tmp, "dup.csv"), "date,X\n2000-01-01,1\n2000-01-01,2\n2000-04-01,3\n")
    check("같은 날짜 두 번 → 오류", raises(lambda: eqn.wfopen(p), ValueError, "두 번"))
    p = write(os.path.join(tmp, "uns.csv"), "date,X\n2000-07-01,3\n2000-01-01,1\n2000-04-01,2\n")
    check("정렬 안 된 날짜 → 정렬", np.allclose(quiet(eqn.wfopen, p)["X"].to_numpy(), [1, 2, 3]))
    p = write(os.path.join(tmp, "lab.csv"), "period,X\n2000Q1,1\n2000Q2,2\n2000Q3,3\n")
    check("기간 라벨('2000Q1') 날짜 열", quiet(eqn.wfopen, p).freq == "Q")
    p = write(os.path.join(tmp, "yr.csv"), "year,X\n2000,1\n2001,2\n2002,3\n")
    check("연도 숫자 날짜 열 → 연간", quiet(eqn.wfopen, p).freq == "A")
    check("빈 파일 → 분명한 오류", raises(lambda: eqn.wfopen(write(os.path.join(tmp, "e.csv"), "")), ValueError, "빈 파일"))
    check("wfcreate 시작 > 끝 → 오류", raises(lambda: eqn.wfcreate("x", "Q", "2001Q1", "2000Q1"), ValueError))
    w = quiet(eqn.wfcreate, "a", "Q", "2000Q1", "2002Q4")
    quiet(w.genr, "K = 1")
    check("genr 상수식", np.allclose(w["K"].to_numpy(), 1.0))
    w["X"] = np.arange(12.0)
    check("분기 라벨 슬라이스(인덱스에 pandas freq 없음 — 회계 분기로 어긋나지 않음)",
          w.data.index.freq is None and w["X"].index.freq is None and w.elem("X", "2001Q2") == 5.0
          and list(span(w, "X", "2001Q2", "2001Q3")) == [5.0, 6.0])
    check("예약 이름 시리즈 C → 오류", raises(lambda: w.__setitem__("C", 1.0), ValueError, "상수항"))
    check("예약 이름 시리즈 LOG(genr) → 오류", raises(lambda: w.genr("LOG = 1"), ValueError, "함수"))
    check("식 안의 변수 C → 분명한 오류(상수항과 혼동 방지)",
          raises(lambda: w.equation("rc").ls("X c C"), DSLError, "상수항"))
    p = write(os.path.join(tmp, "res.csv"), "date,C,X\n2000-01-01,1,2\n2000-04-01,2,3\n2000-07-01,3,4\n")
    with warnings.catch_warnings(record=True) as ws, contextlib.redirect_stdout(io.StringIO()):
        warnings.simplefilter("always")
        eqn.wfopen(p)
    check("예약 이름 열이 든 파일 → 경고하고 연다", any("쓸 수 없는 열 이름" in str(x.message) for x in ws))
    wa = quiet(eqn.wfcreate, "aa", "A", "1990", "2000")
    check("연간에 분기 표기 smpl → 오류", raises(lambda: wa.smpl("1992Q1", "1995Q1"), ValueError, "분기"))
    wm = quiet(eqn.wfcreate, "mm", "M", "2010M1", "2012M12")
    wm["MX"] = rng.normal(size=36)
    wm["MY"] = wm["MX"] + rng.normal(size=36)
    check("월간 @d(2011Q2) → 오류", raises(lambda: wm.equation("d").ls("MY c MX @d(2011Q2)"), Exception, "분기"))
    pg = quiet(w.page, "mon", "M")
    check("분기 → 월 페이지: 마지막 분기의 세 달까지(2002M12)", pg._label(pg.index[-1]) == "2002M12" and len(pg.data) == 36)
    wsrc = quiet(eqn.wfcreate, "src", "Q", "2000Q1", "2004Q4")
    wsrc["V"] = np.arange(20.0)
    csv = quiet(wsrc.write, os.path.join(tmp, "새 폴더", "v 1.csv"))
    w2 = quiet(eqn.wfcreate, "r", "Q", "2002Q1", "2002Q4")
    with logged() as msgs:
        quiet(w2.read, csv)
    check("read: 뒤는 기간을 늘리고 앞은 경고(값은 기간에 맞게)",
          len(w2.data) == 12 and w2.elem("V", "2002Q1") == 8.0 and w2.elem("V", "2004Q4") == 19.0
          and any("앞의" in m for m in msgs))
    mcsv = quiet(pg.write, os.path.join(tmp, "m.csv"), ["X"]) if quiet(pg.__setitem__, "X", np.arange(36.0)) is None else None
    check("read: 다른 주기 파일 → 오류", raises(lambda: w2.read(mcsv), ValueError, "월"))
    check("read: 없는 열 → 오류", raises(lambda: w2.read(csv, ["NOPE"]), KeyError))
    rcsv = write(os.path.join(tmp, "rc.csv"), "date,C,V2\n2002-01-01,1,2\n2002-04-01,2,3\n2002-07-01,3,4\n")
    with logged() as msgs:
        got = quiet(w2.read, rcsv)
    check("read: 예약 이름 열은 건너뛰고 경고 · 직접 지정하면 오류", got == ["V2"] and any("읽지 않았습니다" in x for x in msgs)
          and raises(lambda: w2.read(rcsv, ["C"]), ValueError, "상수항"))

    print("\n" + "=" * 80)
    print("B. 추정")
    print("=" * 80)
    wb = quiet(eqn.wfcreate, "e", "Q", "1990Q1", "2019Q4")
    T = len(wb.data)
    x1 = rng.normal(size=T)
    wb["X1"] = x1
    wb["XC"] = 2 * x1
    wb["K5"] = 5.0
    wb["Y"] = 1 + 0.5 * x1 + rng.normal(scale=0.5, size=T)
    with logged() as msgs:
        e = quiet(wb.equation("col").ls, "Y c X1 XC")
    check("완전 공선 → 경고·통계·출력 표시", e.stats.get("collinear") == ["X1", "XC"]
          and "선형 종속" in e.output().text() and any("선형 종속" in m for m in msgs))
    check("상수 계열 + 상수항 → 공선 표시", quiet(wb.equation("col2").ls, "Y c K5 X1").stats.get("collinear") == ["const", "K5"])
    check("고정 계수 식에는 공선 경고 없음", "collinear" not in quiet(wb.equation("fx").fixed, "Y c X1", [1, 0.5]).stats)
    perf = quiet(wb.equation("perf").ls, "XC X1")
    check("완전 적합 → 잔차 검정 거부", raises(perf.diagnostics, ValueError, "완전 적합")
          and raises(perf.normality, ValueError, "완전 적합"))
    e = quiet(wb.equation("o").ls, "Y c X1")
    check("Wald: 서로 모순인 제약 → 오류", raises(lambda: e.wald("c(2) = 0", "c(2) = 1"), ValueError, "모순"))
    from equion.stats import diagnostics as D
    check("작은 표본: Ljung-Box·ARCH·BG 시차 → 분명한 오류",
          raises(lambda: D.ljung_box(np.ones(5), 10), ValueError) and raises(lambda: D.arch_lm(np.ones(6), 4), ValueError))
    check("wls 가중치가 배열 → 안내(TypeError)", raises(lambda: wb.equation("wl").wls("Y c X1", weights=np.ones(T)),
                                                 TypeError, "시리즈"))
    pd_ = quiet(wb.equation("pdl").ls, "Y c pdl(X1, 4, 2)")
    check("lag_distribution 범위 밖 → 오류", raises(lambda: pd_.lag_distribution(5), ValueError))

    print("\n" + "=" * 80)
    print("C. 모델·시나리오")
    print("=" * 80)
    w = quiet(macro_wf)
    m = quiet(macro_model, w)
    quiet(w.smpl, "2000Q1", "2019Q4")
    r = quiet(m.solve)
    check("동적 풀이 80기 정상", r.counts()["ok"] == 80)
    sc = quiet(m.scenario, "rep", "_r")
    sc.use_residuals()
    rr = quiet(m.solve, scenario="rep")
    check("표본 잔차 조정항 → 동적 풀이가 실측 재현",
          np.nanmax(np.abs(rr.values["CN"].to_numpy() / span(w, "CN", "2000Q1", "2019Q4").to_numpy() - 1)) < 1e-8)
    quiet(m.scenario, "baseline")
    check("풀이 옵션 검사(tolerance ≤ 0 · max_iterations 0 · 오타)",
          raises(lambda: m.solve(tolerance=-1), ValueError, "tolerance") and raises(lambda: m.solve(max_iterations=0), ValueError)
          and raises(lambda: m.solve(mode="dynamik"), ValueError) and raises(lambda: m.solve(jacobian="x"), ValueError))
    sx = quiet(m.scenario, "bad")
    sx.add_factor("Y", 1.0)
    check("조정항: 항등식 목표 → 오류", raises(lambda: m.solve(scenario="bad"), ValueError, "항등식"))
    sx.clear().add_factor("NOPE", 1.0)
    check("조정항: 없는 식 → 오류", raises(lambda: m.solve(scenario="bad"), ValueError, "추정식이 없습니다"))
    sx.clear().add_factor("cn", 1.0)
    check("조정항: 목표변수 대소문자 무시", quiet(m.solve, "2010Q1", "2010Q2", scenario="bad").counts()["ok"] == 2)
    check("빈 모델 → 오류", raises(lambda: w.model("empty").solve(), Exception, "방정식이 없습니다"))
    kw = dict(method="gauss-seidel", fallback=(), max_iterations=1)
    check("미수렴 정책: actual→대체 · nan→실패 · stop→오류",
          quiet(m.solve, **kw).counts()["fallback"] > 0 and quiet(m.solve, on_fail="nan", **kw).counts()["failed"] > 0
          and raises(lambda: m.solve(on_fail="stop", **kw), Exception))
    w3 = quiet(macro_wf, "f3")
    m3 = quiet(macro_model, w3, "m3")
    quiet(m3.forecast, "2020Q1", "2021Q4", exog_fill="last")
    s3 = quiet(m3.scenario, "f")
    s3.override("G", 40.0).override("R", 3.0)
    check("전망 시작 앞 내생변수 실측이 비면 → 분명한 안내",
          raises(lambda: m3.forecast("2022Q1", "2022Q4", scenario="f"), ValueError, "fillna"))
    check("값을 하나도 얻지 못한 기간은 '실패'(일부식 제외로 보이지 않음)",
          quiet(m3.solve, "2022Q1", "2022Q4", scenario="f").counts()["failed"] == 4)
    for v in ("CN", "I", "P", "Y"):
        w3[v] = w3[v].fillna(w3[v + "_0"])
    check("앞 풀이 값을 실측에 채운 뒤 이어서 전망", quiet(m3.forecast, "2022Q1", "2022Q4", scenario="f").counts()["ok"] == 4)
    quiet(m.scenario, "baseline")
    quiet(m.solve)
    tgt = w["Y_0"].iloc[w._index_of("2010Q1"):w._index_of("2010Q4") + 1] * 1.05
    gpath = quiet(m.control, "Y", "G", tgt, "2010Q1", "2010Q4")
    chk = quiet(m.scenario, "ctl")
    chk.override("G", gpath)
    rc = quiet(m.solve, "2010Q1", "2010Q4", scenario="ctl")
    check("control: 역산한 도구 경로로 풀면 목표 달성", np.max(np.abs(rc.values["Y"].to_numpy() / tgt.to_numpy() - 1)) < 1e-8)
    quiet(m.scenario, "baseline")
    d2 = quiet(m.scenario, "dec2")
    d2.shock("G", 10, "2010Q1", "2010Q4").override("R", 5.0).add_factor("eqc", 1.0)
    t = quiet(m.decompose, ["Y"], "dec2", start="2010Q1", end="2010Q4").table("Y")
    tot = "합계(시나리오 − 기준선)"
    check("Shapley 분해: 항목 합 = 전체 차이", np.allclose(t.drop(columns=[tot]).sum(axis=1), t[tot]) and t[tot].abs().max() > 0)
    quiet(m.scenario, "baseline")
    mu = quiet(m.multipliers, "G", 1.0, "2010Q1", "2011Q4")
    check("승수: G +1 → Y 충격 승수 > 1", mu.level["Y"].iloc[0] > 1)
    w6 = quiet(macro_wf, "mce")
    T6 = len(w6.data)
    w6["XQ"] = rng.normal(size=T6)
    w6["QQ"] = np.cumsum(rng.normal(size=T6)) * 0.1
    mq = w6.model("mq").merge(quiet(w6.equation("fq").fixed, "QQ c QQ(1) QQ(-1) XQ", [0.0, 0.3, 0.5, 0.3]))
    quiet(w6.smpl, "2000Q1", "2010Q4")
    ft = quiet(mq.solve, mce=True).values["QQ"].to_numpy()
    st = quiet(mq.solve, mce=True, mce_method="stacked").values["QQ"].to_numpy()
    check("MCE: Fair-Taylor = stacked", np.max(np.abs(ft - st)) < 1e-6)
    check("MCE: mce_damping 0 → 오류('수렴'으로 보이는 첫 추측 방지)", raises(lambda: mq.solve(mce=True, mce_damping=0),
                                                                        ValueError, "mce_damping"))
    with logged() as msgs:
        quiet(mq.solve)
    check("선행변수 모델을 mce 없이 풀면 경고", any("선행변수" in x for x in msgs))
    check("선행변수 모델 안정성 → 안내", raises(lambda: mq.stability("2005Q1"), ValueError, "선행"))
    hs_before = os.path.isdir(os.path.join(tmp, "HS"))
    with cwd(tmp):
        out = quiet(r.save, os.path.join(tmp, "결과 폴더", "hs.csv"))
    check("SolveResult.save: 없는 폴더를 만들고, 작업 폴더에 HS/를 만들지 않음",
          os.path.isfile(out) and not hs_before and not os.path.isdir(os.path.join(tmp, "HS")))

    print("\n" + "=" * 80)
    print("D. 시스템·VAR·VECM")
    print("=" * 80)
    ws = quiet(eqn.wfcreate, "s", "Q", "1980Q1", "2019Q4")
    T = len(ws.data)
    v1, v2 = np.zeros(T), np.zeros(T)
    for t_ in range(1, T):
        v1[t_] = 0.5 * v1[t_ - 1] + 0.1 * v2[t_ - 1] + rng.normal()
        v2[t_] = 0.2 * v1[t_ - 1] + 0.3 * v2[t_ - 1] + rng.normal()
    ws["V1"], ws["V2"] = v1, v2
    x = np.cumsum(rng.normal(size=T))
    ws["CX"], ws["CY"] = x, 0.8 * x + rng.normal(scale=0.5, size=T)
    va = quiet(ws.var, "va", ["V1", "V2"], lags=2)
    check("VAR 시차 0·음수 → 오류", raises(lambda: ws.var("vg", ["V1", "V2"], lags=0), ValueError, "시차")
          and raises(lambda: ws.var("vh", ["V1", "V2"], lags=-1), ValueError, "시차"))
    check("VAR 같은 시리즈 두 번 → 오류", raises(lambda: ws.var("vk", ["V1", "v1"]), ValueError, "두 번"))
    check("VAR 예측·분산분해 기간 0 → 오류", raises(lambda: va.forecast(0), ValueError) and raises(lambda: va.fevd(0), ValueError))
    check("irf_graph 없는 충격 → 분명한 오류", raises(lambda: va.irf_graph("NOPE"), KeyError, "충격"))
    check("실패한 재추정은 이전 객체를 지우지 않음",
          raises(lambda: ws.var("va", ["V1", "V2"], lags=-1)) and ws.obj("va").fit.p == 2)
    k = quiet(ws.vecm, "k", ["CY", "CX"], deterministic="ci lo")
    check("VECM deterministic 띄어 쓰기('ci lo') 허용", k.fit.det in ("cilo", "ci lo"))
    check("VECM co·ci 겹침 → 오류", raises(lambda: ws.vecm("k2", ["CY", "CX"], deterministic="coci"), ValueError, "두 번"))
    check("VECM 순위 0 → 안내(차분 VAR)", raises(lambda: ws.vecm("k0", ["CY", "CX"], rank=0), ValueError, "차분 VAR"))
    check("VECM 차분 시차 음수 → 오류", raises(lambda: ws.vecm("k3", ["CY", "CX"], lags_diff=-1), ValueError))
    sy = ws.system("sy")
    sy.append("V1 c V1(-1) V2(-1)", "V2 c V1(-1) V2(-1)")
    check("FIML start 길이 틀림 → 분명한 오류", raises(lambda: sy.fiml(start=[1, 2]), ValueError, "start 길이"))
    check("시스템 tsls: 도구 없는 식 → 안내", raises(lambda: ws.system("s2").append("V1 c V2", "V2 c V1 @inst V1(-1)").tsls(),
                                                     ValueError, "도구변수가 없습니다"))
    path = os.path.join(tmp, "broken.eqw")
    quiet(ws.save, path)
    with open(os.path.join(path, "workfile.json"), encoding="utf-8") as f:
        j = json.load(f)
    j["objects"].append({"type": "var", "name": "bad", "series": ["V1", "V2"], "lags": -1, "trend": "c"})
    with open(os.path.join(path, "workfile.json"), "w", encoding="utf-8") as f:
        json.dump(j, f, ensure_ascii=False)
    with logged() as msgs:
        w2 = quiet(eqn.wfopen, path)
    check("망가진 객체가 든 워크파일 → 그 객체만 건너뛰고 경고", "bad" not in w2._objects and w2.obj("va").fit.p == 2
          and any("복원하지 못한" in x for x in msgs))

    print("\n" + "=" * 80)
    print("E. 식 계산·변환·저장·출력")
    print("=" * 80)
    we = quiet(eqn.wfcreate, "g", "Q", "2000Q1", "2004Q4")
    we["X"] = np.arange(20.0)
    check("eval: @trend·@seas(n)·@d·@step", we.eval("@trend").iloc[1] == 1 and we.eval("@seas(2)").iloc[:4].tolist() == [0, 1, 0, 0]
          and we.eval("@d(2001Q1)").sum() == 1 and we.eval("@step(2001Q1)").sum() == 16)
    quiet(we.genr, "TR = @trend * 2 + X")
    check("genr: 지시자 사용", we["TR"].iloc[2] == 6.0)
    check("eval: 번호 없는 @seas → 안내", raises(lambda: we.eval("@seas"), DSLError, "번호"))
    check("write: 모르는 확장자 → 오류", raises(lambda: we.write(os.path.join(tmp, "x.txt")), ValueError, "xlsx"))
    check("graph kind 오타·기간 거꾸로 → 오류", raises(lambda: we.graph("g1", "X", kind="pie"), ValueError, "kind")
          and raises(lambda: we.graph("g2", "X", start="2003Q1", end="2001Q1"), ValueError))
    g = quiet(we.graph, "g3", "X TR")
    gp = os.path.join(tmp, "그림 폴더", "g 1.html")
    quiet(g.save, gp)
    check("graph.save: 없는 폴더를 만든다 · 모르는 확장자는 오류", os.path.isfile(gp)
          and raises(lambda: g.save(os.path.join(tmp, "g.doc")), ValueError))
    fpath = write(os.path.join(tmp, "afile.eqw"), "")
    check("save 경로가 파일 → 분명한 오류", raises(lambda: we.save(fpath), ValueError, "파일입니다"))
    # 전 객체 저장 왕복
    wf = quiet(eqn.wfcreate, "full", "Q", "1990Q1", "2019Q4")
    n = len(wf.data)
    xx, zz = rng.normal(size=n), rng.normal(size=n)
    wf["X"], wf["Z"] = xx, zz
    wf["Y"] = 1 + 0.5 * xx + rng.normal(scale=0.3, size=n)
    wf["Z2"], wf["W"] = rng.normal(size=n), 1 + rng.uniform(size=n)
    quiet(wf.meta, "Y", desc="종속", unit="%")
    quiet(wf.smpl, "1991Q1", "2019Q4")
    specs = {"o": ("ls", "Y c X Y(-1)"), "a": ("ls", "Y c X ar(1)"), "p": ("ls", "Y c pdl(X, 4, 2)"),
             "n": ("ls", "Y = c(1) + c(2)*X @start 0 0.1"), "t": ("tsls", "Y c X @inst Z X(-1)"),
             "g": ("gmm", "Y c X @inst Z X(-1)"), "l": ("liml", "Y c X @inst Z X(-1)")}
    for nm, (meth, sp) in specs.items():
        quiet(getattr(wf.equation("e_" + nm), meth), sp)
    quiet(wf.equation("e_w").wls, "Y c X", weights="W")
    quiet(wf.equation("e_f").fixed, "Z2 c X", [1.0, 0.5])
    mf = wf.model("m").merge("e_o", "e_f")
    mf.append("Q = Y + X")
    s1 = quiet(mf.scenario, "s1")
    s1.override("X", wf["X"] * 2).exclude("Y", "2000Q1", "2000Q4").add_factor("e_o", {"2001Q1": 1.0}).shock("X", 1.0, "2002Q1")
    quiet(mf.scenario, "s2").control("Y", "X", 1.0)
    quiet(mf.scenario, "baseline")
    sysw = wf.system("sy")
    sysw.append("Y c X", "Z c X")
    quiet(sysw.sur, restrict=["c(2) = c(4)"])
    quiet(wf.var, "v", ["X", "Z"], lags=2, trend="ct")
    wf["CX"] = np.cumsum(xx)
    wf["CY"] = wf["CX"] * 0.5 + rng.normal(size=n)
    quiet(wf.vecm, "k", ["CY", "CX"], deterministic="cili")
    quiet(wf.graph, "gr", "X Y", kind="bar", title="그림", start="2000Q1")
    quiet(wf.table, "tb", pd.DataFrame({"가": [1.5, None]}))
    pga = quiet(wf.page, "ann", "A")
    quiet(wf.convert, "Y", pga, name="YA")
    path = os.path.join(tmp, "전체 저장", "full.eqw")
    quiet(wf.save, path)
    w2 = quiet(eqn.wfopen, path)
    bad = [nm for nm in list(specs) + ["w", "f"]
           if not (np.allclose(wf.obj("e_" + nm).coefs.to_numpy(), w2.obj("e_" + nm).coefs.to_numpy())
                   and np.allclose(wf.obj("e_" + nm).stderrs.to_numpy(), w2.obj("e_" + nm).stderrs.to_numpy(), equal_nan=True))]
    for sc_ in ("baseline", "s1", "s2"):
        a_ = quiet(mf.solve, "2003Q1", "2003Q4", scenario=sc_).values.to_numpy()
        b_ = quiet(w2.obj("m").solve, "2003Q1", "2003Q4", scenario=sc_).values.to_numpy()
        if not np.allclose(a_, b_):
            bad.append("solve " + sc_)
    if not (w2.smpl() == wf.smpl() and w2.meta("Y") == wf.meta("Y")):
        bad.append("smpl·meta")
    if not np.allclose(w2.obj("sy").coefs.to_numpy(), sysw.coefs.to_numpy()):
        bad.append("system")
    if not (np.allclose(w2.obj("v").coefs.to_numpy(), wf.obj("v").coefs.to_numpy())
            and np.allclose(w2.obj("k").beta.to_numpy(), wf.obj("k").beta.to_numpy())):
        bad.append("var·vecm")
    if w2.obj("gr").output().text() != wf.obj("gr").output().text() or "tb" not in w2._objects:
        bad.append("graph·table")
    if not np.allclose(w2.page("ann")["YA"].dropna(), pga["YA"].dropna()):
        bad.append("page")
    check("저장/불러오기: 추정법 9종·모델 시나리오 3개·시스템·VAR·VECM·그래프·표·페이지·메타데이터", bad == [], str(bad))

    print("\n" + "=" * 80)
    print("F. 명령줄")
    print("=" * 80)
    proj = os.path.join(tmp, "새 프로젝트 1")
    code, _, _ = run(["new", proj], tmp)
    script = os.path.join("scripts", "main.py")
    code, _, _ = run(["run", script, "--out", "보고서 폴더", "--run-id", "실행 1", "--format", "csv"], proj)
    check("한글·공백 경로: new → run → 보고서", code == 0
          and os.path.isfile(os.path.join(proj, "보고서 폴더", "실행 1", "manifest.json")))
    codes = [run(["run", script, "--run-id", rid, "--no-report"], proj)[0] for rid in ("../탈출", os.path.join(tmp, "abs"), "", "a/b")]
    check("--run-id: 경로·'..'·절대 경로·빈 값 → 3", codes == [3, 3, 3, 3] and not os.path.exists(os.path.join(proj, "탈출")),
          str(codes))
    codes = [run(["run", script, *a], proj)[0] for a in (["--format", ""], ["--smpl", "2010Q1:2000Q1"],
                                                       ["--watch", "--interval", "0"], ["--smpl", "2001M3:2002M1x"])]
    check("--format 빈 값·--smpl 거꾸로·--interval 0·잘못된 시점 → 3", codes == [3, 3, 3, 3], str(codes))
    write(os.path.join(proj, "note.txt"), "print(1)\n")
    check("스크립트는 .py만 → 3", run(["run", "note.txt"], proj)[0] == 3)
    with open(os.path.join(proj, "cp.py"), "wb") as f:
        f.write("# -*- coding: cp949 -*-\nprint('한글 출력')\n".encode("cp949"))
    code, out, err = run(["run", "cp.py", "--no-report"], proj)
    check("cp949 스크립트(coding 선언) 실행", code == 0 and "한글 출력" in out, err[-200:])
    write(os.path.join(proj, "cd.py"), "import os\nos.chdir(os.path.expanduser('~'))\nprint('CD')\n")
    code, _, _ = run(["run", "cd.py", "--run-id", "cdrun", "--format", "csv"], proj)
    check("스크립트가 작업 폴더를 바꿔도 보고서는 실행한 자리", code == 0 and os.path.isdir(os.path.join(proj, "out", "cdrun"))
          and os.path.samefile(os.getcwd(), ROOT))
    write(os.path.join(proj, "empty.txt"), "# 주석만\n\n")
    check("check: 식이 없는 방정식 파일 → 3", run(["check", "empty.txt"], proj)[0] == 3)
    with open(os.path.join(proj, "cp949.txt"), "wb") as f:
        f.write("Y c X  # 소비\nZ = Y + X\n".encode("cp949"))
    write(os.path.join(proj, "bom.txt"), "﻿Y c X\nZ = Y + X\n")
    with logged() as msgs:
        code, out, err = run(["check", "cp949.txt"], proj)
    check("check: cp949(ANSI) 방정식 파일은 경고하고 읽는다", code == 0 and any("cp949" in x for x in msgs))
    wq = quiet(eqn.wfcreate, "b", "Q", "2000Q1", "2010Q4")
    wq["X"] = np.arange(44.0)
    wq["Y"] = 2 * wq["X"] + 1 + np.sin(np.arange(44.0))
    mb = quiet(wq.model("mb").merge, os.path.join(proj, "bom.txt"))
    mc = quiet(wq.model("mc").merge, os.path.join(proj, "cp949.txt"))
    check("model.merge: BOM·cp949 방정식 파일", [o.eq.dependent_var for o in mb.equations] == ["Y"]
          and [o.eq.dependent_var for o in mc.equations] == ["Y"] and mb.identities == ["Z = Y + X"])
    write(os.path.join(proj, "rc.txt"), "C c Y\n")
    code, out, _ = run(["check", "rc.txt"], proj)
    check("check: 변수 이름 C → 3(상수항 안내)", code == 3 and "상수항" in out)

    print("\n" + "=" * 80)
    print("G. 예제 자료(eqn.datasets)")
    print("=" * 80)
    from equion.datasets import _make
    shapes = {}
    for nm in eqn.datasets.names():
        wd = quiet(eqn.datasets.load, nm)
        shapes[nm] = (wd.freq, wd.smpl(), len(wd.data.columns))
    check("예제 자료 4종: 주기·기간·시리즈 수", shapes == {
        "toy_q": ("Q", ("1970Q1", "2019Q4"), 10), "toy_a": ("A", ("1970", "2019"), 9),
        "toy_m": ("M", ("2000M1", "2019M12"), 3), "klein_like": ("A", ("1921", "1990"), 10)}, str(shapes))
    wd = quiet(eqn.datasets.load, "toy_q")
    check("메타데이터(설명·단위·집계)와 참 모형 설명", wd.meta("Y")["agg"] == "sum" and "CN + I + G" in wd.meta("Y")["desc"]
          and "0.15·Y(-1)" in eqn.datasets.describe("toy_q") and raises(lambda: eqn.datasets.load("nope"), KeyError))
    regen = {"toy_q": _make.make_toy_q(), "klein_like": _make.make_klein_like()}
    regen["toy_a"], regen["toy_m"] = _make.make_toy_a(regen["toy_q"]), _make.make_toy_m(regen["toy_q"])
    same = all(np.allclose(pd.read_csv(eqn.datasets.path(k), index_col=0).to_numpy(dtype=float), v.to_numpy(dtype=float),
                           rtol=1e-6, atol=1e-6, equal_nan=True) for k, v in regen.items())
    check("들어 있는 CSV = 만드는 코드(_make.py)의 결과(참 모형 설명이 자료와 맞음)", same)
    wd.equation("ds_i").ls("I c Y(-1) R")
    tv = quiet(wd.equation("ds_cn").tsls, "CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
    check("toy_q: 투자식 OLS·소비식 TSLS가 참 계수 근처", abs(wd.obj("ds_i").coefs["R"] + 1.0) < 0.1
          and abs(tv.coefs["Y"] - 0.5) < 0.06)
    # 열 구성만 실제 자료와 같은 가상 값(실제 Klein 자료는 이용 조건이 분명하지 않아 저장소에 넣지 않는다)
    kf = write(os.path.join(tmp, "klein.csv"), "Year,C,P,Wp,I,K1,X,Wg,G,T\n1920,40.0,12.0,28.0,3.0,180.0,45.0,2.0,2.5,3.5\n"
               "1921,42.0,13.0,26.0,-1.0,183.0,46.0,3.0,4.0,7.0\n1922,45.0,16.0,29.0,2.0,182.0,50.0,3.0,3.0,4.0\n")
    wk = quiet(eqn.datasets.klein, kf)
    check("klein(): 직접 구한 Klein 파일의 열 이름 바꾸기(C→CONS·P→PR)·추세 A·자본 K",
          {"CONS", "PR", "WP", "K", "A"} <= set(wk.data.columns) and wk.elem("A", "1921") == -10.0
          and abs(wk.elem("K", "1920") - 183.0) < 1e-9)

    print("\n" + "=" * 80)
    print("H. 기간 표기는 periods 모듈로(pandas 4 대비)")
    print("=" * 80)
    from equion import Data, Equation, Model
    from equion.log import silenced

    def strict(fn):
        """경고를 오류로 바꿔 fn()을 부른다(pandas의 기간 문자열 해석 경고 — Pandas4Warning 등). (값, 오류 글)"""
        try:
            with warnings.catch_warnings(), contextlib.redirect_stdout(io.StringIO()), silenced():
                warnings.simplefilter("error")
                return fn(), ""
        except Exception as ex:                       # noqa: BLE001 — 실패로 기록
            return None, f"{type(ex).__name__}: {ex}"

    def engine_model():
        dq = Data(eqn.datasets.path("toy_q"))
        e1, e2 = Equation("I c Y(-1) R", dq), Equation("CN c Y CN(-1)", dq)
        e1.process()
        e2.process()
        me = Model(dq, [e1, e2])
        me.add_identity("Y = CN + I + G")
        return me, me.simulate("2010Q1", "2010Q4", verbose=False)

    res, err = strict(engine_model)
    me, rs = res if res else (None, None)
    check("엔진 Model(WorkTable 없이)에 '2010Q1' 시점 표기", rs is not None and rs.counts()["ok"] == 4, err)
    check("없는 시점은 자료 기간과 extend 안내", me is not None and raises(lambda: me._to_index("2030Q1"), ValueError, "1970Q1~2019Q4"))

    def label_roundtrip():
        wq = eqn.datasets.load("toy_q")
        eq_h = wq.equation("h_i").ls("I c Y(-1) R")
        mh = wq.model("h_m").merge(eq_h, "CN c Y CN(-1)").append("Y = CN + I + G")
        lab = wq.to_pandas(["G"], labels=True)["G"].loc["2010Q1":"2010Q4"] * 1.1     # 기간 라벨 인덱스 경로
        mh.scenario("h_hi").override("G", lab)
        mh.solve("2010Q1", "2010Q4")
        wq2 = eqn.wfopen(wq.save(os.path.join(tmp, "hlab")))
        wq2.obj("h_m").solve("2010Q1", "2010Q4", scenario="h_hi")
        return float(wq["Y_1"].dropna().iloc[-1]), float(wq2["Y_1"].dropna().iloc[-1])

    ys, err = strict(label_roundtrip)
    check("기간 라벨 인덱스 시나리오 경로: 저장·열기 뒤 같은 풀이", ys is not None and abs(ys[0] - ys[1]) < 1e-9, err)

    print("\n" + "=" * 80)
    print("I. 플랫폼(BLAS·LAPACK)에 따라 달라지지 않는 결과")
    print("=" * 80)
    from equion.stats import diagnostics as _dg
    wp = quiet(eqn.datasets.load, "toy_q")
    ep = quiet(wp.equation("i_p").ls, "dlog(P) c dlog(Y) dlog(POIL)")
    e_p, X_p = ep.eq.residuals.to_numpy(dtype=float), ep.eq._X.to_numpy(dtype=float)
    lags_p = _dg._lags_of(e_p, 2, pad=True)
    aux = np.linalg.lstsq(np.column_stack([X_p, lags_p]), e_p, rcond=None)[0]       # 상수항 하나뿐인 보조 회귀
    fit = np.column_stack([X_p, lags_p]) @ aux
    lm_ref = len(e_p) * (1 - ((e_p - fit) ** 2).sum() / ((e_p - e_p.mean()) ** 2).sum())
    bg = _dg.breusch_godfrey(e_p, X_p, 2)
    check("계열상관 LM: X에 상수항이 있으면 보조 회귀에 상수열을 또 넣지 않는다(겹친 열의 절단이 플랫폼마다 달랐다)",
          abs(bg.statistic - lm_ref) < 1e-8 and abs(bg.pvalue - 0.4052) < 1e-3, f"{bg.statistic} vs {lm_ref}")
    bg_nc = _dg.breusch_godfrey(e_p, X_p[:, 1:], 2)
    check("계열상관 LM: 상수항 없는 X에는 상수열을 더한다(전과 같음)", abs(bg_nc.statistic - bg.statistic) < 1e-8)
    kk = quiet(eqn.datasets.load, "klein_like")
    sk = kk.system("i_kl").append("CONS c PR PR(-1) WP+WG", "I c PR PR(-1) K(-1)", "WP c X X(-1) A",
                                  "@inst G T WG A PR(-1) K(-1) X(-1)")
    quiet(sk.three_sls)
    mk = quiet(kk.model("i_km").merge, sk).append("X = CONS + I + G", "PR = X - T - WP", "K = K(-1) + I")
    sv = quiet(mk.stability, "1960")
    ev = np.asarray(sv.eigenvalues)
    check("안정성: 켤레 근 쌍은 허수부가 양인 쪽이 먼저(순서가 LAPACK에 따라 달라지지 않게)",
          ev[0].imag > 0 and abs(ev[0] - np.conj(ev[1])) < 1e-12, str(ev[:2]))
    mt = quiet(wp.model("i_toy").merge, quiet(wp.equation("i_i").ls, "I c Y(-1) R"), "CN c Y CN(-1)", ep)
    mt.append("Y = CN + I + G")
    st = quiet(mt.stability, "2010Q1")                 # 가장 큰 근은 물가 식의 것 — 다른 변수의 비중은 0
    foot = st.output(4).text()
    check("안정성: '함께 움직이는 변수'에 0%로 반올림되는 변수는 보이지 않는다(그 순서는 잡음이라 플랫폼마다 달랐다)",
          "함께 움직이는 변수: P 100%" in foot and " 0%" not in foot, foot.splitlines()[-2] if foot else "")

    print("\n" + "=" * 80)
    print("J. 예제 자료로 옮기며 찾은 결함")
    print("=" * 80)
    rng_u = np.random.default_rng(24)
    x_u = np.cumsum(0.01 + 0.01 * rng_u.standard_normal(120)) + 5
    u_u = np.zeros(120)
    for t_ in range(1, 120):
        u_u[t_] = 0.99 * u_u[t_ - 1] + 0.01 * rng_u.standard_normal()
    w_u = quiet(eqn.wfcreate, "aru", "Q", "1990Q1", "2019Q4")
    w_u["YY"] = np.exp(1 + 0.8 * x_u + u_u + 0.02 * np.sin(np.arange(120) / 6.0))
    w_u["XX"] = np.exp(x_u)
    check("AR(1): 제곱합이 ρ → 1로 계속 줄면(오차의 단위근) 원인과 대안을 알리는 오류(전: '함수 평가 횟수 초과')",
          raises(lambda: w_u.equation("e_u").ls("log(YY) c log(XX) ar(1)"), ValueError, "단위근"))
    w_s = quiet(eqn.datasets.load, "toy_q")
    s_w = w_s.system("j_sys").append("dlog(CN) = c(1) + c(2)*dlog(Y) + c(3)*dlog(CN(-1))",
                                     "dlog(I) c dlog(Y) dlog(I(-1))")
    quiet(s_w.sur, restrict="c(2) = c(5)")
    check("시스템 Wald: 이미 넣은 제약 하나를 다시 검정하면 오류(전: 1×1 공분산이라 판정을 못 하고 큰 χ²)",
          raises(lambda: s_w.wald("c(2) = c(5)"), ValueError, "이미"))
    quiet(s_w.sur)
    w_ok = quiet(s_w.wald, "c(2) = c(5)")
    check("시스템 Wald: 제약 없이 추정한 뒤에는 그대로 검정", np.isfinite(w_ok.statistic) and 0 <= w_ok.pvalue <= 1)

    print("\n" + "=" * 80)
    total = len(PASS) + len(FAIL)
    print(f"  RESULT: {len(PASS)} PASS / {len(FAIL)} FAIL  (total {total})  — {time.time() - t0:.1f}s")
    print("  " + ("[OK] ALL PASSED!" if not FAIL else "실패: " + ", ".join(FAIL)))
    print("=" * 80)
    eqn.verbose(1)
    return len(FAIL)


def test_suite():
    """pytest 진입점 — 이 파일의 검사 묶음 전체(하나라도 실패하면 실패). `python tests/test_scenarios.py`와 같은 검사."""
    assert main() == 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(99)
