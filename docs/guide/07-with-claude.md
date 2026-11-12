# 가이드 7. Claude와 함께

Claude Code에게 모형 작업을 맡기는 사람의 길입니다. Claude는 사람과 **같은 명령**을 쓰고 **같은 기록**을 남깁니다 — 그래서 Claude가 한 일은
`work list`·`history list`에 그대로 보이고, 결론에는 근거 기록의 이름이 붙고, 마음에 들지 않으면 되돌립니다.

```console
$ equion new withclaude --template desk
$ cd withclaude
```
<!-- out -->
```text
$ equion new withclaude --template desk
새 프로젝트 withclaude:
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
  cd withclaude
  equion assemble main

$ cd withclaude
```

## 1. 준비 — 안내와 스킬

예제 프로젝트에는 `CLAUDE.md`가 있어, 그 폴더에서 Claude Code를 열면 먼저 **모형 작업 안내**(`equion guide`)를 읽습니다. 안내에는 꼭 지킬 것
(계산은 명령으로 · 결론에 근거 기록 · 결과는 고치지 않는다 · 정의 파일은 명령으로 먼저 · "제안만"이면 `propose`), 프로젝트 지도, 명령·분석 표,
판단 기준, 보고하는 꼴이 들어 있습니다. 내 프로젝트라면 `CLAUDE.md`에 "먼저 `equion guide`를 읽는다"는 줄 하나를 넣으면 됩니다.

```python
from pathlib import Path

print(Path("CLAUDE.md").read_text(encoding="utf-8"))
```
<!-- out -->
```text
# 이 폴더는 Equion 프로젝트입니다

모형 작업을 하기 전에 안내를 읽으세요: `equion guide`(규칙·프로젝트 지도·명령·분석·판단 기준·보고 꼴).

- 계산은 `equion` 명령으로(est·hs·sim·an·run) — 결론에는 근거 기록의 이름(`est:…`·`hs:…`·`sim:…`)을 붙입니다.
- `work/`·`DATA/raw/`·노트와 보고서의 결과 구역은 고치지 않습니다. 정의 파일은 명령(`adopt`·`data use`·`data define`·`block add`·
  `scenario define`·`propose`)으로 먼저 — 정의를 한꺼번에 되돌리는 `milestone restore`·`history revert`는 사람에게 먼저 묻습니다.
- 월간 작업: 새 원자료를 `DATA/raw/inbox/`에 → `equion data inbox` → `equion run FLOWS/monthly.eqs --dry-run` → `equion run FLOWS/monthly.eqs`.
```

Claude Code 스킬 초안도 있습니다. 모든 프로젝트에서 쓰려면 `--install user`, 이 프로젝트에서만이면 `--install project`(시킬 때만 쓴다).

```console
$ equion guide --path
$ equion guide skill --install project
```
<!-- out -->
```text
$ equion guide --path
equion\help\guide.md

$ equion guide skill --install project
[guide skill] withclaude\.claude\skills\equion\SKILL.md — Claude Code를 다시 열면 스킬 equion이 보입니다
```

## 2. 부탁하는 말

| 부탁 | Claude가 하는 일 | 확인할 곳 |
|---|---|---|
| "이번 달 원자료가 받은 상자에 들어왔어요. 월간 작업 돌리고 결과 알려 주세요." | `data inbox` → `check` → `run FLOWS/monthly.eqs --dry-run` → 실행 → 자료 점검 → 보고(근거 기록·알아서 한 것·볼 것) | `work show run:…` |
| "소비 식 후보를 찾아 주세요. 채택은 하지 말고." | `est "…" --for demand:CN` 여러 개 → `compare --part` → `hs --swap … --vs` → 근거와 함께 추천 | `work list --kind est` |
| "그 후보로 바꾸는 걸 제안만 해 주세요." | 파일은 그대로, `propose new … --part demand:CN=est:…` | `propose show p1` |
| "유가 30% 시나리오를 만들어 돌려 주세요." | `scenario define oil30 --shock POIL=+30%` → `sim oil30` | `history list`(누가 Claude) · `work show sim:…` |
| "보고서 요약을 써 주세요." | 구역 밖 `## 요약`에 글 — 숫자 구역은 손대지 않는다 | `report check` |

좋은 부탁은 **무엇을 할지와 어디까지 할지**를 함께 말합니다 — "찾아만", "제안만", "채택까지". Claude는 판단이 필요한 곳(틀을 고칠지, 손으로 고친
구역을 덮을지, 채택할지)에서 묻습니다.

## 3. Claude가 한 일 확인하기

Claude Code 안에서 친 명령의 기록·바뀜에는 누가 `Claude`로 남습니다(사람은 `터미널`). Claude가 스크립트를 돌렸으면 Claude로 남는 것은
실행 기록(`run:…`) 하나이고, 그 단계가 만든 기록·바뀜은 `스크립트`(바뀜 기록에는 `(run:…)`처럼 그 실행)로 남습니다. 여기서는 Claude가 했을 일을
같은 명령으로 해 봅니다 — 후보 추정과 제안.

```console
$ equion est demand:CN --as cn_now
$ equion est "CN c Y Y(-1) CN(-1)" --for demand:CN --as cn3
$ equion compare --part demand:CN
$ equion propose new p1 --title "소비 식에 소득 시차를 더한다" --why "est:cn3 — 판단 기준 통과(지금 식은 LM에 걸림), AIC 가장 낮음" --part demand:CN=est:cn3
```
<!-- out -->
```text
$ equion est demand:CN --as cn_now
[est:cn_now] OLS CN · 1970Q2~2019Q4 · n=199   R²adj 0.9999 · SE 0.5029 · DW 1.652 · AIC 294.1 · BIC 304.0
  계수   c 11.647(t 42.990) · Y 0.5869(t 51.970) · CN(-1) 0.1782(t 11.260)
  진단   LM(2) p=0.046 ! · White p=0.485 ✓ · JB p=0.325 ✓ · RESET p=0.484 ✓ · LB(4) p=0.151 ✓
  기준   걸러짐: LM(2) p=0.046
  알아서 한 것  시차·결측으로 표본 시작 1970Q1 → 1970Q2
  기록   est:cn_now (work/est/cn_now/) · demand:CN 후보

$ equion est "CN c Y Y(-1) CN(-1)" --for demand:CN --as cn3
[est:cn3] OLS CN · 1970Q2~2019Q4 · n=199   R²adj 0.9999 · SE 0.4843 · DW 2.001 · AIC 280.1 · BIC 293.3
  계수   c 8.677(t 11.141) · Y 0.6045(t 51.623) · Y(-1) -0.1678(t -4.047) · CN(-1) 0.3885(t 7.172)
  진단   LM(2) p=0.718 ✓ · White p=0.543 ✓ · JB p=0.290 ✓ · RESET p=0.681 ✓ · LB(4) p=0.923 ✓
  기준   통과 · 부호 Y + ✓
  알아서 한 것  시차·결측으로 표본 시작 1970Q1 → 1970Q2
  기록   est:cn3 (work/est/cn3/) · demand:CN 후보

$ equion compare --part demand:CN
[compare] 추정 기록 2
                              식         부품 채택             표본    n   R²adj      SE     DW    AIC    BIC LM(2) p White p   JB p RESET p                  기준
기록
est:cn_now        CN c Y CN(-1)  demand:CN     1970Q2~2019Q4  199  0.9999  0.5029  1.652  294.1  304.0   0.046   0.485  0.325   0.484  걸러짐: LM(2) p=0.046
est:cn3     CN c Y Y(-1) CN(-1)  demand:CN     1970Q2~2019Q4  199  0.9999  0.4843  2.001  280.1  293.3   0.718   0.543  0.290   0.681                  통과

$ equion propose new p1 --title "소비 식에 소득 시차를 더한다" --why "est:cn3 — 판단 기준 통과(지금 식은 LM에 걸림), AIC 가장 낮음" --part demand:CN=est:cn3
[prop:p1] 소비 식에 소득 시차를 더한다 · 열림 · 2026-11-13T05:17:38 · 터미널
  까닭   est:cn3 — 판단 기준 통과(지금 식은 LM에 걸림), AIC 가장 낮음
  바꿀 파일  EQUATIONS/demand.txt · EQUATIONS/adopted.toml
  식     demand:CN ← est:cn3
  카드   work/proposals/p1/proposal.md
```

제안은 **파일을 바꾸지 않습니다**. 사람이 보고 적용하거나 버립니다. 만든 뒤 그 파일이 바뀌었으면 '낡음'으로 적용을 거절합니다.

```console
$ equion propose show p1
$ equion propose apply p1
$ equion history list
```
<!-- out -->
```text
$ equion propose show p1
[prop:p1] 소비 식에 소득 시차를 더한다 · 열림 · 2026-11-13T05:17:38 · 터미널
  까닭   est:cn3 — 판단 기준 통과(지금 식은 LM에 걸림), AIC 가장 낮음
  바꿀 파일  EQUATIONS/demand.txt · EQUATIONS/adopted.toml
  식     demand:CN ← est:cn3
--- a/EQUATIONS/demand.txt
+++ b/EQUATIONS/demand.txt
@@ -1,4 +1,4 @@
 # 수요 블록 — 한 줄에 한 식, '#' 뒤는 설명(문법: docs/explain/equations.md)
-CN c Y CN(-1)            # 소비
+CN c Y Y(-1) CN(-1)      # 소비
 I c Y(-1) R              # 투자
 Y = CN + I + G           # 국민소득(항등식)

--- a/EQUATIONS/adopted.toml
+++ b/EQUATIONS/adopted.toml
@@ -0,0 +1,2 @@
+# 채택표 — 식(부품)마다 채택한 추정 기록. 모형은 이 계수로 푼다(equion adopt가 고친다)
+"demand:CN" = "est:cn3"

$ equion propose apply p1
[prop:p1] 소비 식에 소득 시차를 더한다 · 적용 · 2026-11-13T05:17:38 · 터미널
  까닭   est:cn3 — 판단 기준 통과(지금 식은 LM에 걸림), AIC 가장 낮음
  바꿀 파일  EQUATIONS/demand.txt · EQUATIONS/adopted.toml
  식     demand:CN ← est:cn3
  적용   2026-11-13T05:17:41 · 터미널 · 바뀜 기록 h0002

$ equion history list
[history list] withclaude: 바뀜 2
[h0001] 2026-11-13T05:17:28 · 터미널 · data use d2026-11a
  파일   equion.toml(고침)
  메모   자료 회차 d2026-11a
[h0002] 2026-11-13T05:17:41 · 터미널 · equion propose apply p1
  파일   EQUATIONS/adopted.toml(새로) · EQUATIONS/demand.txt(고침)
  메모   제안 prop:p1 적용: 소비 식에 소득 시차를 더한다
```

마음에 들지 않으면 바뀜 하나를 되돌립니다(`equion history revert h…` — 그 바뀜만 물리고, 되돌리기도 기록에 남는다. 뒤의 바뀜이 같은 곳을
고쳤으면 멈춘다 — [8. 막혔을 때](08-troubleshooting.md#5-되돌리기)). Claude가 명령 없이 직접 고친 파일은 다음 명령 때 '바깥' 바뀜으로 남습니다 —
그래서 안내는 정의 파일을 명령(`scenario define`·`block add`·`data define`·`adopt` …)으로 먼저 고치게 합니다.

## 4. Claude의 보고 읽기

안내가 정한 꼴은 이렇습니다 — 무엇을 했나(실행 기록 이름·자료 회차), 결과마다 근거 기록, **알아서 한 것**, **볼 것**(사람의 판단이 필요한 곳과
다음 명령). 근거 기록은 `equion work show 기록`(짧은 글)·`--md`(카드)·Desk·Lectern에서 엽니다.

## 확인할 것

- [ ] 프로젝트 폴더에서 Claude Code를 열면 `CLAUDE.md`를 따라 `equion guide`를 먼저 읽는다
- [ ] "월간 작업 돌려 줘"에 Claude가 미리보기 → 실행 → 근거 기록 붙은 보고를 한다
- [ ] Claude가 친 명령의 기록·바뀜에 누가 `Claude`(스크립트를 돌렸으면 실행 기록 `run:…`이 Claude, 단계의 기록은 `스크립트`)
- [ ] "제안만"이라고 하면 파일이 바뀌지 않고 `propose list`에 제안이 남는다
- [ ] Claude가 보고서의 숫자 구역을 고치지 않는다(글만)

다음: [8. 막혔을 때](08-troubleshooting.md)
