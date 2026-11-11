# Equion Desk

Equion 프로젝트(자료 → 식 → 조립 → 과거 재현 → 전망 → 보고서)를 화면에서 다루는 데스크톱 앱입니다. **Windows 전용**이고,
패키지 [`equion`](../README.md)의 함수를 부르는 화면입니다 — 계산과 파일 형식은 모두 패키지에 있습니다.

지금은 **시험판(D0)을 만드는 중**입니다. 계획은 [`docs/DESK_DEVPLAN.md`](../docs/DESK_DEVPLAN.md).

    uv sync --all-packages                       # 패키지 + 앱 의존성
    uv run --package equion-desk equion-desk 프로젝트폴더          # 창으로 (--browser: 서버만 띄우고 브라우저로, --est demand:CN: 열자마자 추정)
    uv run --package equion-desk python desk/tests/bench_s1.py   # 추정 1초 기준(S1) 재기 — 합성 큰 모형
    uv run --package equion-desk pytest desk     # 앱 시험

| 폴더 | 내용 |
|---|---|
| `equion_desk/` | 창(`__main__`)·로컬 서버(`server`)·작업 프로세스(`worker`)·터미널(`terminal`·`conpty`)·격리 환경(`runtime`) |
| `equion_desk/web/` | 화면(순수 JS, 내장 라이브러리 `vendor/`) — 패키지 안에 두어 설치본의 런타임에 함께 설치된다 |
| `build/` | 런타임 묶기·설치 파일(Inno Setup) |
| `tests/` | 앱 시험(서버 API·경계) |

Lectern(같은 저자, MIT)에서 복사한 코드와 묶어 내는 프로그램의 고지는 [`THIRD-PARTY-NOTICES.md`](THIRD-PARTY-NOTICES.md).
