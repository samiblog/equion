#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""블록 컴파일러 — IR을 블록별 잔차·자코비안 파이썬 함수로 한 번만 컴파일 (엔진 v3).

생성 함수의 인자 (모두 numpy 배열, t는 정수 기간 위치):
    x   : 블록 미지수 벡터
    S   : 현시점 상태 행렬 [T × 변수] — 외생·고정·앞 블록에서 이미 푼 값
    L   : 시차/선행 값 행렬 — 동적 모의에선 S(모의값), 정적 모의에선 실측
    AF  : 조정항 행렬 [T × 행동식]
    P   : 전역 계수 벡터

잔차 = 좌변 - 우변 - 조정항. 정의역 위반(log 음수 등)·0으로 나누기는 None(=NaN)으로 돌려
라인서치가 보폭을 줄이게 한다. 자코비안은 IR 기호 미분으로 정확히 계산한다.
생성 코드는 builtins 없이 실행되며, 변수는 이름이 아니라 배열 색인으로만 참조된다.

희소 자코비안(D25): 같은 미분 코드로 0이 아닌 칸의 값만 돌려주는 `_jacd`도 만든다(행·열 위치는 `jac_pattern`).
큰 블록에서 solver가 scipy.sparse로 LU 분해한다.
전체 상태 식(compile_equation_full): 식 하나의 모든 잎을 상태 행렬에서 읽고, 잎(변수·시차/선행)마다 미분 함수를 만든다
— 모든 기간을 한 번에 푸는 stacked-time MCE가 쓴다.
"""

from typing import Callable, Dict, List

import numpy as np

from ..formula import ir
from .analyzer import Block, ModelSystem, SystemEquation


class CompiledBlock:
    def __init__(self, n, resid, jac, eq_resid, eq_deriv, parts, src, jac_data=None, jac_pattern=None):
        self.n = n
        self.jac_data = jac_data    # (x,S,L,AF,P,t) -> 0이 아닌 칸 값(jac_pattern 순서) | None
        self.jac_pattern = jac_pattern or ([], [])   # (행 목록, 열 목록)
        self.resid = resid          # (x,S,L,AF,P,t) -> ndarray | None
        self.jac = jac              # (x,S,L,AF,P,t) -> ndarray(n,n) | None
        self.eq_resid = eq_resid    # [k](x,...) -> float (nan on error)
        self.eq_deriv = eq_deriv    # [k](x,...) -> ∂r_k/∂x_k (가우스-자이델용)
        self.parts = parts          # (x,...) -> (lhs ndarray, rhs ndarray) | None
        self.source = src           # 생성 소스(디버깅용)


def _leaf_code(system: ModelSystem, positions: Dict[int, int]) -> Callable[[ir.Var], str]:
    def leaf(v: ir.Var) -> str:
        j = system.var_index[v.name]
        if v.lag == 0:
            if j in positions:
                return f"x[{positions[j]}]"
            return f"S[t, {j}]"
        return f"L[t{v.lag:+d}, {j}]"
    return leaf


def compile_block(system: ModelSystem, block: Block) -> CompiledBlock:
    positions = {j: k for k, j in enumerate(block.vars)}
    leaf = _leaf_code(system, positions)
    eqs: List[SystemEquation] = [system.eqs[e] for e in block.eqs]

    def coef_code(eq):
        return lambda c: f"P[{eq.coef_offset + c.index}]"

    lhs_codes, rhs_codes, res_codes = [], [], []
    for eq in eqs:
        lc = ir.to_code(eq.lhs, leaf, coef_code(eq))
        rc = ir.to_code(eq.rhs, leaf, coef_code(eq))
        af = f" - AF[t, {eq.af_slot}]" if eq.af_slot is not None else ""
        lhs_codes.append(lc)
        rhs_codes.append(rc)
        res_codes.append(f"({lc}) - ({rc}){af}")

    n = len(eqs)
    lines = ["def _resid(x, S, L, AF, P, t):", "    try:", "        return _arr(("]
    lines += [f"            {c}," for c in res_codes]
    lines += ["        ))", "    except _ERR:", "        return None", ""]

    lines += ["def _parts(x, S, L, AF, P, t):", "    try:",
              "        return _arr((" + ", ".join(lhs_codes) + ",)), _arr((" + ", ".join(rhs_codes) + ",))",
              "    except _ERR:", "        return None", ""]

    # 자코비안(기호 미분)
    lines += ["def _jac(x, S, L, AF, P, t):", f"    J = _zeros(({n}, {n}))", "    try:"]
    entries = []
    for i, eq in enumerate(eqs):
        r = eq.residual
        for j_var in sorted(system.var_index[nm] for nm in eq.current if system.var_index[nm] in positions):
            name = system.var_names[j_var]
            d = ir.deriv(r, ir.Var(name, 0))
            if isinstance(d, ir.Const) and d.value == 0.0:
                continue
            code = ir.to_code(d, leaf, coef_code(eq))
            lines.append(f"        J[{i}, {positions[j_var]}] = {code}")
            entries.append((i, positions[j_var], code))
    lines += ["    except _ERR:", "        return None", "    return J", ""]
    lines += ["def _jacd(x, S, L, AF, P, t):", "    try:",
              "        return _arr((" + "".join(f"{c}, " for _, _, c in entries) + "))",
              "    except _ERR:", "        return None", ""]

    # 식별 잔차·자기 미분(가우스-자이델)
    for i, eq in enumerate(eqs):
        name = system.var_names[block.vars[i]]
        d = ir.deriv(eq.residual, ir.Var(name, 0))
        lines += [f"def _r{i}(x, S, L, AF, P, t):", "    try:",
                  f"        return {res_codes[i]}", "    except _ERR:", "        return nan", "",
                  f"def _d{i}(x, S, L, AF, P, t):", "    try:",
                  f"        return {ir.to_code(d, leaf, coef_code(eq))}", "    except _ERR:",
                  "        return nan", ""]

    src = "\n".join(lines)
    ns = dict(ir.RUNTIME)
    ns.update({"_arr": _float_array, "_zeros": np.zeros, "_ERR": ir.EVAL_ERRORS})
    code = compile(src, f"<block {block.eqs[:3]}>", "exec")
    exec(code, ns)  # noqa: S102 — 생성 소스는 검증된 IR에서만 만들어진다(이름 없음, 색인만)
    return CompiledBlock(
        n=n, resid=ns["_resid"], jac=ns["_jac"],
        eq_resid=[ns[f"_r{i}"] for i in range(n)],
        eq_deriv=[ns[f"_d{i}"] for i in range(n)],
        parts=ns["_parts"], src=src, jac_data=ns["_jacd"],
        jac_pattern=([i for i, _, _ in entries], [j for _, j, _ in entries]))


def _float_array(values):
    return np.array(values, dtype=float)


def ensure_compiled(system: ModelSystem, block: Block) -> CompiledBlock:
    if block.compiled is None:
        block.compiled = compile_block(system, block)
    return block.compiled


class CompiledEquation:
    """식 하나(전체 상태): resid(S, L, AF, P, t)·parts(…)·잎별 미분 [(변수 색인, 시차, 함수)]."""

    def __init__(self, resid, parts, derivs, src):
        self.resid, self.parts, self.derivs, self.source = resid, parts, derivs, src


def compile_equation_full(system: ModelSystem, e: int) -> CompiledEquation:
    """모든 잎을 상태 행렬에서 읽는 식 e — 현시점은 S[t, j], 시차·선행은 L[t±k, j]."""
    eq = system.eqs[e]
    leaf = _leaf_code(system, {})
    cc = (lambda c: f"P[{eq.coef_offset + c.index}]")
    lc, rc = ir.to_code(eq.lhs, leaf, cc), ir.to_code(eq.rhs, leaf, cc)
    af = f" - AF[t, {eq.af_slot}]" if eq.af_slot is not None else ""
    lines = ["def _r(S, L, AF, P, t):", "    try:", f"        return ({lc}) - ({rc}){af}",
             "    except _ERR:", "        return nan", "",
             "def _p(S, L, AF, P, t):", "    try:", f"        return _abs({lc}) + _abs({rc})",
             "    except _ERR:", "        return nan", ""]
    leaves = []
    for k, (name, lag) in enumerate(sorted(eq.leaves)):
        d = ir.deriv(eq.residual, ir.Var(name, lag))
        if isinstance(d, ir.Const) and d.value == 0.0:
            continue
        lines += [f"def _d{k}(S, L, AF, P, t):", "    try:", f"        return {ir.to_code(d, leaf, cc)}",
                  "    except _ERR:", "        return nan", ""]
        leaves.append((system.var_index[name], lag, f"_d{k}"))
    src = "\n".join(lines)
    ns = dict(ir.RUNTIME)
    ns.update({"_ERR": ir.EVAL_ERRORS})
    exec(compile(src, f"<equation {e}>", "exec"), ns)  # noqa: S102 — 검증된 IR에서 만든 코드(색인만)
    return CompiledEquation(ns["_r"], ns["_p"], [(j, lag, ns[fn]) for j, lag, fn in leaves], src)
