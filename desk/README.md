# Equion Desk

Equion 프로젝트(자료 → 식 → 조립 → 과거 재현 → 전망 → 보고서)를 화면에서 다루는 데스크톱 앱입니다. **Windows 전용**이고,
패키지 [`equion`](../README.md)의 함수를 부르는 화면입니다 — 계산과 파일 형식은 모두 패키지에 있습니다.

지금은 **뼈대(D1)까지** 만들었습니다 — 프로젝트를 탭으로 열고, 식을 추정하고, 터미널(사람·Claude)에서 친 명령의 기록이 생기는 순간
화면의 띠에 뜨고 카드로 열립니다. 닫았다 열면 지난 화면이 이어집니다. 계획은 [`docs/DESK_DEVPLAN.md`](../docs/DESK_DEVPLAN.md),
만들며 정한 것은 [`docs/DECISIONS.md`](../docs/DECISIONS.md)의 D39~D41, 설치 점검은 [`docs/DESK_D0_CHECK.md`](../docs/DESK_D0_CHECK.md).

    uv sync --all-packages                                        # 패키지 + 앱 의존성
    uv run --package equion-desk equion-desk [프로젝트폴더]        # 창으로 — 이미 떠 있으면 그 창의 새 탭으로(창은 하나)
    uv run --package equion-desk equion-desk --browser 폴더       # 개발용: 서버만 띄우고 브라우저로(http://127.0.0.1:8766/)
    uv run --package equion-desk pytest desk                      # 앱 시험(서버·작업 프로세스·터미널·탭·기록 읽기·감시)
    uv run --package equion-desk --group ui python desk/tests/ui_check.py [--shots 폴더]   # 화면 점검 — PC의 Edge를 몬다
    uv run --package equion-desk python desk/tests/bench_s1.py    # 추정 1초 기준(S1) 재기 — 합성 큰 모형
    uv run python desk/build/make.py                              # 설치 파일(Inno Setup 6 필요) → desk/dist/EquionDesk-<판>-setup.exe
    uv run python desk/build/smoke.py "<설치 폴더>" [--window]     # 설치본 기동 시험 — 설치 폴더의 런타임만으로

## 화면

| 자리 | 내용 |
|---|---|
| 제목줄 | 프로젝트 탭(8개까지) · 바뀜 기록 · 사이드바·터미널 보이기 · 설정(바탕 자동·밝게·어둡게, 글자 크기) |
| 사이드바 | **부품**(모형·블록과 식·가정·시나리오·스크립트 — 식 옆의 점은 가장 최근 추정의 통과·걸러짐, ★는 채택) · **파일**(프로젝트 폴더) |
| 가운데 탭 | 개요(모형마다 과거 재현·전망) · 식 작업대(식을 고쳐 추정 — 계수·진단·차트) · 결과 카드(`summary.md` — 표와 차트) · 파일(md·csv·글, 읽기 전용) · 작업 기록 · 바뀜 기록(차이) |
| 터미널 | 프로젝트 폴더에서 뜨는 셸 — `python`·`equion`은 앱의 런타임, `claude`는 PC의 것. '터미널로' 단추는 이름·명령을 붙이기만 한다(Enter는 직접) |
| 아래 띠 | 작업 줄(도는 계산·지난 시간·취소) · 작업 기록 띠(새 기록이 생기는 순간 — 누가·핵심 수치) · 상태줄(폴더·자료 회차·작업 프로세스·판) |

원칙(기획안 §2.4): 계산은 단추나 명령이 있을 때만 한다 — 화면을 여는 것만으로는 계산하지 않는다. 파일이 바뀌면 화면은 다시 읽지만 다시
계산하지 않는다. 기록은 고치지 않는다. 정의 파일이 밖에서 바뀌면 바뀜 기록에 남기고 알린다.

## 폴더

| 폴더 | 내용 |
|---|---|
| `equion_desk/` | 창(`__main__`) · 로컬 서버(`server`) · 프로젝트 탭과 파일 읽기(`projects`) · 작업 프로세스(`worker`) · 알림 줄과 감시(`watch`) · 기록 읽기(`records`) · 설정과 지난 화면(`config`) · 창은 하나(`instance`) · 작업 개체(`jobs`) · 터미널(`terminal`·`conpty`) · 격리 환경(`runtime`) |
| `equion_desk/web/` | 화면 — 순수 JS 모듈(`js/main.js` 틀 · `project.js` 프로젝트 탭 · `views/` 화면들 · `md.js` 문서와 차트 · `chart.js` 식 작업대 차트 · `terminal.js`), 스타일(`css/tokens.css` 색과 치수 · `app.css` 틀 · `views.css` 화면), 내장 라이브러리 `vendor/`. 패키지 안에 두어 설치본의 런타임에 함께 설치된다 |
| `equion_desk/assets/` | 아이콘(`equion-desk.ico` — `build/icon.py`가 그린다) |
| `build/` | `runtime.py`(설치본의 Python 런타임 만들기) · `make.py`·`equiondesk.iss`(설치 파일) · `icon.py`(아이콘) · `smoke.py`(설치본 기동 시험) |
| `tests/` | `test_desk.py`(경계·뼈대) · `test_app.py`(서버·작업 프로세스·터미널·탭·읽기·감시·창은 하나) · `ui_check.py`(화면 점검 — 브라우저가 있어야 해서 pytest가 모으지 않는다) · `bench_s1.py` |

앱 프로세스는 `equion`을 불러오지 않습니다(계산은 작업 프로세스가, 기록·파일은 그대로 읽는다 — D41). 설정과 지난 화면은 사용자 폴더
(`%APPDATA%\EquionDesk\config.json`)에 적고 프로젝트 폴더에는 쓰지 않습니다 — 시험·점검은 `EQUION_DESK_CONFIG_DIR`로 다른 곳을 줍니다.

Lectern(같은 저자, MIT)에서 복사한 코드와 묶어 내는 프로그램의 고지는 [`THIRD-PARTY-NOTICES.md`](THIRD-PARTY-NOTICES.md).
