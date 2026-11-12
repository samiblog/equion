# 이 파일은 docs/howto/data.md에서 만든다(python docs/build_docs.py) — 고치려면 문서를 고친다.
"""레시피: 자료 — 문서: docs/howto/data.md"""


# %% 레시피: 자료
import numpy as np
import pandas as pd
import equion as eqn

wf = eqn.datasets.load("toy_q")

# %% R1. 첫 열이 날짜가 아닌 파일 열기
raw = pd.DataFrame({"name": ["a", "b", "c", "d"], "date": ["2020Q1", "2020Q2", "2020Q3", "2020Q4"],
                    "SALES": [10.0, 11.0, 12.5, 13.0]})
raw[["date", "SALES"]].to_csv("sales.csv", index=False)       # 날짜를 첫 열로
w1 = eqn.wfopen("sales.csv")
print(w1.freq, w1.to_pandas(labels=True)["SALES"].tolist())

# %% R2. 여러 파일을 한 워크파일로
wf.write("part_a.csv", ["Y", "CN"])
wf.write("part_b.csv", ["I", "G"])
w2 = eqn.wfcreate("merged", "Q", "1970Q1", "2019Q4")
w2.read("part_a.csv")
w2.read("part_b.csv")
print(w2.series())

# %% R3. 빠진 기간이 있는 자료
gap = wf.to_pandas(["Y"], labels=True).iloc[:8].drop(index=["1970Q3"])     # 한 분기 빠짐
gap.to_csv("gap.csv")
w3 = eqn.wfopen("gap.csv")
print(w3.to_pandas(labels=True)["Y"].round(1).tolist())
w3["Y"] = w3["Y"].interpolate()                                             # 선형 보간
print(round(w3.elem("Y", "1970Q3"), 1))

# %% R4. 이름 바꾸기·복사하기 — 그리고 `C`라는 열
raw = pd.DataFrame({"period": ["2020Q1", "2020Q2", "2020Q3"], "C": [1.0, 2.0, 3.0]})
raw.to_csv("with_c.csv", index=False)
import warnings
with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always")
    w4 = eqn.wfopen("with_c.csv")
print(str(caught[0].message)[:60])
w4.data.rename(columns={"C": "CONS"}).to_csv("renamed.csv", index_label="period")
print(eqn.wfopen("renamed.csv").series())

# %% R5. 파생 시리즈를 한꺼번에
for v in ("Y", "CN", "I"):
    wf.genr(f"G_{v} = {v}.yoy")              # 전년동기대비 %
    wf.genr(f"L_{v} = log({v})")
print(wf.series("G_*"), round(wf.elem("G_Y", "2019Q4"), 2))

# %% R6. 분기 ↔ 연간
ya = wf.convert("Y", "A")                                # 흐름(agg='sum')은 합
ra = wf.convert("R", "A")                                # 금리(agg='mean')는 평균
print(round(float(ya.iloc[-1]), 1), round(float(ra.iloc[-1]), 3))
ann = wf.page("ann", "A")                                # 연간 합을 다시 분기로 나눌 때는 연간 페이지에서
wf.convert("Y", ann, name="YA")
print(round(float(ann.convert("YA", "Q", method="split").iloc[:4].sum()), 1) == round(float(ya.iloc[0]), 1))

# %% R7. 월간 지표로 분기 자료를 월간으로 나누기
mon = wf.page("mon", "M")
mon.read(eqn.datasets.path("toy_m"))
wf.convert("Y", mon, method="chow-lin", indicator="IP", name="Y_M", start="2000Q1", end="2019Q4")
q_back = mon.convert("Y_M", "Q").loc["2010-01-01":"2010-10-01"].round(3).tolist()
print(q_back == wf["Y"].loc["2010-01-01":"2010-10-01"].round(3).tolist())

# %% R8. pandas와 오가기
df = wf.to_pandas(["Y", "CN", "I"], smpl=False)
df["SHARE"] = df["CN"] / df["Y"]                         # pandas로 계산
wf["SHARE"] = df["SHARE"]                                # 다시 워크파일로(날짜로 맞춰 들어간다)
print(round(wf.elem("SHARE", "2019Q4"), 4))
new = eqn.wfcreate("from_df", "Q", "1970Q1", "2019Q4")
for c in df.columns:
    new[c] = df[c]
print(new.series())

# %% R49. 원자료에서 자료 회차로 — 넣기·만들기·차이·바꾸기
p = eqn.Project.create("data_prj", force=True)       # 예제 프로젝트 — 첫 회차를 만들어 지금 회차로
v0 = p.vintage
raw = pd.read_csv("data_prj/DATA/raw/toy_q.csv", index_col=0)
raw.loc["2019Q1":"2019Q4", "CN"] *= 1.01             # 받은 새 자료: 지난 4분기 소비 개정
raw.loc["2020Q1"] = raw.iloc[-1] * 1.005             # + 새 분기
raw.to_csv("toy_q_new.csv")
print(p.data_add("toy_q_new.csv", source="na").text())   # 틀 검사 뒤 넣기 — 명령줄 equion data add toy_q_new.csv --source na
r = p.data_build()                                   # 새 회차 — 지금 회차는 아직 그대로
print(r.text())
print(p.data_diff().text())                          # 지금 회차 → 새 회차: 새 기간·개정(기간·크기)
print(p.data_impact().text())                        # 바뀐 시리즈를 쓰는 식·모형(다시 계산하지 않는다)
p.data_use(r.id)                                     # 이 회차로 바꾸기 — equion.toml [data] vintage
h = p.hs("main")                                     # [hs] range = "2005Q1:last" — 새 끝(2020Q1)까지
print(h.start, h.end, h.counts()["ok"])

# %% R59. 새 원자료를 정의에 — 미리 보고, 열을 시리즈로
p = eqn.Project.create("def_prj", force=True)
with open("def_prj/DATA/raw/kr.csv", "w", encoding="utf-8") as f:      # 받은 파일(가상): 제목 줄 · 열 이름 · 단위 줄 · 결측 표시 · 천 단위
    f.write('표 1. 지출(가상)\n시점,민간소비,GDP\n,십억원,십억원\n2018년 3/4분기,"1,195.0","2,931.9"\n2018년 4/4분기,"1,198.3","2,940.2"\n'
            '2019년 1/4분기,"1,201.5","2,950.1"\n2019년 2/4분기,-,"2,961.0"\n2019년 3/4분기,"1,214.2","2,975.4"\n2019년 4/4분기,"1,220.8","2,990.3"\n')
print(p.data_preview("DATA/raw/kr.csv").error)                         # 틀 없이 읽으면 어디서 막히는지(칸 위치)
print(p.data_preview("DATA/raw/kr.csv", header_row=2, unit_row=3, missing="-", thousands=",", rows=4).text())
r = p.data_define("kr", file="DATA/raw/kr.csv", header_row=2, unit_row=3, missing="-", thousands=",",
                  series={"KCN": {"column": "민간소비", "desc": "민간소비", "fill": "linear"}, "KGDP": "GDP"})
print(r.text())
b = p.data_build(use=True)                                             # 정의만으로는 자료가 생기지 않는다 — 만들고, 바꾼다
print(b.n_series, p.workfile["KCN"].dropna().round(1).tolist())

# %% R64. 시점이 열로 가는 통계표 · 머리줄이 여러 줄인 표
p = eqn.Project.create("wide_prj", force=True)
with open("wide_prj/DATA/raw/kosis.csv", "w", encoding="utf-8") as f:   # 받은 표(가상): 시점이 오른쪽으로, 줄마다 시리즈
    f.write("표 1. 산업별 생산(가상)\n항목,단위,2018 1/4,2018 2/4,2018 3/4,2018 4/4\n제조업,십억원,100,101,103,104\n서비스업,십억원,200,202,-,205\n")
v = p.data_preview("DATA/raw/kosis.csv", time_axis="columns", time_row=2, name_col="A", missing=["-"])
print(v.text())
with open("wide_prj/DATA/raw/na2.csv", "w", encoding="utf-8") as f:     # 머리줄 두 줄 — 위 줄은 병합 칸
    f.write("시점,국내총생산,,소비,\n,명목,실질,명목,실질\n2018Q1,10,9,6,5\n2018Q2,11,10,6.5,5.2\n2018Q3,12,11,7,5.4\n")
print([c["name"] for c in p.data_preview("DATA/raw/na2.csv", header_row=[1, 2]).columns])
print(p.data_define("kosis", file="DATA/raw/kosis.csv", time_axis="columns", time_row=2, name_col="A", missing=["-"],
                    series={"MFG": "제조업"}).text())
