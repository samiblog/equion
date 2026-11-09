#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_guide.py — Claude용 모형 작업 안내·스킬 초안(개발 계획 E6) 테스트.

실행: uv run python tests/test_guide.py   (종료코드 = 실패 수)

  A. 안내: 제목·자동 표(명령·분석·허용 목록)가 채워져 있고 코드와 같다 · 모든 명령·분석 이름이 안내에 · 파일 이름이 CLAUDE.md로 읽히지 않는다
  B. 명령 예: 안내·스킬의 ```bash 블록에 든 `equion …` 줄이 모두 명령줄로 읽힌다(선택지·인자까지)
  C. 스킬: 앞머리(name: equion · description 1024자 이하) · 방정식 예가 분류대로 읽히고 예제 자료로 추정된다
  D. 명령줄: guide · --path · skill · skill --install project·user(다른 내용이면 --force 없이 덮지 않음) · --install은 스킬에만
  E. 예제 프로젝트: CLAUDE.md가 equion guide와 월간 스크립트를 가리킨다
"""

import contextlib
import io
import os
import re
import shlex
import shutil
import sys
import tempfile
import time
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import equion as eqn  # noqa: E402
from equion import help as guide  # noqa: E402
from equion import registry as reg  # noqa: E402
from equion.cli import main as cli  # noqa: E402
from equion.cli.commands import build_parser  # noqa: E402
from equion.formula.parser import classify_line  # noqa: E402
from equion.script.language import strip_comment  # noqa: E402

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  — {detail}" if detail else ""))


def run(args, where=None):
    out, err = io.StringIO(), io.StringIO()
    old = os.getcwd()
    os.chdir(where or old)
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli(list(args))
    finally:
        os.chdir(old)
    return code, out.getvalue(), err.getvalue()


def bash_lines(text):
    """```bash 블록 안의 `equion …` 줄(줄 끝 주석 뺌)."""
    out, inside = [], False
    for line in text.split("\n"):
        s = line.strip()
        if s.startswith("```"):
            inside = s == "```bash"
            continue
        if inside and s.startswith("equion "):
            out.append(strip_comment(s).strip())
    return out


def parses(line):
    """명령줄로 읽히면 None, 아니면 까닭."""
    err = io.StringIO()
    try:
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            build_parser().parse_args(shlex.split(line)[1:])
    except SystemExit:
        return err.getvalue().strip().splitlines()[-1] if err.getvalue().strip() else "SystemExit"
    return None


def main():
    t0 = time.time()
    tmp = tempfile.mkdtemp(prefix="eqn-guide-")
    old_verbose = eqn.verbose()
    eqn.verbose(0)
    try:
        return _main(tmp, t0)
    finally:
        eqn.verbose(old_verbose)
        shutil.rmtree(tmp, ignore_errors=True)


def _main(tmp, t0):
    g, sk = guide.guide_text(), guide.skill_text()

    print("\n== A. 안내 ==")
    check("A1 제목 · 쓴 파일이 그대로 읽힌다", g.splitlines()[0] == "# Equion — Claude를 위한 모형 작업 안내"
          and os.path.isfile(guide.GUIDE) and os.path.isfile(guide.SKILL))
    secs = re.findall(r"<!-- equion:auto (\w+) -->\n(.*?)<!-- /equion:auto -->", g, re.S)
    check("A2 자동 표 셋이 채워져 있다(명령·분석·허용 목록)", sorted(n for n, _ in secs) == ["allowed", "analyses", "commands"]
          and all(body.startswith("| ") for _, body in secs))
    check("A3 파일의 표가 지금 코드와 같다(make_api --check와 같은 검사)", guide.sync(check=True) == [])
    import argparse
    p = build_parser()
    sub = next(a for a in p._actions if isinstance(a, argparse._SubParsersAction))
    missing = [n for n in sub.choices if f"`{n}`" not in g]
    check("A4 명령줄의 모든 명령이 안내에", not missing, ", ".join(missing))
    missing = [a.name for a in reg.analyses() if f"`{a.name}`" not in g]
    check("A5 등록부의 모든 분석이 안내에", not missing, ", ".join(missing))
    names = [n.lower() for n in os.listdir(os.path.dirname(guide.GUIDE))]
    check("A6 안내 파일이 CLAUDE.md로 읽히지 않는다(대소문자를 가리지 않는 OS)", "claude.md" not in names)
    check("A7 꼭 지킬 것 — 근거 기록·결과 불변·제안만·거른 후보·알아서 한 것", all(r in g for r in (
        "근거 기록의 이름", "결과는 고치지 않는다", "제안만", "거른 후보도 기록", "알아서 한 것")))

    print("\n== B. 명령 예 ==")
    lines = bash_lines(g) + bash_lines(sk)
    bad = [(ln, why) for ln in lines for why in [parses(ln)] if why]
    check(f"B1 ```bash의 equion 줄 {len(lines)}개가 모두 읽힌다", len(lines) >= 20 and not bad, str(bad[:3]))
    prose = "\n".join(x for x in g.split("\n") if not x.lstrip().startswith("|"))      # 표(자동 표의 도움말 글) 말고 글
    inline = re.findall(r"`(equion [^`…<>]+)`", prose)
    bad = [(ln, why) for ln in inline for why in [parses(ln)]
           if why and "인자가 필요합니다" not in why and "이름" not in ln and "x.eqs" not in ln]   # 이름만 가리킨 것(인자 없음)은 괜찮다
    check(f"B2 글 안의 `equion …` {len(inline)}개도 읽힌다(이름만 가리킨 것 말고)", len(inline) >= 8 and not bad, str(bad[:3]))

    print("\n== C. 스킬 ==")
    m = re.match(r"^---\nname: (\S+)\ndescription: (.+?)\n---\n", sk, re.S)
    check("C1 앞머리 — name: equion · description(1024자 이하)", m is not None and m[1] == "equion" and 50 < len(m[2]) <= 1024)
    eqs = [strip_comment(x.strip()) for x in sk.split("## 방정식 파일")[1].split("시계열:")[0].split("\n")
           if x.startswith("    ") and x.strip()]
    check("C2 방정식 예의 분류(추정식·추정식·항등식·추정식)", [classify_line(x) for x in eqs] ==
          ["estimated", "estimated", "identity", "estimated"], str(eqs))
    wf = eqn.wfopen(eqn.datasets.path("toy_q"))
    ok = []
    for i, x in enumerate(eqs):
        if classify_line(x) == "estimated":
            r = wf.equation(f"skill_{i}").ls(x)
            ok.append(r is not None)
    check("C3 추정식 예가 예제 자료로 추정된다", ok and all(ok))
    geqs = [strip_comment(x.strip()) for x in g.split("## 9. 방정식 문법")[1].split("| 쓸 수 있는 것")[0].split("\n")
            if x.startswith("    ") and x.strip()]
    check("C4 안내의 방정식 예 — 추정식·추정식·항등식·추정식·비선형", [classify_line(x) for x in geqs] ==
          ["estimated", "estimated", "identity", "estimated", "nls"], str(geqs))
    r = wf.equation("guide_fn").ls("CN c d(Y,1,4) abs(R) sqrt(Y) exp(R/100) @pca(P) @movsum(G,4) @seas @d(2008Q4) @step(2010Q1) @trend")
    check("C5 안내의 함수·지시자 표가 실제로 읽힌다", r is not None)

    print("\n== D. 명령줄 ==")
    code, out, _ = run(["guide"])
    check("D1 equion guide", code == 0 and out.startswith("# Equion — Claude를 위한 모형 작업 안내") and "| `est` |" in out)
    code, out, _ = run(["guide", "--path"])
    code2, out2, _ = run(["guide", "skill"])
    check("D2 --path · skill", code == 0 and os.path.samefile(out.strip(), guide.GUIDE) and code2 == 0 and out2.startswith("---\nname: equion"))
    prj = os.path.join(tmp, "prj")
    os.makedirs(prj)
    code, out, _ = run(["guide", "skill", "--install", "project", "-p", prj])
    dst = os.path.join(prj, ".claude", "skills", "equion", "SKILL.md")
    code2, _, _ = run(["guide", "skill", "--install", "project", "-p", prj])
    with open(dst, "a", encoding="utf-8") as f:
        f.write("\n내가 고친 줄\n")
    code3, _, err3 = run(["guide", "skill", "--install", "project", "-p", prj])
    code4, _, _ = run(["guide", "skill", "--install", "project", "-p", prj, "--force"])
    check("D3 --install project — 같은 내용은 다시 써도 되고, 다르면 --force 없이 덮지 않는다(3)",
          (code, code2, code3, code4) == (0, 0, 3, 0) and "--force" in err3
          and open(dst, encoding="utf-8").read() == guide.skill_text())
    saved = {k: os.environ.get(k) for k in ("HOME", "USERPROFILE")}
    os.environ["HOME"] = os.environ["USERPROFILE"] = os.path.join(tmp, "home")
    try:
        path = guide.install_skill("user")
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    check("D4 --install user → ~/.claude/skills/equion/SKILL.md", path.replace(os.sep, "/").endswith("home/.claude/skills/equion/SKILL.md")
          and os.path.isfile(path))
    code, _, err = run(["guide", "--install", "user"])
    check("D5 --install은 스킬에만(3)", code == 3 and "스킬에만" in err)

    print("\n== E. 예제 프로젝트 ==")
    with contextlib.redirect_stdout(io.StringIO()):
        q = eqn.Project.create(os.path.join(tmp, "demo"))
    cm = open(os.path.join(q.root, "CLAUDE.md"), encoding="utf-8").read()
    check("E1 CLAUDE.md — equion guide · 월간 스크립트 · 받은 상자", "`equion guide`" in cm and "FLOWS/monthly.eqs" in cm
          and "DATA/raw/inbox/" in cm)
    inline = re.findall(r"`(equion [^`]+)`", cm)
    check("E2 CLAUDE.md의 명령도 읽힌다", inline and all(parses(x) is None for x in inline), str(inline))

    print()
    print(f"결과: {len(PASS)}/{len(PASS) + len(FAIL)} 통과 ({time.time() - t0:.1f}초)")
    if FAIL:
        print("실패:", ", ".join(FAIL))
    return len(FAIL)


def test_suite():
    """pytest 진입점 — 이 파일의 검사 묶음 전체(하나라도 실패하면 실패). `python tests/test_guide.py`와 같은 검사."""
    assert main() == 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(99)
