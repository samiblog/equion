"""Equion — 방정식·연립방정식의 추정·풀이·시뮬레이션.

개별 회귀식(OLS·2SLS·NLS·고정 계수 등)부터 비선형 연립방정식 모델(블록 분해 + Newton)의 풀이·전망·
시나리오까지. `import equion as eqn`(라이브러리)과 `equion run 스크립트.py`(명령줄)로 쓴다.

공개 API(안정 — 바꿀 때는 경고 후 다음 큰 버전에서):
    eqn.wfopen · eqn.wfcreate · eqn.Workfile   워크파일 API(방정식·모델·시나리오·그래프·표 객체)
    eqn.show · eqn.params · eqn.verbose · eqn.spool   출력·매개변수
    eqn.stats    회귀 결과·강건 공분산·진단 검정·단위근/공적분(numpy·pandas를 받는 함수)
    eqn.log      로그 설정
    eqn.datasets 예제 자료(toy_q·toy_a·toy_m·klein_like — 문서·튜토리얼이 쓰는 가상 자료)
    명령줄 `equion run|check|info|new|convert`
고급(엔진 수준 — 드라이버·확장용, 바뀔 수 있음):
    eqn.Data · eqn.Equation · eqn.Model · eqn.Scenario · eqn.WorkTable · eqn.Workspace
내부(직접 쓰지 말 것): formula · system · worktable 하위 모듈의 밑줄 없는 이름 외 모든 것, `_legacy/`(1.0에서 삭제)

빠른 시작:
    import equion as eqn
    wf = eqn.datasets.load("toy_q")                      # 예제 자료(분기 거시 모형)
    cn = wf.equation("eq_cn").ls("CN c Y CN(-1)")
    eqn.show(cn)
"""
from .version import __version__, print_version
from .data.dataset import Data
from .estimation.equation import Equation
from .system.model import Model
from .scenario import Scenario
from .worktable import WorkTable, Workspace, current
from .workfile import Workfile, wfcreate, wfopen, show, params, secret, verbose, spool
from . import datasets, log, stats

__all__ = [
    # 공개 API
    "__version__", "print_version",
    "Workfile", "wfcreate", "wfopen", "show", "params", "secret", "verbose", "spool", "stats", "log", "datasets",
    # 고급(엔진 수준)
    "Data", "Equation", "Model", "Scenario", "WorkTable", "Workspace", "current",
]
