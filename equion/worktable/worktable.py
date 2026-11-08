#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Work Table 모듈 — Workspace + WorkTable 세션 파사드.

데이터(Data)·방정식(Equation)·모델(Model)을 감싸는 오케스트레이션 계층.
주기/표본을 보유하고 번들 저장·복원을 담당한다.

(구 worktable.py 본문. 로직 무변경. 주기 유틸은 .freq, JSON 헬퍼는 ._serial로 분리.)
"""

import os
import pickle
import shutil
import warnings
from datetime import datetime

import pandas as pd

from ..data.dataset import Data
from ..estimation.equation import Equation
from ..system.model import Model
from ..version import ENGINE_VERSION

from ..data.periods import FREQ_LABEL as _FREQ_LABEL
from ..data.periods import infer_freq_code, locate, normalize_freq, parse_period, to_period
from ..data.periods import resample as _resample
from .freq import parse_equation_file
from ..data.store import read_frame, write_frame
from ._serial import (
    _jsonable,
    _nested_int_to_str,
    _nested_str_to_int,
    _write_json,
    _read_json,
    _dir_size,
)
from .._compat import load_pickle, require_pickle_permission
from ..log import engine as _log


class Workspace:
    """열려 있는 WorkTable들을 이름으로 보관하고 활성 테이블을 추적한다.

    전부 클래스 메서드(모듈 전역 단일 작업공간). 월별/연별 등 여러 주기의
    워크테이블을 동시에 열어두고 `Workspace.use(name)`으로 전환한다.
    """

    _tables = {}
    _active = None

    @classmethod
    def register(cls, wt: "WorkTable"):
        cls._tables[wt.name] = wt
        cls._active = wt.name
        return wt

    @classmethod
    def use(cls, name: str) -> "WorkTable":
        if name not in cls._tables:
            raise KeyError(f"워크테이블 '{name}' 없음. 열린 목록: {list(cls._tables)}")
        cls._active = name
        return cls._tables[name]

    @classmethod
    def active(cls):
        return cls._tables.get(cls._active)

    @classmethod
    def get(cls, name: str):
        return cls._tables.get(name)

    @classmethod
    def names(cls):
        return list(cls._tables)

    @classmethod
    def close(cls, name: str):
        cls._tables.pop(name, None)
        if cls._active == name:
            cls._active = next(iter(cls._tables), None)

    @classmethod
    def show(cls):
        _log.info("=" * 60)
        _log.info("Workspace — 열린 Work Table")
        _log.info("=" * 60)
        if not cls._tables:
            _log.info("  (없음)")
        for name, wt in cls._tables.items():
            mark = "*" if name == cls._active else " "
            _log.info(f" {mark} {name:20s} freq={wt.freq}  {wt._status_str()}")
        _log.info("=" * 60)


# ============================================================================
# WorkTable — 세션/작업공간의 중심 객체
# ============================================================================

BUNDLE_FORMAT_VERSION = 3  # v3(엔진 v3): 추정법·도구변수·공분산·HS 상태 추가 (v2 읽기 호환)


class WorkTable:
    """EViews workfile 대응. 주기·표본을 보유하고 데이터/방정식/모델을 소유한다."""

    def __init__(self, name: str = "untitled", freq: str = "Q",
                 start=None, end=None, register: bool = True):
        self.name = name
        self._freq = normalize_freq(freq)

        # 자식(편입 대상)
        self.data: Data = None
        self.equations: list = []
        self.model: Model = None

        # 방정식 원천
        self.eq_strings: list = []
        self.identity_strings: list = []
        self.equations_source: str = None

        # 표본(sample) — Period 튜플 (start, end) 또는 None(전체)
        self._sample = None
        if start is not None or end is not None:
            self._sample = (parse_period(start, self._freq),
                            parse_period(end, self._freq))

        _log.info(f"[WT] 새 Work Table 생성: '{name}' (freq={self._freq} "
              f"= {_FREQ_LABEL[self._freq]})")

        if register:
            Workspace.register(self)

    # ----- 주기/표본 (설정의 단일 출처) ---------------------------------
    @property
    def freq(self) -> str:
        """주기 코드(Q/M/A). 생성 시 고정 — 변경하려면 resample로 새 WT를 만든다."""
        return self._freq

    @freq.setter
    def freq(self, _):
        raise AttributeError(
            "freq는 생성 시 고정됩니다. 다른 주기는 wt.resample(freq=...)로 "
            "새 Work Table을 만드세요.")

    def sample(self, start=None, end=None):
        """표본기간 설정/조회 (EViews smpl).

        인자 없이 호출하면 현재 표본 (start_period, end_period)을 반환한다.
        설정 시 이미 계산된 모델 결과(solve/HS)를 무효화해 전파한다.
        """
        if start is None and end is None:
            return self._sample
        new = (parse_period(start, self._freq), parse_period(end, self._freq))
        if new[0] is not None and new[1] is not None and new[0] > new[1]:
            raise ValueError(f"표본 시작이 끝보다 뒤입니다: {start} > {end}")
        self._sample = new
        _log.info(f"[WT] 표본 설정: {self._fmt_period(new[0])} ~ {self._fmt_period(new[1])}")
        self._propagate_change("sample")
        return self

    def clear_sample(self):
        """표본을 전체 구간으로 되돌린다."""
        self._sample = None
        self._propagate_change("sample")
        return self

    def _propagate_change(self, what: str):
        """설정 변경을 자식(모델)에 전파 — 낡은 결과를 무효화한다."""
        if self.model is None:
            return
        had = bool(getattr(self.model, "solutions", None) or
                   getattr(self.model, "hs_solutions", None))
        self.model.solutions = {}
        self.model.hs_solutions = {}
        self.model.hs_statistics = {}
        self.model.hs_status = {}
        self.model.solve_status = {}
        self.model.simulations = {}
        self.model.scenario_results = {}
        self.model.is_prepared = False
        self.model.current_time_index = None
        self.model.formulas_for_solver = []
        if had:
            _log.info(f"[WT] '{what}' 변경 → 기존 solve/HS 결과를 무효화했습니다 "
                  f"(재실행 필요).")

    # ----- 데이터/방정식/모델 편입 -------------------------------------
    def load_data(self, file_path: str, index_col: str = None,
                  check_freq: bool = True) -> Data:
        """데이터를 워크테이블로 편입한다. 인덱스 주기를 freq와 대조한다."""
        self.data = Data(file_path, index_col)
        self.data.wt = self  # 역참조
        if check_freq:
            self._check_data_freq()
        return self.data

    def set_data(self, data: Data, check_freq: bool = True) -> Data:
        """이미 만든 Data 객체를 편입한다."""
        self.data = data
        self.data.wt = self
        if check_freq:
            self._check_data_freq()
        return self.data

    def _check_data_freq(self):
        if self.data is None or self.data.data is None:
            return
        idx = self.data.data.index
        code = infer_freq_code(idx)
        if code is None and infer_freq_code(idx, allow_gaps=True) == self._freq:
            from ..data.periods import regularize        # 빠진 기간은 빈 행으로 — 행 위치가 기간과 맞게(시차 정합)
            n0 = len(idx)
            self.data.data = regularize(self.data.data, self._freq)
            _log.info(f"[WT] 빠진 기간 {len(self.data.data) - n0}개를 빈 행으로 채웠습니다")
            idx = self.data.data.index
            code = self._freq
        if code is None:
            warnings.warn(
                f"[WT] 데이터 주기를 추론하지 못했습니다 (freq={self._freq} 가정). "
                "인덱스가 균일한 시계열인지 확인하세요.", stacklevel=2)
            return
        if code != self._freq:
            raise ValueError(
                f"[WT] 데이터 주기 불일치: 워크테이블 freq={self._freq}"
                f"({_FREQ_LABEL[self._freq]}) ≠ 데이터 추론 주기={code}"
                f"({_FREQ_LABEL[code]}). "
                f"WorkTable(freq='{code}')로 만들거나 wt.resample('{self._freq}')를 "
                "사용하세요.")
        _log.info(f"[WT] 데이터 주기 확인: {code} ({len(idx)}기)")

    def load_equations(self, file_path: str):
        """방정식 파일을 파싱해 워크테이블에 적재한다(추정은 estimate에서)."""
        self.eq_strings, self.identity_strings = parse_equation_file(file_path)
        self.equations_source = file_path
        _log.info(f"[WT] 방정식 적재: 추정식 {len(self.eq_strings)} · "
              f"항등식 {len(self.identity_strings)}")
        return self

    def estimate(self, verbose: bool = False):
        """적재된 방정식을 추정하고 모델을 자동 구성한다(데이터·식이 모델로 편입)."""
        if self.data is None:
            raise RuntimeError("먼저 load_data로 데이터를 편입하세요.")
        if not self.eq_strings and not self.identity_strings:
            raise RuntimeError("먼저 load_equations로 방정식을 적재하세요.")

        self.equations = []
        failed = []
        for i, s in enumerate(self.eq_strings):
            try:
                eq = Equation(s, self.data)
                eq.process()
                eq.wt = self
                self.equations.append(eq)
            except Exception as e:
                failed.append((i + 1, s, str(e)))
                if verbose:
                    _log.info(f"  [추정실패 {i+1}] {s[:60]} — {e}")

        self.model = Model(self.data, self.equations)
        self.model.wt = self
        for ident in self.identity_strings:
            try:
                self.model.add_identity(ident)
            except Exception as e:
                failed.append((-1, ident, str(e)))

        _log.info(f"[WT] 추정 완료: 성공 {len(self.equations)}/"
              f"{len(self.eq_strings)} · 항등식 {len(self.model.identities)} · "
              f"내생 {len(self.model.endogenous_vars)}")
        if failed:
            _log.info(f"[WT] 실패 {len(failed)}건 (wt.last_failed 참조)")
        self.last_failed = failed
        return self.model

    # ----- 표본 → 정수 인덱스 ------------------------------------------
    def index_of(self, period) -> int:
        """'2000Q1' 등 시점 표기를 데이터 위치 인덱스로 변환한다."""
        self._require_data()
        return locate(self.data.data.index, period, self._freq)

    def _sample_bounds(self, start=None, end=None):
        """(start, end) 인자 → 정수 인덱스. 미지정 시 sample, 그것도 없으면 전체."""
        self._require_data()
        n = len(self.data.data)
        # 시작
        if start is not None:
            s = self.index_of(start)
        elif self._sample and self._sample[0] is not None:
            s = self._period_to_index(self._sample[0], side="start")
        else:
            s = 0
        # 끝
        if end is not None:
            e = self.index_of(end)
        elif self._sample and self._sample[1] is not None:
            e = self._period_to_index(self._sample[1], side="end")
        else:
            e = n - 1
        if s > e:
            raise ValueError(f"표본 구간이 비었습니다: {s} > {e}")
        return s, e

    def _period_to_index(self, period: pd.Period, side: str) -> int:
        periods = [to_period(ts, self._freq) for ts in self.data.data.index]
        if period in periods:
            return periods.index(period)
        # 경계 밖이면 가장 가까운 안쪽으로 클램프
        if side == "start":
            for i, p in enumerate(periods):
                if p >= period:
                    return i
            return len(periods) - 1
        else:
            for i in range(len(periods) - 1, -1, -1):
                if periods[i] <= period:
                    return i
            return 0

    # ----- solve / HS 위임 (표본 반영) ---------------------------------
    def solve(self, period, solve_id: str = "solve", **kw):
        """단일 시점 해. period는 '2010Q1' 등 시점 표기."""
        self._require_model()
        return self.model.solve(self.index_of(period), solve_id=solve_id, **kw)

    def hs(self, start=None, end=None, hs_id: str = None, **kw):
        """표본(또는 인자) 구간 Historical Simulation.

        start='auto'면 표본 시작 이후 모든 식의 입력(시차·외생)이 갖춰지는 첫 시점부터 푼다.
        """
        self._require_model()
        auto = isinstance(start, str) and start.lower() == "auto"
        s, e = self._sample_bounds(None if auto else start, end)
        if auto:
            first = self.model.first_complete_index(s, e)
            if first is None:
                raise ValueError("표본 안에 모든 입력이 갖춰지는 시점이 없습니다(wt.input_gaps() 확인)")
            if first != s:
                _log.info(f"[WT] start='auto' → {to_period(self.data.data.index[first], self._freq)}"
                      f" (그 전은 입력 결측)")
            s = first
        if hs_id is None:
            ps = to_period(self.data.data.index[s], self._freq)
            pe = to_period(self.data.data.index[e], self._freq)
            hs_id = f"hs_{ps}_{pe}"
        result = self.model.hs(s, e, hs_id=hs_id, **kw)
        return result

    # ----- 구조·진단 ---------------------------------------------------
    def blocks(self):
        """블록 구조(풀이 순서) 출력 후 목록 반환."""
        self._require_model()
        self.model.show_blocks()
        return self.model.block_structure()

    def input_gaps(self, start=None, end=None):
        """기간·식별 결측 입력 진단표(DataFrame)."""
        self._require_model()
        s, e = self._sample_bounds(start, end)
        return self.model.input_gaps(s, e)

    # ----- 일반 모의 / 전망 / 시나리오 --------------------------------
    def simulate(self, start=None, end=None, **kw):
        """구간 모의(mode='dynamic'|'static'|'fit'). 결과(SimulationResult)를 반환."""
        self._require_model()
        s, e = self._sample_bounds(start, end)
        return self.model.simulate(s, e, **kw)

    def scenario(self, name: str = "baseline", alias: str = None):
        from ..scenario import Scenario
        return Scenario(name, alias)

    def extend(self, end, exog_fill: str = None, columns=None, window: int = None):
        """데이터 인덱스를 end까지 늘리고(결정적 지시자 재계산), 필요하면 외생 경로를 채운다.

        exog_fill: None | 'last' | 'growth' | 'trend' — columns(기본: 모델 외생변수 중
        결정적 지시자 제외) 의 마지막 관측 이후를 규칙으로 채운다(가정 경로 초안).
        """
        self._require_data()
        n = self.data.extend(end)
        if exog_fill:
            cols = columns
            if cols is None:
                self._require_model()
                ind = set(self.data.indicators)
                cols = [v for v in self.model.exogenous_vars
                        if v in self.data.data.columns and v not in ind]
            filled = self.data.fill_series(cols, method=exog_fill, window=window)
            nz = {k: v for k, v in filled.items() if v}
            _log.info(f"[WT] 외생 경로 채움({exog_fill}): {len(nz)}개 변수")
        return n

    def forecast(self, start, end, scenario=None, exog_fill: str = None,
                 check: bool = True, **kw):
        """전망: (필요 시 기간 확장 → 외생 채움) → 동적 시나리오 풀이. ScenarioResult 반환.

        check=True면 지평에서 비어 있는 외생 경로를 먼저 진단해 알려준다.
        """
        from ..scenario import Scenario, missing_exogenous
        self._require_model()
        last = to_period(self.data.data.index[-1], self._freq)
        if parse_period(end, self._freq) > last or exog_fill:
            self.extend(end, exog_fill=exog_fill)
        sc = scenario or Scenario("forecast")
        if check:
            miss = missing_exogenous(self.model, start, end, sc)
            if miss:
                lines = [f"{k}: {v[0]}~{v[-1]} ({len(v)}기)" for k, v in list(miss.items())[:12]]
                raise ValueError(
                    "전망 지평에 외생변수 경로가 없습니다 — scenario.override(...)로 지정하거나 "
                    "exog_fill='last'|'growth'|'trend'를 쓰세요:\n  " + "\n  ".join(lines))
        return sc.run(self.model, start, end, **kw)

    def stochastic(self, start=None, end=None, **kw):
        self._require_model()
        s, e = self._sample_bounds(start, end)
        return self.model.stochastic(s, e, **kw)

    def control(self, target, instrument, path, start=None, end=None, **kw):
        self._require_model()
        s, e = self._sample_bounds(start, end)
        return self.model.control(target, instrument, path, s, e, **kw)

    def multipliers(self, shock_var, shock, start=None, end=None, **kw):
        self._require_model()
        s, e = self._sample_bounds(start, end)
        return self.model.multipliers(shock_var, shock, s, e, **kw)

    # ----- 파생: 주기 변환 → 새 WorkTable ------------------------------
    def resample(self, freq: str, name: str = None, how="mean",
                 register: bool = True) -> "WorkTable":
        """데이터를 다른 주기로 변환한 **새 WorkTable**을 만든다.

        방정식·모델은 주기마다 다르므로 옮기지 않는다(데이터만 이관).
        how: 'mean'/'sum'/'last' 또는 {열: 규칙} dict.
        """
        self._require_data()
        target = normalize_freq(freq)
        res = _resample(self.data.data, target, how)
        new_name = name or f"{self.name}_{target}"
        wt = WorkTable(name=new_name, freq=target, register=register)
        d = Data()
        d.data = res
        d.file_path = self.data.file_path
        d.metadata = {
            "loaded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "n_rows": len(res), "n_cols": len(res.columns),
            "columns": list(res.columns),
            "index_name": res.index.name or "N/A",
            "resampled_from": f"{self.name}({self._freq})", "rule": rule,
        }
        wt.set_data(d, check_freq=False)
        _log.info(f"[WT] resample {self._freq}→{target}: '{self.name}'→'{new_name}' "
              f"({len(df)}→{len(res)}기, how={how})")
        return wt

    # ============================================================
    # 직렬화 — 방향 B 디렉토리 번들
    # ============================================================
    def save(self, path: str, fmt: str = "bundle", overwrite: bool = True) -> str:
        """워크테이블 전체를 저장한다.

        fmt='bundle'(기본): `path.wt/` 디렉토리 번들(매니페스트+npz 자료+계수 JSON).
        fmt='pickle': 객체 그래프 단일 파일(레거시 호환).
        """
        if fmt == "pickle":
            warnings.warn("fmt='pickle'은 1.0에서 없어집니다 — 번들(fmt='bundle') 또는 워크파일(.eqw)을 쓰세요",
                          DeprecationWarning, stacklevel=2)
            return self._save_pickle(path)
        if fmt != "bundle":
            raise ValueError("fmt는 'bundle' 또는 'pickle'")
        return self._save_bundle(path, overwrite=overwrite)

    def _bundle_dir(self, path: str) -> str:
        return path if path.endswith(".wt") else path + ".wt"

    def _save_bundle(self, path: str, overwrite: bool = True) -> str:
        self._require_model()
        out = self._bundle_dir(path)
        parent = os.path.dirname(out)
        if parent:
            os.makedirs(parent, exist_ok=True)
        # 기존 산출물 정리(WT는 git 제외 생성물)
        if os.path.isfile(out):
            os.remove(out)
        elif os.path.isdir(out):
            if not overwrite:
                raise FileExistsError(f"이미 존재: {out} (overwrite=True 필요)")
            shutil.rmtree(out)
        os.makedirs(out)
        os.makedirs(os.path.join(out, "results"), exist_ok=True)

        # 1) data.npz (numpy 압축 — pickle 없음)
        write_frame(out, "data", self.data.data)

        # 2) equations.txt (자체 포함 DSL 원문)
        with open(os.path.join(out, "equations.txt"), "w", encoding="utf-8") as f:
            f.write("# === 추정식 ===\n")
            for s in self.eq_strings:
                f.write(s + "\n")
            f.write("\n# === 항등식 ===\n")
            for s in self.identity_strings:
                f.write(s + "\n")

        # 3) coefficients.json (계수만 → 재추정 없이 복원)
        coefs = [_jsonable(eq.to_saved()) for eq in self.equations]
        _write_json(os.path.join(out, "coefficients.json"), coefs)

        # 4) residuals.npz (add-factor용)
        res_cols = {}
        for i, eq in enumerate(self.equations):
            if eq.residuals is not None:
                res_cols[str(i)] = eq.residuals
        if res_cols:
            write_frame(out, "residuals", pd.DataFrame(res_cols))

        # 5) results/ — solve/HS 결과 + 통계
        _write_json(os.path.join(out, "results", "solutions.json"),
                    _nested_int_to_str(self.model.solutions))
        _write_json(os.path.join(out, "results", "hs_solutions.json"),
                    _nested_int_to_str(self.model.hs_solutions))
        _write_json(os.path.join(out, "results", "hs_statistics.json"),
                    _jsonable(getattr(self.model, "hs_statistics", {})))
        _write_json(os.path.join(out, "results", "hs_status.json"),
                    _jsonable(_nested_int_to_str(getattr(self.model, "hs_status", {}))))

        # 6) worktable.json (매니페스트)
        manifest = {
            "format": "worktable-bundle",
            "format_version": BUNDLE_FORMAT_VERSION,
            "engine_version": ENGINE_VERSION,
            "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "name": self.name,
            "freq": self._freq,
            "sample": {
                "start": self._fmt_period(self._sample[0]) if self._sample else None,
                "end": self._fmt_period(self._sample[1]) if self._sample else None,
            },
            "equations_source": self.equations_source,
            "summary": {
                "n_estimated": len(self.equations),
                "n_identities": len(self.model.identities),
                "n_endogenous": len(self.model.endogenous_vars),
                "n_exogenous": len(self.model.exogenous_vars),
                "solve_ids": sorted(self.model.solutions.keys()),
                "hs_ids": sorted(self.model.hs_solutions.keys()),
            },
            "data": {
                "file": "data.npz",
                "n_rows": len(self.data.data),
                "n_cols": len(self.data.data.columns),
                "index_name": self.data.data.index.name or "N/A",
            },
        }
        _write_json(os.path.join(out, "worktable.json"), manifest)

        size = _dir_size(out) / 1024
        _log.info(f"[WT] 번들 저장: {out} ({size:.1f} KB) — 추정식 "
              f"{len(self.equations)} · 항등식 {len(self.model.identities)} · "
              f"HS {len(self.model.hs_solutions)}건")
        return out

    @staticmethod
    def load(path: str, refit: bool = False, register: bool = True, allow_pickle: bool = False) -> "WorkTable":
        """번들 또는 레거시 pickle을 자동 판별해 복원한다.

        refit=False(기본): 계수만 되살려 재추정 없이 즉시 복원(빠름).
        refit=True: equations.txt+data로 재추정(엔진 변경 시 정밀 재현).
        allow_pickle: 레거시 pickle은 열 때 코드가 실행될 수 있어 True일 때만 연다(번들은 상관없음).
        """
        bundle = path if os.path.isdir(path) else (
            path if (path.endswith(".wt") and os.path.isdir(path)) else None)
        if bundle is None and os.path.isdir(path + ".wt"):
            bundle = path + ".wt"
        if bundle and os.path.isdir(bundle):
            return WorkTable._load_bundle(bundle, refit=refit, register=register)
        return WorkTable._load_pickle(path, register=register, allow_pickle=allow_pickle)

    @staticmethod
    def _load_bundle(out: str, refit: bool = False,
                     register: bool = True) -> "WorkTable":
        man_path = os.path.join(out, "worktable.json")
        if not os.path.exists(man_path):
            raise ValueError(f"번들 매니페스트 없음: {man_path}")
        manifest = _read_json(man_path)

        eng = manifest.get("engine_version")
        if eng != ENGINE_VERSION:
            warnings.warn(f"엔진 버전 불일치(저장 {eng} ≠ 현재 {ENGINE_VERSION}). "
                          "계수는 복원되나 동작이 다를 수 있습니다.", stacklevel=2)

        wt = WorkTable(name=manifest["name"], freq=manifest["freq"],
                       register=register)
        smp = manifest.get("sample") or {}
        if smp.get("start") or smp.get("end"):
            wt._sample = (parse_period(smp.get("start"), wt._freq),
                          parse_period(smp.get("end"), wt._freq))

        # 데이터
        df = read_frame(out, "data")
        if df is None:
            raise ValueError(f"번들 자료(data.npz)가 없습니다: {out}")
        d = Data()
        d.data = df
        d.metadata = {"loaded_at": manifest.get("saved_at"),
                      "n_rows": len(df), "n_cols": len(df.columns),
                      "columns": list(df.columns),
                      "index_name": df.index.name or "N/A"}
        wt.set_data(d, check_freq=False)

        # 방정식 원천
        eq_src = os.path.join(out, "equations.txt")
        if os.path.exists(eq_src):
            wt.eq_strings, wt.identity_strings = parse_equation_file(eq_src)
            wt.equations_source = eq_src

        if refit:
            wt.estimate()
            _log.info(f"[WT] 번들 복원(재추정): {out}")
            return wt

        # 빠른 복원 — 계수에서 Equation 재구성(재추정 없음)
        coefs = _read_json(os.path.join(out, "coefficients.json"))
        res_df = read_frame(out, "residuals")

        equations = []
        for i, c in enumerate(coefs):
            eq = Equation.restore(c, wt.data)
            if res_df is not None and str(i) in res_df.columns:
                r = res_df[str(i)].dropna()
                r.index = pd.to_datetime(r.index)
                eq.residuals = r
            eq.wt = wt
            equations.append(eq)

        wt.equations = equations
        wt.model = Model(wt.data, equations)
        wt.model.wt = wt
        for ident in wt.identity_strings:
            wt.model.add_identity(ident)

        # 결과 복원
        wt.model.solutions = _nested_str_to_int(
            _read_json(os.path.join(out, "results", "solutions.json")))
        wt.model.hs_solutions = _nested_str_to_int(
            _read_json(os.path.join(out, "results", "hs_solutions.json")))
        wt.model.hs_statistics = _read_json(
            os.path.join(out, "results", "hs_statistics.json"))
        st_path = os.path.join(out, "results", "hs_status.json")
        if os.path.exists(st_path):
            wt.model.hs_status = _nested_str_to_int(_read_json(st_path))

        s = manifest.get("summary", {})
        _log.info(f"[WT] 번들 복원: {out} (저장 {manifest.get('saved_at')}, "
              f"엔진 {eng}) — 추정식 {s.get('n_estimated','?')} · "
              f"항등식 {s.get('n_identities','?')} · "
              f"HS {len(s.get('hs_ids', []))}건")
        return wt

    # ----- 레거시 pickle (객체 그래프 통째 직렬화) ----------------------
    def _save_pickle(self, path: str) -> str:
        self._require_model()
        if not os.path.splitext(path)[1]:
            path += ".wtp"
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        payload = {
            "format": "worktable-pickle",
            "format_version": BUNDLE_FORMAT_VERSION,
            "engine_version": ENGINE_VERSION,
            "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "name": self.name, "freq": self._freq,
            "sample": self._sample,
            "model": self.model,
            "eq_strings": self.eq_strings,
            "identity_strings": self.identity_strings,
            "equations_source": self.equations_source,
        }
        with open(path, "wb") as f:
            pickle.dump(payload, f, protocol=pickle.HIGHEST_PROTOCOL)
        _log.info(f"[WT] pickle 저장: {path} "
              f"({os.path.getsize(path)/1024:.1f} KB)")
        return path

    @staticmethod
    def _load_pickle(path: str, register: bool = True, allow_pickle: bool = False) -> "WorkTable":
        if not os.path.exists(path):
            raise FileNotFoundError(f"파일 없음: {path}")
        require_pickle_permission(path, allow_pickle)
        with open(path, "rb") as f:
            payload = load_pickle(f)
        if not isinstance(payload, dict) or "model" not in payload:
            raise ValueError(f"WorkTable pickle 형식이 아닙니다: {path}")
        wt = WorkTable(name=payload.get("name", "restored"),
                       freq=payload.get("freq", "Q"), register=register)
        wt._sample = payload.get("sample")
        wt.model = payload["model"]
        wt.model.wt = wt
        wt.data = wt.model.data
        wt.data.wt = wt
        wt.equations = wt.model.equations
        wt.eq_strings = payload.get("eq_strings", [])
        wt.identity_strings = payload.get("identity_strings", [])
        wt.equations_source = payload.get("equations_source")
        _log.info(f"[WT] pickle 복원: {path}")
        return wt

    # ----- 편의/표시 --------------------------------------------------
    def _require_data(self):
        if self.data is None or self.data.data is None:
            raise RuntimeError("데이터가 없습니다. wt.load_data(...)를 먼저 호출하세요.")

    def _require_model(self):
        if self.model is None:
            raise RuntimeError("모델이 없습니다. wt.estimate()를 먼저 호출하세요.")

    def _fmt_period(self, p):
        return None if p is None else str(p)

    def _status_str(self):
        d = "데이터✓" if self.data is not None and self.data.data is not None else "데이터✗"
        m = f"모델✓({len(self.model.endogenous_vars)}내생)" if self.model else "모델✗"
        smp = ("전체" if not self._sample else
               f"{self._fmt_period(self._sample[0])}~{self._fmt_period(self._sample[1])}")
        return f"{d} {m} 표본={smp}"

    def info(self):
        _log.info("=" * 70)
        _log.info(f"Work Table '{self.name}'  (freq={self._freq} = {_FREQ_LABEL[self._freq]})")
        _log.info("=" * 70)
        _log.info(f"  표본: {('전체' if not self._sample else self._status_str())}")
        if self.data is not None and self.data.data is not None:
            idx = self.data.data.index
            _log.info(f"  데이터: {len(idx)}기 × {len(self.data.data.columns)}열 "
                  f"({to_period(idx[0], self._freq)} ~ {to_period(idx[-1], self._freq)})")
        n_ident = (len(self.model.identities) if self.model is not None
                   else len(self.identity_strings))
        _log.info(f"  추정식: {len(self.equations)} · 항등식: {n_ident}")
        if self.model is not None:
            _log.info(f"  내생: {len(self.model.endogenous_vars)} · 외생: "
                  f"{len(self.model.exogenous_vars)} · "
                  f"HS: {len(self.model.hs_solutions)}건")
        _log.info("=" * 70)

    def __repr__(self):
        return (f"WorkTable('{self.name}', freq={self._freq}, "
                f"{self._status_str()})")


# 활성 워크테이블 단축 접근
def current() -> WorkTable:
    """현재 활성 Work Table을 반환한다(Workspace.active)."""
    return Workspace.active()
