#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""VAR·VECM — 벡터자기회귀와 벡터오차수정모형 (DECISIONS D23).

    fit_var(Y, p, trend)          OLS VAR(p): 계수·Σ·정보기준·안정성
    select_order(Y, maxlags)      같은 표본에서 p = 0…maxlags의 AIC·BIC·HQ·FPE
    granger(res, caused, causing) Granger 인과 Wald F
    irf(res, h, orth)             충격반응(직교화는 Σ의 촐레스키)
    fevd(res, h)                  예측오차 분산분해
    forecast(res, steps)          점 예측
    fit_vecm(Y, k_diff, r, det)   Johansen 최우 VECM(β 정규화: 위 r×r = I)

배열(numpy)을 받고 돌려준다. 결정항: 'n' 없음 · 'c' 상수 · 'ct' 상수+추세. VECM 결정항: 'n'·'co'(상수, 관계 밖)·
'ci'(상수, 공적분 관계 안)·'lo'(선형추세, 밖)·'li'(선형추세, 안)과 그 조합('cili'·'colo' …). 정의는 statsmodels VAR·VECM과 같게 맞췄다(검증 기준값).
"""

from dataclasses import dataclass, field
from typing import List, Sequence

import numpy as np
from scipy import stats

from .regression import pinv_svd

TRENDS = ("n", "c", "ct")


def _det(T: int, trend: str, start: int = 1) -> np.ndarray:
    cols = []
    if trend in ("c", "ct"):
        cols.append(np.ones(T))
    if trend == "ct":
        cols.append(np.arange(start, start + T, dtype=float))
    return np.column_stack(cols) if cols else np.empty((T, 0))


def lag_matrix(Y: np.ndarray, p: int, trend: str = "c", offset: int = 0):
    """VAR 회귀 자료: 행 t = p+offset … T−1, Z = [결정항, y(t−1), …, y(t−p)] (statsmodels와 같은 열 순서)."""
    T, k = Y.shape
    rows = np.arange(p + offset, T)
    lags = [Y[rows - i] for i in range(1, p + 1)]
    D = _det(len(rows), trend, start=p + offset + 1)
    Z = np.column_stack([D] + lags) if lags or D.size else np.empty((len(rows), 0))
    return Y[rows], Z


@dataclass
class VARFit:
    p: int
    trend: str
    coefs: np.ndarray            # (n_det + k·p, k): 열 = 식
    resid: np.ndarray            # (T_eff, k)
    sigma_u: np.ndarray          # 자유도 보정 ÛᵀÛ/(T − 계수 수)
    sigma_mle: np.ndarray        # ÛᵀÛ/T
    cov_params: np.ndarray       # vec(B)의 공분산 = Σ_u ⊗ (ZᵀZ)⁻¹ (식별로 쌓은 순서)
    nobs: int
    k: int
    n_det: int
    Y_last: np.ndarray           # 마지막 p개 관측(예측 시작점)
    extra: dict = field(default_factory=dict)

    @property
    def ar(self) -> np.ndarray:
        """A₁…A_p: (p, k, k), Aᵢ[행 = 식, 열 = 변수]."""
        B = self.coefs[self.n_det:]
        return np.stack([B[i * self.k:(i + 1) * self.k].T for i in range(self.p)]) if self.p else np.zeros((0, self.k, self.k))

    @property
    def intercepts(self) -> np.ndarray:
        return self.coefs[:self.n_det]

    def companion(self) -> np.ndarray:
        k, p = self.k, self.p
        C = np.zeros((k * p, k * p))
        C[:k, :] = np.concatenate(list(self.ar), axis=1) if p else 0
        if p > 1:
            C[k:, :-k] = np.eye(k * (p - 1))
        return C

    def eigenvalues(self) -> np.ndarray:
        return np.linalg.eigvals(self.companion()) if self.p else np.zeros(0)

    @property
    def is_stable(self) -> bool:
        ev = self.eigenvalues()
        return bool(len(ev) == 0 or np.max(np.abs(ev)) < 1.0)

    def info_criteria(self) -> dict:
        """statsmodels VARResults.info_criteria와 같은 정의."""
        k, T = self.k, self.nobs
        ld = np.linalg.slogdet(self.sigma_mle)[1]
        free = self.p * k * k + k * self.n_det
        df_model = k * self.p + self.n_det
        return {"aic": ld + 2.0 / T * free, "bic": ld + np.log(T) / T * free,
                "hqic": ld + 2.0 * np.log(np.log(T)) / T * free,
                "fpe": ((T + df_model) / (T - df_model)) ** k * np.exp(ld)}


def fit_var(Y: np.ndarray, p: int, trend: str = "c", offset: int = 0) -> VARFit:
    Y = np.asarray(Y, dtype=float)
    if trend not in TRENDS:
        raise ValueError(f"trend는 {TRENDS} 중 하나")
    if int(p) != p or p < 0:
        raise ValueError(f"VAR 시차는 0 이상의 정수여야 합니다(받은 값 {p})")
    p = int(p)
    if Y.ndim != 2 or Y.shape[1] < 1:
        raise ValueError("Y는 (기간, 변수) 2차원 배열")
    if not np.all(np.isfinite(Y)):
        raise ValueError("VAR 자료에 결측이 있습니다")
    y, Z = lag_matrix(Y, p, trend, offset)
    T, k = y.shape
    nd = 0 if trend == "n" else (1 if trend == "c" else 2)
    if T <= Z.shape[1]:
        raise ValueError(f"관측치({T})가 식마다의 계수 수({Z.shape[1]})보다 많아야 합니다")
    P, _ = pinv_svd(Z) if Z.shape[1] else (np.zeros((0, T)), None)
    B = P @ y if Z.shape[1] else np.zeros((0, k))
    U = y - (Z @ B if Z.shape[1] else 0)
    df_resid = T - Z.shape[1]
    su = U.T @ U / df_resid
    ZZi = P @ P.T if Z.shape[1] else np.zeros((0, 0))
    return VARFit(p, trend, B, U, su, U.T @ U / T, np.kron(su, ZZi), T, k, nd, Y[len(Y) - p:] if p else Y[:0])


def select_order(Y: np.ndarray, maxlags: int, trend: str = "c") -> dict:
    """p = 0…maxlags를 같은 표본(처음 maxlags 기 제외)에서 추정해 정보기준 표와 고른 p."""
    rows = []
    for p in range(maxlags + 1):
        f = fit_var(Y, p, trend, offset=maxlags - p)
        rows.append(f.info_criteria())
    best = {c: int(np.argmin([r[c] for r in rows])) for c in ("aic", "bic", "hqic", "fpe")}
    return {"table": rows, "selected": best}


def granger(fit: VARFit, caused: Sequence[int], causing: Sequence[int]) -> dict:
    """causing 변수들의 모든 시차 계수가 caused 식에서 0인가 — Wald F(statsmodels test_causality kind='f'와 같음)."""
    k, p, nd = fit.k, fit.p, fit.n_det
    nrow = fit.coefs.shape[0]
    idx = []
    for eq in caused:
        for lag in range(p):
            for var in causing:
                idx.append(eq * nrow + nd + lag * k + var)   # vec(B): 식(열) 순서로 쌓음
    b = fit.coefs.T.ravel()
    R = np.zeros((len(idx), len(b)))
    R[np.arange(len(idx)), idx] = 1.0
    d = R @ b
    w = float(d @ np.linalg.solve(R @ fit.cov_params @ R.T, d))
    q = len(idx)
    df2 = k * (fit.nobs - nrow)
    F = w / q
    return {"F": F, "pvalue": float(stats.f.sf(F, q, df2)), "df": (q, df2), "chi2": w,
            "chi2_p": float(stats.chi2.sf(w, q))}


def ma_coefs(fit: VARFit, h: int) -> np.ndarray:
    """MA 표현 Ψ₀…Ψ_h: (h+1, k, k)."""
    k, A = fit.k, fit.ar
    Psi = np.zeros((h + 1, k, k))
    Psi[0] = np.eye(k)
    for i in range(1, h + 1):
        for j in range(1, min(i, fit.p) + 1):
            Psi[i] += Psi[i - j] @ A[j - 1]
    return Psi


def irf(fit: VARFit, h: int, orth: bool = True) -> np.ndarray:
    """충격반응 (h+1, 반응 변수, 충격 변수). orth=True면 Ψᵢ·P(P = chol(Σ_u), 1표준편차 충격)."""
    Psi = ma_coefs(fit, h)
    if not orth:
        return Psi
    P = np.linalg.cholesky(fit.sigma_u)
    return np.einsum("hij,jk->hik", Psi, P)


def fevd(fit: VARFit, h: int) -> np.ndarray:
    """예측오차 분산분해 (반응 변수, h, 충격 변수) — 각 [i, s, :]의 합 = 1 (statsmodels fevd().decomp와 같은 배열)."""
    Th = irf(fit, h - 1, orth=True)
    num = np.cumsum(Th ** 2, axis=0)                 # (h, i, j)
    tot = num.sum(axis=2, keepdims=True)
    return np.transpose(num / tot, (1, 0, 2))


def forecast(fit: VARFit, steps: int, last: np.ndarray = None, t0: int = None) -> np.ndarray:
    """점 예측 (steps, k). last = 마지막 p개 관측(기본: 추정 표본 끝), t0 = 첫 예측의 추세 값."""
    k, p = fit.k, fit.p
    hist = list(np.asarray(fit.Y_last if last is None else last, dtype=float))
    t = (fit.nobs + fit.p + 1) if t0 is None else t0
    out = []
    A = fit.ar
    for s in range(steps):
        y = np.zeros(k)
        if fit.n_det >= 1:
            y += fit.intercepts[0]
        if fit.n_det == 2:
            y += fit.intercepts[1] * (t + s)
        for j in range(p):
            y += A[j] @ hist[-1 - j]
        out.append(y)
        hist.append(y)
    return np.array(out)


# ---------------------------------------------------------------------------
# VECM (Johansen 최우)
# ---------------------------------------------------------------------------
VECM_DET = ("n", "co", "ci", "lo", "li", "cili", "colo", "coli", "cilo")


@dataclass
class VECMFit:
    k_diff: int
    rank: int
    det: str
    alpha: np.ndarray            # (k, r)
    beta: np.ndarray             # (k + 관계 안 결정항 수, r) — 위 r×r = I
    gamma: np.ndarray            # (k, k·k_diff): [Γ₁ … Γ_p]
    det_coef: np.ndarray         # (k, 관계 밖 결정항 수)
    resid: np.ndarray            # (T, k)
    sigma_u: np.ndarray          # ÛᵀÛ/T
    eigenvalues: np.ndarray
    nobs: int
    y_hist: np.ndarray           # 예측 시작용 마지막 k_diff+1개 수준
    extra: dict = field(default_factory=dict)

    @property
    def Pi(self) -> np.ndarray:
        return self.alpha @ self.beta[:self.alpha.shape[0]].T


def _det_tokens(det: str) -> List[str]:
    """'cili' → ['ci', 'li']. 각 두 글자: co·ci(상수 관계 밖·안), lo·li(선형추세 밖·안), n(없음)."""
    raw = det
    det = "".join(ch for ch in str(det).lower() if ch not in " ,+_")    # 'ci lo'·'ci+lo'도 받는다
    if det == "n":
        return []
    toks = [det[i:i + 2] for i in range(0, len(det), 2)]
    if not det or any(t not in ("co", "ci", "lo", "li") for t in toks) or len(det) % 2:
        raise ValueError(f"deterministic은 'n' 또는 co·ci·lo·li를 이은 문자열(예: 'ci', 'colo', 'cili'): {raw!r}")
    if len(set(toks)) < len(toks) or {"co", "ci"} <= set(toks) or {"lo", "li"} <= set(toks):
        raise ValueError(f"deterministic {raw!r}: 같은 결정항을 관계 안·밖에 두 번 둘 수 없습니다(co·ci, lo·li 중 하나씩)")
    return toks


def _vecm_det(T: int, det: str, start: int):
    """(관계 밖 결정항, 관계 안 결정항) 열 — statsmodels VECM과 같은 정의·순서(상수 다음 추세).
    추세는 관계 안이 start(= k_diff + 1)부터, 관계 밖이 start + 1부터(Lütkepohl 2005의 시점 표기)."""
    toks = _det_tokens(det)
    t = np.arange(start, start + T, dtype=float)
    out_ = [np.ones(T)] * ("co" in toks) + [t + 1] * ("lo" in toks)
    in_ = [np.ones(T)] * ("ci" in toks) + [t] * ("li" in toks)
    mk = lambda c: np.column_stack(c) if c else np.empty((T, 0))  # noqa: E731
    return mk(out_), mk(in_)


def fit_vecm(Y: np.ndarray, k_diff: int, rank: int, det: str = "ci") -> VECMFit:
    """Δyₜ = α(β'yₜ₋₁ + 관계 안 결정항) + Σ Γᵢ Δyₜ₋ᵢ + 관계 밖 결정항 + εₜ, Johansen 축소순위 회귀."""
    Y = np.asarray(Y, dtype=float)
    _det_tokens(det)
    T0, k = Y.shape
    if not 1 <= rank < k:
        raise ValueError(f"공적분 순위는 1 이상 {k - 1}(변수 수 − 1) 이하여야 합니다(받은 값 {rank}) — "
                         "순위 0이면 차분 VAR, 순위 = 변수 수면 수준 VAR를 쓰세요")
    if int(k_diff) != k_diff or k_diff < 0:
        raise ValueError(f"차분 시차는 0 이상의 정수여야 합니다(받은 값 {k_diff})")
    det = "".join(ch for ch in str(det).lower() if ch not in " ,+_")
    dY = np.diff(Y, axis=0)
    rows = np.arange(k_diff, len(dY))                  # dY 기준 행
    T = len(rows)
    y0 = dY[rows]
    lagd = [dY[rows - i] for i in range(1, k_diff + 1)]
    ylag = Y[rows]                                      # = y_{t-1} (dY[t] = Y[t+1] − Y[t])
    D_out, D_in = _vecm_det(T, det, start=k_diff + 1)
    Zs = np.column_stack(lagd + [D_out]) if (lagd or D_out.size) else np.empty((T, 0))
    Y1 = np.column_stack([ylag, D_in]) if D_in.size else ylag

    def res_on(A, B):
        if A.shape[1] == 0:
            return B
        P, _ = pinv_svd(A)
        return B - A @ (P @ B)
    R0, R1 = res_on(Zs, y0), res_on(Zs, Y1)
    S00, S01, S11 = R0.T @ R0 / T, R0.T @ R1 / T, R1.T @ R1 / T
    S10 = S01.T
    # S11^-½ S10 S00⁻¹ S01 S11^-½ 의 고유문제(대칭) → β = S11^-½·고유벡터
    w, V = np.linalg.eigh(S11)
    S11_mh = (V / np.sqrt(w)) @ V.T
    M = S11_mh @ S10 @ np.linalg.solve(S00, S01) @ S11_mh
    lam, E = np.linalg.eigh((M + M.T) / 2)
    order = np.argsort(lam)[::-1]
    lam, E = lam[order], E[:, order]
    beta = S11_mh @ E[:, :rank]
    beta = beta @ np.linalg.inv(beta[:rank, :rank])     # 위 r×r = I
    alpha = S01 @ beta @ np.linalg.inv(beta.T @ S11 @ beta)
    ec = Y1 @ beta
    resid_target = y0 - ec @ alpha.T
    P, _ = pinv_svd(Zs) if Zs.shape[1] else (np.zeros((0, T)), None)
    G = (P @ resid_target).T if Zs.shape[1] else np.zeros((k, 0))   # (k, k·k_diff + 밖 결정항)
    U = resid_target - (Zs @ G.T if Zs.shape[1] else 0)
    ng = k * k_diff
    return VECMFit(k_diff, rank, det, alpha, beta, G[:, :ng], G[:, ng:], U, U.T @ U / T, lam, T,
                   Y[len(Y) - (k_diff + 1):], extra={"t_last": T0})


def vecm_forecast(fit: VECMFit, steps: int) -> np.ndarray:
    """수준 예측 (steps, k)."""
    k = fit.alpha.shape[0]
    levels = list(fit.y_hist)
    diffs = [levels[i + 1] - levels[i] for i in range(len(levels) - 1)]
    t = fit.extra["t_last"]
    out = []
    for s in range(steps):
        y_prev = levels[-1]
        tt = float(t + s)
        toks = _det_tokens(fit.det)
        din = [1.0] * ("ci" in toks) + [tt] * ("li" in toks)
        dout = [1.0] * ("co" in toks) + [tt + 1] * ("lo" in toks)
        z = np.concatenate([y_prev, din]) if din else y_prev
        dy = fit.alpha @ (fit.beta.T @ z)
        for i in range(fit.k_diff):
            dy = dy + fit.gamma[:, i * k:(i + 1) * k] @ diffs[-1 - i]
        if dout:
            dy = dy + fit.det_coef @ np.asarray(dout)
        y_new = y_prev + dy
        levels.append(y_new)
        diffs.append(dy)
        out.append(y_new)
    return np.array(out)


__all__ = ["TRENDS", "VECM_DET", "VARFit", "VECMFit", "fit_var", "select_order", "granger", "ma_coefs", "irf",
           "fevd", "forecast", "fit_vecm", "vecm_forecast", "lag_matrix"]
