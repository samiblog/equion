"""앱이 도는 Python 런타임과, 그 런타임을 PC의 다른 Python과 떨어뜨리는 환경(DECISIONS D39).

설치본에서는 설치 폴더 안의 런타임 하나로 앱·작업 프로세스·터미널이 모두 돈다. 개발 중에는 지금 Python(.venv)이 그 자리다.
터미널과 작업 프로세스에 넘기는 환경은 여기서 만든다 — PATH 맨 앞에 런타임을 두고, PC의 Python 설정이 섞이지 않게 지운다.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# PC의 Python 설정 — 런타임에 섞이면 다른 판의 패키지를 읽는다. 셸·작업 프로세스로 넘기지 않는다
FOREIGN = ("PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP", "PYTHONUSERBASE", "PYTHONEXECUTABLE", "PYTHONINSPECT",
           "VIRTUAL_ENV", "CONDA_PREFIX", "CONDA_DEFAULT_ENV", "CONDA_PYTHON_EXE", "__PYVENV_LAUNCHER__",
           # Desk를 Claude Code 안에서 띄웠을 때 물려받는 '그 세션'의 값 — 터미널의 claude 가 자식 세션으로 묶이거나, 사람이 친 명령이
           # '누가 claude'로 남지 않게 지운다. 사용자의 설정(ANTHROPIC_* · CLAUDE_CONFIG_DIR · CLAUDE_CODE_USE_* 등)은 그대로 둔다
           "CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "CLAUDE_CODE_SESSION_ID", "CLAUDE_CODE_CHILD_SESSION",
           "CLAUDE_CODE_SESSION_ATTENDED", "CLAUDE_CODE_MESSAGING_SOCKET", "CLAUDE_CODE_MESSAGING_TOKEN",
           "CLAUDE_CODE_BRIDGE_SESSION_ID", "CLAUDE_CODE_EXECPATH", "CLAUDE_PID", "EQUION_WHO")


def python_exe() -> str:
    """앱이 도는 Python 실행 파일(창 없는 `pythonw.exe`로 떴으면 같은 폴더의 `python.exe`)."""
    exe = Path(sys.executable)
    if exe.stem.lower() == "pythonw":
        console = exe.with_name("python" + exe.suffix)
        if console.is_file():
            return str(console)
    return str(exe)


def bin_dirs() -> list[str]:
    """`python`·`equion`이 있는 폴더들 — 터미널의 PATH 맨 앞에 둔다.

    Windows의 런타임은 `python.exe`가 최상위에, 명령(`equion.exe`)이 `Scripts/`에 있다. 가상환경은 둘 다 `Scripts/`.
    """
    base = Path(python_exe()).parent
    dirs = [base]
    for name in ("Scripts", "bin"):
        if (base / name).is_dir():
            dirs.append(base / name)
    return [str(d) for d in dirs]


def clean_env(base: dict[str, str] | None = None) -> dict[str, str]:
    """런타임을 PATH 맨 앞에 두고 PC의 Python 설정을 지운 환경.

    - `PYTHONNOUSERSITE=1`: 사용자 site-packages를 읽지 않는다.
    - `PYTHONUTF8=1`: 출력·파일의 기본 인코딩을 UTF-8로(한국어 Windows의 cp949에서 글자가 깨지지 않게).
    - 사용자의 시스템 PATH는 그대로 뒤에 둔다 — `claude`·`git` 같은 다른 프로그램을 터미널에서 쓴다.
    """
    env = dict(os.environ if base is None else base)
    for key in list(env):
        if key.upper() in FOREIGN:
            del env[key]
    path_key = next((k for k in env if k.upper() == "PATH"), "PATH")
    ours = bin_dirs()
    seen = {os.path.normcase(d) for d in ours}
    rest = [p for p in env.get(path_key, "").split(os.pathsep) if p and os.path.normcase(p.rstrip("\\/")) not in seen]
    env[path_key] = os.pathsep.join(ours + rest)
    env["PYTHONNOUSERSITE"] = "1"
    env["PYTHONUTF8"] = "1"
    return env
