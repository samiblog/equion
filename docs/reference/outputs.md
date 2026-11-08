# 출력 표 읽는 법

Equion이 내는 표와 사전의 항목. 아래 코드는 실제 항목 이름을 찍어 이 문서가 코드와 같은지 확인합니다.

```python
import equion as eqn

wf = eqn.datasets.load("toy_q")
eq = wf.equation("eq_i").ls("I c Y(-1) R")
print(sorted(eq.stats))
```
<!-- out -->
```text
[toy_q] 열기 toy_q.csv — 분기(Quarterly) 1970Q1~2019Q4 · 시리즈 10
[eq_i] OLS I — n=199, R²=0.9985
['adj_r_squared', 'aic', 'bic', 'cov_label', 'cov_type', 'durbin_watson', 'f_pvalue', 'f_statistic', 'log_likelihood', 'method', 'n_obs', 'r_squared', 'se_regression', 'ssr']
```

## 회귀 결과표와 `eq.stats`

| 항목(`stats` 키) | 표에서 | 뜻 |
|---|---|---|
| 계수 · 표준오차 · t값 · p값 | 계수 표 | `eq.coefs` · `eq.stderrs` · `eq.tstats` · `eq.pvalues`. 별표: *** 1% · ** 5% · * 10% |
| `r_squared` | R² | 1 − SSR/중심화 총제곱합(상수항이 없으면 `r_squared_uncentered`도) |
| `adj_r_squared` | 조정 R² | 1 − (1 − R²)(n − 1)/(n − k) |
| `se_regression` | 회귀 표준오차 | √(SSR/(n − k)) |
| `ssr` | | 잔차 제곱합 |
| `durbin_watson` | DW | Σ(eₜ − eₜ₋₁)²/Σeₜ² — 2 근처면 1차 자기상관이 작다 |
| `log_likelihood` · `aic` · `bic` | 로그우도 · AIC · BIC | 정규 오차 가정. 정보기준은 같은 종속변수·표본끼리 비교 |
| `f_statistic` · `f_pvalue` | F | 상수항 말고 모든 계수 = 0 |
| `n_obs` · `method` · `cov_type` · `cov_label` | 머리말 | 관측치 · 추정법 · 공분산 종류 |
| `collinear` | 꼬리 줄 ⚠ | 선형 종속인 회귀변수(있을 때만) |
| `j_statistic` · `j_pvalue` · `j_df` | | GMM의 Hansen J(과대식별 검정) |
| `liml_kappa` | | LIML의 κ |
| `unweighted_*` | | WLS의 가중 전 R²·SSR·DW |
| `r_squared_uncentered` | | 상수항이 없을 때 비중심 R² |

## 검정 결과(`TestResult`)

| 속성 | 뜻 |
|---|---|
| `.statistic` · `.pvalue` | 대표 통계량과 p값(없으면 NaN — 예: CUSUM은 경계 대비 비율만) |
| `.null` | 귀무가설(글) |
| `.reject(0.05)` | 그 수준에서 기각하는가 |
| `.rows` · `.info` · `.table` | 보조 통계(F 형태·임계값 …) · 머리말 정보(시차·표본 …) · 딸린 표(시차별 Q, 순위별 Johansen) |
| `.graph` · `.data` | CUSUM 같은 그림과 기간별 값 |

## 풀이 결과(`SolveResult`)

```python
m = wf.model("toy").merge(eq, "CN c Y CN(-1)").append("Y = CN + I + G")
r = m.solve("2010Q1", "2010Q4")
print(list(r.status().columns))
print(list(r.statistics().columns))
```
<!-- out -->
```text
[eq_cn] OLS CN — n=199, R²=0.9999
[toy] baseline(_0) dynamic 2010Q1~2010Q4: 정상 4 · 일부식 제외 0 · 실패대체 0 · 실패 0
['t', 'status', 'iterations', 'max_resid', 'methods', 'excluded', 'fallback', 'message']
['RMSPE', 'MAE_pct', 'MAE', 'RMSE', 'mean_error', 'std_error', 'n_samples', 'n_excluded']
```

`r.status()` — 기간마다:

| 열 | 뜻 |
|---|---|
| `status` | `ok` · `partial` · `fallback` · `failed`([연립 풀이](../explain/solving.md#결측과-실패--기간-상태)) |
| `iterations` | 블록 풀이 반복 수의 합 |
| `max_resid` | 가장 큰 정규화 잔차(수렴 기준 1e-10) |
| `methods` | 쓴 풀이법 |
| `excluded` | 입력이 비어 뺀 식과 이유(`I:Y(-1) 범위 밖`) |
| `fallback` | 실측으로 대신한 변수 |
| `message` | 실패 블록과 시도한 방법 |

`r.statistics()` — 변수마다(실측으로 대신한·뺀 기간은 제외):

| 열 | 뜻 |
|---|---|
| `RMSPE` | 평균 제곱근 백분율 오차(%) — 0 근처 계열은 과대 |
| `MAE_pct` | 평균 절대 백분율 오차(%) |
| `MAE` · `RMSE` | 평균 절대 오차 · 평균 제곱근 오차(수준) |
| `mean_error` · `std_error` | 평균 오차(치우침) · 오차 표준편차 |
| `n_samples` · `n_excluded` | 쓴 기간 수 · 뺀 기간 수 |

## HS CSV(`r.save(path)`)

열: `period` · `time_index` · 상태 열(`status`·`iterations`·`max_resid`·`excluded`·`fallback`) · 변수마다 `X_hs`(풀이) ·
`X_actual`(실측) · `X_error_pct`(오차 %). UTF-8(BOM)으로 써서 엑셀에서 한글이 깨지지 않습니다.

## 진단 한 표(`eq.diagnostics()`)

열: `통계량` · `p값` · `5%에서`(기각·기각 못 함) · `귀무가설`. 행: 계열상관 LM · White · Breusch-Pagan-Godfrey · Ljung-Box ·
ARCH LM · Jarque-Bera · RESET(OLS가 아니면 잔차 검정만).

## 보고서 manifest.json

명령줄 보고서의 재현 기록. `format: "equion-run"`과 `format_version`이 형식을 밝히고, 필드를 바꾸면 판을 올립니다.

| 필드 | 뜻 |
|---|---|
| `run_id` · `status` · `exit_code` | 실행 ID · `ok`·`error`·`solve_failed`·`input_error`·`interrupted` · 종료 코드 |
| `script` · `script_sha256` · `argv` · `script_args` · `cwd` | 실행한 것(`--redact`면 경로를 줄이고 작업 폴더를 뺀다) |
| `params` | `overrides`(준 값) · `resolved`(최종 값) · `unused`(스크립트가 쓰지 않은 `--set`) |
| `smpl` · `fail_on` · `fail_reasons` · `error` | 기본 표본 · 실패 조건과 사유 · 오류(형식·메시지) |
| `started_at` · `finished_at` · `elapsed_sec` | 시각 |
| `versions` · `platform` · `threads` · `git` | equion·numpy·pandas·scipy·BLAS 판, OS·CPU, 스레드, git 커밋·변경 여부 |
| `inputs` · `written` | 읽은 파일(경로·종류·sha256·크기) · 스크립트가 쓴 파일 |
| `solves` | 풀이마다 모델·시나리오·구간·모드·상태 수·기간별 상태 |
| `outputs` | `eqn.show`로 보인 출력(종류·이름·제목·파일) |

관련: [파일 형식](formats.md)
