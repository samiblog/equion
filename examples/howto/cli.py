# 이 파일은 docs/howto/cli.md에서 만든다(python docs/build_docs.py) — 고치려면 문서를 고친다.
"""레시피: 명령줄 — 문서: docs/howto/cli.md"""


# %% 레시피: 명령줄
import json
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd


def equion(*args):
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable, "-m", "equion", *args], capture_output=True, text=True, encoding="utf-8", env=env)
    print((r.stdout + r.stderr).rstrip())
    return r.returncode


Path("forecast.py").write_text('''import equion as eqn
p = eqn.params(g_up=0.0)
wf = eqn.datasets.load("toy_q")
m = wf.model("toy").merge("I c Y(-1) R", "CN c Y CN(-1)").append("Y = CN + I + G")
m.scenario("s").shock("G", p.g_up, "2015Q1", "2019Q4", kind="pct")
m.solve("2015Q1", "2019Q4")
eqn.show(wf.table("result", wf.to_pandas(["Y_1"], labels=True).loc["2019Q1":"2019Q4"]))
''', encoding="utf-8")

# %% R44. 매개변수를 바꿔 가며 여러 번
for g in (0, 5, 10):
    equion("run", "forecast.py", "--set", f"g_up={g}", "--run-id", f"g{g}", "--format", "csv", "-q")

# %% R45. 보고서에서 결과 숫자 꺼내기
rows = {}
for g in (0, 5, 10):
    d = Path("out") / f"g{g}"
    man = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
    table = sorted((d / "tables").glob("*result*.csv"))[0]
    rows[man["params"]["resolved"]["g_up"]] = float(pd.read_csv(table, index_col=0).iloc[-1, 0])
print({k: round(v, 1) for k, v in rows.items()})
