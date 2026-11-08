# 이 파일은 docs/tutorial/04-model.md에서 만든다(python docs/build_docs.py) — 고치려면 문서를 고친다.
"""4. 연립 모델 — 문서: docs/tutorial/04-model.md"""


# %% 4. 연립 모델
import equion as eqn

wf = eqn.datasets.load("toy_q")
eq_i = wf.equation("eq_i").ls("I c Y(-1) R")
eq_cn = wf.equation("eq_cn").tsls("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
eq_p = wf.equation("eq_p").ls("dlog(P) c dlog(Y) dlog(POIL)")

# %% 4.1 모델 만들기
m = wf.model("toy")
m.merge(eq_i, "eq_cn")                     # 객체 또는 객체 이름
m.merge(eq_p)
m.append("Y = CN + I + G")                 # 항등식(여러 줄 글자도 된다)
print(m)
eqn.show(m)                                # 식 목록
with open("toy_model.txt", "w", encoding="utf-8") as f:
    f.write("""# 작은 거시 모형
I c Y(-1) R                                   # 투자
CN c Y CN(-1) @inst G R CN(-1) Y(-1)          # 소비(2SLS — @inst가 있으면 도구변수 추정)
dlog(P) c dlog(Y) dlog(POIL)                  # 물가
Y = CN + I + G                                # 국민소득 항등식
""")
m_file = wf.model("toy_file").merge("toy_model.txt")
print(m_file.endogenous, len(m_file.equations), m_file.identities)

# %% 4.2 구조 보기
print(m.endogenous, m.exogenous)
eqn.show(m.blocks())
print(m.variables().head())

# %% 4.3 과거 재현 — 동적 풀이
wf.smpl("1975Q1", "2019Q4")
r = m.solve()
print(r)
eqn.show(r.summary())
print(m.compare("Y").tail(4).round(1))         # 실측과 모든 시나리오 결과(표본 구간)
g = wf.graph("g_hs", "Y Y_0", start="2005Q1", title="국민소득: 실측과 동적 풀이")
g.save("hs.html")

# %% 4.4 정적 풀이와 fit
for mode in ("fit", "static", "dynamic"):
    st = m.solve(mode=mode).statistics()
    print(f"{mode:8s}", st["RMSPE"].round(3).to_dict())

# %% 4.5 기간 상태
r0 = m.solve("1970Q1", "1970Q4")
print(r0.counts())
print(r0.status()[["status", "excluded"]])
eqn.show(m.gaps("1970Q1", "1970Q2"))      # 비어 있는 입력 진단

# %% 4.6 과거를 그대로 재현하기
sc = m.scenario("replay")
sc.use_residuals()
rr = m.solve(scenario="replay")
cmp = wf.to_pandas(["Y", "Y" + sc.alias, "CN", "CN" + sc.alias], labels=True).loc["2019Q1":"2019Q4"]
print(cmp.round(3))
m.scenario("baseline")                     # 다음 풀이가 기준선으로 가도록

# %% 4.7 결과 저장
path = r.save("results/hs_toy.csv")
import pandas as pd
df = pd.read_csv(path)
print(path, df.shape)
print(list(df.columns[:9]))

# %% 4.8 풀이 설정과 실패 정책
hard = dict(method="gauss-seidel", fallback=(), max_iterations=1)     # 한 번만 돌고 다른 방법도 쓰지 않음
print(m.solve("2010Q1", "2010Q4", **hard).counts())                  # 기본 on_fail='actual' → 실측 대체(fallback)
print(m.solve("2010Q1", "2010Q4", on_fail="nan", **hard).counts())   # 값 없음(failed)
print(m.solve("2010Q1", "2010Q4").counts())                          # 기본 설정은 문제없이 풀린다

# %% 4.9 모델 고치기
eq_i.ls("I c Y(-1) R @smpl 1990Q1 2019Q4")     # 표본을 바꿔 다시 추정
print(m.solve().statistics()["RMSPE"].round(3).to_dict())
m2 = wf.model("toy_small").merge(eq_i, eq_cn).append("Y = CN + I + G")
m2.drop("eq_i")
print(m2.endogenous)
