# 이 파일은 docs/tutorial/02-estimation.md에서 만든다(python docs/build_docs.py) — 고치려면 문서를 고친다.
"""2. 방정식 추정 — 문서: docs/tutorial/02-estimation.md"""


# %% 2. 방정식 추정
import numpy as np
import equion as eqn

wf = eqn.datasets.load("toy_q")

# %% 2.1 방정식 문법 한눈에
e1 = wf.equation("e1").ls("log(CN) c log(Y) log(CN(-1))")
print(e1.coefs.round(4).to_dict())
e2 = wf.equation("e2").ls("dlog(CNNSA) c dlog(Y) @seas")          # 계절조정 전 소비 + 계절 더미
print(list(e2.coefs.index))
e3 = wf.equation("e3").ls("I c Y(-1 to -2) R @smpl 1990Q1 2019Q4")
print(e3.nobs, list(e3.coefs.index))

# %% 2.2 결과표 읽기
eq = wf.equation("eq_i").ls("I c Y(-1) R")
eqn.show(eq)

# %% 2.3 결과 꺼내기
print(eq.coefs.round(4).to_dict())               # 계수(Series)
print(eq.stderrs.round(4).to_dict())             # 표준오차
print(eq.pvalues.map("{:.2e}".format).to_dict())  # p값  (t값은 eq.tstats)
print(eq.nobs, eq.method, eq.dependent)
print(sorted(eq.stats)[:8])                      # 통계 사전의 키
print(round(eq.stats["se_regression"], 4), round(eq.stats["durbin_watson"], 3))
fit = eq.fitted                                  # 적합값(표본 기간)
res = eq.resid                                   # 잔차 = 실측 − 적합값
print(round(float((eq.actual - fit - res).abs().max()), 12))
print(res.describe().round(3).to_dict())

# %% 2.4 표본
wf.smpl("1990Q1", "2019Q4")
a = wf.equation("eq_i90").ls("I c Y(-1) R")
wf.smpl("@all")
b = wf.equation("eq_i70").ls("I c Y(-1) R @smpl 1970Q1 1989Q4")
print(a.nobs, a.coefs.round(3).to_dict())
print(b.nobs, b.coefs.round(3).to_dict())

# %% 2.5 강건 표준오차
w = wf.equation("eq_w").ls("I c Y(-1) R", cov="white")         # 이분산 강건(HC1)
h = wf.equation("eq_h").ls("I c Y(-1) R", cov="hac", lags=4)   # 이분산·자기상관 강건(Newey-West)
print(eq.stderrs.round(4).tolist())
print(w.stderrs.round(4).tolist())
print(h.stderrs.round(4).tolist())
h.set_cov(None)                                                 # 다시 보통 표준오차로(재추정 없이)
print(h.stderrs.round(4).tolist())

# %% 2.6 내생 설명변수 — 2단계 최소제곱·GMM·LIML
ols = wf.equation("cn_ols").ls("CN c Y CN(-1)")
iv = wf.equation("cn_tsls").tsls("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
iv2 = wf.equation("cn_tsls2").tsls("CN c Y CN(-1)", inst=["G", "R", "CN(-1)", "Y(-1)"])   # 같은 것
print("참값   {'const': 10, 'Y': 0.5, 'CN(-1)': 0.3}")
print("OLS  ", ols.coefs.round(3).to_dict())
print("TSLS ", iv.coefs.round(3).to_dict(), bool(np.allclose(iv.coefs, iv2.coefs)))
gm = wf.equation("cn_gmm").gmm("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
li = wf.equation("cn_liml").liml("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
print("GMM  ", gm.coefs.round(3).to_dict(), "J p값", round(gm.stats["j_pvalue"], 3))
print("LIML ", li.coefs.round(3).to_dict(), "κ", round(li.stats["liml_kappa"], 4))

# %% 2.7 비선형 식
nl = wf.equation("cn_nls").ls("CN = c(1) + c(2)*Y^c(3) @start 10 0.5 1")
print(nl.coefs.round(4).to_dict(), nl.method)

# %% 2.8 AR 오차
ar = wf.equation("p_ar").ls("dlog(P) c dlog(Y) ar(1)")
print(ar.coefs.round(4).to_dict())

# %% 2.9 다항 분포시차(PDL)
pdl = wf.equation("i_pdl").ls("I c pdl(Y, 4, 2) R")
eqn.show(pdl.lag_distribution())

# %% 2.10 가중 최소제곱
wf.genr("WT = 1 / Y")                     # 규모가 클수록 분산이 크다고 가정
wl = wf.equation("i_wls").wls("I c Y(-1) R", weights="WT")
print(wl.coefs.round(4).to_dict())

# %% 2.11 다른 곳에서 얻은 계수 넣기
fx = wf.equation("i_fixed").fixed("I c Y(-1) R", [5.0, 0.15, -1.0])     # 참값
print(fx.coefs.to_dict(), fx.method, round(fx.stats["r_squared"], 4))

# %% 2.12 식 하나로 예측하기
f = eq.forecast(start="2015Q1", end="2019Q4")          # 동적: 종속변수의 시차에 예측값
print(f.name, round(float((f.dropna() - wf["I"].loc[f.dropna().index]).abs().mean()), 3))

# %% 2.13 흔한 문제
wf.genr("Y2 = 2 * Y")
bad = wf.equation("bad").ls("CN c Y Y2")
print(bad.stats["collinear"])
try:  # 이 예는 일부러 오류를 보인다
    wf.equation("typo").ls("CN c log(Y CN(-1)")
except Exception as e:
    print(f"{type(e).__name__}: {e}")
