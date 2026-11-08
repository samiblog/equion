# 레시피: 모델

```python
import pandas as pd
import equion as eqn

wf = eqn.datasets.load("toy_q")
eq_i = wf.equation("eq_i").ls("I c Y(-1) R")
eq_cn = wf.equation("eq_cn").tsls("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
eq_p = wf.equation("eq_p").ls("dlog(P) c dlog(Y) dlog(POIL)")
m = wf.model("toy").merge(eq_i, eq_cn, eq_p).append("Y = CN + I + G")
```
<!-- out -->
```text
[toy_q] 열기 toy_q.csv — 분기(Quarterly) 1970Q1~2019Q4 · 시리즈 10
[eq_i] OLS I — n=199, R²=0.9985
[eq_cn] TSLS CN — n=199, R²=0.9999
[eq_p] OLS dlog(P) — n=199, R²=0.3271
```

## R20. 방정식 파일로 모델 관리하기

식을 글 파일 하나에 두면 고치기·비교·버전 관리가 쉽습니다. 한 줄에 한 식, `#` 뒤는 주석, 추정법 지시자(`@inst`)도 씁니다.

```python
with open("model.txt", "w", encoding="utf-8") as f:
    f.write("""# 작은 거시 모형
I c Y(-1) R
CN c Y CN(-1) @inst G R CN(-1) Y(-1)
dlog(P) c dlog(Y) dlog(POIL)
Y = CN + I + G
""")
mf = wf.model("from_file").merge("model.txt")
print(mf.endogenous, [o.eq.method for o in mf.equations])
```
<!-- out -->
```text
[from_file] merge model.txt — 추정식 3/3 · 항등식 1
['CN', 'I', 'P', 'Y'] ['ols', 'tsls', 'ols']
```

실행 전에 문법·구조·결측 입력을 검사하려면 명령줄 `equion check model.txt --data 자료.csv`([명령줄 레시피](cli.md)).

## R21. 모델 일부만 풀기

```python
part = wf.model("no_price").merge(eq_i, eq_cn).append("Y = CN + I + G")     # 물가식 빼고 새로
print(part.endogenous)
fix = m.scenario("i_actual").exclude("I")                                   # 같은 모델에서 I만 실측으로
print(m.solve("2015Q1", "2015Q4").counts())
m.scenario("baseline")
```
<!-- out -->
```text
['CN', 'I', 'Y']
[toy] i_actual(_1) dynamic 2015Q1~2015Q4: 정상 4 · 일부식 제외 0 · 실패대체 0 · 실패 0
{'ok': 4, 'partial': 0, 'fallback': 0, 'failed': 0}
```

## R22. 수렴하지 않을 때

순서대로 확인합니다: ① `on_fail="stop"`으로 처음 실패한 기간과 블록 보기, ② 정적 풀이(`mode="static"`)가 되는지(되면
동태 불안정 의심 — `m.stability()`), ③ 풀이법·반복 수·시작값 바꾸기.

```python
r = m.solve("2010Q1", "2010Q4", method="newton", fallback=("hybr", "lm", "gauss-seidel"),
            tolerance=1e-10, max_iterations=100)
print(r.counts(), r.status()["iterations"].tolist())
print(m.stability("2010Q1").verdict)
```
<!-- out -->
```text
[toy] baseline(_0) dynamic 2010Q1~2010Q4: 정상 4 · 일부식 제외 0 · 실패대체 0 · 실패 0
{'ok': 4, 'partial': 0, 'fallback': 0, 'failed': 0} [4, 4, 4, 5]
단위근
```

## R23. 과거 재현 결과를 엑셀로

```python
wf.smpl("1975Q1", "2019Q4")
r = m.solve()
r.save("hs/hs_toy.csv")                                         # 상태 열 + 변수별 풀이·실측·오차(%)
cmp = wf.to_pandas(["Y", "Y_0", "CN", "CN_0"], smpl=True, labels=True)
with pd.ExcelWriter("hs_toy.xlsx") as xw:
    cmp.to_excel(xw, sheet_name="경로")
    r.statistics().to_excel(xw, sheet_name="적합도")
print(sorted(r.statistics().columns)[:4])
```
<!-- out -->
```text
[toy_q] smpl 1975Q1 ~ 2019Q4
[toy] baseline(_0) dynamic 1975Q1~2019Q4: 정상 180 · 일부식 제외 0 · 실패대체 0 · 실패 0
['MAE', 'MAE_pct', 'RMSE', 'RMSPE']
```

## R24. 출발 시점별 과거 재현 비교

동적 풀이의 오차는 출발점에서 쌓이므로, 출발 시점을 바꿔 보면 모델이 어디서 흔들리는지 보입니다.

```python
rows = {}
for start in ("1980Q1", "1990Q1", "2000Q1", "2010Q1"):
    st = m.solve(start, "2019Q4").statistics()
    rows[start] = st["RMSPE"]
print(pd.DataFrame(rows).round(3))
```
<!-- out -->
```text
[toy] baseline(_0) dynamic 1980Q1~2019Q4: 정상 160 · 일부식 제외 0 · 실패대체 0 · 실패 0
[toy] baseline(_0) dynamic 1990Q1~2019Q4: 정상 120 · 일부식 제외 0 · 실패대체 0 · 실패 0
[toy] baseline(_0) dynamic 2000Q1~2019Q4: 정상 80 · 일부식 제외 0 · 실패대체 0 · 실패 0
[toy] baseline(_0) dynamic 2010Q1~2019Q4: 정상 40 · 일부식 제외 0 · 실패대체 0 · 실패 0
    1980Q1  1990Q1  2000Q1  2010Q1
CN   0.519   0.543   0.510   0.329
I    1.032   0.920   0.843   0.613
P    1.204   1.780   0.908   0.527
Y    0.499   0.510   0.477   0.300
```

## R25. 식 하나를 바꿨을 때 모델 성능 비교

```python
base = m.solve("1990Q1", "2019Q4").statistics()["RMSPE"]
alt_cn = wf.equation("eq_cn_alt").ls("CN c Y CN(-1)")                       # TSLS 대신 OLS
m_alt = wf.model("toy_alt").merge(eq_i, alt_cn, eq_p).append("Y = CN + I + G")
alt = m_alt.solve("1990Q1", "2019Q4").statistics()["RMSPE"]
print(pd.DataFrame({"TSLS 소비식": base, "OLS 소비식": alt}).round(3))
```
<!-- out -->
```text
[toy] baseline(_0) dynamic 1990Q1~2019Q4: 정상 120 · 일부식 제외 0 · 실패대체 0 · 실패 0
[eq_cn_alt] OLS CN — n=180, R²=0.9999
[toy_alt] baseline(_0) dynamic 1990Q1~2019Q4: 정상 120 · 일부식 제외 0 · 실패대체 0 · 실패 0
    TSLS 소비식  OLS 소비식
Y      0.510    0.534
CN     0.543    0.570
I      0.920    0.945
P      1.780    1.767
```

같은 별칭(`_0`)에 쓰므로 비교할 때는 결과를 먼저 꺼내 둡니다(`statistics()` · `to_pandas`). 별칭을 나누려면 시나리오를 쓰세요.

관련: [튜토리얼 4](../tutorial/04-model.md) · [연립 풀이 해설](../explain/solving.md)

## R48. 프로젝트로 블록·모형 조립하기

식을 블록(방정식 파일 하나)으로 나누고, `equion.toml`에서 블록과 다른 모형을 이름으로 끼워 모형을 조립합니다(형식은
[파일 형식](../reference/formats.md#프로젝트equiontoml)). 예제 프로젝트는 명령줄 `equion new 폴더 --template desk`로도 만듭니다.

```python
p = eqn.Project.create("demo_prj", force=True)   # 블록 demand·price·finance, 모형 core·main·main_fixrl
print(p.assemble("main").text())          # 계산 없이 조립 검사 — 명령줄 equion assemble main
```
<!-- out -->
```text
[demo_prj] 열기 data.csv — 분기(Quarterly) 1970Q1~2019Q4 · 시리즈 10
[assemble main] 수요 + 물가 + 금융 — 블록 3 · 추정식 5 · 항등식 1
  조립   main = core(demand) + price + finance
  내생 6  CN · I · Y · P · RL · M2
  외생 3  G(~2019Q4) · POIL(~2019Q4) · R(~2019Q4)
  연결   demand →Y→ price · price →P→ finance · demand →Y→ finance
  풀이   블록 5 (동시 CN·Y)
  문제   없음
```

```python
r = p.hs("main")                          # [hs]의 구간·방식으로 과거 재현 — 식은 지금 자료로 추정해 조립
print(r.statistics()["RMSPE"].round(3))
print(p.hs("demand").counts())            # 블록 HS — 수요 블록만 풀고 나머지 변수는 실측
print(p.ident("demand:Y").text())         # 항등식을 실측으로 검사 — 명령줄 equion ident demand:Y --check
```
<!-- out -->
```text
[main] 채택 기록 없이 지금 자료로 추정: demand:CN, demand:I, price:P, finance:RL, finance:M2
[main] baseline(_0) dynamic 2005Q1~2019Q4: 정상 60 · 일부식 제외 0 · 실패대체 0 · 실패 0
Y     0.474
CN    0.505
I     0.857
P     1.435
M2    2.243
RL    9.682
Name: RMSPE, dtype: float64
[demand] baseline(_0) dynamic 2005Q1~2019Q4: 정상 60 · 일부식 제외 0 · 실패대체 0 · 실패 0
{'ok': 60, 'partial': 0, 'fallback': 0, 'failed': 0}
[ident demand:Y] Y = CN + I + G   (EQUATIONS/demand.txt:4)
  구간   1970Q1~2019Q4 · 비교 200기
  결과   성립 · 최대 |차이| 1e-06 · 최대 |차이%| 3.431e-07%
```

모형을 고치기 전에 영향 범위는 `p.used_by("demand")`, 파일을 바꾸지 않고 식 하나만 바꿔 보려면 `p.hs("main", swap={"demand:CN": "CN c Y"})`.
