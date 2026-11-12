#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""명령 한 줄 실행기 (D52) — Equion Desk의 명령 창이 쓴다: `est demand:CN`처럼 친 줄을 같은 프로세스에서 명령줄 그대로 돌린다.

    from equion.cli.line import run_line, catalog
    r = run_line("D:/prj", "an unitroot Y --trend ct")
    r.code, r.records, r.changes, r.out

- 문법은 명령줄 그대로(앞의 `equion`은 빼도 된다). 터미널에서 같은 줄을 치면 같은 일이 되고 같은 기록이 남는다.
- 받지 않는 것: Python 스크립트 실행(`run x.py`)과 새 프로젝트(`new`), 다른 프로젝트(`-p`/`--project` — 명령 창은 그 탭의 프로젝트),
  프로세스를 다시 띄우거나 지켜보는 선택지(`--threads` · `--watch`), 사용자 폴더에 스킬 설치(`guide skill --install`) — 그것은 터미널에서.
  셸 명령은 애초에 Equion 명령이 아니다. Desk의 작업 프로세스는 Python 단계·블록을 돌리지 않는다(EQUION_NO_PYTHON — 스크립트의 `py` 단계와
  노트의 Python 블록은 '거절'로 끝나고 터미널에 붙일 명령을 알린다).
- 명령은 입력을 기다리지 않는다 — 표준 입력은 비워 둔다(Desk의 작업 프로세스는 표준 입력으로 요청을 받는다).
- 돌려주는 것: 종료 코드·출력 글·새로 생긴 기록(work/log.jsonl)·새 바뀜 기록(work/history) — 화면이 결과 탭과 '되돌리기'를 잇는다.
- `catalog()`는 명령줄 정의(argparse)에서 명령·옵션 목록을 뽑는다 — 자동 완성의 재료. 분석이 늘면 함께 는다(등록부).
"""

import argparse
import contextlib
import io
import json
import os
import re
import shlex
import time
from dataclasses import dataclass, field
from typing import List, Optional

DENIED = {
    "new": "새 프로젝트는 터미널이나 Desk의 시작 화면에서",
}
MAX_OUT = 60_000


@dataclass
class LineResult:
    """명령 한 줄의 결과 — `.line`(실행한 줄) · `.code`(종료 코드) · `.out`(출력 글) · `.records`(새 기록) · `.changes`(새 바뀜 기록) ·
    `.seconds` · `.denied`(받지 않은 까닭)."""

    line: str
    code: int
    out: str = ""
    records: List[str] = field(default_factory=list)
    changes: List[str] = field(default_factory=list)
    seconds: float = 0.0
    denied: Optional[str] = None

    def to_dict(self) -> dict:
        return {"line": self.line, "code": self.code, "out": self.out, "records": self.records, "changes": self.changes,
                "seconds": self.seconds, "denied": self.denied}


def _log_ids(root: str) -> List[str]:
    path = os.path.join(root, "work", "log.jsonl")
    out = []
    try:
        with open(path, encoding="utf-8") as f:
            for raw in f:
                try:
                    rid = json.loads(raw).get("id")
                except (ValueError, AttributeError):
                    continue
                if isinstance(rid, str):
                    out.append(rid)
    except OSError:
        pass
    return out


def _history_ids(root: str) -> List[str]:
    base = os.path.join(root, "work", "history")
    try:
        return sorted(n for n in os.listdir(base) if re.fullmatch(r"h\d+", n))
    except OSError:
        return []


def split(line: str) -> List[str]:
    """줄 → 낱말(명령줄과 같은 따옴표 규칙 — POSIX). 앞의 `equion`은 뺀다."""
    toks = shlex.split(str(line or "").strip())
    if toks and toks[0].lower() == "equion":
        toks = toks[1:]
    return toks


def why_not(toks: List[str]) -> Optional[str]:
    """받지 않는 줄이면 까닭(받으면 None)."""
    if not toks:
        return "빈 줄"
    if toks[0] in DENIED:
        return DENIED[toks[0]]
    if toks[0] == "run" and any(t.lower().endswith(".py") for t in toks[1:]):
        return "Python 스크립트는 터미널에서(equion run x.py) — 명령 창은 Equion 명령과 .eqs 스크립트만"
    from ..registry import names_project
    if any(names_project(t) for t in toks[1:]):
        return "명령 창은 이 탭의 프로젝트에서만 — 다른 프로젝트는 그 프로젝트의 탭이나 터미널에서(-p/--project 없이)"
    for opt, what in (("--threads", "스레드 수를 바꿔 다시 띄우기"), ("--watch", "파일을 지켜보며 다시 돌리기")):
        if any(len(t.split("=", 1)[0]) >= 5 and opt.startswith(t.split("=", 1)[0]) for t in toks[1:]):
            return f"{opt}({what})는 터미널에서 — 명령 창은 한 번 돌고 끝나는 명령만"
    if toks[0] == "guide" and any(len(t.split("=", 1)[0]) >= 5 and "--install".startswith(t.split("=", 1)[0]) for t in toks[1:]):
        return "스킬 설치(guide skill --install)는 사용자 폴더에 파일을 쓴다 — 터미널에서"
    return None


def run_line(root: str, line: str, who: str = "desk") -> LineResult:
    """명령 한 줄을 프로젝트 폴더에서 같은 프로세스로 실행한다(명령줄 `equion …`과 같다). 기록의 '누가'는 who."""
    from ..work.store import detect_who  # noqa: F401 — 같은 규칙(EQUION_WHO)을 쓴다
    from .commands import main as cli
    try:
        toks = split(line)
    except ValueError as e:
        why = "따옴표가 닫히지 않았습니다" if "quotation" in str(e) else str(e)
        return LineResult(str(line), 3, f"줄을 나누지 못했습니다 — {why}", denied=why)
    text = shlex.join(toks)
    why = why_not(toks)
    if why:
        return LineResult(text, 3, why, denied=why)
    before_r, before_h = set(_log_ids(root)), set(_history_ids(root))
    buf = io.StringIO()
    old_cwd, old_who = os.getcwd(), os.environ.get("EQUION_WHO")
    stdin = __import__("sys").stdin
    t0 = time.perf_counter()
    try:
        os.chdir(root)
        os.environ["EQUION_WHO"] = who
        __import__("sys").stdin = io.StringIO("")
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                code = cli(list(toks))
            except SystemExit as e:
                code = e.code if isinstance(e.code, int) else (0 if e.code is None else 3)
            except Exception:  # noqa: BLE001 — 명령의 예상 못 한 오류도 글로
                import traceback
                traceback.print_exc()
                code = 1
    finally:
        __import__("sys").stdin = stdin
        os.chdir(old_cwd)
        if old_who is None:
            os.environ.pop("EQUION_WHO", None)
        else:
            os.environ["EQUION_WHO"] = old_who
    out = buf.getvalue()
    if len(out) > MAX_OUT:
        out = out[:MAX_OUT] + f"\n… (글이 길어 {MAX_OUT}자에서 잘랐다)"
    records = [r for r in _log_ids(root) if r not in before_r]
    changes = [h for h in _history_ids(root) if h not in before_h]
    return LineResult(text, int(code or 0), out, records, changes, round(time.perf_counter() - t0, 4))


def catalog() -> List[dict]:
    """명령·옵션 목록(자동 완성의 재료) — 명령 경로마다 {command, help, args: [{name, help, choices}], options: [{flags, help, choices, takes, metavar}]}."""
    from .commands import build_parser
    out: List[dict] = []

    def describe(p: argparse.ArgumentParser, path: List[str], help_text: str):
        subs = [a for a in p._actions if isinstance(a, argparse._SubParsersAction)]
        if subs:
            helps = {c.dest: c.help for c in subs[0]._choices_actions}
            for name, sp in subs[0].choices.items():
                describe(sp, path + [name], helps.get(name) or "")
            return
        args, opts = [], []
        for a in p._actions:
            if isinstance(a, (argparse._HelpAction, argparse._VersionAction)):
                continue
            item = {"help": a.help or "", "choices": [str(c) for c in a.choices] if a.choices else None, "metavar": a.metavar}
            if a.option_strings:
                opts.append({**item, "flags": list(a.option_strings), "takes": a.nargs != 0})
            else:
                args.append({**item, "name": a.dest, "many": a.nargs in ("*", "+", argparse.REMAINDER)})
        out.append({"command": " ".join(path), "help": help_text, "args": args, "options": opts,
                    "denied": why_not(path)})

    describe(build_parser(), [], "")
    return out
