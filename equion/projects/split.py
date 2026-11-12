"""전망 회차 비교의 요인 나누기 (D59) — `equion an split "sim:앞 sim:뒤"`.

두 전망 기록 사이의 바뀜을 **자료 → 가정 → 식** 차례로 하나씩 바꿔 다시 풀어 나눈다.

    S0 = 앞의 식 · 앞의 자료 · 앞의 가정        (앞 기록을 다시 푼 것)
    S1 = 앞의 식 · 뒤의 자료 · 앞의 가정        자료의 몫 = S1 − S0
    S2 = 앞의 식 · 뒤의 자료 · 뒤의 가정        가정의 몫 = S2 − S1
    S3 = 뒤의 식 · 뒤의 자료 · 뒤의 가정        식의 몫   = S3 − S2   (뒤 기록을 다시 푼 것)

- 식은 기록의 조립 명세(assembly.json — 식 글자·계수), 자료는 기록의 자료 회차(내용 해시가 같아야 한다), 가정은 기록에 적힌 외생 경로(levels.csv —
  가정·채움·시나리오 충격이 든 그 값)와 보정항 경로(addfactors.csv)다. 지금 파일과 무관하게 기록만으로 푼다.
- 전망 구간과 풀이 방식은 자료를 준 기록의 것(자료가 늘면 구간도 늦어진다). 가정 경로가 그 구간을 다 덮지 못하면 외생은 마지막 값으로, 보정항은 마지막 값을 이어 붙인다.
- 몫은 차례에 따라 달라질 수 있다(경로 의존) — 차례는 늘 자료 → 가정 → 식이고 카드에 적는다. S0·S3이 기록과 다르면 그 차이를 '나머지'로 따로 보인다.
- 나누는 것은 연간 성장률(%)이다 — 두 기록이 모두 푼 해만.
"""
from __future__ import annotations

from typing import List, Tuple

import numpy as np
import pandas as pd

from ..data.periods import PERIODS_PER_YEAR
from ..workfile.runtime import quiet
from .config import ProjectError
from .records import data_label, replay_model, replay_workfile, store_of

STEPS = ("자료", "가정", "식")


def _solve(p, eqs, data, assume, tag: str):
    """식(eqs 기록) · 자료(data 기록) · 가정(assume 기록)으로 전망을 다시 푼다 → (수준 표(라벨), 연간 표, 알아서 한 것)."""
    from .sim import _annual, _before, _between, _when
    asm = eqs.read_json("assembly.json")
    ds = data.meta["data"]
    wf = replay_workfile(p, ds, tag)
    m = replay_model(wf, asm, tag)
    s, e = data.meta["range"]
    mode = data.meta.get("mode") or "dynamic"
    F = wf.freq
    ppy = PERIODS_PER_YEAR[F]
    quiet(wf.extend, e)
    i0, i1 = wf._bounds(s, e)
    labels = [wf._label(t) for t in wf.data.index]
    rng = labels[i0:i1 + 1]
    notes: List[str] = []
    lv = assume.read_csv("levels.csv")
    try:
        fg = assume.read_csv("flags.csv")
    except (OSError, ValueError):
        fg = None
    sd = assume.meta.get("scenario_def") or {}
    sa, ea = assume.meta["range"]
    exo = [v for v in m.exogenous if v in wf.data.columns and v not in set(wf._data.indicators)]
    shocked = {}                                      # 시나리오가 외생 경로에 준 충격의 기간(가정이다 — 실측 칸이어도)
    for sh in sd.get("shocks") or []:
        if sh.get("var") in exo and sh.get("kind") != "add_factor":
            shocked.setdefault(sh["var"], []).append((_when(sh["from"], sa, ea, F), _when(sh["to"], sa, ea, F, end=True)))
    held = []
    for v in exo:
        vals = wf._data.data[v].to_numpy(dtype=float).copy()
        src = lv[v] if v in lv.columns else None
        kind = fg[v] if fg is not None and v in fg.columns else None
        for j, lab in enumerate(rng, start=i0):
            if src is None or lab not in src.index or not np.isfinite(src.loc[lab]):
                continue
            # 가정 · 채움 칸과 시나리오 충격 칸만 기록의 값으로 — 실측 칸(전망 구간 안의 외생 실측)은 자료를 준 기록의 값(그 개정은 '자료'의 몫)
            if (kind is None or str(kind.get(lab, "")) in ("가정", "채움")
                    or any(_between(lab, a_, b_, F) for a_, b_ in shocked.get(v, []))):
                vals[j] = float(src.loc[lab])
        wf._data.data[v] = vals
        seg = vals[i0:i1 + 1]
        if not np.isfinite(seg).all():
            quiet(wf._data.fill_series, [v], method="last")
            held.append(v)
    if held:
        notes.append(f"{tag}: 가정 경로가 구간을 다 덮지 못해 마지막 값으로 — {', '.join(held[:6])}")
    afp = assume.read_csv("addfactors.csv")
    sc0 = m.scenario("baseline")
    for x in asm["parts"]:
        if x["kind"] != "equation":
            continue
        target = x["id"].split(":", 1)[1]
        if x["id"] not in afp.columns:
            continue
        col = afp[x["id"]].dropna()
        if not len(col):
            continue
        last = float(col.iloc[-1])
        path = np.array([float(col.loc[lab]) if lab in col.index else last for lab in rng])
        for ad in sd.get("addfactor") or []:            # 시나리오의 식 보정 — 기록의 보정항 경로에는 들지 않는다
            if str(ad.get("eq", "")).lower() == x["id"].lower():
                a_, b_ = _when(ad["from"], sa, ea, F), _when(ad["to"], sa, ea, F, end=True)
                for k, lab in enumerate(rng):
                    if _between(lab, a_, b_, F):
                        path[k] += float(ad["value"])
        if np.any(path != 0):
            sc0.add_factor(target, pd.Series(path, index=wf.data.index[i0:i1 + 1]))
    endo_set = set(m.endogenous)
    for sh in sd.get("shocks") or []:                  # 내생변수의 충격 · 보정항 꼴 충격 — 풀 때 다시 준다(엔진은 보정항으로 푼다)
        if sh.get("var") in endo_set or (sh.get("kind") == "add_factor" and sh.get("var") not in exo):
            a_, b_ = _when(sh["from"], sa, ea, F), _when(sh["to"], sa, ea, F, end=True)
            lo = s if _before(a_, s, F) else a_                     # 풀 구간과 겹치는 데만
            hi = b_ if _before(b_, e, F) else e
            if not _before(hi, lo, F):
                sc0.shock(sh["var"], sh["value"], lo, hi, kind=sh["kind"])
    try:
        res = quiet(m.forecast, s, e, mode=mode, scenario="baseline")
    except ValueError as ex:
        raise ProjectError(f"{tag}: 전망을 풀 수 없습니다 — {ex}") from None
    endo = [v for v in res.values.columns]
    full = pd.DataFrame(index=wf.data.index)
    for v in endo:
        col = wf.data[v].to_numpy(dtype=float).copy() if v in wf.data.columns else np.full(len(wf.data), np.nan)
        col[i0:i1 + 1] = res.values[v].to_numpy(dtype=float)
        full[v] = col
    full.index = pd.Index(labels, name="period")
    years = sorted({lab[:4] for lab in rng})
    ann = _annual(full[endo].iloc[:i1 + 1], ppy, years)
    return full.iloc[max(0, i0 - 2 * ppy):i1 + 1], ann, notes


def _growth(ann: pd.DataFrame, var: str, year: str):
    col = f"{var}_증가율"
    if col not in ann.columns or year not in ann.index:
        return None
    v = ann.loc[year, col]
    return float(v) if np.isfinite(v) else None


def split(p, target: str, vars: str = None) -> Tuple[dict, list, list, list, list, tuple]:
    """요인 나누기 계산 — (payload, 표들, 차트들, 줄들, 알아서 한 것, (앞 기록, 뒤 기록)). analyses.py의 'split'이 부른다."""
    from .analyses import _tokens
    ids = _tokens(target)
    if len(ids) != 2:
        raise ProjectError(f"요인 나누기는 전망 기록 둘('sim:앞 sim:뒤') — 지금 {len(ids)}개")
    store = store_of(p)
    recs = [store.get(r) for r in ids]
    for r in recs:
        if r.kind != "sim":
            raise ProjectError(f"{r.id}: 요인 나누기는 전망 기록(sim:)끼리")
    order = {d.get("id"): k for k, d in enumerate(store.log())}      # 같은 초에 만든 기록은 기록장의 차례로
    old, new = sorted(recs, key=lambda r: (str(r.meta.get("created") or ""), order.get(r.id, 0)))
    if old.meta.get("scenario") != new.meta.get("scenario"):
        implicit_sc = [f"시나리오가 다릅니다({old.meta.get('scenario')} → {new.meta.get('scenario')}) — 그 차이는 '가정'의 몫에 든다"]
    else:
        implicit_sc = []
    try:
        _, a0, n0 = _solve(p, old, old, old, "S0")
        _, a1, n1 = _solve(p, old, new, old, "S1")
        _, a2, n2 = _solve(p, old, new, new, "S2")
        _, a3, n3 = _solve(p, new, new, new, "S3")
        ra = old.read_csv("annual.csv")
        rb = new.read_csv("annual.csv")
    except (FileNotFoundError, KeyError) as ex:
        raise ProjectError(f"요인 나누기: 기록의 파일이 없습니다 — {ex} (기록이 손상되었거나 옛 판의 기록)") from None
    endo = list(new.meta.get("endogenous") or [])
    by_low = {v.lower(): v for v in endo}
    want = [by_low.get(v.strip().lower(), v.strip()) for v in str(vars).replace(",", " ").split()] if vars else endo[:4]
    unknown = [v for v in want if v not in endo]
    if unknown:
        raise ProjectError(f"{new.id}의 내생변수가 아닙니다: {', '.join(unknown)} (있는 것: {', '.join(endo[:12])})")
    years = [y for y in rb.index if y in ra.index]
    rows, steps = [], []
    worst = 0.0
    for v in want:
        for y in years:
            g = [_growth(t, v, y) for t in (ra, rb, a0, a1, a2, a3)]
            if any(x is None for x in g):
                continue
            ga, gb, s0, s1, s2, s3 = g
            rest = (gb - ga) - (s3 - s0)
            worst = max(worst, abs(s0 - ga), abs(s3 - gb))
            rows.append({"변수": v, "연도": y, "앞": round(ga, 3), "뒤": round(gb, 3), "바뀜": round(gb - ga, 3),
                         "자료": round(s1 - s0, 3), "가정": round(s2 - s1, 3), "식": round(s3 - s2, 3), "나머지": round(rest, 3)})
            steps.append({"변수": v, "연도": y, "S0 앞을 다시": round(s0, 3), "S1 자료만 뒤로": round(s1, 3), "S2 가정까지": round(s2, 3),
                          "S3 식까지(뒤를 다시)": round(s3, 3)})
    if not rows:
        raise ProjectError(f"두 기록이 함께 푼 해가 없습니다({', '.join(ra.index)} · {', '.join(rb.index)}) — 견줄 수 없습니다")
    tab = pd.DataFrame(rows)
    tab.index = pd.Index([f"{r['변수']} {r['연도']}" for r in rows], name="변수 · 연도")
    tab = tab.drop(columns=["변수", "연도"])
    stp = pd.DataFrame(steps)
    stp.index = pd.Index([f"{r['변수']} {r['연도']}" for r in steps], name="변수 · 연도")
    stp = stp.drop(columns=["변수", "연도"])
    show_rest = bool(np.any(np.abs(tab["나머지"].to_numpy(dtype=float)) >= 0.005))
    if not show_rest:
        tab = tab.drop(columns=["나머지"])
    v0, y0 = rows[0]["변수"], rows[0]["연도"]
    first = rows[0]
    bars = pd.DataFrame({"%p": [first[k] for k in STEPS] + ([first["나머지"]] if show_rest else [])},
                        index=pd.Index(list(STEPS) + (["나머지"] if show_rest else []), name="요인"))
    lines = []
    for r in rows[: max(4, len(want))]:
        lines.append(f"{r['변수']} {r['연도']} 성장률 {r['앞']:.2f}% → {r['뒤']:.2f}% ({r['바뀜']:+.2f}%p)  자료 {r['자료']:+.2f} · 가정 {r['가정']:+.2f} · 식 {r['식']:+.2f}"
                     + (f" · 나머지 {r['나머지']:+.2f}" if show_rest else ""))
    implicit = [f"차례: 자료 → 가정 → 식(하나씩 바꿔 다시 풀어 나눔 — 차례가 바뀌면 몫이 달라질 수 있다) · 앞 {old.id} · 뒤 {new.id}(만든 때 순)",
                f"자료 {data_label(old.meta['data'])} → {data_label(new.meta['data'])} · 구간 {'~'.join(old.meta['range'])} → {'~'.join(new.meta['range'])}",
                "가정은 기록에 적힌 외생 경로(가정·채움·시나리오 충격)와 보정항 경로 — 보정항 규칙 값의 변화도 '가정'의 몫에 든다",
                "식은 기록의 조립 명세(식 글자·계수) — 지금 파일과 무관"] + implicit_sc + n0 + n1 + n2 + n3
    if worst >= 0.005:
        implicit.append(f"기록을 다시 푼 값이 기록과 최대 {worst:.3f}%p 다릅니다 — 그 차이는 '나머지'")
    payload = {"old": old.id, "new": new.id, "rows": rows, "order": list(STEPS), "max_rebuild_diff": worst}
    charts = [(f"{v0} {y0} 성장률 바뀜의 몫(%p)", bars, ["%p"], {"kind": "bar", "y": "%p"})]
    tables = [("요인 나누기 — 연간 성장률(%, %p)", tab), ("단계마다 다시 푼 성장률(%)", stp)]
    return payload, tables, charts, lines, implicit, (old, new)
