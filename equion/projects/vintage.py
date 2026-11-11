#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""자료 정의와 자료 회차 (D34) — 원자료 → 정의(`series.toml`·`derived.txt`) → 회차(`work/data/<회차>/`).

    원자료   DATA/raw/        받은 그대로 — 넣기만 한다(`equion data add`), 같은 이름이면 날짜를 붙여 나란히
    정의     DATA/series.toml [source.이름] 불러오기 틀 · [series.이름] 어느 열·변환·계절조정·단위·설명
             DATA/derived.txt 파생식(한 줄에 '이름 = 식', 위에서부터)
    회차     work/data/<회차>/ '자료 만들기'(`equion data build`)로만 생긴다 — 고치지 않는다
             series.csv · flags.csv(값의 종류) · meta.json · build.json(입력 해시·알아서 한 것) · summary.md

회차를 만들어도 지금 회차는 저절로 바뀌지 않는다 — '이 회차로 바꾸기'(`equion data use`)로 `equion.toml [data] vintage`를 고친다.
같은 원자료·정의로 다시 만들면 내용이 같아 새 회차를 만들지 않고 같은 회차를 알린다.
"""

import hashlib
import json
import os
import shutil
import tomllib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from ..data import transform as tr
from ..data.periods import PERIODS_PER_YEAR, format_period, normalize_freq, period_starts, to_period
from ..data.source import SourceSpec, SourceTable, file_sha256, read_source
from ..workfile.output import TableOutput, TextOutput, verbose
from .config import NAME_RE, VID_RE, ProjectError

FORMAT = "equion-data-vintage"
FORMAT_VERSION = 1
VINTAGE_DIR = os.path.join("work", "data")
RAW_DIR = os.path.join("DATA", "raw")
FLAG_KO = {"actual": "실측", "transformed": "변환", "filled": "채움", "derived": "파생", "missing": "결측"}
AGG = ("mean", "sum", "first", "last", "max", "min")
EXPAND = ("constant", "split", "linear", "denton")


# ---------------------------------------------------------------------------
# 정의 읽기
# ---------------------------------------------------------------------------
@dataclass
class SeriesSpec:
    name: str
    source: str
    column: str
    convert: Optional[str] = None
    denton: str = "sum"
    seas: Optional[dict] = None
    scale: Optional[float] = None
    fill: Optional[str] = None
    unit: str = ""
    desc: str = ""


@dataclass
class DataDefs:
    root: str
    freq: str
    series_file: str
    derived_file: Optional[str]
    sources: Dict[str, SourceSpec]
    series: Dict[str, SeriesSpec]
    derived: List[Tuple[int, str, str, str]]       # (줄, 이름, 식, 설명)
    texts: Dict[str, str]                         # 정의 파일 → sha256

    def used_sources(self) -> List[str]:
        out = []
        for s in self.series.values():
            if s.source not in out:
                out.append(s.source)
        return out


def _sha_text(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def load_defs(root: str, series_file: str, derived_file: Optional[str], freq: str,
              series_text: Optional[str] = None) -> DataDefs:
    """series.toml·derived.txt를 읽고 검사한다. 문제는 모아서 ProjectError.

    series_text를 주면 series.toml 파일 대신 그 글을 검사한다(고친 내용을 쓰기 전에 보는 데 — `define_text`).
    """
    from ..formula.parser import reserved_name_error
    problems: List[str] = []
    spath = os.path.join(root, series_file)
    try:
        if series_text is not None:
            raw = tomllib.loads(series_text)
        else:
            with open(spath, "rb") as f:
                raw = tomllib.load(f)
    except FileNotFoundError:
        raise ProjectError(f"자료 정의 파일이 없습니다: {series_file}") from None
    except tomllib.TOMLDecodeError as e:
        raise ProjectError(f"{series_file} 문법 오류: {e}") from None
    for k in raw:
        if k not in ("source", "series"):
            problems.append(f"{series_file}: 알 수 없는 표 [{k}] — [source.이름]·[series.이름]만")
    sources: Dict[str, SourceSpec] = {}
    for name, v in (raw.get("source") or {}).items():
        where = f"{series_file} [source.{name}]"
        if not NAME_RE.match(name):
            problems.append(f"{where}: 이름은 영문으로 시작하고 영문·숫자·_만")
            continue
        if not isinstance(v, dict) or not v.get("file"):
            problems.append(f"{where}: file이 없습니다")
            continue
        unknown = set(v) - {"file", "sheet", "header_row", "unit_row", "time_col", "time_axis", "missing", "thousands",
                            "freq", "desc", "inbox"}
        if unknown:
            problems.append(f"{where}: 알 수 없는 키 {', '.join(sorted(unknown))}")
        miss = v.get("missing", [])
        if isinstance(miss, str):
            miss = [miss]
        fp = os.path.normpath(os.path.join(root, v["file"]))
        if not os.path.isfile(fp):
            problems.append(f"{where}: 원자료 파일이 없습니다 — {v['file']}")
        try:
            sources[name] = SourceSpec(name=name, file=v["file"], path=fp, sheet=v.get("sheet"),
                                       header_row=int(v.get("header_row", 1)),
                                       unit_row=int(v["unit_row"]) if v.get("unit_row") else None,
                                       time_col=v.get("time_col"), time_axis=v.get("time_axis", "rows"),
                                       missing=[str(x) for x in miss], thousands=v.get("thousands"),
                                       freq=normalize_freq(v["freq"]) if v.get("freq") else None)
        except (TypeError, ValueError) as e:
            problems.append(f"{where}: {e}")
    series: Dict[str, SeriesSpec] = {}
    for name, v in (raw.get("series") or {}).items():
        where = f"{series_file} [series.{name}]"
        if not NAME_RE.match(name):
            problems.append(f"{where}: 이름은 영문으로 시작하고 영문·숫자·_만(한글은 desc로)")
            continue
        err = reserved_name_error(name)
        if err:
            problems.append(f"{where}: {err}")
            continue
        if not isinstance(v, dict) or not v.get("from"):
            problems.append(f"{where}: from = \"원자료이름:열\"이 없습니다")
            continue
        unknown = set(v) - {"from", "convert", "denton", "seas", "scale", "fill", "unit", "desc", "made_by"}
        if unknown:
            problems.append(f"{where}: 알 수 없는 키 {', '.join(sorted(unknown))}")
        src, _, col = str(v["from"]).partition(":")
        if not col:
            problems.append(f"{where}: from = {v['from']!r} — \"원자료이름:열\" 꼴")
            continue
        if src not in sources:
            problems.append(f"{where}: 없는 원자료 '{src}' (있는 원자료: {', '.join(sources) or '없음'})")
        conv = v.get("convert")
        if conv is not None and conv not in AGG + EXPAND:
            problems.append(f"{where}: convert = {conv!r} — {' · '.join(AGG + EXPAND)}")
        seas = v.get("seas")
        if isinstance(seas, str):
            seas = {"method": seas}
        if seas is not None:
            if not isinstance(seas, dict) or seas.get("method", "stl") not in ("stl", "classical") or \
                    seas.get("model", "additive") not in ("additive", "multiplicative"):
                problems.append(f"{where}: seas = \"stl\"·\"classical\" 또는 {{ method = …, model = \"additive\"·\"multiplicative\" }}")
                seas = None
        fill = v.get("fill")
        if fill is not None and fill != "linear":
            problems.append(f"{where}: fill = {fill!r} — 지금은 \"linear\"(안쪽 결측 선형 보간)만")
        series[name] = SeriesSpec(name=name, source=src, column=col, convert=conv, denton=v.get("denton", "sum"),
                                  seas=seas, scale=v.get("scale"), fill=fill, unit=str(v.get("unit", "")),
                                  desc=str(v.get("desc", "")))
    if not series:
        problems.append(f"{series_file}: 시리즈가 하나도 없습니다 — [series.이름] from = \"원자료이름:열\"")
    lows = {}
    for nm in series:
        if nm.lower() in lows:
            problems.append(f"{series_file}: 대소문자만 다른 시리즈 이름 {lows[nm.lower()]} · {nm}")
        lows[nm.lower()] = nm
    derived: List[Tuple[int, str, str, str]] = []
    texts = {series_file: hashlib.sha256(series_text.encode("utf-8")).hexdigest() if series_text is not None else _sha_text(spath)}
    if derived_file:
        dpath = os.path.join(root, derived_file)
        if not os.path.isfile(dpath):
            problems.append(f"파생식 파일이 없습니다: {derived_file}")
        else:
            from ..data.io import read_text
            texts[derived_file] = _sha_text(dpath)
            for k, line in enumerate(read_text(dpath).splitlines(), 1):
                body, _, comment = line.partition("#")
                body = body.strip()
                if not body:
                    continue
                name, eq, expr = body.partition("=")
                name = name.strip()
                if not eq or not expr.strip():
                    problems.append(f"{derived_file}:{k}: '이름 = 식' 꼴이어야 합니다 — {body[:60]}")
                    continue
                if not NAME_RE.match(name):
                    problems.append(f"{derived_file}:{k}: 이름 {name!r} — 영문으로 시작하고 영문·숫자·_만")
                    continue
                if name.lower() in lows:
                    problems.append(f"{derived_file}:{k}: 파생 이름 {name}이(가) series.toml의 시리즈와 겹칩니다")
                    continue
                lows[name.lower()] = name
                derived.append((k, name, expr.strip(), comment.strip()))
    if problems:
        raise ProjectError(problems)
    return DataDefs(root=root, freq=freq, series_file=series_file, derived_file=derived_file, sources=sources,
                    series=series, derived=derived, texts=texts)


# ---------------------------------------------------------------------------
# 회차 만들기
# ---------------------------------------------------------------------------
@dataclass
class BuildResult:
    """자료 만들기 결과 — 새로 만들었으면 `.created`, 같은 내용의 회차가 이미 있으면 그 회차(`.same_as`)."""

    id: str
    path: str
    created: bool
    n_series: int
    span: Tuple[str, str]
    implicit: List[str]
    same_as: Optional[str] = None
    inbox: list = field(default_factory=list)      # 받은 원자료(InboxItem) — --inbox로 넣은 것
    waiting: int = 0                               # --inbox 없이 만들 때 받은 상자에 남은 파일 수

    def text(self) -> str:
        """명령줄에 보이는 짧은 글."""
        head = (f"[data build] 새 회차 {self.id}" if self.created else
                f"[data build] 바뀐 것 없음 — 회차 {self.id}와 내용이 같습니다(새로 만들지 않음)")
        L = [head, f"  시리즈 {self.n_series} · {self.span[0]}~{self.span[1]}"]
        if self.inbox:
            L.append(f"  받은 원자료 {len(self.inbox)}")
            L += [f"    - {x.text()}" for x in self.inbox]
        if self.waiting:
            L.append(f"  받은 상자(DATA/raw/inbox/)에 파일 {self.waiting}개 — 넣으려면 equion data build --inbox ask")
        if self.implicit:
            L.append("  알아서 한 것")
            L += [f"    - {x}" for x in self.implicit]
        return "\n".join(L)

    def to_dict(self) -> dict:
        """명령줄 --json과 같은 사전."""
        return {"id": self.id, "created": self.created, "n_series": self.n_series, "span": list(self.span),
                "implicit": self.implicit, "path": self.path, "inbox": [x.to_dict() for x in self.inbox],
                "waiting": self.waiting}

    def __repr__(self):
        return f"<자료 회차 {self.id}{'' if self.created else ' (이미 있음)'}: 시리즈 {self.n_series}>"


class _Quiet:
    def __enter__(self):
        self.old = verbose()
        verbose(0)

    def __exit__(self, *a):
        verbose(self.old)


def _seasonal(s: pd.Series, freq: str, opts: dict) -> pd.Series:
    if freq == "A":
        raise ValueError("연간 자료에는 계절조정이 없습니다")
    method, model = opts.get("method", "stl"), opts.get("model", "additive")
    kw = {k: v for k, v in opts.items() if k not in ("method", "model")}
    vals = s.to_numpy(dtype=float)
    ok = np.isfinite(vals)
    if not ok.any():
        return s
    a, b = int(np.argmax(ok)), len(ok) - 1 - int(np.argmax(ok[::-1]))
    y = vals[a:b + 1]
    if not np.isfinite(y).all():
        raise ValueError("안쪽에 결측이 있어 계절조정을 할 수 없습니다 — fill = \"linear\"로 채우거나 원자료를 확인하세요")
    period = PERIODS_PER_YEAR[freq]
    mult = model == "multiplicative"
    if method == "stl":
        if mult and np.any(y <= 0):
            raise ValueError("승법 STL에는 양수 자료만 됩니다")
        S, _, _, _ = tr.stl(np.log(y) if mult else y, period, **kw)
        S = np.exp(S) if mult else S
    else:
        S, _, _ = tr.classical(y, period, model)
    out = vals.copy()
    out[a:b + 1] = y / S if mult else y - S
    return pd.Series(out, index=s.index, name=s.name)


def _convert(s: pd.Series, src_freq: str, freq: str, spec: SeriesSpec) -> pd.Series:
    up = PERIODS_PER_YEAR[src_freq] < PERIODS_PER_YEAR[freq]      # 낮은 → 높은 주기
    how = spec.convert
    if how is None:
        raise ValueError(f"원자료 주기 {src_freq} ≠ 자료 주기 {freq} — convert = "
                         + ("\"constant\"·\"split\"·\"linear\"·\"denton\"" if up else "\"mean\"·\"sum\"·\"first\"·\"last\""))
    if up:
        if how not in EXPAND:
            raise ValueError(f"{src_freq} → {freq}(높은 주기로)에는 convert = constant·split·linear·denton")
        ok = np.isfinite(s.to_numpy(dtype=float))
        if not ok.any():
            raise ValueError("값이 없습니다")
        a, b = int(np.argmax(ok)), len(ok) - 1 - int(np.argmax(ok[::-1]))
        blk = s.iloc[a:b + 1]
        if blk.isna().any():
            raise ValueError("안쪽에 결측이 있어 주기를 바꿀 수 없습니다")
        if how == "denton":
            k = PERIODS_PER_YEAR[freq] // PERIODS_PER_YEAR[src_freq]
            vals = tr.denton(blk.to_numpy(dtype=float), k, conversion=spec.denton)
            p0 = pd.Period(blk.index[0], freq={"Q": "Q", "M": "M"}[freq])
            idx = period_starts(p0, p0 + len(vals) - 1, freq)
            return pd.Series(vals, index=idx, name=s.name)
        return tr.expand(blk, src_freq, freq, how)
    if how not in AGG:
        raise ValueError(f"{src_freq} → {freq}(낮은 주기로)에는 convert = mean·sum·first·last·max·min")
    return tr.aggregate(s, src_freq, freq, how, complete=True)


def _series_values(s: pd.Series, src_freq: str, F: str, spec: SeriesSpec, implicit: List[str]) -> Tuple[pd.Series, pd.Series]:
    """원자료의 열 하나를 정의대로 — 주기 변환 → 배율 → 채움 → 계절조정. (값, 값의 종류). 알아서 한 것은 implicit에, 문제는 ValueError."""
    if src_freq != F:
        s = _convert(s, src_freq, F, spec).rename(spec.name)
        implicit.append(f"{spec.name}: {src_freq} → {F} {spec.convert}")
    flags = pd.Series(np.where(np.isfinite(s.to_numpy(dtype=float)),
                               "transformed" if src_freq != F else "actual", "missing"), index=s.index)
    if spec.scale is not None:
        s = s * float(spec.scale)
        flags[flags == "actual"] = "transformed"
    if spec.fill == "linear":
        before = s.isna()
        s = s.interpolate(limit_area="inside")
        filled = before & s.notna()
        if filled.any():
            flags[filled] = "filled"
            implicit.append(f"{spec.name}: 안쪽 결측 {int(filled.sum())}칸을 선형으로 채움 "
                            f"({format_period(s.index[filled.to_numpy()][0], F)}부터)")
    if spec.seas:
        s = _seasonal(s, F, spec.seas)
        flags[flags == "actual"] = "transformed"
        implicit.append(f"{spec.name}: 계절조정 {spec.seas.get('method', 'stl')} "
                        f"{spec.seas.get('model', 'additive')}")
    return s, flags


def _suffix(n: int) -> str:
    s = ""
    n += 1
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(97 + r) + s
    return s


def next_id(root: str, now: datetime = None) -> str:
    now = now or datetime.now()
    base = f"d{now:%Y-%m}"
    have = {v["id"] for v in list_vintages(root)}
    k = 0
    while f"{base}{_suffix(k)}" in have:
        k += 1
    return f"{base}{_suffix(k)}"


def build_vintage(defs: DataDefs, equion_version: str, now: datetime = None) -> BuildResult:
    """정의대로 자료 회차를 만든다. 문제(틀이 안 맞음·없는 열·주기 변환)는 모아서 ProjectError."""
    from ..workfile.workfile import _from_frame
    F = defs.freq
    implicit: List[str] = []
    problems: List[str] = []
    tables: Dict[str, SourceTable] = {}
    for name in defs.used_sources():
        if name not in defs.sources:
            continue
        try:
            t = read_source(defs.sources[name])
        except ValueError as e:
            problems.append(f"[source.{name}] {e}")
            continue
        tables[name] = t
        implicit.append(t.time_note)
        if t.missing_cells:
            implicit.append(f"{name}: 결측 표시로 본 칸 {len(t.missing_cells)}개 (예: {', '.join(t.missing_cells[:3])})")
        if t.bad_cells:
            implicit.append(f"{name}: 숫자가 아닌 칸 {len(t.bad_cells)}개를 결측으로 (예: {', '.join(t.bad_cells[:3])})")
    out: Dict[str, Tuple[pd.Series, pd.Series]] = {}
    meta: Dict[str, dict] = {}
    for spec in defs.series.values():
        t = tables.get(spec.source)
        if t is None:
            continue
        col, case = t.column(spec.column)
        where = f"[series.{spec.name}]"
        if col is None:
            problems.append(f"{where} from = '{spec.source}:{spec.column}': 열이 없습니다 "
                            f"(있는 열: {', '.join(map(str, t.data.columns[:12]))})")
            continue
        if case:
            implicit.append(f"{spec.name}: 열 {spec.column} → {col}(대소문자만 다름)")
        s = t.data[col].astype(float).rename(spec.name)
        try:
            s, flags = _series_values(s, t.freq, F, spec, implicit)
        except ValueError as e:
            problems.append(f"{where} {e}")
            continue
        out[spec.name] = (s, flags)
        unit = spec.unit or t.units.get(col, "")
        meta[spec.name] = {"kind": "series", "from": f"{spec.source}:{col}", "unit": unit, "desc": spec.desc,
                           "convert": spec.convert, "seas": spec.seas, "scale": spec.scale, "fill": spec.fill}
    if problems:
        raise ProjectError(problems)
    if not out:
        raise ProjectError("만들 시리즈가 없습니다")
    p0 = min(to_period(s.index[0], F) for s, _ in out.values())
    p1 = max(to_period(s.index[-1], F) for s, _ in out.values())
    idx = period_starts(p0, p1, F)
    df = pd.DataFrame({n: s.reindex(idx) for n, (s, _) in out.items()}, index=pd.DatetimeIndex(idx, name="date"))
    fl = pd.DataFrame({n: f.reindex(idx).fillna("missing") for n, (_, f) in out.items()}, index=idx)
    spans = {(format_period(s.first_valid_index(), F), format_period(s.last_valid_index(), F))
             for s, _ in out.values() if s.first_valid_index() is not None}
    if len(spans) > 1:
        implicit.append(f"시리즈마다 자료 구간이 다릅니다 — 회차는 {format_period(p0, F)}~{format_period(p1, F)}, "
                        "빈 칸은 결측")
    if defs.derived:
        with _Quiet():
            wf = _from_frame(df.copy(), F, "vintage", check=False)
            for line, name, expr, desc in defs.derived:
                try:
                    wf.genr(f"{name} = {expr}", smpl=False)
                except Exception as e:  # noqa: BLE001 — 식 오류를 줄 번호와 함께
                    problems.append(f"{defs.derived_file}:{line}: {str(e)[:200]} — {name} = {expr}")
                    continue
                vals = wf[name].to_numpy(dtype=float)
                df[name] = vals
                fl[name] = np.where(np.isfinite(vals), "derived", "missing")
                meta[name] = {"kind": "derived", "expr": expr, "line": line, "desc": desc, "unit": ""}
        if problems:
            raise ProjectError(problems)
    return _write_vintage(defs, df, fl, meta, implicit, equion_version, now)


def _write_vintage(defs, df, fl, meta, implicit, equion_version, now) -> BuildResult:
    F = defs.freq
    root = defs.root
    labels = [format_period(ts, F) for ts in df.index]
    series_csv = df.set_axis(pd.Index(labels, name="period")).to_csv(lineterminator="\n")
    flags_csv = fl.set_axis(pd.Index(labels, name="period")).to_csv(lineterminator="\n")
    meta_doc = {"format": FORMAT, "freq": F, "series": meta}
    meta_json = json.dumps(meta_doc, ensure_ascii=False, indent=2, sort_keys=True)
    content = hashlib.sha256((series_csv + "\0" + flags_csv + "\0" + meta_json).encode("utf-8")).hexdigest()
    span = (labels[0], labels[-1])
    for v in list_vintages(root):
        if v.get("content_sha256") == content:
            return BuildResult(v["id"], v["path"], False, len(df.columns), span, implicit, same_as=v["id"])
    vid = next_id(root, now)
    base = os.path.join(root, VINTAGE_DIR)
    os.makedirs(base, exist_ok=True)
    tmp = os.path.join(base, f".tmp-{vid}")
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp)
    sources = []
    for name in defs.used_sources():
        sp = defs.sources.get(name)
        if sp is not None:
            sources.append({"name": name, "file": sp.file, "sha256": file_sha256(sp.path)})
    build = {"format": FORMAT, "format_version": FORMAT_VERSION, "id": vid,
             "created": (now or datetime.now()).isoformat(timespec="seconds"), "equion": equion_version,
             "freq": F, "span": list(span), "n_series": len(df.columns), "series": list(df.columns),
             "definitions": defs.texts, "sources": sources, "content_sha256": content, "implicit": implicit}
    files = {"series.csv": series_csv, "flags.csv": flags_csv, "meta.json": meta_json,
             "build.json": json.dumps(build, ensure_ascii=False, indent=2),
             "summary.md": _summary_md(vid, build, df, fl, meta)}
    for fn, text in files.items():
        with open(os.path.join(tmp, fn), "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
    final = os.path.join(base, vid)
    os.replace(tmp, final)
    return BuildResult(vid, final, True, len(df.columns), span, implicit)


def _summary_md(vid, build, df, fl, meta) -> str:
    F = build["freq"]
    L = [f"# 자료 회차 {vid}", "",
         "| 기록 | 만든 때 | 주기 | 구간 | 시리즈 | equion |", "|---|---|---|---|---|---|",
         f"| `data:{vid}` | {build['created']} | {F} | {build['span'][0]}~{build['span'][1]} | {build['n_series']} | "
         f"{build['equion']} |", "",
         "| 시리즈 | 출처·식 | 처음 | 끝 | 값 | 설명 |", "|---|---|---|---|---|---|"]
    for c in df.columns:
        s = df[c]
        fv, lv = s.first_valid_index(), s.last_valid_index()
        m = meta.get(c, {})
        src = m.get("from") or (f"= {m.get('expr')}" if m.get("expr") else "")
        L.append(f"| {c} | {src} | {format_period(fv, F) if fv is not None else ''} | "
                 f"{format_period(lv, F) if lv is not None else ''} | {int(s.notna().sum())} | {m.get('desc', '')} |")
    L += ["", "**알아서 한 것** — " + (" · ".join(build["implicit"]) if build["implicit"] else "없음"), ""]
    return "\n".join(L)


# ---------------------------------------------------------------------------
# 목록·읽기·비교
# ---------------------------------------------------------------------------
def list_vintages(root: str) -> List[dict]:
    """회차 목록(만든 때 순) — build.json의 내용과 경로."""
    base = os.path.join(root, VINTAGE_DIR)
    out = []
    if not os.path.isdir(base):
        return out
    for name in os.listdir(base):
        p = os.path.join(base, name, "build.json")
        if VID_RE.match(name) and os.path.isfile(p):
            with open(p, encoding="utf-8") as f:
                b = json.load(f)
            b["path"] = os.path.join(base, name)
            out.append(b)
    return sorted(out, key=lambda b: (b.get("created", ""), b["id"][:9], len(b["id"]), b["id"]))


def vintage_path(root: str, vid: str) -> str:
    p = os.path.join(root, VINTAGE_DIR, vid)
    if not VID_RE.match(vid or "") or not os.path.isfile(os.path.join(p, "series.csv")):
        have = [v["id"] for v in list_vintages(root)]
        raise ProjectError(f"자료 회차 {vid!r}가 없습니다 (있는 회차: {', '.join(have) or '없음 — equion data build'})")
    return p


def read_vintage(root: str, vid: str) -> Tuple[pd.DataFrame, pd.DataFrame, dict]:
    """(값 표, 값의 종류 표, meta) — 인덱스는 기간 라벨."""
    p = vintage_path(root, vid)
    df = pd.read_csv(os.path.join(p, "series.csv"), index_col=0)
    fl = pd.read_csv(os.path.join(p, "flags.csv"), index_col=0, dtype=str)
    with open(os.path.join(p, "meta.json"), encoding="utf-8") as f:
        meta = json.load(f)
    df.index = df.index.astype(str)
    fl.index = fl.index.astype(str)
    return df.astype(float), fl, meta


@dataclass
class VintageDiff:
    """두 회차의 차이 — 새·없어진 시리즈, 시리즈마다 새 기간·개정(기간·크기)."""

    a: str
    b: str
    span_a: Tuple[str, str]
    span_b: Tuple[str, str]
    added: List[str]
    removed: List[str]
    changes: pd.DataFrame          # 시리즈 · 새 값 · 개정 · 처음 개정 · 끝 개정 · 최대 |차이| · 최대 |차이%| · 없어진 값
    unchanged: List[str]

    @property
    def changed(self) -> List[str]:
        """새 값·개정·없어진 값이 있는 시리즈."""
        return list(self.changes.index)

    def text(self) -> str:
        """명령줄에 보이는 짧은 글."""
        L = [f"[data diff {self.a} → {self.b}]",
             f"  구간   {self.span_a[0]}~{self.span_a[1]} → {self.span_b[0]}~{self.span_b[1]}"]
        if self.added:
            L.append(f"  새 시리즈 {len(self.added)}  " + " · ".join(self.added))
        if self.removed:
            L.append(f"  없어진 시리즈 {len(self.removed)}  " + " · ".join(self.removed))
        if len(self.changes):
            L.append(f"  바뀐 시리즈 {len(self.changes)}")
            for name, r in self.changes.iterrows():
                bits = []
                if r["개정"]:
                    bits.append(f"개정 {int(r['개정'])}기({r['처음 개정']}~{r['끝 개정']}) 최대 {r['최대 |차이%|']:.3g}%")
                if r["새 값"]:
                    bits.append(f"새 값 {int(r['새 값'])}기")
                if r["없어진 값"]:
                    bits.append(f"없어진 값 {int(r['없어진 값'])}기")
                L.append(f"    {name:<8} " + " · ".join(bits))
        L.append(f"  그대로 {len(self.unchanged)}")
        return "\n".join(L)

    def to_dict(self) -> dict:
        """명령줄 --json과 같은 사전."""
        ch = self.changes.reset_index().to_dict(orient="records")
        for r in ch:
            for k, v in list(r.items()):
                if isinstance(v, (np.integer,)):
                    r[k] = int(v)
                elif isinstance(v, float) and np.isnan(v):
                    r[k] = None
        return {"a": self.a, "b": self.b, "span_a": list(self.span_a), "span_b": list(self.span_b),
                "added": self.added, "removed": self.removed, "changes": ch, "unchanged": self.unchanged}

    def output(self) -> TableOutput:
        """바뀐 시리즈 표."""
        return TableOutput(self.changes, title=f"자료 회차 {self.a} → {self.b}", name=f"diff_{self.a}_{self.b}",
                           head=[f"새 시리즈 {len(self.added)} · 없어진 시리즈 {len(self.removed)} · 바뀐 {len(self.changes)}"])

    def show(self):
        """짧은 글을 보인다."""
        from ..workfile.output import spool
        spool.show(TextOutput(self.text(), title=f"자료 회차 {self.a} → {self.b}"))

    def __repr__(self):
        return f"<회차 차이 {self.a}→{self.b}: 새 {len(self.added)} · 바뀜 {len(self.changes)}>"


def diff_vintages(root: str, a: str, b: str, tol: float = 1e-9) -> VintageDiff:
    da, _, _ = read_vintage(root, a)
    db, _, _ = read_vintage(root, b)
    added = [c for c in db.columns if c not in da.columns]
    removed = [c for c in da.columns if c not in db.columns]
    labels = list(dict.fromkeys(list(da.index) + list(db.index)))
    rows, same = {}, []
    for c in [c for c in db.columns if c in da.columns]:
        va = da[c].reindex(labels).to_numpy(dtype=float)
        vb = db[c].reindex(labels).to_numpy(dtype=float)
        fa, fb = np.isfinite(va), np.isfinite(vb)
        new = fb & ~fa
        lost = fa & ~fb
        both = fa & fb
        with np.errstate(all="ignore"):
            d = np.where(both, vb - va, 0.0)
            rev = both & (np.abs(d) > tol * np.maximum(1.0, np.abs(va)))
            pct = np.where(rev & (va != 0), 100 * np.abs(d) / np.abs(va), 0.0)
        if new.any() or lost.any() or rev.any():
            ri = np.flatnonzero(rev)
            rows[c] = {"새 값": int(new.sum()), "개정": int(rev.sum()),
                       "처음 개정": labels[ri[0]] if len(ri) else "", "끝 개정": labels[ri[-1]] if len(ri) else "",
                       "최대 |차이|": float(np.abs(d[rev]).max()) if len(ri) else 0.0,
                       "최대 |차이%|": float(pct.max()) if len(ri) else 0.0, "없어진 값": int(lost.sum())}
        else:
            same.append(c)
    cols = ["새 값", "개정", "처음 개정", "끝 개정", "최대 |차이|", "최대 |차이%|", "없어진 값"]
    ch = pd.DataFrame.from_dict(rows, orient="index", columns=cols) if rows else pd.DataFrame(columns=cols)
    ch.index.name = "시리즈"
    return VintageDiff(a, b, (da.index[0], da.index[-1]), (db.index[0], db.index[-1]), added, removed, ch, same)


# ---------------------------------------------------------------------------
# 원자료 넣기·지금 회차 바꾸기 — 정의 파일은 주석·순서를 지키며 고친다(tomlkit, D38)
# ---------------------------------------------------------------------------
@dataclass
class AddResult:
    """원자료 넣기 결과."""

    file: str                      # 프로젝트 기준 경로
    sha256: str
    copied: bool                   # 같은 파일이 이미 있으면 거짓
    source: Optional[str] = None   # 바꾼 출처
    previous: Optional[str] = None
    problems: List[str] = field(default_factory=list)

    def text(self) -> str:
        """명령줄에 보이는 짧은 글."""
        if self.problems:
            L = [f"[data add] {self.file} — 넣지 않았습니다: 출처 '{self.source}'의 틀이 맞지 않습니다({len(self.problems)})"]
            L += [f"    - {p}" for p in self.problems]
            L.append(f"  출처는 그대로 {self.previous}")
            return "\n".join(L)
        L = [f"[data add] {self.file}" + ("" if self.copied else " — 같은 파일이 이미 있습니다(새로 넣지 않음)"),
             f"  해시   {self.sha256[:16]}…"]
        if self.source:
            if self.previous == self.file:
                L.append(f"  출처   [source.{self.source}] 이미 이 파일을 읽습니다")
            else:
                L.append(f"  출처   [source.{self.source}] {self.previous} → {self.file}")
                L.append("  다음   equion data build → equion data use <회차>")
        return "\n".join(L)

    def to_dict(self) -> dict:
        """명령줄 --json과 같은 사전."""
        return {"file": self.file, "sha256": self.sha256, "copied": self.copied, "source": self.source,
                "previous": self.previous, "problems": self.problems}


def _rel(root, path):
    return os.path.relpath(path, root).replace(os.sep, "/")


def add_raw(root: str, src: str, as_name: str = None, note: str = None) -> AddResult:
    """원자료 파일을 DATA/raw/에 복사한다(받은 파일은 고치지 않는다). 같은 이름·다른 내용이면 날짜를 붙여 나란히."""
    if not os.path.isfile(src):
        raise ProjectError(f"파일이 없습니다: {src}")
    name = as_name or os.path.basename(src)
    if any(ch in name for ch in '/\\:*?"<>|') or name.strip(" .") == "" or name.startswith("."):
        raise ProjectError(f"DATA/raw/에 둘 이름은 파일 이름 하나입니다(폴더·특수문자 불가): {name!r}")
    stem, ext = os.path.splitext(name)
    if ext.lower() not in (".csv", ".xlsx", ".xls"):
        raise ProjectError(f"원자료는 csv·xlsx·xls입니다: {name}")
    raw = os.path.join(root, RAW_DIR)
    os.makedirs(raw, exist_ok=True)
    sha = file_sha256(src)
    size = os.path.getsize(src)
    for have in sorted(os.listdir(raw)):   # 같은 내용이 다른 이름으로 이미 있으면 그 파일을 쓴다
        hp = os.path.join(raw, have)
        if (os.path.splitext(have)[1].lower() in (".csv", ".xlsx", ".xls") and os.path.isfile(hp)
                and os.path.getsize(hp) == size and file_sha256(hp) == sha):
            return AddResult(_rel(root, hp), sha, False)
    dest = os.path.join(raw, name)
    if os.path.exists(dest):   # 같은 이름·다른 내용 — 날짜를 붙여 나란히(옛 회차가 읽은 파일은 그대로)
        day = datetime.now().strftime("%Y%m%d")
        dest = os.path.join(raw, f"{stem}_{day}{ext}")
        k = 2
        while os.path.exists(dest):
            dest = os.path.join(raw, f"{stem}_{day}_{k}{ext}")
            k += 1
    shutil.copy2(src, dest)
    import tomlkit
    side = tomlkit.document()
    side.add(tomlkit.comment("원자료의 출처 — equion data add가 남긴다"))
    side["file"] = os.path.basename(dest)
    side["from"] = os.path.basename(src)
    side["added"] = datetime.now().isoformat(timespec="seconds")
    side["sha256"] = sha
    side["bytes"] = os.path.getsize(dest)
    if note:
        side["note"] = note
    with open(dest + ".source.toml", "w", encoding="utf-8", newline="\n") as f:
        f.write(tomlkit.dumps(side))
    return AddResult(_rel(root, dest), sha, True)


def toml_with_value(path: str, table: List[str], key: str, value) -> str:
    """TOML 파일의 표(table 경로)의 key를 value로 바꾼 새 내용 — 주석·순서·서식은 그대로(tomlkit). 파일은 쓰지 않는다."""
    import tomlkit
    with open(path, encoding="utf-8") as f:
        doc = tomlkit.parse(f.read())
    node = doc
    for t in table:
        if t not in node:
            node[t] = tomlkit.table()
        node = node[t]
    node[key] = value
    return tomlkit.dumps(doc)


def set_toml_value(path: str, table: List[str], key: str, value):
    """TOML 파일의 표(table 경로)의 key를 value로 — 주석·순서·서식은 그대로(tomlkit)."""
    text = toml_with_value(path, table, key, value)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


# ---- 불러오기: 원자료 미리보기와 자료 정의 쓰기 ------------------------------------------------

FRAME_KEYS = ("sheet", "header_row", "unit_row", "time_col", "missing", "thousands", "freq")
SERIES_KEYS = ("convert", "denton", "seas", "scale", "fill", "unit", "desc")


def _frame_spec(root: str, file: str, name: str = "preview", sheet=None, header_row=None, unit_row=None, time_col=None,
                missing=None, thousands=None, freq=None) -> SourceSpec:
    """파일과 틀(시트·열 이름 줄·단위 줄·시점 열·결측 표시·천 단위·주기)로 불러오기 틀 하나를 만든다. 문제는 ProjectError."""
    from ..data.source import EXTENSIONS
    path = os.path.normpath(file if os.path.isabs(file) else os.path.join(root, file))
    if not os.path.isfile(path):
        raise ProjectError(f"파일이 없습니다: {file}")
    if os.path.splitext(path)[1].lower() not in EXTENSIONS:
        raise ProjectError(f"{file}: 읽을 수 없는 형식 — csv·xlsx·xls")
    inside = os.path.normcase(path).startswith(os.path.normcase(os.path.abspath(root)) + os.sep)
    rel = os.path.relpath(path, root).replace(os.sep, "/") if inside else path
    miss = [missing] if isinstance(missing, str) else list(missing or [])
    if isinstance(sheet, str) and sheet.strip().isdigit():
        sheet = int(sheet)
    if isinstance(time_col, str) and time_col.strip().isdigit():
        time_col = int(time_col)
    try:
        return SourceSpec(name=name, file=rel, path=path, sheet=sheet if sheet not in ("", None) else None,
                          header_row=int(header_row or 1), unit_row=int(unit_row) if unit_row else None,
                          time_col=time_col if time_col not in ("", None) else None, missing=[str(m) for m in miss if str(m) != ""],
                          thousands=thousands or None, freq=normalize_freq(freq) if freq else None)
    except (TypeError, ValueError) as e:
        raise ProjectError(f"{file}: 틀을 읽을 수 없습니다 — {e}") from None


@dataclass
class SourcePreview:
    """원자료 미리보기 — 읽은 그대로의 칸(`grid`)과, 그 틀로 읽어 본 결과(주기·구간·열마다 값의 수). 아무것도 쓰지 않는다."""

    file: str                              # 프로젝트 기준 경로(프로젝트 밖이면 받은 경로)
    sheets: List[str]                      # 엑셀의 시트 이름(csv는 빈 목록)
    shape: Tuple[int, int]                 # 파일의 (줄, 열)
    grid: List[List[str]]                  # 앞쪽 줄 — 읽은 그대로(글자)
    frame: dict                            # 본 틀
    ok: bool = False                       # 그 틀로 읽혔나
    error: str = ""                        # 읽지 못한 까닭(칸 위치와 함께)
    freq: Optional[str] = None
    span: Optional[List[str]] = None
    note: str = ""                         # "시점 열 A('1970Q1' 꼴) → Q 1970Q1~2019Q4"
    time_col: Optional[int] = None         # 시점 열의 자리(0부터)
    columns: List[dict] = field(default_factory=list)       # 열마다 name·col·letter·unit·n·first·last·missing·bad·name_ok
    missing_cells: List[str] = field(default_factory=list)  # 결측 표시로 읽은 칸('C42 "–"' 꼴)
    bad_cells: List[str] = field(default_factory=list)      # 숫자가 아니어서 결측으로 본 칸
    series: Optional[dict] = None          # 열 하나를 변환대로 만들어 본 것(`data_preview(series=…)`)

    def to_dict(self) -> dict:
        """명령줄 --json과 같은 사전."""
        return {"file": self.file, "sheets": self.sheets, "shape": list(self.shape), "grid": self.grid, "frame": self.frame,
                "ok": self.ok, "error": self.error, "freq": self.freq, "span": self.span, "note": self.note,
                "time_col": self.time_col, "columns": self.columns, "missing_cells": self.missing_cells,
                "bad_cells": self.bad_cells, "series": self.series}

    def text(self) -> str:
        """명령줄에 보이는 짧은 글."""
        L = [f"[data preview] {self.file} — {self.shape[0]}줄 × {self.shape[1]}열"
             + (f" · 시트 {', '.join(self.sheets)}" if self.sheets else "")]
        for k, row in enumerate(self.grid[:6], 1):
            L.append(f"  {k:>3} | " + " | ".join(c[:12] for c in row[:8]) + (" | …" if len(row) > 8 else ""))
        if not self.ok:
            L.append(f"  읽지 못했습니다: {self.error}")
            return "\n".join(L)
        L.append(f"  읽은 것  {self.note}")
        for c in self.columns:
            L.append(f"    {c['letter']:>3} {c['name']:<16} {c['first'] or '—'}~{c['last'] or '—'} · 값 {c['n']}"
                     + (f" · 결측 표시 {c['missing']}" if c["missing"] else "") + (f" · 숫자 아님 {c['bad']}" if c["bad"] else "")
                     + (f" · {c['unit']}" if c["unit"] else ""))
        if self.series:
            s = self.series
            L.append(f"  만들어 본 것  {s['column']} → {s['freq']} {s['period'][0] if s['period'] else '—'}~"
                     f"{s['period'][-1] if s['period'] else '—'} · 값 {s['n']}" + "".join(f"\n    - {x}" for x in s["implicit"]))
        return "\n".join(L)


def preview_source(root: str, file: str, sheet=None, header_row=None, unit_row=None, time_col=None, missing=None,
                   thousands=None, freq=None, rows: int = 30) -> SourcePreview:
    """원자료 파일을 미리 본다 — 읽은 그대로의 앞쪽 줄과, 준 틀로 읽어 본 결과. 틀이 맞지 않아도 예외가 아니라 `.error`에 까닭."""
    import re

    from ..data.source import _cell_text, _read_grid, _time_index, col_letter
    spec = _frame_spec(root, file, "preview", sheet, header_row, unit_row, time_col, missing, thousands, freq)
    sheets: List[str] = []
    if not spec.path.lower().endswith(".csv"):
        try:
            with pd.ExcelFile(spec.path) as book:
                sheets = [str(s) for s in book.sheet_names]
        except Exception as e:  # noqa: BLE001 — 깨진 파일·암호가 걸린 파일
            raise ProjectError(f"{spec.file}: 열 수 없습니다 — {e}") from None
    try:
        grid = _read_grid(spec)
    except ValueError as e:
        raise ProjectError(str(e)) from None
    head = [[_cell_text(v) for v in row] for row in grid.iloc[:max(1, int(rows))].values.tolist()]
    out = SourcePreview(spec.file, sheets, (int(grid.shape[0]), int(grid.shape[1])), head,
                        {"sheet": spec.sheet, "header_row": spec.header_row, "unit_row": spec.unit_row, "time_col": spec.time_col,
                         "missing": list(spec.missing), "thousands": spec.thousands, "freq": spec.freq})
    try:
        t = read_source(spec)
        names = [_cell_text(v) or f"열{col_letter(k)}" for k, v in enumerate(grid.iloc[spec.header_row - 1].tolist())]
        tcol = _time_index(grid, names, spec)
    except ValueError as e:
        out.error = str(e)
        return out

    def by_letter(cells: List[str]) -> Dict[str, int]:
        count: Dict[str, int] = {}
        for c in cells:
            m = re.match(r"([A-Z]+)\d+", c)
            if m:
                count[m.group(1)] = count.get(m.group(1), 0) + 1
        return count

    miss, bad = by_letter(t.missing_cells), by_letter(t.bad_cells)
    for k, nm in enumerate(names):
        if k == tcol:
            continue
        valid = t.data[nm].dropna()
        out.columns.append({"name": nm, "col": k, "letter": col_letter(k), "unit": t.units.get(nm, ""), "n": int(len(valid)),
                            "first": format_period(valid.index[0], t.freq) if len(valid) else None,
                            "last": format_period(valid.index[-1], t.freq) if len(valid) else None,
                            "missing": miss.get(col_letter(k), 0), "bad": bad.get(col_letter(k), 0),
                            "name_ok": bool(NAME_RE.match(nm))})
    out.ok, out.freq, out.time_col = True, t.freq, int(tcol)
    out.span = [format_period(t.data.index[0], t.freq), format_period(t.data.index[-1], t.freq)]
    out.note = t.time_note.split(": ", 1)[-1]
    out.missing_cells, out.bad_cells = t.missing_cells[:200], t.bad_cells[:200]
    return out


def _seas_spec(seas):
    """seas 값 — "stl"·"classical"·"stl:multiplicative"·사전 → 사전(없으면 None)."""
    if seas in (None, "", False):
        return None
    if isinstance(seas, str):
        method, _, model = seas.partition(":")
        seas = {"method": method.strip(), **({"model": model.strip()} if model.strip() else {})}
    if not isinstance(seas, dict) or seas.get("method", "stl") not in ("stl", "classical") or \
            seas.get("model", "additive") not in ("additive", "multiplicative"):
        raise ProjectError(f"seas = {seas!r} — \"stl\"·\"classical\" 또는 {{ method, model = \"additive\"·\"multiplicative\" }}")
    return dict(seas)


def preview_series(freq: str, spec: SourceSpec, column: str, convert=None, denton: str = "sum", seas=None, scale=None,
                   fill=None, name: str = None) -> dict:
    """열 하나를 변환대로 만들어 본다(자료 만들기와 같은 계산 — 아무것도 쓰지 않는다).

    돌려주는 것: column·freq·period·values(만든 값) · source_freq·raw_period·raw(원자료 값) · n · unit · implicit(알아서 한 것).
    문제(없는 열·주기 변환·계절조정)는 ProjectError.
    """
    try:
        t = read_source(spec)
    except ValueError as e:
        raise ProjectError(str(e)) from None
    col, _case = t.column(column)
    if col is None:
        raise ProjectError(f"열이 없습니다: {column} (있는 열: {', '.join(map(str, t.data.columns[:12]))})")
    if convert is not None and convert not in AGG + EXPAND:
        raise ProjectError(f"convert = {convert!r} — {' · '.join(AGG + EXPAND)}")
    ss = SeriesSpec(name=name or str(col), source=spec.name, column=str(col), convert=convert or None, denton=denton or "sum",
                    seas=_seas_spec(seas), scale=float(scale) if scale not in (None, "") else None, fill=fill or None,
                    unit="", desc="")
    raw = t.data[col].astype(float)
    implicit: List[str] = []
    try:
        s, _flags = _series_values(raw.rename(ss.name), t.freq, freq, ss, implicit)
    except ValueError as e:
        raise ProjectError(str(e)) from None

    def plain(x: pd.Series) -> List[Optional[float]]:
        return [float(v) if np.isfinite(v) else None for v in x.to_numpy(dtype=float)]

    return {"column": str(col), "freq": freq, "period": [format_period(i, freq) for i in s.index], "values": plain(s),
            "source_freq": t.freq, "raw_period": [format_period(i, t.freq) for i in raw.index], "raw": plain(raw),
            "n": int(s.notna().sum()), "unit": t.units.get(col, ""), "implicit": implicit}


@dataclass
class DefineResult:
    """자료 정의 쓰기 결과 — 어느 출처·시리즈가 생기고 바뀌었나."""

    source: str
    file: str
    new_source: bool
    added: List[str] = field(default_factory=list)      # 새 시리즈
    changed: List[str] = field(default_factory=list)    # 고친 시리즈
    change: Optional[str] = None                        # 바뀜 기록(바뀐 것이 없으면 None)

    def text(self) -> str:
        """명령줄에 보이는 짧은 글."""
        L = [f"[data define] [source.{self.source}] {self.file}" + (" — 새 출처" if self.new_source else "")]
        if self.added:
            L.append(f"  새 시리즈   {', '.join(self.added)}")
        if self.changed:
            L.append(f"  고친 시리즈 {', '.join(self.changed)}")
        if self.change:
            L += [f"  바뀜 기록  {self.change}", "  다음   equion data build → equion data use <회차>"]
        else:
            L.append("  바뀐 것이 없습니다")
        return "\n".join(L)

    def to_dict(self) -> dict:
        """명령줄 --json과 같은 사전."""
        return {"source": self.source, "file": self.file, "new_source": self.new_source, "added": self.added,
                "changed": self.changed, "change": self.change}


def define_text(root: str, series_file: str, derived_file: Optional[str], freq: str, source: str, file: str = None,
                frame: dict = None, desc: str = None, series: dict = None, replace: bool = False) -> Tuple[str, DefineResult]:
    """`series.toml`에 출처(불러오기 틀)와 시리즈를 더하거나 고친 **새 내용**을 만든다 — 주석·순서는 그대로(tomlkit), 파일은 쓰지 않는다.

    frame: 틀의 키(sheet·header_row·unit_row·time_col·missing·thousands·freq) — 준 키만 바꾸고, 빈 값·기본값이면 그 키를 지운다.
    series: {이름: 열 이름 또는 {column, unit, desc, convert, denton, seas, scale, fill}} — 없는 이름은 더하고, 있는 이름은 준 키만 고친다
    (다른 열로 바꾸는 것은 replace=True일 때만).
    검사: 이름·키·새 내용 전체(`load_defs`)·그 틀로 원자료를 읽어 이 출처의 시리즈가 쓰는 열이 다 있는지·변환이 되는지.
    문제는 모아서 ProjectError(아무것도 쓰지 않았다).
    """
    import tomlkit
    problems: List[str] = []
    if not NAME_RE.match(str(source)):
        raise ProjectError(f"출처 이름 {source!r} — 영문으로 시작하고 영문·숫자·_만")
    with open(os.path.join(root, series_file), encoding="utf-8") as f:
        doc = tomlkit.parse(f.read())
    for key in ("source", "series"):
        if key not in doc:
            doc[key] = tomlkit.table(True)
    sources, stable = doc["source"], doc["series"]
    new_source = source not in sources
    tb = tomlkit.table() if new_source else sources[source]
    if file:
        path = os.path.normpath(file if os.path.isabs(file) else os.path.join(root, file))
        if not os.path.normcase(path).startswith(os.path.normcase(os.path.abspath(root)) + os.sep):
            raise ProjectError(f"프로젝트 밖의 파일입니다: {file} — 먼저 equion data add로 DATA/raw/에 넣으세요")
        tb["file"] = os.path.relpath(path, root).replace(os.sep, "/")
    elif new_source:
        raise ProjectError(f"새 출처 '{source}'에는 file이 있어야 합니다(DATA/raw/의 파일)")
    for k, v in (frame or {}).items():
        if k not in FRAME_KEYS:
            problems.append(f"[source.{source}] 알 수 없는 틀의 키 {k} — {' · '.join(FRAME_KEYS)}")
            continue
        if k == "missing":
            v = [str(x) for x in ([v] if isinstance(v, str) else list(v or [])) if str(x) != ""]
        elif k in ("header_row", "unit_row") and v not in (None, ""):
            try:
                v = int(v)
            except (TypeError, ValueError):
                problems.append(f"[source.{source}] {k} = {v!r} — 줄 번호(1부터)")
                continue
        elif k in ("sheet", "time_col") and isinstance(v, str) and v.strip().isdigit():
            v = int(v)
        if v in (None, "", [], 0) or (k == "header_row" and v == 1):
            if k in tb:
                del tb[k]
        else:
            tb[k] = v
    if desc is not None:
        if desc:
            tb["desc"] = str(desc)
        elif "desc" in tb:
            del tb["desc"]
    if new_source:
        sources[source] = tb
    lows = {str(k).lower(): str(k) for k in stable}
    res = DefineResult(source, str(tb.get("file", "")), new_source)
    wanted: Dict[str, str] = {}
    for name, given in (series or {}).items():
        where = f"[series.{name}]"
        given = {"column": given} if isinstance(given, str) else dict(given or {})
        col = given.pop("column", None)
        unknown = set(given) - set(SERIES_KEYS)
        if not col:
            problems.append(f"{where} 어느 열을 읽을지 없습니다(column)")
            continue
        if unknown:
            problems.append(f"{where} 알 수 없는 키 {', '.join(sorted(unknown))} — {' · '.join(SERIES_KEYS)}")
            continue
        if not NAME_RE.match(str(name)):
            problems.append(f"{where} 이름은 영문으로 시작하고 영문·숫자·_만(한글은 desc로)")
            continue
        try:
            if "seas" in given and given["seas"] not in (None, "", False):
                inline = tomlkit.inline_table()
                inline.update(_seas_spec(given["seas"]))
                given["seas"] = inline
            if given.get("scale") not in (None, ""):
                given["scale"] = float(given["scale"])
        except (ProjectError, TypeError, ValueError) as e:
            problems.append(f"{where} {e}")
            continue
        frm = f"{source}:{col}"
        have = lows.get(str(name).lower())
        if have is None:
            t = tomlkit.table()
            t["from"] = frm
            for k in SERIES_KEYS:
                if given.get(k) not in (None, "", False):
                    t[k] = given[k]
            stable[name] = t
            lows[str(name).lower()] = str(name)
            res.added.append(str(name))
        elif have != name:
            problems.append(f"{where} 대소문자만 다른 시리즈가 이미 있습니다: {have}")
            continue
        else:
            cur = stable[name]
            if str(cur.get("from")) != frm and not replace:
                problems.append(f"{where} 이미 있는 시리즈입니다(from = {cur.get('from')!r}) — 다른 열로 바꾸려면 replace(--replace)")
                continue
            before = json.dumps(cur.unwrap(), sort_keys=True, default=str, ensure_ascii=False)
            cur["from"] = frm
            for k in SERIES_KEYS:
                if k not in given:
                    continue
                if given[k] in (None, "", False):
                    if k in cur:
                        del cur[k]
                else:
                    cur[k] = given[k]
            if json.dumps(cur.unwrap(), sort_keys=True, default=str, ensure_ascii=False) != before:
                res.changed.append(str(name))
        wanted[str(name)] = str(col)
    if problems:
        raise ProjectError(problems)
    text = tomlkit.dumps(doc)
    defs = load_defs(root, series_file, derived_file, freq, series_text=text)     # 새 내용 전체를 검사(문제는 ProjectError)
    try:
        t = read_source(defs.sources[source])
    except ValueError as e:
        raise ProjectError(f"[source.{source}] 이 틀로 원자료를 읽을 수 없습니다 — {e}") from None
    for s in defs.series.values():
        if s.source != source:
            continue
        col, _case = t.column(s.column)
        if col is None:
            problems.append(f"[series.{s.name}] 원자료에 없는 열: {s.column} (있는 열: {', '.join(map(str, t.data.columns[:12]))})")
        elif s.name in wanted:
            try:
                _series_values(t.data[col].astype(float).rename(s.name), t.freq, freq, s, [])
            except ValueError as e:
                problems.append(f"[series.{s.name}] {e}")
    if problems:
        raise ProjectError(problems)
    res.file = defs.sources[source].file
    return text, res
