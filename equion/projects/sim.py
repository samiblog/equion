#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""전망·시나리오(`equion sim`) — 가정 세트·보정항·시나리오 파일로 풀고 기록을 남긴다 (K4·D33, E3).

    ASSUMPTIONS/이름.csv     외생 가정 경로 — 첫 열이 기간, 열마다 시리즈(전망 구간 안의 값만 쓴다). 비면 채우기 규칙([forecast] fill)
    ADDFACTORS/이름.toml     보정항 — default = "zero"|"last"|"decay"|"mean", [eq."블록:목표"] rule · half_life · n,
                             values = "ADDFACTORS/이름.csv"(판단 값 — 규칙 값을 덮는다, 열 = 부품)
    SCENARIOS/이름.toml      시나리오 — desc · base(가정 세트) · addfactors · model, [[shock]] var·from·to·pct|value,
                             [[addfactor]] eq·from·to·value. 기간은 라벨 또는 start · end · start+N · end-N(전망 구간 기준)

전망 구간의 기본은 `[forecast] range`(없으면 next:8 — 자료 끝 다음 기부터 8기). 시나리오면 같은 가정·보정항의 기준선도 함께 풀어
차이를 적는다. 계산한 값은 실측 자리에 쓰지 않는다 — 기록(`sim:이름`)의 levels.csv·flags.csv(값의 종류: 실측·해·가정·채움)에 남는다.
"""

import os
import re
import tomllib
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

import numpy as np
import pandas as pd

from ..reporting import markdown as md
from ..workfile.runtime import quiet
from ..work.store import WHO_KO, Record, now_iso
from .config import NAME_RE, ProjectError
from .records import (_assembly, _labels, _status_implicit, _version, _who, data_label, data_spec, history_of, pct,
                      store_of)

ASSUME_DIR, AF_DIR, SC_DIR = "ASSUMPTIONS", "ADDFACTORS", "SCENARIOS"
AF_RULES = ("zero", "last", "decay", "mean")
REL = re.compile(r"^(start|end)\s*(?:([+-])\s*(\d+))?$", re.I)


def _sha(path):
    import hashlib
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _rel(p, path):
    return os.path.relpath(path, p.root).replace(os.sep, "/")


# ---------------------------------------------------------------------------
# 정의 파일 읽기
# ---------------------------------------------------------------------------
def load_assumptions(p, name: str, freq: str) -> dict:
    """가정 세트 — {name, file, sha256, values(DataFrame, 인덱스 = 기간 라벨)}. 'base'인데 파일이 없으면 빈 세트."""
    from ..data.periods import format_period, parse_period
    path = os.path.join(p.root, ASSUME_DIR, f"{name}.csv")
    if not os.path.isfile(path):
        if name == "base":
            return {"name": name, "file": None, "sha256": None, "values": pd.DataFrame()}
        raise ProjectError(f"가정 세트가 없습니다: {ASSUME_DIR}/{name}.csv")
    raw = pd.read_csv(path, index_col=0, dtype=str, keep_default_na=False)
    rel = _rel(p, path)
    problems, idx = [], []
    for k, lab in enumerate(raw.index, 2):
        try:
            idx.append(format_period(parse_period(str(lab).strip(), freq), freq))
        except (ValueError, KeyError):
            problems.append(f"{rel}:{k}: 기간으로 읽을 수 없습니다 — {lab!r}")
            idx.append(None)
    vals = pd.DataFrame(index=[i for i in idx if i is not None])
    for c in raw.columns:
        col = []
        for k, (lab, v) in enumerate(zip(idx, raw[c].tolist()), 2):
            if lab is None:
                continue
            t = str(v).strip()
            if t == "":
                col.append(np.nan)
                continue
            try:
                col.append(float(t.replace(",", "")))
            except ValueError:
                problems.append(f"{rel}:{k}: {c} 칸이 숫자가 아닙니다 — {t!r}")
                col.append(np.nan)
        vals[str(c).strip()] = col
    if problems:
        raise ProjectError(problems)
    return {"name": name, "file": rel, "sha256": _sha(path), "values": vals}


def load_addfactors(p, name: str, freq: str) -> dict:
    """보정항 세트 — {name, file, sha256, default, eqs: {부품: {rule, half_life, n}}, values(판단 값 DataFrame), values_file}."""
    path = os.path.join(p.root, AF_DIR, f"{name}.toml")
    out = {"name": name, "file": None, "sha256": None, "default": "zero", "eqs": {}, "values": pd.DataFrame(),
           "values_file": None}
    if not os.path.isfile(path):
        if name == "base":
            return out
        raise ProjectError(f"보정항 세트가 없습니다: {AF_DIR}/{name}.toml")
    rel = _rel(p, path)
    try:
        with open(path, "rb") as f:
            raw = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise ProjectError(f"{rel} 문법 오류: {e}") from None
    problems = []
    out.update(file=rel, sha256=_sha(path), default=str(raw.get("default", "zero")))
    if out["default"] not in AF_RULES:
        problems.append(f"{rel}: default = {out['default']!r} — {' · '.join(AF_RULES)}")
    for pid, v in (raw.get("eq") or {}).items():
        if not isinstance(v, dict) or v.get("rule", "zero") not in AF_RULES:
            problems.append(f"{rel} [eq.\"{pid}\"]: rule = {' · '.join(AF_RULES)}")
            continue
        out["eqs"][pid] = {"rule": v.get("rule", "zero"), "half_life": float(v.get("half_life", 4)), "n": int(v.get("n", 4))}
    if raw.get("values"):
        vp = os.path.join(p.root, raw["values"])
        if not os.path.isfile(vp):
            problems.append(f"{rel}: values = {raw['values']!r} — 파일이 없습니다")
        else:
            sub = {"name": "", "file": None}
            sub.update(load_assumptions_like(p, vp, freq))
            out["values"], out["values_file"] = sub["values"], _rel(p, vp)
            out["values_sha256"] = _sha(vp)
    for k in raw:
        if k not in ("default", "eq", "values"):
            problems.append(f"{rel}: 알 수 없는 키 {k} — default · values · [eq.\"블록:목표\"]")
    if problems:
        raise ProjectError(problems)
    return out


def load_assumptions_like(p, path, freq) -> dict:
    """기간 × 열 CSV 하나(가정·판단 값 같은 꼴)."""
    from ..data.periods import format_period, parse_period
    raw = pd.read_csv(path, index_col=0, dtype=str, keep_default_na=False)
    rel = _rel(p, path)
    vals, problems = {}, []
    idx = []
    for k, lab in enumerate(raw.index, 2):
        try:
            idx.append(format_period(parse_period(str(lab).strip(), freq), freq))
        except (ValueError, KeyError):
            problems.append(f"{rel}:{k}: 기간으로 읽을 수 없습니다 — {lab!r}")
    if problems:
        raise ProjectError(problems)
    for c in raw.columns:
        vals[str(c).strip()] = [float(str(v).replace(",", "")) if str(v).strip() else np.nan for v in raw[c]]
    return {"values": pd.DataFrame(vals, index=idx)}


def load_scenario(p, name: str) -> dict:
    """시나리오 정의 — 'base'인데 파일이 없으면 빈 시나리오(가정·보정항만)."""
    path = os.path.join(p.root, SC_DIR, f"{name}.toml")
    out = {"name": name, "file": None, "sha256": None, "desc": "", "base": None, "addfactors": None, "model": None,
           "shocks": [], "addfactor": []}
    if not NAME_RE.match(name):
        raise ProjectError(f"시나리오 이름은 영문·숫자·_: {name!r}")
    if not os.path.isfile(path):
        if name == "base":
            return out
        have = sorted(f[:-5] for f in os.listdir(os.path.join(p.root, SC_DIR))) if os.path.isdir(
            os.path.join(p.root, SC_DIR)) else []
        raise ProjectError(f"시나리오가 없습니다: {SC_DIR}/{name}.toml (있는 것: {', '.join(['base'] + have)})")
    rel = _rel(p, path)
    try:
        with open(path, "rb") as f:
            raw = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise ProjectError(f"{rel} 문법 오류: {e}") from None
    from .scenarios import check_raw                # 쓰기(scenario define)와 같은 검사
    problems = check_raw(raw, rel, freq=p.config.freq)
    if problems:
        raise ProjectError(problems)
    for s in raw.get("shock") or []:
        out["shocks"].append({"var": str(s["var"]), "from": str(s.get("from", "start")), "to": str(s.get("to", "end")),
                              "kind": "pct" if "pct" in s else "level", "value": float(s.get("pct", s.get("value")))})
    for a in raw.get("addfactor") or []:
        out["addfactor"].append({"eq": str(a["eq"]), "from": str(a.get("from", "start")), "to": str(a.get("to", "end")),
                                 "value": float(a["value"])})
    out.update(file=rel, sha256=_sha(path), desc=str(raw.get("desc", "")), base=raw.get("base"),
               addfactors=raw.get("addfactors"), model=raw.get("model"))
    return out


def _between(lab, s: str, e: str, freq: str) -> bool:
    """기간 라벨 lab이 s~e 안인가 — 글자가 아니라 기간으로 견준다(월간 '2020M10'은 '2020M2' 뒤)."""
    from ..data.periods import parse_period
    try:
        x = parse_period(str(lab).strip(), freq)
        return parse_period(str(s), freq) <= x <= parse_period(str(e), freq)
    except (ValueError, TypeError, KeyError):
        return False


def _before(lab, s: str, freq: str) -> bool:
    from ..data.periods import parse_period
    try:
        return parse_period(str(lab).strip(), freq) < parse_period(str(s), freq)
    except (ValueError, TypeError, KeyError):
        return False


def _when(token: str, s: str, e: str, freq: str) -> str:
    """시나리오의 기간 — 라벨 또는 start · end · start+N · end-N(전망 구간 기준)."""
    from ..data.periods import format_period, parse_period
    m = REL.match(str(token).strip())
    if not m:
        return format_period(parse_period(str(token).strip(), freq), freq)
    base = parse_period(s if m[1].lower() == "start" else e, freq)
    k = int(m[3] or 0) * (-1 if m[2] == "-" else 1)
    return format_period(base + k, freq)


# ---------------------------------------------------------------------------
# 기록
# ---------------------------------------------------------------------------
@dataclass
class SimRecord:
    """전망 기록 하나 — `.id`(sim:…) · `.levels`(수준 — 실측 + 해·가정·채움) · `.annual`(연간 수준·증가율) · `.diff`(시나리오 − 기준선) ·
    `.text()` · `.to_dict()`."""

    record: Record
    result: object = None

    @property
    def id(self) -> str:
        """기록 이름 sim:…"""
        return self.record.id

    @property
    def meta(self) -> dict:
        """record.json 내용."""
        return self.record.meta

    @property
    def levels(self) -> pd.DataFrame:
        """수준(levels.csv — 전망 앞 2년의 실측과 전망 구간)."""
        return self.record.read_csv("levels.csv")

    @property
    def flags(self) -> pd.DataFrame:
        """값의 종류(flags.csv — 실측·해·가정·채움·결측)."""
        return self.record.read_csv("flags.csv")

    @property
    def annual(self) -> pd.DataFrame:
        """연간 평균 수준과 증가율(annual.csv)."""
        return self.record.read_csv("annual.csv")

    @property
    def diff(self) -> Optional[pd.DataFrame]:
        """시나리오 − 기준선(diff.csv — 수준 차이·%) — 기준선 기록이면 None."""
        f = self.record.file("diff.csv")
        return self.record.read_csv("diff.csv") if os.path.isfile(f) else None

    def counts(self):
        """기간 상태 수 {'ok', 'partial', 'fallback', 'failed'}."""
        return dict(self.meta["counts"])

    def text(self) -> str:
        """명령줄에 보이는 짧은 글."""
        return sim_text(self.meta)

    def to_dict(self) -> dict:
        """명령줄 --json과 같은 사전."""
        d = dict(self.meta)
        d["path"] = self.record.path
        return d

    def __repr__(self):
        return f"<전망 기록 {self.id}: {self.meta['model']} {self.meta['scenario']} {self.meta['range'][0]}~{self.meta['range'][1]}>"


def sim_text(m: dict) -> str:
    c = m["counts"]
    L = [f"[{m['id']}] {m['model']} · {m['scenario']} · {m['range'][0]}~{m['range'][1]} {m['mode']} · 정상 {c['ok']} · "
         f"일부식 제외 {c['partial']} · 실패대체 {c['fallback']} · 실패 {c['failed']}"]
    ann = m.get("annual") or {}
    if ann:
        L.append("  연간 증가율  " + " │ ".join(f"{y}: " + " · ".join(f"{v} {pct(g)}" for v, g in list(row.items())[:4])
                                         for y, row in ann.items()))
    a = m["assume"]
    bits = []
    if a.get("used"):
        bits.append(f"{a['name']}: " + "·".join(a["used"]) + f" {a['cells']}칸")
    if a.get("filled"):
        bits.append(f"채움({a['fill']}) " + " · ".join(f"{k} {v}칸" for k, v in a["filled"].items()))
    L.append("  가정   " + (" · ".join(bits) if bits else "없음(외생 실측이 전망 구간을 덮음)"))
    af = m["addfactors"]
    rules = [f"{k} {v['rule']}" + (f"({v['value']:+.3g})" if v.get("value") is not None and v["rule"] == "last" else "")
             for k, v in af["eqs"].items() if v["rule"] != "zero"]
    L.append(f"  보정항  {af['name']}: " + (" · ".join(rules) if rules else "모두 0")
             + (f" · 판단 값 {af['judgment']}칸" if af.get("judgment") else ""))
    if m.get("scenario_def"):
        sd = m["scenario_def"]
        sh = [f"{s['var']} {'+' if s['value'] >= 0 else ''}{s['value']:g}{'%' if s['kind'] == 'pct' else ''} {s['from']}~{s['to']}"
              for s in sd["shocks"]] + [f"보정 {a['eq']} {a['value']:+g} {a['from']}~{a['to']}" for a in sd["addfactor"]]
        L.append(f"  시나리오  {m['scenario']}" + (f" ({sd['desc']})" if sd.get("desc") else "") + ": " + " · ".join(sh))
    if m.get("vs_base"):
        L.append("  기준선 대비(끝 기 수준)  " + " · ".join(f"{k} {v:+.2f}%" for k, v in list(m["vs_base"].items())[:6]))
    if m.get("vs"):
        vs = m["vs"]
        ch = [f"{y} {v} {pct(a)} → {pct(b)} ({b - a:+.2f}%p)" for y, row in vs["growth"].items()
              for v, (a, b) in row.items() if a is not None and b is not None and abs(b - a) >= 0.005]
        L.append(f"  비교   vs {vs['id']} — " + (" · ".join(ch[:6]) + (" …" if len(ch) > 6 else "") if ch else
                                                 ("연간 증가율 그대로" if vs["growth"] else "견줄 연도 없음")))
    if m.get("implicit"):
        L.append("  알아서 한 것  " + " · ".join(m["implicit"]))
    L.append(f"  기록   {m['id']} ({m['path']}/)")
    return "\n".join(L)


def _sim_md(m, levels, annual, diff) -> str:
    c = m["counts"]
    a, af = m["assume"], m["addfactors"]
    sections = [("연간 평균과 증가율", md.table(annual)),
                ("풀이 상태", f"정상 {c['ok']} · 일부식 제외 {c['partial']} · 실패대체 {c['fallback']} · 실패 {c['failed']}"),
                ("가정", md.bullets(([f"{a['file']} — {', '.join(a['used'])} ({a['cells']}칸, 값의 종류 '가정')"] if a.get("used") else [])
                                    + [f"채우기 규칙 {a['fill']}: {k} {v}칸 ('채움')" for k, v in (a.get("filled") or {}).items()])),
                ("보정항", md.bullets([f"{k}: {v['rule']}" + (f" — {v['value']:+.4g}" if v.get("value") is not None else "")
                                      for k, v in af["eqs"].items()] + ([f"판단 값 {af['judgment']}칸 ({af.get('values_file')})"]
                                                                       if af.get("judgment") else [])))]
    if diff is not None:
        sections.append(("시나리오 − 기준선", md.table(diff.tail(8))))
    if m.get("vs"):
        rows = {f"{y} {v}": {"앞": a_, "지금": b_, "차이(%p)": (b_ - a_) if a_ is not None and b_ is not None else None}
                for y, row in m["vs"]["growth"].items() for v, (a_, b_) in row.items()}
        sections.append((f"비교 — vs {m['vs']['id']}", md.table(pd.DataFrame.from_dict(rows, orient="index"))))
    top = [v for v in m["endogenous"][:3]]
    if top:
        charts = [md.vega_line("levels.csv", "period", [v], f"{v} — 실측 · 전망", height=160) for v in top]
        sections.append(("수준", "\n\n".join(charts)))
    sections.append(("알아서 한 것", md.bullets(m.get("implicit") or [])))
    head = [("모형", m["model"]), ("시나리오", m["scenario"]), ("구간", f"{m['range'][0]}~{m['range'][1]} · {m['mode']}"),
            ("자료", data_label(m["data"])), ("만든 때", m.get("created") or now_iso()),
            ("누가", WHO_KO.get(m["who"], m["who"])), ("명령", m["command"]), ("equion", m["equion"])]
    return md.card(f"전망 {m['id']}", head, sections)


def _growth(df: pd.DataFrame, ppy: int) -> pd.DataFrame:
    out = {}
    for c in df.columns:
        s = df[c].astype(float)
        out[f"{c}_전기비"] = 100 * (s / s.shift(1) - 1)
        out[f"{c}_전년동기비"] = 100 * (s / s.shift(ppy) - 1)
    return pd.DataFrame(out, index=df.index)


def _annual(full: pd.DataFrame, ppy: int, years: List[str]) -> pd.DataFrame:
    """연간 평균 수준과 증가율(그 해의 기간이 다 있는 해만)."""
    yrs = pd.Index([str(i)[:4] for i in full.index])
    rows = {}
    for y in sorted(set(yrs)):
        part = full[yrs == y]
        if len(part) == ppy and part.notna().all().all():
            rows[y] = part.mean()
    ann = pd.DataFrame(rows).T
    if not len(ann):
        return ann
    g = 100 * (ann / ann.shift(1) - 1)
    out = pd.concat([ann, g.add_suffix("_증가율")], axis=1)
    out.index.name = "연도"
    return out.loc[[y for y in out.index if y in years]]


def _key_order(p, endogenous: List[str]) -> List[str]:
    """보이는 순서 — [group]의 첫 묶음(핵심 변수)을 앞에, 나머지는 조립 순서."""
    first = next(iter(p.config.groups.values()), None)
    head = [v for v in (first.series if first else []) if v in endogenous]
    return head + [v for v in endogenous if v not in head]


def _vintage_wf(p, vid):
    from ..workfile.workfile import wfopen
    from .vintage import vintage_path
    if not p.config.uses_vintages:
        raise ProjectError("--vintage는 자료 회차를 쓰는 프로젝트에서만")
    path = os.path.join(vintage_path(p.root, vid), "series.csv")
    wf = quiet(wfopen, path, freq=p.config.freq, name=p.name)
    p._wf = wf
    p._data_cols = list(wf.data.columns)
    p.config.vintage = vid
    return wf


def run_sim(p, scenario: str = "base", model: str = None, rng: str = None, vintage: str = None, vs: str = None,
            as_name: str = None, mode: str = None, who: str = None, command: str = None) -> SimRecord:
    """전망(기준선) 또는 시나리오를 풀고 기록을 남긴다."""
    from ..data.periods import PERIODS_PER_YEAR
    history_of(p).scan()
    store = store_of(p)
    fc = p.config.forecast or {}
    sd = load_scenario(p, scenario)
    name_model = model or sd.get("model") or fc.get("model") or p._default(None)
    assume = sd.get("base") or fc.get("assume") or "base"
    afname = sd.get("addfactors") or fc.get("addfactors") or "base"
    fill = fc.get("fill", "last")
    mode = mode or fc.get("mode") or "dynamic"
    if as_name:
        store.check_new("sim", as_name)
    p._reset()
    try:
        if vintage:
            _vintage_wf(p, vintage)
        wf = p.workfile
        F = wf.freq
        ppy = PERIODS_PER_YEAR[F]
        rng_spec = rng or fc.get("range") or "next:8"
        s, e = p.span(rng_spec)
        n0 = len(p.notes)
        m = p.model(name_model)
        rep = p.assemble(name_model)
        implicit = [f"구간 {rng_spec} → {s}~{e}"] + list(p.notes[n0:])
        if vintage:
            implicit.insert(0, f"자료 회차 {vintage}로(지금 회차는 그대로)")
        A = load_assumptions(p, assume, F)
        AF = load_addfactors(p, afname, F)
        quiet(wf.extend, e)
        exo = [v for v in m.exogenous if v in wf.data.columns and v not in set(wf._data.indicators)]
        endo = _key_order(p, rep.endogenous)
        i0, i1 = wf._bounds(s, e)
        labels = [wf._label(t) for t in wf.data.index]
        flags = {v: ["실측" if np.isfinite(x) else "결측" for x in wf.data[v].to_numpy(dtype=float)] for v in exo}
        used, cells, warn = [], 0, []
        for col in A["values"].columns:
            if col not in exo:
                warn.append(f"가정 {col}: 모형 {name_model}의 외생변수가 아님 — 쓰지 않음")
                continue
            ser = A["values"][col].dropna()
            before = [lab for lab in ser.index if _before(lab, s, F)]
            if before:
                warn.append(f"가정 {col}: 전망 앞 기간({before[0]}~{before[-1]})은 실측 자리라 쓰지 않음")
            k = 0
            vals = wf._data.data[col].to_numpy(dtype=float).copy()
            for lab, v in ser.items():
                if lab in labels and _between(lab, s, e, F):
                    j = labels.index(lab)
                    vals[j] = v
                    flags[col][j] = "가정"
                    k += 1
            if k:
                wf._data.data[col] = vals
                used.append(col)
                cells += k
        filled = {}
        if fill != "none":
            for col in exo:
                seg = wf.data[col].to_numpy(dtype=float)[i0:i1 + 1]
                if np.isfinite(seg).all():
                    continue
                before = np.isfinite(wf.data[col].to_numpy(dtype=float))
                try:
                    quiet(wf._data.fill_series, [col], method=fill)
                except ValueError as ex:
                    warn.append(f"{col}: 채우지 못함 — {ex}")
                    continue
                after = np.isfinite(wf.data[col].to_numpy(dtype=float))
                new = [j for j in range(i0, i1 + 1) if after[j] and not before[j]]
                for j in new:
                    flags[col][j] = "채움"
                if new:
                    filled[col] = len(new)
        # 보정항
        sc0 = m.scenario("baseline")
        af_info, af_table, judgment = {}, {}, 0
        eq_parts = [x for x in rep.parts if x.kind == "equation"]
        jv = AF["values"]
        for x in eq_parts:
            spec = AF["eqs"].get(x.id) or {"rule": AF["default"], "half_life": 4.0, "n": 4}
            eqo = next(o for o in m.equations if o.target == x.target)
            res = eqo.eq.residual_series().to_numpy(dtype=float)
            hist = res[:i0]
            fin = np.where(np.isfinite(hist))[0]
            path = np.zeros(i1 - i0 + 1)
            val = None
            if spec["rule"] != "zero" and len(fin):
                last = float(hist[fin[-1]])
                if spec["rule"] == "last":
                    path[:], val = last, last
                elif spec["rule"] == "decay":
                    path[:] = [last * 0.5 ** ((k + 1) / spec["half_life"]) for k in range(len(path))]
                    val = last
                else:
                    val = float(np.mean(hist[fin[-spec["n"]:]]))
                    path[:] = val
            if x.id in jv.columns:
                for lab, v in jv[x.id].dropna().items():
                    if lab in labels and _between(lab, s, e, F):
                        path[labels.index(lab) - i0] = v
                        judgment += 1
            af_info[x.id] = {"rule": spec["rule"], "value": val, "half_life": spec.get("half_life"), "n": spec.get("n")}
            af_table[x.id] = path
            if np.any(path != 0):
                sc0.add_factor(x.target, pd.Series(path, index=wf.data.index[i0:i1 + 1]))
        n_rule = sum(int(np.count_nonzero(v)) for v in af_table.values()) - judgment
        if n_rule > 0:
            implicit.append(f"보정항 규칙 값 {n_rule}칸")
        if judgment:
            implicit.append(f"보정항 판단 값 {judgment}칸")
        if cells:
            implicit.append(f"가정 {cells}칸({', '.join(used)})")
        for k_, v_ in filled.items():
            implicit.append(f"외생 {k_} {v_}칸을 채움({fill})")
        implicit += warn
        try:
            res0 = m.forecast(s, e, mode=mode, scenario="baseline")
        except ValueError as ex:
            raise ProjectError(f"전망을 풀 수 없습니다: {ex}") from None
        res = res0
        diff = None
        vs_base = None
        exo_shock = []      # 시나리오가 외생 경로에 준 충격 (변수, 종류, 값, 처음, 끝) — 기록의 수준에 푼 그 경로를 적는다
        if scenario != "base" or sd.get("shocks") or sd.get("addfactor"):
            sc1 = m.scenario(scenario)
            for x in eq_parts:
                if np.any(af_table[x.id] != 0):
                    sc1.add_factor(x.target, pd.Series(af_table[x.id], index=wf.data.index[i0:i1 + 1]))
            for sh in sd["shocks"]:
                a_, b_ = _when(sh["from"], s, e, F), _when(sh["to"], s, e, F)
                if sh["var"] not in exo and sh["var"] not in endo:
                    raise ProjectError(f"시나리오 {scenario}: {sh['var']}는 모형 {name_model}에 없는 변수입니다")
                sc1.shock(sh["var"], sh["value"], a_, b_, kind=sh["kind"])
                if sh["var"] in exo and sh["kind"] != "add_factor":
                    exo_shock.append((sh["var"], sh["kind"], sh["value"], *wf._bounds(a_, b_)))
            for ad in sd["addfactor"]:
                pt = p.part(ad["eq"])
                sc1.shock(pt.target, ad["value"], _when(ad["from"], s, e, F), _when(ad["to"], s, e, F), kind="add_factor")
            res = quiet(m.solve, s, e, mode=mode, scenario=scenario)
            b = res0.values
            d = res.values[[c for c in b.columns]]
            lab_f = _labels(wf, b.index)
            diff = pd.concat([(d - b).add_suffix("_차이"), (100 * (d / b - 1)).add_suffix("_%")], axis=1)
            diff.index = pd.Index(lab_f, name="period")
            vs_base = {v: float(100 * (d[v].iloc[-1] / b[v].iloc[-1] - 1)) for v in endo if v in b.columns}
        # 수준·값의 종류
        h0 = max(0, i0 - 2 * ppy)
        full = pd.DataFrame(index=wf.data.index)
        sol = res.values
        for v in endo:
            col = wf.data[v].to_numpy(dtype=float).copy() if v in wf.data.columns else np.full(len(wf.data), np.nan)
            col[i0:i1 + 1] = sol[v].to_numpy(dtype=float)
            full[v] = col
        for v in exo:
            full[v] = wf.data[v].to_numpy(dtype=float)
        for v, kind, value, ja, jb in exo_shock:        # Scenario.build와 같은 셈 — 기준선의 가정 경로가 아니라 시나리오가 푼 경로
            col = full[v].to_numpy(dtype=float).copy()
            col[ja:jb + 1] = col[ja:jb + 1] + value if kind == "level" else col[ja:jb + 1] * (1 + value / 100.0)
            full[v] = col
        full.index = pd.Index(labels, name="period")
        levels = full.iloc[h0:i1 + 1]
        fl = pd.DataFrame(index=levels.index)
        for v in endo:
            fl[v] = ["해" if i0 <= j <= i1 else ("실측" if np.isfinite(full[v].iloc[j]) else "결측") for j in range(h0, i1 + 1)]
        for v in exo:
            fl[v] = flags[v][h0:i1 + 1]
        years = sorted({lab[:4] for lab in labels[i0:i1 + 1]})
        ann = _annual(full[endo].iloc[:i1 + 1], ppy, years)
        ann_meta = {y: {v: (None if not np.isfinite(ann.loc[y, f"{v}_증가율"]) else float(ann.loc[y, f"{v}_증가율"]))
                        for v in endo} for y in ann.index} if len(ann) else {}
        growth = _growth(levels[endo], ppy)
        afdf = pd.DataFrame(af_table, index=pd.Index(labels[i0:i1 + 1], name="period"))
        vs_info = None
        if vs:
            other = store.get(vs, "sim")
            oa = other.read_csv("annual.csv")
            g = {}
            for y in ann.index:
                if y in oa.index:
                    g[y] = {v: (float(oa.loc[y, f"{v}_증가율"]) if f"{v}_증가율" in oa.columns and np.isfinite(oa.loc[y, f"{v}_증가율"]) else None,
                                ann_meta.get(y, {}).get(v)) for v in endo}
            vs_info = {"id": other.id, "growth": g}
        asm = _assembly(p, name_model, m, rep.parts, (s, e), mode, {}, {})
        asm["forecast"] = {"scenario": scenario, "assume": {"name": assume, "file": A["file"], "sha256": A["sha256"]},
                           "addfactors": {"name": afname, "file": AF["file"], "sha256": AF["sha256"],
                                          "values_file": AF.get("values_file"), "values_sha256": AF.get("values_sha256")},
                           "scenario_file": {"file": sd["file"], "sha256": sd["sha256"]}, "fill": fill, "range": rng_spec}
        name = as_name or _sim_name(store, scenario, vintage or p.vintage)
        rel = f"work/sim/{name}"
        c = res.counts()
        meta = {"who": _who(who), "command": command or f"sim {scenario}", "project": p.name, "equion": _version(),
                "target": name_model, "model": name_model, "scenario": scenario, "range": [s, e], "mode": mode,
                "counts": c, "endogenous": endo, "exogenous": exo, "annual": ann_meta,
                "assume": {"name": assume, "file": A["file"], "used": used, "cells": cells, "fill": fill, "filled": filled},
                "addfactors": {"name": afname, "file": AF["file"], "eqs": af_info, "judgment": judgment,
                               "values_file": AF.get("values_file")},
                "scenario_def": ({k: sd[k] for k in ("desc", "shocks", "addfactor", "file")} if sd["file"] else None),
                "vs_base": vs_base, "vs": vs_info, "implicit": implicit + _status_implicit(res), "data": data_spec(p),
                "path": rel, "id": f"sim:{name}"}
        files = {"assembly.json": asm, "levels.csv": levels, "flags.csv": fl, "growth.csv": growth, "annual.csv": ann,
                 "addfactors.csv": afdf}
        if diff is not None:
            files["diff.csv"] = diff
        summary = _sim_md(meta, levels, ann, diff)
        rec = store.write("sim", name, meta, files, summary,
                          log={"metric": " · ".join(f"{y} {v} {pct(g)}" for y, row in list(ann_meta.items())[:1]
                                                    for v, g in list(row.items())[:2]), "counts": c})
        return SimRecord(rec, res)
    finally:
        p._reset()


def _sim_name(store, scenario, vintage) -> str:
    base = f"{datetime.now():%Y-%m}_{scenario}"
    if not store.exists("sim", base):
        return base
    k = 2
    while store.exists("sim", f"{base}_{k}"):
        k += 1
    return f"{base}_{k}"
