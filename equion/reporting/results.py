#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""결과 저장(CSV) — solve/HS 결과를 표 형태로 내보낸다.

드라이버·외부 분석이 소비하는 결과 출력 계층. Model의 수치 상태(solutions /
hs_solutions)를 인자로 받아 파일로 직렬화하며, 수치 코어와 분리되어 있다.
엔진 v3: 기간별 풀이 상태(status·반복·잔차·제외/대체 변수) 열을 함께 저장한다.
  status: ok | partial(입력 결측으로 일부 식 제외) | fallback(블록 실패 → 실측 대체) | failed
"""

import os
import pandas as pd
from ..log import engine as _log


def _status_cols(status_by_t, t):
    st = (status_by_t or {}).get(t)
    if not st:
        return {}
    return {
        'status': st.get('status'),
        'iterations': st.get('iterations'),
        'max_resid': st.get('max_resid'),
        'excluded': "; ".join(st.get('excluded') or []),
        'fallback': ", ".join(st.get('fallback') or []),
    }


def save_solve_results(model, solve_id: str, output_file: str = None, include_all_vars: bool = True):
    """solve 결과를 CSV 파일로 저장"""
    if solve_id not in model.solutions:
        _log.info(f"[ERROR] solve_id '{solve_id}'의 결과가 없습니다!")
        return None

    if output_file is None:
        indices = sorted(model.solutions[solve_id].keys())
        sp = model.data.data.index[indices[0]]
        ep = model.data.data.index[indices[-1]]
        if sp == ep:
            output_file = os.path.join("HS", f"{solve_id}_results_{model._period_label(sp)}.csv")
        else:
            output_file = os.path.join("HS", f"{solve_id}_results_{model._period_label(sp)}_{model._period_label(ep)}.csv")
    else:
        if not os.path.dirname(output_file) and not output_file.startswith("HS") and not os.path.isabs(output_file):
             output_file = os.path.join("HS", output_file)

    results_list = []
    vars_to_save = model.endogenous_vars if include_all_vars else model.endogenous_vars[:10]

    for time_index in sorted(model.solutions[solve_id].keys()):
        p = model.data.data.index[time_index]
        row = {'period': model._period_label(p), 'time_index': time_index}
        row.update(_status_cols(getattr(model, 'solve_status', {}).get(solve_id), time_index))

        for var_name in vars_to_save:
            if var_name in model.solutions[solve_id][time_index]:
                sol_val = model.solutions[solve_id][time_index][var_name]
                row[f'{var_name}_solve'] = sol_val
                if var_name in model.data.data.columns:
                    try:
                        actual = model.data.data.iloc[time_index][var_name]
                        row[f'{var_name}_actual'] = actual
                        if actual != 0:
                            row[f'{var_name}_error_pct'] = (sol_val - actual) / actual * 100
                    except Exception:
                        pass

        results_list.append(row)

    df = pd.DataFrame(results_list)
    df.to_csv(output_file, index=False, encoding='utf-8-sig')
    _log.info(f"[OK] solve 결과 저장: {output_file} ({len(df)}행)")
    return output_file


def save_hs_results(model, hs_id: str, output_file: str = None, include_all_vars: bool = True):
    """HS 결과를 CSV 파일로 저장"""
    if hs_id not in model.hs_solutions:
        _log.info(f"[ERROR] hs_id '{hs_id}'의 결과가 없습니다!")
        return None

    if output_file is None:
        indices = sorted(model.hs_solutions[hs_id].keys())
        sp = model.data.data.index[indices[0]]
        ep = model.data.data.index[indices[-1]]
        output_file = os.path.join("HS", f"{hs_id}_results_{model._period_label(sp)}_{model._period_label(ep)}.csv")
    else:
        if not os.path.dirname(output_file) and not output_file.startswith("HS") and not os.path.isabs(output_file):
             output_file = os.path.join("HS", output_file)

    results_list = []
    vars_to_save = model.endogenous_vars if include_all_vars else model.endogenous_vars[:10]

    for time_index in sorted(model.hs_solutions[hs_id].keys()):
        p = model.data.data.index[time_index]
        row = {'period': model._period_label(p), 'time_index': time_index}
        row.update(_status_cols(getattr(model, 'hs_status', {}).get(hs_id), time_index))

        for var_name in vars_to_save:
            if var_name in model.hs_solutions[hs_id][time_index]:
                hs_val = model.hs_solutions[hs_id][time_index][var_name]
                row[f'{var_name}_hs'] = hs_val
                if var_name in model.data.data.columns:
                    try:
                        actual = model.data.data.iloc[time_index][var_name]
                        row[f'{var_name}_actual'] = actual
                        if actual != 0:
                            row[f'{var_name}_error_pct'] = (hs_val - actual) / actual * 100
                    except Exception:
                        pass

        results_list.append(row)

    df = pd.DataFrame(results_list)
    if os.path.dirname(output_file):
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
    df.to_csv(output_file, index=False, encoding='utf-8-sig')
    _log.info(f"[OK] HS 결과 저장: {output_file} ({len(df)}행)")
    return output_file
