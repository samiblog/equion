#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ast_formula.py

AST(Abstract Syntax Tree) 기반의 수식 변환 모듈

기존 equation_model_core.py에서 정규표현식(Regex)으로 처리하던
    사용자 수식 → pandas 수식
    pandas 수식 → solver 수치 수식
변환을 Python 내장 ast 모듈로 완전히 대체합니다.

장점:
  - 괄호 중첩/불균형 문제 완전 해소
  - 새로운 연산자 추가 시 패턴 분기가 불필요
  - 연산자 우선순위가 Python 파서에 의해 자동 보장

작성: 2026-04-18
버전: 2.1.0 (2026-10-29: 입력 허용 목록 검증 추가. 엔진 v3의 풀이 경로는
      parser/ir/system을 쓰며, 이 모듈은 pandas 문자열 변환 유틸·하위호환용이다.)
"""

import ast
import re
import copy
import numpy as np
import pandas as pd
from typing import List, Dict, Optional, Set, Tuple

__version__ = "2.1.0"


# ============================================================================
# 입력 검증 (엔진 v3) — eval 이전에 허용 목록 밖의 구문을 차단한다
# ============================================================================

def _validate_user(expr: str) -> None:
    """사용자 형식 식을 허용 목록으로 검증(parser.validate_expression)."""
    from .parser import validate_expression  # 순환 import 회피(지연 import)
    validate_expression(expr)


_PANDAS_METHODS = frozenset({'shift', 'pct_change', 'diff', 'rolling', 'mean'})
_NP_FUNCS = frozenset({'log', 'exp', 'abs', 'sqrt'})


def _check_pandas_tree(tree: ast.AST, src: str) -> None:
    """pandas 형식 식(df['X'].shift(1) 등) 허용 목록 검증. 위반 시 ValueError."""
    def bad(n, why):
        raise ValueError(f"허용되지 않는 pandas 식 구문({why}): {src[:80]}")

    def chk(n):
        if isinstance(n, ast.Expression):
            return chk(n.body)
        if isinstance(n, ast.Constant):
            if isinstance(n.value, bool) or not isinstance(n.value, (int, float)):
                bad(n, '상수')
            return
        if isinstance(n, ast.BinOp):
            if not isinstance(n.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow)):
                bad(n, '연산자')
            chk(n.left); chk(n.right); return
        if isinstance(n, ast.UnaryOp):
            if not isinstance(n.op, (ast.USub, ast.UAdd)):
                bad(n, '단항')
            chk(n.operand); return
        if isinstance(n, ast.Subscript):
            if not (isinstance(n.value, ast.Name) and n.value.id == 'df'
                    and isinstance(n.slice, ast.Constant) and isinstance(n.slice.value, str)
                    and not n.slice.value.startswith('__')):
                bad(n, "df['이름'] 외 첨자")
            return
        if isinstance(n, ast.Call):
            if n.keywords:
                bad(n, '키워드 인자')
            f = n.func
            if (isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name)
                    and f.value.id == 'np' and f.attr in _NP_FUNCS):
                for a in n.args:
                    chk(a)
                return
            if isinstance(f, ast.Attribute) and f.attr in _PANDAS_METHODS:
                chk(f.value)
                for a in n.args:
                    chk(a)
                return
            bad(n, '호출')
        if isinstance(n, ast.Name):
            if n.id not in ('df', 'np'):
                bad(n, f"이름 {n.id}")
            return
        bad(n, type(n).__name__)
    chk(tree)


# ============================================================================
# 1단계: 사용자 수식 → pandas 표현식  (추정용)
# ============================================================================

class _UserCallTransformer(ast.NodeTransformer):
    """
    사용자 수식의 함수형 속성 호출을 pandas 호출로 변환합니다.

    변환 규칙:
      .t(-N)   → .shift(N)            (시차: 부호 반전)
      .ma(N)   → .rolling(N).mean()   (이동평균)
      .gr(N)   → .pct_change(N) * 100 (N기 증가율 %)
      dlog(X)  → log(X).diff()        (로그차분)
      d(X)     → X.diff()             (1차 차분)

    dlog/d/.gr 는 모두 기존 원시 연산(.diff/.pct_change)으로 환원되므로
    solver 변환기(_PandasToSolverTransformer)를 수정하지 않아도 동작합니다.
    """

    def visit_Call(self, node: ast.Call) -> ast.AST:
        # 자식 먼저 (bottom-up)
        self.generic_visit(node)

        # ---- 함수형 매크로: dlog(X), d(X) ----
        if isinstance(node.func, ast.Name):
            if node.func.id == 'dlog' and len(node.args) == 1:
                # dlog(X) → log(X).diff   (.diff 속성은 _UserAttrTransformer가 처리)
                log_call = ast.Call(
                    func=ast.Name(id='log', ctx=ast.Load()),
                    args=[node.args[0]], keywords=[])
                diff_attr = ast.Attribute(value=log_call, attr='diff', ctx=ast.Load())
                return ast.copy_location(diff_attr, node)
            if node.func.id == 'd' and len(node.args) == 1:
                # d(X) → X.diff
                diff_attr = ast.Attribute(value=node.args[0], attr='diff', ctx=ast.Load())
                return ast.copy_location(diff_attr, node)
            return node

        if not isinstance(node.func, ast.Attribute):
            return node

        attr = node.func.attr

        # ---- .gr(N) → .pct_change(N) * 100 ----
        if attr == 'gr' and len(node.args) == 1:
            call = ast.Call(
                func=ast.Attribute(
                    value=node.func.value, attr='pct_change', ctx=ast.Load()),
                args=node.args, keywords=[])
            mult = ast.BinOp(left=call, op=ast.Mult(),
                             right=ast.Constant(value=100))
            return ast.copy_location(mult, node)

        # ---- .t(-N) → .shift(N) ----
        if attr == 't' and len(node.args) == 1:
            arg = node.args[0]
            # .t(-1) : UnaryOp(USub, 1)  →  shift(1)
            if isinstance(arg, ast.UnaryOp) and isinstance(arg.op, ast.USub):
                shift_val = arg.operand
            # .t(2) 같은 양수 → shift(-2)
            elif isinstance(arg, ast.Constant):
                shift_val = ast.Constant(value=-arg.value)
            else:
                shift_val = arg

            new = ast.Call(
                func=ast.Attribute(
                    value=node.func.value, attr='shift', ctx=ast.Load()),
                args=[shift_val],
                keywords=[],
            )
            return ast.copy_location(new, node)

        # ---- .ma(N) → .rolling(N).mean() ----
        if attr == 'ma':
            rolling = ast.Call(
                func=ast.Attribute(
                    value=node.func.value, attr='rolling', ctx=ast.Load()),
                args=node.args,
                keywords=[],
            )
            mean = ast.Call(
                func=ast.Attribute(
                    value=rolling, attr='mean', ctx=ast.Load()),
                args=[],
                keywords=[],
            )
            return ast.copy_location(mean, node)

        return node


class _UserAttrTransformer(ast.NodeTransformer):
    """
    단순 속성(.qoq, .yoy, .diff)을 pandas 호출로 변환합니다.

    변환 규칙:
      .qoq   → .pct_change() * 100      (disable_qoq=True면 사용 금지)
      .yoy   → .pct_change(N) * 100      (N=yoy_periods; 연간1·분기4·월12)
      .diff  → .diff()

    yoy_periods/disable_qoq는 WorkTable 주기에 따라 호출부에서 주입한다.
    기본값(4, False)은 분기 동작(하위호환).
    """

    def __init__(self, yoy_periods: int = 4, disable_qoq: bool = False):
        super().__init__()
        self.yoy_periods = yoy_periods
        self.disable_qoq = disable_qoq

    def visit_Attribute(self, node: ast.Attribute) -> ast.AST:
        self.generic_visit(node)
        attr = node.attr

        if attr == 'qoq':
            if self.disable_qoq:
                raise ValueError(
                    "이 주기(연간)에서는 .qoq를 사용할 수 없습니다. "
                    "전년대비는 .yoy를 사용하세요.")
            call = ast.Call(
                func=ast.Attribute(
                    value=node.value, attr='pct_change', ctx=ast.Load()),
                args=[], keywords=[])
            mult = ast.BinOp(left=call, op=ast.Mult(),
                             right=ast.Constant(value=100))
            return ast.copy_location(mult, node)

        if attr == 'yoy':
            call = ast.Call(
                func=ast.Attribute(
                    value=node.value, attr='pct_change', ctx=ast.Load()),
                args=[ast.Constant(value=self.yoy_periods)], keywords=[])
            mult = ast.BinOp(left=call, op=ast.Mult(),
                             right=ast.Constant(value=100))
            return ast.copy_location(mult, node)

        if attr == 'diff':
            call = ast.Call(
                func=ast.Attribute(
                    value=node.value, attr='diff', ctx=ast.Load()),
                args=[], keywords=[])
            return ast.copy_location(call, node)

        return node


class _NameToPandasTransformer(ast.NodeTransformer):
    """
    변수명을 df["VAR"] 형태로 변환하고, 함수명(log, exp)은 np. 접두어를 붙입니다.

    수집된 변수명은 self.variables 에 저장됩니다.
    """

    # 변환하지 말아야 할 예약어
    _RESERVED = frozenset({'np', 'df', 'pd', 'log', 'exp', 'abs', 'sqrt'})

    def __init__(self):
        super().__init__()
        self.variables: Set[str] = set()

    def visit_Name(self, node: ast.Name) -> ast.AST:
        if node.id in self._RESERVED:
            return node

        self.variables.add(node.id)
        new = ast.Subscript(
            value=ast.Name(id='df', ctx=ast.Load()),
            slice=ast.Constant(value=node.id),
            ctx=node.ctx,
        )
        return ast.copy_location(new, node)

    def visit_Call(self, node: ast.Call) -> ast.AST:
        self.generic_visit(node)
        if isinstance(node.func, ast.Name) and node.func.id in ('log', 'exp', 'abs', 'sqrt'):
            node.func = ast.Attribute(
                value=ast.Name(id='np', ctx=ast.Load()),
                attr=node.func.id,
                ctx=ast.Load(),
            )
        return node


def user_to_pandas(expr: str, yoy_periods: int = 4,
                   disable_qoq: bool = False) -> str:
    """
    사용자 친화적 수식 하나를 pandas 표현식 문자열로 변환합니다.

    Args:
        expr: 사용자 수식 (예: "log(RCPSA.t(-1))", "WAGE.qoq", "(CPI/KRW).ma(2)")
        yoy_periods: .yoy의 pct_change 시차(연간1·분기4·월12). 기본 4(분기).
        disable_qoq: True면 .qoq 사용 시 에러(연간 — 전년대비는 .yoy 사용).

    Returns:
        str: pandas 수식 (예: "np.log(df['RCPSA'].shift(1))")

    Examples:
        >>> user_to_pandas("WAGE.qoq")
        "df['WAGE'].pct_change() * 100"

        >>> user_to_pandas("WAGE.yoy", yoy_periods=1)
        "df['WAGE'].pct_change(1) * 100"
    """
    _validate_user(expr)
    tree = ast.parse(expr, mode='eval')
    tree = _UserCallTransformer().visit(tree)
    tree = _UserAttrTransformer(yoy_periods, disable_qoq).visit(tree)
    tree = _NameToPandasTransformer().visit(tree)
    ast.fix_missing_locations(tree)
    return ast.unparse(tree)


def extract_variables(expr: str) -> Set[str]:
    """
    수식에서 참조되는 변수명 집합을 반환합니다.

    Args:
        expr: 사용자 수식

    Returns:
        Set[str]: 변수명 집합
    """
    _validate_user(expr)
    tree = ast.parse(expr, mode='eval')
    tree = _UserCallTransformer().visit(tree)
    tree = _UserAttrTransformer().visit(tree)
    namer = _NameToPandasTransformer()
    namer.visit(tree)
    return namer.variables


# ============================================================================
# 2단계: 사용자 수식 → solver 수치 수식  (scipy.fsolve 용)
# ============================================================================

class _SolverCallTransformer(ast.NodeTransformer):
    """
    solver용: .t(-N), .ma(N) 을 실제 수치로 미리 계산합니다.

    내생변수의 현 시점(t=0)은 기호로 남기고,
    과거 시점(.t(-N))이나 외생변수는 데이터에서 값을 꺼내 상수로 치환합니다.
    """

    def __init__(self, data_df: pd.DataFrame, time_index: int,
                 endogenous_vars: List[str],
                 hs_solutions: dict = None, hs_id: str = None):
        super().__init__()
        self.df = data_df
        self.ti = time_index
        self.endogenous = set(endogenous_vars)
        self.hs_solutions = hs_solutions
        self.hs_id = hs_id

    def _get_value(self, var_name: str, offset: int = 0):
        """데이터에서 값을 가져오는 헬퍼. HS 과거 결과 우선 조회."""
        idx = self.ti + offset  # offset은 이미 양수(과거)
        # Historical Simulation: 이전 시점의 내생변수 → HS 결과에서 조회
        if self.hs_solutions and self.hs_id and var_name in self.endogenous and offset != 0:
            if idx in self.hs_solutions.get(self.hs_id, {}):
                sol = self.hs_solutions[self.hs_id][idx]
                if var_name in sol:
                    return float(sol[var_name])
        # 일반 데이터에서 조회
        if 0 <= idx < len(self.df):
            val = self.df.iloc[idx][var_name] if var_name in self.df.columns else np.nan
            return float(val)
        return np.nan

    def visit_Call(self, node: ast.Call) -> ast.AST:
        self.generic_visit(node)

        if not isinstance(node.func, ast.Attribute):
            return node

        attr = node.func.attr

        # ---- .t(-N) ----
        if attr == 't' and len(node.args) == 1:
            var_node = node.func.value
            arg = node.args[0]

            # shift 값 결정
            if isinstance(arg, ast.UnaryOp) and isinstance(arg.op, ast.USub):
                shift = arg.operand.value  # 양수
            elif isinstance(arg, ast.Constant):
                shift = -arg.value
            else:
                return node

            # 변수 이름 추출
            var_name = self._extract_var_name(var_node)
            if var_name:
                val = self._get_value(var_name, -shift)
                if not np.isnan(val):
                    return ast.Constant(value=val)
            return node

        # ---- .ma(N) ----
        if attr == 'ma' and len(node.args) == 1:
            var_node = node.func.value
            var_name = self._extract_var_name(var_node)
            window = node.args[0].value if isinstance(node.args[0], ast.Constant) else None

            if var_name and window:
                vals = [self._get_value(var_name, -i) for i in range(window)]
                if all(not np.isnan(v) for v in vals):
                    return ast.Constant(value=float(np.mean(vals)))
            return node

        return node

    @staticmethod
    def _extract_var_name(node: ast.AST) -> Optional[str]:
        """AST 노드에서 단순 변수명을 추출합니다."""
        if isinstance(node, ast.Name):
            return node.id
        return None


class _SolverAttrTransformer(ast.NodeTransformer):
    """
    solver용: .qoq, .yoy, .diff 를 실제 수치로 미리 계산합니다.
    """

    def __init__(self, data_df: pd.DataFrame, time_index: int,
                 endogenous_vars: List[str],
                 hs_solutions: dict = None, hs_id: str = None):
        super().__init__()
        self.df = data_df
        self.ti = time_index
        self.endogenous = set(endogenous_vars)
        self.hs_solutions = hs_solutions
        self.hs_id = hs_id

    def _get_val(self, var_name, offset=0):
        idx = self.ti + offset
        if self.hs_solutions and self.hs_id and var_name in self.endogenous and offset != 0:
            if idx in self.hs_solutions.get(self.hs_id, {}):
                sol = self.hs_solutions[self.hs_id][idx]
                if var_name in sol:
                    return float(sol[var_name])
        if 0 <= idx < len(self.df) and var_name in self.df.columns:
            return float(self.df.iloc[idx][var_name])
        return np.nan

    def visit_Attribute(self, node: ast.Attribute) -> ast.AST:
        self.generic_visit(node)
        attr = node.attr
        var_name = self._extract_var(node.value)

        if var_name is None:
            return node

        # 현 시점 내생변수인 경우 → 기호 유지 (solver가 풀어야 할 대상)
        # 하지만 .qoq, .yoy는 과거값이 필요하므로 계산 가능
        if attr == 'qoq':
            v_now = self._get_val(var_name, 0) if var_name not in self.endogenous else None
            v_prev = self._get_val(var_name, -1)
            if v_now is not None and not np.isnan(v_now) and not np.isnan(v_prev) and v_prev != 0:
                return ast.Constant(value=(v_now / v_prev - 1) * 100)
            # 내생변수의 현시점 qoq → 기호로 유지
            return node

        if attr == 'yoy':
            v_now = self._get_val(var_name, 0) if var_name not in self.endogenous else None
            v_prev = self._get_val(var_name, -4)
            if v_now is not None and not np.isnan(v_now) and not np.isnan(v_prev) and v_prev != 0:
                return ast.Constant(value=(v_now / v_prev - 1) * 100)
            return node

        if attr == 'diff':
            v_now = self._get_val(var_name, 0) if var_name not in self.endogenous else None
            v_prev = self._get_val(var_name, -1)
            if v_now is not None and not np.isnan(v_now) and not np.isnan(v_prev):
                return ast.Constant(value=v_now - v_prev)
            return node

        return node

    @staticmethod
    def _extract_var(node):
        if isinstance(node, ast.Name):
            return node.id
        return None


class _SolverNameTransformer(ast.NodeTransformer):
    """
    solver용: 외생변수를 현 시점 수치 상수로 치환합니다.
    내생변수(현 시점)는 변수명을 그대로 유지합니다.
    """

    _RESERVED = frozenset({'np', 'df', 'pd', 'log', 'exp', 'abs', 'sqrt'})

    def __init__(self, data_df: pd.DataFrame, time_index: int,
                 endogenous_vars: List[str]):
        super().__init__()
        self.df = data_df
        self.ti = time_index
        self.endogenous = set(endogenous_vars)

    def visit_Name(self, node: ast.Name) -> ast.AST:
        if node.id in self._RESERVED:
            return node

        # 내생변수 → 기호 유지
        if node.id in self.endogenous:
            return node

        # 외생변수 → 수치 치환
        if node.id in self.df.columns and 0 <= self.ti < len(self.df):
            val = float(self.df.iloc[self.ti][node.id])
            if not np.isnan(val):
                return ast.Constant(value=val)

        return node

    def visit_Call(self, node: ast.Call) -> ast.AST:
        self.generic_visit(node)
        if isinstance(node.func, ast.Name) and node.func.id in ('log', 'exp', 'abs', 'sqrt'):
            node.func = ast.Attribute(
                value=ast.Name(id='np', ctx=ast.Load()),
                attr=node.func.id,
                ctx=ast.Load(),
            )
        return node


def user_to_solver(
    expr: str,
    data_df: pd.DataFrame,
    time_index: int,
    endogenous_vars: List[str],
    hs_solutions: dict = None,
    hs_id: str = None,
) -> str:
    """
    사용자 수식을 solver(scipy.fsolve)용 수치 수식으로 변환합니다.

    내생변수(현 시점)는 기호로 남기고,
    외생변수와 과거 시점 값은 실제 수치로 치환합니다.

    Args:
        expr: 사용자 수식
        data_df: 데이터 DataFrame
        time_index: 현재 시점 인덱스
        endogenous_vars: 내생변수 목록
        hs_solutions: Historical Simulation 이전 결과 (선택)
        hs_id: HS 구분자 (선택)

    Returns:
        str: solver에 넣을 수 있는 수치 수식 문자열
    """
    _validate_user(expr)
    tree = ast.parse(expr, mode='eval')

    # 1) .t(), .ma() 함수형 호출 → 수치 치환
    tree = _SolverCallTransformer(
        data_df, time_index, endogenous_vars, hs_solutions, hs_id
    ).visit(tree)

    # 2) .qoq, .yoy, .diff 속성 → 수치 치환
    tree = _SolverAttrTransformer(
        data_df, time_index, endogenous_vars, hs_solutions, hs_id
    ).visit(tree)

    # 3) 변수명 치환(외생→수치, 내생→유지) + 함수명 변환(log→np.log)
    tree = _SolverNameTransformer(
        data_df, time_index, endogenous_vars
    ).visit(tree)

    ast.fix_missing_locations(tree)
    return ast.unparse(tree)


# ============================================================================
# 3단계: pandas_formula (계수 포함) → solver 수식
# ============================================================================

def pandas_formula_to_solver(
    pandas_formula: str,
    data_df: pd.DataFrame,
    time_index: int,
    endogenous_vars: List[str],
    hs_solutions: dict = None,
    hs_id: str = None,
) -> str:
    """
    Equation.pandas_formula (계수가 포함된 추정 결과 수식)를
    solver용 수치 수식으로 변환합니다.

    pandas_formula 형식:
      "np.log(df['RCPSA']) = 0.123 + 0.456 * (np.log(df['RCPSA'].shift(1))) + ..."

    결과:
      "np.log(RCPSA) = 0.123 + 0.456 * np.log(12345.6) + ..."

    Args:
        pandas_formula: 계수 포함 pandas 공식 문자열
        data_df: 데이터 DataFrame
        time_index: 현재 시점 인덱스
        endogenous_vars: 내생변수 목록
        hs_solutions: HS 이전 결과 (선택)
        hs_id: HS 구분자 (선택)

    Returns:
        str: solver용 수치 수식 (LHS = RHS)
    """
    if ' = ' not in pandas_formula:
        raise ValueError(f"pandas_formula에 ' = '가 없습니다: {pandas_formula[:80]}")

    lhs_raw, rhs_raw = pandas_formula.split(' = ', 1)

    # ---- LHS 변환 ----
    lhs_tree = ast.parse(lhs_raw.strip(), mode='eval')
    _check_pandas_tree(lhs_tree, lhs_raw)
    lhs_tree = _PandasToSolverTransformer(
        data_df, time_index, endogenous_vars, hs_solutions, hs_id
    ).visit(lhs_tree)
    ast.fix_missing_locations(lhs_tree)
    lhs_out = ast.unparse(lhs_tree)

    # ---- RHS 변환 ----
    rhs_tree = ast.parse(rhs_raw.strip(), mode='eval')
    _check_pandas_tree(rhs_tree, rhs_raw)
    rhs_tree = _PandasToSolverTransformer(
        data_df, time_index, endogenous_vars, hs_solutions, hs_id
    ).visit(rhs_tree)
    ast.fix_missing_locations(rhs_tree)
    rhs_out = ast.unparse(rhs_tree)

    return f"{lhs_out} = {rhs_out}"


class _PandasToSolverTransformer(ast.NodeTransformer):
    """
    pandas 스타일 수식(df['VAR'].shift(1) 등)을 solver 수치 수식으로 변환합니다.

    핵심 원칙:
      - df['VAR'] (내생, 현 시점)            → 변수명 기호 (solver가 풀 미지수)
      - df['VAR'] (외생, 현 시점)            → 현 시점 수치 상수
      - 시계열 연산(.shift/.pct_change/.diff/.rolling().mean())
          · 순수 과거항(.shift) → 내부식을 데이터에서 수치 평가한 상수
          · 현 시점이 섞인 변화율/평균(.pct_change/.diff/.rolling.mean)
            → 현 시점항은 기호로 두고, 과거항만 수치로 평가하여 결합

    이를 위해 '내부식(inner)'은 변환 전 pandas 형태를 그대로 데이터프레임에서
    평가(eval)하여 임의 시점의 수치값을 구합니다. 따라서 (A-B).qoq, (A/B).ma(2),
    중첩식 등 복합 표현도 누출 없이 처리됩니다.

    Historical Simulation 시에는 과거 내생변수 값이 필요하므로, 데이터프레임에
    이전 분기 HS 해를 덮어쓴 사본(df_eval)을 만들어 과거항 평가에 사용합니다.
    """

    _RESERVED = frozenset({'np', 'df', 'pd', 'log', 'exp', 'abs', 'sqrt'})

    def __init__(self, data_df, time_index, endogenous_vars,
                 hs_solutions=None, hs_id=None, df_eval=None):
        super().__init__()
        self.df = data_df
        self.ti = time_index
        self.endogenous = set(endogenous_vars)
        self.hs = hs_solutions
        self.hs_id = hs_id
        # 과거항 수치 평가용 데이터프레임 (HS 해 병합본). 재귀 호출 시 재사용.
        self.df_eval = df_eval if df_eval is not None else self._build_df_eval()

    def _build_df_eval(self) -> pd.DataFrame:
        """이전 분기 HS 해를 덮어쓴 데이터프레임 사본을 만든다(HS 미사용 시 원본)."""
        if not (self.hs and self.hs_id and self.hs_id in self.hs):
            return self.df
        df2 = self.df.copy()
        for idx, sol in self.hs[self.hs_id].items():
            if 0 <= idx < len(df2):
                for var, val in sol.items():
                    if var in df2.columns:
                        df2.iat[idx, df2.columns.get_loc(var)] = val
        return df2

    # ---- 헬퍼 ----
    @staticmethod
    def _const_int(node) -> Optional[int]:
        """상수 정수 인자 추출 (-1 등 UnaryOp 포함)."""
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return int(node.value)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            inner = node.operand
            if isinstance(inner, ast.Constant):
                return -int(inner.value)
        return None

    def _expr_has_endo(self, node) -> bool:
        """pandas 부분식이 현 시점 내생변수 df['VAR']를 참조하는지 검사."""
        for n in ast.walk(node):
            if (isinstance(n, ast.Subscript) and isinstance(n.value, ast.Name)
                    and n.value.id == 'df' and isinstance(n.slice, ast.Constant)
                    and n.slice.value in self.endogenous):
                return True
        return False

    def _value_at(self, inner_node, offset: int) -> float:
        """변환 전 pandas 내부식을 df_eval에서 평가해 ti+offset 시점의 수치값을 반환."""
        try:
            expr = ast.unparse(inner_node)
            series = eval(expr, {'df': self.df_eval, 'np': np, 'pd': pd})
            idx = self.ti + offset
            if isinstance(series, pd.Series):
                if 0 <= idx < len(series):
                    return float(series.iloc[idx])
                return np.nan
            return float(series)
        except Exception:
            return np.nan

    def _solver_now(self, inner_node) -> ast.AST:
        """내부식의 현 시점 solver 표현(내생=기호, 외생=수치)으로 재귀 변환."""
        sub = _PandasToSolverTransformer(
            self.df, self.ti, self.endogenous,
            self.hs, self.hs_id, df_eval=self.df_eval,
        )
        return sub.visit(copy.deepcopy(inner_node))

    # ---- df['VAR'] 패턴 ----
    def visit_Subscript(self, node: ast.Subscript) -> ast.AST:
        if (isinstance(node.value, ast.Name) and node.value.id == 'df'
                and isinstance(node.slice, ast.Constant)
                and isinstance(node.slice.value, str)):
            var_name = node.slice.value
            # 내생변수(현 시점) → 기호 유지
            if var_name in self.endogenous:
                return ast.copy_location(ast.Name(id=var_name, ctx=ast.Load()), node)
            # 외생변수(현 시점) → 수치 치환
            val = self._value_at(node, 0)
            if not np.isnan(val):
                return ast.copy_location(ast.Constant(value=val), node)
            return ast.copy_location(ast.Name(id=var_name, ctx=ast.Load()), node)

        self.generic_visit(node)
        return node

    # ---- 시계열 메서드 ----
    def visit_Call(self, node: ast.Call) -> ast.AST:
        if isinstance(node.func, ast.Attribute):
            attr = node.func.attr
            inner = node.func.value

            # .shift(N): 순수 과거항 → 수치 상수
            if attr == 'shift' and len(node.args) == 1:
                k = self._const_int(node.args[0])
                if k is not None:
                    val = self._value_at(inner, -k)
                    if not np.isnan(val):
                        return ast.copy_location(ast.Constant(value=val), node)
                self.generic_visit(node)
                return node

            # .pct_change(N) → (현시점 / 과거값 - 1)
            if attr == 'pct_change':
                n = 1
                if node.args:
                    n = self._const_int(node.args[0]) or 1
                return self._build_change(node, inner, n, kind='pct')

            # .diff() → (현시점 - 과거값)
            if attr == 'diff' and len(node.args) == 0:
                return self._build_change(node, inner, 1, kind='diff')

            # .rolling(W).mean()
            if attr == 'mean' and len(node.args) == 0:
                rn = inner
                if (isinstance(rn, ast.Call) and isinstance(rn.func, ast.Attribute)
                        and rn.func.attr == 'rolling' and len(rn.args) == 1):
                    w = self._const_int(rn.args[0])
                    if w:
                        return self._build_rolling_mean(node, rn.func.value, w)

        self.generic_visit(node)
        return node

    def _build_change(self, node, inner, n, kind):
        """pct_change/diff 변환. 현시점 내생 포함 시 기호 결합, 아니면 상수."""
        lag = self._value_at(inner, -n)
        if not self._expr_has_endo(inner):
            now = self._value_at(inner, 0)
            if not np.isnan(now) and not np.isnan(lag):
                if kind == 'pct' and lag != 0:
                    return ast.copy_location(ast.Constant(value=(now / lag - 1)), node)
                if kind == 'diff':
                    return ast.copy_location(ast.Constant(value=(now - lag)), node)
            self.generic_visit(node)
            return node

        if np.isnan(lag) or (kind == 'pct' and lag == 0):
            self.generic_visit(node)
            return node

        now_node = self._solver_now(inner)
        if kind == 'pct':
            # now / lag - 1
            expr = ast.BinOp(
                left=ast.BinOp(left=now_node, op=ast.Div(),
                               right=ast.Constant(value=float(lag))),
                op=ast.Sub(), right=ast.Constant(value=1))
        else:
            expr = ast.BinOp(left=now_node, op=ast.Sub(),
                             right=ast.Constant(value=float(lag)))
        return ast.copy_location(expr, node)

    def _build_rolling_mean(self, node, base, w):
        """rolling(w).mean() 변환. 현시점항은 기호, 과거 w-1개 항은 수치 평균."""
        if not self._expr_has_endo(base):
            vals = [self._value_at(base, -i) for i in range(w)]
            if all(not np.isnan(v) for v in vals):
                return ast.copy_location(ast.Constant(value=float(np.mean(vals))), node)
            self.generic_visit(node)
            return node

        lag_vals = [self._value_at(base, -i) for i in range(1, w)]
        if any(np.isnan(v) for v in lag_vals):
            self.generic_visit(node)
            return node

        total = self._solver_now(base)
        for v in lag_vals:
            total = ast.BinOp(left=total, op=ast.Add(),
                              right=ast.Constant(value=float(v)))
        expr = ast.BinOp(left=total, op=ast.Div(),
                         right=ast.Constant(value=float(w)))
        return ast.copy_location(expr, node)


# ============================================================================
# 유틸리티 함수
# ============================================================================

def validate_user_expression(expr: str) -> Tuple[bool, str]:
    """
    사용자 수식이 유효한 DSL 식인지 검증합니다(문법 + 허용 목록).

    Returns:
        (bool, str): (유효 여부, 에러 메시지 또는 빈 문자열)
    """
    try:
        ast.parse(expr, mode='eval')
    except SyntaxError as e:
        return False, str(e)
    try:
        _validate_user(expr)
    except ValueError as e:
        return False, str(e)
    return True, ""


def normalize_user_input(equation_str: str) -> str:
    """
    사용자 방정식 입력을 정규화합니다.

    - 공백 정리
    - 대문자 C → c (상수항)
    - Log/LOG → log, Exp/EXP → exp
    - QoQ/YoY/MA/T → 소문자
    - 전각→반각 변환
    """
    s = equation_str.strip()
    s = re.sub(r'\s+', ' ', s)

    # 상수항 정규화
    s = re.sub(r'\s+C\s+', ' c ', s)

    # 함수명
    s = re.sub(r'\bLog\b', 'log', s)
    s = re.sub(r'\bLOG\b', 'log', s)
    s = re.sub(r'\bExp\b', 'exp', s)
    s = re.sub(r'\bEXP\b', 'exp', s)
    s = re.sub(r'\bDlog\b', 'dlog', s)
    s = re.sub(r'\bDLOG\b', 'dlog', s)

    # 시계열 함수
    s = re.sub(r'\.QoQ\b', '.qoq', s, flags=re.IGNORECASE)
    s = re.sub(r'\.YoY\b', '.yoy', s, flags=re.IGNORECASE)
    s = re.sub(r'\.MA\(', '.ma(', s, flags=re.IGNORECASE)
    s = re.sub(r'\.GR\(', '.gr(', s, flags=re.IGNORECASE)
    s = re.sub(r'\.Diff\b', '.diff', s, flags=re.IGNORECASE)
    s = re.sub(r'\.T\(', '.t(', s)

    # 수학/변환 함수명 대소문자 통일 (괄호 앞에 오는 경우만): LOG( → log(
    _FUNCS = {'log', 'exp', 'abs', 'sqrt', 'dlog', 'd'}
    s = re.sub(r'\b([A-Za-z]+)\s*\(',
               lambda m: (m.group(1).lower() + '(')
               if m.group(1).lower() in _FUNCS else m.group(0), s)

    # 전각→반각
    for full, half in [('（', '('), ('）', ')'), ('＋', '+'),
                       ('－', '-'), ('＊', '*'), ('／', '/')]:
        s = s.replace(full, half)

    return s


# ============================================================================
# 4단계: 전처리 헬퍼 (시차범위 전개 / @def 매크로)
# ============================================================================

# .t(-1 to -2) / .t(-1:-2) / .t(-1..-2) 형태의 시차 범위
# (구분자 to / : / .. 모두 허용, 주변 공백 허용)
_LAGRANGE_RE = re.compile(r'\.t\(\s*(-?\d+)\s*(?:to|:|\.\.)\s*(-?\d+)\s*\)')
# 토큰 보존용(내부 공백 제거) 마커
_LAGRANGE_MARK = re.compile(r'\.t\((-?\d+)\x00(-?\d+)\)')

# @def NAME = EXPR  (텍스트 매크로 정의)
_DEF_RE = re.compile(r'^@def\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+)$')


def expand_lag_ranges(eq_str: str) -> str:
    """
    `.t(-a to -b)` 시차 범위를 개별 항으로 전개합니다.

    하나의 항(공백으로 구분)에 들어 있는 시차 범위를 a..b 각 시차에 대한
    별도 항으로 복제합니다. 추정식에서 다항분포시차(PDL)/다중시차를 간결하게
    작성할 때 사용합니다. 구분자는 `to`, `:`, `..` 모두 허용합니다.

    Examples:
        >>> expand_lag_ranges("log(PIMI) c log(PIMI.t(-1 to -2))")
        'log(PIMI) c log(PIMI.t(-1)) log(PIMI.t(-2))'

    제약: 한 항에 시차 범위는 하나만 사용할 수 있습니다.
    """
    # 1) 범위 표기 내부 공백을 마커(\x00)로 치환 → split() 시 토큰이 깨지지 않음
    #    (.t(-1 to -2) 처럼 범위 안에 공백이 있어도 한 토큰으로 유지)
    s = _LAGRANGE_RE.sub(lambda m: f'.t({m.group(1)}\x00{m.group(2)})', eq_str)

    out = []
    for tok in s.split():
        m = _LAGRANGE_MARK.search(tok)
        if not m:
            out.append(tok)
            continue
        a, b = int(m.group(1)), int(m.group(2))
        lo, hi = (a, b) if a <= b else (b, a)
        for k in range(lo, hi + 1):
            out.append(tok[:m.start()] + f'.t({k})' + tok[m.end():])
    return ' '.join(out)


# 변수명 토큰 (앞에 영숫자/_/. 가 오지 않는 식별자)
_IDENT_RE = re.compile(r'(?<![A-Za-z0-9_.])([A-Za-z_][A-Za-z0-9_]*)(?![A-Za-z0-9_])')

# 대소문자 교정에서 제외할 예약어 (상수항 c, 함수/연산자/시계열 속성)
_CANON_SKIP = frozenset({
    'c', 'log', 'exp', 'abs', 'sqrt', 'dlog', 'd', 'gr',
    'np', 'df', 'pd', 't', 'ma', 'qoq', 'yoy', 'diff', 'to',
})


def canonicalize_columns(expr: str, columns) -> str:
    """식 문자열의 변수명을 데이터 컬럼의 실제 대소문자로 교정한다(대소문자 무시).

    - 데이터 컬럼에 대소문자 무시 매칭이 있을 때만 그 컬럼명으로 치환한다.
    - 함수 호출(바로 뒤 `(`), 시계열 속성(앞에 `.`), 상수항 `c`,
      예약어/연산자는 건드리지 않는다.
    - 매칭되는 컬럼이 없으면(오타·식별자 등) 원형 유지 → 이후 검증이 처리.

    Examples:
        >>> canonicalize_columns("log(rcpsa) c log(Krw/cpi)", ["RCPSA","KRW","CPI"])
        "log(RCPSA) c log(KRW/CPI)"
    """
    if columns is None:
        return expr
    colmap = {}
    for c in columns:
        colmap.setdefault(str(c).lower(), str(c))
    if not colmap:
        return expr

    def _repl(m: 're.Match') -> str:
        tok = m.group(1)
        low = tok.lower()
        if low in _CANON_SKIP or tok.startswith('_at_'):
            return tok
        # 함수 호출이면(바로 뒤가 '(') 건드리지 않음. 단 함수가 아닌 이름 뒤의 '('는
        # EViews 시차 표기 X(-1)이므로 변수로 보고 교정한다.
        if expr[m.end():].lstrip().startswith('(') and low not in colmap:
            return tok
        return colmap.get(low, tok)

    return _IDENT_RE.sub(_repl, expr)


def _apply_macros(s: str, macros: Dict[str, str]) -> str:
    """문자열 s에서 매크로 이름을 (정의식)으로 치환합니다(단어 경계 기준)."""
    for name, expr in macros.items():
        s = re.sub(
            r'(?<![A-Za-z0-9_])' + re.escape(name) + r'(?![A-Za-z0-9_])',
            '(' + expr + ')', s)
    return s


def expand_macros(lines: List[str]) -> List[str]:
    """
    `@def NAME = EXPR` 매크로를 수집해 이후 줄에서 이름을 정의식으로 치환합니다.

    - @def 줄 자체는 결과에서 제거됩니다.
    - 매크로 정의는 위에서 아래로 순서대로 적용되며, 뒤 매크로 정의에서
      앞 매크로를 사용할 수 있습니다.
    - 치환은 단어 경계 기준이라 변수명의 일부에는 영향을 주지 않습니다.

    Examples:
        >>> expand_macros(["@def REALRATE = CBR3YAA_ - CPI.yoy",
        ...                 "log(RFISA) c log(REALRATE+100)"])
        ['log(RFISA) c log((CBR3YAA_ - CPI.yoy)+100)']
    """
    macros: Dict[str, str] = {}
    out: List[str] = []
    for line in lines:
        m = _DEF_RE.match(line.strip())
        if m:
            name, expr = m.group(1), m.group(2).strip()
            macros[name] = _apply_macros(expr, macros)
            continue
        out.append(_apply_macros(line, macros) if macros else line)
    return out
