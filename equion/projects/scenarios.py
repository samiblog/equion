"""시나리오 정의 쓰기 (`SCENARIOS/*.toml`, D55) — `equion scenario list · show · define · remove`.

    # SCENARIOS/oil20.toml
    desc = "유가 20% 상승"
    base = "base"                 # 가정 세트 ASSUMPTIONS/base.csv
    [[shock]]
    var = "POIL"
    from = "start"                # 라벨 또는 start · end · start+N · end-N(전망 구간 기준) — to가 없으면 end까지
    pct = 20                      # 또는 value = 수준만큼

명령줄의 충격 한 줄은 `변수=크기[%][@처음[:끝]]` — `POIL=+20%`(끝까지) · `R=+0.5@start:start+3` · `WY=-2%@2026Q1:2026Q4`.
식 보정은 `블록:목표=값[@처음[:끝]]`. 읽기(풀이)는 `sim.load_scenario` — 같은 검사(`check_raw`)를 쓴다.
쓰기는 준 것만 바꾸고(빈 글은 그 키를 지움) 주석은 그대로 두며(tomlkit), 쓰기 전에 새 내용 전체를 검사한다.
"""
from __future__ import annotations

import math
import os
import re
import tomllib
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from .config import NAME_RE, ProjectError

FOLDER = "SCENARIOS"
KEYS = ("desc", "base", "addfactors", "model", "shock", "addfactor")
REL = re.compile(r"^(start|end)\s*(?:([+-])\s*(\d+))?$", re.I)
_NUM = r"([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)"
_WHEN = r"(?:\s*@\s*([^:\s]+)(?:\s*:\s*([^:\s]+))?)?"
SHOCK_RE = re.compile(rf"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*{_NUM}\s*(%)?{_WHEN}\s*$")
AF_RE = re.compile(rf"^\s*([^\s:=]+:[^\s:=]+)\s*=\s*{_NUM}{_WHEN}\s*$")


@dataclass
class ScenarioChange:
    """시나리오 쓰기·지우기 결과 — `.name` · `.file` · `.new` · `.removed` · `.change`(바뀜 기록) · `.shocks` · `.addfactor`."""

    name: str
    file: str
    new: bool = False
    removed: bool = False
    change: Optional[str] = None
    shocks: int = 0
    addfactor: int = 0
    warnings: List[str] = field(default_factory=list)

    def text(self) -> str:
        """명령줄에 보이는 짧은 글."""
        if self.removed:
            head = f"[scenario remove] {self.file} — 지웠습니다"
        else:
            head = f"[scenario define] {self.file}" + (" — 새 시나리오" if self.new else (" — 고침" if self.change else " — 바뀐 것이 없습니다"))
            head += f"\n  충격 {self.shocks} · 식 보정 {self.addfactor}"
        return head + "".join(f"\n  ! {w}" for w in self.warnings) + (f"\n  바뀜 기록  {self.change}" if self.change else "") + (
            f"\n  다음   equion sim {self.name}" if not self.removed else "")

    def to_dict(self) -> dict:
        """명령줄 --json과 같은 사전."""
        return {"name": self.name, "file": self.file, "new": self.new, "removed": self.removed, "change": self.change,
                "shocks": self.shocks, "addfactor": self.addfactor, "warnings": list(self.warnings)}


def parse_shock(text: str) -> dict:
    """`POIL=+20%@start:end` → {var, pct 또는 value, from, to}. 기간을 빼면 start부터 end까지."""
    m = SHOCK_RE.match(str(text))
    if not m:
        raise ProjectError(f"충격 {text!r} — 변수=크기[%][@처음[:끝]] 꼴(예: POIL=+20% · R=+0.5@start:start+3)")
    size = float(m[2])
    if not math.isfinite(size):
        raise ProjectError(f"충격 {text!r} — 크기가 유한한 수가 아닙니다")
    out = {"var": m[1], ("pct" if m[3] else "value"): size, "from": m[4] or "start", "to": m[5] or "end"}
    return out


def parse_addfactor(text: str) -> dict:
    """`demand:CN=-0.2@start:start+3` → {eq, value, from, to}."""
    m = AF_RE.match(str(text))
    if not m:
        raise ProjectError(f"식 보정 {text!r} — 블록:목표=값[@처음[:끝]] 꼴(예: demand:CN=-0.2@start:start+3)")
    value = float(m[2])
    if not math.isfinite(value):
        raise ProjectError(f"식 보정 {text!r} — 값이 유한한 수가 아닙니다")
    return {"eq": m[1], "value": value, "from": m[3] or "start", "to": m[4] or "end"}


def shock_word(s: dict) -> str:
    """충격 하나 → 명령줄의 한 낱말(parse_shock의 거꾸로)."""
    pct = "pct" in s
    v = s.get("pct", s.get("value"))
    num = f"{float(v):+g}"
    when = "" if (s.get("from", "start"), s.get("to", "end")) == ("start", "end") else f"@{s.get('from', 'start')}:{s.get('to', 'end')}"
    return f"{s['var']}={num}{'%' if pct else ''}{when}"


def addfactor_word(a: dict) -> str:
    """식 보정 하나 → 명령줄의 한 낱말."""
    when = "" if (a.get("from", "start"), a.get("to", "end")) == ("start", "end") else f"@{a.get('from', 'start')}:{a.get('to', 'end')}"
    return f"{a['eq']}={float(a['value']):+g}{when}"


def _when_ok(token, freq: Optional[str]) -> bool:
    if REL.match(str(token).strip()):
        return True
    if freq is None:
        return True
    from ..data.periods import parse_period
    try:
        parse_period(str(token).strip(), freq)
        return True
    except Exception:
        return False


def check_raw(raw: dict, rel: str, known=None, parts=None, assumptions=None, addfactor_sets=None, models=None,
              freq: Optional[str] = None) -> List[str]:
    """시나리오 파일 내용의 문제들(빈 목록이면 좋다). 뒤의 이름 목록을 주면 변수·식·가정 세트·보정항·모형이 있는지도 본다."""
    problems: List[str] = []
    for k in raw:
        if k not in KEYS:
            problems.append(f"{rel}: 알 수 없는 키 {k} — desc · base · addfactors · model · [[shock]] · [[addfactor]]")
    have = {str(x).upper() for x in known} if known is not None else None
    for k, s in enumerate(raw.get("shock") or [], 1):
        if not isinstance(s, dict) or not s.get("var") or ("pct" in s) == ("value" in s):
            problems.append(f"{rel} [[shock]] {k}번째: var와 pct 또는 value(둘 중 하나)가 있어야 합니다")
            continue
        val = s.get("pct", s.get("value"))
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            problems.append(f"{rel} [[shock]] {k}번째: 크기는 숫자 — {val!r}")
        if have is not None and str(s["var"]).upper() not in have:
            problems.append(f"{rel} [[shock]] {k}번째: 자료에 없는 변수 {s['var']}")
        for key in ("from", "to"):
            if key in s and not _when_ok(s[key], freq):
                problems.append(f"{rel} [[shock]] {k}번째: {key} = {s[key]!r} — 기간 라벨 또는 start · end · start+N · end-N")
    for k, a in enumerate(raw.get("addfactor") or [], 1):
        if not isinstance(a, dict) or not a.get("eq") or "value" not in a:
            problems.append(f"{rel} [[addfactor]] {k}번째: eq(블록:목표)와 value가 있어야 합니다")
            continue
        val = a.get("value")
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            problems.append(f"{rel} [[addfactor]] {k}번째: value는 숫자 — {val!r}")
        if parts is not None and a["eq"] not in parts:
            problems.append(f"{rel} [[addfactor]] {k}번째: 없는 식 {a['eq']}")
        for key in ("from", "to"):
            if key in a and not _when_ok(a[key], freq):
                problems.append(f"{rel} [[addfactor]] {k}번째: {key} = {a[key]!r} — 기간 라벨 또는 start · end · start+N · end-N")
    if assumptions is not None and raw.get("base") and raw["base"] not in assumptions:
        problems.append(f"{rel}: base = {raw['base']!r} — 없는 가정 세트(ASSUMPTIONS/{raw['base']}.csv; 있는 것: {', '.join(assumptions) or '없음'})")
    if addfactor_sets is not None and raw.get("addfactors") and raw["addfactors"] not in addfactor_sets:
        problems.append(f"{rel}: addfactors = {raw['addfactors']!r} — 없는 보정항(ADDFACTORS/{raw['addfactors']}.toml)")
    if models is not None and raw.get("model") and raw["model"] not in models:
        problems.append(f"{rel}: model = {raw['model']!r} — 없는 모형(있는 것: {', '.join(models)})")
    return problems


def _names(root: str, folder: str, ext: str) -> List[str]:
    try:
        return sorted(os.path.splitext(f)[0] for f in os.listdir(os.path.join(root, folder)) if f.lower().endswith(ext))
    except OSError:
        return []


def check_model(p, raw: dict, rel: str) -> Tuple[List[str], List[str]]:
    """시나리오를 그 모형(시나리오의 model → [forecast] model → [hs] model)과 전망 구간([forecast] range, 없으면 next:8)에 대어 본다
    — (문제, 알림). 문제: 항등식에 식 보정 · 항등식이 정하는 내생변수에 충격 · 기간이 거꾸로이거나 전망 구간 밖(효과 없음).
    알림: 추정식의 내생변수에 준 충격(그 식의 보정항으로 들어간다) · 기간 일부가 전망 구간 밖(잘림) · 그 모형에 없는 식의 보정."""
    from .sim import _when
    from ..data.periods import parse_period
    problems: List[str] = []
    warns: List[str] = []
    by_id = {x.id.lower(): x for x in p.parts()}
    for k, a in enumerate(raw.get("addfactor") or [], 1):
        pt = by_id.get(str(a.get("eq", "")).lower()) if isinstance(a, dict) else None
        if pt is not None and pt.kind == "identity":
            problems.append(f"{rel} [[addfactor]] {k}번째: {pt.id}는 항등식입니다 — 식 보정(보정항)은 추정식에만 붙입니다"
                            "(항등식의 오른쪽 외생변수에 충격을 주거나 추정식을 보정하세요)")
    fc = p.config.forecast or {}
    try:
        mname = raw.get("model") or fc.get("model") or p._default(None)
        rep = p.assemble(mname)
    except (KeyError, ValueError):
        return problems, warns
    if not rep.ok:
        return problems, warns
    ident = {x.target.upper(): x.id for x in rep.parts if x.kind == "identity"}
    eqs = {x.target.upper(): x.id for x in rep.parts if x.kind == "equation"}
    eq_ids = {x.id.lower() for x in rep.parts if x.kind == "equation"}
    try:
        F = p.config.freq or p.workfile.freq
        s, e = p.span(fc.get("range") or "next:8")
    except (KeyError, ValueError):
        s = e = None

    def when(what, item, k):
        if s is None:
            return
        try:
            a_, b_ = _when(item.get("from", "start"), s, e, F), _when(item.get("to", "end"), s, e, F, end=True)
            pa, pb, ps, pe = (parse_period(x, F) for x in (a_, b_, s, e))
        except (KeyError, ValueError, TypeError):
            return                                  # 꼴은 check_raw가 본다
        if pa > pb:
            problems.append(f"{rel} {what} {k}번째: 기간 {a_}~{b_} — 시작이 끝보다 뒤입니다")
        elif pb < ps or pa > pe:
            problems.append(f"{rel} {what} {k}번째: 기간 {a_}~{b_}이(가) 전망 구간 {s}~{e} 밖이라 효과가 없습니다 — "
                            "start · end · start+N · end-N이나 구간 안의 라벨로")
        elif pa < ps or pb > pe:
            warns.append(f"{what} {k}번째: 기간 {a_}~{b_} 가운데 지금 전망 구간 {s}~{e} 밖은 풀 때 뺍니다")
    for k, sh in enumerate(raw.get("shock") or [], 1):
        if not isinstance(sh, dict) or not sh.get("var"):
            continue
        v = str(sh["var"]).upper()
        if v in ident:
            problems.append(f"{rel} [[shock]] {k}번째: {sh['var']}는 모형 {mname}에서 항등식({ident[v]})이 정하는 내생변수라 충격을 "
                            "줄 식이 없습니다 — 그 항등식 오른쪽의 외생변수나 추정식에 주세요")
        elif v in eqs:
            warns.append(f"충격 {sh['var']}: 모형 {mname}의 내생변수({eqs[v]})라 그 식의 보정항(+{sh.get('pct', sh.get('value'))}, 식의 단위"
                         + (" — %가 아니라 그 수만큼" if "pct" in sh else "") + ")으로 들어갑니다 — 식을 보정하려면 "
                         + f"--addfactor {eqs[v]}=값")
        when("[[shock]]", sh, k)
    for k, a in enumerate(raw.get("addfactor") or [], 1):
        if not isinstance(a, dict) or not a.get("eq"):
            continue
        pt = by_id.get(str(a["eq"]).lower())
        if pt is not None and pt.kind == "equation" and pt.id.lower() not in eq_ids:
            warns.append(f"식 보정 {pt.id}: 모형 {mname}에 없는 식입니다 — 그 모형으로 풀면 오류(--model로 그 식이 있는 모형을)")
        when("[[addfactor]]", a, k)
    return problems, warns


def scenario_text(p, name: str, desc: str = None, base: str = None, addfactors: str = None, model: str = None,
                  shocks=None, addfactor=None, warnings: list = None) -> Tuple[str, bool, dict]:
    """시나리오를 더하거나 고친 **새 내용** — (글, 새 시나리오인지, 읽은 내용). 파일은 쓰지 않는다.
    준 것만 바꾼다: 글(desc·base·addfactors·model)은 빈 글이면 그 키를 지우고, shocks·addfactor는 목록을 주면 통째로 바꾼다(빈 목록은 지움).
    목록의 항목은 사전({var, pct|value, from, to}) 또는 명령줄 꼴의 글. 모형·전망 구간에 대어 본 문제(`check_model`)도 ProjectError이고,
    warnings(목록)를 주면 알림을 거기에 더한다."""
    import tomlkit
    if not NAME_RE.match(str(name)) or str(name) == "base":
        raise ProjectError(f"시나리오 이름 {name!r} — 영문으로 시작하고 영문·숫자·_만('base'는 기준선 이름이라 쓰지 않는다)")
    rel = f"{FOLDER}/{name}.toml"
    path = os.path.join(p.root, FOLDER, f"{name}.toml")
    new = not os.path.isfile(path)
    if new:
        doc = tomlkit.document()
    else:
        with open(path, encoding="utf-8") as f:
            doc = tomlkit.parse(f.read())
    for key, value in (("desc", desc), ("base", base), ("addfactors", addfactors), ("model", model)):
        if value is None:
            continue
        if str(value).strip() == "":
            if key in doc:
                del doc[key]
        else:
            doc[key] = str(value).strip()
    for key, items, parse in (("shock", shocks, parse_shock), ("addfactor", addfactor, parse_addfactor)):
        if items is None:
            continue
        rows = [parse(x) if isinstance(x, str) else dict(x) for x in items]
        if key in doc:
            del doc[key]
        if rows:
            aot = tomlkit.aot()
            for r in rows:
                t = tomlkit.table()
                for k2 in (("var",) if key == "shock" else ("eq",)) + ("from", "to"):
                    if k2 in r and not (k2 == "to" and str(r[k2]) == "end"):          # to가 없으면 end(전망 끝)까지
                        t[k2] = str(r[k2])
                num = lambda v: int(float(v)) if float(v).is_integer() else float(v)       # noqa: E731 — 20 이지 20.0 이 아니게
                if key == "shock":
                    if "pct" in r:
                        t["pct"] = num(r["pct"])
                    elif "value" in r:
                        t["value"] = num(r["value"])
                else:
                    t["value"] = num(r.get("value"))
                aot.append(t)
            doc[key] = aot
    text = tomlkit.dumps(doc)
    raw = tomllib.loads(text)
    problems = check_raw(raw, rel, known=[str(c) for c in p.workfile.data.columns], parts=[x.id for x in p.parts()],
                         assumptions=_names(p.root, "ASSUMPTIONS", ".csv"), addfactor_sets=_names(p.root, "ADDFACTORS", ".toml"),
                         models=list(p.config.models), freq=p.config.freq)
    if problems:
        raise ProjectError(problems)
    problems, warns = check_model(p, raw, rel)
    if problems:
        raise ProjectError(problems)
    if warnings is not None:
        warnings.extend(warns)
    return text, new, raw
