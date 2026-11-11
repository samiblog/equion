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

설치본에 Python 런타임과 수치 패키지를 넣는 걸음(D0-4)에서 CPython·numpy·pandas·scipy·openpyxl 등의 고지를 여기에 더한다.
