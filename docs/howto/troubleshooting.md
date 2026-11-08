# 문제 해결

자주 만나는 문제와 고치는 법. 각 항목의 오류 메시지는 실제 출력입니다. 메시지별 목록은 [오류 메시지 참조](../reference/errors.md).

```python
import equion as eqn

wf = eqn.datasets.load("toy_q")
eq_i = wf.equation("eq_i").ls("I c Y(-1) R")
eq_cn = wf.equation("eq_cn").ls("CN c Y CN(-1)")
```
<!-- out -->
```text
[toy_q] 열기 toy_q.csv — 분기(Quarterly) 1970Q1~2019Q4 · 시리즈 10
[eq_i] OLS I — n=199, R²=0.9985
[eq_cn] OLS CN — n=199, R²=0.9999
```

## T1. "데이터에도 없고 어떤 식도 결정하지 않는 변수가 있습니다"

모델의 식에 쓴 변수가 자료에도 없고 어떤 식의 목표변수도 아닙니다 — 오타이거나 시리즈를 아직 넣지 않았습니다.

<!-- error -->
```python
wf.model("t1").merge(eq_i, eq_cn).append("Y = CN + I + GOV").endogenous
```
<!-- out -->
```text
StructureError: 데이터에도 없고 어떤 식도 결정하지 않는 변수가 있습니다: GOV (사용: Y)
```

메시지 끝의 `(사용: Y)`가 그 변수를 쓴 식입니다. 이름을 고치거나(`G`) 시리즈를 넣습니다. 이름은 대소문자를 가리지 않습니다.

## T2. "같은 변수를 결정하는 식이 둘 이상입니다"

두 식이 같은 변수를 목표로 합니다(추정식 두 개, 또는 추정식과 항등식).

<!-- error -->
```python
eq_cn2 = wf.equation("eq_cn2").ls("CN c Y")
wf.model("t2").merge(eq_cn, eq_cn2).append("Y = CN + I + G").endogenous
```
<!-- out -->
```text
[eq_cn2] OLS CN — n=200, R²=0.9999
StructureError: 같은 변수를 결정하는 식이 둘 이상입니다 → CN: 추정식 'CN c Y CN(-1)', 추정식 'CN c Y'. 식 하나를 빼거나(모델의 drop) 그 식의 좌변을 바꾸세요 — 목표변수는 좌변의 첫 변수입니다.
```

하나를 빼거나(`m.drop("eq_cn2")`), 식의 좌변을 다른 변수로 바꿉니다. 목표변수는 좌변의 첫 변수입니다
(`log(CN/P)`의 목표는 `CN`).

## T3. 상태가 '일부식 제외'(partial)

그 기간에 어떤 식의 입력(대개 시차)이 비어 그 식을 빼고 풀었습니다. 빠진 식의 목표변수는 실측으로 둡니다.

```python
m = wf.model("t3").merge(eq_i, eq_cn).append("Y = CN + I + G")
r = m.solve("1970Q1", "1970Q4")
print(r.status()[["status", "excluded"]].head(2))
eqn.show(m.gaps("1970Q1", "1970Q1"))
```
<!-- out -->
```text
[t3] baseline(_0) dynamic 1970Q1~1970Q4: 정상 3 · 일부식 제외 1 · 실패대체 0 · 실패 0
         status                      excluded
period
1970Q1  partial  I:Y(-1) 범위 밖, CN:CN(-1) 범위 밖
1970Q2       ok
────────────────────────────────────────
   period  t equation target missing
0  1970Q1  0        I      I   Y(-1)
1  1970Q1  0       CN     CN  CN(-1)
────────────────────────────────────────
```

자료가 갖춰진 기간부터 풀거나(여기서는 1970Q2), 빈 입력을 채웁니다. 일부 변수의 자료가 짧으면 그 변수 쪽에서 생깁니다.

## T4. 상태가 '실패대체'(fallback)·'실패'(failed)

블록이 수렴하지 않았습니다(기본은 실측으로 대신하고 표시 — 실패한 해는 다음 기간으로 흘러가지 않는다). 원인 찾기:

1. `m.solve(on_fail="stop")` — 처음 실패한 기간에서 멈추고 블록·시도한 방법을 알려 준다
2. `m.solve(mode="static")`이 되면 동태 문제일 가능성 — `m.stability(기간)`으로 1보다 큰 근이 있는지
3. 풀이 설정 — `method="gauss-seidel"`·`fallback=(…)`·`max_iterations=200`
4. 식 자체 — 로그 안이 음수가 되는 경로, 0으로 나누는 식, 아주 큰 계수

값을 하나도 얻지 못한 기간(모든 식이 입력 결측으로 빠진 경우 등)도 '실패'입니다.

## T5. 시나리오 결과가 기준선과 같다

- **활성 시나리오**: `m.scenario("이름")`이 시나리오를 고릅니다. 다른 시나리오를 만든 뒤 `m.solve()`는 마지막에 고른 시나리오로 풉니다.
  `m.scenario()`(인자 없이)로 지금 활성인 것을 확인합니다.
- **기간**: override·충격이 풀이 구간 밖에만 있으면 차이가 없습니다.
- **모델에 안 쓰이는 변수**: 바꾼 변수가 모델의 어떤 식에도 없으면 아무 일도 없습니다 — 충격은 이 경우 오류로 알려 줍니다.

```python
m.scenario("check").shock("G", 10, "2015Q1")
print(m.scenario().name, m.scenario().alias)
```
<!-- out -->
```text
check _1
```

## T6. "'…'은(는) 이미 시리즈 이름입니다"

시리즈와 객체(방정식·모델·그래프 …)는 이름을 함께 쓰고, 대소문자를 가리지 않습니다 — 시리즈 `G`가 있으면 객체 이름 `g`도
안 됩니다. 객체 이름에 접두사를 붙이는 습관이 편합니다(`eq_i`, `m_toy`, `g_y`).

<!-- error -->
```python
wf.equation("i").ls("I c Y(-1) R")
```
<!-- out -->
```text
ValueError: 'i'은(는) 이미 시리즈 이름입니다(시리즈 I — 이름은 대소문자를 가리지 않고 시리즈·객체가 함께 씁니다. 객체 이름에 접두사를 붙이세요: 예 eq_i)
```

## T7. "시점 표기 오류"

시점은 워크파일의 주기로 씁니다: 분기 `2010Q1`, 월 `2010M3`(또는 `2010-03`), 연 `2010`. 다른 주기의 표기는 받지 않습니다.

<!-- error -->
```python
wf.smpl("2010M3", "2012M1")
```
<!-- out -->
```text
ValueError: 시점 표기 오류: '2010M3'은(는) 월(Monthly) 표기입니다 — 분기(Quarterly) 자료의 시점은 2000Q1 꼴입니다
```

## T8. 전망에서 "외생변수 값이 없습니다"

전망 기간의 외생변수 경로가 비었습니다. `exog_fill="last"|"growth"|"trend"`로 채우거나, 시나리오 `override`로 가정을 줍니다
([전망 레시피](forecast.md)). 시작 앞의 내생변수 실측이 비었다는 메시지면 실측이 끝난 바로 다음 기간부터 전망하거나 앞 전망 값을 채웁니다.

## T9. 결과가 컴퓨터마다 마지막 자리에서 다르다

선형대수 라이브러리(BLAS)·CPU에 따라 마지막 자리가 다를 수 있습니다(1e-12 수준). 결과 비교는 허용오차로 하고, 같은 컴퓨터에서
똑같이 재현하려면 명령줄의 `--threads 1`로 스레드 수를 고정합니다. [검증 보고서](../explain/validation.md).

## T10. 출력이 너무 많다(또는 적다)

`eqn.verbose(0)` 조용히 · `1` 요약 한 줄(기본) · `2` 엔진 상세. 명령줄은 `-q`·`-v`.

관련: [오류 메시지 참조](../reference/errors.md) · [레시피 목록](README.md)
