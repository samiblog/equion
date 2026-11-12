#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""스크립트 실행 하나 (D33·D36) — 단계(명령·확인·Python)를 차례로 하고 실행 기록 `work/run/<이름>/`(`run:`)을 남긴다.

`.eqs` 실행(`equion run x.eqs`)과 내보낸 Python(`equion script export --py`)이 같은 이것을 쓴다:

    with eqn.script.session("FLOWS/monthly.eqs", params={"scenarios": "base oil20"}) as s:
        s.section("자료")
        s.cmd("data build --inbox ask --use")
        s.cmd("hs main --range 2005Q1:last")
        s.expect("hs", "Y.rmspe < 2%", stop=False)

    work/run/<이름>/
      record.json      단계마다 줄(값을 바꿔 넣은 뒤)·상태·종료 코드·만든 기록·바뀜 기록 · 매개변수 · 자료 회차(처음·끝) · 판
      script.eqs       이 결과를 만든 스크립트(값을 바꿔 넣은 뒤) — 복사해 동료나 Claude에게
      src/             원래 스크립트(포함한 것까지)·Python 단계 파일 — `--replay`가 이것으로 다시 돈다
      defs/            시작할 때의 정의 파일 사본(equion.toml·블록·채택표·자료 정의·가정·보정항·시나리오·노트·보고서)
      steps/NN.txt     단계마다 명령의 출력
      summary.md       카드 — 단계 표·표시·스크립트

단계 안의 명령은 같은 프로세스에서 명령줄 그대로 돈다(누가 = '스크립트', 기록에는 `run` = 이 실행). 명령이 실패하면(종료 코드 ≠ 0) 거기서
멈추고 그 종료 코드로 끝난다. `expect --stop`에 걸리면 종료 코드 2(결과 확인 실패 — `--fail-on`과 같은 갈래, D15 안에서).
"""

import contextlib
import io
import os
import platform
import re
import shlex
import subprocess
import sys
import time
import traceback
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Dict, List, Optional

from .. import registry as reg
from ..work.store import NAME_RE, RecordError, WorkStore, detect_who
from .language import (EXPECT_KINDS, RECORD_REFS, ScriptError, _q, parse_expect, places, resolve)

EXIT_OK, EXIT_SCRIPT, EXIT_SOLVE, EXIT_INPUT, EXIT_INTERRUPT = 0, 1, 2, 3, 130
MARK = {"ok": "✓", "flag": "!", "stop": "×", "error": "×", "denied": "×", "skip": "–", "interrupted": "×", "cancelled": "×"}
STATUS_KO = {"ok": "정상", "flag": "표시", "stop": "멈춤(확인)", "error": "오류", "denied": "허용 안 됨", "skip": "건너뜀",
             "interrupted": "중단", "cancelled": "끝나지 못함(취소·중단)"}
FAIL_ON = {"failed": ("failed",), "fallback": ("failed", "fallback"), "partial": ("failed", "fallback", "partial"), "never": ()}


class ScriptStop(Exception):
    """단계가 실패하거나 expect --stop에 걸려 실행을 멈춘다 — `.code`(종료 코드)."""

    def __init__(self, code: int, message: str = ""):
        super().__init__(message)
        self.code = code


@dataclass
class StepResult:
    """단계 하나의 결과."""

    n: int
    kind: str                          # cmd · expect · py
    line: str                          # 값을 바꿔 넣은 뒤의 줄
    source: str = ""                   # 스크립트에 적힌 줄
    section: str = ""
    where: str = ""
    status: str = "ok"                 # ok · flag · stop · error · denied · skip · interrupted
    code: Optional[int] = 0
    records: List[str] = field(default_factory=list)
    changes: List[str] = field(default_factory=list)
    effects: List[str] = field(default_factory=list)
    vintage: Optional[str] = None      # 단계가 끝난 뒤 지금 회차
    detail: str = ""
    inbox: List[dict] = field(default_factory=list)
    elapsed: float = 0.0
    out: str = ""
    warnings: List[str] = field(default_factory=list)   # 경고(파이썬 경고·[WARN] 줄) — 결과 줄 대신 보이지 않게 따로

    @property
    def brief(self) -> str:
        """한 줄 요약 — 명령 출력의 첫 결과 줄(경고 줄은 건너뜀) 또는 까닭."""
        first = next((x.strip() for x in _split_warnings(self.out)[0] if x.strip()), "")
        return self.detail or first

    def to_dict(self) -> dict:
        """사전(출력 글은 steps/NN.txt에)."""
        return {"n": self.n, "kind": self.kind, "line": self.line, "source": self.source, "section": self.section,
                "where": self.where, "status": self.status, "code": self.code, "records": self.records,
                "changes": self.changes, "effects": self.effects, "vintage": self.vintage, "detail": self.detail,
                "inbox": self.inbox, "elapsed": round(self.elapsed, 3), "warnings": self.warnings}


_PYWARN = re.compile(r"^\S.*?:\d+: [A-Za-z_]*Warning: ")


def _is_warning(line: str) -> bool:
    """명령 출력의 경고 줄인가 — 엔진의 [WARN] 줄 · 파이썬 경고('파일:줄: …Warning: …')."""
    t = line.strip()
    return t.startswith("[WARN]") or bool(_PYWARN.match(t))


def _split_warnings(out: str):
    """출력 → (경고가 아닌 줄들, 경고 줄들). 파이썬 경고 바로 뒤의 들여 쓴 줄(경고가 난 소스 줄)도 경고에 붙인다."""
    plain, warn, after_py = [], [], False
    for x in (out or "").splitlines():
        if _is_warning(x):
            warn.append(x.strip())
            after_py = bool(_PYWARN.match(x.strip()))
            continue
        if after_py and x[:1] in (" ", chr(9)) and x.strip():
            after_py = False
            continue
        after_py = False
        plain.append(x)
    return plain, warn


def _warning_lines(out: str) -> List[str]:
    """출력에서 경고 줄(같은 글은 하나로)."""
    return list(dict.fromkeys(_split_warnings(out)[1]))


def find_root(path: str) -> str:
    """프로젝트 폴더 — path(폴더·파일)에서 위로 올라가며 equion.toml이 있는 곳."""
    d = os.path.abspath(path)
    if os.path.isfile(d):
        d = os.path.dirname(d)
    while True:
        if os.path.isfile(os.path.join(d, "equion.toml")):
            return d
        up = os.path.dirname(d)
        if up == d:
            raise ScriptError(f"프로젝트(equion.toml)를 찾지 못했습니다: {path} — 스크립트는 프로젝트 안에서(또는 -p 폴더)")
        d = up


def _stem(script: Optional[str]) -> str:
    s = os.path.splitext(os.path.basename(script or ""))[0]
    s = re.sub(r"[^A-Za-z0-9_\-]", "_", s).strip("_-")
    return s if s and NAME_RE.match(s) else "run"


def _as_list(v) -> List[str]:
    if isinstance(v, (list, tuple)):
        return [str(x) for x in v]
    return shlex.split(str(v)) if str(v).strip() else []


def versions() -> dict:
    """판 — equion·Python·numpy·pandas·scipy·운영체제."""
    from ..version import project_version
    out = {"equion": project_version(), "python": platform.python_version(), "os": platform.platform(terse=True)}
    for mod in ("numpy", "pandas", "scipy"):
        try:
            out[mod] = __import__(mod).__version__
        except ImportError:
            out[mod] = None
    return out


def snapshot(p) -> Dict[str, bytes]:
    """정의 파일의 지금 내용 {경로: 바이트}(바뀜 기록이 보는 파일 전부)."""
    from ..projects.records import history_of
    from ..work.history import tracked
    h = history_of(p)
    out = {}
    for rel in tracked(p.root, h.extra):
        with open(os.path.join(p.root, rel), "rb") as f:
            out[rel] = f.read()
    return out


class Session:
    """스크립트 실행 하나 — `cmd`·`expect`·`py`·`section`을 차례로 부르고 `close()`(또는 with 블록 끝)에서 실행 기록을 남긴다.

    매개변수
        project: 프로젝트 폴더 또는 그 안의 파일(스크립트 경로 — 위로 올라가며 equion.toml을 찾는다)
        params: 매개변수 {이름: 값}(값은 목록 또는 띄어 쓴 글자) — 줄의 {이름}에 들어간다
        script: 스크립트 경로(기록 이름의 앞부분·`src/`) · name: 기록 이름(기본 <스크립트>_0001 …)
        fail_on: 'failed'(기본)·'fallback'·'partial'·'never' — HS·전망 기록에 이 상태의 기간이 있으면 종료 코드 2
        echo: 단계마다 한 줄을 받는 함수(기본: 보이지 않음) · python: Python 단계를 돌릴지(Desk 앱은 거짓 — 환경 변수
            EQUION_NO_PYTHON이 있으면 늘 거짓)
        from_step: 이 단계 번호부터(앞 단계는 건너뜀 — 그 기록이 필요하면 프로젝트의 가장 새 기록)
    """

    def __init__(self, project: str = ".", params: dict = None, script: str = None, name: str = None, who: str = None,
                 command: str = None, fail_on: str = "failed", echo=None, verbosity: int = 1, python: bool = True,
                 from_step: int = None, today: str = None, total: int = None, sources: Dict[str, bytes] = None,
                 title: str = "", replay_of: str = None, origin: str = "python"):
        from ..projects import Project
        from ..projects.records import data_spec
        from . import record as _rec
        root = find_root(project)
        self.p = Project.open(root)
        self.root = self.p.root
        self.store = WorkStore(self.root)
        try:
            _rec.recover(self.root)          # 끝나지 못한 실행(취소·프로세스 끝남)은 먼저 그 기록을 남긴다 — 그 이름을 다시 쓰지 않게
        except Exception:  # noqa: BLE001 — 지난 실행을 정리하지 못해도 이번 실행은 한다
            pass
        self.params = {k: _as_list(v) for k, v in (params or {}).items()}
        if script and os.path.isabs(script):
            script = os.path.relpath(script, self.root).replace(os.sep, "/")
        self.script = script
        if fail_on not in FAIL_ON:
            raise ScriptError(f"fail_on은 {' · '.join(FAIL_ON)}: {fail_on!r}")
        self.who = who or detect_who("python")
        self.command = command
        self.fail_on = fail_on
        self.echo = echo
        self.verbosity = verbosity
        self.python = python and not os.environ.get("EQUION_NO_PYTHON")
        self.from_step = from_step
        self.today = today or date.today().isoformat()
        self.total = total
        self.sources = dict(sources or {})
        self.title = title
        self.replay_of = replay_of
        self.origin = origin                 # eqs(equion run x.eqs) · python(eqn.script.session)
        self.started = datetime.now()
        self._t0 = time.perf_counter()
        self.steps: List[StepResult] = []
        self.lines: List[str] = []
        self.section_title = ""
        self.implicit: List[str] = []
        self.defs = snapshot(self.p)
        self.vintage0 = self.p.vintage
        try:
            self.data0 = data_spec(self.p)
        except Exception:  # noqa: BLE001 — 회차가 아직 없을 수 있다
            self.data0 = None
        self.result = None
        self.status = "ok"
        self.exit_code = EXIT_OK
        self.name = _rec.reserve(self.store, name, _stem(script))     # 이름을 잡아 둔다(work/run/.active/<이름>.json)
        self.id = f"run:{self.name}"
        self._save_active()

    def _save_active(self, current: "StepResult" = None):
        """도는 실행의 상태(지금까지의 단계·하는 단계)를 work/run/.active/<이름>.json에 — 끝나지 못하면 다음 실행이 이것으로 기록을 남긴다."""
        from .record import save_active
        try:
            save_active(self, current)
        except OSError:                      # 상태를 못 써도 실행은 한다(끝나면 기록은 그대로 남는다)
            pass

    # ---- 값 ------------------------------------------------------------
    def values(self, text: str = "") -> dict:
        """줄에 들어갈 값 — 매개변수와 내장 값(지금 프로젝트 상태로 — 앞 단계가 회차를 바꿨으면 새 회차)."""
        from ..projects import Project
        vals = dict(self.params)
        need = {n for n, _ in places(text)} if text else {"vintage", "last", "model"}
        p = Project.open(self.root) if need & {"vintage", "last", "model"} else None
        if p is not None:
            vals["vintage"] = p.vintage or "-"
            vals["model"] = p.config.hs.get("model") or p.config.forecast.get("model") or (p.models[0] if p.models else "-")
            if "last" in need:
                try:
                    vals["last"] = p.span("last:last")[1]
                except Exception:  # noqa: BLE001
                    vals["last"] = "-"
        vals["today"] = self.today
        vals["run"] = self.name
        return vals

    def records(self, kind: str = None, filt: str = None) -> List[str]:
        """이 실행의 가장 뒤 단계가 만든 그 종류의 기록(filt: 시나리오·부품·분석·모형 이름) — 없으면 []."""
        for st in reversed(self.steps):
            ids = [r for r in st.records if kind is None or r.startswith(f"{kind}:")]
            if filt:
                ids = [r for r in ids if self._matches(r, filt)]
            if ids:
                return ids
        return []

    def _matches(self, rid: str, filt: str) -> bool:
        try:
            m = self.store.get(rid).meta
        except RecordError:
            return False
        return any(str(m.get(k) or "").lower() == filt.lower() for k in ("scenario", "part", "analysis", "model", "target"))

    def _refs(self, kind: str, filt: Optional[str]) -> List[str]:
        ids = self.records(kind, filt)
        if ids:
            return ids
        if self.from_step:                              # 건너뛴 단계의 기록 — 지금 자료 회차에서 계산한 가장 새 것
            from ..projects import Project
            vint = Project.open(self.root).vintage
            recs = [r for r in self.store.records(kind) if not filt or self._matches(r.id, filt)]
            here = [r for r in recs if not vint or ((r.meta.get("data") or {}).get("id") == vint)]
            if here:
                rid = here[-1].id
                self.implicit.append(f"{{{kind}{':' + filt if filt else ''}}} — 건너뛴 단계의 기록 대신 자료 회차 {vint or '-'}의 가장 새 기록 {rid}")
                return [rid]
            if recs:
                other = (recs[-1].meta.get("data") or {}).get("id")
                raise ScriptError(f"{{{kind}{':' + filt if filt else ''}}} — 건너뛴 단계의 기록이 지금 자료 회차 {vint}에는 없습니다"
                                  f"(가장 새 {recs[-1].id}는 회차 {other}) — 옛 회차의 기록을 쓰지 않습니다. --from을 그 기록을 만드는 "
                                  "단계로 당기세요")
        raise ScriptError(f"{{{kind}{':' + filt if filt else ''}}} — 이 실행에서 아직 {RECORD_REFS[kind]} 기록이 없습니다")

    def resolve(self, text: str) -> str:
        """줄의 {이름}을 값으로."""
        return resolve(text, self.values(text), self._refs)

    # ---- 단계 ----------------------------------------------------------
    def section(self, title: str):
        """단계 묶음 제목(## 제목)."""
        self.section_title = title
        self.lines += ["", f"## {title}"]

    def _new(self, kind, source, where) -> StepResult:
        return StepResult(len(self.steps) + 1, kind, source, source, self.section_title, where or "")

    def _skip(self, st: StepResult) -> bool:
        if self.from_step and st.n < self.from_step:
            st.status, st.code, st.detail = "skip", None, f"--from {self.from_step}"
            self._done(st)
            return True
        return False

    def _done(self, st: StepResult):
        self.steps.append(st)
        if self.result is None:
            self._save_active()
        if st.status != "skip":
            self.lines.append(st.line)
        if self.echo and self.verbosity > 0:
            tot = self.total or "?"
            brief = st.brief.replace("\n", " ")
            brief = brief if len(brief) <= 90 else brief[:89] + "…"
            self.echo(f"[{st.n}/{tot}] {st.line:<44} {MARK[st.status]} {brief}".rstrip())
            if self.verbosity > 1 and st.out.strip():
                self.echo("\n".join("      " + x for x in st.out.rstrip().splitlines()))

    def _state(self) -> dict:
        from ..projects.inbox import inbox_files
        from ..projects.vintage import RAW_DIR, list_vintages
        from ..data.source import file_sha256
        from ..projects.records import history_of
        from ..projects import Project
        raw = os.path.join(self.root, RAW_DIR)
        p = Project.open(self.root)
        return {"log": {d["id"] for d in self.store.log()},
                "vintages": [v["id"] for v in list_vintages(self.root)],
                "vintage": p.vintage,
                "changes": set(history_of(p)._ids()),
                "inbox": {os.path.basename(f): file_sha256(os.path.join(self.root, f)) for f in inbox_files(self.root)},
                "raw": set(n for n in (os.listdir(raw) if os.path.isdir(raw) else []) if os.path.isfile(os.path.join(raw, n)))}

    def _effects(self, st: StepResult, before: dict, after: dict):
        from ..data.source import file_sha256
        from ..projects.vintage import RAW_DIR
        # 이 실행의 단계가 만든 것만(기록의 run이 이 실행) — 같은 프로젝트에서 다른 명령·흐름이 동시에 만든 기록을 이 단계의 것({sim:base} 등)으로 잡지 않게
        new_log = [d["id"] for d in self.store.log() if d["id"] not in before["log"] and d.get("run") == self.id]
        st.records = new_log
        made = [v for v in after["vintages"] if v not in before["vintages"]]
        if made or after["vintage"] != before["vintage"]:
            st.records = [f"data:{v}" for v in (made or [after["vintage"]])] + st.records
        st.vintage = after["vintage"]
        st.changes = sorted(after["changes"] - before["changes"])
        if st.changes:                          # 다른 명령이 동시에 남긴 바뀜은 빼고(이 실행의 것과 이 단계가 알아본 '바깥' 바뀜만)
            from ..work.history import History
            h = History(self.root)
            keep = []
            for cid in st.changes:
                try:
                    c = h.get(cid)
                except (KeyError, OSError, ValueError):
                    continue
                if c.run == self.id or c.who == "바깥":
                    keep.append(cid)
            st.changes = keep
        gone = {k: v for k, v in before["inbox"].items() if k not in after["inbox"]}
        raw = os.path.join(self.root, RAW_DIR)
        for name, sha in gone.items():
            to = next((n for n in sorted(after["raw"]) if file_sha256(os.path.join(raw, n)) == sha), None)
            st.inbox.append({"from": name, "sha256": sha, "to": f"{RAW_DIR}/{to}".replace(os.sep, "/") if to else None,
                             "new": bool(to and to not in before["raw"])})

    def _flag(self, st: StepResult, vintage_before: Optional[str] = None):
        """명령은 성공했지만 사람이 볼 것 — 기준 미달 식 · 실패 대체 기간 · 지금 회차가 더 옛 회차·짧은 회차로 바뀜."""
        notes = []
        if vintage_before and st.vintage and st.vintage != vintage_before:
            from ..projects.vintage import move_notes
            try:
                notes += move_notes(self.root, vintage_before, st.vintage)
            except Exception:  # noqa: BLE001 — 회차를 읽지 못하면 표시하지 않는다(단계는 끝났다)
                pass
        for rid in st.records:
            if rid.startswith("data:"):
                continue
            try:
                m = self.store.get(rid).meta
            except RecordError:
                continue
            cr = m.get("criteria") or {}
            if rid.startswith("est:") and cr.get("pass") is False:
                notes.append(f"기준 미달 {m.get('part') or m.get('target')}")
            elif rid.startswith("est:") and cr and cr.get("pass") is None and cr.get("untested"):
                # 기준의 검정을 그 추정법이 계산하지 않았다 — 통과로 보지 않는다(est --adopted --adopt if_pass도 채택하지 않는다)
                notes.append(f"기준 판단 못 함 {m.get('part') or m.get('target')}" + (f"({cr['note']})" if cr.get("note") else ""))
            c = m.get("counts") or {}
            bad = (c.get("fallback") or 0) + (c.get("failed") or 0)
            if bad:
                notes.append(f"{rid} 실패 대체·실패 {bad}기")
        if notes:
            st.status = "flag"
            st.detail = " · ".join(notes) + (f" — {st.brief}" if st.brief and not st.detail else "")

    def cmd(self, line: str, where: str = None) -> StepResult:
        """명령 한 줄(등록부의 명령 — 앞의 equion은 빼도 된다)을 같은 프로세스에서. 실패하면 ScriptStop(그 종료 코드)."""
        st = self._new("cmd", line, where)
        if self._skip(st):
            return st
        try:
            st.line = self.resolve(line)
            toks = shlex.split(st.line)
        except (ScriptError, ValueError) as e:
            st.status, st.code, st.detail = "error", EXIT_SCRIPT, str(e)
            self._done(st)
            raise ScriptStop(EXIT_SCRIPT, str(e)) from None
        if toks and toks[0] == "equion":
            toks = toks[1:]
            st.line = shlex.join(toks)
        why = reg.allowed(toks, where="script")
        if why:
            st.status, st.code, st.detail = "denied", EXIT_INPUT, why
            self._done(st)
            raise ScriptStop(EXIT_INPUT, why)
        st.effects = reg.effects(toks)
        before = self._state()
        self._save_active(st)
        t0 = time.perf_counter()
        code, out, soft, warned = self._call(toks)
        st.elapsed = time.perf_counter() - t0
        st.warnings = list(dict.fromkeys(warned + _warning_lines(out)))
        st.code, st.out = code, out + ("".join(f"\n[경고] {w}" for w in warned) if warned else "")
        self._effects(st, before, self._state())
        if code != 0 and soft and code == EXIT_INPUT:
            # 명령은 '사람이 정할 것'만 남기고 끝났다(손으로 고친 결과 구역을 덮지 않음 등) — 멈추지 않고 '!'로 까닭을 남긴다
            st.status = "flag"
            st.detail = " · ".join(dict.fromkeys(soft))
            self._done(st)
            return st
        if code != 0:
            st.status = "error"
            st.detail = _error_line(out, code)
            self._done(st)
            raise ScriptStop(code, st.detail)
        self._flag(st, before.get("vintage"))
        self._done(st)
        return st

    def _env(self):
        return {"EQUION_WHO": "script", "EQUION_RUN": self.id}

    def _call(self, toks: List[str]):
        """명령 한 줄 → (종료 코드, 출력, 사람에게 넘긴 것, 경고) — 셋째는 명령이 errors.soft()로 알린 까닭들, 넷째는 파이썬 경고
        (출력의 첫 줄 — 단계 줄·실행 카드의 결과 — 을 가리지 않게 따로 모은다, 같은 경고는 하나로 · 몇 번인지)."""
        import warnings as _warnings
        from ..cli import errors
        from ..cli.commands import main as cli
        errors.LAST_SOFT = []
        buf = io.StringIO()
        old_cwd = os.getcwd()
        saved = {k: os.environ.get(k) for k in self._env()}
        os.environ.update(self._env())
        os.chdir(self.root)                          # 기록의 '명령'이 스크립트의 줄 그대로 남게
        caught = []
        try:
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf), _warnings.catch_warnings(record=True) as caught:
                _warnings.simplefilter("always")
                try:
                    code = cli(list(toks))
                except SystemExit as e:
                    code = e.code if isinstance(e.code, int) else EXIT_INPUT
                except KeyboardInterrupt:
                    raise
                except Exception:  # noqa: BLE001 — 명령의 예상 못 한 오류도 단계 오류로
                    traceback.print_exc()
                    code = EXIT_SCRIPT
        finally:
            os.chdir(old_cwd)
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
        counts: Dict[str, int] = {}
        for w in caught or []:
            key = f"{w.category.__name__}: {str(w.message).splitlines()[0][:160]}"
            counts[key] = counts.get(key, 0) + 1
        warned = [k + (f" (×{n})" if n > 1 else "") for k, n in counts.items()]
        return (code if code is not None else EXIT_OK), buf.getvalue(), list(errors.LAST_SOFT), warned

    def expect(self, target: str, cond: str, stop: bool = True, where: str = None, _source: str = None) -> StepResult:
        """확인 — target(hs·sim·est = 이 실행의 앞 단계 기록, 또는 기록 이름)의 지표가 조건을 지키나. 어긋나면 stop이면 ScriptStop(2),
        아니면 표시하고 계속. 지표: HS `Y.rmspe`·`Y.mae_pct`·`Y.mae`·`Y.me`·`failed`·`fallback` · 전망 `Y.growth[2021]`·`Y.level[2021Q4]` ·
        추정 `r2`·`dw`·`se`·`failed`(기준 미달 식 수)·`passed`·`n`."""
        source = _source or f"expect {target} {cond}" + ("" if stop else " --flag")
        st = self._new("expect", source, where)
        if self._skip(st):
            return st
        try:
            st.line = self.resolve(source)
            tgt, (metric, op, val), _ = parse_expect(shlex.split(st.line)[1:])
            if tgt in EXPECT_KINDS:
                ids = self.records(tgt)
                if not ids:
                    raise ScriptError(f"expect {tgt} — 이 실행에서 아직 {RECORD_REFS[tgt]} 기록이 없습니다")
            else:
                ids = tgt.split()
            vals = metric_values([self.store.get(i) for i in ids], metric)
        except (ScriptError, RecordError, ValueError, KeyError) as e:
            st.status, st.code, st.detail = "error", EXIT_SCRIPT, str(e.args[0] if isinstance(e, KeyError) else e)
            self._done(st)
            raise ScriptStop(EXIT_SCRIPT, st.detail) from None
        bad = [(lab, v) for lab, v in vals if not _cmp(v, op, val)]
        shown = " · ".join(f"{lab} {_fmt(v)}" for lab, v in vals[:4]) + (" …" if len(vals) > 4 else "")
        st.records = ids
        if bad:
            st.detail = f"어긋남: {' · '.join(f'{lab} {_fmt(v)}' for lab, v in bad[:4])} — 조건 {metric} {op} {_fmt(val)}"
            st.status, st.code = ("stop", EXIT_SOLVE) if stop else ("flag", EXIT_OK)
            self._done(st)
            if stop:
                raise ScriptStop(EXIT_SOLVE, st.detail)
            return st
        st.detail = f"{shown} — {metric} {op} {_fmt(val)}"
        self._done(st)
        return st

    def expect_line(self, line: str, where: str = None) -> StepResult:
        """`expect 대상 조건 [--stop·--flag]` 한 줄."""
        toks = shlex.split(line)
        stop = "--flag" not in toks
        rest = [t for t in toks[1:] if t not in ("--stop", "--flag")]
        return self.expect(rest[0] if rest else "", " ".join(rest[1:]), stop=stop, where=where, _source=line)

    def py(self, line: str, where: str = None) -> StepResult:
        """Python 단계 `py x.py [--set 이름=값 …]` — `equion run x.py`(보고서 폴더 없이)를 프로젝트 폴더에서. 명령줄에서만(python=False면 허용 안 됨)."""
        source = line if line.startswith("py ") else f"py {line}"
        st = self._new("py", source, where)
        if self._skip(st):
            return st
        try:
            st.line = self.resolve(source)
            toks = shlex.split(st.line)
        except (ScriptError, ValueError) as e:
            st.status, st.code, st.detail = "error", EXIT_SCRIPT, str(e)
            self._done(st)
            raise ScriptStop(EXIT_SCRIPT, str(e)) from None
        if not self.python:
            st.status, st.code = "denied", EXIT_INPUT
            st.detail = "Python 단계는 명령줄에서만 돈다 — 이 줄을 터미널에 붙여 넣어 주세요: equion run " + shlex.join(toks[1:])
            self._done(st)
            raise ScriptStop(EXIT_INPUT, st.detail)
        before = self._state()
        self._save_active(st)
        env = dict(os.environ, **self._env(), PYTHONIOENCODING="utf-8")    # 출력을 UTF-8로 받는다(아래 encoding과 같게)
        t0 = time.perf_counter()
        r = subprocess.run([sys.executable, "-m", "equion", "run", toks[1], "--no-report", "-q", *toks[2:]], cwd=self.root,
                           capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
        st.elapsed = time.perf_counter() - t0
        st.code, st.out = r.returncode, (r.stdout or "") + (r.stderr or "")
        self._effects(st, before, self._state())
        if r.returncode != 0:
            st.status = "error"
            st.detail = next((x.strip() for x in reversed(st.out.splitlines()) if x.strip()), f"종료 코드 {r.returncode}")
            self._done(st)
            raise ScriptStop(r.returncode, st.detail)
        self._done(st)
        return st

    # ---- 끝 ------------------------------------------------------------
    def __enter__(self):
        from ..cli.commands import _safe_streams
        _safe_streams()          # 내보낸 Python(python x.py)도 명령줄과 같은 출력 인코딩(Windows 파이프 → UTF-8)
        return self

    def __exit__(self, et, ev, tb):
        if isinstance(ev, ScriptStop):
            res = self.close(ev.code)
            if ev.code:
                # 멈춘 까닭을 알린다 — 내보낸 Python(python x.py · equion run x.py)이 말없이 끝나지 않게(.eqs 실행의 끝 줄과 같은 글)
                print(res.text(), file=sys.stderr, flush=True)
                raise SystemExit(ev.code)
            return True
        if isinstance(ev, KeyboardInterrupt):
            self.close(EXIT_INTERRUPT)
            return False
        if ev is not None:
            self.implicit.append(f"Python 오류: {type(ev).__name__}: {ev}")
            self.close(EXIT_SCRIPT)
            return False
        self.close()
        return False

    def close(self, code: int = None):
        """실행 기록을 쓴다(한 번만) — 종료 코드: 멈춘 단계의 코드 · 아니면 fail_on에 걸리면 2 · 아니면 0."""
        if self.result is not None:
            return self.result
        from .record import write_run
        if code is None:
            code = EXIT_OK
        if code == EXIT_INTERRUPT:
            self.status = "interrupted"
        elif code:
            last = next((s for s in reversed(self.steps) if s.status != "skip"), None)
            self.status = last.status if last and last.status in ("stop", "error", "denied") else "error"
        else:
            tripped = self._fail_on()
            if tripped:
                code = EXIT_SOLVE
                self.status = "error"
                self.implicit.append(f"--fail-on {self.fail_on}: {tripped}")
            else:
                self.status = "flag" if any(s.status == "flag" for s in self.steps) else "ok"
        self.exit_code = code
        self.result = write_run(self)
        from .record import release
        release(self.store, self.name)
        return self.result

    def _fail_on(self) -> str:
        kinds = FAIL_ON[self.fail_on]
        if not kinds:
            return ""
        out, seen = [], set()
        for st in self.steps:
            if st.kind == "expect":                  # 확인 단계는 앞 단계의 기록을 가리킬 뿐이다
                continue
            for rid in st.records:
                if not rid.startswith(("hs:", "sim:")) or rid in seen:
                    continue
                seen.add(rid)
                try:
                    c = self.store.get(rid).meta.get("counts") or {}
                except RecordError:
                    continue
                n = sum(int(c.get(k) or 0) for k in kinds)
                if n:
                    out.append(f"{rid} {'·'.join(kinds)} {n}기")
        return " · ".join(out)


def _error_line(out: str, code: int, max_lines: int = 8, max_chars: int = 600) -> str:
    """명령 출력에서 까닭 — 'equion: 오류:' 줄과 그 뒤의 까닭 줄(여러 줄 오류의 '  - 파일 → 출처 …' — 어느 파일·열인지)을 한 줄로 이어
    (줄 수·글자 수 한도 안에서), 없으면 경고가 아닌 마지막 줄."""
    lines = [x.rstrip() for x in (out or "").splitlines() if x.strip()]
    at = [i for i, x in enumerate(lines) if x.strip().startswith("equion: 오류:")]
    if at:
        head = lines[at[-1]].strip().replace("equion: 오류: ", "", 1)
        rest = []
        for x in lines[at[-1] + 1:]:
            if not x.startswith((" ", "\t")) or _is_warning(x):      # 들여 쓴 까닭 줄만 — 뒤의 다른 출력은 아니다
                break
            rest.append(x.strip())
        more = len(rest) > max_lines - 1
        text = " ".join([head] + rest[:max_lines - 1]) + (f" … (외 {len(rest) - max_lines + 1}줄 — 단계 출력 steps/에)" if more else "")
        return text if len(text) <= max_chars else text[:max_chars - 1] + "…"
    plain = [x.strip() for x in _split_warnings(chr(10).join(lines))[0] if x.strip()]
    return plain[-1] if plain else (lines[-1].strip() if lines else f"종료 코드 {code}")


def _cmp(v, op, x) -> bool:
    if v is None or v != v:
        return False
    return {"<": v < x, "<=": v <= x, ">": v > x, ">=": v >= x, "==": v == x, "!=": v != x}[op]


def _fmt(v) -> str:
    if v is None or v != v:
        return "없음"
    if float(v).is_integer() and abs(v) < 1e9:
        return str(int(v))
    return f"{v:.4g}"


_HS = {"rmspe": "RMSPE", "mae_pct": "MAE_pct", "mae": "MAE", "me": "mean_error", "n": "n_samples"}
_EST = {"r2": "r_squared", "adj_r2": "adj_r_squared", "dw": "durbin_watson", "se": "se_regression"}
_COUNTS = ("ok", "partial", "fallback", "failed")


def metric_values(recs, metric: str) -> List[tuple]:
    """기록들의 지표 값 [(이름, 값)] — 모든 값이 조건을 지켜야 통과. 모르는 지표는 ScriptError."""
    if not recs:
        raise ScriptError("확인할 기록이 없습니다")
    kind = recs[0].kind
    if any(r.kind != kind for r in recs):
        raise ScriptError("expect의 기록은 한 종류여야 합니다")
    m = re.match(r"^(?:([A-Za-z_]\w*)\.)?([A-Za-z_]\w*)(?:\[([\w\-]+)\])?$", metric)
    var, name, arg = m[1], m[2].lower(), m[3]
    if kind in ("hs", "sim") and var is None and name in _COUNTS:
        return [(name, float(sum(int((r.meta.get("counts") or {}).get(name) or 0) for r in recs)))]
    if kind == "hs" and var and name in _HS:
        out = []
        for r in recs:
            st = r.read_csv("stats.csv")
            idx = {str(i).lower(): i for i in st.index}
            if var.lower() not in idx:
                raise ScriptError(f"{r.id}에 {var}가 없습니다(있는 것: {', '.join(map(str, st.index[:8]))})")
            out.append((f"{var} {_HS[name]}", float(st.loc[idx[var.lower()], _HS[name]])))
        return out
    if kind == "sim" and var and name in ("growth", "level") and arg:
        out = []
        for r in recs:
            if name == "growth":
                t = r.read_csv("annual.csv")
                col = next((c for c in t.columns if c.lower() == f"{var.lower()}_증가율"), None)
                if col is None or arg not in t.index:
                    raise ScriptError(f"{r.id}의 연간 증가율에 {var}·{arg}가 없습니다")
                out.append((f"{r.meta.get('scenario')} {var} {arg} 증가율", float(t.loc[arg, col])))
            else:
                t = r.read_csv("levels.csv")
                col = next((c for c in t.columns if c.lower() == var.lower()), None)
                if col is None or arg not in t.index:
                    raise ScriptError(f"{r.id}의 수준에 {var}·{arg}가 없습니다")
                out.append((f"{r.meta.get('scenario')} {var} {arg}", float(t.loc[arg, col])))
        return out
    if kind == "est" and var is None:
        if name in ("failed", "passed", "n"):
            crit = [(r.meta.get("criteria") or {}).get("pass") for r in recs]
            v = {"failed": sum(1 for c in crit if c is False), "passed": sum(1 for c in crit if c is True), "n": len(recs)}[name]
            return [(name, float(v))]
        if name in _EST:
            return [(f"{r.meta.get('part') or r.id} {name}", float((r.meta.get("stats") or {}).get(_EST[name]) or float("nan")))
                    for r in recs]
    hint = {"hs": "Y.rmspe · Y.mae_pct · Y.mae · Y.me · failed · fallback",
            "sim": "Y.growth[연도] · Y.level[기간] · failed · fallback",
            "est": "r2 · adj_r2 · dw · se · failed · passed · n"}.get(kind, "—")
    raise ScriptError(f"{kind} 기록의 모르는 지표 {metric!r} (있는 것: {hint})")


def session(project: str = ".", **kw) -> Session:
    """스크립트 실행 하나를 연다 — with 블록으로 쓰면 끝에서 실행 기록(run:)을 남긴다. 매개변수는 `Session`과 같다.

    예
        >>> import tempfile, os
        >>> p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
        >>> with eqn.script.session(p.root, script="FLOWS/check.eqs") as s:
        ...     _ = s.cmd("assemble main")
        ...     _ = s.cmd("hs main --range 2010Q1:last")
        ...     _ = s.expect("hs", "Y.rmspe < 5%")
        >>> s.result.id, s.result.exit_code, [x.status for x in s.result.steps]
        ('run:check_0001', 0, ['ok', 'ok', 'ok'])
    """
    return Session(project, **kw)


__all__ = ["Session", "StepResult", "ScriptStop", "session", "metric_values", "find_root", "snapshot", "versions", "_q"]
