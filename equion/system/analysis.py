#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""모델 분석 — 동태 안정성(동반행렬 고윳값)과 시나리오 기여도 분해 (DECISIONS D24).

stability(model, t, values, measure)
    t기 값에서 모델을 선형화한다: 식마다 잔차 εₑ(y, x)의 현시점·과거 내생변수 미분 A₀, A₁ … A_L(IR 기호 미분, 정확).
    A₀Δyₜ + Σₖ AₖΔyₜ₋ₖ = 0 → Δyₜ = −A₀⁻¹ΣAₖΔyₜ₋ₖ 의 동반행렬 고윳값. |λ| < 1이면 그 점 근처의 편차가 줄어든다.
    measure='relative'(기본): 양수인 변수는 상대 편차 Δy/y로 잰다 — 성장하는 경제에서 수준 편차는 추세만큼 커지므로
    로그식 모델의 근이 성장률만큼 부풀지 않게(log Y = a + b·log Y(-1)이면 정확히 b). 'level'은 수준 편차 그대로.

decompose(model, scenario, base, s, e, variables, method)
    시나리오의 항목(외생 경로·exclude·조정항·충격·목표추적·잔차 사용)이 기준선 대비 차이에 얼마씩 기여했는지.
    method='shapley': 모든 부분집합을 풀어 Shapley 값 — 비선형 모델에서도 합이 정확히 전체 차이(항목 8개 이하).
    method='single': 항목 하나씩만 더한 차이 + '상호작용'(= 전체 − 합).
"""

import itertools
import math
from dataclasses import dataclass, field
from typing import Dict, List, Sequence

import numpy as np
import pandas as pd

from ..formula import ir


# ---------------------------------------------------------------------------
# 안정성
# ---------------------------------------------------------------------------
@dataclass
class StabilityResult:
    period: str
    eigenvalues: np.ndarray          # 모듈러스 내림차순
    measure: str
    variables: List[str]
    max_lag: int
    loadings: pd.Series = None       # 가장 큰 근의 고유벡터(현시점 부분)에서 변수별 크기(합 1)
    relative_vars: List[str] = field(default_factory=list)

    @property
    def moduli(self) -> np.ndarray:
        return np.abs(self.eigenvalues)

    @property
    def max_modulus(self) -> float:
        return float(self.moduli.max()) if len(self.eigenvalues) else 0.0

    @property
    def stable(self) -> bool:
        return self.max_modulus < 1.0

    UNIT_TOL = 1e-6

    @property
    def unit_roots(self) -> int:
        """모듈러스가 1인 근(단위근)의 수 — 차분식의 목표처럼 수준이 적분된 변수에서 생긴다."""
        return int(np.sum(np.abs(self.moduli - 1.0) <= self.UNIT_TOL))

    @property
    def explosive(self) -> int:
        """모듈러스가 1보다 큰 근의 수 — 편차가 커진다(폭발)."""
        return int(np.sum(self.moduli > 1.0 + self.UNIT_TOL))

    @property
    def verdict(self) -> str:
        """'안정'(모든 근 < 1) · '단위근'(1인 근만 있고 1보다 큰 근 없음) · '불안정'(1보다 큰 근)."""
        return "불안정" if self.explosive else ("단위근" if self.unit_roots else "안정")


def _getter(model, values: pd.DataFrame = None):
    frame = model.data.data
    T = len(frame)
    cache = {}

    def get(name):
        if name not in cache:
            arr = frame[name].to_numpy(dtype=float).copy() if name in frame.columns else np.full(T, np.nan)
            if values is not None and name in values.columns:
                v = values[name].reindex(frame.index).to_numpy(dtype=float)
                arr = np.where(np.isfinite(v), v, arr)
            cache[name] = arr
        return cache[name]
    return get, T


def stability(model, t: int, values: pd.DataFrame = None, measure: str = "relative") -> StabilityResult:
    if measure not in ("relative", "level"):
        raise ValueError("measure는 'relative' 또는 'level'")
    sysm = model.system
    if sysm.max_lead > 0:
        raise ValueError("선행(리드) 변수가 있는 모델(MCE)은 이 방법으로 안정성을 볼 수 없습니다")
    P = model.coefficient_vector()
    get, T = _getter(model, values)
    endo = list(sysm.endogenous)
    pos = {v: j for j, v in enumerate(endo)}
    m = len(endo)
    L = max(1, sysm.max_lag)
    A = np.zeros((L + 1, m, m))
    for i, e in enumerate(sysm.eqs):
        coefs = {k: float(P[e.coef_offset + k]) for k in range(e.n_coef)}
        r = e.residual
        for name, lag in e.leaves:
            if name not in pos or lag > 0:
                continue
            d = ir.deriv(r, ir.Var(name, lag))                  # ∂εₑ/∂y(t+lag) — 잎은 (이름, 시차)로 구별된다
            val = ir.evaluate(d, get, coefs, length=T)
            A[-lag, i, pos[name]] += float(np.asarray(val)[t])
    scale = np.ones((L + 1, m))
    rel = []
    if measure == "relative":
        for j, v in enumerate(endo):
            ys = np.array([get(v)[t - k] if t - k >= 0 else np.nan for k in range(L + 1)])
            if np.all(np.isfinite(ys)) and np.all(ys > 0):
                scale[:, j] = ys
                rel.append(v)
    At = A * scale[:, None, :]
    if not np.all(np.isfinite(At)):
        bad = sorted({endo[j] for j in np.argwhere(~np.isfinite(At))[:, 2]})
        raise ValueError(f"{t}기 선형화에 값이 없는 변수가 있습니다: {bad[:8]}")
    try:
        B = -np.linalg.solve(At[0], np.concatenate(list(At[1:]), axis=1))
    except np.linalg.LinAlgError:
        raise ValueError("현시점 야코비안이 특이합니다(그 시점에서 모델을 풀 수 없음)") from None
    C = np.zeros((m * L, m * L))
    C[:m] = B
    if L > 1:
        C[m:, :-m] = np.eye(m * (L - 1))
    ev, vec = np.linalg.eig(C)
    # 모듈러스가 큰 순서, 같으면(켤레 쌍) 허수부가 양인 쪽 먼저 — LAPACK·플랫폼마다 쌍의 순서가 달라도 결과 순서는 같게
    order = np.lexsort((-ev.real, -ev.imag, -np.round(np.abs(ev), 12)))
    ev, vec = ev[order], vec[:, order]
    load = None
    if len(ev):
        w = np.abs(vec[:m, 0])
        if w.sum() > 0:
            load = pd.Series(w / w.sum(), index=endo).sort_values(ascending=False)
    label = model._period_label(model.data.data.index[t])
    return StabilityResult(label, ev, measure, endo, L, load, rel)


# ---------------------------------------------------------------------------
# 시나리오 기여도
# ---------------------------------------------------------------------------
def scenario_drivers(sc, base=None) -> List[tuple]:
    """시나리오의 항목 목록 [(라벨, 적용 함수)] — 기준선(base)에 이미 같은 값으로 있는 항목은 뺀다."""
    def same(a, b):
        try:
            if isinstance(a, pd.Series) and isinstance(b, pd.Series):
                return a.equals(b)
            return bool(a == b) if not isinstance(a == b, (pd.Series, np.ndarray)) else bool(np.all(a == b))
        except Exception:  # noqa: BLE001
            return False
    out = []
    bo = base.exo_overrides if base else {}
    for k, v in sc.exo_overrides.items():
        if not (k in bo and same(bo[k], v)):
            out.append((f"외생 {k}", lambda s, k=k, v=v: s.exo_overrides.__setitem__(k, v)))
    be = base.excludes if base else {}
    for k, v in sc.excludes.items():
        if not (k in be and same(be[k], v)):
            out.append((f"고정 {k}", lambda s, k=k, v=v: s.excludes.__setitem__(k, v)))
    ba = base.add_factors if base else {}
    for k, v in sc.add_factors.items():
        if not (k in ba and same(ba[k], v)):
            out.append((f"조정항 {k}", lambda s, k=k, v=v: s.add_factors.__setitem__(k, v)))
    for item in sc.add_factor_inits:
        if not (base and item in base.add_factor_inits):
            out.append((f"조정항 유지 {item[0]}", lambda s, it=item: s.add_factor_inits.append(it)))
    for item in sc.shocks:
        if not (base and item in base.shocks):
            out.append((f"충격 {item[0]} {item[1]:+g}", lambda s, it=item: s.shocks.append(it)))
    for item in sc.controls:
        if not (base and item in base.controls):
            out.append((f"목표추적 {item[0]}←{item[1]}", lambda s, it=item: s.controls.append(it)))
    if getattr(sc, "residual_af", False) and not (base and getattr(base, "residual_af", False)):
        out.append(("추정 잔차", lambda s: setattr(s, "residual_af", True)))
    return out


@dataclass
class Decomposition:
    method: str
    total: pd.DataFrame                       # 시나리오 − 기준선 (기간 × 변수)
    contributions: Dict[str, pd.DataFrame]    # 변수 → (기간 × 항목[, 상호작용])
    drivers: List[str]
    runs: int

    def table(self, var: str) -> pd.DataFrame:
        df = self.contributions[var].copy()
        df["합계(시나리오 − 기준선)"] = self.total[var]
        return df


def decompose(model, scenario, base, s: int, e: int, variables: Sequence[str] = None, method: str = "shapley",
              mode: str = "dynamic", max_shapley: int = 8, **opts) -> Decomposition:
    from ..scenario import Scenario
    drivers = scenario_drivers(scenario, base)
    if not drivers:
        raise ValueError("기준선과 다른 시나리오 항목이 없습니다(분해할 것이 없음)")
    n = len(drivers)
    if method == "shapley" and n > max_shapley:
        raise ValueError(f"항목이 {n}개라 Shapley(2^{n}번 풀이)는 너무 큽니다 — method='single'로")
    if method not in ("shapley", "single"):
        raise ValueError("method는 'shapley' 또는 'single'")
    cache = {}

    def run(subset):
        key = frozenset(subset)
        if key not in cache:
            sc = base.copy("_decomp", "_d") if base is not None else Scenario("_decomp", "_d")
            for i in sorted(subset):
                drivers[i][1](sc)
            res = sc.run(model, s, e, mode=mode, store=False, verbose=False, **opts)
            cache[key] = res.values
        return cache[key]
    v0 = run(())
    vN = run(range(n))
    cols = list(variables) if variables else list(v0.columns)
    missing = [c for c in cols if c not in v0.columns]
    if missing:
        raise KeyError(f"모델 결과에 없는 변수: {missing}")
    total = (vN[cols] - v0[cols])
    contrib = {c: pd.DataFrame(0.0, index=v0.index, columns=[d[0] for d in drivers]) for c in cols}
    if method == "single":
        for i, (lab, _) in enumerate(drivers):
            d = run((i,))[cols] - v0[cols]
            for c in cols:
                contrib[c][lab] = d[c]
        for c in cols:
            contrib[c]["상호작용"] = total[c] - contrib[c][[d[0] for d in drivers]].sum(axis=1)
    else:
        fact = math.factorial
        for i, (lab, _) in enumerate(drivers):
            others = [j for j in range(n) if j != i]
            acc = pd.DataFrame(0.0, index=v0.index, columns=cols)
            for r in range(n):
                w = fact(r) * fact(n - r - 1) / fact(n)
                for S in itertools.combinations(others, r):
                    acc += w * (run(S + (i,))[cols] - run(S)[cols])
            for c in cols:
                contrib[c][lab] = acc[c]
    return Decomposition(method, total, contrib, [d[0] for d in drivers], len(cache))
