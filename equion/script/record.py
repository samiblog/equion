#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""실행 기록 `work/run/<이름>/`(`run:`) 쓰기·읽기와 결과 글."""

import os
import time
from dataclasses import dataclass, field
from typing import List, Optional

from ..reporting import markdown as md
from ..work.store import WHO_KO, now_iso
from .session import MARK, STATUS_KO, StepResult, versions

FORMAT = "equion-run"
FORMAT_VERSION = 1


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
                 + (f"  → {' · '.join(s['records'][:3])}" if s.get("records") and s["kind"] != "expect" else ""))
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
    """Session → 실행 기록."""
    elapsed = time.perf_counter() - s._t0
    end_v = _vint(s)
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
    if m.get("inbox"):
        sections.append(("받은 원자료", md.bullets([f"{i['from']} → {i['to']}" for i in m["inbox"]])))
    if m.get("implicit"):
        sections.append(("알아서 한 것", md.bullets(m["implicit"])))
    sections.append(("이 결과를 만든 스크립트", "\n".join("    " + x for x in script.rstrip().split("\n"))))
    return md.card(f"스크립트 실행 {m.get('id') or ''}".strip(), list(head.items()), sections)
