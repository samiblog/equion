"""명령줄 — 라이브러리 위의 2단계(DECISIONS D1·D5·D6).

    equion run scripts/main.py --set oil=1.5 --smpl 2023Q1:2026Q4
    python -m equion check EQUATIONS/model.txt --data DATA/data.csv

실행기(runner)·보고서(report)는 P3 데스크톱 앱의 프로그램 실행에서도 그대로 쓴다.
"""
from .commands import main
from .runner import RunOptions, RunResult, run_script

__all__ = ["main", "run_script", "RunOptions", "RunResult"]
