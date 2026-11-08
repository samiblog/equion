#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""워크파일 객체 — 방정식·모델·시나리오·그래프·표.

모든 객체는 이름으로 워크파일에 등록되고(`wf.obj("이름")`, `wf.이름`), `.output()`으로 출력 객체를,
`.show()`로 화면 표시를 한다. 계산 결과는 pandas 객체로 바로 꺼내 Python에서 이어 쓴다(D14).
"""

import fnmatch
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Union

import numpy as np
import pandas as pd

from ..estimation.equation import Equation
from ..stats import diagnostics as _diag
from ..stats.result import TestResult
from ..scenario import (Scenario, control_simulation, missing_exogenous, missing_history, multipliers,
                        stochastic_simulation)
from ..system.model import Model
from ..system.simulate import SimulationResult
from .output import GraphOutput, TableOutput, say, spool
from .runtime import quiet, record_input, record_output, record_solve

_METHOD_LABEL = {"ols": "최소제곱(OLS)", "wls": "가중 최소제곱(WLS)", "tsls": "2단계 최소제곱(TSLS)",
                 "gmm": "일반화 적률법(GMM)", "liml": "제한정보 최우(LIML)",
                 "nls": "비선형 최소제곱(NLS)", "fixed": "고정 계수"}
_WTYPE_LABEL = {"ivar": "1/분산", "var": "분산(역수로)", "istdev": "1/표준편차", "stdev": "표준편차(역수로)"}


class MergeError(ValueError):
    """방정식 파일을 merge할 때 일부 식을 추정하지 못함(입력 오류 — CLI 종료 코드 3)."""


def _stars(p):
    if p is None or not np.isfinite(p):
        return ""
    return "***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.1 else ""


# ===========================================================================
# 방정식
# ===========================================================================
class EquationObject:
    """이름 붙은 추정 방정식. `ls`/`tsls`/`nls`/`fixed`로 (다시) 추정한다."""

    kind = "equation"

    def __init__(self, wf, name: str):
        self._wf = wf
        self.name = name
        self.eq: Optional[Equation] = None
        self.spec: Optional[str] = None
        self.version = 0

    def __repr__(self):
        return f"<방정식 {self.name}: {self.spec or '(추정 전)'}>"

    # ---- 추정 -------------------------------------------------------------
    def _make(self, spec, method=None, instruments=None, coefficients=None, start=None, cov=None, lags=None, **opts):
        wf = self._wf

        def build():
            eq = Equation(spec, wf._data, method=method, instruments=instruments, cov=cov, lags=lags, **opts)
            if start is not None:
                eq.start_values = [float(v) for v in start]
            if eq.smpl_start is None and eq.smpl_end is None and wf._smpl is not None:
                eq.smpl_start, eq.smpl_end = wf._smpl_tokens()
            eq.wt = wf._wt
            if coefficients is not None:
                eq.set_coefficients(coefficients)
            else:
                eq.process()
            return eq
        return quiet(build)

    def _adopt(self, eq: Equation, spec: str, loud: bool = True):
        self.eq, self.spec = eq, spec
        self.version += 1
        if loud:
            st = eq.statistics
            say(f"[{self.name}] {eq.method.upper()} {eq.dependent_var} — n={st.get('n_obs')}, "
                f"R²={st.get('r_squared', float('nan')):.4f}")
        return self

    def ls(self, spec: str, cov: str = None, lags: int = None):
        """최소제곱(OLS) 추정. 식이 계수 `c(n)` 꼴이면 비선형(NLS), 식 끝에 `@coef`가 있으면 고정 계수로 처리한다.

        표본은 워크파일 smpl(또는 식 끝 `@smpl`) 안의 결측 없는 기간이다. 식 문법은 docs/explain/equations.md.

        매개변수
            spec: 추정식 — 첫 항이 종속변수, c는 상수항(예: "I c Y(-1) R", "log(CN) c log(Y) @seas")
            cov: 계수 공분산 — None(보통) · 'white'(= 'hc1') · 'hc0'~'hc3' · 'hac'(Newey-West)
            lags: hac의 시차(기본 ⌊4(n/100)^(2/9)⌋)

        돌려주는 것
            이 방정식 객체(이어 부르기 — .coefs · .stats · eqn.show(eq))

        오류
            DSLError: 문법·없는 함수 · ValueError: 없는 변수, 관측치가 계수보다 적음, 예약 이름 변수

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> eq = wf.equation("eq_i").ls("I c Y(-1) R")
            >>> eq.coefs.round(3).to_dict()
            {'const': 4.481, 'Y(-1)': 0.151, 'R': -0.963}
            >>> eq.nobs, round(eq.stats["r_squared"], 4)
            (199, 0.9985)

        관련: tsls · nls · fixed · set_cov
        """
        if " @inst" in f" {spec}" or " @ " in f" {spec} ":
            raise ValueError("도구변수가 있는 식은 .tsls(...)로 추정하세요.")
        return self._adopt(self._make(spec, cov=cov, lags=lags), spec)

    def tsls(self, spec: str, inst: Union[str, Sequence[str]] = None, cov: str = None, lags: int = None):
        """2단계 최소제곱(TSLS) — 내생 설명변수가 있을 때.

        도구변수는 inst=[…]나 식 끝의 `@inst …`로 준다. 상수항은 도구에 저절로 들어가고, 식 안의 외생 설명변수도 도구에 넣는다.

        매개변수
            spec: 추정식
            inst: 도구변수(이름·식 목록 또는 공백 구분 글자)
            cov, lags: ls와 같다

        오류
            ValueError: 도구가 계수보다 적음(식별 불가)

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> eq = wf.equation("eq_cn").tsls("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
            >>> eq.coefs.round(3).to_dict()
            {'const': 10.651, 'Y': 0.531, 'CN(-1)': 0.256}

        관련: gmm · liml · ls
        """
        if isinstance(inst, str):
            inst = inst.split()
        if inst is None and "@inst" not in spec and " @ " not in f" {spec} ":
            raise ValueError("tsls에는 도구변수가 필요합니다 (inst=[...] 또는 '@inst …').")
        return self._adopt(self._make(spec, method="tsls", instruments=inst, cov=cov, lags=lags), spec)

    def wls(self, spec: str, weights: str, wtype: str = "ivar", cov: str = None, lags: int = None):
        """가중 최소제곱(WLS) — 관측마다 오차 분산이 다를 때.

        weights는 계열 이름이나 식(예: "1/POP", "@trend"), wtype은 그 계열의 뜻: 'ivar'(1/분산, 기본) · 'var'(분산) ·
        'istdev'(1/표준편차) · 'stdev'(표준편차). R²·SSR·DW는 가중 잔차로, 가중 전 값은 stats의 unweighted_*로.
        연립 풀이에서는 OLS 식과 똑같이 쓰인다.

        오류
            TypeError: weights가 배열 — 먼저 시리즈로(wf['W'] = 값) · ValueError: 0 이하 가중치

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> _ = wf.genr("WT = 1 / Y")
            >>> eq = wf.equation("eq_w").wls("I c Y(-1) R", weights="WT")
            >>> eq.method, round(float(eq.coefs["R"]), 2)
            ('wls', -0.97)
        """
        if not isinstance(weights, str):
            raise TypeError("weights는 계열 이름이나 식(문자열)입니다 — 배열·Series면 먼저 시리즈로 넣으세요: "
                            "wf['W'] = 값 → .wls(spec, weights='W')")
        return self._adopt(self._make(spec, method="wls", weights=weights, wtype=wtype, cov=cov, lags=lags), spec)

    def gmm(self, spec: str, inst: Union[str, Sequence[str]] = None, weight: str = "white", lags: int = None,
            iterate: bool = False):
        """선형 GMM(도구변수) — 이분산·자기상관에 강건한 가중.

        1단계 TSLS 잔차로 가중행렬을 만들어 다시 추정하고(2단계), iterate=True면 수렴할 때까지 반복한다. 과대식별이면
        Hansen J 검정(stats['j_statistic'] · ['j_pvalue'])을 함께 낸다.

        매개변수
            inst: 도구변수(tsls와 같이)
            weight: 'white'(이분산 강건) · 'hac'(Bartlett, lags)

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> eq = wf.equation("eq_gmm").gmm("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
            >>> round(float(eq.coefs["Y"]), 2), round(eq.stats["j_pvalue"], 2)
            (0.53, 0.1)
        """
        if isinstance(inst, str):
            inst = inst.split()
        if inst is None and "@inst" not in spec and " @ " not in f" {spec} ":
            raise ValueError("gmm에는 도구변수가 필요합니다 (inst=[...] 또는 '@inst …').")
        return self._adopt(self._make(spec, method="gmm", instruments=inst, lags=lags, gmm_weight=weight,
                                      iterate=iterate), spec)

    def liml(self, spec: str, inst: Union[str, Sequence[str]] = None, cov: str = None, lags: int = None):
        """제한정보 최우(LIML, k-class) — 약한 도구에 TSLS보다 덜 치우친다. κ는 stats['liml_kappa'].

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> eq = wf.equation("eq_liml").liml("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
            >>> round(float(eq.coefs["Y"]), 2), round(eq.stats["liml_kappa"], 3)
            (0.53, 1.023)
        """
        if isinstance(inst, str):
            inst = inst.split()
        if inst is None and "@inst" not in spec and " @ " not in f" {spec} ":
            raise ValueError("liml에는 도구변수가 필요합니다 (inst=[...] 또는 '@inst …').")
        return self._adopt(self._make(spec, method="liml", instruments=inst, cov=cov, lags=lags), spec)

    def nls(self, spec: str, start: Sequence[float] = None, cov: str = None, lags: int = None):
        """비선형 최소제곱(NLS) — 식은 `Y = c(1) + c(2)*X^c(3)` 꼴. 기울기는 식을 미분해 정확히 계산한다.

        시작값은 start=[…] 또는 식 끝 `@start …`(없으면 0). cov·lags는 ls와 같다.

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> eq = wf.equation("eq_nls").nls("CN = c(1) + c(2)*Y^c(3)", start=[10, 0.5, 1])
            >>> eq.coefs.round(2).to_dict()
            {'c(1)': 11.31, 'c(2)': 0.76, 'c(3)': 0.99}
        """
        return self._adopt(self._make(spec, method="nls", start=start, cov=cov, lags=lags), spec)

    def set_cov(self, cov: str = None, lags: int = None):
        """계수 공분산만 바꿔 다시 계산한다(계수는 그대로). cov=None이면 보통 공분산.

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> eq = wf.equation("eq_i").ls("I c Y(-1) R")
            >>> before = eq.stderrs.round(4).tolist()
            >>> _ = eq.set_cov("hac", lags=4)
            >>> eq.stderrs.round(4).tolist() != before
            True
        """
        eq = self._require()
        from ..stats.robust import normalize_cov_type
        eq.cov_type, eq.cov_lags = normalize_cov_type(cov), (None if lags is None else int(lags))
        self._ensure_fit(force=True)
        return self._adopt(eq, self.spec, loud=False)

    def fixed(self, spec: str, coefs: Union[Dict[str, float], Sequence[float]]):
        """다른 곳(다른 프로그램·Python 추정 등)에서 얻은 계수를 고정해 넣는다 — 모델에서 추정식처럼 쓰인다.

        coefs는 식에 쓴 항 순서의 목록이거나 {계수 이름: 값}(상수항 이름은 'const').

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> eq = wf.equation("eq_fx").fixed("I c Y(-1) R", [5.0, 0.15, -1.0])
            >>> eq.method, eq.coefs.to_dict()
            ('fixed', {'const': 5.0, 'Y(-1)': 0.15, 'R': -1.0})
        """
        return self._adopt(self._make(spec, method="fixed", coefficients=coefs), spec)

    # ---- 진단 검정 (equion.stats — 외부 회귀 패키지 없이) ----------------
    def _ensure_fit(self, force: bool = False):
        """잔차·회귀변수가 메모리에 있게 한다(저장 파일에서 복원한 식은 같은 자료로 다시 추정)."""
        eq = self._require()
        if force or eq._results is None or eq._y is None:
            def refit():
                if eq.lhs_ir is None:
                    eq._parse()
                eq._validate_variables()
                eq._prepare_data()
                eq.fit()
            quiet(refit)
        return eq

    def _residuals_ok(self, eq, test: str):
        """잔차가 사실상 0(완전 적합)이면 잔차 검정은 의미가 없다 — 반올림 잡음을 검정하게 되므로 막는다."""
        e = eq._results.resid.to_numpy(dtype=float)
        y = eq._y.to_numpy(dtype=float)
        if not len(e) or np.max(np.abs(e)) <= 1e-10 * (1.0 + np.max(np.abs(y))):
            raise ValueError(f"{test}: 잔차가 사실상 0입니다(완전 적합) — 잔차 검정을 할 수 없습니다")
        return eq

    def _linear(self, test: str):
        eq = self._residuals_ok(self._ensure_fit(), test)
        if eq.method != "ols" or eq.ar_lags:
            raise ValueError(f"{test}은(는) OLS 식에만 쓸 수 있습니다({self.name}: {eq.method.upper()}). "
                             "잔차 검정(ljungbox·arch·normality)과 wald는 모든 추정법에 쓸 수 있습니다.")
        return eq, eq._results

    def _say(self, r: TestResult) -> TestResult:
        say(f"[{self.name}] {r.name}: 통계량 {r.statistic:.4f}" + (f", p={r.pvalue:.4f}" if np.isfinite(r.pvalue) else ""))
        return r

    def serial_lm(self, lags: int = 2) -> TestResult:
        """계열상관 LM 검정(Breusch-Godfrey). 귀무가설: 시차 lags까지 잔차에 계열상관이 없다. OLS·WLS 식.

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> eq = wf.equation("eq_i").ls("I c Y(-1) R")
            >>> r = eq.serial_lm(4)
            >>> round(r.statistic, 3), r.reject(0.05)
            (4.215, False)
        """
        eq, res = self._linear("계열상관 LM 검정")
        return self._say(_diag.breusch_godfrey(res.resid.to_numpy(), eq._X.to_numpy(), lags))

    def ljungbox(self, lags: int = None) -> TestResult:
        """Ljung-Box Q 검정(잔차 자기상관). 결과의 .table에 시차별 자기상관·Q·p값. 모든 추정법.

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> eq = wf.equation("eq_i").ls("I c Y(-1) R")
            >>> r = eq.ljungbox(8)
            >>> len(r.table), r.reject(0.05)
            (8, False)
        """
        eq = self._residuals_ok(self._ensure_fit(), "Ljung-Box 검정")
        return self._say(_diag.ljung_box(eq._results.resid.to_numpy(), lags))

    def white(self, cross: bool = True) -> TestResult:
        """White 이분산 검정 — 잔차²를 회귀변수·제곱(cross=True면 교차곱까지)에 회귀. 귀무가설: 동분산.

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> eq = wf.equation("eq_i").ls("I c Y(-1) R")
            >>> eq.white().reject(0.05)
            False
        """
        eq, res = self._linear("White 검정")
        return self._say(_diag.white(res.resid.to_numpy(), eq._X.to_numpy(), cross))

    def breusch_pagan(self) -> TestResult:
        """Breusch-Pagan-Godfrey 이분산 검정. 귀무가설: 동분산.

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> eq = wf.equation("eq_i").ls("I c Y(-1) R")
            >>> eq.breusch_pagan().reject(0.05)
            False
        """
        eq, res = self._linear("Breusch-Pagan 검정")
        return self._say(_diag.breusch_pagan(res.resid.to_numpy(), eq._X.to_numpy()))

    def arch(self, lags: int = 1) -> TestResult:
        """ARCH LM 검정 — 잔차 분산의 자기상관. 모든 추정법.

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> eq = wf.equation("eq_i").ls("I c Y(-1) R")
            >>> round(eq.arch(4).pvalue, 2)
            0.22
        """
        eq = self._residuals_ok(self._ensure_fit(), "ARCH 검정")
        return self._say(_diag.arch_lm(eq._results.resid.to_numpy(), lags))

    def normality(self) -> TestResult:
        """Jarque-Bera 잔차 정규성 검정. 모든 추정법.

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> eq = wf.equation("eq_i").ls("I c Y(-1) R")
            >>> eq.normality().reject(0.05)
            False
        """
        eq = self._residuals_ok(self._ensure_fit(), "Jarque-Bera 검정")
        return self._say(_diag.jarque_bera(eq._results.resid.to_numpy()))

    def reset(self, terms: int = 1) -> TestResult:
        """Ramsey RESET — 적합값의 2~(terms+1)제곱을 더하면 나아지는가(함수 형태 검정).

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> wf.equation("good").ls("I c Y(-1) R").reset(1).reject(0.05)
            False
            >>> wf.equation("bad").ls("CN c G").reset(1).reject(0.05)
            True
        """
        eq, res = self._linear("RESET 검정")
        return self._say(_diag.reset(eq._y.to_numpy(), eq._X.to_numpy(), res.fittedvalues.to_numpy(), terms))

    def _ls_family(self, test: str):
        eq = self._ensure_fit()
        if eq.method not in ("ols", "wls") or eq.ar_lags:
            raise ValueError(f"{test}은(는) OLS·WLS 식에만 쓸 수 있습니다({self.name}: {eq.method.upper()}).")
        return eq

    @staticmethod
    def _term_list(terms) -> List[str]:
        out = []
        for t in terms:
            out.extend(t.split() if isinstance(t, str) and "(" not in t else [t])
        return [t for t in out if t]

    def _nested_table(self, y, X, w) -> pd.DataFrame:
        from ..stats import regression as _reg
        r = _reg.wls(y, X, w) if w is not None else _reg.ols(y, X)
        p = r.pvalues
        return pd.DataFrame({"계수": r.params, "표준오차": r.bse, "t값": r.tvalues, "p값": p,
                             "": [_stars(v) for v in p]}).rename_axis("변수")

    def omitted(self, *terms: str) -> TestResult:
        """누락 변수 검정 — 항들을 더하면 설명력이 유의하게 느는가(F·LR). 두 식을 공통 표본에서 다시 추정한다.

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> eq = wf.equation("eq_i").ls("I c Y(-1) R")
            >>> eq.omitted("R(-1)", "G").reject(0.05)
            False
        """
        eq = self._ls_family("누락 변수 검정")
        terms = self._term_list(terms)
        if not terms:
            raise ValueError("더할 항을 하나 이상 주세요: eq.omitted('X2')")
        new = eq.evaluate_terms(terms).loc[eq._y.index]
        clash = [c for c in new.columns if c in eq._X.columns]
        if clash:
            raise ValueError(f"이미 식에 있는 항: {clash}")
        keep = np.isfinite(new.to_numpy(dtype=float)).all(axis=1)
        y, Xs = eq._y[keep], eq._X[keep]
        Xb = pd.concat([Xs, new[keep]], axis=1)
        w = eq._W[keep].to_numpy(dtype=float) if eq._W is not None else None
        r = _diag.nested(y.to_numpy(), Xs.to_numpy(), Xb.to_numpy(), w, name="누락 변수 검정",
                         null=f"더한 항의 계수 = 0 ({' · '.join(new.columns)})")
        r.info["추정법"] = eq.method.upper()
        if int((~keep).sum()):
            r.info["공통 표본"] = f"새 항의 결측으로 {int((~keep).sum())}개 관측치를 빼고 두 식 모두 다시 추정"
        r.table = self._nested_table(y, Xb, w)
        return self._say(r)

    def redundant(self, *terms: str) -> TestResult:
        """불필요 변수 검정 — 식의 항들을 빼도 되는가(계수가 함께 0). 이름은 식에 쓴 그대로(상수항은 'c').

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> eq = wf.equation("eq_i").ls("I c Y(-1) R")
            >>> eq.redundant("R").reject(0.05)
            True
        """
        eq = self._ls_family("불필요 변수 검정")
        terms = self._term_list(terms)
        if not terms:
            raise ValueError("뺄 항을 하나 이상 주세요: eq.redundant('X2')")
        cols = ["const" if t == "c" else t for t in terms]
        missing = [t for t in cols if t not in eq._X.columns]
        if missing:
            raise ValueError(f"식에 없는 항: {missing} (있는 항: {list(eq._X.columns)})")
        keep_cols = [c for c in eq._X.columns if c not in cols]
        w = eq._W.to_numpy(dtype=float) if eq._W is not None else None
        r = _diag.nested(eq._y.to_numpy(), eq._X[keep_cols].to_numpy(), eq._X.to_numpy(), w,
                         name="불필요 변수 검정", null=f"뺀 항의 계수 = 0 ({' · '.join(cols)})")
        r.info["추정법"] = eq.method.upper()
        r.table = self._nested_table(eq._y, eq._X[keep_cols], w) if keep_cols else None
        return self._say(r)

    def lag_distribution(self, which: int = 0) -> TableOutput:
        """pdl(...) 항의 시차별 계수(β₀…β_k)·표준오차와 합계 표. which = 식 안의 몇 번째 pdl 항인지(0부터).

        오류
            ValueError: pdl 항이 없거나 which가 범위 밖

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> eq = wf.equation("eq_pdl").ls("I c pdl(Y, 4, 2) R")
            >>> t = eq.lag_distribution()
            >>> len(t.data), round(float(t.data["계수"].iloc[-1]), 3)
            (6, 0.151)
        """
        eq = self._require()
        if eq.cov_params is None:
            self._ensure_fit(force=True)
        df = eq.lag_distribution(which)
        p = eq.pdl_terms[which]
        cons = {0: "제약 없음", 1: "가까운 끝 0", 2: "먼 끝 0", 3: "양 끝 0"}[p["constraint"]]
        return TableOutput(df, title=f"방정식 {self.name} 시차 분포 — {p['term']}",
                           head=[f"시차 {p['lags']} · 다항식 차수 {p['degree']} · {cons} · 계수 {', '.join(p['names'])}"],
                           name=f"{self.name}_pdl{which + 1}")

    def _coef_order(self):
        """c(n) 번호 → 계수 위치, 번호별 이름. OLS·TSLS는 쓴 항 순서(c는 상수항), NLS는 식의 c(n) 번호."""
        eq = self._ensure_fit()
        names = list(eq.coef_names)
        if eq.kind == "nls":
            return {num: names.index(f"c({num})") for num in eq._coef_numbers}, {n: f"c({n})" for n in eq._coef_numbers}
        order = ["const" if t == "c" else t for t in eq.term_order]
        return {i + 1: names.index(t) for i, t in enumerate(order)}, {i + 1: t for i, t in enumerate(order)}

    def wald(self, *restrictions: str) -> TestResult:
        """Wald 계수 제약 검정 — `eq.wald("c(2) + c(3) = 1", "c(4) = 0")`. c(n)은 식에 쓴 항 순서(상수항 c가 c(1)).

        공분산은 추정 때 고른 것을 쓴다(강건 공분산이면 강건 Wald).

        오류
            ValueError: 문법 오류, 계수 번호 범위 밖, 서로 겹치거나 모순인 제약

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> eq = wf.equation("eq_i").ls("I c Y(-1) R")
            >>> eq.wald("c(2) = 0.15", "c(3) = -1").reject(0.05)        # 참값
            False
            >>> eq.wald("c(2) = 0.2").reject(0.05)
            True
        """
        if len(restrictions) == 1 and "," in restrictions[0]:
            restrictions = tuple(r.strip() for r in restrictions[0].split(","))
        if not restrictions:
            raise ValueError("제약을 하나 이상 주세요: eq.wald('c(2) = 0')")
        eq = self._ensure_fit()
        if eq.method == "fixed":
            raise ValueError("고정 계수식에는 Wald 검정을 할 수 없습니다(표준오차 없음)")
        pos, labels = self._coef_order()
        R, q = _diag.parse_restrictions(restrictions, max(pos))
        missing = [i + 1 for i in range(R.shape[1]) if i + 1 not in pos and np.any(R[:, i] != 0)]
        if missing:
            raise ValueError(f"식에 없는 계수 번호: {['c(%d)' % i for i in missing]} (있는 번호: {sorted(pos)})")
        res = eq._results
        R2 = np.zeros((R.shape[0], len(res.params)))
        for num, j in pos.items():
            R2[:, j] = R[:, num - 1]
        b, V = res.params.to_numpy(), res.cov_params().to_numpy()
        F, fp, chi2, cp, m = _diag.wald_linear(b, V, R2, q, res.df_resid)
        table = pd.DataFrame({"제약(R·b − q)": R2 @ b - q, "표준오차": np.sqrt(np.diag(R2 @ V @ R2.T))},
                             index=pd.Index(list(restrictions), name="제약"))
        r = TestResult("Wald 계수 제약 검정", F, fp, null=" 그리고 ".join(restrictions),
                       rows={"χ² 통계량": chi2, "χ² p값": cp, "제약 수": m},
                       info={"제약 수": m, "공분산": res.cov_label}, table=table,
                       notes=["계수 번호: " + " · ".join(f"c({n})={labels[n]}" for n in sorted(pos))])
        return self._say(r)

    def chow(self, period) -> TestResult:
        """Chow 구조변화 검정 — period(예: '1995Q1')부터를 뒤 구간으로 놓고 두 구간의 계수가 같은지.

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> eq = wf.equation("eq_i").ls("I c Y(-1) R")
            >>> eq.chow("1995Q1").reject(0.05)
            False
        """
        eq, res = self._linear("Chow 검정")
        wf = self._wf
        p = int(period) if isinstance(period, (int, np.integer)) else wf._wt.index_of(period)
        when = wf.index[p]
        split = int(np.searchsorted(eq._y.index.values, np.datetime64(when)))
        return self._say(_diag.chow(eq._y.to_numpy(), eq._X.to_numpy(), split, wf._label(when)))

    def cusum(self, alpha: float = 0.95) -> TestResult:
        """CUSUM 안정성 검정 — 재귀 잔차의 누적합이 경계를 벗어나는가.

        통계량은 누적합이 경계에 가장 가까이 간 비율(1보다 작으면 경계 안 — 안정). 결과의 .graph는 그림, .data는 기간별 값.

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> eq = wf.equation("eq_i").ls("I c Y(-1) R")
            >>> r = eq.cusum()
            >>> bool(r.statistic < 1)
            True
        """
        eq, res = self._linear("CUSUM 검정")
        r = _diag.cusum(eq._y.to_numpy(), eq._X.to_numpy(), eq._y.index, alpha)
        r.graph = GraphOutput(r.data, title=f"{self.name} CUSUM ({int(alpha * 100)}% 경계)", name=f"{self.name}_cusum")
        return self._say(r)

    def recursive(self) -> pd.DataFrame:
        """재귀 계수 — 처음 k개 관측치로 시작해 한 기씩 늘려 추정한 계수(날짜 × 계수 DataFrame). 계수가 시간에 따라 안정한지 본다.

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> eq = wf.equation("eq_i").ls("I c Y(-1) R")
            >>> rc = eq.recursive()
            >>> list(rc.columns), round(float(rc["R"].iloc[-1]), 3)
            (['const', 'Y(-1)', 'R'], -0.963)
        """
        eq, res = self._linear("재귀 추정")
        r = _diag.recursive(eq._y.to_numpy(), eq._X.to_numpy())
        return pd.DataFrame(r["rparams"], index=eq._y.index, columns=list(eq.coef_names))

    def diagnostics(self, lags: int = 2) -> TableOutput:
        """표준 진단 한 표 — 계열상관 LM·White·Breusch-Pagan·Ljung-Box·ARCH·Jarque-Bera·RESET.

        OLS가 아니면 잔차 검정(Ljung-Box·ARCH·Jarque-Bera)만. 잔차가 사실상 0이면(완전 적합) 오류다.

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> eq = wf.equation("eq_i").ls("I c Y(-1) R")
            >>> t = eq.diagnostics()
            >>> list(t.data.columns)
            ['통계량', 'p값', '5%에서', '귀무가설']
        """
        eq = self._residuals_ok(self._ensure_fit(), "진단")
        e = eq._results.resid.to_numpy()
        tests = []
        if eq.method == "ols":
            X, y, f = eq._X.to_numpy(), eq._y.to_numpy(), eq._results.fittedvalues.to_numpy()
            tests += [(f"계열상관 LM({lags})", _diag.breusch_godfrey(e, X, lags)),
                      ("White(교차항)", _diag.white(e, X)), ("Breusch-Pagan-Godfrey", _diag.breusch_pagan(e, X))]
        tests += [(f"Ljung-Box Q({max(lags, 4)})", _diag.ljung_box(e, max(lags, 4))), ("ARCH LM(1)", _diag.arch_lm(e, 1)),
                  ("Jarque-Bera", _diag.jarque_bera(e))]
        if eq.method == "ols":
            tests.append(("RESET(1)", _diag.reset(y, X, f, 1)))
        df = pd.DataFrame({"통계량": [t.statistic for _, t in tests], "p값": [t.pvalue for _, t in tests],
                           "5%에서": ["기각" if t.reject() else "기각 못 함" for _, t in tests],
                           "귀무가설": [t.null for _, t in tests]}, index=pd.Index([n for n, _ in tests], name="검정"))
        foot = [] if eq.method == "ols" else [f"{eq.method.upper()} 식이라 잔차 검정만 했습니다"]
        return TableOutput(df, title=f"방정식 {self.name} 진단", foot=foot, name=f"{self.name}_diag")

    # ---- 결과 접근 (pandas) ---------------------------------------------
    def _require(self) -> Equation:
        if self.eq is None:
            raise RuntimeError(f"방정식 {self.name}이(가) 아직 추정되지 않았습니다 (.ls(...) 등).")
        return self.eq

    @property
    def method(self):
        """추정법: 'ols' · 'wls' · 'tsls' · 'gmm' · 'liml' · 'nls' · 'fixed'."""
        return self._require().method

    @property
    def dependent(self):
        """종속변수 표기(좌변 그대로, 예: 'dlog(P)')."""
        return self._require().dependent_var

    @property
    def target(self):
        """이 식이 결정하는 변수(목표변수) — 좌변의 첫 변수(예: 'dlog(P)'의 'P'). 모델의 내생변수가 된다."""
        return self._require().target

    def _coef_series(self, key):
        eq = self._require()
        rr = eq.regression_results.get(key, {})
        return pd.Series([rr.get(n, np.nan) for n in eq.coef_names], index=eq.coef_names, dtype=float)

    @property
    def coefs(self) -> pd.Series:
        """계수(pandas Series, 이름 = 항 — 상수항은 'const')."""
        return self._coef_series("coefficients")

    @property
    def stderrs(self) -> pd.Series:
        """계수 표준오차(Series). 공분산은 추정 때 고른 것(cov)."""
        return self._coef_series("std_errors")

    @property
    def tstats(self) -> pd.Series:
        """계수의 t값(Series)."""
        return self._coef_series("t_values")

    @property
    def pvalues(self) -> pd.Series:
        """계수 = 0 검정의 p값(Series, t 분포)."""
        return self._coef_series("p_values")

    @property
    def stats(self) -> dict:
        """통계 사전 — r_squared · adj_r_squared · se_regression · durbin_watson · log_likelihood · aic · bic · f_statistic ·
        n_obs 등(추정법별 항목 추가: j_statistic · liml_kappa · collinear …). 항목 설명은 docs/reference/outputs.md.
        """
        return dict(self._require().statistics)

    @property
    def resid(self) -> pd.Series:
        """잔차(표본 기간 Series) = 실측 − 적합값."""
        r = self._require().residuals
        return r.copy() if r is not None else pd.Series(dtype=float)

    @property
    def actual(self) -> pd.Series:
        """종속변수(좌변 식 그대로, 예: log(RCPSA))의 전 기간 값."""
        return self._require().dependent_series()

    @property
    def fitted(self) -> pd.Series:
        """적합값(표본 기간 Series)."""
        r = self.resid
        return (self.actual.loc[r.index] - r).rename("fitted")

    @property
    def results(self):
        """추정 결과 객체(equion.stats.Results) — params·bse·tvalues·pvalues·resid·cov_params()·set_cov()."""
        return self._require()._results

    @property
    def nobs(self) -> int:
        """추정에 쓴 관측치 수."""
        return int(self.stats.get("n_obs", 0))

    # ---- 출력 ------------------------------------------------------------
    def output(self) -> TableOutput:
        """결과표(TableOutput — .text() · .html() · .data). `eqn.show(eq)`가 보이는 것과 같다."""
        eq = self._require()
        p = self.pvalues
        df = pd.DataFrame({"계수": self.coefs, "표준오차": self.stderrs, "t값": self.tstats,
                           "p값": p, "": [_stars(v) for v in p]})
        df.index.name = "변수"
        res = eq.residuals
        wf = self._wf
        span = (f"{wf._label(res.index[0])} ~ {wf._label(res.index[-1])}" if res is not None and len(res)
                else "-")
        head = [f"종속변수: {eq.dependent_var}   목표변수: {eq.target}   추정법: {_METHOD_LABEL.get(eq.method, eq.method)}",
                f"표본: {span} (관측치 {self.nobs})"]
        if eq.instruments:
            head.append("도구변수: " + " ".join(eq.instruments))
        st = eq.statistics
        if eq.method == "wls":
            head.append(f"가중치: {eq.weights_expr} ({_WTYPE_LABEL.get(eq.wtype, eq.wtype)}) — 아래 통계는 가중 잔차 기준")
        if eq.method == "gmm" and eq._results is not None:
            head.append(f"{eq._results.cov_label}")
        if eq.ar_lags:
            head.append(f"오차: AR({', '.join(map(str, eq.ar_lags))}) — 조건부 최소제곱(통계는 εₜ 기준)")
        if st.get("cov_type", "nonrobust") != "nonrobust":
            head.append(f"계수 공분산: {st.get('cov_label')}")
        f = lambda k, d=4: ("NA" if st.get(k) is None or not np.isfinite(st.get(k, np.nan))
                            else f"{st[k]:.{d}f}")
        foot = [f"R² {f('r_squared')}   조정 R² {f('adj_r_squared')}   회귀 표준오차 {f('se_regression', 5)}"
                f"   DW {f('durbin_watson', 3)}",
                f"로그우도 {f('log_likelihood', 2)}   AIC {f('aic', 2)}   BIC {f('bic', 2)}"
                + (f"   F {f('f_statistic', 2)} (p={f('f_pvalue')})" if np.isfinite(st.get('f_statistic', np.nan)) else "")]
        if "r_squared_uncentered" in st:
            foot.append(f"(상수항 없음 — 비중심 R² {f('r_squared_uncentered')})")
        if "j_statistic" in st:
            foot.append(f"Hansen J {f('j_statistic')} (자유도 {st.get('j_df')}, p={f('j_pvalue')}) — 과대식별 제약이 맞는가")
        if "ar_inverted_roots" in st:
            roots = ", ".join(f"{a:.3f}" + (f"{b:+.3f}i" if abs(b) > 1e-12 else "") for a, b in st["ar_inverted_roots"])
            foot.append(f"역 AR 근: {roots}" + ("" if st.get("ar_stationary", True) else "  ⚠ 단위원 밖 — 비정상 AR"))
            if st.get("ar_note"):
                foot.append(f"참고: {st['ar_note']}")
        if "liml_kappa" in st:
            foot.append(f"LIML κ {f('liml_kappa', 6)}")
        if "unweighted_r_squared" in st:
            foot.append(f"가중 전: R² {f('unweighted_r_squared')}   SSR {f('unweighted_ssr', 5)}   DW {f('unweighted_durbin_watson', 3)}")
        if eq.pdl_terms:
            foot.append("PDL 시차별 계수: .lag_distribution()")
        if st.get("collinear"):
            foot.append(f"⚠ 회귀변수가 선형 종속입니다({', '.join(st['collinear'])}) — 계수·표준오차가 유일하지 않습니다(최소 노름 해)")
        if np.isfinite(st.get("wald_f_statistic", np.nan)):
            foot.append(f"강건 Wald F(상수항 외 계수 = 0) {f('wald_f_statistic', 2)} (p={f('wald_f_pvalue')})")
        foot.append("유의수준: *** 1%  ** 5%  * 10%")
        return TableOutput(df, title=f"방정식 {self.name}", head=head, foot=foot, name=self.name)

    def show(self):
        """결과표를 보인다(`eqn.show(eq)`와 같다)."""
        spool.show(self.output())

    def _repr_html_(self):
        return self.output().html() if self.eq is not None else None

    # ---- 단일식 예측 -----------------------------------------------------
    def forecast(self, name: str = None, start=None, end=None, mode: str = "dynamic") -> pd.Series:
        """이 식 하나만 풀어 목표변수를 예측한다(다른 변수는 실측·워크파일 값). 결과는 시리즈로 워크파일에 쓴다.

        매개변수
            name: 결과 시리즈 이름(기본: 목표변수 + 'F')
            start, end: 구간(기본: 표본)
            mode: 'dynamic'(종속변수 시차에 예측값) · 'static'(시차에 실측)

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> eq = wf.equation("eq_i").ls("I c Y(-1) R")
            >>> f = eq.forecast(start="2015Q1", end="2019Q4")
            >>> f.name, int(f.notna().sum())
            ('IF', 20)
        """
        eq = self._require()
        wf = self._wf
        s, e = wf._bounds(start, end)

        def run():
            m = Model(wf._data, [eq])
            m.wt = wf._wt
            return m.simulate(s, e, mode=mode, verbose=False)
        sim = quiet(run)
        out = name or f"{eq.target}F"
        wf._write_range(out, sim.values[eq.target].to_numpy(dtype=float), s, e)
        c = sim.counts()
        say(f"[{self.name}] {mode} 예측 → {out} ({wf._label(wf.data.index[s])}~{wf._label(wf.data.index[e])}"
            f", 정상 {c['ok']} · 일부 제외 {c['partial']} · 실패 {c['fallback'] + c['failed']})")
        return wf[out]


# ===========================================================================
# 모델 분석 결과 보기
# ===========================================================================
class StabilityView:
    """ModelObject.stability() 결과: .eigenvalues·.max_modulus·.stable·.verdict('안정'·'단위근'·'불안정')·.loadings,
    .output(top)/.show()."""

    def __init__(self, model_name, result):
        self.model, self.r = model_name, result

    def __getattr__(self, k):
        return getattr(self.__dict__["r"], k)

    def __repr__(self):
        return f"<안정성 {self.model} {self.r.period}: 최대 |λ| = {self.r.max_modulus:.4f} ({self.r.verdict})>"

    def output(self, top: int = 15) -> TableOutput:
        """고윳값 표(가장 큰 top개)와 판정·가장 큰 근과 함께 움직이는 변수."""
        r = self.r
        ev = r.eigenvalues[:top]
        df = pd.DataFrame({"실수부": ev.real, "허수부": ev.imag, "모듈러스": np.abs(ev)},
                          index=pd.RangeIndex(1, len(ev) + 1, name="순위"))
        head = [f"선형화 시점 {r.period} · {'상대 편차' if r.measure == 'relative' else '수준 편차'} · "
                f"내생변수 {len(r.variables)} · 최대 시차 {r.max_lag} · 근 {len(r.eigenvalues)}개",
                f"최대 |λ| = {r.max_modulus:.4f} → " + {
                    "안정": "안정(편차가 줄어든다)",
                    "단위근": f"단위근 {r.unit_roots}개 — 1보다 큰 근은 없다(수준이 적분된 변수: 편차가 줄지도 커지지도 않음)",
                    "불안정": f"⚠ 불안정 — 1보다 큰 근 {r.explosive}개(편차가 커진다)"}[r.verdict]]
        foot = []
        if r.loadings is not None:
            top = [(k, v) for k, v in r.loadings.head(6).items() if v >= 0.005]     # 0%로 반올림되는 변수는 보이지 않는다
            foot.append("가장 큰 근과 함께 움직이는 변수: " + ", ".join(f"{k} {v:.0%}" for k, v in top))
        foot.append("수준 경로가 적분된 변수(예: 차분식의 목표)는 근 1을 가진다 — 정상 여부는 1보다 큰 근으로 판단")
        return TableOutput(df, title=f"모델 {self.model} 동태 안정성", head=head, foot=foot, name=f"{self.model}_stability")

    def show(self):
        """고윳값 표를 보인다."""
        spool.show(self.output())

    def _repr_html_(self):
        return self.output().html()


class DecompositionView:
    """ModelObject.decompose() 결과: .table(var)(DataFrame)·.output(var)·.graph(var)·.show()·.total·.drivers."""

    def __init__(self, model_obj, d, scenario, base):
        self._m, self.d, self.scenario, self.base = model_obj, d, scenario, base

    @property
    def drivers(self):
        """분해한 시나리오 항목의 이름 목록."""
        return list(self.d.drivers)

    @property
    def total(self) -> pd.DataFrame:
        """변수별 전체 차이(시나리오 − 기준선) DataFrame."""
        return self._labelled(self.d.total)

    def _labelled(self, df):
        out = df.copy()
        out.index = pd.Index([self._m._wf._label(i) for i in out.index], name="기간")
        return out

    def table(self, var: str) -> pd.DataFrame:
        """한 변수의 항목별 기여도와 합계 표(DataFrame, 행 = 기간 라벨)."""
        return self._labelled(self.d.table(var))

    def output(self, var: str = None) -> TableOutput:
        """한 변수(기본: 첫 변수)의 기여도 표(TableOutput)."""
        var = var or list(self.d.contributions)[0]
        how = "Shapley(모든 부분집합 평균 — 합이 정확히 전체)" if self.d.method == "shapley" else "하나씩 + 상호작용"
        return TableOutput(self.table(var), title=f"{var}: {self.scenario} − {self.base} 기여도",
                           head=[f"분해 {how} · 항목 {len(self.drivers)} · 풀이 {self.d.runs}회"],
                           name=f"{self._m.name}_decomp_{var}")

    def graph(self, var: str = None) -> GraphOutput:
        """한 변수의 기여도 쌓은 막대 그림(GraphOutput)."""
        var = var or list(self.d.contributions)[0]
        df = self.d.contributions[var]
        return GraphOutput(df, title=f"{var}: {self.scenario} − {self.base} 기여도", kind="stacked",
                           name=f"{self._m.name}_decomp_{var}_g")

    def show(self):
        """모든 변수의 기여도 표를 보인다."""
        for v in self.d.contributions:
            spool.show(self.output(v))

    def _repr_html_(self):
        return self.output().html()


# ===========================================================================
# 오차수정모형 결과
# ===========================================================================
class ECMResult:
    """wf.ecm(...)의 결과. .shortrun(방정식 객체 — 모델에 넣는 식) · .longrun_eq · .coint(Engle-Granger 검정) ·
    .longrun()(장기 계수 표) · .adjustment(조정 속도 α) · .half_life · .output()/.show()."""

    kind = "ecm"

    def __init__(self, wf, name, method, y, xs, shortrun: EquationObject, longrun_eq: EquationObject,
                 coint: TestResult, const: bool = True):
        self._wf, self.name, self.method, self.y, self.xs = wf, name, method, y, list(xs)
        self.shortrun, self.longrun_eq, self.coint, self.const = shortrun, longrun_eq, coint, const

    def __repr__(self):
        return f"<오차수정모형 {self.name} ({self.method}): α = {self.adjustment['계수']:.4f}>"

    def _pick(self, idx: List[int], names: List[str], eq: EquationObject) -> pd.DataFrame:
        c, s, t, p = (getattr(eq, k).iloc[idx].to_numpy() for k in ("coefs", "stderrs", "tstats", "pvalues"))
        return pd.DataFrame({"계수": c, "표준오차": s, "t값": t, "p값": p}, index=pd.Index(names, name="변수"))

    def longrun(self) -> pd.DataFrame:
        """장기 관계 y = a + b·x의 계수(two-step은 장기 OLS — 표준오차는 참고용, nls는 NLS 표준오차)."""
        names = (["상수"] if self.const else []) + self.xs
        if self.method == "nls":
            return self._pick(list(range(1, 1 + len(names))), names, self.shortrun)
        return self._pick(list(range(len(names))), names, self.longrun_eq)

    @property
    def adjustment(self) -> pd.Series:
        """조정 속도 α(EC(-1)의 계수 — 음수이고 |α| < 2여야 균형으로 돌아간다)."""
        i = 0 if self.method == "nls" else (1 if self.const else 0) + len(self.xs)
        return self._pick([i], ["α"], self.shortrun).iloc[0]

    @property
    def half_life(self) -> float:
        """균형 이탈이 절반으로 주는 기간 수 ln(0.5)/ln(1+α) (−1 < α < 0일 때)."""
        a = float(self.adjustment["계수"])
        return float(np.log(0.5) / np.log(1 + a)) if -1 < a < 0 else float("nan")

    def output(self) -> TableOutput:
        """장기 계수 표와 조정 속도·반감기·공적분 검정."""
        a = self.adjustment
        lab = "Engle-Granger 두 단계" if self.method == "two-step" else "한 번에(NLS)"
        head = [f"오차수정모형({lab}) — 단기식 방정식 객체 '{self.shortrun.name}'"
                + (f", 장기식 '{self.longrun_eq.name}'" if self.method == "two-step" else ""),
                f"장기 관계: {self.y} = " + (" + ".join((["a"] if self.const else []) + [f"b·{x}" for x in self.xs])),
                f"조정 속도 α = {a['계수']:.4f} (표준오차 {a['표준오차']:.4f}, t {a['t값']:.2f}, p {a['p값']:.4f})"
                + (f" · 반감기 {self.half_life:.1f}기" if np.isfinite(self.half_life) else "")]
        foot = []
        if self.coint is not None:
            foot.append(f"Engle-Granger 공적분: τ {self.coint.statistic:.4f}, p {self.coint.pvalue:.4f} "
                        "(귀무가설: 공적분 없음)")
        if self.method == "two-step":
            foot.append("두 단계의 장기 계수 표준오차는 초일치 추정이라 통상의 t 검정에 쓰지 않는다 — 추론은 method='nls'로")
        return TableOutput(self.longrun(), title=f"오차수정모형 {self.name} — 장기 계수", head=head, foot=foot,
                           name=f"{self.name}_ecm")

    def show(self):
        """결과 표를 보인다."""
        spool.show(self.output())

    def _repr_html_(self):
        return self.output().html()


# ===========================================================================
# 시나리오
# ===========================================================================
class ScenarioObject:
    """모델의 시나리오 — 결과는 별칭(alias)을 붙인 시리즈로 워크파일에 쓰인다(D4)."""

    def __init__(self, model_obj, name: str, alias: str):
        self._m = model_obj
        self.name = name
        self.alias = alias
        self._sc = Scenario(name, alias)

    def __repr__(self):
        sc = self._sc
        parts = []
        if sc.exo_overrides:
            parts.append(f"override {list(sc.exo_overrides)}")
        if sc.excludes:
            parts.append(f"exclude {list(sc.excludes)}")
        if sc.add_factors or sc.add_factor_inits:
            parts.append("조정항")
        if sc.shocks:
            parts.append(f"충격 {len(sc.shocks)}")
        if sc.controls:
            parts.append(f"control {len(sc.controls)}")
        return f"<시나리오 {self.name} ({self.alias}){': ' + ', '.join(parts) if parts else ''}>"

    def _path(self, path):
        if isinstance(path, str) and path in self._m._wf:
            return self._m._wf[path]
        return path

    def override(self, var: str, path):
        """외생변수의 경로를 바꾼다(주지 않은 기간은 실측). path: Series · {기간: 값} · 스칼라 · 워크파일 시리즈 이름.

        exclude한 내생변수에 주면 그 고정 경로가 되고, exclude하지 않은 내생변수에 주면 풀이 구간 밖의 값(초기 시차)으로만 쓰인다.

        돌려주는 것
            이 시나리오(이어 부르기)

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> eq_i = wf.equation("eq_i").ls("I c Y(-1) R")
            >>> eq_cn = wf.equation("eq_cn").tsls("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
            >>> m = wf.model("toy").merge(eq_i, eq_cn).append("Y = CN + I + G")
            >>> sc = m.scenario("hi_g").override("G", wf["G"] * 1.1)
            >>> _ = m.solve("2010Q1", "2010Q4")
            >>> bool(wf.elem("Y_1", "2010Q1") > wf.elem("Y", "2010Q1"))
            True
        """
        self._sc.override(var, self._path(path))
        return self

    def exclude(self, var: str, start=None, end=None):
        """내생변수를 식 대신 실측(또는 override 경로)으로 고정한다. start·end를 주면 그 구간만.

        오류
            SimulationError: 내생변수가 아님(풀 때)

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> eq_i = wf.equation("eq_i").ls("I c Y(-1) R")
            >>> eq_cn = wf.equation("eq_cn").tsls("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
            >>> m = wf.model("toy").merge(eq_i, eq_cn).append("Y = CN + I + G")
            >>> _ = m.scenario("fix_i").exclude("I")
            >>> r = m.solve("2010Q1", "2010Q4")
            >>> bool((r.values["I"] == wf["I"].loc[r.values.index]).all())
            True
        """
        self._sc.exclude(var, start, end)
        return self

    def add_factor(self, var: str, path):
        """식의 조정항(좌변 단위)을 더한다. var: 방정식 객체 이름 · 종속변수 표기(`dlog(P)`) · 목표변수. path는 override와 같다.

        오류
            ValueError: 해당 추정식이 없음(항등식 변수에는 조정항을 줄 수 없다)

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> eq_i = wf.equation("eq_i").ls("I c Y(-1) R")
            >>> eq_cn = wf.equation("eq_cn").tsls("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
            >>> m = wf.model("toy").merge(eq_i, eq_cn).append("Y = CN + I + G")
            >>> _ = m.scenario("af").add_factor("eq_cn", -5.0)
            >>> _ = m.solve("2010Q1", "2010Q1")
            >>> bool(wf.elem("CN_1", "2010Q1") < wf.elem("CN", "2010Q1"))
            True
        """
        self._sc.add_factor(self._m._eq_key(var), self._path(path))
        return self

    def init_add_factor(self, var: str, base):
        """base 시점의 식 잔차를 조정항으로 그 뒤 기간에 이어 붙인다 — 전망이 실측에서 매끄럽게 출발하게('착지').

        오류
            SimulationError: 해당 추정식이 없거나 그 시점 잔차를 계산할 수 없음

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> eq_i = wf.equation("eq_i").ls("I c Y(-1) R")
            >>> eq_cn = wf.equation("eq_cn").tsls("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
            >>> m = wf.model("toy").merge(eq_i, eq_cn).append("Y = CN + I + G")
            >>> sc = m.scenario("landed").init_add_factor("eq_cn", "2009Q4")
            >>> m.solve("2010Q1", "2010Q4").counts()["ok"]
            4
        """
        self._sc.init_add_factor(self._m._eq_key(var), base)
        return self

    def shock(self, var: str, value: float, start, end=None, kind: str = "level"):
        """충격 — 외생변수면 경로를(kind='level' 더하기 · 'pct' %), 추정식의 목표변수면(또는 kind='add_factor') 식 조정항을 바꾼다.

        end를 주지 않으면 한 기간. 같은 변수에 여러 번 주면 차례로 더해진다.

        오류
            ValueError: kind가 틀림 · SimulationError: 항등식 변수, 모델에 없는 변수

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> eq_i = wf.equation("eq_i").ls("I c Y(-1) R")
            >>> eq_cn = wf.equation("eq_cn").tsls("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
            >>> m = wf.model("toy").merge(eq_i, eq_cn).append("Y = CN + I + G")
            >>> _ = m.scenario("g5").shock("G", 5, "2015Q1")
            >>> _ = m.solve("2015Q1", "2015Q1")
            >>> round(wf.elem("Y_1", "2015Q1") - wf.elem("Y", "2015Q1"), 1) > 5
            True
        """
        self._sc.shock(self._m._eq_key(var) if kind == "add_factor" else var, value, start, end, kind)
        return self

    def control(self, target: str, instrument: str, path):
        """이 시나리오에 목표 추적을 넣는다 — 풀 때 target 경로를 맞추도록 instrument(외생)를 함께 푼다.

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> eq_i = wf.equation("eq_i").ls("I c Y(-1) R")
            >>> eq_cn = wf.equation("eq_cn").tsls("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
            >>> m = wf.model("toy").merge(eq_i, eq_cn).append("Y = CN + I + G")
            >>> _ = m.scenario("tgt").control("Y", "G", 600.0)
            >>> r = m.solve("2010Q1", "2010Q2")
            >>> r.values["Y"].round(6).tolist()
            [600.0, 600.0]
        """
        self._sc.control(target, instrument, self._path(path))
        return self

    def use_residuals(self, on: bool = True):
        """표본 안의 추정 잔차를 모든 추정식의 조정항으로 더한다 — 항등식이 자료에서 성립하면 과거를 그대로 재현한다(모델 점검용).

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> eq_i = wf.equation("eq_i").ls("I c Y(-1) R")
            >>> eq_cn = wf.equation("eq_cn").tsls("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
            >>> m = wf.model("toy").merge(eq_i, eq_cn).append("Y = CN + I + G")
            >>> _ = m.scenario("replay").use_residuals()
            >>> r = m.solve("2010Q1", "2019Q4")
            >>> float((r.values["Y"] / wf["Y"].loc[r.values.index] - 1).abs().max()) < 1e-8
            True
        """
        self._sc.use_residuals(on)
        return self

    def clear(self):
        """설정을 모두 지운다(이름·별칭은 그대로).

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> eq_i = wf.equation("eq_i").ls("I c Y(-1) R")
            >>> eq_cn = wf.equation("eq_cn").tsls("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
            >>> m = wf.model("toy").merge(eq_i, eq_cn).append("Y = CN + I + G")
            >>> sc = m.scenario("tmp").override("G", 1.0)
            >>> sc.clear()
            <시나리오 tmp (_1)>
        """
        self._sc = Scenario(self.name, self.alias)
        return self


@dataclass
class SolveResult:
    model: str
    scenario: str
    alias: str
    sim: SimulationResult
    start: str
    end: str
    engine: Optional[Model] = field(default=None, repr=False)

    @property
    def values(self) -> pd.DataFrame:
        """풀린 내생변수 값(DataFrame, 행 = 풀이 기간)."""
        return self.sim.values

    def counts(self) -> Dict[str, int]:
        """기간 상태 수 {'ok', 'partial', 'fallback', 'failed'}."""
        return self.sim.counts()

    def status(self) -> pd.DataFrame:
        """기간별 상태 표 — status · iterations · max_resid(정규화 잔차) · methods · excluded(빠진 식과 이유) · fallback · message."""
        return self.sim.status_frame()

    def output(self) -> TableOutput:
        """상태 표(TableOutput)."""
        df = self.status()
        cols = [c for c in ("status", "iterations", "max_resid", "excluded", "fallback", "message") if c in df.columns]
        c = self.counts()
        head = [f"모델 {self.model} · 시나리오 {self.scenario} ({self.alias}) · {self.sim.mode} · {self.start}~{self.end}",
                f"정상 {c['ok']} · 일부식 제외 {c['partial']} · 실패대체 {c['fallback']} · 실패 {c['failed']}"]
        return TableOutput(df[cols], title="풀이 상태", head=head, name=f"{self.model}{self.alias}")

    def show(self):
        """상태 표를 보인다."""
        spool.show(self.output())

    def _repr_html_(self):
        return self.summary(10).html()

    def _store(self, hs_id: str = None) -> str:
        hid = hs_id or f"{self.model}{self.alias}"
        m = self.engine
        m._store_result(hid, self.sim)
        m.hs_statistics[hid] = m._calculate_hs_statistics(hid, self.sim.start, self.sim.end)
        return hid

    def statistics(self) -> pd.DataFrame:
        """변수별 적합도(실측 대비 RMSPE·MAE 등, 실측 대체·제외 기간은 뺌) — RMSPE 오름차순."""
        hid = self._store()
        st = pd.DataFrame(self.engine.hs_statistics[hid]).T
        if "n_samples" in st.columns:
            st["n_samples"] = st["n_samples"].astype(int)
        return st.sort_values("RMSPE") if len(st) else st

    def summary(self, top: int = 10) -> TableOutput:
        """적합도 상위 top개 표(RMSPE·MAE 등 — 실측 대체·제외 기간은 뺀다). 0 근처 계열은 RMSPE가 과대하니 MAE도 본다."""
        st = self.statistics()
        cols = [c for c in ("RMSPE", "MAE_pct", "MAE", "mean_error", "n_samples") if c in st.columns]
        c = self.counts()
        return TableOutput(st[cols].head(top), title=f"적합도 상위 {top} — {self.model}·{self.scenario}({self.alias})",
                           name=f"{self.model}{self.alias}_fit",
                           head=[f"{self.start}~{self.end} · 정상 {c['ok']} · 일부식 제외 {c['partial']} · "
                                 f"실패대체 {c['fallback']} · 실패 {c['failed']}"],
                           foot=["※ 0 근처 계열(잔액·금리)은 RMSPE가 과대 — MAE(수준)도 함께 보세요"])

    def save(self, path: str = None, hs_id: str = None) -> str:
        """결과를 기존 HS CSV 형식(기간별 상태 열 포함)으로 저장한다. 기본: HS/<hs_id>_results_<시작>_<끝>.csv"""
        hid = self._store(hs_id)
        out = quiet(self.engine.save_hs_results, hid, path)
        record_output(out, "solve")
        return out

    def __repr__(self):
        c = self.counts()
        return (f"<풀이 {self.model}·{self.scenario}({self.alias}) {self.start}~{self.end}: "
                f"정상 {c['ok']}·일부 {c['partial']}·대체 {c['fallback']}·실패 {c['failed']}>")


# ===========================================================================
# 모델
# ===========================================================================
class ModelObject:
    """이름 붙은 연립방정식 모델 — 방정식 객체를 merge, 항등식을 append, 시나리오별로 solve."""

    kind = "model"

    def __init__(self, wf, name: str):
        self._wf = wf
        self.name = name
        self._eq_names: List[str] = []
        self._identities: List[str] = []
        self._scenarios: Dict[str, ScenarioObject] = {}
        self._active = "baseline"
        self._engine: Optional[Model] = None
        self._key = None
        self.last: Optional[SolveResult] = None
        self.version = 0
        self.scenario("baseline", alias="_0")

    def __repr__(self):
        return (f"<모델 {self.name}: 방정식 {len(self._eq_names)} · 항등식 {len(self._identities)} · "
                f"시나리오 {list(self._scenarios)} (활성 {self._active})>")

    # ---- 구성 ------------------------------------------------------------
    def merge(self, *items):
        """추정식을 모델에 더한다.

        받는 것: 방정식 객체 · 객체 이름 · 추정식 글자(그 자리에서 현재 표본으로 추정) · 방정식 파일 경로(한 줄에 한 식 — 추정식은
        추정하고 항등식은 그대로 더한다) · 시스템·VAR·VECM 객체(추정 계수를 고정한 식으로) · 그 목록.

        돌려주는 것
            이 모델 객체(이어 부르기)

        오류
            ValueError: 항등식을 merge(→ append) · MergeError: 파일의 식 추정 실패(줄 번호와 함께)

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> eq_i = wf.equation("eq_i").ls("I c Y(-1) R")
            >>> eq_cn = wf.equation("eq_cn").tsls("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
            >>> m = wf.model("toy").merge(eq_i, eq_cn).append("Y = CN + I + G")
            >>> m.endogenous
            ['CN', 'I', 'Y']
            >>> _ = m.merge("dlog(P) c dlog(Y) dlog(POIL)")
            >>> m.endogenous
            ['CN', 'I', 'P', 'Y']

        관련: append · drop
        """
        import os
        from ..formula.parser import is_identity
        from ..worktable.freq import parse_equation_file
        wf = self._wf
        for item in items:
            if isinstance(item, (list, tuple)):
                self.merge(*item)
                continue
            if isinstance(item, EquationObject):
                self._add_eq(item.name)
                continue
            if getattr(item, "kind", None) in ("system", "var", "vecm"):   # 시스템·VAR·VECM → 계수를 고정한 식들
                for obj in item.make_equations():
                    self._add_eq(obj.name)
                continue
            if not isinstance(item, str):
                raise TypeError(f"merge할 수 없는 대상: {item!r}")
            if item.lower() in wf._objects and isinstance(wf._objects[item.lower()], EquationObject):
                self._add_eq(wf._objects[item.lower()].name)
            elif os.path.isfile(item):
                est, ids = parse_equation_file(item)
                record_input(item, "equations")
                failed, n0 = [], len(self._eq_names)
                for k, line in enumerate(est, 1):
                    try:
                        obj = wf._new_equation_auto(line, loud=False)
                        self._add_eq(obj.name)
                    except Exception as e:  # noqa: BLE001
                        failed.append(f"  {k}. {line[:60]} — {str(e)[:120]}")
                self._identities.extend(ids)
                self._touch()
                say(f"[{self.name}] merge {os.path.basename(item)} — 추정식 {len(self._eq_names) - n0}"
                    f"/{len(est)} · 항등식 {len(ids)}")
                if failed:
                    raise MergeError("추정에 실패한 식이 있습니다:\n" + "\n".join(failed))
            elif is_identity(item):
                raise ValueError("항등식은 .append(...)로 넣으세요.")
            else:
                self._add_eq(wf._new_equation_auto(item).name)
        return self

    def append(self, *lines: str):
        """항등식을 더한다(계수 없이 늘 성립하는 식 — 좌변의 첫 변수가 목표변수). 여러 줄 글자도 되고 `#` 뒤는 주석.
        이미 있는 항등식(공백·대소문자 무시)은 다시 넣지 않는다.

        오류
            ValueError: 항등식이 아님(추정식은 merge)

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> m = wf.model("m1").merge("I c Y(-1) R", "CN c Y CN(-1)")
            >>> _ = m.append("Y = CN + I + G   # 국민소득")
            >>> m.identities
            ['Y = CN + I + G']
        """
        from ..formula.parser import is_identity
        for text in lines:
            for line in str(text).splitlines():
                line = line.split("#", 1)[0].strip()
                if not line:
                    continue
                if not is_identity(line):
                    raise ValueError(f"항등식이 아닙니다(추정식은 .merge): {line}")
                key = "".join(line.split()).lower()
                if any("".join(x.split()).lower() == key for x in self._identities):
                    continue                 # 같은 항등식은 한 번만(같은 셀·스크립트를 다시 돌려도 겹치지 않게)
                self._identities.append(line)
        self._touch()
        return self

    def drop(self, *names: str):
        """식을 뺀다 — 방정식 객체 이름 또는 항등식의 목표변수. 뺀 식의 목표변수는 외생(실측)이 된다.

        오류
            KeyError: 모델에 없는 이름

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> eq_i = wf.equation("eq_i").ls("I c Y(-1) R")
            >>> eq_cn = wf.equation("eq_cn").tsls("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
            >>> m = wf.model("toy").merge(eq_i, eq_cn).append("Y = CN + I + G")
            >>> _ = m.drop("eq_i")
            >>> m.endogenous, "I" in m.exogenous
            (['CN', 'Y'], True)
        """
        for nm in names:
            low = nm.lower()
            before = len(self._eq_names) + len(self._identities)
            self._eq_names = [n for n in self._eq_names if n.lower() != low]
            self._identities = [s for s in self._identities if s.split("=", 1)[0].strip().lower() != low]
            if len(self._eq_names) + len(self._identities) == before:
                raise KeyError(f"모델 {self.name}에 '{nm}'이(가) 없습니다.")
        self._touch()
        return self

    def _add_eq(self, name: str):
        if name.lower() not in (n.lower() for n in self._eq_names):
            self._eq_names.append(name)
        self._touch()

    def _touch(self):
        self.version += 1

    @property
    def equations(self) -> List[EquationObject]:
        """모델의 추정식(방정식 객체 목록)."""
        return [self._wf.obj(n) for n in self._eq_names]

    @property
    def identities(self) -> List[str]:
        """모델의 항등식(글자 목록)."""
        return list(self._identities)

    def _eq_key(self, var: str) -> str:
        """조정항 대상 → 엔진이 알아보는 키(종속변수 표기). 방정식 객체 이름도 받는다."""
        low = var.lower()
        for obj in self.equations:
            if obj.name.lower() == low:
                return obj.eq.dependent_var
        return var

    def _build(self) -> Model:
        objs = self.equations
        for o in objs:
            if o.eq is None:
                raise RuntimeError(f"방정식 {o.name}이(가) 추정되지 않았습니다.")
        key = (tuple((o.name, o.version) for o in objs), tuple(self._identities))
        if self._engine is None or key != self._key:
            wf = self._wf

            def build():
                m = Model(wf._data, [o.eq for o in objs])
                m.wt = wf._wt
                for s in self._identities:
                    m.add_identity(s)
                m.system  # 구조 검사(중복 정의·미지 변수)를 지금
                return m
            self._engine = quiet(build)
            self._key = key
        return self._engine

    @property
    def engine(self) -> Model:
        """엔진 Model 객체 — 고급 사용(직접 simulate 등)."""
        return self._build()

    @property
    def endogenous(self) -> List[str]:
        """내생변수 — 각 식의 목표변수(이름 순)."""
        return self._build().get_endogenous_variables()

    @property
    def exogenous(self) -> List[str]:
        """외생변수 — 식에 쓰였지만 어떤 식도 결정하지 않는 변수(이름 순). 지시자 열(@trend 등)도 포함."""
        return self._build().get_exogenous_variables()

    # ---- 보기 ------------------------------------------------------------
    def output(self) -> TableOutput:
        """식 목록 표(종류·이름·목표변수·추정법·식)."""
        rows = []
        for o in self.equations:
            rows.append({"종류": "추정식", "이름": o.name, "목표변수": o.eq.target if o.eq else "",
                         "추정법": o.eq.method if o.eq else "", "식": o.spec})
        for s in self._identities:
            rows.append({"종류": "항등식", "이름": "", "목표변수": s.split("=", 1)[0].strip(),
                         "추정법": "", "식": s})
        df = pd.DataFrame(rows, columns=["종류", "이름", "목표변수", "추정법", "식"])
        return TableOutput(df, title=f"모델 {self.name}", index=False, name=self.name,
                           head=[f"추정식 {len(self._eq_names)} · 항등식 {len(self._identities)}"])

    def show(self):
        """식 목록 표를 보인다."""
        spool.show(self.output())

    def _repr_html_(self):
        return self.output().html()

    def blocks(self) -> TableOutput:
        """블록 구조 표 — 함께 풀어야 하는 변수 묶음(동시 블록)과 풀이 순서(위에서부터).

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> eq_i = wf.equation("eq_i").ls("I c Y(-1) R")
            >>> eq_cn = wf.equation("eq_cn").tsls("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
            >>> m = wf.model("toy").merge(eq_i, eq_cn).append("Y = CN + I + G")
            >>> t = m.blocks()
            >>> t.data[["종류", "변수"]].values.tolist()
            [['순차', 'I'], ['동시', 'CN, Y']]
        """
        bl = self._build().block_structure()
        df = pd.DataFrame([{"블록": b["block"], "종류": "동시" if b["size"] > 1 else "순차",
                            "크기": b["size"],
                            "변수": ", ".join(b["variables"][:12]) + (" …" if b["size"] > 12 else "")}
                           for b in bl])
        sim = sum(1 for b in bl if b["size"] > 1)
        return TableOutput(df, title=f"모델 {self.name} 블록 구조", index=False, name=f"{self.name}_blocks",
                           head=[f"블록 {len(bl)}개 (동시 {sim}) — 위에서부터 풀이 순서"])

    def variables(self) -> pd.DataFrame:
        """변수 표(변수 · 구분 = 내생/외생).

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> eq_i = wf.equation("eq_i").ls("I c Y(-1) R")
            >>> eq_cn = wf.equation("eq_cn").tsls("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
            >>> m = wf.model("toy").merge(eq_i, eq_cn).append("Y = CN + I + G")
            >>> sorted(m.variables()["구분"].value_counts().items())
            [('내생', 3), ('외생', 2)]
        """
        m = self._build()
        endo, exo = m.get_endogenous_variables(), m.get_exogenous_variables()
        return pd.DataFrame({"변수": endo + exo, "구분": ["내생"] * len(endo) + ["외생"] * len(exo)})

    def gaps(self, start=None, end=None) -> pd.DataFrame:
        """입력 결측 진단 — 기간·식마다 비어 있는 입력(시차 포함). 풀이 때 그 기간 그 식은 빠진다(on_missing='exclude').

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> eq_i = wf.equation("eq_i").ls("I c Y(-1) R")
            >>> eq_cn = wf.equation("eq_cn").tsls("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
            >>> m = wf.model("toy").merge(eq_i, eq_cn).append("Y = CN + I + G")
            >>> g = m.gaps("1970Q1", "1970Q2")
            >>> g[["period", "target", "missing"]].values.tolist()
            [['1970Q1', 'I', 'Y(-1)'], ['1970Q1', 'CN', 'CN(-1)']]
        """
        s, e = self._wf._bounds(start, end)
        return self._build().input_gaps(s, e)

    # ---- 시나리오·풀이 -----------------------------------------------------
    def scenario(self, name: str = None, alias: str = None) -> ScenarioObject:
        """시나리오를 만들거나 고르고 **활성화**한다 — 이후 solve()는 활성 시나리오로 푼다. 인자 없이 부르면 활성 시나리오.

        기준선은 처음부터 있는 'baseline'(별칭 `_0`), 새 시나리오의 별칭은 `_1`, `_2` … 또는 alias로 정한다(이름은 대소문자 무시).

        오류
            ValueError: 별칭이 이미 다른 시나리오의 것

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> eq_i = wf.equation("eq_i").ls("I c Y(-1) R")
            >>> eq_cn = wf.equation("eq_cn").tsls("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
            >>> m = wf.model("toy").merge(eq_i, eq_cn).append("Y = CN + I + G")
            >>> sc = m.scenario("hi_g")
            >>> sc.alias, list(m.scenarios)
            ('_1', ['baseline', 'hi_g'])
            >>> m.scenario("baseline").alias
            '_0'

        관련: solve · ScenarioObject
        """
        if name is None:
            return self._scenarios[self._active]
        key = name.lower()
        if key not in self._scenarios:
            al = alias or ("_0" if key == "baseline" else f"_{len(self._scenarios)}")
            if not al.startswith("_"):
                al = "_" + al
            if any(s.alias == al for s in self._scenarios.values()):
                raise ValueError(f"별칭 {al}을(를) 이미 다른 시나리오가 씁니다.")
            self._scenarios[key] = ScenarioObject(self, name, al)
        self._active = key
        return self._scenarios[key]

    @property
    def scenarios(self) -> Dict[str, ScenarioObject]:
        """시나리오 {이름: ScenarioObject}."""
        return dict(self._scenarios)

    def _sc(self, scenario) -> ScenarioObject:
        if scenario is None:
            return self._scenarios[self._active]
        if isinstance(scenario, ScenarioObject):
            return scenario
        key = str(scenario).lower()
        if key not in self._scenarios:
            raise KeyError(f"시나리오 '{scenario}'이(가) 없습니다: {list(self._scenarios)}")
        return self._scenarios[key]

    def solve(self, start=None, end=None, mode: str = "dynamic", scenario=None, **opts) -> SolveResult:
        """활성(또는 지정) 시나리오로 풀고, 결과를 별칭 시리즈(예: Y_0)로 워크파일에 쓴다(구간 밖은 빈 칸).

        매개변수
            start, end: 구간(기본: 표본)
            mode: 'dynamic'(시차에 풀이 값) · 'static'(시차에 실측) · 'fit'(식마다 따로)
            scenario: 시나리오 이름(기본: 활성)
            **opts: method · fallback · tolerance · max_iterations · on_missing · on_fail · jacobian · mce · mce_method · terminal

        돌려주는 것
            SolveResult — .counts() · .status() · .statistics() · .summary() · .save()

        오류
            ValueError: 옵션 값이 틀림 · StructureError: 모델 구조(같은 변수를 두 식이 결정 등)

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> eq_i = wf.equation("eq_i").ls("I c Y(-1) R")
            >>> eq_cn = wf.equation("eq_cn").tsls("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
            >>> m = wf.model("toy").merge(eq_i, eq_cn).append("Y = CN + I + G")
            >>> r = m.solve("2010Q1", "2019Q4")
            >>> r.counts()
            {'ok': 40, 'partial': 0, 'fallback': 0, 'failed': 0}
            >>> round(wf.elem("Y_0", "2019Q4"), 1)
            624.9

        관련: forecast · scenario · docs/explain/solving.md
        """
        sc = self._sc(scenario)
        model = self._build()
        wf = self._wf
        s, e = wf._bounds(start, end)
        if model.system.max_lead > 0 and not (opts.get("mce") and mode == "dynamic"):
            from ..log import workfile as _wlog
            _wlog.warning(f"[WARN] 모델 {self.name}에 선행변수(X(1) 등)가 있습니다 — mce 없이 풀면(또는 정적·fit) 선행 값은 "
                          "실측·시나리오 경로로 고정됩니다. 모형 일관 기대는 mode='dynamic', mce=True")
        res = quiet(lambda: sc._sc.run(model, s, e, mode=mode, store=False, verbose=False, **opts))
        sim = res.sim
        wf._write_block({f"{v}{sc.alias}": sim.values[v].to_numpy(dtype=float) for v in sim.values.columns}, s, e)
        self.last = SolveResult(self.name, sc.name, sc.alias, sim,
                                wf._label(wf.data.index[s]), wf._label(wf.data.index[e]), engine=model)
        record_solve(self.last)
        c = sim.counts()
        say(f"[{self.name}] {sc.name}({sc.alias}) {mode} {self.last.start}~{self.last.end}: 정상 {c['ok']} · "
            f"일부식 제외 {c['partial']} · 실패대체 {c['fallback']} · 실패 {c['failed']}")
        return self.last

    def forecast(self, start, end, exog_fill: str = None, mode: str = "dynamic", scenario=None,
                 **opts) -> SolveResult:
        """전망 — 필요하면 기간을 늘리고, exog_fill로 외생 경로를 채운 뒤 푼다. 시작 앞 내생변수 실측과 외생 경로를 미리 진단한다.

        매개변수
            start, end: 전망 구간
            exog_fill: 비어 있는 외생을 채울 규칙 'last' · 'growth' · 'trend'(None이면 채우지 않음 — 비었으면 오류로 알려 준다)
            mode, scenario, **opts: solve와 같다

        오류
            ValueError: 외생 경로가 빔(무엇이 언제) · 시작 앞 내생변수 실측이 빔(채우는 법과 함께)

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> eq_i = wf.equation("eq_i").ls("I c Y(-1) R")
            >>> eq_cn = wf.equation("eq_cn").tsls("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
            >>> m = wf.model("toy").merge(eq_i, eq_cn).append("Y = CN + I + G")
            >>> r = m.forecast("2020Q1", "2020Q4", exog_fill="last")
            >>> r.counts()["ok"]
            4
        """
        wf = self._wf
        from ..data.periods import parse_period, to_period
        if parse_period(end, wf.freq) > to_period(wf.index[-1], wf.freq):
            wf.extend(end)
        model = self._build()
        if exog_fill:
            ind = set(wf._data.indicators)
            cols = [v for v in model.get_exogenous_variables() if v in wf.data.columns and v not in ind]
            quiet(wf._data.fill_series, cols, method=exog_fill)
        sc = self._sc(scenario)
        miss = missing_exogenous(model, wf._index_of(start), wf._index_of(end), sc._sc)
        if miss:
            lines = [f"{k}: {v[0]}~{v[-1]} ({len(v)}기)" for k, v in list(miss.items())[:12]]
            raise ValueError("전망 구간에 외생변수 값이 없습니다 — 시나리오 override, wf.fill(...), 또는 "
                             "exog_fill='last'|'growth'|'trend':\n  " + "\n  ".join(lines))
        if mode == "dynamic":
            hist = missing_history(model, wf._index_of(start), sc._sc)
            if hist:
                v0 = next(iter(hist))
                lines = [f"{k}: {', '.join(v[-3:])}" for k, v in list(hist.items())[:12]]
                raise ValueError("전망 시작 앞의 내생변수 실측이 비어 있어 첫 기간부터 풀 수 없습니다:\n  " + "\n  ".join(lines)
                                 + "\n  → 실측이 끝난 바로 다음 기간부터 전망하거나, 앞선 풀이 값을 실측 자리에 채우세요"
                                 f"(예: wf['{v0}'] = wf['{v0}'].fillna(wf['{v0}_0']))")
        return self.solve(start, end, mode=mode, scenario=scenario, **opts)

    def stochastic(self, start=None, end=None, reps: int = 100, seed: int = None, scenario=None, **kw):
        """확률적 모의 — 추정 잔차를 기간마다 다시 뽑아(식 사이 상관 보존) reps번 풀어 평균·표준편차·분위수 띠를 낸다.

        coef_uncertainty=True면 계수도 추정 분포에서 뽑는다. percentiles로 분위수를 고른다(기본 5·50·95).

        돌려주는 것
            StochasticResult — .mean · .std · .percentiles · .band(변수)

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> eq_i = wf.equation("eq_i").ls("I c Y(-1) R")
            >>> eq_cn = wf.equation("eq_cn").tsls("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
            >>> m = wf.model("toy").merge(eq_i, eq_cn).append("Y = CN + I + G")
            >>> s = m.stochastic("2018Q1", "2018Q4", reps=50, seed=1)
            >>> list(s.band("Y").columns)
            ['mean', 'std', 'p5', 'p50', 'p95']
        """
        s, e = self._wf._bounds(start, end)
        return quiet(stochastic_simulation, self._build(), s, e, reps=reps, seed=seed,
                     scenario=self._sc(scenario)._sc, verbose=False, **kw)

    def control(self, target: str, instrument: str, path, start=None, end=None, name: str = None,
                scenario=None, **kw) -> pd.Series:
        """목표 추적 — target(내생)이 path를 따르도록 instrument(외생)를 거꾸로 풀어 시리즈(기본 이름 instrument + '_C')로 쓴다.

        path는 Series·{기간: 값}·스칼라 — start~end 구간에만 쓰인다.

        오류
            SimulationError: instrument가 내생이거나 target이 instrument에 반응하지 않음

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> eq_i = wf.equation("eq_i").ls("I c Y(-1) R")
            >>> eq_cn = wf.equation("eq_cn").tsls("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
            >>> m = wf.model("toy").merge(eq_i, eq_cn).append("Y = CN + I + G")
            >>> g = m.control("Y", "G", 600.0, "2010Q1", "2010Q4")
            >>> g.name, round(wf.elem("G_C", "2010Q1"), 1)
            ('G_C', 76.4)
        """
        wf = self._wf
        s, e = wf._bounds(start, end)
        path = self._sc(scenario)._path(path)
        sim = quiet(control_simulation, self._build(), target, instrument, path, s, e,
                    scenario=self._sc(scenario)._sc, verbose=False, **kw)
        out = name or f"{instrument}_C"
        wf._write_range(out, sim.values[instrument].to_numpy(dtype=float), s, e)
        say(f"[{self.name}] control {target} ← {instrument} → {out}")
        return wf[out]

    def multipliers(self, var: str, shock: float, start=None, end=None, scenario=None, **kw):
        """충격 승수 — var(외생)를 shock만큼 바꿨을 때 내생변수의 기간별 반응(충격 − 기준선).

        kind='level'(더하기) · 'pct'(%), permanent=False면 첫 기간만 충격. 내생변수를 주면 그 식의 조정항에 더한다.

        돌려주는 것
            MultiplierResult — .level(수준 차) · .pct(% 차) · .baseline · .shocked

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> eq_i = wf.equation("eq_i").ls("I c Y(-1) R")
            >>> eq_cn = wf.equation("eq_cn").tsls("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
            >>> m = wf.model("toy").merge(eq_i, eq_cn).append("Y = CN + I + G")
            >>> mu = m.multipliers("G", 1.0, "2015Q1", "2015Q4")
            >>> round(float(mu.level["Y"].iloc[0]), 2)
            2.13
        """
        s, e = self._wf._bounds(start, end)
        return quiet(multipliers, self._build(), var, shock, s, e, scenario=self._sc(scenario)._sc, **kw)

    # ---- 분석: 안정성·기여도 ------------------------------------------------
    def _solved_values(self, scenario) -> Optional[pd.DataFrame]:
        """시나리오를 풀어 둔 별칭 시리즈(X_0 …)가 있으면 내생변수 이름의 DataFrame으로."""
        if scenario is None:
            return None
        sc = self._sc(scenario)
        wf = self._wf
        cols = {v: f"{v}{sc.alias}" for v in self._build().get_endogenous_variables()}
        have = {v: c for v, c in cols.items() if wf._col(c)}
        if not have:
            raise ValueError(f"시나리오 {sc.name}을(를) 먼저 푸세요(.solve(scenario=…)) — 그 값에서 선형화합니다")
        return pd.DataFrame({v: wf[c] for v, c in have.items()}, index=wf.data.index)

    def stability(self, period=None, scenario=None, measure: str = "relative"):
        """동태 안정성 — period(기본: 표본 끝)의 값에서 선형화한 모델의 동반행렬 고윳값.

        모든 근이 1보다 작으면 그 근처의 편차가 줄어든다(안정). 1인 근만 있으면 '단위근'(차분식처럼 수준이 적분된 변수),
        1보다 큰 근이 있으면 '불안정'. scenario를 주면 그 풀이 값에서 선형화한다. 선행변수가 있는 모델은 쓸 수 없다.

        매개변수
            measure: 'relative'(양수 변수는 상대 편차 — 로그식이 성장률만큼 부풀지 않음) · 'level'

        돌려주는 것
            StabilityView — .eigenvalues · .max_modulus · .verdict · .loadings(가장 큰 근과 함께 움직이는 변수) · .output()

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> eq_i = wf.equation("eq_i").ls("I c Y(-1) R")
            >>> eq_cn = wf.equation("eq_cn").tsls("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
            >>> m = wf.model("toy").merge(eq_i, eq_cn).append("Y = CN + I + G")
            >>> st = m.stability("2010Q1")
            >>> st.verdict, round(st.max_modulus, 2)
            ('안정', 0.76)
        """
        from ..system.analysis import stability as _stab
        wf = self._wf
        t = wf._bounds(None, None)[1] if period is None else wf._index_of(period)
        r = _stab(self._build(), t, self._solved_values(scenario), measure)
        return StabilityView(self.name, r)

    def stability_path(self, start=None, end=None, scenario=None, measure: str = "relative") -> pd.DataFrame:
        """기간마다 가장 큰 근의 모듈러스·1 이상인 근의 수·판정(행 = 기간 라벨).

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> eq_i = wf.equation("eq_i").ls("I c Y(-1) R")
            >>> eq_cn = wf.equation("eq_cn").tsls("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
            >>> m = wf.model("toy").merge(eq_i, eq_cn).append("Y = CN + I + G")
            >>> p = m.stability_path("2010Q1", "2010Q4")
            >>> list(p.columns)
            ['최대 모듈러스', '1 이상인 근', '안정', '판정']
        """
        from ..system.analysis import stability as _stab
        wf = self._wf
        s, e = wf._bounds(start, end)
        model, vals = self._build(), self._solved_values(scenario)
        rows = []
        for t in range(s, e + 1):
            try:
                r = _stab(model, t, vals, measure)
                rows.append({"기간": r.period, "최대 모듈러스": r.max_modulus,
                             "1 이상인 근": int(np.sum(r.moduli >= 1 - 1e-12)), "안정": r.stable, "판정": r.verdict})
            except ValueError as ex:
                rows.append({"기간": wf._label(wf.data.index[t]), "최대 모듈러스": np.nan, "1 이상인 근": np.nan,
                             "안정": None, "판정": None, "비고": str(ex)[:60]})
        return pd.DataFrame(rows).set_index("기간")

    def decompose(self, variables, scenario, base: str = "baseline", start=None, end=None, method: str = "shapley",
                  mode: str = "dynamic", **opts):
        """시나리오 기여도 분해 — scenario와 base(기준선)의 차이를 시나리오 항목(외생 경로·충격·조정항·exclude·목표 추적)별로 나눈다.

        method='shapley'(모든 부분집합의 평균 — 합이 정확히 전체 차이, 항목 8개 이하) · 'single'(하나씩 + 상호작용).
        구간 기본값은 표본.

        돌려주는 것
            DecompositionView — .table(var) · .output(var) · .graph(var) · .drivers · .total

        오류
            ValueError: 기준선과 다른 항목이 없음 · 항목이 많아 shapley가 너무 큼

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> eq_i = wf.equation("eq_i").ls("I c Y(-1) R")
            >>> eq_cn = wf.equation("eq_cn").tsls("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
            >>> m = wf.model("toy").merge(eq_i, eq_cn).append("Y = CN + I + G")
            >>> sc = m.scenario("mix")
            >>> _ = sc.shock("G", 10, "2015Q1", "2015Q4").override("R", 5.0)
            >>> d = m.decompose("Y", "mix", start="2015Q1", end="2015Q4")
            >>> t = d.table("Y")
            >>> bool(abs(t.drop(columns="합계(시나리오 − 기준선)").sum(axis=1) - t["합계(시나리오 − 기준선)"]).max() < 1e-9)
            True
        """
        from ..system.analysis import decompose as _dec
        wf = self._wf
        s, e = wf._bounds(start, end)
        variables = [variables] if isinstance(variables, str) else list(variables)
        sc, bs = self._sc(scenario), (self._sc(base) if base else None)
        model = self._build()
        d = quiet(lambda: _dec(model, sc._sc, bs._sc if bs else None, s, e, variables, method, mode, **opts))
        say(f"[{self.name}] 기여도 분해({method}) {sc.name} − {bs.name if bs else '빈 시나리오'}: 항목 {len(d.drivers)}"
            f" · 풀이 {d.runs}회")
        return DecompositionView(self, d, sc.name, bs.name if bs else "-")

    def compare(self, var: str, aliases: Sequence[str] = None) -> pd.DataFrame:
        """실측과 시나리오 결과 시리즈를 나란히(표본 구간). aliases로 별칭을 고른다.

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> eq_i = wf.equation("eq_i").ls("I c Y(-1) R")
            >>> eq_cn = wf.equation("eq_cn").tsls("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
            >>> m = wf.model("toy").merge(eq_i, eq_cn).append("Y = CN + I + G")
            >>> _ = m.solve("2019Q1", "2019Q4")
            >>> list(m.compare("Y").columns)
            ['Y', 'Y_0']
        """
        wf = self._wf
        cols = [var] if var in wf else []
        als = aliases or [s.alias for s in self._scenarios.values()]
        cols += [f"{var}{a}" for a in als if f"{var}{a}" in wf]
        s, e = wf._bounds()
        return wf.to_pandas(cols).iloc[s:e + 1]


# ===========================================================================
# 그래프·표
# ===========================================================================
class GraphObject:
    kind = "graph"

    def __init__(self, wf, name: str, series, kind: str = "line", title: str = None,
                 start=None, end=None):
        self._wf = wf
        self.name = name
        self.series = series.split() if isinstance(series, str) else list(series)
        if kind not in ("line", "bar", "stacked"):
            raise ValueError(f"그래프 kind는 'line'·'bar'·'stacked' 중 하나입니다(받은 값 {kind!r})")
        self.chart = kind
        self.title = title
        self.start, self.end = start, end

    def __repr__(self):
        return f"<그래프 {self.name}: {' '.join(self.series)}>"

    def _columns(self) -> List[str]:
        cols = list(self._wf.data.columns)
        out = []
        for pat in self.series:
            hits = [c for c in cols if fnmatch.fnmatchcase(c.upper(), pat.upper())] if any(
                ch in pat for ch in "*?[") else [self._wf._col(pat)]
            if not hits or hits == [None]:
                raise KeyError(f"그래프 {self.name}: 시리즈 '{pat}'이(가) 없습니다.")
            out += [h for h in hits if h not in out]
        return out

    def data(self) -> pd.DataFrame:
        """그래프에 쓰는 자료(DataFrame, 그래프의 구간).

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> g = wf.graph("g1", "Y CN", start="2019Q1", end="2019Q4")
            >>> g.data().shape
            (4, 2)
        """
        s, e = self._wf._bounds(self.start, self.end)
        return self._wf.to_pandas(self._columns()).iloc[s:e + 1]

    def output(self) -> GraphOutput:
        """그래프 출력(GraphOutput — .html() · .spec() · .save())."""
        return GraphOutput(self.data(), title=self.title or self.name, kind=self.chart, name=self.name)

    def figure(self):
        """plotly Figure(plotly가 있을 때: pip install 'equion[plot]')."""
        return self.output().figure()

    def _repr_mimebundle_(self, include=None, exclude=None):
        return self.output()._repr_mimebundle_(include, exclude)

    def show(self):
        """그래프를 보인다(노트북에서는 그림, 스크립트에서는 요약)."""
        spool.show(self.output())

    def save(self, path: str) -> str:
        """그래프를 파일로 — .html(plotly 없이도 됨) · .png·.svg·.pdf(plotly와 kaleido가 필요). 없는 폴더는 만든다.

        오류
            ValueError: 모르는 확장자

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> wf.graph("g1", "Y CN").save("doc_graph.html")
            'doc_graph.html'
        """
        return self.output().save(path)


class TableObject:
    kind = "table"

    def __init__(self, wf, name: str, data, title: str = None):
        self._wf = wf
        self.name = name
        if hasattr(data, "output") and callable(data.output):
            data = data.output()
        self.frame = data.data if isinstance(data, TableOutput) else pd.DataFrame(data)
        self.title = title or (data.title if isinstance(data, TableOutput) else name)

    def __repr__(self):
        return f"<표 {self.name}: {self.frame.shape[0]}행 {self.frame.shape[1]}열>"

    def output(self) -> TableOutput:
        """표 출력(TableOutput)."""
        return TableOutput(self.frame, title=self.title, name=self.name)

    def _repr_html_(self):
        return self.output().html()

    def show(self):
        """표를 보인다."""
        spool.show(self.output())

    def save(self, path: str) -> str:
        """표를 파일로 — .csv · .xlsx · .html · .txt(글자 표). 없는 폴더는 만든다.

        오류
            ValueError: 모르는 확장자

        예
            >>> import pandas as pd
            >>> wf = eqn.datasets.load("toy_q")
            >>> wf.table("t1", pd.DataFrame({"a": [1, 2]})).save("doc_table.csv")
            'doc_table.csv'
        """
        import os
        ext = os.path.splitext(path)[1].lower()
        if ext not in (".csv", ".xlsx", ".html", ".htm", ".txt"):
            raise ValueError(f"표는 .csv·.xlsx·.html·.txt로 저장합니다(받은 것: {ext or '확장자 없음'})")
        if os.path.dirname(path):
            os.makedirs(os.path.dirname(path), exist_ok=True)
        if ext == ".xlsx":
            self.frame.to_excel(path)
        elif ext == ".csv":
            self.frame.to_csv(path, encoding="utf-8-sig")
        else:
            out = self.output()
            with open(path, "w", encoding="utf-8") as f:
                f.write(out.html() if ext in (".html", ".htm") else out.text() + "\n")
        record_output(path, "table")
        return path
