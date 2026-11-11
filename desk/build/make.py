"""Equion Desk 설치 파일을 만든다 — 런타임 묶기(runtime.py) → Inno Setup.

    uv run python desk/build/make.py            # desk/dist/EquionDesk-<판>-setup.exe
    uv run python desk/build/make.py --keep     # 이미 만든 런타임(desk/dist/EquionDesk/runtime)을 그대로 쓴다

Inno Setup 6이 있어야 한다(`winget install JRSoftware.InnoSetup`). 설치 파일은 커밋하지 않는다(DECISIONS D28).
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent
DESK = HERE.parent
DIST = DESK / "dist"


def find_iscc() -> Path | None:
    for base in (os.environ.get("LOCALAPPDATA", ""), os.environ.get("ProgramFiles(x86)", ""), os.environ.get("ProgramFiles", "")):
        for sub in ("Programs/Inno Setup 6/ISCC.exe", "Inno Setup 6/ISCC.exe"):
            exe = Path(base) / sub if base else None
            if exe and exe.is_file():
                return exe
    return None


def installer_version(version: str) -> str:
    """설치 파일 이름의 판 — `0.1.0rc1` 그대로(출시 후보임이 이름에 보이게)."""
    return version


def main() -> int:
    ap = argparse.ArgumentParser(description="Equion Desk 설치 파일 만들기")
    ap.add_argument("--keep", action="store_true", help="런타임을 다시 만들지 않는다")
    args = ap.parse_args()
    if sys.platform != "win32":
        print("설치 파일은 Windows에서 만듭니다(D29).", file=sys.stderr)
        return 3
    with open(DESK / "pyproject.toml", "rb") as f:
        version = tomllib.load(f)["project"]["version"]
    out = DIST / "EquionDesk"
    if not (args.keep and (out / "runtime" / "python.exe").is_file()):
        sys.path.insert(0, str(HERE))
        import runtime

        runtime.build(out, "3.13")
    iscc = find_iscc()
    if iscc is None:
        print("Inno Setup 6이 없습니다 — winget install JRSoftware.InnoSetup", file=sys.stderr)
        return 3
    subprocess.run([str(iscc), "/Q", f"/DAppVersion={installer_version(version)}", f"/DSourceDir={out}", str(HERE / "equiondesk.iss")], check=True)
    setup = DIST / f"EquionDesk-{installer_version(version)}-setup.exe"
    print(f"설치 파일: {setup} ({setup.stat().st_size / 1024 / 1024:.0f}MB)")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
