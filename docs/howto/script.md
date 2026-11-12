# 레시피 — 스크립트·재연

원자료에서 보고서까지를 Equion 스크립트(`.eqs` — 한 줄이 `equion` 명령 하나) 하나로 적어 두면, 새 자료가 올 때마다 **원자료를 넣고 한 번 돌리면**
같은 일이 같은 차례로 다시 됩니다. 문법은 [파일 형식 — 스크립트](../reference/formats.md#스크립트flowseqs와-실행-기록workrun),
명령은 [명령줄 — 스크립트](../reference/cli.md#스크립트--run-xeqs--run---replay--check-xeqs--script). 예제는 위에서부터 이어서 돕니다.

## R56 자료만 넣고 스크립트 한 번

예제 프로젝트에는 월간 스크립트 `FLOWS/monthly.eqs`가 들어 있습니다(자료 → 조립 검사 → 다시 추정 → 과거 재현 → 전망 → 노트·보고서·엑셀).
새 원자료는 `DATA/raw/inbox/`에 놓습니다 — 어느 출처를 바꾸는지는 파일 이름으로 짝짓고(또는 `series.toml`의 `[source.이름] inbox = "글롭"`),
그 출처의 불러오기 틀로 읽어 봅니다. 여기서는 예제 자료 toy_q에 한 분기를 더한 합성 표를 '이번 달 원자료'로 씁니다.

```python
from pathlib import Path

import pandas as pd
import equion as eqn

p = eqn.Project.create("monthly_prj", force=True)
df = pd.read_csv(Path(p.root, "DATA/raw/toy_q.csv"), index_col=0)
df.loc["2020Q1"] = df.iloc[-1] * 1.01                      # 새 분기(합성)
df.to_csv(Path(p.root, "DATA/raw/inbox/toy_q_2020Q1.csv"))
for item in p.data_inbox():                                 # 미리보기 — equion data inbox
    print(item.text())
```
<!-- out -->
```text
[monthly_prj] 자료 회차 d2026-11a를 만들었습니다
[monthly_prj] 지금 자료 회차: d2026-11a
toy_q_2020Q1.csv → [source.na] (이름이 toy_q.csv와 같은 앞부분) · 틀 검사 통과
```

돌리기 전에 미리 봅니다 — 단계마다 실행할 줄과 바꾸는 파일, 실행 때 정해지는 값(`{vintage}` — 첫 단계가 회차를 바꾼다, `{hs}` — 앞 단계의 기록).
기록은 남지 않습니다(`equion run FLOWS/monthly.eqs --dry-run`).

```python
plan = p.run_script("FLOWS/monthly.eqs", dry_run=True)
print("\n".join(plan.text().splitlines()[:12]))
```
<!-- out -->
```text
[monthly_prj] 열기 series.csv — 분기(Quarterly) 1970Q1~2019Q4 · 시리즈 13
[미리보기] FLOWS/monthly.eqs — 월간 전망 — 새 원자료로 회차·다시 추정·과거 재현·전망·보고서까지 · 단계 11 · 기록을 남기지 않습니다
  매개변수  scenarios = base oil20
  ## 자료
  [1] data build --inbox ask --use
       바꾸는 것  DATA/raw/(받은 원자료), DATA/series.toml, equion.toml [data] vintage
  [2] assemble main
  ## 추정
  [3] est main --adopted --adopt if_pass
       바꾸는 것  EQUATIONS/adopted.toml
  ## 과거 재현
  [4] hs main
  [5] 확인 expect hs Y.rmspe < 3% --flag
```

실행합니다(`equion run FLOWS/monthly.eqs`). 단계마다 한 줄 — `✓` 정상, `!` 사람이 볼 것(여기서는 판단 기준을 통과하지 못한 식 — 정책
`if_pass`대로 옛 계수를 쓰고 계속), `×`이면 거기서 멈춥니다.

```python
r = p.run_script("FLOWS/monthly.eqs", echo=print)
print(r.text())
```
<!-- out -->
```text
[1/11] data build --inbox ask --use                 ✓ [data build] 새 회차 d2026-11b
[2/11] assemble main                                ✓ [assemble main] 수요 + 물가 + 금융 — 블록 3 · 추정식 5 · 항등식 1
[3/11] est main --adopted --adopt if_pass           ! 기준 미달 demand:CN · 기준 미달 finance:RL · 기준 미달 finance:M2 — [est --adopted] main · 정책 if_pass…
[4/11] hs main                                      ✓ [hs:hs_0001] main dynamic 2005Q1~2020Q1 · 정상 61 · 일부식 제외 0 · 실패대체 0 · 실패 0
[5/11] expect hs Y.rmspe < 3% --flag                ✓ Y RMSPE 0.4879 — Y.rmspe < 3
[6/11] sim base oil20 --model main                  ✓ [sim:2026-11_base] main · base · 2020Q2~2022Q1 dynamic · 정상 8 · 일부식 제외 0 · 실패대체 0 · 실패 0
[7/11] note run notes/data_check.md                 ✓ [note run] notes/data_check.md: 블록 2
[8/11] report new reports/forecast_d2026-11b.md --title "월간 전망 — 자료 d2026-11b" --exist-ok ✓ [report new] reports/forecast_d2026-11b.md
[9/11] report add reports/forecast_d2026-11b.md sim:2026-11_base --key growth --rows Y,CN,I,P --show yoy --annual --title "성장률 전망" ✓ [report add] reports/forecast_d2026-11b.md
[10/11] report add reports/forecast_d2026-11b.md hs:hs_0001 --key hs --rows Y,CN --chart --title "과거 재현" ✓ [report add] reports/forecast_d2026-11b.md
[11/11] export hs:hs_0001 sim:2026-11_base sim:2026-11_oil20 --xlsx exports/forecast_d2026-11b.xlsx ✓ [export] exports/forecast_d2026-11b.xlsx — 기록 3 · 시트 15: 출처, hs_0001_적합도, hs_0001_해, hs_0…
기록  run:monthly_0001 · 단계 11 · 표시 1 · 종료 코드 0 · 자료 회차 d2026-11a → d2026-11b
```

보고서는 이번 회차의 이름으로 생겼습니다. 같은 회차로 다시 돌려도 보고서의 글은 그대로이고(`report new --exist-ok`), 구역만 그 자리에서 새 기록으로
바뀝니다(`report add --key`). 손으로 고친 구역은 덮지 않고 멈춥니다.

```python
q = eqn.project("monthly_prj")                              # 회차가 바뀌었으니 다시 연다
text = Path(q.root, "reports", f"forecast_{q.vintage}.md").read_text(encoding="utf-8")
print(text.split("<!-- /equion:report -->")[0].strip())     # 머리와 첫 구역
```
<!-- out -->
```text
# 월간 전망 — 자료 d2026-11b

2026-11-13 · 자료 회차 d2026-11b · 모형 main

## 요약

(글)

## 본문

<!-- equion:report sim:2026-11_base #1 · 2026-11-13 · data:d2026-11b {"rows": ["Y", "CN", "I", "P"], "show": "yoy", "annual": true, "title": "성장률 전망", "n": 1, "key": "growth", "h": "1bfda15172d8"} -->
**표 1. 성장률 전망** (연간 증가율, %)

| 시리즈 | 2020 | 2021 |
|---|---|---|
| Y | 2.1 | 2.1 |
| CN | 2.2 | 2.1 |
| I | 1.3 | 2.3 |
| P | 3.1 | 2.7 |

연간 값 — 2020년은 실측 1기 + 전망 3기

자료: Equion sim:2026-11_base(자료 회차 d2026-11b)
```

## R57 그때 그대로 다시 · 이 단계부터

실행 기록(`work/run/monthly_0001/`)에는 값을 바꿔 넣은 뒤의 스크립트(`script.eqs`), 원래 스크립트(`src/`), 시작할 때의 정의 사본(`defs/`), 단계마다
만든 기록·바뀜 기록, 받은 원자료, 자료 회차와 판이 들어 있습니다. `--replay`는 프로젝트를 임시 폴더에 복사해 그때의 상태로 되돌린 뒤 같은 스크립트를
다시 돌리고 단계마다 숫자를 견줍니다 — 그 사이 정의 파일을 고쳤어도 그때 그대로입니다. 프로젝트는 바뀌지 않습니다.

```python
rp = q.replay_run(r.id)                                     # equion run --replay run:monthly_0001
print(rp.text())
```
<!-- out -->
```text
[run --replay] run:monthly_0001 — 단계 11 · 모두 같음
  [1] = data build --inbox ask --use  — 숫자 같음 — data:d2026-11b
  [2] = assemble main  — 기록 없음 — 상태 같음
  [3] = est main --adopted --adopt if_pass  — 숫자 같음 — est:cn_0001 · est:i_0001 · est:p_0001 …
  [4] = hs main  — 숫자 같음 — hs:hs_0001
  [5] = expect hs Y.rmspe < 3% --flag  — Y RMSPE 0.4879 — Y.rmspe < 3
  [6] = sim base oil20 --model main  — 숫자 같음 — sim:2026-11_base · sim:2026-11_oil20
  [7] = note run notes/data_check.md  — 숫자 같음 — an:summary_0001
  [8] = report new reports/forecast_d2026-11b.md --title "월간 전망 — 자료 d2026-11b" --exist-ok  — 기록 없음 — 상태 같음
  [9] = report add reports/forecast_d2026-11b.md sim:2026-11_base --key growth --rows Y,CN,I,P --show yoy --annual --title "성장률 전망"  — 기록 없음 — 상태 같음
  [10] = report add reports/forecast_d2026-11b.md hs:hs_0001 --key hs --rows Y,CN --chart --title "과거 재현"  — 기록 없음 — 상태 같음
  [11] = export hs:hs_0001 sim:2026-11_base sim:2026-11_oil20 --xlsx exports/forecast_d2026-11b.xlsx  — 기록 없음 — 상태 같음
기록  run:monthly_0002 · 종료 코드 0
```

식을 손본 뒤에는 처음부터 다시 할 필요 없이 그 단계부터 돌립니다(`--from 단계번호` 또는 `--from "## 제목"`). 앞 단계는 '건너뜀'이고, 뒤에서 앞 단계의
기록(`{hs}` 등)이 필요하면 프로젝트의 가장 새 기록을 씁니다(실행 기록의 '알아서 한 것'에 남는다).

```python
r2 = q.run_script("FLOWS/monthly.eqs", sets={"scenarios": "base"}, from_step="전망", echo=print)
print(r2.text())
```
<!-- out -->
```text
[1/11] data build --inbox ask --use                 – --from 6
[2/11] assemble main                                – --from 6
[3/11] est main --adopted --adopt if_pass           – --from 6
[4/11] hs main                                      – --from 6
[5/11] expect hs Y.rmspe < 3% --flag                – --from 6
[6/11] sim base --model main                        ✓ [sim:2026-11_base_2] main · base · 2020Q2~2022Q1 dynamic · 정상 8 · 일부식 제외 0 · 실패대체 0 · 실패 0
[7/11] note run notes/data_check.md                 ✓ [note run] notes/data_check.md: 블록 2
[8/11] report new reports/forecast_d2026-11b.md --title "월간 전망 — 자료 d2026-11b" --exist-ok ✓ [report new] reports/forecast_d2026-11b.md — 이미 있어 그대로 둠
[9/11] report add reports/forecast_d2026-11b.md sim:2026-11_base_2 --key growth --rows Y,CN,I,P --show yoy --annual --title "성장률 전망" ✓ [report add] reports/forecast_d2026-11b.md
[10/11] report add reports/forecast_d2026-11b.md hs:hs_0001 --key hs --rows Y,CN --chart --title "과거 재현" ✓ [report add] reports/forecast_d2026-11b.md
[11/11] export hs:hs_0001 sim:2026-11_base_2 --xlsx exports/forecast_d2026-11b.xlsx ✓ [export] exports/forecast_d2026-11b.xlsx — 기록 2 · 시트 9: 출처, hs_0001_적합도, hs_0001_해, hs_00…
기록  run:monthly_0003 · 단계 6 · 종료 코드 0
  알아서 한 것  {hs} — 건너뛴 단계의 기록 대신 자료 회차 d2026-11b의 가장 새 기록 hs:hs_0001
```

## R58 탐색한 기록으로 스크립트 · Python으로

터미널이나 Claude와 탐색하며 남긴 기록에서 스크립트 초안을 만듭니다(`equion script new 이름 --from-records 기록…`). 기록의 명령이 차례로 들어가고,
`-p`·`--as`·`--json`은 뺍니다(다시 돌려도 이름이 겹치지 않게). 앞 단계가 만든 기록을 가리키려면 `{est}`·`{hs}`로 바꿔 씁니다.

```python
e = q.est("CN c Y CN(-1) CN(-2)", part="demand:CN", as_name="cn_lag2",
          command='equion est "CN c Y CN(-1) CN(-2)" --for demand:CN --as cn_lag2')
h = q.hs("main", record=True, swap={"demand:CN": e.id}, command=f"equion hs main --swap demand:CN={e.id}")
rel = q.new_script("try_lag2", records=[e.id, h.id])
src = Path(q.root, rel).read_text(encoding="utf-8").replace(f"demand:CN={e.id}", "demand:CN={est}")
Path(q.root, rel).write_text(src, encoding="utf-8")         # 이번에 추정한 식으로 바꿔 끼우게
print(src)
print(q.check_script(rel).text())
```
<!-- out -->
```text
[monthly_prj] 열기 series.csv — 분기(Quarterly) 1970Q1~2020Q1 · 시리즈 13
[main] 채택 계수: demand:I(est:i_0001), price:P(est:p_0001)
[main] 채택 기록 없이 지금 자료로 추정: finance:RL, finance:M2
[main] baseline(_0) dynamic 2005Q1~2020Q1: 정상 61 · 일부식 제외 0 · 실패대체 0 · 실패 0
# try_lag2 — equion script new가 만든 초안(2026-11-13) · 고쳐 쓰세요
# 한 줄 = equion 명령 하나 · ## 제목 = 단계 묶음 · param 이름 = 값 · {이름} · expect … --flag(문법: docs/reference/formats.md)

## 추정
est 'CN c Y CN(-1) CN(-2)' --for demand:CN   # ← est:cn_lag2

## 과거 재현
hs main --swap demand:CN={est}   # ← hs:hs_0002

[check] FLOWS/try_lag2.eqs: 단계 2 · 문제 없음
```

반복·조건·직접 계산이 필요하면 같은 일을 하는 Python으로 내보내 고쳐 씁니다(`equion script export FLOWS/try_lag2.eqs --py`). 줄마다 `s.cmd(…)`가 그
명령을 그대로 돌리므로 기록·바뀜 기록·실행 기록이 `.eqs`로 돌린 것과 같습니다.

```python
py = q.export_script(rel)
print(Path(q.root, py).read_text(encoding="utf-8"))
```
<!-- out -->
```text
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FLOWS/try_lag2.eqs를 Python으로 — equion script export --py가 만들었다(2026-11-13).

try_lag2 — equion script new가 만든 초안(2026-11-13) · 고쳐 쓰세요

같은 단계를 같은 차례로 한다: s.cmd(…)는 그 명령 한 줄을 그대로(기록·바뀜 기록도 같다), s.expect(…)는 확인, s.py(…)는 Python
단계. 끝나면 실행 기록 run:…이 남는다. 반복·조건·직접 계산을 더하려면 이 파일을 고쳐 쓴다 — 프로젝트 API는 s.p(eqn.project),
앞 단계의 기록 이름은 s.records("hs") · 기록은 eqn.project(...)의 저장소에서 읽는다.

    python FLOWS/try_lag2.py
"""

import equion as eqn

P = eqn.params()

with eqn.script.session(__file__, params=vars(P), script='FLOWS/try_lag2.eqs') as s:
    s.section('추정')
    s.cmd("est 'CN c Y CN(-1) CN(-2)' --for demand:CN")
    s.section('과거 재현')
    s.cmd('hs main --swap demand:CN={est}')

print(s.result.text())
```

관련: [파일 형식 — 스크립트와 실행 기록](../reference/formats.md#스크립트flowseqs와-실행-기록workrun) · [R52 제안·바뀜 기록·그때 그대로 다시](model.md) ·
[R55 보고서로 보내기](output.md) · [명령줄 레시피](cli.md)
