"""통계 — 외부 회귀 패키지 없이 numpy·scipy로 (DECISIONS D17).

    regression   OLS(유사역행렬)·WLS·TSLS·GMM·LIML·NLS·고정 계수의 공통 결과 객체 Results
    robust       강건 공분산: HC0~HC3·White·HAC(Newey-West)
    diagnostics  계열상관 LM·Ljung-Box·White·Breusch-Pagan·ARCH·Jarque-Bera·RESET·Wald·Chow·CUSUM·재귀 추정·
                 누락/불필요 변수(nested)
    unitroot     ADF·KPSS·Engle-Granger·Johansen (수치표: _tables, 출처는 THIRD-PARTY-NOTICES.md)
    forecast     예측 평가(RMSE·MAE·MAPE·Theil U1/U2·MSE 분해)·Diebold-Mariano 검정
    system       연립 추정(배열): 시스템 OLS·SUR·2SLS·3SLS·FIML·선형 제약 — 워크파일에서는 wf.system(…)
    describe     기초 분석: 기술 통계·상관·자기상관(ACF·PACF·Q)·교차상관·히스토그램·쌍별 Granger 인과(D50)

모든 함수는 numpy 배열·pandas 객체를 받고, 검정은 TestResult(.statistic·.pvalue·.show())를 돌려준다.
워크파일에서는 방정식 객체의 메서드(eq.serial_lm() …)와 wf.adf()·wf.kpss()·wf.coint()·wf.johansen()로 쓴다.
"""
from .describe import (Correlation, acf, ccf, correlation, correlogram, describe, granger_causality, granger_table,
                       histogram, pacf)
from .diagnostics import (arch_lm, breusch_godfrey, breusch_pagan, chow, cusum, jarque_bera, ljung_box, nested,
                          parse_restrictions, recursive, reset, wald, wald_linear, white)
from .forecast import diebold_mariano, evaluate as forecast_evaluate, evaluate_many as forecast_table
from .regression import GMM_WEIGHTS, Results, constant_info, fixed, gmm, liml, nls, ols, pinv_svd, tsls, wls
from .result import TestResult
from .robust import COV_TYPES, newey_west_lags, normalize_cov_type
from .unitroot import adf, engle_granger, johansen, kpss, mackinnon_crit, mackinnon_p

__all__ = [
    "Results", "ols", "wls", "tsls", "gmm", "liml", "nls", "fixed", "pinv_svd", "constant_info", "GMM_WEIGHTS",
    "COV_TYPES", "newey_west_lags", "normalize_cov_type", "TestResult",
    "breusch_godfrey", "ljung_box", "white", "breusch_pagan", "arch_lm", "jarque_bera", "reset",
    "wald", "wald_linear", "parse_restrictions", "chow", "recursive", "cusum", "nested",
    "adf", "kpss", "engle_granger", "johansen", "mackinnon_p", "mackinnon_crit",
    "forecast_evaluate", "forecast_table", "diebold_mariano",
    "describe", "correlation", "acf", "pacf", "correlogram", "ccf", "histogram", "granger_causality", "granger_table",
]
