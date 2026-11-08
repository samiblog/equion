# Your first model

Build a small macro model from start to finish: open data, estimate equations, assemble a simultaneous model, run a
historical simulation, a scenario and a forecast, and save the work. Every block runs as shown, and the outputs
are real results (the documentation check re-runs them). The Korean version, with Equion's own tables, is
[30분 첫 모델](../start/first-model.md).

Equion prints progress messages in Korean; this page turns them off and prints plain pandas objects.

## 1. Open the example data

`toy_q` is a synthetic quarterly data set generated from a known model, so estimates can be compared with the truth.

```python
import equion as eqn

eqn.verbose(0)                            # silence progress messages
wf = eqn.datasets.load("toy_q")           # a workfile: series, sample and objects
print(wf.freq, wf.smpl(), list(wf.data.columns))
```
<!-- out -->
```text
Q ('1970Q1', '2019Q4') ['CN', 'I', 'G', 'Y', 'R', 'RL', 'P', 'POIL', 'M2', 'CNNSA']
```

The true model:

| Equation | True form |
|---|---|
| Investment | `I = 5 + 0.15·Y(-1) − 1.0·R + e` |
| Consumption | `CN = 10 + 0.5·Y + 0.3·CN(-1) + e` |
| Income (identity) | `Y = CN + I + G` |
| Prices | `dlog(P) = 0.005 + 0.3·dlog(Y) + 0.02·dlog(POIL) + e` |

`G` (government spending), `R` (policy rate) and `POIL` (oil price index) are exogenous.

## 2. Estimate equations

Equations are text: the first term is the dependent variable, `c` is the constant and `Y(-1)` is the value one
quarter earlier.

```python
eq_i = wf.equation("eq_i").ls("I c Y(-1) R")      # least squares
print(eq_i.coefs.round(3).to_dict())
print(eq_i.stderrs.round(4).to_dict())
print(round(eq_i.stats["r_squared"], 4), round(eq_i.stats["durbin_watson"], 2))
```
<!-- out -->
```text
{'const': 4.481, 'Y(-1)': 0.151, 'R': -0.963}
{'const': 0.4947, 'Y(-1)': 0.0007, 'R': 0.0401}
0.9985 1.93
```

`eqn.show(eq_i)` prints the full regression table (headings in Korean — see the [glossary](README.md#language-of-messages-and-tables)).

In the consumption equation, current income `Y` is determined together with consumption, so least squares is biased.
Two-stage least squares with instruments (`@inst`) moves the estimates towards the true 0.5 and 0.3:

```python
ols = wf.equation("eq_cn_ols").ls("CN c Y CN(-1)")
eq_cn = wf.equation("eq_cn").tsls("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
print("OLS ", ols.coefs.round(3).to_dict())
print("TSLS", eq_cn.coefs.round(3).to_dict())
```
<!-- out -->
```text
OLS  {'const': 11.647, 'Y': 0.587, 'CN(-1)': 0.178}
TSLS {'const': 10.651, 'Y': 0.531, 'CN(-1)': 0.256}
```

The price equation is in differences: `dlog(P)` is `log(P) − log(P(-1))`.

```python
eq_p = wf.equation("eq_p").ls("dlog(P) c dlog(Y) dlog(POIL)")
print(eq_p.coefs.round(4).to_dict())
tests = {"serial LM(2)": eq_p.serial_lm(2), "White": eq_p.white(), "RESET": eq_p.reset()}
print({k: round(float(t.pvalue), 3) for k, t in tests.items()})      # p-values of residual tests
```
<!-- out -->
```text
{'const': 0.005, 'dlog(Y)': 0.2714, 'dlog(POIL)': 0.0138}
{'serial LM(2)': 0.405, 'White': 0.308, 'RESET': 0.374}
```

## 3. Assemble the model

Merge the estimated equations and add the identity. The endogenous variables are the equations' targets and the
identity's left-hand side.

```python
m = wf.model("toy").merge(eq_i, eq_cn, eq_p).append("Y = CN + I + G")
print(m.endogenous, m.exogenous)
```
<!-- out -->
```text
['CN', 'I', 'P', 'Y'] ['G', 'POIL', 'R']
```

## 4. Historical simulation

Solve the model dynamically: lagged endogenous variables take the model's own solution from earlier periods.
Results are written back as alias series (`Y_0`, `CN_0`, …).

```python
wf.smpl("1975Q1", "2019Q4")              # default span for estimation, solving and charts
base = m.solve()
print(base.counts())
print(base.statistics()[["RMSPE", "MAE"]].round(2))
print(wf.to_pandas(["Y", "Y_0"], labels=True).loc["2019Q1":"2019Q4"].round(1))
```
<!-- out -->
```text
{'ok': 180, 'partial': 0, 'fallback': 0, 'failed': 0}
    RMSPE   MAE
Y    0.54  1.94
CN   0.56  1.52
I    1.06  0.57
P    1.27  1.25
            Y    Y_0
2019Q1  621.0  621.1
2019Q2  625.7  623.9
2019Q3  626.1  623.3
2019Q4  625.7  624.9
```

`base.status()` gives the status of every period (`ok`, `partial`, `fallback`, `failed`) with the reason.

## 5. Scenario

Raise government spending by 10% from 2015. A scenario keeps its results under its own alias (`_1`), next to the
baseline (`_0`).

```python
sc = m.scenario("g_up")
sc.shock("G", 10, "2015Q1", "2019Q4", kind="pct")
m.solve("2015Q1", "2019Q4")
cmp = wf.to_pandas(["Y_0", "Y_1"], labels=True).loc["2015Q1":"2015Q4"]
cmp["diff_pct"] = (cmp["Y_1"] / cmp["Y_0"] - 1) * 100
print(cmp.round(2))
```
<!-- out -->
```text
           Y_0     Y_1  diff_pct
2015Q1  583.31  598.01      2.52
2015Q2  587.92  610.96      3.92
2015Q3  590.63  619.79      4.94
2015Q4  594.06  627.86      5.69
```

Higher spending raises income, which raises consumption and next quarter's investment, so the effect builds up.

## 6. Forecast

The data end in 2019Q4. Extend the exogenous variables with their recent trend and solve two years ahead.

```python
m.scenario("baseline")                    # back to the baseline scenario
m.forecast("2020Q1", "2021Q4", exog_fill="trend")
print(wf.to_pandas(["Y_0", "CN_0", "I_0"], labels=True).loc["2020Q1":"2021Q4"].round(1))
```
<!-- out -->
```text
          Y_0   CN_0   I_0
2020Q1  626.9  461.9  95.8
2020Q2  627.3  462.2  96.1
2020Q3  627.4  462.3  96.1
2020Q4  627.5  462.4  96.2
2021Q1  627.5  462.4  96.2
2021Q2  627.4  462.4  96.3
2021Q3  627.3  462.3  96.3
2021Q4  627.1  462.2  96.3
```

## 7. Charts and saving

```python
g = wf.graph("g_y", "Y Y_0 Y_1", start="2010Q1", end="2021Q4", title="Income: actual, baseline, scenario")
g.save("y.html")                          # opens offline; plotly is not required
wf.save("toy")                            # toy.eqw/ — data, estimates, model and scenarios
wf2 = eqn.wfopen("toy.eqw")               # reopens without re-estimating
print(wf2.obj("eq_i").coefs.round(3).to_dict())
```
<!-- out -->
```text
{'const': 4.481, 'Y(-1)': 0.151, 'R': -0.963}
```

## 8. From the command line

A script is plain Python; `eqn.params` reads parameters that `--set` can override, and `equion run` writes a report
folder (`out/<run id>/report.html`, `manifest.json` with versions, inputs and solver status):

```bash
equion run my_model.py --set g_up=5 --smpl 1990Q1:2019Q4
equion check model.txt --data data.csv      # check an equation file without running it
```

Exit codes: 0 success · 1 script error · 2 solve failure (`--fail-on`) · 3 input error · 130 interrupted.

## Next

- [Cheat sheet](cheatsheet.md)
- [API reference](../reference/api.md) (signatures; descriptions in Korean)
- The Korean tutorials ([튜토리얼](../tutorial/README.md)) go through each step in depth; the code reads the same in any language.
