"""Equion Desk(데스크톱 앱)에 알리기 — `work/desk/requests.jsonl`에 한 줄을 덧붙인다(D47).

패키지는 앱을 불러오지 않는다(의존은 `equion-desk → equion` 한쪽 — D28). 앱이 이 파일을 지켜보다가 새 줄이 오면 그 화면을 연다.
앱이 떠 있지 않거나 이 프로젝트를 열어 두지 않았으면 아무 일도 일어나지 않는다(지난 줄은 앱이 다시 읽지 않는다).

    {"at": "2026-11-12T10:12:03", "who": "claude", "show": "est:cn_0003", "kind": "record"}
"""
from __future__ import annotations

import json
import os

from ..work.store import RecordError, detect_who, now_iso
from .config import ProjectError

FILE = "work/desk/requests.jsonl"
PLACES = ("home", "data", "analysis", "forecast", "reports", "records", "changes", "proposals")     # 이름만으로 여는 화면
RECORDS = ("est", "hs", "sim", "an", "run")
LIMIT = 64 * 1024            # 이보다 커지면 지난 줄을 버린다(앱은 새 줄만 읽는다)


def resolve(p, name: str) -> str:
    """이름이 무엇을 가리키는지 — record · proposal · data(자료 회차) · part · model · place · file. 없는 것이면 ProjectError."""
    name = str(name or "").strip()
    if not name or len(name) > 300 or "\n" in name:
        raise ProjectError("열 화면의 이름이 비었습니다 — 기록(est:… · hs:… · sim:… · an:… · run:…) · 제안(prop:…) · 부품(블록:목표) · 모형(model:이름) · 파일 경로 · "
                           + " · ".join(PLACES))
    if name in PLACES:
        return "place"
    head, _, rest = name.partition(":")
    if head in RECORDS and rest:
        from .records import store_of
        try:
            store_of(p).get(name)
        except RecordError as e:
            raise ProjectError(str(e)) from None
        return "record"
    if head == "prop" and rest:
        from . import proposals
        proposals.get(p, rest)
        return "proposal"
    if head == "data" and rest:
        if not any(v["id"] == rest for v in p.data_list()):
            raise ProjectError(f"없는 자료 회차 {rest}")
        return "data"
    if head == "model" and rest:
        if rest not in p.config.models:
            raise ProjectError(f"없는 모형 {rest!r} (있는 것: {', '.join(p.config.models) or '없음'})")
        return "model"
    if ":" in name and "/" not in name and "\\" not in name:
        try:
            p.part(name)
        except KeyError as e:
            raise ProjectError(str(e.args[0]) if e.args else f"없는 부품 {name}") from None
        return "part"
    from .config import project_path
    path = project_path(p.root, name, "경로")
    if not os.path.isfile(path):
        raise ProjectError(f"무엇을 가리키는지 알 수 없습니다: {name!r} — 기록 · 제안(prop:…) · 부품(블록:목표) · 모형(model:이름) · 프로젝트 안의 파일 · "
                           + " · ".join(PLACES))
    return "file"


def request_show(p, name: str, who: str = None) -> dict:
    """Desk에 "이 화면을 열어 달라"고 알린다 — 이름을 확인한 뒤 요청 파일에 한 줄. 돌려주는 것: {show, kind, file}."""
    kind = resolve(p, name)
    name = str(name).strip()
    if kind == "file":
        from .config import project_path
        name = os.path.relpath(project_path(p.root, name, "경로"), p.root).replace(os.sep, "/")
    path = os.path.join(p.root, *FILE.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    line = json.dumps({"at": now_iso(), "who": who or detect_who("python"), "show": name, "kind": kind}, ensure_ascii=False) + "\n"
    mode = "a"
    try:
        if os.path.getsize(path) > LIMIT:
            mode = "w"
    except OSError:
        pass
    with open(path, mode, encoding="utf-8", newline="\n") as f:
        f.write(line)
    return {"show": name, "kind": kind, "file": FILE}
