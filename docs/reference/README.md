# 참조

| 문서 | 내용 |
|---|---|
| [API 참조](api.md) | 공개 함수·메서드의 서명·설명·예제(코드의 docstring에서 자동 생성 — `python docs/make_api.py`) |
| [명령줄](cli.md) | `equion run`·`check`·`info`·`new`·`convert`의 옵션 전체(도움말 그대로)·종료 코드·환경변수 |
| [방정식 함수·지시자](functions.md) | 식에 쓰는 함수·시계열 연산·지시자 한 표 |
| [출력 표 읽는 법](outputs.md) | 회귀 결과표·통계 사전·진단 표·풀이 상태·적합도·HS CSV의 항목 |
| [오류 메시지](errors.md) | 메시지 → 원인 → 고치는 법(실제 메시지) |
| [파일 형식](formats.md) | 방정식 파일 · 워크파일(.eqw) · HS CSV · 보고서 폴더 · manifest.json |
| [예제 자료](datasets.md) | toy_q·toy_a·toy_m·klein_like의 참 모형과 변수, 실제 Klein 자료 쓰는 법 |

## docstring 쓰는 법

공개 함수·메서드의 docstring은 API 참조가 되고, 그 안의 예제는 문서 검사가 실제로 돌립니다(`tests/test_docs.py`).

```text
요약 한 문단 — API 목록 표에 그대로 쓰인다.

(선택) 자세한 설명 문단.

매개변수
    이름: 뜻(기본값과 고를 수 있는 값)
돌려주는 것
    무엇을 돌려주는지
오류
    ValueError: 언제
예
    >>> wf = eqn.datasets.load("toy_q")
    >>> eq = wf.equation("eq_i").ls("I c Y(-1) R")
    >>> round(float(eq.coefs["R"]), 2)
    -0.96
관련: 다른 함수 · 문서
```

- 예제의 `eqn`·`np`·`pd`는 미리 들어 있다. 예제 자료(`eqn.datasets`)를 쓰고, 결과는 반올림해 플랫폼마다 같게 한다.
- numpy 값의 비교는 `bool(...)`·`float(...)`로 감싼다(`np.True_`가 찍히지 않게). 돌리면 안 되는 줄은 `# doctest: +SKIP`.
- 공개 함수(속성·보기 메서드 제외)는 예제가 있어야 하고, 모든 공개 항목은 설명이 있어야 한다 — 검사가 확인한다.
- docstring을 고치면 `python docs/make_api.py`로 API 참조를 다시 만든다(CI가 `--check`).
