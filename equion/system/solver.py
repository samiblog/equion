#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""블록 솔버 — Newton(해석적 자코비안·스케일링·라인서치) + 폴백 (엔진 v3).

방법(method):
  newton        : 감쇠 Newton (기본). 열(변수) 스케일링 + 백트래킹 라인서치
  gauss-seidel  : 식별 1차원 Newton을 순서대로 반복 (EViews 기본 방식과 같은 계열)
  broyden       : scipy root(method='broyden1')
  hybr / lm     : scipy root (MINPACK). 구 엔진의 fsolve(hybr)와 같은 계열

수렴 판정(정규화 잔차): max_i |r_i| / (1 + |좌변_i| + |우변_i|) < ftol.
실패하면 fallback 목록을 차례로 시도하고, 어떤 방법이 성공했는지 기록한다.

자코비안(jacobian): 'dense' · 'sparse'(scipy.sparse LU) · 'auto'(블록이 SPARSE_MIN 변수 이상이면 희소, D25).
희소 경로는 Newton에만 쓰이고, 폴백(hybr·lm 등)은 밀집 행렬로 받는다.
"""

import math
from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np

METHODS = ("newton", "gauss-seidel", "broyden", "hybr", "lm")
DEFAULT_FALLBACK = ("hybr", "lm", "gauss-seidel")
JACOBIANS = ("auto", "dense", "sparse")
SPARSE_MIN = 100     # 'auto'에서 희소 LU를 쓰는 블록 크기


@dataclass
class BlockResult:
    x: np.ndarray
    converged: bool
    method: str = ""
    iterations: int = 0
    max_resid: float = float("nan")
    message: str = ""
    tried: List[str] = field(default_factory=list)


class _Ctx:
    """블록 함수 호출에 필요한 고정 인자 묶음."""

    def __init__(self, cb, S, L, AF, P, t, sparse=False):
        self.cb, self.S, self.L, self.AF, self.P, self.t = cb, S, L, AF, P, t
        self.sparse = sparse and cb.jac_data is not None

    def jac_sparse(self, x):
        """희소 자코비안(CSC) — 값이 비정상이면 None(밀집 수치 미분으로)."""
        from scipy import sparse as sp
        d = self.cb.jac_data(x, self.S, self.L, self.AF, self.P, self.t)
        if d is None or not np.all(np.isfinite(d)):
            return None
        rows, cols = self.cb.jac_pattern
        return sp.csc_matrix((d, (rows, cols)), shape=(self.cb.n, self.cb.n))

    def resid(self, x):
        return self.cb.resid(x, self.S, self.L, self.AF, self.P, self.t)

    def jac(self, x):
        J = self.cb.jac(x, self.S, self.L, self.AF, self.P, self.t)
        if J is None or not np.all(np.isfinite(J)):
            return self.fd_jac(x)
        return J

    def fd_jac(self, x):
        r0 = self.resid(x)
        if r0 is None:
            return None
        n = len(x)
        J = np.empty((n, n))
        for j in range(n):
            h = 1e-7 * max(abs(x[j]), 1.0)
            xp = x.copy()
            xp[j] += h
            rp = self.resid(xp)
            if rp is None:
                return None
            J[:, j] = (rp - r0) / h
        return J

    def scale(self, x):
        p = self.cb.parts(x, self.S, self.L, self.AF, self.P, self.t)
        if p is None:
            return np.ones(len(x))
        s = 1.0 + np.abs(p[0]) + np.abs(p[1])
        return np.where(np.isfinite(s), s, 1.0)


def _norm_resid(r, scale):
    if r is None or not np.all(np.isfinite(r)):
        return math.inf
    return float(np.max(np.abs(r) / scale)) if len(r) else 0.0


def _newton(ctx: _Ctx, x0, ftol, maxiter) -> BlockResult:
    x = np.array(x0, dtype=float)
    r = ctx.resid(x)
    if r is None or not np.all(np.isfinite(r)):
        return BlockResult(x, False, "newton", 0, math.inf, "초기값에서 잔차 계산 불가(NaN/정의역)")
    scale = ctx.scale(x)
    nr = _norm_resid(r, scale)
    it = 0
    for it in range(1, maxiter + 1):
        if nr < ftol:
            return BlockResult(x, True, "newton", it - 1, nr)
        D = np.maximum(np.abs(x), 1.0)   # 열 스케일링: 규모가 다른 변수(금리~1, 통관~1e8)
        Jsp = ctx.jac_sparse(x) if ctx.sparse else None
        if Jsp is not None:
            dz = _sparse_step(Jsp, D, r)
        else:
            J = ctx.jac(x)
            if J is None:
                return BlockResult(x, False, "newton", it, nr, "자코비안 계산 불가")
            Js = J * D
            try:
                dz = np.linalg.solve(Js, -r)
            except np.linalg.LinAlgError:
                dz = np.linalg.lstsq(Js, -r, rcond=None)[0]
        dx = dz * D
        if not np.all(np.isfinite(dx)):
            return BlockResult(x, False, "newton", it, nr, "Newton 보폭 계산 불가(특이 자코비안)")
        f0 = float(np.sum((r / scale) ** 2))
        lam = 1.0
        while lam >= 1e-8:
            xn = x + lam * dx
            rn = ctx.resid(xn)
            if rn is not None and np.all(np.isfinite(rn)):
                fn = float(np.sum((rn / scale) ** 2))
                if fn <= (1 - 1e-4 * lam) * f0 or fn < (ftol ** 2):
                    break
            lam *= 0.5
        else:
            return BlockResult(x, False, "newton", it, nr, "라인서치 실패(잔차가 줄지 않음)")
        x, r = xn, rn
        scale = ctx.scale(x)
        nr = _norm_resid(r, scale)
    if nr < ftol:
        return BlockResult(x, True, "newton", it, nr)
    return BlockResult(x, False, "newton", it, nr, f"최대 반복({maxiter}) 도달")


def _sparse_step(J, D, r):
    """희소 LU로 (J·diag(D))·dz = −r. 특이하면 밀집 최소제곱으로."""
    from scipy import sparse as sp
    from scipy.sparse.linalg import splu
    Js = (J @ sp.diags(D)).tocsc()
    try:
        return splu(Js).solve(-r)
    except RuntimeError:                       # 정확히 특이
        return np.linalg.lstsq(Js.toarray(), -r, rcond=None)[0]


def _gauss_seidel(ctx: _Ctx, x0, ftol, maxiter, damping=1.0) -> BlockResult:
    cb = ctx.cb
    x = np.array(x0, dtype=float)
    args = (ctx.S, ctx.L, ctx.AF, ctx.P, ctx.t)
    for it in range(1, maxiter * 20 + 1):
        maxrel = 0.0
        for k in range(cb.n):
            for _ in range(30):
                rk = cb.eq_resid[k](x, *args)
                dk = cb.eq_deriv[k](x, *args)
                if not (math.isfinite(rk) and math.isfinite(dk)) or dk == 0.0:
                    return BlockResult(x, False, "gauss-seidel", it, math.inf,
                                       f"식 {k}에서 1차원 풀이 불가(잔차/미분 비정상)")
                step = damping * rk / dk
                x[k] -= step
                rel = abs(step) / max(abs(x[k]), 1e-8)
                maxrel = max(maxrel, rel)
                if rel < 1e-14:
                    break
        r = ctx.resid(x)
        nr = _norm_resid(r, ctx.scale(x))
        if nr < ftol:
            return BlockResult(x, True, "gauss-seidel", it, nr)
        if not math.isfinite(nr) or maxrel > 1e12:
            break
    r = ctx.resid(x)
    return BlockResult(x, False, "gauss-seidel", it, _norm_resid(r, ctx.scale(x)), "수렴하지 않음(발산/진동)")


def _scipy(ctx: _Ctx, x0, ftol, maxiter, method) -> BlockResult:
    from scipy.optimize import root
    x0 = np.array(x0, dtype=float)
    D = np.maximum(np.abs(x0), 1.0)
    scale0 = ctx.scale(x0)

    def fun(z):
        r = ctx.resid(z * D)
        if r is None or not np.all(np.isfinite(r)):
            return np.full(len(z), 1e10)
        return r / scale0

    def jac(z):
        J = ctx.jac(z * D)
        if J is None:
            return np.eye(len(z))
        return (J * D) / scale0[:, None]

    kw = {}
    if method in ("hybr", "lm"):
        kw["jac"] = jac
        kw["options"] = {"xtol": 1e-14, ("maxfev" if method == "hybr" else "maxiter"): 200 * (len(x0) + 1)}
    else:
        kw["options"] = {"maxiter": maxiter * 20, "fatol": ftol}
    try:
        sol = root(fun, x0 / D, method=method, **kw)
    except Exception as e:  # noqa: BLE001
        return BlockResult(x0, False, method, 0, math.inf, f"{type(e).__name__}: {e}")
    x = sol.x * D
    nr = _norm_resid(ctx.resid(x), ctx.scale(x))
    return BlockResult(x, nr < ftol, method, int(getattr(sol, "nfev", 0) or 0), nr,
                       "" if nr < ftol else str(getattr(sol, "message", "")))


def solve_block(cb, x0, S, L, AF, P, t, method="newton", ftol=1e-10, maxiter=50,
                fallback=DEFAULT_FALLBACK, jacobian: str = "auto") -> BlockResult:
    """블록 하나를 푼다. 주 방법 실패 시 fallback을 차례로 시도."""
    if jacobian not in JACOBIANS:
        raise ValueError(f"jacobian은 {JACOBIANS} 중 하나")
    sparse = jacobian == "sparse" or (jacobian == "auto" and cb.n >= SPARSE_MIN)
    with np.errstate(all="ignore"):
        return _solve_block(cb, x0, S, L, AF, P, t, method, ftol, maxiter, fallback, sparse)


def _solve_block(cb, x0, S, L, AF, P, t, method, ftol, maxiter, fallback, sparse=False) -> BlockResult:
    ctx = _Ctx(cb, S, L, AF, P, t, sparse)
    order = [method] + [m for m in (fallback or ()) if m != method]
    tried, best = [], None
    for m in order:
        if m == "newton":
            res = _newton(ctx, x0, ftol, maxiter)
        elif m == "gauss-seidel":
            res = _gauss_seidel(ctx, x0, ftol, maxiter)
        elif m == "broyden":
            res = _scipy(ctx, x0, ftol, maxiter, "broyden1")
            res.method = "broyden"
        elif m in ("hybr", "lm"):
            res = _scipy(ctx, x0, ftol, maxiter, m)
        else:
            raise ValueError(f"알 수 없는 풀이법: {m} (지원: {', '.join(METHODS)})")
        tried.append(m if res.converged else f"{m}✗")
        if res.converged:
            res.tried = tried
            return res
        if best is None or (math.isfinite(res.max_resid) and res.max_resid < best.max_resid):
            best = res
    best.tried = tried
    best.message = "; ".join(t for t in [best.message] if t) or "모든 방법 실패"
    return best
