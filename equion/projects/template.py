#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""예제 프로젝트(`equion new 폴더 --template desk`) — 가상 분기 모형, 원자료는 예제 자료 toy_q·toy_m.

    폴더/
      equion.toml            자료 정의·블록·모형 조립·HS 기본값
      DATA/raw/toy_q.csv     원자료 — 분기 거시(1970Q1~2019Q4, 가상)
      DATA/raw/toy_m.csv     원자료 — 월간 지표(2000M1~2019M12, 가상)
      DATA/series.toml       자료 정의 — 불러오기 틀·시리즈(주기 변환·계절조정 예 포함)
      DATA/derived.txt       파생 시리즈
      EQUATIONS/demand.txt   수요 블록 — 소비·투자·국민소득 항등식
      EQUATIONS/price.txt    물가 블록
      EQUATIONS/finance.txt  금융 블록 — 장기금리(1980Q1부터)·통화
      ASSUMPTIONS/base.csv   가정 세트 — 전망 구간의 정부지출·유가 경로(정책금리는 채우기 규칙)
      ADDFACTORS/base.toml   보정항 — 소비 last · 투자 decay
      SCENARIOS/oil20.toml   시나리오 — 유가 20% 상승
      README.md · .gitignore
자료 회차(work/data/<회차>/)는 Project.create가 만들고 지금 회차로 정한다.
"""

import os
import shutil

CONFIG = """\
# Equion 프로젝트 — 예제(가상 분기 모형). 형식: docs/reference/formats.md "프로젝트"
[project]
name = "{name}"
format = "equion-project"
format_version = 1

[data]                            # 자료 정의와 회차 — 원자료 DATA/raw/ → 정의 → 회차 work/data/<회차>/
series = "DATA/series.toml"       # 어느 원자료의 어느 열을 어떻게 읽어 어떤 시리즈로
derived = "DATA/derived.txt"      # 파생 시리즈(이름 = 식)
freq = "Q"

[block]                           # 블록 = 방정식 파일 하나
demand  = {{ file = "EQUATIONS/demand.txt",  desc = "수요" }}
price   = {{ file = "EQUATIONS/price.txt",   desc = "물가" }}
finance = {{ file = "EQUATIONS/finance.txt", desc = "금융" }}

[model.core]
desc = "수요 블록만"
blocks = ["demand"]

[model.main]
desc = "수요 + 물가 + 금융"
include = ["core"]                # 모형 안에 모형
blocks = ["price", "finance"]

[model.main_fixrl]
desc = "장기금리를 실측으로 둔 main"
include = ["main"]
exclude = ["finance:RL"]          # 뺀 식의 목표는 외생(실측)이 된다

[group]
core = {{ series = ["Y", "CN", "I"], desc = "핵심 수요" }}

[criteria]                        # 판단 기준 — 추정 기록의 '기준' 줄(통과·걸러짐과 까닭)
alpha = 0.05                      # 진단 유의수준
tests = ["lm", "reset"]           # 기준에 넣는 진단(p < alpha면 걸러짐)

[criteria.signs]                  # 기대 부호
"demand:CN" = {{ Y = "+" }}
"demand:I" = {{ R = "-" }}

[hs]                              # 과거 재현(HS) 기본값
model = "main"
range = "2005Q1:last"             # last = 자료의 마지막 기 — 새 자료 회차로 바꾸면 따라 늘어난다
mode = "dynamic"

[forecast]                        # 전망 기본값 — equion sim
model = "main"
range = "next:8"                  # 자료 끝 다음 기부터 8기
assume = "base"                   # 가정 세트 ASSUMPTIONS/base.csv
addfactors = "base"               # 보정항 ADDFACTORS/base.toml
fill = "last"                     # 가정이 없는 외생의 채우기: last · growth · trend · none
"""

ADDFACTORS = """\
# 보정항 — 식마다 전망 구간의 초깃값 규칙(전망 앞 마지막 잔차 기준). 형식: docs/reference/formats.md "가정·보정항·시나리오"
default = "zero"                  # 적지 않은 식: zero · last · decay · mean

[eq."demand:CN"]
rule = "last"                     # 마지막 잔차를 그대로

[eq."demand:I"]
rule = "decay"                    # 마지막 잔차를 반감기로 줄이기
half_life = 4
"""

OIL20 = """\
# 시나리오 — 유가 20% 상승(전망 구간 내내). 기간은 라벨 또는 start · end · start+N · end-N
desc = "유가 20% 상승"
base = "base"                     # 가정 세트

[[shock]]
var = "POIL"
from = "start"
pct = 20
"""

SERIES = """\
# 자료 정의 — 원자료(DATA/raw/)를 어떻게 읽어 어떤 시리즈로 만드는지. 형식: docs/reference/formats.md "자료 정의"
# 원자료는 고치지 않는다. 정의를 고친 뒤 equion data build → equion data use <회차>

[source.na]                       # 분기 거시 자료(예제 자료 toy_q) — 첫 줄이 열 이름, 첫 열이 시점
file = "DATA/raw/toy_q.csv"

[source.monthly]                  # 월간 지표(예제 자료 toy_m)
file = "DATA/raw/toy_m.csv"

[series.CN]
from = "na:CN"
unit = "조원(가상)"
desc = "소비"

[series.I]
from = "na:I"
unit = "조원(가상)"
desc = "투자"

[series.G]
from = "na:G"
unit = "조원(가상)"
desc = "정부지출"

[series.Y]
from = "na:Y"
unit = "조원(가상)"
desc = "국민소득"

[series.R]
from = "na:R"
unit = "%"
desc = "정책금리"

[series.RL]
from = "na:RL"
unit = "%"
desc = "장기금리(1980Q1부터)"

[series.P]
from = "na:P"
desc = "물가 지수"

[series.POIL]
from = "na:POIL"
desc = "유가 지수"

[series.M2]
from = "na:M2"
unit = "조원(가상)"
desc = "통화량"

[series.CNSA]
from = "na:CNNSA"
seas = { method = "stl", model = "multiplicative" }
unit = "조원(가상)"
desc = "소비 — 계절조정 전 자료를 STL 승법으로 조정(예)"

[series.IPQ]
from = "monthly:IP"
convert = "mean"                  # 월간 → 분기 평균
desc = "산업생산 — 월간을 분기 평균으로(예)"
"""

DERIVED = """\
# 파생 시리즈 — 한 줄에 '이름 = 식'(방정식 문법), 위에서부터 차례로 만든다
PI = 100*(P/P(-4) - 1)            # 물가 상승률(전년동기, %)
RR = R - PI                       # 실질금리
"""

DEMAND = """\
# 수요 블록 — 한 줄에 한 식, '#' 뒤는 설명(문법: docs/explain/equations.md)
CN c Y CN(-1)            # 소비
I c Y(-1) R              # 투자
Y = CN + I + G           # 국민소득(항등식)
"""

PRICE = """\
# 물가 블록
dlog(P) c dlog(Y) dlog(POIL)           # 물가 — 수요와 유가
"""

FINANCE = """\
# 금융 블록 — 장기금리 자료는 1980Q1부터
RL c R RL(-1)                          # 장기금리
log(M2) c log(P) log(Y) RL log(M2(-1)) # 통화
"""

README = """\
# {name}

Equion 프로젝트(예제 — 가상 분기 모형, 원자료는 예제 자료 toy_q·toy_m)입니다. `equion.toml`이 자료 정의와 블록(방정식 파일)을
이름으로 묶고, 모형은 블록과 다른 모형을 끼워 조립합니다.

```bash
equion data list              # 자료 회차 목록(* 지금 회차)
equion data build             # 원자료·정의가 바뀌면 새 회차 → equion data use <회차>
equion assemble main          # 조립 검사 — 내생·외생·겹친 목표·모르는 변수·블록 사이 연결(계산 없이)
equion assemble main_fixrl    # 장기금리 식을 뺀 조립
equion ident demand:Y --check # 항등식을 실측으로 검사
```

```python
import equion as eqn
p = eqn.project(".")
r = p.hs("main")              # 과거 재현(HS) — [hs]의 구간·방식
r.statistics()
p.hs("demand")                # 블록 HS — 수요 블록만 풀고 나머지 변수는 실측
```

| 위치 | 내용 |
|---|---|
| `equion.toml` | 자료 정의·블록·모형 조립·HS 기본값 |
| `DATA/raw/` | 원자료 — 받은 그대로(고치지 않는다) |
| `DATA/series.toml` · `DATA/derived.txt` | 자료 정의 — 어느 열을 어떻게 읽어 어떤 시리즈로 · 파생 시리즈 |
| `EQUATIONS/` | 블록 — 방정식 파일 하나가 블록 하나(한 줄에 한 식) |
| `work/data/` | 자료 회차 — '자료 만들기'로만 생긴다(git 제외) |
"""

GITIGNORE = """\
work/
out/
exports/
DATA/raw/
*.eqw/
__pycache__/
"""


def create_desk_project(path: str, force: bool = False) -> list:
    """예제 프로젝트의 파일을 쓰고 만든 파일 목록(상대 경로)을 돌려준다. 자료 회차는 만들지 않는다(Project.create가 만든다)."""
    from ..datasets import path as dataset_path
    if os.path.exists(path) and os.listdir(path) and not force:
        raise FileExistsError(f"폴더가 비어 있지 않습니다: {path} (덮어쓰려면 --force)")
    name = os.path.basename(os.path.abspath(path))
    files = {
        "equion.toml": CONFIG.format(name=name),
        "DATA/series.toml": SERIES,
        "DATA/derived.txt": DERIVED,
        "EQUATIONS/demand.txt": DEMAND,
        "EQUATIONS/price.txt": PRICE,
        "EQUATIONS/finance.txt": FINANCE,
        "ADDFACTORS/base.toml": ADDFACTORS,
        "SCENARIOS/oil20.toml": OIL20,
        "README.md": README.format(name=name),
        ".gitignore": GITIGNORE,
    }
    for d in ("DATA/raw", "EQUATIONS", "ASSUMPTIONS", "ADDFACTORS", "SCENARIOS"):
        os.makedirs(os.path.join(path, d), exist_ok=True)
    created = []
    for rel, text in files.items():
        with open(os.path.join(path, rel), "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        created.append(rel)
    for ds in ("toy_q", "toy_m"):
        shutil.copyfile(dataset_path(ds), os.path.join(path, "DATA", "raw", f"{ds}.csv"))
        created.append(f"DATA/raw/{ds}.csv")
    with open(os.path.join(path, "ASSUMPTIONS", "base.csv"), "w", encoding="utf-8", newline="\n") as f:
        f.write(_assumptions(dataset_path("toy_q")))
    created.append("ASSUMPTIONS/base.csv")
    return created


def _assumptions(src: str) -> str:
    """가정 세트 예 — 자료 끝 다음 12분기의 정부지출(분기 0.5% 증가)·유가(분기 1% 증가). 정책금리 R은 적지 않아 채우기 규칙(last)."""
    import pandas as pd
    from ..data.periods import format_period, parse_period
    df = pd.read_csv(src, index_col=0)
    last = parse_period(str(df.index[-1]), "Q")
    g, oil = float(df["G"].iloc[-1]), float(df["POIL"].iloc[-1])
    lines = ["period,G,POIL"]
    for k in range(1, 13):
        lines.append(f"{format_period(last + k, 'Q')},{g * 1.005 ** k:.3f},{oil * 1.01 ** k:.3f}")
    return "\n".join(lines) + "\n"
