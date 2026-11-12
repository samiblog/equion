#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""방정식 DSL 파서 — 단일 문법·안전 검증·EViews 문법 수용 (엔진 v3).

역할(문자열 단계만 담당, 수치는 다루지 않는다):
  - 줄 분류: 최상위 `=` 유무(공백 무관) + 계수참조 `c(n)` 여부
      · `=` 없음            → 추정식(EViews `Y c X1 X2 ...`)
      · `=` 있고 c(n) 없음  → 항등식
      · `=` 있고 c(n) 있음  → 비선형(NLS) 추정식
  - 항 분리: 괄호 깊이 0의 공백만 항 구분자(괄호 안 공백 허용)
  - EViews 문법 변환: `^`→`**`, `X(-1)` 시차, `X(-1 to -4)` 시차범위, `@pc/@pch/...` 함수
  - 지시자 분리: `@smpl S E`, `@inst Z ...`(또는 단독 `@`), `@coef v ...`, `@start v ...`
  - 화이트리스트 검증: 허용된 노드·함수·속성 외에는 전부 거부(코드 실행 차단)

수치 의미(시차 전개 등)는 ir.py가 담당한다.
"""

import ast
import re
from typing import Dict, List, Optional, Tuple

from .ast_formula import normalize_user_input


class UnknownVariableError(ValueError):
    """식이 자료에 없는 변수를 씀(오타·자료 누락) — 식 문법 오류처럼 입력 오류다(명령줄 종료 코드 3, `equion check`와 같게)."""


class DSLError(ValueError):
    """방정식 문법/검증 오류 (사용자에게 그대로 보여줄 메시지)."""


# ---------------------------------------------------------------------------
# 허용 목록
# ---------------------------------------------------------------------------
#: 사용자 함수(소문자). dlog/d는 (x[, n[, s]]) 인자를 받는다.
FUNCTIONS = frozenset({"log", "exp", "abs", "sqrt", "dlog", "d"})

#: EViews @함수 → 내부 이름(`_at_` 접두). 인자 개수는 ir.py에서 검사.
AT_FUNCTIONS = {
    "pc": "_at_pc",        # 100*(x/x(-1)-1)
    "pch": "_at_pch",      # x/x(-1)-1
    "pca": "_at_pca",      # 연율화 % 변화
    "pcy": "_at_pcy",      # 100*(x/x(-연간시차)-1)
    "pchy": "_at_pchy",    # x/x(-연간시차)-1
    "movav": "_at_movav",  # 이동평균(x, n)
    "movsum": "_at_movsum",  # 이동합(x, n)
    "abs": "_at_abs", "log": "_at_log", "exp": "_at_exp", "sqrt": "_at_sqrt",
}
INTERNAL_FUNCTIONS = frozenset(AT_FUNCTIONS.values())

RESERVED_NAMES = frozenset({"c"}) | FUNCTIONS   # 변수 이름으로 못 쓰는 이름(소문자 비교)


def reserved_name_error(name: str) -> Optional[str]:
    """변수·시리즈 이름으로 쓸 수 없는 이름이면 그 까닭(아니면 None)."""
    low = str(name).lower()
    if low == "c":
        return f"'{name}'은(는) 상수항·계수(c, c(1)…) 이름이라 변수로 쓸 수 없습니다 — 시리즈 이름을 바꾸세요(예: CONS)"
    if low in FUNCTIONS:
        return f"'{name}'은(는) 함수 {low}()의 이름이라 변수로 쓸 수 없습니다 — 시리즈 이름을 바꾸세요(예: {name.upper()}_)"
    return None


#: 속성형 연산자(호출 없이): X.qoq / X.yoy / X.diff
PLAIN_ATTRS = frozenset({"qoq", "yoy", "diff"})
#: 메서드형 연산자: X.t(k) / X.ma(n) / X.gr(n)
CALL_ATTRS = frozenset({"t", "ma", "gr"})

#: 식 안에서 따로 처리되는 지시자(데이터 컬럼으로 바뀌는 것 포함)
DIRECTIVES = frozenset({"smpl", "inst", "coef", "start", "seas", "trend", "d", "step", "def"})

#: 입력 한도 — 실수나 악의적인 입력이 메모리·시간·재귀 한계를 넘지 않게(DECISIONS D18)
MAX_TEXT = 20_000     # 한 식(줄)의 글자 수
MAX_DEPTH = 250       # 식 트리 깊이(괄호 중첩·연산 사슬)
MAX_LAG = 1_000       # 시차·앞섬·차분·이동평균 길이의 절댓값
MAX_RANGE = 100       # 시차범위 X(-a to -b) 한 개가 펼치는 항 수
MAX_TERMS = 500       # 추정식 한 개의 항 수(전개 후)

_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_COEF_RE = re.compile(r"(?<![A-Za-z0-9_.])[cC]\(\s*\d+\s*\)")


# ---------------------------------------------------------------------------
# 줄 분류 / 등호 분리
# ---------------------------------------------------------------------------
def find_top_level_eq(text: str) -> int:
    """괄호 깊이 0의 단일 `=` 위치(없으면 -1). `==`,`<=`,`>=`,`!=`는 등호가 아니다."""
    depth = 0
    for i, ch in enumerate(text):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == "=" and depth == 0:
            prev = text[i - 1] if i > 0 else ""
            nxt = text[i + 1] if i + 1 < len(text) else ""
            if prev in "=<>!" or nxt == "=":
                continue
            return i
    return -1


def has_coef_refs(text: str) -> bool:
    """`c(1)` 같은 계수 참조가 있는가 (NLS 식 판별)."""
    return bool(_COEF_RE.search(text))


def classify_line(line: str) -> str:
    """방정식 한 줄 → 'estimated' | 'identity' | 'nls'."""
    if find_top_level_eq(line) < 0:
        return "estimated"
    return "nls" if has_coef_refs(line) else "identity"


def is_identity(line: str) -> bool:
    return classify_line(line) == "identity"


def split_equation(text: str) -> Tuple[str, str]:
    """`LHS = RHS`를 최상위 등호에서 둘로 나눈다."""
    pos = find_top_level_eq(text)
    if pos < 0:
        raise DSLError(f"등호(=)가 없습니다: {text}")
    lhs, rhs = text[:pos].strip(), text[pos + 1:].strip()
    if not lhs or not rhs:
        raise DSLError(f"등호 양쪽이 비었습니다: {text}")
    return lhs, rhs


# ---------------------------------------------------------------------------
# 정규화 / EViews 문법 변환
# ---------------------------------------------------------------------------
_AT_CALL_RE = re.compile(r"@([A-Za-z_][A-Za-z0-9_]*)\s*\(")
_EVIEWS_RANGE_RE = re.compile(                    # 'to'는 대소문자 무시(X(-1 TO -4)) — 함수 이름·@지시자처럼
    r"(?<![A-Za-z0-9_.])([A-Za-z_][A-Za-z0-9_]*)\(\s*(-?\d+)\s*(?:[Tt][Oo]|:|\.\.)\s*(-?\d+)\s*\)")


def normalize(text: str) -> str:
    """사용자 입력 정규화: 기존 normalize_user_input + `^`→`**`."""
    if len(text) > MAX_TEXT:
        raise DSLError(f"식이 너무 깁니다({len(text):,}자 > {MAX_TEXT:,}자) — 식을 나누세요")
    s = normalize_user_input(text)
    s = s.replace("^", "**")
    s = re.sub(r"(?<![A-Za-z0-9_.])C\(\s*(\d+)\s*\)", r"c(\1)", s)   # NLS 계수 C(1) → c(1)
    return s


def convert_at_functions(text: str) -> str:
    """`@pc(`·`@movav(` 등 EViews 함수 호출을 내부 이름으로 바꾼다.

    지시자(@seas/@d/@step/@trend 등)는 이 단계 전에 처리돼 있어야 한다.
    모르는 @함수는 오류.
    """
    def repl(m):
        name = m.group(1).lower()
        if name in AT_FUNCTIONS:
            return AT_FUNCTIONS[name] + "("
        raise DSLError(f"지원하지 않는 함수 @{m.group(1)}( — 지원: "
                       + ", ".join("@" + k for k in sorted(AT_FUNCTIONS)))
    s = _AT_CALL_RE.sub(repl, text)
    m = re.search(r"@[A-Za-z_]*", s)
    if m:
        raise DSLError(f"처리되지 않은 지시자/기호 '{m.group(0)}' (위치 {m.start()})")
    return s


def convert_eviews_lag_ranges(text: str) -> str:
    """`X(-1 to -4)` (EViews 시차범위) → `X.t(-1 to -4)` (함수명은 제외)."""
    def repl(m):
        name = m.group(1)
        if name.lower() in FUNCTIONS or name in INTERNAL_FUNCTIONS or name == "c":
            return m.group(0)
        return f"{name}.t({m.group(2)} to {m.group(3)})"
    return _EVIEWS_RANGE_RE.sub(repl, text)


# ---------------------------------------------------------------------------
# 항 분리 (괄호 깊이 0의 공백 기준)
# ---------------------------------------------------------------------------
def _raw_split(text: str) -> List[str]:
    out, buf, depth = [], [], 0
    for i, ch in enumerate(text):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth < 0:
                raise DSLError(f"닫는 괄호가 더 많습니다 (위치 {i}): {text}")
        if ch.isspace() and depth == 0:
            if buf:
                out.append("".join(buf))
                buf = []
            continue
        buf.append(ch)
    if depth != 0:
        raise DSLError(f"괄호가 닫히지 않았습니다 (열린 괄호 {depth}개 남음): {text}")
    if buf:
        out.append("".join(buf))
    return out


def split_terms(text: str) -> List[str]:
    """추정식 명세를 항 목록으로 나눈다.

    규칙(EViews 관례 + 편의):
      - 괄호 깊이 0의 공백이 항 구분자. 괄호 안 공백은 자유롭다.
      - 단독 연산자 토큰(`+ - * / **`)은 앞뒤 토큰을 이어 한 항으로 만든다.
      - 연산자로 끝나는 토큰은 다음 토큰과, `*`·`/`로 시작하는 토큰은 앞 토큰과 잇는다.
      - `+`/`-`로 시작하는 토큰은 새 항(단항 부호)으로 본다. 예: `X -Y` → 두 항.
    """
    toks = _raw_split(text)
    merged: List[str] = []
    i = 0
    while i < len(toks):
        tok = toks[i]
        if merged and (tok in ("+", "-", "*", "/", "**") or tok.startswith(("*", "/"))):
            if tok in ("+", "-", "*", "/", "**"):
                if i + 1 >= len(toks):
                    raise DSLError(f"연산자 '{tok}' 뒤에 항이 없습니다: {text}")
                merged[-1] = f"{merged[-1]} {tok} {toks[i + 1]}"
                i += 2
            else:
                merged[-1] = f"{merged[-1]} {tok}"
                i += 1
            continue
        merged.append(tok)
        i += 1
        while merged[-1].endswith(("+", "-", "*", "/")) and i < len(toks):
            merged[-1] = f"{merged[-1]} {toks[i]}"
            i += 1
    for t in merged:
        if t in ("+", "-", "*", "/", "**") or t.endswith(("+", "-", "*", "/")):
            raise DSLError(f"연산자가 완결되지 않은 항: '{t}'")
    return merged


_LAGRANGE_RE = re.compile(r"\.t\(\s*(-?\d+)\s*(?:[Tt][Oo]|:|\.\.)\s*(-?\d+)\s*\)")


def expand_term_lag_range(term: str) -> List[str]:
    """한 항의 `.t(-a to -b)` 범위를 개별 항으로 전개(항당 범위 1개)."""
    found = list(_LAGRANGE_RE.finditer(term))
    if not found:
        return [term]
    if len(found) > 1:
        raise DSLError(f"한 항에는 시차범위를 하나만 쓸 수 있습니다: {term}")
    m = found[0]
    a, b = int(m.group(1)), int(m.group(2))
    if abs(b - a) + 1 > MAX_RANGE:
        raise DSLError(f"시차범위가 너무 깁니다({abs(b - a) + 1}개 > {MAX_RANGE}개): {term}")
    if max(abs(a), abs(b)) > MAX_LAG:
        raise DSLError(f"시차가 너무 큽니다(|{max(abs(a), abs(b))}| > {MAX_LAG}): {term}")
    step = 1 if b >= a else -1          # 쓴 방향 그대로: -1 to -3 → -1, -2, -3
    return [term[:m.start()] + f".t({k})" + term[m.end():] for k in range(a, b + step, step)]


# ---------------------------------------------------------------------------
# 지시자 분리 (@smpl / @inst / @coef / @start)
# ---------------------------------------------------------------------------
_DIRECTIVE_SPLIT_RE = re.compile(r"(?<![A-Za-z0-9_])@(smpl|inst|coef|start)\b|(?<=\s)@(?=\s|$)",
                                 re.IGNORECASE)
_INST_RE = re.compile(r"(?<![A-Za-z0-9_])@inst\b|(?<=\s)@(?=\s|$)", re.IGNORECASE)


def has_instruments(text: str) -> bool:
    """식 명세에 도구변수 지시자(`@inst …`·EViews식 단독 `@`)가 있는가.

    extract_directives와 같은 규칙이다(대소문자 무시). `#` 뒤 주석은 보지 않는다."""
    return bool(_INST_RE.search((text or "").split("#", 1)[0]))


def extract_directives(text: str) -> Tuple[str, Dict[str, List[str]]]:
    """명세 문자열에서 꼬리 지시자를 떼어낸다.

    지원: `@smpl S E`, `@inst Z1 Z2 ...`(EViews식 단독 `@`도 동일), `@coef v1 v2 ...`,
    `@start v1 v2 ...`. 지시자는 다음 지시자 또는 줄 끝까지 이어진다.
    반환: (본문, {'smpl': [...], 'inst': [...], 'coef': [...], 'start': [...]})
    """
    out: Dict[str, List[str]] = {}
    matches = list(_DIRECTIVE_SPLIT_RE.finditer(text))
    if not matches:
        return text.strip(), out
    body = text[:matches[0].start()].strip()
    for k, m in enumerate(matches):
        name = (m.group(1) or "inst").lower()
        end = matches[k + 1].start() if k + 1 < len(matches) else len(text)
        payload = text[m.end():end].strip()
        if name in out:
            raise DSLError(f"지시자 @{name}가 두 번 나왔습니다: {text}")
        out[name] = _raw_split(payload) if payload else []
    if "smpl" in out and len(out["smpl"]) != 2:
        raise DSLError(f"@smpl은 시작·끝 두 시점이 필요합니다: @smpl {' '.join(out['smpl'])}")
    for key in ("coef", "start"):
        if key in out:
            try:
                out[key] = [float(v) for v in out[key]]
            except ValueError:
                raise DSLError(f"@{key} 값은 숫자여야 합니다: {out[key]}")
    return body, out


# ---------------------------------------------------------------------------
# 화이트리스트 검증 + 파싱
# ---------------------------------------------------------------------------
_AT_DISPLAY = {v: "@" + k for k, v in AT_FUNCTIONS.items()}


def _lag_ok(node, expr, value, what):
    if value is not None and abs(value) > MAX_LAG:
        _err(node, expr, f"{what} 값이 너무 큽니다(|{value}| > {MAX_LAG})")


def _depth(tree) -> int:
    """식 트리 깊이(재귀 없이)."""
    best, stack = 0, [(tree, 1)]
    while stack:
        node, d = stack.pop()
        if d > best:
            best = d
            if best > MAX_DEPTH:
                return best
        stack.extend((c, d + 1) for c in ast.iter_child_nodes(node))
    return best


def _int_arg(node) -> Optional[int]:
    if isinstance(node, ast.Constant) and isinstance(node.value, int) and not isinstance(node.value, bool):
        return node.value
    if (isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd))
            and isinstance(node.operand, ast.Constant)
            and isinstance(node.operand.value, int) and not isinstance(node.operand.value, bool)):
        return -node.operand.value if isinstance(node.op, ast.USub) else node.operand.value
    return None


def _err(node, expr, msg):
    col = getattr(node, "col_offset", None)
    where = f" (위치 {col}: '{expr[col:col + 20]}')" if col is not None else ""
    raise DSLError(f"{msg}{where} — 식: {expr}")


def _check(node, expr: str, allow_coef: bool):
    """허용 목록 밖의 구문을 만나면 DSLError."""
    if isinstance(node, ast.Expression):
        return _check(node.body, expr, allow_coef)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            _err(node, expr, "숫자 외의 상수는 쓸 수 없습니다")
        return
    if isinstance(node, ast.Name):
        if not _NAME_RE.match(node.id) or node.id.startswith("__"):
            _err(node, expr, f"허용되지 않는 이름 '{node.id}'")
        return
    if isinstance(node, ast.BinOp):
        if not isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow)):
            _err(node, expr, f"허용되지 않는 연산자 {type(node.op).__name__}")
        _check(node.left, expr, allow_coef)
        _check(node.right, expr, allow_coef)
        return
    if isinstance(node, ast.UnaryOp):
        if not isinstance(node.op, (ast.USub, ast.UAdd)):
            _err(node, expr, f"허용되지 않는 단항 연산자 {type(node.op).__name__}")
        _check(node.operand, expr, allow_coef)
        return
    if isinstance(node, ast.Attribute):
        if node.attr not in PLAIN_ATTRS:
            _err(node, expr, f"허용되지 않는 속성 '.{node.attr}' "
                             f"(허용: {', '.join('.' + a for a in sorted(PLAIN_ATTRS | CALL_ATTRS))})")
        _check(node.value, expr, allow_coef)
        return
    if isinstance(node, ast.Call):
        if node.keywords:
            _err(node, expr, "키워드 인자는 쓸 수 없습니다")
        f = node.func
        if isinstance(f, ast.Attribute):
            if f.attr not in CALL_ATTRS:
                _err(node, expr, f"허용되지 않는 메서드 '.{f.attr}()'")
            if len(node.args) != 1 or _int_arg(node.args[0]) is None:
                _err(node, expr, f"'.{f.attr}()'는 정수 인자 하나가 필요합니다")
            _lag_ok(node, expr, _int_arg(node.args[0]), f"'.{f.attr}()'의 인자")
            _check(f.value, expr, allow_coef)
            return
        if isinstance(f, ast.Name):
            name = f.id
            if name == "c" and allow_coef:
                if len(node.args) != 1 or _int_arg(node.args[0]) is None or _int_arg(node.args[0]) < 1:
                    _err(node, expr, "계수는 c(1), c(2)… 형태여야 합니다")
                return
            if name in FUNCTIONS or name in INTERNAL_FUNCTIONS:
                if not node.args:
                    _err(node, expr, f"{name}()에 인자가 없습니다")
                _check(node.args[0], expr, allow_coef)
                for a in node.args[1:]:
                    if _int_arg(a) is None:
                        _err(node, expr, f"{name}()의 추가 인자는 정수여야 합니다")
                    _lag_ok(node, expr, _int_arg(a), f"{_AT_DISPLAY.get(name, name)}()의 인자")
                return
            # EViews 시차 X(-1): 변수 이름 + 정수 인자 하나
            if _NAME_RE.match(name) and not name.startswith("__"):
                if len(node.args) == 1 and _int_arg(node.args[0]) is not None:
                    _lag_ok(node, expr, _int_arg(node.args[0]), "시차")
                    return
                _err(node, expr, f"알 수 없는 함수 '{name}()' (지원: "
                                 f"{', '.join(sorted(FUNCTIONS))}, @"
                                 f"{', @'.join(sorted(AT_FUNCTIONS))}; 시차는 X(-1) 또는 X.t(-1))")
        _err(node, expr, "허용되지 않는 호출 형태")
    _err(node, expr, f"허용되지 않는 구문 {type(node).__name__}")


def parse_expression(expr: str, allow_coef: bool = False) -> ast.Expression:
    """정규화된 식 문자열을 파싱하고 허용 목록으로 검증한 AST를 반환한다."""
    if len(expr) > MAX_TEXT:
        raise DSLError(f"식이 너무 깁니다({len(expr):,}자 > {MAX_TEXT:,}자) — 식을 나누세요")
    try:
        tree = ast.parse(expr, mode="eval")
    except (SyntaxError, RecursionError, MemoryError) as e:
        msg = getattr(e, "msg", None) or "식이 너무 깊거나 큽니다"
        pos = f" (위치 {e.offset})" if getattr(e, "offset", None) else ""
        raise DSLError(f"구문 오류{pos}: {msg} — 식: {expr[:200]}") from None
    if _depth(tree) > MAX_DEPTH:
        raise DSLError(f"식이 너무 깊습니다(중첩·연산 사슬 > {MAX_DEPTH}) — 긴 합은 중간 변수로 나누세요: {expr[:120]}…")
    _check(tree, expr, allow_coef)
    return tree


def validate_expression(expr: str, allow_coef: bool = False) -> None:
    """검증만 수행(통과 시 None, 실패 시 DSLError)."""
    parse_expression(expr, allow_coef=allow_coef)


def coef_numbers(tree: ast.AST) -> List[int]:
    """AST 안의 c(n) 번호들(등장 순서 유지, 중복 제거)."""
    seen, out = set(), []
    for n in ast.walk(tree):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "c"
                and n.args and _int_arg(n.args[0]) is not None):
            k = _int_arg(n.args[0])
            if k not in seen:
                seen.add(k)
                out.append(k)
    return sorted(out)
