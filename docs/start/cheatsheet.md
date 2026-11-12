# 치트시트

자주 쓰는 명령 한 장. 예제의 `wf`는 워크파일, `eq`는 방정식 객체, `m`은 모델 객체입니다. 자세한 것은 [API 참조](../reference/api.md).

## 자료

| 하려는 일 | 코드 |
|---|---|
| 예제 자료 열기 | `wf = eqn.datasets.load("toy_q")` (`toy_a` 연간 · `toy_m` 월간 · `klein_like`) |
| 파일 열기(주기 자동 추론) | `wf = eqn.wfopen("data.xlsx")` · `eqn.wfopen("data.csv", freq="Q")` |
| 빈 워크파일 | `wf = eqn.wfcreate("sim", "Q", "2000Q1", "2030Q4")` |
| 시리즈 읽기·쓰기 | `wf["Y"]`(pandas Series) · `wf["X"] = 값`(전체 기간) · `del wf["X"]` |
| 한 기간 값 | `wf.elem("Y", "2010Q1")` |
| 표본 | `wf.smpl("2000Q1", "2019Q4")` · `wf.smpl("@all")` · `wf.smpl()`(조회) |
| 식으로 만들기(표본 안) | `wf.genr("YD = Y - G")` · `wf.genr("T2 = @trend^2")` · 자기 시차 `wf.genr("Z = Z(-1)*1.02")` |
| 식 계산만 | `wf.eval("dlog(Y)*400")` |
| 라벨 인덱스 표 | `wf.to_pandas(["Y", "CN"], labels=True).loc["2010Q1":"2010Q4"]` |
| 설명·단위 | `wf.meta("Y", desc="국민소득", unit="조원", agg="sum")` · `wf.metadata()` |
| 기간 늘리기·채우기 | `wf.extend("2025Q4")` · `wf.fill("G", method="trend")`(`last`·`growth`) |
| 주기 변환 | `wf.convert("Y", "A")` · `pg = wf.page("mon", "M")` → `wf.convert("Y", pg, method="denton")` |
| 계절조정 | `wf.seas("CNNSA")` → `CNNSA_SA`·`CNNSA_SF` (`method="classical"`) |
| 파일 입출력 | `wf.write("out.xlsx", ["Y"])` · `wf.read("more.csv")` |
| 저장·열기 | `wf.save("work")` → `work.eqw/` · `eqn.wfopen("work.eqw")` |

## 방정식

| 하려는 일 | 코드 |
|---|---|
| 최소제곱 | `eq = wf.equation("eq_i").ls("I c Y(-1) R")` |
| 강건 표준오차 | `.ls(spec, cov="white")` · `cov="hac", lags=4` |
| 2단계 최소제곱 | `.tsls("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")` |
| 비선형 | `.ls("Y = c(1) + c(2)*X^c(3) @start 1 1 1")` |
| 비선형 2단계 최소제곱 | `.tsls("Y = c(1) + c(2)*X^c(3) @start 1 1 1 @inst Z1 Z2 X(-1)")` (NL-TSLS) |
| AR(1) 오차 · PDL | `.ls("CN c Y ar(1)")` · `.ls("CN c pdl(Y, 4, 2)")` |
| GMM · LIML · WLS | `.gmm(spec + " @inst …")` · `.liml(…)` · `.wls(spec, weights="W")` |
| 고정 계수 | `wf.equation("f").fixed("CN c Y", [10, 0.6])` |
| 결과 | `eqn.show(eq)` · `eq.coefs` · `eq.stderrs` · `eq.pvalues` · `eq.resid` · `eq.fitted` · `eq.stats` |
| 진단 | `eq.diagnostics()` · `eq.serial_lm(4)` · `eq.white()` · `eq.reset()` · `eq.chow("2000Q1")` |
| 계수 제약 | `eq.wald("c(2) = 0.5")` |
| 단위근·공적분 | `wf.adf("Y")` · `wf.kpss("Y")` · `wf.coint("RL", "R")` · `wf.johansen("log(M2) log(P) log(Y) RL")` |
| 오차수정모형 | `wf.ecm("e1", "RL", ["R"])` |

## 모델

| 하려는 일 | 코드 |
|---|---|
| 만들기 | `m = wf.model("toy").merge(eq_i, eq_cn).append("Y = CN + I + G")` · `.merge("model.txt")` |
| 구조 | `m.blocks()` · `m.endogenous` · `m.exogenous` · `m.gaps()` |
| 풀이(과거 재현) | `r = m.solve()`(표본, 동적) · `m.solve(mode="static")` · `r.summary()` · `r.status()` |
| 결과 | `wf["Y_0"]`(기준선 별칭) · `m.compare("Y")` · `r.save("hs.csv")` |
| 시나리오 | `sc = m.scenario("hi_g")` → `.override("G", wf["G"]*1.1)` · `.shock("G", 10, "2015Q1", kind="pct")` |
| 내생 고정·조정항 | `.exclude("I", "2015Q1", "2015Q4")` · `.add_factor("eq_cn", 1.0)` · `.use_residuals()` |
| 목표 추적 | `m.control("Y", "G", 목표경로, "2015Q1", "2015Q4")` |
| 전망 | `m.forecast("2020Q1", "2021Q4", exog_fill="trend")` |
| 분석 | `m.decompose("Y", "hi_g")` · `m.multipliers("G", 1.0)` · `m.stochastic(reps=200)` · `m.stability("2010Q1")` |
| 선행변수(모형 일관 기대) | `m.solve(mce=True)` · `mce_method="stacked"` |

## 시스템·VAR·VECM

| 하려는 일 | 코드 |
|---|---|
| 시스템 추정 | `s = wf.system("s"); s.append("…", "…", "@inst …"); s.sur()` · `.three_sls()` · `.fiml()` — `c(n)` 꼴의 비선형 식도 |
| 식 사이 제약 | 같은 `c(n)`을 두 식에 · `s.sur(restrict=["c(2) = c(5)"])` |
| VAR | `v = wf.var("v", ["dlog(Y)", "R"], lags=2)` → `.lag_order()` · `.granger(…)` · `.irf(8)` · `.fevd(8)` · `.forecast(4)` |
| VECM | `k = wf.vecm("k", ["RL", "R"], rank=1)` → `.alpha` · `.beta` · `.forecast(4)` |
| 모델에 넣기 | `wf.model("mv").merge(v)` (계수를 고정한 식으로) |

## 명령줄

| 하려는 일 | 명령 |
|---|---|
| 스크립트 실행 + 보고서 | `equion run script.py` → `out/<실행ID>/report.html` |
| 매개변수 · 표본 | `--set g=0.05` · `--params p.json` · `--smpl 2000Q1:2019Q4` |
| 실패를 종료 코드로 | `--fail-on fallback`(종료 코드 2) |
| 실행 없이 검사 | `equion check model.txt --data data.csv` |
| 요약 | `equion info data.csv` · `equion info out/<실행ID>` |
| 새 프로젝트 | `equion new 폴더` · 블록·모형·자료 회차가 있는 프로젝트 `equion new 폴더 --template desk` |

종료 코드: 0 성공 · 1 스크립트 오류 · 2 풀이 실패(`--fail-on`) · 3 입력 오류 · 130 중단.

## 프로젝트(명령마다 기록)

| 하려는 일 | 명령 |
|---|---|
| 조립 검사 | `equion assemble main` |
| 자료 회차 | `equion data list` · `data inbox` · `data build --use` · `data diff` · `data impact` |
| 식 추정·후보·채택 | `equion est demand:CN` · `est "식" --for demand:CN` · `compare --part demand:CN` · `adopt est:…` |
| 과거 재현 | `equion hs` · `hs --swap demand:CN=est:… --vs hs:…` · `hs --replay hs:…` |
| 전망·시나리오 | `equion sim base oil20` · `scenario define 이름 --shock POIL=+20%` · `an split "sim:… sim:…"` |
| 분석·노트·보고서 | `equion an unitroot core` · `note run notes/x.md` · `report add 보고서 sim:… --show yoy` · `report update 보고서` |
| 기록·바뀜 | `equion work list` · `work show 기록` · `history list` · `history revert h…` |
| 스크립트 | `equion run FLOWS/monthly.eqs [--dry-run]` · `run --replay run:…` · `check FLOWS/monthly.eqs` |
| 이정표·옮기기 | `equion milestone make 이름` · `bundle make` · `bundle open 묶음.zip 폴더` |
| Claude용 안내 | `equion guide` · `guide skill --install project` |

흐름은 [튜토리얼 9](../tutorial/09-project.md)와 [가이드](../guide/README.md), 화면으로는 [Equion Desk 사용설명서](../desk/README.md).
