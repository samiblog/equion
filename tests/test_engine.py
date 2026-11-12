#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_engine.py — 엔진 v3 회귀 테스트 (parser → IR → 추정 → 구조 → 블록 솔버 → 시나리오).

실행: uv run python tests/test_engine.py   (종료코드 = 실패 수)

검증 항목
  A. 번역 일관성: 실측을 넣은 컴파일 잔차 == OLS 잔차 (분기·연·월 시험 모델의 방정식 전부)
  B. DSL 형태: 괄호 안 공백, ^, X(-1), 시차범위, @pch/@movav, d(x,n,s), 대소문자 …
  C. 오류·보안: 미지 함수, 이중밑줄 속성, 첨자, 문자열, 코드 실행 시도 → 거부
  D. 분류·항등식: 공백 없는 '=', 식 좌변 항등식, 항등식 안의 시차·변화율
  E. 구조: 블록 분해, 중복 정의·미지 변수·비정방 오류
  F. HS/solve: 수렴·통계, hs_id 재사용 초기화, 상태 기록, 성능
  G. 전망·시나리오·승수·control·확률 시뮬·MCE
  H. 추정법: NLS==OLS(선형), TSLS, fixed(@coef), set_coefficients
  I. 번들 저장/복원, 주기 인지(@seas 월, @d 월, 연간 .yoy)
수치 기준선은 같은 환경 안에서도 BLAS에 따라 미세하게 달라질 수 있어 허용오차로 비교한다.
자료는 패키지의 예제 자료(eqn.datasets: toy_q·toy_a·toy_m — 참 모형을 아는 가상 자료)만 쓴다.
"""

import contextlib
import io
import os
import sys
import tempfile
import time
import traceback

import numpy as np

import equion as eqn  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from equion.estimation.equation import Equation  # noqa: E402
from equion.formula import ir  # noqa: E402
from equion.formula.ast_formula import pandas_formula_to_solver, user_to_pandas  # noqa: E402
from equion.formula.parser import DSLError, classify_line  # noqa: E402
from equion.scenario import Scenario  # noqa: E402
from equion.system.analyzer import Block, StructureError  # noqa: E402
from equion.system.compiler import compile_block  # noqa: E402
from equion.system.model import Model  # noqa: E402
from equion.system.simulate import SimulationError  # noqa: E402
from equion.worktable import WorkTable  # noqa: E402

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  — {detail}" if detail else ""))


def raises(fn, exc=Exception, contains=None):
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            fn()
    except exc as e:
        return contains is None or contains in str(e)
    except Exception:
        return False
    return False


def quiet(fn, *a, **k):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a, **k)


def close(a, b, rtol=1e-8, atol=1e-12):
    """같은 모양(또는 b가 스칼라)이고 허용오차 안이면 True."""
    a, b = np.atleast_1d(np.asarray(a)), np.atleast_1d(np.asarray(b))     # 복소(고윳값)도 그대로 비교
    if a.shape != b.shape and b.size != 1:
        return False
    return bool(np.allclose(a, b, rtol=rtol, atol=atol))


def make_wt(freq, data, eqs=None, estimate=True):
    def build():
        wt = WorkTable(name=f"t{freq}", freq=freq, register=False)
        wt.load_data(data)
        if eqs:
            wt.load_equations(eqs)
            if estimate:
                wt.estimate()
        return wt
    return quiet(build)


# 시험 모델 — 예제 자료(가상)로 만든 작은 연립 모델(분기 6식 + 항등식, 연간 5식 + 항등식, 월간 3식)
EQS = {
    "Q": """# 분기 시험 모델(toy_q)
I c Y(-1) R
CN c Y CN(-1)
dlog(P) c dlog(Y) dlog(POIL)
RL c R RL(-1)
log(M2) c log(P) log(Y) RL log(M2(-1))
dlog(CNNSA) c dlog(CN) @seas
Y = CN + I + G
""",
    "A": """# 연간 시험 모델(toy_a)
I c Y(-1) R
CN c Y CN(-1)
dlog(P) c dlog(Y) dlog(POIL)
RL c R
log(M2) c log(P) log(Y) RL
Y = CN + I + G
""",
    "M": """# 월간 시험 모델(toy_m)
log(IP) c log(IP(-1)) @seas
dlog(CPIM) c dlog(IP) @seas
RM c RM(-1)
""",
}
N_EQ = {"Q": 6, "A": 5, "M": 3}
_TMP = tempfile.mkdtemp(prefix="eqn-engine-")
FILES = {}
for _f, _ds in (("Q", "toy_q"), ("A", "toy_a"), ("M", "toy_m")):
    _p = os.path.join(_TMP, f"model_{_f}.txt")
    with open(_p, "w", encoding="utf-8") as _fh:
        _fh.write(EQS[_f])
    FILES[_f] = (eqn.datasets.path(_ds), _p)


def residual_consistency(model):
    """각 추정식: 목표변수 = 실측일 때 컴파일 잔차 vs OLS 잔차 최대 차이."""
    system = model.system
    df = model.data.data
    A = np.full((len(df), len(system.var_names)), np.nan)
    for j, nm in enumerate(system.var_names):
        if nm in df.columns:
            A[:, j] = df[nm].to_numpy(dtype=float)
    P = model.coefficient_vector()
    AF = np.zeros((len(df), max(system.n_af, 1)))
    worst = 0.0
    for e, eq in enumerate(system.eqs):
        if eq.kind != "behavioral":
            continue
        j = system.var_index[eq.target]
        cb = compile_block(system, Block(eqs=[e], vars=[j]))
        for date, r in eq.source.residuals.items():
            t = df.index.get_loc(date)
            val = cb.resid(np.array([A[t, j]]), A, A, AF, P, t)[0]
            worst = max(worst, abs(val - r) / max(1.0, abs(r)))
    return worst


def main():
    t_start = time.time()
    print("=" * 80)
    print("A. 번역 일관성 (컴파일 잔차 == OLS 잔차)")
    print("=" * 80)
    wts = {}
    for freq, (d, e) in FILES.items():
        wt = make_wt(freq, d, e)
        wts[freq] = wt
        check(f"[{freq}] {N_EQ[freq]}/{N_EQ[freq]} 추정", len(wt.equations) == N_EQ[freq] and not wt.last_failed,
              f"실패 {len(wt.last_failed)}")
        w = residual_consistency(wt.model)
        check(f"[{freq}] 잔차 재현", w < 1e-9, f"max diff {w:.1e}")
    wtq = wts["Q"]
    m = wtq.model
    D = wtq.data

    def est(s, **kw):
        def go():
            eq = Equation(s, D, **kw)
            eq.wt = wtq
            eq.process()
            return eq
        return quiet(go)

    print("\n" + "=" * 80)
    print("B. DSL 형태")
    print("=" * 80)
    forms = [
        ("괄호 안 공백", "log(CN) c log(Y - G)", 2),
        ("거듭제곱 ^", "log(CN) c log(Y) R^2", 3),
        ("EViews 시차 X(-1)", "log(CN) c log(CN(-1))", 2),
        ("EViews 시차범위", "log(cn) c log(cn(-1 to -3))", 4),
        (".t 시차범위", "log(CN) c log(CN.t(-1 to -2))", 3),
        ("@pch/@movav", "log(CN) c @pch(Y) @movav(POIL,4)", 3),
        ("d(x,n,s)·@pcy", "dlog(CN) c d(log(Y),1,4) @pcy(POIL)", 3),
        ("식의 시차", "log(CN) c log((CN+I).t(-1))", 2),
        ("내생 변화율 이동평균", "log(CN) c (Y.qoq).ma(4)", 2),
        ("단독 연산자 결합", "log(CN) c log(Y) + log(POIL)", 2),
        ("lead", "log(CN) c log(Y(1))", 2),
        ("더미·추세", "log(CN) c @trend @d(2008Q4) @step(2010Q1)", 4),
        ("지시자·TO 대소문자, # 주석", "log(CN) c @TREND @D(2008Q4) @Step(2010Q1) log(Y(-1 TO -2))  # 주석", 6),
        ("@smpl", "log(CN) c log(Y) @smpl 2005Q1 2019Q4", 2),
    ]
    for label, s, k in forms:
        try:
            eq = est(s)
            ok = len(eq.coef_names) == k
            mm = quiet(Model, D, [eq])
            mm.wt = wtq
            w = residual_consistency(mm)
            check(f"{label}", ok and w < 1e-9, f"계수 {len(eq.coef_names)} · 잔차차 {w:.1e}")
        except Exception as ex:  # noqa: BLE001
            check(f"{label}", False, f"{type(ex).__name__}: {str(ex)[:80]}")
    eq = est("log(CN) c log(Y) @smpl 2005Q1 2019Q4")
    check("@smpl 관측치 60", eq.statistics["n_obs"] == 60, str(eq.statistics["n_obs"]))
    eq = est("log(CN) c @pch(Y)")
    check("@함수 표시명 유지", eq.coef_names == ["const", "@pch(Y)"], str(eq.coef_names))

    print("\n" + "=" * 80)
    print("C. 오류·보안")
    print("=" * 80)
    bad = {
        "미지 함수 max()": "log(CN) c max(R,2)",
        "이중밑줄 속성": "log(CN) c Y.__class__",
        "첨자": "log(CN) c Y[0]",
        "문자열 상수": "log(CN) c 'abc'",
        "코드 실행 시도": "log(CN) Y.__class__.__init__.__globals__['__builtins__']['__import__']('os').getpid()",
        "괄호 불균형": "log(CN c log(Y)",
        "중복 설명변수": "log(CN) c log(Y) log(Y)",
        "@coef 개수 불일치": "log(CN) c log(Y) @coef 0.5",
        "미지 @함수": "log(CN) c @foo(Y)",
    }
    for label, s in bad.items():
        check(f"거부: {label}", raises(lambda s=s: est(s), (DSLError, ValueError)))
    check("거부: 데이터에 없는 변수", raises(lambda: est("log(CN) c log(NOSUCHVAR)"), ValueError, "데이터에 없는"))
    check("거부: 항등식을 추정식으로", raises(lambda: est("CI = CN + I"), DSLError, "항등식"))
    check("레거시 user_to_pandas 보안", raises(lambda: user_to_pandas("X.__class__"), ValueError))
    check("레거시 pandas_formula_to_solver 보안",
          raises(lambda: pandas_formula_to_solver("df['X'] = __import__('os').getpid()", D.data, 10, []), ValueError))

    print("\n" + "=" * 80)
    print("D. 분류·항등식")
    print("=" * 80)
    check("분류: 공백 없는 '=' → 항등식", classify_line("CI=CN+I") == "identity")
    check("분류: c(n) → NLS", classify_line("Y = c(1) + c(2)*X") == "nls")
    check("분류: 등호 없음 → 추정식", classify_line("log(Y) c X") == "estimated")
    mm = quiet(Model, D, [est("log(CN) c log(Y) log(CN(-1))")])
    mm.wt = wtq
    for s in ["CI=CN+I", "log(XX1) = log(CN + (I+G).t(-1))",
              "XX2 = CN*(1+dlog(I)) + I.yoy + (I+G).qoq + I.gr(4) + @pc(I)"]:
        quiet(mm.add_identity, s)
    check("항등식 목표변수", set(mm.endogenous_vars) == {"CN", "CI", "XX1", "XX2"}, str(mm.endogenous_vars))
    r = quiet(mm.simulate, "2010Q1", "2010Q4", mode="static", excludes={"CN": True}, verbose=False)
    t = wtq.index_of("2010Q1")
    d = D.data
    want = d["CN"].iloc[t] + d["I"].iloc[t - 1] + d["G"].iloc[t - 1]
    check("식 좌변·식의 시차 항등식", abs(r.values["XX1"].iloc[0] - want) < 1e-6 * want,
          f"{r.values['XX1'].iloc[0]:.1f} vs {want:.1f}")
    g = d["I"]
    want2 = (d["CN"].iloc[t] * (1 + np.log(g.iloc[t] / g.iloc[t - 1])) + (g.iloc[t] / g.iloc[t - 4] - 1) * 100
             + ((g + d["G"]).iloc[t] / (g + d["G"]).iloc[t - 1] - 1) * 100
             + (g.iloc[t] / g.iloc[t - 4] - 1) * 100 + (g.iloc[t] / g.iloc[t - 1] - 1) * 100)
    check("항등식 안 dlog/.yoy/.qoq/.gr/@pc", abs(r.values["XX2"].iloc[0] - want2) < 1e-6 * abs(want2))

    print("\n" + "=" * 80)
    print("E. 구조")
    print("=" * 80)
    blocks = m.block_structure()
    sizes = sorted((b["size"] for b in blocks), reverse=True)
    check("분기 시험 모델: 블록 6개(동시 CN·Y 2 + 순차 5)", len(blocks) == 6 and sizes[0] == 2
          and sorted(blocks[[b["size"] for b in blocks].index(2)]["variables"]) == ["CN", "Y"], str(sizes))
    m2 = quiet(Model, D, [est("log(CN) c log(Y)"), est("log(CN) c log(POIL)")])
    check("중복 정의 → 구조 오류", raises(lambda: m2.system, StructureError, "둘 이상"))
    m3 = quiet(Model, D, [est("log(CN) c log(Y)")])
    quiet(m3.add_identity, "XX = NEWVAR + CN")
    check("미지 변수 → 구조 오류", raises(lambda: m3.system, StructureError, "NEWVAR"))

    print("\n" + "=" * 80)
    print("F. HS / solve")
    print("=" * 80)
    t0 = time.time()
    h = quiet(wtq.hs, "1975Q1", "2019Q4", hs_id="full")
    dt = time.time() - t0
    check("분기 HS 180/180 풀림(실패대체 0) — RL 자료가 1980Q1부터라 그 전은 일부식 제외",
          h["success_count"] == 180 and h["fallback_count"] == 0 and h["partial_count"] == 21,
          f"ok {h['ok_count']} · partial {h['partial_count']}")
    check("분기 HS 성능 < 10초", dt < 10, f"{dt:.2f}s")
    st = m.hs_statistics["full"]
    check("분기 HS 적합(Y<1%·CN<1%·P<2%)",
          st["Y"]["RMSPE"] < 1 and st["CN"]["RMSPE"] < 1 and st["P"]["RMSPE"] < 2,
          f"Y {st['Y']['RMSPE']:.2f} · CN {st['CN']['RMSPE']:.2f} · P {st['P']['RMSPE']:.2f}")
    s0 = m.hs_status["full"][wtq.index_of("1980Q1")]
    check("결측 입력 식 제외 기록(1980Q1: RL(-1)이 자료 시작 전)", s0["status"] == "partial"
          and s0["excluded"] == ["RL:RL(-1)"], str(s0["excluded"]))
    s1 = m.hs_status["full"][wtq.index_of("1980Q2")]
    check("입력이 다 갖춰진 다음 기간은 정상", s1["status"] == "ok", s1["status"])
    # hs_id 재사용: 이전 결과를 덮어써야 한다(이전 해가 시차로 섞이면 안 됨)
    quiet(wtq.hs, "2010Q1", "2010Q2", hs_id="re")
    m.hs_solutions["re"][wtq.index_of("2010Q2")]["CN"] *= 1.1
    quiet(wtq.hs, "2010Q3", "2010Q3", hs_id="re")
    quiet(wtq.hs, "2010Q3", "2010Q3", hs_id="fresh")
    t3 = wtq.index_of("2010Q3")
    check("hs_id 재사용 시 초기화", abs(m.hs_solutions["re"][t3]["CN"] - m.hs_solutions["fresh"][t3]["CN"]) < 1e-6
          and wtq.index_of("2010Q1") not in m.hs_solutions["re"])
    sol = quiet(m.solve, wtq.index_of("2012Q2"), solve_id="s")
    stat = quiet(m.simulate, "2012Q2", "2012Q2", mode="static", verbose=False)
    check("solve = 정적 simulate", max(abs(sol[v] - stat.values[v].iloc[0]) for v in sol) < 1e-8)
    check("데이터 끝 밖 solve → 명확한 오류", raises(lambda: m.simulate(len(D.data), len(D.data)), Exception))
    check("on_missing='stop' → 중단", raises(lambda: m.simulate("1980Q1", "1980Q1", on_missing="stop", verbose=False),
                                            SimulationError, "결측"))
    rn = quiet(m.simulate, "1980Q1", "1980Q1", on_missing="nan", verbose=False)
    check("on_missing='nan' → 결측 전파", not np.isfinite(rn.values["RL"].iloc[0]))
    fit = quiet(m.simulate, "2010Q1", "2010Q4", mode="fit", verbose=False)
    check("fit 모드", fit.counts()["ok"] == 4)

    print("\n" + "=" * 80)
    print("G. 전망·시나리오·승수·control·확률·MCE")
    print("=" * 80)
    wtf = make_wt("Q", *FILES["Q"])
    check("전망: 외생 경로 없으면 진단 오류",
          raises(lambda: wtf.forecast("2020Q1", "2021Q4", verbose=False), ValueError, "외생변수"))
    fr = quiet(wtf.forecast, "2020Q1", "2023Q4", exog_fill="last", verbose=False)
    check("전망(기간 확장 + 외생 채움) 16/16", fr.counts()["ok"] == 16 and len(wtf.data.data) == 216,
          f"{fr.counts()} · 행 {len(wtf.data.data)}")
    check("기간 확장 시 결정적 지시자 연장", np.isfinite(wtf.data.data["_Q2"].iloc[-1]))
    base = quiet(Scenario("base").run, m, "2010Q1", "2012Q4", verbose=False)
    oil = quiet(Scenario("oil").shock("POIL", 50, "2010Q1", "2012Q4", kind="pct").run, m, "2010Q1", "2012Q4",
                verbose=False)
    check("시나리오: 유가 +50% → 물가 상승", oil.pct_diff(base)["P"].iloc[-1] > 0)
    ex = quiet(Scenario("x").exclude("RL").override("RL", 3.0).run, m, "2010Q1", "2010Q4", verbose=False)
    check("시나리오: exclude + override", np.allclose(ex.values["RL"], 3.0))
    af = quiet(Scenario("af").init_add_factor("P", "2009Q4").run, m, "2010Q1", "2010Q1", verbose=False)
    check("시나리오: add factor 초기화", np.isfinite(af.values["P"].iloc[0]))
    # 표본 잔차 조정항 → 모든 식이 실측에서 성립하므로(항등식 Y = CN + I + G도 자료에서 성립) 정적 풀이 해 = 실측
    rep = quiet(m.simulate, "2005Q1", "2005Q4", mode="static", add_factors=True, verbose=False)
    cols = [c for c in rep.values.columns if c in D.data.columns]
    rel = np.nanmax(np.abs(rep.values[cols].to_numpy() / D.data[cols].loc[rep.values.index].to_numpy() - 1))
    check("정적 + 표본 잔차 조정항 → 전 내생변수 실측 재현", rel < 1e-6, f"max rel {rel:.1e}")
    mu = quiet(m.multipliers, "R", 1.0, wtq.index_of("2010Q1"), wtq.index_of("2011Q4"))
    check("승수: 금리 R +1 → 투자 I 감소(참 계수 −1)", mu.level["I"].iloc[-1] < 0)
    cr = quiet(m.control, "Y", "G", {"2010Q1": 600.0, "2010Q2": 600.0},
               wtq.index_of("2010Q1"), wtq.index_of("2010Q2"), verbose=False)
    check("control: 목표 경로 달성", np.allclose(cr.values["Y"], 600.0) and "G" in cr.values.columns)
    sto = quiet(m.stochastic, wtq.index_of("2010Q1"), wtq.index_of("2011Q4"), reps=20, seed=7, verbose=False)
    sto2 = quiet(m.stochastic, wtq.index_of("2010Q1"), wtq.index_of("2011Q4"), reps=20, seed=7, verbose=False)
    b = sto.band("Y")
    check("확률 시뮬: 재현성·밴드 순서", np.allclose(sto.mean.values, sto2.mean.values)
          and (b["p5"] <= b["p50"]).all() and (b["p50"] <= b["p95"]).all())
    fe = est("log(P) c log(P(1)) log(P(-1)) log(POIL) @coef 0.2 0.3 0.6 0.01")
    mm = quiet(Model, D, [fe])
    mm.wt = wtq
    rm = quiet(mm.simulate, "2010Q1", "2014Q4", mce=True, terminal="actual", verbose=False)
    S_ = rm.values["P"]
    i0 = wtq.index_of("2010Q1")
    worst = 0.0
    for k in range(1, len(S_) - 1):
        lhs = np.log(S_.iloc[k])
        rhs = 0.2 + 0.3 * np.log(S_.iloc[k + 1]) + 0.6 * np.log(S_.iloc[k - 1]) + 0.01 * np.log(D.data["POIL"].iloc[i0 + k])
        worst = max(worst, abs(lhs - rhs))
    check("MCE(Fair-Taylor) 수렴·모형 일관", rm.mce_converged and worst < 1e-7, f"{rm.mce_passes}회 · {worst:.1e}")

    print("\n" + "=" * 80)
    print("H. 추정법")
    print("=" * 80)
    o = est("log(CN) c log(Y) log(CN(-1))").regression_results["coefficients"]
    n = est("log(CN) = c(1) + c(2)*log(Y) + c(3)*log(CN(-1)) @start 0 0.5 0.5").regression_results["coefficients"]
    check("NLS(선형) == OLS (해석적 자코비안, 1e-10)", np.allclose(list(o.values()), list(n.values()), rtol=1e-10, atol=0))
    n2 = est("log(CN) = c(1) + c(2)*log(Y) + c(3)*log(CN(-1)) @start 1 0 0").regression_results["coefficients"]
    check("NLS 시작값과 무관하게 같은 해", np.allclose(list(n.values()), list(n2.values()), rtol=1e-10, atol=0))
    tq = est("log(CN) c log(Y) log(CN(-1)) @inst log(Y(-1)) log(CN(-1)) log(G)")
    check("TSLS 추정", tq.method == "tsls" and np.isfinite(list(tq.regression_results["coefficients"].values())).all())
    fx = est("log(CN) c log(Y) @coef 0.5 0.9")
    check("fixed(@coef)", fx.method == "fixed" and fx.regression_results["coefficients"] == {"const": 0.5, "log(Y)": 0.9})
    e2 = est("log(CN) c log(Y)")
    quiet(e2.set_coefficients, {"const": 1.0, "log(Y)": 0.8})
    check("set_coefficients(외부 계수)", e2.method == "fixed" and abs(e2.coef_vector()[1] - 0.8) < 1e-12)
    cb = est("RL R RL(-1)")                                  # 상수항 없는 식
    check("상수항 없는 식은 중심화 R² + 비중심 R² 별도",
          "r_squared_uncentered" in cb.statistics and cb.statistics["r_squared"] < cb.statistics["r_squared_uncentered"])

    print("\n" + "=" * 80)
    print("I. 번들·주기")
    print("=" * 80)
    with tempfile.TemporaryDirectory() as tmp:
        p = quiet(wtq.save, os.path.join(tmp, "k"))
        w2 = quiet(WorkTable.load, p, register=False)
        quiet(w2.hs, "1975Q1", "2019Q4", hs_id="fullb")
        a, bb = m.hs_solutions["full"], w2.model.hs_solutions["fullb"]
        dmax = max(abs(a[t][v] - bb[t][v]) / max(1e-9, abs(a[t][v])) for t in a for v in a[t])
        check("번들 라운드트립(재추정 없음) HS 동일", dmax < 1e-12, f"{dmax:.1e}")
        check("번들: 상태 복원", "full" in w2.model.hs_status)
    wa = wts["A"]
    eqa = quiet(lambda: Equation("log(CN) c Y.yoy", wa.data))
    quiet(eqa._parse)
    check("연간 .yoy = 1기 변화율", ir.to_str(eqa.term_irs[0]) == "(Y / Y(-1) - 1) * 100")
    check("연간 @seas → 오류", raises(lambda: quiet(lambda: Equation("log(CN) c @seas", wa.data)), ValueError))
    wm = wts["M"]
    em = quiet(lambda: Equation("log(IP) c @seas @d(2008M3)", wm.data))
    quiet(em._parse)
    check("월간 @seas(12개월)·@d(월)", len(em.independent_vars) == 12 and "D_2008M03" in em.independent_vars,
          str(em.independent_vars[-2:]))
    ea = quiet(lambda: Equation("log(CN) c Y.yoy @smpl 2005 2015", wa.data))
    quiet(lambda: (ea._parse(), ea._prepare_data()))
    check("연간 @smpl", len(ea._y) == 11, str(len(ea._y)))

    print("\n" + "=" * 80)
    print("J. 기간·주기 (equion.data.periods — pandas 시간 API는 여기서만)")
    print("=" * 80)
    import pandas as pd
    from equion.data import periods as P
    qs = pd.date_range("2000-01-01", periods=8, freq="QS")
    qe = pd.DatetimeIndex(["2000-03-31", "2000-06-30", "2000-09-29", "2000-12-29"])   # 분기 말·영업일
    check("주기 추론: 분기(첫날·말일·영업일)", P.infer_freq_code(qs) == "Q" and P.infer_freq_code(qe) == "Q")
    check("주기 추론: 월·연·불규칙·짧음", P.infer_freq_code(pd.date_range("2000-01-01", periods=5, freq="MS")) == "M"
          and P.infer_freq_code(pd.date_range("2000-01-01", periods=4, freq="YS")) == "A"
          and P.infer_freq_code(qs.delete(3)) is None and P.infer_freq_code(qs[:2]) is None)
    ps = P.period_starts("2000Q1", "2001Q2", "Q")
    check("기간 첫날 인덱스", list(ps.strftime("%Y-%m-%d")) == ["2000-01-01", "2000-04-01", "2000-07-01",
                                                          "2000-10-01", "2001-01-01", "2001-04-01"])
    check("기간 표기 왕복", P.format_period(P.parse_period("2003M7", "M"), "M") == "2003M7"
          and P.format_period(P.parse_period("2003", "A"), "A") == "2003"
          and P.format_period(P.to_period(pd.Timestamp("2003-08-15"), "Q"), "Q") == "2003Q3")
    mdf = pd.DataFrame({"x": np.arange(12.0)}, index=pd.date_range("2000-01-01", periods=12, freq="MS"))
    rq = P.resample(mdf, "Q", "sum")
    check("주기 변환(월 → 분기 합)", list(rq["x"]) == [3.0, 12.0, 21.0, 30.0]
          and list(rq.index.strftime("%Y-%m")) == ["2000-01", "2000-04", "2000-07", "2000-10"])
    check("개월 이동", P.shift_months(pd.Timestamp("2022-12-01"), -11) == pd.Timestamp("2022-01-01"))

    print("\n" + "=" * 80)
    print("K. 입력 한도·퍼징 (D18 — 메모리·시간·재귀 한계를 넘는 식은 바로 DSLError)")
    print("=" * 80)
    import random
    import time as _time
    from equion.formula import parser as PS
    extremes = {"시차범위 10만": "Y c X(-1 to -100000)", "이동평균 100만": "Y c @movav(X, 1000000)",
                "시차 100만": "Y c X(-1000000)", "합 3000항": "Y c " + "+".join(["X"] * 3000),
                "글자 20만": "Y c " + " ".join(["X(-1)"] * 40000), "차분 100만": "Y c d(X, 1000000)",
                "항 600개": "Y c " + " ".join(f"X(-{k})" for k in range(1, 601))}
    fast = True
    for label, spec in extremes.items():
        t1 = _time.time()
        ok = raises(lambda s=spec: Equation(s, D)._parse(), DSLError)
        fast = fast and ok and (_time.time() - t1) < 1.0
    check("극단 입력 7종 → 1초 안에 DSLError", fast)
    check("한도 안의 큰 식은 통과(시차범위 100·합 200항)",
          not raises(lambda: Equation("log(CN) c Y(-1 to -100)", D)._parse())
          and not raises(lambda: quiet(lambda: Model(D).add_identity("Q = " + "+".join(["Y"] * 200)))))
    TOK = ["Y", "P", "c", "log(", "exp(", "d(", "dlog(", "@pc(", "@movav(", "(", ")", "+", "-", "*", "/", "^",
           " ", " ", ",", ".t(", ".ma(", ".qoq", ".yoy", "1", "-1", "-4", "0.5", "1e9", "=", "c(1)", "@seas", "@trend",
           "@inst", "__import__", "lambda", "[", "]", "{", "'", '"', "\\", ";", "#", "%", "os.system", "eval", "X(-1 to -3)"]
    random.seed(7)
    leaked = []
    for _ in range(3000):
        s_ = "".join(random.choice(TOK) for _ in range(random.randint(1, 18)))
        for fn in (lambda: Equation(s_, D)._parse(), lambda: Model(D).add_identity(s_)):
            try:
                quiet(fn)
            except ValueError:          # DSLError 포함
                pass
            except Exception as ex:      # noqa: BLE001
                leaked.append((s_, type(ex).__name__))
    check("퍼징 3000개 × 2경로: DSLError/ValueError 외 예외 없음", not leaked, str(leaked[:2]))

    print("\n" + "=" * 80)
    print("L. 모델 분석 — 동태 안정성(동반행렬 근)·시나리오 기여도 분해 (D24)")
    print("=" * 80)
    from equion.system.analysis import scenario_drivers
    rng = np.random.default_rng(4)
    ws = quiet(eqn.wfcreate, "lin", "Q", "2000Q1", "2019Q4")
    T80 = 80
    X = rng.standard_normal(T80)
    Y1, Y2 = np.zeros(T80), np.zeros(T80)
    Y1[0], Y2[0] = 1.0, 1.0
    for t in range(1, T80):
        Y1[t] = 0.5 * Y1[t - 1] + 0.2 * Y2[t - 1] + X[t]
        Y2[t] = 0.4 * Y1[t] + 0.1 * Y1[t - 1] + 0.3 * Y2[t - 1]
    for nm, v in (("Y1", Y1), ("Y2", Y2), ("X", X), ("P", np.exp(np.cumsum(0.01 + 0.01 * X)))):
        ws[nm] = v
    quiet(ws.equation("f1").fixed, "Y1 Y1(-1) Y2(-1) X", [0.5, 0.2, 1.0])
    quiet(ws.equation("f2").fixed, "Y2 Y1 Y1(-1) Y2(-1)", [0.4, 0.1, 0.3])
    ml = ws.model("lin")
    quiet(ml.merge, ["f1", "f2"])
    A0 = np.array([[1, 0], [-0.4, 1]])
    B = np.linalg.solve(A0, np.array([[0.5, 0.2], [0.1, 0.3]]))
    st = quiet(ml.stability, "2010Q1", measure="level")
    check("선형 연립: 근 = A₀⁻¹A₁의 고윳값(독립 계산)", close(np.sort(np.abs(st.eigenvalues)), np.sort(np.abs(np.linalg.eigvals(B))), 1e-12)
          and st.stable)
    quiet(ws.equation("g").fixed, "log(P) c log(P(-1))", [0.01, 0.9])
    mg = ws.model("lg")
    quiet(mg.merge, "g")
    t0 = ws._index_of("2010Q1")
    rel_ = quiet(mg.stability, "2010Q1").eigenvalues
    lev_ = quiet(mg.stability, "2010Q1", measure="level").eigenvalues
    check("로그식: 상대 편차 근 = b, 수준 편차 근 = b·yₜ/yₜ₋₁(성장률만큼)", close(rel_, [0.9], 1e-12)
          and close(lev_, [0.9 * ws["P"].iloc[t0] / ws["P"].iloc[t0 - 1]], 1e-12))
    wq = quiet(eqn.datasets.load, "toy_q")
    v = quiet(wq.var, "vv", ["dlog(Y)", "dlog(CN)", "dlog(I)"], lags=2)
    mvv = wq.model("mvv")
    quiet(mvv.merge, v)
    sv = quiet(mvv.stability, "2010Q1")
    mods = np.sort(np.abs(sv.eigenvalues))[::-1]
    check("VAR로 만든 모델: 근 = VAR 동반행렬 근 + 변수마다 단위근(수준의 적분)", close(mods[:3], 1.0, 1e-10)
          and close(mods[3:], np.sort(np.abs(v.fit.eigenvalues()))[::-1], 1e-10))
    mk = wq.model("toy")
    quiet(mk.merge, FILES["Q"][1])
    sk = quiet(mk.stability, "2015Q1")
    check("분기 시험 모델: 근 7개(내생 7 × 최대 시차 1), 판정 = 단위근(차분식 dlog의 수준), 안정 = 최대 |λ| < 1",
          len(sk.eigenvalues) == 7 * 1 and sk.stable == (sk.max_modulus < 1) and sk.loadings is not None
          and sk.verdict == "단위근", f"최대 |λ| {sk.max_modulus:.4f} · {sk.verdict}")
    path = quiet(mk.stability_path, "2014Q1", "2014Q4")
    check("기간별 안정성 표", list(path.columns[:3]) == ["최대 모듈러스", "1 이상인 근", "안정"] and len(path) == 4)
    wl = quiet(eqn.wfcreate, "lead", "Q", "2000Q1", "2005Q4")
    wl["A"] = np.arange(24.0)
    quiet(wl.equation("fl").fixed, "A A(1)", [0.5])
    mlead = wl.model("ml")
    quiet(mlead.merge, "fl")
    check("선행 변수(MCE) 모델 → 분명한 오류", raises(lambda: mlead.stability("2002Q1"), ValueError, "선행"))

    sc2 = ml.scenario("ab")
    sc2.shock("X", 1.0, "2015Q1")
    sc2.add_factor("Y2", {"2015Q2": 0.5})
    d = quiet(ml.decompose, ["Y1", "Y2"], "ab", start="2015Q1", end="2016Q4")
    tb = d.table("Y2")
    check("선형 모델 Shapley: 합 = 전체, 하나씩과 같고 상호작용 0", close(tb.iloc[:, :2].sum(axis=1), tb.iloc[:, -1], 1e-12)
          and close(quiet(ml.decompose, "Y2", "ab", start="2015Q1", end="2016Q4", method="single").table("Y2")["상호작용"], 0.0, 1e-12, 1e-12))
    check("항목 목록: 충격·조정항(기준선에 없는 것만)", d.drivers == ["조정항 Y2", "충격 X +1"] or d.drivers == ["충격 X +1", "조정항 Y2"],
          str(d.drivers))
    sk2 = mk.scenario("oil")
    sk2.shock("POIL", 20, "2015Q1", "2015Q4")
    sk2.shock("R", 1.0, "2015Q1", "2015Q4")
    sk2.add_factor("P", {"2015Q2": 0.01})
    dk = quiet(mk.decompose, ["Y", "M2"], "oil", start="2015Q1", end="2016Q2")
    dsg = quiet(mk.decompose, ["Y", "M2"], "oil", start="2015Q1", end="2016Q2", method="single")
    ok = all(close(dk.table(v_).iloc[:, :3].sum(axis=1), dk.table(v_).iloc[:, -1], 1e-9, 1e-9) for v_ in ("Y", "M2"))
    ok2 = all(close(dsg.table(v_).iloc[:, :4].sum(axis=1), dsg.table(v_).iloc[:, -1], 1e-9, 1e-9) for v_ in ("Y", "M2"))
    check("비선형 분기 모델 Shapley: 항목 기여 합 = 시나리오 − 기준선(2³ = 8번 풀이)", ok and dk.d.runs == 8)
    check("하나씩 분해: 항목 + 상호작용 = 전체", ok2 and dsg.d.runs == 5)
    check("기여도 그래프: 쌓은 막대", d.graph("Y2").spec()["layout"].get("barmode") == "relative")
    check("기준선과 같은 시나리오 → 분해할 항목 없음(오류)", raises(lambda: ml.decompose("Y1", "baseline"), ValueError, "항목"))

    print("\n" + "=" * 80)
    print("M. 큰 모델 — 희소 자코비안·stacked-time MCE (D25)")
    print("=" * 80)
    rs = quiet(mm.simulate, "2010Q1", "2014Q4", mce=True, terminal="actual", mce_method="stacked", verbose=False)
    n_ = len(S_)
    zx = np.log(D.data["POIL"].iloc[i0:i0 + n_].to_numpy())
    z0 = np.log(D.data["P"].iloc[i0 - 1])
    zT = np.log(D.data["P"].iloc[i0 + n_])
    M_ = np.eye(n_) - 0.3 * np.eye(n_, k=1) - 0.6 * np.eye(n_, k=-1)
    bvec = 0.2 + 0.01 * zx
    bvec[0] += 0.6 * z0
    bvec[-1] += 0.3 * zT
    exact_z = np.linalg.solve(M_, bvec)
    check("stacked MCE = 삼중대각 선형계의 직접 해(독립 계산)", close(np.log(rs.values["P"].to_numpy()), exact_z, 1e-10))
    e_ft = np.max(np.abs(rm.values["P"].to_numpy() / np.exp(exact_z) - 1))
    e_st = np.max(np.abs(rs.values["P"].to_numpy() / np.exp(exact_z) - 1))
    check("stacked = Fair-Taylor(그 수렴 기준 안), 정확도는 stacked가 높다", rs.mce_converged
          and close(rs.values["P"], rm.values["P"], 1e-7) and e_st < e_ft,
          f"Newton {rs.mce_passes}회 · 오차 {e_st:.0e} / Fair-Taylor {rm.mce_passes}회 · 오차 {e_ft:.0e}")
    fx2 = est("log(P) c log(P(1)) log(P(-1)) log(POIL) @coef 0.0 1.3 -0.35 0.01")
    m2 = quiet(Model, D, [fx2])
    m2.wt = wtq
    rf = quiet(m2.simulate, "2010Q1", "2014Q4", mce=True, terminal="actual", verbose=False)
    rs2 = quiet(m2.simulate, "2010Q1", "2014Q4", mce=True, terminal="actual", mce_method="stacked", verbose=False)
    zz = np.log(rs2.values["P"].to_numpy())
    zfull = np.concatenate([[np.log(D.data["P"].iloc[i0 - 1])], zz, [np.log(D.data["P"].iloc[i0 + n_])]])
    res2 = zfull[1:-1] - (1.3 * zfull[2:] - 0.35 * zfull[:-2] + 0.01 * zx)
    check("선행 계수 > 1: Fair-Taylor는 수렴 못 해도 stacked는 풀린다", (not rf.mce_converged) and rs2.mce_converged
          and np.max(np.abs(res2)) < 1e-9)
    # terminal='hold': 끝 다음 값 = 풀린 끝 값(z_{T+1} = z_T) — 첫 추정(실측)에 묶이지 않는다
    Mh = M_.copy()
    Mh[-1, -1] -= 0.3
    bh = bvec.copy()
    bh[-1] -= 0.3 * zT
    exact_h = np.linalg.solve(Mh, bh)
    rsh = quiet(mm.simulate, "2010Q1", "2014Q4", mce=True, terminal="hold", mce_method="stacked", verbose=False)
    rfh = quiet(mm.simulate, "2010Q1", "2014Q4", mce=True, terminal="hold", verbose=False)
    check("stacked MCE terminal='hold' = 끝 값을 이어 붙인 선형계의 직접 해(독립 계산) · Fair-Taylor와 같다",
          rsh.mce_converged and close(np.log(rsh.values["P"].to_numpy()), exact_h, 1e-10)
          and close(rfh.values["P"], rsh.values["P"], 1e-7),
          f"{np.max(np.abs(np.log(rsh.values['P'].to_numpy()) - exact_h)):.1e}")
    hs_d = quiet(m.simulate, "2003Q1", "2010Q4", verbose=False)
    hs_s = quiet(m.simulate, "2003Q1", "2010Q4", jacobian="sparse", verbose=False)
    dif = np.nanmax(np.abs(hs_s.values.to_numpy() / hs_d.values.to_numpy() - 1))
    check("분기 시험 모델 HS: 희소 LU = 밀집(같은 해, 상태 동일)", dif < 1e-8 and hs_s.counts() == hs_d.counts(), f"최대 상대차 {dif:.1e}")
    nring = 150
    wr = quiet(eqn.wfcreate, "ring", "Q", "2000Q1", "2000Q4")
    xr = rng.standard_normal((4, nring))
    for i in range(nring):
        wr[f"X{i}"] = xr[:, i]
        wr[f"Y{i}"] = np.zeros(4)
    for i in range(nring):
        quiet(wr.equation(f"r{i}").fixed, f"Y{i} Y{(i + 1) % nring} X{i}", [0.3, 1.0])
    mr = wr.model("ring")
    quiet(mr.merge, [f"r{i}" for i in range(nring)])
    sol = quiet(mr.solve, "2000Q1", "2000Q4")
    Pm = np.roll(np.eye(nring), 1, axis=1)
    exact = np.linalg.solve(np.eye(nring) - 0.3 * Pm, xr.T).T
    got = sol.values[[f"Y{i}" for i in range(nring)]].to_numpy()
    sol_d = quiet(mr.solve, "2000Q1", "2000Q4", jacobian="dense")
    check("동시 블록 150변수: 'auto'는 희소 LU — 직접 선형 해·밀집 풀이와 같음", close(got, exact, 1e-10)
          and close(sol_d.values[[f"Y{i}" for i in range(nring)]].to_numpy(), exact, 1e-10)
          and mr.engine.system.structure().blocks[0].size == nring)
    check("jacobian·mce_method 잘못된 값 → 오류", raises(lambda: m.simulate("2003Q1", "2003Q2", jacobian="x"), ValueError)
          and raises(lambda: mm.simulate("2010Q1", "2010Q2", mce=True, mce_method="x"), ValueError))

    print("\n" + "=" * 80)
    print("N. 수렴한 해의 확인 — 해가 없는 블록·서로 종속인 식, 해만 적은 구간 끝, 정의역 밖 표본 (D66)")
    print("=" * 80)
    from equion.system import solver as SV

    def toy_model(lines, fixed=None):
        w = quiet(eqn.datasets.load, "toy_q")
        quiet(w.smpl, "1990Q1", "2019Q4")
        mdl = w.model("m")
        if fixed:
            quiet(mdl.merge, quiet(w.equation("e_fix").fixed, *fixed))
        for t in lines:
            quiet(mdl.append if "=" in t else mdl.merge, t)
        return w, mdl
    # 해가 없는 동시 블록: CN = Y(계수 고정)와 Y = CN + I + G → 0 = I + G. 전에는 값이 1e18까지 커져 반올림으로 잔차가 0이 되면 '정상'이었고
    # 그 값이 다음 기의 시차(Y(-1) → I)로 흘렀다
    w, ms = toy_model(["I c Y(-1) R", "Y = CN + I + G"], fixed=("CN c Y CN(-1)", [0.0, 1.0, 0.0]))
    rs = quiet(ms.solve, "2005Q1", "2009Q4")
    st = rs.status()
    act = w.data.loc[rs.values.index]
    check("해가 없는 블록 → 모든 기 실패 대체(정상 없음) · 값은 실측 · 다음 기로 흐르지 않음(I는 실측 근처)",
          rs.counts()["ok"] == 0 and rs.counts()["fallback"] == 20
          and close(rs.values["Y"], act["Y"]) and close(rs.values["CN"], act["CN"])
          and float(np.max(np.abs(rs.values["I"] / act["I"] - 1))) < 0.1
          and st["message"].str.contains("특이|발산").all(), str(rs.counts()))
    # 서로 종속인 항등식(통계상 불일치 SD를 두 번) — 아무 값에서나 잔차가 0이라 시작값이 그대로 '정상'이었다
    w, md = toy_model(["CN c Y CN(-1)", "I c Y(-1) R", "Y = CN + I + G + SD", "SD = Y - CN - I - G"])
    rd = quiet(md.solve, "2005Q1", "2006Q4")
    check("서로 종속인 항등식 → 모든 기 실패 대체 · '서로 종속이라 해가 하나로 정해지지 않습니다'",
          rd.counts()["ok"] == 0 and rd.status()["message"].str.contains("서로 종속").all(), str(rd.counts()))
    sysd = md.engine.system
    dep = sysd.dependent_identities()
    w2, mab = toy_model(["CN c Y CN(-1)", "I c Y(-1) R", "Y = CN + I + G", "A = B + G", "B = A - G"])
    dab = mab.engine.system.dependent_identities()
    w3, mok = toy_model(["CN c Y CN(-1)", "I c Y(-1) R", "Y = CN + I + G", "YN = Y * P", "LY = log(YN)"])
    check("구조 검사: 서로 종속인 항등식을 계수·자료 없이 찾는다(SD 두 번 · A=B+G와 B=A-G) · 보통 모형은 없음",
          len(dep) == 1 and set(dep[0]["variables"]) == {"CN", "Y", "SD"} and len(dep[0]["identities"]) == 2
          and len(dab) == 1 and set(dab[0]["variables"]) == {"A", "B"}
          and mok.engine.system.dependent_identities() == [], f"{dep} {dab}")
    rab = quiet(mab.solve, "2005Q1", "2005Q4")
    check("종속 블록만 실패 — 다른 블록(CN·I·Y)은 풀린다(실측과 같지 않음)",
          rab.counts()["fallback"] == 4 and not close(rab.values["Y"], w2.data.loc[rab.values.index, "Y"])
          and np.isfinite(rab.values["Y"]).all())
    # 크기를 맞춘 역조건수: 단위와 무관 · 밀집과 희소가 같은 판정
    from scipy import sparse as _sp
    Jd = np.array([[1.0, -0.6], [-1.0, 1.0]])
    Js = np.array([[1.0, -1.0], [-1.0, 1.0]])
    big = np.eye(150) - 0.3 * np.roll(np.eye(150), 1, axis=1)
    sing = np.eye(150) - np.roll(np.eye(150), 1, axis=1)
    check("역조건수: 보통 행렬은 크고(단위를 바꿔도 같음) 특이 행렬은 0 근처 — 밀집·희소 같은 판정",
          SV.equilibrated_rcond(Jd) > 1e-2
          and abs(SV.equilibrated_rcond(Jd * np.array([1e8, 1e-3])) - SV.equilibrated_rcond(Jd)) < 1e-12
          and SV.equilibrated_rcond(Js) < SV.RCOND_MIN and SV.equilibrated_rcond(sing) < SV.RCOND_MIN
          and SV.equilibrated_rcond(_sp.csc_matrix(sing)) < SV.RCOND_MIN
          and SV.equilibrated_rcond(_sp.csc_matrix(big)) > 1e-2 and SV.equilibrated_rcond(big) > 1e-2)
    # 큰(희소) 블록도 같은 확인: 150변수 고리에서 계수 1 → (I − P)가 특이 → 해 없음
    wr2 = quiet(eqn.wfcreate, "ring2", "Q", "2000Q1", "2000Q4")
    for i in range(nring):
        wr2[f"X{i}"] = xr[:, i]
        wr2[f"Y{i}"] = np.zeros(4)
    for i in range(nring):
        quiet(wr2.equation(f"r{i}").fixed, f"Y{i} Y{(i + 1) % nring} X{i}", [1.0, 1.0])
    mr2 = wr2.model("ring2")
    quiet(mr2.merge, [f"r{i}" for i in range(nring)])
    sol2 = quiet(mr2.solve, "2000Q1", "2000Q1", fallback=())
    check("희소 블록(150변수, 특이) → 실패 대체", sol2.counts()["fallback"] == 1 and sol2.counts()["ok"] == 0,
          str(sol2.counts()))
    # stacked MCE가 풀지 못하면 그 해를 쓰지 않는다 — 실패 정책대로 대체하고 상태도 실패
    wl = quiet(eqn.datasets.load, "toy_q")
    ml = wl.model("lead")
    quiet(ml.merge, quiet(wl.equation("e_l").fixed, "CN CN(1) Y", [0.5, 0.3]))
    quiet(ml.append, "Y = CN + I + G", "A = B + G", "B = A - G")
    rl = quiet(ml.solve, "2010Q1", "2010Q4", mce=True, mce_method="stacked")
    check("stacked MCE 실패(종속 블록) → 상태 실패 대체 · 값은 실측 · on_fail='stop'이면 멈춤",
          rl.counts()["ok"] == 0 and rl.counts()["fallback"] == 4
          and close(rl.values["CN"], wl.data.loc[rl.values.index, "CN"])
          and rl.status()["message"].str.contains("MCE\\(stacked\\) 미수렴").all()
          and raises(lambda: ml.solve("2010Q1", "2010Q4", mce=True, mce_method="stacked", on_fail="stop"),
                     Exception), str(rl.counts()))
    # 보통 모형: 받아들인 해는 그대로(확인이 거절한 블록 없음)
    w4, m4 = toy_model(["CN c Y CN(-1)", "I c Y(-1) R", "Y = CN + I + G"])
    r4 = quiet(m4.solve, "1991Q1", "2019Q4")
    check("보통 모형은 모든 기 정상(확인이 거절하지 않음)", r4.counts()["ok"] == 116, str(r4.counts()))

    # 해만 적은 구간의 끝 = 그 해의 마지막 기(EViews 'smpl 2000 2019'처럼). 시작은 첫 기 그대로
    idx_q = P.period_starts("2000Q1", "2019Q2", "Q")
    check("해만 적은 끝: 분기 2019 → 2019Q4 · 월 → 2019M12 · 연간 그대로 · 시작은 첫 기",
          str(P.parse_period("2019", "Q", end=True)) == "2019Q4" and str(P.parse_period("2019", "Q")) == "2019Q1"
          and P.format_period(P.parse_period("2019", "M", end=True), "M") == "2019M12"
          and P.format_period(P.parse_period("2019", "A", end=True), "A") == "2019"
          and P.parse_period("2019Q2", "Q", end=True) == P.parse_period("2019Q2", "Q"))
    check("구간 표기 2000:2019 → 2000Q1~2019Q4 · 자료가 2019Q2에서 끝나면 그 해의 마지막 자료 기",
          P.resolve_span("2000:2019", P.period_starts("1990Q1", "2024Q4", "Q"), "Q") == ("2000Q1", "2019Q4")
          and P.resolve_span("2000:2019", idx_q, "Q") == ("2000Q1", "2019Q2")
          and P.locate(idx_q, "2019", "Q", end=True) == len(idx_q) - 1 and P.locate(idx_q, "2019", "Q") == 76
          and P.resolve_span("2018:2019", P.period_starts("2000M1", "2024M12", "M"), "M") == ("2018M1", "2019M12"))
    e_yr = quiet(lambda: Equation("log(CN) c log(Y) @smpl 2005 2019", D))
    quiet(lambda: (e_yr._parse(), e_yr._prepare_data()))
    check("@smpl 2005 2019 (분기) → 2005Q1~2019Q4, 60기", len(e_yr._y) == 60, str(len(e_yr._y)))
    r_yr = quiet(m4.solve, "2018", "2019")
    check("solve('2018', '2019') → 2018Q1~2019Q4(8기)", len(r_yr.values) == 8, str(len(r_yr.values)))

    # log·dlog 안의 값이 0 이하 → 결측이 아니라 정의역 밖으로 빠진 것이라고 구분한다(표본·계수는 그대로)
    wn = quiet(eqn.datasets.load, "toy_q")
    wn["DY"] = wn["Y"] - wn["Y"].shift(1)
    en = quiet(lambda: Equation("log(DY) c R", wn._data))
    quiet(lambda: (en._parse(), en._prepare_data()))
    dy = wn.data["DY"]
    check("정의역 밖 표본: 0 이하 DY의 log는 'domain', 첫 기(시차)는 'missing'",
          len(en.sample_drops["domain"]) == int((dy <= 0).sum()) and len(en.sample_drops["missing"]) == 1
          and "0 이하" in en.sample_drops["why"] and len(en._y) == int((dy > 0).sum()),
          f"{len(en.sample_drops['domain'])} vs {(dy <= 0).sum()}")

    print("\n" + "=" * 80)
    total = len(PASS) + len(FAIL)
    print(f"  RESULT: {len(PASS)} PASS / {len(FAIL)} FAIL  (total {total})  — {time.time() - t_start:.1f}s")
    if FAIL:
        print("  실패:", ", ".join(FAIL))
    else:
        print("  [OK] ALL PASSED!")
    print("=" * 80)
    return len(FAIL)


def test_suite():
    """pytest 진입점 — 이 파일의 검사 묶음 전체(하나라도 실패하면 실패). `python tests/test_engine.py`와 같은 검사."""
    assert main() == 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(99)
