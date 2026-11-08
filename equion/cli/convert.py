#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`equion convert` — 옛 저장 형식을 워크파일(.eqw)로 바꾼다.

받는 것: 레거시 Work Table pickle(파일 — --allow-pickle 필요), Work Table 번들(.wt/), 옛 워크파일(.mmw/),
워크파일(.eqw/), 데이터 파일(xlsx/csv). 결과는 pickle 없는 워크파일 폴더(.eqw/)다.
"""

import os


def convert(src: str, dst: str, allow_pickle: bool = False, name: str = None) -> str:
    from ..workfile import output as _output
    from ..workfile.workfile import _from_worktable, wfopen
    p = src.rstrip("/\\")
    if not os.path.exists(p) and not any(os.path.isdir(p + ext) for ext in (".eqw", ".mmw", ".wt")):
        raise FileNotFoundError(f"없는 경로: {src}")
    old = _output.verbose()
    _output.verbose(0)
    try:
        if os.path.isfile(p) and not p.lower().endswith((".xlsx", ".xls", ".csv")):
            wf = _from_worktable(p, name, allow_pickle=allow_pickle)     # 레거시 pickle
        else:
            wf = wfopen(p, name=name)
        out = wf.save(dst)
    finally:
        _output.verbose(old)
    return out
