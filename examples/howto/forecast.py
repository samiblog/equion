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

# %% R51. 전망 기록 — 가정 세트·보정항·시나리오
p = eqn.Project.create("fc_prj", force=True)   # 예제 프로젝트 — 가정 base · 보정항 base · 시나리오 oil20
b = p.sim(as_name="base_1")                    # 기준선 — [forecast] range = next:8
print(b.text())
print(b.flags.loc["2019Q4":"2020Q2", ["Y", "G", "POIL", "R"]])
o = p.sim("oil20", as_name="oil_1", vs="sim:base_1")
print(o.text())

# %% R61. 시나리오를 명령으로 쓰기 — 충격 표
p = eqn.Project.create("sc_prj", force=True)
r = p.scenario_define("oil_rate", desc="유가와 금리 동반 상승", shocks=["POIL=+20%", "R=+0.5@start:start+3"],
                      addfactor=["demand:CN=-0.2@start:start+1"])
print(r.text())
with open(f"{p.root}/SCENARIOS/oil_rate.toml", encoding="utf-8") as f:
    print(f.read())
print(p.sim("oil_rate").text())

# %% R63. 회차 비교의 요인 나누기 — 자료 · 가정 · 식의 몫
p = eqn.Project.create("split_prj", force=True)
p.sim(as_name="oct")                                         # 지난달 기준선
raw = pd.read_csv("split_prj/DATA/raw/toy_q.csv", index_col=0)    # 자료 개정(가상): 마지막 두 기의 소비 +1%
raw.loc[raw.index[-2:], "CN"] *= 1.01
raw.to_csv("split_prj/DATA/raw/toy_q.csv")
p.data_build(use=True)
a = pd.read_csv("split_prj/ASSUMPTIONS/base.csv", index_col=0)     # 가정: 유가 경로 +10%
a["POIL"] *= 1.1
a.to_csv("split_prj/ASSUMPTIONS/base.csv")
p.adopt(p.est("CN c Y", part="demand:CN").id)                 # 식: 소비함수를 바꿔 채택
p.sim(as_name="nov")
print(p.an("split", "sim:oct sim:nov", vars="Y,CN").text())
