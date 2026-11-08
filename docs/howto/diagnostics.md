# 레시피: 진단

```python
import pandas as pd
import equion as eqn

wf = eqn.datasets.load("toy_q")
eqs = {"투자": wf.equation("eq_i").ls("I c Y(-1) R"),
       "소비": wf.equation("eq_cn").ls("CN c Y CN(-1)"),
       "물가": wf.equation("eq_p").ls("dlog(P) c dlog(Y) dlog(POIL)")}
```
<!-- out -->
```text
[toy_q] 열기 toy_q.csv — 분기(Quarterly) 1970Q1~2019Q4 · 시리즈 10
[eq_i] OLS I — n=199, R²=0.9985
[eq_cn] OLS CN — n=199, R²=0.9999
[eq_p] OLS dlog(P) — n=199, R²=0.3271
```

## R16. 여러 식의 진단을 한 표로

```python
rows = {}
for name, e in eqs.items():
    d = e.diagnostics().data
    rows[name] = d["p값"]
print(pd.DataFrame(rows).round(3))
```
<!-- out -->
```text
                          투자     소비     물가
검정
계열상관 LM(2)             0.416  0.046  0.405
White(교차항)             0.338  0.485  0.308
Breusch-Pagan-Godfrey  0.608  0.414  0.326
Ljung-Box Q(4)         0.444  0.151  0.578
ARCH LM(1)             0.026  0.334  0.279
Jarque-Bera            0.966  0.325  0.998
RESET(1)               0.850  0.484  0.374
```

## R17. 여러 시리즈의 단위근 표

```python
eqn.verbose(0)                                  # 검정마다 찍히는 요약 줄을 끈다
rows = {}
for x in ("Y", "log(Y)", "dlog(Y)", "R", "d(R)", "RL - R"):
    a, k = wf.adf(x), wf.kpss(x)
    rows[x] = {"ADF p": a.pvalue, "KPSS p": k.pvalue, "판정": "정상" if a.pvalue < 0.05 and k.pvalue > 0.05 else "단위근 의심"}
eqn.verbose(1)
print(pd.DataFrame(rows).T)
```
<!-- out -->
```text
            ADF p    KPSS p      판정
Y        0.952186      0.01  단위근 의심
log(Y)   0.319936      0.01  단위근 의심
dlog(Y)       0.0       0.1      정상
R        0.737894      0.01  단위근 의심
d(R)          0.0       0.1      정상
RL - R   0.000003  0.044037  단위근 의심
```

두 검정이 엇갈리면(`RL − R`: ADF는 단위근을 기각, KPSS는 5%에서 정상을 기각) 결정항·시차 선택을 바꿔 보고, 이론과
함께 판단합니다(참 모형에서 `RL − R`은 AR(0.7)로 정상이다).

## R18. 구조 변화 시점 찾기

후보 시점마다 Chow 검정을 해 가장 강한 곳을 봅니다(탐색해서 고른 시점의 p값은 그대로 믿지 않는다 — 참고용).

```python
eqn.verbose(0)
stats = {f"{y}Q1": eqs["투자"].chow(f"{y}Q1").statistic for y in range(1980, 2015, 5)}
eqn.verbose(1)
print({k: round(v, 2) for k, v in stats.items()})
```
<!-- out -->
```text
{'1980Q1': 0.29, '1985Q1': 0.12, '1990Q1': 0.93, '1995Q1': 0.55, '2000Q1': 0.3, '2005Q1': 1.47, '2010Q1': 3.01}
```

## R19. 계수 제약 여러 개를 한꺼번에

```python
e = eqs["투자"]
e.wald("c(2) = 0.15")
e.wald("c(3) = -1")
e.wald("c(2) = 0.15", "c(3) = -1")             # 함께
```
<!-- out -->
```text
[eq_i] Wald 계수 제약 검정: 통계량 1.2289, p=0.2690
[eq_i] Wald 계수 제약 검정: 통계량 0.8732, p=0.3512
[eq_i] Wald 계수 제약 검정: 통계량 0.6198, p=0.5391
```

관련: [튜토리얼 3](../tutorial/03-diagnostics.md)
