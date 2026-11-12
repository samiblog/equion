# 바뀐 점

Equion의 판별 변경 기록. 새것이 위에 있습니다. 설계 결정은 [`docs/DECISIONS.md`](docs/DECISIONS.md)(D-번호), 검증은
[`docs/explain/validation.md`](docs/explain/validation.md), 계획은 [`docs/ROADMAP.md`](docs/ROADMAP.md).

## 미공개

### 추가
- **기초 통계 분석(D50)**: `equion an stats`(기술 통계 — 관측치·평균·표준편차·사분위·왜도·첨도·Jarque-Bera) · `an corr`(상관 — 피어슨·스피어만, p값,
  색 격자 차트) · `an acf`(자기상관·편자기상관·Ljung-Box Q, 막대 차트와 띠) · `an granger`(쌍별 그랜저 인과 — 시차 지정, 쌍마다 공통 표본) ·
  `an hist`(히스토그램) · `an xcorr`(교차상관 corr(x_t, y_{t−k})) — 계산은 `equion.stats`의 `describe`·`correlation`·`acf`·`pacf`·`correlogram`·
  `ccf`·`histogram`·`granger_causality`·`granger_table`(자체 구현). 계산이 있던 `an fevd`(분산분해)·`an convert`(주기 변환)·`an stochastic`(확률적 모의)도
  분석으로 등록했습니다. 등록부의 분석마다 받는 대상의 수(`Analysis.count` — one·two·many·any)를 적습니다. 결과 카드의 차트에 막대·색 격자·산점도가
  더해졌습니다(`reporting.markdown.vega_bar`·`vega_heat`·`vega_scatter`).
- **묶음과 식 한 줄 명령(D51)**: `equion group list · define 이름 --series A,B [--desc 글] [--transform dlog] · remove 이름`(`p.group_define`·`p.group_remove`)이
  `equion.toml`의 `[group]`을, `equion block add 블록 "식" [--desc 글] [--from 블록:목표] · block remove 블록:목표`(`p.part_add`·`p.part_remove`)가 블록 파일의
  식 한 줄을 더하고 뺍니다 — `--from`은 다른 블록에서 옮기기, 빼면 채택표의 그 줄도 빠집니다. 한 블록에 같은 목표는 하나, 없는 시리즈·블록은 거절합니다.
  주석·차례를 지키고 바뀜 기록에 남깁니다.
- **명령 한 줄 실행기(D52)**: `equion.cli.line.run_line(폴더, "est demand:CN")`이 명령줄(`equion …`)과 같은 일을 같은 프로세스에서 하고 종료 코드·출력 글·새 기록·
  새 바뀜 기록을 돌려줍니다(`LineResult`). 새 프로젝트와 Python 스크립트는 받지 않습니다. `catalog()`는 명령줄 정의에서 명령·인자·옵션 목록을 뽑습니다 —
  Equion Desk의 명령 창이 씁니다.
- **추정 기록이 계수 공분산을 말합니다**: `equion est … --cov white|hac`로 견고한 표준오차를 고르면 기록(`record.json`의 `cov` — 종류·이름·시차),
  카드(`계수 공분산` 줄), 명령줄의 짧은 글(`[공분산 HAC(…)]`)에 적습니다. 전에는 t값이 다른 까닭이 기록에 남지 않았습니다. 보통 공분산이면 `cov`는 `null`이고
  출력은 그대로입니다.

- **원자료 미리보기와 자료 정의 쓰기**: `p.data_preview(파일, header_row=…, unit_row=…, missing=…, thousands=…)`(명령줄 `equion data preview`)가
  원자료를 읽은 그대로의 줄과 그 틀로 읽은 결과(주기·구간·열마다 값의 수·결측으로 읽은 칸)로 보여 줍니다 — 아무것도 쓰지 않고, 틀이 맞지 않으면
  예외가 아니라 까닭(칸 위치)을 돌려줍니다. `series={…}`를 주면 열 하나를 변환대로(주기 변환·채움·계절조정) 만들어 본 값도 줍니다.
  `p.data_define(출처, file=…, 틀…, series={이름: 열 또는 {column, unit, desc, convert, seas, scale, fill}})`(명령줄
  `equion data define 출처 --file 파일 --series 이름=열 --set 이름.키=값`)이 `series.toml`에 출처(불러오기 틀)와 시리즈를 더하거나 고칩니다 —
  쓰기 전에 새 내용 전체와 원자료의 열·변환을 검사하고(문제가 있으면 아무것도 쓰지 않음), 주석·순서는 그대로 두며, 바뀜 기록에 남깁니다.
  레시피 R59. `load_defs(…, series_text=…)`는 파일 대신 글을 검사합니다.
- **모형·블록 정의 쓰기**: `p.model_define(이름, blocks=…, include=…, exclude=…, desc=…)`(명령줄 `equion model define 이름 --blocks a,b --include m
  --exclude 블록:목표 --desc 글`)이 `equion.toml`의 `[model.이름]`을 더하거나 고칩니다 — 준 키만 바꾸고(빈 목록은 그 키를 지움), 쓰기 전에 새 설정 전체를
  검사합니다(없는 블록·모형, include 순환, 블록과 같은 이름 — 문제가 있으면 아무것도 쓰지 않음). `p.block_define(이름, file=…, desc=…)`(명령줄
  `equion block define 이름`)이 `[block]`에 블록을 더하고, 파일이 없으면 머리 주석만 있는 빈 블록 파일(`EQUATIONS/<이름>.txt`)을 함께 만듭니다.
  둘 다 주석·순서를 지키고 바뀜 기록에 남깁니다. `load_config(…, text=…)`는 파일 대신 글을 검사합니다.
- **보기(`VIEWS/*.toml`)**: 어느 시리즈를 어떤 모양(수준·전기비·전년동기비·연간·기준선 대비)으로 볼지를 이름으로 적어 둡니다 —
  `p.view_define(이름, series=…, show=…, title=…, range=…)`(명령줄 `equion view define 이름 --series Y,CN --show yoy --title 글`)이 쓰고
  `p.views()`(`equion view list`)가 읽습니다. 준 것만 바꾸고(빈 글은 그 키를 지움) 주석은 그대로, 시리즈 이름이 자료에 있는지 본 뒤 쓰며, 바뀜 기록에
  남깁니다. 보기는 결과를 만들지 않습니다 — 과거 재현·전망·시나리오의 결과를 같은 시리즈·같은 모양으로 다시 보는 데 씁니다(형식은 `docs/reference/formats.md`).
- **파일 하나만 되돌리기**: `equion history revert h0007 --file equion.toml`(`History.revert(…, files=[…])`)이 그 바뀜이 고친 파일 가운데 고른 것만
  앞 내용으로 되돌립니다 — 파일 여럿을 고친 바뀜에서 하나만 물릴 때. 그 바뀜이 고친 파일이 아니면 오류이고 아무것도 쓰지 않습니다.
- **Desk에 알리기**: `equion desk show <이름>`(`p.desk_show(이름)`)이 Equion Desk(데스크톱 앱)에 그 화면을 열어 달라고 알립니다 — 기록(`est:…`·`hs:…`·
  `sim:…`·`an:…`·`run:…`)·제안(`prop:…`)·자료 회차(`data:…`)·부품(`블록:목표`)·모형(`model:이름`)·파일 경로·화면 이름. 이름을 확인한 뒤
  `work/desk/requests.jsonl`에 한 줄을 덧붙일 뿐이고(화면 이동만 — 계산하거나 바꾸지 않습니다), 패키지는 앱을 불러오지 않습니다.

### 고침
- **시나리오 기록의 외생 수준**: `equion sim <시나리오>`의 기록(`levels.csv`)에 충격을 준 외생 변수가 기준선의 가정 경로 그대로 적혀 있었습니다(풀이와 `diff.csv`는
  맞았습니다). 시나리오가 푼 그 경로(예: 유가 +20%)로 적습니다 — 기준선 기록과 다른 외생·전망 앞 기간은 그대로입니다.
- **'낡음'의 범위**: 기록이 낡았는지(`note check`·`report check`)를 볼 때 계산의 입력이 아닌 정의까지 견주었습니다. 보기(`VIEWS/`)는 조립 명세에 넣지 않고 낡음에서
  빼며(보기를 저장해도 기록이 낡지 않습니다), 가정·보정항·시나리오(`ASSUMPTIONS/`·`ADDFACTORS/`·`SCENARIOS/`)가 바뀌면 그것을 읽는 전망 기록만 낡습니다 —
  추정·과거 재현·분석 기록은 그대로입니다.
- **제안·자료 회차 폴더 옮기기(Windows)**: `propose new`와 `data build`가 임시 폴더를 제자리로 옮길 때, 폴더를 지켜보는 프로그램(Equion Desk·백신·색인)이
  방금 쓴 파일을 잠깐 쥐고 있으면 `PermissionError`로 실패했습니다. 작업 기록·바뀜 기록처럼 잠깐씩 기다리며 다시 옮깁니다.
- **줄마다 칸 수가 다른 CSV**: 표 위에 제목 줄이 있는 통계표처럼 첫 줄의 칸 수가 아래 줄보다 적은 CSV는 원자료로 읽지 못했습니다
  (`Error tokenizing data`). 이런 파일은 가장 긴 줄에 맞춰 빈칸으로 채워 읽습니다 — `[source.이름] header_row`로 열 이름 줄을 가리키면 됩니다.
  칸 수가 고른 파일의 읽기는 그대로입니다.
- **기록 폴더 옮기기(Windows)**: 작업 기록·바뀜 기록은 임시 폴더에 쓴 뒤 제자리로 옮기는데, 방금 쓴 파일을 다른 프로그램(백신·색인·폴더 감시)이
  잠깐 쥐고 있으면 옮기기가 거절돼 명령이 실패할 수 있었습니다. 잠깐씩 기다리며 다시 옮깁니다(`equion.work.store.move_into_place`).

## 0.8.0 — 2026-11-11

### 추가
- **프로젝트 — 부품과 조립(0.8 E1, D32)**: 폴더 하나를 `equion.toml`(자료 파일·블록·모형 조립·묶음·HS 기본값)로 다룹니다.
  블록은 방정식 파일 하나, 식 한 줄은 부품 `블록:목표`(예: `demand:CN`)이고, 모형은 블록과 다른 모형을 이름으로 끼워(`include`) 식을 빼서(`exclude`)
  조립합니다. `eqn.project(폴더)` → `Project`: `.assemble`(계산 없이 조립 검사 — 내생·외생·겹친 목표·모르는 변수·외생 자료 끝·블록 사이 연결·풀이 블록),
  `.model`(워크파일 모델 객체로), `.hs`(과거 재현 — 블록 이름이면 블록 HS), `.ident`(항등식을 실측으로 검사), `.used_by`(쓰는 곳),
  바꿔 끼우기(`swap={부품: 식}` — 파일은 그대로). 명령줄 `equion assemble [모형]`·`equion ident 블록:목표 [--check]`,
  예제 프로젝트 `equion new 폴더 --template desk`(가상 분기 모형). 형식은 [`docs/reference/formats.md`](docs/reference/formats.md), 레시피 R48.
- **자료 정의와 자료 회차(0.8 E2, D34)**: 원자료(`DATA/raw/`, 받은 그대로) → 정의(`DATA/series.toml` — 불러오기 틀: 시트·열 이름 줄·단위 줄·
  시점 열·결측 표시·천 단위, 시리즈마다 출처 열·주기 변환·배율·채움·계절조정·단위·설명 / `DATA/derived.txt` — 파생식) → 회차(`work/data/<회차>/` —
  `series.csv`·`flags.csv`(값의 종류: 실측·변환·채움·파생·결측)·`meta.json`·`build.json`(입력 해시·알아서 한 것)·`summary.md`).
  같은 원자료·정의로 다시 만들면 같은 회차를 알리고 새로 만들지 않습니다. 만들어도 지금 회차는 그대로이고 '이 회차로 바꾸기'가
  `equion.toml [data] vintage`를 고칩니다(주석·순서 그대로). 두 회차의 차이(새·없어진 시리즈, 새 기간, 개정의 기간·크기)와
  영향(바뀐 시리즈를 쓰는 식·모형 — 다시 계산하지 않음). 원자료 넣기는 틀로 먼저 읽어 보고 맞을 때만 출처를 바꿉니다.
  흔한 시점 꼴(`2003.Q4`·`2003년 4/4분기`·`2003년 10월`·`2003.10`)과 괄호 음수, cp949 csv를 읽습니다.
  `Project.data_build·data_use·data_list·data_diff·data_impact·data_add`, 명령줄 `equion data list·add·build·use·diff·impact`,
  상대 기간 `Project.span`(`2005Q1:last`·`last-39:last`·`first+3`·`next:12` — `[hs] range`·`hs`·`ident`에서도). 레시피 R49.
- **작업 명령과 기록(0.8 E3, D33·D35)**: 계산할 때마다 `work/<종류>/<이름>/`에 기록(`record.json`·결과 CSV·카드 `summary.md` — 표와
  vega-lite 차트)과 `work/log.jsonl` 한 줄. 기록은 고치지 않는다(다시 계산하면 새 기록). `Project.est`·명령줄 `equion est 부품|"식"` —
  추정·진단·판단 기준(`[criteria]` 기대 부호·진단 p값·|t| 하한 → 통과·걸러짐과 까닭)·단독 모의, 식 글자는 목표가 같은 부품의 후보.
  `adopt est:…` — 채택표 `EQUATIONS/adopted.toml`과 블록 파일의 그 줄(설명은 그대로), 그 뒤 모형은 **채택 계수**로 푼다(다시 추정 없음).
  `compare` — 후보 표(종속변수·표본이 다르면 경고)·HS 기록의 변수별 RMSPE. `hs [모형] --swap 부품=est:…|"식" --vs hs:… --replay hs:…`
  — 조립 명세(`assembly.json`: 식 글자·계수·자료 회차·정의 파일 해시)를 남기고, `--replay`는 지금 파일과 무관하게 그때 그대로 다시 푼다.
  바뀜 기록 `work/history/`(누가·명령·전후·차이 — 명령 밖의 고침은 '바깥'으로) · `history list·show·revert`, `work list·show·pin·memo·clean`.
  출력 객체에 `.md()`(md 렌더러 `equion.reporting.markdown`).
- **전망 기록과 제안(0.8 E3, K4·K6)**: `Project.sim`·`equion sim [시나리오…]` — 가정 세트 `ASSUMPTIONS/이름.csv`(전망 구간의 외생 경로,
  빈 칸은 `[forecast] fill`), 보정항 `ADDFACTORS/이름.toml`(식마다 `last`·`decay`·`mean`·`zero`, 판단 값 CSV), 시나리오 `SCENARIOS/이름.toml`
  (`[[shock]]`·`[[addfactor]]`, 기간은 `start`·`end±N`도). 시나리오면 기준선과의 차이, 칸마다 값의 종류(실측·해·가정·채움), 연간 증가율,
  `--vs`(지난 전망과)·`--vintage`(옛 회차로). 계산한 값은 실측 자리에 쓰지 않는다. `Project.reestimate`·`equion est --adopted --adopt
  never|if_pass|all` — 채택한 식을 지금 자료로 다시 추정하고 기준을 통과한 식만 새 계수(걸린 식은 옛 계수·표시). `Project.propose`·
  `equion propose new|list|show|apply|drop` — 바꿀 내용·까닭·미리 계산한 기록을 먼저 보이고(낡으면 적용하지 않음), 적용은 바뀜 기록에.
  `Project.export`·`equion export 기록… --xlsx` — 값·값의 종류·출처 시트. `[forecast]`·`[criteria]`가 `equion.toml`의 표가 됐다.
  레시피 R50~R52.
- **분석 등록부·노트·보고서(0.8 E4, D37)**: 분석 하나 = 명령 하나 = 기록 하나(`work/an/<이름>/`) = md 카드 하나. 등록부 `eqn.registry`에
  분석 13개 — 보는 분석(요약·단위근 ADF+KPSS·공적분 Johansen/Engle-Granger·식 진단 Chow/CUSUM·예측 평가 DM·동태 안정성·충격 승수),
  만드는 분석(계절조정·파생 — `an keep`이 `series.toml`의 새 시리즈(`made_by`)·`derived.txt` 한 줄로), 부품을 내는 분석(ECM·VAR·VECM·
  시스템 추정 — `an keep`이 식 후보 `est:`로, 계수 그대로). `Project.an`·`keep`, 명령줄 `equion an list·<분석>·--help·keep`(옵션은 등록부에서).
  노트 `notes/*.md` — ```` ```equion ```` 블록을 `equion note run`이 실행해 바로 아래 결과 구역(펼친 md 카드)을 채운다. 블록은 등록부의
  계산·보기 명령만(허용 목록), 손으로 고친 구역은 `--force` 없이 덮지 않고, `note check`가 낡은 구역·없는 기록을 알린다. 보고서
  `reports/*.md` — `report new·add·check·update`: 결과만 보내고(행·전기비·전년동기비·기준선 대비·연간·소수점·차트 — 자료는 보고서 옆
  `_data/`로), 새 기록으로 바꿀 때 같은 모양으로 다시 만들어 숫자의 차이를 보이며 손으로 고친 곳은 차이로 알린다. 레시피 R53~R55.
- **Equion 스크립트와 재연(0.8 E5, D36)**: `FLOWS/*.eqs` — 한 줄이 `equion` 명령 하나(앞의 `equion`은 빼도 된다), `# 주석` · `## 제목`(단계 묶음) ·
  `param 이름 = 값 …` · `{이름}`(매개변수·`{vintage}`·`{last}`·`{today}`·`{model}`·`{run}`·앞 단계의 기록 `{hs}`·`{sim:base}`) ·
  `expect 대상 조건 --stop·--flag`(HS `Y.rmspe`·전망 `Y.growth[2021]`·추정 `r2`·`failed` …) · `run 다른.eqs`(포함) · `py x.py`(Python 단계,
  명령줄에서만). 반복·조건·셸은 없다 — 등록부의 명령만 돈다(`eqn.registry.allowed(…, where='script')`). `equion run x.eqs [--set] [--from 단계·제목]
  [--dry-run]` → 실행 기록 `work/run/<이름>/`(`run:` — 값을 바꿔 넣은 뒤의 스크립트 `script.eqs`·원래 스크립트 `src/`·정의 사본 `defs/`·
  단계 출력·카드), 단계의 기록·바뀜 기록에는 누가 '스크립트'와 그 실행 이름(`run`). 기준 미달 식·실패 대체 기간은 `!`로 표시하고 계속.
  `equion run --replay run:…` — 프로젝트 사본에서 그때의 정의·받은 원자료·스크립트·매개변수로 다시 돌려 단계마다 숫자를 견준다(프로젝트는 그대로).
  `equion check x.eqs`(실행 없이 — 문법·명령·선택지·{이름}·매개변수·모형·시나리오·부품·노트), `equion script new 이름 --from-records 기록…`
  (작업 기록의 명령으로 초안 — `--as`·`-p`·`--json` 뺌), `equion script export x.eqs --py`(같은 일을 하는 Python — `eqn.script.session`).
  `Project.run_script·check_script·replay_run·new_script·export_script`. 받은 원자료 `DATA/raw/inbox/` — `equion data build --inbox ask|auto`가
  출처와 짝지어(파일 이름 또는 `[source.이름] inbox = "글롭"`) 틀 검사 뒤 넣고 회차를 만든다(하나라도 문제면 아무것도 넣지 않음),
  미리보기 `equion data inbox` · `Project.data_inbox`. 예제 프로젝트에 월간 스크립트 `FLOWS/monthly.eqs`·자료 점검 노트. 레시피 R56~R58.
  **종료 코드(D15 안에서)**: `.eqs`는 멈춘 단계의 종료 코드 · `expect --stop`에 걸리면 2 · `--fail-on`에 걸리면 2 · 실행 전 검사 문제·모르는
  `--set`은 3 · `--replay`에 다른 단계가 있으면 2.
- **Claude용 안내와 스킬 초안(0.8 E6)**: 패키지에 모형 작업 안내 `equion/help/guide.md`(꼭 지킬 것 — 계산은 명령으로·결론에 근거 기록·
  결과는 고치지 않음·정의는 명령으로 먼저·"제안만"이면 propose·거른 후보도 기록 / 프로젝트 지도·이름·명령·판단 기준·기록 읽기·분석·노트·
  보고서·스크립트와 월간 작업·종료 코드와 흔한 문제·보고 꼴)와 Claude Code 스킬 초안 `equion/help/skill/SKILL.md`(`name: equion`).
  안내의 명령·분석·허용 목록 표는 명령줄과 등록부에서 만들고 `docs/make_api.py --check`가 코드와 같은지 본다. `equion guide`·`--path`·
  `guide skill`·`guide skill --install user|project`(사람이 시킬 때만, 다른 내용은 `--force` 없이 덮지 않음), `eqn.help`.
  예제 프로젝트에 `CLAUDE.md`(먼저 `equion guide`). 튜토리얼 9편 "프로젝트와 스크립트", 파일 형식에 프로젝트 파일 지도.
- **가이드 9편(`docs/guide/`)**: 사람과 상황별 — 처음 한 시간 · 내 모형을 프로젝트로(엑셀 원자료·불러오기 틀·조립·내 스크립트) · 매달 하는 일 ·
  식 고르기 · 전망과 시나리오 · 분석·노트·보고서 · Claude와 함께 · 막혔을 때 · 자동으로 돌리기. 터미널 세션(`console` 블록 — `$ equion …`)을
  문서 도구가 실제로 실행해 출력을 채우고 CI가 검사한다. 가이드마다 시험하며 확인할 것.
- **문서 체계(D27)**: 시작하기 · 튜토리얼 8편 · 레시피 · 해설 · 참조 · 사례 연구(Klein형) · EViews 사용자 안내 ·
  영문 시작 문서. 시작점은 [`docs/README.md`](docs/README.md)입니다. 문서의 예제는 실제로 돌고, 출력도 실행 결과입니다.
  `python docs/build_docs.py --check`가 CI에서 예제 실행·출력·링크·API 설명과 예제·doctest를 확인합니다.
- **예제 자료 `eqn.datasets`**: `toy_q`(분기 거시) · `toy_a`(연간) · `toy_m`(월간) · `klein_like`(Klein 모형 I 구조). 참 모형을 아는
  가상 자료이며 패키지에 들어 있습니다. 실제 Klein 자료는 이용 조건이 분명하지 않아 넣지 않았고, 직접 구한 파일은 `eqn.datasets.klein(path)`로 엽니다.
- 공개 함수·메서드 전체에 매개변수·돌려주는 것·오류·예제(doctest)를 담은 docstring을 달았습니다. API 참조 `docs/reference/api.md`가 여기서 만들어집니다.
- 예제 스크립트·노트북 `examples/`(문서에서 자동으로 만든다).
- `wf.convert(…, start=, end=)`: 변환할 구간을 고릅니다.
- `TableObject.save`: `.csv`·`.xlsx`·`.html`·`.txt`를 받고, 없는 폴더는 만듭니다.
- 안정성 판정이 `안정`·`단위근`·`불안정`으로 나뉩니다(`StabilityResult.verdict`·`unit_roots`·`explosive`). `stability_path`에 `판정` 열을 더했습니다.

### 바뀜
- 예제 프로젝트(`--template desk`)는 자료 정의·회차를 씁니다 — 원자료 `DATA/raw/toy_q.csv`·`toy_m.csv`, 만들 때 첫 회차를 지금 회차로,
  `[hs] range = "2005Q1:last"`(새 회차로 바꾸면 따라 늘어난다). 자료 파일 하나(`[data] file`)를 쓰는 프로젝트도 그대로 됩니다.
- 필수 의존성 `tomlkit`(정의 파일을 주석·순서를 지키며 고친다, D38).
- **`--json`이면 오류도 JSON**: 표준출력에 `{"error": {"message", "exit_code", "kind", "kind_ko"}}` 하나 — 사용법 오류는 `usage`, 예상 못 한
  내부 오류(종료 코드 1)는 `type`·`internal`·`traceback`도. 종료 코드는 그대로이고, `--json`이 없으면 전처럼 표준오류에 한 줄(`equion.cli.errors`).
- `report new --exist-ok`(있으면 그대로) · `report add --key 이름`(같은 이름의 구역을 그 자리에서 새 기록으로 — 손으로 고친 구역은 `--force`일 때만).
  `[source.이름] inbox` 키. 작업 기록에 `run`(그 기록을 만든 스크립트 실행)·바뀜 기록에 `run`. `FLOWS/*.eqs`도 바뀜 기록에 남는다.
- 노트의 블록은 정의 파일을 바꾸는 줄(`est --adopt`·`an keep`·`an --note`)도 부를 수 없다(전에는 명령 이름만 봤다).
- 보고서의 전망 연간 표 제목은 `(연간 증가율, %)`(전에는 `전년동기비`)이고, 실측과 전망이 섞인 해를 밝힌다(`2020년은 실측 1기 + 전망 3기`).
- `est --adopted`의 글: 옛 채택 계수가 없는 식은 `옛 계수 없음 · … · 채택 안 함 — 옛 계수가 없어 모형은 이 자료로 추정한 계수로 푼다`
  (전에는 `처음 채택`·`채택 없음`이 함께 나와 모순으로 읽혔다). `work list`의 '회차 다름'은 실행 기록이면 끝났을 때의 회차로 본다.
  `work show run:…`은 잘린 기록 수를 `외 n`으로 보인다. 예제의 자료 점검 노트에 항등식 검사 블록.
- `series.toml`의 시리즈에 `made_by`(그 정의를 만든 분석 기록)를 적을 수 있다. 노트·보고서도 바뀜 기록에 남는다(낡음 판정의 입력은 아니다).
- 예제 프로젝트에 판단 기준 `[criteria]`·전망 `[forecast]`과 `ASSUMPTIONS/base.csv`·`ADDFACTORS/base.toml`·`SCENARIOS/oil20.toml`을 더했다.
  프로젝트의 모형은 채택 기록이 있으면 그 계수로 푼다(없으면 지금처럼 지금 자료로 추정하고 알린다).
- `docs/EQUATION_GUIDE.md` → `docs/explain/equations.md`, `docs/API.md` → `docs/reference/api.md`(옛 위치에는 안내만 남김).
- 모델에 같은 항등식을 다시 `append`해도 한 번만 들어갑니다(공백·대소문자 무시).
- `forecast(start, end)`는 `end`가 워크파일 끝보다 뒤일 때만 기간을 늘립니다.

### 고침
- 받은 원자료가 둘째 달부터 짝지어지지 않던 것 — 파일 이름 끝의 날짜·기간 토막을 빼고 짝짓는다(`toy_q_2020Q1` → `toy_q`).
- 보고서·노트·내보내기·스크립트 초안·스크립트의 포함과 Python 단계의 경로가 프로젝트 밖을 가리킬 수 있던 것 — 프로젝트 안만(밖이면 3).
- `--set` 값으로 스크립트의 명령에 선택지를 끼워 넣을 수 있던 것 — 거절(3, 음수는 된다).
- `work clean --yes`가 실행 기록과 그 단계의 기록을 지워 재연할 수 없게 되던 것 — 실행 기록이 가리키는 기록은 남기고, 실행 기록은 `--kind run`일 때만.
- 프로젝트의 하위 폴더에서 명령이 프로젝트를 찾지 못하던 것 — 위로 올라가며 `equion.toml`을 찾는다.
- `work list`가 보일 기록만 연다(기록이 많을 때 빠르게).
- `--log logs/x.log`처럼 아직 없는 폴더를 주면 트레이스백으로 끝나던 것 — 폴더를 만든다(가이드 9를 쓰다 찾았다).
  (모두 사용자 관점의 시나리오 시험 `tests/test_journeys.py` — `docs/TEST_SCENARIOS.md` — 에서 찾았다)
- 선행변수(`X(1)`)가 있는 모델을 `mce=False`로 풀면 경고합니다(선행값으로 실측을 쓴다는 뜻).
- FIML에서 도구변수에 없는 같은 기 설명변수(항등식이 정하는 내생변수)를 외생으로 다루게 될 때 경고합니다.
- 오류 메시지를 더 분명하게 바꿨습니다: 목표변수 중복(어느 식인지와 `drop` 안내), 목표 추적(`control`) 구조 오류의 힌트,
  없는 시점(워크파일 기간과 `extend` 안내), 시리즈와 겹치는 객체 이름(대소문자 무시와 접두사 안내), 주기 변환 지표가 구간을 덮지 못할 때(두 구간 표시).
- `equion --help`에 종료 코드 130(중단)을 표시합니다.
- 계열상관 LM(Breusch-Godfrey) 검정의 보조 회귀에 상수열이 겹쳐 들어가 있었습니다(식에 상수항이 이미 있어도 하나 더). 완전 공선인
  열의 절단이 BLAS에 따라 달라져 p값이 플랫폼마다 달랐습니다(예: 0.405 · 0.468). 이제 상수항이 없을 때만 더합니다 — 결과는
  절단이 맞게 된 경우의 값과 같습니다.
- 안정성: 켤레 근 쌍은 허수부가 양인 쪽을 먼저 보입니다(순서가 LAPACK에 따라 달랐다). '가장 큰 근과 함께 움직이는 변수'에서
  0%로 반올림되는 변수는 보이지 않습니다.
- pandas 4 대비: 엔진 `Model`에 `'2010Q1'` 같은 시점 표기를 주거나, 기간 라벨 인덱스의 시나리오 경로를 저장했다가 다시 열 때
  pandas가 기간 문자열을 직접 해석하지 않게 했습니다(`data/periods.py`의 `locate`·`parse_dates`를 거친다 — 새 pandas에서는 경고, pandas 4에서는 오류였을 것).

## 0.7.0 — 2026-10-30

### 추가
- 추정: WLS · GMM(Hansen J) · LIML · PDL · 누락/불필요 변수 검정(D20), AR(p) 오차항 · 오차수정모형 · 예측 평가(Theil · Diebold-Mariano)(D21).
- 시스템 추정: OLS · SUR · 2SLS · 3SLS · FIML · 식 사이 제약, 모델로 `merge`(D22). VAR · VECM(D23).
- 모델 분석: 동태 안정성(선형화 동반행렬 고윳값) · 시나리오 기여도 분해(Shapley)(D24). 큰 블록의 희소 자코비안 · stacked-time MCE(D25).
- 자료: 시리즈 메타데이터 · 페이지 · 주기 변환 · Denton/Chow-Lin · STL/고전 계절조정(D26).
- 보안: 비밀 값 가리기(`eqn.secret`) · `--redact` · 레거시 pickle 기본 차단(`equion convert`) · 방정식 입력 한도와 퍼징(D18).
- 영문 README, API 목록 자동 생성, 저장소 분리 계획(계획만).
- 상황별 시나리오 시험 641개와 회귀 시험 `tests/test_scenarios.py`.

### 바뀜
- 라이브러리 출력을 `logging`으로(`eqn.verbose`). 공개 버전 번호 하나, 공개·고급·내부 API 구분, `_legacy` 사용 경고(D18).
- 워크파일·번들의 표를 npz로 저장합니다. pyarrow·plotly는 선택 기능입니다(`equion[parquet]` · `equion[plot]`)(D19).
- 의존성을 범위로 두고 `uv.lock`으로 고정했습니다. CI는 3 OS × Python 3.12~3.14와 하한·최신·선택 의존성 없이·기준선·감사를 봅니다(D19).

### 고침
- 시나리오 시험에서 찾은 결함(경계·오용·연/월·명령줄)을 고쳤습니다. 고친 것마다 `tests/test_scenarios.py`에 시험이 있습니다.
- 이미 넣은 제약을 Wald로 검정하면 분명한 오류를 냅니다.

## 0.6.0 — 2026-10-29

- statsmodels를 없애고 회귀·검정을 자체 구현했습니다(OLS 계수·통계가 이전과 같다)(D17).
- NLS 해석적 자코비안(IR 기호 미분). 기간·주기 연산을 `data/periods.py` 한 곳으로 모았습니다(pandas 버전 변화 흡수).
- 강건 공분산(HC0~3 · HAC) · 진단 검정 · 단위근/공적분.

## 0.5.0 — 2026-10-29

- 이름을 `macromodel`에서 **Equion**으로 바꿨습니다(패키지 · import · 명령 `equion`, 별칭 `eqn`, 워크파일 `.eqw`)(D16).
  옛 `.mmw` 워크파일 · `macromodel-run` 보고서 · 레거시 pickle · `MACROMODEL_PARAMS`는 계속 읽습니다.

## 0.4.0 — 2026-10-29

- 명령줄 `run` · `check` · `info` · `new`, 보고서 폴더(`report.html` · `manifest.json`), 종료 코드 약속(D5 · D15).
- 설치형 패키지(D6). 웹 대시보드를 삭제했습니다(D11).

## 0.3.0 — 2026-10-29

- 워크파일 API(라이브러리 1단계): 워크파일 · 표본 · genr · 방정식 · 모델 · 시나리오 · 그래프 · 표 객체(D2~D14).

## 0.2.0 — 2026-10-29

- 엔진 v3: 단일 방정식 파서 · IR · 블록 분해 + Newton · 실패 정책 · 시나리오 · 전망 · 확률적 모의 · 목표 추적 · MCE · TSLS/NLS.

## 0.1 — 2026-05-31

- 첫 스냅샷(태그 `v0.1`).

## 이전 이력(macromodel 시절)

- v2.1 (2026-05-31): 대소문자 무시 매칭, `@seas`, `@d`/`@step`/`@trend`, 시차 범위, `@def`, `@smpl`, `dlog`/`d`/`.gr(N)`, `hs(add_factors=…)`.
- v2.0.1 (2026-05-29): 풀이기의 복합·내생 시계열 항 변환 오류 수정, 방정식 로더 분류 수정.
- v2.0.0 (2026-04-18): AST 기반으로 다시 짬.
- 원본: `equation_model_core.py` v1.4.1 (2025-10-11).
