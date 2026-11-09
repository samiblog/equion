#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""항등식 단독 검사 — 실측으로 좌변과 우변을 계산해 견준다(계수가 없어 추정이 필요 없다)."""

from dataclasses import dataclass
from typing import List

import numpy as np
import pandas as pd

from ..formula import ir
from ..workfile.output import TableOutput, TextOutput
from .parts import Part


@dataclass
class IdentityCheck:
    """항등식 검사 결과 — `.ok`(허용오차 안에서 늘 성립), `.table`(기간·좌변·우변·차이·차이%), 통계."""

    part: Part
    start: str
    end: str
    tol: float
    table: pd.DataFrame          # 기간 라벨 인덱스: 좌변 · 우변 · 차이 · 차이%
    n: int                       # 두 쪽 다 값이 있는 기간 수
    n_missing: int               # 한쪽이라도 비어 계산하지 못한 기간 수
    mismatches: List[str]        # 허용오차를 넘은 기간

    @property
    def ok(self) -> bool:
        """비교한 모든 기간에서 |차이| ≤ tol·max(1, |좌변|)이면 참."""
        return self.n > 0 and not self.mismatches

    @property
    def max_abs(self) -> float:
        """가장 큰 |차이|."""
        d = self.table["차이"].abs()
        return float(d.max()) if d.notna().any() else float("nan")

    @property
    def max_pct(self) -> float:
        """가장 큰 |차이%|."""
        d = self.table["차이%"].abs()
        return float(d.max()) if d.notna().any() else float("nan")

    def text(self) -> str:
        """명령줄에 보이는 짧은 글."""
        p = self.part
        mark = "성립" if self.ok else ("비교할 기간 없음" if self.n == 0 else f"어긋남 {len(self.mismatches)}기")
        L = [f"[ident {p.id}] {p.text}   ({p.where})",
             f"  구간   {self.start}~{self.end} · 비교 {self.n}기" + (f" · 값 없음 {self.n_missing}기" if self.n_missing else ""),
             f"  결과   {mark} · 최대 |차이| {self.max_abs:.6g} · 최대 |차이%| {self.max_pct:.4g}%"]
        if self.mismatches:
            show = self.mismatches[:8]
            L.append("  어긋난 기간  " + ", ".join(show) + (" …" if len(self.mismatches) > 8 else ""))
        return "\n".join(L)

    def to_dict(self) -> dict:
        """명령줄 --json과 같은 사전."""
        return {"part": self.part.id, "where": self.part.where, "text": self.part.text, "start": self.start,
                "end": self.end, "ok": self.ok, "n": self.n, "n_missing": self.n_missing,
                "max_abs": None if np.isnan(self.max_abs) else self.max_abs,
                "max_pct": None if np.isnan(self.max_pct) else self.max_pct, "mismatches": self.mismatches,
                "tol": self.tol}

    def output(self) -> TableOutput:
        """기간별 표(좌변·우변·차이·차이%)."""
        return TableOutput(self.table, title=f"항등식 {self.part.id}", name=f"{self.part.block}_{self.part.target}_ident",
                           head=[self.part.text, f"최대 |차이| {self.max_abs:.6g} · 어긋남 {len(self.mismatches)}기"])

    def show(self):
        """짧은 글을 보인다."""
        from ..workfile.output import spool
        spool.show(TextOutput(self.text(), title=f"항등식 {self.part.id}"))

    def __repr__(self):
        return f"<항등식 검사 {self.part.id}: {'성립' if self.ok else '어긋남'} · 비교 {self.n}기>"


def check_identity(part: Part, data, start_idx: int, end_idx: int, label, tol: float = 1e-6) -> IdentityCheck:
    """실측으로 좌변·우변을 계산해 견준다. label(ts) → 기간 라벨."""
    if part.kind != "identity":
        raise ValueError(f"{part.id} — 항등식이 아니라 추정식입니다(항등식만 검사합니다)")
    df = data.data
    missing = sorted(v for v in ir.variables(part.lhs) | ir.variables(part.rhs) if v not in df.columns)
    if missing:
        raise ValueError(f"{part.id}: 자료에 없는 변수 {missing}")

    def get(name):
        return df[name].to_numpy(dtype=float)

    lhs = ir.evaluate(part.lhs, get, length=len(df))
    rhs = ir.evaluate(part.rhs, get, length=len(df))
    sl = slice(start_idx, end_idx + 1)
    idx = pd.Index([label(ts) for ts in df.index[sl]], name="기간")
    a, b = lhs[sl], rhs[sl]
    with np.errstate(all="ignore"):
        diff = a - b
        pct = np.where(a != 0, 100.0 * diff / np.abs(a), np.nan)
    table = pd.DataFrame({"좌변": a, "우변": b, "차이": diff, "차이%": pct}, index=idx)
    both = np.isfinite(a) & np.isfinite(b)
    bad = both & (np.abs(diff) > tol * np.maximum(1.0, np.abs(a)))
    return IdentityCheck(part=part, start=str(idx[0]) if len(idx) else "", end=str(idx[-1]) if len(idx) else "",
                         tol=tol, table=table, n=int(both.sum()), n_missing=int((~both).sum()),
                         mismatches=[str(x) for x in idx[bad]])
