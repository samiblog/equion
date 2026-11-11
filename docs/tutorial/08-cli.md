# 8. 명령줄

같은 분석을 매번 손으로 돌리지 않고, 평범한 Python 스크립트로 써 두고 `equion run`으로 실행합니다. 실행마다 보고서 폴더
(결과 표·그래프·로그·재현 기록)가 남고, 종료 코드로 성공·실패를 알려 주므로 자동화(일정 실행·CI)에 그대로 씁니다.

터미널에서는 `equion run 스크립트.py`처럼 씁니다. 이 문서는 출력을 함께 보이려고 Python에서 같은 명령을 부르는 작은 도우미를 씁니다.

```python
import json
import os
import subprocess
import sys
from pathlib import Path


def equion(*args):
    """터미널의 `equion …`과 같다 — 화면 출력과 종료 코드를 보인다."""
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable, "-m", "equion", *args], capture_output=True, text=True,
                       encoding="utf-8", env=env)
    print((r.stdout + r.stderr).rstrip())
    print(f"(종료 코드 {r.returncode})")
    return r.returncode


equion("--version")
```
<!-- out -->
```text
equion 0.8.0
(종료 코드 0)
```

## 8.1 스크립트 쓰기

스크립트는 평범한 Python입니다. 바꿔 가며 돌릴 값은 `eqn.params(이름=기본값)`으로 받습니다 — 명령줄의 `--set 이름=값`이 기본값을
덮고, 기본값의 형(정수·실수·글자)으로 바뀝니다. `eqn.show(…)`로 보인 표·그래프는 보고서에 모입니다.

```python
os.makedirs("scripts", exist_ok=True)
with open("scripts/toy_forecast.py", "w", encoding="utf-8") as f:
    f.write('''"""작은 거시 모형: 추정 → 과거 재현 → 정부지출 시나리오 → 전망."""
import equion as eqn

p = eqn.params(g_up=10.0, start="1975Q1", end="2019Q4", horizon="2021Q4")

wf = eqn.datasets.load("toy_q")
wf.smpl(p.start, p.end)
eq_i = wf.equation("eq_i").ls("I c Y(-1) R")
eq_cn = wf.equation("eq_cn").tsls("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")
eq_p = wf.equation("eq_p").ls("dlog(P) c dlog(Y) dlog(POIL)")
m = wf.model("toy").merge(eq_i, eq_cn, eq_p).append("Y = CN + I + G")
eqn.show(eq_cn)

base = m.solve()
eqn.show(base.summary())

m.scenario("g_up").shock("G", p.g_up, "2015Q1", p.end, kind="pct")
m.solve("2015Q1", p.end)
eqn.show(wf.graph("g_y", "Y Y_0 Y_1", start="2010Q1", title="국민소득"))

m.scenario("baseline")
m.forecast("2020Q1", p.horizon, exog_fill="trend")
eqn.show(wf.table("fc", wf.to_pandas(["Y_0", "CN_0", "I_0"], labels=True).loc["2020Q1":p.horizon].round(1),
                  title="전망"))
''')
print(len(Path("scripts/toy_forecast.py").read_text(encoding="utf-8").splitlines()), "줄")
```
<!-- out -->
```text
24 줄
```

## 8.2 실행과 보고서

```python
equion("run", "scripts/toy_forecast.py", "--run-id", "first", "-q")
print(sorted(os.listdir("out/first")))
```
<!-- out -->
```text
[equion] 성공 · 0.2초 · 풀이 3회(정상 208 · 일부식 제외 0 · 실패대체 0 · 실패 0) · 보고서 out/first/report.html · 종료 코드 0
(종료 코드 0)
['graphs', 'manifest.json', 'plotly.min.js', 'report.html', 'run.log', 'tables']
```

`-q`는 요약 줄만 보입니다(없으면 스크립트 출력이 그대로 나온다). 보고서 폴더에는:

| 파일 | 내용 |
|---|---|
| `report.html` | 모든 출력을 한 페이지로(표·그래프·풀이 상태·입력 파일·로그). 인터넷 없이 열린다 |
| `manifest.json` | 재현 기록: 버전·플랫폼·git 커밋·명령줄·매개변수·입력 파일 해시·풀이마다 기간 상태·출력 목록·시간 |
| `run.log` | 화면 출력 그대로 |
| `tables/` · `graphs/` | 표(csv·xlsx·json)와 그래프(html + 데이터) |

```python
man = json.loads(Path("out/first/manifest.json").read_text(encoding="utf-8"))
print(man["format"], man["status"], man["exit_code"])
print(man["params"]["resolved"])
print([(s["model"], s["scenario"], s["counts"]["ok"]) for s in man["solves"]])
print([o["title"] for o in man["outputs"]])
```
<!-- out -->
```text
equion-run ok 0
{'g_up': 10.0, 'start': '1975Q1', 'end': '2019Q4', 'horizon': '2021Q4'}
[('toy', 'baseline', 180), ('toy', 'g_up', 20), ('toy', 'baseline', 8)]
['방정식 eq_cn', '적합도 상위 10 — toy·baseline(_0)', '국민소득', '전망']
```

## 8.3 매개변수와 옵션

```python
equion("run", "scripts/toy_forecast.py", "--set", "g_up=5", "--smpl", "1990Q1:2019Q4",
       "--format", "csv,xlsx", "--run-id", "g5", "-q")
man = json.loads(Path("out/g5/manifest.json").read_text(encoding="utf-8"))
print(man["params"]["resolved"]["g_up"], man["smpl"], sorted(os.listdir("out/g5/tables"))[:3])
```
<!-- out -->
```text
[equion] 성공 · 0.2초 · 풀이 3회(정상 208 · 일부식 제외 0 · 실패대체 0 · 실패 0) · 보고서 out/g5/manifest.json · 종료 코드 0
(종료 코드 0)
5.0 1990Q1 2019Q4 ['01_eq_cn.csv', '02_toy_0_fit.csv', '04_fc.csv']
```

| 옵션 | 뜻 |
|---|---|
| `--set 이름=값` · `--params 파일.json` | 매개변수(JSON 위에 `--set`이 덮는다). 스크립트가 선언하지 않은 이름은 끝에 알려 준다 |
| `--smpl S:E` | 새로 여는 워크파일의 기본 표본, 그리고 매개변수 `smpl` |
| `--out 폴더` · `--run-id ID` | 보고서 위치(기본 `out/날짜-시각_스크립트이름`). ID는 폴더 이름 하나 |
| `--format csv,xlsx,json,html` | 표 형식과 report.html(기본 `csv,html`) · `--no-report`는 보고서 없이 |
| `--fail-on failed\|fallback\|partial\|never` | 이 상태의 기간이 있으면 종료 코드 2 |
| `-q` · `-v` · `--log 파일` | 요약만 · 엔진 상세까지 · 로그 사본 |
| `--threads N` | BLAS 스레드 수 고정(재현성) · `--watch`는 파일이 바뀌면 다시 실행 · `-i`는 실행 뒤 대화창 |
| `--dry-run` | 실행하지 않고 문법·설정만 확인 · `--redact`는 공유용(경로를 줄이고 작업 폴더를 뺀다) |

## 8.4 종료 코드 — 자동화의 약속

| 코드 | 뜻 |
|---|---|
| 0 | 성공 |
| 1 | 스크립트 오류(예외·문법 오류) |
| 2 | 풀이 실패 조건(`--fail-on`)에 걸림 |
| 3 | 입력 오류(파일 없음·방정식 문법·모델 구조·잘못된 명령줄 인자) |
| 130 | Ctrl+C로 중단 |

자료 첫 분기부터 풀면 일부 식을 빼는 기간(`partial`)이 생깁니다. 기본(`--fail-on failed`)은 성공으로 두고, 더 엄격하게
하면 종료 코드 2가 됩니다.

```python
equion("run", "scripts/toy_forecast.py", "--set", "start=1970Q1", "--fail-on", "partial", "--run-id", "strict", "-q")
equion("run", "scripts/없는파일.py")
```
<!-- out -->
```text
[equion] 풀이 실패 조건(--fail-on partial):
  모델 toy · 시나리오 baseline(_0) 1970Q1~2019Q4: 일부식 제외 1
[equion] 풀이 실패 · 0.2초 · 풀이 3회(정상 227 · 일부식 제외 1 · 실패대체 0 · 실패 0) · 보고서 out/strict/report.html · 종료 코드 2
(종료 코드 2)
equion: 오류: 스크립트가 없습니다: scripts/없는파일.py
(종료 코드 3)
```

## 8.5 실행 없이 검사하기 — check

방정식 파일은 실행하기 전에 문법·구조·결측 입력을 검사할 수 있습니다(데이터를 주면 변수 존재와 결측까지).

```python
with open("toy_model.txt", "w", encoding="utf-8") as f:
    f.write("I c Y(-1) R\nCN c Y CN(-1)\ndlog(P) c dlog(Y) dlog(POIL)\nY = CN + I + G\n")
import equion as eqn
equion("check", "toy_model.txt", "--data", eqn.datasets.path("toy_q"))
with open("broken.txt", "w", encoding="utf-8") as f:
    f.write("I c Y(-1) R\nCN c log(Y CN(-1)\nY = CN + I + NOPE\n")
equion("check", "broken.txt")
```
<!-- out -->
```text
검사: toy_model.txt (방정식 파일)
  데이터: equion/datasets/toy_q.csv — Q 1970Q1~2019Q4 · 시리즈 10
  식: 추정식 3 · NLS 0 · 항등식 1 (문법 오류 0)
  변수: 내생 4 · 외생 3
  블록: 3개 — 동시 1 (최대 2변수) · 순차 2
  표본: 1970Q1~2019Q4 (200기)
  [경고] 1행: I 식의 입력이 1기 비어 있음(1970Q1~1970Q1) — 풀이 때 그 기간 이 식은 제외됩니다(on_missing='exclude')
  [경고] 2행: CN 식의 입력이 1기 비어 있음(1970Q1~1970Q1) — 풀이 때 그 기간 이 식은 제외됩니다(on_missing='exclude')
  [경고] 3행: P 식의 입력이 1기 비어 있음(1970Q1~1970Q1) — 풀이 때 그 기간 이 식은 제외됩니다(on_missing='exclude')
결과: 통과 — 오류 0 · 경고 3
(종료 코드 0)
검사: broken.txt (방정식 파일)
  식: 추정식 1 · NLS 0 · 항등식 1 (문법 오류 1)
  구조: 문법 오류가 있어 검사하지 않음
  [오류] 2행: 괄호가 닫히지 않았습니다 (열린 괄호 1개 남음): CN c log(Y CN(-1)
         CN c log(Y CN(-1)
결과: 실패 — 오류 1 · 경고 0
(종료 코드 3)
```

## 8.6 요약 보기와 새 프로젝트

```python
equion("info", eqn.datasets.path("toy_m"))
equion("info", "out/first")
equion("new", "my_project")
print(sorted(os.listdir("my_project")))
```
<!-- out -->
```text
종류: 데이터 파일
경로: equion/datasets/toy_m.csv
이름: toy_m
주기: M
기간: 2000M1~2019M12
기간 수: 240
시리즈: 3
마지막 관측(기간: 시리즈 수):
  2019M12: 3
(종료 코드 0)
종류: 실행 보고서
경로: out/first
실행 ID: first
스크립트: scripts/toy_forecast.py
상태: ok
종료 코드: 0
시작: 2026-10-30T03:01:17
소요(초): 0.174
매개변수:
  g_up: 10.0
  start: 1975Q1
  end: 2019Q4
  horizon: 2021Q4
풀이 수: 3
기간 상태 합계:
  ok: 208
  partial: 0
  fallback: 0
  failed: 0
출력 수: 4
입력 파일: equion/datasets/toy_q.csv
버전: 0.8.0
(종료 코드 0)
새 프로젝트 my_project:
  README.md
  .gitignore
  scripts/main.py
  EQUATIONS/model.txt
  DATA/data.csv

다음:
  cd my_project
  equion run scripts/main.py
(종료 코드 0)
['.gitignore', 'DATA', 'EQUATIONS', 'README.md', 'scripts']
```

`equion new`가 만든 폴더에는 예시 자료·방정식 파일·스크립트·README가 있어 그대로 `equion run scripts/main.py`로 돕니다.

## 8.7 자동화 예

일정 실행이나 CI에서는 검사 → 실행 → 결과 확인을 종료 코드로 잇습니다.

<!-- skip -->
```bash
set -e
equion check EQUATIONS/model.txt --data DATA/data.csv --strict
equion run scripts/main.py --fail-on fallback --run-id "$(date +%Y%m%d)" -q
```

API 키 같은 비밀 값은 스크립트에 쓰지 말고 환경변수로 넘겨 `eqn.secret("이름")`으로 읽습니다 — 읽은 값은 보고서·로그에서
`***`로 가려집니다. 보고서를 남에게 보낼 때는 `--redact`로 작업 폴더·실행 파일 경로를 뺍니다.

## 정리

| 하려는 일 | 명령 |
|---|---|
| 실행 + 보고서 | `equion run s.py` · `--set a=1` · `--smpl S:E` · `--format …` · `--run-id ID` · `-q` |
| 실패를 코드로 | `--fail-on fallback` → 2 |
| 검사 · 요약 · 새로 | `equion check model.txt --data d.csv` · `equion info 경로` · `equion new 폴더` |

전체 옵션: [명령줄 참조](../reference/cli.md). 레시피: [명령줄 레시피](../howto/cli.md).
