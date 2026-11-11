# Equion — estimate and solve single equations and simultaneous-equation models

**Equion** is a Python package for the whole workflow of an econometric model: estimate single equations,
assemble them into a (non-linear) simultaneous system, solve it period by period, run historical simulations,
forecasts and scenarios, and analyse the results. Equations are plain text in a compact time-series notation, and
the engine is built to accept equation sets that change often — the model is an input, not code.

- Version **0.8.0** (2026-11-11) · Python 3.12+ · numpy · pandas · scipy · openpyxl · [MIT licence](LICENSE)
- Use it as a **library** (`import equion as eqn`) or from the **command line** (`equion run script.py`).
- Synthetic example data sets ship with the package (`eqn.datasets`: `toy_q`, `toy_a`, `toy_m`, `klein_like`), generated
  from known models, so every example and test runs anywhere and estimates can be compared with the truth.
- A Windows desktop app, **Equion Desk**, is planned once the package has matured.
- Most documentation is in Korean ([`docs/README.md`](docs/README.md)). In English: [getting started](docs/en/README.md),
  [your first model](docs/en/first-model.md), a [cheat sheet](docs/en/cheatsheet.md), and the generated API reference
  [`docs/reference/api.md`](docs/reference/api.md), which lists every public function and method with its signature.

## Quick start

The package is not on PyPI yet; install it from the repository:

```bash
pip install "equion[all] @ git+https://github.com/samiblog/equion"
```

```bash
equion new myproject
```

The second command creates a small project (example data, an equation file and a script). Inside it,
`equion run scripts/main.py` estimates the model, solves it, runs a scenario and a forecast, and writes a report
folder `out/<run id>/` with `report.html` (tables, interactive charts, log), `manifest.json` (versions, git commit,
parameters, input file hashes, per-period solver status) and the tables as CSV.

To work on Equion itself, clone the repository and run `uv sync` ([uv](https://docs.astral.sh/uv/); the environment
is pinned by `uv.lock`).

## A five-minute example

```python
import equion as eqn

wf = eqn.datasets.load("toy_q")                                   # workfile (example data — eqn.wfopen("file.xlsx") for yours)
eq_i = wf.equation("eq_i").ls("I c Y(-1) R")                       # investment: last quarter's income, interest rate
eq_cn = wf.equation("eq_cn").tsls("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")   # consumption (2SLS — income is endogenous)
eqn.show(eq_cn)                                                    # estimation table

m = wf.model("toy").merge(eq_i, eq_cn).append("Y = CN + I + G")    # simultaneous model (plus an identity)
wf.smpl("1990Q1", "2019Q4")
eqn.show(m.solve().summary())                                      # baseline historical simulation → series Y_0 …

m.scenario("g_up").shock("G", 10, "2015Q1", "2019Q4", kind="pct")  # scenario: government spending +10%
m.solve()                                                          # → series *_1
print(m.compare("Y").tail(4).round(1))

m.forecast("2020Q1", "2021Q4", exog_fill="trend", scenario="baseline")      # forecast
m.stability("2015Q1").show()                                       # eigenvalues of the linearised model
wf.save("toy")                                                     # → toy.eqw/
```

Every result is a pandas object, so anything else is ordinary Python: loops over scenario grids, scikit-learn
coefficients fixed into the model (`wf.equation("x").fixed(spec, coefs)`), your own plots.

## Equation notation

```text
log(CN) c log(Y - G) log(CN(-1)) @seas                # OLS, seasonal dummies
log(CN) c log(Y) log(CN(-1)) @inst log(Y(-1)) log(CN(-1)) log(G)  # 2SLS
log(CN) c log(Y) ar(1)                                # AR(1) error
log(CN) c pdl(log(Y), 8, 3) log(CN(-1))               # polynomial distributed lag
CN = c(1) * Y^c(2)  @start 1 1                        # non-linear least squares
Y = CN + I + G                                        # identity
```

Lags `X(-1)`, ranges `X(-1 to -4)`, `.qoq` / `.yoy` / `d(x, n, s)` / `dlog`, `@pc`·`@pcy`·`@movav`,
`@trend`·`@d(P)`·`@step(P)`·`@seas`, per-equation samples `@smpl`. Text is checked against an allow-list grammar
with size limits — equation text can never execute code.

## What it does

| Area | Features |
|---|---|
| Single-equation estimation | OLS, WLS, 2SLS, linear GMM (Hansen J), LIML, NLS (analytic Jacobian), fixed coefficients, AR(p) errors, PDL, error-correction models; robust covariances (HC0–HC3, HAC) |
| Diagnostics | serial-correlation LM, Ljung–Box, White, Breusch–Pagan, ARCH, Jarque–Bera, RESET, Wald, Chow, CUSUM, omitted/redundant variables; ADF, KPSS, Engle–Granger, Johansen; forecast evaluation (RMSE, Theil U, Diebold–Mariano) |
| Systems | system OLS, SUR (iterated = ML), 2SLS, 3SLS, FIML; cross-equation restrictions via shared `c(n)` or `restrict=` |
| Multivariate | VAR (lag selection, Granger causality, impulse responses, variance decomposition, forecasts), VECM (Johansen ML) |
| Model solving | block decomposition + analytic-Jacobian Newton with fallbacks, sparse LU for large blocks; dynamic / static / fit simulation; per-period status — a failed solution is never carried into the next period |
| Model use | forecasts, scenarios (overrides, excludes, add factors, shocks), stochastic simulation, control (target tracking), multipliers, model-consistent expectations (Fair–Taylor or stacked-time Newton), dynamic stability, Shapley scenario decomposition |
| Data | metadata, pages at other frequencies, frequency conversion (aggregation, Denton, Chow–Lin), seasonal adjustment (STL, classical) |
| Command line | `equion run` (report folder, exit codes 0/1/2/3, `--set`, `--smpl`, `--fail-on`, `--watch`, `--redact`), `check`, `info`, `new`, `convert` |

Estimation and solving share one intermediate representation of every equation, so "the residual of the compiled
model on actual data equals the estimation residual" holds by construction — this is checked in the test suite.

All statistics are implemented in the package itself (no external regression package). They are verified against
statsmodels and linearmodels results frozen in `tests/fixtures/`, and against independent computations (for
example 50-digit arithmetic for GMM, where the normal-equation route of the external package loses precision).

## Dependencies

Dependencies are version ranges (numpy ≥ 2.1, pandas ≥ 2.2.2, scipy ≥ 1.14, openpyxl ≥ 3.1); the repository's
own environment is pinned exactly by `uv.lock`. Optional extras: `[parquet]` (reading workfiles saved by 0.6.0 and
earlier) and `[plot]` (plotly `Figure` objects — charts themselves use a bundled copy of plotly.js).

## Development

```bash
uv run pytest
```

CI (`.github/workflows/ci.yml`) runs the suites on Linux, Windows and macOS with Python 3.12–3.14, with the
locked versions, with the lowest and the latest allowed versions, without the optional extras, checks that every
documentation example runs and prints what the page shows, and audits the locked dependencies. The tests use only
the bundled example data.
Design decisions are recorded in [`docs/DECISIONS.md`](docs/DECISIONS.md) (in Korean).

## Licence and trademarks

[MIT](LICENSE) © 2025-2026 samiblog. Third-party material bundled in the package (statistical tables, plotly.js)
is listed in [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md).

EViews is a registered trademark of S&P Global Inc. This project is independent, is not affiliated with or endorsed
by S&P Global, and does not use EViews code, documentation or images. Its workflow is designed to feel familiar to
users of such tools; the implementation is original.
