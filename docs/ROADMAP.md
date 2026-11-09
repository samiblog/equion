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

## 0.8 — 프로젝트·작업 명령·기록·스크립트 (진행, 2026-11-09 — D31~D38)

Equion Desk 개발 계획(`DESK_DEVPLAN.md`)의 단계 E. 끝나면 Desk 없이도 Lectern 터미널과 Claude로 "자료를 넣고 `equion run monthly.eqs`"가 된다.
수치 코어(파서·IR·풀이·통계)는 고치지 않는다 — 워크파일 API 위의 새 층.

- [x] E1 프로젝트·조립(2026-11-09): `equion.toml`·블록·이름·조립 검사·블록 HS·바꿔 끼우기·항등식 검사·`eqn.project()`, 예제 프로젝트
      `equion new --template desk`(가상 분기 모형) — `assemble`·`ident` (D32). 채택표는 기록과 함께 E3로 — 지금은 모형을 만들 때 지금 자료로 추정하고 알린다
- [x] E2 자료 정의·회차(2026-11-09): 원자료·출처 해시, `series.toml`(불러오기 틀)·`derived.txt`, 회차·값의 종류, 틀 검사, 상대 기간 —
      `data add·build·use·diff·impact` (D34). 시점이 열로 가는 표(`time_axis = "columns"`)는 다음 판
- [x] E3 작업 명령·기록(2026-11-09): `work/` 기록·조립 명세·알아서 한 것·`summary.md`(md 렌더러), 채택표 `adopted.toml`, 바뀜 기록·제안 —
      `est`·`adopt`·`compare`·`hs`·`sim`·`export`·`work`·`propose`·`history` (D33·D35)
- [x] E4 분석·노트·보고서(2026-11-09): 등록부·`an`·`note`·`report`, 묶음 (D37). 블록 후보(VAR를 블록으로)·기초 통계는 2차판
- [x] E5 스크립트·재연(2026-11-09): `.eqs` 해석기·`run x.eqs`·`check x.eqs`·`--replay`·`script new·export`, `DATA/raw/inbox/` (D36). `expect --stop` = 종료 코드 2
- [x] E6 안내·문서(2026-11-09): Claude용 모형 작업 안내 `equion guide`(`equion/help/guide.md` — 표는 코드에서)·스킬 초안 `guide skill`, 튜토리얼 9편, 파일 지도. 안내만 읽은 새 Claude가 예제의 월간 스크립트를 돌림
- [ ] `tomlkit` 의존성(D38), 오류 메시지에서 문서 절 안내

## 다음 (0.9 후보)

- [ ] 외부 데이터 연결(ECOS·KOSIS 먼저 — 받은 파일을 원자료로, 출처 정의 파일 `equion data fetch`) — 0.8에서 옮김(D31)
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
- [ ] D1 뼈대: Lectern 0.69.1에서 복사(창·서버·단일 인스턴스·탭·사이드바·터미널·설정·감시), 작업 줄·작업 기록 띠·바뀜 알림, md·카드 보기, 초안
- [ ] D2 식·자료: W1 식 작업대, W4 자료 작업대(불러오기 화면·회차), 분석 메뉴·분석 탭
- [ ] D3 조립·HS·흐름: W0 조립, W2 모형(HS·전후 비교·원인 따라가기), 흐름 화면(스크립트), 회차 바꾼 뒤 할 일
- [ ] D4 전망·보고서: W3(가정·보정항·기준선·시나리오·회차 비교), 보기, 보고서로 보내기, 엑셀로
- [ ] D5 Claude·마감·설치본: 맡기기·제안 받기, 제안 카드, 바뀜 기록·되돌리기, `equion desk show`, 설치본·Windows CI·예제 프로젝트·도움말

**2차판** — 노트 ▶ 실행 화면, 후보 묶음·시나리오 폼, 기초 분석(기술 통계·히스토그램·상관·ACF·PACF), 두 기록 비교, 회차 비교 요인 나누기 화면,
시점이 열인 표 불러오기, 묶어 보내기·이정표, Lectern 수정(LC1~LC6), 영문 화면

**배포를 넓힐 때** — 코드 서명(D29), 인터넷 없는 PC용 큰 설치본 · **미래** — scikit-learn 선택 확장 팩(Keras 제외)

## 하지 않기로 한 것

- EViews 프로그램 문법(.prg) 실행기, `.wf1` 파일 직접 읽기, 'EViews' 이름·아이콘·설명서 문장 사용 (D13)
- 다중 사용자 웹 대시보드(FastAPI + Vue) — 0.4.0에서 삭제, 화면은 데스크톱 앱 하나로 (D11)
- PyQt6(GPL) 기반 배포 (D8)
