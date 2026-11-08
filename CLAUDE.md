# CLAUDE.md

이 파일은 Claude Code가 `equion` 저장소(패키지 **Equion**)에서 작업할 때 참고하는 가이드입니다.

## 프로젝트 개요

**Equion** — 개별 방정식과 비선형 연립방정식의 추정·풀이·시뮬레이션 패키지(`equion/`). 방정식 텍스트를
**파서 → IR**로 바꿔 추정하고, **블록 분해 + 해석적 자코비안 Newton**으로 연립 풀이·Historical
Simulation(HS)·전망·시나리오를 수행한다. **방정식(회귀 체계)은 언제든 바뀌는 입력**이고 엔진이 그것을
견고하게 받아야 한다. 패키지는 특정 모델에 묶이지 않는다.

- **저장소 분리(D30, 2026-11-08)**: 이 저장소는 `macro_model`에서 패키지만 떼어 **새 기록**으로 시작했다. 한국 거시모델
  (자료·방정식·HS 기준선·드라이버·한국 모델 시험·`IMPROVEMENTS.md`)은 비공개 저장소 `macro_model`에 남고, 그쪽이 `equion`을
  판 번호로 가져다 쓴다. **이 저장소에는 실제 자료를 넣지 않는다** — 시험·문서·예제는 예제 자료 `eqn.datasets`만 쓴다.
- **이름(D16)**: 패키지·import·명령 `equion`(별칭 `import equion as eqn`), 데스크톱 앱 **Equion Desk**
  (설치 파일 `EquionDesk-<버전>-setup.exe`, Windows 전용 — D29). 0.5.0에서 `macromodel` → `equion`으로 바꿨다 —
  옛 `.mmw` 워크파일·`macromodel-run` 보고서·레거시 pickle(`macromodel.*` 경로)·`MACROMODEL_PARAMS`는 계속 읽는다.
- Equion **0.7.0** (2026-10-30, 공개 버전 하나 — 엔진 형식 표시 `ENGINE_VERSION`은 내부 값). 결정 D1~D30(`docs/DECISIONS.md`),
  진행 `docs/ROADMAP.md`, 바뀐 점 `CHANGELOG.md`. 사용자 문서 첫 페이지 `docs/README.md`(D27), 문서 검사 `docs/build_docs.py`.
- **세 단계(D1)**: ① 라이브러리 — 워크파일 API `import equion as eqn` (완료) ② CLI `equion run` (완료)
  ③ 데스크톱 앱 Equion Desk(lectern 스타일, **Windows 전용**(D29) — 패키지는 3 OS 그대로) — **향후 프로젝트, 지금은 기획만**.
  만들 때는 이 저장소 `desk/`의 별도 패키지 `equion-desk`(uv workspace, 의존은 `equion-desk → equion` 한쪽만, D28).

## 실행 환경

**`uv` 자체 가상환경(`.venv`)**. 의존성은 `pyproject.toml`에 **범위**(numpy>=2.1·pandas>=2.2.2·scipy>=1.14·openpyxl,
Python>=3.12 — 회귀 패키지 없음, D17·D19), 이 저장소 환경은 **`uv.lock`이 정확한 버전·해시로 고정**(numpy 2.4.4·pandas 3.0.2·
scipy 1.17.1). pyarrow·plotly는 선택 기능(`equion[parquet]`·`[plot]`, dev 그룹엔 포함). Python은 `.python-version`(3.13).
문서의 출력은 `uv.lock` 판으로 만든 것이다.

> BLAS·CPU 차이(OpenBLAS 커널, MKL)로 말자리 수치가 달라질 수 있다. 결과 비교는 **md5가 아니라 허용오차**로 한다.

```bash
uv sync                 # 노트북 커널 포함 + equion 편집 가능 설치(명령 .venv/bin/equion). 코어만: --no-dev

uv run equion new demo                        # 바로 도는 예시 프로젝트(자료·방정식·스크립트)
uv run equion check demo/EQUATIONS/model.txt --data demo/DATA/data.csv   # 실행 없이 검사
uv run python docs/make_api.py                # docs/reference/api.md 다시 만들기(공개 docstring을 고쳤을 때, --check)
uv run python docs/build_docs.py              # 문서 예제 실행 → 출력 채우기 · examples/ 내보내기 (--check: 바꾸지 않고 검사, --only 경로)

uv run python tests/test_engine.py            # 엔진 회귀 104/104 (일관성·DSL·보안·구조·HS·시나리오·기간 모듈·입력 한도/퍼징·안정성·기여도 분해·희소·stacked MCE…)
uv run python tests/test_workfile.py          # 워크파일 API 83/83 (로그·npz 저장·선택 의존성·메타데이터·페이지·주기 변환·Denton/Chow-Lin·STL 포함)
uv run python tests/test_cli.py               # 명령줄 68/68 (보안·Windows 인코딩 포함)
uv run python tests/test_scenarios.py         # 상황별 시나리오 92/92 (합성 자료 — 경계·오용·연/월·명령줄·예제 자료·기간 표기·플랫폼 무관)
uv run python tests/test_stats.py             # 자체 통계 166/166 (OLS·WLS·GMM·LIML·PDL·AR 오차·ECM·예측 평가·시스템(SUR·3SLS·FIML)·VAR·VECM·강건 공분산·진단·단위근)
uv run python tests/test_ast_formula.py       # 66/66 (레거시 formula 유틸)
uv run python tests/test_100_equations.py     # 100/100
uv run python tests/test_error_equations.py   # 에러 검증 시각화
uv run python tests/test_docs.py              # 문서 검사(build_docs --check: 예제·출력·링크·API 설명과 예제·doctest)

uv run pytest                                 # 위 묶음을 한 번에(파일마다 test_suite())

# 의존성 추가/제거: uv add <pkg> / uv remove <pkg>  (pyproject.toml·uv.lock 자동 갱신)
# CI(.github/workflows/ci.yml): locked(3 OS × py3.12~3.14)·minimal(선택 의존성 없이)·lowest·latest·audit
```

> ⚠ uv는 **0.13.7 이상**(`pyproject.toml`의 `[tool.uv] required-version` — CI의 setup-uv도 이 값을 따른다).
> 옛 uv(0.5.x)는 pyproject를 고치면 lock의 무관한 마커까지 다시 썼고, 저장소 최상위에서 `uv run equion`이 실패했다.
> `pyproject.toml`의 의존성·버전을 고치면 다음 `uv run`이 lock을 갱신하므로 `git diff uv.lock`으로 바뀐 줄을 확인한다.
> 줄바꿈은 `.gitattributes`가 LF로 고정한다(Windows의 `core.autocrlf`와 무관 — 문서 도구·`equion new`도 LF로 쓴다).
> 패키지는 설치형(hatchling, `[project.scripts] equion`)이라 `uv sync`가 편집 가능 설치한다(D6).

## 파일 구조

### `equion/` 패키지

| 모듈 | 역할 |
|------|------|
| `formula/parser.py` | **DSL 파서**: 줄 분류(최상위 `=`·`c(n)`), 괄호 깊이 기준 항 분리, EViews 표기(`X(-1)`·`^`·`@pc`…·시차범위), 꼬리 지시자(`@smpl`·`@inst`·`@coef`·`@start`), **허용 목록 검증(보안)** |
| `formula/ir.py` | **IR**: 시계열 연산 → `Var(이름,시차)` 산술식 전개, 벡터 평가(추정), 코드 생성(풀이), 기호 미분(자코비안), 표시 문자열 |
| `formula/ast_formula.py` | (레거시) user→pandas 문자열 변환·정규화·대소문자 교정·매크로. 입력은 허용 목록 검증. 풀이 경로는 쓰지 않음 |
| `data/dataset.py` · `io.py` | `Data`(주기 인지 `@seas`/`@d`/`@step`/`@trend`, 지시자 레지스트리, `extend`·`fill_series`) · 파일 읽기 |
| `data/transform.py` | 주기 변환(집계·확장)·Denton·Chow-Lin·STL·고전 분해(D26) — 시간 인덱스 연산은 periods를 거친다 |
| `data/periods.py` | **기간·주기 연산은 모두 여기**(주기 추론·Period 변환·기간 첫날 인덱스·리샘플·개월 이동·`locate`) — 다른 모듈은 pandas 시간 API를 직접 부르지 않는다(pandas 버전 변화 흡수). 인덱스에 pandas freq를 달지 않는다(분기 라벨 `.loc["2001Q2"]`가 회계 분기로 어긋남). 다른 주기의 시점 표기(연간에 `2000Q1`)는 오류. `worktable/freq.py`는 옛 이름 재노출 |
| `estimation/equation.py` | `Equation` — OLS·TSLS·NLS(해석적 자코비안)·fixed(결과는 `equion.stats`), 계수 공분산 `cov`·`lags`, 중심화 R², 시스템 인터페이스(`target`·`system_rhs`·`coef_vector`), 번들 직렬화 |
| `stats/` | **자체 통계(D17·D20~22)**: `regression.py`(OLS 유사역행렬 — 0.5.0까지의 외부 패키지와 같은 계산 순서, TSLS·NLS·fixed 결과 `Results`) · `robust.py`(HC0~3·HAC) · `diagnostics.py`(LM·Ljung-Box·White·BP·ARCH·JB·RESET·Wald·Chow·CUSUM·재귀) · `unitroot.py`(ADF·KPSS·Engle-Granger·Johansen) · `_tables.py`(MacKinnon·MHM 수치표, 고지 `THIRD-PARTY-NOTICES.md`) · `forecast.py`(예측 평가·Diebold-Mariano) · `system.py`(SUR·2SLS·3SLS·FIML) · `var.py`(VAR·VECM) · `result.py`(`TestResult`) |
| `system/analyzer.py` | `SystemEquation`·`ModelSystem`: 정규화 매칭(Kuhn)·정방성/중복/미지 변수 검사·블록 분해(Tarjan)·구조 캐시 |
| `system/compiler.py` | 블록 잔차·자코비안 파이썬 함수 생성(색인 참조, builtins 없음) |
| `system/solver.py` | Newton(스케일링·라인서치, 큰 블록은 희소 LU) / Gauss-Seidel / Broyden / hybr / lm + 폴백 |
| `system/simulate.py` | 기간 루프: dynamic·static·fit, `on_missing`·`on_fail` 정책, 기간 상태, control, MCE(Fair-Taylor·stacked) |
| `system/model.py` | `Model` — `simulate`·`hs`·`solve`·블록 보기·`input_gaps`·시나리오 위임. 결과저장은 reporting |
| `system/analysis.py` | 동태 안정성(선형화 동반행렬 고윳값)·시나리오 기여도 분해(Shapley) |
| `scenario/scenario.py` | `Scenario`(override·exclude·add-factor·충격·control)·전망 보조·확률적 모의·control·승수 |
| `reporting/results.py` · `charts.py` | 결과 CSV(상태 열 포함) / 표시·차트 |
| `workfile/` | **워크파일 API(라이브러리 1단계)**: `workfile.py`(`Workfile`·`wfopen`·`wfcreate`·smpl·genr·read/write·`.eqw` 저장·`ecm`·`forecast_eval`·`meta`·`page`·`convert`·`seas`) · `objects.py`(방정식·모델·시나리오·그래프·표 객체, `SolveResult`, `ECMResult`) · `sysobj.py`(시스템 객체) · `varobj.py`(VAR·VECM 객체) · `output.py`(출력 객체·스풀·`eqn.show`·`eqn.verbose`) · `runtime.py`(`eqn.params`). 엔진 API 위의 얇은 층 |
| `cli/` | **명령줄(2단계)**: `commands.py`(argparse·`run`/`check`/`info`/`new`·`--threads` 재실행·`--watch`) · `runner.py`(스크립트 실행기·로그·종료 코드·`--fail-on`) · `report.py`(보고서 폴더·`manifest.json`·`report.html`) · `check.py` · `info.py` · `new.py`. `python -m equion` = `equion/__main__.py`. 실행 기록은 `workfile/runtime.py`의 `RunRecord` |
| `worktable/worktable.py` | (엔진 수준) `WorkTable`/`Workspace` 세션: 주기·표본, `hs(start='auto')`, `forecast`·`extend`·`simulate`·`blocks`, 번들 v3 저장/복원(v2 읽기) |
| `worktable/freq.py` · `_serial.py` | 주기 유틸·방정식 파일 파서(분류는 parser) / 번들 JSON 헬퍼 |
| `datasets/` | **예제 자료(D27)**: `toy_q`·`toy_a`·`toy_m`·`klein_like`(참 모형을 아는 가상 자료, 만드는 코드 `_make.py`·고정 시드) · `load`·`describe`·`path`·`klein(path)`(사용자가 구한 실제 Klein 자료). 문서·docstring·시험 예제는 이것만 쓴다 |
| `version.py` · `_compat.py` | 엔진 버전(`project_version()`=패키지 버전) · 이름 변경 전 레거시 pickle 읽기(`macromodel.*` → `equion.*`) |

### 루트 디렉토리 레이아웃

| 위치 | 내용 |
|------|------|
| `tests/` | `test_engine.py` · `test_workfile.py` · `test_cli.py` · `test_stats.py` · `test_scenarios.py`(상황별 시나리오) · `test_ast_formula.py` · `test_100_equations.py` · `test_error_equations.py` · `test_docs.py`. 모두 예제 자료·합성 자료로 돈다. 기준값 `fixtures/{stats,estimation,data}_reference.json` — 만드는 `fixtures/make_*_reference.py`는 statsmodels·linearmodels·mpmath가 있는 **별도 환경**에서만(`PYTHONPATH=.`). `uv run pytest`가 파일마다 `test_suite()`를 부른다 |
| `docs/` | **사용자 문서(D27, Markdown 원본)**: `README.md`(첫 페이지) · `start/`(설치·첫 모델·치트시트) · `tutorial/`(1~8) · `howto/`(레시피) · `explain/`(방정식 문법 `equations.md`·추정·풀이·시나리오·동태·검증·엔진 API) · `reference/`(`api.md` **자동 생성** — `make_api.py` · 명령줄·함수·출력·오류·파일 형식·예제 자료) · `cases/`(Klein형) · `eviews.md` · `en/`. 도구 `build_docs.py`·`make_api.py`. 프로젝트 문서 `DECISIONS.md`(D-번호) · `ROADMAP.md`. `USER_GUIDE.md`·`EQUATION_GUIDE.md`·`API.md`는 새 위치 안내만 |
| `examples/` | `start/`·`tutorial/` 스크립트와 `notebooks/` — **문서에서 자동 생성**(`build_docs.py`), 손으로 고치지 않는다 |
| `.github/` | `workflows/ci.yml`(locked 3 OS × py3.12~3.14 · minimal · lowest · latest · audit) · `release.yml`(태그 → 휠·설치 시험, PyPI는 `PYPI_PUBLISH` 변수로만) · `dependabot.yml` |
| `out/` · `WT/` | CLI 보고서 `out/<실행ID>/` · 워크파일 `.eqw/`·Work Table `.wt/` 번들(자동 생성·git 제외) |
| 루트 파일 | `README.md`(저장소 소개) · `README.en.md`(English) · `LICENSE`(MIT) · `THIRD-PARTY-NOTICES.md`(포함한 외부 자료 고지 — 수치표·plotly.js) · `CHANGELOG.md` · `CLAUDE.md` · `VERSION` · `pyproject.toml` · `uv.lock` · `.python-version` · `.gitignore` · `.gitattributes`(줄바꿈 LF) |

## 방정식 파일 규칙

한 줄에 한 방정식. `#` 이후는 주석(인라인 포함). 문법 전체는 `docs/explain/equations.md`(함수 표 `docs/reference/functions.md`).

- **분류(parser.classify_line)**: 최상위 `=` 없음 → 추정식, `=` 있고 계수 `c(n)` 없음 → 항등식,
  `=`와 `c(n)` → NLS 추정식. **등호 양옆 공백 무관.** `c`(상수항) 유무로 분류하지 않는다.
- **항 분리**: 괄호 밖 공백만 구분자(괄호 안 공백 자유). 단독 연산자는 앞뒤를 잇는다.
- **목표변수**: 좌변의 첫 변수(EViews 규칙). 항등식 좌변도 식이어도 된다(`log(X) = ...`).
- 시계열: `.t(-N)`=`X(-N)`, `.qoq`/`.yoy`(주기별 시차: 분기4·월12·연1)/`.gr(N)`/`.diff`/`.ma(N)`,
  `d(x,n,s)`·`dlog`, `@pc/@pch/@pca/@pcy/@pchy/@movav/@movsum`, `^`=`**`. 연간은 `.qoq` 금지.
- 지시자: `@seas`(분기 `_Q*`·월 `_M*`, 연간 오류)·`@trend`·`@d(P)`·`@step(P)`(주기별 시점 표기),
  `.t(-1 to -2)`/`X(-1 to -2)` 시차범위, `@smpl`, `@def`, 추정법 `@inst`·`@coef`·`@start`.
- **변수명 대소문자 무시**(`canonicalize_columns`, EViews 시차 표기 포함). 대소문자만 다른 중복
  열은 `Data.load` 시 경고. 함수명과 같은 변수명·`C` 변수는 불가 — 식·시리즈 이름에 쓰면 오류(`parser.reserved_name_error`),
  그런 열이 든 파일은 열 때 경고. 방정식 파일은 UTF-8(BOM 무관), cp949는 경고하고 읽는다(`data.io.read_text`).

## 엔진 v3 핵심 (parser → IR → system)

- **추정과 풀이는 같은 IR을 쓴다.** IR은 모든 시계열 연산을 시차 잎 산술식으로 전개한 것이라
  "실측을 넣은 컴파일 잔차 = OLS 잔차"가 구조적으로 성립해야 한다. `ir.py`·`parser.py`·
  `compiler.py`를 고치면 `tests/test_engine.py` A·B절(번역 일관성)이 반드시 통과해야 한다.
- **보안**: 사용자 텍스트는 파서의 허용 목록을 통과해야만 IR이 된다. 생성 코드는 변수 이름 대신
  색인만 쓰고 builtins 없이 실행된다. 새 연산·함수를 추가할 때도 허용 목록 방식을 유지할 것
  (`AT_FUNCTIONS` 등록 + `ir._Builder.apply_function` 전개 규칙).
- **실패 정책**: 미수렴 블록은 기본 `on_fail='actual'`(실측 대체·`fallback` 표시), 입력 결측은
  `on_missing='exclude'`(그 식만 그 기간 제외·`partial`). 실패 해를 다음 기간 시차로 흘려보내지
  않는 것이 핵심 불변식이다. 통계는 고정·대체된 변수-기간을 제외한다.

## 워크파일 API·확장 원칙 (DECISIONS D2~D14)

- **라이브러리 진입점은 워크파일 API**(`eqn.wfopen` → `wf.smpl` → `wf.equation(…).ls(…)` → `wf.model(…)` →
  `m.scenario(…)`/`m.solve()`). 엔진 API(`WorkTable`/`Model`/`Equation`)는 그 아래 층으로 유지한다.
  표본(smpl)은 추정·풀이·genr·그래프의 기본 구간, 풀이 결과는 별칭 시리즈(`X_0`, `X_1`)로 워크파일에.
- **Python 완전 연동(D14)**: 새 기능은 pandas·numpy 객체를 받고 돌려준다. 별도 스크립트 언어를 만들지 않는다.
- **의존성(D17)**: 회귀·검정·수치표는 자체 구현(`equion/stats`). 새 필수 의존성은 결정 기록(D-번호)으로만, 외부 자료(표)를
  옮기면 `THIRD-PARTY-NOTICES.md`에 고지. 시간 인덱스 연산은 `data/periods.py`만 거친다. 외부 결과와 비교하는 기준값은
  `tests/fixtures`에 고정하고, 외부 구현이 부정확한 곳(예: 재귀 잔차 갱신 공식)은 독립 계산과 비교한다.
- **명령줄(D5·D6·D15)**: 스크립트는 평범한 Python(`eqn.params`로 매개변수, `--smpl`은 새 워크파일 표본과
  `smpl` 매개변수). 종료 코드 0 성공·1 스크립트 오류·2 풀이 실패(`--fail-on`)·3 입력 오류(사용법 오류 포함)는
  자동화 약속이라 바꾸지 않는다. 보고서 `manifest.json`은 `format: equion-run`·`format_version` — 필드를
  바꾸면 버전을 올린다. 새 입력·출력 경로를 만들면 `runtime.record_input`/`record_output`을 부를 것.
- **하위 사용자 호환**: 비공개 저장소 `macro_model`(한국 모델)이 이 패키지를 판 번호로 쓴다. 공개 API·방정식 문법·
  번들/워크파일 형식을 바꾸면 `CHANGELOG.md`에 적고, 옛 형식은 계속 읽는다.
- **EViews 관련 법적 원칙(D13)** — 지킬 것: 'EViews' 이름·로고를 제품·앱·패키지·아이콘에 쓰지 않는다,
  EViews 설명서·도움말 문장·예제·화면·아이콘을 복사하지 않는다(문서·출력 표는 우리 말로), EViews 프로그램
  역설계나 `.wf1` 같은 비공개 형식 역설계를 하지 않는다, `.prg` 문법 실행기를 만들지 않는다. 기능·방법·
  명령 이름을 Python으로 다시 구현하는 것과 사실에 맞는 비교·상표 고지는 괜찮다. 앱 화면은 lectern을 따른다.

## 작업 시 주의

- **실제 자료를 이 저장소에 넣지 않는다**(D30). 시험·문서·docstring 예제는 `eqn.datasets` 또는 코드로 만든 합성 자료만 쓴다.
- 수치 코어(`formula/parser.py`·`formula/ir.py`·`system/*`·`estimation/equation.py`·`stats/*`)를 바꾸면
  `tests/test_engine.py`(104)·`tests/test_stats.py`(166) + 레거시 시험 2종(`test_ast_formula`·`test_100_equations`)과
  `tests/test_docs.py`(문서 출력)를 다시 돌린다. OLS 계산 순서는 0.5.0까지의 외부 패키지 경로와 같다 — 바꾸지 말 것
  (하위 사용자의 기준선이 바이트 그대로여야 한다). 회귀 비교는 **허용오차**로.
- 엔진은 방정식 내용을 바꾸지 않는다.
- **문서(D27)**: 공개 함수·메서드를 더하거나 바꾸면 docstring(요약·매개변수·돌려주는 것·오류·예 `>>>`·관련 — `docs/reference/README.md`)을
  쓰고 `python docs/make_api.py`. 출력이 바뀌는 코드를 고치면 `python docs/build_docs.py`로 문서 출력·`examples/`를 다시 채우고
  바뀐 숫자를 검토한다(출력은 손으로 고치지 않는다). 새 기능의 완료 기준: 코드 + 시험 + docstring 예제 + 튜토리얼·해설의 절 + 필요한 레시피.
  메시지·표를 바꾸면 `docs/reference/errors.md`·`outputs.md`도 다시 만들어진다(빌드).
- 결과 CSV·번들·보고서는 **cwd 기준** `HS/`·`WT/`·`out/`에 저장된다(`WT/`·`out/`은 git 제외).

## 다음 단계 (참고)

- **ROADMAP 0.8 후보**: 외부 데이터 연결(ECOS·KOSIS), `equion new --template`·오류 메시지의 문서 안내, 비선형(계수) 시스템 추정.
- **공개 전 확인(D30)**: 이름 상표(D16 — KIPRIS·USPTO). 공개 뒤 `macro_model`은 이 저장소의 태그를 가져다 쓰고 패키지 코드를 지운다.
- P3 데스크톱 앱(lectern 스택, Windows 전용 pywebview(WebView2), Python 콘솔 — 프로그램 실행은 CLI와 같은
  `cli.runner`·`cli.report`)은 향후 프로젝트로 기획만 둔다.
- **엔진 후속(선택)**: Model의 `.wt` 역참조 → 주기 값객체, `compare_and_plot`/`show_hs_summary` 본문의 reporting 완전 이관,
  시나리오 결과 번들 저장.
