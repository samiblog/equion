#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""보고서 (D37) — `reports/*.md`. 명령 블록 없이 **결과만** 보낸다. 구역마다 보이지 않는 표시에 기록 이름·보낸 날·자료 회차·보낸 모양.

    <!-- equion:report sim:2026-11_base #1 · 2026-11-09 · d2026-11a {"record": …, "rows": […], "show": "yoy", "annual": true, …} -->
    **표 1. 주요 지표 전망** (전년동기비, %)

    | 시리즈 | 2020 | 2021 |
    |---|---|---|
    | Y | 0.9 | 1.7 |

    자료: Equion sim:2026-11_base(자료 회차 d2026-11a)
    <!-- /equion:report -->

보고서는 혼자 선다 — 차트 자료는 `reports/<보고서>_data/`로 복사한다. 사람의 글이라 손으로 고쳐도 된다. 새 기록으로 바꾸기는 사람이 시킬 때만
(`report update`)이고, 바꾸기 전에 숫자의 차이를 보이며 손으로 고친 구역은 그 고친 곳을 차이로 알리고 `--force` 없이는 덮지 않는다.
"""

import json
import os
import re
from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd

from ..reporting import markdown as md
from ..workfile.runtime import record_output
from ..work.store import RecordError
from .config import ProjectError
from .notes import _h, read_text, region_diff, stale_reasons
from .records import _who, data_label, history_of, store_of

REP_DIR = "reports"
OPEN = re.compile(r"^<!-- equion:report (\S+) (.*?)(\{.*\}) -->\s*$")
CLOSE = "<!-- /equion:report -->"
SHOW_KO = {"level": "수준", "qoq": "전기비, %", "yoy": "전년동기비, %", "diff": "기준선 대비, %"}


@dataclass
class Region:
    """보고서 구역 하나 — 줄 위치·기록·보낸 모양·본문."""

    n: int
    start: int
    end: int
    record: str
    shape: dict
    body: str

    @property
    def edited(self) -> bool:
        """보낸 뒤 손으로 고쳤으면 참."""
        return bool(self.shape.get("h")) and _h(self.body) != self.shape["h"]


def regions(text: str) -> List[Region]:
    """보고서 글 → 구역 목록(위에서부터 1, 2, …)."""
    lines = text.split("\n")
    out, i = [], 0
    while i < len(lines):
        m = OPEN.match(lines[i])
        if m:
            j = i + 1
            while j < len(lines) and lines[j].strip() != CLOSE:
                j += 1
            try:
                shape = json.loads(m[3])
            except json.JSONDecodeError:
                shape = {}
            out.append(Region(len(out) + 1, i, j, m[1], shape, "\n".join(lines[i + 1:j])))
            i = j
        i += 1
    return out


def _path(p, report: str) -> str:
    name = report if report.endswith(".md") else f"{report}.md"
    if not os.path.isabs(name) and "/" not in name.replace(os.sep, "/"):
        name = os.path.join(REP_DIR, name)
    return name if os.path.isabs(name) else os.path.join(p.root, name)


def _rel(p, path):
    return os.path.relpath(path, p.root).replace(os.sep, "/")


def _fmt(v, digits):
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return ""
    if isinstance(v, (int, float, np.floating, np.integer)):
        return f"{float(v):,.{digits}f}"
    return str(v)


def _table_md(df: pd.DataFrame, digits: int) -> str:
    t = df.copy()
    for c in t.columns:
        t[c] = [_fmt(v, digits) for v in t[c]]
    return md.table(t)


# ---------------------------------------------------------------------------
# 모양대로 다시 만들기 — 기록 + 보낸 모양 → 구역 본문
# ---------------------------------------------------------------------------
def _sim_table(rec, shape):
    m = rec.meta
    rows = shape.get("rows") or m["endogenous"][:4]
    show = shape.get("show", "level")
    miss = [v for v in rows if v not in m["endogenous"] + m.get("exogenous", [])]
    if miss:
        raise ProjectError(f"{rec.id}에 없는 시리즈: {', '.join(miss)}")
    if show == "diff":
        d = rec.read_csv("diff.csv") if os.path.isfile(rec.file("diff.csv")) else None
        if d is None:
            raise ProjectError(f"{rec.id}는 기준선 기록이라 차이(diff)가 없습니다 — 시나리오 기록에서")
        t = pd.DataFrame({v: d[f"{v}_%"] for v in rows}).T
    elif shape.get("annual"):
        a = rec.read_csv("annual.csv")
        t = pd.DataFrame({v: a[f"{v}_증가율" if show in ("yoy", "qoq") else v] for v in rows}).T
    else:
        fl = rec.read_csv("flags.csv")
        fc = [lab for lab in fl.index if (fl.loc[lab] == "해").any()]
        src = rec.read_csv("levels.csv") if show == "level" else rec.read_csv("growth.csv")
        col = (lambda v: v) if show == "level" else (lambda v: f"{v}_{'전기비' if show == 'qoq' else '전년동기비'}")
        t = pd.DataFrame({v: src.loc[fc, col(v)] for v in rows}).T
    t.index.name = "시리즈"
    unit = SHOW_KO["yoy" if (shape.get("annual") and show == "qoq") else show]
    if shape.get("annual") and show == "level":
        unit = "연평균 수준"
    title = shape.get("title") or f"전망 — {m['scenario']} ({m['model']})"
    return t, title, unit


def _record_table(rec, shape) -> Tuple[pd.DataFrame, str, str]:
    m = rec.meta
    rows = shape.get("rows")
    if rec.kind == "sim":
        return _sim_table(rec, shape)
    if rec.kind == "hs":
        t = rec.read_csv("stats.csv")
        cols = [c for c in ("RMSPE", "MAE_pct", "MAE", "mean_error") if c in t.columns]
        t = t[cols]
        t.index.name = "변수"
        title, unit = shape.get("title") or f"과거 재현 적합도 — {m['model']} {m['range'][0]}~{m['range'][1]}", "RMSPE·MAE_pct는 %"
    elif rec.kind == "est":
        t = rec.read_csv("coefs.csv").rename(columns={"coef": "계수", "se": "표준오차", "t": "t값", "p": "p값"})
        title, unit = shape.get("title") or f"추정 — {m['text']}", f"{m['sample'][0]}~{m['sample'][1]} · n={m['n']}"
    elif rec.kind == "an":
        k = int(shape.get("table") or 1)
        names = m.get("tables") or []
        if not 1 <= k <= len(names):
            raise ProjectError(f"{rec.id}의 표는 {len(names)}개입니다(#1~#{len(names)})")
        t = rec.read_csv(f"table_{k}.csv")
        title, unit = shape.get("title") or f"{m['label']} — {m['target_label']}: {names[k - 1]}", ""
    else:
        raise ProjectError(f"{rec.id}: 보고서로 보낼 수 없는 기록")
    if rows:
        miss = [r for r in rows if r not in t.index]
        if miss:
            raise ProjectError(f"{rec.id}의 표에 없는 행: {', '.join(miss)} (있는 행: {', '.join(map(str, t.index[:12]))})")
        t = t.loc[rows]
    return t, title, unit


def _chart(rec, shape, data_rel: str, n: int):
    """차트 — 기록의 CSV에서 고른 시리즈만 보고서 옆 폴더로 복사할 자료와 vega-lite 블록."""
    if rec.kind == "sim":
        src = rec.read_csv("levels.csv")
        cols = shape.get("rows") or rec.meta["endogenous"][:4]
    elif rec.kind == "hs":
        src = rec.read_csv("series.csv")
        base = shape.get("rows") or list((rec.meta.get("rmspe") or {}).keys())[:2]
        cols = [c for v in base for c in (v, f"{v}_실측")]
    elif rec.kind == "an" and os.path.isfile(rec.file("chart_1.csv")):
        src = rec.read_csv("chart_1.csv")
        cols = shape.get("rows") or list(src.columns)[:4]
    else:
        return None, None
    cols = [c for c in cols if c in src.columns]
    df = src[cols]
    df.index.name = src.index.name or "period"
    fname = f"{rec.kind}_{rec.name}_{n}.csv"
    block = md.vega_line(f"{data_rel}/{fname}", df.index.name, cols, shape.get("title") or rec.id)
    return (fname, df), block


def render(p, report_path: str, rid: str, shape: dict) -> Tuple[str, Optional[tuple]]:
    """구역 본문과 (복사할 차트 자료 파일 이름, DataFrame)."""
    store = store_of(p)
    rec = store.get(rid)
    t, title, unit = _record_table(rec, shape)
    digits = int(shape.get("digits") if shape.get("digits") is not None else (1 if rec.kind == "sim" else 3))
    n = int(shape.get("n", 1))
    data_rel = os.path.splitext(os.path.basename(report_path))[0] + "_data"
    vint = data_label(rec.meta.get("data") or {})
    parts = [f"**표 {n}. {title}**" + (f" ({unit})" if unit else ""), "", _table_md(t, digits)]
    data = None
    if shape.get("chart"):
        data, block = _chart(rec, shape, data_rel, n)
        if block:
            parts += ["", block]
    parts += ["", f"자료: Equion {rec.id}({vint.replace('data:', '자료 회차 ')})"]
    return "\n".join(parts), data


def _open_line(rid, shape, vint) -> str:
    sh = {k: v for k, v in shape.items() if v not in (None, False, [], "")}
    return f"<!-- equion:report {rid} #{shape.get('n', 1)} · {date.today().isoformat()} · {vint} {json.dumps(sh, ensure_ascii=False)} -->"


def _write_data(p, report_path, data):
    if not data:
        return None
    fname, df = data
    d = os.path.join(os.path.dirname(report_path), os.path.splitext(os.path.basename(report_path))[0] + "_data")
    os.makedirs(d, exist_ok=True)
    out = os.path.join(d, fname)
    df.to_csv(out, lineterminator="\n")
    record_output(out, "report")
    return out


# ---------------------------------------------------------------------------
# 명령
# ---------------------------------------------------------------------------
@dataclass
class ReportResult:
    """보고서 명령의 결과 — 보고서·구역마다 상태·차이·바뀜 기록."""

    report: str
    action: str
    items: List[dict] = field(default_factory=list)
    change: Optional[str] = None
    exists: bool = False                   # report new --exist-ok: 이미 있어 그대로 둠

    def text(self) -> str:
        """명령줄에 보이는 짧은 글."""
        L = [f"[report {self.action}] {self.report}" + (f" — 구역 {len(self.items)}" if self.items and self.action != "add" else "")
             + (" — 이미 있어 그대로 둠" if self.exists else "")]
        for it in self.items:
            L.append(f"  #{it['n']} {it['record']}" + (f" → {it['to']}" if it.get("to") and it["to"] != it["record"] else "")
                     + f"  {it['status']}" + (f" — {it['detail']}" if it.get("detail") else ""))
            if it.get("diff"):
                L += ["    " + x for x in it["diff"].rstrip().splitlines()[:40]]
        if self.change:
            L.append(f"  바뀜 기록  {self.change}")
        return "\n".join(L)

    def to_dict(self) -> dict:
        """명령줄 --json과 같은 사전."""
        return {"report": self.report, "action": self.action, "items": self.items, "change": self.change,
                "exists": self.exists}


def new_report(p, name: str, title: str = None, from_report: str = None, exist_ok: bool = False, who: str = None,
               command: str = None) -> ReportResult:
    """새 보고서 — 틀(제목·날짜·자료 회차·모형) 또는 지난 보고서를 복사하고(from) 구역마다 바꿔 낄 기록을 제안한다.
    exist_ok면 이미 있는 보고서는 그대로 둔다(스크립트를 같은 회차로 다시 돌릴 때 — 글이 지워지지 않게)."""
    path = _path(p, name)
    rel = _rel(p, path)
    if os.path.exists(path):
        if exist_ok:
            return ReportResult(rel, "new", [], None, exists=True)
        raise ProjectError(f"이미 있는 보고서 {rel} — 그대로 두려면 --exist-ok")
    items = []
    if from_report:
        src = _path(p, from_report)
        if not os.path.isfile(src):
            raise ProjectError(f"없는 보고서: {_rel(p, src)}")
        text = read_text(src)
        for r in regions(text):
            newer = newest_like(p, r.record)
            items.append({"n": r.n, "record": r.record, "to": newer, "status": "바꿔 낄 기록 있음" if newer and newer != r.record else "그대로",
                          "detail": f"equion report update {rel} --region {r.n} --to {newer}" if newer and newer != r.record else ""})
        old_data = os.path.join(os.path.dirname(src), os.path.splitext(os.path.basename(src))[0] + "_data")
        new_data = os.path.join(os.path.dirname(path), os.path.splitext(os.path.basename(path))[0] + "_data")
        text = text.replace(os.path.basename(old_data) + "/", os.path.basename(new_data) + "/")
        if os.path.isdir(old_data):
            import shutil
            shutil.copytree(old_data, new_data, dirs_exist_ok=True)
    else:
        t = title or os.path.splitext(os.path.basename(path))[0]
        m = p.config.forecast.get("model") or p.config.hs.get("model") or ""
        text = (f"# {t}\n\n{date.today().isoformat()} · 자료 회차 {p.vintage or '-'}" + (f" · 모형 {m}" if m else "")
                + "\n\n## 요약\n\n(글)\n\n## 본문\n")
    ch = history_of(p).write_files({rel: text}, _who(who), command or f"report new {rel}",
                                   note=f"보고서 {rel}" + (f" ← {_rel(p, _path(p, from_report))}" if from_report else ""))
    return ReportResult(rel, "new", items, ch.id if ch else None)


def add(p, report: str, rid: str, rows: List[str] = None, show: str = "level", annual: bool = False, digits: int = None,
        title: str = None, chart: bool = False, under: str = None, table: int = None, key: str = None, force: bool = False,
        who: str = None, command: str = None) -> ReportResult:
    """보고서로 보내기 — 기록의 표(와 차트)를 고른 모양으로 보고서에 넣는다(under 제목 아래 끝, 없으면 맨 끝).

    key(구역 이름)를 주면 같은 이름의 구역이 있을 때 그 자리에서 이 기록으로 바꾼다 — 스크립트가 달마다 같은 구역을 새 기록으로
    채울 때. 그 구역을 손으로 고쳤으면 force일 때만 덮는다(아니면 ProjectError — 고친 곳과 함께).
    """
    path = _path(p, report)
    rel = _rel(p, path)
    if not os.path.isfile(path):
        raise ProjectError(f"없는 보고서 {rel} — equion report new {os.path.splitext(os.path.basename(path))[0]}")
    if "#" in rid:
        rid, _, k = rid.partition("#")
        table = int(re.sub(r"\D", "", k) or 1)
    if show not in SHOW_KO:
        raise ProjectError(f"--show {show!r} — {' · '.join(SHOW_KO)}")
    text = read_text(path)
    regs = regions(text)
    same = [r for r in regs if key and r.shape.get("key") == key]
    n = same[0].n if same else len(regs) + 1
    shape = {"rows": list(rows or []), "show": show, "annual": bool(annual), "digits": digits, "title": title,
             "chart": bool(chart), "table": table, "n": n, "key": key}
    body, data = render(p, path, rid, shape)
    shape["h"] = _h(body)
    rec = store_of(p).get(rid)
    block = "\n".join([_open_line(rid, shape, data_label(rec.meta.get("data") or {})), body, CLOSE])
    lines = text.split("\n")
    if same:
        r = same[0]
        if r.edited and not force:
            try:
                orig, _ = render(p, path, r.record, dict(r.shape))
                hand = region_diff(orig, r.body, "보낸 것 → 지금")
            except (RecordError, ProjectError):
                hand = ""
            raise ProjectError(f"{rel}의 구역 #{r.n}({key})을 손으로 고쳤습니다 — 덮으려면 --force" + (f"\n{hand}" if hand else ""))
        diff = region_diff(r.body, body, f"#{r.n}")
        lines[r.start:r.end + 1] = block.split("\n")
        new = "\n".join(lines)
        _write_data(p, path, data)
        ch = history_of(p).write_files({rel: new}, _who(who), command or f"report add {rel} {rid} --key {key}",
                                       note=f"구역 #{n}({key}) {r.record} → {rid}")
        return ReportResult(rel, "add", [{"n": n, "record": r.record, "to": rid,
                                          "status": "바꿈" if diff else "그대로", "detail": f"구역 {key}", "diff": diff}],
                            ch.id if ch else None)
    pos = len(lines)
    if under:
        hdr = [i for i, x in enumerate(lines) if x.strip() == under.strip()]
        if not hdr:
            raise ProjectError(f"{rel}에 제목 {under!r}이 없습니다")
        level = len(under.strip()) - len(under.strip().lstrip("#"))
        pos = len(lines)
        for j in range(hdr[0] + 1, len(lines)):
            s = lines[j].lstrip()
            if s.startswith("#") and len(s) - len(s.lstrip("#")) <= level:
                pos = j
                break
    while pos > 0 and not lines[pos - 1].strip():
        pos -= 1
    lines[pos:pos] = ["", block, ""]
    new = "\n".join(lines).rstrip("\n") + "\n"
    _write_data(p, path, data)
    ch = history_of(p).write_files({rel: new}, _who(who), command or f"report add {rel} {rid}", note=f"구역 #{n} ← {rid}")
    return ReportResult(rel, "add", [{"n": n, "record": rid, "status": "넣음", "detail": body.splitlines()[0]}],
                        ch.id if ch else None)


def _family(rec) -> tuple:
    m = rec.meta
    if rec.kind == "sim":
        return ("sim", m.get("model"), m.get("scenario"))
    if rec.kind == "hs":
        return ("hs", m.get("model"), m.get("mode"))
    if rec.kind == "est":
        return ("est", m.get("part") or m.get("target"))
    return ("an", m.get("analysis"), m.get("target"))


def newest_like(p, rid: str) -> Optional[str]:
    """같은 갈래(전망: 모형·시나리오 · HS: 모형 · 추정: 부품 · 분석: 분석·대상)의 가장 새 기록."""
    store = store_of(p)
    try:
        rec = store.get(rid)
    except RecordError:
        return None
    fam = _family(rec)
    same = [r for r in store.records(rec.kind) if _family(r) == fam]
    return same[-1].id if same else rid


def check(p, report: str) -> ReportResult:
    """보고서 검사 — 구역마다 없는 기록 · 더 새 기록 · 낡음(자료·정의가 바뀜) · 손으로 고침."""
    path = _path(p, report)
    rel = _rel(p, path)
    if not os.path.isfile(path):
        raise ProjectError(f"없는 보고서 {rel}")
    store = store_of(p)
    items = []
    for r in regions(read_text(path)):
        st, detail, to = [], [], None
        try:
            rec = store.get(r.record)
        except RecordError:
            items.append({"n": r.n, "record": r.record, "status": "없는 기록", "detail": "기록이 지워졌습니다"})
            continue
        newer = newest_like(p, r.record)
        if newer and newer != r.record:
            st.append("더 새 기록")
            detail.append(newer)
            to = newer
        sr = stale_reasons(p, rec)
        if sr:
            st.append("낡음")
            detail += sr
        if r.edited:
            st.append("손으로 고침")
        items.append({"n": r.n, "record": r.record, "to": to, "status": " · ".join(st) or "정상", "detail": "; ".join(detail)})
    return ReportResult(rel, "check", items)


def update(p, report: str, region: int = None, to: str = None, dry_run: bool = False, force: bool = False,
           who: str = None, command: str = None) -> ReportResult:
    """새 기록으로 바꾸기 — 같은 모양으로 다시 만들어 차이를 보이고 적용한다. 손으로 고친 구역은 고친 곳을 보이고 force일 때만 덮는다."""
    path = _path(p, report)
    rel = _rel(p, path)
    if not os.path.isfile(path):
        raise ProjectError(f"없는 보고서 {rel}")
    if to and region is None:
        raise ProjectError("--to는 --region과 함께(구역 하나를 그 기록으로)")
    text = read_text(path)
    lines = text.split("\n")
    regs = regions(text)
    if region is not None and not any(r.n == region for r in regs):
        raise ProjectError(f"{rel}에 구역 #{region}이 없습니다(구역 {len(regs)}개)")
    items, edits, datas = [], [], []
    for r in regs:
        if region is not None and r.n != region:
            continue
        target = to or newest_like(p, r.record) or r.record
        shape = dict(r.shape)
        shape.pop("h", None)
        try:
            body, data = render(p, path, target, shape)
        except (RecordError, ProjectError) as e:
            items.append({"n": r.n, "record": r.record, "to": target, "status": "바꿀 수 없음", "detail": str(e)})
            continue
        if r.edited:
            hand = ""
            try:
                orig, _ = render(p, path, r.record, shape)
                hand = region_diff(orig, r.body, "보낸 것 → 지금")
            except (RecordError, ProjectError):
                hand = "(원래 기록이 없어 고친 곳을 견줄 수 없습니다)"
            if not force:
                items.append({"n": r.n, "record": r.record, "to": target, "status": "손으로 고침 — 바꾸지 않음(--force)",
                              "detail": "고친 곳", "diff": hand})
                continue
        diff = region_diff(r.body, body, f"#{r.n}")
        status = "바뀜" if diff else "그대로"
        items.append({"n": r.n, "record": r.record, "to": target,
                      "status": status + (" (미리보기)" if dry_run and diff else "") + (" · 손으로 고친 것을 덮음" if r.edited else ""),
                      "diff": diff})
        if diff or target != r.record:
            shape["h"] = _h(body)
            rec = store_of(p).get(target)
            edits.append((r, [_open_line(target, shape, data_label(rec.meta.get("data") or {})), body, CLOSE]))
            datas.append(data)
    change = None
    if edits and not dry_run:
        for r, block in sorted(edits, key=lambda x: -x[0].start):
            lines[r.start:r.end + 1] = block
        for d in datas:
            _write_data(p, path, d)
        ch = history_of(p).write_files({rel: "\n".join(lines)}, _who(who), command or f"report update {rel}",
                                       note="구역 " + ", ".join(f"#{r.n}" for r, _ in edits))
        change = ch.id if ch else None
    return ReportResult(rel, "update" + (" --dry-run" if dry_run else ""), items, change)
