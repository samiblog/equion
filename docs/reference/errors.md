# 오류 메시지

자주 만나는 오류의 실제 메시지와 원인·고치는 법. 각 메시지는 아래 코드를 실행해 얻은 그대로입니다(문서 검사가 매번 다시 돌린다 —
메시지가 바뀌면 이 문서도 바뀐다). 상황별 처방은 [문제 해결](../howto/troubleshooting.md).

```python
import numpy as np
import equion as eqn

eqn.verbose(0)
wf = eqn.datasets.load("toy_q")
eq_i = wf.equation("eq_i").ls("I c Y(-1) R")
m = wf.model("toy").merge(eq_i, "CN c Y CN(-1)").append("Y = CN + I + G")
```
<!-- out -->
```text
```

## 자료·워크파일

**같은 날짜가 두 번** — 파일에 같은 기간의 행이 둘 이상. 중복 행을 지운다.

<!-- error -->
```python
import pandas as pd
pd.DataFrame({"date": ["2020-01-01", "2020-01-01", "2020-04-01"], "X": [1, 2, 3]}).to_csv("dup.csv", index=False)
eqn.wfopen("dup.csv")
```
<!-- out -->
```text
ValueError: 같은 날짜가 두 번 있습니다: 2020-01-01 — dup.csv
```

**예약 이름** — `C`·`LOG`·`EXP`·`ABS`·`SQRT`·`D`·`DLOG`는 시리즈 이름이 될 수 없다. 다른 이름을 쓴다.

<!-- error -->
```python
wf["LOG"] = 1.0
```
<!-- out -->
```text
ValueError: 'LOG'은(는) 함수 log()의 이름이라 변수로 쓸 수 없습니다 — 시리즈 이름을 바꾸세요(예: LOG_)
```

**이름 충돌** — 시리즈와 객체는 이름을 함께 쓴다(대소문자 무시). 객체 이름에 접두사(`eq_`)를 붙인다.

<!-- error -->
```python
wf.model("g")
```
<!-- out -->
```text
ValueError: 'g'은(는) 이미 시리즈 이름입니다(시리즈 G — 이름은 대소문자를 가리지 않고 시리즈·객체가 함께 씁니다. 객체 이름에 접두사를 붙이세요: 예 eq_g)
```

**시점 표기** — 워크파일 주기의 표기로 쓴다(분기 `2010Q1` · 월 `2010M3` · 연 `2010`).

<!-- error -->
```python
wf.smpl("2010M1", "2010M12")
```
<!-- out -->
```text
ValueError: 시점 표기 오류: '2010M1'은(는) 월(Monthly) 표기입니다 — 분기(Quarterly) 자료의 시점은 2000Q1 꼴입니다
```

**기간 밖** — 워크파일 기간 밖의 시점. 먼저 `wf.extend(…)`.

<!-- error -->
```python
wf.elem("Y", "2030Q1")
```
<!-- out -->
```text
ValueError: 데이터에서 시점을 찾을 수 없음: 2030Q1 — 기간은 1970Q1~2019Q4입니다(늘리려면 extend)
```

**주기가 다른 파일 읽기** — 그 주기의 페이지(`wf.page("mon", "M")`)에 읽고 `convert`로 옮긴다.

<!-- error -->
```python
wf.read(eqn.datasets.path("toy_m"))
```
<!-- out -->
```text
ValueError: toy_m.csv은(는) 월(Monthly) 자료입니다 — 워크파일은 분기(Quarterly)입니다(그 주기의 페이지에 읽은 뒤 convert로 옮기세요)
```

**지표가 짧음(Denton·Chow-Lin)** — 지표가 있는 구간으로 `start`·`end`를 준다.

<!-- error -->
```python
mon = wf.page("mon", "M")
mon.read(eqn.datasets.path("toy_m"))
wf.convert("Y", mon, method="denton", indicator="IP")
```
<!-- out -->
```text
ValueError: 지표가 변환 구간을 다 덮지 않습니다 — 바꿀 구간 1970Q1~2019Q4, 지표 2000M1~2019M12. start·end로 구간을 좁히세요
```

## 방정식 문법

**괄호** — 열린 괄호 수가 맞지 않는다.

<!-- error -->
```python
wf.equation("e1").ls("I c log(Y(-1) R")
```
<!-- out -->
```text
DSLError: 괄호가 닫히지 않았습니다 (열린 괄호 1개 남음): I c log(Y(-1) R
```

**없는 함수** — 지원 함수는 [함수 목록](functions.md).

<!-- error -->
```python
wf.equation("e2").ls("I c @foo(Y) R")
```
<!-- out -->
```text
DSLError: 지원하지 않는 함수 @foo( — 지원: @abs, @exp, @log, @movav, @movsum, @pc, @pca, @pch, @pchy, @pcy, @sqrt
```

**없는 변수** — 이름이 틀렸거나 시리즈를 넣지 않았다(대소문자는 무시).

<!-- error -->
```python
wf.equation("e3").ls("I c YY(-1) R")
```
<!-- out -->
```text
ValueError: 데이터에 없는 변수 ['YY'] (오타이거나 데이터/지시자 누락). 식: I c YY(-1) R
```

**허용되지 않는 구문** — 식은 허용 목록 문법만 받는다(코드를 실행할 수 없다).

<!-- error -->
```python
wf.equation("e4").ls("I c Y.__class__")
```
<!-- out -->
```text
DSLError: 허용되지 않는 속성 '.__class__' (허용: .diff, .gr, .ma, .qoq, .t, .yoy) (위치 0: 'Y.__class__') — 식: Y.__class__
```

**연간에 `.qoq`·`@seas`** — 연간 자료에는 분기 대비·계절이 없다(`.yoy`를 쓴다).

<!-- error -->
```python
eqn.datasets.load("toy_a").equation("e5").ls("Y.qoq c R")
```
<!-- out -->
```text
DSLError: 이 주기(연간)에서는 .qoq를 사용할 수 없습니다. 전년대비는 .yoy를 사용하세요 — 식: Y.qoq
```

## 추정

**관측치 부족** — 결측 없는 관측치가 계수보다 적거나 같다. 표본을 넓히거나 항을 줄인다.

<!-- error -->
```python
wf.equation("e6").ls("I c Y(-1) R @smpl 2019Q1 2019Q3")
```
<!-- out -->
```text
ValueError: 관측치 3개가 계수 3개보다 많아야 합니다 (식: I c Y(-1) R)
```

**도구변수 부족** — 도구가 계수보다 적다(식별 불가). 외생 변수와 시차를 도구에 더 넣는다.

<!-- error -->
```python
wf.equation("e7").tsls("CN c Y CN(-1) @inst G")
```
<!-- out -->
```text
ValueError: 도구변수 2개 < 계수 3개 — 식별 불가 (@inst에 도구를 더 넣으세요)
```

**Wald 제약 모순·중복** — 같은 계수 조합을 두 번 제약했다. 독립인 제약만 준다.

<!-- error -->
```python
eq_i.wald("c(2) = 0", "c(2) = 1")
```
<!-- out -->
```text
ValueError: 제약끼리 겹치거나 서로 모순됩니다(같은 계수 조합을 두 번 제약) — 독립인 제약만 주세요
```

**완전 적합의 잔차 검정** — 잔차가 사실상 0이면(항등식을 추정한 경우 등) 잔차 검정이 의미가 없다.

<!-- error -->
```python
wf.genr("Y2 = 2 * Y")
wf.equation("e8").ls("Y2 Y").diagnostics()
```
<!-- out -->
```text
ValueError: 진단: 잔차가 사실상 0입니다(완전 적합) — 잔차 검정을 할 수 없습니다
```

## 모델 구조와 풀이

**정해지지 않는 변수** — 식에 쓴 변수가 자료에도 없고 어떤 식의 목표도 아니다.

<!-- error -->
```python
wf.model("bad1").merge(eq_i).append("Y = CN + I + GOV").endogenous
```
<!-- out -->
```text
StructureError: 데이터에도 없고 어떤 식도 결정하지 않는 변수가 있습니다: GOV (사용: Y)
```

**같은 변수를 두 식이** — 하나를 빼거나 좌변을 바꾼다.

<!-- error -->
```python
wf.model("bad2").merge(eq_i, "I c R").endogenous
```
<!-- out -->
```text
StructureError: 같은 변수를 결정하는 식이 둘 이상입니다 → I: 추정식 'I c Y(-1) R', 추정식 'I c R'. 식 하나를 빼거나(모델의 drop) 그 식의 좌변을 바꾸세요 — 목표변수는 좌변의 첫 변수입니다.
```

**빈 모델** — 식을 넣지 않았다.

<!-- error -->
```python
wf.model("bad3").solve()
```
<!-- out -->
```text
StructureError: 모델에 방정식이 없습니다 — 추정식이나 항등식을 넣으세요
```

**풀이 옵션** — 이름·값이 틀렸다(`mode`: dynamic·static·fit · `on_fail`: actual·keep·nan·stop …).

<!-- error -->
```python
m.solve("2010Q1", "2010Q4", tolerance=0)
```
<!-- out -->
```text
ValueError: tolerance는 0보다 커야 합니다(받은 값 0)
```

**처음 실패한 기간에서 멈추기**(`on_fail="stop"`) — 블록과 시도한 방법을 알려 준다.

<!-- error -->
```python
m.solve("2010Q1", "2010Q4", method="gauss-seidel", fallback=(), max_iterations=1, on_fail="stop")
```
<!-- out -->
```text
SimulationError: 2010Q1: 블록 풀이 실패 [CN, Y] 수렴하지 않음(발산/진동) (시도: gauss-seidel✗)
```

## 시나리오·전망

**조정항 대상** — 항등식 변수에는 조정항을 줄 수 없다(추정식 이름·종속변수 표기·목표변수).

<!-- error -->
```python
m.scenario("s1").add_factor("Y", 1.0)
m.solve("2010Q1", "2010Q1")
```
<!-- out -->
```text
ValueError: 조정항 대상 ['Y']에 해당하는 추정식이 없습니다 — 항등식 변수에는 조정항을 줄 수 없습니다
```

**충격 대상** — 모델에 쓰이지 않는 변수.

<!-- error -->
```python
m.scenario("s2").shock("POIL", 10, "2010Q1")
m.solve("2010Q1", "2010Q1")
```
<!-- out -->
```text
SimulationError: shock: 'POIL'는 모델에서 쓰이지 않습니다
```

**목표 추적이 닿지 않음** — 도구에서 목표로 가는 같은 기 경로가 없다.

<!-- error -->
```python
m.scenario("baseline")
m.control("I", "G", 100.0, "2010Q1", "2010Q2")
```
<!-- out -->
```text
SimulationError: 2010Q1: 구조적으로 풀 수 없는 시스템입니다(정규화 매칭 실패): 식 'I'에 배정할 미지수가 없습니다. 남은 미지수: ['G'] — 목표 추적(I ← G): 목표가 같은 기의 도구에 반응해야 풀 수 있습니다(도구에서 목표로 가는 같은 기 경로가 없음)
```

**전망 구간의 외생 경로가 빔** — `exog_fill`이나 시나리오 `override`로 채운다.

<!-- error -->
```python
m.forecast("2020Q1", "2020Q4")
```
<!-- out -->
```text
ValueError: 전망 구간에 외생변수 값이 없습니다 — 시나리오 override, wf.fill(...), 또는 exog_fill='last'|'growth'|'trend':
  G: 2020Q1~2020Q4 (4기)
  R: 2020Q1~2020Q4 (4기)
```

**기여도 분해할 것이 없음** — 기준선과 다른 항목이 없는 시나리오.

<!-- error -->
```python
m.scenario("empty_sc")
m.decompose("Y", "empty_sc", start="2010Q1", end="2010Q4")
```
<!-- out -->
```text
ValueError: 기준선과 다른 시나리오 항목이 없습니다(분해할 것이 없음)
```

## 시스템·VAR·VECM

**VAR 시차** — 1 이상의 정수.

<!-- error -->
```python
wf.var("v0", ["dlog(Y)", "R"], lags=0)
```
<!-- out -->
```text
ValueError: VAR 시차는 1 이상의 정수여야 합니다(받은 값 0) — 시차 0과의 비교는 .lag_order()
```

**VECM 순위** — 1 ~ 변수 수 − 1(순위 0이면 차분 VAR, 변수 수면 수준 VAR).

<!-- error -->
```python
wf.vecm("k0", ["RL", "R"], rank=2)
```
<!-- out -->
```text
ValueError: 공적분 순위는 1 이상 1(변수 수 − 1) 이하여야 합니다(받은 값 2) — 순위 0이면 차분 VAR, 순위 = 변수 수면 수준 VAR를 쓰세요
```

**시스템에 항등식** — 항등식은 모델에 넣는다.

<!-- error -->
```python
s = wf.system("sys1")
s.append("Y = CN + I + G")
s.ols()
```
<!-- out -->
```text
ValueError: 시스템에는 항등식을 넣지 않습니다(모델에서 .append) — Y = CN + I + G
```

## 저장

**저장 경로가 파일** — 워크파일은 폴더(.eqw)로 저장한다.

<!-- error -->
```python
open("afile.eqw", "w", encoding="utf-8").close()        # 같은 이름의 파일
wf.save("afile.eqw")
```
<!-- out -->
```text
ValueError: 저장 경로 afile.eqw이(가) 파일입니다 — 워크파일은 폴더(.eqw)로 저장합니다. 다른 경로를 주세요
```

**모르는 확장자** — 시리즈 쓰기는 .xlsx·.csv, 그래프는 .html(·.png·.svg·.pdf), 표는 .csv·.xlsx·.html·.txt.

<!-- error -->
```python
wf.write("out.json")
```
<!-- out -->
```text
ValueError: 쓸 수 있는 형식은 .xlsx·.csv입니다(받은 것: .json)
```

명령줄의 오류(종료 코드 3)는 [명령줄 참조](cli.md).
