# Equion API 참조

Equion 0.8.0의 공개 API — `docs/make_api.py`가 코드의 서명과 docstring에서 만든다(손으로 고치지 말 것). 배우는 순서는 [시작하기](../start/first-model.md)와 [튜토리얼](../tutorial/README.md), 방정식 문법은 [방정식 문법](../explain/equations.md). 예제의 `eqn`·`np`·`pd`는 `import equion as eqn`·`numpy`·`pandas`다.

*English: generated reference of the public API (signatures and docstrings, in Korean). See [README.en.md](../../README.en.md) and [docs/en](../en/README.md).*

## 목차

- [1. import equion as eqn](#1-import-equion-as-eqn)
- [2. 예제 자료 eqn.datasets](#2-예제-자료-eqndatasets)
- [3. 워크파일 Workfile](#3-워크파일-workfile)
- [4. 방정식 객체 wf.equation(…)](#4-방정식-객체-wfequation)
- [5. 모델 객체 wf.model(…)](#5-모델-객체-wfmodel)
- [6. 시나리오 객체 m.scenario(…)](#6-시나리오-객체-mscenario)
- [7. 풀이 결과 SolveResult](#7-풀이-결과-solveresult)
- [8. 시스템 객체 wf.system(…)](#8-시스템-객체-wfsystem)
- [9. VAR 객체 wf.var(…)](#9-var-객체-wfvar)
- [10. VECM 객체 wf.vecm(…)](#10-vecm-객체-wfvecm)
- [11. 오차수정모형 결과 wf.ecm(…)](#11-오차수정모형-결과-wfecm)
- [12. 안정성 결과 m.stability(…)](#12-안정성-결과-mstability)
- [13. 기여도 분해 결과 m.decompose(…)](#13-기여도-분해-결과-mdecompose)
- [14. 계절조정 결과 wf.seas(…)](#14-계절조정-결과-wfseas)
- [15. 그래프 객체 wf.graph(…)](#15-그래프-객체-wfgraph)
- [16. 표 객체 wf.table(…)](#16-표-객체-wftable)
- [17. 그래프 출력 GraphOutput](#17-그래프-출력-graphoutput)
- [18. 표 출력 TableOutput](#18-표-출력-tableoutput)
- [19. 통계 eqn.stats](#19-통계-eqnstats)
- [20. 자료 변환 equion.data.transform](#20-자료-변환-equiondatatransform)
- [21. 프로젝트 eqn.project(…)](#21-프로젝트-eqnproject)
- [22. 조립 검사 결과 p.assemble(…)](#22-조립-검사-결과-passemble)
- [23. 항등식 검사 결과 p.ident(…)](#23-항등식-검사-결과-pident)
- [24. 자료 만들기 결과 p.data_build()](#24-자료-만들기-결과-pdata_build)
- [25. 자료 회차 차이 p.data_diff(…)](#25-자료-회차-차이-pdata_diff)
- [26. 회차 영향 p.data_impact(…)](#26-회차-영향-pdata_impact)
- [27. 원자료 넣기 결과 p.data_add(…)](#27-원자료-넣기-결과-pdata_add)
- [28. 추정 기록 p.est(…)](#28-추정-기록-pest)
- [29. HS 기록 p.hs(…, record=True)](#29-hs-기록-phs-recordtrue)
- [30. 채택 결과 p.adopt(…)](#30-채택-결과-padopt)
- [31. 기록 비교 p.compare(…)](#31-기록-비교-pcompare)
- [32. 전망 기록 p.sim(…)](#32-전망-기록-psim)
- [33. 다시 추정 결과 p.reestimate(…)](#33-다시-추정-결과-preestimate)
- [34. 제안 p.propose(…)](#34-제안-ppropose)
- [35. 분석 기록 p.an(…)](#35-분석-기록-pan)
- [36. 남기기 결과 p.keep(…)](#36-남기기-결과-pkeep)
- [37. 노트 결과 p.note_run(…)](#37-노트-결과-pnote_run)
- [38. 보고서 결과 p.report_add(…)](#38-보고서-결과-preport_add)
- [39. 등록부 eqn.registry](#39-등록부-eqnregistry)
- [40. 스크립트 eqn.script](#40-스크립트-eqnscript)
- [41. 스크립트 실행 eqn.script.session(…)](#41-스크립트-실행-eqnscriptsession)
- [42. 단계 결과 StepResult](#42-단계-결과-stepresult)
- [43. 실행 결과 p.run_script(…)](#43-실행-결과-prun_script)
- [44. 미리보기 p.run_script(…, dry_run=True)](#44-미리보기-prun_script-dry_runtrue)
- [45. 스크립트 검사 p.check_script(…)](#45-스크립트-검사-pcheck_script)
- [46. 재연 결과 p.replay_run(…)](#46-재연-결과-preplay_run)
- [47. 받은 원자료 p.data_inbox()](#47-받은-원자료-pdata_inbox)
- [48. 작업 기록 저장소 p.work](#48-작업-기록-저장소-pwork)
- [49. 작업 기록 하나 p.work.get(…)](#49-작업-기록-하나-pworkget)
- [50. 바뀜 기록 p.history](#50-바뀜-기록-phistory)
- [51. 바뀜 하나 p.history.get(…)](#51-바뀜-하나-phistoryget)
- [52. 고급(엔진 수준) — 드라이버·확장용, 바뀔 수 있다](#52-고급엔진-수준--드라이버확장용-바뀔-수-있다)
- [22. 명령줄 `equion`](#22-명령줄-equion)

## 1. `import equion as eqn`

| 이름 | 서명 | 설명 |
|---|---|---|
| `print_version` | `()` | 버전 정보를 찍는다. |
| `Workfile` | `클래스(wt, name=None)` | 시계열(시리즈)·표본·객체(방정식·모델·그래프·표)를 담는 작업 단위. |
| [`wfcreate`](#eqnwfcreate) | `(name, freq, start, end)` | 빈 워크파일을 만든다(모의 실험·가정 경로 만들기). |
| [`wfopen`](#eqnwfopen) | `(path, freq=None, name=None)` | 워크파일 열기 — 데이터 파일(xlsx·csv), 저장한 워크파일(`.eqw/`, 옛 `.mmw/`), 옛 Work Table 번들(`.wt/`). |
| `show` | `(*objs)` | 출력 객체·워크파일 객체·DataFrame을 실행 환경에 맞게 보이고 스풀에 남긴다. |
| [`params`](#eqnparams) | `(**defaults)` | 스크립트 매개변수 — 기본값을 주면 명령줄 `--set 이름=값`(또는 환경변수 EQUION_PARAMS의 JSON)이 덮는다. |
| [`secret`](#eqnsecret) | `(name, default=None)` | 비밀 값(API 키 등)을 환경변수에서 읽는다 — 스크립트·명령줄·보고서에 값을 남기지 않으려고 쓴다. |
| [`verbose`](#eqnverbose) | `(level=None)` | 출력 수준: 0 조용히 · 1 요약 한 줄(기본) · 2 엔진 상세 로그까지. 인자 없이 부르면 현재 값. |
| `spool` | `(…)` | 보인 출력을 모은다. mode: 'auto'(바로 보임) · 'collect'(모으기만, CLI/앱) · 'silent'. |
| [`project`](#eqnproject) | `(path='.')` | 프로젝트 열기 — 폴더(또는 그 안의 equion.toml)를 읽어 블록·모형·자료를 이름으로 다룬다. |
| [`Project`](#eqnproject) | `클래스(config)` | Equion 프로젝트 — 블록(방정식 파일)·모형(조립)·자료를 이름으로 다룬다. 여는 법은 `eqn.project(폴더)`. |

### eqn.wfcreate

`wfcreate(name, freq, start, end)`

빈 워크파일을 만든다(모의 실험·가정 경로 만들기).

**매개변수**

- `name`: 워크파일 이름(저장할 때 기본 파일 이름)
- `freq`: 주기 'Q'(분기) · 'M'(월) · 'A'(연)
- `start, end`: 처음·끝 기간('2000Q1' · '2000M1' · '2000')

**돌려주는 것**

Workfile — 시리즈 없음, 표본은 전체 기간.  

**오류**

- `ValueError`: 시점 표기가 주기와 맞지 않거나 start > end

**예**

<!-- skip -->
```python
sim = eqn.wfcreate("sim", "Q", "2020Q1", "2021Q4")
sim["X"] = 1.0
sim.freq, len(sim.data), sim.smpl()
# ('Q', 8, ('2020Q1', '2021Q4'))
```

**관련** — wfopen · datasets.load

### eqn.wfopen

`wfopen(path, freq=None, name=None)`

워크파일 열기 — 데이터 파일(xlsx·csv), 저장한 워크파일(`.eqw/`, 옛 `.mmw/`), 옛 Work Table 번들(`.wt/`).

데이터 파일은 첫 열을 날짜(2000-01-01)나 기간 라벨(2000Q1 · 2000M3 · 2000-03 · 2000)로 읽고 주기를 추론한다.  
빠진 기간은 빈 행(NaN)으로 채우고, 같은 날짜가 두 번이면 오류다. 저장한 워크파일은 재추정 없이 그대로 돌아온다.  

**매개변수**

- `path`: 파일 또는 `.eqw` 폴더 경로
- `freq`: 주기를 직접 정할 때 'Q' · 'M' · 'A'
- `name`: 워크파일 이름(기본: 파일 이름)

**돌려주는 것**

Workfile  

**오류**

- `FileNotFoundError`: 파일이 없음 · ValueError: 날짜 열을 읽지 못하거나 주기를 추론하지 못함

**예**

<!-- skip -->
```python
wf = eqn.wfopen(eqn.datasets.path("toy_q"))
wf.freq, wf.smpl()
# ('Q', ('1970Q1', '2019Q4'))
```

**관련** — wfcreate · Workfile.save · Workfile.read

### eqn.params

`params(**defaults)`

스크립트 매개변수 — 기본값을 주면 명령줄 `--set 이름=값`(또는 환경변수 EQUION_PARAMS의 JSON)이 덮는다.

값은 기본값의 형(정수·실수·글자·참거짓)으로 바뀐다. `smpl`이라는 이름은 명령줄 `--smpl S:E`로도 덮인다.  
스크립트를 `equion run`으로 실행하면 준 값과 최종 값이 보고서 manifest.json에 남는다.  

**매개변수**

- `**defaults`: 이름=기본값

**돌려주는 것**

속성으로 읽는 객체(p.이름)  

**예**

<!-- skip -->
```python
p = eqn.params(g_up=10.0, start="1990Q1")
p.g_up, p.start
# (10.0, '1990Q1')
```

**관련** — 명령줄 equion run --set · secret

### eqn.secret

`secret(name, default=None)`

비밀 값(API 키 등)을 환경변수에서 읽는다 — 스크립트·명령줄·보고서에 값을 남기지 않으려고 쓴다.

읽은 값은 이 프로세스의 명령줄 보고서(manifest.json·report.html·run.log)에서 '***'로 가려진다.  

**매개변수**

- `name`: 환경변수 이름
- `default`: 없을 때 쓸 값(None이면 오류)

**오류**

- `ValueError`: 환경변수가 없고 default도 없음

**예**

<!-- skip -->
```python
import os
os.environ["EQUION_DOC_KEY"] = "abc123"
eqn.secret("EQUION_DOC_KEY")
# 'abc123'
eqn.secret("EQUION_NO_SUCH_KEY", default="")
# ''
```

**관련** — params

### eqn.verbose

`verbose(level=None)`

출력 수준: 0 조용히 · 1 요약 한 줄(기본) · 2 엔진 상세 로그까지. 인자 없이 부르면 현재 값.

**예**

<!-- skip -->
```python
old = eqn.verbose()
eqn.verbose(0)
# 0
eqn.verbose(old) == old
# True
```

**관련** — log.use_own_handler(파이썬 logging 설정을 쓸 때)

### eqn.project

`project(path='.')`

프로젝트 열기 — 폴더(또는 그 안의 equion.toml)를 읽어 블록·모형·자료를 이름으로 다룬다.

프로젝트는 폴더 하나다: `equion.toml`(자료 파일·블록·모형 조립) + 자료 파일 + 블록 파일(방정식 파일). 예제 프로젝트는  
`eqn.Project.create(폴더)` 또는 명령줄 `equion new 폴더 --template desk`.  

**매개변수**

- `path`: 프로젝트 폴더 또는 equion.toml 경로(기본: 지금 폴더)

**돌려주는 것**

Project — .assemble · .model · .hs · .ident · .parts · .used_by  

**오류**

- `ProjectError`: 설정 파일이 없음·문법 오류·없는 파일·잘못된 이름(문제를 모두 모아서)

**예**

<!-- skip -->
```python
import tempfile, os
d = os.path.join(tempfile.mkdtemp(), "demo")
_ = eqn.Project.create(d)
p = eqn.project(d)
p.models
# ['core', 'main', 'main_fixrl']
```

**관련** — Project · docs/reference/formats.md

### eqn.Project

`Project(config)`

Equion 프로젝트 — 블록(방정식 파일)·모형(조립)·자료를 이름으로 다룬다. 여는 법은 `eqn.project(폴더)`.

**예**

<!-- skip -->
```python
import tempfile, os
p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
p.blocks, p.models
# (['demand', 'price', 'finance'], ['core', 'main', 'main_fixrl'])
```

**관련** — eqn.project · Project.assemble · Project.hs

## 2. 예제 자료 `eqn.datasets`

| 이름 | 서명 | 설명 |
|---|---|---|
| [`names`](#eqndatasetsnames) | `()` | 들어 있는 예제 자료 이름. |
| [`path`](#eqndatasetspath) | `(name)` | 예제 자료 CSV 파일의 경로 — 파일로 직접 열거나 내용을 볼 때. |
| [`describe`](#eqndatasetsdescribe) | `(name)` | 예제 자료의 참 모형과 변수 설명(글). |
| [`load`](#eqndatasetsload) | `(name='toy_q')` | 예제 자료를 워크파일로 연다(시리즈 설명·단위·집계 방식 메타데이터 포함). |
| [`klein`](#eqndatasetsklein) | `(file_path)` | 직접 구한 실제 Klein 모형 I 자료(1920~1941, Klein 1950 · Greene 『Econometric Analysis』 부록 표 등)를 연다. |

### eqn.datasets.names

`names()`

들어 있는 예제 자료 이름.

**예**

<!-- skip -->
```python
eqn.datasets.names()
# ['klein_like', 'toy_a', 'toy_m', 'toy_q']
```

### eqn.datasets.path

`path(name)`

예제 자료 CSV 파일의 경로 — 파일로 직접 열거나 내용을 볼 때.

**예**

<!-- skip -->
```python
p = eqn.datasets.path("toy_q")
p.endswith("toy_q.csv")
# True
eqn.wfopen(p).freq
# 'Q'
```

**오류**

- `KeyError`: 없는 이름

### eqn.datasets.describe

`describe(name)`

예제 자료의 참 모형과 변수 설명(글).

**예**

<!-- skip -->
```python
text = eqn.datasets.describe("toy_q")
print(text.splitlines()[0])
# 작은 거시 모형 — 분기(1970Q1~2019Q4, 200기)
"Y  = CN + I + G" in text
# True
```

### eqn.datasets.load

`load(name='toy_q')`

예제 자료를 워크파일로 연다(시리즈 설명·단위·집계 방식 메타데이터 포함).

**매개변수**

- `name`: 'toy_q'(분기 거시 모형) · 'toy_a'(같은 경제의 연간) · 'toy_m'(월간 지표) · 'klein_like'(Klein 구조 가상 자료)
**돌려주는 것**

Workfile — 이름은 자료 이름.  
**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
wf.freq, wf.smpl()
# ('Q', ('1970Q1', '2019Q4'))
```

### eqn.datasets.klein

`klein(file_path)`

직접 구한 실제 Klein 모형 I 자료(1920~1941, Klein 1950 · Greene 『Econometric Analysis』 부록 표 등)를 연다.

열 이름을 Equion 이름으로 바꾼다: C → CONS(이름 C는 상수항), P → PR, Wp → WP, I, K1(전년 말 자본), X, Wg → WG, G, T.  
추세 A = 연도 − 1931을 더한다. 첫 열은 연도여야 한다. 이 자료는 이용 조건이 분명하지 않아 패키지에 넣지 않았다.  

**예**

<!-- skip -->
```python
wf = eqn.datasets.klein("TableF10-3.csv")
```

## 3. 워크파일 `Workfile`

| 이름 | 서명 | 설명 |
|---|---|---|
| `freq` | `속성` | 주기 코드: 'Q'(분기) · 'M'(월) · 'A'(연). |
| `data` | `속성` | 전체 시리즈 DataFrame(읽기 용도 — 바꿀 때는 wf['X'] = … 또는 genr). |
| `index` | `속성` | 기간 첫날의 날짜 인덱스(pandas DatetimeIndex, freq 없음). |
| [`smpl`](#workfilesmpl) | `(start=None, end=None)` | 표본 설정·조회 — 추정(ls 등)·풀이(solve)·genr·그래프의 기본 구간. |
| [`series`](#workfileseries) | `(pattern='*')` | 시리즈 이름 목록 — 와일드카드(`*` `?` `[…]`, 대소문자 무시)로 고를 수 있다. |
| [`delete`](#workfiledelete) | `(*names)` | 시리즈 또는 객체를 지운다(이름 여러 개). |
| [`meta`](#workfilemeta) | `(name, **fields)` | 시리즈 메타데이터 읽기·쓰기 — 설명·단위·출처·집계 방식 등. 워크파일과 함께 저장된다. |
| [`metadata`](#workfilemetadata) | `(pattern='*')` | 시리즈 목록과 메타데이터·관측 구간 표(.data는 DataFrame). pattern으로 고를 수 있다. |
| `page` | `(name, freq=None, start=None, end=None)` | 다른 주기의 페이지(없으면 만든다 — freq 필요). 기간은 이 워크파일 전체를 덮는 범위(또는 start·end). 페이지는 워크파일과 함께 저장되고, `wf.convert(…, to=페이지)`로 시리즈를 옮긴다. |
| `pages` | `속성` | 이 워크파일에 딸린 다른 주기의 페이지 {이름: Workfile}. |
| [`convert`](#workfileconvert) | `(series, to, method=None, name=None, indicator=None, conversion=None, complete=True, start=None, end=None)` | 주기 변환 — 이 워크파일의 시리즈를 다른 주기로 바꿔 돌려주거나 페이지에 쓴다. |
| [`seas`](#workfileseas) | `(series, method='stl', model='additive', name=None, write=True, **kw)` | 계절조정 — STL(기본) 또는 고전 분해로 계절 성분을 떼어 조정 계열을 만든다. |
| [`genr`](#workfilegenr) | `(expr, func=None, smpl=True)` | 시리즈 만들기·고치기 — **표본 안만** 계산해 쓴다(표본 밖 값은 그대로). |
| [`eval`](#workfileeval) | `(expr)` | 방정식 식 문법으로 계산한 시리즈 — 워크파일에 쓰지 않는다. |
| [`adf`](#workfileadf) | `(x, trend='c', lags=None, ic='bic', maxlag=None)` | ADF 단위근 검정(표본 구간). 귀무가설: 단위근이 있다. |
| [`kpss`](#workfilekpss) | `(x, trend='c', lags='auto')` | KPSS 정상성 검정(표본 구간). 귀무가설이 '정상'이라 ADF와 반대 방향이다. p값은 표 보간(0.01~0.10). |
| [`coint`](#workfilecoint) | `(y, x, trend='c', lags=None, ic='bic', maxlag=None)` | Engle-Granger 공적분 검정 — y를 x(이름 목록 또는 공백 구분 글자)에 회귀한 잔차의 단위근 검정. |
| [`johansen`](#workfilejohansen) | `(series, det=0, lags=1)` | Johansen 공적분 순위 검정(트레이스·최대 고유값, 표본 구간). |
| [`forecast_eval`](#workfileforecast_eval) | `(actual, *forecasts, start=None, end=None)` | 예측 평가 표 — RMSE·MAE·MAPE·Theil U1·MSE 분해(편의·분산·공분산)·Theil U2(표본 구간 또는 start~end). |
| [`dm_test`](#workfiledm_test) | `(actual, f1, f2, h=1, loss='squared', start=None, end=None)` | Diebold-Mariano 검정 — 두 예측(f1·f2)의 정확도가 같은가. |
| [`ecm`](#workfileecm) | `(name, y, x, method='two-step', lags=0, const=True)` | 오차수정모형(ECM) — 공적분 관계(장기식)와 균형 오차로 돌아오는 단기식을 한 번에 추정한다. |
| [`elem`](#workfileelem) | `(name, period)` | 한 기간의 값 — `wf.elem("Y", "2010Q1")`(기간 라벨 또는 정수 위치). |
| [`to_pandas`](#workfileto_pandas) | `(names=None, smpl=False, labels=False)` | 시리즈들을 DataFrame으로(복사본). smpl=True면 표본 구간만, labels=True면 인덱스를 기간 라벨('2019Q4')로. |
| [`read`](#workfileread) | `(path, names=None)` | 파일(xlsx·csv)의 시리즈를 이 워크파일로 가져온다. |
| [`write`](#workfilewrite) | `(path, names=None, smpl=True)` | 시리즈를 xlsx·csv로 내보낸다(기본: 표본 구간). 없는 폴더는 만든다. |
| [`extend`](#workfileextend) | `(end)` | 기간을 end까지 늘린다(새 기간은 빈 칸, @trend·계절 더미·@d 등 지시자 열은 저절로 이어진다). 줄이지는 않는다. |
| [`fill`](#workfilefill) | `(names, method='last', window=None, start=None, end=None)` | 마지막 관측 다음의 빈 칸을 규칙으로 채운다 — 전망의 외생 가정 초안. |
| [`obj`](#workfileobj) | `(name)` | 이름으로 객체(방정식·모델·시스템·VAR·그래프·표 …)를 찾는다(대소문자 무시). |
| [`equation`](#workfileequation) | `(name)` | 방정식 객체(없으면 만든다) — 이어서 .ls · .tsls · .nls · .gmm · .liml · .wls · .fixed로 추정한다. |
| [`system`](#workfilesystem) | `(name)` | 시스템 객체(없으면 만든다) — 여러 식을 함께 추정: .append(식…) → .ols · .sur · .tsls · .three_sls · .fiml. |
| [`var`](#workfilevar) | `(name, series, lags=1, trend='c')` | VAR(p)을 추정한 객체를 만든다(같은 이름이 있으면 바꾼다 — 추정이 실패하면 이전 객체를 그대로 둔다). |
| [`vecm`](#workfilevecm) | `(name, series, lags_diff=1, rank=1, deterministic='ci')` | VECM(Johansen 최우)을 추정한 객체를 만든다(추정이 실패하면 이전 객체를 그대로 둔다). |
| [`model`](#workfilemodel) | `(name)` | 모델 객체(없으면 만든다) — 이어서 .merge(추정식) · .append(항등식) · .solve(). |
| `graph` | `(name, series, kind='line', title=None, start=None, end=None)` | 그래프 객체. series: 이름 목록 또는 공백 구분 문자열(와일드카드 가능). |
| `table` | `(name, data, title=None)` | 표 객체(DataFrame·출력 객체·방정식 등). |
| [`objects`](#workfileobjects) | `()` | 워크파일 객체 목록 표(종류·이름·요약, 시리즈 수 포함). |
| `show` | `()` | 워크파일 요약(시리즈·객체 목록)을 보인다. |
| [`save`](#workfilesave) | `(path=None)` | 워크파일을 `이름.eqw/` 폴더로 저장한다 — 시리즈·표본·메타데이터·페이지와 방정식(계수·잔차)·모델·시나리오· 시스템·VAR·VECM·그래프·표. 다시 열면 재추정 없이 그대로 돌아온다. |
| [`load`](#workfileload) | `(path)` | 저장한 워크파일(.eqw 폴더)을 연다 — 보통은 `eqn.wfopen(path)`를 쓴다. |

### Workfile.smpl

`smpl(start=None, end=None)`

표본 설정·조회 — 추정(ls 등)·풀이(solve)·genr·그래프의 기본 구간.

`wf.smpl("2000Q1", "2019Q4")` · `wf.smpl("2000Q1 2019Q4")` · `wf.smpl("@all")` · `wf.smpl("@first", "2010Q4")` ·  
`wf.smpl("1990Q1", "@last")`. 인자 없이 부르면 (시작, 끝) 라벨을, 설정하면 워크파일을 돌려준다.  

**오류**

- `ValueError`: 시점 표기가 주기와 맞지 않음(연간에 '2000Q1' 등) · 시작이 끝보다 뒤

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
wf.smpl("2000Q1", "2019Q4")                  # 설정하면 워크파일을 돌려준다(이어 부르기)
# <워크파일 toy_q: ... smpl 2000Q1~2019Q4>
wf.smpl()
# ('2000Q1', '2019Q4')
wf.smpl("@all").smpl()
# ('1970Q1', '2019Q4')
```

### Workfile.series

`series(pattern='*')`

시리즈 이름 목록 — 와일드카드(`*` `?` `[…]`, 대소문자 무시)로 고를 수 있다.

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
wf.series("C*")
# ['CN', 'CNNSA']
len(wf.series())
# 10
```

### Workfile.delete

`delete(*names)`

시리즈 또는 객체를 지운다(이름 여러 개).

**오류**

- `KeyError`: 그런 시리즈나 객체가 없음

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
wf["TMP"] = 1.0
_ = wf.delete("TMP")
"TMP" in wf
# False
```

### Workfile.meta

`meta(name, **fields)`

시리즈 메타데이터 읽기·쓰기 — 설명·단위·출처·집계 방식 등. 워크파일과 함께 저장된다.

`agg`(mean·sum·first·last·max·min)는 낮은 주기로 바꿀 때(convert) 기본 집계다. 값을 None으로 주면 그 항목을 지운다.  

**매개변수**

- `name`: 시리즈 이름
- `**fields`: desc · unit · source · agg · notes 등

**돌려주는 것**

그 시리즈의 메타데이터 dict  

**오류**

- `KeyError`: 없는 시리즈 · ValueError: agg 값이 틀림

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
wf.meta("Y")["agg"]
# 'sum'
wf.meta("R", notes="정책금리 — 분기 평균")["notes"]
# '정책금리 — 분기 평균'
```

### Workfile.metadata

`metadata(pattern='*')`

시리즈 목록과 메타데이터·관측 구간 표(.data는 DataFrame). pattern으로 고를 수 있다.

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
t = wf.metadata("R*")
list(t.data.index)
# ['R', 'RL']
t.data.loc["RL", "처음"]
# '1980Q1'
```

### Workfile.convert

`convert(series, to, method=None, name=None, indicator=None, conversion=None, complete=True, start=None, end=None)`

주기 변환 — 이 워크파일의 시리즈를 다른 주기로 바꿔 돌려주거나 페이지에 쓴다.

높은 → 낮은 주기(예: 분기 → 연): method는 mean·sum·first·last·max·min(기본은 메타데이터 agg, 없으면 mean).  
complete=True면 하위 기간이 하나라도 비면 그 기간은 결측(부분 연도 방지).  
낮은 → 높은 주기(예: 분기 → 월): constant(반복, 기본)·split(합을 나눔)·linear·denton·chow-lin.  
denton·chow-lin은 낮은 주기 값(conversion: sum·average·first·last — 기본은 agg가 sum이면 sum, 아니면 average)을  
정확히 지키면서 indicator(대상 페이지의 높은 주기 시리즈 이름 또는 Series)를 따라 나눈다(chow-lin은 지표가 필수).  
지표가 낮은 주기 끝보다 길면 그 뒤를 외삽한다.  

**매개변수**

- `series`: 시리즈 이름(또는 목록 — 그러면 {이름: 결과})
- `to`: 주기 'A'·'Q'·'M'(돌려주기만) 또는 페이지·페이지 이름(그 페이지에 쓴다)
- `name`: 페이지에 쓸 이름(기본: 같은 이름)
- `start, end`: 바꿀 원래 구간(지표가 더 짧을 때 맞춘다)

**돌려주는 것**

변환한 pandas Series(.attrs['convert']에 방법·변환 정보)  

**오류**

- `ValueError`: 방법·변환 이름이 틀림, 지표가 구간을 다 덮지 않음, 안쪽 결측

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
ya = wf.convert("Y", "A")                         # Y의 agg는 sum → 연간 합
round(float(ya.iloc[0]), 1) == round(float(wf["Y"].iloc[:4].sum()), 1)
# True
round(float(wf.convert("R", "A", method="last").iloc[0]), 3) == round(wf.elem("R", "1970Q4"), 3)
# True
```

**관련** — page · datasets.load("toy_m")(월간 지표)

### Workfile.seas

`seas(series, method='stl', model='additive', name=None, write=True, **kw)`

계절조정 — STL(기본) 또는 고전 분해로 계절 성분을 떼어 조정 계열을 만든다.

STL 옵션(seasonal·trend·low_pass·robust 등)은 **kw로. model='multiplicative'면 로그에서 분해해 되돌린다(계절 요인 = 비율).  
표본 안의 관측 구간을 쓴다. write=True면 `이름_SA`(조정 계열)와 `이름_SF`(계절 성분: 가법은 차이, 승법은 요인)를 쓴다.  

**매개변수**

- `series`: 시리즈 이름
- `method`: 'stl' · 'classical'
- `model`: 'additive' · 'multiplicative'
- `name`: 결과 시리즈 이름의 앞부분(기본: series)

**돌려주는 것**

SeasonalResult — .table(실측·계절·추세·불규칙·조정) · .output() · .graph()  

**오류**

- `ValueError`: 연간 자료, 안쪽 결측, 너무 짧은 계열, 승법인데 0 이하 값

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
r = wf.seas("CNNSA")
wf.series("CNNSA*")
# ['CNNSA', 'CNNSA_SA', 'CNNSA_SF']
abs(float(wf["CNNSA_SF"].iloc[-4:].sum())) < 3
# True
```

### Workfile.genr

`genr(expr, func=None, smpl=True)`

시리즈 만들기·고치기 — **표본 안만** 계산해 쓴다(표본 밖 값은 그대로).

식은 방정식과 같은 문법이다: 시차 `X(-1)` · `log`·`dlog`·`d` · `.yoy`·`.qoq` · `@pcy` · `@trend`·`@seas(n)`·`@d(P)`·`@step(P)`.  
자기 시차가 있는 식(`Z = Z(-1)*1.02`)은 앞에서부터 한 기씩 계산한다. 함수를 주면 `func(시리즈 DataFrame)`의 결과를 쓴다.  

**매개변수**

- `expr`: "이름 = 식" 또는 (func을 줄 때) 이름
- `func`: DataFrame → 값(배열·Series)인 Python 함수
- `smpl`: False면 표본을 무시하고 전 기간

**돌려주는 것**

만든 시리즈(pandas Series)  

**오류**

- `DSLError`: 식 문법 · ValueError: 없는 시리즈, 예약 이름(C·LOG 등)

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
_ = wf.genr("YD = Y - G")
round(wf.elem("YD", "2010Q1"), 2) == round(wf.elem("Y", "2010Q1") - wf.elem("G", "2010Q1"), 2)
# True
_ = wf.genr("T2 = @trend ^ 2")
wf.elem("T2", "1970Q3")
# 4.0
_ = wf.genr("GAP", lambda d: d.Y / d.Y.rolling(4).mean() - 1)
```

**관련** — eval · smpl

### Workfile.eval

`eval(expr)`

방정식 식 문법으로 계산한 시리즈 — 워크파일에 쓰지 않는다.

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
g = wf.eval("dlog(Y) * 400")                     # 연율 성장률(%)
int(g.notna().sum())
# 199
wf.eval("@seas(1)").iloc[:4].tolist()
# [1.0, 0.0, 0.0, 0.0]
```

**오류**

- `DSLError`: 문법 · ValueError: 없는 시리즈 · 번호 없는 @seas

**관련** — genr

### Workfile.adf

`adf(x, trend='c', lags=None, ic='bic', maxlag=None)`

ADF 단위근 검정(표본 구간). 귀무가설: 단위근이 있다.

**매개변수**

- `x`: 시리즈 이름 · 식(`"log(Y)"`) · pandas Series
- `trend`: 'n'(결정항 없음) · 'c'(상수) · 'ct'(상수 + 추세)
- `lags`: 차분 시차 수(None이면 ic로 고른다)
- `ic`: 'bic' · 'aic' · 't-stat'

**돌려주는 것**

TestResult(.statistic = ADF t, .pvalue = MacKinnon 근사 p값, .rows = 임계값)  

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
wf.adf("log(Y)", trend="ct").pvalue > 0.05        # 수준: 단위근을 기각하지 못한다
# True
wf.adf("dlog(Y)").pvalue < 0.01                   # 차분: 정상
# True
```

**관련** — kpss · coint

### Workfile.kpss

`kpss(x, trend='c', lags='auto')`

KPSS 정상성 검정(표본 구간). 귀무가설이 '정상'이라 ADF와 반대 방향이다. p값은 표 보간(0.01~0.10).

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
wf.kpss("dlog(Y)").pvalue >= 0.05
# True
```

**관련** — adf

### Workfile.coint

`coint(y, x, trend='c', lags=None, ic='bic', maxlag=None)`

Engle-Granger 공적분 검정 — y를 x(이름 목록 또는 공백 구분 글자)에 회귀한 잔차의 단위근 검정.

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
wf.coint("RL", "R").pvalue < 0.01                 # RL = 1 + R + 정상 오차
# True
```

**관련** — johansen · ecm

### Workfile.johansen

`johansen(series, det=0, lags=1)`

Johansen 공적분 순위 검정(트레이스·최대 고유값, 표본 구간).

**매개변수**

- `series`: 이름·식 목록 또는 공백 구분 글자
- `det`: −1 결정항 없음 · 0 상수 · 1 상수 + 추세
- `lags`: 차분 시차 수

**돌려주는 것**

TestResult — .table(순위별 통계량·5% 임계값), .rows(고른 순위)  

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
j = wf.johansen("RL R")
j.rows["트레이스 기준 순위(5%)"]
# 1
```

**관련** — vecm · coint

### Workfile.forecast_eval

`forecast_eval(actual, *forecasts, start=None, end=None)`

예측 평가 표 — RMSE·MAE·MAPE·Theil U1·MSE 분해(편의·분산·공분산)·Theil U2(표본 구간 또는 start~end).

예측마다 실측과 함께 관측된 기간만 쓴다.  

**매개변수**

- `actual`: 실측(시리즈 이름·식·Series)
- `*forecasts`: 예측들(이름·식·Series)

**돌려주는 것**

TableOutput(.data는 DataFrame, 행 = 예측)  

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
t = wf.forecast_eval("Y", "Y(-1)", "Y(-4)")
list(t.data.index)
# ['Y(-1)', 'Y(-4)']
bool(t.data.loc["Y(-1)", "RMSE"] < t.data.loc["Y(-4)", "RMSE"])
# True
```

**관련** — dm_test

### Workfile.dm_test

`dm_test(actual, f1, f2, h=1, loss='squared', start=None, end=None)`

Diebold-Mariano 검정 — 두 예측(f1·f2)의 정확도가 같은가.

Harvey-Leybourne-Newbold 작은 표본 보정과 t 분포를 쓴다. 통계량이 음수면 f1이 더 정확하다.  

**매개변수**

- `actual, f1, f2`: 실측과 두 예측(이름·식·Series)
- `h`: 몇 기 앞 예측인가(오차의 MA(h−1) 구조)
- `loss`: 'squared' · 'absolute'

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
r = wf.dm_test("Y", "Y(-1)", "Y(-4)")
r.statistic < 0 and r.pvalue < 0.05
# True
```

**관련** — forecast_eval

### Workfile.ecm

`ecm(name, y, x, method='two-step', lags=0, const=True)`

오차수정모형(ECM) — 공적분 관계(장기식)와 균형 오차로 돌아오는 단기식을 한 번에 추정한다.

method='two-step'(Engle-Granger): ① 장기식 `y c x…`(객체 이름 name_lr)을 OLS로, ② 단기식  
`d(y) c d(x)… EC(-1)`을 OLS로. EC(-1) = (y − a − b·x)(-1)은 장기 계수를 숫자로 넣은 식이라 연립 풀이에서도  
y·x에 따라 움직인다. 장기 잔차의 Engle-Granger 검정을 함께 보인다.  
method='nls': `d(y) = c(1)*(y(-1) − c(2) − c(3)*x(-1) …) + …`를 한 번에 NLS로 — 장기 계수의 표준오차를 바로 얻는다.  

**매개변수**

- `name`: 단기식 방정식 객체 이름(모델에 넣을 수 있다)
- `y, x`: 시리즈 이름이나 식(보통 로그 수준), x는 목록
- `lags`: 단기식에 넣을 d(y)·d(x)의 시차 수
- `const`: 장기식의 상수항

**돌려주는 것**

ECMResult — .longrun() · .adjustment(α) · .half_life · .shortrun(방정식 객체) · .output()  

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
e = wf.ecm("ecm_rl", "RL", ["R"])
bool(-0.6 < e.adjustment["계수"] < -0.1)
# True
wf.obj("ecm_rl").method
# 'ols'
```

**관련** — coint · model.merge

### Workfile.elem

`elem(name, period)`

한 기간의 값 — `wf.elem("Y", "2010Q1")`(기간 라벨 또는 정수 위치).

기간 라벨로 pandas `.loc["2010Q1"]`을 쓰지 않아도 된다(pandas 3.1부터 날짜 인덱스의 분기 문자열 해석은 사라질 예정).  

**오류**

- `KeyError`: 없는 시리즈 · ValueError: 없는 기간

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
round(wf.elem("R", "2019Q4"), 4)
# 3.1552
wf.elem("Y", 0) == float(wf["Y"].iloc[0])
# True
```

### Workfile.to_pandas

`to_pandas(names=None, smpl=False, labels=False)`

시리즈들을 DataFrame으로(복사본). smpl=True면 표본 구간만, labels=True면 인덱스를 기간 라벨('2019Q4')로.

라벨 인덱스는 기간 라벨로 자를 때 쓴다(`.loc["2010Q1":"2010Q4"]`).  

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
df = wf.to_pandas(["Y", "CN"], labels=True)
list(df.index[:2]), list(df.columns)
# (['1970Q1', '1970Q2'], ['Y', 'CN'])
len(df.loc["2010Q1":"2010Q4"])
# 4
```

### Workfile.read

`read(path, names=None)`

파일(xlsx·csv)의 시리즈를 이 워크파일로 가져온다.

파일의 날짜가 워크파일 끝보다 뒤면 기간을 늘리고, 시작보다 앞의 값은 읽지 않고 경고한다. 주기가 다른 파일은 오류다  
(그 주기의 페이지에 읽은 뒤 convert로 옮긴다). names를 주지 않으면 예약 이름(C·LOG 등) 열은 건너뛴다.  

**매개변수**

- `path`: 파일 경로
- `names`: 가져올 열(기본: 전부)

**돌려주는 것**

가져온 시리즈 이름 목록  

**예**

<!-- skip -->
```python
wf = eqn.wfcreate("w", "M", "2000M1", "2019M12")
wf.read(eqn.datasets.path("toy_m"))
# ['IP', 'CPIM', 'RM']
```

**관련** — write · wfopen · page

### Workfile.write

`write(path, names=None, smpl=True)`

시리즈를 xlsx·csv로 내보낸다(기본: 표본 구간). 없는 폴더는 만든다.

**매개변수**

- `path`: .xlsx 또는 .csv
- `names`: 내보낼 시리즈(기본: 전부)
- `smpl`: False면 전 기간

**돌려주는 것**

쓴 경로  

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
wf.write("toy_y.csv", ["Y", "CN"])
# 'toy_y.csv'
eqn.wfopen("toy_y.csv").series()
# ['Y', 'CN']
```

**관련** — read · to_pandas

### Workfile.extend

`extend(end)`

기간을 end까지 늘린다(새 기간은 빈 칸, @trend·계절 더미·@d 등 지시자 열은 저절로 이어진다). 줄이지는 않는다.

**돌려주는 것**

늘어난 기간 수(이미 그만큼 있으면 0)  

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
wf.extend("2021Q4")
# 8
wf.smpl()[1], bool(wf["Y"].iloc[-1] != wf["Y"].iloc[-1])
# ('2021Q4', True)
```

**관련** — fill · ModelObject.forecast

### Workfile.fill

`fill(names, method='last', window=None, start=None, end=None)`

마지막 관측 다음의 빈 칸을 규칙으로 채운다 — 전망의 외생 가정 초안.

**매개변수**

- `names`: 시리즈 이름(공백 구분 글자·목록·와일드카드)
- `method`: 'last'(마지막 값 유지) · 'growth'(최근 window기 평균 성장률) · 'trend'(최근 window기 평균 증분)
- `window`: 평균을 낼 기간 수(기본: 1년)
- `start, end`: 채울 구간(기본: 마지막 관측 다음 ~ 워크파일 끝)

**돌려주는 것**

{시리즈: 채운 기간 수}  

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
_ = wf.extend("2020Q4")
wf.fill("G R", method="last")
# {'G': 4, 'R': 4}
wf.elem("R", "2020Q4") == wf.elem("R", "2019Q4")
# True
```

### Workfile.obj

`obj(name)`

이름으로 객체(방정식·모델·시스템·VAR·그래프·표 …)를 찾는다(대소문자 무시).

**오류**

- `KeyError`: 그런 객체가 없음

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
_ = wf.equation("eq_i").ls("I c Y(-1) R")
wf.obj("EQ_I").kind
# 'equation'
```

### Workfile.equation

`equation(name)`

방정식 객체(없으면 만든다) — 이어서 .ls · .tsls · .nls · .gmm · .liml · .wls · .fixed로 추정한다.

이름은 시리즈 이름과 겹칠 수 없다(대소문자 무시 — 시리즈 G가 있으면 객체 이름 'g'도 안 된다).  

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
eq = wf.equation("eq_i").ls("I c Y(-1) R")
round(float(eq.coefs["R"]), 2)
# -0.96
```

**관련** — model · system

### Workfile.system

`system(name)`

시스템 객체(없으면 만든다) — 여러 식을 함께 추정: .append(식…) → .ols · .sur · .tsls · .three_sls · .fiml.

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("klein_like")
s = wf.system("kl")
_ = s.append("CONS c PR PR(-1) WP+WG", "I c PR PR(-1) K(-1)", "@inst G T WG A PR(-1) K(-1) X(-1)")
_ = s.three_sls()
len(s.coefs)
# 8
```

### Workfile.var

`var(name, series, lags=1, trend='c')`

VAR(p)을 추정한 객체를 만든다(같은 이름이 있으면 바꾼다 — 추정이 실패하면 이전 객체를 그대로 둔다).

**매개변수**

- `name`: 객체 이름
- `series`: 이름·식 목록 또는 공백 구분 글자(둘 이상, 겹치면 오류)
- `lags`: 시차(1 이상)
- `trend`: 'n' · 'c'(상수) · 'ct'(상수 + 추세)

**돌려주는 것**

VARObject — .coefs · .lag_order() · .granger() · .irf() · .fevd() · .forecast() · .stability(), model.merge(var)  

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
v = wf.var("v1", ["dlog(Y)", "R"], lags=2)
v.coefs.shape
# (5, 2)
```

### Workfile.vecm

`vecm(name, series, lags_diff=1, rank=1, deterministic='ci')`

VECM(Johansen 최우)을 추정한 객체를 만든다(추정이 실패하면 이전 객체를 그대로 둔다).

**매개변수**

- `series`: 이름·식 목록(둘 이상)
- `lags_diff`: 차분 시차 수(0 이상)
- `rank`: 공적분 순위(1 ~ 변수 수 − 1 — wf.johansen으로 정한다)
- `deterministic`: 'n' 또는 co·ci·lo·li 조합(관계 밖·안의 상수·선형추세, 예: 'ci' · 'colo' · 'ci lo')

**돌려주는 것**

VECMObject — .alpha · .beta · .gamma · .forecast(), model.merge(vecm)  

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
_ = wf.smpl("1980Q1", "2019Q4")              # RL이 있는 구간
k = wf.vecm("k1", ["RL", "R"], rank=1)
round(float(k.beta.loc["R", "EC1"]), 1)
# -1.0
```

### Workfile.model

`model(name)`

모델 객체(없으면 만든다) — 이어서 .merge(추정식) · .append(항등식) · .solve().

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
eq = wf.equation("eq_i").ls("I c Y(-1) R")
m = wf.model("toy").merge(eq, "CN c Y CN(-1)").append("Y = CN + I + G")
m.endogenous
# ['CN', 'I', 'Y']
```

### Workfile.objects

`objects()`

워크파일 객체 목록 표(종류·이름·요약, 시리즈 수 포함).

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
_ = wf.equation("eq_i").ls("I c Y(-1) R")
t = wf.objects()
"eq_i" in t.text()
# True
```

### Workfile.save

`save(path=None)`

워크파일을 `이름.eqw/` 폴더로 저장한다 — 시리즈·표본·메타데이터·페이지와 방정식(계수·잔차)·모델·시나리오· 시스템·VAR·VECM·그래프·표. 다시 열면 재추정 없이 그대로 돌아온다.

**매개변수**

- `path`: 폴더 경로(.eqw는 붙여 준다, 기본: 워크파일 이름)

**돌려주는 것**

저장한 폴더 경로  

**오류**

- `ValueError`: 경로가 이미 파일임

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
_ = wf.equation("eq_i").ls("I c Y(-1) R")
wf.save("doc_save")
# 'doc_save.eqw'
eqn.wfopen("doc_save.eqw").obj("eq_i").coefs.round(2).tolist()
# [4.48, 0.15, -0.96]
```

**관련** — wfopen

### Workfile.load

`load(path)`

저장한 워크파일(.eqw 폴더)을 연다 — 보통은 `eqn.wfopen(path)`를 쓴다.

복원하지 못한 객체(망가진 정의 등)는 건너뛰고 경고한다.  

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
p = wf.save("doc_load")
eqn.Workfile.load(p).name
# 'toy_q'
```

**관련** — wfopen · save

## 4. 방정식 객체 `wf.equation(…)`

| 이름 | 서명 | 설명 |
|---|---|---|
| [`ls`](#equationobjectls) | `(spec, cov=None, lags=None)` | 최소제곱(OLS) 추정. 식이 계수 `c(n)` 꼴이면 비선형(NLS), 식 끝에 `@coef`가 있으면 고정 계수로 처리한다. |
| [`tsls`](#equationobjecttsls) | `(spec, inst=None, cov=None, lags=None)` | 2단계 최소제곱(TSLS) — 내생 설명변수가 있을 때. |
| [`wls`](#equationobjectwls) | `(spec, weights, wtype='ivar', cov=None, lags=None)` | 가중 최소제곱(WLS) — 관측마다 오차 분산이 다를 때. |
| [`gmm`](#equationobjectgmm) | `(spec, inst=None, weight='white', lags=None, iterate=False)` | 선형 GMM(도구변수) — 이분산·자기상관에 강건한 가중. |
| [`liml`](#equationobjectliml) | `(spec, inst=None, cov=None, lags=None)` | 제한정보 최우(LIML, k-class) — 약한 도구에 TSLS보다 덜 치우친다. κ는 stats['liml_kappa']. |
| [`nls`](#equationobjectnls) | `(spec, start=None, cov=None, lags=None)` | 비선형 최소제곱(NLS) — 식은 `Y = c(1) + c(2)*X^c(3)` 꼴. 기울기는 식을 미분해 정확히 계산한다. |
| [`set_cov`](#equationobjectset_cov) | `(cov=None, lags=None)` | 계수 공분산만 바꿔 다시 계산한다(계수는 그대로). cov=None이면 보통 공분산. |
| [`fixed`](#equationobjectfixed) | `(spec, coefs)` | 다른 곳(다른 프로그램·Python 추정 등)에서 얻은 계수를 고정해 넣는다 — 모델에서 추정식처럼 쓰인다. |
| [`serial_lm`](#equationobjectserial_lm) | `(lags=2)` | 계열상관 LM 검정(Breusch-Godfrey). 귀무가설: 시차 lags까지 잔차에 계열상관이 없다. OLS·WLS 식. |
| [`ljungbox`](#equationobjectljungbox) | `(lags=None)` | Ljung-Box Q 검정(잔차 자기상관). 결과의 .table에 시차별 자기상관·Q·p값. 모든 추정법. |
| [`white`](#equationobjectwhite) | `(cross=True)` | White 이분산 검정 — 잔차²를 회귀변수·제곱(cross=True면 교차곱까지)에 회귀. 귀무가설: 동분산. |
| [`breusch_pagan`](#equationobjectbreusch_pagan) | `()` | Breusch-Pagan-Godfrey 이분산 검정. 귀무가설: 동분산. |
| [`arch`](#equationobjectarch) | `(lags=1)` | ARCH LM 검정 — 잔차 분산의 자기상관. 모든 추정법. |
| [`normality`](#equationobjectnormality) | `()` | Jarque-Bera 잔차 정규성 검정. 모든 추정법. |
| [`reset`](#equationobjectreset) | `(terms=1)` | Ramsey RESET — 적합값의 2~(terms+1)제곱을 더하면 나아지는가(함수 형태 검정). |
| [`omitted`](#equationobjectomitted) | `(*terms)` | 누락 변수 검정 — 항들을 더하면 설명력이 유의하게 느는가(F·LR). 두 식을 공통 표본에서 다시 추정한다. |
| [`redundant`](#equationobjectredundant) | `(*terms)` | 불필요 변수 검정 — 식의 항들을 빼도 되는가(계수가 함께 0). 이름은 식에 쓴 그대로(상수항은 'c'). |
| [`lag_distribution`](#equationobjectlag_distribution) | `(which=0)` | pdl(...) 항의 시차별 계수(β₀…β_k)·표준오차와 합계 표. which = 식 안의 몇 번째 pdl 항인지(0부터). |
| [`wald`](#equationobjectwald) | `(*restrictions)` | Wald 계수 제약 검정 — `eq.wald("c(2) + c(3) = 1", "c(4) = 0")`. c(n)은 식에 쓴 항 순서(상수항 c가 c(1)). |
| [`chow`](#equationobjectchow) | `(period)` | Chow 구조변화 검정 — period(예: '1995Q1')부터를 뒤 구간으로 놓고 두 구간의 계수가 같은지. |
| [`cusum`](#equationobjectcusum) | `(alpha=0.95)` | CUSUM 안정성 검정 — 재귀 잔차의 누적합이 경계를 벗어나는가. |
| [`recursive`](#equationobjectrecursive) | `()` | 재귀 계수 — 처음 k개 관측치로 시작해 한 기씩 늘려 추정한 계수(날짜 × 계수 DataFrame). 계수가 시간에 따라 안정한지 본다. |
| [`diagnostics`](#equationobjectdiagnostics) | `(lags=2)` | 표준 진단 한 표 — 계열상관 LM·White·Breusch-Pagan·Ljung-Box·ARCH·Jarque-Bera·RESET. |
| `method` | `속성` | 추정법: 'ols' · 'wls' · 'tsls' · 'gmm' · 'liml' · 'nls' · 'fixed'. |
| `dependent` | `속성` | 종속변수 표기(좌변 그대로, 예: 'dlog(P)'). |
| `target` | `속성` | 이 식이 결정하는 변수(목표변수) — 좌변의 첫 변수(예: 'dlog(P)'의 'P'). 모델의 내생변수가 된다. |
| `coefs` | `속성` | 계수(pandas Series, 이름 = 항 — 상수항은 'const'). |
| `stderrs` | `속성` | 계수 표준오차(Series). 공분산은 추정 때 고른 것(cov). |
| `tstats` | `속성` | 계수의 t값(Series). |
| `pvalues` | `속성` | 계수 = 0 검정의 p값(Series, t 분포). |
| `stats` | `속성` | 통계 사전 — r_squared · adj_r_squared · se_regression · durbin_watson · log_likelihood · aic · bic · f_statistic · n_obs 등(추정법별 항목 추가: j_statistic · liml_kappa · collinear …). 항목 설명은 docs/reference/outputs.md. |
| `resid` | `속성` | 잔차(표본 기간 Series) = 실측 − 적합값. |
| `actual` | `속성` | 종속변수(좌변 식 그대로, 예: log(RCPSA))의 전 기간 값. |
| `fitted` | `속성` | 적합값(표본 기간 Series). |
| `results` | `속성` | 추정 결과 객체(equion.stats.Results) — params·bse·tvalues·pvalues·resid·cov_params()·set_cov(). |
| `nobs` | `속성` | 추정에 쓴 관측치 수. |
| `output` | `()` | 결과표(TableOutput — .text() · .html() · .data). `eqn.show(eq)`가 보이는 것과 같다. |
| `show` | `()` | 결과표를 보인다(`eqn.show(eq)`와 같다). |
| [`forecast`](#equationobjectforecast) | `(name=None, start=None, end=None, mode='dynamic')` | 이 식 하나만 풀어 목표변수를 예측한다(다른 변수는 실측·워크파일 값). 결과는 시리즈로 워크파일에 쓴다. |

### EquationObject.ls

`ls(spec, cov=None, lags=None)`

최소제곱(OLS) 추정. 식이 계수 `c(n)` 꼴이면 비선형(NLS), 식 끝에 `@coef`가 있으면 고정 계수로 처리한다.

표본은 워크파일 smpl(또는 식 끝 `@smpl`) 안의 결측 없는 기간이다. 식 문법은 docs/explain/equations.md.  

**매개변수**

- `spec`: 추정식 — 첫 항이 종속변수, c는 상수항(예: "I c Y(-1) R", "log(CN) c log(Y) @seas")
- `cov`: 계수 공분산 — None(보통) · 'white'(= 'hc1') · 'hc0'~'hc3' · 'hac'(Newey-West)
- `lags`: hac의 시차(기본 ⌊4(n/100)^(2/9)⌋)

**돌려주는 것**

이 방정식 객체(이어 부르기 — .coefs · .stats · eqn.show(eq))  

**오류**

- `DSLError`: 문법·없는 함수 · ValueError: 없는 변수, 관측치가 계수보다 적음, 예약 이름 변수

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
eq = wf.equation("eq_i").ls("I c Y(-1) R")
eq.coefs.round(3).to_dict()
# {'const': 4.481, 'Y(-1)': 0.151, 'R': -0.963}
eq.nobs, round(eq.stats["r_squared"], 4)
# (199, 0.9985)
```

**관련** — tsls · nls · fixed · set_cov

### EquationObject.tsls

`tsls(spec, inst=None, cov=None, lags=None)`

2단계 최소제곱(TSLS) — 내생 설명변수가 있을 때.

도구변수는 inst=[…]나 식 끝의 `@inst …`로 준다. 상수항은 도구에 저절로 들어가고, 식 안의 외생 설명변수도 도구에 넣는다.  

**매개변수**

- `spec`: 추정식
- `inst`: 도구변수(이름·식 목록 또는 공백 구분 글자)
- `cov, lags`: ls와 같다

**오류**

- `ValueError`: 도구가 계수보다 적음(식별 불가)

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
eq = wf.equation("eq_cn").tsls("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
eq.coefs.round(3).to_dict()
# {'const': 10.651, 'Y': 0.531, 'CN(-1)': 0.256}
```

**관련** — gmm · liml · ls

### EquationObject.wls

`wls(spec, weights, wtype='ivar', cov=None, lags=None)`

가중 최소제곱(WLS) — 관측마다 오차 분산이 다를 때.

weights는 계열 이름이나 식(예: "1/POP", "@trend"), wtype은 그 계열의 뜻: 'ivar'(1/분산, 기본) · 'var'(분산) ·  
'istdev'(1/표준편차) · 'stdev'(표준편차). R²·SSR·DW는 가중 잔차로, 가중 전 값은 stats의 unweighted_*로.  
연립 풀이에서는 OLS 식과 똑같이 쓰인다.  

**오류**

- `TypeError`: weights가 배열 — 먼저 시리즈로(wf['W'] = 값) · ValueError: 0 이하 가중치

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
_ = wf.genr("WT = 1 / Y")
eq = wf.equation("eq_w").wls("I c Y(-1) R", weights="WT")
eq.method, round(float(eq.coefs["R"]), 2)
# ('wls', -0.97)
```

### EquationObject.gmm

`gmm(spec, inst=None, weight='white', lags=None, iterate=False)`

선형 GMM(도구변수) — 이분산·자기상관에 강건한 가중.

1단계 TSLS 잔차로 가중행렬을 만들어 다시 추정하고(2단계), iterate=True면 수렴할 때까지 반복한다. 과대식별이면  
Hansen J 검정(stats['j_statistic'] · ['j_pvalue'])을 함께 낸다.  

**매개변수**

- `inst`: 도구변수(tsls와 같이)
- `weight`: 'white'(이분산 강건) · 'hac'(Bartlett, lags)

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
eq = wf.equation("eq_gmm").gmm("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
round(float(eq.coefs["Y"]), 2), round(eq.stats["j_pvalue"], 2)
# (0.53, 0.1)
```

### EquationObject.liml

`liml(spec, inst=None, cov=None, lags=None)`

제한정보 최우(LIML, k-class) — 약한 도구에 TSLS보다 덜 치우친다. κ는 stats['liml_kappa'].

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
eq = wf.equation("eq_liml").liml("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
round(float(eq.coefs["Y"]), 2), round(eq.stats["liml_kappa"], 3)
# (0.53, 1.023)
```

### EquationObject.nls

`nls(spec, start=None, cov=None, lags=None)`

비선형 최소제곱(NLS) — 식은 `Y = c(1) + c(2)*X^c(3)` 꼴. 기울기는 식을 미분해 정확히 계산한다.

시작값은 start=[…] 또는 식 끝 `@start …`(없으면 0). cov·lags는 ls와 같다.  

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
eq = wf.equation("eq_nls").nls("CN = c(1) + c(2)*Y^c(3)", start=[10, 0.5, 1])
eq.coefs.round(2).to_dict()
# {'c(1)': 11.31, 'c(2)': 0.76, 'c(3)': 0.99}
```

### EquationObject.set_cov

`set_cov(cov=None, lags=None)`

계수 공분산만 바꿔 다시 계산한다(계수는 그대로). cov=None이면 보통 공분산.

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
eq = wf.equation("eq_i").ls("I c Y(-1) R")
before = eq.stderrs.round(4).tolist()
_ = eq.set_cov("hac", lags=4)
eq.stderrs.round(4).tolist() != before
# True
```

### EquationObject.fixed

`fixed(spec, coefs)`

다른 곳(다른 프로그램·Python 추정 등)에서 얻은 계수를 고정해 넣는다 — 모델에서 추정식처럼 쓰인다.

coefs는 식에 쓴 항 순서의 목록이거나 {계수 이름: 값}(상수항 이름은 'const').  

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
eq = wf.equation("eq_fx").fixed("I c Y(-1) R", [5.0, 0.15, -1.0])
eq.method, eq.coefs.to_dict()
# ('fixed', {'const': 5.0, 'Y(-1)': 0.15, 'R': -1.0})
```

### EquationObject.serial_lm

`serial_lm(lags=2)`

계열상관 LM 검정(Breusch-Godfrey). 귀무가설: 시차 lags까지 잔차에 계열상관이 없다. OLS·WLS 식.

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
eq = wf.equation("eq_i").ls("I c Y(-1) R")
r = eq.serial_lm(4)
round(r.statistic, 3), r.reject(0.05)
# (4.215, False)
```

### EquationObject.ljungbox

`ljungbox(lags=None)`

Ljung-Box Q 검정(잔차 자기상관). 결과의 .table에 시차별 자기상관·Q·p값. 모든 추정법.

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
eq = wf.equation("eq_i").ls("I c Y(-1) R")
r = eq.ljungbox(8)
len(r.table), r.reject(0.05)
# (8, False)
```

### EquationObject.white

`white(cross=True)`

White 이분산 검정 — 잔차²를 회귀변수·제곱(cross=True면 교차곱까지)에 회귀. 귀무가설: 동분산.

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
eq = wf.equation("eq_i").ls("I c Y(-1) R")
eq.white().reject(0.05)
# False
```

### EquationObject.breusch_pagan

`breusch_pagan()`

Breusch-Pagan-Godfrey 이분산 검정. 귀무가설: 동분산.

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
eq = wf.equation("eq_i").ls("I c Y(-1) R")
eq.breusch_pagan().reject(0.05)
# False
```

### EquationObject.arch

`arch(lags=1)`

ARCH LM 검정 — 잔차 분산의 자기상관. 모든 추정법.

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
eq = wf.equation("eq_i").ls("I c Y(-1) R")
round(eq.arch(4).pvalue, 2)
# 0.22
```

### EquationObject.normality

`normality()`

Jarque-Bera 잔차 정규성 검정. 모든 추정법.

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
eq = wf.equation("eq_i").ls("I c Y(-1) R")
eq.normality().reject(0.05)
# False
```

### EquationObject.reset

`reset(terms=1)`

Ramsey RESET — 적합값의 2~(terms+1)제곱을 더하면 나아지는가(함수 형태 검정).

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
wf.equation("good").ls("I c Y(-1) R").reset(1).reject(0.05)
# False
wf.equation("bad").ls("CN c G").reset(1).reject(0.05)
# True
```

### EquationObject.omitted

`omitted(*terms)`

누락 변수 검정 — 항들을 더하면 설명력이 유의하게 느는가(F·LR). 두 식을 공통 표본에서 다시 추정한다.

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
eq = wf.equation("eq_i").ls("I c Y(-1) R")
eq.omitted("R(-1)", "G").reject(0.05)
# False
```

### EquationObject.redundant

`redundant(*terms)`

불필요 변수 검정 — 식의 항들을 빼도 되는가(계수가 함께 0). 이름은 식에 쓴 그대로(상수항은 'c').

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
eq = wf.equation("eq_i").ls("I c Y(-1) R")
eq.redundant("R").reject(0.05)
# True
```

### EquationObject.lag_distribution

`lag_distribution(which=0)`

pdl(...) 항의 시차별 계수(β₀…β_k)·표준오차와 합계 표. which = 식 안의 몇 번째 pdl 항인지(0부터).

**오류**

- `ValueError`: pdl 항이 없거나 which가 범위 밖

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
eq = wf.equation("eq_pdl").ls("I c pdl(Y, 4, 2) R")
t = eq.lag_distribution()
len(t.data), round(float(t.data["계수"].iloc[-1]), 3)
# (6, 0.151)
```

### EquationObject.wald

`wald(*restrictions)`

Wald 계수 제약 검정 — `eq.wald("c(2) + c(3) = 1", "c(4) = 0")`. c(n)은 식에 쓴 항 순서(상수항 c가 c(1)).

공분산은 추정 때 고른 것을 쓴다(강건 공분산이면 강건 Wald).  

**오류**

- `ValueError`: 문법 오류, 계수 번호 범위 밖, 서로 겹치거나 모순인 제약

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
eq = wf.equation("eq_i").ls("I c Y(-1) R")
eq.wald("c(2) = 0.15", "c(3) = -1").reject(0.05)        # 참값
# False
eq.wald("c(2) = 0.2").reject(0.05)
# True
```

### EquationObject.chow

`chow(period)`

Chow 구조변화 검정 — period(예: '1995Q1')부터를 뒤 구간으로 놓고 두 구간의 계수가 같은지.

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
eq = wf.equation("eq_i").ls("I c Y(-1) R")
eq.chow("1995Q1").reject(0.05)
# False
```

### EquationObject.cusum

`cusum(alpha=0.95)`

CUSUM 안정성 검정 — 재귀 잔차의 누적합이 경계를 벗어나는가.

통계량은 누적합이 경계에 가장 가까이 간 비율(1보다 작으면 경계 안 — 안정). 결과의 .graph는 그림, .data는 기간별 값.  

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
eq = wf.equation("eq_i").ls("I c Y(-1) R")
r = eq.cusum()
bool(r.statistic < 1)
# True
```

### EquationObject.recursive

`recursive()`

재귀 계수 — 처음 k개 관측치로 시작해 한 기씩 늘려 추정한 계수(날짜 × 계수 DataFrame). 계수가 시간에 따라 안정한지 본다.

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
eq = wf.equation("eq_i").ls("I c Y(-1) R")
rc = eq.recursive()
list(rc.columns), round(float(rc["R"].iloc[-1]), 3)
# (['const', 'Y(-1)', 'R'], -0.963)
```

### EquationObject.diagnostics

`diagnostics(lags=2)`

표준 진단 한 표 — 계열상관 LM·White·Breusch-Pagan·Ljung-Box·ARCH·Jarque-Bera·RESET.

OLS가 아니면 잔차 검정(Ljung-Box·ARCH·Jarque-Bera)만. 잔차가 사실상 0이면(완전 적합) 오류다.  

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
eq = wf.equation("eq_i").ls("I c Y(-1) R")
t = eq.diagnostics()
list(t.data.columns)
# ['통계량', 'p값', '5%에서', '귀무가설']
```

### EquationObject.forecast

`forecast(name=None, start=None, end=None, mode='dynamic')`

이 식 하나만 풀어 목표변수를 예측한다(다른 변수는 실측·워크파일 값). 결과는 시리즈로 워크파일에 쓴다.

**매개변수**

- `name`: 결과 시리즈 이름(기본: 목표변수 + 'F')
- `start, end`: 구간(기본: 표본)
- `mode`: 'dynamic'(종속변수 시차에 예측값) · 'static'(시차에 실측)

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
eq = wf.equation("eq_i").ls("I c Y(-1) R")
f = eq.forecast(start="2015Q1", end="2019Q4")
f.name, int(f.notna().sum())
# ('IF', 20)
```

## 5. 모델 객체 `wf.model(…)`

| 이름 | 서명 | 설명 |
|---|---|---|
| [`merge`](#modelobjectmerge) | `(*items)` | 추정식을 모델에 더한다. |
| [`append`](#modelobjectappend) | `(*lines)` | 항등식을 더한다(계수 없이 늘 성립하는 식 — 좌변의 첫 변수가 목표변수). 여러 줄 글자도 되고 `#` 뒤는 주석. 이미 있는 항등식(공백·대소문자 무시)은 다시 넣지 않는다. |
| [`drop`](#modelobjectdrop) | `(*names)` | 식을 뺀다 — 방정식 객체 이름 또는 항등식의 목표변수. 뺀 식의 목표변수는 외생(실측)이 된다. |
| `equations` | `속성` | 모델의 추정식(방정식 객체 목록). |
| `identities` | `속성` | 모델의 항등식(글자 목록). |
| `engine` | `속성` | 엔진 Model 객체 — 고급 사용(직접 simulate 등). |
| `endogenous` | `속성` | 내생변수 — 각 식의 목표변수(이름 순). |
| `exogenous` | `속성` | 외생변수 — 식에 쓰였지만 어떤 식도 결정하지 않는 변수(이름 순). 지시자 열(@trend 등)도 포함. |
| `output` | `()` | 식 목록 표(종류·이름·목표변수·추정법·식). |
| `show` | `()` | 식 목록 표를 보인다. |
| [`blocks`](#modelobjectblocks) | `()` | 블록 구조 표 — 함께 풀어야 하는 변수 묶음(동시 블록)과 풀이 순서(위에서부터). |
| [`variables`](#modelobjectvariables) | `()` | 변수 표(변수 · 구분 = 내생/외생). |
| [`gaps`](#modelobjectgaps) | `(start=None, end=None)` | 입력 결측 진단 — 기간·식마다 비어 있는 입력(시차 포함). 풀이 때 그 기간 그 식은 빠진다(on_missing='exclude'). |
| [`scenario`](#modelobjectscenario) | `(name=None, alias=None)` | 시나리오를 만들거나 고르고 **활성화**한다 — 이후 solve()는 활성 시나리오로 푼다. 인자 없이 부르면 활성 시나리오. |
| `scenarios` | `속성` | 시나리오 {이름: ScenarioObject}. |
| [`solve`](#modelobjectsolve) | `(start=None, end=None, mode='dynamic', scenario=None, **opts)` | 활성(또는 지정) 시나리오로 풀고, 결과를 별칭 시리즈(예: Y_0)로 워크파일에 쓴다(구간 밖은 빈 칸). |
| [`forecast`](#modelobjectforecast) | `(start, end, exog_fill=None, mode='dynamic', scenario=None, **opts)` | 전망 — 필요하면 기간을 늘리고, exog_fill로 외생 경로를 채운 뒤 푼다. 시작 앞 내생변수 실측과 외생 경로를 미리 진단한다. |
| [`stochastic`](#modelobjectstochastic) | `(start=None, end=None, reps=100, seed=None, scenario=None, **kw)` | 확률적 모의 — 추정 잔차를 기간마다 다시 뽑아(식 사이 상관 보존) reps번 풀어 평균·표준편차·분위수 띠를 낸다. |
| [`control`](#modelobjectcontrol) | `(target, instrument, path, start=None, end=None, name=None, scenario=None, **kw)` | 목표 추적 — target(내생)이 path를 따르도록 instrument(외생)를 거꾸로 풀어 시리즈(기본 이름 instrument + '_C')로 쓴다. |
| [`multipliers`](#modelobjectmultipliers) | `(var, shock, start=None, end=None, scenario=None, **kw)` | 충격 승수 — var(외생)를 shock만큼 바꿨을 때 내생변수의 기간별 반응(충격 − 기준선). |
| [`stability`](#modelobjectstability) | `(period=None, scenario=None, measure='relative')` | 동태 안정성 — period(기본: 표본 끝)의 값에서 선형화한 모델의 동반행렬 고윳값. |
| [`stability_path`](#modelobjectstability_path) | `(start=None, end=None, scenario=None, measure='relative')` | 기간마다 가장 큰 근의 모듈러스·1 이상인 근의 수·판정(행 = 기간 라벨). |
| [`decompose`](#modelobjectdecompose) | `(variables, scenario, base='baseline', start=None, end=None, method='shapley', mode='dynamic', **opts)` | 시나리오 기여도 분해 — scenario와 base(기준선)의 차이를 시나리오 항목(외생 경로·충격·조정항·exclude·목표 추적)별로 나눈다. |
| [`compare`](#modelobjectcompare) | `(var, aliases=None)` | 실측과 시나리오 결과 시리즈를 나란히(표본 구간). aliases로 별칭을 고른다. |

### ModelObject.merge

`merge(*items)`

추정식을 모델에 더한다.

받는 것: 방정식 객체 · 객체 이름 · 추정식 글자(그 자리에서 현재 표본으로 추정) · 방정식 파일 경로(한 줄에 한 식 — 추정식은  
추정하고 항등식은 그대로 더한다) · 시스템·VAR·VECM 객체(추정 계수를 고정한 식으로) · 그 목록.  

**돌려주는 것**

이 모델 객체(이어 부르기)  

**오류**

- `ValueError`: 항등식을 merge(→ append) · MergeError: 파일의 식 추정 실패(줄 번호와 함께)

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
eq_i = wf.equation("eq_i").ls("I c Y(-1) R")
eq_cn = wf.equation("eq_cn").tsls("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
m = wf.model("toy").merge(eq_i, eq_cn).append("Y = CN + I + G")
m.endogenous
# ['CN', 'I', 'Y']
_ = m.merge("dlog(P) c dlog(Y) dlog(POIL)")
m.endogenous
# ['CN', 'I', 'P', 'Y']
```

**관련** — append · drop

### ModelObject.append

`append(*lines)`

항등식을 더한다(계수 없이 늘 성립하는 식 — 좌변의 첫 변수가 목표변수). 여러 줄 글자도 되고 `#` 뒤는 주석. 이미 있는 항등식(공백·대소문자 무시)은 다시 넣지 않는다.

**오류**

- `ValueError`: 항등식이 아님(추정식은 merge)

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
m = wf.model("m1").merge("I c Y(-1) R", "CN c Y CN(-1)")
_ = m.append("Y = CN + I + G   # 국민소득")
m.identities
# ['Y = CN + I + G']
```

### ModelObject.drop

`drop(*names)`

식을 뺀다 — 방정식 객체 이름 또는 항등식의 목표변수. 뺀 식의 목표변수는 외생(실측)이 된다.

**오류**

- `KeyError`: 모델에 없는 이름

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
eq_i = wf.equation("eq_i").ls("I c Y(-1) R")
eq_cn = wf.equation("eq_cn").tsls("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
m = wf.model("toy").merge(eq_i, eq_cn).append("Y = CN + I + G")
_ = m.drop("eq_i")
m.endogenous, "I" in m.exogenous
# (['CN', 'Y'], True)
```

### ModelObject.blocks

`blocks()`

블록 구조 표 — 함께 풀어야 하는 변수 묶음(동시 블록)과 풀이 순서(위에서부터).

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
eq_i = wf.equation("eq_i").ls("I c Y(-1) R")
eq_cn = wf.equation("eq_cn").tsls("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
m = wf.model("toy").merge(eq_i, eq_cn).append("Y = CN + I + G")
t = m.blocks()
t.data[["종류", "변수"]].values.tolist()
# [['순차', 'I'], ['동시', 'CN, Y']]
```

### ModelObject.variables

`variables()`

변수 표(변수 · 구분 = 내생/외생).

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
eq_i = wf.equation("eq_i").ls("I c Y(-1) R")
eq_cn = wf.equation("eq_cn").tsls("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
m = wf.model("toy").merge(eq_i, eq_cn).append("Y = CN + I + G")
sorted(m.variables()["구분"].value_counts().items())
# [('내생', 3), ('외생', 2)]
```

### ModelObject.gaps

`gaps(start=None, end=None)`

입력 결측 진단 — 기간·식마다 비어 있는 입력(시차 포함). 풀이 때 그 기간 그 식은 빠진다(on_missing='exclude').

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
eq_i = wf.equation("eq_i").ls("I c Y(-1) R")
eq_cn = wf.equation("eq_cn").tsls("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
m = wf.model("toy").merge(eq_i, eq_cn).append("Y = CN + I + G")
g = m.gaps("1970Q1", "1970Q2")
g[["period", "target", "missing"]].values.tolist()
# [['1970Q1', 'I', 'Y(-1)'], ['1970Q1', 'CN', 'CN(-1)']]
```

### ModelObject.scenario

`scenario(name=None, alias=None)`

시나리오를 만들거나 고르고 **활성화**한다 — 이후 solve()는 활성 시나리오로 푼다. 인자 없이 부르면 활성 시나리오.

기준선은 처음부터 있는 'baseline'(별칭 `_0`), 새 시나리오의 별칭은 `_1`, `_2` … 또는 alias로 정한다(이름은 대소문자 무시).  

**오류**

- `ValueError`: 별칭이 이미 다른 시나리오의 것

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
eq_i = wf.equation("eq_i").ls("I c Y(-1) R")
eq_cn = wf.equation("eq_cn").tsls("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
m = wf.model("toy").merge(eq_i, eq_cn).append("Y = CN + I + G")
sc = m.scenario("hi_g")
sc.alias, list(m.scenarios)
# ('_1', ['baseline', 'hi_g'])
m.scenario("baseline").alias
# '_0'
```

**관련** — solve · ScenarioObject

### ModelObject.solve

`solve(start=None, end=None, mode='dynamic', scenario=None, **opts)`

활성(또는 지정) 시나리오로 풀고, 결과를 별칭 시리즈(예: Y_0)로 워크파일에 쓴다(구간 밖은 빈 칸).

**매개변수**

- `start, end`: 구간(기본: 표본)
- `mode`: 'dynamic'(시차에 풀이 값) · 'static'(시차에 실측) · 'fit'(식마다 따로)
- `scenario`: 시나리오 이름(기본: 활성)
- `**opts`: method · fallback · tolerance · max_iterations · on_missing · on_fail · jacobian · mce · mce_method · terminal

**돌려주는 것**

SolveResult — .counts() · .status() · .statistics() · .summary() · .save()  

**오류**

- `ValueError`: 옵션 값이 틀림 · StructureError: 모델 구조(같은 변수를 두 식이 결정 등)

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
eq_i = wf.equation("eq_i").ls("I c Y(-1) R")
eq_cn = wf.equation("eq_cn").tsls("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
m = wf.model("toy").merge(eq_i, eq_cn).append("Y = CN + I + G")
r = m.solve("2010Q1", "2019Q4")
r.counts()
# {'ok': 40, 'partial': 0, 'fallback': 0, 'failed': 0}
round(wf.elem("Y_0", "2019Q4"), 1)
# 624.9
```

**관련** — forecast · scenario · docs/explain/solving.md

### ModelObject.forecast

`forecast(start, end, exog_fill=None, mode='dynamic', scenario=None, **opts)`

전망 — 필요하면 기간을 늘리고, exog_fill로 외생 경로를 채운 뒤 푼다. 시작 앞 내생변수 실측과 외생 경로를 미리 진단한다.

**매개변수**

- `start, end`: 전망 구간
- `exog_fill`: 비어 있는 외생을 채울 규칙 'last' · 'growth' · 'trend'(None이면 채우지 않음 — 비었으면 오류로 알려 준다)
- `mode, scenario, **opts`: solve와 같다

**오류**

- `ValueError`: 외생 경로가 빔(무엇이 언제) · 시작 앞 내생변수 실측이 빔(채우는 법과 함께)

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
eq_i = wf.equation("eq_i").ls("I c Y(-1) R")
eq_cn = wf.equation("eq_cn").tsls("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
m = wf.model("toy").merge(eq_i, eq_cn).append("Y = CN + I + G")
r = m.forecast("2020Q1", "2020Q4", exog_fill="last")
r.counts()["ok"]
# 4
```

### ModelObject.stochastic

`stochastic(start=None, end=None, reps=100, seed=None, scenario=None, **kw)`

확률적 모의 — 추정 잔차를 기간마다 다시 뽑아(식 사이 상관 보존) reps번 풀어 평균·표준편차·분위수 띠를 낸다.

coef_uncertainty=True면 계수도 추정 분포에서 뽑는다. percentiles로 분위수를 고른다(기본 5·50·95).  

**돌려주는 것**

StochasticResult — .mean · .std · .percentiles · .band(변수)  

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
eq_i = wf.equation("eq_i").ls("I c Y(-1) R")
eq_cn = wf.equation("eq_cn").tsls("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
m = wf.model("toy").merge(eq_i, eq_cn).append("Y = CN + I + G")
s = m.stochastic("2018Q1", "2018Q4", reps=50, seed=1)
list(s.band("Y").columns)
# ['mean', 'std', 'p5', 'p50', 'p95']
```

### ModelObject.control

`control(target, instrument, path, start=None, end=None, name=None, scenario=None, **kw)`

목표 추적 — target(내생)이 path를 따르도록 instrument(외생)를 거꾸로 풀어 시리즈(기본 이름 instrument + '_C')로 쓴다.

path는 Series·{기간: 값}·스칼라 — start~end 구간에만 쓰인다.  

**오류**

- `SimulationError`: instrument가 내생이거나 target이 instrument에 반응하지 않음

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
eq_i = wf.equation("eq_i").ls("I c Y(-1) R")
eq_cn = wf.equation("eq_cn").tsls("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
m = wf.model("toy").merge(eq_i, eq_cn).append("Y = CN + I + G")
g = m.control("Y", "G", 600.0, "2010Q1", "2010Q4")
g.name, round(wf.elem("G_C", "2010Q1"), 1)
# ('G_C', 76.4)
```

### ModelObject.multipliers

`multipliers(var, shock, start=None, end=None, scenario=None, **kw)`

충격 승수 — var(외생)를 shock만큼 바꿨을 때 내생변수의 기간별 반응(충격 − 기준선).

kind='level'(더하기) · 'pct'(%), permanent=False면 첫 기간만 충격. 내생변수를 주면 그 식의 조정항에 더한다.  

**돌려주는 것**

MultiplierResult — .level(수준 차) · .pct(% 차) · .baseline · .shocked  

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
eq_i = wf.equation("eq_i").ls("I c Y(-1) R")
eq_cn = wf.equation("eq_cn").tsls("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
m = wf.model("toy").merge(eq_i, eq_cn).append("Y = CN + I + G")
mu = m.multipliers("G", 1.0, "2015Q1", "2015Q4")
round(float(mu.level["Y"].iloc[0]), 2)
# 2.13
```

### ModelObject.stability

`stability(period=None, scenario=None, measure='relative')`

동태 안정성 — period(기본: 표본 끝)의 값에서 선형화한 모델의 동반행렬 고윳값.

모든 근이 1보다 작으면 그 근처의 편차가 줄어든다(안정). 1인 근만 있으면 '단위근'(차분식처럼 수준이 적분된 변수),  
1보다 큰 근이 있으면 '불안정'. scenario를 주면 그 풀이 값에서 선형화한다. 선행변수가 있는 모델은 쓸 수 없다.  

**매개변수**

- `measure`: 'relative'(양수 변수는 상대 편차 — 로그식이 성장률만큼 부풀지 않음) · 'level'

**돌려주는 것**

StabilityView — .eigenvalues · .max_modulus · .verdict · .loadings(가장 큰 근과 함께 움직이는 변수) · .output()  

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
eq_i = wf.equation("eq_i").ls("I c Y(-1) R")
eq_cn = wf.equation("eq_cn").tsls("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
m = wf.model("toy").merge(eq_i, eq_cn).append("Y = CN + I + G")
st = m.stability("2010Q1")
st.verdict, round(st.max_modulus, 2)
# ('안정', 0.76)
```

### ModelObject.stability_path

`stability_path(start=None, end=None, scenario=None, measure='relative')`

기간마다 가장 큰 근의 모듈러스·1 이상인 근의 수·판정(행 = 기간 라벨).

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
eq_i = wf.equation("eq_i").ls("I c Y(-1) R")
eq_cn = wf.equation("eq_cn").tsls("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
m = wf.model("toy").merge(eq_i, eq_cn).append("Y = CN + I + G")
p = m.stability_path("2010Q1", "2010Q4")
list(p.columns)
# ['최대 모듈러스', '1 이상인 근', '안정', '판정']
```

### ModelObject.decompose

`decompose(variables, scenario, base='baseline', start=None, end=None, method='shapley', mode='dynamic', **opts)`

시나리오 기여도 분해 — scenario와 base(기준선)의 차이를 시나리오 항목(외생 경로·충격·조정항·exclude·목표 추적)별로 나눈다.

method='shapley'(모든 부분집합의 평균 — 합이 정확히 전체 차이, 항목 8개 이하) · 'single'(하나씩 + 상호작용).  
구간 기본값은 표본.  

**돌려주는 것**

DecompositionView — .table(var) · .output(var) · .graph(var) · .drivers · .total  

**오류**

- `ValueError`: 기준선과 다른 항목이 없음 · 항목이 많아 shapley가 너무 큼

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
eq_i = wf.equation("eq_i").ls("I c Y(-1) R")
eq_cn = wf.equation("eq_cn").tsls("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
m = wf.model("toy").merge(eq_i, eq_cn).append("Y = CN + I + G")
sc = m.scenario("mix")
_ = sc.shock("G", 10, "2015Q1", "2015Q4").override("R", 5.0)
d = m.decompose("Y", "mix", start="2015Q1", end="2015Q4")
t = d.table("Y")
bool(abs(t.drop(columns="합계(시나리오 − 기준선)").sum(axis=1) - t["합계(시나리오 − 기준선)"]).max() < 1e-9)
# True
```

### ModelObject.compare

`compare(var, aliases=None)`

실측과 시나리오 결과 시리즈를 나란히(표본 구간). aliases로 별칭을 고른다.

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
eq_i = wf.equation("eq_i").ls("I c Y(-1) R")
eq_cn = wf.equation("eq_cn").tsls("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
m = wf.model("toy").merge(eq_i, eq_cn).append("Y = CN + I + G")
_ = m.solve("2019Q1", "2019Q4")
list(m.compare("Y").columns)
# ['Y', 'Y_0']
```

## 6. 시나리오 객체 `m.scenario(…)`

| 이름 | 서명 | 설명 |
|---|---|---|
| [`override`](#scenarioobjectoverride) | `(var, path)` | 외생변수의 경로를 바꾼다(주지 않은 기간은 실측). path: Series · {기간: 값} · 스칼라 · 워크파일 시리즈 이름. |
| [`exclude`](#scenarioobjectexclude) | `(var, start=None, end=None)` | 내생변수를 식 대신 실측(또는 override 경로)으로 고정한다. start·end를 주면 그 구간만. |
| [`add_factor`](#scenarioobjectadd_factor) | `(var, path)` | 식의 조정항(좌변 단위)을 더한다. var: 방정식 객체 이름 · 종속변수 표기(`dlog(P)`) · 목표변수. path는 override와 같다. |
| [`init_add_factor`](#scenarioobjectinit_add_factor) | `(var, base)` | base 시점의 식 잔차를 조정항으로 그 뒤 기간에 이어 붙인다 — 전망이 실측에서 매끄럽게 출발하게('착지'). |
| [`shock`](#scenarioobjectshock) | `(var, value, start, end=None, kind='level')` | 충격 — 외생변수면 경로를(kind='level' 더하기 · 'pct' %), 추정식의 목표변수면(또는 kind='add_factor') 식 조정항을 바꾼다. |
| [`control`](#scenarioobjectcontrol) | `(target, instrument, path)` | 이 시나리오에 목표 추적을 넣는다 — 풀 때 target 경로를 맞추도록 instrument(외생)를 함께 푼다. |
| [`use_residuals`](#scenarioobjectuse_residuals) | `(on=True)` | 표본 안의 추정 잔차를 모든 추정식의 조정항으로 더한다 — 항등식이 자료에서 성립하면 과거를 그대로 재현한다(모델 점검용). |
| [`clear`](#scenarioobjectclear) | `()` | 설정을 모두 지운다(이름·별칭은 그대로). |

### ScenarioObject.override

`override(var, path)`

외생변수의 경로를 바꾼다(주지 않은 기간은 실측). path: Series · {기간: 값} · 스칼라 · 워크파일 시리즈 이름.

exclude한 내생변수에 주면 그 고정 경로가 되고, exclude하지 않은 내생변수에 주면 풀이 구간 밖의 값(초기 시차)으로만 쓰인다.  

**돌려주는 것**

이 시나리오(이어 부르기)  

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
eq_i = wf.equation("eq_i").ls("I c Y(-1) R")
eq_cn = wf.equation("eq_cn").tsls("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
m = wf.model("toy").merge(eq_i, eq_cn).append("Y = CN + I + G")
sc = m.scenario("hi_g").override("G", wf["G"] * 1.1)
_ = m.solve("2010Q1", "2010Q4")
bool(wf.elem("Y_1", "2010Q1") > wf.elem("Y", "2010Q1"))
# True
```

### ScenarioObject.exclude

`exclude(var, start=None, end=None)`

내생변수를 식 대신 실측(또는 override 경로)으로 고정한다. start·end를 주면 그 구간만.

**오류**

- `SimulationError`: 내생변수가 아님(풀 때)

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
eq_i = wf.equation("eq_i").ls("I c Y(-1) R")
eq_cn = wf.equation("eq_cn").tsls("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
m = wf.model("toy").merge(eq_i, eq_cn).append("Y = CN + I + G")
_ = m.scenario("fix_i").exclude("I")
r = m.solve("2010Q1", "2010Q4")
bool((r.values["I"] == wf["I"].loc[r.values.index]).all())
# True
```

### ScenarioObject.add_factor

`add_factor(var, path)`

식의 조정항(좌변 단위)을 더한다. var: 방정식 객체 이름 · 종속변수 표기(`dlog(P)`) · 목표변수. path는 override와 같다.

**오류**

- `ValueError`: 해당 추정식이 없음(항등식 변수에는 조정항을 줄 수 없다)

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
eq_i = wf.equation("eq_i").ls("I c Y(-1) R")
eq_cn = wf.equation("eq_cn").tsls("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
m = wf.model("toy").merge(eq_i, eq_cn).append("Y = CN + I + G")
_ = m.scenario("af").add_factor("eq_cn", -5.0)
_ = m.solve("2010Q1", "2010Q1")
bool(wf.elem("CN_1", "2010Q1") < wf.elem("CN", "2010Q1"))
# True
```

### ScenarioObject.init_add_factor

`init_add_factor(var, base)`

base 시점의 식 잔차를 조정항으로 그 뒤 기간에 이어 붙인다 — 전망이 실측에서 매끄럽게 출발하게('착지').

**오류**

- `SimulationError`: 해당 추정식이 없거나 그 시점 잔차를 계산할 수 없음

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
eq_i = wf.equation("eq_i").ls("I c Y(-1) R")
eq_cn = wf.equation("eq_cn").tsls("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
m = wf.model("toy").merge(eq_i, eq_cn).append("Y = CN + I + G")
sc = m.scenario("landed").init_add_factor("eq_cn", "2009Q4")
m.solve("2010Q1", "2010Q4").counts()["ok"]
# 4
```

### ScenarioObject.shock

`shock(var, value, start, end=None, kind='level')`

충격 — 외생변수면 경로를(kind='level' 더하기 · 'pct' %), 추정식의 목표변수면(또는 kind='add_factor') 식 조정항을 바꾼다.

end를 주지 않으면 한 기간. 같은 변수에 여러 번 주면 차례로 더해진다.  

**오류**

- `ValueError`: kind가 틀림 · SimulationError: 항등식 변수, 모델에 없는 변수

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
eq_i = wf.equation("eq_i").ls("I c Y(-1) R")
eq_cn = wf.equation("eq_cn").tsls("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
m = wf.model("toy").merge(eq_i, eq_cn).append("Y = CN + I + G")
_ = m.scenario("g5").shock("G", 5, "2015Q1")
_ = m.solve("2015Q1", "2015Q1")
round(wf.elem("Y_1", "2015Q1") - wf.elem("Y", "2015Q1"), 1) > 5
# True
```

### ScenarioObject.control

`control(target, instrument, path)`

이 시나리오에 목표 추적을 넣는다 — 풀 때 target 경로를 맞추도록 instrument(외생)를 함께 푼다.

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
eq_i = wf.equation("eq_i").ls("I c Y(-1) R")
eq_cn = wf.equation("eq_cn").tsls("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
m = wf.model("toy").merge(eq_i, eq_cn).append("Y = CN + I + G")
_ = m.scenario("tgt").control("Y", "G", 600.0)
r = m.solve("2010Q1", "2010Q2")
r.values["Y"].round(6).tolist()
# [600.0, 600.0]
```

### ScenarioObject.use_residuals

`use_residuals(on=True)`

표본 안의 추정 잔차를 모든 추정식의 조정항으로 더한다 — 항등식이 자료에서 성립하면 과거를 그대로 재현한다(모델 점검용).

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
eq_i = wf.equation("eq_i").ls("I c Y(-1) R")
eq_cn = wf.equation("eq_cn").tsls("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
m = wf.model("toy").merge(eq_i, eq_cn).append("Y = CN + I + G")
_ = m.scenario("replay").use_residuals()
r = m.solve("2010Q1", "2019Q4")
float((r.values["Y"] / wf["Y"].loc[r.values.index] - 1).abs().max()) < 1e-8
# True
```

### ScenarioObject.clear

`clear()`

설정을 모두 지운다(이름·별칭은 그대로).

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
eq_i = wf.equation("eq_i").ls("I c Y(-1) R")
eq_cn = wf.equation("eq_cn").tsls("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
m = wf.model("toy").merge(eq_i, eq_cn).append("Y = CN + I + G")
sc = m.scenario("tmp").override("G", 1.0)
sc.clear()
# <시나리오 tmp (_1)>
```

## 7. 풀이 결과 `SolveResult`

| 이름 | 서명 | 설명 |
|---|---|---|
| `values` | `속성` | 풀린 내생변수 값(DataFrame, 행 = 풀이 기간). |
| `counts` | `()` | 기간 상태 수 {'ok', 'partial', 'fallback', 'failed'}. |
| `status` | `()` | 기간별 상태 표 — status · iterations · max_resid(정규화 잔차) · methods · excluded(빠진 식과 이유) · fallback · message. |
| `output` | `()` | 상태 표(TableOutput). |
| `show` | `()` | 상태 표를 보인다. |
| `statistics` | `()` | 변수별 적합도(실측 대비 RMSPE·MAE 등, 실측 대체·제외 기간은 뺌) — RMSPE 오름차순. |
| `summary` | `(top=10)` | 적합도 상위 top개 표(RMSPE·MAE 등 — 실측 대체·제외 기간은 뺀다). 0 근처 계열은 RMSPE가 과대하니 MAE도 본다. |
| `save` | `(path=None, hs_id=None)` | 결과를 기존 HS CSV 형식(기간별 상태 열 포함)으로 저장한다. 기본: HS/<hs_id>_results_<시작>_<끝>.csv |

## 8. 시스템 객체 `wf.system(…)`

| 이름 | 서명 | 설명 |
|---|---|---|
| [`append`](#systemobjectappend) | `(*lines)` | 식을 더한다(여러 줄 글자도 됨). 추정식 꼴(`Y c X` — 계수 번호는 이어서 자동)이나 `c(n)` 꼴(`Y = c(1) + c(2)*X`)로 쓴다. |
| `equations` | `속성` | 시스템의 식(글자 목록, @inst 줄 제외). |
| [`ols`](#systemobjectols) | `(restrict=None)` | 식마다 최소제곱 — 공유 계수·restrict 제약은 함께 반영하고, 공분산은 식 사이 상관을 반영한 샌드위치. |
| [`sur`](#systemobjectsur) | `(iterate=False, restrict=None)` | SUR(Zellner, 실행 가능한 GLS) — OLS 잔차의 Σ̂로 GLS. iterate=True면 Σ̂·계수를 수렴할 때까지(= 정규 최우). |
| [`tsls`](#systemobjecttsls) | `(inst=None, restrict=None)` | 시스템 2단계 최소제곱 — 식마다 도구변수로 투영해 추정. inst를 주면 모든 식에 그 도구. |
| [`three_sls`](#systemobjectthree_sls) | `(inst=None, restrict=None, iterate=False)` | 3단계 최소제곱 — 2SLS 잔차의 Σ̂로 투영 자료에 GLS(식 사이 오차 상관까지 쓴다). iterate=True면 반복. |
| [`fiml`](#systemobjectfiml) | `(restrict=None, start=None)` | 완전정보 최우 — 집중 로그우도 −(T/2)log\|Σ̂\| + Σ log\|det ∂ε/∂y\|를 최대화(해석적 기울기 BFGS + Newton 마무리). |
| `coefs` | `속성` | 계수(Series, 이름 c(1)…). |
| `stderrs` | `속성` | 계수 표준오차(Series). |
| `zstats` | `속성` | 계수의 z값(Series — 시스템 추정은 정규 근사). |
| `pvalues` | `속성` | 계수 = 0 검정의 p값(Series, 정규 근사). |
| `cov` | `()` | 계수 공분산 행렬(DataFrame). |
| `resid` | `속성` | 식별 구조 잔차(표본 기간 × 식, 열 이름 = 목표변수). |
| `sigma` | `속성` | 잔차 공분산 Σ̂ = ÊᵀÊ/T. |
| `equation_stats` | `()` | 식별 R²·회귀 표준오차·DW·관측치. |
| `output` | `()` | 계수 표와 식별 통계. |
| `show` | `()` | 결과 표를 보인다. |
| [`wald`](#systemobjectwald) | `(*restrictions)` | 시스템 계수(c(n))의 선형 제약 Wald 검정(χ²). 이미 추정에 넣은 제약을 다시 검정하면 오류로 알려 준다. |
| [`make_equations`](#systemobjectmake_equations) | `()` | 추정한 계수를 고정한 방정식 객체들(이름 시스템_목표변수, 소문자)을 워크파일에 만든다 — 모델 merge가 쓴다. |
| `to_json` | `()` | 저장용 정의(dict — 식·도구·추정 설정). 열 때 같은 설정으로 다시 추정한다. |
| `from_json` | `(wf, d)` | 저장한 정의로 시스템 객체를 되살린다(워크파일 열기가 쓴다). |

### SystemObject.append

`append(*lines)`

식을 더한다(여러 줄 글자도 됨). 추정식 꼴(`Y c X` — 계수 번호는 이어서 자동)이나 `c(n)` 꼴(`Y = c(1) + c(2)*X`)로 쓴다.

같은 c(n)을 두 식에 쓰면 그 계수가 같게 묶인다(식 사이 제약). 식 끝의 `@inst …`는 그 식만의 도구, `@inst …`만 있는 줄은  
모든 식의 도구다(상수항은 늘 포함). 계수에 선형인 식만 된다. 항등식은 넣지 않는다(모델에서 append).  

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("klein_like")
s = wf.system("kl")
_ = s.append("CONS c PR PR(-1) WP+WG", "I c PR PR(-1) K(-1)", "WP c X X(-1) A",
             "@inst G T WG A PR(-1) K(-1) X(-1)")
len(s.equations)
# 3
```

### SystemObject.ols

`ols(restrict=None)`

식마다 최소제곱 — 공유 계수·restrict 제약은 함께 반영하고, 공분산은 식 사이 상관을 반영한 샌드위치.

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("klein_like")
s = wf.system("kl")
_ = s.append("CONS c PR PR(-1) WP+WG", "I c PR PR(-1) K(-1)", "WP c X X(-1) A",
             "@inst G T WG A PR(-1) K(-1) X(-1)")
round(float(s.ols().coefs["c(2)"]), 2)
# 0.25
```

### SystemObject.sur

`sur(iterate=False, restrict=None)`

SUR(Zellner, 실행 가능한 GLS) — OLS 잔차의 Σ̂로 GLS. iterate=True면 Σ̂·계수를 수렴할 때까지(= 정규 최우).

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("klein_like")
s = wf.system("kl")
_ = s.append("CONS c PR PR(-1) WP+WG", "I c PR PR(-1) K(-1)", "WP c X X(-1) A",
             "@inst G T WG A PR(-1) K(-1) X(-1)")
s.sur(iterate=True).method
# 'sur-it'
```

### SystemObject.tsls

`tsls(inst=None, restrict=None)`

시스템 2단계 최소제곱 — 식마다 도구변수로 투영해 추정. inst를 주면 모든 식에 그 도구.

**오류**

- `ValueError`: 도구가 없는 식, 도구가 계수보다 적은 식

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("klein_like")
s = wf.system("kl")
_ = s.append("CONS c PR PR(-1) WP+WG", "I c PR PR(-1) K(-1)", "WP c X X(-1) A",
             "@inst G T WG A PR(-1) K(-1) X(-1)")
round(float(s.tsls().coefs["c(2)"]), 2)
# 0.16
```

### SystemObject.three_sls

`three_sls(inst=None, restrict=None, iterate=False)`

3단계 최소제곱 — 2SLS 잔차의 Σ̂로 투영 자료에 GLS(식 사이 오차 상관까지 쓴다). iterate=True면 반복.

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("klein_like")
s = wf.system("kl")
_ = s.append("CONS c PR PR(-1) WP+WG", "I c PR PR(-1) K(-1)", "WP c X X(-1) A",
             "@inst G T WG A PR(-1) K(-1) X(-1)")
s.three_sls().coefs.round(2)[["c(2)", "c(6)"]].tolist()
# [0.16, -0.06]
```

### SystemObject.fiml

`fiml(restrict=None, start=None)`

완전정보 최우 — 집중 로그우도 −(T/2)log|Σ̂| + Σ log|det ∂ε/∂y|를 최대화(해석적 기울기 BFGS + Newton 마무리).

내생변수는 시스템 식의 목표변수다. 시작값 기본은 시스템 OLS, 공분산은 관측 정보(헤시안). 시스템에는 항등식을 넣을 수 없으므로  
항등식이 정하는 같은 기 내생변수(예: Klein 모형의 이윤·총수요)가 설명변수에 있으면 그것을 외생으로 다룬다 — 그런 모형은  
3SLS를 쓰거나 항등식을 대입해 식을 다시 쓴다(도구 목록이 있으면 도구에 없는 같은 기 설명변수를 경고한다).  

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
s = wf.system("s2")
_ = s.append("I c Y(-1) R", "RL c R")
round(float(s.fiml().coefs["c(3)"]), 2)                # 두 식이 함께 관측되는 1980Q1~
# -1.0
```

### SystemObject.wald

`wald(*restrictions)`

시스템 계수(c(n))의 선형 제약 Wald 검정(χ²). 이미 추정에 넣은 제약을 다시 검정하면 오류로 알려 준다.

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("klein_like")
s = wf.system("kl")
_ = s.append("CONS c PR PR(-1) WP+WG", "I c PR PR(-1) K(-1)", "WP c X X(-1) A",
             "@inst G T WG A PR(-1) K(-1) X(-1)")
_ = s.three_sls()
s.wald("c(3) = c(7)").reject(0.05)
# True
```

### SystemObject.make_equations

`make_equations()`

추정한 계수를 고정한 방정식 객체들(이름 시스템_목표변수, 소문자)을 워크파일에 만든다 — 모델 merge가 쓴다.

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("klein_like")
s = wf.system("kl")
_ = s.append("CONS c PR PR(-1) WP+WG", "I c PR PR(-1) K(-1)", "WP c X X(-1) A",
             "@inst G T WG A PR(-1) K(-1) X(-1)")
_ = s.three_sls()
[o.name for o in s.make_equations()]
# ['kl_cons', 'kl_i', 'kl_wp']
```

## 9. VAR 객체 `wf.var(…)`

| 이름 | 서명 | 설명 |
|---|---|---|
| `to_json` | `()` | 저장용 정의(dict — 변수·시차·결정항). |
| `from_json` | `(wf, d)` | 저장한 정의로 다시 추정해 되살린다(워크파일 열기가 쓴다). |
| [`estimate`](#varobjectestimate) | `(series, lags=1, trend='c')` | 같은 객체를 다른 변수·시차로 다시 추정한다(보통은 wf.var가 부른다). |
| `coefs` | `속성` | 계수(행 = 회귀변수, 열 = 식). |
| `stderrs` | `속성` | 계수 표준오차(행 = 회귀변수, 열 = 식). |
| `sigma` | `속성` | 잔차 공분산 Σ̂(DataFrame). |
| `resid` | `속성` | 잔차(DataFrame, 행 = 기간, 열 = 식). |
| `ic` | `()` | 정보기준 {aic, bic, hqic, fpe}. |
| [`lag_order`](#varobjectlag_order) | `(maxlags=8)` | 시차 고르기 — 같은 표본(처음 maxlags기 제외)에서 시차 0…maxlags의 AIC·BIC·HQ·FPE(*: 각 기준이 고른 시차). |
| [`granger`](#varobjectgranger) | `(caused, causing)` | Granger 인과 — causing(변수 하나 또는 목록)의 모든 시차가 caused 식에서 0인가(Wald F). |
| [`granger_table`](#varobjectgranger_table) | `()` | 모든 변수 쌍의 Granger F p값 표(행 = 원인, 열 = 결과). |
| [`irf`](#varobjectirf) | `(periods=10, orth=True)` | 충격반응 — 행 = 0…periods, 열 = (반응, 충격). orth=True면 촐레스키(변수 순서대로) 1 표준편차 충격, False면 단위 충격. |
| `irf_graph` | `(impulse, periods=10, orth=True)` | 한 충격에 대한 모든 변수의 반응 그림(GraphOutput). |
| [`fevd`](#varobjectfevd) | `(periods=10)` | 예측오차 분산분해 — {반응 변수: DataFrame(행 = 1…periods, 열 = 충격 변수, 행 합 = 1)}. |
| [`forecast`](#varobjectforecast) | `(steps=8)` | 추정 표본 끝 다음부터 steps기 점 예측(행 = 기간 라벨). |
| [`stability`](#varobjectstability) | `()` | 동반행렬 고윳값 표(모듈러스가 모두 1보다 작으면 안정). |
| `output` | `()` | 식별 계수·표준오차·t값 표와 정보기준. |
| [`make_equations`](#varobjectmake_equations) | `()` | 식마다 `Y c Y(-1) … @trend`를 추정 계수로 고정한 방정식 객체(이름 VAR이름_변수) — 모델 merge가 쓴다. |

### VARObject.estimate

`estimate(series, lags=1, trend='c')`

같은 객체를 다른 변수·시차로 다시 추정한다(보통은 wf.var가 부른다).

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
v = wf.var("v1", ["dlog(Y)", "R"], lags=2)
v.estimate(["dlog(Y)", "R"], lags=1).coefs.shape
# (3, 2)
```

### VARObject.lag_order

`lag_order(maxlags=8)`

시차 고르기 — 같은 표본(처음 maxlags기 제외)에서 시차 0…maxlags의 AIC·BIC·HQ·FPE(*: 각 기준이 고른 시차).

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
v = wf.var("v1", ["dlog(Y)", "R"], lags=2)
t = v.lag_order(4)
len(t.data)
# 5
```

### VARObject.granger

`granger(caused, causing)`

Granger 인과 — causing(변수 하나 또는 목록)의 모든 시차가 caused 식에서 0인가(Wald F).

**오류**

- `KeyError`: VAR에 없는 변수

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
v = wf.var("v1", ["dlog(Y)", "R"], lags=2)
round(v.granger("dlog(Y)", "R").pvalue, 2)
# 0.06
```

### VARObject.granger_table

`granger_table()`

모든 변수 쌍의 Granger F p값 표(행 = 원인, 열 = 결과).

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
v = wf.var("v1", ["dlog(Y)", "R"], lags=2)
v.granger_table().data.shape
# (2, 2)
```

### VARObject.irf

`irf(periods=10, orth=True)`

충격반응 — 행 = 0…periods, 열 = (반응, 충격). orth=True면 촐레스키(변수 순서대로) 1 표준편차 충격, False면 단위 충격.

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
v = wf.var("v1", ["dlog(Y)", "R"], lags=2)
irf = v.irf(4)
irf.shape, float(irf[("dlog(Y)", "R")].iloc[0])
# ((5, 4), 0.0)
```

### VARObject.fevd

`fevd(periods=10)`

예측오차 분산분해 — {반응 변수: DataFrame(행 = 1…periods, 열 = 충격 변수, 행 합 = 1)}.

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
v = wf.var("v1", ["dlog(Y)", "R"], lags=2)
d = v.fevd(4)
float(d["dlog(Y)"].sum(axis=1).round(10).iloc[-1])
# 1.0
```

### VARObject.forecast

`forecast(steps=8)`

추정 표본 끝 다음부터 steps기 점 예측(행 = 기간 라벨).

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
v = wf.var("v1", ["dlog(Y)", "R"], lags=2)
list(v.forecast(2).index)
# ['2020Q1', '2020Q2']
```

### VARObject.stability

`stability()`

동반행렬 고윳값 표(모듈러스가 모두 1보다 작으면 안정).

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
v = wf.var("v1", ["dlog(Y)", "R"], lags=2)
"안정" in v.stability().text()
# True
```

### VARObject.make_equations

`make_equations()`

식마다 `Y c Y(-1) … @trend`를 추정 계수로 고정한 방정식 객체(이름 VAR이름_변수) — 모델 merge가 쓴다.

식(dlog(Y) 등)으로 만든 VAR도 그 식을 종속변수로 쓴다.  

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
v = wf.var("v1", ["dlog(Y)", "R"], lags=2)
[o.eq.dependent_var for o in v.make_equations()]
# ['dlog(Y)', 'R']
```

## 10. VECM 객체 `wf.vecm(…)`

| 이름 | 서명 | 설명 |
|---|---|---|
| `to_json` | `()` | 저장용 정의(dict — 변수·차분 시차·순위·결정항). |
| `from_json` | `(wf, d)` | 저장한 정의로 다시 추정해 되살린다. |
| [`estimate`](#vecmobjectestimate) | `(series, lags_diff=1, rank=1, deterministic='ci')` | 같은 객체를 다른 설정으로 다시 추정한다(보통은 wf.vecm이 부른다). |
| `alpha` | `속성` | 조정 속도 α(행 = 변수, 열 = 공적분 관계) — 균형 오차에 각 변수가 반응하는 크기. |
| `beta` | `속성` | 공적분 벡터 β(행 = 변수(+관계 안 결정항), 열 = 관계, 위 r×r은 단위행렬로 정규화). |
| `gamma` | `속성` | 단기 계수 Γ(차분 시차와 관계 밖 결정항). |
| `sigma` | `속성` | 잔차 공분산 Σ̂. |
| [`forecast`](#vecmobjectforecast) | `(steps=8)` | 추정 표본 끝 다음부터 steps기 점 예측(수준, 행 = 기간 라벨). |
| `output` | `()` | α·Γ 표와 공적분 벡터. |
| [`make_equations`](#vecmobjectmake_equations) | `()` | 식마다 d(Y) = Σα·EC(-1) + ΣΓ·d(·)(-i) + 결정항 — 추정 계수를 고정한 방정식 객체(모델 merge가 쓴다). |

### VECMObject.estimate

`estimate(series, lags_diff=1, rank=1, deterministic='ci')`

같은 객체를 다른 설정으로 다시 추정한다(보통은 wf.vecm이 부른다).

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
_ = wf.smpl("1980Q1", "2019Q4")
k = wf.vecm("k1", ["RL", "R"], rank=1)
k.estimate(["RL", "R"], lags_diff=2, rank=1).fit.k_diff
# 2
```

### VECMObject.forecast

`forecast(steps=8)`

추정 표본 끝 다음부터 steps기 점 예측(수준, 행 = 기간 라벨).

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
_ = wf.smpl("1980Q1", "2019Q4")
k = wf.vecm("k1", ["RL", "R"], rank=1)
list(k.forecast(2).columns)
# ['RL', 'R']
```

### VECMObject.make_equations

`make_equations()`

식마다 d(Y) = Σα·EC(-1) + ΣΓ·d(·)(-i) + 결정항 — 추정 계수를 고정한 방정식 객체(모델 merge가 쓴다).

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
_ = wf.smpl("1980Q1", "2019Q4")
k = wf.vecm("k1", ["RL", "R"], rank=1)
[o.eq.target for o in k.make_equations()]
# ['RL', 'R']
```

## 11. 오차수정모형 결과 `wf.ecm(…)`

| 이름 | 서명 | 설명 |
|---|---|---|
| `longrun` | `()` | 장기 관계 y = a + b·x의 계수(two-step은 장기 OLS — 표준오차는 참고용, nls는 NLS 표준오차). |
| `adjustment` | `속성` | 조정 속도 α(EC(-1)의 계수 — 음수이고 \|α\| < 2여야 균형으로 돌아간다). |
| `half_life` | `속성` | 균형 이탈이 절반으로 주는 기간 수 ln(0.5)/ln(1+α) (−1 < α < 0일 때). |
| `output` | `()` | 장기 계수 표와 조정 속도·반감기·공적분 검정. |
| `show` | `()` | 결과 표를 보인다. |

## 12. 안정성 결과 `m.stability(…)`

| 이름 | 서명 | 설명 |
|---|---|---|
| `output` | `(top=15)` | 고윳값 표(가장 큰 top개)와 판정·가장 큰 근과 함께 움직이는 변수. |
| `show` | `()` | 고윳값 표를 보인다. |

## 13. 기여도 분해 결과 `m.decompose(…)`

| 이름 | 서명 | 설명 |
|---|---|---|
| `drivers` | `속성` | 분해한 시나리오 항목의 이름 목록. |
| `total` | `속성` | 변수별 전체 차이(시나리오 − 기준선) DataFrame. |
| `table` | `(var)` | 한 변수의 항목별 기여도와 합계 표(DataFrame, 행 = 기간 라벨). |
| `output` | `(var=None)` | 한 변수(기본: 첫 변수)의 기여도 표(TableOutput). |
| `graph` | `(var=None)` | 한 변수의 기여도 쌓은 막대 그림(GraphOutput). |
| `show` | `()` | 모든 변수의 기여도 표를 보인다. |

## 14. 계절조정 결과 `wf.seas(…)`

| 이름 | 서명 | 설명 |
|---|---|---|
| `output` | `()` | 실측·계절·추세·불규칙·조정 표. |
| `graph` | `()` | 실측·조정·추세 그림(GraphOutput). |
| `show` | `()` | 결과 표를 보인다. |

## 15. 그래프 객체 `wf.graph(…)`

| 이름 | 서명 | 설명 |
|---|---|---|
| [`data`](#graphobjectdata) | `()` | 그래프에 쓰는 자료(DataFrame, 그래프의 구간). |
| `output` | `()` | 그래프 출력(GraphOutput — .html() · .spec() · .save()). |
| `figure` | `()` | plotly Figure(plotly가 있을 때: pip install 'equion[plot]'). |
| `show` | `()` | 그래프를 보인다(노트북에서는 그림, 스크립트에서는 요약). |
| [`save`](#graphobjectsave) | `(path)` | 그래프를 파일로 — .html(plotly 없이도 됨) · .png·.svg·.pdf(plotly와 kaleido가 필요). 없는 폴더는 만든다. |

### GraphObject.data

`data()`

그래프에 쓰는 자료(DataFrame, 그래프의 구간).

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
g = wf.graph("g1", "Y CN", start="2019Q1", end="2019Q4")
g.data().shape
# (4, 2)
```

### GraphObject.save

`save(path)`

그래프를 파일로 — .html(plotly 없이도 됨) · .png·.svg·.pdf(plotly와 kaleido가 필요). 없는 폴더는 만든다.

**오류**

- `ValueError`: 모르는 확장자

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
wf.graph("g1", "Y CN").save("doc_graph.html")
# 'doc_graph.html'
```

## 16. 표 객체 `wf.table(…)`

| 이름 | 서명 | 설명 |
|---|---|---|
| `output` | `()` | 표 출력(TableOutput). |
| `show` | `()` | 표를 보인다. |
| [`save`](#tableobjectsave) | `(path)` | 표를 파일로 — .csv · .xlsx · .html · .txt(글자 표). 없는 폴더는 만든다. |

### TableObject.save

`save(path)`

표를 파일로 — .csv · .xlsx · .html · .txt(글자 표). 없는 폴더는 만든다.

**오류**

- `ValueError`: 모르는 확장자

**예**

<!-- skip -->
```python
import pandas as pd
wf = eqn.datasets.load("toy_q")
wf.table("t1", pd.DataFrame({"a": [1, 2]})).save("doc_table.csv")
# 'doc_table.csv'
```

## 17. 그래프 출력 `GraphOutput`

| 이름 | 서명 | 설명 |
|---|---|---|
| `data` | `속성` | 그림의 자료(DataFrame). |
| `spec` | `()` | plotly.js 그림 정의 {"data": [...], "layout": {...}} — JSON으로 바로 쓸 수 있는 순수 dict(결측은 None). |
| `figure` | `()` | plotly Figure(plotly 패키지가 있을 때: pip install 'equion[plot]'). |
| `text` | `()` | 글로 된 요약(스크립트·로그용). |
| `html` | `(include_js='cdn', height='420px')` | 그래프 조각(div + 그리기 스크립트). include_js는 `_js_tag` 참조 — 페이지가 이미 plotly.js를 부르면 None. |
| `page` | `(include_js='cdn')` | 그래프 하나짜리 HTML 문서. |
| `save` | `(path, include_js='cdn')` | .html — plotly 없이(include_js='inline'이면 인터넷 없이 열림). png·svg·pdf — plotly와 kaleido가 필요. |

## 18. 표 출력 `TableOutput`

| 이름 | 서명 | 설명 |
|---|---|---|
| `data` | `속성` | 표의 DataFrame. |
| `text` | `()` | 글자 표(머리말·꼬리 줄 포함 — 스크립트·로그용). |
| [`md`](#tableoutputmd) | `()` | md 표(작업 기록 카드·노트·보고서용) — 제목은 굵게, 머리·꼬리 줄은 문단. |
| `html` | `()` | HTML 표(노트북·보고서용). |

### TableOutput.md

`md()`

md 표(작업 기록 카드·노트·보고서용) — 제목은 굵게, 머리·꼬리 줄은 문단.

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
print(wf.equation("eq_i").ls("I c Y(-1) R").output().md().splitlines()[0])
# **방정식 eq_i**
```

## 19. 통계 `eqn.stats`

| 이름 | 서명 | 설명 |
|---|---|---|
| [`Results`](#eqnstatsresults) | `클래스(method, params, y, fitted, df_resid, cov, bread=None, G=None, df_model=nan, k_constant=0, rank=None, wresid=None, weights=None, cov_text=None)` | 추정 결과. params·bse·tvalues·pvalues는 pandas Series, cov_params()는 DataFrame. |
| [`ols`](#eqnstatsols) | `(y, X)` | 최소제곱 — y(Series)를 X(DataFrame, 열 = 회귀변수, 상수항 열 포함)에 회귀. 유사역행렬(SVD)로 푼다. |
| [`wls`](#eqnstatswls) | `(y, X, w)` | 가중 최소제곱 — Σ wₜeₜ² 최소(w ∝ 1/분산). resid·fittedvalues는 가중 전 값, ssr·R²·F·강건 공분산은 가중 잔차로. |
| [`tsls`](#eqnstatstsls) | `(y, X, Z)` | 2단계 최소제곱 — Z는 도구변수(외생 회귀변수 포함). 두 단계 모두 유사역행렬로 푼다(조건수가 제곱되지 않는다). |
| [`gmm`](#eqnstatsgmm) | `(y, X, Z, weight='white', lags=None, iterate=False, maxiter=500, tol=1e-10)` | 선형 GMM — 모멘트 E[zₜ(yₜ − xₜb)] = 0. 1단계 TSLS 잔차로 가중행렬 W = S⁻¹을 만들어 다시 추정하고(2단계), iterate=True면 W를 고쳐 가며 반복한다. weight: 'white' · 'hac'(Bartlett, lags). J 통계량(Hansen)은 extra에. |
| [`liml`](#eqnstatsliml) | `(y, X, Z, exog=None)` | 제한정보 최우(LIML, k-class) — b = [Xᵀ(I − κM_Z)X]⁻¹ Xᵀ(I − κM_Z)y, κ는 최소 고윳값. exog로 외생 회귀변수를 표시한다. |
| [`nls`](#eqnstatsnls) | `(y, params, fitted, J)` | 비선형 최소제곱의 결과 객체를 만든다 — 해(params)·적합값과 해에서의 기울기 J(관측치 × 계수)로 표준오차를 계산한다. |
| [`fixed`](#eqnstatsfixed) | `(y, params, fitted)` | 고정(외부) 계수의 결과 객체 — 표준오차 없음, 적합도 통계만. |
| [`pinv_svd`](#eqnstatspinv_svd) | `(X, rcond=1e-15)` | (유사역행렬, 특이값) — 특이값이 최댓값×rcond 이하인 방향은 버린다(완전 공선에서도 최소 노름 해). |
| [`constant_info`](#eqnstatsconstant_info) | `(X)` | (상수항 수 0\|1, 상수열 위치 또는 None). 명시 상수열이 없으면 암묵적 상수(예: 계절 더미 합 = 1)도 찾는다. |
| [`newey_west_lags`](#eqnstatsnewey_west_lags) | `(n)` | Newey-West 고정 대역폭 규칙 ⌊4·(n/100)^(2/9)⌋ — cov='hac'의 기본 시차. |
| [`normalize_cov_type`](#eqnstatsnormalize_cov_type) | `(cov_type)` | 공분산 이름을 표준 이름으로 — None·'nonrobust' → 'nonrobust', 'white' → 'hc1', 대소문자 무시. |
| [`TestResult`](#eqnstatstestresult) | `클래스(name, statistic, pvalue, null='', rows=<factory>, info=<factory>, details=<factory>, table=None, notes=<factory>, graph=None, data=None)` | 검정 결과. |
| [`breusch_godfrey`](#eqnstatsbreusch_godfrey) | `(resid, X, lags=2)` | 계열상관 LM 검정(Breusch-Godfrey) — 잔차를 X와 잔차 시차(표본 앞은 0)에 회귀, LM = n·R². |
| [`ljung_box`](#eqnstatsljung_box) | `(resid, lags=None, model_df=0)` | Ljung-Box Q 검정 — 시차별 자기상관·Q·p값 표 포함. 기본 시차 min(10, n/5), model_df는 자유도에서 뺄 수. |
| [`white`](#eqnstatswhite) | `(resid, X, cross=True)` | White 이분산 검정 — 잔차²를 회귀변수·제곱(cross=True면 교차곱까지)에 회귀, LM = n·R². |
| [`breusch_pagan`](#eqnstatsbreusch_pagan) | `(resid, X)` | Breusch-Pagan-Godfrey 이분산 검정 — LM = n·R²(Koenker), 원래 형태(설명 제곱합/2)도 함께. |
| [`arch_lm`](#eqnstatsarch_lm) | `(resid, lags=1)` | ARCH LM 검정 — 잔차²를 상수와 잔차² 시차에 회귀, LM = (n − 시차)·R². |
| [`jarque_bera`](#eqnstatsjarque_bera) | `(resid)` | Jarque-Bera 정규성 검정 — JB = n/6·(왜도² + (첨도 − 3)²/4). |
| [`reset`](#eqnstatsreset) | `(y, X, fitted, terms=1)` | Ramsey RESET — 적합값의 2~(terms+1)제곱을 더한 회귀에서 추가 항 계수 = 0의 F·LR. |
| [`wald`](#eqnstatswald) | `(params, cov, restrictions, df_resid=None, labels=None)` | Wald 계수 제약 검정 — params·cov는 계수 순서(c(1), c(2), …)대로, restrictions는 "c(2) = 2" 같은 글자. |
| [`wald_linear`](#eqnstatswald_linear) | `(params, cov, R, q, df_resid=None)` | H₀: R·b = q의 Wald 통계 — (F, F p값, χ², χ² p값, 제약 수). F 자유도는 (제약 수, df_resid). |
| [`parse_restrictions`](#eqnstatsparse_restrictions) | `(restrictions, n_coef)` | 제약 글자 → (R, q). c(n)은 1부터 센다. 숫자·c(n)·+−×÷만 읽는다(허용 목록 문법). |
| [`chow`](#eqnstatschow) | `(y, X, split, label=None)` | Chow 구조변화 검정 — split = 둘째 구간이 시작하는 행 위치(0부터). |
| [`recursive`](#eqnstatsrecursive) | `(y, X, alpha=0.95)` | 재귀 잔차·재귀 계수·CUSUM과 신뢰 경계(Brown-Durbin-Evans) — 처음 k개 관측치로 시작해 한 기씩 늘린다. |
| [`cusum`](#eqnstatscusum) | `(y, X, index=None, alpha=0.95)` | CUSUM 안정성 검정 — 누적 재귀 잔차가 경계(5%: ±0.948·[√(n−k) + 2(t−k)/√(n−k)])를 벗어나는가. |
| [`nested`](#eqnstatsnested) | `(y, X_small, X_big, weights=None, name='변수 추가 검정', null='', labels_added=None)` | 작은 식(X_small) ⊂ 큰 식(X_big)의 최소제곱 비교 — 누락·불필요 변수 검정의 공통 계산(F·LR). |
| [`adf`](#eqnstatsadf) | `(x, trend='c', lags=None, ic='bic', maxlag=None, name=None)` | ADF 단위근 검정 — lags=None이면 ic('bic'·'aic'·'t-stat')로 0~maxlag 중에서 고른다. trend 'n'·'c'·'ct'. |
| [`kpss`](#eqnstatskpss) | `(x, trend='c', lags='auto', name=None)` | KPSS 정상성 검정 — lags: 'auto'(Hobijn 등 1998) · 'legacy' · 정수. p값은 표 보간(0.01~0.10). |
| [`engle_granger`](#eqnstatsengle_granger) | `(y, X, trend='c', lags=None, ic='bic', maxlag=None, names=None)` | Engle-Granger 공적분 검정 — y를 X(+결정항)에 회귀한 잔차의 ADF(p값·임계값은 변수 수 반영). |
| [`johansen`](#eqnstatsjohansen) | `(Y, det=0, lags=1, names=None)` | Johansen 공적분 순위 검정(트레이스·최대 고유값). det: −1 없음 · 0 상수 · 1 상수 + 추세, lags = 차분 시차. |
| [`mackinnon_p`](#eqnstatsmackinnon_p) | `(stat, trend='c', n_vars=1)` | ADF·Engle-Granger 통계량의 근사 p값(MacKinnon 1994). n_vars: 공적분 회귀의 변수 수(ADF는 1). |
| [`mackinnon_crit`](#eqnstatsmackinnon_crit) | `(n_vars=1, trend='c', nobs=inf)` | 1%·5%·10% 임계값(MacKinnon 2010 반응곡면). |
| [`forecast_evaluate`](#eqnstatsforecast_evaluate) | `(actual, forecast)` | 예측 오차 지표 — RMSE·MAE·MAPE·Theil U1·MSE 분해(편의·분산·공분산)·Theil U2. |
| [`forecast_table`](#eqnstatsforecast_table) | `(actual, forecasts)` | 여러 예측의 지표 표 — forecasts: {이름: 예측 Series·배열}. 예측마다 따로 공통 기간을 맞춘다. |
| [`diebold_mariano`](#eqnstatsdiebold_mariano) | `(actual, f1, f2, h=1, loss='squared', harvey=True)` | Diebold-Mariano 검정 — 두 예측의 기대 손실이 같은가(HLN 작은 표본 보정·t 분포, 통계량 음수면 첫 예측이 더 정확). |

### eqn.stats.Results

`Results(method, params, y, fitted, df_resid, cov, bread=None, G=None, df_model=nan, k_constant=0, rank=None, wresid=None, weights=None, cov_text=None)`

추정 결과. params·bse·tvalues·pvalues는 pandas Series, cov_params()는 DataFrame.

공분산은 cov_type으로 고른다: 'nonrobust'(기본) · 'hc0'~'hc3' · 'white'(=hc1) · 'hac'(Newey-West).  
t·p값은 언제나 t 분포(자유도 df_resid)로 계산한다.  

### eqn.stats.ols

`ols(y, X)`

최소제곱 — y(Series)를 X(DataFrame, 열 = 회귀변수, 상수항 열 포함)에 회귀. 유사역행렬(SVD)로 푼다.

**돌려주는 것**

Results — params · bse · tvalues · pvalues(Series) · resid · fittedvalues · rsquared · rsquared_adj · ssr · llf · aic · bic ·  
fvalue · f_pvalue · cov_params() · set_cov(cov_type, lags)  

**예**

<!-- skip -->
```python
rng = np.random.default_rng(0)
x = rng.normal(size=100)
X = pd.DataFrame({"const": 1.0, "x": x})
y = pd.Series(1 + 2 * x + rng.normal(size=100))
r = eqn.stats.ols(y, X)
r.params.round(3).to_dict()
# {'const': 0.945, 'x': 2.055}
round(r.rsquared, 4), int(r.nobs)
# (0.8111, 100)
```

### eqn.stats.wls

`wls(y, X, w)`

가중 최소제곱 — Σ wₜeₜ² 최소(w ∝ 1/분산). resid·fittedvalues는 가중 전 값, ssr·R²·F·강건 공분산은 가중 잔차로.

**예**

<!-- skip -->
```python
rng = np.random.default_rng(0)
x = rng.normal(size=100)
X = pd.DataFrame({"const": 1.0, "x": x})
y = pd.Series(1 + 2 * x + rng.normal(size=100))
r = eqn.stats.wls(y, X, np.ones(100))
r.params.round(3).to_dict() == eqn.stats.ols(y, X).params.round(3).to_dict()
# True
```

### eqn.stats.tsls

`tsls(y, X, Z)`

2단계 최소제곱 — Z는 도구변수(외생 회귀변수 포함). 두 단계 모두 유사역행렬로 푼다(조건수가 제곱되지 않는다).

**예**

<!-- skip -->
```python
rng = np.random.default_rng(0)
x = rng.normal(size=100)
X = pd.DataFrame({"const": 1.0, "x": x})
y = pd.Series(1 + 2 * x + rng.normal(size=100))
Z = pd.DataFrame({"const": 1.0, "z": x + rng.normal(scale=0.1, size=100)})
round(float(eqn.stats.tsls(y, X, Z).params["x"]), 2)
# 2.06
```

### eqn.stats.gmm

`gmm(y, X, Z, weight='white', lags=None, iterate=False, maxiter=500, tol=1e-10)`

선형 GMM — 모멘트 E[zₜ(yₜ − xₜb)] = 0. 1단계 TSLS 잔차로 가중행렬 W = S⁻¹을 만들어 다시 추정하고(2단계), iterate=True면 W를 고쳐 가며 반복한다. weight: 'white' · 'hac'(Bartlett, lags). J 통계량(Hansen)은 extra에.

**예**

<!-- skip -->
```python
rng = np.random.default_rng(0)
x = rng.normal(size=100)
X = pd.DataFrame({"const": 1.0, "x": x})
y = pd.Series(1 + 2 * x + rng.normal(size=100))
Z = pd.DataFrame({"const": 1.0, "z1": x + rng.normal(scale=0.1, size=100), "z2": x ** 3})
r = eqn.stats.gmm(y, X, Z)
round(float(r.params["x"]), 1), sorted(k for k in r.extra if k.startswith("j_"))
# (2.0, ['j_df', 'j_pvalue', 'j_statistic'])
```

### eqn.stats.liml

`liml(y, X, Z, exog=None)`

제한정보 최우(LIML, k-class) — b = [Xᵀ(I − κM_Z)X]⁻¹ Xᵀ(I − κM_Z)y, κ는 최소 고윳값. exog로 외생 회귀변수를 표시한다.

**예**

<!-- skip -->
```python
rng = np.random.default_rng(0)
x = rng.normal(size=100)
X = pd.DataFrame({"const": 1.0, "x": x})
y = pd.Series(1 + 2 * x + rng.normal(size=100))
Z = pd.DataFrame({"const": 1.0, "z": x + rng.normal(scale=0.1, size=100)})
r = eqn.stats.liml(y, X, Z)
round(float(r.params["x"]), 2), round(r.extra["liml_kappa"], 3)
# (2.06, 1.0)
```

### eqn.stats.nls

`nls(y, params, fitted, J)`

비선형 최소제곱의 결과 객체를 만든다 — 해(params)·적합값과 해에서의 기울기 J(관측치 × 계수)로 표준오차를 계산한다.

**예**

<!-- skip -->
```python
rng = np.random.default_rng(0)
x = rng.normal(size=100)
X = pd.DataFrame({"const": 1.0, "x": x})
y = pd.Series(1 + 2 * x + rng.normal(size=100))
b = eqn.stats.ols(y, X).params
r = eqn.stats.nls(y, b, X @ b, X.to_numpy())             # 선형 식이면 OLS와 같다
bool(np.allclose(r.bse, eqn.stats.ols(y, X).bse))
# True
```

### eqn.stats.fixed

`fixed(y, params, fitted)`

고정(외부) 계수의 결과 객체 — 표준오차 없음, 적합도 통계만.

**예**

<!-- skip -->
```python
rng = np.random.default_rng(0)
x = rng.normal(size=100)
X = pd.DataFrame({"const": 1.0, "x": x})
y = pd.Series(1 + 2 * x + rng.normal(size=100))
b = pd.Series({"const": 1.0, "x": 2.0})
r = eqn.stats.fixed(y, b, X @ b)
round(r.rsquared, 3)
# 0.81
```

### eqn.stats.pinv_svd

`pinv_svd(X, rcond=1e-15)`

(유사역행렬, 특이값) — 특이값이 최댓값×rcond 이하인 방향은 버린다(완전 공선에서도 최소 노름 해).

**예**

<!-- skip -->
```python
P, sv = eqn.stats.pinv_svd(np.array([[1.0, 2.0], [2.0, 4.0], [1.0, 2.0]]))
int((sv > 1e-12).sum())                                   # 계수 1(두 열이 비례)
# 1
```

### eqn.stats.constant_info

`constant_info(X)`

(상수항 수 0|1, 상수열 위치 또는 None). 명시 상수열이 없으면 암묵적 상수(예: 계절 더미 합 = 1)도 찾는다.

**예**

<!-- skip -->
```python
eqn.stats.constant_info(np.column_stack([np.ones(5), np.arange(5.0)]))
# (1, 0)
```

### eqn.stats.newey_west_lags

`newey_west_lags(n)`

Newey-West 고정 대역폭 규칙 ⌊4·(n/100)^(2/9)⌋ — cov='hac'의 기본 시차.

**예**

<!-- skip -->
```python
eqn.stats.newey_west_lags(200)
# 4
```

### eqn.stats.normalize_cov_type

`normalize_cov_type(cov_type)`

공분산 이름을 표준 이름으로 — None·'nonrobust' → 'nonrobust', 'white' → 'hc1', 대소문자 무시.

**오류**

- `ValueError`: 모르는 이름

**예**

<!-- skip -->
```python
eqn.stats.normalize_cov_type("White"), eqn.stats.normalize_cov_type(None)
# ('hc1', 'nonrobust')
```

### eqn.stats.TestResult

`TestResult(name, statistic, pvalue, null='', rows=<factory>, info=<factory>, details=<factory>, table=None, notes=<factory>, graph=None, data=None)`

검정 결과.

statistic·pvalue는 대표 통계량(예: LM, ADF t)과 p값, rows는 함께 보이는 보조 통계(이름 → 값),  
info는 머리에 보이는 설명(결정항·시차 선택·표본 등), details는 프로그램이 쓰는 값(lags·nobs·crit 등),  
table은 검정에 딸린 표(예: 시차별 Q, 순위별 Johansen),  
data는 보이지는 않는 뒷받침 자료(예: CUSUM 기간별 값), graph는 함께 보이는 그래프.  

### eqn.stats.breusch_godfrey

`breusch_godfrey(resid, X, lags=2)`

계열상관 LM 검정(Breusch-Godfrey) — 잔차를 X와 잔차 시차(표본 앞은 0)에 회귀, LM = n·R².

**예**

<!-- skip -->
```python
rng = np.random.default_rng(0)
x = rng.normal(size=100)
X = pd.DataFrame({"const": 1.0, "x": x})
y = pd.Series(1 + 2 * x + rng.normal(size=100))
r = eqn.stats.ols(y, X)
eqn.stats.breusch_godfrey(r.resid, X, lags=2).reject(0.05)
# False
```

### eqn.stats.ljung_box

`ljung_box(resid, lags=None, model_df=0)`

Ljung-Box Q 검정 — 시차별 자기상관·Q·p값 표 포함. 기본 시차 min(10, n/5), model_df는 자유도에서 뺄 수.

**예**

<!-- skip -->
```python
rng = np.random.default_rng(0)
x = rng.normal(size=100)
X = pd.DataFrame({"const": 1.0, "x": x})
y = pd.Series(1 + 2 * x + rng.normal(size=100))
r = eqn.stats.ols(y, X)
q = eqn.stats.ljung_box(r.resid, 5)
len(q.table), q.reject(0.05)
# (5, False)
```

### eqn.stats.white

`white(resid, X, cross=True)`

White 이분산 검정 — 잔차²를 회귀변수·제곱(cross=True면 교차곱까지)에 회귀, LM = n·R².

**예**

<!-- skip -->
```python
rng = np.random.default_rng(0)
x = rng.normal(size=100)
X = pd.DataFrame({"const": 1.0, "x": x})
y = pd.Series(1 + 2 * x + rng.normal(size=100))
r = eqn.stats.ols(y, X)
eqn.stats.white(r.resid, X).reject(0.05)
# False
```

### eqn.stats.breusch_pagan

`breusch_pagan(resid, X)`

Breusch-Pagan-Godfrey 이분산 검정 — LM = n·R²(Koenker), 원래 형태(설명 제곱합/2)도 함께.

**예**

<!-- skip -->
```python
rng = np.random.default_rng(0)
x = rng.normal(size=100)
X = pd.DataFrame({"const": 1.0, "x": x})
y = pd.Series(1 + 2 * x + rng.normal(size=100))
r = eqn.stats.ols(y, X)
eqn.stats.breusch_pagan(r.resid, X).reject(0.05)
# False
```

### eqn.stats.arch_lm

`arch_lm(resid, lags=1)`

ARCH LM 검정 — 잔차²를 상수와 잔차² 시차에 회귀, LM = (n − 시차)·R².

**예**

<!-- skip -->
```python
rng = np.random.default_rng(0)
x = rng.normal(size=100)
X = pd.DataFrame({"const": 1.0, "x": x})
y = pd.Series(1 + 2 * x + rng.normal(size=100))
r = eqn.stats.ols(y, X)
eqn.stats.arch_lm(r.resid, 2).reject(0.05)
# False
```

### eqn.stats.jarque_bera

`jarque_bera(resid)`

Jarque-Bera 정규성 검정 — JB = n/6·(왜도² + (첨도 − 3)²/4).

**예**

<!-- skip -->
```python
rng = np.random.default_rng(0)
x = rng.normal(size=100)
X = pd.DataFrame({"const": 1.0, "x": x})
y = pd.Series(1 + 2 * x + rng.normal(size=100))
r = eqn.stats.ols(y, X)
eqn.stats.jarque_bera(r.resid).reject(0.05)
# False
```

### eqn.stats.reset

`reset(y, X, fitted, terms=1)`

Ramsey RESET — 적합값의 2~(terms+1)제곱을 더한 회귀에서 추가 항 계수 = 0의 F·LR.

**예**

<!-- skip -->
```python
rng = np.random.default_rng(0)
x = rng.normal(size=100)
X = pd.DataFrame({"const": 1.0, "x": x})
y = pd.Series(1 + 2 * x + rng.normal(size=100))
r = eqn.stats.ols(y, X)
eqn.stats.reset(y, X, r.fittedvalues, 2).reject(0.05)
# False
```

### eqn.stats.wald

`wald(params, cov, restrictions, df_resid=None, labels=None)`

Wald 계수 제약 검정 — params·cov는 계수 순서(c(1), c(2), …)대로, restrictions는 "c(2) = 2" 같은 글자.

df_resid를 주면 F 통계(작은 표본), 없으면 χ².  

**예**

<!-- skip -->
```python
rng = np.random.default_rng(0)
x = rng.normal(size=100)
X = pd.DataFrame({"const": 1.0, "x": x})
y = pd.Series(1 + 2 * x + rng.normal(size=100))
r = eqn.stats.ols(y, X)
eqn.stats.wald(r.params, r.cov_params(), ["c(2) = 2"], df_resid=r.df_resid).reject(0.05)
# False
```

### eqn.stats.wald_linear

`wald_linear(params, cov, R, q, df_resid=None)`

H₀: R·b = q의 Wald 통계 — (F, F p값, χ², χ² p값, 제약 수). F 자유도는 (제약 수, df_resid).

**오류**

- `ValueError`: 제약끼리 겹치거나 모순(R의 계수 < 행 수)

**예**

<!-- skip -->
```python
rng = np.random.default_rng(0)
x = rng.normal(size=100)
X = pd.DataFrame({"const": 1.0, "x": x})
y = pd.Series(1 + 2 * x + rng.normal(size=100))
r = eqn.stats.ols(y, X)
F, pF, chi2, pchi, q = eqn.stats.wald_linear(r.params, r.cov_params(), [[0, 1]], [2.0], r.df_resid)
q, bool(pF > 0.05)
# (1, True)
```

### eqn.stats.parse_restrictions

`parse_restrictions(restrictions, n_coef)`

제약 글자 → (R, q). c(n)은 1부터 센다. 숫자·c(n)·+−×÷만 읽는다(허용 목록 문법).

**예**

<!-- skip -->
```python
R, q = eqn.stats.parse_restrictions(["c(2) + c(3) = 1", "c(1) = 0"], 3)
R.tolist(), q.tolist()
# ([[0.0, 1.0, 1.0], [1.0, 0.0, 0.0]], [1.0, 0.0])
```

### eqn.stats.chow

`chow(y, X, split, label=None)`

Chow 구조변화 검정 — split = 둘째 구간이 시작하는 행 위치(0부터).

**예**

<!-- skip -->
```python
rng = np.random.default_rng(0)
x = rng.normal(size=100)
X = pd.DataFrame({"const": 1.0, "x": x})
y = pd.Series(1 + 2 * x + rng.normal(size=100))
eqn.stats.chow(y, X, 50).reject(0.05)
# False
```

### eqn.stats.recursive

`recursive(y, X, alpha=0.95)`

재귀 잔차·재귀 계수·CUSUM과 신뢰 경계(Brown-Durbin-Evans) — 처음 k개 관측치로 시작해 한 기씩 늘린다.

각 시점의 계수는 그때까지의 관측치로 직접 최소제곱한다(갱신 공식의 반올림 누적을 피한다).  

**예**

<!-- skip -->
```python
rng = np.random.default_rng(0)
x = rng.normal(size=100)
X = pd.DataFrame({"const": 1.0, "x": x})
y = pd.Series(1 + 2 * x + rng.normal(size=100))
out = eqn.stats.recursive(y.to_numpy(), X.to_numpy())
sorted(out)
# ['bound', 'cusum', 'rparams', 'rresid', 'standardized', 'start']
```

### eqn.stats.cusum

`cusum(y, X, index=None, alpha=0.95)`

CUSUM 안정성 검정 — 누적 재귀 잔차가 경계(5%: ±0.948·[√(n−k) + 2(t−k)/√(n−k)])를 벗어나는가.

통계량은 경계 대비 최대 비율(1보다 작으면 안정).  

**예**

<!-- skip -->
```python
rng = np.random.default_rng(0)
x = rng.normal(size=100)
X = pd.DataFrame({"const": 1.0, "x": x})
y = pd.Series(1 + 2 * x + rng.normal(size=100))
bool(eqn.stats.cusum(y.to_numpy(), X.to_numpy()).statistic < 1)
# True
```

### eqn.stats.nested

`nested(y, X_small, X_big, weights=None, name='변수 추가 검정', null='', labels_added=None)`

작은 식(X_small) ⊂ 큰 식(X_big)의 최소제곱 비교 — 누락·불필요 변수 검정의 공통 계산(F·LR).

**예**

<!-- skip -->
```python
rng = np.random.default_rng(0)
x = rng.normal(size=100)
X = pd.DataFrame({"const": 1.0, "x": x})
y = pd.Series(1 + 2 * x + rng.normal(size=100))
big = X.assign(z=rng.normal(size=100))
eqn.stats.nested(y, X, big).reject(0.05)
# False
```

### eqn.stats.adf

`adf(x, trend='c', lags=None, ic='bic', maxlag=None, name=None)`

ADF 단위근 검정 — lags=None이면 ic('bic'·'aic'·'t-stat')로 0~maxlag 중에서 고른다. trend 'n'·'c'·'ct'.

**예**

<!-- skip -->
```python
rng = np.random.default_rng(1)
eqn.stats.adf(np.cumsum(rng.normal(size=200))).pvalue > 0.05      # 랜덤워크
# True
eqn.stats.adf(rng.normal(size=200)).pvalue < 0.01                 # 백색잡음
# True
```

### eqn.stats.kpss

`kpss(x, trend='c', lags='auto', name=None)`

KPSS 정상성 검정 — lags: 'auto'(Hobijn 등 1998) · 'legacy' · 정수. p값은 표 보간(0.01~0.10).

**예**

<!-- skip -->
```python
rng = np.random.default_rng(1)
eqn.stats.kpss(rng.normal(size=200)).pvalue >= 0.05
# True
```

### eqn.stats.engle_granger

`engle_granger(y, X, trend='c', lags=None, ic='bic', maxlag=None, names=None)`

Engle-Granger 공적분 검정 — y를 X(+결정항)에 회귀한 잔차의 ADF(p값·임계값은 변수 수 반영).

**예**

<!-- skip -->
```python
rng = np.random.default_rng(1)
x = np.cumsum(rng.normal(size=200))
eqn.stats.engle_granger(2 * x + rng.normal(size=200), x).pvalue < 0.01
# True
```

### eqn.stats.johansen

`johansen(Y, det=0, lags=1, names=None)`

Johansen 공적분 순위 검정(트레이스·최대 고유값). det: −1 없음 · 0 상수 · 1 상수 + 추세, lags = 차분 시차.

임계값은 MacKinnon-Haug-Michelis(1999), 변수 12개까지.  

**예**

<!-- skip -->
```python
rng = np.random.default_rng(1)
x = np.cumsum(rng.normal(size=300))
Y = np.column_stack([x, x + rng.normal(size=300)])
eqn.stats.johansen(Y).rows["트레이스 기준 순위(5%)"]
# 1
```

### eqn.stats.mackinnon_p

`mackinnon_p(stat, trend='c', n_vars=1)`

ADF·Engle-Granger 통계량의 근사 p값(MacKinnon 1994). n_vars: 공적분 회귀의 변수 수(ADF는 1).

**예**

<!-- skip -->
```python
round(eqn.stats.mackinnon_p(-2.86, "c"), 2)
# 0.05
```

### eqn.stats.mackinnon_crit

`mackinnon_crit(n_vars=1, trend='c', nobs=inf)`

1%·5%·10% 임계값(MacKinnon 2010 반응곡면).

**예**

<!-- skip -->
```python
eqn.stats.mackinnon_crit(1, "c").round(2).tolist()
# [-3.43, -2.86, -2.57]
```

### eqn.stats.forecast_evaluate

`forecast_evaluate(actual, forecast)`

예측 오차 지표 — RMSE·MAE·MAPE·Theil U1·MSE 분해(편의·분산·공분산)·Theil U2.

**예**

<!-- skip -->
```python
a = pd.Series([1.0, 2.0, 3.0, 4.0])
e = eqn.stats.forecast_evaluate(a, a + 0.1)
round(float(e["RMSE"]), 3), round(float(e["편의 비중"]), 3)
# (0.1, 1.0)
```

### eqn.stats.forecast_table

`forecast_table(actual, forecasts)`

여러 예측의 지표 표 — forecasts: {이름: 예측 Series·배열}. 예측마다 따로 공통 기간을 맞춘다.

**예**

<!-- skip -->
```python
a = pd.Series([1.0, 2.0, 3.0, 4.0])
t = eqn.stats.forecast_table(a, {"f1": a + 0.1, "f2": a * 1.1})
list(t.index)
# ['f1', 'f2']
```

### eqn.stats.diebold_mariano

`diebold_mariano(actual, f1, f2, h=1, loss='squared', harvey=True)`

Diebold-Mariano 검정 — 두 예측의 기대 손실이 같은가(HLN 작은 표본 보정·t 분포, 통계량 음수면 첫 예측이 더 정확).

손실 차이의 분산이 0이면(같은 예측) 통계량은 NA와 설명이다.  

**예**

<!-- skip -->
```python
rng = np.random.default_rng(2)
a = pd.Series(rng.normal(size=80))
r = eqn.stats.diebold_mariano(a, a + rng.normal(scale=0.1, size=80), a + rng.normal(size=80))
r.statistic < 0, r.pvalue < 0.01
# (True, True)
```

## 20. 자료 변환 `equion.data.transform`

| 이름 | 서명 | 설명 |
|---|---|---|
| [`ratio`](#transformratio) | `(from_freq, to_freq)` | 높은 주기 하나에 낮은 주기 몇 개(예: 분기 → 연 4, 월 → 분기 3). |
| [`aggregate`](#transformaggregate) | `(s, from_freq, to_freq, how='mean', complete=True)` | 높은 주기 시리즈 → 낮은 주기. how: mean·sum·first·last·max·min. complete=True면 하위 기간이 하나라도 비면 결측. |
| [`expand`](#transformexpand) | `(s, from_freq, to_freq, how='constant')` | 낮은 주기 → 높은 주기(분할 없이): constant(같은 값 반복)·split(값/k)·linear(각 낮은 기간의 마지막 하위 기간에 값을 두고 선형 보간). |
| [`denton`](#transformdenton) | `(y_low, k, indicator=None, conversion='sum', T=None)` | 비례 Denton(Cholette 수정, 1차 차분) — min Σ (xₜ/iₜ − xₜ₋₁/iₜ₋₁)² s.t. Cx = y. |
| [`chow_lin`](#transformchow_lin) | `(y_low, X_high, k, conversion='sum', rho=None)` | Chow-Lin — 높은 주기 x = Xβ + u, u ~ AR(1)(ρ), 낮은 주기 y = Cx. ρ=None이면 최우로 고른다. |
| [`stl`](#transformstl) | `(y, period, seasonal=7, trend=None, low_pass=None, seasonal_deg=1, trend_deg=1, low_pass_deg=1, robust=False, inner=None, outer=None)` | STL 분해 → (계절, 추세, 잔차, 강건 가중치). 창 길이 기본값은 원 알고리즘(Cleveland 등 1990)과 같다. |
| [`classical`](#transformclassical) | `(y, period, model='additive')` | 고전 분해 → (계절, 추세, 잔차). 추세 = 중심 이동평균(짝수 주기는 2×period, 양끝 결측), 계절 = 주기 위치별 평균. |

### transform.ratio

`ratio(from_freq, to_freq)`

높은 주기 하나에 낮은 주기 몇 개(예: 분기 → 연 4, 월 → 분기 3).

**예**

<!-- skip -->
```python
from equion.data import transform
transform.ratio("Q", "A"), transform.ratio("M", "Q")
# (4, 3)
```

### transform.aggregate

`aggregate(s, from_freq, to_freq, how='mean', complete=True)`

높은 주기 시리즈 → 낮은 주기. how: mean·sum·first·last·max·min. complete=True면 하위 기간이 하나라도 비면 결측.

**예**

<!-- skip -->
```python
from equion.data import transform
wf = eqn.datasets.load("toy_q")
a = transform.aggregate(wf["Y"], "Q", "A", "sum")
len(a), round(float(a.iloc[0]), 1) == round(float(wf["Y"].iloc[:4].sum()), 1)
# (50, True)
```

### transform.expand

`expand(s, from_freq, to_freq, how='constant')`

낮은 주기 → 높은 주기(분할 없이): constant(같은 값 반복)·split(값/k)·linear(각 낮은 기간의 마지막 하위 기간에 값을 두고 선형 보간).

**예**

<!-- skip -->
```python
from equion.data import transform
wa = eqn.datasets.load("toy_a")
q = transform.expand(wa["Y"], "A", "Q", "split")
round(float(q.iloc[:4].sum()), 3) == round(float(wa["Y"].iloc[0]), 3)
# True
```

### transform.denton

`denton(y_low, k, indicator=None, conversion='sum', T=None)`

비례 Denton(Cholette 수정, 1차 차분) — min Σ (xₜ/iₜ − xₜ₋₁/iₜ₋₁)² s.t. Cx = y.

indicator가 없으면 iₜ = 1(가법 = 비례). T(높은 주기 길이)가 n·k보다 길면 뒤를 지표 흐름대로 외삽한다.  
conversion: 'sum' · 'average' · 'first' · 'last'(낮은 주기 값이 하위 기간의 무엇인가).  

**예**

<!-- skip -->
```python
from equion.data import transform
x = transform.denton(np.array([10.0, 12.0]), 4)
x.reshape(2, 4).sum(axis=1).round(10).tolist()
# [10.0, 12.0]
```

### transform.chow_lin

`chow_lin(y_low, X_high, k, conversion='sum', rho=None)`

Chow-Lin — 높은 주기 x = Xβ + u, u ~ AR(1)(ρ), 낮은 주기 y = Cx. ρ=None이면 최우로 고른다.

돌려주는 dict: x(제약 Cx = y를 정확히 만족) · beta · rho · loglik.  

**예**

<!-- skip -->
```python
from equion.data import transform
rng = np.random.default_rng(0)
ind = 10 + np.cumsum(rng.normal(size=12))
y = ind.reshape(3, 4).sum(axis=1) * 1.5
r = transform.chow_lin(y, np.column_stack([np.ones(12), ind]), 4)
bool(np.allclose(r["x"].reshape(3, 4).sum(axis=1), y))
# True
```

### transform.stl

`stl(y, period, seasonal=7, trend=None, low_pass=None, seasonal_deg=1, trend_deg=1, low_pass_deg=1, robust=False, inner=None, outer=None)`

STL 분해 → (계절, 추세, 잔차, 강건 가중치). 창 길이 기본값은 원 알고리즘(Cleveland 등 1990)과 같다.

trend = 1.5·period/(1 − 1.5/seasonal)를 올림한 홀수, low_pass = period + 1을 홀수로. robust=True면 강건 반복.  

**예**

<!-- skip -->
```python
from equion.data import transform
t = np.arange(48.0)
y = t + 3 * np.tile([1.0, -1.0, 2.0, -2.0], 12)
s, tr, r, w = transform.stl(y, 4)
bool(np.allclose(s + tr + r, y)), round(float(s[:4].round(1).sum()), 1)
# (True, 0.0)
```

### transform.classical

`classical(y, period, model='additive')`

고전 분해 → (계절, 추세, 잔차). 추세 = 중심 이동평균(짝수 주기는 2×period, 양끝 결측), 계절 = 주기 위치별 평균.

model: 'additive'(계절 합 0) · 'multiplicative'(계절 평균 1).  

**예**

<!-- skip -->
```python
from equion.data import transform
y = np.arange(24.0) + np.tile([1.0, -1.0, 2.0, -2.0], 6)
s, tr, r = transform.classical(y, 4)
s[:4].round(6).tolist()
# [1.0, -1.0, 2.0, -2.0]
```

## 21. 프로젝트 `eqn.project(…)`

| 이름 | 서명 | 설명 |
|---|---|---|
| [`open`](#projectopen) | `(path='.')` | 프로젝트 폴더(또는 그 안의 equion.toml)를 연다 — `eqn.project(path)`와 같다. |
| [`create`](#projectcreate) | `(path, template='desk', force=False)` | 예제 프로젝트를 만들고 연다 — 명령줄 `equion new 폴더 --template desk`와 같다. |
| `name` | `속성` | 프로젝트 이름([project] name, 없으면 폴더 이름). |
| `root` | `속성` | 프로젝트 폴더의 절대 경로. |
| `blocks` | `속성` | 블록 이름 목록(설정 파일 순서). |
| `models` | `속성` | 모형 이름 목록(설정 파일 순서). |
| [`workfile`](#projectworkfile) | `속성` | 프로젝트 자료의 워크파일 — 자료 정의를 쓰면 지금 자료 회차, 아니면 [data] file(처음 쓸 때 연다). |
| `vintage` | `속성` | 지금 자료 회차(equion.toml [data] vintage) — 자료 파일 하나를 쓰면 None. |
| [`data_build`](#projectdata_build) | `(use=False, inbox=None, ask=None, who=None, command=None)` | 자료 만들기 — 원자료를 정의(series.toml·derived.txt)대로 읽어 새 자료 회차(work/data/<회차>/)를 만든다. |
| [`data_inbox`](#projectdata_inbox) | `()` | 받은 상자(DATA/raw/inbox/)의 파일마다 짝지을 출처와 틀 검사 — 미리보기(아무것도 바꾸지 않는다). InboxItem 목록. |
| [`data_use`](#projectdata_use) | `(vid, who=None, command=None)` | 이 회차로 바꾸기 — equion.toml의 [data] vintage를 고치고(주석·순서는 그대로) 자료를 다시 연다. 이전 회차를 돌려준다. |
| [`data_list`](#projectdata_list) | `()` | 자료 회차 목록(만든 때 순) — {id, created, span, n_series, current}. |
| [`data_diff`](#projectdata_diff) | `(a=None, b=None)` | 두 자료 회차의 차이 — 새·없어진 시리즈, 시리즈마다 새 기간과 개정(기간·크기). |
| [`data_impact`](#projectdata_impact) | `(a=None, b=None)` | 회차를 바꾸면 영향받는 것 — 바뀐 시리즈를 쓰는 식(부품)과 모형. 다시 계산은 하지 않는다(사람이 시킬 때만). |
| [`data_add`](#projectdata_add) | `(path, source=None, as_name=None, note=None, who=None, command=None)` | 원자료 넣기 — 파일을 DATA/raw/에 복사한다(받은 그대로, 같은 이름이면 날짜를 붙여 나란히). source를 주면 그 출처가 이 파일을 읽도록 series.toml을 고치되, 먼저 그 출처의 불러오기 틀로 읽어 보고 시리즈가 쓰는 열이 다 있고 주기가 같을 때만 넣고 고친다(틀 검사 — 맞지 않으면 아무것도 바꾸지 않고 `.problems`에 까닭). |
| [`parts`](#projectparts) | `(name=None)` | 부품(식·항등식) 목록 — name이 없으면 전부, 블록 이름이면 그 블록, 모형 이름이면 조립된 식들. |
| [`part`](#projectpart) | `(pid)` | 부품 하나 — `블록:목표`(대소문자 무시). |
| [`used_by`](#projectused_by) | `(name)` | 쓰는 곳 — 블록이나 부품(`블록:목표`)을 쓰는 모형 목록. 고치기 전에 영향 범위를 본다. |
| [`assemble`](#projectassemble) | `(name=None, swap=None)` | 조립 검사 — 계산 없이 모형(또는 블록)의 구조를 본다: 내생·외생, 겹친 목표, 모르는 변수, 외생 자료 끝, 블록 사이 연결, 풀이 블록. |
| [`adopted`](#projectadopted) | `속성` | 채택표(EQUATIONS/adopted.toml) — {부품: est:기록}. 모형은 이 기록의 계수로 푼다(D35). |
| [`model`](#projectmodel) | `(name=None, swap=None)` | 모형(또는 블록)을 조립해 워크파일 모델 객체로 — 추정식은 지금 자료로 추정하고 항등식은 그대로 넣는다. |
| [`span`](#projectspan) | `(spec)` | 구간 표기 → (시작, 끝) 라벨 — '2005Q1:2019Q4' · '2005Q1:last' · 'last-39:last' · 'next:12'. last는 자료의 마지막 값이 있는 기간. |
| [`hs`](#projecths) | `(name=None, start=None, end=None, mode=None, swap=None, record=False, vs=None, as_name=None, who=None, command=None, **opts)` | 과거 재현(HS) — 모형이나 블록을 풀어 실측과 견준다. 블록이면 그 블록만 풀고 나머지 변수는 실측(블록 HS). |
| [`est`](#projectest) | `(target, method=None, smpl=None, as_name=None, part=None, sim=False, cov=None, who=None, command=None)` | 식 하나를 추정해 작업 기록(`work/est/<이름>/`)을 남긴다 — 부품(블록 파일의 그 줄) 또는 식 글자(후보). |
| [`adopt`](#projectadopt) | `(record, part=None, who=None, command=None)` | 추정 기록을 그 부품의 채택 계수로 — 블록 파일의 그 줄을 기록의 식으로 바꾸고(다르면) 채택표 `EQUATIONS/adopted.toml`을 고친다(주석·순서 그대로). 바뀜 기록에 남고, 그 뒤 모형은 이 계수로 푼다(다시 추정하지 않음). |
| [`compare`](#projectcompare) | `(*records, target=None, part=None)` | 기록 비교 — 추정 기록이면 식·표본·적합 통계·진단·기준·단독 모의 표(종속변수·표본이 다르면 경고), HS 기록이면 변수별 RMSPE. |
| [`replay`](#projectreplay) | `(record, as_name=None, who=None, command=None)` | HS 기록을 그때 그대로 다시 — 기록의 조립 명세(식 글자·계수·자료 회차·구간·방식)로 푼다. 지금 파일과 무관하고, 원래 기록의 풀린 값과 견주어(`.meta['replay']` — same · max_abs_diff) 새 기록을 남긴다. |
| [`sim`](#projectsim) | `(scenario='base', model=None, range=None, vintage=None, vs=None, as_name=None, mode=None, who=None, command=None)` | 전망·시나리오 — 가정 세트(`ASSUMPTIONS/이름.csv`, 빈 외생은 `[forecast] fill`)·보정항(`ADDFACTORS/이름.toml`)·시나리오 (`SCENARIOS/이름.toml`)로 풀고 작업 기록(`work/sim/<이름>/`)을 남긴다. 시나리오면 같은 가정·보정항의 기준선도 풀어 차이를 적는다. |
| [`an`](#projectan) | `(analysis, target, smpl=None, as_name=None, note=None, who=None, command=None, **options)` | 분석 하나 — 등록부(`equion.registry`)의 분석을 돌려 기록(`work/an/<이름>/` — 표 CSV·차트 CSV·카드 summary.md)을 남긴다. |
| [`keep`](#projectkeep) | `(record, as_name=None, replace=False, who=None, command=None)` | 분석 기록을 남긴다 — 만드는 분석(계절조정·파생)은 정의(`series.toml`·`derived.txt`, `made_by` = 기록)로, 부품을 내는 분석(ECM·VAR·VECM·시스템)은 식 후보(est: 기록 — 계수 그대로)로. 정의를 고치면 바뀜 기록에 남고, 자료에는 `data build`로 들어간다. |
| [`note_run`](#projectnote_run) | `(note, block=None, stale=False, force=False, who=None, command=None)` | 노트의 ```` ```equion ```` 블록을 실행해 블록 아래 결과 구역을 채운다(블록마다 새 기록). 블록은 등록부의 계산·보기 명령만 부를 수 있고, 손으로 고친 구역은 force일 때만 덮는다. Python 블록은 block으로 고를 때만 돈다. |
| [`note_check`](#projectnote_check) | `(note)` | 노트 검사(실행하지 않고) — 블록마다 실행 안 함 · 없는 기록 · 낡음(자료·정의가 바뀜) · 손으로 고침 · 허용 안 된 명령. |
| [`report_new`](#projectreport_new) | `(name, title=None, from_report=None, exist_ok=False, who=None, command=None)` | 새 보고서(`reports/이름.md`) — 틀(제목·날짜·자료 회차·모형). from_report면 지난 보고서를 복사하고 구역마다 바꿔 낄 기록을 제안한다. exist_ok면 이미 있는 보고서는 그대로 둔다(`.exists` — 스크립트를 같은 회차로 다시 돌릴 때 글을 지키려고). |
| [`report_add`](#projectreport_add) | `(report, record, rows=None, show='level', annual=False, digits=None, title=None, chart=False, under=None, key=None, force=False, who=None, command=None)` | 보고서로 보내기 — 기록의 표(와 차트)를 고른 모양(행·보이기·연간·소수점)으로 보고서에 넣는다. 구역에는 보이지 않는 표시 (기록·보낸 날·자료 회차·모양)가 붙고, 차트 자료는 보고서 옆 `_data/`로 복사한다. |
| [`report_check`](#projectreport_check) | `(report)` | 보고서 검사 — 구역마다 없는 기록 · 더 새 기록(같은 갈래) · 낡음(자료·정의가 바뀜) · 손으로 고침. |
| [`report_update`](#projectreport_update) | `(report, region=None, to=None, dry_run=False, force=False, who=None, command=None)` | 새 기록으로 바꾸기 — 구역을 같은 모양으로 다시 만들어 차이를 보이고 적용한다(기본: 같은 갈래의 가장 새 기록). 손으로 고친 구역은 고친 곳을 차이로 보이고 force일 때만 덮는다. |
| [`reestimate`](#projectreestimate) | `(name=None, adopt='never', who=None, command=None)` | 모형(또는 블록)의 추정식을 블록 파일의 글자 그대로 지금 자료로 다시 추정해 기록을 남기고, 정책에 따라 새 계수를 채택한다 (명령줄 `equion est --adopted [모형] --adopt 정책`, D35). |
| [`propose`](#projectpropose) | `(name=None, title='', why='', parts=None, files=None, previews=(), who=None, command=None)` | 제안을 만든다 — 파일은 바꾸지 않고 "이렇게 바꾸면"을 `work/proposals/<이름>/`에 남긴다(바뀔 내용·까닭·미리 계산한 기록). |
| [`proposals`](#projectproposals) | `()` | 제안 목록(만든 순) — 열림·적용·버림 모두. |
| [`apply_proposal`](#projectapply_proposal) | `(name, force=False, who=None, command=None)` | 제안을 적용한다 — 바꿀 파일을 새 내용으로 쓰고 바뀜 기록에 "제안 … 적용". 만든 뒤 파일이 바뀌었으면(낡음) force일 때만. |
| [`drop_proposal`](#projectdrop_proposal) | `(name, why='', who=None)` | 제안을 버린다 — 파일은 그대로, 제안 기록은 남는다(상태 '버림'). |
| [`export`](#projectexport) | `(records, xlsx)` | 기록(est:· hs:· sim:· data:회차)을 엑셀 한 권으로 — 값·값의 종류·출처 시트. 기록은 남기지 않는다. |
| [`run_script`](#projectrun_script) | `(script, sets=None, from_step=None, dry_run=False, fail_on='failed', name=None, who=None, command=None, echo=None, verbosity=1, python=True)` | Equion 스크립트(`.eqs`)를 실행하고 실행 기록 `work/run/<이름>/`(`run:`)을 남긴다 — 명령줄 `equion run x.eqs`. |
| [`check_script`](#projectcheck_script) | `(script, sets=None)` | 스크립트를 실행 없이 검사 — 문법·명령(허용 목록)·선택지·{이름}·매개변수·부품·모형·시나리오·노트·포함한 파일. |
| [`replay_run`](#projectreplay_run) | `(run, who=None, command=None, echo=None)` | 실행 기록을 그때 그대로 다시 — 정의 사본(defs/)·받은 원자료·같은 스크립트(src/)·매개변수로 프로젝트 사본에서 돌리고 단계마다 기록의 숫자를 견준다(허용오차). 프로젝트는 바꾸지 않고 견준 결과를 새 실행 기록(`replay_of`)으로 남긴다. |
| [`new_script`](#projectnew_script) | `(name, records=None, last=None, title=None, force=False, who=None, command=None)` | 작업 기록의 명령으로 스크립트 초안 `FLOWS/<이름>.eqs`(바뀜 기록에 남는다) — 탐색하며 한 일을 굳힌다. 명령에서 -p·--as·--note·--json은 뺀다(다시 돌려도 이름이 겹치지 않게). 기록이 없으면 빈 틀. |
| [`export_script`](#projectexport_script) | `(script, out=None, force=False)` | 스크립트를 같은 일을 하는 Python 파일로(`eqn.script.session` — 같은 명령·같은 기록) → 프로젝트 기준 경로. |
| `work` | `속성` | 작업 기록 저장소(`work/`) — .records(종류) · .get(이름) · .log() · .mark(…). |
| `history` | `속성` | 바뀜 기록(`work/history/`) — .list() · .get(h0001) · .revert(h0001, who) · .scan(). |
| [`ident`](#projectident) | `(pid, start=None, end=None, tol=1e-06)` | 항등식 단독 검사 — 실측으로 좌변과 우변을 계산해 견준다(추정 없이). |

### Project.open

`open(path='.')`

프로젝트 폴더(또는 그 안의 equion.toml)를 연다 — `eqn.project(path)`와 같다.

**오류**

- `ProjectError`: 설정 파일이 없음·문법 오류·없는 블록 파일 등(문제를 모두 모아서)

**예**

<!-- skip -->
```python
import tempfile, os
d = os.path.join(tempfile.mkdtemp(), "demo")
_ = eqn.Project.create(d)
eqn.Project.open(d).name
# 'demo'
```

### Project.create

`create(path, template='desk', force=False)`

예제 프로젝트를 만들고 연다 — 명령줄 `equion new 폴더 --template desk`와 같다.

예제는 가상 분기 모형이다: 원자료 toy_q·toy_m(DATA/raw/), 자료 정의(DATA/series.toml·derived.txt — 주기 변환·계절조정 예 포함),  
블록 demand(소비·투자·국민소득 항등식)·price(물가)·finance(장기금리·통화), 모형 core·main·main_fixrl.  
첫 자료 회차를 만들어 지금 회차로 정한다(`.created_files`에 만든 파일 목록).  

**매개변수**

- `path`: 만들 폴더(비어 있어야 한다)
- `template`: 'desk'
- `force`: 비어 있지 않은 폴더에도 쓴다(같은 이름 파일을 덮음)

**오류**

- `FileExistsError`: 폴더가 비어 있지 않음 · ValueError: 모르는 template

**예**

<!-- skip -->
```python
import tempfile, os
p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
p.assemble("main").ok, p.vintage is not None
# (True, True)
```

### Project.workfile

`workfile` (속성)

프로젝트 자료의 워크파일 — 자료 정의를 쓰면 지금 자료 회차, 아니면 [data] file(처음 쓸 때 연다).

**오류**

- `ProjectError`: 자료 정의를 쓰는데 지금 회차가 없음(equion data build → equion data use)

### Project.data_build

`data_build(use=False, inbox=None, ask=None, who=None, command=None)`

자료 만들기 — 원자료를 정의(series.toml·derived.txt)대로 읽어 새 자료 회차(work/data/<회차>/)를 만든다.

같은 원자료·정의로 만든 회차가 이미 있으면 새로 만들지 않고 그 회차를 알린다. 지금 회차는 저절로 바뀌지 않는다(use=True면 바꾼다).  
inbox를 주면 먼저 받은 상자(DATA/raw/inbox/)의 새 파일을 출처와 짝지어 넣는다(`data_inbox`로 미리 본다) — 하나라도 짝이  
없거나 틀이 맞지 않으면 아무것도 넣지 않고 회차도 만들지 않는다.  

**매개변수**

- `use`: 참이면 만든(또는 같은) 회차를 지금 회차로
- `inbox`: None · 'auto'(짝이 하나이고 틀이 맞으면 넣는다) · 'ask'(ask(item)이 참인 것만 — ask가 없으면 auto)
- `ask`: 받은 파일마다 부르는 함수(InboxItem → 참거짓) — 명령줄은 터미널이면 묻는다

**돌려주는 것**

BuildResult — .id · .created · .n_series · .span · .implicit(알아서 한 것) · .text()  

**오류**

- `ProjectError`: 정의·원자료 문제(없는 열·틀이 맞지 않음·주기 변환·파생식 — 위치와 함께)

**예**

<!-- skip -->
```python
import tempfile, os
p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
r = p.data_build()
r.created, r.id == p.vintage        # 정의가 그대로라 같은 회차
# (False, True)
```

### Project.data_inbox

`data_inbox()`

받은 상자(DATA/raw/inbox/)의 파일마다 짝지을 출처와 틀 검사 — 미리보기(아무것도 바꾸지 않는다). InboxItem 목록.

짝짓기: series.toml `[source.이름] inbox = "글롭"`을 적었으면 그것만, 아니면 출처가 지금 읽는 파일 이름(날짜 꼬리 뺌)으로  
시작하는 파일 — 가장 긴 것. 넣기는 `data_build(inbox='auto')`·명령줄 `equion data build --inbox ask`.  

**예**

<!-- skip -->
```python
import tempfile, os, shutil
p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
_ = shutil.copy(eqn.datasets.path("toy_q"), os.path.join(p.root, "DATA/raw/inbox/toy_q_new.csv"))
[(x.source, x.status) for x in p.data_inbox()]
# [('na', 'ready')]
```

### Project.data_use

`data_use(vid, who=None, command=None)`

이 회차로 바꾸기 — equion.toml의 [data] vintage를 고치고(주석·순서는 그대로) 자료를 다시 연다. 이전 회차를 돌려준다.

**오류**

- `ProjectError`: 없는 회차

**예**

<!-- skip -->
```python
import tempfile, os
p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
v = p.vintage
p.data_use(v) == v
# True
```

### Project.data_list

`data_list()`

자료 회차 목록(만든 때 순) — {id, created, span, n_series, current}.

**예**

<!-- skip -->
```python
import tempfile, os
p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
[v["current"] for v in p.data_list()]
# [True]
```

### Project.data_diff

`data_diff(a=None, b=None)`

두 자료 회차의 차이 — 새·없어진 시리즈, 시리즈마다 새 기간과 개정(기간·크기).

기본은 지금 회차 → 가장 새 회차(같으면 그 앞 회차 → 가장 새 회차).  

**예**

<!-- skip -->
```python
import tempfile, os
p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
d = p.data_diff(p.vintage, p.vintage)
d.added, d.changed
# ([], [])
```

### Project.data_impact

`data_impact(a=None, b=None)`

회차를 바꾸면 영향받는 것 — 바뀐 시리즈를 쓰는 식(부품)과 모형. 다시 계산은 하지 않는다(사람이 시킬 때만).

**예**

<!-- skip -->
```python
import tempfile, os
p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
r = p.data_impact(p.vintage, p.vintage)
r.parts, r.models
# ([], [])
```

### Project.data_add

`data_add(path, source=None, as_name=None, note=None, who=None, command=None)`

원자료 넣기 — 파일을 DATA/raw/에 복사한다(받은 그대로, 같은 이름이면 날짜를 붙여 나란히). source를 주면 그 출처가 이 파일을 읽도록 series.toml을 고치되, 먼저 그 출처의 불러오기 틀로 읽어 보고 시리즈가 쓰는 열이 다 있고 주기가 같을 때만 넣고 고친다(틀 검사 — 맞지 않으면 아무것도 바꾸지 않고 `.problems`에 까닭).

**매개변수**

- `path`: 넣을 파일(csv·xlsx·xls)
- `source`: 바꿀 출처 이름([source.이름]) — 원자료 바꾸기
- `as_name`: DATA/raw/에 둘 이름(기본: 파일 이름)
- `note`: 출처 메모(옆 파일 *.source.toml에)

**돌려주는 것**

AddResult — .file · .copied · .source · .problems(틀이 맞지 않으면 — 그때 출처는 그대로)  

**예**

<!-- skip -->
```python
import tempfile, os
p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
r = p.data_add(eqn.datasets.path("toy_q"))      # 같은 파일이 이미 있다
r.copied, r.file
# (False, 'DATA/raw/toy_q.csv')
```

### Project.parts

`parts(name=None)`

부품(식·항등식) 목록 — name이 없으면 전부, 블록 이름이면 그 블록, 모형 이름이면 조립된 식들.

**예**

<!-- skip -->
```python
import tempfile, os
p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
[x.id for x in p.parts("demand")]
# ['demand:CN', 'demand:I', 'demand:Y']
```

### Project.part

`part(pid)`

부품 하나 — `블록:목표`(대소문자 무시).

**오류**

- `KeyError`: 없는 부품(있는 부품 이름과 함께)

**예**

<!-- skip -->
```python
import tempfile, os
p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
p.part("demand:y").text
# 'Y = CN + I + G'
```

### Project.used_by

`used_by(name)`

쓰는 곳 — 블록이나 부품(`블록:목표`)을 쓰는 모형 목록. 고치기 전에 영향 범위를 본다.

**예**

<!-- skip -->
```python
import tempfile, os
p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
p.used_by("demand"), p.used_by("finance:RL")
# (['core', 'main', 'main_fixrl'], ['main'])
```

### Project.assemble

`assemble(name=None, swap=None)`

조립 검사 — 계산 없이 모형(또는 블록)의 구조를 본다: 내생·외생, 겹친 목표, 모르는 변수, 외생 자료 끝, 블록 사이 연결, 풀이 블록.

**매개변수**

- `name`: 모형 또는 블록 이름(기본: [hs] model, 모형이 하나면 그것)
- `swap`: {부품: 식} — 파일을 바꾸지 않고 그 식만 바꿔 끼워 검사

**돌려주는 것**

AssemblyReport — .ok · .problems · .endogenous · .exogenous · .blocks · .text()  

**예**

<!-- skip -->
```python
import tempfile, os
p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
r = p.assemble("main")
r.ok, r.endogenous
# (True, ['CN', 'I', 'Y', 'P', 'RL', 'M2'])
r.exogenous
# ['G', 'POIL', 'R']
p.assemble("main_fixrl").exogenous
# ['G', 'POIL', 'R', 'RL']
```

### Project.adopted

`adopted` (속성)

채택표(EQUATIONS/adopted.toml) — {부품: est:기록}. 모형은 이 기록의 계수로 푼다(D35).

**예**

<!-- skip -->
```python
import tempfile, os
p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
p.adopted
# {}
```

### Project.model

`model(name=None, swap=None)`

모형(또는 블록)을 조립해 워크파일 모델 객체로 — 추정식은 지금 자료로 추정하고 항등식은 그대로 넣는다.

채택 기록이 없으면(작업 기록은 다음 단계) 식을 지금 자료·식의 표본(`@smpl`, 없으면 자료 전체)으로 추정하고 `.notes`에 적는다.  
같은 식은 한 번만 추정한다(다시 부르면 그 추정을 쓴다).  

**매개변수**

- `name`: 모형 또는 블록 이름(블록이면 그 블록의 식만 — 나머지 변수는 실측)
- `swap`: {부품: 식} — 파일을 바꾸지 않고 그 식만 바꿔 끼운다(목표변수는 같아야 한다)

**돌려주는 것**

ModelObject — .solve() · .forecast() · .scenario() …(워크파일 API)  

**오류**

- `ProjectError`: 조립 문제(겹친 목표·모르는 변수 등 — assemble의 문제 목록)

**예**

<!-- skip -->
```python
import tempfile, os
p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
m = p.model("core")
m.endogenous
# ['CN', 'I', 'Y']
```

### Project.span

`span(spec)`

구간 표기 → (시작, 끝) 라벨 — '2005Q1:2019Q4' · '2005Q1:last' · 'last-39:last' · 'next:12'. last는 자료의 마지막 값이 있는 기간.

**예**

<!-- skip -->
```python
import tempfile, os
p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
p.span("last-3:last"), p.span("next:4")
# (('2019Q1', '2019Q4'), ('2020Q1', '2020Q4'))
```

### Project.hs

`hs(name=None, start=None, end=None, mode=None, swap=None, record=False, vs=None, as_name=None, who=None, command=None, **opts)`

과거 재현(HS) — 모형이나 블록을 풀어 실측과 견준다. 블록이면 그 블록만 풀고 나머지 변수는 실측(블록 HS).

구간·방식의 기본은 equion.toml `[hs]`의 range·mode, 없으면 자료 전체·dynamic. 풀이 값은 워크파일의 별칭 시리즈(`CN_0` …)에 쓴다.  

**매개변수**

- `name`: 모형 또는 블록 이름(기본: [hs] model)
- `start, end`: 구간(기본: [hs] range)
- `mode`: 'dynamic' · 'static' · 'fit'(기본: [hs] mode)
- `swap`: {부품: 식 또는 est:기록} — 그 식만 바꿔 끼워 푼다(파일은 그대로). 기록이면 그 기록의 계수로
- `record`: 참이면 작업 기록(`work/hs/<이름>/` — 조립 명세·적합도·풀린 값·summary.md)을 남기고 HSRecord를 돌려준다
- `vs`: 견줄 HS 기록(record=True일 때 — 변수별 RMSPE 전후)
- `as_name`: 기록 이름(기본 hs_0001, hs_0002 …)
- `who, command`: 기록에 적을 '누가'·'명령'(명령줄이 채운다)
- `**opts`: ModelObject.solve의 선택지(on_missing · on_fail · tolerance …)

**돌려주는 것**

SolveResult — .statistics() · .counts() · .summary() (record=True면 HSRecord — .id · .stats · .text())  

**예**

<!-- skip -->
```python
import tempfile, os
p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
r = p.hs("main")
r.start, r.end, r.counts()["ok"]
# ('2005Q1', '2019Q4', 60)
p.hs("demand").counts()["ok"]
# 60
```

### Project.est

`est(target, method=None, smpl=None, as_name=None, part=None, sim=False, cov=None, who=None, command=None)`

식 하나를 추정해 작업 기록(`work/est/<이름>/`)을 남긴다 — 부품(블록 파일의 그 줄) 또는 식 글자(후보).

식 글자의 목표변수가 한 부품의 목표면 그 부품의 후보가 된다(여럿이면 part로). 판단 기준(`[criteria]` — 기대 부호·진단·|t|)이  
있으면 통과·걸러짐과 까닭을 적는다. 채택은 따로(`adopt`).  

**매개변수**

- `target`: 부품 `블록:목표` 또는 식 글자(예: "CN c Y CN(-1)")
- `method`: 'auto'(기본 — @inst가 있으면 tsls) · 'ls' · 'tsls'
- `smpl`: 표본 'S:E'(상대 기간 가능 — '1990Q1:last')
- `as_name`: 기록 이름(기본: 목표변수_0001 …)
- `part`: 어느 부품의 후보인지(목표가 같은 식이 여럿일 때)
- `sim`: 참이면 식 하나의 동태 모의([hs] range — 다른 변수는 실측)와 RMSPE
- `cov`: 계수 공분산('white' · 'hac' …)

**돌려주는 것**

EstRecord — .id · .coefs · .passed · .meta · .text()  

**오류**

- `ProjectError`: 항등식·추정할 수 없는 식 · RecordError: 이미 있는 기록 이름

**예**

<!-- skip -->
```python
import tempfile, os
p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
r = p.est("CN c Y CN(-1) CN(-2)", as_name="cn_lag2")
r.id, r.meta["part"], r.meta["n"]
# ('est:cn_lag2', 'demand:CN', 198)
```

### Project.adopt

`adopt(record, part=None, who=None, command=None)`

추정 기록을 그 부품의 채택 계수로 — 블록 파일의 그 줄을 기록의 식으로 바꾸고(다르면) 채택표 `EQUATIONS/adopted.toml`을 고친다(주석·순서 그대로). 바뀜 기록에 남고, 그 뒤 모형은 이 계수로 푼다(다시 추정하지 않음).

**돌려주는 것**

AdoptResult — .part · .record · .previous · .line_changed · .change(바뀜 기록) · .text()  

**예**

<!-- skip -->
```python
import tempfile, os
p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
r = p.est("demand:CN", as_name="cn_now")
p.adopt("est:cn_now").line_changed, p.adopted
# (False, {'demand:CN': 'est:cn_now'})
```

### Project.compare

`compare(*records, target=None, part=None)`

기록 비교 — 추정 기록이면 식·표본·적합 통계·진단·기준·단독 모의 표(종속변수·표본이 다르면 경고), HS 기록이면 변수별 RMSPE.

**매개변수**

- `*records`: 기록 이름(est:… · hs:…)
- `target`: 이 목표변수의 추정 기록 전부 · part: 이 부품의 후보 전부

**돌려주는 것**

CompareResult — .table(DataFrame) · .warnings · .text()  

**예**

<!-- skip -->
```python
import tempfile, os
p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
_ = p.est("CN c Y CN(-1)", as_name="a")
_ = p.est("CN c Y", as_name="b")
list(p.compare(target="CN").table.index)
# ['est:a', 'est:b']
```

### Project.replay

`replay(record, as_name=None, who=None, command=None)`

HS 기록을 그때 그대로 다시 — 기록의 조립 명세(식 글자·계수·자료 회차·구간·방식)로 푼다. 지금 파일과 무관하고, 원래 기록의 풀린 값과 견주어(`.meta['replay']` — same · max_abs_diff) 새 기록을 남긴다.

**예**

<!-- skip -->
```python
import tempfile, os
p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
h = p.hs("main", record=True)
p.replay(h.id).meta["replay"]["same"]
# True
```

### Project.sim

`sim(scenario='base', model=None, range=None, vintage=None, vs=None, as_name=None, mode=None, who=None, command=None)`

전망·시나리오 — 가정 세트(`ASSUMPTIONS/이름.csv`, 빈 외생은 `[forecast] fill`)·보정항(`ADDFACTORS/이름.toml`)·시나리오 (`SCENARIOS/이름.toml`)로 풀고 작업 기록(`work/sim/<이름>/`)을 남긴다. 시나리오면 같은 가정·보정항의 기준선도 풀어 차이를 적는다.

**매개변수**

- `scenario`: 'base'(기준선 — 파일이 없어도 된다) 또는 SCENARIOS/의 이름
- `model`: 모형(기본: 시나리오의 model → [forecast] model → [hs] model)
- `range`: 전망 구간(기본 [forecast] range, 없으면 'next:8')
- `vintage`: 다른 자료 회차로(지금 회차는 그대로)
- `vs`: 견줄 전망 기록(sim:…) — 연간 증가율 전후
- `as_name`: 기록 이름(기본: 연-월_시나리오)
- `mode`: 'dynamic'(기본) · 'static'

**돌려주는 것**

SimRecord — .id · .levels · .flags(값의 종류) · .annual · .diff · .text()  

**오류**

- `ProjectError`: 없는 시나리오·가정·보정항 파일, 파일 문법, 전망 구간의 외생이 비어 채우지 못함

**예**

<!-- skip -->
```python
import tempfile, os
p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
r = p.sim(as_name="base_a")
r.meta["range"], r.counts()["ok"]
# (['2020Q1', '2021Q4'], 8)
p.sim("oil20", as_name="oil_a").meta["vs_base"]["P"] > 0
# True
```

### Project.an

`an(analysis, target, smpl=None, as_name=None, note=None, who=None, command=None, **options)`

분석 하나 — 등록부(`equion.registry`)의 분석을 돌려 기록(`work/an/<이름>/` — 표 CSV·차트 CSV·카드 summary.md)을 남긴다.

분석 목록은 `eqn.registry.table()`(명령줄 `equion an list`). 계절조정·파생은 미리보기만 하고 `keep`이 정의로, ECM·VAR·VECM·시스템은  
`keep`이 식 후보로 남긴다. 나머지(요약·단위근·공적분·식 진단·예측 평가·안정성·승수)는 아무 파일도 바꾸지 않는다.  

**매개변수**

- `analysis`: 분석 이름(summary · unitroot · coint · diag · fcsteval · stability · multipliers · seas · genr · ecm · var · vecm · system)
- `target`: 대상 — 시리즈·묶음([group])·식('log(Y) R')·부품·est: 기록·모형·블록·'이름 = 식'(분석마다)
- `smpl`: 표본 'S:E'(상대 기간 가능)
- `as_name`: 기록 이름(기본 분석_0001 …)
- `note`: 노트 경로 — 그 끝에 명령 블록과 결과 구역을 더한다
- `**options`: 분석의 옵션(`equion an <분석> --help`)

**돌려주는 것**

AnRecord — .id · .table(k) · .meta · .text()  

**예**

<!-- skip -->
```python
import tempfile, os
p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
r = p.an("unitroot", "dlog(Y) R")
r.table(1)["판단"].tolist()
# ['정상', '단위근']
```

### Project.keep

`keep(record, as_name=None, replace=False, who=None, command=None)`

분석 기록을 남긴다 — 만드는 분석(계절조정·파생)은 정의(`series.toml`·`derived.txt`, `made_by` = 기록)로, 부품을 내는 분석(ECM·VAR·VECM·시스템)은 식 후보(est: 기록 — 계수 그대로)로. 정의를 고치면 바뀜 기록에 남고, 자료에는 `data build`로 들어간다.

**예**

<!-- skip -->
```python
import tempfile, os
p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
k = p.keep(p.an("genr", "GAP = Y - CN - I").id)
k.kind, k.what[0]
# ('derived', 'DATA/derived.txt: GAP = Y - CN - I   # an:genr_0001')
```

### Project.note_run

`note_run(note, block=None, stale=False, force=False, who=None, command=None)`

노트의 ```` ```equion ```` 블록을 실행해 블록 아래 결과 구역을 채운다(블록마다 새 기록). 블록은 등록부의 계산·보기 명령만 부를 수 있고, 손으로 고친 구역은 force일 때만 덮는다. Python 블록은 block으로 고를 때만 돈다.

**돌려주는 것**

NoteResult — .blocks(블록마다 상태) · .ok · .change · .text()  

**예**

<!-- skip -->
```python
import tempfile, os
p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
_ = open(os.path.join(p.root, "n.md"), "w", encoding="utf-8").write("# n\n\n```equion\nan unitroot R\n```\n")
[b.status for b in p.note_run("n.md").blocks]
# ['run']
```

### Project.note_check

`note_check(note)`

노트 검사(실행하지 않고) — 블록마다 실행 안 함 · 없는 기록 · 낡음(자료·정의가 바뀜) · 손으로 고침 · 허용 안 된 명령.

**예**

<!-- skip -->
```python
import tempfile, os
p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
_ = open(os.path.join(p.root, "n.md"), "w", encoding="utf-8").write("```equion\nan unitroot R\n```\n")
[b.status for b in p.note_check("n.md").blocks]
# ['never']
```

### Project.report_new

`report_new(name, title=None, from_report=None, exist_ok=False, who=None, command=None)`

새 보고서(`reports/이름.md`) — 틀(제목·날짜·자료 회차·모형). from_report면 지난 보고서를 복사하고 구역마다 바꿔 낄 기록을 제안한다. exist_ok면 이미 있는 보고서는 그대로 둔다(`.exists` — 스크립트를 같은 회차로 다시 돌릴 때 글을 지키려고).

**예**

<!-- skip -->
```python
import tempfile, os
p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
p.report_new("monthly").report
# 'reports/monthly.md'
```

### Project.report_add

`report_add(report, record, rows=None, show='level', annual=False, digits=None, title=None, chart=False, under=None, key=None, force=False, who=None, command=None)`

보고서로 보내기 — 기록의 표(와 차트)를 고른 모양(행·보이기·연간·소수점)으로 보고서에 넣는다. 구역에는 보이지 않는 표시 (기록·보낸 날·자료 회차·모양)가 붙고, 차트 자료는 보고서 옆 `_data/`로 복사한다.

**매개변수**

- `record`: 기록(sim:… · hs:… · est:… · an:…#표 번호)
- `rows`: 행(시리즈·변수 목록) · show: 'level' · 'qoq' · 'yoy' · 'diff'(전망) · annual: 연간(전망)
- `digits`: 소수점 · title: 표 제목(번호는 저절로) · chart: 차트도 · under: 그 제목 아래 끝에
- `key`: 구역 이름 — 같은 이름의 구역이 있으면 그 자리에서 이 기록으로 바꾼다(손으로 고친 구역은 force일 때만)

**예**

<!-- skip -->
```python
import tempfile, os
p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
_ = p.report_new("m")
s = p.sim(as_name="b")
p.report_add("m", "sim:b", rows=["Y", "CN"], show="yoy", annual=True).items[0]["detail"]
# '**표 1. 전망 — base (main)** (연간 증가율, %)'
```

### Project.report_check

`report_check(report)`

보고서 검사 — 구역마다 없는 기록 · 더 새 기록(같은 갈래) · 낡음(자료·정의가 바뀜) · 손으로 고침.

**예**

<!-- skip -->
```python
import tempfile, os
p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
_ = p.report_new("m")
_ = p.report_add("m", p.hs("main", record=True).id)
p.report_check("m").items[0]["status"]
# '정상'
```

### Project.report_update

`report_update(report, region=None, to=None, dry_run=False, force=False, who=None, command=None)`

새 기록으로 바꾸기 — 구역을 같은 모양으로 다시 만들어 차이를 보이고 적용한다(기본: 같은 갈래의 가장 새 기록). 손으로 고친 구역은 고친 곳을 차이로 보이고 force일 때만 덮는다.

**예**

<!-- skip -->
```python
import tempfile, os
p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
_ = p.report_new("m")
_ = p.report_add("m", p.hs("main", record=True).id)
h2 = p.hs("main", record=True, swap={"demand:CN": "CN c Y"})
p.report_update("m").items[0]["to"] == h2.id
# True
```

### Project.reestimate

`reestimate(name=None, adopt='never', who=None, command=None)`

모형(또는 블록)의 추정식을 블록 파일의 글자 그대로 지금 자료로 다시 추정해 기록을 남기고, 정책에 따라 새 계수를 채택한다 (명령줄 `equion est --adopted [모형] --adopt 정책`, D35).

**매개변수**

- `name`: 모형 또는 블록(기본: [hs] model)
- `adopt`: 'never'(기록만 — 기본) · 'if_pass'(판단 기준을 통과한 식만, 기준이 없으면 통과) · 'all'

**돌려주는 것**

ReestResult — .rows(식마다 옛·새 기록·기준·채택·계수 변화) · .adopted · .flagged · .change · .text()  

**예**

<!-- skip -->
```python
import tempfile, os
p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
r = p.reestimate("demand", adopt="all")
r.adopted, sorted(p.adopted)
# (['demand:CN', 'demand:I'], ['demand:CN', 'demand:I'])
```

### Project.propose

`propose(name=None, title='', why='', parts=None, files=None, previews=(), who=None, command=None)`

제안을 만든다 — 파일은 바꾸지 않고 "이렇게 바꾸면"을 `work/proposals/<이름>/`에 남긴다(바뀔 내용·까닭·미리 계산한 기록).

**매개변수**

- `name`: 제안 이름(기본 p1, p2 …)
- `title, why`: 제목·까닭(사람이 읽는 글 — 근거 기록 이름을 넣는다)
- `parts`: {부품: est:기록(그 식으로 바꾸고 채택) 또는 식 글자}
- `files`: {프로젝트 안 경로: 새 내용 파일}
- `previews`: 미리 계산한 기록(hs:… · sim:… · est:…)

**돌려주는 것**

Proposal — .id · .status · .stale · .diff() · .text()  

**예**

<!-- skip -->
```python
import tempfile, os
p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
pr = p.propose(title="소비에 시차 하나 더", parts={"demand:CN": "CN c Y CN(-1) CN(-2)"})
pr.id, pr.status, p.part("demand:CN").text
# ('prop:p1', 'open', 'CN c Y CN(-1)')
```

### Project.proposals

`proposals()`

제안 목록(만든 순) — 열림·적용·버림 모두.

**예**

<!-- skip -->
```python
import tempfile, os
p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
_ = p.propose(parts={"demand:CN": "CN c Y"})
[(x.id, x.status) for x in p.proposals()]
# [('prop:p1', 'open')]
```

### Project.apply_proposal

`apply_proposal(name, force=False, who=None, command=None)`

제안을 적용한다 — 바꿀 파일을 새 내용으로 쓰고 바뀜 기록에 "제안 … 적용". 만든 뒤 파일이 바뀌었으면(낡음) force일 때만.

**예**

<!-- skip -->
```python
import tempfile, os
p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
_ = p.propose(parts={"demand:CN": "CN c Y CN(-1) CN(-2)"})
p.apply_proposal("p1").status, p.part("demand:CN").text
# ('applied', 'CN c Y CN(-1) CN(-2)')
```

### Project.drop_proposal

`drop_proposal(name, why='', who=None)`

제안을 버린다 — 파일은 그대로, 제안 기록은 남는다(상태 '버림').

**예**

<!-- skip -->
```python
import tempfile, os
p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
_ = p.propose(parts={"demand:CN": "CN c Y"})
p.drop_proposal("p1", why="설명할 수 없다").status
# 'dropped'
```

### Project.export

`export(records, xlsx)`

기록(est:· hs:· sim:· data:회차)을 엑셀 한 권으로 — 값·값의 종류·출처 시트. 기록은 남기지 않는다.

**돌려주는 것**

{path, sheets, records}  

**예**

<!-- skip -->
```python
import tempfile, os
p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
h = p.hs("main", record=True)
out = p.export([h.id, "data:" + p.vintage], "exports/hs.xlsx")
out["sheets"][:3]
# ['출처', 'hs_0001_적합도', 'hs_0001_해']
```

### Project.run_script

`run_script(script, sets=None, from_step=None, dry_run=False, fail_on='failed', name=None, who=None, command=None, echo=None, verbosity=1, python=True)`

Equion 스크립트(`.eqs`)를 실행하고 실행 기록 `work/run/<이름>/`(`run:`)을 남긴다 — 명령줄 `equion run x.eqs`.

한 줄이 명령 하나이고 같은 프로세스에서 명령줄 그대로 돈다(단계의 기록·바뀜 기록에는 누가 '스크립트', 그 실행 이름).  
명령이 실패하면 거기서 멈추고 그 종료 코드, `expect --stop`에 걸리면 2, HS·전망 기록에 fail_on 상태의 기간이 있으면 2.  

**매개변수**

- `script`: 스크립트 경로(프로젝트 기준) · sets: --set {이름: 값}(값은 목록 또는 띄어 쓴 글자)
- `from_step`: 이 단계(번호 또는 ## 제목)부터 · dry_run: 미리보기(기록을 남기지 않음 → Plan)
- `fail_on`: 'failed'·'fallback'·'partial'·'never' · name: 실행 기록 이름(기본 <스크립트>_0001 …)
- `echo`: 단계마다 한 줄을 받는 함수(예: print) · python: Python 단계(py)를 돌릴지

**돌려주는 것**

RunResult — .id · .exit_code · .status · .steps(단계마다 .line·.status·.records) · .text()  
(dry_run이면 Plan — .steps · .problems · .text())  

**오류**

- `ScriptError`: 문법·명령·매개변수 문제(실행하지 않는다)

**예**

<!-- skip -->
```python
import tempfile, os
p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
r = p.run_script("FLOWS/monthly.eqs", sets={"scenarios": "base"})
r.exit_code, r.steps[3].line, r.steps[2].status          # 기준 미달 식이 있으면 표시(!)하고 계속
# (0, 'hs main', 'flag')
```

### Project.check_script

`check_script(script, sets=None)`

스크립트를 실행 없이 검사 — 문법·명령(허용 목록)·선택지·{이름}·매개변수·부품·모형·시나리오·노트·포함한 파일.

**돌려주는 것**

ScriptCheck — .ok · .problems · .changing(정의 파일을 바꾸는 단계) · .python · .text()  

**예**

<!-- skip -->
```python
import tempfile, os
p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
p.check_script("FLOWS/monthly.eqs").ok
# True
```

### Project.replay_run

`replay_run(run, who=None, command=None, echo=None)`

실행 기록을 그때 그대로 다시 — 정의 사본(defs/)·받은 원자료·같은 스크립트(src/)·매개변수로 프로젝트 사본에서 돌리고 단계마다 기록의 숫자를 견준다(허용오차). 프로젝트는 바꾸지 않고 견준 결과를 새 실행 기록(`replay_of`)으로 남긴다.

**돌려주는 것**

ReplayResult — .same · .steps(단계마다 verdict 같음·다름·detail) · .id · .exit_code(같으면 0, 다르면 2)  

**예**

<!-- skip -->
```python
import tempfile, os
p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
r = p.run_script("FLOWS/monthly.eqs", sets={"scenarios": "base"})
p.replay_run(r.id).same
# True
```

### Project.new_script

`new_script(name, records=None, last=None, title=None, force=False, who=None, command=None)`

작업 기록의 명령으로 스크립트 초안 `FLOWS/<이름>.eqs`(바뀜 기록에 남는다) — 탐색하며 한 일을 굳힌다. 명령에서 -p·--as·--note·--json은 뺀다(다시 돌려도 이름이 겹치지 않게). 기록이 없으면 빈 틀.

**매개변수**

- `records`: 기록 이름 목록 · last: 최근 기록 n개(실행 기록 run: 제외)

**예**

<!-- skip -->
```python
import tempfile, os
p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
e = p.est("demand:CN", as_name="c1", command="equion est demand:CN --as c1")
rel = p.new_script("mine", records=[e.id])
open(os.path.join(p.root, rel), encoding="utf-8").read().splitlines()[3:5]
# ['## 추정', 'est demand:CN   # ← est:c1']
```

### Project.export_script

`export_script(script, out=None, force=False)`

스크립트를 같은 일을 하는 Python 파일로(`eqn.script.session` — 같은 명령·같은 기록) → 프로젝트 기준 경로.

**예**

<!-- skip -->
```python
import tempfile, os
p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
p.export_script("FLOWS/monthly.eqs")
# 'FLOWS/monthly.py'
```

### Project.ident

`ident(pid, start=None, end=None, tol=1e-06)`

항등식 단독 검사 — 실측으로 좌변과 우변을 계산해 견준다(추정 없이).

**매개변수**

- `pid`: 항등식 부품 `블록:목표`(예: demand:Y)
- `start, end`: 구간(기본: 자료 전체)
- `tol`: 허용오차 — |좌변 − 우변| ≤ tol·max(1, |좌변|)이면 성립

**돌려주는 것**

IdentityCheck — .ok · .mismatches · .max_abs · .table · .text()  

**오류**

- `KeyError`: 없는 부품 · ValueError: 항등식이 아님

**예**

<!-- skip -->
```python
import tempfile, os
p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
c = p.ident("demand:Y")
c.ok, c.n
# (True, 200)
```

## 22. 조립 검사 결과 `p.assemble(…)`

| 이름 | 서명 | 설명 |
|---|---|---|
| `ok` | `속성` | 문제가 없으면 참. |
| `n_equations` | `속성` | 추정식 수. |
| `n_identities` | `속성` | 항등식 수. |
| `text` | `()` | 명령줄에 보이는 짧은 글. |
| `to_dict` | `()` | 명령줄 --json과 같은 사전. |
| `output` | `()` | 부품 표(부품·종류·위치·식·설명). |
| `show` | `()` | 짧은 글을 보인다. |

## 23. 항등식 검사 결과 `p.ident(…)`

| 이름 | 서명 | 설명 |
|---|---|---|
| `ok` | `속성` | 비교한 모든 기간에서 \|차이\| ≤ tol·max(1, \|좌변\|)이면 참. |
| `max_abs` | `속성` | 가장 큰 \|차이\|. |
| `max_pct` | `속성` | 가장 큰 \|차이%\|. |
| `text` | `()` | 명령줄에 보이는 짧은 글. |
| `to_dict` | `()` | 명령줄 --json과 같은 사전. |
| `output` | `()` | 기간별 표(좌변·우변·차이·차이%). |
| `show` | `()` | 짧은 글을 보인다. |

## 24. 자료 만들기 결과 `p.data_build()`

| 이름 | 서명 | 설명 |
|---|---|---|
| `text` | `()` | 명령줄에 보이는 짧은 글. |
| `to_dict` | `()` | 명령줄 --json과 같은 사전. |

## 25. 자료 회차 차이 `p.data_diff(…)`

| 이름 | 서명 | 설명 |
|---|---|---|
| `changed` | `속성` | 새 값·개정·없어진 값이 있는 시리즈. |
| `text` | `()` | 명령줄에 보이는 짧은 글. |
| `to_dict` | `()` | 명령줄 --json과 같은 사전. |
| `output` | `()` | 바뀐 시리즈 표. |
| `show` | `()` | 짧은 글을 보인다. |

## 26. 회차 영향 `p.data_impact(…)`

| 이름 | 서명 | 설명 |
|---|---|---|
| `text` | `()` | 명령줄에 보이는 짧은 글. |
| `to_dict` | `()` | 명령줄 --json과 같은 사전. |
| `show` | `()` | 짧은 글을 보인다. |

## 27. 원자료 넣기 결과 `p.data_add(…)`

| 이름 | 서명 | 설명 |
|---|---|---|
| `text` | `()` | 명령줄에 보이는 짧은 글. |
| `to_dict` | `()` | 명령줄 --json과 같은 사전. |

## 28. 추정 기록 `p.est(…)`

| 이름 | 서명 | 설명 |
|---|---|---|
| `id` | `속성` | 기록 이름 est:… |
| `meta` | `속성` | record.json 내용. |
| `coefs` | `속성` | 계수(이름 = 항, 상수항은 const). |
| `passed` | `속성` | 판단 기준 통과(기준이 없으면 None). |
| `text` | `()` | 명령줄에 보이는 짧은 글. |
| `to_dict` | `()` | 명령줄 --json과 같은 사전(record.json에서 식 직렬화를 뺀 것). |

## 29. HS 기록 `p.hs(…, record=True)`

| 이름 | 서명 | 설명 |
|---|---|---|
| `id` | `속성` | 기록 이름 hs:… |
| `meta` | `속성` | record.json 내용. |
| `stats` | `속성` | 변수별 적합도(stats.csv). |
| `solved` | `속성` | 풀린 값(solved.csv — 행 = 기간). |
| `start` | `속성` | 구간 시작. |
| `end` | `속성` | 구간 끝. |
| `counts` | `()` | 기간 상태 수 {'ok', 'partial', 'fallback', 'failed'}. |
| `text` | `()` | 명령줄에 보이는 짧은 글. |
| `to_dict` | `()` | 명령줄 --json과 같은 사전. |

## 30. 채택 결과 `p.adopt(…)`

| 이름 | 서명 | 설명 |
|---|---|---|
| `text` | `()` | 명령줄에 보이는 짧은 글. |
| `to_dict` | `()` | 명령줄 --json과 같은 사전. |

## 31. 기록 비교 `p.compare(…)`

| 이름 | 서명 | 설명 |
|---|---|---|
| `text` | `()` | 명령줄에 보이는 짧은 글. |
| `to_dict` | `()` | 명령줄 --json과 같은 사전. |
| `md` | `()` | md 표. |

## 32. 전망 기록 `p.sim(…)`

| 이름 | 서명 | 설명 |
|---|---|---|
| `id` | `속성` | 기록 이름 sim:… |
| `meta` | `속성` | record.json 내용. |
| `levels` | `속성` | 수준(levels.csv — 전망 앞 2년의 실측과 전망 구간). |
| `flags` | `속성` | 값의 종류(flags.csv — 실측·해·가정·채움·결측). |
| `annual` | `속성` | 연간 평균 수준과 증가율(annual.csv). |
| `diff` | `속성` | 시나리오 − 기준선(diff.csv — 수준 차이·%) — 기준선 기록이면 None. |
| `counts` | `()` | 기간 상태 수 {'ok', 'partial', 'fallback', 'failed'}. |
| `text` | `()` | 명령줄에 보이는 짧은 글. |
| `to_dict` | `()` | 명령줄 --json과 같은 사전. |

## 33. 다시 추정 결과 `p.reestimate(…)`

| 이름 | 서명 | 설명 |
|---|---|---|
| `adopted` | `속성` | 새 계수를 채택한 부품. |
| `flagged` | `속성` | 기준을 통과하지 못해 사람이 볼 부품. |
| `text` | `()` | 명령줄에 보이는 짧은 글. |
| `to_dict` | `()` | 명령줄 --json과 같은 사전. |

## 34. 제안 `p.propose(…)`

| 이름 | 서명 | 설명 |
|---|---|---|
| `id` | `속성` | 제안 이름 prop:… |
| `path` | `속성` | 제안 폴더. |
| `status` | `속성` | open · applied · dropped. |
| `new_content` | `(rel)` | 바뀔 파일의 새 내용(지우는 파일이면 None). |
| `stale` | `속성` | 만든 뒤 지금 내용이 바뀐 파일(적용하면 그 바뀜을 덮는다). |
| `diff` | `()` | 지금 파일 대비 바뀔 내용의 차이(unified diff). |
| `text` | `()` | 명령줄에 보이는 짧은 글. |
| `to_dict` | `()` | 명령줄 --json과 같은 사전. |

## 35. 분석 기록 `p.an(…)`

| 이름 | 서명 | 설명 |
|---|---|---|
| `id` | `속성` | 기록 이름 an:… |
| `meta` | `속성` | record.json 내용. |
| `table` | `(k=1)` | 표 k번(1부터 — table_k.csv). |
| `text` | `()` | 명령줄에 보이는 짧은 글. |
| `to_dict` | `()` | 명령줄 --json과 같은 사전. |

## 36. 남기기 결과 `p.keep(…)`

| 이름 | 서명 | 설명 |
|---|---|---|
| `text` | `()` | 명령줄에 보이는 짧은 글. |
| `to_dict` | `()` | 명령줄 --json과 같은 사전. |

## 37. 노트 결과 `p.note_run(…)`

| 이름 | 서명 | 설명 |
|---|---|---|
| `ok` | `속성` | 오류·허용 안 됨이 없으면 참. |
| `text` | `()` | 명령줄에 보이는 짧은 글. |
| `to_dict` | `()` | 명령줄 --json과 같은 사전. |

## 38. 보고서 결과 `p.report_add(…)`

| 이름 | 서명 | 설명 |
|---|---|---|
| `text` | `()` | 명령줄에 보이는 짧은 글. |
| `to_dict` | `()` | 명령줄 --json과 같은 사전. |

## 39. 등록부 `eqn.registry`

| 이름 | 서명 | 설명 |
|---|---|---|
| `analyses` | `(for_kind=None)` | 등록된 분석(등록 순) — for_kind를 주면 그 대상 종류를 받는 것만. |
| [`get`](#eqnregistryget) | `(name)` | 분석 하나(이름). |
| `table` | `()` | 분석 목록 표(이름·갈래·대상·만드는 것·결과) — `equion an list`·Claude 안내가 쓴다. |
| [`allowed`](#eqnregistryallowed) | `(tokens, where='note')` | 명령 한 줄이 허용 목록에 있으면 None, 아니면 까닭. |
| `register` | `(a)` | 분석을 등록한다(이름이 겹치면 오류). |

### eqn.registry.get

`get(name)`

분석 하나(이름).

**오류**

- `KeyError`: 없는 분석(있는 분석 목록과 함께)

### eqn.registry.allowed

`allowed(tokens, where='note')`

명령 한 줄이 허용 목록에 있으면 None, 아니면 까닭.

where='note'(노트의 블록): 계산·보기 명령만 — 정의 파일을 바꾸는 줄(`est --adopt`·`an keep` 등)은 안 된다.  
where='script'(스크립트 .eqs): 그에 더해 자료 만들기·채택·노트 실행·보고서·내보내기(SCRIPT_COMMANDS).  

## 40. 스크립트 `eqn.script`

| 이름 | 서명 | 설명 |
|---|---|---|
| [`session`](#eqnscriptsession) | `(project='.', **kw)` | 스크립트 실행 하나를 연다 — with 블록으로 쓰면 끝에서 실행 기록(run:)을 남긴다. 매개변수는 `Session`과 같다. |
| `parse` | `(root, path, _stack=(), _section='')` | 스크립트를 읽는다 — `run 다른.eqs`는 그 자리에 펼친다(매개변수는 하나의 이름 공간 — 먼저 적은 기본값이 이긴다). 문제는 `.problems`에 모은다(첫 문제에서 멈추지 않는다). 경로는 프로젝트 폴더 기준. |
| `resolve` | `(text, values, refs=None, keep=())` | {이름}을 값으로 — 목록은 띄어 쓰고(빈칸·따옴표가 든 값만 따옴표), {{·}}는 글자 그대로. keep의 이름은 그대로 둔다(미리보기). |
| `run_script` | `(p, path, sets=None, from_step=None, fail_on='failed', name=None, who=None, command=None, echo=None, verbosity=1, python=True, today=None, replay_of=None, sc=None)` | 스크립트를 실행하고 실행 기록을 남긴다 → RunResult. 문법·검사 문제가 있으면 아무것도 하지 않고 ScriptError. |
| `plan` | `(p, path, sets=None, from_step=None)` | 미리보기 — 실행하지 않고 단계마다 줄(바꿔 넣은 값)·바꾸는 정의 파일·실행 때 정해지는 값. 기록을 남기지 않는다. |
| `check` | `(p, path, sets=None)` | 실행 없이 검사 — 문법·명령(허용 목록)·선택지·{이름}·매개변수(--set)·부품·모형·시나리오·노트·포함한 파일. |
| `replay` | `(p, rid, who=None, command=None, echo=None, verbosity=1)` | 실행 기록을 그때 그대로 다시 — 정의 사본·받은 원자료·같은 스크립트(src/)·매개변수·오늘 날짜로, 프로젝트 사본에서 돌리고 단계마다 기록의 숫자를 견준다(허용오차). 프로젝트는 바꾸지 않고, 견준 결과를 새 실행 기록(replay_of)으로 남긴다. 다른 단계가 있으면 종료 코드 2. |
| `draft` | `(p, records=None, last=None, title=None)` | 작업 기록의 명령으로 스크립트 초안(글) — 같은 종류가 이어지면 한 제목 아래. 부를 수 없는 명령은 주석으로 남긴다. |
| `new_script` | `(p, name, records=None, last=None, title=None, force=False, who=None, command=None)` | FLOWS/<이름>.eqs를 만든다(바뀜 기록에 남는다) → 프로젝트 기준 경로. |
| `export_py` | `(p, path, out=None, force=False)` | 스크립트를 Python 파일로(기본: 같은 자리의 .py) → 프로젝트 기준 경로. 문제가 있는 스크립트는 ScriptError. |
| `to_python` | `(sc)` | 스크립트 → 같은 일을 하는 Python(eqn.script.session — 같은 명령·같은 기록·같은 실행 기록). |

### eqn.script.session

`session(project='.', **kw)`

스크립트 실행 하나를 연다 — with 블록으로 쓰면 끝에서 실행 기록(run:)을 남긴다. 매개변수는 `Session`과 같다.

**예**

<!-- skip -->
```python
import tempfile, os
p = eqn.Project.create(os.path.join(tempfile.mkdtemp(), "demo"))
with eqn.script.session(p.root, script="FLOWS/check.eqs") as s:
    _ = s.cmd("assemble main")
    _ = s.cmd("hs main --range 2010Q1:last")
    _ = s.expect("hs", "Y.rmspe < 5%")
s.result.id, s.result.exit_code, [x.status for x in s.result.steps]
# ('run:check_0001', 0, ['ok', 'ok', 'ok'])
```

## 41. 스크립트 실행 `eqn.script.session(…)`

| 이름 | 서명 | 설명 |
|---|---|---|
| `values` | `(text='')` | 줄에 들어갈 값 — 매개변수와 내장 값(지금 프로젝트 상태로 — 앞 단계가 회차를 바꿨으면 새 회차). |
| `records` | `(kind=None, filt=None)` | 이 실행의 가장 뒤 단계가 만든 그 종류의 기록(filt: 시나리오·부품·분석·모형 이름) — 없으면 []. |
| `resolve` | `(text)` | 줄의 {이름}을 값으로. |
| `section` | `(title)` | 단계 묶음 제목(## 제목). |
| `cmd` | `(line, where=None)` | 명령 한 줄(등록부의 명령 — 앞의 equion은 빼도 된다)을 같은 프로세스에서. 실패하면 ScriptStop(그 종료 코드). |
| `expect` | `(target, cond, stop=True, where=None, _source=None)` | 확인 — target(hs·sim·est = 이 실행의 앞 단계 기록, 또는 기록 이름)의 지표가 조건을 지키나. 어긋나면 stop이면 ScriptStop(2), 아니면 표시하고 계속. 지표: HS `Y.rmspe`·`Y.mae_pct`·`Y.mae`·`Y.me`·`failed`·`fallback` · 전망 `Y.growth[2021]`·`Y.level[2021Q4]` · 추정 `r2`·`dw`·`se`·`failed`(기준 미달 식 수)·`passed`·`n`. |
| `expect_line` | `(line, where=None)` | `expect 대상 조건 [--stop·--flag]` 한 줄. |
| `py` | `(line, where=None)` | Python 단계 `py x.py [--set 이름=값 …]` — `equion run x.py`(보고서 폴더 없이)를 프로젝트 폴더에서. 명령줄에서만(python=False면 허용 안 됨). |
| `close` | `(code=None)` | 실행 기록을 쓴다(한 번만) — 종료 코드: 멈춘 단계의 코드 · 아니면 fail_on에 걸리면 2 · 아니면 0. |

## 42. 단계 결과 `StepResult`

| 이름 | 서명 | 설명 |
|---|---|---|
| `brief` | `속성` | 한 줄 요약 — 명령 출력의 첫 줄 또는 까닭. |
| `to_dict` | `()` | 사전(출력 글은 steps/NN.txt에). |

## 43. 실행 결과 `p.run_script(…)`

| 이름 | 서명 | 설명 |
|---|---|---|
| `flags` | `속성` | 표시한 단계(!). |
| `records` | `속성` | 이 실행이 만든 기록(단계 순). |
| `text` | `()` | 명령줄에 보이는 끝 줄(단계 줄은 실행하면서 보인다). |
| `to_dict` | `()` | 명령줄 --json과 같은 사전. |

## 44. 미리보기 `p.run_script(…, dry_run=True)`

| 이름 | 서명 | 설명 |
|---|---|---|
| `ok` | `속성` | 문제가 없으면 참. |
| `text` | `()` | 명령줄에 보이는 글. |
| `to_dict` | `()` | 사전. |

## 45. 스크립트 검사 `p.check_script(…)`

| 이름 | 서명 | 설명 |
|---|---|---|
| `ok` | `속성` | 문제가 없으면 참. |
| `text` | `()` | 명령줄에 보이는 글. |
| `to_dict` | `()` | 사전. |

## 46. 재연 결과 `p.replay_run(…)`

| 이름 | 서명 | 설명 |
|---|---|---|
| `exit_code` | `속성` | 같으면 0, 다르면 2. |
| `text` | `()` | 명령줄에 보이는 글. |
| `to_dict` | `()` | 사전. |

## 47. 받은 원자료 `p.data_inbox()`

| 이름 | 서명 | 설명 |
|---|---|---|
| `ok` | `속성` | 넣을 수 있거나 넣었으면 참. |
| `text` | `()` | 한 줄. |
| `to_dict` | `()` | 사전. |

## 48. 작업 기록 저장소 `p.work`

| 이름 | 서명 | 설명 |
|---|---|---|
| `split` | `(rid)` | 'est:cons_c5' → ('est', 'cons_c5'). |
| `dir` | `(kind)` | 그 종류의 기록 폴더(work/<종류>). |
| `exists` | `(kind, name)` | 그 기록이 있으면 참. |
| `names` | `(kind)` | 그 종류의 기록 이름(가나다순). |
| `next_name` | `(kind, prefix)` | prefix_0001, prefix_0002 … — 같은 앞글자의 가장 큰 번호 다음. |
| `check_new` | `(kind, name)` | 새 기록 이름을 검사한다 — 글자가 틀리거나 이미 있으면 RecordError(기록은 고치지 않는다). |
| `write` | `(kind, name, meta, files, summary, log=None)` | 기록 하나를 쓴다 — files의 값은 글자·DataFrame(CSV)·dict(JSON). record.json·summary.md를 더하고 log.jsonl에 한 줄. |
| `get` | `(rid, kind=None)` | 기록 하나. kind를 주면 그 종류여야 한다. |
| `log` | `()` | log.jsonl의 줄(지운 기록은 뺀다) — 만든 순. |
| `records` | `(kind=None)` | 기록 목록(만든 순). |
| `marks` | `()` | {기록: {pinned, memo}}. |
| `mark` | `(rid, pinned=None, memo=None)` | 고정(pinned)·메모 — 기록 자체는 그대로, marks.json에만. |
| `remove` | `(rid)` | 기록 폴더를 지운다(정리 — 사람이 고를 때만). log.jsonl의 줄은 남고 목록에서 빠진다. |

## 49. 작업 기록 하나 `p.work.get(…)`

| 이름 | 서명 | 설명 |
|---|---|---|
| `id` | `속성` | 기록 이름 `종류:이름`. |
| `file` | `(fname)` | 기록 폴더 안 파일의 경로. |
| `read_json` | `(fname)` | 기록 폴더의 JSON 파일. |
| `read_csv` | `(fname, index_col=0)` | 기록 폴더의 CSV(첫 열이 기간 라벨). |
| `summary_md` | `()` | 사람이 읽는 카드(summary.md). |

## 50. 바뀜 기록 `p.history`

| 이름 | 서명 | 설명 |
|---|---|---|
| `scan` | `()` | 명령 밖에서 바뀐 정의 파일을 '바깥' 바뀜으로 적는다. 처음이면 지금 내용을 기준으로 삼고 아무것도 적지 않는다. |
| `write_files` | `(new, who, how, note='', reverts=None)` | 정의 파일을 고치고 바뀜 기록을 남긴다 — new: {경로: 새 내용(None이면 지움)}. 먼저 바깥 바뀜을 따로 적는다. |
| `list` | `()` | 바뀜 기록(오래된 것부터). |
| `get` | `(cid)` | 바뀜 하나. |
| `revert` | `(cid, who, how=None)` | 그 바뀜 앞의 내용으로 되돌린다(그 뒤에 같은 파일이 또 바뀌었어도 — 지금 내용과의 차이가 새 바뀜으로 남는다). |

## 51. 바뀜 하나 `p.history.get(…)`

| 이름 | 서명 | 설명 |
|---|---|---|
| `text` | `()` | 명령줄에 보이는 짧은 글. |
| `to_dict` | `()` | 명령줄 --json과 같은 사전. |

## 52. 고급(엔진 수준) — 드라이버·확장용, 바뀔 수 있다

| 이름 | 서명 | 설명 |
|---|---|---|
| [`Data`](#eqndata) | `클래스(file_path=None, index_col=None)` | (고급) 자료 객체 — 시계열 DataFrame과 지시자 열(@trend·@seas·@d 등)을 관리한다. 워크파일이 안에서 쓴다. |
| [`Equation`](#eqnequation) | `클래스(equation_str, data, auto_fix=True, method=None, instruments=None, coefficients=None, cov=None, lags=None, weights=None, wtype='ivar', gmm_weight=None, iterate=False)` | (고급) 방정식 한 개의 엔진 객체 — 추정(OLS·TSLS·NLS·WLS·GMM·LIML·고정)과 연립 풀이용 IR을 가진다. |
| [`Model`](#eqnmodel) | `클래스(data, equations=None)` | (고급) 연립방정식 모델의 엔진 객체 — 블록 분해·Newton 풀이·과거 재현·시나리오 실행. |
| `Scenario` | `클래스(name='baseline', alias=None)` | 전망/정책충격 시나리오 — 외생 경로·exclude·조정항·충격·목표추적 묶음. |
| `WorkTable` | `클래스(name='untitled', freq='Q', start=None, end=None, register=True)` | EViews workfile 대응. 주기·표본을 보유하고 데이터/방정식/모델을 소유한다. |
| [`Workspace`](#eqnworkspace) | `클래스()` | 열려 있는 WorkTable들을 이름으로 보관하고 활성 테이블을 추적한다. |
| `current` | `()` | 현재 활성 Work Table을 반환한다(Workspace.active). |

### eqn.Data

`Data(file_path=None, index_col=None)`

(고급) 자료 객체 — 시계열 DataFrame과 지시자 열(@trend·@seas·@d 등)을 관리한다. 워크파일이 안에서 쓴다.

보통은 워크파일 API(`eqn.wfopen`·`eqn.datasets.load`)를 쓴다. 엔진을 직접 다룰 때는 `wf._data` 대신 파일에서 만든다.  

**예**

<!-- skip -->
```python
d = eqn.Data(eqn.datasets.path("toy_q"))           # 엔진 객체는 진행 로그를 찍는다
# [OK] 데이터 로드: toy_q.csv (200행 x 10열)
d.data.shape
# (200, 10)
```

### eqn.Equation

`Equation(equation_str, data, auto_fix=True, method=None, instruments=None, coefficients=None, cov=None, lags=None, weights=None, wtype='ivar', gmm_weight=None, iterate=False)`

(고급) 방정식 한 개의 엔진 객체 — 추정(OLS·TSLS·NLS·WLS·GMM·LIML·고정)과 연립 풀이용 IR을 가진다.

보통은 워크파일의 방정식 객체(`wf.equation("이름").ls(…)`)를 쓰고, 엔진 객체는 그 `.eq`로 얻는다.  

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
e = wf.equation("eq_i").ls("I c Y(-1) R").eq
type(e).__name__, e.target, e.method
# ('Equation', 'I', 'ols')
```

### eqn.Model

`Model(data, equations=None)`

(고급) 연립방정식 모델의 엔진 객체 — 블록 분해·Newton 풀이·과거 재현·시나리오 실행.

보통은 워크파일의 모델 객체(`wf.model("이름")`)를 쓰고, 엔진 객체는 그 `.engine`으로 얻는다(직접 simulate 등).  

**예**

<!-- skip -->
```python
wf = eqn.datasets.load("toy_q")
m = wf.model("toy").merge("I c Y(-1) R", "CN c Y CN(-1)").append("Y = CN + I + G")
eng = m.engine
type(eng).__name__, sorted(eng.get_endogenous_variables())
# ('Model', ['CN', 'I', 'Y'])
```

### eqn.Workspace

`Workspace()`

열려 있는 WorkTable들을 이름으로 보관하고 활성 테이블을 추적한다.

전부 클래스 메서드(모듈 전역 단일 작업공간). 월별/연별 등 여러 주기의  
워크테이블을 동시에 열어두고 `Workspace.use(name)`으로 전환한다.  

## 22. 명령줄 `equion`

종료 코드: 0 성공 · 1 스크립트 오류 · 2 풀이 실패(`--fail-on`) · 3 입력 오류 · 130 중단(Ctrl+C). 자세한 쓰임은 [명령줄 참조](cli.md).

| 명령 | 옵션 | 설명 |
|---|---|---|
| `run` | --dry-run --fail-on --format --from --help --interactive --interval --json --log --manifest-to --no-report --out --params --plotlyjs --project --quiet --redact --replay --run-id --set --smpl --threads --verbose --watch | 스크립트를 실행한다 — .py는 보고서 폴더(out/), Equion 스크립트 .eqs는 실행 기록(work/run/) |
| `check` | --data --freq --help --json --project --set --smpl --strict | 실행 없이 방정식 파일·스크립트를 검사한다 |
| `info` | --all --freq --help --json | 데이터·워크파일·방정식 파일·보고서 폴더 요약(경로 없으면 실행 환경) |
| `convert` | --allow-pickle --help --name | 옛 저장 형식(레거시 pickle·.wt·.mmw)을 워크파일(.eqw)로 |
| `new` | --bare --force --help --template | 새 프로젝트 폴더(예시 데이터·방정식·스크립트) |
| `assemble` | --help --json --project | 프로젝트의 모형을 조립해 검사한다(계산 없이 — 내생·외생·겹친 목표·모르는 변수) |
| `ident` | --check --help --json --project --range --strict --tol | 프로젝트의 항등식을 보이거나(--check) 실측으로 계산해 견준다 |
| `data` | --help | 프로젝트의 자료 회차 — 목록·원자료 넣기·만들기·바꾸기·차이·영향 |
| `est` | --adopt --adopted --as --cov --for --help --json --method --project --sim --smpl | 식 하나를 추정해 기록을 남긴다(부품 또는 식 글자 — 후보) |
| `adopt` | --help --json --part --project | 추정 기록을 부품의 채택 계수로(블록 파일의 줄·채택표를 고치고 바뀜 기록에) |
| `compare` | --help --json --part --project --target | 기록 비교 — 추정 후보(적합·진단·기준·단독 모의) 또는 HS(변수별 RMSPE) |
| `hs` | --as --help --json --mode --project --range --replay --swap --vs | 과거 재현을 풀고 기록을 남긴다(바꿔 끼우기·전후 비교·그때 그대로 다시) |
| `sim` | --as --help --json --mode --model --project --range --vintage --vs | 전망·시나리오를 풀고 기록을 남긴다(가정 세트·보정항·시나리오 파일) |
| `propose` | --help | 제안 — 파일을 바꾸기 전에 보여 주기(만들기·목록·보기·적용·버림) |
| `export` | --help --json --project --xlsx | 기록의 값·값의 종류·출처를 엑셀로 |
| `work` | --help | 작업 기록 — 목록·보기·고정·메모·정리 |
| `history` | --help | 바뀜 기록 — 정의 파일이 누가·언제·어떻게 바뀌었나, 되돌리기 |
| `an` | --help | 분석 — 등록부의 분석 하나 = 기록 하나(an:) · 목록·남기기 |
| `note` | --help | 노트 — ```equion 블록을 실행해 결과 구역을 채운다 · 검사 |
| `report` | --help | 보고서 — 결과만 보내기(명령 블록 없이) · 검사 · 새 기록으로 바꾸기 |
| `script` | --help | 스크립트(.eqs) — 작업 기록으로 초안 · 같은 일을 하는 Python으로 |
| `guide` | --force --help --install --path --project | Claude(AI)용 모형 작업 안내 · Claude Code 스킬 초안 |
