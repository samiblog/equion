# 가이드 6. 분석·노트·보고서

보고서를 쓰는 사람의 길입니다. 계산은 **기록**으로 남기고, 탐색은 **노트**(명령 블록과 결과)에서, 남에게 보내는 글은 **보고서**(결과만)에 씁니다.
보고서의 숫자는 기록에서 오므로, 새 기록이 생기면 같은 모양으로 다시 만들어 숫자의 차이를 보이고 바꿉니다.

```console
$ equion new rep --template desk
$ cd rep
```
<!-- out -->
```text
$ equion new rep --template desk
새 프로젝트 rep:
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
  cd rep
  equion assemble main

$ cd rep
```

## 1. 분석 — 하나 = 기록 하나

```console
$ equion an list --for group
$ equion an unitroot core --as ur1
```
<!-- out -->
```text
$ equion an list --for group
[an list] 분석 5 — 대상 묶음
  summary      요약       시리즈 · 묶음 · 식(log(Y) 등)       만드는 것 —
  unitroot     단위근      시리즈 · 묶음 · 식(log(Y) 등)       만드는 것 —
  coint        공적분      묶음 · 식(log(Y) 등)             만드는 것 —
  var          VAR      묶음 · 식(log(Y) 등)             만드는 것 식 후보(est:)
  vecm         VECM     묶음 · 식(log(Y) 등)             만드는 것 식 후보(est:)
  옵션·예: equion an <분석> --help

$ equion an unitroot core --as ur1
[an:ur1] 단위근 · 묶음 core(Y · CN · I) · 1970Q1~2019Q4 · 자료 data:d2026-11a
  Y            ADF -0.072 p=0.952 · KPSS 2.097 p=0.010 → 단위근
  CN           ADF 0.007 p=0.959 · KPSS 2.097 p=0.010 → 단위근
  I            ADF -0.346 p=0.919 · KPSS 2.079 p=0.010 → 단위근
  알아서 한 것  ADF 시차 수를 BIC로 골랐다 · 판단: ADF(귀무 단위근)·KPSS(귀무 정상) 모두 5%
  기록   an:ur1 (work/an/ur1/summary.md)
```

옵션은 `equion an <분석> --help`. 부품을 내는 분석(ECM·VAR·VECM·시스템)은 `an keep`으로 식 후보가 되어 [식 고르기](04-equations.md)로 이어집니다.

```console
$ equion an ecm "log(CN) log(Y)" --as ecm1
$ equion an keep an:ecm1 --as cons_ecm
$ equion compare --target CN
```
<!-- out -->
```text
$ equion an ecm "log(CN) log(Y)" --as ecm1
[an:ecm1] 오차수정모형 · log(CN) · log(Y) · 1970Q2~2019Q4 · 자료 data:d2026-11a
  장기  상수 -0.0326 · log(Y) 0.9573
  조정 속도 α -0.5571 (t -10.393) · 반감기 0.8511기
  단기식  d(log(CN)) c d(log(Y)) ((log(CN)) - (-0.03257274703047641) - (0.957308749513049)*(log(Y))).t(-1)
  장기 잔차 Engle-Granger p=<0.001
  알아서 한 것  two-step — 장기 계수를 단기식의 EC(-1)에 숫자로 넣음
  남기기   equion an keep an:ecm1 — 식 후보(est:)로
  기록   an:ecm1 (work/an/ecm1/summary.md)

$ equion an keep an:ecm1 --as cons_ecm
[an keep] an:ecm1 → 식 후보(est:)
  est:cons_ecm
  다음   equion compare --part … · equion hs --swap 부품=est:… · equion adopt est:…

$ equion compare --target CN
[compare] 추정 기록 1
                                                                                                             식         부품 채택             표본    n   R²adj      SE     DW       AIC       BIC LM(2) p White p   JB p RESET p  기준
기록
est:cons_ecm  d(log(CN)) c d(log(Y)) ((log(CN)) - (-0.03257274703047641) - (0.957308749513049)*(log(Y))).t(-1)  demand:CN     1970Q2~2019Q4  199  0.9320  0.0016  1.977  -2,003.8  -1,993.9   0.901   0.493  0.110   0.779  통과
```

## 2. 노트 — 명령 블록과 결과 구역

노트는 작업 문서입니다. ```` ```equion ```` 블록에 명령을 적고 `note run`이 바로 아래에 결과 구역(표·차트)을 채웁니다. 글은 블록 밖에 씁니다.

```python
from pathlib import Path

f = "`" * 3                                        # 코드 펜스(편집기에서는 그냥 친다)
Path("notes/look.md").write_text(
    f"# 이번 달 살펴보기\n\n핵심 수요 시리즈부터.\n\n{f}equion\nan summary core\n{f}\n\n"
    f"수요 블록만 따로 풀어 본다.\n\n{f}equion\nhs demand\n{f}\n", encoding="utf-8")
print(Path("notes/look.md").read_text(encoding="utf-8").replace(f, "~~~"))   # (펜스를 ~~~로 바꿔 보인다)
```
<!-- out -->
```text
# 이번 달 살펴보기

핵심 수요 시리즈부터.

~~~equion
an summary core
~~~

수요 블록만 따로 풀어 본다.

~~~equion
hs demand
~~~
```

```console
$ equion note run notes/look.md
$ equion note check notes/look.md
```
<!-- out -->
```text
$ equion note run notes/look.md
[note run] notes/look.md: 블록 2
   1 equion 실행     an:summary_0001
   2 equion 실행     hs:hs_0001
  바뀜 기록  h0003

$ equion note check notes/look.md
[note check] notes/look.md: 블록 2
   1 equion 정상     an:summary_0001
   2 equion 정상     hs:hs_0001
```

## 3. 보고서 — 결과만 보내기

```console
$ equion sim base --as s1
$ equion report new memo --title "이번 달 전망"
$ equion report add memo sim:s1 --rows Y,CN,I --show yoy --annual --title "성장률" --under "## 본문"
$ equion report add memo an:ur1#1 --title "단위근 검정"
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

$ equion report new memo --title "이번 달 전망"
[report new] reports/memo.md
  바뀜 기록  h0004

$ equion report add memo sim:s1 --rows Y,CN,I --show yoy --annual --title "성장률" --under "## 본문"
[report add] reports/memo.md
  #1 sim:s1  넣음 — **표 1. 성장률** (연간 증가율, %)
  바뀜 기록  h0005

$ equion report add memo an:ur1#1 --title "단위근 검정"
[report add] reports/memo.md
  #2 an:ur1  넣음 — **표 2. 단위근 검정**
  바뀜 기록  h0006
```

`reports/memo.md`의 구역에는 보이지 않는 표시(기록·보낸 모양)가 붙습니다. 구역 밖의 글(`## 요약`의 `(글)` 자리)은 사람이 씁니다.

## 4. 새 기록으로 바꾸기

가정이 바뀌어 전망을 다시 풀었습니다. `report update`가 같은 모양으로 다시 만들어 숫자의 차이를 보입니다(`--dry-run`이면 보기만).

```python
import pandas as pd

a = pd.read_csv("ASSUMPTIONS/base.csv", index_col=0)
a["G"] *= 1.02
a.to_csv("ASSUMPTIONS/base.csv", float_format="%.3f")
```

```console
$ equion sim base --as s2
$ equion report update memo --region 1 --to sim:s2
```
<!-- out -->
```text
$ equion sim base --as s2
[sim:s2] main · base · 2020Q1~2021Q4 dynamic · 정상 8 · 일부식 제외 0 · 실패대체 0 · 실패 0
  연간 증가율  2020: Y 1.84% · CN 1.73% · I 0.37% · P 2.78% │ 2021: Y 2.27% · CN 2.21% · I 2.74% · P 2.72%
  가정   base: G·POIL 16칸 · 채움(last) R 8칸
  보정항  base: demand:CN last(+0.654) · demand:I decay
  알아서 한 것  구간 next:8 → 2020Q1~2021Q4 · 채택 기록 없이 지금 자료로 추정: demand:CN, demand:I, price:P, finance:RL, finance:M2 · 보정항 규칙 값 16칸 · 가정 16칸(G, POIL) · 외생 R 8칸을 채움(last)
  기록   sim:s2 (work/sim/s2/)

$ equion report update memo --region 1 --to sim:s2
[report update] reports/memo.md — 구역 1
  #1 sim:s1 → sim:s2  바뀜
    --- #1(전)
    +++ #1(후)
    @@ -2,8 +2,8 @@

     | 시리즈 | 2020 | 2021 |
     |---|---|---|
    -| Y | 0.9 | 1.7 |
    -| CN | 0.9 | 1.7 |
    -| I | -0.3 | 2.0 |
    +| Y | 1.8 | 2.3 |
    +| CN | 1.7 | 2.2 |
    +| I | 0.4 | 2.7 |

    -자료: Equion sim:s1(자료 회차 d2026-11a)
    +자료: Equion sim:s2(자료 회차 d2026-11a)
  바뀜 기록  h0008
```

손으로 구역의 숫자를 고쳤다면 덮지 않고 고친 곳을 보입니다 — 덮으려면 `--force`.

```python
memo = Path("reports/memo.md")
memo.write_text(memo.read_text(encoding="utf-8").replace("| Y |", "| Y(고침) |", 1), encoding="utf-8")
```

```console
$ equion report check memo
$ equion report update memo --region 1 --to sim:s1
```
<!-- out -->
```text
$ equion report check memo
[report check] reports/memo.md — 구역 2
  #1 sim:s2  손으로 고침
  #2 an:ur1  정상

$ equion report update memo --region 1 --to sim:s1
[report update] reports/memo.md — 구역 1
  #1 sim:s2 → sim:s1  손으로 고침 — 바꾸지 않음(--force) — 고친 곳
    --- 보낸 것 → 지금(전)
    +++ 보낸 것 → 지금(후)
    @@ -2,7 +2,7 @@

     | 시리즈 | 2020 | 2021 |
     |---|---|---|
    -| Y | 1.8 | 2.3 |
    +| Y(고침) | 1.8 | 2.3 |
     | CN | 1.7 | 2.2 |
     | I | 0.4 | 2.7 |
```

## 5. 엑셀로

```console
$ equion export sim:s1 sim:s2 --xlsx exports/memo.xlsx
```
<!-- out -->
```text
$ equion export sim:s1 sim:s2 --xlsx exports/memo.xlsx
[export] exports/memo.xlsx — 기록 2 · 시트 11: 출처, s1_수준, s1_값의종류, s1_연간, s1_증가율, s1_보정항, s2_수준, s2_값의종류 …
```

## 확인할 것

- [ ] 분석마다 `work/an/<이름>/summary.md`(표·차트) 카드가 생긴다
- [ ] `an keep`이 식 후보를 만들어 `compare`에 나온다
- [ ] 노트의 블록 아래에 결과 구역이 채워지고, 다시 돌리면 새 기록으로 바뀐다
- [ ] 보고서가 Lectern·편집기에서 표·차트로 읽힌다(차트 자료는 `reports/<보고서>_data/`)
- [ ] `report update`가 숫자의 차이를 보이고, 손으로 고친 구역은 `--force` 없이 덮지 않는다

다음: [7. Claude와 함께](07-with-claude.md)
