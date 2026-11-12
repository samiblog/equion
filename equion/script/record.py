#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""실행 기록 `work/run/<이름>/`(`run:`) 쓰기·읽기와 결과 글."""

import json
import os
import re
import time
from dataclasses import dataclass, field, fields
from datetime import datetime
from types import SimpleNamespace
from typing import List, Optional, Set

from ..reporting import markdown as md
from ..work.store import WHO_KO, RecordError, WorkStore, move_into_place, now_iso
from .session import EXIT_INTERRUPT, MARK, STATUS_KO, StepResult, versions

FORMAT = "equion-run"
FORMAT_VERSION = 1
ACTIVE = ".active"          # work/run/.active/<이름>.json — 도는 실행이 이름을 잡아 두고 단계마다 상태를 적는 곳
_HERE: Set[tuple] = set()   # 이 프로세스에서 지금 도는 실행 (프로젝트, 이름)


# ---------------------------------------------------------------------------
# 도는 실행 — 이름 잡기 · 상태 · 끝나지 못한 실행의 기록
# ---------------------------------------------------------------------------
def _active_dir(store) -> str:
    return os.path.join(store.dir("run"), ACTIVE)


def active_names(store) -> Set[str]:
    """지금 돌거나 끝나지 못한 실행이 잡아 둔 이름."""
    try:
        return {n[:-5] for n in os.listdir(_active_dir(store)) if n.endswith(".json")}
    except OSError:
        return set()


def next_run_name(store, prefix: str) -> str:
    """prefix_0001 … — 남은 실행 기록과 잡아 둔 이름(도는 실행·끝나지 못한 실행) 모두의 가장 큰 번호 다음."""
    rx = re.compile(rf"^{re.escape(prefix)}_(\d+)$")
    names = set(store.names("run")) | active_names(store)
    nums = [int(m[1]) for n in names for m in [rx.match(n)] if m]
    return f"{prefix}_{(max(nums) if nums else 0) + 1:04d}"


def reserve(store, name: Optional[str], prefix: str) -> str:
    """실행 이름을 잡는다 → 이름. 이름을 주지 않으면 다음 번호(다른 프로세스가 같은 번호를 먼저 잡으면 그다음). 이미 있는 기록이나
    지금 도는 실행의 이름이면 RecordError — 실행 기록의 이름은 다시 쓰지 않는다(그 이름을 가리키는 바뀜 기록이 있을 수 있다)."""
    d = _active_dir(store)
    os.makedirs(d, exist_ok=True)
    for _ in range(50):
        nm = name or next_run_name(store, prefix)
        store.check_new("run", nm)
        try:
            fd = os.open(os.path.join(d, nm + ".json"), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            if name:
                raise RecordError(f"지금 도는(또는 끝나지 못한) 실행이 이 이름을 씁니다: run:{nm} — 다른 이름으로") from None
            continue
        os.close(fd)
        _HERE.add((os.path.normcase(store.root), nm))
        return nm
    raise RecordError(f"실행 이름을 잡지 못했습니다(run:{prefix}_…)")


def save_active(s, current: StepResult = None) -> None:
    """도는 실행의 상태를 적는다(단계마다) — 프로세스가 끝나 버려도(Desk의 '취소' 등) 다음 실행이 이것으로 기록을 남긴다."""
    state = {"format": "equion-run-active", "pid": os.getpid(), "name": s.name, "id": s.id, "project": s.p.name,
             "who": s.who, "command": s.command, "script": s.script, "title": s.title, "params": s.params,
             "from": s.from_step, "today": s.today, "fail_on": s.fail_on, "origin": s.origin, "replay_of": s.replay_of,
             "vintage0": s.vintage0, "data0": s.data0, "started": now_iso(s.started), "updated": now_iso(),
             "elapsed": round(time.perf_counter() - s._t0, 2), "lines": list(s.lines), "implicit": list(s.implicit),
             "steps": [dict(x.to_dict(), out=x.out) for x in s.steps],
             "current": dict(current.to_dict(), status="interrupted") if current is not None else None}
    path = os.path.join(_active_dir(s.store), s.name + ".json")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(state, ensure_ascii=False, default=str))
    move_into_place(tmp, path)


def release(store, name: str) -> None:
    """실행이 끝나 기록을 남겼다 — 잡아 둔 이름을 놓는다."""
    _HERE.discard((os.path.normcase(store.root), name))
    for fn in (name + ".json", name + ".json.tmp"):
        try:
            os.remove(os.path.join(_active_dir(store), fn))
        except OSError:
            pass


def _pid_alive(pid) -> bool:
    """그 프로세스가 아직 있나(모르면 있다고 본다 — 도는 실행을 끝난 것으로 적지 않게)."""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if os.name == "nt":
        import ctypes
        k = ctypes.WinDLL("kernel32", use_last_error=True)
        h = k.OpenProcess(0x1000, False, pid)             # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return ctypes.get_last_error() == 5             # 권한 없음 = 프로세스는 있다
        try:
            code = ctypes.c_ulong()
            if not k.GetExitCodeProcess(h, ctypes.byref(code)):
                return True
            return code.value == 259                        # STILL_ACTIVE
        finally:
            k.CloseHandle(h)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        return True
    return True


def _running(store, state: dict) -> bool:
    if state.get("pid") == os.getpid():
        return (os.path.normcase(store.root), state.get("name")) in _HERE
    return _pid_alive(state.get("pid"))


def recover(root: str) -> List[str]:
    """끝나지 못한 실행(프로세스가 끝났는데 기록이 없는 것 — Desk의 '취소'·창 닫기·강제 종료)의 실행 기록을 남긴다 → 남긴 기록 이름들.

    기록은 그때까지 끝난 단계와 하던 단계(그 단계가 만든 기록 — 기록의 run이 이 실행인 것), 상태 '끝나지 못함(취소·중단)'·종료 코드 130.
    정의 사본(defs/)이 없어 다시 하기(--replay)는 안 된다. 도는 실행(다른 프로세스·이 프로세스)은 건드리지 않는다."""
    store = WorkStore(root)
    d = _active_dir(store)
    if not os.path.isdir(d):
        return []
    made = []
    for fn in sorted(os.listdir(d)):
        if not fn.endswith(".json"):
            continue
        name = fn[:-5]
        try:
            with open(os.path.join(d, fn), encoding="utf-8") as f:
                text = f.read()
            state = json.loads(text) if text.strip() else None
        except (OSError, ValueError):
            continue
        if state is None:                    # 이름만 잡고 아직 쓰기 전 — 도는 중일 수 있다(하루가 지났으면 놓는다)
            try:
                if time.time() - os.path.getmtime(os.path.join(d, fn)) > 86400:
                    release(store, name)
            except OSError:
                pass
            continue
        if store.exists("run", name):        # 기록은 남았고 이름만 덜 놓였다
            release(store, name)
            continue
        if _running(store, state):
            continue
        made.append(_write_cancelled(store, name, state))
        release(store, name)
    return made


def _step(d: dict) -> StepResult:
    keys = {f.name for f in fields(StepResult)}
    return StepResult(**{k: v for k, v in d.items() if k in keys})


def _write_cancelled(store, name: str, state: dict) -> str:
    steps = [_step(x) for x in state.get("steps") or []]
    cur = state.get("current")
    done = {r for st in steps for r in st.records}
    rid = state.get("id") or f"run:{name}"
    if cur and not any(st.n == cur.get("n") for st in steps):
        st = _step(cur)
        st.status, st.code = "interrupted", None
        st.detail = "이 단계 도중에 끝났습니다(취소·프로세스 끝남)"
        st.records = [x["id"] for x in store.log() if x.get("run") == rid and x["id"] not in done]
        steps.append(st)
    last = next((st for st in reversed(steps) if st.status != "skip"), None)
    implicit = list(state.get("implicit") or []) + [
        "끝나지 못한 실행 — " + (f"[{last.n}] {last.line} " if last else "") + "에서 취소되었거나 프로세스가 끝났습니다. 그때까지의 단계와 "
        "기록만 남겼습니다(정의 파일·자료 회차는 그 단계까지 바뀌었을 수 있다 — equion history list). 다시 하려면 스크립트를 새로 돌린다"]
    try:
        started = datetime.fromisoformat(state.get("started"))
    except (TypeError, ValueError):
        started = datetime.now()
    s = SimpleNamespace(
        _t0=None, elapsed=state.get("elapsed") or 0.0, who=state.get("who"), command=state.get("command"), script=state.get("script"),
        p=SimpleNamespace(name=state.get("project")), title=state.get("title") or "", params=state.get("params") or {},
        from_step=state.get("from"), today=state.get("today"), fail_on=state.get("fail_on") or "failed", status="cancelled",
        exit_code=EXIT_INTERRUPT, steps=steps, vintage0=state.get("vintage0"), data0=state.get("data0"), implicit=implicit,
        replay_of=state.get("replay_of"), origin=state.get("origin") or "eqs", started=started, name=name, id=rid, sources={}, defs={},
        store=store, root=store.root, lines=state.get("lines") or [], created=state.get("updated"),
        end_vintage=next((st.vintage for st in reversed(steps) if st.vintage), None) or state.get("vintage0"))
    return write_run(s).id


@dataclass
class RunResult:
    """스크립트 실행 결과 — `.id`(run:…) · `.exit_code` · `.status` · `.steps`(단계마다 StepResult) · `.text()`."""

    id: str
    exit_code: int
    status: str
    steps: List[StepResult]
    path: str = ""
    meta: dict = field(default_factory=dict)

    @property
    def flags(self) -> List[StepResult]:
        """표시한 단계(!)."""
        return [s for s in self.steps if s.status == "flag"]

    @property
    def records(self) -> List[str]:
        """이 실행이 만든 기록(단계 순)."""
        return [r for s in self.steps if s.kind != "expect" for r in s.records]

    def text(self) -> str:
        """명령줄에 보이는 끝 줄(단계 줄은 실행하면서 보인다)."""
        m = self.meta
        L = [f"기록  {self.id} · 단계 {len([s for s in self.steps if s.status != 'skip'])}"
             + (f" · 표시 {len(self.flags)}" if self.flags else "")
             + (f" · {STATUS_KO.get(self.status, self.status)}" if self.status not in ("ok", "flag") else "")
             + f" · 종료 코드 {self.exit_code}"
             + (f" · 자료 회차 {m.get('vintage', {}).get('start')} → {m['vintage']['end']}"
                if (m.get("vintage") or {}).get("start") != (m.get("vintage") or {}).get("end") else "")]
        for s in self.steps:
            if s.status in ("stop", "error", "denied"):
                L.append(f"  멈춘 단계 [{s.n}] {s.line} — {s.detail}")
        for x in m.get("implicit") or []:
            L.append(f"  알아서 한 것  {x}")
        return "\n".join(L)

    def to_dict(self) -> dict:
        """명령줄 --json과 같은 사전."""
        return {"id": self.id, "exit_code": self.exit_code, "status": self.status, "path": self.path,
                "steps": [s.to_dict() for s in self.steps], "records": self.records,
                "flags": [s.n for s in self.flags], "implicit": self.meta.get("implicit") or []}

    def __repr__(self):
        return f"<실행 기록 {self.id}: {STATUS_KO.get(self.status, self.status)} · 종료 코드 {self.exit_code}>"


def run_text(m: dict) -> str:
    """실행 기록의 짧은 글(equion work show run:…)."""
    if m.get("replay_of"):
        L = [f"[{m['id']}] 재연 ← {m['replay_of']} · " + ("모두 같음" if m.get("same") else "다른 단계가 있음")]
        L += [f"  [{s['n']}] {'=' if s['verdict'] == '같음' else '≠'} {s['line']}" + (f"  — {s['detail']}" if s.get("detail") else "")
              for s in m.get("steps") or []]
        return "\n".join(L)
    v = m.get("vintage") or {}
    L = [f"[{m['id']}] {m.get('script') or '(Python)'} · {STATUS_KO.get(m.get('status'), m.get('status'))} · 종료 코드 {m.get('exit_code')}"
         + (f" · 자료 회차 {v.get('start')} → {v.get('end')}" if v.get("start") != v.get("end") else f" · 자료 회차 {v.get('end')}")]
    if m.get("params"):
        L.append("  매개변수  " + " · ".join(f"{k} = {' '.join(x)}" for k, x in m["params"].items()))
    for s in m.get("steps") or []:
        L.append(f"  [{s['n']}] {MARK.get(s['status'], '?')} {s['line']}" + (f"  — {s['detail']}" if s.get("detail") else "")
                 + (f"  → {' · '.join(s['records'][:3])}" + (f" 외 {len(s['records']) - 3}" if len(s["records"]) > 3 else "")
                    if s.get("records") and s["kind"] != "expect" else ""))
    L += [f"  알아서 한 것  {x}" for x in m.get("implicit") or []]
    return "\n".join(L)


def resolved_script(s) -> str:
    """값을 바꿔 넣은 뒤의 스크립트(script.eqs)."""
    head = [f"# {s.id} — {s.script or '(Python에서)'}" + (f" · {s.title}" if s.title else ""),
            f"# 값을 바꿔 넣은 뒤의 줄 · {now_iso(s.started)} · 자료 회차 {s.vintage0 or '-'} → {_vint(s)}"]
    for k, v in s.params.items():
        head.append(f"# param {k} = {' '.join(v)}")
    if s.from_step:
        head.append(f"# --from {s.from_step} (앞 단계는 건너뜀)")
    body = [x for x in s.lines]
    while body and not body[0].strip():
        body.pop(0)
    return "\n".join(head + [""] + body).rstrip() + "\n"


def _vint(s):
    from ..projects import Project
    try:
        return Project.open(s.root).vintage or "-"
    except Exception:  # noqa: BLE001
        return "-"


def write_run(s) -> RunResult:
    """Session → 실행 기록(끝나지 못한 실행은 recover가 그 상태로 만든 것을 받는다)."""
    elapsed = s.elapsed if getattr(s, "_t0", None) is None else time.perf_counter() - s._t0
    end_v = getattr(s, "end_vintage", None) or _vint(s)
    meta = {"who": s.who, "command": s.command or f"(Python) {s.script or ''}".strip(), "project": s.p.name,
            "equion": versions()["equion"], "versions": versions(), "target": s.script or "(Python)",
            "script": s.script, "title": s.title, "params": s.params, "from": s.from_step, "today": s.today,
            "fail_on": s.fail_on, "status": s.status, "exit_code": s.exit_code,
            "steps": [x.to_dict() for x in s.steps], "records": [r for x in s.steps if x.kind != "expect" for r in x.records],
            "changes": [c for x in s.steps for c in x.changes], "flags": [x.n for x in s.steps if x.status == "flag"],
            "vintage": {"start": s.vintage0, "end": end_v}, "data": s.data0, "implicit": list(dict.fromkeys(s.implicit)),
            "inbox": [i for x in s.steps for i in x.inbox], "replay_of": s.replay_of, "origin": s.origin,
            "started": now_iso(s.started), "elapsed": round(elapsed, 2), "python_steps": [x.n for x in s.steps if x.kind == "py"],
            "path": f"work/run/{s.name}", "id": s.id}
    if getattr(s, "created", None):
        meta["created"] = s.created
    files = {"script.eqs": resolved_script(s)}
    for rel, data in s.sources.items():
        files[f"src/{rel}"] = data
    for rel, data in s.defs.items():
        files[f"defs/{rel}"] = data
    for x in s.steps:
        if x.out:
            files[f"steps/{x.n:02d}.txt"] = x.out
    summary = run_md(meta, s.steps, files["script.eqs"])
    rec = s.store.write("run", s.name, meta, files, summary,
                        log={"metric": f"단계 {len([x for x in s.steps if x.status != 'skip'])} · "
                                       f"표시 {len(meta['flags'])} · 종료 코드 {s.exit_code}",
                             "status": s.status})
    return RunResult(rec.id, s.exit_code, s.status, s.steps, rec.path, rec.meta)


def run_md(m: dict, steps: List[StepResult], script: str) -> str:
    """실행 기록 카드."""
    head = {"기록": m.get("id") or "", "스크립트": m.get("script") or "(Python)", "상태": STATUS_KO.get(m["status"], m["status"]),
            "종료 코드": m["exit_code"], "누가": WHO_KO.get(m.get("who"), m.get("who")), "명령": f"`{m.get('command')}`",
            "자료 회차": f"{m['vintage']['start'] or '-'} → {m['vintage']['end'] or '-'}", "판": f"equion {m['equion']}",
            "걸린 시간": f"{m['elapsed']}초"}
    if m.get("params"):
        head["매개변수"] = " · ".join(f"{k} = {' '.join(v)}" for k, v in m["params"].items())
    if m.get("replay_of"):
        head["다시 한 것"] = m["replay_of"]
    import pandas as pd
    rows = pd.DataFrame([{"단계": x.n, "묶음": x.section, "줄": f"`{x.line}`", "": MARK[x.status],
                          "기록": " · ".join(x.records[:4]) + (" …" if len(x.records) > 4 else ""),
                          "결과": (x.brief or "")[:120]} for x in steps]).set_index("단계") if steps else pd.DataFrame()
    sections = [("단계", md.table(rows) if len(rows) else "(단계 없음)")]
    flags = [x for x in steps if x.status in ("flag", "stop", "error", "denied")]
    if flags:
        sections.append(("볼 것", md.bullets([f"[{x.n}] {STATUS_KO[x.status]} — `{x.line}` — {x.detail}" for x in flags])))
    warned = [f"[{x.n}] {w}" for x in steps for w in (getattr(x, "warnings", None) or [])]
    if warned:                                   # 경고는 결과 줄을 가리지 않게 따로(단계 출력 steps/NN.txt에도 있다)
        sections.append(("경고", md.bullets(warned[:40] + ([f"… 외 {len(warned) - 40}"] if len(warned) > 40 else []))))
    if m.get("inbox"):
        sections.append(("받은 원자료", md.bullets([f"{i['from']} → {i['to']}" for i in m["inbox"]])))
    if m.get("implicit"):
        sections.append(("알아서 한 것", md.bullets(m["implicit"])))
    sections.append(("이 결과를 만든 스크립트", "\n".join("    " + x for x in script.rstrip().split("\n"))))
    return md.card(f"스크립트 실행 {m.get('id') or ''}".strip(), list(head.items()), sections)
