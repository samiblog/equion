#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""md 렌더러 (D33) — 작업 기록의 카드(`summary.md`)·노트·보고서가 같은 모양을 쓴다.

표는 파이프 표, 차트는 ```` ```vega-lite ```` 블록(자료는 같은 폴더의 CSV — Lectern이 그린다). 출력 객체의 `.md()`도 여기를 거친다.
"""

import json
import math
from typing import Iterable, List, Optional, Sequence, Tuple

import pandas as pd


def cell(v, digits: int = 4) -> str:
    """표 칸 하나 — 숫자는 자릿수를 맞추고, 글자의 `|`·줄바꿈은 표가 깨지지 않게."""
    if v is None:
        return ""
    if isinstance(v, bool):
        return "예" if v else "아니오"
    if isinstance(v, (int,)) and not isinstance(v, bool):
        return f"{v:,}"
    if isinstance(v, float):
        if math.isnan(v):
            return "NA"
        if v != 0 and (abs(v) >= 1e6 or abs(v) < 1e-3):
            return f"{v:.{digits}e}"
        return f"{v:,.{digits}f}"
    try:
        import numpy as np
        if isinstance(v, np.integer):
            return f"{int(v):,}"
        if isinstance(v, np.floating):
            return cell(float(v), digits)
    except ImportError:  # pragma: no cover
        pass
    return str(v).replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def table(df: pd.DataFrame, index: bool = True, digits: int = 4, index_label: str = None) -> str:
    """DataFrame → 파이프 표. 빈 표는 '(없음)'."""
    if df is None or len(df) == 0:
        return "(없음)"
    cols = [str(c) for c in df.columns]
    head = ([index_label or (df.index.name or "")] if index else []) + cols
    lines = ["| " + " | ".join(cell(h) for h in head) + " |",
             "|" + "|".join("---" for _ in head) + "|"]
    for key, *row in df.itertuples(index=True, name=None):      # 열마다 자료형 그대로(정수는 정수로)
        vals = ([cell(key)] if index else []) + [cell(v, digits) for v in row]
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def kv(rows: Iterable[Tuple[str, object]]) -> str:
    """두 칸 표(항목 · 값) — 기록의 머리 정보."""
    rows = [(k, v) for k, v in rows if v not in (None, "", [])]
    lines = ["| 항목 | 값 |", "|---|---|"]
    lines += [f"| {cell(k)} | {cell(v)} |" for k, v in rows]
    return "\n".join(lines)


def bullets(items: Sequence[str]) -> str:
    """글머리 목록(없으면 '없음')."""
    return "\n".join(f"- {cell(x)}" for x in items) if items else "없음"


def vega_line(csv: str, x: str, series: Sequence[str], title: str = "", height: int = 220) -> str:
    """선 차트 블록 — 같은 폴더의 CSV(넓은 표: x 열 + 시리즈 열)를 vega-lite로. Lectern·vega 렌더러가 그린다."""
    spec = {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": title, "height": height, "width": "container",
        "data": {"url": csv},
        "transform": [{"fold": list(series), "as": ["시리즈", "값"]}],
        "mark": {"type": "line"},
        "encoding": {"x": {"field": x, "type": "ordinal", "axis": {"labelOverlap": True}, "title": None},
                     "y": {"field": "값", "type": "quantitative", "scale": {"zero": False}, "title": None},
                     "color": {"field": "시리즈", "type": "nominal", "title": None}},
    }
    return "```vega-lite\n" + json.dumps(spec, ensure_ascii=False) + "\n```"


def card(title: str, head: Sequence[Tuple[str, object]] = (), sections: Sequence[Tuple[str, str]] = (),
         lead: Optional[str] = None) -> str:
    """기록 카드 하나 — `# 제목`, 머리 정보 표, 절(`## 제목` + 본문)."""
    out: List[str] = [f"# {title}", ""]
    if lead:
        out += [lead, ""]
    if head:
        out += [kv(head), ""]
    for h, body in sections:
        if body is None or body == "":
            continue
        out += [f"## {h}", "", body.rstrip(), ""]
    return "\n".join(out).rstrip() + "\n"


def output_md(out) -> str:
    """출력 객체(TableOutput·TextOutput) → md. 제목은 굵게, 머리·꼬리 줄은 문단."""
    lines: List[str] = []
    if getattr(out, "title", ""):
        lines += [f"**{out.title}**", ""]
    head = getattr(out, "head", None) or []
    lines += [h for h in head] + ([""] if head else [])
    if getattr(out, "kind", "") == "table":
        lines.append(table(out.df, index=out.index, digits=out.digits))
    else:
        lines += ["```text", str(getattr(out, "body", out.text())), "```"]
    foot = getattr(out, "foot", None) or []
    if foot:
        lines += [""] + [f for f in foot]
    return "\n".join(lines).rstrip() + "\n"
