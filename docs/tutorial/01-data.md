# 1. 자료 다루기

워크파일을 열고, 시리즈를 읽고 쓰고, 표본을 정하고, 식으로 새 시리즈를 만들고, 기간을 늘리고, 주기를 바꾸고,
계절조정하고, 파일로 주고받는 법을 배웁니다.

## 1.1 워크파일 열기

워크파일은 시리즈와 표본, 그리고 앞으로 만들 방정식·모델 같은 객체를 담는 작업 단위입니다. 세 가지로 엽니다.

```python
import numpy as np
import pandas as pd
import equion as eqn

wf = eqn.datasets.load("toy_q")                     # ① 패키지에 든 예제 자료
print(wf)
print(wf.freq, wf.smpl(), len(wf.data))
```
<!-- out -->
```text
[toy_q] 열기 toy_q.csv — 분기(Quarterly) 1970Q1~2019Q4 · 시리즈 10
<워크파일 toy_q: 분기(Quarterly) 1970Q1~2019Q4 · 시리즈 10 · 객체 0 · smpl 1970Q1~2019Q4>
Q ('1970Q1', '2019Q4') 200
```

② 파일(xlsx·csv)은 `eqn.wfopen`으로 엽니다. 첫 열이 날짜(`2000-01-01`)나 기간 라벨(`2000Q1`·`2000M3`·`2000`)이면
주기를 스스로 알아냅니다. 예제 자료도 CSV 파일이라 직접 열어 볼 수 있습니다.

```python
path = eqn.datasets.path("toy_q")
with open(path, encoding="utf-8") as f:
    for line in f.read().splitlines()[:3]:
        print(line[:60] + " …")
wf_file = eqn.wfopen(path, name="from_file")
print(wf_file.freq, wf_file.series()[:5])
```
<!-- out -->
```text
period,CN,I,G,Y,R,RL,P,POIL,M2,CNNSA …
1970Q1,221.740608,42.853018,26.903033,291.496660,5.426436,,5 …
1970Q2,224.830466,43.332271,26.504027,294.666765,5.627462,,5 …
[from_file] 열기 toy_q.csv — 분기(Quarterly) 1970Q1~2019Q4 · 시리즈 10
Q ['CN', 'I', 'G', 'Y', 'R']
```

③ 빈 워크파일을 만들고 값을 채울 수도 있습니다(모의 실험·가정 경로 만들기에 씁니다).

```python
sim = eqn.wfcreate("sim", "Q", "2020Q1", "2025Q4")
sim["X"] = np.arange(len(sim.data), dtype=float)      # 전체 기간에 배열을 넣는다
sim["G"] = 1.5                                         # 스칼라는 모든 기간에 같은 값
print(sim.to_pandas(labels=True).head(3))
```
<!-- out -->
```text
[sim] 새 워크파일 — 분기(Quarterly) 2020Q1~2025Q4 (24기)
          X    G
2020Q1  0.0  1.5
2020Q2  1.0  1.5
2020Q3  2.0  1.5
```

빠진 기간이 있는 파일(예: 한 분기가 없는 분기 자료)은 빈 칸(NaN)으로 채워 열립니다 — 시차가 어긋나지 않습니다.
같은 날짜가 두 번 있으면 오류로 알려 줍니다.

## 1.2 시리즈 읽기와 쓰기

`wf["이름"]`은 pandas Series를 돌려줍니다(복사본 — 바꿔도 워크파일은 그대로). 이름은 대소문자를 가리지 않습니다.

```python
y = wf["y"]                       # Y와 같다
print(type(y).__name__, y.index[0].date(), round(y.iloc[-1], 2))
print(wf.elem("Y", "2010Q1"))     # 한 기간의 값은 elem
print(wf.to_pandas(["Y", "CN"], labels=True).loc["2010Q1":"2010Q3"].round(2))
```
<!-- out -->
```text
Series 1970-01-01 625.71
564.92656
             Y      CN
2010Q1  564.93  418.06
2010Q2  565.29  417.56
2010Q3  565.21  417.50
```

`wf.to_pandas(..., labels=True)`는 인덱스가 `2010Q1` 같은 기간 라벨인 DataFrame입니다. 기간 라벨로 자르고 싶을 때 씁니다
(날짜 인덱스의 `wf["Y"].loc["2010Q1"]`은 pandas 3.1부터 없어질 예정이라 권하지 않습니다).

시리즈 쓰기는 대입입니다. Series를 넣으면 날짜로 맞춰 들어가고, 없는 기간은 빈 칸입니다.

```python
wf["YD"] = wf["Y"] - wf["G"]                      # 가처분소득 비슷한 것
wf["SHORT"] = wf["Y"].iloc[:4]                    # 처음 4기만 값이 있다
print(wf["SHORT"].notna().sum(), wf.series("Y*"))
del wf["SHORT"]
```
<!-- out -->
```text
4 ['Y', 'YD']
```

`C`(상수항)와 함수 이름(`LOG`·`EXP`·`ABS`·`SQRT`·`D`·`DLOG`)은 시리즈 이름으로 쓸 수 없습니다 — 방정식에서 다른 뜻이기 때문입니다.

<!-- error -->
```python
wf["C"] = 1.0
```
<!-- out -->
```text
ValueError: 'C'은(는) 상수항·계수(c, c(1)…) 이름이라 변수로 쓸 수 없습니다 — 시리즈 이름을 바꾸세요(예: CONS)
```

## 1.3 표본

표본(smpl)은 추정·풀이·genr·그래프가 기본으로 쓰는 기간입니다. 설정하면 그 뒤의 작업이 모두 그 구간에서 이뤄집니다.

```python
wf.smpl("2000Q1", "2019Q4")
print(wf.smpl())
wf.smpl("@all")                   # 전체 기간으로
print(wf.smpl())
wf.smpl("@first", "1989Q4")       # 처음 ~ 1989Q4
print(wf.smpl())
wf.smpl("@all")
```
<!-- out -->
```text
[toy_q] smpl 2000Q1 ~ 2019Q4
('2000Q1', '2019Q4')
[toy_q] smpl 전체
('1970Q1', '2019Q4')
[toy_q] smpl 1970Q1 ~ 1989Q4
('1970Q1', '1989Q4')
[toy_q] smpl 전체
```

## 1.4 식으로 시리즈 만들기 — genr

`genr`은 방정식과 같은 식 문법(시차 `X(-1)`, `log`·`dlog`·`d`, `.yoy`·`.qoq`, `@pcy`, `@trend` …)으로 계산해
**표본 안만** 씁니다. 표본 밖 값은 건드리지 않습니다.

```python
wf.genr("GY = Y.yoy")                          # 전년동기대비 증가율(%)
wf.genr("LY = log(Y)")
wf.genr("TR = @trend")                         # 0, 1, 2, …
print(wf.to_pandas(["Y", "GY", "LY", "TR"], labels=True).loc["1971Q1":"1971Q2"].round(3))
```
<!-- out -->
```text
              Y     GY     LY   TR
1971Q1  299.717  2.820  5.703  4.0
1971Q2  306.712  4.088  5.726  5.0
```

```python
wf.smpl("2019Q1", "2019Q4")
wf.genr("FLAG = 1")                            # 표본 안만 1
wf.smpl("@all")
print(int(wf["FLAG"].sum()), wf["FLAG"].isna().sum())
```
<!-- out -->
```text
[toy_q] smpl 2019Q1 ~ 2019Q4
[toy_q] smpl 전체
4 196
```

자기 시차가 있는 식은 앞에서부터 한 기씩 계산합니다 — 성장 경로 만들기에 좋습니다.

```python
sim.genr("PATH = 100")
sim.smpl("2020Q2", "2025Q4")
sim.genr("PATH = PATH(-1) * 1.01")             # 분기 1% 성장
sim.smpl("@all")
print(sim.to_pandas(["PATH"], labels=True).round(2).head(4))
```
<!-- out -->
```text
[sim] smpl 2020Q2 ~ 2025Q4
[sim] smpl 전체
          PATH
2020Q1  100.00
2020Q2  101.00
2020Q3  102.01
2020Q4  103.03
```

워크파일에 쓰지 않고 계산만 하려면 `eval`, Python 계산을 그대로 쓰려면 `genr(이름, 함수)`입니다.

```python
print(wf.eval("dlog(Y) * 400").dropna().round(2).head(3).tolist())   # 연율 성장률
wf.genr("GAP", lambda d: d.Y / d.Y.rolling(8).mean() - 1)            # d는 시리즈 DataFrame
print(round(wf.elem("GAP", "2010Q1"), 4))
```
<!-- out -->
```text
[4.33, -0.28, 1.99]
0.0057
```

## 1.5 설명·단위 — 메타데이터

시리즈마다 설명·단위·출처·집계 방식(`agg` — 낮은 주기로 바꿀 때의 기본)을 달 수 있고, 워크파일과 함께 저장됩니다.

```python
wf.meta("YD", desc="소득 − 정부지출", unit="조원(가상)", agg="sum")
print(wf.meta("YD"))
eqn.show(wf.metadata("Y*"))
```
<!-- out -->
```text
{'desc': '소득 − 정부지출', 'unit': '조원(가상)', 'agg': 'sum'}
워크파일 toy_q 시리즈
─────────────────────────────────────────────────────────────────────────────
                    설명      단위                출처   집계      처음       끝  관측치 메모
시리즈
Y    국민소득 = CN + I + G  조원(가상)  Equion 예제 자료(가상)  sum  1970Q1  2019Q4  200
YD           소득 − 정부지출  조원(가상)                    sum  1970Q1  2019Q4  200
─────────────────────────────────────────────────────────────────────────────
```

## 1.6 기간 늘리기와 앞날 채우기

전망하려면 기간을 늘리고 외생변수의 앞날을 채워야 합니다. `extend`는 기간을 늘리고(새 기간은 빈 칸, `@trend`·계절 더미는
저절로 이어진다), `fill`은 마지막 관측 다음을 규칙으로 채웁니다.

```python
wf.extend("2021Q4")
print(wf.smpl(), wf["G"].iloc[-8:].isna().all())
wf.fill("G", method="trend", window=20)       # 최근 20기 평균 증분 지속('last' 유지, 'growth' 평균 성장률)
wf.fill("R", method="last")
print(wf.to_pandas(["G", "R"], labels=True).loc["2019Q3":"2020Q2"].round(2))
```
<!-- out -->
```text
[toy_q] 기간 확장 → 2021Q4 (+8)
('1970Q1', '2021Q4') True
            G     R
2019Q3  67.88  2.72
2019Q4  69.15  3.16
2020Q1  69.48  3.16
2020Q2  69.81  3.16
```

## 1.7 주기 바꾸기

낮은 주기로는 평균·합·처음·끝·최대·최소로 모읍니다(기본은 메타데이터의 `agg`). 하위 기간이 하나라도 비면 그 기간은 빈 칸입니다.

```python
ya = wf.convert("Y", "A")                      # Y의 agg는 sum → 연간 합(돌려주는 것은 연간 pandas Series)
for d, v in ya.dropna().tail(2).items():
    print(d.year, round(v, 1))
print(wf.convert("R", "A", method="last").iloc[:2].round(3).tolist())
```
<!-- out -->
```text
2018 2489.6
2019 2498.6
[5.744, 6.234]
```

다른 주기의 시리즈를 함께 두려면 **페이지**를 만듭니다. 높은 주기로 나눌 때는 반복(`constant`)·균등 분할(`split`)·
선형 보간(`linear`)·Denton·Chow-Lin을 고릅니다. Denton과 Chow-Lin은 낮은 주기 값을 정확히 지키면서 지표의 움직임을 따릅니다.

```python
mon = wf.page("mon", "M")                      # 같은 기간의 월간 페이지
mon.read(eqn.datasets.path("toy_m"))           # 페이지에 월간 지표(산업생산 IP 등)를 읽는다
wf.convert("Y", mon, method="denton", indicator="IP", name="Y_M", start="2000Q1", end="2019Q4")   # 지표가 있는 구간만
chk = mon.convert("Y_M", "Q").loc["2010-01-01":"2010-07-01"]      # 다시 분기로 합치면 원래 값
print(chk.round(3).tolist(), wf["Y"].loc["2010-01-01":"2010-07-01"].round(3).tolist())
```
<!-- out -->
```text
[mon] 새 워크파일 — 월(Monthly) 1970M1~2021M12 (624기)
[toy_q] 페이지 mon — 월(Monthly) 1970M1~2021M12
[mon] read toy_m.csv — 시리즈 3
[toy_q] Y → mon.Y_M (denton, Q→M)
[564.927, 565.294, 565.211] [564.927, 565.294, 565.211]
```

## 1.8 계절조정

`seas`는 STL(기본) 또는 고전 분해로 계절 성분을 떼어 `이름_SA`(조정 계열)와 `이름_SF`(계절 성분)를 씁니다.
`CNNSA`는 계절조정 전 소비입니다.

```python
r = wf.seas("CNNSA")
print(wf.series("CNNSA*"))
print(wf.to_pandas(["CNNSA", "CNNSA_SA", "CNNSA_SF"], labels=True).loc["2010Q1":"2010Q4"].round(2))
```
<!-- out -->
```text
[toy_q] 계절조정 CNNSA — stl·additive → CNNSA_SA·CNNSA_SF
['CNNSA', 'CNNSA_SA', 'CNNSA_SF']
         CNNSA  CNNSA_SA  CNNSA_SF
2010Q1  429.94    417.72     12.22
2010Q2  410.13    419.43     -9.30
2010Q3  424.51    419.18      5.33
2010Q4  410.07    418.35     -8.27
```

월간 자료도 같습니다. 곱셈 꼴 계절성이면 `model="multiplicative"`.

```python
wm = eqn.datasets.load("toy_m")
wm.seas("IP", model="multiplicative")
print(wm.to_pandas(["IP", "IP_SA", "IP_SF"], labels=True).loc["2010M1":"2010M3"].round(3))
```
<!-- out -->
```text
[toy_m] 열기 toy_m.csv — 월(Monthly) 2000M1~2019M12 · 시리즈 3
[toy_m] 계절조정 IP — stl·multiplicative → IP_SA·IP_SF
             IP    IP_SA  IP_SF
2010M1  111.355  118.390  0.941
2010M2  112.811  117.643  0.959
2010M3  123.721  117.990  1.049
```

## 1.9 파일로 주고받기와 저장

```python
wf.write("toy_out.xlsx", ["Y", "CN", "I"])                 # 기본은 표본 구간
wf.write("toy_out.csv", ["Y", "CN", "I"])
other = eqn.wfcreate("other", "Q", "1970Q1", "2019Q4")
print(other.read("toy_out.csv"))                           # 파일의 시리즈를 가져온다
wf.save("tutorial1")                                       # tutorial1.eqw/ 폴더
again = eqn.wfopen("tutorial1.eqw")
print(again.smpl(), again.meta("YD")["desc"], list(again.pages))
```
<!-- out -->
```text
[toy_q] write toy_out.xlsx — 3열 208행
[toy_q] write toy_out.csv — 3열 208행
[other] 새 워크파일 — 분기(Quarterly) 1970Q1~2019Q4 (200기)
[other] read toy_out.csv — 시리즈 3
['Y', 'CN', 'I']
[mon] 저장 → tutorial1.eqw/pages/mon.eqw (시리즈 4 · 객체 0)
[toy_q] 저장 → tutorial1.eqw (시리즈 19 · 객체 0)
[mon] 열기 tutorial1.eqw/pages/mon.eqw (시리즈 4 · 객체 0)
[toy_q] 열기 tutorial1.eqw (시리즈 19 · 객체 0 · 페이지 1)
('1970Q1', '2021Q4') 소득 − 정부지출 ['mon']
```

워크파일 저장(`.eqw`)에는 시리즈·표본·메타데이터·페이지와, 다음 튜토리얼부터 만들 방정식(계수·잔차)·모델·시나리오·
그래프·표가 모두 들어갑니다. 다시 열면 재추정 없이 그대로 돌아옵니다.

## 정리

| 하려는 일 | 코드 |
|---|---|
| 열기 | `eqn.datasets.load` · `eqn.wfopen` · `eqn.wfcreate` |
| 읽기·쓰기 | `wf["Y"]` · `wf.elem` · `wf.to_pandas(labels=True)` · `wf["X"] = …` · `del wf["X"]` |
| 표본 · 식 | `wf.smpl` · `wf.genr` · `wf.eval` |
| 기간 · 주기 · 계절 | `wf.extend` · `wf.fill` · `wf.convert` · `wf.page` · `wf.seas` |
| 파일 | `wf.write` · `wf.read` · `wf.save` · `eqn.wfopen("….eqw")` |

다음: [2. 방정식 추정](02-estimation.md). 관련 레시피: [자료 레시피](../howto/data.md).
