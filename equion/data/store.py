#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""표 저장 — 워크파일(.eqw)·Work Table 번들(.wt)의 시계열 표를 numpy 압축 파일(.npz)로 (DECISIONS D18).

- 숫자 열만(시계열 표는 모두 float). 인덱스는 날짜(ns 정수)·정수·문자열을 그대로 되살린다.
- 읽을 때 `allow_pickle=False` — 파일을 열어도 코드가 실행되지 않는다.
- 0.6.0까지의 parquet(`*.parquet`)도 읽는다(pyarrow가 있을 때 — `pip install equion[parquet]`).
"""

import os

import numpy as np
import pandas as pd


def write_frame(directory: str, stem: str, df: pd.DataFrame) -> str:
    """df → directory/stem.npz. 숫자가 아닌 열이 있으면 오류."""
    values = df.to_numpy(dtype=float) if len(df.columns) else np.empty((len(df), 0))
    idx = df.index
    unit = ""
    if isinstance(idx, pd.DatetimeIndex):
        unit = np.datetime_data(idx.dtype)[0]       # pandas 3은 'us', 2는 'ns' — 단위를 함께 저장
        kind, raw = "datetime", idx.asi8
    elif pd.api.types.is_integer_dtype(idx):
        kind, raw = "int", np.asarray(idx, dtype=np.int64)
    else:
        kind, raw = "str", np.asarray([str(v) for v in idx], dtype=str)
    path = os.path.join(directory, f"{stem}.npz")
    np.savez_compressed(path, values=values, index=raw, index_kind=np.asarray(kind), index_unit=np.asarray(unit),
                        columns=np.asarray([str(c) for c in df.columns], dtype=str),
                        index_name=np.asarray("" if idx.name is None else str(idx.name)))
    return path


def read_frame(directory: str, stem: str):
    """directory/stem.npz(없으면 stem.parquet) → DataFrame. 둘 다 없으면 None."""
    path = os.path.join(directory, f"{stem}.npz")
    if os.path.exists(path):
        with np.load(path, allow_pickle=False) as z:
            kind = str(z["index_kind"])
            raw = z["index"]
            if kind == "datetime":
                unit = str(z["index_unit"]) if "index_unit" in z.files else "ns"
                idx = pd.DatetimeIndex(raw.astype(f"datetime64[{unit or 'ns'}]"))
            elif kind == "int":
                idx = pd.Index(raw.astype(np.int64))
            else:
                idx = pd.Index([str(v) for v in raw])
            name = str(z["index_name"])
            idx.name = name or None
            return pd.DataFrame(z["values"], index=idx, columns=[str(c) for c in z["columns"]])
    legacy = os.path.join(directory, f"{stem}.parquet")
    if os.path.exists(legacy):
        try:
            return pd.read_parquet(legacy)
        except ImportError as e:
            raise ImportError(f"{legacy}는 0.6.0까지의 parquet 형식입니다 — pyarrow가 필요합니다: "
                              "pip install pyarrow (선택 기능 equion[parquet]) — 또는 pyarrow가 있는 곳에서 equion convert로 새 형식으로") from e
    return None
