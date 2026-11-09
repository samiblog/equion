# 이 파일은 docs/howto/script.md에서 만든다(python docs/build_docs.py) — 고치려면 문서를 고친다.
"""레시피 — 스크립트·재연 — 문서: docs/howto/script.md"""


# %% R56 자료만 넣고 스크립트 한 번
from pathlib import Path

import pandas as pd
import equion as eqn

p = eqn.Project.create("monthly_prj", force=True)
df = pd.read_csv(Path(p.root, "DATA/raw/toy_q.csv"), index_col=0)
df.loc["2020Q1"] = df.iloc[-1] * 1.01                      # 새 분기(합성)
df.to_csv(Path(p.root, "DATA/raw/inbox/toy_q_2020Q1.csv"))
for item in p.data_inbox():                                 # 미리보기 — equion data inbox
    print(item.text())
plan = p.run_script("FLOWS/monthly.eqs", dry_run=True)
print("\n".join(plan.text().splitlines()[:12]))
r = p.run_script("FLOWS/monthly.eqs", echo=print)
print(r.text())
q = eqn.project("monthly_prj")                              # 회차가 바뀌었으니 다시 연다
text = Path(q.root, "reports", f"forecast_{q.vintage}.md").read_text(encoding="utf-8")
print(text.split("<!-- /equion:report -->")[0].strip())     # 머리와 첫 구역

# %% R57 그때 그대로 다시 · 이 단계부터
rp = q.replay_run(r.id)                                     # equion run --replay run:monthly_0001
print(rp.text())
r2 = q.run_script("FLOWS/monthly.eqs", sets={"scenarios": "base"}, from_step="전망", echo=print)
print(r2.text())

# %% R58 탐색한 기록으로 스크립트 · Python으로
e = q.est("CN c Y CN(-1) CN(-2)", part="demand:CN", as_name="cn_lag2",
          command='equion est "CN c Y CN(-1) CN(-2)" --for demand:CN --as cn_lag2')
h = q.hs("main", record=True, swap={"demand:CN": e.id}, command=f"equion hs main --swap demand:CN={e.id}")
rel = q.new_script("try_lag2", records=[e.id, h.id])
src = Path(q.root, rel).read_text(encoding="utf-8").replace(f"demand:CN={e.id}", "demand:CN={est}")
Path(q.root, rel).write_text(src, encoding="utf-8")         # 이번에 추정한 식으로 바꿔 끼우게
print(src)
print(q.check_script(rel).text())
py = q.export_script(rel)
print(Path(q.root, py).read_text(encoding="utf-8"))
