#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""데이터 로딩·관리 모듈 — Data 클래스.

(구 equation_model_core.py에서 분리. 로직 무변경.)
"""

import os
import re
import numpy as np
import pandas as pd
from typing import List, Dict, Optional, Union
from datetime import datetime
import warnings
from ..log import engine as _log


class Data:
    """(고급) 자료 객체 — 시계열 DataFrame과 지시자 열(@trend·@seas·@d 등)을 관리한다. 워크파일이 안에서 쓴다.

    보통은 워크파일 API(`eqn.wfopen`·`eqn.datasets.load`)를 쓴다. 엔진을 직접 다룰 때는 `wf._data` 대신 파일에서 만든다.

    예
        >>> d = eqn.Data(eqn.datasets.path("toy_q"))           # 엔진 객체는 진행 로그를 찍는다
        [OK] 데이터 로드: toy_q.csv (200행 x 10열)
        >>> d.data.shape
        (200, 10)
    """

    def __init__(self, file_path: str = None, index_col: str = None):
        self.data = None
        self.file_path = None
        self.metadata = {}

        if file_path:
            self.load(file_path, index_col)

    def load(self, file_path: str, index_col: str = None):
        """
        엑셀/CSV 파일 로드 (파일 읽기는 equion.data.io에 위임)

        Args:
            file_path: 데이터 파일 경로
            index_col: 인덱스 컬럼명 (None이면 자동 감지)
        """
        from .io import read_dataframe
        df = read_dataframe(file_path, index_col)

        self.data = df
        self.file_path = file_path
        self.metadata = {
            'loaded_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'n_rows': len(df),
            'n_cols': len(df.columns),
            'columns': list(df.columns),
            'index_name': df.index.name if df.index.name else 'N/A'
        }

        _log.info(f"[OK] 데이터 로드: {os.path.basename(file_path)} ({len(df)}행 x {len(df.columns)}열)")
        self._warn_case_collisions()

    def _warn_case_collisions(self):
        """대소문자만 다른 중복 열을 감지해 경고한다.

        변수명을 대소문자 구분 없이 사용하므로(canonicalize_columns), 철자는
        같고 대소문자만 다른 열들은 서로 구분되지 않아 어느 열로 매칭될지
        모호해진다. 이 경우 사용자가 데이터에서 열 이름을 수정하도록 안내한다.
        """
        if self.data is None:
            return
        from ..formula.parser import reserved_name_error
        bad = [str(c) for c in self.data.columns if reserved_name_error(str(c))]
        if bad:
            msg = (f"[경고] 방정식에서 쓸 수 없는 열 이름: {', '.join(bad)} — C는 상수항, LOG·EXP·ABS·SQRT·D·DLOG는 "
                   "함수 이름입니다. 이 열을 식에 쓰려면 파일에서 이름을 바꿔 주세요.")
            _log.info(msg)
            warnings.warn(msg, stacklevel=2)
        groups = {}
        for col in self.data.columns:
            groups.setdefault(str(col).lower(), []).append(str(col))
        dups = [v for v in groups.values() if len(v) > 1]
        if not dups:
            return
        lines = "\n".join(f"    · {' / '.join(g)}" for g in dups)
        msg = (
            "[경고] 대소문자만 다른 중복 열이 발견되었습니다.\n"
            "       변수명은 대소문자를 구분하지 않으므로 아래 열들은 서로 구분되지\n"
            "       않아 어느 열이 사용될지 모호합니다(임의로 첫 열이 선택됨):\n"
            f"{lines}\n"
            "       → 데이터 파일에서 해당 열 이름을 철자까지 서로 다르게 수정해 주세요."
        )
        _log.info(msg)
        warnings.warn(msg, stacklevel=2)

    def add_column(self, name: str, values: Union[pd.Series, np.ndarray, list]):
        """컬럼 추가"""
        if self.data is None:
            raise ValueError("데이터가 로드되지 않았습니다.")
        self.data[name] = values
        self.metadata['n_cols'] = len(self.data.columns)
        self.metadata['columns'] = list(self.data.columns)
        _log.info(f"[OK] 컬럼 추가: {name}")

    def get_column(self, name: str) -> pd.Series:
        """컬럼 값 가져오기"""
        if self.data is None:
            raise ValueError("데이터가 로드되지 않았습니다.")
        if name not in self.data.columns:
            raise ValueError(f"컬럼을 찾을 수 없습니다: {name}")
        return self.data[name]

    def has_column(self, name: str) -> bool:
        """컬럼 존재 여부 확인"""
        if self.data is None:
            return False
        return name in self.data.columns

    def get_index(self) -> pd.Index:
        """인덱스 가져오기"""
        if self.data is None:
            raise ValueError("데이터가 로드되지 않았습니다.")
        return self.data.index

    def get_value(self, index, column: str):
        """특정 위치의 값 가져오기"""
        if self.data is None:
            raise ValueError("데이터가 로드되지 않았습니다.")
        return self.data.loc[index, column]

    def info(self):
        """데이터 정보 출력"""
        if self.data is None:
            _log.info("데이터가 로드되지 않았습니다.")
            return

        _log.info("=" * 60)
        _log.info("Data 정보")
        _log.info("=" * 60)
        _log.info(f"파일: {os.path.basename(self.file_path) if self.file_path else 'N/A'}")
        _log.info(f"로드 시간: {self.metadata['loaded_at']}")
        _log.info(f"행 수: {self.metadata['n_rows']}")
        _log.info(f"열 수: {self.metadata['n_cols']}")
        _log.info(f"인덱스: {self.metadata['index_name']}")
        _log.info(f"\n컬럼 목록 (처음 20개):")
        for i, col in enumerate(self.metadata['columns'][:20]):
            _log.info(f"  {i+1:2}. {col}")
        if self.metadata['n_cols'] > 20:
            _log.info(f"  ... (외 {self.metadata['n_cols'] - 20}개)")
        _log.info("=" * 60)

    def __repr__(self):
        if self.data is None:
            return "Data(empty)"
        return f"Data(rows={len(self.data)}, cols={len(self.data.columns)})"

    def __len__(self):
        if self.data is None:
            return 0
        return len(self.data)

    # ------------------------------------------------------------------
    # 주기 / 결정적 지시자 (엔진 v3: 주기 인지 + 기간 확장 시 자동 재생성)
    # ------------------------------------------------------------------
    @property
    def freq(self) -> str:
        """데이터 주기 코드(Q/M/A). WorkTable 역참조가 있으면 그 주기, 없으면 인덱스로 추론."""
        wt = getattr(self, 'wt', None)
        if wt is not None:
            return wt.freq
        from .periods import infer_freq_code
        code = infer_freq_code(self.data.index) if self.data is not None else None
        return code or 'Q'

    @property
    def indicators(self) -> Dict[str, str]:
        """생성된 결정적 지시자 컬럼 → 정의(spec). extend() 시 재생성에 쓴다."""
        if not hasattr(self, '_indicators'):
            self._indicators = {}
        return self._indicators

    def _ensure_datetime_index(self):
        if not isinstance(self.data.index, pd.DatetimeIndex):
            from .periods import parse_dates
            idx = parse_dates(self.data.index)       # 기간 라벨('2000Q1')·ISO 날짜 — 형식을 추측하지 않는다
            if idx is None:
                raise ValueError("인덱스를 DatetimeIndex로 변환할 수 없습니다.")
            self.data.index = idx

    def _set_columns(self, cols: Dict[str, np.ndarray]):
        """여러 컬럼을 한 번에 설정(단편화 경고 없이)."""
        new = {k: v for k, v in cols.items() if k not in self.data.columns}
        for k, v in cols.items():
            if k in self.data.columns:
                self.data[k] = v
        if new:
            self.data = pd.concat([self.data, pd.DataFrame(new, index=self.data.index)], axis=1)
        self.metadata['n_cols'] = len(self.data.columns)
        self.metadata['columns'] = list(self.data.columns)

    def set_user_columns(self, cols: Dict[str, np.ndarray]):
        """사용자가 쓰는 열(대입·genr·read) — 지시자 열 이름에 쓰면 그 열은 이제 사용자 자료라 지시자 등록을 지운다
        (기간을 늘려도 다시 계산해 덮어쓰지 않고, 다음에 그 지시자를 쓰면 _claim_indicator가 알린다)."""
        for k in cols:
            self.indicators.pop(k, None)
        self._set_columns(cols)

    def _claim_indicator(self, col: str, spec: str, values: np.ndarray) -> bool:
        """지시자 열 이름 col을 지시자로 써도 되는가 — 사용자 열을 지시자로 몰래 쓰거나 덮어쓰지 않는다.

        이미 지시자로 등록된 열이면 그대로 쓴다. 등록되지 않은 같은 이름(대소문자 무시) 열이 있으면, 이름까지 같고 값이
        지시자 값과 똑같을 때만 지시자로 받아들이고(지시자 열을 파일로 내보냈다 다시 연 경우 — 등록을 잃은 채 기간을
        늘려 뒤쪽만 빈 칸이면 그 칸을 채운다), 아니면 오류다 — 그 열을 지시자로 쓰면 계수가 몰래 틀리고, 기간을 늘릴 때
        사용자 자료가 지시자 값으로 덮인다. 열 이름을 바꿀지는 사람이 정한다(엔진이 지시자 열 이름을 바꾸면 계수 이름이
        바뀌어 기존 결과와 맞지 않는다).

        돌려주는 것: 열을 (다시) 써야 하면 True."""
        if col in self.indicators and col in self.data.columns:
            return False
        low = col.lower()
        have = next((str(c) for c in self.data.columns if str(c).lower() == low), None)
        if have is None:
            return True
        same, fill = False, False
        if have == col:
            try:
                cur = self.data[have].to_numpy(dtype=float)
                want = np.asarray(values, dtype=float)
                n_ok = int(np.isfinite(cur).sum())
                same = (cur.shape == want.shape and n_ok > 0 and bool(np.isfinite(cur[:n_ok]).all())
                        and bool(np.array_equal(cur[:n_ok], want[:n_ok])))
                fill = same and n_ok < len(cur)
            except (TypeError, ValueError):
                same = False
        if not same:
            raise ValueError(f"자료의 '{have}' 열이 {spec}이(가) 만드는 지시자 열 '{col}'과(와) 이름이 겹칩니다(변수 이름은 "
                             f"대소문자를 가리지 않습니다) — 사용자 열을 {spec} 대신 쓰거나 덮어쓰지 않도록 멈춥니다. "
                             f"자료에서 '{have}' 열의 이름을 바꿔 주세요.")
        return fill

    def seasonal_columns(self) -> List[str]:
        """현 주기의 계절더미 컬럼명 목록 (분기 _Q1.._Q4 / 월 _M1.._M12)."""
        freq = self.freq
        if freq == 'Q':
            return [f'_Q{q}' for q in range(1, 5)]
        if freq == 'M':
            return [f'_M{m}' for m in range(1, 13)]
        raise ValueError("@seas는 연간 데이터에서 쓸 수 없습니다(계절성이 없습니다).")

    def ensure_seasonal_dummies(self):
        """계절더미 내부 컬럼을 필요 시 생성한다 (@seas 전용, 멱등).

        분기 → _Q1.._Q4, 월 → _M1.._M12. 연간은 오류.
        사용자가 q1~q4를 직접 쓰는 기능은 제거되었으며,
        계절성은 @seas / @seas(n) 으로만 사용한다.
        """
        if self.data is None:
            raise ValueError("데이터가 로드되지 않았습니다.")
        cols = self.seasonal_columns()
        self._ensure_datetime_index()
        attr = 'quarter' if self.freq == 'Q' else 'month'
        values = getattr(self.data.index, attr)
        dummies = {c: (values == k).astype(int) for k, c in enumerate(cols, 1)}
        self._set_columns({c: v for c, v in dummies.items() if self._claim_indicator(c, '@seas', v)})
        for k, c in enumerate(cols, 1):
            self.indicators[c] = f'@seas({k})'

    def add_dummy_variables(self):
        """(폐지됨) 과거 q1~q4 분기더미 생성 메서드.

        계절성은 이제 @seas / @seas(n) 으로만 사용한다. 하위호환을 위해
        호출은 허용하지만 q 컬럼을 만들지 않는다(아무 동작도 하지 않음)."""
        warnings.warn(
            "add_dummy_variables()는 폐지되었습니다. 계절더미는 @seas / @seas(n)을 사용하세요.",
            DeprecationWarning, stacklevel=2)

    def _period_pos(self, token: str):
        """'2008Q4' / '2008M3' / '2008' 등 → (행 위치 또는 None, 표준 라벨)."""
        from ..worktable.freq import parse_period, to_period
        freq = self.freq
        p = parse_period(token, freq)
        if freq == 'Q':
            label = f"{p.year}Q{p.quarter}"
        elif freq == 'M':
            label = f"{p.year}M{p.month:02d}"
        else:
            label = f"{p.year}"
        for i, dt in enumerate(self.data.index):
            if to_period(dt, freq) == p:
                return i, label
        return None, label

    def _quarter_to_pos(self, q: str) -> Optional[int]:
        """(하위호환) 시점 표기 → 행 위치(정수). 못 찾으면 None."""
        return self._period_pos(q)[0]

    def _indicator_values(self, spec: str) -> np.ndarray:
        """지시자 정의 → 현재 인덱스 길이의 값 배열."""
        n = len(self.data)
        if spec == '@trend':
            return np.arange(n, dtype=float)
        m = re.match(r'^@seas\((\d+)\)$', spec)
        if m:
            k = int(m.group(1))
            attr = 'quarter' if self.freq == 'Q' else 'month'
            return (getattr(self.data.index, attr) == k).astype(int)
        m = re.match(r'^@step\(\s*([^)]+?)\s*\)$', spec)
        if m:
            pos, _ = self._period_pos(m.group(1))
            if pos is None:
                raise ValueError(f"@step 시점을 데이터에서 찾을 수 없음: {m.group(1)}")
            v = np.zeros(n)
            v[pos:] = 1.0
            return v
        m = re.match(r'^@d\(\s*([^)]+?)\s*\)$', spec)
        if m:
            arg = m.group(1).strip()
            if ':' in arg:
                a, b = [x.strip() for x in arg.split(':', 1)]
                p1, _ = self._period_pos(a)
                p2, _ = self._period_pos(b)
                if p1 is None or p2 is None:
                    raise ValueError(f"@d 구간 시점을 찾을 수 없음: {arg}")
                if p1 > p2:
                    p1, p2 = p2, p1
                v = np.zeros(n)
                v[p1:p2 + 1] = 1.0
                return v
            pos, _ = self._period_pos(arg)
            if pos is None:
                raise ValueError(f"@d 시점을 데이터에서 찾을 수 없음: {arg}")
            v = np.zeros(n)
            v[pos] = 1.0
            return v
        raise ValueError(f"인식할 수 없는 지시자: {spec}")

    def ensure_indicator(self, spec: str) -> str:
        """
        지시자 토큰을 데이터 컬럼으로 생성하고 컬럼명을 반환한다(멱등, 주기 인지).

        지원 토큰 (시점 표기는 주기에 맞게: 분기 2008Q4 / 월 2008M3·2008-03 / 연 2008):
          @trend              → 선형추세 컬럼 TREND (0,1,2,...)
          @d(2008Q4)          → 펄스 더미 D_2008Q4 (해당 시점만 1)
          @d(2008Q4:2009Q1)   → 구간 더미 D_2008Q4_2009Q1 (구간 내 1)
          @step(2020Q1)       → 계단 더미 STEP_2020Q1 (해당 시점부터 1)
        """
        spec = spec.strip()
        if spec.lower() == '@trend':                 # 지시자 이름은 대소문자를 가리지 않는다(@TREND·@Step(…))
            spec, col = '@trend', 'TREND'
        else:
            m = re.match(r'^@(d|step)\(\s*([^)]+?)\s*\)$', spec, re.IGNORECASE)
            if not m:
                raise ValueError(f"인식할 수 없는 지시자: {spec}")
            kind, arg = m.group(1).lower(), m.group(2).strip()
            spec = f"@{kind}({arg})"
            if ':' in arg and kind == 'd':
                a, b = [x.strip() for x in arg.split(':', 1)]
                col = f"D_{self._period_pos(a)[1]}_{self._period_pos(b)[1]}"
            elif kind == 'd':
                col = f"D_{self._period_pos(arg)[1]}"
            else:
                col = f"STEP_{self._period_pos(arg)[1]}"
        if not (col in self.indicators and col in self.data.columns):
            values = self._indicator_values(spec)
            if self._claim_indicator(col, spec, values):
                self._set_columns({col: values})
                _log.info(f"[OK] 지시자 컬럼 생성: {col} ({spec})")
        self.indicators[col] = spec
        return col

    def refresh_indicators(self):
        """등록된 결정적 지시자(추세·계절·더미) 컬럼을 현재 인덱스 길이로 다시 계산한다."""
        if not self.indicators:
            return
        self._set_columns({c: self._indicator_values(spec) for c, spec in self.indicators.items()})

    # ------------------------------------------------------------------
    # 기간 확장 / 외생 경로 채우기 (전망용)
    # ------------------------------------------------------------------
    def extend(self, end) -> int:
        """인덱스를 end 시점까지 늘린다(새 행은 NaN, 결정적 지시자는 재계산).

        Returns:
            추가된 기간 수(이미 충분하면 0).
        """
        from .periods import parse_period, period_starts, to_period
        if self.data is None:
            raise ValueError("데이터가 로드되지 않았습니다.")
        self._ensure_datetime_index()
        freq = self.freq
        last = to_period(self.data.index[-1], freq)
        target = parse_period(end, freq, end=True)
        if target <= last:
            return 0
        new_index = period_starts(last + 1, target, freq)
        name = self.data.index.name
        ext = pd.DataFrame(np.nan, index=new_index, columns=self.data.columns)
        self.data = pd.concat([self.data, ext])
        self.data.index.name = name
        self.refresh_indicators()
        self.metadata['n_rows'] = len(self.data)
        _log.info(f"[OK] 기간 확장: {last} → {target} (+{len(new_index)}기)")
        return len(new_index)

    def fill_series(self, columns, method: str = 'last', start=None, end=None,
                    window: int = None) -> Dict[str, int]:
        """열의 마지막 관측 이후 결측을 규칙으로 채운다(외생 가정 경로 초안용).

        method:
          'last'   : 마지막 관측값 유지
          'growth' : 최근 window기 평균 성장률(로그) 지속 (window 기본 = 연간 시차)
          'trend'  : 최근 window기 평균 증분(선형) 지속
        start/end: 채울 구간(기본: 마지막 관측 다음 ~ 데이터 끝).
        Returns: {열: 채운 기간 수}
        """
        from .periods import parse_period, to_period
        if isinstance(columns, str):
            columns = [columns]
        freq = self.freq
        if window is None:
            window = {'Q': 4, 'M': 12, 'A': 1}.get(freq, 4)
        elif method in ('growth', 'trend') and (isinstance(window, bool) or not isinstance(window, (int, np.integer))
                                               or window < 1):
            raise ValueError(f"window는 1 이상의 정수입니다(받은 값 {window!r}) — 최근 몇 기의 평균 "
                             f"{'성장률' if method == 'growth' else '증분'}을 이어 갈지입니다")
        periods = [to_period(ts, freq) for ts in self.data.index]
        p_start = parse_period(start, freq) if start is not None else None
        p_end = parse_period(end, freq, end=True) if end is not None else None
        filled = {}
        for col in columns:
            if col not in self.data.columns:
                raise ValueError(f"컬럼을 찾을 수 없습니다: {col}")
            s = self.data[col].astype(float).to_numpy().copy()
            valid = np.where(np.isfinite(s))[0]
            if len(valid) == 0:
                raise ValueError(f"'{col}'에 관측값이 없어 채울 수 없습니다.")
            last = valid[-1]
            if method == 'growth':
                base = s[max(0, last - window):last + 1]
                base = base[np.isfinite(base)]
                if len(base) < 2 or np.any(base <= 0):
                    raise ValueError(f"'{col}': growth 방식은 양수 관측 2개 이상이 필요합니다.")
                step = (np.log(base[-1]) - np.log(base[0])) / (len(base) - 1)
            elif method == 'trend':
                base = s[max(0, last - window):last + 1]
                base = base[np.isfinite(base)]
                step = (base[-1] - base[0]) / (len(base) - 1) if len(base) >= 2 else 0.0
            elif method != 'last':
                raise ValueError(f"알 수 없는 method: {method} (last/growth/trend)")
            n = 0
            for i in range(last + 1, len(s)):
                if p_start is not None and periods[i] < p_start:
                    continue
                if p_end is not None and periods[i] > p_end:
                    break
                if np.isfinite(s[i]):
                    continue
                prev = s[i - 1]
                if method == 'last':
                    s[i] = prev
                elif method == 'growth':
                    s[i] = prev * np.exp(step)
                else:
                    s[i] = prev + step
                n += 1
            self.data[col] = s
            filled[col] = n
        return filled
