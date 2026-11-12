# Cheat sheet

The commands used most often. `wf` is a workfile, `eq` an equation object, `m` a model object. Full list:
[API reference](../reference/api.md). Korean version: [치트시트](../start/cheatsheet.md).

## Data

| Task | Code |
|---|---|
| Open example data | `wf = eqn.datasets.load("toy_q")` (`toy_a` annual · `toy_m` monthly · `klein_like`) |
| Open a file (frequency inferred) | `wf = eqn.wfopen("data.xlsx")` · `eqn.wfopen("data.csv", freq="Q")` |
| Empty workfile | `wf = eqn.wfcreate("sim", "Q", "2000Q1", "2030Q4")` |
| Read and write series | `wf["Y"]` (pandas Series) · `wf["X"] = values` (whole range) · `del wf["X"]` |
| One value | `wf.elem("Y", "2010Q1")` |
| Sample | `wf.smpl("2000Q1", "2019Q4")` · `wf.smpl("@all")` · `wf.smpl()` (query) |
| Generate from an expression (inside the sample) | `wf.genr("YD = Y - G")` · `wf.genr("T2 = @trend^2")` · recursive `wf.genr("Z = Z(-1)*1.02")` |
| Evaluate only | `wf.eval("dlog(Y)*400")` |
| Table with period labels | `wf.to_pandas(["Y", "CN"], labels=True).loc["2010Q1":"2010Q4"]` |
| Descriptions and units | `wf.meta("Y", desc="income", unit="tn won", agg="sum")` · `wf.metadata()` |
| Extend and fill | `wf.extend("2025Q4")` · `wf.fill("G", method="trend")` (`last` · `growth`) |
| Frequency conversion | `wf.convert("Y", "A")` · `pg = wf.page("mon", "M")` → `wf.convert("Y", pg, method="denton")` |
| Seasonal adjustment | `wf.seas("CNNSA")` → `CNNSA_SA` · `CNNSA_SF` (`method="classical"`) |
| File input and output | `wf.write("out.xlsx", ["Y"])` · `wf.read("more.csv")` |
| Save and reopen | `wf.save("work")` → `work.eqw/` · `eqn.wfopen("work.eqw")` |

## Equations

| Task | Code |
|---|---|
| Least squares | `eq = wf.equation("eq_i").ls("I c Y(-1) R")` |
| Robust standard errors | `.ls(spec, cov="white")` · `cov="hac", lags=4` |
| Two-stage least squares | `.tsls("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")` |
| Non-linear | `.ls("Y = c(1) + c(2)*X^c(3) @start 1 1 1")` |
| Non-linear two-stage least squares | `.tsls("Y = c(1) + c(2)*X^c(3) @start 1 1 1 @inst Z1 Z2 X(-1)")` (NL-TSLS) |
| AR(1) errors · PDL | `.ls("CN c Y ar(1)")` · `.ls("CN c pdl(Y, 4, 2)")` |
| GMM · LIML · WLS | `.gmm(spec + " @inst …")` · `.liml(…)` · `.wls(spec, weights="W")` |
| Fixed coefficients | `wf.equation("f").fixed("CN c Y", [10, 0.6])` |
| Results | `eqn.show(eq)` · `eq.coefs` · `eq.stderrs` · `eq.pvalues` · `eq.resid` · `eq.fitted` · `eq.stats` |
| Diagnostics | `eq.diagnostics()` · `eq.serial_lm(4)` · `eq.white()` · `eq.reset()` · `eq.chow("2000Q1")` |
| Coefficient restrictions | `eq.wald("c(2) = 0.5")` |
| Unit roots and cointegration | `wf.adf("Y")` · `wf.kpss("Y")` · `wf.coint("RL", "R")` · `wf.johansen("log(M2) log(P) log(Y) RL")` |
| Error-correction model | `wf.ecm("e1", "RL", ["R"])` |

## Models

| Task | Code |
|---|---|
| Build | `m = wf.model("toy").merge(eq_i, eq_cn).append("Y = CN + I + G")` · `.merge("model.txt")` |
| Structure | `m.blocks()` · `m.endogenous` · `m.exogenous` · `m.gaps()` |
| Solve (historical simulation) | `r = m.solve()` (sample, dynamic) · `m.solve(mode="static")` · `r.summary()` · `r.status()` |
| Results | `wf["Y_0"]` (baseline alias) · `m.compare("Y")` · `r.save("results/hs.csv")` |
| Scenarios | `sc = m.scenario("hi_g")` → `.override("G", wf["G"]*1.1)` · `.shock("G", 10, "2015Q1", kind="pct")` |
| Fix endogenous variables · add factors | `.exclude("I", "2015Q1", "2015Q4")` · `.add_factor("eq_cn", 1.0)` · `.use_residuals()` |
| Target tracking | `m.control("Y", "G", target_path, "2015Q1", "2015Q4")` |
| Forecast | `m.forecast("2020Q1", "2021Q4", exog_fill="trend")` |
| Analysis | `m.decompose("Y", "hi_g")` · `m.multipliers("G", 1.0)` · `m.stochastic(reps=200)` · `m.stability("2010Q1")` |
| Leads (model-consistent expectations) | `m.solve(mce=True)` · `mce_method="stacked"` |

## Systems, VAR, VECM

| Task | Code |
|---|---|
| System estimation | `s = wf.system("s"); s.append("…", "…", "@inst …"); s.sur()` · `.three_sls()` · `.fiml()` — also for non-linear `c(n)` equations |
| Cross-equation restrictions | the same `c(n)` in two equations · `s.sur(restrict=["c(2) = c(5)"])` |
| VAR | `v = wf.var("v", ["dlog(Y)", "R"], lags=2)` → `.lag_order()` · `.granger(…)` · `.irf(8)` · `.fevd(8)` · `.forecast(4)` |
| VECM | `k = wf.vecm("k", ["RL", "R"], rank=1)` → `.alpha` · `.beta` · `.forecast(4)` |
| Into a model | `wf.model("mv").merge(v)` (as equations with fixed coefficients) |

## Command line

| Task | Command |
|---|---|
| Run a script with a report | `equion run script.py` → `out/<run id>/report.html` |
| Parameters · sample | `--set g=0.05` · `--params p.json` · `--smpl 2000Q1:2019Q4` |
| Failures as exit codes | `--fail-on fallback` (exit code 2) |
| Check without running | `equion check model.txt --data data.csv` |
| Summaries | `equion info data.csv` · `equion info out/<run id>` |
| New project | `equion new folder` · a project with blocks, models and data vintages: `equion new folder --template desk` |

Exit codes: 0 success · 1 script error · 2 solve failure (`--fail-on`) · 3 input error · 130 interrupted.

## Projects (a record for every command)

| Task | Command |
|---|---|
| Check the assembly | `equion assemble main` |
| Data vintages | `equion data list` · `data inbox` · `data build --use` · `data diff` · `data impact` |
| Estimate, compare, adopt | `equion est demand:CN` · `est "equation" --for demand:CN` · `compare --part demand:CN` · `adopt est:…` |
| Historical simulation | `equion hs` · `hs --swap demand:CN=est:… --vs hs:…` · `hs --replay hs:…` |
| Forecasts and scenarios | `equion sim base oil20` · `scenario define name --shock POIL=+20%` · `an split "sim:… sim:…"` |
| Analyses, notes, reports | `equion an unitroot core` · `note run notes/x.md` · `report add report sim:… --show yoy` · `report update report` |
| Records and changes | `equion work list` · `work show record` · `history list` · `history revert h…` |
| Scripts | `equion run FLOWS/monthly.eqs [--dry-run]` · `run --replay run:…` · `check FLOWS/monthly.eqs` |
| Milestones, moving a project | `equion milestone make name` · `bundle make` · `bundle open bundle.zip folder` |
| Guide for Claude | `equion guide` · `guide skill --install project` |

The project workflow is described (in Korean) in [tutorial 9](../tutorial/09-project.md) and the [guides](../guide/README.md); the desktop app Equion Desk has its own manual in [`docs/desk/`](../desk/README.md).
