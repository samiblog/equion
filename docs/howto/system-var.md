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
