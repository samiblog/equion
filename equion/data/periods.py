#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""기간·주기 — 시간 인덱스 연산은 모두 이 모듈을 거친다(pandas 버전 변화를 한 곳에서 흡수).

정규 주기 코드: Q(분기) · M(월) · A(연). 시계열 인덱스는 각 기간 **첫날**의 Timestamp(DatetimeIndex)다.
pandas의 주기 문자열('Q'·'QS'·'Y'…)과 동작이 버전마다 바뀌어 왔으므로(예: 연 'A' → 'Y', infer_freq 반환형),
다른 모듈은 pandas 시간 API를 직접 부르지 말고 여기 함수를 쓴다.
"""

import re
from typing import Optional

import numpy as np
import pandas as pd

FREQ_ALIASES = {
    "Q": "Q", "QUARTER": "Q", "QUARTERLY": "Q", "분기": "Q",
    "M": "M", "MONTH": "M", "MONTHLY": "M", "월": "M", "월별": "M",
    "A": "A", "Y": "A", "ANNUAL": "A", "YEAR": "A", "YEARLY": "A",
    "연": "A", "연간": "A", "연별": "A",
}
PERIOD_FREQ = {"Q": "Q", "M": "M", "A": "Y"}      # pandas Period 주기
RESAMPLE_RULE = {"Q": "QS", "M": "MS", "A": "YS"}  # 기간 첫날 기준 리샘플 규칙
FREQ_LABEL = {"Q": "분기(Quarterly)", "M": "월(Monthly)", "A": "연(Annual)"}
PERIODS_PER_YEAR = {"Q": 4, "M": 12, "A": 1}
_MONTH_STEP = {3: "Q", 1: "M", 12: "A"}


def normalize_freq(freq: str) -> str:
    """사용자 주기 입력을 정규 코드(Q/M/A)로 변환한다."""
    if freq is None:
        raise ValueError("freq가 필요합니다 (Q/M/A).")
    key = str(freq).strip().upper()
    if key in FREQ_ALIASES:
        return FREQ_ALIASES[key]
    raise ValueError(f"알 수 없는 주기: {freq!r} (사용 가능: Q, M, A)")


def infer_freq_code(index: pd.Index, allow_gaps: bool = False):
    """DatetimeIndex에서 정규 주기 코드(Q/M/A)를 추론한다(연속한 날짜의 개월 차가 모두 3·1·12). 실패 시 None.
    allow_gaps=True면 개월 차 중 가장 작은 값이 3·1·12이고 나머지가 그 배수일 때도 그 주기(빠진 기간이 있는 자료 —
    부르는 쪽이 regularize로 빈 칸을 채워야 한다. 그대로 쓰면 시차가 어긋난다).

    pandas.infer_freq를 쓰지 않는다 — 반환형이 버전마다 바뀌고(pandas 4: 문자열 → 오프셋 객체),
    분기 첫날·말일·영업일 표기를 모두 같은 '분기'로 보면 충분하다."""
    if not isinstance(index, pd.DatetimeIndex) or len(index) < 3:
        return None
    months = np.asarray(index.year, dtype=np.int64) * 12 + np.asarray(index.month, dtype=np.int64)
    steps = np.unique(np.diff(months))
    if len(steps) == 0 or steps.min() <= 0:
        return None
    base = int(steps.min())
    if base not in _MONTH_STEP or np.any(steps % base) or (len(steps) > 1 and not allow_gaps):
        return None
    if base in (3, 12) and len(np.unique(months % base)) != 1:      # 분기·연인데 달 위치가 들쭉날쭉
        return None
    return _MONTH_STEP[base]


_LABEL_PATTERNS = (
    (re.compile(r"^(\d{4})\s*[Qq]([1-4])$"), lambda m: pd.Timestamp(int(m[1]), 3 * int(m[2]) - 2, 1)),
    (re.compile(r"^(\d{4})\s*[Mm](\d{1,2})$"), lambda m: pd.Timestamp(int(m[1]), int(m[2]), 1)),
    (re.compile(r"^(\d{4})-(\d{1,2})$"), lambda m: pd.Timestamp(int(m[1]), int(m[2]), 1)),
    (re.compile(r"^(\d{4})(?:\.0)?$"), lambda m: pd.Timestamp(int(m[1]), 1, 1)),
)


def parse_dates(values) -> Optional[pd.DatetimeIndex]:
    """파일의 날짜 열 → DatetimeIndex. 기간 라벨('2000Q1'·'2000M3'·'2000-03'·연도 2000)은 기간 첫날로, 그 밖은
    ISO 날짜로 읽는다(형식을 추측하지 않는다 — pandas의 경고·모호한 일/월 해석을 피함). 날짜가 아니면 None."""
    vals = list(values)
    if not vals:
        return None
    if isinstance(values, pd.DatetimeIndex):
        return values
    strs = [str(v).strip() for v in vals]
    for pat, make in _LABEL_PATTERNS:
        ms = [pat.match(x) for x in strs]
        if all(ms):
            try:
                if pat.pattern.startswith("^(\\d{4})(?:"):          # 연도: 범위 확인
                    if not all(1000 <= int(m[1]) <= 3000 for m in ms):
                        return None
                return pd.DatetimeIndex([make(m) for m in ms])
            except ValueError:
                return None
    for kw in ({"format": "ISO8601"}, {"format": "mixed", "dayfirst": False}):
        try:
            return pd.DatetimeIndex(pd.to_datetime(pd.Series(vals), **kw))
        except (ValueError, TypeError):
            continue
    return None


def regularize(df: pd.DataFrame, freq: str) -> pd.DataFrame:
    """날짜를 기간 첫날로 맞추고 빠진 기간은 빈 행(NaN)으로 채운 정규 인덱스의 표. 같은 기간이 둘이면 오류."""
    per = periods_of(df.index, freq)
    if per.has_duplicates:
        dup = per[per.duplicated()][0]
        raise ValueError(f"같은 기간({format_period(dup, freq)})의 행이 둘 이상입니다")
    out = df.copy()
    out.index = pd.DatetimeIndex([p.start_time for p in per], name=df.index.name)
    full = period_starts(per.min(), per.max(), freq)
    if len(full) != len(out) or not out.index.equals(full):
        out = out.reindex(full)
        out.index.name = df.index.name
    return out


def parse_period(token, freq: str) -> pd.Period:
    """'2000Q1' / '2000M3' / '2000-03' / '2000' 등을 freq에 맞는 Period로 변환."""
    if token is None:
        return None
    if isinstance(token, pd.Period):
        return token.asfreq(PERIOD_FREQ[freq])
    s = str(token).strip().upper()
    pf = PERIOD_FREQ[freq]
    hint = {"Q": "2000Q1", "M": "2000M3 또는 2000-03", "A": "2000"}[freq]
    other = ("Q" if re.fullmatch(r"\d{4}Q[1-4]", s) else "M" if re.fullmatch(r"\d{4}M\d{1,2}", s) else None)
    if other and other != freq:      # 다른 주기의 기간 표기(연간에 '2000Q1', 월간에 '2015Q2')는 받지 않는다
        raise ValueError(f"시점 표기 오류: {token!r}은(는) {FREQ_LABEL[other]} 표기입니다 — "
                         f"{FREQ_LABEL[freq]} 자료의 시점은 {hint} 꼴입니다")
    if freq == "A":                                   # 연도만 들어온 경우
        s = s.replace("A", "").replace("Y", "")
    if freq == "M" and "M" in s and "-" not in s:     # 'YYYYMn' → 'YYYY-0n'
        y, m = s.split("M", 1)
        s = f"{y}-{int(m):02d}"
    try:
        return pd.Period(s, freq=pf)
    except Exception:
        raise ValueError(f"시점 표기 오류: {token!r} — {FREQ_LABEL[freq]} 자료의 시점은 {hint} 꼴입니다") from None


def to_period(ts, freq: str) -> pd.Period:
    """Timestamp → 해당 주기의 Period."""
    return pd.Timestamp(ts).to_period(PERIOD_FREQ[freq])


def locate(index: pd.DatetimeIndex, token, freq: str) -> int:
    """시점 표기('2000Q1'·'2000M3'·'2000')의 인덱스 위치. 없으면 ValueError(자료 기간과 extend 안내)."""
    target = parse_period(token, freq)
    for i, ts in enumerate(index):
        if to_period(ts, freq) == target:
            return i
    span = (f"{format_period(to_period(index[0], freq), freq)}~{format_period(to_period(index[-1], freq), freq)}"
            if len(index) else "비어 있음")
    raise ValueError(f"데이터에서 시점을 찾을 수 없음: {token} — 기간은 {span}입니다(늘리려면 extend)")


def periods_of(index: pd.DatetimeIndex, freq: str) -> pd.PeriodIndex:
    """DatetimeIndex 전체 → PeriodIndex."""
    return pd.DatetimeIndex(index).to_period(PERIOD_FREQ[freq])


def format_period(p, freq: str = "Q") -> str:
    """기간(Timestamp/Period) → 라벨. 연 '2003' · 분기 '2003Q1' · 월 '2003M3'."""
    if freq == "A":
        return f"{p.year}"
    if freq == "M":
        return f"{p.year}M{p.month}"
    return f"{p.year}Q{p.quarter}"


def period_starts(start, end, freq: str) -> pd.DatetimeIndex:
    """start~end(양끝 포함) 각 기간의 첫날. start·end는 Period 또는 '2000Q1' 같은 표기.

    인덱스에 pandas freq를 달지 않는다 — 분기 freq(QS-OCT 등)가 달리면 pandas가 `s.loc['2001Q2']`의 분기를
    회계연도 기준으로 읽어 한 분기 어긋난 값을 돌려준다."""
    p0 = start if isinstance(start, pd.Period) else parse_period(start, freq)
    p1 = end if isinstance(end, pd.Period) else parse_period(end, freq)
    return pd.DatetimeIndex(pd.period_range(p0, p1, freq=PERIOD_FREQ[freq]).to_timestamp(how="start"), freq=None)


def shift_months(ts, months: int) -> pd.Timestamp:
    """날짜를 개월 단위로 옮긴다(음수면 과거로)."""
    return pd.Timestamp(ts) + pd.DateOffset(months=int(months))


def resample(df: pd.DataFrame, freq: str, how="mean") -> pd.DataFrame:
    """다른 주기로 변환(기간 첫날 인덱스). how: 'mean'·'sum'·'last'… 또는 {열: 규칙}."""
    r = df.resample(RESAMPLE_RULE[normalize_freq(freq)])
    return r.agg(how) if isinstance(how, dict) else getattr(r, how)()
