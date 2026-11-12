# 9. 프로젝트와 스크립트

1~8편은 Python 스크립트 하나에서 워크파일을 열고 식을 추정해 모델을 풀었습니다. 실제 모형 작업은 오래 가고 여러 사람(과 Claude)이 함께 합니다 —
식은 블록 파일로 나뉘고, 자료는 달마다 새로 오며, 무엇을 언제 어떤 자료로 계산했는지가 남아야 합니다. **프로젝트**는 그것을 폴더 하나로 다룹니다.

- 블록(방정식 파일)과 모형(블록을 끼운 조립) — `equion.toml`
- 원자료 → 정의 → **자료 회차**(만든 자료는 고치지 않는다)
- 계산할 때마다 **작업 기록**(`work/`) — 결론은 기록 이름으로 말한다
- 원자료에서 보고서까지의 순서를 적은 **스크립트**(`.eqs`) — 새 자료가 오면 한 번 돌리고, 그때 그대로 다시 할 수 있다

이 편은 모두 터미널 명령으로 합니다. 사람이 터미널에서 치는 것, Claude가 치는 것, 노트·스크립트에 적는 것이 같은 줄입니다. 출력을 함께 보이려고
8편처럼 Python에서 명령을 부르는 작은 도우미를 씁니다.

```python
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd
import equion as eqn


def equion(*args, cwd="prj"):
    """터미널의 `equion …`과 같다 — 프로젝트 폴더(cwd)에서, 화면 출력과 종료 코드를 보인다."""
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable, "-m", "equion", *args], cwd=cwd, capture_output=True, text=True,
                       encoding="utf-8", env=env, stdin=subprocess.DEVNULL)
    print((r.stdout + r.stderr).rstrip())
    if r.returncode:
        print(f"(종료 코드 {r.returncode})")
    return r.returncode


equion("new", "prj", "--template", "desk", "--force", cwd=".")
```
<!-- out -->
```text
새 프로젝트 prj:
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
  cd prj
  equion assemble main
```

## 9.1 블록과 모형 — 조립

블록은 방정식 파일 하나(`EQUATIONS/demand.txt` …), 식 한 줄은 **부품** `블록:목표`(`demand:CN`)입니다. 모형은 블록과 다른 모형을 이름으로 끼워
만듭니다(`equion.toml`의 `[model.main]` — `include = ["core"]`, `blocks = ["price", "finance"]`). 조립 검사는 계산 없이 내생·외생·겹친 목표·
모르는 변수·외생 자료의 끝을 봅니다.

```python
print(Path("prj/EQUATIONS/demand.txt").read_text(encoding="utf-8"))
equion("assemble", "main")
```
<!-- out -->
```text
# 수요 블록 — 한 줄에 한 식, '#' 뒤는 설명(문법: docs/explain/equations.md)
CN c Y CN(-1)            # 소비
I c Y(-1) R              # 투자
Y = CN + I + G           # 국민소득(항등식)

[assemble main] 수요 + 물가 + 금융 — 블록 3 · 추정식 5 · 항등식 1
  조립   main = core(demand) + price + finance
  내생 6  CN · I · Y · P · RL · M2
  외생 3  G(~2019Q4) · POIL(~2019Q4) · R(~2019Q4)
  연결   demand →Y→ price · price →P→ finance · demand →Y→ finance
  풀이   블록 5 (동시 CN·Y)
  문제   없음
```

## 9.2 자료 회차

원자료(`DATA/raw/` — 받은 그대로)를 정의(`DATA/series.toml`·`derived.txt`)대로 읽은 것이 자료 회차입니다(`work/data/<회차>/`). 만든 회차는 고치지
않고, 새 자료가 오면 새 회차를 만들어 바꿉니다(`data build --use`). 예제 프로젝트는 만들 때 첫 회차를 만들어 두었습니다.

```python
equion("data", "list")
```
<!-- out -->
```text
[data list] prj: 자료 회차 1
  * d2026-11a    2026-11-13T05:20:29  1970Q1~2019Q4    시리즈 13
```

## 9.3 식 고르기 — 추정·후보·비교·채택

추정은 할 때마다 기록(`est:…`)을 남깁니다. 블록 파일의 식은 그대로 두고 **후보 식**을 추정해(`--for 부품`) 견주고, 바꿔 끼워 과거 재현(HS)으로
확인한 뒤 채택합니다. 채택하면 블록 파일의 그 줄과 채택표(`EQUATIONS/adopted.toml`)가 바뀌고, 그 뒤 모형은 **채택 계수**로 풉니다(다시 추정하지 않는다).

```python
equion("est", "demand:CN", "--as", "cn1")
equion("est", "CN c Y CN(-1) CN(-2)", "--for", "demand:CN", "--as", "cn2")
equion("compare", "--part", "demand:CN")
```
<!-- out -->
```text
[est:cn1] OLS CN · 1970Q2~2019Q4 · n=199   R²adj 0.9999 · SE 0.5029 · DW 1.652 · AIC 294.1 · BIC 304.0
  계수   c 11.647(t 42.990) · Y 0.5869(t 51.970) · CN(-1) 0.1782(t 11.260)
  진단   LM(2) p=0.046 ! · White p=0.485 ✓ · JB p=0.325 ✓ · RESET p=0.484 ✓ · LB(4) p=0.151 ✓
  기준   걸러짐: LM(2) p=0.046
  알아서 한 것  시차·결측으로 표본 시작 1970Q1 → 1970Q2
  기록   est:cn1 (work/est/cn1/) · demand:CN 후보
[est:cn2] OLS CN · 1970Q3~2019Q4 · n=198   R²adj 0.9999 · SE 0.4959 · DW 1.529 · AIC 288.1 · BIC 301.2
  계수   c 11.686(t 42.978) · Y 0.5890(t 52.524) · CN(-1) 0.1326(t 5.199) · CN(-2) 0.0427(t 2.315)
  진단   LM(2) p=0.001 ! · White p=0.082 ✓ · JB p=0.482 ✓ · RESET p=0.345 ✓ · LB(4) p=0.016 !
  기준   걸러짐: LM(2) p=0.001
  알아서 한 것  시차·결측으로 표본 시작 1970Q1 → 1970Q3
  기록   est:cn2 (work/est/cn2/) · demand:CN 후보
[compare] 추정 기록 2
                            식         부품 채택             표본    n   R²adj      SE     DW    AIC    BIC LM(2) p White p   JB p RESET p                  기준
기록
est:cn1         CN c Y CN(-1)  demand:CN     1970Q2~2019Q4  199  0.9999  0.5029  1.652  294.1  304.0   0.046   0.485  0.325   0.484  걸러짐: LM(2) p=0.046
est:cn2  CN c Y CN(-1) CN(-2)  demand:CN     1970Q3~2019Q4  198  0.9999  0.4959  1.529  288.1  301.2   0.001   0.082  0.482   0.345  걸러짐: LM(2) p=0.001
  ! 표본이 달라 AIC·BIC를 그대로 견주기 어렵습니다
```

판단 기준(`equion.toml`의 `[criteria]` — 기대 부호·진단 p값)은 후보마다 '기준' 줄에 통과·걸러짐과 까닭을 적습니다. 바꿔 끼우기는 파일을 바꾸지 않습니다.

```python
equion("hs", "main", "--as", "h_now")
equion("hs", "main", "--swap", "demand:CN=est:cn2", "--vs", "hs:h_now", "--as", "h_cn2")
```
<!-- out -->
```text
[hs:h_now] main dynamic 2005Q1~2019Q4 · 정상 60 · 일부식 제외 0 · 실패대체 0 · 실패 0
  RMSPE  Y 0.47% · CN 0.51% · I 0.86% · P 1.43% · M2 2.24% · RL 9.68%
  알아서 한 것  구간 [hs] range = 2005Q1:last → 2005Q1~2019Q4 · 채택 기록 없이 지금 자료로 추정: demand:CN, demand:I, price:P, finance:RL, finance:M2
  기록   hs:h_now (work/hs/h_now/)
[hs:h_cn2] main dynamic 2005Q1~2019Q4 · 정상 60 · 일부식 제외 0 · 실패대체 0 · 실패 0
  RMSPE  Y 0.46% · CN 0.49% · I 0.84% · P 1.44% · M2 2.25% · RL 9.68%
  비교   vs hs:h_now — Y 0.47% → 0.46% · CN 0.51% → 0.49% · I 0.86% → 0.84% · P 1.43% → 1.44% · M2 2.24% → 2.25% (나머지 그대로)
  바꿔 끼움  demand:CN ← est:cn2 (파일은 그대로)
  알아서 한 것  구간 [hs] range = 2005Q1:last → 2005Q1~2019Q4 · 채택 기록 없이 지금 자료로 추정: demand:I, price:P, finance:RL, finance:M2 · 바꿔 끼움: demand:CN ← est:cn2
  기록   hs:h_cn2 (work/hs/h_cn2/)
```

채택과 바뀜 기록 — 정의 파일이 바뀔 때마다 누가·어떤 명령으로·무엇이 바뀌었는지 남고(`history show`), 되돌릴 수 있습니다(`history revert`).
되돌리기는 **그 바뀜 하나만** 물립니다 — 뒤의 바뀜은 그대로 두고, 뒤의 바뀜이 같은 줄을 고쳤으면 아무것도 쓰지 않고 멈춥니다(종료 코드 3).
그래도 그 파일을 그 바뀜 앞 내용으로 통째로 되돌리려면 `--force`(뒤의 바뀜도 그 파일에서 함께 물린다).

```python
equion("adopt", "est:cn2")
equion("history", "list")
```
<!-- out -->
```text
[adopt] demand:CN ← est:cn2
  블록 파일  그 줄을 이 식으로 바꿈
  채택표   EQUATIONS/adopted.toml
  바뀜 기록  h0002 (EQUATIONS/adopted.toml, EQUATIONS/demand.txt)
  다음   모형을 풀면 이 기록의 계수를 쓴다(다시 추정하지 않음)
[history list] prj: 바뀜 2
[h0001] 2026-11-13T05:20:29 · Python · data use d2026-11a
  파일   equion.toml(고침)
  메모   자료 회차 d2026-11a
[h0002] 2026-11-13T05:20:42 · Python · equion adopt est:cn2
  파일   EQUATIONS/adopted.toml(새로) · EQUATIONS/demand.txt(고침)
  메모   demand:CN ← est:cn2
```

## 9.4 전망과 보고서

전망은 가정 세트(`ASSUMPTIONS/`)·보정항(`ADDFACTORS/`)·시나리오(`SCENARIOS/`)로 풉니다. 계산한 값은 실측 자리에 쓰지 않고 기록에만 남습니다.
보고서에는 명령 블록 없이 결과만 보냅니다 — 표의 모양(행·전년동기비·연간)은 구역 표시에 남아, 새 기록으로 바꿀 때 같은 모양으로 다시 만듭니다.

```python
equion("sim", "base", "--as", "fc_base")
equion("sim", "oil20", "--as", "fc_oil20")
equion("report", "new", "memo", "--title", "이번 전망")
equion("report", "add", "memo", "sim:fc_base", "--rows", "Y,CN,I", "--show", "yoy", "--annual", "--title", "성장률")
equion("report", "add", "memo", "sim:fc_oil20", "--rows", "Y,P", "--show", "diff", "--title", "유가 20% 상승의 영향")
```
<!-- out -->
```text
[sim:fc_base] main · base · 2020Q1~2021Q4 dynamic · 정상 8 · 일부식 제외 0 · 실패대체 0 · 실패 0
  연간 증가율  2020: Y 0.89% · CN 0.88% · I -0.24% · P 2.52% │ 2021: Y 1.70% · CN 1.60% · I 1.94% · P 2.56%
  가정   base: G·POIL 16칸 · 채움(last) R 8칸
  보정항  base: demand:CN last(+0.629) · demand:I decay
  알아서 한 것  구간 next:8 → 2020Q1~2021Q4 · 채택 계수: demand:CN(est:cn2) · 채택 기록 없이 지금 자료로 추정: demand:I, price:P, finance:RL, finance:M2 · 보정항 규칙 값 16칸 · 가정 16칸(G, POIL) · 외생 R 8칸을 채움(last)
  기록   sim:fc_base (work/sim/fc_base/)
[sim:fc_oil20] main · oil20 · 2020Q1~2021Q4 dynamic · 정상 8 · 일부식 제외 0 · 실패대체 0 · 실패 0
  연간 증가율  2020: Y 0.89% · CN 0.88% · I -0.24% · P 2.78% │ 2021: Y 1.70% · CN 1.60% · I 1.94% · P 2.56%
  가정   base: G·POIL 16칸 · 채움(last) R 8칸
  보정항  base: demand:CN last(+0.629) · demand:I decay
  시나리오  oil20 (유가 20% 상승): POIL +20% start~end
  기준선 대비(끝 기 수준)  Y +0.00% · CN +0.00% · I +0.00% · P +0.25% · RL +0.00% · M2 +0.26%
  알아서 한 것  구간 next:8 → 2020Q1~2021Q4 · 채택 계수: demand:CN(est:cn2) · 채택 기록 없이 지금 자료로 추정: demand:I, price:P, finance:RL, finance:M2 · 보정항 규칙 값 16칸 · 가정 16칸(G, POIL) · 외생 R 8칸을 채움(last)
  기록   sim:fc_oil20 (work/sim/fc_oil20/)
[report new] reports/memo.md
  바뀜 기록  h0003
[report add] reports/memo.md
  #1 sim:fc_base  넣음 — **표 1. 성장률** (연간 증가율, %)
  바뀜 기록  h0004
[report add] reports/memo.md
  #2 sim:fc_oil20  넣음 — **표 2. 유가 20% 상승의 영향** (기준선 대비, %)
  바뀜 기록  h0005
```

분석도 같습니다 — 분석 하나 = 명령 하나 = 기록 하나(`an:`). 노트(`notes/*.md`)의 ```` ```equion ```` 블록에 적으면 `note run`이 결과를 그 아래에 채웁니다.

```python
equion("an", "unitroot", "core", "--trend", "c")
```
<!-- out -->
```text
[an:unitroot_0001] 단위근 · 묶음 core(Y · CN · I) · 1970Q1~2019Q4 · 자료 data:d2026-11a
  Y            ADF -0.072 p=0.952 · KPSS 2.097 p=0.010 → 단위근
  CN           ADF 0.007 p=0.959 · KPSS 2.097 p=0.010 → 단위근
  I            ADF -0.346 p=0.919 · KPSS 2.079 p=0.010 → 단위근
  알아서 한 것  ADF 시차 수를 BIC로 골랐다 · 판단: ADF(귀무 단위근)·KPSS(귀무 정상) 모두 5%
  기록   an:unitroot_0001 (work/an/unitroot_0001/summary.md)
```

## 9.5 스크립트 한 번 — 새 자료가 오면

지금까지의 순서를 스크립트에 적어 두면(`FLOWS/monthly.eqs` — 한 줄이 명령 하나) 새 자료가 올 때 한 번 돌리면 됩니다. 새 원자료는 받은 상자
`DATA/raw/inbox/`에 놓습니다 — 파일 이름으로 출처를 짝짓고 불러오기 틀로 읽어 봅니다. 여기서는 예제 자료에 한 분기를 더한 합성 표를 씁니다.

```python
df = pd.read_csv("prj/DATA/raw/toy_q.csv", index_col=0)
df.loc["2020Q1"] = df.iloc[-1] * 1.01
df.to_csv("prj/DATA/raw/inbox/toy_q_2020Q1.csv")
equion("data", "inbox")
equion("check", "FLOWS/monthly.eqs")
```
<!-- out -->
```text
[data inbox] 받은 원자료 1 — DATA/raw/inbox/
  toy_q_2020Q1.csv → [source.na] (이름이 toy_q.csv와 같은 앞부분) · 틀 검사 통과
  넣기   스크립트의 자료 단계(예: equion run FLOWS/monthly.eqs) — 따로 넣으려면 equion data build --inbox ask --use
[check] FLOWS/monthly.eqs: 단계 11 · 문제 없음
  파일을 바꾸는 단계 1, 3, 7, 8, 9, 10, 11
```

실행합니다. 단계마다 한 줄 — `✓` 정상, `!` 사람이 볼 것(판단 기준을 통과하지 못한 식은 옛 계수를 쓰고 계속), `×`이면 멈춥니다. 미리보기는
`--dry-run`, 매개변수는 `--set scenarios=base`, 중간부터는 `--from 단계`.

```python
equion("run", "FLOWS/monthly.eqs")
```
<!-- out -->
```text
[1/11] data build --inbox ask --use                 ✓ [data build] 새 회차 d2026-11b
[2/11] assemble main                                ✓ [assemble main] 수요 + 물가 + 금융 — 블록 3 · 추정식 5 · 항등식 1
[3/11] est main --adopted --adopt if_pass           ! 기준 미달 demand:CN · 기준 미달 finance:RL · 기준 미달 finance:M2 — [est --adopted] main · 정책 if_pass…
[4/11] hs main                                      ✓ [hs:hs_0001] main dynamic 2005Q1~2020Q1 · 정상 61 · 일부식 제외 0 · 실패대체 0 · 실패 0
[5/11] expect hs Y.rmspe < 3% --flag                ✓ Y RMSPE 0.4659 — Y.rmspe < 3
[6/11] sim base oil20 --model main                  ✓ [sim:2026-11_base] main · base · 2020Q2~2022Q1 dynamic · 정상 8 · 일부식 제외 0 · 실패대체 0 · 실패 0
[7/11] note run notes/data_check.md                 ✓ [note run] notes/data_check.md: 블록 2
[8/11] report new reports/forecast_d2026-11b.md --title "월간 전망 — 자료 d2026-11b" --exist-ok ✓ [report new] reports/forecast_d2026-11b.md
[9/11] report add reports/forecast_d2026-11b.md sim:2026-11_base --key growth --rows Y,CN,I,P --show yoy --annual --title "성장률 전망" ✓ [report add] reports/forecast_d2026-11b.md
[10/11] report add reports/forecast_d2026-11b.md hs:hs_0001 --key hs --rows Y,CN --chart --title "과거 재현" ✓ [report add] reports/forecast_d2026-11b.md
[11/11] export hs:hs_0001 sim:2026-11_base sim:2026-11_oil20 --xlsx exports/forecast_d2026-11b.xlsx ✓ [export] exports/forecast_d2026-11b.xlsx — 기록 3 · 시트 15: 출처, hs_0001_적합도, hs_0001_해, hs_0…
기록  run:monthly_0001 · 단계 11 · 표시 1 · 종료 코드 0 · 자료 회차 d2026-11a → d2026-11b
```

실행 기록(`run:monthly_0001`)에는 값을 바꿔 넣은 뒤의 스크립트·정의 사본·받은 원자료·자료 회차·판이 들어 있어, 그때 그대로 다시 돌려 단계마다
숫자를 견줄 수 있습니다. 프로젝트는 바뀌지 않습니다.

```python
equion("run", "--replay", "run:monthly_0001", "-q")
```
<!-- out -->
```text
[run --replay] run:monthly_0001 — 단계 11 · 모두 같음
  [1] = data build --inbox ask --use  — 숫자 같음 — data:d2026-11b
  [2] = assemble main  — 기록 없음 — 상태 같음
  [3] = est main --adopted --adopt if_pass  — 숫자 같음 — est:cn_0001 · est:i_0001 · est:p_0001 …
  [4] = hs main  — 숫자 같음 — hs:hs_0001
  [5] = expect hs Y.rmspe < 3% --flag  — Y RMSPE 0.4659 — Y.rmspe < 3
  [6] = sim base oil20 --model main  — 숫자 같음 — sim:2026-11_base · sim:2026-11_oil20
  [7] = note run notes/data_check.md  — 숫자 같음 — an:summary_0001
  [8] = report new reports/forecast_d2026-11b.md --title "월간 전망 — 자료 d2026-11b" --exist-ok  — 기록 없음 — 상태 같음
  [9] = report add reports/forecast_d2026-11b.md sim:2026-11_base --key growth --rows Y,CN,I,P --show yoy --annual --title "성장률 전망"  — 기록 없음 — 상태 같음
  [10] = report add reports/forecast_d2026-11b.md hs:hs_0001 --key hs --rows Y,CN --chart --title "과거 재현"  — 기록 없음 — 상태 같음
  [11] = export hs:hs_0001 sim:2026-11_base sim:2026-11_oil20 --xlsx exports/forecast_d2026-11b.xlsx  — 기록 없음 — 상태 같음
기록  run:monthly_0002 · 종료 코드 0
```

## 9.6 Claude와 함께

같은 폴더에서 Claude Code를 띄우면 Claude도 같은 명령을 씁니다. 예제 프로젝트의 `CLAUDE.md`가 먼저 `equion guide`(모형 작업 안내 — 규칙·프로젝트
지도·명령·분석·판단 기준·보고 꼴)를 읽게 합니다. 규칙의 핵심은 사람과 같습니다 — 계산은 명령으로, 결론에는 근거 기록의 이름, 결과는 고치지 않고,
정의 파일은 명령(채택·`block add`·`scenario define`·제안 …)으로 먼저, "제안만"이면 파일 대신 `equion propose`.

```python
print("\n".join(eqn.help.guide_text().splitlines()[4:19]))
```
<!-- out -->
```text

## 1. 꼭 지킬 것

1. **계산은 명령으로.** 추정·과거 재현(HS)·전망·분석은 `equion est`·`hs`·`sim`·`an`으로 한다 — 할 때마다 `work/<종류>/<이름>/`에 기록이 남고
   사람이 Desk에서 그 기록을 연다. 같은 계산을 Python으로 따로 하지 않는다. 꼭 Python이면 `eqn.project(".")`의 메서드 — `p.est`·`p.sim`·`p.an`은
   명령과 같은 기록을 남기지만 `p.hs("main")`은 풀기만 한다(기록 `hs:`는 `p.hs("main", record=True)`).
2. **결론에는 근거 기록의 이름을 붙인다.** "c5가 가장 낫다(근거 `est:cons_c5` · `hs:hs_0009`)". 이름 없는 수치를 말하지 않는다.
3. **결과는 고치지 않는다.** `work/` 아래의 기록·`DATA/raw/`의 원자료·보고서와 노트의 결과 구역(`<!-- equion:… -->` 사이)은 손대지 않는다.
   다시 계산하면 새 기록이고, 구역은 `note run`·`report update`가 바꾼다.
4. **정의 파일은 명령으로 먼저 고친다.** 채택은 `equion adopt est:…`, 회차 바꾸기는 `equion data use`, 정의로 남기기는 `equion an keep`,
   블록 파일의 식 한 줄은 `equion block add 블록 "식"`·`block remove 블록:목표`, 자료 정의(출처·시리즈)는 `equion data define`,
   모형·블록·묶음은 `model define`·`block define`·`group define`, 시나리오는 `scenario define`, 노트의 블록은 `note add` —
   명령으로 고친 것은 바뀜 기록에 누가(Claude)와 함께 남는다. 여러 파일은 제안(`equion propose new … ` → 사람이 `propose apply`).
   명령이 없는 고침(주석·가정 CSV의 값 등)은 사람이 시켰을 때만 직접 고치고 — 다음 명령 때 '바깥' 바뀜으로 바뀜 기록에 남는다 — 무엇을 고쳤는지 말한다.
   **정의를 한꺼번에 되돌리는 명령(`milestone restore`·`history revert`)은 사람에게 먼저 묻는다** — 사람이 시켰어도 먼저 무엇이 물려지는지
```

Claude Code 스킬 초안도 들어 있습니다(`equion guide skill`). 쓰려면 사람이 시킬 때 `equion guide skill --install user`(모든 프로젝트) 또는
`--install project`(이 프로젝트의 `.claude/skills/`)로 넣습니다.

## 정리

| 할 일 | 명령 |
|---|---|
| 조립 검사 | `equion assemble main` |
| 자료 회차 | `equion data list` · `data build --use` · `data inbox` · `data diff` |
| 식 고르기 | `equion est 부품` · `est "식" --for 부품` · `compare --part 부품` · `hs --swap 부품=est:… --vs hs:…` · `adopt est:…` |
| 전망·보고서 | `equion sim base oil20` · `report new 이름` · `report add 이름 sim:… --rows … --show yoy` |
| 분석·노트 | `equion an <분석> <대상>` · `an keep an:…` · `note run notes/x.md` |
| 기록·바뀜 | `equion work list` · `work show 기록` · `history list` · `history revert h…`(그 바뀜 하나만 — 뒤의 바뀜과 겹치면 멈춘다) |
| 시나리오·이정표 | `equion scenario define 이름 --shock POIL=+20%` · `an split "sim:… sim:…"` · `milestone make 이름` · `bundle make` |
| 스크립트 | `equion check x.eqs` · `run x.eqs [--dry-run · --set · --from]` · `run --replay run:…` · `script new·export --py` |
| Claude | `equion guide` · `guide skill --install user` |

파일 형식은 [파일 형식](../reference/formats.md), 명령은 [명령줄](../reference/cli.md), 할 일별 처방은 [레시피](../howto/README.md)
(R48~R66 — 프로젝트·회차·후보·전망 기록·제안·분석·노트·보고서·스크립트·자료 정의·시나리오 쓰기·요인 나누기·이정표와 묶어 보내기·비선형 시스템)에 있습니다.
