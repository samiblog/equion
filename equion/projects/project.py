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
from dataclasses import dataclass
from typing import Dict, List, Optional

from ..workfile.output import say
from ..workfile.runtime import quiet
from .assembly import AssemblyReport, check, resolve
from .config import ProjectConfig, ProjectError, load_config
from .identity import IdentityCheck, check_identity
from .parts import Part, parse_line, read_block
from .vintage import (AddResult, BuildResult, VintageDiff, add_raw, build_vintage, diff_vintages, list_vintages,
                      load_defs, set_toml_value, vintage_path)
from ..data.source import read_source
from ..workfile.output import TextOutput


@dataclass
class ImpactReport:
    """회차를 바꿀 때 영향받는 것 — 바뀐 시리즈를 쓰는 식과 모형. 다시 계산은 사람이 시킬 때만."""

    diff: VintageDiff
    parts: List[str]
    models: List[str]
    uses: Dict[str, List[str]]          # 부품 → 쓰는 바뀐 시리즈

    def text(self) -> str:
        """명령줄에 보이는 짧은 글."""
        d = self.diff
        L = [f"[data impact {d.a} → {d.b}]",
             f"  바뀐 시리즈 {len(d.changed)} · 새 {len(d.added)} · 없어진 {len(d.removed)}"]
        if self.parts:
            L.append("  쓰는 식   " + " · ".join(f"{p} ({'·'.join(self.uses[p])})" for p in self.parts))
            L.append("  쓰는 모형  " + (" · ".join(self.models) if self.models else "없음"))
            L.append("  다시 할 일  그 회차로 바꾼 뒤 모형을 다시 추정·풀면 새 자료로 계산된다(저절로 하지 않는다)")
        else:
            L.append("  쓰는 식   없음 — 모형에 영향 없음")
        return "\n".join(L)

    def to_dict(self) -> dict:
        """명령줄 --json과 같은 사전."""
        return {"diff": self.diff.to_dict(), "parts": self.parts, "models": self.models, "uses": self.uses}

    def show(self):
        """짧은 글을 보인다."""
        from ..workfile.output import spool
        spool.show(TextOutput(self.text(), title="회차 영향"))

    def __repr__(self):
        return f"<회차 영향 {self.diff.a}→{self.diff.b}: 식 {len(self.parts)} · 모형 {len(self.models)}>"


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
        self.created_files: List[str] = []
        self._data_cols: List[str] = []

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

        예제는 가상 분기 모형이다: 원자료 toy_q·toy_m(DATA/raw/), 자료 정의(DATA/series.toml·derived.txt — 주기 변환·계절조정 예 포함),
        블록 demand(소비·투자·국민소득 항등식)·price(물가)·finance(장기금리·통화), 모형 core·main·main_fixrl.
        첫 자료 회차를 만들어 지금 회차로 정한다(`.created_files`에 만든 파일 목록).

        매개변수
            path: 만들 폴더(비어 있어야 한다)
            template: 'desk'
            force: 비어 있지 않은 폴더에도 쓴다(같은 이름 파일을 덮음)

        오류
            FileExistsError: 폴더가 비어 있지 않음 · ValueError: 모르는 template

        예
            >>> import tempfile, os
            >>> p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
            >>> p.assemble("main").ok, p.vintage is not None
            (True, True)
        """
        from .template import create_desk_project
        if template != "desk":
            raise ValueError(f"모르는 template: {template!r} (가능: 'desk')")
        files = create_desk_project(path, force=force)
        p = cls.open(path)
        p.data_build(use=True)
        p.created_files = files
        return p

    def __repr__(self):
        c = self.config
        data = f"회차 {c.vintage or '없음'}" if c.uses_vintages else f"자료 {c.data_file}"
        return f"<프로젝트 {c.name}: 블록 {len(c.blocks)} · 모형 {len(c.models)} · {data}>"

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
        """프로젝트 자료의 워크파일 — 자료 정의를 쓰면 지금 자료 회차, 아니면 [data] file(처음 쓸 때 연다).

        오류
            ProjectError: 자료 정의를 쓰는데 지금 회차가 없음(equion data build → equion data use)
        """
        if self._wf is None:
            from ..workfile.workfile import wfopen
            c = self.config
            if c.uses_vintages:
                if not c.vintage:
                    raise ProjectError("지금 자료 회차가 없습니다 — 자료 만들기(equion data build) 다음 이 회차로 바꾸기"
                                       "(equion data use <회차>)")
                path = os.path.join(vintage_path(c.root, c.vintage), "series.csv")
                self._wf = quiet(wfopen, path, freq=c.freq, name=c.name)
            else:
                self._wf = quiet(wfopen, c.data_path, name=c.name)
            self._data_cols = list(self._wf.data.columns)
        return self._wf

    @property
    def vintage(self) -> Optional[str]:
        """지금 자료 회차(equion.toml [data] vintage) — 자료 파일 하나를 쓰면 None."""
        return self.config.vintage if self.config.uses_vintages else None

    def _reset(self):
        """설정을 다시 읽고 자료·부품·추정을 버린다(회차를 바꾼 뒤)."""
        self.config = load_config(self.config.path)
        self._wf, self._parts, self._part_problems, self._est = None, None, {}, {}

    # ---- 자료 정의·회차(D34) -------------------------------------------
    def _need_defs(self):
        if not self.config.uses_vintages:
            raise ProjectError("이 프로젝트는 자료 파일 하나([data] file)를 씁니다 — 자료 회차는 [data] series·freq를 적은 "
                               "프로젝트에서(docs/reference/formats.md)")
        c = self.config
        return load_defs(c.root, c.series_file, c.derived_file, c.freq)

    def data_build(self, use: bool = False) -> BuildResult:
        """자료 만들기 — 원자료를 정의(series.toml·derived.txt)대로 읽어 새 자료 회차(work/data/<회차>/)를 만든다.

        같은 원자료·정의로 만든 회차가 이미 있으면 새로 만들지 않고 그 회차를 알린다. 지금 회차는 저절로 바뀌지 않는다(use=True면 바꾼다).

        매개변수
            use: 참이면 만든(또는 같은) 회차를 지금 회차로

        돌려주는 것
            BuildResult — .id · .created · .n_series · .span · .implicit(알아서 한 것) · .text()

        오류
            ProjectError: 정의·원자료 문제(없는 열·틀이 맞지 않음·주기 변환·파생식 — 위치와 함께)

        예
            >>> import tempfile, os
            >>> p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
            >>> r = p.data_build()
            >>> r.created, r.id == p.vintage        # 정의가 그대로라 같은 회차
            (False, True)
        """
        from ..version import project_version
        defs = self._need_defs()
        res = build_vintage(defs, project_version())
        say(f"[{self.name}] " + (f"자료 회차 {res.id}를 만들었습니다" if res.created else f"자료 회차 {res.id}와 같습니다"))
        if use and res.id != self.config.vintage:
            self.data_use(res.id)
        return res

    def data_use(self, vid: str) -> str:
        """이 회차로 바꾸기 — equion.toml의 [data] vintage를 고치고(주석·순서는 그대로) 자료를 다시 연다. 이전 회차를 돌려준다.

        오류
            ProjectError: 없는 회차

        예
            >>> import tempfile, os
            >>> p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
            >>> v = p.vintage
            >>> p.data_use(v) == v
            True
        """
        self._need_defs()
        vintage_path(self.root, vid)
        old = self.config.vintage
        set_toml_value(self.config.path, ["data"], "vintage", vid)
        self._reset()
        say(f"[{self.name}] 지금 자료 회차: {vid}" + (f" (전: {old})" if old and old != vid else ""))
        return old

    def data_list(self) -> List[dict]:
        """자료 회차 목록(만든 때 순) — {id, created, span, n_series, current}.

        예
            >>> import tempfile, os
            >>> p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
            >>> [v["current"] for v in p.data_list()]
            [True]
        """
        return [{"id": v["id"], "created": v.get("created"), "span": v.get("span"), "n_series": v.get("n_series"),
                 "current": v["id"] == self.vintage} for v in list_vintages(self.root)]

    def _pair(self, a, b):
        ids = [v["id"] for v in list_vintages(self.root)]
        if not ids:
            raise ProjectError("자료 회차가 없습니다 — equion data build")
        b = b or ids[-1]
        if a is None:
            a = self.vintage if self.vintage and self.vintage != b else None
            if a is None:
                k = ids.index(b) if b in ids else len(ids) - 1
                if k == 0:
                    raise ProjectError(f"견줄 회차가 없습니다 — 회차가 {b} 하나입니다")
                a = ids[k - 1]
        return a, b

    def data_diff(self, a: str = None, b: str = None) -> VintageDiff:
        """두 자료 회차의 차이 — 새·없어진 시리즈, 시리즈마다 새 기간과 개정(기간·크기).

        기본은 지금 회차 → 가장 새 회차(같으면 그 앞 회차 → 가장 새 회차).

        예
            >>> import tempfile, os
            >>> p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
            >>> d = p.data_diff(p.vintage, p.vintage)
            >>> d.added, d.changed
            ([], [])
        """
        self._need_defs()
        a, b = self._pair(a, b)
        return diff_vintages(self.root, a, b)

    def data_impact(self, a: str = None, b: str = None) -> "ImpactReport":
        """회차를 바꾸면 영향받는 것 — 바뀐 시리즈를 쓰는 식(부품)과 모형. 다시 계산은 하지 않는다(사람이 시킬 때만).

        예
            >>> import tempfile, os
            >>> p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
            >>> r = p.data_impact(p.vintage, p.vintage)
            >>> r.parts, r.models
            ([], [])
        """
        d = self.data_diff(a, b)
        touched = set(d.changed) | set(d.added) | set(d.removed)
        parts = [x for x in self.parts() if touched & (x.data_vars | x.variables)]
        models = [m for m in self.models if any(x.id in {y.id for y in self.parts(m)} for x in parts)]
        return ImpactReport(d, [x.id for x in parts], models,
                            {x.id: sorted(touched & (x.data_vars | x.variables)) for x in parts})

    def data_add(self, path: str, source: str = None, as_name: str = None, note: str = None) -> AddResult:
        """원자료 넣기 — 파일을 DATA/raw/에 복사한다(받은 그대로, 같은 이름이면 날짜를 붙여 나란히). source를 주면 그 출처가
        이 파일을 읽도록 series.toml을 고치되, 먼저 그 출처의 불러오기 틀로 읽어 보고 시리즈가 쓰는 열이 다 있고 주기가 같을
        때만 넣고 고친다(틀 검사 — 맞지 않으면 아무것도 바꾸지 않고 `.problems`에 까닭).

        매개변수
            path: 넣을 파일(csv·xlsx·xls)
            source: 바꿀 출처 이름([source.이름]) — 원자료 바꾸기
            as_name: DATA/raw/에 둘 이름(기본: 파일 이름)
            note: 출처 메모(옆 파일 *.source.toml에)

        돌려주는 것
            AddResult — .file · .copied · .source · .problems(틀이 맞지 않으면 — 그때 출처는 그대로)

        예
            >>> import tempfile, os
            >>> p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
            >>> r = p.data_add(eqn.datasets.path("toy_q"))      # 같은 파일이 이미 있다
            >>> r.copied, r.file
            (False, 'DATA/raw/toy_q.csv')
        """
        defs = self._need_defs()
        if not source:
            return add_raw(self.root, path, as_name=as_name, note=note)
        if source not in defs.sources:
            raise ProjectError(f"없는 출처 '{source}' (있는 출처: {', '.join(defs.sources)})")
        if not os.path.isfile(path):
            raise ProjectError(f"파일이 없습니다: {path}")
        sp = defs.sources[source]
        from dataclasses import replace
        from ..data.source import file_sha256
        problems = []
        try:   # 틀 검사 — 넣기 전에, 받은 파일을 이 출처의 불러오기 틀로 읽어 본다
            t = read_source(replace(sp, file=os.path.basename(path), path=os.path.abspath(path)))
            for s in defs.series.values():
                if s.source == source and t.column(s.column)[0] is None:
                    problems.append(f"[series.{s.name}] 새 파일에 없는 열: {s.column}")
            old_freq = read_source(sp).freq if os.path.isfile(sp.path) else t.freq
            if t.freq != old_freq:
                problems.append(f"주기가 다릅니다: 새 파일은 {t.freq}, 출처 '{source}'는 {old_freq}")
        except ValueError as e:
            problems.append(str(e))
        if problems:
            return AddResult(path, file_sha256(path), False, source, sp.file, problems)
        res = add_raw(self.root, path, as_name=as_name, note=note)
        res.source, res.previous = source, sp.file
        if res.file != sp.file:
            set_toml_value(os.path.join(self.root, self.config.series_file), ["source", source], "file", res.file)
        return res

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

    def span(self, spec: str):
        """구간 표기 → (시작, 끝) 라벨 — '2005Q1:2019Q4' · '2005Q1:last' · 'last-39:last' · 'next:12'. last는 자료의 마지막 값이 있는 기간.

        예
            >>> import tempfile, os
            >>> p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
            >>> p.span("last-3:last"), p.span("next:4")
            (('2019Q1', '2019Q4'), ('2020Q1', '2020Q4'))
        """
        from ..data.periods import resolve_span
        wf = self.workfile
        df = wf.data[[c for c in self._data_cols if c in wf.data.columns]]   # 자료 시리즈만(풀이 별칭 X_0 제외)
        ok = df.notna().any(axis=1).to_numpy()
        first = int(ok.argmax()) if ok.any() else 0
        last = len(ok) - 1 - int(ok[::-1].argmax()) if ok.any() else len(ok) - 1
        return resolve_span(spec, df.index, wf.freq, first=first, last=last)

    def _range(self, start, end):
        from ..data.periods import is_relative
        rng = self.config.hs.get("range")
        if (start is None or end is None) and rng:
            s, e = self.span(rng)
            start = start if start is not None else s
            end = end if end is not None else e
        if is_relative(start) or is_relative(end):
            s, e = self.span(f"{start or 'first'}:{end or 'last'}")
            start, end = s, e
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
        from ..data.periods import is_relative
        if is_relative(start) or is_relative(end):
            start, end = self.span(f"{start or 'first'}:{end or 'last'}")
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
