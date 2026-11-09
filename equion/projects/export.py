#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""내보내기(`equion export … --xlsx`) — 기록의 값·값의 종류·출처를 엑셀 한 권으로 (K3).

기록마다 시트 몇 장: 추정(계수·적합) · HS(적합도·풀린 값·상태) · 전망(수준·값의 종류·연간·증가율·차이·보정항) · 자료 회차(값·값의 종류·
출처). 맨 앞 '출처' 시트에 기록마다 이름·만든 때·누가·명령·자료·equion 판을 적는다. 내보내기는 계산이 아니라 기록을 남기지 않는다.
"""

import os
from typing import List

import pandas as pd

from ..workfile.runtime import record_output
from .config import ProjectError
from .records import data_label, store_of

SHEETS = {"est": ("coefs.csv", "series.csv"), "hs": ("stats.csv", "solved.csv", "status.csv"),
          "sim": ("levels.csv", "flags.csv", "annual.csv", "growth.csv", "diff.csv", "addfactors.csv")}
SHEET_KO = {"coefs": "계수", "series": "적합", "stats": "적합도", "solved": "해", "status": "상태", "levels": "수준",
            "flags": "값의종류", "annual": "연간", "growth": "증가율", "diff": "차이", "addfactors": "보정항"}


def _sheet(name: str, used: set) -> str:
    bad = '[]:*?/\\'
    s = "".join("_" if ch in bad else ch for ch in name)[:31]
    base, k = s, 2
    while s in used:
        s = f"{base[:28]}_{k}"
        k += 1
    used.add(s)
    return s


def export_xlsx(p, ids: List[str], path: str) -> dict:
    """기록(est:· hs:· sim:· data:회차)을 엑셀 한 권으로. {path, sheets} — 기록은 남기지 않는다."""
    if not ids:
        raise ProjectError("내보낼 기록이 없습니다 — 기록 이름(est:… · hs:… · sim:… · data:회차)")
    if not path.lower().endswith(".xlsx"):
        raise ProjectError(f"--xlsx 파일 이름은 .xlsx로 끝나야 합니다: {path}")
    store = store_of(p)
    used, sheets, prov = set(), [], []
    frames = []
    for rid in ids:
        if rid.startswith("data:"):
            from .vintage import read_vintage, vintage_path
            vid = rid[5:]
            vp = vintage_path(p.root, vid)
            df, fl, meta = read_vintage(p.root, vid)
            src = pd.DataFrame({k: {"출처·식": v.get("from") or (f"= {v.get('expr')}" if v.get("expr") else ""),
                                    "단위": v.get("unit", ""), "설명": v.get("desc", "")}
                                for k, v in meta.get("series", {}).items()}).T
            src.index.name = "시리즈"
            frames += [(f"{vid}_값", df), (f"{vid}_값의종류", fl), (f"{vid}_출처", src)]
            import json
            with open(os.path.join(vp, "build.json"), encoding="utf-8") as f:
                b = json.load(f)
            prov.append({"기록": rid, "만든 때": b.get("created"), "누가": "", "명령": "data build",
                         "자료": rid, "equion": b.get("equion"), "경로": os.path.relpath(vp, p.root).replace(os.sep, "/")})
            continue
        rec = store.get(rid)
        m = rec.meta
        prov.append({"기록": rec.id, "만든 때": m.get("created"), "누가": m.get("who"), "명령": m.get("command"),
                     "자료": data_label(m.get("data") or {}), "equion": m.get("equion"), "경로": m.get("path")})
        for fn in SHEETS.get(rec.kind, ()):
            if os.path.isfile(rec.file(fn)):
                stem = fn[:-4]
                frames.append((f"{rec.name}_{SHEET_KO.get(stem, stem)}", rec.read_csv(fn)))
    full = os.path.abspath(os.path.join(p.root, path) if not os.path.isabs(path) else path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with pd.ExcelWriter(full, engine="openpyxl") as xw:
        pv = pd.DataFrame(prov).set_index("기록")
        nm = _sheet("출처", used)
        pv.to_excel(xw, sheet_name=nm)
        sheets.append(nm)
        for title, df in frames:
            nm = _sheet(title, used)
            df.to_excel(xw, sheet_name=nm)
            sheets.append(nm)
    record_output(full, "export")
    return {"path": full, "sheets": sheets, "records": list(ids)}
