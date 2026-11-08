#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""실행 환경 공유 상태 — 스크립트 매개변수(`eqn.params`), 엔진 로그 감추기, 실행 기록.

실행 기록(RunRecord)은 CLI(`equion run`)가 보고서 manifest에 남기는 것이다: 읽은 입력 파일(해시),
스크립트가 쓴 파일, 풀이 결과, 새로 여는 워크파일의 기본 표본(`--smpl`). 실행 중이 아니면(노트북·일반
스크립트) 기록 함수는 아무것도 하지 않는다.
"""

import hashlib
import json
import os
import re
from types import SimpleNamespace

from .output import verbose

_OVERRIDES: dict = {}

#: 이름이 이렇게 생긴 매개변수 값은 비밀로 본다(보고서·로그에서 가림)
SENSITIVE_NAME = re.compile(r"(?i)(key|token|secret|passw|pwd|credential|auth)")
_SECRET_VALUES: set = set()   # 이 프로세스에서 비밀로 표시된 값(4글자 이상) — 보고서·run.log에서 '***'로


def _remember_secret(value):
    if isinstance(value, str) and len(value) >= 4:
        _SECRET_VALUES.add(value)


def secret_values() -> set:
    return set(_SECRET_VALUES)


def secret(name: str, default: str = None) -> str:
    """비밀 값(API 키 등)을 환경변수에서 읽는다 — 스크립트·명령줄·보고서에 값을 남기지 않으려고 쓴다.

    읽은 값은 이 프로세스의 명령줄 보고서(manifest.json·report.html·run.log)에서 '***'로 가려진다.

    매개변수
        name: 환경변수 이름
        default: 없을 때 쓸 값(None이면 오류)

    오류
        ValueError: 환경변수가 없고 default도 없음

    예
        >>> import os
        >>> os.environ["EQUION_DOC_KEY"] = "abc123"
        >>> eqn.secret("EQUION_DOC_KEY")
        'abc123'
        >>> eqn.secret("EQUION_NO_SUCH_KEY", default="")
        ''

    관련: params
    """
    value = os.environ.get(name, default)
    if value is None:
        raise ValueError(f"비밀 값 {name}이(가) 환경변수에 없습니다 — 실행 전에 환경변수로 넣으세요(스크립트에 쓰지 말 것)")
    _remember_secret(value)
    return value


def set_params(values: dict):
    """CLI(`--set 이름=값`)가 스크립트 실행 전에 넣는다."""
    _OVERRIDES.clear()
    _OVERRIDES.update(values or {})


def _coerce(value, default):
    if not isinstance(value, str) or default is None:
        return value
    if isinstance(default, bool):
        return value.strip().lower() in ("1", "true", "yes", "on", "y")
    if isinstance(default, int):
        return int(value)
    if isinstance(default, float):
        return float(value)
    return value


def params(**defaults) -> SimpleNamespace:
    """스크립트 매개변수 — 기본값을 주면 명령줄 `--set 이름=값`(또는 환경변수 EQUION_PARAMS의 JSON)이 덮는다.

    값은 기본값의 형(정수·실수·글자·참거짓)으로 바뀐다. `smpl`이라는 이름은 명령줄 `--smpl S:E`로도 덮인다.
    스크립트를 `equion run`으로 실행하면 준 값과 최종 값이 보고서 manifest.json에 남는다.

    매개변수
        **defaults: 이름=기본값

    돌려주는 것
        속성으로 읽는 객체(p.이름)

    예
        >>> p = eqn.params(g_up=10.0, start="1990Q1")
        >>> p.g_up, p.start
        (10.0, '1990Q1')

    관련: 명령줄 equion run --set · secret
    """
    merged = dict(defaults)
    sources = []
    env = os.environ.get("EQUION_PARAMS") or os.environ.get("MACROMODEL_PARAMS")  # 옛 이름도 읽는다
    if env:
        try:
            sources.append(json.loads(env))
        except json.JSONDecodeError as e:
            raise ValueError(f"EQUION_PARAMS 가 JSON이 아닙니다: {e}") from None
    sources.append(_OVERRIDES)
    for src in sources:
        for k, v in src.items():
            merged[k] = _coerce(v, defaults.get(k))
    for k, v in merged.items():
        if SENSITIVE_NAME.search(k):
            _remember_secret(v)
    rec = _RUN["record"]
    if rec is not None and rec.smpl and "smpl" in defaults and "smpl" not in _OVERRIDES:
        merged["smpl"] = rec.smpl  # CLI --smpl 은 스크립트가 선언한 smpl 매개변수도 덮는다
    if rec is not None:
        rec.params.update(merged)
        rec.params_declared.update(defaults)
    return SimpleNamespace(**merged)


def quiet(fn, *args, **kwargs):
    """엔진의 상세 로그('equion.engine')를 감춘 채 실행한다(eqn.verbose(2)면 그대로 보인다).
    경고(logging.WARNING 이상)는 감추지 않는다."""
    if verbose() >= 2:
        return fn(*args, **kwargs)
    from ..log import silenced
    with silenced():
        return fn(*args, **kwargs)


# ---------------------------------------------------------------------------
# 실행 기록 (CLI)
# ---------------------------------------------------------------------------
class RunRecord:
    def __init__(self, smpl: str = None):
        self.smpl = smpl        # 새로 여는 워크파일의 기본 표본("2000Q1 2022Q4" 또는 "@all")
        self.inputs: list = []  # [{"path", "kind", "sha256", "bytes"}]
        self.written: list = []  # [{"path", "kind"}]
        self.solves: list = []  # [SolveResult]
        self.params: dict = {}  # 스크립트가 eqn.params로 받은 최종 값
        self.params_declared: dict = {}  # 스크립트가 선언한 기본값

    def input_paths(self) -> list:
        return [d["path"] for d in self.inputs]


_RUN = {"record": None}


def begin_run(smpl: str = None) -> RunRecord:
    _RUN["record"] = RunRecord(smpl)
    return _RUN["record"]


def end_run() -> RunRecord:
    rec, _RUN["record"] = _RUN["record"], None
    return rec


def current_run():
    return _RUN["record"]


def file_digest(path: str):
    """(sha256, 바이트 수). 폴더(워크파일 .eqw·번들 .wt)면 안의 파일을 상대경로 순서로 이어 해시한다."""
    h, size = hashlib.sha256(), 0
    if os.path.isdir(path):
        files = sorted(os.path.relpath(os.path.join(r, f), path)
                       for r, _, fs in os.walk(path) for f in fs)
    else:
        files = [None]
    for rel in files:
        fp = path if rel is None else os.path.join(path, rel)
        if rel is not None:
            h.update(rel.replace(os.sep, "/").encode("utf-8") + b"\0")
        with open(fp, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
                size += len(chunk)
    return h.hexdigest(), size


def record_input(path: str, kind: str):
    rec = _RUN["record"]
    if rec is None or not path or not os.path.exists(path):
        return
    ap = os.path.abspath(path)
    if any(d["abspath"] == ap for d in rec.inputs):
        return
    digest, size = file_digest(path)
    rec.inputs.append({"path": path, "abspath": ap, "kind": kind, "sha256": digest, "bytes": size})


def record_output(path: str, kind: str):
    rec = _RUN["record"]
    if rec is not None and path:
        rec.written.append({"path": str(path), "kind": kind})


def record_solve(result):
    rec = _RUN["record"]
    if rec is not None:
        rec.solves.append(result)


def apply_default_smpl(wf):
    """CLI `--smpl`이 있으면 새로 연 워크파일의 표본으로 둔다(스크립트의 wf.smpl(...)이 그 뒤에 덮는다)."""
    rec = _RUN["record"]
    if rec is not None and rec.smpl:
        wf.smpl(rec.smpl)
    return wf
