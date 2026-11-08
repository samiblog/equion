#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_docs.py — 문서가 실제로 돌아가는지(docs/build_docs.py --check).

실행: uv run python tests/test_docs.py   (종료코드 = 문제가 있으면 1)

  · 사용자 문서(docs/start·tutorial·howto·explain·reference·cases·en, README)의 python 예제를 차례로 실행
  · 문서에 적힌 출력과 실행 출력 비교(uv.lock의 numpy·pandas일 때 — 다른 판은 실행만)
  · examples/(스크립트·노트북)가 문서에서 만든 것과 같은지
  · 문서 사이 링크·앵커
  · 공개 API의 설명·예제 유무와 docstring 예제(doctest)
API 참조(docs/reference/api.md)가 코드와 같은지는 CI의 make_api --check가 본다(Python 판마다 서명 표기가 같은 한 곳에서).
"""

import os
import sys
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "docs"))
sys.path.insert(0, ROOT)

import build_docs  # noqa: E402


def main():
    return build_docs.main(["--check"])


def test_suite():
    """pytest 진입점 — `python tests/test_docs.py`와 같은 검사."""
    assert main() == 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(99)
