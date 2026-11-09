# 이 파일은 docs/howto/diagnostics.md에서 만든다(python docs/build_docs.py) — 고치려면 문서를 고친다.
"""레시피: 진단 — 문서: docs/howto/diagnostics.md"""


# %% 레시피: 진단
import pandas as pd
import equion as eqn

wf = eqn.datasets.load("toy_q")
eqs = {"투자": wf.equation("eq_i").ls("I c Y(-1) R"),
       "소비": wf.equation("eq_cn").ls("CN c Y CN(-1)"),
       "물가": wf.equation("eq_p").ls("dlog(P) c dlog(Y) dlog(POIL)")}

# %% R16. 여러 식의 진단을 한 표로
rows = {}
for name, e in eqs.items():
    d = e.diagnostics().data
    rows[name] = d["p값"]
print(pd.DataFrame(rows).round(3))

# %% R17. 여러 시리즈의 단위근 표
eqn.verbose(0)                                  # 검정마다 찍히는 요약 줄을 끈다
rows = {}
for x in ("Y", "log(Y)", "dlog(Y)", "R", "d(R)", "RL - R"):
    a, k = wf.adf(x), wf.kpss(x)
    rows[x] = {"ADF p": a.pvalue, "KPSS p": k.pvalue, "판정": "정상" if a.pvalue < 0.05 and k.pvalue > 0.05 else "단위근 의심"}
eqn.verbose(1)
print(pd.DataFrame(rows).T)

# %% R18. 구조 변화 시점 찾기
eqn.verbose(0)
stats = {f"{y}Q1": eqs["투자"].chow(f"{y}Q1").statistic for y in range(1980, 2015, 5)}
eqn.verbose(1)
print({k: round(v, 2) for k, v in stats.items()})

# %% R19. 계수 제약 여러 개를 한꺼번에
e = eqs["투자"]
e.wald("c(2) = 0.15")
e.wald("c(3) = -1")
e.wald("c(2) = 0.15", "c(3) = -1")             # 함께

# %% R53. 분석을 기록으로 — 단위근·공적분·오차수정, 그리고 남기기
p = eqn.Project.create("an_prj", force=True)
print(p.an("unitroot", "core", trend="ct").text())      # 명령줄 equion an unitroot core --trend ct
print(p.an("coint", "RL R").text())
e = p.an("ecm", "log(CN) log(Y)", as_name="ecm_1")
print(p.keep(e.id, as_name="cons_ecm1").text())         # 단기식을 demand:CN의 후보로 — 계수 그대로
print(p.compare(part="demand:CN").table[["R²adj", "기준"]])
