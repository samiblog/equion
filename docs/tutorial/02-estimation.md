# 2. 방정식 추정

방정식을 글자로 쓰고 추정해, 결과표를 읽고, 결과를 pandas로 꺼내는 법을 배웁니다. 이어서 강건 표준오차, 내생 설명변수
(2단계 최소제곱·GMM·LIML), 비선형 식, AR 오차, 다항 분포시차, 가중 최소제곱, 다른 곳에서 얻은 계수 넣기를 다룹니다.

```python
import numpy as np
import equion as eqn

wf = eqn.datasets.load("toy_q")
```
<!-- out -->
```text
[toy_q] 열기 toy_q.csv — 분기(Quarterly) 1970Q1~2019Q4 · 시리즈 10
```

## 2.1 방정식 문법 한눈에

추정식은 **공백으로 나뉜 항**입니다. 첫 항이 종속변수(좌변), 나머지가 설명변수, `c`는 상수항입니다. 괄호 안의 공백은
자유이고, 항 하나가 식이어도 됩니다(`log(Y/P)`). 자세한 것은 [방정식 문법](../explain/equations.md).

| 쓰는 법 | 뜻 |
|---|---|
| `Y(-1)` · `Y(-1 to -4)` | 한 기 전 · 1~4기 전(항 4개로 펼침) |
| `log(Y)` · `dlog(Y)` · `d(Y)` · `d(Y, 1, 4)` | 로그 · 로그 차분 · 차분 · 1차 + 계절(4기) 차분 |
| `Y.yoy` · `Y.qoq` · `@pcy(Y)` | 전년동기대비·전기대비 증가율(%) |
| `@seas` · `@seas(2)` · `@trend` · `@d(2008Q4)` · `@step(2008Q4)` | 계절 더미 · 2분기 더미 · 추세 · 한 시점 더미 · 그 시점부터 1 |
| `@smpl 1990Q1 2019Q4` (식 끝) | 이 식만의 표본 |
| `Y = c(1) + c(2)*X^c(3)` | 비선형 식(계수를 `c(n)`으로) |

```python
e1 = wf.equation("e1").ls("log(CN) c log(Y) log(CN(-1))")
print(e1.coefs.round(4).to_dict())
e2 = wf.equation("e2").ls("dlog(CNNSA) c dlog(Y) @seas")          # 계절조정 전 소비 + 계절 더미
print(list(e2.coefs.index))
e3 = wf.equation("e3").ls("I c Y(-1 to -2) R @smpl 1990Q1 2019Q4")
print(e3.nobs, list(e3.coefs.index))
```
<!-- out -->
```text
[e1] OLS log(CN) — n=199, R²=0.9999
{'const': -0.0229, 'log(Y)': 0.7809, 'log(CN(-1))': 0.1838}
[e2] OLS dlog(CNNSA) — n=199, R²=0.9856
['const', 'dlog(Y)', '_Q2', '_Q3', '_Q4']
[e3] OLS I — n=120, R²=0.9971
120 ['const', 'Y.t(-1)', 'Y.t(-2)', 'R']
```

`@seas`에 상수항이 있으면 더미 하나를 빼서 완전 공선을 피합니다(분기라면 2~4분기 더미 `_Q2`~`_Q4`).
시차 범위 `Y(-1 to -2)`는 항 두 개 `Y.t(-1)`·`Y.t(-2)`로 펼쳐집니다(`.t(-k)`는 `(-k)`와 같은 시차 표기).

## 2.2 결과표 읽기

```python
eq = wf.equation("eq_i").ls("I c Y(-1) R")
eqn.show(eq)
```
<!-- out -->
```text
[eq_i] OLS I — n=199, R²=0.9985
방정식 eq_i
종속변수: I   목표변수: I   추정법: 최소제곱(OLS)
표본: 1970Q2 ~ 2019Q4 (관측치 199)
──────────────────────────────────────────────────────
            계수        표준오차        t값           p값
변수
const   4.4805      0.4947    9.0579   1.3578e-16  ***
Y(-1)   0.1508  7.3804e-04  204.3497  2.3161e-230  ***
R      -0.9625      0.0401  -23.9963   3.0370e-60  ***
──────────────────────────────────────────────────────
R² 0.9985   조정 R² 0.9985   회귀 표준오차 0.61416   DW 1.930
로그우도 -183.84   AIC 373.69   BIC 383.57   F 65141.62 (p=0.0000)
유의수준: *** 1%  ** 5%  * 10%
```

| 항목 | 뜻 |
|---|---|
| 계수 · 표준오차 · t값 · p값 | 추정값, 그 불확실성, 계수 = 0 검정의 통계량과 확률. 별표는 유의수준(*** 1% · ** 5% · * 10%) |
| R² · 조정 R² | 설명된 변동의 비율(상수항이 있으면 중심화). 조정 R²는 설명변수 수를 벌점으로 |
| 회귀 표준오차 | 잔차의 표준편차(자유도 보정) — 종속변수 단위 |
| DW | Durbin-Watson. 2 근처면 1차 자기상관이 작다(시차 종속변수가 있으면 [LM 검정](03-diagnostics.md)을) |
| 로그우도 · AIC · BIC | 정규 오차 가정의 우도와 정보기준(작을수록 좋다 — 같은 종속변수·표본끼리 비교) |
| F | 상수항 말고 모든 계수가 0인가 |

참 모형은 `I = 5 + 0.15·Y(-1) − 1.0·R`이므로 추정값이 가깝습니다. 출력 표 항목 전체는 [출력 표 읽는 법](../reference/outputs.md).

## 2.3 결과 꺼내기

모든 결과는 pandas 객체입니다 — 그대로 계산·그림·엑셀로 이어 쓸 수 있습니다.

```python
print(eq.coefs.round(4).to_dict())               # 계수(Series)
print(eq.stderrs.round(4).to_dict())             # 표준오차
print(eq.pvalues.map("{:.2e}".format).to_dict())  # p값  (t값은 eq.tstats)
print(eq.nobs, eq.method, eq.dependent)
print(sorted(eq.stats)[:8])                      # 통계 사전의 키
print(round(eq.stats["se_regression"], 4), round(eq.stats["durbin_watson"], 3))
```
<!-- out -->
```text
{'const': 4.4805, 'Y(-1)': 0.1508, 'R': -0.9625}
{'const': 0.4947, 'Y(-1)': 0.0007, 'R': 0.0401}
{'const': '1.36e-16', 'Y(-1)': '2.32e-230', 'R': '3.04e-60'}
199 ols I
['adj_r_squared', 'aic', 'bic', 'cov_label', 'cov_type', 'durbin_watson', 'f_pvalue', 'f_statistic']
0.6142 1.93
```

```python
fit = eq.fitted                                  # 적합값(표본 기간)
res = eq.resid                                   # 잔차 = 실측 − 적합값
print(round(float((eq.actual - fit - res).abs().max()), 12))
print(res.describe().round(3).to_dict())
```
<!-- out -->
```text
0.0
{'count': 199.0, 'mean': -0.0, 'std': 0.611, 'min': -1.844, '25%': -0.367, '50%': -0.011, '75%': 0.4, 'max': 1.568}
```

## 2.4 표본

추정은 워크파일 표본(`wf.smpl`) 안에서, 결측이 없는 기간으로 합니다. 식 하나만 다른 구간으로 하려면 식 끝에 `@smpl`을 씁니다.

```python
wf.smpl("1990Q1", "2019Q4")
a = wf.equation("eq_i90").ls("I c Y(-1) R")
wf.smpl("@all")
b = wf.equation("eq_i70").ls("I c Y(-1) R @smpl 1970Q1 1989Q4")
print(a.nobs, a.coefs.round(3).to_dict())
print(b.nobs, b.coefs.round(3).to_dict())
```
<!-- out -->
```text
[toy_q] smpl 1990Q1 ~ 2019Q4
[eq_i90] OLS I — n=120, R²=0.9971
[toy_q] smpl 전체
[eq_i70] OLS I — n=79, R²=0.9872
120 {'const': 3.386, 'Y(-1)': 0.153, 'R': -0.919}
79 {'const': 4.446, 'Y(-1)': 0.153, 'R': -1.056}
```

## 2.5 강건 표준오차

잔차가 이분산이거나 자기상관이면 보통 표준오차가 틀립니다. 계수는 그대로 두고 공분산만 바꿉니다.

```python
w = wf.equation("eq_w").ls("I c Y(-1) R", cov="white")         # 이분산 강건(HC1)
h = wf.equation("eq_h").ls("I c Y(-1) R", cov="hac", lags=4)   # 이분산·자기상관 강건(Newey-West)
print(eq.stderrs.round(4).tolist())
print(w.stderrs.round(4).tolist())
print(h.stderrs.round(4).tolist())
h.set_cov(None)                                                 # 다시 보통 표준오차로(재추정 없이)
print(h.stderrs.round(4).tolist())
```
<!-- out -->
```text
[eq_w] OLS I — n=199, R²=0.9985
[eq_h] OLS I — n=199, R²=0.9985
[0.4947, 0.0007, 0.0401]
[0.4815, 0.0007, 0.0416]
[0.3814, 0.0005, 0.0364]
[0.4947, 0.0007, 0.0401]
```

`cov`는 `"white"`(= `"hc1"`), `"hc0"`~`"hc3"`, `"hac"`를 받습니다.

## 2.6 내생 설명변수 — 2단계 최소제곱·GMM·LIML

소비식 `CN = 10 + 0.5·Y + 0.3·CN(-1)`에서 `Y`는 `CN`을 포함한 항등식으로 정해지므로 오차와 상관합니다. 최소제곱은 치우치고,
`Y`와 상관하되 오차와 무관한 **도구변수**(외생 `G`·`R`, 시차들)를 쓰면 바로잡을 수 있습니다.

```python
ols = wf.equation("cn_ols").ls("CN c Y CN(-1)")
iv = wf.equation("cn_tsls").tsls("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
iv2 = wf.equation("cn_tsls2").tsls("CN c Y CN(-1)", inst=["G", "R", "CN(-1)", "Y(-1)"])   # 같은 것
print("참값   {'const': 10, 'Y': 0.5, 'CN(-1)': 0.3}")
print("OLS  ", ols.coefs.round(3).to_dict())
print("TSLS ", iv.coefs.round(3).to_dict(), bool(np.allclose(iv.coefs, iv2.coefs)))
```
<!-- out -->
```text
[cn_ols] OLS CN — n=199, R²=0.9999
[cn_tsls] TSLS CN — n=199, R²=0.9999
[cn_tsls2] TSLS CN — n=199, R²=0.9999
참값   {'const': 10, 'Y': 0.5, 'CN(-1)': 0.3}
OLS   {'const': 11.647, 'Y': 0.587, 'CN(-1)': 0.178}
TSLS  {'const': 10.651, 'Y': 0.531, 'CN(-1)': 0.256} True
```

도구변수 목록에는 상수항이 저절로 들어갑니다. 식 안의 외생 설명변수(`CN(-1)`)도 도구에 넣어야 합니다.
GMM은 이분산에 강건한 가중으로, 과대식별(도구가 계수보다 많음)이면 Hansen J 검정을 함께 냅니다. LIML은 약한 도구에 덜 치우칩니다.

```python
gm = wf.equation("cn_gmm").gmm("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
li = wf.equation("cn_liml").liml("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
print("GMM  ", gm.coefs.round(3).to_dict(), "J p값", round(gm.stats["j_pvalue"], 3))
print("LIML ", li.coefs.round(3).to_dict(), "κ", round(li.stats["liml_kappa"], 4))
```
<!-- out -->
```text
[cn_gmm] GMM CN — n=199, R²=0.9999
[cn_liml] LIML CN — n=199, R²=0.9999
GMM   {'const': 10.644, 'Y': 0.531, 'CN(-1)': 0.256} J p값 0.102
LIML  {'const': 10.619, 'Y': 0.529, 'CN(-1)': 0.259} κ 1.0232
```

## 2.7 비선형 식

계수를 `c(1)`, `c(2)` …로 쓰면 비선형 최소제곱입니다. 시작값은 식 끝의 `@start`나 `start=[…]`로 줍니다(없으면 0).
기울기는 식을 미분해 정확히 계산합니다.

```python
nl = wf.equation("cn_nls").ls("CN = c(1) + c(2)*Y^c(3) @start 10 0.5 1")
print(nl.coefs.round(4).to_dict(), nl.method)
```
<!-- out -->
```text
[cn_nls] NLS CN — n=200, R²=0.9999
{'c(1)': 11.3056, 'c(2)': 0.7573, 'c(3)': 0.9918} nls
```

## 2.8 AR 오차

잔차가 자기상관하면 오차를 AR(p)로 둘 수 있습니다(`ar(1)` 항, 여러 차수는 `ar(1) ar(2)`). 결과의 `AR(1)`이 오차의
자기상관 계수 ρ입니다 — 이 자료의 물가식 오차는 참 모형에서 자기상관이 없으므로 0에 가깝습니다.

```python
ar = wf.equation("p_ar").ls("dlog(P) c dlog(Y) ar(1)")
print(ar.coefs.round(4).to_dict())
```
<!-- out -->
```text
[p_ar] OLS dlog(P) — n=198, R²=0.2885
{'const': 0.005, 'dlog(Y)': 0.2827, 'AR(1)': -0.0677}
```

## 2.9 다항 분포시차(PDL)

시차가 긴 반응을 적은 계수로: `pdl(X, 시차 수, 다항 차수[, 끝점 제약])`. 시차별 계수는 `lag_distribution()`으로 봅니다.

```python
pdl = wf.equation("i_pdl").ls("I c pdl(Y, 4, 2) R")
eqn.show(pdl.lag_distribution())
```
<!-- out -->
```text
[i_pdl] OLS I — n=196, R²=0.9989
방정식 i_pdl 시차 분포 — pdl(Y, 4, 2)
시차 4 · 다항식 차수 2 · 제약 없음 · 계수 PDL01, PDL02, PDL03
────────────────────────────────────────────────
            계수        표준오차        t값
시차
Y       0.1124      0.0105   10.7585
Y(-1)   0.0321      0.0052    6.1391
Y(-2)  -0.0090      0.0093   -0.9672
Y(-3)  -0.0109      0.0052   -2.0825
Y(-4)   0.0264      0.0105    2.5273
합계      0.1512  6.5401e-04  231.1144
────────────────────────────────────────────────
```

## 2.10 가중 최소제곱

관측마다 오차 분산이 다를 때 가중치를 줍니다. 가중치는 시리즈 이름이나 식이고, `wtype`이 그 뜻(기본 `"ivar"` = 1/분산)입니다.

```python
wf.genr("WT = 1 / Y")                     # 규모가 클수록 분산이 크다고 가정
wl = wf.equation("i_wls").wls("I c Y(-1) R", weights="WT")
print(wl.coefs.round(4).to_dict())
```
<!-- out -->
```text
[i_wls] WLS I — n=199, R²=0.9985
{'const': 4.5426, 'Y(-1)': 0.1507, 'R': -0.9678}
```

## 2.11 다른 곳에서 얻은 계수 넣기

다른 프로그램이나 Python(예: scikit-learn)으로 얻은 계수를 고정해 모델에 쓸 수 있습니다. 목록은 식에 쓴 항 순서입니다.

```python
fx = wf.equation("i_fixed").fixed("I c Y(-1) R", [5.0, 0.15, -1.0])     # 참값
print(fx.coefs.to_dict(), fx.method, round(fx.stats["r_squared"], 4))
```
<!-- out -->
```text
[i_fixed] FIXED I — n=199, R²=0.9985
{'const': 5.0, 'Y(-1)': 0.15, 'R': -1.0} fixed 0.9985
```

## 2.12 식 하나로 예측하기

모델을 만들기 전에 식 하나만 풀어 볼 수 있습니다(다른 변수는 실측). 결과는 목표변수 이름에 `F`를 붙인 시리즈
(여기서는 `IF`, 다른 이름은 `name=`)로 워크파일에 씁니다.

```python
f = eq.forecast(start="2015Q1", end="2019Q4")          # 동적: 종속변수의 시차에 예측값
print(f.name, round(float((f.dropna() - wf["I"].loc[f.dropna().index]).abs().mean()), 3))
```
<!-- out -->
```text
[eq_i] dynamic 예측 → IF (2015Q1~2019Q4, 정상 20 · 일부 제외 0 · 실패 0)
IF 0.44
```

## 2.13 흔한 문제

설명변수끼리 완전히 겹치면(선형 종속) 계수가 하나로 정해지지 않습니다. Equion은 추정은 하되 분명히 경고하고 표에 표시합니다.

```python
wf.genr("Y2 = 2 * Y")
bad = wf.equation("bad").ls("CN c Y Y2")
print(bad.stats["collinear"])
```
<!-- out -->
```text
[WARN] CN: 회귀변수가 선형 종속입니다(Y, Y2) — 계수·표준오차가 유일하지 않습니다(최소 노름 해)
[bad] OLS CN — n=200, R²=0.9999
['Y', 'Y2']
```

없는 변수나 문법 오류는 위치와 함께 알려 줍니다.

<!-- error -->
```python
wf.equation("typo").ls("CN c log(Y CN(-1)")
```
<!-- out -->
```text
DSLError: 괄호가 닫히지 않았습니다 (열린 괄호 1개 남음): CN c log(Y CN(-1)
```

## 정리

| 하려는 일 | 코드 |
|---|---|
| 최소제곱 · 강건 | `wf.equation("e").ls(spec)` · `cov="white"`·`"hac", lags=4` · `.set_cov(…)` |
| 도구변수 | `.tsls(spec + " @inst …")` · `.gmm(…)` · `.liml(…)` |
| 비선형 · AR · PDL · WLS · 고정 | `.ls("Y = c(1)…")` · `ar(1)` · `pdl(X, 4, 2)` · `.wls(spec, weights="W")` · `.fixed(spec, coefs)` |
| 결과 | `eqn.show(eq)` · `.coefs` `.stderrs` `.tstats` `.pvalues` `.resid` `.fitted` `.actual` `.stats` `.nobs` |
| 예측 | `eq.forecast(start=…, end=…)` |

다음: [3. 진단 검정](03-diagnostics.md). 관련 레시피: [추정 레시피](../howto/estimation.md). 식과 가정: [추정법 해설](../explain/estimation.md).
