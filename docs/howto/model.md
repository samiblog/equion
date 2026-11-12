# 레시피: 모델

```python
import pandas as pd
import equion as eqn

wf = eqn.datasets.load("toy_q")
eq_i = wf.equation("eq_i").ls("I c Y(-1) R")
eq_cn = wf.equation("eq_cn").tsls("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
eq_p = wf.equation("eq_p").ls("dlog(P) c dlog(Y) dlog(POIL)")
m = wf.model("toy").merge(eq_i, eq_cn, eq_p).append("Y = CN + I + G")
```
<!-- out -->
```text
[toy_q] 열기 toy_q.csv — 분기(Quarterly) 1970Q1~2019Q4 · 시리즈 10
[eq_i] OLS I — n=199, R²=0.9985
[eq_cn] TSLS CN — n=199, R²=0.9999
[eq_p] OLS dlog(P) — n=199, R²=0.3271
```

## R20. 방정식 파일로 모델 관리하기

식을 글 파일 하나에 두면 고치기·비교·버전 관리가 쉽습니다. 한 줄에 한 식, `#` 뒤는 주석, 추정법 지시자(`@inst`)도 씁니다.

```python
with open("model.txt", "w", encoding="utf-8") as f:
    f.write("""# 작은 거시 모형
I c Y(-1) R
CN c Y CN(-1) @inst G R CN(-1) Y(-1)
dlog(P) c dlog(Y) dlog(POIL)
Y = CN + I + G
""")
mf = wf.model("from_file").merge("model.txt")
print(mf.endogenous, [o.eq.method for o in mf.equations])
```
<!-- out -->
```text
[from_file] merge model.txt — 추정식 3/3 · 항등식 1
['CN', 'I', 'P', 'Y'] ['ols', 'tsls', 'ols']
```

실행 전에 문법·구조·결측 입력을 검사하려면 명령줄 `equion check model.txt --data 자료.csv`([명령줄 레시피](cli.md)).

## R21. 모델 일부만 풀기

```python
part = wf.model("no_price").merge(eq_i, eq_cn).append("Y = CN + I + G")     # 물가식 빼고 새로
print(part.endogenous)
fix = m.scenario("i_actual").exclude("I")                                   # 같은 모델에서 I만 실측으로
print(m.solve("2015Q1", "2015Q4").counts())
m.scenario("baseline")
```
<!-- out -->
```text
['CN', 'I', 'Y']
[toy] i_actual(_1) dynamic 2015Q1~2015Q4: 정상 4 · 일부식 제외 0 · 실패대체 0 · 실패 0
{'ok': 4, 'partial': 0, 'fallback': 0, 'failed': 0}
```

## R22. 수렴하지 않을 때

순서대로 확인합니다: ① `on_fail="stop"`으로 처음 실패한 기간과 블록 보기, ② 정적 풀이(`mode="static"`)가 되는지(되면
동태 불안정 의심 — `m.stability()`), ③ 풀이법·반복 수·시작값 바꾸기.

```python
r = m.solve("2010Q1", "2010Q4", method="newton", fallback=("hybr", "lm", "gauss-seidel"),
            tolerance=1e-10, max_iterations=100)
print(r.counts(), r.status()["iterations"].tolist())
print(m.stability("2010Q1").verdict)
```
<!-- out -->
```text
[toy] baseline(_0) dynamic 2010Q1~2010Q4: 정상 4 · 일부식 제외 0 · 실패대체 0 · 실패 0
{'ok': 4, 'partial': 0, 'fallback': 0, 'failed': 0} [4, 4, 4, 5]
단위근
```

## R23. 과거 재현 결과를 엑셀로

```python
wf.smpl("1975Q1", "2019Q4")
r = m.solve()
r.save("hs/hs_toy.csv")                                         # 상태 열 + 변수별 풀이·실측·오차(%)
cmp = wf.to_pandas(["Y", "Y_0", "CN", "CN_0"], smpl=True, labels=True)
with pd.ExcelWriter("hs_toy.xlsx") as xw:
    cmp.to_excel(xw, sheet_name="경로")
    r.statistics().to_excel(xw, sheet_name="적합도")
print(sorted(r.statistics().columns)[:4])
```
<!-- out -->
```text
[toy_q] smpl 1975Q1 ~ 2019Q4
[toy] baseline(_0) dynamic 1975Q1~2019Q4: 정상 180 · 일부식 제외 0 · 실패대체 0 · 실패 0
['MAE', 'MAE_pct', 'RMSE', 'RMSPE']
```

## R24. 출발 시점별 과거 재현 비교

동적 풀이의 오차는 출발점에서 쌓이므로, 출발 시점을 바꿔 보면 모델이 어디서 흔들리는지 보입니다.

```python
rows = {}
for start in ("1980Q1", "1990Q1", "2000Q1", "2010Q1"):
    st = m.solve(start, "2019Q4").statistics()
    rows[start] = st["RMSPE"]
print(pd.DataFrame(rows).round(3))
```
<!-- out -->
```text
[toy] baseline(_0) dynamic 1980Q1~2019Q4: 정상 160 · 일부식 제외 0 · 실패대체 0 · 실패 0
[toy] baseline(_0) dynamic 1990Q1~2019Q4: 정상 120 · 일부식 제외 0 · 실패대체 0 · 실패 0
[toy] baseline(_0) dynamic 2000Q1~2019Q4: 정상 80 · 일부식 제외 0 · 실패대체 0 · 실패 0
[toy] baseline(_0) dynamic 2010Q1~2019Q4: 정상 40 · 일부식 제외 0 · 실패대체 0 · 실패 0
    1980Q1  1990Q1  2000Q1  2010Q1
CN   0.519   0.543   0.510   0.329
I    1.032   0.920   0.843   0.613
P    1.204   1.780   0.908   0.527
Y    0.499   0.510   0.477   0.300
```

## R25. 식 하나를 바꿨을 때 모델 성능 비교

```python
base = m.solve("1990Q1", "2019Q4").statistics()["RMSPE"]
alt_cn = wf.equation("eq_cn_alt").ls("CN c Y CN(-1)")                       # TSLS 대신 OLS
m_alt = wf.model("toy_alt").merge(eq_i, alt_cn, eq_p).append("Y = CN + I + G")
alt = m_alt.solve("1990Q1", "2019Q4").statistics()["RMSPE"]
print(pd.DataFrame({"TSLS 소비식": base, "OLS 소비식": alt}).round(3))
```
<!-- out -->
```text
[toy] baseline(_0) dynamic 1990Q1~2019Q4: 정상 120 · 일부식 제외 0 · 실패대체 0 · 실패 0
[eq_cn_alt] OLS CN — n=180, R²=0.9999
[toy_alt] baseline(_0) dynamic 1990Q1~2019Q4: 정상 120 · 일부식 제외 0 · 실패대체 0 · 실패 0
    TSLS 소비식  OLS 소비식
Y      0.510    0.534
CN     0.543    0.570
I      0.920    0.945
P      1.780    1.767
```

같은 별칭(`_0`)에 쓰므로 비교할 때는 결과를 먼저 꺼내 둡니다(`statistics()` · `to_pandas`). 별칭을 나누려면 시나리오를 쓰세요.

관련: [튜토리얼 4](../tutorial/04-model.md) · [연립 풀이 해설](../explain/solving.md)

## R48. 프로젝트로 블록·모형 조립하기

식을 블록(방정식 파일 하나)으로 나누고, `equion.toml`에서 블록과 다른 모형을 이름으로 끼워 모형을 조립합니다(형식은
[파일 형식](../reference/formats.md#프로젝트equiontoml)). 예제 프로젝트는 명령줄 `equion new 폴더 --template desk`로도 만듭니다.

```python
p = eqn.Project.create("demo_prj", force=True)   # 블록 demand·price·finance, 모형 core·main·main_fixrl
print(p.assemble("main").text())          # 계산 없이 조립 검사 — 명령줄 equion assemble main
```
<!-- out -->
```text
[demo_prj] 자료 회차 d2026-11a를 만들었습니다
[demo_prj] 지금 자료 회차: d2026-11a
[demo_prj] 열기 series.csv — 분기(Quarterly) 1970Q1~2019Q4 · 시리즈 13
[assemble main] 수요 + 물가 + 금융 — 블록 3 · 추정식 5 · 항등식 1
  조립   main = core(demand) + price + finance
  내생 6  CN · I · Y · P · RL · M2
  외생 3  G(~2019Q4) · POIL(~2019Q4) · R(~2019Q4)
  연결   demand →Y→ price · price →P→ finance · demand →Y→ finance
  풀이   블록 5 (동시 CN·Y)
  문제   없음
```

```python
r = p.hs("main")                          # [hs]의 구간·방식으로 과거 재현 — 식은 지금 자료로 추정해 조립
print(r.statistics()["RMSPE"].round(3))
print(p.hs("demand").counts())            # 블록 HS — 수요 블록만 풀고 나머지 변수는 실측
print(p.ident("demand:Y").text())         # 항등식을 실측으로 검사 — 명령줄 equion ident demand:Y --check
```
<!-- out -->
```text
[main] 채택 기록 없이 지금 자료로 추정: demand:CN, demand:I, price:P, finance:RL, finance:M2
[main] baseline(_0) dynamic 2005Q1~2019Q4: 정상 60 · 일부식 제외 0 · 실패대체 0 · 실패 0
Y     0.474
CN    0.505
I     0.857
P     1.435
M2    2.243
RL    9.682
Name: RMSPE, dtype: float64
[demand] baseline(_0) dynamic 2005Q1~2019Q4: 정상 60 · 일부식 제외 0 · 실패대체 0 · 실패 0
{'ok': 60, 'partial': 0, 'fallback': 0, 'failed': 0}
[ident demand:Y] Y = CN + I + G   (EQUATIONS/demand.txt:4)
  구간   1970Q1~2019Q4 · 비교 200기
  결과   성립 · 최대 |차이| 1e-06 · 최대 |차이%| 3.431e-07%
```

모형을 고치기 전에 영향 범위는 `p.used_by("demand")`, 파일을 바꾸지 않고 식 하나만 바꿔 보려면 `p.hs("main", swap={"demand:CN": "CN c Y"})`.

## R50. 후보 식 고르기 — 추정 기록·비교·바꿔 끼운 HS·채택

식을 고를 때마다 작업 기록을 남기면 무엇을 해 봤고 왜 골랐는지가 기록 이름으로 남습니다(D33). 식 글자의 목표변수가 한 부품의 목표면 그 부품의
후보가 되고, `[criteria]`(기대 부호·진단·|t|)로 통과·걸러짐과 까닭이 붙습니다. 명령줄은 `equion est · compare · hs --swap · adopt`.

```python
c1 = p.est("demand:CN", as_name="cons_c1", sim=True)          # 블록 파일의 그 줄 — equion est demand:CN --as cons_c1 --sim
c3 = p.est("CN c Y(-1) CN(-1)", as_name="cons_c3", sim=True)  # 식 글자 — 목표가 CN이라 demand:CN의 후보
print(c3.text())
print(p.compare(part="demand:CN").table[["식", "R²adj", "LM(2) p", "기준", "단독 RMSPE%"]].round(4))
```
<!-- out -->
```text
[est:cons_c3] OLS CN · 1970Q2~2019Q4 · n=199   R²adj 0.9993 · SE 1.850 · DW 2.223 · AIC 812.5 · BIC 822.4
  계수   c 13.446(t 4.552) · Y(-1) 0.6259(t 4.255) · CN(-1) 0.1235(t 0.5993)
  진단   LM(2) p=0.237 ✓ · White p=0.736 ✓ · JB p=0.048 ! · RESET p=0.997 ✓ · LB(4) p=0.107 ✓
  기준   통과 · 부호 Y + (항 없음)
  단독 모의  2005Q1~2019Q4 CN RMSPE 0.39%
  알아서 한 것  시차·결측으로 표본 시작 1970Q1 → 1970Q2
  기록   est:cons_c3 (work/est/cons_c3/) · demand:CN 후보
                             식   R²adj  LM(2) p                  기준  단독 RMSPE%
기록
est:cons_c1      CN c Y CN(-1)  0.9999   0.0465  걸러짐: LM(2) p=0.046     0.1214
est:cons_c3  CN c Y(-1) CN(-1)  0.9993   0.2368                  통과     0.3937
```

```python
before = p.hs("main", record=True, as_name="before")
after = p.hs("main", record=True, swap={"demand:CN": "est:cons_c3"}, vs="hs:before")   # 파일은 그대로, 그 기록의 계수로
print(after.text())
print(p.adopt("est:cons_c1").text())        # c3는 기준은 통과했지만 HS가 나빠졌다 — 지금 식(c1)을 채택(계수 고정)
```
<!-- out -->
```text
[main] baseline(_0) dynamic 2005Q1~2019Q4: 정상 60 · 일부식 제외 0 · 실패대체 0 · 실패 0
[main] baseline(_0) dynamic 2005Q1~2019Q4: 정상 60 · 일부식 제외 0 · 실패대체 0 · 실패 0
[hs:hs_0001] main dynamic 2005Q1~2019Q4 · 정상 60 · 일부식 제외 0 · 실패대체 0 · 실패 0
  RMSPE  Y 0.67% · CN 0.77% · I 0.86% · P 1.51% · M2 2.38% · RL 9.68%
  비교   vs hs:before — Y 0.47% → 0.67% · CN 0.51% → 0.77% · I 0.86% → 0.86% · P 1.43% → 1.51% · M2 2.24% → 2.38% (나머지 그대로)
  바꿔 끼움  demand:CN ← est:cons_c3 (파일은 그대로)
  알아서 한 것  구간 [hs] range = 2005Q1:last → 2005Q1~2019Q4 · 바꿔 끼움: demand:CN ← est:cons_c3
  기록   hs:hs_0001 (work/hs/hs_0001/)
[adopt] demand:CN ← est:cons_c1
  블록 파일  그대로(같은 식)
  채택표   EQUATIONS/adopted.toml
  바뀜 기록  h0002 (EQUATIONS/adopted.toml)
  다음   모형을 풀면 이 기록의 계수를 쓴다(다시 추정하지 않음)
```

판단 기준은 거르는 표시일 뿐 고르는 것은 사람입니다 — 걸러진 c1이라도 HS로 견주어 고를 수 있고, 다른 후보를 채택하면 블록 파일의 그 줄도
그 식으로 바뀝니다. 채택한 식은 자료 회차를 바꿔도 다시 추정하지 않습니다. 새 자료로 다시 추정하려면 `p.reestimate("main", adopt="if_pass")`(명령줄
`equion est --adopted --adopt if_pass`) — 기준을 통과한 식만 새 계수로, 걸린 식은 옛 계수를 쓰고 표시합니다.

## R52. 제안·바뀜 기록·그때 그대로 다시

파일을 바로 고치는 대신 제안으로 남기면 바꿀 내용·까닭·미리 계산한 기록을 먼저 봅니다(K6). 정의 파일이 바뀔 때마다 바뀜 기록에 전후가 남고
(명령 밖의 고침은 '바깥'), HS 기록은 그때의 조립 명세로 언제든 그대로 다시 풉니다.

```python
pr = p.propose(title="소비에 시차 하나 더", why="est:cons_c1의 LM 검정이 경계선(p=0.046)",
               parts={"demand:CN": "CN c Y CN(-1) CN(-2)"})   # 파일은 그대로 — equion propose new --part …
print(pr.diff())
p.apply_proposal(pr.name)                                     # equion propose apply p1
for c in p.history.list():
    print(c.text())
rp = p.replay("hs:before")                                    # 파일이 바뀐 뒤에도 그때 그대로 — equion hs --replay hs:before
print(rp.meta["replay"]["of"], "같은 결과" if rp.meta["replay"]["same"] else "다름")
```
<!-- out -->
```text
[demo_prj] 열기 series.csv — 분기(Quarterly) 1970Q1~2019Q4 · 시리즈 13
--- a/EQUATIONS/demand.txt
+++ b/EQUATIONS/demand.txt
@@ -1,4 +1,4 @@
 # 수요 블록 — 한 줄에 한 식, '#' 뒤는 설명(문법: docs/explain/equations.md)
-CN c Y CN(-1)            # 소비
+CN c Y CN(-1) CN(-2)     # 소비
 I c Y(-1) R              # 투자
 Y = CN + I + G           # 국민소득(항등식)

--- a/EQUATIONS/adopted.toml
+++ b/EQUATIONS/adopted.toml
@@ -1,2 +1 @@
 # 채택표 — 식(부품)마다 채택한 추정 기록. 모형은 이 계수로 푼다(equion adopt가 고친다)
-"demand:CN" = "est:cons_c1"

[h0001] 2026-11-09T09:51:18 · Python · data use d2026-11a
  파일   equion.toml(고침)
  메모   자료 회차 d2026-11a
[h0002] 2026-11-09T09:51:19 · Python · adopt est:cons_c1
  파일   EQUATIONS/adopted.toml(새로)
  메모   demand:CN ← est:cons_c1
[h0003] 2026-11-09T09:51:19 · Python · propose apply p1
  파일   EQUATIONS/adopted.toml(고침) · EQUATIONS/demand.txt(고침)
  메모   제안 prop:p1 적용: 소비에 시차 하나 더
[demo_prj_replay] 열기 series.csv — 분기(Quarterly) 1970Q1~2019Q4 · 시리즈 13
[replay] baseline(_0) dynamic 2005Q1~2019Q4: 정상 60 · 일부식 제외 0 · 실패대체 0 · 실패 0
hs:before 같은 결과
```

## R65. 이정표와 묶어 보내기 — 확정한 때를 남기고, 다른 PC로 옮기기

전망을 확정한 때처럼 중요한 때에 이정표를 만들어 두면(정의 파일 사본 · 자료 회차 · 고정한 기록), 나중에 지금과 견주고 정의를 그때로 되돌릴 수
있습니다. 다른 PC로 옮길 때는 묶어 보내기(zip) — 정의 · 노트 · 보고서 · 지금 자료 회차 · 남길 기록이 들고, 원자료는 고를 때만 넣습니다.

```python
p = eqn.Project.create("ms_prj", force=True)
print(p.milestone_make("fc_2026_11", note="11월 전망 확정").text())
with open("ms_prj/EQUATIONS/price.txt", "a", encoding="utf-8") as f:   # 이정표 뒤의 고침
    f.write("# 이정표 뒤에 더한 주석\n")
print(p.milestone_diff("fc_2026_11").text())
print(p.milestone_restore("fc_2026_11") is not None, p.milestone_diff("fc_2026_11").same)
b = p.bundle()
print(b.text())
q = eqn.Project.from_bundle("ms_prj/" + b.path, "ms_copy")             # 다른 PC에서 — equion bundle open 묶음.zip ms_copy
print(q.name, q.vintage == p.vintage, [m["name"] for m in q.milestones()])
```
<!-- out -->
```text
[ms_prj] 자료 회차 d2026-11a를 만들었습니다
[ms_prj] 지금 자료 회차: d2026-11a
[milestone] fc_2026_11 — 11월 전망 확정
  만든 때 2026-11-12T13:27:22 · python
  자료 회차 d2026-11a · 정의 파일 11 · 고정한 기록 0
  폴더   work/milestones/fc_2026_11
[milestone show] fc_2026_11 와 지금 — 바뀐 파일 1
  고침  EQUATIONS/price.txt  +1 −0
  되돌리기  equion milestone restore fc_2026_11
True True
[bundle make] exports/ms_prj_2026-11-12.zip — 파일 32 · 34KB
  자료 회차 d2026-11a · 기록 0 · 원자료 넣지 않음
  뺀 것   원자료 DATA/raw/ — 받은 쪽은 지금 자료 회차로 이어 한다(자료를 다시 만들려면 원자료를 따로 넣는다)
  뺀 것   기록 — 남길 것만(모두 0개 가운데 0개)
  뺀 것   바뀜 기록 work/history · Desk 화면 상태 — 그 PC의 것
  받은 쪽  equion bundle open 묶음.zip 폴더
ms_prj True ['fc_2026_11']
```

명령줄은 `equion milestone make · list · show · restore` · `equion bundle make [--raw] [--records keep|all|none]` · `equion bundle open 묶음.zip 폴더`.
되돌리기는 바뀜 기록 하나로 남아 그것도 되돌릴 수 있습니다. Equion Desk에서는 기록 탭의 '이정표'와 개요의 '묶어 보내기', 첫 화면의 '묶음 열기'.

관련: [R52](#r52-제안바뀜-기록그때-그대로-다시)
