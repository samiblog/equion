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

# %% R48. 프로젝트로 블록·모형 조립하기
p = eqn.Project.create("demo_prj", force=True)   # 블록 demand·price·finance, 모형 core·main·main_fixrl
print(p.assemble("main").text())          # 계산 없이 조립 검사 — 명령줄 equion assemble main
r = p.hs("main")                          # [hs]의 구간·방식으로 과거 재현 — 식은 지금 자료로 추정해 조립
print(r.statistics()["RMSPE"].round(3))
print(p.hs("demand").counts())            # 블록 HS — 수요 블록만 풀고 나머지 변수는 실측
print(p.ident("demand:Y").text())         # 항등식을 실측으로 검사 — 명령줄 equion ident demand:Y --check

# %% R50. 후보 식 고르기 — 추정 기록·비교·바꿔 끼운 HS·채택
c1 = p.est("demand:CN", as_name="cons_c1", sim=True)          # 블록 파일의 그 줄 — equion est demand:CN --as cons_c1 --sim
c3 = p.est("CN c Y(-1) CN(-1)", as_name="cons_c3", sim=True)  # 식 글자 — 목표가 CN이라 demand:CN의 후보
print(c3.text())
print(p.compare(part="demand:CN").table[["식", "R²adj", "LM(2) p", "기준", "단독 RMSPE%"]].round(4))
before = p.hs("main", record=True, as_name="before")
after = p.hs("main", record=True, swap={"demand:CN": "est:cons_c3"}, vs="hs:before")   # 파일은 그대로, 그 기록의 계수로
print(after.text())
print(p.adopt("est:cons_c1").text())        # c3는 기준은 통과했지만 HS가 나빠졌다 — 지금 식(c1)을 채택(계수 고정)

# %% R52. 제안·바뀜 기록·그때 그대로 다시
pr = p.propose(title="소비에 시차 하나 더", why="est:cons_c1의 LM 검정이 경계선(p=0.046)",
               parts={"demand:CN": "CN c Y CN(-1) CN(-2)"})   # 파일은 그대로 — equion propose new --part …
print(pr.diff())
p.apply_proposal(pr.name)                                     # equion propose apply p1
for c in p.history.list():
    print(c.text())
rp = p.replay("hs:before")                                    # 파일이 바뀐 뒤에도 그때 그대로 — equion hs --replay hs:before
print(rp.meta["replay"]["of"], "같은 결과" if rp.meta["replay"]["same"] else "다름")

# %% R65. 이정표와 묶어 보내기 — 확정한 때를 남기고, 다른 PC로 옮기기
p = eqn.Project.create("ms_prj", force=True)
print(p.milestone_make("fc_2026_11", note="11월 전망 확정").text())
with open("ms_prj/EQUATIONS/price.txt", "a", encoding="utf-8") as f:   # 이정표 뒤의 고침
    f.write("# 이정표 뒤에 더한 주석\n")
print(p.milestone_diff("fc_2026_11").text())
print(p.milestone_restore("fc_2026_11") is not None, p.milestone_diff("fc_2026_11").same)
b = p.bundle()
print(b.text())
q = eqn.Project.from_bundle("ms_prj/" + b.path, "ms_copy")             # 다른 PC에서 — equion bundle open 묶음.zip ms_copy
print(q.name, q.vintage == p.vintage, [m["name"] for m in q.milestones()])
