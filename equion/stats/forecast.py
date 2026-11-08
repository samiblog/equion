#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""예측 평가 — 오차 지표(RMSE·MAE·MAPE·Theil U)와 두 예측 비교(Diebold-Mariano) (DECISIONS D21).

    evaluate(actual, forecast)            지표 한 줄(pandas Series)
    evaluate_many(actual, {이름: 예측})    지표 표(DataFrame — 행 = 예측)
    diebold_mariano(actual, f1, f2, h)    두 예측의 정확도가 같은가(TestResult)

결측은 실측과 예측이 모두 있는 기간만 쓴다(인덱스가 있으면 인덱스로 맞춘다).
"""

import numpy as np
import pandas as pd
from scipy import stats

from .result import TestResult

MEASURES = ("N", "RMSE", "MAE", "MAPE(%)", "Theil U1", "편의 비중", "분산 비중", "공분산 비중", "Theil U2")


def _align(actual, *forecasts):
    """실측·예측을 같은 기간으로 맞추고 모두 관측된 행만 남긴다 → (실측, [예측…]) numpy 배열."""
    items = [actual, *forecasts]
    if all(isinstance(x, pd.Series) for x in items):
        df = pd.concat(items, axis=1, join="inner")
    else:
        arrs = [np.asarray(x, dtype=float).ravel() for x in items]
        if len({len(a) for a in arrs}) != 1:
            raise ValueError("실측과 예측의 길이가 다릅니다(pandas Series면 기간으로 맞춥니다)")
        df = pd.DataFrame(np.column_stack(arrs))
    df = df.astype(float).replace([np.inf, -np.inf], np.nan).dropna()
    if len(df) == 0:
        raise ValueError("실측과 예측이 함께 관측된 기간이 없습니다")
    v = df.to_numpy()
    return v[:, 0], [v[:, i] for i in range(1, v.shape[1])]


def evaluate(actual, forecast) -> pd.Series:
    """예측 오차 지표 — RMSE·MAE·MAPE·Theil U1·MSE 분해(편의·분산·공분산)·Theil U2.

    예
        >>> a = pd.Series([1.0, 2.0, 3.0, 4.0])
        >>> e = eqn.stats.forecast_evaluate(a, a + 0.1)
        >>> round(float(e["RMSE"]), 3), round(float(e["편의 비중"]), 3)
        (0.1, 1.0)
    """
    a, (f,) = _align(actual, forecast)
    e = f - a
    n = len(a)
    mse = float(np.mean(e ** 2))
    rmse = np.sqrt(mse)
    sa, sf = float(np.std(a)), float(np.std(f))
    r = float(np.corrcoef(a, f)[0, 1]) if n > 1 and sa > 0 and sf > 0 else np.nan
    denom = np.sqrt(np.mean(f ** 2)) + np.sqrt(np.mean(a ** 2))
    with np.errstate(divide="ignore", invalid="ignore"):
        mape = 100 * float(np.mean(np.abs(e / a))) if np.all(a != 0) else np.nan
        if n > 1 and np.all(a[:-1] != 0):
            num = np.sum(((f[1:] - a[1:]) / a[:-1]) ** 2)
            den = np.sum(((a[1:] - a[:-1]) / a[:-1]) ** 2)
            u2 = float(np.sqrt(num / den)) if den > 0 else np.nan
        else:
            u2 = np.nan
    props = ((float(np.mean(f) - np.mean(a)) ** 2 / mse, (sf - sa) ** 2 / mse, 2 * (1 - r) * sf * sa / mse)
             if mse > 0 else (np.nan, np.nan, np.nan))
    return pd.Series([n, rmse, float(np.mean(np.abs(e))), mape, float(rmse / denom) if denom > 0 else np.nan,
                      *props, u2], index=list(MEASURES), dtype=float)


def evaluate_many(actual, forecasts: dict) -> pd.DataFrame:
    """여러 예측의 지표 표 — forecasts: {이름: 예측 Series·배열}. 예측마다 따로 공통 기간을 맞춘다.

    예
        >>> a = pd.Series([1.0, 2.0, 3.0, 4.0])
        >>> t = eqn.stats.forecast_table(a, {"f1": a + 0.1, "f2": a * 1.1})
        >>> list(t.index)
        ['f1', 'f2']
    """
    rows = {str(k): evaluate(actual, v) for k, v in forecasts.items()}
    df = pd.DataFrame(rows).T
    df.index.name = "예측"
    df["N"] = df["N"].astype(int)
    return df


def diebold_mariano(actual, f1, f2, h: int = 1, loss: str = "squared", harvey: bool = True) -> TestResult:
    """Diebold-Mariano 검정 — 두 예측의 기대 손실이 같은가(HLN 작은 표본 보정·t 분포, 통계량 음수면 첫 예측이 더 정확).

    손실 차이의 분산이 0이면(같은 예측) 통계량은 NA와 설명이다.

    예
        >>> rng = np.random.default_rng(2)
        >>> a = pd.Series(rng.normal(size=80))
        >>> r = eqn.stats.diebold_mariano(a, a + rng.normal(scale=0.1, size=80), a + rng.normal(size=80))
        >>> r.statistic < 0, r.pvalue < 0.01
        (True, True)
    """
    h = int(h)
    if h < 1:
        raise ValueError("h(예측 기간)는 1 이상")
    loss = loss.lower()
    if loss not in ("squared", "absolute"):
        raise ValueError("loss는 'squared' 또는 'absolute'")
    a, (x1, x2) = _align(actual, f1, f2)
    e1, e2 = x1 - a, x2 - a
    d = (e1 ** 2 - e2 ** 2) if loss == "squared" else (np.abs(e1) - np.abs(e2))
    n = len(d)
    if n <= h + 1:
        raise ValueError(f"관측치 {n}개로는 h = {h} 검정을 할 수 없습니다")
    dbar = float(d.mean())
    dc = d - dbar
    gamma = [float(dc[k:] @ dc[:n - k]) / n for k in range(h)]
    V = gamma[0] + 2 * sum(gamma[1:])
    kernel = "직사각(h−1)"
    if V <= 0:
        V = gamma[0] + 2 * sum((1 - k / h) * g for k, g in enumerate(gamma[1:], start=1))
        kernel = "Bartlett(직사각 분산이 0 이하라 대신)"
    if V <= 0:
        return TestResult("Diebold-Mariano 예측 정확도 비교", np.nan, np.nan,
                          null="두 예측의 기대 손실이 같다", info={"관측치": n, "h": h},
                          notes=["손실 차이의 분산이 0 — 두 예측의 오차가 같습니다"])
    dm = dbar / np.sqrt(V / n)
    if harvey:
        stat = dm * np.sqrt((n + 1 - 2 * h + h * (h - 1) / n) / n)
        p = float(2 * stats.t.sf(abs(stat), n - 1))
        dist = f"t({n - 1}) — Harvey-Leybourne-Newbold 보정"
    else:
        stat = dm
        p = float(2 * stats.norm.sf(abs(stat)))
        dist = "표준정규"
    better = "첫 예측" if dbar < 0 else "둘째 예측" if dbar > 0 else "같음"
    return TestResult("Diebold-Mariano 예측 정확도 비교", float(stat), p, null="두 예측의 기대 손실이 같다",
                      rows={"DM(보정 전)": float(dm), "평균 손실 차이 d̄": dbar, "손실이 작은 쪽": better},
                      info={"관측치": n, "h": h, "손실": "제곱 오차" if loss == "squared" else "절대 오차",
                            "분포": dist, "장기 분산": kernel},
                      details={"dm": float(dm), "dbar": dbar, "variance": float(V), "n": n, "h": h})
