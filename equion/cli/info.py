#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`equion info` — 경로의 요약(데이터 파일·워크파일 .eqw·옛 번들 .wt·방정식 파일·보고서 폴더).

경로가 없으면 설치·실행 환경(버전·BLAS·스레드)을 보인다.
"""

import json
import os
from collections import Counter

from .report import FORMAT as RUN_FORMAT
from .report import LEGACY_FORMATS as RUN_LEGACY
from .report import platform_info, threads_info, versions


def _read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def environment() -> dict:
    return {"kind": "environment", "versions": versions(), "platform": platform_info(),
            "threads": threads_info() or "(지정 없음)"}


def describe_data(path: str, freq: str = None, show_all: bool = False) -> dict:
    from ..workfile import output as _output
    from ..workfile.workfile import wfopen
    old = _output.verbose()
    _output.verbose(0)
    try:
        wf = wfopen(path, freq=freq)
    finally:
        _output.verbose(old)
    df = wf.data
    last = {}
    for c in df.columns:
        v = df[c].dropna()
        last[c] = wf._label(v.index[-1]) if len(v) else None
    groups = Counter(v or "(값 없음)" for v in last.values())
    out = {"kind": "data", "path": path, "name": wf.name, "freq": wf.freq,
           "range": f"{wf._label(wf.index[0])}~{wf._label(wf.index[-1])}", "periods": len(df),
           "series": len(df.columns),
           "last_observation": dict(sorted(groups.items(), key=lambda kv: -kv[1]))}
    if show_all:
        out["series_last"] = last
    return out


def describe_workfile(path: str) -> dict:
    man = _read_json(os.path.join(path, "workfile.json"))
    objs = man.get("objects", [])
    kinds = Counter(o["type"] for o in objs)
    from ..data.store import read_frame
    df = read_frame(path, "data")
    return {"kind": "workfile", "path": path, "name": man.get("name"), "freq": man.get("freq"),
            "saved_at": man.get("saved_at"), "engine_version": man.get("engine_version"),
            "smpl": man.get("smpl"), "periods": len(df), "series": len(df.columns),
            "objects": dict(kinds),
            "models": {o["name"]: {"equations": len(o.get("equations", [])),
                                   "identities": len(o.get("identities", [])),
                                   "scenarios": [s["name"] for s in o.get("scenarios", [])]}
                       for o in objs if o["type"] == "model"}}


def describe_worktable(path: str) -> dict:
    man = _read_json(os.path.join(path, "worktable.json"))
    keep = ("name", "freq", "format_version", "engine_version", "saved_at")
    out = {"kind": "worktable", "path": path, **{k: man.get(k) for k in keep if k in man}}
    for k in ("equations", "identities"):
        if isinstance(man.get(k), list):
            out[k] = len(man[k])
    return out


def describe_equations(path: str) -> dict:
    from ..formula.parser import classify_line
    from ..worktable.freq import parse_equation_file
    est, ids = parse_equation_file(path)
    kinds = Counter(classify_line(x) for x in est)
    return {"kind": "equations", "path": path, "estimated": kinds.get("estimated", 0),
            "nls": kinds.get("nls", 0), "identities": len(ids)}


def describe_report(path: str) -> dict:
    man = _read_json(os.path.join(path, "manifest.json"))
    tot = Counter()
    for s in man.get("solves", []):
        tot.update(s.get("counts", {}))
    return {"kind": "report", "path": path, "run_id": man.get("run_id"), "script": man.get("script"),
            "status": man.get("status"), "exit_code": man.get("exit_code"),
            "started_at": man.get("started_at"), "elapsed_sec": man.get("elapsed_sec"),
            "params": man.get("params", {}).get("resolved"), "solves": len(man.get("solves", [])),
            "period_status": dict(tot), "outputs": len(man.get("outputs", [])),
            "inputs": [d["path"] for d in man.get("inputs", [])],
            "versions": man.get("versions", {}).get("equion") or man.get("versions", {}).get("macromodel")}


def describe(path: str = None, freq: str = None, show_all: bool = False) -> dict:
    if not path:
        return environment()
    p = path.rstrip("/\\")
    if os.path.isdir(p):
        if os.path.isfile(os.path.join(p, "manifest.json")) and \
                _read_json(os.path.join(p, "manifest.json")).get("format") in (RUN_FORMAT, *RUN_LEGACY):
            return describe_report(p)
        if os.path.isfile(os.path.join(p, "workfile.json")):
            return describe_workfile(p)
        if os.path.isfile(os.path.join(p, "worktable.json")):
            return describe_worktable(p)
        raise ValueError(f"알 수 없는 폴더입니다(워크파일·번들·보고서가 아님): {path}")
    if not os.path.exists(p):
        raise FileNotFoundError(f"파일이 없습니다: {path}")
    if p.lower().endswith((".xlsx", ".xls", ".csv")):
        return describe_data(p, freq=freq, show_all=show_all)
    if p.lower().endswith(".txt"):
        return describe_equations(p)
    raise ValueError(f"알 수 없는 파일 형식입니다: {path}")


_LABELS = {"kind": "종류", "path": "경로", "name": "이름", "freq": "주기", "range": "기간", "periods": "기간 수",
           "series": "시리즈", "last_observation": "마지막 관측(기간: 시리즈 수)", "series_last": "시리즈별 마지막 관측",
           "saved_at": "저장 시각", "engine_version": "엔진 버전", "smpl": "표본", "objects": "객체",
           "models": "모델", "estimated": "추정식", "nls": "NLS 식", "identities": "항등식", "equations": "방정식",
           "run_id": "실행 ID", "script": "스크립트", "status": "상태", "exit_code": "종료 코드",
           "started_at": "시작", "elapsed_sec": "소요(초)", "params": "매개변수", "solves": "풀이 수",
           "period_status": "기간 상태 합계", "outputs": "출력 수", "inputs": "입력 파일", "versions": "버전",
           "platform": "플랫폼", "threads": "스레드 설정", "format_version": "형식 버전"}
_KINDS = {"environment": "실행 환경", "data": "데이터 파일", "workfile": "워크파일", "worktable": "Work Table 번들",
          "equations": "방정식 파일", "report": "실행 보고서"}


def to_text(info: dict) -> str:
    lines = []
    for k, v in info.items():
        label = _LABELS.get(k, k)
        if k == "kind":
            v = _KINDS.get(v, v)
        if isinstance(v, dict):
            lines.append(f"{label}:")
            for kk, vv in v.items():
                lines.append(f"  {kk}: {vv}")
        elif isinstance(v, list):
            lines.append(f"{label}: " + (", ".join(map(str, v)) if v else "(없음)"))
        else:
            lines.append(f"{label}: {v}")
    return "\n".join(lines)
