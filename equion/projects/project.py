#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""프로젝트 — 폴더 하나(equion.toml + 자료 + 블록 파일)를 부품과 조립으로 다룬다 (D32).

    import equion as eqn
    p = eqn.project("모형폴더")          # equion.toml을 읽는다
    p.assemble("main").show()            # 조립 검사(계산 없이)
    m = p.model("main")                  # 워크파일 모델 객체(ModelObject) — 식을 추정해 조립
    r = p.hs("main")                     # 과거 재현(HS) — [hs]의 구간·방식
    r = p.hs("demand")                   # 블록 HS — 그 블록만 풀고 나머지 변수는 실측
    p.ident("demand:Y").show()           # 항등식을 실측으로 검사

조립 층은 워크파일 API(D2) 위의 얇은 층이다 — 추정·풀이는 늘 엔진 한 곳에서 한다. 채택 기록(D32의 채택표)은 작업 기록이
생기는 단계(E3)에서 쓰고, 지금은 모형을 만들 때 식을 지금 자료로 추정하며 그렇게 했다고 알린다.
"""

import os
from typing import Dict, List, Optional

from ..workfile.output import say
from ..workfile.runtime import quiet
from .assembly import AssemblyReport, check, resolve
from .config import ProjectConfig, ProjectError, load_config
from .identity import IdentityCheck, check_identity
from .parts import Part, parse_line, read_block


class Project:
    """Equion 프로젝트 — 블록(방정식 파일)·모형(조립)·자료를 이름으로 다룬다. 여는 법은 `eqn.project(폴더)`.

    예
        >>> import tempfile, os
        >>> p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
        >>> p.blocks, p.models
        (['demand', 'price', 'finance'], ['core', 'main', 'main_fixrl'])

    관련: eqn.project · Project.assemble · Project.hs
    """

    def __init__(self, config: ProjectConfig):
        self.config = config
        self._wf = None
        self._parts: Optional[Dict[str, List[Part]]] = None
        self._part_problems: Dict[str, List[str]] = {}
        self._est: Dict[tuple, object] = {}
        self.notes: List[str] = []

    # ---- 열기·만들기 ---------------------------------------------------
    @classmethod
    def open(cls, path: str = ".") -> "Project":
        """프로젝트 폴더(또는 그 안의 equion.toml)를 연다 — `eqn.project(path)`와 같다.

        오류
            ProjectError: 설정 파일이 없음·문법 오류·없는 블록 파일 등(문제를 모두 모아서)

        예
            >>> import tempfile, os
            >>> d = os.path.join(tempfile.mkdtemp(), "demo")
            >>> _ = eqn.Project.create(d)
            >>> eqn.Project.open(d).name
            'demo'
        """
        return cls(load_config(path))

    @classmethod
    def create(cls, path: str, template: str = "desk", force: bool = False) -> "Project":
        """예제 프로젝트를 만들고 연다 — 명령줄 `equion new 폴더 --template desk`와 같다.

        예제는 가상 분기 모형(예제 자료 toy_q)이다: 블록 demand(소비·투자·국민소득 항등식)·price(물가)·finance(장기금리·통화),
        모형 core·main·main_fixrl.

        매개변수
            path: 만들 폴더(비어 있어야 한다)
            template: 'desk'
            force: 비어 있지 않은 폴더에도 쓴다(같은 이름 파일을 덮음)

        오류
            FileExistsError: 폴더가 비어 있지 않음 · ValueError: 모르는 template

        예
            >>> import tempfile, os
            >>> p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
            >>> p.assemble("main").ok
            True
        """
        from .template import create_desk_project
        if template != "desk":
            raise ValueError(f"모르는 template: {template!r} (가능: 'desk')")
        create_desk_project(path, force=force)
        return cls.open(path)

    def __repr__(self):
        c = self.config
        return f"<프로젝트 {c.name}: 블록 {len(c.blocks)} · 모형 {len(c.models)} · 자료 {c.data_file}>"

    # ---- 이름·부품 -----------------------------------------------------
    @property
    def name(self) -> str:
        """프로젝트 이름([project] name, 없으면 폴더 이름)."""
        return self.config.name

    @property
    def root(self) -> str:
        """프로젝트 폴더의 절대 경로."""
        return self.config.root

    @property
    def blocks(self) -> List[str]:
        """블록 이름 목록(설정 파일 순서)."""
        return list(self.config.blocks)

    @property
    def models(self) -> List[str]:
        """모형 이름 목록(설정 파일 순서)."""
        return list(self.config.models)

    @property
    def workfile(self):
        """프로젝트 자료의 워크파일(처음 쓸 때 [data] file을 연다)."""
        if self._wf is None:
            from ..workfile.workfile import wfopen
            self._wf = quiet(wfopen, self.config.data_path, name=self.config.name)
        return self._wf

    def _load(self):
        if self._parts is None:
            data = self.workfile._data
            self._parts, self._part_problems = {}, {}
            for b, spec in self.config.blocks.items():
                self._parts[b], self._part_problems[b] = quiet(read_block, spec, data)
        return self._parts

    def parts(self, name: str = None) -> List[Part]:
        """부품(식·항등식) 목록 — name이 없으면 전부, 블록 이름이면 그 블록, 모형 이름이면 조립된 식들.

        예
            >>> import tempfile, os
            >>> p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
            >>> [x.id for x in p.parts("demand")]
            ['demand:CN', 'demand:I', 'demand:Y']
        """
        by_block = self._load()
        if name is None:
            return [x for b in self.config.blocks for x in by_block[b]]
        parts, _, _ = resolve(self.config, by_block, name)
        return parts

    def part(self, pid: str) -> Part:
        """부품 하나 — `블록:목표`(대소문자 무시).

        오류
            KeyError: 없는 부품(있는 부품 이름과 함께)

        예
            >>> import tempfile, os
            >>> p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
            >>> p.part("demand:y").text
            'Y = CN + I + G'
        """
        low = pid.lower()
        for x in self.parts():
            if x.id.lower() == low:
                return x
        raise KeyError(f"없는 부품: {pid} (있는 부품: {', '.join(x.id for x in self.parts())})")

    def used_by(self, name: str) -> List[str]:
        """쓰는 곳 — 블록이나 부품(`블록:목표`)을 쓰는 모형 목록. 고치기 전에 영향 범위를 본다.

        예
            >>> import tempfile, os
            >>> p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
            >>> p.used_by("demand"), p.used_by("finance:RL")
            (['core', 'main', 'main_fixrl'], ['main'])
        """
        by_block = self._load()
        out = []
        for m in self.config.models:
            parts, _, _ = resolve(self.config, by_block, m)
            if any(x.block == name or x.id.lower() == name.lower() for x in parts):
                out.append(m)
        return out

    def _default(self, name):
        if name:
            return name
        d = self.config.default_model()
        if not d:
            raise ProjectError("모형 이름을 주세요 — [hs] model이 없고 모형이 여럿입니다: " + ", ".join(self.models))
        return d

    def _blocks_of(self, name) -> List[str]:
        if name in self.config.blocks:
            return [name]
        out, stack = [], [name]
        while stack:
            m = stack.pop()
            spec = self.config.models.get(m)
            if spec is None:
                continue
            out += [b for b in spec.blocks if b not in out]
            stack += [i for i in spec.include]
        return out

    def _swapped(self, parts: List[Part], swap: Optional[dict]) -> (List[Part], List[str]):
        if not swap:
            return parts, []
        problems, out = [], list(parts)
        data = self.workfile._data
        for pid, text in swap.items():
            k = next((i for i, x in enumerate(out) if x.id.lower() == pid.lower()), None)
            if k is None:
                problems.append(f"바꿔 끼우기 {pid}: 이 모형에 그런 식이 없습니다")
                continue
            old = out[k]
            try:
                info = quiet(parse_line, text, data)
            except (ValueError, KeyError) as e:
                problems.append(f"바꿔 끼우기 {pid}: {e}")
                continue
            if info["target"] != old.target:
                problems.append(f"바꿔 끼우기 {pid}: 새 식의 목표가 {info['target']}입니다 — {old.target}이어야 합니다")
                continue
            from ..formula import ir
            out[k] = Part(block=old.block, target=old.target, kind=info["kind"], text=text, expr=text,
                          file="(바꿔 끼움)", line=0, desc=f"{old.id} 대신", lhs=info["lhs"], rhs=info["rhs"],
                          data_vars=set(info["data_vars"]),
                          leaves=frozenset(ir.leaves(info["lhs"]) | ir.leaves(info["rhs"])))
        return out, problems

    # ---- 조립 ----------------------------------------------------------
    def assemble(self, name: str = None, swap: dict = None) -> AssemblyReport:
        """조립 검사 — 계산 없이 모형(또는 블록)의 구조를 본다: 내생·외생, 겹친 목표, 모르는 변수, 외생 자료 끝, 블록 사이 연결, 풀이 블록.

        매개변수
            name: 모형 또는 블록 이름(기본: [hs] model, 모형이 하나면 그것)
            swap: {부품: 식} — 파일을 바꾸지 않고 그 식만 바꿔 끼워 검사

        돌려주는 것
            AssemblyReport — .ok · .problems · .endogenous · .exogenous · .blocks · .text()

        예
            >>> import tempfile, os
            >>> p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
            >>> r = p.assemble("main")
            >>> r.ok, r.endogenous
            (True, ['CN', 'I', 'Y', 'P', 'RL', 'M2'])
            >>> r.exogenous
            ['G', 'POIL', 'R']
            >>> p.assemble("main_fixrl").exogenous
            ['G', 'POIL', 'R', 'RL']
        """
        name = self._default(name)
        by_block = self._load()
        sub, sp = by_block, []
        if swap:                                # 바꿔 끼운 식으로 블록 목록을 고쳐 검사한다(파일·설정은 그대로)
            parts, _, _ = resolve(self.config, by_block, name)
            swapped, sp = self._swapped(parts, swap)
            new = {(y.block, y.target): y for y in swapped if y.line == 0}
            sub = {b: [new.get((x.block, x.target), x) for x in ps] for b, ps in by_block.items()}
        rep = check(self.config, sub, name, self.workfile._data)
        rep.problems = sp + rep.problems
        pp = [q for b in self._blocks_of(name) for q in self._part_problems.get(b, [])]
        rep.problems = pp + rep.problems
        rep.warnings = list(self.config.warnings) + rep.warnings
        return rep

    # ---- 모형·HS --------------------------------------------------------
    def _obj_name(self, name: str) -> str:
        wf = self.workfile
        base = name if wf._col(name) is None else f"m_{name}"
        return base

    def _estimate(self, part: Part):
        from ..workfile.objects import EquationObject
        wf = self.workfile
        key = (part.id, part.expr)
        obj = self._est.get(key)
        if obj is not None:
            return obj
        nm = f"{part.block}_{part.target}"
        if part.line == 0:                      # 바꿔 끼운 식 — 글자마다 다른 이름(같은 식은 같은 이름)
            import hashlib
            nm += "_s" + hashlib.md5(part.expr.encode("utf-8")).hexdigest()[:6]
        if wf._col(nm) is not None:
            nm = "eq_" + nm
        wf._objects.pop(nm.lower(), None)
        obj = EquationObject(wf, nm)
        eq = obj._make(part.expr)
        wf._register(obj)
        obj._adopt(eq, part.expr, loud=False)
        self._est[key] = obj
        return obj

    def model(self, name: str = None, swap: dict = None):
        """모형(또는 블록)을 조립해 워크파일 모델 객체로 — 추정식은 지금 자료로 추정하고 항등식은 그대로 넣는다.

        채택 기록이 없으면(작업 기록은 다음 단계) 식을 지금 자료·식의 표본(`@smpl`, 없으면 자료 전체)으로 추정하고 `.notes`에 적는다.
        같은 식은 한 번만 추정한다(다시 부르면 그 추정을 쓴다).

        매개변수
            name: 모형 또는 블록 이름(블록이면 그 블록의 식만 — 나머지 변수는 실측)
            swap: {부품: 식} — 파일을 바꾸지 않고 그 식만 바꿔 끼운다(목표변수는 같아야 한다)

        돌려주는 것
            ModelObject — .solve() · .forecast() · .scenario() …(워크파일 API)

        오류
            ProjectError: 조립 문제(겹친 목표·모르는 변수 등 — assemble의 문제 목록)

        예
            >>> import tempfile, os
            >>> p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
            >>> m = p.model("core")
            >>> m.endogenous
            ['CN', 'I', 'Y']
        """
        name = self._default(name)
        rep = self.assemble(name, swap=swap)
        if not rep.ok:
            raise ProjectError([f"모형 {name}을(를) 조립할 수 없습니다:"] + rep.problems)
        wf = self.workfile
        obj = self._obj_name(name)
        wf._objects.pop(obj.lower(), None)
        m = wf.model(obj)
        new = []
        for x in rep.parts:
            if x.kind == "identity":
                m.append(x.expr)
            else:
                fresh = (x.id, x.expr) not in self._est
                m.merge(self._estimate(x))
                if fresh:
                    new.append(x.id)
        if new:
            note = f"채택 기록 없이 지금 자료로 추정: {', '.join(new)}"
            self.notes.append(note)
            say(f"[{name}] {note}")
        return m

    def _range(self, start, end):
        rng = self.config.hs.get("range")
        if (start is None or end is None) and rng:
            s, e = [t.strip() for t in rng.split(":", 1)]
            start = start if start is not None else s
            end = end if end is not None else e
        return start, end

    def hs(self, name: str = None, start=None, end=None, mode: str = None, swap: dict = None, **opts):
        """과거 재현(HS) — 모형이나 블록을 풀어 실측과 견준다. 블록이면 그 블록만 풀고 나머지 변수는 실측(블록 HS).

        구간·방식의 기본은 equion.toml `[hs]`의 range·mode, 없으면 자료 전체·dynamic. 풀이 값은 워크파일의 별칭 시리즈(`CN_0` …)에 쓴다.

        매개변수
            name: 모형 또는 블록 이름(기본: [hs] model)
            start, end: 구간(기본: [hs] range)
            mode: 'dynamic' · 'static' · 'fit'(기본: [hs] mode)
            swap: {부품: 식} — 그 식만 바꿔 끼워 푼다(파일은 그대로)
            **opts: ModelObject.solve의 선택지(on_missing · on_fail · tolerance …)

        돌려주는 것
            SolveResult — .statistics() · .counts() · .summary()

        예
            >>> import tempfile, os
            >>> p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
            >>> r = p.hs("main")
            >>> r.start, r.end, r.counts()["ok"]
            ('2005Q1', '2019Q4', 60)
            >>> p.hs("demand").counts()["ok"]
            60
        """
        name = self._default(name)
        m = self.model(name, swap=swap)
        start, end = self._range(start, end)
        mode = mode or self.config.hs.get("mode") or "dynamic"
        return m.solve(start, end, mode=mode, **opts)

    # ---- 항등식 검사 ----------------------------------------------------
    def ident(self, pid: str, start=None, end=None, tol: float = 1e-6) -> IdentityCheck:
        """항등식 단독 검사 — 실측으로 좌변과 우변을 계산해 견준다(추정 없이).

        매개변수
            pid: 항등식 부품 `블록:목표`(예: demand:Y)
            start, end: 구간(기본: 자료 전체)
            tol: 허용오차 — |좌변 − 우변| ≤ tol·max(1, |좌변|)이면 성립

        돌려주는 것
            IdentityCheck — .ok · .mismatches · .max_abs · .table · .text()

        오류
            KeyError: 없는 부품 · ValueError: 항등식이 아님

        예
            >>> import tempfile, os
            >>> p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
            >>> c = p.ident("demand:Y")
            >>> c.ok, c.n
            (True, 200)
        """
        part = self.part(pid)
        wf = self.workfile
        s, e = wf._bounds(start, end) if (start is not None or end is not None) else (0, len(wf.data) - 1)
        return check_identity(part, wf._data, s, e, wf._label, tol=tol)


def open_project(path: str = ".") -> Project:
    """프로젝트 열기 — 폴더(또는 그 안의 equion.toml)를 읽어 블록·모형·자료를 이름으로 다룬다.

    프로젝트는 폴더 하나다: `equion.toml`(자료 파일·블록·모형 조립) + 자료 파일 + 블록 파일(방정식 파일). 예제 프로젝트는
    `eqn.Project.create(폴더)` 또는 명령줄 `equion new 폴더 --template desk`.

    매개변수
        path: 프로젝트 폴더 또는 equion.toml 경로(기본: 지금 폴더)

    돌려주는 것
        Project — .assemble · .model · .hs · .ident · .parts · .used_by

    오류
        ProjectError: 설정 파일이 없음·문법 오류·없는 파일·잘못된 이름(문제를 모두 모아서)

    예
        >>> import tempfile, os
        >>> d = os.path.join(tempfile.mkdtemp(), "demo")
        >>> _ = eqn.Project.create(d)
        >>> p = eqn.project(d)
        >>> p.models
        ['core', 'main', 'main_fixrl']

    관련: Project · docs/reference/formats.md
    """
    return Project.open(path)
