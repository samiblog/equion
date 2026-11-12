#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""기간 루프 시뮬레이터 — 동적/정적/적합(fit) 모의, 결측·실패 정책, 선행변수(MCE) (엔진 v3).

한 기간 t의 처리:
  1. 고정 변수 결정: 외생 + 시나리오 exclude(목표변수 고정) + control 목표(경로 고정)
  2. 결측 입력 검사: 식의 알려진 잎(시차값·현시점 고정값)이 결측이면 on_missing 정책 적용
     ('exclude' → 그 식을 이 기간만 빼고 목표변수를 실측으로 고정 — 연쇄 적용)
  3. 구조(블록) 조회(캐시) → 블록 순서대로 풀이
  4. 블록 실패 시 on_fail 정책: 'actual'(실측 대체·표시) | 'keep'(미수렴 값 유지·표시) | 'nan' | 'stop'
  5. 상태 기록: ok / partial(일부 식 제외) / fallback(실패 블록 대체) / failed(NaN)

실패한 해는 절대 조용히 다음 기간의 시차로 흘러가지 않는다(정책에 따라 실측/NaN으로 대체).

선행변수(MCE): mce_method='fair-taylor'(기본 — 기간 루프를 되풀이) | 'stacked'(모든 기간의 미지수를 한 번에 Newton,
희소 자코비안 — D25). stacked는 Fair-Taylor 첫 회로 기간별 식·미지수 집합과 시작값을 정한 뒤 전 기간을 동시에 푼다.
"""

import math
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Set, Tuple

import numpy as np
import pandas as pd

from .analyzer import Block, ModelSystem, StructureError
from .compiler import compile_equation_full, ensure_compiled
from .solver import DEFAULT_FALLBACK, GROWTH_MAX, JACOBIANS, RCOND_MIN, equilibrated_rcond, solve_block
from ..log import engine as _log

MODES = ("dynamic", "static", "fit")
ON_MISSING = ("exclude", "nan", "stop")
ON_FAIL = ("actual", "keep", "nan", "stop")


class SimulationError(RuntimeError):
    """시뮬레이션 중단(정책 'stop' 또는 구조 오류)."""


@dataclass
class SimOptions:
    mode: str = "dynamic"
    method: str = "newton"
    fallback: Tuple[str, ...] = DEFAULT_FALLBACK
    ftol: float = 1e-10
    maxiter: int = 50
    on_missing: str = "exclude"
    on_fail: str = "actual"
    mce: bool = False
    mce_tol: float = 1e-8
    mce_maxiter: int = 200
    mce_damping: float = 1.0
    terminal: str = "actual"
    mce_method: str = "fair-taylor"
    jacobian: str = "auto"
    verbose: bool = True

    def validate(self):
        if self.mode not in MODES:
            raise ValueError(f"mode는 {MODES} 중 하나")
        if self.on_missing not in ON_MISSING:
            raise ValueError(f"on_missing은 {ON_MISSING} 중 하나")
        if self.on_fail not in ON_FAIL:
            raise ValueError(f"on_fail은 {ON_FAIL} 중 하나")
        if self.terminal not in ("hold", "actual"):
            raise ValueError("terminal은 'hold' 또는 'actual'")
        if self.mce_method not in ("fair-taylor", "stacked"):
            raise ValueError("mce_method는 'fair-taylor' 또는 'stacked'")
        if self.jacobian not in JACOBIANS:
            raise ValueError(f"jacobian은 {JACOBIANS} 중 하나")
        if not (self.ftol > 0):
            raise ValueError(f"tolerance는 0보다 커야 합니다(받은 값 {self.ftol})")
        if int(self.maxiter) < 1:
            raise ValueError(f"max_iterations는 1 이상이어야 합니다(받은 값 {self.maxiter})")
        if not (0 < self.mce_damping <= 1):
            raise ValueError(f"mce_damping은 0보다 크고 1 이하여야 합니다(받은 값 {self.mce_damping}) — "
                             "0이면 기대가 갱신되지 않아 첫 추측이 '수렴'으로 보입니다")
        if not (self.mce_tol > 0) or int(self.mce_maxiter) < 1:
            raise ValueError("mce_tol은 0보다, mce_maxiter는 1 이상이어야 합니다")


@dataclass
class Control:
    """목표 추적: target 변수를 path로 고정하고 instrument(외생)를 미지수로 푼다."""
    target: str
    instrument: str
    path: np.ndarray                 # 길이 T, NaN인 기간은 control 미적용


@dataclass
class SimulationResult:
    sim_id: str
    mode: str
    start: int
    end: int
    index: pd.Index
    values: pd.DataFrame             # 기간 × 내생변수(+control 도구변수)
    status: List[dict]
    fixed: Dict[int, Set[str]]       # 기간 → 실측/경로로 고정돼 '풀리지 않은' 변수
    mce_passes: int = 0
    mce_converged: Optional[bool] = None
    instruments: List[str] = field(default_factory=list)

    def counts(self) -> Dict[str, int]:
        out = {"ok": 0, "partial": 0, "fallback": 0, "failed": 0}
        for s in self.status:
            out[s["status"]] = out.get(s["status"], 0) + 1
        return out

    def status_frame(self) -> pd.DataFrame:
        rows = []
        for s in self.status:
            rows.append({k: (", ".join(v) if isinstance(v, (list, tuple)) else v)
                         for k, v in s.items()})
        return pd.DataFrame(rows).set_index("period") if rows else pd.DataFrame()


def _initial_guess(j, t, S, A):
    for v in (S[t - 1, j] if t > 0 else np.nan, A[t, j]):
        if np.isfinite(v):
            return v
    col = S[:t, j]
    fin = col[np.isfinite(col)]
    return fin[-1] if len(fin) else 1.0


def run_simulation(system: ModelSystem, df: pd.DataFrame, start: int, end: int,
                   P: np.ndarray, AF_base: np.ndarray, opts: SimOptions,
                   overrides: Dict[str, np.ndarray] = None,
                   excludes: Dict[str, np.ndarray] = None,
                   controls: Sequence[Control] = (),
                   sim_id: str = "sim",
                   label: Callable[[pd.Timestamp], str] = str,
                   initial: Dict[str, float] = None) -> SimulationResult:
    """시스템을 start..end(정수 위치) 구간에서 푼다."""
    opts.validate()
    T = len(df)
    if not (0 <= start <= end < T):
        raise SimulationError(f"기간 범위 오류: start={start}, end={end}, 데이터 길이={T}")
    names = system.var_names
    V = len(names)
    pad = system.max_lead if (opts.mce and system.max_lead > 0) else 0
    TT = T + pad

    # ---- 실측(+시나리오 입력) 행렬 A ----
    A = np.full((TT, V), np.nan)
    for j, nm in enumerate(names):
        if nm in df.columns:
            A[:T, j] = df[nm].to_numpy(dtype=float)
    for nm, arr in (overrides or {}).items():
        if nm not in system.var_index:
            raise SimulationError(f"override 변수 '{nm}'는 모델에서 쓰이지 않습니다")
        j = system.var_index[nm]
        arr = np.asarray(arr, dtype=float)
        sel = np.isfinite(arr)
        A[:T, j][sel] = arr[sel]
    S = A.copy()
    L = S if opts.mode == "dynamic" else A
    AF = np.zeros((TT, max(system.n_af, 1)))
    if AF_base is not None and system.n_af:
        AF[:T, :system.n_af] = AF_base

    # ---- 기간별 exclude / control ----
    excl_mask = {}
    for nm, mask in (excludes or {}).items():
        if nm not in system.var_index or system.var_index[nm] not in system.eq_of_var:
            raise SimulationError(f"exclude 대상 '{nm}'는 내생변수가 아닙니다")
        excl_mask[system.var_index[nm]] = np.asarray(mask, dtype=bool)
    ctrl = []
    for c in controls:
        for nm in (c.target, c.instrument):
            if nm not in system.var_index:
                raise SimulationError(f"control 변수 '{nm}'는 모델에서 쓰이지 않습니다")
        jt, ji = system.var_index[c.target], system.var_index[c.instrument]
        if jt not in system.eq_of_var:
            raise SimulationError(f"control 목표 '{c.target}'는 내생변수여야 합니다")
        if ji in system.eq_of_var:
            raise SimulationError(f"control 도구 '{c.instrument}'는 외생변수여야 합니다")
        ctrl.append((jt, ji, np.asarray(c.path, dtype=float)))

    init_idx = {system.var_index[k]: float(v) for k, v in (initial or {}).items()
                if k in system.var_index and v is not None and math.isfinite(float(v))}
    eq_leaves = [[(system.var_index[n], lag, n) for n, lag in sorted(e.leaves)] for e in system.eqs]
    endo = set(system.endo_idx)
    all_eqs = frozenset(range(len(system.eqs)))
    out_vars = list(system.endo_idx) + [ji for _, ji, _ in ctrl if ji not in system.endo_idx]
    R = np.full((T, len(names)), np.nan)          # fit 모드 결과
    fit_blocks: Dict[int, Block] = {}
    active: Dict[int, Tuple[Set[int], Set[int]]] = {}   # 기간 → (풀 식, 미지수) — stacked MCE가 쓴다

    def one_period(t, pass_no):
        fixed_now: Set[int] = set()
        excluded: List[Tuple[str, str]] = []
        E = set(all_eqs)
        U = set(endo)
        for j, mask in excl_mask.items():
            if t < len(mask) and mask[t]:
                E.discard(system.eq_of_var[j])
                U.discard(j)
                fixed_now.add(j)
                S[t, j] = A[t, j]
        for jt, ji, path in ctrl:
            if t < len(path) and np.isfinite(path[t]):
                U.discard(jt)
                U.add(ji)
                S[t, jt] = path[t]
        # 결측 입력 연쇄 검사
        changed = True
        while changed:
            changed = False
            for e in sorted(E):
                miss = None
                for j, lag, nm in eq_leaves[e]:
                    if lag == 0:
                        if opts.mode == "fit":
                            if j == system.var_index[system.eqs[e].target]:
                                continue
                            v = A[t, j]
                        else:
                            if j in U:
                                continue
                            v = S[t, j]
                    else:
                        r = t + lag
                        if r < 0 or r >= TT:
                            miss = f"{nm}({lag:+d}) 범위 밖"
                            break
                        v = L[r, j]
                    if not math.isfinite(v):
                        miss = nm if lag == 0 else f"{nm}({lag:+d})"
                        break
                if miss is None:
                    continue
                eq = system.eqs[e]
                if opts.on_missing == "stop":
                    raise SimulationError(f"{label(df.index[min(t, T - 1)])}: 식 '{eq.label}' 입력 결측 {miss}")
                E.discard(e)
                jt = system.var_index[eq.target]
                if jt in U:
                    U.discard(jt)
                elif opts.mode != "fit":
                    raise SimulationError(
                        f"{label(df.index[t])}: control 목표식 '{eq.label}'이 입력 결측({miss})으로 빠져 풀 수 없습니다")
                fixed_now.add(jt)
                S[t, jt] = A[t, jt] if opts.on_missing == "exclude" else np.nan
                excluded.append((eq.target, miss))
                changed = True

        it_total, maxres, methods, fb, failed_blocks = 0, 0.0, set(), [], []
        if opts.mode == "fit":
            for e in sorted(E):
                jt = system.var_index[system.eqs[e].target]
                blk = fit_blocks.get(e)
                if blk is None:
                    blk = fit_blocks[e] = Block(eqs=[e], vars=[jt])
                cb = ensure_compiled(system, blk)
                x0 = np.array([_initial_guess(jt, t, A, A)])
                res = solve_block(cb, x0, A, A, AF, P, t, opts.method, opts.ftol, opts.maxiter, opts.fallback,
                                  opts.jacobian)
                it_total += res.iterations
                methods.add(res.method)
                if res.converged:
                    R[t, jt] = res.x[0]
                    maxres = max(maxres, res.max_resid)
                else:
                    failed_blocks.append(f"{system.eqs[e].label}: {res.message}")
                    R[t, jt] = A[t, jt] if opts.on_fail == "actual" else (res.x[0] if opts.on_fail == "keep" else np.nan)
                    fb.append(system.eqs[e].target)
                    if opts.on_fail == "stop":
                        raise SimulationError(f"{label(df.index[t])}: {failed_blocks[-1]}")
            for j in fixed_now:
                R[t, j] = A[t, j]
        else:
            active[t] = (set(E), set(U))
            try:
                st = system.structure(frozenset(E), frozenset(U))
            except StructureError as ex:
                hint = ""
                if ctrl:
                    pairs = ", ".join(f"{names[jt]} ← {names[ji]}" for jt, ji, _ in ctrl)
                    hint = (f" — 목표 추적({pairs}): 목표가 같은 기의 도구에 반응해야 풀 수 있습니다"
                            "(도구에서 목표로 가는 같은 기 경로가 없음)")
                raise SimulationError(f"{label(df.index[t])}: {ex}{hint}") from None
            instr = {c[1] for c in ctrl}
            for blk in st.blocks:
                cb = ensure_compiled(system, blk)
                x0 = np.array([init_idx[j] if (t == start and j in init_idx)
                               else (S[t, j] if (j in instr and math.isfinite(S[t, j]))
                                     else _initial_guess(j, t, S, A)) for j in blk.vars])
                res = solve_block(cb, x0, S, L, AF, P, t, opts.method, opts.ftol, opts.maxiter, opts.fallback,
                                  opts.jacobian)
                it_total += res.iterations
                methods.add(res.method)
                if res.converged:
                    S[t, blk.vars] = res.x
                    maxres = max(maxres, res.max_resid)
                    continue
                vars_nm = [names[j] for j in blk.vars]
                failed_blocks.append(f"[{', '.join(vars_nm[:4])}{'…' if len(vars_nm) > 4 else ''}] "
                                     f"{res.message} (시도: {', '.join(res.tried)})")
                if opts.on_fail == "stop":
                    raise SimulationError(f"{label(df.index[t])}: 블록 풀이 실패 {failed_blocks[-1]}")
                if opts.on_fail == "actual":
                    S[t, blk.vars] = A[t, blk.vars]
                elif opts.on_fail == "keep":
                    S[t, blk.vars] = res.x
                else:
                    S[t, blk.vars] = np.nan
                fb.extend(vars_nm)
                fixed_now.update(blk.vars)

        out = R if opts.mode == "fit" else S
        empty = [names[j] for j in system.endo_idx if not math.isfinite(out[t, j])]
        if empty and len(empty) == len(system.endo_idx):
            # 내생변수가 하나도 값을 얻지 못했다(모든 식이 입력 결측으로 빠지고 대체할 실측도 없음) — 풀리지 않은 기간
            failed_blocks.append(f"값 없음: {', '.join(empty[:6])}{' …' if len(empty) > 6 else ''}")
        else:
            empty = []
        if failed_blocks:
            status = "failed" if (opts.on_fail == "nan" or empty) else "fallback"
        elif excluded:
            status = "partial"
        else:
            status = "ok"
        return {
            "t": t, "period": label(df.index[t]), "status": status,
            "iterations": it_total, "max_resid": maxres,
            "methods": sorted(methods), "excluded": [f"{v}:{why}" for v, why in excluded],
            "fallback": fb, "message": " | ".join(failed_blocks),
        }, {names[j] for j in fixed_now}

    def fill_terminal():
        if not pad and not opts.mce:
            return
        # 지평 이후(선행 참조용) 값: actual(있으면) 또는 end 값 유지
        for j in system.endo_idx:
            for r in range(end + 1, TT):
                if opts.terminal == "actual" and math.isfinite(A[r, j]):
                    S[r, j] = A[r, j]
                else:
                    S[r, j] = S[end, j]

    def stacked():
        """모든 기간의 미지수를 한 번에: 행 = (기간, 식), 열 = (기간, 미지수), 희소 자코비안으로 감쇠 Newton."""
        from scipy import sparse as sp
        from scipy.sparse.linalg import splu
        cache = system.__dict__.setdefault("_full_eqs", {})
        cols = [(t, j) for t in range(start, end + 1) for j in sorted(active[t][1])]
        rows = [(t, e) for t in range(start, end + 1) for e in sorted(active[t][0])]
        if len(cols) != len(rows):
            raise SimulationError(f"stacked MCE: 식 {len(rows)}개 ≠ 미지수 {len(cols)}개")
        colmap = {c: k for k, c in enumerate(cols)}
        ceqs = []
        for _, e in rows:
            if e not in cache:
                cache[e] = compile_equation_full(system, e)
            ceqs.append(cache[e])
        ti = np.array([t for t, _ in cols])
        ji = np.array([j for _, j in cols])
        # 지평 뒤 칸 가운데 끝 값을 따라가는 것(terminal='hold', 또는 'actual'인데 실측이 없음 — fill_terminal과 같은 규칙):
        # Newton이 끝 값을 바꿀 때마다 같이 바꾸고, 자코비안에서는 그 칸의 미분을 끝 값의 열에 더한다.
        # (한 번만 채워 두면 끝 다음 값이 첫 추정에 묶여 Fair-Taylor와 다른 해가 나온다.)
        held = {(r_, j) for j in system.endo_idx for r_ in range(end + 1, TT)
                if not (opts.terminal == "actual" and math.isfinite(A[r_, j]))}
        hr = np.array([r_ for r_, _ in sorted(held)], dtype=int)
        hj = np.array([j for _, j in sorted(held)], dtype=int)

        def put(x):
            S[ti, ji] = x
            if hr.size:
                S[hr, hj] = S[end, hj]

        def F(x):
            put(x)
            r = np.array([ce.resid(S, S, AF, P, t) for ce, (t, _) in zip(ceqs, rows)])
            sc = 1.0 + np.array([ce.parts(S, S, AF, P, t) for ce, (t, _) in zip(ceqs, rows)])
            return r, np.where(np.isfinite(sc), sc, 1.0)

        def Jac(x):
            put(x)
            ri, ci, vv = [], [], []
            for k, (ce, (t, _)) in enumerate(zip(ceqs, rows)):
                for j, lag, fn in ce.derivs:
                    c = colmap.get((t + lag, j))
                    if c is None and (t + lag, j) in held:
                        c = colmap.get((end, j))
                    if c is not None:
                        ri.append(k)
                        ci.append(c)
                        vv.append(fn(S, S, AF, P, t))
            return sp.csc_matrix((vv, (ri, ci)), shape=(len(rows), len(cols)))
        x = S[ti, ji].copy()
        r, sc = F(x)
        sc0 = sc.copy()
        nr = float(np.max(np.abs(r) / sc)) if len(r) and np.all(np.isfinite(r)) else np.inf
        it = 0
        with np.errstate(all="ignore"):
            for it in range(1, opts.maxiter + 1):
                if nr < opts.ftol:
                    break
                J = Jac(x)
                if not np.all(np.isfinite(J.data)):
                    break
                D = np.maximum(np.abs(x), 1.0)
                try:
                    dz = splu((J @ sp.diags(D)).tocsc()).solve(-r)
                except RuntimeError:
                    break
                dx = dz * D
                f0 = float(np.sum((r / sc) ** 2))
                lam = 1.0
                while lam >= 1e-8:
                    rn, scn = F(x + lam * dx)
                    if np.all(np.isfinite(rn)) and float(np.sum((rn / sc) ** 2)) <= (1 - 1e-4 * lam) * f0:
                        break
                    lam *= 0.5
                else:
                    put(x)
                    break
                x, r, sc = x + lam * dx, rn, scn
                nr = float(np.max(np.abs(r) / sc))
        put(x)
        ok = nr < opts.ftol
        why = ""
        if ok and len(cols):                      # 수렴으로 보인 해의 확인 — 블록 풀이(solver._verify)와 같은 규칙
            rt = np.array([t for t, _ in rows])
            grow = max((float(np.max(sc[rt == t])) / max(float(np.max(sc0[rt == t])), 1.0)
                        for t in set(rt.tolist())), default=1.0)
            if not np.all(np.isfinite(x)):
                why = "해에 무한·NaN 값이 있습니다"
            elif grow > GROWTH_MAX:
                why = f"해가 없어 값이 끝없이 커집니다(발산 — 식의 크기가 시작값의 {grow:.1e}배)"
            else:
                with np.errstate(all="ignore"):
                    rc = equilibrated_rcond(Jac(x), np.maximum(np.abs(x), 1.0), sc)
                if rc < RCOND_MIN:
                    why = (f"식이 서로 종속이라 해가 하나로 정해지지 않습니다(자코비안 특이 — 크기를 맞춘 역조건수 {rc:.1e})")
            ok = not why
        per = {}
        for (t, _), v in zip(rows, np.abs(r) / sc):
            per[t] = max(per.get(t, 0.0), float(v))
        return ok, it, per, nr, why

    passes = 1
    mce_ok = None
    statuses: List[dict] = []
    fixed: Dict[int, Set[str]] = {}
    if opts.mce and system.max_lead > 0 and opts.mode == "dynamic" and opts.mce_method == "stacked":
        for j in system.endo_idx:                 # 첫 추정: 결측인 미래 내생값은 시작 직전 값으로
            last = S[start - 1, j] if start > 0 else np.nan
            for r_ in range(start, TT):
                if math.isfinite(S[r_, j]):
                    last = S[r_, j]
                else:
                    S[r_, j] = last
        fill_terminal()
        for t in range(start, end + 1):           # 기간별 식·미지수 집합과 시작값(Fair-Taylor 1회)
            st_, fx = one_period(t, 1)
            statuses.append(st_)
            fixed[t] = fx
        mce_ok, passes, per, nr, why = stacked()
        if not mce_ok and opts.on_fail == "stop":
            raise SimulationError(f"MCE(stacked) 미수렴 — {why or f'최대 정규화 잔차 {nr:.2e}'}")
        for st_ in statuses:
            t = st_["t"]
            st_["methods"] = ["stacked"]
            st_["iterations"] = passes
            st_["max_resid"] = per.get(t, 0.0)
            if mce_ok:
                st_["fallback"], st_["message"] = [], ""
                st_["status"] = "partial" if st_["excluded"] else "ok"
            else:
                # 풀리지 않은 해는 쓰지 않는다 — 그 기의 미지수에 실패 정책(on_fail)을 적용하고 상태도 실패로
                unk = sorted(active[t][1])
                if unk and opts.on_fail == "actual":
                    S[t, unk] = A[t, unk]
                elif unk and opts.on_fail == "nan":
                    S[t, unk] = np.nan
                fixed[t] = set(fixed.get(t, set())) | {names[j] for j in unk}
                st_["fallback"] = sorted(set(st_["fallback"]) | {names[j] for j in unk})
                vals = S[t, system.endo_idx]
                st_["status"] = ("failed" if opts.on_fail == "nan" or not np.isfinite(vals).any()
                                 else "fallback")
                st_["message"] = (st_["message"] + " | " if st_["message"] else "") + \
                    f"MCE(stacked) 미수렴 — {why or f'최대 정규화 잔차 {nr:.2e}'}"
        if opts.verbose:
            _log.info(f"[MCE] stacked-time Newton {passes}회 — {'수렴' if mce_ok else '미수렴'}")
    elif opts.mce and system.max_lead > 0 and opts.mode == "dynamic":
        # 첫 추정: 지평 내 결측 내생 미래값을 시작 직전 값으로 채움
        for j in system.endo_idx:
            last = S[start - 1, j] if start > 0 else np.nan
            for r in range(start, TT):
                if math.isfinite(S[r, j]):
                    last = S[r, j]
                else:
                    S[r, j] = last
        prev = None
        for passes in range(1, opts.mce_maxiter + 1):
            fill_terminal()
            statuses, fixed = [], {}
            for t in range(start, end + 1):
                s, fx = one_period(t, passes)
                statuses.append(s)
                fixed[t] = fx
            cur = S[start:end + 1, system.endo_idx].copy()
            if prev is not None:
                if opts.mce_damping != 1.0:
                    cur = opts.mce_damping * cur + (1 - opts.mce_damping) * prev
                    S[start:end + 1, system.endo_idx] = cur
                denom = np.maximum(np.abs(prev), 1e-8)
                with np.errstate(all="ignore"):
                    diff = np.nanmax(np.abs(cur - prev) / denom) if np.isfinite(cur).any() else 0.0
                if not np.isfinite(diff) or diff > 1e12:
                    mce_ok = False
                    if opts.verbose:
                        _log.info("[WARN] MCE(Fair-Taylor) 발산 — mce_damping<1 또는 모형의 안장경로 안정성 확인")
                    break
                if diff < opts.mce_tol:
                    mce_ok = True
                    break
            prev = cur
        else:
            mce_ok = False
            if opts.verbose:
                _log.info(f"[WARN] MCE(Fair-Taylor) {opts.mce_maxiter}회 내 미수렴")
        if not mce_ok:
            for st_ in statuses:
                st_["message"] = (st_["message"] + " | " if st_["message"] else "") + "MCE 미수렴"
        if opts.verbose:
            cnt = {}
            for s in statuses:
                cnt[s["status"]] = cnt.get(s["status"], 0) + 1
            _log.info(f"[MCE] Fair-Taylor {passes}회 반복 — 상태 {cnt}")
    else:
        for k, t in enumerate(range(start, end + 1), 1):
            s, fx = one_period(t, 1)
            statuses.append(s)
            fixed[t] = fx
            if opts.verbose:
                tag = {"ok": "OK", "partial": "OK*", "fallback": "FALLBACK", "failed": "FAIL"}[s["status"]]
                extra = ""
                if s["excluded"]:
                    extra += f" (제외 {len(s['excluded'])}식)"
                if s["fallback"]:
                    extra += f" (대체 {len(s['fallback'])}변수)"
                _log.info(f"[{k}/{end - start + 1}] {s['period']}... {tag}{extra}")

    src = R if opts.mode == "fit" else S
    idx = df.index[start:end + 1]
    cols = [names[j] for j in out_vars]
    values = pd.DataFrame(src[start:end + 1][:, out_vars], index=idx, columns=cols)
    return SimulationResult(sim_id=sim_id, mode=opts.mode, start=start, end=end, index=idx,
                            values=values, status=statuses, fixed=fixed, mce_passes=passes,
                            mce_converged=mce_ok,
                            instruments=[names[ji] for _, ji, _ in ctrl])
