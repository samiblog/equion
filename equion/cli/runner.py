#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""스크립트 실행기 — CLI `run`이 쓰고, P3 데스크톱 앱의 프로그램 실행도 같은 것을 쓴다(D1).

스크립트는 평범한 Python이다(D5). 실행기는 그 앞뒤로 다음을 한다.
- 매개변수(`--set`·`--params`)를 `eqn.params`에, 기본 표본(`--smpl`)을 새로 여는 워크파일에 넣는다.
- 화면 출력을 그대로 보이면서 로그로 모으고, `eqn.show`·`.show()`로 보인 표·그래프를 스풀에 모은다.
- 읽은 입력 파일(해시)·쓴 파일·풀이 결과를 기록한다(runtime.RunRecord).
- 종료 코드: 0 성공 · 1 스크립트 오류 · 2 풀이 실패(`--fail-on`) · 3 입력 오류 · 130 중단.
"""

import io
import os
import sys
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from ..formula.parser import DSLError, UnknownVariableError
from ..system.analyzer import StructureError
from ..workfile import output as _output
from ..workfile import runtime as _runtime
from ..workfile.objects import MergeError

EXIT_OK, EXIT_SCRIPT, EXIT_SOLVE, EXIT_INPUT, EXIT_INTERRUPT = 0, 1, 2, 3, 130
STATUS = {EXIT_OK: "ok", EXIT_SCRIPT: "error", EXIT_SOLVE: "solve_failed",
          EXIT_INPUT: "input_error", EXIT_INTERRUPT: "interrupted"}
STATUS_KO = {"ok": "성공", "error": "스크립트 오류", "solve_failed": "풀이 실패",
             "input_error": "입력 오류", "interrupted": "중단"}

# --fail-on 수준 → 실패로 보는 기간 상태
FAIL_ON = {"never": (), "failed": ("failed",), "fallback": ("fallback", "failed"),
           "partial": ("partial", "fallback", "failed")}
PERIOD_KO = {"ok": "정상", "partial": "일부식 제외", "fallback": "실패대체", "failed": "실패"}

# 입력 문제로 보는 예외(파일 없음·방정식 문법·자료에 없는 변수·모델 구조·merge 실패·--set 값의 형)
INPUT_ERRORS = (FileNotFoundError, NotADirectoryError, IsADirectoryError, DSLError, StructureError, MergeError,
                UnknownVariableError, _runtime.ParamError)


@dataclass
class RunOptions:
    script: str
    params: dict = field(default_factory=dict)
    smpl: Optional[str] = None
    out: str = "out"
    run_id: Optional[str] = None
    formats: tuple = ("csv", "html")
    report: bool = True
    plotlyjs: str = "copy"
    fail_on: str = "failed"
    verbosity: int = 1
    log: Optional[str] = None
    script_args: List[str] = field(default_factory=list)
    argv: List[str] = field(default_factory=list)  # 명령줄 전체(manifest 기록용)
    redact: bool = False  # 보고서에서 작업 폴더·실행 파일 경로·git 브랜치를 빼고 경로를 줄인다


@dataclass
class RunResult:
    options: RunOptions
    exit_code: int
    started: datetime
    finished: datetime
    elapsed: float
    error: Optional[dict]
    namespace: dict
    record: "_runtime.RunRecord"
    outputs: list
    log: str
    fail_reasons: List[str] = field(default_factory=list)
    report_dir: Optional[str] = None

    @property
    def status(self) -> str:
        return STATUS.get(self.exit_code, "error")

    def solve_counts(self) -> dict:
        tot = {"ok": 0, "partial": 0, "fallback": 0, "failed": 0}
        for r in self.record.solves:
            for k, v in r.counts().items():
                tot[k] = tot.get(k, 0) + v
        return tot

    def unused_params(self) -> List[str]:
        """--set으로 줬지만 스크립트의 eqn.params가 선언하지 않은 이름."""
        return sorted(k for k in self.options.params if k not in self.record.params_declared)


def normalize_smpl(text: Optional[str]) -> Optional[str]:
    """'2000Q1:2022Q4' · '2000Q1 2022Q4' · '@all' → wf.smpl 인자 문자열."""
    if text is None:
        return None
    t = text.strip()
    if t.lower() in ("@all", "all"):
        return "@all"
    parts = t.replace(":", " ").split()
    if len(parts) != 2:
        raise ValueError(f"--smpl 형식은 시작:끝 (예: 2000Q1:2022Q4) 입니다: {text!r}")
    from ..data.periods import parse_period
    if not any(p.startswith("@") for p in parts):
        freq = "Q" if "Q" in parts[0].upper() else "M" if ("M" in parts[0].upper() or "-" in parts[0]) else "A"
        try:
            a, b = parse_period(parts[0], freq), parse_period(parts[1], freq)
        except ValueError as e:
            raise ValueError(f"--smpl: {e}") from None
        if a > b:
            raise ValueError(f"--smpl 시작({parts[0]})이 끝({parts[1]})보다 뒤입니다")
    return " ".join(parts)


class _Tee(io.TextIOBase):
    """화면에 쓰면서 로그 버퍼에도 남긴다."""

    def __init__(self, stream, buf: io.StringIO):
        self._stream = stream
        self._buf = buf

    def write(self, s):
        self._stream.write(s)
        self._buf.write(s)
        return len(s)

    def flush(self):
        self._stream.flush()

    def isatty(self):
        return getattr(self._stream, "isatty", lambda: False)()

    @property
    def encoding(self):
        return getattr(self._stream, "encoding", "utf-8")


def _script_traceback(exc: BaseException, path: str) -> str:
    """실행기 자신의 프레임을 빼고 스크립트부터 시작하는 traceback."""
    if isinstance(exc, SyntaxError):
        return "".join(traceback.format_exception_only(type(exc), exc))
    tb = exc.__traceback__
    while tb is not None and os.path.abspath(tb.tb_frame.f_code.co_filename) != path:
        tb = tb.tb_next
    return "".join(traceback.format_exception(type(exc), exc, tb or exc.__traceback__))


def _check_fail_on(record, fail_on: str) -> List[str]:
    bad = FAIL_ON.get(fail_on, ())
    reasons = []
    for r in record.solves:
        c = r.counts()
        hit = [f"{PERIOD_KO[k]} {c[k]}" for k in bad if c.get(k)]
        if hit:
            reasons.append(f"모델 {r.model} · 시나리오 {r.scenario}({r.alias}) {r.start}~{r.end}: "
                           + " · ".join(hit))
    return reasons


def run_script(opts: RunOptions) -> RunResult:
    """스크립트를 한 번 실행하고 결과(종료 코드·출력·기록)를 돌려준다. 보고서는 report.write_report."""
    path = os.path.abspath(opts.script)
    started, t0 = datetime.now(), time.perf_counter()
    buf = io.StringIO()
    ns = {"__name__": "__main__", "__file__": path, "__package__": None}
    error, code = None, EXIT_OK

    old = {"stdout": sys.stdout, "stderr": sys.stderr, "argv": sys.argv, "path": list(sys.path),
           "verbose": _output.verbose(), "mode": _output.spool.mode}
    _output.spool.clear()
    _output.spool.mode = "auto" if opts.verbosity >= 1 else "collect"
    _output.verbose(opts.verbosity)
    _runtime.set_params(opts.params)
    for k, v in opts.params.items():                 # 이름이 비밀처럼 생긴 --set 값은 보고서·로그에서 가린다
        if _runtime.SENSITIVE_NAME.search(k):
            _runtime._remember_secret(v)
    record = _runtime.begin_run(opts.smpl)
    sys.stdout, sys.stderr = _Tee(old["stdout"], buf), _Tee(old["stderr"], buf)
    sys.argv = [path, *opts.script_args]
    sys.path.insert(0, os.path.dirname(path))
    cwd = os.getcwd()
    try:
        with open(path, "rb") as f:          # 바이트로 — 인코딩 선언(# -*- coding: cp949 -*-)·BOM을 Python이 처리
            source = f.read()
        exec(compile(source, path, "exec"), ns)  # noqa: S102 — 사용자가 실행을 요청한 스크립트
    except SystemExit as e:
        c = e.code
        if c is None or c == 0:
            code = EXIT_OK
        elif isinstance(c, int):
            code = c
        else:
            print(c, file=sys.stderr)
            code = EXIT_SCRIPT
        if code != EXIT_OK:
            error = {"type": "SystemExit", "message": str(c), "traceback": ""}
    except KeyboardInterrupt:
        code = EXIT_INTERRUPT
        error = {"type": "KeyboardInterrupt", "message": "사용자가 중단했습니다", "traceback": ""}
        print("\n[equion] 중단됨", file=sys.stderr)
    except BaseException as e:  # noqa: BLE001 — 스크립트의 모든 오류를 종료 코드로 바꾼다
        code = EXIT_INPUT if isinstance(e, INPUT_ERRORS) else EXIT_SCRIPT
        tb = _script_traceback(e, path)
        error = {"type": type(e).__name__, "message": str(e), "traceback": tb}
        sys.stderr.write(tb)
    finally:
        try:
            os.chdir(cwd)                    # 스크립트가 작업 폴더를 바꿔도 보고서는 실행한 자리 기준
        except OSError:
            pass
        sys.stdout, sys.stderr = old["stdout"], old["stderr"]
        sys.argv = old["argv"]
        sys.path[:] = old["path"]
        _runtime.end_run()
        _runtime.set_params({})
        outputs = list(_output.spool.items)
        _output.spool.clear()
        _output.spool.mode = old["mode"]
        _output.verbose(old["verbose"])

    fail_reasons = []
    if code == EXIT_OK:
        fail_reasons = _check_fail_on(record, opts.fail_on)
        if fail_reasons:
            code = EXIT_SOLVE
            msg = f"[equion] 풀이 실패 조건(--fail-on {opts.fail_on}):\n  " + "\n  ".join(fail_reasons)
            print(msg, file=sys.stderr)
            buf.write(msg + "\n")
    return RunResult(opts, code, started, datetime.now(), time.perf_counter() - t0, error, ns,
                     record, outputs, buf.getvalue(), fail_reasons)
