#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""명령줄의 오류 — 사람에게는 표준오류의 한 줄(`equion: 오류: …`), `--json`이면 표준출력의 JSON 하나.

    {"error": {"message": "없는 부품: demand:ZZ (있는 부품: …)", "exit_code": 3, "kind": "input", "kind_ko": "입력 오류"}}

종료 코드는 어느 쪽이든 같다(0·1·2·3·130 — D15). 자동화·Claude는 종료 코드를 보고, 0이 아니면 `error`를 읽는다.
`--json` 여부는 명령 한 번마다 정한다(`main`이 그 호출의 인자로 정하고 끝나면 되돌린다 — 스크립트·노트가 같은 프로세스에서 명령을 부르므로).
"""

import json
import sys
import traceback

from .runner import EXIT_INPUT, EXIT_INTERRUPT, EXIT_SCRIPT, EXIT_SOLVE

PROG = "equion"
KIND = {EXIT_SCRIPT: "script", EXIT_SOLVE: "check", EXIT_INPUT: "input", EXIT_INTERRUPT: "interrupted"}
KIND_KO = {EXIT_SCRIPT: "스크립트 오류", EXIT_SOLVE: "풀이 실패·확인 실패", EXIT_INPUT: "입력 오류", EXIT_INTERRUPT: "중단"}
JSON = False          # 지금 명령에 --json이 있나(main이 정한다)


def payload(message, code: int = EXIT_INPUT, **extra) -> dict:
    """오류 JSON(사전)."""
    err = {"message": str(message), "exit_code": code, "kind": KIND.get(code, "error"), "kind_ko": KIND_KO.get(code, "오류")}
    err.update({k: v for k, v in extra.items() if v is not None})
    return {"error": err}


def fail(message, code: int = EXIT_INPUT, **extra) -> int:
    """오류를 알린다 — --json이면 표준출력에 JSON, 아니면 표준오류에 한 줄. 종료 코드를 돌려준다."""
    if JSON:
        print(json.dumps(payload(message, code, **extra), ensure_ascii=False, indent=2))
    else:
        print(f"{PROG}: 오류: {message}", file=sys.stderr)
    return code


def internal(exc: BaseException) -> int:
    """예상 못 한 오류(버그) — --json이면 JSON(형과 트레이스백 끝), 아니면 트레이스백 그대로. 종료 코드 1."""
    if JSON:
        tb = traceback.format_exception(type(exc), exc, exc.__traceback__)
        print(json.dumps(payload(f"{type(exc).__name__}: {exc}", EXIT_SCRIPT, type=type(exc).__name__, internal=True,
                                 traceback="".join(tb[-6:])), ensure_ascii=False, indent=2))
    else:
        traceback.print_exception(type(exc), exc, exc.__traceback__)
    return EXIT_SCRIPT
