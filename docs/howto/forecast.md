# 레시피: 전망

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

## R32. 외생 가정을 표(엑셀·CSV)로 받아 전망

가정은 보통 다른 사람이 표로 줍니다. 표를 읽어 시나리오의 `override`로 넣으면 실측 시리즈는 그대로 둡니다.

```python
assume = pd.DataFrame({"period": [f"{y}Q{q}" for y in (2020, 2021) for q in (1, 2, 3, 4)],
                       "G": [70 + 0.5 * k for k in range(8)], "R": [3.0] * 4 + [2.5] * 4, "POIL": [62.0] * 8})
assume.to_csv("assumptions.csv", index=False)
a = pd.read_csv("assumptions.csv").set_index("period")
sc = m.scenario("plan")
for v in a.columns:
    sc.override(v, a[v].to_dict())                     # {기간 라벨: 값}
r = m.forecast("2020Q1", "2021Q4", scenario="plan")
print(r.counts(), round(wf.elem("Y" + sc.alias, "2021Q4"), 1))
```
<!-- out -->
```text
[toy_q] 기간 확장 → 2021Q4 (+8)
[toy] plan(_1) dynamic 2020Q1~2021Q4: 정상 8 · 일부식 제외 0 · 실패대체 0 · 실패 0
{'ok': 8, 'partial': 0, 'fallback': 0, 'failed': 0} 654.3
```

## R33. 전망을 연간으로 모으기

```python
ya = wf.convert("Y" + sc.alias, "A", method="sum")
print({d.year: round(v, 1) for d, v in ya.dropna().items() if d.year >= 2020})
print(round((ya.iloc[-1] / ya.iloc[-2] - 1) * 100, 2), "% (2021년 성장률)")
```
<!-- out -->
```text
{2020: 2534.2, 2021: 2593.8}
2.35 % (2021년 성장률)
```

`Y_1`처럼 결과 시리즈에는 메타데이터 `agg`가 없으므로 `method="sum"`을 줍니다(원래 `Y`의 agg는 sum).

## R34. 앞 전망에 이어 더 멀리

실측이 끝난 뒤에 공백이 있으면 첫 기간부터 풀 수 없습니다(시작 앞의 내생변수 실측이 비어서). 앞 전망 값을 실측 자리에
채운 뒤 이어서 풉니다.

```python
m.scenario("baseline")
m.forecast("2020Q1", "2021Q4", exog_fill="last")
for v in m.endogenous:                                  # 앞 전망(_0)을 실측 자리에
    wf[v] = wf[v].fillna(wf[v + "_0"])
r2 = m.forecast("2022Q1", "2022Q4", exog_fill="last")
print(r2.counts())
```
<!-- out -->
```text
[toy] baseline(_0) dynamic 2020Q1~2021Q4: 정상 8 · 일부식 제외 0 · 실패대체 0 · 실패 0
[toy_q] 기간 확장 → 2022Q4 (+4)
[toy] baseline(_0) dynamic 2022Q1~2022Q4: 정상 4 · 일부식 제외 0 · 실패대체 0 · 실패 0
{'ok': 4, 'partial': 0, 'fallback': 0, 'failed': 0}
```

## R35. 굴리는 예측 평가

추정 끝을 한 해씩 늘리며 다음 해를 동적으로 풀어, 예측 오차가 어떻게 달라지는지 봅니다.

```python
eqn.verbose(0)
ev = eqn.datasets.load("toy_q")
e_i, e_cn = ev.equation("e_i"), ev.equation("e_cn")
mv = ev.model("mv").merge(e_i.ls("I c Y(-1) R"), e_cn.ls("CN c Y CN(-1)")).append("Y = CN + I + G")
rows = {}
for end in range(2010, 2019):
    ev.smpl("1970Q1", f"{end}Q4")
    e_i.ls("I c Y(-1) R")                                  # 다시 추정하면 모델은 다음 풀이 때 새 계수를 쓴다
    e_cn.tsls("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
    r = mv.solve(f"{end + 1}Q1", f"{end + 1}Q4")
    err = (r.values["Y"] / ev["Y"].loc[r.values.index] - 1) * 100
    rows[end + 1] = round(float(err.abs().mean()), 3)
eqn.verbose(1)
print(rows)
```
<!-- out -->
```text
{2011: 0.325, 2012: 0.373, 2013: 0.308, 2014: 0.444, 2015: 0.154, 2016: 0.191, 2017: 0.304, 2018: 0.253, 2019: 0.206}
```

관련: [튜토리얼 6](../tutorial/06-forecast.md)

## R51. 전망 기록 — 가정 세트·보정항·시나리오

프로젝트의 전망은 가정 세트(`ASSUMPTIONS/이름.csv`)·보정항(`ADDFACTORS/이름.toml`)·시나리오(`SCENARIOS/이름.toml`)로 풀고 기록을 남깁니다
([파일 형식](../reference/formats.md#가정보정항시나리오assumptionsaddfactorsscenarios)). 계산한 값은 실측 자리에 쓰지 않고, 칸마다 값의 종류
(실측·해·가정·채움)가 따라갑니다. 명령줄은 `equion sim [시나리오…]`.

```python
p = eqn.Project.create("fc_prj", force=True)   # 예제 프로젝트 — 가정 base · 보정항 base · 시나리오 oil20
b = p.sim(as_name="base_1")                    # 기준선 — [forecast] range = next:8
print(b.text())
print(b.flags.loc["2019Q4":"2020Q2", ["Y", "G", "POIL", "R"]])
o = p.sim("oil20", as_name="oil_1", vs="sim:base_1")
print(o.text())
```
<!-- out -->
```text
[fc_prj] 자료 회차 d2026-11a를 만들었습니다
[fc_prj] 지금 자료 회차: d2026-11a
[fc_prj] 열기 series.csv — 분기(Quarterly) 1970Q1~2019Q4 · 시리즈 13
[main] 채택 기록 없이 지금 자료로 추정: demand:CN, demand:I, price:P, finance:RL, finance:M2
[fc_prj] 기간 확장 → 2021Q4 (+8)
[main] baseline(_0) dynamic 2020Q1~2021Q4: 정상 8 · 일부식 제외 0 · 실패대체 0 · 실패 0
[sim:base_1] main · base · 2020Q1~2021Q4 dynamic · 정상 8 · 일부식 제외 0 · 실패대체 0 · 실패 0
  연간 증가율  2020: Y 0.89% · CN 0.87% · I -0.25% · P 2.52% │ 2021: Y 1.74% · CN 1.65% · I 1.97% · P 2.58%
  가정   base: G·POIL 16칸 · 채움(last) R 8칸
  보정항  base: demand:CN last(+0.654) · demand:I decay
  알아서 한 것  구간 next:8 → 2020Q1~2021Q4 · 채택 기록 없이 지금 자료로 추정: demand:CN, demand:I, price:P, finance:RL, finance:M2 · 보정항 규칙 값 16칸 · 가정 16칸(G, POIL) · 외생 R 8칸을 채움(last)
  기록   sim:base_1 (work/sim/base_1/)
         Y   G POIL   R
period
2019Q4  실측  실측   실측  실측
2020Q1   해  가정   가정  채움
2020Q2   해  가정   가정  채움
[fc_prj] 열기 series.csv — 분기(Quarterly) 1970Q1~2019Q4 · 시리즈 13
[main] 채택 기록 없이 지금 자료로 추정: demand:CN, demand:I, price:P, finance:RL, finance:M2
[fc_prj] 기간 확장 → 2021Q4 (+8)
[main] baseline(_0) dynamic 2020Q1~2021Q4: 정상 8 · 일부식 제외 0 · 실패대체 0 · 실패 0
[main] oil20(_1) dynamic 2020Q1~2021Q4: 정상 8 · 일부식 제외 0 · 실패대체 0 · 실패 0
[sim:oil_1] main · oil20 · 2020Q1~2021Q4 dynamic · 정상 8 · 일부식 제외 0 · 실패대체 0 · 실패 0
  연간 증가율  2020: Y 0.89% · CN 0.87% · I -0.25% · P 2.78% │ 2021: Y 1.74% · CN 1.65% · I 1.97% · P 2.58%
  가정   base: G·POIL 16칸 · 채움(last) R 8칸
  보정항  base: demand:CN last(+0.654) · demand:I decay
  시나리오  oil20 (유가 20% 상승): POIL +20% start~end
  기준선 대비(끝 기 수준)  Y +0.00% · CN +0.00% · I +0.00% · P +0.25% · RL +0.00% · M2 +0.26%
  비교   vs sim:base_1 — 2020 P 2.52% → 2.78% (+0.26%p) · 2020 M2 3.35% → 3.59% (+0.24%p) · 2021 M2 4.28% → 4.31% (+0.03%p)
  알아서 한 것  구간 next:8 → 2020Q1~2021Q4 · 채택 기록 없이 지금 자료로 추정: demand:CN, demand:I, price:P, finance:RL, finance:M2 · 보정항 규칙 값 16칸 · 가정 16칸(G, POIL) · 외생 R 8칸을 채움(last)
  기록   sim:oil_1 (work/sim/oil_1/)
```

새 자료 회차로 바꾼 뒤 `p.sim(vs="sim:base_1")`이면 지난 전망과 연간 증가율을 견주고, `p.sim(vintage="d…")`는 옛 회차로 같은 가정을 풀어
자료 개정의 몫만 따로 봅니다.

## R61. 시나리오를 명령으로 쓰기 — 충격 표

시나리오 파일(`SCENARIOS/이름.toml`)은 손으로 써도 되고 `scenario_define`(명령줄 `equion scenario define`)으로 써도 됩니다. 충격 한 줄은
`변수=크기[%][@처음[:끝]]` — `%`가 있으면 경로를 그만큼 % 올리고, 없으면 그 값을 더합니다. 기간을 빼면 전망 구간 처음부터 끝까지입니다.
쓰기 전에 변수·식·가정 세트·기간을 검사하고, 준 것만 바꾸며(충격 목록은 주면 통째로), 바뀜 기록에 남깁니다. 풀기는 그대로 `sim`.

```python
p = eqn.Project.create("sc_prj", force=True)
r = p.scenario_define("oil_rate", desc="유가와 금리 동반 상승", shocks=["POIL=+20%", "R=+0.5@start:start+3"],
                      addfactor=["demand:CN=-0.2@start:start+1"])
print(r.text())
with open(f"{p.root}/SCENARIOS/oil_rate.toml", encoding="utf-8") as f:
    print(f.read())
print(p.sim("oil_rate").text())
```
<!-- out -->
```text
[sc_prj] 자료 회차 d2026-11a를 만들었습니다
[sc_prj] 지금 자료 회차: d2026-11a
[sc_prj] 열기 series.csv — 분기(Quarterly) 1970Q1~2019Q4 · 시리즈 13
[scenario define] SCENARIOS/oil_rate.toml — 새 시나리오
  충격 2 · 식 보정 1
  바뀜 기록  h0002
  다음   equion sim oil_rate
desc = "유가와 금리 동반 상승"

[[shock]]
var = "POIL"
from = "start"
pct = 20

[[shock]]
var = "R"
from = "start"
to = "start+3"
value = 0.5

[[addfactor]]
eq = "demand:CN"
from = "start"
to = "start+1"
value = -0.2

[sc_prj] 열기 series.csv — 분기(Quarterly) 1970Q1~2019Q4 · 시리즈 13
[main] 채택 기록 없이 지금 자료로 추정: demand:CN, demand:I, price:P, finance:RL, finance:M2
[sc_prj] 기간 확장 → 2021Q4 (+8)
[main] baseline(_0) dynamic 2020Q1~2021Q4: 정상 8 · 일부식 제외 0 · 실패대체 0 · 실패 0
[main] oil_rate(_1) dynamic 2020Q1~2021Q4: 정상 8 · 일부식 제외 0 · 실패대체 0 · 실패 0
[sim:2026-11_oil_rate] main · oil_rate · 2020Q1~2021Q4 dynamic · 정상 8 · 일부식 제외 0 · 실패대체 0 · 실패 0
  연간 증가율  2020: Y 0.46% · CN 0.46% · I -1.05% · P 2.66% │ 2021: Y 1.96% · CN 1.84% · I 2.48% · P 2.63%
  가정   base: G·POIL 16칸 · 채움(last) R 8칸
  보정항  base: demand:CN last(+0.654) · demand:I decay
  시나리오  oil_rate (유가와 금리 동반 상승): POIL +20% start~end · R +0.5 start~start+3 · 보정 demand:CN -0.2 start~start+1
  기준선 대비(끝 기 수준)  Y -0.12% · CN -0.12% · I -0.16% · P +0.22% · RL +0.11% · M2 +0.07%
  알아서 한 것  구간 next:8 → 2020Q1~2021Q4 · 채택 기록 없이 지금 자료로 추정: demand:CN, demand:I, price:P, finance:RL, finance:M2 · 보정항 규칙 값 16칸 · 가정 16칸(G, POIL) · 외생 R 8칸을 채움(last)
  기록   sim:2026-11_oil_rate (work/sim/2026-11_oil_rate/)
```

명령줄로는 `equion scenario define oil_rate --shock POIL=+20% --shock R=+0.5@start:start+3`, 목록은 `equion scenario list`, 지우기는
`equion scenario remove 이름`(바뀜 기록에서 되돌릴 수 있습니다). Equion Desk의 시나리오 폼이 같은 일을 표로 합니다.

관련: [R51](#r51-전망-기록--가정-세트보정항시나리오) · [파일 형식](../reference/formats.md#가정보정항시나리오assumptionsaddfactorsscenarios)
