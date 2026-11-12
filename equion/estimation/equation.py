#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""방정식 추정·분석 모듈 — Equation 클래스 + 방정식 유틸 (엔진 v3).

명세 문자열 → parser(검증·정규화) → IR(시계열 연산 전개) → 추정.
추정과 연립 풀이(system)가 **같은 IR**을 쓰므로 둘의 의미가 구조적으로 일치한다.

계수 공분산(cov): 'nonrobust'(기본)·'hc0'~'hc3'·'white'(=hc1)·'hac'(Newey-West, lags) — equion.stats.robust.

지원 추정법(method):
  ols   : 최소제곱(자체 구현, 유사역행렬)  — `Y c X1 X2`
  wls   : 가중 최소제곱                     — weights="1/POP"(식), wtype='ivar'·'var'·'istdev'·'stdev'
  tsls  : 2단계 최소제곱(도구변수)          — `Y c X1 X2 @inst Z1 Z2` (EViews식 `@`도 가능)
  gmm   : 선형 GMM(도구변수)                — gmm_weight='white'|'hac'(lags), iterate=True면 반복 GMM, J 통계량
  liml  : 제한정보 최우(도구변수)           — k-class κ
  nls   : 비선형 최소제곱(계수 c(n) 명시)   — `Y = c(1) + c(2)*X^c(3)`  (`@start` 시작값). `@inst`를 붙이면 비선형 2단계 최소제곱
          (NL-2SLS — 잔차를 도구에 투영한 제곱합을 최소화, Sargan 과대식별 검정, 도구에는 상수항이 늘 든다)
  fixed : 외부 계수 고정(재추정 없음)       — `Y c X1 @coef 0.3 0.8` 또는 set_coefficients()

AR(p) 오차: 선형 추정식에 `ar(1) ar(2)`(또는 `ar(1 to 4)`) — yₜ = xₜb + uₜ, uₜ = Σρₚuₜ₋ₚ + εₜ를 조건부 최소제곱
  (NLS, 해석적 자코비안)으로. 계수 이름 AR(1)…, 풀이 IR은 xₜb + Σρₚ(yₜ₋ₚ − xₜ₋ₚb)라 동적 풀이에서 uₜ가 ρ로 이어진다.

다항 분포시차(PDL): 선형 추정식의 항 `pdl(X, k, d[, 제약])` — X(0)~X(−k)의 계수를 d차 다항식으로 묶는다.
  제약 0 없음 · 1 가까운 끝(β₋₁ = 0) · 2 먼 끝(β_{k+1} = 0) · 3 양 끝. 계수 이름은 PDL01, PDL02 …,
  시차별 계수는 lag_distribution(). 풀이에서는 시차들의 선형결합이라 다른 항과 똑같이 IR로 풀린다.
"""

import math
import re
from typing import Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
import pandas as pd

from ..formula import ir
from ..stats import regression as _reg
from ..stats.robust import normalize_cov_type
from ..formula.ast_formula import user_to_pandas, canonicalize_columns
from ..formula.parser import (
    MAX_TERMS,
    DSLError, normalize, classify_line, split_equation, extract_directives,
    split_terms, expand_term_lag_range, convert_at_functions, convert_eviews_lag_ranges,
    _raw_split,
)
from ..data.dataset import Data
from ..log import engine as _log

METHODS = ("ols", "wls", "tsls", "gmm", "liml", "nls", "fixed")
IV_METHODS = ("tsls", "gmm", "liml")
WEIGHT_TYPES = ("ivar", "var", "istdev", "stdev")   # 가중 계열이 뜻하는 것: 1/분산 · 분산 · 1/표준편차 · 표준편차
_PDL_RE = re.compile(r"^\s*pdl\s*\((.*)\)\s*$", re.IGNORECASE | re.DOTALL)
_AR_RE = re.compile(r"^\s*ar\s*\(\s*(\d+)(?:\s+to\s+(\d+))?\s*\)\s*$", re.IGNORECASE)
_LEGACY_FUNCS = frozenset({"log", "exp", "abs", "sqrt", "dlog", "d"})


class Equation:
    """(고급) 방정식 한 개의 엔진 객체 — 추정(OLS·TSLS·NLS·WLS·GMM·LIML·고정)과 연립 풀이용 IR을 가진다.

    보통은 워크파일의 방정식 객체(`wf.equation("이름").ls(…)`)를 쓰고, 엔진 객체는 그 `.eq`로 얻는다.

    예
        >>> wf = eqn.datasets.load("toy_q")
        >>> e = wf.equation("eq_i").ls("I c Y(-1) R").eq
        >>> type(e).__name__, e.target, e.method
        ('Equation', 'I', 'ols')
    """

    def __init__(self, equation_str: str, data: Data, auto_fix: bool = True,
                 method: str = None, instruments: Sequence[str] = None,
                 coefficients: Sequence[float] = None, cov: str = None, lags: int = None,
                 weights: str = None, wtype: str = "ivar", gmm_weight: str = None, iterate: bool = False):
        self.original_input = equation_str
        if "#" in equation_str:          # 방정식 파일·append·genr처럼 '#' 뒤는 주석(식 문법에 '#'는 없다)
            equation_str = equation_str.split("#", 1)[0]
        self.cov_type = normalize_cov_type(cov)
        self.cov_lags = None if lags is None else int(lags)
        wtype = (wtype or "ivar").lower()
        if wtype not in WEIGHT_TYPES:
            raise ValueError(f"알 수 없는 가중치 종류: {wtype!r} (가능: {', '.join(WEIGHT_TYPES)})")
        self.wtype = wtype
        self.gmm_weight = gmm_weight
        self.gmm_iterate = bool(iterate)
        self.data = data
        self.auto_fix = auto_fix
        self.input_fixes = []

        s = normalize(equation_str) if auto_fix else equation_str.strip()
        kind = classify_line(s)
        if kind == "identity":
            raise DSLError(
                "등호(=)가 있고 계수 c(n)이 없는 식은 항등식입니다 — 추정식이 아니라 "
                f"항등식 목록(Model.add_identity)에 넣으세요: {equation_str}")
        self.kind = kind  # 'estimated' | 'nls'

        # (1) 꼬리 지시자 분리: @smpl / @inst(@) / @coef / @start
        body, directives = extract_directives(s)
        body, ar_lags = _extract_ar(body)      # 시차 범위 변환(ar(1 to 3) → 리드)보다 먼저 떼어 낸다
        if ar_lags and kind == "nls":
            raise DSLError("ar(...) 오차항은 선형 추정식에서만 쓸 수 있습니다(c(n) 계수식에는 안 됨)")
        self.smpl_start = self.smpl_end = None
        if "smpl" in directives:
            self.smpl_start, self.smpl_end = [x.upper() for x in directives["smpl"]]
        self.fixed_coefs = (list(coefficients) if coefficients is not None
                            else directives.get("coef"))
        self.start_values = directives.get("start")
        inst_terms = list(instruments) if instruments is not None else directives.get("inst")

        # (2) @seas / @trend / @d(...) / @step(...) → 데이터 컬럼
        body = self._expand_indicators(body)
        inst_str = self._expand_indicators(" ".join(inst_terms)) if inst_terms else ""

        # (3) EViews 문법: X(-1 to -4) 시차범위. @pc/@movav 등 함수는 표기를 유지하고
        #     (계수 이름·표시용) IR 생성 직전에 내부 이름으로 바꾼다 — 여기서는 검증만.
        body = convert_eviews_lag_ranges(body)
        convert_at_functions(body)
        if inst_str:
            inst_str = convert_eviews_lag_ranges(inst_str)
            convert_at_functions(inst_str)

        # (4) 변수명 대소문자 교정 (데이터 컬럼 기준)
        if self.data is not None and self.data.data is not None:
            body = canonicalize_columns(body, self.data.data.columns)
            if inst_str:
                inst_str = canonicalize_columns(inst_str, self.data.data.columns)

        # (5) 항 분리(괄호 깊이 0) + 시차범위 전개
        if kind == "estimated":
            terms: List[str] = []
            for t in split_terms(body):
                terms.extend(expand_term_lag_range(t))
                if len(terms) > MAX_TERMS:
                    raise DSLError(f"추정식의 항이 너무 많습니다(> {MAX_TERMS}개): {equation_str[:120]}…")
            body = " ".join(terms)
        self.instruments: List[str] = []
        if inst_str:
            for t in split_terms(inst_str):
                self.instruments.extend(expand_term_lag_range(t))

        if ar_lags:                            # 정규형 ar(p)로 다시 붙인다(저장·복원은 이 글자를 다시 파싱)
            body = body + " " + " ".join(f"ar({p})" for p in ar_lags)
        self.equation_str = body
        self.user_formula = self.equation_str

        # 가중치 식(WLS): 지시자·시차 범위·대소문자를 본문과 같게 다듬는다
        self.weights_expr = None
        if weights is not None and str(weights).strip():
            w = convert_eviews_lag_ranges(self._expand_indicators(normalize(str(weights))))
            convert_at_functions(w)
            if self.data is not None and self.data.data is not None:
                w = canonicalize_columns(w, self.data.data.columns)
            self.weights_expr = w

        if method is not None:
            method = method.lower()
            if method not in METHODS:
                raise ValueError(f"알 수 없는 추정법: {method} (지원: {', '.join(METHODS)})")
        elif self.fixed_coefs is not None:
            method = "fixed"
        elif kind == "nls":
            method = "tsls" if self.instruments else "nls"
        elif self.instruments:
            method = "tsls"
        elif self.weights_expr:
            method = "wls"
        else:
            method = "ols"
        if method in IV_METHODS and not self.instruments:
            raise DSLError(f"{method}에는 도구변수(@inst ...)가 필요합니다")
        if method == "wls" and not self.weights_expr:
            raise DSLError("wls에는 가중치 식(weights=...)이 필요합니다")
        if kind == "nls" and method not in ("nls", "tsls", "fixed"):
            raise DSLError("c(n) 계수식은 nls · tsls(도구변수 @inst — 비선형 2단계 최소제곱) · fixed로만 추정할 수 있습니다")
        if ar_lags and method not in ("ols", "fixed"):
            raise DSLError(f"ar(...) 오차항은 ls(최소제곱)·fixed에서만 쓸 수 있습니다(지금: {method})")
        if method == "gmm" and self.cov_type != "nonrobust":
            raise ValueError("GMM의 계수 공분산은 가중행렬(gmm_weight='white'|'hac')로 정합니다 — cov는 쓰지 않습니다")
        self.method = method

        # 파싱 결과
        self.dependent_var = None
        self.independent_vars = []
        self.has_constant = False
        self.term_order: List[str] = []
        self.coef_names: List[str] = []
        self.lhs_ir = None
        self.term_irs = []
        self.rhs_template = None
        self.instrument_irs = []
        self.weights_ir = None
        self.pdl_terms: List[dict] = []
        self.ar_lags: List[int] = list(ar_lags)
        self._coef_numbers: List[int] = []
        self.target_override: Optional[str] = None

        # 생성된 공식
        self.pandas_formula = None

        # 회귀분석 결과
        self._results = None
        self.regression_results = {}
        self.statistics = {}
        self.residuals = None   # 추정 잔차(날짜 인덱스) - add-factor·확률 시뮬용
        self.cov_params = None  # 계수 공분산 (k×k ndarray)

        # 내부 데이터
        self._y = None
        self._X = None
        self._Z = None
        self._W = None

        # 상태
        self.is_processed = False
        self.is_fitted = False

    _DEFAULTS = {
        "kind": "estimated", "method": "ols", "instruments": [], "fixed_coefs": None,
        "start_values": None, "term_order": [], "coef_names": [], "lhs_ir": None,
        "term_irs": [], "rhs_template": None, "instrument_irs": [], "_coef_numbers": [],
        "target_override": None, "cov_params": None, "_Z": None,
        "cov_type": "nonrobust", "cov_lags": None,
        "weights_expr": None, "wtype": "ivar", "gmm_weight": None, "gmm_iterate": False,
        "weights_ir": None, "pdl_terms": [], "_W": None, "ar_lags": [], "_ar_note": None,
    }

    def __setstate__(self, state):
        """(레거시 pickle 호환) 새 속성 기본값을 채운다 — IR은 필요할 때 다시 파싱."""
        self.__dict__.update(state)
        for k, v in self._DEFAULTS.items():
            if k not in self.__dict__:
                setattr(self, k, list(v) if isinstance(v, list) else v)
        if type(self.__dict__.get("_results")).__name__ == "_Unavailable":
            self._results = None  # 이름 변경 전 외부 패키지 결과 객체 — 계수·통계는 따로 저장돼 있다

    # ------------------------------------------------------------------
    # 파이프라인
    # ------------------------------------------------------------------
    def process(self):
        """방정식 처리 (파싱 -> 검증 -> 회귀분석 -> pandas_formula 생성)"""
        self._parse()
        self._validate_variables()
        self._prepare_data()
        self.fit()
        self._generate_pandas_formula()
        self.is_processed = True
        _log.info(f"[OK] {self.dependent_var} 처리 완료 "
              f"({self.method.upper()}, R-sq={self.statistics.get('r_squared', 0):.4f})")

    def _freq(self) -> str:
        if self.data is None:
            return "Q"
        return getattr(self.data, "freq", "Q") or "Q"

    def _yoy_kw(self) -> dict:
        """WorkTable 주기에 맞춘 user_to_pandas 키워드.

        .yoy 시차(연간1·분기4·월12)와 연간 .qoq 비활성을 결정한다.
        """
        freq = self._freq()
        return {"yoy_periods": {"Q": 4, "A": 1, "M": 12}.get(freq, 4),
                "disable_qoq": freq == "A"}

    def _ctx(self, allow_coef=False) -> ir.BuildContext:
        kw = self._yoy_kw()
        return ir.BuildContext(yoy_periods=kw["yoy_periods"],
                               disable_qoq=kw["disable_qoq"], allow_coef=allow_coef)

    def _expand_indicators(self, s: str) -> str:
        """@seas(n) / @seas / @trend / @d(...) / @step(...) 토큰을 데이터 컬럼명으로 치환한다."""
        return expand_indicators(self.data, s)

    def _parse(self):
        """방정식 문자열 파싱 → IR."""
        if self.kind == "nls":
            if re.search(r"\bpdl\s*\(", self.equation_str, re.IGNORECASE):
                raise DSLError("pdl(...)은 선형 추정식에서만 쓸 수 있습니다(c(n) 계수식 안에서는 안 됨)")
            lhs, rhs = split_equation(self.equation_str)
            self.dependent_var = lhs
            self.independent_vars = []
            self.has_constant = False
            self.lhs_ir = _build(lhs, self._ctx())
            self.rhs_template = _build(rhs, self._ctx(allow_coef=True))
            self._coef_numbers = sorted(ir.coef_indices(self.rhs_template))
            if not self._coef_numbers:
                raise DSLError(f"NLS 식에 계수 c(n)이 없습니다: {self.equation_str}")
            self.coef_names = [f"c({k})" for k in self._coef_numbers]
            self.term_order = list(self.coef_names)
        else:
            parts = split_terms(self.equation_str)
            if len(parts) < 2:
                raise ValueError("방정식 형식 오류: 최소 2개 항 필요")
            self.dependent_var = parts[0]
            ctx = self._ctx()
            lin, ar = [], []
            for t in parts[1:]:
                m = _AR_RE.match(t)
                (ar.append(int(m.group(1))) if m else lin.append(t))
            self.ar_lags = sorted(ar)
            self.term_order, pdl_nodes = self._expand_pdl(lin, ctx)
            self.has_constant = "c" in self.term_order
            if self.term_order.count("c") > 1:
                raise DSLError("상수항 c가 두 번 들어 있습니다")
            self.independent_vars = [t for t in self.term_order if t != "c"]
            dup = sorted({t for t in self.independent_vars if self.independent_vars.count(t) > 1})
            if dup:
                raise DSLError(f"같은 설명변수가 중복되었습니다: {dup}")
            self.lhs_ir = _build(self.dependent_var, ctx)
            self.term_irs = [pdl_nodes[t] if t in pdl_nodes else _build(t, ctx) for t in self.independent_vars]
            ar_names = [f"AR({p})" for p in self.ar_lags]
            self.coef_names = (["const"] if self.has_constant else []) + self.independent_vars + ar_names
            self.term_order = self.term_order + ar_names     # c(n) 번호: 쓴 항 다음에 AR 계수
            if len(self.coef_names) == len(ar_names):
                raise ValueError("방정식 형식 오류: 설명변수가 없습니다")
        if not ir.variables(self.lhs_ir):
            raise DSLError(f"좌변에 변수가 없습니다: {self.dependent_var}")
        ctx = self._ctx()
        self.instrument_irs = [_build(z, ctx) for z in self.instruments if z != "c"]
        self.weights_ir = _build(self.weights_expr, ctx) if self.weights_expr else None
        _log.info(f"[PARSE] {self.dependent_var} = f({len(self.coef_names)}개 계수, {self.method})")

    def _expand_pdl(self, terms: List[str], ctx):
        """`pdl(X, k, d[, 제약])` 항을 PDL01… 계수 항으로 펼친다 → (항 목록, 이름 → IR)."""
        out, nodes, self.pdl_terms = [], {}, []
        for t in terms:
            m = _PDL_RE.match(t)
            if not m:
                out.append(t)
                continue
            args = _split_args(m.group(1))
            if len(args) not in (3, 4):
                raise DSLError(f"pdl(변수, 시차 수, 차수[, 제약]) 꼴이어야 합니다: {t}")
            try:
                k, d = int(args[1]), int(args[2])
                cons = int(args[3]) if len(args) == 4 else 0
            except ValueError:
                raise DSLError(f"pdl의 시차 수·차수·제약은 정수여야 합니다: {t}") from None
            from ..formula.parser import MAX_LAG
            if not 1 <= k <= MAX_LAG or not 0 <= d <= k or cons not in (0, 1, 2, 3):
                raise DSLError(f"pdl 인자 범위: 1 ≤ 시차 수 ≤ {MAX_LAG}, 0 ≤ 차수 ≤ 시차 수, 제약 0~3 — {t}")
            basis = pdl_basis(k, d, cons)
            base = _build(args[0], ctx)
            names = []
            for j in range(basis.shape[1]):
                node = None
                for i in range(k + 1):
                    if basis[i, j] != 0.0:
                        term = ir.mul(ir.Const(float(basis[i, j])), ir.shift(base, -i))
                        node = term if node is None else ir.add(node, term)
                name = f"PDL{sum(len(p['names']) for p in self.pdl_terms) + j + 1:02d}"
                nodes[name] = node if node is not None else ir.ZERO
                names.append(name)
            self.pdl_terms.append({"term": t, "variable": args[0], "lags": k, "degree": d, "constraint": cons,
                                   "names": names, "basis": basis.tolist()})
            out.extend(names)
        return out, nodes

    def lag_distribution(self, which: int = 0) -> pd.DataFrame:
        """PDL 항(which번째)의 시차별 계수 β₀…β_k와 표준오차·t값(β = Bγ, Var β = B·Var γ·Bᵀ). 마지막 행은 합."""
        if not self.pdl_terms:
            raise ValueError("이 식에는 pdl(...) 항이 없습니다")
        if not -len(self.pdl_terms) <= which < len(self.pdl_terms):
            raise ValueError(f"pdl 항은 {len(self.pdl_terms)}개입니다(which = 0…{len(self.pdl_terms) - 1})")
        p = self.pdl_terms[which]
        B = np.asarray(p["basis"], dtype=float)
        idx = [self.coef_names.index(n) for n in p["names"]]
        g = self.coef_vector()[idx]
        V = (np.asarray(self.cov_params, dtype=float)[np.ix_(idx, idx)] if self.cov_params is not None
             else np.full((len(idx), len(idx)), np.nan))
        beta, vb = B @ g, B @ V @ B.T
        se = np.sqrt(np.diag(vb))
        one = np.ones(len(beta))
        tot, tot_se = float(one @ beta), float(np.sqrt(one @ vb @ one))
        df = pd.DataFrame({"계수": list(beta) + [tot], "표준오차": list(se) + [tot_se]},
                          index=pd.Index([f"{p['variable']}(-{i})" if i else f"{p['variable']}"
                                          for i in range(len(beta))] + ["합계"], name="시차"))
        df["t값"] = df["계수"] / df["표준오차"]
        return df

    def _all_irs(self):
        nodes = [self.lhs_ir] + list(self.term_irs) + list(self.instrument_irs)
        if self.rhs_template is not None:
            nodes.append(self.rhs_template)
        if self.weights_ir is not None:
            nodes.append(self.weights_ir)
        return nodes

    def evaluate_terms(self, terms: Sequence[str]) -> pd.DataFrame:
        """DSL 항들(예: 'log(X(-1)) @trend')을 이 식과 같은 규칙으로 계산한 전 기간 DataFrame(열 = 항)."""
        text = " ".join(terms) if not isinstance(terms, str) else terms
        text = convert_eviews_lag_ranges(self._expand_indicators(normalize(text)))
        convert_at_functions(text)
        if self.data is not None and self.data.data is not None:
            text = canonicalize_columns(text, self.data.data.columns)
        out = {}
        ctx = self._ctx()
        for t in split_terms(text):
            for one in expand_term_lag_range(t):
                if one == "c":
                    out["const"] = pd.Series(1.0, index=self.data.data.index)
                    continue
                node = _build(one, ctx)
                unknown = sorted(v for v in ir.variables(node) if v not in self.data.data.columns)
                if unknown:
                    raise ValueError(f"데이터에 없는 변수 {unknown}: {one}")
                out[one] = self._series(node, one)
        return pd.DataFrame(out, index=self.data.data.index)

    def _validate_variables(self):
        """참조 변수가 데이터에 존재하는지 검사하여 오타/누락을 조기에 잡는다."""
        cols = set(self.data.data.columns)
        referenced = set()
        for node in self._all_irs():
            referenced |= ir.variables(node)
        unknown = sorted(v for v in referenced if v not in cols)
        if unknown:
            from ..formula.parser import UnknownVariableError
            raise UnknownVariableError(
                f"데이터에 없는 변수 {unknown} (오타이거나 데이터/지시자 누락). "
                f"식: {self.equation_str[:80]}")

    def _get_array(self, name):
        return self.data.data[name].to_numpy(dtype=float)

    def _series(self, node, label):
        try:
            v = ir.evaluate(node, self._get_array)
        except DSLError:
            raise
        except Exception as e:
            raise ValueError(f"'{label}' 계산 오류: {e}") from None
        if not np.isfinite(v).any():
            raise ValueError(f"'{label}'의 값이 전 구간 결측/비유한값입니다")
        return pd.Series(v, index=self.data.data.index)

    def _prepare_data(self):
        """회귀분석을 위한 데이터 준비 (IR 벡터 평가)."""
        df = self.data.data
        self._y = self._series(self.lhs_ir, self.dependent_var)

        if self.kind == "nls":
            mask = pd.Series(True, index=df.index)
            for node in (self.lhs_ir, self.rhs_template):
                for name, lag in ir.leaves(node):
                    arr = ir.shift_array(self._get_array(name), lag)
                    mask &= np.isfinite(arr)
            X = pd.DataFrame(index=df.index)
        else:
            X = pd.DataFrame({name: self._series(node, name)
                              for name, node in zip(self.independent_vars, self.term_irs)},
                             index=df.index)
            if self.has_constant:
                X.insert(0, "const", 1.0)
            mask = None

        Z = None
        if self.method in IV_METHODS:
            Z = pd.DataFrame({name: self._series(node, name)
                              for name, node in zip([z for z in self.instruments if z != "c"],
                                                    self.instrument_irs)}, index=df.index)
            if self.has_constant or "c" in self.instruments or self.kind == "nls":
                Z.insert(0, "const", 1.0)

        parts = [self._y.rename("__y__"), X]
        if Z is not None:
            parts.append(Z.add_prefix("__z__"))
        if self.ar_lags:                       # AR 오차: p기 전 좌변·회귀변수도 관측돼야 한다(표본 밖 앞 기간은 써도 됨)
            for p in self.ar_lags:
                parts.append(self._y.shift(p).rename(f"__ar{p}__y"))
                parts.append(X.shift(p).add_prefix(f"__ar{p}__"))
        if self.method == "wls":
            w = self._series(self.weights_ir, f"가중치 {self.weights_expr}")
            w = {"ivar": w, "var": 1.0 / w, "istdev": w ** 2, "stdev": 1.0 / w ** 2}[self.wtype]
            parts.append(w.rename("__w__"))
        combined = pd.concat(parts, axis=1).replace([np.inf, -np.inf], np.nan)
        if mask is not None:
            combined = combined[mask.to_numpy()]

        # 표본기간(@smpl) 적용 — 주기 인지
        if self.smpl_start or self.smpl_end:
            from ..data.periods import parse_period, periods_of
            freq = self._freq()
            per = periods_of(combined.index, freq)
            if self.smpl_start:
                combined = combined[per >= parse_period(self.smpl_start, freq)]
                per = periods_of(combined.index, freq)
            if self.smpl_end:
                combined = combined[per <= parse_period(self.smpl_end, freq, end=True)]   # 해만 적은 끝 = 그 해 끝

        combined_clean = combined.dropna()
        try:                                   # 까닭은 알림용 — 계산하지 못해도 추정은 그대로
            self.sample_drops = self._drop_reasons(combined, combined_clean)
        except Exception:  # noqa: BLE001
            self.sample_drops = {"missing": [], "domain": [], "why": ""}
        self._y = combined_clean["__y__"]
        self._X = combined_clean[[c for c in X.columns]]
        self._Z = (combined_clean[[c for c in combined_clean.columns if c.startswith("__z__")]]
                   if Z is not None else None)
        self._W = combined_clean["__w__"] if self.method == "wls" else None
        if self._W is not None and (self._W <= 0).any():
            bad = self._W.index[self._W <= 0][0]
            raise ValueError(f"가중치가 0 이하인 관측치가 있습니다(처음: {bad:%Y-%m-%d}) — 가중치 식 {self.weights_expr}")
        n, k = len(self._y), len(self.coef_names)
        if n <= k:
            raise ValueError(f"관측치 {n}개가 계수 {k}개보다 많아야 합니다 (식: {self.equation_str[:60]})")
        dom = self.sample_drops["domain"]
        dom_note = f" — {self.sample_drops['why']}라 {len(dom)}기 빠짐(결측이 아님)" if dom else ""
        if self.smpl_start or self.smpl_end:
            _log.info(f"[DATA] 관측치: {n}개 "
                  f"(@smpl {self.smpl_start or '처음'}~{self.smpl_end or '끝'}){dom_note}")
        else:
            _log.info(f"[DATA] 관측치: {n}개{dom_note}")

    def _drop_reasons(self, combined: pd.DataFrame, clean: pd.DataFrame) -> dict:
        """표본 구간에서 빠진 기간과 까닭(D66) — 계산 결과에는 손대지 않는다.

        돌려주는 것
            {"missing": [입력 값이 없어(시차로 자료 밖 포함) 빠진 기간], "domain": [입력 값은 다 있는데 log·sqrt·나눗셈의
             정의역 밖이라(0 이하의 log 등) 빠진 기간], "why": 정의역 쪽 까닭 글(예: 'log·dlog 안의 값이 0 이하')}
        """
        nodes = [self.lhs_ir] + ([self.rhs_template] if self.kind == "nls" else list(self.term_irs))
        if self.method in IV_METHODS:
            nodes += list(self.instrument_irs)
        if self.method == "wls":
            nodes.append(self.weights_ir)
        T = len(self.data.data)
        ok = np.ones(T, dtype=bool)
        with np.errstate(all="ignore"):
            for node in nodes:
                for name, lag in ir.leaves(node):
                    ok &= np.isfinite(ir.shift_array(self._get_array(name), lag))
        base = ok.copy()
        for p in (self.ar_lags or ()):
            p = int(p)
            ok &= np.concatenate([np.zeros(min(p, T), dtype=bool), base[:max(T - p, 0)]])
        pos = self.data.data.index.get_indexer(combined.index)
        dropped = ~combined.index.isin(clean.index)
        have = ok[pos] if len(pos) else np.zeros(0, dtype=bool)
        kinds = []
        for node in nodes:
            for nd in ir.walk(node):
                k = ("log" if isinstance(nd, ir.Func) and nd.name == "log" else
                     "sqrt" if isinstance(nd, ir.Func) and nd.name == "sqrt" else
                     "/" if isinstance(nd, ir.Bin) and nd.op == "/" else
                     "**" if isinstance(nd, ir.Bin) and nd.op == "**" else None)
                if k and k not in kinds:
                    kinds.append(k)
        if kinds == ["log"]:
            why = "log·dlog 안의 값이 0 이하"
        else:
            label = {"log": "log·dlog", "sqrt": "sqrt", "/": "나눗셈", "**": "거듭제곱"}
            why = ("·".join(label[k] for k in kinds) if kinds else "계산") + \
                "의 정의역 밖 값(0 이하의 log · 음수의 sqrt · 0으로 나누기 등)"
        return {"missing": list(combined.index[dropped & ~have]), "domain": list(combined.index[dropped & have]),
                "why": why}

    # ------------------------------------------------------------------
    # 추정
    # ------------------------------------------------------------------
    def fit(self):
        """추정 실행 (method에 따라 OLS/TSLS/NLS/fixed)."""
        if self._y is None or (self._X is None and self.kind != "nls"):
            raise ValueError("데이터가 준비되지 않았습니다.")
        getattr(self, f"_fit_{self.method}")()
        res = self._results
        if self.cov_type != "nonrobust":
            if self.method == "fixed":
                raise ValueError("고정 계수식에는 강건 공분산을 쓸 수 없습니다")
            res.set_cov(self.cov_type, self.cov_lags)
        names = list(self.coef_names)
        params = pd.Series(np.asarray(res.params, dtype=float), index=names)
        bse = pd.Series(np.asarray(res.bse, dtype=float), index=names)
        tv = pd.Series(np.asarray(res.tvalues, dtype=float), index=names)
        pv = pd.Series(np.asarray(res.pvalues, dtype=float), index=names)
        self.regression_results = {
            "coefficients": dict(zip(names, params)),
            "std_errors": dict(zip(names, bse)),
            "t_values": dict(zip(names, tv)),
            "p_values": dict(zip(names, pv)),
        }
        resid = pd.Series(np.asarray(res.resid, dtype=float), index=self._y.index)
        y = self._y.to_numpy(dtype=float)
        e = resid.to_numpy()
        n, k = len(y), len(names)
        if res.wresid is not None:                       # WLS: 통계는 가중 잔차로(가중 전 값은 따로)
            e_raw = e
            e = res.wresid
            ssr = float(e @ e)
            r2 = float(res.rsquared)
        else:
            ssr = float(e @ e)
            tss = float(np.sum((y - y.mean()) ** 2))
            r2 = 1 - ssr / tss if tss > 0 else np.nan    # 항상 중심화 R²(EViews 기준)
        stats = {
            "r_squared": r2,
            "adj_r_squared": (1 - (1 - r2) * (n - 1) / (n - k)) if n > k else np.nan,
            "f_statistic": float(res.fvalue) if res.fvalue is not None else np.nan,
            "f_pvalue": float(res.f_pvalue) if res.f_pvalue is not None else np.nan,
            "n_obs": int(n),
            "aic": float(res.aic),
            "bic": float(res.bic),
            "ssr": ssr,
            "se_regression": math.sqrt(ssr / (n - k)) if n > k else np.nan,
            "durbin_watson": float(np.sum(np.diff(e) ** 2) / ssr) if ssr > 0 else np.nan,
            "log_likelihood": float(getattr(res, "llf", np.nan)),
            "method": "NL-TSLS" if (self.kind == "nls" and self.method == "tsls") else self.method.upper(),
            "cov_type": res.cov_type,
            "cov_label": res.cov_label,
        }
        if res.cov_type == "hac":
            stats["hac_lags"] = int(res.cov_lags)
        if res.cov_type != "nonrobust" and "const" in names and k > 1:
            stats["wald_f_statistic"], stats["wald_f_pvalue"] = _slope_wald_f(res, names)
        if self.kind != "nls" and not self.has_constant:
            yy = float(np.sum(res.weights * y * y)) if res.weights is not None else float(y @ y)
            stats["r_squared_uncentered"] = 1 - ssr / yy if yy > 0 else np.nan
        if res.wresid is not None:
            tss_u = float(np.sum((y - y.mean()) ** 2))
            ssr_u = float(e_raw @ e_raw)
            stats.update({"weights": self.weights_expr, "weight_type": self.wtype,
                          "unweighted_r_squared": 1 - ssr_u / tss_u if tss_u > 0 else np.nan,
                          "unweighted_ssr": ssr_u,
                          "unweighted_durbin_watson": float(np.sum(np.diff(e_raw) ** 2) / ssr_u) if ssr_u > 0 else np.nan})
        for key, val in getattr(res, "extra", {}).items():
            stats[key] = val
        if self._X is not None and self._X.shape[1] and self.kind != "nls" and self.method != "fixed" and not self.fixed_coefs:
            dup = collinear_terms(self._X)
            if dup:
                stats["collinear"] = dup
                _log.warning(f"[WARN] {self.dependent_var}: 회귀변수가 선형 종속입니다({', '.join(dup)}) — "
                             "계수·표준오차가 유일하지 않습니다(최소 노름 해)")
        self.statistics = stats
        try:
            cov = res.cov_params()
            self.cov_params = np.asarray(cov, dtype=float)
        except Exception:
            self.cov_params = None
        self.is_fitted = True
        # add-factor(잔차 이월)·확률 시뮬용: 날짜 인덱스 잔차 보관
        self.residuals = resid

    def _fit_ols(self):
        if self.ar_lags:
            return self._fit_ar()
        self._results = _reg.ols(self._y, self._X)

    def _ar_template(self) -> ir.Node:
        """f = Σbᵢxᵢ에 AR 오차를 붙인 우변: f + Σρₚ(lhs(−p) − f(−p)). 계수는 Coef(0..K−1)(coef_names 순서)."""
        K = len(self.coef_names) - len(self.ar_lags)
        terms = dict(zip(self.independent_vars, self.term_irs))
        f = None
        for i, name in enumerate(self.coef_names[:K]):
            node = ir.Coef(i) if name == "const" else ir.mul(ir.Coef(i), terms[name])
            f = node if f is None else ir.Bin("+", f, node)
        rhs = f
        for j, p in enumerate(self.ar_lags):
            u = ir.sub(ir.shift(self.lhs_ir, -p), ir.shift(f, -p))
            rhs = ir.Bin("+", rhs, ir.mul(ir.Coef(K + j), u))
        return rhs

    def _fit_ar(self):
        """AR(p) 오차의 조건부 최소제곱: 시작값은 OLS 계수와 OLS 잔차의 자기회귀 계수, 해석적 자코비안으로 Levenberg-Marquardt."""
        from scipy.optimize import least_squares
        y, X = self._y, self._X
        K, P = X.shape[1], len(self.ar_lags)
        rhs = self._ar_template()
        derivs = [ir.deriv(rhs, ir.Coef(i)) for i in range(K + P)]
        T, index = len(self.data.data), self.data.data.index
        pos = index.get_indexer(y.index)

        def at(node, c):
            return ir.evaluate(node, self._get_array, dict(enumerate(c)), length=T)[pos]
        b0 = _reg.ols(y, X).params.to_numpy(dtype=float)
        terms = dict(zip(self.independent_vars, self.term_irs))
        Xfull = np.column_stack([np.ones(T) if c == "const" else ir.evaluate(terms[c], self._get_array, length=T)
                                 for c in X.columns])
        u = pd.Series(ir.evaluate(self.lhs_ir, self._get_array) - Xfull @ b0, index=index)   # OLS 잔차(전 기간)
        U = pd.concat([u.shift(p) for p in self.ar_lags], axis=1).loc[y.index]
        ok = (U.notna().all(axis=1) & u.loc[y.index].notna()).to_numpy()
        rho0 = (np.linalg.lstsq(U[ok].to_numpy(), u.loc[y.index][ok].to_numpy(), rcond=None)[0]
                if ok.sum() > P else np.zeros(P))
        x0 = np.concatenate([b0, rho0])
        yv = y.to_numpy(dtype=float)

        def fun(c):
            r = yv - at(rhs, c)
            return np.where(np.isfinite(r), r, 1e6)

        def jac(c):
            J = -np.column_stack([at(d, c) for d in derivs])
            return np.where(np.isfinite(J), J, 0.0)
        sol = least_squares(fun, x0, jac=jac, method="lm", xtol=1e-15, ftol=1e-15, gtol=1e-15)
        # 조건부 제곱합은 ρ에 대해 국소 최소가 여럿일 수 있다(단위근 가까이에서 흔함 — 이 자료의 소비식 AR(1)은 OLS에서
        # 출발하면 ρ = 0.81의 국소 최소, 전역 최소는 ρ = 0.986). ρ를 고정하면 b는 준차분 자료의 OLS이므로 ρ만의 집중
        # 목적함수를 넓게 찾고(AR(1)은 격자, 그 이상은 여러 시작점의 Nelder-Mead), 가장 좋은 점에서 다시 LM으로 다듬어
        # 제곱합이 더 작은 쪽을 고른다 — 추정량의 정의(전역 최소)를 따른다.
        Yfull = ir.evaluate(self.lhs_ir, self._get_array)

        def conc(rho):
            ys = Yfull[pos] - sum(r * Yfull[pos - p] for r, p in zip(rho, self.ar_lags))
            Xs = Xfull[pos] - sum(r * Xfull[pos - p] for r, p in zip(rho, self.ar_lags))
            b = np.linalg.lstsq(Xs, ys, rcond=None)[0]
            e = ys - Xs @ b
            return float(e @ e), b
        local_ssr = float(sol.fun @ sol.fun) if sol.success else np.inf
        cands = []
        if P == 1:
            grid = np.linspace(-0.999, 0.999, 401)
            vals = [conc([r])[0] for r in grid]
            cands.append(np.array([grid[int(np.argmin(vals))]]))
        else:
            from scipy.optimize import minimize
            for r0 in (sol.x[K:], rho0, np.zeros(P), 0.9 * np.eye(P)[0], np.full(P, 0.9 / P)):
                try:
                    o = minimize(lambda r: conc(r)[0], np.asarray(r0, dtype=float), method="Nelder-Mead",
                                 options={"xatol": 1e-6, "fatol": 1e-14, "maxiter": 300 * P})
                    cands.append(o.x)
                except (np.linalg.LinAlgError, ValueError):
                    continue
        self._ar_note = None
        for rc in cands:
            if conc(rc)[0] < local_ssr * (1 - 1e-9):
                alt = least_squares(fun, np.concatenate([conc(rc)[1], rc]), jac=jac, method="lm",
                                    xtol=1e-15, ftol=1e-15, gtol=1e-15)
                if alt.success and float(alt.fun @ alt.fun) < float(sol.fun @ sol.fun) * (1 - 1e-12):
                    self._ar_note = (f"OLS에서 출발한 국소 최소(ρ = {', '.join(f'{v:.4f}' for v in sol.x[K:])}, "
                                     f"SSR {local_ssr:.6g})보다 제곱합이 작은 전역 최소를 골랐습니다")
                    sol = alt
        if not sol.success:
            rho = sol.x[K:]
            if ar_root_stats(rho, self.ar_lags)["ar_max_modulus"] > 0.999:
                raise ValueError("AR 오차 추정이 정해지지 않습니다: 조건부 제곱합이 ρ → 1(오차의 단위근) 쪽으로 계속 줄어 "
                                 f"상수항이 발산합니다(ρ = {', '.join(f'{v:.4f}' for v in rho)}). 차분 식(d(…)·dlog(…))이나 "
                                 "오차수정모형(wf.ecm)을 쓰세요")
            raise ValueError(f"AR 오차 추정 수렴 실패: {sol.message}")
        names = pd.Index(self.coef_names)
        fitted = pd.Series(at(rhs, sol.x), index=y.index)
        res = _reg.nls(y, pd.Series(sol.x, index=names), fitted, -jac(sol.x))
        res.method = "LS-AR"
        res.extra = ar_root_stats(sol.x[K:], self.ar_lags)
        if self._ar_note:
            res.extra["ar_note"] = self._ar_note
        self._results = res

    def _fit_wls(self):
        self._results = _reg.wls(self._y, self._X, self._W.to_numpy(dtype=float))

    def _fit_tsls(self):
        if self.kind == "nls":
            return self._fit_nls(Z=self._Z)
        self._results = _reg.tsls(self._y, self._X, self._Z)

    def _fit_gmm(self):
        self._results = _reg.gmm(self._y, self._X, self._Z, weight=self.gmm_weight, lags=self.cov_lags,
                                 iterate=self.gmm_iterate)

    def _fit_liml(self):
        self._results = _reg.liml(self._y, self._X, self._Z)

    def _nls_rhs(self, cvals, index=None):
        coefs = dict(zip(self._coef_numbers, cvals))
        v = ir.evaluate(self.rhs_template, self._get_array, coefs)
        s = pd.Series(v, index=self.data.data.index)
        return s.loc[index if index is not None else self._y.index]

    def _nls_jacobian(self, cvals) -> np.ndarray:
        """해석적 자코비안 ∂f/∂c(관측치 × 계수) — IR 기호 미분을 표본 행에서 평가한다."""
        coefs = dict(zip(self._coef_numbers, cvals))
        T = len(self.data.data)
        cols = [pd.Series(ir.evaluate(node, self._get_array, coefs, length=T), index=self.data.data.index)
                .loc[self._y.index].to_numpy(dtype=float) for node in self._nls_deriv_nodes]
        return np.column_stack(cols)

    def _fit_nls(self, Z=None):
        """비선형 최소제곱 — Z(도구)를 주면 비선형 2단계 최소제곱: 잔차를 도구의 열공간(직교 기저 Q)에 투영한 Qᵀr을 최소화한다.
        시작값은 @start, 없으면 0. 도구가 있는데 @start가 없으면 NLS 해에서 시작한다."""
        from scipy.optimize import least_squares
        y = self._y
        k = len(self._coef_numbers)
        x0 = np.zeros(k) if self.start_values is None else np.asarray(self.start_values, dtype=float)
        if len(x0) != k:
            raise DSLError(f"@start 값 {len(x0)}개 ≠ 계수 {k}개")
        self._nls_deriv_nodes = [ir.deriv(self.rhs_template, ir.Coef(num)) for num in self._coef_numbers]
        Q = None
        if Z is not None:
            U, sv, _ = np.linalg.svd(np.asarray(Z, dtype=float), full_matrices=False)
            rank = int(np.sum(sv > sv[0] * 1e-12)) if sv.size else 0
            if rank < k:
                raise ValueError(f"도구변수 {rank}개(상수항 포함) < 계수 {k}개 — 식별 불가 (@inst에 도구를 더 넣으세요)")
            Q = U[:, :rank]

        def fun(c):
            r = (y - self._nls_rhs(c)).to_numpy(dtype=float)
            r = np.where(np.isfinite(r), r, 1e6)
            return r if Q is None else Q.T @ r

        def jac(c):
            J = -self._nls_jacobian(c)          # 잔차 = y − f 이므로 ∂r/∂c = −∂f/∂c
            J = np.where(np.isfinite(J), J, 0.0)
            return J if Q is None else Q.T @ J

        def solve(start):
            m = len(y) if Q is None else Q.shape[1]
            return least_squares(fun, start, jac=jac, method="lm" if m > k else "trf", xtol=1e-15, ftol=1e-15, gtol=1e-15)
        if Q is not None and self.start_values is None:      # NL-2SLS: NLS 해에서 시작(실패하면 0에서)
            Q_, Q = Q, None
            try:
                first = solve(x0)
                if first.success and np.all(np.isfinite(first.x)):
                    x0 = first.x
            finally:
                Q = Q_
        sol = solve(x0)
        what = "NL-2SLS" if Q is not None else "NLS"
        if not sol.success:
            raise ValueError(f"{what} 수렴 실패: {sol.message} (@start로 시작값을 지정해 보세요)")
        r_end = (y - self._nls_rhs(sol.x)).to_numpy(dtype=float)
        if not np.all(np.isfinite(r_end)) or not np.all(np.isfinite(self._nls_jacobian(sol.x))):
            bad = int(np.sum(~np.isfinite(r_end)))
            raise ValueError(f"{what}: 계수 {np.round(sol.x, 6).tolist()}에서 식이 수가 아닌 관측치가 {bad}개 — 식의 정의역(로그·거듭제곱·나눗셈)을 "
                             "확인하거나 @start로 시작값을 바꾸세요")
        names = pd.Index(self.coef_names)
        if Q is not None:
            self._results = _reg.nltsls(y, pd.Series(sol.x, index=names), self._nls_rhs(sol.x),
                                        self._nls_jacobian(sol.x), Z)
            return
        self._results = _reg.nls(y, pd.Series(sol.x, index=names), self._nls_rhs(sol.x),
                                 self._nls_jacobian(sol.x))

    def _fit_fixed(self):
        vals = list(self.fixed_coefs or [])
        k = len(self.coef_names)
        if len(vals) != k:
            raise DSLError(f"@coef 값 {len(vals)}개 ≠ 계수 {k}개 "
                           f"(쓴 순서: {' '.join(self.term_order)})")
        if self.kind == "nls":
            b = np.asarray(vals, dtype=float)
        else:
            by_term = dict(zip(self.term_order, vals))
            b = np.asarray([by_term["c" if nm == "const" else nm] for nm in self.coef_names], dtype=float)
        names = pd.Index(self.coef_names)
        if self.kind == "nls":
            fitted = self._nls_rhs(b)
        elif self.ar_lags:
            vals = ir.evaluate(self._ar_template(), self._get_array, dict(enumerate(b)), length=len(self.data.data))
            fitted = pd.Series(vals, index=self.data.data.index).loc[self._y.index]
        else:
            fitted = pd.Series(self._X.to_numpy(dtype=float) @ b, index=self._y.index)
        self._results = _reg.fixed(self._y, pd.Series(b, index=names), fitted)

    def set_coefficients(self, values: Union[Dict[str, float], Sequence[float]], refresh: bool = True):
        """외부 계수를 주입한다(추정법이 'fixed'로 바뀜). dict는 계수명, 시퀀스는 쓴 순서."""
        if not self.coef_names:
            self._parse()
        if isinstance(values, dict):
            missing = [n for n in self.coef_names if n not in values]
            if missing:
                raise ValueError(f"계수 누락: {missing} (필요: {self.coef_names})")
            ordered = [values[n] for n in self.coef_names]
            if self.kind == "nls":
                self.fixed_coefs = ordered
            else:
                lookup = dict(zip(self.coef_names, ordered))
                self.fixed_coefs = [lookup["const" if t == "c" else t] for t in self.term_order]
        else:
            self.fixed_coefs = list(values)
        self.method = "fixed"
        if refresh and self.data is not None:
            self._validate_variables()
            self._prepare_data()
            self.fit()
            self._generate_pandas_formula()
            self.is_processed = True

    # ------------------------------------------------------------------
    # 연립 풀이용 인터페이스
    # ------------------------------------------------------------------
    @property
    def target(self) -> str:
        """이 식이 결정하는 내생변수(정규화). 기본은 좌변 첫 변수(EViews 규칙)."""
        if self.target_override:
            return self.target_override
        if self.lhs_ir is None:
            self._parse()
        return ir.first_variable(self.lhs_ir)

    def residual_series(self) -> pd.Series:
        """현재 계수로 전 기간 잔차(좌변 − 우변)를 계산한다(표본 밖 포함, add-factor 초기화용)."""
        rhs = self.system_rhs()
        vals = dict(enumerate(self.coef_vector()))
        lhs = ir.evaluate(self.lhs_ir, self._get_array)
        r = ir.evaluate(rhs, self._get_array, vals)
        return pd.Series(lhs - r, index=self.data.data.index)

    def coef_vector(self) -> np.ndarray:
        coefs = self.regression_results.get("coefficients", {})
        return np.asarray([float(coefs[n]) for n in self.coef_names], dtype=float)

    def system_rhs(self) -> ir.Node:
        """우변 IR — 계수는 Coef(0..k-1) (coef_names 순서) 잎으로 남긴다."""
        if self.lhs_ir is None:
            self._parse()
        if self.kind == "nls":
            mapping = {num: i for i, num in enumerate(self._coef_numbers)}
            return _remap_coefs(self.rhs_template, mapping)
        if self.ar_lags:
            return self._ar_template()
        rhs = None
        terms = dict(zip(self.independent_vars, self.term_irs))
        for i, name in enumerate(self.coef_names):
            node = ir.Coef(i) if name == "const" else ir.mul(ir.Coef(i), terms[name])
            rhs = node if rhs is None else ir.Bin("+", rhs, node)
        return rhs

    # ------------------------------------------------------------------
    # 표시/보조
    # ------------------------------------------------------------------
    def _legacy_term(self, term: str) -> bool:
        """구형 user_to_pandas가 정확히 표현할 수 있는 항인가(표시 문자열용)."""
        import ast as _ast
        try:
            tree = _ast.parse(term, mode="eval")
        except SyntaxError:
            return False
        for n in _ast.walk(tree):
            if isinstance(n, _ast.Call) and isinstance(n.func, _ast.Name):
                if n.func.id not in _LEGACY_FUNCS or (n.func.id in ("d", "dlog") and len(n.args) > 1):
                    return False
        return True

    def _pandas_str(self, term: str, node) -> str:
        if self._legacy_term(term) and not any(term in p["names"] for p in self.pdl_terms):
            try:
                return user_to_pandas(term, **self._yoy_kw())
            except Exception:
                pass
        return ir.to_pandas_str(node)

    def _generate_pandas_formula(self):
        """pandas_formula 생성 (계수 포함, 표시·하위호환용 — 풀이는 IR을 쓴다)."""
        if not self.is_fitted:
            raise ValueError("회귀분석이 먼저 수행되어야 합니다.")
        lhs = self._pandas_str(self.dependent_var, self.lhs_ir)
        coefs = self.regression_results["coefficients"]
        if self.ar_lags:
            vals = {i: coefs[n] for i, n in enumerate(self.coef_names)}
            rhs = ir.to_pandas_str(ir.substitute_coefs(self._ar_template(), vals))
        elif self.kind == "nls":
            vals = {num: coefs[f"c({num})"] for num in self._coef_numbers}
            rhs = ir.to_pandas_str(ir.substitute_coefs(self.rhs_template, vals))
        else:
            terms = dict(zip(self.independent_vars, self.term_irs))
            rhs_terms = []
            for name in self.coef_names:
                coeff = coefs[name]
                if name == "const":
                    rhs_terms.append(f"{coeff}")
                else:
                    rhs_terms.append(f"{coeff} * ({self._pandas_str(name, terms[name])})")
            rhs = " + ".join(rhs_terms)
        self.pandas_formula = f"{lhs} = {rhs}"

    def show_coeff(self, show_stats: bool = True):
        """회귀계수 출력"""
        if not self.is_fitted:
            _log.info("[ERROR] 회귀분석이 수행되지 않았습니다.")
            return

        _log.info("=" * 70)
        _log.info(f"Equation: {self.dependent_var}   [{self.method.upper()}]")
        _log.info("=" * 70)
        _log.info(f"\n{'변수':<20} {'계수':<15} {'표준오차':<15} {'t값':<12} {'p값':<12}")
        _log.info("-" * 70)

        rr = self.regression_results
        for var in rr.get("coefficients", {}):
            coeff = rr["coefficients"][var]
            se = rr["std_errors"].get(var, np.nan)
            t_val = rr["t_values"].get(var, np.nan)
            p_val = rr["p_values"].get(var, np.nan)

            sig = ""
            if p_val is not None and not np.isnan(p_val):
                if p_val < 0.01:
                    sig = "***"
                elif p_val < 0.05:
                    sig = "**"
                elif p_val < 0.1:
                    sig = "*"

            _log.info(f"{var:<20} {coeff:>12.6f}   {se:>12.6f}   {t_val:>10.4f}   {p_val:>10.4f} {sig}")

        if show_stats:
            st = self.statistics
            _log.info("\n" + "-" * 70)
            _log.info(f"  R-sq = {st.get('r_squared', np.nan):.4f}   Adj R-sq = {st.get('adj_r_squared', np.nan):.4f}")
            if "r_squared_uncentered" in st:
                _log.info(f"  (상수항 없음 — 비중심 R-sq = {st['r_squared_uncentered']:.4f})")
            if st.get("f_statistic") is not None and not np.isnan(st.get("f_statistic", np.nan)):
                _log.info(f"  F-stat = {st['f_statistic']:.2f} (p={st['f_pvalue']:.4f})")
            if "durbin_watson" in st:
                _log.info(f"  DW = {st['durbin_watson']:.3f}   S.E. = {st.get('se_regression', np.nan):.5g}")
            _log.info(f"  N = {st.get('n_obs')}")

        _log.info("=" * 70)

    def predict(self, period=None):
        """표본 내 적합값(fitted = 종속 - 잔차)"""
        if not self.is_fitted:
            raise ValueError("회귀분석이 먼저 수행되어야 합니다.")
        y = self.dependent_series()
        fitted = (y.loc[self.residuals.index] - self.residuals)
        if period is not None:
            return fitted.loc[period]
        return fitted

    def get_residuals(self):
        """잔차 반환"""
        if not self.is_fitted:
            raise ValueError("회귀분석이 먼저 수행되어야 합니다.")
        return self.residuals

    def dependent_series(self):
        """종속변수(변환 적용) 시계열을 데이터에서 계산해 반환(IR 평가).

        추정 결과 객체에 의존하지 않으므로 refit=False로 복원된 번들에서도 동작한다."""
        if self.lhs_ir is None:
            self._parse()
        v = ir.evaluate(self.lhs_ir, self._get_array)
        return pd.Series(v, index=self.data.data.index)

    # ------------------------------------------------------------------
    # 직렬화 지원
    # ------------------------------------------------------------------
    def to_saved(self) -> dict:
        return {
            "dependent_var": self.dependent_var,
            "original_input": self.original_input,
            "equation_str": self.equation_str,
            "independent_vars": list(self.independent_vars),
            "has_constant": bool(self.has_constant),
            "smpl_start": self.smpl_start, "smpl_end": self.smpl_end,
            "method": self.method,
            "kind": self.kind,
            "instruments": list(self.instruments),
            "start_values": self.start_values,
            "target_override": self.target_override,
            "pandas_formula": self.pandas_formula,
            "regression_results": self.regression_results,
            "statistics": self.statistics,
            "cov_params": None if self.cov_params is None else np.asarray(self.cov_params).tolist(),
            "cov_type": self.cov_type, "cov_lags": self.cov_lags,
            "weights": self.weights_expr, "wtype": self.wtype,
            "gmm_weight": self.gmm_weight, "gmm_iterate": self.gmm_iterate,
        }

    @classmethod
    def restore(cls, saved: dict, data: Data) -> "Equation":
        """번들 coefficients.json 항목에서 재추정 없이 복원한다."""
        text = saved["equation_str"]
        kind = saved.get("kind", "estimated")
        eq = cls(text, data, auto_fix=False,
                 instruments=saved.get("instruments") or None, weights=saved.get("weights"),
                 wtype=saved.get("wtype") or "ivar", gmm_weight=saved.get("gmm_weight"),
                 iterate=bool(saved.get("gmm_iterate", False)))
        eq.original_input = saved.get("original_input", text)
        eq.smpl_start = saved.get("smpl_start")
        eq.smpl_end = saved.get("smpl_end")
        eq.start_values = saved.get("start_values")
        eq.method = saved.get("method", "ols")
        eq.cov_type = normalize_cov_type(saved.get("cov_type"))
        eq.cov_lags = saved.get("cov_lags")
        eq.kind = kind
        eq._parse()
        eq.target_override = saved.get("target_override")
        rr = saved.get("regression_results", {}) or {}
        coefs = rr.get("coefficients", {})
        missing = [n for n in eq.coef_names if n not in coefs]
        if missing:
            raise ValueError(f"저장된 계수와 식이 맞지 않습니다(누락 {missing}) — refit=True로 복원하세요")
        eq.regression_results = rr
        eq.statistics = saved.get("statistics", {}) or {}
        cov = saved.get("cov_params")
        eq.cov_params = None if cov is None else np.asarray(cov, dtype=float)
        eq.pandas_formula = saved.get("pandas_formula")
        eq.is_processed = True
        eq.is_fitted = True
        return eq

    def __repr__(self):
        if self.is_fitted:
            return f"Equation({self.dependent_var}, {self.method}, R-sq={self.statistics.get('r_squared', float('nan')):.4f})"
        return f"Equation({self.dependent_var or '?'}, not fitted)"


def _slope_wald_f(res, names) -> Tuple[float, float]:
    """상수항을 뺀 모든 계수 = 0 의 Wald F(현재 공분산 — 강건 공분산일 때 보고)."""
    from scipy import stats as _st
    idx = [i for i, nm in enumerate(names) if nm != "const"]
    b = res.params.to_numpy(dtype=float)[idx]
    V = res.cov_params().to_numpy(dtype=float)[np.ix_(idx, idx)]
    try:
        w = float(b @ np.linalg.solve(V, b))
    except np.linalg.LinAlgError:
        return np.nan, np.nan
    q = len(idx)
    return w / q, float(_st.f.sf(w / q, q, res.df_resid))


def expand_indicators(data, s: str, bare_seas: bool = True) -> str:
    """@seas(n) / @seas / @trend / @d(...) / @step(...) 토큰을 데이터(Data)의 지시자 컬럼명으로 치환한다.
    bare_seas=False(식 하나를 계산하는 genr·eval)면 번호 없는 @seas는 오류 — 더미가 여럿이라."""
    if not s:
        return s
    if re.search(r"@seas", s, re.IGNORECASE):
        data.ensure_seasonal_dummies()
        cols = data.seasonal_columns()

        def one(m):
            k = int(m.group(1))
            if not 1 <= k <= len(cols):
                raise DSLError(f"@seas({k}) 범위 밖 (1~{len(cols)})")
            return cols[k - 1]
        s = re.sub(r"@seas\(\s*(\d+)\s*\)", one, s, flags=re.IGNORECASE)
        if re.search(r"@seas\b(?!\()", s, re.IGNORECASE):
            if not bare_seas:
                raise DSLError("식 계산에서는 @seas에 번호를 주세요(예: @seas(1)) — 번호 없는 @seas는 추정식에서 더미 묶음입니다")
            has_const = "c" in _raw_split(s)
            seas = " ".join(cols[1:] if has_const else cols)
            s = re.sub(r"@seas\b(?!\()", seas, s, flags=re.IGNORECASE)

    def repl(m):
        return data.ensure_indicator(m.group(0))
    s = re.sub(r"@step\([^)]*\)", repl, s, flags=re.IGNORECASE)     # @seas처럼 대소문자를 가리지 않는다(@TREND·@STEP(…))
    s = re.sub(r"@d\([^)]*\)", repl, s, flags=re.IGNORECASE)
    s = re.sub(r"@trend\b", repl, s, flags=re.IGNORECASE)
    return s


def collinear_terms(X: pd.DataFrame) -> List[str]:
    """선형 종속인 회귀변수 이름(없으면 빈 목록). 특이값이 최대×1e-10 이하인 방향의 영벡터에서 0이 아닌 열."""
    A = X.to_numpy(dtype=float)
    if A.shape[0] == 0:
        return []
    scale = np.maximum(np.abs(A).max(axis=0), 1e-300)
    _, sv, vt = np.linalg.svd(A / scale, full_matrices=False)
    null = vt[sv <= sv.max() * 1e-10] if sv.size else vt[:0]
    if null.shape[0] == 0:
        return []
    involved = np.any(np.abs(null) > 1e-6, axis=0)
    return [str(c) for c, f in zip(X.columns, involved) if f]


def _extract_ar(body: str) -> Tuple[str, List[int]]:
    """본문에서 ar(p)·ar(p to q) 항을 떼어 낸다 → (나머지 본문, 정렬한 AR 시차)."""
    from ..formula.parser import MAX_LAG
    keep, lags = [], []
    for t in split_terms(body):
        m = _AR_RE.match(t)
        if not m:
            keep.append(t)
            continue
        a = int(m.group(1))
        b = int(m.group(2)) if m.group(2) else a
        if not 1 <= a <= b <= MAX_LAG:
            raise DSLError(f"ar 시차는 1 이상 {MAX_LAG} 이하, 앞이 작아야 합니다: {t}")
        lags.extend(range(a, b + 1))
    if len(set(lags)) != len(lags):
        raise DSLError(f"같은 AR 시차가 두 번 들어 있습니다: {sorted(lags)}")
    return " ".join(keep), sorted(lags)


def ar_root_stats(rho, lags) -> dict:
    """AR 다항식 1 − Σρₚ Lᵖ의 역근(EViews 'Inverted AR Roots'와 같은 뜻): 모두 단위원 안이면 정상."""
    p = max(lags)
    coef = np.zeros(p + 1)
    coef[0] = 1.0
    for r, lag in zip(rho, lags):
        coef[lag] = -float(r)
    roots = np.roots(coef)                     # zᵖ − ρ₁zᵖ⁻¹ − … − ρₚ = 0 의 근 = 역근
    mod = np.abs(roots)
    return {"ar_inverted_roots": [[float(z.real), float(z.imag)] for z in roots],
            "ar_max_modulus": float(mod.max()) if len(mod) else 0.0,
            "ar_stationary": bool(len(mod) == 0 or mod.max() < 1.0)}


def pdl_basis(k: int, d: int, constraint: int = 0) -> np.ndarray:
    """PDL 기저 B((k+1) × m): 시차 계수 β = Bγ. 다항식은 가운데 시차 c = ⌊k/2⌋ 기준 (i − c)^j, j = 0…d.
    constraint 1 = β₋₁ = 0, 2 = β_{k+1} = 0, 3 = 둘 다 — 제약을 만족하는 γ 공간(영공간)으로 줄인다."""
    c = k // 2
    lags = np.arange(k + 1, dtype=float) - c
    M = np.column_stack([lags ** j for j in range(d + 1)])
    rows = []
    if constraint in (1, 3):
        rows.append([(-1.0 - c) ** j for j in range(d + 1)])
    if constraint in (2, 3):
        rows.append([(k + 1.0 - c) ** j for j in range(d + 1)])
    if not rows:
        return M
    R = np.asarray(rows)
    _, sv, vt = np.linalg.svd(R)
    rank = int(np.sum(sv > 1e-12 * sv.max()))
    N = vt[rank:].T
    if N.shape[1] == 0:
        raise DSLError(f"pdl 제약을 걸면 남는 계수가 없습니다(차수 {d}, 제약 {constraint}) — 차수를 높이세요")
    return M @ N


def _split_args(text: str) -> List[str]:
    """괄호 밖 쉼표로 인자를 나눈다."""
    out, depth, cur = [], 0, []
    for ch in text:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            out.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    out.append("".join(cur).strip())
    return out


def _build(text: str, ctx) -> "ir.Node":
    """사용자 표기(@함수 포함) → IR."""
    return ir.build(convert_at_functions(text), ctx)


def _remap_coefs(node, mapping):
    if isinstance(node, ir.Coef):
        return ir.Coef(mapping[node.index])
    if isinstance(node, (ir.Const, ir.Var)):
        return node
    if isinstance(node, ir.Neg):
        return ir.Neg(_remap_coefs(node.arg, mapping))
    if isinstance(node, ir.Bin):
        return ir.Bin(node.op, _remap_coefs(node.a, mapping), _remap_coefs(node.b, mapping))
    if isinstance(node, ir.Func):
        return ir.Func(node.name, _remap_coefs(node.arg, mapping))
    raise TypeError(node)


def util_extract_variables(expression: str) -> List[str]:
    """수식에서 변수명 추출(하위호환 — 정규식 기반 근사)."""
    pattern = r'\b[A-Za-z_][A-Za-z0-9_]*\b'
    matches = re.findall(pattern, expression)
    exclude = {'log', 'exp', 'np', 'pd', 'sin', 'cos', 'tan', 'sqrt', 'abs',
               'max', 'min', 'mean', 'std', 'var', 'sum', 'df', 'c',
               'shift', 'pct_change', 'rolling', 'diff', 'qoq', 'yoy', 'ma', 't'}
    return [m for m in matches if m not in exclude]


def util_convert_ratio_equation(
    formula: str, endogenous_vars: List[str]
) -> Tuple[str, bool]:
    """
    (하위호환) 비율 방정식 변환 — AST로 정확한 패턴만 인식한다.

    VAR1/VAR2 = RHS          -> VAR1 = VAR2 * (RHS)
    np.log(VAR1/VAR2) = RHS  -> VAR1 = VAR2 * np.exp(RHS)

    그 외 좌변(예: np.log(X)/4)은 변환하지 않는다. 엔진 v3의 연립 풀이는 이 변환을
    쓰지 않고 암시적 형태(좌변-우변=0)를 그대로 푼다.
    """
    import ast as _ast
    from ..formula.parser import find_top_level_eq
    pos = find_top_level_eq(formula)
    if pos < 0:
        return formula, False
    lhs, rhs = formula[:pos].strip(), formula[pos + 1:].strip()
    try:
        node = _ast.parse(lhs, mode="eval").body
    except SyntaxError:
        return formula, False

    def ratio(n):
        if (isinstance(n, _ast.BinOp) and isinstance(n.op, _ast.Div)
                and isinstance(n.left, _ast.Name)
                and isinstance(n.right, (_ast.Name, _ast.Constant))):
            return n.left.id, _ast.unparse(n.right)
        return None

    is_log = (isinstance(node, _ast.Call) and isinstance(node.func, _ast.Attribute)
              and isinstance(node.func.value, _ast.Name) and node.func.value.id == "np"
              and node.func.attr == "log" and len(node.args) == 1)
    r = ratio(node.args[0]) if is_log else ratio(node)
    if r is None or r[0] not in endogenous_vars:
        return formula, False
    var1, var2 = r
    if is_log:
        return f"{var1} = {var2} * np.exp({rhs})", True
    return f"{var1} = {var2} * ({rhs})", True
