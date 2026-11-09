# 명령줄 참조

`equion`은 설치하면 생기는 명령입니다(`uv run equion …` 또는 `python -m equion …`도 같다). 아래 도움말은 실제 출력입니다.
배우는 순서는 [튜토리얼 8](../tutorial/08-cli.md).

```python
import os
import subprocess
import sys


def helptext(*args):
    env = dict(os.environ, PYTHONIOENCODING="utf-8", COLUMNS="110")
    r = subprocess.run([sys.executable, "-m", "equion", *args], capture_output=True, text=True, encoding="utf-8", env=env)
    print(r.stdout.rstrip())


helptext("--help")
```
<!-- out -->
```text
사용법: equion [-h] [--version] 명령 ...

Equion — 방정식 추정·연립 모델 풀이: 스크립트 실행·검사·정보·새 프로젝트·조립 검사·자료 회차·작업 명령

인자:
  명령
    run       스크립트를 실행하고 보고서 폴더를 남긴다
    check     실행 없이 방정식 파일·스크립트를 검사한다
    info      데이터·워크파일·방정식 파일·보고서 폴더 요약(경로 없으면 실행 환경)
    convert   옛 저장 형식(레거시 pickle·.wt·.mmw)을 워크파일(.eqw)로
    new       새 프로젝트 폴더(예시 데이터·방정식·스크립트)
    assemble  프로젝트의 모형을 조립해 검사한다(계산 없이 — 내생·외생·겹친 목표·모르는 변수)
    ident     프로젝트의 항등식을 보이거나(--check) 실측으로 계산해 견준다
    data      프로젝트의 자료 회차 — 목록·원자료 넣기·만들기·바꾸기·차이·영향
    est       식 하나를 추정해 기록을 남긴다(부품 또는 식 글자 — 후보)
    adopt     추정 기록을 부품의 채택 계수로(블록 파일의 줄·채택표를 고치고 바뀜 기록에)
    compare   기록 비교 — 추정 후보(적합·진단·기준·단독 모의) 또는 HS(변수별 RMSPE)
    hs        과거 재현을 풀고 기록을 남긴다(바꿔 끼우기·전후 비교·그때 그대로 다시)
    work      작업 기록 — 목록·보기·고정·메모·정리
    history   바뀜 기록 — 정의 파일이 누가·언제·어떻게 바뀌었나, 되돌리기

옵션:
  -h, --help  도움말을 보이고 끝낸다
  --version   버전을 보이고 끝낸다

종료 코드: 0 성공 · 1 스크립트 오류 · 2 풀이 실패(--fail-on) · 3 입력 오류 · 130 중단
```

## 종료 코드

| 코드 | 뜻 |
|---|---|
| 0 | 성공 |
| 1 | 스크립트 오류(예외·문법 오류) · `sys.exit(문자열)` |
| 2 | 풀이 실패 조건(`--fail-on`)에 걸림 — 사유는 화면과 manifest의 `fail_reasons` |
| 3 | 입력 오류: 파일 없음·방정식 문법·모델 구조·merge 실패·잘못된 명령줄 인자 |
| 130 | Ctrl+C로 중단 |

스크립트의 `sys.exit(n)`(정수)은 그대로 n입니다. 이 약속은 자동화가 기대므로 바꾸지 않습니다(DECISIONS D15).

## equion run

```python
helptext("run", "--help")
```
<!-- out -->
```text
사용법: equion run [-h] [--smpl S:E] [--set 이름=값] [--params FILE.json] [--out 폴더] [--run-id ID] [--format 목록]
                [--no-report] [--plotlyjs {copy,cdn}] [--fail-on {failed,fallback,partial,never}]
                [--threads N] [-q | -v] [--log FILE] [-i] [--watch] [--interval 초] [--dry-run] [--redact]
                script

평범한 Python 스크립트를 실행한다. 스크립트에 넘길 인자는 -- 뒤에 쓴다.

인자:
  script                실행할 .py 스크립트

옵션:
  -h, --help            도움말을 보이고 끝낸다
  --smpl S:E            새로 여는 워크파일의 기본 표본(예: 2000Q1:2022Q4, @all)
  --set 이름=값            스크립트 매개변수(eqn.params)를 덮는다. 여러 번 쓸 수 있다
  --params FILE.json    매개변수 JSON 파일(--set이 그 위에 덮는다)
  --out 폴더              보고서를 둘 폴더(기본: out)
  --run-id ID           보고서 하위 폴더 이름(기본: 날짜-시각_스크립트이름)
  --format 목록           출력 형식 csv·xlsx·json·html 중 쉼표로(기본: csv,html)
  --no-report           보고서 폴더를 만들지 않는다
  --plotlyjs {copy,cdn}
                        그래프 스크립트: copy(보고서에 넣음, 인터넷 없이 열림·기본) · cdn
  --fail-on {failed,fallback,partial,never}
                        이 상태의 기간이 있으면 종료 코드 2(기본: failed)
  --threads N           BLAS 스레드 수 고정(재현성)
  -q, --quiet           요약 줄과 오류만 보인다
  -v, --verbose         엔진 상세 로그까지 보인다
  --log FILE            실행 로그를 이 파일에도 쓴다
  -i, --interactive     실행 뒤 스크립트 변수를 가진 Python 대화창으로
  --watch               스크립트·입력 파일이 바뀌면 다시 실행한다(Ctrl+C로 끝)
  --interval 초          --watch 확인 간격(기본 1초)
  --dry-run             실행하지 않고 문법·설정만 확인한다
  --redact              공유용 보고서: 작업 폴더·실행 파일 경로·git 브랜치를 빼고 경로를 줄인다
```

- 스크립트는 `.py` 파일. 인코딩 선언(`# -*- coding: cp949 -*-`)과 BOM을 따른다. 스크립트가 작업 폴더를 바꿔도 보고서는 실행한 자리 기준.
- `--run-id`는 `--out` 안의 폴더 이름 하나(경로 구분자·`..`·빈 값 불가). 같은 ID면 이전 보고서를 지우고 다시 쓴다(보고서가 아닌 폴더는 지우지 않음).
- 비밀 값: `eqn.secret("이름")`으로 읽은 값과 이름이 key·token·secret·password 같은 `--set` 값은 보고서·로그에서 `***`로 가린다.
- `-- 인자…`: `--` 뒤는 스크립트의 `sys.argv`로 간다.

## equion check

```python
helptext("check", "--help")
```
<!-- out -->
```text
사용법: equion check [-h] [--data FILE] [--freq {Q,M,A}] [--smpl S:E] [--json] [--strict] path

인자:
  path            방정식 파일(.txt) 또는 스크립트(.py)

옵션:
  -h, --help      도움말을 보이고 끝낸다
  --data FILE     데이터 파일·워크파일 — 변수 존재와 결측 입력까지 검사
  --freq {Q,M,A}  주기(데이터가 없거나 추론이 안 될 때)
  --smpl S:E      결측 입력을 볼 구간(기본: 데이터 전체)
  --json          결과를 JSON으로
  --strict        경고도 실패(종료 코드 3)로 본다
```

방정식 파일(.txt)은 문법·구조(목표변수 중복·정해지지 않는 변수)·블록, `--data`를 주면 변수 존재와 결측 입력까지, 스크립트(.py)는
Python 문법만 봅니다. 식이 하나도 없는 파일은 오류입니다. 방정식 파일은 UTF-8(BOM 무관), cp949는 경고하고 읽습니다.

## equion info

```python
helptext("info", "--help")
```
<!-- out -->
```text
사용법: equion info [-h] [--freq {Q,M,A}] [--all] [--json] [path]

인자:
  path            경로

옵션:
  -h, --help      도움말을 보이고 끝낸다
  --freq {Q,M,A}  데이터 주기(추론이 안 될 때)
  --all           시리즈별 마지막 관측까지
  --json          결과를 JSON으로
```

경로 없이 부르면 실행 환경(판·플랫폼·BLAS·스레드), 데이터 파일·워크파일·방정식 파일·보고서 폴더면 그 요약.

## equion new · equion convert

```python
helptext("new", "--help")
helptext("convert", "--help")
```
<!-- out -->
```text
사용법: equion new [-h] [--template {script,desk}] [--bare] [--force] path

인자:
  path                  만들 폴더

옵션:
  -h, --help            도움말을 보이고 끝낸다
  --template {script,desk}
                        script: 스크립트 예시(기본) · desk: 블록·모형 조립 프로젝트(equion.toml)
  --bare                예시 없이 빈 뼈대만(script)
  --force               비어 있지 않은 폴더에도 쓴다(같은 이름 파일을 덮음)
사용법: equion convert [-h] [--allow-pickle] [--name NAME] src dst

인자:
  src             원본: 레거시 pickle 파일 · .wt/ 번들 · .mmw/ · 데이터 파일
  dst             만들 워크파일 경로(.eqw가 붙는다)

옵션:
  -h, --help      도움말을 보이고 끝낸다
  --allow-pickle  레거시 pickle을 연다(열 때 코드가 실행될 수 있음 — 믿을 수 있는 파일만)
  --name NAME     워크파일 이름
```

## equion assemble · equion ident

프로젝트 폴더(`equion.toml` — [파일 형식](formats.md#프로젝트equiontoml))에서 씁니다. 예제 프로젝트는 `equion new 폴더 --template desk`.

```python
helptext("assemble", "--help")
helptext("ident", "--help")
```
<!-- out -->
```text
사용법: equion assemble [-h] [--project 폴더] [--json] [model]

인자:
  model             모형 또는 블록 이름(기본: equion.toml [hs] model)

옵션:
  -h, --help        도움말을 보이고 끝낸다
  --project, -p 폴더  프로젝트 폴더(기본: 지금 폴더)
  --json            결과를 JSON으로
사용법: equion ident [-h] [--check] [--range S:E] [--tol TOL] [--strict] [--project 폴더] [--json] part

인자:
  part              항등식 이름 블록:목표(예: demand:Y)

옵션:
  -h, --help        도움말을 보이고 끝낸다
  --check           실측으로 좌변·우변을 계산해 견준다
  --range S:E       검사 구간(기본: 자료 전체)
  --tol TOL         허용오차(|차이| ≤ tol·max(1,|좌변|), 기본 1e-6)
  --strict          어긋나면 실패(종료 코드 3)로 본다
  --project, -p 폴더  프로젝트 폴더(기본: 지금 폴더)
  --json            결과를 JSON으로
```

`assemble`은 계산 없이 모형(또는 블록 하나)의 구조를 봅니다 — 조립(모형 안의 모형·블록·뺀 식), 내생·외생과 외생 자료의 끝, 블록 사이 연결,
풀이 블록, 문제(한 모형에 같은 목표변수가 둘 · 자료에도 없고 어떤 식도 정하지 않는 변수 · 블록 파일의 문법 오류 — 파일:줄과 함께).
문제가 있으면 종료 코드 3입니다. `ident`는 항등식 하나를 보이고(쓰는 모형 포함), `--check`면 실측으로 좌변과 우변을 계산해 견줍니다
(어긋나도 0, `--strict`면 3).

## equion data

자료 정의와 자료 회차를 쓰는 프로젝트(`[data] series` — [파일 형식](formats.md#자료-정의seriestomlderivedtxt와-자료-회차workdata))에서 씁니다.

```python
helptext("data", "--help")
helptext("data", "add", "--help")
```
<!-- out -->
```text
사용법: equion data [-h] 동작 ...

인자:
  동작
    list      자료 회차 목록(* 지금 회차)
    add       원자료 파일을 DATA/raw/에 넣는다(받은 그대로 — --source로 출처를 그 파일로)
    build     원자료를 정의대로 읽어 새 자료 회차를 만든다(같은 내용이면 만들지 않음)
    use       지금 자료 회차를 바꾼다(equion.toml [data] vintage)
    diff      두 회차의 차이 — 새·없어진 시리즈, 새 기간·개정
    impact    회차를 바꾸면 영향받는 식·모형(다시 계산하지 않음)

옵션:
  -h, --help  도움말을 보이고 끝낸다
사용법: equion data add [-h] [--project 폴더] [--json] [--source 출처] [--as 이름] [--note 메모] file

인자:
  file              넣을 파일(csv·xlsx·xls)

옵션:
  -h, --help        도움말을 보이고 끝낸다
  --project, -p 폴더  프로젝트 폴더(기본: 지금 폴더)
  --json            결과를 JSON으로
  --source 출처       series.toml의 [source.출처]가 이 파일을 읽게(틀이 맞을 때만)
  --as 이름           DATA/raw/에 둘 이름(기본: 파일 이름)
  --note 메모         출처 메모(옆 파일 *.source.toml에)
```

| 동작 | 하는 일 | 종료 코드 |
|---|---|---|
| `list` | 회차 목록 — `*`가 지금 회차 | 0 |
| `add 파일 [--source 이름]` | 원자료를 `DATA/raw/`에 넣는다. `--source`면 그 틀로 먼저 읽어 보고 맞을 때만 넣고 출처를 고친다 | 틀이 맞지 않으면 3(아무것도 바꾸지 않음) |
| `build [--use]` | 정의대로 새 회차를 만든다 — 같은 내용이면 만들지 않고 그 회차를 알린다. 지금 회차는 `--use`일 때만 바뀐다 | 정의·원자료 문제면 3 |
| `use 회차` | 지금 회차를 바꾼다(`equion.toml [data] vintage`, 주석은 그대로) | 없는 회차면 3 |
| `diff [A B]` | 두 회차의 차이 — 새·없어진 시리즈, 시리즈마다 새 기간과 개정(처음·끝 기간, 최대 차이%). 기본은 지금 회차 → 가장 새 회차 | 0 |
| `impact [A B]` | 바뀐 시리즈를 쓰는 식과 모형 — 다시 계산하지는 않는다 | 0 |

자료 파일 하나(`[data] file`)를 쓰는 프로젝트에서는 3입니다. 흐름은 [R49](../howto/data.md#r49-원자료에서-자료-회차로--넣기만들기차이바꾸기).

## 환경변수

| 이름 | 뜻 |
|---|---|
| `EQUION_PARAMS` | 스크립트 매개변수 JSON(`--set`이 그 위에 덮는다). 옛 이름 `MACROMODEL_PARAMS`도 읽는다 |
| `EQUION_THREADS` | `--threads`가 다시 실행할 때 쓴다(직접 둘 필요 없음) |
| `PYTHONIOENCODING` | 화면 출력 인코딩. 한글을 못 쓰는 출력(영문 Windows 파이프)에서도 Equion은 멈추지 않고 `\uXXXX`로 바꿔 쓴다 |

관련: [파일 형식 — 보고서 폴더·manifest](formats.md) · [명령줄 레시피](../howto/cli.md)
