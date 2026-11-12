#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""원자료를 '불러오기 틀'로 읽는다 (D34) — 받은 파일은 고치지 않고, 어느 칸을 어떻게 읽을지만 정한다.

불러오기 틀(`series.toml`의 `[source.이름]`):

    file         원자료 파일(csv·xlsx·xls)
    sheet        엑셀 시트 이름 또는 번호(1부터, 기본 첫 시트)
    header_row   열 이름 줄(1부터, 기본 1) — 여러 줄이면 [3, 4](위 줄의 병합 칸은 오른쪽으로 이어 붙여 '국내총생산 실질' 꼴)
    unit_row     단위 줄(선택)
    time_col     시점 열 — 열 이름 · 엑셀 열 글자(A) · 번호(1부터). 기본 첫 열
    time_axis    'rows'(시점이 행으로 내려간다, 기본) · 'columns'(시점이 열로 간다 — 줄마다 시리즈 하나인 통계표)
    time_row     (columns) 시점이 적힌 줄(1부터, 기본 1) — 그 아래 줄들이 시리즈
    name_col     (columns) 시리즈 이름 열(A·번호, 기본 첫 열) — 여러 열이면 ["A", "B"](이어 붙인다)
    unit_col     (columns) 단위 열(선택)
    missing      결측으로 볼 표시(예: ["–", "…", "x"]) — 빈 칸은 늘 결측
    thousands    천 단위 구분 글자(예: ",")
    freq         주기를 직접 정할 때 'Q' · 'M' · 'A'(기본: 시점에서 추론)

시점 꼴은 기간 라벨(2003Q4 · 2003M10 · 2003-10 · 2003)과 ISO 날짜, 그리고 흔한 꼴(2003.Q4 · 2003 Q4 · 2003년 4분기 ·
2003년 4/4분기 · 2003 4/4 · 2003년 10월 · 2003.10)을 읽는다. 숫자가 아닌 칸은 결측으로 보고 칸 위치(C42)와 함께 알린다.
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
    header_row: object = 1            # 줄 번호 하나 또는 여럿([3, 4])
    unit_row: Optional[int] = None
    time_col: object = None
    time_axis: str = "rows"
    time_row: Optional[int] = None    # time_axis = "columns" — 시점이 적힌 줄
    name_col: object = None           # time_axis = "columns" — 시리즈 이름 열(하나 또는 여럿)
    unit_col: object = None           # time_axis = "columns" — 단위 열
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
    places: Dict[str, str] = field(default_factory=dict)      # 시리즈 → 원래 표의 자리('C' 열 · '12줄')
    positions: Dict[str, int] = field(default_factory=dict)   # 시리즈 → 원래 표의 열 번호(rows) · 줄 번호(columns), 0부터
    missing_by: Dict[str, int] = field(default_factory=dict)  # 시리즈마다 결측 표시로 읽은 칸 수
    bad_by: Dict[str, int] = field(default_factory=dict)      # 시리즈마다 숫자가 아닌 칸 수
    time_pos: int = 0               # 시점 열(rows) · 시점 줄(columns)의 자리, 0부터

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
    (re.compile(r"^(\d{4})\s*[.\s]\s*([1-4])\s*/\s*4\s*(?:분기)?$"), lambda m: f"{m[1]}Q{m[2]}"),     # 2018 1/4 · 2018.1/4 — 통계표의 분기
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


def row_list(value) -> List[int]:
    """줄 번호(1부터) 하나·여럿 → 목록. 3 · [3, 4] · "3,4" · "3-4" · "3:4"."""
    if value in (None, ""):
        return [1]
    if isinstance(value, bool):
        raise ValueError(f"줄 번호 {value!r}")
    if isinstance(value, int):
        return [value]
    if isinstance(value, (list, tuple)):
        return [int(v) for v in value]
    text = str(value).strip()
    m = re.fullmatch(r"(\d+)\s*[-:~]\s*(\d+)", text)
    if m:
        a, b = int(m[1]), int(m[2])
        return list(range(min(a, b), max(a, b) + 1))
    return [int(x) for x in re.split(r"[,\s]+", text) if x]


def col_index(value, width: int, what: str = "열") -> int:
    """열 하나(엑셀 글자 A · 번호 1부터) → 0부터의 자리."""
    if isinstance(value, bool):
        raise ValueError(f"{what} {value!r}")
    if isinstance(value, int) or (isinstance(value, str) and value.strip().isdigit()):
        k = int(value) - 1
    elif isinstance(value, str) and re.fullmatch(r"[A-Za-z]{1,3}", value.strip()):
        k = 0
        for ch in value.strip().upper():
            k = k * 26 + (ord(ch) - 64)
        k -= 1
    else:
        raise ValueError(f"{what} {value!r} — 엑셀 열 글자(A) 또는 번호(1부터)")
    if not 0 <= k < width:
        raise ValueError(f"{what} {value!r} — 표는 {col_letter(width - 1)}열까지")
    return k


def _names(work: pd.DataFrame, rows: List[int], label) -> List[str]:
    """머리줄(하나·여럿) → 열마다 이름. 위 머리줄의 빈 칸은 왼쪽 값을 잇는다(병합 칸) — 같은 글이 겹치면 하나만."""
    width = work.shape[1]
    parts = [[_cell_text(work.iat[r, k]) for k in range(width)] for r in rows]
    for line in parts[:-1]:
        last = ""
        for k in range(width):
            if line[k]:
                last = line[k]
            else:
                line[k] = last
    out = []
    for k in range(width):
        bits = [p[k] for p in parts if p[k]]
        bits = [b for j, b in enumerate(bits) if j == 0 or b != bits[j - 1]]
        out.append(" ".join(bits) or f"열{label(k)}")
    return out


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


def _layout(spec: SourceSpec, grid: pd.DataFrame):
    """방향에 따라 → (작업 표, 머리줄들, 단위 줄, 시점 열(작업 표의 자리 — rows면 None: 이름으로 찾는다), 칸 이름 함수, 시리즈 자리 이름).
    작업 표는 늘 '시점이 행으로 내려가는' 꼴이다 — 시점이 열로 가는 표는 뒤집어 읽는다(칸 자리는 원래 표 기준으로 알린다)."""
    if spec.time_axis == "columns":
        work = grid.T.reset_index(drop=True)
        work.columns = range(work.shape[1])
        names_at = spec.name_col if spec.name_col not in (None, "", []) else ["A"]
        hdr = [col_index(c, grid.shape[1], "name_col") for c in (names_at if isinstance(names_at, (list, tuple)) else [names_at])]
        unit = col_index(spec.unit_col, grid.shape[1], "unit_col") if spec.unit_col not in (None, "") else None
        trow = int(spec.time_row or 1) - 1
        if not 0 <= trow < len(grid):
            raise ValueError(f"{spec.file}: time_row {spec.time_row} — 파일은 {len(grid)}줄")
        return work, hdr, unit, trow, (lambda r, c: f"{col_letter(r)}{c + 1}"), (lambda c: f"{c + 1}줄")
    rows = row_list(spec.header_row)
    for r in rows:
        if not 1 <= r <= len(grid):
            raise ValueError(f"{spec.file}: header_row {r} — 파일은 {len(grid)}줄")
    unit = None
    if spec.unit_row:
        unit = spec.unit_row - 1
        if not 0 <= unit < len(grid):
            raise ValueError(f"{spec.file}: unit_row {spec.unit_row} — 파일은 {len(grid)}줄")
    return grid, [r - 1 for r in rows], unit, None, (lambda r, c: f"{col_letter(c)}{r + 1}"), col_letter


def read_source(spec: SourceSpec) -> SourceTable:
    """불러오기 틀로 원자료를 읽는다. 문제는 ValueError(파일·줄·칸 위치와 함께)."""
    if spec.time_axis not in ("rows", "columns"):
        raise ValueError(f"[source.{spec.name}] time_axis = {spec.time_axis!r} — 'rows'(시점이 행으로) · 'columns'(시점이 열로)")
    if not os.path.isfile(spec.path):
        raise ValueError(f"[source.{spec.name}] 원자료 파일이 없습니다: {spec.file}")
    grid = _read_grid(spec)
    columns = spec.time_axis == "columns"
    work, hdr, unit, tcol, ref, place = _layout(spec, grid)
    label = (lambda k: f"{k + 1}줄") if columns else col_letter
    names = _names(work, hdr, label)
    if tcol is None:
        tcol = _time_index(work, names, spec)
    series_cols = [k for k in range(work.shape[1]) if k != tcol and (not columns or k > tcol)]
    taken = [names[k] for k in series_cols]
    dup = sorted({n for n in taken if taken.count(n) > 1})
    if dup:
        raise ValueError(f"{spec.file}: 같은 {'시리즈 이름' if columns else '열 이름'}이 둘 이상 — {', '.join(dup)}"
                         + (" (이름 열을 더 고르면 이어 붙인다)" if columns else " (머리줄을 여럿 고르면 이어 붙인다)"))
    units = {}
    if unit is not None:
        units = {names[k]: _cell_text(work.iat[unit, k]) for k in series_cols if _cell_text(work.iat[unit, k])}
    start = max(hdr + ([unit] if unit is not None else [])) + 1
    body = work.iloc[start:]
    # 끝의 빈 줄은 버린다(시점 칸이 빈 줄)
    tvals = [_cell_text(v) for v in body.iloc[:, tcol].tolist()]
    skipped = []
    if columns:                                     # 시점 줄의 앞쪽 글 열(단위 · 비고 …)은 건너뛴다 — 첫 시점부터
        while tvals and (not tvals[0] or parse_dates([normalize_label(tvals[0])]) is None) and len(skipped) < 6:
            if unit is None and tvals[0].strip().lower() in ("단위", "unit", "units"):
                unit = start                        # 시점 줄에 '단위'라고 적힌 열 — 단위 열로 읽는다
                units = {names[k]: _cell_text(work.iat[unit, k]) for k in series_cols if _cell_text(work.iat[unit, k])}
            skipped.append(col_letter(start))
            start += 1
            tvals = tvals[1:]
        body = work.iloc[start:]
    keep = [k for k, t in enumerate(tvals) if t]
    if not keep:
        raise ValueError(f"{spec.file}: 시점 칸이 모두 비었습니다(시점 {'줄 ' + str(tcol + 1) if columns else '열 ' + col_letter(tcol)})")
    last = keep[-1]
    gaps = [k for k in range(last + 1) if not tvals[k]]
    if gaps:
        at = f"{col_letter(start + gaps[0])}열" if columns else f"{start + gaps[0] + 1}줄"
        raise ValueError(f"{spec.file}: {at}의 시점 칸({ref(start + gaps[0], tcol)})이 비었습니다")
    body = body.iloc[:last + 1]
    labels = [normalize_label(t) for t in tvals[:last + 1]]
    idx = parse_dates(labels)
    if idx is None:
        bad = next((k for k, lab in enumerate(labels) if parse_dates([lab]) is None), 0)
        raise ValueError(f"{spec.file}: 시점으로 읽을 수 없습니다 — {ref(start + bad, tcol)} {tvals[bad]!r} "
                         "(2003Q4 · 2003-10 · 2003 · 2003-10-01 · 2003년 4분기 꼴)")
    miss = {m.strip() for m in spec.missing if str(m).strip()}
    cols, missing_cells, bad_cells = {}, [], []
    places, positions, missing_by, bad_by = {}, {}, {}, {}
    for k in series_cols:
        nm = names[k]
        vals = np.full(len(body), np.nan)
        nmiss = nbad = 0
        for i, v in enumerate(body.iloc[:, k].tolist()):
            if isinstance(v, (int, float, np.integer, np.floating)) and not isinstance(v, bool):
                vals[i] = float(v)
                continue
            t = _cell_text(v)
            if not t:
                continue
            cell = ref(start + i, k)
            if t in miss:
                missing_cells.append(f"{cell} {t!r}")
                nmiss += 1
                continue
            u = t.replace(spec.thousands, "") if spec.thousands else t
            neg = u.startswith("(") and u.endswith(")")
            if neg:
                u = u[1:-1]
            try:
                vals[i] = -float(u) if neg else float(u)
            except ValueError:
                bad_cells.append(f"{cell} {t!r}")
                nbad += 1
        if columns and nm.startswith("열") and not np.isfinite(vals).any() and not nmiss and not nbad:
            continue                                  # 이름도 값도 없는 줄(빈 줄)
        cols[nm] = vals
        places[nm], positions[nm] = place(k), k
        missing_by[nm], bad_by[nm] = nmiss, nbad
    df = pd.DataFrame(cols, index=pd.DatetimeIndex(idx, name="date"))
    freq = normalize_freq(spec.freq) if spec.freq else infer_freq_code(df.index, allow_gaps=True)
    if freq is None:
        raise ValueError(f"{spec.file}: 주기를 알 수 없습니다 — [source.{spec.name}] freq = \"Q\"·\"M\"·\"A\"")
    df = regularize(df.sort_index(), freq)
    where = f"시점 줄 {tcol + 1}" if columns else f"시점 열 {col_letter(tcol)}"
    note = (f"{spec.name}: {where}('{tvals[0]}' 꼴) → {freq} "
            f"{format_period(df.index[0], freq)}~{format_period(df.index[-1], freq)}"
            + (f" · 시리즈 {len(cols)}줄(시점이 열로 가는 표)" if columns else "")
            + (f" · 글 열 {', '.join(skipped)} 건너뜀" if skipped else "")
            + (f" · 열 이름은 {len(hdr)}줄을 이어 붙임" if not columns and len(hdr) > 1 else ""))
    return SourceTable(spec, df, freq, units, missing_cells, bad_cells, file_sha256(spec.path), note, places, positions,
                       missing_by, bad_by, int(tcol))
