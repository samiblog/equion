# Equion documentation (English)

Equion estimates single equations and solves (non-linear) simultaneous-equation models in Python: historical
simulation, forecasts, scenarios, multipliers, stochastic simulation and stability analysis. The full documentation
is written in Korean; this English section covers getting started and points to the parts that are language-neutral.

| Page | What it covers |
|---|---|
| [Your first model](first-model.md) | data → estimation → model → historical simulation → scenario → forecast → save, in one sitting |
| [Cheat sheet](cheatsheet.md) | the commands you use most, on one page |
| [API reference](../reference/api.md) | every public function and method with its signature (generated from the code; descriptions are in Korean) |
| [Equation functions](../reference/functions.md) | the functions, time-series operators and directives allowed in equations (tables) |
| [Project README](../../README.en.md) | overview, feature list, installation |

## Install

Equion is not on PyPI yet, so install it from the repository. Inside a clone, [uv](https://docs.astral.sh/uv/) builds
the environment pinned by `uv.lock`:

```bash
uv sync
```

Into another environment:

```bash
pip install "equion[all] @ git+https://github.com/samiblog/equion"
```

The extras are `[plot]` (plotly `Figure` objects; PNG/SVG export also needs kaleido) and `[parquet]` (workfiles saved
before 0.6.0). HTML charts work without plotly. Python 3.12 or later. Check the installation:

```bash
equion info
```

## Language of messages and tables

Log messages, table headings and error messages are in Korean. The examples here silence the log
(`eqn.verbose(0)`) and print plain pandas objects, whose labels are the series and coefficient names. When you do
look at Equion's own tables, these words come up most:

| Korean | English |
|---|---|
| 계수 · 표준오차 · t값 · p값 | coefficient · standard error · t-statistic · p-value |
| 종속변수 · 목표변수 · 추정법 · 표본 · 관측치 | dependent variable · target variable · method · sample · observations |
| 조정 R² · 회귀 표준오차 · 로그우도 | adjusted R² · standard error of regression · log likelihood |
| 정상 · 일부식 제외 · 실패대체 · 실패 | ok · partial (some equations excluded) · fallback (actual value used) · failed |
| 내생 · 외생 · 블록 · 동시 · 순차 | endogenous · exogenous · block · simultaneous · recursive |
| 시나리오 · 기준선 · 별칭 | scenario · baseline · alias |
| 기각 · 기각 못 함 · 귀무가설 | rejected · not rejected · null hypothesis |
| 안정 · 단위근 · 불안정 | stable · unit root · unstable |

The period status columns and statistics keys (`ok`, `partial`, `fallback`, `failed`, `RMSPE`, `r_squared` …) are
English identifiers, so code that reads results does not depend on the language.

## Example data

`eqn.datasets` ships small synthetic data sets generated from known models, so you can compare estimates with the
true coefficients:

| Name | Frequency and span | Model |
|---|---|---|
| `toy_q` | quarterly 1970Q1–2019Q4 | investment, consumption, income identity, prices, money, a long rate (cointegrated with the policy rate) |
| `toy_a` | annual 1970–2019 | `toy_q` aggregated to years |
| `toy_m` | monthly 2000M1–2019M12 | industrial production and consumer prices before seasonal adjustment, a policy rate |
| `klein_like` | annual 1921–1990 | the structure of Klein's Model I (consumption, investment, private wages + three identities) |

```python
import equion as eqn

print(eqn.datasets.names())
```
<!-- out -->
```text
['klein_like', 'toy_a', 'toy_m', 'toy_q']
```

The real Klein Model I data are not bundled because their terms of use are unclear; if you have a copy, open it with
`eqn.datasets.klein("klein.csv")`, which renames the columns (`C` → `CONS`, `P` → `PR`, `Wp` → `WP`, …).
