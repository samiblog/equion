# 레시피: 추정

```python
import numpy as np
import pandas as pd
import equion as eqn

wf = eqn.datasets.load("toy_q")
```
<!-- out -->
```text
[toy_q] 열기 toy_q.csv — 분기(Quarterly) 1970Q1~2019Q4 · 시리즈 10
```

## R9. 후보 식 여러 개를 한 번에 비교

```python
cands = {"기본": "I c Y(-1) R",
         "시차 2": "I c Y(-1 to -2) R",
         "금리 시차": "I c Y(-1) R R(-1)",
         "로그": "log(I) c log(Y(-1)) R"}
rows = {}
for label, spec in cands.items():
    e = wf.equation("cand_" + str(len(rows))).ls(spec + " @smpl 1971Q1 2019Q4")      # 같은 표본으로
    rows[label] = {"R²": e.stats["adj_r_squared"], "AIC": e.stats["aic"], "BIC": e.stats["bic"], "DW": e.stats["durbin_watson"]}
print(pd.DataFrame(rows).T.round(4))
```
<!-- out -->
```text
[cand_0] OLS I — n=196, R²=0.9984
[cand_1] OLS I — n=196, R²=0.9984
[cand_2] OLS I — n=196, R²=0.9984
[cand_3] OLS log(I) — n=196, R²=0.9981
           R²        AIC        BIC      DW
기본     0.9984   370.6037   380.4380  1.9271
시차 2   0.9984   372.3392   385.4516  1.8950
금리 시차  0.9984   372.4069   385.5193  1.9171
로그     0.9981 -1249.3821 -1239.5477  1.7122
```

AIC·BIC는 **같은 종속변수·같은 표본**끼리만 견줍니다(`log(I)` 식은 종속변수가 달라 직접 비교할 수 없다).

## R10. 계수 표를 엑셀로

```python
eq = wf.equation("eq_i").ls("I c Y(-1) R")
tab = pd.DataFrame({"계수": eq.coefs, "표준오차": eq.stderrs, "t값": eq.tstats, "p값": eq.pvalues})
tab.to_excel("eq_i.xlsx")
wf.table("t_eq_i", eq).save("eq_i_table.html")          # 결과표 그대로(html·csv·xlsx·txt)
print(tab.round(4).assign(p값=tab["p값"].map("{:.1e}".format)))
```
<!-- out -->
```text
[eq_i] OLS I — n=199, R²=0.9985
           계수    표준오차        t값        p값
const  4.4805  0.4947    9.0579   1.4e-16
Y(-1)  0.1508  0.0007  204.3497  2.3e-230
R     -0.9625  0.0401  -23.9963   3.0e-60
```

## R11. 표본을 굴리며 계수 안정성 보기

```python
rows = []
for end in range(1990, 2020, 5):
    e = wf.equation("roll").ls(f"I c Y(-1) R @smpl {end - 19}Q1 {end}Q4")       # 20년 창
    rows.append({"끝": end, "Y(-1)": e.coefs["Y(-1)"], "R": e.coefs["R"]})
print(pd.DataFrame(rows).set_index("끝").round(3))
```
<!-- out -->
```text
[roll] OLS I — n=80, R²=0.9852
[roll] OLS I — n=80, R²=0.9845
[roll] OLS I — n=80, R²=0.9880
[roll] OLS I — n=80, R²=0.9926
[roll] OLS I — n=80, R²=0.9953
[roll] OLS I — n=80, R²=0.9918
      Y(-1)      R
끝
1990  0.152 -1.098
1995  0.153 -1.086
2000  0.149 -1.041
2005  0.148 -1.030
2010  0.151 -0.921
2015  0.155 -0.866
```

한 기씩 늘리는 재귀 계수는 `eq.recursive()`, 구조 변화 검정은 [진단 레시피](diagnostics.md).

## R12. 더미 넣기

```python
d1 = wf.equation("dum").ls("I c Y(-1) R @d(2008Q4) @step(2009Q1)")     # 한 시점 더미 · 그때부터 1
print(list(d1.coefs.index))
d2 = wf.equation("seas").ls("dlog(CNNSA) c dlog(Y) @seas")              # 계절 더미(상수항이 있어 하나 뺀다)
print(list(d2.coefs.index))
```
<!-- out -->
```text
[dum] OLS I — n=199, R²=0.9985
['const', 'Y(-1)', 'R', 'D_2008Q4', 'STEP_2009Q1']
[seas] OLS dlog(CNNSA) — n=199, R²=0.9856
['const', 'dlog(Y)', '_Q2', '_Q3', '_Q4']
```

`@d`·`@step`의 시점은 워크파일 주기로 씁니다(연간 `2008`, 월간 `2008M10`).

## R13. 다른 도구로 추정한 계수를 모델에 쓰기

NumPy·scikit-learn 등으로 얻은 계수를 고정 계수 식으로 넣으면 모델·시나리오에서 추정식처럼 쓰입니다.

```python
d = wf.to_pandas(["I", "Y", "R"]).assign(Y1=lambda x: x.Y.shift(1)).dropna()
A = np.column_stack([np.ones(len(d)), d.Y1, d.R])
b, *_ = np.linalg.lstsq(A, d.I.to_numpy(), rcond=None)                   # 직접 최소제곱
fx = wf.equation("i_ext").fixed("I c Y(-1) R", b.tolist())
print(fx.method, fx.coefs.round(4).to_dict())
m = wf.model("m_ext").merge(fx, "CN c Y CN(-1)").append("Y = CN + I + G")
print(m.solve("2015Q1", "2015Q4").counts())
```
<!-- out -->
```text
[i_ext] FIXED I — n=199, R²=0.9985
fixed {'const': 4.4805, 'Y(-1)': 0.1508, 'R': -0.9625}
[eq_cn] OLS CN — n=199, R²=0.9999
[m_ext] baseline(_0) dynamic 2015Q1~2015Q4: 정상 4 · 일부식 제외 0 · 실패대체 0 · 실패 0
{'ok': 4, 'partial': 0, 'fallback': 0, 'failed': 0}
```

## R14. 장기 효과(시차 합) 계산

`Y = a + b·X + c·Y(-1)`이면 X의 장기 효과는 b/(1 − c). 계수에서 바로 계산하고, 불확실성은 Wald 검정으로 봅니다.

```python
e = wf.equation("lr").ls("CN c Y CN(-1)")
b, c = e.coefs["Y"], e.coefs["CN(-1)"]
print("단기", round(b, 3), "장기", round(b / (1 - c), 3))
e.wald("c(2) + c(3) = 1")                                # 장기 효과 = 1(장기 소비성향 1)인가
```
<!-- out -->
```text
[lr] OLS CN — n=199, R²=0.9999
단기 0.587 장기 0.714
[lr] Wald 계수 제약 검정: 통계량 2664.6860, p=0.0000
```

## R15. 강건 표준오차로 다시 보기

```python
e = wf.equation("rob").ls("dlog(P) c dlog(Y) dlog(POIL)")
t0 = e.tstats.round(2).to_dict()
e.set_cov("hac", lags=4)
print(t0)
print(e.tstats.round(2).to_dict())
```
<!-- out -->
```text
[rob] OLS dlog(P) — n=199, R²=0.3271
{'const': 20.31, 'dlog(Y)': 8.48, 'dlog(POIL)': 3.53}
{'const': 20.78, 'dlog(Y)': 9.97, 'dlog(POIL)': 3.27}
```

관련: [튜토리얼 2](../tutorial/02-estimation.md) · [추정법 해설](../explain/estimation.md)
