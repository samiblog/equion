# 이 파일은 docs/howto/output.md에서 만든다(python docs/build_docs.py) — 고치려면 문서를 고친다.
"""레시피: 출력·보고서 — 문서: docs/howto/output.md"""


# %% 레시피: 출력·보고서
from pathlib import Path

import equion as eqn

wf = eqn.datasets.load("toy_q")
eq = wf.equation("eq_i").ls("I c Y(-1) R")

# %% R40. 표를 여러 형식으로
t = wf.table("t_i", eq)                         # 방정식·검정·DataFrame·출력 객체를 표로
for path in ("eq.csv", "eq.xlsx", "eq.html", "eq.txt"):
    t.save(path)
print(Path("eq.txt").read_text(encoding="utf-8").splitlines()[0])

# %% R41. 그래프를 html로(인터넷 없이 열리게)
g = wf.graph("g_y", "Y CN I", start="2000Q1", title="소득과 구성 요소")
g.output().save("y_inline.html", include_js="inline")     # plotly.js를 파일에 넣는다(약 3MB)
g.save("y_cdn.html")                                       # 기본: 인터넷에서 plotly.js를 부른다(작음)
spec = g.output().spec()                                   # JSON으로 쓸 수 있는 그림 정의(dict)
print(sorted(spec), len(spec["data"]))

# %% R42. 출력 여러 개를 한 보고서로
eqn.spool.clear()
eqn.spool.mode = "collect"                     # 화면에 찍지 않고 모으기만
eqn.show(eq, eq.diagnostics(), wf.graph("g2", "I"))
print([type(o).__name__ for o in eqn.spool.items])
eqn.spool.mode = "auto"

# %% R43. 출력 수준 조절
eqn.verbose(0)                                 # 요약 줄도 끔
wf.equation("quiet_eq").ls("CN c Y")
eqn.verbose(1)                                 # 기본(요약 한 줄)
wf.equation("loud_eq").ls("CN c Y")
