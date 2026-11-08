"""tests/fixtures/estimation_reference.json 생성 — 추정법 확장(WLS·GMM·LIML·누락/불필요 변수·시스템·VAR·VECM)의 기준값.

statsmodels(WLS·F/LR 비교)와 linearmodels(IV-GMM·LIML·2SLS)로 한 번 계산해 고정한다. Equion은 둘 다에 의존하지
않으므로(DECISIONS D17) **별도 환경**에서만 돌린다:
    PYTHONPATH=<저장소> <statsmodels·linearmodels·mpmath가 있는 python> tests/fixtures/make_estimation_reference.py
y·X·Z·가중치는 Equion이 만든 것을 그대로 넘긴다 — 같은 자료에서 계산 방법만 비교한다.

GMM은 linearmodels가 정규방정식으로 풀어 이 자료에서 계수가 상대 2.4e-7 어긋난다(조건수 제곱). 그래서 GMM의 주
기준값은 mpmath 50자리로 같은 공식을 직접 계산한 값(gmm_mp_*)이고, linearmodels 값은 느슨한 교차 확인용이다.
"""
import json
import os
import sys
import warnings

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
warnings.simplefilter("ignore")
import linearmodels  # noqa: E402
import numpy as np  # noqa: E402
import statsmodels  # noqa: E402
import statsmodels.api as sm  # noqa: E402
from linearmodels.iv import IV2SLS, IVGMM, IVLIML  # noqa: E402

import equion as eqn  # noqa: E402

eqn.verbose(0)
L = lambda a: [float(v) for v in np.atleast_1d(np.asarray(a, dtype=float))]  # noqa: E731
wf = eqn.datasets.load("toy_q")             # 예제 자료(가상) — 저장소 밖에서도 같은 기준값
wf.smpl("@all")
out = {"_provenance": f"statsmodels {statsmodels.__version__} · linearmodels {linearmodels.__version__} · "
                      f"numpy {np.__version__} 로 계산(tests/fixtures/make_estimation_reference.py). "
                      "Equion 자체 구현이 같은 값을 내는지 tests/test_stats.py가 확인한다."}

# --- WLS ---------------------------------------------------------------------
WLS_SPEC = "log(CN) c log(Y) log(CN(-1))"
WLS_W = "1/(@trend+10)"
e = wf.equation("w").wls(WLS_SPEC, weights=WLS_W).eq
r = sm.WLS(e._y, e._X, weights=e._W).fit()
out["wls"] = {"spec": WLS_SPEC, "weights": WLS_W, "params": L(r.params), "bse": L(r.bse),
              "bse_hc1": L(r.get_robustcov_results("HC1").bse), "llf": float(r.llf), "rsquared": float(r.rsquared),
              "fvalue": float(r.fvalue), "ssr": float(r.ssr), "aic": float(r.aic)}

# --- 도구변수 식(GMM·LIML·TSLS) ---------------------------------------------
# 성장률 식 — 수준(로그) 식은 예제 자료에서 회귀변수가 거의 공선이라(조건수가 큼) 계산 방법끼리 말자리가 갈린다
IV_SPEC = ("dlog(CN) c dlog(Y) dlog(CN(-1)) "
           "@inst dlog(Y(-1)) dlog(Y(-2)) dlog(I(-1)) dlog(CN(-1))")
t = wf.equation("t").tsls(IV_SPEC).eq
y = t._y
X = t._X
Z = t._Z
names = list(X.columns)
exog_cols = [c for c in names if any(np.array_equal(X[c].to_numpy(), Z[z].to_numpy()) for z in Z.columns)]
endog_cols = [c for c in names if c not in exog_cols]
instr = Z[[z for z in Z.columns if not any(np.array_equal(Z[z].to_numpy(), X[c].to_numpy()) for c in exog_cols)]]
dep, exog, endog = y, X[exog_cols], X[endog_cols]
pick = lambda res: [float(res.params[c]) for c in names]  # noqa: E731
pick_se = lambda res: [float(res.std_errors[c]) for c in names]  # noqa: E731
iv = {"spec": IV_SPEC, "names": names, "endogenous": endog_cols}
r = IV2SLS(dep, exog, endog, instr).fit(cov_type="unadjusted", debiased=True)
iv["tsls"] = {"params": pick(r), "bse": pick_se(r)}
r = IVGMM(dep, exog, endog, instr, weight_type="robust").fit(cov_type="robust")
iv["gmm_white"] = {"params": pick(r), "bse": pick_se(r), "j": float(r.j_stat.stat), "j_p": float(r.j_stat.pval)}
r = IVGMM(dep, exog, endog, instr, weight_type="kernel", kernel="bartlett", bandwidth=4).fit(
    cov_type="kernel", kernel="bartlett", bandwidth=4)
iv["gmm_hac4"] = {"params": pick(r), "bse": pick_se(r), "j": float(r.j_stat.stat)}
r = IVGMM(dep, exog, endog, instr, weight_type="robust").fit(iter_limit=1000, tol=1e-14, cov_type="robust")
iv["gmm_iter"] = {"params": pick(r), "bse": pick_se(r), "j": float(r.j_stat.stat)}
r = IVLIML(dep, exog, endog, instr).fit(cov_type="unadjusted", debiased=True)
iv["liml"] = {"params": pick(r), "bse": pick_se(r), "kappa": float(r.kappa)}
r = IVLIML(dep, exog, endog, instr).fit(cov_type="robust", debiased=True)
iv["liml_robust_hc1"] = {"bse": pick_se(r)}


def gmm_mp(Xn, Zn, yn, kind="white", L=None, iterate=False):
    """같은 GMM 공식을 50자리로: 1단계 TSLS → W = S⁻¹ → b, 샌드위치 공분산, J = n·ḡᵀWḡ."""
    import mpmath as mp
    mp.mp.dps = 50
    n = len(yn)
    Xm, Zm, ym = mp.matrix(Xn.tolist()), mp.matrix(Zn.tolist()), mp.matrix(yn.tolist())
    ZX, Zy = Zm.T * Xm, Zm.T * ym
    ZZi = (Zm.T * Zm) ** -1
    b = (ZX.T * ZZi * ZX) ** -1 * (ZX.T * ZZi * Zy)
    G, gy = ZX / n, Zy / n

    def S_of(bb):
        e = ym - Xm * bb
        u = [Zm[i, :] * e[i] for i in range(n)]
        S = mp.zeros(Zn.shape[1], Zn.shape[1])
        for i in range(n):
            S += u[i].T * u[i]
        if kind == "hac":
            for lag in range(1, L + 1):
                g = mp.zeros(Zn.shape[1], Zn.shape[1])
                for i in range(lag, n):
                    g += u[i].T * u[i - lag]
                S += (1 - mp.mpf(lag) / (L + 1)) * (g + g.T)
        return S / n
    for _ in range(200 if iterate else 1):
        W = S_of(b) ** -1
        A = G.T * W * G
        b_new = A ** -1 * (G.T * W * gy)
        moved = max(abs(b_new[i] - b[i]) for i in range(len(b)))
        b = b_new
        if moved < mp.mpf(10) ** -40:
            break
    e = ym - Xm * b
    Ai = A ** -1
    cov = Ai * (G.T * W * S_of(b) * W * G) * Ai / n
    gbar = Zm.T * e / n
    J = n * (gbar.T * W * gbar)[0]
    return ([float(b[i]) for i in range(len(b))], [float(mp.sqrt(cov[i, i])) for i in range(len(b))], float(J))


Xn, Zn, yn = X.to_numpy(), Z.to_numpy(), y.to_numpy()
for key, kw in (("gmm_mp_white", {}), ("gmm_mp_hac4", {"kind": "hac", "L": 4}), ("gmm_mp_iter", {"iterate": True})):
    b_, se_, j_ = gmm_mp(Xn, Zn, yn, **kw)
    iv[key] = {"params": b_, "bse": se_, "j": j_}
out["iv"] = iv

# --- 누락·불필요 변수(F·LR) --------------------------------------------------
NEST_SPEC = "log(I) c log(Y) log(I(-1)) @seas"
e = wf.equation("n").ls(NEST_SPEC).eq
ADD = ["log(Y(-1))", "log(I(-2))"]
new = e.evaluate_terms(ADD).loc[e._y.index]
keep = np.isfinite(new.to_numpy()).all(axis=1)
small = sm.OLS(e._y[keep], e._X[keep]).fit()
big = sm.OLS(e._y[keep], np.column_stack([e._X[keep].to_numpy(), new[keep].to_numpy()])).fit()
f = big.compare_f_test(small)
lr = big.compare_lr_test(small)
nest = {"spec": NEST_SPEC, "omitted": ADD, "omitted_f": [float(f[0]), float(f[1])], "omitted_lr": [float(lr[0]), float(lr[1])],
        "nobs_common": int(keep.sum())}
DROP = ["log(Y)"]
full = sm.OLS(e._y, e._X).fit()
sub = sm.OLS(e._y, e._X.drop(columns=DROP)).fit()
f, lr = full.compare_f_test(sub), full.compare_lr_test(sub)
nest["redundant"] = DROP
nest["redundant_f"] = [float(f[0]), float(f[1])]
nest["redundant_lr"] = [float(lr[0]), float(lr[1])]
# WLS 식에서의 누락 변수 F(가중 제곱합)
ew = wf.equation("nw").wls(NEST_SPEC, weights=WLS_W).eq
new = ew.evaluate_terms(ADD).loc[ew._y.index]
keep = np.isfinite(new.to_numpy()).all(axis=1)
w = ew._W[keep]
small = sm.WLS(ew._y[keep], ew._X[keep], weights=w).fit()
big = sm.WLS(ew._y[keep], np.column_stack([ew._X[keep].to_numpy(), new[keep].to_numpy()]), weights=w).fit()
nest["omitted_wls_f"] = [float(v) for v in big.compare_f_test(small)[:2]]
out["nested"] = nest

# --- 시스템(SUR·OLS·2SLS·3SLS, 식 사이 제약) — linearmodels.system ----------------------------------
from linearmodels.system import SUR as LM_SUR, IV3SLS  # noqa: E402
import pandas as pd  # noqa: E402

SYS_LINES = ["dlog(CN) = c(1) + c(2)*dlog(Y) + c(3)*dlog(CN(-1))",
             "dlog(I) c dlog(Y) dlog(I(-1))",
             "@inst dlog(Y(-1)) dlog(Y(-2)) dlog(CN(-1)) dlog(I(-1))"]
s_obj = wf.system("sysref")
s_obj.append(*SYS_LINES)
a = s_obj._arrays()                         # SUR·OLS: 식의 변수만으로 정한 공통 표본
coefs = a["coefs"]
used = [[j for j in range(len(coefs)) if np.any(X[:, j] != 0)] for X in a["Xs"]]
names = []
eqs_sur, eqs_iv = {}, {}
for i, (yv, X, u) in enumerate(zip(a["ys"], a["Xs"], used)):
    idx = pd.RangeIndex(len(yv))
    cols = {f"c{coefs[j]}": X[:, j] for j in u}
    names += [f"e{i}_c{coefs[j]}" for j in u]
    eqs_sur[f"e{i}"] = {"dependent": pd.Series(yv, idx), "exog": pd.DataFrame(cols, idx)}
a = s_obj._arrays(need_inst=True)           # 2SLS·3SLS: 도구까지 관측되는 공통 표본
for i, (yv, X, Z, u) in enumerate(zip(a["ys"], a["Xs"], a["Zs"], used)):
    idx = pd.RangeIndex(len(yv))
    cols = {f"c{coefs[j]}": X[:, j] for j in u}
    exog = {k: v for k, v in cols.items() if any(np.array_equal(v, Z[:, c]) for c in range(Z.shape[1]))}
    endog = {k: v for k, v in cols.items() if k not in exog}
    ins = {f"z{c}": Z[:, c] for c in range(Z.shape[1]) if not any(np.array_equal(Z[:, c], v) for v in exog.values())}
    eqs_iv[f"e{i}"] = {"dependent": pd.Series(yv, idx), "exog": pd.DataFrame(exog, idx),
                       "endog": pd.DataFrame(endog, idx), "instruments": pd.DataFrame(ins, idx)}
pick = lambda r: [float(r.params[n]) for n in names]  # noqa: E731
pse = lambda r: [float(r.std_errors[n]) for n in names]  # noqa: E731
sysref = {"lines": SYS_LINES, "coefs": coefs}
r = LM_SUR(eqs_sur).fit(cov_type="unadjusted", method="ols")
sysref["ols"] = {"params": pick(r), "bse": pse(r)}
r = LM_SUR(eqs_sur).fit(cov_type="unadjusted", method="gls")
sysref["sur"] = {"params": pick(r), "bse": pse(r)}
r = LM_SUR(eqs_sur).fit(cov_type="unadjusted", method="gls", iterate=True, iter_limit=1000, tol=1e-12)
sysref["sur_it"] = {"params": pick(r), "bse": pse(r)}
Rm = np.zeros((1, len(names)))
Rm[0, names.index("e0_c2")] = 1
Rm[0, names.index("e1_c5")] = -1
mod = LM_SUR(eqs_sur)
mod.add_constraints(pd.DataFrame(Rm, columns=names), pd.Series([0.0]))
r = mod.fit(cov_type="unadjusted", method="gls")
sysref["sur_restricted"] = {"restrict": "c(2) = c(5)", "params": pick(r), "bse": pse(r)}
for key, meth in (("tsls", "ols"), ("3sls", "gls")):
    r = IV3SLS(eqs_iv).fit(cov_type="unadjusted", method=meth)
    sysref[key] = {"params": pick(r), "bse": pse(r)}
out["system"] = sysref

# --- VAR·VECM — statsmodels.tsa ---------------------------------------------------------------------
from statsmodels.tsa.api import VAR as SM_VAR  # noqa: E402
from statsmodels.tsa.vector_ar.vecm import VECM as SM_VECM  # noqa: E402

VAR_SERIES = ["dlog(Y)", "dlog(CN)", "dlog(I)"]
Dv = wf._test_frame(VAR_SERIES).to_numpy()
var_ref = {"series": VAR_SERIES}
for tr in ("c", "ct"):
    r = SM_VAR(Dv).fit(2, trend=tr)
    d = {"params": r.params.tolist(), "bse": r.bse.tolist(), "sigma_u": r.sigma_u.tolist(),
         "ic": [float(r.aic), float(r.bic), float(r.hqic), float(r.fpe)],
         "irf_orth8": r.irf(8).orth_irfs.tolist(), "fevd8": r.fevd(8).decomp.tolist(),
         "forecast5": r.forecast(Dv[-2:], 5).tolist()}
    g = r.test_causality(0, [1, 2], kind="f")
    d["granger_0_12"] = [float(g.test_statistic), float(g.pvalue), [int(x) for x in g.df]]
    var_ref[tr] = d
so = SM_VAR(Dv).select_order(4, trend="c")
var_ref["select4"] = {"aic": [float(x) for x in so.ics["aic"]], "bic": [float(x) for x in so.ics["bic"]],
                      "selected": {k: int(v) for k, v in so.selected_orders.items()}}
out["var"] = var_ref
VECM_SERIES = ["RL", "R", "log(M2)"]     # 예제 자료의 공적분 관계(장기금리 = 1 + 정책금리 + u)
Lv = wf._test_frame(VECM_SERIES).to_numpy()
vecm_ref = {"series": VECM_SERIES}
for det in ("ci", "co", "n", "li", "lo", "cili", "colo"):
    m_ = SM_VECM(Lv, k_ar_diff=2, coint_rank=1, deterministic=det).fit()
    vecm_ref[det] = {"alpha": m_.alpha.tolist(), "beta": m_.beta.tolist(), "gamma": m_.gamma.tolist(),
                     "sigma_u": m_.sigma_u.tolist(), "forecast4": m_.predict(steps=4).tolist(),
                     "det_coef": np.asarray(m_.det_coef).tolist(),
                     "det_coef_coint": np.asarray(m_.det_coef_coint).tolist()}
out["vecm"] = vecm_ref

with open(os.path.join(ROOT, "tests", "fixtures", "estimation_reference.json"), "w", encoding="utf-8") as fh:
    json.dump(out, fh, ensure_ascii=False, indent=1)
print("ok", len(json.dumps(out)), "bytes")
