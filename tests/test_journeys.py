#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_journeys.py — 사용자의 관점에서 본 시나리오(docs/TEST_SCENARIOS.md의 J1~J7).

실행: uv run python tests/test_journeys.py   (종료코드 = 실패 수)

  J1. 한 해 운영 — 매달 새 원자료로 월간 스크립트(여섯 달): 짝짓기·회차·보고서·재연·정리·채택의 실행 이름·회차 다름
  J2. 사람과 Claude가 같은 폴더에서: 바깥 고침·채택 글자 어긋남·낡은 제안·채택 되돌리기·누가 claude
  J3. 실패와 회복: 망가진 받은 파일·중간 실패와 --from·Ctrl+C·남은 임시 폴더·깨진 설정·지워진 원자료
  J4. 적대적 입력: 프로젝트 밖 경로(보고서·노트·포함·py)·--set 선택지 끼우기·셸 문자·이름의 경로 문자
  J5. 이식성·재연: 공백·한글 경로·옮긴 프로젝트(절대 경로 없음)·다른 판·CRLF·BOM
  J6. 명령줄 사용성: 모든 --help·--json·cp949 출력·하위 폴더·오류의 다음 할 일
  J7. 규모: 기록 1,000개
자료는 예제 자료를 코드로 바꾼 합성 표만 쓴다(D30).
"""

import contextlib
import glob
import io
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import traceback

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import equion as eqn  # noqa: E402
from equion.cli import main as cli  # noqa: E402
from equion.cli.commands import build_parser  # noqa: E402
from equion.projects import Project  # noqa: E402
from equion.script import ScriptError  # noqa: E402
from equion.script.runner import compare_records  # noqa: E402

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  — {detail}" if detail else ""))


def quiet(fn, *a, **k):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return fn(*a, **k)


def run(args, where):
    out, err = io.StringIO(), io.StringIO()
    old = os.getcwd()
    os.chdir(where)
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = cli(list(args))
            except SystemExit as e:
                code = e.code
    finally:
        os.chdir(old)
    return code, out.getvalue(), err.getvalue()


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def write(path, text, newline="\n", bom=False):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8-sig" if bom else "utf-8", newline=newline) as f:
        f.write(text)


def new_project(base, name):
    d = os.path.join(base, name)
    return quiet(Project.create, d), d


def quarter(k):
    """2019Q4 다음 k번째 분기 라벨."""
    y, q = 2019 + (k + 3) // 4, (k + 3) % 4 + 1
    return f"{y}Q{q}"


def monthly_file(d, k):
    """k번째 달의 원자료(합성) — toy_q에 k분기를 더하고(분기 0.4% + 작은 굴곡) 지난달의 새 분기 소비를 0.1% 고친 표. 받은 상자에 놓는다."""
    df = pd.read_csv(os.path.join(d, "DATA", "raw", "toy_q.csv"), index_col=0)
    last = df.loc["2019Q4"]
    for j in range(1, k + 1):
        df.loc[quarter(j)] = last * (1.004 ** j) * (1 + 0.002 * math.sin(j))
    if k > 1:
        df.loc[quarter(k - 1), "CN"] *= 1.001
    name = f"toy_q_{quarter(k)}.csv"
    df.to_csv(os.path.join(d, "DATA", "raw", "inbox", name))
    return name


def last_run(p_root):
    return quiet(Project.open, p_root).work.records("run")[-1]


def main():
    t0 = time.time()
    tmp = tempfile.mkdtemp(prefix="eqn-journeys-")
    old_verbose = eqn.verbose()
    eqn.verbose(0)
    saved_env = {k: os.environ.get(k) for k in ("EQUION_WHO", "CLAUDECODE")}
    os.environ.pop("EQUION_WHO", None)
    os.environ.pop("CLAUDECODE", None)
    try:
        return _main(tmp, t0)
    finally:
        eqn.verbose(old_verbose)
        for k, v in saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(tmp, ignore_errors=True)


def _main(tmp, t0):
    j1(tmp)
    j2(tmp)
    j3(tmp)
    j4(tmp)
    j5(tmp)
    j6(tmp)
    j7(tmp)
    print()
    print(f"결과: {len(PASS)}/{len(PASS) + len(FAIL)} 통과 ({time.time() - t0:.1f}초)")
    if FAIL:
        print("실패:", ", ".join(FAIL))
    return len(FAIL)


# ---------------------------------------------------------------------------
def j1(tmp):
    print("\n== J1. 한 해 운영 — 매달 새 원자료로 월간 스크립트 ==")
    p, d = new_project(tmp, "year")
    v0 = p.vintage
    codes, names, errs = [], [], []
    for k in range(1, 7):
        names.append(monthly_file(d, k))
        code, out, err = run(["run", "FLOWS/monthly.eqs", "-q", "--set", "scenarios=base"], d)
        codes.append(code)
        if code:
            errs.append(f"{k}달: {(out + err).strip().splitlines()[-1][:160]}")
    p = quiet(Project.open, d)
    src = read(os.path.join(d, "DATA", "series.toml"))
    check("J1.1 여섯 달 모두 받은 파일이 출처 na로 짝지어지고 종료 코드 0", codes == [0] * 6
          and f'file = "DATA/raw/{names[-1]}"' in src and os.listdir(os.path.join(d, "DATA", "raw", "inbox")) == [],
          "; ".join(errs))
    vs = [v["id"] for v in p.data_list()]
    reps = sorted(os.path.basename(x) for x in glob.glob(os.path.join(d, "reports", "forecast_*.md")))
    xls = glob.glob(os.path.join(d, "exports", "forecast_*.xlsx"))
    check("J1.2 회차 1+6 · 달마다 보고서와 엑셀 · 자료 끝이 분기씩 밀림", len(vs) == 7 and vs[0] == v0 and p.vintage == vs[-1]
          and len(reps) == 6 and len(xls) == 6 and p.span("last:last")[1] == quarter(6), f"회차 {vs} · 보고서 {len(reps)}")
    runs = p.work.records("run")
    second = runs[1].id if len(runs) > 1 else "run:monthly_0002"
    code, out, err = run(["run", "--replay", second, "-q"], d)
    check("J1.3 둘째 달의 실행을 여섯 달 뒤에 재연 — 단계마다 같음", code == 0 and "모두 같음" in out, (out + err)[-400:])
    code, out, _ = run(["work", "clean", "--yes"], d)
    rec2 = quiet(Project.open, d).work.get(second)
    alive = all(_exists(d, r) for s in rec2.meta["steps"] for r in s["records"] if not r.startswith("data:"))
    code2, out2, err2 = run(["run", "--replay", second, "-q"], d)
    check("J1.4 정리(work clean --yes) 뒤에도 실행 기록의 단계 기록이 남아 재연이 된다", code == 0 and alive and code2 == 0
          and "모두 같음" in out2, (out2 + err2)[-300:])
    chs = [c for c in quiet(Project.open, d).history.list() if "EQUATIONS/adopted.toml" in c.files]
    check("J1.5 채택표의 바뀜마다 그 실행 이름 · 누가 '스크립트'", chs and all(c.run and c.run.startswith("run:monthly_") and c.who == "script"
                                                                 for c in chs), str([(c.id, c.who, c.run) for c in chs][:3]))
    code, out, _ = run(["work", "list", "--kind", "run", "--limit", "0"], d)
    rows = [x for x in out.splitlines() if x.strip().startswith("run:monthly_")]
    last = [x for x in rows if runs[-1].id in x]
    check("J1.6 지난달 실행에는 '회차 다름', 이번 달 것에는 없음", code == 0 and last and "회차 다름" not in last[0]
          and any("회차 다름" in x for x in rows if runs[0].id in x), "\n".join(rows[:3]))


def _exists(d, rid):
    try:
        quiet(Project.open, d).work.get(rid)
        return True
    except Exception:  # noqa: BLE001
        return False


# ---------------------------------------------------------------------------
def j2(tmp):
    print("\n== J2. 사람과 Claude가 같은 폴더에서 ==")
    p, d = new_project(tmp, "together")
    demand = os.path.join(d, "EQUATIONS", "demand.txt")
    orig = read(demand)
    run(["history", "list"], d)                       # 지금 내용을 기준으로
    write(demand, orig.replace("# 수요 블록", "# 수요 블록(사람이 편집기로 고침)"))
    code, out, _ = run(["history", "list"], d)
    check("J2.1 편집기로 고친 블록 파일 → 바뀜 기록에 '바깥'", code == 0 and "바깥" in out and "EQUATIONS/demand.txt" in out)
    run(["est", "demand:I", "--as", "i1"], d)
    run(["adopt", "est:i1"], d)
    write(demand, read(demand).replace("I c Y(-1) R", "I c Y R"))
    code, out, err = run(["hs", "main", "--as", "h_mismatch"], d)
    check("J2.2 채택 기록과 블록 글자가 다르면 알리고 지금 자료로 추정", code == 0 and "est:i1의 식이 블록 파일과 다릅니다" in out,
          out[-300:])
    write(demand, orig)
    run(["history", "list"], d)
    run(["est", "CN c Y CN(-1) CN(-2)", "--for", "demand:CN", "--as", "cn2"], d)
    os.environ["CLAUDECODE"] = "1"
    try:
        code, out, _ = run(["propose", "new", "p1", "--title", "소비 식에 시차 하나 더", "--why", "est:cn2", "--part",
                            "demand:CN=est:cn2"], d)
        e = run(["est", "demand:CN", "--as", "by_claude"], d)
    finally:
        os.environ.pop("CLAUDECODE", None)
    write(demand, read(demand).replace("# 소비", "# 소비(사람)"))
    c1, o1, e1 = run(["propose", "apply", "p1"], d)
    c2, o2, _ = run(["propose", "apply", "p1", "--force"], d)
    check("J2.3 그 사이 사람이 고친 파일 → 제안 적용은 낡음으로 거절(3), --force로만", code == 0 and c1 == 3 and "낡" in (o1 + e1)
          and c2 == 0, (o1 + e1)[-200:])
    rec = quiet(Project.open, d).work.get("est:by_claude")
    pr = [c for c in quiet(Project.open, d).history.list() if "propose" in c.how]
    check("J2.5 Claude Code 안에서 만든 기록 → 누가 'claude'", e[0] == 0 and rec.meta["who"] == "claude")
    q, dq = new_project(tmp, "revert")
    run(["hs", "main", "--as", "h_before"], dq)
    run(["est", "CN c Y CN(-1) CN(-2)", "--for", "demand:CN", "--as", "cn2"], dq)
    code, out, _ = run(["adopt", "est:cn2"], dq)
    cid = re.search(r"바뀜 기록\s+(h\d{4})", out)
    run(["hs", "main", "--as", "h_adopted"], dq)
    code2, out2, err2 = run(["history", "revert", cid[1] if cid else "h0000"], dq)
    run(["hs", "main", "--as", "h_after"], dq)
    w = quiet(Project.open, dq).work
    same = compare_records(w.get("hs:h_before"), w.get("hs:h_after")) == []
    diff = compare_records(w.get("hs:h_before"), w.get("hs:h_adopted")) != []
    check("J2.4 채택을 되돌리면 HS 숫자가 채택 전과 같다", code == 0 and code2 == 0 and same and diff, (out2 + err2)[-200:])
    del pr


# ---------------------------------------------------------------------------
def j3(tmp):
    print("\n== J3. 실패와 회복 ==")
    p, d = new_project(tmp, "recover")
    v0 = p.vintage
    st0 = read(os.path.join(d, "DATA", "series.toml"))
    bad = os.path.join(d, "DATA", "raw", "inbox", "toy_q_2020Q1.csv")
    with open(bad, "wb") as f:
        f.write(b"\x00\x01\x02 not a table \xff\xfe\n,,,\n")
    code, out, err = run(["run", "FLOWS/monthly.eqs", "-q"], d)
    q = quiet(Project.open, d)
    r = q.work.records("run")[-1].meta
    check("J3.1 망가진 받은 파일 → 1단계에서 3으로 멈추고 회차·정의·받은 상자 그대로", code == 3 and q.vintage == v0
          and read(os.path.join(d, "DATA", "series.toml")) == st0 and os.path.isfile(bad) and r["steps"][0]["status"] == "error"
          and len(r["steps"]) == 1, (out + err)[-300:])
    os.remove(bad)
    oil = os.path.join(d, "SCENARIOS", "oil20.toml")
    shutil.move(oil, oil + ".bak")
    code, out, err = run(["run", "FLOWS/monthly.eqs", "-q"], d)
    r = last_run(d).meta
    st = [s["status"] for s in r["steps"]]
    check("J3.2a 중간 단계 실패(시나리오 파일 없음) → 그 단계에서 멈춤, 뒤 단계는 하지 않는다", code == 3 and st[-1] == "error"
          and len(st) == 6 and r["steps"][-1]["line"].startswith("sim"), str(st))
    shutil.move(oil + ".bak", oil)
    code, out, err = run(["run", "FLOWS/monthly.eqs", "-q", "--from", "전망"], d)
    r = last_run(d).meta
    check("J3.2b 고친 뒤 --from 전망으로 이어서 끝까지", code == 0 and [s["status"] for s in r["steps"]][:5] == ["skip"] * 5
          and r["steps"][-1]["status"] == "ok", (out + err)[-300:])
    S = sys.modules["equion.script.session"]          # 모듈(같은 이름의 함수 eqn.script.session과 다르다)
    orig = S.Session._call

    def interrupted(self, toks):
        if toks and toks[0] == "hs":
            raise KeyboardInterrupt
        return orig(self, toks)
    S.Session._call = interrupted
    try:
        res = quiet(quiet(Project.open, d).run_script, "FLOWS/monthly.eqs")
    finally:
        S.Session._call = orig
    tmps = glob.glob(os.path.join(d, "work", "*", ".tmp-*"))
    check("J3.3 Ctrl+C → 130 · 실행 기록 '중단' · 반쯤 쓴 기록 없음", res.exit_code == 130 and res.status == "interrupted"
          and not tmps and len(res.steps) == 3, f"{res.exit_code} {res.status} {tmps}")
    junk = os.path.join(d, "work", "hs", ".tmp-hs_9999")
    write(os.path.join(junk, "record.json"), "{ 반쯤")
    c1, o1, _ = run(["work", "list"], d)
    c2, o2, _ = run(["hs", "main"], d)
    check("J3.4 남은 임시 폴더가 있어도 목록·다음 실행 정상", c1 == 0 and c2 == 0 and ".tmp" not in o1
          and re.search(r"\[hs:hs_\d{4}\]", o2) is not None, o2[:120])
    cfg = os.path.join(d, "equion.toml")
    good = read(cfg)
    write(cfg, good + "\n[[[깨짐\n")
    c1, o1, e1 = run(["work", "list"], d)
    c2, o2, _ = run(["guide", "--path"], d)
    write(cfg, good)
    check("J3.5 깨진 equion.toml → 3과 위치(line·column), guide는 된다", c1 == 3 and "line" in e1 and c2 == 0, e1[-160:])
    c0, _, _ = run(["run", "FLOWS/monthly.eqs", "-q", "--set", "scenarios=base"], d)   # 자료 단계까지 다 돈 실행 하나
    full = last_run(d).id
    os.remove(os.path.join(d, "DATA", "raw", "toy_m.csv"))
    c1, o1, e1 = run(["data", "build"], d)
    c2, o2, e2 = run(["run", "--replay", full, "-q"], d)
    check("J3.6 지워진 원자료 → data build가 그 파일을 말하고(3), 재연은 다름(2)과 까닭", c0 == 0 and c1 == 3 and "toy_m.csv" in e1
          and c2 == 2 and "toy_m.csv" in (o2 + e2), (o2 + e2)[-300:])


# ---------------------------------------------------------------------------
def j4(tmp):
    print("\n== J4. 적대적 입력 ==")
    p, d = new_project(tmp, "adv")
    outside = os.path.join(tmp, "outside")
    os.makedirs(outside, exist_ok=True)
    before = set(os.listdir(tmp)) | set(os.listdir(outside)) | set(os.listdir(os.path.dirname(tmp)))
    c1, o1, e1 = run(["report", "new", "../../evil_report"], d)
    c2, o2, e2 = run(["report", "new", os.path.join(outside, "abs_report.md")], d)
    after = set(os.listdir(tmp)) | set(os.listdir(outside)) | set(os.listdir(os.path.dirname(tmp)))
    check("J4.1 보고서 이름이 프로젝트 밖(../..·절대 경로) → 3, 밖에 파일 없음", c1 == 3 and c2 == 3
          and not any("evil_report" in x or "abs_report" in x for x in after - before), (o1 + e1)[-150:])
    note = os.path.join(outside, "note.md")
    write(note, "# 밖\n\n```equion\nassemble main\n```\n")
    c1, o1, e1 = run(["note", "run", note], d)
    c2, o2, e2 = run(["note", "run", "../outside/note.md"], d)
    check("J4.2 프로젝트 밖의 노트 → 3, 밖의 파일은 그대로", c1 == 3 and c2 == 3 and "equion:out" not in read(note), (o1 + e1)[-150:])
    write(os.path.join(outside, "x.eqs"), "assemble main\n")
    write(os.path.join(outside, "x.py"), "print('밖')\n")
    write(os.path.join(d, "FLOWS", "esc1.eqs"), "run ../outside/x.eqs\n")
    write(os.path.join(d, "FLOWS", "esc2.eqs"), "py ../outside/x.py\n")
    write(os.path.join(d, "FLOWS", "esc3.eqs"), f"run {os.path.join(outside, 'x.eqs').replace(os.sep, '/')}\n")
    res = [run(["check", f"FLOWS/esc{i}.eqs"], d) for i in (1, 2, 3)]
    check("J4.3 스크립트의 포함·py가 프로젝트 밖 → 검사 문제(3)", all(c == 3 and "프로젝트 밖" in (o + e) for c, o, e in res),
          " | ".join((o + e).strip()[-90:] for _, o, e in res))
    write(os.path.join(d, "FLOWS", "inj.eqs"), "param who = base\nparam x = 1\nsim {who}\n")
    c1, o1, e1 = run(["run", "FLOWS/inj.eqs", "--dry-run", "--set", "who=base --model core"], d)
    c2, o2, e2 = run(["run", "FLOWS/inj.eqs", "--dry-run", "--set", "x=-0.5"], d)
    check("J4.4 --set 값으로 선택지 끼우기는 거절(3) · 음수는 된다", c1 == 3 and "선택지" in (o1 + e1) and c2 == 0, (o1 + e1)[-150:])
    nb = os.path.join(d, "notes", "shell.md")
    write(nb, "# 셸\n\n```equion\nassemble main; echo hacked > hacked.txt\n```\n\n```equion\nassemble main && echo x > x.txt\n```\n\n"
              "```equion\nhs $(whoami)\n```\n\n```equion\nwork list | tee t.txt\n```\n")
    c, o, e = run(["note", "run", "notes/shell.md"], d)
    made = [x for x in ("hacked.txt", "x.txt", "t.txt") if os.path.exists(os.path.join(d, x)) or os.path.exists(os.path.join(ROOT, x))]
    check("J4.5 노트 블록의 셸 문자는 셸로 돌지 않는다(파일이 생기지 않음)", not made and c in (1, 3) and "오류" in o, o[-300:])
    c1, _, _ = run(["est", "demand:CN", "--as", "../x"], d)
    c2, _, _ = run(["report", "new", ""], d)
    c3, _, _ = run(["script", "new", "../x"], d)
    c4, _, _ = run(["run", "FLOWS/monthly.eqs", "--run-id", "../x"], d)
    c5, _, _ = run(["est", "demand:CN", "--as", "a\\b"], d)
    check("J4.6 이름의 경로 문자·빈 이름 → 3", (c1, c2, c3, c4, c5) == (3, 3, 3, 3, 3), str((c1, c2, c3, c4, c5)))


# ---------------------------------------------------------------------------
def j5(tmp):
    print("\n== J5. 이식성·재연 ==")
    p, d = new_project(tmp, "월간 모형 폴더")
    c1, o1, e1 = run(["run", "FLOWS/monthly.eqs", "-q", "--set", "scenarios=base"], d)
    c2, o2, e2 = run(["run", "--replay", "run:monthly_0001", "-q"], d)
    check("J5.1 공백·한글 경로에서 실행·재연", c1 == 0 and c2 == 0 and "모두 같음" in o2, (o2 + e2)[-200:])
    d2 = os.path.join(tmp, "copied")
    shutil.copytree(d, d2)
    c, o, e = run(["run", "--replay", "run:monthly_0001", "-q"], d2)
    leaks = []
    for f in glob.glob(os.path.join(d2, "work", "**", "*.json"), recursive=True) + [os.path.join(d2, "work", "log.jsonl")]:
        t = read(f)
        for root in (d, d2):
            for form in (root, root.replace("\\", "/"), root.replace("\\", "\\\\")):
                if form in t:
                    leaks.append(os.path.relpath(f, d2))
    check("J5.2 옮긴 프로젝트에서 재연 같음 · 기록에 절대 경로 없음", c == 0 and "모두 같음" in o and not leaks,
          f"{(o + e)[-120:]} · {sorted(set(leaks))[:4]}")
    rj = os.path.join(d2, "work", "run", "monthly_0001", "record.json")
    m = json.loads(read(rj))
    m["versions"]["equion"] = "0.0.1"
    write(rj, json.dumps(m, ensure_ascii=False, indent=2))
    c, o, e = run(["run", "--replay", "run:monthly_0001"], d2)
    check("J5.3 다른 판의 실행을 재연 → 판이 다르다고 알리고 허용오차로", c == 0 and "판이 다릅니다" in o and "0.0.1" in o, o[-200:])
    write(os.path.join(d, "FLOWS", "crlf.eqs"), "# CRLF와 BOM\n## 묶음\nparam s = base\nassemble main\nsim {s} --as crlf_sim\n",
          newline="\r\n", bom=True)
    write(os.path.join(d, "notes", "crlf.md"), "# CRLF 노트\n\n```equion\nassemble main\n```\n", newline="\r\n", bom=True)
    c1, o1, e1 = run(["run", "FLOWS/crlf.eqs", "-q"], d)
    c2, o2, e2 = run(["note", "run", "notes/crlf.md"], d)
    c3, o3, _ = run(["note", "check", "notes/crlf.md"], d)
    check("J5.4 CRLF·BOM 스크립트·노트가 돈다(다시 검사해도 정상)", c1 == 0 and c2 == 0 and c3 == 0 and "정상" in o3,
          (o1 + e1 + o2 + e2 + o3)[-300:])


# ---------------------------------------------------------------------------
def _help_paths():
    import argparse
    out = []

    def walk(parser, path):
        out.append(path)
        for a in parser._actions:
            if isinstance(a, argparse._SubParsersAction):
                for name, sp in a.choices.items():
                    walk(sp, path + [name])
    walk(build_parser(), [])
    return out


def j6(tmp):
    print("\n== J6. 명령줄 사용성 ==")
    paths = _help_paths()
    bad = []
    for path in paths:
        code, out, err = run([*path, "--help"], ROOT)
        if code != 0 or not out.strip():
            bad.append(" ".join(path) + f" → {code} {err.strip()[-80:]}")
    check(f"J6.1 명령·하위 동작 {len(paths)}개의 --help가 모두 0", not bad and len(paths) > 60, "; ".join(bad[:4]))
    p, d = new_project(tmp, "cli")
    run(["est", "demand:CN", "--as", "c1"], d)
    run(["hs", "main", "--as", "h1"], d)
    run(["sim", "base", "--as", "s1"], d)
    run(["report", "new", "memo"], d)
    run(["report", "add", "memo", "sim:s1"], d)
    run(["run", "FLOWS/monthly.eqs", "-q", "--set", "scenarios=base"], d)
    cmds = [["assemble", "main"], ["data", "list"], ["data", "inbox"], ["work", "list"], ["work", "show", "hs:h1"],
            ["work", "show", "run:monthly_0001"], ["history", "list"], ["an", "list"], ["report", "check", "memo"],
            ["note", "check", "notes/data_check.md"], ["check", "FLOWS/monthly.eqs"], ["run", "FLOWS/monthly.eqs", "--dry-run"],
            ["compare", "--part", "demand:CN"], ["est", "demand:CN"], ["hs", "main"], ["sim", "base"], ["ident", "demand:Y", "--check"],
            ["propose", "list"], ["an", "summary", "core"]]
    bad = []
    for c in cmds:
        code, out, err = run([*c, "--json"], d)
        try:
            json.loads(out)
        except ValueError:
            bad.append(f"{' '.join(c)} → {code} {(out + err).strip()[:80]}")
    check(f"J6.2 --json 읽기·계산 명령 {len(cmds)}개의 출력이 JSON", not bad, "; ".join(bad[:4]))
    env = dict(os.environ, PYTHONIOENCODING="cp949")
    probs = []
    for args in (["run", "FLOWS/monthly.eqs", "--dry-run"], ["work", "show", "run:monthly_0001"], ["guide"], ["check", "FLOWS/monthly.eqs"]):
        r = subprocess.run([sys.executable, "-m", "equion", *args], cwd=d, capture_output=True, env=env, stdin=subprocess.DEVNULL)
        text = (r.stdout + r.stderr).decode("cp949", errors="replace")
        if r.returncode != 0 or "Traceback" in text or "UnicodeEncodeError" in text:
            probs.append(f"{' '.join(args)} → {r.returncode} {text[-120:]}")
    check("J6.3 출력이 cp949여도 멈추지 않는다", not probs, "; ".join(probs[:2]))
    c1, o1, e1 = run(["assemble", "main"], os.path.join(d, "FLOWS"))
    c2, o2, e2 = run(["work", "list"], os.path.join(d, "notes"))
    c3, o3, e3 = run(["run", "monthly.eqs", "--dry-run"], os.path.join(d, "FLOWS"))
    check("J6.4 프로젝트 하위 폴더에서도 프로젝트를 찾는다", (c1, c2, c3) == (0, 0, 0), (e1 + e2 + e3)[-200:])
    cases = [(["est", "demand:ZZ"], "있는 부품"), (["work", "show", "est:nope"], "없는 기록"), (["hs", "nomodel"], "main"),
             (["sim", "zz9"], "SCENARIOS"), (["report", "add", "nope", "sim:s1"], "report new"), (["adopt", "est:nope"], "없는 기록"),
             (["note", "run", "notes/none.md"], "없습니다")]
    bad = []
    for args, hint in cases:
        code, out, err = run(args, d)
        if code != 3 or hint not in err:
            bad.append(f"{' '.join(args)} → {code} {err.strip()[-90:]}")
    check(f"J6.5 흔한 오류 {len(cases)}가지 — 3과 다음 할 일", not bad, "; ".join(bad[:3]))


# ---------------------------------------------------------------------------
def j7(tmp):
    print("\n== J7. 규모 ==")
    p, d = new_project(tmp, "big")
    e = quiet(p.est, "demand:CN", as_name="seed")
    store = p.work
    src = store.get(e.id)
    files = {"coefs.csv": src.read_csv("coefs.csv")}
    t0 = time.time()
    for i in range(1000):
        meta = dict(src.meta)
        meta.pop("id", None)
        store.write("est", f"syn_{i:04d}", meta, files, "# 합성 기록\n", log={"metric": "합성"})
    t_write = time.time() - t0
    t0 = time.time()
    code0, out0, _ = run(["work", "list"], d)          # 기본(최근 30) — 막 쓴 기록 그대로(차가운 디스크)
    t_default = time.time() - t0
    run(["work", "list", "--limit", "0"], d)            # 한 번 읽어 두고(운영 중에는 기록이 몇 달에 걸쳐 쌓인다)
    t0 = time.time()
    code, out, _ = run(["work", "list", "--limit", "0"], d)
    t_list = time.time() - t0
    t0 = time.time()
    nxt = store.next_name("est", "syn")
    t_next = time.time() - t0
    run(["report", "new", "big"], d)
    run(["report", "add", "big", "est:syn_0999"], d)
    t0 = time.time()
    c2, o2, _ = run(["report", "check", "big"], d)
    t_check = time.time() - t0
    check("J7.1 기록 1,000개 — work list(기본·전부)·다음 이름·report check가 몇 초 안", code0 == 0 and len(out0.splitlines()) == 31
          and code == 0 and len(out.splitlines()) > 1000 and nxt == "syn_1000" and c2 == 0 and t_default < 3 and t_list < 8
          and t_next < 1 and t_check < 5,
          f"쓰기 {t_write:.1f}초 · 기본 목록 {t_default:.2f}초 · 전부 {t_list:.1f}초 · 다음 이름 {t_next:.2f}초 · 보고서 검사 {t_check:.1f}초")


def test_suite():
    """pytest 진입점 — 이 파일의 검사 묶음 전체(하나라도 실패하면 실패). `python tests/test_journeys.py`와 같은 검사."""
    assert main() == 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(99)
