# 사용 가이드(옛 통합 안내) → 새 문서 안내

예전에는 이 파일 하나에 모든 사용법을 모았습니다. 이제 내용은 [문서 첫 페이지](README.md)에서 시작하는 튜토리얼·레시피·해설·참조로
나뉘었습니다. 새 문서의 예제는 모두 실제로 돌고, 출력도 실행 결과입니다(`python docs/build_docs.py --check`). 옛 절이 어디로 갔는지는
아래 표에 있습니다.

| 옛 절 | 새 위치 |
|---|---|
| §1 개요 · 세 단계 · 엔진 구조 | [저장소 소개](../README.md) · [문서 첫 페이지](README.md) · [연립 풀이](explain/solving.md) · [엔진 수준 API — 층 구조](explain/engine.md#층-구조) |
| §2.1 워크파일 | [튜토리얼 1 자료 다루기](tutorial/01-data.md) |
| §2.2 방정식 객체 | [튜토리얼 2 방정식 추정](tutorial/02-estimation.md) · [추정법](explain/estimation.md) |
| §2.3 모델 객체 | [튜토리얼 4 연립 모델](tutorial/04-model.md) · [튜토리얼 5 시나리오](tutorial/05-scenario.md) |
| §2.4 그래프·표·출력 | [출력·보고서 레시피](howto/output.md) |
| §2.5 Python 완전 연동 | [EViews 사용자 안내 — 한 흐름을 Python으로](eviews.md#한-흐름을-python으로) · [추정 레시피](howto/estimation.md) |
| §2.6 진단 검정 · 강건 표준오차 · 단위근/공적분 | [튜토리얼 3 진단 검정](tutorial/03-diagnostics.md) · [출력 표 읽는 법](reference/outputs.md) |
| §2.7 오차수정모형 · 예측 평가 | [튜토리얼 3](tutorial/03-diagnostics.md) · [튜토리얼 6 전망](tutorial/06-forecast.md) |
| §2.8 시스템 추정 · §2.9 VAR · VECM | [튜토리얼 7 시스템·VAR·VECM](tutorial/07-systems.md) · [Klein형 사례](cases/klein.md) |
| §2.10 안정성 · 기여도 분해 · 큰 모델 | [동태: 선행변수와 안정성](explain/dynamics.md) · [시나리오와 전망](explain/scenarios.md) |
| §2.11 메타데이터 · 페이지 · 주기 변환 · 계절조정 | [튜토리얼 1](tutorial/01-data.md) · [자료 레시피](howto/data.md) |
| §3 명령줄 | [튜토리얼 8 명령줄](tutorial/08-cli.md) · [명령줄 참조](reference/cli.md) · [명령줄 레시피](howto/cli.md) |
| §4 설치 · 폴더 구조 | [설치](start/install.md) · [저장소 소개 — 폴더](../README.md) |
| §5 빠른 시작 | [30분 첫 모델](start/first-model.md) · [Klein형 사례](cases/klein.md) |
| §6 방정식 문법 요약 | [방정식 함수·지시자](reference/functions.md) · [방정식 문법](explain/equations.md) |
| §7~§12 Data · Equation · Model · 시나리오(엔진) · WorkTable · formula | [엔진 수준 API](explain/engine.md) |
| §13 FAQ · 트러블슈팅 | [문제 해결](howto/troubleshooting.md) · [오류 메시지](reference/errors.md) |
| 버전 정보 | [바뀐 점](../CHANGELOG.md) |
