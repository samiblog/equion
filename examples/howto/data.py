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
