# 가이드 5. 전망과 시나리오

전망을 짜는 사람의 길입니다. 전망은 세 가지 정의로 정해집니다 — **가정 세트**(`ASSUMPTIONS/` — 외생 변수의 경로), **보정항**(`ADDFACTORS/` —
식마다 전망 구간의 조정 규칙), **시나리오**(`SCENARIOS/` — 가정에 얹는 충격). 계산한 값은 실측 자리에 쓰지 않고 기록(`sim:…`)에만 남습니다.

```console
$ equion new fc --template desk
$ cd fc
```
<!-- out -->
```text
$ equion new fc --template desk
새 프로젝트 fc:
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
  cd fc
  equion assemble main

$ cd fc
```

## 1. 가정 세트와 보정항

가정 세트는 첫 열이 기간, 열마다 외생 변수인 CSV입니다. 적지 않은 외생(여기서는 정책금리 `R`)은 `[forecast] fill` 규칙(`last`)으로 채우고
'채움'으로 표시합니다. 보정항은 식마다 전망 앞 마지막 잔차를 어떻게 이을지 적습니다.

```python
from pathlib import Path

print("\n".join(Path("ASSUMPTIONS/base.csv").read_text(encoding="utf-8").splitlines()[:5]))
print(Path("ADDFACTORS/base.toml").read_text(encoding="utf-8"))
```
<!-- out -->
```text
period,G,POIL
2020Q1,69.491,62.530
2020Q2,69.838,63.155
2020Q3,70.187,63.787
2020Q4,70.538,64.425
# 보정항 — 식마다 전망 구간의 초깃값 규칙(전망 앞 마지막 잔차 기준). 형식: docs/reference/formats.md "가정·보정항·시나리오"
default = "zero"                  # 적지 않은 식: zero · last · decay · mean

[eq."demand:CN"]
rule = "last"                     # 마지막 잔차를 그대로

[eq."demand:I"]
rule = "decay"                    # 마지막 잔차를 반감기로 줄이기
half_life = 4
```

```console
$ equion sim base --as b0
```
<!-- out -->
```text
$ equion sim base --as b0
[sim:b0] main · base · 2020Q1~2021Q4 dynamic · 정상 8 · 일부식 제외 0 · 실패대체 0 · 실패 0
  연간 증가율  2020: Y 0.89% · CN 0.87% · I -0.25% · P 2.52% │ 2021: Y 1.74% · CN 1.65% · I 1.97% · P 2.58%
  가정   base: G·POIL 16칸 · 채움(last) R 8칸
  보정항  base: demand:CN last(+0.654) · demand:I decay
  알아서 한 것  구간 next:8 → 2020Q1~2021Q4 · 채택 기록 없이 지금 자료로 추정: demand:CN, demand:I, price:P, finance:RL, finance:M2 · 보정항 규칙 값 16칸 · 가정 16칸(G, POIL) · 외생 R 8칸을 채움(last)
  기록   sim:b0 (work/sim/b0/)
```

## 2. 시나리오 만들기

시나리오는 가정 세트에 충격을 얹습니다. 정부지출을 전망 구간 내내 5% 늘리는 시나리오를 `scenario define`으로 씁니다 — 충격은
`변수=크기[%][@처음[:끝]]`(기간은 라벨 또는 `start`·`end`·`start+N`, 없으면 처음부터 끝까지). 명령으로 쓰면 쓰기 전에 검사하고(전망 구간 밖의
기간 · 항등식에 준 식 보정은 거절) 바뀜 기록에 남습니다.

```console
$ equion scenario define g_up --desc "정부지출 5% 확대" --base base --shock G=+5%
```
<!-- out -->
```text
$ equion scenario define g_up --desc "정부지출 5% 확대" --base base --shock G=+5%
[scenario define] SCENARIOS/g_up.toml — 새 시나리오
  충격 1 · 식 보정 0
  바뀜 기록  h0002
  다음   equion sim g_up
```

쓴 파일은 사람이 읽고 고칠 수 있는 TOML입니다(편집기로 고쳐도 됩니다 — 다음 명령 때 '바깥' 바뀜으로 남는다).

```python
print(Path("SCENARIOS/g_up.toml").read_text(encoding="utf-8"))
```
<!-- out -->
```text
desc = "정부지출 5% 확대"
base = "base"

[[shock]]
var = "G"
from = "start"
pct = 5
```

```console
$ equion sim g_up --as g5
```
<!-- out -->
```text
$ equion sim g_up --as g5
[sim:g5] main · g_up · 2020Q1~2021Q4 dynamic · 정상 8 · 일부식 제외 0 · 실패대체 0 · 실패 0
  연간 증가율  2020: Y 3.26% · CN 3.01% · I 1.30% · P 3.17% │ 2021: Y 3.05% · CN 3.04% · I 3.87% · P 2.93%
  가정   base: G·POIL 16칸 · 채움(last) R 8칸
  보정항  base: demand:CN last(+0.654) · demand:I decay
  시나리오  g_up (정부지출 5% 확대): G +5% start~end
  기준선 대비(끝 기 수준)  Y +3.86% · CN +3.71% · I +3.71% · P +1.03% · RL +0.00% · M2 +3.78%
  알아서 한 것  구간 next:8 → 2020Q1~2021Q4 · 채택 기록 없이 지금 자료로 추정: demand:CN, demand:I, price:P, finance:RL, finance:M2 · 보정항 규칙 값 16칸 · 가정 16칸(G, POIL) · 외생 R 8칸을 채움(last)
  기록   sim:g5 (work/sim/g5/)
```

시나리오는 같은 가정·보정항의 기준선도 함께 풀어 차이를 적습니다(`기준선 대비`).

## 3. 가정을 고친 뒤 — 지난 전망과 견주기

가정 경로를 고치면 새 전망은 새 기록입니다. `--vs`로 지난 전망과 연간 증가율을 견줍니다.

```python
import pandas as pd

a = pd.read_csv("ASSUMPTIONS/base.csv", index_col=0)
a["G"] *= 1.01                                    # 정부지출 경로를 1% 위로
a.to_csv("ASSUMPTIONS/base.csv", float_format="%.3f")
```

```console
$ equion sim base --as b1 --vs sim:b0
$ equion work list --kind sim
```
<!-- out -->
```text
$ equion sim base --as b1 --vs sim:b0
[sim:b1] main · base · 2020Q1~2021Q4 dynamic · 정상 8 · 일부식 제외 0 · 실패대체 0 · 실패 0
  연간 증가율  2020: Y 1.36% · CN 1.30% · I 0.06% · P 2.65% │ 2021: Y 2.01% · CN 1.93% · I 2.36% · P 2.65%
  가정   base: G·POIL 16칸 · 채움(last) R 8칸
  보정항  base: demand:CN last(+0.654) · demand:I decay
  비교   vs sim:b0 — 2020 Y 0.89% → 1.36% (+0.47%p) · 2020 CN 0.87% → 1.30% (+0.43%p) · 2020 I -0.25% → 0.06% (+0.31%p) · 2020 P 2.52% → 2.65% (+0.13%p) · 2020 M2 3.35% → 3.77% (+0.42%p) · 2021 Y 1.74% → 2.01% (+0.27%p) …
  알아서 한 것  구간 next:8 → 2020Q1~2021Q4 · 채택 기록 없이 지금 자료로 추정: demand:CN, demand:I, price:P, finance:RL, finance:M2 · 보정항 규칙 값 16칸 · 가정 16칸(G, POIL) · 외생 R 8칸을 채움(last)
  기록   sim:b1 (work/sim/b1/)

$ equion work list --kind sim
[work list] fc: 기록 3 (최근 30)
  sim:b0             2026-11-13T05:16 터미널    main base 2020Q1~2021Q4 · 2020 Y 0.89% · 2020 CN 0.87%
  sim:g5             2026-11-13T05:16 터미널    main g_up 2020Q1~2021Q4 · 2020 Y 3.26% · 2020 CN 3.01%
  sim:b1             2026-11-13T05:16 터미널    main base 2020Q1~2021Q4 · 2020 Y 1.36% · 2020 CN 1.30%
```

성장률이 왜 바뀌었는지는 **요인 나누기**로 봅니다. 두 전망 기록 사이에서 자료 → 가정 → 식을 차례로 하나씩 바꿔 다시 풀어, 연간 성장률의
바뀜을 셋의 몫으로 나눕니다(여기서는 가정만 바꿨으므로 몫이 모두 '가정'에 갑니다).

```console
$ equion an split "sim:b0 sim:b1" --vars Y,CN
```
<!-- out -->
```text
$ equion an split "sim:b0 sim:b1" --vars Y,CN
[an:split_0001] 요인 나누기 · sim:b1 ← sim:b0 · 2020Q1~2021Q4 · 자료 data:d2026-11a
  Y 2020 성장률 0.89% → 1.36% (+0.47%p)  자료 +0.00 · 가정 +0.47 · 식 +0.00
  Y 2021 성장률 1.74% → 2.01% (+0.27%p)  자료 +0.00 · 가정 +0.27 · 식 +0.00
  CN 2020 성장률 0.87% → 1.30% (+0.43%p)  자료 +0.00 · 가정 +0.43 · 식 +0.00
  CN 2021 성장률 1.65% → 1.93% (+0.28%p)  자료 +0.00 · 가정 +0.28 · 식 +0.00
  알아서 한 것  차례: 자료 → 가정 → 식(하나씩 바꿔 다시 풀어 나눔 — 차례가 바뀌면 몫이 달라질 수 있다) · 앞 sim:b0 · 뒤 sim:b1(만든 때 순) · 자료 data:d2026-11a → data:d2026-11a · 구간 2020Q1~2021Q4 → 2020Q1~2021Q4 · 가정은 기록에 적힌 외생 경로(가정·채움·시나리오 충격)와 보정항 경로 — 보정항 규칙 값의 변화도 '가정'의 몫에 든다 · 식은 기록의 조립 명세(식 글자·계수) — 지금 파일과 무관
  기록   an:split_0001 (work/an/split_0001/summary.md)
```

## 4. 구간과 모형 바꾸기

| 하고 싶은 것 | 명령 |
|---|---|
| 12분기 전망 | `equion sim base --range next:12` |
| 다른 모형으로 | `equion sim base --model core` |
| 옛 회차로 | `equion sim base --vintage d2026-10a` |
| 여러 시나리오를 한 번에 | `equion sim base oil20 g_up` |
| 표로 꺼내기 | `equion export sim:b1 sim:g5 --xlsx exports/전망.xlsx` · 보고서로는 [6. 분석·노트·보고서](06-reports.md) |
| 시나리오 보기·고치기·지우기 | `equion scenario list` · `scenario show g_up` · `scenario define g_up --shock G=+3%@start:start+3`(준 목록을 통째로 바꾼다) · `scenario remove g_up` |
| 식 보정을 얹기 | `equion scenario define g_up --addfactor demand:CN=-0.2@start:start+3`(추정식에만 — 항등식은 거절) |
| 확정한 전망을 남기기 | `equion milestone make fc_2026_11 --note "11월 전망 확정"` — 정의·자료 회차·고정한 기록([R65](../howto/model.md#r65-이정표와-묶어-보내기--확정한-때를-남기고-다른-pc로-옮기기)) |

## 확인할 것

- [ ] 가정이 없는 외생이 채우기 규칙으로 채워지고 '채움'으로 적힌다
- [ ] `scenario define`으로 쓴 충격이 '기준선 대비'에 보이고, 전망 구간 밖의 기간은 거절된다
- [ ] 가정 세트를 고친 뒤 `--vs`가 연간 증가율의 전후를, `an split`이 자료·가정·식의 몫을 보인다
- [ ] 가정 세트에 모형에 없는 변수를 적으면 쓰지 않고 알린다

다음: [6. 분석·노트·보고서](06-reports.md)
