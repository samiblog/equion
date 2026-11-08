# Equion 문서

Equion은 방정식 하나의 추정부터 비선형 연립방정식 모델의 풀이·전망·시나리오까지를 Python으로 하는 패키지입니다.
이 문서는 네 부분으로 나뉩니다 — **따라 하며 배우는** 튜토리얼, **할 일을 찾아 쓰는** 레시피, **원리를 설명하는** 해설,
**빠짐없이 찾아보는** 참조. 모든 예제는 패키지에 든 예제 자료로 바로 돌고, 문서에 보이는 출력은 실제 실행 결과입니다
(문서 검사 `python docs/build_docs.py --check`가 CI에서 매번 다시 돌려 확인합니다).

## 처음이라면

1. [설치](start/install.md) — uv 또는 pip, 확인하는 법
2. [30분 첫 모델](start/first-model.md) — 자료 → 추정 → 모델 → 과거 재현 → 시나리오 → 전망 → 저장을 한 번에
3. [치트시트](start/cheatsheet.md) — 자주 쓰는 명령 한 장

## 튜토리얼 — 차례로 배우기

| | 주제 | 배우는 것 |
|---|---|---|
| 1 | [자료 다루기](tutorial/01-data.md) | 워크파일·시리즈·표본·genr·메타데이터·기간 늘리기·주기 변환·계절조정·파일 입출력 |
| 2 | [방정식 추정](tutorial/02-estimation.md) | 방정식 문법, OLS 결과표 읽기, 결과 꺼내기, 강건 표준오차, 2SLS·NLS·AR·PDL·고정 계수 |
| 3 | [진단 검정](tutorial/03-diagnostics.md) | 잔차 자기상관·이분산·정규성·구조 변화·계수 제약, 단위근·공적분, 오차수정모형 |
| 4 | [연립 모델](tutorial/04-model.md) | merge·항등식·블록 구조, 동적·정적 풀이, 기간 상태, 적합도, 결측·실패 정책 |
| 5 | [시나리오](tutorial/05-scenario.md) | 외생 경로·내생 고정·조정항·충격·목표 추적, 기여도 분해, 승수, 확률적 모의 |
| 6 | [전망](tutorial/06-forecast.md) | 기간 늘리기, 외생 가정, 결측 진단, 예측 평가 |
| 7 | [시스템·VAR·VECM](tutorial/07-systems.md) | SUR·3SLS·FIML·식 사이 제약, VAR(충격반응·분산분해·인과), VECM, 모델에 넣기, 안정성 |
| 8 | [명령줄](tutorial/08-cli.md) | 스크립트 매개변수, `equion run`, 보고서 폴더, `check`·`info`·`new`, 자동화 |

튜토리얼마다 같은 내용의 스크립트가 [`examples/tutorial/`](../examples/tutorial)에, 노트북이
[`examples/notebooks/`](../examples/notebooks)에 있습니다(문서에서 자동으로 만든다).

## 레시피 — 할 일별 처방

[레시피 목록](howto/README.md): 자료 · 추정 · 진단 · 모델 · 시나리오 · 전망 · 시스템·VAR · 출력·보고서 · 명령줄 · 문제 해결.

## 해설 — 원리

- [방정식 문법](explain/equations.md) — 항 분리·시차·함수·지시자·추정법 지시자 전체
- [추정법](explain/estimation.md) — OLS·WLS·2SLS·GMM·LIML·NLS·AR·PDL·강건 공분산의 식과 언제 쓰나
- [연립 풀이](explain/solving.md) — 블록 분해·Newton·폴백, 동적/정적/fit, 결측·실패 정책과 기간 상태
- [시나리오와 전망](explain/scenarios.md) — 별칭·override·exclude·조정항·충격·목표 추적·기여도 분해의 뜻
- [동태: 선행변수와 안정성](explain/dynamics.md) — 모형 일관 기대(Fair-Taylor·stacked), 동반행렬 고윳값
- [검증 보고서](explain/validation.md) — 외부 구현·독립 계산과 견준 결과와 허용오차
- [엔진 수준 API](explain/engine.md) — `Data`·`Equation`·`Model`·`Scenario`·`WorkTable`과 파서·IR(드라이버가 쓰는 아래 층)

## 참조 — 찾아보기

- [API 참조](reference/api.md) — 모든 공개 함수·메서드(서명·설명·예제, 코드에서 자동 생성)
- [명령줄](reference/cli.md) · [방정식 함수·지시자 목록](reference/functions.md) · [출력 표 읽는 법](reference/outputs.md)
- [오류 메시지](reference/errors.md) — 메시지 → 원인 → 고치는 법 · [파일 형식](reference/formats.md) · [예제 자료](reference/datasets.md)

## 사례 연구

- [Klein형 모형](cases/klein.md) — 교과서 모형 I의 구조로 2SLS·3SLS·FIML·시뮬레이션

## 그 밖에

- [EViews 사용자를 위한 안내](eviews.md) — 개념·명령 대응
- [바뀐 점](../CHANGELOG.md) · [English](en/README.md)
- 프로젝트 문서: [설계 결정](DECISIONS.md) · [로드맵](ROADMAP.md) · [Equion Desk 개발 계획](DESK_DEVPLAN.md) · 예전 통합 안내 [USER_GUIDE](USER_GUIDE.md)(새 위치 안내)

## 문서를 쓰는 사람에게

- 사용자 문서(위 네 부분·사례·README)의 `python` 블록은 위에서부터 차례로 실행된다. 바로 뒤에 `<!-- out -->`을 두면
  다음 `text` 블록에 실행 출력이 들어간다(`python docs/build_docs.py`가 채운다 — 손으로 고치지 않는다).
  `<!-- skip -->`은 실행하지 않는 조각, `<!-- error -->`는 오류로 끝나야 하는 예다.
- 튜토리얼·레시피·시작하기는 `examples/`의 스크립트(·노트북)로 자동 내보낸다 — 예제를 고치려면 문서를 고친다.
- 공개 함수의 docstring은 [API 참조의 틀](reference/README.md#docstring-쓰는-법)대로 쓰고 예제(`>>>`)를 단다 — 검사가 확인한다.
- 새 기능의 완료 기준: 코드 + 시험 + docstring(예제) + 튜토리얼이나 해설의 절 + 필요한 레시피.
