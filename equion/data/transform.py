#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""자료 변환 — 주기 변환·시간 분할(Denton·Chow-Lin)·계절조정(STL·고전 분해) (DECISIONS D26).

    aggregate(s, to, how)               높은 주기 → 낮은 주기: mean·sum·first·last·max·min (빠진 하위 기간이 있으면 결측)
    expand(s, to, how)                  낮은 주기 → 높은 주기: constant(반복)·split(합을 나눔)·linear(끝 값 맞춤 선형)
    denton(y, k, indicator, conversion) 비례 Denton(Cholette 수정, 1차 차분) — 낮은 주기 제약(sum·average·first·last) 만족
    chow_lin(y, X, k, conversion, rho)  Chow-Lin GLS(AR(1) 오차, ρ는 최우 또는 지정)
    stl(y, period, …)                   STL(Cleveland 외 1990) — 원 알고리즘의 loess·저역통과·강건 가중치 그대로
    classical(y, period, model)         고전 분해(중심 이동평균 추세 + 계절 평균) — 가법·승법

pandas 시간 인덱스 연산은 data/periods.py를 거친다(D17). 함수는 numpy 배열·pandas Series를 받고 돌려준다.
"""

from typing import Optional, Tuple

import numpy as np
import pandas as pd

from .periods import PERIODS_PER_YEAR, format_period, normalize_freq, period_starts, periods_of

AGG_METHODS = ("mean", "sum", "first", "last", "max", "min")
EXPAND_METHODS = ("constant", "split", "linear", "denton", "chow-lin")
CONVERSIONS = ("sum", "average", "first", "last")


# ---------------------------------------------------------------------------
# 주기 변환
# ---------------------------------------------------------------------------
def ratio(from_freq: str, to_freq: str) -> int:
    """높은 주기 하나에 낮은 주기 몇 개(예: 분기 → 연 4, 월 → 분기 3).

    예
        >>> from equion.data import transform
        >>> transform.ratio("Q", "A"), transform.ratio("M", "Q")
        (4, 3)
    """
    a, b = PERIODS_PER_YEAR[normalize_freq(from_freq)], PERIODS_PER_YEAR[normalize_freq(to_freq)]
    if a % b and b % a:
        raise ValueError(f"주기 {from_freq}→{to_freq}는 정수배가 아닙니다")
    return max(a, b) // min(a, b)


def aggregate(s: pd.Series, from_freq: str, to_freq: str, how: str = "mean", complete: bool = True) -> pd.Series:
    """높은 주기 시리즈 → 낮은 주기. how: mean·sum·first·last·max·min. complete=True면 하위 기간이 하나라도 비면 결측.

    예
        >>> from equion.data import transform
        >>> wf = eqn.datasets.load("toy_q")
        >>> a = transform.aggregate(wf["Y"], "Q", "A", "sum")
        >>> len(a), round(float(a.iloc[0]), 1) == round(float(wf["Y"].iloc[:4].sum()), 1)
        (50, True)
    """
    if how not in AGG_METHODS:
        raise ValueError(f"how는 {AGG_METHODS} 중 하나")
    k = ratio(from_freq, to_freq)
    tf = normalize_freq(to_freq)
    per = periods_of(s.index, tf)
    g = pd.Series(s.to_numpy(dtype=float), index=per)
    grp = g.groupby(level=0)
    cnt = grp.count()
    size = grp.size()
    out = getattr(grp, how)() if how not in ("first", "last") else grp.agg(lambda v: v.iloc[0] if how == "first" else v.iloc[-1])
    if complete:
        out[(cnt < k) | (size < k)] = np.nan
    idx = period_starts(out.index[0], out.index[-1], tf)
    return pd.Series(out.reindex(pd.period_range(out.index[0], out.index[-1], freq=out.index.freq)).to_numpy(),
                     index=idx, name=s.name)


def expand(s: pd.Series, from_freq: str, to_freq: str, how: str = "constant") -> pd.Series:
    """낮은 주기 → 높은 주기(분할 없이): constant(같은 값 반복)·split(값/k)·linear(각 낮은 기간의 마지막 하위 기간에 값을 두고 선형 보간).

    예
        >>> from equion.data import transform
        >>> wa = eqn.datasets.load("toy_a")
        >>> q = transform.expand(wa["Y"], "A", "Q", "split")
        >>> round(float(q.iloc[:4].sum()), 3) == round(float(wa["Y"].iloc[0]), 3)
        True
    """
    k = ratio(from_freq, to_freq)
    tf = normalize_freq(to_freq)
    vals = s.to_numpy(dtype=float)
    p0 = periods_of(s.index[:1], normalize_freq(from_freq))[0]
    start = pd.Period(p0.start_time, freq=_pfreq(tf))
    idx = period_starts(start, start + len(vals) * k - 1, tf)
    if how == "constant":
        out = np.repeat(vals, k)
    elif how == "split":
        out = np.repeat(vals / k, k)
    elif how == "linear":
        pos = np.arange(len(vals)) * k + (k - 1)
        out = np.interp(np.arange(len(vals) * k), pos, vals, left=np.nan, right=np.nan)
        if len(vals) > 1:                       # 첫 낮은 기간 앞부분: 첫 구간 기울기로 늘림
            slope = (vals[1] - vals[0]) / k
            out[:k - 1] = vals[0] - slope * np.arange(k - 1, 0, -1)
    else:
        raise ValueError("how는 'constant'·'split'·'linear'")
    return pd.Series(out, index=idx, name=s.name)


def _pfreq(f):
    from .periods import PERIOD_FREQ
    return PERIOD_FREQ[f]


def _cmat(n_low: int, k: int, T: int, conversion: str) -> np.ndarray:
    """집계 행렬 C(n_low × T): 높은 주기 x를 낮은 주기 y = Cx로. T > n_low·k면 뒤는 외삽(제약 없음)."""
    if conversion not in CONVERSIONS:
        raise ValueError(f"conversion은 {CONVERSIONS} 중 하나")
    C = np.zeros((n_low, T))
    for i in range(n_low):
        sl = slice(i * k, (i + 1) * k)
        if conversion == "sum":
            C[i, sl] = 1.0
        elif conversion == "average":
            C[i, sl] = 1.0 / k
        elif conversion == "first":
            C[i, i * k] = 1.0
        else:
            C[i, (i + 1) * k - 1] = 1.0
    return C


# ---------------------------------------------------------------------------
# 시간 분할
# ---------------------------------------------------------------------------
def denton(y_low, k: int, indicator=None, conversion: str = "sum", T: int = None) -> np.ndarray:
    """비례 Denton(Cholette 수정, 1차 차분) — min Σ (xₜ/iₜ − xₜ₋₁/iₜ₋₁)² s.t. Cx = y.

    indicator가 없으면 iₜ = 1(가법 = 비례). T(높은 주기 길이)가 n·k보다 길면 뒤를 지표 흐름대로 외삽한다.
    conversion: 'sum' · 'average' · 'first' · 'last'(낮은 주기 값이 하위 기간의 무엇인가).

    예
        >>> from equion.data import transform
        >>> x = transform.denton(np.array([10.0, 12.0]), 4)
        >>> x.reshape(2, 4).sum(axis=1).round(10).tolist()
        [10.0, 12.0]
    """
    y = np.asarray(y_low, dtype=float)
    n = len(y)
    if not np.all(np.isfinite(y)):
        raise ValueError("낮은 주기 시리즈에 결측이 있습니다")
    i = np.ones(T or n * k) if indicator is None else np.asarray(indicator, dtype=float)
    T = len(i)
    if T < n * k:
        raise ValueError(f"지표가 {T}기로, 낮은 주기 {n}기 × {k} = {n * k}기보다 짧습니다")
    if not np.all(np.isfinite(i)) or np.any(i == 0):
        raise ValueError("지표에 결측이나 0이 있습니다")
    C = _cmat(n, k, T, conversion) @ np.diag(i)              # z = x/i 에 대한 제약
    D = np.diff(np.eye(T), axis=0)                            # 1차 차분
    K = np.block([[D.T @ D, C.T], [C, np.zeros((n, n))]])
    rhs = np.concatenate([np.zeros(T), y])
    z = np.linalg.lstsq(K, rhs, rcond=None)[0][:T]
    return z * i


def _ar1_corr(T: int, rho: float) -> np.ndarray:
    j = np.arange(T)
    return rho ** np.abs(j[:, None] - j[None, :]) / (1.0 - rho ** 2)


def _chow_lin_fixed(y, X, C, rho):
    """ρ가 정해졌을 때의 GLS: (x̂, β̂, σ̂², 로그우도)."""
    V = _ar1_corr(X.shape[0], rho)
    W = C @ V @ C.T
    Wi = np.linalg.inv(W)
    Xl = C @ X
    A = Xl.T @ Wi @ Xl
    beta = np.linalg.solve(A, Xl.T @ Wi @ y)
    u = y - Xl @ beta
    n = len(y)
    s2 = float(u @ Wi @ u) / n
    ll = -0.5 * n * (np.log(2 * np.pi * s2) + 1) - 0.5 * np.linalg.slogdet(W)[1]
    x = X @ beta + V @ C.T @ Wi @ u
    return x, beta, s2, ll


def chow_lin(y_low, X_high, k: int, conversion: str = "sum", rho: Optional[float] = None) -> dict:
    """Chow-Lin — 높은 주기 x = Xβ + u, u ~ AR(1)(ρ), 낮은 주기 y = Cx. ρ=None이면 최우로 고른다.

    돌려주는 dict: x(제약 Cx = y를 정확히 만족) · beta · rho · loglik.

    예
        >>> from equion.data import transform
        >>> rng = np.random.default_rng(0)
        >>> ind = 10 + np.cumsum(rng.normal(size=12))
        >>> y = ind.reshape(3, 4).sum(axis=1) * 1.5
        >>> r = transform.chow_lin(y, np.column_stack([np.ones(12), ind]), 4)
        >>> bool(np.allclose(r["x"].reshape(3, 4).sum(axis=1), y))
        True
    """
    from scipy.optimize import minimize_scalar
    y = np.asarray(y_low, dtype=float)
    X = np.asarray(X_high, dtype=float)
    if X.ndim == 1:
        X = X[:, None]
    n, T = len(y), X.shape[0]
    if T < n * k:
        raise ValueError(f"지표가 {T}기로, 낮은 주기 {n}기 × {k}보다 짧습니다")
    if not (np.all(np.isfinite(y)) and np.all(np.isfinite(X))):
        raise ValueError("Chow-Lin 자료에 결측이 있습니다")
    C = _cmat(n, k, T, conversion)
    if rho is None:
        grid = np.linspace(-0.99, 0.99, 199)
        lls = [_chow_lin_fixed(y, X, C, r)[3] for r in grid]
        g0 = grid[int(np.argmax(lls))]
        opt = minimize_scalar(lambda r: -_chow_lin_fixed(y, X, C, r)[3],
                              bounds=(max(-0.999, g0 - 0.01), min(0.999, g0 + 0.01)), method="bounded",
                              options={"xatol": 1e-10})
        rho = float(opt.x)
    x, beta, s2, ll = _chow_lin_fixed(y, X, C, float(rho))
    return {"x": x, "beta": beta, "rho": float(rho), "sigma2": s2, "loglik": ll}


# ---------------------------------------------------------------------------
# 계절조정
# ---------------------------------------------------------------------------
def _odd(v: int) -> int:
    return v + (v % 2 == 0)


def _est(y, n, length, ideg, xs, nleft, nright, userw, rw):
    """STL loess 한 점(원 Fortran stlest, 0-기준 색인 대신 1-기준 위치 xs·nleft·nright)."""
    rng = n - 1.0
    h = max(xs - nleft, nright - xs)
    if length > n:
        h += (length - n) // 2
    h9, h1 = 0.999 * h, 0.001 * h
    j = np.arange(nleft, nright + 1)
    r = np.abs(j - xs)
    w = np.zeros(len(j))
    inside = r <= h9
    w[inside] = np.where(r[inside] <= h1, 1.0, (1 - (r[inside] / h) ** 3) ** 3)
    if userw:
        w = w * rw[j - 1]
    a = w.sum()
    if a <= 0:
        return None
    w = w / a
    if h > 0 and ideg > 0:
        a = float(np.sum(w * j))
        b = xs - a
        c = float(np.sum(w * (j - a) ** 2))
        if np.sqrt(c) > 0.001 * rng:
            b = b / c
            w = w * (b * (j - a) + 1)
    return float(np.sum(w * y[j - 1]))


def _ess(y, length, ideg, userw, rw):
    """loess 평활(점프 1): 모든 점에서 길이 length의 이웃."""
    n = len(y)
    out = np.empty(n)
    if n < 2:
        return y.copy()
    if length >= n:
        nleft, nright = 1, n
        for i in range(1, n + 1):
            v = _est(y, n, length, ideg, i, nleft, nright, userw, rw)
            out[i - 1] = y[i - 1] if v is None else v
        return out
    nsh = (length + 1) // 2
    for i in range(1, n + 1):
        if i < nsh:
            nleft, nright = 1, length
        elif i >= n - nsh + 1:
            nleft, nright = n - length + 1, n
        else:
            nleft, nright = i - nsh + 1, length + i - nsh
        v = _est(y, n, length, ideg, i, nleft, nright, userw, rw)
        out[i - 1] = y[i - 1] if v is None else v
    return out


def _ss(w, n, period, ns, isdeg, userw, rw):
    """주기 부분계열(cycle-subseries)마다 loess, 양끝 한 칸씩 늘린다 → 길이 n + 2·period."""
    season = np.zeros(n + 2 * period)
    for j in range(period):
        k = (n - j - 1) // period + 1
        sub = w[j::period][:k]
        rws = rw[j::period][:k] if userw else None
        sm = _ess(sub, ns, isdeg, userw, rws)
        out = np.empty(k + 2)
        out[1:k + 1] = sm
        nright = min(ns, k)
        v = _est(sub, k, ns, isdeg, 0, 1, nright, userw, rws)
        out[0] = out[1] if v is None else v           # 원 알고리즘: 실패하면 이웃 평활값
        nleft = max(1, k - ns + 1)
        v = _est(sub, k, ns, isdeg, k + 1, nleft, k, userw, rws)
        out[k + 1] = out[k] if v is None else v
        season[j::period][:k + 2] = out
    return season


def _ma(x, length):
    c = np.cumsum(np.concatenate([[0.0], x]))
    return (c[length:] - c[:-length]) / length


def _robust_weights(y, fit):
    """이중제곱 가중치: h = 6·중앙값|잔차| (원 stlrwt — 가운데 두 값의 평균 ×3 ×2)."""
    r = np.abs(y - fit)
    h = 6.0 * np.median(r)
    c1, c9 = 0.001 * h, 0.999 * h
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(r <= c1, 1.0, np.where(r <= c9, (1 - (r / h) ** 2) ** 2, 0.0))


def stl(y, period: int, seasonal: int = 7, trend: int = None, low_pass: int = None, seasonal_deg: int = 1,
        trend_deg: int = 1, low_pass_deg: int = 1, robust: bool = False, inner: int = None,
        outer: int = None) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """STL 분해 → (계절, 추세, 잔차, 강건 가중치). 창 길이 기본값은 원 알고리즘(Cleveland 등 1990)과 같다.

    trend = 1.5·period/(1 − 1.5/seasonal)를 올림한 홀수, low_pass = period + 1을 홀수로. robust=True면 강건 반복.

    예
        >>> from equion.data import transform
        >>> t = np.arange(48.0)
        >>> y = t + 3 * np.tile([1.0, -1.0, 2.0, -2.0], 12)
        >>> s, tr, r, w = transform.stl(y, 4)
        >>> bool(np.allclose(s + tr + r, y)), round(float(s[:4].round(1).sum()), 1)
        (True, 0.0)
    """
    y = np.asarray(y, dtype=float)
    n = len(y)
    if not np.all(np.isfinite(y)):
        raise ValueError("STL 자료에 결측이 있습니다")
    if period < 2 or n < 2 * period:
        raise ValueError(f"STL에는 주기({period}) 두 배 이상의 관측치가 필요합니다")
    if seasonal < 3 or seasonal % 2 == 0:
        raise ValueError("seasonal은 3 이상 홀수")
    if trend is None:
        trend = _odd(int(np.ceil(1.5 * period / (1 - 1.5 / seasonal))))
    if low_pass is None:
        low_pass = _odd(period + 1)
    inner = (2 if robust else 5) if inner is None else inner
    outer = (15 if robust else 0) if outer is None else outer
    T = np.zeros(n)
    rw = np.ones(n)
    userw = False
    S = np.zeros(n)
    for o in range(outer + 1):
        for _ in range(inner):
            C = _ss(y - T, n, period, seasonal, seasonal_deg, userw, rw)
            L = _ess(_ma(_ma(_ma(C, period), period), 3), low_pass, low_pass_deg, False, None)
            S = C[period:period + n] - L
            T = _ess(y - S, trend, trend_deg, userw, rw)
        if o < outer:
            rw = _robust_weights(y, S + T)
            userw = True
    if outer == 0:
        rw = np.ones(n)
    return S, T, y - S - T, rw


def classical(y, period: int, model: str = "additive") -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """고전 분해 → (계절, 추세, 잔차). 추세 = 중심 이동평균(짝수 주기는 2×period, 양끝 결측), 계절 = 주기 위치별 평균.

    model: 'additive'(계절 합 0) · 'multiplicative'(계절 평균 1).

    예
        >>> from equion.data import transform
        >>> y = np.arange(24.0) + np.tile([1.0, -1.0, 2.0, -2.0], 6)
        >>> s, tr, r = transform.classical(y, 4)
        >>> s[:4].round(6).tolist()
        [1.0, -1.0, 2.0, -2.0]
    """
    y = np.asarray(y, dtype=float)
    n = len(y)
    if model not in ("additive", "multiplicative"):
        raise ValueError("model은 'additive' 또는 'multiplicative'")
    if model == "multiplicative" and np.any(y <= 0):
        raise ValueError("승법 분해에는 양수 자료만 됩니다")
    if n < 2 * period:
        raise ValueError(f"고전 분해에는 주기({period}) 두 배 이상의 관측치가 필요합니다")
    filt = (np.array([0.5] + [1.0] * (period - 1) + [0.5]) / period if period % 2 == 0
            else np.repeat(1.0 / period, period))
    m = len(filt)
    half = m // 2
    trend = np.full(n, np.nan)
    for t in range(half, n - half):
        trend[t] = float(filt @ y[t - half:t - half + m])
    det = y - trend if model == "additive" else y / trend
    means = np.array([np.nanmean(det[i::period]) for i in range(period)])
    means = means - means.mean() if model == "additive" else means / means.mean()
    seas = np.tile(means, n // period + 1)[:n]
    resid = y - seas - trend if model == "additive" else y / seas / trend
    return seas, trend, resid


__all__ = ["AGG_METHODS", "EXPAND_METHODS", "CONVERSIONS", "ratio", "aggregate", "expand", "denton", "chow_lin",
           "stl", "classical"]
