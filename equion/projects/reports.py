#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""보고서 (D37) — `reports/*.md`. 명령 블록 없이 **결과만** 보낸다. 구역마다 보이지 않는 표시에 기록 이름·보낸 날·자료 회차·보낸 모양.

    <!-- equion:report sim:2026-11_base #1 · 2026-11-09 · d2026-11a {"record": …, "rows": […], "show": "yoy", "annual": true, …} -->
    **표 1. 주요 지표 전망** (연간 증가율, %)

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
from ..work.lock import locked
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
    from .config import project_path
    if not str(report or "").strip() or os.path.splitext(os.path.basename(str(report).strip()))[0] in ("", "."):
        raise ProjectError("보고서 이름이 비었습니다")
    name = report if report.endswith(".md") else f"{report}.md"
    if not os.path.isabs(name) and "/" not in name.replace(os.sep, "/"):
        name = os.path.join(REP_DIR, name)
    return project_path(p.root, name, "보고서")


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
def _ppy(labels) -> int:
    """기간 라벨 → 한 해의 기간 수(2020Q1 → 4 · 2020M3 → 12 · 2020 → 1)."""
    lab = str(next(iter(labels), ""))
    return 4 if re.fullmatch(r"\d{4}Q[1-4]", lab) else 12 if re.fullmatch(r"\d{4}M\d{1,2}", lab) else 1


def _sim_table(rec, shape):
    from .sim import _annual, _growth
    m = rec.meta
    rows = shape.get("rows") or m["endogenous"][:4]
    show = shape.get("show", "level")
    exo = m.get("exogenous", [])
    miss = [v for v in rows if v not in m["endogenous"] + exo]
    if miss:
        raise ProjectError(f"{rec.id}에 없는 시리즈: {', '.join(miss)} (내생: {', '.join(m['endogenous'][:8])} · 외생: "
                           f"{', '.join(exo[:8]) or '없음'})")
    if show == "diff":
        d = rec.read_csv("diff.csv") if os.path.isfile(rec.file("diff.csv")) else None
        if d is None:
            raise ProjectError(f"{rec.id}는 기준선 기록이라 차이(diff)가 없습니다 — 시나리오 기록에서")
        ex = [v for v in rows if f"{v}_%" not in d.columns]
        if ex:
            raise ProjectError(f"{rec.id}: {', '.join(ex)}는 외생변수라 기준선 대비 차이가 기록에 없습니다(시나리오가 준 경로는 "
                               "--show level · yoy로 봅니다) — 행에서 빼거나 다른 모양으로")
        t = pd.DataFrame({v: d[f"{v}_%"] for v in rows}).T
    elif shape.get("annual"):
        a = rec.read_csv("annual.csv")
        col = (lambda v: f"{v}_증가율") if show in ("yoy", "qoq") else (lambda v: v)
        lack = [v for v in rows if col(v) not in a.columns]
        if lack:                                   # 외생변수 — 기록의 수준(levels.csv)에서 같은 셈으로(연평균 · 앞 해 대비)
            lv = rec.read_csv("levels.csv")
            more = _annual(lv[[v for v in lack if v in lv.columns]], _ppy(lv.index), [str(y) for y in a.index])
            more.index = more.index.astype(str)
            a = a.copy()
            a.index = a.index.astype(str)
            for v in lack:
                a[col(v)] = more[col(v)] if col(v) in more.columns else np.nan
        t = pd.DataFrame({v: a[col(v)] for v in rows}).T
    else:
        fl = rec.read_csv("flags.csv")
        fc = [lab for lab in fl.index if (fl.loc[lab] == "해").any()]
        src = rec.read_csv("levels.csv") if show == "level" else rec.read_csv("growth.csv")
        col = (lambda v: v) if show == "level" else (lambda v: f"{v}_{'전기비' if show == 'qoq' else '전년동기비'}")
        lack = [v for v in rows if col(v) not in src.columns]
        if lack:                                   # 외생변수의 증가율 — 수준에서 같은 셈으로
            lv = rec.read_csv("levels.csv")
            g = _growth(lv[[v for v in lack if v in lv.columns]], _ppy(lv.index))
            src = pd.concat([src, g.reindex(src.index)], axis=1)
        t = pd.DataFrame({v: src.loc[fc, col(v)] for v in rows}).T
    t.index.name = "시리즈"
    unit = SHOW_KO["yoy" if (shape.get("annual") and show == "qoq") else show]
    if shape.get("annual") and show in ("yoy", "qoq"):
        unit = "연간 증가율, %"
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
    mixed = _mixed_years(rec, t) if rec.kind == "sim" and shape.get("annual") and shape.get("show") != "diff" else ""
    if mixed:
        parts += ["", mixed]
    parts += ["", f"자료: Equion {rec.id}({vint.replace('data:', '자료 회차 ')})"]
    return "\n".join(parts), data


def _mixed_years(rec, t) -> str:
    """연간 표에서 실측과 전망이 섞인 해 — '2020년은 실측 1기 + 전망 3기'."""
    try:
        fl = rec.read_csv("flags.csv")
    except OSError:
        return ""
    var = next((v for v in t.index if v in fl.columns), None)
    if var is None:
        return ""
    out = []
    for y in t.columns:
        labs = [lab for lab in fl.index if str(lab).startswith(str(y))]
        n_act = sum(1 for lab in labs if fl.loc[lab, var] == "실측")
        n_sol = sum(1 for lab in labs if fl.loc[lab, var] == "해")
        if n_act and n_sol:
            out.append(f"{y}년은 실측 {n_act}기 + 전망 {n_sol}기")
    return ("연간 값 — " + " · ".join(out)) if out else ""


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
    notes: List[str] = field(default_factory=list)   # 알아서 한 것(report new --from — 머리의 회차를 바꿈)

    def text(self) -> str:
        """명령줄에 보이는 짧은 글."""
        L = [f"[report {self.action}] {self.report}" + (f" — 구역 {len(self.items)}" if self.items and self.action != "add" else "")
             + (" — 이미 있어 그대로 둠" if self.exists else "")]
        for it in self.items:
            L.append(f"  #{it['n']} {it['record']}" + (f" → {it['to']}" if it.get("to") and it["to"] != it["record"] else "")
                     + f"  {it['status']}" + (f" — {it['detail']}" if it.get("detail") else ""))
            if it.get("diff"):
                L += ["    " + x for x in it["diff"].rstrip().splitlines()[:40]]
        L += [f"  알아서 한 것  {x}" for x in self.notes]
        if self.change:
            L.append(f"  바뀜 기록  {self.change}")
        return "\n".join(L)

    def to_dict(self) -> dict:
        """명령줄 --json과 같은 사전."""
        return {"report": self.report, "action": self.action, "items": self.items, "change": self.change,
                "exists": self.exists, "notes": self.notes}


@locked
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
    items, notes = [], []
    if from_report:
        src = _path(p, from_report)
        if not os.path.isfile(src):
            raise ProjectError(f"없는 보고서: {_rel(p, src)}")
        text = read_text(src)
        old_v = about_vintage(p, text)
        if old_v and p.vintage and old_v != p.vintage:   # 새 보고서는 지금 회차의 보고서 — 머리(첫 구역 앞)의 회차를 지금 회차로
            head, sep, rest = text.partition("<!-- equion:report")
            if report_vintage(text):
                head = _VID.sub(p.vintage, head)
            else:                                        # 머리에 회차가 없었다 — 제목 아래에 한 줄
                hl = head.split("\n")
                k = next((i + 1 for i, x in enumerate(hl) if x.startswith("# ")), 0)
                hl[k:k] = ["", f"자료 회차 {p.vintage}"] if k else [f"자료 회차 {p.vintage}", ""]
                head = "\n".join(hl)
            text = head + sep + rest
            notes.append(f"머리의 자료 회차 {old_v} → {p.vintage}(구역은 report update로 이 회차의 기록으로)")
        for r in regions(text):
            newer = newest_like(p, r.record, p.vintage)
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
    return ReportResult(rel, "new", items, ch.id if ch else None, notes=notes)


@locked
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
    """갈래의 굵은 열쇠 — 이것이 같아야 같은 갈래(자세한 것은 `_same_run`)."""
    m = rec.meta
    if rec.kind == "sim":
        return ("sim", m.get("model"), m.get("scenario"), m.get("mode"))
    if rec.kind == "hs":
        rp = (m.get("replay") or {}).get("of")
        return ("hs", m.get("model"), m.get("mode"), tuple(sorted((m.get("swaps") or {}).items())), rp)
    if rec.kind == "est":
        cov = m.get("cov") or {}
        return ("est", m.get("part") or m.get("target"), m.get("text"), m.get("method_label") or m.get("method"), cov.get("type"))
    return ("an", m.get("analysis"), m.get("target"), json.dumps(m.get("options") or {}, sort_keys=True, default=str),
            str(m.get("smpl") or ""))


def sim_pin(m: dict) -> Optional[str]:
    """`sim --vintage`로 다른 자료 회차에 묶어 푼 전망이면 그 회차(아니면 None). 옛 기록은 '알아서 한 것'의 글로 알아본다."""
    if "vintage_pin" in m:
        return m["vintage_pin"]
    for x in m.get("implicit") or []:
        if str(x).startswith("자료 회차 ") and "(지금 회차는 그대로)" in str(x):
            return (m.get("data") or {}).get("id")
    return None


_VID = re.compile(r"(?<![A-Za-z0-9_])d\d{4}-\d{2}[a-z]+(?![A-Za-z0-9_])")


def report_vintage(text: str) -> Optional[str]:
    """보고서가 다루는 자료 회차 — 머리(첫 구역 앞)에 적힌 회차 이름이 하나면 그것(`report new`가 적는 '자료 회차 d2026-11b'와 제목),
    없거나 여럿이면 None."""
    head = text.split("<!-- equion:report", 1)[0]
    ids = set(_VID.findall(head))
    return ids.pop() if len(ids) == 1 else None


def rec_vintage(rec) -> Optional[str]:
    """기록이 계산에 쓴 자료 회차(자료 파일 하나 프로젝트면 None)."""
    d = rec.meta.get("data") or {}
    return d.get("id") if d.get("kind") == "vintage" else None


def _same_run(p, a, b) -> bool:
    """b가 a와 같은 갈래의 계산이라 보고서 구역을 b로 바꿔 껴도 되는가 — '더 새 기록'은 같은 계산을 새 자료로 다시 한 것이지
    실험·다른 후보가 아니다.

    전망: 모형·시나리오·풀이 방식이 같고, 다른 자료 회차에 묶어 푼 것(`--vintage`)이 아니다(지금 회차에 묶은 것은 된다 —
    a가 묶인 것이면 같은 회차에 묶인 것만). 구간은 달라도 된다(새 자료로 늘어난 전망). 과거 재현: 모형(블록)·풀이 방식이 같고
    바꿔 끼우기(`--swap`)·그때 그대로 다시(`--replay`)가 a와 같다(보통은 둘 다 없음). 추정: 부품(없으면 목표)·식 글자·추정법·
    계수 공분산 종류·표본 표기(--smpl)가 같다 — 같은 식을 새 자료로 다시 추정한 것(`est --adopted`)이지 다른 후보가 아니다.
    분석: 분석·대상·옵션·표본이 같다."""
    if a.kind != b.kind or _family(a) != _family(b):
        return False
    ma, mb = a.meta, b.meta
    if a.kind == "sim":
        pa, pb = sim_pin(ma), sim_pin(mb)
        if pa and pa != p.vintage:
            return pb == pa
        return pb is None or pb == p.vintage
    if a.kind == "est":
        if "smpl" in ma and "smpl" in mb:
            return ma["smpl"] == mb["smpl"]
        return (ma.get("sample") or [None])[0] == (mb.get("sample") or [None])[0]   # 옛 기록: 표본 시작으로
    return True


def newest_like(p, rid: str, vintage: Optional[str] = None) -> Optional[str]:
    """같은 갈래의 가장 새 기록(`_same_run` — 같은 종류의 계산을 다시 한 것만, 실험·다른 후보·다른 회차에 묶은 것은 아니다).

    자료 회차의 규칙: 바꿔 낄 기록은 보고서가 다루는 회차(vintage — `about_vintage`)에서 계산한 것만이다. vintage가 없으면 원래 기록의
    회차에서 계산한 것만. 그래서 옛 회차에 잠깐 다녀온 계산이 지금 회차 보고서의 '더 새 기록'이 되지 않고, 1월 보고서를 몇 달 뒤 고쳐도
    뒤 회차의 전망이 1월 제목 아래 끼지 않는다. 새 회차의 보고서는 `report new 새이름 --from 이것`(머리의 회차를 지금 회차로) 다음
    `report update`. 고를 것이 없으면 원래 기록."""
    store = store_of(p)
    try:
        rec = store.get(rid)
    except RecordError:
        return None
    want = vintage or rec_vintage(rec)
    same = [r for r in store.records(rec.kind) if (r.id == rec.id or _same_run(p, rec, r)) and rec_vintage(r) == want]
    return same[-1].id if same else rid


def later_like(p, rid: str, vintage: Optional[str]) -> Optional[str]:
    """보고서 회차보다 뒤에 만든 회차에서 같은 계산을 다시 한 가장 새 기록(알림용 — 바꿔 끼지 않는다). 없으면 None."""
    from .vintage import list_vintages
    store = store_of(p)
    try:
        rec = store.get(rid)
    except RecordError:
        return None
    base = vintage or rec_vintage(rec)
    order = [v["id"] for v in list_vintages(p.root)]
    if base not in order:
        return None
    later = [r for r in store.records(rec.kind) if r.id != rec.id and _same_run(p, rec, r)
             and rec_vintage(r) in order and order.index(rec_vintage(r)) > order.index(base)]
    return later[-1].id if later else None


def about_vintage(p, text: str) -> Optional[str]:
    """보고서가 다루는 자료 회차 — 머리(첫 구역 앞)에 적힌 회차 하나(`report_vintage`), 없으면 구역 기록들이 모두 같은 회차면 그것.
    둘 다 아니면 None(그때는 구역마다 그 기록의 회차)."""
    rv = report_vintage(text)
    if rv:
        return rv
    store = store_of(p)
    vs = set()
    for r in regions(text):
        try:
            vs.add(rec_vintage(store.get(r.record)))
        except RecordError:
            continue
    vs.discard(None)
    return vs.pop() if len(vs) == 1 else None


def check(p, report: str) -> ReportResult:
    """보고서 검사 — 구역마다 없는 기록 · 더 새 기록 · 낡음(자료·정의가 바뀜) · 손으로 고침."""
    path = _path(p, report)
    rel = _rel(p, path)
    if not os.path.isfile(path):
        raise ProjectError(f"없는 보고서 {rel}")
    store = store_of(p)
    items = []
    text = read_text(path)
    rv = about_vintage(p, text)
    for r in regions(text):
        st, detail, to = [], [], None
        try:
            rec = store.get(r.record)
        except RecordError:
            items.append({"n": r.n, "record": r.record, "status": "없는 기록", "detail": "기록이 지워졌습니다"})
            continue
        if rv and rec_vintage(rec) and rec_vintage(rec) != rv:
            st.append("다른 회차")
            detail.append(f"구역의 기록은 회차 {rec_vintage(rec)} — 보고서는 회차 {rv}")
        newer = newest_like(p, r.record, rv)
        if newer and newer != r.record:
            st.append("더 새 기록")
            detail.append(newer)
            to = newer
        later = later_like(p, r.record, rv)
        if later:
            st.append("새 회차에 같은 계산")
            detail.append(f"{later}(회차 {rec_vintage(store.get(later))}) — 이 보고서는 회차 {rv or rec_vintage(rec)}의 것이라 바꿔 끼지 "
                          f"않습니다. 새 회차의 보고서는 equion report new 새이름 --from {rel}")
        sr = stale_reasons(p, rec)
        if sr:
            st.append("낡음")
            detail += sr
        if r.edited:
            st.append("손으로 고침")
        items.append({"n": r.n, "record": r.record, "to": to, "status": " · ".join(st) or "정상", "detail": "; ".join(detail)})
    return ReportResult(rel, "check", items)


@locked
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
    rv = about_vintage(p, text)                # 보고서가 다루는 회차 — 바꿔 낄 기록은 그 회차에서 계산한 것만
    if region is not None and not any(r.n == region for r in regs):
        raise ProjectError(f"{rel}에 구역 #{region}이 없습니다(구역 {len(regs)}개)")
    items, edits, datas = [], [], []
    for r in regs:
        if region is not None and r.n != region:
            continue
        target = to or newest_like(p, r.record, rv) or r.record
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
