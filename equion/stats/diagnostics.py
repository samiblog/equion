#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""회귀 진단 검정 — 잔차(계열상관·이분산·정규성), 함수 형태, 계수 제약, 구조 안정성.

입력은 numpy 배열이나 pandas 객체(잔차 e, 회귀변수 X, 종속변수 y)이고 결과는 TestResult다.
보조 회귀는 모두 equion.stats.regression.ols(자체 OLS)로 푼다. 분포 함수만 scipy를 쓴다.
"""

import ast
from typing import Dict, List, Sequence, Tuple

import numpy as np
import pandas as pd
from scipy import stats

from .regression import Results, constant_info, pinv_svd
from .regression import ols as _ols_frame
from .result import TestResult


# ---------------------------------------------------------------------------
# 보조
# ---------------------------------------------------------------------------
def _ols(y: np.ndarray, X: np.ndarray) -> Results:
    n = len(y)
    idx = pd.RangeIndex(n)
    return _ols_frame(pd.Series(np.asarray(y, dtype=float), index=idx),
                      pd.DataFrame(np.asarray(X, dtype=float), index=idx,
                                   columns=[f"x{i}" for i in range(np.shape(X)[1])]))


def _arr(v) -> np.ndarray:
    return np.asarray(v, dtype=float)


def _with_const(X: np.ndarray) -> np.ndarray:
    """상수항이 없으면 맨 앞에 붙인다(이분산 보조 회귀용)."""
    X = _arr(X)
    k, _ = constant_info(X)
    return X if k else np.column_stack([np.ones(len(X)), X])


def wald_linear(params, cov, R, q, df_resid=None) -> Tuple[float, float, float, float, int]:
    """H₀: R·b = q의 Wald 통계 — (F, F p값, χ², χ² p값, 제약 수). F 자유도는 (제약 수, df_resid).

    오류
        ValueError: 제약끼리 겹치거나 모순(R의 계수 < 행 수)

    예
        >>> rng = np.random.default_rng(0)
        >>> x = rng.normal(size=100)
        >>> X = pd.DataFrame({"const": 1.0, "x": x})
        >>> y = pd.Series(1 + 2 * x + rng.normal(size=100))
        >>> r = eqn.stats.ols(y, X)
        >>> F, pF, chi2, pchi, q = eqn.stats.wald_linear(r.params, r.cov_params(), [[0, 1]], [2.0], r.df_resid)
        >>> q, bool(pF > 0.05)
        (1, True)
    """
    b = _arr(params)
    R = np.atleast_2d(_arr(R))
    q = np.atleast_1d(_arr(q))
    if np.linalg.matrix_rank(R) < R.shape[0]:
        raise ValueError("제약끼리 겹치거나 서로 모순됩니다(같은 계수 조합을 두 번 제약) — 독립인 제약만 주세요")
    d = R @ b - q
    V = R @ _arr(cov) @ R.T
    chi2 = float(d @ np.linalg.pinv(V) @ d)
    m = R.shape[0]
    F = chi2 / m
    fp = float(stats.f.sf(F, m, df_resid)) if df_resid else np.nan
    return F, fp, chi2, float(stats.chi2.sf(chi2, m)), m


def _f_restrict(res: Results, idx: Sequence[int]) -> Tuple[float, float]:
    """보조 회귀에서 idx 계수 = 0 의 F(일반 공분산)."""
    k = len(res.params)
    R = np.eye(k)[list(idx)]
    F, fp, *_ = wald_linear(res.params, res.cov_params(), R, np.zeros(len(idx)), res.df_resid)
    return F, fp


def _lags_of(x: np.ndarray, lags: int, pad: bool) -> np.ndarray:
    """x의 1~lags 시차 행렬. pad=True면 표본 앞을 0으로 채워 길이 n 유지, False면 앞 lags행을 버린다."""
    n = len(x)
    if pad:
        z = np.concatenate([np.zeros(lags), x])
        return np.column_stack([z[lags - j: lags - j + n] for j in range(1, lags + 1)])
    return np.column_stack([x[lags - j: n - j] for j in range(1, lags + 1)])


# ---------------------------------------------------------------------------
# 잔차: 계열상관
# ---------------------------------------------------------------------------
def breusch_godfrey(resid, X, lags: int = 2) -> TestResult:
    """계열상관 LM 검정(Breusch-Godfrey) — 잔차를 X와 잔차 시차(표본 앞은 0)에 회귀, LM = n·R².

    예
        >>> rng = np.random.default_rng(0)
        >>> x = rng.normal(size=100)
        >>> X = pd.DataFrame({"const": 1.0, "x": x})
        >>> y = pd.Series(1 + 2 * x + rng.normal(size=100))
        >>> r = eqn.stats.ols(y, X)
        >>> eqn.stats.breusch_godfrey(r.resid, X, lags=2).reject(0.05)
        False
    """
    e, X = _arr(resid), _arr(X)
    if lags < 1:
        raise ValueError("시차는 1 이상")
    n = len(e)
    if n - X.shape[1] - 1 - lags < 1:
        raise ValueError(f"시차 {lags}가 너무 깁니다 — 관측치 {n}, 회귀변수 {X.shape[1]}로는 보조 회귀를 할 수 없습니다")
    # 상수항은 X에 없을 때만 더한다 — 겹친 상수열은 완전 공선이라 유사역행렬의 절단이 BLAS에 따라 달라진다(결과가 플랫폼마다 달랐다)
    Z = np.column_stack([_with_const(X), _lags_of(e, lags, pad=True)])
    aux = _ols(e, Z)
    lm = n * aux.rsquared
    F, fp = _f_restrict(aux, range(Z.shape[1] - lags, Z.shape[1]))
    return TestResult("계열상관 LM 검정(Breusch-Godfrey)", lm, float(stats.chi2.sf(lm, lags)),
                      null=f"잔차에 시차 {lags}까지 계열상관이 없다",
                      rows={"F 통계량": F, "F p값": fp, "자유도(LM)": lags},
                      info={"시차": lags, "관측치": n})


def _acf(x: np.ndarray, nlags: int) -> np.ndarray:
    xo = x - x.mean()
    n = len(x)
    avf = np.correlate(xo, xo, "full")[n - 1:] / n
    return avf[: nlags + 1] / avf[0]


def ljung_box(resid, lags: int = None, model_df: int = 0) -> TestResult:
    """Ljung-Box Q 검정 — 시차별 자기상관·Q·p값 표 포함. 기본 시차 min(10, n/5), model_df는 자유도에서 뺄 수.

    예
        >>> rng = np.random.default_rng(0)
        >>> x = rng.normal(size=100)
        >>> X = pd.DataFrame({"const": 1.0, "x": x})
        >>> y = pd.Series(1 + 2 * x + rng.normal(size=100))
        >>> r = eqn.stats.ols(y, X)
        >>> q = eqn.stats.ljung_box(r.resid, 5)
        >>> len(q.table), q.reject(0.05)
        (5, False)
    """
    e = _arr(resid)
    n = len(e)
    L = min(10, n // 5) if lags is None else int(lags)
    if not 1 <= L < n:
        raise ValueError(f"Ljung-Box 시차는 1 이상, 관측치({n})보다 작아야 합니다 (지금 {L})")
    ac = _acf(e, L)
    k = np.arange(1, L + 1)
    q = n * (n + 2) * np.cumsum(ac[1:] ** 2 / (n - k))
    dfs = k - model_df
    p = np.full(L, np.nan)
    p[dfs > 0] = stats.chi2.sf(q[dfs > 0], dfs[dfs > 0])
    table = pd.DataFrame({"자기상관": ac[1:], "Q": q, "p값": p}, index=pd.Index(k, name="시차"))
    return TestResult("Ljung-Box Q 검정", float(q[-1]), float(p[-1]), null=f"시차 {L}까지 자기상관이 없다",
                      rows={"시차": L}, info={"시차": L, "관측치": n}, details={"lags": L, "nobs": n}, table=table)


# ---------------------------------------------------------------------------
# 잔차: 이분산
# ---------------------------------------------------------------------------
def white(resid, X, cross: bool = True) -> TestResult:
    """White 이분산 검정 — 잔차²를 회귀변수·제곱(cross=True면 교차곱까지)에 회귀, LM = n·R².

    예
        >>> rng = np.random.default_rng(0)
        >>> x = rng.normal(size=100)
        >>> X = pd.DataFrame({"const": 1.0, "x": x})
        >>> y = pd.Series(1 + 2 * x + rng.normal(size=100))
        >>> r = eqn.stats.ols(y, X)
        >>> eqn.stats.white(r.resid, X).reject(0.05)
        False
    """
    e, X = _arr(resid), _with_const(X)
    n, m = X.shape
    if cross:
        i0, i1 = np.triu_indices(m)
        Z = X[:, i0] * X[:, i1]
    else:
        kc, ci = constant_info(X)
        sq = [j for j in range(m) if j != ci]
        Z = np.column_stack([X, X[:, sq] ** 2])
    aux = _ols(e ** 2, Z)
    lm = n * aux.rsquared
    df = aux.df_model
    return TestResult("White 이분산 검정" + ("(교차항 포함)" if cross else "(교차항 없음)"), lm,
                      float(stats.chi2.sf(lm, df)), null="잔차 분산이 일정하다(동분산)",
                      rows={"F 통계량": aux.fvalue, "F p값": aux.f_pvalue, "자유도(LM)": df},
                      info={"관측치": n})


def breusch_pagan(resid, X) -> TestResult:
    """Breusch-Pagan-Godfrey 이분산 검정 — LM = n·R²(Koenker), 원래 형태(설명 제곱합/2)도 함께.

    예
        >>> rng = np.random.default_rng(0)
        >>> x = rng.normal(size=100)
        >>> X = pd.DataFrame({"const": 1.0, "x": x})
        >>> y = pd.Series(1 + 2 * x + rng.normal(size=100))
        >>> r = eqn.stats.ols(y, X)
        >>> eqn.stats.breusch_pagan(r.resid, X).reject(0.05)
        False
    """
    e, X = _arr(resid), _with_const(X)
    n, m = X.shape
    e2 = e ** 2
    aux = _ols(e2, X)
    lm = n * aux.rsquared
    aux2 = _ols(e2 / np.mean(e2), X)
    y2 = aux2.endog.to_numpy(dtype=float)
    ess = float(np.sum((y2 - y2.mean()) ** 2) - aux2.ssr)
    df = m - 1
    return TestResult("Breusch-Pagan-Godfrey 이분산 검정", lm, float(stats.chi2.sf(lm, df)),
                      null="잔차 분산이 일정하다(동분산)",
                      rows={"F 통계량": aux.fvalue, "F p값": aux.f_pvalue, "설명 제곱합/2(원래 BP)": ess / 2,
                            "원래 BP p값": float(stats.chi2.sf(ess / 2, df)), "자유도": df},
                      info={"관측치": n})


def arch_lm(resid, lags: int = 1) -> TestResult:
    """ARCH LM 검정 — 잔차²를 상수와 잔차² 시차에 회귀, LM = (n − 시차)·R².

    예
        >>> rng = np.random.default_rng(0)
        >>> x = rng.normal(size=100)
        >>> X = pd.DataFrame({"const": 1.0, "x": x})
        >>> y = pd.Series(1 + 2 * x + rng.normal(size=100))
        >>> r = eqn.stats.ols(y, X)
        >>> eqn.stats.arch_lm(r.resid, 2).reject(0.05)
        False
    """
    x = _arr(resid) ** 2
    if lags < 1:
        raise ValueError("시차는 1 이상")
    if len(x) - 2 * lags - 1 < 1:
        raise ValueError(f"ARCH 시차 {lags}가 너무 깁니다 — 관측치 {len(x)}")
    Z = np.column_stack([np.ones(len(x) - lags), _lags_of(x, lags, pad=False)])
    aux = _ols(x[lags:], Z)
    nobs = len(x) - lags
    lm = nobs * aux.rsquared
    return TestResult("ARCH LM 검정", lm, float(stats.chi2.sf(lm, lags)), null=f"시차 {lags}까지 ARCH 효과가 없다",
                      rows={"F 통계량": aux.fvalue, "F p값": aux.f_pvalue, "자유도(LM)": lags},
                      info={"시차": lags, "관측치": nobs})


# ---------------------------------------------------------------------------
# 잔차: 정규성
# ---------------------------------------------------------------------------
def jarque_bera(resid) -> TestResult:
    """Jarque-Bera 정규성 검정 — JB = n/6·(왜도² + (첨도 − 3)²/4).

    예
        >>> rng = np.random.default_rng(0)
        >>> x = rng.normal(size=100)
        >>> X = pd.DataFrame({"const": 1.0, "x": x})
        >>> y = pd.Series(1 + 2 * x + rng.normal(size=100))
        >>> r = eqn.stats.ols(y, X)
        >>> eqn.stats.jarque_bera(r.resid).reject(0.05)
        False
    """
    e = _arr(resid)
    n = len(e)
    sk = float(stats.skew(e))
    ku = float(3 + stats.kurtosis(e))
    jb = n / 6.0 * (sk ** 2 + 0.25 * (ku - 3) ** 2)
    return TestResult("Jarque-Bera 정규성 검정", jb, float(stats.chi2.sf(jb, 2)), null="잔차가 정규분포를 따른다",
                      rows={"왜도": sk, "첨도": ku}, info={"관측치": n})


# ---------------------------------------------------------------------------
# 함수 형태
# ---------------------------------------------------------------------------
def reset(y, X, fitted, terms: int = 1) -> TestResult:
    """Ramsey RESET — 적합값의 2~(terms+1)제곱을 더한 회귀에서 추가 항 계수 = 0의 F·LR.

    예
        >>> rng = np.random.default_rng(0)
        >>> x = rng.normal(size=100)
        >>> X = pd.DataFrame({"const": 1.0, "x": x})
        >>> y = pd.Series(1 + 2 * x + rng.normal(size=100))
        >>> r = eqn.stats.ols(y, X)
        >>> eqn.stats.reset(y, X, r.fittedvalues, 2).reject(0.05)
        False
    """
    y, X, f = _arr(y), _arr(X), _arr(fitted)
    if terms < 1:
        raise ValueError("추가 항 수는 1 이상")
    aug = np.column_stack([X] + [f ** p for p in range(2, terms + 2)])
    full, base = _ols(y, aug), _ols(y, X)
    F, fp = _f_restrict(full, range(X.shape[1], aug.shape[1]))
    lr = 2 * (full.llf - base.llf)
    return TestResult("Ramsey RESET 검정", F, fp, null="함수 형태가 맞다(적합값 거듭제곱 항이 필요 없다)",
                      rows={"LR 통계량": lr, "LR p값": float(stats.chi2.sf(lr, terms)), "추가 항": terms},
                      info={"추가 항": terms, "관측치": len(y)})


# ---------------------------------------------------------------------------
# 계수 제약 (Wald)
# ---------------------------------------------------------------------------
class _Linear(ast.NodeVisitor):
    """c(n)에 선형인 식 → ({계수번호: 계수}, 상수)."""

    def __init__(self, text):
        self.text = text

    def fail(self, why):
        raise ValueError(f"계수 제약을 읽을 수 없습니다({why}): {self.text!r} — 예: c(2) + c(3) = 1")

    def lin(self, node):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return {}, float(node.value)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id.lower() == "c" \
                and len(node.args) == 1 and not node.keywords and isinstance(node.args[0], ast.Constant) \
                and isinstance(node.args[0].value, int):
            return {int(node.args[0].value): 1.0}, 0.0
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            c, k = self.lin(node.operand)
            s = -1.0 if isinstance(node.op, ast.USub) else 1.0
            return {i: s * v for i, v in c.items()}, s * k
        if isinstance(node, ast.BinOp):
            (ca, ka), (cb, kb) = self.lin(node.left), self.lin(node.right)
            if isinstance(node.op, (ast.Add, ast.Sub)):
                s = 1.0 if isinstance(node.op, ast.Add) else -1.0
                out = dict(ca)
                for i, v in cb.items():
                    out[i] = out.get(i, 0.0) + s * v
                return out, ka + s * kb
            if isinstance(node.op, ast.Mult):
                if ca and cb:
                    self.fail("계수끼리 곱")
                return ({i: v * kb for i, v in ca.items()}, ka * kb) if ca else ({i: v * ka for i, v in cb.items()}, ka * kb)
            if isinstance(node.op, ast.Div):
                if cb:
                    self.fail("계수로 나눔")
                if kb == 0:
                    self.fail("0으로 나눔")
                return {i: v / kb for i, v in ca.items()}, ka / kb
        self.fail("허용하지 않는 표현")


def parse_restrictions(restrictions: Sequence[str], n_coef: int) -> Tuple[np.ndarray, np.ndarray]:
    """제약 글자 → (R, q). c(n)은 1부터 센다. 숫자·c(n)·+−×÷만 읽는다(허용 목록 문법).

    예
        >>> R, q = eqn.stats.parse_restrictions(["c(2) + c(3) = 1", "c(1) = 0"], 3)
        >>> R.tolist(), q.tolist()
        ([[0.0, 1.0, 1.0], [1.0, 0.0, 0.0]], [1.0, 0.0])
    """
    rows, qs = [], []
    for text in restrictions:
        parts = str(text).split("=")
        if len(parts) != 2:
            raise ValueError(f"계수 제약에는 '='가 하나 있어야 합니다: {text!r}")
        p = _Linear(text)
        try:
            lhs = p.lin(ast.parse(parts[0].strip(), mode="eval").body)
            rhs = p.lin(ast.parse(parts[1].strip(), mode="eval").body)
        except SyntaxError:
            p.fail("문법 오류")
        coef = dict(lhs[0])
        for i, v in rhs[0].items():
            coef[i] = coef.get(i, 0.0) - v
        bad = [i for i in coef if not 1 <= i <= n_coef]
        if bad:
            raise ValueError(f"계수 번호 {bad}가 범위(1~{n_coef}) 밖입니다: {text!r}")
        r = np.zeros(n_coef)
        for i, v in coef.items():
            r[i - 1] = v
        rows.append(r)
        qs.append(rhs[1] - lhs[1])
    return np.array(rows), np.array(qs)


def wald(params, cov, restrictions: Sequence[str], df_resid: float = None, labels: Sequence[str] = None) -> TestResult:
    """Wald 계수 제약 검정 — params·cov는 계수 순서(c(1), c(2), …)대로, restrictions는 "c(2) = 2" 같은 글자.

    df_resid를 주면 F 통계(작은 표본), 없으면 χ².

    예
        >>> rng = np.random.default_rng(0)
        >>> x = rng.normal(size=100)
        >>> X = pd.DataFrame({"const": 1.0, "x": x})
        >>> y = pd.Series(1 + 2 * x + rng.normal(size=100))
        >>> r = eqn.stats.ols(y, X)
        >>> eqn.stats.wald(r.params, r.cov_params(), ["c(2) = 2"], df_resid=r.df_resid).reject(0.05)
        False
    """
    b = _arr(params)
    R, q = parse_restrictions(restrictions, len(b))
    F, fp, chi2, cp, m = wald_linear(b, cov, R, q, df_resid)
    V = R @ _arr(cov) @ R.T
    table = pd.DataFrame({"제약(R·b − q)": R @ b - q, "표준오차": np.sqrt(np.diag(V))},
                         index=pd.Index(list(restrictions), name="제약"))
    rows = {"χ² 통계량": chi2, "χ² p값": cp, "제약 수": m}
    notes = []
    if labels is not None:
        notes.append("계수 번호: " + " · ".join(f"c({i + 1})={nm}" for i, nm in enumerate(labels)))
    return TestResult("Wald 계수 제약 검정", F, fp, null=" 그리고 ".join(restrictions), rows=rows,
                      info={"제약 수": m}, table=table, notes=notes)


# ---------------------------------------------------------------------------
# 구조 안정성
# ---------------------------------------------------------------------------
def chow(y, X, split: int, label: str = None) -> TestResult:
    """Chow 구조변화 검정 — split = 둘째 구간이 시작하는 행 위치(0부터).

    예
        >>> rng = np.random.default_rng(0)
        >>> x = rng.normal(size=100)
        >>> X = pd.DataFrame({"const": 1.0, "x": x})
        >>> y = pd.Series(1 + 2 * x + rng.normal(size=100))
        >>> eqn.stats.chow(y, X, 50).reject(0.05)
        False
    """
    y, X = _arr(y), _arr(X)
    n, k = X.shape
    if not (k < split < n - k):
        raise ValueError(f"구간마다 관측치가 계수 수({k})보다 많아야 합니다 (나눔 위치 {split}, 전체 {n})")
    full, a, b = _ols(y, X), _ols(y[:split], X[:split]), _ols(y[split:], X[split:])
    s_u = a.ssr + b.ssr
    F = ((full.ssr - s_u) / k) / (s_u / (n - 2 * k))
    lr = -2 * (full.llf - (a.llf + b.llf))
    return TestResult(f"Chow 구조변화 검정({label or split})", F, float(stats.f.sf(F, k, n - 2 * k)),
                      null="나눈 두 구간의 계수가 같다(구조변화 없음)",
                      rows={"LR 통계량": lr, "LR p값": float(stats.chi2.sf(lr, k)), "자유도": f"({k}, {n - 2 * k})"},
                      info={"관측치": n, "앞 구간": split, "뒤 구간": n - split})


def nested(y, X_small, X_big, weights=None, name: str = "변수 추가 검정", null: str = "",
           labels_added: Sequence[str] = None) -> TestResult:
    """작은 식(X_small) ⊂ 큰 식(X_big)의 최소제곱 비교 — 누락·불필요 변수 검정의 공통 계산(F·LR).

    예
        >>> rng = np.random.default_rng(0)
        >>> x = rng.normal(size=100)
        >>> X = pd.DataFrame({"const": 1.0, "x": x})
        >>> y = pd.Series(1 + 2 * x + rng.normal(size=100))
        >>> big = X.assign(z=rng.normal(size=100))
        >>> eqn.stats.nested(y, X, big).reject(0.05)
        False
    """
    y, Xs, Xb = _arr(y), _arr(X_small), _arr(X_big)
    n = len(y)
    if Xs.shape[0] != n or Xb.shape[0] != n:
        raise ValueError("두 식의 관측치 수가 다릅니다")
    if weights is not None:
        sw = np.sqrt(_arr(weights))
        y, Xs, Xb = y * sw, Xs * sw[:, None], Xb * sw[:, None]
    small = _ols(y, Xs) if Xs.shape[1] else None
    big = _ols(y, Xb)
    ssr_s = small.ssr if small is not None else float(y @ y)
    q = int(big.rank - (small.rank if small is not None else 0))
    if q <= 0:
        raise ValueError("더하거나 뺀 변수가 기존 변수와 선형 종속입니다(검정할 제약이 없음)")
    df2 = n - big.rank
    F = ((ssr_s - big.ssr) / q) / (big.ssr / df2)
    lr = n * np.log(ssr_s / big.ssr)
    rows = {"LR 통계량": float(lr), "LR p값": float(stats.chi2.sf(lr, q)), "자유도": f"({q}, {int(df2)})",
            "SSR(작은 식)": ssr_s, "SSR(큰 식)": big.ssr}
    return TestResult(name, float(F), float(stats.f.sf(F, q, df2)), null=null, rows=rows,
                      info={"관측치": n, "제약 수": q}, details={"q": q, "df_resid": df2, "lr": float(lr)})


def recursive(y, X, alpha: float = 0.95) -> Dict[str, np.ndarray]:
    """재귀 잔차·재귀 계수·CUSUM과 신뢰 경계(Brown-Durbin-Evans) — 처음 k개 관측치로 시작해 한 기씩 늘린다.

    각 시점의 계수는 그때까지의 관측치로 직접 최소제곱한다(갱신 공식의 반올림 누적을 피한다).

    예
        >>> rng = np.random.default_rng(0)
        >>> x = rng.normal(size=100)
        >>> X = pd.DataFrame({"const": 1.0, "x": x})
        >>> y = pd.Series(1 + 2 * x + rng.normal(size=100))
        >>> out = eqn.stats.recursive(y.to_numpy(), X.to_numpy())
        >>> sorted(out)
        ['bound', 'cusum', 'rparams', 'rresid', 'standardized', 'start']
    """
    y, X = _arr(y), _arr(X)
    n, k = X.shape
    a = {0.90: 0.850, 0.95: 0.948, 0.99: 1.143}.get(alpha)
    if a is None:
        raise ValueError("alpha는 0.90·0.95·0.99 중 하나")
    if np.linalg.matrix_rank(X[:k]) < k:
        raise ValueError("처음 k개 관측치의 회귀변수가 선형 종속이라 재귀 추정을 시작할 수 없습니다")
    rparams = np.full((n, k), np.nan)
    rresid = np.full(n, np.nan)
    rvar = np.full(n, np.nan)
    xtxi_prev = None
    for i in range(k - 1, n):                      # rparams[i] = 0~i번째 관측치로 추정한 계수
        P, _ = pinv_svd(X[:i + 1])
        beta = P @ y[:i + 1]
        xtxi = P @ P.T
        rparams[i] = beta
        if i == k - 1:
            rresid[i] = y[i] - X[i] @ beta
            rvar[i] = 1 + X[i] @ xtxi @ X[i]
        else:                                      # i번째 관측치를 그 전까지의 계수로 예측
            rresid[i] = y[i] - X[i] @ rparams[i - 1]
            rvar[i] = 1 + X[i] @ xtxi_prev @ X[i]
        xtxi_prev = xtxi
    scaled = rresid / np.sqrt(rvar)
    sigma2 = scaled[k:].var(ddof=1)
    standardized = scaled / np.sqrt(sigma2)
    cusum = standardized[k - 1:].cumsum()
    nrr = n - k
    bound = a * np.sqrt(nrr) + 2 * a * np.arange(0, n - k) / np.sqrt(nrr)
    return {"rresid": rresid, "rparams": rparams, "standardized": standardized, "cusum": cusum,
            "bound": bound, "start": k}


def cusum(y, X, index=None, alpha: float = 0.95) -> TestResult:
    """CUSUM 안정성 검정 — 누적 재귀 잔차가 경계(5%: ±0.948·[√(n−k) + 2(t−k)/√(n−k)])를 벗어나는가.

    통계량은 경계 대비 최대 비율(1보다 작으면 안정).

    예
        >>> rng = np.random.default_rng(0)
        >>> x = rng.normal(size=100)
        >>> X = pd.DataFrame({"const": 1.0, "x": x})
        >>> y = pd.Series(1 + 2 * x + rng.normal(size=100))
        >>> bool(eqn.stats.cusum(y.to_numpy(), X.to_numpy()).statistic < 1)
        True
    """
    r = recursive(y, X, alpha)
    k = r["start"]
    w = r["cusum"][1:]                          # 첫 재귀 잔차(k−1번째)는 0 기준점
    b = r["bound"]
    ratio = np.abs(w) / b
    crossed = bool(np.any(ratio > 1))
    idx = index[k:] if index is not None else pd.RangeIndex(k, k + len(w))
    table = pd.DataFrame({"CUSUM": w, "하한": -b, "상한": b}, index=idx)
    note = "경계를 벗어남 — 계수가 안정적이지 않을 수 있음" if crossed else "경계 안 — 계수 안정성을 기각하지 못함"
    res = TestResult(f"CUSUM 안정성 검정({int(alpha * 100)}% 경계)", float(ratio.max()), np.nan,
                     null="계수가 표본 전체에서 일정하다",
                     rows={"경계 대비 최대 비율": float(ratio.max()), "경계를 벗어난 기간 수": int(np.sum(ratio > 1))},
                     info={"관측치": len(r["standardized"])}, details={"crossed": crossed}, notes=[note], data=table)
    return res
