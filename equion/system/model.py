#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""연립방정식 모듈 — Model 클래스 (엔진 v3).

구성:
    추정식(Equation)·항등식 → SystemEquation(IR) → ModelSystem(구조 분석·블록 캐시)
    → 블록 컴파일(잔차·해석적 자코비안) → 기간 루프(simulate.run_simulation)

주요 API (EViews Model 대응):
    simulate(start, end, mode='dynamic'|'static'|'fit', ...)   일반 모의(시나리오 입력 포함)
    hs(start, end, hs_id, ...)          Historical Simulation (= 동적 모의, 결과·통계 저장)
    solve(t, solve_id)                  단일 기간 정적 풀이
    block_structure() / show_blocks()   블록 구조 보기
    input_gaps(start, end)              결측 입력 진단 / first_complete_index()
    scenario(...) / forecast / stochastic / control / multipliers → equion.scenario

결과 저장(CSV)은 reporting.results에 위임한다.
"""

import math
import os
import pickle
import warnings
from datetime import datetime
from typing import Dict, List, Optional, Sequence, Union

import numpy as np
import pandas as pd

from ..formula import ir
from ..formula.ast_formula import canonicalize_columns
from ..formula.parser import DSLError, convert_at_functions, normalize, split_equation
from ..version import ENGINE_VERSION  # 저장 형식 호환 표시(공개 버전 아님)
from ..data.dataset import Data
from ..data.periods import locate
from ..estimation.equation import Equation, util_extract_variables, util_convert_ratio_equation  # noqa: F401
from .analyzer import ModelSystem, StructureError, SystemEquation
from .simulate import Control, SimOptions, SimulationError, SimulationResult, run_simulation
from .solver import DEFAULT_FALLBACK
from .._compat import load_pickle, require_pickle_permission
from ..log import engine as _log


class Model:
    """(고급) 연립방정식 모델의 엔진 객체 — 블록 분해·Newton 풀이·과거 재현·시나리오 실행.

    보통은 워크파일의 모델 객체(`wf.model("이름")`)를 쓰고, 엔진 객체는 그 `.engine`으로 얻는다(직접 simulate 등).

    예
        >>> wf = eqn.datasets.load("toy_q")
        >>> m = wf.model("toy").merge("I c Y(-1) R", "CN c Y CN(-1)").append("Y = CN + I + G")
        >>> eng = m.engine
        >>> type(eng).__name__, sorted(eng.get_endogenous_variables())
        ('Model', ['CN', 'I', 'Y'])
    """

    WORKTABLE_FORMAT_VERSION = 1

    def __init__(self, data: Data, equations: List[Equation] = None):
        _log.info("=" * 80)
        _log.info("Model 초기화 시작")
        _log.info("=" * 80)

        self.data = data
        self.equations = list(equations) if equations else []
        self.identities = []

        self.n_equations = len(self.equations)
        self.equation_dict = {}

        self.endogenous_vars = []
        self.exogenous_vars = []
        self.all_vars = set()

        self.current_time_index = None
        self.formulas_for_solver = []
        self.is_prepared = False

        self.solutions = {}
        self.hs_solutions = {}
        self.hs_statistics = {}
        self.solve_status = {}
        self.hs_status = {}
        self.simulations = {}
        self.scenario_results = {}
        self._system = None

        if self.equations:
            self._initialize_system()

        _log.info(f"[OK] Model 초기화 완료: {self.n_equations}개 방정식")
        _log.info("=" * 80)

    # ------------------------------------------------------------------
    # 직렬화: 컴파일된 함수는 저장하지 않는다(복원 시 재컴파일)
    # ------------------------------------------------------------------
    def __getstate__(self):
        state = self.__dict__.copy()
        state["_system"] = None
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)
        for k in ("hs_statistics", "solve_status", "hs_status", "simulations", "scenario_results"):
            if getattr(self, k, None) is None:
                setattr(self, k, {})
        self._system = None

    def _identity_ir(self, idn: dict) -> dict:
        """(레거시 pickle 호환) IR 키가 없는 항등식 dict를 보강한다."""
        if "lhs_ir" not in idn or "target" not in idn:
            ctx = self._ctx()
            idn["lhs_ir"] = ir.build(convert_at_functions(normalize(idn["lhs"])), ctx)
            idn["rhs_ir"] = ir.build(convert_at_functions(normalize(idn["rhs"])), ctx)
            idn["target"] = ir.first_variable(idn["lhs_ir"])
        return idn

    # ------------------------------------------------------------------
    # 변수 분류
    # ------------------------------------------------------------------
    def _initialize_system(self):
        """시스템 초기화 (연립방정식 관점)"""
        _log.info("\n[INIT] 시스템 초기화 중...")
        self._refresh_variables(report=True)
        _log.info(f"  - 내생변수 (좌변): {len(self.endogenous_vars)}개")
        _log.info(f"  - 전체 변수 (좌변+우변): {len(self.all_vars)}개")
        _log.info(f"  - 외생변수 (우변에만): {len(self.exogenous_vars)}개")
        _log.info("[OK] 시스템 초기화 완료")

    def _eq_nodes(self, eq):
        if getattr(eq, "lhs_ir", None) is None:
            eq._parse()
        nodes = [eq.lhs_ir] + list(eq.term_irs)
        if eq.rhs_template is not None:
            nodes.append(eq.rhs_template)
        return nodes

    def _refresh_variables(self, report: bool = False):
        targets, referenced = [], set()
        self.equation_dict = {}
        for eq in self.equations:
            for node in self._eq_nodes(eq):
                referenced |= ir.variables(node)
            targets.append(eq.target)
            self.equation_dict[eq.dependent_var] = eq
        for idn in self.identities:
            self._identity_ir(idn)
            referenced |= ir.variables(idn["lhs_ir"]) | ir.variables(idn["rhs_ir"])
            targets.append(idn["target"])
        dup = sorted({t for t in targets if targets.count(t) > 1})
        if dup and report:
            _log.info(f"  [WARNING] 같은 변수를 결정하는 식이 둘 이상: {dup} "
                  f"(풀이 시 구조 오류 — 목표변수를 조정하세요)")
        self.endogenous_vars = sorted(set(targets))
        self.all_vars = set(self.endogenous_vars) | referenced
        self.exogenous_vars = sorted(referenced - set(self.endogenous_vars))
        self.n_equations = len(self.equations)
        self._system = None

    def _extract_base_variable(self, dependent_var: str) -> str:
        """(하위호환) 종속변수 표기 → 목표(기본) 변수명 (IR의 첫 변수, EViews 규칙)."""
        node = ir.build(normalize(dependent_var), self._ctx())
        return ir.first_variable(node)

    def _freq(self) -> str:
        return getattr(getattr(self, "wt", None), "freq", None) or getattr(self.data, "freq", "Q")

    def _ctx(self) -> ir.BuildContext:
        freq = self._freq()
        return ir.BuildContext(yoy_periods={"Q": 4, "A": 1, "M": 12}.get(freq, 4),
                               disable_qoq=(freq == "A"))

    def add_identity(self, identity_str: str):
        """항등식 추가. 좌변은 식이어도 된다(예: log(X) = ...). 목표변수 = 좌변 첫 변수."""
        s = normalize(identity_str)
        if self.data is not None and self.data.data is not None:
            s = canonicalize_columns(s, self.data.data.columns)
        lhs, rhs = split_equation(s)
        ctx = self._ctx()
        lhs_ir = ir.build(convert_at_functions(lhs), ctx)
        rhs_ir = ir.build(convert_at_functions(rhs), ctx)
        target = ir.first_variable(lhs_ir)
        if target is None:
            raise DSLError(f"항등식 좌변에 변수가 없습니다: {identity_str}")
        self.identities.append({
            "lhs": lhs, "rhs": rhs, "formula": f"{lhs} = {rhs}", "type": "identity",
            "target": target, "lhs_ir": lhs_ir, "rhs_ir": rhs_ir,
        })
        self._refresh_variables()
        _log.info(f"[OK] 항등식 추가: {lhs}")

    def get_endogenous_variables(self) -> List[str]:
        return self.endogenous_vars.copy()

    def get_exogenous_variables(self) -> List[str]:
        return self.exogenous_vars.copy()

    def show_variables(self, show_exogenous: bool = False, max_display: int = 20):
        """변수 정보 출력"""
        _log.info("=" * 70)
        _log.info("변수 정보")
        _log.info("=" * 70)
        _log.info(f"\n[내생변수] {len(self.endogenous_vars)}개:")
        for i, var in enumerate(self.endogenous_vars[:max_display]):
            _log.info(f"  {i+1:2}. {var}")
        if len(self.endogenous_vars) > max_display:
            _log.info(f"  ... (외 {len(self.endogenous_vars) - max_display}개)")

        if show_exogenous:
            _log.info(f"\n[외생변수] {len(self.exogenous_vars)}개:")
            for i, var in enumerate(self.exogenous_vars[:max_display]):
                _log.info(f"  {i+1:2}. {var}")
            if len(self.exogenous_vars) > max_display:
                _log.info(f"  ... (외 {len(self.exogenous_vars) - max_display}개)")
        _log.info("=" * 70)

    def __repr__(self):
        return (f"Model(equations={self.n_equations}, identities={len(self.identities)}, "
                f"endogenous={len(self.endogenous_vars)})")

    # ------------------------------------------------------------------
    # 시스템(IR) 구성
    # ------------------------------------------------------------------
    @property
    def system(self) -> ModelSystem:
        if getattr(self, "_system", None) is None:
            self._system = self._build_system()
        return self._system

    def invalidate(self):
        """식 목록·목표변수를 바꾼 뒤 호출 — 구조·컴파일 캐시를 버린다."""
        self._refresh_variables()

    def _build_system(self) -> ModelSystem:
        if not self.equations and not self.identities:
            raise StructureError("모델에 방정식이 없습니다 — 추정식이나 항등식을 넣으세요")
        eqs, off = [], 0
        for slot, eq in enumerate(self.equations):
            if getattr(eq, "lhs_ir", None) is None:
                eq._parse()
            k = len(eq.coef_names)
            eqs.append(SystemEquation(
                index=len(eqs), kind="behavioral", label=eq.dependent_var, target=eq.target,
                lhs=eq.lhs_ir, rhs=eq.system_rhs(), n_coef=k, coef_offset=off,
                af_slot=slot, source=eq))
            off += k
        for idn in self.identities:
            self._identity_ir(idn)
            eqs.append(SystemEquation(
                index=len(eqs), kind="identity", label=idn["lhs"], target=idn["target"],
                lhs=idn["lhs_ir"], rhs=idn["rhs_ir"], source=idn))
        return ModelSystem(eqs, self.data.data.columns)

    def coefficient_vector(self) -> np.ndarray:
        parts = [eq.coef_vector() for eq in self.equations]
        return np.concatenate(parts) if parts else np.zeros(0)

    # ------------------------------------------------------------------
    # 입력 변환 유틸
    # ------------------------------------------------------------------
    def _to_index(self, p) -> int:
        if p is None:
            raise ValueError("시점이 필요합니다")
        if isinstance(p, (int, np.integer)):
            return int(p)
        wt = getattr(self, "wt", None)
        if wt is not None:
            return wt.index_of(p)
        if isinstance(p, (pd.Timestamp, np.datetime64)):
            return int(self.data.data.index.get_loc(pd.Timestamp(p)))
        return locate(self.data.data.index, p, self.data.freq)    # '2010Q1' 등 — 기간 연산은 periods로

    def _series_to_array(self, spec, T) -> np.ndarray:
        """Series(날짜)/dict(시점→값)/스칼라/배열 → 길이 T 배열(NaN=미지정)."""
        idx = self.data.data.index
        out = np.full(T, np.nan)
        if isinstance(spec, pd.Series):
            s = spec.copy()
            if not isinstance(s.index, pd.DatetimeIndex):
                s.index = [idx[self._to_index(k)] for k in s.index]
            s = s.reindex(idx)
            return s.to_numpy(dtype=float)
        if isinstance(spec, dict):
            for k, v in spec.items():
                if isinstance(k, (pd.Timestamp, np.datetime64)) and pd.Timestamp(k) in idx:
                    out[idx.get_loc(pd.Timestamp(k))] = float(v)
                else:
                    out[self._to_index(k)] = float(v)
            return out
        arr = np.asarray(spec, dtype=float)
        if arr.ndim == 0:
            out[:] = float(arr)
            return out
        if len(arr) != T:
            raise ValueError(f"배열 길이 {len(arr)} ≠ 데이터 길이 {T}")
        return arr

    def _af_matrix(self, add_factors, T) -> np.ndarray:
        """조정항 행렬 [T × 추정식]. True=표본 내 잔차 이월, dict=수동."""
        AF = np.zeros((T, len(self.equations)))
        if add_factors is False or add_factors is None:
            return AF
        if isinstance(add_factors, np.ndarray):
            if add_factors.shape != AF.shape:
                raise ValueError(f"add_factors 배열 크기 {add_factors.shape} ≠ {AF.shape}")
            return np.where(np.isfinite(add_factors), add_factors, 0.0)
        idx = self.data.data.index
        if isinstance(add_factors, dict):
            known = {}
            for eq in self.equations:
                for key in (eq.dependent_var, eq.target):
                    known[key] = known[key.lower()] = True
            bad = [k for k in add_factors if k not in known and str(k).lower() not in known]
            if bad:
                idn = [k for k in bad if str(k).lower() in {i["target"].lower() for i in self.identities}]
                raise ValueError(f"조정항 대상 {bad}에 해당하는 추정식이 없습니다"
                                 + (" — 항등식 변수에는 조정항을 줄 수 없습니다" if idn else
                                    f" (추정식: {', '.join(e.dependent_var for e in self.equations[:8])})"))
            add_factors = {**add_factors, **{str(k).lower(): v for k, v in add_factors.items()}}
        for k, eq in enumerate(self.equations):
            if add_factors is True:
                if eq.residuals is not None:
                    AF[:, k] = eq.residuals.reindex(idx).fillna(0.0).to_numpy(dtype=float)
                continue
            if isinstance(add_factors, dict):
                spec = add_factors.get(eq.dependent_var, add_factors.get(eq.target))
                if spec is None:
                    spec = add_factors.get(eq.dependent_var.lower(), add_factors.get(eq.target.lower()))
                if spec is None:
                    continue
                arr = self._series_to_array(spec, T)
                AF[:, k] = np.where(np.isfinite(arr), arr, 0.0)
                continue
            raise ValueError("add_factors는 False/True/dict/[T×식] 배열이어야 합니다")
        return AF

    def _range_mask(self, spec, T, start, end) -> np.ndarray:
        mask = np.zeros(T, dtype=bool)
        if spec is True or spec is None:
            mask[start:end + 1] = True
        elif isinstance(spec, (tuple, list)) and len(spec) == 2:
            a = self._to_index(spec[0]) if spec[0] is not None else start
            b = self._to_index(spec[1]) if spec[1] is not None else end
            mask[a:b + 1] = True
        else:
            raise ValueError("exclude 구간은 True 또는 (시작, 끝)")
        return mask

    # ------------------------------------------------------------------
    # 일반 모의
    # ------------------------------------------------------------------
    def simulate(self, start, end, mode: str = "dynamic", sim_id: str = None,
                 add_factors=False, overrides: Dict[str, object] = None,
                 excludes=None, controls: Sequence[Control] = (),
                 method: str = "newton", fallback=DEFAULT_FALLBACK,
                 tolerance: float = 1e-10, max_iterations: int = 50,
                 on_missing: str = "exclude", on_fail: str = "actual",
                 mce: bool = False, terminal: str = "actual", mce_damping: float = 1.0,
                 mce_method: str = "fair-taylor", jacobian: str = "auto",
                 initial_guess: Dict[str, float] = None,
                 coefficients: np.ndarray = None,
                 verbose: bool = True) -> SimulationResult:
        """모델을 start..end 구간에서 푼다(결과를 반환만 하고 저장은 하지 않음).

        Args:
            start/end: 정수 위치 또는 '2010Q1' 같은 시점 표기.
            mode: 'dynamic'(시차=모의값) | 'static'(시차=실측) | 'fit'(식별 단독, 다른 내생=실측).
            add_factors: False | True(표본 내 잔차) | {식/목표변수: 경로} | [T×식] 배열.
            overrides: {변수: 경로} — 외생 가정(또는 exclude된 내생의 고정 경로).
            excludes: [변수] 또는 {변수: True|(시작,끝)} — 내생변수를 식 대신 경로로 고정.
            controls: Control(target, instrument, path) 목록 — 목표 추적.
            method/fallback/tolerance/max_iterations: 블록 솔버 설정.
            on_missing: 'exclude'(기본) | 'nan' | 'stop' — 입력 결측 시.
            on_fail: 'actual'(기본) | 'keep' | 'nan' | 'stop' — 블록 미수렴 시.
            mce/terminal: 선행변수(lead) 풀이와 지평 끝 조건. mce_method 'fair-taylor'(기본)|'stacked'(전 기간 동시 Newton).
            jacobian: 'auto'(블록 100변수 이상이면 희소 LU) | 'dense' | 'sparse'.
            coefficients: 전역 계수 벡터 대체(확률 시뮬 등).
        """
        T = len(self.data.data)
        s, e = self._to_index(start), self._to_index(end)
        if s > e:
            raise ValueError(f"시작({s})이 끝({e})보다 뒤입니다")
        system = self.system
        P = self.coefficient_vector() if coefficients is None else np.asarray(coefficients, dtype=float)
        AF = self._af_matrix(add_factors, T)
        ov = {k: self._series_to_array(v, T) for k, v in (overrides or {}).items()}
        ex = {}
        if excludes:
            items = excludes.items() if isinstance(excludes, dict) else [(v, True) for v in excludes]
            ex = {k: self._range_mask(v, T, s, e) for k, v in items}
        opts = SimOptions(mode=mode, method=method, fallback=tuple(fallback or ()),
                          ftol=tolerance, maxiter=max_iterations, on_missing=on_missing,
                          on_fail=on_fail, mce=mce, terminal=terminal, mce_damping=mce_damping,
                          mce_method=mce_method, jacobian=jacobian, verbose=verbose)
        return run_simulation(system, self.data.data, s, e, P, AF, opts,
                              overrides=ov, excludes=ex, controls=controls,
                              sim_id=sim_id or f"sim_{s}_{e}", label=self._period_label,
                              initial=initial_guess)

    # ------------------------------------------------------------------
    # prepare / 구조 보기 / 입력 진단
    # ------------------------------------------------------------------
    def prepare(self, time_index: int, validate: bool = False, tolerance: float = 1e-8) -> dict:
        """특정 시점의 시스템 구조를 만들고 사람이 읽을 수 있는 풀이식 목록을 생성한다.

        (엔진 v3에서는 풀이에 문자열을 쓰지 않는다. formulas_for_solver는 확인용 표시다.)
        """
        t = self._to_index(time_index)
        system = self.system
        df = self.data.data
        P = self.coefficient_vector()
        endo = set(system.endogenous)

        def leaf(v):
            if v.lag == 0 and v.name in endo:
                return v.name
            r = t + v.lag
            val = df[v.name].iloc[r] if (v.name in df.columns and 0 <= r < len(df)) else np.nan
            return repr(float(val)) if v.lag == 0 else f"{float(val)!r}"

        self.formulas_for_solver = []
        for eq in system.eqs:
            rhs = ir.substitute_coefs(eq.rhs, {i: P[eq.coef_offset + i] for i in range(eq.n_coef)})
            self.formulas_for_solver.append(f"{ir.to_str(eq.lhs, leaf)} = {ir.to_str(rhs, leaf)}")
        st = system.structure()
        self.current_time_index = t
        self.is_prepared = True
        return {
            "time_index": t,
            "period": df.index[t],
            "n_formulas": len(self.formulas_for_solver),
            "failed_count": 0,
            "is_prepared": True,
            "blocks": st.describe(system),
        }

    def block_structure(self) -> List[dict]:
        """전체 시스템의 블록 구조(풀이 순서). 동시블록·순차블록 구분."""
        return self.system.structure().describe(self.system)

    def show_blocks(self, max_vars: int = 12):
        blocks = self.block_structure()
        sim = [b for b in blocks if b["size"] > 1]
        _log.info("=" * 80)
        _log.info(f"블록 구조: {len(blocks)}개 블록 (동시블록 {len(sim)}개, "
              f"최대 {max([b['size'] for b in blocks] or [0])}변수)")
        _log.info("=" * 80)
        for b in blocks:
            vs = ", ".join(b["variables"][:max_vars]) + (" …" if b["size"] > max_vars else "")
            _log.info(f"  [{b['block']:>2}] {b['type']:<12} {b['size']:>3}  {vs}")
        _log.info("=" * 80)

    def input_gaps(self, start=None, end=None) -> pd.DataFrame:
        """각 기간·식의 결측 입력(시차값·현시점 외생)을 실측 기준으로 진단한다."""
        system = self.system
        df = self.data.data
        T = len(df)
        s = 0 if start is None else self._to_index(start)
        e = T - 1 if end is None else self._to_index(end)
        endo = set(system.endogenous)
        cols = {n: df[n].to_numpy(dtype=float) for n in system.var_names if n in df.columns}
        rows = []
        for t in range(s, e + 1):
            for eq in system.eqs:
                miss = []
                for nm, lag in sorted(eq.leaves):
                    if lag == 0 and nm in endo:
                        continue
                    r = t + lag
                    v = cols[nm][r] if (nm in cols and 0 <= r < T) else np.nan
                    if not math.isfinite(v):
                        miss.append(nm if lag == 0 else f"{nm}({lag:+d})")
                if miss:
                    rows.append({"period": self._period_label(df.index[t]), "t": t,
                                 "equation": eq.label, "target": eq.target, "missing": ", ".join(miss)})
        return pd.DataFrame(rows, columns=["period", "t", "equation", "target", "missing"])

    def first_complete_index(self, start=None, end=None) -> Optional[int]:
        """start 이후, 그 시점부터 end까지 모든 식의 입력이 갖춰지는 첫 위치(없으면 None)."""
        gaps = self.input_gaps(start, end)
        s = 0 if start is None else self._to_index(start)
        e = len(self.data.data) - 1 if end is None else self._to_index(end)
        if gaps.empty:
            return s
        last_gap = int(gaps["t"].max())
        return last_gap + 1 if last_gap + 1 <= e else None

    # ------------------------------------------------------------------
    # solve (단일 기간 정적 풀이)
    # ------------------------------------------------------------------
    def solve(
        self, time_index: int,
        tolerance: float = 1e-10,
        max_iterations: int = 50,
        initial_guess: dict = None,
        solve_id: str = 'default',
        **kw,
    ) -> dict:
        """특정 시점의 내생변수 해 (정적: 시차는 실측). 결과는 solutions[solve_id][t]."""
        t = self._to_index(time_index)
        _log.info(f"\n{'='*80}")
        _log.info(f"연립방정식 해 계산: {self.data.data.index[t]}")
        _log.info(f"  내생변수: {len(self.endogenous_vars)}개, 방정식: "
              f"{len(self.equations) + len(self.identities)}개")
        _log.info(f"{'='*80}")
        try:
            res = self.simulate(t, t, mode=kw.pop("mode", "static"), sim_id=solve_id,
                                tolerance=tolerance, max_iterations=max_iterations,
                                initial_guess=initial_guess, verbose=False, **kw)
        except (SimulationError, StructureError) as e:
            _log.info(f"[ERROR] solve 실패: {e}")
            return None
        sol = {k: float(v) for k, v in res.values.iloc[0].items()}
        self.solutions.setdefault(solve_id, {})[t] = sol
        st = res.status[0]
        self.solve_status.setdefault(solve_id, {})[t] = st
        if st["status"] in ("ok", "partial"):
            extra = f", 제외 {len(st['excluded'])}식" if st["excluded"] else ""
            _log.info(f"[SUCCESS] 수렴 성공! (최대 정규화잔차: {st['max_resid']:.2e}{extra})")
        else:
            _log.info(f"[WARNING] 수렴 미달: {st['message'][:120]}")
        return sol

    # ========================================================================
    # Historical Simulation
    # ========================================================================
    def _period_label(self, p) -> str:
        """기간 라벨을 워크테이블 주기에 맞춰 포맷한다.

        연(A)→'2003', 분기(Q)→'2003Q1', 월(M)→'2003M3'.
        """
        from ..worktable.freq import format_period
        return format_period(p, self._freq())

    def hs(
        self, start_index: int, end_index: int,
        hs_id: str = 'default', tolerance: float = 1e-10,
        add_factors=False, mode: str = "dynamic", **kw,
    ) -> dict:
        """
        Historical Simulation 실행 (동적 모의). 같은 hs_id의 이전 결과는 **덮어쓴다**.

        Args:
            add_factors: 조정항. False(기본) / True(표본 내 잔차 이월) /
                         dict{종속변수표기 또는 목표변수: Series|{시점: 값}}.
            mode: 'dynamic'(기본) | 'static' | 'fit'.
            kw: simulate()의 나머지 옵션(method, on_missing, on_fail, overrides, ...).
        """
        s, e = self._to_index(start_index), self._to_index(end_index)
        idx = self.data.data.index
        _log.info(f"\n{'='*100}")
        _log.info(f"Historical Simulation 시작")
        _log.info(f"  hs_id: {hs_id}   mode: {mode}")
        _log.info(f"  기간: {self._period_label(idx[s])} ~ {self._period_label(idx[e])}  ({e - s + 1}개)")
        _log.info(f"{'='*100}\n")

        res = self.simulate(s, e, mode=mode, sim_id=hs_id, add_factors=add_factors,
                            tolerance=tolerance, **kw)
        self._store_result(hs_id, res)
        var_statistics = self._calculate_hs_statistics(hs_id, s, e)
        self.hs_statistics[hs_id] = var_statistics

        c = res.counts()
        total = e - s + 1
        success = c["ok"] + c["partial"]
        _log.info(f"\n{'='*100}")
        _log.info(f"HS 완료: 성공 {success}/{total} ({success/total*100:.1f}%) — "
              f"정상 {c['ok']} · 일부식 제외(OK*) {c['partial']} · "
              f"실패대체 {c['fallback']} · 실패 {c['failed']}")
        excl = sorted({x.split(':')[0] for st in res.status for x in st['excluded']})
        if excl:
            _log.info(f"  (입력 결측으로 일부 기간 제외된 식의 목표변수: {', '.join(excl[:10])}"
                  f"{' …' if len(excl) > 10 else ''} — 해당 기간은 통계에서 제외)")
        _log.info(f"{'='*100}")

        return {
            'hs_id': hs_id,
            'n_periods': total,
            'success_count': success,
            'fail_count': c['fallback'] + c['failed'],
            'ok_count': c['ok'], 'partial_count': c['partial'],
            'fallback_count': c['fallback'], 'failed_count': c['failed'],
            'statistics': var_statistics,
        }

    def _store_result(self, hs_id: str, res: SimulationResult):
        T = self.data.data.index
        sols = {}
        for k, t in enumerate(range(res.start, res.end + 1)):
            row = res.values.iloc[k]
            sols[t] = {v: float(row[v]) for v in res.values.columns}
        self.hs_solutions[hs_id] = sols
        self.hs_status[hs_id] = {st["t"]: st for st in res.status}
        self.simulations[hs_id] = res

    def _calculate_hs_statistics(self, hs_id, start_index, end_index) -> dict:
        """HS 결과의 변수별 통계 (실측 대체·제외·실패 기간은 그 변수에서 뺀다)."""
        var_stats = {}
        res = self.simulations.get(hs_id)
        status = self.hs_status.get(hs_id, {})
        df = self.data.data
        sols = self.hs_solutions.get(hs_id, {})
        for var_name in self.endogenous_vars:
            if var_name not in df.columns:
                continue
            errors, abs_errors, n_skip = [], [], 0
            col = df[var_name]
            for time_index in range(start_index, end_index + 1):
                sol = sols.get(time_index)
                if not sol or var_name not in sol:
                    continue
                st = status.get(time_index, {})
                fixed = res.fixed.get(time_index, set()) if res is not None else set()
                if st.get("status") == "failed" or var_name in fixed:
                    n_skip += 1
                    continue
                hs_value = sol[var_name]
                actual_value = col.iloc[time_index]
                if pd.isna(actual_value) or actual_value == 0 or not np.isfinite(hs_value):
                    continue
                errors.append((hs_value - actual_value) / actual_value * 100)
                abs_errors.append(abs(hs_value - actual_value))
            if errors:
                err = np.asarray(errors)
                var_stats[var_name] = {
                    'RMSPE': float(np.sqrt(np.mean(err ** 2))),
                    'MAE_pct': float(np.mean(np.abs(err))),
                    'MAE': float(np.mean(abs_errors)),
                    'RMSE': float(np.sqrt(np.mean(np.square(abs_errors)))),
                    'mean_error': float(np.mean(err)),
                    'std_error': float(np.std(err)),
                    'n_samples': len(errors),
                    'n_excluded': n_skip,
                }
        return var_stats

    def show_hs_summary(self, hs_id: str = None, top_n: int = 20):
        """HS 결과 요약 표시"""
        if not getattr(self, "hs_statistics", None):
            _log.info("[ERROR] HS 통계가 없습니다! 먼저 model.hs()를 실행하세요.")
            return

        hs_ids = [hs_id] if hs_id else list(self.hs_statistics.keys())

        for hid in hs_ids:
            if hid not in self.hs_statistics:
                _log.info(f"[ERROR] hs_id '{hid}' 없음. 사용 가능: {list(self.hs_statistics.keys())}")
                continue

            stats = self.hs_statistics[hid]
            _log.info(f"\n{'='*100}")
            _log.info(f"Historical Simulation 결과: hs_id='{hid}'")
            st = self.hs_status.get(hid, {})
            if st:
                cnt = {}
                for v in st.values():
                    cnt[v["status"]] = cnt.get(v["status"], 0) + 1
                _log.info(f"  기간 상태: {cnt}")
            _log.info(f"{'='*100}")

            sorted_vars = sorted(stats.items(),
                                 key=lambda x: (np.isnan(x[1]['RMSPE']), x[1]['RMSPE']))
            _log.info(f"\n{'순위':>4s} {'변수':20s} {'RMSPE':>10s} {'MAE%':>10s} {'평균오차':>10s} {'N':>5s}")
            _log.info("-" * 66)

            for rank, (var_name, var_stat) in enumerate(sorted_vars[:top_n], 1):
                _log.info(f"{rank:4d} {var_name:20s} {var_stat['RMSPE']:9.3f}% "
                      f"{var_stat['MAE_pct']:9.3f}% {var_stat['mean_error']:+9.3f}% "
                      f"{var_stat.get('n_samples', 0):5d}")

            all_rmspe = np.array([v['RMSPE'] for v in stats.values()], dtype=float)
            n_nan = int(np.isnan(all_rmspe).sum())
            if len(all_rmspe):
                _log.info(f"\n  평균 RMSPE: {np.nanmean(all_rmspe):.3f}%")
                _log.info(f"  중앙값 RMSPE: {np.nanmedian(all_rmspe):.3f}%")
            if n_nan:
                _log.info(f"  (RMSPE 산출 불가 {n_nan}개 변수 제외)")
            _log.info("  ※ 0 근처 계열(잔액·불일치·금리)은 RMSPE가 과대 — MAE(수준) 병행 확인")
            _log.info(f"{'='*100}")

    def compare_and_plot(
        self, variables: list,
        start_index: int = None, end_index: int = None,
        output_file: str = 'comparison_chart.html',
        show_chart: bool = False,
        solve_id: str = None, hs_id: str = None
    ):
        """solve 또는 HS 결과와 실제 데이터 비교 차트 (Plotly)"""
        try:
            import plotly.graph_objects as go
            from plotly.subplots import make_subplots
        except ImportError:
            _log.info("[ERROR] plotly 필요: pip install plotly")
            return

        if solve_id and hs_id:
            _log.info("[ERROR] solve_id와 hs_id 중 하나만 지정하세요!")
            return
        if not solve_id and not hs_id:
            _log.info("[ERROR] solve_id 또는 hs_id를 지정하세요!")
            return

        if solve_id:
            results_dict = self.solutions.get(solve_id, {})
            result_label = f"solve ({solve_id})"
        else:
            results_dict = self.hs_solutions.get(hs_id, {})
            result_label = f"HS ({hs_id})"

        if not results_dict:
            _log.info(f"[ERROR] 결과가 없습니다!")
            return

        solved_indices = sorted(results_dict.keys())
        if start_index is None: start_index = solved_indices[0]
        if end_index is None: end_index = solved_indices[-1]
        indices = [idx for idx in solved_indices if start_index <= idx <= end_index]

        n_vars = len(variables)
        fig = make_subplots(rows=n_vars, cols=1,
                          subplot_titles=[f'{var}: 실제 vs 시뮬레이션' for var in variables],
                          vertical_spacing=0.08)

        for i, var_name in enumerate(variables, 1):
            periods, actual_vals, solved_vals = [], [], []
            for idx in indices:
                p = self.data.data.index[idx]
                periods.append(self._period_label(p))
                actual_vals.append(self.data.data.iloc[idx].get(var_name))
                solved_vals.append(results_dict[idx].get(var_name))

            fig.add_trace(go.Scatter(x=periods, y=actual_vals, name=f'{var_name} (실제)',
                                     mode='lines+markers', line=dict(color='blue', width=2)),
                         row=i, col=1)
            fig.add_trace(go.Scatter(x=periods, y=solved_vals, name=f'{var_name} ({result_label})',
                                     mode='lines+markers', line=dict(color='red', width=2, dash='dot')),
                         row=i, col=1)

        fig.update_layout(title=f'Model 시뮬레이션 vs 실제값', height=400 * n_vars,
                         template='plotly_white')
        fig.write_html(output_file)
        _log.info(f"[OK] 차트 저장: {output_file}")

        if show_chart:
            import webbrowser
            webbrowser.open('file://' + os.path.abspath(output_file))

    def save_solve_results(self, solve_id: str, output_file: str = None, include_all_vars: bool = True):
        """solve 결과를 CSV로 저장 (구현: equion.reporting.results)."""
        from ..reporting.results import save_solve_results as _impl
        return _impl(self, solve_id, output_file, include_all_vars)

    def save_hs_results(self, hs_id: str, output_file: str = None, include_all_vars: bool = True):
        """HS 결과를 CSV로 저장 (구현: equion.reporting.results)."""
        from ..reporting.results import save_hs_results as _impl
        return _impl(self, hs_id, output_file, include_all_vars)

    # ------------------------------------------------------------------
    # 시나리오/전망/확률/목표추적 (구현: equion.scenario)
    # ------------------------------------------------------------------
    def scenario(self, name: str = "baseline"):
        from ..scenario import Scenario
        return Scenario(name)

    def stochastic(self, start, end, **kw):
        from ..scenario import stochastic_simulation
        return stochastic_simulation(self, start, end, **kw)

    def control(self, target: str, instrument: str, path, start, end, **kw):
        from ..scenario import control_simulation
        return control_simulation(self, target, instrument, path, start, end, **kw)

    def multipliers(self, shock_var: str, shock, start, end, **kw):
        from ..scenario import multipliers
        return multipliers(self, shock_var, shock, start, end, **kw)

    # ========================================================================
    # Work Table (EViews workfile 대응) — 레거시 단일 pickle
    # ========================================================================
    def save_worktable(self, path: str) -> str:
        """현재 작업 상태 전체를 단일 pickle로 저장한다(레거시 — 1.0에서 없어짐, 워크파일 .eqw 권장)."""
        warnings.warn("save_worktable(pickle)은 1.0에서 없어집니다 — 워크파일(.eqw)을 쓰세요", DeprecationWarning,
                      stacklevel=2)
        if not os.path.splitext(path)[1]:
            path += '.wt'

        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)

        payload = {
            'format_version': self.WORKTABLE_FORMAT_VERSION,
            'engine_version': ENGINE_VERSION,
            'saved_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'summary': {
                'n_equations': self.n_equations,
                'n_identities': len(self.identities),
                'n_endogenous': len(self.endogenous_vars),
                'solve_ids': sorted(self.solutions.keys()),
                'hs_ids': sorted(self.hs_solutions.keys()),
            },
            'model': self,
        }

        with open(path, 'wb') as f:
            pickle.dump(payload, f, protocol=pickle.HIGHEST_PROTOCOL)

        size_kb = os.path.getsize(path) / 1024
        _log.info(f"[OK] Work Table 저장: {path} ({size_kb:.1f} KB) "
              f"— 추정식 {self.n_equations} · 항등식 {len(self.identities)} · "
              f"HS {len(self.hs_solutions)}건")
        return path

    @staticmethod
    def load_worktable(path: str, allow_pickle: bool = False) -> 'Model':
        """save_worktable로 저장한 Work Table(레거시 pickle)을 복원해 Model을 반환한다.
        pickle은 열 때 코드가 실행될 수 있어 allow_pickle=True일 때만 연다."""
        if not os.path.exists(path):
            raise FileNotFoundError(f"Work Table 파일을 찾을 수 없습니다: {path}")
        require_pickle_permission(path, allow_pickle)

        with open(path, 'rb') as f:
            payload = load_pickle(f)

        if not isinstance(payload, dict) or 'model' not in payload:
            raise ValueError(f"Work Table 형식이 아닙니다: {path}")

        fmt = payload.get('format_version')
        if fmt != Model.WORKTABLE_FORMAT_VERSION:
            warnings.warn(
                f"Work Table 포맷 버전 불일치 (파일 {fmt} ≠ 현재 "
                f"{Model.WORKTABLE_FORMAT_VERSION}). 복원은 시도하지만 호환되지 "
                f"않을 수 있습니다.", stacklevel=2)

        eng = payload.get('engine_version')
        if eng != ENGINE_VERSION:
            warnings.warn(
                f"엔진 버전 불일치 (저장 {eng} ≠ 현재 {ENGINE_VERSION}). "
                f"계수는 그대로 복원되지만 동작이 다를 수 있습니다.", stacklevel=2)

        model = payload['model']
        s = payload.get('summary', {})
        _log.info(f"[OK] Work Table 복원: {path} "
              f"(저장 {payload.get('saved_at', '?')}, 엔진 {eng}) "
              f"— 추정식 {s.get('n_equations', '?')} · "
              f"항등식 {s.get('n_identities', '?')} · "
              f"HS {len(s.get('hs_ids', []))}건")
        return model
