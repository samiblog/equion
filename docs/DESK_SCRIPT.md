# Equion Desk — Equion 스크립트 (제안, 2026-11-09)

**지금은 없다.** 지금 명령줄의 `equion run`은 Python 스크립트(`.py`)만 돌린다. **제안**: 명령 한 줄씩으로 된 **Equion 스크립트**(`.eqs`)를 더한다.
한 줄은 터미널에서 치는 `equion` 명령 하나와 같다. Desk만의 것이 아니라 **equion 패키지의 것**이라 Desk 없이 명령줄에서 그대로 돈다(`equion run monthly.eqs`).
Desk는 그것을 단계 화면으로 보여 주고, 사람이 손으로 쓰지 않아도 **작업 기록에서 대신 써 준다**. 사람·Claude·노트·스크립트가 모두 같은 줄을 쓰므로 AI와 주고받기도 쉽다.
[`DESK_REPRO.md`](DESK_REPRO.md)의 흐름은 이 스크립트로 쓰자는 것이 이 안의 권고다(Q26).

## 1. 생김새

```text
# FLOWS/monthly.eqs — 월간 전망: 새 원자료로 전망·보고서까지
param scenarios = base oil20 wy_m2 krw10

## 자료
data build --inbox ask --use            # 새 원자료로 회차를 만들고 바꾼다
assemble main --stop-on error           # 조립·틀·외생 자료 끝 검사

## 추정
est --adopted --adopt if_pass           # 채택한 식을 다시 추정, 기준을 통과한 식만 새 계수 채택

## 과거 재현
hs main --range 2005Q1:last
expect hs Y.rmspe < 1.5% --flag         # 어긋나면 표시하고 계속

## 전망
sim {scenarios} --model main --range next:12

## 결과물
note run notes/자료점검.md
report new reports/전망_{vintage}.md --from reports/전망_지난달.md
export view:core_hs view:risk --xlsx exports/전망_{vintage}.xlsx
```

명령줄에서 돌리면(예시 수치):

```text
> equion run FLOWS/monthly.eqs
[1/9] data build --inbox ask --use       국민계정_2026-12.xlsx → 출처 na? [Y/n] y · d2026-12a · 개정 4분기   ✓
[2/9] assemble main --stop-on error      문제 0                                                 ✓
[3/9] est --adopted --adopt if_pass      10식 중 9 채택 · demand:I 기준 미달(RR t −0.9) → 옛 계수   !
[4/9] hs main --range 2005Q1:last        hs:hs_0040 · Y RMSPE 0.8%                              ✓
[5/9] expect hs Y.rmspe < 1.5%           0.8% < 1.5%                                            ✓
[6/9] sim base oil20 wy_m2 krw10 …       sim:2026-12_base 외 3 · 2026년 성장률 1.7%              ✓
[7/9] note run notes/자료점검.md          구역 5 새로                                             ✓
[8/9] report new reports/전망_d2026-12a.md   구역 6 · 숫자 바뀐 칸 23                              ✓
[9/9] export view:core_hs view:risk …    exports/전망_d2026-12a.xlsx                            ✓
기록  run:monthly_0007 · 표시 1 · 종료 코드 0
```

## 2. 문법 한눈에

| 줄 | 뜻 |
|---|---|
| `# …` | 주석(줄 끝에도) |
| `## 제목` | 단계 묶음 제목 — Desk 흐름 화면의 칸이 된다 |
| `param 이름 = 값 …` | 매개변수와 기본값. 실행할 때 `--set 이름=…`으로 바꾼다(지금 `equion run`의 `--set`과 같다) |
| `<명령> …` | 등록부의 명령 한 줄 — 터미널에서 치는 것과 같다. 앞의 `equion`은 써도 되고 빼도 된다 |
| `{이름}` | 매개변수나 내장 값(`{vintage}`·`{last}`·`{today}`·`{model}`)을 바꿔 넣는다. 실행 기록에는 바꿔 넣은 뒤의 줄이 남는다 |
| `expect <대상> <조건> --stop·--flag` | 확인 — 어긋나면 멈추거나(`--stop`) 표시하고 계속(`--flag`) |
| `run 다른.eqs` | 다른 스크립트를 포함한다(레고) |
| `py scripts/x.py` | Python 단계 — 명령줄에서만 돈다. Desk 앱 안에서는 실행하지 않고 터미널에 붙여 넣는다(§6-1) |

**일부러 없는 것**: 반복문·조건문·변수 계산·셸 명령. 시나리오 여럿처럼 되풀이할 것은 명령이 목록을 받고, 판단은 명령의 정책(`--adopt if_pass`·`--stop-on`)과 `expect`로 한다.
이것으로 모자라면 Python(`equion run x.py`)이다. 그래서 스크립트는 **위에서 아래로 읽으면 무엇이 일어날지 다 보이고**, 실행 전 미리보기(`--dry-run`)가 정확하며,
AI가 써도 임의의 코드가 돌지 않는다(등록부가 허용 목록 — K1).

## 3. 쓰지 않아도 생긴다 — Desk가 대신 쓰는 길

| 길 | 어떻게 |
|---|---|
| 작업 기록에서 | 작업 기록 띠에서 기록 몇 개를 고르고 '스크립트로 저장' — 그 기록들의 명령이 차례로 들어간다. 탐색하며 한 일을 그대로 굳힌다 |
| 카드에서 | 결과 카드마다 '스크립트에 넣기' — 그 결과를 낸 명령 한 줄을 고른 스크립트 끝(또는 고른 제목 아래)에 |
| 흐름 화면에서 | 단계를 넣고 빼고 끌어 옮기면 스크립트의 줄이 바뀐다. 거꾸로 스크립트를 글로 고치면 화면이 바뀐다(두 길) |
| 노트에서 | 노트의 ```` ```equion ```` 블록은 같은 문법이다. '노트를 스크립트로'는 글을 빼고 블록만, '스크립트를 노트로'는 단계마다 글 쓸 자리를 둔다 |
| 결과에서 거꾸로 | 모든 실행 기록에 "이 결과를 만든 스크립트"(값을 바꿔 넣은 뒤의 줄)가 들어 있다 — 복사해 동료나 Claude에게 |

## 4. AI와 소통할 때

- **짧다**: 한 달 전망 전체가 열 줄 남짓이다. Claude가 프로젝트의 일하는 방식을 문맥을 적게 쓰고 읽는다(K3의 짧은 글과 같은 생각).
- **같은 말**: 사람이 터미널에서 치는 것, Claude가 치는 것, 노트의 블록, 스크립트가 모두 같은 줄이다. Claude의 답에 든 줄은 그대로 붙여 넣어 돌린다.
- **부탁이 쉽다**: "monthly.eqs를 `--set scenarios=base`로 돌려 줘", "3단계부터 다시", "이 스크립트에 환율 시나리오를 넣어 줘".
- **제안이 쉽다**: Claude의 제안(K6)이 스크립트의 차이 몇 줄로 온다 — 제안 카드에서 바뀔 줄을 보고 적용한다.
- **설명이 쉽다**: "이 숫자는 어떻게 나왔나?"에 실행 기록의 스크립트와 단계별 기록 이름으로 답한다(§2.4-8의 근거 기록).
- **안전하다**: 등록부의 명령만 돈다. Claude가 쓴 스크립트도 정의 파일을 바꾸는 줄(`adopt`·`propose apply` 등)은 실행 전 미리보기에 따로 표시된다.

## 5. 명령과 다른 형식과의 관계

| 명령 | 하는 일 |
|---|---|
| `equion run <스크립트.eqs> [--set 이름=값] [--from 줄·제목] [--dry-run]` | 실행 → 실행 기록. `--dry-run`이면 할 일만(지금 `equion run`의 선택지를 그대로 쓴다 — `--fail-on`·`--threads`·`--redact` 등) |
| `equion check <스크립트.eqs>` | 실행 없이 문법·명령 이름·부품 이름·매개변수 검사(지금 `check`가 `.txt`·`.py`를 받는 것에 더한다) |
| `equion run --replay <실행 기록>` | 그때의 스크립트·회차·정의 사본·판으로 그대로 다시 |
| `equion script new --from-records <기록…>` | 작업 기록의 명령으로 스크립트 초안 |
| `equion script export <스크립트> --py` | 같은 일을 하는 Python 스크립트(워크파일 API)로 |

| 형식 | 맡는 것 |
|---|---|
| 정의 TOML·CSV·방정식 파일 | **무엇** — 시리즈·식·블록·모형·가정·보정항·시나리오·보기(부품) |
| Equion 스크립트 `.eqs` | **순서와 판단 규칙** — 무엇을 어떤 차례로 돌리고 어디서 멈추나(흐름) |
| 노트 `.md` | 탐색 — 같은 줄에 글과 결과를 곁들인다 |
| Python `.py` | 스크립트로 모자란 일 — 반복·조건·직접 계산(`equion run`, 앱 밖에서) |

[`DESK_REPRO.md`](DESK_REPRO.md) §3의 흐름 TOML 초안은 같은 내용을 이 스크립트로 쓰는 것으로 바꾸기를 권한다. 줄 하나가 명령 하나라 터미널·노트·AI와 말이 같고, 더 짧다.

## 더할 것과 정할 것

| 단계 | 더할 것 |
|---|---|
| E2 보강 | 스크립트 해석기(줄 → 등록부의 명령 — 명령줄과 같은 함수), `param`·`{…}`·`expect`·`run`, `equion run`·`check`가 `.eqs`를 받기, `script new·export` |
| E1 보강 | 실행 기록에 바꿔 넣은 뒤의 스크립트·단계별 기록 이름·상태 |
| D3 보강 | 흐름 화면 = 스크립트의 단계 보기·고치기, '스크립트로 저장'·'스크립트에 넣기' |

| # | 질문 | 추천 | 다른 길 |
|---|---|---|---|
| Q26 | 흐름의 형식 | **Equion 스크립트(`.eqs`, 명령 한 줄씩)** — 터미널·노트·AI와 같은 말 | 흐름 TOML(`DESK_REPRO.md` §3 초안) / Python만 |
| Q27 | 스크립트에 반복·조건을 넣나 | **넣지 않는다** — 목록 인자·정책·`expect`로, 모자라면 Python | 단순한 반복·조건을 넣는다(읽기·미리보기가 어려워지고 AI가 쓴 것을 검토하기 힘들다) |
| Q28 | `expect --stop`에 걸렸을 때의 종료 코드 | **지금 약속(0·1·2·3)을 바꾸지 않고 그 안에서 고른다** — 정할 때 CHANGELOG에 | 새 종료 코드를 더한다(자동화 약속이 바뀐다 — D15) |
