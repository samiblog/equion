# 레시피: 진단

```python
import pandas as pd
import equion as eqn

wf = eqn.datasets.load("toy_q")
eqs = {"투자": wf.equation("eq_i").ls("I c Y(-1) R"),
       "소비": wf.equation("eq_cn").ls("CN c Y CN(-1)"),
       "물가": wf.equation("eq_p").ls("dlog(P) c dlog(Y) dlog(POIL)")}
```
<!-- out -->
```text
[toy_q] 열기 toy_q.csv — 분기(Quarterly) 1970Q1~2019Q4 · 시리즈 10
[eq_i] OLS I — n=199, R²=0.9985
[eq_cn] OLS CN — n=199, R²=0.9999
[eq_p] OLS dlog(P) — n=199, R²=0.3271
```

## R16. 여러 식의 진단을 한 표로

```python
rows = {}
for name, e in eqs.items():
    d = e.diagnostics().data
    rows[name] = d["p값"]
print(pd.DataFrame(rows).round(3))
```
<!-- out -->
```text
                          투자     소비     물가
검정
계열상관 LM(2)             0.416  0.046  0.405
White(교차항)             0.338  0.485  0.308
Breusch-Pagan-Godfrey  0.608  0.414  0.326
Ljung-Box Q(4)         0.444  0.151  0.578
ARCH LM(1)             0.026  0.334  0.279
Jarque-Bera            0.966  0.325  0.998
RESET(1)               0.850  0.484  0.374
```

## R17. 여러 시리즈의 단위근 표

```python
eqn.verbose(0)                                  # 검정마다 찍히는 요약 줄을 끈다
rows = {}
for x in ("Y", "log(Y)", "dlog(Y)", "R", "d(R)", "RL - R"):
    a, k = wf.adf(x), wf.kpss(x)
    rows[x] = {"ADF p": a.pvalue, "KPSS p": k.pvalue, "판정": "정상" if a.pvalue < 0.05 and k.pvalue > 0.05 else "단위근 의심"}
eqn.verbose(1)
print(pd.DataFrame(rows).T)
```
<!-- out -->
```text
            ADF p    KPSS p      판정
Y        0.952186      0.01  단위근 의심
log(Y)   0.319936      0.01  단위근 의심
dlog(Y)       0.0       0.1      정상
R        0.737894      0.01  단위근 의심
d(R)          0.0       0.1      정상
RL - R   0.000003  0.044037  단위근 의심
```

두 검정이 엇갈리면(`RL − R`: ADF는 단위근을 기각, KPSS는 5%에서 정상을 기각) 결정항·시차 선택을 바꿔 보고, 이론과
함께 판단합니다(참 모형에서 `RL − R`은 AR(0.7)로 정상이다).

## R18. 구조 변화 시점 찾기

후보 시점마다 Chow 검정을 해 가장 강한 곳을 봅니다(탐색해서 고른 시점의 p값은 그대로 믿지 않는다 — 참고용).

```python
eqn.verbose(0)
stats = {f"{y}Q1": eqs["투자"].chow(f"{y}Q1").statistic for y in range(1980, 2015, 5)}
eqn.verbose(1)
print({k: round(v, 2) for k, v in stats.items()})
```
<!-- out -->
```text
{'1980Q1': 0.29, '1985Q1': 0.12, '1990Q1': 0.93, '1995Q1': 0.55, '2000Q1': 0.3, '2005Q1': 1.47, '2010Q1': 3.01}
```

## R19. 계수 제약 여러 개를 한꺼번에

```python
e = eqs["투자"]
e.wald("c(2) = 0.15")
e.wald("c(3) = -1")
e.wald("c(2) = 0.15", "c(3) = -1")             # 함께
```
<!-- out -->
```text
[eq_i] Wald 계수 제약 검정: 통계량 1.2289, p=0.2690
[eq_i] Wald 계수 제약 검정: 통계량 0.8732, p=0.3512
[eq_i] Wald 계수 제약 검정: 통계량 0.6198, p=0.5391
```

## R53. 분석을 기록으로 — 단위근·공적분·오차수정, 그리고 남기기

프로젝트에서는 분석 하나가 명령 하나(`equion an <분석> <대상>`)이고 기록 하나(`an:`)입니다. 분석 목록·옵션은 등록부(`eqn.registry.table()`,
명령줄 `equion an list`·`equion an <분석> --help`)에 있습니다. 계절조정·파생은 미리보기이고 `keep`이 정의로, ECM·VAR·VECM·시스템은
`keep`이 식 후보(`est:`)로 남깁니다 — 계산한 값을 실측 자리에 바로 쓰지 않습니다.

```python
p = eqn.Project.create("an_prj", force=True)
print(p.an("unitroot", "core", trend="ct").text())      # 명령줄 equion an unitroot core --trend ct
print(p.an("coint", "RL R").text())
e = p.an("ecm", "log(CN) log(Y)", as_name="ecm_1")
print(p.keep(e.id, as_name="cons_ecm1").text())         # 단기식을 demand:CN의 후보로 — 계수 그대로
print(p.compare(part="demand:CN").table[["R²adj", "기준"]])
```
<!-- out -->
```text
[an_prj] 자료 회차 d2026-11a를 만들었습니다
[an_prj] 지금 자료 회차: d2026-11a
[an_prj] 열기 series.csv — 분기(Quarterly) 1970Q1~2019Q4 · 시리즈 13
[an:unitroot_0001] 단위근 · 묶음 core(Y · CN · I) · 1970Q1~2019Q4 · 자료 data:d2026-11a
  Y            ADF -1.831 p=0.689 · KPSS 0.184 p=0.022 → 단위근
  CN           ADF -2.564 p=0.297 · KPSS 0.182 p=0.023 → 단위근
  I            ADF -2.142 p=0.523 · KPSS 0.249 p=0.010 → 단위근
  알아서 한 것  ADF 시차 수를 BIC로 골랐다 · 판단: ADF(귀무 단위근)·KPSS(귀무 정상) 모두 5%
  기록   an:unitroot_0001 (work/an/unitroot_0001/summary.md)
[an:coint_0001] 공적분 · RL · R · 1980Q1~2019Q4 · 자료 data:d2026-11a
  Johansen 순위(5%) 트레이스 1 · 최대 고유값 1
  알아서 한 것  Johansen — 차분 시차 1
  기록   an:coint_0001 (work/an/coint_0001/summary.md)
[an keep] an:ecm_1 → 식 후보(est:)
  est:cons_ecm1
  다음   equion compare --part … · equion hs --swap 부품=est:… · equion adopt est:…
                  R²adj  기준
기록
est:cons_ecm1  0.931958  통과
```

분석 카드(`work/an/<이름>/summary.md`)에는 그 결과를 낸 명령이 그대로 적혀 있어, 같은 자료 회차에서 그 명령을 치면 같은 결과가 새 기록으로 나옵니다.

관련: [튜토리얼 3](../tutorial/03-diagnostics.md)

## R60. 기초 통계 — 기술 통계·상관·자기상관·그랜저, 그리고 묶음

식을 세우기 전에 변수를 살펴보는 분석도 명령 하나 · 기록 하나입니다. 여러 변수는 빈칸으로 띄워 적거나(`"dlog(Y) dlog(CN)"`) 묶음 이름을 씁니다.
묶음은 `p.group_define`(명령줄 `equion group define 이름 --series Y,CN,I`)으로 `equion.toml`의 `[group]`에 남깁니다.

```python
p = eqn.Project.create("stat_prj", force=True)
print(p.an("stats", "core").text())                          # equion an stats core
print(p.an("acf", "dlog(Y)", lags=8).text())                 # equion an acf "dlog(Y)" --lags 8
print(p.an("granger", "dlog(Y) dlog(CN)", lags=2).text())    # equion an granger "dlog(Y) dlog(CN)" --lags 2
p.group_define("money", series=["M2", "R", "P"], desc="돈과 물가")
print(p.an("corr", "money").text())                          # equion an corr money
```
<!-- out -->
```text
[stat_prj] 자료 회차 d2026-11a를 만들었습니다
[stat_prj] 지금 자료 회차: d2026-11a
[stat_prj] 열기 series.csv — 분기(Quarterly) 1970Q1~2019Q4 · 시리즈 13
[an:stats_0001] 기술 통계 · 묶음 core(Y · CN · I) · 1970Q1~2019Q4 · 자료 data:d2026-11a
  Y          관측치 200 · 평균 456.9 · 표준편차 95.944 · 왜도 0.12 · 첨도 1.74 · JB p=0.001
  CN         관측치 200 · 평균 340.2 · 표준편차 68.511 · 왜도 0.12 · 첨도 1.75 · JB p=0.001
  I          관측치 200 · 평균 68.755 · 표준편차 15.834 · 왜도 0.18 · 첨도 1.65 · JB p=<0.001
  알아서 한 것  결측은 시리즈마다 뺐다 · 왜도·첨도는 표본 모멘트(정규분포의 첨도는 3), Jarque-Bera는 정규성 검정
  기록   an:stats_0001 (work/an/stats_0001/summary.md)
[an:acf_0001] 자기상관 · dlog(Y) · 1970Q2~2019Q4 · 자료 data:d2026-11a
  자기상관(시차 1~4)  +0.03 · +0.14 · +0.20 · +0.09
  Q(8) 23.56 p=0.003 → 자기상관이 있다(5%)
  95% 한계 ±0.139을 넘는 시차: 3, 5
  알아서 한 것  시차 8 · 편자기상관은 Yule-Walker(Durbin-Levinson) · 한계는 ±1.96/√n
  기록   an:acf_0001 (work/an/acf_0001/summary.md)
[an:granger_0001] Granger 인과 · dlog(Y) · dlog(CN) · 1970Q2~2019Q4 · 자료 data:d2026-11a
  5%에서 Granger 인과인 쌍이 없다
  알아서 한 것  시차 2 · 쌍마다 두 시리즈가 모두 있는 기간 — 상수 + 각자의 시차 · 귀무가설: 원인의 시차 계수가 모두 0
  기록   an:granger_0001 (work/an/granger_0001/summary.md)
[stat_prj] 열기 series.csv — 분기(Quarterly) 1970Q1~2019Q4 · 시리즈 13
[an:corr_0001] 상관 · 묶음 money(M2 · R · P) · 1970Q1~2019Q4 · 자료 data:d2026-11a
  M2 · P  +0.99 (p=<0.001)
  M2 · R  -0.83 (p=<0.001)
  R · P  -0.77 (p=<0.001)
  알아서 한 것  피어슨(값) 상관 · 공통 표본 200기 · p값은 '상관이 0'의 t 검정 — 추세가 있는 수준끼리는 상관이 크게 나오기 쉽다(차분·증가율로도 보라)
  기록   an:corr_0001 (work/an/corr_0001/summary.md)
```

카드에는 표와 차트(자기상관은 막대와 ±1.96/√n 띠, 상관은 색 격자)가 함께 남습니다. Equion Desk에서는 변수 탭에서 변수를 골라 우클릭하면
고른 수에 맞는 분석만 나옵니다(자기상관은 하나, 교차상관은 둘, 상관·그랜저는 여럿).

관련: [R53](#r53-분석을-기록으로--단위근공적분오차수정-그리고-남기기) · [등록부의 분석 목록](../reference/cli.md)
