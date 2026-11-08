#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""블록 파일 → 부품(식·항등식) — 추정하지 않고 구조만 읽는다 (D32).

블록 파일은 지금 방정식 파일 문법 그대로다(한 줄에 한 식, `#` 뒤는 설명, `@def` 매크로). 줄마다:

    분류        추정식(최상위 `=` 없음) · NLS(`=`와 `c(n)`) · 항등식(`=`만)
    목표변수    좌변의 첫 변수 — 부품 이름은 `블록:목표`(예: demand:CN)
    변수        식이 쓰는 변수(시차 포함)와 같은 기(시차 0) 변수 — 조립 검사·블록 분해에 쓴다

문제(문법 오류·한 블록 안의 목표 겹침)는 `파일:줄` 위치와 함께 모은다.
"""

from dataclasses import dataclass, field
from typing import FrozenSet, List, Optional, Set, Tuple

from ..data.io import read_text
from ..estimation.equation import Equation
from ..formula import ir
from ..formula.ast_formula import _DEF_RE, canonicalize_columns, expand_macros
from ..formula.parser import DSLError, classify_line, convert_at_functions, normalize, split_equation
from .config import BlockSpec


@dataclass
class Part:
    """블록 파일의 식 한 줄 — 혼자서도(추정·검사) 쓰이고 조립하면 모형의 식이 된다."""

    block: str
    target: str
    kind: str                 # 'equation'(추정식·NLS) | 'identity'
    text: str                 # 쓴 그대로(주석 뺌)
    expr: str                 # @def 매크로를 펼친 식
    file: str                 # 프로젝트 기준 경로
    line: int                 # 1부터
    desc: str = ""            # 줄 끝 '#' 뒤 설명
    lhs: Optional[ir.Node] = None
    rhs: Optional[ir.Node] = None
    data_vars: Set[str] = field(default_factory=set)     # 자료에 있어야 하는 변수(도구변수 포함)
    leaves: FrozenSet[Tuple[str, int]] = frozenset()      # 식이 쓰는 (변수, 시차)

    @property
    def id(self) -> str:
        return f"{self.block}:{self.target}"

    @property
    def where(self) -> str:
        return f"{self.file}:{self.line}"

    @property
    def variables(self) -> Set[str]:
        return {n for n, _ in self.leaves}

    @property
    def current(self) -> Set[str]:
        return {n for n, lag in self.leaves if lag == 0}

    def __repr__(self):
        return f"<부품 {self.id} ({'항등식' if self.kind == 'identity' else '추정식'}) {self.where}>"


def _ctx(data) -> ir.BuildContext:
    freq = getattr(data, "freq", "Q") or "Q"
    return ir.BuildContext(yoy_periods={"Q": 4, "A": 1, "M": 12}.get(freq, 4), disable_qoq=(freq == "A"))


def _sum(nodes):
    out = None
    for n in nodes:
        out = n if out is None else ir.add(out, n)
    return out if out is not None else ir.ZERO


def parse_line(expr: str, data) -> dict:
    """식 한 줄 → {kind, target, lhs, rhs, data_vars}. 추정하지 않는다."""
    kind = classify_line(normalize(expr))
    if kind == "identity":
        s = normalize(expr)
        if data is not None and data.data is not None:
            s = canonicalize_columns(s, data.data.columns)
        lhs, rhs = split_equation(s)
        ctx = _ctx(data)
        lhs_ir = ir.build(convert_at_functions(lhs), ctx)
        rhs_ir = ir.build(convert_at_functions(rhs), ctx)
        target = ir.first_variable(lhs_ir)
        if target is None:
            raise DSLError("항등식 좌변에 변수가 없습니다")
        used = ir.variables(lhs_ir) | ir.variables(rhs_ir)
        return {"kind": "identity", "target": target, "lhs": lhs_ir, "rhs": rhs_ir, "data_vars": used}
    eq = Equation(expr, data)
    eq._parse()
    if eq.rhs_template is not None:                       # NLS
        rhs_ir = eq.rhs_template
    else:
        rhs_ir = _sum(eq.term_irs)
    used = ir.variables(eq.lhs_ir) | ir.variables(rhs_ir)
    for z in eq.instrument_irs:
        used |= ir.variables(z)
    if eq.weights_ir is not None:
        used |= ir.variables(eq.weights_ir)
    return {"kind": "equation", "target": eq.target, "lhs": eq.lhs_ir, "rhs": rhs_ir, "data_vars": used}


def read_block(spec: BlockSpec, data) -> Tuple[List[Part], List[str]]:
    """블록 파일을 읽어 (부품 목록, 문제 목록). 문제는 '파일:줄: 내용'."""
    parts: List[Part] = []
    problems: List[str] = []
    try:
        text = read_text(spec.path)
    except (OSError, ValueError) as e:
        return [], [f"{spec.file}: {e}"]
    defs: List[str] = []
    for k, raw in enumerate(text.splitlines(), 1):
        body, _, comment = raw.partition("#")
        body = body.strip()
        if not body:
            continue
        if _DEF_RE.match(body):
            defs.append(body)
            continue
        expr = expand_macros(defs + [body])[-1] if defs else body
        try:
            info = parse_line(expr, data)
        except (DSLError, ValueError, KeyError) as e:
            problems.append(f"{spec.file}:{k}: {str(e)[:200]} — {body[:80]}")
            continue
        lhs, rhs = info["lhs"], info["rhs"]
        parts.append(Part(block=spec.name, target=info["target"], kind=info["kind"], text=body, expr=expr,
                          file=spec.file, line=k, desc=comment.strip(), lhs=lhs, rhs=rhs,
                          data_vars=set(info["data_vars"]),
                          leaves=frozenset(ir.leaves(lhs) | ir.leaves(rhs))))
    seen = {}
    for p in parts:
        if p.target in seen:
            problems.append(f"{spec.file}:{p.line}: 목표변수 {p.target}을(를) {spec.file}:{seen[p.target].line}의 식도 "
                            f"정합니다 — 한 블록에 같은 목표는 하나(목표변수는 좌변의 첫 변수)")
        else:
            seen[p.target] = p
    return parts, problems
