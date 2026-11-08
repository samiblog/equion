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

프로젝트는 폴더 하나입니다 — `equion.toml`이 자료 파일과 블록(방정식 파일 하나 = 블록 하나)을 이름으로 묶고, 모형은 블록과 다른 모형을
이름으로 끼워 조립합니다(D32). 여는 법은 `eqn.project(폴더)`, 검사는 `equion assemble`, 예제는 `equion new 폴더 --template desk`.

```toml
[project]
name = "demo"
format = "equion-project"
format_version = 1

[data]
file = "DATA/data.csv"            # 첫 열이 날짜인 자료 파일

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

[hs]                              # 과거 재현 기본값
model = "main"
range = "2005Q1:2019Q4"
mode = "dynamic"                  # dynamic · static · fit
```

| 규칙 | 내용 |
|---|---|
| 이름 | 블록·모형·묶음은 영문으로 시작하고 영문·숫자·`_`만(한글은 `desc`). 블록과 모형은 이름이 겹칠 수 없다 |
| 부품 이름 | 블록 파일의 식 한 줄은 `블록:목표변수`(예: `demand:CN`). 목표변수는 좌변의 첫 변수, 한 블록에 같은 목표는 하나 |
| 내생·외생 | 적지 않는다 — 모형에서 어떤 식의 목표면 내생, 아니면 외생 |
| 조립 문제 | 한 모형에 같은 목표가 둘, 자료에도 없고 어떤 식도 정하지 않는 변수, 순환 include, 없는 블록·모형·식(exclude) |
| 블록 파일 | 방정식 파일과 같은 문법(위). 줄 끝 `#` 뒤는 그 식의 설명으로 보인다 |
| 형식 판 | `format_version`이 이 equion이 읽는 판보다 크면 오류(새 판으로). 모르는 표는 경고하고 쓰지 않는다 |

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
