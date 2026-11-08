# 이 파일은 docs/start/first-model.md에서 만든다(python docs/build_docs.py) — 고치려면 문서를 고친다.
"""30분 첫 모델 — 문서: docs/start/first-model.md"""


# %% 1. 예제 자료 열기
import equion as eqn

wf = eqn.datasets.load("toy_q")          # 워크파일: 시리즈·표본·객체를 담는 작업 단위
print(wf)
eqn.show(wf.metadata())
print(eqn.datasets.describe("toy_q"))

# %% 2. 방정식 추정
eq_i = wf.equation("eq_i").ls("I c Y(-1) R")      # 최소제곱(OLS)
eqn.show(eq_i)
print(eq_i.coefs.round(3).to_dict())
print(round(eq_i.stats["r_squared"], 4))
ols = wf.equation("eq_cn_ols").ls("CN c Y CN(-1)")
eq_cn = wf.equation("eq_cn").tsls("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
print("OLS ", ols.coefs.round(3).to_dict())
print("TSLS", eq_cn.coefs.round(3).to_dict())
eq_p = wf.equation("eq_p").ls("dlog(P) c dlog(Y) dlog(POIL)")
print(eq_p.coefs.round(4).to_dict())

# %% 3. 연립 모델 만들기
m = wf.model("toy").merge(eq_i, eq_cn, eq_p).append("Y = CN + I + G")
print(m.endogenous, m.exogenous)
eqn.show(m.blocks())                      # 함께 풀어야 하는 변수 묶음(동시 블록)과 풀이 순서

# %% 4. 과거 재현(Historical Simulation)
wf.smpl("1975Q1", "2019Q4")              # 풀이·추정·그래프의 기본 구간(표본)
base = m.solve()
eqn.show(base.summary())
print(wf.to_pandas(["Y", "Y_0"], labels=True).loc["2019Q1":"2019Q4"].round(1))

# %% 5. 시나리오
sc = m.scenario("g_up")
sc.shock("G", 10, "2015Q1", "2019Q4", kind="pct")    # G를 10% 높인다
m.solve("2015Q1", "2019Q4")
cmp = wf.to_pandas(["Y_0", "Y_1"], labels=True).loc["2015Q1":"2015Q4"]
cmp["차이(%)"] = (cmp["Y_1"] / cmp["Y_0"] - 1) * 100
print(cmp.round(2))

# %% 6. 전망
m.scenario("baseline")                    # 기준선 시나리오로 돌아간다
fc = m.forecast("2020Q1", "2021Q4", exog_fill="trend")
print(wf.to_pandas(["Y_0", "CN_0", "I_0"], labels=True).loc["2020Q1":"2021Q4"].round(1))

# %% 7. 그래프와 저장
g = wf.graph("g_y", "Y Y_0 Y_1", start="2010Q1", end="2021Q4", title="국민소득: 실측·기준선·시나리오")
g.save("y.html")                          # 인터넷 없이 열리는 html(plotly 없이도 됨)
wf.save("toy")                            # toy.eqw/ — 자료·방정식 계수·모델·시나리오를 모두 저장
wf2 = eqn.wfopen("toy.eqw")               # 다시 열면 재추정 없이 그대로
print(wf2.obj("eq_i").coefs.round(3).to_dict())
