#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""조립 — 모형 = 블록과 다른 모형을 이름으로 끼운 것. 추정하지 않고 구조만 검사한다 (D32).

조립 규칙
    1. 내생·외생은 변수에 적지 않는다 — 어떤 식의 목표변수면 내생, 아니면 외생.
    2. 한 모형에 같은 목표변수는 하나 — 겹치면 문제(어느 블록의 몇째 줄인지).
    3. 자료에도 없고 어떤 식도 정하지 않는 변수는 문제(어느 식이 쓰는지).
    4. 모형은 부품을 이름으로 가리킨다 — include한 모형의 부품도 함께, exclude(블록:목표)로 뺀 식의 목표는 외생(실측)이 된다.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from ..system.analyzer import ModelSystem, StructureError, SystemEquation
from ..workfile.output import TableOutput, TextOutput
from .config import ProjectConfig
from .parts import Part


@dataclass
class AssemblyReport:
    """조립 검사 결과 — 계산 없이 모형의 구조를 본다. `.ok`가 거짓이면 `.problems`에 무엇이 어디서 틀렸는지."""

    model: str
    desc: str
    composition: str                    # main = core(demand) + price + finance
    parts: List[Part]
    excluded: List[str]
    endogenous: List[str]
    exogenous: List[str]
    exo_info: Dict[str, dict]           # 외생 → {in_data, first, last}
    links: List[Tuple[str, str, str]]   # (정하는 블록, 변수, 쓰는 블록)
    blocks: List[dict]                  # 풀이 블록 구조(문제가 없을 때)
    problems: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """문제가 없으면 참."""
        return not self.problems

    @property
    def n_equations(self) -> int:
        """추정식 수."""
        return sum(1 for p in self.parts if p.kind == "equation")

    @property
    def n_identities(self) -> int:
        """항등식 수."""
        return sum(1 for p in self.parts if p.kind == "identity")

    def text(self) -> str:
        """명령줄에 보이는 짧은 글."""
        L = [f"[assemble {self.model}] {self.desc + ' — ' if self.desc else ''}"
             f"블록 {len({p.block for p in self.parts})} · 추정식 {self.n_equations} · 항등식 {self.n_identities}",
             f"  조립   {self.composition}"]
        if self.excluded:
            L.append(f"  뺀 식  {' · '.join(self.excluded)} (목표는 실측으로)")
        L.append(f"  내생 {len(self.endogenous)}  " + " · ".join(self.endogenous))
        ex = []
        for v in self.exogenous:
            info = self.exo_info.get(v, {})
            if not info.get("in_data"):
                ex.append(f"{v}(자료 없음)")
            elif info.get("last"):
                ex.append(f"{v}(~{info['last']})")
            else:
                ex.append(v)
        L.append(f"  외생 {len(self.exogenous)}  " + (" · ".join(ex) if ex else "없음"))
        if self.links:
            L.append("  연결   " + " · ".join(f"{a} →{v}→ {b}" for a, v, b in self.links))
        if self.blocks:
            sim = [b for b in self.blocks if b["size"] > 1]
            line = f"  풀이   블록 {len(self.blocks)}"
            if sim:
                line += " (동시 " + ", ".join("·".join(b["variables"][:6]) + ("…" if b["size"] > 6 else "")
                                            for b in sim) + ")"
            L.append(line)
        for w in self.warnings:
            L.append(f"  주의   {w}")
        if self.problems:
            L.append(f"  문제 {len(self.problems)}")
            L += [f"    - {p}" for p in self.problems]
        else:
            L.append("  문제   없음")
        return "\n".join(L)

    def to_dict(self) -> dict:
        """명령줄 --json과 같은 사전."""
        return {
            "model": self.model, "desc": self.desc, "ok": self.ok, "composition": self.composition,
            "parts": [{"id": p.id, "kind": p.kind, "where": p.where, "text": p.text, "desc": p.desc} for p in self.parts],
            "excluded": self.excluded, "endogenous": self.endogenous, "exogenous": self.exogenous,
            "exogenous_data": self.exo_info, "links": [list(x) for x in self.links],
            "blocks": self.blocks, "problems": self.problems, "warnings": self.warnings,
        }

    def output(self) -> TableOutput:
        """부품 표(부품·종류·위치·식·설명)."""
        df = pd.DataFrame([{"부품": p.id, "종류": "항등식" if p.kind == "identity" else "추정식", "위치": p.where,
                            "식": p.text, "설명": p.desc} for p in self.parts],
                          columns=["부품", "종류", "위치", "식", "설명"])
        head = [f"조립 {self.composition}", f"내생 {len(self.endogenous)} · 외생 {len(self.exogenous)} · "
                f"문제 {len(self.problems)}"]
        return TableOutput(df, title=f"모형 {self.model} 조립", index=False, name=f"{self.model}_assembly", head=head)

    def show(self):
        """짧은 글을 보인다."""
        from ..workfile.output import spool
        spool.show(TextOutput(self.text(), title=f"모형 {self.model} 조립"))

    def __repr__(self):
        return f"<조립 {self.model}: 식 {len(self.parts)} · 문제 {len(self.problems)}>"


def composition(cfg: ProjectConfig, name: str) -> str:
    """'main = core(demand) + price + finance' 꼴."""
    def inner(m, seen):
        spec = cfg.models.get(m)
        if spec is None or m in seen:
            return m
        return " + ".join([f"{inc}({inner(inc, seen | {m})})" for inc in spec.include] + list(spec.blocks))
    return f"{name} = {inner(name, set())}"


def resolve(cfg: ProjectConfig, parts_by_block: Dict[str, List[Part]], name: str) -> Tuple[List[Part], List[str], List[str]]:
    """모형(또는 블록) 이름 → (부품 목록, 뺀 부품 이름, 문제). 같은 부품이 여러 길로 들어오면 한 번만."""
    problems: List[str] = []
    if name in cfg.blocks:
        return list(parts_by_block.get(name, [])), [], problems
    if name not in cfg.models:
        raise KeyError(f"없는 모형·블록: {name} (모형: {', '.join(cfg.models) or '없음'} · 블록: {', '.join(cfg.blocks) or '없음'})")
    excluded: List[str] = []

    def expand(m, stack) -> List[Part]:
        spec = cfg.models[m]
        out: List[Part] = []
        for inc in spec.include:
            if inc in stack:
                continue                    # 순환은 설정 검사가 이미 알렸다
            out += expand(inc, stack + [inc])
        for b in spec.blocks:
            out += parts_by_block.get(b, [])
        ids = {p.id for p in out}
        for x in spec.exclude:
            blk, _, tgt = x.partition(":")
            match = [p for p in out if p.block == blk and p.target.lower() == tgt.lower()]
            if not match:
                problems.append(f"[model.{m}] exclude '{x}': 이 모형에 그런 식이 없습니다"
                                f"(있는 식: {', '.join(sorted(ids))[:200]})")
                continue
            excluded.extend(p.id for p in match)
            out = [p for p in out if p not in match]
        return out

    seen, parts = set(), []
    for p in expand(name, [name]):
        if (p.block, p.line) not in seen:
            seen.add((p.block, p.line))
            parts.append(p)
    return parts, excluded, problems


def check(cfg: ProjectConfig, parts_by_block: Dict[str, List[Part]], name: str, data) -> AssemblyReport:
    """조립 검사 — 겹친 목표·모르는 변수·외생 자료 끝·블록 사이 연결·풀이 블록 구조."""
    parts, excluded, problems = resolve(cfg, parts_by_block, name)
    desc = cfg.models[name].desc if name in cfg.models else cfg.blocks[name].desc
    comp = composition(cfg, name) if name in cfg.models else f"{name} (블록 하나 — 나머지 변수는 실측)"
    warnings: List[str] = []

    # 2. 겹친 목표
    by_target: Dict[str, List[Part]] = {}
    for p in parts:
        by_target.setdefault(p.target, []).append(p)
    for t, ps in by_target.items():
        if len(ps) > 1:
            problems.append(f"목표 겹침 {t}: " + " · ".join(f"{p.id} ({p.where})" for p in ps)
                            + " — 한 모형에 같은 목표는 하나(하나를 exclude로 빼거나 블록을 나누세요)")
    targets = list(dict.fromkeys(p.target for p in parts))
    endo = set(targets)

    # 3. 모르는 변수
    cols = set(data.data.columns) if data is not None else set()
    used_by: Dict[str, List[str]] = {}
    for p in parts:
        for v in sorted(p.data_vars | p.variables):
            if v not in endo and v not in cols:
                used_by.setdefault(v, []).append(p.id)
    for v, users in sorted(used_by.items()):
        problems.append(f"모르는 변수 {v} — 자료에도 없고 어떤 식도 정하지 않습니다(쓰는 식: {', '.join(users[:4])})")

    # 외생과 자료 끝
    referenced = set()
    for p in parts:
        referenced |= p.variables
    exo = sorted(referenced - endo)
    exo_info: Dict[str, dict] = {}
    df = data.data if data is not None else None
    ind = set(getattr(data, "indicators", {}) or {}) if data is not None else set()
    for v in exo:
        if df is not None and v in df.columns:
            s = df[v]
            valid = s[np.isfinite(s.to_numpy(dtype=float))] if len(s) else s
            lab = (lambda ts: _label(data, ts))
            exo_info[v] = {"in_data": True, "indicator": v in ind,
                           "first": lab(valid.index[0]) if len(valid) else None,
                           "last": lab(valid.index[-1]) if len(valid) else None}
        else:
            exo_info[v] = {"in_data": False}
    lasts = {v: i["last"] for v, i in exo_info.items() if i.get("last") and not i.get("indicator")}
    if lasts and df is not None:
        latest = max(lasts.values(), key=lambda lab: _pos(data, lab))
        early = sorted(v for v, lab in lasts.items() if _pos(data, lab) < _pos(data, latest))
        if early:
            warnings.append("자료가 일찍 끝나는 외생: " + " · ".join(f"{v}(~{lasts[v]})" for v in early)
                            + f" — 다른 외생은 {latest}까지")

    # 블록 사이 연결(정하는 블록 →변수→ 쓰는 블록)
    owner = {p.target: p.block for p in parts}
    links = []
    for p in parts:
        for v in sorted(p.variables):
            b = owner.get(v)
            if b and b != p.block and (b, v, p.block) not in links:
                links.append((b, v, p.block))

    # 풀이 블록 구조
    blocks: List[dict] = []
    if not problems and parts:
        eqs = [SystemEquation(index=i, kind="identity" if p.kind == "identity" else "behavioral",
                              label=p.id, target=p.target, lhs=p.lhs, rhs=p.rhs, source=p)
               for i, p in enumerate(parts)]
        try:
            system = ModelSystem(eqs, list(cols) + targets)
            for b in system.structure().describe(system):
                blocks.append({"block": b["block"], "type": "동시" if b["size"] > 1 else "순차",
                               "size": b["size"], "variables": list(b["variables"])})
        except StructureError as e:
            problems.append(f"구조: {e}")
    return AssemblyReport(model=name, desc=desc, composition=comp, parts=parts, excluded=excluded,
                          endogenous=targets, exogenous=exo, exo_info=exo_info, links=links, blocks=blocks,
                          problems=problems, warnings=warnings)


def _label(data, ts) -> str:
    from ..data.periods import format_period
    try:
        return format_period(ts, data.freq)
    except Exception:  # noqa: BLE001
        return str(ts)[:10]


def _pos(data, label) -> int:
    from ..data.periods import locate
    try:
        return locate(data.data.index, label, data.freq)
    except ValueError:
        return -1
