---
name: equion
description: Equion 프로젝트(equion.toml이 있는 폴더)에서 거시 모형을 다룰 때 — 방정식 추정·과거 재현(HS)·전망·시나리오·자료 회차·분석·노트·보고서·스크립트(.eqs)를 equion 명령으로 하고 결과를 기록 이름으로 보고한다. 방정식 파일(EQUATIONS/*.txt)의 문법, equion 명령의 오류와 종료 코드, 월간 스크립트 돌리기에도 쓴다.
---

# Equion

Equion 프로젝트에서 일할 때의 요약입니다. **처음 한 번은 전체 안내를 읽는다**: `equion guide`(프로젝트 지도·명령 표·분석 표·판단 기준·
보고 꼴). 명령마다 `equion <명령> --help`.

## 규칙

- 계산은 `equion` 명령으로(est·hs·sim·an·run) — 할 때마다 `work/`에 기록이 남는다. 결론에는 근거 기록 이름(`est:…`·`hs:…`·`sim:…`)을 붙인다.
- `work/`·`DATA/raw/`·보고서와 노트의 결과 구역(`<!-- equion:… -->`)은 고치지 않는다.
- 정의 파일은 명령으로 먼저(`adopt`·`data use`·`data define`·`an keep`·`block add`·`block remove`·`model define`·`scenario define`·`note add`·`propose`)
  — 바뀜 기록에 Claude로 남는다. "제안만"이면 `equion propose new`로 남기고 파일은 그대로.
- 정의를 한꺼번에 되돌리는 `milestone restore`·`history revert`는 사람에게 먼저 묻는다 — 시켰어도 무엇이 물려지는지(특히 사람·Desk가 한 바뀜)를 먼저 보인다.
- 판단 기준에 걸린 기록(걸러짐·판단 못 함)의 채택은 사람이 이름을 대고 시켜도 까닭을 보이고 한 번 확인받는다. `work clean --yes`는 미리보기를 보이고 묻는다.
- 후보는 3~5개부터. '무슨 일이 있었나' 같은 물음은 기록을 읽어 답하고 다시 계산하지 않는다. 채택 기록의 표본(`--smpl`)은 `est --adopted`가 그대로 쓴다(블록 줄에 `@smpl` 불필요).
- 거른 후보도 `equion est "식" --for 부품`으로 기록하고 `equion compare`로 견준다.
- 돌리기 전에 `equion check …`·`--dry-run`. 출력은 짧은 글 — 필요한 것만 `--json`.

## 방정식 파일(EQUATIONS/<블록>.txt)

한 줄에 한 식, `#` 뒤는 설명. 최상위 `=`가 없으면 추정식(첫 변수가 목표, `c`는 상수항), `=`가 있고 `c(n)`이 없으면 항등식, `=`와 `c(n)`이 있으면 비선형 추정식.

    CN c Y CN(-1)                 # 추정식 — 소비
    dlog(P) c dlog(Y) dlog(POIL)  # 차분·로그 차분
    Y = CN + I + G                # 항등식
    I c Y(-1 to -2) R @smpl 1990Q1 2019Q4   # 시차 범위·표본

시계열: `X(-1)`·`d(X)`·`dlog(X)`·`@pc(X)`·`@pcy(X)`·`@movav(X,4)`, 지시자 `@seas`·`@trend`·`@d(2008Q4)`·`@step(2020Q2)`, 추정법 `@inst`·`@coef`.
변수 이름은 대소문자를 가리지 않고 함수 이름·`C`는 변수로 못 쓴다.

## 자주 쓰는 명령

```bash
equion assemble main                       # 조립 검사(계산 없이)
equion est demand:CN --sim                 # 부품 추정 · 후보: equion est "CN c Y CN(-1) CN(-2)" --for demand:CN
equion compare --part demand:CN            # 후보 견주기 → equion adopt est:이름
equion hs main                             # 과거 재현 · --swap demand:CN=est:이름 --vs hs:이름
equion sim base oil20                      # 전망·시나리오
equion work list --limit 10                # 기록 · work show 기록 [--md]
equion data inbox                          # 받은 원자료(DATA/raw/inbox/) 미리보기
equion run FLOWS/monthly.eqs --dry-run     # 월간 스크립트 미리보기 → --dry-run 없이 실행 → run --replay run:이름
equion block add single "M2 c Y RL"        # 블록 파일에 식 한 줄 · 빼기 block remove single:M2
equion scenario define oil30 --shock POIL=+30%   # 시나리오 쓰기 → equion sim oil30
equion work show sim:2026-11_base          # 기록 하나 — '알아서 한 것'은 여기서 전부 읽는다(단계 줄은 줄여 보인다)
```

## 종료 코드

0 성공(스크립트면 `!` 표시를 읽어 전한다) · 1 스크립트 오류 · 2 풀이 실패 조건·`expect --stop`·재연에 다름 · 3 입력 오류(없는 파일·부품, 문법,
틀이 맞지 않음, 허용 안 된 명령, 손으로 고친 구역을 덮지 않고 건너뜀 — `note run`·`report update`, 스크립트 안에서는 그 단계가 `!`).
메시지에 고칠 곳과 있는 이름 목록이 나온다 — 그대로 따르고, 사람의 판단이 필요한 것(틀을 고칠지, 손으로 고친 구역을 덮을지, 채택할지)은 묻는다.
스크립트 단계의 기록은 '누가'가 `스크립트`(그 실행 `run:…`) — Claude 이름으로는 실행 기록 하나가 남는다.
