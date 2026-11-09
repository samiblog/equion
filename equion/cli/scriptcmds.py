#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""스크립트 명령(D36, E5) — `.eqs` 실행·미리보기·재연·검사, 초안·Python으로.

    equion run FLOWS/monthly.eqs [--set 이름=값] [--from 단계·제목] [--dry-run] [--fail-on …] [-q·-v] [-p 프로젝트]
    equion run --replay run:monthly_0001 [-p 프로젝트]
    equion check FLOWS/monthly.eqs [--set 이름=값]
    equion script new 이름 [--from-records 기록…] [--last n] · equion script export FLOWS/monthly.eqs --py [-o 파일]
"""

import json
import os
import sys

from .runner import EXIT_INPUT, EXIT_OK

PROG = "equion"
COMMANDS = ("script",)
_PY_ONLY = (("smpl", None, "--smpl"), ("watch", False, "--watch"), ("interactive", False, "-i"), ("out", "out", "--out"),
            ("format", "csv,html", "--format"), ("no_report", False, "--no-report"), ("plotlyjs", "copy", "--plotlyjs"),
            ("redact", False, "--redact"), ("run_args", None, "--"))


def _err(msg) -> int:
    from .errors import fail
    return fail(msg)


def _project(args, script=None):
    from ..projects import Project
    from ..script.session import find_root
    root = args.project or find_root(script or ".")
    return Project.open(root)


def _script_path(p, script):
    full = os.path.abspath(script)
    if not os.path.isfile(full) and os.path.isfile(os.path.join(p.root, script)):
        full = os.path.join(p.root, script)
    return os.path.relpath(full, p.root).replace(os.sep, "/")


def cmd_run_eqs(args, argv, script_args=()) -> int:
    """`equion run x.eqs` · `equion run --replay run:…`."""
    from ..projects import ProjectError
    from ..script import ScriptError
    from ..work.store import RecordError, detect_who
    from ..workfile.output import verbose
    from .commands import _cmdline, _parse_sets
    bad = [flag for name, default, flag in _PY_ONLY if name != "run_args" and getattr(args, name, default) != default]
    if script_args:
        bad.append("-- 스크립트 인자")
    if bad:
        return _err(f".eqs 실행에서는 쓰지 않는 선택지: {', '.join(bad)} — 실행 기록은 work/run/에 남는다(.py 스크립트용 선택지)")
    if args.replay and args.script:
        return _err("--replay에는 스크립트를 주지 않습니다(실행 기록에 들어 있다): equion run --replay run:이름")
    who = detect_who("terminal")
    cmdline = _cmdline(argv)
    verbosity = 0 if args.quiet else (2 if args.verbose else 1)
    log = []

    def echo(line):
        log.append(line)
        if not args.json:
            print(line, flush=True)
    old = verbose()
    verbose(0)
    try:
        p = _project(args, args.script)
        if args.replay:
            res = p.replay_run(args.replay, who=who, command=cmdline)
            out = res.to_dict() if args.json else res.text()
            code = res.exit_code
        else:
            if not os.path.isfile(args.script) and not os.path.isfile(os.path.join(p.root, args.script)):
                return _err(f"스크립트가 없습니다: {args.script}")
            rel = _script_path(p, args.script)
            params = _parse_sets(args.sets, args.params)
            if args.dry_run:
                pl = p.run_script(rel, sets=params, from_step=args.from_step, dry_run=True)
                out = pl.to_dict() if args.json else pl.text()
                code = EXIT_OK if pl.ok else EXIT_INPUT
            else:
                res = p.run_script(rel, sets=params, from_step=args.from_step, fail_on=args.fail_on, name=args.run_id,
                                   who=who, command=cmdline, echo=echo, verbosity=verbosity)
                out = res.to_dict() if args.json else res.text()
                code = res.exit_code
    except (ScriptError, ProjectError, RecordError, KeyError, ValueError, OSError) as e:
        return _err(e.args[0] if isinstance(e, KeyError) else e)
    finally:
        verbose(old)
    text = json.dumps(out, ensure_ascii=False, indent=2, default=str) if args.json else out
    print(text, file=sys.stderr if (code and not args.json) else sys.stdout)
    if args.log:
        with open(args.log, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(log + [text if isinstance(text, str) else ""]) + "\n")
    return code


def cmd_check_eqs(args) -> int:
    """`equion check x.eqs`."""
    from ..projects import ProjectError
    from ..script import ScriptError
    from ..workfile.output import verbose
    from .commands import _parse_sets
    old = verbose()
    verbose(0)
    try:
        p = _project(args, args.path)
        r = p.check_script(_script_path(p, args.path), sets=_parse_sets(args.sets or [], None))
    except (ScriptError, ProjectError, KeyError, ValueError) as e:
        return _err(e.args[0] if isinstance(e, KeyError) else e)
    finally:
        verbose(old)
    print(json.dumps(r.to_dict(), ensure_ascii=False, indent=2) if args.json else r.text())
    return EXIT_OK if r.ok else EXIT_INPUT


def add_parsers(sub):
    s = sub.add_parser("script", help="스크립트(.eqs) — 작업 기록으로 초안 · 같은 일을 하는 Python으로")
    ssub = s.add_subparsers(dest="script_command", metavar="동작")
    ssub.required = True
    sn = ssub.add_parser("new", help="새 스크립트 FLOWS/<이름>.eqs — 작업 기록의 명령으로 초안(없으면 빈 틀)")
    sn.add_argument("name", metavar="이름")
    sn.add_argument("--from-records", nargs="+", default=None, metavar="기록", help="이 기록들의 명령을 차례로")
    sn.add_argument("--last", type=int, metavar="n", help="최근 기록 n개의 명령(실행 기록 run: 제외)")
    sn.add_argument("--title", help="제목(첫 주석 줄)")
    sn.add_argument("--force", action="store_true", help="이미 있으면 덮는다")
    se = ssub.add_parser("export", help="스크립트를 같은 일을 하는 Python 파일로(eqn.script.session)")
    se.add_argument("script", metavar="스크립트.eqs")
    se.add_argument("--py", action="store_true", required=True, help="Python으로(지금은 이것만)")
    se.add_argument("-o", "--out", metavar="파일.py", help="쓸 파일(기본: 같은 자리의 .py)")
    se.add_argument("--force", action="store_true", help="이미 있으면 덮는다")
    for sp in (sn, se):
        sp.add_argument("--project", "-p", default=None, metavar="폴더", help="프로젝트 폴더(기본: 지금 폴더에서 위로)")
        sp.add_argument("--json", action="store_true", help="결과를 JSON으로")


def dispatch(args, cmdline: str) -> int:
    from ..projects import ProjectError
    from ..script import ScriptError
    from ..work.store import detect_who
    from ..workfile.output import verbose
    old = verbose()
    verbose(0)
    try:
        if args.script_command == "new":
            p = _project(args, ".")
            rel = p.new_script(args.name, records=args.from_records, last=args.last, title=args.title, force=args.force,
                               who=detect_who("terminal"), command=cmdline)
            text = open(os.path.join(p.root, rel), encoding="utf-8").read()
            out = {"script": rel, "text": text} if args.json else (f"[script new] {rel}\n" + "\n".join(
                "  " + x for x in text.rstrip().splitlines()) + f"\n  다음   equion check {rel} → equion run {rel} --dry-run")
        else:
            p = _project(args, args.script)
            rel = p.export_script(_script_path(p, args.script), out=args.out, force=args.force)
            out = {"script": args.script, "py": rel} if args.json else (
                f"[script export] {args.script} → {rel}\n  실행   python {rel}   (또는 equion run {rel} --set 이름=값)")
    except (ScriptError, ProjectError, KeyError, ValueError, OSError) as e:
        return _err(e.args[0] if isinstance(e, KeyError) else e)
    finally:
        verbose(old)
    print(json.dumps(out, ensure_ascii=False, indent=2) if args.json else out)
    return EXIT_OK
