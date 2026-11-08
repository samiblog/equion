# 이 파일은 docs/tutorial/07-systems.md에서 만든다(python docs/build_docs.py) — 고치려면 문서를 고친다.
"""7. 시스템·VAR·VECM — 문서: docs/tutorial/07-systems.md"""


# %% 7.1 시스템 추정
import equion as eqn

kw = eqn.datasets.load("klein_like")
print(eqn.datasets.describe("klein_like").splitlines()[3:7])
kl = kw.system("klein")
kl.append("CONS c PR PR(-1) WP+WG",
          "I c PR PR(-1) K(-1)",
          "WP c X X(-1) A",
          "@inst G T WG A PR(-1) K(-1) X(-1)")
truth = [16.4, 0.125, 0.163, 0.79, 28.2, -0.013, 0.756, -0.195, 1.8, 0.4, 0.181, 0.15]
import pandas as pd
table = {"참값": truth}
for method in ("ols", "tsls", "three_sls"):
    getattr(kl, method)()
    table[method] = kl.coefs.round(3).tolist()
print(pd.DataFrame(table, index=kl.coefs.index))
kl.fiml()
print(kl.coefs.round(3)[["c(2)", "c(6)"]].to_dict())     # OLS 쪽으로 치우친다
kl.three_sls()
eqn.show(kl.equation_stats())
print(kl.sigma.round(3))                     # 식 사이 잔차 공분산

# %% 7.2 식 사이 제약
kl.three_sls()
kl.wald("c(3) = c(7)")                       # 소비·투자의 지난 이윤 계수가 같은가(참값 0.163·0.756 — 기각)
kl.three_sls(restrict=["c(3) = c(7)"])
print(kl.coefs.round(3)[["c(3)", "c(7)"]].to_dict())

# %% 7.3 시스템을 모델에 넣기
kl.three_sls()
km = kw.model("klein_model").merge(kl)
km.append("X = CONS + I + G", "PR = X - T - WP", "K = K(-1) + I")
r = km.solve("1925", "1990")
eqn.show(r.summary())
print(km.stability("1960"))

# %% 7.4 VAR
wf = eqn.datasets.load("toy_q")
eqn.show(wf.var("v_sel", ["dlog(Y)", "R"], lags=1).lag_order(6))     # 시차 고르기(같은 표본에서 정보기준)
v = wf.var("v1", ["dlog(Y)", "R"], lags=2)
eqn.show(v)
v.granger("dlog(Y)", "R")                    # R의 시차가 dlog(Y)를 설명하는가
irf = v.irf(8)                               # 촐레스키(변수 순서대로) 1 표준편차 충격
print(irf.xs("R", axis=1, level="충격").iloc[:4].round(5))
fe = v.fevd(8)
print(fe["dlog(Y)"].iloc[[0, 3, 7]].round(3))
print(v.forecast(4).round(4))
print(v.stability())

# %% 7.5 VECM
wf.smpl("1980Q1", "2019Q4")                  # RL이 있는 구간
k = wf.vecm("vecm_rl", ["RL", "R"], lags_diff=1, rank=1)
print(k.beta.round(3))                       # 공적분 벡터(첫 변수로 정규화): RL − 1.0·R
print(k.alpha.round(3))                      # 조정 속도
print(k.forecast(4).round(3))

# %% 7.6 VAR·VECM을 모델에 넣기
mv = wf.model("m_vecm").merge(k)
print(mv.endogenous)
r = mv.solve("2015Q1", "2019Q4", mode="static")
print(r.counts())
