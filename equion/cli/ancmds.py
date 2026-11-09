#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""분석·노트·보고서 명령(D37, E4) — 옵션과 도움말은 등록부(`equion.registry`)에서 나온다.

    equion an list [--for 종류]                      equion an <분석> --help
    equion an <분석> <대상> [옵션] [--smpl S:E] [--as 이름] [--note 노트]
    equion an keep an:이름 [--as 이름] [--replace]     (만드는 분석 → 정의 · 부품을 내는 분석 → 식 후보)
    equion note run 노트 [--block n] [--stale] [--force] · equion note check 노트…
    equion report new 이름 [--title] [--from 보고서] · add 보고서 기록[#표] [모양] · check 보고서 · update 보고서 [--region n] [--to 기록]
"""

import json
import sys

from .. import registry as reg
from .runner import EXIT_INPUT, EXIT_OK, EXIT_SCRIPT
from .errors import fail

PROG = "equion"
COMMANDS = ("an", "note", "report")


def _common(sp):
    sp.add_argument("--project", "-p", default=".", metavar="폴더", help="프로젝트 폴더(기본: 지금 폴더)")
    sp.add_argument("--json", action="store_true", help="결과를 JSON으로")
    return sp


def _esc(text: str) -> str:
    """argparse 도움말의 %를 글자 그대로(등록부의 글은 서식이 아니다)."""
    return str(text).replace("%", "%%")


def _add_option(sp, o: reg.Opt):
    flag = "--" + o.name.replace("_", "-")
    if o.type == "bool":
        if o.default:
            sp.add_argument(f"--no-{o.name.replace('_', '-')}", dest=o.name, action="store_false", help=_esc(f"{o.help}을(를) 하지 않음"))
        else:
            sp.add_argument(flag, dest=o.name, action="store_true", help=_esc(o.help))
        return
    kw = {"dest": o.name, "default": None, "help": _esc(o.help + (f" (기본 {o.default})" if o.default is not None else ""))}
    if o.type == "int":
        kw["type"] = int
    elif o.type == "float":
        kw["type"] = float
    elif o.type == "choice":
        kw["choices"] = list(o.choices)
    if o.metavar:
        kw["metavar"] = o.metavar
    sp.add_argument(flag, **kw)


def add_parsers(sub):
    a = sub.add_parser("an", help="분석 — 등록부의 분석 하나 = 기록 하나(an:) · 목록·남기기")
    asub = a.add_subparsers(dest="an_command", metavar="분석")
    asub.required = True
    al = _common(asub.add_parser("list", help="분석 목록 — 이름·대상·만드는 것"))
    al.add_argument("--for", dest="for_kind", choices=list(reg.TARGET_KO), help="이 대상 종류를 받는 분석만")
    ak = _common(asub.add_parser("keep", help="남기기 — 만드는 분석은 정의로, 부품을 내는 분석은 식 후보로"))
    ak.add_argument("record", metavar="an:이름")
    ak.add_argument("--as", dest="as_name", metavar="이름", help="새 시리즈·파생·후보 기록의 이름")
    ak.add_argument("--replace", action="store_true", help="(계절조정) 새 시리즈 대신 그 시리즈의 정의를 바꾼다")
    for x in reg.analyses():
        desc = f"{x.label}: {x.help}. 결과: {x.results}" + (f". 만드는 것: {reg.MAKES_KO[x.makes]}" if x.makes else "")
        sp = _common(asub.add_parser(x.name, help=_esc(f"{x.label} — {x.help}"), description=desc,
                                     epilog=f"예: {x.example}" if x.example else None))
        sp.add_argument("target", metavar="대상", help=" · ".join(reg.TARGET_KO[t] for t in x.targets))
        for o in x.options:
            _add_option(sp, o)
        sp.add_argument("--smpl", metavar="S:E", help="표본(상대 기간 가능 — 1990Q1:last)")
        sp.add_argument("--as", dest="as_name", metavar="이름", help=f"기록 이름(기본 {x.name}_0001 …)")
        sp.add_argument("--note", metavar="노트", help="그 노트 끝에 명령 블록과 결과 구역을 더한다")

    n = sub.add_parser("note", help="노트 — ```equion 블록을 실행해 결과 구역을 채운다 · 검사")
    nsub = n.add_subparsers(dest="note_command", metavar="동작")
    nsub.required = True
    nr = _common(nsub.add_parser("run", help="노트의 블록을 실행(블록마다 새 기록) — 손으로 고친 구역은 --force일 때만 덮는다"))
    nr.add_argument("note", metavar="노트")
    nr.add_argument("--block", type=int, metavar="n", help="그 블록만(Python 블록은 이것으로만 돈다)")
    nr.add_argument("--stale", action="store_true", help="낡았거나 아직 실행 안 한 블록만")
    nr.add_argument("--force", action="store_true", help="손으로 고친 결과 구역도 덮는다")
    nc = _common(nsub.add_parser("check", help="실행하지 않고 — 낡은 구역·없는 기록·손으로 고친 구역·허용 안 된 명령"))
    nc.add_argument("notes", nargs="+", metavar="노트")

    r = sub.add_parser("report", help="보고서 — 결과만 보내기(명령 블록 없이) · 검사 · 새 기록으로 바꾸기")
    rsub = r.add_subparsers(dest="report_command", metavar="동작")
    rsub.required = True
    rn = _common(rsub.add_parser("new", help="새 보고서(틀) — --from이면 지난 보고서를 복사하고 바꿔 낄 기록을 제안"))
    rn.add_argument("name", metavar="이름", help="보고서 이름(reports/이름.md)")
    rn.add_argument("--title", help="제목")
    rn.add_argument("--from", dest="from_report", metavar="보고서", help="이 보고서를 복사")
    rn.add_argument("--exist-ok", action="store_true", help="이미 있으면 그대로 둔다(스크립트를 같은 회차로 다시 돌릴 때)")
    ra = _common(rsub.add_parser("add", help="보고서로 보내기 — 기록의 표(와 차트)를 고른 모양으로"))
    ra.add_argument("report", metavar="보고서")
    ra.add_argument("record", metavar="기록[#표]", help="sim:… · hs:… · est:… · an:…#2(분석의 표 번호)")
    ra.add_argument("--rows", metavar="A,B", help="행(시리즈·변수) — 쉼표로")
    ra.add_argument("--show", choices=("level", "qoq", "yoy", "diff"), default="level", help="보이기(전망 — 수준·전기비·전년동기비·기준선 대비)")
    ra.add_argument("--annual", action="store_true", help="연간(전망)")
    ra.add_argument("--digits", type=int, metavar="n", help="소수점 자리(기본: 전망 1 · 그 밖 3)")
    ra.add_argument("--title", help="표 제목(번호는 저절로)")
    ra.add_argument("--chart", action="store_true", help="차트도(자료는 보고서 옆 _data/로 복사)")
    ra.add_argument("--under", metavar="제목", help='이 제목 아래 끝에(예: "## 전망") — 없으면 맨 끝')
    ra.add_argument("--key", metavar="이름", help="구역 이름 — 같은 이름의 구역이 있으면 그 자리에서 이 기록으로 바꾼다(스크립트)")
    ra.add_argument("--force", action="store_true", help="(--key) 손으로 고친 구역도 덮는다")
    rc = _common(rsub.add_parser("check", help="구역마다 — 없는 기록·더 새 기록·낡음·손으로 고침"))
    rc.add_argument("report", metavar="보고서")
    ru = _common(rsub.add_parser("update", help="새 기록으로 바꾸기 — 같은 모양으로 다시 만들어 차이를 보이고 적용"))
    ru.add_argument("report", metavar="보고서")
    ru.add_argument("--region", type=int, metavar="n", help="구역 하나만")
    ru.add_argument("--to", metavar="기록", help="그 구역을 이 기록으로(기본: 같은 갈래의 가장 새 기록)")
    ru.add_argument("--dry-run", action="store_true", help="차이만 보이고 바꾸지 않는다")
    ru.add_argument("--force", action="store_true", help="손으로 고친 구역도 덮는다")


def dispatch(args, cmdline: str) -> int:
    from ..projects import Project, ProjectError
    from ..work.store import RecordError, detect_who
    from ..workfile.output import verbose
    old = verbose()
    verbose(0)
    who = detect_who("terminal")
    code = EXIT_OK
    try:
        p = Project.open(args.project)
        if args.command == "an":
            out, code = _an(p, args, who, cmdline)
        elif args.command == "note":
            if args.note_command == "run":
                r = p.note_run(args.note, block=args.block, stale=args.stale, force=args.force, who=who, command=cmdline)
                out = r.to_dict() if args.json else r.text()
                code = EXIT_OK if r.ok else EXIT_SCRIPT
            else:
                rs = [p.note_check(nm) for nm in args.notes]
                out = [r.to_dict() for r in rs] if args.json else "\n".join(r.text() for r in rs)
                code = EXIT_OK if all(r.ok for r in rs) else EXIT_INPUT
        else:
            out = _report(p, args, who, cmdline)
    except (ProjectError, RecordError, KeyError, ValueError) as e:
        fail(f"{e.args[0] if isinstance(e, KeyError) else e}")
        return EXIT_INPUT
    finally:
        verbose(old)
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str) if args.json else out)
    return code


def _an(p, args, who, cmdline):
    act = args.an_command
    if act == "list":
        rows = reg.table() if not args.for_kind else [r for r in reg.table()
                                                       if reg.TARGET_KO[args.for_kind] in r["대상"].split(" · ")]
        if args.json:
            return rows, EXIT_OK
        L = [f"[an list] 분석 {len(rows)}" + (f" — 대상 {reg.TARGET_KO[args.for_kind]}" if args.for_kind else "")]
        for r in rows:
            L.append(f"  {r['분석']:<12} {r['이름']:<8} {r['대상']:<28} 만드는 것 {r['만드는 것']}")
        L.append("  옵션·예: equion an <분석> --help")
        return "\n".join(L), EXIT_OK
    if act == "keep":
        r = p.keep(args.record, as_name=args.as_name, replace=args.replace, who=who, command=cmdline)
        return (r.to_dict() if args.json else r.text()), EXIT_OK
    a = reg.get(act)
    opts = {o.name: getattr(args, o.name) for o in a.options}
    r = p.an(act, args.target, smpl=args.smpl, as_name=args.as_name, note=args.note, who=who, command=cmdline, **opts)
    return (r.to_dict() if args.json else r.text()), EXIT_OK


def _report(p, args, who, cmdline):
    act = args.report_command
    if act == "new":
        r = p.report_new(args.name, title=args.title, from_report=args.from_report, exist_ok=args.exist_ok, who=who,
                         command=cmdline)
    elif act == "add":
        rows = [x.strip() for x in args.rows.split(",") if x.strip()] if args.rows else None
        r = p.report_add(args.report, args.record, rows=rows, show=args.show, annual=args.annual, digits=args.digits,
                         title=args.title, chart=args.chart, under=args.under, key=args.key, force=args.force, who=who,
                         command=cmdline)
    elif act == "check":
        r = p.report_check(args.report)
    else:
        r = p.report_update(args.report, region=args.region, to=args.to, dry_run=args.dry_run, force=args.force, who=who,
                            command=cmdline)
    return r.to_dict() if args.json else r.text()
