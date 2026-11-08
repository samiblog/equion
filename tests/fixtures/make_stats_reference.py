"""tests/fixtures/stats_reference.json 생성 — statsmodels(기준 구현)로 한 번 계산해 고정한다.

개발용 스크립트다. Equion은 statsmodels에 의존하지 않으므로(DECISIONS D17), statsmodels를 설치한 **별도 환경**에서만
돌린다:  PYTHONPATH=<저장소> <statsmodels가 있는 python> tests/fixtures/make_stats_reference.py
"""
import sys, os, json, warnings
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT); os.chdir(ROOT)
warnings.simplefilter("ignore")
import numpy as np, statsmodels, statsmodels.api as sm
from statsmodels.stats import diagnostic as smd
from statsmodels.stats.stattools import jarque_bera
from statsmodels.tsa.stattools import adfuller, kpss, coint
from statsmodels.tsa.vector_ar.vecm import coint_johansen
import equion as eqn
eqn.verbose(0)
L = lambda a: [float(v) for v in np.atleast_1d(np.asarray(a, dtype=float))]
wf = eqn.datasets.load("toy_q"); wf.smpl("@all")
out = {"_provenance": f"statsmodels {statsmodels.__version__} · numpy {np.__version__} 로 계산(tests/fixtures/make_stats_reference.py). "
                      "Equion 자체 구현이 같은 값을 내는지 tests/test_stats.py가 확인한다.",
       "equations": {}, "series": {}}
for key, spec in (("cp", "log(CN) c log(Y) log(CN(-1))"), ("fi", "log(I) c log(Y) log(I(-1)) @seas")):
    e = wf.equation("e_" + key).ls(spec).eq
    y, X = e._y, e._X
    r = sm.OLS(y, X).fit()
    d = {"spec": spec, "params": L(r.params), "bse": L(r.bse), "fvalue": float(r.fvalue), "llf": float(r.llf)}
    for ct in ("HC0", "HC1", "HC2", "HC3"):
        d["bse_" + ct.lower()] = L(r.get_robustcov_results(ct, use_t=True).bse)
    d["bse_hac4"] = L(r.get_robustcov_results("HAC", maxlags=4, use_correction=True, use_t=True).bse)
    d["pvalues_hac4"] = L(r.get_robustcov_results("HAC", maxlags=4, use_correction=True, use_t=True).pvalues)
    ev, Xv = r.resid.to_numpy(), X.to_numpy()
    d["bg"] = {str(p): L(smd.acorr_breusch_godfrey(r, nlags=p)) for p in (1, 2, 4)}
    d["white"] = L(smd.het_white(ev, Xv)); d["bp"] = L(smd.het_breuschpagan(ev, Xv))
    d["bp_original"] = float(smd.het_breuschpagan(ev, Xv, robust=False)[0])
    d["arch"] = {str(p): L(smd.het_arch(ev, nlags=p)) for p in (1, 4)}
    jb = jarque_bera(ev); d["jb"] = [float(jb[0]), float(jb[1]), float(jb[2]), float(jb[3])]
    lb = smd.acorr_ljungbox(ev, lags=8); d["lb_q"] = L(lb["lb_stat"]); d["lb_p"] = L(lb["lb_pvalue"])
    d["reset_f"] = {str(t): float(smd.linear_reset(r, power=t + 1, use_f=True).fvalue) for t in (1, 2)}
    k = Xv.shape[1]; Rm = np.zeros((2, k)); Rm[0, 1] = Rm[0, 2] = 1; Rm[1, 0] = 1
    ft = r.f_test((Rm, np.array([1.0, 0.0]))); d["wald"] = [float(ft.fvalue), float(ft.pvalue)]
    split = int(np.searchsorted(y.index.values, np.datetime64("2008-01-01")))
    a, b = sm.OLS(y.iloc[:split], X.iloc[:split]).fit(), sm.OLS(y.iloc[split:], X.iloc[split:]).fit()
    n = len(y); su = a.ssr + b.ssr
    d["chow_2008Q1"] = float(((r.ssr - su) / k) / (su / (n - 2 * k)))
    # 재귀 잔차·CUSUM 값은 기준값으로 쓰지 않는다: statsmodels의 갱신 공식은 조건수가 큰 자료에서 반올림이 쌓여
    # (이 자료의 소비식에서 마지막 재귀 잔차가 상대 3e-4 어긋남) — 테스트는 시점별 직접 최소제곱과 비교한다.
    rr = smd.recursive_olsresiduals(r)
    d["cusum_bound_last"] = float(rr[6][1][-1])
    out["equations"][key] = d
x = np.log(wf["Y"]).dropna().to_numpy(); c = np.log(wf["CN"]).dropna().to_numpy(); fi = np.log(wf["I"]).dropna().to_numpy()
n = min(len(x), len(c), len(fi)); x, c, fi = x[:n], c[:n], fi[:n]
s = {}
for tr in ("n", "c", "ct"):
    for ic in ("bic", "aic"):
        a = adfuller(x, regression=tr, autolag=ic.upper()); s[f"adf_{tr}_{ic}"] = [float(a[0]), float(a[1]), int(a[2]), L([a[4]["1%"], a[4]["5%"], a[4]["10%"]])]
    a = adfuller(np.diff(x), maxlag=2, regression=tr, autolag=None); s[f"adf_diff_{tr}_lag2"] = [float(a[0]), float(a[1])]
for tr in ("c", "ct"):
    for lg in ("auto", 4):
        k_ = kpss(np.diff(x), regression=tr, nlags=lg); s[f"kpss_{tr}_{lg}"] = [float(k_[0]), float(k_[1]), int(k_[2])]
for tr in ("c", "ct"):
    e_ = coint(c, x, trend=tr, autolag="bic"); s[f"eg_{tr}"] = [float(e_[0]), float(e_[1]), L(e_[2])]
for det in (0, 1):
    j = coint_johansen(np.column_stack([c, x, fi]), det, 2); s[f"johansen_{det}_2"] = {"eig": L(j.eig), "trace": L(j.lr1), "maxeig": L(j.lr2)}
s["n"] = n
out["series"] = s
json.dump(out, open(os.path.join(ROOT, "tests", "fixtures", "stats_reference.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("ok", len(json.dumps(out)), "bytes")
