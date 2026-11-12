#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Claude(AI)에게 주는 안내 — 모형 작업 안내 `help/guide.md`(기획의 help/claude.md)와 Claude Code 스킬 초안 `help/skill/SKILL.md` (DESK §7, E6).

    equion guide                       안내를 보인다(등록부의 분석·명령 표는 지금 코드에서)
    equion guide --path                안내 파일의 경로 — "이 파일을 읽어"라고 Claude에게
    equion guide skill                 스킬 초안을 보인다
    equion guide skill --install user  ~/.claude/skills/equion/SKILL.md에 쓴다(project면 <프로젝트>/.claude/skills/equion/)

안내의 표 몇 개(`<!-- equion:auto 이름 -->` … `<!-- /equion:auto -->`)는 등록부·명령줄에서 만든다. 파일에 든 표가 코드와 같은지는
`python docs/make_api.py --check`가 본다(CI).
"""

import os
import re
from typing import Dict, List

HERE = os.path.dirname(os.path.abspath(__file__))
GUIDE = os.path.join(HERE, "guide.md")        # claude.md가 아니다 — 대소문자를 가리지 않는 OS에서 CLAUDE.md(지시 파일)로 읽힌다
SKILL = os.path.join(HERE, "skill", "SKILL.md")
AUTO = re.compile(r"(<!-- equion:auto (\w+) -->\n)(.*?)(<!-- /equion:auto -->)", re.S)


def _cell(s) -> str:
    return str(s).replace("|", "\\|").replace("\n", " ")


def _commands() -> str:
    """명령줄의 명령 표(이름 — 도움말) — 하위 동작이 있으면 함께."""
    import argparse
    from ..cli.commands import build_parser
    p = build_parser()
    sub = next(a for a in p._actions if isinstance(a, argparse._SubParsersAction))
    helps = {a.dest: a.help for a in sub._choices_actions}
    rows = ["| 명령 | 하는 일 | 동작 |", "|---|---|---|"]
    for name, sp in sub.choices.items():
        acts = ""
        inner = [a for a in sp._actions if isinstance(a, argparse._SubParsersAction)]
        if inner and name != "an":
            acts = " · ".join(inner[0].choices)
        elif name == "an":
            acts = "list · keep · <분석>(아래 표)"
        rows.append(f"| `{name}` | {_cell(helps.get(name, ''))} | {acts} |")
    return "\n".join(rows)


def _analyses() -> str:
    from .. import registry as reg
    rows = ["| 분석 | 이름 | 대상 | 만드는 것 | 결과 |", "|---|---|---|---|---|"]
    for r in reg.table():
        rows.append(f"| `{r['분석']}` | {_cell(r['이름'])} | {_cell(r['대상'])} | {_cell(r['만드는 것'])} | {_cell(r['결과'])} |")
    return "\n".join(rows)


def _allowed() -> str:
    from .. import registry as reg
    note = sorted({" ".join(x for x in k if x) for k in reg.COMMANDS})
    script = sorted({" ".join(x for x in k if x) for k in (*reg.COMMANDS, *reg.SCRIPT_COMMANDS)} - set(note))
    return ("| 어디서 | 부를 수 있는 명령 |\n|---|---|\n"
            f"| 노트의 ```` ```equion ```` 블록 | {' · '.join(f'`{x}`' for x in note)} — 정의 파일을 바꾸는 줄(`est --adopt`·`an keep`)은 안 된다 |\n"
            f"| 스크립트 `.eqs` | 노트의 것 + {' · '.join(f'`{x}`' for x in script)} |")


def auto_sections() -> Dict[str, str]:
    """안내에 끼우는 표 {이름: md} — 등록부·명령줄에서."""
    return {"commands": _commands(), "analyses": _analyses(), "allowed": _allowed()}


def fill(text: str) -> str:
    """`<!-- equion:auto 이름 -->` 구역을 지금 코드의 표로 바꾼다(모르는 이름은 그대로)."""
    secs = auto_sections()
    return AUTO.sub(lambda m: m[1] + secs[m[2]] + "\n" + m[4] if m[2] in secs else m[0], text)


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def guide_text() -> str:
    """AI용 모형 작업 안내(표는 지금 코드에서).

    예
        >>> t = eqn.help.guide_text()
        >>> t.splitlines()[0]
        '# Equion — Claude를 위한 모형 작업 안내'
    """
    return fill(_read(GUIDE))


def skill_text() -> str:
    """Claude Code 스킬 초안(SKILL.md — 앞머리 name: equion).

    예
        >>> eqn.help.skill_text().splitlines()[1]
        'name: equion'
    """
    return fill(_read(SKILL))


def install_skill(where: str = "user", project: str = ".", force: bool = False) -> str:
    """스킬을 Claude Code의 스킬 폴더에 쓴다 → 쓴 경로. where: 'user'(~/.claude/skills/equion/) · 'project'(<프로젝트>/.claude/skills/equion/ —
    프로젝트는 project 폴더에서 위로 올라가며 equion.toml이 있는 곳, 없으면 project 폴더 그대로).
    이미 다른 내용이 있으면 force일 때만 덮는다(FileExistsError). 사람이 시킬 때만 쓴다."""
    if where == "user":
        base = os.path.join(os.path.expanduser("~"), ".claude", "skills", "equion")
    elif where == "project":
        from ..projects.config import ProjectError, find_config
        try:
            top = os.path.dirname(find_config(project))   # 프로젝트의 하위 폴더(EQUATIONS/ 등)에서 쳐도 프로젝트 폴더에
        except ProjectError:
            top = os.path.abspath(project)
        base = os.path.join(top, ".claude", "skills", "equion")
    else:
        raise ValueError(f"where는 user · project입니다: {where!r}")
    dst = os.path.join(base, "SKILL.md")
    text = skill_text()
    if os.path.isfile(dst) and _read(dst) != text and not force:
        raise FileExistsError(f"이미 다른 스킬이 있습니다: {dst} — 덮으려면 --force")
    os.makedirs(base, exist_ok=True)
    with open(dst, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    return dst


def sync(check: bool = False) -> List[str]:
    """패키지의 안내 파일들의 자동 표를 지금 코드로 — 바뀐(check면 바뀔) 파일 목록."""
    out = []
    for path in (GUIDE, SKILL):
        old = _read(path)
        new = fill(old)
        if new != old:
            out.append(path)
            if not check:
                with open(path, "w", encoding="utf-8", newline="\n") as f:
                    f.write(new)
    return out


__all__ = ["guide_text", "skill_text", "install_skill", "fill", "auto_sections", "sync", "GUIDE", "SKILL"]
