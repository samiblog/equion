#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""보고서 폴더 — 실행 한 번의 표·그래프·로그·기록을 한 폴더에 남긴다.

    out/<실행ID>/
      report.html      모든 출력을 한 페이지로(그래프 포함, 인터넷 없이 열림)
      manifest.json    버전·git 커밋·매개변수·입력 파일 해시·풀이 상태·출력 목록·소요 시간
      run.log          화면 출력 그대로
      tables/          표 (csv · xlsx는 tables.xlsx 한 파일 · json)
      graphs/          그래프 (html) + 그래프 데이터 (csv · json)
      plotly.min.js    그래프용 스크립트(--plotlyjs copy일 때 — 패키지에 내장한 plotly.js, MIT)
"""

import html
import json
import math
import os
import platform
import re
import shutil
import subprocess
import sys
from typing import List

import numpy as np
import pandas as pd

from ..version import project_version
from .runner import PERIOD_KO, STATUS_KO, RunResult

FORMAT = "equion-run"
LEGACY_FORMATS = ("macromodel-run",)  # 0.4.0 이전(패키지 이름 변경 전) 보고서
FORMAT_VERSION = 2  # 2: versions에서 'engine' 제거(버전 하나로, D18)
DATA_FORMATS = ("csv", "xlsx", "json")
ALL_FORMATS = DATA_FORMATS + ("html",)
THREAD_VARS = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS")


# ---------------------------------------------------------------------------
# 환경 정보
# ---------------------------------------------------------------------------
def versions() -> dict:
    import scipy
    out = {"equion": project_version(), "python": platform.python_version(),
           "numpy": np.__version__, "pandas": pd.__version__, "scipy": scipy.__version__}
    try:
        cfg = np.show_config(mode="dicts")
        blas = cfg["Build Dependencies"]["blas"]
        out["blas"] = f"{blas.get('name')} {blas.get('version', '')}".strip()
    except Exception:  # noqa: BLE001 — numpy 빌드에 따라 없을 수 있다
        pass
    return out


def platform_info() -> dict:
    return {"system": platform.system(), "release": platform.release(), "machine": platform.machine(),
            "python_executable": sys.executable}


def threads_info() -> dict:
    return {k: os.environ.get(k) for k in THREAD_VARS if os.environ.get(k) is not None}


def git_info(path: str):
    """스크립트가 있는 git 저장소의 커밋·브랜치·변경 여부(git이 없거나 저장소가 아니면 None)."""
    cwd = os.path.dirname(os.path.abspath(path))

    def git(*args):
        r = subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=10)
        if r.returncode != 0:
            raise RuntimeError(r.stderr)
        return r.stdout.strip()
    try:
        return {"commit": git("rev-parse", "HEAD"), "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
                "dirty": bool(git("status", "--porcelain", "--untracked-files=no"))}
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------------------
# 보조
# ---------------------------------------------------------------------------
def _slug(text: str, limit: int = 40) -> str:
    s = re.sub(r"[^\w\-]+", "_", str(text or ""), flags=re.UNICODE).strip("_")
    return (s or "output")[:limit]


def _jsonable(o):
    if isinstance(o, dict):
        return {str(k): _jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple, set)):
        return [_jsonable(v) for v in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (float, np.floating)):
        f = float(o)
        return None if math.isnan(f) or math.isinf(f) else f
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, (pd.Timestamp, pd.Period)):
        return str(o)
    return o


def _write_json(path: str, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(_jsonable(obj), f, ensure_ascii=False, indent=2)
        f.write("\n")


def _frame_json(df: pd.DataFrame, meta: dict) -> dict:
    payload = json.loads(df.to_json(orient="split", date_format="iso", double_precision=15,
                                    default_handler=str))
    return {**meta, **payload}


def _sheet_name(stem: str, used: set) -> str:
    base = re.sub(r"[\[\]:*?/\\]", "_", stem)[:31]
    name, k = base, 2
    while name in used:
        tail = f"_{k}"
        name, k = base[:31 - len(tail)] + tail, k + 1
    used.add(name)
    return name


def prepare_dir(base: str, run_id: str, explicit: bool) -> str:
    """보고서 폴더를 만든다. 이름을 지정했고 이미 있으면, 그것이 이전 실행 보고서일 때만 비우고 다시 쓴다."""
    d = os.path.join(base, run_id)
    if os.path.exists(d):
        if not explicit:
            k = 2
            while os.path.exists(f"{d}_{k}"):
                k += 1
            d = f"{d}_{k}"
        else:
            man = os.path.join(d, "manifest.json")
            ok = False
            if os.path.isfile(man):
                try:
                    with open(man, encoding="utf-8") as f:
                        ok = json.load(f).get("format") in (FORMAT, *LEGACY_FORMATS)
                except (OSError, ValueError):
                    ok = False
            if not ok and os.listdir(d):
                raise FileExistsError(f"보고서 폴더가 이미 있고 이전 실행 보고서가 아닙니다(지우지 않음): {d}")
            shutil.rmtree(d)
    os.makedirs(d)
    return d


# ---------------------------------------------------------------------------
# 비밀 값 가리기·공유용 줄이기(--redact)
# ---------------------------------------------------------------------------
MASK = "***"


def collect_secrets(result: RunResult) -> set:
    from ..workfile.runtime import SENSITIVE_NAME, secret_values
    vals = secret_values()
    vals |= {str(v) for k, v in result.options.params.items() if SENSITIVE_NAME.search(k) and len(str(v)) >= 4}
    return vals


def scrub(text, secrets) -> str:
    if not isinstance(text, str):
        return text
    for s in sorted(secrets, key=len, reverse=True):
        text = text.replace(s, MASK)
    return text


def _protect(obj, secrets):
    from ..workfile.runtime import SENSITIVE_NAME
    if isinstance(obj, dict):
        return {k: (MASK if isinstance(k, str) and SENSITIVE_NAME.search(k) and isinstance(v, (str, int, float))
                    else _protect(v, secrets)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_protect(v, secrets) for v in obj]
    if isinstance(obj, str):
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", obj)        # --set 이름=값
        if m and SENSITIVE_NAME.search(m.group(1)):
            return f"{m.group(1)}={MASK}"
        return scrub(obj, secrets)
    return obj


def _short_path(p, cwd):
    if not isinstance(p, str) or not os.path.isabs(p):
        return p
    try:
        rel = os.path.relpath(p, cwd)
    except ValueError:                                  # Windows: 다른 드라이브
        return os.path.basename(p)
    return rel.replace(os.sep, "/") if not rel.startswith("..") else os.path.basename(p)   # 어느 OS에서나 '/'


def redact_manifest(man: dict) -> dict:
    """공유용: 작업 폴더·실행 파일 경로·git 브랜치를 빼고, 절대 경로를 작업 폴더 기준 상대 경로(밖이면 파일 이름)로."""
    man = json.loads(json.dumps(man, default=str))
    cwd = man.pop("cwd", os.getcwd())
    man.get("platform", {}).pop("python_executable", None)
    if man.get("git"):
        man["git"].pop("branch", None)
    man["script"] = _short_path(man.get("script"), cwd)
    man["argv"] = [_short_path(a, cwd) for a in man.get("argv", [])]
    for key in ("inputs", "written"):
        for d in man.get(key, []):
            d["path"] = _short_path(d.get("path"), cwd)
    man["redacted"] = True
    return man


def safe_manifest(result: RunResult, entries: list = None) -> dict:
    """보고서에 쓰는 manifest — 비밀 값을 가리고, --redact면 공유용으로 줄인다."""
    man = _protect(manifest(result, entries), collect_secrets(result))
    return redact_manifest(man) if result.options.redact else man


# ---------------------------------------------------------------------------
# 쓰기
# ---------------------------------------------------------------------------
def write_report(result: RunResult, directory: str) -> str:
    """실행 결과를 보고서 폴더에 쓴다. manifest.json 경로가 아니라 폴더 경로를 돌려준다."""
    opts = result.options
    formats = [f for f in opts.formats if f in ALL_FORMATS]
    want_html = "html" in formats
    entries, sheets = [], []
    has_graph = False
    for i, out in enumerate(result.outputs, 1):
        stem = f"{i:02d}_{_slug(out.name or out.title or out.kind)}"
        files: List[str] = []
        meta = {"title": out.title, "name": out.name}
        if out.kind == "table":
            os.makedirs(os.path.join(directory, "tables"), exist_ok=True)
            df = out.df
            meta.update({"head": out.head, "foot": out.foot})
            if "csv" in formats:
                p = f"tables/{stem}.csv"
                df.to_csv(os.path.join(directory, p), index=out.index, encoding="utf-8-sig")
                files.append(p)
            if "json" in formats:
                p = f"tables/{stem}.json"
                _write_json(os.path.join(directory, p), _frame_json(df if out.index else df.reset_index(drop=True), meta))
                files.append(p)
            if "xlsx" in formats:
                sheets.append((stem, df, out.index))
                files.append("tables.xlsx")
        elif out.kind == "graph":
            has_graph = True
            os.makedirs(os.path.join(directory, "graphs"), exist_ok=True)
            df = out.frame
            if "csv" in formats:
                p = f"graphs/{stem}.csv"
                df.to_csv(os.path.join(directory, p), encoding="utf-8-sig")
                files.append(p)
            if "json" in formats:
                p = f"graphs/{stem}.json"
                _write_json(os.path.join(directory, p), _frame_json(df, meta))
                files.append(p)
            if want_html:
                p = f"graphs/{stem}.html"
                js = "../plotly.min.js" if opts.plotlyjs == "copy" else "cdn"
                with open(os.path.join(directory, p), "w", encoding="utf-8") as f:
                    f.write(out.page(include_js=js))
                files.append(p)
        entries.append({"index": i, "kind": out.kind, "name": out.name, "title": out.title,
                        "anchor": f"out{i}", "files": files})

    if sheets:
        used = set()
        with pd.ExcelWriter(os.path.join(directory, "tables.xlsx")) as xw:
            for stem, df, index in sheets:
                df.to_excel(xw, sheet_name=_sheet_name(stem, used), index=index)
    if want_html and has_graph and opts.plotlyjs == "copy":
        from ..assets import plotly_js
        with open(os.path.join(directory, "plotly.min.js"), "wb") as f:
            f.write(plotly_js())

    secrets = collect_secrets(result)
    log_text = scrub(result.log, secrets)
    with open(os.path.join(directory, "run.log"), "w", encoding="utf-8") as f:
        f.write(log_text)
    man = safe_manifest(result, entries)
    files = {"manifest": "manifest.json", "log": "run.log"}
    if want_html:
        files["report"] = "report.html"
        with open(os.path.join(directory, "report.html"), "w", encoding="utf-8") as f:
            f.write(render_html(result, man, entries, log_text,
                                scrub((result.error or {}).get("traceback", ""), secrets)))
    man["files"] = files
    _write_json(os.path.join(directory, "manifest.json"), man)
    return directory


def solve_entries(result: RunResult) -> list:
    out = []
    for r in result.record.solves:
        st = r.sim.status
        out.append({"model": r.model, "scenario": r.scenario, "alias": r.alias, "mode": r.sim.mode,
                    "start": r.start, "end": r.end, "counts": r.counts(),
                    "periods": {str(s["period"]): s["status"] for s in st}})
    return out


def manifest(result: RunResult, entries: list = None) -> dict:
    opts, rec = result.options, result.record
    from ..workfile.runtime import file_digest
    script = os.path.abspath(opts.script)
    try:
        script_sha = file_digest(script)[0]
    except OSError:
        script_sha = None
    err = None
    if result.error:
        err = {"type": result.error["type"], "message": result.error["message"]}
    return {
        "format": FORMAT, "format_version": FORMAT_VERSION,
        "run_id": os.path.basename(result.report_dir) if result.report_dir else opts.run_id,
        "status": result.status, "exit_code": result.exit_code,
        "script": opts.script, "script_sha256": script_sha,
        "argv": list(opts.argv), "script_args": list(opts.script_args), "cwd": os.getcwd(),
        "params": {"overrides": dict(opts.params), "resolved": dict(rec.params),
                   "unused": result.unused_params()},
        "smpl": opts.smpl,
        "started_at": result.started.isoformat(timespec="seconds"),
        "finished_at": result.finished.isoformat(timespec="seconds"),
        "elapsed_sec": round(result.elapsed, 3),
        "fail_on": opts.fail_on, "fail_reasons": list(result.fail_reasons),
        "error": err,
        "versions": versions(), "platform": platform_info(), "threads": threads_info(),
        "git": git_info(script),
        "inputs": [{k: d[k] for k in ("path", "kind", "sha256", "bytes")} for d in rec.inputs],
        "written": list(rec.written),
        "solves": solve_entries(result),
        "outputs": [{k: e[k] for k in ("index", "kind", "name", "title", "files")} for e in (entries or [])],
    }


# ---------------------------------------------------------------------------
# report.html
# ---------------------------------------------------------------------------
_CSS = """
:root{--bg:#fbfbfa;--fg:#1d1f21;--muted:#6b7075;--line:#e3e3df;--card:#ffffff;--accent:#2f5d8a;
--ok:#2e7d4f;--warn:#a86b00;--bad:#b3261e;--code:#f3f3f1}
@media (prefers-color-scheme: dark){:root{--bg:#17191b;--fg:#e6e6e3;--muted:#9aa0a6;--line:#2c2f33;
--card:#1e2124;--accent:#8ab4e0;--ok:#6fcf97;--warn:#f2c46d;--bad:#f28b82;--code:#24272b}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.55 system-ui,-apple-system,"Segoe UI",
"Noto Sans KR","Malgun Gothic",sans-serif}
main{max-width:1100px;margin:0 auto;padding:24px 16px 64px}
h1{font-size:22px;margin:0 0 4px}h2{font-size:17px;margin:32px 0 10px;padding-bottom:4px;border-bottom:1px solid var(--line)}
.sub{color:var(--muted)}
.badge{display:inline-block;padding:2px 10px;border-radius:999px;font-weight:600;font-size:13px;color:#fff;vertical-align:middle;margin-left:8px}
.b-ok{background:var(--ok)}.b-warn{background:var(--warn)}.b-bad{background:var(--bad)}
.grid{display:grid;grid-template-columns:max-content 1fr;gap:4px 16px;margin-top:14px}
.grid div:nth-child(odd){color:var(--muted)}
.card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px 14px;margin:12px 0;overflow-x:auto}
.card h3{font-size:15px;margin:0 0 6px}
table{border-collapse:collapse;font-variant-numeric:tabular-nums}
th,td{padding:3px 10px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap}
th:first-child,td:first-child{text-align:left}
thead th{border-bottom:2px solid var(--line)}
pre{background:var(--code);padding:10px 12px;border-radius:6px;overflow-x:auto;font:12.5px/1.45 ui-monospace,Consolas,monospace}
.eqn-out div[style*="color"]{color:var(--muted)!important}
ol.toc{columns:2;padding-left:20px}@media (max-width:640px){ol.toc{columns:1}.grid{grid-template-columns:1fr}}
a{color:var(--accent)}code{font:12.5px ui-monospace,Consolas,monospace}
.files{font-size:12px;color:var(--muted);margin-top:6px}
details summary{cursor:pointer;color:var(--accent)}
footer{margin-top:40px;color:var(--muted);font-size:12px}
.err{border-color:var(--bad)}
"""


def _e(x) -> str:
    return html.escape("" if x is None else str(x))


def _badge(status: str) -> str:
    cls = {"ok": "b-ok", "solve_failed": "b-warn"}.get(status, "b-bad")
    return f'<span class="badge {cls}">{_e(STATUS_KO.get(status, status))}</span>'


def _kv_table(rows: List[list], head: List[str]) -> str:
    th = "".join(f"<th>{_e(h)}</th>" for h in head)
    body = "".join("<tr>" + "".join(f"<td>{_e(c)}</td>" for c in r) + "</tr>" for r in rows)
    return f"<table><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table>"


def render_html(result: RunResult, man: dict, entries: list, log_text: str = None, traceback_text: str = None) -> str:
    """보고서 한 페이지. 비밀 값·경로는 man(가린 manifest)과 log_text에서만 가져온다."""
    opts = result.options
    log_text = result.log if log_text is None else log_text
    title = f"실행 보고서 — {os.path.basename(opts.script)}"
    parts = [f"<!doctype html><html lang='ko'><head><meta charset='utf-8'>"
             f"<meta name='viewport' content='width=device-width,initial-scale=1'><title>{_e(title)}</title>"
             f"<style>{_CSS}</style>"]
    if any(e["kind"] == "graph" for e in entries):
        from ..assets import plotly_cdn
        src = "plotly.min.js" if opts.plotlyjs == "copy" else plotly_cdn()
        parts.append(f"<script charset='utf-8' src='{src}'></script>")
    parts.append("</head><body><main>")
    parts.append(f"<h1>{_e(os.path.basename(opts.script))}{_badge(result.status)}</h1>")
    parts.append(f"<div class='sub'>Equion 실행 보고서 · 실행 ID <code>{_e(man['run_id'])}</code></div>")

    params = ", ".join(f"{k}={v}" for k, v in man["params"]["resolved"].items()) or "(없음)"
    over = ", ".join(f"{k}={v}" for k, v in man["params"]["overrides"].items()) or "(없음)"
    git = man.get("git")
    grid = [("스크립트", man["script"]), ("시작", man["started_at"]), ("소요", f"{result.elapsed:.2f}초"),
            ("종료 코드", f"{result.exit_code} ({STATUS_KO.get(result.status, result.status)})"),
            ("기본 표본(--smpl)", opts.smpl or "(스크립트가 정함)"), ("매개변수", params),
            ("명령줄에서 준 값(--set)", over), ("실패 기준(--fail-on)", opts.fail_on)]
    if man["params"]["unused"]:
        grid.append(("쓰이지 않은 --set", ", ".join(man["params"]["unused"])))
    if git:
        grid.append(("git", (f"{git['branch']} @ " if git.get("branch") else "") + git["commit"][:10]
                     + (" (변경 있음)" if git["dirty"] else "")))
    if man.get("redacted"):
        grid.append(("공유용", "작업 폴더·실행 파일 경로·git 브랜치를 뺐습니다(--redact)"))
    parts.append("<div class='grid'>" + "".join(f"<div>{_e(k)}</div><div>{_e(v)}</div>" for k, v in grid)
                 + "</div>")

    if man.get("error"):
        tb = traceback_text if traceback_text is not None else (result.error or {}).get("traceback", "")
        parts.append("<h2>오류</h2><div class='card err'>"
                     f"<b>{_e(man['error']['type'])}</b>: {_e(man['error']['message'])}"
                     + (f"<pre>{_e(tb)}</pre>" if tb else "") + "</div>")
    if result.fail_reasons:
        parts.append("<h2>풀이 실패 조건</h2><div class='card err'><ul>"
                     + "".join(f"<li>{_e(r)}</li>" for r in result.fail_reasons) + "</ul></div>")

    if man["solves"]:
        rows = [[s["model"], f"{s['scenario']} ({s['alias']})", s["mode"], f"{s['start']}~{s['end']}",
                 *(s["counts"].get(k, 0) for k in PERIOD_KO)] for s in man["solves"]]
        parts.append("<h2>풀이</h2><div class='card'>"
                     + _kv_table(rows, ["모델", "시나리오", "방식", "구간", *PERIOD_KO.values()]) + "</div>")

    if entries:
        parts.append("<h2>출력</h2><ol class='toc'>"
                     + "".join(f"<li><a href='#{e['anchor']}'>{_e(e['title'] or e['name'] or e['kind'])}</a></li>"
                               for e in entries) + "</ol>")
        for e, out in zip(entries, result.outputs):
            parts.append(f"<div class='card' id='{e['anchor']}'>")
            if out.kind == "graph":
                parts.append(out.html(include_js=None, height="420px"))
            elif out.kind == "table":
                parts.append(out.html())
            else:
                if out.title:
                    parts.append(f"<h3>{_e(out.title)}</h3>")
                parts.append(f"<pre>{_e(out.data)}</pre>")
            if e["files"]:
                parts.append("<div class='files'>"
                             + " · ".join(f"<a href='{_e(p)}'>{_e(p)}</a>" for p in dict.fromkeys(e["files"]))
                             + "</div>")
            parts.append("</div>")

    if man["inputs"]:
        rows = [[d["path"], d["kind"], d["sha256"][:12], f"{d['bytes']:,}"] for d in man["inputs"]]
        parts.append("<h2>입력 파일</h2><div class='card'>"
                     + _kv_table(rows, ["경로", "종류", "sha256", "바이트"]) + "</div>")
    if man["written"]:
        rows = [[d["path"], d["kind"]] for d in man["written"]]
        parts.append("<h2>스크립트가 쓴 파일</h2><div class='card'>" + _kv_table(rows, ["경로", "종류"]) + "</div>")

    parts.append(f"<h2>실행 로그</h2><details><summary>run.log 펼치기</summary><pre>{_e(log_text)}</pre></details>")
    v = man["versions"]
    parts.append(f"<footer>Equion {_e(v['equion'])} · Python {_e(v['python'])} · "
                 f"numpy {_e(v['numpy'])} · pandas {_e(v['pandas'])} · scipy {_e(v['scipy'])}"
                 + (f" · BLAS {_e(v['blas'])}" if v.get("blas") else "")
                 + f" · {_e(man['finished_at'])}</footer>")
    parts.append("</main></body></html>")
    return "".join(parts)
