# 5. 시나리오

시나리오는 "가정을 바꾸면 결과가 어떻게 달라지나"를 묻는 도구입니다. 외생 경로 바꾸기, 내생변수 고정, 식에 조정항 더하기,
충격, 목표 경로 맞추기를 배우고, 그 차이를 항목별로 나누는 기여도 분해, 충격 승수, 확률적 모의까지 다룹니다.

```python
import equion as eqn

wf = eqn.datasets.load("toy_q")
eq_i = wf.equation("eq_i").ls("I c Y(-1) R")
eq_cn = wf.equation("eq_cn").tsls("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
eq_p = wf.equation("eq_p").ls("dlog(P) c dlog(Y) dlog(POIL)")
m = wf.model("toy").merge(eq_i, eq_cn, eq_p).append("Y = CN + I + G")
wf.smpl("2010Q1", "2019Q4")
base = m.solve()                      # 기준선 → Y_0, CN_0 …
```
<!-- out -->
```text
[toy_q] 열기 toy_q.csv — 분기(Quarterly) 1970Q1~2019Q4 · 시리즈 10
[eq_i] OLS I — n=199, R²=0.9985
[eq_cn] TSLS CN — n=199, R²=0.9999
[eq_p] OLS dlog(P) — n=199, R²=0.3271
[toy_q] smpl 2010Q1 ~ 2019Q4
[toy] baseline(_0) dynamic 2010Q1~2019Q4: 정상 40 · 일부식 제외 0 · 실패대체 0 · 실패 0
```

## 5.1 시나리오와 별칭

모델에는 처음부터 기준선 시나리오 `baseline`(별칭 `_0`)이 있습니다. `m.scenario("이름")`은 시나리오를 만들거나 고르고
**활성화**합니다 — 이후 `m.solve()`는 활성 시나리오로 풀고, 결과를 그 별칭(`_1`, `_2` …)의 시리즈로 씁니다.

```python
hi = m.scenario("hi_g")               # 새 시나리오 → 별칭 _1, 활성화
print(hi, hi.alias)
print(list(m.scenarios))
```
<!-- out -->
```text
<시나리오 hi_g (_1)> _1
['baseline', 'hi_g']
```

## 5.2 외생 경로 바꾸기 — override

외생변수의 경로를 통째로 바꿉니다. 경로는 pandas Series, `{기간: 값}`, 스칼라, 워크파일 시리즈 이름 중 하나입니다.
주지 않은 기간은 실측 그대로입니다.

```python
hi.override("G", wf["G"] * 1.10)      # 정부지출 10% 높게(전 기간)
m.solve()
d = wf.to_pandas(["Y_0", "Y_1"], labels=True).loc["2010Q1":"2010Q4"]
print((d["Y_1"] / d["Y_0"] - 1).mul(100).round(2).to_dict())
```
<!-- out -->
```text
[toy] hi_g(_1) dynamic 2010Q1~2019Q4: 정상 40 · 일부식 제외 0 · 실패대체 0 · 실패 0
{'2010Q1': 2.26, '2010Q2': 3.63, '2010Q3': 4.65, '2010Q4': 5.43}
```

```python
low_r = m.scenario("low_r")           # 별칭 _2
low_r.override("R", {"2012Q1": 0.5, "2012Q2": 0.5})     # 두 분기만 금리를 0.5%로
m.solve()
print(wf.to_pandas(["I_0", "I_2"], labels=True).loc["2012Q1":"2012Q4"].round(2))
```
<!-- out -->
```text
[toy] low_r(_2) dynamic 2010Q1~2019Q4: 정상 40 · 일부식 제외 0 · 실패대체 0 · 실패 0
          I_0   I_2
2012Q1  87.37  89.4
2012Q2  87.31  90.0
2012Q3  87.45  88.5
2012Q4  86.90  87.6
```

`R`이 `I` 식에만 들어가므로 같은 분기의 `I`가 바로 늘고, 소득을 거쳐 다음 분기에도 남습니다.

## 5.3 충격 — shock

충격은 기간을 정해 더하거나(`kind="level"`) 비율로 바꿉니다(`"pct"`). 외생변수면 경로를, 추정식의 목표변수면 그 식의
조정항을 바꿉니다. 끝을 주지 않으면 한 기간만입니다.

```python
sh = m.scenario("shock")
sh.shock("G", 5, "2015Q1")                        # 2015Q1 한 분기 G +5
sh.shock("CN", -3, "2016Q1", "2016Q4")            # 소비식에 −3(소비 심리 위축)
m.solve()
print(wf.to_pandas(["Y_0", "Y" + sh.alias], labels=True).loc["2015Q1":"2015Q3"].round(2))
```
<!-- out -->
```text
[toy] shock(_3) dynamic 2010Q1~2019Q4: 정상 40 · 일부식 제외 0 · 실패대체 0 · 실패 0
           Y_0     Y_3
2015Q1  583.30  593.96
2015Q2  587.91  594.44
2015Q3  590.62  595.41
```

## 5.4 내생변수 고정 — exclude

내생변수를 식 대신 실측(또는 override 경로)으로 묶습니다. 예를 들어 투자를 실측대로 두면, 소비·소득 블록만 모델로 풉니다.

```python
ex = m.scenario("i_fixed")
ex.exclude("I", "2013Q1", "2014Q4")              # 이 구간만 실측
ex.override("I", wf["I"] * 0.95)                  # 고정할 경로를 바꿀 수도 있다(실측의 95%)
m.solve()
print(wf.to_pandas(["I", "I" + ex.alias], labels=True).loc["2013Q1":"2013Q2"].round(2))
```
<!-- out -->
```text
[toy] i_fixed(_4) dynamic 2010Q1~2019Q4: 정상 40 · 일부식 제외 0 · 실패대체 0 · 실패 0
            I    I_4
2013Q1  86.68  82.35
2013Q2  87.08  82.72
```

## 5.5 조정항 — add_factor

식의 우변에 값을 더합니다(좌변 단위). 대상은 방정식 객체 이름, 종속변수 표기(`dlog(P)`), 목표변수 중 하나입니다.
항등식 변수에는 조정항을 줄 수 없습니다(오류로 알려 준다).

```python
af = m.scenario("af")
af.add_factor("eq_p", 0.002)                      # 물가 상승률을 분기 0.2%p 높게(전 기간)
m.solve()
print(wf.to_pandas(["P_0", "P" + af.alias], labels=True).loc["2019Q4":"2019Q4"].round(2))
```
<!-- out -->
```text
[toy] af(_5) dynamic 2010Q1~2019Q4: 정상 40 · 일부식 제외 0 · 실패대체 0 · 실패 0
           P_0     P_5
2019Q4  189.56  205.35
```

전망의 출발점을 실측에 맞추고 싶을 때는 기준 시점의 잔차를 조정항으로 이어 붙입니다(`init_add_factor("CN", "2019Q4")`),
과거 전체를 그대로 재현하려면 표본 잔차를 모두 더합니다(`use_residuals()` — [튜토리얼 4](04-model.md#46-과거를-그대로-재현하기)).

## 5.6 목표 경로 맞추기 — control

"소득이 이 경로를 따르려면 정부지출이 얼마여야 하나"처럼 내생변수(목표)의 경로를 정하고 외생변수(도구)를 거꾸로 풉니다.
결과 도구 경로는 `도구_C` 시리즈로 씁니다.

```python
target = wf["Y_0"] * 1.02                         # 기준선보다 2% 높게(경로는 start~end 구간에만 쓰인다)
g_needed = m.control("Y", "G", target, "2018Q1", "2019Q4")
print(wf.to_pandas(["G", "G_C"], labels=True).loc["2018Q1":"2018Q4"].round(2))
```
<!-- out -->
```text
[toy] control Y ← G → G_C
            G    G_C
2018Q1  67.99  73.21
2018Q2  68.94  71.11
2018Q3  68.90  70.72
2018Q4  69.42  71.15
```

시나리오 안에 목표 추적을 넣어 다른 가정과 함께 쓸 수도 있습니다(`scenario.control("Y", "G", 경로)`).

## 5.7 결과 비교와 기여도 분해

`compare`는 실측과 모든 시나리오 결과를 나란히 보여 줍니다. 시나리오에 가정이 여럿이면 `decompose`가 기준선과의 차이를
가정별로 나눕니다(Shapley: 모든 순서의 평균 — 합이 정확히 전체 차이).

```python
mix = m.scenario("mix")
mix.override("G", wf["G"] * 1.05).shock("R", -1, "2014Q1", "2019Q4").add_factor("eq_cn", -2)
m.solve()
print(m.compare("Y").loc["2019-10-01"].round(1).to_dict())
dec = m.decompose("Y", "mix", start="2015Q1", end="2015Q4")
eqn.show(dec)
```
<!-- out -->
```text
[toy] mix(_6) dynamic 2010Q1~2019Q4: 정상 40 · 일부식 제외 0 · 실패대체 0 · 실패 0
{'Y': 625.7, 'Y_0': 624.9, 'Y_1': 675.5, 'Y_2': 624.9, 'Y_3': 624.2, 'Y_4': 624.8, 'Y_5': 624.9, 'Y_6': 637.4}
[toy] 기여도 분해(shapley) mix − baseline: 항목 3 · 풀이 8회
Y: mix − baseline 기여도
분해 Shapley(모든 부분집합 평균 — 합이 정확히 전체) · 항목 3 · 풀이 8회
─────────────────────────────────────────────────
           외생 G    조정항 CN 충격 R -1 합계(시나리오 − 기준선)
기간
2015Q1   6.7887   -4.2643  2.0522         4.5766
2015Q2  11.0860   -7.9674  3.3080         6.4266
2015Q3  14.2505  -10.8316  4.2294         7.6483
2015Q4  16.6486  -13.0134  4.9259         8.5611
─────────────────────────────────────────────────
```

`dec.table("Y")`는 같은 표를 DataFrame으로, `dec.graph("Y")`는 막대를 쌓은 그림으로 줍니다. 가정이 8개를 넘으면
`method="single"`(하나씩 넣은 효과 + 상호작용)을 씁니다.

## 5.8 충격 승수

외생변수를 한 단위(또는 1%) 바꿨을 때 내생변수가 기간마다 얼마나 반응하는지 — 정책 효과의 크기와 지속을 봅니다.

```python
mu = m.multipliers("G", 1.0, "2015Q1", "2016Q4")            # G를 지속적으로 +1
print(mu.level[["Y", "CN", "I"]].iloc[[0, 1, 3, 7]].round(3))
mu1 = m.multipliers("G", 1.0, "2015Q1", "2016Q4", permanent=False)   # 한 분기만 +1
print(mu1.level["Y"].iloc[[0, 1, 3, 7]].round(3).tolist())
```
<!-- out -->
```text
                Y     CN      I
period
2015-01-01  2.132  1.132  0.000
2015-04-01  3.437  2.115  0.322
2015-10-01  5.118  3.455  0.663
2016-10-01  6.643  4.677  0.966
[2.132, 1.305, 0.724, 0.241]
```

첫 분기 승수 약 2(= 1/(1 − 0.5), 소비의 소득 탄력)이고, 투자와 소비의 시차를 거치며 더 커집니다. 한 분기 충격은 점점 사라집니다.

## 5.9 확률적 모의

추정 잔차를 기간마다 무작위로 다시 뽑아(식 사이 상관 보존) 여러 번 풀면 결과의 불확실성 띠를 얻습니다.
`coef_uncertainty=True`면 계수의 불확실성도 더합니다.

```python
m.scenario("baseline")
sto = m.stochastic("2018Q1", "2019Q4", reps=200, seed=1)
print(sto.band("Y").round(1).head(4))
```
<!-- out -->
```text
             mean  std     p5    p50    p95
period
2018-01-01  618.0  1.7  615.2  617.9  620.7
2018-04-01  621.1  2.0  618.0  621.2  624.1
2018-07-01  622.8  2.2  619.4  622.8  626.5
2018-10-01  624.7  2.4  621.2  624.7  628.7
```

## 정리

| 하려는 일 | 코드 |
|---|---|
| 시나리오 만들기·고르기 | `sc = m.scenario("이름")` · `m.scenario("baseline")` · `sc.alias` · `sc.clear()` |
| 외생 · 충격 | `sc.override("G", 경로)` · `sc.shock("G", 5, "2015Q1", kind="level"\|"pct")` |
| 내생 고정 · 조정항 | `sc.exclude("I", s, e)` · `sc.add_factor("eq_cn", 값)` · `sc.init_add_factor("CN", "2019Q4")` · `sc.use_residuals()` |
| 목표 추적 | `m.control("Y", "G", 경로, s, e)` · `sc.control(…)` |
| 분석 | `m.compare("Y")` · `m.decompose("Y", "mix")` · `m.multipliers("G", 1.0)` · `m.stochastic(reps=200)` |

다음: [6. 전망](06-forecast.md). 원리: [시나리오와 전망 해설](../explain/scenarios.md). 레시피: [시나리오 레시피](../howto/scenario.md).
