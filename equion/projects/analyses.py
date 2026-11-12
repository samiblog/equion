#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""분석 (D37, E4) — 등록부의 분석 하나 = 명령 하나(`equion an <분석> <대상>`) = 기록 하나(`work/an/<이름>/`) = md 카드 하나.

세 갈래로 나뉜다.

    보는 분석       summary · unitroot · coint · diag · fcsteval · stability · multipliers · stats · hist · acf · corr · xcorr ·
                    granger · fevd · convert · stochastic — 아무 파일도 바꾸지 않는다
    만드는 분석     seas · genr — `an keep`이 정의(series.toml · derived.txt)로 남긴다. 실측 자리에 바로 쓰지 않는다
    부품을 내는 분석  ecm · var · vecm · system — `an keep`이 식 후보(est: 기록)로 남긴다. 채택은 사람이(adopt)

계산은 워크파일 API·엔진(`equion.stats`)으로 한다. 이 층은 대상(시리즈·묶음·식·부품·모형·기록)을 풀고 기록·카드를 남긴다.
"""

import os
import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd

from .. import registry as reg
from ..registry import Analysis, Opt, register
from ..reporting import markdown as md
from ..workfile.runtime import quiet
from ..work.store import WHO_KO, Record, now_iso
from .config import NAME_RE, ProjectError
from .records import (_version, _who, data_label, data_spec, definition_hashes, history_of, pfmt, record_equation,
                      short, store_of)


@dataclass
class AnOut:
    """분석 하나의 결과 — 기록 쓰기 전."""

    title: str
    target: str
    sample: Optional[Tuple[str, str]] = None
    tables: List[Tuple[str, pd.DataFrame]] = field(default_factory=list)
    charts: List[tuple] = field(default_factory=list)      # (제목, 표, 시리즈) 선 차트 · (제목, 표, 시리즈, {kind: bar·heat·scatter, …})
    lines: List[str] = field(default_factory=list)
    implicit: List[str] = field(default_factory=list)
    payload: dict = field(default_factory=dict)
    makes: Optional[dict] = None
    inputs: dict = field(default_factory=dict)


@dataclass
class AnRecord:
    """분석 기록 하나 — `.id`(an:…) · `.meta`(record.json) · `.table(k)`(표 k번, 1부터) · `.text()` · `.to_dict()`."""

    record: Record

    @property
    def id(self) -> str:
        """기록 이름 an:…"""
        return self.record.id

    @property
    def meta(self) -> dict:
        """record.json 내용."""
        return self.record.meta

    def table(self, k: int = 1) -> pd.DataFrame:
        """표 k번(1부터 — table_k.csv)."""
        return self.record.read_csv(f"table_{k}.csv")

    def text(self) -> str:
        """명령줄에 보이는 짧은 글."""
        return an_text(self.meta)

    def to_dict(self) -> dict:
        """명령줄 --json과 같은 사전."""
        d = dict(self.meta)
        d["path"] = self.record.path
        return d

    def __repr__(self):
        return f"<분석 기록 {self.id}: {self.meta.get('label')} {self.meta.get('target')}>"


def an_text(m: dict) -> str:
    head = f"[{m['id']}] {m['label']} · {m['target_label']}"
    if m.get("sample"):
        head += f" · {m['sample'][0]}~{m['sample'][1]}"
    head += f" · 자료 {data_label(m['data'])}"
    L = [head] + [f"  {x}" for x in m.get("lines", [])]
    if m.get("implicit"):
        L.append("  알아서 한 것  " + " · ".join(m["implicit"]))
    if m.get("makes"):
        L.append(f"  남기기   equion an keep {m['id']} — {reg.MAKES_KO[m['makes']['kind']]}로")
    L.append(f"  기록   {m['id']} ({m['path']}/summary.md)")
    return "\n".join(L)


def _an_md(m: dict, tables, charts) -> str:
    head = [("기록", f"`{m['id']}`"), ("명령", f"`{m['command']}`"), ("자료", data_label(m["data"])),
            ("표본", f"{m['sample'][0]}~{m['sample'][1]}" if m.get("sample") else None),
            ("누가 · 언제", f"{WHO_KO.get(m['who'], m['who'])} · {m.get('created') or now_iso()}"), ("equion", m["equion"])]
    secs = []
    for k, (title, df) in enumerate(tables, 1):
        if len(df) > 24:
            body = md.table(df.tail(12)) + f"\n\n(끝 12행 — 전체 {len(df)}행은 `table_{k}.csv`)"
        else:
            body = md.table(df)
        secs.append((title, body))
    for k, chart in enumerate(charts, 1):
        title, df, series = chart[:3]
        spec = chart[3] if len(chart) > 3 else {}
        x = df.index.name or "period"
        csv = f"chart_{k}.csv"
        kind = spec.get("kind", "line")
        if kind == "bar":
            body = md.vega_bar(csv, x, spec.get("y", series[0]), title, band=spec.get("band"), line=spec.get("line"))
        elif kind == "heat":
            body = md.vega_heat(csv, title=title)
        elif kind == "scatter":
            body = md.vega_scatter(csv, spec["x"], spec["y"], title)
        else:
            body = md.vega_line(csv, x, series, title)
        secs.append((title, body))
    secs.append(("알아서 한 것", md.bullets(m.get("implicit") or [])))
    return md.card(f"{m['label']} — {m['target_label']}", head, secs)


def _command(name: str, target: str, opts: dict, defaults: dict, smpl: str = None) -> str:
    """기록에 적을 명령(명령줄 그대로 다시 돌릴 수 있게 — 따옴표 · 기본값과 다른 옵션 · 표본)."""
    import shlex
    words = ["an", name, str(target)]
    for k, v in opts.items():
        if v is None or v == defaults.get(k):
            continue
        flag = "--" + k.replace("_", "-")
        if isinstance(v, bool):
            words.append(flag if v else "--no-" + k.replace("_", "-"))
        elif isinstance(v, (list, tuple)):
            words += [flag, ",".join(map(str, v))]
        else:
            words += [flag, str(v)]
    if smpl:
        words += ["--smpl", str(smpl)]
    return shlex.join(words)


def run_an(p, name: str, target: str, options: dict = None, smpl: str = None, as_name: str = None, note: str = None,
           who: str = None, command: str = None) -> AnRecord:
    """분석 하나를 돌려 기록을 남긴다. note를 주면 그 노트 끝에 명령 블록과 결과 구역을 더한다."""
    a = reg.get(name)
    if name == "split" and smpl:
        raise ProjectError("요인 나누기는 표본(--smpl)을 쓰지 않습니다 — 두 기록의 전망 구간을 그대로 나눕니다")
    opts = a.defaults()
    defaults = dict(opts)
    for k, v in (options or {}).items():
        if k not in opts:
            raise ProjectError(f"{name}: 모르는 옵션 --{k} (옵션: {', '.join('--' + o for o in opts) or '없음'})")
        if v is not None:
            opts[k] = v
    history_of(p).scan()
    store = store_of(p)
    rname = as_name or store.next_name("an", name)
    store.check_new("an", rname)
    from ..workfile.output import verbose
    wf = p.workfile
    old, old_v = wf._smpl, verbose()
    verbose(0)                            # 엔진의 요약 줄은 감춘다 — 결과는 기록의 짧은 글·카드에
    try:
        if smpl:
            s0, e0 = p.span(smpl)
            quiet(wf.smpl, s0, e0)
        try:
            out = a.run(p, target, **opts)
        except (ValueError, KeyError, RuntimeError, np.linalg.LinAlgError) as ex:
            if isinstance(ex, ProjectError):
                raise
            raise ProjectError(f"{a.label}({target}): {ex.args[0] if isinstance(ex, KeyError) else ex}") from None
    finally:
        wf._smpl = old
        verbose(old_v)
    cmd = command or _command(name, target, opts, defaults, smpl)
    meta = {"who": _who(who), "command": cmd, "project": p.name, "equion": _version(), "analysis": name,
            "label": a.label, "target": target, "target_label": out.target, "options": opts, "smpl": smpl,
            "sample": list(out.sample) if out.sample else None, "lines": out.lines, "implicit": out.implicit,
            "result": out.payload, "makes": out.makes, "data": data_spec(p), "inputs": out.inputs,
            "tables": [t for t, _ in out.tables], "charts": [c[0] for c in out.charts],
            "path": f"work/an/{rname}", "id": f"an:{rname}"}
    files = {}
    for k, (_, df) in enumerate(out.tables, 1):
        files[f"table_{k}.csv"] = df
    for k, chart in enumerate(out.charts, 1):
        files[f"chart_{k}.csv"] = chart[1]
    rec = store.write("an", rname, meta, files, _an_md(meta, out.tables, out.charts),
                      log={"metric": out.lines[0][:80] if out.lines else ""})
    r = AnRecord(rec)
    if note:
        from .notes import append_block
        append_block(p, note, cmd, r.id, who=who)
    return r


# ---------------------------------------------------------------------------
# 대상 풀기
# ---------------------------------------------------------------------------
def _tokens(text: str) -> List[str]:
    """괄호 밖 공백으로 나눈다('log(Y) dlog(CN)' → 두 개)."""
    out, cur, depth = [], "", 0
    for ch in str(text).strip():
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch.isspace() and depth == 0:
            if cur:
                out.append(cur)
            cur = ""
        else:
            cur += ch
    if cur:
        out.append(cur)
    return out


def _items(p, target: str) -> Tuple[str, List[str]]:
    """대상 → (보이는 이름, 시리즈·식 목록). 묶음([group])이면 그 시리즈(변환 transform을 씌워)."""
    for g in p.config.groups.values():
        if g.name.lower() == str(target).strip().lower():
            items = [f"{g.transform}({s})" if g.transform else s for s in g.series]
            return f"묶음 {g.name}({' · '.join(items)})", items
    items = _tokens(target)
    if not items:
        raise ProjectError("대상이 없습니다 — 시리즈·묶음·식")
    return " · ".join(items), items


def _ser(wf, x) -> pd.Series:
    return wf[x] if wf._col(x) else wf.eval(x)


def _sample_of(wf, df) -> Tuple[str, str]:
    return wf._label(df.index[0]), wf._label(df.index[-1])


def _frame(wf, items) -> pd.DataFrame:
    return quiet(wf._test_frame, items)


def _labelled(wf, df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.index = pd.Index([wf._label(t) for t in df.index], name="period")
    return out


# ---------------------------------------------------------------------------
# 보는 분석
# ---------------------------------------------------------------------------
def _summary(p, target):
    wf = p.workfile
    label, items = _items(p, target)
    meta, flags = {}, None
    if p.config.uses_vintages and p.vintage:
        from .vintage import read_vintage
        _, flags, vm = read_vintage(p.root, p.vintage)
        meta = vm.get("series", {})
    s0, e0 = wf._bounds()
    rows = {}
    chart = pd.DataFrame(index=wf.data.index[s0:e0 + 1])
    for it in items:
        s = _ser(wf, it).iloc[s0:e0 + 1]
        fv, lv = s.first_valid_index(), s.last_valid_index()
        inside = s.loc[fv:lv] if fv is not None else s.iloc[:0]
        kinds = ""
        if flags is not None and it in flags.columns:
            vc = flags[it].value_counts()
            kinds = " · ".join(f"{k} {int(v)}" for k, v in vc.items() if k != "missing")
        rows[it] = {"처음": wf._label(fv) if fv is not None else "", "끝": wf._label(lv) if lv is not None else "",
                    "값": int(s.notna().sum()), "안쪽 결측": int(inside.isna().sum()),
                    "마지막 값": float(s.loc[lv]) if lv is not None else np.nan,
                    "단위": meta.get(it, {}).get("unit", ""), "설명": meta.get(it, {}).get("desc", ""), "값의 종류": kinds}
        chart[it] = s.to_numpy()
    tab = pd.DataFrame.from_dict(rows, orient="index")
    tab.index.name = "시리즈"
    lines = [f"{k:<10} {v['처음']}~{v['끝']} · 값 {v['값']}" + (f" · 안쪽 결측 {v['안쪽 결측']}" if v["안쪽 결측"] else "")
             + (f" · 끝 {short(v['마지막 값'])}" if np.isfinite(v["마지막 값"]) else "") for k, v in rows.items()]
    return AnOut("요약", label, (wf._label(wf.data.index[s0]), wf._label(wf.data.index[e0])),
                 [("시리즈 요약", tab)], [("수준", _labelled(wf, chart.dropna(how="all")), list(items)[:6])], lines,
                 payload={"rows": rows})


def _unitroot(p, target, trend="c", lags=None, ic="bic", maxlag=None):
    wf = p.workfile
    label, items = _items(p, target)
    rows, lines, implicit, spans = {}, [], [], []
    for it in items:
        a = quiet(wf.adf, it, trend=trend, lags=lags, ic=ic, maxlag=maxlag)
        kt = "c" if trend == "n" else trend
        k = quiet(wf.kpss, it, trend=kt)
        adf_rej, kpss_rej = a.pvalue < 0.05, k.pvalue < 0.05
        verdict = ("정상" if adf_rej and not kpss_rej else "단위근" if not adf_rej and kpss_rej else "엇갈림 — 두 검정이 다르다")
        rows[it] = {"ADF t": a.statistic, "ADF p": a.pvalue, "시차": int(a.details.get("lags", 0)),
                    "KPSS": k.statistic, "KPSS p": k.pvalue, "판단": verdict}
        spans.append(a.info.get("표본", ""))
        lines.append(f"{it:<12} ADF {a.statistic:.3f} p={pfmt(a.pvalue)} · KPSS {k.statistic:.3f} p={pfmt(k.pvalue)} → {verdict}")
    tab = pd.DataFrame.from_dict(rows, orient="index")
    tab.index.name = "시리즈"
    if lags is None:
        implicit.append(f"ADF 시차 수를 {ic.upper()}로 골랐다" + (f"(최대 {maxlag})" if maxlag else ""))
    if trend == "n":
        implicit.append("KPSS는 결정항 없음이 없어 상수로")
    implicit.append("판단: ADF(귀무 단위근)·KPSS(귀무 정상) 모두 5%")
    sample = None
    if spans and spans[0] and "~" in str(spans[0]):
        a_, b_ = str(spans[0]).split("~")[:2]
        sample = (a_.strip().split()[0], b_.strip().split()[0])
    return AnOut("단위근", label, sample, [("단위근 검정", tab)], [], lines, implicit,
                 payload={"rows": rows, "trend": trend})


def _coint(p, target, method="johansen", trend="c", lags=1, det=0):
    wf = p.workfile
    label, items = _items(p, target)
    if len(items) < 2:
        raise ProjectError("공적분은 시리즈 둘 이상(묶음 또는 'Y X1 X2')")
    if method == "engle":
        r = quiet(wf.coint, items[0], items[1:], trend=trend, lags=None if lags in (None, 0) else lags)
        tab = r.frame()
        lines = [f"Engle-Granger τ {r.statistic:.3f} p={pfmt(r.pvalue)} → " + ("공적분" if r.pvalue < 0.05 else "공적분 아님(5%)")]
        payload = {"statistic": r.statistic, "pvalue": r.pvalue}
    else:
        r = quiet(wf.johansen, items, det=det, lags=lags)
        tab = r.table.copy()
        rt, rm = r.details.get("rank_trace"), r.details.get("rank_maxeig")
        lines = [f"Johansen 순위(5%) 트레이스 {rt} · 최대 고유값 {rm}"]
        payload = {"rank_trace": rt, "rank_maxeig": rm}
    sample = None
    sp = str(r.info.get("표본", ""))
    if "~" in sp:
        a_, b_ = sp.split("~")[:2]
        sample = (a_.strip().split()[0], b_.strip().split()[0])
    return AnOut("공적분", label, sample, [(r.name, tab)], [], lines,
                 [f"{'Johansen' if method != 'engle' else 'Engle-Granger'} — 차분 시차 {lags}"], payload)


def _diag(p, target, lags=2, chow=None, cusum=True):
    from ..workfile.objects import EquationObject
    wf = p.workfile
    t = str(target).strip()
    implicit = []
    if t.startswith("est:"):
        rec = store_of(p).get(t, "est")
        expr, label = rec.meta["expr"], f"{t} ({rec.meta['text']})"
        if rec.meta["data"] != data_spec(p):
            implicit.append(f"기록의 자료({data_label(rec.meta['data'])})가 지금과 달라 지금 자료로 다시 추정")
    else:
        pt = p.part(t)
        if pt.kind != "equation":
            raise ProjectError(f"{pt.id}는 항등식입니다 — 진단은 추정식만")
        expr, label = pt.expr, f"{pt.id} ({pt.text})"
    obj = EquationObject(wf, "diag")
    obj._adopt(obj._make(expr, method="tsls" if "@inst" in expr else None), expr, loud=False)
    implicit.append("지금 자료로 추정해 진단(채택 계수가 아니라)")
    tabs, charts, lines = [], [], []
    d = obj.diagnostics(lags).data
    tabs.append(("진단 검정", d))
    bad = [n for n, r in d.iterrows() if r["p값"] < 0.05]
    lines.append("진단   " + " · ".join(f"{n} p={pfmt(r['p값'])}" for n, r in d.iterrows()))
    lines.append("5%에서 기각  " + (" · ".join(bad) if bad else "없음"))
    for per in ([chow] if isinstance(chow, str) else (chow or [])):
        for x in str(per).split(","):
            x = x.strip()
            if not x:
                continue
            c = quiet(obj.chow, x)
            tabs.append((f"Chow 구조 변화 {x}", c.frame()))
            lines.append(f"Chow {x}  F {c.statistic:.3f} p={pfmt(c.pvalue)}" + (" → 구조 변화" if c.pvalue < 0.05 else ""))
    if cusum and obj.method == "ols":
        try:
            cu = quiet(obj.cusum)
            charts.append(("CUSUM(5% 경계)", _labelled(wf, cu.data), list(cu.data.columns)))
            lines.append(f"CUSUM  경계 대비 {cu.statistic:.2f}" + (" → 경계를 벗어남" if cu.statistic >= 1 else " (경계 안)"))
        except ValueError as ex:
            implicit.append(f"CUSUM 못 함: {ex}")
    res = obj.resid
    sample = (wf._label(res.index[0]), wf._label(res.index[-1]))
    return AnOut("식 진단", label, sample, tabs, charts, lines, implicit,
                 payload={"tests": {n: {"stat": float(r["통계량"]), "p": float(r["p값"])} for n, r in d.iterrows()}},
                 inputs={"expr": expr})


def _record_series(p, rid, var):
    rec = store_of(p).get(rid)
    wf = p.workfile
    if rec.kind == "hs":
        df = rec.read_csv("solved.csv")
    elif rec.kind == "sim":
        df = rec.read_csv("levels.csv")
        fl = rec.read_csv("flags.csv")
        if var in fl.columns:
            df = df[fl[var] == "해"]
    elif rec.kind == "est":
        sd = rec.read_csv("series.csv")
        col = f"{var}_sim"
        if col not in sd.columns:
            raise ProjectError(f"{rid}에 {var}의 단독 모의가 없습니다 — est … --sim으로 만든 기록")
        df = pd.DataFrame({var: sd[col]})
    else:
        raise ProjectError(f"{rid}: 예측 평가는 hs·sim·est(--sim) 기록")
    if var not in df.columns:
        raise ProjectError(f"{rid}에 {var}가 없습니다")
    labels = [wf._label(t) for t in wf.data.index]
    s = pd.Series(np.nan, index=wf.data.index, name=rid)
    for lab, v in df[var].dropna().items():
        if lab in labels:
            s.iloc[labels.index(lab)] = float(v)
    return s, rec


def _fcsteval(p, target, var=None):
    wf = p.workfile
    ids = _tokens(target)
    if not var:
        raise ProjectError("--var 변수(예: --var Y)를 주세요 — 견줄 변수")
    if len(ids) < 1:
        raise ProjectError("견줄 기록(hs:· sim:· est:)을 하나 이상")
    fs, implicit = [], []
    for rid in ids:
        s, rec = _record_series(p, rid, var)
        if rec.meta.get("data") != data_spec(p):
            implicit.append(f"{rid}의 자료({data_label(rec.meta['data'])})가 지금과 다름 — 실측은 지금 자료")
        fs.append(s)
    tab = wf.forecast_eval(var, *fs).data
    lines = [f"{k:<18} RMSE {short(r['RMSE'])} · MAE {short(r['MAE'])}" + (f" · Theil U1 {short(r['Theil U1'])}" if "Theil U1" in r else "")
             for k, r in tab.iterrows()]
    tabs = [(f"예측 평가 — 실측 {var}", tab)]
    payload = {"rows": {k: {c: float(v) for c, v in r.items() if isinstance(v, (int, float))} for k, r in tab.iterrows()}}
    if len(fs) >= 2:
        dm = quiet(wf.dm_test, var, fs[0], fs[1])
        tabs.append((f"Diebold-Mariano — {ids[0]} 대 {ids[1]}", dm.frame()))
        lines.append(f"DM {dm.statistic:.3f} p={pfmt(dm.pvalue)}" + (f" → {ids[0] if dm.statistic < 0 else ids[1]}이 더 정확(5%)"
                                                                    if dm.pvalue < 0.05 else " → 차이 없음(5%)"))
        payload["dm"] = {"statistic": dm.statistic, "pvalue": dm.pvalue}
    both = pd.concat([_ser(wf, var).rename(var)] + fs, axis=1).dropna(subset=[f.name for f in fs], how="all")
    return AnOut("예측 평가", f"{var} · " + " · ".join(ids), None, tabs,
                 [(f"{var} — 실측과 예측", _labelled(wf, both), [var] + ids)], lines, implicit, payload,
                 inputs={"records": ids})


def _split(p, target, vars=None):
    from .split import split
    payload, tables, charts, lines, implicit, (old, new) = split(p, target, vars)
    return AnOut("요인 나누기", f"{new.id} ← {old.id}", tuple(new.meta["range"]), tables, charts, lines, implicit, payload,
                 inputs={"records": [old.id, new.id]})


def _stability(p, target, period=None):
    m = p.model(target)
    sv = m.stability(period)
    tab = sv.output().data
    lines = [f"최대 |λ| {sv.max_modulus:.4f} → {sv.verdict}" + (f" · {sv.r.period}" if getattr(sv.r, "period", None) else "")]
    return AnOut("동태 안정성", f"모형 {target}", None, [("고윳값(선형화 동반행렬)", tab)], [], lines,
                 ["선형화 시점: " + str(getattr(sv.r, "period", "") or "자료 끝")], {"max_modulus": sv.max_modulus,
                                                                                "verdict": sv.verdict},
                 inputs={"files": definition_hashes(p)})


def _multipliers(p, target, var=None, shock=1.0, range=None, kind="level"):
    if not var:
        raise ProjectError("--var 충격 줄 외생변수(예: --var G)")
    m = p.model(target)
    s, e = p.span(range) if range else p._range(None, None)
    mu = m.multipliers(var, float(shock), s, e, kind=kind)
    wf = p.workfile
    lv = _labelled(wf, mu.level)
    pc = _labelled(wf, mu.pct)
    lines = [f"{v:<6} 첫 기 {short(lv[v].iloc[0])} · 끝 기 {short(lv[v].iloc[-1])} (수준 차)" for v in list(lv.columns)[:6]]
    return AnOut("충격 승수", f"모형 {target} · {var} {'+' if float(shock) >= 0 else ''}{shock}{'%' if kind == 'pct' else ''}",
                 (s, e), [("수준 차(충격 − 기준선)", lv), ("% 차", pc)], [("수준 차", lv, list(lv.columns)[:4])], lines,
                 [f"충격 {var} {shock} ({kind}) {s}~{e} 내내"], {"var": var, "shock": shock},
                 inputs={"files": definition_hashes(p)})


# ---------------------------------------------------------------------------
# 만드는 분석 — 정의로 남긴다
# ---------------------------------------------------------------------------
def _seas(p, target, method="stl", model="additive", robust=False):
    wf = p.workfile
    items = _tokens(target)
    if len(items) != 1 or not wf._col(items[0]):
        raise ProjectError("계절조정은 시리즈 하나(자료 회차의 시리즈 이름)")
    x = items[0]
    kw = {"robust": True} if robust and method == "stl" else {}
    r = quiet(wf.seas, x, method=method, model=model, write=False, **kw)
    tab = _labelled(wf, r.table)
    seas = {"method": method, "model": model}
    if kw:
        seas["robust"] = True
    lines = [f"{x}: {method} {model}" + (" robust" if kw else "") + f" · {tab.index[0]}~{tab.index[-1]}",
             f"계절 성분 폭 {short(float(r.table['계절'].max() - r.table['계절'].min()))}"]
    return AnOut("계절조정", x, (tab.index[0], tab.index[-1]), [("분해", tab)],
                 [("실측 · 조정 · 추세", tab, ["실측", "조정", "추세"])], lines,
                 ["관측 구간만 분해", "미리보기 — 자료에 넣으려면 an keep(정의) → data build → data use"],
                 {"seas": seas}, makes={"kind": "definition", "series": x, "seas": seas})


def _genr(p, target):
    wf = p.workfile
    name, eq, expr = str(target).partition("=")
    name, expr = name.strip(), expr.strip()
    if not eq or not expr or not NAME_RE.match(name):
        raise ProjectError("파생은 '이름 = 식'(예: \"RR2 = R - 100*dlog(P,4)\")")
    if wf._col(name):
        raise ProjectError(f"이미 있는 시리즈 {name} — 다른 이름으로")
    s = wf.eval(expr)
    df = pd.DataFrame({name: s})
    fv, lv = s.first_valid_index(), s.last_valid_index()
    if fv is None:
        raise ProjectError(f"{expr}: 값이 하나도 없습니다")
    tab = _labelled(wf, df.loc[fv:lv])
    lines = [f"{name} = {expr} · {wf._label(fv)}~{wf._label(lv)} · 끝 {short(float(s.loc[lv]))}"]
    return AnOut("파생", f"{name} = {expr}", (wf._label(fv), wf._label(lv)), [("값", tab)], [(name, tab, [name])], lines,
                 ["미리보기 — 자료에 넣으려면 an keep(derived.txt 한 줄) → data build → data use"],
                 {"name": name, "expr": expr}, makes={"kind": "derived", "name": name, "expr": expr})


# ---------------------------------------------------------------------------
# 부품을 내는 분석 — 식 후보로 남긴다
# ---------------------------------------------------------------------------
def _eq_payload(objs) -> list:
    return [{"text": o.spec, "target": o.eq.target, "saved": o.eq.to_saved()} for o in objs]


def _ecm(p, target, method="two-step", lags=0):
    wf = p.workfile
    items = _tokens(target)
    if len(items) < 2:
        raise ProjectError("ECM은 'Y X1 X2…'(목표와 설명 변수 — 보통 로그 수준: 'log(CN) log(Y)')")
    r = quiet(wf.ecm, "an_ecm", items[0], items[1:], method=method, lags=lags)
    tabs = [("장기식", r.longrun()), ("단기식", r.shortrun.output().data)]
    al = r.adjustment
    lines = ["장기  " + " · ".join(f"{k} {short(v)}" for k, v in r.longrun()["계수"].items()),
             f"조정 속도 α {short(float(al['계수']))} (t {short(float(al['t값']))}) · 반감기 {short(r.half_life)}기",
             f"단기식  {r.shortrun.spec}"]
    if r.coint is not None:
        lines.append(f"장기 잔차 Engle-Granger p={pfmt(r.coint.pvalue)}")
    res = r.shortrun.resid
    return AnOut("오차수정모형", " · ".join(items), (wf._label(res.index[0]), wf._label(res.index[-1])), tabs, [], lines,
                 [f"{method} — 장기 계수를 단기식의 EC(-1)에 숫자로 넣음"], {"alpha": float(al["계수"]), "half_life": r.half_life},
                 makes={"kind": "candidate", "equations": _eq_payload([r.shortrun])})


def _var(p, target, lags=1, trend="c", maxlags=8, irf=10):
    wf = p.workfile
    label, items = _items(p, target)
    v = quiet(wf.var, "an_var", items, lags=lags, trend=trend)
    tabs = [("VAR 계수", v.output().data), ("시차 고르기(정보기준)", quiet(v.lag_order, maxlags).data),
            ("Granger 인과", quiet(v.granger_table).data), ("안정성", quiet(v.stability).data)]
    ir = v.irf(irf)
    first = items[0]
    resp = ir.xs(first, axis=1, level="충격")
    resp.index.name = "기"
    lines = [f"VAR({lags}) · 변수 {len(items)} · 추세 {trend}"]
    g = tabs[2][1]
    if len(g):
        sig = [f"{i}" for i, r in g.iterrows() if "p값" in r and r["p값"] < 0.05]
        lines.append("Granger 5% 유의  " + (" · ".join(sig[:6]) if sig else "없음"))
    return AnOut("VAR", label, None, tabs, [(f"{first} 충격의 반응", resp, list(resp.columns))], lines,
                 [f"충격반응은 촐레스키(변수 순서대로) 1 표준편차 — {irf}기"], {"lags": lags},
                 makes={"kind": "candidate", "equations": _eq_payload(quiet(v.make_equations))})


def _vecm(p, target, lags_diff=1, rank=1, det="ci"):
    wf = p.workfile
    label, items = _items(p, target)
    v = quiet(wf.vecm, "an_vecm", items, lags_diff=lags_diff, rank=rank, deterministic=det)
    tabs = [("VECM", v.output().data), ("조정 계수 α", v.alpha), ("공적분 벡터 β", v.beta)]
    lines = [f"VECM · 순위 {rank} · 차분 시차 {lags_diff} · 결정항 {det}"]
    return AnOut("VECM", label, None, tabs, [], lines, [], {"rank": rank},
                 makes={"kind": "candidate", "equations": _eq_payload(quiet(v.make_equations))})


_CNUM = re.compile(r"(?i)\bc\(\s*(\d+)\s*\)")


def _renumber(exprs, shared: bool):
    """블록 파일의 c(n)은 식마다 따로다 — 시스템에 넣을 때 식마다 번호를 이어 붙여(c(1)·c(2) → c(4)·c(5)) 우연히 공유되지 않게.
    shared=True면 그대로(같은 번호 = 같은 계수 — 식 사이 제약)."""
    if shared:
        return list(exprs), []
    out, top, moved = [], 0, []
    for e in exprs:
        nums = [int(m[1]) for m in _CNUM.finditer(e)]
        if not nums:
            out.append(e)
            continue
        off = top
        out.append(_CNUM.sub(lambda m: f"c({int(m[1]) + off})", e) if off else e)
        if off:
            moved.append(e)
        top = off + max(nums)
    return out, moved


def _system(p, target, method="sur", inst=None, shared=False):
    wf = p.workfile
    if target not in p.config.blocks:
        raise ProjectError(f"시스템 추정의 대상은 블록입니다(있는 블록: {', '.join(p.blocks)})")
    eqs = [x for x in p.parts(target) if x.kind == "equation"]
    if len(eqs) < 2:
        raise ProjectError(f"블록 {target}의 추정식이 둘 이상이어야 합니다")
    if "an_sys" in wf._objects:                    # 같은 프로젝트 객체로 다시 부르면 지난 식이 남아 있다 — 새로
        quiet(wf.delete, "an_sys")
    s = wf.system("an_sys")
    exprs, moved = _renumber([x.expr for x in eqs], shared)
    s.append(*exprs)
    if inst:
        s.append("@inst " + " ".join(_tokens(inst.replace(",", " "))))
    fn = {"ols": s.ols, "sur": s.sur, "tsls": s.tsls, "3sls": s.three_sls, "fiml": s.fiml}[method]
    quiet(fn)
    nonlinear = s.nonlinear
    tabs = [(f"시스템 추정 {method.upper()}", s.output().data), ("식마다", s.equation_stats())]
    lines = [f"{method.upper()}{' · 비선형' if nonlinear else ''} · 식 {len(eqs)}: " + " · ".join(x.id for x in eqs)]
    implicit = [] if inst or method in ("ols", "sur", "fiml") else ["도구변수는 식의 @inst로"]
    if nonlinear:
        implicit.append("계수에 비선형인 식이 있어 비선형 추정(시작값은 식 끝의 @start, 없으면 0)")
    if moved:
        implicit.append("c(n)은 식마다 따로 — 시스템에서는 번호를 이어 붙였다(같은 계수로 묶으려면 --shared)")
    elif shared:
        implicit.append("--shared: 같은 c(n) 번호는 식 사이에 같은 계수(식 사이 제약)")
    return AnOut("시스템 추정", f"블록 {target}", None, tabs, [], lines, implicit,
                 {"method": method, "nonlinear": nonlinear}, makes={"kind": "candidate", "equations": _eq_payload(quiet(s.make_equations))},
                 inputs={"files": definition_hashes(p)})


# ---------------------------------------------------------------------------
# 기초 분석 · 인과 · 변환 · 확률적 모의 (D50)
# ---------------------------------------------------------------------------
_PPY = {"Q": 4, "M": 12, "A": 1}


def _window(wf, items) -> pd.DataFrame:
    """대상들의 값 — 지금 표본(smpl) 안에서, 열마다 하나(식이면 계산한 값)."""
    s0, e0 = wf._bounds()
    idx = wf.data.index[s0:e0 + 1]
    return pd.DataFrame({it: _ser(wf, it).iloc[s0:e0 + 1].to_numpy(dtype=float) for it in items}, index=idx)


def _span(wf, df) -> Optional[Tuple[str, str]]:
    d = df.dropna(how="all")
    return (wf._label(d.index[0]), wf._label(d.index[-1])) if len(d) else None


def _single(items, what: str) -> str:
    if len(items) != 1:
        raise ProjectError(f"{what}은(는) 시리즈 하나(또는 식 하나 — log(Y) 등) — 지금 {len(items)}개")
    return items[0]


def _gaps(s: pd.Series) -> int:
    fv, lv = s.first_valid_index(), s.last_valid_index()
    return int(s.loc[fv:lv].isna().sum()) if fv is not None else 0


def _freq(p) -> str:
    return getattr(p.workfile, "freq", None) or p.config.freq or "Q"


def _stats(p, target):
    from .. import stats as S
    wf = p.workfile
    label, items = _items(p, target)
    df = _window(wf, items)
    d = S.describe(df)
    lines = [f"{k:<10} 관측치 {int(r['관측치'])} · 평균 {short(r['평균'])} · 표준편차 {short(r['표준편차'])} · 왜도 {r['왜도']:.2f} · "
             f"첨도 {r['첨도']:.2f} · JB p={pfmt(r['JB p값'])}" for k, r in d.iterrows() if r["관측치"]]
    implicit = ["결측은 시리즈마다 뺐다", "왜도·첨도는 표본 모멘트(정규분포의 첨도는 3), Jarque-Bera는 정규성 검정"]
    return AnOut("기술 통계", label, _span(wf, df), [("기술 통계", d)], [], lines, implicit,
                 payload={"rows": {k: {c: (None if pd.isna(v) else float(v)) for c, v in r.items()} for k, r in d.iterrows()}})


def _hist(p, target, bins=None):
    from .. import stats as S
    wf = p.workfile
    label, items = _items(p, target)
    x = _single(items, "히스토그램")
    s = _window(wf, [x])[x].dropna()
    h = S.histogram(s.to_numpy(), bins)
    d = S.describe(s.to_frame(x)).iloc[0]
    tab = h.copy()
    chart = pd.DataFrame({"도수": h["도수"].to_numpy(), "정규 기대도수": h["정규 기대도수"].round(2).to_numpy()},
                         index=pd.Index([f"{short(a)}~{short(b)}" for a, b in zip(h["시작"], h["끝"])], name="구간"))
    lines = [f"구간 {len(h)} · 관측치 {int(d['관측치'])} · 평균 {short(d['평균'])} · 표준편차 {short(d['표준편차'])}",
             f"왜도 {d['왜도']:.2f} · 첨도 {d['첨도']:.2f} · Jarque-Bera p={pfmt(d['JB p값'])} → "
             + ("정규분포와 다르다(5%)" if d["JB p값"] < 0.05 else "정규분포와 다르다고 할 수 없다(5%)")]
    implicit = [f"구간 수 {'스터지스(⌈log₂ n⌉ + 1)' if not bins else '지정'} · 같은 폭",
                "정규 기대도수는 같은 평균·표준편차의 정규분포에서"]
    return AnOut("히스토그램", label, _span(wf, s.to_frame()), [("히스토그램", tab)],
                 [("도수", chart, ["도수"], {"kind": "bar", "y": "도수", "line": "정규 기대도수"})], lines, implicit,
                 payload={"bins": len(h), "jb_p": float(d["JB p값"])})


def _acf(p, target, lags=None):
    from .. import stats as S
    wf = p.workfile
    label, items = _items(p, target)
    x = _single(items, "자기상관")
    raw = _window(wf, [x])[x]
    s = raw.dropna()
    n = len(s)
    L = int(lags) if lags else max(1, min({"Q": 12, "M": 24, "A": 10}.get(_freq(p), 12), n // 4))
    cg = S.correlogram(s.to_numpy(), L)
    band = cg.attrs["band"]
    out = [int(k) for k, v in cg["자기상관"].items() if abs(v) > band]
    q, qp = float(cg["Q"].iloc[-1]), float(cg["p값"].iloc[-1])
    head = " · ".join(f"{v:+.2f}" for v in cg["자기상관"].iloc[:4])
    lines = [f"자기상관(시차 1~{min(4, L)})  {head}",
             f"Q({L}) {q:.2f} p={pfmt(qp)} → " + ("자기상관이 있다(5%)" if qp < 0.05 else "자기상관이 없다고 볼 수 있다(5%)"),
             f"95% 한계 ±{band:.3f}을 넘는 시차: " + (", ".join(map(str, out[:12])) if out else "없음")]
    implicit = [f"시차 {L}" + ("" if lags else "(주기에 맞춘 기본 — 관측치의 1/4을 넘지 않게)"),
                "편자기상관은 Yule-Walker(Durbin-Levinson)", "한계는 ±1.96/√n"]
    if _gaps(raw):
        implicit.append(f"표본 안의 결측 {_gaps(raw)}기는 빼고 이었다")
    charts = [("자기상관", cg[["자기상관"]], ["자기상관"], {"kind": "bar", "y": "자기상관", "band": band}),
              ("편자기상관", cg[["편자기상관"]], ["편자기상관"], {"kind": "bar", "y": "편자기상관", "band": band})]
    return AnOut("자기상관", label, _span(wf, s.to_frame()), [("자기상관 표", cg)], charts, lines, implicit,
                 payload={"lags": L, "q": q, "q_p": qp, "band": band})


def _corr(p, target, method="pearson"):
    from .. import stats as S
    wf = p.workfile
    label, items = _items(p, target)
    if len(items) < 2:
        raise ProjectError("상관은 시리즈 둘 이상(묶음 또는 'Y CN P')")
    df = _window(wf, items)
    c = S.correlation(df, method)
    common = df.dropna()
    pairs = c.pairs()
    long = pd.DataFrame([{"행": a, "열": b, "값": round(float(c.corr.loc[a, b]), 4)} for a in c.corr.index for b in c.corr.columns])
    long.index.name = "칸"
    charts = [("상관 행렬", long, ["값"], {"kind": "heat"})]
    if len(items) == 2:
        sc = _labelled(wf, common.copy())
        charts.append((f"{items[0]} · {items[1]}", sc, list(sc.columns), {"kind": "scatter", "x": items[0], "y": items[1]}))
    lines = [f"{r['변수1']} · {r['변수2']}  {r['상관']:+.2f} (p={pfmt(r['p값'])})" for _, r in pairs.head(5).iterrows()]
    implicit = [f"{'피어슨(값)' if method == 'pearson' else '스피어먼(순위)'} 상관 · 공통 표본 {c.nobs}기",
                "p값은 '상관이 0'의 t 검정" + (" — 추세가 있는 수준끼리는 상관이 크게 나오기 쉽다(차분·증가율로도 보라)" if _levels(items) else "")]
    if len(common) < len(df.dropna(how="all")):
        implicit.append("어느 시리즈든 결측인 기간은 뺐다")
    return AnOut("상관", label, _span(wf, common), [("상관 행렬", c.corr), ("p값", c.pvalues), ("공분산", c.cov), ("쌍마다", pairs)],
                 charts, lines, implicit, payload={"nobs": c.nobs, "method": method,
                                                   "pairs": [[r["변수1"], r["변수2"], float(r["상관"])] for _, r in pairs.head(20).iterrows()]})


def _xcorr(p, target, lags=None):
    from .. import stats as S
    wf = p.workfile
    label, items = _items(p, target)
    if len(items) != 2:
        raise ProjectError(f"교차상관은 시리즈 둘('X Y') — 지금 {len(items)}개")
    a, b = items
    df = _window(wf, items).dropna()
    n = len(df)
    L = int(lags) if lags else max(1, min(2 * _PPY.get(_freq(p), 4) + 4, n // 4))
    cc = S.ccf(df[a].to_numpy(), df[b].to_numpy(), L)
    band = cc.attrs["band"]
    k = int(cc["상관"].abs().idxmax())
    v = float(cc.loc[k, "상관"])
    lead = (f"{b}가 {k}기 앞선다" if k > 0 else f"{a}가 {-k}기 앞선다" if k < 0 else "같은 기에 가장 크다")
    lines = [f"가장 큰 교차상관  시차 {k:+d} → {v:+.2f} ({lead})", f"시차 0  {float(cc.loc[0, '상관']):+.2f} · 95% 한계 ±{band:.3f}"]
    implicit = [f"시차 k마다 corr({a}_t, {b}_(t−k)) — k > 0이면 {b}의 과거와 {a}의 지금", f"시차 ±{L}" + ("" if lags else "(기본)"),
                f"공통 표본 {n}기"]
    return AnOut("교차상관", label, _span(wf, df), [("교차상관", cc)],
                 [("교차상관", cc, ["상관"], {"kind": "bar", "y": "상관", "band": band})], lines, implicit,
                 payload={"best_lag": k, "best": v, "band": band})


def _levels(items) -> bool:
    """대상이 모두 이름 그대로(수준)인가 — log(Y)·dlog(Y)·d(Y)처럼 식이면 False."""
    return all(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", str(x)) for x in items)


def _granger(p, target, lags=None):
    from .. import stats as S
    wf = p.workfile
    label, items = _items(p, target)
    if len(items) < 2:
        raise ProjectError("Granger 인과는 시리즈 둘 이상(묶음 또는 'Y CN P')")
    df = _window(wf, items)
    L = int(lags) if lags else max(2, _PPY.get(_freq(p), 4))
    g = S.granger_table(df, L)
    mat = g.pivot(index="원인", columns="결과", values="p값").reindex(index=items, columns=items)
    mat.index.name = "원인 \\ 결과"
    sig = g[g["인과(5%)"]]
    lines = ([f"{r['원인']} → {r['결과']}  F {r['F']:.2f} p={pfmt(r['p값'])}" for _, r in sig.iterrows()][:8]
             or ["5%에서 Granger 인과인 쌍이 없다"])
    implicit = [f"시차 {L}" + ("" if lags else "(주기에 맞춘 기본 — 분기 4 · 월 12 · 연 2)"),
                "쌍마다 두 시리즈가 모두 있는 기간 — 상수 + 각자의 시차", "귀무가설: 원인의 시차 계수가 모두 0"]
    if _levels(items):
        implicit.append("수준 그대로 검정했다 — 단위근이 있는 시리즈는 차분·증가율로 다시 보는 것이 맞다")
    return AnOut("Granger 인과", label, _span(wf, df.dropna()), [("Granger 인과", g), ("p값(행 원인 → 열 결과)", mat)], [], lines, implicit,
                 payload={"lags": L, "pairs": [[r["원인"], r["결과"], float(r["p값"])] for _, r in g.iterrows()]})


def _fevd(p, target, lags=1, periods=10, trend="c"):
    wf = p.workfile
    label, items = _items(p, target)
    if len(items) < 2:
        raise ProjectError("분산분해는 시리즈 둘 이상(VAR — 묶음 또는 'dlog(Y) R')")
    v = quiet(wf.var, "an_fevd", items, lags=int(lags), trend=trend)
    d = v.fevd(int(periods))
    tabs = [(f"{s}의 예측오차 분산분해(%)", (d[s] * 100).round(2)) for s in items]
    first = (d[items[0]] * 100).round(2)
    lines = [f"{s} — {periods}기: " + " · ".join(f"{k} {val:.0f}%" for k, val in (d[s].iloc[-1] * 100).items()) for s in items[:6]]
    implicit = [f"VAR({lags}) · 결정항 {trend}", "촐레스키(변수 순서대로) — 순서를 바꾸면 결과가 달라진다"]
    return AnOut("분산분해", label, None, tabs, [(f"{items[0]}의 분산분해(%)", first, list(first.columns))], lines, implicit,
                 payload={"lags": lags, "periods": periods})


def _convert(p, target, to="A", how="mean"):
    from ..data import transform
    from ..data.periods import format_period, to_period
    wf = p.workfile
    label, items = _items(p, target)
    F = _freq(p)
    if to == F:
        raise ProjectError(f"자료가 이미 {to} 주기입니다 — 더 낮은 주기로(분기 → 연, 월 → 분기·연)")
    try:
        transform.ratio(F, to)
    except ValueError as e:
        raise ProjectError(f"{F} → {to}: {e}") from None
    df = _window(wf, items)
    cols = {}
    for it in items:
        cols[it] = transform.aggregate(pd.Series(df[it].to_numpy(), index=df.index, name=it), F, to, how)
    out = pd.DataFrame(cols)
    out.index = pd.Index([format_period(to_period(t, to), to) for t in out.index], name="period")
    out = out.dropna(how="all")
    name = {"A": "연", "Q": "분기", "M": "월"}
    lines = [f"{name.get(F, F)} → {name.get(to, to)} · {how} · {len(out)}기"] + \
            [f"{it:<10} 끝 {out[it].last_valid_index()} {short(out[it].dropna().iloc[-1])}" for it in items[:6] if out[it].notna().any()]
    implicit = ["하위 기간이 하나라도 비면 그 기간은 결측", "보기만 — 시리즈로 쓰려면 자료 정의의 convert로"]
    return AnOut("주기 변환", label, (out.index[0], out.index[-1]) if len(out) else None, [("주기 변환", out)],
                 [("주기 변환", out, list(out.columns)[:6])], lines, implicit, payload={"to": to, "how": how})


def _stochastic(p, target, var=None, reps=100, range=None, seed=1):
    m = p.model(target)
    s, e = p.span(range) if range else p._range(None, None)
    r = quiet(m.stochastic, s, e, reps=int(reps), seed=None if seed in (None, "") else int(seed))
    wf = p.workfile
    names = [var] if var else list(r.mean.columns)[:4]
    tabs, charts, lines = [], [], []
    for v in names:
        b = r.band(v)
        if isinstance(b.index, pd.DatetimeIndex):
            b = _labelled(wf, b)
        b.index.name = "period"
        tabs.append((f"{v} — 평균·표준편차·분위수", b))
        last = b.iloc[-1]
        lines.append(f"{v:<6} 끝 기 평균 {short(last['mean'])} · 90% 띠 {short(last['p5'])}~{short(last['p95'])}")
        if not charts:
            charts.append((f"{v} — 평균과 90% 띠", b[["mean", "p5", "p95"]], ["mean", "p5", "p95"]))
    implicit = [f"추정 잔차를 기간마다 다시 뽑아(식 사이 상관 보존) {reps}번 풀었다", f"씨앗 {seed}" if seed not in (None, "") else "씨앗 없음(매번 다르다)"]
    return AnOut("확률적 모의", f"모형 {target}", (s, e), tabs, charts, lines, implicit, payload={"reps": reps},
                 inputs={"files": definition_hashes(p)})


# ---------------------------------------------------------------------------
# 등록
# ---------------------------------------------------------------------------
_SMPL_HELP = "표본(상대 기간 가능 — 1990Q1:last)"

register(Analysis("summary", "요약", "자료 살펴보기", ("series", "group", "expr"), [], None,
                  "구간·결측·끝 값·단위·값의 종류 표, 수준 차트", "시리즈마다 처음·끝·값 수·안쪽 결측·마지막 값·단위·설명",
                  "equion an summary core", _summary))
register(Analysis("unitroot", "단위근", "단위근·공적분", ("series", "group", "expr"),
                  [Opt("trend", "choice", "c", ("n", "c", "ct"), "결정항 — n 없음 · c 상수 · ct 상수+추세"),
                   Opt("lags", "int", None, help="ADF 시차 수(없으면 정보기준으로)"),
                   Opt("ic", "choice", "bic", ("bic", "aic"), "시차를 고르는 정보기준"),
                   Opt("maxlag", "int", None, help="고를 때의 최대 시차")], None,
                  "시리즈 × ADF·KPSS·판단 표", "ADF(귀무: 단위근)와 KPSS(귀무: 정상)를 함께 — 둘이 다르면 '엇갈림'",
                  "equion an unitroot core --trend ct", _unitroot))
register(Analysis("coint", "공적분", "단위근·공적분", ("group", "expr"),
                  [Opt("method", "choice", "johansen", ("johansen", "engle"), "Johansen 순위 또는 Engle-Granger"),
                   Opt("trend", "choice", "c", ("n", "c", "ct"), "Engle-Granger의 결정항"),
                   Opt("lags", "int", 1, help="차분 시차 수"),
                   Opt("det", "int", 0, help="Johansen 결정항 −1 없음 · 0 상수 · 1 상수+추세")], None,
                  "순위 검정 표", "묶음 또는 'Y X1 X2'(첫 시리즈가 Engle-Granger의 y)", "equion an coint core --lags 2", _coint, count="many"))
register(Analysis("diag", "식 진단", "식", ("part", "est"),
                  [Opt("lags", "int", 2, help="계열상관 LM 시차"),
                   Opt("chow", "str", None, help="Chow 검정 시점(쉼표로 여럿 — 2008Q3,2015Q1)", metavar="기간"),
                   Opt("cusum", "bool", True, help="CUSUM 그림(OLS)")], None,
                  "진단 검정 표·Chow·CUSUM 차트", "부품(블록 파일의 그 줄) 또는 est: 기록 — 지금 자료로 추정해 진단",
                  "equion an diag price:P --chow 2008Q3", _diag))
register(Analysis("fcsteval", "예측 평가", "예측", ("records",),
                  [Opt("var", "str", None, help="견줄 변수(필수)", metavar="변수")], None,
                  "RMSE·MAE·Theil U·MSE 분해, Diebold-Mariano", "hs·sim·est(--sim) 기록의 풀린 값을 실측과 견준다",
                  "equion an fcsteval \"hs:hs_0001 hs:hs_0002\" --var Y", _fcsteval))
register(Analysis("split", "요인 나누기", "예측", ("records",),
                  [Opt("vars", "str", None, help="볼 변수(쉼표로 — 없으면 핵심 변수 넷)", metavar="변수들")], None,
                  "변수·연도마다 앞·뒤·바뀜과 자료·가정·식의 몫 표, 단계마다 다시 푼 값, 막대 차트",
                  "두 전망 기록(sim:)의 연간 성장률 바뀜을 자료 → 가정 → 식 차례로 하나씩 바꿔 다시 풀어 나눈다",
                  "equion an split \"sim:2026-10_base sim:2026-11_base\"", _split, count="two"))
register(Analysis("stability", "동태 안정성", "모형", ("model",),
                  [Opt("period", "str", None, help="선형화 시점(기본: 자료 끝)", metavar="기간")], None,
                  "고윳값 표·판정", "선형화 동반행렬의 고윳값 — 안정·단위근·불안정", "equion an stability main", _stability))
register(Analysis("multipliers", "충격 승수", "모형", ("model",),
                  [Opt("var", "str", None, help="충격 줄 외생변수(필수)", metavar="변수"),
                   Opt("shock", "float", 1.0, help="충격 크기"),
                   Opt("kind", "choice", "level", ("level", "pct"), "level 더하기 · pct %"),
                   Opt("range", "str", None, help="구간(기본 [hs] range)", metavar="S:E")], None,
                  "기간별 반응 표·차트", "외생 하나를 바꿨을 때 내생변수의 반응(충격 − 기준선)",
                  "equion an multipliers main --var G --shock 1", _multipliers))
register(Analysis("seas", "계절조정", "만드는 분석", ("series",),
                  [Opt("method", "choice", "stl", ("stl", "classical"), "STL 또는 고전 분해"),
                   Opt("model", "choice", "additive", ("additive", "multiplicative"), "가법·승법"),
                   Opt("robust", "bool", False, help="STL 강건(이상값에 덜 끌린다)")], "definition",
                  "실측·계절·추세·불규칙·조정 표와 차트", "미리보기 — an keep이 series.toml에 계절조정 시리즈 정의를 남긴다",
                  "equion an seas CN --model multiplicative", _seas, count="one"))
register(Analysis("genr", "파생", "만드는 분석", ("assign",), [], "derived",
                  "값 표·차트", "'이름 = 식' 미리보기 — an keep이 derived.txt에 한 줄로 남긴다",
                  "equion an genr \"RR2 = R - 100*dlog(P,4)\"", _genr))
register(Analysis("ecm", "오차수정모형", "부품을 내는 분석", ("expr",),
                  [Opt("method", "choice", "two-step", ("two-step", "nls"), "Engle-Granger 두 단계 또는 NLS 한 번에"),
                   Opt("lags", "int", 0, help="단기식에 넣을 차분 시차 수")], "candidate",
                  "장기식·조정 속도·반감기·단기식", "'Y X1 X2'(보통 로그 수준) — an keep이 단기식을 식 후보로",
                  "equion an ecm \"log(CN) log(Y)\"", _ecm, count="many"))
register(Analysis("var", "VAR", "부품을 내는 분석", ("group", "expr"),
                  [Opt("lags", "int", 1, help="시차 수"), Opt("trend", "choice", "c", ("n", "c", "ct"), "결정항"),
                   Opt("maxlags", "int", 8, help="시차 고르기 표의 최대 시차"),
                   Opt("irf", "int", 10, help="충격반응 기간")], "candidate",
                  "계수·시차 고르기·Granger·안정성 표, 충격반응 차트", "an keep이 식마다 식 후보로",
                  "equion an var \"dlog(Y) R\" --lags 2", _var, count="many"))
register(Analysis("vecm", "VECM", "부품을 내는 분석", ("group", "expr"),
                  [Opt("lags_diff", "int", 1, help="차분 시차 수"), Opt("rank", "int", 1, help="공적분 순위"),
                   Opt("det", "choice", "ci", ("n", "ci", "co", "li", "lo"), "결정항")], "candidate",
                  "α·β·Γ 표", "an keep이 식마다 식 후보로", "equion an vecm \"RL R\" --rank 1", _vecm, count="many"))
register(Analysis("system", "시스템 추정", "부품을 내는 분석", ("block",),
                  [Opt("method", "choice", "sur", ("ols", "sur", "tsls", "3sls", "fiml"), "추정법"),
                   Opt("inst", "str", None, help="모든 식의 도구변수(쉼표·공백)", metavar="변수들"),
                   Opt("shared", "bool", False, help="같은 c(n) 번호를 식 사이에 같은 계수로(식 사이 제약 — 기본은 식마다 따로)")], "candidate",
                  "계수·식마다 통계 표", "블록의 추정식을 한 번에(계수에 비선형인 식도 — D64) — an keep이 식마다 식 후보로",
                  "equion an system demand --method sur", _system))

register(Analysis("stats", "기술 통계", "기초 통계", ("series", "group", "expr"), [], None,
                  "시리즈마다 관측치·평균·표준편차·사분위·왜도·첨도·Jarque-Bera 표", "결측은 시리즈마다 뺀다 — 묶음이면 시리즈마다 한 줄",
                  "equion an stats core", _stats, count="any"))
register(Analysis("hist", "히스토그램", "기초 통계", ("series", "expr"),
                  [Opt("bins", "int", None, help="구간 수(없으면 스터지스)")], None,
                  "구간별 도수·비율·정규 기대도수 표, 막대 차트", "시리즈 하나 — 같은 평균·표준편차의 정규분포와 견준다",
                  "equion an hist \"dlog(Y)\"", _hist, count="one"))
register(Analysis("acf", "자기상관", "기초 통계", ("series", "expr"),
                  [Opt("lags", "int", None, help="시차 수(없으면 주기에 맞춰 — 분기 12 · 월 24 · 연 10)")], None,
                  "시차별 자기상관·편자기상관·Q·p값 표, 막대 차트(95% 한계)", "시리즈 하나 — 차분·증가율로도 본다(dlog(Y))",
                  "equion an acf \"dlog(Y)\" --lags 12", _acf, count="one"))
register(Analysis("corr", "상관", "기초 통계", ("group", "expr"),
                  [Opt("method", "choice", "pearson", ("pearson", "spearman"), "pearson 값 · spearman 순위")], None,
                  "상관 행렬·p값·공분산·쌍마다 표, 색 격자(둘이면 산점도)", "묶음 또는 'Y CN P' — 공통 표본에서",
                  "equion an corr core", _corr, count="many"))
register(Analysis("xcorr", "교차상관", "기초 통계", ("expr",),
                  [Opt("lags", "int", None, help="시차 ±L(없으면 주기에 맞춰)")], None,
                  "시차별 교차상관 표, 막대 차트(95% 한계)", "'X Y' 둘 — k > 0이면 Y의 과거와 X의 지금",
                  "equion an xcorr \"dlog(CN) dlog(Y)\"", _xcorr, count="two"))
register(Analysis("granger", "Granger 인과", "인과·동학", ("group", "expr"),
                  [Opt("lags", "int", None, help="시차 수(없으면 분기 4 · 월 12 · 연 2)")], None,
                  "원인 → 결과마다 F·p값 표, p값 행렬", "묶음 또는 'Y CN P' — 쌍마다 두 시리즈의 공통 표본, 상수 + 각자의 시차",
                  "equion an granger \"dlog(Y) dlog(CN)\" --lags 4", _granger, count="many"))
register(Analysis("fevd", "분산분해", "인과·동학", ("group", "expr"),
                  [Opt("lags", "int", 1, help="VAR 시차 수"), Opt("periods", "int", 10, help="기간"),
                   Opt("trend", "choice", "c", ("n", "c", "ct"), "결정항")], None,
                  "반응 변수마다 기간별 분산분해(%) 표·차트", "VAR의 예측오차 분산분해 — 촐레스키(변수 순서대로)",
                  "equion an fevd \"dlog(Y) R\" --lags 2", _fevd, count="many"))
register(Analysis("convert", "주기 변환", "자료 살펴보기", ("series", "group", "expr"),
                  [Opt("to", "choice", "A", ("A", "Q"), "낮은 주기 — A 연 · Q 분기"),
                   Opt("how", "choice", "mean", ("mean", "sum", "first", "last", "max", "min"), "모으는 방법")], None,
                  "변환한 값 표·차트", "보기만 — 시리즈로 쓰려면 자료 정의(series.toml)의 convert로",
                  "equion an convert core --to A --how sum", _convert, count="any"))
register(Analysis("stochastic", "확률적 모의", "모형", ("model",),
                  [Opt("var", "str", None, help="볼 변수(없으면 내생 앞의 넷)", metavar="변수"),
                   Opt("reps", "int", 100, help="풀이 횟수"), Opt("range", "str", None, help="구간(기본 [hs] range)", metavar="S:E"),
                   Opt("seed", "int", 1, help="씨앗(같은 결과를 다시)")], None,
                  "변수마다 평균·표준편차·5·50·95% 표, 평균과 90% 띠 차트", "추정 잔차를 기간마다 다시 뽑아(식 사이 상관 보존) 여러 번 푼다",
                  "equion an stochastic main --var Y --reps 200", _stochastic))


# ---------------------------------------------------------------------------
# 남기기 — 정의로 · 후보로
# ---------------------------------------------------------------------------
@dataclass
class KeepResult:
    """`an keep` 결과 — 무엇을 어디에 남겼나(`.kind` definition·derived·candidate · `.what` · `.records` · `.change`)."""

    record: str
    kind: str
    what: List[str]
    records: List[str]
    change: Optional[str]

    def text(self) -> str:
        """명령줄에 보이는 짧은 글."""
        L = [f"[an keep] {self.record} → {reg.MAKES_KO[self.kind]}"]
        L += [f"  {w}" for w in self.what]
        if self.change:
            L.append(f"  바뀜 기록  {self.change}")
        if self.kind in ("definition", "derived"):
            L.append("  다음   equion data build → equion data use <회차>")
        else:
            L.append("  다음   equion compare --part … · equion hs --swap 부품=est:… · equion adopt est:…")
        return "\n".join(L)

    def to_dict(self) -> dict:
        """명령줄 --json과 같은 사전."""
        return {"record": self.record, "kind": self.kind, "what": self.what, "records": self.records, "change": self.change}


def keep(p, rid: str, as_name: str = None, replace: bool = False, who: str = None, command: str = None) -> KeepResult:
    """분석 기록을 남긴다 — 만드는 분석은 정의(series.toml·derived.txt, made_by = 기록)로, 부품을 내는 분석은 식 후보(est:)로."""
    import tomlkit
    from ..workfile.objects import EquationObject
    from .notes import read_text
    store = store_of(p)
    rec = store.get(rid, "an")
    mk = rec.meta.get("makes")
    if not mk:
        raise ProjectError(f"{rid}({rec.meta['label']})는 보는 분석이라 남길 것이 없습니다")
    cmd = command or f"an keep {rid}"
    if mk["kind"] == "definition":
        p._need_defs()
        x = mk["series"]
        sf = p.config.series_file
        path = os.path.join(p.root, sf)
        with open(path, encoding="utf-8") as f:
            doc = tomlkit.parse(f.read())
        series = doc.get("series") or {}
        if x not in series:
            raise ProjectError(f"{x}는 {sf}의 [series.{x}]가 아닙니다(파생식이면 derived.txt에서) — 정의로 남길 수 없습니다")
        seas = tomlkit.inline_table()
        seas.update(mk["seas"])
        if replace:
            new_name = x
            series[x]["seas"] = seas
            series[x]["made_by"] = rid
        else:
            new_name = as_name or f"{x}SA"
            if not NAME_RE.match(new_name):
                raise ProjectError(f"시리즈 이름 {new_name!r} — 영문으로 시작하고 영문·숫자·_만")
            if new_name in series or p.workfile._col(new_name):
                raise ProjectError(f"이미 있는 시리즈 {new_name} — --as로 다른 이름, 또는 --replace로 {x}를 바꾸기")
            t = tomlkit.table()
            for k in ("from", "convert", "denton", "scale", "fill", "unit"):
                if k in series[x]:
                    t[k] = series[x][k]
            t["seas"] = seas
            t["desc"] = f"{series[x].get('desc', x)} — 계절조정({mk['seas']['method']} {mk['seas']['model']})"
            t["made_by"] = rid
            series[new_name] = t
        ch = history_of(p).write_files({sf: tomlkit.dumps(doc)}, _who(who), cmd, note=f"[series.{new_name}] ← {rid}")
        return KeepResult(rid, "definition", [f"{sf} [series.{new_name}] seas = {mk['seas']} · made_by = {rid}"], [],
                          ch.id if ch else None)
    if mk["kind"] == "derived":
        p._need_defs()
        dfile = p.config.derived_file
        if not dfile:
            raise ProjectError("파생식 파일이 없습니다 — equion.toml [data] derived = \"DATA/derived.txt\"")
        name = as_name or mk["name"]
        path = os.path.join(p.root, dfile)
        cur = read_text(path) if os.path.isfile(path) else ""
        if re.search(rf"^\s*{re.escape(name)}\s*=", cur, re.M | re.I):
            raise ProjectError(f"{dfile}에 이미 {name}이 있습니다 — --as로 다른 이름")
        line = f"{name} = {mk['expr']}   # {rid}"
        new = cur + ("" if cur.endswith("\n") or not cur else "\n") + line + "\n"
        ch = history_of(p).write_files({dfile: new}, _who(who), cmd, note=f"{name} ← {rid}")
        return KeepResult(rid, "derived", [f"{dfile}: {line}"], [], ch.id if ch else None)
    # candidate
    wf = p.workfile
    made = []
    for k, e in enumerate(mk["equations"], 1):
        sv = e["saved"]
        obj = EquationObject(wf, f"keep_{k}")
        if sv.get("method") == "fixed":       # VAR·VECM·시스템 — 그 계수 그대로
            coefs = (sv.get("regression_results") or {}).get("coefficients") or {}
            eq = obj._make(e["text"], method="fixed", coefficients=coefs)
        else:                                 # ECM 단기식 — 같은 자료로 같은 추정
            eq = obj._make(e["text"], method="tsls" if sv.get("method") == "tsls" else None)
        obj._adopt(eq, e["text"], loud=False)
        nm = (as_name if len(mk["equations"]) == 1 else f"{as_name}_{k}") if as_name else None
        r = record_equation(p, obj, as_name=nm, notes=[f"{rid}({rec.meta['label']})가 낸 식 — 계수 그대로"], who=who,
                            command=cmd)
        made.append(r.id)
    return KeepResult(rid, "candidate", [f"{x}" for x in made], made, None)
