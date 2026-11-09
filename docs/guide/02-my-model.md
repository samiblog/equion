# 가이드 2. 내 모형을 프로젝트로

자기 원자료(엑셀)와 방정식이 있는 사람이 프로젝트를 만드는 길입니다. 예제 프로젝트를 틀로 쓰고 하나씩 내 것으로 바꿉니다 —
원자료 넣기 → 불러오기 틀(`DATA/series.toml`) → 블록(방정식 파일) → 모형 조립(`equion.toml`) → 첫 회차 → 추정·과거 재현 → 내 월간 스크립트.

여기서는 '내 원자료'로 이런 엑셀을 씁니다(예제 자료를 바꿔 만든 가상 자료). 첫 줄은 제목, 둘째 줄이 열 이름, 셋째 줄이 단위이고, 시점은
`1970년 1/4분기` 꼴, 빈 칸 하나가 `-`로 적혀 있습니다 — 흔한 통계표 모양입니다.

```python
import pandas as pd
from openpyxl import Workbook
import equion as eqn

q = eqn.datasets.load("toy_q")[["CN", "I", "G", "Y", "R"]]
wb = Workbook()
ws = wb.active
ws.title = "분기"
ws.append(["분기 국민계정(가상)"])
ws.append(["시점", "민간소비", "설비투자", "정부지출", "국내총생산", "기준금리"])
ws.append(["", "조원", "조원", "조원", "조원", "%"])
for p, row in zip(pd.PeriodIndex(q.index, freq="Q"), q.itertuples(index=False)):
    ws.append([f"{p.year}년 {p.quarter}/4분기", *[round(float(v), 3) for v in row]])
ws["C11"] = "-"                                   # 빈 칸(결측) 하나
wb.save("국민계정_2019Q4.xlsx")
```

## 1. 틀이 될 프로젝트와 원자료

```console
$ equion new mine --template desk
$ cd mine
$ equion data add ../국민계정_2019Q4.xlsx
```
<!-- out -->
```text
$ equion new mine --template desk
새 프로젝트 mine:
  equion.toml
  DATA/series.toml
  DATA/derived.txt
  EQUATIONS/demand.txt
  EQUATIONS/price.txt
  EQUATIONS/finance.txt
  ADDFACTORS/base.toml
  SCENARIOS/oil20.toml
  FLOWS/monthly.eqs
  notes/data_check.md
  CLAUDE.md
  README.md
  .gitignore
  DATA/raw/toy_q.csv
  DATA/raw/toy_m.csv
  ASSUMPTIONS/base.csv
자료 회차 d2026-11a를 만들어 지금 회차로 정했습니다(work/data/d2026-11a/)

다음:
  cd mine
  equion assemble main

$ cd mine
$ equion data add ../국민계정_2019Q4.xlsx
[data add] DATA/raw/국민계정_2019Q4.xlsx
  해시   46d1ca9e40252137…
```

`data add`는 파일을 `DATA/raw/`에 **받은 그대로** 복사하고 해시를 적습니다(원자료는 고치지 않는다).

## 2. 불러오기 틀과 시리즈 — `DATA/series.toml`

어느 원자료의 어느 열을 어떻게 읽어 어떤 이름의 시리즈로 만들지 적습니다. 시리즈 이름은 영문(식에 쓴다), 한글은 원자료의 열 이름과 `desc`에.
편집기로 `DATA/series.toml`을 이렇게 바꿉니다(아래 Python은 편집기 대신 같은 내용을 씁니다).

```python
from pathlib import Path

Path("DATA/series.toml").write_text('''\
[source.na]                       # 불러오기 틀 — 원자료 파일 하나를 어떻게 읽나
file = "DATA/raw/국민계정_2019Q4.xlsx"
sheet = "분기"
header_row = 2                    # 열 이름 줄
unit_row = 3                      # 단위 줄
missing = ["-"]                   # 결측 표시

[series.CN]
from = "na:민간소비"               # 원자료:열 이름
desc = "민간소비"

[series.I]
from = "na:설비투자"
fill = "linear"                   # 안쪽 빈 칸은 선형으로 채운다(알아서 한 것에 적힌다)
desc = "설비투자"

[series.G]
from = "na:정부지출"

[series.Y]
from = "na:국내총생산"

[series.R]
from = "na:기준금리"
''', encoding="utf-8")
Path("DATA/derived.txt").write_text("# 파생 시리즈 — 한 줄에 '이름 = 식'\n", encoding="utf-8")
```

## 3. 블록 — 방정식 파일

블록은 방정식 파일 하나입니다. 한 줄에 한 식, `#` 뒤는 설명. 추정식은 `목표 c 설명변수…`, 항등식은 `=`.

```python
Path("EQUATIONS/demand.txt").write_text('''\
# 수요 블록 — 내 모형
CN c Y CN(-1)                     # 민간소비
I c Y(-1) R                       # 설비투자
Y = CN + I + G                    # 국내총생산(항등식)
''', encoding="utf-8")
```

새 원자료로 회차를 만들어 지금 회차로 바꾸고 조립을 검사합니다.

<!-- error -->
```console
$ equion data build --use
$ equion assemble main
```
<!-- out -->
```text
$ equion data build --use
[data build] 새 회차 d2026-11b
  시리즈 5 · 1970Q1~2019Q4
  알아서 한 것
    - na: 시점 열 A('1970년 1/4분기' 꼴) → Q 1970Q1~2019Q4
    - na: 결측 표시로 본 칸 1개 (예: C11 '-')
    - I: 안쪽 결측 1칸을 선형으로 채움 (1971Q4부터)
  지금 회차 d2026-11b

$ equion assemble main
[assemble main] 수요 + 물가 + 금융 — 블록 3 · 추정식 5 · 항등식 1
  조립   main = core(demand) + price + finance
  내생 6  CN · I · Y · P · RL · M2
  외생 3  G(~2019Q4) · POIL(자료 없음) · R(~2019Q4)
  연결   demand →Y→ price · price →P→ finance · demand →Y→ finance
  문제 1
    - 모르는 변수 POIL — 자료에도 없고 어떤 식도 정하지 않습니다(쓰는 식: price:P)
(종료 코드 3)
```

틀이 맞았습니다 — '알아서 한 것'에 시점 꼴, 결측으로 본 칸(`C11 '-'`), 채운 칸이 적혀 있습니다. 조립은 문제가 하나입니다. 예제의 모형 `main`이
아직 물가·금융 블록을 끼우고 있어 내 자료에 없는 유가(`POIL`)를 찾기 때문입니다. **실행 전에 이렇게 잡히는 것**이 조립 검사의 일입니다.

## 4. 모형 조립 — `equion.toml`

`equion.toml`에서 쓰지 않을 블록과 모형을 지우고 `main`이 수요 블록만 끼우게 합니다.

```python
cfg = Path("equion.toml").read_text(encoding="utf-8")
cfg = cfg.replace('price   = { file = "EQUATIONS/price.txt",   desc = "물가" }\n', "")
cfg = cfg.replace('finance = { file = "EQUATIONS/finance.txt", desc = "금융" }\n', "")
cfg = cfg.replace('desc = "수요 + 물가 + 금융"\ninclude = ["core"]                # 모형 안에 모형\nblocks = ["price", "finance"]\n',
                  'desc = "내 모형 — 수요"\ninclude = ["core"]\n')
cfg = cfg.split("[model.main_fixrl]")[0] + "[group]" + cfg.split("[group]")[1]
Path("equion.toml").write_text(cfg, encoding="utf-8")
for f in ("EQUATIONS/price.txt", "EQUATIONS/finance.txt", "SCENARIOS/oil20.toml", "FLOWS/monthly.eqs"):
    Path(f).unlink()                              # 예제의 것 — 내 모형에는 쓰지 않는다
```

```console
$ equion assemble main
$ equion est demand:I
$ equion hs main
```
<!-- out -->
```text
$ equion assemble main
[assemble main] 내 모형 — 수요 — 블록 1 · 추정식 2 · 항등식 1
  조립   main = core(demand)
  내생 3  CN · I · Y
  외생 2  G(~2019Q4) · R(~2019Q4)
  풀이   블록 2 (동시 CN·Y)
  문제   없음

$ equion est demand:I
[est:i_0001] OLS I · 1970Q2~2019Q4 · n=199   R²adj 0.9985 · SE 0.6105 · DW 1.930 · AIC 371.3 · BIC 381.2
  계수   c 4.529(t 9.210) · Y(-1) 0.1507(t 205.5) · R -0.9639(t -24.174)
  진단   LM(2) p=0.382 ✓ · White p=0.202 ✓ · JB p=0.947 ✓ · RESET p=0.716 ✓ · LB(4) p=0.434 ✓
  기준   통과 · 부호 R - ✓
  알아서 한 것  시차·결측으로 표본 시작 1970Q1 → 1970Q2
  기록   est:i_0001 (work/est/i_0001/) · demand:I 후보

$ equion hs main
[hs:hs_0001] main dynamic 2005Q1~2019Q4 · 정상 60 · 일부식 제외 0 · 실패대체 0 · 실패 0
  RMSPE  Y 0.48% · CN 0.51% · I 0.86%
  알아서 한 것  구간 [hs] range = 2005Q1:last → 2005Q1~2019Q4 · 채택 기록 없이 지금 자료로 추정: demand:CN, demand:I
  기록   hs:hs_0001 (work/hs/hs_0001/)
```

`equion.toml`의 다른 표 — 판단 기준 `[criteria]`(기대 부호·진단), 과거 재현 `[hs]`(구간 `2005Q1:last`), 전망 `[forecast]`(구간 `next:8`·가정
세트) — 는 예제의 것을 그대로 썼습니다. 내 모형에 맞게 고치면 다음 명령부터 그대로 씁니다.

## 5. 내 월간 스크립트

한 줄이 명령 하나인 스크립트를 씁니다. 다음 달에는 새 엑셀(`국민계정_2020Q1.xlsx`)을 `DATA/raw/inbox/`에 놓고 이것 하나를 돌리면 됩니다 —
파일 이름 끝의 기간(`_2020Q1`)을 빼고 `국민계정`으로 출처를 짝짓습니다.

```python
Path("FLOWS/mine.eqs").write_text('''\
# 내 모형 — 월간
param scenarios = base

## 자료
data build --inbox ask --use
assemble main

## 추정
est main --adopted --adopt if_pass

## 과거 재현
hs main
expect hs Y.rmspe < 5% --flag

## 전망
sim {scenarios} --model main
report new reports/mine_{vintage}.md --title "내 모형 전망 — {vintage}" --exist-ok
report add reports/mine_{vintage}.md {sim:base} --key growth --rows Y,CN,I --show yoy --annual --title "성장률"
''', encoding="utf-8")
```

```console
$ equion check FLOWS/mine.eqs
$ equion run FLOWS/mine.eqs
```
<!-- out -->
```text
$ equion check FLOWS/mine.eqs
[check] FLOWS/mine.eqs: 단계 8 · 문제 없음
  파일을 바꾸는 단계 1, 3, 7, 8

$ equion run FLOWS/mine.eqs
[1/8] data build --inbox ask --use                 ✓ [data build] 바뀐 것 없음 — 회차 d2026-11b와 내용이 같습니다(새로 만들지 않음)
[2/8] assemble main                                ✓ [assemble main] 내 모형 — 수요 — 블록 1 · 추정식 2 · 항등식 1
[3/8] est main --adopted --adopt if_pass           ! 기준 미달 demand:CN — [est --adopted] main · 정책 if_pass: 식 2 — 새 계수 채택 1 · 기준 미달 1
[4/8] hs main                                      ✓ [hs:hs_0002] main dynamic 2005Q1~2019Q4 · 정상 60 · 일부식 제외 0 · 실패대체 0 · 실패 0
[5/8] expect hs Y.rmspe < 5% --flag                ✓ Y RMSPE 0.4751 — Y.rmspe < 5
[6/8] sim base --model main                        ✓ [sim:2026-11_base] main · base · 2020Q1~2021Q4 dynamic · 정상 8 · 일부식 제외 0 · 실패대체 0 · 실패 0
[7/8] report new reports/mine_d2026-11b.md --title "내 모형 전망 — d2026-11b" --exist-ok ✓ [report new] reports/mine_d2026-11b.md
[8/8] report add reports/mine_d2026-11b.md sim:2026-11_base --key growth --rows Y,CN,I --show yoy --annual --title "성장률" ✓ [report add] reports/mine_d2026-11b.md
기록  run:mine_0001 · 단계 8 · 표시 1 · 종료 코드 0
```

## 확인할 것

- [ ] 내 엑셀(제목 줄·단위 줄·`1970년 1/4분기`·`-`)이 틀 그대로 읽히고, 결측·채움이 '알아서 한 것'에 적힌다
- [ ] 열 이름을 틀리게 적으면(`na:민간소비지출`) `data build`가 그 칸과 함께 알린다
- [ ] 모형에서 블록을 빼기 전에는 `assemble`이 모르는 변수를 잡는다(종료 코드 3)
- [ ] 내 스크립트가 `check`를 통과하고 끝까지 돈다
- [ ] 다음 달 파일을 받은 상자에 넣고 `equion data inbox`가 출처 `na`로 짝짓는다

다음: [3. 매달 하는 일](03-monthly.md) · 형식 전체는 [파일 형식 — 자료 정의](../reference/formats.md#자료-정의seriestomlderivedtxt와-자료-회차workdata)
