#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`equion check` — 실행(추정·풀이) 없이 입력을 검사한다.

- 방정식 파일(.txt): 줄마다 문법·분류(추정식/항등식/NLS), 모델 구조(목표변수 중복·미지 변수·정방성·
  블록), 데이터를 주면 변수 존재와 표본 구간의 결측 입력까지.
- 스크립트(.py): Python 문법만 확인한다(실행하지 않는다).
"""

import os
from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np

from ..formula import ir
from ..formula.ast_formula import _DEF_RE, _apply_macros, canonicalize_columns
from ..formula.parser import DSLError, convert_at_functions, is_identity, normalize, split_equation
from ..system.analyzer import ModelSystem, StructureError, SystemEquation


@dataclass
class Issue:
    level: str                # 'error' | 'warning'
    message: str
    line: Optional[int] = None
    text: str = ""


@dataclass
class CheckReport:
    path: str
    kind: str                 # 'equations' | 'script'
    issues: List[Issue] = field(default_factory=list)
    info: dict = field(default_factory=dict)

    @property
    def errors(self) -> List[Issue]:
        return [i for i in self.issues if i.level == "error"]

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict:
        return {"path": self.path, "kind": self.kind, "ok": self.ok, "info": self.info,
                "issues": [vars(i) for i in self.issues]}

    def text(self) -> str:
        lines = [f"검사: {self.path} ({'방정식 파일' if self.kind == 'equations' else '스크립트'})"]
        for k, v in self.info.items():
            lines.append(f"  {k}: {v}")
        for i in self.issues:
            tag = "오류" if i.level == "error" else "경고"
            loc = f"{i.line}행: " if i.line else ""
            lines.append(f"  [{tag}] {loc}{i.message}")
            if i.text:
                lines.append(f"         {i.text[:100]}")
        n_err = len(self.errors)
        n_warn = len(self.issues) - n_err
        lines.append(f"결과: {'통과' if self.ok else '실패'} — 오류 {n_err} · 경고 {n_warn}")
        return "\n".join(lines)


def _numbered_lines(path: str):
    """(줄 번호, 내용) — 주석 제거, @def 매크로 전개(정의 줄은 빠진다)."""
    from ..data.io import read_text
    macros, out = {}, []
    for no, raw in enumerate(read_text(path).splitlines(), 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        m = _DEF_RE.match(line)
        if m:
            macros[m.group(1)] = _apply_macros(m.group(2).strip(), macros)
            continue
        out.append((no, _apply_macros(line, macros) if macros else line))
    return out


def check_script(path: str) -> CheckReport:
    rep = CheckReport(path, "script")
    try:
        with open(path, "rb") as f:              # 바이트로 — 인코딩 선언(# -*- coding: cp949 -*-)·BOM을 Python이 처리
            src = f.read()
        compile(src, path, "exec")
        rep.info["문법"] = "정상(실행하지 않음)"
    except SyntaxError as e:
        rep.issues.append(Issue("error", f"Python 문법 오류: {e.msg}", e.lineno, (e.text or "").strip()))
    return rep


def check_equations(path: str, data: str = None, freq: str = None, smpl: str = None) -> CheckReport:
    """방정식 파일을 검사한다. data(xlsx/csv·워크파일)를 주면 변수 존재·결측 입력도 본다."""
    from ..estimation.equation import Equation
    from ..workfile import output as _output
    from ..workfile.runtime import quiet
    from ..workfile.workfile import wfopen

    rep = CheckReport(path, "equations")
    wf = None
    if data:
        old = _output.verbose()
        _output.verbose(0)
        try:
            wf = wfopen(data, freq=freq)
        finally:
            _output.verbose(old)
        rep.info["데이터"] = (f"{data} — {wf.freq} {wf._label(wf.index[0])}~{wf._label(wf.index[-1])} · "
                            f"시리즈 {len(wf.data.columns)}")
    f = wf.freq if wf is not None else (freq or "Q").upper()
    ctx = ir.BuildContext(yoy_periods={"Q": 4, "A": 1, "M": 12}.get(f, 4), disable_qoq=(f == "A"))
    columns = list(wf.data.columns) if wf is not None else None

    sys_eqs, n_est, n_nls, n_id = [], 0, 0, 0
    for no, line in _numbered_lines(path):
        try:
            if is_identity(line):
                s = normalize(line)
                if columns is not None:
                    s = canonicalize_columns(s, columns)
                lhs, rhs = split_equation(s)
                lhs_ir = ir.build(convert_at_functions(lhs), ctx)
                rhs_ir = ir.build(convert_at_functions(rhs), ctx)
                target = ir.first_variable(lhs_ir)
                if target is None:
                    raise DSLError("항등식 좌변에 변수가 없습니다")
                sys_eqs.append((no, line, SystemEquation(index=len(sys_eqs), kind="identity", label=lhs,
                                                         target=target, lhs=lhs_ir, rhs=rhs_ir)))
                n_id += 1
            else:
                def parse():
                    eq = Equation(line, wf._data if wf is not None else None)
                    if wf is not None:
                        eq.wt = wf._wt
                    eq._parse()
                    return eq
                eq = quiet(parse)
                sys_eqs.append((no, line, SystemEquation(index=len(sys_eqs), kind="behavioral",
                                                         label=eq.dependent_var, target=eq.target,
                                                         lhs=eq.lhs_ir, rhs=eq.system_rhs(),
                                                         n_coef=len(eq.coef_names))))
                if eq.kind == "nls":
                    n_nls += 1
                else:
                    n_est += 1
        except (DSLError, SyntaxError, ValueError, KeyError, TypeError) as e:
            rep.issues.append(Issue("error", str(e).splitlines()[0][:300], no, line))

    rep.info["식"] = f"추정식 {n_est} · NLS {n_nls} · 항등식 {n_id} (문법 오류 {len(rep.errors)})"
    if not sys_eqs and not rep.errors:
        rep.issues.append(Issue("error", "식이 하나도 없습니다(빈 파일이거나 주석뿐)"))
    if rep.errors:
        rep.info["구조"] = "문법 오류가 있어 검사하지 않음"
        return rep

    eqs = [e for _, _, e in sys_eqs]
    referenced = set()
    for e in eqs:
        referenced |= {n for n, _ in e.leaves}
    # 데이터 열은 식을 읽은 뒤에 다시 본다(@seas·@trend 같은 지시자 열이 그때 만들어진다)
    cols = list(wf.data.columns) if wf is not None else sorted(referenced)
    try:
        system = ModelSystem(eqs, cols)
        st = system.structure()
    except StructureError as e:
        rep.issues.append(Issue("error", f"모델 구조: {e}"))
        return rep
    blocks = st.describe(system)
    sim = [b for b in blocks if b["size"] > 1]
    rep.info["변수"] = f"내생 {len(system.endogenous)} · 외생 {len(system.exogenous)}"
    rep.info["블록"] = (f"{len(blocks)}개 — 동시 {len(sim)}" +
                      (f" (최대 {max(b['size'] for b in sim)}변수)" if sim else "") +
                      f" · 순차 {len(blocks) - len(sim)}")
    if wf is None:
        rep.issues.append(Issue("warning", "데이터를 주지 않아 변수 존재·결측 입력은 검사하지 않았습니다(--data)."))
        return rep

    # 표본 구간의 결측 입력(시차값·현시점 외생) — 엔진 on_missing='exclude'면 그 식만 그 기간 제외된다
    if smpl and smpl.lower() not in ("@all", "all"):
        old = _output.verbose()
        _output.verbose(0)
        try:
            wf.smpl(smpl.replace(":", " "))
        finally:
            _output.verbose(old)
    s, e = wf._bounds()
    df = wf.data
    T = len(df)
    endo = set(system.endogenous)
    arrays = {n: df[n].to_numpy(dtype=float) for n in system.var_names if n in df.columns}
    gaps = {}
    for (no, line, eq) in sys_eqs:
        periods = []
        for t in range(s, e + 1):
            for nm, lag in eq.leaves:
                if lag == 0 and nm in endo:
                    continue
                r = t + lag
                v = arrays[nm][r] if (nm in arrays and 0 <= r < T) else np.nan
                if not np.isfinite(v):
                    periods.append(t)
                    break
        if periods:
            gaps[(no, eq.target)] = periods
    rep.info["표본"] = f"{wf._label(df.index[s])}~{wf._label(df.index[e])} ({e - s + 1}기)"
    for (no, target), ps in gaps.items():
        span = f"{wf._label(df.index[ps[0]])}~{wf._label(df.index[ps[-1]])}"
        rep.issues.append(Issue("warning", f"{target} 식의 입력이 {len(ps)}기 비어 있음({span}) — 풀이 때 그 기간 "
                                           "이 식은 제외됩니다(on_missing='exclude')", no))
    if not gaps:
        rep.info["결측 입력"] = "없음"
    return rep


def check_path(path: str, data: str = None, freq: str = None, smpl: str = None) -> CheckReport:
    if not os.path.exists(path):
        raise FileNotFoundError(f"파일이 없습니다: {path}")
    if path.lower().endswith(".py"):
        return check_script(path)
    return check_equations(path, data=data, freq=freq, smpl=smpl)
