#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""문서 빌드·검사 — 문서의 예제가 실제로 돌아가고 출력이 맞는지를 기계가 확인한다(DECISIONS D27).

    python docs/build_docs.py              # 예제를 실행해 출력을 문서에 써 넣고, examples/(스크립트·노트북)를 다시 만든다
    python docs/build_docs.py --check      # 다시 쓰지 않고 검사만(CI): 예제 실행 · 출력 일치 · examples/ 동기화 ·
                                           #   링크 · 공개 API 설명/예제 · docstring 예제(doctest)
    python docs/build_docs.py --only tutorial/01   # 경로에 이 글자가 든 문서만

문서 쓰는 법(마크다운 안의 표시 — 화면에는 보이지 않는다):

    ```python … ```   실행되는 예제. 한 문서의 블록은 위에서부터 같은 이름공간에서 차례로 돈다(노트북처럼).
                      작업 폴더는 문서마다 새 임시 폴더다(DATA/·EQUATIONS/를 쓰면 저장소 것을 이어 준다).
    <!-- out -->      바로 앞 예제 블록의 화면 출력을 다음 ```text 블록에 써 넣는다(빌드가 채운다 — 손으로 고치지 않는다).
    <!-- skip -->     다음 블록은 실행하지 않는다(설명용 조각).
    <!-- error -->    다음 블록은 오류로 끝나야 한다(오류 메시지가 출력이 된다).
    <!-- no-export --> 이 문서는 examples/로 내보내지 않는다.

출력 비교는 숫자를 그 자릿수의 반올림 범위 안에서 같다고 보고, 걸린 시간·실행 ID·임시 경로는 가린다(BLAS·OS 차이 흡수).
"""

import argparse
import contextlib
import doctest
import io
import json
import os
import re
import shutil
import sys
import tempfile
import traceback
import warnings

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
DOCS = os.path.join(ROOT, "docs")
EXAMPLES = os.path.join(ROOT, "examples")

# 예제를 실행하는 문서(사용자 문서). 프로젝트 문서(DECISIONS·ROADMAP …)의 코드는 설명용이라 돌리지 않는다.
RUN_DIRS = ("start", "tutorial", "howto", "guide", "explain", "reference", "cases", "en")
RUN_FILES = ("docs/README.md", "docs/eviews.md", "README.md", "README.en.md")
# examples/로 내보내는 문서 묶음: 묶음 → 노트북도 만들지
EXPORT = {"start": True, "tutorial": True, "howto": False}
LINK_ROOTS = ("docs", "examples")
LINK_FILES = ("README.md", "README.en.md", "CHANGELOG.md", "CLAUDE.md", "THIRD-PARTY-NOTICES.md")

MARK_RE = re.compile(r"^\s*<!--\s*(skip|out|error)\s*-->\s*$")
HEAD_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")


def rel(p):
    return os.path.relpath(p, ROOT).replace(os.sep, "/")


# ---------------------------------------------------------------------------
# 마크다운 읽기
# ---------------------------------------------------------------------------
class Block:
    def __init__(self, lang, start, end, code, flags):
        self.lang, self.start, self.end, self.code, self.flags = lang, start, end, code, set(flags)
        self.out = None            # 출력 블록(Block) — <!-- out --> 뒤의 ```text
        self.out_marker = None     # <!-- out --> 줄 번호(출력 블록이 아직 없을 때 넣을 자리)


def parse(text):
    """블록 목록과 줄 목록. 블록 = 펜스(```) 안. 표시 주석은 바로 다음(skip·error) 또는 바로 앞(out) 블록에 붙는다."""
    lines = text.split("\n")
    blocks, pending, i, last_py = [], set(), 0, None
    want_out = None
    while i < len(lines):
        line = lines[i]
        m = MARK_RE.match(line)
        if m:
            if m.group(1) == "out":
                if last_py is None:
                    raise ValueError(f"{i + 1}행: <!-- out --> 앞에 python·console 블록이 없습니다")
                last_py.out_marker = i
                want_out = last_py
            else:
                pending.add(m.group(1))
            i += 1
            continue
        if line.startswith("```"):
            info = line[3:].strip()
            lang = info.split()[0] if info else ""
            j = i + 1
            while j < len(lines) and lines[j].strip() != "```":
                j += 1
            if j >= len(lines):
                raise ValueError(f"{i + 1}행: 닫히지 않은 코드 블록")
            b = Block(lang, i, j, "\n".join(lines[i + 1:j]), pending)
            pending = set()
            if want_out is not None and lang == "text":
                want_out.out = b
                want_out = None
            else:
                want_out = None
                blocks.append(b)
                if lang in ("python", "console"):
                    last_py = b
            i = j + 1
            continue
        if line.strip():
            want_out = None        # <!-- out --> 다음에는 (빈 줄 뒤) 곧바로 ```text 블록이어야 한다
        i += 1
    return blocks, lines


def headings(lines):
    """(줄 번호, 수준, 제목) — 코드 블록 안은 뺀다."""
    out, fence = [], False
    for k, line in enumerate(lines):
        if line.startswith("```"):
            fence = not fence
            continue
        if not fence:
            m = HEAD_RE.match(line)
            if m:
                out.append((k, len(m.group(1)), m.group(2)))
    return out


def slug(title):
    """GitHub 머리글 앵커 규칙(소문자, 글자·숫자·공백·-·_만 남기고 공백은 -)."""
    t = re.sub(r"<[^>]+>", "", title)
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", t)
    t = t.strip().lower()
    t = re.sub(r"[^\w\- ]", "", t)
    return t.replace(" ", "-")


def anchors(lines):
    seen, out = {}, set()
    for _, _, title in headings(lines):
        s = slug(title)
        n = seen.get(s, 0)
        out.add(s if n == 0 else f"{s}-{n}")
        seen[s] = n + 1
    return out


# ---------------------------------------------------------------------------
# 실행
# ---------------------------------------------------------------------------
def _link_repo_dirs(work, code):
    # 저장소 입력 폴더만 잇는다 — 이어 준 폴더에 쓰면 저장소가 바뀌므로 문서 예제는 거기에 쓰지 않는다
    for d in ("DATA", "EQUATIONS"):
        if f"{d}/" in code and os.path.isdir(os.path.join(ROOT, d)) and not os.path.exists(os.path.join(work, d)):
            try:
                os.symlink(os.path.join(ROOT, d), os.path.join(work, d), target_is_directory=True)
            except (OSError, NotImplementedError):          # Windows(개발자 모드 아님) — 복사
                shutil.copytree(os.path.join(ROOT, d), os.path.join(work, d))


def _reset_equion():
    import equion as eqn
    eqn.verbose(1)
    eqn.spool.clear()
    eqn.spool.mode = "auto"


CONSOLE_ENV = {"PYTHONIOENCODING": "utf-8", "EQUION_WHO": "terminal"}


def run_console(code: str):
    """```console 블록 — `$ equion …`(명령줄 그대로, 하위 프로세스)과 `$ cd 폴더`만 받는다. → (기록 글, 0이 아닌 종료 코드 목록, 문제)."""
    import shlex
    import subprocess
    out, bad = [], []
    for raw in code.split("\n"):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if not line.startswith("$ "):
            return "\n".join(out), bad, f"console 블록의 줄은 '$ '로 시작해야 합니다: {line!r}"
        cmd = line[2:].strip()
        toks = shlex.split(cmd, posix=True)
        if toks[0] == "cd" and len(toks) == 2:
            os.chdir(toks[1])
            out.append(f"$ {cmd}")
            continue
        if toks[0] != "equion":
            return "\n".join(out), bad, f"console 블록은 equion·cd만 실행합니다: {cmd!r}"
        env = dict(os.environ, **CONSOLE_ENV)
        r = subprocess.run([sys.executable, "-m", "equion", *toks[1:]], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", env=env, stdin=subprocess.DEVNULL)
        text = (r.stdout + r.stderr).rstrip()
        out.append(f"$ {cmd}" + ("\n" + text if text else ""))
        if r.returncode:
            out.append(f"(종료 코드 {r.returncode})")
            bad.append((cmd, r.returncode))
        out.append("")
    return "\n".join(out).rstrip(), bad, None


def run_blocks(md_path, blocks, work):
    """python·console 블록을 차례로 실행 → [(블록, 출력 글, 문제 또는 None)]. console의 0이 아닌 종료 코드는
    `<!-- error -->`를 붙인 블록에서만 괜찮다."""
    ns = {"__name__": "__main__"}
    results = []
    old = os.getcwd()
    os.makedirs(work, exist_ok=True)
    os.chdir(work)
    _reset_equion()
    try:
        for b in blocks:
            if b.lang == "console" and "skip" not in b.flags:
                text, bad, problem = run_console(b.code)
                if problem:
                    problem = f"{rel(md_path)}:{b.start + 1}: {problem}"
                elif bad and "error" not in b.flags:
                    problem = (f"{rel(md_path)}:{b.start + 1}: 명령이 실패했습니다 — "
                               + " · ".join(f"{c} → {k}" for c, k in bad) + f"\n{text[-600:]}")
                elif "error" in b.flags and not bad:
                    problem = f"{rel(md_path)}:{b.start + 1}: 오류로 끝나야 하는 명령이 모두 성공했습니다"
                results.append((b, _clean(text, work), problem))
                if problem:
                    break
                continue
            if b.lang != "python" or "skip" in b.flags:
                continue
            _link_repo_dirs(work, b.code)
            buf = io.StringIO()
            err = None
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf), warnings.catch_warnings():
                warnings.simplefilter("default")
                # 인코딩 경고(PYTHONWARNDEFAULTENCODING — CI)는 Equion과 문서 예제의 것만 보인다. 다른 패키지(openpyxl·plotly)의
                # 경고는 사용자가 보는 출력이 아니다. Equion 자체의 인코딩은 다른 시험 묶음이 같은 설정으로 검사한다.
                warnings.filterwarnings("ignore", category=EncodingWarning, module=r"(?!equion\b|__main__\b)")
                try:
                    exec(compile(b.code, f"{rel(md_path)}:{b.start + 2}", "exec"), ns)  # noqa: S102 — 저장소의 문서 예제
                except Exception as e:  # noqa: BLE001
                    err = e
            out = buf.getvalue()
            problem = None
            if "error" in b.flags:
                if err is None:
                    problem = f"{rel(md_path)}:{b.start + 1}: 오류로 끝나야 하는 예제가 정상 종료했습니다"
                else:
                    out += f"{type(err).__name__}: {err}\n"
            elif err is not None:
                tb = "".join(traceback.format_exception(type(err), err, err.__traceback__)[-4:])
                problem = f"{rel(md_path)}:{b.start + 1}: 예제 실행 오류 — {type(err).__name__}: {err}\n{tb}"
            results.append((b, _clean(out, work), problem))
            if problem and "error" not in b.flags:
                break
    finally:
        os.chdir(old)
    return results


def _clean(text, work):
    """임시 작업 폴더·저장소 경로를 '.'로, 줄 끝 공백 제거."""
    # 긴 경로부터 — macOS의 /var는 /private/var를 가리켜, 짧은 것을 먼저 지우면 '/private'가 남는다
    for p in sorted({work, os.path.realpath(work)}, key=len, reverse=True):
        text = text.replace(p + os.sep, "").replace(p + "/", "").replace(p, ".")
    for p in sorted({ROOT, os.path.realpath(ROOT)}, key=len, reverse=True):
        text = text.replace(p + os.sep, "").replace(p + "/", "").replace(p, ".")
    return "\n".join(line.rstrip() for line in text.rstrip("\n").split("\n"))


VOLATILE = [
    (re.compile(r"\d+(?:\.\d+)?\s*초"), "#초"),
    (re.compile(r"(소요\(초\)|elapsed[_ a-z]*)\W+[\d.]+"), r"\1 #"),
    (re.compile(r"\b\d{8}-\d{6}(?:_\w+)?"), "#실행ID"),
    (re.compile(r"\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?"), "#시각"),
    (re.compile(r"(?<![A-Za-z0-9])d\d{4}-\d{2}[a-z]+\b"), "#회차"),        # 자료 회차 이름(만든 달) — forecast_d2026-11a.md도
    (re.compile(r"(?<![\w-])20\d{2}-\d{2}_(?=[A-Za-z])"), "#달_"),          # 전망 기록 이름의 달(sim:2026-11_base)
    (re.compile(r"(?<![\w-])\d{4}-\d{2}-\d{2}(?![\w:])"), "#날"),           # 날짜만(보고서 머리·{today})
    (re.compile(r"_\d{8}(?=[._])"), "_#날짜"),                             # 같은 이름 원자료에 붙는 날짜
    # 파일 해시(줄바꿈이 OS마다 다를 수 있다) — 줄인 해시(16자 + …)나 온 해시(64자)만. 수(4.54e-13)의 숫자를 가리지 않게
    (re.compile(r"(?<![\w.])[0-9a-f]{16}(?=…)|(?<![\w.])[0-9a-f]{64}(?![\w])"), "#해시"),
    (re.compile(r'"h": "[0-9a-f]{12}"'), '"h": "#해시"'),                   # 노트·보고서 구역 본문의 해시(본문에 시각이 있다)
    (re.compile(r"[\\/]"), "/"),
]
NUM = re.compile(r"[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][-+]?\d+)?")


def _mask(t):
    for rx, rep in VOLATILE:
        t = rx.sub(rep, t)
    return re.sub(r"[ \t]+", " ", t).strip()


def _decimals(s):
    m = re.match(r"[-+]?\d*\.(\d+)", s)
    return len(m.group(1)) if m else 0


def same_output(a, b):
    """숫자는 표시 자릿수의 반올림 범위(±1.5 ulp)·상대 1e-6 안이면 같다. 아주 작은 수(< 1e-8)는 서로 같다고 본다."""
    a, b = _mask(a), _mask(b)
    if a == b:
        return True
    if NUM.split(a) != NUM.split(b):
        return False
    for x, y in zip(NUM.findall(a), NUM.findall(b)):
        if x == y:
            continue
        fx, fy = float(x), float(y)
        if abs(fx) < 1e-8 and abs(fy) < 1e-8:
            continue
        tol = max(1.5 * 10 ** -max(_decimals(x), _decimals(y)) if "e" not in x.lower() + y.lower() else 0.0,
                  1e-6 * max(abs(fx), abs(fy)))
        if abs(fx - fy) > tol:
            return False
    return True


# ---------------------------------------------------------------------------
# examples/ 만들기
# ---------------------------------------------------------------------------
def _title(lines):
    for _, lvl, t in headings(lines):
        if lvl == 1:
            return t
    return ""


def export_script(md, blocks, lines):
    r = rel(md)
    out = [f"# 이 파일은 {r}에서 만든다(python docs/build_docs.py) — 고치려면 문서를 고친다.",
           f'"""{_title(lines)} — 문서: {r}"""', ""]
    heads = headings(lines)
    last_head = None
    for b in blocks:
        if b.lang != "python" or "skip" in b.flags:
            continue
        h = [t for k, _, t in heads if k < b.start]
        if h and h[-1] != last_head:
            last_head = h[-1]
            out += ["", f"# %% {last_head}"]
        if "error" in b.flags:
            out += ["try:  # 이 예는 일부러 오류를 보인다"] + ["    " + ln if ln else "" for ln in b.code.split("\n")]
            out += ["except Exception as e:", '    print(f"{type(e).__name__}: {e}")']
        else:
            out += b.code.split("\n")
    return "\n".join(out).rstrip() + "\n"


def export_notebook(md, blocks, lines):
    """노트북: 문서의 글은 마크다운 셀, 실행 예제는 코드 셀(출력 블록·표시 주석은 뺀다 — 노트북이 직접 출력한다)."""
    cells, used, n, cur = [], set(), 0, 0
    for b in blocks:
        if b.lang == "python" and "skip" not in b.flags:
            used.update(range(b.start, b.end + 1))
        if b.out is not None:
            used.update(range(b.out.start, b.out.end + 1))
    py = [b for b in blocks if b.lang == "python" and "skip" not in b.flags]

    src_dir, dst_dir = os.path.dirname(md), os.path.join(EXAMPLES, "notebooks")

    def add(kind, src):
        nonlocal n
        n += 1
        if kind == "markdown":
            src = _relink(src, src_dir, dst_dir)
        c = {"cell_type": kind, "id": f"c{n:03d}", "metadata": {}, "source": _src(src)}
        if kind == "code":
            c.update({"execution_count": None, "outputs": []})
        cells.append(c)

    for b in py:
        text = [ln for j, ln in enumerate(lines[cur:b.start], start=cur) if j not in used and not MARK_RE.match(ln)]
        txt = "\n".join(text).strip("\n")
        if txt.strip():
            add("markdown", txt)
        code = b.code
        if "error" in b.flags:
            code = ("try:  # 이 예는 일부러 오류를 보인다\n" + "\n".join("    " + ln if ln else "" for ln in code.split("\n"))
                    + "\nexcept Exception as e:\n    print(f\"{type(e).__name__}: {e}\")")
        add("code", code)
        cur = (b.out.end if b.out is not None else b.end) + 1
    tail = "\n".join(ln for j, ln in enumerate(lines[cur:], start=cur) if j not in used and not MARK_RE.match(ln)).strip("\n")
    if tail.strip():
        add("markdown", tail)
    nb = {"cells": cells,
          "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                       "language_info": {"name": "python"}},
          "nbformat": 4, "nbformat_minor": 5}
    return json.dumps(nb, ensure_ascii=False, indent=1) + "\n"


def _relink(text, src_dir, dst_dir):
    """마크다운 상대 링크를 다른 폴더(노트북 자리) 기준으로 바꾼다."""
    def fix(m):
        tgt = m.group(2)
        if re.match(r"^[a-z]+:", tgt) or tgt.startswith("#"):
            return m.group(0)
        path, sep, anc = tgt.partition("#")
        new = os.path.relpath(os.path.normpath(os.path.join(src_dir, path)), dst_dir).replace(os.sep, "/")
        return f"[{m.group(1)}]({new}{sep}{anc})"
    return LINK_RE.sub(fix, text)


def _src(text):
    ls = text.split("\n")
    return [ln + "\n" for ln in ls[:-1]] + [ls[-1]]


def export_targets(md):
    """문서 → [(경로, 내용 만드는 함수)]."""
    r = rel(md)
    parts = r.split("/")
    if len(parts) == 3 and parts[0] == "docs" and parts[1] in EXPORT:
        stem = os.path.splitext(parts[2])[0]
        t = [(os.path.join(EXAMPLES, parts[1], stem + ".py"), export_script)]
        if EXPORT[parts[1]]:
            t.append((os.path.join(EXAMPLES, "notebooks", stem + ".ipynb"), export_notebook))
        return t
    return []


# ---------------------------------------------------------------------------
# 링크
# ---------------------------------------------------------------------------
LINK_RE = re.compile(r"(?<!!)\[([^\]]+)\]\(([^)\s]+)\)")


def check_links(files):
    problems, cache = [], {}

    def anchor_set(path):
        if path not in cache:
            with open(path, encoding="utf-8") as f:
                cache[path] = anchors(f.read().split("\n"))
        return cache[path]

    for md in files:
        with open(md, encoding="utf-8") as f:
            lines = f.read().split("\n")
        fence = False
        for no, line in enumerate(lines, 1):
            if line.startswith("```"):
                fence = not fence
                continue
            if fence:
                continue
            for m in LINK_RE.finditer(re.sub(r"`[^`]*`", "", line)):
                tgt = m.group(2)
                if re.match(r"^[a-z]+:", tgt):
                    continue
                path, _, anc = tgt.partition("#")
                full = os.path.normpath(os.path.join(os.path.dirname(md), path)) if path else md
                if not os.path.exists(full):
                    problems.append(f"{rel(md)}:{no}: 없는 파일로 가는 링크 {tgt}")
                elif anc and full.endswith(".md") and anc not in anchor_set(full):
                    problems.append(f"{rel(md)}:{no}: {rel(full)}에 없는 앵커 #{anc}")
    return problems


# ---------------------------------------------------------------------------
# 공개 API: 설명·예제·doctest
# ---------------------------------------------------------------------------
NO_EXAMPLE = {"show", "output", "to_json", "from_json", "text", "html", "page", "figure", "spec", "graph",
              "cov", "irf_graph", "equation_stats", "table", "ic"}


def public_items():
    """(이름, 대상, 예제가 필요한지)."""
    sys.path.insert(0, DOCS)
    import make_api
    return make_api.public_items()


def check_api():
    import inspect
    problems = []
    for name, obj, need_example in public_items():
        d = inspect.getdoc(obj) or ""
        if not d.strip():
            problems.append(f"설명 없음: {name}")
        elif need_example and ">>>" not in d:
            problems.append(f"예제 없음: {name}")
    return problems


def run_doctests():
    import inspect
    import numpy as np
    import pandas as pd
    import equion as eqn
    problems = []
    finder = doctest.DocTestFinder(recurse=False, exclude_empty=True)
    flags = doctest.ELLIPSIS | doctest.NORMALIZE_WHITESPACE
    work = tempfile.mkdtemp(prefix="eqn-doctest-")
    old = os.getcwd()
    os.chdir(work)
    eqn.verbose(0)
    try:
        seen = set()
        for name, obj, _ in public_items():
            target = obj.fget if isinstance(obj, property) else obj
            if id(target) in seen or not (inspect.getdoc(target) or "").count(">>>"):
                continue
            seen.add(id(target))
            try:
                tests = finder.find(target, name, globs={"eqn": eqn, "np": np, "pd": pd})
            except ValueError as e:
                problems.append(f"doctest 형식 오류: {name} — {e}")
                continue
            for test in tests:
                buf = io.StringIO()
                runner = doctest.DocTestRunner(optionflags=flags, verbose=False)
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    runner.run(test, out=buf.write)
                if runner.failures:
                    problems.append(f"doctest 실패: {name}\n" + "\n".join(buf.getvalue().splitlines()[:30]))
    finally:
        os.chdir(old)
        eqn.verbose(1)
        shutil.rmtree(work, ignore_errors=True)
    return problems


# ---------------------------------------------------------------------------
def doc_files(only=None):
    files = []
    for d in RUN_DIRS:
        base = os.path.join(DOCS, d)
        for dirpath, _, names in os.walk(base):
            files += [os.path.join(dirpath, n) for n in sorted(names) if n.endswith(".md")]
    files += [os.path.join(ROOT, f) for f in RUN_FILES if os.path.exists(os.path.join(ROOT, f))]
    files = sorted(set(files))
    if only:
        files = [f for f in files if only in rel(f)]
    return files


def link_files():
    files = [os.path.join(ROOT, f) for f in LINK_FILES if os.path.exists(os.path.join(ROOT, f))]
    for d in LINK_ROOTS:
        for dirpath, _, names in os.walk(os.path.join(ROOT, d)):
            files += [os.path.join(dirpath, n) for n in names if n.endswith(".md")]
    return sorted(set(files))


def locked_versions() -> bool:
    """Python이 .python-version이고 numpy·pandas가 uv.lock에 잠근 판이면 True — 출력 비교는 이때만
    (다른 판은 표 서식·도움말 줄바꿈이 달라질 수 있어 실행만 확인)."""
    try:
        import numpy as np
        import pandas as pd
        with open(os.path.join(ROOT, "uv.lock"), encoding="utf-8") as f:
            lock = f.read()
        with open(os.path.join(ROOT, ".python-version"), encoding="utf-8") as f:
            pyver = f.read().strip()
    except OSError:
        return False
    if f"{sys.version_info.major}.{sys.version_info.minor}" != pyver:
        return False

    def ver(pkg):
        m = re.search(r'\[\[package\]\]\nname = "' + pkg + r'"\nversion = "([^"]+)"', lock)
        return m.group(1) if m else None
    return ver("numpy") == np.__version__ and ver("pandas") == pd.__version__


COMPARE = True


def process(md, check, base):
    """문서 하나: 실행 → (새 글 또는 None, 문제 목록, 내보낼 [(경로, 내용)])."""
    with open(md, encoding="utf-8") as f:
        text = f.read()
    try:
        blocks, lines = parse(text)
    except ValueError as e:
        return None, [f"{rel(md)}: {e}"], []
    problems = []
    results = run_blocks(md, blocks, os.path.join(base, rel(md).replace("/", "_")))
    edits = []
    for b, out, prob in results:
        if prob:
            problems.append(prob)
        if b.out_marker is None:
            continue
        if b.out is None:
            edits.append((b.out_marker + 1, b.out_marker, ["```text", *out.split("\n"), "```"]))
            if check:
                problems.append(f"{rel(md)}:{b.out_marker + 1}: 출력 블록이 없습니다(빌드하세요)")
        else:
            cur = "\n".join(lines[b.out.start + 1:b.out.end])
            if check and COMPARE and not same_output(cur, out):
                problems.append(f"{rel(md)}:{b.out.start + 1}: 출력이 문서와 다릅니다(python docs/build_docs.py)\n"
                                f"--- 문서\n{cur[:600]}\n--- 실행\n{out[:600]}")
            # 시각·소요 시간·말자리처럼 비교에서 같다고 보는 차이만 있으면 그대로 둔다(다시 빌드할 때마다 문서가 바뀌지 않게).
            # 잠긴 판이 아닌 환경(COMPARE 아님)에서는 있는 출력을 바꾸지 않는다 — 문서의 출력은 uv.lock 기준이다.
            if COMPARE and not same_output(cur, out):
                edits.append((b.out.start + 1, b.out.end, out.split("\n")))
    new_text = None
    if edits and not check:
        for start, end, repl in sorted(edits, reverse=True):
            lines[start:end] = repl
        new_text = "\n".join(lines)
        blocks, lines = parse(new_text)        # 출력을 넣은 글 기준으로 내보낸다
    runnable = any(b.lang == "python" and "skip" not in b.flags for b in blocks) and "<!-- no-export -->" not in text
    exports = [(path, fn(md, blocks, lines)) for path, fn in export_targets(md)] if runnable else []
    return new_text, problems, exports


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="문서 예제 실행·검사")
    ap.add_argument("--check", action="store_true", help="다시 쓰지 않고 검사만(어긋나면 종료 코드 1)")
    ap.add_argument("--only", help="경로에 이 글자가 든 문서만")
    ap.add_argument("--no-api", action="store_true", help="공개 API 설명·doctest 검사를 건너뛴다")
    ap.add_argument("--compare", choices=("auto", "yes", "no"), default="auto",
                    help="출력 비교: auto = uv.lock의 numpy·pandas일 때만(기본)")
    a = ap.parse_args(argv)
    global COMPARE
    COMPARE = a.compare == "yes" or (a.compare == "auto" and locked_versions())
    if a.check and not COMPARE:
        print("  (numpy·pandas가 uv.lock과 달라 출력 비교는 건너뛰고 실행만 확인한다)")
    problems = []
    # 예제가 띄우는 하위 프로세스(equion run·check)에는 CI의 인코딩 경고 설정을 넘기지 않는다 — 문서 출력은 사용자가 보는
    # 기본 환경의 출력이다(다른 패키지의 경고가 섞이지 않게).
    os.environ.pop("PYTHONWARNDEFAULTENCODING", None)
    # 작업 기록의 '누가'는 실행 환경(Claude Code 안이면 claude)에 따라 다르다 — 문서 출력은 어디서 만들어도 같게
    os.environ["EQUION_WHO"] = "python"
    base = tempfile.mkdtemp(prefix="eqn-docs-")
    expected_exports = set()
    try:
        files = doc_files(a.only)
        for md in files:
            new_text, probs, exports = process(md, a.check, base)
            problems += probs
            print(f"  {'문제' if probs else '정상'}  {rel(md)}" + (f" ({len(probs)})" if probs else ""))
            if new_text is not None:
                with open(md, "w", encoding="utf-8", newline="\n") as f:
                    f.write(new_text)
            for path, content in exports:
                expected_exports.add(os.path.normpath(path))
                cur = open(path, encoding="utf-8").read() if os.path.exists(path) else None
                if cur != content:
                    if a.check:
                        problems.append(f"{rel(path)}: 문서와 어긋납니다(python docs/build_docs.py)")
                    else:
                        os.makedirs(os.path.dirname(path), exist_ok=True)
                        with open(path, "w", encoding="utf-8", newline="\n") as f:
                            f.write(content)
        if not a.only:
            for sub in list(EXPORT) + ["notebooks"]:
                d = os.path.join(EXAMPLES, sub)
                for n in (os.listdir(d) if os.path.isdir(d) else []):
                    p = os.path.normpath(os.path.join(d, n))
                    if n.endswith((".py", ".ipynb")) and p not in expected_exports:
                        if a.check:
                            problems.append(f"{rel(p)}: 만든 문서가 없는 예제 파일입니다")
                        else:
                            os.remove(p)
            problems += check_links(link_files())
            if not a.no_api:
                problems += check_api()
                problems += run_doctests()
    finally:
        shutil.rmtree(base, ignore_errors=True)
    print(f"\n문서 {len(doc_files(a.only))}개 · 문제 {len(problems)}개")
    for p in problems:
        print("  - " + p.replace("\n", "\n    "))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
