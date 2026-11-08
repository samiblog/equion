#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""하위호환 — 패키지 이름 변경(0.5.0: macromodel → equion) 이전에 저장한 레거시 pickle 읽기.

pickle은 클래스를 모듈 경로(예: `macromodel.estimation.equation.Equation`)로 기록하므로, 옛 경로를
새 패키지로 바꿔 찾는다. 레거시 pickle은 신뢰하는 파일만 열 것 — pickle은 열 때 코드를 실행할 수 있다.
"""

import pickle

_OLD = "macro" + "model"
_NEW = __name__.split(".")[0]


class _RenamingUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        if module == _OLD or module.startswith(_OLD + "."):
            module = _NEW + module[len(_OLD):]
        return super().find_class(module, name)


class PickleNotAllowed(ValueError):
    """레거시 pickle 열기가 허용되지 않음 — allow_pickle=True 또는 EQUION_ALLOW_PICKLE=1로만."""


def require_pickle_permission(path: str, allow: bool = False):
    """pickle은 열 때 임의 코드를 실행할 수 있다 — 명시적으로 허용했을 때만 연다(DECISIONS D18)."""
    import os
    if allow or os.environ.get("EQUION_ALLOW_PICKLE") == "1":
        return
    raise PickleNotAllowed(
        f"레거시 pickle 파일은 기본으로 열지 않습니다(열 때 코드가 실행될 수 있음): {path}\n"
        "  믿을 수 있는 파일이면: allow_pickle=True, 또는 명령줄 "
        "`equion convert <파일> <새 이름> --allow-pickle`로 안전한 워크파일(.eqw)로 바꾸세요.")


def load_pickle(f):
    """pickle.load 대신 — 옛 패키지 이름으로 저장된 객체도 읽는다."""
    return _RenamingUnpickler(f).load()
