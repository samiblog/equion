# 레시피: 시스템·VAR

```python
import pandas as pd
import equion as eqn

wf = eqn.datasets.load("toy_q")
v = wf.var("v1", ["dlog(Y)", "R"], lags=2)
```
<!-- out -->
```text
[toy_q] 열기 toy_q.csv — 분기(Quarterly) 1970Q1~2019Q4 · 시리즈 10
[v1] VAR(2) 추정 — 변수 2 · 관측치 197 · AIC -12.5242
```

## R36. 충격반응 그림 저장

```python
v.irf_graph("R", periods=12).save("irf_r.html")          # R 충격에 대한 모든 변수의 반응
irf = v.irf(12)
irf.to_csv("irf.csv")                                     # 수치는 DataFrame(열 = (반응, 충격))
print(irf.columns.tolist()[:2])
```
<!-- out -->
```text
[('dlog(Y)', 'dlog(Y)'), ('dlog(Y)', 'R')]
```

## R37. Granger 인과 표

```python
eqn.show(v.granger_table())
```
<!-- out -->
```text
VAR v1 Granger 인과 p값
────────────────────────────────────────
        dlog(Y)       R
원인 → 결과
dlog(Y)      NA  0.4366
R        0.0586      NA
────────────────────────────────────────
```

행이 원인, 열이 결과, 값은 p값입니다(작으면 원인 변수의 시차가 결과 변수를 설명한다).

## R38. 공적분 순위 고르기와 VECM

```python
wf.smpl("1980Q1", "2019Q4")
j = wf.johansen("RL R", det=0, lags=1)
rank = j.rows["트레이스 기준 순위(5%)"]
k = wf.vecm("vecm1", ["RL", "R"], lags_diff=1, rank=rank)
print(rank, k.beta.round(3).iloc[:, 0].to_dict())
```
<!-- out -->
```text
[toy_q] smpl 1980Q1 ~ 2019Q4
[toy_q] Johansen 공적분 검정 — RL · R: 순위(트레이스 5%) 1 · 최대 고유값 1
[vecm1] VECM — 변수 2 · 공적분 순위 1 · 차분 시차 1 · 결정항 ci · 관측치 158
1 {'RL': 1.0, 'R': -0.985, 'c': -1.058}
```

순위가 0이면 차분 VAR(`wf.var("…", ["d(RL)", "d(R)"])`), 변수 수와 같으면 수준 VAR를 씁니다.

## R39. 시스템 추정 결과를 모델로

```python
kw = eqn.datasets.load("klein_like")
s = kw.system("kl")
s.append("CONS c PR PR(-1) WP+WG", "I c PR PR(-1) K(-1)", "WP c X X(-1) A", "@inst G T WG A PR(-1) K(-1) X(-1)")
s.three_sls()
km = kw.model("km").merge(s).append("X = CONS + I + G", "PR = X - T - WP", "K = K(-1) + I")
mu = km.multipliers("G", 1.0, "1960", "1965")
print(mu.level["X"].round(3).tolist())
```
<!-- out -->
```text
[klein_like] 열기 klein_like.csv — 연(Annual) 1921~1990 · 시리즈 10
[kl] 3단계 최소제곱(3SLS) — 식 3 · 계수 12 · 표본 69기
[1.692, 3.456, 4.66, 5.12, 4.904, 4.218]
```

관련: [튜토리얼 7](../tutorial/07-systems.md)

## R66. 비선형 시스템 — 계수 공유와 도구변수

계수에 비선형인 식(생산함수의 지수, 탄력성이 변하는 소비함수 등)을 함께 추정합니다. 같은 `c(n)`은 두 식이 함께 쓰는 계수(식 사이 제약)이고,
시작값은 식 끝의 `@start`나 `start=`로 줍니다. 식 하나면 `tsls`가 비선형 2단계 최소제곱(NL-2SLS)입니다.

```python
ns = wf.system("ns")
ns.append("CN = c(1) + c(2)*Y^c(3) + c(4)*CN(-1) @start 10 0.5 1 0.2",
          "I = c(5) + c(6)*Y(-1)^c(3) + c(7)*R",
          "@inst G R CN(-1) Y(-1) POIL")
ns.three_sls()
print(ns.coefs.round(3).to_dict())
print(ns.wald("c(4) = 0").pvalue < 0.01)
one = wf.equation("one").tsls("CN = c(1) + c(2)*Y^c(3) + c(4)*CN(-1) @start 10 0.5 1 0.2 @inst G R CN(-1) Y(-1) POIL")
print(one.stats["method"], round(float(one.coefs["c(3)"]), 3))
```
<!-- out -->
```text
[ns] 3단계 최소제곱(3SLS) — 비선형 · 식 2 · 계수 7 · 표본 160기
{'c(1)': 37.531, 'c(2)': 0.236, 'c(3)': 1.116, 'c(4)': 0.246, 'c(5)': 12.048, 'c(6)': 0.066, 'c(7)': -0.969}
[ns] 시스템 Wald 계수 제약 검정: χ² 87.1837, p=0.0000
True
[one] NL-TSLS CN — n=160, R²=0.9999
NL-TSLS 1.112
```

프로젝트의 블록이면 `equion an system demand --method 3sls --inst "G R CN(-1) Y(-1) POIL"` — 블록 파일의 c(n)은 식마다 따로라 시스템에서는
번호를 이어 붙이고(`c(1)` → `c(5)`), 같은 번호를 같은 계수로 묶으려면 `--shared`. 식 하나의 NL-2SLS는 `equion est "CN = c(1) + … @inst …" --for demand:CN`
(기록의 추정법 이름 `NL-TSLS`).

관련: [해설 — 추정](../explain/estimation.md#시스템-추정--wfsystem) · [R39](#r39-시스템-추정-결과를-모델로)
