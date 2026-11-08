# 동태: 선행변수와 안정성

## 선행변수와 모형 일관 기대(MCE)

식에 앞 기간 값(`X(1)`, `X.t(1)`)이 들어가면 그 기의 풀이가 아직 풀지 않은 미래에 기댑니다.

- **mce 없이**(기본): 선행 값은 실측(또는 시나리오 경로)으로 고정됩니다 — 과거 재현에는 맞지만 전망·시나리오에서는 미래를
  모델이 정하지 않습니다. Equion은 선행변수가 있는 모델을 mce 없이 풀면 경고합니다.
- **`mce=True, mce_method="fair-taylor"`**: 선행 값을 추측해 기간 루프를 풀고, 풀이 값으로 추측을 고쳐 되풀이합니다(Fair-Taylor).
  `mce_damping`(0 < d ≤ 1)으로 고침을 줄일 수 있습니다.
- **`mce_method="stacked"`**: 모든 기간의 미지수를 한 번에 Newton으로 풉니다(stacked-time). 선행 계수가 커서 Fair-Taylor가
  발산하는 모형도 풀리고, 정확도가 높습니다.
- **`terminal`**: 지평 끝 다음의 선행 값 — `"actual"`(실측, 없으면 끝 값 유지) · `"hold"`(끝 값 유지).

```python
import equion as eqn

wf = eqn.datasets.load("toy_q")
wf["EXPT"] = wf["R"]                                        # 예: 기대를 담는 변수
fe = wf.equation("fe").fixed("EXPT c EXPT(1) EXPT(-1) R", [0.0, 0.3, 0.5, 0.2])
mq = wf.model("mq").merge(fe)
ft = mq.solve("2010Q1", "2012Q4", mce=True).values["EXPT"]
st = mq.solve("2010Q1", "2012Q4", mce=True, mce_method="stacked").values["EXPT"]
print(float((ft - st).abs().max()) < 1e-6)                      # 두 방법이 같은 해
```
<!-- out -->
```text
[toy_q] 열기 toy_q.csv — 분기(Quarterly) 1970Q1~2019Q4 · 시리즈 10
[fe] FIXED EXPT — n=198, R²=0.9913
[mq] baseline(_0) dynamic 2010Q1~2012Q4: 정상 12 · 일부식 제외 0 · 실패대체 0 · 실패 0
[mq] baseline(_0) dynamic 2010Q1~2012Q4: 정상 12 · 일부식 제외 0 · 실패대체 0 · 실패 0
True
```

## 동태 안정성

모델을 한 시점 근처에서 선형화하면 yₜ = A₁yₜ₋₁ + … + A_Lyₜ₋L + (외생 항) 꼴이 됩니다(같은 기 결합은 A₀로 풀어 넣는다). 이 동반행렬의
고윳값 λ가 편차의 움직임을 정합니다.

| 판정 | 고윳값 | 뜻 |
|---|---|---|
| 안정 | 모든 \|λ\| < 1 | 편차가 줄어든다 — 충격이 사라진다 |
| 단위근 | \|λ\| = 1인 근만 있고 1보다 큰 근 없음 | 수준이 적분된 변수(차분식의 목표 등) — 편차가 줄지도 커지지도 않음 |
| 불안정 | \|λ\| > 1인 근 | 편차가 커진다 — 동적 풀이가 발산하거나 크게 흔들린다 |

`measure="relative"`(기본)는 양수 변수의 상대 편차로 선형화해 로그식이 성장률만큼 부풀지 않게 합니다. `loadings`는 가장 큰 근과
함께 움직이는 변수의 비중 — 불안정의 출처를 찾는 출발점입니다(D24).

```python
m = wf.model("toy").merge("I c Y(-1) R", "CN c Y CN(-1)", "dlog(P) c dlog(Y) dlog(POIL)").append("Y = CN + I + G")
st = m.stability("2010Q1")
print(st.verdict, round(st.max_modulus, 4), st.loadings.round(2).to_dict())
eqn.show(m.stability_path("2010Q1", "2010Q4"))
```
<!-- out -->
```text
[eq_i] OLS I — n=199, R²=0.9985
[eq_cn] OLS CN — n=199, R²=0.9999
[eq_p] OLS dlog(P) — n=199, R²=0.3271
단위근 1.0 {'P': 1.0, 'I': 0.0, 'CN': 0.0, 'Y': 0.0}
────────────────────────────────────────
       최대 모듈러스  1 이상인 근     안정   판정
기간
2010Q1  1.0000        1  False  단위근
2010Q2  1.0000        1  False  단위근
2010Q3  1.0000        1  False  단위근
2010Q4  1.0000        1  False  단위근
────────────────────────────────────────
```

물가 `P`는 `dlog(P)` 식의 목표라 근 1(단위근)을 가집니다. 소득·소비·투자 쪽 근은 1보다 작아 안정합니다.

관련: [연립 풀이](solving.md) · [튜토리얼 7: Klein형 모형의 안정성](../tutorial/07-systems.md#73-시스템을-모델에-넣기)
