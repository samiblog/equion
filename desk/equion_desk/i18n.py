"""화면에 나가는 서버 문구. 1차판은 한국어 화면만이라(D31 — 영문 화면은 2차판) 문장을 그대로 돌려준다.

Lectern에서 복사한 모듈(conpty·terminal)이 `t('문장 {이름}', 이름=값)` 꼴로 부르므로 같은 모양을 지킨다 —
영문 화면을 더할 때 여기에 번역표만 넣으면 된다.
"""
from __future__ import annotations

from typing import Any


def t(text: str, **slots: Any) -> str:
    """문구에 값을 끼워 돌려준다. `t('{what} 실패: {error}', what='열기', error=exc)`."""
    return text.format(**slots) if slots else text


def N_(text: str) -> str:
    """나중에 `t()`로 옮길 문구를 표시만 한다(값은 그대로)."""
    return text
