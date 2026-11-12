# Equion — Claude를 위한 모형 작업 안내

이 안내는 Equion 프로젝트에서 모형 작업을 맡은 Claude가 먼저 읽는 글입니다(`equion guide`로 언제든 다시 본다). 사람은 같은 폴더를 Equion Desk·Lectern·
편집기로 보며, 둘이 **같은 명령·같은 기록·같은 파일**을 씁니다. 계산은 늘 `equion` 명령으로 하고, 결론은 기록 이름으로 말합니다.

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
   (특히 그 뒤에 사람·Desk가 한 바뀜 — `equion history list`·`milestone show`)를 보이고 한 번 확인받는다.
   **판단 기준에 걸린 기록(걸러짐·판단 못 함)의 채택은 사람이 이름을 대고 시켜도** 걸린 까닭을 보이고 한 번 확인받은 뒤 `adopt`한다.
   **되돌릴 수 없는 명령(`work clean --yes`)은 미리보기(`work clean`)를 보이고 묻는다.**
5. **"제안만"이면 파일을 고치지 않는다** — `equion propose new --title … --why "근거 기록…" --part 부품=est:… --preview hs:…`.
   사람이 Equion Desk를 쓰고 있으면 `equion desk show prop:p3`(또는 기록 `hs:hs_0003`·부품 `demand:CN`·모형 `model:main`·파일 경로)으로
   그 화면을 사람 앞에 띄운다 — 화면 이동만 한다.
6. **거른 후보도 기록으로 남긴다.** 후보 식은 `equion est "식" --for 부품`으로 기록하고 `compare`로 견준다. 말로만 버리지 않는다.
7. **돌리기 전에 미리 본다.** 스크립트는 `equion check x.eqs` → `equion run x.eqs --dry-run` → `equion run x.eqs`. 원자료를 넣기 전엔 `equion data inbox`.
8. **짧은 글을 읽는다.** 명령의 출력은 짧은 글이 기본이다. 필요한 것만 `--json`·`work show 기록 --json`·기록 폴더의 CSV로 더 본다(문맥을 아낀다).
   `--json`이면 오류도 JSON 하나 — `{"error": {"message", "exit_code", "kind"}}`(표준출력).
9. **일의 크기를 맞춘다.** 후보는 3~5개부터 견주고 사람과 이야기한 뒤 넓힌다. "무슨 일이 있었나"·"지금 어떤가" 같은 물음에는 기록을 읽어
   답하고(`work list`·`history list`·`work show`) 다시 계산하지 않는다. 사람의 부탁으로 정의를 바꿨으면 보고에 "누가 시켜서 무엇을"을 적는다
   (바뀜 기록에는 누가 Claude로만 남으므로, 다음 세션이 알 수 있게).
10. **'알아서 한 것'을 전한다.** 기록의 '알아서 한 것'(채움·결측 제외·실패 대체·건너뛴 단계 등)은 사람에게 그대로 알린다. 스크립트의 단계 줄·끝 줄은
   한 줄로 줄여 보이므로 전부는 그 기록에서 읽는다 — `equion work show sim:…`(또는 `hs:…`·`est:…`·`run:…`).

## 2. 프로젝트 지도

| 위치 | 무엇 | 누가 고치나 |
|---|---|---|
| `equion.toml` | 자료 정의 파일·지금 회차 `[data] vintage` · 블록 `[block]` · 모형 `[model.이름]`(blocks·include·exclude) · 묶음 `[group]` · 판단 기준 `[criteria]` · `[hs]`·`[forecast]` 기본값 | 사람·명령(`data use`·`model define`·`block define`·`group define`) |
| `EQUATIONS/<블록>.txt` | 블록 = 방정식 파일 하나(한 줄에 한 식, `#` 뒤는 설명) | 사람·명령(`adopt`·`block add`·`block remove`) |
| `EQUATIONS/adopted.toml` | 채택표 `"demand:CN" = "est:cons_c5"` — 모형은 이 계수로 푼다 | 명령(`adopt`·`est --adopted --adopt`·`propose apply`·`block remove`) |
| `DATA/raw/` · `DATA/raw/inbox/` | 원자료(받은 그대로 — 고치지 않는다) · 새로 받은 파일을 놓는 곳 | 명령(`data add`·`data build --inbox`) |
| `DATA/series.toml` · `DATA/derived.txt` | 자료 정의(불러오기 틀·시리즈·변환) · 파생식 | 사람·명령(`data define` — 출처의 틀과 시리즈 · `an keep` · `data add --source`·`data build --inbox` — 출처의 `file`) |
| `ASSUMPTIONS/` · `ADDFACTORS/` · `SCENARIOS/` | 가정 경로(CSV) · 보정항 규칙 · 시나리오(충격·식 보정) | 사람 · 시나리오는 명령도(`scenario define`·`scenario remove`) |
| `VIEWS/*.toml` | 보기 — 어느 시리즈를 어떤 모양으로 볼지(계산의 입력이 아니다) | 사람·명령(`view define`) |
| `FLOWS/*.eqs` | 스크립트 — 원자료에서 보고서까지의 순서 | 사람·`script new` |
| `notes/*.md` · `reports/*.md` | 노트(명령 블록 + 결과 구역) · 보고서(결과만) | 글은 사람·Claude, 구역은 명령(`note run`·`note add`·`report add`·`report update`) |
| `work/` | 기록 `est/` `hs/` `sim/` `an/` `run/` · 자료 회차 `data/` · `log.jsonl` · 바뀜 기록 `history/` · 제안 `proposals/` | 명령만(덧붙이기) |
| `work/milestones/` | 이정표 — 중요한 때의 정의 사본·자료 회차·고정한 기록 | 명령(`milestone make` — 되돌리기 `milestone restore`는 사람이 시킬 때) |
| `exports/` | 엑셀(`export --xlsx`)·묶음(`bundle make`) — 보내는 파일 | 명령 |

**이름**: 부품(식 하나) `블록:목표` — `demand:CN`. 기록 `종류:이름` — `est:cons_c5` · `hs:hs_0003` · `sim:2026-11_base` · `an:unitroot_0001` ·
`run:monthly_0001`. 자료 회차 `d2026-11a`. 영문·숫자·`_`만(한글은 `desc`·제목에). 기간 `2005Q1`·`2020M3`·`2019`, 상대 기간 `2005Q1:last`·`last-39:last`·`next:8`.

## 3. 명령

모든 명령은 프로젝트 폴더(또는 그 하위 폴더 — 위로 올라가며 `equion.toml`을 찾는다)에서 돌거나 `-p 폴더`를 받는다. 출력은 짧은 글, `--json`이면 전체.
**경로**: 있는 파일을 가리키는 상대 경로는 지금 폴더에서 먼저, 없으면 프로젝트 폴더에서 찾는다(`-p`로 다른 폴더에서 불러도
`data add DATA/raw/inbox/x.csv`·`check EQUATIONS/demand.txt`가 된다). 새로 만드는 파일(보고서·노트·내보내기·묶음·스킬)의 상대 경로는
프로젝트 폴더 기준이고, 보고서·노트·내보내기·스크립트는 프로젝트 안만 받는다.

<!-- equion:auto commands -->
| 명령 | 하는 일 | 동작 |
|---|---|---|
| `run` | 스크립트를 실행한다 — .py는 보고서 폴더(out/), Equion 스크립트 .eqs는 실행 기록(work/run/) |  |
| `check` | 실행 없이 방정식 파일·스크립트를 검사한다 |  |
| `info` | 데이터·워크파일·방정식 파일·보고서 폴더 요약(경로 없으면 실행 환경) |  |
| `convert` | 옛 저장 형식(레거시 pickle·.wt·.mmw)을 워크파일(.eqw)로 |  |
| `new` | 새 프로젝트 폴더(예시 데이터·방정식·스크립트) |  |
| `assemble` | 프로젝트의 모형을 조립해 검사한다(계산 없이 — 내생·외생·겹친 목표·모르는 변수) |  |
| `model` | 프로젝트의 모형 정의 — equion.toml의 [model.이름]을 더하거나 고친다 | define |
| `block` | 프로젝트의 블록 — equion.toml의 [block]에 블록(방정식 파일 하나)을 더하거나 고친다 | define · add · remove |
| `group` | 프로젝트의 묶음 — equion.toml의 [group](이름 붙인 시리즈 묶음 — 분석의 대상) | list · define · remove |
| `desk` | Equion Desk(데스크톱 앱)에 알린다 — 떠 있는 앱이 그 화면을 연다 | show |
| `view` | 프로젝트의 보기(VIEWS/*.toml) — 어느 시리즈를 어떤 모양으로 볼지 | list · define |
| `milestone` | 이정표 — 중요한 때의 정의·자료 회차·고정한 기록을 이름으로 묶어 두고, 지금과 견주고, 되돌린다 | list · make · show · restore |
| `bundle` | 프로젝트 묶어 보내기(zip) · 묶음 열기 — 다른 PC로 옮길 때 | make · open |
| `scenario` | 프로젝트의 시나리오(SCENARIOS/*.toml) — 목록·보기·쓰기·지우기(풀기는 equion sim) | list · show · define · remove |
| `ident` | 프로젝트의 항등식을 보이거나(--check) 실측으로 계산해 견준다 |  |
| `data` | 프로젝트의 자료 회차 — 목록·원자료 넣기·만들기·바꾸기·차이·영향 | list · add · build · inbox · preview · define · use · diff · impact |
| `est` | 식 하나를 추정해 기록을 남긴다(부품 또는 식 글자 — 후보) |  |
| `adopt` | 추정 기록을 부품의 채택 계수로(블록 파일의 줄·채택표를 고치고 바뀜 기록에) |  |
| `compare` | 기록 비교 — 추정 후보(적합·진단·기준·단독 모의) 또는 HS(변수별 RMSPE) |  |
| `hs` | 과거 재현을 풀고 기록을 남긴다(바꿔 끼우기·전후 비교·그때 그대로 다시) |  |
| `sim` | 전망·시나리오를 풀고 기록을 남긴다(가정 세트·보정항·시나리오 파일) |  |
| `propose` | 제안 — 파일을 바꾸기 전에 보여 주기(만들기·목록·보기·적용·버림) | new · list · show · apply · drop |
| `export` | 기록의 값·값의 종류·출처를 엑셀로 |  |
| `work` | 작업 기록 — 목록·보기·고정·메모·정리 | list · show · pin · unpin · memo · clean |
| `history` | 바뀜 기록 — 정의 파일이 누가·언제·어떻게 바뀌었나, 되돌리기 | list · show · revert |
| `an` | 분석 — 등록부의 분석 하나 = 기록 하나(an:) · 목록·남기기 | list · keep · <분석>(아래 표) |
| `note` | 노트 — ```equion 블록을 실행해 결과 구역을 채운다 · 검사 | run · check · add |
| `report` | 보고서 — 결과만 보내기(명령 블록 없이) · 검사 · 새 기록으로 바꾸기 | new · add · check · update |
| `script` | 스크립트(.eqs) — 작업 기록으로 초안 · 같은 일을 하는 Python으로 | new · export |
| `guide` | Claude(AI)용 모형 작업 안내 · Claude Code 스킬 초안 |  |
<!-- /equion:auto -->

자주 쓰는 꼴:

```bash
equion assemble main                                  # 조립 검사(계산 없이) — 내생·외생·겹친 목표·모르는 변수
equion data list                                      # 자료 회차(* 지금)
equion data build --use                               # 정의대로 회차를 만들고 바꾼다(같은 내용이면 그대로)
equion est demand:CN --sim                            # 부품 하나 추정(+ 식 하나의 동태 모의)
equion est "CN c Y CN(-1) CN(-2)" --for demand:CN --as cons_c5   # 후보 식(파일은 그대로)
equion compare --part demand:CN                       # 그 부품의 후보 모두 — 적합·진단·기준
equion hs main --swap demand:CN=est:cons_c5 --vs hs:hs_0001       # 바꿔 끼워 과거 재현, 전후 견주기
equion adopt est:cons_c5                              # 채택(블록 파일의 줄·채택표 — 바뀜 기록에)
equion sim base oil20 --model main                    # 전망·시나리오
equion an unitroot core --trend ct                    # 분석(아래 표) — an list · an <분석> --help
equion work list --kind est --limit 10                # 기록 목록 · work show 기록 [--md]
equion block add single "M2 c Y RL"                   # 블록 파일에 식 한 줄(블록이 없으면 먼저 block define single) · 빼기 block remove single:M2
equion scenario define oil30 --shock POIL=+30%        # 시나리오 쓰기(SCENARIOS/oil30.toml) → equion sim oil30
equion note add notes/invest.md --record an:unitroot_0001   # 노트 끝에 그 기록의 명령 블록과 결과 구역
equion milestone make m2026_11 --note "11월 전망 확정"  # 이정표(정의 사본·회차·고정한 기록) · milestone show 이름 — 지금과
equion history list                                   # 정의 파일이 누가·언제·어떻게 바뀌었나
equion history revert h0007                           # 바뀜 하나 되돌리기 — milestone restore와 함께 사람에게 먼저 묻는다
```

## 4. 판단 기준과 기록 읽기

- **판단 기준** `[criteria]`: 기대 부호(`[criteria.signs]`), 진단 p값(`tests` — p < `alpha`면 걸러짐), `t_min`. 추정 기록의 '기준' 줄이
  통과·걸러짐과 까닭을 적는다. `est --adopted --adopt if_pass`는 통과한 식만 새 계수로 채택하고, 걸린 식은 옛 채택 계수를 쓰며 `!`로 표시한다.
  **옛 채택 계수가 없는 식**(처음 돌릴 때)은 걸려도 이번 자료로 추정한 계수로 푼다 — HS·전망 카드의 '채택 기록 없이 지금 자료로 추정'. 결론에 그렇게 말한다.
- **기록 하나**: `equion work show est:cons_c5`(짧은 글) · `--md`(카드 `summary.md` — 표와 차트) · `--json`(record.json). 값은 기록 폴더의 CSV
  (`est`: coefs.csv·series.csv · `hs`: stats.csv(변수별 RMSPE·MAE)·solved.csv · `sim`: levels.csv·annual.csv·diff.csv · `an`: table_1.csv …).
- **HS 기록**에는 조립 명세(`assembly.json` — 쓴 식의 글자·계수·자료 회차·정의 파일 해시)가 있어 `equion hs --replay hs:…`가 그때 그대로 다시 푼다.
- **낡음**: 기록의 자료 회차나 정의 파일이 지금과 다르면 노트·보고서 검사(`note check`·`report check`)가 '낡음'으로 알린다. `work list`의
  `회차 다름(d2026-11a)`은 그 기록을 지금과 다른 회차로 계산했다는 표시다(실행 기록은 끝났을 때의 회차로 본다). 저절로 다시 계산하지 않는다.
- **보정항 값**(전망 카드의 `demand:CN last(+1.36)`)은 그 식의 잔차 단위다 — 수준 식이면 목표변수 수준(같은 단위), `dlog(…)` 식이면 로그 차분.
- **상태**: HS·전망의 기간마다 정상 · 일부식 제외(입력 결측) · 실패 대체(미수렴 → 실측) · 실패. 실패 대체가 있으면 결론에 그 기간을 말한다.

**표본과 채택**: `est 부품 --smpl 1980Q1:last`로 만든 기록을 채택하면 그 표본 표기가 기록에 남고, `est --adopted`는 채택 기록과 같은 표본 ·
공분산 · 추정법으로 다시 추정한다(끝이 `last`면 지금 자료 끝까지 늘어난다). 블록 줄에 `@smpl`을 넣을 필요가 없다 — `@smpl`은 두 시점이 다 있어야 하고
`last`를 받지 않는다. 해만 적은 구간(`--smpl 2000:2019`)의 끝은 그 해의 마지막 기(2019Q4)다.

**파일 읽기(Windows)**: 정의 파일·노트·보고서는 BOM 없는 UTF-8이다. Windows PowerShell 5.1의 `Get-Content`는 이것을 깨뜨려 보이므로
`Get-Content -Encoding utf8`이나 파일 읽기 도구로 읽는다(`equion` 명령의 출력은 파이프·파일로도 UTF-8이다).

## 5. 분석·노트·보고서

분석 하나 = 명령 하나 = 기록 하나(`an:`) = 카드 하나. 옵션은 `equion an <분석> --help`.

<!-- equion:auto analyses -->
| 분석 | 이름 | 대상 | 만드는 것 | 결과 |
|---|---|---|---|---|
| `summary` | 요약 | 시리즈 · 묶음 · 식(log(Y) 등) | — | 구간·결측·끝 값·단위·값의 종류 표, 수준 차트 |
| `unitroot` | 단위근 | 시리즈 · 묶음 · 식(log(Y) 등) | — | 시리즈 × ADF·KPSS·판단 표 |
| `coint` | 공적분 | 묶음 · 식(log(Y) 등) | — | 순위 검정 표 |
| `diag` | 식 진단 | 부품(블록:목표) · 추정 기록 | — | 진단 검정 표·Chow·CUSUM 차트 |
| `fcsteval` | 예측 평가 | 기록 여럿 | — | RMSE·MAE·Theil U·MSE 분해, Diebold-Mariano |
| `split` | 요인 나누기 | 기록 여럿 | — | 변수·연도마다 앞·뒤·바뀜과 자료·가정·식의 몫 표, 단계마다 다시 푼 값, 막대 차트 |
| `stability` | 동태 안정성 | 모형 | — | 고윳값 표·판정 |
| `multipliers` | 충격 승수 | 모형 | — | 기간별 반응 표·차트 |
| `seas` | 계절조정 | 시리즈 | 시리즈 정의(series.toml) | 실측·계절·추세·불규칙·조정 표와 차트 |
| `genr` | 파생 | 이름 = 식 | 파생식(derived.txt) | 값 표·차트 |
| `ecm` | 오차수정모형 | 식(log(Y) 등) | 식 후보(est:) | 장기식·조정 속도·반감기·단기식 |
| `var` | VAR | 묶음 · 식(log(Y) 등) | 식 후보(est:) | 계수·시차 고르기·Granger·안정성 표, 충격반응 차트 |
| `vecm` | VECM | 묶음 · 식(log(Y) 등) | 식 후보(est:) | α·β·Γ 표 |
| `system` | 시스템 추정 | 블록 | 식 후보(est:) | 계수·식마다 통계 표 |
| `stats` | 기술 통계 | 시리즈 · 묶음 · 식(log(Y) 등) | — | 시리즈마다 관측치·평균·표준편차·사분위·왜도·첨도·Jarque-Bera 표 |
| `hist` | 히스토그램 | 시리즈 · 식(log(Y) 등) | — | 구간별 도수·비율·정규 기대도수 표, 막대 차트 |
| `acf` | 자기상관 | 시리즈 · 식(log(Y) 등) | — | 시차별 자기상관·편자기상관·Q·p값 표, 막대 차트(95% 한계) |
| `corr` | 상관 | 묶음 · 식(log(Y) 등) | — | 상관 행렬·p값·공분산·쌍마다 표, 색 격자(둘이면 산점도) |
| `xcorr` | 교차상관 | 식(log(Y) 등) | — | 시차별 교차상관 표, 막대 차트(95% 한계) |
| `granger` | Granger 인과 | 묶음 · 식(log(Y) 등) | — | 원인 → 결과마다 F·p값 표, p값 행렬 |
| `fevd` | 분산분해 | 묶음 · 식(log(Y) 등) | — | 반응 변수마다 기간별 분산분해(%) 표·차트 |
| `convert` | 주기 변환 | 시리즈 · 묶음 · 식(log(Y) 등) | — | 변환한 값 표·차트 |
| `stochastic` | 확률적 모의 | 모형 | — | 변수마다 평균·표준편차·5·50·95% 표, 평균과 90% 띠 차트 |
<!-- /equion:auto -->

- **만드는 분석**(계절조정·파생)은 `equion an keep an:…`으로만 자료 정의가 된다(그 뒤 `data build`). **부품을 내는 분석**(ECM·VAR·VECM·시스템)은
  `an keep`으로 식 후보(`est:`)가 되고 `compare`·`hs --swap`·`adopt`로 이어진다.
- **노트** `notes/*.md`: ```` ```equion ```` 블록에 명령을 적고 `equion note run notes/x.md`(블록 바로 아래에 결과 구역). 글은 블록 밖에 쓴다.
- **보고서** `reports/*.md`: 결과만 — `equion report new 이름` → `equion report add 이름 sim:… --rows Y,CN --show yoy --annual`. 새 기록으로는
  `report update`(차이를 보이고, 손으로 고친 구역은 `--force` 없이 덮지 않는다). 구역 밖의 글(`## 요약`의 `(글)` 자리 등)은 사람이 "써 달라"고 할 때
  Claude가 쓴다 — 월간 작업만 시켰으면 초안을 보고에 붙이고 넣을지 묻는다.

<!-- equion:auto allowed -->
| 어디서 | 부를 수 있는 명령 |
|---|---|
| 노트의 ```` ```equion ```` 블록 | `an` · `assemble` · `compare` · `data diff` · `data impact` · `data list` · `est` · `hs` · `ident` · `sim` · `work list` · `work show` — 정의 파일을 바꾸는 줄(`est --adopt`·`an keep`)은 안 된다 |
| 스크립트 `.eqs` | 노트의 것 + `adopt` · `check` · `data add` · `data build` · `data inbox` · `data use` · `export` · `note check` · `note run` · `report add` · `report check` · `report new` · `report update` · `work memo` · `work pin` |
<!-- /equion:auto -->

## 6. 스크립트와 월간 작업

`FLOWS/*.eqs`는 한 줄이 명령 하나인 스크립트다(`# 주석` · `## 제목` · `param 이름 = 값` · `{이름}` · `expect … --flag` · `run 다른.eqs` · `py x.py`).
반복·조건은 없다 — 모자라면 `equion script export x.eqs --py`. 새 자료가 오면:

```bash
equion data inbox                                     # 1. DATA/raw/inbox/의 새 파일 — 짝지을 출처·틀 검사(미리보기 — 넣기는 스크립트 1단계)
equion check FLOWS/monthly.eqs                        # 2. 실행 없이 검사
equion run FLOWS/monthly.eqs --dry-run                # 3. 할 일 — 단계·바꾸는 파일·실행 때 정해지는 값
equion run FLOWS/monthly.eqs                          # 4. 실행 → 실행 기록 run:monthly_NNNN
equion work show run:monthly_0001                     # 5. 단계마다 상태·기록 — ! 단계는 사람에게 알린다
equion data diff                                      # 6. 자료 — 지난 회차 → 지금: 새 기간·개정(시리즈·기간·크기)
equion data impact                                    #    그 개정이 닿는 식·모형
equion ident demand:Y --check --range last-7:last     #    항등식이 새 자료에서도 맞나(개정이 한 시리즈에만 오면 어긋난다)
equion work list --kind hs --limit 3                  # 7. 지난달과 — 지난 HS 기록을 찾아
equion compare hs:hs_0005 hs:hs_0007                  #    변수별 RMSPE 전후(지난 HS 기록이 없으면 첫 실행 — 견줄 것이 없다고 말한다)
equion run FLOWS/monthly.eqs --from "과거 재현"        # 식을 손본 뒤 그 단계부터
equion run --replay run:monthly_0001                  # 그때 그대로 다시 — 단계마다 같음·다름
```

- `--set 이름=값`으로 매개변수(목록은 띄어 쓴 값 — `--set scenarios="base oil20"`).
- 스크립트 단계가 만든 기록·바뀜 기록의 '누가'는 `스크립트`(바뀜 기록에는 `(run:monthly_0003)`처럼 그 실행)이고, Claude가 돌린 것으로 남는
  것은 실행 기록 `run:…` 하나다. 보고할 때는 `run:` 이름과 단계가 만든 기록 이름을 함께 말한다.
- 손으로 고친 노트·보고서의 결과 구역은 `note run`·`report update`·`report add --key`가 덮지 않는다 — 명령줄에서는 종료 코드 3, 스크립트에서는
  그 단계가 `!`(까닭과 함께)이고 실행은 이어 간다. 그 구역을 덮을지는 사람에게 묻는다(`--force`).
- 실행이 끝나지 못하면(Desk의 '취소'·프로세스 끝남) 다음 실행이 그 이름으로 '끝나지 못함(취소·중단)' 기록을 남기고 새 번호를 쓴다 — 그 실행의
  바뀜 기록이 가리키는 이름이 다른 실행과 겹치지 않는다. 그 기록은 `--replay`로 다시 하지 못한다.
- `data build --inbox ask`는 터미널이 아니면 묻지 않고 짝이 하나이고 틀이 맞는 파일만 넣는다. 짝이 없거나 틀이 맞지 않으면 아무것도 넣지 않고 까닭을 보인다
  — 그때는 사람에게 묻거나 `series.toml`의 `[source.이름] inbox = "글롭"`을 제안한다.
- 받은 파일은 스크립트의 자료 단계(`data build --inbox ask --use`)가 넣는다 — 스크립트 전에 따로 `data build`를 하지 않는다(두 번 하게 된다).
- 숫자가 이상해 보이면(새 기간이 모든 시리즈에서 같은 비율, 한 시리즈만 개정 등) 계산을 고치지 말고 그대로 사람에게 묻는다 — 원자료는 사람이 확인한다.
- 탐색한 일을 굳히려면 `equion script new 이름 --from-records 기록…`(초안 — 고쳐 쓴다).

## 7. 종료 코드와 흔한 문제

| 코드 | 뜻 | 할 일 |
|---|---|---|
| 0 | 성공(스크립트면 `!` 표시가 있을 수 있다) | `!` 단계를 읽고 전한다 |
| 1 | 스크립트 오류(Python 예외·`expect`의 모르는 지표·노트 블록의 명령 실패) | 메시지의 줄·이름을 고친다 |
| 2 | 풀이 실패 조건(`--fail-on`) · 스크립트의 `expect --stop` · `--replay`에 다른 단계 | 걸린 기간·지표·단계를 보고 사람에게 알린다 |
| 3 | 입력 오류 — 없는 파일·부품·모형, 문법, 틀이 맞지 않음, 모르는 `--set`, 허용 안 된 명령, 손으로 고친 구역을 덮지 않고 건너뜀(`note run`·`report update` — 나머지는 했다) | 메시지대로 고치거나 묻는다 |

| 메시지 | 까닭 · 할 일 |
|---|---|
| `없는 부품: demand:ZZ (있는 부품: …)` | 부품은 `블록:목표` — `equion assemble`·괄호 안 목록에서 고른다 |
| `지금 자료 회차가 없습니다` | `equion data build --use` |
| `틀이 맞지 않습니다` · `새 파일에 없는 열` | 받은 파일의 열 이름·시트가 바뀌었다 — 사람에게 보이고 `series.toml`의 틀을 고칠지 묻는다 |
| `짝지을 출처가 없습니다` · `짝이 여럿입니다` | 받은 파일 이름이 출처와 맞지 않는다 — 어느 출처인지 묻고 `data add 파일 --source 이름` |
| `기준 미달 …` (`!`) | 판단 기준에 걸린 식 — 옛 계수를 쓴다. 후보를 찾아 `est … --for 부품` → `compare` → 사람이 `adopt` |
| `기준 판단 못 함 …` (`!`) | 그 추정법이 기준의 검정을 계산하지 않았다(c(n) 식 등 — 까닭이 괄호에) — 통과로 보지 않고 채택하지 않는다. 사람에게 알리고 판단을 묻는다 |
| `손으로 고쳤습니다 — 덮으려면 --force` | 보고서·노트의 결과 구역을 사람이 고쳤다 — 덮지 말고 사람에게 묻는다 |
| `노트에서 부를 수 없습니다` · `스크립트에서 부를 수 없습니다` | 허용 목록 밖(위 표) — 바꾸는 명령은 터미널에서 |
| `채택 기록 없이 지금 자료로 추정` | 그 식은 아직 채택 계수가 없다 — 정상이지만 결론에 말한다 |

## 8. 사람에게 보고하는 꼴

짧게, 근거 기록을 붙여서, 사람이 할 일을 명령으로:

    월간 스크립트를 돌렸습니다(run:monthly_0003 · 자료 회차 d2026-12a, 새 기간 2020Q1).
    - 자료: toy_q_2020Q1.csv → [source.na] · 개정 I 2019Q4 −0.5% · 항등식 demand:Y 2019Q4에서 0.08% 어긋남 [!]
    - 다시 추정: 5식 중 2식 새 계수(est:i_0002 · est:p_0002), 3식은 기준 미달로 옛 계수 — demand:CN(LM p=0.01) 등 [!]
    - 과거 재현 hs:hs_0007 — Y RMSPE 0.49%(지난달 hs:hs_0005 0.47%)
    - 전망 sim:2026-12_base — 2020년 Y 2.1%, 유가 20% 시나리오 sim:2026-12_oil20 −0.3%p
    - 보고서 reports/forecast_d2026-12a.md(구역 2 새로), 엑셀 exports/forecast_d2026-12a.xlsx
    알아서 한 것: 가정이 없는 정책금리 R을 마지막 값으로 채움(2020Q2~2022Q1).
    볼 것: demand:CN 후보를 찾아볼까요? (equion est "…" --for demand:CN → equion compare --part demand:CN)

## 9. 방정식 문법(요약)

블록 파일은 한 줄에 한 식, `#` 뒤는 설명. 최상위 `=`가 없으면 추정식(첫 변수가 목표, `c`는 상수항), `=`가 있고 `c(n)`이 없으면 항등식,
`=`와 `c(n)`이 있으면 비선형 추정식이다(`c` 유무로 가르지 않는다).

    CN c Y CN(-1)                          # 추정식
    dlog(P) c dlog(Y) dlog(POIL)           # 로그 차분
    Y = CN + I + G                         # 항등식(좌변의 첫 변수가 목표)
    I c Y(-1 to -2) R @smpl 1990Q1 2019Q4  # 시차 범위 · 표본
    Q = c(1)*K^c(2)*L^c(3)                 # 비선형(NLS) — 시작값은 끝에 @start 1 0.3 0.7, 도구변수를 붙이면 NL-2SLS

| 쓸 수 있는 것 | 예 |
|---|---|
| 시차·차분 | `X(-1)` · `X(-1 to -4)` · `d(X)` · `d(X,1,4)` · `dlog(X)` · `X.qoq`·`X.yoy`(주기에 맞는 시차) |
| 함수 | `log` · `exp` · `abs` · `sqrt` · `@pc`·`@pch`·`@pca`·`@pcy` · `@movav(X,4)` · `@movsum(X,4)` · `^` |
| 지시자·꼬리 | `@seas`(계절 더미) · `@trend` · `@d(2008Q4)`(그 기만 1) · `@step(2020Q2)`(그 기부터 1) · `@smpl 시작 끝` · `@inst …`(TSLS) · `@coef …` · `@start …` |
| 이름 | 대소문자를 가리지 않는다. 함수 이름·`C`는 변수 이름으로 못 쓴다 |

새 식은 `equion block add 블록 "식"`으로 넣는다(쓰기 전에 문법·한 블록에 목표 하나·자료에 있는 시리즈를 본다). 파일을 직접 고쳤으면
`equion check EQUATIONS/<블록>.txt --data work/data/<회차>/series.csv`(실행 없이 문법·변수·결측 입력 검사)와 `equion assemble`.
문서(`docs/explain/equations.md`·`docs/reference/formats.md` 등)는 Equion 저장소에 있고 프로젝트 안에는 없다 — 프로젝트에서는 이 안내와
`equion <명령> --help`·`equion an <분석> --help`로 충분하게 썼다.
