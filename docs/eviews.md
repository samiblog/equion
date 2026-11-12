# EViews 사용자를 위한 안내

EViews에 익숙하다면 Equion의 작업 흐름은 낯설지 않습니다. 워크파일을 열고, 표본을 정하고, 방정식 객체를 추정하고, 모델에 모아
시나리오별로 풉니다. 다른 점은 이 흐름 전체가 **평범한 Python**이라는 것입니다. 프로그램 언어를 따로 만들지 않았고(정해진 작업을 차례로 적는 Equion 스크립트
`.eqs`는 한 줄에 `equion` 명령 하나일 뿐이다), 시리즈는 pandas 객체이고, 반복·함수·외부 자료 수집은 Python 그대로 씁니다.

> EViews는 S&P Global Inc.의 등록상표입니다. Equion은 EViews 및 S&P Global과 관계가 없는 독립 구현이며, EViews의 코드·설명서·그림을
> 쓰지 않습니다. 이 문서는 개념이 어떻게 대응하는지를 사실대로 적은 안내입니다.

## 개념 대응

| 익숙한 개념 | Equion | 비고 |
|---|---|---|
| 워크파일 | `wf = eqn.wfopen("data.xlsx")` · `eqn.wfcreate("w", "Q", "2000Q1", "2030Q4")` | 저장은 `wf.save("w")` → `w.eqw/` 폴더 |
| 페이지(다른 주기) | `pg = wf.page("annual", "A")` | 주기 변환 `wf.convert("Y", pg)` |
| 표본 | `wf.smpl("2000Q1", "2019Q4")` · `wf.smpl("@all")` | 추정·풀이·genr·그래프의 기본 구간 |
| 시리즈 | `wf["Y"]` | pandas Series. 대입 `wf["X"] = …` |
| 생성 | `wf.genr("YD = Y - G")` | 표본 안만 쓴다. 자기 시차 재귀(`Z = Z(-1)*1.02`)도 된다 |
| 방정식 객체 | `eq = wf.equation("eq_cn").ls("CN c Y CN(-1)")` | `.tsls` · `.gmm` · `.liml` · `.wls` · 비선형은 `c(n)` 식 |
| 결과 보기 | `eqn.show(eq)` · `eq.coefs` · `eq.resid` | 값은 모두 pandas — 그대로 다른 Python 도구로 |
| 잔차 검정 | `eq.serial_lm(4)` · `eq.white()` · `eq.diagnostics()` | [출력 표](reference/outputs.md) |
| 계수 검정 | `eq.wald("c(2) = 0.5")` | 계수 이름 `c(1)`·`c(2)`…는 항 순서 |
| 시스템 | `s = wf.system("s")` → `.sur()` · `.three_sls()` · `.fiml()` | 식 사이 제약은 같은 `c(n)` |
| VAR · VECM | `wf.var("v", ["dlog(Y)", "R"], lags=2)` · `wf.vecm(…)` | 충격반응 `.irf()` · 분산분해 `.fevd()` |
| 모델 | `m = wf.model("m").merge(eq1, eq2).append("Y = CN + I + G")` | 방정식 파일도 `merge("model.txt")` |
| 풀이 | `m.solve()`(동적) · `m.solve(mode="static")` | 결과는 별칭 시리즈 `Y_0` |
| 시나리오와 별칭 | `m.scenario("hi_g")` → 결과 `Y_1` … | 별칭을 직접 정할 수도 있다(`alias="_hg"`) |
| 외생 경로 바꾸기 | `sc.override("G", 경로)` | 기준선 자료는 그대로 |
| 내생변수 고정 | `sc.exclude("I", "2015Q1", "2015Q4")` | 그 기간 실측(또는 준 값) |
| 조정항(add factor) | `sc.add_factor("eq_cn", 1.0)` · `sc.use_residuals()` | 식의 잔차 자리에 더한다 |
| 목표 추적 | `m.control("Y", "G", 목표, 시작, 끝)` | 도구변수를 풀어 목표 경로를 맞춘다 |
| 확률적 모의 | `m.stochastic(reps=200)` | 잔차를 다시 뽑아 반복(`coef_uncertainty=True`면 계수도) |
| 그래프 · 표 | `wf.graph("g", "Y Y_0")` · `wf.table("t", df)` | html·png·csv·xlsx로 저장 |
| 출력 모음 | `eqn.show(…)` + `equion run` 보고서 | `out/<실행ID>/report.html` |
| 프로그램 파일 | Python 스크립트 + `equion run script.py` | 매개변수 `eqn.params` · `--set` |

## 방정식 표기

시계열 표기는 거의 그대로 씁니다: `X(-1)`, `d(X)`, `dlog(X)`, `@pc(X)`, `@pcy(X)`, `@movav(X, 4)`, `@trend`, `@seas`, `X(-1 to -4)`,
`c(1)`처럼 번호 붙은 계수, `ar(1)`, `pdl(X, 4, 2)`. 여기에 Python 스타일의 `X.t(-1)`, `X.yoy`, `X.ma(4)`도 있습니다.
목록 전체: [방정식 함수·지시자](reference/functions.md).

알아 둘 점:

- **변수명은 대소문자를 가리지 않습니다.** `cpi`와 `CPI`는 같은 시리즈입니다. 시리즈와 객체(방정식·모델 …)는 이름을 함께 쓰므로,
  시리즈 `G`가 있으면 객체 이름 `g`는 쓸 수 없습니다. 객체 이름에는 `eq_`·`m_` 같은 접두사를 붙이세요.
- `C`와 함수 이름(`LOG`·`EXP`·`ABS`·`SQRT`·`D`·`DLOG`)은 시리즈 이름으로 쓸 수 없습니다.
- 식의 줄 끝에 추정 지시를 둡니다: `@inst …`(도구변수) · `@smpl S E`(이 식만의 표본) · `@coef …`(고정 계수) · `@start …`(비선형 시작값).
- 방정식 파일(`.txt`)은 한 줄에 식 하나입니다. 최상위 `=`가 없으면 추정식, `=`만 있으면 항등식, `=`와 `c(n)`이 함께 있으면 비선형 추정식입니다.

## 한 흐름을 Python으로

```python
import equion as eqn

wf = eqn.datasets.load("toy_q")
wf.smpl("1971Q1", "2019Q4")
eq_i = wf.equation("eq_i").ls("I c Y(-1) R")
eq_cn = wf.equation("eq_cn").tsls("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
m = wf.model("m_toy").merge(eq_i, eq_cn).append("Y = CN + I + G")

wf.smpl("2010Q1", "2019Q4")
m.solve()                                              # 기준선 → Y_0
sc = m.scenario("hi_g")
sc.override("G", wf["G"] * 1.1)                        # 정부지출 10% 증가
m.solve()                                              # → Y_1
wf.genr("DY = 100 * (Y_1 / Y_0 - 1)")
print(round(float(wf["DY"].mean()), 2))                # 2010~2019 평균 GDP 증가(%)
```
<!-- out -->
```text
[toy_q] 열기 toy_q.csv — 분기(Quarterly) 1970Q1~2019Q4 · 시리즈 10
[toy_q] smpl 1971Q1 ~ 2019Q4
[eq_i] OLS I — n=196, R²=0.9984
[eq_cn] TSLS CN — n=196, R²=0.9999
[toy_q] smpl 2010Q1 ~ 2019Q4
[m_toy] baseline(_0) dynamic 2010Q1~2019Q4: 정상 40 · 일부식 제외 0 · 실패대체 0 · 실패 0
[m_toy] hi_g(_1) dynamic 2010Q1~2019Q4: 정상 40 · 일부식 제외 0 · 실패대체 0 · 실패 0
7.38
```

반복은 Python으로 씁니다. 예를 들어 정부지출 증가율을 바꿔 가며:

```python
for g in (0.05, 0.10, 0.20):
    m.scenario(f"g{int(g * 100)}").override("G", wf["G"] * (1 + g))
    r = m.solve()
    gap = 100 * (wf.elem(f"Y{r.alias}", "2019Q4") / wf.elem("Y_0", "2019Q4") - 1)
    print(g, r.alias, round(gap, 2))
```
<!-- out -->
```text
[m_toy] g5(_2) dynamic 2010Q1~2019Q4: 정상 40 · 일부식 제외 0 · 실패대체 0 · 실패 0
0.05 _2 4.05
[m_toy] g10(_3) dynamic 2010Q1~2019Q4: 정상 40 · 일부식 제외 0 · 실패대체 0 · 실패 0
0.1 _3 8.11
[m_toy] g20(_4) dynamic 2010Q1~2019Q4: 정상 40 · 일부식 제외 0 · 실패대체 0 · 실패 0
0.2 _4 16.21
```

## 다르게 동작하는 것

| 주제 | Equion |
|---|---|
| 결측 입력 | 풀이 중 식의 입력이 비면 그 식만 그 기간 빼고(`partial`) 그 변수는 실측을 씁니다. 다른 식은 그대로 풉니다 — `on_missing` |
| 풀이 실패 | 블록이 수렴하지 않으면 그 기간 그 변수는 실측으로 대신하고(`fallback`) 실패 해를 다음 기간에 넘기지 않습니다 — `on_fail` |
| 기간 상태 | 풀이 결과마다 기간별 `ok`·`partial`·`fallback`·`failed`와 이유가 남습니다(`r.status()`) |
| 적합도 | `r.statistics()`가 RMSPE·MAE 등을 내고, 실측으로 대신한 기간은 뺍니다 |
| 블록 풀이 | 모델을 블록으로 나눠 Newton(해석적 자코비안)으로 풀고, 안 되면 다른 방법으로 넘어갑니다([연립 풀이](explain/solving.md)) |
| 저장 형식 | 워크파일은 폴더(`.eqw/`: JSON + numpy 압축 배열)입니다. `.wf1`은 읽지 않습니다 |
| 출력 | 표·그래프는 Equion의 형식입니다. 숫자는 같은 방법이면 같아야 하지만 표의 모양은 다릅니다 |

## 자료 옮기기

EViews에서 시리즈를 엑셀(xlsx)이나 CSV로 내보낸 뒤 `eqn.wfopen`으로 엽니다. 첫 열이 시점(날짜 또는 `2000Q1` 표기), 첫 행이 시리즈
이름이면 됩니다([파일 형식](reference/formats.md#데이터-파일읽기)). 방정식은 텍스트로 옮겨 방정식 파일로 만들고 `equion check`로
먼저 검사합니다.

```bash
equion check model.txt --data data.xlsx
```

## 결과 비교

같은 자료·같은 식·같은 방법이면 계수와 표준오차가 같아야 합니다. Equion의 회귀·검정은 외부 구현과 독립 계산으로 검증합니다
([검증 보고서](explain/validation.md)). 차이가 나면 표본(결측 처리), 상수항 포함 여부, 공분산 종류(`cov=`), 자유도 보정을 먼저 보세요.
다른 소프트웨어와 견준 결과를 외부에 공개할 때는 그 소프트웨어 라이선스의 벤치마크·공개 조항을 확인하세요.

관련: [30분 첫 모델](start/first-model.md) · [치트시트](start/cheatsheet.md) · [튜토리얼](tutorial/README.md)
