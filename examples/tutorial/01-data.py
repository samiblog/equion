# 이 파일은 docs/tutorial/01-data.md에서 만든다(python docs/build_docs.py) — 고치려면 문서를 고친다.
"""1. 자료 다루기 — 문서: docs/tutorial/01-data.md"""


# %% 1.1 워크파일 열기
import numpy as np
import pandas as pd
import equion as eqn

wf = eqn.datasets.load("toy_q")                     # ① 패키지에 든 예제 자료
print(wf)
print(wf.freq, wf.smpl(), len(wf.data))
path = eqn.datasets.path("toy_q")
with open(path, encoding="utf-8") as f:
    for line in f.read().splitlines()[:3]:
        print(line[:60] + " …")
wf_file = eqn.wfopen(path, name="from_file")
print(wf_file.freq, wf_file.series()[:5])
sim = eqn.wfcreate("sim", "Q", "2020Q1", "2025Q4")
sim["X"] = np.arange(len(sim.data), dtype=float)      # 전체 기간에 배열을 넣는다
sim["G"] = 1.5                                         # 스칼라는 모든 기간에 같은 값
print(sim.to_pandas(labels=True).head(3))

# %% 1.2 시리즈 읽기와 쓰기
y = wf["y"]                       # Y와 같다
print(type(y).__name__, y.index[0].date(), round(y.iloc[-1], 2))
print(wf.elem("Y", "2010Q1"))     # 한 기간의 값은 elem
print(wf.to_pandas(["Y", "CN"], labels=True).loc["2010Q1":"2010Q3"].round(2))
wf["YD"] = wf["Y"] - wf["G"]                      # 가처분소득 비슷한 것
wf["SHORT"] = wf["Y"].iloc[:4]                    # 처음 4기만 값이 있다
print(wf["SHORT"].notna().sum(), wf.series("Y*"))
del wf["SHORT"]
try:  # 이 예는 일부러 오류를 보인다
    wf["C"] = 1.0
except Exception as e:
    print(f"{type(e).__name__}: {e}")

# %% 1.3 표본
wf.smpl("2000Q1", "2019Q4")
print(wf.smpl())
wf.smpl("@all")                   # 전체 기간으로
print(wf.smpl())
wf.smpl("@first", "1989Q4")       # 처음 ~ 1989Q4
print(wf.smpl())
wf.smpl("@all")

# %% 1.4 식으로 시리즈 만들기 — genr
wf.genr("GY = Y.yoy")                          # 전년동기대비 증가율(%)
wf.genr("LY = log(Y)")
wf.genr("TR = @trend")                         # 0, 1, 2, …
print(wf.to_pandas(["Y", "GY", "LY", "TR"], labels=True).loc["1971Q1":"1971Q2"].round(3))
wf.smpl("2019Q1", "2019Q4")
wf.genr("FLAG = 1")                            # 표본 안만 1
wf.smpl("@all")
print(int(wf["FLAG"].sum()), wf["FLAG"].isna().sum())
sim.genr("PATH = 100")
sim.smpl("2020Q2", "2025Q4")
sim.genr("PATH = PATH(-1) * 1.01")             # 분기 1% 성장
sim.smpl("@all")
print(sim.to_pandas(["PATH"], labels=True).round(2).head(4))
print(wf.eval("dlog(Y) * 400").dropna().round(2).head(3).tolist())   # 연율 성장률
wf.genr("GAP", lambda d: d.Y / d.Y.rolling(8).mean() - 1)            # d는 시리즈 DataFrame
print(round(wf.elem("GAP", "2010Q1"), 4))

# %% 1.5 설명·단위 — 메타데이터
wf.meta("YD", desc="소득 − 정부지출", unit="조원(가상)", agg="sum")
print(wf.meta("YD"))
eqn.show(wf.metadata("Y*"))

# %% 1.6 기간 늘리기와 앞날 채우기
wf.extend("2021Q4")
print(wf.smpl(), wf["G"].iloc[-8:].isna().all())
wf.fill("G", method="trend", window=20)       # 최근 20기 평균 증분 지속('last' 유지, 'growth' 평균 성장률)
wf.fill("R", method="last")
print(wf.to_pandas(["G", "R"], labels=True).loc["2019Q3":"2020Q2"].round(2))

# %% 1.7 주기 바꾸기
ya = wf.convert("Y", "A")                      # Y의 agg는 sum → 연간 합(돌려주는 것은 연간 pandas Series)
for d, v in ya.dropna().tail(2).items():
    print(d.year, round(v, 1))
print(wf.convert("R", "A", method="last").iloc[:2].round(3).tolist())
mon = wf.page("mon", "M")                      # 같은 기간의 월간 페이지
mon.read(eqn.datasets.path("toy_m"))           # 페이지에 월간 지표(산업생산 IP 등)를 읽는다
wf.convert("Y", mon, method="denton", indicator="IP", name="Y_M", start="2000Q1", end="2019Q4")   # 지표가 있는 구간만
chk = mon.convert("Y_M", "Q").loc["2010-01-01":"2010-07-01"]      # 다시 분기로 합치면 원래 값
print(chk.round(3).tolist(), wf["Y"].loc["2010-01-01":"2010-07-01"].round(3).tolist())

# %% 1.8 계절조정
r = wf.seas("CNNSA")
print(wf.series("CNNSA*"))
print(wf.to_pandas(["CNNSA", "CNNSA_SA", "CNNSA_SF"], labels=True).loc["2010Q1":"2010Q4"].round(2))
wm = eqn.datasets.load("toy_m")
wm.seas("IP", model="multiplicative")
print(wm.to_pandas(["IP", "IP_SA", "IP_SF"], labels=True).loc["2010M1":"2010M3"].round(3))

# %% 1.9 파일로 주고받기와 저장
wf.write("toy_out.xlsx", ["Y", "CN", "I"])                 # 기본은 표본 구간
wf.write("toy_out.csv", ["Y", "CN", "I"])
other = eqn.wfcreate("other", "Q", "1970Q1", "2019Q4")
print(other.read("toy_out.csv"))                           # 파일의 시리즈를 가져온다
wf.save("tutorial1")                                       # tutorial1.eqw/ 폴더
again = eqn.wfopen("tutorial1.eqw")
print(again.smpl(), again.meta("YD")["desc"], list(again.pages))
