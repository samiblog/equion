#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""작업 명령 — 추정(`est`)·채택(`adopt`)·비교(`compare`)·과거 재현(`hs` — 바꿔 끼우기·전후 비교·그때 그대로 다시) (D33·D35, E3).

계산할 때마다 `work/<종류>/<이름>/`에 기록을 남긴다(store). 출력은 짧은 글(`.text()` — Claude의 문맥을 아낀다)과 사전(`.to_dict()` —
명령줄 `--json`), 사람이 읽는 카드(`summary.md`). 계산은 늘 워크파일 API·엔진 한 곳에서 한다 — 이 층은 기록과 이름만 붙인다.
"""

import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from ..reporting import markdown as md
from ..workfile.runtime import quiet
from ..work.history import History
from ..work.lock import locked, project_lock, read_bytes
from ..work.store import KIND_KO, WHO_KO, Record, RecordError, WorkStore, detect_who, now_iso
from .config import ProjectError

ADOPTED = "EQUATIONS/adopted.toml"
METHOD_KO = {"ols": "OLS", "tsls": "TSLS", "nls": "NLS", "fixed": "고정", "wls": "WLS", "gmm": "GMM", "liml": "LIML"}


def _method_label(eq) -> str:
    """추정법의 보이는 이름 — c(n) 식의 도구변수 추정은 NL-TSLS(D64)."""
    lab = (getattr(eq, "statistics", None) or getattr(eq, "stats", None) or {}).get("method")
    return lab if lab == "NL-TSLS" else METHOD_KO.get(eq.method, str(eq.method).upper())
DIAG_KEYS = (("계열상관 LM", "lm"), ("White", "white"), ("Breusch-Pagan", "bp"), ("Ljung-Box", "lb"),
             ("ARCH", "arch"), ("Jarque-Bera", "jb"), ("RESET", "reset"))
DIAG_LABEL = {"lm": "LM(2)", "white": "White", "bp": "BP", "lb": "LB(4)", "arch": "ARCH", "jb": "JB", "reset": "RESET"}
DIAG_SHOW = ("lm", "white", "jb", "reset", "lb")


# ---------------------------------------------------------------------------
# 작은 도움
# ---------------------------------------------------------------------------
def store_of(p) -> WorkStore:
    return WorkStore(p.root)


def history_of(p) -> History:
    extra = [b.file for b in p.config.blocks.values()] + [ADOPTED]
    return History(p.root, extra=extra)


def short(v) -> str:
    """짧은 수 — 크기에 맞춘 자릿수."""
    if v is None or not np.isfinite(v):
        return "NA"
    a = abs(v)
    if a >= 100:
        return f"{v:,.1f}"
    if a >= 1:
        return f"{v:.3f}"
    if a >= 1e-3 or a == 0:
        return f"{v:.4f}"
    return f"{v:.2e}"


def pfmt(p) -> str:
    if p is None or not np.isfinite(p):
        return "NA"
    return "<0.001" if p < 0.001 else f"{p:.3f}"


def pct(v) -> str:
    return "NA" if v is None or not np.isfinite(v) else f"{v:.2f}%"


def _norm_term(t: str) -> str:
    t = str(t).replace(" ", "").lower()
    return "const" if t in ("c", "const") else t


def _labels(wf, idx) -> List[str]:
    if isinstance(idx, pd.DatetimeIndex):
        return [wf._label(t) for t in idx]
    return [str(t) for t in idx]


def data_spec(p) -> dict:
    """계산에 쓴 자료 — 자료 회차(이름·내용 해시) 또는 자료 파일(해시)."""
    c = p.config
    if c.uses_vintages:
        from .vintage import vintage_path
        with open(os.path.join(vintage_path(c.root, c.vintage), "build.json"), encoding="utf-8") as f:
            b = json.load(f)
        return {"kind": "vintage", "id": c.vintage, "content_sha256": b.get("content_sha256"), "freq": c.freq}
    from ..data.source import file_sha256
    return {"kind": "file", "file": c.data_file, "sha256": file_sha256(c.data_path)}


NOT_INPUT = ("notes/", "reports/", "FLOWS/", "VIEWS/")      # 바뀜 기록은 지켜보지만 계산의 입력은 아닌 정의 파일
FORECAST_ONLY = ("ASSUMPTIONS/", "ADDFACTORS/", "SCENARIOS/")  # 전망(sim)만 읽는 정의 — 추정·과거 재현·분석 기록은 이것이 바뀌어도 낡지 않는다


def definition_hashes(p) -> Dict[str, str]:
    """정의 파일(블록·equion.toml·채택표·자료 정의·가정·보정항·시나리오)의 해시 — 조립 명세에 남긴다."""
    import hashlib
    from ..work.history import tracked
    out = {}
    for rel in tracked(p.root, [b.file for b in p.config.blocks.values()] + [ADOPTED]):
        if rel.startswith(NOT_INPUT):   # 노트·보고서는 글, 스크립트는 순서, 보기는 보이는 모양 — 계산의 입력이 아니다
            continue
        try:
            data = read_bytes(os.path.join(p.root, rel), p.root)
        except PermissionError:         # 다른 프로그램이 쥐고 있다 — 해시는 모름(None)으로 남기고 계산은 잇는다
            out[rel] = None
            continue
        if data is not None:
            out[rel] = hashlib.sha256(data).hexdigest()
    return out


def definition_files(p, documents: bool = False) -> List[str]:
    """정의 파일(프로젝트 기준 경로) — 바뀜 기록이 지켜보는 표준 자리(equion.toml · EQUATIONS/ · DATA/series.toml·derived.txt ·
    ASSUMPTIONS/ · ADDFACTORS/ · SCENARIOS/ · VIEWS/ · FLOWS/)와 equion.toml이 가리키는 다른 자리(블록 파일 · 자료 정의 · 보정항의 판단 값 파일).
    documents=True면 노트·보고서(notes/·reports/)도. 프로젝트 밖·work/를 가리키는 경로는 넣지 않는다 — 이정표·묶음이 쓴다."""
    import glob
    import tomllib
    from ..work.history import tracked
    cfg = p.config
    extra = [b.file for b in cfg.blocks.values()] + [ADOPTED] + [x for x in (cfg.series_file, cfg.derived_file) if x]
    for f in sorted(glob.glob(os.path.join(p.root, "ADDFACTORS", "*.toml"))):
        try:
            with open(f, "rb") as fh:
                raw = tomllib.load(fh)
        except (OSError, ValueError):
            continue
        if isinstance(raw.get("values"), str):
            extra.append(raw["values"])
    root = os.path.abspath(p.root)
    out = set()
    for rel in tracked(p.root, extra):
        full = os.path.abspath(os.path.join(root, rel))
        try:
            inside = os.path.commonpath([os.path.normcase(full), os.path.normcase(root)]) == os.path.normcase(root)
        except ValueError:                       # 다른 드라이브
            inside = False
        rel = os.path.relpath(full, root).replace(os.sep, "/") if inside else ""
        if not rel or rel.startswith("work/") or (not documents and rel.startswith(("notes/", "reports/"))):
            continue
        out.add(rel)
    return sorted(out)


def data_label(spec: dict) -> str:
    return f"data:{spec['id']}" if spec.get("kind") == "vintage" else f"{spec.get('file')}"


def _version():
    from ..version import project_version
    return project_version()


def _who(who):
    return who or detect_who("python")


def _criteria(cfg) -> dict:
    return cfg.criteria or {}


def judge(criteria: dict, part_id: Optional[str], coefs: pd.Series, tstats: pd.Series, diag: dict,
          method: str = None, label: str = None) -> Optional[dict]:
    """판단 기준 — 기대 부호·진단 p값·|t| 하한. 기준이 없으면 None. {pass, reasons, signs: [{term, want, coef, ok}]}.

    기준에 넣은 진단(tests)을 이 추정법이 계산하지 않았으면(TSLS·NLS에는 LM·RESET이 없다 — 진단을 못 했을 때도) 판단할 수 없다:
    pass = None(판단 못 함) · untested = [검정] · note(까닭). c(n) 식(NLS)은 계수 이름이 항 이름이 아니라 기대 부호도 볼 수 없다.
    걸러질 까닭이 따로 있으면 pass = False(걸러짐)이다. 모두 계산했으면 전과 같다(untested 키 없음)."""
    if not criteria:
        return None
    alpha = criteria.get("alpha", 0.05)
    reasons, signs, untested = [], [], []
    want = (criteria.get("signs") or {})
    terms = {}
    if part_id:
        for k, v in want.items():
            if k.lower() == part_id.lower():
                terms = v
    names = {_norm_term(n): n for n in coefs.index}
    for term, sgn in terms.items():
        n = names.get(_norm_term(term))
        if n is None:
            signs.append({"term": term, "want": sgn, "coef": None, "ok": None})
            if method == "nls":
                untested.append(f"{term} 부호")
            continue
        c = float(coefs[n])
        ok = c > 0 if sgn == "+" else c < 0
        signs.append({"term": term, "want": sgn, "coef": c, "ok": bool(ok)})
        if not ok:
            reasons.append(f"{term} 부호")
    no_test = []
    for t in criteria.get("tests") or []:
        d = diag.get(t)
        if d is None:
            no_test.append(t)
            continue
        if np.isfinite(d["p"]) and d["p"] < alpha:
            reasons.append(f"{DIAG_LABEL[t]} p={pfmt(d['p'])}")
    tmin = criteria.get("t_min")
    if tmin:
        for n, t in tstats.items():
            if n != "const" and np.isfinite(t) and abs(t) < tmin:
                reasons.append(f"{n} t {t:.2f}")
    out = {"pass": not reasons, "reasons": reasons, "signs": signs, "alpha": alpha}
    if no_test or untested:
        lab = label or (METHOD_KO.get(method, str(method).upper()) if method else "이 추정법")
        bits = []
        if no_test:
            bits.append(f"검정 없음 — {'·'.join(DIAG_LABEL.get(t, t) for t in no_test)}을(를) {lab}에는 계산하지 않음")
        if untested:
            bits.append(f"기대 부호 — c(n) 식이라 항 이름으로 볼 수 없음({', '.join(x.split()[0] for x in untested)})")
        out["untested"] = [DIAG_LABEL.get(t, t) for t in no_test] + untested
        out["note"] = " · ".join(bits)
        if not reasons:
            out["pass"] = None
    return out


def criteria_text(cr: Optional[dict]) -> str:
    if cr is None:
        return ""
    sg = " · ".join(f"{s['term']} {s['want']} " + ("✓" if s["ok"] else ("✗" if s["ok"] is False else "(항 없음)"))
                    for s in cr["signs"])
    if cr["pass"]:
        return "통과" + (f" · 부호 {sg}" if sg else "")
    if cr["pass"] is None:
        return "판단 못 함: " + (cr.get("note") or "") + (f" · 부호 {sg}" if sg else "")
    return "걸러짐: " + " · ".join(cr["reasons"]) + (f" (판단 못 한 것: {cr['note']})" if cr.get("note") else "")


def criteria_word(cr: Optional[dict]) -> str:
    """기준 한 낱말 — 통과 · 걸러짐 · 판단 못 함(기준이 없으면 빈 글)."""
    if cr is None:
        return ""
    return "통과" if cr["pass"] else ("판단 못 함" if cr["pass"] is None else "걸러짐")


# ---------------------------------------------------------------------------
# 추정 기록
# ---------------------------------------------------------------------------
@dataclass
class EstRecord:
    """추정 기록 하나 — `.id`(est:…) · `.meta`(record.json) · `.coefs` · `.passed`(판단 기준) · `.text()` · `.to_dict()`."""

    record: Record

    @property
    def id(self) -> str:
        """기록 이름 est:…"""
        return self.record.id

    @property
    def meta(self) -> dict:
        """record.json 내용."""
        return self.record.meta

    @property
    def coefs(self) -> pd.Series:
        """계수(이름 = 항, 상수항은 const)."""
        return pd.Series({c["name"]: c["coef"] for c in self.meta["coefs"]}, dtype=float)

    @property
    def passed(self) -> Optional[bool]:
        """판단 기준 통과(기준이 없으면 None)."""
        cr = self.meta.get("criteria")
        return None if cr is None else cr["pass"]

    def text(self) -> str:
        """명령줄에 보이는 짧은 글."""
        return est_text(self.meta)

    def to_dict(self) -> dict:
        """명령줄 --json과 같은 사전(record.json에서 식 직렬화를 뺀 것)."""
        d = dict(self.meta)
        d.pop("equation", None)
        d["path"] = self.record.path
        return d

    def __repr__(self):
        return f"<추정 기록 {self.id}: {self.meta.get('text')}>"


def est_text(m: dict) -> str:
    st = m["stats"]
    s, e = m["sample"]
    head = (f"[{m['id']}] {m.get('method_label') or METHOD_KO.get(m['method'], m['method'].upper())} {m['dependent']} · {s}~{e} · n={m['n']}   "
            f"R²adj {short(st.get('adj_r_squared'))} · SE {short(st.get('se_regression'))} · "
            f"DW {short(st.get('durbin_watson'))} · AIC {short(st.get('aic'))} · BIC {short(st.get('bic'))}")
    L = [head]
    L.append("  계수   " + " · ".join(f"{'c' if c['name'] == 'const' else c['name']} {short(c['coef'])}(t {short(c['t'])})"
                                    for c in m["coefs"])
             + (f"   [공분산 {m['cov'].get('label') or m['cov'].get('type')}]" if m.get("cov") else ""))
    alpha = (m.get("criteria") or {}).get("alpha", 0.05)
    dg = m.get("diagnostics") or {}
    shown = [f"{DIAG_LABEL[k]} p={pfmt(dg[k]['p'])} {'✓' if dg[k]['p'] >= alpha else '!'}"
             for k in DIAG_SHOW if k in dg and np.isfinite(dg[k]["p"])]
    if shown:
        L.append("  진단   " + " · ".join(shown))
    ct = criteria_text(m.get("criteria"))
    if ct:
        L.append(f"  기준   {ct}")
    if m.get("sim"):
        sm = m["sim"]
        L.append(f"  단독 모의  {sm['start']}~{sm['end']} {m['target']} RMSPE {pct(sm['rmspe'])}")
    if m.get("implicit"):
        L.append("  알아서 한 것  " + " · ".join(m["implicit"]))
    tail = f"  기록   {m['id']} ({m['path']}/)"
    if m.get("part"):
        tail += f" · {m['part']} 후보"
    L.append(tail)
    return "\n".join(L)


def _diagnostics(obj) -> (dict, List[str]):
    try:
        t = quiet(obj.diagnostics, 2).data
    except (ValueError, RuntimeError, np.linalg.LinAlgError) as e:
        return {}, [f"진단 못 함: {str(e)[:80]}"]
    out = {}
    for name, row in t.iterrows():
        key = next((v for k, v in DIAG_KEYS if str(name).startswith(k)), None)
        if key:
            out[key] = {"name": str(name), "stat": float(row["통계량"]), "p": float(row["p값"])}
    return out, []


def _single_sim(p, obj, target, start, end):
    """식 하나의 동태 모의(다른 변수는 실측) — 목표변수 수준의 RMSPE."""
    from ..system.model import Model
    wf = p.workfile
    s, e = wf._bounds(start, end)
    eq = obj.eq

    def run():
        m = Model(wf._data, [eq])
        m.wt = wf._wt
        return m.simulate(s, e, mode="dynamic", verbose=False)
    sim = quiet(run)
    v = sim.values[target].to_numpy(dtype=float)
    a = wf.data[target].to_numpy(dtype=float)[s:e + 1]
    ok = np.isfinite(v) & np.isfinite(a) & (a != 0)
    rmspe = float(100 * np.sqrt(np.mean(((v[ok] - a[ok]) / a[ok]) ** 2))) if ok.any() else float("nan")
    return {"start": wf._label(wf.data.index[s]), "end": wf._label(wf.data.index[e]), "rmspe": rmspe,
            "n": int(ok.sum())}, pd.Series(v, index=wf.data.index[s:e + 1])


def _not_a_formula(p, t: str):
    """est에 식이 아니라 모형·블록·목표변수 이름 하나를 주었으면 할 일을 알린다('방정식 형식 오류: 최소 2개 항' 대신)."""
    if not t or any(ch in t for ch in " =()+-*/^@"):
        return
    low = t.lower()
    model = next((m for m in p.models if m.lower() == low), None)
    block = next((b for b in p.blocks if b.lower() == low), None)
    if model or block:
        nm = model or block
        eqs = [x.id for x in p.parts(nm) if x.kind == "equation"]
        raise ProjectError(f"{nm}는 {'모형' if model else '블록'} 이름입니다 — 그 추정식을 모두 다시 추정하려면 equion est {nm} --adopted"
                           + (f", 식 하나는 부품으로(예: equion est {eqs[0]})" if eqs else ""))
    cands = [x.id for x in p.parts() if x.kind == "equation" and x.target.lower() == low]
    if cands:
        raise ProjectError(f"{t}는 목표변수 이름입니다 — 부품으로 주세요: {' · '.join(cands)}(예: equion est {cands[0]}). "
                           f"새 식 후보면 식 글자 그대로(예: equion est \"{t} c …\" --for {cands[0]})")


def run_est(p, target: str, method: str = None, smpl: str = None, as_name: str = None, part: str = None,
            sim: bool = False, cov: str = None, who: str = None, command: str = None) -> EstRecord:
    """식 하나를 추정해 기록을 남긴다. target은 부품(`demand:CN` — 블록 파일의 그 줄) 또는 식 글자."""
    from ..workfile.objects import EquationObject
    from .parts import parse_line
    history_of(p).scan()
    store = store_of(p)
    wf = p.workfile
    data = wf._data
    pt = None
    t = target.strip()
    if ":" in t and " " not in t and not t.startswith("@"):
        pt = p.part(t)
        if pt.kind != "equation":
            raise ProjectError(f"{pt.id}는 항등식입니다 — 추정하지 않습니다(equion ident {pt.id} --check)")
        text, expr = pt.text, pt.expr
    else:
        text = expr = t
        _not_a_formula(p, t)
    info = quiet(parse_line, expr, data)
    if info["kind"] == "identity":
        raise ProjectError(f"항등식입니다 — 추정하지 않습니다: {text}")
    tv = info["target"]
    notes = []
    if pt is None and part:
        pt = p.part(part)
        if pt.target != tv:
            raise ProjectError(f"--for {pt.id}: 목표가 {pt.target}인데 이 식의 목표는 {tv}입니다")
    elif pt is None:
        cands = [x for x in p.parts() if x.kind == "equation" and x.target == tv]
        if len(cands) == 1:
            pt = cands[0]
        elif len(cands) > 1:
            notes.append(f"목표 {tv}의 식이 여럿({', '.join(x.id for x in cands)}) — 후보로 묶으려면 --for")
    if as_name:
        store.check_new("est", as_name)               # 준 이름은 계산 전에 알린다 — 이름은 다 계산한 뒤 잠금 안에서 정한다
    if method not in (None, "auto", "ls", "tsls"):
        raise ProjectError(f"--method {method!r} — auto · ls · tsls")
    from ..formula.parser import has_instruments
    meth = "tsls" if (method == "tsls" or (method in (None, "auto") and has_instruments(expr))) else None
    if method == "ls" and has_instruments(expr):
        raise ProjectError("도구변수(@inst)가 있는 식은 --method tsls(또는 auto)로")
    old_smpl = wf._smpl
    req = None
    try:
        if smpl:
            s0, e0 = p.span(smpl)
            quiet(wf.smpl, s0, e0)
            req = (s0, e0)
        obj = EquationObject(wf, f"est_{as_name or tv.lower()}")
        try:
            eq = obj._make(expr, method=meth, cov=cov)
        except Exception as ex:  # noqa: BLE001 — 문법·자료 문제를 그대로 알린다
            raise ProjectError(f"추정할 수 없습니다: {ex}") from None
        obj._adopt(eq, expr, loud=False)
    finally:
        wf._smpl = old_smpl
    return _write_est(p, store, obj, text, expr, pt, tv, as_name, req, notes, sim, who, command or f"est {target}",
                      smpl_spec=smpl)


def record_equation(p, obj, part: str = None, as_name: str = None, notes=(), who: str = None,
                    command: str = None) -> EstRecord:
    """이미 계수가 있는 방정식 객체(분석이 낸 식 — ECM 단기식·VAR·VECM·시스템)를 추정 기록(후보)으로 남긴다. 다시 추정하지 않는다."""
    from .parts import parse_line
    history_of(p).scan()
    store = store_of(p)
    expr = obj.spec
    tv = obj.eq.target
    pt = p.part(part) if part else None
    if pt is None:
        cands = [x for x in p.parts() if x.kind == "equation" and x.target == tv]
        pt = cands[0] if len(cands) == 1 else None
    elif pt.target != tv:
        raise ProjectError(f"--part {pt.id}: 목표가 {pt.target}인데 이 식의 목표는 {tv}입니다")
    quiet(parse_line, expr, p.workfile._data)
    if as_name:
        store.check_new("est", as_name)
    import re
    src = re.search(r"\b(an:[A-Za-z0-9][A-Za-z0-9_\-]*)", " ".join([str(command or "")] + [str(x) for x in notes]))
    return _write_est(p, store, obj, expr, expr, pt, tv, as_name, None, list(notes), False, who, command or "an keep",
                      source=src[1] if src else None)


def _write_est(p, store, obj, text, expr, pt, tv, as_name, req, notes, sim, who, command, smpl_spec=None,
               source=None) -> EstRecord:
    """추정 기록을 쓴다 — 이름(as_name, 없으면 목표의 다음 번호)은 계산을 다 한 뒤 프로젝트 잠금 안에서 정한다(같은 식을 여럿이
    한꺼번에 추정해도 이름이 겹치지 않게)."""
    wf = p.workfile
    eq = obj.eq
    res = eq.residuals
    lab = _labels(wf, res.index)
    s, e = lab[0], lab[-1]
    implicit = []
    if expr != text:
        implicit.append("@def 매크로를 펼침")
    first, last = (req if req else (wf._label(wf.data.index[0]), wf._label(wf.data.index[-1])))
    if eq.smpl_start or eq.smpl_end:
        first = eq.smpl_start or first
        last = eq.smpl_end or last
    drops = getattr(eq, "sample_drops", None) or {}          # 빠진 기간의 까닭(엔진 — D66): 결측 · 정의역 밖 값
    dom, dom_why = set(drops.get("domain") or ()), drops.get("why") or "정의역 밖 값"

    def _at(lab, end=False):                                 # 라벨 → 자료 위치(못 찾으면 None)
        try:
            return wf._bounds(lab, lab)[1 if end else 0]
        except (ValueError, KeyError, TypeError):
            return None

    def _dom(a, b):                                          # 위치 a..b(양끝 포함)에서 정의역 탓으로 빠진 기간 수
        if not dom or a is None or b is None:
            return 0
        return sum(1 for t in wf.data.index[max(a, 0):b + 1] if t in dom)

    def _why(k, n, other):                                   # 빠진 n기 가운데 k기가 정의역 탓
        return f"{dom_why} {k}기" + (f" · {other} {n - k}기" if n > k else "(결측이 아님)")
    if s != first:
        a0, a1 = _at(first), _at(s)
        k = _dom(a0, a1 - 1) if a1 is not None else 0
        implicit.append(f"시차·결측으로 표본 시작 {first} → {s}" if not k else
                        f"표본 시작 {first} → {s} — " + _why(k, a1 - a0, "시차·결측"))
    if e != last:
        b0, b1 = _at(e), _at(last, end=True)
        k = _dom(b0 + 1, b1) if b0 is not None else 0
        implicit.append(f"결측으로 표본 끝 {last} → {e}" if not k else
                        f"표본 끝 {last} → {e} — " + _why(k, b1 - b0, "결측"))
    span_n = wf._bounds(s, e)
    gap = (span_n[1] - span_n[0] + 1) - int(obj.nobs)
    if gap > 0:
        k = _dom(span_n[0], span_n[1])
        implicit.append(f"안쪽 결측 {gap}기 빠짐" if not k else f"안쪽 {gap}기 빠짐 — " + _why(k, gap, "결측"))
    w0, w1 = _at(first), _at(last, end=True)
    n_win = (w1 - w0 + 1) if w0 is not None and w1 is not None else 0
    if n_win and int(obj.nobs) < 0.75 * n_win:
        implicit.append(f"표본이 크게 줄었습니다 — 구간 {first}~{last} {n_win}기 가운데 {int(obj.nobs)}기만 추정에 씀")
    if eq.method == "tsls" and eq.has_constant:
        implicit.append("상수항을 도구변수에 넣음")
    st = obj.stats
    if st.get("collinear"):
        implicit.append(f"회귀변수 선형 종속({', '.join(st['collinear'])})")
    implicit += notes
    coefs, se, tt, pv = obj.coefs, obj.stderrs, obj.tstats, obj.pvalues
    diag, dn = _diagnostics(obj)
    implicit += dn
    cr = judge(_criteria(p.config), pt.id if pt else None, coefs, tt, diag, method=eq.method, label=_method_label(eq))
    sim_info, sim_s = None, None
    if sim:
        s1, e1 = p._range(None, None)
        if s1 is None or e1 is None:
            s1, e1 = s, e
        from ..data.periods import parse_period
        if parse_period(s1, wf.freq) < parse_period(s, wf.freq):
            s1 = s
        sim_info, sim_s = _single_sim(p, obj, tv, s1, e1)
    with store.naming("est", as_name, tv.lower()) as name:
        rel = f"work/est/{name}"
        meta = {
            "who": _who(who), "command": command, "project": p.name, "equion": _version(),
            "target": tv, "part": pt.id if pt else None, "text": text, "expr": expr, "method": eq.method,
            "method_label": _method_label(eq),
            "dependent": eq.dependent_var, "sample": [s, e], "n": int(obj.nobs),
            "smpl": smpl_spec,                 # 준 표본 표기(--smpl, 상대 기간 그대로) — 없으면 None(식의 @smpl, 없으면 자료 전체)
            "stats": {k: st.get(k) for k in ("r_squared", "adj_r_squared", "se_regression", "durbin_watson",
                                              "log_likelihood", "aic", "bic", "f_statistic", "f_pvalue")},
            "coefs": [{"name": n, "coef": float(coefs[n]), "se": float(se[n]), "t": float(tt[n]), "p": float(pv[n])}
                      for n in coefs.index],
            "diagnostics": diag, "criteria": cr, "sim": sim_info, "implicit": implicit, "data": data_spec(p),
            "equation": eq.to_saved(), "path": rel, "id": f"est:{name}",
            **({"from": source} if source else {}),   # 이 식을 낸 분석 기록(an keep) — 정리(work clean)가 그 기록을 지키도록
            # 계수 공분산(표준오차·t·p의 종류) — 보통이면 None. 견고한 공분산으로 본 기록은 t값이 다른 까닭을 기록이 스스로 말한다
            "cov": ({"type": st.get("cov_type"), "label": st.get("cov_label"), "lags": st.get("hac_lags")}
                    if st.get("cov_type", "nonrobust") != "nonrobust" else None),
        }
        act = obj.actual.loc[res.index]
        series = pd.DataFrame({"actual": act.to_numpy(), "fitted": (act - res).to_numpy(), "resid": res.to_numpy()},
                              index=pd.Index(lab, name="period"))
        if sim_s is not None:
            series = series.join(pd.DataFrame({f"{tv}": wf.data[tv].loc[sim_s.index].to_numpy(),
                                               f"{tv}_sim": sim_s.to_numpy()},
                                              index=pd.Index(_labels(wf, sim_s.index), name="period")), how="outer")
        ctab = pd.DataFrame([{k: c[k] for k in ("coef", "se", "t", "p")} for c in meta["coefs"]],
                            index=pd.Index([c["name"] for c in meta["coefs"]], name="항"))
        summary = _est_md(meta, ctab, sim_s is not None)
        rec = store.write("est", name, meta, {"coefs.csv": ctab, "series.csv": series}, summary,
                          log={"part": meta["part"], "metric": f"R²adj {short(st.get('adj_r_squared'))}",
                               "pass": None if cr is None else cr["pass"]})
        return EstRecord(rec)


def _est_md(m, ctab, has_sim) -> str:
    st = m["stats"]
    dg = m.get("diagnostics") or {}
    dtab = pd.DataFrame([{"통계량": v["stat"], "p값": v["p"]} for v in dg.values()],
                        index=pd.Index([v["name"] for v in dg.values()], name="검정")) if dg else None
    stat_line = (f"R² {short(st.get('r_squared'))} · 조정 R² {short(st.get('adj_r_squared'))} · 회귀 표준오차 "
                 f"{short(st.get('se_regression'))} · DW {short(st.get('durbin_watson'))} · AIC {short(st.get('aic'))} · "
                 f"BIC {short(st.get('bic'))}")
    sections = [("계수", md.table(ctab.rename(columns={"coef": "계수", "se": "표준오차", "t": "t값", "p": "p값"}))
                 + "\n\n" + stat_line),
                ("진단", md.table(dtab) if dtab is not None else "없음")]
    ct = criteria_text(m.get("criteria"))
    if ct:
        sections.append(("판단 기준", ct))
    if m.get("sim"):
        sm = m["sim"]
        sections.append(("단독 모의", f"{sm['start']}~{sm['end']} 동태 모의(다른 변수는 실측) — {m['target']} RMSPE "
                                    f"{pct(sm['rmspe'])}\n\n" + md.vega_line("series.csv", "period",
                                                                            [m["target"], f"{m['target']}_sim"],
                                                                            f"{m['target']} 실측 · 단독 모의")))
    sections.append(("실측과 적합", md.vega_line("series.csv", "period", ["actual", "fitted"], f"{m['dependent']}")))
    sections.append(("알아서 한 것", md.bullets(m.get("implicit") or [])))
    head = [("식", m["text"]), ("부품", m.get("part")), ("추정법", m.get("method_label") or METHOD_KO.get(m["method"], m["method"])),
            ("표본", f"{m['sample'][0]}~{m['sample'][1]} (관측치 {m['n']})"), ("자료", data_label(m["data"])),
            ("만든 때", m.get("created") or now_iso()), ("누가", WHO_KO.get(m["who"], m["who"])), ("명령", m["command"]),
            ("equion", m["equion"])]
    if m["expr"] != m["text"]:
        head.insert(1, ("펼친 식", m["expr"]))
    if m.get("cov"):
        head.insert(3, ("계수 공분산", m["cov"].get("label") or m["cov"].get("type")))
    return md.card(f"추정 {m['id']}", head, sections)


# ---------------------------------------------------------------------------
# 채택
# ---------------------------------------------------------------------------
def replace_line(old: str, text: str) -> str:
    """블록 파일의 한 줄을 새 식으로 — 들여쓰기와 줄 끝 설명(`# …`)은 그대로, 설명의 자리도 맞출 수 있으면 그대로."""
    body, hash_, comment = old.partition("#")
    indent = old[:len(old) - len(old.lstrip())]
    new = indent + text
    if not hash_:
        return new
    gap = len(body) - len(new)
    return new + (" " * gap if gap >= 1 else "   ") + "#" + comment


def read_text(root: str, rel: str) -> Optional[str]:
    """정의 파일의 글자(없으면 None) — 줄바꿈은 LF로 읽는다(쓸 때 바뀜 기록이 지금 파일의 줄바꿈을 따른다).
    다른 프로그램이 쥐고 있어 읽을 수 없으면 FileBusy(그 파일 이름과 함께)."""
    data = read_bytes(os.path.join(root, rel), root)
    return None if data is None else data.decode("utf-8-sig").replace("\r\n", "\n")


def read_adopted(root: str) -> Dict[str, str]:
    """채택표 EQUATIONS/adopted.toml — {부품: est:기록}."""
    import tomllib
    text = read_text(root, ADOPTED)
    if text is None:
        return {}
    raw = tomllib.loads(text)
    return {str(k): str(v) for k, v in raw.items() if isinstance(v, str)}


def _adopted_doc(root: str):
    """채택표를 고치려고 읽은 tomlkit 문서(없으면 머리 주석만 있는 새 문서)."""
    import tomlkit
    text = read_text(root, ADOPTED)
    if text is not None:
        return tomlkit.parse(text)
    doc = tomlkit.document()
    doc.add(tomlkit.comment("채택표 — 식(부품)마다 채택한 추정 기록. 모형은 이 계수로 푼다(equion adopt가 고친다)"))
    return doc


@dataclass
class AdoptResult:
    """채택 결과 — 부품·기록·바뀐 파일·바뀜 기록."""

    part: str
    record: str
    previous: Optional[str]
    line_changed: bool
    change: Optional[str]
    files: List[str] = field(default_factory=list)

    def text(self) -> str:
        """명령줄에 보이는 짧은 글."""
        L = [f"[adopt] {self.part} ← {self.record}" + (f" (전: {self.previous})" if self.previous else "")]
        L.append("  블록 파일  " + ("그 줄을 이 식으로 바꿈" if self.line_changed else "그대로(같은 식)"))
        L.append(f"  채택표   {ADOPTED}")
        if self.change:
            L.append(f"  바뀜 기록  {self.change} ({', '.join(self.files)})")
        L.append("  다음   모형을 풀면 이 기록의 계수를 쓴다(다시 추정하지 않음)")
        return "\n".join(L)

    def to_dict(self) -> dict:
        """명령줄 --json과 같은 사전."""
        return {"part": self.part, "record": self.record, "previous": self.previous, "line_changed": self.line_changed,
                "change": self.change, "files": self.files}


@locked
def adopt(p, rid: str, part: str = None, who: str = None, command: str = None) -> AdoptResult:
    """추정 기록을 그 부품의 채택 계수로 — 블록 파일의 줄을 그 식으로 바꾸고(다르면) 채택표를 고친다. 바뀜 기록에 남는다.

    프로젝트 잠금 안에서 블록 파일·채택표를 읽어 고쳐 쓴다 — 채택 여럿을 한꺼번에 해도 하나도 사라지지 않는다. 블록 파일과 채택표는
    한 묶음으로 바뀐다(하나를 바꾸지 못하면 둘 다 그대로 — FileBusy)."""
    import tomlkit
    store = store_of(p)
    rec = store.get(rid, "est")
    pid = part or rec.meta.get("part")
    if not pid:
        raise ProjectError(f"{rid}가 어느 부품의 후보인지 모릅니다 — --part 블록:목표")
    pt = p.part(pid)
    if pt.kind != "equation":
        raise ProjectError(f"{pt.id}는 항등식입니다 — 채택할 수 없습니다")
    if pt.target != rec.meta["target"]:
        raise ProjectError(f"{pt.id}의 목표는 {pt.target}인데 {rid}의 목표는 {rec.meta['target']}입니다")
    new: Dict[str, str] = {}
    text = rec.meta["text"]
    changed = text != pt.text
    if changed:
        lines = (read_text(p.root, pt.file) or "").split("\n")
        lines[pt.line - 1] = replace_line(lines[pt.line - 1], text)
        new[pt.file] = "\n".join(lines)
    doc = _adopted_doc(p.root)
    prev = doc.get(pt.id)
    prev = str(prev) if prev is not None else None
    doc[pt.id] = rid
    new[ADOPTED] = tomlkit.dumps(doc)
    ch = history_of(p).write_files(new, _who(who), command or f"adopt {rid}",
                                   note=f"{pt.id} ← {rid}" + (f" (전: {prev})" if prev else ""))
    p._reset()
    return AdoptResult(pt.id, rid, prev, changed, ch.id if ch else None, sorted(ch.files) if ch else [])


# ---------------------------------------------------------------------------
# 다시 추정 — 채택한 식을 지금 자료로, 정책에 따라 새 계수 채택(D35)
# ---------------------------------------------------------------------------
POLICIES = ("never", "if_pass", "all")


@dataclass
class ReestResult:
    """`est --adopted` 결과 — 식마다 옛 기록·새 기록·기준·채택 여부와 계수 변화(`.rows`), 바뀜 기록(`.change`)."""

    model: str
    policy: str
    rows: List[dict]
    change: Optional[str]

    @property
    def adopted(self) -> List[str]:
        """새 계수를 채택한 부품."""
        return [r["part"] for r in self.rows if r["adopted"]]

    @property
    def flagged(self) -> List[str]:
        """기준을 통과하지 못했거나(걸러짐) 판단할 수 없어(검정 없음) 사람이 볼 부품."""
        return [r["part"] for r in self.rows if r["passed"] is False or r.get("untested")]

    def text(self) -> str:
        """명령줄에 보이는 짧은 글."""
        n = len(self.rows)
        bad = [r for r in self.rows if r["passed"] is False]
        unk = [r for r in self.rows if r["passed"] is not False and r.get("untested")]
        L = [f"[est --adopted] {self.model} · 정책 {self.policy}: 식 {n} — 새 계수 채택 {len(self.adopted)}"
             + (f" · 기준 미달 {len(bad)}" if bad else "") + (f" · 기준 판단 못 함 {len(unk)}" if unk else "")]
        for r in self.rows:
            if r.get("mismatch"):
                ch = "채택 기록의 식이 블록 파일과 다름(계수 변화를 견주지 않음)"
            else:
                ch = f"계수 최대 변화 {r['max_change_pct']:.2f}%" if r.get("max_change_pct") is not None else "옛 계수 없음"
            if r.get("as_adopted"):
                ch += f" · 채택 기록대로 {' · '.join(r['as_adopted'])}"
            if r["adopted"]:
                what = "채택"
            elif self.policy == "never":
                what = "기록만(정책 never)"
            elif r.get("mismatch"):
                what = "채택 안 함 — 채택 기록의 식이 블록 파일과 달라 모형은 블록 파일의 식을 지금 자료로 추정해 푼다"
            elif r["passed"] is False or r.get("untested"):
                what = ("옛 계수 유지" if r["old"] else "채택 안 함 — 옛 계수가 없어 모형은 이 자료로 추정한 계수로 푼다")
                if r["passed"] is not False:
                    what = "채택 안 함(사람이 볼 것) — " + what
            else:
                what = "채택 안 함"
            mark = "!" if (r["passed"] is False or r.get("untested")) else "✓"
            if r["passed"]:
                judged = "기준 통과"
            elif r["passed"] is False:
                judged = "기준 미달: " + " · ".join(r["reasons"])
            elif r.get("untested"):
                judged = "기준 판단 못 함: " + (r.get("note") or "검정 없음")
            else:
                judged = "기준 없음"
            L.append(f"  {mark} {r['part']:<12} {r['old'] or '—'} → {r['new']} · {ch} · {judged} · {what}")
        if self.change:
            L.append(f"  바뀜 기록  {self.change} (EQUATIONS/adopted.toml)")
        return "\n".join(L)

    def to_dict(self) -> dict:
        """명령줄 --json과 같은 사전."""
        return {"model": self.model, "policy": self.policy, "rows": self.rows, "change": self.change,
                "adopted": self.adopted, "flagged": self.flagged}


def _smpl_of_command(cmd) -> Optional[str]:
    """옛 추정 기록(표본 표기를 따로 적기 전)의 명령에서 --smpl 값."""
    import re
    import shlex
    try:
        toks = shlex.split(str(cmd or ""))
    except ValueError:
        toks = str(cmd or "").split()
    for k, t in enumerate(toks):
        if t == "--smpl" and k + 1 < len(toks):
            return toks[k + 1]
        m = re.match(r"^--smpl=(.+)$", t)
        if m:
            return m[1]
    return None


def adopted_settings(p, om: dict) -> (dict, List[str]):
    """채택 기록을 '그때와 같은 방법으로' 다시 추정할 설정 — ({run_est 인자}, [보이는 글]).

    표본: 채택 기록의 --smpl 표기 그대로(`1990Q1:last`처럼 끝이 last·last-N이면 지금 자료의 끝까지 늘어나고, 라벨로 못 박은 끝은 그대로).
    표기를 지금 자료로 풀 수 없으면 자료 전체로 하고 그렇다고 적는다. 계수 공분산(--cov)과 --method tsls도 그대로."""
    kw, shown = {}, []
    sm = om["smpl"] if "smpl" in om else _smpl_of_command(om.get("command"))
    if sm:
        try:
            p.span(sm)
            kw["smpl"] = sm
            shown.append(f"표본 {sm}")
        except (ValueError, KeyError):
            shown.append(f"표본 {sm}을(를) 지금 자료로 풀 수 없어 자료 전체로")
    cv = om.get("cov") or {}
    if cv.get("type"):
        kw["cov"] = cv["type"]
        shown.append(f"공분산 {cv.get('label') or cv['type']}")
    if om.get("method") == "tsls":
        kw["method"] = "tsls"
    return kw, shown


def reestimate(p, name: str = None, policy: str = "never", who: str = None, command: str = None) -> ReestResult:
    """모형(또는 블록)의 추정식을 블록 파일의 글자 그대로 지금 자료로 다시 추정해 기록을 남기고, 정책에 따라 새 계수를 채택한다.

    정책: never(기록만) · if_pass(판단 기준을 통과한 식만 — 기준이 없으면 통과로 본다, 기준의 검정을 이 추정법이 계산하지 않아
    판단할 수 없으면 채택하지 않고 표시) · all. 채택은 채택표 한 번의 바뀜 기록으로.

    채택 기록이 있고 그 식이 블록 파일의 줄과 같으면 그 기록과 같은 방법(표본 표기·계수 공분산 — `adopted_settings`)으로 다시 추정하고
    계수 변화를 견준다. 채택 기록의 식이 블록 파일과 다르면(줄을 고친 뒤) 모형도 그 기록을 쓰지 않으므로 견주지 않고 그렇다고 적는다."""
    import tomlkit
    if policy not in POLICIES:
        raise ProjectError(f"--adopt {policy!r} — {' · '.join(POLICIES)}")
    history_of(p).scan()
    name = p._default(name)
    store = store_of(p)
    parts = [x for x in p.parts(name) if x.kind == "equation"]
    adopted = p.adopted
    rows = []
    for x in parts:
        old = adopted.get(x.id)
        om = None
        if old:
            try:
                om = store.get(old, "est").meta
            except RecordError:
                old = None
        mismatch = om is not None and om.get("expr") != x.expr
        kw, shown = adopted_settings(p, om) if om is not None and not mismatch else ({}, [])
        rec = run_est(p, x.id, who=who, command=command or f"est --adopted {name} --adopt {policy}", **kw)
        mc = None
        if om is not None and not mismatch:
            oc = pd.Series({c["name"]: c["coef"] for c in om["coefs"]}, dtype=float)
            nc = rec.coefs
            both = [k for k in nc.index if k in oc.index]
            if both:
                mc = float(np.max(np.abs((nc[both] - oc[both]) / np.where(oc[both] == 0, 1, np.abs(oc[both])))) * 100)
        passed = rec.passed
        cr = rec.meta.get("criteria")
        untested = (cr or {}).get("untested") or []
        take = policy == "all" or (policy == "if_pass" and (cr is None or passed is True))
        row = {"part": x.id, "old": old, "new": rec.id, "passed": passed,
               "reasons": (cr or {}).get("reasons", []), "adopted": bool(take), "max_change_pct": mc}
        if untested:
            row.update(untested=untested, note=cr.get("note"))
        if mismatch:
            row["mismatch"] = True
        if shown:
            row["as_adopted"] = shown
        rows.append(row)
    change = None
    chosen = [r for r in rows if r["adopted"]]
    if chosen:
        with project_lock(p.root):                   # 채택표는 잠금 안에서 다시 읽어 고친다(추정하는 사이 다른 채택이 있었어도)
            doc = _adopted_doc(p.root)
            for r in chosen:
                doc[r["part"]] = r["new"]
            by = command or f"est --adopted {name} --adopt {policy}"
            ch = history_of(p).write_files({ADOPTED: tomlkit.dumps(doc)}, _who(who), by,
                                           note=f"정책 {policy}가 채택: " + ", ".join(f"{r['part']} ← {r['new']}" for r in chosen))
        change = ch.id if ch else None
        p._reset()
    return ReestResult(name, policy, rows, change)


# ---------------------------------------------------------------------------
# 비교
# ---------------------------------------------------------------------------
@dataclass
class CompareResult:
    """후보 비교 표 — `.table`(DataFrame) · `.warnings` · `.text()` · `.to_dict()`."""

    kind: str
    table: pd.DataFrame
    warnings: List[str]

    def text(self) -> str:
        """명령줄에 보이는 짧은 글."""
        t = self.table.copy()
        for c in t.columns:
            if pd.api.types.is_float_dtype(t[c]):
                t[c] = t[c].map(pfmt if c.endswith(" p") else short)
        with pd.option_context("display.width", 250, "display.max_columns", 40, "display.max_colwidth", 48):
            body = t.to_string() if len(t) else "(없음)"
        n = len(self.table) if self.kind == "est" else len([c for c in self.table.columns if c != "차이"])
        L = [f"[compare] {KIND_KO.get(self.kind, self.kind)} 기록 {n}", body]
        L += [f"  ! {w}" for w in self.warnings]
        return "\n".join(L)

    def to_dict(self) -> dict:
        """명령줄 --json과 같은 사전."""
        t = self.table.reset_index().replace({np.nan: None})
        return {"kind": self.kind, "rows": t.to_dict(orient="records"), "warnings": self.warnings}

    def md(self) -> str:
        """md 표."""
        return md.table(self.table, digits=4) + ("\n\n" + md.bullets(self.warnings) if self.warnings else "") + "\n"


def compare(p, ids: List[str] = (), target: str = None, part: str = None) -> CompareResult:
    """기록 비교 — 추정 기록이면 식·표본·적합 통계·진단·기준·단독 모의 표, HS 기록이면 변수별 RMSPE 표."""
    store = store_of(p)
    ids = list(ids or [])
    if target or part:
        want_part = p.part(part).id if part else None
        for r in store.records("est"):
            m = r.meta
            if (target and m.get("target", "").lower() == target.lower()) or (want_part and m.get("part") == want_part):
                if r.id not in ids:
                    ids.append(r.id)
    if not ids:
        raise ProjectError("견줄 기록이 없습니다 — 기록 이름(est:… · hs:…)이나 --target·--part")
    recs = [store.get(i) for i in ids]
    kinds = {r.kind for r in recs}
    if len(kinds) > 1:
        raise ProjectError(f"같은 종류의 기록끼리 견줍니다(지금: {', '.join(sorted(kinds))})")
    kind = kinds.pop()
    warns = []
    if kind == "est":
        adopted = read_adopted(p.root)
        rows = {}
        for r in recs:
            m = r.meta
            st, dg = m["stats"], m.get("diagnostics") or {}
            cr = m.get("criteria")
            rows[r.id] = {"식": m["text"], "부품": m.get("part") or "", "채택": "★" if adopted.get(m.get("part") or "") == r.id else "",
                          "표본": f"{m['sample'][0]}~{m['sample'][1]}", "n": m["n"],
                          "R²adj": st.get("adj_r_squared"), "SE": st.get("se_regression"), "DW": st.get("durbin_watson"),
                          "AIC": st.get("aic"), "BIC": st.get("bic"),
                          **{f"{DIAG_LABEL[k]} p": (dg.get(k) or {}).get("p") for k in ("lm", "white", "jb", "reset")},
                          "기준": "" if cr is None else ("통과" if cr["pass"] else (
                              "판단 못 함: " + (cr.get("note") or "") if cr["pass"] is None else "걸러짐: " + " · ".join(cr["reasons"]))),
                          "단독 RMSPE%": (m.get("sim") or {}).get("rmspe")}
        tab = pd.DataFrame.from_dict(rows, orient="index")
        tab.index.name = "기록"
        tab = tab.dropna(axis=1, how="all")
        deps = {r.meta["dependent"] for r in recs}
        if len(deps) > 1:
            warns.append(f"종속변수가 달라({' · '.join(sorted(deps))}) R²·SE·AIC·BIC를 견줄 수 없습니다 — 단독 모의 RMSPE로")
        smp = {tuple(r.meta["sample"]) for r in recs}
        if len(smp) > 1:
            warns.append("표본이 달라 AIC·BIC를 그대로 견주기 어렵습니다")
        vin = {data_label(r.meta["data"]) for r in recs}
        if len(vin) > 1:
            warns.append(f"자료가 다릅니다: {' · '.join(sorted(vin))}")
        return CompareResult("est", tab, warns)
    if kind == "sim":                    # 전망 — 연간 증가율을 나란히(sim 기록에는 적합도 표 stats.csv가 없다)
        cols, order = {}, []
        for r in recs:
            row = {}
            for y, vals in (r.meta.get("annual") or {}).items():
                for v, g in (vals or {}).items():
                    key = f"{v} {y}"
                    row[key] = g
                    if key not in order:
                        order.append(key)
            cols[r.id] = row
        order.sort(key=lambda k: (k.rsplit(" ", 1)[0], k.rsplit(" ", 1)[1]))
        tab = pd.DataFrame(cols, index=order, dtype=float)
        tab.index.name = "연간 증가율%"
        if len(recs) == 2 and len(tab):
            tab["차이"] = tab[recs[1].id] - tab[recs[0].id]
        if not len(tab):
            warns.append("견줄 연간 증가율이 없습니다(전망 구간이 한 해를 다 채우지 않음)")
        for what, key in (("시나리오", "scenario"), ("모형", "model")):
            vals = {str(r.meta.get(key)) for r in recs}
            if len(vals) > 1:
                warns.append(f"{what}가 다릅니다: {' · '.join(sorted(vals))}")
        rng = {tuple(r.meta.get("range", [])) for r in recs}
        if len(rng) > 1:
            warns.append("구간이 다릅니다: " + " · ".join("~".join(x) for x in sorted(rng)))
        vin = {data_label(r.meta["data"]) for r in recs if r.meta.get("data")}
        if len(vin) > 1:
            warns.append(f"자료가 다릅니다: {' · '.join(sorted(vin))}")
        if len(recs) == 2:
            warns.append(f"차이를 자료·가정·식으로 나누려면: equion an split \"{recs[0].id} {recs[1].id}\"")
        return CompareResult("sim", tab, warns)
    if kind == "hs":
        cols = {}
        for r in recs:
            st = r.read_csv("stats.csv")
            cols[r.id] = st["RMSPE"] if "RMSPE" in st.columns else pd.Series(dtype=float)
        tab = pd.DataFrame(cols)
        tab.index.name = "RMSPE%"
        rng = {tuple(r.meta.get("range", [])) for r in recs}
        if len(rng) > 1:
            warns.append("구간이 다릅니다: " + " · ".join("~".join(x) for x in sorted(rng)))
        return CompareResult(kind, tab, warns)
    raise ProjectError(f"{kind} 기록은 견줄 수 없습니다")


# ---------------------------------------------------------------------------
# 과거 재현(HS) 기록
# ---------------------------------------------------------------------------
@dataclass
class HSRecord:
    """HS 기록 하나 — `.id`(hs:…) · `.result`(풀이 결과 SolveResult, 이번 계산일 때) · `.stats`(변수별 RMSPE…) ·
    `.vs`(전후 비교) · `.replay`(다시 돌린 결과와 원래 기록의 차이) · `.text()` · `.to_dict()`."""

    record: Record
    result: object = None

    @property
    def id(self) -> str:
        """기록 이름 hs:…"""
        return self.record.id

    @property
    def meta(self) -> dict:
        """record.json 내용."""
        return self.record.meta

    @property
    def stats(self) -> pd.DataFrame:
        """변수별 적합도(stats.csv)."""
        return self.record.read_csv("stats.csv")

    @property
    def solved(self) -> pd.DataFrame:
        """풀린 값(solved.csv — 행 = 기간)."""
        return self.record.read_csv("solved.csv")

    @property
    def start(self) -> str:
        """구간 시작."""
        return self.meta["range"][0]

    @property
    def end(self) -> str:
        """구간 끝."""
        return self.meta["range"][1]

    def counts(self) -> Dict[str, int]:
        """기간 상태 수 {'ok', 'partial', 'fallback', 'failed'}."""
        return dict(self.meta["counts"])

    def text(self) -> str:
        """명령줄에 보이는 짧은 글."""
        return hs_text(self.meta)

    def to_dict(self) -> dict:
        """명령줄 --json과 같은 사전."""
        d = dict(self.meta)
        d["path"] = self.record.path
        return d

    def __repr__(self):
        return f"<HS 기록 {self.id}: {self.meta['model']} {self.start}~{self.end}>"


def hs_text(m: dict) -> str:
    c = m["counts"]
    L = [f"[{m['id']}] {m['model']} {m['mode']} {m['range'][0]}~{m['range'][1]} · 정상 {c['ok']} · "
         f"일부식 제외 {c['partial']} · 실패대체 {c['fallback']} · 실패 {c['failed']}"]
    rm = m.get("rmspe") or {}
    if rm:
        items = list(rm.items())
        L.append("  RMSPE  " + " · ".join(f"{k} {pct(v)}" for k, v in items[:10]) + (" …" if len(items) > 10 else ""))
    if m.get("vs"):
        vs = m["vs"]
        ch = [f"{k} {pct(a)} → {pct(b)}" for k, (a, b) in vs["rmspe"].items()
              if a is not None and b is not None and abs(a - b) > 5e-4]
        L.append(f"  비교   vs {vs['id']} — " + (" · ".join(ch[:8]) + (" …" if len(ch) > 8 else "") if ch else "RMSPE 그대로")
                 + (" (나머지 그대로)" if ch and len(ch) < len(vs["rmspe"]) else ""))
    if m.get("swaps"):
        L.append("  바꿔 끼움  " + " · ".join(f"{k} ← {v}" for k, v in m["swaps"].items()) + " (파일은 그대로)")
    if m.get("replay"):
        r = m["replay"]
        L.append(f"  다시 돌림  {r['of']} — " + ("같은 결과" if r["same"] else "다름") + f"(최대 |차이| {r['max_abs_diff']:.3g})")
    if m.get("implicit"):
        L.append("  알아서 한 것  " + " · ".join(m["implicit"]))
    L.append(f"  기록   {m['id']} ({m['path']}/)")
    return "\n".join(L)


def _resolve_swap(p, swap: Optional[Dict[str, str]]) -> (Dict[str, str], Dict[str, str]):
    """{부품: est:기록 또는 식} → ({부품: 식}, {부품: 표시}). 기록이면 그 계수를 쓰도록 프로젝트에 알린다."""
    if not swap:
        return {}, {}
    store = store_of(p)
    texts, shown = {}, {}
    for pid, v in swap.items():
        pt = p.part(pid)
        v = str(v).strip()
        if v.startswith("est:"):
            rec = store.get(v, "est")
            if rec.meta["target"] != pt.target:
                raise ProjectError(f"바꿔 끼우기 {pt.id}: {v}의 목표는 {rec.meta['target']}입니다 — {pt.target}이어야 합니다")
            texts[pt.id] = rec.meta["expr"]
            p._swap_saved[(pt.id, rec.meta["expr"])] = (v, rec.meta["equation"])
            shown[pt.id] = v
        else:
            texts[pt.id] = v
            shown[pt.id] = f'"{v}"'
    return texts, shown


def _assembly(p, name, model_obj, parts, rng, mode, opts, swaps) -> dict:
    eqs = {}
    for e in model_obj.equations:
        eqs[e.name] = e
    out = []
    for x in parts:
        d = {"id": x.id, "kind": x.kind, "text": x.text, "expr": x.expr, "file": x.file, "line": x.line}
        if x.kind != "identity":
            key = p._part_key(x)
            obj = p._est.get(key)
            d["source"] = p._sources.get(key, "estimated")
            d["saved"] = obj.eq.to_saved() if obj is not None else None
        out.append(d)
    return {"format": "equion-assembly", "format_version": 1, "model": name, "range": list(rng), "mode": mode,
            "options": opts, "data": data_spec(p), "parts": out, "swaps": swaps, "files": definition_hashes(p),
            "equion": _version()}


def _write_hs(p, name_model, res, asm, wf, implicit, vs, replay, who, command, as_name) -> HSRecord:
    store = store_of(p)
    if as_name:
        store.check_new("hs", as_name)
    st = res.statistics()
    keep = [c for c in ("RMSPE", "MAE_pct", "MAE", "mean_error", "n_samples") if c in st.columns]
    st = st[keep]
    st.index.name = "변수"
    vals = res.values.copy()
    vals.index = pd.Index(_labels(wf, vals.index), name="period")
    status = res.status()
    status.index = pd.Index([str(i) for i in status.index], name="period")
    c = res.counts()
    rm = {k: float(v) for k, v in st["RMSPE"].items()} if "RMSPE" in st.columns else {}
    vs_info = None
    if vs:
        other = store.get(vs, "hs")
        ost = other.read_csv("stats.csv")
        both = {}
        for v in sorted(set(rm) | set(ost.index), key=lambda k: list(rm).index(k) if k in rm else 999):
            a = float(ost.loc[v, "RMSPE"]) if v in ost.index else None
            b = rm.get(v)
            both[v] = (a, b)
        vs_info = {"id": other.id, "range": other.meta.get("range"), "rmspe": both}
    act = wf.data[[v for v in vals.columns if v in wf.data.columns]].copy()
    act.index = pd.Index(_labels(wf, act.index), name="period")
    # 해와 실측을 나란히 — 열을 하나씩 더하지 않고 한 번에(변수가 많으면 pandas가 조각난 표라며 경고를 쏟는다)
    both = pd.concat([vals, pd.DataFrame({f"{v}_실측": act[v].reindex(vals.index).to_numpy() for v in act.columns},
                                         index=vals.index)], axis=1)
    with store.naming("hs", as_name, "hs") as name:
        rel = f"work/hs/{name}"
        meta = {"who": _who(who), "command": command, "project": p.name, "equion": _version(), "target": name_model,
                "model": name_model, "range": asm["range"], "mode": asm["mode"], "counts": c, "rmspe": rm,
                "swaps": asm.get("swaps") or {}, "implicit": implicit, "data": asm["data"], "vs": vs_info,
                "replay": replay, "path": rel, "id": f"hs:{name}"}
        summary = _hs_md(meta, st, vs_info)
        rec = store.write("hs", name, meta, {"assembly.json": asm, "stats.csv": st, "solved.csv": vals,
                                             "status.csv": status, "series.csv": both}, summary,
                          log={"metric": " · ".join(f"{k} {pct(v)}" for k, v in list(rm.items())[:3]),
                               "counts": c})
        return HSRecord(rec, res)


def _hs_md(m, st, vs) -> str:
    c = m["counts"]
    sections = [("변수별 적합도", md.table(st)),
                ("풀이 상태", f"정상 {c['ok']} · 일부식 제외 {c['partial']} · 실패대체 {c['fallback']} · 실패 {c['failed']}")]
    if vs:
        t = pd.DataFrame({vs["id"]: {k: a for k, (a, b) in vs["rmspe"].items()},
                          m["id"]: {k: b for k, (a, b) in vs["rmspe"].items()}})
        t["차이"] = t[m["id"]] - t[vs["id"]]
        t.index.name = "RMSPE%"
        sections.append((f"전후 비교 — vs {vs['id']}", md.table(t)))
    if m.get("swaps"):
        sections.append(("바꿔 끼움(파일은 그대로)", md.bullets([f"{k} ← {v}" for k, v in m["swaps"].items()])))
    if m.get("replay"):
        r = m["replay"]
        sections.append(("다시 돌림", f"{r['of']}의 조립 명세로 그대로 — " + ("같은 결과" if r["same"] else "다름")
                         + f"(최대 |차이| {r['max_abs_diff']:.3g})"))
    top = list((m.get("rmspe") or {}).keys())[:3]
    if top:
        charts = [md.vega_line("series.csv", "period", [v, f"{v}_실측"], f"{v} — 해 · 실측", height=160) for v in top]
        sections.append(("해와 실측", "\n\n".join(charts)))
    sections.append(("알아서 한 것", md.bullets(m.get("implicit") or [])))
    head = [("모형", m["model"]), ("구간", f"{m['range'][0]}~{m['range'][1]} · {m['mode']}"), ("자료", data_label(m["data"])),
            ("만든 때", m.get("created") or now_iso()), ("누가", WHO_KO.get(m["who"], m["who"])), ("명령", m["command"]),
            ("equion", m["equion"]), ("조립 명세", "assembly.json — 식 글자·계수·자료·정의 파일 해시(--replay로 그대로 다시)")]
    return md.card(f"과거 재현 {m['id']}", head, sections)


def _status_implicit(res) -> List[str]:
    out = []
    df = res.status()
    if not len(df) or "status" not in df.columns:
        return out
    fb = [str(i) for i, v in df["status"].items() if v == "fallback"]
    if fb:
        gaps = {}
        try:                                    # 실패 대체 기간에 대신 쓸 실측이 없던 값(전망 구간 등) — 빈 값으로 남는다
            vals = res.values
            if len(vals) == len(df):
                pos = [k for k, v in enumerate(df["status"]) if v == "fallback"]
                gaps = {str(c): int(n) for c, n in vals.iloc[pos].isna().sum().items() if n}
        except (AttributeError, KeyError, TypeError, ValueError):
            gaps = {}
        why = ""                                # 엔진이 해를 확인하다 찾은 까닭(식이 서로 종속 · 해가 없어 발산 — D66)
        if "message" in df.columns:
            msgs = [str(m) for m, v in zip(df["message"], df["status"]) if v == "fallback" and isinstance(m, str)]
            hit = next((m for m in msgs if any(w in m for w in ("서로 종속", "특이", "발산"))), "")
            if hit:
                why = " — " + hit.split(" (시도:")[0][:160]
        if gaps:
            out.append(f"수렴하지 않은 기간 {len(fb)}기({fb[0]}~{fb[-1]}) — 실측이 있는 값은 실측으로 대체, 실측이 없어 빈 값: "
                       + " · ".join(f"{c} {n}기" for c, n in gaps.items()) + why)
        else:
            out.append(f"수렴하지 않아 실측 대체 {len(fb)}기({fb[0]}~{fb[-1]}){why}")
    pa = df[df["status"] == "partial"]
    if len(pa):
        ex = pa["excluded"].iloc[0] if "excluded" in pa.columns else ""
        out.append(f"입력 결측으로 식 제외 {len(pa)}기({pa.index[0]}~{pa.index[-1]}{' — ' + str(ex)[:60] if ex else ''})")
    fl = [str(i) for i, v in df["status"].items() if v == "failed"]
    if fl:
        out.append(f"실패 {len(fl)}기({fl[0]}~{fl[-1]})")
    return out


def run_hs(p, name: str = None, start=None, end=None, mode: str = None, swap: Dict[str, str] = None, vs: str = None,
           as_name: str = None, who: str = None, command: str = None, **opts) -> HSRecord:
    """과거 재현을 풀고 기록을 남긴다 — 조립 명세(assembly.json)에 그때의 식 글자·계수·자료·정의 파일 해시를 통째로."""
    history_of(p).scan()
    name = p._default(name)
    texts, shown = _resolve_swap(p, swap)
    n0 = len(p.notes)
    m = p.model(name, swap=texts or None)
    rep = p.assemble(name, swap=texts or None)
    s, e = p._range(start, end)
    rng_spec = p.config.hs.get("range")
    mode = mode or p.config.hs.get("mode") or "dynamic"
    from .sim import lead_options, quiet_lead_warning     # 선행변수: 기본은 실측 선행 값, --mce·[hs] mce면 모형 일관 기대
    given = opts.pop("mce", None)
    if given is True and opts.get("mce_method"):
        given = opts.pop("mce_method")
    lead_opts, lead_notes = lead_options(p, m, "hs", given, mode)
    opts = {**opts, **lead_opts}
    with quiet_lead_warning():
        res = m.solve(s, e, mode=mode, **opts)
    implicit = list(p.notes[n0:]) + lead_notes
    if rng_spec and start is None and end is None:
        implicit.insert(0, f"구간 [hs] range = {rng_spec} → {res.start}~{res.end}")
    if shown:
        implicit.append("바꿔 끼움: " + " · ".join(f"{k} ← {v}" for k, v in shown.items()))
    implicit += _status_implicit(res)
    asm = _assembly(p, name, m, rep.parts, (res.start, res.end), mode, _jsonable_opts(opts), shown)
    return _write_hs(p, name, res, asm, p.workfile, implicit, vs, None, who, command or f"hs {name}", as_name)


def _jsonable_opts(opts) -> dict:
    out = {}
    for k, v in opts.items():
        if isinstance(v, (str, int, float, bool)) or v is None:
            out[k] = v
        else:
            raise ProjectError(f"기록에 남길 수 없는 선택지 {k}={v!r} — 글자·수만")
    return out


def replay_workfile(p, ds: dict, tag: str = "replay"):
    """기록의 자료 명세(data spec) → 그때의 자료로 연 워크파일. 회차는 내용 해시, 자료 파일은 파일 해시가 같아야 한다."""
    from ..workfile.workfile import wfopen
    if ds["kind"] == "vintage":
        from .vintage import vintage_path
        vp = vintage_path(p.root, ds["id"])
        try:
            with open(os.path.join(vp, "build.json"), encoding="utf-8") as f:
                b = json.load(f)
        except OSError:
            raise ProjectError(f"자료 회차 {ds['id']}가 없습니다 — 그때의 자료로 풀 수 없습니다") from None
        if ds.get("content_sha256") and b.get("content_sha256") != ds["content_sha256"]:
            raise ProjectError(f"자료 회차 {ds['id']}의 내용이 기록과 다릅니다(내용 해시) — 그대로 다시 돌릴 수 없습니다")
        return quiet(wfopen, os.path.join(vp, "series.csv"), freq=ds.get("freq"), name=f"{p.name}_{tag}")
    from ..data.source import file_sha256
    path = os.path.join(p.root, ds["file"])
    if not os.path.isfile(path) or file_sha256(path) != ds.get("sha256"):
        raise ProjectError(f"자료 파일 {ds['file']}이 기록 때와 다릅니다(해시) — 그대로 다시 돌릴 수 없습니다")
    return quiet(wfopen, path, name=f"{p.name}_{tag}")


def replay_model(wf, asm: dict, name: str = "replay"):
    """조립 명세(assembly.json)의 식 글자·계수로 모형을 만든다(지금 파일과 무관)."""
    from ..estimation.equation import Equation
    from ..workfile.objects import EquationObject
    m = wf.model(name)
    for x in asm["parts"]:
        if x["kind"] == "identity":
            m.append(x["expr"])
            continue
        if not x.get("saved"):
            raise ProjectError(f"{x['id']}: 기록에 계수가 없습니다 — 다시 돌릴 수 없습니다")
        eq = quiet(Equation.restore, x["saved"], wf._data)
        eq.wt = wf._wt
        obj = EquationObject(wf, "r_" + x["id"].replace(":", "_"))
        wf._register(obj)
        obj._adopt(eq, x["expr"], loud=False)
        m.merge(obj)
    return m


def replay_hs(p, rid: str, vs: bool = True, as_name: str = None, who: str = None, command: str = None) -> HSRecord:
    """HS 기록을 그때 그대로 다시 — 조립 명세의 식 글자·계수·자료(회차·해시)·구간·방식으로 푼다(지금 파일과 무관).
    결과를 원래 기록의 풀린 값과 견주어 새 기록에 적는다."""
    store = store_of(p)
    rec = store.get(rid, "hs")
    asm = rec.read_json("assembly.json")
    ds = asm["data"]
    wf = replay_workfile(p, ds)
    m = replay_model(wf, asm)
    s, e = asm["range"]
    res = m.solve(s, e, mode=asm["mode"], **(asm.get("options") or {}))
    old = rec.read_csv("solved.csv")
    new = res.values.copy()
    new.index = pd.Index(_labels(wf, new.index), name="period")
    common = [c for c in old.columns if c in new.columns]
    a, b = old[common].to_numpy(dtype=float), new.loc[old.index, common].to_numpy(dtype=float)
    ok = np.isfinite(a) & np.isfinite(b)
    diff = float(np.max(np.abs(a[ok] - b[ok]))) if ok.any() else 0.0
    scale = float(np.max(np.abs(a[ok]))) if ok.any() else 1.0
    same = bool(diff <= 1e-9 * max(1.0, scale)) and np.array_equal(np.isfinite(a), np.isfinite(b))
    replay = {"of": rec.id, "same": same, "max_abs_diff": diff}
    implicit = [f"{rec.id}의 조립 명세 그대로(식 글자·계수·{data_label(ds)}·{s}~{e}·{asm['mode']}) — 지금 파일과 무관"]
    implicit += _status_implicit(res)
    return _write_hs(p, asm["model"], res, asm, wf, implicit, rec.id if vs else None, replay, who,
                     command or f"hs --replay {rid}", as_name)
