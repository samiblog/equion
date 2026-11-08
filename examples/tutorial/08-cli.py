# 이 파일은 docs/tutorial/08-cli.md에서 만든다(python docs/build_docs.py) — 고치려면 문서를 고친다.
"""8. 명령줄 — 문서: docs/tutorial/08-cli.md"""


# %% 8. 명령줄
import json
import os
import subprocess
import sys
from pathlib import Path


def equion(*args):
    """터미널의 `equion …`과 같다 — 화면 출력과 종료 코드를 보인다."""
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable, "-m", "equion", *args], capture_output=True, text=True,
                       encoding="utf-8", env=env)
    print((r.stdout + r.stderr).rstrip())
    print(f"(종료 코드 {r.returncode})")
    return r.returncode


equion("--version")

# %% 8.1 스크립트 쓰기
os.makedirs("scripts", exist_ok=True)
with open("scripts/toy_forecast.py", "w", encoding="utf-8") as f:
    f.write('''"""작은 거시 모형: 추정 → 과거 재현 → 정부지출 시나리오 → 전망."""
import equion as eqn

p = eqn.params(g_up=10.0, start="1975Q1", end="2019Q4", horizon="2021Q4")

wf = eqn.datasets.load("toy_q")
wf.smpl(p.start, p.end)
eq_i = wf.equation("eq_i").ls("I c Y(-1) R")
eq_cn = wf.equation("eq_cn").tsls("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
eq_p = wf.equation("eq_p").ls("dlog(P) c dlog(Y) dlog(POIL)")
m = wf.model("toy").merge(eq_i, eq_cn, eq_p).append("Y = CN + I + G")
eqn.show(eq_cn)

base = m.solve()
eqn.show(base.summary())

m.scenario("g_up").shock("G", p.g_up, "2015Q1", p.end, kind="pct")
m.solve("2015Q1", p.end)
eqn.show(wf.graph("g_y", "Y Y_0 Y_1", start="2010Q1", title="국민소득"))

m.scenario("baseline")
m.forecast("2020Q1", p.horizon, exog_fill="trend")
eqn.show(wf.table("fc", wf.to_pandas(["Y_0", "CN_0", "I_0"], labels=True).loc["2020Q1":p.horizon].round(1),
                  title="전망"))
''')
print(len(Path("scripts/toy_forecast.py").read_text(encoding="utf-8").splitlines()), "줄")

# %% 8.2 실행과 보고서
equion("run", "scripts/toy_forecast.py", "--run-id", "first", "-q")
print(sorted(os.listdir("out/first")))
man = json.loads(Path("out/first/manifest.json").read_text(encoding="utf-8"))
print(man["format"], man["status"], man["exit_code"])
print(man["params"]["resolved"])
print([(s["model"], s["scenario"], s["counts"]["ok"]) for s in man["solves"]])
print([o["title"] for o in man["outputs"]])

# %% 8.3 매개변수와 옵션
equion("run", "scripts/toy_forecast.py", "--set", "g_up=5", "--smpl", "1990Q1:2019Q4",
       "--format", "csv,xlsx", "--run-id", "g5", "-q")
man = json.loads(Path("out/g5/manifest.json").read_text(encoding="utf-8"))
print(man["params"]["resolved"]["g_up"], man["smpl"], sorted(os.listdir("out/g5/tables"))[:3])

# %% 8.4 종료 코드 — 자동화의 약속
equion("run", "scripts/toy_forecast.py", "--set", "start=1970Q1", "--fail-on", "partial", "--run-id", "strict", "-q")
equion("run", "scripts/없는파일.py")

# %% 8.5 실행 없이 검사하기 — check
with open("toy_model.txt", "w", encoding="utf-8") as f:
    f.write("I c Y(-1) R\nCN c Y CN(-1)\ndlog(P) c dlog(Y) dlog(POIL)\nY = CN + I + G\n")
import equion as eqn
equion("check", "toy_model.txt", "--data", eqn.datasets.path("toy_q"))
with open("broken.txt", "w", encoding="utf-8") as f:
    f.write("I c Y(-1) R\nCN c log(Y CN(-1)\nY = CN + I + NOPE\n")
equion("check", "broken.txt")

# %% 8.6 요약 보기와 새 프로젝트
equion("info", eqn.datasets.path("toy_m"))
equion("info", "out/first")
equion("new", "my_project")
print(sorted(os.listdir("my_project")))
