"""워크파일 API — 라이브러리 1단계 (DECISIONS D2·D3·D4·D14).

    import equion as eqn
    wf = eqn.wfopen("data.xlsx")           # 또는 예제 자료 eqn.datasets.load("toy_q")
"""
from .objects import EquationObject, GraphObject, ModelObject, ScenarioObject, SolveResult, TableObject
from .output import GraphOutput, Output, TableOutput, TextOutput, show, spool, verbose
from .runtime import params, quiet, secret, set_params
from .workfile import Workfile, wfcreate, wfopen

__all__ = [
    "Workfile", "wfcreate", "wfopen",
    "EquationObject", "ModelObject", "ScenarioObject", "SolveResult", "GraphObject", "TableObject",
    "Output", "TableOutput", "TextOutput", "GraphOutput",
    "show", "spool", "verbose", "params", "set_params", "quiet", "secret",
]
