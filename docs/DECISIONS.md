# 설계 결정 기록

Equion(옛 이름 macromodel)의 큰 설계 결정을 번호(D-n)로 남긴다. 결정을 바꿀 때는 지우지 말고 그 항목에
'변경'을 덧붙인다. 엔진 v3의 설계·검증은 `IMPROVEMENTS.md` §9에 있다.

> 이 저장소는 2026-11-08에 `macro_model`에서 패키지만 떼어 새 기록으로 시작했다(D30). 아래에 나오는 `IMPROVEMENTS.md`·
> `REPO_SPLIT.md`·`PRESENTATION.md`, 한국 모델의 자료·방정식·드라이버(`DATA/`·`EQUATIONS/`·`HS/`·`scripts/`·`kmodel/`)와
> 한국 모델 시험(`tests/test_korea_model.py`·`compare_hs.py`)은 비공개 저장소 `macro_model`에 남아 있다.

> 0.5.0에서 이름이 바뀌었다(D16): 패키지·명령 `macromodel` → `equion`, 별칭 `mm` → `eqn`, 워크파일
> `.mmw` → `.eqw`. 아래 옛 항목의 이름은 당시 그대로 두었다 — 지금 이름으로 읽는다.

---

## D1. 세 단계, 코어 하나 (2026-10-29)

- **결정**: 프로그램을 ① 라이브러리(Python에서 import) ② CLI(`python -m macromodel run 스크립트.py`)
  ③ 데스크톱 앱(Windows/Linux)으로 나눈다. 세 단계는 하나의 **세션 코어**(워크파일·객체 목록·
  출력 수집기) 위의 앞단이고, 같은 스크립트가 노트북·CLI·앱에서 그대로 돈다.
- **이유**: 기능을 한 곳에서만 만들고, 사용 방식(대화형·자동화·화면)만 바꿔 끼운다.
- **순서**: P1 라이브러리 → P2 CLI → P3 데스크톱 (`ROADMAP.md`).
- **변경 (2026-11-08, D29)**: 데스크톱 앱은 **Windows 전용**. 라이브러리·CLI는 Windows·macOS·Linux 그대로.

## D2. 라이브러리 API는 워크파일 중심 객체 API (2026-10-29, 제안 L1-A)

- **결정**: `wf = mm.wfopen(...)`, `wf.smpl(...)`, `wf.genr("X = …")`, `wf.equation("e").ls("…")`,
  `m = wf.model("m")`, `m.merge(...)`, `m.append(...)`, `m.scenario(...)`, `m.solve()` 처럼 **이름 붙은
  객체가 워크파일에 등록**되는 방식. 작업 흐름은 EViews 사용자에게 익숙하게, **문법은 Python**이다.
- **고르지 않은 것**: 지금 API에 별칭만 붙이기(L1-B) — 객체 목록·결과 시리즈 감각이 약함.
  명령 문자열 실행기(L1-C) — EViews 문법을 받아들이는 길이라 하지 않는다(D13).
- **기존 API**: `WorkTable`/`Model`/`Equation`은 내부 계층으로 그대로 두고 하위호환을 유지한다.

## D3. 진입은 최상위 `mm.*` (제안 L2)

- `import macromodel as mm` 후 `mm.wfopen` · `mm.wfcreate` · `mm.show` · `mm.params` · `mm.verbose`.
- **변경 (0.5.0, D16)**: `import equion as eqn` 후 `eqn.wfopen` · `eqn.show` · `eqn.params` …

## D4. 시나리오 결과는 별칭 시리즈로 워크파일에 (제안 L3)

- `m.solve()`는 활성 시나리오의 별칭(기준선 `_0`, 그 밖 `_이름` 또는 지정)을 붙인 시리즈
  (`RGDPSA_0`, `RGDPSA_1` …)를 워크파일에 쓴다. 풀이 구간 밖은 NaN. 그래프·내보내기·앱 표시가
  같은 시리즈를 쓴다. 결과 객체(`SolveResult`)도 함께 돌려준다.

## D5. CLI 스크립트 약속과 명령줄 처리 (제안 S1·C1)

- 스크립트는 **평범한 Python** — 인자는 `p = mm.params(oil=1.0)`로 받고 CLI `--set oil=1.5`가 덮는다.
- 명령줄은 표준 `argparse`(의존성 없음, lectern과 같음).
- **완료(0.4.0)**: `macromodel/cli/`. 세부 약속은 D15.

## D6. 설치형 패키지로 전환 (제안 C2) — P2에서

- `pyproject.toml`의 `package = false`를 바꾸고 `macromodel` 명령을 등록한다. `uv.lock`이 바뀐다.
- **완료(0.4.0)**: 빌드 백엔드 hatchling, `[project.scripts] macromodel = "macromodel.cli:main"`. `uv sync`가
  저장소를 편집 가능 설치하고, 다른 PC에는 `pipx install`·`uv tool install`.

## D7. 데스크톱 앱은 lectern 스택 (제안 D1) — P3에서

- pywebview + 로컬 HTTP 서버(Flask/werkzeug) + 빌드 단계 없는 순수 JS, 라이브러리는 `web/vendor`에
  내장, PyInstaller onedir. 화면 구성·스타일은 사용자의 lectern(github.com/samiblog/lectern)을 따른다.
- 기존 Vue 대시보드(약 1.2천 줄)는 재사용하지 않는다(lectern 원칙: 번들러·프레임워크 없음) — 0.4.0에서 삭제(D11).

## D8. 리눅스 창 엔진은 `pywebview[pyside6]` (제안 W1) — P3에서

- Qt WebEngine(Chromium)이라 Windows의 WebView2와 같은 렌더링, LGPL. `pywebview[qt]`(PyQt6, GPL)는
  MIT 앱 배포와 어긋나므로 쓰지 않는다. 대가: 리눅스 배포본이 수백 MB.
- **폐지 (2026-11-08, D29)**: 앱이 Windows 전용이 되어 Linux 창 엔진이 필요 없다(PySide6를 쓰지 않는다).

## D9. 명령 창은 앱 안의 Python 해석기 (제안 K1) — P3에서

- 콘솔에서 친 명령은 라이브러리 API(D2)이고, 객체 창과 같은 워크파일을 공유한다.
- **변경 (2026-11-09, D31)**: 앱 안의 Python 해석기를 두지 않는다. 명령 창은 앱 오른쪽의 터미널(Claude Code·`python`·`equion`)이고,
  방정식으로 하는 계산은 앱의 작업대가 명령이 있을 때만 한다. 임의의 Python은 앱이 실행하지 않고 터미널에서 `equion run`으로 돌린다.

## D10. lectern 코드는 복사해 가져온다 (제안 R1) — P3에서

- 테마·아이콘·i18n·설명서 보기·xterm/CodeMirror/Plotly 내장본. 같은 소유자의 MIT 코드이며
  `THIRD-PARTY-NOTICES`에 출처를 적는다. 공용 패키지 분리는 하지 않는다.

## D11. 기존 웹 대시보드는 당분간 병행 (제안 B1)

- 다중 사용자 웹 대시보드(FastAPI + Vue)는 그대로 두고, 데스크톱 1차판 뒤 통합 여부를 정한다.
- **변경 (2026-10-29, 제안 B3)**: 웹 대시보드를 **삭제**한다 — 백엔드 `macromodel/dashboard/`, 프론트엔드
  `frontend/`, `scripts/dashboard.py`·`usermgmt.py`, 대시보드 전용 `reporting/api.py`, `tests/test_dashboard_api.py`,
  의존성 fastapi·uvicorn·httpx. 화면은 P3 데스크톱 앱 하나로 간다. 코드는 git 이력(0.3.0까지)에 남는다.

## D12. 앱 이름은 일단 'macromodel' (제안 N)

- 제품·창 제목·아이콘에 'EViews'를 쓰지 않는다(D13). 이름은 나중에 바꿀 수 있다.
- **변경 (2026-10-29, D16)**: 앱 이름은 **Equion Desk**.

## D13. EViews 관련 법적 원칙 (2026-10-29)

- **배경**: 작업 흐름과 기능을 EViews 사용자에게 익숙하게 만들되 법적 문제가 없어야 한다.
  (법률 자문이 아니다 — 공개·상업 배포 전에는 변호사 검토를 받는다.)
- **할 수 있는 것** (보호 대상이 아님 / 위험 낮음):
  - 기능·계량경제 방법(OLS·2SLS·NLS·Gauss-Seidel·Newton·Fair-Taylor·조정항·시나리오) — 학술 지식.
  - 작업 개념(워크파일·표본·모델·시나리오)과 명령 이름(`smpl`·`genr`·`ls`·`merge`·`solve` 등)을
    Python API로 다시 구현 — 한국 저작권법 제101조의2(프로그램 언어·규약·해법 제외), EU 판례
    SAS v WPL(기능·프로그래밍 언어·데이터 형식은 저작권 보호 밖), 미국 Google v. Oracle(재구현의
    공정이용)의 취지.
  - 사실에 맞는 비교·호환 설명("EViews 사용자에게 익숙한 흐름")과 상표 고지.
- **하지 않는 것**:
  - 'EViews' 이름·로고를 제품명·앱 이름·아이콘·창 제목·패키지·도메인에 쓰기, 'EViews 무료판/
    클론' 같은 홍보.
  - EViews 설명서·도움말 문장, 예제 프로그램·예제 데이터, 화면 캡처, 아이콘·그림을 복사하기
    (SAS v WPL에서도 설명서 문장 복사는 침해로 판단됨). 문서·출력 표는 우리 말과 구성으로 쓴다.
  - EViews 프로그램을 역설계·디컴파일하거나 리소스를 뽑아 쓰기, `.wf1` 같은 비공개 파일 형식을
    역설계해 읽기 — EViews에서 xlsx/csv로 내보낸 것을 읽는다.
  - EViews 프로그램 문법(.prg)을 그대로 받아들이는 실행기(L1-C).
  - 화면은 EViews의 그림·대화상자 모양이 아니라 lectern(사용자 자신의 디자인)을 따른다.
- **주의**: EViews를 가진 사용자가 결과를 비교해 보는 것은 보통 사용이지만, 비교 결과를 외부에
  공개할 때는 그 라이선스(EULA)의 벤치마크·공개 조항을 확인한다.
- **상표 고지**: README에 "EViews는 S&P Global Inc.의 등록상표이며, 이 프로젝트는 EViews·S&P
  Global과 관계가 없다"를 둔다.

## D14. Python 완전 연동을 핵심 특징으로 (2026-10-29)

- **결정**: 모든 객체가 pandas·numpy와 바로 오가고, 스크립트는 평범한 Python이다.
  - `wf["X"]`는 pandas Series, `wf["X"] = 어떤 Series·배열`, `wf.genr("X", 함수)`로 임의 Python 계산.
  - 방정식의 `.results`·`.resid`·`.fitted`, 모델의 결과 표는 그대로 statsmodels·scikit-learn·plotly 등
    Python 생태계로 이어진다. 외부 추정 결과는 `.fixed(…, coefs)`로 모델에 넣는다.
  - 반복·함수·클래스·외부 API(데이터 수집 등)는 Python 그 자체로 쓴다 — 별도 스크립트 언어가 없다.
- **이유**: EViews와 다른 이 프로그램의 가장 큰 장점이며, 라이브러리·CLI·앱 콘솔(D9)이 같은
  Python이라 배운 것이 그대로 이어진다.
- **변경 (0.6.0, D17)**: `.results`는 statsmodels 결과가 아니라 자체 `equion.stats.Results`다. 진단·강건 표준오차는
  Equion 메서드로(`eq.diagnostics()`·`eq.ls(…, cov="hac")`), 그 밖의 분석은 pandas 잔차·계수로 이어 간다.

## D15. 명령줄 세부 약속 (2026-10-29, P2)

- **종료 코드**: 0 성공 · 1 스크립트 오류 · 2 풀이 실패(`--fail-on`) · 3 입력 오류 · 130 중단. 스크립트의
  `sys.exit(n)`은 n. argparse의 사용법 오류(기본 2)도 **3**으로 바꾼다 — 2는 풀이 실패 전용(자동화가 구분).
  입력 오류 = 파일 없음·DSL 문법·모델 구조·`merge` 실패(`MergeError`).
- **`--fail-on` 기본은 `failed`**: 엔진 기본 정책(`on_fail='actual'`)의 실패대체(fallback)와 입력 결측의
  일부식 제외(partial)는 성공으로 본다. 더 엄격하게는 `fallback`·`partial`.
- **보고서 폴더** `out/<날짜-시각_스크립트>/`(또는 `--run-id`): `report.html`·`manifest.json`
  (`format: macromodel-run`, `format_version: 1`)·`run.log`·`tables/`·`graphs/`·`plotly.min.js`. 그래프 스크립트를
  폴더에 넣어 인터넷 없이 열린다(`--plotlyjs cdn`으로 끌 수 있음). 같은 `--run-id`는 이전 보고서일 때만
  지우고 다시 쓴다.
- **`--smpl`**: 스크립트가 여는 워크파일의 처음 표본이자, `mm.params`에 `smpl`이 있으면 그 값. 스크립트가
  `wf.smpl(...)`을 직접 부르면 그것이 우선한다(스크립트가 주인).
- **`--threads N`**: BLAS 스레드 환경변수(OMP·OPENBLAS·MKL·VECLIB)를 정해 **하위 프로세스로 다시 실행**한다
  (numpy가 이미 올라온 뒤에는 바꿀 수 없어서). **`--watch`**도 매 실행을 하위 프로세스로 돌려 상태가 섞이지
  않게 하고, 스크립트와 그 실행이 읽은 입력 파일(manifest `inputs`)을 감시한다.
- **실행기 재사용**: `cli.runner.run_script`·`cli.report.write_report`는 P3 앱의 프로그램 실행(F5)에서 그대로 쓴다.
- **고르지 않은 것**: Click/Typer(의존성), 보고서 템플릿 엔진(Jinja 등 — 의존성), 그래프 PNG(kaleido 필요).

## D16. 이름: 패키지 Equion, 데스크톱 앱 Equion Desk (2026-10-29, 0.5.0)

- **결정**: 1·2단계(라이브러리 + 명령줄)를 하나의 패키지 **`equion`**으로(PyPI·import·명령 이름 같음),
  3단계는 그 패키지를 내장한 독립 설치 파일 **Equion Desk**로 한다. Desk는 Equion의 완성도가 높아진 뒤 만든다.
- **뜻**: **Equ**ation + Un**ion** — 개별 방정식을 묶어 연립 체계를 만든다. 매크로 모델에 한정하지 않는다.
- **기준**: EViews(및 Stata·GAUSS·RATS·Estima·EQS 등)가 연상되지 않을 것, 쓰임새(macro·korea)로 좁히지
  않을 것, 짧고 칠 수 있을 것. 2026-10-29 PyPI에 같은 이름이 없고 웹에서 같은 이름의 소프트웨어를 찾지
  못했다. 상표(KIPRIS 9·42류, USPTO) 확인은 공개 배포 전에 한다.
- **별칭 `eqn`**: `eq`는 방정식 객체 변수 이름(`eq = wf.equation(...)`)과 겹치므로 쓰지 않는다.
- **앱 이름을 따로 둔 이유**: Windows는 파일 이름 대소문자를 구분하지 않아 앱 `Equion.exe`와 pip 명령
  `equion.exe`가 PATH에서 부딪힐 수 있다. 설치 파일은 lectern 규칙 `EquionDesk-<버전>-setup.exe`
  (Linux `EquionDesk-<버전>-x86_64.AppImage`).
- **하위호환**: 옛 워크파일 `.mmw`·형식 이름 `macromodel-workfile`, 보고서 `macromodel-run`, 환경변수
  `MACROMODEL_PARAMS`, 레거시 pickle의 `macromodel.*` 모듈 경로(`equion/_compat.py`의 이름 바꿔 찾는
  unpickler)를 계속 읽는다. `import macromodel`은 지원하지 않는다(별칭 패키지를 두지 않음).
- **고르지 않은 것**: Statera(같은 이름 업무 소프트웨어, Stata 연상), Equilibra(Python CGE 패키지
  `equilibria`와 거의 같음), Zygos(법률 소프트웨어 회사), Simeq(설명적 이름 — 상표로 약함), Simora.
- 저장소 이름(`macro_model`)은 그대로다 — 패키지와 한국 모델이 한 저장소에 있다.
- **변경 (2026-11-08, D29)**: 앱은 Windows 전용 — 설치 파일은 `EquionDesk-<버전>-setup.exe` 하나, AppImage는 만들지 않는다.

## D17. 회귀·검정은 자체 구현, 외부 회귀 패키지에 의존하지 않는다 (2026-10-29, 0.6.0)

- **배경(검사 결과)**: statsmodels는 이 코드에서 OLS 한 줄에만 쓰였는데 53MB와 간접 의존성 6개 이상(0.15에서 `formulaic`
  추가)을 끌어왔고, 릴리스가 느리며(3년 정식판 7회, 최대 공백 276일) pandas·scipy 새 버전과 충돌한 이력이 있다
  (의존성 명세의 `pandas!=2.1.0`·`scipy!=1.9.2`). 수치로는 문제가 없었다(0.14.4~0.15.0 계수 차이 0) — 위험은 구조적이었다.
- **결정**:
  - OLS는 무어-펜로즈 유사역행렬(SVD, 기준 1e-15)로 직접 푼다. 0.5.0까지와 **같은 연산 순서**라 분기·연·월 모델 OLS 식
    135개의 계수·표준오차·t·p·F·로그우도·AIC·BIC·잔차·공분산이 **차이 0**, HS 기준선 CSV가 바이트 그대로다.
  - 강건 공분산(HC0~3·HAC)·진단 검정·단위근/공적분 검정을 `equion/stats`에 직접 구현한다(scipy는 분포 함수와 최적화만).
  - 검정의 수치표(MacKinnon 1994·2010, MacKinnon-Haug-Michelis 1999)는 공개 자료값을 옮기고 출처를
    `THIRD-PARTY-NOTICES.md`에 둔다(statsmodels의 정리본 — BSD 3-Clause 고지 포함). 계산 코드는 직접 쓴다.
  - 검증 기준값은 statsmodels로 **한 번** 계산해 `tests/fixtures/stats_reference.json`에 고정하고(만드는 스크립트는 별도
    환경용), 테스트는 외부 패키지 없이 돈다. 외부 구현이 부정확한 곳은 따르지 않는다 — 재귀 잔차는 갱신 공식 대신 시점별
    직접 최소제곱(statsmodels 값은 이 자료에서 상대 3e-4 어긋남), TSLS는 정규방정식 대신 유사역행렬(도구=회귀변수일 때
    OLS와 1e-11 이내, 이전 5e-10).
  - NLS는 IR 기호 미분으로 해석적 자코비안을 넘긴다 — 선형식에서 OLS와 1e-14(이전 수치미분 3.7e-7, scipy 1.14에서 1.3e-6).
  - 기간·주기 연산은 `equion/data/periods.py` 한 곳에서만 pandas를 부른다(주기 추론은 개월 차로 직접 — pandas 4에서
    `infer_freq` 반환형이 바뀜). pandas 3.1에서 우리 코드의 경고 0, pandas 2.2·scipy 1.14 조합에서도 전 테스트 통과.
- **기본값 선택**: ADF·Engle-Granger 시차 선택은 SIC(BIC), 최대 시차 ⌈12(n/100)^¼⌉; KPSS 대역폭은 Hobijn 등(1998);
  HAC 시차 ⌊4(n/100)^(2/9)⌋, HC1·HAC는 n/(n−k) 보정, 강건 공분산의 t·p도 t 분포.
- **원칙**: 새 필수 의존성은 결정 기록으로만 더한다. 외부 자료를 옮기면 고지한다.

## D18. 로그·버전 하나·공개 API·보안 기본값 (2026-10-29, 0.7.0)

- **로그**: 라이브러리 안에서는 `print` 대신 `logging`(`equion` · `equion.engine` · `equion.workfile`). 기본으로 메시지만
  찍는 처리기를 붙이되 찍는 순간의 `sys.stdout`으로 보내 노트북·`redirect_stdout`·`run.log` 수집과 맞물린다.
  애플리케이션이 직접 다루려면 `eqn.log.use_own_handler(False)`. `eqn.verbose(0|1|2)`는 그 위의 편의 장치.
- **버전 하나**: 공개 버전은 패키지 버전(`equion.__version__`·`equion --version`·보고서) 하나다. `ENGINE_VERSION`은
  번들·워크파일 형식 표시용 내부 값으로만 남긴다. 보고서 `manifest.json`의 `versions`에서 `engine`을 빼고
  `format_version`을 2로 올렸다(D15 약속대로).
- **공개 API 등급**: 공개(`wfopen`·`wfcreate`·`Workfile`·`show`·`params`·`secret`·`verbose`·`spool`·`stats`·`log`·CLI) /
  고급(`Data`·`Equation`·`Model`·`Scenario`·`WorkTable`·`Workspace` — 엔진 API) / 내부(그 밖). `__all__`도 이 순서.
  `_legacy/`는 1.0에서 없앤다(가져오면 DeprecationWarning).
- **보안 기본값**:
  - 방정식 텍스트 한도: 길이 20,000자 · 중첩 250 · 시차 1,000 · 시차 범위 100 · 항 500. 넘으면 바로 `DSLError`
    (극단 입력이 멈추거나 재귀 한계로 죽던 것을 막음). 퍼징 3,000개 × 2경로로 DSLError/ValueError 외 예외 없음을 검사.
  - 비밀 값: `eqn.secret("이름")`·민감한 이름(`key·token·secret·passw·pwd·credential·auth`)의 매개변수는 보고서
    `manifest.json`·`report.html`·`run.log`에서 `***`로 가린다. 공유용 `--redact`는 작업 폴더·실행 파일 경로·git
    브랜치를 빼고 절대 경로를 상대 경로로.
  - 레거시 pickle은 기본으로 열지 않는다(`allow_pickle=True` 또는 `EQUION_ALLOW_PICKLE=1`) — pickle은 여는 순간 코드가
    실행될 수 있다. `equion convert`로 새 형식으로 바꾼다. pickle 저장은 DeprecationWarning.
  - 워크파일·번들의 표는 `.npz`(`allow_pickle=False`로 읽음) — 열어도 코드가 실행되지 않고 pyarrow가 필요 없다.
    워크파일 `FORMAT_VERSION` 2. 0.6.0까지의 parquet은 pyarrow가 있으면 계속 읽는다.
- **뒤로 미룬 것**: 신뢰 폴더(처음 여는 폴더의 스크립트 실행 확인)는 데스크톱 앱(P3)에서.

## D19. 범위 의존성 + 잠금 파일, 선택 기능, CI (2026-10-29, 0.7.0)

- **배경**: 0.6.0까지는 `pyproject.toml`에 버전을 `==`로 고정했다. 이 저장소에선 재현성이 좋지만, 다른 패키지와 함께
  설치하면(pip·pipx·데스크톱 앱) 충돌하고 보안 갱신을 받지 못한다.
- **결정**:
  - `pyproject.toml`은 **범위**(`numpy>=2.1,<3` · `pandas>=2.2.2,<4` · `scipy>=1.14,<2` · `openpyxl>=3.1,<4`,
    Python `>=3.12`), 이 저장소의 실행 환경은 **`uv.lock`이 정확한 버전·해시로 고정**한다(커밋된 HS 기준선은 lock 기준).
    하한·상한은 말로만 두지 않고 CI가 실제로 검사한다 — 하한(Python 3.12 · numpy 2.1.0 · pandas 2.2.2 · scipy 1.14.0 ·
    openpyxl 3.1.0)과 최신판(Python 3.14 · numpy 2.5 · pandas 3.1 · scipy 1.18)에서 전 테스트 통과, 하한 환경의 분기 HS는
    기준선과 상대 1e-10 이내·상태 열 동일.
  - **선택 기능**: pyarrow(`equion[parquet]` — 옛 parquet 읽기)와 plotly(`equion[plot]` — `figure()` 객체·
    `compare_and_plot`)를 필수에서 뺐다. 그래프는 그림 정의(JSON)를 직접 만들고 plotly.js(MIT, gzip 1.5MB)를 패키지에
    내장해 그린다 — 보고서는 인터넷 없이 열리고, 코어 설치가 pyarrow·plotly 몫만큼 가벼워진다(데스크톱 앱에도 유리).
    `equion[all]`은 둘 다. 개발 그룹(dev)에는 둘 다 넣어 선택 경로도 검사한다.
  - **CI**(`.github/workflows/ci.yml`): locked(Linux·Windows·macOS × Python 3.12~3.14) · minimal(선택 의존성 없이) ·
    lowest · latest(주간 일정은 사전 공개판까지) · baseline(드라이버 3종 → `tests/compare_hs.py`로 허용오차 비교) ·
    audit(pip-audit, 잠근 해시 그대로). 각 테스트 파일은 그대로 `python tests/test_x.py`로 돌고, pytest는 파일마다
    `test_suite()` 하나로 묶어 부른다.
  - **Windows 인코딩**: 패키지 코드의 파일·하위 프로세스 입출력은 모두 `encoding="utf-8"`(`-X warn_default_encoding`으로
    검사). 명령줄은 표준출력이 UTF-8이 아니면(영문 Windows 파이프 cp1252, 한글 cp949에 없는 '—') 그 문자만 `\uXXXX`로
    써서 멈추지 않는다 — 0.6.0까지는 `UnicodeEncodeError`로 끝났다. 보고서 경로는 어느 OS에서나 `/`.
  - **갱신**: dependabot(uv·GitHub Actions, 주간). numpy·pandas·scipy는 한 묶음 PR — 기준선을 한 번에 확인.
  - **배포**: `release.yml`은 태그(`v*`)에서 휠을 만들고 세 OS에서 설치 시험까지 한다. PyPI 올리기는 저장소 주인이
    신뢰 배포(OIDC)를 등록하고 `PYPI_PUBLISH` 변수를 켤 때만 — 토큰을 쓰지 않는다.

## D20. 추정법 확장 — WLS·GMM·LIML·PDL·누락/불필요 변수 (2026-10-29, 0.7.0)

- **추가**: `wf.equation(…).wls(spec, weights=식, wtype=…)` · `.gmm(spec, inst, weight='white'|'hac', lags, iterate)` ·
  `.liml(spec, inst)`, 선형식의 항 `pdl(X, 시차, 차수[, 제약])`(+ `.lag_distribution()`), 검정 `.omitted(…)`·`.redundant(…)`.
  모두 `equion/stats/regression.py`·`diagnostics.py`의 자체 구현이고, 풀이에서는 지금까지의 식과 똑같이 IR로 풀린다
  (WLS·GMM·LIML은 계수만 다른 선형식, PDL 항은 시차들의 선형결합 IR).
- **정의(기준 구현과 같게)**:
  - WLS: 가중치 ∝ 1/분산(statsmodels WLS와 같음). 잔차는 가중 전 값(y − Xb — 풀이·add-factor와 같은 뜻), R²·SSR·DW·F·
    강건 공분산은 가중 잔차로, 가중 전 R²·SSR·DW는 따로(`unweighted_*`). `wtype`은 가중 계열이 1/분산·분산·
    1/표준편차·표준편차 중 무엇인지.
  - GMM: 1단계 TSLS 잔차로 W = S⁻¹(중심화하지 않음), 2단계(또는 반복). 공분산은 최종 잔차의 S로 만든 샌드위치(작은 표본
    보정 없음), J = 그 계수를 낸 가중행렬로 잰 목적함수 n·ḡᵀWḡ — linearmodels IVGMM과 같은 정의.
  - LIML: κ = (YᵀM_Z Y)⁻¹(YᵀM_{Z₁}Y)의 최소 고윳값, 일반 공분산 σ²[Xᵀ(I − κM_Z)X]⁻¹(σ² = ê'ê/(n−k)), 강건 공분산의
    meat는 P_Z x — linearmodels IVLIML과 같은 선택. 외생 회귀변수는 도구 목록에 같은 값의 열이 있는 것.
  - PDL: β = Bγ, 다항식은 가운데 시차 c = ⌊k/2⌋ 기준 (i − c)^j. 제약(가까운 끝 β₋₁ = 0, 먼 끝 β_{k+1} = 0)은 γ를 영공간으로
    줄여 건다. 계수 이름 PDL01…(식 전체에서 이어 번호), Wald의 c(n) 번호에도 그대로 들어간다.
  - 누락/불필요 변수: F와 LR(= n·log(SSR_작은식/SSR_큰식)). 누락 검정은 새 항까지 관측되는 공통 표본에서 두 식을 모두 다시
    추정(statsmodels compare_f_test/compare_lr_test와 같은 값). OLS·WLS 식에만.
- **수치 정확도 결정**: GMM은 정규방정식 (GᵀWG)b = GᵀWḡ 대신 S^-½로 희게 만든 최소제곱을 유사역행렬로 풀고, 공분산은
  M⁺(W^½ŜW^½)M⁺ᵀ로 계산한다. 이 자료에서 linearmodels(정규방정식)는 계수가 50자리 계산과 상대 2.4e-7, 세 행렬 곱 공분산은
  4e-8 어긋났고, 이렇게 바꾼 Equion은 둘 다 2e-10 이내다. 그래서 GMM의 기준값은 mpmath 50자리 직접 계산이고 linearmodels는
  교차 확인(1e-5)으로만 쓴다(D17의 원칙: 외부 구현이 부정확한 곳은 독립 계산과 비교).
- **기준값**: `tests/fixtures/estimation_reference.json`(`make_estimation_reference.py` — statsmodels·linearmodels·mpmath가
  있는 별도 환경에서만). PDL은 기준값 없이 독립 계산과 비교(차수 = 시차 수면 개별 시차 OLS, 제약이 있으면 제약 최소제곱의
  투영 공식).

## D21. AR(p) 오차·오차수정모형·예측 평가 (2026-10-29, 0.7.0)

- **AR(p) 오차**: 선형 추정식에 `ar(1) ar(2)`·`ar(1 to 4)`. yₜ = xₜb + uₜ, uₜ = Σρₚuₜ₋ₚ + εₜ를 조건부 최소제곱(NLS, IR 기호
  미분 자코비안)으로 푼다. 풀이 IR은 xₜb + Σρₚ(yₜ₋ₚ − xₜ₋ₚb) — 동적 풀이에서 u가 ρ로 이어져(uₜ₊ₕ = ρʰ⁺¹uₜ₋₁) 따로
  잔차를 들고 다닐 필요가 없고, "실측을 넣은 풀이 잔차 = 추정 잔차 εₜ"가 그대로 성립한다. ls·fixed에서만(도구변수·가중 없음).
  계수 이름 AR(1)…, c(n) 번호는 쓴 항 다음. 저장은 정규형 `ar(p)` 글자로.
- **전역 최소를 고른다**: 조건부 제곱합은 ρ에 대해 국소 최소가 여럿일 수 있다(이 자료의 소비식 `log(RCPSA) c log(RGDPSA)
  ar(1)`: OLS에서 출발하면 ρ = 0.81, 전역 최소는 ρ = 0.986). ρ를 고정하면 b가 준차분 OLS로 정해지므로 ρ만의 집중 목적함수를
  격자(AR(1))·여러 시작점 Nelder-Mead(AR(p≥2))로 넓게 찾고 LM으로 다듬어 더 작은 제곱합을 고른다 — 추정량의 정의를
  따른다. OLS 출발점의 국소 최소와 다르면 결과에 알린다(`stats['ar_note']`·결과표). OLS 출발점에서만 수렴시키는 프로그램과
  값이 다를 수 있는 곳이라 기록한다.
- **오차수정모형** `wf.ecm(name, y, x, method='two-step'|'nls', lags)`: 두 단계는 장기 OLS(`이름_lr`)의 계수를 숫자로 넣은
  EC(-1) 식을 단기식 항으로 쓴다 — 모델에서 y·x를 따라 움직인다. NLS는 `d(y) = c(1)*(y(-1) − c(2) − c(3)*x(-1)) + …`
  (장기 계수의 표준오차가 바로 나옴, 시작값은 두 단계 결과). 장기 잔차의 Engle-Granger 검정·조정 속도·반감기를 함께 보인다.
  검증: NLS 형은 제약 없는 ECM(OLS)의 정확한 재모수화라 α = π, a = −c₀/π, b = −θ/π가 1e-6 안에서 같다.
- **예측 평가**: `eqn.stats.forecast_evaluate/forecast_table`, `wf.forecast_eval(실측, 예측…)` — RMSE·MAE·MAPE·Theil U1·
  MSE 분해(편의·분산·공분산)·Theil U2. `diebold_mariano`·`wf.dm_test` — 직사각 커널 장기 분산(0 이하면 Bartlett),
  Harvey-Leybourne-Newbold 보정 + t(n−1) 기본.

## D22. 시스템 추정 — OLS·SUR·2SLS·3SLS·FIML·식 사이 제약 (2026-10-29, 0.7.0)

- **객체**: `wf.system(name).append(식…, "@inst …")` → `.ols()`·`.sur(iterate)`·`.tsls()`·`.three_sls()`·`.fiml()`,
  `restrict=["c(2) = c(5)"]`, `.wald(…)`, 결과 `.coefs`·`.stderrs`·`.resid`·`.sigma`·`.equation_stats()`. `wf.model(…).merge(시스템)`은
  추정한 계수를 고정한 식(이름 `시스템_목표변수`)을 만들어 넣는다 — 모델 풀이·시나리오는 지금까지와 같다.
- **식 쓰기**: c(n) 꼴(`Y = c(1) + c(2)*X`) 또는 추정식 꼴(`Y c X` — 계수 번호는 쓰인 번호 다음부터 자동). 여러 식에 같은
  c(n)을 쓰면 그것이 식 사이 제약(EViews 시스템과 같은 관례)이고, 일반 선형 제약은 `restrict`(b = b₀ + Nθ). 계수에 선형인 식만
  (IR로 ∂식/∂c(n)에 계수가 남지 않는지 확인). 표본은 모든 식(과 도구)이 함께 관측되는 기간. 항등식·ar 항은 시스템에 넣지 않는다.
- **정의**: Σ̂ = ÊᵀÊ/T(자유도 보정 없음), SUR·3SLS의 공분산 (X̃ᵀ(Σ̂⁻¹⊗I)X̃)⁻¹, OLS·2SLS는 식 사이 상관을 반영한 샌드위치 —
  linearmodels SUR·IV3SLS 기본값과 같다(계수·표준오차 1e-9 이내, 공유 계수 = 같은 제약의 restrict). GLS는 Σ̂^-½로 희게 만든
  자료에 유사역행렬(D20과 같은 이유). z값·p값은 정규분포.
- **FIML**: 집중 로그우도 −(Tm/2)(1 + log 2π) − (T/2)log|Σ̂(b)| + Σₜ log|det ∂εₜ/∂yₜ|. 내생변수는 각 식의 목표변수,
  ∂ε/∂y와 그 계수 미분은 IR 기호 미분으로 정확히 만든다(로그 좌변의 1/Y 같은 변환 야코비안도 들어간다). 해석적 기울기로 BFGS,
  뉴턴 단계로 마무리(기울기 1e-10까지), 공분산은 관측 정보(헤시안). 외부 기준 구현이 없어 알려진 동치로 검증: 우변에 현시점
  내생변수가 없으면 FIML = 반복 SUR, 정확 식별이면 FIML = 3SLS = 2SLS, 과대 식별이면 로그우도가 3SLS보다 크고 기울기 ≈ 0,
  표준오차 = 로그우도의 수치 헤시안.
- **저장**: 워크파일에는 식·도구·추정법·제약을 적고, 열 때 다시 추정한다(결정적이라 같은 값).

## D23. VAR·VECM (2026-10-29, 0.7.0)

- **객체**: `wf.var(name, series, lags, trend='n'|'c'|'ct')` → `.coefs`·`.stderrs`·`.sigma`·`.lag_order(maxlags)`·
  `.granger(caused, causing)`·`.granger_table()`·`.irf(h, orth)`·`.irf_graph`·`.fevd(h)`·`.forecast(steps)`·`.stability()`.
  `wf.vecm(name, series, lags_diff, rank, deterministic='n'|'co'|'ci'|'lo'|'li'|조합)` → `.alpha`·`.beta`(위 r×r = I)·`.gamma`·
  `.forecast`. 시리즈는 이름이나 식(`dlog(RGDPSA)`), 표본은 smpl 안에서 모두 관측되는 구간. 둘 다 `model.merge(…)`로
  계수를 고정한 식이 된다(VAR 추세는 `@trend − s0 + 1`, VECM의 EC 항은 β를 숫자로 넣은 식) — VAR·VECM 잔차와 같은 잔차.
- **정의**: statsmodels VAR·VECM과 같다(계수·표준오차·Σ_u(자유도 보정)·AIC·BIC·HQ·FPE·같은 표본의 시차 선택·Granger F와
  자유도·직교 충격반응(촐레스키)·분산분해·예측 1e-9 이내, VECM 결정항 7종 α·β·Γ·결정항·Σ·예측 1e-7 이내 — VECM 'co'의 고윳값은
  Johansen 검정(det=0)과 1e-10). 계산은 자체(유사역행렬 OLS, S₁₁^-½ 대칭 고유문제).

## D24. 모델 분석 — 동태 안정성·시나리오 기여도 분해 (2026-10-29, 0.7.0)

- **안정성** `model.stability(period, scenario, measure)`: 그 시점 값(실측 또는 시나리오 풀이값)에서 모든 식의 잔차를 현시점·
  과거 내생변수로 미분(IR 기호 미분 — 수치 미분 아님)해 동반행렬을 만들고 고윳값을 본다. 기본 `measure='relative'`는 양수
  변수를 상대 편차로 재서 로그식의 근이 성장률만큼 부풀지 않게 한다(log Y = a + b·log Y(-1)이면 근 = b, 수준 편차면 b·Yₜ/Yₜ₋₁).
  차분식 목표처럼 수준이 적분된 변수는 근 1을 가진다(VAR로 만든 모델 = VAR 근 + 변수마다 1로 확인). `stability_path`는 기간별
  최대 모듈러스. 선행 변수(MCE) 모델은 대상이 아니다.
- **진단 결과(기록)**: 분기 모델은 2015Q1 최대 |λ| ≈ 1.01~1.02(BOPSBSA·RCINSA·RDJSA가 함께 움직임), 연간 모델은 2008년
  1.86 등 매년 1을 넘고 가장 큰 근이 URATE(96%)·EACTP에 실린다 — IMPROVEMENTS §9.7 ⑥(연간 모델 동태 불안정)의 출발점.
- **기여도 분해** `model.decompose(vars, scenario, base, method)`: 시나리오의 항목(외생 경로·고정·조정항·충격·목표추적·잔차 사용
  — 기준선에 이미 같은 값으로 있는 것은 뺌)별로 기준선 대비 차이를 나눈다. 기본 Shapley(모든 부분집합을 풀어 평균 기여 —
  비선형 모델에서도 합이 정확히 전체, 항목 8개까지), `single`은 하나씩 + 상호작용. 결과 표·쌓은 막대 그래프(kind='stacked').

## D25. 큰 모델 — 희소 자코비안·stacked-time MCE (2026-10-29, 0.7.0)

- **희소 자코비안**: 블록 컴파일러가 같은 기호 미분 코드로 0이 아닌 칸의 값만 돌려주는 함수(`jac_data`·`jac_pattern`)도 만든다.
  Newton은 `jacobian='auto'`(기본)에서 블록이 100변수 이상이면 scipy.sparse LU(열 스케일링 그대로), 그보다 작으면 지금까지의
  밀집 풀이 — 한국 모델(가장 큰 블록 46)의 HS는 바이트 그대로. `'sparse'`·`'dense'`로 강제할 수 있다. 폴백(hybr·lm)은 밀집.
  검증: 분기 모델 HS를 희소로 풀면 밀집과 상대 2e-10·상태 같음, 150변수 동시 블록은 직접 선형 해와 1e-10.
- **stacked-time MCE** `mce=True, mce_method='stacked'`: 모든 기간(start…end)의 미지수를 한 번에 감쇠 Newton으로 푼다.
  행 = (기간, 식), 열 = (기간, 미지수), 자코비안은 식마다 잎(변수·시차/선행)별 기호 미분(`compile_equation_full`)으로 만든
  희소 행렬. 기간별 식·미지수 집합(결측 입력 제외·exclude·control)과 시작값은 Fair-Taylor 1회로 정한다. 지평 밖 선행값은
  terminal 조건(actual·hold). Fair-Taylor는 그대로 기본값.
  검증: 선형(로그) 선행 모형에서 삼중대각 선형계의 직접 해와 1e-10(Fair-Taylor는 수렴 기준 때문에 2e-8), 선행 계수가 1보다
  커서 Fair-Taylor가 발산하는 모형도 stacked는 수렴하고 식을 1e-9로 만족.

## D26. 자료 — 메타데이터·페이지·주기 변환·시간 분할·계절조정 (2026-10-29, 0.7.0)

- **메타데이터** `wf.meta(이름, desc=…, unit=…, source=…, notes=…, agg=…)`, `wf.metadata()` 표. `agg`(mean·sum·first·last·
  max·min)는 낮은 주기로 바꿀 때의 기본 집계다. 워크파일에 함께 저장된다.
- **페이지** `wf.page(이름, 주기)`: 다른 주기의 워크파일을 같은 작업 단위에 둔다(이 워크파일 전체를 덮는 기간). 저장하면
  `<워크파일>.eqw/pages/<이름>.eqw`로 함께 쓰이고 열 때 같이 열린다(페이지 안 페이지도).
- **주기 변환** `wf.convert(시리즈, to=페이지|주기, method, indicator, conversion)`:
  높은 → 낮은 주기는 mean·sum·first·last·max·min(하위 기간이 하나라도 비면 결측 — 부분연도 방지, 연간 빌더의 min_count와 같은
  원칙), 낮은 → 높은 주기는 constant·split·linear·denton·chow-lin. 페이지로 보내면 그 페이지에 쓰고 메모(출처·방법)를 남긴다.
- **시간 분할**: Denton은 비례 1차 차분(Cholette 수정) — KKT 연립으로 풀고 제약(sum·average·first·last)을 정확히 만족, 지표가
  길면 외삽(statsmodels dentonm과 1e-8). Chow-Lin은 AR(1) 오차 GLS, ρ는 집중 로그우도 최대(격자 → Brent), 고정 ρ의 GLS 식·
  합 제약을 독립 계산과 비교.
- **계절조정** `wf.seas(시리즈, method='stl'|'classical', model='additive'|'multiplicative')` → `이름_SA`·`이름_SF`.
  STL은 원 알고리즘(Cleveland 외 1990)의 loess·저역통과·강건 가중치를 그대로 옮겼다(statsmodels STL과 계절·추세·가중치
  1e-9, 기본·강건·창 지정 4가지). 승법 STL은 로그에서 분해해 되돌린다. 고전 분해는 statsmodels seasonal_decompose와 같은
  정의(중심 이동평균 + 위치별 평균). X-13 같은 외부 프로그램은 쓰지 않는다(외부 실행 파일 의존을 만들지 않음).

## D27. 문서 체계 — Markdown 원본·실행되는 문서·예제 자료 (2026-10-30)

- **결정**: 사용자 문서는 저장소의 Markdown이 원본이다. 정적 사이트 생성기는 쓰지 않는다(GitHub에서 그대로 읽힘). 구성은 네 부분과 사례:
  시작하기(`docs/start`) · 튜토리얼(`docs/tutorial`, 차례로 배우기) · 레시피(`docs/howto`, 할 일별) · 해설(`docs/explain`, 원리) ·
  참조(`docs/reference`, 찾아보기) · 사례 연구(`docs/cases`) · EViews 사용자 안내(`docs/eviews.md`) · 영문(`docs/en`). 첫 페이지 `docs/README.md`.
- **실행되는 문서**: 문서의 `python` 블록은 파일마다 새 임시 폴더에서 위에서부터 실행한다. `<!-- out -->` 다음 `text` 블록은
  실행 출력으로 채우고(`python docs/build_docs.py`), `--check`는 출력이 숫자 허용오차 안에서 같은지, 링크·앵커, 공개 API의 설명·예제,
  docstring 예제(doctest)를 확인한다(`tests/test_docs.py` → CI). 출력 비교는 `.python-version`과 `uv.lock`의 numpy·pandas 판에서만
  한다(다른 판에서는 실행만). 시작하기·튜토리얼은 `examples/`의 스크립트·노트북으로 내보낸다 — 예제를 고치려면 문서를 고친다.
- **예제 자료** `eqn.datasets`: 참 모형을 아는 가상 자료(`toy_q`·`toy_a`·`toy_m`·`klein_like`)를 패키지에 넣는다(고정 시드,
  `equion/datasets/_make.py`). 문서·docstring 예제는 이것만 쓰므로 저장소 밖에서도 돈다. 한국 모델 자료는 사례 연구에서만 쓴다.
  실제 Klein 모형 I 자료는 이용 조건이 분명하지 않아 넣지 않고, 사용자가 구한 파일을 여는 `eqn.datasets.klein(path)`만 둔다.
- **언어**: 한국어가 원본. 영어는 시작 문서(`docs/en`)와 자동 생성 API 참조(서명)만. 메시지·표 머리말은 한국어로 두고, 영문 문서에
  용어 대응표를 둔다.
- **API 참조**: `docs/reference/api.md`는 docstring에서 만든다(`python docs/make_api.py`, CI가 `--check`). 공개 함수·메서드의
  docstring은 요약 · 매개변수 · 돌려주는 것 · 오류 · 예(`>>>`) · 관련 순서로 쓰고, 공개 함수에는 예제가 있어야 한다.
- **완료 기준**: 새 기능은 코드 + 시험 + docstring(예제) + 튜토리얼이나 해설의 절 + 필요한 레시피가 있어야 끝난다.
- **이유**: 분석 패키지는 자세한 문서와 그에 맞는 예제가 있어야 쓰인다. 문서 출력이 코드와 어긋나지 않게 하는 가장 확실한 방법은
  문서를 시험처럼 돌리는 것이다.

## D28. Equion Desk는 같은 저장소의 별도 패키지로 (2026-11-08, P3에서)

- **결정**: 데스크톱 앱 Equion Desk는 이 저장소의 `desk/` 폴더에 별도 Python 패키지 `equion-desk`(자체 `pyproject.toml`)로 둔다.
  루트의 `equion` 패키지와 uv workspace로 묶어(`[tool.uv.workspace] members = ["desk"]`) 잠금 파일 `uv.lock`은 하나를 함께 쓰고,
  설치는 따로 된다 — `pip install equion`에는 앱 의존성이 딸려 오지 않는다.

  ```text
  desk/
    pyproject.toml     이름 equion-desk · 의존성: equion(같은 저장소), pywebview[pyside6] …
    equion_desk/       창·로컬 서버·콘솔
    web/               lectern 스타일 화면(순수 JS, vendor 내장 — D7·D10)
    build/             PyInstaller·Inno Setup·AppImage 스크립트
    tests/
  ```

- **경계**:
  - 의존 방향은 `equion-desk → equion` 한쪽만. 패키지는 앱을 import하지 않는다(시험으로 확인).
  - 앱 의존성(pywebview[pyside6]·로컬 서버·PyInstaller 등)은 `desk/pyproject.toml`에만 둔다. 패키지의 필수 의존성(D17·D19)은 그대로.
  - CI: 패키지 검사(3 OS × Python 3판)는 지금 그대로. 앱 빌드(설치 파일·AppImage)는 `desk/`가 바뀔 때와 앱 태그에서만 돌린다.
  - 출시 태그를 나눈다: 패키지 `vX.Y.Z`, 앱 `desk-vX.Y.Z`. 앱은 같은 커밋의 패키지를 품고 배포된다(D7).
  - 라이선스: 패키지는 MIT 그대로. 앱 배포본에 들어가는 Qt(PySide6, LGPL — D8)·lectern 코드(D10)·화면용 JS 라이브러리의 고지는
    `desk/`에 따로 둔다.
  - 설치 파일(.exe·.AppImage)은 커밋하지 않고 GitHub Releases에 올린다. 화면용 JS 내장본만 커밋한다.
  - 앱 설치본에는 예제 자료(`eqn.datasets`)만 넣는다. 한국 모델 자료(`DATA/`·`EQUATIONS/`·`HS/`)는 넣지 않는다.
- **이유**: 세 단계는 코어 하나 위의 앞단이다(D1). 앱의 Python 콘솔은 라이브러리 API를(D9), 프로그램 실행은 명령줄과 같은
  `cli.runner`·`cli.report`를 쓰므로 패키지와 앱이 함께 바뀌는 일이 많다 — 한 저장소면 그런 변경이 커밋 하나·CI 한 번으로 끝나고
  두 저장소 사이의 판 맞추기가 없다. 운영자가 한 사람이라 이슈·PR·문서·결정이 한 곳에 있는 편이 낫다.
- **저장소 분리 계획과의 관계**: `REPO_SPLIT.md`(보류)는 패키지와 **한국 모델**을 나누는 계획이다. 나누게 되면 Desk는 패키지 쪽
  (`equion` 저장소)으로 함께 간다 — 이 결정과 부딪히지 않는다.
- **지금 할 일은 없다**: P3는 향후 프로젝트(기획만, ROADMAP). 시작할 때 이 구성으로 만든다.
- **변경 (2026-11-08, D29)**: 앱이 Windows 전용이 되어 — 의존성은 `pywebview[pyside6]` 대신 pywebview(Windows의 WebView2,
  Windows에서만 설치되게 표시), `build/`는 PyInstaller·Inno Setup만, 설치 파일은 `.exe`만, Qt(LGPL) 고지는 없다.
  앱 빌드 CI는 `windows-latest`에서만 돌린다. 나머지(같은 저장소의 `desk/` 별도 패키지, 의존 방향, 태그, 자료)는 그대로.

## D29. Equion Desk는 Windows 전용, 패키지는 세 OS 그대로 (2026-11-08, P3에서)

- **결정**: 데스크톱 앱 Equion Desk는 lectern처럼 **Windows 전용**으로 만든다. 패키지 `equion`(라이브러리·명령줄)은 지금처럼
  Windows·macOS·Linux를 모두 지원하고, CI도 3 OS × Python 3판 그대로 둔다.
- **앱 구성**:
  - 창: pywebview의 Windows 기본 엔진인 Edge WebView2 하나. Linux용 PySide6(Qt)는 쓰지 않는다 — D8 폐지.
  - 설치 파일: `EquionDesk-<버전>-setup.exe`(PyInstaller onedir + Inno Setup) 하나. AppImage는 만들지 않는다(D16 변경).
  - WebView2 런타임: Windows 11에는 기본으로 있고 Windows 10도 대부분 있다. 없는 PC를 위해 설치 파일에 Microsoft의 설치 도우미
    (Evergreen bootstrapper)를 넣는다.
  - `desk/`(D28)의 앱 의존성(pywebview 등)은 Windows에서만 설치되게 표시한다(`sys_platform == 'win32'`) — Linux·macOS에서 잠금
    파일과 패키지 검사가 영향을 받지 않는다.
  - CI: 앱 빌드·앱 시험은 `windows-latest`에서만(`desk/`가 바뀔 때와 앱 태그 `desk-vX.Y.Z`). 패키지 CI는 그대로.
  - 라이선스 고지: Qt(LGPL) 고지가 없어진다. lectern 코드(D10)·화면용 JS 라이브러리·WebView2 설치 도우미의 고지는 `desk/`에 둔다.
- **개발과 확인**: 앱의 로컬 서버·화면 로직·시험은 어느 OS에서나 만들 수 있게 짠다(서버 코드는 플랫폼에 묶지 않는다). 실제 창
  확인과 설치 파일 시험은 Windows(사용자 PC·Windows CI)에서 한다.
- **나중에 정할 것**: 코드 서명 — 서명하지 않은 exe는 처음 실행할 때 Windows SmartScreen 경고가 뜬다. 배포를 시작할 때 정한다.
- **이유**: 저장소 주인의 결정(lectern과 같은 방식). 화면 엔진이 하나라 렌더링 차이가 없고, Linux 배포본(수백 MB)·Qt LGPL 의무·
  두 OS 빌드가 사라진다. 패키지는 노트북·서버 자동화·CI에서 여러 OS로 쓰이고, 3 OS 검사는 플랫폼마다 다른 결과를 찾아
  수치 품질을 지키므로(예: 0.7.x의 계열상관 LM 고침) 그대로 둔다.
- **바뀌는 결정**: D1(데스크톱 앱 Windows 전용) · D8(폐지) · D16(AppImage 없음) · D28(앱 의존성·빌드·고지·CI) — 각 결정에 변경 표시.
- **변경 (2026-11-09, D39)**: 설치 파일 안의 구성을 PyInstaller onedir에서 **설치 폴더 안 Python 런타임 하나**(python-build-standalone +
  잠긴 패키지)로 바꾼다. 설치 파일 이름·WebView2 설치 도우미·Windows 전용은 그대로.

## D30. 저장소 분리 실행 — 공개 패키지 `equion` / 비공개 한국 모델 `macro_model` (2026-11-08)

- **결정**: 보류했던 저장소 분리(`REPO_SPLIT.md`)를 지금 한다. 저장소 주인은 패키지를 공개하되 자료는 넣지 않기로 했다.
  - 새 저장소 `samiblog/equion`(공개 예정): 패키지 `equion/`·시험·사용자 문서·예제(`examples/`)·CI·배포 워크플로.
    Desk(D28·D29)도 나중에 여기의 `desk/`에 둔다.
  - 지금 저장소 `samiblog/macro_model`(비공개): 한국 모델 — 자료(`DATA/`)·방정식(`EQUATIONS/`)·HS 기준선(`HS/`)·드라이버
    (`scripts/`)·드라이버 지원 코드(`kmodel/`)·노트북·한국 모델 회귀 시험(`tests/test_korea_model.py`·`compare_hs.py`)·사례 연구
    (`docs/cases/korea.md`)·개선 기록(`IMPROVEMENTS.md`). 패키지는 `equion`을 판 번호(git 태그, 나중에 PyPI)로 가져다 쓴다.
- **깨끗한 기록으로 시작**: 새 저장소는 자료가 한 번도 들어간 적 없는 첫 커밋에서 시작한다. 지금 저장소의 기록에는 자료의 지난
  판이 있고, 닫히지 않은 PR이 옛 커밋을 붙들고 있어 기록을 고쳐 쓰는 것으로는 막을 수 없다. 전체 기록은 비공개 저장소에 남는다.
- **패키지 시험은 예제 자료만**: 시험·기준값(`tests/fixtures`)을 `eqn.datasets`로 다시 만들었다(D27의 예제 자료). 한국 모델로 하던
  검사(추정 45/45·HS 92/92·기준선·명령줄 예시)는 `tests/test_korea_model.py`로 옮겼다.
- **공개 전 확인**: 이름 상표(D16 — KIPRIS·USPTO), 새 기록의 작성자는 noreply 주소, 문서의 개인 경로.
- **이유**: 공개하면 CI가 무료이고 누구나 설치·기여할 수 있다. 패키지와 한국 모델은 바뀌는 속도와 쓰는 사람이 다르다(REPO_SPLIT §1).

## D31. Equion Desk 개발 계획 — 패키지 0.8을 먼저, 그다음 Desk 1차판 (2026-11-09)

- **결정**: P3를 기획에서 개발로 옮긴다. 기준 문서는 `docs/DESK_DEVPLAN.md`(개발 계획)이고, 근거인 기획 자료 아홉 개
  (`docs/DESK.md`·`DESK_REVIEW.md`·`DESK_SCENARIO.md`·`DESK_ANALYSIS.md`·`DESK_SCENES.md`·`DESK_SOLO.md`·`DESK_DATA.md`·
  `DESK_REPRO.md`·`DESK_SCRIPT.md`)는 그대로 둔다 — 자료와 개발 계획이 다르면 개발 계획을 따른다.
- **순서**: ① 패키지 equion 0.8(단계 E — E1 프로젝트·조립, E2 자료 정의·회차, E3 작업 명령·기록, E4 분석·노트·보고서,
  E5 스크립트·재연, E6 안내·문서) ② Desk 1차판 equion-desk 0.1(단계 D — D0 시험판, D1 뼈대, D2 식·자료, D3 조립·HS·흐름,
  D4 전망·보고서, D5 Claude·설치본). D0 시험판만 E와 나란히 일찍 한다(설치·속도 위험을 먼저 안다). 그 뒤 2차판,
  ECOS·KOSIS 받기는 equion 0.9(0.8 후보에서 옮김), scikit-learn 확장은 미래.
- **운영 원칙**(기획안 §2): 두 길(손으로도 Claude로도 — 같은 명령), 보이는 계산(명령이 있을 때만 계산, 엔진이 알아서 한 것은 결과에 적음),
  결과는 고치지 않음(다시 계산하면 새 기록), 레고(이름 있는 부품을 조립), 설치만 하면 작동.
- **기획 자료의 상충 정리**: Lectern 수정·기초 분석 추가·노트 ▶ 화면·묶어 보내기·이정표는 2차판 · 흐름은 Equion 스크립트(D36) ·
  결과 카드는 `summary.md` · 프로젝트 안의 실행 기록은 `work/run/<id>/`(`run:`) · "스크립트 없이"는 "Python 스크립트 없이" ·
  미리보기는 기록을 남기지 않고 '미리보기'로 표시 · '회차 바꾼 뒤 할 일' 화면과 스크립트는 둘 다 둔다.
- **1차판의 사용자**: 저장소 주인과 가까운 동료 — 서명 없는 설치본, 한국어 화면. 코드 서명·오프라인 큰 설치본은 배포를 넓힐 때,
  영문 화면은 2차판.
- **바뀌는 결정**: D9(앱 안 Python 해석기 → 터미널) · D29(설치본 구성 — D39) · ROADMAP P3의 3-0~3-7 계획.
- **이유**: 계산·형식을 패키지에 먼저 굳히면 Desk 없이도 Lectern 터미널과 Claude로 바로 쓰고(0.8), 화면은 같은 명령을 부르는
  층이 되어 두 길이 저절로 선다. 저장소 주인이 기획 자료 전체와 개발 계획의 추천안을 받아들였다(2026-11-09).

## D32. 프로젝트 — 부품·조립·채택표·이름 (2026-11-09, 0.8에서)

- **결정**: 프로젝트는 폴더 하나다. 조립은 `equion.toml`(`[data]` 정의 파일과 지금 자료 회차 `vintage` · `[block]` 블록 = 방정식 파일 하나 ·
  `[model.이름]` 블록·다른 모형 포함·`exclude` · `[group]` 묶음 · `[criteria]` 판단 기준 · `[hs]`·`[forecast]` 기본값). 정의 파일은
  TOML + CSV + 방정식 파일(지금 문법 그대로).
- **채택표**: 모형은 식마다 **채택한 추정 기록의 계수**로 푼다 — `EQUATIONS/adopted.toml`(`"demand:CN" = "est:cons_c5"`). 블록 파일의
  줄은 식의 글자이고, 글자와 채택 기록이 다르면 알린다.
- **조립 규칙**: 내생·외생은 조립이 정한다, 한 모형에 같은 목표변수는 하나, 모르는 변수는 오류, 부품은 이름으로 가리킨다,
  바꿔 끼우기는 파일을 바꾸지 않는다, 모든 HS·전망 기록에 조립 명세(쓴 부품의 판·해시·equion 판)를 남긴다.
- **이름**: 영문·숫자·`_`(한글은 `desc`로). 식·항등식은 `블록:목표`(`demand:CN`). 기록 이름의 앞글자는 `data:`·`est:`·`hs:`·`sim:`·
  `an:`·`run:`·`prop:`. 파일 형식마다 형식 이름과 판을 적고, 바꾸면 판을 올리고 옛 것을 계속 읽는다.
- **이유**: 텍스트 파일이라 비교·버전 관리·Claude 편집이 쉽고, 부품이 저마다 혼자서도 쓰이며 조립하면 모형이 된다(레고).
  조립 층은 워크파일 API(D2) 위의 얇은 층이라 계산은 늘 엔진 한 곳에서 한다.

## D33. 작업 기록과 보이는 계산 (2026-11-09, 0.8에서)

- **결정**: 계산(추정·HS·전망·분석·스크립트)은 사람의 단추나 명령이 있을 때만 하고, 할 때마다 `work/<종류>/<id>/`에 기록을 남긴다 —
  한 줄 목록 `work/log.jsonl`, 결과 값(CSV·JSON), 사람이 읽는 카드 `summary.md`(md 렌더러 하나로 — 표와 `vega-lite` 차트),
  **알아서 한 것** 목록(실패 대체·결측 제외·채우기·보정항 규칙 값·실제 표본 등). 기록은 고치지 않는다 — 다시 계산하면 새 기록.
- 미리보기(불러오기·보고서 보내기·`--dry-run`)는 기록을 남기지 않고 '미리보기'로 표시한다.
- 정의 파일이 바뀔 때마다 `work/history/`에 전후와 차이(누가: 사람·명령·바깥)를 남기고, 되돌리기도 기록한다. 제안은 `work/proposals/`.
- 정리는 사람이 고를 때만(`equion work clean --dry-run`으로 목록 먼저). 고정한 기록과 노트·보고서가 쓰는 기록은 빠진다.
- 프로젝트 안의 `equion run` 기록은 `work/run/<id>/`(`run:`), 프로젝트 밖에서는 지금처럼 `out/<id>/`(D5).
- **이유**: 사람과 Claude가 같은 곳에서 같은 결과를 보고, 결론마다 근거 기록의 이름을 댈 수 있다. 뒤에서 몰래 도는 계산이 없다.

## D34. 자료 — 원자료·정의·회차 (2026-11-09, 0.8에서)

- **결정**: 자료는 세 층이다. ① 원자료 `DATA/raw/` — 받은 그대로, 아무도 고치지 않는다(같은 이름은 날짜를 붙여 나란히, 해시를 적는다)
  ② 정의 `DATA/series.toml`(출처·**불러오기 틀**·변환·단위·설명)·`DATA/derived.txt`(파생식) ③ 자료 회차 `work/data/<회차>/` —
  '자료 만들기'로만 생긴다.
- **불러오기 틀**: 시트·열 이름 줄·단위 줄·시점이 행인지 열인지·시점 꼴·숫자 꼴·결측 표시. 0.8은 시점이 행인 표부터, 시점이 열인 표와
  여러 머리줄은 2차판. 자료를 갱신할 때 같은 틀로 다시 읽고 어긋나면 알린다(틀 검사).
- **회차**: 만들기와 바꾸기를 나눈다 — 새 회차를 만들어도 '이 회차로 바꾸기'(`equion data use`)를 해야 쓴다. 지금 회차는
  `equion.toml`의 `[data] vintage`. 다른 회차로 계산한 결과에는 '자료 회차 다름'을 붙이고 저절로 다시 계산하지 않는다.
- 계산 결과는 실측 자리에 쓰지 않는다(`hs:hs_0009:CN`처럼 기록 이름으로 가리킨다). 값마다 종류(실측·변환·결측·가정·채움·해·대체·제외·보정).
- 상대 기간 `last`·`next:n`·`last-n:last`를 쓸 수 있고, 실제로 쓴 기간은 기록마다 풀어서 적는다.
- git에는 정의만 넣는다 — `work/`·`exports/`·`DATA/raw/`는 `equion new`의 `.gitignore`가 기본으로 뺀다(바꾸는 것은 사람). 실제 자료는
  이 저장소에 넣지 않는다(D30).
- **이유**: 무엇이 언제 어디서 왔는지, 어떤 자료로 계산했는지가 늘 보이고, 원자료 + 정의만 있으면 회차를 다시 만든다(재연).

## D35. 모형의 계수 — 채택 계수 고정, 스크립트는 기준을 통과한 식만 (2026-11-09, 0.8에서)

- **결정**: 평소에는 채택한 계수로 풀고 다시 추정하지 않는다. 새 자료로 다시 추정하는 일은 사람이 누를 때(다시 추정 → 옛 계수와 비교 →
  사람이 채택)나, 스크립트에 적은 정책으로만 한다 — 틀의 기본은 `--adopt if_pass`(판단 기준 `[criteria]`을 통과한 식만 새 계수 채택,
  아니면 옛 계수를 쓰고 표시). 정책이 채택하면 바뀜 기록에 "스크립트 <이름>이 채택"으로 남는다.
- **이유**: 같은 모형이 자료 회차마다 몰래 달라지지 않으면서도, 자료만 넣으면 새 결과가 나온다. 판단 기준에 걸린 식만 사람이 본다.

## D36. Equion 스크립트(`.eqs`) — 재연의 단위 (2026-11-09, 0.8에서)

- **결정**: 원자료에서 보고서까지 한 번에 다시 하는 단위는 Equion 스크립트다 — 한 줄이 `equion` 명령 하나(앞의 `equion`은 빼도 된다).
  `# 주석` · `## 제목`(단계 묶음) · `param 이름 = 값` · `{이름}`(매개변수·`{vintage}`·`{last}`·`{today}`) · `expect … --stop/--flag` ·
  `run 다른.eqs` · `py 스크립트.py`(명령줄에서만 — 앱은 실행하지 않는다). 반복문·조건문·변수 계산·셸 명령은 넣지 않는다 — 모자라면 Python.
- `equion run x.eqs`가 실행하고(지금 `equion run`의 `--set`·`--dry-run`·`--fail-on`·`--threads` 등을 그대로), `equion check x.eqs`가 실행 없이 검사한다.
  실행 기록에는 값을 바꿔 넣은 뒤의 스크립트·단계별 기록 이름·쓴 정의 파일의 사본·자료 회차·판이 들어가고, `--replay`가 그때 그대로 다시 돈다.
- 종료 코드는 지금 약속(0·1·2·3, D15) 안에서 쓴다 — **구현(E5)**: `expect --stop`에 걸리면 2(결과 확인 실패 — `--fail-on`과 같은 갈래),
  단계가 실패하면 그 단계의 종료 코드, 실행 전 검사 문제는 3, `--replay`에 다른 단계가 있으면 2(CHANGELOG).
- 노트의 ```` ```equion ```` 블록과 같은 문법이다. Desk의 흐름 화면은 이 스크립트를 단계로 보여 주고 고친다.
- **이유**: 명시적으로 재연되고(원자료 + 정의 + 스크립트 = 결과), 터미널·노트·AI와 같은 말이며 짧다. 등록부의 명령만 돌아서
  AI가 써도 임의의 코드가 돌지 않는다. EViews 프로그램 문법(.prg)이 아니다(D13).

## D37. 분석 등록부·노트·보고서 (2026-11-09, 0.8에서)

- **결정**: 명령과 분석은 **등록부** 한 곳에 적는다(이름·대상 종류·옵션·엔진 함수·결과·만드는 것). 명령줄 옵션·Desk 폼·도움말·AI 안내가
  여기서 나오고, 노트·스크립트가 부를 수 있는 것의 허용 목록이다. 분석은 `equion an <분석> <대상>` — 분석마다 기록(`an:`).
  시리즈를 만드는 분석은 '정의로 남기기'로만 자료에 들어가고, 식을 내는 분석은 '후보로 남기기'로만 모형 후보가 된다.
- **노트**(`notes/*.md`): 명령 블록 + 펼친 md 결과 구역. 실행은 명령이 있을 때만(`equion note run`), 다시 실행하면 새 기록, Python 블록은 터미널에서.
- **보고서**(`reports/*.md`): 명령 블록 없이 결과만 보낸다(`equion report add`) — 차트 자료는 보고서 옆 폴더로 복사, 구역에는 보이지 않는
  표시(기록·보낸 모양). 새 기록으로 바꾸기는 사람이 누를 때만, 차이를 보이고 손으로 고친 곳은 묻는다.
- 기초 분석(기술 통계·히스토그램·상관표·ACF·PACF) 추가는 2차판.
- **이유**: 분석 하나를 더하면 명령·화면·도움말·AI 안내가 함께 생기고, 모든 결과가 같은 md 카드라 노트·보고서·Lectern에서 그대로 읽힌다.

## D38. 정의 파일을 고치는 데 `tomlkit` (필수 의존성 추가, 2026-11-09, 0.8에서)

- **결정**: 패키지의 필수 의존성에 `tomlkit`(순수 Python·MIT)을 더한다. 명령(`adopt`·`an keep`·`data use` 등)과 Desk가 `equion.toml`·
  `series.toml`·`adopted.toml`을 고칠 때 사람이 쓴 주석·순서·서식을 지킨다. 읽기만 하는 곳은 표준 라이브러리 `tomllib`.
- **이유**: 정의 파일은 사람과 Claude가 함께 고치는 글이라 명령이 주석을 지우면 안 된다. 자체 편집기는 품과 버그 위험이 크다.
  D17(새 필수 의존성은 결정 기록으로만)에 따른 기록이다. 하한 판은 0.8 구현 때 `lowest` CI로 정한다.

## D39. Desk 런타임과 배포 (2026-11-09, D29 변경)

- **결정**: 설치본은 설치 폴더 안에 **Python 런타임 하나**(python-build-standalone CPython 3.13 + `uv.lock`에 잠긴 패키지를 미리 설치)를 넣는다.
  앱과 계산 프로세스는 격리 모드로 돌고(사용자 PC의 Python·`PYTHONPATH`·사용자 site-packages를 쓰지 않는다), Desk 터미널의 PATH 맨 앞에도
  같은 런타임을 둔다. 설치는 사용자별(관리자 권한 없음), Inno Setup, WebView2 설치 도우미 포함. D0 시험판에서 1초 응답·PC 여덟 가지
  설치 시험을 넘지 못하면 PyInstaller 앱 + 터미널용 런타임으로 바꾼다.
- 코드 서명·인터넷 없는 PC용 큰 설치본은 배포를 넓힐 때(D29의 '나중에 정할 것' 그대로).
- Lectern(같은 저자, MIT) 0.69.1(`cd7fb26`)에서 코드를 복사하고 고지를 남긴다(D10). Lectern 쪽 수정(LC1~LC6)은 2차판에서, 다른 프로젝트에도
  쓰이는 일반 기능으로만 한다.
- **바뀌는 결정**: D29(PyInstaller onedir → 런타임 하나).
- **이유**: 설치만 하면 PC의 Python과 무관하게 돌고, 앱과 터미널의 `python`·`equion`이 같은 판이라 터미널에서 만든 결과를 앱이 같은 판으로 읽는다.

## D40. Desk 개발 시작 — D0를 여섯 걸음으로, 빠진 것 채우기 (2026-11-11, 단계 D에서)

단계 E가 끝나 Desk 개발을 시작하며 개발 계획을 점검했다. 뼈대(D0~D5)는 그대로 두고 아래를 정했다.

- **재 본 것**: 예제 프로젝트에서 띄워 둔 프로세스 안의 추정은 0.02~0.04초, 과거 재현 0.04~0.06초, 전망 0.15초. 명령마다 새 프로세스를
  띄우면 1.7초(그중 `import equion` 1.3초)라 1초 기준(S1)을 넘는다 — **작업 프로세스를 띄워 두는 것이 필수**다. 큰 모형은 D0-3에서 잰다.
- **D0를 여섯 걸음으로**: D0-1 `desk/` 뼈대·uv workspace → D0-2 창·서버·테마·터미널(Lectern에서 최소 복사) → D0-3 작업 프로세스와
  추정 한 화면(1초 — 예제와 합성 큰 모형) → D0-4 런타임 묶기(크기·격리) → D0-5 설치본(Inno Setup) → D0-6 PC 여덟 가지 점검표.
- **실행기**: D0에서는 바로 가기(`pythonw.exe -I -m equion_desk`)로 시작한다. 작업 표시줄 아이콘·보안 프로그램에서 문제가 나면 전용 exe로 바꾼다.
- **작업 프로세스**: 프로젝트마다 띄워 둔 프로세스 하나가 `eqn.project`의 함수를 부른다. 취소는 프로세스를 끝내고 다시 띄운다 — 기록은
  임시 폴더에 쓴 뒤 옮기므로(D33) 중간에 끝나도 깨지지 않는다. 터미널에서 친 명령은 `work/log.jsonl` 감시로 알아챈다.
- **workspace의 Python 범위**: uv는 구성원의 범위를 겹친 것으로 잠근다. `equion-desk`의 `requires-python`은 패키지와 같게 둔다
  (`>=3.12`) — 좁히면 잠금 파일에서 3.12가 빠져 패키지 CI가 깨진다(시험으로 지킨다). 설치본의 런타임은 3.13 그대로(D39).
- **앱 의존성**: flask·waitress·watchdog은 어느 OS에서나, pywebview만 Windows에서(D29). 최상위의 `uv sync`는 지금처럼 `equion`만 설치하고,
  앱까지는 `uv sync --all-packages`.
- **보기 파일(`VIEWS/`)**: 패키지에 아직 없다 — D4에서 패키지 작업으로 함께 넣는다.
- **화면 시험**: 서버 API 시험(pytest, 3 OS)에 더해 D1부터 화면 점검(playwright — Lectern의 방식)을 Windows에서 돌린다.
- **설치본 빌드를 D1로 당긴다**(계획은 D5): 묶음이 끝날 때마다 설치 파일로 확인한다. **D2는 둘로**: D2a 식 작업대, D2b 자료 작업대·분석 탭.
- **Lectern 복사 기준**은 0.69.1(`cd7fb26`) 그대로 — 0.70.0에서 달라진 것은 업무 관리 기능이라 Desk에 필요 없다.
- **0.8.0 태그**: 가이드 시험 의견을 반영한 뒤, 늦어도 D1 전에. D0는 태그에 기대지 않는다(같은 저장소의 패키지를 쓴다).
- **바뀌는 결정**: D28(앱 의존성 — PyInstaller 없음, 서버 의존성은 3 OS) · D31(D0 걸음·D1 설치본·D2 나눔).

## D41. Desk D1(뼈대) — 앱 프로세스는 읽기만, 알림 줄 하나, 화면의 색과 틀 (2026-11-11, 단계 D에서)

D1(뼈대 — 프로젝트 탭·사이드바·가운데 탭·작업 기록 띠·바뀜 알림·md와 카드 보기·지난 화면)을 만들며 정한 것.

- **앱 프로세스는 `equion`을 불러오지 않는다.** 계산과 정의 읽기(개요·추정·과거 재현·전망·바깥 고침 적기)는 작업 프로세스에 시키고,
  기록·카드·파일은 `work/`와 프로젝트 폴더에서 그대로 읽는다(`records.py`·`projects.py`). 창이 뜨는 시간과 메모리를 아끼고, 계산이 도는
  동안에도 화면이 기록과 파일을 읽는다. 시험이 지킨다(서버 모듈을 불러온 뒤 `sys.modules`에 `equion`·`pandas`가 없음).
  그래서 감시하는 정의 파일 목록(`watch.DEFINITIONS`)은 패키지의 `history.PATTERNS`를 옮겨 둔 것이고, 둘이 같은지 시험이 본다.
- **작업 프로세스는 정의 파일이 바뀌면 프로젝트를 다시 연다.** 요청마다 정의 파일의 크기·시각을 견주고(밀리초 아래) 달라졌을 때만
  `eqn.project()`를 다시 부른다 — 블록 파일을 밖에서 고친 뒤의 추정이 옛 식으로 도는 일이 없다. 계산은 여전히 명령이 있을 때만 한다(§2.4-1).
- **알림 줄 하나(긴 폴링).** 서버의 `Feed`에 새 기록(`record`)·바뀜(`change`)·정의 바뀜(`defs`)·파일 나무(`tree`)·작업 줄(`job`)·탭(`tabs`)을
  넣고 화면은 `GET /api/events?since=N` 하나로 받는다. 웹소켓은 쓰지 않는다 — 터미널이 이미 긴 폴링이고, 의존성이 늘지 않는다.
- **감시는 두 겹.** watchdog(운영체제의 변경 알림)이 깨우면 바로, 깨우지 않아도 2초마다 **상태를 견줘서** 알림을 만든다(로그 파일의 크기·
  바뀜 기록의 번호·정의 파일의 크기와 시각). 알림을 그대로 믿지 않으므로 빠지거나 겹쳐도 화면이 틀리지 않고, 네트워크 드라이브처럼
  알림이 오지 않는 곳에서도 늦게나마 뜬다.
- **바깥 고침은 Desk가 바뀜 기록에 적는다(K7).** 정의 파일이 명령 밖에서 바뀌면 0.6초 뒤 작업 프로세스가 `History.scan()`을 부른다
  (명령이 고친 것이면 그 명령이 이미 적었으므로 아무것도 생기지 않는다). 프로젝트를 열 때도 한 번 불러 "꺼져 있는 동안 바뀐 파일"을 알린다.
  적지 못하면(방금 쓴 파일을 백신이 쥐고 있을 때 등) 몇 번 다시 한다. 화면은 파일을 고치지 않는다 — D1의 파일 보기는 읽기 전용이고
  고치는 화면은 D2부터다.
- **기록에 적는 명령은 터미널에서 치는 글 그대로**(`equion est demand:CN`) — Desk의 단추로 했든 터미널에서 했든 기록의 `command`가 같은
  모양이라 그대로 복사해 다시 돌린다. '누가'만 다르다(`desk`·`terminal`·`claude`).
- **지난 화면은 사용자 폴더의 `config.json` 하나에**(`%APPDATA%\EquionDesk\`) — 프로젝트 탭·고른 탭·최근 폴더·창 크기·화면 설정(바탕·글자 크기·
  폭)·프로젝트마다 화면 상태(연 탭·쓰던 식·펼친 폴더). 프로젝트 폴더에는 쓰지 않는다(프로젝트는 여럿이 함께 쓰는 정의와 기록만).
  화면이 고칠 수 있는 설정은 이름·형식의 허용 목록으로 받고, 깨진 파일은 기본값으로 뜬 뒤 옆에 `.bad`로 남긴다.
- **창은 하나, 프로젝트는 탭**(Lectern D34): 또 실행하면 이름 있는 파이프로 폴더를 넘기고 끝낸다(`instance.py` — Lectern에서 복사).
  탭마다 작업 프로세스 하나·터미널 하나, 되살린 탭은 화면이 부를 때까지 작업 프로세스를 띄우지 않는다. 탭은 8개까지.
- **작업 프로세스는 작업 개체 안에서 돈다**(`jobs.py` — '닫으면 함께 끝내기'). 앱을 강제로 끝내도 큰 모형의 계산이 남아 돌지 않는다.
- **화면의 색과 틀.** 뼈대(제목줄의 프로젝트 탭·사이드바·가운데 탭·오른쪽 터미널·상태줄)는 Lectern을 따르고, 색은 따로 잡았다 — 종이(따뜻한
  흰색)와 잉크, 강조는 청록. Lectern(파랑)과 나란히 띄워도 가려진다. 색·글꼴·치수는 `web/css/tokens.css` 한 곳의 이름으로만 쓰고 밝은·어두운
  바탕을 함께 둔다(기본은 운영체제 설정). 터미널은 어느 바탕에서나 어둡다 — 그 안에서 도는 프로그램(Claude Code 등)의 색이 어두운 바탕에
  맞춰져 있다. 실측은 잉크·적합(해)은 청록 — 식 작업대의 차트와 카드의 차트가 같은 색을 쓴다. 스타일과 스크립트는 새로 썼다(프레임워크 없음).
- **아이콘은 코드로 그린다**(`desk/build/icon.py` — 청록 둥근 네모에 흰 가로줄 셋(항등 '≡'이자 E)과 점 하나). 다른 프로그램의 아이콘을 옮기지
  않고(D13), 그리는 도구에 기대지 않는다. 실행기가 바로 가기(`pythonw.exe`)라 창의 아이콘은 앱이 뜨면서 달고, 바로 가기·우클릭 메뉴·제거 목록은
  설치 폴더의 `.ico`를 가리킨다.
- **문서·차트 라이브러리**: markdown-it·DOMPurify·Vega·Vega-Lite를 Lectern이 쓰는 판 그대로 넣는다(D10). md 속 HTML은 글로만 보이고 그린 뒤
  한 번 더 정화한다. 차트의 자료는 프로젝트 안의 파일만(서버가 폴더 밖을 거절), 바깥 주소는 읽지 않는다. Vega가 식을 함수로 만들어 돌려
  CSP의 `script-src`에 `'unsafe-eval'`을 둔다(Lectern D14와 같다 — 바깥으로 나가는 길은 `connect-src 'self'`가 막는다).
- **'터미널로' 단추는 붙이기만 한다**(K5): 이름·명령을 터미널에 Enter 없이 붙인다. 실행은 사람이 한다 — 셸로 가는 길은 사용자의 키 입력과
  사용자가 누른 단추뿐이다. 조립 검사·항등식 검사·되돌리기처럼 아직 화면이 없는 일은 이 단추로 명령을 건넨다.
- **CI**: `desk-ui`(playwright로 실행기의 Edge를 몰아 화면까지 — 터미널에 친 명령의 기록이 띠에 뜨고 카드로 열림, 닫았다 열면 이어짐),
  `desk-installer`(설치 파일 만들기 → 조용히 설치 → 설치 폴더의 런타임만으로 기동 시험 → 제거, 설치 파일은 작업 결과물로 14일).
- **패키지에서 고친 것**: 기록 폴더를 제자리로 옮길 때 Windows에서 잠깐 거절되면 다시 한다(`equion.work.store.move_into_place`) — 감시·백신과
  함께 돌 때 명령이 드물게 실패할 수 있었다.
- **뒤로 미룬 것**: 후보 목록·겹쳐 보기·채택과 파일 고치기(D2a), 조립 보기·HS 화면(D3), 터미널 여러 개와 터미널 모음(필요해질 때),
  고정·메모·되돌리기 단추와 제안 카드(D5 — 지금은 명령으로), 큰 모형의 과거 재현 진행률(D3 — 지금은 지난 시간과 취소).

## D42. Desk D2a(식 작업대) — 후보 목록이 한가운데, 채택은 보이고 나서 (2026-11-11, 단계 D에서)

D2a(W1 식 작업대 — 식 다듬기·후보 견주기·겹쳐 보기·채택)를 만들며 정한 것. 겨눈 장면은 혼자 장면 2(식 하나 다듬기)와 장면 2(소비함수 고르기)다.

- **화면의 순서는 식 칸 → 후보 목록 → 고른 기록의 결과.** 추정할 때마다 후보 목록의 맨 위에 한 줄이 생기고 그 줄이 곧 요약(조정 R²·표준오차·기준)이라,
  바로 앞의 시도들과 위아래로 견준다. 그 아래에 계수표가 온다 — 기본 창 크기(1360×860, 터미널을 연 채)에서 계수표까지 한 화면에 들어오게
  머리줄·단추 줄·적합 통계(한 줄 띠)를 줄였다. 목록은 3줄 반 높이(더 보려면 높이 단추·스크롤), 좁으면 덜 중요한 열부터 감춘다(컨테이너 질의).
- **같은 계산은 한 줄로 모은다(×n).** 식·표본·표준오차·자료·추정법이 같은 기록은 목록에서 한 줄이다(대표는 지금 보는 것 > 채택한 것 > 단독 모의가
  있는 것 > 가장 새것). Ctrl+Enter를 여러 번 눌러도 목록이 같은 줄로 메워지지 않는다. 기록은 모두 남아 있고 작업 기록 화면에는 다 보인다.
- **견줄 수 없는 칸은 흐리게.** 지금 보는 기록과 종속변수가 다르면 R²·SE·AIC·BIC, 표본이 다르면 AIC·BIC를 흐리게 하고 까닭을 알린다(엔진의
  `compare` 경고와 같은 규칙). 가장 좋은 값(굵게)은 견줄 수 있는 줄 가운데서만, 모두 같으면 표시하지 않는다.
- **후보 목록은 앱이 기록을 직접 읽어 만든다**(`records.read_candidates` — `record.json`의 요약, 기록은 고치지 않는 파일이라 한 번 읽은 것은 들고 있는다).
  사람·터미널·Claude가 낸 것이 한 목록이고, 밖에서 생긴 추정 기록은 알림 줄로 와서 목록에 표시와 함께 더해진다(고른 줄은 그대로).
- **치는 동안에는 문법만 본다(계산이 아니다 — 기획안 §2.4-1의 예외).** 작업 프로세스의 `check`가 식을 읽어만 보고(1~2ms) 종류·목표·자료에 없는 변수를
  알린다. 읽을 수 없는 식·항등식·자료에 없는 변수·이 부품의 목표가 아닌 식은 까닭을 보이고 추정 단추를 막는다. 다른 계산이 도는 중이면 검사는 기다리지
  않는다(`Worker.call(wait=False)`) — 검사 없이도 추정은 할 수 있다.
- **추정의 옵션은 셋만 앞에**: 표본(처음~끝, 상대 기간 가능)·표준오차(보통·White·HAC)·단독 모의(기본 켬 — 0.04초라 1초 기준에 영향이 없고 후보를
  견주는 데 쓴다). 기록 이름과 추정법은 톱니 단추 안에(추정법은 식이 정한다 — `@inst`면 TSLS, `c(n)`이면 NLS). 옵션은 탭과 함께 기억한다.
- **채택은 무엇이 바뀌는지 보이고 나서.** 확인 상자에 블록 파일의 그 줄(전·후)과 채택표의 줄, 판단 기준에 걸린 기록이면 그 까닭, 자료 회차가 다르면 그것을
  보인다. 하는 일은 `equion adopt`와 같고 바뀜 기록에 '누가 Desk · 명령 그대로'로 남는다. Desk에서 한 바뀜은 알림 카드를 띄우지 않는다(한 사람이 안다).
  되돌리기는 아직 명령으로(`equion history revert` — 화면의 단추는 D5).
- **'이 후보로 과거 재현'은 기준과 함께 푼다.** 작업 프로세스의 `hs_swap`이 지금 정의 파일·자료 그대로 푼 과거 재현 기록을 찾아(조립 명세의 파일 해시와
  자료 해시가 지금과 같은 가장 최근 것) 있으면 쓰고 없으면 먼저 푼 뒤, 부품을 바꿔 끼워 풀고 둘을 견준다(`hs --swap … --vs …`). 둘 다 기록으로 남는다.
  결과 카드는 변수마다 전후 RMSPE를 맨 위에 보인다(소수 둘째 아래의 차이는 '그대로'). 모형은 그 부품을 쓰는 것 가운데 `[hs] model`이 기본, 여럿이면 고른다.
- **기간을 짚어 더미를 넣는다.** 차트에서 기간을 누르면 그 기간의 실측·적합·잔차(몇 σ인지)가 차트 위에 뜨고, '이 기간 더미'가 식 칸에 `@d(기간)`을
  붙인다(꼬리 지시자 `@smpl`·`@inst`… 앞에). 계산은 추정을 누를 때다.
- **항등식은 추정하지 않고 실측으로 검사한다**(`equion ident … --check`와 같다 — 기록은 남기지 않는다). 맞으면 한 줄로, 어긋나면 차이 차트와 어긋난 기간.
- **패키지에서 고친 것**: 추정 기록이 계수 공분산(`cov` — 종류·이름·시차)을 적는다. `--cov`로 본 기록의 t값이 다른 까닭이 기록·카드에 남지 않았다.
- **화면 규칙 둘을 시험으로**: 스타일시트의 색은 `tokens.css`의 이름으로만(시험 B7), 화면 스크립트는 모두 문법에 맞게(B6 — node가 있을 때).
  화면 점검은 값 대신 `null`·`undefined`·`NaN`이 찍힌 곳이 없는지도 본다(Z2 — 실제로 한 곳을 잡았다).
- **뒤로 미룬 것**: 후보 묶음 폼(2차판), 표본 띠를 끌어 다시 추정·재귀 계수·표본 밖 예측 탭(지금은 표본 칸과 '진단 더 보기' — `an diag`의 CUSUM),
  강건 SE를 계수표 옆에 나란히(지금은 표준오차를 골라 다시 추정 — 그 기록이 따로 남는다), 블록 파일을 화면에서 고치기(D3의 조립 작업대와 함께),
  후보에 메모·고정(명령 `work memo·pin`).

## D43. Desk D2b-1(자료 작업대·분석 탭) — 세 층을 한 화면에, 만들기와 바꾸기는 따로 (2026-11-11, 단계 D에서)

D2b(W4 자료 작업대 · W8 분석)를 두 걸음으로 나눠 첫 걸음을 만들며 정한 것. 첫 걸음(D2b-1)은 **있는 정의로 자료를 돌리는 일**(받은 파일 넣기 →
자료 만들기 → 견주기 → 이 회차로 바꾸기)과 **분석 탭**, 둘째 걸음(D2b-2)은 **정의를 새로 짝짓는 불러오기 화면**(원자료의 열 ↔ 시리즈)이다.
불러오기 화면은 정의 파일을 새로 쓰는 일이라 패키지에 함수가 먼저 있어야 한다(화면이 TOML을 직접 쓰지 않는다 — D41). 겨눈 장면은 혼자 장면 4(새 분기
자료가 왔다)와 장면 5(계절조정 시리즈를 하나 더).

- **자료의 세 층이 설명이자 갈래다.** 화면 위의 세 칸(① 원자료 → ② 시리즈 → ③ 회차)이 자료가 어디서 와서 무엇이 되는지를 말하고, 누르면 그 층의
  목록이 아래에 온다. 그 사이의 **한 줄이 지금 할 일**을 말한다 — 정의를 읽지 못함 / 아직 만든 자료가 없음 / 새 회차가 준비돼 있음(견주기·바꾸기) /
  지금 회차를 만든 뒤 바뀐 것이 있음(자료 만들기) / 받은 상자에 새 파일 / 원자료·정의와 같음. 한 번에 하나만 보인다(앞의 것이 먼저).
- **만들기와 바꾸기는 따로, 저절로 하는 것은 없다.** '자료 만들기'는 새 회차를 만들 뿐 지금 회차를 바꾸지 않는다(`equion data build`와 같다 — 내용이
  같으면 만들지 않는다). 만든 직후 무엇이 달라졌는지(늘어난 값·고쳐진 값(개정)·그것을 쓰는 식과 모형)를 보이고, '이 회차로 바꾸기'는 `equion.toml`의
  어느 줄이 바뀌는지와 **다시 추정·풀기는 따로 시켜야 함**을 확인 상자에 보이고 나서 한다. 옛 회차는 지워지지 않아 같은 단추로 되돌아간다.
- **'다시 만드세요'는 근거와 함께.** 지금 회차의 `build.json`(정의 파일과 원자료의 해시)을 지금 파일과 견주어 무엇이 바뀌었는지 이름으로 알린다
  (`series.toml · 원자료 na`). 가장 새 회차가 이미 지금의 원자료·정의로 만든 것이면 만들기가 아니라 바꾸기를 권한다(`pending`).
- **원자료는 고치지 않고 넣기만 한다.** 받은 상자(`DATA/raw/inbox/`)의 파일마다 짝지은 원자료(이름·`inbox =` 규칙 — 패키지의 규칙 그대로)와 틀 검사를
  보이고, 틀이 맞지 않으면 까닭을 보이며 넣기를 막는다. 넣으면 `DATA/raw/`로 들어가고 출처가 그 파일을 읽으며 **받은 상자에서는 빠진다**
  (`equion data build --inbox`와 같은 뜻 — 같은 내용(해시)의 파일이 들어간 것을 확인한 뒤에만 뺀다). 옛 파일은 '읽지 않는 파일'로 남는다.
  화면이 아무 경로나 보내 복사시키지 못한다: 받은 상자의 파일 이름이거나, 창 모드의 파일 고르기 대화상자가 돌려준 경로뿐이다.
- **시리즈는 한 줄씩, 누르면 내력.** 줄마다 이름·설명 · 만드는 법(출처·열·변환 또는 파생식) · 구간 · 값의 수와 결측 · 쓰는 식의 수. 누르면 그 줄 아래에
  내력(원자료 → 열 → 변환 → 시리즈 — 파일은 눌러 연다), 차트(변환한 시리즈는 원자료 값과 겹쳐), 쓰는 식(눌러 식 작업대로), 분석으로 가는 단추가 온다.
  정의에는 있지만 지금 회차에 없는 시리즈는 '회차에 없음'으로 표시한다. 정의 파일은 화면에서 고치지 않는다(읽기 전용으로 연다 — 고친 것은 바로 보인다).
- **자료 한눈에는 개요보다 무겁다.** 원자료를 틀대로 읽어 보므로(예제에서 1초 남짓) 자료 작업대를 처음 열 때 읽고, 그 뒤로는 정의·폴더가 바뀔 때만
  다시 읽는다(`Project.loadData`). 사이드바의 '자료' 줄과 개요의 자료 칸은 읽은 뒤부터 손볼 것이 있으면 점으로 알린다.
- **분석 탭은 등록부가 그린다(D37).** 분석의 이름·갈래·대상의 종류·옵션(형·기본값·고를 값·도움말)이 모두 `equion.registry`에서 온다 — 화면이 아는 분석은
  없다. 고를 값의 풀이(`n 없음 · c 상수 · ct 상수+추세`)와 짧은 이름도 도움말에서 얻는다. 분석을 고르기 전에는 갈래마다 한 줄씩 목록으로, 고른 뒤에는
  「분석 · 대상 · 실행」 한 줄과 옵션, 대상으로 고를 이름(묶음·시리즈·부품·모형·블록·기록 — 여럿 받는 분석은 더하고 뺀다)이 온다.
- **실행 전에 같은 일을 하는 명령을 그대로 보인다.** 폼 아래의 한 줄(`equion an unitroot core --trend ct`)은 기록에 적히는 명령과 글자까지 같다
  (기본값과 다른 옵션만, 따옴표는 셸 규칙으로) — 화면 점검이 둘을 견준다. 누르면 복사한다.
- **결과는 같은 화면에, 카드 그대로.** 실행하면 기록(`an:`)의 `summary.md`를 폼 아래에 그린다(카드 머리의 표는 감춘다 — 위의 한 줄과 폼에 이미 있다).
  옵션을 바꿔 다시 돌리는 일이 한 화면에서 끝난다. 지난 분석을 누르면 그 기록과 함께 폼도 그때의 대상·옵션으로 돌아간다.
- **만드는 분석은 미리보기, 남기기는 보이고 나서.** 계절조정·파생·ECM·VAR…은 돌려도 아무것도 바뀌지 않는다고 알리고, '정의로 남기기'/'식 후보로 남기기'가
  무엇이 어느 파일에 적히는지(시리즈 이름은 고칠 수 있다)를 확인 상자에 보이고 나서 `equion an keep`과 같은 일을 한다. 정의로 남기면 자료 작업대가
  '회차에 없음'과 '자료 만들기'로 이어 받고, 식 후보로 남기면 추정 기록(`est:`)이 식 작업대의 후보 목록에 뜬다.
- **고친 것**: 옵션 이름표(`label.opt.check`)가 후보 목록의 네모 단추 스타일(`.check` — 폭 16px)을 함께 받아 눌려 있었다(식 작업대의 '단독 모의'도) —
  단추에만 걸리게 했다.
- **뒤로 미룬 것**: 불러오기 화면(D2b-2 — 원자료 미리보기·열 ↔ 시리즈 짝짓기·틀 고치기), 시리즈 여럿을 한 차트에 겹쳐 보기, 회차 지우기·고정,
  묶음 편집, 분석 결과를 노트·보고서에 붙이기(D4), 분석 옵션의 표본을 차트에서 끌어 고르기.

## D44. Desk D2b-2(불러오기 화면) — 정의를 쓰는 함수는 패키지에, 화면은 틀을 권하기만 (2026-11-11, 단계 D에서)

D2b의 둘째 걸음(W4의 불러오기 — 원자료의 열 ↔ 시리즈)을 만들며 정한 것. 겨눈 장면은 혼자 장면 1(받은 통계표를 시리즈로)이다. 이 걸음부터는
"남은 단계를 끝까지, 갈리는 곳은 만드는 쪽이 고른다"는 사용자의 말(2026-11-11)대로 묻지 않고 정했다 — 뒤집을 수 있게 까닭을 적는다.

- **정의를 쓰는 함수를 패키지에 먼저(0.8 다음 판).** `Project.data_preview`(원자료를 읽은 그대로의 줄 + 그 틀로 읽은 결과 — 쓰지 않는다)와
  `Project.data_define`(출처의 틀과 시리즈를 `series.toml`에 — tomlkit으로 주석·순서를 지키고 바뀜 기록에 남긴다), 명령줄 `equion data preview·define`.
  쓰기 전에 새 내용 전체(`load_defs(series_text=…)`)와 원자료의 열·변환(자료 만들기와 같은 계산 `_series_values`)을 검사한다 — 문제가 있으면 아무것도
  쓰지 않는다. 화면은 이 둘만 부른다(화면이 TOML을 쓰지 않는다 — D41·D43).
- **줄마다 칸 수가 다른 CSV를 읽는다.** 통계표는 표 위에 제목 줄이 있어 첫 줄의 칸 수가 적다 — 불러오기 화면이 맨 먼저 만나는 파일인데 읽지 못했다.
  칸 수가 고른 파일의 읽기(pandas)는 그대로 두고, 그 읽기가 실패할 때만 가장 긴 줄에 맞춰 채워 읽는다(하위 사용자의 자료 읽기가 바뀌지 않게).
- **화면의 순서는 ① 파일 → ② 틀 → ③ 시리즈 → ④ 저장.** 파일을 고르면 이미 그 파일을 읽는 출처가 있는지부터 본다 — 있으면 그 틀과 짝지은 열로
  열리고(고치기), 없으면 새 출처다(이름은 파일 이름에서 짓되 고칠 수 있다). 한 화면이 '새로 짝짓기'와 '틀 고치기'를 함께 한다.
- **'읽은 그대로'의 표가 틀을 말한다.** 열 이름 줄·단위 줄·시점 열·결측 표시로 읽은 칸을 표 위에 색으로 보인다. 줄 번호를 누르면 그 줄이 열 이름 줄,
  열 글자를 누르면 그 열을 시리즈로 고른다. 틀의 숫자를 치는 동안 표가 다시 그려져도 치던 칸에 그대로 있게 했다.
- **틀은 권하기만 한다.** 읽지 못했을 때 칸이 반 넘게 찬 첫 줄을 열 이름 줄로, 그 아래 시점 칸이 비고 숫자가 없는 줄을 단위 줄로, 숫자가 아닌 칸에
  `1,234` 꼴이 있으면 쉼표를 천 단위로, 짧은 글자(`-`·`…`)를 결측 표시로 — 단추로 권하고 사람이 누른다. 저절로 고르지 않는다(틀린 짐작이 조용히
  자료를 바꾸면 안 된다).
- **시리즈는 고른 열만, 이름은 영문.** 열마다 한 줄이고 고른 열만 입력 칸이 펼쳐진다(이름·단위·설명·주기 변환·결측 채움·계절조정). 열 이름이 영문이면
  그대로 이름으로, 한글이면 설명으로 옮기고 이름을 비워 둔다 — 영문이 아니거나 이미 있는 이름은 치는 동안 알린다. 주기가 프로젝트와 다르면 변환을 꼭 고른다.
- **미리보기는 기록을 남기지 않고, 안 되는 것은 오류가 아니라 까닭.** 열 하나를 변환대로 만들어 원자료 값과 겹쳐 보인다. 변환이 빠졌거나 안쪽 결측 때문에
  계절조정이 안 되면 그 까닭을 차트 자리에 보인다(서버는 200으로 `series_error`를 돌려준다 — 화면 점검의 '콘솔 오류 없음'이 잡았다).
- **저장은 무엇이 적히는지 보이고 나서.** 먼저 쓰지 않고 만들어 본다(`dry`) — `series.toml`의 차이와 같은 일을 하는 명령(`equion data define …`)을
  확인 상자에 보이고, 누르면 쓴다. 저장해도 자료는 생기지 않는다: 자료 작업대가 '회차에 없음'·'자료 만들기'로 이어 받는다(D43).
- **있는 시리즈는 빼지 않는다.** 이미 정의에 있는 열은 체크를 풀 수 없고(빼려면 `series.toml`에서 지운다) 이름도 고칠 수 없다 — 그 이름을 쓰는 식이
  있을 수 있다. 단위·설명·변환은 고친 키만 보낸다.
- **쓰던 짝짓기는 탭과 함께 기억한다**(기획안의 '초안' — 따로 파일을 두지 않고 화면 상태에). 받은 상자의 짝 없는 파일은 '새 원자료로 불러오기'가 넣고 연다.
- **뒤로 미룬 것**: 붙여 넣어 원자료로(클립보드), 열 이름·단위를 한꺼번에 붙여 넣는 표, 시점이 열로 가는 표·여러 머리줄(2차판 — D34), 결측 칸을 눌러
  원자료의 그 칸으로 가기, 파생식을 이 화면에서 치기(지금은 분석 탭의 '파생' → 남기기), 시리즈 정의 지우기·이름 바꾸기.

## D45. Desk D3(조립·과거 재현·흐름) — 모형 작업대 하나에 조립과 풀이, 원인은 읽어서 따라간다 (2026-11-11, 단계 D에서)

D3(W0 조립 작업대 · W2 모형 작업대 · 흐름 화면 · 회차 바꾼 뒤 할 일)를 만들며 정한 것. 겨눈 장면은 혼자 장면 5(모형을 조립해 풀어 보기)와
장면 4(오차의 원인 찾기)·장면 10(블록을 더해 다른 모형으로), 그리고 "스크립트를 화면에서 실행"이다.

- **W0와 W2를 모형마다 탭 하나로.** 탭 '모형 main'에 ① 조립 → ② 과거 재현 두 칸(자료 작업대의 세 칸과 같은 모양 — ③ 전망은 D4에서). 조립을 보다가
  바로 풀고, 풀다가 조립으로 돌아간다. 사이드바의 모형 줄과 개요의 '모형 작업대'가 연다.
- **조립은 읽기만 하므로 열 때 검사한다.** 구성(블록마다 식 — 끼운 모형에서 온 블록은 어디서 왔는지, 뺀 식은 줄을 그어), 블록 사이의 연결(주고받는 변수),
  풀이 순서(동시 블록 표시), 외생 변수와 자료 끝, 함께 쓰는 모형(블록 파일을 고치면 함께 바뀐다는 뜻). 문제가 있으면 맨 위에 모두 보이고 '풀기'를 막는다.
- **모형과 블록을 쓰는 함수를 패키지에(0.8 다음 판).** `Project.model_define`·`block_define`(명령줄 `equion model define`·`equion block define`) —
  쓰기 전에 새 설정 전체를 검사하고(`load_config(text=…)`), 주석·순서를 지키며, 바뀜 기록에 남긴다. 화면은 고르기 → equion.toml의 차이와 명령 보기 → 저장의
  두 걸음이다(D44의 불러오기와 같은 방식). 끌어 넣기는 하지 않는다 — 블록·모형·뺄 식을 누르는 칩으로 고른다.
- **정의 파일은 화면에서 글로 고친다.** 파일 보기에 '고치기' — 바뀜 기록이 지켜보는 정의 파일만(블록 파일·equion.toml·자료 정의·가정·시나리오·스크립트·
  노트·보고서. 작업 프로세스가 한 번 더 가린다). 치는 동안 읽어 본다(블록 파일은 줄마다 식 문법과 겹친 목표, TOML은 문법과 설정 검사 — 쓰지 않는다),
  저장(Ctrl+S)하면 `History.write_files`로 '누가 Desk'로 남는다. 문제가 있는 채로 저장하려면 한 번 더 묻는다. 쓰던 글은 탭과 함께 기억하고, 고치는 동안
  파일이 밖에서 바뀌면 덮어쓰기 전에 알린다. 전용 편집기(구문 색·자동 완성)는 두지 않는다 — 큰 편집은 편집기·Claude가 하고 화면은 그것을 바로 보인다.
- **과거 재현은 '무엇을 · 범위 · 방식'과 명령 줄.** 모형이나 그 블록 하나(블록이면 나머지는 실측), 범위(비우면 `[hs] range`), 방식(동태·정태·식마다).
  푼 기록은 목록에 쌓이고(터미널·스크립트가 푼 것도), 줄을 누르면 보이고 네모를 고르면 견준다.
- **풀이 상태를 숫자와 띠로.** 정상·일부식 제외·실패대체·실패의 수와 기간마다의 띠 — 정상이 아닌 기간은 무엇을 뺐고 무엇을 실측으로 대신했는지 글로
  적는다(엔진의 불변식 "실패한 해를 다음 기로 넘기지 않는다"가 화면에 보이게). '알아서 한 것'은 접어 둔다.
- **원인 따라가기는 계산이 아니라 읽기다.** 변수를 누르면 그 식의 입력마다 이 풀이에서의 오차(내생)나 '실측'(외생), 자기 시차를 보이고, 내생 입력을 누르면
  그 변수로 거슬러 올라간다(지나온 길은 위에 남아 돌아갈 수 있다). 식만 따로 모의한 기록(`est --sim`)이 있으면 식 자체의 오차를 함께 보이고, 없으면
  단추로 시킨다. '이 블록만 풀기'·'식마다 풀기'는 새로 풀어 방금 보던 풀이와 견준다 — 오차가 식 자체에서 오는지, 입력·누적에서 오는지 가르는 데 쓴다.
  오차를 식·입력의 몫으로 숫자로 나누는 것은 패키지에 없어 하지 않는다(있는 것만 정직하게 보인다).
- **흐름 화면은 스크립트의 글을 단계 줄로 편다.** 여는 것은 미리보기(`--dry-run` — 기록 없음)이고 실행은 단추다. 단계마다 무엇을 바꾸는지('바꿈'),
  끝난 모양(✓ 통과 · ! 표시하고 계속 · ✗ 멈춤)과 남긴 기록, '여기부터'(앞 단계는 건너뛴다). 매개변수는 칸으로(`--set`). 글을 고치는 것은 파일 보기의
  '고치기'로(단계를 끌어 옮기는 편집은 하지 않는다 — 글이 원본이다). Python 단계는 앱이 돌리지 않는다고 알리고 터미널 명령을 보인다.
- **하는 동안의 진행은 작업 프로세스가 알린다.** 요청 하나에 응답 하나이던 통로에 진행 줄(`{"progress": …}`)을 더했다 — 스크립트의 단계가 끝날 때마다
  작업 줄의 '3/11'과 흐름 화면의 단계 줄이 바뀐다. 취소는 그대로 프로세스를 끝낸다(끝난 단계의 기록은 남는다).
- **이 화면에서 시킨 스크립트가 고친 것은 알림 카드를 쌓지 않는다**(D41의 "Desk에서 한 바뀜"과 같은 까닭 — 단계 줄과 실행 기록이 말한다). 바뀜 기록에는 똑같이 남는다.
- **회차 바꾼 뒤 할 일은 자료 작업대에.** 지금 회차가 아닌 자료로 추정한 채택 계수·가장 최근의 과거 재현·전망을 읽어 알린다(다시 계산하지 않는다).
  '다시 추정해 견주기'는 기록만 남기고(`est --adopted`) 옛·새의 가장 크게 바뀐 계수·조정 R²·표준오차·판단 기준을 나란히 — 채택은 사람이 고른 식만,
  채택표의 바뀔 줄을 보이고 나서. 노트 전체 실행·'새 보고서 — 지난달에서'는 D4에서.
- **작업 기록에서 스크립트로.** 작업 기록 목록에서 기록을 골라 그 명령들을 초안으로(`equion script new`) — 흐름 화면이 연다.
- **가운데 탭의 한도를 14에서 24로.** 작업대가 늘어(자료·분석·불러오기·모형·흐름) 한 번의 작업에 탭이 14개를 넘는다 — 쓰던 식 작업대가 저절로 닫혔다.
- **뒤로 미룬 것**: 제안 받기·제안 카드(D5 — 장면 4의 4~6걸음), 조립 그림(블록을 상자와 화살표로), 끌어 넣기, 큰 모형 과거 재현의 진행률(어디에 시간이
  드는지 재는 것 포함), 두 과거 재현의 조립 명세 차이를 줄마다 보이기(지금은 변수마다의 전후), 실패한 기간을 차트에 표시, 단계를 끌어 옮기는 스크립트 편집.

## D46. Desk D4(전망·보고서) — 가정·풀기·결과를 한 화면에, 보고서는 구역만 바꾼다 (2026-11-12, 단계 D에서)

D4(W3 전망 작업대 · 보기 · 보고서로 보내기 · 보고서 검사와 새 기록으로 바꾸기 · 엑셀로)를 만들며 정한 것. 겨눈 장면은 혼자 장면 6(가정을 적어 전망)·
장면 8(결과를 보고서로), 장면 5(시나리오를 기준선과 견주기)·장면 6(달마다 같은 보고서를 새 기록으로)이다.

- **전망 작업대는 탭 하나.** 위에서부터 ② 풀기 줄(모형 · 기준선과 시나리오 칩 · 구간 · 견줄 지난 전망 · 자료 회차 · 같은 일을 하는 명령 줄),
  ① 가정 표, 보정항 한 줄, ③ 푼 전망의 목록과 결과. 사이드바 '작업대'의 전망, 모형 작업대의 셋째 칸(① 조립 → ② 과거 재현 → ③ 전망), 개요의 '전망'이 연다.
  개요의 '전망' 단추는 이제 바로 풀지 않고 작업대를 연다(가정을 보지 않고 푸는 단추는 두지 않는다).
- **가정 표는 외생 × 전망 구간의 칸.** 직접 적은 칸이 '가정'이고 마지막 값 뒤의 빈칸은 채우기 규칙(`[forecast] fill`)이 채운다('채움'). 전망 앞의 실측 두 기를
  위에 함께 보인다. 엑셀에서 복사한 칸들을 그대로 붙여 넣고, 위·아래·Enter로 칸을 오간다. **값 사이의 빈칸은 엔진이 채우지 않는다** — 화면이 그 칸을 붉게
  알리고 '풀기'를 막는다(엔진의 오류를 받기 전에). 저장은 `History.write_files`로 '누가 Desk'로 남긴다 — 가정 CSV는 사람이 쓰는 파일이라 패키지에 쓰는
  명령을 따로 두지 않았다. 이번 전망 구간의 줄만 바꾸고 지난 가정의 줄은 그대로 둔다. '풀기'를 누르면 저장하지 않은 가정을 먼저 저장한다.
- **가정을 고쳐도 저절로 다시 풀지 않는다**(계산은 단추를 누를 때만 — 기획안의 원칙). 푼 전망이 있으면 가정 표는 한 줄 요약으로 접어 결과가 먼저 보이게 한다
  (핵심 고리가 한 화면에 — 변수마다 직접 적은 칸 수·채움). 그 줄을 눌러 편다.
- **기준선과 시나리오를 한 번에 푼다(작업 하나).** 고른 것을 차례로 풀고 하는 동안 '1/2 base'를 알린다. 앞의 것이 풀린 뒤 하나가 실패하면 오류로 끊지 않고
  남긴 기록과 까닭을 함께 돌려준다. 함께 푼 것은 나란히 견주게 고른다.
- **연달아 시키는 일이 '바쁨'에 걸렸다.** 화면은 알림 줄의 '끝남'을 보고 바쁨을 풀었는데, 응답이 먼저 오고 '끝남'은 조금 늦게 와서 바로 이어 시킨 일
  (새 보고서 → 보내기)이 조용히 버려졌다. 응답에 일의 이름(`job`)을 돌려주어, 이 화면이 시킨 일은 응답이 오면 끝난 것으로 안다.
- **결과는 모양을 바꿔 가며 본다.** 수준 · 전기비 · 전년동기비 · 연간 · 기준선 대비(시나리오), 값의 종류(실측·해·가정·채움)를 칸의 색으로, 시리즈는 칩으로
  고르고(외생은 점선), 여러 기록을 고르면 연간 증가율을 나란히, 열 이름을 누르면 실측에 이은 전망 차트(견주는 기록과 함께). 표에는 전망 앞 실측 네 기만 보인다.
- **보기(`VIEWS/*.toml`)를 패키지에(0.8 다음 판).** 어느 시리즈를 어떤 모양으로 볼지를 이름으로 — `Project.views`·`view_define`, 명령줄 `equion view list·define`.
  화면의 '보기' 메뉴가 고르고 '이 보기 저장…'이 쓴다. 보기는 결과를 만들지 않으며 계산의 입력이 아니다(보기를 저장해도 기록이 낡지 않는다).
- **보정항의 규칙과 시나리오는 정의 파일을 고친다.** 작업대에는 무엇이 걸려 있는지만 보이고(규칙·판단 값 파일, 시나리오의 충격), '규칙 고치기'·'시나리오'가
  파일 보기의 고치기를 연다(D45). 폼은 2차판.
- **보고서로 보내기는 어디서나 같은 대화상자.** 전망 작업대와 결과 카드(추정·과거 재현·전망·분석)의 '보고서로' — 보고서(또는 그 자리에서 새 보고서),
  행(시리즈)·모양·연간·소수점, 표 제목, 보낼 곳(보고서의 작은 제목에서 고른다 — 패키지는 제목 줄 전체를 받으므로 화면이 찾아 준다), 차트도 함께.
  전망 작업대에서는 지금 보는 시리즈와 모양이 그대로 채워진다. 기록은 고치지 않는다.
- **보고서 탭은 검사와 바꾸기.** 보고서를 고르면 구역마다 정상 · 더 새 기록 · 낡음 · 손으로 고침 · 없는 기록을 보이고, '새 기록으로 바꾸기'는 구역마다 무엇이
  달라지는지(차이)를 먼저 보이고 나서 바꾼다(D44·D45의 "먼저 보이고 저장"과 같은 방식). 손으로 고친 구역은 고친 곳을 보이고 덮겠다고 할 때만 덮는다.
  글은 파일 보기의 '고치기'로 고친다 — 보고서는 사람의 글이고 화면은 구역만 다룬다.
- **엑셀로는 `exports/<이름>.xlsx`.** 보는 전망과 견주는 전망을 한 권으로(값·값의 종류·출처 시트), 같은 일을 하는 명령과 함께 알린다.
- **패키지에서 고친 것 셋.** ① 시나리오 기록의 수준(`levels.csv`)에 충격을 준 외생 변수가 기준선의 가정 경로로 적혀 있었다 — 푼 그 경로로 적는다.
  ② 보기(`VIEWS/`)가 조립 명세의 정의 파일에 들어 보기를 저장하면 모든 기록이 '낡음'이 되었다 — 계산의 입력이 아닌 것으로 뺀다.
  ③ 가정·보정항·시나리오를 고치면 추정·과거 재현·분석 기록까지 '낡음'이 되었다 — 그것을 읽는 전망 기록만 낡는다.
- **뒤로 미룬 것**: 회차 비교의 요인 나누기 화면(자료·가정·식의 몫 — 지금은 `--vintage`·`--vs`로 풀어 연간을 나란히 본다), 시나리오 폼·보정항 폼·판단 값 표,
  노트 ▶ 실행·노트에 담기, 과거 재현 결과에 보기 적용, '새 보고서 — 지난달에서'의 구역마다 바꿔 낄 기록 고르기(지금은 틀로 복사한 뒤 '새 기록으로 바꾸기'),
  보고서를 다른 형식으로 내보내기.

## D47. Desk D5(Claude·마감·설치본) — 맡기는 것과 받는 것을 같은 자리에서, 화면은 제안을 만들지 않는다 (2026-11-12, 단계 D에서)

D5(맡기기·제안 받기 · 제안 카드 · 바뀜 기록의 되돌리기 · `equion desk show` · Claude Code에 Equion 알려 주기 · 도움말 · 설치본)를 만들며 정한 것.
겨눈 장면은 장면 8(맡겼는데 결과가 나빠졌다 — 바뀜 기록과 되돌리기)과 장면 4의 4~6걸음(제안 받기 → 제안 카드 → 적용)이다.

- **'Claude ▾' 하나에 세 가지.** 맡기기(바로 고치고 명령으로 계산) · 제안 받기(파일은 그대로 — 제안만) · 이름만 보내기. 무엇에 관한 일인지(이름과 한 줄 요약)와
  방식을 적은 요청 글을 터미널에 **Enter 없이** 붙인다 — 사람이 이어 치고 Enter를 누른다(앱이 대신 보내지 않는다). 식 작업대·모형 작업대·전망 작업대·
  결과 카드의 머리에 둔다. 기획의 단추 둘(맡기기·제안 받기)을 메뉴 하나로 묶었다 — 머리가 좁고, 방식의 차이를 메뉴의 한 줄 설명으로 읽게 하려는 것이다.
  결과 카드의 '터미널로'는 이 메뉴의 '이름만 보내기'가 대신한다.
- **Claude Code가 없어도 된다.** `claude` 명령을 찾지 못하면 단추는 흐리게 보이고 메뉴가 설치를 안내한다(맡기기·제안 받기는 꺼진다). 화면의 모든 기능은
  그대로다(출시 관문). 'Claude Code에 Equion 알려 주기'는 `equion guide skill --install project`를 터미널에 붙인다(메뉴와 설정 — 한 번만).
- **화면은 제안을 만들지 않는다 — 읽고, 적용하거나 버린다.** 제안은 Claude(또는 사람)가 `equion propose new`로 만든다. 새 제안이 생기는 순간 알림 카드
  (누가·제목·바꿀 파일 수 — "아직 아무것도 바뀌지 않았습니다")와 사이드바 '제안'의 점이 뜬다. 제안 탭은 목록과 카드 — 지금 파일 대비 바뀔 내용의 차이,
  까닭, 식, 미리 계산한 결과(바꿔 끼워 푼 과거 재현이면 변수마다의 전후 RMSPE). '적용'은 바꿀 파일과 같은 일을 하는 명령을 보이고 나서 쓰고,
  바뀜 기록에 "제안 … 적용"으로 남는다. '적용하고 고치기'는 적용한 뒤 그 파일을 고치기로 연다(기획의 '고쳐서 적용'). '버림'은 까닭을 받아 남긴다.
- **낡은 제안은 덮겠다고 할 때만.** 제안을 만든 뒤 그 파일이 바뀌었으면 목록과 카드에 '낡음' — 차이는 늘 지금 파일과 견준 것이고, 적용하려면 "그 사이에
  고친 것을 덮는다"를 골라야 한다(`--force`).
- **제안·고정은 앱 프로세스가 그대로 읽는다**(`proposal.json`·`marks.json` — D41의 "기록·파일은 그대로 읽는다"). 차이를 내는 것과 적용·버림은 작업 프로세스
  (패키지)가 한다. 감시는 제안의 상태(열림·적용·버림)를 견줘 새 제안과 바뀐 상태를 알린다.
- **되돌리기는 바뀜 기록의 단추로.** 무엇이 돌아가는지(파일마다 '앞 내용으로'·'지움'·'되살림')와 명령을 보이고 나서 되돌린다 — 되돌린 것도 바뀜 기록에 남아
  다시 되돌릴 수 있다. 파일 여럿을 고친 바뀜은 **파일 하나만** 되돌릴 수 있다(장면 8의 3걸음: 범위 변경만 물리고 식 변경은 둔다) — 패키지에
  `History.revert(…, files=[…])`·`equion history revert h… --file 경로`를 더했다.
- **고정과 메모는 결과 카드에서.** 기록은 그대로 두고 `marks.json`에만 적는다(`WorkStore.mark` — `equion work pin·memo`). 작업 기록 목록에 고정 표시와 메모가
  보이고 '고정'으로 가려 본다.
- **`equion desk show <이름>`은 파일로 알린다.** 패키지는 앱을 불러오지 않으므로(D28) 앱의 파이프(창은 하나 — D41)를 쓰지 않고, 이름을 확인한 뒤
  `work/desk/requests.jsonl`에 한 줄을 덧붙인다. 그 프로젝트를 열어 둔 앱의 감시가 새 줄만 읽어 화면을 연다(기록·제안·자료 회차·부품·모형·파일·화면 이름).
  앱이 꺼져 있어도 명령은 실패하지 않고, 프로젝트마다 따로이며, 다시 띄운 앱은 지난 줄을 열지 않는다. 화면 이동만 한다.
- **도움말은 앱에 든 글 하나.** F1·제목줄의 단추·첫 화면에서 연다 — 화면의 지도, 핵심 고리, 고치는 것과 되돌리기, Claude와 함께, 같은 일을 하는 명령, 손버릇.
  자세한 사용법은 패키지 문서가 맡는다(앱에 문서를 통째로 넣지 않는다).
- **목록과 내용이 나란한 화면은 좁으면 위아래로.** 바뀜 기록과 제안 탭은 가운데 폭이 780px보다 좁으면 목록을 위에 둔다(터미널을 연 채로도 차이가 읽힌다).
- **WebView2 설치 도우미는 품지 않는다.** 없으면 설치할 때 알리고 Microsoft의 'WebView2 Runtime'을 안내한다(지금 그대로). Windows 11에는 기본으로 있고
  Windows 10도 대부분 있다. Microsoft가 배포하는 파일을 설치본에 넣으면 고지와 판 갱신을 떠안는다 — 없는 PC가 실제로 나오면 그때 다시 정한다.
- **판은 `0.1.0rc1`(출시 후보).** 1차판의 화면은 모두 들어갔다. 출시 관문 가운데 "다른 PC 여덟 가지 설치 점검"(점검표 ①③⑥⑦⑧)은 만드는 PC에서 할 수 없어
  남아 있다 — 그 점검을 지나면 `0.1.0`으로 올린다.
- **패키지에서 고친 것.** `propose new`와 `data build`가 임시 폴더를 제자리로 옮길 때 폴더를 지켜보는 프로그램(Desk의 감시 포함)이 파일을 잠깐 쥐고 있으면
  `PermissionError`로 실패했다 — 작업 기록처럼 기다렸다 다시 옮긴다(Desk를 띄운 채 Claude가 제안을 만들면 가끔 실패하던 것).
- **뒤로 미룬 것(2차판)**: 화면의 줄·칸을 짚어 보내기, 사람이 화면에서 '제안으로 남기기', 맡기기의 범위 고르기(식만·정의까지·설정까지 — 지금은 프로젝트
  `CLAUDE.md`의 규칙으로), 낡은 기록의 '다시 계산' 단추, 명령 찾기(Ctrl+K), '터미널 밖에서도 equion 쓰기'(PATH), 코드 서명, 영문 화면.

## D48. Desk의 터미널 색은 창의 바탕을 따른다 — Lectern과 같이 (2026-11-12, 사용자 지시)

D41에서 "터미널은 어느 바탕에서나 어둡다"고 정했던 것을 뒤집는다. 사용자가 1차판 출시 후보를 보고 "터미널이 계속 검은색이면 안 된다, 스타일에 따라 바뀌어야
한다 — Lectern을 참고"라고 했다.

- **터미널은 창의 바탕(밝게·어둡게)을 따른다.** 밝은 바탕에서는 밝은 터미널(본문의 흰 종이보다 한 톤 가라앉은 종이 색에 잉크 글자), 어두운 바탕에서는
  어두운 터미널. 바탕을 바꾸면 열려 있던 터미널도 바로 바뀐다(이미 찍힌 글도 새 색으로 다시 그려진다). 처음 그릴 때부터 맞는 색이다
  (`boot.js` — 흰·검은 화면이 번쩍이지 않게).
- **방식은 Lectern의 `terminal.js`와 같다.** 바탕·글자·커서·선택 색은 색 이름(`tokens.css`의 `--term-*`)에서 읽고, ANSI 16색은 밝기에 맞는 색표를 쓴다
  (밝은 색표는 Lectern의 것 — '흰색'을 프로그램이 또렷한 글자로 쓰므로 어두운 색으로 둔다). 셸과 프로그램(PSReadLine·Claude Code)은 어두운 바탕을 가정하고
  색을 고르기도 하므로, 글자와 그 칸 바탕의 대비가 4.5보다 낮으면 xterm이 글자 색을 고친다(`minimumContrastRatio`) — 밝은 터미널에서도 다 읽힌다.
- **'늘 어둡게'를 고를 수 있다.** 설정(톱니)의 '터미널 색 — 바탕에 맞춤 · 늘 어둡게'(설정 이름 `term_follow`, 기본은 따름 — Lectern의
  `terminal_follow_style`과 같은 뜻). 터미널 안의 프로그램 색이 어두운 바탕에서 더 잘 보인다는 D41의 까닭은 이 선택으로 남긴다.
- 색은 여전히 `tokens.css` 한 곳의 이름으로만 쓴다 — 터미널의 스크롤바도 터미널의 색 이름을 쓴다.

## D49. Desk의 릴리스 — `desk-v<판>` 태그와 GitHub 릴리스, 출시 후보는 사전 릴리스로 (2026-11-12, 사용자 지시)

사용자가 1차판 출시 후보를 마무리하고 "깃 푸시·릴리스"를 지시했다. Desk의 첫 릴리스라 방식을 정한다.

- **Desk는 `desk-v<판>` 태그와 GitHub 릴리스로 낸다.** 설치 파일(`EquionDesk-<판>-setup.exe`)을 릴리스에 붙인다. 패키지의 태그(`v<판>` —
  `release.yml`이 휠을 만든다)와 이름을 달리해 서로 건드리지 않는다(`desk-v…`는 그 워크플로를 깨우지 않는다). 설치 파일은 여전히 저장소에 넣지 않는다(D28).
- **출시 후보(`rc`)는 사전 릴리스로 표시한다.** `0.1.0rc1`은 1차판의 화면이 모두 들어간 판이고, 출시 관문의 "다른 PC 설치 점검"(점검표)이 남아 있다 —
  받는 사람이 그것을 알 수 있게 릴리스 글의 맨 위에 적는다. 점검을 지나면 `0.1.0`을 정식 릴리스로 낸다.
- **패키지는 이번에 판을 올리지 않는다.** 설치본에 든 `equion`은 `0.8.0` 태그 뒤의 미공개 변경(CHANGELOG의 '미공개' — 보기·정의 쓰기·`desk show` 등)을
  포함한 `main`의 것이다. 릴리스 글에 그 커밋을 적는다. 패키지 `0.8.1`(미공개 → 판)은 Desk `0.1.0`과 함께 낸다 — 출시 후보마다 패키지 판을 올리지 않는다.
- **PyPI에는 올리지 않는다**(지금처럼 꺼 둔다 — D19). 릴리스는 GitHub의 태그와 릴리스뿐이다.
- **CI는 꺼 둔 채로 낸다**(2026-11-12에 사용자가 멈추게 했다 — 다시 켜라고 할 때까지). 이 릴리스의 확인은 만든 PC의 것이다: 패키지 시험 전체, 앱 시험, 화면 점검,
  설치본의 설치·기동 시험·지우기, 실제 창. CI로 확인된 마지막 커밋은 D3이고, 그 뒤의 패키지 변경은 D4 푸시의 CI에서 세 OS를 통과했다(D5의 패키지 커밋은 돌지 않았다).
- 서명은 없다 — 처음 실행할 때 SmartScreen이 묻는다(릴리스 글에 적는다). 파일의 SHA-256을 릴리스 글에 적는다.
