#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""VAR·VECM 객체 (DECISIONS D23).

    v = wf.var("v1", ["dlog(Y)", "dlog(CN)"], lags=2)              # 이름·식 모두 가능, trend 'n'·'c'·'ct'
    v.lag_order(8).show(); v.granger("dlog(CN)", "dlog(Y)")
    v.irf(12)  → DataFrame(열 = (반응, 충격)), v.fevd(12), v.forecast(8), v.stability()
    k = wf.vecm("k1", ["RL", "R"], lags_diff=1, rank=1, deterministic="ci")
    wf.model("m").merge(v)                                          # 추정 계수를 고정한 식으로 모델에

표본은 워크파일 smpl 안에서 모든 시리즈가 관측되는 가장 긴 연속 구간이다.
"""

from typing import List, Sequence

import numpy as np
import pandas as pd

from ..stats import var as _var
from ..stats.result import TestResult
from .output import GraphOutput, TableOutput, say, spool


def _names(series) -> List[str]:
    return [s for s in series.split()] if isinstance(series, str) else [str(s) for s in series]


class _Base:
    def __init__(self, wf, name: str):
        self._wf, self.name = wf, name
        self.series: List[str] = []
        self.fit = None
        self.version = 0

    def _frame(self, series) -> pd.DataFrame:
        names = _names(series)
        if len(names) < 2:
            raise ValueError("VAR·VECM에는 시리즈가 둘 이상 필요합니다")
        low = [n.lower() for n in names]
        dup = sorted({n for n, l in zip(names, low) if low.count(l) > 1})
        if dup:
            raise ValueError(f"같은 시리즈가 두 번 있습니다: {dup}")
        df = self._wf._test_frame(names)            # 표본 구간, 양끝 결측 제외, 안쪽 결측은 오류
        self.series = names
        self._index = df.index
        self._s0 = int(self._wf.index.get_loc(df.index[0]))
        return df

    def _require(self):
        if self.fit is None:
            raise RuntimeError(f"{self.kind} {self.name}이(가) 아직 추정되지 않았습니다")
        return self.fit

    def show(self):
        spool.show(self.output())

    def _repr_html_(self):
        return self.output().html() if self.fit is not None else None

    def _lag(self, s: str, k: int) -> str:
        return f"({s}).t(-{k})"


def _steps(n, lo: int, what: str):
    if int(n) != n or n < lo:
        raise ValueError(f"{what}는 {lo} 이상의 정수여야 합니다(받은 값 {n})")


class VARObject(_Base):
    kind = "var"

    def to_json(self) -> dict:
        """저장용 정의(dict — 변수·시차·결정항)."""
        f = self.fit
        return {"type": "var", "name": self.name, "series": self.series,
                "lags": f.p if f else None, "trend": f.trend if f else None}

    @classmethod
    def from_json(cls, wf, d):
        """저장한 정의로 다시 추정해 되살린다(워크파일 열기가 쓴다)."""
        o = cls(wf, d["name"])
        if d.get("lags") is not None:
            o.estimate(d["series"], d["lags"], d["trend"])
        return o

    def __repr__(self):
        return f"<VAR {self.name}: {' '.join(self.series)} · 시차 {self.fit.p if self.fit else '?'}>"

    def estimate(self, series, lags: int = 1, trend: str = "c"):
        """같은 객체를 다른 변수·시차로 다시 추정한다(보통은 wf.var가 부른다).

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> v = wf.var("v1", ["dlog(Y)", "R"], lags=2)
            >>> v.estimate(["dlog(Y)", "R"], lags=1).coefs.shape
            (3, 2)
        """
        if int(lags) != lags or lags < 1:
            raise ValueError(f"VAR 시차는 1 이상의 정수여야 합니다(받은 값 {lags}) — 시차 0과의 비교는 .lag_order()")
        df = self._frame(series)
        self.fit = _var.fit_var(df.to_numpy(), int(lags), trend)
        self.trend = trend
        self.version += 1
        f = self.fit
        say(f"[{self.name}] VAR({f.p}) 추정 — 변수 {f.k} · 관측치 {f.nobs} · AIC {f.info_criteria()['aic']:.4f}"
            + ("" if f.is_stable else " · ⚠ 불안정(근 모듈러스 ≥ 1)"))
        return self

    # ---- 결과 -------------------------------------------------------------
    def _reg_labels(self) -> List[str]:
        det = {"n": [], "c": ["c"], "ct": ["c", "@trend"]}[self.fit.trend]
        return det + [f"{s}(-{i})" for i in range(1, self.fit.p + 1) for s in self.series]

    @property
    def coefs(self) -> pd.DataFrame:
        """계수(행 = 회귀변수, 열 = 식)."""
        return pd.DataFrame(self._require().coefs, index=self._reg_labels(), columns=self.series)

    @property
    def stderrs(self) -> pd.DataFrame:
        """계수 표준오차(행 = 회귀변수, 열 = 식)."""
        f = self._require()
        se = np.sqrt(np.diag(f.cov_params)).reshape(f.k, -1).T
        return pd.DataFrame(se, index=self._reg_labels(), columns=self.series)

    @property
    def sigma(self) -> pd.DataFrame:
        """잔차 공분산 Σ̂(DataFrame)."""
        return pd.DataFrame(self._require().sigma_u, index=self.series, columns=self.series)

    @property
    def resid(self) -> pd.DataFrame:
        """잔차(DataFrame, 행 = 기간, 열 = 식)."""
        f = self._require()
        return pd.DataFrame(f.resid, index=self._index[f.p:], columns=self.series)

    def ic(self) -> dict:
        """정보기준 {aic, bic, hqic, fpe}."""
        return self._require().info_criteria()

    def _pos(self, names) -> List[int]:
        out = []
        for n in _names(names):
            if n not in self.series:
                raise KeyError(f"VAR에 없는 변수 {n!r} (변수: {self.series})")
            out.append(self.series.index(n))
        return out

    def lag_order(self, maxlags: int = 8) -> TableOutput:
        """시차 고르기 — 같은 표본(처음 maxlags기 제외)에서 시차 0…maxlags의 AIC·BIC·HQ·FPE(*: 각 기준이 고른 시차).

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> v = wf.var("v1", ["dlog(Y)", "R"], lags=2)
            >>> t = v.lag_order(4)
            >>> len(t.data)
            5
        """
        df_ = self._wf._test_frame(self.series)
        r = _var.select_order(df_.to_numpy(), maxlags, getattr(self, "trend", "c"))
        tab = pd.DataFrame(r["table"], index=pd.Index(range(maxlags + 1), name="시차"))
        tab.columns = ["AIC", "BIC", "HQ", "FPE"]
        mark = pd.DataFrame("", index=tab.index, columns=[f"{c}*" for c in tab.columns])
        for c, k in zip(tab.columns, ("aic", "bic", "hqic", "fpe")):
            mark.loc[r["selected"][k], f"{c}*"] = "*"
        out = pd.concat([tab, mark], axis=1)[[x for c in tab.columns for x in (c, f"{c}*")]]
        sel = " · ".join(f"{c} {r['selected'][k]}" for c, k in zip(tab.columns, ("aic", "bic", "hqic", "fpe")))
        return TableOutput(out, title=f"VAR {self.name} 시차 선택", head=[f"고른 시차: {sel}"], name=f"{self.name}_lags")

    def granger(self, caused, causing) -> TestResult:
        """Granger 인과 — causing(변수 하나 또는 목록)의 모든 시차가 caused 식에서 0인가(Wald F).

        오류
            KeyError: VAR에 없는 변수

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> v = wf.var("v1", ["dlog(Y)", "R"], lags=2)
            >>> round(v.granger("dlog(Y)", "R").pvalue, 2)
            0.06
        """
        f = self._require()
        g = _var.granger(f, self._pos(caused), self._pos(causing))
        r = TestResult("Granger 인과 검정", g["F"], g["pvalue"],
                       null=f"{' · '.join(_names(causing))} → {' · '.join(_names(caused))} 인과 없음",
                       rows={"자유도": f"({g['df'][0]}, {g['df'][1]})", "χ²": g["chi2"], "χ² p값": g["chi2_p"]},
                       info={"VAR": f"{self.name}({f.p})"})
        say(f"[{self.name}] {r.name}: F {r.statistic:.4f}, p={r.pvalue:.4f}")
        return r

    def granger_table(self) -> TableOutput:
        """모든 변수 쌍의 Granger F p값 표(행 = 원인, 열 = 결과).

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> v = wf.var("v1", ["dlog(Y)", "R"], lags=2)
            >>> v.granger_table().data.shape
            (2, 2)
        """
        k = len(self.series)
        P = pd.DataFrame(np.nan, index=self.series, columns=self.series)
        for i in range(k):
            for j in range(k):
                if i != j:
                    P.iloc[i, j] = _var.granger(self._require(), [j], [i])["pvalue"]
        P.index.name = "원인 → 결과"
        return TableOutput(P, title=f"VAR {self.name} Granger 인과 p값", name=f"{self.name}_granger")

    def irf(self, periods: int = 10, orth: bool = True) -> pd.DataFrame:
        """충격반응 — 행 = 0…periods, 열 = (반응, 충격). orth=True면 촐레스키(변수 순서대로) 1 표준편차 충격, False면 단위 충격.

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> v = wf.var("v1", ["dlog(Y)", "R"], lags=2)
            >>> irf = v.irf(4)
            >>> irf.shape, float(irf[("dlog(Y)", "R")].iloc[0])
            ((5, 4), 0.0)
        """
        _steps(periods, 0, "periods")
        R = _var.irf(self._require(), periods, orth)
        cols = pd.MultiIndex.from_product([self.series, self.series], names=["반응", "충격"])
        return pd.DataFrame(R.reshape(periods + 1, -1), index=pd.RangeIndex(periods + 1, name="기"), columns=cols)

    def irf_graph(self, impulse: str, periods: int = 10, orth: bool = True) -> GraphOutput:
        """한 충격에 대한 모든 변수의 반응 그림(GraphOutput)."""
        if impulse not in self.series:
            raise KeyError(f"VAR에 없는 충격 변수 '{impulse}' (변수: {self.series})")
        df = self.irf(periods, orth).xs(impulse, axis=1, level="충격")
        return GraphOutput(df, title=f"{self.name}: {impulse} 충격의 반응", name=f"{self.name}_irf")

    def fevd(self, periods: int = 10) -> dict:
        """예측오차 분산분해 — {반응 변수: DataFrame(행 = 1…periods, 열 = 충격 변수, 행 합 = 1)}.

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> v = wf.var("v1", ["dlog(Y)", "R"], lags=2)
            >>> d = v.fevd(4)
            >>> float(d["dlog(Y)"].sum(axis=1).round(10).iloc[-1])
            1.0
        """
        _steps(periods, 1, "periods")
        D = _var.fevd(self._require(), periods)
        idx = pd.RangeIndex(1, periods + 1, name="기")
        return {s: pd.DataFrame(D[i], index=idx, columns=self.series) for i, s in enumerate(self.series)}

    def forecast(self, steps: int = 8) -> pd.DataFrame:
        """추정 표본 끝 다음부터 steps기 점 예측(행 = 기간 라벨).

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> v = wf.var("v1", ["dlog(Y)", "R"], lags=2)
            >>> list(v.forecast(2).index)
            ['2020Q1', '2020Q2']
        """
        _steps(steps, 1, "steps")
        f = self._require()
        fc = _var.forecast(f, steps)
        from ..data.periods import format_period, to_period
        last = to_period(self._index[-1], self._wf.freq)
        labels = [format_period(last + i, self._wf.freq) for i in range(1, steps + 1)]
        return pd.DataFrame(fc, index=pd.Index(labels, name="기간"), columns=self.series)

    def stability(self) -> TableOutput:
        """동반행렬 고윳값 표(모듈러스가 모두 1보다 작으면 안정).

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> v = wf.var("v1", ["dlog(Y)", "R"], lags=2)
            >>> "안정" in v.stability().text()
            True
        """
        ev = self._require().eigenvalues()
        order = np.argsort(-np.abs(ev))
        df = pd.DataFrame({"실수부": ev.real[order], "허수부": ev.imag[order], "모듈러스": np.abs(ev)[order]})
        ok = self.fit.is_stable
        return TableOutput(df, title=f"VAR {self.name} 안정성", index=False, name=f"{self.name}_stability",
                           head=["모든 근이 단위원 안 — 안정" if ok else "⚠ 단위원 밖의 근이 있음 — 불안정"])

    def output(self) -> TableOutput:
        """식별 계수·표준오차·t값 표와 정보기준."""
        f = self._require()
        c, se = self.coefs, self.stderrs
        tab = pd.concat({s: pd.DataFrame({"계수": c[s], "표준오차": se[s], "t값": c[s] / se[s]}) for s in self.series},
                        axis=1)
        ic = f.info_criteria()
        head = [f"VAR({f.p}) · 결정항 {f.trend} · 표본 {self._wf._label(self._index[f.p])}~{self._wf._label(self._index[-1])}"
                f" ({f.nobs}기)", f"AIC {ic['aic']:.4f} · BIC {ic['bic']:.4f} · HQ {ic['hqic']:.4f} · "
                f"log|Σ| {np.linalg.slogdet(f.sigma_mle)[1]:.4f} · " + ("안정" if f.is_stable else "⚠ 불안정")]
        return TableOutput(tab, title=f"VAR {self.name}", head=head, name=self.name)

    def make_equations(self) -> list:
        """식마다 `Y c Y(-1) … @trend`를 추정 계수로 고정한 방정식 객체(이름 VAR이름_변수) — 모델 merge가 쓴다.

        식(dlog(Y) 등)으로 만든 VAR도 그 식을 종속변수로 쓴다.

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> v = wf.var("v1", ["dlog(Y)", "R"], lags=2)
            >>> [o.eq.dependent_var for o in v.make_equations()]
            ['dlog(Y)', 'R']
        """
        from .objects import EquationObject
        f = self._require()
        wf, objs = self._wf, []
        B = f.coefs
        for j, s in enumerate(self.series):
            terms = [self._lag(v, i) for i in range(1, f.p + 1) for v in self.series]
            vals = list(B[f.n_det:, j])
            head, hv = [], []
            if f.n_det >= 1:
                const = B[0, j] + (B[1, j] * (1 - self._s0) if f.n_det == 2 else 0.0)   # VAR 추세 = @trend − s0 + 1
                head, hv = ["c"], [const]
                if f.n_det == 2:
                    head.append("@trend")
                    hv.append(B[1, j])
            spec = f"{s} " + " ".join(head + terms)
            nm = f"{self.name}_eq{j + 1}".lower()
            wf._objects.pop(nm, None)
            obj = wf._register(EquationObject(wf, nm))
            obj._adopt(obj._make(spec, method="fixed", coefficients=hv + vals), spec, loud=False)
            objs.append(obj)
        return objs


class VECMObject(_Base):
    kind = "vecm"

    def to_json(self) -> dict:
        """저장용 정의(dict — 변수·차분 시차·순위·결정항)."""
        f = self.fit
        return {"type": "vecm", "name": self.name, "series": self.series, "lags_diff": f.k_diff if f else None,
                "rank": f.rank if f else None, "deterministic": f.det if f else None}

    @classmethod
    def from_json(cls, wf, d):
        """저장한 정의로 다시 추정해 되살린다."""
        o = cls(wf, d["name"])
        if d.get("rank") is not None:
            o.estimate(d["series"], d["lags_diff"], d["rank"], d["deterministic"])
        return o

    def __repr__(self):
        return f"<VECM {self.name}: {' '.join(self.series)}>"

    def estimate(self, series, lags_diff: int = 1, rank: int = 1, deterministic: str = "ci"):
        """같은 객체를 다른 설정으로 다시 추정한다(보통은 wf.vecm이 부른다).

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> _ = wf.smpl("1980Q1", "2019Q4")
            >>> k = wf.vecm("k1", ["RL", "R"], rank=1)
            >>> k.estimate(["RL", "R"], lags_diff=2, rank=1).fit.k_diff
            2
        """
        df = self._frame(series)
        self.fit = _var.fit_vecm(df.to_numpy(), int(lags_diff), int(rank), deterministic)
        self.version += 1
        say(f"[{self.name}] VECM — 변수 {len(self.series)} · 공적분 순위 {rank} · 차분 시차 {lags_diff} · "
            f"결정항 {deterministic} · 관측치 {self.fit.nobs}")
        return self

    @property
    def alpha(self) -> pd.DataFrame:
        """조정 속도 α(행 = 변수, 열 = 공적분 관계) — 균형 오차에 각 변수가 반응하는 크기."""
        f = self._require()
        return pd.DataFrame(f.alpha, index=self.series, columns=[f"EC{j + 1}" for j in range(f.rank)])

    @property
    def beta(self) -> pd.DataFrame:
        """공적분 벡터 β(행 = 변수(+관계 안 결정항), 열 = 관계, 위 r×r은 단위행렬로 정규화)."""
        f = self._require()
        toks = _var._det_tokens(f.det)
        rows = self.series + ["c"] * ("ci" in toks) + ["@trend"] * ("li" in toks)
        return pd.DataFrame(f.beta, index=rows, columns=[f"EC{j + 1}" for j in range(f.rank)])

    @property
    def gamma(self) -> pd.DataFrame:
        """단기 계수 Γ(차분 시차와 관계 밖 결정항)."""
        f = self._require()
        cols = [f"d({v})(-{i})" for i in range(1, f.k_diff + 1) for v in self.series]
        return pd.DataFrame(f.gamma, index=self.series, columns=cols)

    @property
    def sigma(self) -> pd.DataFrame:
        """잔차 공분산 Σ̂."""
        return pd.DataFrame(self._require().sigma_u, index=self.series, columns=self.series)

    def forecast(self, steps: int = 8) -> pd.DataFrame:
        """추정 표본 끝 다음부터 steps기 점 예측(수준, 행 = 기간 라벨).

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> _ = wf.smpl("1980Q1", "2019Q4")
            >>> k = wf.vecm("k1", ["RL", "R"], rank=1)
            >>> list(k.forecast(2).columns)
            ['RL', 'R']
        """
        from ..data.periods import format_period, to_period
        _steps(steps, 1, "steps")
        fc = _var.vecm_forecast(self._require(), steps)
        last = to_period(self._index[-1], self._wf.freq)
        labels = [format_period(last + i, self._wf.freq) for i in range(1, steps + 1)]
        return pd.DataFrame(fc, index=pd.Index(labels, name="기간"), columns=self.series)

    def output(self) -> TableOutput:
        """α·Γ 표와 공적분 벡터."""
        f = self._require()
        tab = pd.concat([self.alpha.add_prefix("α "), self.gamma], axis=1)
        head = [f"VECM · 공적분 순위 {f.rank} · 차분 시차 {f.k_diff} · 결정항 {f.det} · 관측치 {f.nobs}",
                "공적분 벡터 β(위 r×r = I): " + "; ".join(
                    f"EC{j + 1} = " + " + ".join(f"{v:.4f}·{n}" for n, v in self.beta.iloc[:, j].items())
                    for j in range(f.rank)),
                "Johansen 고윳값: " + ", ".join(f"{x:.4f}" for x in f.eigenvalues)]
        return TableOutput(tab, title=f"VECM {self.name}", head=head, name=self.name)

    def make_equations(self) -> list:
        """식마다 d(Y) = Σα·EC(-1) + ΣΓ·d(·)(-i) + 결정항 — 추정 계수를 고정한 방정식 객체(모델 merge가 쓴다).

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> _ = wf.smpl("1980Q1", "2019Q4")
            >>> k = wf.vecm("k1", ["RL", "R"], rank=1)
            >>> [o.eq.target for o in k.make_equations()]
            ['RL', 'R']
        """
        from .objects import EquationObject
        f = self._require()
        toks = _var._det_tokens(f.det)
        wf, objs = self._wf, []
        k = len(self.series)
        ecs = []
        for j in range(f.rank):
            parts = [f"({float(f.beta[i, j])!r})*{self._lag(v, 1)}" for i, v in enumerate(self.series)]
            r = k
            if "ci" in toks:
                parts.append(f"({float(f.beta[r, j])!r})")
                r += 1
            if "li" in toks:      # 관계 안 추세 = @trend − s0 (statsmodels 시점 표기와 맞춤)
                parts.append(f"({float(f.beta[r, j])!r})*(@trend - {self._s0})")
            ecs.append("(" + " + ".join(parts) + ")")
        for i, s in enumerate(self.series):
            terms, vals = [], []
            for j, ec in enumerate(ecs):
                terms.append(ec)
                vals.append(f.alpha[i, j])
            for lag in range(1, f.k_diff + 1):
                for m, v in enumerate(self.series):
                    terms.append(f"d({v}).t(-{lag})")
                    vals.append(f.gamma[i, (lag - 1) * k + m])
            d = 0
            if "co" in toks:
                terms.append("1")
                vals.append(f.det_coef[i, d])
                d += 1
            if "lo" in toks:
                terms.append(f"(@trend - {self._s0} + 1)")
                vals.append(f.det_coef[i, d])
            spec = f"d({s}) = " + " + ".join(f"c({n + 1})*{t}" for n, t in enumerate(terms))
            nm = f"{self.name}_eq{i + 1}".lower()
            wf._objects.pop(nm, None)
            obj = wf._register(EquationObject(wf, nm))
            obj._adopt(obj._make(spec, method="fixed", coefficients={f"c({n + 1})": v for n, v in enumerate(vals)}),
                       spec, loud=False)
            objs.append(obj)
        return objs
