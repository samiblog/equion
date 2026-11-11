# Equion Desk — 제3자 고지

Equion Desk 설치본에 들어가는 다른 프로그램·코드의 고지입니다. 패키지 `equion`의 고지는 저장소 최상위의
[`THIRD-PARTY-NOTICES.md`](../THIRD-PARTY-NOTICES.md)에 있습니다.

| 무엇 | 어디에 쓰나 | 라이선스 |
|---|---|---|
| Lectern 0.69.1 (`cd7fb26`, 같은 저자) | `conpty.py`·`terminal.py`·`instance.py`를 복사해 고치고, 서버의 보호 장치·`HttpServer`·터미널 규약·설정 파일의 틀·차트 그리기의 틀을 가져왔다(DECISIONS D10·D39·D41) — 복사한 파일은 머리말에 적는다. 화면의 뼈대(툴바·프로젝트 탭·사이드바·가운데 탭·오른쪽 터미널·상태줄)도 Lectern을 따랐다(스타일과 스크립트는 새로 썼다) | MIT |
| xterm.js (@xterm/xterm 5.5.0) · @xterm/addon-fit 0.10.0 · @xterm/addon-unicode11 0.8.0 | 터미널 화면 — `equion_desk/web/vendor/xterm/`, 라이선스 전문 `equion_desk/web/vendor/licenses/` | MIT |
| markdown-it | 문서(md) 그리기 — 결과 카드와 프로젝트의 md 파일. `equion_desk/web/vendor/markdown-it/` | MIT |
| DOMPurify 3.4.16 | 그린 문서의 정화 — `equion_desk/web/vendor/dompurify/` | Apache-2.0 (MPL-2.0 과 이중 라이선스) |
| Vega 6.4.0 · Vega-Lite 6.5.0 | 문서의 ```vega-lite 차트 — `equion_desk/web/vendor/vega/` (안에 든 d3 모듈은 ISC) | BSD-3-Clause |
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
