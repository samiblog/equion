# 바뀐 점

Equion의 판별 변경 기록. 새것이 위에 있습니다. 설계 결정은 [`docs/DECISIONS.md`](docs/DECISIONS.md)(D-번호), 검증은
[`docs/explain/validation.md`](docs/explain/validation.md), 계획은 [`docs/ROADMAP.md`](docs/ROADMAP.md).

## 미공개

### 추가
- **문서 체계(D27)**: 시작하기 · 튜토리얼 8편 · 레시피 · 해설 · 참조 · 사례 연구(Klein형) · EViews 사용자 안내 ·
  영문 시작 문서. 시작점은 [`docs/README.md`](docs/README.md)입니다. 문서의 예제는 실제로 돌고, 출력도 실행 결과입니다.
  `python docs/build_docs.py --check`가 CI에서 예제 실행·출력·링크·API 설명과 예제·doctest를 확인합니다.
- **예제 자료 `eqn.datasets`**: `toy_q`(분기 거시) · `toy_a`(연간) · `toy_m`(월간) · `klein_like`(Klein 모형 I 구조). 참 모형을 아는
  가상 자료이며 패키지에 들어 있습니다. 실제 Klein 자료는 이용 조건이 분명하지 않아 넣지 않았고, 직접 구한 파일은 `eqn.datasets.klein(path)`로 엽니다.
- 공개 함수·메서드 전체에 매개변수·돌려주는 것·오류·예제(doctest)를 담은 docstring을 달았습니다. API 참조 `docs/reference/api.md`가 여기서 만들어집니다.
- 예제 스크립트·노트북 `examples/`(문서에서 자동으로 만든다).
- `wf.convert(…, start=, end=)`: 변환할 구간을 고릅니다.
- `TableObject.save`: `.csv`·`.xlsx`·`.html`·`.txt`를 받고, 없는 폴더는 만듭니다.
- 안정성 판정이 `안정`·`단위근`·`불안정`으로 나뉩니다(`StabilityResult.verdict`·`unit_roots`·`explosive`). `stability_path`에 `판정` 열을 더했습니다.

### 바뀜
- `docs/EQUATION_GUIDE.md` → `docs/explain/equations.md`, `docs/API.md` → `docs/reference/api.md`(옛 위치에는 안내만 남김).
- 모델에 같은 항등식을 다시 `append`해도 한 번만 들어갑니다(공백·대소문자 무시).
- `forecast(start, end)`는 `end`가 워크파일 끝보다 뒤일 때만 기간을 늘립니다.

### 고침
- 선행변수(`X(1)`)가 있는 모델을 `mce=False`로 풀면 경고합니다(선행값으로 실측을 쓴다는 뜻).
- FIML에서 도구변수에 없는 같은 기 설명변수(항등식이 정하는 내생변수)를 외생으로 다루게 될 때 경고합니다.
- 오류 메시지를 더 분명하게 바꿨습니다: 목표변수 중복(어느 식인지와 `drop` 안내), 목표 추적(`control`) 구조 오류의 힌트,
  없는 시점(워크파일 기간과 `extend` 안내), 시리즈와 겹치는 객체 이름(대소문자 무시와 접두사 안내), 주기 변환 지표가 구간을 덮지 못할 때(두 구간 표시).
- `equion --help`에 종료 코드 130(중단)을 표시합니다.
- 계열상관 LM(Breusch-Godfrey) 검정의 보조 회귀에 상수열이 겹쳐 들어가 있었습니다(식에 상수항이 이미 있어도 하나 더). 완전 공선인
  열의 절단이 BLAS에 따라 달라져 p값이 플랫폼마다 달랐습니다(예: 0.405 · 0.468). 이제 상수항이 없을 때만 더합니다 — 결과는
  절단이 맞게 된 경우의 값과 같습니다.
- 안정성: 켤레 근 쌍은 허수부가 양인 쪽을 먼저 보입니다(순서가 LAPACK에 따라 달랐다). '가장 큰 근과 함께 움직이는 변수'에서
  0%로 반올림되는 변수는 보이지 않습니다.
- pandas 4 대비: 엔진 `Model`에 `'2010Q1'` 같은 시점 표기를 주거나, 기간 라벨 인덱스의 시나리오 경로를 저장했다가 다시 열 때
  pandas가 기간 문자열을 직접 해석하지 않게 했습니다(`data/periods.py`의 `locate`·`parse_dates`를 거친다 — 새 pandas에서는 경고, pandas 4에서는 오류였을 것).

## 0.7.0 — 2026-10-30

### 추가
- 추정: WLS · GMM(Hansen J) · LIML · PDL · 누락/불필요 변수 검정(D20), AR(p) 오차항 · 오차수정모형 · 예측 평가(Theil · Diebold-Mariano)(D21).
- 시스템 추정: OLS · SUR · 2SLS · 3SLS · FIML · 식 사이 제약, 모델로 `merge`(D22). VAR · VECM(D23).
- 모델 분석: 동태 안정성(선형화 동반행렬 고윳값) · 시나리오 기여도 분해(Shapley)(D24). 큰 블록의 희소 자코비안 · stacked-time MCE(D25).
- 자료: 시리즈 메타데이터 · 페이지 · 주기 변환 · Denton/Chow-Lin · STL/고전 계절조정(D26).
- 보안: 비밀 값 가리기(`eqn.secret`) · `--redact` · 레거시 pickle 기본 차단(`equion convert`) · 방정식 입력 한도와 퍼징(D18).
- 영문 README, API 목록 자동 생성, 저장소 분리 계획(계획만).
- 상황별 시나리오 시험 641개와 회귀 시험 `tests/test_scenarios.py`.

### 바뀜
- 라이브러리 출력을 `logging`으로(`eqn.verbose`). 공개 버전 번호 하나, 공개·고급·내부 API 구분, `_legacy` 사용 경고(D18).
- 워크파일·번들의 표를 npz로 저장합니다. pyarrow·plotly는 선택 기능입니다(`equion[parquet]` · `equion[plot]`)(D19).
- 의존성을 범위로 두고 `uv.lock`으로 고정했습니다. CI는 3 OS × Python 3.12~3.14와 하한·최신·선택 의존성 없이·기준선·감사를 봅니다(D19).

### 고침
- 시나리오 시험에서 찾은 결함(경계·오용·연/월·명령줄)을 고쳤습니다. 고친 것마다 `tests/test_scenarios.py`에 시험이 있습니다.
- 이미 넣은 제약을 Wald로 검정하면 분명한 오류를 냅니다.

## 0.6.0 — 2026-10-29

- statsmodels를 없애고 회귀·검정을 자체 구현했습니다(OLS 계수·통계가 이전과 같다)(D17).
- NLS 해석적 자코비안(IR 기호 미분). 기간·주기 연산을 `data/periods.py` 한 곳으로 모았습니다(pandas 버전 변화 흡수).
- 강건 공분산(HC0~3 · HAC) · 진단 검정 · 단위근/공적분.

## 0.5.0 — 2026-10-29

- 이름을 `macromodel`에서 **Equion**으로 바꿨습니다(패키지 · import · 명령 `equion`, 별칭 `eqn`, 워크파일 `.eqw`)(D16).
  옛 `.mmw` 워크파일 · `macromodel-run` 보고서 · 레거시 pickle · `MACROMODEL_PARAMS`는 계속 읽습니다.

## 0.4.0 — 2026-10-29

- 명령줄 `run` · `check` · `info` · `new`, 보고서 폴더(`report.html` · `manifest.json`), 종료 코드 약속(D5 · D15).
- 설치형 패키지(D6). 웹 대시보드를 삭제했습니다(D11).

## 0.3.0 — 2026-10-29

- 워크파일 API(라이브러리 1단계): 워크파일 · 표본 · genr · 방정식 · 모델 · 시나리오 · 그래프 · 표 객체(D2~D14).

## 0.2.0 — 2026-10-29

- 엔진 v3: 단일 방정식 파서 · IR · 블록 분해 + Newton · 실패 정책 · 시나리오 · 전망 · 확률적 모의 · 목표 추적 · MCE · TSLS/NLS.

## 0.1 — 2026-05-31

- 첫 스냅샷(태그 `v0.1`).

## 이전 이력(macromodel 시절)

- v2.1 (2026-05-31): 대소문자 무시 매칭, `@seas`, `@d`/`@step`/`@trend`, 시차 범위, `@def`, `@smpl`, `dlog`/`d`/`.gr(N)`, `hs(add_factors=…)`.
- v2.0.1 (2026-05-29): 풀이기의 복합·내생 시계열 항 변환 오류 수정, 방정식 로더 분류 수정.
- v2.0.0 (2026-04-18): AST 기반으로 다시 짬.
- 원본: `equation_model_core.py` v1.4.1 (2025-10-11).
