"""설치본에 넣을 Python 런타임을 만든다(DECISIONS D39) — python-build-standalone CPython + 잠긴 패키지를 미리 설치.

    uv run python desk/build/runtime.py [--out desk/dist/EquionDesk] [--python 3.13]

하는 일
1. uv로 python-build-standalone CPython을 받아(`uv python install`) `<out>/runtime/`에 복사한다.
2. `uv.lock`의 앱 의존성(equion-desk와 그 의존성, 개발용 제외)을 해시 검사와 함께 그 런타임에 설치한다.
3. 이 저장소의 `equion`·`equion-desk`를 휠로 만들어 설치한다(편집 가능 설치가 아니다 — 설치본은 저장소와 무관하게 돈다).
4. 설치본에 필요 없는 것을 뺀다(tcl/tk·IDLE·시험 폴더·pip 등)과 크기를 잰다.

결과는 `<out>/runtime/python.exe`·`pythonw.exe`·`Scripts/equion.cmd`(어디로 옮겨도 돈다). 앱은 `runtime\\pythonw.exe -I -m equion_desk`로 뜬다.
Windows에서 돌린다(설치본은 Windows 전용 — D29). 인터넷이 필요하다(만들 때만 — 설치본은 인터넷 없이 돈다).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# 설치본에 필요 없는 것 — 런타임 폴더 기준. 앱·터미널·작업 프로세스가 쓰지 않는다
TRIM = ["tcl", "Lib/tkinter", "Lib/idlelib", "Lib/turtledemo", "Lib/test", "Lib/ensurepip", "Lib/lib2to3", "Lib/pydoc_data",
        "DLLs/tcl86t.dll", "DLLs/tk86t.dll", "DLLs/_tkinter.pyd", "DLLs/tcl90t.dll", "DLLs/tk90t.dll", "DLLs/zlib1.dll.bak",
        "include", "libs", "share"]
TRIM_PACKAGE_DIRS = ("tests", "testing/tests", "test")     # 패키지 안의 시험 폴더(numpy/tests …)
TRIM_PACKAGES = ("pip", "setuptools", "wheel")
SHIMS = {"equion": "equion", "equion-desk": "equion_desk"}     # 터미널에서 치는 명령 → 모듈


def run(*cmd: str, **kw) -> subprocess.CompletedProcess:
    print("  $", " ".join(str(c) for c in cmd), flush=True)
    return subprocess.run([str(c) for c in cmd], check=True, **kw)


def size_of(path: Path) -> int:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def mb(n: int) -> str:
    return f"{n / 1024 / 1024:.0f}MB"


def fetch_python(version: str, work: Path) -> Path:
    """python-build-standalone CPython을 받아 그 폴더를 돌려준다."""
    store = work / "py"
    run("uv", "python", "install", version, "--install-dir", store, "--no-bin", "--color", "never",
        env=dict(os.environ, UV_PYTHON_INSTALL_REGISTRY="0"))     # PC의 레지스트리(PEP 514)에 등록하지 않는다
    # 판 폴더(cpython-3.13.18-…)와 그것을 가리키는 연결(cpython-3.13-…)이 함께 생긴다 — 연결이 아닌 진짜 폴더를 쓴다
    found = [d for d in store.iterdir() if d.is_dir() and d.name.startswith("cpython-") and (d / "python.exe").is_file()
             and not d.is_symlink() and not d.is_junction()]
    if len(found) != 1:
        raise SystemExit(f"받은 Python을 찾지 못했습니다: {[d.name for d in store.iterdir()]}")
    return found[0]


def build(out: Path, version: str) -> dict:
    runtime = out / "runtime"
    if runtime.exists():
        shutil.rmtree(runtime)
    out.mkdir(parents=True, exist_ok=True)
    began = time.perf_counter()
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        print("1. Python 받기")
        shutil.copytree(fetch_python(version, work), runtime)
        py = runtime / "python.exe"
        base = size_of(runtime)

        print("2. 잠긴 의존성 설치(해시 검사)")
        req = work / "requirements.txt"
        run("uv", "export", "--locked", "--package", "equion-desk", "--no-dev", "--no-emit-workspace", "--format", "requirements-txt",
            "--output-file", req, "--color", "never", cwd=ROOT, stdout=subprocess.DEVNULL)
        pip = ["uv", "pip", "install", "--python", py, "--break-system-packages", "--link-mode", "copy", "--compile-bytecode",
               "--color", "never"]
        run(*pip, "--require-hashes", "--no-deps", "-r", req, env=dict(os.environ, UV_PYTHON_PLATFORM="", VIRTUAL_ENV=""))

        print("3. equion·equion-desk 휠을 만들어 설치")
        wheels = work / "wheels"
        run("uv", "build", "--wheel", "--out-dir", wheels, "--color", "never", cwd=ROOT)
        run("uv", "build", "--wheel", "--out-dir", wheels, "--package", "equion-desk", "--color", "never", cwd=ROOT)
        run(*pip, "--no-deps", *sorted(wheels.glob("*.whl")))

    print("4. 필요 없는 것 빼기")
    full = size_of(runtime)
    for rel in TRIM:
        target = runtime / rel
        if target.is_dir():
            shutil.rmtree(target)
        elif target.is_file():
            target.unlink()
    site = runtime / "Lib" / "site-packages"
    for pkg in TRIM_PACKAGES:
        for hit in list(site.glob(pkg)) + list(site.glob(f"{pkg}-*.dist-info")):
            shutil.rmtree(hit, ignore_errors=True)
    for pkg in site.iterdir():
        if pkg.is_dir() and pkg.name in ("numpy", "pandas", "scipy"):
            for sub in list(pkg.rglob("tests")):
                if sub.is_dir():
                    shutil.rmtree(sub, ignore_errors=True)
    # 명령 실행기: 설치 도구가 만든 Scripts/*.exe는 만든 곳의 python.exe 절대 경로를 품고 있어, 설치 폴더로 옮기면 돌지 않는다.
    # 모두 지우고 자기 위치 기준으로 런타임을 부르는 .cmd를 둔다(격리 모드 -I — PC의 Python 설정을 읽지 않는다).
    scripts = runtime / "Scripts"
    for exe in scripts.glob("*.exe"):
        exe.unlink()
    for name, module in SHIMS.items():
        (scripts / f"{name}.cmd").write_text(f'@"%~dp0..\\python.exe" -I -m {module} %*\r\n', encoding="ascii", newline="")

    print("5. 확인 — 격리 모드로 불러오기")
    probe = ("import sys, json, equion, equion_desk, numpy, pandas, scipy, flask, waitress, watchdog, webview;"
             "print(json.dumps({'python': sys.version.split()[0], 'equion': equion.__version__, 'desk': equion_desk.__version__,"
             "'numpy': numpy.__version__, 'pandas': pandas.__version__, 'scipy': scipy.__version__, 'prefix': sys.prefix}))")
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith(("PYTHON", "VIRTUAL_ENV", "UV_"))}
    r = subprocess.run([str(py), "-I", "-c", probe], capture_output=True, text=True, env=env, cwd=str(out))
    if r.returncode != 0:
        raise SystemExit("런타임이 패키지를 불러오지 못했습니다:\n" + r.stderr)
    info = json.loads(r.stdout)
    r = subprocess.run(["cmd", "/c", str(scripts / "equion.cmd"), "--version"], capture_output=True, text=True, env=env, cwd=str(out))
    if r.returncode != 0 or info["equion"] not in r.stdout:
        raise SystemExit("equion 명령이 돌지 않습니다:\n" + r.stdout + r.stderr)
    info.update(base_bytes=base, full_bytes=full, bytes=size_of(runtime), seconds=round(time.perf_counter() - began, 1),
                files=sum(1 for f in runtime.rglob("*") if f.is_file()))
    (out / "runtime.json").write_text(json.dumps(info, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n런타임: {runtime}\n  Python {info['python']} · equion {info['equion']} · desk {info['desk']} · numpy {info['numpy']} · "
          f"pandas {info['pandas']} · scipy {info['scipy']}\n  크기: Python만 {mb(base)} → 패키지 설치 뒤 {mb(full)} → 뺀 뒤 {mb(info['bytes'])}"
          f" (파일 {info['files']}개) · {info['seconds']}초")
    return info


def main() -> int:
    ap = argparse.ArgumentParser(description="Equion Desk 설치본의 Python 런타임 만들기")
    ap.add_argument("--out", default=str(ROOT / "desk" / "dist" / "EquionDesk"), help="만들 폴더(그 안에 runtime/)")
    ap.add_argument("--python", default="3.13", help="CPython 판(기본 3.13 — D39)")
    args = ap.parse_args()
    if sys.platform != "win32":
        print("설치본은 Windows에서 만듭니다(D29).", file=sys.stderr)
        return 3
    build(Path(args.out).resolve(), args.python)
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
