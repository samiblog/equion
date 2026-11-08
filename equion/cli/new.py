#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`equion new` — 새 프로젝트 폴더의 뼈대를 만든다.

    폴더/
      README.md            사용법
      DATA/data.csv        예시 분기 데이터(소비 CONS·투자 INV·정부지출 GOV·금리 RATE·GDP, 2000Q1~2024Q4)
                           — --bare면 빈 폴더
      EQUATIONS/model.txt  예시 모델(행태식 2 + 항등식 1)
      scripts/main.py      예시 스크립트(추정 → 모델 → 기준선·시나리오 → 그래프 → 전망)
      .gitignore           out/ · *.eqw/ 제외

예시 데이터는 아래 모형에서 난수로 만든 가상 자료이다(재현 가능: 고정 시드).
"""

import os

import numpy as np
import pandas as pd

from ..data.periods import period_starts

EQUATIONS = """\
# 예시 모델 — 한 줄에 한 식, '#' 뒤는 주석 (문법: docs/explain/equations.md)
# 등호가 없으면 추정식(첫 항이 종속변수, c는 상수항), 등호가 있고 c(n)이 없으면 항등식이다.

# 변수 이름 C는 상수항과 겹쳐 쓸 수 없다.

log(CONS) c log(CONS(-1)) log(GDP)          # 소비: 습관 + 소득
log(INV) c log(INV(-1)) log(GDP) RATE       # 투자: 조정 비용 + 소득 + 금리
GDP = CONS + INV + GOV                      # 국민소득 항등식
"""

SCRIPT = '''\
"""예시 스크립트 — 평범한 Python이다. 프로젝트 폴더에서 실행한다:

    equion run scripts/main.py
    equion run scripts/main.py --set g_shock=0.05 --format csv,xlsx,html
"""
import equion as eqn

# 명령줄 --set 이름=값 으로 바꿀 수 있는 매개변수(기본값의 형으로 변환된다)
p = eqn.params(g_shock=0.02, start="2005Q1", end="2024Q4", horizon="2026Q4")

wf = eqn.wfopen("DATA/data.csv")
wf.smpl(p.start, p.end)                       # 추정·풀이·genr·그래프의 기본 구간

# 방정식 파일의 추정식을 현재 표본으로 추정해 모델에 넣는다(항등식은 그대로)
m = wf.model("demo").merge("EQUATIONS/model.txt")
for eq in m.equations:
    eq.show()                                 # 추정 결과표
m.blocks().show()                             # 블록 구조(동시·순차)

# 기준선(실측 외생, 동적 풀이) → CONS_0 · INV_0 · GDP_0
base = m.solve()
base.summary().show()

# 시나리오: 정부지출을 g_shock 만큼 늘린다 → *_1
m.scenario("g_up").override("GOV", wf["GOV"] * (1 + p.g_shock))
m.solve()
wf.genr("GDP_EFFECT = 100 * (GDP_1 / GDP_0 - 1)")
wf.graph("g_gdp", "GDP GDP_0 GDP_1", title="GDP — 실측 · 기준선 · 정부지출 확대").show()
wf.graph("g_effect", "GDP_EFFECT", title=f"정부지출 {p.g_shock:.0%} 확대의 GDP 효과(%)").show()

# 전망: 기간을 늘리고 외생변수 경로를 Python으로 정한 뒤 기준선으로 푼다
wf.extend(p.horizon)
wf.fill("GOV", "growth")                      # 평균 성장률로
wf.fill("RATE", "last")                       # 마지막 값 유지
m.scenario("baseline")
m.forecast("2025Q1", p.horizon)
wf.smpl("2023Q1", p.horizon)
wf.table("t_forecast", wf.to_pandas(["GDP", "GDP_0", "CONS_0", "INV_0", "GOV", "RATE"], smpl=True, labels=True),
         title="전망 — 2023Q1~ (2025Q1부터 전망)").show()
'''

README = """\
# {name}

Equion 프로젝트입니다. 스크립트는 평범한 Python이고, 명령줄에서 실행하면 표·그래프·로그를
보고서 폴더(`out/<실행ID>/`)에 남깁니다.

```bash
equion check EQUATIONS/model.txt --data DATA/data.csv
```

```bash
equion run scripts/main.py
```

```bash
equion run scripts/main.py --set g_shock=0.05 --format csv,xlsx,html
```

| 위치 | 내용 |
|---|---|
| `DATA/` | 데이터 파일(xlsx/csv, 첫 열이 날짜) |
| `EQUATIONS/` | 방정식 파일(한 줄에 한 식) |
| `scripts/` | 실행 스크립트(`eqn.params`로 명령줄 매개변수를 받는다) |
| `out/` | 실행 보고서(`report.html`·`manifest.json`·`run.log`·표·그래프) |

설치하지 않았다면 `equion` 대신 `python -m equion` 로 실행합니다.
"""

GITIGNORE = """\
out/
*.eqw/
__pycache__/
"""

BARE_SCRIPT = '''\
"""스크립트 — equion run scripts/main.py"""
import equion as eqn

p = eqn.params()

# wf = eqn.wfopen("DATA/data.xlsx")
# wf.smpl("2000Q1", "2022Q4")
# m = wf.model("m").merge("EQUATIONS/model.txt")
# m.solve().summary().show()
'''


def example_data(seed: int = 2026) -> pd.DataFrame:
    """예시 분기 데이터(가상): 위 모형을 고정 시드로 모의해 만든다."""
    rng = np.random.default_rng(seed)
    idx = period_starts("2000Q1", "2024Q4", "Q")
    T = len(idx)
    C, I, G, R, Y = (np.zeros(T) for _ in range(5))
    C[0], I[0], G[0], R[0] = 60.0, 20.0, 20.0, 3.0
    Y[0] = C[0] + I[0] + G[0]
    a, b = 0.3 * np.log(0.6), 0.4 * np.log(0.2) + 0.03
    for t in range(1, T):
        G[t] = G[t - 1] * np.exp(0.008 + 0.005 * rng.standard_normal())
        R[t] = 3.0 + 0.9 * (R[t - 1] - 3.0) + 0.2 * rng.standard_normal()
        e1, e2 = 0.004 * rng.standard_normal(), 0.015 * rng.standard_normal()
        y = Y[t - 1]
        for _ in range(100):                       # Y = C(Y) + I(Y) + G 고정점
            c = np.exp(a + 0.7 * np.log(C[t - 1]) + 0.3 * np.log(y) + e1)
            i = np.exp(b + 0.6 * np.log(I[t - 1]) + 0.4 * np.log(y) - 0.01 * R[t] + e2)
            y_new = c + i + G[t]
            if abs(y_new - y) < 1e-12:
                break
            y = y_new
        C[t], I[t], Y[t] = c, i, y_new
    df = pd.DataFrame({"CONS": C, "INV": I, "GOV": G, "RATE": R, "GDP": Y},
                      index=pd.DatetimeIndex(idx, name="date"))
    return df.round(6)


def create_project(path: str, bare: bool = False, force: bool = False) -> list:
    """프로젝트 뼈대를 만들고 만든 파일 목록을 돌려준다. 이미 있는 파일은 force가 아니면 건드리지 않는다."""
    if os.path.exists(path) and os.listdir(path) and not force:
        raise FileExistsError(f"폴더가 비어 있지 않습니다: {path} (덮어쓰려면 --force)")
    name = os.path.basename(os.path.abspath(path))
    files = {
        "README.md": README.format(name=name),
        ".gitignore": GITIGNORE,
        "scripts/main.py": BARE_SCRIPT if bare else SCRIPT,
    }
    if not bare:
        files["EQUATIONS/model.txt"] = EQUATIONS
    created = []
    for d in ("DATA", "EQUATIONS", "scripts"):
        os.makedirs(os.path.join(path, d), exist_ok=True)
    for rel, text in files.items():
        fp = os.path.join(path, rel)
        with open(fp, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        created.append(rel)
    if not bare:
        example_data().to_csv(os.path.join(path, "DATA", "data.csv"), date_format="%Y-%m-%d")
        created.append("DATA/data.csv")
    return created
