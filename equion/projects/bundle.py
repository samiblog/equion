"""프로젝트 묶어 보내기 · 묶음 열기 (D61) — 다른 PC로 프로젝트를 zip 하나로 옮긴다.

묶음에 드는 것:
    정의       equion.toml · EQUATIONS/ · DATA/series.toml·derived.txt · ASSUMPTIONS/ · ADDFACTORS/ · SCENARIOS/ · VIEWS/ · FLOWS/
    글         notes/ · reports/(+ 보고서 자료 폴더) · CLAUDE.md · README.md · .gitignore
    자료       지금 자료 회차(work/data/<회차>/) — 원자료 없이도 같은 값으로 이어 한다(자료 파일 하나 프로젝트는 그 파일).
               넣는 기록·이정표가 쓰는 다른 회차도 함께 — 받은 쪽에서 그 기록을 그대로 다시 풀 수 있게
    기록       남길 기록 — 채택·고정·다른 기록이나 노트·보고서가 가리키는 것(records="keep", 기본) · 모두("all") · 없음("none")
    원자료     DATA/raw/(받은 상자 inbox 는 빼고) — raw=True일 때만(기본은 넣지 않는다 — 묶을 때마다 고른다, Q20)
    이정표     work/milestones/ — 있으면 늘
    bundle.json  묶음 명세(format "equion-bundle") — 무엇이 들었고 무엇을 뺐나

바뀜 기록(work/history)과 Desk의 화면 상태는 넣지 않는다 — 그 PC의 것이다. 묶음 열기는 빈 폴더(또는 없는 폴더)에 풀고,
zip 안의 경로가 그 폴더 밖을 가리키면 거절한다.
"""
from __future__ import annotations

import json
import os
import zipfile
from dataclasses import dataclass, field
from typing import List, Optional

from ..work.store import now_iso
from .config import ProjectError

FORMAT = "equion-bundle"
FORMAT_VERSION = 1
TEXT_DIRS = ("EQUATIONS", "ASSUMPTIONS", "ADDFACTORS", "SCENARIOS", "VIEWS", "FLOWS", "notes", "reports")
TOP_FILES = ("equion.toml", "CLAUDE.md", "README.md", ".gitignore")
MAX_FILES = 200_000
MAX_BYTES = 4 * 1024 ** 3


@dataclass
class BundleResult:
    """묶어 보내기 결과 — `.path`(zip) · `.files` · `.bytes` · `.records` · `.raw` · `.vintage`."""

    path: str
    files: int
    bytes: int
    records: List[str] = field(default_factory=list)
    raw: bool = False
    vintage: Optional[str] = None
    left_out: List[str] = field(default_factory=list)
    vintages: List[str] = field(default_factory=list)

    def text(self) -> str:
        """명령줄에 보이는 짧은 글."""
        size = f"{self.bytes / 1024 / 1024:.1f}MB" if self.bytes >= 1024 * 1024 else f"{max(1, round(self.bytes / 1024))}KB"
        return (f"[bundle make] {self.path} — 파일 {self.files} · {size}"
                + f"\n  자료 회차 {self.vintage or '(자료 파일)'} · 기록 {len(self.records)} · 원자료 {'넣음' if self.raw else '넣지 않음'}"
                + (f"\n  기록이 쓰는 회차  {', '.join(v for v in self.vintages if v != self.vintage)}"
                   if any(v != self.vintage for v in self.vintages) else "")
                + "".join(f"\n  뺀 것   {x}" for x in self.left_out)
                + "\n  받은 쪽  equion bundle open 묶음.zip 폴더")

    def to_dict(self) -> dict:
        """명령줄 --json과 같은 사전."""
        return {"path": self.path, "files": self.files, "bytes": self.bytes, "records": self.records, "raw": self.raw,
                "vintage": self.vintage, "vintages": self.vintages, "left_out": self.left_out}


def _walk(root: str, rel: str):
    base = os.path.join(root, rel)
    if os.path.isfile(base):
        yield rel.replace(os.sep, "/")
        return
    for dirpath, dirnames, files in os.walk(base):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith(".") and d != "__pycache__")
        for f in sorted(files):
            if f.endswith((".tmp-equion", ".pyc")):
                continue
            yield os.path.relpath(os.path.join(dirpath, f), root).replace(os.sep, "/")


def _kept_records(p) -> set:
    """남길 기록 — 정리(`work clean`)에서 빠지는 것과 같은 규칙(채택·고정·다른 기록·노트·보고서·이정표가 가리키는 것)."""
    from ..cli.workcmds import _referenced
    from .records import store_of
    return set(_referenced(p, store_of(p)))


def make(p, out: str = None, raw: bool = False, records: str = "keep", who: str = None) -> BundleResult:
    """프로젝트를 zip 하나로 묶는다. out이 없으면 exports/<프로젝트>_<날짜>.zip."""
    from .records import store_of
    if records not in ("keep", "all", "none"):
        raise ProjectError(f"records = {records!r} — keep(남길 기록) · all(모두) · none(없음)")
    root = p.root
    stamp = now_iso()[:10]
    top = _safe_top(p.name)
    if out and os.path.isdir(out):
        out = os.path.join(out, f"{top}_{stamp}.zip")
    path = os.path.abspath(out or os.path.join(root, "exports", f"{top}_{stamp}.zip"))
    if not out:                                      # 같은 날 다시 묶으면 _2 · _3 — 앞 묶음을 덮지 않는다
        k = 2
        while os.path.exists(path):
            path = os.path.abspath(os.path.join(root, "exports", f"{top}_{stamp}_{k}.zip"))
            k += 1
    if _inside(path, os.path.join(os.path.abspath(root), "work")):
        raise ProjectError("묶음을 work/ 안에 둘 수 없습니다 — exports/ 나 다른 폴더에")
    names: List[str] = []
    for rel in TOP_FILES:
        if os.path.isfile(os.path.join(root, rel)):
            names.append(rel)
    for d in TEXT_DIRS:
        if os.path.isdir(os.path.join(root, d)):
            names += list(_walk(root, d))
    cfg = p.config
    from .records import definition_files
    names += definition_files(p)                     # equion.toml이 가리키는 다른 자리의 블록·자료 정의·판단 값 파일까지
    left_out: List[str] = []
    store = store_of(p)
    kept: List[str] = []
    if records != "none":
        want = None if records == "all" else _kept_records(p)
        kept = [r.id for r in store.records() if r.kind != "data" and (want is None or r.id in want)]
    vintages: List[str] = []
    if cfg.series_file:
        from . import milestones
        if p.vintage and not os.path.isdir(os.path.join(root, "work", "data", p.vintage)):
            raise ProjectError(f"지금 자료 회차 {p.vintage}의 폴더가 없습니다 — equion data build 로 다시 만든 뒤 묶으세요")
        wanted = [p.vintage] if p.vintage else []
        for rid in kept:
            ds = (store.get(rid).meta or {}).get("data") or {}
            if ds.get("kind") == "vintage" and ds.get("id"):
                wanted.append(ds["id"])
        wanted += [m.vintage for m in milestones.list_all(p) if m.vintage]
        missing = []
        for vid in dict.fromkeys(wanted):
            if os.path.isdir(os.path.join(root, "work", "data", vid)):
                vintages.append(vid)
                names += list(_walk(root, os.path.join("work", "data", vid)))
            else:
                missing.append(vid)
        if missing:
            left_out.append(f"자료 회차 {', '.join(missing)} — 이 프로젝트에도 없어(정리됨) 그 회차를 쓰는 기록은 받은 쪽에서 다시 풀 수 없다")
    elif cfg.data_file and os.path.isfile(os.path.join(root, cfg.data_file)):
        names.append(cfg.data_file.replace(os.sep, "/"))
    if raw:
        names += [n for n in _walk(root, os.path.join("DATA", "raw")) if "/inbox/" not in n]
    elif os.path.isdir(os.path.join(root, "DATA", "raw")):
        left_out.append("원자료 DATA/raw/ — 받은 쪽은 지금 자료 회차로 이어 한다(자료를 다시 만들려면 원자료를 따로 넣는다)")
    if os.path.isdir(os.path.join(root, FOLDER_MS)):
        names += list(_walk(root, FOLDER_MS))
    for rid in kept:
        kind, name = rid.split(":", 1)
        names += list(_walk(root, os.path.join("work", kind, name)))
    if records != "all":
        left_out.append(f"기록 — {'남길 것만' if records == 'keep' else '넣지 않음'}(모두 {len(store.records())}개 가운데 {len(kept)}개)")
    left_out.append("바뀜 기록 work/history · Desk 화면 상태 — 그 PC의 것")
    seen, total = set(), 0
    names = [n for n in names if not (n in seen or seen.add(n))]
    if len(names) > MAX_FILES:
        raise ProjectError(f"파일이 너무 많습니다({len(names)}) — records='keep'으로 줄이세요")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp-equion"
    log_lines = []
    log_path = os.path.join(root, "work", "log.jsonl")
    if os.path.isfile(log_path):
        keep_ids = set(kept) | {f"data:{v}" for v in vintages}
        with open(log_path, encoding="utf-8") as f:
            for line in f:
                try:
                    if json.loads(line).get("id") in keep_ids:
                        log_lines.append(line.rstrip("\n"))
                except ValueError:
                    continue
    marks = {k: v for k, v in store.marks().items() if k in set(kept)}
    manifest = {"format": FORMAT, "format_version": FORMAT_VERSION, "project": p.name, "created": now_iso(), "who": who or "python",
                "equion": _version(), "vintage": p.vintage, "vintages": vintages, "raw": bool(raw), "records": kept, "files": len(names) + 1,
                "left_out": left_out}
    try:
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
            for n in names:
                full = os.path.join(root, *n.split("/"))
                total += os.path.getsize(full)
                if total > MAX_BYTES:
                    raise ProjectError("묶음이 4GB를 넘습니다 — 원자료나 기록을 빼세요")
                z.write(full, f"{top}/{n}")
            if log_lines:
                z.writestr(f"{top}/work/log.jsonl", "\n".join(log_lines) + "\n")
            if marks:
                z.writestr(f"{top}/work/marks.json", json.dumps(marks, ensure_ascii=False, indent=2))
            z.writestr(f"{top}/bundle.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
    rel = os.path.relpath(path, root).replace(os.sep, "/") if _inside(path, os.path.abspath(root)) else path
    return BundleResult(rel, len(names) + 1, os.path.getsize(path), kept, bool(raw), p.vintage, left_out, vintages)


FOLDER_MS = os.path.join("work", "milestones")


def _inside(path: str, folder: str) -> bool:
    """path가 folder 안(또는 그 자체)인가 — 이름의 앞부분만 같은 다른 폴더(workshop)는 아니다."""
    try:
        return os.path.commonpath([os.path.normcase(os.path.abspath(path)), os.path.normcase(os.path.abspath(folder))]) \
            == os.path.normcase(os.path.abspath(folder))
    except ValueError:
        return False


def _safe_top(name: str) -> str:
    """zip의 맨 위 폴더 이름 — 경로 글자(/ \\ : 등)는 _로."""
    import re
    t = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", str(name or "project")).strip(" .") or "project"
    return t[:80]


def _version() -> str:
    from ..version import project_version
    return project_version()


def open_bundle(zip_path: str, dest: str) -> dict:
    """묶음을 dest 폴더(없거나 비어 있어야 한다)에 푼다 — zip 안의 경로가 dest 밖을 가리키면 거절. 돌려주는 것: 명세와 푼 폴더."""
    if not os.path.isfile(zip_path):
        raise ProjectError(f"묶음 파일이 없습니다: {zip_path}")
    dest = os.path.abspath(dest)
    if os.path.exists(dest) and (not os.path.isdir(dest) or os.listdir(dest)):
        raise ProjectError(f"빈 폴더에만 풉니다 — {dest}에 이미 파일이 있습니다")
    made = not os.path.exists(dest)
    try:
        return _open(zip_path, dest)
    except BaseException as e:
        # 반쯤 푼 것은 지운다 — 다시 열 수 있게(처음부터 비어 있던 폴더만)
        import shutil
        if os.path.isdir(dest):
            if made:
                shutil.rmtree(dest, ignore_errors=True)
            else:
                for n in os.listdir(dest):
                    full = os.path.join(dest, n)
                    shutil.rmtree(full, ignore_errors=True) if os.path.isdir(full) else os.remove(full)
        if isinstance(e, ProjectError) or not isinstance(e, Exception):
            raise
        raise ProjectError(f"묶음을 풀 수 없습니다(깨졌거나 암호가 걸린 묶음) — {type(e).__name__}: {e}") from None


def _open(zip_path: str, dest: str) -> dict:
    try:
        z = zipfile.ZipFile(zip_path)
    except zipfile.BadZipFile:
        raise ProjectError(f"zip 파일이 아닙니다: {zip_path}") from None
    with z:
        infos = z.infolist()
        tops = {i.filename.split("/", 1)[0] for i in infos if i.filename}
        if len(tops) != 1:
            raise ProjectError("Equion 묶음이 아닙니다 — 맨 위 폴더가 하나여야 합니다")
        top = tops.pop()
        try:
            manifest = json.loads(z.read(f"{top}/bundle.json").decode("utf-8"))
        except KeyError:
            raise ProjectError("Equion 묶음이 아닙니다 — bundle.json이 없습니다") from None
        except (ValueError, UnicodeDecodeError) as e:
            raise ProjectError(f"Equion 묶음이 아닙니다 — bundle.json을 읽을 수 없습니다({e})") from None
        if not isinstance(manifest, dict) or manifest.get("format") != FORMAT:
            raise ProjectError(f"Equion 묶음이 아닙니다 — format {manifest.get('format') if isinstance(manifest, dict) else None!r}")
        fv = manifest.get("format_version")
        if not isinstance(fv, int) or isinstance(fv, bool) or fv < 1:
            raise ProjectError(f"Equion 묶음이 아닙니다 — format_version {fv!r}")
        if fv > FORMAT_VERSION:
            raise ProjectError(f"더 새 판의 묶음입니다(format_version {fv}) — equion을 올리세요")
        if len(infos) > MAX_FILES or sum(i.file_size for i in infos) > MAX_BYTES:
            raise ProjectError("묶음이 너무 큽니다")
        base = os.path.normcase(dest + os.sep)
        plan = []
        for i in infos:
            name = i.filename
            if name.endswith("/"):
                continue
            rel = name.split("/", 1)[1] if "/" in name else ""
            if not rel or rel.startswith("/") or "\\" in rel or ":" in rel.split("/")[0] or any(seg in ("..", "") for seg in rel.split("/")):
                raise ProjectError(f"묶음 안의 경로가 잘못되었습니다: {name}")
            target = os.path.abspath(os.path.join(dest, *rel.split("/")))
            if not os.path.normcase(target).startswith(base):
                raise ProjectError(f"묶음 안의 경로가 폴더 밖을 가리킵니다: {name}")
            plan.append((i, target))
        if f"{top}/equion.toml" not in {i.filename for i in infos}:
            raise ProjectError("Equion 묶음이 아닙니다 — equion.toml이 없습니다")
        os.makedirs(dest, exist_ok=True)
        for i, target in plan:
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with z.open(i) as src, open(target, "wb") as out:
                while True:
                    chunk = src.read(1 << 20)
                    if not chunk:
                        break
                    out.write(chunk)
    os.remove(os.path.join(dest, "bundle.json"))
    with open(os.path.join(dest, "work", "bundle.json") if os.path.isdir(os.path.join(dest, "work")) else os.path.join(dest, "bundle.json"),
              "w", encoding="utf-8") as f:
        json.dump({**manifest, "opened": now_iso(), "from": os.path.basename(zip_path)}, f, ensure_ascii=False, indent=2)
    return {"path": dest, "manifest": manifest}


def describe(zip_path: str) -> dict:
    """묶음을 풀지 않고 명세만 읽는다."""
    with zipfile.ZipFile(zip_path) as z:
        tops = {i.filename.split("/", 1)[0] for i in z.infolist() if i.filename}
        if len(tops) != 1:
            raise ProjectError("Equion 묶음이 아닙니다")
        top = tops.pop()
        try:
            return {"top": top, **json.loads(z.read(f"{top}/bundle.json").decode("utf-8"))}
        except KeyError:
            raise ProjectError("Equion 묶음이 아닙니다 — bundle.json이 없습니다") from None

