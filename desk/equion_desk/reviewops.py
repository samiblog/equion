"""제안·되돌리기·기록 표시의 일(작업 프로세스 안에서 돈다) — 사람과 Claude가 서로의 일을 받아들이고 물리는 곳(D5).

하는 일은 패키지의 함수다: 제안은 `Project.proposals·apply_proposal·drop_proposal`, 되돌리기는 `History.revert`, 고정·메모는 `WorkStore.mark`.
여기서는 화면이 쓰기 좋은 모양으로 묶는다. 제안을 '만드는' 것은 화면이 하지 않는다 — Claude(또는 사람)가 `equion propose new`로 만든다.
"""
from __future__ import annotations

from typing import Any

from .dataops import command

KEEP = ("id", "title", "why", "who", "created", "status", "parts", "previews", "stale", "decided", "command")


def _slim(prop: Any) -> dict:
    d = prop.to_dict()
    out = {k: d.get(k) for k in KEEP}
    out["name"] = prop.name
    out["files"] = [{"path": rel, "delete": bool((v or {}).get("delete")), "stale": rel in (d.get("stale") or [])} for rel, v in (d.get("files") or {}).items()]
    return out


def proposals(project: Any) -> dict:
    """제안 목록(만든 순) — 열림·적용·버림 모두. 열린 제안은 만든 뒤 바뀐 파일(낡음)과 함께."""
    return {"proposals": [_slim(p) for p in project.proposals()]}


def proposal(project: Any, name: str) -> dict:
    """제안 하나 — 지금 파일 대비 바뀔 내용의 차이, 까닭, 미리 계산한 기록(과거 재현이면 전후 RMSPE와 함께). 아무것도 바꾸지 않는다."""
    from equion.projects import proposals as P

    prop = P.get(project, name)
    out = _slim(prop)
    out["diff"] = prop.diff()
    previews = []
    for rid in out.get("previews") or []:
        try:
            rec = project.work.get(rid)
        except Exception:
            previews.append({"id": rid, "missing": True})
            continue
        m = rec.meta
        vs = m.get("vs") if isinstance(m.get("vs"), dict) else None
        previews.append({"id": rid, "kind": rec.kind, "model": m.get("model"), "swaps": m.get("swaps") or None,
                         "rmspe": m.get("rmspe") if isinstance(m.get("rmspe"), dict) else None,
                         "vs": {"id": vs.get("id"), "rmspe": vs.get("rmspe")} if vs and vs.get("rmspe") else None})
    out["previews"] = previews
    out["commands"] = {"apply": command("propose", "apply", name), "drop": command("propose", "drop", name)}
    return out


def proposal_apply(project: Any, name: str, force: bool = False) -> dict:
    """제안을 적용한다(`equion propose apply`) — 바꿀 파일을 새 내용으로 쓰고 바뀜 기록에 "제안 … 적용". 낡았으면 force일 때만."""
    prop = project.apply_proposal(name, force=bool(force), who="desk", command=command("propose", "apply", name, *(["--force"] if force else [])))
    return _slim(prop)


def proposal_drop(project: Any, name: str, why: str | None = None) -> dict:
    """제안을 버린다(`equion propose drop`) — 파일은 그대로, 제안 기록은 남는다."""
    return _slim(project.drop_proposal(name, why=why or "", who="desk"))


class RevertBlocked(ValueError):
    """되돌리기가 뒤의 바뀜과 겹침 — 작업 프로세스가 kind 'conflict'(409)로 알린다(ValueError라 그 경로로 잡힌다)."""

    kind = "conflict"


def revert(project: Any, change: str, files: list[str] | None = None, force: bool = False) -> dict:
    """되돌리기(`equion history revert`) — 그 바뀜 하나만 물린다(뒤의 바뀜은 그대로, 이것도 바뀜 기록에 남는다). files를 주면 그 파일만.

    뒤의 바뀜이 같은 줄을 고쳤으면 패키지가 겹침(RevertConflict)으로 멈춘다 — 화면이 알아보게 kind 'conflict'로 알리고,
    사람이 고르면 force로 그 파일을 그 바뀜 앞 내용으로 통째로 쓴다(`--force`)."""
    from equion.work.history import RevertConflict

    words = ["history", "revert", change, *[x for f in (files or []) for x in ("--file", f)], *(["--force"] if force else [])]
    try:
        done = project.history.revert(change, "desk", command(*words), files=files or None, force=force)
    except RevertConflict as exc:
        raise RevertBlocked(str(exc)) from None
    return {"change": done.id if done is not None else None, "reverts": change, "files": list(done.files) if done is not None else [], "command": command(*words)}


def mark(project: Any, record: str, pinned: bool | None = None, memo: str | None = None) -> dict:
    """기록에 고정·메모(`equion work pin·memo`) — 기록 자체는 그대로, marks.json에만."""
    return {"record": record, **project.work.mark(record, pinned=pinned, memo=memo)}
