# 가이드 1. 처음 한 시간

예제 프로젝트 하나로 Equion의 한 바퀴를 돕니다 — 만들기 → 조립 검사 → 식 추정 → 과거 재현 → 전망 → 보고서 → 스크립트 → 그때 그대로 다시.
예제는 가상 분기 모형입니다(소비·투자·국민소득 항등식의 수요 블록, 물가 블록, 금리·통화의 금융 블록).

## 1. 예제 프로젝트 만들기

```console
$ equion new demo --template desk
$ cd demo
```
<!-- out -->
```text
$ equion new demo --template desk
새 프로젝트 demo:
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
  cd demo
  equion assemble main

$ cd demo
```

폴더 하나가 프로젝트입니다. 사람이 쓰는 **정의**(`equion.toml`·`EQUATIONS/`·`DATA/series.toml`·`ASSUMPTIONS/`·`SCENARIOS/`·`FLOWS/`)와,
명령이 덧붙여 쓰는 **기록**(`work/`)으로 나뉩니다. 만들 때 원자료(`DATA/raw/`)를 정의대로 읽어 첫 **자료 회차**를 만들어 두었습니다.

## 2. 조립 검사

모형 `main`은 블록 셋을 끼운 것입니다. 계산 없이 무엇이 내생이고 외생인지, 모르는 변수나 겹친 목표가 없는지 봅니다.

```console
$ equion assemble main
$ equion data list
```
<!-- out -->
```text
$ equion assemble main
[assemble main] 수요 + 물가 + 금융 — 블록 3 · 추정식 5 · 항등식 1
  조립   main = core(demand) + price + finance
  내생 6  CN · I · Y · P · RL · M2
  외생 3  G(~2019Q4) · POIL(~2019Q4) · R(~2019Q4)
  연결   demand →Y→ price · price →P→ finance · demand →Y→ finance
  풀이   블록 5 (동시 CN·Y)
  문제   없음

$ equion data list
[data list] demo: 자료 회차 1
  * d2026-11a    2026-11-09T13:59:01  1970Q1~2019Q4    시리즈 13
```

## 3. 식 하나 추정하기

부품(식 한 줄)은 `블록:목표`로 부릅니다. 추정할 때마다 기록(`est:…`)이 남고, '기준' 줄이 판단 기준(`equion.toml`의 `[criteria]`)을
통과했는지 알려 줍니다.

```console
$ equion est demand:CN
```
<!-- out -->
```text
$ equion est demand:CN
[est:cn_0001] OLS CN · 1970Q2~2019Q4 · n=199   R²adj 0.9999 · SE 0.5029 · DW 1.652 · AIC 294.1 · BIC 304.0
  계수   c 11.647(t 42.990) · Y 0.5869(t 51.970) · CN(-1) 0.1782(t 11.260)
  진단   LM(2) p=0.046 ! · White p=0.485 ✓ · JB p=0.325 ✓ · RESET p=0.484 ✓ · LB(4) p=0.151 ✓
  기준   걸러짐: LM(2) p=0.046
  알아서 한 것  시차·결측으로 표본 시작 1970Q1 → 1970Q2
  기록   est:cn_0001 (work/est/cn_0001/) · demand:CN 후보
```

## 4. 과거 재현과 전망

과거 재현(HS)은 실제 과거를 모형으로 다시 풀어 보는 것, 전망은 자료 끝 다음 기간을 가정 세트(`ASSUMPTIONS/base.csv`)로 푸는 것입니다.
기록 이름을 직접 주면(`--as`) 뒤에서 가리키기 쉽습니다.

```console
$ equion hs main
$ equion sim base --as first_base
$ equion sim oil20 --as first_oil
```
<!-- out -->
```text
$ equion hs main
[hs:hs_0001] main dynamic 2005Q1~2019Q4 · 정상 60 · 일부식 제외 0 · 실패대체 0 · 실패 0
  RMSPE  Y 0.47% · CN 0.51% · I 0.86% · P 1.43% · M2 2.24% · RL 9.68%
  알아서 한 것  구간 [hs] range = 2005Q1:last → 2005Q1~2019Q4 · 채택 기록 없이 지금 자료로 추정: demand:CN, demand:I, price:P, finance:RL, finance:M2
  기록   hs:hs_0001 (work/hs/hs_0001/)

$ equion sim base --as first_base
[sim:first_base] main · base · 2020Q1~2021Q4 dynamic · 정상 8 · 일부식 제외 0 · 실패대체 0 · 실패 0
  연간 증가율  2020: Y 0.89% · CN 0.87% · I -0.25% · P 2.52% │ 2021: Y 1.74% · CN 1.65% · I 1.97% · P 2.58%
  가정   base: G·POIL 16칸 · 채움(last) R 8칸
  보정항  base: demand:CN last(+0.654) · demand:I decay
  알아서 한 것  구간 next:8 → 2020Q1~2021Q4 · 채택 기록 없이 지금 자료로 추정: demand:CN, demand:I, price:P, finance:RL, finance:M2 · 보정항 규칙 값 16칸 · 가정 16칸(G, POIL) · 외생 R 8칸을 채움(last)
  기록   sim:first_base (work/sim/first_base/)

$ equion sim oil20 --as first_oil
[sim:first_oil] main · oil20 · 2020Q1~2021Q4 dynamic · 정상 8 · 일부식 제외 0 · 실패대체 0 · 실패 0
  연간 증가율  2020: Y 0.89% · CN 0.87% · I -0.25% · P 2.78% │ 2021: Y 1.74% · CN 1.65% · I 1.97% · P 2.58%
  가정   base: G·POIL 16칸 · 채움(last) R 8칸
  보정항  base: demand:CN last(+0.654) · demand:I decay
  시나리오  oil20 (유가 20% 상승): POIL +20% start~end
  기준선 대비(끝 기 수준)  Y +0.00% · CN +0.00% · I +0.00% · P +0.25% · RL +0.00% · M2 +0.26%
  알아서 한 것  구간 next:8 → 2020Q1~2021Q4 · 채택 기록 없이 지금 자료로 추정: demand:CN, demand:I, price:P, finance:RL, finance:M2 · 보정항 규칙 값 16칸 · 가정 16칸(G, POIL) · 외생 R 8칸을 채움(last)
  기록   sim:first_oil (work/sim/first_oil/)
```

## 5. 보고서로 보내기

보고서(`reports/*.md`)에는 결과만 보냅니다. 표 모양(행·전년동기비·연간)은 구역에 남아, 나중에 새 기록으로 바꿀 때 같은 모양으로 다시 만듭니다.

```console
$ equion report new first --title "첫 전망"
$ equion report add first sim:first_base --rows Y,CN,I --show yoy --annual --title "성장률"
$ equion report add first sim:first_oil --rows Y,P --show diff --title "유가 20% 상승의 영향"
$ equion work list
```
<!-- out -->
```text
$ equion report new first --title "첫 전망"
[report new] reports/first.md
  바뀜 기록  h0002

$ equion report add first sim:first_base --rows Y,CN,I --show yoy --annual --title "성장률"
[report add] reports/first.md
  #1 sim:first_base  넣음 — **표 1. 성장률** (연간 증가율, %)
  바뀜 기록  h0003

$ equion report add first sim:first_oil --rows Y,P --show diff --title "유가 20% 상승의 영향"
[report add] reports/first.md
  #2 sim:first_oil  넣음 — **표 2. 유가 20% 상승의 영향** (기준선 대비, %)
  바뀜 기록  h0004

$ equion work list
[work list] demo: 기록 4 (최근 30)
  est:cn_0001        2026-11-09T13:59 터미널    R²adj 0.9999 · CN c Y CN(-1)   걸러짐
  hs:hs_0001         2026-11-09T13:59 터미널    main 2005Q1~2019Q4 · Y 0.47% · CN 0.51% · I 0.86%
  sim:first_base     2026-11-09T13:59 터미널    main base 2020Q1~2021Q4 · 2020 Y 0.89% · 2020 CN 0.87%
  sim:first_oil      2026-11-09T13:59 터미널    main oil20 2020Q1~2021Q4 · 2020 Y 0.89% · 2020 CN 0.87%
```

`reports/first.md`는 평범한 md라 Lectern·편집기·GitHub에서 표째 읽힙니다.

## 6. 스크립트 한 번

지금까지의 순서가 월간 스크립트 `FLOWS/monthly.eqs`에 적혀 있습니다(한 줄 = 명령 하나). 미리 보고(`--dry-run` — 기록을 남기지 않는다) 돌립니다.

```console
$ equion run FLOWS/monthly.eqs --dry-run
```
<!-- out -->
```text
$ equion run FLOWS/monthly.eqs --dry-run
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
  ## 전망
  [6] sim base oil20 --model main
  ## 결과물
  [7] note run notes/data_check.md
       바꾸는 것  notes/data_check.md
  [8] report new reports/forecast_{vintage}.md --title "월간 전망 — 자료 {vintage}" --exist-ok
       바꾸는 것  reports/forecast_{vintage}.md
       실행 때 정해짐  {vintage}
  [9] report add reports/forecast_{vintage}.md {sim:base} --key growth --rows Y,CN,I,P --show yoy --annual --title "성장률 전망"
       바꾸는 것  reports/forecast_{vintage}.md
       실행 때 정해짐  {sim:base}, {vintage}
  [10] report add reports/forecast_{vintage}.md {hs} --key hs --rows Y,CN --chart --title "과거 재현"
       바꾸는 것  reports/forecast_{vintage}.md
       실행 때 정해짐  {hs}, {vintage}
  [11] export {hs} {sim} --xlsx exports/forecast_{vintage}.xlsx
       바꾸는 것  exports/forecast_{vintage}.xlsx(내보내기)
       실행 때 정해짐  {hs}, {sim}, {vintage}
  파일을 바꾸는 단계  1, 3, 7, 8, 9, 10, 11(정의 파일·노트·보고서는 바뀜 기록에 '스크립트'로 남는다)
```

```console
$ equion run FLOWS/monthly.eqs
```
<!-- out -->
```text
$ equion run FLOWS/monthly.eqs
[1/11] data build --inbox ask --use                 ✓ [data build] 바뀐 것 없음 — 회차 d2026-11a와 내용이 같습니다(새로 만들지 않음)
[2/11] assemble main                                ✓ [assemble main] 수요 + 물가 + 금융 — 블록 3 · 추정식 5 · 항등식 1
[3/11] est main --adopted --adopt if_pass           ! 기준 미달 demand:CN · 기준 미달 finance:RL · 기준 미달 finance:M2 — [est --adopted] main · 정책 if_pass…
[4/11] hs main                                      ✓ [hs:hs_0002] main dynamic 2005Q1~2019Q4 · 정상 60 · 일부식 제외 0 · 실패대체 0 · 실패 0
[5/11] expect hs Y.rmspe < 3% --flag                ✓ Y RMSPE 0.4745 — Y.rmspe < 3
[6/11] sim base oil20 --model main                  ✓ [sim:2026-11_base] main · base · 2020Q1~2021Q4 dynamic · 정상 8 · 일부식 제외 0 · 실패대체 0 · 실패 0
[7/11] note run notes/data_check.md                 ✓ [note run] notes/data_check.md: 블록 2
[8/11] report new reports/forecast_d2026-11a.md --title "월간 전망 — 자료 d2026-11a" --exist-ok ✓ [report new] reports/forecast_d2026-11a.md
[9/11] report add reports/forecast_d2026-11a.md sim:2026-11_base --key growth --rows Y,CN,I,P --show yoy --annual --title "성장률 전망" ✓ [report add] reports/forecast_d2026-11a.md
[10/11] report add reports/forecast_d2026-11a.md hs:hs_0002 --key hs --rows Y,CN --chart --title "과거 재현" ✓ [report add] reports/forecast_d2026-11a.md
[11/11] export hs:hs_0002 sim:2026-11_base sim:2026-11_oil20 --xlsx exports/forecast_d2026-11a.xlsx ✓ [export] exports/forecast_d2026-11a.xlsx — 기록 3 · 시트 15: 출처, hs_0002_적합도, hs_0002_해, hs_0…
기록  run:monthly_0001 · 단계 11 · 표시 1 · 종료 코드 0
```

`!`는 사람이 볼 것입니다 — 여기서는 판단 기준을 통과하지 못한 식(옛 채택 계수가 없어 이번 추정 계수로 푼다). 실행 기록 `run:monthly_0001`에는
값을 바꿔 넣은 뒤의 스크립트, 시작할 때의 정의 사본, 단계마다 만든 기록이 들어 있습니다.

## 7. 그때 그대로 다시

```console
$ equion run --replay run:monthly_0001 -q
```
<!-- out -->
```text
$ equion run --replay run:monthly_0001 -q
[run --replay] run:monthly_0001 — 단계 11 · 모두 같음
  [1] = data build --inbox ask --use  — 기록 없음 — 상태 같음
  [2] = assemble main  — 기록 없음 — 상태 같음
  [3] = est main --adopted --adopt if_pass  — 숫자 같음 — est:cn_0002 · est:i_0001 · est:p_0001 …
  [4] = hs main  — 숫자 같음 — hs:hs_0002
  [5] = expect hs Y.rmspe < 3% --flag  — Y RMSPE 0.4745 — Y.rmspe < 3
  [6] = sim base oil20 --model main  — 숫자 같음 — sim:2026-11_base · sim:2026-11_oil20
  [7] = note run notes/data_check.md  — 숫자 같음 — an:summary_0001
  [8] = report new reports/forecast_d2026-11a.md --title "월간 전망 — 자료 d2026-11a" --exist-ok  — 기록 없음 — 상태 같음
  [9] = report add reports/forecast_d2026-11a.md sim:2026-11_base --key growth --rows Y,CN,I,P --show yoy --annual --title "성장률 전망"  — 기록 없음 — 상태 같음
  [10] = report add reports/forecast_d2026-11a.md hs:hs_0002 --key hs --rows Y,CN --chart --title "과거 재현"  — 기록 없음 — 상태 같음
  [11] = export hs:hs_0002 sim:2026-11_base sim:2026-11_oil20 --xlsx exports/forecast_d2026-11a.xlsx  — 기록 없음 — 상태 같음
기록  run:monthly_0002 · 종료 코드 0
```

프로젝트를 임시 사본으로 옮겨 그때의 정의·자료·스크립트로 다시 돌리고 단계마다 숫자를 견줍니다. 프로젝트는 바뀌지 않습니다.

## 확인할 것

- [ ] `equion new … --template desk`가 프로젝트를 만들고 첫 자료 회차를 정한다
- [ ] `assemble main`의 내생 6 · 외생 3, 문제 없음
- [ ] `est`·`hs`·`sim`마다 `work list`에 기록이 하나씩 는다
- [ ] `reports/first.md`가 편집기·Lectern에서 표로 보인다
- [ ] `run FLOWS/monthly.eqs`가 11단계를 끝까지(종료 코드 0), `--replay`가 '모두 같음'

다음: [2. 내 모형을 프로젝트로](02-my-model.md) · [3. 매달 하는 일](03-monthly.md)
