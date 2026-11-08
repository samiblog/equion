#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""연립(시스템) 추정 — 계수에 선형인 식 여러 개를 함께 추정한다 (DECISIONS D22).

식 i(= 1…m)는 yᵢ = Xᵢ b + εᵢ 꼴로 받는다. b는 시스템 전체의 계수 벡터(K개)이고, 식마다 쓰지 않는 계수의 열은 0이다 —
여러 식이 같은 계수를 쓰면(c(n) 공유) 그것이 곧 식 사이 제약이다. 일반 선형 제약 R·b = q는 b = b₀ + Nθ(N은 R의 영공간)로
바꿔 θ를 추정한다. 표본은 모든 식이 함께 관측되는 기간(균형 표본, T).

    ols     식별 없이 쌓은 최소제곱(같은 계수 공유 반영)
    sur     Zellner SUR(실행 가능한 GLS), iterate=True면 수렴할 때까지(= 정규 최우)
    tsls    식별 2단계 최소제곱(식마다 도구 Zᵢ로 X̂ᵢ = P_Zᵢ Xᵢ)
    3sls    3단계 최소제곱: 2SLS 잔차의 Σ로 X̂에 GLS
    fiml    완전정보 최우: 집중 로그우도 −(T/2)log|Σ̂(b)| + Σₜ log|det Jₜ(b)|, Jₜ = ∂εₜ/∂yₜ(현시점 내생변수)

GLS는 Σ^-½로 희게 만든 자료에 유사역행렬 최소제곱으로 푼다(정규방정식을 만들지 않음 — D20의 GMM과 같은 이유).
Σ̂ = ÊᵀÊ/T(자유도 보정 없음), 계수 공분산은 linearmodels SUR·IV3SLS의 기본값과 같은 정의다.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Sequence

import numpy as np
import pandas as pd
from scipy import stats

from .regression import RCOND, _inv_sqrt, pinv_svd

METHODS = ("ols", "sur", "tsls", "3sls", "fiml")


@dataclass
class SystemFit:
    """시스템 추정 결과(배열). 워크파일의 시스템 객체가 표·pandas로 바꿔 보인다."""
    method: str
    params: np.ndarray          # (K,)
    cov: np.ndarray             # (K, K)
    resid: np.ndarray           # (T, m) 구조 잔차
    sigma: np.ndarray           # (m, m) 잔차 공분산 ÊᵀÊ/T
    iterations: int = 1
    loglik: float = np.nan
    extra: dict = field(default_factory=dict)

    @property
    def bse(self) -> np.ndarray:
        return np.sqrt(np.diag(self.cov))


def restriction_basis(R: Optional[np.ndarray], q: Optional[np.ndarray], K: int):
    """R·b = q → (b₀, N): b = b₀ + Nθ. R이 없으면 (0, I)."""
    if R is None or len(R) == 0:
        return np.zeros(K), np.eye(K)
    R = np.atleast_2d(np.asarray(R, dtype=float))
    q = np.asarray(q, dtype=float).ravel()
    u, s, vt = np.linalg.svd(R)
    rank = int(np.sum(s > s.max() * 1e-12))
    b0 = np.linalg.pinv(R) @ q
    if np.max(np.abs(R @ b0 - q)) > 1e-8 * (1 + np.max(np.abs(q))):
        raise ValueError("제약이 서로 맞지 않습니다(R·b = q를 만족하는 b가 없음)")
    N = vt[rank:].T
    if N.shape[1] == 0:
        raise ValueError("제약이 계수 수만큼 있어 추정할 것이 남지 않습니다")
    return b0, N


def _whiten(blocks: Sequence[np.ndarray], W: np.ndarray) -> np.ndarray:
    """(Σ^-½ ⊗ I)·[블록 쌓기]: i번째 블록 = Σⱼ Wᵢⱼ·blockⱼ."""
    m = len(blocks)
    return np.concatenate([sum(W[i, j] * blocks[j] for j in range(m)) for i in range(m)], axis=0)


def _sigma(E: np.ndarray) -> np.ndarray:
    return E.T @ E / E.shape[0]


def _stack_fit(ys, Xs, N, b0, W=None):
    """(희게 만든) 쌓은 최소제곱 → (b, (X̃ᵀX̃)⁻¹(θ 공간), θ의 유사역행렬)."""
    m = len(ys)
    yt = [ys[i] - Xs[i] @ b0 for i in range(m)]
    XN = [Xs[i] @ N for i in range(m)]
    if W is None:
        Xa, ya = np.concatenate(XN, axis=0), np.concatenate(yt)
    else:
        Xa, ya = _whiten(XN, W), _whiten([v[:, None] for v in yt], W)[:, 0]
    P, _ = pinv_svd(Xa)
    theta = P @ ya
    return b0 + N @ theta, P @ P.T, P


def _resid(ys, Xs, b) -> np.ndarray:
    return np.column_stack([ys[i] - Xs[i] @ b for i in range(len(ys))])


def _project(Xs, Zs):
    """X̂ᵢ = P_Zᵢ Xᵢ (도구가 없으면 Xᵢ 그대로)."""
    out = []
    for X, Z in zip(Xs, Zs):
        if Z is None:
            out.append(X)
        else:
            Pz, _ = pinv_svd(Z)
            out.append(Z @ (Pz @ X))
    return out


def _cov_sandwich(Xs, N, A_inv, S):
    """OLS·2SLS 시스템의 공분산 N·A⁻¹·Xᵀ(Σ⊗I)X·A⁻¹·Nᵀ (식 사이 상관을 반영 — linearmodels의 full_cov)."""
    m = len(Xs)
    XN = [X @ N for X in Xs]
    meat = sum(S[i, j] * XN[i].T @ XN[j] for i in range(m) for j in range(m))
    return N @ A_inv @ meat @ A_inv @ N.T


def fit_linear(ys: List[np.ndarray], Xs: List[np.ndarray], method: str = "ols", Zs: List[np.ndarray] = None,
               R=None, q=None, iterate: bool = False, maxiter: int = 1000, tol: float = 1e-10) -> SystemFit:
    """선형 시스템 추정. ys: 식마다 (T,), Xs: 식마다 (T, K), Zs: 식마다 도구 (T, Lᵢ) 또는 None."""
    method = method.lower()
    if method not in ("ols", "sur", "tsls", "3sls"):
        raise ValueError(f"알 수 없는 시스템 추정법: {method}")
    m, K = len(ys), Xs[0].shape[1]
    b0, N = restriction_basis(R, q, K)
    if method in ("tsls", "3sls"):
        if Zs is None or all(z is None for z in Zs):
            raise ValueError(f"{method}에는 도구변수가 필요합니다")
        for i, (X, Z) in enumerate(zip(Xs, Zs)):
            used = np.flatnonzero(np.any(X != 0, axis=0))
            if Z is not None and np.linalg.matrix_rank(Z) < len(used):
                raise ValueError(f"식 {i + 1}: 도구변수({np.linalg.matrix_rank(Z)}개)가 계수({len(used)}개)보다 적어 식별 불가")
        Xr = _project(Xs, Zs)
    else:
        Xr = Xs
    b, Ainv, _ = _stack_fit(ys, Xr, N, b0)                  # 1단계: (2)SLS
    E = _resid(ys, Xs, b)
    S = _sigma(E)
    it = 1
    if method in ("ols", "tsls"):
        cov = _cov_sandwich(Xr, N, Ainv, S)
        return SystemFit(method, b, cov, E, S, it)
    while True:                                             # SUR·3SLS: Σ̂로 GLS(반복 가능)
        W = _inv_sqrt(S)
        b_new, Ainv, _ = _stack_fit(ys, Xr, N, b0, W)
        it += 1
        moved = float(np.max(np.abs(b_new - b)))
        b = b_new
        E = _resid(ys, Xs, b)
        S_new = _sigma(E)
        if not iterate or moved <= tol * (1 + float(np.max(np.abs(b)))) or it > maxiter:
            break
        S = S_new
    cov = N @ Ainv @ N.T
    fit = SystemFit(method, b, cov, E, S_new, it - 1)
    fit.extra["sigma_used"] = S                             # 마지막 GLS에 쓴 Σ̂
    if method == "sur":
        fit.loglik = gaussian_loglik(E)
    return fit


def gaussian_loglik(E: np.ndarray, logdetJ: float = 0.0) -> float:
    """집중 정규 로그우도 −(Tm/2)(1 + log 2π) − (T/2)log|ÊᵀÊ/T| + Σₜ log|det Jₜ|."""
    T, m = E.shape
    sign, ld = np.linalg.slogdet(_sigma(E))
    if sign <= 0:
        return -np.inf
    return float(-0.5 * T * m * (1 + np.log(2 * np.pi)) - 0.5 * T * ld + logdetJ)


def fit_fiml(ys: List[np.ndarray], Xs: List[np.ndarray], A: np.ndarray, B: np.ndarray, start: np.ndarray,
             R=None, q=None, maxiter: int = 2000, gtol: float = 1e-9) -> SystemFit:
    """완전정보 최우(계수에 선형인 식). 잔차 εᵢₜ = yᵢₜ − Xᵢₜb, 현시점 내생변수에 대한 야코비안 Jₜ(b) = Aₜ + Σₖ bₖBₖₜ.

    A: (T, m, m), B: (K, T, m, m). 최대화는 해석적 기울기(BFGS) — ∂/∂bₖ = tr(Σ̂⁻¹ÊᵀXₖ) + Σₜ tr(Jₜ⁻¹Bₖₜ).
    공분산은 관측 정보: 해석적 기울기의 수치 미분으로 만든 헤시안의 −역행렬."""
    from scipy.optimize import minimize
    m, K = len(ys), Xs[0].shape[1]
    T = len(ys[0])
    b0, N = restriction_basis(R, q, K)
    Xk = np.stack([np.column_stack([Xs[i][:, k] for i in range(m)]) for k in range(K)])   # (K, T, m)
    Y = np.column_stack(ys)

    def parts(b):
        E = Y - np.einsum("ktm,k->tm", Xk, b)
        J = A + np.einsum("ktij,k->tij", B, b)
        return E, J

    def negll(theta):
        b = b0 + N @ theta
        E, J = parts(b)
        sgn, ld = np.linalg.slogdet(J)
        if np.any(sgn == 0):
            return np.inf
        val = gaussian_loglik(E, float(np.sum(ld)))
        return -val if np.isfinite(val) else np.inf

    def grad_b(b):
        E, J = parts(b)
        Sinv = np.linalg.inv(_sigma(E))
        g1 = np.einsum("ti,ij,ktj->k", E, Sinv, Xk)          # tr(Σ⁻¹ÊᵀXₖ)
        Jinv = np.linalg.inv(J)                              # (T, m, m)
        g2 = np.einsum("tij,ktji->k", Jinv, B)               # Σₜ tr(Jₜ⁻¹Bₖₜ)
        return g1 + g2

    def neggrad(theta):
        return -(N.T @ grad_b(b0 + N @ theta))
    th0 = np.linalg.lstsq(N, np.asarray(start, dtype=float) - b0, rcond=None)[0]
    res = minimize(negll, th0, jac=neggrad, method="BFGS", options={"gtol": gtol, "maxiter": maxiter})
    if not np.isfinite(res.fun):
        raise ValueError("FIML: 로그우도를 계산할 수 없습니다(야코비안이 특이) — 시작값·식을 확인하세요")
    theta = res.x

    def hessian(th):
        """관측 정보: 해석적 기울기를 중앙 차분한 헤시안."""
        h = 1e-5 * np.maximum(1.0, np.abs(th))
        I = np.eye(len(th))
        H = np.column_stack([(neggrad(th + h[j] * I[j]) - neggrad(th - h[j] * I[j])) / (2 * h[j]) for j in range(len(th))])
        return (H + H.T) / 2
    # BFGS가 기울기 1e-6 근처에서 멈추는 경우가 있어 뉴턴 단계로 마무리한다(로그우도가 줄지 않을 때만 받아들임)
    for _ in range(20):
        g = neggrad(theta)
        if np.max(np.abs(g)) < 1e-10:
            break
        try:
            step = np.linalg.solve(hessian(theta), g)
        except np.linalg.LinAlgError:
            break
        cand = theta - step
        if not negll(cand) <= negll(theta) + 1e-12 * abs(negll(theta)):
            break
        theta = cand
    H = hessian(theta)
    try:
        cov_t = np.linalg.inv(H)
    except np.linalg.LinAlgError:
        cov_t = np.linalg.pinv(H)
    b = b0 + N @ theta
    E, _ = parts(b)
    fit = SystemFit("fiml", b, N @ cov_t @ N.T, E, _sigma(E), int(res.nit), loglik=-float(negll(theta)))
    gnorm = float(np.max(np.abs(neggrad(theta))))
    fit.extra.update({"converged": bool(gnorm < 1e-6), "message": str(res.message), "gradient_norm": gnorm})
    return fit


def wald(fit: SystemFit, R: np.ndarray, q: np.ndarray, df_resid: float = None):
    """시스템 계수의 선형 제약 Wald: χ²(r)와 F(r, df) — df_resid가 없으면 χ²만."""
    R = np.atleast_2d(np.asarray(R, dtype=float))
    q = np.asarray(q, dtype=float).ravel()
    d = R @ fit.params - q
    V = R @ fit.cov @ R.T
    sv = np.linalg.svd(V, compute_uv=False)
    # 특이 판정의 잣대: 제약에 든 계수 표준오차로 만든 크기 — V 자신의 최대 특이값만 쓰면 제약이 하나(1×1)일 때
    # 언제나 최소 = 최대라 이미 넣은 제약(V ≈ 0, 반올림으로 음수일 수도)을 알아보지 못한다
    se = np.sqrt(np.clip(np.diag(fit.cov), 0.0, None))
    scale = float(np.max((np.abs(R) @ se) ** 2)) if R.size else 0.0
    if sv.size == 0 or sv.min() <= 1e-12 * max(sv.max(), 1e-300) or sv.min() <= 1e-10 * max(scale, 1e-300):
        raise ValueError("제약의 공분산이 특이합니다 — 이미 추정에 넣은 제약(restrict·공유 c(n))이거나 서로 겹치는 제약입니다. "
                         "제약 없이 추정한 뒤 검정하세요.")
    w = float(d @ np.linalg.solve(V, d))
    r = R.shape[0]
    out = {"chi2": w, "chi2_p": float(stats.chi2.sf(w, r)), "r": r}
    if df_resid:
        out.update({"F": w / r, "F_p": float(stats.f.sf(w / r, r, df_resid))})
    return out


__all__ = ["METHODS", "SystemFit", "fit_linear", "fit_fiml", "gaussian_loglik", "restriction_basis", "wald", "RCOND"]
