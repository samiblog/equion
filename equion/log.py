#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""로그 — 라이브러리 안에서는 print 대신 logging을 쓴다(DECISIONS D18).

로거
    equion            전체(아래 둘의 부모)
    equion.engine     엔진 상세: 추정·풀이·번들·드라이버 진행 메시지
    equion.workfile   워크파일 API의 요약 한 줄(eqn.verbose(1) 이상에서)

기본으로 'equion' 로거에 표준출력 처리기를 하나 붙인다. 메시지만 찍고, 찍는 순간의 sys.stdout으로 보내므로
노트북·contextlib.redirect_stdout·CLI 로그 수집(run.log)과 그대로 맞물린다. 이 처리기를 떼고 애플리케이션의
logging 설정을 따르게 하려면 `eqn.log.use_own_handler(False)`.
"""

import contextlib
import logging
import sys

logger = logging.getLogger("equion")
engine = logging.getLogger("equion.engine")
workfile = logging.getLogger("equion.workfile")


class _StdoutHandler(logging.Handler):
    """찍는 순간의 sys.stdout으로 메시지만 쓴다."""

    def emit(self, record):
        try:
            msg = self.format(record) + "\n"
            out = sys.stdout
            try:
                out.write(msg)
            except UnicodeEncodeError:  # UTF-8이 아닌 파이프(Windows cp949·cp1252): 없는 문자만 \\uXXXX로
                enc = getattr(out, "encoding", None) or "ascii"
                out.write(msg.encode(enc, "backslashreplace").decode(enc))
        except Exception:  # noqa: BLE001 — logging 규약
            self.handleError(record)


_handler = _StdoutHandler()
_handler.setFormatter(logging.Formatter("%(message)s"))


def use_own_handler(on: bool = True):
    """True(기본): Equion의 표준출력 처리기를 쓴다. False: 떼고 상위(root) logging 설정으로 넘긴다."""
    if on:
        if _handler not in logger.handlers:
            logger.addHandler(_handler)
        logger.propagate = False
    else:
        if _handler in logger.handlers:
            logger.removeHandler(_handler)
        logger.propagate = True


def set_level(level):
    """'equion' 로거 수준(logging.INFO·'WARNING' 등)."""
    logger.setLevel(level)


@contextlib.contextmanager
def silenced(log: logging.Logger = engine, level: int = logging.WARNING):
    """잠시 로거 수준을 올려 메시지를 감춘다(경고 이상은 그대로)."""
    old = log.level
    log.setLevel(level)
    try:
        yield
    finally:
        log.setLevel(old)


logger.setLevel(logging.INFO)
use_own_handler(True)
