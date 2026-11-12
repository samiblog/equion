# 가이드 3. 매달 하는 일

매달 새 원자료가 오면 하는 일입니다. 사람이 하는 일은 **원자료를 넣고, 한 번 돌리고, 표시(`!`)된 곳을 보고, 글을 고치는 것**뿐이고,
나머지 순서는 스크립트(`FLOWS/monthly.eqs`)가 정합니다. 예제 프로젝트로 두 달을 돌려 봅니다.

```console
$ equion new monthly --template desk
$ cd monthly
```
<!-- out -->
```text
$ equion new monthly --template desk
새 프로젝트 monthly:
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
  cd monthly
  equion assemble main

$ cd monthly
```

## 1. 새 원자료를 받은 상자에

통계표 파일을 `DATA/raw/inbox/`에 끌어다 놓습니다. 여기서는 예제 자료에 2020년 1분기를 더하고 2019년 4분기 투자를 조금 고친 표를 씁니다.

```python
import pandas as pd

df = pd.read_csv("DATA/raw/toy_q.csv", index_col=0)
df.loc["2020Q1"] = df.loc["2019Q4"] * 1.006       # 새 분기
df.loc["2019Q4", "I"] *= 0.996                    # 지난 분기 개정
df.to_csv("DATA/raw/inbox/toy_q_2020Q1.csv")
```

넣기 전에 봅니다 — 어느 출처를 바꾸는지(파일 이름으로 짝짓기), 그 출처의 불러오기 틀로 읽히는지(틀 검사). 넣기는 스크립트의 첫 단계가 합니다.

```console
$ equion data inbox
$ equion check FLOWS/monthly.eqs
```
<!-- out -->
```text
$ equion data inbox
[data inbox] 받은 원자료 1 — DATA/raw/inbox/
  toy_q_2020Q1.csv → [source.na] (이름이 toy_q.csv와 같은 앞부분) · 틀 검사 통과
  넣기   스크립트의 자료 단계(예: equion run FLOWS/monthly.eqs) — 따로 넣으려면 equion data build --inbox ask --use

$ equion check FLOWS/monthly.eqs
[check] FLOWS/monthly.eqs: 단계 11 · 문제 없음
  파일을 바꾸는 단계 1, 3, 7, 8, 9, 10, 11
```

## 2. 한 번 돌리기

```console
$ equion run FLOWS/monthly.eqs
```
<!-- out -->
```text
$ equion run FLOWS/monthly.eqs
[1/11] data build --inbox ask --use                 ✓ [data build] 새 회차 d2026-11b
[2/11] assemble main                                ✓ [assemble main] 수요 + 물가 + 금융 — 블록 3 · 추정식 5 · 항등식 1
[3/11] est main --adopted --adopt if_pass           ! 기준 미달 demand:CN · 기준 미달 finance:RL · 기준 미달 finance:M2 — [est --adopted] main · 정책 if_pass…
[4/11] hs main                                      ✓ [hs:hs_0001] main dynamic 2005Q1~2020Q1 · 정상 61 · 일부식 제외 0 · 실패대체 0 · 실패 0
[5/11] expect hs Y.rmspe < 3% --flag                ✓ Y RMSPE 0.4786 — Y.rmspe < 3
[6/11] sim base oil20 --model main                  ✓ [sim:2026-11_base] main · base · 2020Q2~2022Q1 dynamic · 정상 8 · 일부식 제외 0 · 실패대체 0 · 실패 0
[7/11] note run notes/data_check.md                 ✓ [note run] notes/data_check.md: 블록 2
[8/11] report new reports/forecast_d2026-11b.md --title "월간 전망 — 자료 d2026-11b" --exist-ok ✓ [report new] reports/forecast_d2026-11b.md
[9/11] report add reports/forecast_d2026-11b.md sim:2026-11_base --key growth --rows Y,CN,I,P --show yoy --annual --title "성장률 전망" ✓ [report add] reports/forecast_d2026-11b.md
[10/11] report add reports/forecast_d2026-11b.md hs:hs_0001 --key hs --rows Y,CN --chart --title "과거 재현" ✓ [report add] reports/forecast_d2026-11b.md
[11/11] export hs:hs_0001 sim:2026-11_base sim:2026-11_oil20 --xlsx exports/forecast_d2026-11b.xlsx ✓ [export] exports/forecast_d2026-11b.xlsx — 기록 3 · 시트 15: 출처, hs_0001_적합도, hs_0001_해, hs_0…
기록  run:monthly_0001 · 단계 11 · 표시 1 · 종료 코드 0 · 자료 회차 d2026-11a → d2026-11b
```

단계마다 `✓` 정상 · `!` 사람이 볼 것 · `×` 멈춤. 끝 줄에 실행 기록 이름과 자료 회차가 어떻게 바뀌었는지 나옵니다. 단계를 다시 보려면:

```console
$ equion work show run:monthly_0001
```
<!-- out -->
```text
$ equion work show run:monthly_0001
[run:monthly_0001] FLOWS/monthly.eqs · 표시 · 종료 코드 0 · 자료 회차 d2026-11a → d2026-11b
  매개변수  scenarios = base oil20
  [1] ✓ data build --inbox ask --use  → data:d2026-11b
  [2] ✓ assemble main
  [3] ! est main --adopted --adopt if_pass  — 기준 미달 demand:CN · 기준 미달 finance:RL · 기준 미달 finance:M2 — [est --adopted] main · 정책 if_pass: 식 5 — 새 계수 채택 2 · 기준 미달 3  → est:cn_0001 · est:i_0001 · est:p_0001 외 2
  [4] ✓ hs main  → hs:hs_0001
  [5] ✓ expect hs Y.rmspe < 3% --flag  — Y RMSPE 0.4786 — Y.rmspe < 3
  [6] ✓ sim base oil20 --model main  → sim:2026-11_base · sim:2026-11_oil20
  [7] ✓ note run notes/data_check.md  → an:summary_0001
  [8] ✓ report new reports/forecast_d2026-11b.md --title "월간 전망 — 자료 d2026-11b" --exist-ok
  [9] ✓ report add reports/forecast_d2026-11b.md sim:2026-11_base --key growth --rows Y,CN,I,P --show yoy --annual --title "성장률 전망"
  [10] ✓ report add reports/forecast_d2026-11b.md hs:hs_0001 --key hs --rows Y,CN --chart --title "과거 재현"
  [11] ✓ export hs:hs_0001 sim:2026-11_base sim:2026-11_oil20 --xlsx exports/forecast_d2026-11b.xlsx
  카드   work/run/monthly_0001/summary.md
```

## 3. 자료 점검 — 무엇이 바뀌었나

새 기간과 개정, 그 개정이 닿는 식, 개정이 한 시리즈에만 와서 항등식이 어긋나지 않는지 봅니다(스크립트의 자료 점검 노트도 항등식을 봅니다).

```console
$ equion data diff
$ equion data impact
$ equion ident demand:Y --check --range last-7:last
```
<!-- out -->
```text
$ equion data diff
[data diff d2026-11a → d2026-11b]
  구간   1970Q1~2019Q4 → 1970Q1~2020Q1
  바뀐 시리즈 12
    CN       새 값 1기
    I        개정 1기(2019Q4~2019Q4) 최대 0.4% · 새 값 1기
    G        새 값 1기
    Y        새 값 1기
    R        새 값 1기
    RL       새 값 1기
    P        새 값 1기
    POIL     새 값 1기
    M2       새 값 1기
    CNSA     개정 41기(2009Q3~2019Q4) 최대 1.05% · 새 값 1기
    PI       새 값 1기
    RR       새 값 1기
  그대로 1

$ equion data impact
[data impact d2026-11a → d2026-11b]
  바뀐 시리즈 12 · 새 0 · 없어진 0
  쓰는 식   demand:CN (CN·Y) · demand:I (I·R·Y) · demand:Y (CN·G·I·Y) · price:P (P·POIL·Y) · finance:RL (R·RL) · finance:M2 (M2·P·RL·Y)
  쓰는 모형  core · main · main_fixrl
  다시 할 일  그 회차로 바꾼 뒤 모형을 다시 추정·풀면 새 자료로 계산된다(저절로 하지 않는다)

$ equion ident demand:Y --check --range last-7:last
[ident demand:Y] Y = CN + I + G   (EQUATIONS/demand.txt:4)
  구간   2018Q2~2020Q1 · 비교 8기
  결과   어긋남 1기 · 최대 |차이| 0.379094 · 최대 |차이%| 0.06059%
  어긋난 기간  2019Q4
```

투자(`I`)만 개정되고 국민소득(`Y`)은 그대로라 2019Q4에서 항등식이 조금 어긋납니다 — 이런 것은 계산을 고치지 말고 원자료를 낸 곳에 확인합니다.

## 4. 둘째 달 — 지난달과 견주기

다음 달 파일(`toy_q_2020Q2.csv`)이 왔습니다. 이름 끝의 기간이 바뀌어도 같은 출처로 짝짓습니다.

```python
df = pd.read_csv("DATA/raw/toy_q_2020Q1.csv", index_col=0)
df.loc["2020Q2"] = df.loc["2020Q1"] * 1.005
df.to_csv("DATA/raw/inbox/toy_q_2020Q2.csv")
```

```console
$ equion run FLOWS/monthly.eqs -q
$ equion work list --kind hs
$ equion compare hs:hs_0001 hs:hs_0002
```
<!-- out -->
```text
$ equion run FLOWS/monthly.eqs -q
기록  run:monthly_0002 · 단계 11 · 표시 1 · 종료 코드 0 · 자료 회차 d2026-11b → d2026-11c

$ equion work list --kind hs
[work list] monthly: 기록 2 (최근 30)
  hs:hs_0001         2026-11-13T05:16 스크립트   main 2005Q1~2020Q1 · Y 0.48% · CN 0.51% · I 0.86%   회차 다름(d2026-11b)
  hs:hs_0002         2026-11-13T05:16 스크립트   main 2005Q1~2020Q2 · Y 0.49% · CN 0.53% · I 0.85%

$ equion compare hs:hs_0001 hs:hs_0002
[compare] 과거 재현 기록 2
       hs:hs_0001 hs:hs_0002
RMSPE%
Y          0.4786     0.4853
CN         0.5142     0.5267
I          0.8593     0.8545
P           1.420      1.398
M2          2.246      2.242
RL          9.773      9.851
  ! 구간이 다릅니다: 2005Q1~2020Q1 · 2005Q1~2020Q2
```

`-q`는 끝 줄만 보입니다. 과거 재현의 적합도를 지난달(`hs:hs_0001`)과 견줬습니다. 보고서는 회차마다 따로 생깁니다(`reports/forecast_<회차>.md`) —
같은 회차로 다시 돌려도 보고서의 글은 그대로이고, 숫자 구역만 그 자리에서 새 기록으로 바뀝니다.

## 5. 그때 그대로 다시

지난달 결과를 누가 물으면 그 실행을 다시 돌려 봅니다. 그 사이 원자료·정의·채택이 바뀌었어도 그때의 사본으로 돕니다.

```console
$ equion run --replay run:monthly_0001 -q
```
<!-- out -->
```text
$ equion run --replay run:monthly_0001 -q
[run --replay] run:monthly_0001 — 단계 11 · 모두 같음
  [1] = data build --inbox ask --use  — 숫자 같음 — data:d2026-11b
  [2] = assemble main  — 기록 없음 — 상태 같음
  [3] = est main --adopted --adopt if_pass  — 숫자 같음 — est:cn_0001 · est:i_0001 · est:p_0001 …
  [4] = hs main  — 숫자 같음 — hs:hs_0001
  [5] = expect hs Y.rmspe < 3% --flag  — Y RMSPE 0.4786 — Y.rmspe < 3
  [6] = sim base oil20 --model main  — 숫자 같음 — sim:2026-11_base · sim:2026-11_oil20
  [7] = note run notes/data_check.md  — 숫자 같음 — an:summary_0001
  [8] = report new reports/forecast_d2026-11b.md --title "월간 전망 — 자료 d2026-11b" --exist-ok  — 기록 없음 — 상태 같음
  [9] = report add reports/forecast_d2026-11b.md sim:2026-11_base --key growth --rows Y,CN,I,P --show yoy --annual --title "성장률 전망"  — 기록 없음 — 상태 같음
  [10] = report add reports/forecast_d2026-11b.md hs:hs_0001 --key hs --rows Y,CN --chart --title "과거 재현"  — 기록 없음 — 상태 같음
  [11] = export hs:hs_0001 sim:2026-11_base sim:2026-11_oil20 --xlsx exports/forecast_d2026-11b.xlsx  — 기록 없음 — 상태 같음
기록  run:monthly_0003 · 종료 코드 0
```

## 6. 이달을 확정하고 남기기 — 이정표 · 묶어 보내기

전망을 확정했으면 **이정표**를 만들어 둡니다(정의 파일 사본 · 자료 회차 · 고정한 기록 — `work/milestones/<이름>/`). 나중에 `milestone show`로 지금과
견주고, `milestone restore`로 정의를 그때로 되돌립니다(바뀜 기록에 남는다). 다른 PC로 옮길 때는 **묶어 보내기** — 정의·노트·보고서·지금 자료
회차·남길 기록을 zip 하나로(원자료는 `--raw`일 때만), 받는 쪽은 `equion bundle open 묶음.zip 폴더`.

```console
$ equion milestone make fc_2026_11 --note "11월 전망 확정"
$ equion bundle make
```
<!-- out -->
```text
$ equion milestone make fc_2026_11 --note "11월 전망 확정"
[milestone] fc_2026_11 — 11월 전망 확정
  만든 때 2026-11-13T05:16:24 · terminal
  자료 회차 d2026-11c · 정의 파일 11 · 고정한 기록 0
  폴더   work/milestones/fc_2026_11

$ equion bundle make
[bundle make] exports/monthly_2026-11-13.zip — 파일 138 · 242KB
  자료 회차 d2026-11c · 기록 18 · 원자료 넣지 않음
  기록이 쓰는 회차  d2026-11b
  뺀 것   원자료 DATA/raw/ — 받은 쪽은 지금 자료 회차로 이어 한다(자료를 다시 만들려면 원자료를 따로 넣는다)
  뺀 것   기록 — 남길 것만(모두 21개 가운데 18개)
  뺀 것   바뀜 기록 work/history · Desk 화면 상태 — 그 PC의 것
  받은 쪽  equion bundle open 묶음.zip 폴더
```

## 표시(`!`)가 떴을 때

| 표시 | 뜻 | 할 일 |
|---|---|---|
| `est … ! 기준 미달 demand:CN` | 판단 기준에 걸린 식 — 옛 채택 계수를 쓴다(없으면 이번 추정 계수) | [4. 식 고르기](04-equations.md)로 후보를 찾고 채택 |
| `hs … ! … 실패 대체` | 풀리지 않은 기간이 있어 실측으로 대신했다 | 그 기간·식을 본다(`work show hs:…`) |
| `expect … ! 어긋남` | 스크립트의 확인 조건(`expect … --flag`)에 걸렸다 | 조건이 맞는지, 결과가 이상한지 본다 |
| 1단계 `×` 받은 원자료를 넣지 못했습니다 | 짝이 없거나 틀이 맞지 않는 파일 — 아무것도 넣지 않았다 | `equion data inbox`로 까닭을 보고 고친다([8. 막혔을 때](08-troubleshooting.md)) |

식을 고친 뒤에는 처음부터 다시 돌릴 필요 없이 `equion run FLOWS/monthly.eqs --from "과거 재현"`.

## 확인할 것

- [ ] 받은 상자의 파일이 출처와 짝지어지고 틀 검사를 통과한다(`data inbox`)
- [ ] 한 번 돌리면 새 회차·다시 추정·HS·전망·노트·보고서·엑셀이 생긴다
- [ ] 둘째 달 파일(이름 끝 기간이 다른)도 짝지어진다
- [ ] `data diff`가 새 기간과 개정을, `ident --check`가 어긋난 기간을 보인다
- [ ] 같은 회차로 다시 돌려도 보고서에 쓴 글이 남는다
- [ ] `--replay`가 '모두 같음'
- [ ] 이정표가 `milestone list`에 보이고, 묶음(`exports/*.zip`)을 다른 폴더에 `bundle open`으로 풀면 같은 회차로 이어 할 수 있다

다음: [4. 식 고르기](04-equations.md) · [9. 자동으로 돌리기](09-automation.md)
