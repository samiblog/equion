#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""방정식 파일 파서 + (하위호환) 주기 함수 재노출 — 주기·기간 연산 본체는 equion.data.periods.
"""

import os

from ..formula.ast_formula import expand_macros


# 기간·주기 함수는 equion.data.periods로 옮겼다 — 기존 import 경로를 위해 같은 이름으로 다시 내보낸다.
from ..data.periods import (  # noqa: E402,F401
    FREQ_ALIASES as _FREQ_ALIASES,
    FREQ_LABEL as _FREQ_LABEL,
    PERIOD_FREQ as _PERIOD_FREQ,
    RESAMPLE_RULE as _RESAMPLE_RULE,
    format_period,
    infer_freq_code,
    normalize_freq,
    parse_period,
    to_period,
)


# ============================================================================
# 방정식 파일 파서(로더의 정식 위치)
# ============================================================================

def parse_equation_file(file_path: str):
    """equations 텍스트 파일을 (추정식 리스트, 항등식 리스트)로 파싱한다.

    처리: ① 인라인/전체 주석(#) 제거 → ② @def 매크로 전개 →
    ③ 분류: 최상위 `=`가 있고 계수 c(n)이 없으면 항등식, 그 외(등호 없음 또는
       c(n) 계수식=NLS)는 추정식. 등호 양옆 공백은 상관없다.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"방정식 파일을 찾을 수 없습니다: {file_path}")

    from ..data.io import read_text
    raw_lines = []
    for line in read_text(file_path).splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            raw_lines.append(line)

    expanded = expand_macros(raw_lines)

    from ..formula.parser import is_identity
    estimated, identities = [], []
    for line in expanded:
        (identities if is_identity(line) else estimated).append(line)
    return estimated, identities
