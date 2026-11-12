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

수렴으로 보인 해의 확인(`_verify`, D66): 정규화 잔차는 값이 끝없이 커지면(해가 없는 블록) 반올림으로 0이 되어
'수렴'처럼 보이고, 식이 서로 종속인 블록은 아무 값에서나 잔차가 0이다. 그래서 수렴한 해도
  ① 값이 모두 유한한지, ② 식의 크기(1 + |좌변| + |우변|의 최댓값)가 시작값의 GROWTH_MAX배를 넘지 않는지,
  ③ 행·열 크기를 맞춘 자코비안이 특이하지 않은지(1-노름 역조건수 ≥ RCOND_MIN, 변수 둘 이상인 블록)
를 본다. 하나라도 어기면 그 방법은 실패로 치고 다음 방법으로 — 모두 실패하면 실패 정책(on_fail)대로 대체한다.
받아들인 해는 건드리지 않으므로 보통 모형의 결과는 바이트까지 그대로다.

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
GROWTH_MAX = 1e6     # 수렴한 해의 식 크기가 시작값의 이 배수를 넘으면 발산으로 본다
RCOND_MIN = 1e-12    # 크기를 맞춘 자코비안의 역조건수가 이보다 작으면 특이(식이 서로 종속이거나 해가 없음)


@dataclass
class BlockResult:
    x: np.ndarray
    converged: bool
    method: str = ""
    iterations: int = 0
    max_resid: float = float("nan")
    message: str = ""
    tried: List[str] = field(default_factory=list)
    # 해 확인(_verify)이 다시 계산하지 않도록 방법이 이미 구한 것(없으면 None): 시작·끝의 식 크기 벡터, 마지막 자코비안
    scale0: Optional[np.ndarray] = field(default=None, repr=False)
    scale: Optional[np.ndarray] = field(default=None, repr=False)
    J: object = field(default=None, repr=False)


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


def _size(ctx: _Ctx, x) -> float:
    """블록 식의 크기 — max_i(1 + |좌변_i| + |우변_i|). 계산할 수 없으면 1 + max|x|."""
    p = ctx.cb.parts(x, ctx.S, ctx.L, ctx.AF, ctx.P, ctx.t)
    if p is not None:
        s = 1.0 + np.abs(p[0]) + np.abs(p[1])
        s = s[np.isfinite(s)]
        if len(s):
            return float(np.max(s))
    xf = np.abs(np.asarray(x, dtype=float))
    xf = xf[np.isfinite(xf)]
    return 1.0 + (float(np.max(xf)) if len(xf) else 0.0)


def equilibrated_rcond(J, D=None, scale=None) -> float:
    """정방 행렬 J의 크기를 맞춘 1-노름 역조건수(0 = 특이, 1 = 아주 좋음).

    열에 D(변수 크기)를 곱하고 행을 scale(식 크기)로 나눈 뒤, 행·열의 최대 절댓값이 1이 되게 맞춘다 —
    변수·식의 단위와 무관한 수. 행이나 열이 모두 0이면 0. J는 밀집 배열이나 scipy 희소 행렬.
    """
    from scipy import sparse as sp
    n = J.shape[0]
    if n == 0:
        return 1.0
    if sp.issparse(J):
        A = sp.csr_matrix(J, dtype=float)
        if D is not None:
            A = A @ sp.diags(np.asarray(D, dtype=float))
        if scale is not None:
            A = sp.diags(1.0 / np.asarray(scale, dtype=float)) @ A
        if not np.all(np.isfinite(A.data)):
            return 0.0
        r = np.asarray(abs(A).max(axis=1).todense()).ravel()
        if np.any(r == 0):
            return 0.0
        A = sp.diags(1.0 / r) @ A
        c = np.asarray(abs(A).max(axis=0).todense()).ravel()
        if np.any(c == 0):
            return 0.0
        A = (A @ sp.diags(1.0 / c)).tocsc()
        from scipy.sparse.linalg import LinearOperator, onenormest, splu
        try:
            lu = splu(A)
        except RuntimeError:                   # 정확히 특이
            return 0.0
        inv = LinearOperator((n, n), matvec=lu.solve, rmatvec=lambda v: lu.solve(v, trans="T"), dtype=float)
        try:
            est = float(onenormest(inv))
        except Exception:  # noqa: BLE001 — 추정이 안 되면 특이로 보지 않는다
            return 1.0
        anorm = float(abs(A).sum(axis=0).max())
        return 0.0 if not (math.isfinite(est) and est > 0) else 1.0 / (anorm * est)
    A = np.array(J, dtype=float)
    if D is not None:
        A = A * np.asarray(D, dtype=float)[None, :]
    if scale is not None:
        A = A / np.asarray(scale, dtype=float)[:, None]
    if not np.all(np.isfinite(A)):
        return 0.0
    r = np.max(np.abs(A), axis=1)
    if np.any(r == 0):
        return 0.0
    A = A / r[:, None]
    c = np.max(np.abs(A), axis=0)
    if np.any(c == 0):
        return 0.0
    A = A / c[None, :]
    from scipy.linalg import lapack
    anorm = float(np.max(np.sum(np.abs(A), axis=0)))
    lu, _piv, info = lapack.dgetrf(A)
    if info > 0:                               # 피벗이 정확히 0
        return 0.0
    rc, info = lapack.dgecon(lu, anorm, norm="1")
    return float(rc) if info == 0 and math.isfinite(rc) else 0.0


_RC_CACHE_MAX = 256   # 블록마다 기억하는 자코비안 수(선형 블록은 자코비안이 늘 같아 한 번만 계산한다)


def _rcond_cached(cb, J) -> float:
    """블록 자코비안의 크기를 맞춘 역조건수 — 같은 자코비안(선형 블록)이면 계산해 둔 값을 쓴다.

    행·열 크기를 맞추므로(equilibrated_rcond) 변수·식의 단위를 곱한 행렬과 판정이 같다 — 그래서 값 그대로를 열쇠로 쓴다."""
    data = J.data if hasattr(J, "tocsc") else J
    try:
        key = np.ascontiguousarray(data, dtype=float).tobytes()
    except (TypeError, ValueError):
        return equilibrated_rcond(J)
    cache = cb.__dict__.setdefault("_rcond_cache", {})
    rc = cache.get(key)
    if rc is None:
        rc = equilibrated_rcond(J)
        if len(cache) < _RC_CACHE_MAX:
            cache[key] = rc
    return rc


def _verify(ctx: _Ctx, x0, res: BlockResult) -> str:
    """수렴으로 보인 해를 확인한다 — 문제가 없으면 '', 있으면 까닭(그 해는 받아들이지 않는다).

    방법이 이미 구한 식 크기·자코비안(Newton의 마지막 반복)이 있으면 그것을 쓴다(다시 계산하지 않는다)."""
    x = res.x
    if not np.all(np.isfinite(x)):
        return "해에 무한·NaN 값이 있습니다"
    n = len(x)
    s0 = float(np.max(res.scale0)) if res.scale0 is not None and len(res.scale0) else _size(ctx, x0)
    sc = res.scale if res.scale is not None else ctx.scale(x)
    s = float(np.max(sc)) if res.scale is not None and len(sc) else _size(ctx, x)
    grown = math.isfinite(s0) and math.isfinite(s) and s > GROWTH_MAX * max(s0, 1.0)
    rc = None
    if n >= 2:
        J = res.J
        if J is None and ctx.sparse:
            J = ctx.jac_sparse(x)
        if J is None:
            J = ctx.jac(x)
        rc = _rcond_cached(ctx.cb, J) if J is not None else None
    singular = rc is not None and rc < RCOND_MIN
    if grown:
        return (f"해가 없어 값이 끝없이 커집니다(발산 — 식의 크기가 시작값의 {s / max(s0, 1.0):.1e}배에서 "
                "반올림으로 잔차가 0이 되어 수렴처럼 보였습니다"
                + (f"; 자코비안 특이, 역조건수 {rc:.1e}" if singular else "") + ")")
    if singular:
        return (f"식이 서로 종속이라 해가 하나로 정해지지 않습니다(자코비안 특이 — 크기를 맞춘 역조건수 {rc:.1e}). "
                "같은 관계를 두 번 적은 식(예: 항등식과 그것을 다른 변수로 고쳐 쓴 항등식)이 없는지 보세요")
    return ""


def _newton(ctx: _Ctx, x0, ftol, maxiter) -> BlockResult:
    x = np.array(x0, dtype=float)
    r = ctx.resid(x)
    if r is None or not np.all(np.isfinite(r)):
        return BlockResult(x, False, "newton", 0, math.inf, "초기값에서 잔차 계산 불가(NaN/정의역)")
    scale = scale0 = ctx.scale(x)
    nr = _norm_resid(r, scale)
    it = 0
    Jlast = None
    for it in range(1, maxiter + 1):
        if nr < ftol:
            return BlockResult(x, True, "newton", it - 1, nr, scale0=scale0, scale=scale, J=Jlast)
        D = np.maximum(np.abs(x), 1.0)   # 열 스케일링: 규모가 다른 변수(금리~1, 통관~1e8)
        Jsp = ctx.jac_sparse(x) if ctx.sparse else None
        if Jsp is not None:
            Jlast = Jsp
            dz = _sparse_step(Jsp, D, r)
        else:
            J = ctx.jac(x)
            if J is None:
                return BlockResult(x, False, "newton", it, nr, "자코비안 계산 불가")
            Jlast = J
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
        return BlockResult(x, True, "newton", it, nr, scale0=scale0, scale=scale, J=Jlast)
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
    tried, best, rejected = [], None, ""
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
        if res.converged:
            why = _verify(ctx, x0, res)
            if why:                            # 수렴처럼 보였지만 받아들일 수 없는 해 — 다음 방법으로
                res.converged, res.message = False, why
                rejected = rejected or why
        tried.append(m if res.converged else f"{m}✗")
        if res.converged:
            res.tried = tried
            return res
        if best is None or (math.isfinite(res.max_resid) and res.max_resid < best.max_resid):
            best = res
    best.tried = tried
    if not rejected and cb.n >= 2:
        rejected = _singular_start(ctx, x0)
    # 해를 확인하다 걸린 까닭(발산·종속)이 있으면 그것이 블록의 진짜 문제다 — 다른 방법의 '수렴 못 함'보다 앞에
    best.message = rejected or "; ".join(t for t in [best.message] if t) or "모든 방법 실패"
    return best


def _singular_start(ctx: _Ctx, x0) -> str:
    """모든 방법이 실패한 블록 — 시작점의 자코비안이 특이하면 그 까닭을(아니면 '')."""
    x0 = np.asarray(x0, dtype=float)
    if not np.all(np.isfinite(x0)):
        return ""
    J = ctx.jac(x0)
    if J is None:
        return ""
    rc = equilibrated_rcond(J, np.maximum(np.abs(x0), 1.0), ctx.scale(x0))
    if rc >= RCOND_MIN:
        return ""
    return (f"자코비안이 특이합니다(크기를 맞춘 역조건수 {rc:.1e}) — 식이 서로 종속이거나(해가 하나로 정해지지 않음) "
            "서로 맞지 않습니다(해가 없음). 같은 관계를 두 번 적은 식이나, 계수를 고정해 두 식이 같은 관계가 된 곳이 없는지 보세요")
