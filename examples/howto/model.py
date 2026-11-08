# 이 파일은 docs/howto/model.md에서 만든다(python docs/build_docs.py) — 고치려면 문서를 고친다.
"""레시피: 모델 — 문서: docs/howto/model.md"""


# %% 레시피: 모델
import pandas as pd
import equion as eqn

wf = eqn.datasets.load("toy_q")
eq_i = wf.equation("eq_i").ls("I c Y(-1) R")
eq_cn = wf.equation("eq_cn").tsls("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
eq_p = wf.equation("eq_p").ls("dlog(P) c dlog(Y) dlog(POIL)")
m = wf.model("toy").merge(eq_i, eq_cn, eq_p).append("Y = CN + I + G")

# %% R20. 방정식 파일로 모델 관리하기
with open("model.txt", "w", encoding="utf-8") as f:
    f.write("""# 작은 거시 모형
I c Y(-1) R
CN c Y CN(-1) @inst G R CN(-1) Y(-1)
dlog(P) c dlog(Y) dlog(POIL)
Y = CN + I + G
""")
mf = wf.model("from_file").merge("model.txt")
print(mf.endogenous, [o.eq.method for o in mf.equations])

# %% R21. 모델 일부만 풀기
part = wf.model("no_price").merge(eq_i, eq_cn).append("Y = CN + I + G")     # 물가식 빼고 새로
print(part.endogenous)
fix = m.scenario("i_actual").exclude("I")                                   # 같은 모델에서 I만 실측으로
print(m.solve("2015Q1", "2015Q4").counts())
m.scenario("baseline")

# %% R22. 수렴하지 않을 때
r = m.solve("2010Q1", "2010Q4", method="newton", fallback=("hybr", "lm", "gauss-seidel"),
            tolerance=1e-10, max_iterations=100)
print(r.counts(), r.status()["iterations"].tolist())
print(m.stability("2010Q1").verdict)

# %% R23. 과거 재현 결과를 엑셀로
wf.smpl("1975Q1", "2019Q4")
r = m.solve()
r.save("hs/hs_toy.csv")                                         # 상태 열 + 변수별 풀이·실측·오차(%)
cmp = wf.to_pandas(["Y", "Y_0", "CN", "CN_0"], smpl=True, labels=True)
with pd.ExcelWriter("hs_toy.xlsx") as xw:
    cmp.to_excel(xw, sheet_name="경로")
    r.statistics().to_excel(xw, sheet_name="적합도")
print(sorted(r.statistics().columns)[:4])

# %% R24. 출발 시점별 과거 재현 비교
rows = {}
for start in ("1980Q1", "1990Q1", "2000Q1", "2010Q1"):
    st = m.solve(start, "2019Q4").statistics()
    rows[start] = st["RMSPE"]
print(pd.DataFrame(rows).round(3))

# %% R25. 식 하나를 바꿨을 때 모델 성능 비교
base = m.solve("1990Q1", "2019Q4").statistics()["RMSPE"]
alt_cn = wf.equation("eq_cn_alt").ls("CN c Y CN(-1)")                       # TSLS 대신 OLS
m_alt = wf.model("toy_alt").merge(eq_i, alt_cn, eq_p).append("Y = CN + I + G")
alt = m_alt.solve("1990Q1", "2019Q4").statistics()["RMSPE"]
print(pd.DataFrame({"TSLS 소비식": base, "OLS 소비식": alt}).round(3))
