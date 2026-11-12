"""전망과 보고서의 일(작업 프로세스 안에서 돈다) — 가정 표·보정항·시나리오·전망 기록 보기·보기·보고서로 보내기·엑셀로(D4).

하는 일은 패키지의 함수다: 전망은 `Project.sim`, 보고서는 `report_new·report_add·report_check·report_update`, 엑셀은 `export`,
보기는 `view_define`. 가정 표를 고친 것은 `History.write_files`로 바뀜 기록에 남긴다. 여기서는 화면이 쓰기 좋은 모양으로 묶는다.
"""
from __future__ import annotations

import csv
import io
import os
import re
from typing import Any

from .dataops import command
from .modelops import _data_id, _float

NAME = re.compile(r"[A-Za-z][A-Za-z0-9_\-]{0,60}")
SHOW = ("level", "qoq", "yoy", "diff")


def _labels(freq: str, start: str, end: str) -> list[str]:
    """구간의 기간 라벨들(2020Q1 · 2020M1 · 2020 꼴)."""
    import pandas as pd

    code = {"Q": "Q", "M": "M", "A": "Y"}[freq]
    out = []
    for p in pd.period_range(start=start.replace("M", "-") if freq == "M" else start, end=end.replace("M", "-") if freq == "M" else end, freq=code):
        out.append(f"{p.year}Q{p.quarter}" if freq == "Q" else f"{p.year}M{p.month}" if freq == "M" else str(p.year))
    return out


def _csv_grid(path: str) -> tuple[list[str], dict[str, dict[str, str]]]:
    """가정 CSV → (열 이름들, {기간: {열: 글자}})."""
    try:
        with open(path, encoding="utf-8-sig", newline="") as f:
            rows = list(csv.reader(f))
    except OSError:
        return [], {}
    if not rows:
        return [], {}
    cols = [c.strip() for c in rows[0][1:]]
    grid: dict[str, dict[str, str]] = {}
    for row in rows[1:]:
        if not row or not row[0].strip():
            continue
        grid[row[0].strip()] = {c: (row[i + 1].strip() if i + 1 < len(row) else "") for i, c in enumerate(cols)}
    return cols, grid


def forecast(project: Any, model: str | None = None) -> dict:
    """전망 한눈에 — 모형과 구간, 가정 표(외생 × 전망 구간), 채우기 규칙, 보정항 규칙, 시나리오, 전망 기록. 계산하지 않는다."""
    from equion.projects import sim as S

    cfg = project.config
    fc = dict(cfg.forecast or {})
    name = model or fc.get("model") or (cfg.hs or {}).get("model") or next(iter(cfg.models), None)
    out: dict[str, Any] = {"models": list(cfg.models), "model": name, "freq": cfg.freq, "forecast": fc, "error": None, "range": None, "periods": [],
                           "exogenous": [], "assume": None, "addfactors": None, "scenarios": [], "records": [], "views": [], "vintages": []}
    if not name:
        return out
    try:
        start, end = project.span(fc.get("range") or "next:8")
        out["range"], out["periods"] = [start, end], _labels(cfg.freq, start, end)
        report = project.assemble(name)
        exo = [v for v in report.exogenous if not (report.exo_info.get(v) or {}).get("indicator")]
    except Exception as exc:
        out["error"] = str(exc.args[0]) if isinstance(exc, KeyError) and exc.args else str(exc)
        return out

    # 외생 변수의 끝 실측(가정을 적을 때 견줄 값)
    frame = project.workfile.data
    wf = project.workfile
    cols = {str(c).upper(): c for c in frame.columns}
    for v in exo:
        col = cols.get(v.upper())
        tail = frame[col].dropna().iloc[-4:] if col is not None else []
        out["exogenous"].append({"name": v, "last": [{"period": wf._label(ts), "value": _float(val)} for ts, val in (tail.items() if col is not None else [])]})

    assume = fc.get("assume") or "base"
    rel = f"ASSUMPTIONS/{assume}.csv"
    acols, grid = _csv_grid(os.path.join(str(project.root), *rel.split("/")))
    names = {c.upper(): c for c in acols}
    out["assume"] = {"name": assume, "file": rel, "exists": bool(acols), "fill": fc.get("fill") or "last",
                     "extra": [c for c in acols if c.upper() not in {v.upper() for v in exo}],
                     "values": {p: {v: (grid.get(p) or {}).get(names.get(v.upper(), v), "") for v in exo} for p in out["periods"]}}

    add = fc.get("addfactors") or "base"
    try:
        loaded = S.load_addfactors(project, add, cfg.freq)
        out["addfactors"] = {"name": add, "file": loaded.get("file"), "default": loaded.get("default"),
                             "eqs": {k: dict(v) for k, v in (loaded.get("eqs") or {}).items()}, "values_file": loaded.get("values_file")}
    except Exception as exc:
        out["addfactors"] = {"name": add, "file": f"ADDFACTORS/{add}.toml", "error": str(exc)}

    folder = os.path.join(str(project.root), "SCENARIOS")
    try:
        files = sorted(f for f in os.listdir(folder) if f.lower().endswith(".toml"))
    except OSError:
        files = []
    for f in files:
        sname = os.path.splitext(f)[0]
        try:
            sc = S.load_scenario(project, sname)
            out["scenarios"].append({"name": sname, "file": f"SCENARIOS/{f}", "desc": sc.get("desc", ""), "base": sc.get("base"), "model": sc.get("model"),
                                     "shocks": [dict(x) for x in sc.get("shocks") or []], "addfactor": [dict(x) for x in sc.get("addfactor") or []]})
        except Exception as exc:
            out["scenarios"].append({"name": sname, "file": f"SCENARIOS/{f}", "error": str(exc)})

    for rec in project.work.records("sim"):
        m = rec.meta
        out["records"].append({"id": rec.id, "scenario": m.get("scenario"), "model": m.get("model"), "range": m.get("range"), "created": m.get("created"),
                               "who": m.get("who"), "vintage": _data_id(m), "annual": m.get("annual"), "vs_base": m.get("vs_base")})
    try:
        out["views"] = views(project)["views"]
    except Exception:
        out["views"] = []
    if cfg.series_file:
        out["vintages"] = [{"id": v["id"], "current": bool(v.get("current"))} for v in project.data_list()]
    return out


def _period_key(period: str) -> list[int]:
    return [int(x) for x in re.findall(r"\d+", period)]


def assume_write(project: Any, name: str, columns: list[str], rows: dict[str, dict[str, str]], bases: dict[str, dict[str, str]] | None = None,
                 force: bool = False) -> dict:
    """가정 표를 쓴다(`ASSUMPTIONS/<이름>.csv`) — 기간 × 외생 변수. 빈칸은 그대로 빈칸(채우기 규칙이 채운다). 바뀜 기록에 'Desk'로 남는다.

    rows 는 고친 칸만 받는다(화면은 사람이 친 칸만 보낸다) — 그 칸들을 **지금 파일**에 얹으므로, 화면이 표를 읽은 뒤 밖(엑셀·Claude·편집기)에서
    고친 다른 칸은 그대로 남는다. bases(칸마다 고치기 시작할 때 읽은 값)를 주면, 그 사이 밖에서도 같은 칸이 다른 값으로 바뀐 것을 가려
    쓰지 않고 `Conflict`(409 — detail 에 칸마다 읽은 값·지금 값·친 값)로 알린다. force 면 친 값으로 덮는다.

    바뀐 칸이 있는 줄만 다시 쓴다 — 나머지 줄은 글자 그대로(따옴표·숫자 모양·줄 끝까지) 두어 바뀜 기록에 고친 줄만 남는다.
    파일에 없던 열은 값을 적은 칸이 있을 때만 더한다(화면은 모형의 외생 모두를 보내지만, 비운 열을 덧붙이면 모든 줄이 바뀐다).
    열 이름은 대소문자를 가리지 않고 파일의 것에 맞춘다. 표에 없던 기간의 줄(지난 전망의 가정)은 그대로 둔다."""
    from equion.projects.config import ProjectError

    if not NAME.fullmatch(name):
        raise ProjectError(f"가정 세트 이름 {name!r} — 영문으로 시작하고 영문·숫자·_ 만")
    rel = f"ASSUMPTIONS/{name}.csv"
    path = os.path.join(str(project.root), *rel.split("/"))
    for period, cells in rows.items():
        for col, text in cells.items():
            if text not in ("", None):
                try:
                    float(str(text).replace(",", ""))
                except ValueError:
                    raise ProjectError(f"{period} {col}: 숫자가 아닙니다 — {text!r}") from None
    from equion.work.lock import project_lock

    with project_lock(str(project.root)):          # 지금 파일 읽기 → 친 칸 얹기 → 쓰기를 한 번에(그 사이 다른 명령이 같은 표를 고치지 못하게)
        return _assume_merge(project, rel, path, rows, bases, force)


def _assume_merge(project: Any, rel: str, path: str, rows: dict[str, dict[str, str]], bases: dict[str, dict[str, str]] | None, force: bool) -> dict:
    """`assume_write`의 몸 — 프로젝트 잠금 안에서 부른다. 지금 파일을 읽어 친 칸을 얹고(밖에서도 바뀐 칸은 `Conflict`) 바뀜 기록으로 쓴다.
    다른 프로그램(엑셀)이 파일을 쥐고 있어 읽지 못하면 `FileBusy`(입력 오류) — 빈 파일로 보고 덮어쓰지 않는다."""
    from equion.work.lock import as_busy

    try:
        with open(path, "rb") as f:
            raw = f.read()
    except FileNotFoundError:
        raw = b""
    except OSError as exc:
        raise as_busy(exc, rel, reading=True) from None
    bom = raw.startswith(b"\xef\xbb\xbf")
    old_text = raw.decode("utf-8-sig", errors="replace")
    eol = "\r\n" if "\r\n" in old_text else "\n"
    lines = old_text.splitlines()
    parsed = [next(csv.reader([ln])) if ln.strip() else [] for ln in lines]
    header = parsed[0] if parsed and parsed[0] else ["period"]
    cols = [c.strip() for c in header[1:]]
    where = {c.upper(): i for i, c in enumerate(cols)}

    # 밖에서도 바뀐 칸 — 읽은 값(base)과 지금 파일의 값이 다르고, 지금 값이 친 값과도 다르면 겹친 것이다
    if bases and not force:
        current = {cells[0].strip(): cells for cells in parsed[1:] if cells and cells[0].strip()}
        clashes = []
        for period, cells in rows.items():
            for col, value in cells.items():
                base = (bases.get(period) or {}).get(col)
                if base is None:
                    continue
                mine = "" if value is None else str(value).replace(",", "").strip()
                j, row = where.get(str(col).upper()), current.get(str(period).strip())
                now = row[j + 1].strip() if row is not None and j is not None and j + 1 < len(row) else ""
                if now != str(base).strip() and now != mine:
                    clashes.append({"period": period, "name": col, "base": str(base).strip(), "now": now, "mine": mine})
        if clashes:
            from .modelops import Conflict

            shown = " · ".join(f"{c['name']} {c['period']}" for c in clashes[:4]) + (f" 외 {len(clashes) - 4}칸" if len(clashes) > 4 else "")
            raise Conflict(f"고치는 동안 밖에서도 바뀐 칸이 있습니다 — {shown}. 어느 값을 쓸지 고르세요.", clashes)

    # 받은 칸 → 파일의 열 번호(값을 적은 새 열만 더한다)
    want: dict[str, dict[int, str]] = {}
    added = False
    for period, cells in rows.items():
        for col, value in cells.items():
            text = "" if value is None else str(value).replace(",", "").strip()
            j = where.get(str(col).upper())
            if j is None:
                if not text:
                    continue
                cols.append(str(col))
                j = where[str(col).upper()] = len(cols) - 1
                added = True
            want.setdefault(str(period).strip(), {})[j] = text

    if not raw and not any(text for cells in want.values() for text in cells.values()):
        return {"path": rel, "change": None}         # 파일도 없고 적은 값도 없다 — 빈 파일을 만들지 않는다

    def line(cells: list[str]) -> str:
        buf = io.StringIO()
        csv.writer(buf, lineterminator="").writerow(cells)
        return buf.getvalue()

    out: list[str] = [line(["period" if not parsed or not parsed[0] else header[0], *cols]) if added or not lines else lines[0]]
    seen: set[str] = set()
    keys: list[list[int] | None] = []      # 줄마다 기간의 차례(새 줄을 끼울 자리) — 기간이 아닌 줄은 None
    for ln, cells in zip(lines[1:], parsed[1:]):
        period = cells[0].strip() if cells else ""
        if not period:
            out.append(ln)
            keys.append(None)
            continue
        seen.add(period)
        vals = [(cells[i + 1].strip() if i + 1 < len(cells) else "") for i in range(len(cols))]
        changed = False
        for j, text in want.get(period, {}).items():
            if vals[j] != text:
                vals[j], changed = text, True
        out.append(line([cells[0], *vals]) if changed or added else ln)
        keys.append(_period_key(period))
    # 파일에 없던 기간 — 적은 값이 있을 때만, 기간 차례에 맞는 자리에
    for period in sorted((p for p in want if p not in seen and any(want[p].values())), key=_period_key):
        vals = [""] * len(cols)
        for j, text in want[period].items():
            vals[j] = text
        k = _period_key(period)
        at = next((i for i, key in enumerate(keys) if key is not None and key > k), len(keys))
        out.insert(at + 1, line([period, *vals]))
        keys.insert(at, k)
    text = eol.join(out) + eol
    if text == old_text or (old_text and text == old_text + eol):
        return {"path": rel, "change": None}
    change = project.history.write_files({rel: ("\ufeff" if bom else "") + text}, "desk", "Desk 에서 고침(가정 표)", note=rel)
    return {"path": rel, "change": change.id if change is not None else None}


def sim_run(project: Any, scenarios: list[str] | None = None, model: str | None = None, range_: str | None = None, vintage: str | None = None,
            vs: str | None = None, notify: Any = None) -> dict:
    """전망·시나리오(`equion sim`) — 고른 것을 차례로 풀어 기록을 남긴다(작업 하나). 시나리오면 같은 가정·보정항의 기준선도 풀어 차이를 적는다.

    돌려주는 것: `{ids, id(마지막 기록), failed, error}` — 앞의 것이 풀린 뒤에 하나가 실패하면 오류로 끊지 않고 남긴 기록과 까닭을 함께 돌려준다
    (하나도 풀지 못했으면 오류)."""
    names = list(dict.fromkeys(scenarios or ["base"]))
    made: list[str] = []
    for i, scenario in enumerate(names):
        if notify is not None and len(names) > 1:
            notify(line=f"{i + 1}/{len(names)} {scenario}")
        words: list[Any] = ["sim", scenario, *(["--model", model] if model else []), *(["--range", range_] if range_ else []),
                            *(["--vintage", vintage] if vintage else []), *(["--vs", vs] if vs else [])]
        try:
            rec = project.sim(scenario, model=model or None, range=range_ or None, vintage=vintage or None, vs=vs or None, who="desk", command=command(*words))
        except Exception as exc:
            if not made:
                raise
            return {"ids": made, "id": made[-1], "failed": scenario, "error": str(exc.args[0]) if isinstance(exc, KeyError) and exc.args else str(exc)}
        made.append(rec.id)
    return {"ids": made, "id": made[-1], "failed": None, "error": None}


def sim_view(project: Any, record: str) -> dict:
    """전망 기록 하나 — 수준·값의 종류(실측·해·가정·채움)·전기비·전년동기비·연간·기준선 대비 차이."""
    rec = project.work.get(record, "sim")
    meta = dict(rec.meta)

    def table(fname: str) -> Any:
        try:
            return rec.read_csv(fname)
        except (OSError, ValueError):
            return None

    levels, flags, growth, annual, diff = (table(f) for f in ("levels.csv", "flags.csv", "growth.csv", "annual.csv", "diff.csv"))
    names = [str(c) for c in levels.columns] if levels is not None else []
    out: dict[str, Any] = {"id": rec.id, "path": meta.get("path"), "vintage": _data_id(meta), "names": names,
                           "period": [str(i) for i in levels.index] if levels is not None else [],
                           "level": {n: [_float(v) for v in levels[n].tolist()] for n in names} if levels is not None else {},
                           "flag": {n: [str(v) for v in flags[n].tolist()] for n in names if flags is not None and n in flags.columns},
                           "qoq": {}, "yoy": {}, "annual": None, "diff": None}
    if growth is not None:
        for n in names:
            for key, col in (("qoq", f"{n}_전기비"), ("yoy", f"{n}_전년동기비")):
                if col in growth.columns:
                    out[key][n] = [_float(v) for v in growth[col].reindex(levels.index).tolist()]
    if annual is not None:
        out["annual"] = {"years": [str(i) for i in annual.index],
                         "level": {n: [_float(v) for v in annual[n].tolist()] for n in names if n in annual.columns},
                         "growth": {n: [_float(v) for v in annual[f"{n}_증가율"].tolist()] for n in names if f"{n}_증가율" in annual.columns}}
    if diff is not None:
        base = [c[:-3] for c in diff.columns if str(c).endswith("_차이")]
        out["diff"] = {"period": [str(i) for i in diff.index], "abs": {n: [_float(v) for v in diff[f"{n}_차이"].tolist()] for n in base},
                       "pct": {n: [_float(v) for v in diff[f"{n}_%"].tolist()] for n in base if f"{n}_%" in diff.columns}}
    keep = ("who", "command", "created", "model", "scenario", "range", "mode", "counts", "endogenous", "exogenous", "assume", "addfactors",
            "scenario_def", "vs_base", "vs", "implicit", "data")
    out["meta"] = {k: meta.get(k) for k in keep}
    return out


# ---- 보기 ----------------------------------------------------------------------------------------

def views(project: Any) -> dict:
    """저장한 보기(`VIEWS/*.toml`) — 어느 시리즈를 어떤 모양으로 볼지."""
    return {"views": [dict(v) for v in project.views()]}


def view_define(project: Any, name: str, series: list[str], show: str = "level", title: str | None = None) -> dict:
    """이 보기 저장(`equion view define`) — 시리즈와 보이기를 이름으로. 바뀜 기록에 남는다."""
    res = project.view_define(name, series=series, show=show, title=title or None, who="desk",
                              command=command("view", "define", name, "--series", ",".join(series), *(["--show", show] if show != "level" else []),
                                              *(["--title", title] if title else [])))
    return res.to_dict()


# ---- 보고서 · 엑셀 --------------------------------------------------------------------------------

def reports(project: Any) -> dict:
    """보고서 목록(`reports/*.md`) — 구역(기록에서 온 표·차트)의 수와 함께."""
    from equion.projects.reports import regions

    folder = os.path.join(str(project.root), "reports")
    try:
        files = sorted((f for f in os.listdir(folder) if f.lower().endswith(".md")), key=lambda f: -os.path.getmtime(os.path.join(folder, f)))
    except OSError:
        files = []
    out = []
    for f in files:
        path = os.path.join(folder, f)
        try:
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
            found = regions(text)
        except Exception:
            text, found = "", []
        title = next((ln[2:].strip() for ln in text.splitlines() if ln.startswith("# ")), "")
        out.append({"name": os.path.splitext(f)[0], "path": f"reports/{f}", "title": title, "regions": len(found), "mtime": os.path.getmtime(path),
                    "headings": _headings(text)})
    return {"reports": out}


def _headings(text: str) -> list[str]:
    """보고서의 작은 제목들(## · ### — 구역 안과 코드 블록 안은 뺀다). 보낼 곳을 고르는 데 쓴다."""
    out, inside, fence = [], False, False
    for ln in text.splitlines():
        s = ln.strip()
        if s.startswith("```"):
            fence = not fence
        elif s.startswith("<!-- equion:report "):
            inside = True
        elif s == "<!-- /equion:report -->":
            inside = False
        elif not fence and not inside and re.fullmatch(r"#{2,4} \S.*", s):
            out.append(s)
    return out[:60]


def _under(project: Any, report: str, under: str | None) -> str | None:
    """보낼 곳 — 제목 줄 그대로(`## 전망`)거나 제목의 글만(`전망`)이어도 받는다. 패키지는 줄 전체를 받으므로 글만 온 것은 그 줄을 찾아 준다."""
    if not under or under.lstrip().startswith("#"):
        return under or None
    path = os.path.join(str(project.root), "reports", f"{report}.md")
    try:
        with open(path, encoding="utf-8") as f:
            for ln in f:
                if ln.startswith("#") and ln.lstrip("#").strip() == under.strip():
                    return ln.strip()
    except OSError:
        pass
    return under


def report_new(project: Any, name: str, title: str | None = None, from_report: str | None = None) -> dict:
    res = project.report_new(name, title=title or None, from_report=from_report or None, who="desk",
                             command=command("report", "new", name, *(["--title", title] if title else []), *(["--from", from_report] if from_report else [])))
    return res.to_dict()


def report_add(project: Any, report: str, record: str, rows: list[str] | None = None, show: str = "level", annual: bool = False,
               digits: int | None = None, title: str | None = None, chart: bool = False, under: str | None = None) -> dict:
    """보고서로 보내기(`equion report add`) — 기록의 표(와 차트)를 고른 모양으로. 구역에는 어느 기록에서 왔는지가 적힌다."""
    under = _under(project, report, under)
    words: list[Any] = ["report", "add", report, record, *(["--rows", ",".join(rows)] if rows else []), *(["--show", show] if show != "level" else []),
                        *(["--annual"] if annual else []), *(["--digits", digits] if digits is not None else []), *(["--title", title] if title else []),
                        *(["--chart"] if chart else []), *(["--under", under] if under else [])]
    res = project.report_add(report, record, rows=rows or None, show=show, annual=bool(annual), digits=digits, title=title or None, chart=bool(chart),
                             under=under or None, who="desk", command=command(*words))
    return {**res.to_dict(), "command": command(*words)}


def report_check(project: Any, report: str) -> dict:
    return project.report_check(report).to_dict()


def report_update(project: Any, report: str, region: int | None = None, dry: bool = False, force: bool = False) -> dict:
    """새 기록으로 바꾸기(`equion report update`) — dry 면 바꾸지 않고 구역마다 무엇이 달라지는지(차이)만."""
    words = ["report", "update", report, *(["--region", region] if region else []), *(["--force"] if force else [])]
    res = project.report_update(report, region=region, dry_run=bool(dry), force=bool(force), who="desk", command=command(*words))
    return {**res.to_dict(), "command": command(*words)}


def export(project: Any, records: list[str], name: str) -> dict:
    """엑셀로(`equion export … --xlsx`) — 값·값의 종류·출처 시트. `exports/<이름>.xlsx`."""
    from equion.projects.config import ProjectError

    if not NAME.fullmatch(name):
        raise ProjectError(f"파일 이름 {name!r} — 영문으로 시작하고 영문·숫자·_·- 만")
    rel = f"exports/{name}.xlsx"
    res = project.export(records, rel)
    return {"path": rel, "sheets": res.get("sheets"), "records": res.get("records"), "command": command("export", *records, "--xlsx", rel)}
