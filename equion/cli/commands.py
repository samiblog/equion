#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""명령줄 — `equion <명령>` (설치 시) 또는 `python -m equion <명령>` (DECISIONS D5·D6).

    equion run 스크립트.py [--smpl S:E] [--set 이름=값 ...] [--out 폴더] [--format csv,html] [-- 스크립트 인자]
    equion run FLOWS/monthly.eqs [--set 이름=값] [--from 단계] [--dry-run]  ·  equion run --replay run:이름   (스크립트 — D36)
    equion check 방정식.txt [--data 자료.xlsx] [--smpl S:E]    |  equion check 스크립트.py  |  equion check 스크립트.eqs
    equion info [경로]
    equion new 폴더 [--bare | --template desk]  ·  equion convert 옛파일 새이름 [--allow-pickle]
    equion assemble [모형] [-p 프로젝트]  ·  equion ident 블록:목표 [--check]     (프로젝트 — equion.toml, D32)
    equion data list|add 파일|build [--use]|use 회차|diff [A B]|impact [A B]      (자료 회차 — D34)
    equion est · adopt · compare · hs · sim · propose · export · work · history   (작업 명령·기록 — D33)
    equion an · note · report  (분석·노트·보고서 — D37)  ·  equion script new·export  (스크립트 — D36)
    equion guide [skill] [--path] [--install user|project]  (Claude용 모형 작업 안내·스킬 초안)

종료 코드: 0 성공 · 1 스크립트 오류 · 2 풀이 실패(--fail-on) · 3 입력 오류 · 130 중단
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime

from ..version import project_version
from .runner import EXIT_INPUT, EXIT_INTERRUPT, EXIT_OK, EXIT_SCRIPT, STATUS_KO, RunOptions, normalize_smpl
from .errors import fail

PROG = "equion"
_ARGV: list = []
_THREAD_ENV = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS")


_KO = {
    "usage: ": "사용법: ", "positional arguments": "인자", "options": "옵션",
    "show this help message and exit": "도움말을 보이고 끝낸다",
    "show program's version number and exit": "버전을 보이고 끝낸다",
    "the following arguments are required: %s": "다음 인자가 필요합니다: %s",
    "unrecognized arguments: %s": "알 수 없는 인자: %s",
    "argument %(argument_name)s: %(message)s": "인자 %(argument_name)s: %(message)s",
    "invalid choice: %(value)r (choose from %(choices)s)": "고를 수 없는 값: %(value)r (가능: %(choices)s)",
    "expected one argument": "값이 하나 필요합니다",
    "invalid %(type)s value: %(value)r": "올바르지 않은 %(type)s 값: %(value)r",
    "not allowed with argument %s": "%s 와(과) 함께 쓸 수 없습니다",
}
argparse._ = lambda text: _KO.get(text, text)  # argparse 고정 문구를 한국어로(모듈 안 이름 조회를 바꾼다)


class _Parser(argparse.ArgumentParser):
    """사용법 오류도 입력 오류(3)로 끝낸다(2는 풀이 실패에 쓴다)."""

    def error(self, message):
        from . import errors
        if errors.JSON:                         # --json이면 사용법 오류도 JSON 하나(표준출력)
            errors.fail(f"{self.prog}: {message}", usage=self.format_usage().strip())
            self.exit(EXIT_INPUT)
        self.print_usage(sys.stderr)
        self.exit(EXIT_INPUT, f"{self.prog}: 오류: {message}\n")


def build_parser() -> argparse.ArgumentParser:
    p = _Parser(prog=PROG, description="Equion — 방정식 추정·연립 모델 풀이: 스크립트 실행·검사·정보·새 프로젝트·조립 검사·자료 회차·작업 명령",
                epilog="종료 코드: 0 성공 · 1 스크립트 오류 · 2 풀이 실패(--fail-on) · 3 입력 오류 · 130 중단")
    p.add_argument("--version", action="version",
                   version=f"equion {project_version()}")
    sub = p.add_subparsers(dest="command", metavar="명령", parser_class=_Parser)

    r = sub.add_parser("run", help="스크립트를 실행한다 — .py는 보고서 폴더(out/), Equion 스크립트 .eqs는 실행 기록(work/run/)",
                       description="Python 스크립트(.py)를 실행하거나(스크립트에 넘길 인자는 -- 뒤에), Equion 스크립트(.eqs — 한 줄이 "
                                   "equion 명령 하나)를 프로젝트에서 실행한다. .eqs의 종료 코드: 멈춘 단계의 코드 · expect --stop에 "
                                   "걸리면 2 · --fail-on에 걸리면 2.")
    r.add_argument("script", nargs="?", help="실행할 스크립트(.py · .eqs)")
    r.add_argument("--smpl", metavar="S:E", help="새로 여는 워크파일의 기본 표본(예: 2000Q1:2022Q4, @all)")
    r.add_argument("--set", dest="sets", action="append", default=[], metavar="이름=값",
                   help="스크립트 매개변수(eqn.params)를 덮는다. 여러 번 쓸 수 있다")
    r.add_argument("--params", metavar="FILE.json", help="매개변수 JSON 파일(--set이 그 위에 덮는다)")
    r.add_argument("--out", default="out", metavar="폴더", help="보고서를 둘 폴더(기본: out)")
    r.add_argument("--run-id", metavar="ID", help="보고서 하위 폴더 이름(기본: 날짜-시각_스크립트이름)")
    r.add_argument("--format", default="csv,html", metavar="목록",
                   help="출력 형식 csv·xlsx·json·html 중 쉼표로(기본: csv,html)")
    r.add_argument("--no-report", action="store_true", help="보고서 폴더를 만들지 않는다")
    r.add_argument("--plotlyjs", choices=("copy", "cdn"), default="copy",
                   help="그래프 스크립트: copy(보고서에 넣음, 인터넷 없이 열림·기본) · cdn")
    r.add_argument("--fail-on", choices=("failed", "fallback", "partial", "never"), default="failed",
                   help="이 상태의 기간이 있으면 종료 코드 2(기본: failed)")
    r.add_argument("--threads", type=int, metavar="N", help="BLAS 스레드 수 고정(재현성)")
    g = r.add_mutually_exclusive_group()
    g.add_argument("-q", "--quiet", action="store_true", help="요약 줄과 오류만 보인다")
    g.add_argument("-v", "--verbose", action="store_true", help="엔진 상세 로그까지 보인다")
    r.add_argument("--log", metavar="FILE", help="실행 로그를 이 파일에도 쓴다")
    r.add_argument("-i", "--interactive", action="store_true", help="실행 뒤 스크립트 변수를 가진 Python 대화창으로")
    r.add_argument("--watch", action="store_true", help="스크립트·입력 파일이 바뀌면 다시 실행한다(Ctrl+C로 끝)")
    r.add_argument("--interval", type=float, default=1.0, metavar="초", help="--watch 확인 간격(기본 1초)")
    r.add_argument("--dry-run", action="store_true", help="실행하지 않고 문법·설정만 확인한다")
    r.add_argument("--redact", action="store_true",
                   help="공유용 보고서: 작업 폴더·실행 파일 경로·git 브랜치를 빼고 경로를 줄인다")
    r.add_argument("--from", dest="from_step", metavar="단계", help="(.eqs) 이 단계 번호 또는 ## 제목부터(앞 단계는 건너뛴다)")
    r.add_argument("--replay", metavar="run:이름", help="(.eqs) 실행 기록을 그때 그대로 다시 — 단계마다 같음·다름(다르면 종료 코드 2)")
    r.add_argument("--project", "-p", metavar="폴더", help="(.eqs) 프로젝트 폴더(기본: 스크립트에서 위로 equion.toml을 찾는다)")
    r.add_argument("--json", action="store_true", help="(.eqs) 결과를 JSON으로")
    r.add_argument("--manifest-to", help=argparse.SUPPRESS)

    c = sub.add_parser("check", help="실행 없이 방정식 파일·스크립트를 검사한다")
    c.add_argument("path", help="방정식 파일(.txt) · 스크립트(.py) · Equion 스크립트(.eqs)")
    c.add_argument("--data", metavar="FILE", help="데이터 파일·워크파일 — 변수 존재와 결측 입력까지 검사")
    c.add_argument("--freq", choices=("Q", "M", "A"), help="주기(데이터가 없거나 추론이 안 될 때)")
    c.add_argument("--smpl", metavar="S:E", help="결측 입력을 볼 구간(기본: 데이터 전체)")
    c.add_argument("--json", action="store_true", help="결과를 JSON으로")
    c.add_argument("--strict", action="store_true", help="경고도 실패(종료 코드 3)로 본다")
    c.add_argument("--set", dest="sets", action="append", default=[], metavar="이름=값", help="(.eqs) 매개변수도 검사")
    c.add_argument("--project", "-p", metavar="폴더", help="(.eqs) 프로젝트 폴더(기본: 스크립트에서 위로)")

    i = sub.add_parser("info", help="데이터·워크파일·방정식 파일·보고서 폴더 요약(경로 없으면 실행 환경)")
    i.add_argument("path", nargs="?", help="경로")
    i.add_argument("--freq", choices=("Q", "M", "A"), help="데이터 주기(추론이 안 될 때)")
    i.add_argument("--all", action="store_true", help="시리즈별 마지막 관측까지")
    i.add_argument("--json", action="store_true", help="결과를 JSON으로")

    cv = sub.add_parser("convert", help="옛 저장 형식(레거시 pickle·.wt·.mmw)을 워크파일(.eqw)로")
    cv.add_argument("src", help="원본: 레거시 pickle 파일 · .wt/ 번들 · .mmw/ · 데이터 파일")
    cv.add_argument("dst", help="만들 워크파일 경로(.eqw가 붙는다)")
    cv.add_argument("--allow-pickle", action="store_true",
                    help="레거시 pickle을 연다(열 때 코드가 실행될 수 있음 — 믿을 수 있는 파일만)")
    cv.add_argument("--name", help="워크파일 이름")

    n = sub.add_parser("new", help="새 프로젝트 폴더(예시 데이터·방정식·스크립트)")
    n.add_argument("path", help="만들 폴더")
    n.add_argument("--template", choices=("script", "desk"), default="script",
                   help="script: 스크립트 예시(기본) · desk: 블록·모형 조립 프로젝트(equion.toml)")
    n.add_argument("--bare", action="store_true", help="예시 없이 빈 뼈대만(script)")
    n.add_argument("--force", action="store_true", help="비어 있지 않은 폴더에도 쓴다(같은 이름 파일을 덮음)")

    a = sub.add_parser("assemble", help="프로젝트의 모형을 조립해 검사한다(계산 없이 — 내생·외생·겹친 목표·모르는 변수)")
    a.add_argument("model", nargs="?", help="모형 또는 블록 이름(기본: equion.toml [hs] model)")
    a.add_argument("--project", "-p", default=".", metavar="폴더", help="프로젝트 폴더(기본: 지금 폴더)")
    a.add_argument("--json", action="store_true", help="결과를 JSON으로")

    mo = sub.add_parser("model", help="프로젝트의 모형 정의 — equion.toml의 [model.이름]을 더하거나 고친다")
    msub = mo.add_subparsers(dest="define_command", metavar="동작")
    msub.required = True
    md = msub.add_parser("define", help="모형을 더하거나 고친다(블록·끼울 모형·뺄 식·설명) — 준 것만 바꾼다")
    md.add_argument("name", help="모형 이름(없으면 새로 만든다)")
    md.add_argument("--blocks", metavar="블록들", help="블록 이름들(쉼표로 — 빈 글이면 지운다)")
    md.add_argument("--include", metavar="모형들", help="끼울 모형들(쉼표로)")
    md.add_argument("--exclude", metavar="식들", help="뺄 식들(블록:목표, 쉼표로 — 그 목표는 외생이 된다)")
    md.add_argument("--desc", metavar="글", help="설명")
    bl = sub.add_parser("block", help="프로젝트의 블록 — equion.toml의 [block]에 블록(방정식 파일 하나)을 더하거나 고친다")
    bsub = bl.add_subparsers(dest="define_command", metavar="동작")
    bsub.required = True
    bd = bsub.add_parser("define", help="블록을 더한다 — 파일이 없으면 빈 블록 파일을 함께 만든다")
    bd.add_argument("name", help="블록 이름")
    bd.add_argument("--file", metavar="파일", help="블록 파일(기본 EQUATIONS/<이름>.txt)")
    bd.add_argument("--desc", metavar="글", help="설명")
    for sp in (md, bd):
        sp.add_argument("--project", "-p", default=".", metavar="폴더", help="프로젝트 폴더(기본: 지금 폴더)")
        sp.add_argument("--json", action="store_true", help="결과를 JSON으로")

    vw = sub.add_parser("view", help="프로젝트의 보기(VIEWS/*.toml) — 어느 시리즈를 어떤 모양으로 볼지")
    vsub = vw.add_subparsers(dest="view_command", metavar="동작")
    vsub.required = True
    vl = vsub.add_parser("list", help="저장한 보기 목록")
    vd = vsub.add_parser("define", help="보기를 더하거나 고친다(시리즈·보이기·제목·구간) — 준 것만 바꾼다")
    vd.add_argument("name", help="보기 이름(없으면 새로 만든다)")
    vd.add_argument("--series", metavar="시리즈들", help="시리즈 이름들(쉼표로)")
    vd.add_argument("--show", choices=("level", "qoq", "yoy", "annual", "diff"), help="보이기 — 수준·전기비·전년동기비·연간·기준선 대비")
    vd.add_argument("--title", metavar="글", help="제목")
    vd.add_argument("--range", metavar="S:E", help="구간(상대 기간 가능 — 2015Q1:last)")
    for sp in (vl, vd):
        sp.add_argument("--project", "-p", default=".", metavar="폴더", help="프로젝트 폴더(기본: 지금 폴더)")
        sp.add_argument("--json", action="store_true", help="결과를 JSON으로")

    d = sub.add_parser("ident", help="프로젝트의 항등식을 보이거나(--check) 실측으로 계산해 견준다")
    d.add_argument("part", help="항등식 이름 블록:목표(예: demand:Y)")
    d.add_argument("--check", action="store_true", help="실측으로 좌변·우변을 계산해 견준다")
    d.add_argument("--range", metavar="S:E", help="검사 구간(기본: 자료 전체)")
    d.add_argument("--tol", type=float, default=1e-6, help="허용오차(|차이| ≤ tol·max(1,|좌변|), 기본 1e-6)")
    d.add_argument("--strict", action="store_true", help="어긋나면 실패(종료 코드 3)로 본다")
    d.add_argument("--project", "-p", default=".", metavar="폴더", help="프로젝트 폴더(기본: 지금 폴더)")
    d.add_argument("--json", action="store_true", help="결과를 JSON으로")

    da = sub.add_parser("data", help="프로젝트의 자료 회차 — 목록·원자료 넣기·만들기·바꾸기·차이·영향")
    dsub = da.add_subparsers(dest="data_command", metavar="동작")
    dsub.required = True

    def _common(sp):
        sp.add_argument("--project", "-p", default=".", metavar="폴더", help="프로젝트 폴더(기본: 지금 폴더)")
        sp.add_argument("--json", action="store_true", help="결과를 JSON으로")
        return sp

    _common(dsub.add_parser("list", help="자료 회차 목록(* 지금 회차)"))
    dad = _common(dsub.add_parser("add", help="원자료 파일을 DATA/raw/에 넣는다(받은 그대로 — --source로 출처를 그 파일로)"))
    dad.add_argument("file", help="넣을 파일(csv·xlsx·xls)")
    dad.add_argument("--source", metavar="출처", help="series.toml의 [source.출처]가 이 파일을 읽게(틀이 맞을 때만)")
    dad.add_argument("--as", dest="as_name", metavar="이름", help="DATA/raw/에 둘 이름(기본: 파일 이름)")
    dad.add_argument("--note", metavar="메모", help="출처 메모(옆 파일 *.source.toml에)")
    db = _common(dsub.add_parser("build", help="원자료를 정의대로 읽어 새 자료 회차를 만든다(같은 내용이면 만들지 않음)"))
    db.add_argument("--use", action="store_true", help="만든 회차를 지금 회차로")
    db.add_argument("--inbox", choices=("ask", "auto", "no"), help="먼저 받은 원자료(DATA/raw/inbox/)를 출처와 짝지어 넣는다 — "
                    "ask: 터미널이면 파일마다 묻는다(아니면 auto) · auto: 짝이 하나이고 틀이 맞으면 넣는다")
    _common(dsub.add_parser("inbox", help="받은 원자료(DATA/raw/inbox/) — 파일마다 짝지을 출처와 틀 검사(미리보기)"))

    def _frame(sp):
        sp.add_argument("--sheet", metavar="시트", help="엑셀의 시트(이름 또는 번호 — 기본 첫 시트)")
        sp.add_argument("--header-row", type=int, metavar="줄", help="열 이름이 있는 줄(1부터, 기본 1)")
        sp.add_argument("--unit-row", type=int, metavar="줄", help="단위가 있는 줄(없으면 생략)")
        sp.add_argument("--time-col", metavar="열", help="시점 열(이름·A·B… 또는 번호 — 기본 첫 열)")
        sp.add_argument("--missing", action="append", metavar="표시", help="결측으로 볼 글자(여러 번 — 예: --missing - --missing …)")
        sp.add_argument("--thousands", metavar="글자", help="천 단위 구분 글자(예: ,)")
        sp.add_argument("--freq", metavar="주기", help="원자료의 주기 Q·M·A(기본: 시점에서 읽는다)")
        return sp

    dpv = _frame(_common(dsub.add_parser("preview", help="원자료 파일을 미리 본다 — 읽은 그대로의 줄과 그 틀로 읽어 본 결과(쓰지 않는다)")))
    dpv.add_argument("file", help="원자료 파일(csv·xlsx·xls)")
    dpv.add_argument("--rows", type=int, default=12, metavar="줄", help="읽은 그대로 보일 줄 수(기본 12)")
    dpv.add_argument("--column", metavar="열", help="이 열을 변환대로 만들어 본다(--convert·--seas와 함께)")
    dpv.add_argument("--convert", metavar="방법", help="주기 변환(mean·sum·last… · constant·linear·denton)")
    dpv.add_argument("--seas", metavar="방법", help="계절조정 stl·classical(승법은 stl:multiplicative)")
    ddf = _frame(_common(dsub.add_parser("define", help="자료 정의 쓰기 — series.toml에 출처(불러오기 틀)와 시리즈를 더하거나 고친다")))
    ddf.add_argument("source", help="출처 이름([source.이름] — 없으면 새로 만든다)")
    ddf.add_argument("--file", metavar="파일", help="원자료 파일(프로젝트 안 — 보통 DATA/raw/). 새 출처에는 꼭")
    ddf.add_argument("--desc", metavar="글", help="출처 설명")
    ddf.add_argument("--series", action="append", default=[], metavar="이름=열", help="시리즈를 그 열로(여러 번)")
    ddf.add_argument("--set", dest="sets", action="append", default=[], metavar="이름.키=값",
                     help="시리즈의 키(unit·desc·convert·denton·seas·scale·fill — 예: --set CN.unit=조원 --set CN.seas=stl:multiplicative)")
    ddf.add_argument("--replace", action="store_true", help="이미 있는 시리즈를 다른 열로 바꿔도 된다")
    du = _common(dsub.add_parser("use", help="지금 자료 회차를 바꾼다(equion.toml [data] vintage)"))
    du.add_argument("vintage", help="회차(equion data list)")
    for nm, hl in (("diff", "두 회차의 차이 — 새·없어진 시리즈, 새 기간·개정"),
                   ("impact", "회차를 바꾸면 영향받는 식·모형(다시 계산하지 않음)")):
        sp = _common(dsub.add_parser(nm, help=hl))
        sp.add_argument("a", nargs="?", help="앞 회차(기본: 지금 회차)")
        sp.add_argument("b", nargs="?", help="뒤 회차(기본: 가장 새 회차)")

    from .workcmds import add_parsers
    add_parsers(sub)
    from .ancmds import add_parsers as add_an_parsers
    add_an_parsers(sub)
    from .scriptcmds import add_parsers as add_script_parsers
    add_script_parsers(sub)

    gd = sub.add_parser("guide", help="Claude(AI)용 모형 작업 안내 · Claude Code 스킬 초안",
                        description="Equion 프로젝트에서 일하는 Claude가 먼저 읽는 안내(규칙·프로젝트 지도·명령·분석·판단 기준·보고 꼴)와 "
                                    "Claude Code 스킬 초안. 스킬은 --install로 시킬 때만 쓴다.")
    gd.add_argument("topic", nargs="?", choices=("claude", "skill"), default="claude",
                    help="claude: 모형 작업 안내(기본) · skill: 스킬 초안(SKILL.md)")
    gd.add_argument("--path", action="store_true", help="파일 경로만 — Claude에게 '이 파일을 읽어'")
    gd.add_argument("--install", choices=("user", "project"),
                    help="(skill) 스킬 폴더에 쓴다 — user: ~/.claude/skills/equion/ · project: <프로젝트>/.claude/skills/equion/")
    gd.add_argument("--project", "-p", default=".", metavar="폴더", help="(--install project) 프로젝트 폴더")
    gd.add_argument("--force", action="store_true", help="(--install) 다른 내용의 스킬이 있어도 덮는다")
    return p


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------
def _parse_sets(items, params_file):
    params = {}
    if params_file:
        with open(params_file, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("--params 파일은 JSON 객체({이름: 값})여야 합니다")
        params.update(data)
    for it in items:
        if "=" not in it:
            raise ValueError(f"--set 형식은 이름=값 입니다: {it!r}")
        k, v = it.split("=", 1)
        k = k.strip()
        if not k.isidentifier():
            raise ValueError(f"--set 이름이 올바르지 않습니다: {k!r}")
        params[k] = v
    return params


def _check_run_id(rid: str):
    """--run-id는 보고서 폴더(--out) 안의 폴더 이름 하나 — 경로 구분자·'..'·절대 경로는 받지 않는다."""
    if (not rid.strip() or rid.strip() in (".", "..") or any(ch in rid for ch in '/\\:*?"<>|')
            or os.path.isabs(rid)):
        raise ValueError(f"--run-id는 폴더 이름 하나여야 합니다(경로·'..'·빈 값·특수문자 불가): {rid!r}")


def _formats(text: str):
    from .report import ALL_FORMATS
    fs = tuple(dict.fromkeys(f.strip().lower() for f in text.split(",") if f.strip()))
    if not fs:
        raise ValueError(f"--format이 비었습니다 (가능: {', '.join(ALL_FORMATS)})")
    bad = [f for f in fs if f not in ALL_FORMATS]
    if bad:
        raise ValueError(f"알 수 없는 형식: {', '.join(bad)} (가능: {', '.join(ALL_FORMATS)})")
    return fs


def _summary_line(res, report_path=None) -> str:
    c = res.solve_counts()
    parts = [f"[equion] {STATUS_KO.get(res.status, res.status)} · {res.elapsed:.1f}초"]
    if res.record.solves:
        parts.append(f"풀이 {len(res.record.solves)}회(정상 {c['ok']} · 일부식 제외 {c['partial']} · "
                     f"실패대체 {c['fallback']} · 실패 {c['failed']})")
    if res.unused_params():
        parts.append(f"쓰이지 않은 --set: {', '.join(res.unused_params())}")
    if report_path:
        parts.append(f"보고서 {report_path}")
    parts.append(f"종료 코드 {res.exit_code}")
    return " · ".join(parts)


def _reexec_with_threads(n: int, argv) -> int:
    env = dict(os.environ)
    for k in _THREAD_ENV:
        env[k] = str(n)
    env["EQUION_THREADS"] = str(n)
    return subprocess.call([sys.executable, "-m", "equion", *argv], env=env)


def _strip_watch_args(argv):
    out, skip = [], False
    for a in argv:
        if skip:
            skip = False
            continue
        if a == "--watch":
            continue
        if a == "--interval":
            skip = True
            continue
        if a.startswith("--interval="):
            continue
        out.append(a)
    return out


def _with_manifest(argv, path):
    """하위 실행에 --manifest-to를 붙인다(스크립트 인자 구분자 -- 앞에)."""
    if "--" in argv:
        k = argv.index("--")
        return [*argv[:k], "--manifest-to", path, *argv[k:]]
    return [*argv, "--manifest-to", path]


def _rel(path):
    try:
        return os.path.relpath(path)
    except ValueError:  # Windows: 다른 드라이브
        return path


def _mtimes(paths):
    out = {}
    for p in paths:
        try:
            if os.path.isdir(p):
                out[p] = max([os.path.getmtime(os.path.join(r, f)) for r, _, fs in os.walk(p) for f in fs] or [0])
            else:
                out[p] = os.path.getmtime(p)
        except OSError:
            out[p] = None
    return out


def watch(argv, script: str, interval: float = 1.0, max_runs: int = None) -> int:
    """스크립트를 하위 프로세스로 실행하고, 스크립트·읽은 입력 파일이 바뀌면 다시 실행한다."""
    child = _strip_watch_args(argv)
    code, runs = EXIT_OK, 0
    try:
        while True:
            fd, mf = tempfile.mkstemp(prefix="equion-", suffix=".json")
            os.close(fd)
            try:
                code = subprocess.call([sys.executable, "-m", "equion", *_with_manifest(child, mf)])
                watched = [os.path.abspath(script)]
                try:
                    with open(mf, encoding="utf-8") as f:
                        watched += [os.path.abspath(d["path"]) for d in json.load(f).get("inputs", [])]
                except (OSError, ValueError):
                    pass
            finally:
                os.unlink(mf)
            runs += 1
            if max_runs is not None and runs >= max_runs:
                return code
            watched = list(dict.fromkeys(watched))
            print(f"[watch] 파일 {len(watched)}개를 지켜보는 중 — 바뀌면 다시 실행합니다 (Ctrl+C로 끝)", flush=True)
            before = _mtimes(watched)
            while True:
                time.sleep(interval)
                now = _mtimes(watched)
                changed = [p for p in watched if now.get(p) != before.get(p)]
                if changed:
                    rel = ", ".join(_rel(p) for p in changed[:3])
                    print(f"\n[watch] {datetime.now():%H:%M:%S} 바뀜: {rel} → 다시 실행", flush=True)
                    break
    except KeyboardInterrupt:
        print("\n[watch] 끝", flush=True)
        return code


def cmd_run(args, argv, script_args) -> int:
    from . import report, runner

    if args.threads is not None:
        if args.threads < 1:
            fail(f"--threads는 1 이상이어야 합니다")
            return EXIT_INPUT
        if os.environ.get("EQUION_THREADS") != str(args.threads):
            return _reexec_with_threads(args.threads, argv)
    if args.replay or (args.script and args.script.lower().endswith(".eqs")):
        from .scriptcmds import cmd_run_eqs
        return cmd_run_eqs(args, argv, script_args)
    if not args.script:
        fail(f"실행할 스크립트가 필요합니다(.py · .eqs) — 실행 기록을 다시 하려면 --replay run:이름")
        return EXIT_INPUT
    eqs_only = [f for f, v in (("--from", args.from_step), ("-p", args.project), ("--json", args.json)) if v]
    if eqs_only:
        fail(f"{', '.join(eqs_only)}는 Equion 스크립트(.eqs)에서만 씁니다")
        return EXIT_INPUT
    if not os.path.isfile(args.script):
        fail(f"스크립트가 없습니다: {args.script}")
        return EXIT_INPUT
    if not args.script.lower().endswith(".py"):
        fail(f"스크립트는 .py 또는 .eqs 파일이어야 합니다: {args.script}")
        return EXIT_INPUT
    try:
        params = _parse_sets(args.sets, args.params)
        formats = _formats(args.format)
        smpl = normalize_smpl(args.smpl)
        if args.run_id is not None:
            _check_run_id(args.run_id)
        if args.interval is not None and not args.interval > 0:
            raise ValueError(f"--interval은 0보다 커야 합니다(받은 값 {args.interval})")
    except (OSError, ValueError) as e:
        fail(f"{e}")
        return EXIT_INPUT
    if args.watch:
        if args.interactive:
            fail(f"--watch와 -i는 함께 쓸 수 없습니다")
            return EXIT_INPUT
        return watch(argv, args.script, args.interval)

    if args.dry_run:
        from .check import check_script
        rep = check_script(args.script)
        print(rep.text())
        print(f"매개변수(--set): {params or '(없음)'} · 기본 표본: {smpl or '(스크립트가 정함)'} · "
              f"보고서: {'만들지 않음' if args.no_report else os.path.join(args.out, args.run_id or '<날짜-시각_이름>')}"
              f" · 형식: {','.join(formats)}")
        return EXIT_OK if rep.ok else EXIT_SCRIPT

    verbosity = 0 if args.quiet else (2 if args.verbose else 1)
    opts = RunOptions(script=args.script, params=params, smpl=smpl, out=args.out, run_id=args.run_id,
                      formats=formats, report=not args.no_report, plotlyjs=args.plotlyjs, fail_on=args.fail_on,
                      verbosity=verbosity, log=args.log, script_args=list(script_args), argv=[PROG, *argv],
                      redact=args.redact)
    res = runner.run_script(opts)

    report_path = None
    if opts.report:
        stem = os.path.splitext(os.path.basename(args.script))[0]
        run_id = args.run_id or f"{res.started:%Y%m%d-%H%M%S}_{stem}"
        try:
            d = report.prepare_dir(args.out, run_id, explicit=bool(args.run_id))
            res.report_dir = d
            report.write_report(res, d)
            with open(os.path.join(args.out, "LATEST"), "w", encoding="utf-8") as f:
                f.write(os.path.basename(d) + "\n")
            report_path = os.path.join(d, "report.html" if "html" in formats else "manifest.json")
        except Exception as e:  # noqa: BLE001 — 보고서 실패가 스크립트 결과를 가리지 않게
            print(f"{PROG}: 보고서를 쓰지 못했습니다: {type(e).__name__}: {e}", file=sys.stderr)
            if res.exit_code == EXIT_OK:
                res.exit_code = EXIT_SCRIPT
    if args.manifest_to:
        report._write_json(args.manifest_to, report.safe_manifest(res))
    if args.log:
        os.makedirs(os.path.dirname(os.path.abspath(args.log)), exist_ok=True)   # logs/처럼 아직 없는 폴더도
        with open(args.log, "w", encoding="utf-8") as f:
            f.write(report.scrub(res.log, report.collect_secrets(res)))
    print(_summary_line(res, report_path), file=sys.stderr if res.exit_code else sys.stdout)

    if args.interactive:
        import code
        ns = res.namespace
        banner = (f"Equion 대화창 — 스크립트 {args.script}의 변수가 들어 있습니다 "
                  f"(종료: exit() 또는 Ctrl+D)")
        try:
            code.interact(banner=banner, local=ns, exitmsg="")
        except SystemExit:
            pass
    return res.exit_code


# ---------------------------------------------------------------------------
# check / info / new
# ---------------------------------------------------------------------------
def cmd_check(args) -> int:
    if args.path.lower().endswith(".eqs"):
        from .scriptcmds import cmd_check_eqs
        return cmd_check_eqs(args)
    from .check import check_path
    try:
        rep = check_path(args.path, data=args.data, freq=args.freq, smpl=args.smpl)
    except Exception as e:  # noqa: BLE001 — 파일 없음·데이터 읽기 실패
        fail(f"{e}")
        return EXIT_INPUT
    print(json.dumps(rep.to_dict(), ensure_ascii=False, indent=2) if args.json else rep.text())
    failed = not rep.ok or (args.strict and rep.issues)
    return EXIT_INPUT if failed else EXIT_OK


def cmd_info(args) -> int:
    from .info import describe, to_text
    try:
        info = describe(args.path, freq=args.freq, show_all=args.all)
    except Exception as e:  # noqa: BLE001
        fail(f"{e}")
        return EXIT_INPUT
    print(json.dumps(info, ensure_ascii=False, indent=2, default=str) if args.json else to_text(info))
    return EXIT_OK


def cmd_convert(args) -> int:
    from .convert import convert
    try:
        out = convert(args.src, args.dst, allow_pickle=args.allow_pickle, name=args.name)
    except Exception as e:  # noqa: BLE001 — 파일 없음·pickle 거부·형식 오류
        fail(f"{e}")
        return EXIT_INPUT
    print(f"변환 완료: {args.src} → {out}")
    return EXIT_OK


def cmd_guide(args) -> int:
    from .. import help as guide
    if args.install:
        if args.topic != "skill":
            fail(f"--install은 스킬에만: equion guide skill --install user")
            return EXIT_INPUT
        try:
            dst = guide.install_skill(args.install, project=args.project, force=args.force)
        except (FileExistsError, ValueError, OSError) as e:
            fail(f"{e}")
            return EXIT_INPUT
        print(f"[guide skill] {dst} — Claude Code를 다시 열면 스킬 equion이 보입니다")
        return EXIT_OK
    if args.path:
        print(guide.SKILL if args.topic == "skill" else guide.GUIDE)
        return EXIT_OK
    print(guide.skill_text() if args.topic == "skill" else guide.guide_text())
    return EXIT_OK


def cmd_new(args) -> int:
    from .new import create_project
    prj = None
    try:
        if args.template == "desk":
            if args.bare:
                raise ValueError("--bare는 --template script에서만 씁니다")
            from ..projects import Project, ProjectError
            from ..workfile.output import verbose
            old = verbose()
            verbose(0)
            try:
                prj = Project.create(args.path, force=args.force)
            except ProjectError as e:
                raise ValueError(str(e)) from None
            finally:
                verbose(old)
            files = prj.created_files
        else:
            files = create_project(args.path, bare=args.bare, force=args.force)
    except (OSError, FileExistsError, ValueError) as e:
        fail(f"{e}")
        return EXIT_INPUT
    print(f"새 프로젝트 {args.path}:")
    for f in files:
        print(f"  {f}")
    if prj is not None:
        print(f"자료 회차 {prj.vintage}를 만들어 지금 회차로 정했습니다(work/data/{prj.vintage}/)")
        print(f"\n다음:\n  cd {args.path}\n  equion assemble main")
    elif not args.bare:
        print(f"\n다음:\n  cd {args.path}\n  equion run scripts/main.py")
    return EXIT_OK


# ---------------------------------------------------------------------------
# 프로젝트: assemble / ident
# ---------------------------------------------------------------------------
def _open_project(path):
    from ..projects import Project
    return Project.open(path)


def _summary_quiet(fn):
    """명령의 결과 글만 보이게 — 실행하는 동안 요약 줄(자료 열기 등)을 감추고 끝나면 되돌린다."""
    def wrapped(args):
        from ..workfile.output import verbose
        old = verbose()
        verbose(0)
        try:
            return fn(args)
        finally:
            verbose(old)
    return wrapped


@_summary_quiet
def cmd_assemble(args) -> int:
    from ..projects import ProjectError
    try:
        p = _open_project(args.project)
        rep = p.assemble(args.model)
    except (ProjectError, KeyError) as e:
        fail(f"{e.args[0] if isinstance(e, KeyError) else e}")
        return EXIT_INPUT
    print(json.dumps(rep.to_dict(), ensure_ascii=False, indent=2) if args.json else rep.text())
    return EXIT_OK if rep.ok else EXIT_INPUT


@_summary_quiet
def cmd_view(args) -> int:
    """equion view list · equion view define — 보기(VIEWS/*.toml)."""
    from ..projects import ProjectError
    from ..work.store import detect_who
    try:
        p = _open_project(args.project)
        if args.view_command == "list":
            rows = p.views()
            out = rows if args.json else (f"[view list] {p.name} — 보기 {len(rows)}" + "".join(
                f"\n  {v['name']:<14} {v['show']:<7} {', '.join(v['series'])}" + (f"  — {v['title']}" if v["title"] else "") for v in rows))
        else:
            res = p.view_define(args.name, series=args.series, show=args.show, title=args.title, range=args.range,
                                who=detect_who("terminal"), command=_cmdline(_ARGV))
            out = res.to_dict() if args.json else res.text()
    except (ProjectError, KeyError, ValueError) as e:
        fail(f"{e.args[0] if isinstance(e, KeyError) else e}")
        return EXIT_INPUT
    print(json.dumps(out, ensure_ascii=False, indent=2) if args.json else out)
    return EXIT_OK


def cmd_define(args) -> int:
    """equion model define · equion block define — 설정(equion.toml)의 모형·블록을 쓴다."""
    from ..projects import ProjectError
    from ..work.store import detect_who
    try:
        p = _open_project(args.project)
        who, cmdline = detect_who("terminal"), _cmdline(_ARGV)
        if args.command == "model":
            res = p.model_define(args.name, blocks=args.blocks, include=args.include, exclude=args.exclude, desc=args.desc,
                                 who=who, command=cmdline)
        else:
            res = p.block_define(args.name, file=args.file, desc=args.desc, who=who, command=cmdline)
    except (ProjectError, KeyError, ValueError) as e:
        fail(f"{e.args[0] if isinstance(e, KeyError) else e}")
        return EXIT_INPUT
    print(json.dumps(res.to_dict(), ensure_ascii=False, indent=2) if args.json else res.text())
    return EXIT_OK


@_summary_quiet
def cmd_ident(args) -> int:
    from ..projects import ProjectError
    try:
        p = _open_project(args.project)
        part = p.part(args.part)
        if part.kind != "identity":
            raise ValueError(f"{part.id} — 항등식이 아니라 추정식입니다: {part.text}")
        if not args.check:
            info = {"part": part.id, "where": part.where, "text": part.text, "desc": part.desc,
                    "used_by": p.used_by(part.id)}
            if args.json:
                print(json.dumps(info, ensure_ascii=False, indent=2))
            else:
                print(f"[ident {part.id}] {part.text}   ({part.where})"
                      + (f"\n  설명   {part.desc}" if part.desc else "")
                      + f"\n  쓰는 곳  {', '.join(info['used_by']) or '없음'}"
                      + "\n  실측으로 검사: --check")
            return EXIT_OK
        start = end = None
        if args.range:
            if ":" not in args.range:
                raise ValueError(f"--range는 시작:끝 꼴입니다: {args.range!r}")
            start, end = [t.strip() or None for t in args.range.split(":", 1)]
        res = p.ident(part.id, start=start, end=end, tol=args.tol)
    except (ProjectError, KeyError, ValueError) as e:
        fail(f"{e.args[0] if isinstance(e, KeyError) else e}")
        return EXIT_INPUT
    print(json.dumps(res.to_dict(), ensure_ascii=False, indent=2) if args.json else res.text())
    return EXIT_INPUT if (args.strict and not res.ok) else EXIT_OK


def _data_list_text(name, rows) -> str:
    if not rows:
        return f"[data list] {name}: 자료 회차 없음 — equion data build"
    L = [f"[data list] {name}: 자료 회차 {len(rows)}"]
    for r in rows:
        span = "~".join(r["span"]) if r.get("span") else ""
        L.append(f"  {'*' if r['current'] else ' '} {r['id']:<12} {r.get('created') or '':<20} {span:<16} "
                 f"시리즈 {r.get('n_series')}")
    return "\n".join(L)


@_summary_quiet
def cmd_data(args) -> int:
    from ..projects import ProjectError
    try:
        p = _open_project(args.project)
        act = args.data_command
        code = EXIT_OK
        from ..work.store import detect_who
        who, cmdline = detect_who("terminal"), _cmdline(_ARGV)
        if act == "list":
            rows = p.data_list()
            out = rows if args.json else _data_list_text(p.name, rows)
        elif act == "add":
            res = p.data_add(args.file, source=args.source, as_name=args.as_name, note=args.note, who=who,
                             command=cmdline)
            out = res.to_dict() if args.json else res.text()
            code = EXIT_INPUT if res.problems else EXIT_OK
        elif act == "build":
            tty = args.inbox == "ask" and _interactive()
            res = p.data_build(use=args.use, inbox=args.inbox, ask=_ask_inbox if tty else None, who=who, command=cmdline)
            d = res.to_dict()
            d["current"] = p.vintage
            note = ("\n  (터미널이 아니라 묻지 않았습니다 — 짝이 하나이고 틀이 맞는 파일만 넣음)"
                    if args.inbox == "ask" and not tty and res.inbox else "")
            out = d if args.json else res.text() + note + (f"\n  지금 회차 {p.vintage}" if args.use else
                                                           ("" if res.id == p.vintage else
                                                            f"\n  다음   equion data use {res.id}"))
        elif act == "inbox":
            items = p.data_inbox()
            out = [x.to_dict() for x in items] if args.json else (
                f"[data inbox] 받은 원자료 {len(items)} — DATA/raw/inbox/" + "".join(f"\n  {x.text()}" for x in items)
                + ("\n  넣기   스크립트의 자료 단계(예: equion run FLOWS/monthly.eqs) — 따로 넣으려면 equion data build --inbox ask --use"
                   if items else ""))
            code = EXIT_OK if all(x.ok for x in items) else EXIT_INPUT
        elif act == "preview":
            frame = dict(sheet=args.sheet, header_row=args.header_row, unit_row=args.unit_row, time_col=args.time_col,
                         missing=args.missing, thousands=args.thousands, freq=args.freq)
            one = ({"column": args.column, **({"convert": args.convert} if args.convert else {}),
                    **({"seas": args.seas} if args.seas else {})} if args.column else None)
            res = p.data_preview(args.file, rows=args.rows, series=one, **frame)
            out = res.to_dict() if args.json else res.text()
            code = EXIT_OK if res.ok else EXIT_INPUT
        elif act == "define":
            series = {}
            for item in args.series:
                name, eq, col = item.partition("=")
                if not eq or not name.strip() or not col.strip():
                    raise ProjectError(f"--series {item!r} — 이름=열 꼴")
                series[name.strip()] = {"column": col.strip()}
            for item in args.sets:
                left, eq, value = item.partition("=")
                name, dot, key = left.partition(".")
                if not eq or not dot or name.strip() not in series:
                    raise ProjectError(f"--set {item!r} — 이름.키=값 꼴이고, 이름은 --series로 준 시리즈여야 합니다")
                series[name.strip()][key.strip()] = value
            res = p.data_define(args.source, file=args.file, sheet=args.sheet, header_row=args.header_row, unit_row=args.unit_row,
                                time_col=args.time_col, missing=args.missing, thousands=args.thousands, freq=args.freq,
                                desc=args.desc, series=series or None, replace=args.replace, who=who, command=cmdline)
            out = res.to_dict() if args.json else res.text()
        elif act == "use":
            old = p.data_use(args.vintage, who=who, command=cmdline)
            out = ({"vintage": p.vintage, "previous": old} if args.json else
                   f"[data use] 지금 자료 회차 {p.vintage}" + (f" (전: {old})" if old and old != p.vintage else ""))
        elif act == "diff":
            res = p.data_diff(args.a, args.b)
            out = res.to_dict() if args.json else res.text()
        else:  # impact
            res = p.data_impact(args.a, args.b)
            out = res.to_dict() if args.json else res.text()
    except (ProjectError, KeyError, ValueError) as e:
        fail(f"{e.args[0] if isinstance(e, KeyError) else e}")
        return EXIT_INPUT
    print(json.dumps(out, ensure_ascii=False, indent=2) if args.json else out)
    return code


def _interactive() -> bool:
    """사람에게 물을 수 있나 — 표준입력이 콘솔(터미널)일 때만. Windows의 NUL·파이프(자동화·Claude의 터미널)·재연(EQUION_NO_ASK)은 아니다."""
    if os.environ.get("EQUION_NO_ASK") == "1" or os.environ.get("CI"):
        return False
    s = sys.__stdin__
    try:
        if s is None or not s.isatty():
            return False
        if os.name == "nt":                        # NUL도 isatty()가 참 — 콘솔인지 콘솔 모드로 본다
            import ctypes
            import msvcrt
            mode = ctypes.c_uint32()
            return bool(ctypes.windll.kernel32.GetConsoleMode(msvcrt.get_osfhandle(s.fileno()), ctypes.byref(mode)))
        return True
    except (OSError, ValueError, AttributeError):
        return False


def _ask_inbox(item) -> bool:
    """받은 파일 하나를 넣을지 터미널에서 묻는다(출력이 갈무리되어도 터미널로)."""
    err, inp = sys.__stderr__, sys.__stdin__
    err.write(f"[data build] {item.text()} — 넣을까요? [Y/n] ")
    err.flush()
    ans = (inp.readline() or "").strip().lower()
    return ans in ("", "y", "yes", "예", "네", "ㅇ")


def _cmdline(argv) -> str:
    """기록에 적을 명령 그대로(equion …)."""
    import shlex
    return "equion " + shlex.join(argv)


def _safe_streams():
    """표준출력·오류가 UTF-8이 아니면(예: Windows 파이프의 cp949·cp1252) 인코딩은 그대로 두고, 그 인코딩에 없는
    문자(cp949의 '—', cp1252의 한글 등)만 \\uXXXX로 쓴다 — 출력 때문에 실행이 멈추지 않게. Windows 콘솔·UTF-8은 그대로."""
    import codecs
    for stream in (sys.stdout, sys.stderr):
        try:
            if codecs.lookup(stream.encoding or "ascii").name != "utf-8":
                stream.reconfigure(errors="backslashreplace")
        except (AttributeError, LookupError, ValueError):  # 바꿀 수 없는 스트림(테스트용 StringIO 등)
            pass


def main(argv=None) -> int:
    """명령줄 진입점 — 종료 코드를 돌려준다. `--json`이면 오류도 JSON 하나(equion.cli.errors)."""
    from . import errors
    argv = list(sys.argv[1:] if argv is None else argv)
    old = errors.JSON
    errors.JSON = "--json" in (argv[:argv.index("--")] if "--" in argv else argv)
    try:
        return _main(argv)
    except KeyboardInterrupt:
        return errors.fail("중단했습니다(Ctrl+C)", EXIT_INTERRUPT) if errors.JSON else EXIT_INTERRUPT
    except Exception as e:  # noqa: BLE001 — 예상 못 한 오류: --json이면 JSON으로, 아니면 트레이스백 그대로
        if not errors.JSON:
            raise
        return errors.internal(e)
    finally:
        errors.JSON = old


def _main(argv) -> int:
    _safe_streams()
    script_args = []
    if "--" in argv:
        k = argv.index("--")
        argv, script_args = argv[:k], argv[k + 1:]
    global _ARGV
    _ARGV = list(argv)
    parser = build_parser()
    if not argv:
        parser.print_help()
        return EXIT_OK
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else EXIT_INPUT
    if args.command == "run":
        return cmd_run(args, argv + (["--", *script_args] if script_args else []), script_args)
    if script_args:
        fail(f"'--' 뒤 인자는 run에서만 쓸 수 있습니다")
        return EXIT_INPUT
    try:
        if args.command == "check":
            return cmd_check(args)
        if args.command == "info":
            return cmd_info(args)
        if args.command == "new":
            return cmd_new(args)
        if args.command == "guide":
            return cmd_guide(args)
        if args.command == "convert":
            return cmd_convert(args)
        if args.command == "assemble":
            return cmd_assemble(args)
        if args.command == "ident":
            return cmd_ident(args)
        if args.command in ("model", "block"):
            return cmd_define(args)
        if args.command == "view":
            return cmd_view(args)
        if args.command == "data":
            return cmd_data(args)
        from .workcmds import COMMANDS, dispatch
        if args.command in COMMANDS:
            return dispatch(args, _cmdline(argv))
        from . import ancmds
        if args.command in ancmds.COMMANDS:
            return ancmds.dispatch(args, _cmdline(argv))
        from . import scriptcmds
        if args.command in scriptcmds.COMMANDS:
            return scriptcmds.dispatch(args, _cmdline(argv))
    except KeyboardInterrupt:
        return EXIT_INTERRUPT
    parser.print_help()
    return EXIT_OK
