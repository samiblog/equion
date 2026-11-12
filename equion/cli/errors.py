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
SOFT = None           # 지금 명령이 사람에게 넘긴 것 — soft()가 채운다(main이 명령마다 새로)
LAST_SOFT: list = []  # 방금 끝난 명령의 그것(main이 끝날 때 옮긴다 — 스크립트가 그 단계를 멈추지 않고 '!'로 표시한다)


def soft(reason) -> None:
    """종료 코드가 0이 아닌 까닭이 '사람이 정할 것'뿐임을 알린다(손으로 고친 결과 구역을 덮지 않고 건너뜀 등).

    명령줄에서는 그대로 종료 코드 3이다. 스크립트(.eqs)에서는 그 단계에서 멈추지 않고 '!'(표시)로 까닭을 남기고 이어 간다
    — 사람이 볼 것이지 실행을 멈출 오류가 아니므로."""
    if SOFT is not None:
        SOFT.append(str(reason))


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


def busy_text(exc: BaseException):
    """파일을 다른 프로그램이 쥐고 있어서(접근 거부·공유 위반) 또는 다른 명령이 프로젝트를 고치는 중이라 난 오류면 사람이 읽을 글,
    아니면 None — 트레이스백 대신 입력 오류(종료 코드 3)로 알린다."""
    from ..work.lock import FileBusy, ProjectBusy, is_busy
    if isinstance(exc, (FileBusy, ProjectBusy)):
        return str(exc)
    if isinstance(exc, OSError) and is_busy(exc):
        name = exc.filename or "파일"
        return (f"{name}을(를) 열거나 바꿀 수 없습니다 — 다른 프로그램(엑셀·동기화·백신 등)이 쓰고 있거나 읽기 전용입니다. "
                f"그 프로그램에서 닫고 다시 하세요. ({exc.strerror or exc})")
    return None


def internal(exc: BaseException) -> int:
    """예상 못 한 오류(버그) — --json이면 JSON(형과 트레이스백 끝), 아니면 트레이스백 그대로. 종료 코드 1."""
    if JSON:
        tb = traceback.format_exception(type(exc), exc, exc.__traceback__)
        print(json.dumps(payload(f"{type(exc).__name__}: {exc}", EXIT_SCRIPT, type=type(exc).__name__, internal=True,
                                 traceback="".join(tb[-6:])), ensure_ascii=False, indent=2))
    else:
        traceback.print_exception(type(exc), exc, exc.__traceback__)
    return EXIT_SCRIPT
