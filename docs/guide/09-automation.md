# 가이드 9. 자동으로 돌리기

정해진 시각에 월간 스크립트를 돌리거나, CI에서 검사하거나, 다른 프로그램이 Equion을 부르는 경우입니다. 약속은 둘입니다 — **종료 코드**
(0 성공 · 1 스크립트 오류 · 2 풀이·확인 실패 · 3 입력 오류 · 130 중단)는 바뀌지 않고, **`--json`**이면 결과든 오류든 표준출력에 JSON 하나가 나옵니다.

```console
$ equion new auto --template desk
$ cd auto
```
<!-- out -->
```text
$ equion new auto --template desk
새 프로젝트 auto:
  equion.toml
  DATA/series.toml
  DATA/derived.txt
  EQUATIONS/demand.txt
  EQUATIONS/price.txt
  EQUATIONS/finance.txt
  ADDFACTORS/base.toml
  SCENARIOS/oil20.toml
  FLOWS/monthly.eqs
  notes/data_check.md
  CLAUDE.md
  README.md
  .gitignore
  DATA/raw/toy_q.csv
  DATA/raw/toy_m.csv
  ASSUMPTIONS/base.csv
자료 회차 d2026-11a를 만들어 지금 회차로 정했습니다(work/data/d2026-11a/)

다음:
  cd auto
  equion assemble main

$ cd auto
```

## 1. 결과와 오류를 JSON으로

```python
import json
import os
import subprocess
import sys


def equion_json(*args):
    """명령을 돌려 (종료 코드, JSON) — 다른 프로그램이 Equion을 부르는 꼴. 출력을 UTF-8로 받게 PYTHONIOENCODING을 준다."""
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable, "-m", "equion", *args, "--json"], capture_output=True, text=True, encoding="utf-8",
                       env=env, stdin=subprocess.DEVNULL)
    return r.returncode, json.loads(r.stdout)


code, res = equion_json("run", "FLOWS/monthly.eqs", "--set", "scenarios=base")
print(code, res["status"], [s["status"] for s in res["steps"]])
print("단계 4의 기록:", res["steps"][3]["records"])

code, err = equion_json("est", "demand:ZZ")
print(code, err["error"]["kind"], "—", err["error"]["message"][:40])
```
<!-- out -->
```text
0 flag ['ok', 'ok', 'flag', 'ok', 'ok', 'ok', 'ok', 'ok', 'ok', 'ok', 'ok']
단계 4의 기록: ['hs:hs_0001']
3 input — 없는 부품: demand:ZZ (있는 부품: demand:CN, dema
```

**Windows에서 다른 프로그램이 부를 때**는 환경 변수 `PYTHONIOENCODING=utf-8`을 주고 UTF-8로 읽습니다 — 주지 않으면 출력이 시스템 코드 페이지
(한국어 Windows는 cp949)로 나와 UTF-8로 읽다가 깨집니다.

오류의 JSON은 `{"error": {"message", "exit_code", "kind", "kind_ko"}}`입니다(사용법 오류에는 `usage`, 예상 못 한 내부 오류에는 `traceback`도).
결과가 있는 실패(멈춘 스크립트, 문제가 있는 조립)는 오류 대신 그 결과의 JSON이 나오고 종료 코드만 0이 아닙니다.

## 2. 실패를 판정하는 규칙

| 무엇에 걸리면 | 종료 코드 | 어떻게 정하나 |
|---|---|---|
| 스크립트의 단계가 실패 | 그 단계의 코드(대개 3) | 스크립트에 적은 명령 |
| `expect 대상 조건`(기본 `--stop`) | 2 | 스크립트의 `expect` 줄 — `--flag`면 표시만(0) |
| 풀리지 않은 기간(HS·전망) | 2 | `--fail-on failed`(기본) · `fallback` · `partial` · `never` |
| 재연에 다른 단계 | 2 | `equion run --replay run:…` |

```console
$ equion run FLOWS/monthly.eqs -q --set scenarios=base --fail-on fallback --log logs/monthly.log
```
<!-- out -->
```text
$ equion run FLOWS/monthly.eqs -q --set scenarios=base --fail-on fallback --log logs/monthly.log
기록  run:monthly_0002 · 단계 11 · 표시 1 · 종료 코드 0
```

`--log`는 화면의 단계 줄과 끝 줄을 파일에도 씁니다. 실행마다 `work/run/<이름>/`에 실행 기록이 남으므로, 로그를 따로 모으지 않아도
`equion work list --kind run`과 `equion work show run:… --json`으로 지난 실행을 봅니다.

## 3. 정해진 시각에 — Windows 작업 스케줄러

매달 5일 아침 7시에 돌리는 예입니다(경로는 자기 것으로). 받은 상자에 파일이 없으면 자료 단계는 '바뀐 것 없음'으로 지나갑니다.

    schtasks /Create /TN "Equion 월간" /SC MONTHLY /D 5 /ST 07:00 ^
      /TR "cmd /c cd /d D:\모형\prj && equion run FLOWS\monthly.eqs -q --log logs\monthly.log"

터미널이 아닌 곳에서 돌면 `data build --inbox ask`는 묻지 않고 짝이 하나이고 틀이 맞는 파일만 넣습니다(아니면 아무것도 넣지 않고 종료 코드 3).

## 4. CI에서 검사 — 정의를 고친 커밋마다

프로젝트를 git에 넣었다면(정의만 — `work/`·`DATA/raw/`·`exports/`는 `.gitignore`), 고칠 때마다 계산 없이 검사합니다.

    # .github/workflows/equion.yml (줄임)
    - run: pip install equion
    - run: equion assemble main
    - run: equion check FLOWS/monthly.eqs
    - run: equion check EQUATIONS/demand.txt

원자료가 저장소에 없으므로(실제 자료는 넣지 않는다) CI에서는 조립·문법 검사까지, 계산은 원자료가 있는 PC에서 합니다.

## 5. 다른 프로그램에서 Python으로

명령 대신 같은 일을 Python으로 해도 기록이 같습니다 — `eqn.project(".")`의 메서드나, 스크립트를 내보낸 Python(`equion script export FLOWS/monthly.eqs --py`
— 줄마다 `s.cmd(…)`)을 쓰면 반복·조건을 더할 수 있습니다.

## 확인할 것

- [ ] `--json`의 출력이 결과·오류 모두 `json.loads`로 읽힌다
- [ ] 종료 코드가 위 표대로 나온다(특히 `expect`의 2, `--fail-on`의 2)
- [ ] `--log` 파일에 단계 줄이 남는다
- [ ] 작업 스케줄러(또는 cron)에서 돌아도 묻지 않는다
- [ ] CI에서 `assemble`·`check`가 계산 없이 끝난다

처음으로: [가이드 목록](README.md)
