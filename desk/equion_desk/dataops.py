"""자료 작업대와 분석 탭의 일 — 작업 프로세스 안에서 돈다(`worker.py`가 부른다. 앱 프로세스는 이 모듈을 불러오지 않는다).

자료는 세 층이다(기획안 K8): **원자료**(받은 파일 그대로 — 고치지 않는다) → **정의**(어느 열을 어떤 시리즈로 — `series.toml`·`derived.txt`)
→ **회차**(정의대로 만든 자료 한 벌 — `work/data/<회차>/`). 화면은 이 흐름을 그대로 보인다. 여기의 함수는 그 화면이 묻는 것에 답한다:

- `overview`    세 층의 지금 상태 — 원자료 파일과 틀, 시리즈마다 만드는 법·구간·쓰는 식, 회차 목록, 지금 회차가 낡았는지
- `series`      시리즈 하나 — 값·값의 종류·내력(원자료의 열 → 변환 → 계절조정 / 파생식)
- `build`·`use`·`diff`·`add`   자료 만들기 · 이 회차로 바꾸기 · 두 회차의 차이와 영향 · 원자료 넣기 — 명령(`equion data …`)과 같은 일
- `analyses`·`run_analysis`·`keep`   분석 등록부(폼이 여기서 나온다) · 분석 하나 실행 · 정의·후보로 남기기 — `equion an …`과 같은 일

계산·파일 형식은 모두 패키지 `equion`의 것이다. 여기서는 부르고, 화면이 그리기 좋은 모양으로 옮길 뿐이다.
"""
from __future__ import annotations

import hashlib
import json
import os
import shlex
from typing import Any

CONVERT_KO = {"mean": "평균", "sum": "합", "last": "끝값", "first": "첫값", "denton": "Denton", "chowlin": "Chow-Lin", "repeat": "반복", "linear": "선형"}
FREQ_KO = {"A": "연", "Q": "분기", "M": "월"}
DIFF_KEYS = {"시리즈": "name", "새 값": "new", "개정": "revised", "처음 개정": "first", "끝 개정": "last", "최대 |차이|": "max_abs",
             "최대 |차이%|": "max_pct", "없어진 값": "lost"}
MAX_POINTS = 4000       # 시리즈 하나에서 화면으로 보내는 값의 수


def command(*words: Any) -> str:
    """기록에 적는 명령 — 같은 일을 터미널에서 할 때 치는 글 그대로."""
    return shlex.join(["equion", *[str(w) for w in words if w not in (None, "")]])


def _seas_text(seas: Any) -> str:
    """계절조정 방법을 짧게 — 'STL 승법'."""
    seas = seas if isinstance(seas, dict) else {"method": seas}
    model = {"multiplicative": "승법", "additive": "가법"}.get(seas.get("model"), "")
    return f"{str(seas.get('method', 'stl')).upper()}{' ' + model if model else ''}"


def _how(spec: Any, freq: str) -> str:
    """시리즈를 만드는 법을 한 줄로 — '분기 평균 · 계절조정(STL 승법)'."""
    bits = []
    if spec.convert:
        bits.append(f"{FREQ_KO.get(freq, freq)} {CONVERT_KO.get(spec.convert, spec.convert)}")
    if spec.seas:
        bits.append(f"계절조정({_seas_text(spec.seas)})")
    if spec.scale not in (None, 1, 1.0):
        bits.append(f"× {spec.scale:g}")
    if spec.fill:
        bits.append(f"채움 {spec.fill}")
    return " · ".join(bits)


def _stat(path: str) -> dict:
    try:
        st = os.stat(path)
        return {"exists": True, "size": st.st_size, "mtime": st.st_mtime}
    except OSError:
        return {"exists": False, "size": 0, "mtime": None}


def _uses(project: Any) -> dict[str, list[str]]:
    """시리즈(대문자) → 그것을 쓰는 부품들."""
    out: dict[str, list[str]] = {}
    for part in project.parts():
        for name in sorted(part.variables):
            out.setdefault(str(name).upper(), []).append(part.id)
    return out


def _span(column: Any) -> tuple[str | None, str | None, int, int]:
    """(처음, 끝, 값의 수, 처음~끝 사이의 결측 수)."""
    valid = column.dropna()
    if not len(valid):
        return None, None, 0, 0
    inside = column.loc[valid.index[0]:valid.index[-1]]
    return str(valid.index[0]), str(valid.index[-1]), int(len(valid)), int(inside.isna().sum())


def _build_info(root: str, vintage: str | None) -> dict:
    if not vintage:
        return {}
    try:
        with open(os.path.join(root, "work", "data", vintage, "build.json"), encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def overview(project: Any) -> dict:
    """자료의 세 층을 한눈에. 계산은 하지 않는다(파일을 읽기만 — 원자료는 틀대로 읽어 구간과 열을 본다)."""
    from equion.data.source import file_sha256, read_source
    from equion.projects.vintage import load_defs, read_vintage

    cfg = project.config
    root = str(project.root)
    uses = _uses(project)
    out: dict[str, Any] = {
        "mode": "defs" if cfg.series_file else "file", "freq": cfg.freq, "data_file": cfg.data_file, "series_file": cfg.series_file,
        "derived_file": cfg.derived_file, "current": None, "vintages": [], "sources": [], "raw": [], "inbox": [], "series": [], "problems": [],
        "stale": None, "pending": False, "fingerprint": None, "groups": [{"name": g.name, "series": list(g.series), "desc": g.desc, "transform": g.transform} for g in cfg.groups.values()],
    }
    if not cfg.series_file:
        # 자료 파일 하나를 그대로 쓰는 프로젝트 — 회차가 없다
        frame = project.workfile.data
        wf = project.workfile
        labels = [wf._label(ts) for ts in frame.index]
        for name in frame.columns:
            col = frame[name].set_axis(labels)
            start, end, n, missing = _span(col)
            out["series"].append({"name": str(name), "kind": "file", "how": "", "from": cfg.data_file, "start": start, "end": end, "n": n, "missing": missing,
                                  "unit": "", "desc": "", "used_by": uses.get(str(name).upper(), [])})
        out["span"] = [labels[0], labels[-1]] if labels else None
        return out

    try:
        defs = load_defs(root, cfg.series_file, cfg.derived_file, cfg.freq)
    except Exception as exc:              # 정의 파일을 읽지 못함 — 까닭을 그대로 보인다
        out["problems"].append(str(exc))
        defs = None
    vintages = project.data_list()
    out["vintages"] = vintages
    current = next((v["id"] for v in vintages if v.get("current")), None)
    out["current"] = current
    frame = flags = None
    if current:
        try:
            frame, flags, _meta = read_vintage(root, current)
        except Exception as exc:
            out["problems"].append(f"지금 회차 {current} 를 읽지 못했습니다: {exc}")
    build = _build_info(root, current)
    if defs is None:
        return out

    # 지금 회차를 만든 뒤 정의·원자료가 바뀌었는가 — 바뀌었으면 '자료 만들기'를 권한다(저절로 만들지 않는다)
    changed_defs = sorted(f for f, sha in defs.texts.items() if (build.get("definitions") or {}).get(f) != sha) if build else []
    built = {s.get("name"): s for s in build.get("sources") or [] if isinstance(s, dict)}
    changed_sources = []
    seen: dict[str, tuple[str, str]] = {}      # 출처 → (지금 파일의 해시, 파일)

    by_source: dict[str, list[str]] = {}
    for spec in defs.series.values():
        by_source.setdefault(spec.source, []).append(spec.name)
    referenced = {}
    for name, spec in defs.sources.items():
        info = {"name": name, "file": spec.file, **_stat(spec.path), "sheet": spec.sheet, "header_row": spec.header_row, "unit_row": spec.unit_row,
                "series": by_source.get(name, []), "freq": None, "note": "", "rows": 0, "columns": [], "missing_cells": 0, "bad_cells": 0,
                "cells": [], "error": None, "changed": False}
        referenced[os.path.normcase(os.path.abspath(spec.path))] = name
        if info["exists"]:
            try:
                table = read_source(spec)
                info.update(freq=table.freq, note=table.time_note.split(": ", 1)[-1], rows=int(len(table.data)), columns=[str(c) for c in table.data.columns],
                            missing_cells=len(table.missing_cells), bad_cells=len(table.bad_cells), cells=(table.missing_cells + table.bad_cells)[:12])
                was = built.get(name)
                seen[name] = (table.sha256, spec.file)
                if build and (was is None or was.get("sha256") != table.sha256 or was.get("file") != spec.file):
                    info["changed"] = True
                    changed_sources.append(name)
            except Exception as exc:      # 틀이 맞지 않음 — 자료 만들기도 여기서 멈춘다
                info["error"] = str(exc)
        else:
            info["error"] = "파일이 없습니다"
        out["sources"].append(info)
    if build and (changed_defs or changed_sources):
        out["stale"] = {"definitions": changed_defs, "sources": changed_sources}
    # '자료 만들기'를 누르면 새 회차가 생기는가 — 가장 새 회차가 이미 지금의 원자료·정의로 만든 것이면 생기지 않는다(바꾸기만 남았다)
    newest = vintages[-1]["id"] if vintages else None
    if newest and newest != current:
        nb = _build_info(root, newest)
        made = {s.get("name"): s for s in nb.get("sources") or [] if isinstance(s, dict)}
        out["pending"] = (not nb or any((nb.get("definitions") or {}).get(f) != sha for f, sha in defs.texts.items())
                          or any(made.get(n) is None or made[n].get("sha256") != sha or made[n].get("file") != file for n, (sha, file) in seen.items()))
    else:
        out["pending"] = bool(out["stale"]) or not current
    # 지금의 정의·원자료를 가리키는 지문 — '자료 만들기'를 눌렀는데 값이 같아 새 회차가 생기지 않았을 때(정의의 주석만 고친 경우 등),
    # 화면이 이 지문을 기억해 두고 같은 것을 다시 권하지 않는다
    out["fingerprint"] = hashlib.sha256(json.dumps([sorted(defs.texts.items()), sorted(seen.items())], ensure_ascii=False).encode("utf-8")).hexdigest()[:16]

    raw_dir = os.path.join(root, "DATA", "raw")
    try:
        entries = sorted(os.scandir(raw_dir), key=lambda e: e.name.casefold())
    except OSError:
        entries = []
    for entry in entries:
        if entry.is_file() and not entry.name.endswith(".source.toml"):
            out["raw"].append({"file": f"DATA/raw/{entry.name}", **_stat(entry.path), "source": referenced.get(os.path.normcase(os.path.abspath(entry.path)))})
    try:
        out["inbox"] = [item.to_dict() for item in project.data_inbox()]
    except Exception as exc:
        out["problems"].append(f"받은 상자를 읽지 못했습니다: {exc}")

    columns = {str(c).upper(): c for c in frame.columns} if frame is not None else {}

    def stats(name: str) -> dict:
        col = columns.get(name.upper())
        if col is None:
            return {"start": None, "end": None, "n": 0, "missing": 0, "built": False}
        start, end, n, missing = _span(frame[col])
        return {"start": start, "end": end, "n": n, "missing": missing, "built": True}

    for spec in defs.series.values():
        out["series"].append({"name": spec.name, "kind": "series", "source": spec.source, "column": spec.column, "from": f"{spec.source}:{spec.column}",
                              "how": _how(spec, cfg.freq), "unit": spec.unit, "desc": spec.desc, "used_by": uses.get(spec.name.upper(), []), **stats(spec.name)})
    for line, name, expr, desc in defs.derived:
        out["series"].append({"name": name, "kind": "derived", "expr": expr, "line": line, "from": f"= {expr}", "how": "", "unit": "", "desc": desc,
                              "used_by": uses.get(name.upper(), []), **stats(name)})
    out["span"] = next((v.get("span") for v in vintages if v.get("current")), None)
    return out


def series(project: Any, name: str) -> dict:
    """시리즈 하나 — 지금 회차의 값과 값의 종류, 그리고 내력. 계절조정·배율이 걸린 시리즈는 원자료의 그 열도 함께(겹쳐 보게)."""
    from equion.data.periods import format_period
    from equion.data.source import read_source
    from equion.projects.config import ProjectError
    from equion.projects.vintage import load_defs, read_vintage

    cfg = project.config
    root = str(project.root)
    out: dict[str, Any] = {"name": name, "period": [], "values": [], "flags": [], "raw": None, "lineage": [], "vintage": None}
    if not cfg.series_file:
        frame = project.workfile.data
        col = next((c for c in frame.columns if str(c).upper() == name.upper()), None)
        if col is None:
            raise ProjectError(f"없는 시리즈: {name}")
        wf = project.workfile
        out.update(name=str(col), period=[wf._label(ts) for ts in frame.index][-MAX_POINTS:], values=frame[col].tolist()[-MAX_POINTS:],
                   lineage=[{"step": "자료 파일", "text": cfg.data_file}])
        return out
    vintage = project.vintage
    if not vintage:
        raise ProjectError("아직 만든 자료 회차가 없습니다 — 자료 만들기(equion data build)")
    frame, flags, _meta = read_vintage(root, vintage)
    col = next((c for c in frame.columns if str(c).upper() == name.upper()), None)
    if col is None:
        raise ProjectError(f"지금 회차 {vintage} 에 없는 시리즈: {name} — 정의에 더했으면 자료를 다시 만드세요")
    values = frame[col]
    valid = values.dropna()
    if len(valid):                       # 앞뒤의 빈 기간은 뺀다
        values = values.loc[valid.index[0]:valid.index[-1]]
    values = values.iloc[-MAX_POINTS:]
    out.update(name=str(col), vintage=vintage, period=[str(i) for i in values.index], values=values.tolist(),
               flags=[str(x) for x in flags[col].reindex(values.index).tolist()] if col in flags.columns else [])
    defs = load_defs(root, cfg.series_file, cfg.derived_file, cfg.freq)
    spec = next((s for s in defs.series.values() if s.name.upper() == name.upper()), None)
    if spec is not None:
        source = defs.sources.get(spec.source)
        out["lineage"] = [{"step": "원자료", "text": source.file if source else spec.source, "file": source.file if source else None},
                          {"step": "열", "text": spec.column}]
        if spec.convert:
            out["lineage"].append({"step": "주기 변환", "text": f"{FREQ_KO.get(cfg.freq, cfg.freq)} {CONVERT_KO.get(spec.convert, spec.convert)}"})
        if spec.scale not in (None, 1, 1.0):
            out["lineage"].append({"step": "배율", "text": f"× {spec.scale:g}"})
        if spec.fill:
            out["lineage"].append({"step": "채움", "text": str(spec.fill)})
        if spec.seas:
            out["lineage"].append({"step": "계절조정", "text": _seas_text(spec.seas)})
        if source is not None and (spec.seas or spec.scale not in (None, 1, 1.0)):
            try:
                table = read_source(source)
                real, _ = table.column(spec.column)
                if real is not None and table.freq == cfg.freq:        # 같은 주기일 때만 한 축에 놓는다
                    raw = table.data[real].set_axis([format_period(ts, table.freq) for ts in table.data.index]).reindex(values.index)
                    out["raw"] = {"label": f"{spec.source}:{spec.column}(원자료)", "values": raw.tolist()}
            except Exception:            # 원자료를 못 읽어도 시리즈는 보인다
                pass
    else:
        found = next((d for d in defs.derived if d[1].upper() == name.upper()), None)
        if found:
            out["lineage"] = [{"step": "파생식", "text": f"{found[1]} = {found[2]}", "file": cfg.derived_file, "line": found[0]}]
    return out


def _diff(report: Any) -> dict:
    d = report.to_dict()
    rows = [{DIFF_KEYS.get(k, k): v for k, v in row.items()} for row in d.get("changes") or []]
    spans = (d.get("span_a") or [None, None], d.get("span_b") or [None, None])
    return {"a": d.get("a"), "b": d.get("b"), "span_a": spans[0], "span_b": spans[1], "added": d.get("added") or [], "removed": d.get("removed") or [],
            "unchanged": d.get("unchanged") or [], "rows": rows, "revised": sum(1 for r in rows if r.get("revised")),
            "extended": sum(1 for r in rows if r.get("new")), "text": report.text()}


def diff(project: Any, a: str | None = None, b: str | None = None) -> dict:
    """두 회차의 차이(새 기간·개정)와, 바뀐 시리즈를 쓰는 식·모형. 다시 계산하지 않는다."""
    out = _diff(project.data_diff(a, b))
    try:
        impact = project.data_impact(a, b).to_dict()
        out["impact"] = {"parts": impact.get("parts") or [], "models": impact.get("models") or [], "uses": impact.get("uses") or {}}
    except Exception:
        out["impact"] = {"parts": [], "models": [], "uses": {}}
    return out


def build(project: Any) -> dict:
    """자료 만들기 — 원자료를 정의대로 읽어 새 회차를 만든다(내용이 같으면 만들지 않는다). 지금 회차는 그대로다."""
    before = project.vintage
    result = project.data_build(who="desk", command=command("data", "build")).to_dict()
    out = {"id": result.get("id"), "created": bool(result.get("created")), "span": result.get("span"), "n_series": result.get("n_series"),
           "implicit": result.get("implicit") or [], "current": before, "kind": "data", "record": f"data:{result.get('id')}"}
    if out["created"] and before and before != out["id"]:
        try:
            out["diff"] = _diff(project.data_diff(before, out["id"]))
        except Exception:
            pass
    return out


def use(project: Any, vintage: str) -> dict:
    """이 회차로 바꾸기 — `equion.toml [data] vintage`를 고친다(바뀜 기록에 남는다). 결과는 다시 계산하지 않는다."""
    previous = project.data_use(vintage, who="desk", command=command("data", "use", vintage))
    return {"vintage": vintage, "previous": previous}


def add(project: Any, path: str, source: str | None = None, name: str | None = None, inbox: bool = False) -> dict:
    """원자료 넣기 — 파일을 `DATA/raw/`에 복사한다(받은 그대로). source 를 주면 그 출처가 이 파일을 읽게 한다(틀이 맞을 때만).

    inbox: 받은 상자(`DATA/raw/inbox/`)의 파일이다 — 넣고 나면 받은 상자에서 뺀다(`equion data build --inbox`가 하는 것과 같다).
    빼는 것은 `DATA/raw/`에 같은 내용(해시)의 파일이 들어간 것을 확인한 뒤에만 한다.
    """
    from equion.data.source import file_sha256

    shown = os.path.relpath(path, str(project.root)).replace(os.sep, "/") if inbox else path
    result = project.data_add(path, source=source, as_name=name, who="desk",
                              command=command("data", "add", shown, *(["--source", source] if source else []), *(["--as", name] if name else [])))
    out = result.to_dict()
    out["removed"] = False
    if inbox and not out.get("problems"):
        kept = os.path.join(str(project.root), *str(out.get("file") or "").split("/"))
        if os.path.isfile(kept) and not os.path.samefile(kept, path) and file_sha256(kept) == file_sha256(path):
            os.remove(path)
            out["removed"] = True
    return out


def analyses(project: Any) -> dict:
    """분석 등록부 — 화면의 옵션 폼이 여기서 나온다(명령줄 옵션·도움말과 같은 곳). 대상으로 고를 수 있는 이름들도 함께."""
    from equion import registry

    cfg = project.config
    items = []
    for a in registry.analyses():
        items.append({"name": a.name, "label": a.label, "group": a.group, "targets": list(a.targets), "target_labels": [registry.TARGET_KO.get(t, t) for t in a.targets],
                      "makes": a.makes, "makes_label": registry.MAKES_KO.get(a.makes) if a.makes else None, "results": a.results, "help": a.help, "example": a.example,
                      "options": [{"name": o.name, "type": o.type, "default": o.default, "choices": list(o.choices), "help": o.help, "metavar": o.metavar} for o in a.options]})
    names: list[str] = []
    try:
        names = [str(c) for c in project.workfile.data.columns]
        if cfg.series_file:
            # 회차에 든 시리즈만 — 식 작업대가 만들어 둔 지시자 열(@d·@seas 의 더미)은 고를 이름이 아니다
            from equion.projects.vintage import read_vintage

            current = next((v["id"] for v in project.data_list() if v.get("current")), None)
            if current:
                kept = {str(c).upper() for c in read_vintage(str(project.root), current)[0].columns}
                names = [n for n in names if n.upper() in kept] or names
    except Exception:
        pass
    parts = [p.id for p in project.parts() if p.kind == "equation"]
    return {"analyses": items, "names": {"series": names, "group": list(cfg.groups), "part": parts, "model": list(cfg.models), "block": list(cfg.blocks)}}


def analysis_command(analysis: str, target: str, options: dict, smpl: str | None, name: str | None) -> str:
    """분석 명령 글 — 명령줄(`equion an …`)이 받는 모양 그대로. 화면이 실행 전에 보이는 글과 같다."""
    from equion import registry

    spec = registry.get(analysis)
    words: list[Any] = ["an", analysis, target]
    for o in spec.options:
        if o.name not in options:
            continue
        value = options[o.name]
        flag = "--" + o.name.replace("_", "-")
        if o.type == "bool":
            if bool(value) != bool(o.default):
                words.append(f"--no-{o.name.replace('_', '-')}" if o.default else flag)
        elif value not in (None, "") and value != o.default:
            words += [flag, value]
    if smpl:
        words += ["--smpl", smpl]
    if name:
        words += ["--as", name]
    return command(*words)


def run_analysis(project: Any, analysis: str, target: str, options: dict | None = None, smpl: str | None = None, name: str | None = None) -> dict:
    """분석 하나 — 등록부의 분석을 돌려 기록(an:)을 남긴다. 옵션은 등록부에 있는 이름만, 형식에 맞게."""
    from equion import registry
    from equion.projects.config import ProjectError

    spec = registry.get(analysis)
    clean: dict[str, Any] = {}
    for o in spec.options:
        if o.name not in (options or {}):
            continue
        value = (options or {})[o.name]
        if value in (None, ""):
            continue
        try:
            if o.type == "int":
                value = int(value)
            elif o.type == "float":
                value = float(value)
            elif o.type == "bool":
                value = bool(value)
            elif o.type == "choice" and value not in o.choices:
                raise ValueError(value)
            else:
                value = value if o.type in ("int", "float", "bool") else str(value)
        except (TypeError, ValueError):
            raise ProjectError(f"--{o.name}: 받을 수 없는 값 {value!r}" + (f" ({' · '.join(o.choices)})" if o.choices else "")) from None
        clean[o.name] = value
    rec = project.an(analysis, target, smpl=smpl or None, as_name=name or None, who="desk",
                     command=analysis_command(analysis, target, clean, smpl, name), **clean)
    out = rec.to_dict() if hasattr(rec, "to_dict") else {**dict(rec.meta), "id": rec.id}
    out.setdefault("id", rec.id)
    out["makes"] = spec.makes
    return out


def keep(project: Any, record: str, name: str | None = None, replace: bool = False) -> dict:
    """남기기 — 만드는 분석(계절조정·파생)은 정의로, 부품을 내는 분석(ECM·VAR…)은 식 후보로. 정의를 고치면 바뀜 기록에 남는다."""
    kept = project.keep(record, as_name=name or None, replace=bool(replace), who="desk",
                        command=command("an", "keep", record, *(["--as", name] if name else []), *(["--replace"] if replace else [])))
    return kept.to_dict() if hasattr(kept, "to_dict") else {"kind": getattr(kept, "kind", None), "what": list(getattr(kept, "what", []) or [])}
