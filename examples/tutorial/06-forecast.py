# 이 파일은 docs/tutorial/06-forecast.md에서 만든다(python docs/build_docs.py) — 고치려면 문서를 고친다.
"""6. 전망 — 문서: docs/tutorial/06-forecast.md"""


# %% 6. 전망
import equion as eqn

wf = eqn.datasets.load("toy_q")
eq_i = wf.equation("eq_i").ls("I c Y(-1) R")
eq_cn = wf.equation("eq_cn").tsls("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
eq_p = wf.equation("eq_p").ls("dlog(P) c dlog(Y) dlog(POIL)")
m = wf.model("toy").merge(eq_i, eq_cn, eq_p).append("Y = CN + I + G")
print(m.exogenous)                    # 앞날 경로가 필요한 외생변수

# %% 6.1 외생 가정이 없으면
try:  # 이 예는 일부러 오류를 보인다
    m.forecast("2020Q1", "2021Q4")
except Exception as e:
    print(f"{type(e).__name__}: {e}")

# %% 6.2 외생 가정 세우기
r = m.forecast("2020Q1", "2021Q4", exog_fill="last")     # 기간을 늘리고 외생을 마지막 값으로 채워 푼다
print(r)
print(wf.to_pandas(["G", "R", "POIL"], labels=True).loc["2019Q4":"2020Q2"].round(2))
alt = m.scenario("plan")                                  # 다른 가정: 정부지출 연 4% 증가, 금리 인하
g0 = wf.elem("G", "2019Q4")
alt.override("G", {f"{y}Q{q}": g0 * 1.01 ** (4 * (y - 2020) + q) for y in (2020, 2021) for q in (1, 2, 3, 4)})
alt.override("R", {f"2020Q{q}": 2.5 for q in (1, 2, 3, 4)} | {f"2021Q{q}": 2.0 for q in (1, 2, 3, 4)})
m.forecast("2020Q1", "2021Q4", scenario="plan")
print(wf.to_pandas(["Y_0", "Y" + alt.alias], labels=True).loc["2020Q1":"2021Q4"].round(1))

# %% 6.3 출발점 맞추기
land = m.scenario("landed")
for eq in ("eq_i", "eq_cn", "eq_p"):
    land.init_add_factor(eq, "2019Q4")
m.forecast("2020Q1", "2021Q4", scenario="landed")
print(wf.to_pandas(["CN", "CN_0", "CN" + land.alias], labels=True).loc["2019Q4":"2020Q2"].round(2))

# %% 6.4 불확실성 띠
m.scenario("baseline")
sto = m.stochastic("2020Q1", "2021Q4", reps=300, seed=7)
b = sto.band("Y")
b.index = [f"{d.year}Q{(d.month - 1) // 3 + 1}" for d in b.index]
print(b.round(1))

# %% 6.5 예측력 평가 — 지난 기간으로
ev = eqn.datasets.load("toy_q")
ev.smpl("1970Q1", "2009Q4")                               # 추정 구간
for name, spec in (("i", "I c Y(-1) R"), ("p", "dlog(P) c dlog(Y) dlog(POIL)")):
    ev.equation("e_" + name).ls(spec)
ev.equation("e_cn").tsls("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
mv = ev.model("mv").merge("e_i", "e_cn", "e_p").append("Y = CN + I + G")
mv.solve("2010Q1", "2019Q4", mode="static")               # 한 분기 앞 예측(시차는 실측)
ev.smpl("2010Q1", "2019Q4")                               # 평가 구간 — genr도 표본 안만 쓰므로 먼저 바꾼다
ev.genr("Y_NAIVE = Y(-1)")
eqn.show(ev.forecast_eval("Y", "Y_0", "Y_NAIVE"))
ev.dm_test("Y", "Y_0", "Y_NAIVE")                          # 두 예측의 정확도가 같은가(Diebold-Mariano)

# %% 6.6 결과 내보내기
out = wf.to_pandas(["Y_0", "CN_0", "I_0", "P_0"], labels=True).loc["2020Q1":"2021Q4"]
out.to_excel("forecast.xlsx")                              # pandas 그대로
wf.write("forecast.csv", ["Y_0", "Y_1"])                    # 또는 워크파일에서
print(out.round(1).head(2))
