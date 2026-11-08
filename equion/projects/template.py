#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""예제 프로젝트(`equion new 폴더 --template desk`) — 가상 분기 모형, 자료는 예제 자료 toy_q.

    폴더/
      equion.toml          자료 파일·블록·모형 조립·HS 기본값
      DATA/data.csv        toy_q(1970Q1~2019Q4, 가상 자료)
      EQUATIONS/demand.txt 수요 블록 — 소비·투자·국민소득 항등식
      EQUATIONS/price.txt  물가 블록
      EQUATIONS/finance.txt 금융 블록 — 장기금리(1980Q1부터)·통화
      README.md · .gitignore
"""

import os
import shutil

CONFIG = """\
# Equion 프로젝트 — 예제(가상 분기 모형). 형식: docs/reference/formats.md "프로젝트"
[project]
name = "{name}"
format = "equion-project"
format_version = 1

[data]
file = "DATA/data.csv"            # 첫 열이 날짜인 자료 파일(예제 자료 toy_q)

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

[hs]                              # 과거 재현(HS) 기본값
model = "main"
range = "2005Q1:2019Q4"
mode = "dynamic"
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

Equion 프로젝트(예제 — 가상 분기 모형, 자료는 예제 자료 toy_q)입니다. `equion.toml`이 자료 파일과 블록(방정식 파일)을
이름으로 묶고, 모형은 블록과 다른 모형을 끼워 조립합니다.

```bash
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
| `equion.toml` | 자료 파일·블록·모형 조립·HS 기본값 |
| `DATA/` | 자료 파일(첫 열이 날짜) |
| `EQUATIONS/` | 블록 — 방정식 파일 하나가 블록 하나(한 줄에 한 식) |
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
    """예제 프로젝트를 만들고 만든 파일 목록(상대 경로)을 돌려준다."""
    from ..datasets import path as dataset_path
    if os.path.exists(path) and os.listdir(path) and not force:
        raise FileExistsError(f"폴더가 비어 있지 않습니다: {path} (덮어쓰려면 --force)")
    name = os.path.basename(os.path.abspath(path))
    files = {
        "equion.toml": CONFIG.format(name=name),
        "EQUATIONS/demand.txt": DEMAND,
        "EQUATIONS/price.txt": PRICE,
        "EQUATIONS/finance.txt": FINANCE,
        "README.md": README.format(name=name),
        ".gitignore": GITIGNORE,
    }
    for d in ("DATA", "EQUATIONS"):
        os.makedirs(os.path.join(path, d), exist_ok=True)
    created = []
    for rel, text in files.items():
        with open(os.path.join(path, rel), "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        created.append(rel)
    shutil.copyfile(dataset_path("toy_q"), os.path.join(path, "DATA", "data.csv"))
    created.append("DATA/data.csv")
    return created
