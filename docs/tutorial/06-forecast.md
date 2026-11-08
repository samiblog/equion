# 6. 전망

자료가 끝난 뒤를 모델로 풉니다. 외생변수의 앞날 가정을 세우는 법, 가정이 비었을 때의 진단, 전망 출발점을 실측에 맞추는 법,
불확실성 띠, 그리고 지난 기간으로 모델의 예측력을 평가하는 법을 배웁니다.

```python
import equion as eqn

wf = eqn.datasets.load("toy_q")
eq_i = wf.equation("eq_i").ls("I c Y(-1) R")
eq_cn = wf.equation("eq_cn").tsls("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
eq_p = wf.equation("eq_p").ls("dlog(P) c dlog(Y) dlog(POIL)")
m = wf.model("toy").merge(eq_i, eq_cn, eq_p).append("Y = CN + I + G")
print(m.exogenous)                    # 앞날 경로가 필요한 외생변수
```
<!-- out -->
```text
[toy_q] 열기 toy_q.csv — 분기(Quarterly) 1970Q1~2019Q4 · 시리즈 10
[eq_i] OLS I — n=199, R²=0.9985
[eq_cn] TSLS CN — n=199, R²=0.9999
[eq_p] OLS dlog(P) — n=199, R²=0.3271
['G', 'POIL', 'R']
```

## 6.1 외생 가정이 없으면

자료는 2019Q4에서 끝납니다. 외생변수의 앞날을 주지 않고 전망하면, 무엇이 언제 비었는지 알려 주고 멈춥니다.

<!-- error -->
```python
m.forecast("2020Q1", "2021Q4")
```
<!-- out -->
```text
[toy_q] 기간 확장 → 2021Q4 (+8)
ValueError: 전망 구간에 외생변수 값이 없습니다 — 시나리오 override, wf.fill(...), 또는 exog_fill='last'|'growth'|'trend':
  G: 2020Q1~2021Q4 (8기)
  POIL: 2020Q1~2021Q4 (8기)
  R: 2020Q1~2021Q4 (8기)
```

## 6.2 외생 가정 세우기

세 가지 방법이 있습니다. ① `exog_fill`로 규칙에 따라 한꺼번에(마지막 값 유지 `last` · 평균 성장률 `growth` · 평균 증분 `trend`),
② 워크파일 시리즈를 직접 채우기, ③ 시나리오의 `override`로 가정만 따로 두기(실측 시리즈는 그대로).

```python
r = m.forecast("2020Q1", "2021Q4", exog_fill="last")     # 기간을 늘리고 외생을 마지막 값으로 채워 푼다
print(r)
print(wf.to_pandas(["G", "R", "POIL"], labels=True).loc["2019Q4":"2020Q2"].round(2))
```
<!-- out -->
```text
[toy] baseline(_0) dynamic 2020Q1~2021Q4: 정상 8 · 일부식 제외 0 · 실패대체 0 · 실패 0
<풀이 toy·baseline(_0) 2020Q1~2021Q4: 정상 8·일부 0·대체 0·실패 0>
            G     R   POIL
2019Q4  69.15  3.16  61.91
2020Q1  69.15  3.16  61.91
2020Q2  69.15  3.16  61.91
```

```python
alt = m.scenario("plan")                                  # 다른 가정: 정부지출 연 4% 증가, 금리 인하
g0 = wf.elem("G", "2019Q4")
alt.override("G", {f"{y}Q{q}": g0 * 1.01 ** (4 * (y - 2020) + q) for y in (2020, 2021) for q in (1, 2, 3, 4)})
alt.override("R", {f"2020Q{q}": 2.5 for q in (1, 2, 3, 4)} | {f"2021Q{q}": 2.0 for q in (1, 2, 3, 4)})
m.forecast("2020Q1", "2021Q4", scenario="plan")
print(wf.to_pandas(["Y_0", "Y" + alt.alias], labels=True).loc["2020Q1":"2021Q4"].round(1))
```
<!-- out -->
```text
[toy] plan(_1) dynamic 2020Q1~2021Q4: 정상 8 · 일부식 제외 0 · 실패대체 0 · 실패 0
          Y_0    Y_1
2020Q1  626.9  629.8
2020Q2  627.5  633.5
2020Q3  627.8  637.5
2020Q4  628.0  641.8
2021Q1  628.2  647.4
2021Q2  628.4  652.8
2021Q3  628.5  658.2
2021Q4  628.6  663.6
```

`exog_fill`은 비어 있는 외생변수만 채웁니다(이미 값이 있으면 그대로). 시나리오의 `override`는 워크파일의 실측 시리즈를 바꾸지
않으므로, 여러 가정을 나란히 두기 좋습니다.

## 6.3 출발점 맞추기

모델은 마지막 실측 분기(2019Q4)에서도 잔차만큼 실측과 다릅니다. 그 잔차를 앞으로도 이어 붙이면(`init_add_factor`) 전망이
실측에서 매끄럽게 출발합니다 — 실무에서 흔히 쓰는 '착지'입니다.

```python
land = m.scenario("landed")
for eq in ("eq_i", "eq_cn", "eq_p"):
    land.init_add_factor(eq, "2019Q4")
m.forecast("2020Q1", "2021Q4", scenario="landed")
print(wf.to_pandas(["CN", "CN_0", "CN" + land.alias], labels=True).loc["2019Q4":"2020Q2"].round(2))
```
<!-- out -->
```text
[toy] landed(_2) dynamic 2020Q1~2021Q4: 정상 8 · 일부식 제외 0 · 실패대체 0 · 실패 0
            CN    CN_0    CN_2
2019Q4  461.79     NaN     NaN
2020Q1     NaN  461.99  461.79
2020Q2     NaN  462.31  461.77
```

## 6.4 불확실성 띠

```python
m.scenario("baseline")
sto = m.stochastic("2020Q1", "2021Q4", reps=300, seed=7)
b = sto.band("Y")
b.index = [f"{d.year}Q{(d.month - 1) // 3 + 1}" for d in b.index]
print(b.round(1))
```
<!-- out -->
```text
         mean  std     p5    p50    p95
2020Q1  627.1  1.7  623.9  627.1  629.8
2020Q2  627.6  2.0  624.2  627.5  630.9
2020Q3  627.9  2.3  624.3  627.7  631.8
2020Q4  628.3  2.4  624.3  628.3  632.3
2021Q1  628.4  2.4  624.8  628.3  632.1
2021Q2  628.4  2.4  624.9  628.3  632.4
2021Q3  628.4  2.3  624.3  628.4  632.2
2021Q4  628.6  2.4  624.5  628.7  632.6
```

`p5`~`p95`가 90% 띠입니다. 시차가 쌓일수록 띠가 넓어집니다. `coef_uncertainty=True`면 계수 추정의 불확실성도 더합니다.

## 6.5 예측력 평가 — 지난 기간으로

모델의 예측력은 추정에 쓰지 않은 기간을 맞춰 보며 잽니다. 2009년까지로 추정하고 2010~2019년을 풀어 실측과 견줍니다.
비교 대상으로 '전 분기와 같다'(무변화 예측)를 둡니다.

```python
ev = eqn.datasets.load("toy_q")
ev.smpl("1970Q1", "2009Q4")                               # 추정 구간
for name, spec in (("i", "I c Y(-1) R"), ("p", "dlog(P) c dlog(Y) dlog(POIL)")):
    ev.equation("e_" + name).ls(spec)
ev.equation("e_cn").tsls("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
mv = ev.model("mv").merge("e_i", "e_cn", "e_p").append("Y = CN + I + G")
mv.solve("2010Q1", "2019Q4", mode="static")               # 한 분기 앞 예측(시차는 실측)
ev.smpl("2010Q1", "2019Q4")                               # 평가 구간 — genr도 표본 안만 쓰므로 먼저 바꾼다
ev.genr("Y_NAIVE = Y(-1)")
eqn.show(ev.forecast_eval("Y", "Y_0", "Y_NAIVE"))
ev.dm_test("Y", "Y_0", "Y_NAIVE")                          # 두 예측의 정확도가 같은가(Diebold-Mariano)
```
<!-- out -->
```text
[toy_q] 열기 toy_q.csv — 분기(Quarterly) 1970Q1~2019Q4 · 시리즈 10
[toy_q] smpl 1970Q1 ~ 2009Q4
[e_i] OLS I — n=159, R²=0.9976
[e_p] OLS dlog(P) — n=159, R²=0.3155
[e_cn] TSLS CN — n=159, R²=0.9999
[mv] baseline(_0) static 2010Q1~2019Q4: 정상 40 · 일부식 제외 0 · 실패대체 0 · 실패 0
[toy_q] smpl 2010Q1 ~ 2019Q4
예측 평가 — 실측 Y
구간 2010Q1~2019Q4 (실측·예측이 함께 있는 기간)
─────────────────────────────────────────────────────────────────────────────
          N    RMSE     MAE MAPE(%) Theil U1   편의 비중   분산 비중  공분산 비중 Theil U2
예측
Y_0      40  1.8123  1.5243  0.2583   0.0015  0.1313  0.0011  0.8676   0.5373
Y_NAIVE  40  3.4009  2.7325  0.4606   0.0029  0.2024  0.0172  0.7804   1.0000
─────────────────────────────────────────────────────────────────────────────
Theil U1: 0 완벽 ~ 1 · 편의+분산+공분산 비중 = 1(편의·분산이 작을수록 좋음) · Theil U2 < 1이면 '변화 없음' 예측보다 낫다
[toy_q] Diebold-Mariano 예측 정확도 비교: DM -3.9018, p=0.0004
```

`genr`은 표본 안만 계산하므로, 무변화 예측 `Y_NAIVE`를 만들기 전에 평가 구간으로 표본을 바꿨습니다.
RMSE·MAE·MAPE가 작을수록, Theil U가 0에 가까울수록 좋습니다. Diebold-Mariano 통계량이 음수이고 p값이 작으면 첫 예측(모델)이
유의하게 더 정확하다는 뜻입니다. 동적 풀이(`mode="dynamic"`)로 하면 여러 분기 앞 예측의 정확도가 됩니다.

## 6.6 결과 내보내기

```python
out = wf.to_pandas(["Y_0", "CN_0", "I_0", "P_0"], labels=True).loc["2020Q1":"2021Q4"]
out.to_excel("forecast.xlsx")                              # pandas 그대로
wf.write("forecast.csv", ["Y_0", "Y_1"])                    # 또는 워크파일에서
print(out.round(1).head(2))
```
<!-- out -->
```text
[toy_q] write forecast.csv — 2열 208행
          Y_0   CN_0   I_0    P_0
2020Q1  626.9  462.0  95.8  191.6
2020Q2  627.5  462.3  96.0  192.6
```

## 정리

| 하려는 일 | 코드 |
|---|---|
| 전망 | `m.forecast(start, end, exog_fill="last"\|"growth"\|"trend", scenario=…)` |
| 가정 | `wf.fill("G", method=…)` · `wf["G"] = …` · `sc.override("G", {기간: 값})` |
| 착지 | `sc.init_add_factor("eq_cn", "2019Q4")` |
| 띠 | `m.stochastic(start, end, reps=300).band("Y")` |
| 평가 | `wf.forecast_eval("Y", "Y_0", "Y_NAIVE")` · `wf.dm_test("Y", "Y_0", "Y_NAIVE")` |

다음: [7. 시스템·VAR·VECM](07-systems.md). 레시피: [전망 레시피](../howto/forecast.md).
