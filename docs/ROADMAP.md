# 로드맵

세 단계(D1)의 진행 상황. 결정은 `DECISIONS.md`, 엔진 이력은 `IMPROVEMENTS.md`.

> 이 저장소는 2026-11-08에 `macro_model`에서 패키지만 떼어 새 기록으로 시작했다(D30). 아래에 나오는 `IMPROVEMENTS.md`·
> `REPO_SPLIT.md`·`PRESENTATION.md`, 한국 모델의 자료·방정식·드라이버(`DATA/`·`EQUATIONS/`·`HS/`·`scripts/`·`kmodel/`)와
> 한국 모델 시험(`tests/test_korea_model.py`·`compare_hs.py`)은 비공개 저장소 `macro_model`에 남아 있다.

## P0 — 엔진 v3 (완료, 2026-10-29)

- [x] 단일 DSL 파서·IR·블록 솔버·시나리오·전망·확률·control·MCE·TSLS/NLS (`IMPROVEMENTS.md` §9)

## P1 — 라이브러리: 워크파일 API (완료, 2026-10-29, 프로젝트 0.3.0)

- [x] 1-1 워크파일: `eqn.wfcreate`·`eqn.wfopen`(xlsx/csv·번들·옛 `.wt`), `smpl`, 시리즈 읽기·쓰기
      (`wf["X"]`), `genr`(DSL 식·Python 함수), `read`·`write`·`extend`·`fill`·`save`
- [x] 1-2 방정식 객체: `ls`·`tsls`·`nls`·`fixed`(현재 표본으로 추정), 결과표 `output()`, `resid`·`fitted`·
      `results`, 단일식 `forecast`
- [x] 1-3 모델 객체: `merge`(방정식·파일)·`append`(항등식)·`blocks`, 시나리오(override·exclude·조정항·
      충격·control), `solve` → 별칭 시리즈, `forecast`·`stochastic`·`control`·`multipliers`
- [x] 1-4 그래프·표 객체, 출력 수집기(`eqn.show`), `eqn.params`, `eqn.verbose`
- [x] 1-5 노트북 3종을 워크파일 스타일로 다시 쓰기
- [x] 1-6 테스트(`tests/test_workfile.py`)·문서(`USER_GUIDE.md` §2)

## P2 — CLI (완료, 2026-10-29, 프로젝트 0.4.0)

- [x] 2-1 실행기 + 출력 수집기 → 보고서 폴더(표·그래프·`report.html`·`manifest.json`·로그), 종료 코드
- [x] 2-2 `run`·`check`·`info`·`new` 하위 명령, `--smpl`·`--set`·`--params`·`--out`·`--run-id`·`--format`·`--fail-on`·
      `--threads`·`-q`/`-v`·`--log`·`-i`·`--watch`·`--dry-run`
- [x] 2-3 설치형 패키지 전환(D6), 테스트(`tests/test_cli.py`)·문서(`USER_GUIDE.md` §3)·예시 `scripts/korea_hs.py`
- [x] 웹 대시보드 삭제(D11 변경)

## 이름 변경 — Equion (완료, 2026-10-29, 0.5.0)

- [x] 패키지·import·명령 `macromodel` → `equion`(별칭 `eqn`), 워크파일 `.eqw`, 옛 형식 읽기 유지 (D16)

## 0.6 — 자체 통계 (완료, 2026-10-29, 0.6.0)

- [x] statsmodels 제거, 자체 OLS(이전과 계수·통계 동일)·TSLS 유사역행렬 (D17)
- [x] NLS 해석적 자코비안(IR 기호 미분)
- [x] 기간·주기 연산을 `data/periods.py` 한 곳으로(pandas 4 대비), pandas 2.2~3.1·scipy 1.14~1.18 검증
- [x] 강건 공분산(HC0~3·HAC)·진단 검정·단위근/공적분

## 0.7 — Equion 다듬기 (완료, 2026-10-30, 0.7.0)

품질·보안·배포
- [x] 로그(logging)·공개 버전 하나·공개/고급/내부 API 구분, `_legacy` 경고 (D18)
- [x] 보안: 비밀 값 가리기(`eqn.secret`)·`--redact`·레거시 pickle 기본 차단(`equion convert`)·방정식 입력 한도·퍼징 (D18)
- [x] 표 저장 npz(pyarrow 선택), 그래프 그림 정의 직접 생성 + 내장 plotly.js(plotly 선택) (D19)
- [x] 범위 의존성 + `uv.lock`, pytest, CI(Linux·Windows·macOS × py3.12~3.14, 하한·최신·사전 공개판·선택 의존성 없이·
      기준선·pip-audit), dependabot, 배포 워크플로(PyPI는 주인이 켤 때만), Windows 인코딩 수정 (D19)
- [x] 영문 README(`README.en.md`)·API 목록 자동 생성(지금 `docs/reference/api.md`)·저장소 분리 계획(`docs/REPO_SPLIT.md`, 계획만)

추정·모델·자료
- [x] WLS·GMM(J)·LIML·PDL·누락/불필요 변수 (D20) · AR(p) 오차·ECM·예측 평가(Theil·Diebold-Mariano) (D21)
- [x] 시스템 추정 SUR·2SLS·3SLS·FIML·식 사이 제약 (D22) · VAR·VECM (D23)
- [x] 동태 안정성·시나리오 기여도 분해(Shapley) (D24) · 희소 자코비안·stacked-time MCE (D25)
- [x] 메타데이터·페이지·주기 변환·Denton/Chow-Lin·STL/고전 계절조정 (D26)

시험
- [x] 상황별 시나리오 시험 641개(정상·경계·오용·연/월·명령줄 하위 프로세스)와 찾은 결함 수정, 회귀 시험
      `tests/test_scenarios.py`(합성 자료만) — IMPROVEMENTS §15

## 문서 체계 (완료, 2026-10-30, 미공개) — D27

- [x] 예제 자료 `eqn.datasets`(toy_q·toy_a·toy_m·klein_like, 실제 Klein 자료는 `klein(path)`로만)
- [x] 문서 검사 도구 `docs/build_docs.py`(예제 실행·출력 채우기와 비교·`examples/` 내보내기·링크·API 설명과 예제·doctest) + CI
- [x] 시작하기 · 튜토리얼 8편 · 레시피 · 해설 · 참조(API 자동 생성·명령줄·함수·출력·오류·파일 형식·예제 자료) · 사례 연구(한국 · Klein형) ·
      EViews 사용자 안내 · 영문 시작 문서 · `CHANGELOG.md`
- [x] 공개 API 전체 docstring(매개변수·돌려주는 것·오류·예제)
- [x] 옛 `USER_GUIDE.md`는 새 위치 안내로, 엔진 수준 API는 `docs/explain/engine.md`로

## 0.8 — 프로젝트·작업 명령·기록·스크립트 (완료, 2026-11-11, 0.8.0 — D31~D38)

Equion Desk 개발 계획(`DESK_DEVPLAN.md`)의 단계 E. 끝나면 Desk 없이도 Lectern 터미널과 Claude로 "자료를 넣고 `equion run monthly.eqs`"가 된다.
수치 코어(파서·IR·풀이·통계)는 고치지 않는다 — 워크파일 API 위의 새 층.

- [x] E1 프로젝트·조립(2026-11-09): `equion.toml`·블록·이름·조립 검사·블록 HS·바꿔 끼우기·항등식 검사·`eqn.project()`, 예제 프로젝트
      `equion new --template desk`(가상 분기 모형) — `assemble`·`ident` (D32). 채택표는 기록과 함께 E3로 — 지금은 모형을 만들 때 지금 자료로 추정하고 알린다
- [x] E2 자료 정의·회차(2026-11-09): 원자료·출처 해시, `series.toml`(불러오기 틀)·`derived.txt`, 회차·값의 종류, 틀 검사, 상대 기간 —
      `data add·build·use·diff·impact` (D34). 시점이 열로 가는 표(`time_axis = "columns"`)는 2차판에서(D60)
- [x] E3 작업 명령·기록(2026-11-09): `work/` 기록·조립 명세·알아서 한 것·`summary.md`(md 렌더러), 채택표 `adopted.toml`, 바뀜 기록·제안 —
      `est`·`adopt`·`compare`·`hs`·`sim`·`export`·`work`·`propose`·`history` (D33·D35)
- [x] E4 분석·노트·보고서(2026-11-09): 등록부·`an`·`note`·`report`, 묶음 (D37). 블록 후보(VAR를 블록으로)·기초 통계는 2차판
- [x] E5 스크립트·재연(2026-11-09): `.eqs` 해석기·`run x.eqs`·`check x.eqs`·`--replay`·`script new·export`, `DATA/raw/inbox/` (D36). `expect --stop` = 종료 코드 2
- [x] E6 안내·문서(2026-11-09): Claude용 모형 작업 안내 `equion guide`(`equion/help/guide.md` — 표는 코드에서)·스킬 초안 `guide skill`, 튜토리얼 9편, 파일 지도. 안내만 읽은 새 Claude가 예제의 월간 스크립트를 돌림
- [x] `tomlkit` 의존성(D38)

## 다음 (0.9 후보)

- [ ] 오류 메시지에서 문서 절 안내 — 0.8에서 옮김
- ~~외부 데이터 연결(ECOS·KOSIS — `equion data fetch`)~~ — 하지 않는다(D63, 2026-11-12 사용자 결정). 원자료는 사람이 받아 `data add`·받은 상자로 넣는다
- (한국 모델의 방정식 정련은 비공개 저장소 `macro_model`의 일이다 — D30)
- [ ] 비선형 시스템 추정(NLS·FIML의 계수 비선형식), X-13 대체(필요하면 별도 결정)

## 저장소 분리 (진행, 2026-11-08 — D30)

- [x] 패키지에서 한국 자료 떼기: 드라이버 지원 코드 → `kmodel/`, 패키지 시험·기준값을 예제 자료로, 한국 모델 시험 `tests/test_korea_model.py`
- [ ] 새 저장소 `samiblog/equion`: 패키지·문서·예제·시험·CI(깨끗한 기록), 상표 확인 뒤 공개
- [ ] `macro_model`이 `equion`을 판 번호로 가져다 쓰고 패키지 코드를 지운다(공개 뒤)
- (2026-10-30에는 보류로 정했다 — 주인이 공개를 원해 앞당김)

## P3 — 데스크톱 앱 Equion Desk (lectern 스타일, Windows 전용 — D29) — 개발 계획 확정 (2026-11-09, D31)

기획 자료(`DESK*.md`)와 개발 계획(`DESK_DEVPLAN.md`)을 따른다. 0.8(단계 E)을 먼저 끝내고 그 명령 위에 화면을 얹는다 — D0만 E와 나란히.
설치 파일 `EquionDesk-<버전>-setup.exe` 하나(Windows 전용, WebView2 — D29), 설치 폴더 안 Python 런타임 하나(D39). 코드는 이 저장소의
`desk/`에 별도 패키지 `equion-desk`(uv workspace, 의존 방향 `equion-desk → equion`, 태그 `desk-vX.Y.Z` — D28).

**1차판 equion-desk 0.1 (단계 D)** — 저장소 주인과 가까운 동료용, 서명 없는 설치본, 한국어 화면

- [ ] D0 시험판(E와 나란히): 런타임 묶기·격리 실행·Lectern 테마 창·터미널·작업 프로세스 — 추정 1초(S1), PC 여덟 가지 설치(S10)
  - [x] D0-1 `desk/` 뼈대·uv workspace·경계 시험 (2026-11-11, D40)
  - [x] D0-2 창·서버·터미널 · D0-3 작업 프로세스·식 작업대 한 화면 (2026-11-11 — 누른 뒤 화면까지 0.06초, 큰 모형에서도 추정 0.05초)
  - [x] D0-4 런타임 묶기(222MB) · D0-5 설치본(설치 파일 47MB — 개발 PC에서 설치·실행·제거 확인) (2026-11-11)
  - [ ] D0-6 PC 여덟 가지 점검(`docs/DESK_D0_CHECK.md`) — 다른 PC는 사용자가
- [x] D1 뼈대(2026-11-11, D41): 창은 하나·프로젝트 탭·사이드바(부품·파일)·가운데 탭·터미널·설정·감시, 작업 줄·작업 기록 띠·바뀜 알림,
      md·카드 보기(vega-lite 차트), 쓰던 식과 지난 화면 — 터미널에서 친 명령의 기록이 띠에 뜨고 카드로 열린다, 닫았다 열면 이어진다
  - [x] 화면의 색과 틀(밝은·어두운 바탕)·아이콘·작업 개체·설치본의 아이콘
  - [x] 화면 점검(`desk/tests/ui_check.py` — playwright)·CI의 `desk-ui`·`desk-installer`(설치본 빌드·기동 시험)
  - [ ] 설치 파일로 하는 손 점검(`docs/DESK_D0_CHECK.md` — 다른 PC는 사용자가)
- [x] D2 식·자료: W1 식 작업대, W4 자료 작업대(불러오기 화면·회차), 분석 메뉴·분석 탭
  - [x] D2a 식 작업대(2026-11-11, D42): 치는 동안의 문법 검사 · 표본·표준오차·단독 모의 · 후보 목록(같은 계산은 한 줄, 걸러진 것도 남김, 견줄 수 없는 칸 표시)
        · 겹쳐 보기 · 채택(바뀔 줄을 보이고 나서) · 이 후보로 과거 재현(전후 비교) · 기간 짚어 더미 · 항등식 검사 — 장면 2(식 고르기)가 화면으로
  - [x] D2b-1 자료 작업대·분석 탭(2026-11-11, D43): 자료의 세 층(원자료 → 시리즈 → 회차)과 지금 할 일 한 줄 · 시리즈의 내력과 차트 · 받은 상자와 넣기
        · 자료 만들기 → 견주기(개정·쓰는 식) → 이 회차로 바꾸기(바뀔 줄을 보이고 나서) · 등록부가 그리는 분석 폼과 실행 전의 명령 줄 · 미리보기 → 남기기(정의·식 후보)
        — 장면 4의 자료 걸음과 장면 5(계절조정 시리즈)가 화면으로
  - [x] D2b-2 불러오기 화면(2026-11-11, D44): 패키지 `data_preview`·`data_define`(명령줄 `equion data preview·define`) · 읽은 그대로의 표와 틀을 권하는 단추
        · 열마다 이름·단위·설명·변환·채움·계절조정과 미리보기 · 차이와 명령을 보이고 저장 — 혼자 장면 1이 화면으로
- [x] D3 조립·HS·흐름(2026-11-11, D45): 모형 작업대(① 조립 — 구성·연결·풀이 순서·외생·문제, 모형 고치기·새 모형·새 블록 ② 과거 재현 — 풀이 상태·적합도·견주기·
      원인 따라가기) · 정의 파일을 화면에서 글로 고치기 · 흐름 화면(스크립트의 단계·실행·여기부터) · 회차 바꾼 뒤 할 일 · 패키지 `model_define`·`block_define`
- [x] D4 전망·보고서(2026-11-12, D46): 전망 작업대(① 가정 표 — 붙여 넣기·값 사이의 빈칸 알림 ② 기준선과 시나리오를 한 번에 ③ 수준·전기비·전년동기비·연간·
      기준선 대비·값의 종류·견주기·차트) · 보기(패키지 `views`·`view_define`, `equion view`) · 보고서로 보내기 · 보고서 탭(구역 검사·새 기록으로 바꾸기) · 엑셀로
- [x] D5 Claude·마감·설치본(2026-11-12, D47): Claude ▾(맡기기·제안 받기) · 제안 탭(알림·차이·적용·버림·낡음) · 바뀜 기록의 되돌리기(파일 하나만도) ·
      고정과 메모 · `equion desk show`(패키지 — 요청 파일) · 도움말 · 설치본 `0.1.0rc1`. **남은 것**: 다른 PC 설치 점검(점검표) → `0.1.0`
- [x] 출시 후보 릴리스(2026-11-12, D48·D49): 터미널 색이 창의 바탕을 따른다 · `desk-v0.1.0rc1` 사전 릴리스(설치 파일 첨부 — 패키지는 `main`의 미공개 변경 포함,
      `0.8.1`은 Desk `0.1.0`과 함께)

- [x] 2차판 화면 — 대상에서 출발(2026-11-12, D50~D54 — [`DESK_V2.md`](DESK_V2.md), `main`의 Desk `0.2.0.dev0`): 세 열 1/3 · 왼쪽 작업대 줄과 탭 다섯(변수 · 분석 · 모형 · 파일 · 기록) ·
      변수 여럿 고르기와 우클릭 메뉴(등록부의 count) · 묶음 · 변수 창 · 그룹 창 · 분석 탭(개별 식 · 낡음 · 다시 돌리기 · 모형에 넣기) · 터미널 다섯 · 명령 창 ·
      패키지 기초 통계 분석 아홉(`stats`·`corr`·`acf`·`granger`·`hist`·`xcorr` + 등록만 `fevd`·`convert`·`stochastic`) · `group`·`block add·remove` · `equion.cli.line`

- [x] 2차판 — 혼자 하는 폼과 노트(2026-11-12, D55~D58): 후보 묶음(고를 칸의 조합 → 모두 추정 → 노트로 저장) · 시나리오 폼(충격 표 — 패키지 `equion scenario
      list·show·define·remove`) · 노트 화면(블록마다 상태·▶ 실행·노트 전체 실행·낡은 것만 — 패키지 `equion note add`) · 같은 분석의 두 기록 비교(판단이 바뀐 줄)
- [x] 2차판 — 자료 쪽 셋(2026-11-12, D59~D61): 회차 비교의 요인 나누기(`an split` — 자료 → 가정 → 식, 전망 화면의 단추) · 시점이 열로 가는 표와 여러 줄 머리
      (`time_axis`·`time_row`·`name_col`·`unit_col`, `header_row = [3, 4]` — 불러오기 화면) · 이정표(`equion milestone`)와 묶어 보내기 · 묶음 열기(`equion bundle`)
- [x] 2차판 출시 후보(2026-11-12, D62): 짜지 않은 눈의 적대적 시험 셋 · 사용자 관점 J8 · CI 조합을 이 PC에서 — 고친 것은 CHANGELOG '미공개',
      Desk `0.2.0rc1` 사전 릴리스(`desk-v0.2.0rc1`). 영문 화면·CI는 사용자가 뒤에 정한다, Lectern 수정은 하지 않는다

**2차판 나머지** — Lectern 수정(LC1~LC6 — 다른 저장소), 영문 화면

**배포를 넓힐 때** — 코드 서명(D29), 인터넷 없는 PC용 큰 설치본 · **미래** — scikit-learn 선택 확장 팩(Keras 제외)

## 하지 않기로 한 것

- EViews 프로그램 문법(.prg) 실행기, `.wf1` 파일 직접 읽기, 'EViews' 이름·아이콘·설명서 문장 사용 (D13)
- 다중 사용자 웹 대시보드(FastAPI + Vue) — 0.4.0에서 삭제, 화면은 데스크톱 앱 하나로 (D11)
- PyQt6(GPL) 기반 배포 (D8)
