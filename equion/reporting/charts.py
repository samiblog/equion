#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""결과 시각화·요약 — 노트북·드라이버가 소비하는 표시 계층.

현재는 Model의 표시 메서드(show_hs_summary / compare_and_plot)에 위임하는
파사드다. 차트 로직을 Model에서 이쪽으로 완전히 이관하는 것은 후속 단계이며,
이 모듈이 그 지정석이다.
"""

import pandas as pd


def show_hs_summary(model, hs_id: str = None, top_n: int = 20):
    """HS 적합도 요약 (구현: Model.show_hs_summary)."""
    return model.show_hs_summary(hs_id=hs_id, top_n=top_n)


def compare_and_plot(model, *args, **kwargs):
    """실측 vs HS 비교 플롯 (구현: Model.compare_and_plot)."""
    return model.compare_and_plot(*args, **kwargs)


def hs_dataframe(model, hs_id: str) -> pd.DataFrame:
    """HS 결과를 tidy DataFrame으로 — 차트·외부 분석용 단일 진입점.

    열: period, variable, hs, actual, error_pct
    """
    if hs_id not in model.hs_solutions:
        raise KeyError(f"hs_id '{hs_id}' 결과가 없습니다.")
    rows = []
    sol = model.hs_solutions[hs_id]
    for t in sorted(sol.keys()):
        period = model._period_label(model.data.data.index[t])
        for var, val in sol[t].items():
            actual = None
            if var in model.data.data.columns:
                try:
                    actual = float(model.data.data.iloc[t][var])
                except Exception:
                    actual = None
            err = ((val - actual) / actual * 100) if (actual not in (None, 0)) else None
            rows.append({"period": period, "variable": var,
                         "hs": val, "actual": actual, "error_pct": err})
    return pd.DataFrame(rows)
