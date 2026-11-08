# 검증 보고서

Equion의 모든 통계 계산은 패키지 안에서 직접 합니다(외부 회귀 패키지 없음 — DECISIONS D17). 그래서 "계산이 맞는가"를 따로
보여야 합니다. 이 문서는 무엇과 견줬고 얼마나 맞는지, 그리고 그 비교가 언제 다시 돌려지는지를 정리합니다.

## 방법

1. **외부 구현과 대조**: statsmodels·linearmodels가 있는 별도 환경에서 같은 자료로 계산한 값을 `tests/fixtures/*.json`에
   고정하고(만드는 스크립트 `tests/fixtures/make_*_reference.py`), 시험이 매번 그 값과 견줍니다 — 시험 자체는 외부 패키지 없이 돈다.
2. **독립 계산과 대조**: 외부 구현이 부정확한 곳은 다른 길로 계산한 값과 견줍니다 — 예: GMM은 50자리 다정밀 산술(mpmath),
   재귀 잔차는 시점마다 직접 최소제곱, stacked MCE는 삼중대각 직접 해.
3. **알려진 동치**: 이론상 같아야 하는 결과끼리 — 선형 식의 NLS = OLS, 도구 = 회귀변수인 2SLS = OLS, 반복 SUR = 정규 최우 FIML,
   정확 식별 FIML = 2SLS, 표본 잔차를 더한 정적 풀이 = 실측.
4. **예제 모델**: 참 모형을 아는 예제 자료(`eqn.datasets`)로 추정·풀이·시나리오·안정성을 끝까지 돌려, 블록 구조·풀이 상태·
   동치 관계를 시험에 고정합니다. 문서의 모든 예제 출력도 매번 다시 돌려 견줍니다.

## 결과

| 영역 | 비교 대상 | 차이 |
|---|---|---|
| OLS(계수·표준오차·통계 전부) | 0.5.0까지 쓰던 외부 패키지 경로 | 135식 전 항목 0, 과거 재현 결과 바이트 동일 |
| NLS(해석적 자코비안) | 같은 식의 OLS | 1.9e-14 |
| 2SLS | 도구 = 회귀변수일 때의 OLS | 9e-15 ~ 1.6e-11 |
| WLS·2SLS·GMM·LIML | linearmodels | 1e-9 이내 |
| GMM | 50자리 산술 | 2e-10(linearmodels는 정규방정식 경로라 2.4e-7) |
| 강건 공분산 HC0~3·HAC | statsmodels | 1e-11 이하 |
| 진단 검정(LM·White·BP·ARCH·JB·RESET·Chow·Wald·누락/불필요) | statsmodels | 대부분 0 ~ 1e-11 |
| 재귀 잔차·CUSUM | 시점마다 직접 최소제곱 | statsmodels 갱신 공식은 이 자료에서 상대 3e-4 어긋나 독립 계산과 비교 |
| ADF·KPSS·Engle-Granger·Johansen | statsmodels(MacKinnon·MHM 수치표) | 1e-9 이내 |
| SUR(반복)·3SLS | linearmodels | 1e-9 |
| FIML | 반복 SUR(외생)·정확 식별 2SLS | 동치 성립 |
| VAR(충격반응·분산분해·Granger) · VECM(결정항 7종) | statsmodels | 1e-9 · 1e-7 |
| Denton | statsmodels dentonm | 1e-8 |
| Chow-Lin | 독립 GLS·격자 최우 | 1e-8 |
| STL(강건 포함) · 고전 분해 | statsmodels | 1e-9 |
| stacked MCE | 삼중대각 직접 해 | 1e-10 |
| 연립 풀이 | 표본 잔차를 더한 정적 풀이 = 실측 | 상대 1e-6 이내(항등식이 자료에서 성립하지 않으면 그 변수는 실측으로) |

시험(`tests/test_stats.py` · `tests/test_engine.py`)이 매번 다시 확인합니다.

## 다시 돌려지는 곳

| 시험 | 내용 | 언제 |
|---|---|---|
| `tests/test_stats.py` | 통계 166항목 — 위 표의 기준값 비교 | 매 푸시, Linux·Windows·macOS × Python 3.12~3.14, 하한·최신 판 |
| `tests/test_engine.py` | 엔진 104항목 — 번역 일관성(추정 잔차 = 컴파일 잔차), 동치, 예제 모델 | 같음 |
| `tests/test_docs.py` | 문서의 모든 예제와 docstring 예제 실행·출력 비교 | 매 푸시 |

## 마지막 자리 차이

선형대수 라이브러리(OpenBLAS·MKL)와 CPU 명령어(벡터 폭)에 따라 덧셈 순서가 달라져, 같은 계산이 1e-12 수준에서 다를 수 있습니다.
엔진 v2에서는 실패한 해를 다음 기간으로 흘려보내던 결함이 이 작은 차이를 크게 키웠지만(고용 과거 재현 1.8% ↔ 45%), v3에서 그 결함을
없앤 뒤로는 차이가 마지막 자리에 머뭅니다. 결과 비교는 해시가 아니라 허용오차로 합니다.

관련: [추정법](estimation.md) · [연립 풀이](solving.md)
