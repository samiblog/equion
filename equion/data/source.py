#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""원자료를 '불러오기 틀'로 읽는다 (D34) — 받은 파일은 고치지 않고, 어느 칸을 어떻게 읽을지만 정한다.

불러오기 틀(`series.toml`의 `[source.이름]`):

    file         원자료 파일(csv·xlsx·xls)
    sheet        엑셀 시트 이름 또는 번호(1부터, 기본 첫 시트)
    header_row   열 이름 줄(1부터, 기본 1)
    unit_row     단위 줄(선택)
    time_col     시점 열 — 열 이름 · 엑셀 열 글자(A) · 번호(1부터). 기본 첫 열
    time_axis    'rows'(시점이 행으로 내려간다)만 — 시점이 열로 가는 표는 다음 판
    missing      결측으로 볼 표시(예: ["–", "…", "x"]) — 빈 칸은 늘 결측
    thousands    천 단위 구분 글자(예: ",")
    freq         주기를 직접 정할 때 'Q' · 'M' · 'A'(기본: 시점에서 추론)

시점 꼴은 기간 라벨(2003Q4 · 2003M10 · 2003-10 · 2003)과 ISO 날짜, 그리고 흔한 꼴(2003.Q4 · 2003 Q4 · 2003년 4분기 ·
2003년 4/4분기 · 2003년 10월 · 2003.10)을 읽는다. 숫자가 아닌 칸은 결측으로 보고 칸 위치(C42)와 함께 알린다.
"""

import hashlib
import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from .periods import format_period, infer_freq_code, normalize_freq, parse_dates, regularize

EXTENSIONS = (".csv", ".xlsx", ".xls")


@dataclass
class SourceSpec:
    """불러오기 틀 하나."""

    name: str
    file: str                       # 프로젝트 기준 경로(표시용)
    path: str                       # 절대 경로
    sheet: object = None
    header_row: int = 1
    unit_row: Optional[int] = None
    time_col: object = None
    time_axis: str = "rows"
    missing: List[str] = field(default_factory=list)
    thousands: Optional[str] = None
    freq: Optional[str] = None


@dataclass
class SourceTable:
    """틀로 읽은 원자료 — 기간 첫날 인덱스의 숫자 표."""

    spec: SourceSpec
    data: pd.DataFrame
    freq: str
    units: Dict[str, str]
    missing_cells: List[str]        # '열 C42 "–"' 꼴 — 결측 표시로 본 칸
    bad_cells: List[str]            # 숫자도 결측 표시도 아닌 칸(결측으로 봤다)
    sha256: str
    time_note: str                  # 시점 열과 처음 값 — '알아서 한 것'

    def column(self, name: str):
        """열 이름(대소문자 무시)으로 → (실제 이름, 대소문자만 달랐는지)."""
        if name in self.data.columns:
            return name, False
        low = name.lower()
        for c in self.data.columns:
            if str(c).lower() == low:
                return c, True
        return None, False


def file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def col_letter(k: int) -> str:
    """0부터 센 열 번호 → 엑셀 열 글자(A, B, …, AA)."""
    s = ""
    k += 1
    while k:
        k, r = divmod(k - 1, 26)
        s = chr(65 + r) + s
    return s


_LABELS = (
    (re.compile(r"^(\d{4})\s*[.\-/ ]\s*[Qq]\s*([1-4])$"), lambda m: f"{m[1]}Q{m[2]}"),
    (re.compile(r"^(\d{4})\s*년\s*([1-4])\s*(?:/\s*4\s*)?분기$"), lambda m: f"{m[1]}Q{m[2]}"),
    (re.compile(r"^(\d{4})\s*[Qq]\s*([1-4])$"), lambda m: f"{m[1]}Q{m[2]}"),
    (re.compile(r"^(\d{4})\s*년\s*(\d{1,2})\s*월$"), lambda m: f"{m[1]}-{int(m[2]):02d}"),
    (re.compile(r"^(\d{4})\.(\d{2})$"), lambda m: f"{m[1]}-{m[2]}"),
    (re.compile(r"^(\d{4})\s*[.\-/ ]\s*[Mm]\s*(\d{1,2})$"), lambda m: f"{m[1]}-{int(m[2]):02d}"),
    (re.compile(r"^(\d{4})\s*년$"), lambda m: m[1]),
)


def normalize_label(text) -> str:
    """흔한 시점 꼴을 기간 라벨로(2003.Q4 → 2003Q4 · 2003년 4/4분기 → 2003Q4 · 2003년 10월 → 2003-10). 모르면 그대로."""
    s = str(text).strip()
    for rx, make in _LABELS:
        m = rx.match(s)
        if m:
            return make(m)
    return s


def _read_grid(spec: SourceSpec) -> pd.DataFrame:
    ext = os.path.splitext(spec.path)[1].lower()
    if ext not in EXTENSIONS:
        raise ValueError(f"{spec.file}: 읽을 수 없는 형식 {ext} (csv·xlsx·xls)")
    if ext == ".csv":
        with open(spec.path, "rb") as f:
            raw = f.read()
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            try:
                text = raw.decode("cp949")
            except UnicodeDecodeError:
                raise ValueError(f"{spec.file}: 글자 인코딩을 읽을 수 없습니다 — UTF-8로 저장하세요") from None
        import io
        try:
            return pd.read_csv(io.StringIO(text), header=None, dtype=str, keep_default_na=False)
        except pd.errors.ParserError:
            # 줄마다 칸 수가 다른 파일(표 위에 제목 줄이 있는 통계표 등) — 가장 긴 줄에 맞춰 빈칸으로 채운다. 빈 줄은 위와 같이 건너뛴다
            import csv
            rows = [r for r in csv.reader(io.StringIO(text)) if r]
            width = max((len(r) for r in rows), default=0)
            return pd.DataFrame([r + [""] * (width - len(r)) for r in rows], dtype=str)
    sheet = spec.sheet
    if isinstance(sheet, int):
        sheet = sheet - 1
    try:
        return pd.read_excel(spec.path, sheet_name=0 if sheet is None else sheet, header=None, dtype=object)
    except ValueError as e:
        raise ValueError(f"{spec.file}: 시트 {spec.sheet!r}를 열 수 없습니다 — {e}") from None


def _cell_text(v) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return ""
    if isinstance(v, (pd.Timestamp,)):
        return v.strftime("%Y-%m-%d")
    return str(v).strip()


def _time_index(grid: pd.DataFrame, names: List[str], spec: SourceSpec) -> int:
    tc = spec.time_col
    if tc is None:
        return 0
    if isinstance(tc, int):
        if not 1 <= tc <= grid.shape[1]:
            raise ValueError(f"{spec.file}: time_col {tc} — 1~{grid.shape[1]}")
        return tc - 1
    s = str(tc).strip()
    if s in names:
        return names.index(s)
    if re.fullmatch(r"[A-Za-z]{1,3}", s):
        k = 0
        for ch in s.upper():
            k = k * 26 + (ord(ch) - 64)
        if 1 <= k <= grid.shape[1]:
            return k - 1
    raise ValueError(f"{spec.file}: 시점 열 {tc!r}가 없습니다(열: {', '.join(names[:10])})")


def read_source(spec: SourceSpec) -> SourceTable:
    """불러오기 틀로 원자료를 읽는다. 문제는 ValueError(파일·줄·칸 위치와 함께)."""
    if spec.time_axis != "rows":
        raise ValueError(f"[source.{spec.name}] time_axis = {spec.time_axis!r} — 지금은 'rows'(시점이 행으로)만 읽습니다")
    if not os.path.isfile(spec.path):
        raise ValueError(f"[source.{spec.name}] 원자료 파일이 없습니다: {spec.file}")
    grid = _read_grid(spec)
    h = spec.header_row - 1
    if not 0 <= h < len(grid):
        raise ValueError(f"{spec.file}: header_row {spec.header_row} — 파일은 {len(grid)}줄")
    names = [_cell_text(v) or f"열{col_letter(k)}" for k, v in enumerate(grid.iloc[h].tolist())]
    dup = sorted({n for n in names if names.count(n) > 1})
    if dup:
        raise ValueError(f"{spec.file}: 같은 열 이름이 둘 이상 — {', '.join(dup)}")
    units = {}
    if spec.unit_row:
        u = spec.unit_row - 1
        if not 0 <= u < len(grid):
            raise ValueError(f"{spec.file}: unit_row {spec.unit_row} — 파일은 {len(grid)}줄")
        units = {names[k]: _cell_text(v) for k, v in enumerate(grid.iloc[u].tolist()) if _cell_text(v)}
    start = max(h, (spec.unit_row or 0) - 1) + 1
    body = grid.iloc[start:]
    tcol = _time_index(grid, names, spec)
    # 끝의 빈 줄은 버린다(시점 칸이 빈 줄)
    tvals = [_cell_text(v) for v in body.iloc[:, tcol].tolist()]
    keep = [k for k, t in enumerate(tvals) if t]
    if not keep:
        raise ValueError(f"{spec.file}: 시점 칸이 모두 비었습니다(시점 열 {col_letter(tcol)})")
    last = keep[-1]
    gaps = [k for k in range(last + 1) if not tvals[k]]
    if gaps:
        r = start + gaps[0] + 1
        raise ValueError(f"{spec.file}: {r}줄의 시점 칸({col_letter(tcol)}{r})이 비었습니다")
    body = body.iloc[:last + 1]
    labels = [normalize_label(t) for t in tvals[:last + 1]]
    idx = parse_dates(labels)
    if idx is None:
        bad = next((k for k, lab in enumerate(labels) if parse_dates([lab]) is None), 0)
        r = start + bad + 1
        raise ValueError(f"{spec.file}: 시점으로 읽을 수 없습니다 — {col_letter(tcol)}{r} {tvals[bad]!r} "
                         "(2003Q4 · 2003-10 · 2003 · 2003-10-01 · 2003년 4분기 꼴)")
    miss = {m.strip() for m in spec.missing if str(m).strip()}
    cols, missing_cells, bad_cells = {}, [], []
    for k, nm in enumerate(names):
        if k == tcol:
            continue
        vals = np.full(len(body), np.nan)
        for i, v in enumerate(body.iloc[:, k].tolist()):
            if isinstance(v, (int, float, np.integer, np.floating)) and not isinstance(v, bool):
                vals[i] = float(v)
                continue
            t = _cell_text(v)
            if not t:
                continue
            ref = f"{col_letter(k)}{start + i + 1}"
            if t in miss:
                missing_cells.append(f"{ref} {t!r}")
                continue
            u = t.replace(spec.thousands, "") if spec.thousands else t
            neg = u.startswith("(") and u.endswith(")")
            if neg:
                u = u[1:-1]
            try:
                vals[i] = -float(u) if neg else float(u)
            except ValueError:
                bad_cells.append(f"{ref} {t!r}")
        cols[nm] = vals
    df = pd.DataFrame(cols, index=pd.DatetimeIndex(idx, name="date"))
    freq = normalize_freq(spec.freq) if spec.freq else infer_freq_code(df.index, allow_gaps=True)
    if freq is None:
        raise ValueError(f"{spec.file}: 주기를 알 수 없습니다 — [source.{spec.name}] freq = \"Q\"·\"M\"·\"A\"")
    df = regularize(df.sort_index(), freq)
    note = (f"{spec.name}: 시점 열 {col_letter(tcol)}('{tvals[0]}' 꼴) → {freq} "
            f"{format_period(df.index[0], freq)}~{format_period(df.index[-1], freq)}")
    return SourceTable(spec, df, freq, units, missing_cells, bad_cells, file_sha256(spec.path), note)
