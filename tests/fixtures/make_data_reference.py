"""tests/fixtures/data_reference.json 생성 — 계절조정(STL·고전 분해)·Denton의 기준값.

statsmodels(STL·seasonal_decompose·dentonm)로 한 번 계산해 고정한다. Equion은 statsmodels에 의존하지 않으므로
(DECISIONS D17) **별도 환경**에서만 돌린다:
    PYTHONPATH=<저장소> <statsmodels가 있는 python> tests/fixtures/make_data_reference.py
자료는 예제 자료 toy_q의 CNNSA(계절조정 전 소비)와 CN(계절조정 소비)을 그대로 넘긴다.
"""
import json
import os
import sys
import warnings

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
warnings.simplefilter("ignore")
import numpy as np  # noqa: E402
import statsmodels  # noqa: E402
from statsmodels.tsa.interp.denton import dentonm  # noqa: E402
from statsmodels.tsa.seasonal import STL, seasonal_decompose  # noqa: E402

import equion as eqn  # noqa: E402

eqn.verbose(0)
wf = eqn.datasets.load("toy_q")
y = wf["CNNSA"].dropna().to_numpy()
L = lambda a: [float(v) for v in np.asarray(a, dtype=float)]  # noqa: E731
out = {"_provenance": f"statsmodels {statsmodels.__version__} · numpy {np.__version__} 로 계산"
                      "(tests/fixtures/make_data_reference.py). Equion 자체 구현이 같은 값을 내는지 tests/test_workfile.py가 확인한다.",
       "series": "CNNSA", "n": len(y)}
stl = {}
for key, kw in (("default", {}), ("robust", {"robust": True}), ("s13", {"seasonal": 13}),
                ("s9_t23_robust", {"seasonal": 9, "trend": 23, "robust": True})):
    r = STL(np.log(y), period=4, **kw).fit()
    stl[key] = {"kw": kw, "seasonal": L(r.seasonal), "trend": L(r.trend), "weights": L(r.weights)}
out["stl_log"] = stl
cl = {}
for model in ("additive", "multiplicative"):
    r = seasonal_decompose(y, model=model, period=4)
    cl[model] = {"seasonal": L(r.seasonal), "trend": [None if not np.isfinite(v) else float(v) for v in r.trend]}
out["classical"] = cl
q = y[:len(y) // 4 * 4]
a = q.reshape(-1, 4).sum(axis=1)
ind = wf["CN"].dropna().to_numpy()[:len(a) * 4]
out["denton"] = {"annual": L(a), "indicator": L(ind), "x": L(dentonm(ind, a, freq="aq")),
                 "indicator_ext": L(np.concatenate([ind, ind[-3:] * 1.01])),
                 "x_ext": L(dentonm(np.concatenate([ind, ind[-3:] * 1.01]), a, freq="aq"))}
with open(os.path.join(ROOT, "tests", "fixtures", "data_reference.json"), "w", encoding="utf-8") as fh:
    json.dump(out, fh, ensure_ascii=False, indent=1)
print("ok", len(json.dumps(out)), "bytes")
