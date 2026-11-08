# 레시피: 자료

자료를 들이고 다듬는 짧은 처방. 이 문서의 예제는 위에서부터 이어서 돕니다(모두 패키지의 예제 자료를 씁니다).

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

## R1. 첫 열이 날짜가 아닌 파일 열기

`wfopen`은 첫 열을 날짜로 읽습니다. 날짜가 다른 열에 있거나 이름이 붙은 열이면 pandas로 읽어 정리한 뒤 워크파일에 넣습니다.

```python
raw = pd.DataFrame({"name": ["a", "b", "c", "d"], "date": ["2020Q1", "2020Q2", "2020Q3", "2020Q4"],
                    "SALES": [10.0, 11.0, 12.5, 13.0]})
raw[["date", "SALES"]].to_csv("sales.csv", index=False)       # 날짜를 첫 열로
w1 = eqn.wfopen("sales.csv")
print(w1.freq, w1.to_pandas(labels=True)["SALES"].tolist())
```
<!-- out -->
```text
[sales] 열기 sales.csv — 분기(Quarterly) 2020Q1~2020Q4 · 시리즈 1
Q [10.0, 11.0, 12.5, 13.0]
```

기간 라벨(`2020Q1`·`2020M3`·`2020-03`·`2020`)과 날짜(`2020-01-01`, 분기 말일 `2020-03-31`도 그 분기로)를 모두 읽습니다.
주기를 알아내지 못하면 `eqn.wfopen(path, freq="Q")`로 정해 줍니다.

## R2. 여러 파일을 한 워크파일로

```python
wf.write("part_a.csv", ["Y", "CN"])
wf.write("part_b.csv", ["I", "G"])
w2 = eqn.wfcreate("merged", "Q", "1970Q1", "2019Q4")
w2.read("part_a.csv")
w2.read("part_b.csv")
print(w2.series())
```
<!-- out -->
```text
[toy_q] write part_a.csv — 2열 200행
[toy_q] write part_b.csv — 2열 200행
[merged] 새 워크파일 — 분기(Quarterly) 1970Q1~2019Q4 (200기)
[merged] read part_a.csv — 시리즈 2
[merged] read part_b.csv — 시리즈 2
['Y', 'CN', 'I', 'G']
```

파일의 날짜가 워크파일 끝보다 뒤면 기간을 늘리고, 앞이면 그 값은 읽지 않고 알려 줍니다. 주기가 다른 파일은
[R7](#r7-월간-지표로-분기-자료를-월간으로-나누기)처럼 그 주기의 페이지에 읽습니다.

## R3. 빠진 기간이 있는 자료

파일에 기간이 빠져 있으면 빈 칸(NaN)으로 채워 열립니다. 빈 칸을 메우는 규칙은 pandas로 고른 뒤 다시 넣습니다.

```python
gap = wf.to_pandas(["Y"], labels=True).iloc[:8].drop(index=["1970Q3"])     # 한 분기 빠짐
gap.to_csv("gap.csv")
w3 = eqn.wfopen("gap.csv")
print(w3.to_pandas(labels=True)["Y"].round(1).tolist())
w3["Y"] = w3["Y"].interpolate()                                             # 선형 보간
print(round(w3.elem("Y", "1970Q3"), 1))
```
<!-- out -->
```text
[gap] 열기 gap.csv — 분기(Quarterly) 1970Q1~1971Q4 · 시리즈 1 · 빠진 기간 1개는 빈 칸으로
[291.5, 294.7, nan, 295.9, 299.7, 306.7, 310.0, 308.5]
295.3
```

## R4. 이름 바꾸기·복사하기 — 그리고 `C`라는 열

시리즈 이름 바꾸기는 복사 후 지우기입니다. `C`(상수항)·함수 이름(`LOG`·`D` …)인 열은 방정식에 쓸 수 없으므로 열 때 경고하고,
다른 이름으로 옮겨 씁니다.

```python
raw = pd.DataFrame({"period": ["2020Q1", "2020Q2", "2020Q3"], "C": [1.0, 2.0, 3.0]})
raw.to_csv("with_c.csv", index=False)
import warnings
with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always")
    w4 = eqn.wfopen("with_c.csv")
print(str(caught[0].message)[:60])
w4.data.rename(columns={"C": "CONS"}).to_csv("renamed.csv", index_label="period")
print(eqn.wfopen("renamed.csv").series())
```
<!-- out -->
```text
[with_c] 열기 with_c.csv — 분기(Quarterly) 2020Q1~2020Q3 · 시리즈 1
[경고] 방정식에서 쓸 수 없는 열 이름: C — C는 상수항, LOG·EXP·ABS·SQRT·D·DLOG는
[renamed] 열기 renamed.csv — 분기(Quarterly) 2020Q1~2020Q3 · 시리즈 1
['CONS']
```

이미 열린 워크파일 안에서는 `wf["NEW"] = wf["OLD"]` 다음 `del wf["OLD"]`.

## R5. 파생 시리즈를 한꺼번에

```python
for v in ("Y", "CN", "I"):
    wf.genr(f"G_{v} = {v}.yoy")              # 전년동기대비 %
    wf.genr(f"L_{v} = log({v})")
print(wf.series("G_*"), round(wf.elem("G_Y", "2019Q4"), 2))
```
<!-- out -->
```text
['G_Y', 'G_CN', 'G_I'] -0.35
```

## R6. 분기 ↔ 연간

```python
ya = wf.convert("Y", "A")                                # 흐름(agg='sum')은 합
ra = wf.convert("R", "A")                                # 금리(agg='mean')는 평균
print(round(float(ya.iloc[-1]), 1), round(float(ra.iloc[-1]), 3))
ann = wf.page("ann", "A")                                # 연간 합을 다시 분기로 나눌 때는 연간 페이지에서
wf.convert("Y", ann, name="YA")
print(round(float(ann.convert("YA", "Q", method="split").iloc[:4].sum()), 1) == round(float(ya.iloc[0]), 1))
```
<!-- out -->
```text
2498.6 2.892
[ann] 새 워크파일 — 연(Annual) 1970~2019 (50기)
[toy_q] 페이지 ann — 연(Annual) 1970~2019
[toy_q] Y → ann.YA (sum, Q→A)
True
```

하위 기간이 하나라도 비면 그 연도는 빈 칸입니다(부분 연도 방지). 일부만 있어도 계산하려면 `complete=False`.

## R7. 월간 지표로 분기 자료를 월간으로 나누기

분기 `Y`를 월간 산업생산 `IP`의 움직임을 따라 나누되, 석 달 합이 분기 값과 정확히 같게(Chow-Lin).

```python
mon = wf.page("mon", "M")
mon.read(eqn.datasets.path("toy_m"))
wf.convert("Y", mon, method="chow-lin", indicator="IP", name="Y_M", start="2000Q1", end="2019Q4")
q_back = mon.convert("Y_M", "Q").loc["2010-01-01":"2010-10-01"].round(3).tolist()
print(q_back == wf["Y"].loc["2010-01-01":"2010-10-01"].round(3).tolist())
```
<!-- out -->
```text
[mon] 새 워크파일 — 월(Monthly) 1970M1~2019M12 (600기)
[toy_q] 페이지 mon — 월(Monthly) 1970M1~2019M12
[mon] read toy_m.csv — 시리즈 3
[toy_q] Y → mon.Y_M (chow-lin, Q→M)
True
```

지표가 없으면 `method="denton"`(매끄럽게 나눔), 지표가 있으면 `denton`(지표 비례)이나 `chow-lin`(지표에 회귀)을 고릅니다.

## R8. pandas와 오가기

워크파일 ↔ DataFrame은 언제든 바꿀 수 있습니다.

```python
df = wf.to_pandas(["Y", "CN", "I"], smpl=False)
df["SHARE"] = df["CN"] / df["Y"]                         # pandas로 계산
wf["SHARE"] = df["SHARE"]                                # 다시 워크파일로(날짜로 맞춰 들어간다)
print(round(wf.elem("SHARE", "2019Q4"), 4))
new = eqn.wfcreate("from_df", "Q", "1970Q1", "2019Q4")
for c in df.columns:
    new[c] = df[c]
print(new.series())
```
<!-- out -->
```text
0.738
[from_df] 새 워크파일 — 분기(Quarterly) 1970Q1~2019Q4 (200기)
['Y', 'CN', 'I', 'SHARE']
```

## R49. 원자료에서 자료 회차로 — 넣기·만들기·차이·바꾸기

프로젝트는 받은 원자료(`DATA/raw/`)를 고치지 않고, 정의(`DATA/series.toml` — 어느 열을 어떻게 읽어 어떤 시리즈로)대로 **자료 회차**를
만들어 씁니다([파일 형식](../reference/formats.md#자료-정의seriestomlderivedtxt와-자료-회차workdata)). 새 자료를 받으면 넣고 → 만들고 →
견주고 → 바꿉니다. 정의가 그대로면 새 자료로 같은 계산이 다시 됩니다.

```python
p = eqn.Project.create("data_prj", force=True)       # 예제 프로젝트 — 첫 회차를 만들어 지금 회차로
v0 = p.vintage
raw = pd.read_csv("data_prj/DATA/raw/toy_q.csv", index_col=0)
raw.loc["2019Q1":"2019Q4", "CN"] *= 1.01             # 받은 새 자료: 지난 4분기 소비 개정
raw.loc["2020Q1"] = raw.iloc[-1] * 1.005             # + 새 분기
raw.to_csv("toy_q_new.csv")
print(p.data_add("toy_q_new.csv", source="na").text())   # 틀 검사 뒤 넣기 — 명령줄 equion data add toy_q_new.csv --source na
r = p.data_build()                                   # 새 회차 — 지금 회차는 아직 그대로
print(r.text())
```
<!-- out -->
```text
[data_prj] 자료 회차 d2026-11a를 만들었습니다
[data_prj] 지금 자료 회차: d2026-11a
[data add] DATA/raw/toy_q_new.csv
  해시   f1e8be82ee1a79c4…
  출처   [source.na] DATA/raw/toy_q.csv → DATA/raw/toy_q_new.csv
  다음   equion data build → equion data use <회차>
[data_prj] 자료 회차 d2026-11b를 만들었습니다
[data build] 새 회차 d2026-11b
  시리즈 13 · 1970Q1~2020Q1
  알아서 한 것
    - na: 시점 열 A('1970Q1' 꼴) → Q 1970Q1~2020Q1
    - monthly: 시점 열 A('2000M1' 꼴) → M 2000M1~2019M12
    - CNSA: 계절조정 stl multiplicative
    - IPQ: M → Q mean
    - 시리즈마다 자료 구간이 다릅니다 — 회차는 1970Q1~2020Q1, 빈 칸은 결측
```

```python
print(p.data_diff().text())                          # 지금 회차 → 새 회차: 새 기간·개정(기간·크기)
print(p.data_impact().text())                        # 바뀐 시리즈를 쓰는 식·모형(다시 계산하지 않는다)
p.data_use(r.id)                                     # 이 회차로 바꾸기 — equion.toml [data] vintage
h = p.hs("main")                                     # [hs] range = "2005Q1:last" — 새 끝(2020Q1)까지
print(h.start, h.end, h.counts()["ok"])
```
<!-- out -->
```text
[data diff d2026-11a → d2026-11b]
  구간   1970Q1~2019Q4 → 1970Q1~2020Q1
  바뀐 시리즈 12
    CN       개정 4기(2019Q1~2019Q4) 최대 1% · 새 값 1기
    I        새 값 1기
    G        새 값 1기
    Y        새 값 1기
    R        새 값 1기
    RL       새 값 1기
    P        새 값 1기
    POIL     새 값 1기
    M2       새 값 1기
    CNSA     개정 42기(2009Q2~2019Q4) 최대 1.07% · 새 값 1기
    PI       새 값 1기
    RR       새 값 1기
  그대로 1
[data_prj] 열기 series.csv — 분기(Quarterly) 1970Q1~2019Q4 · 시리즈 13
[data impact d2026-11a → d2026-11b]
  바뀐 시리즈 12 · 새 0 · 없어진 0
  쓰는 식   demand:CN (CN·Y) · demand:I (I·R·Y) · demand:Y (CN·G·I·Y) · price:P (P·POIL·Y) · finance:RL (R·RL) · finance:M2 (M2·P·RL·Y)
  쓰는 모형  core · main · main_fixrl
  다시 할 일  그 회차로 바꾼 뒤 모형을 다시 추정·풀면 새 자료로 계산된다(저절로 하지 않는다)
[data_prj] 지금 자료 회차: d2026-11b (전: d2026-11a)
[data_prj] 열기 series.csv — 분기(Quarterly) 1970Q1~2020Q1 · 시리즈 13
[main] 채택 기록 없이 지금 자료로 추정: demand:CN, demand:I, price:P, finance:RL, finance:M2
[main] baseline(_0) dynamic 2005Q1~2020Q1: 정상 61 · 일부식 제외 0 · 실패대체 0 · 실패 0
2005Q1 2020Q1 61
```

틀이 맞지 않는 파일(시리즈가 쓰는 열이 없거나 주기가 다름)은 넣지 않고 까닭을 알립니다. 옛 회차는 그대로 남아 언제든 `p.data_use(v0)`로
돌아갈 수 있습니다. 명령줄은 `equion data list · add · build · use · diff · impact`([명령줄 참조](../reference/cli.md#equion-data)).

관련: [튜토리얼 1](../tutorial/01-data.md) · [API: Workfile](../reference/api.md#3-워크파일-workfile) · [API: Project](../reference/api.md#21-프로젝트-eqnproject)
