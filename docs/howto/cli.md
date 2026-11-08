# 레시피: 명령줄

명령줄은 터미널에서 씁니다. 이 문서의 예는 출력을 함께 보이려고 Python에서 같은 명령을 부릅니다(`equion(…)` = 터미널의 `equion …`).

```python
import json
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd


def equion(*args):
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable, "-m", "equion", *args], capture_output=True, text=True, encoding="utf-8", env=env)
    print((r.stdout + r.stderr).rstrip())
    return r.returncode


Path("forecast.py").write_text('''import equion as eqn
p = eqn.params(g_up=0.0)
wf = eqn.datasets.load("toy_q")
m = wf.model("toy").merge("I c Y(-1) R", "CN c Y CN(-1)").append("Y = CN + I + G")
m.scenario("s").shock("G", p.g_up, "2015Q1", "2019Q4", kind="pct")
m.solve("2015Q1", "2019Q4")
eqn.show(wf.table("result", wf.to_pandas(["Y_1"], labels=True).loc["2019Q1":"2019Q4"]))
''', encoding="utf-8")
```
<!-- out -->
```text
```

## R44. 매개변수를 바꿔 가며 여러 번

```python
for g in (0, 5, 10):
    equion("run", "forecast.py", "--set", f"g_up={g}", "--run-id", f"g{g}", "--format", "csv", "-q")
```
<!-- out -->
```text
[equion] 성공 · 0.0초 · 풀이 1회(정상 20 · 일부식 제외 0 · 실패대체 0 · 실패 0) · 보고서 out/g0/manifest.json · 종료 코드 0
[equion] 성공 · 0.1초 · 풀이 1회(정상 20 · 일부식 제외 0 · 실패대체 0 · 실패 0) · 보고서 out/g5/manifest.json · 종료 코드 0
[equion] 성공 · 0.0초 · 풀이 1회(정상 20 · 일부식 제외 0 · 실패대체 0 · 실패 0) · 보고서 out/g10/manifest.json · 종료 코드 0
```

터미널이라면 `for g in 0 5 10; do equion run forecast.py --set g_up=$g --run-id g$g -q; done`.

## R45. 보고서에서 결과 숫자 꺼내기

```python
rows = {}
for g in (0, 5, 10):
    d = Path("out") / f"g{g}"
    man = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
    table = sorted((d / "tables").glob("*result*.csv"))[0]
    rows[man["params"]["resolved"]["g_up"]] = float(pd.read_csv(table, index_col=0).iloc[-1, 0])
print({k: round(v, 1) for k, v in rows.items()})
```
<!-- out -->
```text
{0.0: 624.4, 5.0: 649.8, 10.0: 675.1}
```

## R46. 정해진 시각에 자동 실행

<!-- skip -->
```bash
# Linux·macOS crontab: 매주 월요일 7시
0 7 * * 1  cd /path/to/project && equion run scripts/main.py --fail-on fallback -q >> run.log 2>&1
```

Windows는 작업 스케줄러에서 `equion run scripts\main.py -q`를 프로젝트 폴더에서 실행하도록 등록합니다.
종료 코드(0 성공 · 1 스크립트 오류 · 2 풀이 실패 · 3 입력 오류)로 결과를 판단합니다.

## R47. CI에서 모델 검사

<!-- skip -->
```bash
equion check EQUATIONS/model.txt --data DATA/data.csv --strict --json > check.json
equion run scripts/main.py --fail-on partial --no-report -q
```

`--strict`는 경고도 실패(3)로 봅니다. `--json`은 결과를 기계가 읽는 꼴로 줍니다.

관련: [튜토리얼 8](../tutorial/08-cli.md) · [명령줄 참조](../reference/cli.md)
