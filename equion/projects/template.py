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
      FLOWS/monthly.eqs      스크립트 — 새 원자료로 회차·다시 추정·HS·전망·보고서까지(equion run FLOWS/monthly.eqs)
      notes/data_check.md    노트 — 자료 점검(스크립트가 실행)
      DATA/raw/inbox/        받은 원자료를 놓는 곳(data build --inbox)
      CLAUDE.md              Claude Code에게 — 먼저 equion guide를 읽으라는 안내
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

MONTHLY = """\
# 월간 전망 — 새 원자료로 회차·다시 추정·과거 재현·전망·보고서까지
# 새 원자료를 DATA/raw/inbox/에 놓고: equion run FLOWS/monthly.eqs   (미리보기 --dry-run · 기준선만 --set scenarios=base)
# 문법: 한 줄 = equion 명령 하나 · ## 제목 = 단계 묶음 · {이름} = 값 · expect … = 확인(docs/reference/formats.md "스크립트")
param scenarios = base oil20

## 자료
data build --inbox ask --use            # 받은 원자료를 넣고 회차를 만들어 바꾼다(내용이 같으면 그 회차 그대로)
assemble main                           # 조립 검사 — 문제가 있으면 여기서 멈춘다

## 추정
est main --adopted --adopt if_pass      # 채택한 식을 새 자료로 다시 — 기준([criteria])을 통과한 식만 새 계수, 아니면 옛 계수와 표시

## 과거 재현
hs main                                 # [hs]의 구간(2005Q1:last — 새 자료면 따라 는다)
expect hs Y.rmspe < 3% --flag           # 국민소득 적합도 — 어긋나면 표시하고 계속

## 전망
sim {scenarios} --model main            # [forecast]의 구간(next:8)·가정 세트·보정항

## 결과물
note run notes/data_check.md            # 자료 점검 노트의 결과 구역을 새 기록으로
report new reports/forecast_{vintage}.md --title "월간 전망 — 자료 {vintage}" --exist-ok
report add reports/forecast_{vintage}.md {sim:base} --key growth --rows Y,CN,I,P --show yoy --annual --title "성장률 전망"
report add reports/forecast_{vintage}.md {hs} --key hs --rows Y,CN --chart --title "과거 재현"
export {hs} {sim} --xlsx exports/forecast_{vintage}.xlsx
"""

NOTE = """\
# 자료 점검

이번 자료 회차의 핵심 수요 시리즈(묶음 core)를 본다 — 월간 스크립트(FLOWS/monthly.eqs)가 `equion note run`으로 결과 구역을 새로 채운다.
아래 블록의 결과 구역은 손으로 고치지 않는다(글은 블록 밖에).

```equion
an summary core
```

항등식이 새 자료에서도 맞는지(개정이 한 시리즈에만 오면 어긋난다):

```equion
ident demand:Y --check --range last-7:last
```
"""

CLAUDE_MD = """\
# 이 폴더는 Equion 프로젝트입니다

모형 작업을 하기 전에 안내를 읽으세요: `equion guide`(규칙·프로젝트 지도·명령·분석·판단 기준·보고 꼴).

- 계산은 `equion` 명령으로(est·hs·sim·an·run) — 결론에는 근거 기록의 이름(`est:…`·`hs:…`·`sim:…`)을 붙입니다.
- `work/`·`DATA/raw/`·노트와 보고서의 결과 구역은 고치지 않습니다. 정의 파일은 명령(`adopt`·`data use`·`data define`·`block add`·
  `scenario define`·`propose`)으로 먼저 — 정의를 한꺼번에 되돌리는 `milestone restore`·`history revert`는 사람에게 먼저 묻습니다.
- 월간 작업: 새 원자료를 `DATA/raw/inbox/`에 → `equion data inbox` → `equion run FLOWS/monthly.eqs --dry-run` → `equion run FLOWS/monthly.eqs`.
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

equion run FLOWS/monthly.eqs --dry-run    # 월간 스크립트 미리보기(기록을 남기지 않음)
equion run FLOWS/monthly.eqs              # 실행 — 새 원자료는 먼저 DATA/raw/inbox/에
equion run --replay run:monthly_0001      # 그 실행을 그때 그대로 다시 — 단계마다 같음·다름
```

```python
import equion as eqn
p = eqn.project(".")
r = p.hs("main")              # 과거 재현(HS) — [hs]의 구간·방식(풀기만 — 기록은 남기지 않는다)
r.statistics()
p.hs("demand")                # 블록 HS — 수요 블록만 풀고 나머지 변수는 실측
h = p.hs("main", record=True) # 기록 hs:hs_0001을 남긴다 — 명령줄 equion hs main과 같다
```

| 위치 | 내용 |
|---|---|
| `equion.toml` | 자료 정의·블록·모형 조립·HS 기본값 |
| `DATA/raw/` | 원자료 — 받은 그대로(고치지 않는다) |
| `DATA/series.toml` · `DATA/derived.txt` | 자료 정의 — 어느 열을 어떻게 읽어 어떤 시리즈로 · 파생 시리즈 |
| `EQUATIONS/` | 블록 — 방정식 파일 하나가 블록 하나(한 줄에 한 식) |
| `FLOWS/` | 스크립트(`.eqs`) — 한 줄이 equion 명령 하나, 원자료에서 보고서까지의 순서 |
| `DATA/raw/inbox/` | 받은 원자료를 놓는 곳 — `data build --inbox ask`가 출처와 짝지어 넣는다 |
| `notes/` · `reports/` | 노트(명령 블록 + 결과) · 보고서(결과만) |
| `CLAUDE.md` | Claude Code에게 — 먼저 `equion guide`(모형 작업 안내)를 읽는다 |
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
        "FLOWS/monthly.eqs": MONTHLY,
        "notes/data_check.md": NOTE,
        "CLAUDE.md": CLAUDE_MD,
        "README.md": README.format(name=name),
        ".gitignore": GITIGNORE,
    }
    for d in ("DATA/raw", "DATA/raw/inbox", "EQUATIONS", "ASSUMPTIONS", "ADDFACTORS", "SCENARIOS", "FLOWS", "notes"):
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
