#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""docs/reference/api.md 생성 — 공개 API(함수·클래스·워크파일 객체 메서드·명령줄)를 코드에서 읽어 참조 문서로 만든다.

    python docs/make_api.py          # docs/reference/api.md를 다시 쓴다
    python docs/make_api.py --check  # 코드와 문서가 어긋나면 종료 코드 1(CI)

서명은 매개변수 이름과 기본값만 적는다(형 주석은 Python 버전에 따라 표기가 달라져 빼 둔다).
목록 표의 설명은 docstring의 첫 문단, 상세는 docstring 전체다 — 문서를 고치려면 코드의 docstring을 고친다.

docstring 틀(docs/reference/README.md "docstring 쓰는 법"):

    요약 한 문단.

    (선택) 자세한 설명.

    매개변수
        이름: 뜻
    돌려주는 것
        …
    오류
        ValueError: …
    예
        >>> wf = eqn.datasets.load("toy_q")
        >>> …
    관련: 다른 함수

`public_items()`는 docs/build_docs.py도 쓴다(설명·예제가 빠진 공개 API를 찾고 예제를 doctest로 돌린다).
"""

import argparse
import inspect
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "docs", "reference", "api.md")

# 예제를 요구하지 않는 메서드(보기·직렬화 등 — 쓰임이 뻔한 것)
NO_EXAMPLE = {"show", "output", "to_json", "from_json", "text", "html", "page", "figure", "spec", "graph",
              "cov", "irf_graph", "equation_stats", "table", "ic", "print_version"}
SECTION_WORDS = ("매개변수", "돌려주는 것", "오류", "예", "참고")


def _sig(obj) -> str:
    try:
        sig = inspect.signature(obj)
    except (TypeError, ValueError):
        return "(…)"
    parts = []
    star = False
    for p in sig.parameters.values():
        if p.name in ("self", "cls"):
            continue
        if p.kind == p.VAR_POSITIONAL:
            parts.append(f"*{p.name}")
            star = True
            continue
        if p.kind == p.VAR_KEYWORD:
            parts.append(f"**{p.name}")
            continue
        if p.kind == p.KEYWORD_ONLY and not star:
            parts.append("*")
            star = True
        parts.append(p.name if p.default is p.empty else f"{p.name}={p.default!r}")
    return "(" + ", ".join(parts) + ")"


def _doc(obj) -> str:
    d = inspect.getdoc(obj) or ""
    first = d.strip().split("\n\n")[0]
    return " ".join(line.strip() for line in first.splitlines())


def _groups():
    """[(제목, 접두사, [(이름, 대상)], 예제 요구)] — 참조 문서의 절 순서."""
    import equion as eqn
    from equion import datasets
    from equion.data import transform
    from equion.workfile import objects, output, sysobj, varobj, workfile
    import equion.projects as project

    def members(cls):
        out = []
        for name, val in cls.__dict__.items():
            if name.startswith("_"):
                continue
            if isinstance(val, (classmethod, staticmethod)):
                out.append((name, val.__func__))
            elif isinstance(val, property) or callable(val):
                out.append((name, val))
        return out

    top = [(n, getattr(eqn, n)) for n in eqn.__all__ if not n.startswith("__") and
           not inspect.ismodule(getattr(eqn, n))]
    groups = [
        ("1. `import equion as eqn`", "eqn", [(n, o) for n, o in top if n not in ADVANCED], True),
        ("2. 예제 자료 `eqn.datasets`", "eqn.datasets", [(n, getattr(datasets, n)) for n in datasets.__all__], True),
        ("3. 워크파일 `Workfile`", "Workfile", members(workfile.Workfile), True),
        ("4. 방정식 객체 `wf.equation(…)`", "EquationObject", members(objects.EquationObject), True),
        ("5. 모델 객체 `wf.model(…)`", "ModelObject", members(objects.ModelObject), True),
        ("6. 시나리오 객체 `m.scenario(…)`", "ScenarioObject", members(objects.ScenarioObject), True),
        ("7. 풀이 결과 `SolveResult`", "SolveResult", members(objects.SolveResult), False),
        ("8. 시스템 객체 `wf.system(…)`", "SystemObject", members(sysobj.SystemObject), True),
        ("9. VAR 객체 `wf.var(…)`", "VARObject", members(varobj.VARObject), True),
        ("10. VECM 객체 `wf.vecm(…)`", "VECMObject", members(varobj.VECMObject), True),
        ("11. 오차수정모형 결과 `wf.ecm(…)`", "ECMResult", members(objects.ECMResult), False),
        ("12. 안정성 결과 `m.stability(…)`", "StabilityView", members(objects.StabilityView), False),
        ("13. 기여도 분해 결과 `m.decompose(…)`", "DecompositionView", members(objects.DecompositionView), False),
        ("14. 계절조정 결과 `wf.seas(…)`", "SeasonalResult", members(workfile.SeasonalResult), False),
        ("15. 그래프 객체 `wf.graph(…)`", "GraphObject", members(objects.GraphObject), True),
        ("16. 표 객체 `wf.table(…)`", "TableObject", members(objects.TableObject), True),
        ("17. 그래프 출력 `GraphOutput`", "GraphOutput", members(output.GraphOutput), False),
        ("18. 표 출력 `TableOutput`", "TableOutput", members(output.TableOutput), False),
        ("19. 통계 `eqn.stats`", "eqn.stats",
         [(n, getattr(eqn.stats, n)) for n in eqn.stats.__all__ if not n.isupper()], True),
        ("20. 자료 변환 `equion.data.transform`", "transform",
         [(n, getattr(transform, n)) for n in transform.__all__ if not n.isupper()], True),
        ("21. 프로젝트 `eqn.project(…)`", "Project", members(project.Project), True),
        ("22. 조립 검사 결과 `p.assemble(…)`", "AssemblyReport", members(project.AssemblyReport), False),
        ("23. 항등식 검사 결과 `p.ident(…)`", "IdentityCheck", members(project.IdentityCheck), False),
        ("24. 고급(엔진 수준) — 드라이버·확장용, 바뀔 수 있다", "eqn", [(n, getattr(eqn, n)) for n in ADVANCED], False),
    ]
    return groups


ADVANCED = ("Data", "Equation", "Model", "Scenario", "WorkTable", "Workspace", "current")


def public_items():
    """(정규 이름, 대상, 예제가 필요한지) — 설명·예제 검사와 doctest의 대상."""
    out = []
    for _, prefix, items, need in _groups():
        for name, obj in items:
            target = obj.fget if isinstance(obj, property) else obj
            need_ex = (need and not isinstance(obj, property) and (inspect.isfunction(target) or inspect.ismethod(target))
                       and name not in NO_EXAMPLE)
            out.append((f"{prefix}.{name}", target, need_ex))
    return out


# ---------------------------------------------------------------------------
# docstring → 마크다운
# ---------------------------------------------------------------------------
def _render_doc(doc: str):
    """요약 문단 뒤의 docstring을 마크다운 줄로: 절 머리말은 굵게, '이름: 뜻'은 목록, >>> 예제는 python 블록."""
    paras = doc.strip().split("\n\n")
    lines_out = []
    body = "\n\n".join(paras[1:])
    lines = body.split("\n")
    i = 0
    in_section = False          # 절 머리말 바로 뒤의 들여 쓴 글은 보통 글(코드가 아님)
    while i < len(lines):
        ln = lines[i]
        s = ln.strip()
        if in_section and ln.startswith("    ") and s and not s.startswith(">>>") and \
                not re.match(r"^\s{2,}([A-Za-z_*][\w*.,()\[\] |'\"=-]*?):\s+(.*)$", ln):
            lines_out.append(s + "  ")
            i += 1
            continue
        if not ln.startswith(" ") and s:
            in_section = False
        if s.startswith(">>>"):
            code = []
            while i < len(lines) and lines[i].strip():
                t = lines[i].strip()
                if t.startswith(">>> ") or t == ">>>":
                    code.append(t[4:])
                elif t.startswith("... ") or t == "...":
                    code.append(t[4:])
                else:
                    code.append("# " + t)
                i += 1
            code = [re.sub(r"\s*# doctest:.*$", "", c) for c in code]
            lines_out += ["<!-- skip -->", "```python", *code, "```", ""]
            continue
        if s in SECTION_WORDS or s.startswith("관련:"):
            if s.startswith("관련:"):
                lines_out += [f"**관련** — {s[3:].strip()}", ""]
            else:
                lines_out += [f"**{s}**", ""]
                in_section = s != "예"
            i += 1
            continue
        m = re.match(r"^\s{2,}([A-Za-z_*][\w*.,()\[\] |'\"=-]*?):\s+(.*)$", ln)
        if m and len(m.group(1)) < 40:
            text = m.group(2)
            i += 1
            while i < len(lines) and lines[i].startswith("      ") and lines[i].strip() and \
                    not re.match(r"^\s{2,}[A-Za-z_*][\w*.,()\[\] |'\"=-]*?:\s", lines[i]):
                text += " " + lines[i].strip()
                i += 1
            lines_out.append(f"- `{m.group(1)}`: {text}")
            continue
        if not s:
            if lines_out and lines_out[-1] != "":
                lines_out.append("")
            i += 1
            continue
        if ln.startswith("    "):          # 들여 쓴 글(코드 조각·표)은 그대로
            block = []
            while i < len(lines) and (lines[i].startswith("    ") or not lines[i].strip()) and \
                    not lines[i].strip().startswith(">>>") and lines[i].strip() not in SECTION_WORDS:
                block.append(lines[i][4:] if lines[i].startswith("    ") else "")
                i += 1
            while block and not block[-1].strip():
                block.pop()
            lines_out += ["```text", *block, "```", ""]
            continue
        lines_out.append(s + "  ")
        i += 1
    while lines_out and lines_out[-1] == "":
        lines_out.pop()
    return lines_out


def _anchor(text):
    t = text.strip().lower()
    t = re.sub(r"[^\w\- ]", "", t)
    return t.replace(" ", "-")


def build() -> str:
    import argparse as _ap
    import equion as eqn
    from equion.cli.commands import build_parser

    L = ["# Equion API 참조", "",
         f"Equion {eqn.__version__}의 공개 API — `docs/make_api.py`가 코드의 서명과 docstring에서 만든다(손으로 고치지 말 것). "
         "배우는 순서는 [시작하기](../start/first-model.md)와 [튜토리얼](../tutorial/README.md), 방정식 문법은 "
         "[방정식 문법](../explain/equations.md). 예제의 `eqn`·`np`·`pd`는 `import equion as eqn`·`numpy`·`pandas`다.", "",
         "*English: generated reference of the public API (signatures and docstrings, in Korean). "
         "See [README.en.md](../../README.en.md) and [docs/en](../en/README.md).*", "",
         "## 목차", ""]
    groups = _groups()
    for title, _, _, _ in groups:
        L.append(f"- [{title.replace('`', '')}](#{_anchor(title)})")
    L += ["- [22. 명령줄 `equion`](#22-명령줄-equion)", ""]
    for title, prefix, items, _ in groups:
        L += [f"## {title}", "", "| 이름 | 서명 | 설명 |", "|---|---|---|"]
        detail = []
        for name, obj in items:
            target = obj.fget if isinstance(obj, property) else obj
            kind = "속성" if isinstance(obj, property) else ("클래스" + _sig(obj) if inspect.isclass(obj) else _sig(target))
            full = f"{prefix}.{name}"
            doc = inspect.getdoc(target) or ""
            rest = _render_doc(doc) if doc.strip().count("\n\n") or ">>>" in doc else []
            label = f"[`{name}`](#{_anchor(full)})" if rest else f"`{name}`"
            L.append(f"| {label} | `{kind}` | {_doc(target).replace('|', chr(92) + '|')} |")
            if rest:
                detail += [f"### {full}", "", f"`{name}{kind if not kind.startswith('클래스') else kind[3:]}`" if kind != "속성"
                           else f"`{name}` (속성)", "", _doc(target), "", *rest, ""]
        L += ["", *detail]
    p = build_parser()
    sub = next(a for a in p._actions if isinstance(a, _ap._SubParsersAction))
    L += ["## 22. 명령줄 `equion`", "", "종료 코드: 0 성공 · 1 스크립트 오류 · 2 풀이 실패(`--fail-on`) · 3 입력 오류 · 130 중단(Ctrl+C). "
          "자세한 쓰임은 [명령줄 참조](cli.md).", "", "| 명령 | 옵션 | 설명 |", "|---|---|---|"]
    for name, sp in sub.choices.items():
        h = next((c.help for c in sub._choices_actions if c.dest == name), "") or ""
        opts = " ".join(sorted({o for a in sp._actions for o in a.option_strings if o.startswith("--")}))
        L.append(f"| `{name}` | {opts or '-'} | {h} |")
    return "\n".join(L).rstrip() + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="docs/reference/api.md 생성")
    ap.add_argument("--check", action="store_true", help="다시 만들지 않고, 코드와 어긋나면 1")
    a = ap.parse_args(argv)
    text = build()
    if a.check:
        try:
            with open(OUT, encoding="utf-8") as f:
                cur = f.read()
        except OSError:
            cur = ""
        if cur != text:
            print("docs/reference/api.md가 코드와 다릅니다 — python docs/make_api.py 로 다시 만드세요", file=sys.stderr)
            return 1
        print("docs/reference/api.md 최신")
        return 0
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print(f"→ {OUT} ({len(text.splitlines())}줄)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
