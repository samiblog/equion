"""혼자 하는 폼과 노트(작업 프로세스 안에서 돈다) — 후보 묶음 · 시나리오 폼 · 노트 화면 · 같은 분석의 두 기록 (2차판, D56~D58).

하는 일은 패키지의 함수다: 추정은 `Project.est`, 시나리오는 `scenario_define·scenario_remove`, 노트는 `note_add·note_run·note_check`.
여기서는 화면이 쓰기 좋은 모양으로 묶는다(차이 미리보기·진행 알림).
"""
from __future__ import annotations

import difflib
import os
from typing import Any

from .dataops import command


def _diff(old: str, new: str, path: str) -> str:
    return "".join(difflib.unified_diff(old.splitlines(keepends=True), new.splitlines(keepends=True), f"a/{path}", f"b/{path}"))


# ---- 후보 묶음 ----------------------------------------------------------------------------------------

def est_batch(project: Any, part: str, texts: list[str], smpl: str | None = None, sim: bool = False, cov: str | None = None,
              notify: Any = None) -> dict:
    """식 여러 개를 차례로 추정해 그 부품의 후보로 남긴다(`equion est '식' --for 부품`을 줄마다). 하나가 틀려도 나머지는 한다."""
    made, failed = [], []
    for i, text in enumerate(texts):
        if notify:
            notify(line=f"[{i}/{len(texts)}] {text}")
        words = ["est", text, "--for", part, *(["--smpl", smpl] if smpl else []), *(["--sim"] if sim else []), *(["--cov", cov] if cov else [])]
        try:
            rec = project.est(text, part=part, smpl=smpl or None, sim=bool(sim), cov=cov or None, who="desk", command=command(*words))
            made.append({"id": rec.id, "text": text})
        except Exception as exc:  # 식 하나의 문제(문법·자료)는 그 줄만 — 까닭을 돌려준다
            failed.append({"text": text, "error": str(exc.args[0]) if isinstance(exc, KeyError) and exc.args else str(exc)})
    if notify:
        notify(line=f"[{len(texts)}/{len(texts)}] 끝")
    return {"part": part, "made": made, "failed": failed, "id": made[-1]["id"] if made else None,
            "lines": [command("est", t, "--for", part, *(["--smpl", smpl] if smpl else []), *(["--sim"] if sim else []),
                              *(["--cov", cov] if cov else [])).replace("equion ", "", 1) for t in texts]}


# ---- 시나리오 폼 ----------------------------------------------------------------------------------------

def scenario_info(project: Any) -> dict:
    """시나리오 폼의 재료 — 시나리오들 · 가정 세트 · 보정항 · 모형 · 고를 수 있는 변수와 식 · 전망 구간."""
    from equion.projects.scenarios import _names

    cfg = project.config
    fc = getattr(cfg, "forecast", None) or {}
    return {"scenarios": project.scenarios(), "assumptions": _names(project.root, "ASSUMPTIONS", ".csv"),
            "addfactor_sets": _names(project.root, "ADDFACTORS", ".toml"), "models": list(cfg.models),
            "series": [str(c) for c in project.workfile.data.columns][:800], "parts": [p.id for p in project.parts() if p.kind == "equation"],
            "forecast": dict(fc) if isinstance(fc, dict) else {}}


def _scenario_words(name, desc, base, addfactors, model, shocks, addfactor) -> list:
    from equion.projects.scenarios import addfactor_word, parse_addfactor, parse_shock, shock_word

    words: list[Any] = ["scenario", "define", name]
    for flag, value in (("--desc", desc), ("--base", base), ("--addfactors", addfactors), ("--model", model)):
        if value is not None:
            words += [flag, value]
    if shocks is not None and not shocks and addfactor is not None and not addfactor:
        words.append("--clear")
    for s in shocks or []:
        words += ["--shock", shock_word(parse_shock(s) if isinstance(s, str) else s)]
    for a in addfactor or []:
        words += ["--addfactor", addfactor_word(parse_addfactor(a) if isinstance(a, str) else a)]
    return words


def scenario_define(project: Any, name: str, desc: str | None = None, base: str | None = None, addfactors: str | None = None,
                    model: str | None = None, shocks: list | None = None, addfactor: list | None = None, dry: bool = False) -> dict:
    """시나리오 쓰기(`equion scenario define`) — dry면 쓰지 않고 차이와 명령만."""
    from equion.projects.scenarios import scenario_text

    words = _scenario_words(name, desc, base, addfactors, model, shocks, addfactor)
    if dry:
        text, new, raw = scenario_text(project, name, desc=desc, base=base, addfactors=addfactors, model=model, shocks=shocks, addfactor=addfactor)
        rel = f"SCENARIOS/{name}.toml"
        path = os.path.join(str(project.root), "SCENARIOS", f"{name}.toml")
        old = ""
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as f:
                old = f.read()
        return {"new": new, "diff": _diff(old, text, rel), "command": command(*words), "file": rel,
                "shocks": len(raw.get("shock") or []), "addfactor": len(raw.get("addfactor") or [])}
    res = project.scenario_define(name, desc=desc, base=base, addfactors=addfactors, model=model, shocks=shocks, addfactor=addfactor,
                                  who="desk", command=command(*words))
    return {**res.to_dict(), "command": command(*words)}


def scenario_remove(project: Any, name: str) -> dict:
    res = project.scenario_remove(name, who="desk", command=command("scenario", "remove", name))
    return {**res.to_dict(), "command": command("scenario", "remove", name)}


# ---- 노트 ----------------------------------------------------------------------------------------------

def _note_files(root: str) -> list[str]:
    out = []
    base = os.path.join(root, "notes")
    for dirpath, dirnames, files in os.walk(base):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith((".", "_")))
        for f in sorted(files):
            if f.lower().endswith(".md"):
                out.append(os.path.relpath(os.path.join(dirpath, f), root).replace(os.sep, "/"))
    return out[:200]


def notes(project: Any) -> dict:
    """노트 목록(`notes/**/*.md`)과 블록 상태의 수 — 실행하지 않는다."""
    rows = []
    for rel in _note_files(str(project.root)):
        try:
            res = project.note_check(rel)
            counts: dict[str, int] = {}
            for b in res.blocks:
                counts[b.status] = counts.get(b.status, 0) + 1
            rows.append({"path": rel, "blocks": len(res.blocks), "counts": counts})
        except Exception as exc:  # 읽지 못한 노트도 목록에는 — 까닭과 함께
            rows.append({"path": rel, "blocks": 0, "counts": {}, "error": str(exc)})
    return {"notes": rows}


def note_view(project: Any, path: str) -> dict:
    """노트 하나 — 글과 블록마다 상태(정상·낡음·실행 안 함·손으로 고침·허용 안 됨)와 명령·기록."""
    from equion.projects.notes import parse, read_text

    full = os.path.join(str(project.root), *path.split("/"))
    text = read_text(full)
    blocks = {b.n: b for b in parse(text)}
    res = project.note_check(path)
    out = []
    for st in res.blocks:
        b = blocks.get(st.n)
        out.append({**st.to_dict(), "commands": b.commands if b else [], "line": b.start if b else None})
    return {"path": path, "text": text, "blocks": out}


def note_run(project: Any, path: str, block: int | None = None, stale: bool = False, force: bool = False) -> dict:
    words = ["note", "run", path, *(["--block", str(block)] if block else []), *(["--stale"] if stale else []), *(["--force"] if force else [])]
    old = os.environ.get("EQUION_WHO")
    os.environ["EQUION_WHO"] = "desk"            # 블록의 명령이 남기는 기록의 '누가'도 Desk(명령줄을 같은 프로세스에서 부른다)
    try:
        res = project.note_run(path, block=block, stale=stale, force=force, who="desk", command=command(*words))
    finally:
        if old is None:
            os.environ.pop("EQUION_WHO", None)
        else:
            os.environ["EQUION_WHO"] = old
    return {**res.to_dict(), "command": command(*words), "records": [r for b in res.blocks for r in b.records]}


def note_add(project: Any, note: str, lines: list[str] | None = None, record: str | None = None, title: str | None = None) -> dict:
    if not str(note or "").replace("\\", "/").startswith("notes/"):
        raise ValueError(f"노트는 notes/ 안에 — {note!r}")
    words = ["note", "add", note, *[x for line in (lines or []) for x in ("--line", line)], *(["--record", record] if record else []),
             *(["--title", title] if title else [])]
    res = project.note_add(note, lines=lines, record=record, title=title, who="desk", command=command(*words))
    return {**res.to_dict(), "command": command(*words)}


# ---- 같은 분석의 두 기록 --------------------------------------------------------------------------------

def an_history(project: Any, record: str) -> dict:
    """그 기록과 같은 분석·같은 대상의 기록들(오래된 것부터) — '이전 기록과 비교'가 쓴다."""
    rec = project.work.get(record)
    m = rec.meta
    key = (m.get("analysis"), str(m.get("target")))
    rows = []
    for r in project.work.records("an"):
        mm = r.meta
        if (mm.get("analysis"), str(mm.get("target"))) == key:
            rows.append({"id": r.id, "created": mm.get("created"), "vintage": (mm.get("data") or {}).get("id"), "options": mm.get("options") or {},
                         "smpl": mm.get("smpl"), "lines": list(mm.get("lines") or []), "who": mm.get("who")})
    rows.sort(key=lambda x: str(x.get("created") or ""))
    ids = [x["id"] for x in rows]
    at = ids.index(record) if record in ids else -1
    return {"analysis": key[0], "label": m.get("label"), "target": key[1], "target_label": m.get("target_label"), "records": rows,
            "previous": ids[at - 1] if at > 0 else None, "next": ids[at + 1] if 0 <= at < len(ids) - 1 else None}


# ---- 이정표 · 묶어 보내기 (D61) --------------------------------------------------------------------------

def milestones(project: Any) -> dict:
    return {"milestones": project.milestones()}


def milestone_make(project: Any, name: str, note: str | None = None) -> dict:
    m = project.milestone_make(name, note=note, who="desk")
    return {**m.to_dict(), "files": len(m.files), "command": command("milestone", "make", name, *(["--note", note] if note else []))}


def milestone_diff(project: Any, name: str) -> dict:
    from equion.projects.milestones import load

    d = project.milestone_diff(name)
    m = load(project, name)
    return {**d.to_dict(), "milestone": {**m.to_dict(), "files": len(m.files)}}


def milestone_restore(project: Any, name: str, files: list | None = None) -> dict:
    words = ["milestone", "restore", name, *[x for f in (files or []) for x in ("--file", f)]]
    ch = project.milestone_restore(name, files=files or None, who="desk", command=command(*words))
    return {"change": ch.id if ch else None, "files": list(ch.files) if ch else [], "command": command(*words)}


def bundle(project: Any, raw: bool = False, records: str = "keep") -> dict:
    res = project.bundle(raw=bool(raw), records=records, who="desk")
    words = ["bundle", "make", *(["--raw"] if raw else []), *(["--records", records] if records != "keep" else [])]
    return {**res.to_dict(), "command": command(*words), "folder": str(project.root)}
