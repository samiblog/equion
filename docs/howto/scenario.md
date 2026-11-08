# 레시피: 시나리오

```python
import pandas as pd
import equion as eqn

wf = eqn.datasets.load("toy_q")
eq_i = wf.equation("eq_i").ls("I c Y(-1) R")
eq_cn = wf.equation("eq_cn").tsls("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
eq_p = wf.equation("eq_p").ls("dlog(P) c dlog(Y) dlog(POIL)")
m = wf.model("toy").merge(eq_i, eq_cn, eq_p).append("Y = CN + I + G")
wf.smpl("2015Q1", "2019Q4")
m.solve()
```
<!-- out -->
```text
[toy_q] 열기 toy_q.csv — 분기(Quarterly) 1970Q1~2019Q4 · 시리즈 10
[eq_i] OLS I — n=199, R²=0.9985
[eq_cn] TSLS CN — n=199, R²=0.9999
[eq_p] OLS dlog(P) — n=199, R²=0.3271
[toy_q] smpl 2015Q1 ~ 2019Q4
[toy] baseline(_0) dynamic 2015Q1~2019Q4: 정상 20 · 일부식 제외 0 · 실패대체 0 · 실패 0
```

## R26. 시나리오 여러 개를 돌려 한 표로

```python
eqn.verbose(0)
rows = {}
for g in (0, 5, 10, 20):
    sc = m.scenario(f"g{g}")
    sc.clear().shock("G", g, "2015Q1", "2019Q4", kind="pct")
    m.solve()
    rows[f"G +{g}%"] = (wf["Y" + sc.alias] / wf["Y_0"] - 1).mul(100).loc["2019-10-01"]
eqn.verbose(1)
print(pd.Series(rows).round(2))
```
<!-- out -->
```text
G +0%      0.00
G +5%      4.04
G +10%     8.08
G +20%    16.15
dtype: float64
```

같은 이름으로 다시 부르면 그 시나리오를 고르고(별칭 유지), `clear()`가 앞 설정을 지웁니다.

## R27. 유가 충격

```python
oil = m.scenario("oil")
oil.shock("POIL", 50, "2016Q1", "2019Q4", kind="pct")           # 유가 50% 상승이 이어짐
m.solve()
d = wf.to_pandas(["P_0", "P" + oil.alias], labels=True)
print(((d["P" + oil.alias] / d["P_0"] - 1) * 100).loc["2016Q1":"2016Q4"].round(3).tolist())
```
<!-- out -->
```text
[toy] oil(_5) dynamic 2015Q1~2019Q4: 정상 20 · 일부식 제외 0 · 실패대체 0 · 실패 0
[0.561, 0.561, 0.561, 0.561]
```

## R28. 목표 경로 맞추기 — 물가 수준 목표

"2018년 물가가 기준선보다 1% 낮으려면 정책금리가 얼마여야 하나". 금리는 같은 분기의 투자 → 소득 → 물가로 이어지므로
물가를 목표로 금리를 거꾸로 풀 수 있습니다.

```python
r_path = m.control("P", "R", wf["P_0"] * 0.99, "2018Q1", "2018Q4")
print(wf.to_pandas(["R", "R_C"], labels=True).loc["2018Q1":"2018Q4"].round(2))
```
<!-- out -->
```text
[toy] control P ← R → R_C
           R    R_C
2018Q1  2.60  25.05
2018Q2  2.81  11.52
2018Q3  3.02  10.02
2018Q4  3.29   9.87
```

첫 분기에 금리를 크게 올려 물가 수준을 1% 낮춘 뒤, 그 수준을 지키는 만큼만 움직입니다. 도구가 목표에 닿지 않으면
(예: 이번 분기 투자 `I`를 목표로 정부지출 `G`를 쓰면 — `I`는 지난 분기 소득에만 반응한다) 풀 수 없다고 알려 줍니다.

<!-- error -->
```python
m.control("I", "G", wf["I_0"] * 1.01, "2018Q1", "2018Q4")
```
<!-- out -->
```text
SimulationError: 2018Q1: 구조적으로 풀 수 없는 시스템입니다(정규화 매칭 실패): 식 'I'에 배정할 미지수가 없습니다. 남은 미지수: ['G'] — 목표 추적(I ← G): 목표가 같은 기의 도구에 반응해야 풀 수 있습니다(도구에서 목표로 가는 같은 기 경로가 없음)
```

## R29. 모든 시나리오의 차이(%)를 한 번에

```python
cmp = m.compare("Y")                                            # 실측 · Y_0 · Y_1 …
pct = cmp.drop(columns=["Y", "Y_0"]).div(cmp["Y_0"], axis=0).sub(1).mul(100)
print(pct.loc["2019-10-01"].round(2).to_dict())
```
<!-- out -->
```text
{'Y_1': 0.0, 'Y_2': 4.04, 'Y_3': 8.08, 'Y_4': 16.15, 'Y_5': 0.0}
```

## R30. 기여도 분해를 그림으로 저장

```python
mix = m.scenario("mix")
mix.shock("G", 5, "2015Q1", "2019Q4", kind="pct").shock("POIL", 30, "2015Q1", "2019Q4", kind="pct")
mix.add_factor("eq_cn", -2)
m.solve()
dec = m.decompose(["Y", "P"], "mix")
dec.graph("Y").save("decomp_y.html")
print(dec.drivers, dec.table("P").round(3).iloc[-1].to_dict())
```
<!-- out -->
```text
[toy] mix(_6) dynamic 2015Q1~2019Q4: 정상 20 · 일부식 제외 0 · 실패대체 0 · 실패 0
[toy] 기여도 분해(shapley) mix − baseline: 항목 3 · 풀이 8회
['조정항 CN', '충격 G +5', '충격 POIL +30'] {'조정항 CN': -1.621, '충격 G +5': 2.062, '충격 POIL +30': 0.684, '합계(시나리오 − 기준선)': 1.125}
```

## R31. 시나리오를 저장하고 다시 쓰기

시나리오 설정(경로·충격·조정항·exclude·목표 추적)은 워크파일과 함께 저장됩니다.

```python
wf.save("toy_scen")
w2 = eqn.wfopen("toy_scen.eqw")
m2 = w2.obj("toy")
print(list(m2.scenarios))
r = m2.solve(scenario="mix")
print(r.counts()["ok"], round(w2.elem("Y" + m2.scenario("mix").alias, "2019Q4"), 1))
```
<!-- out -->
```text
[toy_q] 저장 → toy_scen.eqw (시리즈 39 · 객체 4)
[toy_q] 열기 toy_scen.eqw (시리즈 39 · 객체 4)
['baseline', 'g0', 'g5', 'g10', 'g20', 'oil', 'mix']
[toy] mix(_6) dynamic 2015Q1~2019Q4: 정상 20 · 일부식 제외 0 · 실패대체 0 · 실패 0
20 630.3
```

관련: [튜토리얼 5](../tutorial/05-scenario.md) · [시나리오와 전망 해설](../explain/scenarios.md)
