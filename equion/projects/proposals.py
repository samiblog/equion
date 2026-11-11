#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""제안 (K6·D33) — "이렇게 바꾸면 이렇게 된다"를 적용하기 전에 사람이 보게 한다.

    work/proposals/<이름>/
      proposal.json     제목·까닭·만든 때·누가·명령·바꿀 파일과 그때의 해시·미리 계산한 기록·상태(open·applied·dropped)
      proposal.md       사람이 읽는 카드 — 까닭, 바꿀 파일의 차이, 미리 계산한 기록
      changes/<경로>    바뀔 파일의 새 내용(프로젝트 안 같은 상대 경로)

적용은 사람이 시킬 때만(`propose apply`). 만든 뒤 그 파일이 바뀌었으면 '낡음'이라 적용하지 않는다(`--force`면 적용). 적용·버림 모두
제안 기록에 남고, 적용은 바뀜 기록에도 "제안 p2 적용"으로 남는다. 버린 제안도 지우지 않는다.
"""

import difflib
import hashlib
import json
import os
import re
import shutil
from dataclasses import dataclass
from typing import Dict, List, Optional

from ..work.store import WORK_DIR, WHO_KO, dumps, move_into_place, now_iso
from .config import ProjectError
from .records import ADOPTED, _who, history_of, replace_line, store_of

PROP_DIR = os.path.join(WORK_DIR, "proposals")
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_\-]*$")
STATUS_KO = {"open": "열림", "applied": "적용", "dropped": "버림"}


def _sha_bytes(b: Optional[bytes]) -> Optional[str]:
    return None if b is None else hashlib.sha256(b).hexdigest()


def _read(path) -> Optional[bytes]:
    try:
        with open(path, "rb") as f:
            return f.read()
    except FileNotFoundError:
        return None


@dataclass
class Proposal:
    """제안 하나 — `.id`(prop:…) · `.meta`(proposal.json) · `.stale`(만든 뒤 바뀐 파일) · `.diff()` · `.text()`."""

    root: str
    name: str
    meta: dict

    @property
    def id(self) -> str:
        """제안 이름 prop:…"""
        return f"prop:{self.name}"

    @property
    def path(self) -> str:
        """제안 폴더."""
        return os.path.join(self.root, PROP_DIR, self.name)

    @property
    def status(self) -> str:
        """open · applied · dropped."""
        return self.meta["status"]

    def new_content(self, rel: str) -> Optional[bytes]:
        """바뀔 파일의 새 내용(지우는 파일이면 None)."""
        if self.meta["files"][rel].get("delete"):
            return None
        return _read(os.path.join(self.path, "changes", rel))

    @property
    def stale(self) -> List[str]:
        """만든 뒤 지금 내용이 바뀐 파일(적용하면 그 바뀜을 덮는다)."""
        out = []
        for rel, v in self.meta["files"].items():
            if _sha_bytes(_read(os.path.join(self.root, rel))) != v["base"]:
                out.append(rel)
        return out

    def diff(self) -> str:
        """지금 파일 대비 바뀔 내용의 차이(unified diff)."""
        out = []
        for rel in self.meta["files"]:
            a = (_read(os.path.join(self.root, rel)) or b"").decode("utf-8", "replace").splitlines(keepends=True)
            b = (self.new_content(rel) or b"").decode("utf-8", "replace").splitlines(keepends=True)
            out.append("".join(difflib.unified_diff(a, b, f"a/{rel}", f"b/{rel}")))
        return "\n".join(x for x in out if x)

    def text(self) -> str:
        """명령줄에 보이는 짧은 글."""
        m = self.meta
        L = [f"[{self.id}] {m['title']} · {STATUS_KO[m['status']]} · {m['created']} · {WHO_KO.get(m['who'], m['who'])}"]
        if m.get("why"):
            L.append(f"  까닭   {m['why']}")
        L.append("  바꿀 파일  " + " · ".join(m["files"]))
        if m.get("parts"):
            L.append("  식     " + " · ".join(f"{k} ← {v}" for k, v in m["parts"].items()))
        if m.get("previews"):
            L.append("  미리 계산  " + " · ".join(m["previews"]))
        st = self.stale if m["status"] == "open" else []
        if st:
            L.append(f"  ! 낡음 — 만든 뒤 바뀐 파일: {', '.join(st)} (적용 전에 다시 견주세요 · --force)")
        if m.get("decided"):
            d = m["decided"]
            L.append(f"  {STATUS_KO[m['status']]}   {d['at']} · {WHO_KO.get(d['who'], d['who'])}" + (f" · {d['note']}" if d.get("note") else "")
                     + (f" · 바뀜 기록 {d['change']}" if d.get("change") else ""))
        return "\n".join(L)

    def to_dict(self) -> dict:
        """명령줄 --json과 같은 사전."""
        d = dict(self.meta)
        d["id"] = self.id
        d["stale"] = self.stale if self.status == "open" else []
        return d


def _dir(p):
    return os.path.join(p.root, PROP_DIR)


def _names(p) -> List[str]:
    d = _dir(p)
    if not os.path.isdir(d):
        return []
    return sorted((n for n in os.listdir(d) if os.path.isfile(os.path.join(d, n, "proposal.json"))),
                  key=lambda n: (int(n[1:]) if n[:1] == "p" and n[1:].isdigit() else 10 ** 9, n))


def _save(prop: Proposal):
    with open(os.path.join(prop.path, "proposal.json"), "w", encoding="utf-8", newline="\n") as f:
        f.write(dumps(prop.meta))
    with open(os.path.join(prop.path, "proposal.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write(_card(prop))


def _card(prop: Proposal) -> str:
    from ..reporting import markdown as md
    m = prop.meta
    head = [("제목", m["title"]), ("상태", STATUS_KO[m["status"]]), ("만든 때", m["created"]),
            ("누가", WHO_KO.get(m["who"], m["who"])), ("명령", m.get("command"))]
    secs = [("까닭", m.get("why") or "(적지 않음)")]
    if m.get("parts"):
        secs.append(("식", md.bullets([f"{k} ← {v}" for k, v in m["parts"].items()])))
    secs.append(("바꿀 내용", "```diff\n" + (prop.diff().rstrip() or "(차이 없음)") + "\n```"))
    if m.get("previews"):
        secs.append(("미리 계산한 기록", md.bullets([f"{x} — work/{x.split(':')[0]}/{x.split(':')[1]}/summary.md"
                                                   for x in m["previews"]])))
    if m.get("decided"):
        d = m["decided"]
        secs.append((STATUS_KO[m["status"]], f"{d['at']} · {WHO_KO.get(d['who'], d['who'])}" + (f" — {d['note']}" if d.get("note") else "")))
    return md.card(f"제안 {prop.id}", head, secs)


def get(p, name: str) -> Proposal:
    """제안 하나(prop:p2 또는 p2)."""
    n = name.split(":", 1)[1] if name.startswith("prop:") else name
    f = os.path.join(_dir(p), n, "proposal.json")
    if not os.path.isfile(f):
        raise ProjectError(f"없는 제안 {name} (있는 것: {', '.join('prop:' + x for x in _names(p)[-8:]) or '없음'})")
    with open(f, encoding="utf-8") as fh:
        return Proposal(p.root, n, json.load(fh))


def proposals(p) -> List[Proposal]:
    """제안 목록(만든 순)."""
    return [get(p, n) for n in _names(p)]


def _part_line(p, pid: str, text: str, new: Dict[str, str]):
    pt = p.part(pid)
    if pt.kind != "equation":
        raise ProjectError(f"{pt.id}는 항등식입니다 — --part는 추정식만(항등식은 --file로)")
    cur = new.get(pt.file)
    if cur is None:
        with open(os.path.join(p.root, pt.file), encoding="utf-8-sig") as f:
            cur = f.read()
    lines = cur.split("\n")
    lines[pt.line - 1] = replace_line(lines[pt.line - 1], text)
    new[pt.file] = "\n".join(lines)
    return pt


def new(p, name: str = None, title: str = "", why: str = "", parts: Dict[str, str] = None, files: Dict[str, str] = None,
        previews: List[str] = (), who: str = None, command: str = None) -> Proposal:
    """제안을 만든다 — parts {부품: est:기록(그 식 + 채택) 또는 식 글자}, files {경로: 새 내용 파일}. 파일은 바꾸지 않는다."""
    import tomlkit
    parts, files = dict(parts or {}), dict(files or {})
    if not parts and not files:
        raise ProjectError("바꿀 것이 없습니다 — --part 부품=est:기록|식 또는 --file 경로=새파일")
    store = store_of(p)
    for x in previews:
        store.get(x)
    names = _names(p)
    if name:
        if not NAME_RE.match(name):
            raise ProjectError(f"제안 이름은 영문·숫자로 시작하고 영문·숫자·_·-만: {name!r}")
        if name in names:
            raise ProjectError(f"이미 있는 제안 prop:{name}")
    else:
        nums = [int(n[1:]) for n in names if n[:1] == "p" and n[1:].isdigit()]
        name = f"p{(max(nums) if nums else 0) + 1}"
    new_text: Dict[str, str] = {}
    adopt_set, adopt_drop, shown = {}, [], {}
    for pid, v in parts.items():
        v = str(v).strip()
        if v.startswith("est:"):
            rec = store.get(v, "est")
            pt = p.part(pid)
            if rec.meta["target"] != pt.target:
                raise ProjectError(f"--part {pt.id}: {v}의 목표는 {rec.meta['target']}입니다")
            _part_line(p, pt.id, rec.meta["text"], new_text)
            adopt_set[pt.id] = v
            shown[pt.id] = v
        else:
            pt = _part_line(p, pid, v, new_text)
            if pt.id in p.adopted:
                adopt_drop.append(pt.id)
            shown[pt.id] = f'"{v}"'
    if adopt_set or adopt_drop:
        apath = os.path.join(p.root, ADOPTED)
        if os.path.isfile(apath):
            with open(apath, encoding="utf-8") as f:
                doc = tomlkit.parse(f.read())
        else:
            doc = tomlkit.document()
            doc.add(tomlkit.comment("채택표 — 식(부품)마다 채택한 추정 기록. 모형은 이 계수로 푼다(equion adopt가 고친다)"))
        for k, v in adopt_set.items():
            doc[k] = v
        for k in adopt_drop:
            if k in doc:
                del doc[k]
        new_text[ADOPTED] = tomlkit.dumps(doc)
    for rel, src in files.items():
        rel = rel.replace(os.sep, "/").lstrip("/")
        if ".." in rel.split("/") or os.path.isabs(rel):
            raise ProjectError(f"--file 경로는 프로젝트 안의 상대 경로: {rel!r}")
        if not os.path.isfile(src):
            raise ProjectError(f"--file {rel}: 새 내용 파일이 없습니다 — {src}")
        with open(src, encoding="utf-8-sig") as f:
            new_text[rel] = f.read()
    d = os.path.join(_dir(p), name)
    tmp = d + ".tmp"
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(os.path.join(tmp, "changes"))
    meta_files = {}
    for rel, text in new_text.items():
        cur = _read(os.path.join(p.root, rel))
        meta_files[rel] = {"base": _sha_bytes(cur), "new": _sha_bytes(text.encode("utf-8")), "added": cur is None}
        out = os.path.join(tmp, "changes", rel)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
    meta = {"format": "equion-proposal", "format_version": 1, "name": name, "title": title or f"제안 {name}",
            "why": why, "created": now_iso(), "who": _who(who), "command": command, "status": "open",
            "files": meta_files, "parts": shown, "previews": list(previews), "decided": None}
    with open(os.path.join(tmp, "proposal.json"), "w", encoding="utf-8", newline="\n") as f:
        f.write(dumps(meta))
    move_into_place(tmp, d)          # 폴더 감시(Desk·백신·색인)가 잠깐 쥐고 있어도 기다렸다 옮긴다
    prop = Proposal(p.root, name, meta)
    _save(prop)
    return prop


def apply(p, name: str, force: bool = False, who: str = None, command: str = None) -> Proposal:
    """제안을 적용한다 — 바꿀 파일을 새 내용으로 쓰고 바뀜 기록에 "제안 … 적용"으로. 낡은 제안은 force일 때만."""
    prop = get(p, name)
    if prop.status != "open":
        raise ProjectError(f"{prop.id}는 이미 {STATUS_KO[prop.status]} — 열린 제안만 적용합니다")
    st = prop.stale
    if st and not force:
        raise ProjectError(f"{prop.id}가 낡았습니다 — 만든 뒤 바뀐 파일: {', '.join(st)} (차이를 다시 보고 --force로 적용)")
    files = {rel: prop.new_content(rel) for rel in prop.meta["files"]}
    ch = history_of(p).write_files(files, _who(who), command or f"propose apply {prop.name}",
                                   note=f"제안 {prop.id} 적용: {prop.meta['title']}")
    prop.meta["status"] = "applied"
    prop.meta["decided"] = {"at": now_iso(), "who": _who(who), "note": "낡은 채로 적용(--force)" if st else "",
                            "change": ch.id if ch else None}
    _save(prop)
    p._reset()
    return prop


def drop(p, name: str, why: str = "", who: str = None) -> Proposal:
    """제안을 버린다(지우지 않는다 — 제안 기록은 남는다)."""
    prop = get(p, name)
    if prop.status != "open":
        raise ProjectError(f"{prop.id}는 이미 {STATUS_KO[prop.status]}")
    prop.meta["status"] = "dropped"
    prop.meta["decided"] = {"at": now_iso(), "who": _who(who), "note": why, "change": None}
    _save(prop)
    return prop
