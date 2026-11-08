#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""번들 직렬화용 JSON 헬퍼 (numpy/pandas 스칼라 변환·중첩 키 변환).

(구 worktable.py에서 분리. 로직 무변경.)
"""

import os
import json
import glob

import numpy as np


def _jsonable(obj):
    """numpy/pandas 스칼라를 순정 파이썬 타입으로 변환(재귀).

    NaN/Inf는 그대로 보존한다(라운드트립 충실도). Python json은 기본
    allow_nan=True 라 NaN/Infinity 토큰으로 쓰고 다시 읽으므로, 복원된 상태가
    저장 전과 동일하게 동작한다(예: 0 근처 계열의 RMSPE=nan).
    """
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return [_jsonable(v) for v in obj.tolist()]
    return obj


def _nested_int_to_str(d):
    """{id: {time_index(int): {var: val}}} → time_index를 문자열 키로."""
    out = {}
    for rid, by_t in d.items():
        out[rid] = {str(t): _jsonable(sol) for t, sol in by_t.items()}
    return out


def _nested_str_to_int(d):
    out = {}
    for rid, by_t in d.items():
        out[rid] = {int(t): sol for t, sol in by_t.items()}
    return out


def _write_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def _read_json(path):
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _dir_size(path):
    total = 0
    for f in glob.glob(os.path.join(path, "**", "*"), recursive=True):
        if os.path.isfile(f):
            total += os.path.getsize(f)
    return total
