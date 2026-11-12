#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""시나리오·전망·확률 시뮬·목표추적·승수 (엔진 v3, EViews Model 시나리오 대응).

    sc = Scenario("high_oil")
    sc.override("POIL", {"2020Q1": 150, "2020Q2": 150})  # 외생 경로(EViews override)
    sc.exclude("RL", "2020Q1", "2020Q4")                  # 내생을 식 대신 경로로 고정(exclude)
    sc.add_factor("CN", {"2020Q1": 1.0})                  # 식 조정항(LHS 단위)
    sc.init_add_factor("P", base="2019Q4")                # 기준시점 잔차를 이후로 유지
    sc.shock("R", 1.0, "2020Q1")                          # 외생 +1 (수준) 충격
    res = sc.run(model, "2023Q1", "2024Q4")                # ScenarioResult
    res.diff(base_res)                                     # 기준선 대비 차이

    stochastic_simulation(model, s, e, reps=200)           # 잔차 부트스트랩(+계수 불확실성)
    control_simulation(model, "Y", "G", path, s, e)       # 목표 경로를 맞추는 도구변수
    multipliers(model, "R", 1.0, s, e)                     # 충격 승수(동태 반응)
"""

import copy
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
import pandas as pd

from ..system.simulate import Control, SimulationError, SimulationResult
from ..log import engine as _log


# ---------------------------------------------------------------------------
# 결과
# ---------------------------------------------------------------------------
@dataclass
class ScenarioResult:
    name: str
    alias: str
    sim: SimulationResult

    @property
    def values(self) -> pd.DataFrame:
        return self.sim.values

    @property
    def status(self) -> List[dict]:
        return self.sim.status

    def aliased(self) -> pd.DataFrame:
        """열 이름에 시나리오 별칭을 붙인 표(EViews X_0, X_1 대응)."""
        return self.values.add_suffix(self.alias)

    def diff(self, other: "ScenarioResult") -> pd.DataFrame:
        cols = [c for c in self.values.columns if c in other.values.columns]
        return self.values[cols] - other.values[cols]

    def pct_diff(self, other: "ScenarioResult") -> pd.DataFrame:
        cols = [c for c in self.values.columns if c in other.values.columns]
        base = other.values[cols]
        return (self.values[cols] - base) / base.abs().where(base != 0) * 100

    def counts(self) -> Dict[str, int]:
        return self.sim.counts()

    def to_csv(self, path: str):
        out = self.values.copy()
        out.insert(0, "period", [s["period"] for s in self.sim.status])
        out.insert(1, "status", [s["status"] for s in self.sim.status])
        out.to_csv(path, index=False, encoding="utf-8-sig")
        return path


# ---------------------------------------------------------------------------
# 시나리오
# ---------------------------------------------------------------------------
class Scenario:
    """전망/정책충격 시나리오 — 외생 경로·exclude·조정항·충격·목표추적 묶음."""

    def __init__(self, name: str = "baseline", alias: str = None):
        self.name = name
        self.alias = alias or ("_0" if name == "baseline" else f"_{name}")
        self.exo_overrides: Dict[str, object] = {}     # {var: Series|{period: value}|scalar}
        self.excludes: Dict[str, object] = {}          # {var: True|(start, end)}
        self.add_factors: Dict[str, object] = {}       # {종속변수표기|목표변수: 경로}
        self.add_factor_inits: List[Tuple[str, str, str]] = []  # (var, base, how)
        self.shocks: List[Tuple[str, float, object, object, str]] = []
        self.controls: List[Tuple[str, str, object]] = []
        self.residual_af = False                       # True면 표본 내 추정 잔차를 조정항으로

    # --- 구성 -----------------------------------------------------------
    def set_exo(self, var, period, value):
        """외생변수 한 시점 값 지정(하위호환)."""
        cur = self.exo_overrides.setdefault(var, {})
        if not isinstance(cur, dict):
            raise ValueError(f"{var}는 이미 경로 전체가 지정되어 있습니다(override)")
        cur[period] = value
        return self

    def override(self, var: str, path):
        """외생 경로(또는 exclude된 내생의 고정 경로) 지정: Series / {시점: 값} / 스칼라.
        exclude하지 않은 내생변수에 주면 풀이 구간 밖 값(동적 풀이의 초기 시차, 정적 풀이의 시차)으로만 쓰인다."""
        self.exo_overrides[var] = path
        return self

    def exclude(self, var: str, start=None, end=None):
        """내생변수를 식 대신 실측/override 경로로 고정(EViews exclude)."""
        self.excludes[var] = True if (start is None and end is None) else (start, end)
        return self

    def add_factor(self, var: str, path):
        """식 조정항(좌변 단위)을 더한다. var는 종속변수 표기 또는 목표변수."""
        self.add_factors[var] = path
        return self

    def init_add_factor(self, var: str, base, how: str = "hold"):
        """기준시점 base의 식 잔차를 조정항으로 삼아 지평 내내 유지(how='hold').

        모델이 base 시점의 실측을 정확히 재현하도록 '착지'시킬 때 쓴다.
        """
        if how not in ("hold",):
            raise ValueError("how는 'hold'만 지원합니다")
        self.add_factor_inits.append((var, base, how))
        return self

    def shock(self, var: str, value: float, start, end=None, kind: str = "level"):
        """충격: 외생은 경로를 kind('level' 가산 | 'pct' 비율)로 바꾸고,
        내생이거나 kind='add_factor'면 그 식의 조정항에 더한다. end 생략 = 한 기간."""
        if kind not in ("level", "pct", "add_factor"):
            raise ValueError("kind는 'level' | 'pct' | 'add_factor'")
        self.shocks.append((var, float(value), start, end, kind))
        return self

    def use_residuals(self, on: bool = True):
        """표본 내 추정 잔차를 모든 추정식의 조정항으로 더한다(과거 재현, Model.hs(add_factors=True)와 같음)."""
        self.residual_af = bool(on)
        return self

    def control(self, target: str, instrument: str, path):
        """목표추적: target 경로를 맞추도록 instrument(외생)를 푼다."""
        self.controls.append((target, instrument, path))
        return self

    def copy(self, name: str = None, alias: str = None) -> "Scenario":
        sc = copy.deepcopy(self)
        if name:
            sc.name = name
            sc.alias = alias or f"_{name}"
        return sc

    # --- 실행 입력 구성 ---------------------------------------------------
    def build(self, model, start: int, end: int):
        """model.simulate에 넘길 (overrides, excludes, AF 배열, controls)을 만든다."""
        T = len(model.data.data)
        system = model.system
        ov = {k: model._series_to_array(v, T) for k, v in self.exo_overrides.items()}
        AF = model._af_matrix(self.add_factors or False, T)
        if getattr(self, "residual_af", False):
            AF = AF + model._af_matrix(True, T)
        eq_slot = {}
        for k, eq in enumerate(model.equations):
            eq_slot[eq.dependent_var] = k
            eq_slot[eq.target] = k
        for var, base, how in self.add_factor_inits:
            if var not in eq_slot:
                raise SimulationError(f"init_add_factor: '{var}'에 해당하는 추정식이 없습니다")
            k = eq_slot[var]
            resid = model.equations[k].residual_series()
            b = model._to_index(base)
            val = resid.iloc[b]
            if not np.isfinite(val):
                raise SimulationError(f"init_add_factor: {var}의 {base} 잔차를 계산할 수 없습니다(데이터 결측)")
            AF[b + 1:end + 1, k] += val
        for var, value, s0, e0, kind in self.shocks:
            a = model._to_index(s0)
            b = model._to_index(e0, end=True) if e0 is not None else a
            if kind == "add_factor" or var in eq_slot and var in system.endogenous:
                if var not in eq_slot:
                    raise SimulationError(f"shock: '{var}'에 해당하는 추정식이 없습니다(항등식 변수는 조정항 불가)")
                AF[a:b + 1, eq_slot[var]] += value
                continue
            if var in system.endogenous:
                raise SimulationError(f"shock: '{var}'는 항등식이 결정하는 내생변수 — 충격을 줄 식이 없습니다")
            if var not in system.var_index:
                raise SimulationError(f"shock: '{var}'는 모델에서 쓰이지 않습니다")
            base_path = ov.get(var)
            if base_path is None:
                base_path = model.data.data[var].to_numpy(dtype=float).copy() \
                    if var in model.data.data.columns else np.full(T, np.nan)
            else:
                actual = model.data.data[var].to_numpy(dtype=float) if var in model.data.data.columns \
                    else np.full(T, np.nan)
                base_path = np.where(np.isfinite(base_path), base_path, actual)
            new = base_path.copy()
            if kind == "level":
                new[a:b + 1] = base_path[a:b + 1] + value
            else:
                new[a:b + 1] = base_path[a:b + 1] * (1 + value / 100.0)
            ov[var] = new
        ctrls = [Control(t, i, model._series_to_array(p, T)) for t, i, p in self.controls]
        return ov, dict(self.excludes), AF, ctrls

    def run(self, model, start, end, mode: str = "dynamic", store: bool = True, **kw) -> ScenarioResult:
        s, e = model._to_index(start), model._to_index(end, end=True)
        ov, ex, AF, ctrls = self.build(model, s, e)
        sim = model.simulate(s, e, mode=mode, sim_id=self.name, add_factors=AF,
                             overrides=ov, excludes=ex, controls=ctrls, **kw)
        res = ScenarioResult(self.name, self.alias, sim)
        if store:
            if not hasattr(model, "scenario_results") or model.scenario_results is None:
                model.scenario_results = {}
            model.scenario_results[self.name] = res
        return res


# ---------------------------------------------------------------------------
# 전망 보조
# ---------------------------------------------------------------------------
def missing_exogenous(model, start, end, scenario: Scenario = None) -> Dict[str, List[str]]:
    """지평에서 현시점 값이 비어 있는 외생변수 → 비어 있는 기간 라벨 목록."""
    s, e = model._to_index(start), model._to_index(end, end=True)
    T = len(model.data.data)
    ov = {}
    if scenario is not None:
        ov = {k: model._series_to_array(v, T) for k, v in scenario.exo_overrides.items()}
    out = {}
    idx = model.data.data.index
    used_now = set()
    for eq in model.system.eqs:
        used_now |= {n for n, lag in eq.leaves if lag == 0}
    for var in model.system.exogenous:
        if var not in used_now:
            continue
        col = model.data.data[var].to_numpy(dtype=float) if var in model.data.data.columns \
            else np.full(T, np.nan)
        if var in ov:
            col = np.where(np.isfinite(ov[var]), ov[var], col)
        miss = [model._period_label(idx[t]) for t in range(s, e + 1) if not np.isfinite(col[t])]
        if miss:
            out[var] = miss
    return out


def missing_history(model, start, scenario: Scenario = None) -> Dict[str, List[str]]:
    """start 앞의 시차로 쓰이는 내생변수 값(실측 또는 override)이 비어 있는 것 → 기간 라벨 목록.
    동적 풀이는 시작 직전의 내생변수 실측에서 출발하므로, 비어 있으면 첫 기간부터 풀 수 없다."""
    s = model._to_index(start)
    T = len(model.data.data)
    ov = {}
    if scenario is not None:
        ov = {k: model._series_to_array(v, T) for k, v in scenario.exo_overrides.items()}
    need: Dict[str, set] = {}
    endo = set(model.system.endogenous)
    for eq in model.system.eqs:
        for n, lag in eq.leaves:
            if n in endo and lag < 0:
                need.setdefault(n, set()).update(r for r in range(s + lag, s) if r >= 0)
    idx = model.data.data.index
    out = {}
    for var, rows in sorted(need.items()):
        col = model.data.data[var].to_numpy(dtype=float) if var in model.data.data.columns else np.full(T, np.nan)
        if var in ov:
            col = np.where(np.isfinite(ov[var]), ov[var], col)
        miss = [model._period_label(idx[r]) for r in sorted(rows) if not np.isfinite(col[r])]
        if miss:
            out[var] = miss
    return out


# ---------------------------------------------------------------------------
# 확률적 시뮬레이션
# ---------------------------------------------------------------------------
@dataclass
class StochasticResult:
    mean: pd.DataFrame
    std: pd.DataFrame
    percentiles: Dict[float, pd.DataFrame]
    reps: int
    n_failed: int
    draws: Optional[np.ndarray] = None   # (reps, 기간, 변수) — keep_draws=True일 때

    def band(self, var: str) -> pd.DataFrame:
        out = pd.DataFrame({"mean": self.mean[var], "std": self.std[var]})
        for p, df in sorted(self.percentiles.items()):
            out[f"p{p:g}"] = df[var]
        return out


def stochastic_simulation(model, start, end, reps: int = 200, seed: int = None,
                          scenario: Scenario = None, coef_uncertainty: bool = False,
                          percentiles: Sequence[float] = (5, 50, 95), mode: str = "dynamic",
                          keep_draws: bool = False, verbose: bool = True, **kw) -> StochasticResult:
    """확률적 시뮬레이션 — 추정 잔차 벡터 부트스트랩(식 간 상관 보존) + 선택적 계수 추출.

    매 반복마다 기간별로 잔차가 모두 있는 날짜 하나를 뽑아 그 날의 잔차 벡터를 조정항으로 더한다.
    coef_uncertainty=True면 식별 계수를 N(b, Cov)에서 뽑는다(공분산이 있는 식만).
    """
    if isinstance(reps, bool) or not isinstance(reps, (int, np.integer)) or reps < 1:
        raise ValueError(f"reps는 1 이상의 정수입니다(받은 값 {reps!r}) — 몇 번 되풀이해 풀지입니다")
    rng = np.random.default_rng(seed)
    s, e = model._to_index(start), model._to_index(end, end=True)
    T = len(model.data.data)
    sc = scenario or Scenario("stochastic")
    ov, ex, AF0, ctrls = sc.build(model, s, e)
    idx = model.data.data.index
    n_eq = len(model.equations)
    R = np.full((T, n_eq), np.nan)
    for k, eq in enumerate(model.equations):
        if eq.residuals is not None:
            R[:, k] = eq.residuals.reindex(idx).to_numpy(dtype=float)
    full_rows = np.where(np.all(np.isfinite(R), axis=1))[0]
    joint = len(full_rows) >= 10
    col_rows = [np.where(np.isfinite(R[:, k]))[0] for k in range(n_eq)]
    P0 = model.coefficient_vector()
    chol = []
    if coef_uncertainty:
        off = 0
        for eq in model.equations:
            k = len(eq.coef_names)
            cov = getattr(eq, "cov_params", None)
            L = None
            if cov is not None and np.all(np.isfinite(cov)):
                try:
                    L = np.linalg.cholesky(np.asarray(cov) + 1e-18 * np.eye(k))
                except np.linalg.LinAlgError:
                    L = None
            chol.append((off, k, L))
            off += k
    on_fail = kw.pop("on_fail", "nan")
    out_draws = []
    n_failed = 0
    cols = None
    for r in range(reps):
        AF = AF0.copy()
        for t in range(s, e + 1):
            if joint:
                AF[t, :] += R[rng.choice(full_rows), :]
            else:
                for k in range(n_eq):
                    if len(col_rows[k]):
                        AF[t, k] += R[rng.choice(col_rows[k]), k]
        P = P0.copy()
        for off, k, L in chol:
            if L is not None:
                P[off:off + k] = P0[off:off + k] + L @ rng.standard_normal(k)
        sim = model.simulate(s, e, mode=mode, sim_id=f"stoch_{r}", add_factors=AF, overrides=ov,
                             excludes=ex, controls=ctrls, coefficients=P, verbose=False,
                             on_fail=on_fail, **kw)
        if cols is None:
            cols = list(sim.values.columns)
        vals = sim.values[cols].to_numpy(dtype=float)
        if any(st["status"] in ("failed", "fallback") for st in sim.status):
            n_failed += 1
        out_draws.append(vals)
        if verbose and (r + 1) % max(1, reps // 10) == 0:
            _log.info(f"[STOCH] {r + 1}/{reps} 반복")
    D = np.stack(out_draws)                  # reps × H × V
    index = model.data.data.index[s:e + 1]
    with np.errstate(all="ignore"):
        mean = pd.DataFrame(np.nanmean(D, axis=0), index=index, columns=cols)
        std = pd.DataFrame(np.nanstd(D, axis=0), index=index, columns=cols)
        pct = {float(p): pd.DataFrame(np.nanpercentile(D, p, axis=0), index=index, columns=cols)
               for p in percentiles}
    if verbose:
        _log.info(f"[STOCH] 완료: {reps}회 (실패 포함 반복 {n_failed}) — "
              f"잔차 {'공동(식 간 상관 보존)' if joint else '식별 독립'} 부트스트랩"
              f"{', 계수 불확실성 포함' if coef_uncertainty else ''}")
    return StochasticResult(mean, std, pct, reps, n_failed, D if keep_draws else None)


# ---------------------------------------------------------------------------
# 목표추적(control) / 승수
# ---------------------------------------------------------------------------
def control_simulation(model, target: str, instrument: str, path, start, end,
                       scenario: Scenario = None, **kw) -> SimulationResult:
    """target 변수가 path를 따르도록 instrument(외생)를 푼다(EViews Model control).

    path: Series/{시점: 값}/스칼라 — 지정된 기간만 목표를 강제한다.
    반환 values에는 풀린 instrument 경로가 함께 들어 있다.
    """
    sc = (scenario.copy() if scenario is not None else Scenario("control"))
    sc.control(target, instrument, path)
    return sc.run(model, start, end, store=False, **kw).sim


@dataclass
class MultiplierResult:
    shock_var: str
    shock: float
    kind: str
    level: pd.DataFrame       # 충격 − 기준선 (수준)
    pct: pd.DataFrame         # (충격 − 기준선)/기준선 × 100
    baseline: pd.DataFrame
    shocked: pd.DataFrame


def multipliers(model, shock_var: str, shock: float, start, end, kind: str = "level",
                permanent: bool = True, scenario: Scenario = None, variables: Sequence[str] = None,
                **kw) -> MultiplierResult:
    """승수(동태 반응): 같은 조건의 기준선과 충격 시나리오의 차이.

    permanent=True면 start~end 지속 충격, False면 start 한 기간 충격.
    """
    kw.setdefault("verbose", False)
    base_sc = scenario.copy("mult_base") if scenario is not None else Scenario("mult_base")
    shock_sc = base_sc.copy("mult_shock")
    shock_sc.shock(shock_var, shock, start, end if permanent else None, kind)
    b = base_sc.run(model, start, end, store=False, **kw)
    s = shock_sc.run(model, start, end, store=False, **kw)
    lvl = s.diff(b)
    pct = s.pct_diff(b)
    if variables:
        lvl, pct = lvl[list(variables)], pct[list(variables)]
    return MultiplierResult(shock_var, shock, kind, lvl, pct, b.values, s.values)
