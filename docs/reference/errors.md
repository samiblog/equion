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
UnknownVariableError: 데이터에 없는 변수 ['YY'] (오타이거나 데이터/지시자 누락). 식: I c YY(-1) R
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

## 프로젝트 명령

프로젝트 폴더에서 치는 명령(`equion est`·`hs`·`sim`·`data`·`scenario`·`note`·`history` …)의 오류는 표준오류에 `equion: 오류: …`로 나오고(`--json`이면
표준출력에 `{"error": …}` 하나), 종료 코드는 대개 3(입력 오류)입니다. 3이면 아무것도 쓰지 않았거나 그 단계만 건너뛴 것입니다. 아래는 예제 프로젝트
(`equion new errs --template desk`)에서 실제로 낸 것입니다.

```console
$ equion new errs --template desk
$ cd errs
```

**이름이 틀림 · 쓰기 전 검사** — 없는 부품, 항등식에 준 식 보정, 전망 구간 밖의 충격.

<!-- error -->
```console
$ equion est demand:ZZ
$ equion scenario define bad --addfactor demand:Y=5
$ equion scenario define far --shock G=+5%@2030Q1:2030Q4
```
<!-- out -->
```text
$ equion est demand:ZZ
equion: 오류: 없는 부품: demand:ZZ (있는 부품: demand:CN, demand:I, demand:Y, price:P, finance:RL, finance:M2)
(종료 코드 3)

$ equion scenario define bad --addfactor demand:Y=5
equion: 오류: SCENARIOS/bad.toml [[addfactor]] 1번째: demand:Y는 항등식입니다 — 식 보정(보정항)은 추정식에만 붙입니다(항등식의 오른쪽 외생변수에 충격을 주거나 추정식을 보정하세요)
(종료 코드 3)

$ equion scenario define far --shock G=+5%@2030Q1:2030Q4
equion: 오류: SCENARIOS/far.toml [[shock]] 1번째: 기간 2030Q1~2030Q4이(가) 전망 구간 2020Q1~2021Q4 밖이라 효과가 없습니다 — start · end · start+N · end-N이나 구간 안의 라벨로
(종료 코드 3)
```

**되돌리기가 뒤의 바뀜과 겹침** — 같은 곳을 뒤의 바뀜이 또 고쳤다. 아무것도 쓰지 않았다.

<!-- error -->
```console
$ equion model define main --desc "첫 설명"
$ equion model define main --desc "둘째 설명"
$ equion history revert h0002
```
<!-- out -->
```text
$ equion model define main --desc "첫 설명"
[model define] [model.main] — 고침
  바뀜 기록  h0002
  다음   equion assemble main

$ equion model define main --desc "둘째 설명"
[model define] [model.main] — 고침
  바뀜 기록  h0003
  다음   equion assemble main

$ equion history revert h0002
equion: 오류: h0002(equion model define main --desc '첫 설명')을(를) 되돌릴 수 없습니다 — 그 뒤의 바뀜이 같은 곳을 고쳐서 그 바뀜만 물리면 뒤의 바뀜과 겹칩니다. 파일은 그대로 두었습니다.
  equion.toml: 뒤의 바뀜 h0003(equion model define main --desc '둘째 설명')
  할 수 있는 것: 뒤의 바뀜을 먼저 되돌리거나(새것부터), 그 파일을 직접 고친다. 뒤의 바뀜까지 버리고 equion.toml을(를) h0002 앞 내용으로 통째로 되돌리려면 --force(equion history revert h0002 --force)
(종료 코드 3)
```

**손으로 고친 결과 구역** — `note run`은 그 구역을 덮지 않고 건너뛴다(다른 블록은 돈다).

```console
$ equion note run notes/data_check.md
```

```python
from pathlib import Path

note = Path("notes/data_check.md")
lines = note.read_text(encoding="utf-8").splitlines()
k = next(i for i, s in enumerate(lines) if s.startswith("<!-- equion:out")) + 2
lines[k] += " (손으로 고침)"                                  # 결과 구역 안의 한 줄을 고친다
note.write_text("\n".join(lines) + "\n", encoding="utf-8")
```

<!-- error -->
```console
$ equion note run notes/data_check.md
```
<!-- out -->
```text
$ equion note run notes/data_check.md
[note run] notes/data_check.md: 블록 2
   1 equion 손으로 고침 an:summary_0001  — 결과 구역을 손으로 고쳤습니다 — 덮으려면 --force
   2 equion 실행
  바뀜 기록  h0006
  손으로 고친 결과 구역(블록 1)은 덮지 않았습니다 — 사람에게 묻고, 덮으려면 equion note run notes/data_check.md --force (종료 코드 3)
(종료 코드 3)
```

**받은 원자료가 맞지 않음** — 짝지을 출처가 없거나, 짝은 있는데 틀(시점 열·열 이름 줄)이 맞지 않는다. 하나라도 그러면 아무것도 넣지 않는다.

```python
inbox = Path("DATA/raw/inbox")
inbox.mkdir(parents=True, exist_ok=True)
(inbox / "memo.csv").write_text("a,b\n1,2\n", encoding="utf-8")                    # 어느 출처의 inbox 글롭에도 맞지 않는 이름
(inbox / "toy_q_2020Q2.csv").write_text("x,y\nfoo,bar\n", encoding="utf-8")        # 출처 na의 이름이지만 시점 열이 없다
```

<!-- error -->
```console
$ equion data inbox
```
<!-- out -->
```text
$ equion data inbox
[data inbox] 받은 원자료 2 — DATA/raw/inbox/
  memo.csv — 짝지을 출처가 없습니다: series.toml [source.이름]에 inbox = "파일 이름 글롭"을 적거나 equion data add DATA/raw/inbox/memo.csv --source 이름
  toy_q_2020Q2.csv → [source.na] 틀이 맞지 않습니다: toy_q_2020Q2.csv: 시점 열 A에서 기간을 찾지 못했습니다 — 처음 칸 A2 'foo' (2003Q4 · 2003-10 · 2003 · 2003년 4분기 · 2003 4/4 꼴)
  넣기   스크립트의 자료 단계(예: equion run FLOWS/monthly.eqs) — 따로 넣으려면 equion data build --inbox ask --use
(종료 코드 3)
```

**자료 회차가 없음** — `equion.toml`의 `[data] vintage`가 가리키는 회차가 `work/data/`에 없다. `work/`는 git에 넣지 않으므로, 프로젝트를 새로 받은
(clone한) 폴더에서 흔하다.

```python
import shutil

shutil.rmtree("DATA/raw/inbox")
shutil.move("work", "work_away")                    # work/가 없는 폴더처럼
```

<!-- error -->
```console
$ equion assemble main
```
<!-- out -->
```text
$ equion assemble main
equion: 오류: 자료 회차 'd2026-11a'가 없습니다 (있는 회차: 없음 — equion data build)
(종료 코드 3)
```

```python
shutil.rmtree("work", ignore_errors=True)
shutil.move("work_away", "work")
```

**기준을 판단할 수 없음** — 오류는 아니고(종료 코드 0) 기록의 '기준' 줄에 나온다. 판단 기준의 검정(`[criteria] tests`)을 그 추정법이 계산하지 않는다
(TSLS·NLS·NL-TSLS) — 통과로 보지 않는다.

```console
$ equion est "CN = c(1) + c(2)*Y" --for demand:CN --as nl1
```
<!-- out -->
```text
$ equion est "CN = c(1) + c(2)*Y" --for demand:CN --as nl1
[est:nl1] NLS CN · 1970Q1~2019Q4 · n=200   R²adj 0.9999 · SE 0.6426 · DW 1.124 · AIC 392.7 · BIC 399.3
  계수   c(1) 13.958(t 62.977) · c(2) 0.7140(t 1,503.9)
  진단   JB p=0.106 ✓ · LB(4) p=<0.001 !
  기준   판단 못 함: 검정 없음 — LM(2)·RESET을(를) NLS에는 계산하지 않음 · 기대 부호 — c(n) 식이라 항 이름으로 볼 수 없음(Y) · 부호 Y + (항 없음)
  기록   est:nl1 (work/est/nl1/) · demand:CN 후보
```

| 메시지(앞부분) | 원인 | 고치는 법 |
|---|---|---|
| `없는 부품: demand:ZZ (있는 부품: …)` · `없는 기록 est:zz (최근: …)` · `없는 모형·블록: …` · `시나리오가 없습니다: SCENARIOS/….toml (있는 것: …)` | 이름 오타 | 알려 준 목록에서 고른다(`equion assemble` · `work list` · `scenario list`) |
| `자료 회차 '…'가 없습니다 (있는 회차: …)` | `[data] vintage`의 회차가 `work/data/`에 없다 — 새로 받은 폴더, 지운 회차 | `equion data build --use`(원자료가 있으면) · 있는 회차로 `equion data use 회차` · 묶음이면 `equion bundle open`으로 받는다 |
| `… — 짝지을 출처가 없습니다: series.toml [source.이름]에 inbox = "파일 이름 글롭"을 …` | 받은 상자의 파일 이름이 어느 출처의 `inbox` 글롭에도 맞지 않는다 | 출처에 `inbox = "이름_*.csv"`를 적거나 `equion data add 파일 --source 출처` |
| `… → [source.…] 틀이 맞지 않습니다: …` · `받은 원자료를 넣지 못했습니다(아무것도 넣지 않음)` | 짝은 맞지만 시점 열·열 이름 줄·시트가 정의와 다르다(칸 위치가 함께 나온다) | `equion data preview 파일`로 보고 원자료를 고치거나 `equion data define 출처 --header-row …`로 틀을 바꾼다 |
| `엑셀 97-2003 파일(.xls)은 읽지 못합니다: … — 엑셀에서 .xlsx나 .csv로 저장해 넣으세요` | `.xls`를 읽는 `xlrd`가 없다(필수 의존성이 아님) | .xlsx·.csv로 저장하거나 `xlrd`를 설치 |
| `h…(…)을(를) 되돌릴 수 없습니다 — 그 뒤의 바뀜이 같은 곳을 고쳐서 …` | 뒤의 바뀜이 같은 줄(TOML이면 같은 키)을 고쳤다 — 파일은 그대로 | 뒤의 바뀜을 먼저 되돌리거나(새것부터) · 그 파일을 통째로 그 바뀜 앞으로 `equion history revert h… --force` |
| `손으로 고친 결과 구역(블록 …)은 덮지 않았습니다 — 사람에게 묻고, 덮으려면 …` · `손으로 고친 구역(#…)은 바꾸지 않았습니다` | 노트·보고서의 결과 구역(`<!-- equion:out … -->` 안)을 손으로 고쳤다 — `note run`·`report update`가 3 | 고친 글은 구역 밖으로 옮기고 다시 · 덮어도 되면 `--force` |
| `… 항등식입니다 — 식 보정(보정항)은 추정식에만 붙입니다 …` · `…는 … 항등식(…)이 정하는 내생변수라 충격을 줄 식이 없습니다` | 항등식에는 보정항이 없다 | 항등식 오른쪽의 외생변수에 충격을 주거나 추정식을 보정한다 |
| `기간 …이(가) 전망 구간 … 밖이라 효과가 없습니다` · `기간 … — 시작이 끝보다 뒤입니다` | 충격·식 보정의 기간이 전망 구간(`[forecast] range`, 기본 `next:8`) 밖이거나 거꾸로다 | `start` · `end` · `start+N` · `end-N`이나 구간 안의 라벨로. 일부만 밖이면 쓰되 `!`로 알리고 풀 때 뺀다 |
| `판단 못 함: 검정 없음 — LM(2)·RESET을(를) NLS에는 계산하지 않음` | 그 추정법이 기준의 검정을 계산하지 않는다(`pass` = null) — `est --adopted --adopt if_pass`는 채택하지 않고 `!` | 사람이 기록(`work show est:…`)을 보고 정해 `adopt` · 또는 그 식을 OLS로 다시 쓴다 |
| `NLS 수렴 실패: … (@start로 시작값을 지정해 보세요)` · `NL-2SLS 수렴 실패: …` · `비선형 시스템 추정(…) 수렴 실패: … — 시작값(start=…, 식의 @start)을 확인하세요` · `…이 발산했습니다(계수 …) — 시작값을 바꾸세요` | 비선형 식이 그 시작값에서 수렴하지 않는다(국소 해·발산) | 식 끝의 `@start v1 v2 …`나 `start={"c(3)": 0.8}`로 시작값을 바꾼다 · 식의 정의역(로그·거듭제곱·나눗셈)을 확인 |

명령줄의 오류(종료 코드 3)는 [명령줄 참조](cli.md), 상황별 처방은 [가이드 8. 막혔을 때](../guide/08-troubleshooting.md).
