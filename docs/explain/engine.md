# 엔진 수준 API

보통은 워크파일 API(`eqn.wfopen` → `wf.equation` → `wf.model`)만 쓰면 됩니다. 이 페이지는 그 아래 층, 곧 큰 모델의 일괄 실행 스크립트가
흔히 쓰는 엔진 객체 `Data`·`Equation`·`Model`·`Scenario`·`WorkTable`과 방정식 파서·IR을 다룹니다. 이 층에서는 시점을 정수 위치로도 줄 수 있고,
풀이 옵션을 모두 직접 고를 수 있으며, 기간별 풀이 기록을 바로 읽을 수 있습니다.

워크파일 객체에서 엔진 객체로 내려가는 길도 있습니다: `wf.data`(엔진 `Data`), `eq.eq`(엔진 `Equation`), `m.engine`(엔진 `Model`).

엔진은 진행 상황을 `equion.engine` 로거로 자세히 찍습니다(`eqn.verbose`는 워크파일 요약 줄만 다룬다). 잠시 끄려면
`with equion.log.silenced():`, 계속 끄려면 `logging.getLogger("equion.engine").setLevel("WARNING")`. 경고는 그대로 보입니다.

## 층 구조

```text
워크파일 API   eqn.wfopen · wf.equation · wf.model · m.scenario · m.solve          equion/workfile/
엔진 세션      WorkTable(주기·표본·hs·forecast·번들 저장)                          equion/worktable/
엔진 객체      Data · Equation · Model · Scenario                                  equion/data · estimation · system · scenario
식 처리        parser(분류·항 분리·허용 목록) → IR(시차 잎 산술식) → compiler(블록 함수)   equion/formula · system/compiler.py
```

## Data

```python
import equion as eqn
from equion import Data, Equation, Model

data = Data(eqn.datasets.path("toy_q"))
print(data.freq, data.data.shape, data.data.index[0].date())
```
<!-- out -->
```text
[OK] 데이터 로드: toy_q.csv (200행 x 10열)
Q (200, 10) 1970-01-01
```

| 메서드·속성 | 하는 일 |
|---|---|
| `data.data` | pandas DataFrame(시점 인덱스 — 기간 첫날) |
| `data.freq` | 주기(`Q`·`M`·`A`) — 인덱스에서 추론 |
| `add_column` · `get_column` · `has_column` · `info()` | 기본 조작(이름은 대소문자 무시) |
| `ensure_seasonal_dummies()` | 분기 `_Q1`~`_Q4`, 월 `_M1`~`_M12`(보통 `@seas`가 부른다) |
| `ensure_indicator(spec)` | `@trend` · `@d(…)` · `@step(…)` 열을 만든다 |
| `extend(end)` · `fill_series(cols, method)` | 기간 늘리기(새 행 NaN, 지시자는 다시 계산) · 마지막 관측 뒤 채우기(`last`·`growth`·`trend`) |
| `indicators` | 만든 지시자 → 정의(늘릴 때 다시 만드는 데 쓴다) |

## Equation

```python
eq_i = Equation("I c Y(-1) R", data)
eq_i.process()                       # 파싱(IR) → 변수 확인 → 자료 준비 → 추정
print(eq_i.method, eq_i.target, eq_i.coef_names)
print({k: round(v, 3) for k, v in eq_i.regression_results["coefficients"].items()})
print(round(eq_i.statistics["r_squared"], 4), eq_i.statistics["n_obs"])

eq_cn = Equation("CN c Y CN(-1) @inst G R CN(-1) Y(-1)", data)
eq_cn.process()
print(eq_cn.method)
```
<!-- out -->
```text
[PARSE] I = f(3개 계수, ols)
[DATA] 관측치: 199개
[OK] I 처리 완료 (OLS, R-sq=0.9985)
ols I ['const', 'Y(-1)', 'R']
{'const': 4.481, 'Y(-1)': 0.151, 'R': -0.963}
0.9985 199
[PARSE] CN = f(3개 계수, tsls)
[DATA] 관측치: 199개
[OK] CN 처리 완료 (TSLS, R-sq=0.9999)
tsls
```

| 속성·메서드 | 뜻 |
|---|---|
| `method` | `ols` · `tsls` · `nls` · `fixed` 등 |
| `target` | 이 식이 정하는 내생변수(좌변의 첫 변수) |
| `coef_names` · `regression_results` | 계수 이름 · `coefficients`·`std_errors`·`t_values`·`p_values` |
| `statistics` | `r_squared`(중심화) · `adj_r_squared` · `durbin_watson` · `se_regression` · `ssr` · `aic` · `bic` · `log_likelihood` · `n_obs` … |
| `residuals` · `cov_params` | 표본 잔차 · 계수 공분산 |
| `set_coefficients(…)` | 외부 계수를 넣는다(`method='fixed'`) |
| `residual_series()` · `predict()` | 현재 계수로 전 기간 잔차 · 표본 안 적합값 |

설명변수를 계산하지 못하면 오류로 멈춥니다(그 항을 조용히 빼고 추정하지 않는다).

## Model과 simulate

```python
model = Model(data, [eq_i, eq_cn])
model.add_identity("Y = CN + I + G")
print([b["variables"] for b in model.block_structure()])

r = model.simulate("2010Q1", "2011Q4", mode="dynamic", verbose=False)
print(r.counts())
print(r.values.round(1).head(3))
```
<!-- out -->
```text
================================================================================
Model 초기화 시작
================================================================================

[INIT] 시스템 초기화 중...
  - 내생변수 (좌변): 2개
  - 전체 변수 (좌변+우변): 4개
  - 외생변수 (우변에만): 2개
[OK] 시스템 초기화 완료
[OK] Model 초기화 완료: 2개 방정식
================================================================================
[OK] 항등식 추가: Y
[['I'], ['CN', 'Y']]
{'ok': 8, 'partial': 0, 'fallback': 0, 'failed': 0}
               I     CN      Y
period
2010-01-01  87.2  417.5  564.5
2010-04-01  87.5  417.6  564.7
2010-07-01  87.1  417.3  564.1
```

`simulate`는 결과를 돌려주기만 하고 모델에 저장하지 않습니다. 주요 옵션:

| 인자 | 기본 | 뜻 |
|---|---|---|
| `mode` | `dynamic` | `dynamic`(시차 = 풀이 값) · `static`(시차 = 실측) · `fit`(식마다 따로, 다른 내생변수 = 실측) |
| `method` · `fallback` | `newton` · `(hybr, lm, gauss-seidel)` | 블록 풀이법과 실패 시 차례로 시도할 방법(`broyden`도 된다) |
| `tolerance` · `max_iterations` | `1e-10` · `50` | 정규화 잔차 기준 · Newton 반복 |
| `on_missing` | `exclude` | 입력 결측: 그 식만 그 기간 빼고 목표변수는 실측 · `nan` · `stop` |
| `on_fail` | `actual` | 블록 미수렴: 실측으로 대신(`fallback`) · `keep` · `nan` · `stop` |
| `add_factors` | `False` | `True`(표본 잔차) · `{식 또는 목표변수: 경로}` · `[T×식]` 배열 |
| `overrides` · `excludes` · `controls` | — | 외생 경로 · 내생 고정 · 목표 추적 |
| `mce` · `mce_method` · `terminal` | `False` · `fair-taylor` · `actual` | 선행변수 풀이 · `stacked`(전 기간 동시 Newton) · 지평 끝 값 |
| `jacobian` | `auto` | 블록이 100변수 이상이면 희소 LU · `dense` · `sparse` |
| `initial_guess` · `coefficients` | — | 첫 기간 초기값 · 계수 벡터 대체 |

기간 상태의 뜻은 [연립 풀이](solving.md#결측과-실패--기간-상태)에 있습니다.

## hs — 과거 재현을 모델에 저장

```python
from equion.log import silenced

with silenced():                                  # 기간별 진행 줄을 끈다
    res = model.hs("2010Q1", "2019Q4", hs_id="hs1")
print({k: res[k] for k in ("ok_count", "partial_count", "fallback_count", "failed_count")})
print(round(model.hs_statistics["hs1"]["Y"]["RMSPE"], 3))
out = model.save_hs_results("hs1", "results/hs1.csv")
print(out)
```
<!-- out -->
```text
{'ok_count': 40, 'partial_count': 0, 'fallback_count': 0, 'failed_count': 0}
0.3
[OK] HS 결과 저장: results/hs1.csv (40행)
results/hs1.csv
```

같은 `hs_id`로 다시 부르면 이전 결과를 덮어씁니다. 저장되는 것: `hs_solutions[hs_id]`(기간 → 변수 → 값), `hs_status[hs_id]`,
`hs_statistics[hs_id]`. 실측으로 대신한 변수-기간은 통계에서 뺍니다. `model.show_hs_summary("hs1")`는 상태 집계와 RMSPE 순위를 보입니다.

## Scenario

```python
from equion.scenario import Scenario

base = Scenario("baseline").run(model, "2015Q1", "2016Q4", verbose=False)
alt = (Scenario("hi_g")
       .shock("G", 10, "2015Q1", "2016Q4", kind="pct")     # 외생 G를 10% 높인다
       .add_factor("CN", 0.5))                             # 소비 식에 조정항 +0.5
res = alt.run(model, "2015Q1", "2016Q4", verbose=False)
print(res.pct_diff(base)["Y"].round(2).tolist())
```
<!-- out -->
```text
[2.51, 4.1, 5.28, 6.15, 6.81, 7.32, 7.69, 7.95]
```

| 메서드 | 뜻 |
|---|---|
| `override(var, 경로)` | 외생 경로를 바꾼다(또는 `exclude`한 내생의 고정 경로) |
| `exclude(var, 시작, 끝)` | 내생변수를 식 대신 경로로 고정 |
| `add_factor(식 또는 목표, 값·경로)` · `init_add_factor(var, base=시점)` | 조정항 · 기준 시점의 잔차를 이후로 유지 |
| `shock(var, 크기, 시작, 끝, kind=)` | `level`(더하기) · `pct`(%) · `add_factor` |
| `run(model, 시작, 끝)` | 결과 `ScenarioResult` — `.values` · `.diff(base)` · `.pct_diff(base)` · `.aliased()` |

모델 수준의 분석 함수: `model.multipliers(var, 크기, 시작, 끝)` · `model.stochastic(시작, 끝, reps, seed, coef_uncertainty)` ·
`model.control(목표, 도구, 경로, 시작, 끝)`. 뜻은 [시나리오와 전망](scenarios.md).

## WorkTable — 엔진 세션

드라이버가 쓰는 세션 객체입니다. 자료·방정식 파일·추정·HS·전망·번들 저장을 한 객체로 다룹니다.

```python
from pathlib import Path

from equion.worktable import WorkTable

Path("toy_model.txt").write_text("I c Y(-1) R\nCN c Y CN(-1) @inst G R CN(-1) Y(-1)\nY = CN + I + G\n", encoding="utf-8")
with silenced():
    wt = WorkTable(name="toy", freq="Q")
    wt.load_data(eqn.datasets.path("toy_q"))
    wt.load_equations("toy_model.txt")
    wt.estimate()
    res = wt.hs("2010Q1", "2019Q4", hs_id="hs1")
print(res["ok_count"], wt.model.endogenous_vars)
```
<!-- out -->
```text
40 ['CN', 'I', 'Y']
```

| 메서드 | 하는 일 |
|---|---|
| `load_data` · `load_equations` · `estimate()` | 세션 구성(추정에 실패한 식은 `wt.last_failed`) |
| `sample(s, e)` | 표본 — 이전 풀이 결과를 무효로 한다 |
| `hs(start, end, hs_id)` | 과거 재현. `start="auto"`면 모든 입력이 갖춰지는 첫 시점부터 |
| `simulate` · `forecast(start, end, exog_fill=)` · `scenario(name)` | 모의 · 전망 · 시나리오 |
| `blocks()` · `input_gaps()` · `extend(end, exog_fill=)` | 구조 · 결측 입력 · 기간 늘리기 |
| `save(path)` · `WorkTable.load(path)` | 번들(`.wt/`) 저장·열기(재추정 없이) — 새 작업은 워크파일(`.eqw`)을 권합니다 |
| `resample(freq)` | 다른 주기 자료로 새 세션 |

## 방정식 파서와 IR

방정식 글자는 파서의 허용 목록을 통과해야만 IR(시차 잎으로 펼친 산술식)이 됩니다. 추정과 풀이가 같은 IR을 쓰므로, 실측을 넣은
풀이 잔차는 추정 잔차와 같습니다.

```python
from equion.formula import ir
from equion.formula.parser import classify_line, split_terms, validate_expression

print(classify_line("Y = CN + I + G"), classify_line("CN c Y CN(-1)"), classify_line("Y = c(1) + c(2)*X"))
print(split_terms("log(Y) c log(A - B) X1 + X2"))
node = ir.build("(CPI/KRW).ma(2)")
print(ir.to_str(node))
try:
    validate_expression("X.__class__")
except Exception as e:
    print(type(e).__name__)
```
<!-- out -->
```text
identity estimated nls
['log(Y)', 'c', 'log(A - B)', 'X1 + X2']
(CPI / KRW + CPI(-1) / KRW(-1)) / 2
DSLError
```

새 시계열 함수를 더하려면 `formula/parser.py`의 `AT_FUNCTIONS`에 이름을 등록하고 `formula/ir.py`의 `_Builder.apply_function`에
펼침 규칙(시차 잎 산술식)을 넣습니다. 그러면 추정·풀이·미분이 함께 따라옵니다. 그다음 `tests/test_engine.py`의 번역 일관성 시험(A·B절)이
통과해야 합니다.

`formula/ast_formula.py`(`user_to_pandas` 등)는 옛 문자열 변환 도구로, 하위 호환을 위해 남아 있습니다. 풀이 경로에서는 쓰지 않습니다.

관련: [연립 풀이](solving.md) · [시나리오와 전망](scenarios.md) · [API 참조 — 고급](../reference/api.md)
