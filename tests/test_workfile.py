#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_workfile.py — 워크파일 API(라이브러리 1단계) 테스트.

실행: uv run python tests/test_workfile.py   (종료코드 = 실패 수)

  A. 열기·표본·시리즈: wfopen/wfcreate, smpl, wf[...] 읽기·쓰기, genr(DSL·자기시차·Python 함수), read/write
  B. 방정식 객체: ls(표본 적용)·tsls·nls·fixed, 출력표, pandas 결과, 단일식 forecast
  C. 모델 객체: merge(파일·객체)·append·drop·blocks, solve → 별칭 시리즈(엔진 HS와 동일), 시나리오
  D. 전망·확률·control·승수, 그래프·표, params, 오류 메시지
  E. 저장/복원(.eqw)·옛 Work Table 번들 가져오기
자료는 패키지의 예제 자료(eqn.datasets.toy_q — 참 모형을 아는 가상 자료)만 쓴다.
"""

import contextlib
import io
import os
import sys
import tempfile
import time
import traceback

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import equion as eqn  # noqa: E402
from equion.worktable import WorkTable  # noqa: E402

PASS, FAIL = [], []
DATA = eqn.datasets.path("toy_q")
EQS = os.path.join(tempfile.mkdtemp(prefix="eqn-wf-"), "toy_model.txt")
with open(EQS, "w", encoding="utf-8") as _fh:
    _fh.write("I c Y(-1) R\nCN c Y CN(-1)\ndlog(P) c dlog(Y) dlog(POIL)\nRL c R RL(-1)\n"
              "log(M2) c log(P) log(Y) RL log(M2(-1))\ndlog(CNNSA) c dlog(CN) @seas\nY = CN + I + G\n")


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  — {detail}" if detail else ""))


def raises(fn, exc=Exception, contains=None):
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            fn()
    except exc as e:
        return contains is None or contains in str(e)
    except Exception:
        return False
    return False


def quiet(fn, *a, **k):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a, **k)


def close(a, b, rtol=1e-8, atol=1e-12):
    """같은 모양(또는 b가 스칼라)이고 허용오차 안이면 True."""
    a, b = np.atleast_1d(np.asarray(a, dtype=float)), np.atleast_1d(np.asarray(b, dtype=float))
    if a.shape != b.shape and b.size != 1:
        return False
    return bool(np.allclose(a, b, rtol=rtol, atol=atol))


def main():
    t0 = time.time()
    tmp = tempfile.mkdtemp()
    print("=" * 80)
    print("A. 열기·표본·시리즈")
    print("=" * 80)
    wf = quiet(eqn.wfopen, DATA)
    check("wfopen: 주기 자동 추론(Q)", wf.freq == "Q" and len(wf.data) == 200)
    check("smpl 기본 = 전체", wf.smpl() == ("1970Q1", "2019Q4"))
    quiet(wf.smpl, "1980Q1 2019Q4")
    check("smpl 설정(한 문자열)", wf.smpl() == ("1980Q1", "2019Q4"))
    quiet(wf.smpl, "@all")
    check("smpl @all", wf.smpl() == ("1970Q1", "2019Q4"))
    check("시리즈 읽기는 pandas Series(대소문자 무시)", isinstance(wf["cn"], pd.Series)
          and wf["cn"].name == "CN")
    wf["ONES"] = 1.0
    check("시리즈 쓰기(스칼라)", float(wf["ONES"].sum()) == len(wf.data))
    g4 = (wf["Y"] / wf["Y"].shift(4) - 1) * 100
    wf["G4"] = g4
    check("시리즈 쓰기(pandas 계산)", abs(wf["G4"].dropna().iloc[-1] - g4.dropna().iloc[-1]) < 1e-12)
    quiet(wf.smpl, "2010Q1", "2010Q4")
    quiet(wf.genr, "YD = Y - G/(P/100)")
    r = wf["YD"]
    t = wf._index_of("2010Q2")
    want = wf["Y"].iloc[t] - wf["G"].iloc[t] / (wf["P"].iloc[t] / 100)
    check("genr: DSL 식, 표본 안만", abs(r.iloc[t] - want) < 1e-9 and r.notna().sum() == 4)
    quiet(wf.genr, "LAGG = Y(-1) + Y.qoq")
    check("genr: EViews 시차·.qoq", abs(wf["LAGG"].iloc[t] - (wf["Y"].iloc[t - 1]
          + (wf["Y"].iloc[t] / wf["Y"].iloc[t - 1] - 1) * 100)) < 1e-9)
    wf["PATH"] = np.nan
    wf._data.data.loc[wf.data.index[wf._index_of("2009Q4")], "PATH"] = 100.0
    quiet(wf.genr, "PATH = PATH(-1) * 1.01")
    check("genr: 자기 시차는 차례로 계산", abs(wf["PATH"].iloc[wf._index_of("2010Q4")] - 100 * 1.01 ** 4) < 1e-9)
    quiet(wf.genr, "GAP", lambda d: d.Y / d.Y.rolling(8).mean() - 1)
    check("genr: Python 함수", wf["GAP"].notna().sum() == 4)
    quiet(wf.smpl, "@all")
    p = os.path.join(tmp, "out.csv")
    quiet(wf.write, p, ["Y", "P"])
    wf2 = quiet(eqn.wfcreate, "blank", "Q", "1970Q1", "2030Q4")
    names = quiet(wf2.read, p)
    check("wfcreate + read(csv)", names == ["Y", "P"] and len(wf2.data) == 244
          and abs(wf2["P"].iloc[10] - wf["P"].iloc[10]) < 1e-9)
    check("이름 오류: 시리즈 이름 검사", raises(lambda: wf.__setitem__("1BAD", 1.0), ValueError))
    check("없는 시리즈 genr → 오류", raises(lambda: wf.genr("Z = NOSUCH + 1"), ValueError, "NOSUCH"))

    print("\n" + "=" * 80)
    print("B. 방정식 객체")
    print("=" * 80)
    quiet(wf.smpl, "2003Q1", "2019Q4")
    eq = quiet(lambda: wf.equation("eq_cp").ls("log(CN) c log(Y) log(CN(-1))"))
    check("ls: 현재 표본으로 추정", eq.nobs == 68 and eq.method == "ols", f"n={eq.nobs}")
    check("결과는 pandas(coefs·resid·fitted)", isinstance(eq.coefs, pd.Series)
          and len(eq.resid) == 68 and np.allclose(eq.fitted + eq.resid, eq.actual.loc[eq.resid.index]))
    check("추정 결과 객체 노출(자체 Results)", isinstance(eq.results, eqn.stats.Results)
          and np.allclose(eq.results.params.to_numpy(), eq.coefs.to_numpy()))
    out = eq.output()
    check("출력표(text·html)", "방정식 eq_cp" in out.text() and "<table" in out.html())
    check("속성으로 객체 접근 wf.eq_cp", wf.eq_cp is eq)
    tq = quiet(lambda: wf.equation("eq_iv").tsls("log(CN) c log(Y) log(CN(-1))",
                                                  inst="log(Y(-1)) log(CN(-1)) log(G)"))
    check("tsls", tq.method == "tsls")
    nl = quiet(lambda: wf.equation("eq_nl").nls("log(CN) = c(1) + c(2)*log(Y) + c(3)*log(CN(-1))",
                                                start=[0, 0.5, 0.5]))
    check("nls(선형식) == ls (1e-10)", np.allclose(nl.coefs.to_numpy(), eq.coefs.to_numpy(), rtol=1e-10, atol=0))
    fx = quiet(lambda: wf.equation("eq_fx").fixed("log(CN) c log(Y) log(CN(-1))",
                                                  {"const": 0.5, "log(Y)": 0.2, "log(CN(-1))": 0.75}))
    check("fixed(외부 계수 dict)", fx.method == "fixed" and fx.coefs["log(Y)"] == 0.2)
    check("ls에 도구변수 → 오류", raises(lambda: wf.equation("bad").ls("Y c X @inst Z"), ValueError, "tsls"))
    fc = quiet(eq.forecast, None, "2018Q1", "2019Q4")
    t = wf._index_of("2019Q4")
    check("단일식 forecast → CNF 시리즈", "CNF" in wf and np.isfinite(fc.iloc[t])
          and abs(fc.iloc[t] / wf["CN"].iloc[t] - 1) < 0.1)

    print("\n" + "=" * 80)
    print("C. 모델 객체")
    print("=" * 80)
    quiet(wf.smpl, "@all")
    m = quiet(lambda: wf.model("toy").merge(EQS))
    check("merge(파일): 추정식 6 · 항등식 1", len(m.equations) == 6 and len(m.identities) == 1)
    b = m.blocks().data
    check("blocks: 6개, 동시 2(CN·Y)", len(b) == 6 and int(b["크기"].max()) == 2)
    quiet(wf.smpl, "1990Q1", "2019Q4")
    r0 = quiet(m.solve)
    with contextlib.redirect_stdout(io.StringIO()):
        wt = WorkTable(name="ref", freq="Q", register=False)
        wt.load_data(DATA)
        wt.load_equations(EQS)
        wt.estimate()
        wt.hs("1990Q1", "2019Q4", hs_id="h")
    ref = pd.DataFrame(wt.model.hs_solutions["h"]).T
    s, e = wt.index_of("1990Q1"), wt.index_of("2019Q4")
    mine = wf.to_pandas([c + "_0" for c in ref.columns]).iloc[s:e + 1].to_numpy()
    d = np.nanmax(np.abs(mine - ref.to_numpy()) / np.maximum(1e-9, np.abs(ref.to_numpy())))
    check("solve(기준선) = 엔진 HS, 별칭 _0 시리즈", d < 1e-12 and r0.counts()["ok"] == 120, f"{d:.1e}")
    check("풀이 구간 밖은 NaN", np.isnan(wf["Y_0"].iloc[s - 1]))
    sc = m.scenario("high_oil").override("POIL", wf["POIL"] * 1.5)
    quiet(m.solve)
    cmp = m.compare("P")
    check("시나리오 별칭 _1·compare", list(cmp.columns) == ["P", "P_0", "P_1"]
          and cmp["P_1"].iloc[-1] > cmp["P_0"].iloc[-1])
    quiet(lambda: m.scenario("baseline"))
    check("시나리오 다시 고르기", m.scenario().name == "baseline")
    m2 = quiet(lambda: wf.model("small").merge(eq).append("CI = CN + I"))
    check("merge(객체)+append", len(m2.equations) == 1 and m2.identities == ["CI = CN + I"])
    quiet(m2.drop, "CI")
    check("drop(항등식 목표변수)", m2.identities == [])
    check("append에 추정식 → 오류", raises(lambda: m2.append("log(Y) c X"), ValueError, "merge"))
    quiet(lambda: wf.model("dup").merge(eq, "eq_iv"))
    check("중복 정의 모델 → 구조 오류", raises(lambda: wf.dup.solve(), Exception, "둘 이상"))

    print("\n" + "=" * 80)
    print("D. 전망·확률·control·승수·그래프·표·params")
    print("=" * 80)
    check("전망: 외생 경로 없으면 진단", raises(lambda: m.forecast("2020Q1", "2021Q4"), ValueError, "외생변수"))
    fr = quiet(lambda: m.forecast("2020Q1", "2023Q4", exog_fill="last", scenario="baseline"))
    check("전망(기간 확장·외생 채움) → _0 시리즈", fr.counts()["ok"] == 16 and len(wf.data) == 216
          and np.isfinite(wf["Y_0"].iloc[-1]))
    quiet(wf.smpl, "2010Q1", "2011Q4")
    sto = quiet(lambda: m.stochastic(reps=10, seed=3, scenario="baseline"))
    check("stochastic", sto.reps == 10 and (sto.band("Y")["p5"] <= sto.band("Y")["p95"]).all())
    ctrl = quiet(lambda: m.control("Y", "G", {"2010Q1": 600.0, "2010Q2": 600.0}, "2010Q1", "2010Q2",
                                   scenario="baseline"))
    check("control → G_C 시리즈", "G_C" in wf and np.isfinite(ctrl.iloc[wf._index_of("2010Q1")]))
    mu = quiet(lambda: m.multipliers("R", 1.0, scenario="baseline"))
    check("multipliers(금리 +1 → 투자 감소)", mu.level["I"].iloc[-1] < 0)
    g = wf.graph("g1", "P P_*")
    check("그래프(와일드카드)·그림 정의(spec)", list(g.data().columns) == ["P", "P_0", "P_1"]
          and len(g.output().spec()["data"]) == 3)
    tb = wf.table("t1", eq)
    check("표 객체(방정식 → 계수표)", tb.frame.shape[0] == 3)
    eqn.spool.mode = "silent"
    eqn.spool.clear()
    eqn.show(eq, m.blocks(), g)
    check("eqn.show → 스풀에 모음", len(eqn.spool.items) == 3)
    eqn.spool.mode = "auto"
    eqn.spool.clear()
    os.environ["EQUION_PARAMS"] = '{"oil": "1.5", "flag": "yes"}'
    pr = eqn.params(oil=1.0, flag=False, name="x")
    del os.environ["EQUION_PARAMS"]
    check("params: 덮어쓰기·형 변환", pr.oil == 1.5 and pr.flag is True and pr.name == "x")
    check("객체 이름 = 시리즈 이름 → 오류", raises(lambda: wf.equation("CN"), ValueError, "시리즈"))

    print("\n" + "=" * 80)
    print("E. 저장/복원·옛 번들")
    print("=" * 80)
    path = quiet(wf.save, os.path.join(tmp, "toy"))
    w2 = quiet(eqn.wfopen, path)
    check("저장/복원: 시리즈·객체·표본", w2.data.shape == wf.data.shape and set(w2._objects) == set(wf._objects)
          and w2.smpl() == wf.smpl())
    check("복원: 방정식 계수 그대로(재추정 없음)", np.allclose(w2.eq_cp.coefs.to_numpy(), eq.coefs.to_numpy()))
    check("복원: 시나리오 정의", "high_oil" in w2.toy.scenarios
          and "POIL" in w2.toy.scenarios["high_oil"]._sc.exo_overrides)
    quiet(w2.smpl, "1990Q1", "2019Q4")
    quiet(lambda: w2.toy.solve(scenario="baseline"))
    a = w2.to_pandas(["Y_0"]).iloc[s:e + 1].to_numpy()
    check("복원한 모델로 다시 풀어도 같은 결과", np.nanmax(np.abs(a - mine[:, list(ref.columns).index("Y")][:, None])
                                         / np.abs(a)) < 1e-12)
    bpath = quiet(wt.save, os.path.join(tmp, "legacy"))
    w3 = quiet(eqn.wfopen, bpath)
    check("옛 Work Table 번들 가져오기", len(w3.obj("ref").equations) == 6 and len(w3.obj("ref").identities) == 1)

    # 패키지 이름 변경(0.5.0) 이전에 만든 파일도 읽는다
    import json as _json
    import pickle as _pickle
    import shutil as _shutil
    from equion._compat import load_pickle
    old = "macro" + "model"
    legacy = os.path.join(tmp, "legacy_wf.mmw")
    _shutil.copytree(path, legacy)
    mj = os.path.join(legacy, "workfile.json")
    with open(mj, encoding="utf-8") as fh:
        man = _json.load(fh)
    man["format"] = f"{old}-workfile"
    _json.dump(man, open(mj, "w", encoding="utf-8"))
    w4 = quiet(eqn.wfopen, os.path.join(tmp, "legacy_wf"))
    check("옛 워크파일(.mmw·옛 형식 이름) 열기", w4.data.shape == wf.data.shape and "toy" in w4._objects)
    raw = _pickle.dumps(eqn.Scenario("old"), protocol=0).replace(b"cequion.", f"c{old}.".encode())
    sc_old = load_pickle(io.BytesIO(raw))
    check("옛 패키지 경로 pickle 읽기(이름 바꿔 찾기)", f"{old}.".encode() in raw
          and type(sc_old).__module__.startswith("equion.") and sc_old.name == "old")
    os.environ[f"{old.upper()}_PARAMS"] = '{"oil": "2.0"}'
    p_old = eqn.params(oil=1.0)
    del os.environ[f"{old.upper()}_PARAMS"]
    check("옛 환경변수 이름(매개변수)도 읽기", p_old.oil == 2.0)

    print("\n" + "=" * 80)
    print("F. 로그 (print 대신 logging)")
    print("=" * 80)
    import logging
    from equion import log as eqlog
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        eqlog.engine.info("엔진 메시지")
    check("기본 처리기: 찍는 순간의 stdout으로(메시지만)", buf.getvalue() == "엔진 메시지\n")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        eqn.verbose(1)
        wf.smpl("2001Q1 2002Q4")
        eqn.verbose(0)
        wf.smpl("2001Q1 2003Q4")
        eqn.verbose(1)
    check("verbose 1은 워크파일 요약, 0은 감춤", "smpl 2001Q1 ~ 2002Q4" in buf.getvalue()
          and "2003Q4" not in buf.getvalue())
    from equion.workfile.runtime import quiet as eq_quiet
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        eq_quiet(lambda: eqlog.engine.info("감춰질 메시지"))
        eq_quiet(lambda: eqlog.engine.warning("경고는 보임"))
    check("quiet: 엔진 정보는 감추고 경고는 남김", "감춰질" not in buf.getvalue() and "경고는 보임" in buf.getvalue())
    records = []

    class _Grab(logging.Handler):
        def emit(self, r):
            records.append(r.getMessage())
    root = logging.getLogger()
    h = _Grab()
    root.addHandler(h)
    old_level = root.level
    root.setLevel(logging.INFO)
    eqlog.use_own_handler(False)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        eqlog.engine.info("앱 로깅으로")
    eqlog.use_own_handler(True)
    root.removeHandler(h)
    root.setLevel(old_level)
    check("use_own_handler(False): 앱의 logging 설정으로 넘김", "앱 로깅으로" in records and "앱 로깅으로" not in buf.getvalue())

    print("\n" + "=" * 80)
    print("G. 저장 형식(npz)·선택 의존성(pyarrow·plotly 없이도 동작)")
    print("=" * 80)
    import importlib.util
    import json
    import subprocess
    from equion.data.store import read_frame, write_frame
    from equion.workfile.output import GraphOutput
    has_arrow = importlib.util.find_spec("pyarrow") is not None
    has_plotly = importlib.util.find_spec("plotly") is not None
    with tempfile.TemporaryDirectory() as d:
        frames = {
            "dt_us": pd.DataFrame({"A": [1.0, np.nan, 3.0]},
                                  index=pd.DatetimeIndex(["2000-01-01", "2000-04-01", "2000-07-01"]).as_unit("us")),
            "dt_ns": pd.DataFrame({"A": [1.0, 2.0]}, index=pd.DatetimeIndex(["1995-01-01", "2025-04-01"]).as_unit("ns")),
            "int": pd.DataFrame({"B": [0.5, 1.5]}, index=pd.Index([2001, 2002], name="year")),
            "str": pd.DataFrame({"C": [1.0], "D": [2.0]}, index=pd.Index(["x"])),
        }
        ok = True
        for stem, df in frames.items():
            write_frame(d, stem, df)
            back = read_frame(d, stem)
            ok &= (back.index.equals(df.index) and list(back.columns) == list(df.columns)
                   and np.allclose(back.to_numpy(), df.to_numpy(), equal_nan=True) and back.index.name == df.index.name)
        check("npz 표 저장·읽기: 날짜(us·ns)·정수·문자 인덱스, 결측", ok)
        with np.load(os.path.join(d, "dt_us.npz"), allow_pickle=False) as z:
            check("npz: 객체 배열 없음(allow_pickle=False로 열림)", all(z[k].dtype != object for k in z.files))
        check("없는 표 → None", read_frame(d, "nothing") is None)
        legacy = os.path.join(d, "old.parquet")
        if has_arrow:
            frames["dt_us"].to_parquet(legacy)
            check("0.6.0 parquet 표 읽기(pyarrow 있을 때)", read_frame(d, "old").equals(frames["dt_us"]))
        else:
            open(legacy, "wb").close()
            check("0.6.0 parquet 표: pyarrow 없으면 설치 안내", raises(lambda: read_frame(d, "old"), ImportError,
                                                                 "equion[parquet]"))
    go_ = GraphOutput(pd.DataFrame({"A": [1.0, np.nan], "B": [2.0, 3.0]},
                                   index=pd.DatetimeIndex(["2000-01-01", "2000-04-01"])),
                      title="t</script><script>alert(1)</script>")
    sp = go_.spec()
    check("그림 정의: JSON 그대로(결측 → null), 날짜 x", json.loads(json.dumps(sp, allow_nan=False))["data"][0]["y"]
          == [1.0, None] and sp["data"][0]["x"] == ["2000-01-01", "2000-04-01"])
    h = go_.html(include_js=None)
    check("그래프 html: 제목의 </script>가 태그를 끝내지 못함", h.count("</script>") == 1 and "alert(1)</script>" not in h)
    check("figure(): plotly 있으면 Figure, 없으면 설치 안내",
          len(go_.figure().data) == 2 if has_plotly else raises(go_.figure, ImportError, "equion[plot]"))
    code = ("import sys; sys.modules['plotly'] = None; sys.modules['plotly.graph_objects'] = None\n"
            "import os, tempfile, pandas as pd\n"
            "from equion.workfile.output import GraphOutput\n"
            "g = GraphOutput(pd.DataFrame({'A': [1.0, 2.0]}), title='x')\n"
            "d = tempfile.mkdtemp(); p = g.save(os.path.join(d, 'g.html'))\n"
            "assert 'Plotly.newPlot' in open(p, encoding='utf-8').read()\n"
            "assert set(g._repr_mimebundle_()) == {'text/html', 'text/plain'}\n"
            "try:\n    g.figure(); print('no error')\nexcept ImportError as e:\n    print('hint' if 'equion[plot]' in str(e) else e)\n")
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, encoding="utf-8", cwd=ROOT,
                       env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    check("plotly 없이: save('.html')·노트북 표시 동작, figure()는 설치 안내", r.returncode == 0 and r.stdout.strip() == "hint",
          (r.stdout + r.stderr)[-300:])
    from equion.assets import PLOTLY_JS_VERSION, plotly_js
    check("내장 plotly.js(MIT) 버전 일치", plotly_js()[:40].decode().find(f"plotly.js v{PLOTLY_JS_VERSION}") >= 0)

    print("\n" + "=" * 80)
    print("H. 자료 — 메타데이터·페이지·주기 변환·Denton/Chow-Lin·계절조정 (D26)")
    print("=" * 80)
    import json
    from equion.data import transform as TR
    with open(os.path.join(ROOT, "tests", "fixtures", "data_reference.json"), encoding="utf-8") as fh:
        DR = json.load(fh)
    w = quiet(eqn.wfopen, DATA)
    m_ = w.meta("CNNSA", desc="소비(원계열)", unit="조원", agg="sum")
    check("메타데이터: 쓰기·읽기·지우기(None)", m_ == {"desc": "소비(원계열)", "unit": "조원", "agg": "sum"}
          and w.meta("CNNSA", unit=None) == {"desc": "소비(원계열)", "agg": "sum"})
    check("메타데이터: 잘못된 agg → 오류 · 없는 시리즈 → 오류", raises(lambda: w.meta("CNNSA", agg="median"), ValueError)
          and raises(lambda: w.meta("NOPE", desc="x"), KeyError))
    tabm = w.metadata("CNN*").data
    check("메타데이터 표(설명·관측 구간)", tabm.loc["CNNSA", "설명"] == "소비(원계열)" and tabm.loc["CNNSA", "끝"] == "2019Q4")
    q = w["CNNSA"]
    yr = q.groupby(q.index.year)
    ann = quiet(w.convert, "CNNSA", "A")                         # agg=sum (메타데이터)
    exp_sum = yr.sum(min_count=4).where(yr.count() == 4)
    w["CNX"] = q.where(q.index < pd.Timestamp("2019-07-01"))      # 마지막 해가 반만 있는 시리즈
    annx = quiet(w.convert, "CNX", "A", method="sum")
    check("Q→A 합(메타데이터 agg) = 연도별 합, 부분연도는 결측", close(ann.dropna().to_numpy(), exp_sum.dropna().to_numpy(), 1e-14)
          and len(ann) == 50 and np.isnan(annx.loc["2019-01-01"]) and np.isfinite(annx.loc["2018-01-01"]))
    cpi_a = quiet(w.convert, "P", "A", method="mean")
    check("Q→A 평균·첫/끝 값", close(cpi_a.dropna().to_numpy(), w["P"].groupby(w.index.year).mean().to_numpy(), 1e-14)
          and close(quiet(w.convert, "P", "A", method="last").loc["2000-01-01"], w["P"].loc["2000-10-01"], 1e-15))
    pg = quiet(w.page, "annual", "A")
    quiet(w.convert, "CNNSA", pg)
    check("페이지: 만들기·다시 얻기·주기 불일치 오류, convert(to=페이지)가 쓰고 메모를 남김",
          w.page("annual") is pg and raises(lambda: w.page("annual", "M"), ValueError)
          and close(pg["CNNSA"].dropna(), exp_sum.dropna().to_numpy(), 1e-14) and "sum(Q→A)" in pg.meta("CNNSA")["notes"])
    qp = quiet(pg.page, "q", "Q")
    a_ser = pg["CNNSA"].dropna()
    quiet(pg.convert, "CNNSA", qp, method="split", name="RS")
    quiet(pg.convert, "CNNSA", qp, method="constant", name="RC")
    quiet(pg.convert, "CNNSA", qp, method="linear", name="RLIN")
    rs_, rc_, rl_ = (qp[n].dropna() for n in ("RS", "RC", "RLIN"))
    check("A→Q split(합 보존)·constant(반복)·linear(마지막 분기 = 연 값)",
          close(rs_.groupby(rs_.index.year).sum().to_numpy(), a_ser.to_numpy(), 1e-12)
          and close(rc_.groupby(rc_.index.year).mean().to_numpy(), a_ser.to_numpy(), 1e-12)
          and close(rl_[rl_.index.month == 10].to_numpy(), a_ser.to_numpy(), 1e-12))
    dd = DR["denton"]
    xd = TR.denton(dd["annual"], 4, dd["indicator"], "sum")
    check("Denton(비례, 1차 차분) = 기준값(statsmodels dentonm)", close(xd, dd["x"], 1e-8)
          and close(TR.denton(dd["annual"], 4, dd["indicator_ext"], "sum"), dd["x_ext"], 1e-8))
    ok = True
    for conv in ("sum", "average", "first", "last"):
        x_ = TR.denton(dd["annual"], 4, dd["indicator"], conv)
        agg_ = x_.reshape(-1, 4)
        got_ = {"sum": agg_.sum(1), "average": agg_.mean(1), "first": agg_[:, 0], "last": agg_[:, 3]}[conv]
        ok &= close(got_, dd["annual"], 1e-10)
    check("Denton 제약 4종(sum·average·first·last) 정확히 만족", ok)
    quiet(pg.convert, "CNNSA", qp, method="denton", name="RD")
    rd_ = qp["RD"].dropna()
    check("convert denton(지표 없음, agg=sum → 합 제약)", close(rd_.groupby(rd_.index.year).sum().to_numpy(), a_ser.to_numpy(), 1e-9))
    ind = w["CN"]
    cl = quiet(pg.convert, "CNNSA", qp, method="chow-lin", indicator=ind, name="RCL")
    rcl = qp["RCL"].dropna()
    yv, Xv = a_ser.to_numpy(), np.column_stack([np.ones(len(rcl)), ind.reindex(rcl.index).to_numpy()])
    Cm = np.kron(np.eye(len(yv)), np.ones((1, 4)))
    rho_ = cl.attrs["convert"]["rho"]

    def cl_fixed(r):
        jj = np.arange(len(rcl))
        V = r ** np.abs(jj[:, None] - jj[None, :]) / (1 - r * r)
        W = Cm @ V @ Cm.T
        Wi = np.linalg.inv(W)
        b = np.linalg.solve((Cm @ Xv).T @ Wi @ (Cm @ Xv), (Cm @ Xv).T @ Wi @ yv)
        u = yv - Cm @ Xv @ b
        s2 = u @ Wi @ u / len(yv)
        return Xv @ b + V @ Cm.T @ Wi @ u, -0.5 * len(yv) * (np.log(2 * np.pi * s2) + 1) - 0.5 * np.linalg.slogdet(W)[1]
    grid = np.linspace(-0.99, 0.99, 1981)
    rbest = grid[int(np.argmax([cl_fixed(r)[1] for r in grid]))]
    check("Chow-Lin: 합 제약 정확, 고정 ρ의 GLS 식 그대로(독립 계산), ρ = 로그우도 최대(촘촘한 격자)",
          close(rcl.groupby(rcl.index.year).sum().to_numpy(), yv, 1e-9) and close(rcl.to_numpy(), cl_fixed(rho_)[0], 1e-9)
          and abs(rho_ - rbest) < 2e-3, f"ρ = {rho_:.4f}")
    check("chow-lin 지표 없음 → 오류", raises(lambda: pg.convert("CNNSA", qp, method="chow-lin"), ValueError, "indicator"))
    y_ = w["CNNSA"].dropna().to_numpy()
    ok = True
    for key, d_ in DR["stl_log"].items():
        S_, T_, R_, W_ = TR.stl(np.log(y_), 4, **d_["kw"])
        ok &= close(S_, d_["seasonal"], 1e-9, 1e-12) and close(T_, d_["trend"], 1e-9) and close(W_, d_["weights"], 1e-8, 1e-10)
        if not ok:
            print("     STL 불일치:", key)
    check("STL(기본·강건·창 지정 4종) 계절·추세·강건 가중치 = 기준값(statsmodels)", ok)
    ok = True
    for model, d_ in DR["classical"].items():
        S_, T_, R_ = TR.classical(y_, 4, model)
        tr_ = np.array([np.nan if v is None else v for v in d_["trend"]])
        ok &= close(S_, d_["seasonal"], 1e-12) and np.array_equal(np.isnan(T_), np.isnan(tr_)) \
            and close(T_[~np.isnan(T_)], tr_[~np.isnan(tr_)], 1e-12)
    check("고전 분해(가법·승법) = 기준값(statsmodels seasonal_decompose)", ok)
    r_ = quiet(w.seas, "CNNSA", model="multiplicative")
    S_, _, _, _ = TR.stl(np.log(y_), 4)
    check("wf.seas 승법 STL: 로그 분해의 exp가 계절 요인, 조정 = 실측/요인, _SA·_SF 씀",
          close(w["CNNSA_SF"].dropna(), np.exp(S_), 1e-12) and close(w["CNNSA_SA"].dropna(), y_ / np.exp(S_), 1e-12)
          and close(r_.table["조정"], y_ / np.exp(S_), 1e-12))
    r2_ = quiet(w.seas, "CNNSA", method="classical", name="CNC", write=True)
    check("wf.seas 고전 가법: 조정 = 실측 − 계절", close(w["CNC_SA"].dropna(), y_ - TR.classical(y_, 4)[0], 1e-12)
          and len(r2_.table) == len(y_))
    check("연간 계절조정 → 오류", raises(lambda: pg.seas("CNNSA"), ValueError, "연간"))
    with tempfile.TemporaryDirectory() as tmp:
        quiet(w.save, os.path.join(tmp, "pg.eqw"))
        w5 = quiet(eqn.wfopen, os.path.join(tmp, "pg.eqw"))
        check("저장·열기: 메타데이터·페이지(페이지 안 페이지까지)", w5.meta("CNNSA")["agg"] == "sum"
              and "annual" in w5.pages and "q" in w5.page("annual").pages
              and close(w5.page("annual").page("q")["RD"].dropna(), rd_, 1e-15))

    print("\n" + "=" * 80)
    total = len(PASS) + len(FAIL)
    print(f"  RESULT: {len(PASS)} PASS / {len(FAIL)} FAIL  (total {total})  — {time.time() - t0:.1f}s")
    print("  " + ("[OK] ALL PASSED!" if not FAIL else "실패: " + ", ".join(FAIL)))
    print("=" * 80)
    return len(FAIL)


def test_suite():
    """pytest 진입점 — 이 파일의 검사 묶음 전체(하나라도 실패하면 실패). `python tests/test_workfile.py`와 같은 검사."""
    assert main() == 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(99)
