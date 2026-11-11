"""작업 개체(Windows Job Object) — 앱이 끝나면(강제로 끝내도) 앱이 띄운 작업 프로세스가 함께 끝나게 한다.

작업 프로세스는 표준 입력이 닫히면 스스로 끝나지만, 계산 중이면 그 계산이 끝난 뒤다(큰 모형의 과거 재현은 몇 초~몇 분).
'닫으면 함께 끝내기'(KILL_ON_JOB_CLOSE)를 건 작업 개체에 넣어 두면, 앱이 쥔 핸들이 닫히는 순간 Windows 가 바로 끝낸다.
터미널의 셸은 따로 자기 작업 개체에서 돈다(conpty.py). Windows 가 아니면 아무것도 하지 않는다.
"""
from __future__ import annotations

import sys
from typing import Any

_job: Any = None
_tried = False


def _create() -> Any:
    import ctypes
    from ctypes import wintypes as w

    class IO_COUNTERS(ctypes.Structure):
        _fields_ = [(name, ctypes.c_ulonglong) for name in ("ReadOps", "WriteOps", "OtherOps", "ReadBytes", "WriteBytes", "OtherBytes")]

    class BASIC(ctypes.Structure):
        _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64), ("LimitFlags", w.DWORD),
                    ("MinimumWorkingSetSize", ctypes.c_size_t), ("MaximumWorkingSetSize", ctypes.c_size_t),
                    ("ActiveProcessLimit", w.DWORD), ("Affinity", ctypes.c_size_t), ("PriorityClass", w.DWORD), ("SchedulingClass", w.DWORD)]

    class EXTENDED(ctypes.Structure):
        _fields_ = [("BasicLimitInformation", BASIC), ("IoInfo", IO_COUNTERS), ("ProcessMemoryLimit", ctypes.c_size_t),
                    ("JobMemoryLimit", ctypes.c_size_t), ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]

    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.CreateJobObjectW.argtypes = [ctypes.c_void_p, w.LPCWSTR]
    k.CreateJobObjectW.restype = w.HANDLE
    k.SetInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD]
    k.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
    job = k.CreateJobObjectW(None, None)
    if not job:
        return None
    limits = EXTENDED()
    limits.BasicLimitInformation.LimitFlags = 0x2000          # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if not k.SetInformationJobObject(job, 9, ctypes.byref(limits), ctypes.sizeof(limits)):   # 9 = ExtendedLimitInformation
        return None
    return k, job


def adopt(process: Any) -> bool:
    """`subprocess.Popen` 하나를 앱의 작업 개체에 넣는다. 넣었으면 True(Windows 가 아니거나 실패하면 False — 그대로 돈다)."""
    global _job, _tried
    if sys.platform != "win32":
        return False
    if not _tried:
        _tried = True
        try:
            _job = _create()
        except (OSError, AttributeError):
            _job = None
    if not _job:
        return False
    k, job = _job
    try:
        return bool(k.AssignProcessToJobObject(job, int(process._handle)))
    except (OSError, AttributeError, ValueError):
        return False
