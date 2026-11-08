# 레시피: 출력·보고서

```python
from pathlib import Path

import equion as eqn

wf = eqn.datasets.load("toy_q")
eq = wf.equation("eq_i").ls("I c Y(-1) R")
```
<!-- out -->
```text
[toy_q] 열기 toy_q.csv — 분기(Quarterly) 1970Q1~2019Q4 · 시리즈 10
[eq_i] OLS I — n=199, R²=0.9985
```

## R40. 표를 여러 형식으로

```python
t = wf.table("t_i", eq)                         # 방정식·검정·DataFrame·출력 객체를 표로
for path in ("eq.csv", "eq.xlsx", "eq.html", "eq.txt"):
    t.save(path)
print(Path("eq.txt").read_text(encoding="utf-8").splitlines()[0])
```
<!-- out -->
```text
방정식 eq_i
```

## R41. 그래프를 html로(인터넷 없이 열리게)

```python
g = wf.graph("g_y", "Y CN I", start="2000Q1", title="소득과 구성 요소")
g.output().save("y_inline.html", include_js="inline")     # plotly.js를 파일에 넣는다(약 3MB)
g.save("y_cdn.html")                                       # 기본: 인터넷에서 plotly.js를 부른다(작음)
spec = g.output().spec()                                   # JSON으로 쓸 수 있는 그림 정의(dict)
print(sorted(spec), len(spec["data"]))
```
<!-- out -->
```text
['data', 'layout'] 3
```

`kind="bar"`·`"stacked"`도 됩니다. png·svg가 필요하면 plotly와 kaleido를 설치하고 `.save("y.png")`.

## R42. 출력 여러 개를 한 보고서로

스크립트에서 `eqn.show(…)`로 보인 표·그래프는 `equion run`이 보고서 한 페이지(report.html)로 모읍니다. 파이썬 안에서
모은 출력을 직접 보려면 스풀을 씁니다.

```python
eqn.spool.clear()
eqn.spool.mode = "collect"                     # 화면에 찍지 않고 모으기만
eqn.show(eq, eq.diagnostics(), wf.graph("g2", "I"))
print([type(o).__name__ for o in eqn.spool.items])
eqn.spool.mode = "auto"
```
<!-- out -->
```text
['TableOutput', 'TableOutput', 'GraphOutput']
```

## R43. 출력 수준 조절

```python
eqn.verbose(0)                                 # 요약 줄도 끔
wf.equation("quiet_eq").ls("CN c Y")
eqn.verbose(1)                                 # 기본(요약 한 줄)
wf.equation("loud_eq").ls("CN c Y")
```
<!-- out -->
```text
[loud_eq] OLS CN — n=200, R²=0.9999
```

`eqn.verbose(2)`는 엔진 상세 로그까지 보입니다. 응용 프로그램의 logging 설정을 쓰려면 `eqn.log.use_own_handler(False)`.

관련: [명령줄 튜토리얼](../tutorial/08-cli.md)
