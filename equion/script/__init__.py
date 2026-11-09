#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Equion 스크립트(`.eqs`, D36) — 원자료에서 보고서까지 한 번에 다시 하는 단위. 한 줄이 `equion` 명령 하나다.

    equion run FLOWS/monthly.eqs [--set 이름=값] [--from 단계·제목] [--dry-run]   실행 → 실행 기록 work/run/<이름>/ (run:)
    equion run --replay run:monthly_0001                                          그때 그대로 다시 — 단계마다 같음·다름
    equion check FLOWS/monthly.eqs                                                실행 없이 검사
    equion script new 이름 --from-records 기록…                                   작업 기록으로 초안 · script export x.eqs --py

문법은 `equion.script.language`, 실행은 `Session`(내보낸 Python도 이것을 쓴다).
"""

from .export import draft, export_py, new_script, to_python
from .language import BUILTINS, FORMAT, FORMAT_VERSION, Script, ScriptError, Step, parse, resolve
from .record import RunResult
from .runner import Plan, ReplayResult, ScriptCheck, check, plan, replay, run_script
from .session import ScriptStop, Session, StepResult, session

__all__ = ["Session", "session", "Script", "Step", "StepResult", "ScriptStop", "ScriptError", "RunResult", "Plan",
           "ScriptCheck", "ReplayResult", "parse", "resolve", "run_script", "plan", "check", "replay", "draft",
           "new_script", "export_py", "to_python", "BUILTINS", "FORMAT", "FORMAT_VERSION"]
