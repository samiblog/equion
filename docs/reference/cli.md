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
    sim       전망·시나리오를 풀고 기록을 남긴다(가정 세트·보정항·시나리오 파일)
    propose   제안 — 파일을 바꾸기 전에 보여 주기(만들기·목록·보기·적용·버림)
    export    기록의 값·값의 종류·출처를 엑셀로
    work      작업 기록 — 목록·보기·고정·메모·정리
    history   바뀜 기록 — 정의 파일이 누가·언제·어떻게 바뀌었나, 되돌리기
    an        분석 — 등록부의 분석 하나 = 기록 하나(an:) · 목록·남기기
    note      노트 — ```equion 블록을 실행해 결과 구역을 채운다 · 검사
    report    보고서 — 결과만 보내기(명령 블록 없이) · 검사 · 새 기록으로 바꾸기

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

## 작업 명령 — est · adopt · compare · hs · sim

프로젝트 폴더에서 씁니다. 계산은 할 때마다 작업 기록(`work/<종류>/<이름>/` — [파일 형식](formats.md#작업-기록work))을 남기고, 출력은 짧은 글
(기본 — 끝 줄에 기록 이름) 또는 `--json`입니다. 없는 부품·기록, 이름 겹침, 조립 문제는 종료 코드 3입니다.

```python
helptext("est", "--help")
helptext("hs", "--help")
helptext("sim", "--help")
```
<!-- out -->
```text
사용법: equion est [-h] [--project 폴더] [--json] [--as 이름] [--for 부품] [--method {auto,ls,tsls}] [--smpl S:E]
                [--sim] [--cov COV] [--adopted] [--adopt {never,if_pass,all}]
                [부품|식]

인자:
  부품|식                  부품 블록:목표(블록 파일의 그 줄) 또는 식 글자(예: "CN c Y CN(-1)") — --adopted면 모형·블록

옵션:
  -h, --help            도움말을 보이고 끝낸다
  --project, -p 폴더      프로젝트 폴더(기본: 지금 폴더)
  --json                결과를 JSON으로
  --as 이름               기록 이름(기본: 목표변수_0001 …)
  --for 부품              어느 부품의 후보인지(목표가 같은 식이 여럿일 때)
  --method {auto,ls,tsls}
                        추정법(기본 auto — @inst가 있으면 tsls)
  --smpl S:E            표본(상대 기간 가능 — 1990Q1:last)
  --sim                 식 하나의 동태 모의([hs] range, 다른 변수는 실측)와 RMSPE
  --cov COV             계수 공분산(white · hac …)
  --adopted             모형(기본 [hs] model)의 추정식을 모두 지금 자료로 다시 추정
  --adopt {never,if_pass,all}
                        --adopted의 채택 정책(기본 never — 기록만, if_pass — 판단 기준을 통과한 식만)
사용법: equion hs [-h] [--project 폴더] [--json] [--range S:E] [--mode {dynamic,static,fit}] [--swap 부품=값]
               [--vs hs:이름] [--as 이름] [--replay hs:이름]
               [모형|블록]

인자:
  모형|블록                 모형 또는 블록(기본: [hs] model)

옵션:
  -h, --help            도움말을 보이고 끝낸다
  --project, -p 폴더      프로젝트 폴더(기본: 지금 폴더)
  --json                결과를 JSON으로
  --range S:E           구간(기본: [hs] range — 상대 기간 가능)
  --mode {dynamic,static,fit}
                        풀이 방식(기본: [hs] mode)
  --swap 부품=값           파일을 바꾸지 않고 바꿔 끼우기 — 값은 est:기록(그 계수) 또는 식 글자(여러 번)
  --vs hs:이름            견줄 HS 기록 — 변수별 RMSPE 전후
  --as 이름               기록 이름(기본 hs_0001 …)
  --replay hs:이름        그 기록의 조립 명세로 그대로 다시(지금 파일과 무관)
사용법: equion sim [-h] [--project 폴더] [--json] [--model 모형] [--range S:E] [--vintage 회차] [--vs sim:이름]
                [--as 이름] [--mode {dynamic,static}]
                [시나리오 ...]

인자:
  시나리오                  base(기준선) 또는 SCENARIOS/의 이름(여럿이면 하나씩, 기본 base)

옵션:
  -h, --help            도움말을 보이고 끝낸다
  --project, -p 폴더      프로젝트 폴더(기본: 지금 폴더)
  --json                결과를 JSON으로
  --model 모형            모형(기본: 시나리오 → [forecast] → [hs] model)
  --range S:E           전망 구간(기본 [forecast] range, 없으면 next:8)
  --vintage 회차          다른 자료 회차로(지금 회차는 그대로)
  --vs sim:이름           견줄 전망 기록 — 연간 증가율 전후
  --as 이름               기록 이름(시나리오가 하나일 때, 기본 연-월_시나리오)
  --mode {dynamic,static}
                        풀이 방식(기본 [forecast] mode, 없으면 dynamic)
```

| 명령 | 하는 일 |
|---|---|
| `est 부품` · `est "식" [--as 이름] [--for 부품]` | 식 하나 추정 → 계수·적합 통계·진단·판단 기준(`[criteria]`)·알아서 한 것. 식 글자는 목표가 같은 부품의 후보가 된다. `--sim`이면 식 하나의 동태 모의(다른 변수는 실측)와 RMSPE |
| `est --adopted [모형] --adopt never·if_pass·all` | 모형의 추정식을 블록 파일 글자 그대로 지금 자료로 다시 추정(새 기록) — `if_pass`는 기준을 통과한 식만 새 계수로 채택하고 걸린 식은 옛 계수(표시) |
| `adopt est:이름 [--part 부품]` | 채택 — 채택표와 블록 파일의 그 줄을 고치고 바뀜 기록에. 그 뒤 모형은 이 계수로 푼다 |
| `compare 기록… · --target 변수 · --part 부품` | 추정 후보 표(종속변수·표본이 다르면 경고) 또는 HS 기록의 변수별 RMSPE |
| `hs [모형·블록] [--swap 부품=est:이름·"식"] [--vs hs:이름]` | 과거 재현 기록 — 바꿔 끼우기(파일은 그대로, 기록이면 그 계수)·전후 비교 |
| `hs --replay hs:이름` | 그 기록의 조립 명세로 그때 그대로 다시(지금 파일·회차와 무관) — 원래 해와 견준 결과를 새 기록에 |
| `sim [시나리오…] [--range next:8] [--vintage 회차] [--vs sim:이름]` | 전망·시나리오 기록 — 가정 세트·보정항·시나리오 파일로, 시나리오면 기준선과의 차이도 |

## 제안·내보내기·기록 — propose · export · work · history

```python
helptext("propose", "new", "--help")
helptext("export", "--help")
helptext("work", "--help")
helptext("history", "--help")
```
<!-- out -->
```text
사용법: equion propose new [-h] [--project 폴더] [--json] [--title TITLE] [--why WHY] [--part 부품=값]
                        [--file 경로=새파일] [--preview 기록]
                        [이름]

인자:
  이름                제안 이름(기본 p1, p2 …)

옵션:
  -h, --help        도움말을 보이고 끝낸다
  --project, -p 폴더  프로젝트 폴더(기본: 지금 폴더)
  --json            결과를 JSON으로
  --title TITLE     제목
  --why WHY         까닭(근거 기록 이름을 넣는다)
  --part 부품=값       식 바꾸기 — 값은 est:기록(그 식으로 바꾸고 채택) 또는 식 글자
  --file 경로=새파일     파일 통째로 — 프로젝트 안 경로=새 내용 파일
  --preview 기록      미리 계산한 기록(hs:… · sim:… · est:…)
사용법: equion export [-h] [--project 폴더] [--json] --xlsx 파일 기록 [기록 ...]

인자:
  기록                est:… · hs:… · sim:… · data:회차

옵션:
  -h, --help        도움말을 보이고 끝낸다
  --project, -p 폴더  프로젝트 폴더(기본: 지금 폴더)
  --json            결과를 JSON으로
  --xlsx 파일         만들 엑셀 파일(.xlsx — 프로젝트 기준 경로)
사용법: equion work [-h] 동작 ...

인자:
  동작
    list      기록 목록(새것이 아래)
    show      기록 하나 — 짧은 글(--md면 카드 summary.md)
    pin       고정(정리에서 빠진다)
    unpin     고정 풀기
    memo      메모(기록은 그대로, marks.json에)
    clean     정리 — 고정·채택·참조되지 않은 기록(기본은 목록만, --yes면 지움)

옵션:
  -h, --help  도움말을 보이고 끝낸다
사용법: equion history [-h] 동작 ...

인자:
  동작
    list      바뀜 목록(새것이 아래)
    show      바뀜 하나 — 파일과 차이
    revert    그 바뀜 앞의 내용으로 되돌린다(이것도 바뀜 기록에 남는다)

옵션:
  -h, --help  도움말을 보이고 끝낸다
```

`propose new`는 파일을 바꾸지 않고 바꿀 내용·까닭·미리 계산한 기록을 `work/proposals/<이름>/`에 남기고, `propose apply`가 바꿉니다(만든 뒤 그 파일이
바뀌었으면 낡음 — `--force`). `propose drop`은 버리되 기록은 남깁니다. `work clean`은 고정·채택·다른 기록이나 제안이 가리키는 기록을 빼고 지울
목록만 보이고, `--yes`일 때 지웁니다. `history`는 정의 파일의 바뀜(누가·명령·전후·차이 — 명령 밖의 고침은 '바깥')을 보이고 되돌립니다.

## 분석·노트·보고서 — an · note · report

분석의 이름·대상·옵션·도움말은 등록부(`eqn.registry`)에서 나옵니다 — 분석 하나 = 명령 하나 = 기록 하나(`an:`) = md 카드 하나(D37).

```python
helptext("an", "list")
helptext("an", "unitroot", "--help")
helptext("note", "run", "--help")
helptext("report", "add", "--help")
```
<!-- out -->
```text

사용법: equion an unitroot [-h] [--project 폴더] [--json] [--trend {n,c,ct}] [--lags LAGS] [--ic {bic,aic}]
                        [--maxlag MAXLAG] [--smpl S:E] [--as 이름] [--note 노트]
                        대상

단위근: ADF(귀무: 단위근)와 KPSS(귀무: 정상)를 함께 — 둘이 다르면 '엇갈림'. 결과: 시리즈 × ADF·KPSS·판단 표

인자:
  대상                시리즈 · 묶음 · 식(log(Y) 등)

옵션:
  -h, --help        도움말을 보이고 끝낸다
  --project, -p 폴더  프로젝트 폴더(기본: 지금 폴더)
  --json            결과를 JSON으로
  --trend {n,c,ct}  결정항 — n 없음 · c 상수 · ct 상수+추세 (기본 c)
  --lags LAGS       ADF 시차 수(없으면 정보기준으로)
  --ic {bic,aic}    시차를 고르는 정보기준 (기본 bic)
  --maxlag MAXLAG   고를 때의 최대 시차
  --smpl S:E        표본(상대 기간 가능 — 1990Q1:last)
  --as 이름           기록 이름(기본 unitroot_0001 …)
  --note 노트         그 노트 끝에 명령 블록과 결과 구역을 더한다

예: equion an unitroot core --trend ct
사용법: equion note run [-h] [--project 폴더] [--json] [--block n] [--stale] [--force] 노트

인자:
  노트

옵션:
  -h, --help        도움말을 보이고 끝낸다
  --project, -p 폴더  프로젝트 폴더(기본: 지금 폴더)
  --json            결과를 JSON으로
  --block n         그 블록만(Python 블록은 이것으로만 돈다)
  --stale           낡았거나 아직 실행 안 한 블록만
  --force           손으로 고친 결과 구역도 덮는다
사용법: equion report add [-h] [--project 폴더] [--json] [--rows A,B] [--show {level,qoq,yoy,diff}] [--annual]
                       [--digits n] [--title TITLE] [--chart] [--under 제목]
                       보고서 기록[#표]

인자:
  보고서
  기록[#표]                sim:… · hs:… · est:… · an:…#2(분석의 표 번호)

옵션:
  -h, --help            도움말을 보이고 끝낸다
  --project, -p 폴더      프로젝트 폴더(기본: 지금 폴더)
  --json                결과를 JSON으로
  --rows A,B            행(시리즈·변수) — 쉼표로
  --show {level,qoq,yoy,diff}
                        보이기(전망 — 수준·전기비·전년동기비·기준선 대비)
  --annual              연간(전망)
  --digits n            소수점 자리(기본: 전망 1 · 그 밖 3)
  --title TITLE         표 제목(번호는 저절로)
  --chart               차트도(자료는 보고서 옆 _data/로 복사)
  --under 제목            이 제목 아래 끝에(예: "## 전망") — 없으면 맨 끝
```

| 명령 | 하는 일 | 종료 코드 |
|---|---|---|
| `an <분석> <대상> [옵션] [--smpl S:E] [--as 이름] [--note 노트]` | 분석 하나 → 짧은 글 + 기록. `--note`면 그 노트 끝에 명령 블록과 결과 구역 | 대상·옵션 문제 3 |
| `an keep an:이름 [--as 이름] [--replace]` | 계절조정 → `series.toml`의 새 시리즈(`made_by`), 파생 → `derived.txt` 한 줄, ECM·VAR·VECM·시스템 → 식 후보(`est:` — 계수 그대로) | 보는 분석이면 3 |
| `note run 노트 [--block n] [--stale] [--force]` | 블록을 실행해 결과 구역을 채운다(블록마다 새 기록). 손으로 고친 구역은 `--force`일 때만 덮는다 | 블록에 오류·허용 안 된 명령이 있으면 1 |
| `note check 노트…` | 실행하지 않고 — 실행 안 함·없는 기록·낡음·손으로 고침·허용 안 된 명령 | 허용 안 된 명령이 있으면 3 |
| `report new 이름 [--title] [--from 보고서]` | 새 보고서(틀) — `--from`이면 복사하고 구역마다 바꿔 낄 기록을 제안 | 0 |
| `report add 보고서 기록[#표] [--rows] [--show level·qoq·yoy·diff] [--annual] [--digits] [--chart] [--under 제목]` | 보고서로 보내기 — 결과만(명령 블록 없이) | 없는 행·기록 3 |
| `report check 보고서` · `report update 보고서 [--region n] [--to 기록] [--dry-run] [--force]` | 구역마다 더 새 기록·낡음·손으로 고침 · 같은 모양으로 다시 만들어 차이를 보이고 적용(손으로 고친 구역은 고친 곳을 보이고 `--force`일 때만) | 0 |

## 환경변수

| 이름 | 뜻 |
|---|---|
| `EQUION_PARAMS` | 스크립트 매개변수 JSON(`--set`이 그 위에 덮는다). 옛 이름 `MACROMODEL_PARAMS`도 읽는다 |
| `EQUION_THREADS` | `--threads`가 다시 실행할 때 쓴다(직접 둘 필요 없음) |
| `EQUION_WHO` | 작업 기록·바뀜 기록의 '누가'(`desk`·`script` …) — 없으면 Claude Code 안(`CLAUDECODE`)은 `claude`, 명령줄은 `terminal` |
| `PYTHONIOENCODING` | 화면 출력 인코딩. 한글을 못 쓰는 출력(영문 Windows 파이프)에서도 Equion은 멈추지 않고 `\uXXXX`로 바꿔 쓴다 |

관련: [파일 형식 — 보고서 폴더·manifest](formats.md) · [명령줄 레시피](../howto/cli.md)
