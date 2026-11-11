"""모형의 일(작업 프로세스 안에서 돈다) — 조립 보기·과거 재현 보기·원인 따라가기·정의 고치기·스크립트·회차 바꾼 뒤 할 일(D3).

앱 프로세스는 `equion`을 불러오지 않는다(D41) — 이 모듈은 작업 프로세스(`worker.serve`)만 부른다. 하는 일은 모두 패키지의 함수다:
조립은 `Project.assemble`, 풀이는 `Project.hs`, 스크립트는 `Project.run_script`, 정의를 쓰는 일은 `model_define`·`block_define`·
`History.write_files`. 여기서는 화면이 쓰기 좋은 모양으로 고르고 묶기만 한다.
"""
from __future__ import annotations

import fnmatch
import os
from typing import Any, Callable

from .dataops import command

MAX_POINTS = 4000


def _float(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if out == out and out not in (float("inf"), float("-inf")) else None


def _data_id(meta: dict) -> str | None:
    data = meta.get("data") or {}
    return data.get("id") or data.get("file")


# ---- 조립 ---------------------------------------------------------------------------------------

def assembly(project: Any, model: str | None = None) -> dict:
    """조립 보기 — 모형이 어떤 블록·식으로 이루어지는지, 내생·외생, 블록 사이의 연결, 풀이 블록, 문제. 계산하지 않는다(파일을 읽기만)."""
    cfg = project.config
    name = model or (cfg.hs or {}).get("model") or next(iter(cfg.models), None)
    out: dict[str, Any] = {"models": list(cfg.models), "blocks": [{"name": b.name, "file": b.file, "desc": b.desc} for b in cfg.blocks.values()],
                           "model": name, "report": None, "spec": None, "error": None}
    if not name:
        return out
    spec = cfg.models.get(name)
    if spec is not None:
        out["spec"] = {"name": spec.name, "desc": spec.desc, "blocks": list(spec.blocks), "include": list(spec.include), "exclude": list(spec.exclude)}
    try:
        report = project.assemble(name).to_dict()
    except Exception as exc:              # 없는 모형·깨진 설정 — 까닭을 그대로
        out["error"] = str(exc.args[0]) if isinstance(exc, KeyError) and exc.args else str(exc)
        return out
    adopted = project.adopted
    for part in report.get("parts", []):
        part["block"], _, part["target"] = str(part["id"]).partition(":")
        part["adopted"] = adopted.get(part["id"])
    report["used_by"] = {b: [m for m in project.used_by(b) if m != name] for b in cfg.blocks}
    report["includes"] = {m: list(cfg.models[m].blocks) + [f"({x})" for x in cfg.models[m].include] for m in (spec.include if spec else []) if m in cfg.models}
    out["report"] = report
    out["command"] = command("assemble", name)
    return out


def used_by(project: Any, name: str) -> dict:
    """쓰는 곳 — 블록이나 부품을 쓰는 모형들."""
    return {"name": name, "models": list(project.used_by(name))}


def model_define(project: Any, name: str, blocks: list | None = None, include: list | None = None, exclude: list | None = None,
                 desc: str | None = None, dry: bool = False) -> dict:
    """모형 정의 쓰기(`equion model define`) — dry 면 쓰지 않고 `equion.toml`의 차이만."""
    words: list[Any] = ["model", "define", name]
    for flag, value in (("--blocks", blocks), ("--include", include), ("--exclude", exclude)):
        if value is not None:
            words += [flag, ",".join(value)]
    if desc is not None:
        words += ["--desc", desc]
    cmd = command(*words)
    if dry:
        from equion.projects.config import model_text

        text, new = model_text(project.config.path, name, blocks=blocks, include=include, exclude=exclude, desc=desc)
        return {"kind": "model", "name": name, "new": new, "command": cmd, **_diff(project, "equion.toml", text)}
    res = project.model_define(name, blocks=blocks, include=include, exclude=exclude, desc=desc, who="desk", command=cmd)
    return {**res.to_dict(), "command": cmd}


def block_define(project: Any, name: str, desc: str | None = None, dry: bool = False) -> dict:
    """블록 더하기(`equion block define`) — 빈 블록 파일을 함께 만든다. dry 면 쓰지 않고 차이만."""
    cmd = command("block", "define", name, *(["--desc", desc] if desc else []))
    if dry:
        from equion.projects.config import block_text

        text, new, rel, create = block_text(project.config.path, name, desc=desc)
        return {"kind": "block", "name": name, "new": new, "files": [rel] if create else [], "command": cmd, **_diff(project, "equion.toml", text)}
    res = project.block_define(name, desc=desc, who="desk", command=cmd)
    return {**res.to_dict(), "command": cmd}


def _diff(project: Any, rel: str, text: str) -> dict:
    import difflib

    path = os.path.join(str(project.root), *rel.split("/"))
    try:
        with open(path, encoding="utf-8") as f:
            old = f.read()
    except OSError:
        old = ""
    diff = "".join(difflib.unified_diff(old.splitlines(True), text.splitlines(True), f"a/{rel}", f"b/{rel}", n=1))
    return {"path": rel, "diff": diff, "same": old == text}


# ---- 정의 파일을 글로 고치기 ---------------------------------------------------------------------

def _tracked(project: Any, rel: str) -> bool:
    from equion.work.history import PATTERNS

    rel = rel.replace("\\", "/")
    blocks = {b.file.replace("\\", "/") for b in project.config.blocks.values()}
    return rel in blocks or any(fnmatch.fnmatchcase(rel, pattern) for pattern in PATTERNS)


def check_text(project: Any, path: str, text: str) -> dict:
    """정의 파일의 글을 읽어만 본다(쓰지 않는다) — 블록 파일은 줄마다 식 문법, TOML 은 문법과 설정 검사. `{problems: [{line, text}], kind}`."""
    rel = path.replace("\\", "/")
    problems: list[dict] = []
    kind = "text"
    if rel.lower().endswith(".txt") and (rel.startswith("EQUATIONS/") or any(b.file.replace("\\", "/") == rel for b in project.config.blocks.values())):
        from equion.projects.parts import parse_line

        kind = "block"
        data = project.workfile._data
        targets: dict[str, int] = {}
        for n, raw in enumerate(text.splitlines(), 1):
            body = raw.split("#", 1)[0].strip()
            if not body:
                continue
            try:
                info = parse_line(body, data)
            except Exception as exc:
                problems.append({"line": n, "text": str(exc)})
                continue
            target = str(info.get("target") or "").upper()
            if target in targets:
                problems.append({"line": n, "text": f"목표 {info['target']} 이(가) {targets[target]}줄과 겹칩니다 — 한 블록에 목표 하나에 식 하나"})
            elif target:
                targets[target] = n
    elif rel.lower().endswith(".toml"):
        import tomllib

        kind = "toml"
        try:
            tomllib.loads(text)
        except tomllib.TOMLDecodeError as exc:
            import re

            at = re.search(r"at line (\d+)", str(exc))
            problems.append({"line": int(at.group(1)) if at else None, "text": f"TOML 문법: {exc}"})
        else:
            if rel == "equion.toml":
                from equion.projects.config import ProjectError, load_config

                try:
                    load_config(project.config.path, text=text)
                except ProjectError as exc:
                    problems += [{"line": None, "text": str(p)} for p in (getattr(exc, "problems", None) or [str(exc)])]
            elif rel == project.config.series_file:
                from equion.projects.config import ProjectError
                from equion.projects.vintage import load_defs

                cfg = project.config
                try:
                    load_defs(str(project.root), cfg.series_file, cfg.derived_file, cfg.freq, series_text=text)
                except ProjectError as exc:
                    problems += [{"line": None, "text": str(p)} for p in (getattr(exc, "problems", None) or [str(exc)])]
    return {"path": rel, "kind": kind, "problems": problems}


def write_text(project: Any, path: str, text: str) -> dict:
    """정의 파일을 글로 고쳐 쓴다 — 바뀜 기록에 '누가 Desk'로 남는다. 정의 파일(바뀜 기록이 지켜보는 것)만 받는다."""
    from equion.projects.config import ProjectError

    rel = path.replace("\\", "/")
    if not _tracked(project, rel):
        raise ProjectError(f"화면에서 고칠 수 있는 것은 정의 파일뿐입니다(블록 파일·equion.toml·자료 정의·가정·시나리오·스크립트·노트·보고서): {rel}")
    full = os.path.join(str(project.root), *rel.split("/"))
    if not os.path.isfile(full):
        raise ProjectError(f"없는 파일입니다: {rel}")
    text = text.replace("\r\n", "\n")
    if text and not text.endswith("\n"):
        text += "\n"
    change = project.history.write_files({rel: text}, "desk", "Desk 에서 고침", note=rel)
    return {"path": rel, "change": change.id if change is not None else None}


# ---- 과거 재현 ------------------------------------------------------------------------------------

def hs_run(project: Any, target: str | None = None, start: str | None = None, end: str | None = None, mode: str | None = None,
           vs: str | None = None, name: str | None = None) -> dict:
    """과거 재현(`equion hs`) — 모형 또는 블록(블록이면 그 블록만 풀고 나머지는 실측). 기록을 남긴다."""
    words: list[Any] = ["hs", target]
    if start or end:
        words += ["--range", f"{start or 'first'}:{end or 'last'}"]
    if mode and mode != "dynamic":
        words += ["--mode", mode]
    if vs:
        words += ["--vs", vs]
    if name:
        words += ["--as", name]
    rec = project.hs(target, start=start or None, end=end or None, mode=mode or None, vs=vs or None, record=True, as_name=name or None,
                     who="desk", command=command(*words))
    return rec.to_dict()


def hs_replay(project: Any, record: str) -> dict:
    """그때 그대로 다시(`equion hs --replay`) — 기록의 조립 명세·자료로 다시 풀어 숫자가 같은지 본다."""
    rec = project.replay(record, who="desk", command=command("hs", "--replay", record))
    return rec.to_dict()


def hs_view(project: Any, record: str) -> dict:
    """과거 재현 기록 하나 — 변수마다 적합도, 기간마다 풀이 상태, 조립 명세의 부품(어느 계수로 풀었나)."""
    rec = project.work.get(record, "hs")
    meta = dict(rec.meta)
    stats = rec.read_csv("stats.csv")
    rows = [{"name": str(name), "rmspe": _float(row.get("RMSPE")), "mae_pct": _float(row.get("MAE_pct")), "mae": _float(row.get("MAE")),
             "mean_error": _float(row.get("mean_error")), "n": int(row.get("n_samples") or 0)} for name, row in stats.iterrows()]
    status = []
    try:
        table = rec.read_csv("status.csv")
        for period, row in table.iterrows():
            status.append({"period": str(period), "status": str(row.get("status", "")), "excluded": _text(row.get("excluded")),
                           "fallback": _text(row.get("fallback")), "message": _text(row.get("message")), "iterations": _float(row.get("iterations"))})
    except (OSError, ValueError):
        pass
    parts = []
    try:
        spec = rec.read_json("assembly.json")
        parts = [{"id": p.get("id"), "kind": p.get("kind"), "text": p.get("text"), "source": p.get("source")} for p in spec.get("parts", [])]
    except (OSError, ValueError):
        pass
    keep = ("who", "command", "created", "model", "target", "range", "mode", "counts", "swaps", "vs", "replay", "implicit", "data")
    return {"id": rec.id, "path": meta.get("path"), "meta": {k: meta.get(k) for k in keep}, "stats": rows, "status": status, "parts": parts,
            "vintage": _data_id(meta)}


def _text(value: Any) -> str:
    return "" if value is None or value != value else str(value)


def hs_series(project: Any, record: str, names: list[str]) -> dict:
    """과거 재현 기록의 변수들 — 풀린 값과 실측. `{period, series: {이름: {solved, actual}}}`."""
    rec = project.work.get(record, "hs")
    table = rec.read_csv("series.csv")
    table = table.iloc[-MAX_POINTS:]
    cols = {str(c).upper(): c for c in table.columns}
    out: dict[str, Any] = {"record": rec.id, "period": [str(i) for i in table.index], "series": {}}
    for name in names:
        solved, actual = cols.get(name.upper()), cols.get(f"{name}_실측".upper())
        if solved is None:
            continue
        out["series"][name] = {"solved": [_float(v) for v in table[solved].tolist()],
                               "actual": [_float(v) for v in table[actual].tolist()] if actual is not None else None}
    return out


def trace(project: Any, record: str, name: str) -> dict:
    """원인 따라가기 — 변수의 식이 쓰는 입력마다, 이 과거 재현에서의 오차(내생이면)나 실측(외생)인지. 거슬러 올라갈 재료다.

    계산하지 않는다 — 기록의 적합도 표와 조립 명세, 지금의 부품 정의, 그 식만 따로 모의한 추정 기록(`est --sim`)을 읽을 뿐이다.
    """
    rec = project.work.get(record, "hs")
    stats = rec.read_csv("stats.csv")
    fit = {str(k).upper(): row for k, row in stats.iterrows()}
    try:
        spec = rec.read_json("assembly.json")
    except (OSError, ValueError):
        spec = {}
    by_target = {str(p.get("id", "")).partition(":")[2].upper(): p for p in spec.get("parts", [])}
    part = by_target.get(name.upper())
    out: dict[str, Any] = {"record": rec.id, "name": name, "part": None, "inputs": [], "solo": None, "own": None}
    own = fit.get(name.upper())
    if own is not None:
        out["own"] = {"rmspe": _float(own.get("RMSPE")), "mean_error": _float(own.get("mean_error"))}
    if part is None:
        out["note"] = "이 과거 재현에서는 외생입니다 — 실측을 그대로 썼습니다(오차가 없습니다)."
        return out
    pid = str(part.get("id"))
    out["part"] = {"id": pid, "block": pid.partition(":")[0], "kind": part.get("kind"), "text": part.get("text"), "source": part.get("source")}
    variables: list[str] = []
    try:
        variables = sorted(str(v) for v in project.part(pid).variables)
    except Exception:                     # 그 뒤 지워진 부품 — 기록의 글만 보인다
        pass
    for v in variables:
        if v.upper() == name.upper():
            continue
        row = fit.get(v.upper())
        made = by_target.get(v.upper())
        out["inputs"].append({"name": v, "endogenous": made is not None, "part": made.get("id") if made else None,
                              "block": str(made.get("id", "")).partition(":")[0] if made else None,
                              "rmspe": _float(row.get("RMSPE")) if row is not None else None,
                              "mean_error": _float(row.get("mean_error")) if row is not None else None})
    out["inputs"].sort(key=lambda x: (not x["endogenous"], -(x["rmspe"] or 0.0)))
    out["self_lag"] = any(v.upper() == name.upper() for v in variables)
    # 그 식만 따로 모의한 것(다른 변수는 실측) — 식 자체의 오차
    for r in reversed(project.work.records("est")):
        if r.meta.get("part") == pid and (r.meta.get("sim") or {}).get("rmspe") is not None:
            out["solo"] = {"record": r.id, "rmspe": _float(r.meta["sim"]["rmspe"]), "vintage": _data_id(r.meta)}
            break
    return out


# ---- 스크립트 ------------------------------------------------------------------------------------

def scripts(project: Any) -> dict:
    """스크립트 목록(`FLOWS/*.eqs`)과 가장 최근 실행."""
    root = os.path.join(str(project.root), "FLOWS")
    try:
        names = sorted(f for f in os.listdir(root) if f.lower().endswith(".eqs"))
    except OSError:
        names = []
    last: dict[str, dict] = {}
    for rec in project.work.records("run"):
        script = str(rec.meta.get("script") or "")
        last[script.replace("\\", "/")] = {"id": rec.id, "status": rec.meta.get("status"), "created": rec.meta.get("created")}
    return {"scripts": [{"path": f"FLOWS/{n}", "name": os.path.splitext(n)[0], "last": last.get(f"FLOWS/{n}")} for n in names]}


def script_plan(project: Any, path: str, sets: dict | None = None, from_step: Any = None) -> dict:
    """미리보기(`equion run … --dry-run`) — 단계마다 실행할 줄과 바꾸는 파일. 기록을 남기지 않는다. 문제가 있으면 `problems`."""
    from equion.script.language import ScriptError

    try:
        plan = project.run_script(path, sets=sets or None, from_step=from_step, dry_run=True)
    except ScriptError as exc:
        return {"script": path, "title": "", "params": {}, "steps": [], "problems": [str(exc)], "python": [], "ok": False}
    return {"script": plan.script, "title": plan.title, "params": plan.params, "steps": plan.steps, "problems": list(plan.problems),
            "python": list(plan.python), "ok": plan.ok}


def script_run(project: Any, path: str, sets: dict | None = None, from_step: Any = None, notify: Callable[..., None] | None = None) -> dict:
    """스크립트 실행(`equion run x.eqs`) — 단계가 끝날 때마다 알린다(작업 줄에 '3/7 …'). Python 단계는 돌리지 않는다(터미널에서)."""
    words: list[Any] = ["run", path]
    for key, value in (sets or {}).items():
        words += ["--set", f"{key}={value}"]
    if from_step not in (None, ""):
        words += ["--from", from_step]

    def echo(line: str) -> None:
        if notify is not None:
            notify(line=str(line))

    res = project.run_script(path, sets=sets or None, from_step=from_step if from_step not in (None, "") else None, who="desk",
                             command=command(*words), echo=echo, verbosity=1, python=False)
    out = res.to_dict()
    out["record"] = out.get("id")
    return out


def run_view(project: Any, record: str) -> dict:
    """실행 기록 하나 — 단계마다 상태·남긴 기록·바꾼 것."""
    rec = project.work.get(record, "run")
    meta = dict(rec.meta)
    keep = ("who", "command", "created", "script", "title", "params", "from", "status", "exit_code", "records", "changes", "flags", "vintage",
            "implicit", "elapsed", "replay_of")
    return {"id": rec.id, "path": meta.get("path"), "meta": {k: meta.get(k) for k in keep}, "steps": meta.get("steps") or []}


def script_new(project: Any, name: str, records: list[str], title: str | None = None) -> dict:
    """작업 기록에서 스크립트 초안을 만든다(`equion script new`) — `FLOWS/<이름>.eqs`. 바뀜 기록에 남는다."""
    path = project.new_script(name, records=records or None, title=title or None, who="desk",
                              command=command("script", "new", name, "--from-records", *records, *(["--title", title] if title else [])))
    return {"path": str(path).replace("\\", "/")}


# ---- 회차 바꾼 뒤 할 일 ----------------------------------------------------------------------------

def todo(project: Any) -> dict:
    """지금 회차가 아닌 자료로 계산한 것 — 채택한 계수, 가장 최근의 과거 재현·전망. 다시 계산하지 않는다(무엇이 낡았는지만)."""
    cfg = project.config
    current = None
    if cfg.series_file:
        current = next((v["id"] for v in project.data_list() if v.get("current")), None)
    out: dict[str, Any] = {"vintage": current, "adopted": [], "hs": None, "sim": None, "models": list(cfg.models)}
    if current is None:
        return out
    store = project.work
    for part, rid in project.adopted.items():
        try:
            used = _data_id(store.get(rid, "est").meta)
        except Exception:
            used = None
        if used != current:
            out["adopted"].append({"part": part, "record": rid, "vintage": used})
    for kind in ("hs", "sim"):
        records = [r for r in store.records(kind) if not r.meta.get("swaps") and not r.meta.get("replay")]
        if records:
            last = records[-1]
            out[kind] = {"id": last.id, "vintage": _data_id(last.meta), "stale": _data_id(last.meta) != current, "model": last.meta.get("model"),
                         "scenario": last.meta.get("scenario")}
    return out


def reestimate(project: Any, name: str | None = None, adopt: str = "never", parts: list[str] | None = None) -> dict:
    """채택한 식을 지금 자료로 다시 추정(`equion est --adopted`) — 기록만 남기고(adopt='never') 옛 계수와 견줄 재료를 돌려준다.
    parts 를 주면 그 식들의 새 기록을 채택한다(사람이 고른 것만)."""
    if parts:
        done = []
        for item in parts:
            part, _, rid = item.partition("=")
            done.append(project.adopt(rid, part=part, who="desk", command=command("adopt", rid, "--part", part)).to_dict())
        return {"adopted": done}
    words = ["est", "--adopted", *([name] if name else []), "--adopt", adopt]
    res = project.reestimate(name, adopt=adopt, who="desk", command=command(*words))
    store = project.work
    rows = []
    for row in res.rows:
        item = dict(row)
        for key in ("old", "new"):
            rid = row.get(key)
            if not rid:
                continue
            try:
                m = store.get(rid, "est").meta
            except Exception:
                continue
            fit = m.get("stats") or {}
            item[f"{key}_fit"] = {"r2_adj": _float(fit.get("adj_r_squared")), "se": _float(fit.get("se_regression")), "n": m.get("n"),
                                   "sample": m.get("sample"), "vintage": _data_id(m)}
            item[f"{key}_coefs"] = {c["name"]: _float(c.get("coef")) for c in m.get("coefs") or []}
        rows.append(item)
    return {"model": res.model, "policy": res.policy, "rows": rows, "change": res.change}
