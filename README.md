# Equion — 방정식·연립방정식 추정과 풀이

> **English:** see [README.en.md](README.en.md) — Equion is a Python package for estimating single equations and
> simultaneous-equation systems and for solving, simulating and forecasting them (library + command line).
> EViews is a registered trademark of S&P Global Inc.; this project is independent and not affiliated with it.

**Equion**은 개별 회귀식부터 비선형 연립방정식 모델까지 **추정 → 연립 풀이 → 과거 재현(Historical Simulation) →
전망·시나리오**를 수행하는 Python 패키지입니다. **방정식(회귀 체계)은 언제든 바뀌는 입력**이고, 엔진이
그것을 견고하게 받아 같은 의미로 추정하고 풀도록 설계했습니다. 라이브러리(`import equion as eqn`)와
명령줄(`equion run`)로 씁니다. Windows 데스크톱 앱 **Equion Desk**는 Equion이 충분히 다듬어진 뒤 만듭니다(기획).

- 버전: Equion **0.7.0** (2026-10-30)
- 스택: Python 3.12+ · numpy · pandas · scipy · openpyxl (회귀·검정은 자체 구현, 그래프는 내장 plotly.js)
- 라이선스: [MIT](LICENSE)
- **문서: [docs/README.md](docs/README.md)** — 설치 · [30분 첫 모델](docs/start/first-model.md) · 튜토리얼 8편 · 레시피 · 해설 · 참조 ·
  사례 연구. 예제는 패키지에 든 예제 자료(`eqn.datasets`)로 바로 돌고, 문서의 출력은 실제 실행 결과입니다.

---

## 주요 기능

- **간결한 시계열 방정식 문법**(EViews 사용자에게 익숙한 표기): `log(Y) c log(X(-1)) X^2 @pcy(Z) d(W,1,4)`, 시차범위 `X(-1 to -4)`,
  `@seas`·`@trend`·`@d`·`@step`·`@smpl`·`@def`. 괄호 안 공백도 자유롭게.
- **추정법**: OLS · WLS · 2SLS(`@inst`) · GMM(Hansen J) · LIML · NLS(`Y = c(1) + c(2)*X^c(3)`) · 외부 계수 고정(`@coef`),
  AR(p) 오차(`ar(1)`) · 다항 분포시차(`pdl(X, 8, 3)`) · 오차수정모형(`wf.ecm`). 강건 표준오차(White·HC0~3·HAC Newey-West).
- **시스템·다변량**: SUR · 2SLS · 3SLS · FIML(식 사이 제약 — 같은 `c(n)` 공유 또는 `restrict`), VAR(시차 선택·Granger·
  충격반응·분산분해) · VECM(Johansen 최우) — 추정 결과는 그대로 모델 식이 됩니다.
- **진단·검정**: 계열상관 LM·Ljung-Box·White·Breusch-Pagan·ARCH·Jarque-Bera·RESET·Wald·Chow·CUSUM·누락/불필요 변수,
  단위근·공적분(ADF·KPSS·Engle-Granger·Johansen), 예측 평가(Theil U·Diebold-Mariano). 회귀와 검정은 모두 자체 구현(`equion.stats`) —
  외부 회귀 패키지에 기대지 않습니다(필수 의존성: numpy·pandas·scipy·openpyxl — pyarrow·plotly는 선택 `equion[all]`).
- **추정식과 풀이식의 의미가 항상 같음**: 모든 시계열 연산을 하나의 중간표현(IR)으로 풀어
  추정·풀이·자코비안이 모두 같은 표현을 씁니다.
- **견고한 연립 풀이**: 블록 분해 + 해석적 자코비안 Newton(실패 시 hybr·lm·Gauss-Seidel 재시도).
  입력 결측·미수렴은 정책에 따라 처리하고 기간마다 상태를 남기며, **실패한 해를 다음 기간으로
  흘려보내지 않습니다.**
- **연립모형 기능**: 동적·정적·fit 모의, 전망(기간 확장·외생 경로), 시나리오(override·exclude
  ·조정항·충격), 확률적 모의, 목표추적(control), 승수, 선행변수(Fair-Taylor·stacked-time), 큰 블록 희소 자코비안,
  **동태 안정성**(선형화 동반행렬 고윳값)·**시나리오 기여도 분해**(Shapley).
- **자료**: 메타데이터, 다른 주기 페이지, 주기 변환(집계·Denton·Chow-Lin), 계절조정(STL·고전 분해).
- **안전**: 방정식 텍스트는 허용 목록 문법만 통과하고 길이·중첩·시차에 한도가 있습니다(텍스트로 코드 실행 불가).
  보고서의 비밀 값은 가리고(`eqn.secret`·`--redact`), 레거시 pickle은 기본으로 열지 않습니다.
- **Python 완전 연동**: 워크파일 API(`eqn.wfopen` · `wf.equation(…).ls(…)` · `m.solve()`)의 모든 결과가
  pandas 객체로 바로 이어지고, 스크립트는 평범한 Python입니다.
- **명령줄**: `equion run 스크립트.py --set 이름=값` — 보고서 폴더(`report.html`·재현 기록 `manifest.json`
  ·표·그래프), 자동화용 종료 코드, `check`(실행 없이 방정식·구조 검사)·`info`·`new`.

## 설치

아직 PyPI에 올리지 않았으므로 저장소에서 설치합니다.

```bash
pip install "equion[all] @ git+https://github.com/samiblog/equion"
```

이 저장소를 받아 개발 환경을 만들려면 [uv](https://docs.astral.sh/uv/)를 씁니다(`uv.lock`의 고정 판).

```bash
uv sync
```

자세한 것은 [설치](docs/start/install.md).

## 5분 예제

작업 흐름은 EViews 사용자에게 익숙하게, 문법과 결과는 모두 Python입니다. 예제 자료 `toy_q`는 알려진 참 모형에서 만든 가상
분기 자료라 추정 결과를 참값과 견줄 수 있습니다.

```python
import equion as eqn

wf = eqn.datasets.load("toy_q")                                   # 워크파일(예제 자료 — 직접 쓸 땐 eqn.wfopen("파일.xlsx"))
eq_i = wf.equation("eq_i").ls("I c Y(-1) R")                       # 투자: 지난 분기 소득·금리
eq_cn = wf.equation("eq_cn").tsls("CN c Y CN(-1) @inst G R CN(-1) Y(-1)")   # 소비(2SLS — 소득이 내생)
eqn.show(eq_cn)                                                    # 추정 결과표

m = wf.model("toy").merge(eq_i, eq_cn).append("Y = CN + I + G")    # 연립 모델(항등식 추가)
wf.smpl("1990Q1", "2019Q4")
eqn.show(m.solve().summary())                                      # 기준선 과거 재현 → Y_0 … 시리즈

m.scenario("g_up").shock("G", 10, "2015Q1", "2019Q4", kind="pct")  # 시나리오: 정부지출 +10%
m.solve()                                                          # → *_1 시리즈
print(m.compare("Y").tail(4).round(1))

m.forecast("2020Q1", "2021Q4", exog_fill="trend", scenario="baseline")      # 전망
wf.save("toy")                                                     # → toy.eqw/
```

모든 결과는 pandas 객체라 Python에서 바로 이어 씁니다 — `eq.diagnostics()`·`eq.wald("c(2) = 0")`·
`wf.adf("log(Y)")`로 검정, `eq.ls(…, cov="hac")`로 강건 표준오차, `wf["X"] = 어떤 계산`, 시나리오는
`for` 반복으로 격자를 돌립니다. 처음부터 차례로 배우려면 [30분 첫 모델](docs/start/first-model.md)과
[튜토리얼](docs/tutorial/README.md), 엔진 수준 API(`WorkTable`)는 [`docs/explain/engine.md`](docs/explain/engine.md).

## 방정식 파일 맛보기

```text
# 추정식(OLS): 종속변수 c 설명변수 ...  (= 없음)
log(CN) c log(Y - G) log(CN(-1)) @seas

# 2SLS / 외부 계수 / 비선형
log(CN) c log(Y) log(CN(-1)) @inst log(Y(-1)) log(CN(-1)) log(G)
log(P) c log(POIL) log(P(-1)) @coef 0.1 0.03 0.95
CN = c(1) * Y^c(2)  @start 1 1

# 항등식: 최상위 = (공백 무관), 좌변은 식이어도 됨
Y = CN + I + G
```

전체 문법은 [`docs/explain/equations.md`](docs/explain/equations.md), 함수 목록은 [`docs/reference/functions.md`](docs/reference/functions.md)에 있습니다.

## 구조

```
방정식 텍스트
 → parser    분류 · 항 분리 · EViews 표기 · 허용 목록 검증       equion/formula/parser.py
 → IR        시계열 연산을 시차 변수의 산술식으로 전개              equion/formula/ir.py
 → 추정      OLS · TSLS · NLS · fixed                              equion/estimation/
 → 구조 분석 정규화 매칭 · 정방성 검사 · 블록 분해                 equion/system/analyzer.py
 → 컴파일    블록별 잔차·자코비안 함수 (모델당 1회)                equion/system/compiler.py
 → 풀이      Newton + 폴백, 기간 루프, 결측·실패 정책              equion/system/{solver,simulate}.py
 → 시나리오  override · exclude · 조정항 · 충격 · 확률 · control   equion/scenario/
```

| 폴더 | 내용 |
|------|------|
| `equion/` | 패키지 (위 구조 + `data`·`stats`·`reporting`·`workfile`·`cli`·`worktable`·`datasets`) |
| `tests/` | `test_engine.py` · `test_workfile.py` · `test_cli.py` · `test_stats.py` · `test_scenarios.py`(상황별 시나리오) 외, 기준값 `fixtures/` — 모두 예제 자료로 돈다 |
| `docs/` | 사용자 문서(시작하기·튜토리얼·레시피·해설·참조·사례 연구·영문) · 설계 결정 · 로드맵 |
| `examples/` | 문서에서 자동으로 만든 예제 스크립트·노트북 |

## 명령줄

노트북과 같은 스크립트를 명령줄에서 실행하고 결과를 보고서 폴더로 남깁니다.

```bash
equion new myproject
```

```bash
equion run scripts/main.py --set g_shock=0.05 --format csv,xlsx,html
```

```bash
equion check EQUATIONS/model.txt --data DATA/data.csv
```

- `run`: `out/<실행ID>/`에 `report.html`(표·그래프·로그 한 페이지) · `manifest.json`(버전·git 커밋·매개변수
  ·입력 파일 sha256·기간별 풀이 상태) · `run.log` · `tables/` · `graphs/`.
  주요 옵션: `--set`·`--params`·`--smpl`·`--format`·`--fail-on`·`--threads`·`-q`·`-i`·`--watch`.
- `check`: 추정·풀이 없이 줄별 문법, 모델 구조(목표변수 중복·미지 변수·블록), 표본 구간의 결측 입력.
- `info`: 데이터·워크파일·방정식 파일·보고서 폴더 요약. `new`: 바로 실행되는 예시 프로젝트.
- 종료 코드: 0 성공 · 1 스크립트 오류 · 2 풀이 실패(`--fail-on`) · 3 입력 오류 · 130 중단.

스크립트는 평범한 Python이고 매개변수는 `p = eqn.params(g_shock=0.02)`로 받습니다. 자세한 내용은
[튜토리얼 8](docs/tutorial/08-cli.md)과 [명령줄 참조](docs/reference/cli.md).

## 문서

| 문서 | 내용 |
|------|------|
| [`docs/README.md`](docs/README.md) | 사용자 문서 첫 페이지 — 시작하기 · 튜토리얼 · 레시피 · 해설 · 참조 · 사례 연구 · EViews 사용자 안내 |
| [`docs/reference/api.md`](docs/reference/api.md) | 공개 함수·메서드 참조(docstring에서 자동 생성 — `python docs/make_api.py`) |
| [`CHANGELOG.md`](CHANGELOG.md) | 판별 바뀐 점 |
| [`README.en.md`](README.en.md) · [`docs/en/`](docs/en/README.md) | English overview · getting started |
| [`docs/DECISIONS.md`](docs/DECISIONS.md) · [`docs/ROADMAP.md`](docs/ROADMAP.md) | 설계 결정(세 단계·API·법적 원칙) · 진행 계획(라이브러리 → CLI → 데스크톱) |
| [`CLAUDE.md`](CLAUDE.md) | 개발 가이드 — 모듈 구조, 검증 절차, 작업 시 주의 |

## 개발

```bash
uv run pytest
```

- 수치 코어(`formula/parser.py`·`formula/ir.py`·`system/*`·`estimation/equation.py`·`stats/*`)를 바꾸면
  `tests/test_engine.py`의 번역 일관성 검사와 `tests/test_stats.py`의 기준값 비교가 반드시 통과해야 합니다.
- 의존성은 `pyproject.toml`에 범위로 적고 `uv.lock`이 정확한 버전·해시를 잠급니다(`uv add` / `uv remove`). 하한·최신판·
  Windows·macOS는 CI가 검사합니다(`.github/workflows/ci.yml`).
- 공개 함수·메서드의 docstring을 고치면 `python docs/make_api.py`로 `docs/reference/api.md`를 다시 만듭니다(CI가 `--check`).
- 문서의 예제를 고치거나 출력이 바뀌는 코드를 고치면 `python docs/build_docs.py`로 출력·`examples/`를 다시 채웁니다
  (CI가 `--check` — 예제 실행·출력·링크·API 설명·doctest).

## 라이선스·상표

[MIT License](LICENSE) © 2025-2026 samiblog · 포함된 외부 자료(단위근·공적분 수치표, plotly.js)의 고지는 [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md)

EViews는 S&P Global Inc.의 등록상표입니다. 이 프로젝트는 EViews 및 S&P Global과 관계가 없으며, EViews의 코드·설명서·그림을 사용하지 않습니다. 작업 흐름을 EViews 사용자에게 익숙하게 만든 독립적인 구현입니다(설계 원칙: [`docs/DECISIONS.md`](docs/DECISIONS.md) D13).
