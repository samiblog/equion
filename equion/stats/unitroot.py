#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""단위근·공적분 검정 — ADF, KPSS, Engle-Granger, Johansen.

p값·임계값은 공개된 수치표(MacKinnon 1994·2010, MacKinnon-Haug-Michelis 1999 — equion.stats._tables)로 계산한다.
결정항(trend): 'n' 없음 · 'c' 상수 · 'ct' 상수+선형 추세 · 'ctt' 상수+2차 추세.
"""

import numpy as np
import pandas as pd
from scipy.stats import norm

from . import _tables as T
from .regression import pinv_svd
from .regression import ols as _ols_frame
from .result import TestResult

_TREND_KO = {"n": "없음", "c": "상수", "ct": "상수+추세", "ctt": "상수+2차 추세"}
_IC = {"aic": "AIC", "bic": "SIC(BIC)", "t-stat": "t 통계량(10%)"}


def _ols(y, X):
    idx = pd.RangeIndex(len(y))
    return _ols_frame(pd.Series(np.asarray(y, dtype=float), index=idx),
                      pd.DataFrame(np.asarray(X, dtype=float), index=idx,
                                   columns=[f"x{i}" for i in range(np.shape(X)[1])]))


def _norm_trend(trend: str) -> str:
    t = {"none": "n", "nc": "n", "const": "c", "constant": "c", "trend": "ct"}.get(str(trend).lower(), str(trend).lower())
    if t not in _TREND_KO:
        raise ValueError(f"결정항은 'n'·'c'·'ct'·'ctt' 중 하나입니다: {trend!r}")
    return t


def _trend_cols(n: int, trend: str) -> np.ndarray:
    cols = []
    if trend != "n":
        cols.append(np.ones(n))
    t = np.arange(1, n + 1, dtype=float)
    if trend in ("ct", "ctt"):
        cols.append(t)
    if trend == "ctt":
        cols.append(t ** 2)
    return np.column_stack(cols) if cols else np.empty((n, 0))


def _series(x) -> np.ndarray:
    a = np.asarray(x, dtype=float).ravel()
    if np.isnan(a).any():
        raise ValueError("검정할 시계열에 결측이 있습니다(표본 안쪽은 이어져 있어야 합니다)")
    return a


# ---------------------------------------------------------------------------
# MacKinnon p값·임계값
# ---------------------------------------------------------------------------
def mackinnon_p(stat: float, trend: str = "c", n_vars: int = 1) -> float:
    """ADF·Engle-Granger 통계량의 근사 p값(MacKinnon 1994). n_vars: 공적분 회귀의 변수 수(ADF는 1).

    예
        >>> round(eqn.stats.mackinnon_p(-2.86, "c"), 2)
        0.05
    """
    i = n_vars - 1
    if stat > T.TAU_MAX[trend][i]:
        return 1.0
    if stat < T.TAU_MIN[trend][i]:
        return 0.0
    coef = T.TAU_SMALLP[trend][i] if stat <= T.TAU_STAR[trend][i] else T.TAU_LARGEP[trend][i]
    return float(norm.cdf(np.polyval(np.asarray(coef)[::-1], stat)))


def mackinnon_crit(n_vars: int = 1, trend: str = "c", nobs: float = np.inf) -> np.ndarray:
    """1%·5%·10% 임계값(MacKinnon 2010 반응곡면).

    예
        >>> eqn.stats.mackinnon_crit(1, "c").round(2).tolist()
        [-3.43, -2.86, -2.57]
    """
    tau = np.asarray(T.TAU_2010[trend], dtype=float)
    if not np.isfinite(nobs):
        return tau[n_vars - 1, :, 0]
    return np.polyval(tau[n_vars - 1, :, ::-1].T, 1.0 / nobs)


# ---------------------------------------------------------------------------
# ADF
# ---------------------------------------------------------------------------
def _adf_design(x: np.ndarray, lags: int):
    """Δxₜ를 x(t−1)과 Δx 시차 1~lags에 회귀할 때의 (Δxₜ, [x(t−1), Δx(t−1)…]) — 가능한 가장 긴 표본."""
    dx = np.diff(x)
    nobs = len(dx) - lags
    cols = [x[-nobs - 1:-1]] + [dx[lags - j: len(dx) - j] for j in range(1, lags + 1)]
    return dx[-nobs:], np.column_stack(cols)


def _adf_core(x, trend, lags, ic, maxlag):
    nobs0 = len(x)
    ntrend = len(trend) if trend != "n" else 0
    if lags is not None and maxlag is None:
        maxlag = int(lags)
    if maxlag is None:
        maxlag = int(np.ceil(12.0 * np.power(nobs0 / 100.0, 0.25)))
        maxlag = min(nobs0 // 2 - ntrend - 1, maxlag)
        if maxlag < 0:
            raise ValueError("관측치가 너무 적어 이 결정항으로 검정할 수 없습니다")
    elif maxlag > nobs0 // 2 - ntrend - 1:
        raise ValueError(f"최대 시차는 (관측치/2 − 1 − 결정항 수) = {nobs0 // 2 - ntrend - 1} 이하여야 합니다")
    icbest = None
    if lags is None:
        # 같은 표본(최대 시차 기준)에서 시차 0~maxlag의 정보기준을 비교한다
        y, Z = _adf_design(x, maxlag)
        full = np.column_stack([_trend_cols(len(y), trend), Z])
        start = full.shape[1] - Z.shape[1] + 1
        fits = {lag: _ols(y, full[:, :lag]) for lag in range(start, start + maxlag + 1)}
        if ic == "aic":
            icbest, best = min((v.aic, k) for k, v in fits.items())
        elif ic == "bic":
            icbest, best = min((v.bic, k) for k, v in fits.items())
        elif ic == "t-stat":
            best, icbest = start + maxlag, 0.0
            for lag in range(start + maxlag, start - 1, -1):
                icbest, best = abs(float(fits[lag].tvalues.iloc[-1])), lag
                if icbest >= 1.6448536269514722:
                    break
        else:
            raise ValueError(f"시차 선택 기준은 'aic'·'bic'·'t-stat': {ic!r}")
        used = best - start
    else:
        used = int(lags)
        if not 0 <= used <= maxlag:
            raise ValueError(f"시차 {used}은(는) 0~{maxlag} 사이여야 합니다")
    y, Z = _adf_design(x, used)
    X = np.column_stack([Z, _trend_cols(len(y), trend)])
    res = _ols(y, X)
    return float(res.tvalues.iloc[0]), used, len(y), maxlag, icbest, res


def adf(x, trend: str = "c", lags: int = None, ic: str = "bic", maxlag: int = None, name: str = None) -> TestResult:
    """ADF 단위근 검정 — lags=None이면 ic('bic'·'aic'·'t-stat')로 0~maxlag 중에서 고른다. trend 'n'·'c'·'ct'.

    예
        >>> rng = np.random.default_rng(1)
        >>> eqn.stats.adf(np.cumsum(rng.normal(size=200))).pvalue > 0.05      # 랜덤워크
        True
        >>> eqn.stats.adf(rng.normal(size=200)).pvalue < 0.01                 # 백색잡음
        True
    """
    x = _series(x)
    trend = _norm_trend(trend)
    if x.max() == x.min():
        raise ValueError("상수 시계열은 검정할 수 없습니다")
    stat, used, nobs, maxlag, icbest, _ = _adf_core(x, trend, lags, ic.lower() if lags is None else None, maxlag)
    p = mackinnon_p(stat, trend, 1)
    crit = mackinnon_crit(1, trend, nobs)
    rows = {"임계값 1%": crit[0], "임계값 5%": crit[1], "임계값 10%": crit[2], "시차": used, "관측치": nobs}
    how = f"{_IC[ic.lower()]}, 최대 {maxlag}" if lags is None else "지정"
    return TestResult(f"ADF 단위근 검정{f' — {name}' if name else ''}", stat, p,
                      null="단위근이 있다(비정상)", rows=rows,
                      info={"결정항": _TREND_KO[trend], "시차 선택": f"{used} ({how})", "관측치": nobs},
                      details={"lags": used, "nobs": nobs, "maxlag": maxlag, "icbest": icbest,
                               "crit": {"1%": crit[0], "5%": crit[1], "10%": crit[2]}},
                      notes=["p값: MacKinnon(1994) 근사 · 임계값: MacKinnon(2010)"])


# ---------------------------------------------------------------------------
# KPSS
# ---------------------------------------------------------------------------
_KPSS_CRIT = {"c": [0.347, 0.463, 0.574, 0.739], "ct": [0.119, 0.146, 0.176, 0.216]}
_KPSS_P = [0.10, 0.05, 0.025, 0.01]


def _kpss_autolag(e: np.ndarray, n: int) -> int:
    """Hobijn-Franses-Ooms(1998) 자료 기반 대역폭."""
    covlags = int(np.power(n, 2.0 / 9.0))
    s0 = np.sum(e ** 2) / n
    s1 = 0.0
    for i in range(1, covlags + 1):
        prod = np.dot(e[i:], e[: n - i]) / (n / 2.0)
        s0 += prod
        s1 += i * prod
    s_hat = s1 / s0
    gamma = 1.1447 * np.power(s_hat * s_hat, 1.0 / 3.0)
    return int(gamma * np.power(n, 1.0 / 3.0))


def kpss(x, trend: str = "c", lags="auto", name: str = None) -> TestResult:
    """KPSS 정상성 검정 — lags: 'auto'(Hobijn 등 1998) · 'legacy' · 정수. p값은 표 보간(0.01~0.10).

    예
        >>> rng = np.random.default_rng(1)
        >>> eqn.stats.kpss(rng.normal(size=200)).pvalue >= 0.05
        True
    """
    x = _series(x)
    trend = _norm_trend(trend)
    if trend not in _KPSS_CRIT:
        raise ValueError("KPSS 결정항은 'c'(수준 정상) 또는 'ct'(추세 정상)")
    n = len(x)
    if trend == "ct":
        t = np.arange(1, n + 1, dtype=float)
        e = _ols(x, np.column_stack([np.ones(n), t])).resid.to_numpy(dtype=float)
    else:
        e = x - x.mean()
    if lags == "legacy":
        L = min(int(np.ceil(12.0 * np.power(n / 100.0, 0.25))), n - 1)
    elif lags in ("auto", None):
        L = min(_kpss_autolag(e, n), n - 1)
    else:
        L = int(lags)
        if L >= n:
            raise ValueError(f"시차 {L} ≥ 관측치 {n}")
    eta = np.sum(np.cumsum(e) ** 2) / n ** 2
    s = np.sum(e ** 2)
    for i in range(1, L + 1):
        s += 2 * np.dot(e[i:], e[: n - i]) * (1.0 - i / (L + 1.0))
    stat = float(eta / (s / n))
    crit = _KPSS_CRIT[trend]
    p = float(np.interp(stat, crit, _KPSS_P))
    notes = ["p값: KPSS(1992) 임계값표 보간"]
    if p in (_KPSS_P[0], _KPSS_P[-1]):
        notes.append("통계량이 표 범위 밖 — 실제 p값은 " + ("0.10보다 크다" if p == _KPSS_P[0] else "0.01보다 작다"))
    return TestResult(f"KPSS 정상성 검정{f' — {name}' if name else ''}", stat, p,
                      null=("수준" if trend == "c" else "추세") + " 정상이다",
                      rows={"임계값 10%": crit[0], "임계값 5%": crit[1], "임계값 2.5%": crit[2], "임계값 1%": crit[3],
                            "대역폭(시차)": L, "관측치": n},
                      info={"결정항": _TREND_KO[trend], "대역폭": L, "관측치": n},
                      details={"lags": L, "nobs": n, "crit": dict(zip(["10%", "5%", "2.5%", "1%"], crit))}, notes=notes)


# ---------------------------------------------------------------------------
# Engle-Granger
# ---------------------------------------------------------------------------
def engle_granger(y, X, trend: str = "c", lags: int = None, ic: str = "bic", maxlag: int = None,
                  names=None) -> TestResult:
    """Engle-Granger 공적분 검정 — y를 X(+결정항)에 회귀한 잔차의 ADF(p값·임계값은 변수 수 반영).

    예
        >>> rng = np.random.default_rng(1)
        >>> x = np.cumsum(rng.normal(size=200))
        >>> eqn.stats.engle_granger(2 * x + rng.normal(size=200), x).pvalue < 0.01
        True
    """
    y = _series(y)
    X = np.asarray(X, dtype=float)
    if X.ndim == 1:
        X = X[:, None]
    if np.isnan(X).any():
        raise ValueError("설명변수에 결측이 있습니다")
    trend = _norm_trend(trend)
    n, k = X.shape
    nv = k + 1
    if nv > 12:
        raise ValueError("변수는 12개까지(임계값표 범위)")
    Z = X if trend == "n" else np.column_stack([X, _trend_cols(n, trend)])
    co = _ols(y, Z)
    e = co.resid.to_numpy(dtype=float)
    stat, used, nobs, maxlag, _, _ = _adf_core(e, "n", lags, ic.lower() if lags is None else None, maxlag)
    p = mackinnon_p(stat, trend, nv) if trend != "n" else np.nan
    crit = mackinnon_crit(nv, trend, n - 1) if trend != "n" else np.full(3, np.nan)
    how = f"{_IC[ic.lower()]}, 최대 {maxlag}" if lags is None else "지정"
    title = "Engle-Granger 공적분 검정" + (f" — {' · '.join(names)}" if names else "")
    return TestResult(title, stat, p, null="공적분이 없다(잔차에 단위근)",
                      rows={"임계값 1%": crit[0], "임계값 5%": crit[1], "임계값 10%": crit[2], "시차": used,
                            "관측치": n, "변수 수": nv},
                      info={"결정항": _TREND_KO[trend], "시차 선택": f"{used} ({how})", "관측치": n},
                      details={"lags": used, "nobs": n, "crit": {"1%": crit[0], "5%": crit[1], "10%": crit[2]}},
                      notes=["p값: MacKinnon(1994) 근사 · 임계값: MacKinnon(2010)"],
                      data=pd.DataFrame({"공적분 회귀 계수": co.params.to_numpy(dtype=float)}))


# ---------------------------------------------------------------------------
# Johansen
# ---------------------------------------------------------------------------
def _resid_on(y, x):
    if x.size == 0:
        return y
    P, _ = pinv_svd(x)
    return y - x @ (P @ y)


def _detrend(y, order):
    if order == -1:
        return y
    V = np.vander(np.linspace(-1, 1, len(y)), order + 1)
    return _resid_on(y, V)


def johansen(Y, det: int = 0, lags: int = 1, names=None) -> TestResult:
    """Johansen 공적분 순위 검정(트레이스·최대 고유값). det: −1 없음 · 0 상수 · 1 상수 + 추세, lags = 차분 시차.

    임계값은 MacKinnon-Haug-Michelis(1999), 변수 12개까지.

    예
        >>> rng = np.random.default_rng(1)
        >>> x = np.cumsum(rng.normal(size=300))
        >>> Y = np.column_stack([x, x + rng.normal(size=300)])
        >>> eqn.stats.johansen(Y).rows["트레이스 기준 순위(5%)"]
        1
    """
    Y = np.asarray(Y, dtype=float)
    if Y.ndim != 2 or Y.shape[1] < 2:
        raise ValueError("Johansen 검정에는 시계열이 2개 이상 필요합니다")
    if np.isnan(Y).any():
        raise ValueError("시계열에 결측이 있습니다")
    if det not in (-1, 0, 1):
        raise ValueError("det는 -1·0·1 중 하나")
    nobs, m = Y.shape
    if m > 12:
        raise ValueError("변수는 12개까지(임계값표 범위)")
    f = 0 if det > -1 else det
    Y = _detrend(Y, det)
    dx = np.diff(Y, 1, axis=0)
    k = int(lags)
    z = np.column_stack([np.vstack([np.zeros((j, m)), dx[:-j]]) for j in range(1, k + 1)]) if k > 0 \
        else np.empty((len(dx), 0))
    z = z[k:]
    z = _detrend(z, f) if z.size else z
    dxk = _detrend(dx[k:], f)
    r0 = _resid_on(dxk, z)
    lx = Y[: Y.shape[0] - k][1:]
    rk = _resid_on(_detrend(lx, f), z)
    skk = rk.T @ rk / rk.shape[0]
    sk0 = rk.T @ r0 / rk.shape[0]
    s00 = r0.T @ r0 / r0.shape[0]
    sig = sk0 @ np.linalg.inv(s00) @ sk0.T
    au, du = np.linalg.eig(np.linalg.inv(skk) @ sig)
    temp = np.linalg.inv(np.linalg.cholesky(du.T @ skk @ du))
    dt = du @ temp
    order = np.flipud(np.argsort(au))
    eig = np.real(au[order])
    vec = np.real(dt[:, order])
    nz = vec.flat != 0
    if np.any(nz):
        vec *= np.sign(vec.flat[nz][0])
    t = rk.shape[0]
    trace = np.array([-t * np.sum(np.log(1 - eig[i:])) for i in range(m)])
    maxeig = np.array([-t * np.log(1 - eig[i]) for i in range(m)])
    cvt = np.array([T.JOHANSEN_TRACE[det][m - i - 1] for i in range(m)])
    cvm = np.array([T.JOHANSEN_MAXEIG[det][m - i - 1] for i in range(m)])
    table = pd.DataFrame({"고유값": eig, "트레이스": trace, "트레이스 5% 임계값": cvt[:, 1],
                          "최대 고유값": maxeig, "최대 고유값 5% 임계값": cvm[:, 1]},
                         index=pd.Index([f"순위 ≤ {r}" for r in range(m)], name="귀무가설"))
    rank_trace = int(next((r for r in range(m) if trace[r] < cvt[r, 1]), m))
    rank_max = int(next((r for r in range(m) if maxeig[r] < cvm[r, 1]), m))
    det_ko = {-1: "없음", 0: "상수", 1: "상수+추세"}[det]
    title = "Johansen 공적분 검정" + (f" — {' · '.join(names)}" if names else "")
    return TestResult(title, float(trace[0]), np.nan, null="공적분 순위 ≤ r (위에서부터 차례로)",
                      rows={"트레이스 기준 순위(5%)": rank_trace, "최대 고유값 기준 순위(5%)": rank_max},
                      info={"결정항": det_ko, "차분 시차": k, "관측치": t},
                      details={"rank_trace": rank_trace, "rank_maxeig": rank_max, "eig": eig, "trace": trace,
                               "maxeig": maxeig, "crit_trace": cvt, "crit_maxeig": cvm, "evec": vec},
                      table=table, notes=["임계값: MacKinnon-Haug-Michelis(1999) · 순위는 5% 기준"],
                      data=pd.DataFrame(vec, columns=[f"벡터{i + 1}" for i in range(m)],
                                        index=names if names else None))
