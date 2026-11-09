"""작업 기록·바뀜 기록 (D33) — 계산마다 `work/<종류>/<이름>/`, 정의 파일이 바뀔 때마다 `work/history/`."""
from .history import Change, History
from .store import KINDS, Record, RecordError, WorkStore, detect_who

__all__ = ["WorkStore", "Record", "RecordError", "History", "Change", "detect_who", "KINDS"]
