#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""버전 — 공개 버전은 패키지 버전 하나(`equion.__version__`, DECISIONS D18).

ENGINE_VERSION은 공개 버전이 아니라 **저장 형식 호환 표시**다: Work Table 번들·레거시 pickle·워크파일에
기록하고, 다시 읽을 때 엔진 세대가 같은지 확인하는 데만 쓴다.

엔진 세대
  3.0.0 (2026-10-29): 단일 DSL 파서(허용 목록 검증)·IR 전개·블록 분해·해석적 자코비안 Newton 솔버
          ·시나리오/전망/확률/control/MCE·TSLS/NLS/고정계수.
  2.0.0 (2026-04-18): AST 기반 수식 변환(정규식 대체).
"""

ENGINE_VERSION = "3.0.0"
__author__ = "samiblog"
__date__ = "2026-10-29"


def project_version() -> str:
    """패키지 버전 — 설치 메타데이터, 없으면 저장소의 VERSION 파일."""
    try:
        from importlib.metadata import version
        return version("equion")
    except Exception:  # noqa: BLE001 — 설치하지 않고 저장소에서 쓰는 경우
        import os
        p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "VERSION")
        try:
            with open(p, encoding="utf-8") as f:
                return f.read().strip()
        except OSError:
            return "unknown"


__version__ = project_version()


def version_text() -> str:
    return "\n".join(["=" * 60, f"Equion {__version__}  (엔진 세대 {ENGINE_VERSION.split('.')[0]}: "
                      "parser → IR → block solver)", "=" * 60])


def print_version():
    """버전 정보를 찍는다."""
    print(version_text())
