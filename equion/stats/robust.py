#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""강건 공분산 — 이분산 강건(HC0~HC3)·이분산·자기상관 강건(HAC, Newey-West) 샌드위치 추정.

모든 추정법(OLS·TSLS·NLS)에 같은 식을 쓴다:  V = B · S · B
    B (bread) = (GᵀG)⁻¹,  G = 회귀변수 X(OLS) · 1단계 적합값 X̂(TSLS) · ∂f/∂c(NLS)
    S (meat)  = Σ uₜuₜᵀ (HC), 또는 Γ₀ + Σₗ wₗ(Γₗ + Γₗᵀ) (HAC, Bartlett 가중 wₗ = 1 − l/(L+1)),  uₜ = gₜ·eₜ
작은 표본 보정: HC1·HAC는 n/(n−k)를 곱한다(EViews·statsmodels의 보정 선택과 같음).
"""

import numpy as np

COV_TYPES = ("nonrobust", "hc0", "hc1", "hc2", "hc3", "hac")
_ALIASES = {None: "nonrobust", "": "nonrobust", "ols": "nonrobust", "classic": "nonrobust",
            "white": "hc1", "hc": "hc1", "newey-west": "hac", "neweywest": "hac", "nw": "hac"}
_LABELS = {"nonrobust": "일반(동분산 가정)", "hc0": "이분산 강건(HC0)", "hc1": "이분산 강건(White, HC1)",
           "hc2": "이분산 강건(HC2)", "hc3": "이분산 강건(HC3)"}


def normalize_cov_type(cov_type) -> str:
    """공분산 이름을 표준 이름으로 — None·'nonrobust' → 'nonrobust', 'white' → 'hc1', 대소문자 무시.

    오류
        ValueError: 모르는 이름

    예
        >>> eqn.stats.normalize_cov_type("White"), eqn.stats.normalize_cov_type(None)
        ('hc1', 'nonrobust')
    """
    key = None if cov_type is None else str(cov_type).strip().lower()
    key = _ALIASES.get(key, key)
    if key not in COV_TYPES:
        raise ValueError(f"알 수 없는 공분산 종류: {cov_type!r} (가능: nonrobust, hc0~hc3, white, hac)")
    return key


def newey_west_lags(n: int) -> int:
    """Newey-West 고정 대역폭 규칙 ⌊4·(n/100)^(2/9)⌋ — cov='hac'의 기본 시차.

    예
        >>> eqn.stats.newey_west_lags(200)
        4
    """
    return int(np.floor(4 * (n / 100.0) ** (2.0 / 9.0)))


def cov_label(cov_type: str, lags=None) -> str:
    if cov_type == "hac":
        return f"HAC(Newey-West, Bartlett, 시차 {lags})"
    return _LABELS.get(cov_type, cov_type)


def hac_meat(u: np.ndarray, lags: int) -> np.ndarray:
    """S = Γ₀ + Σₗ wₗ(Γₗ + Γₗᵀ),  Γₗ = Σₜ uₜ uₜ₋ₗᵀ,  wₗ = 1 − l/(L+1)."""
    S = np.dot(u.T, u)
    for lag in range(1, lags + 1):
        g = np.dot(u[lag:].T, u[:-lag])
        S += (1.0 - lag / (lags + 1.0)) * (g + g.T)
    return S


def robust_cov(bread: np.ndarray, G: np.ndarray, e: np.ndarray, cov_type: str, lags: int = None,
               df_resid: float = None):
    """강건 공분산 행렬과 쓴 HAC 시차를 돌려준다. cov_type은 normalize_cov_type을 거친 값."""
    G = np.asarray(G, dtype=float)
    e = np.asarray(e, dtype=float)
    n, k = G.shape
    if df_resid is None:
        df_resid = n - k
    if cov_type in ("hc0", "hc1", "hc2", "hc3"):
        w = e ** 2
        if cov_type in ("hc2", "hc3"):
            h = np.einsum("ij,jk,ik->i", G, bread, G)          # 지렛값(leverage)
            w = w / (1.0 - h) if cov_type == "hc2" else w / (1.0 - h) ** 2
        cov = bread @ ((G * w[:, None]).T @ G) @ bread
        if cov_type == "hc1":
            cov = cov * (n / df_resid)
        return cov, None
    if cov_type == "hac":
        L = newey_west_lags(n) if lags is None else int(lags)
        if L < 0:
            raise ValueError("HAC 시차는 0 이상이어야 합니다")
        u = G * e[:, None]
        cov = bread @ hac_meat(u, L) @ bread
        cov = cov * (n / float(n - k))
        return cov, L
    raise ValueError(f"강건 공분산이 아닙니다: {cov_type}")
