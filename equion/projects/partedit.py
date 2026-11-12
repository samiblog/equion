#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""블록 파일의 식 한 줄 더하기·빼기 (D51) — `Project.part_add` · `part_remove`, 명령 `equion block add·remove`.

블록 파일은 사람이 쓰는 글이다. 여기서는 끝에 한 줄을 더하거나 그 줄 하나를 뺄 뿐이고(다른 줄·주석은 그대로), 쓰기 전에 식 문법과
'한 블록에 목표 하나'를 본다. `from_part`를 주면 그 식을 옮긴다(모형에 안 든 블록의 개별 식 → 모형의 블록) — 두 파일이 바뀜 기록 하나에 남는다.
채택표(EQUATIONS/adopted.toml)의 그 부품 줄은 식을 뺄 때 함께 지운다(옮긴 식은 새 자리에서 다시 추정·채택).
"""

import os
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from ..data.io import read_text
from ..formula.ast_formula import _DEF_RE, expand_macros
from ..formula.parser import DSLError
from .config import ProjectError
from ..workfile.runtime import quiet
from .parts import parse_line

ADOPTED = "EQUATIONS/adopted.toml"


@dataclass
class PartChange:
    """식 더하기·빼기 결과 — `.action`(add·remove) · `.part`(블록:목표) · `.files` · `.change`(바뀜 기록) · `.moved_from`."""

    action: str
    part: str
    files: List[str] = field(default_factory=list)
    change: Optional[str] = None
    moved_from: Optional[str] = None
    text: str = ""

    def summary(self) -> str:
        """명령줄에 보이는 짧은 글."""
        if self.action == "add":
            head = f"[block add] {self.part}" + (f" ← {self.moved_from}에서 옮김" if self.moved_from else "") + f"  {self.text}"
        else:
            head = f"[block remove] {self.part}"
        L = [head] + [f"  파일   {f}" for f in self.files]
        if self.change:
            L.append(f"  바뀜 기록  {self.change}")
        if self.action == "add":
            L.append(f"  다음   equion est {self.part} · equion assemble <모형>" + (" — 채택은 옮기지 않는다(새 자리에서 다시 채택)" if self.moved_from else ""))
        return "\n".join(L)

    def to_dict(self) -> dict:
        """명령줄 --json과 같은 사전."""
        return {"action": self.action, "part": self.part, "files": self.files, "change": self.change, "moved_from": self.moved_from,
                "text": self.text}


def _rel(p, path: str) -> str:
    return os.path.relpath(path, p.root).replace(os.sep, "/")


def add_text(p, block: str, text: str, desc: str = None) -> Tuple[str, str, str, str]:
    """블록 파일 끝에 식 한 줄을 더한 **새 내용** — (새 내용, 부품 이름, 파일(프로젝트 기준), 적힐 줄). 파일은 쓰지 않는다.
    없는 블록 · 여러 줄 · 문법 오류 · 그 블록에 같은 목표가 이미 있음은 ProjectError."""
    spec = p.config.blocks.get(block)
    if spec is None:
        raise ProjectError(f"없는 블록 {block!r} (있는 블록: {', '.join(p.config.blocks) or '없음'}) — 먼저 equion block define {block}")
    body = str(text or "").strip()
    if "\n" in body or "\r" in body:
        raise ProjectError("식은 한 줄만 — 여러 식은 하나씩 더한다")
    if "#" in body:
        body, _, note = body.partition("#")
        body = body.strip()
        desc = desc if desc is not None else note.strip()
    if not body:
        raise ProjectError("식이 비었습니다")
    cur = read_text(spec.path) if os.path.isfile(spec.path) else ""
    defs = [ln.split("#", 1)[0].strip() for ln in cur.splitlines() if _DEF_RE.match(ln.split("#", 1)[0].strip())]
    expr = expand_macros(defs + [body])[-1] if defs else body
    try:
        info = quiet(parse_line, expr, p.workfile._data)
    except (DSLError, ValueError, KeyError) as e:
        raise ProjectError(f"식을 읽지 못했습니다: {e.args[0] if isinstance(e, KeyError) else e} — {body}") from None
    target = info["target"]
    for q in p.parts(block):
        if q.target.upper() == str(target).upper():
            raise ProjectError(f"블록 {block}에 이미 목표 {q.target}의 식이 있습니다({q.where}: {q.text}) — 한 블록에 목표 하나")
    line = body + (f"   # {desc}" if desc else "")
    new = cur + ("" if cur.endswith("\n") or not cur else "\n") + line + "\n"
    return new, f"{block}:{target}", spec.file.replace("\\", "/"), line


def remove_text(p, part: str) -> Tuple[str, str, str]:
    """블록 파일에서 그 부품의 줄을 뺀 **새 내용** — (새 내용, 파일, 부품 이름). 없는 부품은 ProjectError."""
    try:
        pt = p.part(part)
    except KeyError as e:
        raise ProjectError(str(e.args[0]) if e.args else f"없는 부품 {part}") from None
    spec = p.config.blocks[pt.block]
    lines = read_text(spec.path).splitlines(keepends=True)
    k = pt.line - 1
    if not (0 <= k < len(lines)) or lines[k].split("#", 1)[0].strip() != pt.text:
        raise ProjectError(f"{pt.where}의 줄이 읽은 식과 다릅니다 — 파일이 그사이 바뀌었으면 다시 시도하세요")
    del lines[k]
    return "".join(lines), spec.file.replace("\\", "/"), pt.id


def adopted_without(p, part: str) -> Optional[str]:
    """채택표에서 그 부품 줄을 지운 새 내용(그 줄이 없으면 None)."""
    import tomlkit
    path = os.path.join(p.root, *ADOPTED.split("/"))
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as f:
        doc = tomlkit.parse(f.read())
    keys = [k for k in doc if str(k).lower() == part.lower()]
    if not keys:
        return None
    for k in keys:
        del doc[k]
    return tomlkit.dumps(doc)
