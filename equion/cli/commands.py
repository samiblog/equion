#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""명령줄 — `equion <명령>` (설치 시) 또는 `python -m equion <명령>` (DECISIONS D5·D6).

    equion run 스크립트.py [--smpl S:E] [--set 이름=값 ...] [--out 폴더] [--format csv,html] [-- 스크립트 인자]
    equion check 방정식.txt [--data 자료.xlsx] [--smpl S:E]    |  equion check 스크립트.py
    equion info [경로]
    equion new 폴더 [--bare]  ·  equion convert 옛파일 새이름 [--allow-pickle]

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

PROG = "equion"
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
        self.print_usage(sys.stderr)
        self.exit(EXIT_INPUT, f"{self.prog}: 오류: {message}\n")


def build_parser() -> argparse.ArgumentParser:
    p = _Parser(prog=PROG, description="Equion — 방정식 추정·연립 모델 풀이: 스크립트 실행·검사·정보·새 프로젝트",
                epilog="종료 코드: 0 성공 · 1 스크립트 오류 · 2 풀이 실패(--fail-on) · 3 입력 오류 · 130 중단")
    p.add_argument("--version", action="version",
                   version=f"equion {project_version()}")
    sub = p.add_subparsers(dest="command", metavar="명령", parser_class=_Parser)

    r = sub.add_parser("run", help="스크립트를 실행하고 보고서 폴더를 남긴다",
                       description="평범한 Python 스크립트를 실행한다. 스크립트에 넘길 인자는 -- 뒤에 쓴다.")
    r.add_argument("script", help="실행할 .py 스크립트")
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
    r.add_argument("--manifest-to", help=argparse.SUPPRESS)

    c = sub.add_parser("check", help="실행 없이 방정식 파일·스크립트를 검사한다")
    c.add_argument("path", help="방정식 파일(.txt) 또는 스크립트(.py)")
    c.add_argument("--data", metavar="FILE", help="데이터 파일·워크파일 — 변수 존재와 결측 입력까지 검사")
    c.add_argument("--freq", choices=("Q", "M", "A"), help="주기(데이터가 없거나 추론이 안 될 때)")
    c.add_argument("--smpl", metavar="S:E", help="결측 입력을 볼 구간(기본: 데이터 전체)")
    c.add_argument("--json", action="store_true", help="결과를 JSON으로")
    c.add_argument("--strict", action="store_true", help="경고도 실패(종료 코드 3)로 본다")

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
    n.add_argument("--bare", action="store_true", help="예시 없이 빈 뼈대만")
    n.add_argument("--force", action="store_true", help="비어 있지 않은 폴더에도 쓴다(같은 이름 파일을 덮음)")
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
            print(f"{PROG}: 오류: --threads는 1 이상이어야 합니다", file=sys.stderr)
            return EXIT_INPUT
        if os.environ.get("EQUION_THREADS") != str(args.threads):
            return _reexec_with_threads(args.threads, argv)
    if not os.path.isfile(args.script):
        print(f"{PROG}: 오류: 스크립트가 없습니다: {args.script}", file=sys.stderr)
        return EXIT_INPUT
    if not args.script.lower().endswith(".py"):
        print(f"{PROG}: 오류: 스크립트는 .py 파일이어야 합니다: {args.script}", file=sys.stderr)
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
        print(f"{PROG}: 오류: {e}", file=sys.stderr)
        return EXIT_INPUT
    if args.watch:
        if args.interactive:
            print(f"{PROG}: 오류: --watch와 -i는 함께 쓸 수 없습니다", file=sys.stderr)
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
    from .check import check_path
    try:
        rep = check_path(args.path, data=args.data, freq=args.freq, smpl=args.smpl)
    except Exception as e:  # noqa: BLE001 — 파일 없음·데이터 읽기 실패
        print(f"{PROG}: 오류: {e}", file=sys.stderr)
        return EXIT_INPUT
    print(json.dumps(rep.to_dict(), ensure_ascii=False, indent=2) if args.json else rep.text())
    failed = not rep.ok or (args.strict and rep.issues)
    return EXIT_INPUT if failed else EXIT_OK


def cmd_info(args) -> int:
    from .info import describe, to_text
    try:
        info = describe(args.path, freq=args.freq, show_all=args.all)
    except Exception as e:  # noqa: BLE001
        print(f"{PROG}: 오류: {e}", file=sys.stderr)
        return EXIT_INPUT
    print(json.dumps(info, ensure_ascii=False, indent=2, default=str) if args.json else to_text(info))
    return EXIT_OK


def cmd_convert(args) -> int:
    from .convert import convert
    try:
        out = convert(args.src, args.dst, allow_pickle=args.allow_pickle, name=args.name)
    except Exception as e:  # noqa: BLE001 — 파일 없음·pickle 거부·형식 오류
        print(f"{PROG}: 오류: {e}", file=sys.stderr)
        return EXIT_INPUT
    print(f"변환 완료: {args.src} → {out}")
    return EXIT_OK


def cmd_new(args) -> int:
    from .new import create_project
    try:
        files = create_project(args.path, bare=args.bare, force=args.force)
    except (OSError, FileExistsError) as e:
        print(f"{PROG}: 오류: {e}", file=sys.stderr)
        return EXIT_INPUT
    print(f"새 프로젝트 {args.path}:")
    for f in files:
        print(f"  {f}")
    if not args.bare:
        print(f"\n다음:\n  cd {args.path}\n  equion run scripts/main.py")
    return EXIT_OK


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
    _safe_streams()
    argv = list(sys.argv[1:] if argv is None else argv)
    script_args = []
    if "--" in argv:
        k = argv.index("--")
        argv, script_args = argv[:k], argv[k + 1:]
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
        print(f"{PROG}: 오류: '--' 뒤 인자는 run에서만 쓸 수 있습니다", file=sys.stderr)
        return EXIT_INPUT
    try:
        if args.command == "check":
            return cmd_check(args)
        if args.command == "info":
            return cmd_info(args)
        if args.command == "new":
            return cmd_new(args)
        if args.command == "convert":
            return cmd_convert(args)
    except KeyboardInterrupt:
        return EXIT_INTERRUPT
    parser.print_help()
    return EXIT_OK
