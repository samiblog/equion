# 이 파일은 docs/tutorial/05-scenario.md에서 만든다(python docs/build_docs.py) — 고치려면 문서를 고친다.
"""5. 시나리오 — 문서: docs/tutorial/05-scenario.md"""


# %% 5. 시나리오
import equion as eqn

wf = eqn.datasets.load("toy_q")
eq_i = wf.equation("eq_i").ls("I c Y(-1) R")
eq_cn = wf.equation("eq_cn").tsls("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
eq_p = wf.equation("eq_p").ls("dlog(P) c dlog(Y) dlog(POIL)")
m = wf.model("toy").merge(eq_i, eq_cn, eq_p).append("Y = CN + I + G")
wf.smpl("2010Q1", "2019Q4")
base = m.solve()                      # 기준선 → Y_0, CN_0 …

# %% 5.1 시나리오와 별칭
hi = m.scenario("hi_g")               # 새 시나리오 → 별칭 _1, 활성화
print(hi, hi.alias)
print(list(m.scenarios))

# %% 5.2 외생 경로 바꾸기 — override
hi.override("G", wf["G"] * 1.10)      # 정부지출 10% 높게(전 기간)
m.solve()
d = wf.to_pandas(["Y_0", "Y_1"], labels=True).loc["2010Q1":"2010Q4"]
print((d["Y_1"] / d["Y_0"] - 1).mul(100).round(2).to_dict())
low_r = m.scenario("low_r")           # 별칭 _2
low_r.override("R", {"2012Q1": 0.5, "2012Q2": 0.5})     # 두 분기만 금리를 0.5%로
m.solve()
print(wf.to_pandas(["I_0", "I_2"], labels=True).loc["2012Q1":"2012Q4"].round(2))

# %% 5.3 충격 — shock
sh = m.scenario("shock")
sh.shock("G", 5, "2015Q1")                        # 2015Q1 한 분기 G +5
sh.shock("CN", -3, "2016Q1", "2016Q4")            # 소비식에 −3(소비 심리 위축)
m.solve()
print(wf.to_pandas(["Y_0", "Y" + sh.alias], labels=True).loc["2015Q1":"2015Q3"].round(2))

# %% 5.4 내생변수 고정 — exclude
ex = m.scenario("i_fixed")
ex.exclude("I", "2013Q1", "2014Q4")              # 이 구간만 실측
ex.override("I", wf["I"] * 0.95)                  # 고정할 경로를 바꿀 수도 있다(실측의 95%)
m.solve()
print(wf.to_pandas(["I", "I" + ex.alias], labels=True).loc["2013Q1":"2013Q2"].round(2))

# %% 5.5 조정항 — add_factor
af = m.scenario("af")
af.add_factor("eq_p", 0.002)                      # 물가 상승률을 분기 0.2%p 높게(전 기간)
m.solve()
print(wf.to_pandas(["P_0", "P" + af.alias], labels=True).loc["2019Q4":"2019Q4"].round(2))

# %% 5.6 목표 경로 맞추기 — control
target = wf["Y_0"] * 1.02                         # 기준선보다 2% 높게(경로는 start~end 구간에만 쓰인다)
g_needed = m.control("Y", "G", target, "2018Q1", "2019Q4")
print(wf.to_pandas(["G", "G_C"], labels=True).loc["2018Q1":"2018Q4"].round(2))

# %% 5.7 결과 비교와 기여도 분해
mix = m.scenario("mix")
mix.override("G", wf["G"] * 1.05).shock("R", -1, "2014Q1", "2019Q4").add_factor("eq_cn", -2)
m.solve()
print(m.compare("Y").loc["2019-10-01"].round(1).to_dict())
dec = m.decompose("Y", "mix", start="2015Q1", end="2015Q4")
eqn.show(dec)

# %% 5.8 충격 승수
mu = m.multipliers("G", 1.0, "2015Q1", "2016Q4")            # G를 지속적으로 +1
print(mu.level[["Y", "CN", "I"]].iloc[[0, 1, 3, 7]].round(3))
mu1 = m.multipliers("G", 1.0, "2015Q1", "2016Q4", permanent=False)   # 한 분기만 +1
print(mu1.level["Y"].iloc[[0, 1, 3, 7]].round(3).tolist())

# %% 5.9 확률적 모의
m.scenario("baseline")
sto = m.stochastic("2018Q1", "2019Q4", reps=200, seed=1)
print(sto.band("Y").round(1).head(4))
