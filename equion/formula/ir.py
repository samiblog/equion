#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""방정식 중간표현(IR) — 엔진 v3의 단일 의미 모델.

모든 시계열 연산(.t/.ma/.qoq/.yoy/.gr/.diff, d(), dlog(), @pc/@movav 등)을
파싱 단계에서 **시차가 붙은 변수 잎(Var(name, lag))의 산술식**으로 풀어 둔다.

    X.qoq          → (X[0] / X[-1] - 1) * 100
    (A+B).ma(2)    → ((A[0]+B[0]) + (A[-1]+B[-1])) / 2
    log(X).t(-1)   → log(X[-1])
    dlog(X)        → log(X[0]) - log(X[-1])

시차 이동은 점별 함수와 교환되므로 이 전개는 항상 가능하고, 덕분에
  - 추정(전 기간 벡터 평가, `evaluate`)과
  - 풀이(한 기간 스칼라 평가, `to_code`로 생성한 함수)가
**같은 IR을 쓰므로 두 경로의 의미 일치가 구조적으로 보장**된다.
기호 미분(`deriv`)은 해석적 자코비안에 쓰인다.
"""

import ast
import math
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, Optional, Set, Tuple

import numpy as np

from .parser import DSLError, FUNCTIONS, INTERNAL_FUNCTIONS, parse_expression, reserved_name_error, _int_arg


# ---------------------------------------------------------------------------
# 노드
# ---------------------------------------------------------------------------
class Node:
    __slots__ = ()


@dataclass(frozen=True, slots=True)
class Const(Node):
    value: float


@dataclass(frozen=True, slots=True)
class Var(Node):
    name: str
    lag: int = 0          # 음수=과거(시차), 0=현시점, 양수=미래(lead)


@dataclass(frozen=True, slots=True)
class Coef(Node):
    index: int            # 계수 번호(추정식 내부 0부터, NLS는 c(n)의 n)


@dataclass(frozen=True, slots=True)
class Neg(Node):
    arg: Node


@dataclass(frozen=True, slots=True)
class Bin(Node):
    op: str               # '+', '-', '*', '/', '**'
    a: Node
    b: Node


@dataclass(frozen=True, slots=True)
class Func(Node):
    name: str             # 'log', 'exp', 'abs', 'sqrt', 'sign'
    arg: Node


ZERO = Const(0.0)
ONE = Const(1.0)


# ---------------------------------------------------------------------------
# 단순화 생성자 (상수 접기 + 항등원 제거)
# ---------------------------------------------------------------------------
def _is(c, v):
    return isinstance(c, Const) and c.value == v


def add(a, b):
    if _is(a, 0.0):
        return b
    if _is(b, 0.0):
        return a
    if isinstance(a, Const) and isinstance(b, Const):
        return Const(a.value + b.value)
    return Bin("+", a, b)


def sub(a, b):
    if _is(b, 0.0):
        return a
    if _is(a, 0.0):
        return neg(b)
    if isinstance(a, Const) and isinstance(b, Const):
        return Const(a.value - b.value)
    return Bin("-", a, b)


def mul(a, b):
    if _is(a, 0.0) or _is(b, 0.0):
        return ZERO
    if _is(a, 1.0):
        return b
    if _is(b, 1.0):
        return a
    if isinstance(a, Const) and isinstance(b, Const):
        return Const(a.value * b.value)
    return Bin("*", a, b)


def div(a, b):
    if _is(b, 1.0):
        return a
    if _is(a, 0.0) and not _is(b, 0.0):
        return ZERO
    if isinstance(a, Const) and isinstance(b, Const) and b.value != 0:
        return Const(a.value / b.value)
    return Bin("/", a, b)


def power(a, b):
    if _is(b, 1.0):
        return a
    if _is(b, 0.0):
        return ONE
    if isinstance(a, Const) and isinstance(b, Const):
        try:
            v = math.pow(a.value, b.value)
            return Const(v)
        except (ValueError, OverflowError, ZeroDivisionError):
            pass
    return Bin("**", a, b)


def neg(a):
    if isinstance(a, Const):
        return Const(-a.value)
    if isinstance(a, Neg):
        return a.arg
    return Neg(a)


def func(name, a):
    if isinstance(a, Const):
        try:
            return Const(_SCALAR_FUNCS[name](a.value))
        except (ValueError, OverflowError):
            pass
    return Func(name, a)


# ---------------------------------------------------------------------------
# 시차 이동과 시계열 연산 전개
# ---------------------------------------------------------------------------
def shift(node: Node, k: int) -> Node:
    """모든 변수 잎의 시차에 k를 더한다(k=-1 → 한 기 전)."""
    if k == 0:
        return node
    if isinstance(node, Var):
        return Var(node.name, node.lag + k)
    if isinstance(node, (Const, Coef)):
        return node
    if isinstance(node, Neg):
        return Neg(shift(node.arg, k))
    if isinstance(node, Bin):
        return Bin(node.op, shift(node.a, k), shift(node.b, k))
    if isinstance(node, Func):
        return Func(node.name, shift(node.arg, k))
    raise TypeError(node)


def pct_change(x: Node, n: int) -> Node:
    """x / x(-n) - 1  (pandas pct_change(n)와 같은 값)."""
    return sub(div(x, shift(x, -n)), ONE)


def difference(x: Node, n: int = 1, s: int = 0) -> Node:
    """(1-L)^n (1-L^s) x  — EViews d(x, n, s)."""
    for _ in range(n):
        x = sub(x, shift(x, -1))
    if s:
        x = sub(x, shift(x, -s))
    return x


def lag_sum(x: Node, n: int) -> Node:
    total = x
    for i in range(1, n):
        total = add(total, shift(x, -i))
    return total


@dataclass
class BuildContext:
    yoy_periods: int = 4        # .yoy / @pcy 시차(분기4·연1·월12)
    disable_qoq: bool = False   # 연간이면 .qoq 금지
    allow_coef: bool = False    # NLS 식의 c(n) 허용


def build(expr: str, ctx: Optional[BuildContext] = None) -> Node:
    """사용자 식 문자열(정규화·지시자 처리 후) → IR."""
    ctx = ctx or BuildContext()
    tree = parse_expression(expr, allow_coef=ctx.allow_coef)
    return _Builder(ctx, expr).visit(tree.body)


class _Builder:
    def __init__(self, ctx: BuildContext, expr: str):
        self.ctx = ctx
        self.expr = expr

    def fail(self, msg):
        raise DSLError(f"{msg} — 식: {self.expr}")

    def visit(self, n) -> Node:
        if isinstance(n, ast.Constant):
            return Const(float(n.value))
        if isinstance(n, ast.Name):
            return self.var(n.id, 0)
        if isinstance(n, ast.UnaryOp):
            v = self.visit(n.operand)
            return neg(v) if isinstance(n.op, ast.USub) else v
        if isinstance(n, ast.BinOp):
            a, b = self.visit(n.left), self.visit(n.right)
            op = type(n.op)
            if op is ast.Add:
                return add(a, b)
            if op is ast.Sub:
                return sub(a, b)
            if op is ast.Mult:
                return mul(a, b)
            if op is ast.Div:
                return div(a, b)
            return power(a, b)
        if isinstance(n, ast.Attribute):          # .qoq / .yoy / .diff
            x = self.visit(n.value)
            if n.attr == "qoq":
                if self.ctx.disable_qoq:
                    self.fail("이 주기(연간)에서는 .qoq를 사용할 수 없습니다. 전년대비는 .yoy를 사용하세요")
                return mul(pct_change(x, 1), Const(100.0))
            if n.attr == "yoy":
                return mul(pct_change(x, self.ctx.yoy_periods), Const(100.0))
            return difference(x, 1)
        if isinstance(n, ast.Call):
            return self.visit_call(n)
        self.fail(f"지원하지 않는 구문 {type(n).__name__}")

    def visit_call(self, n: ast.Call) -> Node:
        f = n.func
        if isinstance(f, ast.Attribute):          # X.t(k) / X.ma(n) / X.gr(n)
            x = self.visit(f.value)
            k = _int_arg(n.args[0])
            if f.attr == "t":
                return shift(x, k)
            if k is None or k < 1:
                self.fail(f".{f.attr}()의 인자는 1 이상의 정수여야 합니다")
            if f.attr == "ma":
                return div(lag_sum(x, k), Const(float(k)))
            return mul(pct_change(x, k), Const(100.0))      # .gr(n)
        name = f.id
        if name == "c" and self.ctx.allow_coef:
            return Coef(_int_arg(n.args[0]))
        if name in FUNCTIONS or name in INTERNAL_FUNCTIONS:
            x = self.visit(n.args[0])
            extra = [_int_arg(a) for a in n.args[1:]]
            return self.apply_function(name, x, extra)
        # EViews 시차 X(-1)
        k = _int_arg(n.args[0])
        return self.var(name, k)

    def var(self, name: str, lag: int) -> Node:
        why = reserved_name_error(name)
        if why:
            self.fail(why)
        return Var(name, lag)

    def apply_function(self, name, x, extra):
        yoy = self.ctx.yoy_periods

        def need(nmin, nmax):
            if not (nmin <= len(extra) <= nmax):
                self.fail(f"{name.replace('_at_', '@')}()의 인자 개수가 맞지 않습니다")

        if name in ("log", "_at_log"):
            need(0, 0)
            return func("log", x)
        if name in ("exp", "_at_exp"):
            need(0, 0)
            return func("exp", x)
        if name in ("abs", "_at_abs"):
            need(0, 0)
            return func("abs", x)
        if name in ("sqrt", "_at_sqrt"):
            need(0, 0)
            return func("sqrt", x)
        if name in ("d", "dlog"):
            need(0, 2)
            order = extra[0] if len(extra) >= 1 else 1
            seas = extra[1] if len(extra) >= 2 else 0
            if order < 0 or seas < 0:
                self.fail(f"{name}()의 차수는 0 이상이어야 합니다")
            base = func("log", x) if name == "dlog" else x
            return difference(base, order, seas)
        if name == "_at_pc":
            need(0, 0)
            return mul(pct_change(x, 1), Const(100.0))
        if name == "_at_pch":
            need(0, 0)
            return pct_change(x, 1)
        if name == "_at_pcy":
            need(0, 0)
            return mul(pct_change(x, yoy), Const(100.0))
        if name == "_at_pchy":
            need(0, 0)
            return pct_change(x, yoy)
        if name == "_at_pca":
            need(0, 0)
            return mul(sub(power(div(x, shift(x, -1)), Const(float(yoy))), ONE), Const(100.0))
        if name in ("_at_movav", "_at_movsum"):
            need(1, 1)
            k = extra[0]
            if k is None or k < 1:
                self.fail(f"{name.replace('_at_', '@')}()의 기간은 1 이상의 정수여야 합니다")
            total = lag_sum(x, k)
            return div(total, Const(float(k))) if name == "_at_movav" else total
        self.fail(f"알 수 없는 함수 {name}")


# ---------------------------------------------------------------------------
# 순회 유틸
# ---------------------------------------------------------------------------
def walk(node: Node) -> Iterable[Node]:
    stack = [node]
    while stack:
        n = stack.pop()
        yield n
        if isinstance(n, Neg):
            stack.append(n.arg)
        elif isinstance(n, Bin):
            stack.append(n.b)
            stack.append(n.a)
        elif isinstance(n, Func):
            stack.append(n.arg)


def leaves(node: Node) -> Set[Tuple[str, int]]:
    """변수 잎 (이름, 시차) 집합."""
    return {(n.name, n.lag) for n in walk(node) if isinstance(n, Var)}


def variables(node: Node) -> Set[str]:
    return {n.name for n in walk(node) if isinstance(n, Var)}


def coef_indices(node: Node) -> Set[int]:
    return {n.index for n in walk(node) if isinstance(n, Coef)}


def first_variable(node: Node) -> Optional[str]:
    """식에서 왼쪽부터 처음 나오는 변수 이름 (EViews 정규화 규칙)."""
    if isinstance(node, Var):
        return node.name
    if isinstance(node, Neg):
        return first_variable(node.arg)
    if isinstance(node, Func):
        return first_variable(node.arg)
    if isinstance(node, Bin):
        return first_variable(node.a) or first_variable(node.b)
    return None


def max_lag(node: Node) -> int:
    lags = [n.lag for n in walk(node) if isinstance(n, Var)]
    return -min(lags) if lags and min(lags) < 0 else 0


def max_lead(node: Node) -> int:
    lags = [n.lag for n in walk(node) if isinstance(n, Var)]
    return max(lags) if lags and max(lags) > 0 else 0


def substitute_coefs(node: Node, values: Dict[int, float]) -> Node:
    """Coef 잎을 상수로 바꾼다."""
    if isinstance(node, Coef):
        return Const(float(values[node.index])) if node.index in values else node
    if isinstance(node, (Const, Var)):
        return node
    if isinstance(node, Neg):
        return neg(substitute_coefs(node.arg, values))
    if isinstance(node, Bin):
        a, b = substitute_coefs(node.a, values), substitute_coefs(node.b, values)
        return _REBUILD[node.op](a, b)
    if isinstance(node, Func):
        return func(node.name, substitute_coefs(node.arg, values))
    raise TypeError(node)


_REBUILD = {"+": add, "-": sub, "*": mul, "/": div, "**": power}


# ---------------------------------------------------------------------------
# 벡터 평가 (추정용: 전 기간 numpy 배열)
# ---------------------------------------------------------------------------
_NP_FUNCS = {"log": np.log, "exp": np.exp, "abs": np.abs, "sqrt": np.sqrt, "sign": np.sign}


def shift_array(arr: np.ndarray, lag: int) -> np.ndarray:
    """out[t] = arr[t+lag] (범위 밖은 NaN)."""
    T = len(arr)
    if lag == 0:
        return arr
    out = np.full(T, np.nan)
    if lag < 0:
        k = -lag
        if k < T:
            out[k:] = arr[:T - k]
    else:
        if lag < T:
            out[:T - lag] = arr[lag:]
    return out


def evaluate(node: Node, get_array: Callable[[str], np.ndarray],
             coefs: Optional[Dict[int, float]] = None, length: Optional[int] = None) -> np.ndarray:
    """전 기간 벡터 평가. get_array(name) → 길이 T float 배열.

    변수가 없는 식(예: 계수에 대한 도함수 2·c(2))은 length를 주면 그 길이로 채운다."""
    cache: Dict[Tuple[str, int], np.ndarray] = {}

    def ev(n):
        if isinstance(n, Const):
            return n.value
        if isinstance(n, Var):
            key = (n.name, n.lag)
            if key not in cache:
                cache[key] = shift_array(np.asarray(get_array(n.name), dtype=float), n.lag)
            return cache[key]
        if isinstance(n, Coef):
            if coefs is None or n.index not in coefs:
                raise DSLError(f"계수 c({n.index}) 값이 없습니다")
            return coefs[n.index]
        if isinstance(n, Neg):
            return -ev(n.arg)
        if isinstance(n, Bin):
            a, b = ev(n.a), ev(n.b)
            if n.op == "+":
                return a + b
            if n.op == "-":
                return a - b
            if n.op == "*":
                return a * b
            if n.op == "/":
                return a / b
            return np.power(a, b)
        if isinstance(n, Func):
            return _NP_FUNCS[n.name](ev(n.arg))
        raise TypeError(n)

    with np.errstate(all="ignore"):
        out = ev(node)
    if np.isscalar(out):
        T = length
        for name in variables(node):
            T = len(get_array(name))
            break
        if T is None:
            raise DSLError("변수가 없는 상수식은 시계열로 평가할 수 없습니다")
        out = np.full(T, float(out))
    return np.asarray(out, dtype=float)


# ---------------------------------------------------------------------------
# 스칼라 코드 생성 (풀이용)
# ---------------------------------------------------------------------------
def _sign(v):
    return float((v > 0) - (v < 0))


_SCALAR_FUNCS = {"log": math.log, "exp": math.exp, "abs": abs, "sqrt": math.sqrt, "sign": _sign}

#: 생성 코드 실행 네임스페이스 (builtins 없음)
RUNTIME = {
    "__builtins__": {},
    "_log": math.log, "_exp": math.exp, "_sqrt": math.sqrt, "_abs": abs,
    "_sign": _sign, "_pow": math.pow, "nan": float("nan"),
}

#: 생성 코드 평가 중 정의역 위반 등으로 날 수 있는 예외(→ NaN 취급)
EVAL_ERRORS = (ValueError, ZeroDivisionError, OverflowError, TypeError)


def to_code(node: Node, leaf: Callable[[Var], str],
            coef: Callable[[Coef], str] = None) -> str:
    """IR → 파이썬 식 문자열. 잎·계수 표현은 콜백이 결정한다."""
    def c(n):
        if isinstance(n, Const):
            v = n.value
            if math.isnan(v):
                return "nan"
            if math.isinf(v):
                return "(1e308*10)" if v > 0 else "(-1e308*10)"
            return f"({v!r})" if v < 0 else repr(v)
        if isinstance(n, Var):
            return leaf(n)
        if isinstance(n, Coef):
            if coef is None:
                raise DSLError(f"계수 c({n.index})가 상수로 치환되지 않았습니다")
            return coef(n)
        if isinstance(n, Neg):
            return f"(-{c(n.arg)})"
        if isinstance(n, Bin):
            if n.op == "**":
                if isinstance(n.b, Const) and float(n.b.value).is_integer() and abs(n.b.value) <= 64:
                    return f"({c(n.a)} ** {int(n.b.value)})"
                return f"_pow({c(n.a)}, {c(n.b)})"
            return f"({c(n.a)} {n.op} {c(n.b)})"
        if isinstance(n, Func):
            return f"_{n.name}({c(n.arg)})"
        raise TypeError(n)
    return c(node)


# ---------------------------------------------------------------------------
# 기호 미분
# ---------------------------------------------------------------------------
def deriv(node: Node, wrt) -> Node:
    """∂node/∂wrt. wrt는 Var(현시점 변수) 또는 Coef."""
    if isinstance(node, Const):
        return ZERO
    if isinstance(node, (Var, Coef)):
        return ONE if node == wrt else ZERO
    if isinstance(node, Neg):
        return neg(deriv(node.arg, wrt))
    if isinstance(node, Bin):
        a, b = node.a, node.b
        da, db = deriv(a, wrt), deriv(b, wrt)
        if node.op == "+":
            return add(da, db)
        if node.op == "-":
            return sub(da, db)
        if node.op == "*":
            return add(mul(da, b), mul(a, db))
        if node.op == "/":
            if _is(db, 0.0):
                return div(da, b)
            return div(sub(mul(da, b), mul(a, db)), mul(b, b))
        # a ** b
        if _is(db, 0.0):
            if _is(da, 0.0):
                return ZERO
            return mul(mul(b, power(a, sub(b, ONE))), da)
        return mul(node, add(mul(db, func("log", a)), div(mul(b, da), a)))
    if isinstance(node, Func):
        a = node.arg
        da = deriv(a, wrt)
        if _is(da, 0.0):
            return ZERO
        if node.name == "log":
            return div(da, a)
        if node.name == "exp":
            return mul(node, da)
        if node.name == "sqrt":
            return div(da, mul(Const(2.0), node))
        if node.name == "abs":
            return mul(Func("sign", a), da)
        if node.name == "sign":
            return ZERO
    raise TypeError(node)


# ---------------------------------------------------------------------------
# 표시용 문자열
# ---------------------------------------------------------------------------
_PREC = {"+": 1, "-": 1, "*": 2, "/": 2, "**": 3}


def to_str(node: Node, leaf: Callable[[Var], str] = None) -> str:
    """사람이 읽는 식 문자열. 기본 잎 표기는 X, X(-1), X(+1)."""
    def default_leaf(v):
        return v.name if v.lag == 0 else f"{v.name}({v.lag:+d})"
    lf = leaf or default_leaf

    def s(n, parent=0):
        if isinstance(n, Const):
            v = n.value
            txt = repr(v) if not float(v).is_integer() or abs(v) >= 1e15 else str(int(v))
            return f"({txt})" if v < 0 and parent else txt
        if isinstance(n, Var):
            return lf(n)
        if isinstance(n, Coef):
            return f"c({n.index})"
        if isinstance(n, Neg):
            return f"-{s(n.arg, 4)}"
        if isinstance(n, Bin):
            p = _PREC[n.op]
            right_p = p + 1 if n.op in ("-", "/", "**") else p
            out = f"{s(n.a, p)} {n.op} {s(n.b, right_p)}"
            return f"({out})" if p < parent else out
        if isinstance(n, Func):
            return f"{n.name}({s(n.arg)})"
        raise TypeError(n)
    return s(node)


def to_pandas_str(node: Node) -> str:
    """pandas 표현 문자열(df['X'].shift(k)) — 표시·하위호환용."""
    def leaf(v):
        base = f"df['{v.name}']"
        return base if v.lag == 0 else f"{base}.shift({-v.lag})"
    txt = to_str(node, leaf)
    for fn in ("log", "exp", "abs", "sqrt", "sign"):
        txt = txt.replace(f"{fn}(", f"np.{fn}(")
    return txt
