# 가이드 8. 막혔을 때

오류는 종료 코드와 한 줄의 까닭으로 옵니다. 까닭에는 대개 **있는 이름 목록이나 다음 명령**이 들어 있습니다 — 그대로 따르면 됩니다.

| 종료 코드 | 뜻 |
|---|---|
| 0 | 성공(스크립트면 `!` 표시가 있을 수 있다 — 읽고 판단) |
| 1 | 스크립트 오류(Python 예외, 스크립트의 모르는 지표) |
| 2 | 풀이 실패 조건(`--fail-on`) · 스크립트의 `expect --stop` · 재연에 다른 단계 |
| 3 | 입력 오류 — 없는 파일·부품·모형, 문법, 식이 쓴 변수가 자료에 없음, `--set` 값의 형, 틀이 맞지 않음, 손으로 고친 구역, 허용 안 된 명령, 프로젝트 밖 경로 |

```console
$ equion new trouble --template desk
$ cd trouble
```
<!-- out -->
```text
$ equion new trouble --template desk
새 프로젝트 trouble:
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
  cd trouble
  equion assemble main

$ cd trouble
```

## 1. 이름이 틀렸을 때

<!-- error -->
```console
$ equion est demand:ZZ
$ equion hs nomodel
$ equion work show est:nope
```
<!-- out -->
```text
$ equion est demand:ZZ
equion: 오류: 없는 부품: demand:ZZ (있는 부품: demand:CN, demand:I, demand:Y, price:P, finance:RL, finance:M2)
(종료 코드 3)

$ equion hs nomodel
equion: 오류: 없는 모형·블록: nomodel (모형: core, main, main_fixrl · 블록: demand, price, finance)
(종료 코드 3)

$ equion work show est:nope
equion: 오류: 없는 기록 est:nope
(종료 코드 3)
```

부품은 `블록:목표`, 모형·블록은 `equion.toml`의 이름, 기록은 `종류:이름`입니다 — 메시지의 괄호 안 목록에서 고릅니다.

## 2. 받은 원자료가 들어가지 않을 때

```python
from pathlib import Path

Path("DATA/raw/inbox/새자료.csv").write_text("기간,값\n2020Q1,1\n", encoding="utf-8")
```

<!-- error -->
```console
$ equion data inbox
```
<!-- out -->
```text
$ equion data inbox
[data inbox] 받은 원자료 1 — DATA/raw/inbox/
  새자료.csv — 짝지을 출처가 없습니다: series.toml [source.이름]에 inbox = "파일 이름 글롭"을 적거나 equion data add DATA/raw/inbox/새자료.csv --source 이름
  넣기   스크립트의 자료 단계(예: equion run FLOWS/monthly.eqs) — 따로 넣으려면 equion data build --inbox ask --use
(종료 코드 3)
```

파일 이름이 어느 출처와도 맞지 않습니다. 어느 출처의 새 파일인지 정해 넣거나(`equion data add 파일 --source 이름`), 이름 규칙을
`DATA/series.toml`의 `[source.이름] inbox = "글롭"`으로 적습니다. 틀이 맞지 않으면(열 이름이 바뀜 등) 그 열과 함께 알리고 아무것도 넣지 않습니다.

```python
Path("DATA/raw/inbox/새자료.csv").unlink()
```

## 3. 보고서의 숫자를 손으로 고쳤을 때

보고서·노트의 결과 구역은 명령이 다시 만듭니다. 손으로 고친 구역은 덮지 않고 고친 곳을 보입니다 — 덮을지는 사람이 정할 일이라
`report update`·`note run`은 그 구역을 건너뛰고 종료 코드 3으로 끝납니다(다른 구역·블록은 바뀐다, `--dry-run`은 0). 스크립트 안에서는 멈추지 않고 그 단계에 `!`와 까닭이 남습니다.

```console
$ equion sim base --as s1
$ equion report new r1
$ equion report add r1 sim:s1 --rows Y,CN --show yoy --annual
```
<!-- out -->
```text
$ equion sim base --as s1
[sim:s1] main · base · 2020Q1~2021Q4 dynamic · 정상 8 · 일부식 제외 0 · 실패대체 0 · 실패 0
  연간 증가율  2020: Y 0.89% · CN 0.87% · I -0.25% · P 2.52% │ 2021: Y 1.74% · CN 1.65% · I 1.97% · P 2.58%
  가정   base: G·POIL 16칸 · 채움(last) R 8칸
  보정항  base: demand:CN last(+0.654) · demand:I decay
  알아서 한 것  구간 next:8 → 2020Q1~2021Q4 · 채택 기록 없이 지금 자료로 추정: demand:CN, demand:I, price:P, finance:RL, finance:M2 · 보정항 규칙 값 16칸 · 가정 16칸(G, POIL) · 외생 R 8칸을 채움(last)
  기록   sim:s1 (work/sim/s1/)

$ equion report new r1
[report new] reports/r1.md
  바뀜 기록  h0002

$ equion report add r1 sim:s1 --rows Y,CN --show yoy --annual
[report add] reports/r1.md
  #1 sim:s1  넣음 — **표 1. 전망 — base (main)** (연간 증가율, %)
  바뀜 기록  h0003
```

```python
r = Path("reports/r1.md")
r.write_text(r.read_text(encoding="utf-8").replace("| Y |", "| Y(손으로) |", 1), encoding="utf-8")
```

<!-- error -->
```console
$ equion report check r1
$ equion report update r1
```
<!-- out -->
```text
$ equion report check r1
[report check] reports/r1.md — 구역 1
  #1 sim:s1  손으로 고침

$ equion report update r1
[report update] reports/r1.md — 구역 1
  #1 sim:s1  손으로 고침 — 바꾸지 않음(--force) — 고친 곳
    --- 보낸 것 → 지금(전)
    +++ 보낸 것 → 지금(후)
    @@ -2,7 +2,7 @@

     | 시리즈 | 2020 | 2021 |
     |---|---|---|
    -| Y | 0.9 | 1.7 |
    +| Y(손으로) | 0.9 | 1.7 |
     | CN | 0.9 | 1.7 |

     자료: Equion sim:s1(자료 회차 d2026-11a)
  손으로 고친 구역(#1)은 바꾸지 않았습니다 — 사람에게 묻고, 덮으려면 equion report update reports/r1.md --force (종료 코드 3)
(종료 코드 3)
```

글로 남기려면 구역 밖에 쓰고, 구역은 `equion report update r1 --force`로 다시 만듭니다.

## 4. 스크립트가 멈췄을 때

```python
Path("FLOWS/strict.eqs").write_text("hs main\nexpect hs Y.rmspe < 0.01%\nsim base\n", encoding="utf-8")
```

<!-- error -->
```console
$ equion run FLOWS/strict.eqs
$ equion work show run:strict_0001
```
<!-- out -->
```text
$ equion run FLOWS/strict.eqs
[1/3] hs main                                      ✓ [hs:hs_0001] main dynamic 2005Q1~2019Q4 · 정상 60 · 일부식 제외 0 · 실패대체 0 · 실패 0
[2/3] expect hs Y.rmspe < 0.01%                    × 어긋남: Y RMSPE 0.4745 — 조건 Y.rmspe < 0.01
기록  run:strict_0001 · 단계 2 · 멈춤(확인) · 종료 코드 2
  멈춘 단계 [2] expect hs Y.rmspe < 0.01% — 어긋남: Y RMSPE 0.4745 — 조건 Y.rmspe < 0.01
(종료 코드 2)

$ equion work show run:strict_0001
[run:strict_0001] FLOWS/strict.eqs · 멈춤(확인) · 종료 코드 2 · 자료 회차 d2026-11a
  [1] ✓ hs main  → hs:hs_0001
  [2] × expect hs Y.rmspe < 0.01%  — 어긋남: Y RMSPE 0.4745 — 조건 Y.rmspe < 0.01
  카드   work/run/strict_0001/summary.md
```

`expect`가 `--stop`(기본)이면 멈추고 종료 코드 2, `--flag`이면 표시하고 계속합니다. 고친 뒤에는 `--from 단계번호`(또는 `"## 제목"`)로 그 단계부터.

## 5. 되돌리기

정의 파일의 바뀜은 모두 `work/history/`에 남습니다 — 명령이 바꾼 것도, 편집기로 고친 것('바깥' — 위에서 보고서의 숫자를 고치고 스크립트를 새로
쓴 것)도. 채택을 하나 해 보고 되돌립니다. 되돌리기는 **그 바뀜 하나만** 물리는 것이고(뒤의 바뀜은 그대로), 그것도 기록에 남습니다(다시 되돌릴 수 있다).
뒤의 바뀜이 같은 줄(TOML이면 같은 키)을 고쳤으면 아무것도 쓰지 않고 겹친 파일과 뒤의 바뀜을 알리며 멈춥니다(종료 코드 3) — 뒤의 바뀜을
먼저 되돌리거나(새것부터), 그 파일을 그 바뀜 앞 내용으로 통째로 되돌리려면 `--force`(뒤의 바뀜도 그 파일에서 함께 물린다).

```console
$ equion est "CN c Y Y(-1) CN(-1)" --for demand:CN --as cn3
$ equion adopt est:cn3
$ equion history list --limit 2
$ equion history revert h0005
```
<!-- out -->
```text
$ equion est "CN c Y Y(-1) CN(-1)" --for demand:CN --as cn3
[est:cn3] OLS CN · 1970Q2~2019Q4 · n=199   R²adj 0.9999 · SE 0.4843 · DW 2.001 · AIC 280.1 · BIC 293.3
  계수   c 8.677(t 11.141) · Y 0.6045(t 51.623) · Y(-1) -0.1678(t -4.047) · CN(-1) 0.3885(t 7.172)
  진단   LM(2) p=0.718 ✓ · White p=0.543 ✓ · JB p=0.290 ✓ · RESET p=0.681 ✓ · LB(4) p=0.923 ✓
  기준   통과 · 부호 Y + ✓
  알아서 한 것  시차·결측으로 표본 시작 1970Q1 → 1970Q2
  기록   est:cn3 (work/est/cn3/) · demand:CN 후보

$ equion adopt est:cn3
[adopt] demand:CN ← est:cn3
  블록 파일  그 줄을 이 식으로 바꿈
  채택표   EQUATIONS/adopted.toml
  바뀜 기록  h0005 (EQUATIONS/adopted.toml, EQUATIONS/demand.txt)
  다음   모형을 풀면 이 기록의 계수를 쓴다(다시 추정하지 않음)

$ equion history list --limit 2
[history list] trouble: 바뀜 2
[h0004] 2026-11-13T05:18:04 · 바깥 · 명령 밖에서 고침(편집기·직접 편집)
  파일   FLOWS/strict.eqs(새로) · reports/r1.md(고침)
[h0005] 2026-11-13T05:18:09 · 터미널 · equion adopt est:cn3
  파일   EQUATIONS/adopted.toml(새로) · EQUATIONS/demand.txt(고침)
  메모   demand:CN ← est:cn3

$ equion history revert h0005
[history revert] h0005 되돌림
[h0006] 2026-11-13T05:18:12 · 터미널 · equion history revert h0005
  파일   EQUATIONS/adopted.toml(지움) · EQUATIONS/demand.txt(고침)
  메모   h0005 되돌리기
```

## 6. 그 밖에

| 증상 | 할 일 |
|---|---|
| `프로젝트 설정 파일이 없습니다` | 프로젝트 폴더(또는 그 하위 폴더)에서 치거나 `-p 폴더` |
| `equion.toml 문법 오류 … (at line N, column M)` | 그 줄을 고친다(따옴표·괄호). `equion guide`는 설정과 상관없이 된다 |
| `기준 미달 …` (`!`) | 판단 기준에 걸린 식 — [4. 식 고르기](04-equations.md) |
| `채택 기록 …의 식이 블록 파일과 다릅니다` | 블록 파일을 고쳐 채택 계수를 쓸 수 없다 — 다시 추정해 채택하거나 블록 파일을 되돌린다 |
| `노트에서 부를 수 없습니다` | 노트의 블록은 계산·보기 명령만 — 바꾸는 명령은 터미널이나 스크립트에서 |
| `프로젝트 안에만 둡니다` | 보고서·노트·내보내기·스크립트의 경로는 프로젝트 안만 |
| 지난달 결과가 왜 그랬는지 | `equion run --replay run:…` — 그때 그대로 다시 돌려 단계마다 견준다 |

오류 메시지 전체는 [오류 메시지 참조](../reference/errors.md), 엔진 수준의 문제(미수렴·결측)는 [문제 해결 레시피](../howto/troubleshooting.md).

## 확인할 것

- [ ] 틀린 이름마다 3과 있는 이름 목록
- [ ] 받은 파일이 맞지 않으면 아무것도 넣지 않고 까닭(짝 없음·틀이 맞지 않음)
- [ ] 손으로 고친 구역은 `report update`가 덮지 않고, `--force`로만
- [ ] `expect --stop`에 걸리면 2, `work show run:…`에 멈춘 단계와 까닭
- [ ] `history revert`가 그 바뀜만 되돌리고 그것도 기록에 남는다(뒤의 바뀜과 겹치면 3 — `--force`로만 통째로)

다음: [9. 자동으로 돌리기](09-automation.md)
