# 튜토리얼

차례로 따라가면 Equion의 거의 모든 기능을 한 번씩 써 보게 됩니다. 모든 튜토리얼은 패키지에 든 예제 자료
(`eqn.datasets` — [설명](../reference/datasets.md))를 쓰므로 어디서든 바로 돌고, 문서의 출력은 실제 실행 결과입니다.
각 튜토리얼은 처음부터 혼자 돌 수 있게 썼습니다(앞 튜토리얼을 먼저 실행하지 않아도 된다).

| | 튜토리얼 | 스크립트 · 노트북 |
|---|---|---|
| 1 | [자료 다루기](01-data.md) | [01-data.py](../../examples/tutorial/01-data.py) · [ipynb](../../examples/notebooks/01-data.ipynb) |
| 2 | [방정식 추정](02-estimation.md) | [02-estimation.py](../../examples/tutorial/02-estimation.py) · [ipynb](../../examples/notebooks/02-estimation.ipynb) |
| 3 | [진단 검정](03-diagnostics.md) | [03-diagnostics.py](../../examples/tutorial/03-diagnostics.py) · [ipynb](../../examples/notebooks/03-diagnostics.ipynb) |
| 4 | [연립 모델](04-model.md) | [04-model.py](../../examples/tutorial/04-model.py) · [ipynb](../../examples/notebooks/04-model.ipynb) |
| 5 | [시나리오](05-scenario.md) | [05-scenario.py](../../examples/tutorial/05-scenario.py) · [ipynb](../../examples/notebooks/05-scenario.ipynb) |
| 6 | [전망](06-forecast.md) | [06-forecast.py](../../examples/tutorial/06-forecast.py) · [ipynb](../../examples/notebooks/06-forecast.ipynb) |
| 7 | [시스템·VAR·VECM](07-systems.md) | [07-systems.py](../../examples/tutorial/07-systems.py) · [ipynb](../../examples/notebooks/07-systems.ipynb) |
| 8 | [명령줄](08-cli.md) | [08-cli.py](../../examples/tutorial/08-cli.py) · [ipynb](../../examples/notebooks/08-cli.ipynb) |

처음이라면 [30분 첫 모델](../start/first-model.md)을 먼저 보세요. 특정 작업만 찾는다면 [레시피](../howto/README.md)가 빠릅니다.

## 이 문서에서 쓰는 말

| 말 | 뜻 |
|---|---|
| 워크파일 | 시리즈(시계열)·표본·객체(방정식·모델·그래프·표)를 담는 작업 단위 — `eqn.wfopen`·`eqn.wfcreate` |
| 시리즈 | 이름 붙은 시계열 하나. 이름은 대소문자를 가리지 않는다 |
| 표본(smpl) | 추정·풀이·genr·그래프가 기본으로 쓰는 기간 |
| 추정식 · 항등식 | 계수를 추정하는 식(`I c Y(-1) R`) · 계수 없이 늘 성립하는 식(`Y = CN + I + G`) |
| 내생 · 외생 | 모델이 푸는 변수(각 식의 목표변수) · 모델 밖에서 주어지는 변수 |
| 기준선 · 시나리오 · 별칭 | 가정을 바꾸지 않은 풀이(`_0`) · 가정을 바꾼 풀이(`_1` …) · 결과 시리즈 이름 끝의 `_0`·`_1` |
| 과거 재현(HS) | 실제 과거 기간을 모델로 다시 풀어 보는 것(Historical Simulation) |
| 동적 · 정적 풀이 | 시차에 지난 풀이 값을 쓴다 · 시차에 실측을 쓴다 |
