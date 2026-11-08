#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""워크파일 — 시계열 데이터·표본·이름 붙은 객체를 담는 작업 단위 (라이브러리 1단계, D2).

    import equion as eqn
    wf = eqn.wfopen("data.xlsx")                         # 주기는 자동 추론(예제 자료: eqn.datasets.load("toy_q"))
    wf.smpl("1975Q1", "2019Q4")                          # 추정·풀이·genr의 기본 구간
    wf.genr("YD = Y - G")                                # 방정식 DSL 식 그대로
    wf["GAP"] = some_pandas_series                       # 아무 Python 계산이나
    eq = wf.equation("eq_cn").ls("CN c YD CN(-1)")
    m = wf.model("toy").merge(eq).append("…")
    m.solve()                                            # → CN_0 … 시리즈
    wf.save("toy")                                       # → toy.eqw/

작업 흐름은 EViews 사용자에게 익숙하게 만든 독립 구현이다(DECISIONS D13).
"""

import io
import json
import math
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
import pandas as pd

from ..data.dataset import Data
from ..data.store import read_frame, write_frame
from ..estimation.equation import Equation, expand_indicators
from ..formula import ir
from ..formula.ast_formula import canonicalize_columns
from ..formula.parser import DSLError, convert_at_functions, normalize, reserved_name_error, split_equation
from ..version import ENGINE_VERSION
from ..data.periods import FREQ_LABEL as _FREQ_LABEL
from ..data.periods import (PERIODS_PER_YEAR, format_period, infer_freq_code, normalize_freq, parse_period,
                            period_starts, to_period)
from ..worktable.worktable import WorkTable
from ..worktable._serial import _jsonable, _read_json, _write_json
from .objects import EquationObject, GraphObject, ModelObject, ScenarioObject, TableObject
from .sysobj import SystemObject
from .varobj import VARObject, VECMObject
from .output import TableOutput, say, spool
from .runtime import apply_default_smpl, quiet, record_input, record_output

FORMAT = "equion-workfile"
LEGACY_FORMATS = ("macromodel-workfile",)  # 0.5.0 이전(패키지 이름 변경 전) 워크파일
FORMAT_VERSION = 2  # 2: 자료를 .npz로(1: parquet — 계속 읽음)
EXT = ".eqw"
LEGACY_EXTS = (".mmw",)  # 0.5.0 이전 확장자 — 읽기만
_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class Workfile:
    """시계열(시리즈)·표본·객체(방정식·모델·그래프·표)를 담는 작업 단위."""

    def __init__(self, wt: WorkTable, name: str = None):
        self._wt = wt
        self.name = name or wt.name
        self._objects: Dict[str, Any] = {}
        self._smpl: Optional[Tuple[Optional[pd.Period], Optional[pd.Period]]] = None
        self._meta: Dict[str, Dict[str, Any]] = {}      # 시리즈 → 메타데이터(desc·unit·source·notes·agg …)
        self._pages: Dict[str, "Workfile"] = {}          # 다른 주기 페이지(이름 → 워크파일)

    # ------------------------------------------------------------------
    # 기본 정보
    # ------------------------------------------------------------------
    @property
    def freq(self) -> str:
        """주기 코드: 'Q'(분기) · 'M'(월) · 'A'(연)."""
        return self._wt.freq

    @property
    def _data(self) -> Data:
        return self._wt.data

    @property
    def data(self) -> pd.DataFrame:
        """전체 시리즈 DataFrame(읽기 용도 — 바꿀 때는 wf['X'] = … 또는 genr)."""
        return self._wt.data.data

    @property
    def index(self) -> pd.DatetimeIndex:
        """기간 첫날의 날짜 인덱스(pandas DatetimeIndex, freq 없음)."""
        return self.data.index

    def _label(self, ts) -> str:
        return format_period(ts, self.freq)

    def __repr__(self):
        idx = self.index
        span = f"{self._label(idx[0])}~{self._label(idx[-1])}" if len(idx) else "-"
        s = self.smpl()
        return (f"<워크파일 {self.name}: {_FREQ_LABEL[self.freq]} {span} · 시리즈 {len(self.data.columns)} · "
                f"객체 {len(self._objects)} · smpl {s[0]}~{s[1]}>")

    def _repr_html_(self):
        return self.objects().html()

    # ------------------------------------------------------------------
    # 표본(smpl)
    # ------------------------------------------------------------------
    def smpl(self, start=None, end=None):
        """표본 설정·조회 — 추정(ls 등)·풀이(solve)·genr·그래프의 기본 구간.

        `wf.smpl("2000Q1", "2019Q4")` · `wf.smpl("2000Q1 2019Q4")` · `wf.smpl("@all")` · `wf.smpl("@first", "2010Q4")` ·
        `wf.smpl("1990Q1", "@last")`. 인자 없이 부르면 (시작, 끝) 라벨을, 설정하면 워크파일을 돌려준다.

        오류
            ValueError: 시점 표기가 주기와 맞지 않음(연간에 '2000Q1' 등) · 시작이 끝보다 뒤

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> wf.smpl("2000Q1", "2019Q4")                  # 설정하면 워크파일을 돌려준다(이어 부르기)
            <워크파일 toy_q: ... smpl 2000Q1~2019Q4>
            >>> wf.smpl()
            ('2000Q1', '2019Q4')
            >>> wf.smpl("@all").smpl()
            ('1970Q1', '2019Q4')
        """
        if start is None and end is None:
            s, e = self._bounds()
            return (self._label(self.index[s]), self._label(self.index[e]))
        if isinstance(start, str) and end is None:
            tok = start.strip()
            if tok.lower() in ("@all", "all"):
                self._smpl = None
                say(f"[{self.name}] smpl 전체")
                return self
            parts = tok.split()
            if len(parts) == 2:
                start, end = parts
        p0 = None if start is None or str(start).lower() == "@first" else parse_period(start, self.freq)
        p1 = None if end is None or str(end).lower() == "@last" else parse_period(end, self.freq)
        if p0 is not None and p1 is not None and p0 > p1:
            raise ValueError(f"표본 시작이 끝보다 뒤입니다: {start} > {end}")
        self._smpl = (p0, p1)
        s, e = self._bounds()
        say(f"[{self.name}] smpl {self._label(self.index[s])} ~ {self._label(self.index[e])}")
        return self

    def _index_of(self, p) -> int:
        if isinstance(p, (int, np.integer)):
            return int(p)
        return self._wt.index_of(p)

    def _bounds(self, start=None, end=None) -> Tuple[int, int]:
        """(start, end) 인자 → 정수 위치. 없으면 표본, 그것도 없으면 데이터 전체."""
        T = len(self.data)
        if T == 0:
            raise ValueError("워크파일에 기간이 없습니다.")
        if start is not None:
            s = self._index_of(start)
        elif self._smpl and self._smpl[0] is not None:
            s = self._wt._period_to_index(self._smpl[0], side="start")
        else:
            s = 0
        if end is not None:
            e = self._index_of(end)
        elif self._smpl and self._smpl[1] is not None:
            e = self._wt._period_to_index(self._smpl[1], side="end")
        else:
            e = T - 1
        if s > e:
            raise ValueError(f"구간이 비었습니다: {s} > {e}")
        return s, e

    def _smpl_tokens(self) -> Tuple[Optional[str], Optional[str]]:
        """방정식 @smpl에 넘길 시점 문자열(설정 안 된 쪽은 None)."""
        if not self._smpl:
            return None, None
        return tuple(str(p) if p is not None else None for p in self._smpl)

    def _smpl_mask(self) -> np.ndarray:
        s, e = self._bounds()
        mask = np.zeros(len(self.data), dtype=bool)
        mask[s:e + 1] = True
        return mask

    # ------------------------------------------------------------------
    # 시리즈
    # ------------------------------------------------------------------
    def _col(self, name: str) -> Optional[str]:
        if name in self.data.columns:
            return name
        low = str(name).lower()
        for c in self.data.columns:
            if str(c).lower() == low:
                return c
        return None

    def __contains__(self, name) -> bool:
        return self._col(name) is not None

    def __getitem__(self, name) -> pd.Series:
        if isinstance(name, (list, tuple)):
            return self.to_pandas(list(name))
        col = self._col(name)
        if col is None:
            raise KeyError(f"시리즈 '{name}'이(가) 없습니다.")
        return self.data[col].copy()

    def __setitem__(self, name: str, value):
        """시리즈 전체를 쓴다(Python 대입 — 표본과 무관). 표본 안만 바꾸려면 genr."""
        self._check_series_name(name)
        col = self._col(name) or name
        self._data._set_columns({col: self._as_array(value)})

    def __delitem__(self, name: str):
        self.delete(name)

    def _as_array(self, value) -> np.ndarray:
        T = len(self.data)
        if isinstance(value, pd.Series):
            if isinstance(value.index, pd.DatetimeIndex):
                return value.reindex(self.index).to_numpy(dtype=float)
            if len(value) == T:
                return value.to_numpy(dtype=float)
            raise ValueError(f"Series 길이 {len(value)} ≠ 워크파일 기간 {T} (날짜 인덱스를 쓰면 맞춰집니다)")
        if isinstance(value, pd.DataFrame):
            raise TypeError("DataFrame은 열마다 wf['이름'] = df['열'] 로 넣으세요.")
        arr = np.asarray(value, dtype=float)
        if arr.ndim == 0:
            return np.full(T, float(arr))
        if len(arr) != T:
            raise ValueError(f"배열 길이 {len(arr)} ≠ 워크파일 기간 {T}")
        return arr

    def _check_series_name(self, name: str):
        if not isinstance(name, str) or not _NAME_RE.match(name):
            raise ValueError(f"시리즈 이름이 올바르지 않습니다: {name!r}")
        why = reserved_name_error(name)
        if why:
            raise ValueError(why)
        if name.lower() in self._objects:
            raise ValueError(f"'{name}'은(는) 이미 {self._objects[name.lower()].kind} 객체 이름입니다.")

    def series(self, pattern: str = "*") -> List[str]:
        """시리즈 이름 목록 — 와일드카드(`*` `?` `[…]`, 대소문자 무시)로 고를 수 있다.

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> wf.series("C*")
            ['CN', 'CNNSA']
            >>> len(wf.series())
            10
        """
        import fnmatch
        return [c for c in self.data.columns if fnmatch.fnmatchcase(str(c).upper(), pattern.upper())]

    def delete(self, *names: str):
        """시리즈 또는 객체를 지운다(이름 여러 개).

        오류
            KeyError: 그런 시리즈나 객체가 없음

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> wf["TMP"] = 1.0
            >>> _ = wf.delete("TMP")
            >>> "TMP" in wf
            False
        """
        for nm in names:
            low = nm.lower()
            if low in self._objects:
                del self._objects[low]
                continue
            col = self._col(nm)
            if col is None:
                raise KeyError(f"'{nm}'이(가) 없습니다.")
            self._wt.data.data = self.data.drop(columns=[col])
            self._data.indicators.pop(col, None)
            self._meta.pop(col, None)
        return self

    # ------------------------------------------------------------------
    # 메타데이터 · 페이지 · 주기 변환 · 계절조정 (D26)
    # ------------------------------------------------------------------
    META_FIELDS = ("desc", "unit", "source", "notes", "agg")

    def meta(self, name: str, **fields) -> dict:
        """시리즈 메타데이터 읽기·쓰기 — 설명·단위·출처·집계 방식 등. 워크파일과 함께 저장된다.

        `agg`(mean·sum·first·last·max·min)는 낮은 주기로 바꿀 때(convert) 기본 집계다. 값을 None으로 주면 그 항목을 지운다.

        매개변수
            name: 시리즈 이름
            **fields: desc · unit · source · agg · notes 등

        돌려주는 것
            그 시리즈의 메타데이터 dict

        오류
            KeyError: 없는 시리즈 · ValueError: agg 값이 틀림

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> wf.meta("Y")["agg"]
            'sum'
            >>> wf.meta("R", notes="정책금리 — 분기 평균")["notes"]
            '정책금리 — 분기 평균'
        """
        col = self._col(name)
        if col is None:
            raise KeyError(f"시리즈 '{name}'이(가) 없습니다.")
        m = self._meta.setdefault(col, {})
        for k, v in fields.items():
            if k == "agg" and v is not None:
                from ..data.transform import AGG_METHODS
                if v not in AGG_METHODS:
                    raise ValueError(f"agg는 {AGG_METHODS} 중 하나")
            if v is None:
                m.pop(k, None)
            else:
                m[k] = v
        if not m:
            self._meta.pop(col, None)
        return dict(m)

    def metadata(self, pattern: str = "*") -> TableOutput:
        """시리즈 목록과 메타데이터·관측 구간 표(.data는 DataFrame). pattern으로 고를 수 있다.

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> t = wf.metadata("R*")
            >>> list(t.data.index)
            ['R', 'RL']
            >>> t.data.loc["RL", "처음"]
            '1980Q1'
        """
        rows = []
        for c in self.series(pattern):
            v = self.data[c]
            ok = v.notna()
            first = self._label(v.index[ok.argmax()]) if ok.any() else ""
            last = self._label(v.index[len(ok) - 1 - ok[::-1].argmax()]) if ok.any() else ""
            m = self._meta.get(c, {})
            rows.append({"시리즈": c, "설명": m.get("desc", ""), "단위": m.get("unit", ""), "출처": m.get("source", ""),
                         "집계": m.get("agg", ""), "처음": first, "끝": last, "관측치": int(ok.sum()),
                         "메모": m.get("notes", "")})
        df = pd.DataFrame(rows).set_index("시리즈") if rows else pd.DataFrame()
        return TableOutput(df, title=f"워크파일 {self.name} 시리즈", name=f"{self.name}_series")

    def page(self, name: str, freq: str = None, start=None, end=None) -> "Workfile":
        """다른 주기의 페이지(없으면 만든다 — freq 필요). 기간은 이 워크파일 전체를 덮는 범위(또는 start·end).
        페이지는 워크파일과 함께 저장되고, `wf.convert(…, to=페이지)`로 시리즈를 옮긴다."""
        key = name.lower()
        if key in self._pages:
            pg = self._pages[key]
            if freq and normalize_freq(freq) != pg.freq:
                raise ValueError(f"페이지 '{name}'의 주기는 {pg.freq}입니다")
            return pg
        if not freq:
            raise KeyError(f"페이지 '{name}'이(가) 없습니다 — 만들려면 freq를 주세요: wf.page('{name}', 'A')")
        f = normalize_freq(freq)
        p0 = to_period(self.index[0], f) if start is None else parse_period(start, f)
        p1 = to_period(to_period(self.index[-1], self.freq).end_time, f) if end is None else parse_period(end, f)
        pg = quiet(wfcreate, name, f, p0, p1)
        pg._parent = self
        self._pages[key] = pg
        say(f"[{self.name}] 페이지 {name} — {_FREQ_LABEL[f]} {pg._label(pg.index[0])}~{pg._label(pg.index[-1])}")
        return pg

    @property
    def pages(self) -> Dict[str, "Workfile"]:
        """이 워크파일에 딸린 다른 주기의 페이지 {이름: Workfile}."""
        return dict(self._pages)

    def _block(self, name: str, v: pd.Series = None) -> pd.Series:
        """시리즈(또는 그 일부 v)의 처음~끝 관측 구간(안쪽 결측은 오류)."""
        v = self[name] if v is None else v
        ok = v.notna().to_numpy()
        if not ok.any():
            raise ValueError(f"'{name}'에 관측치가 없습니다")
        a, b = int(np.argmax(ok)), len(ok) - 1 - int(np.argmax(ok[::-1]))
        blk = v.iloc[a:b + 1]
        if blk.isna().any():
            raise ValueError(f"'{name}' 안쪽에 결측({self._label(blk.index[blk.isna()][0])})이 있습니다 — 먼저 채우세요")
        return blk

    def convert(self, series, to, method: str = None, name: str = None, indicator=None, conversion: str = None,
                complete: bool = True, start=None, end=None):
        """주기 변환 — 이 워크파일의 시리즈를 다른 주기로 바꿔 돌려주거나 페이지에 쓴다.

        높은 → 낮은 주기(예: 분기 → 연): method는 mean·sum·first·last·max·min(기본은 메타데이터 agg, 없으면 mean).
        complete=True면 하위 기간이 하나라도 비면 그 기간은 결측(부분 연도 방지).
        낮은 → 높은 주기(예: 분기 → 월): constant(반복, 기본)·split(합을 나눔)·linear·denton·chow-lin.
        denton·chow-lin은 낮은 주기 값(conversion: sum·average·first·last — 기본은 agg가 sum이면 sum, 아니면 average)을
        정확히 지키면서 indicator(대상 페이지의 높은 주기 시리즈 이름 또는 Series)를 따라 나눈다(chow-lin은 지표가 필수).
        지표가 낮은 주기 끝보다 길면 그 뒤를 외삽한다.

        매개변수
            series: 시리즈 이름(또는 목록 — 그러면 {이름: 결과})
            to: 주기 'A'·'Q'·'M'(돌려주기만) 또는 페이지·페이지 이름(그 페이지에 쓴다)
            name: 페이지에 쓸 이름(기본: 같은 이름)
            start, end: 바꿀 원래 구간(지표가 더 짧을 때 맞춘다)

        돌려주는 것
            변환한 pandas Series(.attrs['convert']에 방법·변환 정보)

        오류
            ValueError: 방법·변환 이름이 틀림, 지표가 구간을 다 덮지 않음, 안쪽 결측

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> ya = wf.convert("Y", "A")                         # Y의 agg는 sum → 연간 합
            >>> round(float(ya.iloc[0]), 1) == round(float(wf["Y"].iloc[:4].sum()), 1)
            True
            >>> round(float(wf.convert("R", "A", method="last").iloc[0]), 3) == round(wf.elem("R", "1970Q4"), 3)
            True

        관련: page · datasets.load("toy_m")(월간 지표)
        """
        from ..data import transform as tr
        names = series.split() if isinstance(series, str) and " " in series.strip() else (
            [series] if isinstance(series, str) else list(series))
        if isinstance(to, Workfile):
            page = to
        elif isinstance(to, str) and to.lower() in self._pages:
            page = self._pages[to.lower()]
        else:
            page = None
        f_to = page.freq if page is not None else normalize_freq(to)
        if len(names) > 1:
            if name is not None:
                raise ValueError("시리즈가 여럿이면 name을 줄 수 없습니다")
            return {n: self.convert(n, to, method, None, indicator, conversion, complete, start, end) for n in names}
        src = names[0]
        col = self._col(src)
        if col is None:
            raise KeyError(f"시리즈 '{src}'이(가) 없습니다.")
        agg = self._meta.get(col, {}).get("agg")
        hi, lo = PERIODS_PER_YEAR[self.freq], PERIODS_PER_YEAR[f_to]
        info = {"from": self.freq, "to": f_to}
        ser = self[col]
        if start is not None or end is not None:
            a, b = self._index_of(start) if start is not None else 0, \
                self._index_of(end) if end is not None else len(self.index) - 1
            if a > b:
                raise ValueError(f"구간이 비었습니다: {start} > {end}")
            ser = ser.iloc[a:b + 1]
        if hi > lo:
            how = method or agg or "mean"
            out = tr.aggregate(ser, self.freq, f_to, how, complete)
            info["method"] = how
        elif hi == lo:
            out = ser
            info["method"] = "copy"
        else:
            how = method or "constant"
            blk = self._block(col, ser)
            if how in ("constant", "split", "linear"):
                out = tr.expand(blk, self.freq, f_to, how)
            elif how in ("denton", "chow-lin"):
                k = tr.ratio(self.freq, f_to)
                conv = conversion or ("sum" if agg == "sum" else "average")
                hidx = tr.expand(blk, self.freq, f_to, "constant").index
                ind = None
                if indicator is not None:
                    if isinstance(indicator, pd.Series):
                        iser = indicator
                    elif page is not None:
                        iser = page[indicator]
                    else:
                        raise ValueError("indicator가 이름이면 to에 페이지를 주세요(또는 pandas Series)")
                    iser = iser.dropna()
                    tail = iser.loc[iser.index > hidx[-1]]
                    hidx = hidx.append(tail.index)
                    ind = iser.reindex(hidx).to_numpy(dtype=float)
                    if not np.all(np.isfinite(ind)):
                        lab = lambda ts, f: format_period(to_period(ts, f), f)  # noqa: E731
                        span = f"{lab(blk.index[0], self.freq)}~{lab(blk.index[-1], self.freq)}"
                        ispan = f"{lab(iser.index[0], f_to)}~{lab(iser.index[-1], f_to)}" if len(iser) else "관측 없음"
                        raise ValueError(f"지표가 변환 구간을 다 덮지 않습니다 — 바꿀 구간 {span}, 지표 {ispan}. "
                                         "start·end로 구간을 좁히세요")
                if how == "denton":
                    vals = tr.denton(blk.to_numpy(dtype=float), k, ind, conv)
                else:
                    if ind is None:
                        raise ValueError("chow-lin에는 indicator(높은 주기 지표)가 필요합니다")
                    r = tr.chow_lin(blk.to_numpy(dtype=float), np.column_stack([np.ones(len(ind)), ind]), k, conv)
                    vals = r["x"]
                    info.update({"rho": r["rho"], "beta": [float(b) for b in r["beta"]], "loglik": r["loglik"]})
                out = pd.Series(vals, index=hidx, name=col)
                info["conversion"] = conv
            else:
                raise ValueError(f"method는 {tr.EXPAND_METHODS} 중 하나(낮은 → 높은 주기)")
            info["method"] = how
        out = out.rename(name or col)
        out.attrs["convert"] = info
        if page is not None:
            tgt = name or col
            page._check_series_name(tgt)
            page[tgt] = out.reindex(page.index)
            m = dict(self._meta.get(col, {}))
            m["notes"] = (m.get("notes", "") + " · " if m.get("notes") else "") + \
                f"{self.name}.{col}에서 {info['method']}({self.freq}→{f_to})"
            page._meta[page._col(tgt)] = m
            say(f"[{self.name}] {col} → {page.name}.{tgt} ({info['method']}, {self.freq}→{f_to})")
        return out

    def seas(self, series: str, method: str = "stl", model: str = "additive", name: str = None, write: bool = True,
             **kw):
        """계절조정 — STL(기본) 또는 고전 분해로 계절 성분을 떼어 조정 계열을 만든다.

        STL 옵션(seasonal·trend·low_pass·robust 등)은 **kw로. model='multiplicative'면 로그에서 분해해 되돌린다(계절 요인 = 비율).
        표본 안의 관측 구간을 쓴다. write=True면 `이름_SA`(조정 계열)와 `이름_SF`(계절 성분: 가법은 차이, 승법은 요인)를 쓴다.

        매개변수
            series: 시리즈 이름
            method: 'stl' · 'classical'
            model: 'additive' · 'multiplicative'
            name: 결과 시리즈 이름의 앞부분(기본: series)

        돌려주는 것
            SeasonalResult — .table(실측·계절·추세·불규칙·조정) · .output() · .graph()

        오류
            ValueError: 연간 자료, 안쪽 결측, 너무 짧은 계열, 승법인데 0 이하 값

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> r = wf.seas("CNNSA")
            >>> wf.series("CNNSA*")
            ['CNNSA', 'CNNSA_SA', 'CNNSA_SF']
            >>> abs(float(wf["CNNSA_SF"].iloc[-4:].sum())) < 3
            True
        """
        from ..data import transform as tr
        if self.freq == "A":
            raise ValueError("연간 자료에는 계절조정이 없습니다")
        period = PERIODS_PER_YEAR[self.freq]
        col = self._col(series)
        if col is None:
            raise KeyError(f"시리즈 '{series}'이(가) 없습니다(식이면 먼저 genr로 시리즈를 만드세요)")
        s, e = self._bounds()
        v = self[col].iloc[s:e + 1]
        ok = v.notna().to_numpy()
        a, b = int(np.argmax(ok)), len(ok) - 1 - int(np.argmax(ok[::-1]))
        blk = v.iloc[a:b + 1]
        if blk.isna().any():
            raise ValueError(f"'{col}' 안쪽에 결측이 있습니다 — 먼저 채우세요")
        y = blk.to_numpy(dtype=float)
        mult = model == "multiplicative"
        if model not in ("additive", "multiplicative"):
            raise ValueError("model은 'additive' 또는 'multiplicative'")
        if method == "stl":
            if mult and np.any(y <= 0):
                raise ValueError("승법 STL에는 양수 자료만 됩니다(로그 분해)")
            S, T, R, _ = tr.stl(np.log(y) if mult else y, period, **kw)
            if mult:
                S, T, R = np.exp(S), np.exp(T), np.exp(R)
        elif method == "classical":
            S, T, R = tr.classical(y, period, model)
        else:
            raise ValueError("method는 'stl' 또는 'classical'")
        sa = y / S if mult else y - S
        tab = pd.DataFrame({"실측": y, "계절": S, "추세": T, "불규칙": R, "조정": sa}, index=blk.index)
        base = name or col
        if write:
            for suf, vals in (("_SA", sa), ("_SF", S)):
                arr = np.full(len(self.data), np.nan)
                arr[s + a:s + b + 1] = vals
                self._check_series_name(base + suf)
                self[base + suf] = arr
            self._meta[self._col(base + "_SA")] = {"notes": f"{col}의 계절조정({method}, {model})"}
        say(f"[{self.name}] 계절조정 {col} — {method}·{model} → {base}_SA·{base}_SF" if write else
            f"[{self.name}] 계절조정 {col} — {method}·{model}")
        return SeasonalResult(self, col, method, model, tab)


    def genr(self, expr: str, func=None, smpl: bool = True) -> pd.Series:
        """시리즈 만들기·고치기 — **표본 안만** 계산해 쓴다(표본 밖 값은 그대로).

        식은 방정식과 같은 문법이다: 시차 `X(-1)` · `log`·`dlog`·`d` · `.yoy`·`.qoq` · `@pcy` · `@trend`·`@seas(n)`·`@d(P)`·`@step(P)`.
        자기 시차가 있는 식(`Z = Z(-1)*1.02`)은 앞에서부터 한 기씩 계산한다. 함수를 주면 `func(시리즈 DataFrame)`의 결과를 쓴다.

        매개변수
            expr: "이름 = 식" 또는 (func을 줄 때) 이름
            func: DataFrame → 값(배열·Series)인 Python 함수
            smpl: False면 표본을 무시하고 전 기간

        돌려주는 것
            만든 시리즈(pandas Series)

        오류
            DSLError: 식 문법 · ValueError: 없는 시리즈, 예약 이름(C·LOG 등)

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> _ = wf.genr("YD = Y - G")
            >>> round(wf.elem("YD", "2010Q1"), 2) == round(wf.elem("Y", "2010Q1") - wf.elem("G", "2010Q1"), 2)
            True
            >>> _ = wf.genr("T2 = @trend ^ 2")
            >>> wf.elem("T2", "1970Q3")
            4.0
            >>> _ = wf.genr("GAP", lambda d: d.Y / d.Y.rolling(4).mean() - 1)

        관련: eval · smpl
        """
        if func is not None:
            name = expr.strip()
            self._check_series_name(name)
            vals = self._as_array(func(self.data))
        else:
            text = normalize(expr)
            lhs, rhs = split_equation(text)
            name = lhs.strip()
            self._check_series_name(name)
            rhs = canonicalize_columns(quiet(expand_indicators, self._data, rhs, bare_seas=False), self.data.columns)
            freq = self.freq
            ctx = ir.BuildContext(yoy_periods={"Q": 4, "A": 1, "M": 12}.get(freq, 4),
                                  disable_qoq=(freq == "A"))
            node = ir.build(convert_at_functions(rhs), ctx)
            target = self._col(name) or name
            unknown = sorted(v for v in ir.variables(node) if self._col(v) is None and v != target)
            if unknown:
                raise ValueError(f"워크파일에 없는 시리즈 {unknown}: {expr}")
            node = _rename_vars(node, {v: self._col(v) or v for v in ir.variables(node)})
            recursive = any(n == target and lag < 0 for n, lag in ir.leaves(node))
            if recursive:
                vals = self._genr_sequential(node, target, smpl)
            else:
                vals = ir.evaluate(node, lambda n: self.data[n].to_numpy(dtype=float), length=len(self.data))
        col = self._col(name) or name
        mask = self._smpl_mask() if smpl else np.ones(len(self.data), dtype=bool)
        old = self.data[col].to_numpy(dtype=float) if col in self.data.columns else np.full(len(self.data), np.nan)
        self._data._set_columns({col: np.where(mask, vals, old)})
        return self[col]

    def _genr_sequential(self, node, target, smpl) -> np.ndarray:
        """자기 시차가 있는 식: 표본 안을 앞에서부터 한 기씩 계산(앞 결과를 다음 기가 읽음)."""
        T = len(self.data)
        arrays = {n: self.data[n].to_numpy(dtype=float).copy() for n in ir.variables(node) if n in self.data.columns}
        if target not in arrays:
            arrays[target] = np.full(T, np.nan)
        rows = np.where(self._smpl_mask() if smpl else np.ones(T, dtype=bool))[0]
        for t in rows:
            arrays[target][t] = _eval_scalar(node, arrays, t, T)
        return arrays[target]

    # ------------------------------------------------------------------
    # 식 평가·단위근·공적분 검정
    # ------------------------------------------------------------------
    def eval(self, expr: str) -> pd.Series:
        """방정식 식 문법으로 계산한 시리즈 — 워크파일에 쓰지 않는다.

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> g = wf.eval("dlog(Y) * 400")                     # 연율 성장률(%)
            >>> int(g.notna().sum())
            199
            >>> wf.eval("@seas(1)").iloc[:4].tolist()
            [1.0, 0.0, 0.0, 0.0]

        오류
            DSLError: 문법 · ValueError: 없는 시리즈 · 번호 없는 @seas

        관련: genr
        """
        text = canonicalize_columns(quiet(expand_indicators, self._data, normalize(expr), bare_seas=False),
                                    self.data.columns)
        freq = self.freq
        ctx = ir.BuildContext(yoy_periods={"Q": 4, "A": 1, "M": 12}.get(freq, 4), disable_qoq=(freq == "A"))
        node = ir.build(convert_at_functions(text), ctx)
        unknown = sorted(v for v in ir.variables(node) if self._col(v) is None)
        if unknown:
            raise ValueError(f"워크파일에 없는 시리즈 {unknown}: {expr}")
        node = _rename_vars(node, {v: self._col(v) for v in ir.variables(node)})
        vals = ir.evaluate(node, lambda n: self.data[n].to_numpy(dtype=float), length=len(self.data))
        return pd.Series(vals, index=self.index, name=expr)

    def _test_frame(self, items) -> pd.DataFrame:
        """검정할 시리즈들(이름·식·pandas Series) → 표본 구간, 양끝 결측을 뺀 DataFrame(안쪽 결측은 오류)."""
        cols = {}
        for it in items:
            if isinstance(it, pd.Series):
                cols[str(it.name or f"x{len(cols) + 1}")] = it.reindex(self.index)
            else:
                cols[str(it)] = self[it] if self._col(str(it)) else self.eval(str(it))
        df = pd.DataFrame(cols, index=self.index)
        s, e = self._bounds()
        df = df.iloc[s:e + 1]
        ok = df.notna().all(axis=1).to_numpy()
        if not ok.any():
            raise ValueError("표본 안에 모든 시리즈가 관측된 기간이 없습니다")
        first, last = int(np.argmax(ok)), len(ok) - 1 - int(np.argmax(ok[::-1]))
        df = df.iloc[first:last + 1]
        if df.isna().any().any():
            gap = df.index[df.isna().any(axis=1)][0]
            raise ValueError(f"표본 안쪽에 결측이 있습니다({self._label(gap)}) — smpl을 좁히거나 결측을 채우세요")
        return df

    def _span(self, df) -> str:
        return f"{self._label(df.index[0])}~{self._label(df.index[-1])}"

    def adf(self, x, trend: str = "c", lags: int = None, ic: str = "bic", maxlag: int = None):
        """ADF 단위근 검정(표본 구간). 귀무가설: 단위근이 있다.

        매개변수
            x: 시리즈 이름 · 식(`"log(Y)"`) · pandas Series
            trend: 'n'(결정항 없음) · 'c'(상수) · 'ct'(상수 + 추세)
            lags: 차분 시차 수(None이면 ic로 고른다)
            ic: 'bic' · 'aic' · 't-stat'

        돌려주는 것
            TestResult(.statistic = ADF t, .pvalue = MacKinnon 근사 p값, .rows = 임계값)

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> wf.adf("log(Y)", trend="ct").pvalue > 0.05        # 수준: 단위근을 기각하지 못한다
            True
            >>> wf.adf("dlog(Y)").pvalue < 0.01                   # 차분: 정상
            True

        관련: kpss · coint
        """
        from ..stats.unitroot import adf as _adf
        df = self._test_frame([x])
        r = _adf(df.iloc[:, 0].to_numpy(), trend, lags, ic, maxlag, name=str(df.columns[0]))
        r.info["표본"] = self._span(df)
        say(f"[{self.name}] {r.name}: ADF {r.statistic:.4f}, p={r.pvalue:.4f} (시차 {r.details['lags']})")
        return r

    def kpss(self, x, trend: str = "c", lags="auto"):
        """KPSS 정상성 검정(표본 구간). 귀무가설이 '정상'이라 ADF와 반대 방향이다. p값은 표 보간(0.01~0.10).

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> wf.kpss("dlog(Y)").pvalue >= 0.05
            True

        관련: adf
        """
        from ..stats.unitroot import kpss as _kpss
        df = self._test_frame([x])
        r = _kpss(df.iloc[:, 0].to_numpy(), trend, lags, name=str(df.columns[0]))
        r.info["표본"] = self._span(df)
        say(f"[{self.name}] {r.name}: KPSS {r.statistic:.4f}, p={r.pvalue:.3f}")
        return r

    def coint(self, y, x, trend: str = "c", lags: int = None, ic: str = "bic", maxlag: int = None):
        """Engle-Granger 공적분 검정 — y를 x(이름 목록 또는 공백 구분 글자)에 회귀한 잔차의 단위근 검정.

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> wf.coint("RL", "R").pvalue < 0.01                 # RL = 1 + R + 정상 오차
            True

        관련: johansen · ecm
        """
        from ..stats.unitroot import engle_granger
        xs = x.split() if isinstance(x, str) else list(x)
        df = self._test_frame([y, *xs])
        r = engle_granger(df.iloc[:, 0].to_numpy(), df.iloc[:, 1:].to_numpy(), trend, lags, ic, maxlag,
                          names=[str(c) for c in df.columns])
        r.info["표본"] = self._span(df)
        say(f"[{self.name}] {r.name}: τ {r.statistic:.4f}, p={r.pvalue:.4f}")
        return r

    def johansen(self, series, det: int = 0, lags: int = 1):
        """Johansen 공적분 순위 검정(트레이스·최대 고유값, 표본 구간).

        매개변수
            series: 이름·식 목록 또는 공백 구분 글자
            det: −1 결정항 없음 · 0 상수 · 1 상수 + 추세
            lags: 차분 시차 수

        돌려주는 것
            TestResult — .table(순위별 통계량·5% 임계값), .rows(고른 순위)

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> j = wf.johansen("RL R")
            >>> j.rows["트레이스 기준 순위(5%)"]
            1

        관련: vecm · coint
        """
        from ..stats.unitroot import johansen as _johansen
        items = series.split() if isinstance(series, str) else list(series)
        df = self._test_frame(items)
        r = _johansen(df.to_numpy(), det, lags, names=[str(c) for c in df.columns])
        r.info["표본"] = self._span(df)
        say(f"[{self.name}] {r.name}: 순위(트레이스 5%) {r.details['rank_trace']} · 최대 고유값 {r.details['rank_maxeig']}")
        return r

    # ------------------------------------------------------------------
    # 예측 평가 · 오차수정모형
    # ------------------------------------------------------------------
    def _eval_series(self, x) -> pd.Series:
        if isinstance(x, pd.Series):
            return x.reindex(self.index)
        return self[x] if self._col(str(x)) else self.eval(str(x))

    def forecast_eval(self, actual, *forecasts, start=None, end=None) -> TableOutput:
        """예측 평가 표 — RMSE·MAE·MAPE·Theil U1·MSE 분해(편의·분산·공분산)·Theil U2(표본 구간 또는 start~end).

        예측마다 실측과 함께 관측된 기간만 쓴다.

        매개변수
            actual: 실측(시리즈 이름·식·Series)
            *forecasts: 예측들(이름·식·Series)

        돌려주는 것
            TableOutput(.data는 DataFrame, 행 = 예측)

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> t = wf.forecast_eval("Y", "Y(-1)", "Y(-4)")
            >>> list(t.data.index)
            ['Y(-1)', 'Y(-4)']
            >>> bool(t.data.loc["Y(-1)", "RMSE"] < t.data.loc["Y(-4)", "RMSE"])
            True

        관련: dm_test
        """
        from ..stats.forecast import evaluate_many
        if not forecasts:
            raise ValueError("예측 시리즈를 하나 이상 주세요")
        s, e = self._bounds(start, end)
        a = self._eval_series(actual).iloc[s:e + 1]
        fs = {}
        for f in forecasts:
            nm = str(f.name) if isinstance(f, pd.Series) else str(f)
            fs[nm] = self._eval_series(f).iloc[s:e + 1]
        df = evaluate_many(a, fs)
        name = str(actual.name) if isinstance(actual, pd.Series) else str(actual)
        return TableOutput(df, title=f"예측 평가 — 실측 {name}", digits=4, name=f"{self.name}_fceval",
                           head=[f"구간 {self._label(self.index[s])}~{self._label(self.index[e])} (실측·예측이 함께 있는 기간)"],
                           foot=["Theil U1: 0 완벽 ~ 1 · 편의+분산+공분산 비중 = 1(편의·분산이 작을수록 좋음) · "
                                 "Theil U2 < 1이면 '변화 없음' 예측보다 낫다"])

    def dm_test(self, actual, f1, f2, h: int = 1, loss: str = "squared", start=None, end=None):
        """Diebold-Mariano 검정 — 두 예측(f1·f2)의 정확도가 같은가.

        Harvey-Leybourne-Newbold 작은 표본 보정과 t 분포를 쓴다. 통계량이 음수면 f1이 더 정확하다.

        매개변수
            actual, f1, f2: 실측과 두 예측(이름·식·Series)
            h: 몇 기 앞 예측인가(오차의 MA(h−1) 구조)
            loss: 'squared' · 'absolute'

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> r = wf.dm_test("Y", "Y(-1)", "Y(-4)")
            >>> r.statistic < 0 and r.pvalue < 0.05
            True

        관련: forecast_eval
        """
        from ..stats.forecast import diebold_mariano
        s, e = self._bounds(start, end)
        r = diebold_mariano(self._eval_series(actual).iloc[s:e + 1], self._eval_series(f1).iloc[s:e + 1],
                            self._eval_series(f2).iloc[s:e + 1], h=h, loss=loss)
        r.info["비교"] = f"{f1} 대 {f2}"
        say(f"[{self.name}] {r.name}: DM {r.statistic:.4f}, p={r.pvalue:.4f}")
        return r

    def ecm(self, name: str, y: str, x, method: str = "two-step", lags: int = 0, const: bool = True):
        """오차수정모형(ECM) — 공적분 관계(장기식)와 균형 오차로 돌아오는 단기식을 한 번에 추정한다.

        method='two-step'(Engle-Granger): ① 장기식 `y c x…`(객체 이름 name_lr)을 OLS로, ② 단기식
        `d(y) c d(x)… EC(-1)`을 OLS로. EC(-1) = (y − a − b·x)(-1)은 장기 계수를 숫자로 넣은 식이라 연립 풀이에서도
        y·x에 따라 움직인다. 장기 잔차의 Engle-Granger 검정을 함께 보인다.
        method='nls': `d(y) = c(1)*(y(-1) − c(2) − c(3)*x(-1) …) + …`를 한 번에 NLS로 — 장기 계수의 표준오차를 바로 얻는다.

        매개변수
            name: 단기식 방정식 객체 이름(모델에 넣을 수 있다)
            y, x: 시리즈 이름이나 식(보통 로그 수준), x는 목록
            lags: 단기식에 넣을 d(y)·d(x)의 시차 수
            const: 장기식의 상수항

        돌려주는 것
            ECMResult — .longrun() · .adjustment(α) · .half_life · .shortrun(방정식 객체) · .output()

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> e = wf.ecm("ecm_rl", "RL", ["R"])
            >>> bool(-0.6 < e.adjustment["계수"] < -0.1)
            True
            >>> wf.obj("ecm_rl").method
            'ols'

        관련: coint · model.merge
        """
        from .objects import ECMResult
        xs = x.split() if isinstance(x, str) and "(" not in x else ([x] if isinstance(x, str) else list(x))
        method = method.lower().replace("_", "-")
        if method not in ("two-step", "nls"):
            raise ValueError("method는 'two-step' 또는 'nls'")
        lr = self.equation(f"{name}_lr").ls(f"{y} {'c ' if const else ''}{' '.join(xs)}")
        b = lr.coefs
        coint = self.coint(y, xs, trend="c" if const else "n")
        a = float(b["const"]) if const else 0.0
        ec = f"(({y}) - ({a!r})" + "".join(f" - ({float(b[xi])!r})*({xi})" for xi in xs) + ").t(-1)"
        dterms = [f"d({xi})" for xi in xs]
        lagterms = [f"d({v}).t(-{i})" for i in range(1, lags + 1) for v in [y, *xs]]
        two = f"d({y}) {'c ' if const else ''}{' '.join(dterms)} {ec} {' '.join(lagterms)}".strip()
        if method == "two-step":
            sr = self.equation(name).ls(two)
            return ECMResult(self, name, "two-step", y, xs, sr, lr, coint, const=const)
        tmp = EquationObject(self, "_ecm_start")._make(two)
        tv = list(tmp.coef_vector())                    # 위치로: [c] d(x)… EC(-1) 시차항…
        i_ec = (1 if const else 0) + len(xs)
        k = 1
        lr_part = f"({y}).t(-1)"
        start = [tv[i_ec]]
        if const:
            k += 1
            lr_part += f" - c({k})"
            start.append(a)
        for xi in xs:
            k += 1
            lr_part += f" - c({k})*({xi}).t(-1)"
            start.append(float(b[xi]))
        sr_terms = []
        rest = tv[(1 if const else 0):i_ec] + tv[i_ec + 1:]
        for t, v in zip(dterms + lagterms, rest):
            k += 1
            sr_terms.append(f"c({k})*{t}")
            start.append(v)
        spec = f"d({y}) = c(1)*({lr_part})" + "".join(f" + {t}" for t in sr_terms)
        sr = self.equation(name).nls(spec, start=start)
        return ECMResult(self, name, "nls", y, xs, sr, lr, coint, const=const)

    def elem(self, name: str, period) -> float:
        """한 기간의 값 — `wf.elem("Y", "2010Q1")`(기간 라벨 또는 정수 위치).

        기간 라벨로 pandas `.loc["2010Q1"]`을 쓰지 않아도 된다(pandas 3.1부터 날짜 인덱스의 분기 문자열 해석은 사라질 예정).

        오류
            KeyError: 없는 시리즈 · ValueError: 없는 기간

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> round(wf.elem("R", "2019Q4"), 4)
            3.1552
            >>> wf.elem("Y", 0) == float(wf["Y"].iloc[0])
            True
        """
        t = self._index_of(period)
        if not 0 <= t < len(self.data):
            raise IndexError(f"{period!r}은(는) 워크파일 기간({self._label(self.index[0])}~{self._label(self.index[-1])}) 밖입니다")
        return float(self[name].iloc[t])

    def to_pandas(self, names: Sequence[str] = None, smpl: bool = False, labels: bool = False) -> pd.DataFrame:
        """시리즈들을 DataFrame으로(복사본). smpl=True면 표본 구간만, labels=True면 인덱스를 기간 라벨('2019Q4')로.

        라벨 인덱스는 기간 라벨로 자를 때 쓴다(`.loc["2010Q1":"2010Q4"]`).

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> df = wf.to_pandas(["Y", "CN"], labels=True)
            >>> list(df.index[:2]), list(df.columns)
            (['1970Q1', '1970Q2'], ['Y', 'CN'])
            >>> len(df.loc["2010Q1":"2010Q4"])
            4
        """
        cols = list(self.data.columns) if names is None else [self._col(n) or n for n in names]
        missing = [c for c in cols if c not in self.data.columns]
        if missing:
            raise KeyError(f"시리즈 {missing}이(가) 없습니다.")
        df = self.data[cols].copy()
        df.index.name = None
        if smpl:
            s, e = self._bounds()
            df = df.iloc[s:e + 1]
        if labels:
            df.index = pd.Index([self._label(ts) for ts in df.index])
        return df

    def _write_range(self, name: str, values: np.ndarray, s: int, e: int):
        self._write_block({name: values}, s, e)

    def _write_block(self, columns: Dict[str, np.ndarray], s: int, e: int):
        """여러 시리즈의 s..e 구간을 한 번에 쓴다(밖은 기존 값, 새 시리즈면 NaN)."""
        T = len(self.data)
        out = {}
        for name, vals in columns.items():
            if name.lower() in self._objects:
                raise ValueError(f"'{name}'은(는) 객체 이름이라 시리즈로 쓸 수 없습니다.")
            col = self._col(name) or name
            arr = self.data[col].to_numpy(dtype=float).copy() if col in self.data.columns else np.full(T, np.nan)
            arr[s:e + 1] = np.asarray(vals, dtype=float)
            out[col] = arr
        self._data._set_columns(out)

    # ------------------------------------------------------------------
    # 데이터 입출력·기간
    # ------------------------------------------------------------------
    def read(self, path: str, names: Sequence[str] = None) -> List[str]:
        """파일(xlsx·csv)의 시리즈를 이 워크파일로 가져온다.

        파일의 날짜가 워크파일 끝보다 뒤면 기간을 늘리고, 시작보다 앞의 값은 읽지 않고 경고한다. 주기가 다른 파일은 오류다
        (그 주기의 페이지에 읽은 뒤 convert로 옮긴다). names를 주지 않으면 예약 이름(C·LOG 등) 열은 건너뛴다.

        매개변수
            path: 파일 경로
            names: 가져올 열(기본: 전부)

        돌려주는 것
            가져온 시리즈 이름 목록

        예
            >>> wf = eqn.wfcreate("w", "M", "2000M1", "2019M12")
            >>> wf.read(eqn.datasets.path("toy_m"))
            ['IP', 'CPIM', 'RM']

        관련: write · wfopen · page
        """
        from ..data.io import read_dataframe
        df = read_dataframe(path)
        record_input(path, "data")
        if not isinstance(df.index, pd.DatetimeIndex):
            raise ValueError("첫 열이 날짜여야 합니다.")
        f_file = infer_freq_code(df.index, allow_gaps=True)
        if f_file is not None and f_file != self.freq:
            raise ValueError(f"{os.path.basename(path)}은(는) {_FREQ_LABEL[f_file]} 자료입니다 — 워크파일은 "
                             f"{_FREQ_LABEL[self.freq]}입니다(그 주기의 페이지에 읽은 뒤 convert로 옮기세요)")
        per = [to_period(ts, self.freq) for ts in df.index]
        if len(set(per)) < len(per):
            dup = next(p for p in per if per.count(p) > 1)
            raise ValueError(f"같은 기간({format_period(dup, self.freq)})의 행이 둘 이상입니다 — {os.path.basename(path)}")
        last = max(per)
        if last > to_period(self.index[-1], self.freq):
            quiet(self._data.extend, str(last))
        pos = {to_period(ts, self.freq): i for i, ts in enumerate(self.index)}
        rows = [(r, pos[p]) for r, p in enumerate(per) if p in pos]
        before = sum(1 for p in per if p not in pos)
        cols = list(df.columns) if names is None else list(names)
        missing = [c for c in cols if c not in df.columns]
        if missing:
            raise KeyError(f"파일에 없는 열: {missing}")
        skipped = [str(c) for c in cols if names is None and reserved_name_error(str(c))]
        cols = [c for c in cols if str(c) not in skipped]       # 이름을 직접 주면 _check_series_name이 알린다
        out = {}
        for c in cols:
            self._check_series_name(str(c))
            vals = np.full(len(self.index), np.nan)
            src = pd.to_numeric(df[c], errors="coerce").to_numpy(dtype=float)
            for r, i in rows:
                vals[i] = src[r]
            out[self._col(c) or c] = vals
        self._data._set_columns(out)
        say(f"[{self.name}] read {os.path.basename(path)} — 시리즈 {len(out)}")
        if skipped:
            from ..log import workfile as _wlog
            _wlog.warning(f"[WARN] {os.path.basename(path)}: 시리즈 이름으로 쓸 수 없는 열은 읽지 않았습니다: {', '.join(skipped)} "
                          "(C는 상수항, LOG·EXP·ABS·SQRT·D·DLOG는 함수 이름)")
        if before:
            from ..log import workfile as _wlog
            _wlog.warning(f"[WARN] {os.path.basename(path)}: 워크파일 시작({self._label(self.index[0])}) 앞의 {before}기 값은 "
                          "읽지 않았습니다 — 그 기간이 필요하면 더 이른 시작으로 워크파일을 만드세요")
        return list(out)

    def write(self, path: str, names: Sequence[str] = None, smpl: bool = True) -> str:
        """시리즈를 xlsx·csv로 내보낸다(기본: 표본 구간). 없는 폴더는 만든다.

        매개변수
            path: .xlsx 또는 .csv
            names: 내보낼 시리즈(기본: 전부)
            smpl: False면 전 기간

        돌려주는 것
            쓴 경로

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> wf.write("toy_y.csv", ["Y", "CN"])
            'toy_y.csv'
            >>> eqn.wfopen("toy_y.csv").series()
            ['Y', 'CN']

        관련: read · to_pandas
        """
        ext = os.path.splitext(path)[1].lower()
        if ext not in (".xlsx", ".csv"):
            raise ValueError(f"쓸 수 있는 형식은 .xlsx·.csv입니다(받은 것: {ext or '확장자 없음'})")
        df = self.to_pandas(names, smpl=smpl)
        if os.path.dirname(path):
            os.makedirs(os.path.dirname(path), exist_ok=True)
        if ext == ".xlsx":
            df.to_excel(path)
        else:
            df.to_csv(path, encoding="utf-8-sig")
        record_output(path, "series")
        say(f"[{self.name}] write {path} — {df.shape[1]}열 {df.shape[0]}행")
        return path

    def extend(self, end) -> int:
        """기간을 end까지 늘린다(새 기간은 빈 칸, @trend·계절 더미·@d 등 지시자 열은 저절로 이어진다). 줄이지는 않는다.

        돌려주는 것
            늘어난 기간 수(이미 그만큼 있으면 0)

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> wf.extend("2021Q4")
            8
            >>> wf.smpl()[1], bool(wf["Y"].iloc[-1] != wf["Y"].iloc[-1])
            ('2021Q4', True)

        관련: fill · ModelObject.forecast
        """
        n = quiet(self._data.extend, end)
        if n:
            say(f"[{self.name}] 기간 확장 → {self._label(self.index[-1])} (+{n})")
        else:
            say(f"[{self.name}] 이미 {self._label(self.index[-1])}까지 있습니다 — 기간을 줄이지는 않습니다")
        return n

    def fill(self, names, method: str = "last", window: int = None, start=None, end=None) -> Dict[str, int]:
        """마지막 관측 다음의 빈 칸을 규칙으로 채운다 — 전망의 외생 가정 초안.

        매개변수
            names: 시리즈 이름(공백 구분 글자·목록·와일드카드)
            method: 'last'(마지막 값 유지) · 'growth'(최근 window기 평균 성장률) · 'trend'(최근 window기 평균 증분)
            window: 평균을 낼 기간 수(기본: 1년)
            start, end: 채울 구간(기본: 마지막 관측 다음 ~ 워크파일 끝)

        돌려주는 것
            {시리즈: 채운 기간 수}

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> _ = wf.extend("2020Q4")
            >>> wf.fill("G R", method="last")
            {'G': 4, 'R': 4}
            >>> wf.elem("R", "2020Q4") == wf.elem("R", "2019Q4")
            True
        """
        if isinstance(names, str):
            names = self.series(names) if any(ch in names for ch in "*?[") else names.split()
        cols = [self._col(n) or n for n in names]
        return self._data.fill_series(cols, method=method, window=window, start=start, end=end)

    # ------------------------------------------------------------------
    # 객체
    # ------------------------------------------------------------------
    def _restore_object(self, d: dict, resid, models: list):
        """저장된 객체 하나를 되살린다(모델은 방정식 뒤에 따로 — models에 모은다)."""
        wf = self
        t = d["type"]
        if t == "equation":
            obj = wf._register(EquationObject(wf, d["name"]))
            if d.get("saved"):
                eq = quiet(Equation.restore, d["saved"], wf._data)
                eq.wt = wf._wt
                if resid is not None and d["name"] in resid.columns:
                    r = resid[d["name"]].dropna()
                    r.index = pd.to_datetime(r.index)
                    eq.residuals = r
                obj._adopt(eq, d.get("spec"), loud=False)
        elif t == "model":
            models.append(d)
        elif t == "system":
            wf._register(SystemObject.from_json(wf, d))
        elif t in ("var", "vecm"):
            cls = VARObject if t == "var" else VECMObject
            wf._register(quiet(cls.from_json, wf, d))
        elif t == "graph":
            wf._register(GraphObject(wf, d["name"], d["series"], kind=d.get("kind", "line"),
                                     title=d.get("title"), start=d.get("start"), end=d.get("end")))
        elif t == "table":
            fr = pd.read_json(io.StringIO(json.dumps(d["frame"])), orient="split")
            wf._register(TableObject(wf, d["name"], fr, title=d.get("title")))

    def _replace_object(self, obj):
        old = self._objects.pop(obj.name.lower(), None)
        try:
            return self._register(obj)
        except Exception:
            if old is not None:
                self._objects[obj.name.lower()] = old
            raise

    def _register(self, obj):
        if not _NAME_RE.match(obj.name):
            raise ValueError(f"객체 이름이 올바르지 않습니다: {obj.name!r}")
        if self._col(obj.name) is not None:
            raise ValueError(f"'{obj.name}'은(는) 이미 시리즈 이름입니다(시리즈 {self._col(obj.name)} — 이름은 대소문자를 "
                             f"가리지 않고 시리즈·객체가 함께 씁니다. 객체 이름에 접두사를 붙이세요: 예 eq_{obj.name})")
        self._objects[obj.name.lower()] = obj
        return obj

    def obj(self, name: str):
        """이름으로 객체(방정식·모델·시스템·VAR·그래프·표 …)를 찾는다(대소문자 무시).

        오류
            KeyError: 그런 객체가 없음

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> _ = wf.equation("eq_i").ls("I c Y(-1) R")
            >>> wf.obj("EQ_I").kind
            'equation'
        """
        try:
            return self._objects[name.lower()]
        except KeyError:
            raise KeyError(f"객체 '{name}'이(가) 없습니다: {sorted(o.name for o in self._objects.values())}") from None

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        objs = self.__dict__.get("_objects", {})
        if name.lower() in objs:
            return objs[name.lower()]
        raise AttributeError(f"워크파일에 '{name}' 속성·객체가 없습니다 (시리즈는 wf['{name}'])")

    def _get_or_new(self, name, cls):
        low = name.lower()
        if low in self._objects:
            obj = self._objects[low]
            if not isinstance(obj, cls):
                raise ValueError(f"'{name}'은(는) {obj.kind} 객체입니다.")
            return obj
        return self._register(cls(self, name))

    def equation(self, name: str) -> EquationObject:
        """방정식 객체(없으면 만든다) — 이어서 .ls · .tsls · .nls · .gmm · .liml · .wls · .fixed로 추정한다.

        이름은 시리즈 이름과 겹칠 수 없다(대소문자 무시 — 시리즈 G가 있으면 객체 이름 'g'도 안 된다).

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> eq = wf.equation("eq_i").ls("I c Y(-1) R")
            >>> round(float(eq.coefs["R"]), 2)
            -0.96

        관련: model · system
        """
        return self._get_or_new(name, EquationObject)

    def _new_equation_auto(self, spec: str, loud: bool = True) -> EquationObject:
        """식만 주어졌을 때 eq_<목표변수> 이름으로 추정·등록한다(모델 merge용)."""
        tmp = EquationObject(self, "_tmp")
        eq = tmp._make(spec)
        base = f"eq_{eq.target.lower()}"
        name, k = base, 2
        while name in self._objects:
            name, k = f"{base}_{k}", k + 1
        tmp.name = name
        self._register(tmp)
        return tmp._adopt(eq, spec, loud=loud)

    def system(self, name: str) -> SystemObject:
        """시스템 객체(없으면 만든다) — 여러 식을 함께 추정: .append(식…) → .ols · .sur · .tsls · .three_sls · .fiml.

        예
            >>> wf = eqn.datasets.load("klein_like")
            >>> s = wf.system("kl")
            >>> _ = s.append("CONS c PR PR(-1) WP+WG", "I c PR PR(-1) K(-1)", "@inst G T WG A PR(-1) K(-1) X(-1)")
            >>> _ = s.three_sls()
            >>> len(s.coefs)
            8
        """
        return self._get_or_new(name, SystemObject)

    def var(self, name: str, series, lags: int = 1, trend: str = "c") -> VARObject:
        """VAR(p)을 추정한 객체를 만든다(같은 이름이 있으면 바꾼다 — 추정이 실패하면 이전 객체를 그대로 둔다).

        매개변수
            name: 객체 이름
            series: 이름·식 목록 또는 공백 구분 글자(둘 이상, 겹치면 오류)
            lags: 시차(1 이상)
            trend: 'n' · 'c'(상수) · 'ct'(상수 + 추세)

        돌려주는 것
            VARObject — .coefs · .lag_order() · .granger() · .irf() · .fevd() · .forecast() · .stability(), model.merge(var)

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> v = wf.var("v1", ["dlog(Y)", "R"], lags=2)
            >>> v.coefs.shape
            (5, 2)
        """
        obj = VARObject(self, name).estimate(series, lags, trend)     # 추정이 성공해야 등록(실패하면 이전 객체 유지)
        self._replace_object(obj)
        return obj

    def vecm(self, name: str, series, lags_diff: int = 1, rank: int = 1, deterministic: str = "ci") -> VECMObject:
        """VECM(Johansen 최우)을 추정한 객체를 만든다(추정이 실패하면 이전 객체를 그대로 둔다).

        매개변수
            series: 이름·식 목록(둘 이상)
            lags_diff: 차분 시차 수(0 이상)
            rank: 공적분 순위(1 ~ 변수 수 − 1 — wf.johansen으로 정한다)
            deterministic: 'n' 또는 co·ci·lo·li 조합(관계 밖·안의 상수·선형추세, 예: 'ci' · 'colo' · 'ci lo')

        돌려주는 것
            VECMObject — .alpha · .beta · .gamma · .forecast(), model.merge(vecm)

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> _ = wf.smpl("1980Q1", "2019Q4")              # RL이 있는 구간
            >>> k = wf.vecm("k1", ["RL", "R"], rank=1)
            >>> round(float(k.beta.loc["R", "EC1"]), 1)
            -1.0
        """
        obj = VECMObject(self, name).estimate(series, lags_diff, rank, deterministic)
        self._replace_object(obj)
        return obj

    def model(self, name: str) -> ModelObject:
        """모델 객체(없으면 만든다) — 이어서 .merge(추정식) · .append(항등식) · .solve().

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> eq = wf.equation("eq_i").ls("I c Y(-1) R")
            >>> m = wf.model("toy").merge(eq, "CN c Y CN(-1)").append("Y = CN + I + G")
            >>> m.endogenous
            ['CN', 'I', 'Y']
        """
        return self._get_or_new(name, ModelObject)

    def graph(self, name: str, series, kind: str = "line", title: str = None, start=None, end=None) -> GraphObject:
        """그래프 객체. series: 이름 목록 또는 공백 구분 문자열(와일드카드 가능)."""
        g = GraphObject(self, name, series, kind=kind, title=title, start=start, end=end)
        g._columns()
        self._bounds(start, end)
        self._objects.pop(name.lower(), None)
        return self._register(g)

    def table(self, name: str, data, title: str = None) -> TableObject:
        """표 객체(DataFrame·출력 객체·방정식 등)."""
        t = TableObject(self, name, data, title=title)
        self._objects.pop(name.lower(), None)
        return self._register(t)

    def objects(self) -> TableOutput:
        """워크파일 객체 목록 표(종류·이름·요약, 시리즈 수 포함).

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> _ = wf.equation("eq_i").ls("I c Y(-1) R")
            >>> t = wf.objects()
            >>> "eq_i" in t.text()
            True
        """
        rows = []
        for o in self._objects.values():
            if isinstance(o, EquationObject):
                info = f"{o.eq.method.upper()} {o.eq.dependent_var}" if o.eq else "(추정 전)"
            elif isinstance(o, ModelObject):
                info = f"방정식 {len(o._eq_names)} · 항등식 {len(o._identities)} · 시나리오 {len(o._scenarios)}"
            elif isinstance(o, GraphObject):
                info = " ".join(o.series)
            elif isinstance(o, SystemObject):
                info = f"식 {len(o._lines)}" + (f" · {o.method}" if o.method else " · (추정 전)")
            elif isinstance(o, (VARObject, VECMObject)):
                info = " ".join(o.series)
            else:
                info = f"{o.frame.shape[0]}×{o.frame.shape[1]}"
            rows.append({"이름": o.name, "종류": o.kind, "내용": info})
        df = pd.DataFrame(rows, columns=["이름", "종류", "내용"])
        s = self.smpl()
        return TableOutput(df, title=f"워크파일 {self.name}", index=False, name=f"{self.name}_objects",
                           head=[f"{_FREQ_LABEL[self.freq]} · {self._label(self.index[0])}~{self._label(self.index[-1])}"
                                 f" · 시리즈 {len(self.data.columns)} · smpl {s[0]}~{s[1]}"])

    def show(self):
        """워크파일 요약(시리즈·객체 목록)을 보인다."""
        spool.show(self.objects())

    # ------------------------------------------------------------------
    # 저장 / 복원
    # ------------------------------------------------------------------
    def save(self, path: str = None) -> str:
        """워크파일을 `이름.eqw/` 폴더로 저장한다 — 시리즈·표본·메타데이터·페이지와 방정식(계수·잔차)·모델·시나리오·
        시스템·VAR·VECM·그래프·표. 다시 열면 재추정 없이 그대로 돌아온다.

        매개변수
            path: 폴더 경로(.eqw는 붙여 준다, 기본: 워크파일 이름)

        돌려주는 것
            저장한 폴더 경로

        오류
            ValueError: 경로가 이미 파일임

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> _ = wf.equation("eq_i").ls("I c Y(-1) R")
            >>> wf.save("doc_save")
            'doc_save.eqw'
            >>> eqn.wfopen("doc_save.eqw").obj("eq_i").coefs.round(2).tolist()
            [4.48, 0.15, -0.96]

        관련: wfopen
        """
        out = path or self.name
        if not out.endswith((EXT, *LEGACY_EXTS)):
            out += EXT
        if os.path.exists(out) and not os.path.isdir(out):
            raise ValueError(f"저장 경로 {out}이(가) 파일입니다 — 워크파일은 폴더(.eqw)로 저장합니다. 다른 경로를 주세요")
        os.makedirs(out, exist_ok=True)
        write_frame(out, "data", self.data)
        objs, resid = [], {}
        for o in self._objects.values():
            if isinstance(o, EquationObject):
                d = {"type": "equation", "name": o.name, "spec": o.spec,
                     "saved": o.eq.to_saved() if o.eq else None}
                if o.eq is not None and o.eq.residuals is not None:
                    resid[o.name] = o.eq.residuals
                objs.append(d)
            elif isinstance(o, ModelObject):
                objs.append({"type": "model", "name": o.name, "equations": list(o._eq_names),
                             "identities": list(o._identities), "active": o._active,
                             "scenarios": [_scenario_to_json(s, self) for s in o._scenarios.values()]})
            elif isinstance(o, (SystemObject, VARObject, VECMObject)):
                objs.append(o.to_json())
            elif isinstance(o, GraphObject):
                objs.append({"type": "graph", "name": o.name, "series": o.series, "kind": o.chart,
                             "title": o.title, "start": _s(o.start), "end": _s(o.end)})
            elif isinstance(o, TableObject):
                objs.append({"type": "table", "name": o.name, "title": o.title,
                             "frame": json.loads(o.frame.to_json(orient="split", date_format="iso"))})
        if resid:
            write_frame(out, "residuals", pd.DataFrame(resid))
        manifest = {
            "format": FORMAT, "format_version": FORMAT_VERSION, "engine_version": ENGINE_VERSION,
            "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "name": self.name, "freq": self.freq,
            "smpl": [_s(p) for p in self._smpl] if self._smpl else None,
            "indicators": dict(self._data.indicators),
            "objects": objs,
            "metadata": {k: dict(v) for k, v in self._meta.items()},
            "pages": sorted(self._pages),
        }
        for key, pg in self._pages.items():
            quiet(pg.save, os.path.join(out, "pages", key + EXT))
        _write_json(os.path.join(out, "workfile.json"), _jsonable(manifest))
        record_output(out, "workfile")
        say(f"[{self.name}] 저장 → {out} (시리즈 {len(self.data.columns)} · 객체 {len(objs)})")
        return out

    @staticmethod
    def load(path: str) -> "Workfile":
        """저장한 워크파일(.eqw 폴더)을 연다 — 보통은 `eqn.wfopen(path)`를 쓴다.

        복원하지 못한 객체(망가진 정의 등)는 건너뛰고 경고한다.

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> p = wf.save("doc_load")
            >>> eqn.Workfile.load(p).name
            'toy_q'

        관련: wfopen · save
        """
        man = _read_json(os.path.join(path, "workfile.json"))
        if man.get("format") not in (FORMAT, *LEGACY_FORMATS):
            raise ValueError(f"워크파일 형식이 아닙니다: {path}")
        record_input(path, "workfile")
        df = read_frame(path, "data")
        if df is None:
            raise ValueError(f"워크파일 자료(data.npz)가 없습니다: {path}")
        wf = _from_frame(df, man["freq"], man["name"], check=False)
        wf._data._indicators = dict(man.get("indicators") or {})
        if man.get("smpl"):
            a, b = man["smpl"]
            wf._smpl = (parse_period(a, wf.freq) if a else None, parse_period(b, wf.freq) if b else None)
        resid = read_frame(path, "residuals")
        models, skipped = [], []
        for d in man.get("objects", []):
            try:
                wf._restore_object(d, resid, models)
            except Exception as e:  # noqa: BLE001 — 객체 하나가 망가져도 워크파일은 연다
                skipped.append(f"{d.get('type')} {d.get('name')}: {str(e)[:120]}")
                wf._objects.pop(str(d.get("name", "")).lower(), None)
        if skipped:
            from ..log import workfile as _wlog
            _wlog.warning("[WARN] 복원하지 못한 객체(건너뜀):\n  " + "\n  ".join(skipped))
        for d in models:
            m = wf._register(ModelObject(wf, d["name"]))
            m._eq_names = list(d.get("equations", []))
            m._identities = list(d.get("identities", []))
            m._scenarios = {}
            for sd in d.get("scenarios", []):
                m._scenarios[sd["name"].lower()] = _scenario_from_json(m, sd, wf)
            if "baseline" not in m._scenarios:
                m._scenarios["baseline"] = ScenarioObject(m, "baseline", "_0")
            m._active = d.get("active", "baseline")
        wf._meta = {k: dict(v) for k, v in (man.get("metadata") or {}).items()}
        for key in man.get("pages") or []:
            pg = quiet(Workfile.load, os.path.join(path, "pages", key + EXT))
            pg._parent = wf
            wf._pages[key] = pg
        say(f"[{wf.name}] 열기 {path} (시리즈 {len(wf.data.columns)} · 객체 {len(wf._objects)}"
            + (f" · 페이지 {len(wf._pages)}" if wf._pages else "") + ")")
        return wf


class SeasonalResult:
    """wf.seas(...) 결과: .table(DataFrame — 실측·계절·추세·불규칙·조정)·.output()·.graph()·.show()."""

    def __init__(self, wf, series, method, model, table):
        self._wf, self.series, self.method, self.model, self.table = wf, series, method, model, table

    def __repr__(self):
        return f"<계절조정 {self.series}: {self.method}·{self.model} · {len(self.table)}기>"

    def output(self) -> TableOutput:
        """실측·계절·추세·불규칙·조정 표."""
        df = self.table.copy()
        df.index = pd.Index([self._wf._label(i) for i in df.index], name="기간")
        return TableOutput(df, title=f"{self.series} 계절조정({self.method}, {self.model})", name=f"{self.series}_seas")

    def graph(self):
        """실측·조정·추세 그림(GraphOutput)."""
        from .output import GraphOutput
        return GraphOutput(self.table[["실측", "조정", "추세"]], title=f"{self.series} 계절조정", name=f"{self.series}_seas_g")

    def show(self):
        """결과 표를 보인다."""
        spool.show(self.output())

    def _repr_html_(self):
        return self.output().html()


# ---------------------------------------------------------------------------
# 만들기 / 열기
# ---------------------------------------------------------------------------
def _from_frame(df: pd.DataFrame, freq: str, name: str, check: bool = True) -> Workfile:
    def build():
        wt = WorkTable(name=name, freq=freq, register=False)
        d = Data()
        d.data = df
        d.metadata = {"loaded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                      "n_rows": len(df), "n_cols": len(df.columns), "columns": list(df.columns),
                      "index_name": df.index.name or "N/A"}
        wt.set_data(d, check_freq=check)
        return wt
    return Workfile(quiet(build), name)


def wfcreate(name: str, freq: str, start, end) -> Workfile:
    """빈 워크파일을 만든다(모의 실험·가정 경로 만들기).

    매개변수
        name: 워크파일 이름(저장할 때 기본 파일 이름)
        freq: 주기 'Q'(분기) · 'M'(월) · 'A'(연)
        start, end: 처음·끝 기간('2000Q1' · '2000M1' · '2000')

    돌려주는 것
        Workfile — 시리즈 없음, 표본은 전체 기간.

    오류
        ValueError: 시점 표기가 주기와 맞지 않거나 start > end

    예
        >>> sim = eqn.wfcreate("sim", "Q", "2020Q1", "2021Q4")
        >>> sim["X"] = 1.0
        >>> sim.freq, len(sim.data), sim.smpl()
        ('Q', 8, ('2020Q1', '2021Q4'))

    관련: wfopen · datasets.load
    """
    f = normalize_freq(freq)
    p0, p1 = parse_period(start, f), parse_period(end, f)
    if p0 > p1:
        raise ValueError(f"시작({start})이 끝({end})보다 뒤입니다")
    idx = period_starts(p0, p1, f)
    df = pd.DataFrame(index=pd.DatetimeIndex(idx, name="date"))
    wf = _from_frame(df, f, name, check=False)
    say(f"[{name}] 새 워크파일 — {_FREQ_LABEL[f]} {format_period(p0, f)}~{format_period(p1, f)} ({len(idx)}기)")
    return apply_default_smpl(wf)


def wfopen(path: str, freq: str = None, name: str = None) -> Workfile:
    """워크파일 열기 — 데이터 파일(xlsx·csv), 저장한 워크파일(`.eqw/`, 옛 `.mmw/`), 옛 Work Table 번들(`.wt/`).

    데이터 파일은 첫 열을 날짜(2000-01-01)나 기간 라벨(2000Q1 · 2000M3 · 2000-03 · 2000)로 읽고 주기를 추론한다.
    빠진 기간은 빈 행(NaN)으로 채우고, 같은 날짜가 두 번이면 오류다. 저장한 워크파일은 재추정 없이 그대로 돌아온다.

    매개변수
        path: 파일 또는 `.eqw` 폴더 경로
        freq: 주기를 직접 정할 때 'Q' · 'M' · 'A'
        name: 워크파일 이름(기본: 파일 이름)

    돌려주는 것
        Workfile

    오류
        FileNotFoundError: 파일이 없음 · ValueError: 날짜 열을 읽지 못하거나 주기를 추론하지 못함

    예
        >>> wf = eqn.wfopen(eqn.datasets.path("toy_q"))
        >>> wf.freq, wf.smpl()
        ('Q', ('1970Q1', '2019Q4'))

    관련: wfcreate · Workfile.save · Workfile.read
    """
    p = path.rstrip("/\\")
    if os.path.isdir(p) and os.path.exists(os.path.join(p, "workfile.json")):
        return apply_default_smpl(Workfile.load(p))
    for ext in (EXT, *LEGACY_EXTS):
        if not os.path.isdir(p) and os.path.isdir(p + ext):
            return apply_default_smpl(Workfile.load(p + ext))
    if (os.path.isdir(p) and os.path.exists(os.path.join(p, "worktable.json"))) or \
            (not os.path.exists(p) and os.path.isdir(p + ".wt")):
        return apply_default_smpl(_from_worktable(p if os.path.isdir(p) else p + ".wt", name))
    data = quiet(Data, p)
    if not isinstance(data.data.index, pd.DatetimeIndex):
        raise ValueError(f"첫 열을 날짜·기간으로 읽지 못했습니다(예: 2000-01-01 · 2000Q1 · 2000M3 · 2000): {p}")
    if len(data.data) == 0:
        raise ValueError(f"자료 행이 없습니다: {p}")
    f = normalize_freq(freq) if freq else infer_freq_code(data.data.index, allow_gaps=True)
    if f is None:
        raise ValueError("데이터 주기를 추론하지 못했습니다 — freq='Q'|'M'|'A' 로 지정하세요.")
    from ..data.periods import regularize
    frame = regularize(data.data, f)          # 기간 첫날 · 빠진 기간은 빈 행
    added = len(frame) - len(data.data)
    nm = name or os.path.splitext(os.path.basename(p))[0]
    wf = _from_frame(frame, f, nm, check=True)
    wf._wt.data.file_path = p
    record_input(p, "data")
    say(f"[{nm}] 열기 {os.path.basename(p)} — {_FREQ_LABEL[f]} "
        f"{wf._label(wf.index[0])}~{wf._label(wf.index[-1])} · 시리즈 {len(wf.data.columns)}"
        + (f" · 빠진 기간 {added}개는 빈 칸으로" if added else ""))
    return apply_default_smpl(wf)


def _from_worktable(path: str, name: str = None, allow_pickle: bool = False) -> Workfile:
    """옛 Work Table 번들(또는 allow_pickle=True면 레거시 pickle) → 워크파일(방정식 eq_<목표변수>, 모델 1개)."""
    wt = quiet(WorkTable.load, path, False, False, allow_pickle)
    record_input(path, "worktable")
    return _from_wt(wt, name)


def _from_wt(wt: WorkTable, name: str = None) -> Workfile:
    wf = Workfile(wt, name or wt.name)
    m = wf._register(ModelObject(wf, wt.name if _NAME_RE.match(wt.name) and wt.name not in wf else "model1"))
    for eq in wt.equations:
        base = f"eq_{eq.target.lower()}"
        nm, k = base, 2
        while nm in wf._objects:
            nm, k = f"{base}_{k}", k + 1
        obj = wf._register(EquationObject(wf, nm))
        obj._adopt(eq, eq.original_input or eq.equation_str, loud=False)
        m._eq_names.append(nm)
    m._identities = list(wt.identity_strings)
    say(f"[{wf.name}] Work Table 번들 가져오기 — 방정식 {len(wt.equations)} · 항등식 {len(m._identities)} → 모델 {m.name}")
    return wf


# ---------------------------------------------------------------------------
# 보조
# ---------------------------------------------------------------------------
def _s(v):
    return None if v is None else str(v)


def _rename_vars(node, mapping):
    if isinstance(node, ir.Var):
        return ir.Var(mapping.get(node.name, node.name), node.lag)
    if isinstance(node, (ir.Const, ir.Coef)):
        return node
    if isinstance(node, ir.Neg):
        return ir.Neg(_rename_vars(node.arg, mapping))
    if isinstance(node, ir.Bin):
        return ir.Bin(node.op, _rename_vars(node.a, mapping), _rename_vars(node.b, mapping))
    if isinstance(node, ir.Func):
        return ir.Func(node.name, _rename_vars(node.arg, mapping))
    raise TypeError(node)


def _eval_scalar(node, arrays, t, T) -> float:
    def ev(n):
        if isinstance(n, ir.Const):
            return n.value
        if isinstance(n, ir.Var):
            r = t + n.lag
            return float(arrays[n.name][r]) if 0 <= r < T else math.nan
        if isinstance(n, ir.Neg):
            return -ev(n.arg)
        if isinstance(n, ir.Bin):
            a, b = ev(n.a), ev(n.b)
            try:
                if n.op == "+":
                    return a + b
                if n.op == "-":
                    return a - b
                if n.op == "*":
                    return a * b
                if n.op == "/":
                    return a / b
                return math.pow(a, b)
            except (ZeroDivisionError, ValueError, OverflowError):
                return math.nan
        if isinstance(n, ir.Func):
            v = ev(n.arg)
            try:
                return ir._SCALAR_FUNCS[n.name](v)
            except (ValueError, OverflowError):
                return math.nan
        raise TypeError(n)
    return ev(node)


def _path_json(path, wf: Workfile):
    """시나리오 경로(Series·dict·스칼라) → JSON."""
    if isinstance(path, pd.Series):
        s = path.dropna()
        return {"series": {str(pd.Timestamp(k).date()) if isinstance(k, (pd.Timestamp, np.datetime64)) else str(k): float(v)
                           for k, v in s.items()}}
    if isinstance(path, dict):
        return {"dict": {str(k): float(v) for k, v in path.items()}}
    if isinstance(path, (list, tuple)) and len(path) == 2:
        return {"range": [_s(path[0]), _s(path[1])]}
    if path is True or path is None:
        return {"all": True}
    return {"scalar": float(path)}


def _path_from_json(d):
    if "series" in d:
        from ..data.periods import parse_dates
        items = d["series"]
        idx = parse_dates(list(items))           # ISO 날짜·기간 라벨('2010Q1') → 기간 첫날(pandas 시간 API를 직접 쓰지 않는다)
        return pd.Series(list(items.values()), index=idx if idx is not None else list(items), dtype=float)
    if "dict" in d:
        return dict(d["dict"])
    if "range" in d:
        return tuple(d["range"])
    if "all" in d:
        return True
    return d["scalar"]


def _scenario_to_json(so: ScenarioObject, wf: Workfile) -> dict:
    sc = so._sc
    return {
        "name": so.name, "alias": so.alias,
        "overrides": {k: _path_json(v, wf) for k, v in sc.exo_overrides.items()},
        "excludes": {k: _path_json(v, wf) for k, v in sc.excludes.items()},
        "add_factors": {k: _path_json(v, wf) for k, v in sc.add_factors.items()},
        "add_factor_inits": [[v, _s(b), h] for v, b, h in sc.add_factor_inits],
        "shocks": [[v, val, _s(a), _s(b), k] for v, val, a, b, k in sc.shocks],
        "controls": [[t, i, _path_json(p, wf)] for t, i, p in sc.controls],
        "residual_af": bool(getattr(sc, "residual_af", False)),
    }


def _scenario_from_json(m: ModelObject, d: dict, wf: Workfile) -> ScenarioObject:
    so = ScenarioObject(m, d["name"], d["alias"])
    sc = so._sc
    sc.exo_overrides = {k: _path_from_json(v) for k, v in d.get("overrides", {}).items()}
    sc.excludes = {k: _path_from_json(v) for k, v in d.get("excludes", {}).items()}
    sc.add_factors = {k: _path_from_json(v) for k, v in d.get("add_factors", {}).items()}
    sc.add_factor_inits = [tuple(x) for x in d.get("add_factor_inits", [])]
    sc.shocks = [tuple(x) for x in d.get("shocks", [])]
    sc.controls = [(t, i, _path_from_json(p)) for t, i, p in d.get("controls", [])]
    sc.residual_af = bool(d.get("residual_af", False))
    return so
