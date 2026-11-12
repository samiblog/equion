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
import unicodedata
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
    # 2018 1/4 · 2018.1/4 · 2018/1/4 · 2018-1/4 — 통계표의 분기('/4'로 끝나면 분기다 — 날짜로 읽지 않는다)
    (re.compile(r"^(\d{4})\s*[.\s/\-]?\s*([1-4])\s*/\s*4\s*(?:분기)?$"), lambda m: f"{m[1]}Q{m[2]}"),
    (re.compile(r"^(\d{4})\s*[Qq]\s*([1-4])$"), lambda m: f"{m[1]}Q{m[2]}"),
    (re.compile(r"^(\d{4})\s*년\s*(\d{1,2})\s*월$"), lambda m: f"{m[1]}-{int(m[2]):02d}"),
    (re.compile(r"^(\d{4})\.(\d{2})$"), lambda m: f"{m[1]}-{m[2]}"),
    (re.compile(r"^(\d{4})\s*[.\-/ ]\s*[Mm]\s*(\d{1,2})$"), lambda m: f"{m[1]}-{int(m[2]):02d}"),
    (re.compile(r"^(\d{4})\s*년$"), lambda m: m[1]),
)
# 시점 칸 끝의 표시 — 잠정치 p) · (p) · 추정 e) · 별표 · 각주 번호 1) — 떼고 읽는다
_MARK = re.compile(r"\s*(?:\(\s*[pPeE]\s*\)|[pPeE]\s*\)|\*+|\(?\d{1,2}\))$|\s+[pPeE]$|(?<=\d)[pPeE]$")
# 반기(1/2 · 2/2 · 상반기 · 하반기)는 주기로 읽지 않는다 — 달로 잘못 읽히지 않게 따로 알린다
_HALF = re.compile(r"^(\d{4})\s*(?:년)?\s*(?:[.\s/\-]?\s*[12]\s*/\s*2|\s*[상하]\s*반기|\s*[HhSs]\s*[12])\s*(?:반기)?$")
# 기간처럼 보이는 칸(네 자리 해가 든 짧은 글) — 앞뒤의 글 열·각주를 건너뛸 때 이것은 건너뛰지 않는다
_YEARISH = re.compile(r"^\s*(?:1[89]|2[01])\d{2}(?!\d)")


def _yearish(text: str) -> bool:
    """기간처럼 보이나 — 네 자리 해(1800~2199)로 시작하는 짧은 글(전각 숫자도)."""
    t = unicodedata.normalize("NFKC", str(text or ""))
    return bool(t) and len(t) <= 24 and bool(_YEARISH.search(t))


def normalize_label(text) -> str:
    """흔한 시점 꼴을 기간 라벨로(2003.Q4 → 2003Q4 · 2003년 4/4분기 → 2003Q4 · 2003/4/4 → 2003Q4 · 2003년 10월 → 2003-10).
    끝의 잠정치·각주 표시(p) · * · 1))는 뗀다. 모르면 그대로."""
    s = unicodedata.normalize("NFKC", str(text)).strip()
    s = _MARK.sub("", s) if _yearish(s) else s
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
        # 줄 번호는 편집기의 줄 번호와 같게 — 빈 줄도 한 줄로 센다(끝의 빈 줄만 버린다). 줄마다 칸 수가 달라도(표 위의 제목 줄) 가장 긴 줄에 맞춘다
        import csv
        import io
        try:
            rows = [r for r in csv.reader(io.StringIO(text))]
        except csv.Error as e:
            raise ValueError(f"{spec.file}: csv로 읽을 수 없습니다 — {e}") from None
        while rows and not any(c.strip() for c in rows[-1]):
            rows.pop()
        width = max((len(r) for r in rows), default=0)
        if width == 1 and any(";" in r[0] or "\t" in r[0] for r in rows[:20] if r):
            raise ValueError(f"{spec.file}: 칸이 쉼표로 나뉘지 않았습니다(세미콜론·탭?) — 쉼표 csv나 xlsx로 저장하세요")
        return pd.DataFrame([r + [""] * (width - len(r)) for r in rows], dtype=str)
    sheet = spec.sheet
    if isinstance(sheet, int):
        sheet = sheet - 1
    try:
        return pd.read_excel(spec.path, sheet_name=0 if sheet is None else sheet, header=None, dtype=object)
    except ImportError as e:
        need = "xlrd" if ext == ".xls" else "openpyxl"
        raise ValueError(f"{spec.file}: 이 엑셀 파일을 읽는 패키지({need})가 없습니다 — xlsx로 저장하거나 {need}를 설치하세요({e})") from None
    except (KeyError, IndexError) as e:
        raise ValueError(f"{spec.file}: 시트 {spec.sheet!r}를 열 수 없습니다 — {e}") from None
    except ValueError as e:
        if "sheet" in str(e).lower():
            raise ValueError(f"{spec.file}: 시트 {spec.sheet!r}를 열 수 없습니다 — {e}") from None
        raise ValueError(f"{spec.file}: 엑셀 파일을 읽을 수 없습니다(깨졌거나 다른 형식) — {e}") from None
    except Exception as e:  # noqa: BLE001 — 깨진 파일(BadZipFile 등)도 칸 위치처럼 알기 쉬운 글로
        raise ValueError(f"{spec.file}: 엑셀 파일을 읽을 수 없습니다(깨졌거나 다른 형식) — {type(e).__name__}: {e}") from None


def _cell_text(v) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return ""
    if isinstance(v, (pd.Timestamp,)):
        return v.strftime("%Y-%m-%d")
    return str(v).strip()


def _time_text(v) -> str:
    """시점 칸의 글. 엑셀의 숫자 칸은 글로 바꿔 읽는다 — 2018.0 → '2018', 2018.1 → '2018.10'(10월: 숫자 칸에서 2018.10은 2018.1이 된다 —
    1월은 2018.01이다)."""
    if isinstance(v, (float, np.floating)) and np.isfinite(v):
        if float(v).is_integer():
            return str(int(v))
        if 1800 <= v < 2200 and round(v * 100) == round(v * 100, 6):
            return f"{v:.2f}"
    if isinstance(v, (int, np.integer)) and not isinstance(v, bool):
        return str(int(v))
    return _cell_text(v)


def _row_no(value, what: str) -> int:
    """줄 번호 하나(1부터, 정수 — 2.0은 2, 2.7·0·글은 오류)."""
    if isinstance(value, bool):
        raise ValueError(f"{what} {value!r} — 줄 번호(1부터)")
    try:
        f = float(str(value).strip()) if not isinstance(value, (int, float)) else float(value)
    except ValueError:
        raise ValueError(f"{what} {value!r} — 줄 번호(1부터 세는 정수)") from None
    if not f.is_integer() or f < 1:
        raise ValueError(f"{what} {value!r} — 줄 번호(1부터 세는 정수)")
    return int(f)


def row_list(value) -> List[int]:
    """줄 번호(1부터) 하나·여럿 → 목록. 3 · [3, 4] · "3,4" · "3-4" · "3:4". 여럿이면 위에서 아래 차례(겹치지 않게)."""
    if value in (None, ""):
        return [1]
    if isinstance(value, bool):
        raise ValueError(f"줄 번호 {value!r}")
    if isinstance(value, (int, float)):
        return [_row_no(value, "줄 번호")]
    if isinstance(value, (list, tuple)):
        out = [_row_no(v, "줄 번호") for v in value]
    else:
        text = str(value).strip()
        m = re.fullmatch(r"(\d+)\s*[-:~]\s*(\d+)", text)
        if m:
            a, b = int(m[1]), int(m[2])
            out = list(range(min(a, b), max(a, b) + 1))
        else:
            out = [_row_no(x, "줄 번호") for x in re.split(r"[,\s]+", text) if x]
    if not out:
        raise ValueError(f"줄 번호 {value!r} — 하나 이상")
    if any(b <= a for a, b in zip(out, out[1:])):
        raise ValueError(f"줄 번호 {value!r} — 여러 줄은 위에서 아래 차례로(예: 3,4)")
    return out


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


def _name_text(v) -> str:
    """이름 칸의 글 — 칸 안의 줄바꿈(Alt+Enter)은 빈칸 하나로."""
    return re.sub(r"\s*[\r\n]+\s*", " ", _cell_text(v))


def _names(work: pd.DataFrame, rows: List[int], label):
    """머리줄(하나·여럿) → (열마다 이름, 열마다 제 글이 있었나). 위 머리줄의 빈 칸은 왼쪽 값을 잇는다(병합 칸) — 다만 더 위 줄에서
    새 무리가 시작한 열부터는 잇지 않는다(세로 병합 · 무리의 경계). 같은 글이 겹치면 하나만."""
    width = work.shape[1]
    parts = [[_name_text(work.iat[r, k]) for k in range(width)] for r in rows]
    own = [[bool(x) for x in line] for line in parts]
    for i, line in enumerate(parts[:-1]):
        last = ""
        for k in range(width):
            if own[i][k]:
                last = line[k]
            elif any(own[j][k] for j in range(i)):
                last = ""                       # 위 줄에 새 무리가 시작한 열 — 앞 무리의 글을 잇지 않는다
            else:
                line[k] = last
    out = []
    for k in range(width):
        bits = [p[k] for p in parts if p[k]]
        bits = [b for j, b in enumerate(bits) if j == 0 or b != bits[j - 1]]
        out.append(" ".join(bits) or f"열{label(k)}")
    return out, [any(o[k] for o in own) for k in range(width)]


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
        if isinstance(names_at, str) and "," in names_at:
            names_at = [x.strip() for x in names_at.split(",") if x.strip()]
        hdr = [col_index(c, grid.shape[1], "name_col") for c in (names_at if isinstance(names_at, (list, tuple)) else [names_at])]
        unit = col_index(spec.unit_col, grid.shape[1], "unit_col") if spec.unit_col not in (None, "") else None
        trow = _row_no(spec.time_row if spec.time_row not in (None, "") else 1, "time_row") - 1
        if not 0 <= trow < len(grid):
            raise ValueError(f"{spec.file}: time_row {spec.time_row} — 파일은 {len(grid)}줄")
        return work, hdr, unit, trow, (lambda r, c: f"{col_letter(r)}{c + 1}"), (lambda c: f"{c + 1}줄")
    rows = row_list(spec.header_row)
    for r in rows:
        if not 1 <= r <= len(grid):
            raise ValueError(f"{spec.file}: header_row {r} — 파일은 {len(grid)}줄")
    unit = None
    if spec.unit_row:
        unit = _row_no(spec.unit_row, "unit_row") - 1
        if not 0 <= unit < len(grid):
            raise ValueError(f"{spec.file}: unit_row {spec.unit_row} — 파일은 {len(grid)}줄")
    return grid, [r - 1 for r in rows], unit, None, (lambda r, c: f"{col_letter(c)}{r + 1}"), col_letter


def _is_number(v, thousands=None) -> bool:
    """칸이 수인가 — 엑셀의 수 칸, 또는 수로 읽히는 글(천 단위 글자·괄호 음수 포함)."""
    if isinstance(v, bool):
        return False
    if isinstance(v, (int, float, np.integer, np.floating)):
        return bool(np.isfinite(v))
    t = _cell_text(v)
    if not t:
        return False
    if thousands:
        t = t.replace(thousands, "")
    if t.startswith("(") and t.endswith(")"):
        t = t[1:-1]
    try:
        float(t)
        return True
    except ValueError:
        return False


def _unit_problem(spec: SourceSpec, work: pd.DataFrame, unit: int, tcol: int, cols: List[int], ref, columns: bool) -> Optional[str]:
    """단위 줄(열)이 단위가 아니라 값 줄로 보이면 까닭 — 시점 칸이 기간이거나, 채운 칸이 모두 수. 단위 줄이 빠진 파일을 그대로 읽으면
    첫 기간이 단위로 읽혀 말없이 사라진다(D62 — 조용히 잘못 읽는 것이 가장 나쁘다)."""
    t = _time_text(work.iat[unit, tcol])
    filled = [(k, work.iat[unit, k]) for k in cols if _cell_text(work.iat[unit, k])]
    nums = [(k, v) for k, v in filled if _is_number(v, spec.thousands)]
    looks_time = bool(t) and _yearish(t) and parse_dates([normalize_label(t)]) is not None
    if not looks_time and not (filled and len(nums) == len(filled)):
        return None
    where = (f"단위 열({col_letter(unit)}열 — unit_col = {spec.unit_col!r})" if columns else
             f"단위 줄({unit + 1}줄 — unit_row = {spec.unit_row})")
    seen = ([f"{ref(unit, tcol)} {t!r}"] if t else []) + [f"{ref(unit, k)} {_cell_text(v)!r}" for k, v in nums[:2]]
    return (f"{spec.file}: {where}에 단위가 아니라 값이 있습니다 — {', '.join(seen)}. 단위 {'열' if columns else '줄'}이 빠진 파일로 "
            f"보입니다(그대로 읽으면 첫 기간이 단위로 읽혀 사라집니다). 단위 {'열' if columns else '줄'}이 있는 파일로 다시 받거나, 이제부터 "
            f"없다면 [source.{spec.name}]의 {'unit_col' if columns else 'unit_row'}를 지운 틀로 읽으세요"
            f"(먼저 equion data preview {os.path.basename(spec.file)}{' --time-axis columns' if columns else ''}로 확인)")


def read_source(spec: SourceSpec) -> SourceTable:
    """불러오기 틀로 원자료를 읽는다. 문제는 ValueError(파일·줄·칸 위치와 함께)."""
    axis = str(spec.time_axis or "rows").strip().lower()
    if axis not in ("rows", "columns"):
        raise ValueError(f"[source.{spec.name}] time_axis = {spec.time_axis!r} — 'rows'(시점이 행으로) · 'columns'(시점이 열로)")
    if axis != spec.time_axis:
        from dataclasses import replace
        spec = replace(spec, time_axis=axis)
    if not os.path.isfile(spec.path):
        raise ValueError(f"[source.{spec.name}] 원자료 파일이 없습니다: {spec.file}")
    grid = _read_grid(spec)
    if grid.shape[0] == 0 or grid.shape[1] == 0:
        raise ValueError(f"{spec.file}: 빈 파일입니다")
    columns = axis == "columns"
    work, hdr, unit, tcol, ref, place = _layout(spec, grid)
    label = (lambda k: f"{k + 1}줄") if columns else col_letter
    names, own = _names(work, hdr, label)
    if tcol is None:
        tcol = _time_index(work, names, spec)
    unused = ([k for k, v in (("unit_row", spec.unit_row), ("time_col", spec.time_col)) if v not in (None, "")]
              + (["header_row"] if spec.header_row not in (None, "", 1, [1]) else [])) if columns else \
        [k for k, v in (("time_row", spec.time_row), ("name_col", spec.name_col), ("unit_col", spec.unit_col)) if v not in (None, "", [])]
    if columns:
        named = set(hdr + ([unit] if unit is not None else []))
        first_time = next((r for r in range(work.shape[0]) if r not in named and _yearish(_time_text(work.iat[r, tcol]))), None)
        late = [k for k in sorted(named) if first_time is not None and k > first_time]
        if late:
            raise ValueError(f"{spec.file}: 이름 열·단위 열({', '.join(col_letter(k) for k in late)})은 시점이 시작하는 열"
                             f"({col_letter(first_time)})보다 왼쪽에 있어야 합니다")
    series_cols = [k for k in range(work.shape[1]) if k != tcol and (not columns or k > tcol)]
    if unit is not None:
        why = _unit_problem(spec, work, unit, tcol, series_cols, ref, columns)
        if why:
            raise ValueError(why)
    start = max(hdr + ([unit] if unit is not None else [])) + 1
    body = work.iloc[start:]
    # 아주 빈 줄(rows) · 빈 열(columns)은 건너뛴다 — 줄 번호·칸 위치는 원래 표 그대로 센다
    blank = (body.isna() | body.astype(str).apply(lambda s: s.str.strip().eq(""))).all(axis=1).tolist()
    pos = [i for i in range(len(body)) if not blank[i]]
    tvals = [_time_text(body.iat[i, tcol]) for i in pos]
    skipped, tail = [], []
    where_t = (lambda i: col_letter(start + i)) if columns else (lambda i: str(start + i + 1))
    if columns:                                     # 시점 줄의 앞쪽 글 열(단위 · 비고 …)은 건너뛴다 — 기간처럼 보이는 칸부터
        while pos and not _yearish(tvals[0]):
            if unit is None and tvals[0].strip().lower() in ("단위", "unit", "units"):
                unit = start + pos[0]               # 시점 줄에 '단위'라고 적힌 열 — 단위 열로 읽는다
            if tvals[0]:
                skipped.append(where_t(pos[0]))
            pos, tvals = pos[1:], tvals[1:]
    # 끝의 시점 칸이 빈 줄은 버리고, 끝의 글(합계 · 각주 '주: …')은 건너뛴다
    while pos and not _yearish(tvals[-1]):
        if tvals[-1]:
            tail.append(where_t(pos[-1]))
        pos, tvals = pos[:-1], tvals[:-1]
    if not pos:
        seen = [(i, _time_text(body.iat[i, tcol])) for i in range(len(body)) if _time_text(body.iat[i, tcol])]
        what = f"시점 {'줄 ' + str(tcol + 1) if columns else '열 ' + col_letter(tcol)}"
        if seen:
            i, t = seen[0]
            raise ValueError(f"{spec.file}: {what}에서 기간을 찾지 못했습니다 — 처음 칸 {ref(start + i, tcol)} {t!r} "
                             "(2003Q4 · 2003-10 · 2003 · 2003년 4분기 · 2003 4/4 꼴)")
        raise ValueError(f"{spec.file}: 시점 칸이 모두 비었습니다({what})")
    gaps = [j for j, t in enumerate(tvals) if not t]
    if gaps:
        i = pos[gaps[0]]
        at = f"{col_letter(start + i)}열" if columns else f"{start + i + 1}줄"
        raise ValueError(f"{spec.file}: {at}의 시점 칸({ref(start + i, tcol)})이 비었습니다")
    for j, t in enumerate(tvals):
        if _HALF.match(_MARK.sub("", unicodedata.normalize("NFKC", t).strip())):
            raise ValueError(f"{spec.file}: 반기 표기는 주기로 읽지 않습니다 — {ref(start + pos[j], tcol)} {t!r} (분기·월·연만)")
    labels = [normalize_label(t) for t in tvals]
    idx = parse_dates(labels)
    if idx is None:
        bad = next((j for j, lab in enumerate(labels) if parse_dates([lab]) is None), 0)
        raise ValueError(f"{spec.file}: 시점으로 읽을 수 없습니다 — {ref(start + pos[bad], tcol)} {tvals[bad]!r} "
                         "(2003Q4 · 2003-10 · 2003 · 2003-10-01 · 2003년 4분기 · 2003 4/4 꼴)")
    idx = pd.DatetimeIndex(idx)
    odd = [j for j, y in enumerate(idx.year) if not 1800 <= y <= 2200]
    if odd:
        j = odd[0]
        raise ValueError(f"{spec.file}: 시점을 읽은 해가 맞지 않습니다 — {ref(start + pos[j], tcol)} {tvals[j]!r} → {idx[j].year}년 "
                         "(해를 네 자리로: 2018-01 · 2018년 1월)")
    dupe = idx.duplicated(keep=False)
    if dupe.any():
        js = [j for j in range(len(idx)) if dupe[j]][:2]
        raise ValueError(f"{spec.file}: 같은 기간이 둘 이상 — " + " · ".join(f"{ref(start + pos[j], tcol)} {tvals[j]!r}" for j in js))
    if unit is not None:
        units = {names[k]: _cell_text(work.iat[unit, k]) for k in series_cols if _cell_text(work.iat[unit, k])}
    else:
        units = {}
    miss = {m.strip() for m in spec.missing if str(m).strip()}
    cols, missing_cells, bad_cells = {}, [], []
    places, positions, missing_by, bad_by = {}, {}, {}, {}
    empty_named = []
    for k in series_cols:
        nm = names[k]
        vals = np.full(len(pos), np.nan)
        nmiss = nbad = 0
        mc, bc = [], []
        for j, i in enumerate(pos):
            v = body.iat[i, k]
            if isinstance(v, (int, float, np.integer, np.floating)) and not isinstance(v, bool):
                vals[j] = float(v)
                continue
            t = _cell_text(v)
            if not t:
                continue
            cell = ref(start + i, k)
            if t in miss:
                mc.append(f"{cell} {t!r}")
                nmiss += 1
                continue
            u = t.replace(spec.thousands, "") if spec.thousands else t
            neg = u.startswith("(") and u.endswith(")")
            if neg:
                u = u[1:-1]
            try:
                vals[j] = -float(u) if neg else float(u)
            except ValueError:
                bc.append(f"{cell} {t!r}")
                nbad += 1
        if not np.isfinite(vals).any() and not nmiss and not nbad and (columns or not own[k]):
            if own[k]:
                empty_named.append(place(k))          # 값이 하나도 없는 줄(무리 제목 · 각주) — 시리즈가 아니다
            continue                                  # 이름도 값도 없는 줄·열(빈 칸 · 사이 열)
        cols.setdefault(nm, []).append(vals)
        missing_cells += mc
        bad_cells += bc
        places[nm], positions[nm] = place(k), k
        missing_by[nm], bad_by[nm] = nmiss, nbad
    dup = sorted(n for n, v in cols.items() if len(v) > 1)
    if dup:
        raise ValueError(f"{spec.file}: 같은 {'시리즈 이름' if columns else '열 이름'}이 둘 이상 — {', '.join(dup)}"
                         + (" (이름 열을 더 고르면 이어 붙인다)" if columns else " (머리줄을 여럿 고르면 이어 붙인다)"))
    df = pd.DataFrame({n: v[0] for n, v in cols.items()}, index=pd.DatetimeIndex(idx, name="date")).sort_index()
    freq = normalize_freq(spec.freq) if spec.freq else infer_freq_code(df.index, allow_gaps=True)
    if freq is None:
        raise ValueError(f"{spec.file}: 주기를 알 수 없습니다 — [source.{spec.name}] freq = \"Q\"·\"M\"·\"A\"")
    df = regularize(df, freq)
    where = f"시점 줄 {tcol + 1}" if columns else f"시점 열 {col_letter(tcol)}"
    note = (f"{spec.name}: {where}('{tvals[0]}' 꼴) → {freq} "
            f"{format_period(df.index[0], freq)}~{format_period(df.index[-1], freq)}"
            + (f" · 시리즈 {len(cols)}줄(시점이 열로 가는 표)" if columns else "")
            + (f" · 글 열 {', '.join(skipped)} 건너뜀" if skipped else "")
            + (f" · 끝의 글 {'열' if columns else '줄'} {', '.join(reversed(tail))} 건너뜀" if tail else "")
            + (f" · 값이 없는 {'줄' if columns else '열'} {', '.join(empty_named[:6])}{' …' if len(empty_named) > 6 else ''} 건너뜀"
               if empty_named else "")
            + (f" · 열 이름은 {len(hdr)}줄을 이어 붙임" if not columns and len(hdr) > 1 else "")
            + (f" · {'columns' if columns else 'rows'} 방향이라 쓰지 않은 것: {', '.join(unused)}" if unused else ""))
    return SourceTable(spec, df, freq, units, missing_cells, bad_cells, file_sha256(spec.path), note, places, positions,
                       missing_by, bad_by, int(tcol))
