#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""시스템 객체 — 여러 식을 함께 추정한다(SUR·3SLS·FIML·식 사이 제약) (DECISIONS D22).

    s = wf.system("cons_inv")
    s.append("log(CN) = c(1) + c(2)*log(Y) + c(3)*log(CN(-1))",
             "log(I) = c(4) + c(2)*log(Y) + c(5)*log(I(-1))",               # c(2) 공유 = 식 사이 제약
             "@inst log(Y(-1)) log(Y(-2))")                                  # 공통 도구(tsls·3sls)
    s.sur()                     # 또는 .ols() .tsls() .three_sls() .fiml(), restrict=["c(3) = c(5)"]
    s.wald("c(3) = c(5)")
    wf.model("m").merge(s)      # 추정한 계수를 고정한 식들로 모델에

식은 계수 c(n)을 쓴 꼴(`Y = c(1) + c(2)*X`)이나 추정식 꼴(`Y c X`, 계수 번호는 이어서 자동)로 쓴다. 여러 식에 같은 c(n)이 있으면
같은 계수다(식 사이 제약). 계수에 비선형인 식(`Y = c(1) + c(2)*X^c(3)`)도 된다(D64) — 그때는 비선형 최소제곱 꼴로 풀고(NL-OLS·NL-SUR·
NL-2SLS·NL-3SLS·비선형 FIML), 시작값은 start=…나 식 끝의 `@start …`(그 식의 c(n) 차례), 없으면 0. 모든 식이 계수에 선형이면 선형 추정 그대로.
식 끝의 `@inst …`는 그 식만의 도구, `@inst …` 한 줄은 모든 식의 도구(상수항은 늘 포함).
"""

import re
from typing import Dict, List, Optional, Sequence

import numpy as np
import pandas as pd
from scipy import stats

from ..estimation.equation import Equation
from ..formula import ir
from ..formula.parser import DSLError, classify_line, extract_directives, split_terms
from ..stats import diagnostics as _diag
from ..stats import system as _sys
from ..stats.result import TestResult
from .output import TableOutput, say, spool
from .runtime import quiet

_LABEL = {"ols": "시스템 최소제곱(OLS)", "sur": "SUR(실행 가능한 GLS)", "sur-it": "SUR(반복 — 정규 최우)",
          "tsls": "시스템 2단계 최소제곱", "3sls": "3단계 최소제곱(3SLS)", "fiml": "완전정보 최우(FIML)"}


class _SysEq:
    """시스템 안의 식 하나: 원문, c(n) 꼴 글자, IR(좌변·우변), 목표변수, 도구."""

    def __init__(self, text, ctext, lhs, rhs, target, coef_labels, inst, start=None):
        self.text, self.ctext, self.lhs, self.rhs = text, ctext, lhs, rhs
        self.target, self.coef_labels, self.inst = target, coef_labels, inst
        self.start = dict(start or {})                 # 식 끝의 @start — {계수 번호: 시작값}
        self.nonlinear = any(ir.coef_indices(ir.deriv(rhs, ir.Coef(k))) for k in ir.coef_indices(rhs))

    @property
    def coefs(self) -> List[int]:
        return sorted(ir.coef_indices(self.rhs))


class SystemObject:
    kind = "system"

    def __init__(self, wf, name: str):
        self._wf = wf
        self.name = name
        self._lines: List[str] = []
        self._inst: List[str] = []
        self.fit: Optional[_sys.SystemFit] = None
        self.method: Optional[str] = None
        self.options: dict = {}
        self.version = 0
        self._eqs: Optional[List[_SysEq]] = None
        self._sample = None

    def __repr__(self):
        return f"<시스템 {self.name}: 식 {len(self._lines)}개" + (f", {self.method}" if self.method else "") + ">"

    # ---- 식 ---------------------------------------------------------------
    def append(self, *lines: str):
        """식을 더한다(여러 줄 글자도 됨). 추정식 꼴(`Y c X` — 계수 번호는 이어서 자동)이나 `c(n)` 꼴(`Y = c(1) + c(2)*X`)로 쓴다.

        같은 c(n)을 두 식에 쓰면 그 계수가 같게 묶인다(식 사이 제약). 식 끝의 `@inst …`는 그 식만의 도구, `@inst …`만 있는 줄은
        모든 식의 도구다(상수항은 늘 포함). 계수에 비선형인 식도 된다(D64 — 시작값은 식 끝의 `@start …`). 항등식·`ar(…)`·`pdl(…)`·
        `@smpl`·`@coef`는 넣지 않는다(항등식은 모델에서 append, 표본은 wf.smpl).

        예
            >>> wf = eqn.datasets.load("klein_like")
            >>> s = wf.system("kl")
            >>> _ = s.append("CONS c PR PR(-1) WP+WG", "I c PR PR(-1) K(-1)", "WP c X X(-1) A",
            ...              "@inst G T WG A PR(-1) K(-1) X(-1)")
            >>> len(s.equations)
            3
        """
        for text in lines:
            for line in str(text).splitlines():
                line = line.split("#", 1)[0].strip()
                if not line:
                    continue
                if re.match(r"^@inst\b", line, re.IGNORECASE):
                    self._inst.extend(split_terms(line[5:].strip()))
                else:
                    self._lines.append(line)
        self._eqs, self.fit, self.method = None, None, None
        self.version += 1
        return self

    @property
    def equations(self) -> List[str]:
        """시스템의 식(글자 목록, @inst 줄 제외)."""
        return list(self._lines)

    def _parse(self) -> List[_SysEq]:
        if self._eqs is None:
            self._eqs = quiet(self._parse_lines)
        return self._eqs

    def _parse_lines(self) -> List[_SysEq]:
        if not self._lines:
            raise ValueError(f"시스템 {self.name}에 식이 없습니다(.append(...))")
        data = self._wf._data
        parsed, used = [], set()
        for line in self._lines:                       # 1차: c(n) 꼴의 번호를 모은다
            body, d = extract_directives(line)
            if d.get("smpl") or d.get("coef"):
                raise ValueError(f"시스템 식에는 @smpl·@coef를 쓰지 않습니다(표본은 wf.smpl, 계수는 추정한다) — {line}")
            if re.search(r"\bar\s*\(", body, re.IGNORECASE):
                raise ValueError(f"시스템 식에는 ar(…) 오차항을 쓸 수 없습니다 — {line}")
            try:
                if classify_line(body) == "nls":
                    e = Equation(body, data, method="nls")
                    e._parse()
                    used |= set(e._coef_numbers)
                    parsed.append(("nls", line, body, d, e))
                    continue
                if classify_line(body) == "identity":
                    raise ValueError(f"시스템에는 항등식을 넣지 않습니다(모델에서 .append) — {line}")
                e = Equation(body, data)
                e._parse()
            except (KeyError, IndexError) as ex:
                raise ValueError(f"시스템 식을 읽을 수 없습니다 — {line} ({ex})") from None
            if e.ar_lags or e.kind != "estimated":
                raise ValueError(f"시스템 식에는 ar(…) 오차항을 쓸 수 없습니다 — {line}")
            if e.pdl_terms:
                raise ValueError(f"시스템 식에는 pdl(…)을 쓸 수 없습니다(다항 분포시차는 식 하나에서) — {line}")
            parsed.append(("ls", line, body, d, e))
        nxt = max(used, default=0) + 1
        out = []
        for kind, line, body, d, e in parsed:
            inst = list(d.get("inst") or [])
            if kind == "nls":
                rhs, labels = e.rhs_template, {k: f"c({k})" for k in e._coef_numbers}
                ctext = body
            else:
                terms = dict(zip(e.independent_vars, e.term_irs))
                rhs, labels, parts = None, {}, []
                for nm in e.coef_names:
                    k = nxt
                    nxt += 1
                    node = ir.Coef(k) if nm == "const" else ir.mul(ir.Coef(k), terms[nm])
                    rhs = node if rhs is None else ir.Bin("+", rhs, node)
                    labels[k] = "c" if nm == "const" else nm
                    parts.append(f"c({k})" if nm == "const" else f"c({k})*({nm})")
                ctext = f"{e.dependent_var} = " + " + ".join(parts)
            start = {}
            if d.get("start"):
                if kind != "nls":
                    raise ValueError(f"@start는 계수 c(n)을 쓴 식에만 — {line}")
                if len(d["start"]) != len(e._coef_numbers):
                    raise ValueError(f"@start 값 {len(d['start'])}개 ≠ 계수 {len(e._coef_numbers)}개 — {line}")
                start = {k: float(v) for k, v in zip(e._coef_numbers, d["start"])}
            out.append(_SysEq(line, ctext, e.lhs_ir, rhs, e.target, labels, inst, start))
        targets = [q.target for q in out]
        dup = sorted({t for t in targets if targets.count(t) > 1})
        if dup:
            raise ValueError(f"같은 목표변수의 식이 둘 이상입니다: {dup}")
        return out

    # ---- 자료 -------------------------------------------------------------
    def _arrays(self, inst_override=None, need_inst=False, need_jac=False):
        eqs = self._parse()
        wf = self._wf
        frame = wf._data.data
        T_all = len(frame)
        get = lambda n: frame[n].to_numpy(dtype=float)  # noqa: E731
        coefs = sorted(set().union(*(q.coefs for q in eqs)))
        pos = {k: j for j, k in enumerate(coefs)}
        zero = {k: 0.0 for k in coefs}
        ys, Xs, Zs, ok = [], [], [], np.ones(T_all, dtype=bool)
        for q in eqs:
            y = ir.evaluate(q.lhs, get) - ir.evaluate(q.rhs, get, zero, length=T_all)
            X = np.zeros((T_all, len(coefs)))
            for k in q.coefs:
                X[:, pos[k]] = ir.evaluate(ir.deriv(q.rhs, ir.Coef(k)), get, length=T_all)
            ok &= np.isfinite(y) & np.isfinite(X[:, [pos[k] for k in q.coefs]]).all(axis=1)
            ys.append(y)
            Xs.append(X)
            if need_inst:
                terms = list(inst_override) if inst_override else (q.inst or self._inst)
                if not terms:
                    raise ValueError(f"도구변수가 없습니다 — 식 '{q.text}'(식 끝 @inst … 또는 @inst 줄, inst=[…])")
                Zf = _eval_terms(wf, terms)
                Z = np.column_stack([np.ones(T_all), Zf]) if Zf.size else np.ones((T_all, 1))
                ok &= np.isfinite(Z).all(axis=1)
                Zs.append(Z)
        s, e = wf._bounds()
        win = np.zeros(T_all, dtype=bool)
        win[s:e + 1] = True
        ok &= win
        rows = np.flatnonzero(ok)
        if len(rows) <= len(coefs) // len(eqs) + 1:
            raise ValueError(f"모든 식이 함께 관측되는 기간이 너무 짧습니다({len(rows)}기)")
        out = {"coefs": coefs, "rows": rows, "ys": [y[rows] for y in ys], "Xs": [X[rows] for X in Xs],
               "Zs": [Z[rows] for Z in Zs] if need_inst else None}
        if need_jac:
            m = len(eqs)
            A = np.zeros((len(rows), m, m))
            B = np.zeros((len(coefs), len(rows), m, m))
            for i, q in enumerate(eqs):
                resid = ir.sub(q.lhs, q.rhs)
                for j, t in enumerate(q2.target for q2 in eqs):
                    d = ir.deriv(resid, ir.Var(t, 0))
                    A[:, i, j] = np.broadcast_to(ir.evaluate(d, get, zero, length=T_all), (T_all,))[rows]
                    for k in ir.coef_indices(d):
                        B[pos[k], :, i, j] = ir.evaluate(ir.deriv(d, ir.Coef(k)), get, length=T_all)[rows]
            out["A"], out["B"] = A, B
        return out

    @property
    def nonlinear(self) -> bool:
        """계수에 비선형인 식이 있나(그러면 비선형 추정 — D64)."""
        return any(q.nonlinear for q in self._parse())

    def _start(self, coefs, start=None) -> np.ndarray:
        """시작값 — start(사전 {'c(3)': 0.5} · {3: 0.5} · 계수 차례의 목록) > 식 끝의 @start > 0."""
        vals = {}
        for q in self._parse():
            for k, v in q.start.items():
                vals.setdefault(k, v)
        if start is not None:
            if isinstance(start, dict):
                for key, v in start.items():
                    if isinstance(key, int) and not isinstance(key, bool):
                        k = key
                    else:
                        mm = re.fullmatch(r"\s*(?:c\s*\(\s*(\d+)\s*\)|(\d+))\s*", str(key), re.IGNORECASE)
                        if not mm:
                            raise ValueError(f"시작값의 계수 이름 {key!r} — 'c(3)' 꼴이나 번호 3")
                        k = int(mm[1] or mm[2])
                    if k not in coefs:
                        raise ValueError(f"시스템에 없는 계수의 시작값: c({k})")
                    vals[k] = float(v)
            else:
                arr = np.asarray(start, dtype=float).ravel()
                if arr.size != len(coefs):
                    raise ValueError(f"start 길이 {arr.size} ≠ 계수 {len(coefs)}개({', '.join(f'c({k})' for k in coefs)})")
                vals = dict(zip(coefs, arr))
        return np.array([vals.get(k, 0.0) for k in coefs], dtype=float)

    def _nl_setup(self, inst_override=None, need_inst=False, need_jac=False, start=None):
        """계수에 비선형인 시스템의 표본과 함수들 — 잔차 · 기울기 ∂fᵢ/∂b(· FIML이면 Jₜ = ∂εₜ/∂yₜ와 ∂Jₜ/∂b)."""
        eqs = self._parse()
        wf = self._wf
        frame = wf._data.data
        T_all = len(frame)
        get = lambda n: frame[n].to_numpy(dtype=float)  # noqa: E731
        coefs = sorted(set().union(*(q.coefs for q in eqs)))
        pos = {k: j for j, k in enumerate(coefs)}
        ok = np.ones(T_all, dtype=bool)
        lhs = []
        Zs = []
        for q in eqs:
            for node in (q.lhs, q.rhs):
                for name, lag in ir.leaves(node):
                    ok &= np.isfinite(ir.shift_array(get(name), lag))
            lhs.append(ir.evaluate(q.lhs, get))
            if need_inst:
                terms = list(inst_override) if inst_override else (q.inst or self._inst)
                if not terms:
                    raise ValueError(f"도구변수가 없습니다 — 식 '{q.text}'(식 끝 @inst … 또는 @inst 줄, inst=[…])")
                Zf = _eval_terms(wf, terms)
                Z = np.column_stack([np.ones(T_all), Zf]) if Zf.size else np.ones((T_all, 1))
                ok &= np.isfinite(Z).all(axis=1)
                Zs.append(Z)
        s, e = wf._bounds()
        win = np.zeros(T_all, dtype=bool)
        win[s:e + 1] = True
        ok &= win
        before = int(ok.sum())
        for i, q in enumerate(eqs):                      # 좌변과 (시작값의) 우변이 수가 아닌 기간도 뺀다 — log(음수) 등
            ok &= np.isfinite(lhs[i])
            if start is not None:
                c0 = {k: float(start[j]) for j, k in enumerate(coefs)}
                with np.errstate(all="ignore"):
                    ok &= np.isfinite(np.broadcast_to(ir.evaluate(q.rhs, get, c0, length=T_all), (T_all,)))
        rows = np.flatnonzero(ok)
        dropped = before - len(rows)
        if len(rows) <= len(coefs) // len(eqs) + 1:
            raise ValueError(f"모든 식이 함께 관측되는 기간이 너무 짧습니다({len(rows)}기)")
        dnodes = [{k: ir.deriv(q.rhs, ir.Coef(k)) for k in q.coefs} for q in eqs]

        def cd(b):
            return {k: float(b[pos[k]]) for k in coefs}

        def resid(b):
            c = cd(b)
            return np.column_stack([(lhs[i] - ir.evaluate(q.rhs, get, c, length=T_all))[rows] for i, q in enumerate(eqs)])

        def jac(b):
            c = cd(b)
            out = []
            for i, q in enumerate(eqs):
                G = np.zeros((len(rows), len(coefs)))
                for k, node in dnodes[i].items():
                    G[:, pos[k]] = np.broadcast_to(ir.evaluate(node, get, c, length=T_all), (T_all,))[rows]
                out.append(G)
            return out
        a = {"coefs": coefs, "rows": rows, "resid": resid, "jac": jac, "Zs": [Z[rows] for Z in Zs] if need_inst else None,
             "dropped": dropped}
        if need_jac:
            m = len(eqs)
            targets = [q.target for q in eqs]
            Jn = [[ir.deriv(ir.sub(q.lhs, q.rhs), ir.Var(t, 0)) for t in targets] for q in eqs]
            dJn = [[{k: ir.deriv(Jn[i][j], ir.Coef(k)) for k in ir.coef_indices(Jn[i][j])} for j in range(m)] for i in range(m)]

            def J_fn(b):
                c = cd(b)
                J = np.zeros((len(rows), m, m))
                for i in range(m):
                    for j in range(m):
                        J[:, i, j] = np.broadcast_to(ir.evaluate(Jn[i][j], get, c, length=T_all), (T_all,))[rows]
                return J

            def dJ_fn(b):
                c = cd(b)
                D = np.zeros((len(coefs), len(rows), m, m))
                for i in range(m):
                    for j in range(m):
                        for k, node in dJn[i][j].items():
                            D[pos[k], :, i, j] = np.broadcast_to(ir.evaluate(node, get, c, length=T_all), (T_all,))[rows]
                return D
            a["J"], a["dJ"] = J_fn, dJ_fn
        return a

    def _restrict(self, restrict, coefs):
        if not restrict:
            return None, None
        if isinstance(restrict, str):
            restrict = [r.strip() for r in restrict.split(",")]
        R, q = _diag.parse_restrictions(list(restrict), max(coefs))
        extra = [i + 1 for i in range(R.shape[1]) if i + 1 not in coefs and np.any(R[:, i] != 0)]
        if extra:
            raise ValueError(f"시스템에 없는 계수: {['c(%d)' % i for i in extra]}")
        return R[:, [k - 1 for k in coefs]], q

    # ---- 추정 -------------------------------------------------------------
    def _run(self, method, restrict=None, inst=None, **opts):
        iv = method in ("tsls", "3sls")
        if self.nonlinear:
            return self._run_nonlinear(method, restrict, inst, **opts)
        opts.pop("start", None) if method != "fiml" else None
        a = self._arrays(inst, need_inst=iv, need_jac=method == "fiml")
        R, q = self._restrict(restrict, a["coefs"])
        if method == "fiml":
            start = opts.pop("start", None)
            if start is None:
                start = _sys.fit_linear(a["ys"], a["Xs"], "ols", R=R, q=q).params
            else:
                start = self._start(a["coefs"], start)
            _sys._check_sigma(_sys._sigma(np.column_stack([a["ys"][i] - a["Xs"][i] @ start for i in range(len(a["ys"]))])))
            try:
                fit = _sys.fit_fiml(a["ys"], a["Xs"], a["A"], a["B"], np.asarray(start, dtype=float), R=R, q=q)
            except np.linalg.LinAlgError:
                raise ValueError("FIML: 잔차 공분산이나 야코비안이 특이합니다(잔차가 0인 식 · 서로 같은 식) — 식을 확인하세요") from None
        else:
            fit = _sys.fit_linear(a["ys"], a["Xs"], method, Zs=a["Zs"], R=R, q=q, **opts)
        self.fit, self._sample, self._coefs = fit, a["rows"], a["coefs"]
        key = "sur-it" if method == "sur" and opts.get("iterate") else method
        self.method = key
        self.options = {"method": method, "restrict": _restrict_list(restrict),
                        "inst": list(inst) if inst else None,
                        **{k: v for k, v in opts.items() if k in ("iterate",)}}
        self.version += 1
        T = len(a["rows"])
        say(f"[{self.name}] {_LABEL[key]} — 식 {len(a['ys'])} · 계수 {len(a['coefs'])} · 표본 {T}기"
            + (f" · 로그우도 {fit.loglik:.2f}" if np.isfinite(fit.loglik) else ""))
        return self

    def _run_nonlinear(self, method, restrict=None, inst=None, **opts):
        """계수에 비선형인 시스템(D64) — NL-OLS·NL-SUR·NL-2SLS·NL-3SLS·비선형 FIML."""
        iv = method in ("tsls", "3sls")
        given = opts.pop("start", None)
        coefs = sorted(set().union(*(q_.coefs for q_ in self._parse())))
        start = self._start(coefs, given)
        a = self._nl_setup(inst, need_inst=iv, need_jac=method == "fiml", start=start)
        R, q = self._restrict(restrict, a["coefs"])
        if method == "fiml":
            if given is None and not any(q_.start for q_ in self._parse()):
                start = _sys.fit_nonlinear(a["resid"], a["jac"], start, "ols", R=R, q=q).params
            fit = _sys.fit_fiml_nonlinear(a["resid"], a["jac"], a["J"], a["dJ"], start, R=R, q=q)
        else:
            fit = _sys.fit_nonlinear(a["resid"], a["jac"], start, method, Zs=a["Zs"], R=R, q=q,
                                     iterate=bool(opts.get("iterate")))
        self.fit, self._sample, self._coefs = fit, a["rows"], a["coefs"]
        key = "sur-it" if method == "sur" and opts.get("iterate") else method
        self.method = key
        self.options = {"method": method, "restrict": _restrict_list(restrict),
                        "inst": list(inst) if inst else None,
                        **({"start": [float(x) for x in np.ravel(given)] if not isinstance(given, dict)
                            else {str(k): float(v) for k, v in given.items()}} if given is not None else {}),
                        **{k: v for k, v in opts.items() if k in ("iterate",)}}
        self.version += 1
        T = len(a["rows"])
        say(f"[{self.name}] {_LABEL[key]} — 비선형 · 식 {fit.resid.shape[1]} · 계수 {len(a['coefs'])} · 표본 {T}기"
            + (f"(식이 수가 아닌 {a['dropped']}기는 뺐다)" if a.get("dropped") else "")
            + (f" · 로그우도 {fit.loglik:.2f}" if np.isfinite(fit.loglik) else "")
            + (" · ⚠ 식별되지 않는 계수가 있어 표준오차 없음(곱으로만 든 계수 등)" if not fit.extra.get("identified", True)
               else "" if fit.extra.get("converged", True) else " · ⚠ 수렴하지 않음 — 시작값을 바꿔 보세요"))
        return self

    def ols(self, restrict=None, start=None):
        """식마다 최소제곱 — 공유 계수·restrict 제약은 함께 반영하고, 공분산은 식 사이 상관을 반영한 샌드위치.

        예
            >>> wf = eqn.datasets.load("klein_like")
            >>> s = wf.system("kl")
            >>> _ = s.append("CONS c PR PR(-1) WP+WG", "I c PR PR(-1) K(-1)", "WP c X X(-1) A",
            ...              "@inst G T WG A PR(-1) K(-1) X(-1)")
            >>> round(float(s.ols().coefs["c(2)"]), 2)
            0.25
        """
        return self._run("ols", restrict, start=start)

    def sur(self, iterate: bool = False, restrict=None, start=None):
        """SUR(Zellner, 실행 가능한 GLS) — OLS 잔차의 Σ̂로 GLS. iterate=True면 Σ̂·계수를 수렴할 때까지(= 정규 최우).
        계수에 비선형인 식이 있으면 NL-SUR(εᵀ(Σ̂⁻¹⊗I)ε 최소 — Σ̂는 NL-OLS 잔차에서), start는 시작값(사전·목록 — 식의 @start보다 앞).

        예
            >>> wf = eqn.datasets.load("klein_like")
            >>> s = wf.system("kl")
            >>> _ = s.append("CONS c PR PR(-1) WP+WG", "I c PR PR(-1) K(-1)", "WP c X X(-1) A",
            ...              "@inst G T WG A PR(-1) K(-1) X(-1)")
            >>> s.sur(iterate=True).method
            'sur-it'
        """
        return self._run("sur", restrict, iterate=iterate, start=start)

    def tsls(self, inst: Sequence[str] = None, restrict=None, start=None):
        """시스템 2단계 최소제곱 — 식마다 도구변수로 투영해 추정. inst를 주면 모든 식에 그 도구.
        계수에 비선형인 식이 있으면 NL-2SLS(Σᵢ εᵢᵀP_Zᵢεᵢ 최소), start는 시작값.

        오류
            ValueError: 도구가 없는 식, 도구가 계수보다 적은 식

        예
            >>> wf = eqn.datasets.load("klein_like")
            >>> s = wf.system("kl")
            >>> _ = s.append("CONS c PR PR(-1) WP+WG", "I c PR PR(-1) K(-1)", "WP c X X(-1) A",
            ...              "@inst G T WG A PR(-1) K(-1) X(-1)")
            >>> round(float(s.tsls().coefs["c(2)"]), 2)
            0.16
        """
        return self._run("tsls", restrict, inst=_split_inst(inst), start=start)

    def three_sls(self, inst: Sequence[str] = None, restrict=None, iterate: bool = False, start=None):
        """3단계 최소제곱 — 2SLS 잔차의 Σ̂로 투영 자료에 GLS(식 사이 오차 상관까지 쓴다). iterate=True면 반복.
        계수에 비선형인 식이 있으면 NL-3SLS(GMM 꼴 mᵀS⁻¹m — 도구가 모든 식에 같으면 εᵀ(Σ̂⁻¹⊗P_Z)ε), start는 시작값.

        예
            >>> wf = eqn.datasets.load("klein_like")
            >>> s = wf.system("kl")
            >>> _ = s.append("CONS c PR PR(-1) WP+WG", "I c PR PR(-1) K(-1)", "WP c X X(-1) A",
            ...              "@inst G T WG A PR(-1) K(-1) X(-1)")
            >>> s.three_sls().coefs.round(2)[["c(2)", "c(6)"]].tolist()
            [0.16, -0.06]
        """
        return self._run("3sls", restrict, inst=_split_inst(inst), iterate=iterate, start=start)

    def fiml(self, restrict=None, start=None):
        """완전정보 최우 — 집중 로그우도 −(T/2)log|Σ̂| + Σ log|det ∂ε/∂y|를 최대화(해석적 기울기 BFGS + Newton 마무리).
        계수에 비선형인 식이 있으면 비선형 FIML(야코비안과 그 계수 미분을 식의 기호 미분으로 — 시작값 기본은 NL-OLS).

        내생변수는 시스템 식의 목표변수다. 시작값 기본은 시스템 OLS, 공분산은 관측 정보(헤시안). 시스템에는 항등식을 넣을 수 없으므로
        항등식이 정하는 같은 기 내생변수(예: Klein 모형의 이윤·총수요)가 설명변수에 있으면 그것을 외생으로 다룬다 — 그런 모형은
        3SLS를 쓰거나 항등식을 대입해 식을 다시 쓴다(도구 목록이 있으면 도구에 없는 같은 기 설명변수를 경고한다).

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> s = wf.system("s2")
            >>> _ = s.append("I c Y(-1) R", "RL c R")
            >>> round(float(s.fiml().coefs["c(3)"]), 2)                # 두 식이 함께 관측되는 1980Q1~
            -1.0
        """
        self._warn_fiml_exogeneity()
        return self._run("fiml", restrict, start=start)

    def _warn_fiml_exogeneity(self):
        eqs = self._parse()
        targets = {q.target.upper() for q in eqs}
        terms = list(self._inst) + [t for q in eqs for t in (q.inst or [])]
        if not terms:
            return
        inst = {t.strip().upper() for t in terms if re.fullmatch(r"[A-Za-z_]\w*", t.strip())}
        now = sorted({n for q in eqs for n, lag in ir.leaves(q.rhs) if lag == 0 and n.upper() not in targets
                      and n.upper() not in inst})
        if now:
            from ..log import workfile as _wlog
            _wlog.warning(f"[WARN] {self.name}: FIML은 시스템 식의 목표변수만 내생으로 봅니다 — 도구변수에 없는 같은 기 "
                          f"설명변수 {', '.join(now)}은(는) 외생으로 다룹니다(항등식이 정하는 내생변수라면 3SLS를 쓰세요)")

    # ---- 결과 -------------------------------------------------------------
    def _require(self):
        if self.fit is None:
            raise RuntimeError(f"시스템 {self.name}이(가) 아직 추정되지 않았습니다(.sur() 등)")
        return self.fit

    def _labels(self) -> List[str]:
        out = []
        for k in self._coefs:
            where = [f"식{i + 1}:{q.coef_labels[k]}" for i, q in enumerate(self._parse()) if k in q.coef_labels]
            out.append(" · ".join(where))
        return out

    @property
    def coefs(self) -> pd.Series:
        """계수(Series, 이름 c(1)…)."""
        return pd.Series(self._require().params, index=[f"c({k})" for k in self._coefs])

    @property
    def stderrs(self) -> pd.Series:
        """계수 표준오차(Series)."""
        return pd.Series(self._require().bse, index=[f"c({k})" for k in self._coefs])

    @property
    def zstats(self) -> pd.Series:
        """계수의 z값(Series — 시스템 추정은 정규 근사)."""
        return self.coefs / self.stderrs

    @property
    def pvalues(self) -> pd.Series:
        """계수 = 0 검정의 p값(Series, 정규 근사)."""
        return pd.Series(2 * stats.norm.sf(np.abs(self.zstats.to_numpy())), index=self.coefs.index)

    def cov(self) -> pd.DataFrame:
        """계수 공분산 행렬(DataFrame)."""
        idx = self.coefs.index
        return pd.DataFrame(self._require().cov, index=idx, columns=idx)

    @property
    def resid(self) -> pd.DataFrame:
        """식별 구조 잔차(표본 기간 × 식, 열 이름 = 목표변수)."""
        fit = self._require()
        idx = self._wf.data.index[self._sample]
        return pd.DataFrame(fit.resid, index=idx, columns=[q.target for q in self._parse()])

    @property
    def sigma(self) -> pd.DataFrame:
        """잔차 공분산 Σ̂ = ÊᵀÊ/T."""
        cols = [q.target for q in self._parse()]
        return pd.DataFrame(self._require().sigma, index=cols, columns=cols)

    def equation_stats(self) -> pd.DataFrame:
        """식별 R²·회귀 표준오차·DW·관측치."""
        fit = self._require()
        rows = []
        for i, q in enumerate(self._parse()):
            e = fit.resid[:, i]
            lhs = ir.evaluate(q.lhs, lambda n: self._wf._data.data[n].to_numpy(dtype=float))[self._sample]
            tss = float(np.sum((lhs - lhs.mean()) ** 2))
            k = len(q.coefs)
            rows.append({"식": q.text, "목표": q.target, "R²": 1 - float(e @ e) / tss if tss > 0 else np.nan,
                         "회귀 표준오차": float(np.sqrt(e @ e / max(len(e) - k, 1))),
                         "DW": float(np.sum(np.diff(e) ** 2) / (e @ e)) if e @ e > 0 else np.nan, "관측치": len(e)})
        return pd.DataFrame(rows).set_index("목표")

    def output(self) -> TableOutput:
        """계수 표와 식별 통계."""
        fit = self._require()
        p = self.pvalues
        df = pd.DataFrame({"식·항": self._labels(), "계수": self.coefs, "표준오차": self.stderrs, "z값": self.zstats,
                           "p값": p, "": [("***" if v < .01 else "**" if v < .05 else "*" if v < .1 else "") for v in p]})
        df.index.name = "계수"
        idx = self._wf.data.index[self._sample]
        head = [f"추정법: {_LABEL[self.method]} · 식 {len(self._parse())} · 표본 {self._wf._label(idx[0])}~"
                f"{self._wf._label(idx[-1])} ({len(idx)}기, 모든 식 공통)"]
        if self.options.get("restrict"):
            head.append("제약: " + " · ".join(self.options["restrict"]))
        if fit.iterations > 1:
            head.append(f"반복 {fit.iterations}회")
        st = self.equation_stats()
        foot = [f"{t}: R² {r['R²']:.4f} · 표준오차 {r['회귀 표준오차']:.5g} · DW {r['DW']:.3f}" for t, r in st.iterrows()]
        if np.isfinite(fit.loglik):
            foot.append(f"로그우도 {fit.loglik:.3f} · log|Σ̂| {np.linalg.slogdet(fit.sigma)[1]:.4f}")
        foot.append("z값·p값은 정규분포(점근) · 유의수준 *** 1% ** 5% * 10%")
        return TableOutput(df, title=f"시스템 {self.name}", head=head, foot=foot, name=self.name)

    def show(self):
        """결과 표를 보인다."""
        spool.show(self.output())

    def _repr_html_(self):
        return self.output().html() if self.fit is not None else None

    def wald(self, *restrictions: str) -> TestResult:
        """시스템 계수(c(n))의 선형 제약 Wald 검정(χ²). 이미 추정에 넣은 제약을 다시 검정하면 오류로 알려 준다.

        예
            >>> wf = eqn.datasets.load("klein_like")
            >>> s = wf.system("kl")
            >>> _ = s.append("CONS c PR PR(-1) WP+WG", "I c PR PR(-1) K(-1)", "WP c X X(-1) A",
            ...              "@inst G T WG A PR(-1) K(-1) X(-1)")
            >>> _ = s.three_sls()
            >>> s.wald("c(3) = c(7)").reject(0.05)
            True
        """
        if len(restrictions) == 1 and "," in restrictions[0]:
            restrictions = tuple(r.strip() for r in restrictions[0].split(","))
        fit = self._require()
        R, q = self._restrict(list(restrictions), self._coefs)
        w = _sys.wald(fit, R, q)
        r = TestResult("시스템 Wald 계수 제약 검정", w["chi2"], w["chi2_p"], null=" 그리고 ".join(restrictions),
                       rows={"제약 수": w["r"]}, info={"추정법": _LABEL[self.method]})
        say(f"[{self.name}] {r.name}: χ² {r.statistic:.4f}, p={r.pvalue:.4f}")
        return r

    def make_equations(self) -> list:
        """추정한 계수를 고정한 방정식 객체들(이름 시스템_목표변수, 소문자)을 워크파일에 만든다 — 모델 merge가 쓴다.

        예
            >>> wf = eqn.datasets.load("klein_like")
            >>> s = wf.system("kl")
            >>> _ = s.append("CONS c PR PR(-1) WP+WG", "I c PR PR(-1) K(-1)", "WP c X X(-1) A",
            ...              "@inst G T WG A PR(-1) K(-1) X(-1)")
            >>> _ = s.three_sls()
            >>> [o.name for o in s.make_equations()]
            ['kl_cons', 'kl_i', 'kl_wp']
        """
        from .objects import EquationObject
        self._require()
        wf, vals = self._wf, dict(zip(self._coefs, self.fit.params))
        objs = []
        for q in self._parse():
            nm = f"{self.name}_{q.target}".lower()
            obj = wf._objects.get(nm)
            if obj is None or not isinstance(obj, EquationObject):
                wf._objects.pop(nm, None)
                obj = wf._register(EquationObject(wf, nm))
            coefs = {f"c({k})": vals[k] for k in q.coefs}
            obj._adopt(obj._make(q.ctext, method="fixed", coefficients=coefs), q.ctext, loud=False)
            objs.append(obj)
        return objs

    # ---- 저장 -------------------------------------------------------------
    def to_json(self) -> dict:
        """저장용 정의(dict — 식·도구·추정 설정). 열 때 같은 설정으로 다시 추정한다."""
        return {"type": "system", "name": self.name, "lines": list(self._lines), "inst": list(self._inst),
                "options": dict(self.options) if self.method else None}

    @classmethod
    def from_json(cls, wf, d: dict) -> "SystemObject":
        """저장한 정의로 시스템 객체를 되살린다(워크파일 열기가 쓴다)."""
        s = cls(wf, d["name"])
        s._lines, s._inst = list(d.get("lines") or []), list(d.get("inst") or [])
        opts = d.get("options")
        if opts:
            opts = dict(opts)
            method = opts.pop("method")
            quiet(lambda: s._run(method, opts.pop("restrict", None), inst=opts.pop("inst", None), **opts))
        return s


def _restrict_list(restrict):
    """restrict(글자 'c(2) = c(5), c(3) = 0' · 목록) → 목록(저장·표 머리용). 없으면 None."""
    if not restrict:
        return None
    if isinstance(restrict, str):
        return [r.strip() for r in restrict.split(",") if r.strip()]
    return [str(r) for r in restrict]


def _split_inst(inst):
    if inst is None:
        return None
    return split_terms(inst) if isinstance(inst, str) else list(inst)


def _eval_terms(wf, terms: Sequence[str]) -> np.ndarray:
    """도구 항들(DSL)을 전 기간 배열로 — 방정식과 같은 규칙(지시자·시차 범위·대소문자). 상수항 c는 빼고 늘 따로 넣는다."""
    terms = [t for t in terms if t.strip().lower() != "c"]
    if not terms:
        return np.empty((len(wf.data), 0))
    host = Equation(f"{wf._data.data.columns[0]} c", wf._data)   # 항 계산 규칙만 빌린다(추정하지 않음)
    return host.evaluate_terms(terms).to_numpy(dtype=float)
