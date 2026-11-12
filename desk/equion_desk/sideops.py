"""왼쪽 목록과 명령 창의 일(작업 프로세스 안에서 돈다) — 변수 탭·분석 탭·묶음·식 더하기·명령 한 줄·명령 목록 (DESK_V2, D53).

하는 일은 패키지의 함수다: 묶음은 `Project.group_define·group_remove`, 식은 `part_add·part_remove`, 명령 한 줄은 `equion.cli.line.run_line`.
여기서는 화면이 쓰기 좋은 모양으로 묶는다(목록은 계산하지 않고 읽기만 한다).
"""
from __future__ import annotations

import difflib
import os
from typing import Any

from .dataops import command
from .modelops import _data_id, _float

_CATALOG: list | None = None


# ---- 변수 탭 ---------------------------------------------------------------------------------------

def variables(project: Any) -> dict:
    """변수 탭 — 지금 자료의 시리즈마다 이름·설명·단위·구간·끝 값·종류(원자료·파생·계절조정·자료)와 모형과의 관계, 그리고 묶음."""
    cfg = project.config
    wf = project.workfile
    frame = wf.data
    meta: dict = {}
    names = [str(c) for c in frame.columns]
    if cfg.series_file and project.vintage:
        from equion.projects.vintage import read_vintage

        try:
            vframe, _flags, vmeta = read_vintage(str(project.root), project.vintage)
            keep = {str(c).upper() for c in vframe.columns}
            names = [n for n in names if n.upper() in keep] or names
            meta = vmeta.get("series", {}) if isinstance(vmeta, dict) else {}
        except Exception:
            meta = {}
    # 모형과의 관계 — 식의 목표 · 식에 쓰임 · 모형에 든 식
    in_model: dict[str, list[str]] = {}
    for m in cfg.models:
        try:
            for part in project.parts(m):
                in_model.setdefault(part.id, []).append(m)
        except Exception:
            continue
    target_of: dict[str, list[str]] = {}
    used_in: dict[str, set[str]] = {}
    for part in project.parts():
        target_of.setdefault(part.target.upper(), []).append(part.id)
        for v in part.variables:
            used_in.setdefault(str(v).upper(), set()).add(part.id)
    rows = []
    for n in names:
        s = frame[n]
        valid = s.dropna()
        m = meta.get(n) or next((v for k, v in meta.items() if str(k).upper() == n.upper()), {}) or {}
        kind = "자료"
        if meta:
            kind = "파생" if m.get("expr") else ("계절조정" if m.get("seas") else "원자료")
        parts = target_of.get(n.upper(), [])
        model_parts = [p for p in parts if p in in_model]
        users = sorted(used_in.get(n.upper(), set()))
        model_users = [p for p in users if p in in_model]
        if model_parts:
            rel = "endo"
        elif model_users:
            rel = "exo"
        elif parts:
            rel = "single"
        elif users:
            rel = "used"
        else:
            rel = "none"
        rows.append({"name": n, "desc": str(m.get("desc") or ""), "unit": str(m.get("unit") or ""), "kind": kind,
                     "first": wf._label(valid.index[0]) if len(valid) else None, "last": wf._label(valid.index[-1]) if len(valid) else None,
                     "value": _float(valid.iloc[-1]) if len(valid) else None, "n": int(len(valid)),
                     "rel": rel, "parts": parts, "models": sorted({mm for p in model_parts for mm in in_model[p]}), "users": users[:12]})
    groups = [{"name": g.name, "series": list(g.series), "desc": g.desc, "transform": g.transform} for g in cfg.groups.values()]
    return {"variables": rows, "groups": groups, "freq": cfg.freq, "vintage": project.vintage}


def group_define(project: Any, name: str, series: list[str] | None = None, desc: str | None = None, transform: str | None = None,
                 dry: bool = False) -> dict:
    """묶음 저장(`equion group define`) — dry면 쓰지 않고 equion.toml의 차이와 명령만."""
    words = ["group", "define", name, *(["--series", ",".join(series)] if series else []), *(["--desc", desc] if desc else []),
             *(["--transform", transform] if transform is not None else [])]
    if dry:
        from equion.projects.config import group_text

        if series:
            have = {str(c).upper() for c in project.workfile.data.columns}
            missing = [v for v in series if v.upper() not in have]
            if missing:
                from equion.projects.config import ProjectError

                raise ProjectError(f"[group] {name}: 자료에 없는 시리즈 {', '.join(missing)}")
        text, new = group_text(project.config.path, name, series=series, desc=desc, transform=transform)
        with open(project.config.path, encoding="utf-8") as f:
            old = f.read()
        return {"new": new, "diff": _diff(old, text, "equion.toml"), "command": command(*words)}
    res = project.group_define(name, series=series, desc=desc, transform=transform, who="desk", command=command(*words))
    return {**res.to_dict(), "command": command(*words)}


def group_remove(project: Any, name: str) -> dict:
    res = project.group_remove(name, who="desk", command=command("group", "remove", name))
    return {**res.to_dict(), "command": command("group", "remove", name)}


def _diff(old: str, new: str, path: str) -> str:
    return "".join(difflib.unified_diff(old.splitlines(keepends=True), new.splitlines(keepends=True), f"a/{path}", f"b/{path}"))


# ---- 분석 탭 ---------------------------------------------------------------------------------------

def analysis_list(project: Any) -> dict:
    """분석 탭 — 개별 식(어느 모형도 쓰지 않는 블록의 식)과, 돌린 분석을 대상별로 묶은 가장 새 결과(낡음 표시와 함께). 계산하지 않는다."""
    from equion import registry
    from equion.projects.analyses import _tokens

    cfg = project.config
    used: set[str] = set()
    for m in cfg.models:
        try:
            used |= {p.id for p in project.parts(m)}
        except Exception:
            continue
    adopted = project.adopted
    last_est: dict[str, dict] = {}
    for rec in project.work.records("est"):
        part = rec.meta.get("part")
        if part:
            last_est[part] = {"id": rec.id, "created": rec.meta.get("created"), "pass": (rec.meta.get("criteria") or {}).get("pass")}
    singles = []
    for p in project.parts():
        if p.id in used:
            continue
        singles.append({"id": p.id, "block": p.block, "target": p.target, "kind": p.kind, "text": p.text, "desc": p.desc,
                        "adopted": adopted.get(p.id), "last": last_est.get(p.id)})
    current = project.vintage
    groups = {g.name.lower() for g in cfg.groups.values()}
    latest: dict[tuple, dict] = {}
    count: dict[tuple, int] = {}
    for rec in project.work.records("an"):
        m = rec.meta
        key = (m.get("analysis"), str(m.get("target")))
        count[key] = count.get(key, 0) + 1
        latest[key] = {"id": rec.id, "analysis": m.get("analysis"), "label": m.get("label"), "target": m.get("target"),
                       "target_label": m.get("target_label"), "line": (m.get("lines") or [""])[0], "created": m.get("created"),
                       "who": m.get("who"), "options": m.get("options") or {}, "smpl": m.get("smpl"), "vintage": _data_id(m),
                       "stale": bool(current and _data_id(m) and _data_id(m) != current), "makes": (m.get("makes") or {}).get("kind")}
    results = []
    for key, row in latest.items():
        try:
            spec = registry.get(row["analysis"])
            group, cnt, targets = spec.group, spec.count, tuple(spec.targets)
        except KeyError:
            group, cnt, targets = "", "any", ()
        target = str(row["target"])
        if any(t in ("series", "group", "expr", "assign") for t in targets) or not targets:
            scope = "many" if (target.lower() in groups or len(_tokens(target)) > 1) else "one"
        elif any(t in ("part", "est") for t in targets):
            scope = "eq"
        elif "records" in targets:
            scope = "records"
        else:
            scope = "model"
        results.append({**row, "group": group, "count": cnt, "runs": count[key], "scope": scope})
    results.sort(key=lambda r: str(r.get("created") or ""), reverse=True)
    blocks = [{"name": b.name, "desc": b.desc, "used": any(b.name in (cfg.models[m].blocks or []) for m in cfg.models)} for b in cfg.blocks.values()]
    return {"singles": singles, "results": results, "blocks": blocks, "vintage": current}


# ---- 식 더하기·빼기 -----------------------------------------------------------------------------------

def part_add(project: Any, block: str, text: str, desc: str | None = None, from_part: str | None = None, record: str | None = None,
             create: bool = False, dry: bool = False) -> dict:
    """블록에 식 한 줄(`equion block add`) — dry면 쓰지 않고 바뀔 줄과 명령만. create면 없는 블록을 먼저 만든다(개별 식 블록).
    record(est:)를 주면 더한 식에 그 기록을 채택한다(계수 그대로 — ECM·VAR이 낸 식 후보를 모형에 넣을 때)."""
    from equion.projects.config import ProjectError
    from equion.projects.partedit import add_text, remove_text

    words = ["block", "add", block, text, *(["--desc", desc] if desc else []), *(["--from", from_part] if from_part else [])]
    if dry:
        if block not in project.config.blocks:
            if not create:
                raise ProjectError(f"없는 블록 {block!r}")
            return {"diff": f"+++ b/EQUATIONS/{block}.txt\n+{text}" + (f"   # {desc}" if desc else "") + "\n", "part": None,
                    "command": command("block", "define", block) + " · " + command(*words), "new_block": True}
        new, pid, rel, _line = add_text(project, block, text, desc)
        path = os.path.join(str(project.root), *rel.split("/"))
        with open(path, encoding="utf-8") as f:
            old = f.read()
        diff = _diff(old, new, rel)
        if from_part:
            rtext, rrel, _ = remove_text(project, from_part)
            with open(os.path.join(str(project.root), *rrel.split("/")), encoding="utf-8") as f:
                diff += _diff(f.read(), rtext, rrel)
        return {"diff": diff, "part": pid, "command": command(*words), "new_block": False}
    made_block = None
    if block not in project.config.blocks:
        if not create:
            raise ProjectError(f"없는 블록 {block!r}")
        made_block = project.block_define(block, desc="개별 식", who="desk",
                                          command=command("block", "define", block)).change
    res = project.part_add(block, text, desc=desc, from_part=from_part, who="desk", command=command(*words))
    out = {**res.to_dict(), "command": command(*words), "block_change": made_block, "adopted": None}
    if record:
        try:
            done = project.adopt(record, part=res.part, who="desk", command=command("adopt", record, "--part", res.part))
            out["adopted"] = done.to_dict() if hasattr(done, "to_dict") else {"record": record}
        except Exception as exc:  # 채택을 못 해도 식은 더해졌다 — 까닭을 알린다
            out["adopt_error"] = str(exc)
    return out


def part_remove(project: Any, part: str) -> dict:
    res = project.part_remove(part, who="desk", command=command("block", "remove", part))
    return {**res.to_dict(), "command": command("block", "remove", part)}


# ---- 명령 창 ---------------------------------------------------------------------------------------

def line(project: Any, text: str) -> dict:
    """명령 한 줄(`equion …`과 같다) — 출력 글·새 기록·새 바뀜 기록. 기록의 '누가'는 Desk."""
    from equion.cli.line import run_line

    return run_line(str(project.root), text, who="desk").to_dict()


def catalog(project: Any) -> dict:
    """자동 완성의 재료 — 명령·옵션 목록(명령줄 정의에서)과 지금 프로젝트의 이름들(부품·모형·블록·묶음·시리즈·기록·회차·스크립트)."""
    global _CATALOG
    from equion import registry
    from equion.cli.line import catalog as commands

    if _CATALOG is None:
        _CATALOG = commands()
    cfg = project.config
    names = {
        "parts": [p.id for p in project.parts()], "models": list(cfg.models), "blocks": list(cfg.blocks), "groups": list(cfg.groups),
        "series": [str(c) for c in project.workfile.data.columns][:600],
        "records": [r["id"] for r in project.work.log()][-300:][::-1],
        "vintages": [v["id"] for v in project.data_list()] if cfg.series_file else [],
        "scenarios": sorted(os.path.splitext(f)[0] for f in _ls(project, "SCENARIOS") if f.lower().endswith(".toml")),
        "scripts": sorted(f"FLOWS/{f}" for f in _ls(project, "FLOWS") if f.lower().endswith(".eqs")),
        "reports": sorted(os.path.splitext(f)[0] for f in _ls(project, "reports") if f.lower().endswith(".md")),
        "analyses": [{"name": a.name, "label": a.label, "count": a.count, "targets": list(a.targets)} for a in registry.analyses()],
    }
    return {"commands": _CATALOG, "names": names}


def _ls(project: Any, folder: str) -> list[str]:
    try:
        return os.listdir(os.path.join(str(project.root), folder))
    except OSError:
        return []
