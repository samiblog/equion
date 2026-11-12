#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""데이터 파일 입출력 — 파일 포맷 지식을 한곳에 격리한다.

xlsx/csv 등 포맷 판별·읽기를 담당하며, Data(메모리상 관리)와 분리되어 있다.
새 포맷(예: parquet 원천, DB 적재)을 추가할 때 이 모듈만 손대면 된다.
(구 Data.load의 파일 읽기 부분. 로직 무변경.)
"""

import os

import numpy as np
import pandas as pd

from ..log import engine as _log


def read_text(path: str) -> str:
    """사람이 쓰는 텍스트 파일(방정식 파일 등)을 읽는다. UTF-8(BOM 있어도 됨)을 먼저, 안 되면 cp949(한국어 Windows
    메모장의 'ANSI')로 읽고 경고한다. 둘 다 아니면 UTF-8로 저장하라고 알린다."""
    with open(path, "rb") as f:
        raw = f.read()
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        pass
    try:
        text = raw.decode("cp949")
    except UnicodeDecodeError:
        raise ValueError(f"{path}: 글자 인코딩을 읽을 수 없습니다 — UTF-8로 저장하세요") from None
    _log.warning(f"[WARN] {os.path.basename(path)}: UTF-8이 아니어서 cp949(ANSI)로 읽었습니다 — UTF-8로 저장하길 권합니다")
    return text


def read_dataframe(file_path: str, index_col: str = None) -> pd.DataFrame:
    """엑셀/CSV 파일을 읽어 (날짜 인덱스가 설정된) DataFrame을 반환한다.

    Args:
        file_path: 데이터 파일 경로 (.xlsx/.xls/.csv).
        index_col: 인덱스 컬럼명. None이면 첫 열을 날짜로 자동 감지.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"파일을 찾을 수 없습니다: {file_path}")

    ext = os.path.splitext(file_path)[1].lower()

    try:
        if ext in ['.xlsx', '.xls']:
            df = pd.read_excel(file_path)
        elif ext == '.csv':
            df = pd.read_csv(file_path)
        else:
            raise ValueError(f"지원하지 않는 파일 형식: {ext} (xlsx·xls·csv)")
    except pd.errors.EmptyDataError:
        raise ValueError(f"빈 파일입니다: {file_path}") from None

    # 인덱스 설정 — 날짜 해석은 periods.parse_dates(기간 라벨·연도·ISO 날짜, 형식 추측 없음)
    from .periods import parse_dates
    if df.empty and len(df.columns) == 0:
        raise ValueError(f"빈 파일입니다: {file_path}")
    col = index_col if index_col else df.columns[0]
    if index_col and index_col not in df.columns:
        raise ValueError(f"인덱스 열 '{index_col}'이(가) 없습니다: {list(df.columns)[:8]}")
    idx = parse_dates(df[col]) if len(df) else None
    if idx is not None:
        labels = [str(v) for v in df[col]]
        df = df.drop(columns=[col])
        df = _numeric_columns(df, labels, os.path.basename(file_path))
        df.index = idx.rename(str(col))
        if idx.has_duplicates:
            raise ValueError(f"같은 날짜가 두 번 있습니다: {idx[idx.duplicated()][0].date()} — {file_path}")
        if not idx.is_monotonic_increasing:
            df = df.sort_index()
    return df


MAX_LISTED_CELLS = 3        # 경고에 열마다 하나하나 적는 칸 수(나머지는 수만)
MAX_LISTED_COLUMNS = 8      # 경고에 적는 열 수


def _numeric_columns(df: pd.DataFrame, labels, fname: str) -> pd.DataFrame:
    """글자 칸이 섞인 열을 숫자 열로 — 숫자가 아닌 칸은 결측으로 읽고 칸(열·시점·값)을 경고로 알린다.

    원자료 불러오기 틀(data/source.py)과 같은 규칙이다. 그대로 두면 열 전체가 글자형으로 열려, 뒤의 추정·genr·검정이
    칸 위치 없이 'could not convert string to float'로 실패한다(조용히 잘못 읽는 것이 가장 나쁘다 — D62). 빈 칸과
    공백만 있는 칸은 그냥 결측이다."""
    from pandas.api.types import is_object_dtype, is_string_dtype
    mixed, whole = [], []        # 숫자가 섞인 열마다 '열: 칸 · 칸 외 n칸' · 숫자가 하나도 없는 열
    n_bad = 0
    out = {}
    for c in df.columns:
        s = df[c]
        if not (is_object_dtype(s.dtype) or is_string_dtype(s.dtype)):
            continue
        raw = s.astype(object).map(lambda v: (v.strip() or None) if isinstance(v, str) else v)
        num = pd.to_numeric(raw, errors="coerce").astype(float).to_numpy()
        out[c] = num
        pos = np.flatnonzero(raw.notna().to_numpy() & np.isnan(num))
        if not pos.size:
            continue
        n_bad += pos.size
        if np.isnan(num).all():
            whole.append(f"{c}({pos.size}칸)")
            continue
        shown = " · ".join(f"{labels[i]} {str(raw.iloc[i])[:20]!r}" for i in pos[:MAX_LISTED_CELLS])
        more = pos.size - MAX_LISTED_CELLS
        mixed.append(f"{c}: {shown}" + (f" 외 {more}칸" if more > 0 else ""))
    if not out:
        return df
    df = df.copy()
    for c, v in out.items():
        df[c] = v
    if n_bad:
        def listed(items):
            return " / ".join(items[:MAX_LISTED_COLUMNS]) + (f" / 외 {len(items) - MAX_LISTED_COLUMNS}열"
                                                              if len(items) > MAX_LISTED_COLUMNS else "")
        parts = ([listed(mixed)] if mixed else []) + (["숫자가 하나도 없는 열(모두 결측) " + listed(whole)] if whole else [])
        _log.warning(f"[WARN] {fname}: 숫자가 아닌 칸 {n_bad}개를 결측으로 읽었습니다 — " + " | ".join(parts)
                     + " (값이면 파일에서 숫자로 고치세요)")
    return df
