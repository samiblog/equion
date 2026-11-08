#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_stats.py — 자체 통계(equion.stats) 테스트. 외부 회귀 패키지 없이 돌아야 한다(DECISIONS D17).

실행: uv run python tests/test_stats.py   (종료코드 = 실패 수)

기준값 tests/fixtures/stats_reference.json 은 statsmodels로 한 번 계산해 고정한 것이다
(tests/fixtures/make_stats_reference.py — statsmodels가 있는 별도 환경에서만 다시 만든다).

  A. OLS(유사역행렬): 계수·표준오차·F·로그우도, 상수 판별(암묵적 상수), 계수 순위 부족
  B. 강건 공분산: HC0~HC3·HAC, 성질(HAC 시차 0 = HC1 등), TSLS·NLS, set_cov·저장/복원, 결과표
  C. 진단 검정: 계열상관 LM·White·BP·ARCH·JB·Ljung-Box·RESET·Wald·Chow·CUSUM, 진단 표, 제약식 안전성
  D. 단위근·공적분: ADF·KPSS·Engle-Granger·Johansen(워크파일 식 입력), 표본·결측 처리
  E. 의존성: statsmodels를 불러오지 않는다
"""

import contextlib
import io
import json
import os
import sys
import tempfile
import time
import traceback

import numpy as np
import pandas as pd
from scipy.stats import t as stats_t

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import equion as eqn  # noqa: E402
from equion.stats import diagnostics as D  # noqa: E402
from equion.stats import regression as R  # noqa: E402
from equion.stats import unitroot as U  # noqa: E402

PASS, FAIL = [], []
with open(os.path.join(ROOT, "tests", "fixtures", "stats_reference.json"), encoding="utf-8") as _f:
    REF = json.load(_f)
with open(os.path.join(ROOT, "tests", "fixtures", "estimation_reference.json"), encoding="utf-8") as _f:
    EREF = json.load(_f)                 # WLS·GMM·LIML·누락/불필요 변수 — make_estimation_reference.py


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  — {detail}" if detail else ""))


def close(a, b, rtol=1e-8, atol=1e-12):
    a, b = np.atleast_1d(np.asarray(a, dtype=float)), np.atleast_1d(np.asarray(b, dtype=float))
    return a.shape == b.shape and bool(np.allclose(a, b, rtol=rtol, atol=atol))


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


def main():
    t0 = time.time()
    eqn.verbose(0)
    wf = eqn.datasets.load("toy_q")      # 예제 자료(가상, 패키지에 들어 있음) — 기준값도 같은 자료로
    wf.smpl("@all")
    eqs = {k: wf.equation(f"e_{k}").ls(d["spec"]) for k, d in REF["equations"].items()}

    print("=" * 80)
    print("A. OLS (자체 구현 — 유사역행렬)")
    print("=" * 80)
    for k, o in eqs.items():
        d, res = REF["equations"][k], o.results
        check(f"[{k}] 계수·표준오차 = 기준값", close(res.params, d["params"], 1e-12) and close(res.bse, d["bse"], 1e-12))
        check(f"[{k}] F·로그우도 = 기준값", close(res.fvalue, d["fvalue"], 1e-12) and close(res.llf, d["llf"], 1e-12))
    rng = np.random.default_rng(7)
    n = 60
    x1 = rng.standard_normal(n)
    q = np.tile(np.eye(4), (n // 4, 1))                       # 계절 더미 4개(합 = 1, 명시 상수 없음)
    yv = 1 + 0.5 * x1 + rng.standard_normal(n) * 0.1
    idx = pd.RangeIndex(n)
    r1 = R.ols(pd.Series(yv, index=idx), pd.DataFrame(np.column_stack([x1, q]), index=idx))
    check("암묵적 상수(계절 더미 합 = 1) 판별", r1.k_constant == 1 and r1.rank == 5 and r1.df_model == 4.0)
    r2 = R.ols(pd.Series(yv, index=idx), pd.DataFrame(np.column_stack([np.ones(n), x1, 2 * x1]), index=idx))
    check("계수 순위 부족도 풀림(rank 2, 자유도 n−2)", r2.rank == 2 and r2.df_resid == n - 2
          and close(r2.fittedvalues, R.ols(pd.Series(yv, index=idx),
                                           pd.DataFrame(np.column_stack([np.ones(n), x1]), index=idx)).fittedvalues))
    check("결과 객체 = eqn.stats.Results", isinstance(eqs["cp"].results, eqn.stats.Results))

    print("\n" + "=" * 80)
    print("B. 강건 공분산")
    print("=" * 80)
    for k, o in eqs.items():
        d = REF["equations"][k]
        y, X = o.eq._y, o.eq._X
        ok = all(close(R.ols(y, X).set_cov(ct).bse, d[f"bse_{ct}"], 1e-9) for ct in ("hc0", "hc1", "hc2", "hc3"))
        check(f"[{k}] HC0~HC3 표준오차 = 기준값", ok)
        h = R.ols(y, X).set_cov("hac", 4)
        check(f"[{k}] HAC(4) 표준오차·p값 = 기준값", close(h.bse, d["bse_hac4"], 1e-9) and close(h.pvalues, d["pvalues_hac4"], 1e-7, 1e-12))
    y, X = eqs["cp"].eq._y, eqs["cp"].eq._X
    check("HAC 시차 0 = HC1(완전 순위)", close(R.ols(y, X).set_cov("hac", 0).bse, R.ols(y, X).set_cov("white").bse, 1e-9))
    check("Newey-West 기본 시차 ⌊4(n/100)^(2/9)⌋", R.ols(y, X).set_cov("hac").cov_lags == eqn.stats.newey_west_lags(len(y)) == 4)
    tq = R.tsls(y, X, X).set_cov("hc1")
    check("TSLS(도구 = 회귀변수) = OLS (계수 1e-12·강건 표준오차)", close(tq.params, R.ols(y, X).params, 1e-12)
          and close(tq.bse, R.ols(y, X).set_cov("hc1").bse, 1e-9))
    nl = quiet(lambda: wf.equation("e_nl").nls("log(CN) = c(1) + c(2)*log(Y) + c(3)*log(CN(-1))",
                                               start=[0, 0.5, 0.5], cov="hc1"))
    check("NLS(선형식) 강건 공분산 ≈ OLS", close(nl.stderrs.to_numpy(), REF["equations"]["cp"]["bse_hc1"], 1e-7))
    eh = wf.equation("e_hac").ls(REF["equations"]["cp"]["spec"], cov="hac", lags=4)
    st = eh.stats
    check("ls(cov='hac', lags=4) → 표준오차·통계 기록", close(eh.stderrs, REF["equations"]["cp"]["bse_hac4"], 1e-9)
          and st["cov_type"] == "hac" and st["hac_lags"] == 4 and np.isfinite(st["wald_f_statistic"]))
    txt = eh.output().text()
    check("결과표에 공분산·강건 Wald F 줄", "HAC(Newey-West, Bartlett, 시차 4)" in txt and "강건 Wald F" in txt)
    eh.set_cov(None)
    check("set_cov(None) → 일반 공분산(계수 불변)", close(eh.stderrs, REF["equations"]["cp"]["bse"], 1e-12)
          and eh.stats["cov_type"] == "nonrobust")
    eh.set_cov("white")
    tmp = tempfile.mkdtemp()
    path = wf.save(os.path.join(tmp, "robust"))
    w2 = eqn.wfopen(path)
    check("저장/복원 후에도 공분산 종류·표준오차 유지", w2.e_hac.stats["cov_type"] == "hc1"
          and close(w2.e_hac.stderrs, REF["equations"]["cp"]["bse_hc1"], 1e-9))
    check("엔진 수준 Equation(cov=...)", quiet(lambda: eqn.Equation(REF["equations"]["cp"]["spec"], wf._data, cov="hc3"))
          .cov_type == "hc3")
    check("알 수 없는 공분산 종류 → 오류", raises(lambda: wf.equation("e_bad").ls(REF["equations"]["cp"]["spec"], cov="xyz"),
                                            ValueError, "공분산"))
    check("고정 계수식에 강건 공분산 → 오류", raises(lambda: wf.equation("e_fx").fixed("log(CN) c log(Y)", [0.1, 0.9])
                                                .set_cov("hc1"), ValueError))

    print("\n" + "=" * 80)
    print("C. 진단 검정")
    print("=" * 80)
    for k, o in eqs.items():
        d = REF["equations"][k]
        ok = all(close([o.serial_lm(p).statistic, o.serial_lm(p).pvalue, o.serial_lm(p).rows["F 통계량"]],
                       [d["bg"][str(p)][0], d["bg"][str(p)][1], d["bg"][str(p)][2]], 1e-9) for p in (1, 2, 4))
        check(f"[{k}] 계열상관 LM(1·2·4) = 기준값", ok)
        w = o.white()
        check(f"[{k}] White LM·F = 기준값", close([w.statistic, w.pvalue, w.rows["F 통계량"]], [d["white"][0], d["white"][1], d["white"][2]], 1e-9))
        b = o.breusch_pagan()
        check(f"[{k}] Breusch-Pagan(Koenker·원래) = 기준값", close([b.statistic, b.rows["F 통계량"], b.rows["설명 제곱합/2(원래 BP)"]],
                                                         [d["bp"][0], d["bp"][2], d["bp_original"]], 1e-9))
        check(f"[{k}] ARCH LM(1·4) = 기준값", all(close([o.arch(p).statistic, o.arch(p).rows["F 통계량"]],
                                                    [d["arch"][str(p)][0], d["arch"][str(p)][2]], 1e-9) for p in (1, 4)))
        j = o.normality()
        check(f"[{k}] Jarque-Bera·왜도·첨도 = 기준값", close([j.statistic, j.pvalue, j.rows["왜도"], j.rows["첨도"]], d["jb"], 1e-9))
        lb = o.ljungbox(8)
        check(f"[{k}] Ljung-Box Q(1~8) = 기준값", close(lb.table["Q"], d["lb_q"], 1e-9) and close(lb.table["p값"], d["lb_p"], 1e-7, 1e-15))
        check(f"[{k}] RESET(1·2) F = 기준값", all(close(o.reset(t).statistic, d["reset_f"][str(t)], 1e-9) for t in (1, 2)))
        wd = o.wald("c(2) + c(3) = 1", "c(1) = 0")
        check(f"[{k}] Wald F·p = 기준값", close([wd.statistic, wd.pvalue], d["wald"], 1e-9, 1e-15))
        check(f"[{k}] Chow(2008Q1) F = 기준값", close(o.chow("2008Q1").statistic, d["chow_2008Q1"], 1e-9))
        cu = o.cusum()
        yy, XX = o.eq._y.to_numpy(), o.eq._X.to_numpy()
        kk, nn = XX.shape[1], len(yy)
        w = []                                   # 독립 계산: 시점마다 직접 최소제곱(lstsq)으로 재귀 잔차
        for i in range(kk, nn):
            b_ = np.linalg.lstsq(XX[:i], yy[:i], rcond=None)[0]
            w.append((yy[i] - XX[i] @ b_) / np.sqrt(1 + XX[i] @ np.linalg.pinv(XX[:i].T @ XX[:i]) @ XX[i]))
        w = np.array(w)
        ref_cusum = np.cumsum(w / w.std(ddof=1))
        check(f"[{k}] CUSUM = 독립 계산(시점별 lstsq)·경계 = 기준값",
              close(cu.data["CUSUM"].to_numpy()[1:] - cu.data["CUSUM"].to_numpy()[0], ref_cusum[1:] - ref_cusum[0], 1e-6, 1e-9)
              and close(cu.data["상한"].iloc[-1], d["cusum_bound_last"], 1e-12))
    cp = eqs["cp"]
    check("Wald 한 문자열에 쉼표로 여러 제약", close(cp.wald("c(2) + c(3) = 1, c(1) = 0").statistic,
                                            REF["equations"]["cp"]["wald"][0], 1e-9))
    check("Wald: 항 순서대로 c(n) — 상수항을 뒤에 써도", close(
        wf.equation("e_ord").ls("log(CN) log(Y) log(CN(-1)) c").wald("c(1) + c(2) = 1", "c(3) = 0").statistic,
        REF["equations"]["cp"]["wald"][0], 1e-9))
    bad = ["c(2)*c(3) = 1", "c(2)/c(3) = 1", "__import__('os').system('echo x') = 0", "c(9) = 0", "c(2) > 1", "c(2) = = 1"]
    check("제약식은 선형·허용 목록만(코드 실행 불가)", all(raises(lambda b=b: cp.wald(b), ValueError) for b in bad))
    dg = cp.diagnostics()
    check("진단 한 표(OLS 7종)", list(dg.data.index) == ["계열상관 LM(2)", "White(교차항)", "Breusch-Pagan-Godfrey",
                                                    "Ljung-Box Q(4)", "ARCH LM(1)", "Jarque-Bera", "RESET(1)"])
    tq = quiet(lambda: wf.equation("e_tq").tsls("log(CN) c log(Y) log(CN(-1))",
                                               inst="log(Y(-1)) log(CN(-1)) log(POIL)"))
    check("TSLS 식: 회귀변수 검정은 오류, 잔차 검정·Wald는 됨",
          raises(lambda: tq.serial_lm(), ValueError, "OLS") and np.isfinite(tq.ljungbox(4).statistic)
          and np.isfinite(tq.wald("c(2) = 0").statistic) and len(tq.diagnostics().data) == 3)
    rec = cp.recursive()
    check("재귀 계수(마지막 = 전체 표본 OLS)", close(rec.iloc[-1].to_numpy(), REF["equations"]["cp"]["params"], 1e-9))
    check("CUSUM 그래프·결과 표시", cp.cusum().graph is not None and "CUSUM" in cp.cusum().output().text())
    yy, XX = cp.eq._y.to_numpy(), cp.eq._X.to_numpy()
    rr = D.recursive(yy, XX)
    exact = yy[-1] - XX[-1] @ np.linalg.lstsq(XX[:-1], yy[:-1], rcond=None)[0]
    check("재귀 잔차 마지막 = 직접 최소제곱(갱신 공식의 반올림 누적 없음)", close(rr["rresid"][-1], exact, 1e-9))

    print("\n" + "=" * 80)
    print("D. 단위근·공적분 (워크파일 식 입력)")
    print("=" * 80)
    s = REF["series"]
    for tr in ("n", "c", "ct"):
        for ic in ("bic", "aic"):
            a = wf.adf("log(Y)", trend=tr, ic=ic)
            ref = s[f"adf_{tr}_{ic}"]
            check(f"ADF {tr}/{ic}: 통계량·p·시차·임계값", close([a.statistic, a.pvalue], ref[:2], 1e-9)
                  and a.details["lags"] == ref[2] and close(list(a.details["crit"].values()), ref[3], 1e-12))
        a = wf.adf("dlog(Y)", trend=tr, lags=2)
        check(f"ADF {tr} 시차 지정(차분 계열)", close([a.statistic, a.pvalue], s[f"adf_diff_{tr}_lag2"], 1e-9))
    for tr in ("c", "ct"):
        for lg in ("auto", 4):
            k_ = wf.kpss("dlog(Y)", trend=tr, lags=lg)
            ref = s[f"kpss_{tr}_{lg}"]
            check(f"KPSS {tr}/{lg}", close([k_.statistic, k_.pvalue], ref[:2], 1e-9) and k_.details["lags"] == ref[2])
    for tr in ("c", "ct"):
        e = wf.coint("log(CN)", "log(Y)", trend=tr)
        ref = s[f"eg_{tr}"]
        check(f"Engle-Granger {tr}: 통계량·p·임계값", close([e.statistic, e.pvalue], ref[:2], 1e-9)
              and close(list(e.details["crit"].values()), ref[2], 1e-12))
    for det in (0, 1):
        j = wf.johansen("log(CN) log(Y) log(I)", det=det, lags=2)
        ref = s[f"johansen_{det}_2"]
        check(f"Johansen det={det}: 고유값·트레이스·최대 고유값", close(j.details["eig"], ref["eig"], 1e-8)
              and close(j.details["trace"], ref["trace"], 1e-8) and close(j.details["maxeig"], ref["maxeig"], 1e-8))
    check("Johansen 결과 표(순위별)", list(j.table.index) == ["순위 ≤ 0", "순위 ≤ 1", "순위 ≤ 2"])
    check("검정은 표본 구간만 쓴다", quiet(lambda: (wf.smpl("2000Q1", "2019Q4"), wf.adf("log(Y)")))[1]
          .details["nobs"] < s["n"] - 1 and wf.adf("log(Y)").info["표본"] == "2000Q1~2019Q4")
    wf.smpl("@all")
    check("pandas Series 그대로도 받음", close(wf.adf(np.log(wf["Y"]), trend="ct").statistic,
                                         s["adf_ct_bic"][0], 1e-9))
    w3 = eqn.wfcreate("gap", "Q", "2000Q1", "2010Q4")
    v = np.cumsum(np.random.default_rng(1).standard_normal(44))
    v[20] = np.nan
    w3["X"] = v
    check("표본 안쪽 결측 → 분명한 오류", raises(lambda: w3.adf("X"), ValueError, "결측"))
    check("eval: 식 → Series(워크파일에 쓰지 않음)", close(wf.eval("log(Y)").dropna(), np.log(wf["Y"]).dropna(), 1e-15)
          and "log(Y)" not in wf.data.columns)
    check("MacKinnon p값 경계(아주 작음/큼)", U.mackinnon_p(-30.0, "c") == 0.0 and U.mackinnon_p(5.0, "c") == 1.0)

    print("\n" + "=" * 80)
    print("E. 추정법 확장 — WLS·GMM·LIML·누락/불필요 변수·PDL (D20)")
    print("=" * 80)
    d = EREF["wls"]
    w = wf.equation("e_wls").wls(d["spec"], weights=d["weights"])
    r = w.results
    check("WLS 계수·표준오차 = 기준값", close(r.params, d["params"], 1e-10) and close(r.bse, d["bse"], 1e-10))
    check("WLS 로그우도·R²·F·SSR·AIC = 기준값", close([r.llf, r.rsquared, r.fvalue, r.ssr, r.aic],
                                                [d["llf"], d["rsquared"], d["fvalue"], d["ssr"], d["aic"]], 1e-10))
    check("WLS 강건(HC1) 표준오차 = 기준값", close(w.eq._results.set_cov("hc1").bse, d["bse_hc1"], 1e-9))
    w.set_cov(None)
    eqw = w.eq
    check("WLS 잔차는 가중 전 값(y − Xb) — 연립 풀이와 같은 뜻",
          close(eqw.residuals, eqw._y - eqw._X.to_numpy() @ r.params.to_numpy(), 1e-12)
          and close(eqw.residual_series().loc[eqw.residuals.index], eqw.residuals, 1e-9, 1e-12))
    w1 = wf.equation("e_w1").wls(d["spec"], weights="Y/Y")
    check("가중치가 모두 1이면 OLS와 같음", close(w1.coefs, eqs["cp"].coefs, 1e-10) and close(w1.stderrs, eqs["cp"].stderrs, 1e-10))
    wa = wf.equation("e_wa").wls(d["spec"], weights="Y", wtype="var")
    wb = wf.equation("e_wb").wls(d["spec"], weights="1/Y", wtype="ivar")
    wc = wf.equation("e_wc").wls(d["spec"], weights="Y^-0.5", wtype="istdev")
    check("가중치 종류: 분산 X = 1/분산 1/X = 1/표준편차 X^-½", close(wa.coefs, wb.coefs, 1e-10) and close(wa.coefs, wc.coefs, 1e-10))
    check("가중치 0 이하 → 분명한 오류", raises(lambda: wf.equation("e_wz").wls(d["spec"], weights="Y-Y"), ValueError, "0 이하"))
    check("wls 가중치 없이 → 오류", raises(lambda: eqn.Equation(d["spec"], wf._data, method="wls"), Exception, "가중치"))

    iv = EREF["iv"]
    t = wf.equation("e_t").tsls(iv["spec"])
    check("TSLS = 기준값(linearmodels)", close(t.coefs, iv["tsls"]["params"], 1e-8) and close(t.stderrs, iv["tsls"]["bse"], 1e-8))
    # GMM 주 기준값은 50자리 직접 계산(linearmodels는 정규방정식이라 이 자료에서 상대 2.4e-7 어긋남 — 교차 확인만)
    for key, lm_key, kw, tag in (("gmm_mp_white", "gmm_white", {}, "White, 2단계"),
                                  ("gmm_mp_hac4", "gmm_hac4", {"weight": "hac", "lags": 4}, "HAC 4"),
                                  ("gmm_mp_iter", "gmm_iter", {"iterate": True}, "반복")):
        g = wf.equation("e_g").gmm(iv["spec"], **kw)
        ref, lm = iv[key], iv[lm_key]
        check(f"GMM({tag}) 계수·표준오차·J = 50자리 기준값", close(g.coefs, ref["params"], 1e-8)
              and close(g.stderrs, ref["bse"], 1e-8) and close(g.stats["j_statistic"], ref["j"], 1e-8),
              f"반복 {g.stats['gmm_iterations']}회" if kw.get("iterate") else "")
        check(f"GMM({tag}) ≈ linearmodels(교차 확인, 1e-5)", close(g.coefs, lm["params"], 1e-5)
              and close(g.stderrs, lm["bse"], 1e-5) and close(g.stats["j_statistic"], lm["j"], 1e-5))
    g = wf.equation("e_g").gmm(iv["spec"])
    check("GMM J p값 = χ²(도구 − 계수)", close(g.stats["j_pvalue"], iv["gmm_white"]["j_p"], 1e-5) and g.stats["j_df"] == 2)
    li = wf.equation("e_l").liml(iv["spec"])
    check("LIML 계수·표준오차·κ = 기준값", close(li.coefs, iv["liml"]["params"], 1e-9)
          and close(li.stderrs, iv["liml"]["bse"], 1e-9) and close(li.stats["liml_kappa"], iv["liml"]["kappa"], 1e-10))
    check("LIML 강건(HC1) 표준오차 = 기준값", close(wf.equation("e_lr").liml(iv["spec"], cov="hc1").stderrs,
                                              iv["liml_robust_hc1"]["bse"], 1e-9))
    check("LIML 내생 회귀변수 판별", li.stats["endogenous"] == iv["endogenous"], str(li.stats["endogenous"]))
    yv, Xv = eqs["cp"].eq._y, eqs["cp"].eq._X
    ge = R.gmm(yv, Xv, Xv)
    check("정확 식별(도구 = 회귀변수): GMM = OLS, J = 0", close(ge.params, R.ols(yv, Xv).params, 1e-9)
          and abs(ge.extra["j_statistic"]) < 1e-12 and not np.isfinite(ge.extra["j_pvalue"]))
    lo = R.liml(yv, Xv, Xv)
    check("내생 변수 없음: LIML κ = 1, = OLS", close(lo.extra["liml_kappa"], 1.0, 1e-12) and close(lo.params, R.ols(yv, Xv).params, 1e-9))
    check("GMM에 cov 지정 → 오류(가중행렬로 정함)", raises(lambda: eqn.Equation(iv["spec"], wf._data, method="gmm", cov="hc1"),
                                                     ValueError, "가중행렬"))

    nd = EREF["nested"]
    n1 = wf.equation("e_n").ls(nd["spec"])
    om = n1.omitted(*nd["omitted"])
    check("누락 변수 F·LR = 기준값", close([om.statistic, om.pvalue], nd["omitted_f"], 1e-9)
          and close([om.rows["LR 통계량"], om.rows["LR p값"]], nd["omitted_lr"], 1e-9)
          and om.info["관측치"] == nd["nobs_common"], f"공통 표본 {om.info['관측치']}")
    rd = n1.redundant(*nd["redundant"])
    check("불필요 변수 F·LR = 기준값", close([rd.statistic, rd.pvalue], nd["redundant_f"], 1e-9)
          and close([rd.rows["LR 통계량"], rd.rows["LR p값"]], nd["redundant_lr"], 1e-9))
    om2 = wf.equation("e_nw").wls(nd["spec"], weights=EREF["wls"]["weights"]).omitted(*nd["omitted"])
    check("WLS 식의 누락 변수 F = 기준값(가중 제곱합)", close([om2.statistic, om2.pvalue], nd["omitted_wls_f"], 1e-9))
    check("누락: 이미 있는 항 → 오류 · 불필요: 없는 항 → 오류",
          raises(lambda: n1.omitted("log(Y)"), ValueError, "이미") and raises(lambda: n1.redundant("X9"), ValueError, "없는"))
    check("누락·불필요 검정은 OLS·WLS만", raises(lambda: wf.equation("e_tt").tsls(iv["spec"]).omitted("@trend"), ValueError, "OLS"))
    rdc = n1.redundant("c")
    check("불필요 변수: 상수항 'c'도", np.isfinite(rdc.statistic) and rdc.details["q"] == 1)

    # PDL — 독립 계산과 비교: 제약 없는 차수 = 시차 수면 개별 시차 OLS, 제약이 있으면 제약 최소제곱(투영 공식)
    base = "log(CN) c log(CN(-1))"
    lagsx = " ".join(f"log(Y(-{i}))" if i else "log(Y)" for i in range(5))
    full = wf.equation("e_lag").ls(f"log(CN) c {lagsx} log(CN(-1))")
    p4 = wf.equation("e_p4").ls("log(CN) c pdl(log(Y), 4, 4) log(CN(-1))")
    dist = p4.eq.lag_distribution()
    check("PDL 차수 = 시차 수: 시차 계수 = 개별 시차 OLS", close(dist["계수"].iloc[:5], full.coefs.iloc[1:6], 1e-8)
          and close(dist["표준오차"].iloc[:5], full.stderrs.iloc[1:6], 1e-7))
    Xf, yf = full.eq._X.to_numpy(), full.eq._y.to_numpy()
    XtXi = np.linalg.inv(Xf.T @ Xf)
    bo = XtXi @ Xf.T @ yf
    ok = True
    for deg, cons in ((2, 0), (2, 1), (2, 2), (3, 3)):
        B = eqn.estimation.equation.pdl_basis(4, deg, cons)
        Q, _ = np.linalg.qr(B, mode="complete")
        Rl = Q[:, B.shape[1]:].T                                  # 시차 계수 β가 B의 열공간에 있다는 제약: Rβ = 0
        Rm = np.zeros((Rl.shape[0], Xf.shape[1]))
        Rm[:, 1:6] = Rl
        br = bo - XtXi @ Rm.T @ np.linalg.solve(Rm @ XtXi @ Rm.T, Rm @ bo)
        pe = wf.equation(f"e_p{deg}{cons}").ls(f"log(CN) c pdl(log(Y), 4, {deg}, {cons}) log(CN(-1))")
        ok &= close(pe.eq.lag_distribution()["계수"].iloc[:5], br[1:6], 1e-7, 1e-10)
        if cons in (1, 3):
            ok &= abs(float(B[0] @ np.ones(B.shape[1]) * 0)) == 0  # 형식 확인
    check("PDL 제약(없음·가까운 끝·먼 끝·양 끝) = 제약 최소제곱(독립 계산)", ok)
    B13 = eqn.estimation.equation.pdl_basis(4, 2, 3)
    c = 2
    near = np.array([(-1.0 - c) ** j for j in range(3)])
    far = np.array([(5.0 - c) ** j for j in range(3)])
    check("PDL 양 끝 제약: β₋₁ = β₅ = 0", B13.shape == (5, 1) and abs(near @ np.linalg.lstsq(np.column_stack([(np.arange(5) - c) ** j for j in range(3)]), B13, rcond=None)[0][:, 0]) < 1e-10
          and abs(far @ np.linalg.lstsq(np.column_stack([(np.arange(5) - c) ** j for j in range(3)]), B13, rcond=None)[0][:, 0]) < 1e-10)
    pe = wf.equation("e_pr").ls("log(CN) c pdl(log(Y), 4, 2) log(CN(-1))")
    check("PDL: 풀이 IR 잔차 = 추정 잔차", close(pe.eq.residual_series().loc[pe.eq.residuals.index], pe.eq.residuals, 1e-9, 1e-12))
    quiet(pe.forecast, "CN_PF", "2010Q1", "2012Q4", mode="static")
    fit = np.exp(pe.fitted.loc[wf["CN_PF"].dropna().index])
    check("PDL 식 단독 정적 예측 = exp(적합값)(풀이 허용오차 안)", close(wf["CN_PF"].dropna(), fit, 1e-7))
    check("PDL 인자 오류 → DSLError", raises(lambda: wf.equation("e_pe").ls("log(CN) c pdl(log(Y), 4)"), Exception, "pdl")
          and raises(lambda: wf.equation("e_pe2").ls("log(CN) c pdl(log(Y), 3, 5)"), Exception, "차수"))
    p2 = wf.equation("e_pw").ls("log(CN) c pdl(log(Y), 4, 2) log(CN(-1))")
    wd = p2.wald("c(2) = 0")
    check("PDL 계수도 c(n) 번호로 Wald", np.isfinite(wd.statistic) and "PDL01" in wd.notes[0])

    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "est.eqw")
        quiet(wf.save, path)
        w2 = quiet(eqn.wfopen, path)
        same = all(close(w2.obj(nm).coefs, wf.obj(nm).coefs, 1e-12) and w2.obj(nm).method == wf.obj(nm).method
                   for nm in ("e_wls", "e_g", "e_l", "e_pr"))
        om_r = w2.obj("e_nw").omitted(*nd["omitted"])
        check("저장·열기: WLS·GMM·LIML·PDL 식 그대로(가중치·PDL 구조 포함), 연 뒤 검정도",
              same and close(om_r.statistic, om2.statistic, 1e-10)
              and w2.obj("e_pr").lag_distribution().data.shape == (6, 3))

    print("\n" + "=" * 80)
    print("F. AR 오차·오차수정모형·예측 평가 (D21)")
    print("=" * 80)
    from scipy.optimize import minimize, minimize_scalar
    a1 = wf.equation("e_ar1").ls("log(CN) c log(Y) ar(1)")
    e = a1.eq
    yA = np.log(wf["CN"]).to_numpy()
    xA = np.log(wf["Y"]).to_numpy()
    rows = np.flatnonzero(wf.data.index.isin(e._y.index))

    def css(rho, rows=rows):
        """ρ를 고정하면 준차분 자료의 OLS — 조건부 제곱합을 ρ에 대해 따로 최소화(독립 계산)."""
        rho = np.atleast_1d(rho)
        ys = yA[rows] - sum(r * yA[rows - p] for r, p in zip(rho, range(1, len(rho) + 1)))
        Xs = np.column_stack([np.ones(len(rows)) * (1 - rho.sum()),
                              xA[rows] - sum(r * xA[rows - p] for r, p in zip(rho, range(1, len(rho) + 1)))])
        b = np.linalg.lstsq(Xs, ys, rcond=None)[0]
        return float(np.sum((ys - Xs @ b) ** 2)), b
    grid = np.linspace(-0.9995, 0.9995, 4001)                 # 전역 최소: 촘촘한 격자 → 그 칸 안에서 Brent
    g0 = grid[int(np.argmin([css(r)[0] for r in grid]))]
    opt = minimize_scalar(lambda r: css(r)[0], bounds=(g0 - 0.001, g0 + 0.001), method="bounded", options={"xatol": 1e-13})
    ssr1, b1 = css(opt.x)
    check("AR(1) = 집중 조건부 최소제곱의 전역 최소(독립 계산): 계수·ρ·SSR", close(a1.coefs.iloc[:2], b1, 1e-6)
          and close(a1.coefs.iloc[2], opt.x, 1e-6) and close(a1.stats["ssr"], ssr1, 1e-9), f"ρ = {opt.x:.6f}")
    # 국소 최소가 따로 있는 자료(가상): 오차가 단위근 가까운 AR(1) + 주기 성분 — OLS에서 출발하면 ρ≈0.96의 국소 최소,
    # 전역 최소는 ρ≈0.99
    rng_ar = np.random.default_rng(123)
    x_ar = np.cumsum(0.008 + 0.012 * rng_ar.standard_normal(160)) + 5
    u_ar = np.zeros(160)
    for t_ in range(1, 160):
        u_ar[t_] = 0.9 * u_ar[t_ - 1] + 0.01 * rng_ar.standard_normal()
    w_ar = eqn.wfcreate("arloc", "Q", "1980Q1", "2019Q4")
    w_ar["YY"] = np.exp(1 + 0.8 * x_ar + u_ar + 0.03 * np.sin(np.arange(160) / 8.0))
    w_ar["XX"] = np.exp(x_ar)
    a_loc = w_ar.equation("e_loc").ls("log(YY) c log(XX) ar(1)")
    rows_l = np.flatnonzero(w_ar.data.index.isin(a_loc.eq._y.index))
    yl, xl = np.log(w_ar["YY"]).to_numpy(), np.log(w_ar["XX"]).to_numpy()

    def css_l(rho):
        ys = yl[rows_l] - rho * yl[rows_l - 1]
        Xs = np.column_stack([np.full(len(rows_l), 1 - rho), xl[rows_l] - rho * xl[rows_l - 1]])
        b_ = np.linalg.lstsq(Xs, ys, rcond=None)[0]
        return float(np.sum((ys - Xs @ b_) ** 2))
    loc = minimize_scalar(css_l, bounds=(0.9, 0.975), method="bounded", options={"xatol": 1e-13})
    rho_l = float(a_loc.coefs.iloc[2])
    check("AR(1): OLS 출발의 국소 최소(ρ≈0.96)가 따로 있으면 알리고 전역 최소(ρ≈0.99)를 고른다",
          "국소 최소" in a_loc.stats.get("ar_note", "") and css_l(loc.x) > a_loc.stats["ssr"] and rho_l > 0.985
          and close(a_loc.stats["ssr"], css_l(rho_l), 1e-9), f"국소 ρ = {loc.x:.4f} · 전역 ρ = {rho_l:.4f}")
    a2 = wf.equation("e_ar2").ls("log(CN) c log(Y) ar(1 to 2)")
    rows2 = np.flatnonzero(wf.data.index.isin(a2.eq._y.index))
    opt2 = minimize(lambda r: css(r, rows2)[0], a2.coefs.iloc[2:].to_numpy() + 0.05, method="Nelder-Mead",
                    options={"xatol": 1e-12, "fatol": 1e-16, "maxiter": 20000})
    check("AR(2) = 집중 조건부 최소제곱(Nelder-Mead)", close(a2.coefs.iloc[2:], opt2.x, 1e-5)
          and a2.stats["ssr"] <= css(opt2.x, rows2)[0] * (1 + 1e-10))
    c = a1.coefs.to_numpy()

    def resid_np(cc):
        u = yA[rows] - cc[0] - cc[1] * xA[rows]
        return u - cc[2] * (yA[rows - 1] - cc[0] - cc[1] * xA[rows - 1])
    Jn = np.column_stack([(resid_np(c + h * np.eye(3)[i]) - resid_np(c - h * np.eye(3)[i])) / (2 * h)
                          for i, h in enumerate(1e-6 * np.maximum(1, np.abs(c)))])
    se_n = np.sqrt(np.diag(a1.stats["ssr"] / (len(rows) - 3) * np.linalg.inv(Jn.T @ Jn)))
    check("AR(1) 표준오차 = 유한차분 자코비안의 σ²(JᵀJ)⁻¹", close(a1.stderrs, se_n, 1e-6))
    check("AR: 풀이 IR 잔차 = 추정 잔차 εₜ", close(e.residual_series().loc[e.residuals.index], e.residuals, 1e-12, 1e-14))
    check("AR: 역근·정상성", close(a1.stats["ar_inverted_roots"][0][0], c[2], 1e-12) and a1.stats["ar_stationary"])
    quiet(a1.forecast, "CN_AR", "2015Q1", "2018Q4", mode="dynamic")
    s0 = wf._wt.index_of("2015Q1")
    u0 = yA[s0 - 1] - c[0] - c[1] * xA[s0 - 1]
    hh = np.arange(1, 17)
    fc = np.exp(c[0] + c[1] * xA[s0:s0 + 16] + c[2] ** hh * u0)
    check("AR(1) 동적 예측: uₜ = ρʰ·u(시작 전) — 수식 그대로", close(wf["CN_AR"].iloc[s0:s0 + 16], fc, 1e-7))
    check("AR 항: 저장 글자에 정규형으로 남아 복원됨", e.equation_str.endswith("ar(1)")
          and eqn.Equation(e.equation_str, wf._data).ar_lags == [1])
    check("AR 오차는 ls·fixed만", raises(lambda: wf.equation("e_ar_t").tsls("log(CN) c log(Y) ar(1) @inst log(Y(-1))"),
                                       Exception, "ar("))
    check("AR 식에는 OLS 전용 검정 불가(분명한 오류)", raises(a1.white, ValueError, "OLS"))

    m2 = wf.ecm("cons", "log(CN)", ["log(Y)"])
    lr = wf.obj("cons_lr")
    ecs = (np.log(wf["CN"]) - lr.coefs["const"] - lr.coefs["log(Y)"] * np.log(wf["Y"])).shift(1)
    yd = np.log(wf["CN"]).diff()
    xd = np.log(wf["Y"]).diff()
    dfm = pd.concat([yd, xd, ecs], axis=1).dropna()
    bm = np.linalg.lstsq(np.column_stack([np.ones(len(dfm)), dfm.iloc[:, 1], dfm.iloc[:, 2]]), dfm.iloc[:, 0], rcond=None)[0]
    check("ECM 두 단계: α·단기 계수 = 장기 잔차(-1)로 직접 OLS", close(m2.shortrun.coefs, bm, 1e-9)
          and close(m2.adjustment["계수"], bm[2], 1e-9) and m2.coint is not None)
    m3 = wf.ecm("cons_n", "log(CN)", ["log(Y)"], method="nls")
    un = wf.equation("e_uecm").ls("d(log(CN)) c d(log(Y)) log(CN(-1)) log(Y(-1))")
    pi, th, c0, g = (un.coefs[k] for k in ("log(CN(-1))", "log(Y(-1))", "const", "d(log(Y))"))
    check("ECM NLS = 제약 없는 ECM(OLS)의 재모수화: α = π, a = −c₀/π, b = −θ/π", close(m3.adjustment["계수"], pi, 1e-6)
          and close(m3.longrun()["계수"], [-c0 / pi, -th / pi], 1e-6) and close(m3.shortrun.coefs.iloc[3], g, 1e-6)
          and close(m3.shortrun.stats["ssr"], un.stats["ssr"], 1e-9))
    check("ECM 반감기 = ln½/ln(1+α)", close(m3.half_life, np.log(0.5) / np.log(1 + pi), 1e-6))
    quiet(m2.shortrun.forecast, "CN_EC", "2015Q1", "2016Q4", mode="dynamic")
    check("ECM 단기식 동적 예측(EC 항이 y를 따라 움직임)", np.isfinite(wf["CN_EC"].iloc[s0:s0 + 8]).all())

    act = wf["Y"].iloc[20:60]
    f1 = act * 1.01
    f2 = wf["Y"].shift(1).iloc[20:60]
    ev = eqn.stats.forecast_evaluate(act, f1)
    a_, f_ = act.to_numpy(), f1.to_numpy()
    e_ = f_ - a_
    mse = np.mean(e_ ** 2)
    sa, sf = a_.std(), f_.std()
    r_ = np.corrcoef(a_, f_)[0, 1]
    check("예측 평가: RMSE·MAE·MAPE·Theil U1 = 정의", close([ev["RMSE"], ev["MAE"], ev["MAPE(%)"], ev["Theil U1"]],
                                                     [np.sqrt(mse), np.mean(np.abs(e_)), 1.0,
                                                      np.sqrt(mse) / (np.sqrt(np.mean(f_ ** 2)) + np.sqrt(np.mean(a_ ** 2)))], 1e-12))
    check("예측 평가: MSE 분해 세 비중 합 = 1", close(ev[["편의 비중", "분산 비중", "공분산 비중"]].sum(), 1.0, 1e-10)
          and close(ev["분산 비중"], (sf - sa) ** 2 / mse, 1e-10))
    check("Theil U2: '변화 없음' 예측이면 1", close(eqn.stats.forecast_evaluate(act, f2.dropna())["Theil U2"], 1.0, 1e-12))
    d_ = (f2 - act) ** 2 - (f1 - act) ** 2
    d_ = d_.dropna().to_numpy()
    n_ = len(d_)
    for hh_ in (1, 4):
        dc = d_ - d_.mean()
        V = sum((1 if k == 0 else 2) * float(dc[k:] @ dc[:n_ - k]) / n_ for k in range(hh_))
        dm = d_.mean() / np.sqrt(V / n_)
        hln = dm * np.sqrt((n_ + 1 - 2 * hh_ + hh_ * (hh_ - 1) / n_) / n_)
        r = eqn.stats.diebold_mariano(act, f2, f1, h=hh_)
        check(f"Diebold-Mariano(h={hh_}): DM·HLN 보정·t(n−1) p = 정의대로",
              close([r.rows["DM(보정 전)"], r.statistic, r.pvalue], [dm, hln, 2 * stats_t.sf(abs(hln), n_ - 1)], 1e-10))
    r1 = eqn.stats.diebold_mariano(act, f1, f2)
    r2 = eqn.stats.diebold_mariano(act, f2, f1)
    check("DM: 예측 순서를 바꾸면 부호만 바뀜, 같은 예측이면 NA", close(r1.statistic, -r2.statistic, 1e-12)
          and close(r1.pvalue, r2.pvalue, 1e-12) and not np.isfinite(eqn.stats.diebold_mariano(act, f1, f1).statistic))
    tab = wf.forecast_eval("Y", "Y*1.01", "Y(-1)", start="2000Q1", end="2009Q4")
    check("wf.forecast_eval: 표(.data DataFrame, 행 = 예측)", list(tab.data.index) == ["Y*1.01", "Y(-1)"]
          and int(tab.data["N"].iloc[0]) == 40)
    check("wf.dm_test", np.isfinite(wf.dm_test("Y", "Y(-1)", "Y*1.01", start="2000Q1", end="2009Q4").pvalue))

    print("\n" + "=" * 80)
    print("G. 시스템 추정 — OLS·SUR·2SLS·3SLS·FIML·식 사이 제약 (D22)")
    print("=" * 80)
    from equion.stats import system as Sy
    sr = EREF["system"]
    sy = wf.system("s_ref")
    sy.append(*sr["lines"])
    for key, run in (("ols", lambda: sy.ols()), ("sur", lambda: sy.sur()), ("sur_it", lambda: sy.sur(iterate=True)),
                     ("sur_restricted", lambda: sy.sur(restrict=sr["sur_restricted"]["restrict"])),
                     ("tsls", lambda: sy.tsls()), ("3sls", lambda: sy.three_sls())):
        quiet(run)
        tol = 1e-8 if key == "sur_it" else 1e-9
        check(f"시스템 {key} 계수·표준오차 = 기준값(linearmodels)", close(sy.coefs, sr[key]["params"], tol)
              and close(sy.stderrs, sr[key]["bse"], tol), f"표본 {len(sy.resid)}기")
    quiet(sy.sur, restrict="c(2) = c(5)")
    rs = sy.coefs
    sh = wf.system("s_shared")
    sh.append("dlog(CN) = c(1) + c(2)*dlog(Y) + c(3)*dlog(CN(-1))",
              "dlog(I) = c(4) + c(2)*dlog(Y) + c(6)*dlog(I(-1))")
    quiet(sh.sur)
    check("공유 계수 c(2) = restrict 'c(2) = c(5)'(같은 추정)", close(sh.coefs.to_numpy(), rs.drop("c(5)").to_numpy(), 1e-10)
          and close(sh.stderrs.to_numpy(), sy.stderrs.drop("c(5)").to_numpy(), 1e-9))
    quiet(sy.sur, iterate=True)
    it_c = sy.coefs
    quiet(sy.fiml)
    check("FIML(우변에 현시점 내생변수 없음) = 반복 SUR(정규 최우)", close(sy.coefs, it_c, 1e-6)
          and sy.fit.extra["converged"], f"기울기 {sy.fit.extra['gradient_norm']:.1e}")
    quiet(sy.sur)
    mm = wf.model("m_sys")
    mm.merge(sy)
    ok = True
    for obj, col in zip(mm.equations, sy.resid.columns):
        rr = obj.eq.residual_series().loc[sy.resid.index]
        ok &= close(rr, sy.resid[col], 1e-10, 1e-12) and obj.method == "fixed"
    check("모델 merge: 시스템 계수로 고정한 식 — 풀이 잔차 = 시스템 잔차", ok)
    rq = quiet(mm.solve, "2010Q1", "2012Q4")
    check("시스템으로 만든 모델 풀이", rq.counts()["ok"] == 12)
    Rw = np.zeros(6)
    Rw[1], Rw[4] = 1, -1
    V = sy.cov().to_numpy()
    w_ = float((Rw @ sy.coefs.to_numpy()) ** 2 / (Rw @ V @ Rw))
    check("시스템 Wald χ² = (Rb)²/(RVRᵀ)", close(quiet(sy.wald, "c(2) = c(5)").statistic, w_, 1e-12))
    quiet(sy.sur, restrict="c(2) = c(5)")
    check("이미 넣은 제약을 Wald로 검정 → 분명한 오류(특이 행렬 대신)", raises(lambda: sy.wald("c(2) = c(5)"), ValueError, "이미"))
    quiet(sy.sur)

    # 연립(현시점 내생변수가 우변에) — 합성 자료로 알려진 동치를 확인
    rng = np.random.default_rng(11)
    T = 160
    ws = quiet(eqn.wfcreate, "simul", "Q", "1990Q1", "2029Q4")   # 160기
    X1, X2, X3 = rng.standard_normal((3, T))
    Ue = rng.multivariate_normal([0, 0], [[1, .5], [.5, 1]], size=T)
    Mm = np.array([[1, -0.4], [0.3, 1]])
    Yv = np.linalg.solve(Mm, np.column_stack([1 + .5 * X1 + Ue[:, 0], -1 + .8 * X2 + .6 * X3 + Ue[:, 1]]).T).T
    for nm, v in (("Y1", Yv[:, 0]), ("Y2", Yv[:, 1]), ("X1", X1), ("X2", X2), ("X3", X3)):
        ws[nm] = v
    ex = ws.system("exact")
    # 각 식이 외생변수를 정확히 하나씩 뺀다(식1: X2, 식2: X1) → 정확 식별
    ex.append("Y1 = c(1) + c(2)*Y2 + c(3)*X1 + c(4)*X3", "Y2 = c(5) + c(6)*Y1 + c(7)*X2 + c(8)*X3", "@inst X1 X2 X3")
    quiet(ex.tsls)
    b2 = ex.coefs
    quiet(ex.three_sls)
    b3 = ex.coefs
    quiet(ex.fiml)
    check("정확 식별 연립: FIML = 3SLS = 2SLS", close(ex.coefs, b2, 1e-7) and close(b3, b2, 1e-10)
          and ex.fit.extra["converged"])
    ov = ws.system("over")
    ov.append("Y1 = c(1) + c(2)*Y2 + c(3)*X1", "Y2 = c(4) + c(5)*Y1 + c(6)*X2", "@inst X1 X2 X3")
    a_ = ov._arrays(need_jac=True)

    def ll_at(b):
        Ee = np.column_stack([y - X @ b for y, X in zip(a_["ys"], a_["Xs"])])
        Jm = a_["A"] + np.einsum("ktij,k->tij", a_["B"], b)
        return Sy.gaussian_loglik(Ee, float(np.linalg.slogdet(Jm)[1].sum()))
    quiet(ov.three_sls)
    l3 = ll_at(ov.coefs.to_numpy())
    quiet(ov.fiml)
    bf = ov.coefs.to_numpy()
    check("과대 식별 연립: FIML 로그우도 ≥ 3SLS 로그우도, 기울기 ≈ 0", ov.fit.loglik >= l3 and close(ov.fit.loglik, ll_at(bf), 1e-12)
          and ov.fit.extra["gradient_norm"] < 1e-6, f"{ov.fit.loglik:.4f} ≥ {l3:.4f}")
    hs = 1e-4 * np.maximum(1, np.abs(bf))
    H = np.zeros((len(bf), len(bf)))
    I6 = np.eye(len(bf))
    for i in range(len(bf)):
        for j in range(len(bf)):
            H[i, j] = (ll_at(bf + hs[i] * I6[i] + hs[j] * I6[j]) - ll_at(bf + hs[i] * I6[i] - hs[j] * I6[j])
                       - ll_at(bf - hs[i] * I6[i] + hs[j] * I6[j]) + ll_at(bf - hs[i] * I6[i] - hs[j] * I6[j])) / (4 * hs[i] * hs[j])
    se_h = np.sqrt(np.diag(np.linalg.inv(-H)))
    check("FIML 표준오차 = 로그우도의 수치 헤시안(독립 계산)", close(ov.stderrs, se_h, 1e-3))
    with tempfile.TemporaryDirectory() as tmp:
        pth = os.path.join(tmp, "sys.eqw")
        quiet(ws.save, pth)
        w3 = quiet(eqn.wfopen, pth)
        check("저장·열기: 시스템 객체(식·도구·추정법) 다시 추정해 같은 계수", close(w3.obj("over").coefs, ov.coefs, 1e-8)
              and w3.obj("over").method == "fiml")
    bad = ws.system("bad")
    check("시스템 오류: 항등식·비선형 계수·같은 목표·ar 항·도구 없는 3SLS",
          raises(lambda: bad.append("Y1 = Y2 + X1").ols(), ValueError, "항등식")
          and raises(lambda: ws.system("b2").append("Y1 = c(1)*c(2)*X1").ols(), ValueError, "선형")
          and raises(lambda: ws.system("b3").append("Y1 c X1", "Y1 c X2").ols(), ValueError, "목표변수")
          and raises(lambda: ws.system("b4").append("Y1 c X1 ar(1)").ols(), ValueError, "ar")
          and raises(lambda: ws.system("b5").append("Y1 c Y2").three_sls(), ValueError, "도구"))

    print("\n" + "=" * 80)
    print("H. VAR·VECM (D23)")
    print("=" * 80)
    from equion.stats import var as VV
    vr = EREF["var"]
    for tr in ("c", "ct"):
        v = quiet(wf.var, f"v_{tr}", vr["series"], lags=2, trend=tr)
        d = vr[tr]
        f = v.fit
        check(f"VAR(2,{tr}) 계수·표준오차·Σ = 기준값(statsmodels)", close(f.coefs, d["params"], 1e-10)
              and close(v.stderrs.to_numpy(), d["bse"], 1e-9) and close(f.sigma_u, d["sigma_u"], 1e-10))
        ic = f.info_criteria()
        check(f"VAR(2,{tr}) AIC·BIC·HQ·FPE = 기준값", close([ic["aic"], ic["bic"], ic["hqic"], ic["fpe"]], d["ic"], 1e-10))
        check(f"VAR(2,{tr}) 직교 충격반응·분산분해·예측 = 기준값", close(VV.irf(f, 8), d["irf_orth8"], 1e-9)
              and close(VV.fevd(f, 8), d["fevd8"], 1e-9) and close(v.forecast(5).to_numpy(), d["forecast5"], 1e-9))
        g = quiet(v.granger, vr["series"][0], vr["series"][1:])
        check(f"VAR(2,{tr}) Granger F·p·자유도 = 기준값", close([g.statistic, g.pvalue], d["granger_0_12"][:2], 1e-9)
              and g.rows["자유도"] == f"({d['granger_0_12'][2][0]}, {d['granger_0_12'][2][1]})")
    v = wf.obj("v_c")
    lo_ = v.lag_order(4).data
    check("VAR 시차 선택: 같은 표본의 AIC·BIC와 고른 시차 = 기준값", close(lo_["AIC"], vr["select4"]["aic"], 1e-10)
          and close(lo_["BIC"], vr["select4"]["bic"], 1e-10)
          and int(lo_.index[lo_["AIC*"] == "*"][0]) == vr["select4"]["selected"]["aic"])
    check("VAR 안정성: 동반행렬 근 = AR 다항식 det(I − ΣAᵢzⁱ) = 0의 역근", v.fit.is_stable
          and close(np.sort(np.abs(v.fit.eigenvalues())), np.sort(np.abs(np.linalg.eigvals(v.fit.companion()))), 1e-12))
    mv = wf.model("m_var")
    mv.merge(v)
    rr = quiet(mv.solve, "2010Q1", "2012Q4", mode="static")
    resid_ok = all(close(o.eq.residual_series().loc[v.resid.index], v.resid.iloc[:, j], 1e-10, 1e-13)
                   for j, o in enumerate(mv.equations))
    check("VAR → 모델 merge: 고정 계수 식의 잔차 = VAR 잔차, 풀림", resid_ok and rr.counts()["ok"] == 12)
    vt = quiet(wf.var, "v_ct2", vr["series"], lags=2, trend="ct")
    mt = wf.model("m_var_ct")
    mt.merge(vt)
    check("VAR(추세) → 모델: @trend로 옮긴 추세가 같은 잔차", all(
        close(o.eq.residual_series().loc[vt.resid.index], vt.resid.iloc[:, j], 1e-9, 1e-12) for j, o in enumerate(mt.equations)))
    ve = EREF["vecm"]
    ok_all = True
    for det in ("ci", "co", "n", "li", "lo", "cili", "colo"):
        k_ = quiet(wf.vecm, f"k_{det}", ve["series"], lags_diff=2, rank=1, deterministic=det)
        d, f = ve[det], k_.fit
        ok = (close(f.alpha, d["alpha"], 1e-7) and close(f.beta[:3], d["beta"], 1e-7) and close(f.gamma, d["gamma"], 1e-7)
              and close(f.sigma_u, d["sigma_u"], 1e-9) and close(k_.forecast(4).to_numpy(), d["forecast4"], 1e-9))
        if np.size(d["det_coef_coint"]):
            ok &= close(f.beta[3:].ravel(), np.asarray(d["det_coef_coint"]).T.ravel(), 1e-6)
        if np.size(d["det_coef"]):
            ok &= close(f.det_coef, d["det_coef"], 1e-7)
        ok_all &= ok
        if not ok:
            print("     VECM 불일치:", det)
    check("VECM(Johansen 최우) α·β·Γ·결정항·Σ·예측 = 기준값 — 결정항 7종(ci·co·n·li·lo·cili·colo)", ok_all)
    kk = wf.obj("k_ci")
    jo = quiet(wf.johansen, ve["series"], det=0, lags=2)          # det=0: 제약 없는 상수 = VECM 'co'
    check("VECM('co') 고윳값 = Johansen 검정(det=0) 고윳값", close(wf.obj("k_co").fit.eigenvalues, jo.details["eig"], 1e-10))
    mk = wf.model("m_vecm")
    mk.merge(kk)
    rk = quiet(mk.solve, "2010Q1", "2012Q4", mode="static")
    resid_k = all(close(o.eq.residual_series().loc[wf.data.index[wf._index_of("2010Q1"):wf._index_of("2012Q4") + 1]],
                        pd.Series(kk.fit.resid[:, j], index=wf._test_frame(ve["series"]).index[3:]).loc["2010-01-01":"2012-10-01"],
                        1e-8, 1e-12) for j, o in enumerate(mk.equations))
    check("VECM → 모델 merge: 고정 계수 식의 잔차 = VECM 잔차, 풀림", resid_k and rk.counts()["ok"] == 12)
    with tempfile.TemporaryDirectory() as tmp:
        pth = os.path.join(tmp, "var.eqw")
        quiet(wf.save, pth)
        w4 = quiet(eqn.wfopen, pth)
        check("저장·열기: VAR·VECM 객체(다시 추정해 같은 계수)", close(w4.obj("v_c").fit.coefs, wf.obj("v_c").fit.coefs, 1e-12)
              and close(w4.obj("k_ci").fit.alpha, kk.fit.alpha, 1e-12))

    print("\n" + "=" * 80)
    print("I. 의존성")
    print("=" * 80)
    check("statsmodels를 불러오지 않는다", "statsmodels" not in sys.modules)
    from importlib.metadata import requires
    try:
        reqs = requires("equion") or []
    except Exception:  # noqa: BLE001 — 설치하지 않고 저장소에서 돌릴 때
        reqs = []
    check("패키지 의존성에 statsmodels 없음", not any(r.lower().startswith("statsmodels") for r in reqs), str(len(reqs)))

    print("\n" + "=" * 80)
    total = len(PASS) + len(FAIL)
    print(f"  RESULT: {len(PASS)} PASS / {len(FAIL)} FAIL  (total {total})  — {time.time() - t0:.1f}s")
    print("  " + ("[OK] ALL PASSED!" if not FAIL else "실패: " + ", ".join(FAIL)))
    print("=" * 80)
    return len(FAIL)


def test_suite():
    """pytest 진입점 — 이 파일의 검사 묶음 전체(하나라도 실패하면 실패). `python tests/test_stats.py`와 같은 검사."""
    assert main() == 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(99)
