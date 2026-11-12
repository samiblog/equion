#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""연립 구조 분석 — 시스템 방정식, 정규화 매칭, 블록 분해 (엔진 v3).

- SystemEquation : 추정식/항등식을 하나의 형태(좌변 IR, 우변 IR, 목표변수)로 통일
- ModelSystem    : 변수 색인·정방성/중복/미지 변수 검사, 기간별 구조(블록) 캐시
- 매칭           : 식 ↔ 미지수 완전 매칭(기본은 목표변수, 막히면 증가경로로 재배정)
- 블록 분해      : 현시점 의존 그래프의 강연결요소(Tarjan) → 풀이 순서대로
"""

from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional, Sequence, Set, Tuple

from ..formula import ir


class StructureError(ValueError):
    """모델 구조 오류(정방성 위반·중복 정의·미지 변수·구조적 특이)."""


@dataclass
class SystemEquation:
    index: int                    # 시스템 내 번호
    kind: str                     # 'behavioral' | 'identity'
    label: str                    # 표시용(종속변수 표기 또는 항등식 좌변)
    target: str                   # 정규화 목표 변수
    lhs: ir.Node
    rhs: ir.Node                  # behavioral: Coef(0..k-1) 잎 포함
    n_coef: int = 0
    coef_offset: int = 0          # 전역 계수 벡터 P에서의 시작 위치
    af_slot: Optional[int] = None  # 조정항 AF 열 번호(behavioral만)
    source: object = None         # Equation 또는 항등식 dict
    leaves: Set[Tuple[str, int]] = field(default_factory=set)
    current: Set[str] = field(default_factory=set)

    def __post_init__(self):
        self.leaves = ir.leaves(self.lhs) | ir.leaves(self.rhs)
        self.current = {n for n, lag in self.leaves if lag == 0}

    @property
    def residual(self) -> ir.Node:
        return ir.sub(self.lhs, self.rhs)


@dataclass
class Block:
    eqs: List[int]                # 시스템 식 번호
    vars: List[int]               # 변수 색인(eqs와 같은 순서로 매칭된 미지수)
    compiled: object = None       # compiler.CompiledBlock (지연 생성)

    @property
    def size(self):
        return len(self.eqs)


@dataclass
class Structure:
    active: FrozenSet[int]
    unknowns: FrozenSet[int]
    blocks: List[Block]
    matching: Dict[int, int]      # 식 → 변수 색인

    def describe(self, system: "ModelSystem") -> List[dict]:
        out = []
        for k, b in enumerate(self.blocks):
            out.append({
                "block": k,
                "size": b.size,
                "type": "simultaneous" if b.size > 1 else "recursive",
                "variables": [system.var_names[j] for j in b.vars],
                "equations": [system.eqs[e].label for e in b.eqs],
            })
        return out


class ModelSystem:
    """시스템 방정식 집합 + 변수 색인 + 구조 캐시."""

    def __init__(self, equations: Sequence[SystemEquation], data_columns: Sequence[str]):
        self.eqs: List[SystemEquation] = list(equations)
        targets = [e.target for e in self.eqs]
        dup = sorted({t for t in targets if targets.count(t) > 1})
        if dup:
            def show(e):
                src = e.source
                if isinstance(src, dict):                     # 항등식
                    return f"항등식 '{src.get('formula', e.label)}'"
                text = getattr(src, "equation_str", None)
                return f"추정식 '{text}'" if text else e.label
            detail = "; ".join(f"{t}: " + ", ".join(show(e) for e in self.eqs if e.target == t)
                               for t in dup)
            raise StructureError(
                f"같은 변수를 결정하는 식이 둘 이상입니다 → {detail}. "
                "식 하나를 빼거나(모델의 drop) 그 식의 좌변을 바꾸세요 — 목표변수는 좌변의 첫 변수입니다.")
        self.endogenous: List[str] = targets
        referenced: Set[str] = set()
        for e in self.eqs:
            referenced |= {n for n, _ in e.leaves}
        self.exogenous: List[str] = sorted(referenced - set(targets))
        cols = set(data_columns)
        unknown = sorted(v for v in self.exogenous if v not in cols)
        if unknown:
            users = {v: [e.label for e in self.eqs if v in {n for n, _ in e.leaves}] for v in unknown}
            raise StructureError(
                "데이터에도 없고 어떤 식도 결정하지 않는 변수가 있습니다: "
                + "; ".join(f"{v} (사용: {', '.join(u[:3])})" for v, u in users.items()))
        self.var_names: List[str] = sorted(referenced | set(targets))
        self.var_index: Dict[str, int] = {v: j for j, v in enumerate(self.var_names)}
        self.endo_idx: List[int] = [self.var_index[t] for t in targets]
        self.exo_idx: List[int] = [self.var_index[v] for v in self.exogenous]
        self.eq_of_var: Dict[int, int] = {self.var_index[e.target]: e.index for e in self.eqs}
        # 현시점 사용 변수(색인) — 매칭·의존 그래프용
        self.incidence: List[Set[int]] = [{self.var_index[n] for n in e.current} for e in self.eqs]
        self.max_lag = max([-lag for e in self.eqs for _, lag in e.leaves if lag < 0] or [0])
        self.max_lead = max([lag for e in self.eqs for _, lag in e.leaves if lag > 0] or [0])
        self.n_coef = sum(e.n_coef for e in self.eqs)
        self.n_af = sum(1 for e in self.eqs if e.af_slot is not None)
        self._cache: Dict[Tuple[FrozenSet[int], FrozenSet[int]], Structure] = {}

    # ------------------------------------------------------------------
    def structure(self, active: FrozenSet[int] = None, unknowns: FrozenSet[int] = None) -> Structure:
        """활성 식·미지수 집합에 대한 블록 구조(캐시)."""
        if active is None:
            active = frozenset(range(len(self.eqs)))
        if unknowns is None:
            unknowns = frozenset(self.var_index[self.eqs[e].target] for e in active)
        key = (active, unknowns)
        st = self._cache.get(key)
        if st is None:
            st = self._build(active, unknowns)
            self._cache[key] = st
        return st

    def dependent_identities(self, structure: Structure = None, seed: int = 0) -> List[dict]:
        """블록 안에서 서로 종속인 항등식(같은 관계를 두 번 적은 것)을 찾는다 — 계수·자료 없이(D66).

        항등식에는 계수가 없으므로 블록 변수에 대한 항등식 자코비안의 행은 모형마다 정해져 있다. 그 행들이
        무작위 점 두 곳에서 모두 순위가 모자라면 어느 점에서나 모자란다 — 그 블록의 자코비안은 늘 특이하고
        해가 하나로 정해지지 않는다(또는 해가 없다). 예: `Y = CN + I + G + SD`와 `SD = Y - CN - I - G`,
        `A = B + G`와 `B = A - G`.

        돌려주는 것
            [{"block": 블록 번호, "variables": [블록 변수], "identities": [종속인 항등식 표시]}, …] — 없으면 []
        """
        import numpy as np
        st = structure or self.structure()
        rng = np.random.default_rng(seed)
        out = []
        for k, b in enumerate(st.blocks):
            ids = [e for e in b.eqs if self.eqs[e].kind == "identity"]
            if not ids:
                continue
            keys: Dict[Tuple[str, int], int] = {}

            def leaf(v, keys=keys):
                key = (v.name, v.lag)
                if key not in keys:
                    keys[key] = len(keys)
                return f"V[{keys[key]}]"
            try:
                rows = []
                for e in ids:
                    eq = self.eqs[e]
                    row = []
                    for j in b.vars:
                        name = self.var_names[j]
                        if name not in eq.current:
                            row.append("0.0")
                            continue
                        row.append(ir.to_code(ir.deriv(eq.residual, ir.Var(name, 0)), leaf))
                    rows.append("[" + ", ".join(row) + "]")
                fn = eval("lambda V: [" + ", ".join(rows) + "]", dict(ir.RUNTIME))  # noqa: S307 — 검증된 IR에서 만든 식(색인만)
            except Exception:  # noqa: BLE001 — 계수가 든 항등식 등은 보지 않는다
                continue
            deficient, null = 0, None
            for _ in range(2):
                V = rng.uniform(0.5, 1.5, max(len(keys), 1))
                try:
                    with np.errstate(all="ignore"):
                        M = np.array(fn(V), dtype=float)
                except ir.EVAL_ERRORS:
                    break
                if not np.all(np.isfinite(M)):
                    break
                r = np.max(np.abs(M), axis=1)
                r[r == 0] = 1.0
                M = M / r[:, None]
                c = np.max(np.abs(M), axis=0)
                c[c == 0] = 1.0
                M = M / c[None, :]
                U, s, _ = np.linalg.svd(M)
                rank = int(np.sum(s > 1e-9 * max(s[0] if len(s) else 0.0, 1e-300)))
                if rank >= len(ids):
                    break
                deficient += 1
                null = U[:, rank:]
            if deficient == 2 and null is not None:
                who = [ids[i] for i in range(len(ids)) if np.max(np.abs(null[i])) > 1e-8]
                out.append({"block": k, "variables": [self.var_names[j] for j in b.vars],
                            "identities": [self.eqs[e].label for e in (who or ids)]})
        return out

    def _build(self, active: FrozenSet[int], unknowns: FrozenSet[int]) -> Structure:
        if len(active) != len(unknowns):
            raise StructureError(
                f"식 수({len(active)}) ≠ 미지수 수({len(unknowns)}) — 정방 시스템이 아닙니다.")
        match = self._match(sorted(active), unknowns)
        blocks = self._blocks(sorted(active), match)
        return Structure(active, unknowns, blocks, match)

    def _match(self, eqs: List[int], unknowns: FrozenSet[int]) -> Dict[int, int]:
        """식 → 미지수 완전 매칭(Kuhn). 목표변수를 우선 시도한다."""
        cand = {}
        for e in eqs:
            vs = self.incidence[e] & unknowns
            pref = self.var_index[self.eqs[e].target]
            cand[e] = ([pref] if pref in vs else []) + sorted(vs - {pref})
        owner: Dict[int, int] = {}

        def augment(e, seen):
            for v in cand[e]:
                if v in seen:
                    continue
                seen.add(v)
                if v not in owner or augment(owner[v], seen):
                    owner[v] = e
                    return True
            return False

        # 목표변수가 미지수인 식부터 직접 배정(대부분 여기서 끝남)
        for e in eqs:
            pref = self.var_index[self.eqs[e].target]
            if cand[e] and cand[e][0] == pref and pref not in owner:
                owner[pref] = e
        assigned = set(owner.values())
        for e in eqs:
            if e not in assigned and not augment(e, set()):
                free_vars = sorted(unknowns - set(owner))
                raise StructureError(
                    "구조적으로 풀 수 없는 시스템입니다(정규화 매칭 실패): "
                    f"식 '{self.eqs[e].label}'에 배정할 미지수가 없습니다. "
                    f"남은 미지수: {[self.var_names[v] for v in free_vars][:8]}")
            assigned = set(owner.values())
        return {e: v for v, e in owner.items()}

    def _blocks(self, eqs: List[int], match: Dict[int, int]) -> List[Block]:
        """의존 그래프(식 e가 다른 식 e'의 매칭 변수를 현시점에 사용) → SCC(Tarjan, 반복형)."""
        var_owner = {v: e for e, v in match.items()}
        succ = {e: sorted({var_owner[v] for v in self.incidence[e] if v in var_owner} - {e})
                for e in eqs}
        index, low, on, stack, out = {}, {}, set(), [], []
        counter = 0
        for root in eqs:
            if root in index:
                continue
            work = [(root, 0)]
            while work:
                v, i = work.pop()
                if i == 0:
                    index[v] = low[v] = counter
                    counter += 1
                    stack.append(v)
                    on.add(v)
                recurse = False
                nbrs = succ[v]
                while i < len(nbrs):
                    w = nbrs[i]
                    i += 1
                    if w not in index:
                        work.append((v, i))
                        work.append((w, 0))
                        recurse = True
                        break
                    if w in on:
                        low[v] = min(low[v], index[w])
                if recurse:
                    continue
                if low[v] == index[v]:
                    comp = []
                    while True:
                        w = stack.pop()
                        on.discard(w)
                        comp.append(w)
                        if w == v:
                            break
                    out.append(sorted(comp))
                if work:
                    parent = work[-1][0]
                    low[parent] = min(low[parent], low[v])
        # Tarjan은 의존 대상(SCC)을 먼저 내보낸다 → 그대로 풀이 순서
        return [Block(eqs=c, vars=[match[e] for e in c]) for c in out]
