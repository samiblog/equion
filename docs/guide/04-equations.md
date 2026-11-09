# 가이드 4. 식 고르기

식을 손보는 사람의 길입니다. 블록 파일은 그대로 둔 채 **후보**를 추정해 기록으로 남기고, 판단 기준과 진단으로 견주고, 모형에 바꿔 끼워 과거 재현으로
확인한 뒤 **채택**합니다. 채택하면 그 뒤 모형은 그 계수로 풀고(다시 추정하지 않는다), 바뀜 기록에 남아 되돌릴 수 있습니다.

```console
$ equion new eqs --template desk
$ cd eqs
```
<!-- out -->
```text
$ equion new eqs --template desk
새 프로젝트 eqs:
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
  cd eqs
  equion assemble main

$ cd eqs
```

## 1. 지금 식과 후보

```console
$ equion est demand:CN --as cn1
$ equion est "CN c Y CN(-1) CN(-2)" --for demand:CN --as cn2
$ equion est "CN c Y Y(-1) CN(-1)" --for demand:CN --as cn3
```
<!-- out -->
```text
$ equion est demand:CN --as cn1
[est:cn1] OLS CN · 1970Q2~2019Q4 · n=199   R²adj 0.9999 · SE 0.5029 · DW 1.652 · AIC 294.1 · BIC 304.0
  계수   c 11.647(t 42.990) · Y 0.5869(t 51.970) · CN(-1) 0.1782(t 11.260)
  진단   LM(2) p=0.046 ! · White p=0.485 ✓ · JB p=0.325 ✓ · RESET p=0.484 ✓ · LB(4) p=0.151 ✓
  기준   걸러짐: LM(2) p=0.046
  알아서 한 것  시차·결측으로 표본 시작 1970Q1 → 1970Q2
  기록   est:cn1 (work/est/cn1/) · demand:CN 후보

$ equion est "CN c Y CN(-1) CN(-2)" --for demand:CN --as cn2
[est:cn2] OLS CN · 1970Q3~2019Q4 · n=198   R²adj 0.9999 · SE 0.4959 · DW 1.529 · AIC 288.1 · BIC 301.2
  계수   c 11.686(t 42.978) · Y 0.5890(t 52.524) · CN(-1) 0.1326(t 5.199) · CN(-2) 0.0427(t 2.315)
  진단   LM(2) p=0.001 ! · White p=0.082 ✓ · JB p=0.482 ✓ · RESET p=0.345 ✓ · LB(4) p=0.016 !
  기준   걸러짐: LM(2) p=0.001
  알아서 한 것  시차·결측으로 표본 시작 1970Q1 → 1970Q3
  기록   est:cn2 (work/est/cn2/) · demand:CN 후보

$ equion est "CN c Y Y(-1) CN(-1)" --for demand:CN --as cn3
[est:cn3] OLS CN · 1970Q2~2019Q4 · n=199   R²adj 0.9999 · SE 0.4843 · DW 2.001 · AIC 280.1 · BIC 293.3
  계수   c 8.677(t 11.141) · Y 0.6045(t 51.623) · Y(-1) -0.1678(t -4.047) · CN(-1) 0.3885(t 7.172)
  진단   LM(2) p=0.718 ✓ · White p=0.543 ✓ · JB p=0.290 ✓ · RESET p=0.681 ✓ · LB(4) p=0.923 ✓
  기준   통과 · 부호 Y + ✓
  알아서 한 것  시차·결측으로 표본 시작 1970Q1 → 1970Q2
  기록   est:cn3 (work/est/cn3/) · demand:CN 후보
```

`--for 부품`이면 그 부품의 후보로 묶입니다(블록 파일은 그대로). 후보는 거르더라도 기록으로 남깁니다 — 왜 거렀는지가 남아야 합니다.

## 2. 판단 기준과 견주기

판단 기준은 `equion.toml`의 `[criteria]`입니다 — 진단 p값(`tests` — p < `alpha`면 걸러짐), 기대 부호(`[criteria.signs]`), `t_min`.

```python
from pathlib import Path

text = Path("equion.toml").read_text(encoding="utf-8")
print(text[text.index("[criteria]"):text.index("[hs]")].strip())
```
<!-- out -->
```text
[criteria]                        # 판단 기준 — 추정 기록의 '기준' 줄(통과·걸러짐과 까닭)
alpha = 0.05                      # 진단 유의수준
tests = ["lm", "reset"]           # 기준에 넣는 진단(p < alpha면 걸러짐)

[criteria.signs]                  # 기대 부호
"demand:CN" = { Y = "+" }
"demand:I" = { R = "-" }
```

```console
$ equion compare --part demand:CN
```
<!-- out -->
```text
$ equion compare --part demand:CN
[compare] 추정 기록 3
                            식         부품 채택             표본    n   R²adj      SE     DW    AIC    BIC LM(2) p White p   JB p RESET p                  기준
기록
est:cn1         CN c Y CN(-1)  demand:CN     1970Q2~2019Q4  199  0.9999  0.5029  1.652  294.1  304.0   0.046   0.485  0.325   0.484  걸러짐: LM(2) p=0.046
est:cn2  CN c Y CN(-1) CN(-2)  demand:CN     1970Q3~2019Q4  198  0.9999  0.4959  1.529  288.1  301.2   0.001   0.082  0.482   0.345  걸러짐: LM(2) p=0.001
est:cn3   CN c Y Y(-1) CN(-1)  demand:CN     1970Q2~2019Q4  199  0.9999  0.4843  2.001  280.1  293.3   0.718   0.543  0.290   0.681                  통과
  ! 표본이 달라 AIC·BIC를 그대로 견주기 어렵습니다
```

## 3. 바꿔 끼워 과거 재현

식 하나의 적합보다 모형 전체에서 어떻게 도는지가 중요합니다. 파일을 바꾸지 않고 후보를 끼워 풀고 지금 모형과 견줍니다.

```console
$ equion hs main --as h_now
$ equion hs main --swap demand:CN=est:cn3 --vs hs:h_now --as h_cn3
```
<!-- out -->
```text
$ equion hs main --as h_now
[hs:h_now] main dynamic 2005Q1~2019Q4 · 정상 60 · 일부식 제외 0 · 실패대체 0 · 실패 0
  RMSPE  Y 0.47% · CN 0.51% · I 0.86% · P 1.43% · M2 2.24% · RL 9.68%
  알아서 한 것  구간 [hs] range = 2005Q1:last → 2005Q1~2019Q4 · 채택 기록 없이 지금 자료로 추정: demand:CN, demand:I, price:P, finance:RL, finance:M2
  기록   hs:h_now (work/hs/h_now/)

$ equion hs main --swap demand:CN=est:cn2 --vs hs:h_now --as h_cn2
[hs:h_cn2] main dynamic 2005Q1~2019Q4 · 정상 60 · 일부식 제외 0 · 실패대체 0 · 실패 0
  RMSPE  Y 0.46% · CN 0.49% · I 0.84% · P 1.44% · M2 2.25% · RL 9.68%
  비교   vs hs:h_now — Y 0.47% → 0.46% · CN 0.51% → 0.49% · I 0.86% → 0.84% · P 1.43% → 1.44% · M2 2.24% → 2.25% (나머지 그대로)
  바꿔 끼움  demand:CN ← est:cn2 (파일은 그대로)
  알아서 한 것  구간 [hs] range = 2005Q1:last → 2005Q1~2019Q4 · 채택 기록 없이 지금 자료로 추정: demand:I, price:P, finance:RL, finance:M2 · 바꿔 끼움: demand:CN ← est:cn2
  기록   hs:h_cn2 (work/hs/h_cn2/)
```

## 4. 채택과 되돌리기

판단 기준을 통과하고(`cn3` — LM·RESET 통과, 부호 맞음) 모형에서도 적합이 나으면 채택합니다.

```console
$ equion adopt est:cn3
$ equion history list
```
<!-- out -->
```text
$ equion adopt est:cn2
[adopt] demand:CN ← est:cn2
  블록 파일  그 줄을 이 식으로 바꿈
  채택표   EQUATIONS/adopted.toml
  바뀜 기록  h0002 (EQUATIONS/adopted.toml, EQUATIONS/demand.txt)
  다음   모형을 풀면 이 기록의 계수를 쓴다(다시 추정하지 않음)

$ equion history list
[history list] eqs: 바뀜 2
[h0001] 2026-11-09T14:04:04 · 터미널 · data use d2026-11a
  파일   equion.toml(고침)
  메모   자료 회차 d2026-11a
[h0002] 2026-11-09T14:04:15 · 터미널 · equion adopt est:cn2
  파일   EQUATIONS/adopted.toml(새로) · EQUATIONS/demand.txt(고침)
  메모   demand:CN ← est:cn2
```

채택은 블록 파일의 그 줄(설명은 그대로)과 채택표 `EQUATIONS/adopted.toml`을 고치고 바뀜 기록(`h0002`)에 남깁니다. 마음이 바뀌면:

```console
$ equion history revert h0002
$ equion hs main --as h_back
$ equion compare hs:h_now hs:h_back
```
<!-- out -->
```text
$ equion history revert h0002
[history revert] h0002 되돌림
[h0003] 2026-11-09T14:04:18 · 터미널 · equion history revert h0002
  파일   EQUATIONS/adopted.toml(지움) · EQUATIONS/demand.txt(고침)
  메모   h0002 되돌리기

$ equion hs main --as h_back
[hs:h_back] main dynamic 2005Q1~2019Q4 · 정상 60 · 일부식 제외 0 · 실패대체 0 · 실패 0
  RMSPE  Y 0.47% · CN 0.51% · I 0.86% · P 1.43% · M2 2.24% · RL 9.68%
  알아서 한 것  구간 [hs] range = 2005Q1:last → 2005Q1~2019Q4 · 채택 기록 없이 지금 자료로 추정: demand:CN, demand:I, price:P, finance:RL, finance:M2
  기록   hs:h_back (work/hs/h_back/)

$ equion compare hs:h_now hs:h_back
[compare] 과거 재현 기록 2
       hs:h_now hs:h_back
RMSPE%
Y        0.4745    0.4745
CN       0.5052    0.5052
I        0.8569    0.8569
P         1.435     1.435
M2        2.243     2.243
RL        9.682     9.682
```

되돌린 뒤의 과거 재현이 채택 전과 같습니다(되돌리기도 바뀜 기록에 남는다 — 지우지 않는다).

## 5. 새 자료가 오면 — 다시 추정 정책

평소 모형은 채택 계수로 풉니다. 새 자료로 다시 추정할지는 정책으로 정합니다 — 월간 스크립트는 `if_pass`(기준을 통과한 식만 새 계수).

```console
$ equion est main --adopted --adopt if_pass
```
<!-- out -->
```text
$ equion est main --adopted --adopt if_pass
[est --adopted] main · 정책 if_pass: 식 5 — 새 계수 채택 2 · 기준 미달 3
  ! demand:CN    — → est:cn_0001 · 옛 계수 없음 · 기준 미달: LM(2) p=0.046 · 채택 안 함 — 옛 계수가 없어 모형은 이 자료로 추정한 계수로 푼다
  ✓ demand:I     — → est:i_0001 · 옛 계수 없음 · 기준 통과 · 채택
  ✓ price:P      — → est:p_0001 · 옛 계수 없음 · 기준 통과 · 채택
  ! finance:RL   — → est:rl_0001 · 옛 계수 없음 · 기준 미달: LM(2) p=<0.001 · 채택 안 함 — 옛 계수가 없어 모형은 이 자료로 추정한 계수로 푼다
  ! finance:M2   — → est:m2_0001 · 옛 계수 없음 · 기준 미달: LM(2) p=<0.001 · 채택 안 함 — 옛 계수가 없어 모형은 이 자료로 추정한 계수로 푼다
  바뀜 기록  h0004 (EQUATIONS/adopted.toml)
```

| 정책 | 하는 일 |
|---|---|
| `never`(기본) | 다시 추정해 기록만 — 채택은 그대로 |
| `if_pass` | 판단 기준을 통과한 식만 새 계수로 채택, 걸린 식은 옛 채택 계수(없으면 이번 추정 계수)와 `!` |
| `all` | 기준과 상관없이 모두 새 계수 |

## 확인할 것

- [ ] 후보가 `--for`로 부품에 묶이고 `compare --part`에 모두 나온다(표본이 다르면 경고)
- [ ] `[criteria]`를 바꾸면(예: `tests = ["lm"]`) 다음 추정의 '기준' 줄이 그에 따라 바뀐다
- [ ] `hs --swap`이 파일을 바꾸지 않는다(`history list`에 아무것도 늘지 않는다)
- [ ] `adopt` 뒤 블록 파일의 줄과 채택표가 바뀌고, `history revert`로 돌아간다
- [ ] `est main --adopted --adopt if_pass`가 걸린 식을 `!`로 알린다

다음: [5. 전망과 시나리오](05-forecast.md)
