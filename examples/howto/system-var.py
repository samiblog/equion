# 이 파일은 docs/howto/system-var.md에서 만든다(python docs/build_docs.py) — 고치려면 문서를 고친다.
"""레시피: 시스템·VAR — 문서: docs/howto/system-var.md"""


# %% 레시피: 시스템·VAR
import pandas as pd
import equion as eqn

wf = eqn.datasets.load("toy_q")
v = wf.var("v1", ["dlog(Y)", "R"], lags=2)

# %% R36. 충격반응 그림 저장
v.irf_graph("R", periods=12).save("irf_r.html")          # R 충격에 대한 모든 변수의 반응
irf = v.irf(12)
irf.to_csv("irf.csv")                                     # 수치는 DataFrame(열 = (반응, 충격))
print(irf.columns.tolist()[:2])

# %% R37. Granger 인과 표
eqn.show(v.granger_table())

# %% R38. 공적분 순위 고르기와 VECM
wf.smpl("1980Q1", "2019Q4")
j = wf.johansen("RL R", det=0, lags=1)
rank = j.rows["트레이스 기준 순위(5%)"]
k = wf.vecm("vecm1", ["RL", "R"], lags_diff=1, rank=rank)
print(rank, k.beta.round(3).iloc[:, 0].to_dict())

# %% R39. 시스템 추정 결과를 모델로
kw = eqn.datasets.load("klein_like")
s = kw.system("kl")
s.append("CONS c PR PR(-1) WP+WG", "I c PR PR(-1) K(-1)", "WP c X X(-1) A", "@inst G T WG A PR(-1) K(-1) X(-1)")
s.three_sls()
km = kw.model("km").merge(s).append("X = CONS + I + G", "PR = X - T - WP", "K = K(-1) + I")
mu = km.multipliers("G", 1.0, "1960", "1965")
print(mu.level["X"].round(3).tolist())
