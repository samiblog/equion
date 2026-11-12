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
                      load_defs, vintage_path)
from ..data.source import read_source
from ..workfile.output import TextOutput
from ..work.store import detect_who


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
        self._sources: Dict[tuple, str] = {}           # 식 → 어디서 온 계수(adopted:est:… · estimated · swap:…)
        self._swap_saved: Dict[tuple, tuple] = {}      # (부품, 식) → (est:기록, 저장된 식) — 기록의 계수로 바꿔 끼우기

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
        self._sources, self._swap_saved = {}, {}

    # ---- 자료 정의·회차(D34) -------------------------------------------
    def _need_defs(self):
        if not self.config.uses_vintages:
            raise ProjectError("이 프로젝트는 자료 파일 하나([data] file)를 씁니다 — 자료 회차는 [data] series·freq를 적은 "
                               "프로젝트에서(docs/reference/formats.md)")
        c = self.config
        return load_defs(c.root, c.series_file, c.derived_file, c.freq)

    def data_build(self, use: bool = False, inbox: str = None, ask=None, who: str = None, command: str = None) -> BuildResult:
        """자료 만들기 — 원자료를 정의(series.toml·derived.txt)대로 읽어 새 자료 회차(work/data/<회차>/)를 만든다.

        같은 원자료·정의로 만든 회차가 이미 있으면 새로 만들지 않고 그 회차를 알린다. 지금 회차는 저절로 바뀌지 않는다(use=True면 바꾼다).
        inbox를 주면 먼저 받은 상자(DATA/raw/inbox/)의 새 파일을 출처와 짝지어 넣는다(`data_inbox`로 미리 본다) — 하나라도 짝이
        없거나 틀이 맞지 않으면 아무것도 넣지 않고 회차도 만들지 않는다.

        매개변수
            use: 참이면 만든(또는 같은) 회차를 지금 회차로
            inbox: None · 'auto'(짝이 하나이고 틀이 맞으면 넣는다) · 'ask'(ask(item)이 참인 것만 — ask가 없으면 auto)
            ask: 받은 파일마다 부르는 함수(InboxItem → 참거짓) — 명령줄은 터미널이면 묻는다

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
        from . import inbox as ib
        taken = []
        if inbox and inbox != "no":
            taken = ib.take(self, inbox, ask=ask, who=who, command=command)
        defs = self._need_defs()
        res = build_vintage(defs, project_version())
        res.inbox = taken
        if not inbox or inbox == "no":
            res.waiting = len(ib.inbox_files(self.root))
        say(f"[{self.name}] " + (f"자료 회차 {res.id}를 만들었습니다" if res.created else f"자료 회차 {res.id}와 같습니다"))
        if use and res.id != self.config.vintage:
            self.data_use(res.id, who=who, command=command)
        return res

    def data_inbox(self) -> list:
        """받은 상자(DATA/raw/inbox/)의 파일마다 짝지을 출처와 틀 검사 — 미리보기(아무것도 바꾸지 않는다). InboxItem 목록.

        짝짓기: series.toml `[source.이름] inbox = "글롭"`을 적었으면 그것만, 아니면 출처가 지금 읽는 파일 이름(날짜 꼬리 뺌)으로
        시작하는 파일 — 가장 긴 것. 넣기는 `data_build(inbox='auto')`·명령줄 `equion data build --inbox ask`.

        예
            >>> import tempfile, os, shutil
            >>> p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
            >>> _ = shutil.copy(eqn.datasets.path("toy_q"), os.path.join(p.root, "DATA/raw/inbox/toy_q_new.csv"))
            >>> [(x.source, x.status) for x in p.data_inbox()]
            [('na', 'ready')]
        """
        from . import inbox as ib
        return ib.plan(self)

    def data_use(self, vid: str, who: str = None, command: str = None) -> str:
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
        if old != vid:
            from .records import history_of
            from .vintage import toml_with_value
            history_of(self).write_files({"equion.toml": toml_with_value(self.config.path, ["data"], "vintage", vid)},
                                         who or detect_who("python"), command or f"data use {vid}",
                                         note=f"자료 회차 {old} → {vid}" if old else f"자료 회차 {vid}")
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

    def data_add(self, path: str, source: str = None, as_name: str = None, note: str = None, who: str = None,
                 command: str = None) -> AddResult:
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
        from ..data.source import file_sha256
        problems = self._source_problems(defs, source, path)
        if problems:
            return AddResult(path, file_sha256(path), False, source, sp.file, problems)
        res = add_raw(self.root, path, as_name=as_name, note=note)
        res.source, res.previous = source, sp.file
        if res.file != sp.file:
            from .records import history_of
            from .vintage import toml_with_value
            sf = self.config.series_file
            history_of(self).write_files(
                {sf: toml_with_value(os.path.join(self.root, sf), ["source", source], "file", res.file)},
                who or detect_who("python"), command or f"data add {os.path.basename(path)} --source {source}",
                note=f"[source.{source}] {sp.file} → {res.file}")
        return res

    def data_preview(self, file: str, sheet=None, header_row=None, unit_row=None, time_col=None, missing=None,
                     thousands=None, freq=None, rows: int = 30, series: dict = None, time_axis=None, time_row=None, name_col=None,
                     unit_col=None) -> "SourcePreview":
        """원자료 파일을 미리 본다 — 읽은 그대로의 앞쪽 줄과, 준 틀(시트·열 이름 줄·단위 줄·시점 열·결측 표시·천 단위)로 읽어 본 결과.
        아무것도 쓰지 않고 기록도 남기지 않는다. 틀이 맞지 않으면 예외가 아니라 `.ok`가 거짓이고 `.error`에 까닭(칸 위치와 함께).

        매개변수
            file: 원자료 파일(csv·xlsx·xls — 프로젝트 기준 경로 또는 절대 경로)
            sheet · header_row · unit_row · time_col · missing · thousands · freq: 불러오기 틀(docs/reference/formats.md) —
                header_row는 여러 줄도 된다([3, 4] · "3,4" — 이어 붙인 이름)
            time_axis · time_row · name_col · unit_col: 시점이 열로 가는 표(time_axis="columns") — 시점 줄 · 이름 열 · 단위 열
            rows: 읽은 그대로 보일 줄 수
            series: {column, convert, denton, seas, scale, fill} — 그 열을 변환대로 만들어 본 값을 `.series`에(자료 만들기와 같은 계산)

        돌려주는 것
            SourcePreview — .grid · .ok · .error · .freq · .span · .note · .columns · .missing_cells · .bad_cells · .series

        오류
            ProjectError: 없는 파일·읽을 수 없는 형식, series를 주었는데 열이 없거나 변환할 수 없음

        예
            >>> import tempfile, os
            >>> p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
            >>> v = p.data_preview("DATA/raw/toy_q.csv")
            >>> v.ok, v.freq, v.span, v.columns[0]["name"]
            (True, 'Q', ['1970Q1', '2019Q4'], 'CN')

        관련
            data_define · data_add · data_build
        """
        from .vintage import _frame_spec, preview_series, preview_source
        out = preview_source(self.root, file, sheet, header_row, unit_row, time_col, missing, thousands, freq, rows, time_axis, time_row,
                             name_col, unit_col)
        if series and out.ok:
            given = dict(series)
            column = given.pop("column", None)
            if not column:
                raise ProjectError("series에는 column(열 이름)이 있어야 합니다")
            spec = _frame_spec(self.root, file, "preview", sheet, header_row, unit_row, time_col, missing, thousands, freq, time_axis,
                               time_row, name_col, unit_col)
            out.series = preview_series(self.config.freq or out.freq, spec, column, **given)
        return out

    def data_define(self, source: str, file: str = None, sheet=None, header_row=None, unit_row=None, time_col=None,
                    missing=None, thousands=None, freq=None, desc: str = None, series: dict = None, replace: bool = False,
                    who: str = None, command: str = None, time_axis=None, time_row=None, name_col=None, unit_col=None) -> "DefineResult":
        """자료 정의 쓰기 — `series.toml`에 출처(`[source.이름]` = 불러오기 틀)와 시리즈(`[series.이름]`)를 더하거나 고친다.
        쓰기 전에 새 내용 전체와, 그 틀로 원자료를 읽어 시리즈가 쓰는 열이 다 있고 변환이 되는지 검사한다 — 문제가 있으면
        아무것도 쓰지 않는다. 사람이 쓴 주석·순서는 그대로 두고(tomlkit) 바뀜 기록에 남긴다. 자료는 만들지 않는다 —
        이어서 `data_build`, `data_use`.

        매개변수
            source: 출처 이름(없으면 새로 — 그때 file이 있어야 한다)
            file: 원자료 파일(프로젝트 안 — 보통 DATA/raw/)
            sheet · header_row · unit_row · time_col · missing · thousands · freq: 틀. 준 것만 바꾼다(None은 그대로, ""·0은 그 키를 지움)
            time_axis · time_row · name_col · unit_col: 시점이 열로 가는 표(time_axis="columns" — "rows"면 그 키를 지운다)
            desc: 출처 설명
            series: {시리즈 이름: 열 이름 또는 {column, unit, desc, convert, denton, seas, scale, fill}}
            replace: 이미 있는 시리즈를 다른 열로 바꿔도 된다

        돌려주는 것
            DefineResult — .source · .file · .new_source · .added · .changed · .change(바뀜 기록)

        오류
            ProjectError: 자료 정의를 쓰지 않는 프로젝트, 이름·키 문제, 원자료에 없는 열, 변환할 수 없음(문제 모두 — 아무것도 쓰지 않음)

        예
            >>> import tempfile, os
            >>> p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
            >>> r = p.data_define("na", series={"CONS": {"column": "CN", "desc": "소비(다른 이름으로)"}})
            >>> r.added, r.new_source, r.change is not None
            (['CONS'], False, True)

        관련
            data_preview · data_add · data_build · data_use
        """
        self._need_defs()
        from .records import history_of
        from .vintage import define_text
        c = self.config
        frame = {k: v for k, v in (("sheet", sheet), ("header_row", header_row), ("unit_row", unit_row), ("time_col", time_col),
                                   ("missing", missing), ("thousands", thousands), ("freq", freq), ("time_axis", time_axis),
                                   ("time_row", time_row), ("name_col", name_col), ("unit_col", unit_col)) if v is not None}
        text, res = define_text(c.root, c.series_file, c.derived_file, c.freq, source, file=file, frame=frame, desc=desc,
                                series=series, replace=replace)
        names = ", ".join(res.added + res.changed)
        ch = history_of(self).write_files({c.series_file: text}, who or detect_who("python"), command or f"data define {source}",
                                          note=f"[source.{source}]" + (f" · 시리즈 {names}" if names else ""))
        res.change = ch.id if ch else None
        self._reset()
        return res

    def _source_problems(self, defs, source: str, path: str) -> List[str]:
        """틀 검사 — 받은 파일을 그 출처의 불러오기 틀로 읽어 본다: 시리즈가 쓰는 열이 다 있고 주기가 같은가."""
        from dataclasses import replace
        sp = defs.sources[source]
        problems = []
        try:
            t = read_source(replace(sp, file=os.path.basename(path), path=os.path.abspath(path)))
            for s in defs.series.values():
                if s.source == source and t.column(s.column)[0] is None:
                    problems.append(f"[series.{s.name}] 새 파일에 없는 열: {s.column}")
            old_freq = read_source(sp).freq if os.path.isfile(sp.path) else t.freq
            if t.freq != old_freq:
                problems.append(f"주기가 다릅니다: 새 파일은 {t.freq}, 출처 '{source}'는 {old_freq}")
        except ValueError as e:
            problems.append(str(e))
        return problems

    def model_define(self, name: str, blocks=None, include=None, exclude=None, desc: str = None, who: str = None,
                     command: str = None) -> "ConfigChange":
        """모형 정의 쓰기 — `equion.toml`의 `[model.이름]`을 더하거나 고친다(블록·끼울 모형·뺄 식·설명). 준 것만 바꾸고(None은 그대로,
        빈 목록·빈 글은 그 키를 지움), 쓰기 전에 새 설정 전체를 검사한다 — 문제가 있으면 아무것도 쓰지 않는다. 주석·순서는 그대로 두고
        바뀜 기록에 남긴다. 조립은 하지 않는다 — 이어서 `assemble`.

        매개변수
            name: 모형 이름(없으면 새로 — 그때 blocks나 include가 있어야 한다)
            blocks: 블록 이름들(목록 또는 쉼표·공백으로 띄운 글)
            include: 끼울 모형들
            exclude: 뺄 식들(블록:목표 — 그 목표는 외생이 된다)
            desc: 설명

        돌려주는 것
            ConfigChange — .kind('model') · .name · .new · .change(바뀜 기록)

        오류
            ProjectError: 이름·없는 블록·없는 모형·include 순환·블록과 같은 이름(문제 모두 — 아무것도 쓰지 않음)

        예
            >>> import tempfile, os
            >>> p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
            >>> r = p.model_define("demand_price", blocks=["demand", "price"], desc="수요 + 물가")
            >>> r.new, sorted(p.models)[1], p.assemble("demand_price").ok
            (True, 'demand_price', True)

        관련
            block_define · assemble · used_by
        """
        from .config import ConfigChange, model_text
        from .records import history_of
        text, new = model_text(self.config.path, name, blocks=blocks, include=include, exclude=exclude, desc=desc)
        ch = history_of(self).write_files({"equion.toml": text}, who or detect_who("python"), command or f"model define {name}",
                                          note=f"[model.{name}]" + (" 새 모형" if new else ""))
        self._reset()
        return ConfigChange("model", name, new, [], ch.id if ch else None)

    def block_define(self, name: str, file: str = None, desc: str = None, who: str = None, command: str = None) -> "ConfigChange":
        """블록 더하기 — `equion.toml`의 `[block]`에 블록(방정식 파일 하나)을 더하거나 설명을 고친다. 새 블록의 파일이 아직 없으면
        머리 주석만 있는 빈 블록 파일을 함께 만든다(file을 주지 않으면 `EQUATIONS/<이름>.txt`). 바뀜 기록에 남긴다.
        식은 그 파일에 한 줄에 하나씩 적고, 모형에는 `model_define`으로 넣는다.

        매개변수
            name: 블록 이름
            file: 블록 파일(프로젝트 안의 .txt)
            desc: 설명

        돌려주는 것
            ConfigChange — .kind('block') · .name · .new · .files(새로 만든 블록 파일) · .change

        오류
            ProjectError: 이름·모형과 같은 이름·프로젝트 밖의 파일

        예
            >>> import tempfile, os
            >>> p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
            >>> r = p.block_define("labor", desc="노동")
            >>> r.new, r.files, "labor" in p.config.blocks
            (True, ['EQUATIONS/labor.txt'], True)

        관련
            model_define · parts
        """
        from .config import ConfigChange, block_text
        from .records import history_of
        text, new, rel, create = block_text(self.config.path, name, file=file, desc=desc)
        files = {"equion.toml": text}
        if create:
            files[rel] = f"# {desc or name} 블록 — 한 줄에 한 식(# 뒤는 설명). 문법: docs/explain/equations.md\n"
        ch = history_of(self).write_files(files, who or detect_who("python"), command or f"block define {name}",
                                          note=f"[block] {name}" + (" 새 블록" if new else ""))
        self._reset()
        return ConfigChange("block", name, new, [rel] if create else [], ch.id if ch else None)

    def group_define(self, name: str, series=None, desc: str = None, transform: str = None, who: str = None,
                     command: str = None) -> "ConfigChange":
        """묶음 저장 — equion.toml의 `[group]`에 이름 붙인 시리즈 묶음을 더하거나 고친다. 준 것만 바꾸고(None은 그대로, 빈 글은 그 키를 지움)
        주석·순서는 그대로 두며, 시리즈 이름이 자료에 있는지 본 뒤 쓴다. 바뀜 기록에 남긴다. 묶음은 분석의 대상이 된다(`equion an corr 이름`).

        매개변수
            name: 묶음 이름(영문으로 시작 — 한글 설명은 desc)
            series: 시리즈 이름들(목록 또는 쉼표·공백으로 띄운 글 — 순서를 지킨다)
            desc: 설명
            transform: 시리즈마다 씌울 변환(예: dlog — 빈 글이면 지움)

        돌려주는 것
            ConfigChange — .kind('group') · .name · .new · .change

        오류
            ProjectError: 이름 · 새 묶음에 시리즈가 없음 · 자료에 없는 시리즈(아무것도 쓰지 않음)

        예
            >>> import tempfile, os
            >>> p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
            >>> r = p.group_define("prices", "P, POIL", desc="물가와 유가")
            >>> r.new, p.config.groups["prices"].series
            (True, ['P', 'POIL'])

        관련
            group_remove · an
        """
        from .records import history_of
        from .config import ConfigChange, group_text
        if series is not None:
            names = [v for v in series.replace(",", " ").split() if v] if isinstance(series, str) else [str(v) for v in series]
            have = {str(c).upper() for c in self.workfile.data.columns}
            missing = [v for v in names if v.upper() not in have]
            if missing:
                raise ProjectError(f"[group] {name}: 자료에 없는 시리즈 {', '.join(missing)}")
            series = names
        text, new = group_text(self.config.path, name, series=series, desc=desc, transform=transform)
        ch = history_of(self).write_files({"equion.toml": text}, who or detect_who("python"), command or f"group define {name}",
                                          note=f"[group] {name}" + (" 새 묶음" if new else ""))
        self._reset()
        return ConfigChange("group", name, new, [], ch.id if ch else None)

    def group_remove(self, name: str, who: str = None, command: str = None) -> "ConfigChange":
        """묶음 지우기 — equion.toml의 `[group]`에서 그 묶음을 뺀다(시리즈·기록은 그대로). 바뀜 기록에 남긴다.

        오류
            ProjectError: 없는 묶음

        예
            >>> import tempfile, os
            >>> p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
            >>> p.group_remove("core").removed, "core" in p.config.groups
            (True, False)

        관련
            group_define
        """
        from .records import history_of
        from .config import ConfigChange, group_text
        text, _ = group_text(self.config.path, name, remove=True)
        ch = history_of(self).write_files({"equion.toml": text}, who or detect_who("python"), command or f"group remove {name}",
                                          note=f"[group] {name} 지움")
        self._reset()
        return ConfigChange("group", name, False, [], ch.id if ch else None, removed=True)

    def part_add(self, block: str, text: str, desc: str = None, from_part: str = None, who: str = None,
                 command: str = None) -> "PartChange":
        """블록에 식 한 줄을 더한다 — 블록 파일 끝에 적는다(다른 줄·주석은 그대로). 쓰기 전에 식 문법과 '한 블록에 목표 하나'를 본다.
        from_part를 주면 그 식을 옮긴다: 원래 블록의 그 줄을 빼고(채택표의 줄도) 이 블록에 더한다 — 모형에 안 든 블록의 개별 식을
        모형의 블록으로 넣을 때. 두 파일이 바뀜 기록 하나에 남는다.

        매개변수
            block: 더할 블록 이름
            text: 식 한 줄(`#` 뒤는 설명)
            desc: 설명(text에 `#`이 없을 때)
            from_part: 옮겨 올 부품(`블록:목표`)

        돌려주는 것
            PartChange — .part(새 부품 이름) · .files · .change · .moved_from

        오류
            ProjectError: 없는 블록 · 여러 줄 · 식 문법 · 그 블록에 같은 목표가 이미 있음 · 같은 블록에서 옮김

        예
            >>> import tempfile, os
            >>> p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
            >>> _ = p.block_define("single", desc="개별 식")
            >>> r = p.part_add("single", "M2 c Y RL", desc="통화수요")
            >>> r.part, p.part("single:M2").desc
            ('single:M2', '통화수요')

        관련
            part_remove · block_define · used_by
        """
        from .records import history_of
        from .partedit import ADOPTED, PartChange, add_text, adopted_without, remove_text
        new, pid, rel, line = add_text(self, block, text, desc)
        files = {rel: new}
        moved = None
        if from_part:
            try:
                src = self.part(from_part)
            except KeyError as e:
                raise ProjectError(str(e.args[0]) if e.args else f"없는 부품 {from_part}") from None
            if src.block == block:
                raise ProjectError(f"{src.id}는 이미 블록 {block}에 있습니다")
            rtext, rrel, moved = remove_text(self, src.id)
            files[rrel] = rtext
            adop = adopted_without(self, src.id)
            if adop is not None:
                files[ADOPTED] = adop
        ch = history_of(self).write_files(files, who or detect_who("python"), command or f"block add {block}",
                                          note=f"{pid}" + (f" ← {moved}" if moved else " 새 식"))
        self._reset()
        return PartChange("add", pid, sorted(files), ch.id if ch else None, moved, line)

    def part_remove(self, part: str, who: str = None, command: str = None) -> "PartChange":
        """블록에서 식 한 줄을 뺀다 — 그 줄만 지우고(다른 줄·주석은 그대로) 채택표의 그 부품 줄도 함께 지운다. 바뀜 기록에 남긴다.

        오류
            ProjectError: 없는 부품 · 파일이 그사이 바뀜

        예
            >>> import tempfile, os
            >>> p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
            >>> r = p.part_remove("finance:M2")
            >>> r.part, [x.id for x in p.parts("finance")]
            ('finance:M2', ['finance:RL'])

        관련
            part_add
        """
        from .records import history_of
        from .partedit import ADOPTED, PartChange, adopted_without, remove_text
        new, rel, pid = remove_text(self, part)
        files = {rel: new}
        adop = adopted_without(self, pid)
        if adop is not None:
            files[ADOPTED] = adop
        ch = history_of(self).write_files(files, who or detect_who("python"), command or f"block remove {pid}", note=f"{pid} 뺌")
        self._reset()
        return PartChange("remove", pid, sorted(files), ch.id if ch else None)

    def desk_show(self, name: str, who: str = None) -> dict:
        """Equion Desk(데스크톱 앱)에 "이 화면을 열어 달라"고 알린다 — 화면 이동만 하고 아무것도 계산하거나 바꾸지 않는다.

        이름을 확인한 뒤 `work/desk/requests.jsonl`에 한 줄을 덧붙인다. 이 프로젝트를 열어 둔 앱이 그 줄을 보고 화면을 연다(앱이 떠 있지 않으면
        아무 일도 일어나지 않는다). Claude가 방금 만든 기록·제안을 사람 앞에 띄울 때 쓴다.

        매개변수
            name: 기록(`est:…`·`hs:…`·`sim:…`·`an:…`·`run:…`) · 제안(`prop:p1`) · 자료 회차(`data:d2026-11a`) · 부품(`demand:CN`) ·
                  모형(`model:main`) · 프로젝트 안의 파일 경로 · 화면 이름(home·data·analysis·forecast·reports·records·changes·proposals)

        돌려주는 것
            사전 — show(이름) · kind(record·proposal·data·part·model·file·place) · file(요청 파일)

        오류
            ProjectError: 없는 기록·제안·부품·모형·파일(아무것도 쓰지 않음)

        예
            >>> import tempfile, os
            >>> p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
            >>> p.desk_show("demand:CN")["kind"], p.desk_show("model:main")["kind"], p.desk_show("forecast")["kind"]
            ('part', 'model', 'place')

        관련
            propose · history
        """
        from .deskreq import request_show
        return request_show(self, name, who=who)

    def milestones(self) -> List[dict]:
        """이정표 목록(만든 때 순) — 이름·메모·만든 때·누가·자료 회차·정의 파일 수·고정한 기록.

        예
            >>> import tempfile, os
            >>> p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
            >>> p.milestones()
            []
        """
        from . import milestones
        return [{**m.to_dict(), "files": len(m.files)} for m in milestones.list_all(self)]

    def milestone_make(self, name: str, note: str = None, who: str = None):
        """이정표를 만든다(명령줄 `equion milestone make`) — 지금의 정의 파일 사본·자료 회차·고정한 기록을 `work/milestones/이름/`에.
        정의 파일은 바꾸지 않는다. 이정표가 적은 기록은 정리(`work clean`)에서 빠진다.

        돌려주는 것
            Milestone — .name · .vintage · .files(경로 → 해시) · .records

        예
            >>> import tempfile, os
            >>> p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
            >>> m = p.milestone_make("fc_2026_11", note="11월 전망 확정")
            >>> m.name, m.vintage == p.vintage, "equion.toml" in m.files
            ('fc_2026_11', True, True)

        관련
            milestone_diff · milestone_restore
        """
        from . import milestones
        return milestones.make(self, name, note=note, who=who)

    def milestone_diff(self, name: str):
        """이정표와 지금 — 정의 파일마다 같음·고침·새로·지움과 차이, 자료 회차(명령줄 `equion milestone show`).

        예
            >>> import tempfile, os
            >>> p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
            >>> _ = p.milestone_make("m1")
            >>> p.milestone_diff("m1").same
            True
        """
        from . import milestones
        return milestones.diff(self, name)

    def milestone_restore(self, name: str, files=None, who: str = None, command: str = None):
        """정의를 이정표 때로 되돌린다(명령줄 `equion milestone restore`) — 그때 있던 파일은 그때 내용으로, 그 뒤에 생긴 정의 파일은
        지운다(files를 주면 그 파일만). 바뀜 기록 하나로 남아 그것도 되돌릴 수 있다. 계산은 하지 않는다.

        돌려주는 것
            바뀜 기록(Change) — 바뀐 것이 없으면 None

        예
            >>> import tempfile, os
            >>> p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
            >>> _ = p.milestone_make("m1")
            >>> with open(os.path.join(p.root, "EQUATIONS", "price.txt"), "a", encoding="utf-8") as f:
            ...     _ = f.write("# 이정표 뒤에 더한 줄" + chr(10))
            >>> p.milestone_restore("m1") is not None, p.milestone_diff("m1").same
            (True, True)

        관련
            milestone_make · milestone_diff · history
        """
        from . import milestones
        return milestones.restore(self, name, files=files, who=who or detect_who("python"), command=command)

    def bundle(self, out: str = None, raw: bool = False, records: str = "keep", who: str = None):
        """프로젝트를 zip 하나로 묶는다(명령줄 `equion bundle make`) — 정의·노트·보고서·지금 자료 회차·이정표, 기록은 records
        (keep: 채택·고정·가리키는 것 · all · none), 원자료(DATA/raw/)는 raw=True일 때만. 바뀜 기록과 화면 상태는 넣지 않는다.

        돌려주는 것
            BundleResult — .path(기본 exports/<프로젝트>_<날짜>.zip) · .files · .bytes · .records · .raw · .left_out

        예
            >>> import tempfile, os
            >>> p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
            >>> b = p.bundle()
            >>> b.path.startswith("exports/demo_"), b.raw
            (True, False)

        관련
            Project.from_bundle
        """
        from .bundle import make
        return make(self, out=out, raw=raw, records=records, who=who or detect_who("python"))

    @classmethod
    def from_bundle(cls, zip_path: str, dest: str) -> "Project":
        """묶음(zip)을 빈 폴더 dest에 풀고 프로젝트로 연다(명령줄 `equion bundle open`). zip 안의 경로가 폴더 밖을 가리키면 거절한다.

        예
            >>> import tempfile, os
            >>> p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
            >>> b = p.bundle()
            >>> q = eqn.Project.from_bundle(os.path.join(p.root, b.path), os.path.join(tempfile.mkdtemp(), "copy"))
            >>> q.vintage == p.vintage
            True
        """
        from .bundle import open_bundle
        res = open_bundle(zip_path, dest)
        return cls.open(res["path"])

    def scenarios(self) -> List[dict]:
        """시나리오 목록(`SCENARIOS/*.toml`, 이름순) — 이름·파일·설명·가정 세트·모형·충격·식 보정. 읽지 못한 파일은 `error`로.

        예
            >>> import tempfile, os
            >>> p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
            >>> [(x["name"], [s["var"] for s in x["shocks"]]) for x in p.scenarios()]
            [('oil20', ['POIL'])]

        관련
            scenario_define · sim
        """
        from .scenarios import FOLDER
        from .sim import load_scenario
        out = []
        folder = os.path.join(self.root, FOLDER)
        names = sorted(os.path.splitext(f)[0] for f in os.listdir(folder) if f.lower().endswith(".toml")) if os.path.isdir(folder) else []
        for n in names:
            try:
                sc = load_scenario(self, n)
                out.append({k: sc[k] for k in ("name", "file", "desc", "base", "addfactors", "model", "shocks", "addfactor")})
            except ProjectError as e:
                out.append({"name": n, "file": f"{FOLDER}/{n}.toml", "error": str(e)})
        return out

    def scenario_define(self, name: str, desc: str = None, base: str = None, addfactors: str = None, model: str = None,
                        shocks=None, addfactor=None, who: str = None, command: str = None):
        """시나리오를 더하거나 고친다 — `SCENARIOS/이름.toml`(명령줄 `equion scenario define`). 준 것만 바꾸고(글은 빈 글이면 그 키를 지움),
        shocks·addfactor는 목록을 주면 통째로 바꾼다. 쓰기 전에 새 내용 전체를 검사하고(자료에 없는 변수·없는 식·가정 세트·모형·기간),
        주석은 그대로 두며 바뀜 기록에 남긴다. 시나리오는 풀지 않는다 — 풀기는 `sim`.

        매개변수
            name: 시나리오 이름(없으면 새로 — 'base'는 기준선 이름이라 쓰지 않는다)
            desc · base(가정 세트) · addfactors(보정항) · model: 글
            shocks: 충격 목록 — 사전 {var, pct 또는 value, from, to} 또는 글 "POIL=+20%" · "R=+0.5@start:start+3"
            addfactor: 식 보정 목록 — 사전 {eq, value, from, to} 또는 글 "demand:CN=-0.2@start:start+3"

        돌려주는 것
            ScenarioChange — .name · .file · .new · .change(바뀜 기록) · .shocks · .addfactor

        오류
            ProjectError: 이름·꼴이 틀림·자료에 없는 변수·없는 식·가정 세트(아무것도 쓰지 않음)

        예
            >>> import tempfile, os
            >>> p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
            >>> r = p.scenario_define("rate1", desc="금리 1%p 인상", shocks=["R=+1@start:start+3"])
            >>> r.new, r.file, r.shocks
            (True, 'SCENARIOS/rate1.toml', 1)

        관련
            scenarios · scenario_remove · sim
        """
        from .records import history_of
        from .scenarios import ScenarioChange, scenario_text
        text, new, raw = scenario_text(self, name, desc=desc, base=base, addfactors=addfactors, model=model, shocks=shocks,
                                       addfactor=addfactor)
        rel = f"SCENARIOS/{name}.toml"
        ch = history_of(self).write_files({rel: text}, who or detect_who("python"), command or f"scenario define {name}",
                                          note=rel + (" 새 시나리오" if new else ""))
        return ScenarioChange(name, rel, new=new, change=ch.id if ch else None, shocks=len(raw.get("shock") or []),
                              addfactor=len(raw.get("addfactor") or []))

    def scenario_remove(self, name: str, who: str = None, command: str = None):
        """시나리오 파일을 지운다(명령줄 `equion scenario remove`) — 바뀜 기록에 남아 되돌릴 수 있다. 그 시나리오로 푼 기록은 그대로다.

        예
            >>> import tempfile, os
            >>> p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
            >>> p.scenario_remove("oil20").removed
            True
        """
        from .records import history_of
        from .scenarios import FOLDER, ScenarioChange
        if not isinstance(name, str) or not name or "/" in name or "\\" in name:
            raise ProjectError(f"시나리오 이름 {name!r}")
        rel = f"{FOLDER}/{name}.toml"
        if not os.path.isfile(os.path.join(self.root, FOLDER, f"{name}.toml")):
            raise ProjectError(f"시나리오가 없습니다: {rel}")
        ch = history_of(self).write_files({rel: None}, who or detect_who("python"), command or f"scenario remove {name}", note=f"{rel} 지움")
        return ScenarioChange(name, rel, removed=True, change=ch.id if ch else None)

    def note_add(self, note: str, lines=None, record: str = None, title: str = None, who: str = None, command: str = None):
        """노트 끝에 ```` ```equion ```` 블록 하나를 더한다(명령줄 `equion note add`) — lines(명령 줄들)는 실행하지 않고 블록만,
        record를 주면 그 기록을 만든 명령과 결과 구역(카드)을 함께. 노트가 없으면 만든다(제목 title). 블록의 줄은 노트가 부를 수 있는
        명령(등록부의 계산·보기)이어야 한다. 바뀜 기록에 남긴다. 실행은 `note_run`.

        매개변수
            note: 노트 경로(예: notes/invest.md — 프로젝트 안)
            lines: 명령 줄 목록(앞의 equion은 빼도 된다) — 예: ["est 'I c Y' --for demand:I", "est 'I c Y I(-1)' --for demand:I"]
            record: 기록 이름(an:… · est:… — 그 명령과 카드를 담는다)

        돌려주는 것
            NoteAdded — .file · .new · .block(더한 블록 번호) · .change

        예
            >>> import tempfile, os
            >>> p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
            >>> r = p.note_add("notes/check.md", lines=["an unitroot R", "an stats Y"], title="자료 점검")
            >>> r.new, r.file, r.block
            (True, 'notes/check.md', 1)

        관련
            note_run · note_check
        """
        from .notes import add_block
        return add_block(self, note, lines=lines, record=record, title=title, who=who, command=command)

    def views(self) -> List[dict]:
        """저장한 보기(`VIEWS/*.toml`) — 어느 시리즈를 어떤 모양으로 볼지(이름순). 보기마다 name·title·series·show·range·file.

        예
            >>> import tempfile, os
            >>> p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
            >>> _ = p.view_define("core", series=["Y", "CN"], show="yoy", title="핵심 지표")
            >>> [(v["name"], v["series"], v["show"]) for v in p.views()]
            [('core', ['Y', 'CN'], 'yoy')]

        관련
            view_define
        """
        from .views import load_views
        return [v.to_dict() for v in load_views(self.root)]

    def view_define(self, name: str, series=None, show: str = None, title: str = None, range: str = None, who: str = None,
                    command: str = None) -> "ViewChange":
        """보기 저장 — `VIEWS/이름.toml`에 시리즈와 보이기(level·qoq·yoy·annual·diff)·제목·구간을 적는다. 준 것만 바꾸고(None은 그대로,
        빈 글은 그 키를 지움), 시리즈 이름이 자료에 있는지 본 뒤 쓴다. 바뀜 기록에 남긴다. 보기는 결과를 만들지 않는다 — 과거 재현·전망·
        시나리오의 결과를 같은 시리즈·같은 모양으로 다시 보는 데 쓴다.

        매개변수
            name: 보기 이름(없으면 새로 — 그때 series가 있어야 한다)
            series: 시리즈 이름들(목록 또는 쉼표·공백으로 띄운 글)
            show: level(수준) · qoq(전기비) · yoy(전년동기비) · annual(연간) · diff(기준선 대비)
            title: 제목
            range: 구간 "시작:끝"(상대 기간 가능 — 없으면 결과의 구간 그대로)

        돌려주는 것
            ViewChange — .name · .file · .new · .series · .change(바뀜 기록)

        오류
            ProjectError: 이름·series가 없음·모르는 show·자료에 없는 시리즈(아무것도 쓰지 않음)

        예
            >>> import tempfile, os
            >>> p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
            >>> r = p.view_define("core", series="Y, CN, P", show="yoy")
            >>> r.new, r.file, r.series
            (True, 'VIEWS/core.toml', ['Y', 'CN', 'P'])

        관련
            views · report_add
        """
        from .records import history_of
        from .views import ViewChange, view_text
        text, new, spec = view_text(self.root, name, series=series, show=show, title=title, range=range,
                                    known=[str(c) for c in self.workfile.data.columns])
        ch = history_of(self).write_files({spec.file: text}, who or detect_who("python"), command or f"view define {name}",
                                          note=f"{spec.file}" + (" 새 보기" if new else ""))
        return ViewChange(name, spec.file, new, ch.id if ch else None, list(spec.series))

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

    def _part_key(self, part: Part) -> tuple:
        """식 하나의 계수 출처 열쇠 — 채택 기록·바꿔 끼운 기록·지금 자료 추정이 서로 섞이지 않게."""
        if part.line == 0:
            sv = self._swap_saved.get((part.id, part.expr))
            return (part.id, part.expr, f"swap:{sv[0]}" if sv else "swap")
        rid = self.adopted.get(part.id)
        return (part.id, part.expr, f"adopted:{rid}" if rid else "estimated")

    def _estimate(self, part: Part):
        """식 하나의 워크파일 방정식 객체 — 채택 기록이 있고 글자가 같으면 그 계수(다시 추정하지 않음, D35), 바꿔 끼운 기록이면
        그 기록의 계수, 아니면 지금 자료로 추정."""
        from ..estimation.equation import Equation
        from ..workfile.objects import EquationObject
        from ..work.store import RecordError
        from .records import store_of
        wf = self.workfile
        key = self._part_key(part)
        obj = self._est.get(key)
        if obj is not None:
            return obj
        nm = f"{part.block}_{part.target}"
        if part.line == 0:                      # 바꿔 끼운 식 — 글자마다 다른 이름(같은 식은 같은 이름)
            import hashlib
            nm += "_s" + hashlib.md5((part.expr + key[2]).encode("utf-8")).hexdigest()[:6]
        if wf._col(nm) is not None:
            nm = "eq_" + nm
        wf._objects.pop(nm.lower(), None)
        obj = EquationObject(wf, nm)
        saved, src = None, ("estimated" if part.line else "swap")
        if key[2].startswith("swap:"):
            saved, src = self._swap_saved[(part.id, part.expr)][1], key[2]
        elif key[2].startswith("adopted:"):
            rid = key[2][len("adopted:"):]
            try:
                rec = store_of(self).get(rid, "est")
                if rec.meta.get("expr") == part.expr:
                    saved, src = rec.meta["equation"], key[2]
                else:
                    self.notes.append(f"{part.id}: 채택 기록 {rid}의 식이 블록 파일과 다릅니다 — 지금 자료로 추정")
            except RecordError:
                self.notes.append(f"{part.id}: 채택 기록 {rid}이 없습니다 — 지금 자료로 추정")
            if saved is None:
                src = "estimated"
        if saved is not None:
            eq = quiet(Equation.restore, saved, wf._data)
            eq.wt = wf._wt
        else:
            eq = obj._make(part.expr)
        wf._register(obj)
        obj._adopt(eq, part.expr, loud=False)
        self._est[key] = obj
        self._sources[key] = src
        return obj

    @property
    def adopted(self) -> Dict[str, str]:
        """채택표(EQUATIONS/adopted.toml) — {부품: est:기록}. 모형은 이 기록의 계수로 푼다(D35).

        예
            >>> import tempfile, os
            >>> p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
            >>> p.adopted
            {}
        """
        from .records import read_adopted
        return read_adopted(self.root)

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
        if swap and any(str(v).strip().startswith("est:") for v in swap.values()):
            from .records import _resolve_swap
            swap, _ = _resolve_swap(self, swap)
        rep = self.assemble(name, swap=swap)
        if not rep.ok:
            raise ProjectError([f"모형 {name}을(를) 조립할 수 없습니다:"] + rep.problems)
        wf = self.workfile
        obj = self._obj_name(name)
        wf._objects.pop(obj.lower(), None)
        m = wf.model(obj)
        new, used = [], []
        n0 = len(self.notes)
        for x in rep.parts:
            if x.kind == "identity":
                m.append(x.expr)
            else:
                fresh = self._part_key(x) not in self._est
                m.merge(self._estimate(x))
                src = self._sources.get(self._part_key(x), "")
                if fresh and src == "estimated":
                    new.append(x.id)
                elif fresh and src.startswith("adopted:"):
                    used.append(f"{x.id}({src[8:]})")
        for note in self.notes[n0:]:
            say(f"[{name}] {note}")
        if used:
            note = f"채택 계수: {', '.join(used)}"
            self.notes.append(note)
            say(f"[{name}] {note}")
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

    def hs(self, name: str = None, start=None, end=None, mode: str = None, swap: dict = None, record: bool = False,
           vs: str = None, as_name: str = None, who: str = None, command: str = None, **opts):
        """과거 재현(HS) — 모형이나 블록을 풀어 실측과 견준다. 블록이면 그 블록만 풀고 나머지 변수는 실측(블록 HS).

        구간·방식의 기본은 equion.toml `[hs]`의 range·mode, 없으면 자료 전체·dynamic. 풀이 값은 워크파일의 별칭 시리즈(`CN_0` …)에 쓴다.

        매개변수
            name: 모형 또는 블록 이름(기본: [hs] model)
            start, end: 구간(기본: [hs] range)
            mode: 'dynamic' · 'static' · 'fit'(기본: [hs] mode)
            swap: {부품: 식 또는 est:기록} — 그 식만 바꿔 끼워 푼다(파일은 그대로). 기록이면 그 기록의 계수로
            record: 참이면 작업 기록(`work/hs/<이름>/` — 조립 명세·적합도·풀린 값·summary.md)을 남기고 HSRecord를 돌려준다
            vs: 견줄 HS 기록(record=True일 때 — 변수별 RMSPE 전후)
            as_name: 기록 이름(기본 hs_0001, hs_0002 …)
            who, command: 기록에 적을 '누가'·'명령'(명령줄이 채운다)
            **opts: ModelObject.solve의 선택지(on_missing · on_fail · tolerance …)

        돌려주는 것
            SolveResult — .statistics() · .counts() · .summary() (record=True면 HSRecord — .id · .stats · .text())

        예
            >>> import tempfile, os
            >>> p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
            >>> r = p.hs("main")
            >>> r.start, r.end, r.counts()["ok"]
            ('2005Q1', '2019Q4', 60)
            >>> p.hs("demand").counts()["ok"]
            60
        """
        if record:
            from .records import run_hs
            return run_hs(self, name, start, end, mode, swap=swap, vs=vs, as_name=as_name, who=who, command=command,
                          **opts)
        name = self._default(name)
        m = self.model(name, swap=swap)
        start, end = self._range(start, end)
        mode = mode or self.config.hs.get("mode") or "dynamic"
        return m.solve(start, end, mode=mode, **opts)

    # ---- 작업 명령(기록을 남긴다, D33) ----------------------------------
    def est(self, target: str, method: str = None, smpl: str = None, as_name: str = None, part: str = None,
            sim: bool = False, cov: str = None, who: str = None, command: str = None):
        """식 하나를 추정해 작업 기록(`work/est/<이름>/`)을 남긴다 — 부품(블록 파일의 그 줄) 또는 식 글자(후보).

        식 글자의 목표변수가 한 부품의 목표면 그 부품의 후보가 된다(여럿이면 part로). 판단 기준(`[criteria]` — 기대 부호·진단·|t|)이
        있으면 통과·걸러짐과 까닭을 적는다. 채택은 따로(`adopt`).

        매개변수
            target: 부품 `블록:목표` 또는 식 글자(예: "CN c Y CN(-1)")
            method: 'auto'(기본 — @inst가 있으면 tsls) · 'ls' · 'tsls'
            smpl: 표본 'S:E'(상대 기간 가능 — '1990Q1:last')
            as_name: 기록 이름(기본: 목표변수_0001 …)
            part: 어느 부품의 후보인지(목표가 같은 식이 여럿일 때)
            sim: 참이면 식 하나의 동태 모의([hs] range — 다른 변수는 실측)와 RMSPE
            cov: 계수 공분산('white' · 'hac' …)

        돌려주는 것
            EstRecord — .id · .coefs · .passed · .meta · .text()

        오류
            ProjectError: 항등식·추정할 수 없는 식 · RecordError: 이미 있는 기록 이름

        예
            >>> import tempfile, os
            >>> p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
            >>> r = p.est("CN c Y CN(-1) CN(-2)", as_name="cn_lag2")
            >>> r.id, r.meta["part"], r.meta["n"]
            ('est:cn_lag2', 'demand:CN', 198)
        """
        from .records import run_est
        return run_est(self, target, method=method, smpl=smpl, as_name=as_name, part=part, sim=sim, cov=cov, who=who,
                       command=command)

    def adopt(self, record: str, part: str = None, who: str = None, command: str = None):
        """추정 기록을 그 부품의 채택 계수로 — 블록 파일의 그 줄을 기록의 식으로 바꾸고(다르면) 채택표 `EQUATIONS/adopted.toml`을
        고친다(주석·순서 그대로). 바뀜 기록에 남고, 그 뒤 모형은 이 계수로 푼다(다시 추정하지 않음).

        돌려주는 것
            AdoptResult — .part · .record · .previous · .line_changed · .change(바뀜 기록) · .text()

        예
            >>> import tempfile, os
            >>> p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
            >>> r = p.est("demand:CN", as_name="cn_now")
            >>> p.adopt("est:cn_now").line_changed, p.adopted
            (False, {'demand:CN': 'est:cn_now'})
        """
        from .records import adopt
        return adopt(self, record, part=part, who=who, command=command)

    def compare(self, *records: str, target: str = None, part: str = None):
        """기록 비교 — 추정 기록이면 식·표본·적합 통계·진단·기준·단독 모의 표(종속변수·표본이 다르면 경고), HS 기록이면 변수별 RMSPE.

        매개변수
            *records: 기록 이름(est:… · hs:…)
            target: 이 목표변수의 추정 기록 전부 · part: 이 부품의 후보 전부

        돌려주는 것
            CompareResult — .table(DataFrame) · .warnings · .text()

        예
            >>> import tempfile, os
            >>> p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
            >>> _ = p.est("CN c Y CN(-1)", as_name="a")
            >>> _ = p.est("CN c Y", as_name="b")
            >>> list(p.compare(target="CN").table.index)
            ['est:a', 'est:b']
        """
        from .records import compare
        return compare(self, list(records), target=target, part=part)

    def replay(self, record: str, as_name: str = None, who: str = None, command: str = None):
        """HS 기록을 그때 그대로 다시 — 기록의 조립 명세(식 글자·계수·자료 회차·구간·방식)로 푼다. 지금 파일과 무관하고, 원래 기록의
        풀린 값과 견주어(`.meta['replay']` — same · max_abs_diff) 새 기록을 남긴다.

        예
            >>> import tempfile, os
            >>> p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
            >>> h = p.hs("main", record=True)
            >>> p.replay(h.id).meta["replay"]["same"]
            True
        """
        from .records import replay_hs
        return replay_hs(self, record, as_name=as_name, who=who, command=command)

    def sim(self, scenario: str = "base", model: str = None, range: str = None, vintage: str = None, vs: str = None,
            as_name: str = None, mode: str = None, who: str = None, command: str = None):
        """전망·시나리오 — 가정 세트(`ASSUMPTIONS/이름.csv`, 빈 외생은 `[forecast] fill`)·보정항(`ADDFACTORS/이름.toml`)·시나리오
        (`SCENARIOS/이름.toml`)로 풀고 작업 기록(`work/sim/<이름>/`)을 남긴다. 시나리오면 같은 가정·보정항의 기준선도 풀어 차이를 적는다.

        매개변수
            scenario: 'base'(기준선 — 파일이 없어도 된다) 또는 SCENARIOS/의 이름
            model: 모형(기본: 시나리오의 model → [forecast] model → [hs] model)
            range: 전망 구간(기본 [forecast] range, 없으면 'next:8')
            vintage: 다른 자료 회차로(지금 회차는 그대로)
            vs: 견줄 전망 기록(sim:…) — 연간 증가율 전후
            as_name: 기록 이름(기본: 연-월_시나리오)
            mode: 'dynamic'(기본) · 'static'

        돌려주는 것
            SimRecord — .id · .levels · .flags(값의 종류) · .annual · .diff · .text()

        오류
            ProjectError: 없는 시나리오·가정·보정항 파일, 파일 문법, 전망 구간의 외생이 비어 채우지 못함

        예
            >>> import tempfile, os
            >>> p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
            >>> r = p.sim(as_name="base_a")
            >>> r.meta["range"], r.counts()["ok"]
            (['2020Q1', '2021Q4'], 8)
            >>> p.sim("oil20", as_name="oil_a").meta["vs_base"]["P"] > 0
            True
        """
        from .sim import run_sim
        return run_sim(self, scenario, model=model, rng=range, vintage=vintage, vs=vs, as_name=as_name, mode=mode,
                       who=who, command=command)

    # ---- 분석·노트·보고서(D37) ------------------------------------------
    def an(self, analysis: str, target: str, smpl: str = None, as_name: str = None, note: str = None, who: str = None,
           command: str = None, **options):
        """분석 하나 — 등록부(`equion.registry`)의 분석을 돌려 기록(`work/an/<이름>/` — 표 CSV·차트 CSV·카드 summary.md)을 남긴다.

        분석 목록은 `eqn.registry.table()`(명령줄 `equion an list`). 계절조정·파생은 미리보기만 하고 `keep`이 정의로, ECM·VAR·VECM·시스템은
        `keep`이 식 후보로 남긴다. 나머지(요약·단위근·공적분·식 진단·예측 평가·안정성·승수)는 아무 파일도 바꾸지 않는다.

        매개변수
            analysis: 분석 이름(summary · unitroot · coint · diag · fcsteval · stability · multipliers · seas · genr · ecm · var · vecm · system)
            target: 대상 — 시리즈·묶음([group])·식('log(Y) R')·부품·est: 기록·모형·블록·'이름 = 식'(분석마다)
            smpl: 표본 'S:E'(상대 기간 가능)
            as_name: 기록 이름(기본 분석_0001 …)
            note: 노트 경로 — 그 끝에 명령 블록과 결과 구역을 더한다
            **options: 분석의 옵션(`equion an <분석> --help`)

        돌려주는 것
            AnRecord — .id · .table(k) · .meta · .text()

        예
            >>> import tempfile, os
            >>> p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
            >>> r = p.an("unitroot", "dlog(Y) R")
            >>> r.table(1)["판단"].tolist()
            ['정상', '단위근']
        """
        from .analyses import run_an
        return run_an(self, analysis, target, options, smpl=smpl, as_name=as_name, note=note, who=who, command=command)

    def keep(self, record: str, as_name: str = None, replace: bool = False, who: str = None, command: str = None):
        """분석 기록을 남긴다 — 만드는 분석(계절조정·파생)은 정의(`series.toml`·`derived.txt`, `made_by` = 기록)로, 부품을 내는
        분석(ECM·VAR·VECM·시스템)은 식 후보(est: 기록 — 계수 그대로)로. 정의를 고치면 바뀜 기록에 남고, 자료에는 `data build`로 들어간다.

        예
            >>> import tempfile, os
            >>> p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
            >>> k = p.keep(p.an("genr", "GAP = Y - CN - I").id)
            >>> k.kind, k.what[0]
            ('derived', 'DATA/derived.txt: GAP = Y - CN - I   # an:genr_0001')
        """
        from .analyses import keep
        return keep(self, record, as_name=as_name, replace=replace, who=who, command=command)

    def note_run(self, note: str, block: int = None, stale: bool = False, force: bool = False, who: str = None,
                 command: str = None):
        """노트의 ```` ```equion ```` 블록을 실행해 블록 아래 결과 구역을 채운다(블록마다 새 기록). 블록은 등록부의 계산·보기 명령만
        부를 수 있고, 손으로 고친 구역은 force일 때만 덮는다. Python 블록은 block으로 고를 때만 돈다.

        돌려주는 것
            NoteResult — .blocks(블록마다 상태) · .ok · .change · .text()

        예
            >>> import tempfile, os
            >>> p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
            >>> _ = open(os.path.join(p.root, "n.md"), "w", encoding="utf-8").write("# n\\n\\n```equion\\nan unitroot R\\n```\\n")
            >>> [b.status for b in p.note_run("n.md").blocks]
            ['run']
        """
        from .notes import run_note
        return run_note(self, note, block=block, stale=stale, force=force, who=who, command=command)

    def note_check(self, note: str):
        """노트 검사(실행하지 않고) — 블록마다 실행 안 함 · 없는 기록 · 낡음(자료·정의가 바뀜) · 손으로 고침 · 허용 안 된 명령.

        예
            >>> import tempfile, os
            >>> p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
            >>> _ = open(os.path.join(p.root, "n.md"), "w", encoding="utf-8").write("```equion\\nan unitroot R\\n```\\n")
            >>> [b.status for b in p.note_check("n.md").blocks]
            ['never']
        """
        from .notes import check_note
        return check_note(self, note)

    def report_new(self, name: str, title: str = None, from_report: str = None, exist_ok: bool = False, who: str = None,
                   command: str = None):
        """새 보고서(`reports/이름.md`) — 틀(제목·날짜·자료 회차·모형). from_report면 지난 보고서를 복사하고 구역마다 바꿔 낄 기록을 제안한다.
        exist_ok면 이미 있는 보고서는 그대로 둔다(`.exists` — 스크립트를 같은 회차로 다시 돌릴 때 글을 지키려고).

        예
            >>> import tempfile, os
            >>> p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
            >>> p.report_new("monthly").report
            'reports/monthly.md'
        """
        from .reports import new_report
        return new_report(self, name, title=title, from_report=from_report, exist_ok=exist_ok, who=who, command=command)

    def report_add(self, report: str, record: str, rows=None, show: str = "level", annual: bool = False, digits: int = None,
                   title: str = None, chart: bool = False, under: str = None, key: str = None, force: bool = False,
                   who: str = None, command: str = None):
        """보고서로 보내기 — 기록의 표(와 차트)를 고른 모양(행·보이기·연간·소수점)으로 보고서에 넣는다. 구역에는 보이지 않는 표시
        (기록·보낸 날·자료 회차·모양)가 붙고, 차트 자료는 보고서 옆 `_data/`로 복사한다.

        매개변수
            record: 기록(sim:… · hs:… · est:… · an:…#표 번호)
            rows: 행(시리즈·변수 목록) · show: 'level' · 'qoq' · 'yoy' · 'diff'(전망) · annual: 연간(전망)
            digits: 소수점 · title: 표 제목(번호는 저절로) · chart: 차트도 · under: 그 제목 아래 끝에
            key: 구역 이름 — 같은 이름의 구역이 있으면 그 자리에서 이 기록으로 바꾼다(손으로 고친 구역은 force일 때만)

        예
            >>> import tempfile, os
            >>> p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
            >>> _ = p.report_new("m")
            >>> s = p.sim(as_name="b")
            >>> p.report_add("m", "sim:b", rows=["Y", "CN"], show="yoy", annual=True).items[0]["detail"]
            '**표 1. 전망 — base (main)** (연간 증가율, %)'
        """
        from .reports import add
        return add(self, report, record, rows=rows, show=show, annual=annual, digits=digits, title=title, chart=chart,
                   under=under, key=key, force=force, who=who, command=command)

    def report_check(self, report: str):
        """보고서 검사 — 구역마다 없는 기록 · 더 새 기록(같은 갈래) · 낡음(자료·정의가 바뀜) · 손으로 고침.

        예
            >>> import tempfile, os
            >>> p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
            >>> _ = p.report_new("m")
            >>> _ = p.report_add("m", p.hs("main", record=True).id)
            >>> p.report_check("m").items[0]["status"]
            '정상'
        """
        from .reports import check
        return check(self, report)

    def report_update(self, report: str, region: int = None, to: str = None, dry_run: bool = False, force: bool = False,
                      who: str = None, command: str = None):
        """새 기록으로 바꾸기 — 구역을 같은 모양으로 다시 만들어 차이를 보이고 적용한다(기본: 같은 갈래의 가장 새 기록). 손으로 고친 구역은
        고친 곳을 차이로 보이고 force일 때만 덮는다.

        예
            >>> import tempfile, os
            >>> p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
            >>> _ = p.report_new("m")
            >>> _ = p.report_add("m", p.hs("main", record=True).id)
            >>> h2 = p.hs("main", record=True, swap={"demand:CN": "CN c Y"})
            >>> p.report_update("m").items[0]["to"] == h2.id
            True
        """
        from .reports import update
        return update(self, report, region=region, to=to, dry_run=dry_run, force=force, who=who, command=command)

    def reestimate(self, name: str = None, adopt: str = "never", who: str = None, command: str = None):
        """모형(또는 블록)의 추정식을 블록 파일의 글자 그대로 지금 자료로 다시 추정해 기록을 남기고, 정책에 따라 새 계수를 채택한다
        (명령줄 `equion est --adopted [모형] --adopt 정책`, D35).

        매개변수
            name: 모형 또는 블록(기본: [hs] model)
            adopt: 'never'(기록만 — 기본) · 'if_pass'(판단 기준을 통과한 식만, 기준이 없으면 통과) · 'all'

        돌려주는 것
            ReestResult — .rows(식마다 옛·새 기록·기준·채택·계수 변화) · .adopted · .flagged · .change · .text()

        예
            >>> import tempfile, os
            >>> p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
            >>> r = p.reestimate("demand", adopt="all")
            >>> r.adopted, sorted(p.adopted)
            (['demand:CN', 'demand:I'], ['demand:CN', 'demand:I'])
        """
        from .records import reestimate
        return reestimate(self, name, adopt, who=who, command=command)

    def propose(self, name: str = None, title: str = "", why: str = "", parts: dict = None, files: dict = None,
                previews=(), who: str = None, command: str = None):
        """제안을 만든다 — 파일은 바꾸지 않고 "이렇게 바꾸면"을 `work/proposals/<이름>/`에 남긴다(바뀔 내용·까닭·미리 계산한 기록).

        매개변수
            name: 제안 이름(기본 p1, p2 …)
            title, why: 제목·까닭(사람이 읽는 글 — 근거 기록 이름을 넣는다)
            parts: {부품: est:기록(그 식으로 바꾸고 채택) 또는 식 글자}
            files: {프로젝트 안 경로: 새 내용 파일}
            previews: 미리 계산한 기록(hs:… · sim:… · est:…)

        돌려주는 것
            Proposal — .id · .status · .stale · .diff() · .text()

        예
            >>> import tempfile, os
            >>> p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
            >>> pr = p.propose(title="소비에 시차 하나 더", parts={"demand:CN": "CN c Y CN(-1) CN(-2)"})
            >>> pr.id, pr.status, p.part("demand:CN").text
            ('prop:p1', 'open', 'CN c Y CN(-1)')
        """
        from . import proposals
        return proposals.new(self, name, title=title, why=why, parts=parts, files=files, previews=list(previews),
                             who=who, command=command)

    def proposals(self):
        """제안 목록(만든 순) — 열림·적용·버림 모두.

        예
            >>> import tempfile, os
            >>> p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
            >>> _ = p.propose(parts={"demand:CN": "CN c Y"})
            >>> [(x.id, x.status) for x in p.proposals()]
            [('prop:p1', 'open')]
        """
        from . import proposals
        return proposals.proposals(self)

    def apply_proposal(self, name: str, force: bool = False, who: str = None, command: str = None):
        """제안을 적용한다 — 바꿀 파일을 새 내용으로 쓰고 바뀜 기록에 "제안 … 적용". 만든 뒤 파일이 바뀌었으면(낡음) force일 때만.

        예
            >>> import tempfile, os
            >>> p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
            >>> _ = p.propose(parts={"demand:CN": "CN c Y CN(-1) CN(-2)"})
            >>> p.apply_proposal("p1").status, p.part("demand:CN").text
            ('applied', 'CN c Y CN(-1) CN(-2)')
        """
        from . import proposals
        return proposals.apply(self, name, force=force, who=who, command=command)

    def drop_proposal(self, name: str, why: str = "", who: str = None):
        """제안을 버린다 — 파일은 그대로, 제안 기록은 남는다(상태 '버림').

        예
            >>> import tempfile, os
            >>> p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
            >>> _ = p.propose(parts={"demand:CN": "CN c Y"})
            >>> p.drop_proposal("p1", why="설명할 수 없다").status
            'dropped'
        """
        from . import proposals
        return proposals.drop(self, name, why=why, who=who)

    def export(self, records, xlsx: str) -> dict:
        """기록(est:· hs:· sim:· data:회차)을 엑셀 한 권으로 — 값·값의 종류·출처 시트. 기록은 남기지 않는다.

        돌려주는 것
            {path, sheets, records}

        예
            >>> import tempfile, os
            >>> p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
            >>> h = p.hs("main", record=True)
            >>> out = p.export([h.id, "data:" + p.vintage], "exports/hs.xlsx")
            >>> out["sheets"][:3]
            ['출처', 'hs_0001_적합도', 'hs_0001_해']
        """
        from .export import export_xlsx
        return export_xlsx(self, list(records), xlsx)

    # ---- 스크립트(.eqs, D36·E5) ----------------------------------------
    def run_script(self, script: str, sets: dict = None, from_step=None, dry_run: bool = False, fail_on: str = "failed",
                   name: str = None, who: str = None, command: str = None, echo=None, verbosity: int = 1,
                   python: bool = True):
        """Equion 스크립트(`.eqs`)를 실행하고 실행 기록 `work/run/<이름>/`(`run:`)을 남긴다 — 명령줄 `equion run x.eqs`.

        한 줄이 명령 하나이고 같은 프로세스에서 명령줄 그대로 돈다(단계의 기록·바뀜 기록에는 누가 '스크립트', 그 실행 이름).
        명령이 실패하면 거기서 멈추고 그 종료 코드, `expect --stop`에 걸리면 2, HS·전망 기록에 fail_on 상태의 기간이 있으면 2.

        매개변수
            script: 스크립트 경로(프로젝트 기준) · sets: --set {이름: 값}(값은 목록 또는 띄어 쓴 글자)
            from_step: 이 단계(번호 또는 ## 제목)부터 · dry_run: 미리보기(기록을 남기지 않음 → Plan)
            fail_on: 'failed'·'fallback'·'partial'·'never' · name: 실행 기록 이름(기본 <스크립트>_0001 …)
            echo: 단계마다 한 줄을 받는 함수(예: print) · python: Python 단계(py)를 돌릴지

        돌려주는 것
            RunResult — .id · .exit_code · .status · .steps(단계마다 .line·.status·.records) · .text()
            (dry_run이면 Plan — .steps · .problems · .text())

        오류
            ScriptError: 문법·명령·매개변수 문제(실행하지 않는다)

        예
            >>> import tempfile, os
            >>> p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
            >>> r = p.run_script("FLOWS/monthly.eqs", sets={"scenarios": "base"})
            >>> r.exit_code, r.steps[3].line, r.steps[2].status          # 기준 미달 식이 있으면 표시(!)하고 계속
            (0, 'hs main', 'flag')
        """
        from ..script import plan, run_script
        if dry_run:
            return plan(self, script, sets=sets, from_step=from_step)
        return run_script(self, script, sets=sets, from_step=from_step, fail_on=fail_on, name=name, who=who,
                          command=command, echo=echo, verbosity=verbosity, python=python)

    def check_script(self, script: str, sets: dict = None):
        """스크립트를 실행 없이 검사 — 문법·명령(허용 목록)·선택지·{이름}·매개변수·부품·모형·시나리오·노트·포함한 파일.

        돌려주는 것
            ScriptCheck — .ok · .problems · .changing(정의 파일을 바꾸는 단계) · .python · .text()

        예
            >>> import tempfile, os
            >>> p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
            >>> p.check_script("FLOWS/monthly.eqs").ok
            True
        """
        from ..script import check
        return check(self, script, sets=sets)

    def replay_run(self, run: str, who: str = None, command: str = None, echo=None):
        """실행 기록을 그때 그대로 다시 — 정의 사본(defs/)·받은 원자료·같은 스크립트(src/)·매개변수로 프로젝트 사본에서 돌리고
        단계마다 기록의 숫자를 견준다(허용오차). 프로젝트는 바꾸지 않고 견준 결과를 새 실행 기록(`replay_of`)으로 남긴다.

        돌려주는 것
            ReplayResult — .same · .steps(단계마다 verdict 같음·다름·detail) · .id · .exit_code(같으면 0, 다르면 2)

        예
            >>> import tempfile, os
            >>> p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
            >>> r = p.run_script("FLOWS/monthly.eqs", sets={"scenarios": "base"})
            >>> p.replay_run(r.id).same
            True
        """
        from ..script import replay
        return replay(self, run, who=who, command=command, echo=echo)

    def new_script(self, name: str, records=None, last: int = None, title: str = None, force: bool = False,
                   who: str = None, command: str = None) -> str:
        """작업 기록의 명령으로 스크립트 초안 `FLOWS/<이름>.eqs`(바뀜 기록에 남는다) — 탐색하며 한 일을 굳힌다.
        명령에서 -p·--as·--note·--json은 뺀다(다시 돌려도 이름이 겹치지 않게). 기록이 없으면 빈 틀.

        매개변수
            records: 기록 이름 목록 · last: 최근 기록 n개(실행 기록 run: 제외)

        예
            >>> import tempfile, os
            >>> p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
            >>> e = p.est("demand:CN", as_name="c1", command="equion est demand:CN --as c1")
            >>> rel = p.new_script("mine", records=[e.id])
            >>> open(os.path.join(p.root, rel), encoding="utf-8").read().splitlines()[3:5]
            ['## 추정', 'est demand:CN   # ← est:c1']
        """
        from ..script import new_script
        return new_script(self, name, records=records, last=last, title=title, force=force, who=who, command=command)

    def export_script(self, script: str, out: str = None, force: bool = False) -> str:
        """스크립트를 같은 일을 하는 Python 파일로(`eqn.script.session` — 같은 명령·같은 기록) → 프로젝트 기준 경로.

        예
            >>> import tempfile, os
            >>> p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
            >>> p.export_script("FLOWS/monthly.eqs")
            'FLOWS/monthly.py'
        """
        from ..script import export_py
        return export_py(self, script, out=out, force=force)

    @property
    def work(self):
        """작업 기록 저장소(`work/`) — .records(종류) · .get(이름) · .log() · .mark(…)."""
        from .records import store_of
        return store_of(self)

    @property
    def history(self):
        """바뀜 기록(`work/history/`) — .list() · .get(h0001) · .revert(h0001, who) · .scan()."""
        from .records import history_of
        return history_of(self)

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
