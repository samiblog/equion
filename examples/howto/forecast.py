# 이 파일은 docs/howto/forecast.md에서 만든다(python docs/build_docs.py) — 고치려면 문서를 고친다.
"""레시피: 전망 — 문서: docs/howto/forecast.md"""


# %% 레시피: 전망
import pandas as pd
import equion as eqn

wf = eqn.datasets.load("toy_q")
eq_i = wf.equation("eq_i").ls("I c Y(-1) R")
eq_cn = wf.equation("eq_cn").tsls("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
eq_p = wf.equation("eq_p").ls("dlog(P) c dlog(Y) dlog(POIL)")
m = wf.model("toy").merge(eq_i, eq_cn, eq_p).append("Y = CN + I + G")

# %% R32. 외생 가정을 표(엑셀·CSV)로 받아 전망
assume = pd.DataFrame({"period": [f"{y}Q{q}" for y in (2020, 2021) for q in (1, 2, 3, 4)],
                       "G": [70 + 0.5 * k for k in range(8)], "R": [3.0] * 4 + [2.5] * 4, "POIL": [62.0] * 8})
assume.to_csv("assumptions.csv", index=False)
a = pd.read_csv("assumptions.csv").set_index("period")
sc = m.scenario("plan")
for v in a.columns:
    sc.override(v, a[v].to_dict())                     # {기간 라벨: 값}
r = m.forecast("2020Q1", "2021Q4", scenario="plan")
print(r.counts(), round(wf.elem("Y" + sc.alias, "2021Q4"), 1))

# %% R33. 전망을 연간으로 모으기
ya = wf.convert("Y" + sc.alias, "A", method="sum")
print({d.year: round(v, 1) for d, v in ya.dropna().items() if d.year >= 2020})
print(round((ya.iloc[-1] / ya.iloc[-2] - 1) * 100, 2), "% (2021년 성장률)")

# %% R34. 앞 전망에 이어 더 멀리
m.scenario("baseline")
m.forecast("2020Q1", "2021Q4", exog_fill="last")
for v in m.endogenous:                                  # 앞 전망(_0)을 실측 자리에
    wf[v] = wf[v].fillna(wf[v + "_0"])
r2 = m.forecast("2022Q1", "2022Q4", exog_fill="last")
print(r2.counts())

# %% R35. 굴리는 예측 평가
eqn.verbose(0)
ev = eqn.datasets.load("toy_q")
e_i, e_cn = ev.equation("e_i"), ev.equation("e_cn")
mv = ev.model("mv").merge(e_i.ls("I c Y(-1) R"), e_cn.ls("CN c Y CN(-1)")).append("Y = CN + I + G")
rows = {}
for end in range(2010, 2019):
    ev.smpl("1970Q1", f"{end}Q4")
    e_i.ls("I c Y(-1) R")                                  # 다시 추정하면 모델은 다음 풀이 때 새 계수를 쓴다
    e_cn.tsls("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
    r = mv.solve(f"{end + 1}Q1", f"{end + 1}Q4")
    err = (r.values["Y"] / ev["Y"].loc[r.values.index] - 1) * 100
    rows[end + 1] = round(float(err.abs().mean()), 3)
eqn.verbose(1)
print(rows)
