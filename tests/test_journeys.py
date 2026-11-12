#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_journeys.py — 사용자의 관점에서 본 시나리오(docs/TEST_SCENARIOS.md의 J1~J12).

실행: uv run python tests/test_journeys.py   (종료코드 = 실패 수)

  J1. 한 해 운영 — 매달 새 원자료로 월간 스크립트(여섯 달): 짝짓기·회차·보고서·재연·정리·채택의 실행 이름·회차 다름
  J2. 사람과 Claude가 같은 폴더에서: 바깥 고침·채택 글자 어긋남·낡은 제안·채택 되돌리기·누가 claude
  J3. 실패와 회복: 망가진 받은 파일·중간 실패와 --from·Ctrl+C·남은 임시 폴더·깨진 설정·지워진 원자료
  J4. 적대적 입력: 프로젝트 밖 경로(보고서·노트·포함·py)·--set 선택지 끼우기·셸 문자·이름의 경로 문자
  J5. 이식성·재연: 공백·한글 경로·옮긴 프로젝트(절대 경로 없음)·다른 판·CRLF·BOM
  J6. 명령줄 사용성: 모든 --help·--json·cp949 출력·하위 폴더·오류의 다음 할 일
  J7. 규모: 기록 1,000개
  J8. 2차판 — 달을 넘는 요인 나누기·이정표·다른 PC로 보내기·시점이 열로 가는 표의 개정·나쁜 묶음
  J9. 여러 달 운영 — 지난 값 개정·새 열·지난 파일을 다시 받음·보고서의 회차·이름 겹침·재연·이정표 되돌리기와 그 되돌림
  J10. 끊김과 동시 실행 — 월간 스크립트를 세 곳에서 강제 종료·채택 셋·추정 넷을 같은 순간에(프로세스마다)
  J11. 낯선 받은 파일 — 단위 줄 빠짐·열 이름 바뀜·줄바꿈만 바뀐 정의 파일의 되돌리기·최근 8기만 든 파일
  J12. 풀리지 않는 모형 — 해가 없는 동시 블록·서로 종속인 항등식·선행변수·해만 적은 구간
자료는 예제 자료를 코드로 바꾼 합성 표만 쓴다(D30).
"""

import contextlib
import glob
import hashlib
import io
import json
import math
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import zipfile

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
    j8(tmp)
    j9(tmp)
    j10(tmp)
    j11(tmp)
    j12(tmp)
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
            ["propose", "list"], ["an", "summary", "core"], ["data", "diff"]]       # data diff — 회차가 하나라 오류도 JSON
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
    bad = []
    for args, hint in cases + [(["hs", "--range"], "값이 하나"), (["run", "FLOWS/nope.eqs"], "스크립트가 없습니다"),
                               (["data", "diff"], "견줄 회차")]:
        code, out, err = run([*args, "--json"], d)
        try:
            e = json.loads(out)["error"]
            ok = code == 3 and e["exit_code"] == 3 and e["kind"] == "input" and hint in e["message"] and not err.strip()
        except (ValueError, KeyError, TypeError):
            ok = False
        if not ok:
            bad.append(f"{' '.join(args)} → {code} {(out + err).strip()[:90]}")
    from equion.cli import workcmds
    orig = workcmds.dispatch
    workcmds.dispatch = lambda *a, **k: 1 / 0
    try:
        c1, o1, e1 = run(["work", "list", "--json"], d)
        try:
            err1 = json.loads(o1)["error"]
        except (ValueError, KeyError):
            err1 = {}
        raised = False
        try:
            run(["work", "list"], d)
        except ZeroDivisionError:
            raised = True
    finally:
        workcmds.dispatch = orig
    check("J6.6 --json이면 오류도 JSON 하나(표준출력) — 입력 오류·사용법 오류·내부 오류(1, 트레이스백 끝)", not bad and c1 == 1
          and err1.get("internal") is True and err1.get("type") == "ZeroDivisionError" and "Traceback" in err1.get("traceback", "")
          and raised, "; ".join(bad[:3]) or o1[-200:])
    code, out, err = run(["est", "demand:ZZ"], d)
    check("J6.7 --json이 없으면 지금처럼 — 표준오류 한 줄 · 표준출력은 비어 있음", code == 3 and not out.strip()
          and err.startswith("equion: 오류: 없는 부품"))


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


# ---------------------------------------------------------------------------
def _split_rows(out):
    """an split 카드의 '변수 연도 성장률 앞 → 뒤 (바뀜)  자료 · 가정 · 식' 줄."""
    return [x.strip() for x in out.splitlines() if "성장률" in x and "자료" in x]


def _leaks(folder, roots):
    bad = []
    for f in glob.glob(os.path.join(folder, "**", "*"), recursive=True):
        if not os.path.isfile(f) or not f.endswith((".json", ".jsonl", ".md", ".toml", ".txt", ".eqs")):
            continue
        t = read(f)
        for root in roots:
            for form in (root, root.replace("\\", "/"), root.replace("\\", "\\\\")):
                if form in t:
                    bad.append(os.path.relpath(f, folder))
    return sorted(set(bad))


def _evil(path, entries, manifest=None, top="evil"):
    """나쁜 묶음 — entries: [(zip 안의 이름, 내용)]."""
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(f"{top}/bundle.json", json.dumps(manifest or {"format": "equion-bundle", "format_version": 1, "project": top}))
        z.writestr(f"{top}/equion.toml", '[project]\nname = "evil"\n')
        for name, text in entries:
            z.writestr(name, text)


def j8(tmp):
    print("\n== J8. 2차판 — 달을 넘는 요인 나누기 · 이정표 · 다른 PC로 보내기 ==")
    p, d = new_project(tmp, "보낼 모형")
    monthly_file(d, 1)
    codes = [run(["data", "build", "--inbox", "auto", "--use"], d)[0], run(["sim", "--as", "m1"], d)[0],
             run(["hs", "main", "--as", "hs1"], d)[0], run(["work", "pin", "sim:m1"], d)[0]]
    c, o, e = run(["milestone", "make", "fc_m1", "--note", "1달 전망 확정"], d)
    codes += [c, run(["work", "unpin", "sim:m1"], d)[0]]
    monthly_file(d, 2)
    codes.append(run(["data", "build", "--inbox", "auto", "--use"], d)[0])
    est = quiet(Project.open, d).est("CN c Y CN(-1) R", part="demand:CN")
    codes += [run(["adopt", est.id], d)[0], run(["sim", "--as", "m2"], d)[0]]
    c, o, e = run(["an", "split", "sim:m1 sim:m2", "--vars", "Y,CN"], d)
    rows = _split_rows(o)
    an1 = quiet(Project.open, d).work.records("an")[-1]
    t1 = an1.read_csv("table_1.csv")
    sums = None
    if t1 is not None:
        cols = [x for x in ("자료", "가정", "식", "나머지") if x in t1.columns]
        sums = float((t1[cols].sum(axis=1) - t1["바뀜"]).abs().max())
    check("J8.1 두 달의 전망 — 새 분기·개정(자료)과 바꾼 소비함수(식)의 몫이 따로, 몫의 합 = 바뀜",
          codes == [0] * len(codes) and c == 0 and len(rows) >= 4 and sums is not None and sums <= 0.0025 + 1e-9
          and t1 is not None and (t1["자료"].abs() > 1e-6).any() and (t1["식"].abs() > 1e-6).any(),
          f"{codes} {c} 합 차이 {sums} {list(t1.columns) if t1 is not None else None} {(o + e)[-200:] if c else ''}")
    blk = os.path.join(d, "EQUATIONS", "demand.txt")
    write(blk, read(blk) + "# 다음 달에 볼 것\n")
    ap = os.path.join(d, "ASSUMPTIONS", "base.csv")
    a = pd.read_csv(ap, index_col=0)
    a["POIL"] *= 1.2
    a.to_csv(ap, lineterminator=chr(10))
    c2, o2, _ = run(["an", "split", "sim:m1 sim:m2", "--vars", "Y,CN"], d)
    check("J8.2 정의 파일을 고친 뒤에 다시 나눠도 같은 몫(기록만으로 푼다)", c2 == 0 and _split_rows(o2) == rows, "\n".join(_split_rows(o2)[:2]))
    c, o, _ = run(["milestone", "show", "fc_m1"], d)
    changed = [x for x in o.splitlines() if "EQUATIONS/adopted.toml" in x or "EQUATIONS/demand.txt" in x]
    c3, o3, e3 = run(["milestone", "restore", "fc_m1", "--json"], d)
    after = quiet(Project.open, d).milestone_diff("fc_m1")
    chg = json.loads(o3).get("change") if c3 == 0 else None
    c4, _, _ = run(["history", "revert", chg], d) if chg else (1, "", "")
    back = quiet(Project.open, d).milestone_diff("fc_m1")
    check("J8.3 이정표 — 그 뒤의 채택·식 고침이 차이로 보이고, 되돌리면 정의가 같고(자료 회차는 그대로), 되돌림을 되돌리면 다시 다르다",
          c == 0 and len(changed) == 2 and c3 == 0 and after.defs_same and c4 == 0 and not back.defs_same, f"{changed} {(o3 + e3)[-200:]}")
    run(["work", "pin", "hs:hs1"], d)
    run(["work", "pin", "sim:m2"], d)
    run(["work", "clean", "--yes"], d)
    p = quiet(Project.open, d)
    check("J8.4 고정을 푼 뒤 정리(work clean --yes)해도 이정표가 적은 기록(sim:m1)과 이정표가 남는다",
          _exists(d, "sim:m1") and [m["name"] for m in p.milestones()] == ["fc_m1"], str([m["name"] for m in p.milestones()]))

    zp = os.path.join(tmp, "보낼 묶음.zip")
    c, o, e = run(["bundle", "make", "--out", zp, "--records", "all"], d)
    other = os.path.join(tmp, "다른 PC", "받은 모형")
    c2, o2, e2 = run(["bundle", "open", zp, other], tmp)
    q = quiet(Project.open, other) if c2 == 0 else None
    c3, o3, e3 = run(["hs", "--replay", "hs:hs1"], other) if q else (1, "", "")
    c4, o4, _ = run(["an", "split", "sim:m1 sim:m2", "--vars", "Y,CN"], other) if q else (1, "", "")
    leaks = _leaks(other, [d, tmp]) if q else ["(못 엶)"]
    check("J8.5 묶어 보내고 다른 폴더(한글·공백)에서 열면 — 회차·이정표 그대로, HS 재연 같음, 요인 나누기 같음, 기록에 원래 PC의 경로 없음",
          c == 0 and c2 == 0 and q is not None and q.vintage == p.vintage and [m["name"] for m in q.milestones()] == ["fc_m1"]
          and c3 == 0 and ("같은 결과" in o3 or "같음" in o3) and c4 == 0 and _split_rows(o4) == rows and not leaks,
          f"{c} {c2} {c3} {c4} 회차 {q.vintage if q else None}/{p.vintage} {_split_rows(o4)[:1]} {rows[:1]} {(o3 + e3)[-160:]} {leaks[:3]}")
    zr = os.path.join(tmp, "raw.zip")
    c, o, e = run(["bundle", "make", "--raw", "--out", zr, "--records", "none"], d)
    other2 = os.path.join(tmp, "다른 PC", "원자료까지")
    c2, _, _ = run(["bundle", "open", zr, other2], tmp)
    c3, o3, e3 = run(["data", "build", "--json"], other2) if c2 == 0 else (1, "", "")
    vid = json.loads(o3).get("id") if c3 == 0 else None
    check("J8.6 원자료까지 묶으면 받은 쪽에서 회차를 다시 만들어도 같은 회차(내용 해시)", c == 0 and c2 == 0 and c3 == 0 and vid == p.vintage,
          f"{vid} ≠ {p.vintage} {(o3 + e3)[-200:]}")

    bad = []
    outside = os.path.join(tmp, "밖에 생기면 안 됨.txt")
    cases = [
        ("zip-slip", [("evil/../../밖에 생기면 안 됨.txt", "x")], None),
        ("절대 경로", [("evil/C:/x.txt", "x")], None),
        ("역슬래시", [("evil\\..\\..\\x.txt", "x")], None),
        ("새 판", [], {"format": "equion-bundle", "format_version": 99, "project": "evil"}),
        ("다른 형식", [], {"format": "something", "format_version": 1}),
    ]
    for i, (label, entries, manifest) in enumerate(cases):
        ez = os.path.join(tmp, f"evil{i}.zip")
        _evil(ez, entries, manifest)
        dest = os.path.join(tmp, "evil_out", str(i))
        code, out, err = run(["bundle", "open", ez, dest], tmp)
        if code != 3:
            bad.append(f"{label}: 종료 코드 {code} {(out + err)[-120:]}")
    full = os.path.join(tmp, "가득 찬 폴더")
    write(os.path.join(full, "있던 파일.txt"), "x")
    code, out, err = run(["bundle", "open", zp, full], tmp)
    if code != 3 or sorted(os.listdir(full)) != ["있던 파일.txt"]:
        bad.append(f"빈 폴더가 아님: {code}")
    with zipfile.ZipFile(zp) as z:
        names = z.namelist()
    private = [n for n in names if "/work/history/" in n or "/work/desk/" in n or "/DATA/raw/" in n]
    check("J8.7 나쁜 묶음(폴더 밖 경로 · 절대 경로 · 새 판 · 다른 형식) · 빈 폴더가 아니면 3, 밖에 아무것도 생기지 않음 · 기본 묶음에 바뀜 기록·화면 상태·원자료 없음",
          not bad and not os.path.exists(outside) and not os.path.exists(os.path.join(tmp, "x.txt")) and not private, f"{bad} {private[:3]}")

    w, wd = new_project(tmp, "통계표")
    raw = os.path.join(wd, "DATA", "raw", "industry.csv")
    head = "표 2. 산업별 생산(가상)\n항목,단위,2018 1/4,2018 2/4,2018 3/4,2018 4/4\n"
    write(raw, head + "제조업,십억원,100,101,103,104\n서비스업,십억원,200,202,-,205\n")
    c, o, e = run(["data", "define", "ind", "--file", "DATA/raw/industry.csv", "--time-axis", "columns", "--time-row", "2",
                   "--name-col", "A", "--missing", "-", "--series", "MFG=제조업", "--series", "SVC=서비스업"], wd)
    c2, _, _ = run(["data", "build", "--use"], wd)
    v1 = quiet(Project.open, wd).vintage
    new = os.path.join(tmp, "industry_2019Q1.csv")
    write(new, "표 2. 산업별 생산(가상)\n항목,단위,2018 1/4,2018 2/4,2018 3/4,2018 4/4,2019 1/4\n"
               "제조업,십억원,100,101.5,103,104,106\n서비스업,십억원,200,202,203,205,207\n")
    c3, o3, e3 = run(["data", "add", new, "--source", "ind"], wd)
    c4, _, _ = run(["data", "build", "--use"], wd)
    c5, o5, e5 = run(["data", "diff", v1, "--json"], wd)
    wf = quiet(Project.open, wd).workfile
    dj = json.loads(o5) if c5 == 0 else {}
    text = json.dumps(dj, ensure_ascii=False)
    ch = {x.get("시리즈"): x for x in dj.get("changes", [])}
    check("J8.8 시점이 열로 가는 통계표의 다음 판 — 정의 그대로 새 열(새 분기)·고친 칸(개정)·채운 결측이 회차 차이로",
          [c, c2, c3, c4, c5] == [0] * 5 and wf["MFG"].loc[pd.Timestamp("2019-01-01")] == 106 and wf["MFG"].loc[pd.Timestamp("2018-04-01")] == 101.5
          and wf["SVC"].loc[pd.Timestamp("2018-07-01")] == 203 and ch.get("MFG", {}).get("새 값") == 1 and ch.get("MFG", {}).get("개정") == 1
          and ch.get("SVC", {}).get("새 값") == 2,
          f"{[c, c2, c3, c4, c5]} {wf['MFG'].dropna().tolist()} {wf['SVC'].dropna().tolist()} {text[:300]}")


# ---------------------------------------------------------------------------
def _fingerprint(d, skip=("work", "exports")):
    """프로젝트 파일의 지문 {상대 경로: md5} — work/·exports/ 밖(정의·원자료·보고서·노트·equion.toml의 회차까지)."""
    out = {}
    for f in glob.glob(os.path.join(d, "**", "*"), recursive=True):
        rel = os.path.relpath(f, d).replace(os.sep, "/")
        if os.path.isfile(f) and rel.split("/")[0] not in skip:
            with open(f, "rb") as fh:
                out[rel] = hashlib.md5(fh.read()).hexdigest()
    return out


def _j9_file(d, k):
    """J9의 k번째 달 원자료(합성) — toy_q에 k분기를 더한다. 둘째 달부터 2019년 소비를 0.4% 고치고(지난 값 개정),
    셋째 달부터 새 열 EXPO가 붙어 온다. 받은 상자에 `toy_q_<새 분기>.csv`로 놓는다."""
    df = pd.read_csv(os.path.join(d, "DATA", "raw", "toy_q.csv"), index_col=0)
    last = df.loc["2019Q4"]
    for j in range(1, k + 1):
        df.loc[quarter(j)] = last * (1.004 ** j) * (1 + 0.002 * math.sin(j))
    if k >= 2:
        df.loc["2019Q1":"2019Q4", "CN"] *= 1.004
    if k >= 3:
        df["EXPO"] = (df["Y"] * 0.3).round(4)
    name = f"toy_q_{quarter(k)}.csv"
    df.to_csv(os.path.join(d, "DATA", "raw", "inbox", name))
    return name


def _run_id(out):
    """`equion run`의 끝 줄 '기록  run:…' → 실행 기록 이름."""
    m = re.search(r"기록\s+(run:\S+)", out)
    return m[1] if m else None


def _step_text(d, rid, n):
    """실행 기록의 단계 출력(work/run/<이름>/steps/NN.txt) — 없으면 ''."""
    f = os.path.join(d, "work", "run", (rid or "run:-").split(":", 1)[1], "steps", f"{n:02d}.txt")
    return read(f) if os.path.isfile(f) else ""


def j9(tmp):
    print("\n== J9. 여러 달 운영 — 개정 · 새 열 · 지난 파일 · 이정표 ==")
    p, d = new_project(tmp, "months")
    inbox = os.path.join(d, "DATA", "raw", "inbox")
    codes, runs, vints, errs = [], [], [p.vintage], []

    def month(k):
        _j9_file(d, k)
        code, out, err = run(["run", "FLOWS/monthly.eqs", "-q"], d)
        codes.append(code)
        runs.append(_run_id(out))
        if code:
            errs.append(f"{k}달: {(out + err).strip()[-200:]}")

    month(1)
    vints.append(quiet(Project.open, d).vintage)
    month(2)
    vints.append(quiet(Project.open, d).vintage)
    cm, _, _ = run(["milestone", "make", "m2", "--note", "둘째 달 확정"], d)
    c, o, _ = run(["data", "diff", vints[1], "--json"], d)
    cn = {x.get("시리즈"): x for x in (json.loads(o).get("changes", []) if c == 0 else [])}.get("CN", {})
    check("J9.1 두 달 — 받은 파일마다 새 회차 · 지난 값 개정(2019년 소비 넷)이 회차 차이에 '개정'으로 · 둘째 달에 이정표",
          codes == [0, 0] and len(set(vints)) == 3 and cn.get("개정") == 4 and cn.get("새 값") == 1 and cm == 0,
          f"{codes} {vints} 개정 {cn.get('개정')} 새 값 {cn.get('새 값')} {'; '.join(errs)}")

    month(1)                                                   # 셋째 달: 첫 달 파일을 다시 받았다(지금 회차보다 한 분기 짧다)
    q = quiet(Project.open, d)
    st1 = ((q.work.get(runs[-1]).meta.get("steps") if runs[-1] else None) or [{}])[0]
    hs_end = (q.work.records("hs")[-1].meta.get("range") or [None, None])[1]
    check("J9.2 지난 파일을 다시 받은 달 — 자료 단계가 '!'(기간이 짧음)이고 회차는 그대로(옛 회차로 돌아가지 않음) · 파일은 받은 상자에 · 나머지 단계는 지금 회차로(0)",
          codes[-1] == 0 and st1.get("status") == "flag" and q.vintage == vints[-1] and os.listdir(inbox) == ["toy_q_2020Q1.csv"]
          and hs_end == quarter(2) and "기간이 짧습니다" in _step_text(d, runs[-1], 1),
          f"{codes[-1]} {st1.get('status')} 회차 {q.vintage}/{vints[-1]} 상자 {os.listdir(inbox)} hs 끝 {hs_end}")
    os.remove(os.path.join(inbox, "toy_q_2020Q1.csv"))       # 사람이 잘못 둔 파일을 치우고 바른 파일을 둔다

    month(3)                                                   # 새 열 EXPO가 붙어 온다
    vints.append(quiet(Project.open, d).vintage)
    hint = "equion data define na --series EXPO=EXPO" in _step_text(d, runs[-1], 1)
    c1, o1, e1 = run(["data", "define", "na", "--series", "EXPO=EXPO"], d)
    c2, o2, e2 = run(["data", "build", "--use"], d)
    q = quiet(Project.open, d)
    vints.append(q.vintage)
    check("J9.3 새 열이 붙어 온 달 — 자료 단계가 'data define na --series EXPO=EXPO'를 권하고, 그대로 정의하면 새 회차에 EXPO",
          codes[-1] == 0 and hint and c1 == 0 and c2 == 0 and "EXPO" in q.workfile.series(),
          f"{codes[-1]} 권함 {hint} {(o1 + e1 + o2 + e2)[-200:] if c1 or c2 else ''}")
    month(4)
    vints.append(quiet(Project.open, d).vintage)

    q = quiet(Project.open, d)
    bad, reps = [], sorted(glob.glob(os.path.join(d, "reports", "forecast_*.md")))
    for f in reps:
        vin, rel = os.path.basename(f)[len("forecast_"):-3], os.path.relpath(f, d)
        c, o, e = run(["report", "update", rel], d)         # 몇 달 뒤 옛 보고서를 고쳐도 뒤 회차의 기록이 끼지 않는다
        if c != 0:
            bad.append(f"report update {rel} → {c} {(o + e)[-100:]}")
        regions = re.findall(r"<!-- equion:report (\S+) #\d+ · \S+ · data:(\S+)", read(f))
        if len(regions) != 2:
            bad.append(f"{rel} 구역 {len(regions)}")
        for rid, dv in regions:
            try:
                rv = (q.work.get(rid).meta.get("data") or {}).get("id")
            except Exception:  # noqa: BLE001
                rv = "(없는 기록)"
            if dv != vin or rv != vin:
                bad.append(f"{rel}: {rid} 표시 {dv} · 기록 {rv}")
        c, o, e = run(["report", "check", rel], d)
        if c != 0:
            bad.append(f"report check {rel} → {c}")
    have = {os.path.basename(f)[len("forecast_"):-3] for f in reps}
    want = {vints[1], vints[2], vints[3], vints[5]}           # 실행이 돈 회차마다 하나(정의만 바꾼 회차에는 실행이 없다)
    check("J9.4 보고서마다 구역이 제 회차의 기록을 가리킨다(구역 표시와 기록의 자료 회차) — 넷째 달 뒤에 옛 보고서를 report update해도 · report check 0",
          not bad and have == want, f"{bad[:4]} 보고서 {sorted(have)}")

    ids = [x["id"] for x in q.work.log()]
    sims = [r.id for r in q.work.records("sim")]
    dl = [v["id"] for v in q.data_list()]
    check("J9.5 이름이 겹치지 않는다 — 실행 다섯(지난 파일의 달 포함) · 회차 여섯(처음 + 넷 + 정의) · 기록 · 전망 열(달마다 기준선·유가)",
          codes == [0] * 5 and None not in runs and len(set(runs)) == 5 and len(set(vints)) == 6 and sorted(dl) == sorted(vints)
          and len(ids) == len(set(ids)) and len(sims) == len(set(sims)) == 10,
          f"{runs} 회차 {vints} 기록 {len(ids)}/{len(set(ids))} 전망 {len(sims)} {'; '.join(errs)}")

    c, o, e = run(["run", "--replay", runs[0] or "run:x", "-q"], d)
    check("J9.6 첫 달의 실행을 넷째 달 뒤에 재연 — 모두 같음", c == 0 and "모두 같음" in o, (o + e)[-200:] if c else "")

    before, vb = _fingerprint(d), q.vintage
    c, o, e = run(["milestone", "restore", "m2", "--json"], d)
    res = json.loads(o) if c == 0 else {}
    q = quiet(Project.open, d)
    same_defs = q.milestone_diff("m2").defs_same
    pre = _fingerprint(d)
    cb, ob, eb = run(["data", "build"], d)                     # 이정표 때 정의 = 둘째 달 원자료 → 지금 회차보다 짧다
    untouched = pre == _fingerprint(d)
    cr, orr, er = run(["history", "revert", res.get("change") or "h0000"], d)
    after = _fingerprint(d)
    moved = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
    check("J9.7 이정표(둘째 달) restore — 정의는 그때와 같고 회차는 그대로(알림) · 그 뒤 data build는 짧아져 거절(3, 아무것도 바꾸지 않음) · restore를 되돌리면 restore 전과 바이트까지 같다",
          c == 0 and same_defs and q.vintage == vb and any("회차는 그대로" in x for x in res.get("data") or []) and cb == 3
          and "짧" in (ob + eb) and untouched and cr == 0 and not moved and quiet(Project.open, d).vintage == vb,
          f"{c} 정의 같음 {same_defs} 회차 {q.vintage}/{vb} 거절 {cb} 되돌림 {cr} {(orr + er)[-120:] if cr else ''} 다른 파일 {moved[:4]}")


# ---------------------------------------------------------------------------
def _kill(proc, pid=None):
    """강제 종료(작업 관리자의 '작업 끝내기'·Desk 창 닫기와 같다 — 정리할 틈이 없다). pid = equion을 돌리는 Python
    (Windows의 가상환경 python.exe는 그 Python을 자식으로 띄운다). Windows는 그 프로세스를 곧바로 끝내고(TerminateProcess —
    taskkill /F와 같다) taskkill /F /T로 나머지 나무까지, 다른 OS는 SIGKILL."""
    try:
        os.kill(pid or proc.pid, signal.SIGTERM if os.name == "nt" else signal.SIGKILL)
    except OSError:
        pass
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
    proc.wait(timeout=60)


def _progress(state):
    """도는 실행의 상태(work/run/.active/<이름>.json)에서 하는(또는 끝낸) 단계 번호."""
    return max((state.get("current") or {}).get("n") or 0, len(state.get("steps") or []))


def _kill_run(d, at, delay=0.0, limit=90):
    """d에서 `equion run FLOWS/monthly.eqs`를 띄우고 at번째 단계에 들어서고 delay초 뒤에 강제로 끝낸다 → 그 단계에 들어설 때의 실행
    상태(못 잡았으면 None). 시각이 아니라 실행이 적는 상태로 끊으므로 PC의 빠르기와 거의 상관없다(delay는 그 단계 안의 어디쯤)."""
    from equion.script.record import _pid_alive
    proc = subprocess.Popen([sys.executable, "-m", "equion", "run", "FLOWS/monthly.eqs", "-q"], cwd=d, stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    act, state, t0 = os.path.join(d, "work", "run", ".active"), None, time.time()
    while state is None and proc.poll() is None and time.time() - t0 < limit:
        for f in glob.glob(os.path.join(act, "*.json")):
            try:
                s = json.loads(read(f) or "null")
            except (OSError, ValueError):           # 쓰는 중인 파일
                s = None
            if s and _progress(s) >= at:
                state = s
        if state is None:
            time.sleep(0.01)
    if state and delay:
        time.sleep(delay)
    _kill(proc, (state or {}).get("pid"))
    t1 = time.time()
    while state and _pid_alive(state.get("pid")) and time.time() - t1 < 10:
        time.sleep(0.05)
    return state


def _leftovers(d):
    """반쯤 쓴 임시 파일·폴더(`*.tmp-equion` · `.tmp-<이름>-…` 등)."""
    return sorted(os.path.relpath(f, d) for f in glob.glob(os.path.join(d, "**", "*"), recursive=True)
                  if re.search(r"\.tmp|~$|\.partial$", os.path.basename(f)))


def _together(d, cmds):
    """명령 여럿을 같은 순간에 — 프로세스마다(Claude Code가 명령을 나란히 · Desk와 터미널) → [(종료 코드, 출력)]."""
    gate, out = threading.Barrier(len(cmds)), [None] * len(cmds)
    env = dict(os.environ, PYTHONIOENCODING="utf-8")

    def go(i):
        gate.wait()
        r = subprocess.run([sys.executable, "-m", "equion", *cmds[i]], cwd=d, capture_output=True, env=env, stdin=subprocess.DEVNULL)
        out[i] = (r.returncode, (r.stdout + r.stderr).decode("utf-8", "replace"))
    ts = [threading.Thread(target=go, args=(i,)) for i in range(len(cmds))]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    return out


def j10(tmp):
    print("\n== J10. 끊김과 동시 실행 ==")
    _, base = new_project(tmp, "kill_base")
    monthly_file(base, 1)
    got = os.listdir(os.path.join(base, "DATA", "raw", "inbox"))[0]
    # 자료 단계는 0.45초쯤 안에서(받은 파일을 넣은 뒤 · 회차를 만들기 전 언저리), 과거 재현은 조금 들어가서, 보고서는 들어서자마자
    for i, (label, at, delay) in enumerate((("자료 단계 도중", 1, 0.45), ("과거 재현 도중", 4, 0.1), ("보고서 쓰는 중", 8, 0.0))):
        d = os.path.join(tmp, f"kill_{i + 1}")
        shutil.copytree(base, d)
        v0 = quiet(Project.open, d).vintage
        state = _kill_run(d, at, delay)
        q = quiet(Project.open, d)
        na = re.search(r'file = "(DATA/raw/[^"]+)"', read(os.path.join(d, "DATA", "series.toml")))
        # 지금 회차의 폴더가 온전하고, 정의가 가리키는 원자료가 있고, 받은 파일은 받은 상자 아니면 정의가 가리키는 곳에(없어지지 않는다)
        sane = bool(q.vintage and os.path.isfile(os.path.join(d, "work", "data", q.vintage, "series.csv"))
                    and na and os.path.isfile(os.path.join(d, na[1]))
                    and (got in os.listdir(os.path.join(d, "DATA", "raw", "inbox")) or na[1] == f"DATA/raw/{got}"))
        c, o, e = run(["run", "FLOWS/monthly.eqs", "-q"], d)
        q = quiet(Project.open, d)
        name = (state or {}).get("name")
        try:
            km = q.work.get(f"run:{name}").meta
        except Exception:  # noqa: BLE001
            km = {}
        cs, os_, _ = run(["work", "show", f"run:{name}"], d)
        cr, _, _ = run(["run", "--replay", f"run:{name}"], d)
        cc, _, _ = run(["report", "check", f"reports/forecast_{q.vintage}.md"], d)
        runs = [r.id for r in q.work.records("run")]
        vs = [v["id"] for v in q.data_list()]
        left = _leftovers(d)
        marks = [s.get("status") for s in km.get("steps") or []]
        cut = (km.get("steps") or [{}])[-1]
        # 기록의 단계는 끊긴 데까지(본 상태의 단계 이상 — 끊는 사이 조금 더 갔을 수 있다) · 끝 단계만 '끊김'이거나 단계 사이에서 끊겼다
        stopped = bool(marks) and cut.get("n", 0) >= _progress(state or {}) and "interrupted" not in marks[:-1] \
            and (marks[-1] == "interrupted" or len(marks) < 11)
        check(f"J10.{i + 1} {label} 강제 종료 → 회차·정의·받은 파일이 서로 맞고(받은 파일은 상자 아니면 정의 쪽에), 다음 실행이 '끝나지 못함'(130 · 끊긴 단계까지) "
              "기록을 남기고 새 번호로 끝까지 · 그 기록은 재연 거절(3) · 받은 상자 빔 · 회차 둘 · 임시 파일 없음 · 보고서 정상",
              state is not None and sane and c == 0 and km.get("status") == "cancelled" and km.get("exit_code") == 130 and stopped
              and cs == 0 and "끝나지 못함" in os_ and cr == 3 and len(runs) == len(set(runs)) == 2 and _run_id(o) != f"run:{name}"
              and cc == 0 and not os.listdir(os.path.join(d, "DATA", "raw", "inbox"))
              and not os.listdir(os.path.join(d, "work", "run", ".active")) and len(vs) == 2 and v0 in vs
              and q.span("last:last")[1] == quarter(1) and not left,
              f"끊은 단계 {_progress(state or {})} → 기록 {cut.get('n')} {cut.get('status')} · 정의 {sane} · 다시 {c} {(o + e)[-160:] if c else ''}"
              f"· 기록 {km.get('status')}/{km.get('exit_code')} · 재연 {cr} · 보고서 {cc} · 실행 {runs} · 회차 {vs} · 남은 것 {left[:3]}")
        if i == 0:
            c2, o2, e2 = run(["run", "--replay", _run_id(o) or "run:x", "-q"], d)
            check("J10.1b 끊긴 뒤 다시 돈 실행의 재연 — 모두 같음", c2 == 0 and "모두 같음" in o2, (o2 + e2)[-200:] if c2 else "")

    _, d = new_project(tmp, "concurrent")
    for args in (["est", "CN c Y CN(-1) CN(-2)", "--for", "demand:CN", "--as", "cn2"],
                 ["est", "I c Y(-1) R I(-1)", "--for", "demand:I", "--as", "i2"],
                 ["est", "RL c R RL(-1) RL(-2)", "--for", "finance:RL", "--as", "rl2"]):
        run(args, d)
    run(["history", "list"], d)
    h0 = {c.id for c in quiet(Project.open, d).history.list()}
    res = _together(d, [["adopt", "est:cn2"], ["adopt", "est:i2"], ["adopt", "est:rl2"]])
    q = quiet(Project.open, d)
    dem, fin = read(os.path.join(d, "EQUATIONS", "demand.txt")), read(os.path.join(d, "EQUATIONS", "finance.txt"))
    ad = read(os.path.join(d, "EQUATIONS", "adopted.toml"))
    new = [c.id for c in q.history.list() if c.id not in h0]
    kept = [k for k, v in (("demand:CN", "cn2"), ("demand:I", "i2"), ("finance:RL", "rl2")) if f'"{k}" = "est:{v}"' in ad]
    check("J10.4 채택 셋을 같은 순간에(같은 블록 파일의 다른 식 둘 + 다른 블록 하나) — 모두 0 · 블록 파일의 줄과 채택표 항목이 하나도 사라지지 않고 바뀜 기록 번호가 겹치지 않는다",
          [r[0] for r in res] == [0, 0, 0] and "CN c Y CN(-1) CN(-2)" in dem and "I c Y(-1) R I(-1)" in dem and "RL c R RL(-1) RL(-2)" in fin
          and len(kept) == 3 and len(new) == len(set(new)) == 3 and not _leftovers(d) and q.assemble("main").ok,
          f"{[(r[0], r[1].strip()[-120:]) for r in res if r[0]]} 채택표 {kept} 바뀜 {new} {_leftovers(d)[:3]}")
    n0 = len(q.work.records("est"))
    res = _together(d, [["est", "demand:CN"]] * 4)
    q = quiet(Project.open, d)
    ests = [r.id for r in q.work.records("est")]
    lines = [x for x in read(os.path.join(d, "work", "log.jsonl")).splitlines() if x.strip()]
    try:
        ids = [json.loads(x)["id"] for x in lines]
    except (ValueError, KeyError):
        ids = []
    names = sorted(re.findall(r"\[(est:cn_\d{4})\]", " ".join(r[1] for r in res)))
    folders = [x for x in os.listdir(os.path.join(d, "work", "est")) if not x.startswith(".")]
    check("J10.5 같은 부품의 추정 넷을 같은 순간에 — 모두 0 · 서로 다른 이름 넷으로 남고 작업 목록(log.jsonl 줄마다 온전)·기록 폴더에 빠짐·겹침·임시 폴더가 없다",
          [r[0] for r in res] == [0] * 4 and len(names) == len(set(names)) == 4 and len(ests) == n0 + 4
          and len(ids) == len(lines) == len(set(ids)) and set(names) <= set(ids) and len(folders) == len(ests)
          and all(os.path.isfile(os.path.join(d, "work", "est", x, "record.json")) for x in folders) and not _leftovers(d),
          f"{[(r[0], r[1].strip()[-120:]) for r in res if r[0]]} 이름 {names} 기록 {len(ests)}(앞 {n0}) {_leftovers(d)[:3]}")


# ---------------------------------------------------------------------------
def _na_csv(path, df, unit=True, rename=None):
    """통계표처럼 단위 줄(2줄)이 있는 분기 원자료 — unit=False면 단위 줄이 빠진 파일, rename이면 열 이름이 바뀐 파일."""
    df = df.rename(columns=rename or {})
    lines = ["period," + ",".join(df.columns)]
    if unit:
        lines.append("," + ",".join("%" if c in ("R", "RL") else "지수" if c in ("P", "POIL") else "조원" for c in df.columns))
    lines += [i + "," + ",".join("" if pd.isna(v) else f"{v:.6f}" for v in row) for i, row in df.iterrows()]
    write(path, "\n".join(lines) + "\n")


def j11(tmp):
    print("\n== J11. 낯선 받은 파일 ==")
    _, d = new_project(tmp, "odd_files")
    raw, inbox = os.path.join(d, "DATA", "raw"), os.path.join(d, "DATA", "raw", "inbox")
    q = pd.read_csv(os.path.join(raw, "toy_q.csv"), index_col=0)
    nxt = q.copy()
    nxt.loc["2020Q1"] = q.loc["2019Q4"] * 1.004
    _na_csv(os.path.join(raw, "na.csv"), q)                     # 원자료를 단위 줄이 있는 통계표로 바꿔 둔다
    st = os.path.join(d, "DATA", "series.toml")
    write(st, read(st).replace('file = "DATA/raw/toy_q.csv"', 'file = "DATA/raw/na.csv"\nunit_row = 2'))
    c0, _, _ = run(["data", "build", "--use"], d)
    v0, st0 = quiet(Project.open, d).vintage, read(st)
    got = os.path.join(inbox, "na_2020Q1.csv")

    def refused(df, **kw):
        _na_csv(got, df, **kw)
        _, oi, ei = run(["data", "inbox"], d)
        c, o, e = run(["data", "build", "--inbox", "auto", "--use"], d)
        same = quiet(Project.open, d).vintage == v0 and read(st) == st0 and os.listdir(inbox) == ["na_2020Q1.csv"]
        return c, o + e, oi + ei, same

    c, o, oi, same = refused(nxt, unit=False)
    check("J11.1 단위 줄이 빠진 받은 파일 → 넣지 않고(3) 그 줄과 칸을 말한다(A2 '1970Q1' — 첫 기간이 단위로 사라지지 않는다) · data inbox도 · 회차·정의·받은 상자 그대로",
          c0 == 0 and c == 3 and "단위 줄" in o and "A2 '1970Q1'" in o and "A2 '1970Q1'" in oi and same, o[-200:] if c != 3 else "")
    os.remove(got)
    c, o, oi, same = refused(nxt, rename={"CN": "CONS"})
    check("J11.2 열 이름이 바뀐 받은 파일(CN → CONS) → 넣지 않고(3) 없는 열 CN과 새 파일에만 있는 열 CONS를 말한다 · 그대로",
          c == 3 and "없는 열: CN" in o and "CONS" in o and "CONS" in oi and same, o[-200:] if c != 3 else "")
    os.remove(got)

    blk, ad = os.path.join(d, "EQUATIONS", "demand.txt"), os.path.join(d, "EQUATIONS", "adopted.toml")
    blk0 = read(blk)
    run(["est", "CN c Y Y(-1) CN(-1)", "--for", "demand:CN", "--as", "c3"], d)
    c1, o1, _ = run(["adopt", "est:c3"], d)
    h = re.search(r"바뀜 기록\s+(h\d{4})", o1)
    for f in (blk, ad):                                         # 편집기·git autocrlf·Python write_text가 줄바꿈만 CRLF로
        with open(f, "rb") as fh:
            b = fh.read().replace(b"\r\n", b"\n")
        with open(f, "wb") as fh:
            fh.write(b.replace(b"\n", b"\r\n"))
    run(["history", "list"], d)
    outside = quiet(Project.open, d).history.list()[-1]
    cs, os_, _ = run(["history", "show", outside.id], d)
    c2, o2, e2 = run(["history", "revert", h[1] if h else "h0000"], d)
    with open(blk, "rb") as fh:
        b = fh.read()
    check("J11.3 채택 뒤 줄바꿈만 CRLF로 바뀐 블록 파일·채택표 — 그 바뀜은 '줄바꿈만', 채택 되돌리기가 된다(0) · 식은 채택 전으로, 줄바꿈은 CRLF 그대로",
          c1 == 0 and h is not None and cs == 0 and "줄바꿈만 바뀜" in os_ and c2 == 0 and b.replace(b"\r\n", b"\n").decode("utf-8") == blk0
          and b.count(b"\n") == b.count(b"\r\n") and (not os.path.exists(ad) or '"demand:CN"' not in read(ad))
          and quiet(Project.open, d).assemble("main").ok, f"{c1} {outside.id} {os_[-120:] if cs else ''} 되돌림 {c2} {(o2 + e2)[-200:] if c2 else ''}")

    c, o, oi, same = refused(nxt.iloc[-8:])                     # 최근 8기만 든 파일(일부 기간만 내려받음)
    from equion.projects.vintage import ShorterError
    try:
        quiet(quiet(Project.open, d).data_build, use=True, inbox="auto")
        err = None
    except Exception as ex:  # noqa: BLE001
        err = ex
    same2 = quiet(Project.open, d).vintage == v0 and os.listdir(inbox) == ["na_2020Q1.csv"]
    c3, o3, e3 = run(["data", "build", "--inbox", "auto", "--use", "--allow-shorter"], d)
    first = quiet(Project.open, d).workfile["CN"].first_valid_index()
    check("J11.4 최근 8기만 든 받은 파일 → 넣지 않음(3 — Python은 ShorterError) · 회차 그대로 · --allow-shorter면 넣고 짧은 회차를 '!'와 함께",
          c == 3 and "기간이 짧습니다" in o and "--allow-shorter" in o and "기간이 짧습니다" in oi and same and isinstance(err, ShorterError)
          and same2 and c3 == 0 and "! 지금 회차" in o3 and not os.listdir(inbox) and quiet(Project.open, d).vintage != v0
          and first is not None and str(pd.Period(first, "Q")) == "2018Q2",
          f"{c} {type(err).__name__} 넣기 {c3} {(o3 + e3)[-200:] if c3 else ''} 처음 {first}")


# ---------------------------------------------------------------------------
def j12(tmp):
    print("\n== J12. 풀리지 않는 모형 ==")
    _, d = new_project(tmp, "unsolvable")
    blk = os.path.join(d, "EQUATIONS", "demand.txt")
    orig = read(blk)
    write(blk, "CN c Y CN(-1)  @coef 0 1 0   # 계수를 고정해 CN = Y — 국민소득 항등식과 함께 해가 없다\nI c Y(-1) R\nY = CN + I + G\n")
    c, o, e = run(["hs", "core", "--as", "sing"], d)
    ok = n = gap = top = rm = None
    if c == 0:
        rec = quiet(Project.open, d).work.get("hs:sing")
        cnt, sol, act = rec.meta["counts"], rec.read_csv("solved.csv"), rec.read_csv("series.csv")
        ok, n = cnt.get("ok"), cnt.get("fallback")
        gap = float((sol["Y"] - act["Y_실측"]).abs().max())        # 실패한 기는 실측으로 — 그래서 다음 기의 Y(-1)도 실측
        top = float(sol.abs().max().max() / act.abs().max().max())  # 1e18로 커진 값이 남지 않는다
        rm = (rec.meta.get("rmspe") or {}).get("I")                 # I(Y(-1)을 쓴다)는 보통 크기의 오차
    check("J12.1 해가 없는 동시 블록(CN = Y · Y = CN + I + G) → 모든 기가 실패 대체(1e18에서 '정상'이 아님)와 까닭(자코비안 특이) · 다음 기로 흐르지 않는다",
          c == 0 and ok == 0 and n == 60 and "특이" in o and gap == 0 and top is not None and top < 2 and rm is not None and rm < 5,
          f"{c} 정상 {ok} · 대체 {n} · Y−실측 {gap} · 크기 비 {top} · I RMSPE {rm} {(o + e)[-200:] if c else ''}")
    write(blk, "CN c Y CN(-1)\nI c Y(-1) R\nY = CN + I + G + SD   # 통계상 불일치 SD를\nSD = Y - CN - I - G   # 두 번 적었다\n")
    c1, o1, e1 = run(["assemble", "core"], d)
    c2, o2, e2 = run(["hs", "core"], d)
    check("J12.2 서로 종속인 항등식(같은 관계를 두 번) → assemble이 문제로 알리고(3) hs는 풀지 않는다(3 — 아무 값으로나 '정상'이 아님)",
          c1 == 3 and "서로 종속인 항등식 demand:Y · demand:SD" in o1 and c2 == 3 and "서로 종속" in e2, f"assemble {c1} · hs {c2} {e2.strip()[:160]}")
    write(blk, "CN c Y CN(-1)\nI c Y(+1) R   # 선행변수 — 다음 기 소득을 내다보고 투자\nY = CN + I + G\n")
    c1, o1, e1 = run(["sim", "base", "--model", "core", "--as", "lead"], d)
    m = quiet(Project.open, d).work.get("sim:lead").meta if c1 == 0 else {}
    c2, o2, _ = run(["hs", "core", "--as", "hlead"], d)
    check("J12.3 선행변수(I c Y(+1) R) → sim이 Fair-Taylor 모형 일관 기대로 풀고 그렇다고 말한다(정상 8 — 전처럼 '실패 8'이 아님) · hs는 선행 값에 실측(완전 예견)이라고 알린다",
          c1 == 0 and "fair-taylor" in o1 and m.get("mce") == "fair-taylor" and (m.get("counts") or {}).get("ok") == 8
          and c2 == 0 and "완전 예견" in o2, f"{c1} {m.get('mce')} {m.get('counts')} {(o1 + e1)[-200:] if c1 else ''} hs {c2}")
    write(blk, orig)
    c1, o1, e1 = run(["est", "demand:CN", "--smpl", "2000:2019", "--as", "yr"], d)
    c2, o2, e2 = run(["hs", "core", "--range", "2018:2019", "--as", "hyr"], d)
    w = quiet(Project.open, d).work
    em = w.get("est:yr").meta if c1 == 0 else {}
    hm = w.get("hs:hyr").meta if c2 == 0 else {}
    check("J12.4 해만 적은 구간은 그 해의 마지막 기까지 — est --smpl 2000:2019는 2000Q1~2019Q4(n=80) · hs --range 2018:2019는 2018Q1~2019Q4",
          em.get("sample") == ["2000Q1", "2019Q4"] and em.get("n") == 80 and hm.get("range") == ["2018Q1", "2019Q4"],
          f"{em.get('sample')} n={em.get('n')} · {hm.get('range')} {(o1 + e1 + o2 + e2)[-200:] if c1 or c2 else ''}")


def test_suite():
    """pytest 진입점 — 이 파일의 검사 묶음 전체(하나라도 실패하면 실패). `python tests/test_journeys.py`와 같은 검사."""
    assert main() == 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):          # 출력을 파일·파이프로 받을 때(Windows cp949)도 '—' 같은 글자에서 멈추지 않게
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(99)
