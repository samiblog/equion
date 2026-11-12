#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""회귀 결과 — 자체 OLS와 WLS·TSLS·GMM·LIML·NLS·고정 계수의 공통 결과 객체 (DECISIONS D17·D20).

OLS는 무어-펜로즈 유사역행렬(SVD, 기준 1e-15)로 푼다. 0.5.0까지 쓰던 외부 회귀 패키지와 같은 계산
순서라 계수·표준오차·t·p·F·잔차가 같고, 로그우도·AIC·BIC도 반올림 수준까지 같다.

    ols    최소제곱                    wls   가중 최소제곱(가중치 ∝ 1/분산)
    tsls   2단계 최소제곱(도구변수)    gmm   선형 GMM(2단계·반복, 가중행렬 White·HAC, Hansen J)
    liml   제한정보 최우(k-class, κ)  nls   비선형 최소제곱 결과   fixed  고정 계수
"""

import numpy as np
import pandas as pd
from scipy import stats

from .robust import cov_label, hac_meat, newey_west_lags, normalize_cov_type, robust_cov

RCOND = 1e-15


def pinv_svd(X: np.ndarray, rcond: float = RCOND):
    """(유사역행렬, 특이값) — 특이값이 최댓값×rcond 이하인 방향은 버린다(완전 공선에서도 최소 노름 해).

    예
        >>> P, sv = eqn.stats.pinv_svd(np.array([[1.0, 2.0], [2.0, 4.0], [1.0, 2.0]]))
        >>> int((sv > 1e-12).sum())                                   # 계수 1(두 열이 비례)
        1
    """
    u, s, vt = np.linalg.svd(X, False)
    s_orig = np.copy(s)
    cutoff = rcond * np.maximum.reduce(s)
    for i in range(min(X.shape)):
        s[i] = 1.0 / s[i] if s[i] > cutoff else 0.0
    return np.dot(np.transpose(vt), np.multiply(s[:, np.newaxis], np.transpose(u))), s_orig


def constant_info(X: np.ndarray):
    """(상수항 수 0|1, 상수열 위치 또는 None). 명시 상수열이 없으면 암묵적 상수(예: 계절 더미 합 = 1)도 찾는다.

    예
        >>> eqn.stats.constant_info(np.column_stack([np.ones(5), np.arange(5.0)]))
        (1, 0)
    """
    if X.shape[1] == 0:
        return 0, None
    xmax, xmin = np.max(X, axis=0), np.min(X, axis=0)
    const_idx = np.where(xmax == xmin)[0].squeeze()
    k, idx, implicit = int(const_idx.size), None, False
    if k == 1:
        if X[:, const_idx].mean() != 0:
            idx = int(const_idx)
        else:
            implicit = True
    elif k > 1:
        values = []
        for i in const_idx:
            v = X[:, i].mean()
            if v == 1:
                k, idx = 1, int(i)
                break
            values.append(v)
        else:
            pos = np.array(values) != 0
            if pos.any():
                k, idx = 1, int(const_idx[pos.argmax()])
            else:
                implicit = True
    else:
        implicit = True
    if implicit:
        aug = np.column_stack((np.ones(X.shape[0]), X))
        k, idx = int(np.linalg.matrix_rank(X) == np.linalg.matrix_rank(aug)), None
    return k, idx


class Results:
    """추정 결과. params·bse·tvalues·pvalues는 pandas Series, cov_params()는 DataFrame.

    공분산은 cov_type으로 고른다: 'nonrobust'(기본) · 'hc0'~'hc3' · 'white'(=hc1) · 'hac'(Newey-West).
    t·p값은 언제나 t 분포(자유도 df_resid)로 계산한다.
    """

    def __init__(self, method: str, params: pd.Series, y: pd.Series, fitted: pd.Series, df_resid: float,
                 cov: np.ndarray, bread: np.ndarray = None, G: np.ndarray = None, df_model: float = np.nan,
                 k_constant: int = 0, rank: int = None, wresid: np.ndarray = None, weights: np.ndarray = None,
                 cov_text: str = None):
        self.method = method
        self.params = params
        self.endog = y
        self.fittedvalues = fitted
        self.resid = y - fitted
        self.nobs = float(len(y))
        self.df_resid = float(df_resid)
        self.df_model = df_model
        self.k_constant = k_constant
        self.rank = len(params) if rank is None else rank
        self.normalized_cov_params = bread
        self._G = G
        self.cov_type, self.cov_lags = "nonrobust", None
        self._cov_nonrobust = np.asarray(cov, dtype=float)
        self._cov = self._cov_nonrobust
        # 가중 추정(WLS): wresid = √w·e(통계·강건 공분산은 가중 잔차로), weights = w. 그 밖에는 None.
        self.wresid = None if wresid is None else np.asarray(wresid, dtype=float)
        self.weights = None if weights is None else np.asarray(weights, dtype=float)
        self._cov_text = cov_text           # 공분산 설명을 따로 주는 추정법(GMM 가중행렬 등)
        e = self.resid.to_numpy(dtype=float) if self.wresid is None else self.wresid
        self.ssr = float(np.dot(e, e))
        self.scale = self.ssr / self.df_resid if self.df_resid > 0 else np.nan
        self.fvalue = np.nan
        self.f_pvalue = np.nan
        self.llf = self.aic = self.bic = np.nan
        self.extra = {}                     # 추정법별 추가 통계(J 통계량·κ·반복 수 …)

    # ---- 계수 추론 --------------------------------------------------------
    @property
    def bse(self) -> pd.Series:
        return pd.Series(np.sqrt(np.diag(self._cov)), index=self.params.index)

    @property
    def tvalues(self) -> pd.Series:
        return pd.Series(self.params.to_numpy(dtype=float) / np.sqrt(np.diag(self._cov)), index=self.params.index)

    @property
    def pvalues(self) -> pd.Series:
        t = self.params.to_numpy(dtype=float) / np.sqrt(np.diag(self._cov))
        return pd.Series(stats.t.sf(np.abs(t), self.df_resid) * 2, index=self.params.index)

    def cov_params(self) -> pd.DataFrame:
        return pd.DataFrame(self._cov, index=self.params.index, columns=self.params.index)

    @property
    def cov_label(self) -> str:
        if self._cov_text and self.cov_type == "nonrobust":
            return self._cov_text
        return cov_label(self.cov_type, self.cov_lags)

    def set_cov(self, cov_type=None, lags: int = None) -> "Results":
        """공분산 종류를 바꾼다(계수는 그대로). 같은 결과 객체를 돌려준다."""
        kind = normalize_cov_type(cov_type)
        if kind == "nonrobust":
            self._cov, self.cov_type, self.cov_lags = self._cov_nonrobust, kind, None
            return self
        if self.normalized_cov_params is None or self._G is None:
            raise ValueError(f"{self.method} 결과에는 강건 공분산을 계산할 수 없습니다"
                             "(고정 계수, 또는 GMM — GMM은 가중행렬 종류로 정한다)")
        e = self.resid.to_numpy(dtype=float) if self.wresid is None else self.wresid
        self._cov, used = robust_cov(self.normalized_cov_params, self._G, e, kind, lags, self.df_resid)
        self.cov_type, self.cov_lags = kind, used
        return self

    # ---- 적합도 -----------------------------------------------------------
    @property
    def rsquared(self) -> float:
        """중심화 R²(상수항 유무와 무관하게 종속변수 평균 기준). 가중 추정이면 가중 평균·가중 제곱합."""
        y = self.endog.to_numpy(dtype=float)
        if self.weights is not None:
            w = self.weights
            tss = float(np.sum(w * (y - np.average(y, weights=w)) ** 2))
        else:
            tss = float(np.sum((y - y.mean()) ** 2))
        return 1 - self.ssr / tss if tss > 0 else np.nan

    @property
    def rsquared_adj(self) -> float:
        n, k = self.nobs, len(self.params)
        return 1 - (1 - self.rsquared) * (n - 1) / (n - k) if n > k else np.nan

    def predict(self, X) -> np.ndarray:
        return np.asarray(X, dtype=float) @ self.params.to_numpy(dtype=float)

    def __repr__(self):
        return f"<{self.method} 결과: 계수 {len(self.params)} · 관측치 {int(self.nobs)} · 공분산 {self.cov_label}>"


def _gaussian_llf(n: int, ssr: float):
    sigma2 = ssr / n if n else np.nan
    return -0.5 * n * (np.log(2 * np.pi * sigma2) + 1) if sigma2 > 0 else np.nan


# ---------------------------------------------------------------------------
# 추정법별 결과 만들기
# ---------------------------------------------------------------------------
def ols(y: pd.Series, X: pd.DataFrame) -> Results:
    """최소제곱 — y(Series)를 X(DataFrame, 열 = 회귀변수, 상수항 열 포함)에 회귀. 유사역행렬(SVD)로 푼다.

    돌려주는 것
        Results — params · bse · tvalues · pvalues(Series) · resid · fittedvalues · rsquared · rsquared_adj · ssr · llf · aic · bic ·
        fvalue · f_pvalue · cov_params() · set_cov(cov_type, lags)

    예
        >>> rng = np.random.default_rng(0)
        >>> x = rng.normal(size=100)
        >>> X = pd.DataFrame({"const": 1.0, "x": x})
        >>> y = pd.Series(1 + 2 * x + rng.normal(size=100))
        >>> r = eqn.stats.ols(y, X)
        >>> r.params.round(3).to_dict()
        {'const': 0.945, 'x': 2.055}
        >>> round(r.rsquared, 4), int(r.nobs)
        (0.8111, 100)
    """
    yv = np.asarray(y, dtype=float)
    Xv = np.asarray(X, dtype=float)
    P, sv = pinv_svd(Xv)
    ncov = np.dot(P, np.transpose(P))
    rank = int(np.linalg.matrix_rank(np.diag(sv)))
    kc, _ = constant_info(Xv)
    beta = np.dot(P, yv)
    n = float(Xv.shape[0])
    df_model, df_resid = float(rank - kc), n - rank
    e = yv - np.dot(Xv, beta)
    ssr = np.dot(e, e)
    r = Results("OLS", pd.Series(beta, index=X.columns), y, pd.Series(np.dot(Xv, beta), index=y.index),
                df_resid, ncov * (ssr / df_resid), bread=ncov, G=Xv, df_model=df_model, k_constant=kc, rank=rank)
    if kc:  # 가중치 1의 가중 평균·합 — 0.5.0까지의 계산과 같은 반올림
        w = np.ones_like(yv)
        ess = np.sum(w * (yv - np.average(yv, weights=w)) ** 2) - ssr
    else:
        ess = np.dot(yv, yv) - ssr
    mse_model = ess / df_model if df_model != 0 else np.nan
    mse_resid = ssr / df_resid if df_resid != 0 else np.nan
    r.fvalue = float(mse_model / mse_resid)
    r.f_pvalue = float(stats.f.sf(r.fvalue, df_model, df_resid)) if df_model != 0 else np.nan
    nobs2 = n / 2.0
    r.llf = float(-nobs2 * np.log(2 * np.pi) - nobs2 * np.log(np.sum(e ** 2) / n) - nobs2)
    dfwc = df_model + kc
    r.aic = float(-2 * r.llf + 2 * dfwc)
    r.bic = float(-2 * r.llf + np.log(n) * dfwc)
    return r


def wls(y: pd.Series, X: pd.DataFrame, w) -> Results:
    """가중 최소제곱 — Σ wₜeₜ² 최소(w ∝ 1/분산). resid·fittedvalues는 가중 전 값, ssr·R²·F·강건 공분산은 가중 잔차로.

    예
        >>> rng = np.random.default_rng(0)
        >>> x = rng.normal(size=100)
        >>> X = pd.DataFrame({"const": 1.0, "x": x})
        >>> y = pd.Series(1 + 2 * x + rng.normal(size=100))
        >>> r = eqn.stats.wls(y, X, np.ones(100))
        >>> r.params.round(3).to_dict() == eqn.stats.ols(y, X).params.round(3).to_dict()
        True
    """
    yv = np.asarray(y, dtype=float)
    Xv = np.asarray(X, dtype=float)
    wv = np.asarray(w, dtype=float)
    if wv.shape != yv.shape or not np.all(np.isfinite(wv)) or np.any(wv <= 0):
        raise ValueError("WLS 가중치는 관측치마다 하나씩, 모두 양수·유한값이어야 합니다")
    sw = np.sqrt(wv)
    Xw, yw = Xv * sw[:, None], yv * sw
    P, sv = pinv_svd(Xw)
    ncov = np.dot(P, np.transpose(P))
    rank = int(np.linalg.matrix_rank(np.diag(sv)))
    kc, _ = constant_info(Xv)                          # 상수항은 가중 전 X로 판단
    beta = np.dot(P, yw)
    n = float(Xv.shape[0])
    df_model, df_resid = float(rank - kc), n - rank
    ew = yw - np.dot(Xw, beta)
    ssr = float(np.dot(ew, ew))
    r = Results("WLS", pd.Series(beta, index=X.columns), y, pd.Series(np.dot(Xv, beta), index=y.index),
                df_resid, ncov * (ssr / df_resid), bread=ncov, G=Xw, df_model=df_model, k_constant=kc, rank=rank,
                wresid=ew, weights=wv)
    tss = float(np.sum(wv * (yv - np.average(yv, weights=wv)) ** 2)) if kc else float(np.sum(wv * yv ** 2))
    ess = tss - ssr
    mse_model = ess / df_model if df_model != 0 else np.nan
    r.fvalue = float(mse_model / (ssr / df_resid)) if df_resid else np.nan
    r.f_pvalue = float(stats.f.sf(r.fvalue, df_model, df_resid)) if df_model != 0 else np.nan
    nobs2 = n / 2.0
    r.llf = float(-nobs2 * np.log(2 * np.pi) - nobs2 * np.log(ssr / n) - nobs2 + 0.5 * np.sum(np.log(wv)))
    dfwc = df_model + kc
    r.aic = float(-2 * r.llf + 2 * dfwc)
    r.bic = float(-2 * r.llf + np.log(n) * dfwc)
    return r


def tsls(y: pd.Series, X: pd.DataFrame, Z: pd.DataFrame) -> Results:
    """2단계 최소제곱 — Z는 도구변수(외생 회귀변수 포함). 두 단계 모두 유사역행렬로 푼다(조건수가 제곱되지 않는다).

    예
        >>> rng = np.random.default_rng(0)
        >>> x = rng.normal(size=100)
        >>> X = pd.DataFrame({"const": 1.0, "x": x})
        >>> y = pd.Series(1 + 2 * x + rng.normal(size=100))
        >>> Z = pd.DataFrame({"const": 1.0, "z": x + rng.normal(scale=0.1, size=100)})
        >>> round(float(eqn.stats.tsls(y, X, Z).params["x"]), 2)
        2.06
    """
    yv, Xv, Zv = (np.asarray(a, dtype=float) for a in (y, X, Z))
    n, k = Xv.shape
    if Zv.shape[1] < k:
        raise ValueError(f"도구변수 {Zv.shape[1]}개 < 계수 {k}개 — 식별 불가 (@inst에 도구를 더 넣으세요)")
    Pz, _ = pinv_svd(Zv)
    Xhat = Zv @ (Pz @ Xv)
    P, _ = pinv_svd(Xhat)
    b = P @ yv
    e = yv - Xv @ b
    bread = P @ P.T
    r = Results("TSLS", pd.Series(b, index=X.columns), y, pd.Series(Xv @ b, index=y.index), n - k,
                (float(e @ e) / (n - k)) * bread, bread=bread, G=Xhat)
    _info_criteria(r, n, k)
    return r


GMM_WEIGHTS = ("white", "hac")
_GMM_ALIASES = {None: "white", "": "white", "white": "white", "hc": "white", "hc0": "white", "robust": "white",
                "hac": "hac", "newey-west": "hac", "neweywest": "hac", "nw": "hac", "kernel": "hac"}


def _gmm_S(Zv: np.ndarray, e: np.ndarray, kind: str, lags: int) -> np.ndarray:
    """모멘트 공분산 S = (1/n)Σ (zₜeₜ)(zₜeₜ)ᵀ (White) 또는 Bartlett 가중 HAC — 중심화하지 않음."""
    u = Zv * e[:, None]
    n = len(e)
    return (u.T @ u if kind == "white" else hac_meat(u, lags)) / n


def _inv_sqrt(S: np.ndarray) -> np.ndarray:
    """대칭 양(반)정치 행렬의 역제곱근 S^-½(고윳값이 최대×1e-15 이하인 방향은 버림)."""
    vals, vecs = np.linalg.eigh((S + S.T) / 2)
    keep = vals > vals.max() * RCOND
    inv = np.zeros_like(vals)
    inv[keep] = 1.0 / np.sqrt(vals[keep])
    return (vecs * inv) @ vecs.T


def gmm(y: pd.Series, X: pd.DataFrame, Z: pd.DataFrame, weight: str = "white", lags: int = None,
        iterate: bool = False, maxiter: int = 500, tol: float = 1e-10) -> Results:
    """선형 GMM — 모멘트 E[zₜ(yₜ − xₜb)] = 0. 1단계 TSLS 잔차로 가중행렬 W = S⁻¹을 만들어 다시 추정하고(2단계),
    iterate=True면 W를 고쳐 가며 반복한다. weight: 'white' · 'hac'(Bartlett, lags). J 통계량(Hansen)은 extra에.

    예
        >>> rng = np.random.default_rng(0)
        >>> x = rng.normal(size=100)
        >>> X = pd.DataFrame({"const": 1.0, "x": x})
        >>> y = pd.Series(1 + 2 * x + rng.normal(size=100))
        >>> Z = pd.DataFrame({"const": 1.0, "z1": x + rng.normal(scale=0.1, size=100), "z2": x ** 3})
        >>> r = eqn.stats.gmm(y, X, Z)
        >>> round(float(r.params["x"]), 1), sorted(k for k in r.extra if k.startswith("j_"))
        (2.0, ['j_df', 'j_pvalue', 'j_statistic'])
    """
    yv, Xv, Zv = (np.asarray(a, dtype=float) for a in (y, X, Z))
    n, k = Xv.shape
    m = Zv.shape[1]
    if m < k:
        raise ValueError(f"도구변수 {m}개 < 계수 {k}개 — 식별 불가 (@inst에 도구를 더 넣으세요)")
    kind = _GMM_ALIASES.get(None if weight is None else str(weight).strip().lower())
    if kind is None:
        raise ValueError(f"알 수 없는 GMM 가중행렬: {weight!r} (가능: white, hac)")
    L = (newey_west_lags(n) if lags is None else int(lags)) if kind == "hac" else None
    Pz, _ = pinv_svd(Zv)
    P, _ = pinv_svd(Zv @ (Pz @ Xv))
    b = P @ yv                                          # 1단계: TSLS
    G = Zv.T @ Xv / n
    gy = Zv.T @ yv / n
    it = 0
    # 정규방정식 (GᵀWG)b = GᵀW·gy 대신 S^-½로 희게 만든 최소제곱 min‖S^-½(gy − Gb)‖를 유사역행렬로 푼다 —
    # 조건수가 제곱되지 않는다(이 자료에서 50자리 계산과의 계수 차이 2e-7 → 2e-10).
    while True:
        Wh = _inv_sqrt(_gmm_S(Zv, yv - Xv @ b, kind, L))
        M = Wh @ G
        PM, _ = pinv_svd(M)
        b_new = PM @ (Wh @ gy)
        it += 1
        moved = float(np.max(np.abs(b_new - b))) if k else 0.0
        b = b_new
        if not iterate or moved <= tol * (1.0 + float(np.max(np.abs(b)))) or it >= maxiter:
            break
    e = yv - Xv @ b
    S = _gmm_S(Zv, e, kind, L)
    # (GᵀWG)⁻¹GᵀW·Ŝ·WG(GᵀWG)⁻¹ = M⁺(W^½ŜW^½)M⁺ᵀ (M = W^½G = UΣVᵀ) — 큰 항끼리 상쇄하는 곱을 피한다
    # (표준오차가 50자리 계산과 1e-10 이내, 세 행렬 곱이면 4e-8)
    cov = PM @ (Wh @ S @ Wh) @ PM.T / n
    text = "GMM 가중행렬 " + ("White(이분산 강건)" if kind == "white" else f"HAC(Bartlett, 시차 {L})")
    r = Results("GMM", pd.Series(b, index=X.columns), y, pd.Series(Xv @ b, index=y.index), n - k, cov,
                cov_text=text + (f" · 반복 {it}회" if iterate else " · 2단계"))
    u = Wh @ (Zv.T @ e / n)
    J = float(n * u @ u)
    dfj = m - k
    r.extra = {"j_statistic": J, "j_df": dfj, "j_pvalue": float(stats.chi2.sf(J, dfj)) if dfj > 0 else np.nan,
               "gmm_weight": kind, "gmm_lags": L, "gmm_iterations": it}
    _info_criteria(r, n, k)
    return r


def _resid_on(A: np.ndarray, B: np.ndarray) -> np.ndarray:
    """B를 A의 열공간에 회귀한 잔차(A가 비면 B 그대로)."""
    if A.shape[1] == 0:
        return B
    P, _ = pinv_svd(A)
    return B - A @ (P @ B)


def liml(y: pd.Series, X: pd.DataFrame, Z: pd.DataFrame, exog=None) -> Results:
    """제한정보 최우(LIML, k-class) — b = [Xᵀ(I − κM_Z)X]⁻¹ Xᵀ(I − κM_Z)y, κ는 최소 고윳값. exog로 외생 회귀변수를 표시한다.

    예
        >>> rng = np.random.default_rng(0)
        >>> x = rng.normal(size=100)
        >>> X = pd.DataFrame({"const": 1.0, "x": x})
        >>> y = pd.Series(1 + 2 * x + rng.normal(size=100))
        >>> Z = pd.DataFrame({"const": 1.0, "z": x + rng.normal(scale=0.1, size=100)})
        >>> r = eqn.stats.liml(y, X, Z)
        >>> round(float(r.params["x"]), 2), round(r.extra["liml_kappa"], 3)
        (2.06, 1.0)
    """
    yv, Xv, Zv = (np.asarray(a, dtype=float) for a in (y, X, Z))
    n, k = Xv.shape
    if Zv.shape[1] < k:
        raise ValueError(f"도구변수 {Zv.shape[1]}개 < 계수 {k}개 — 식별 불가 (@inst에 도구를 더 넣으세요)")
    if exog is None:
        exog = [any(np.array_equal(Xv[:, j], Zv[:, c]) for c in range(Zv.shape[1])) for j in range(k)]
    exog = np.asarray(exog, dtype=bool)
    Y = np.column_stack([yv, Xv[:, ~exog]])
    Ez = _resid_on(Zv, Y)
    Ez1 = _resid_on(Xv[:, exog], Y)
    ev = np.linalg.eigvals(np.linalg.solve(Ez.T @ Ez, Ez1.T @ Ez1))
    kappa = float(np.min(np.real(ev)))
    Xr = _resid_on(Zv, Xv)
    yr = _resid_on(Zv, yv[:, None])[:, 0]
    A = Xv.T @ Xv - kappa * (Xr.T @ Xr)
    b = np.linalg.solve(A, Xv.T @ yv - kappa * (Xr.T @ yr))
    e = yv - Xv @ b
    bread = np.linalg.inv(A)
    r = Results("LIML", pd.Series(b, index=X.columns), y, pd.Series(Xv @ b, index=y.index), n - k,
                (float(e @ e) / (n - k)) * bread, bread=bread, G=Xv - Xr)
    r.extra = {"liml_kappa": kappa, "endogenous": [str(c) for c, x in zip(X.columns, exog) if not x]}
    _info_criteria(r, n, k)
    return r


def nls(y: pd.Series, params: pd.Series, fitted: pd.Series, J: np.ndarray) -> Results:
    """비선형 최소제곱의 결과 객체를 만든다 — 해(params)·적합값과 해에서의 기울기 J(관측치 × 계수)로 표준오차를 계산한다.

    예
        >>> rng = np.random.default_rng(0)
        >>> x = rng.normal(size=100)
        >>> X = pd.DataFrame({"const": 1.0, "x": x})
        >>> y = pd.Series(1 + 2 * x + rng.normal(size=100))
        >>> b = eqn.stats.ols(y, X).params
        >>> r = eqn.stats.nls(y, b, X @ b, X.to_numpy())             # 선형 식이면 OLS와 같다
        >>> bool(np.allclose(r.bse, eqn.stats.ols(y, X).bse))
        True
    """
    n, k = len(y), len(params)
    e = (y - fitted).to_numpy(dtype=float)
    try:
        bread = np.linalg.inv(J.T @ J)
    except np.linalg.LinAlgError:
        bread = np.full((k, k), np.nan)
    r = Results("NLS", params, y, fitted, n - k, (float(e @ e) / (n - k)) * bread, bread=bread, G=J)
    _info_criteria(r, n, k)
    return r


def nltsls(y: pd.Series, params: pd.Series, fitted: pd.Series, J: np.ndarray, Z) -> Results:
    """비선형 2단계 최소제곱(NL-2SLS)의 결과 객체 — 잔차 e를 도구 Z의 열공간에 투영한 제곱합 eᵀP_Z e를 최소화한 해(params)에서,
    공분산 σ̂²(ĴᵀĴ)⁻¹(Ĵ = P_Z J, σ̂² = eᵀe/(n−k))와 Sargan 과대식별 검정 n·eᵀP_Z e / eᵀe(자유도 = 도구의 계수 − 계수 수)를 낸다.
    J는 해에서의 기울기 ∂f/∂c(관측치 × 계수). 계수에 선형인 식이면 TSLS와 같다.

    예
        >>> rng = np.random.default_rng(0)
        >>> z = rng.normal(size=200)
        >>> x = z + rng.normal(size=200)
        >>> X = pd.DataFrame({"const": 1.0, "x": x})
        >>> y = pd.Series(1 + 2 * x + rng.normal(size=200))
        >>> Z = pd.DataFrame({"const": 1.0, "z": z})
        >>> t = eqn.stats.tsls(y, X, Z)
        >>> r = eqn.stats.nltsls(y, t.params, X @ t.params, X.to_numpy(), Z)    # 선형 식이면 TSLS와 같다
        >>> bool(np.allclose(r.bse, t.bse))
        True
    """
    n, k = len(y), len(params)
    Zv = np.asarray(Z, dtype=float)
    Pz, _ = pinv_svd(Zv)
    Jhat = Zv @ (Pz @ np.asarray(J, dtype=float))
    e = (y - fitted).to_numpy(dtype=float)
    try:
        bread = np.linalg.inv(Jhat.T @ Jhat)
    except np.linalg.LinAlgError:
        bread = np.full((k, k), np.nan)
    r = Results("NL-TSLS", params, y, fitted, n - k, (float(e @ e) / (n - k)) * bread, bread=bread, G=Jhat)
    _info_criteria(r, n, k)
    L = int(np.linalg.matrix_rank(Zv))
    pe = Zv @ (Pz @ e)
    ee = float(e @ e)
    sargan = n * float(e @ pe) / ee if ee > 0 else np.nan
    df = L - k
    r.extra = {"sargan_statistic": sargan, "sargan_df": df,
               "sargan_pvalue": float(stats.chi2.sf(sargan, df)) if df > 0 and np.isfinite(sargan) else np.nan}
    return r


def fixed(y: pd.Series, params: pd.Series, fitted: pd.Series) -> Results:
    """고정(외부) 계수의 결과 객체 — 표준오차 없음, 적합도 통계만.

    예
        >>> rng = np.random.default_rng(0)
        >>> x = rng.normal(size=100)
        >>> X = pd.DataFrame({"const": 1.0, "x": x})
        >>> y = pd.Series(1 + 2 * x + rng.normal(size=100))
        >>> b = pd.Series({"const": 1.0, "x": 2.0})
        >>> r = eqn.stats.fixed(y, b, X @ b)
        >>> round(r.rsquared, 3)
        0.81
    """
    k = len(params)
    r = Results("FIXED", params, y, fitted, len(y) - k, np.full((k, k), np.nan))
    _info_criteria(r, len(y), k)
    return r


def _info_criteria(r: Results, n: int, k: int):
    r.llf = _gaussian_llf(n, r.ssr)
    r.aic = -2 * r.llf + 2 * k
    r.bic = -2 * r.llf + k * np.log(n) if n else np.nan
