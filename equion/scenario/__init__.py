"""전망·정책충격 시나리오 모듈 (엔진 v3).

EViews Model의 시나리오 기능에 대응한다:
  Scenario            외생 override · 내생 exclude · 조정항(add factor/초기화) · 충격 · control
  ScenarioResult      결과(별칭 X_0/X_1식 표, 차이·%차이)
  missing_exogenous   전망 지평에서 비어 있는 외생 경로 진단
  missing_history     전망 시작 앞(시차)에 비어 있는 내생변수 실측 진단
  stochastic_simulation  잔차 부트스트랩(+계수 불확실성) 확률적 모의
  control_simulation  목표 경로 추적(도구변수 역산)
  multipliers         충격 승수(동태 반응)
"""
from .scenario import (
    Scenario, ScenarioResult, StochasticResult, MultiplierResult,
    missing_exogenous, missing_history, stochastic_simulation, control_simulation, multipliers,
)

__all__ = [
    "Scenario", "ScenarioResult", "StochasticResult", "MultiplierResult",
    "missing_exogenous", "missing_history", "stochastic_simulation", "control_simulation", "multipliers",
]
