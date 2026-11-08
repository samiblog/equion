# 이 파일은 docs/howto/estimation.md에서 만든다(python docs/build_docs.py) — 고치려면 문서를 고친다.
"""레시피: 추정 — 문서: docs/howto/estimation.md"""


# %% 레시피: 추정
import numpy as np
import pandas as pd
import equion as eqn

wf = eqn.datasets.load("toy_q")

# %% R9. 후보 식 여러 개를 한 번에 비교
cands = {"기본": "I c Y(-1) R",
         "시차 2": "I c Y(-1 to -2) R",
         "금리 시차": "I c Y(-1) R R(-1)",
         "로그": "log(I) c log(Y(-1)) R"}
rows = {}
for label, spec in cands.items():
    e = wf.equation("cand_" + str(len(rows))).ls(spec + " @smpl 1971Q1 2019Q4")      # 같은 표본으로
    rows[label] = {"R²": e.stats["adj_r_squared"], "AIC": e.stats["aic"], "BIC": e.stats["bic"], "DW": e.stats["durbin_watson"]}
print(pd.DataFrame(rows).T.round(4))

# %% R10. 계수 표를 엑셀로
eq = wf.equation("eq_i").ls("I c Y(-1) R")
tab = pd.DataFrame({"계수": eq.coefs, "표준오차": eq.stderrs, "t값": eq.tstats, "p값": eq.pvalues})
tab.to_excel("eq_i.xlsx")
wf.table("t_eq_i", eq).save("eq_i_table.html")          # 결과표 그대로(html·csv·xlsx·txt)
print(tab.round(4).assign(p값=tab["p값"].map("{:.1e}".format)))

# %% R11. 표본을 굴리며 계수 안정성 보기
rows = []
for end in range(1990, 2020, 5):
    e = wf.equation("roll").ls(f"I c Y(-1) R @smpl {end - 19}Q1 {end}Q4")       # 20년 창
    rows.append({"끝": end, "Y(-1)": e.coefs["Y(-1)"], "R": e.coefs["R"]})
print(pd.DataFrame(rows).set_index("끝").round(3))

# %% R12. 더미 넣기
d1 = wf.equation("dum").ls("I c Y(-1) R @d(2008Q4) @step(2009Q1)")     # 한 시점 더미 · 그때부터 1
print(list(d1.coefs.index))
d2 = wf.equation("seas").ls("dlog(CNNSA) c dlog(Y) @seas")              # 계절 더미(상수항이 있어 하나 뺀다)
print(list(d2.coefs.index))

# %% R13. 다른 도구로 추정한 계수를 모델에 쓰기
d = wf.to_pandas(["I", "Y", "R"]).assign(Y1=lambda x: x.Y.shift(1)).dropna()
A = np.column_stack([np.ones(len(d)), d.Y1, d.R])
b, *_ = np.linalg.lstsq(A, d.I.to_numpy(), rcond=None)                   # 직접 최소제곱
fx = wf.equation("i_ext").fixed("I c Y(-1) R", b.tolist())
print(fx.method, fx.coefs.round(4).to_dict())
m = wf.model("m_ext").merge(fx, "CN c Y CN(-1)").append("Y = CN + I + G")
print(m.solve("2015Q1", "2015Q4").counts())

# %% R14. 장기 효과(시차 합) 계산
e = wf.equation("lr").ls("CN c Y CN(-1)")
b, c = e.coefs["Y"], e.coefs["CN(-1)"]
print("단기", round(b, 3), "장기", round(b / (1 - c), 3))
e.wald("c(2) + c(3) = 1")                                # 장기 효과 = 1(장기 소비성향 1)인가

# %% R15. 강건 표준오차로 다시 보기
e = wf.equation("rob").ls("dlog(P) c dlog(Y) dlog(POIL)")
t0 = e.tstats.round(2).to_dict()
e.set_cov("hac", lags=4)
print(t0)
print(e.tstats.round(2).to_dict())
