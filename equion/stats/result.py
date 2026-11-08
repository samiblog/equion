#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""검정 결과 객체 — 모든 진단·단위근 검정이 같은 모양으로 돌려준다."""

from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np
import pandas as pd


def _num(v, digits=4):
    if v is None:
        return ""
    if isinstance(v, (bool, np.bool_)):
        return "예" if v else "아니오"
    if isinstance(v, (int, np.integer)):
        return str(int(v))
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    if not np.isfinite(f):
        return "NA"
    if f != 0 and (abs(f) >= 1e6 or abs(f) < 1e-3):
        return f"{f:.{digits}e}"
    return f"{f:.{digits}f}"


@dataclass
class TestResult:
    """검정 결과.

    statistic·pvalue는 대표 통계량(예: LM, ADF t)과 p값, rows는 함께 보이는 보조 통계(이름 → 값),
    info는 머리에 보이는 설명(결정항·시차 선택·표본 등), details는 프로그램이 쓰는 값(lags·nobs·crit 등),
    table은 검정에 딸린 표(예: 시차별 Q, 순위별 Johansen),
    data는 보이지는 않는 뒷받침 자료(예: CUSUM 기간별 값), graph는 함께 보이는 그래프."""

    __test__ = False  # pytest가 이 클래스를 테스트로 모으지 않게

    name: str
    statistic: float
    pvalue: float
    null: str = ""
    rows: dict = field(default_factory=dict)
    info: dict = field(default_factory=dict)
    details: dict = field(default_factory=dict)
    table: Optional[pd.DataFrame] = None
    notes: list = field(default_factory=list)
    graph: Any = None
    data: Optional[pd.DataFrame] = None

    def reject(self, level: float = 0.05) -> Optional[bool]:
        """유의수준 level에서 귀무가설을 기각하는가(p값이 없으면 None)."""
        if self.pvalue is None or not np.isfinite(self.pvalue):
            return None
        return bool(self.pvalue < level)

    def frame(self) -> pd.DataFrame:
        """요약 표(항목 · 값)."""
        items = {"통계량": self.statistic}
        if self.pvalue is not None and np.isfinite(self.pvalue):
            items["p값"] = self.pvalue
        items.update(self.rows)
        return pd.DataFrame({"값": [_num(v) for v in items.values()]}, index=list(items))

    def output(self):
        from ..workfile.output import TableOutput
        head = [f"귀무가설: {self.null}"] if self.null else []
        head += [f"{k}: {_num(v) if not isinstance(v, str) else v}" for k, v in self.info.items()]
        body = self.table if self.table is not None else self.frame()
        foot = list(self.notes)
        if self.table is not None and self.pvalue is not None and np.isfinite(self.pvalue):
            extra = [" · ".join(f"{k} {_num(v) if not isinstance(v, str) else v}" for k, v in self.rows.items())]
            foot = [f"통계량 {_num(self.statistic)} · p값 {_num(self.pvalue)}"] + (extra if self.rows else []) + foot
        return TableOutput(body, title=self.name, head=head, foot=foot)

    def show(self):
        from ..workfile.output import spool
        spool.show(self.output())
        if self.graph is not None:
            spool.show(self.graph)

    def to_dict(self) -> dict:
        return {"name": self.name, "statistic": self.statistic, "pvalue": self.pvalue, "null": self.null,
                "rows": dict(self.rows), "info": dict(self.info), "details": dict(self.details)}

    def _repr_html_(self):
        return self.output().html()

    def __repr__(self):
        return f"<{self.name}: 통계량 {_num(self.statistic)}, p값 {_num(self.pvalue)}>"
