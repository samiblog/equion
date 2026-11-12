#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""기초 분석 — 기술 통계·상관·자기상관·교차상관·히스토그램·쌍별 Granger 인과 (D50, 외부 패키지 없이 numpy·scipy로 — D17).

    describe      시리즈마다 관측치·평균·표준편차·사분위·왜도·첨도·Jarque-Bera
    correlation   상관 행렬(피어슨·스피어먼)·p값·공분산 — 공통 표본(결측이 하나라도 있는 기간은 뺀다)
    acf · pacf    자기상관·편자기상관(Yule-Walker — Durbin-Levinson)
    correlogram   시차별 자기상관·편자기상관·Ljung-Box Q·p값 표
    ccf           교차상관 corr(x_t, y_{t−k}), k = −L…L
    histogram     구간별 도수·비율·정규분포 기대도수
    granger_causality · granger_table   한 쌍 / 모든 쌍의 Granger 인과 F 검정(상수 + 각자의 시차 p개)

입력은 numpy 배열·pandas Series·DataFrame. 결측(NaN)은 시리즈마다(describe·histogram·correlogram) 또는 함께(correlation·ccf·granger) 뺀다.
"""

from dataclasses import dataclass
from typing import Optional, Sequence

import numpy as np
import pandas as pd
from scipy import stats

from .result import TestResult


def _clean(x) -> np.ndarray:
    a = np.asarray(x, dtype=float).ravel()
    return a[np.isfinite(a)]


def _frame(data) -> pd.DataFrame:
    if isinstance(data, pd.DataFrame):
        return data.astype(float)
    if isinstance(data, pd.Series):
        return data.astype(float).to_frame(data.name or "x")
    a = np.asarray(data, dtype=float)
    if a.ndim == 1:
        a = a[:, None]
    return pd.DataFrame(a, columns=[f"x{i + 1}" for i in range(a.shape[1])])


# ---------------------------------------------------------------------------
# 기술 통계
# ---------------------------------------------------------------------------
def describe(data) -> pd.DataFrame:
    """기술 통계 — 시리즈(열)마다 관측치·평균·표준편차·최소·사분위·최대·왜도·첨도·Jarque-Bera와 p값.

    왜도·첨도는 표본 모멘트(편향 그대로 — n으로 나눔)이고 첨도는 정규분포가 3이다. JB = n/6·(왜도² + (첨도 − 3)²/4).
    결측은 시리즈마다 뺀다(관측치가 다를 수 있다). 표준편차는 n − 1로 나눈다.

    매개변수
        data: DataFrame·Series·배열(열마다 시리즈)

    돌려주는 것
        DataFrame — 행이 시리즈, 열이 통계

    예
        >>> rng = np.random.default_rng(0)
        >>> d = eqn.stats.describe(pd.DataFrame({"a": rng.normal(size=200), "b": rng.uniform(size=200)}))
        >>> list(d.columns[:4]), int(d.loc["a", "관측치"]), bool(d.loc["b", "최소"] >= 0)
        (['관측치', '평균', '표준편차', '최소'], 200, True)
    """
    df = _frame(data)
    rows = {}
    for c in df.columns:
        x = _clean(df[c])
        n = len(x)
        if n == 0:
            rows[c] = {"관측치": 0}
            continue
        m = float(x.mean())
        dev = x - m
        m2 = float((dev ** 2).mean())
        sk = float((dev ** 3).mean() / m2 ** 1.5) if m2 > 0 else np.nan
        ku = float((dev ** 4).mean() / m2 ** 2) if m2 > 0 else np.nan
        jb = n / 6.0 * (sk ** 2 + 0.25 * (ku - 3) ** 2) if m2 > 0 else np.nan
        q = np.percentile(x, [25, 50, 75])
        rows[c] = {"관측치": n, "평균": m, "표준편차": float(x.std(ddof=1)) if n > 1 else np.nan, "최소": float(x.min()),
                   "25%": float(q[0]), "중앙값": float(q[1]), "75%": float(q[2]), "최대": float(x.max()),
                   "왜도": sk, "첨도": ku, "Jarque-Bera": jb,
                   "JB p값": float(stats.chi2.sf(jb, 2)) if np.isfinite(jb) else np.nan}
    out = pd.DataFrame.from_dict(rows, orient="index")
    out.index.name = "시리즈"
    return out


# ---------------------------------------------------------------------------
# 상관
# ---------------------------------------------------------------------------
@dataclass
class Correlation:
    """상관 결과 — `.corr`(상관 행렬) · `.pvalues`(같은 모양, 대각선은 NaN) · `.cov`(공분산) · `.nobs`(공통 표본) · `.method` · `.pairs()`."""

    corr: pd.DataFrame
    pvalues: pd.DataFrame
    cov: pd.DataFrame
    nobs: int
    method: str

    def pairs(self) -> pd.DataFrame:
        """쌍마다 한 줄(변수1·변수2·상관·p값) — 상관의 절댓값이 큰 순서."""
        cols = list(self.corr.columns)
        rows = []
        for i, a in enumerate(cols):
            for b in cols[i + 1:]:
                rows.append({"변수1": a, "변수2": b, "상관": float(self.corr.loc[a, b]), "p값": float(self.pvalues.loc[a, b])})
        out = pd.DataFrame(rows, columns=["변수1", "변수2", "상관", "p값"])
        if len(out):
            out = out.reindex(out["상관"].abs().sort_values(ascending=False).index).reset_index(drop=True)
        return out


def correlation(data, method: str = "pearson") -> Correlation:
    """상관 행렬 — 피어슨(값) 또는 스피어먼(순위). 공통 표본(어느 시리즈든 결측인 기간은 뺀다)에서.

    p값은 귀무가설 '상관이 0'의 t 검정(t = r·√((n−2)/(1−r²)), 자유도 n − 2 — 스피어먼은 그 근사).
    공분산은 값의 공분산(n − 1로 나눔)이다.

    매개변수
        data: DataFrame(열마다 시리즈, 둘 이상)
        method: "pearson" · "spearman"

    돌려주는 것
        Correlation — .corr · .pvalues · .cov · .nobs · .method · .pairs()

    오류
        ValueError: 시리즈가 둘보다 적음 · 공통 표본이 3보다 작음 · 모르는 method

    예
        >>> rng = np.random.default_rng(1)
        >>> x = rng.normal(size=300)
        >>> c = eqn.stats.correlation(pd.DataFrame({"x": x, "y": 2 * x + rng.normal(size=300), "z": rng.normal(size=300)}))
        >>> round(float(c.corr.loc["x", "y"]), 2), bool(c.pvalues.loc["x", "y"] < 0.01), c.pairs().iloc[0][["변수1", "변수2"]].tolist()
        (0.89, True, ['x', 'y'])
    """
    if method not in ("pearson", "spearman"):
        raise ValueError(f"method는 pearson · spearman — {method!r}")
    df = _frame(data).dropna()
    if df.shape[1] < 2:
        raise ValueError("상관은 시리즈 둘 이상")
    n = len(df)
    if n < 3:
        raise ValueError(f"공통 표본이 너무 짧습니다(관측치 {n})")
    vals = df.to_numpy()
    use = np.column_stack([stats.rankdata(vals[:, j]) for j in range(vals.shape[1])]) if method == "spearman" else vals
    sd = use.std(axis=0)
    if np.any(sd == 0):
        flat = [c for c, s in zip(df.columns, sd) if s == 0]
        raise ValueError(f"값이 하나뿐인 시리즈가 있습니다: {', '.join(map(str, flat))}")
    r = np.corrcoef(use, rowvar=False)
    r = np.clip(r, -1.0, 1.0)
    with np.errstate(divide="ignore", invalid="ignore"):
        t = r * np.sqrt((n - 2) / (1 - r ** 2))
    p = 2 * stats.t.sf(np.abs(t), n - 2)
    np.fill_diagonal(p, np.nan)
    p[~np.isfinite(t)] = 0.0
    np.fill_diagonal(p, np.nan)
    cols = list(df.columns)
    return Correlation(pd.DataFrame(r, index=cols, columns=cols), pd.DataFrame(p, index=cols, columns=cols),
                       pd.DataFrame(np.cov(vals, rowvar=False), index=cols, columns=cols), n, method)


# ---------------------------------------------------------------------------
# 자기상관
# ---------------------------------------------------------------------------
def acf(x, nlags: int) -> np.ndarray:
    """자기상관 ρ₀…ρ_L(ρ₀ = 1) — 표본 자기공분산(n으로 나눔)의 비. 결측은 뺀다.

    예
        >>> rng = np.random.default_rng(2)
        >>> e = rng.normal(size=500)
        >>> x = np.zeros(500)
        >>> for t in range(1, 500):
        ...     x[t] = 0.7 * x[t - 1] + e[t]
        >>> r = eqn.stats.acf(x, 3)
        >>> float(r[0]), bool(0.6 < r[1] < 0.8), len(r)
        (1.0, True, 4)
    """
    a = _clean(x)
    n = len(a)
    L = int(nlags)
    if not 1 <= L < n:
        raise ValueError(f"시차는 1 이상, 관측치({n})보다 작아야 합니다 (지금 {L})")
    d = a - a.mean()
    c0 = float(d @ d) / n
    if c0 == 0:
        raise ValueError("값이 하나뿐인 시리즈는 자기상관을 계산할 수 없습니다")
    out = np.empty(L + 1)
    out[0] = 1.0
    for k in range(1, L + 1):
        out[k] = float(d[k:] @ d[:-k]) / n / c0
    return out


def pacf(x, nlags: int) -> np.ndarray:
    """편자기상관 φ₁₁…φ_LL — 자기상관으로 Yule-Walker 방정식을 푼다(Durbin-Levinson). 길이 L(시차 1부터).

    예
        >>> rng = np.random.default_rng(2)
        >>> e = rng.normal(size=500)
        >>> x = np.zeros(500)
        >>> for t in range(1, 500):
        ...     x[t] = 0.7 * x[t - 1] + e[t]
        >>> p = eqn.stats.pacf(x, 3)
        >>> bool(0.6 < p[0] < 0.8), bool(abs(p[1]) < 0.15)
        (True, True)
    """
    r = acf(x, nlags)
    L = int(nlags)
    out = np.empty(L)
    phi = np.zeros(L + 1)
    prev = np.zeros(L + 1)
    v = 1.0
    for k in range(1, L + 1):
        num = r[k] - sum(prev[j] * r[k - j] for j in range(1, k))
        a = num / v if v > 0 else np.nan
        phi[:] = 0.0
        phi[k] = a
        for j in range(1, k):
            phi[j] = prev[j] - a * prev[k - j]
        v *= (1 - a * a)
        out[k - 1] = a
        prev = phi.copy()
    return out


def correlogram(x, nlags: Optional[int] = None) -> pd.DataFrame:
    """자기상관 표 — 시차별 자기상관·편자기상관·Ljung-Box Q·p값. 95% 한계 ±1.96/√n은 `attrs["band"]`에(관측치는 `attrs["nobs"]`).

    매개변수
        x: 시리즈(결측은 뺀다)
        nlags: 시차 수(없으면 min(24, n/4))

    예
        >>> rng = np.random.default_rng(3)
        >>> t = eqn.stats.correlogram(rng.normal(size=200), 8)
        >>> list(t.columns), len(t), round(t.attrs["band"], 3)
        (['자기상관', '편자기상관', 'Q', 'p값'], 8, 0.139)
    """
    a = _clean(x)
    n = len(a)
    L = int(nlags) if nlags else max(1, min(24, n // 4))
    r = acf(a, L)
    p = pacf(a, L)
    k = np.arange(1, L + 1)
    q = n * (n + 2) * np.cumsum(r[1:] ** 2 / (n - k))
    out = pd.DataFrame({"자기상관": r[1:], "편자기상관": p, "Q": q, "p값": stats.chi2.sf(q, k)}, index=pd.Index(k, name="시차"))
    out.attrs["band"] = float(1.96 / np.sqrt(n))
    out.attrs["nobs"] = n
    return out


def ccf(x, y, nlags: int) -> pd.DataFrame:
    """교차상관 — 시차 k마다 corr(x_t, y_{t−k}), k = −L…L(k > 0이면 y가 앞선다 — y의 과거와 x의 지금). 공통 표본에서.

    값은 표본 교차공분산(n으로 나눔)을 두 표준편차(n으로 나눔)로 나눈 것이다. 95% 한계 ±1.96/√n은 `attrs["band"]`에.

    예
        >>> rng = np.random.default_rng(4)
        >>> y = rng.normal(size=400)
        >>> x = np.r_[0.0, 0.0, y[:-2]] + 0.3 * rng.normal(size=400)
        >>> c = eqn.stats.ccf(x, y, 4)
        >>> int(c["상관"].abs().idxmax()), len(c)
        (2, 9)
    """
    df = pd.DataFrame({"x": np.asarray(x, dtype=float).ravel(), "y": np.asarray(y, dtype=float).ravel()}).dropna()
    n = len(df)
    L = int(nlags)
    if not 1 <= L < n:
        raise ValueError(f"시차는 1 이상, 관측치({n})보다 작아야 합니다 (지금 {L})")
    dx = df["x"].to_numpy() - df["x"].mean()
    dy = df["y"].to_numpy() - df["y"].mean()
    sx, sy = np.sqrt(dx @ dx / n), np.sqrt(dy @ dy / n)
    if sx == 0 or sy == 0:
        raise ValueError("값이 하나뿐인 시리즈는 교차상관을 계산할 수 없습니다")
    vals = []
    for k in range(-L, L + 1):
        if k >= 0:
            c = float(dx[k:] @ dy[:n - k]) / n
        else:
            c = float(dx[:n + k] @ dy[-k:]) / n
        vals.append(c / (sx * sy))
    out = pd.DataFrame({"상관": vals}, index=pd.Index(range(-L, L + 1), name="시차"))
    out.attrs["band"] = float(1.96 / np.sqrt(n))
    out.attrs["nobs"] = n
    return out


# ---------------------------------------------------------------------------
# 히스토그램
# ---------------------------------------------------------------------------
def histogram(x, bins: Optional[int] = None) -> pd.DataFrame:
    """히스토그램 — 구간(같은 폭)마다 도수·비율과 같은 평균·표준편차의 정규분포에서 기대되는 도수. 결측은 뺀다.

    매개변수
        x: 시리즈
        bins: 구간 수(없으면 스터지스 — ⌈log₂ n⌉ + 1)

    예
        >>> rng = np.random.default_rng(5)
        >>> h = eqn.stats.histogram(rng.normal(size=256))
        >>> len(h), int(h["도수"].sum()), list(h.columns[:3])
        (9, 256, ['시작', '끝', '가운데'])
    """
    a = _clean(x)
    n = len(a)
    if n < 2:
        raise ValueError(f"히스토그램에는 관측치가 둘 이상 필요합니다(지금 {n})")
    k = int(bins) if bins else int(np.ceil(np.log2(n)) + 1)
    if k < 1:
        raise ValueError(f"구간 수는 1 이상 — {bins}")
    counts, edges = np.histogram(a, bins=k)
    mu, sd = float(a.mean()), float(a.std(ddof=1))
    expect = n * (stats.norm.cdf(edges[1:], mu, sd) - stats.norm.cdf(edges[:-1], mu, sd)) if sd > 0 else np.full(k, np.nan)
    out = pd.DataFrame({"시작": edges[:-1], "끝": edges[1:], "가운데": (edges[:-1] + edges[1:]) / 2, "도수": counts.astype(int),
                        "비율": counts / n, "정규 기대도수": expect}, index=pd.Index(range(1, k + 1), name="구간"))
    out.attrs["nobs"] = n
    return out


# ---------------------------------------------------------------------------
# Granger 인과
# ---------------------------------------------------------------------------
def _lagmat(a: np.ndarray, p: int) -> np.ndarray:
    T = len(a)
    return np.column_stack([a[p - j:T - j] for j in range(1, p + 1)])


def _rss(y: np.ndarray, X: np.ndarray) -> float:
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    e = y - X @ b
    return float(e @ e)


def granger_causality(y, x, lags: int) -> TestResult:
    """Granger 인과 F 검정 — 귀무가설 'x가 y를 Granger 인과하지 않는다'(y식에서 x의 시차 계수 p개가 모두 0).

    y_t를 상수 + y의 시차 1…p (제약) 와 거기에 x의 시차 1…p 를 더한 것(무제약)에 OLS로 맞춰
    F = ((RSS_제약 − RSS_무제약)/p) / (RSS_무제약/(T − 2p − 1)). 두 시리즈가 모두 있는 기간만 쓴다(사이의 결측은 그 뒤 시차가 끊기지 않게 앞에서 뺀다).

    매개변수
        y: 결과(설명되는) 시리즈 · x: 원인 후보 시리즈 · lags: 시차 수 p

    돌려주는 것
        TestResult — .statistic(F) · .pvalue · .rows(자유도·관측치·χ²)

    예
        >>> rng = np.random.default_rng(6)
        >>> x = rng.normal(size=300)
        >>> y = np.zeros(300)
        >>> for t in range(1, 300):
        ...     y[t] = 0.5 * x[t - 1] + 0.3 * y[t - 1] + rng.normal()
        >>> eqn.stats.granger_causality(y, x, 2).reject(), eqn.stats.granger_causality(x, y, 2).reject()
        (True, False)
    """
    df = pd.DataFrame({"y": np.asarray(y, dtype=float).ravel(), "x": np.asarray(x, dtype=float).ravel()}).dropna()
    p = int(lags)
    T = len(df) - p
    if p < 1:
        raise ValueError(f"시차는 1 이상 — {lags}")
    if T - 2 * p - 1 < 1:
        raise ValueError(f"관측치({len(df)})가 시차 {p}의 Granger 검정에 모자랍니다")
    ya, xa = df["y"].to_numpy(), df["x"].to_numpy()
    Y = ya[p:]
    one = np.ones((T, 1))
    Xr = np.column_stack([one, _lagmat(ya, p)])
    Xu = np.column_stack([Xr, _lagmat(xa, p)])
    rr, ru = _rss(Y, Xr), _rss(Y, Xu)
    df2 = T - 2 * p - 1
    F = ((rr - ru) / p) / (ru / df2) if ru > 0 else np.inf
    chi2 = T * (rr - ru) / ru if ru > 0 else np.inf
    return TestResult("Granger 인과 검정", float(F), float(stats.f.sf(F, p, df2)), null="x가 y를 Granger 인과하지 않는다",
                      rows={"시차": p, "자유도": f"({p}, {df2})", "χ² 통계량": float(chi2), "χ² p값": float(stats.chi2.sf(chi2, p))},
                      info={"관측치": T}, details={"lags": p, "nobs": T, "df": (p, df2)})


def granger_table(data, lags: int, columns: Sequence[str] = None) -> pd.DataFrame:
    """모든 쌍의 Granger 인과 — 원인 → 결과 순서마다 한 줄(F·p값·관측치·5%에서 기각). 쌍마다 두 시리즈의 공통 표본에서.

    예
        >>> rng = np.random.default_rng(6)
        >>> x = rng.normal(size=300)
        >>> y = np.zeros(300)
        >>> for t in range(1, 300):
        ...     y[t] = 0.5 * x[t - 1] + 0.3 * y[t - 1] + rng.normal()
        >>> g = eqn.stats.granger_table(pd.DataFrame({"x": x, "y": y}), 2)
        >>> g[["원인", "결과", "인과(5%)"]].values.tolist()
        [['x', 'y', True], ['y', 'x', False]]
    """
    df = _frame(data)
    cols = list(columns) if columns else list(df.columns)
    if len(cols) < 2:
        raise ValueError("Granger 인과는 시리즈 둘 이상")
    rows = []
    for cause in cols:
        for effect in cols:
            if cause == effect:
                continue
            r = granger_causality(df[effect], df[cause], lags)
            rows.append({"원인": cause, "결과": effect, "F": r.statistic, "p값": r.pvalue, "관측치": r.details["nobs"],
                         "인과(5%)": bool(r.pvalue < 0.05)})
    return pd.DataFrame(rows, columns=["원인", "결과", "F", "p값", "관측치", "인과(5%)"])
