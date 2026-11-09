# 이 파일은 docs/tutorial/09-project.md에서 만든다(python docs/build_docs.py) — 고치려면 문서를 고친다.
"""9. 프로젝트와 스크립트 — 문서: docs/tutorial/09-project.md"""


# %% 9. 프로젝트와 스크립트
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd
import equion as eqn


def equion(*args, cwd="prj"):
    """터미널의 `equion …`과 같다 — 프로젝트 폴더(cwd)에서, 화면 출력과 종료 코드를 보인다."""
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable, "-m", "equion", *args], cwd=cwd, capture_output=True, text=True,
                       encoding="utf-8", env=env, stdin=subprocess.DEVNULL)
    print((r.stdout + r.stderr).rstrip())
    if r.returncode:
        print(f"(종료 코드 {r.returncode})")
    return r.returncode


equion("new", "prj", "--template", "desk", "--force", cwd=".")

# %% 9.1 블록과 모형 — 조립
print(Path("prj/EQUATIONS/demand.txt").read_text(encoding="utf-8"))
equion("assemble", "main")

# %% 9.2 자료 회차
equion("data", "list")

# %% 9.3 식 고르기 — 추정·후보·비교·채택
equion("est", "demand:CN", "--as", "cn1")
equion("est", "CN c Y CN(-1) CN(-2)", "--for", "demand:CN", "--as", "cn2")
equion("compare", "--part", "demand:CN")
equion("hs", "main", "--as", "h_now")
equion("hs", "main", "--swap", "demand:CN=est:cn2", "--vs", "hs:h_now", "--as", "h_cn2")
equion("adopt", "est:cn2")
equion("history", "list")

# %% 9.4 전망과 보고서
equion("sim", "base", "--as", "fc_base")
equion("sim", "oil20", "--as", "fc_oil20")
equion("report", "new", "memo", "--title", "이번 전망")
equion("report", "add", "memo", "sim:fc_base", "--rows", "Y,CN,I", "--show", "yoy", "--annual", "--title", "성장률")
equion("report", "add", "memo", "sim:fc_oil20", "--rows", "Y,P", "--show", "diff", "--title", "유가 20% 상승의 영향")
equion("an", "unitroot", "core", "--trend", "c")

# %% 9.5 스크립트 한 번 — 새 자료가 오면
df = pd.read_csv("prj/DATA/raw/toy_q.csv", index_col=0)
df.loc["2020Q1"] = df.iloc[-1] * 1.01
df.to_csv("prj/DATA/raw/inbox/toy_q_2020Q1.csv")
equion("data", "inbox")
equion("check", "FLOWS/monthly.eqs")
equion("run", "FLOWS/monthly.eqs")
equion("run", "--replay", "run:monthly_0001", "-q")

# %% 9.6 Claude와 함께
print("\n".join(eqn.help.guide_text().splitlines()[4:15]))
