"""작업 기록 읽기 — `work/` 의 파일을 읽기만 한다(equion 을 불러오지 않는다. 앱 프로세스와 작업 프로세스가 함께 쓴다).

기록은 고치지 않는 파일이다(D33): `work/log.jsonl`(한 줄에 기록 하나) · `work/<종류>/<이름>/`(`record.json`·결과 CSV·카드 `summary.md`).
이름은 `est:cn_0003` 처럼 `<종류>:<이름>`. 화면이 준 이름은 모양을 확인한 뒤에만 경로로 바꾼다.
"""
from __future__ import annotations

import csv
import json
import os
import re
import tomllib
from typing import Any

RECORD_ID = re.compile(r"^([a-z]{2,8}):([A-Za-z0-9][A-Za-z0-9_\-]{0,120})$")
CHANGE_ID = re.compile(r"^h\d{1,9}$")
LOG_TAIL = 1024 * 1024        # 기록 띠·목록은 로그의 끝부분만 읽는다
CARD_LIMIT = 2 * 1024 * 1024
SERIES_LIMIT = 8 * 1024 * 1024


def split_id(rid: Any) -> tuple[str, str] | None:
    m = RECORD_ID.match(rid) if isinstance(rid, str) else None
    return (m.group(1), m.group(2)) if m else None


def record_dir(root: str, rid: Any) -> str | None:
    """기록 폴더(있을 때만). 이름의 모양이 틀리면 None."""
    parts = split_id(rid)
    if not parts:
        return None
    path = os.path.join(root, "work", parts[0], parts[1])
    return path if os.path.isdir(path) else None


def read_series(path: str) -> dict[str, list]:
    """기록 폴더의 `series.csv`(기간 + 숫자 열들) → 열마다 목록. 화면의 차트가 쓴다. 숫자가 아닌 칸은 None."""
    out: dict[str, list] = {}
    file = os.path.join(path, "series.csv")
    try:
        if os.path.getsize(file) > SERIES_LIMIT:
            return out
        with open(file, encoding="utf-8", newline="") as f:
            rows = list(csv.reader(f))
    except OSError:
        return out
    if not rows:
        return out
    for i, name in enumerate(rows[0]):
        col: list = []
        for row in rows[1:]:
            cell = row[i] if i < len(row) else ""
            if i == 0:
                col.append(cell)
            else:
                try:
                    value = float(cell)
                    col.append(value if value == value and abs(value) != float("inf") else None)
                except ValueError:
                    col.append(None)
        out[name] = col
    return out


def read_log(root: str, limit: int = 300) -> list[dict[str, Any]]:
    """`work/log.jsonl` 의 최근 줄(만든 순). 지운 기록(폴더가 없다)은 뺀다."""
    path = os.path.join(root, "work", "log.jsonl")
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as f:
            if size > LOG_TAIL:
                f.seek(size - LOG_TAIL)
                f.readline()              # 잘린 첫 줄은 버린다
            data = f.read()
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for raw in data.split(b"\n"):
        raw = raw.strip()
        if not raw:
            continue
        try:
            line = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            continue
        if isinstance(line, dict) and record_dir(root, line.get("id")):
            out.append(line)
    return out[-limit:]


def _json(path: str) -> dict[str, Any]:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def read_adopted(root: str) -> dict[str, str]:
    """채택표(`EQUATIONS/adopted.toml`) — {부품: 추정 기록}. 없거나 읽지 못하면 빈 사전."""
    try:
        with open(os.path.join(root, "EQUATIONS", "adopted.toml"), "rb") as f:
            data = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError):
        return {}
    return {str(k): str(v) for k, v in data.items() if isinstance(v, str)}


_CANDIDATES: dict[tuple[str, str], dict[str, Any]] = {}     # 기록은 고치지 않는 파일이라 한 번 읽은 요약을 들고 있는다


def _candidate(root: str, rid: str) -> dict[str, Any] | None:
    """추정 기록 하나의 요약 — 후보 목록의 한 줄."""
    key = (root, rid)
    if key in _CANDIDATES:
        return _CANDIDATES[key]
    base = record_dir(root, rid)
    m = _json(os.path.join(base, "record.json")) if base else {}
    if not m:
        return None
    stats = m.get("stats") if isinstance(m.get("stats"), dict) else {}
    crit = m.get("criteria") if isinstance(m.get("criteria"), dict) else None
    diag = m.get("diagnostics") if isinstance(m.get("diagnostics"), dict) else {}
    cov = m.get("cov") if isinstance(m.get("cov"), dict) else None
    row = {
        "id": rid, "name": rid.split(":", 1)[1], "who": m.get("who"), "created": m.get("created"), "command": m.get("command"),
        "text": m.get("text"), "method": m.get("method"), "dependent": m.get("dependent"), "sample": m.get("sample"), "n": m.get("n"),
        "stats": {k: stats.get(k) for k in ("adj_r_squared", "r_squared", "se_regression", "durbin_watson", "aic", "bic")},
        "diag": {k: (v or {}).get("p") for k, v in diag.items() if isinstance(v, dict)},
        "pass": crit.get("pass") if crit else None, "reasons": (crit or {}).get("reasons") or [], "signs": (crit or {}).get("signs") or [],
        "alpha": (crit or {}).get("alpha"), "sim": (m.get("sim") or {}).get("rmspe") if isinstance(m.get("sim"), dict) else None,
        "cov": cov.get("type") if cov else None, "cov_label": cov.get("label") if cov else None,
        "data": (m.get("data") or {}).get("id") if isinstance(m.get("data"), dict) else None,
        "coefs": [{k: c.get(k) for k in ("name", "coef", "t", "p")} for c in m.get("coefs") or [] if isinstance(c, dict)],
    }
    if len(_CANDIDATES) > 4000:
        _CANDIDATES.clear()
    _CANDIDATES[key] = row
    return row


def read_candidates(root: str, part: Any, limit: int = 500) -> dict[str, Any]:
    """부품의 후보 — 그 부품에 묶인 추정 기록들(만든 순)과 채택한 기록. 사람이 했든 Claude 가 했든 같은 목록이다."""
    rows: list[dict[str, Any]] = []
    if isinstance(part, str) and part:
        for line in read_log(root, limit=20000):
            if line.get("kind") == "est" and line.get("part") == part:
                row = _candidate(root, line["id"])
                if row:
                    rows.append(row)
    return {"part": part, "adopted": read_adopted(root).get(part) if isinstance(part, str) else None, "rows": rows[-limit:]}


def read_record(root: str, rid: Any) -> dict[str, Any] | None:
    """기록 하나 — `{id, kind, name, path, meta, summary, files, series}`. 없으면 None.

    `meta` 는 `record.json`(자료 회차는 `build.json`), `summary` 는 카드 `summary.md` 의 글, `series` 는 `series.csv`(추정·분석의 차트).
    """
    base = record_dir(root, rid)
    if base is None:
        return None
    kind, name = split_id(rid)  # type: ignore[misc]
    meta = _json(os.path.join(base, "record.json")) or _json(os.path.join(base, "build.json"))
    summary = ""
    try:
        with open(os.path.join(base, "summary.md"), encoding="utf-8", errors="replace") as f:
            summary = f.read(CARD_LIMIT)
    except OSError:
        pass
    files = []
    for entry in sorted(os.scandir(base), key=lambda e: e.name):
        if entry.is_file():
            files.append({"name": entry.name, "size": entry.stat().st_size})
    return {"id": rid, "kind": kind, "name": name, "path": f"work/{kind}/{name}", "meta": meta, "summary": summary, "files": files,
            "series": read_series(base) if kind == "est" else {}}
