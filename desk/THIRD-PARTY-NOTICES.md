# Equion Desk — 제3자 고지

Equion Desk 설치본에 들어가는 다른 프로그램·코드의 고지입니다. 패키지 `equion`의 고지는 저장소 최상위의
[`THIRD-PARTY-NOTICES.md`](../THIRD-PARTY-NOTICES.md)에 있습니다.

| 무엇 | 어디에 쓰나 | 라이선스 |
|---|---|---|
| Lectern 0.69.1 (`cd7fb26`, 같은 저자) | `conpty.py`·`terminal.py`를 복사해 고치고, 서버의 보호 장치·`HttpServer`·터미널 규약을 가져왔다(DECISIONS D10·D39) — 복사한 파일은 머리말에 적는다 | MIT |
| xterm.js (@xterm/xterm 5.5.0) · @xterm/addon-fit 0.10.0 · @xterm/addon-unicode11 0.8.0 | 터미널 화면 — `equion_desk/web/vendor/xterm/`, 라이선스 전문 `equion_desk/web/vendor/licenses/` | MIT |
| pywebview | 창(Edge WebView2) | BSD-3-Clause |
| Flask · Werkzeug · Jinja2 · MarkupSafe · itsdangerous · click · blinker | 로컬 서버 | BSD-3-Clause |
| waitress | 로컬 서버 | ZPL-2.1 |
| watchdog | 프로젝트 폴더 감시 | Apache-2.0 |

설치본의 런타임(`runtime/`)에 들어가는 것 — 각 패키지의 라이선스 전문은 설치 폴더의 `runtime/Lib/site-packages/<패키지>-<판>.dist-info/`에 그대로 들어 있다.

| 무엇 | 라이선스 |
|---|---|
| CPython 3.13 (python-build-standalone 배포본 — OpenSSL·SQLite·zlib·bzip2·xz·libffi 등을 품는다, `runtime/LICENSE.txt`) | PSF-2.0 외 |
| numpy · pandas · scipy (OpenBLAS·LAPACK 포함) | BSD-3-Clause |
| openpyxl · et-xmlfile · tomlkit · six | MIT |
| python-dateutil · tzdata | Apache-2.0 / BSD-3-Clause |
| pythonnet · clr-loader · proxy-tools · bottle · typing-extensions (pywebview의 의존성) | MIT · MIT · MIT · MIT · PSF-2.0 |
