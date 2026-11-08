# 이 파일은 docs/howto/scenario.md에서 만든다(python docs/build_docs.py) — 고치려면 문서를 고친다.
"""레시피: 시나리오 — 문서: docs/howto/scenario.md"""


# %% 레시피: 시나리오
import pandas as pd
import equion as eqn

wf = eqn.datasets.load("toy_q")
eq_i = wf.equation("eq_i").ls("I c Y(-1) R")
eq_cn = wf.equation("eq_cn").tsls("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
eq_p = wf.equation("eq_p").ls("dlog(P) c dlog(Y) dlog(POIL)")
m = wf.model("toy").merge(eq_i, eq_cn, eq_p).append("Y = CN + I + G")
wf.smpl("2015Q1", "2019Q4")
m.solve()

# %% R26. 시나리오 여러 개를 돌려 한 표로
eqn.verbose(0)
rows = {}
for g in (0, 5, 10, 20):
    sc = m.scenario(f"g{g}")
    sc.clear().shock("G", g, "2015Q1", "2019Q4", kind="pct")
    m.solve()
    rows[f"G +{g}%"] = (wf["Y" + sc.alias] / wf["Y_0"] - 1).mul(100).loc["2019-10-01"]
eqn.verbose(1)
print(pd.Series(rows).round(2))

# %% R27. 유가 충격
oil = m.scenario("oil")
oil.shock("POIL", 50, "2016Q1", "2019Q4", kind="pct")           # 유가 50% 상승이 이어짐
m.solve()
d = wf.to_pandas(["P_0", "P" + oil.alias], labels=True)
print(((d["P" + oil.alias] / d["P_0"] - 1) * 100).loc["2016Q1":"2016Q4"].round(3).tolist())

# %% R28. 목표 경로 맞추기 — 물가 수준 목표
r_path = m.control("P", "R", wf["P_0"] * 0.99, "2018Q1", "2018Q4")
print(wf.to_pandas(["R", "R_C"], labels=True).loc["2018Q1":"2018Q4"].round(2))
try:  # 이 예는 일부러 오류를 보인다
    m.control("I", "G", wf["I_0"] * 1.01, "2018Q1", "2018Q4")
except Exception as e:
    print(f"{type(e).__name__}: {e}")

# %% R29. 모든 시나리오의 차이(%)를 한 번에
cmp = m.compare("Y")                                            # 실측 · Y_0 · Y_1 …
pct = cmp.drop(columns=["Y", "Y_0"]).div(cmp["Y_0"], axis=0).sub(1).mul(100)
print(pct.loc["2019-10-01"].round(2).to_dict())

# %% R30. 기여도 분해를 그림으로 저장
mix = m.scenario("mix")
mix.shock("G", 5, "2015Q1", "2019Q4", kind="pct").shock("POIL", 30, "2015Q1", "2019Q4", kind="pct")
mix.add_factor("eq_cn", -2)
m.solve()
dec = m.decompose(["Y", "P"], "mix")
dec.graph("Y").save("decomp_y.html")
print(dec.drivers, dec.table("P").round(3).iloc[-1].to_dict())

# %% R31. 시나리오를 저장하고 다시 쓰기
wf.save("toy_scen")
w2 = eqn.wfopen("toy_scen.eqw")
m2 = w2.obj("toy")
print(list(m2.scenarios))
r = m2.solve(scenario="mix")
print(r.counts()["ok"], round(w2.elem("Y" + m2.scenario("mix").alias, "2019Q4"), 1))
