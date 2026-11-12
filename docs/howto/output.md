# 레시피: 출력·보고서

```python
from pathlib import Path

import equion as eqn

wf = eqn.datasets.load("toy_q")
eq = wf.equation("eq_i").ls("I c Y(-1) R")
```
<!-- out -->
```text
[toy_q] 열기 toy_q.csv — 분기(Quarterly) 1970Q1~2019Q4 · 시리즈 10
[eq_i] OLS I — n=199, R²=0.9985
```

## R40. 표를 여러 형식으로

```python
t = wf.table("t_i", eq)                         # 방정식·검정·DataFrame·출력 객체를 표로
for path in ("eq.csv", "eq.xlsx", "eq.html", "eq.txt"):
    t.save(path)
print(Path("eq.txt").read_text(encoding="utf-8").splitlines()[0])
```
<!-- out -->
```text
방정식 eq_i
```

## R41. 그래프를 html로(인터넷 없이 열리게)

```python
g = wf.graph("g_y", "Y CN I", start="2000Q1", title="소득과 구성 요소")
g.output().save("y_inline.html", include_js="inline")     # plotly.js를 파일에 넣는다(약 3MB)
g.save("y_cdn.html")                                       # 기본: 인터넷에서 plotly.js를 부른다(작음)
spec = g.output().spec()                                   # JSON으로 쓸 수 있는 그림 정의(dict)
print(sorted(spec), len(spec["data"]))
```
<!-- out -->
```text
['data', 'layout'] 3
```

`kind="bar"`·`"stacked"`도 됩니다. png·svg가 필요하면 plotly와 kaleido를 설치하고 `.save("y.png")`.

## R42. 출력 여러 개를 한 보고서로

스크립트에서 `eqn.show(…)`로 보인 표·그래프는 `equion run`이 보고서 한 페이지(report.html)로 모읍니다. 파이썬 안에서
모은 출력을 직접 보려면 스풀을 씁니다.

```python
eqn.spool.clear()
eqn.spool.mode = "collect"                     # 화면에 찍지 않고 모으기만
eqn.show(eq, eq.diagnostics(), wf.graph("g2", "I"))
print([type(o).__name__ for o in eqn.spool.items])
eqn.spool.mode = "auto"
```
<!-- out -->
```text
['TableOutput', 'TableOutput', 'GraphOutput']
```

## R43. 출력 수준 조절

```python
eqn.verbose(0)                                 # 요약 줄도 끔
wf.equation("quiet_eq").ls("CN c Y")
eqn.verbose(1)                                 # 기본(요약 한 줄)
wf.equation("loud_eq").ls("CN c Y")
```
<!-- out -->
```text
[loud_eq] OLS CN — n=200, R²=0.9999
```

`eqn.verbose(2)`는 엔진 상세 로그까지 보입니다. 응용 프로그램의 logging 설정을 쓰려면 `eqn.log.use_own_handler(False)`.

## R54. 노트 — 명령 블록과 결과 구역

노트(`notes/*.md`)는 글 사이에 ```` ```equion ```` 블록을 둔 작업 문서입니다. `note_run`(명령줄 `equion note run`)이 블록을 돌려 바로 아래에 결과
구역(기록 카드를 펼친 md)을 채우고, 다시 돌리면 새 기록으로 바꿉니다([파일 형식](../reference/formats.md#노트notesmd보고서reportsmd)).
블록은 등록부의 계산·보기 명령만 부를 수 있습니다.

```python
p = eqn.Project.create("note_prj", force=True)
Path(p.root, "notes").mkdir(exist_ok=True)
fence = "`" * 3                                               # 코드 블록 울타리(이 문서 안에 그대로 쓰면 블록이 끝나므로)
Path(p.root, "notes", "core.md").write_text(
    f"# core 묶음\n\n{fence}equion\nan unitroot core --trend ct\n{fence}\n\n공적분을 본다.\n\n"
    f"{fence}equion\nan coint \"RL R\"\n{fence}\n", encoding="utf-8")
print(p.note_run("notes/core.md").text())
text = Path(p.root, "notes", "core.md").read_text(encoding="utf-8")
region = text.split("<!-- /equion:out -->")[0].split("<!-- equion:out")[1]   # 첫 블록의 결과 구역
print("<!-- equion:out" + region)
print(p.note_check("notes/core.md").text())
```
<!-- out -->
```text
[note_prj] 자료 회차 d2026-11a를 만들었습니다
[note_prj] 지금 자료 회차: d2026-11a
[note run] notes/core.md: 블록 2
   1 equion 실행     an:unitroot_0001
   2 equion 실행     an:coint_0001
  바뀜 기록  h0003
<!-- equion:out an:unitroot_0001 · 2026-11-12T18:22:16 · d2026-11a {"records": ["an:unitroot_0001"], "h": "cd616e9eea4a"} -->
**단위근 — 묶음 core(Y · CN · I)**

| 항목 | 값 |
|---|---|
| 기록 | `an:unitroot_0001` |
| 명령 | `equion an unitroot core --trend ct` |
| 자료 | data:d2026-11a |
| 표본 | 1970Q1~2019Q4 |
| 누가 · 언제 | Python · 2026-11-12T18:22:16 |
| equion | 0.9.0 |

**단위근 검정**

| 시리즈 | ADF t | ADF p | 시차 | KPSS | KPSS p | 판단 |
|---|---|---|---|---|---|---|
| Y | -1.8314 | 0.6894 | 0 | 0.1840 | 0.0220 | 단위근 |
| CN | -2.5644 | 0.2965 | 3 | 0.1815 | 0.0229 | 단위근 |
| I | -2.1417 | 0.5227 | 0 | 0.2492 | 0.0100 | 단위근 |

**알아서 한 것**

- ADF 시차 수를 BIC로 골랐다
- 판단: ADF(귀무 단위근)·KPSS(귀무 정상) 모두 5%

[note check] notes/core.md: 블록 2
   1 equion 정상     an:unitroot_0001
   2 equion 정상     an:coint_0001
```

결과 구역을 손으로 고치면 다음 실행 때 덮지 않고 알립니다(`--force`면 덮는다). 자료 회차를 바꾸면 `note check`가 '낡음'을 보이고 `note run --stale`이
낡은 구역만 다시 돌립니다.

## R55. 보고서로 보내기 — 결과만, 그리고 새 기록으로 바꾸기

보고서(`reports/*.md`)에는 명령 블록 없이 결과만 보냅니다. 구역마다 보이지 않는 표시에 기록과 보낸 모양이 남아, 다음 달에 같은 모양으로 새 기록을
끼울 수 있습니다. 손으로 고친 곳은 바꾸기 전에 차이로 알립니다.

```python
p = eqn.Project.create("rep_prj", force=True)
p.sim(as_name="base_1")
p.report_new("전망", title="분기 전망")
p.report_add("전망", "sim:base_1", rows=["Y", "CN", "P"], show="yoy", annual=True, title="주요 지표", under="## 본문")
rp = Path(p.root, "reports", "전망.md")
rp.write_text(rp.read_text(encoding="utf-8").replace("| CN |", "| 민간소비 |"), encoding="utf-8")   # 사람이 고친다
p.sim(as_name="base_2", range="next:12")                     # 새 전망
print(p.report_check("전망").text())
print(p.report_update("전망").text())                         # 손으로 고친 구역은 고친 곳만 보이고 그대로
print(p.report_update("전망", force=True).items[0]["status"])
```
<!-- out -->
```text
[rep_prj] 자료 회차 d2026-11a를 만들었습니다
[rep_prj] 지금 자료 회차: d2026-11a
[rep_prj] 열기 series.csv — 분기(Quarterly) 1970Q1~2019Q4 · 시리즈 13
[main] 채택 기록 없이 지금 자료로 추정: demand:CN, demand:I, price:P, finance:RL, finance:M2
[rep_prj] 기간 확장 → 2021Q4 (+8)
[main] baseline(_0) dynamic 2020Q1~2021Q4: 정상 8 · 일부식 제외 0 · 실패대체 0 · 실패 0
[rep_prj] 열기 series.csv — 분기(Quarterly) 1970Q1~2019Q4 · 시리즈 13
[main] 채택 기록 없이 지금 자료로 추정: demand:CN, demand:I, price:P, finance:RL, finance:M2
[rep_prj] 기간 확장 → 2022Q4 (+12)
[main] baseline(_0) dynamic 2020Q1~2022Q4: 정상 12 · 일부식 제외 0 · 실패대체 0 · 실패 0
[report check] reports/전망.md — 구역 1
  #1 sim:base_1 → sim:base_2  더 새 기록 · 손으로 고침 — sim:base_2
[report update] reports/전망.md — 구역 1
  #1 sim:base_1 → sim:base_2  손으로 고침 — 바꾸지 않음(--force) — 고친 곳
    --- 보낸 것 → 지금(전)
    +++ 보낸 것 → 지금(후)
    @@ -3,7 +3,7 @@
     | 시리즈 | 2020 | 2021 |
     |---|---|---|
     | Y | 0.9 | 1.7 |
    -| CN | 0.9 | 1.7 |
    +| 민간소비 | 0.9 | 1.7 |
     | P | 2.5 | 2.6 |

     자료: Equion sim:base_1(자료 회차 d2026-11a)
바뀜 · 손으로 고친 것을 덮음
```

관련: [명령줄 튜토리얼](../tutorial/08-cli.md)

## R62. 노트에 블록 더하기 — 후보 묶음을 매달 다시

`note_add`(명령줄 `equion note add`)가 노트 끝에 ```` ```equion ```` 블록 하나를 더합니다. 명령 줄(lines)은 실행하지 않고 블록만 두고,
기록(record)을 주면 그 명령과 결과 구역(카드)까지 담습니다. 노트가 없으면 만듭니다. 다음 회차에는 `note_run`으로 블록을 다시 돌립니다.

```python
p = eqn.Project.create("cand_prj", force=True)
lines = [f"est '{t}' --for demand:I" for t in ("I c Y", "I c Y I(-1)", "I c Y(-1) I(-1)")]
print(p.note_add("notes/invest.md", lines=lines, title="투자 후보").text())
print(p.note_run("notes/invest.md").text())
u = p.an("unitroot", "R")
print(p.note_add("notes/invest.md", record=u.id).text())
print(p.note_check("notes/invest.md").text())
```
<!-- out -->
```text
[cand_prj] 자료 회차 d2026-11a를 만들었습니다
[cand_prj] 지금 자료 회차: d2026-11a
[note add] notes/invest.md — 새 노트 · 블록 1
  est 'I c Y' --for demand:I
  est 'I c Y I(-1)' --for demand:I
  est 'I c Y(-1) I(-1)' --for demand:I
  다음   equion note run notes/invest.md --block 1
  바뀜 기록  h0002
[note run] notes/invest.md: 블록 1
   1 equion 실행     est:i_0001 · est:i_0002 · est:i_0003
  바뀜 기록  h0003
[cand_prj] 열기 series.csv — 분기(Quarterly) 1970Q1~2019Q4 · 시리즈 13
[note add] notes/invest.md · 블록 2
  an unitroot R
  결과 구역  an:unitroot_0001
  바뀜 기록  h0004
[note check] notes/invest.md: 블록 2
   1 equion 정상     est:i_0001 · est:i_0002 · est:i_0003
   2 equion 정상     an:unitroot_0001
```

Equion Desk에서는 식 작업대의 '후보 묶음'(고를 칸의 조합으로 식 여러 개)이 '노트로 저장'으로, 분석 결과와 카드의 '노트에'가 기록 담기로 같은 일을 합니다.

관련: [R54](#r54-노트--명령-블록과-결과-구역)
