# 파일 형식

Equion이 읽고 쓰는 파일. 아래 코드는 실제로 파일을 만들어 그 구성을 찍으므로, 이 문서는 코드와 어긋나지 않습니다.

## 데이터 파일(읽기)

| 형식 | 확장자 | 규칙 |
|---|---|---|
| 엑셀 | `.xlsx` · `.xls` | 첫 열이 시점(날짜 또는 `2000Q1`·`2000M1`·`2000` 표기), 첫 행이 시리즈 이름. 시트는 `sheet=` |
| CSV | `.csv` | 같은 규칙. UTF-8(BOM 무관) — cp949는 경고하고 읽는다 |
| Parquet | `.parquet` | 선택 기능(`pip install equion[parquet]`) |

- 시리즈 이름은 대소문자를 가리지 않습니다(`cpi`와 `CPI`는 같은 시리즈). 대소문자만 다른 열이 둘 있으면 열 때 경고합니다.
- 주기는 시점에서 추론합니다(안 되면 `freq=`). 숫자가 아닌 칸은 결측입니다.
- 읽는 법: [데이터 레시피](../howto/data.md).

## 방정식 파일(`.txt`)

한 줄에 식 하나, `#` 뒤는 주석. UTF-8(BOM 무관), cp949는 경고하고 읽습니다. 문법은 [방정식 문법](../explain/equations.md).

```text
# 소비함수 — 추정식(최상위 '=' 없음): 목표변수 c 회귀변수...
CN c Y CN(-1)
# 비선형 추정식('='와 c(n))
I = c(1) + c(2)*Y(-1) + c(3)*R
# 항등식('='만)
Y = CN + I + G
@def RG = Y/Y(-1) - 1        # 매크로: 뒤 줄의 RG를 식으로 바꾼다
```

## 프로젝트(`equion.toml`)

프로젝트는 폴더 하나입니다 — `equion.toml`이 자료와 블록(방정식 파일 하나 = 블록 하나)을 이름으로 묶고, 모형은 블록과 다른 모형을
이름으로 끼워 조립합니다(D32). 여는 법은 `eqn.project(폴더)`, 검사는 `equion assemble`, 예제는 `equion new 폴더 --template desk`.

```toml
[project]
name = "demo"
format = "equion-project"
format_version = 1

[data]                            # 자료 정의와 회차(아래 절) — 또는 자료 파일 하나: file = "DATA/data.csv"
series = "DATA/series.toml"
derived = "DATA/derived.txt"
freq = "Q"
vintage = "d2026-11a"             # 지금 자료 회차 — equion data use가 고친다

[block]                           # 이름 = "파일" 또는 { file = …, desc = … }
demand  = { file = "EQUATIONS/demand.txt",  desc = "수요" }
price   = { file = "EQUATIONS/price.txt",   desc = "물가" }
finance = { file = "EQUATIONS/finance.txt", desc = "금융" }

[model.core]
blocks = ["demand"]

[model.main]
include = ["core"]                # 모형 안에 모형
blocks = ["price", "finance"]

[model.main_fixrl]
include = ["main"]
exclude = ["finance:RL"]          # 뺀 식의 목표는 외생(실측)

[group]                           # 묶음 — 여러 시리즈를 이름 하나로
core = { series = ["Y", "CN", "I"], desc = "핵심 수요" }

[criteria]                        # 판단 기준 — 추정 기록의 '기준'(통과·걸러짐과 까닭) · est --adopted --adopt if_pass
alpha = 0.05                      # 진단 유의수준
tests = ["lm", "reset"]           # 기준에 넣는 진단: lm · white · bp · lb · arch · jb · reset (p < alpha면 걸러짐)
t_min = 1.0                       # (선택) 상수항 밖 계수의 |t| 하한

[criteria.signs]                  # 기대 부호 — 부품마다 { 항 = "+" · "-" }
"demand:CN" = { Y = "+" }

[hs]                              # 과거 재현 기본값
model = "main"
range = "2005Q1:last"             # last = 자료의 마지막 기(새 회차로 바꾸면 따라 늘어난다)
mode = "dynamic"                  # dynamic · static · fit

[forecast]                        # 전망 기본값 — equion sim
model = "main"
range = "next:8"                  # 자료 끝 다음 기부터 8기
assume = "base"                   # 가정 세트 ASSUMPTIONS/base.csv
addfactors = "base"               # 보정항 ADDFACTORS/base.toml
fill = "last"                     # 가정이 없는 외생: last · growth · trend · none
```

| 규칙 | 내용 |
|---|---|
| 자료 | `[data]`는 둘 중 하나 — `file`(첫 열이 날짜인 자료 파일 하나) 또는 `series`·`freq`(자료 정의와 회차, 아래 절). 둘을 함께 쓰면 오류 |
| 구간 표기 | `시작:끝`의 시작·끝은 기간(`2005Q1`) · `first` · `last` · `last-N` · `first+N`, 또는 `next:N`(자료 끝 다음 기부터 N기). `last`는 자료 시리즈 중 값이 있는 마지막 기 |
| 이름 | 블록·모형·묶음은 영문으로 시작하고 영문·숫자·`_`만(한글은 `desc`). 블록과 모형은 이름이 겹칠 수 없다 |
| 부품 이름 | 블록 파일의 식 한 줄은 `블록:목표변수`(예: `demand:CN`). 목표변수는 좌변의 첫 변수, 한 블록에 같은 목표는 하나 |
| 내생·외생 | 적지 않는다 — 모형에서 어떤 식의 목표면 내생, 아니면 외생 |
| 조립 문제 | 한 모형에 같은 목표가 둘, 자료에도 없고 어떤 식도 정하지 않는 변수, 순환 include, 없는 블록·모형·식(exclude) |
| 블록 파일 | 방정식 파일과 같은 문법(위). 줄 끝 `#` 뒤는 그 식의 설명으로 보인다 |
| 형식 판 | `format_version`이 이 equion이 읽는 판보다 크면 오류(새 판으로). 모르는 표는 경고하고 쓰지 않는다 |

## 자료 정의(`series.toml`·`derived.txt`)와 자료 회차(`work/data/`)

자료는 세 층입니다(D34) — **원자료**(`DATA/raw/`, 받은 그대로 — 고치지 않는다) → **정의**(어느 파일의 어느 열을 어떻게 읽어 어떤 시리즈로)
→ **회차**(정의대로 만든 자료, `work/data/<회차>/`). 회차는 '자료 만들기'(`equion data build` · `p.data_build()`)로만 생기고 고치지 않습니다.
만들어도 지금 회차는 그대로이고, '이 회차로 바꾸기'(`equion data use` · `p.data_use()`)가 `equion.toml`의 `[data] vintage`를 고칩니다.
같은 원자료·정의로 다시 만들면 내용이 같아 새 회차를 만들지 않습니다. 정의 파일을 프로그램이 고칠 때(`data use`·`data add --source`)는
주석과 순서를 그대로 둡니다.

```toml
# DATA/series.toml
[source.na]                       # 불러오기 틀 — 원자료 파일 하나를 어떻게 읽는지
file = "DATA/raw/na.xlsx"
sheet = "분기"                    # 시트 이름 또는 번호(1부터, 기본 첫 시트)
header_row = 2                    # 열 이름 줄(1부터, 기본 1)
unit_row = 3                      # 단위 줄(선택) — 시리즈의 unit이 없으면 이 칸
time_col = "A"                    # 시점 열 — 열 이름 · 엑셀 열 글자 · 번호(기본 첫 열)
missing = ["–", "…"]              # 결측으로 볼 표시(빈 칸은 늘 결측)
thousands = ","                   # 천 단위 구분 글자

[series.CN]                       # 시리즈 하나 — 이름은 영문(한글은 desc)
from = "na:민간소비"               # 원자료이름:열(열 이름은 대소문자 무시)
unit = "조원"
desc = "민간소비"

[series.CNSA]
from = "na:CNNSA"
seas = { method = "stl", model = "multiplicative" }   # 계절조정 — "stl" · "classical", additive · multiplicative

[series.IPQ]
from = "monthly:IP"
convert = "mean"                  # 원자료 주기 ≠ 자료 주기면 꼭 — 낮은 주기로 mean·sum·first·last·max·min, 높은 주기로 constant·split·linear·denton
```

| 키 | 내용 |
|---|---|
| `[source.이름]` | `file`(csv·xlsx·xls) · `sheet` · `header_row` · `unit_row` · `time_col` · `missing` · `thousands` · `freq`(시점에서 추론이 안 될 때) · `desc` |
| 시점 꼴 | `2003Q4` · `2003M10` · `2003-10` · `2003` · ISO 날짜, 그리고 `2003.Q4` · `2003 Q4` · `2003년 4분기` · `2003년 4/4분기` · `2003년 10월` · `2003.10` |
| 칸 | 천 단위 구분은 `thousands`, 괄호 숫자 `(12)`는 음수. 결측 표시와 숫자가 아닌 칸은 결측으로 보고 칸 위치(`D7`)와 함께 '알아서 한 것'에 적는다 |
| `[series.이름]` | `from`(꼭) · `convert` · `denton`(denton의 conversion, 기본 sum) · `seas` · `scale`(곱할 수) · `fill = "linear"`(안쪽 결측 선형 보간) · `unit` · `desc` |
| 하는 순서 | 읽기 → 주기 변환 → 배율 → 채움 → 계절조정 → (모든 시리즈를 모은 뒤) 파생식 |
| `derived.txt` | 한 줄에 `이름 = 식`(방정식 문법 — `PI = 100*(P/P(-4) - 1)`), `#` 뒤는 설명. 위에서부터 차례로, 앞 줄의 파생 시리즈를 쓸 수 있다 |
| 문제 | 없는 원자료·열, 틀이 맞지 않음, 주기 변환 빠짐, 같은 이름, 함수 이름·`C` 같은 쓸 수 없는 이름, 파생식 오류 — 위치(`series.toml [series.X]` · `derived.txt:3` · 칸 `A3`)와 함께 모아서 알린다 |
| 원자료 넣기 | `equion data add 파일` — `DATA/raw/`에 복사(같은 내용이면 넣지 않고, 같은 이름·다른 내용이면 `_YYYYMMDD`를 붙여 나란히), 옆에 `파일.source.toml`(받은 이름·때·해시·메모). `--source 이름`이면 그 틀로 먼저 읽어 보고 시리즈가 쓰는 열이 다 있고 주기가 같을 때만 넣고 `[source.이름] file`을 고친다 |

회차 폴더는 이렇습니다(아래 코드는 예제 프로젝트를 실제로 만들어 찍습니다).

```python
import json
import os
from pathlib import Path

import pandas as pd
import equion as eqn

p = eqn.Project.create("fmt_prj", force=True)    # 원자료·정의를 쓰고 첫 회차를 만들어 지금 회차로
v = Path(p.root, "work", "data", p.vintage)
print(sorted(os.listdir(v)))
build = json.loads(Path(v, "build.json").read_text(encoding="utf-8"))
print(sorted(build))
flags = pd.read_csv(Path(v, "flags.csv"), index_col=0)
print(flags.loc[["1970Q1", "2000Q1"], ["CN", "RL", "CNSA", "IPQ", "PI"]])
```
<!-- out -->
```text
[fmt_prj] 자료 회차 d2026-11a를 만들었습니다
[fmt_prj] 지금 자료 회차: d2026-11a
['build.json', 'flags.csv', 'meta.json', 'series.csv', 'summary.md']
['content_sha256', 'created', 'definitions', 'equion', 'format', 'format_version', 'freq', 'id', 'implicit', 'n_series', 'series', 'sources', 'span']
            CN       RL         CNSA          IPQ       PI
period
1970Q1  actual  missing  transformed      missing  missing
2000Q1  actual   actual  transformed  transformed  derived
```

| 파일 | 내용 |
|---|---|
| `series.csv` | 값 — 첫 열 `period`(기간 라벨), 열마다 시리즈. 빈 칸은 결측 |
| `flags.csv` | 값의 종류 — `actual`(실측) · `transformed`(주기 변환·배율·계절조정) · `filled`(채움) · `derived`(파생) · `missing`(결측) |
| `meta.json` | 시리즈마다 출처(`원자료:열` 또는 식)·단위·설명·변환 |
| `build.json` | `format: equion-data-vintage` · `format_version` · 회차 이름 · 만든 때 · equion 판 · 원자료 파일과 해시 · 정의 파일 해시 · 내용 해시(같은 회차 알아보기) · 알아서 한 것 |
| `summary.md` | 사람이 읽는 요약 — 시리즈마다 출처·구간·값 수·설명, 알아서 한 것 |

회차 이름은 `d연도-월` 뒤에 글자(`d2026-11a`, 같은 달 둘째는 `b`)입니다. `work/`는 다시 만들 수 있는 산출물이라 git에서 뺍니다(예제의 `.gitignore`).

## 작업 기록(`work/`)

계산(`est`·`hs`·`sim`)은 할 때마다 `work/<종류>/<이름>/`에 기록을 하나 남기고 `work/log.jsonl`에 한 줄을 더합니다(D33). 기록은 고치지
않습니다 — 다시 계산하면 새 기록이고, 같은 이름은 거부합니다. 고정·메모는 `work/marks.json`에만 적습니다. 기록 이름은 `종류:이름`
(`est:cons_c5` · `hs:hs_0003` · `sim:2026-11_base`)이고 명령줄·Python·Desk가 같은 이름을 씁니다.

```python
p = eqn.Project.create("rec_prj", force=True)
e = p.est("CN c Y(-1) CN(-1)", as_name="cons_c3", sim=True)
h = p.hs("main", record=True, swap={"demand:CN": "est:cons_c3"})
print(sorted(os.listdir(e.record.path)))
print(sorted(os.listdir(h.record.path)))
asm = json.loads(Path(h.record.path, "assembly.json").read_text(encoding="utf-8"))
print(sorted(asm))
print([(x["id"], x.get("source")) for x in asm["parts"]])
print(sorted(json.loads(Path(p.root, "work", "log.jsonl").read_text(encoding="utf-8").splitlines()[-1])))
```
<!-- out -->
```text
[rec_prj] 자료 회차 d2026-11a를 만들었습니다
[rec_prj] 지금 자료 회차: d2026-11a
[rec_prj] 열기 series.csv — 분기(Quarterly) 1970Q1~2019Q4 · 시리즈 13
[main] 채택 기록 없이 지금 자료로 추정: demand:I, price:P, finance:RL, finance:M2
[main] baseline(_0) dynamic 2005Q1~2019Q4: 정상 60 · 일부식 제외 0 · 실패대체 0 · 실패 0
['coefs.csv', 'record.json', 'series.csv', 'summary.md']
['assembly.json', 'record.json', 'series.csv', 'solved.csv', 'stats.csv', 'status.csv', 'summary.md']
['data', 'equion', 'files', 'format', 'format_version', 'mode', 'model', 'options', 'parts', 'range', 'swaps']
[('demand:CN', 'swap:est:cons_c3'), ('demand:I', 'estimated'), ('demand:Y', None), ('price:P', 'estimated'), ('finance:RL', 'estimated'), ('finance:M2', 'estimated')]
['command', 'counts', 'created', 'id', 'kind', 'metric', 'path', 'target', 'who']
```

| 종류 | 파일 |
|---|---|
| 공통 | `record.json`(`format: equion-record` · `format_version` · 이름 · 만든 때 · 누가 · 명령 그대로 · 대상 · 자료(회차 이름·내용 해시) · equion 판 · 알아서 한 것) · `summary.md`(카드 — 표와 같은 폴더 CSV의 vega-lite 차트) |
| `est` | `coefs.csv`(계수·표준오차·t·p) · `series.csv`(실측·적합·잔차, `--sim`이면 목표변수의 단독 모의). `record.json`에 식 글자·펼친 식·표본·통계·진단·판단 기준·식 직렬화(계수 그대로 — 채택·바꿔 끼우기에 쓴다) |
| `hs` | `assembly.json`(조립 명세) · `stats.csv`(변수별 RMSPE·MAE…) · `solved.csv`(해) · `status.csv`(기간 상태) · `series.csv`(해와 실측) |
| `sim` | `assembly.json` · `levels.csv`(전망 앞 2년의 실측 + 전망) · `flags.csv`(값의 종류: 실측·해·가정·채움·결측) · `growth.csv`(전기비·전년동기비) · `annual.csv`(연간 평균·증가율) · `addfactors.csv`(식마다 보정항) · `diff.csv`(시나리오 − 기준선) |
| 조립 명세 | `format: equion-assembly` — 모형·구간·방식·선택지, 자료(회차와 내용 해시 또는 자료 파일 해시), 식마다 글자·출처(`adopted:est:…` · `estimated` · `swap:est:…`)·계수, 정의 파일 해시, equion 판. `hs --replay`는 이것만으로 그때 그대로 푼다(자료 해시가 다르면 거부) |
| `log.jsonl` | 한 줄에 기록 하나 — id · created · who(`terminal`·`claude`·`desk`·`python`·`script`) · command · kind · target · path · 핵심 수치 |

'누가'는 환경 변수 `EQUION_WHO`(Desk·스크립트가 정한다), Claude Code 안(`CLAUDECODE`)이면 `claude`, 그 밖은 명령줄 `terminal`·라이브러리 `python`입니다.

## 채택표(`EQUATIONS/adopted.toml`)

식(부품)마다 채택한 추정 기록입니다. 모형을 만들 때 채택 기록이 있고 그 식 글자(펼친 식)가 블록 파일과 같으면 **그 기록의 계수**를 쓰고
다시 추정하지 않습니다(D35). 글자가 다르거나 기록이 없으면 알리고 지금 자료로 추정합니다. `equion adopt est:…`(블록 파일의 그 줄도 그 식으로 —
줄 끝 설명은 그대로)·`est --adopted --adopt if_pass`·`propose apply`가 고칩니다(주석·순서는 그대로).

```toml
# 채택표 — 식(부품)마다 채택한 추정 기록. 모형은 이 계수로 푼다(equion adopt가 고친다)
"demand:CN" = "est:cons_c5"
"price:P" = "est:p_0003"
```

## 가정·보정항·시나리오(`ASSUMPTIONS/`·`ADDFACTORS/`·`SCENARIOS/`)

`equion sim`이 읽습니다(K4). 전망 구간은 `[forecast] range`(없으면 `next:8`)이고, 계산한 값은 실측 자리에 쓰지 않고 기록에만 남깁니다.

| 파일 | 내용 |
|---|---|
| `ASSUMPTIONS/이름.csv` | 외생 가정 경로 — 첫 열 기간, 열마다 시리즈. 전망 구간 안의 값만 쓴다(값의 종류 '가정'). 모형에 없는 변수·전망 앞 기간은 쓰지 않고 알린다. 비는 칸은 `[forecast] fill`(`last`·`growth`·`trend`, 값의 종류 '채움') — `none`이면 비어 있다고 멈춘다 |
| `ADDFACTORS/이름.toml` | `default = "zero"`(적지 않은 식) · `[eq."블록:목표"] rule = "last"`(전망 앞 마지막 잔차) · `"decay"`(+ `half_life`) · `"mean"`(+ `n`, 마지막 n기 평균) · `"zero"`, `values = "ADDFACTORS/이름.csv"`(판단 값 — 열이 부품, 그 칸은 규칙 값을 덮는다) |
| `SCENARIOS/이름.toml` | `desc` · `base`(가정 세트) · `addfactors` · `model`, `[[shock]] var · from · to · pct 또는 value`(외생 경로를 % 또는 수준만큼), `[[addfactor]] eq · from · to · value`(식 보정). 기간은 라벨 또는 `start` · `end` · `start+N` · `end-N`(전망 구간 기준) |

```toml
# SCENARIOS/oil20.toml
desc = "유가 20% 상승"
base = "base"

[[shock]]
var = "POIL"
from = "start"                    # to를 쓰지 않으면 end(전망 끝)까지
pct = 20
```

시나리오는 같은 가정·보정항의 기준선도 함께 풀어 차이(`diff.csv` — 수준 차이와 %)를 적습니다. 시나리오 이름 `base`는 파일이 없어도 됩니다(기준선).

## 제안(`work/proposals/`)·바뀜 기록(`work/history/`)

| 위치 | 내용 |
|---|---|
| `work/proposals/<이름>/` | `proposal.json`(`format: equion-proposal` · 제목 · 까닭 · 만든 때 · 누가 · 명령 · 바꿀 파일과 그때의 해시 · 식 · 미리 계산한 기록 · 상태 open·applied·dropped) · `proposal.md`(카드 — 차이 포함) · `changes/<경로>`(바뀔 파일의 새 내용). 만든 뒤 그 파일이 바뀌면 '낡음' — `apply`는 `--force`일 때만 |
| `work/history/<h번호>/` | `change.json`(`format: equion-change` · 때 · 누가 · 어떻게(명령 그대로 또는 '명령 밖에서 고침') · 메모 · 파일마다 전후 해시 · 되돌린 바뀜) · `before/`·`after/`(전후 사본) · `diff.txt` |
| `work/history/state/` | 지난번에 본 정의 파일의 사본 — 명령 밖의 고침(편집기·Claude의 직접 편집)을 다음 명령 때 '바깥'으로 적는 기준 |

바뀜 기록에 남는 파일은 `equion.toml` · 블록 파일 · `EQUATIONS/adopted.toml` · `DATA/series.toml`·`derived.txt` · `ASSUMPTIONS/` · `ADDFACTORS/` · `SCENARIOS/` · `VIEWS/`입니다.
되돌리기(`history revert`)는 이전 내용으로 다시 쓰는 것이고 그것도 기록에 남습니다.

## 워크파일(`.eqw/` 폴더)

`wf.save("이름")`이 만드는 폴더입니다. 다시 열면(`eqn.wfopen`) 재추정 없이 계수·잔차·모델·시나리오가 그대로 돌아옵니다.

```python
import json
import os
from pathlib import Path

import equion as eqn

wf = eqn.datasets.load("toy_q")
eq = wf.equation("eq_i").ls("I c Y(-1) R")
wf.model("m_toy").merge(eq, "CN c Y CN(-1)").append("Y = CN + I + G")
wf.page("annual", "A")
path = wf.save("demo")
for f in sorted(Path(path).rglob("*")):
    if f.is_file():
        print(f.relative_to(path).as_posix())
man = json.loads(Path(path, "workfile.json").read_text(encoding="utf-8"))
print(sorted(man))
print([(o["type"], o["name"]) for o in man["objects"]])
```
<!-- out -->
```text
[toy_q] 열기 toy_q.csv — 분기(Quarterly) 1970Q1~2019Q4 · 시리즈 10
[eq_i] OLS I — n=199, R²=0.9985
[eq_cn] OLS CN — n=199, R²=0.9999
[annual] 새 워크파일 — 연(Annual) 1970~2019 (50기)
[toy_q] 페이지 annual — 연(Annual) 1970~2019
[annual] 저장 → demo.eqw/pages/annual.eqw (시리즈 0 · 객체 0)
[toy_q] 저장 → demo.eqw (시리즈 10 · 객체 3)
data.npz
pages/annual.eqw/data.npz
pages/annual.eqw/workfile.json
residuals.npz
workfile.json
['engine_version', 'format', 'format_version', 'freq', 'indicators', 'metadata', 'name', 'objects', 'pages', 'saved_at', 'smpl']
[('equation', 'eq_i'), ('model', 'm_toy'), ('equation', 'eq_cn')]
```

| 파일 | 내용 |
|---|---|
| `workfile.json` | 목록: `format: "equion-workfile"` · `format_version`(지금 2) · 주기 · 표본 · 지시자 · 메타데이터 · 객체 · 페이지 |
| `data.npz` | 시리즈 전체(numpy 압축 배열: `values` · `index` · `columns`) — pickle을 쓰지 않아 열 때 코드가 실행되지 않는다 |
| `residuals.npz` | 방정식 잔차 |
| `pages/<이름>.eqw/` | 다른 주기 페이지(같은 구조) |

`workfile.json`의 객체:

| `type` | 담는 것 |
|---|---|
| `equation` | 식(`spec`)과 추정 결과(`saved`: 계수·공분산·통계·추정법) |
| `model` | 방정식 이름 · 항등식 · 시나리오(override·exclude·add-factor·충격·control) · 현재 시나리오 |
| `system` · `var` · `vecm` | 식·추정법·계수 |
| `graph` · `table` | 시리즈·종류·제목·구간 / 표 내용 |

- 열 수 있는 옛 형식: 확장자 `.mmw`와 `format: "macromodel-workfile"`(0.5.0 이전), `format_version` 1(자료가 `data.parquet`).
- 레거시 pickle·`.wt/` 번들은 `equion convert 원본 대상`으로 바꿉니다([명령줄](cli.md#equion-new--equion-convert)).

## HS·풀이 결과 CSV

`r.save(path)`가 쓰는 표. UTF-8(BOM)이라 엑셀에서 한글이 깨지지 않습니다. 경로를 안 주면 `HS/<모델>_<별칭 번호>_results_<시작>_<끝>.csv`(예: `HS/m_toy_0_results_2010Q1_2010Q4.csv`),
폴더 없이 파일 이름만 주면 `HS/` 아래에 씁니다(드라이버의 기준선 위치). 돌려받은 경로를 쓰세요.

```python
import pandas as pd

r = wf.obj("m_toy").solve("2010Q1", "2010Q4")
path = r.save("results/hs.csv")
print(path)
print(list(pd.read_csv(path, nrows=0).columns))
```
<!-- out -->
```text
[m_toy] baseline(_0) dynamic 2010Q1~2010Q4: 정상 4 · 일부식 제외 0 · 실패대체 0 · 실패 0
results/hs.csv
['period', 'time_index', 'status', 'iterations', 'max_resid', 'excluded', 'fallback', 'CN_hs', 'CN_actual', 'CN_error_pct', 'I_hs', 'I_actual', 'I_error_pct', 'Y_hs', 'Y_actual', 'Y_error_pct']
```

열의 뜻은 [출력 표 읽는 법](outputs.md#hs-csvrsavepath).

## 보고서 폴더(`equion run`)

`equion run script.py`는 `out/<실행ID>/`를 만듭니다(실행 ID 기본값은 `날짜-시각_스크립트이름`).

```python
import subprocess
import sys
from pathlib import Path

Path("demo_run.py").write_text(
    "import equion as eqn\n"
    "wf = eqn.datasets.load('toy_q')\n"
    "eq = wf.equation('eq_i').ls('I c Y(-1) R')\n"
    "eqn.show(eq)\n"
    "m = wf.model('m_toy').merge(eq, 'CN c Y CN(-1)').append('Y = CN + I + G')\n"
    "m.solve('2010Q1', '2010Q4')\n"
    "eqn.show(wf.graph('g_y', 'Y Y_0', start='2005Q1'))\n", encoding="utf-8")
subprocess.run([sys.executable, "-m", "equion", "run", "demo_run.py", "--run-id", "demo", "-q",
                "--format", "csv,xlsx,json,html"], check=True, capture_output=True)
for p in sorted(Path("out/demo").rglob("*")):
    if p.is_file():
        print(p.relative_to("out/demo").as_posix())
```
<!-- out -->
```text
graphs/02_g_y.csv
graphs/02_g_y.html
graphs/02_g_y.json
manifest.json
plotly.min.js
report.html
run.log
tables/01_eq_i.csv
tables/01_eq_i.json
tables.xlsx
```

| 파일 | 내용 |
|---|---|
| `report.html` | 모든 출력을 한 페이지로(그래프 포함, 인터넷 없이 열림) |
| `manifest.json` | 재현 기록 — 판·git 커밋·매개변수·입력 파일 해시·풀이 상태·출력 목록·시각([항목](outputs.md#보고서-manifestjson)) |
| `run.log` | 화면 출력 그대로 |
| `tables/` · `tables.xlsx` | `eqn.show`로 보인 표(csv·json) · 표 전체를 시트별로(xlsx를 고르면) |
| `graphs/` | 그래프(html)와 그 데이터(csv·json) |
| `plotly.min.js` | 그래프 스크립트(`--plotlyjs copy`, 기본) |

- 표·그래프 파일 이름 앞의 번호(`01_`)는 `eqn.show`로 보인 순서입니다.
- `out/LATEST`에는 마지막 실행 ID가 적혀 있습니다.
- `--format`으로 형식을 고릅니다(기본 `csv,html`). `--no-report`면 폴더를 만들지 않습니다.
- `manifest.json`은 `format: "equion-run"`과 `format_version`으로 형식을 밝힙니다 — 필드를 바꾸면 판을 올립니다.
- 0.5.0 이전 보고서(`format: "macromodel-run"`)도 `equion info`가 읽습니다.

## 매개변수 JSON(`--params`)

```json
{"oil_shock": 20, "start": "2023Q1"}
```

스크립트는 `p = eqn.params(oil_shock=10, start="2023Q1")`처럼 기본값과 함께 읽고 `p.oil_shock`으로 씁니다.
`--set 이름=값`이 그 위에 덮고, 환경변수 `EQUION_PARAMS`(JSON 문자열)도 읽습니다.

관련: [출력 표 읽는 법](outputs.md) · [명령줄](cli.md) · [워크파일 다루기 튜토리얼](../tutorial/README.md)
