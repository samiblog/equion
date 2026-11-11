"""Equion Desk 시험 — 경계(D28)와 뼈대. `uv run --package equion-desk pytest desk` · `python desk/tests/test_desk.py`."""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tomllib

HERE = os.path.dirname(os.path.abspath(__file__))
DESK = os.path.dirname(HERE)
ROOT = os.path.dirname(DESK)

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(ok), detail))
    print(("  ✓ " if ok else "  ✗ ") + name + (f" — {detail}" if detail and not ok else ""))


def _toml(path: str) -> dict:
    with open(path, "rb") as f:
        return tomllib.load(f)


def section_boundary() -> None:
    print("A. 경계 — equion-desk → equion 한쪽만(D28)")
    hits = []
    for base, _dirs, files in os.walk(os.path.join(ROOT, "equion")):
        for fn in files:
            if fn.endswith(".py"):
                with open(os.path.join(base, fn), encoding="utf-8") as f:
                    if re.search(r"^\s*(import|from)\s+equion_desk\b", f.read(), re.M):
                        hits.append(os.path.relpath(os.path.join(base, fn), ROOT))
    check("A1 패키지 equion은 equion_desk를 import하지 않는다", not hits, ", ".join(hits))

    root = _toml(os.path.join(ROOT, "pyproject.toml"))
    desk = _toml(os.path.join(DESK, "pyproject.toml"))
    check("A2 equion 휠에는 equion/만 들어간다", root["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"] == ["equion"])
    rdeps = " ".join(root["project"]["dependencies"]).lower()
    check("A3 앱 의존성은 패키지의 필수 의존성에 없다", not any(n in rdeps for n in ("pywebview", "flask", "waitress", "watchdog")))
    check("A4 desk는 workspace 구성원이고 equion을 workspace에서 가져온다",
          root["tool"]["uv"]["workspace"]["members"] == ["desk"] and desk["tool"]["uv"]["sources"]["equion"] == {"workspace": True})
    web = [d for d in desk["project"]["dependencies"] if d.startswith("pywebview")]
    check("A5 창(pywebview)은 Windows에서만 설치된다(D29)", len(web) == 1 and "sys_platform == 'win32'" in web[0])
    check("A6 Python 범위가 패키지와 같다(잠금 파일을 함께 쓴다)",
          desk["project"]["requires-python"] == root["project"]["requires-python"])
    with open(os.path.join(ROOT, "uv.lock"), encoding="utf-8") as f:
        head = f.read(200)
    check("A7 잠금 파일의 Python 범위가 줄지 않았다", f'requires-python = "{root["project"]["requires-python"]}"' in head, head[:80])


def section_skeleton() -> None:
    print("B. 뼈대")
    import equion
    import equion_desk

    desk = _toml(os.path.join(DESK, "pyproject.toml"))
    check("B1 판이 pyproject와 같다", equion_desk.__version__ == desk["project"]["version"])
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable, "-m", "equion_desk", "--version"], capture_output=True, text=True, encoding="utf-8", env=env)
    check("B2 python -m equion_desk --version", r.returncode == 0 and equion_desk.__version__ in r.stdout and equion.__version__ in r.stdout,
          r.stdout + r.stderr)


def run() -> int:
    RESULTS.clear()
    section_boundary()
    section_skeleton()
    bad = [n for n, ok, _ in RESULTS if not ok]
    print(f"\nEquion Desk 시험 {len(RESULTS) - len(bad)}/{len(RESULTS)}")
    return len(bad)


def test_suite() -> None:
    assert run() == 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(1 if run() else 0)
