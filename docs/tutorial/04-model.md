# 4. 연립 모델

추정한 식과 항등식을 모델로 묶고, 구조를 보고, 과거 기간을 풀어 봅니다(과거 재현). 동적·정적 풀이의 차이, 기간마다 남는
풀이 상태, 적합도, 결과 저장, 결측·미수렴이 생겼을 때의 정책을 배웁니다.

```python
import equion as eqn

wf = eqn.datasets.load("toy_q")
eq_i = wf.equation("eq_i").ls("I c Y(-1) R")
eq_cn = wf.equation("eq_cn").tsls("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
eq_p = wf.equation("eq_p").ls("dlog(P) c dlog(Y) dlog(POIL)")
```
<!-- out -->
```text
[toy_q] 열기 toy_q.csv — 분기(Quarterly) 1970Q1~2019Q4 · 시리즈 10
[eq_i] OLS I — n=199, R²=0.9985
[eq_cn] TSLS CN — n=199, R²=0.9999
[eq_p] OLS dlog(P) — n=199, R²=0.3271
```

## 4.1 모델 만들기

`merge`는 추정식을 넣고(방정식 객체·객체 이름·추정식 글자·방정식 파일), `append`는 항등식을 넣습니다.

```python
m = wf.model("toy")
m.merge(eq_i, "eq_cn")                     # 객체 또는 객체 이름
m.merge(eq_p)
m.append("Y = CN + I + G")                 # 항등식(여러 줄 글자도 된다)
print(m)
eqn.show(m)                                # 식 목록
```
<!-- out -->
```text
<모델 toy: 방정식 3 · 항등식 1 · 시나리오 ['baseline'] (활성 baseline)>
모델 toy
추정식 3 · 항등식 1
────────────────────────────────────────────────────────
 종류    이름 목표변수  추정법                                    식
추정식  eq_i    I  ols                          I c Y(-1) R
추정식 eq_cn   CN tsls CN c Y CN(-1) @inst G R CN(-1) Y(-1)
추정식  eq_p    P  ols         dlog(P) c dlog(Y) dlog(POIL)
항등식          Y                            Y = CN + I + G
────────────────────────────────────────────────────────
```

추정식 글자를 바로 넣으면 그 자리에서 현재 표본으로 추정합니다. 방정식 파일(한 줄에 한 식, `#` 뒤는 주석)도 넣을 수 있습니다.

```python
with open("toy_model.txt", "w", encoding="utf-8") as f:
    f.write("""# 작은 거시 모형
I c Y(-1) R                                   # 투자
CN c Y CN(-1) @inst G R CN(-1) Y(-1)          # 소비(2SLS — @inst가 있으면 도구변수 추정)
dlog(P) c dlog(Y) dlog(POIL)                  # 물가
Y = CN + I + G                                # 국민소득 항등식
""")
m_file = wf.model("toy_file").merge("toy_model.txt")
print(m_file.endogenous, len(m_file.equations), m_file.identities)
```
<!-- out -->
```text
[toy_file] merge toy_model.txt — 추정식 3/3 · 항등식 1
['CN', 'I', 'P', 'Y'] 3 ['Y = CN + I + G']
```

## 4.2 구조 보기

모델의 내생변수는 각 식의 **목표변수**(추정식은 좌변의 첫 변수, 항등식은 좌변)입니다. 블록 구조는 함께 풀어야 하는
변수 묶음(동시 블록)과 풀이 순서입니다 — `CN`과 `Y`는 서로를 결정하므로 한 블록으로 함께 풉니다.

```python
print(m.endogenous, m.exogenous)
eqn.show(m.blocks())
print(m.variables().head())
```
<!-- out -->
```text
['CN', 'I', 'P', 'Y'] ['G', 'POIL', 'R']
모델 toy 블록 구조
블록 3개 (동시 1) — 위에서부터 풀이 순서
────────────────────────────────────────
 블록 종류  크기    변수
  0 순차   1     I
  1 동시   2 CN, Y
  2 순차   1     P
────────────────────────────────────────
   변수  구분
0  CN  내생
1   I  내생
2   P  내생
3   Y  내생
4   G  외생
```

## 4.3 과거 재현 — 동적 풀이

`solve`는 표본 구간(또는 `start`·`end`)을 한 기씩 풉니다. **동적** 풀이는 내생변수의 시차에 지난 기의 *풀이 값*을 쓰므로
오차가 누적됩니다 — 모델 전체가 과거를 얼마나 따라가는지 보는 기본 시험입니다. 결과는 별칭 시리즈 `X_0`으로 들어갑니다.

```python
wf.smpl("1975Q1", "2019Q4")
r = m.solve()
print(r)
eqn.show(r.summary())
```
<!-- out -->
```text
[toy_q] smpl 1975Q1 ~ 2019Q4
[toy] baseline(_0) dynamic 1975Q1~2019Q4: 정상 180 · 일부식 제외 0 · 실패대체 0 · 실패 0
<풀이 toy·baseline(_0) 1975Q1~2019Q4: 정상 180·일부 0·대체 0·실패 0>
적합도 상위 10 — toy·baseline(_0)
1975Q1~2019Q4 · 정상 180 · 일부식 제외 0 · 실패대체 0 · 실패 0
─────────────────────────────────────────────────
     RMSPE MAE_pct     MAE mean_error  n_samples
Y   0.5356  0.4274  1.9425    -0.0161        180
CN  0.5596  0.4464  1.5214    -0.0192        180
I   1.0598  0.8335  0.5664    -0.0043        180
P   1.2685  1.0548  1.2546    -0.9671        180
─────────────────────────────────────────────────
※ 0 근처 계열(잔액·금리)은 RMSPE가 과대 — MAE(수준)도 함께 보세요
```

`RMSPE`는 평균 제곱근 백분율 오차, `MAE`는 평균 절대 오차(수준), `mean_error`는 평균 오차(치우침)입니다. 0 근처를
오가는 계열(금리·잔액)은 RMSPE가 크게 나오므로 MAE를 함께 봅니다. 실측과 나란히 보려면 `compare`나 그래프를 씁니다.

```python
print(m.compare("Y").tail(4).round(1))         # 실측과 모든 시나리오 결과(표본 구간)
g = wf.graph("g_hs", "Y Y_0", start="2005Q1", title="국민소득: 실측과 동적 풀이")
g.save("hs.html")
```
<!-- out -->
```text
                Y    Y_0
2019-01-01  621.0  621.1
2019-04-01  625.7  623.9
2019-07-01  626.1  623.3
2019-10-01  625.7  624.9
```

## 4.4 정적 풀이와 fit

**정적** 풀이는 시차에 실측을 씁니다(한 기 앞 예측의 정확도). **fit**은 식마다 따로 — 다른 내생변수도 실측으로 두고
그 식만 풉니다(식 하나하나의 적합). 셋을 견주면 오차가 어디서 커지는지 보입니다.

```python
for mode in ("fit", "static", "dynamic"):
    st = m.solve(mode=mode).statistics()
    print(f"{mode:8s}", st["RMSPE"].round(3).to_dict())
```
<!-- out -->
```text
[toy] baseline(_0) fit 1975Q1~2019Q4: 정상 180 · 일부식 제외 0 · 실패대체 0 · 실패 0
fit      {'Y': 0.0, 'CN': 0.158, 'P': 0.31, 'I': 0.902}
[toy] baseline(_0) static 1975Q1~2019Q4: 정상 180 · 일부식 제외 0 · 실패대체 0 · 실패 0
static   {'P': 0.327, 'Y': 0.373, 'CN': 0.386, 'I': 0.902}
[toy] baseline(_0) dynamic 1975Q1~2019Q4: 정상 180 · 일부식 제외 0 · 실패대체 0 · 실패 0
dynamic  {'Y': 0.536, 'CN': 0.56, 'I': 1.06, 'P': 1.269}
```

`fit`과 `static`의 차이는 동시성(이번 기 `Y`·`CN`을 함께 푼 효과), `static`과 `dynamic`의 차이는 오차 누적입니다.

## 4.5 기간 상태

풀이는 기간마다 상태를 남깁니다: `ok`(모든 식이 풀림) · `partial`(입력이 비어 일부 식을 빼고 풂) · `fallback`(블록이
수렴하지 않아 실측으로 대신함) · `failed`(값을 얻지 못함). **실패한 해는 다음 기 시차로 흘러가지 않습니다.**

자료의 첫 분기(1970Q1)부터 풀면 시차 입력(`Y(-1)`·`CN(-1)`)이 자료 시작 전이라 그 식들을 빼야 합니다.

```python
r0 = m.solve("1970Q1", "1970Q4")
print(r0.counts())
print(r0.status()[["status", "excluded"]])
eqn.show(m.gaps("1970Q1", "1970Q2"))      # 비어 있는 입력 진단
```
<!-- out -->
```text
[toy] baseline(_0) dynamic 1970Q1~1970Q4: 정상 3 · 일부식 제외 1 · 실패대체 0 · 실패 0
{'ok': 3, 'partial': 1, 'fallback': 0, 'failed': 0}
         status                                    excluded
period
1970Q1  partial  I:Y(-1) 범위 밖, CN:CN(-1) 범위 밖, P:P(-1) 범위 밖
1970Q2       ok
1970Q3       ok
1970Q4       ok
────────────────────────────────────────────────────
   period  t equation target                 missing
0  1970Q1  0        I      I                   Y(-1)
1  1970Q1  0       CN     CN                  CN(-1)
2  1970Q1  0  dlog(P)      P  P(-1), POIL(-1), Y(-1)
────────────────────────────────────────────────────
```

`partial` 기간의 빠진 식의 목표변수는 실측으로 둡니다. 통계(`statistics`)는 실측으로 대신한 변수-기간을 빼고 계산합니다.

## 4.6 과거를 그대로 재현하기

추정 잔차를 조정항으로 더하면(`use_residuals`) 모든 식이 과거에 정확히 성립하므로, 풀이가 실측을 그대로 재현합니다.
모델이 맞게 조립됐는지(항등식·시차·추정 표본) 확인하는 데 씁니다.

```python
sc = m.scenario("replay")
sc.use_residuals()
rr = m.solve(scenario="replay")
cmp = wf.to_pandas(["Y", "Y" + sc.alias, "CN", "CN" + sc.alias], labels=True).loc["2019Q1":"2019Q4"]
print(cmp.round(3))
m.scenario("baseline")                     # 다음 풀이가 기준선으로 가도록
```
<!-- out -->
```text
[toy] replay(_1) dynamic 1975Q1~2019Q4: 정상 180 · 일부식 제외 0 · 실패대체 0 · 실패 0
              Y      Y_1       CN     CN_1
2019Q1  621.039  621.039  458.476  458.476
2019Q2  625.740  625.740  460.874  460.874
2019Q3  626.108  626.108  461.666  461.666
2019Q4  625.706  625.706  461.788  461.788
```

## 4.7 결과 저장

`SolveResult.save`는 기간마다 상태 열과 변수별 풀이·실측·오차(%) 열을 담은 CSV를 씁니다(없는 폴더는 만든다).

```python
path = r.save("results/hs_toy.csv")
import pandas as pd
df = pd.read_csv(path)
print(path, df.shape)
print(list(df.columns[:9]))
```
<!-- out -->
```text
results/hs_toy.csv (180, 19)
['period', 'time_index', 'status', 'iterations', 'max_resid', 'excluded', 'fallback', 'CN_hs', 'CN_actual']
```

## 4.8 풀이 설정과 실패 정책

블록은 해석적 미분을 쓰는 Newton법으로 풀고, 안 되면 다른 방법(hybr·lm·Gauss-Seidel)으로 다시 시도합니다. 일부러 수렴하지
못하게 해서 정책을 보겠습니다.

```python
hard = dict(method="gauss-seidel", fallback=(), max_iterations=1)     # 한 번만 돌고 다른 방법도 쓰지 않음
print(m.solve("2010Q1", "2010Q4", **hard).counts())                  # 기본 on_fail='actual' → 실측 대체(fallback)
print(m.solve("2010Q1", "2010Q4", on_fail="nan", **hard).counts())   # 값 없음(failed)
print(m.solve("2010Q1", "2010Q4").counts())                          # 기본 설정은 문제없이 풀린다
```
<!-- out -->
```text
[toy] baseline(_0) dynamic 2010Q1~2010Q4: 정상 1 · 일부식 제외 0 · 실패대체 3 · 실패 0
{'ok': 1, 'partial': 0, 'fallback': 3, 'failed': 0}
[toy] baseline(_0) dynamic 2010Q1~2010Q4: 정상 1 · 일부식 제외 1 · 실패대체 0 · 실패 2
{'ok': 1, 'partial': 1, 'fallback': 0, 'failed': 2}
[toy] baseline(_0) dynamic 2010Q1~2010Q4: 정상 4 · 일부식 제외 0 · 실패대체 0 · 실패 0
{'ok': 4, 'partial': 0, 'fallback': 0, 'failed': 0}
```

| 옵션 | 값 | 뜻 |
|---|---|---|
| `mode` | `dynamic`(기본) · `static` · `fit` | 시차에 무엇을 쓰나 |
| `method` · `fallback` | `newton` · (`hybr`, `lm`, `gauss-seidel`) | 블록 풀이법과 다시 시도할 순서 |
| `tolerance` · `max_iterations` | `1e-10` · `50` | 수렴 기준(정규화 잔차)과 반복 수 |
| `on_missing` | `exclude`(기본) · `nan` · `stop` | 입력이 비었을 때 |
| `on_fail` | `actual`(기본) · `keep` · `nan` · `stop` | 블록이 수렴하지 않을 때 |
| `jacobian` | `auto` · `dense` · `sparse` | 큰 블록(100변수 이상)은 희소 행렬로 |

`on_fail="nan"`으로 값을 비운 기간의 다음 기간은 시차 입력이 비어 그 식들을 뺍니다(`partial`) — 실패한 해를 다음 기간의
시차로 흘려보내지 않기 때문입니다. `stop`을 쓰면 처음 문제가 생긴 기간에서 멈추고 원인을 알려 줍니다(원인을 찾을 때 좋다).

## 4.9 모델 고치기

식을 다시 추정하면 모델은 다음 풀이 때 새 계수로 다시 조립됩니다. 식을 빼려면 `drop`(객체 이름 또는 항등식의 목표변수).

```python
eq_i.ls("I c Y(-1) R @smpl 1990Q1 2019Q4")     # 표본을 바꿔 다시 추정
print(m.solve().statistics()["RMSPE"].round(3).to_dict())
m2 = wf.model("toy_small").merge(eq_i, eq_cn).append("Y = CN + I + G")
m2.drop("eq_i")
print(m2.endogenous)
```
<!-- out -->
```text
[eq_i] OLS I — n=120, R²=0.9971
[toy] baseline(_0) dynamic 1975Q1~2019Q4: 정상 180 · 일부식 제외 0 · 실패대체 0 · 실패 0
{'Y': 0.583, 'CN': 0.598, 'I': 1.151, 'P': 1.299}
['CN', 'Y']
```

`I`를 빼면 `I`는 외생변수(실측)가 됩니다.

## 정리

| 하려는 일 | 코드 |
|---|---|
| 만들기 | `wf.model("m").merge(식…, "file.txt").append("Y = …")` · `.drop(…)` |
| 구조 | `m.endogenous` · `m.exogenous` · `m.blocks()` · `m.variables()` · `m.gaps(s, e)` |
| 풀이 | `r = m.solve(start, end, mode=…)` → `X_0` 시리즈 |
| 결과 | `r.counts()` · `r.status()` · `r.statistics()` · `r.summary()` · `r.save(path)` · `m.compare("Y")` |
| 재현 | `m.scenario("replay").use_residuals()` |

다음: [5. 시나리오](05-scenario.md). 원리: [연립 풀이 해설](../explain/solving.md). 레시피: [모델 레시피](../howto/model.md).
