# 예제 자료

`eqn.datasets`에는 문서·튜토리얼·레시피가 쓰는 작은 자료 넷이 들어 있습니다. 패키지에 함께 설치되므로 어느 폴더에서든 바로 열립니다.

**모두 가상 자료입니다.** 알려진 '참 모형'에 고정 시드 난수를 넣어 만들었으므로, 추정 결과를 참값과 비교할 수 있습니다.
실제 경제 자료가 아니니 결과로 경제를 해석하지 마세요.

| 이름 | 주기·기간 | 쓰는 곳 |
|---|---|---|
| `toy_q` | 분기 1970Q1~2019Q4(200기) | 거의 모든 예제 — 추정·진단·모델·시나리오·전망·공적분 |
| `toy_a` | 연 1970~2019(50년) | 연간 모델, 주기 변환 |
| `toy_m` | 월 2000M1~2019M12(240개월) | 계절조정·월간 지표·주기 변환 |
| `klein_like` | 연 1921~1990(70년) | 시스템 추정(2SLS·3SLS·FIML)·승수 |

```python
import equion as eqn

print(eqn.datasets.names())
wf = eqn.datasets.load("toy_q")          # 워크파일로(시리즈 설명·단위·집계 방식 메타데이터 포함)
print(wf.meta("Y"))
print(eqn.datasets.path("toy_q").endswith("toy_q.csv"))   # CSV 파일 자체
```
<!-- out -->
```text
['klein_like', 'toy_a', 'toy_m', 'toy_q']
[toy_q] 열기 toy_q.csv — 분기(Quarterly) 1970Q1~2019Q4 · 시리즈 10
{'desc': '국민소득 = CN + I + G', 'unit': '조원(가상)', 'agg': 'sum', 'source': 'Equion 예제 자료(가상)'}
True
```

## toy_q — 작은 분기 거시 모형

```python
print(eqn.datasets.describe("toy_q"))
```
<!-- out -->
```text
작은 거시 모형 — 분기(1970Q1~2019Q4, 200기)

참 모형:
  I  = 5 + 0.15·Y(-1) − 1.0·R + e₂                         (투자)
  CN = 10 + 0.5·Y + 0.3·CN(-1) + e₁                         (소비 — Y가 내생이라 OLS는 치우친다)
  Y  = CN + I + G                                            (국민소득 항등식)
  dlog(P) = 0.005 + 0.3·dlog(Y) + 0.02·dlog(POIL) + e₃      (물가)
  RL = 1 + R + u,  u = 0.7·u(-1) + ε                        (장기금리 — R과 공적분, 1980Q1부터)
  log(M2) = −2 + log(P) + 0.8·log(Y) − 0.03·RL + v,  v = 0.8·v(-1) + ε  (통화 — 공적분)
  CNNSA = CN × 계절 요인(1.03·0.98·1.01·0.98) × 잡음        (계절조정 전 소비)

변수:
  CN     소비 [조원(가상)]
  I      투자 [조원(가상)]
  G      정부지출(외생) [조원(가상)]
  Y      국민소득 = CN + I + G [조원(가상)]
  R      정책금리(외생) [%]
  RL     장기금리(1980Q1부터) [%]
  P      물가 지수 [지수]
  POIL   유가 지수(외생) [지수]
  M2     통화량 [조원(가상)]
  CNNSA  소비(계절조정 전) [조원(가상)]
```

`CN` 식에는 같은 기의 `Y`가 오른쪽에 있고 `Y = CN + I + G`이므로 `Y`가 오차와 상관됩니다. 그래서 OLS 추정은 치우치고,
외생변수를 도구로 쓰는 2SLS가 참값(10 · 0.5 · 0.3)에 더 가깝습니다:

```python
ols = wf.equation("eq_ols").ls("CN c Y CN(-1)")
iv = wf.equation("eq_iv").tsls("CN c Y CN(-1) @inst G G(-1) Y(-1) CN(-1)")
print("OLS ", ols.coefs.round(3).tolist())
print("2SLS", iv.coefs.round(3).tolist())
```
<!-- out -->
```text
[eq_ols] OLS CN — n=199, R²=0.9999
[eq_iv] TSLS CN — n=199, R²=0.9999
OLS  [11.647, 0.587, 0.178]
2SLS [10.664, 0.532, 0.255]
```

다른 식의 참값: `I`는 5 · 0.15 · −1.0, 물가 식은 0.005 · 0.3 · 0.02입니다. `RL`과 `R`, `log(M2)`와 `log(P)`·`log(Y)`·`RL`은
공적분 관계로 만들었으므로 단위근·공적분 검정과 VECM 예제에 씁니다. `CNNSA`는 `CN`에 계절 요인을 곱한 계열(계절조정 예제)입니다.

## toy_a — 같은 경제의 연간 자료

```python
print(eqn.datasets.describe("toy_a"))
```
<!-- out -->
```text
작은 거시 모형 — 연간(1970~2019, 50년). toy_q를 연간으로(흐름은 합, 금리·지수는 평균)

참 모형:
  toy_q와 같은 경제를 연간으로 본 자료 — 연간 식은 분기 식의 근사다

변수:
  CN     소비 [조원(가상)]
  I      투자 [조원(가상)]
  G      정부지출(외생) [조원(가상)]
  Y      국민소득 = CN + I + G [조원(가상)]
  R      정책금리(외생) [%]
  RL     장기금리(1980년부터) [%]
  P      물가 지수 [지수]
  POIL   유가 지수(외생) [지수]
  M2     통화량(연평균) [조원(가상)]
```

`toy_q`를 연간으로 모은 자료입니다(흐름 변수는 합, 금리·지수는 평균). 연간 식은 분기 식의 근사이므로 계수가 분기 참값과 같지 않습니다.

## toy_m — 월간 지표

```python
print(eqn.datasets.describe("toy_m"))
```
<!-- out -->
```text
같은 경제의 월간 지표(2000M1~2019M12, 240개월)

참 모형:
  IP   = toy_q Y의 월간 경로 × 월별 계절 요인 × 잡음  (산업생산, 계절조정 전, 2000년 평균 = 100)
  CPIM = toy_q P의 월간 경로 × 약한 계절 요인 × 잡음  (소비자물가, 계절조정 전, 2000년 평균 = 100)
  RM   = toy_q R + 잡음                              (월평균 정책금리)

변수:
  IP     산업생산(계절조정 전) [지수(2000 = 100)]
  CPIM   소비자물가(계절조정 전) [지수(2000 = 100)]
  RM     월평균 정책금리 [%]
```

`IP`·`CPIM`은 계절조정 전 계열이라 STL·고전 분해 예제에 쓰고, 분기로 모아 `toy_q`와 비교할 수 있습니다.

## klein_like — Klein 모형 I 구조의 가상 자료

```python
print(eqn.datasets.describe("klein_like"))
```
<!-- out -->
```text
Klein 모형 I의 구조로 만든 가상 자료 — 연간(1921~1990, 70년). 실제 Klein 자료가 아니다

참 모형:
  CONS = 16.4 + 0.125·PR + 0.163·PR(-1) + 0.79·(WP + WG) + e₁   (소비)
  I    = 28.2 − 0.013·PR + 0.756·PR(-1) − 0.195·K(-1) + e₂       (투자)
  WP   = 1.8 + 0.4·X + 0.181·X(-1) + 0.15·A + e₃                (민간 임금)
  X = CONS + I + G,  PR = X − T − WP,  K = K(-1) + I          (항등식)

변수:
  CONS   소비(Klein의 C — 이름 C는 상수항이라 CONS) [가상]
  I      순투자 [가상]
  WP     민간 임금 [가상]
  X      총수요 = CONS + I + G [가상]
  PR     이윤 = X − T − WP [가상]
  K      자본스톡(연말) = K(-1) + I [가상]
  G      정부지출(외생) [가상]
  T      세금(외생) [가상]
  WG     정부 임금(외생) [가상]
  A      추세 = 연도 − 1931(외생) [년]
```

교과서에 자주 나오는 Klein 모형 I(소비·투자·민간 임금 세 식, 항등식 셋)을 본떠 만들었습니다. 참 계수는 문헌에서 흔히 보는 크기로
정했지만 실제 자료를 추정한 값을 재현하려는 것은 아닙니다. 실제 자료는 22년(1920~1941)이지만, 이 자료는 추정 결과가 안정되도록
70년으로 만들었습니다. 이름 `C`는 상수항이므로 소비는 `CONS`, 이윤 `P`는 `PR`입니다.

```python
kw = eqn.datasets.load("klein_like")
s = kw.system("kl")
s.append("CONS c PR PR(-1) WP+WG", "I c PR PR(-1) K(-1)", "WP c X X(-1) A", "@inst G T WG A PR(-1) K(-1) X(-1)")
s.three_sls()
true = [16.4, 0.125, 0.163, 0.79, 28.2, -0.013, 0.756, -0.195, 1.8, 0.4, 0.181, 0.15]
print(s.coefs.round(2).tolist())
print(true)
```
<!-- out -->
```text
[klein_like] 열기 klein_like.csv — 연(Annual) 1921~1990 · 시리즈 10
[kl] 3단계 최소제곱(3SLS) — 식 3 · 계수 12 · 표본 69기
[16.45, 0.16, 0.11, 0.79, 30.64, -0.06, 0.81, -0.21, 1.41, 0.45, 0.14, 0.14]
[16.4, 0.125, 0.163, 0.79, 28.2, -0.013, 0.756, -0.195, 1.8, 0.4, 0.181, 0.15]
```

3SLS 계수가 참값 근처에 옵니다. 표본이 70기뿐이라 오차가 남고, 투자·임금 식의 상수항처럼 덜 정확한 계수도 있습니다.

## 실제 Klein 모형 I 자료 쓰기

실제 자료(미국 1920~1941)는 이용 조건이 분명하지 않아 패키지에 넣지 않았습니다. Klein(1950) *Economic Fluctuations in the United
States, 1921–1941*과 Greene *Econometric Analysis*의 자료 표에 실려 있고, 여러 통계 패키지도 예제 자료로 배포합니다 — 직접 구할 때
그 출처의 이용 조건을 확인하세요.

구한 파일(csv·xlsx — 첫 열이 연도)을 `eqn.datasets.klein(path)`로 열면 열 이름을 Equion 이름으로 바꿔 줍니다:

| 원래 열(대소문자·기호 무시) | Equion 이름 |
|---|---|
| `C` · `Cons` · `Consumption` | `CONS` |
| `P` · `Profit(s)` · `corpProf` | `PR` |
| `Wp` · `privWage` | `WP` |
| `I` · `K1`(전년 말 자본) · `X` · `Wg` · `G` · `T` | `I` · `K1` · `X` · `WG` · `G` · `T` |

추세 `A = 연도 − 1931`을 더하고, `K1`이 있으면 자본스톡 `K = K1 + I`도 만듭니다. 열이 모자라면 무엇이 없는지 알려 줍니다.

<!-- skip -->
```python
wf = eqn.datasets.klein("klein.csv")
wf.smpl("1921", "1941")
s = wf.system("klein")
s.append("CONS c PR PR(-1) WP+WG", "I c PR PR(-1) K1", "WP c X X(-1) A", "@inst G T WG A PR(-1) K1 X(-1)")
s.three_sls()
s.show()
```

결과는 문헌의 표(예: Greene의 Klein 모형 I 추정 예)와 비교할 수 있습니다. 판과 반올림에 따라 끝자리가 다를 수 있습니다.

## 다시 만들기

자료는 `equion/datasets/_make.py`가 고정 시드로 만듭니다. 참 모형을 바꾸려면 그 파일을 고치고 다시 만드세요:

```bash
python -m equion.datasets._make
```

자료를 바꾸면 그 자료를 쓰는 문서의 출력이 모두 바뀝니다 — `python docs/build_docs.py`로 다시 채우고 바뀐 숫자를 검토하세요.

관련: [튜토리얼](../tutorial/README.md) · [시스템 추정 튜토리얼](../tutorial/07-systems.md) · [`eqn.datasets` API](api.md)
