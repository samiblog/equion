# 설치
<!-- no-export -->

Equion은 Python 3.12 이상에서 돕니다. 필수 의존성은 numpy·pandas·scipy·openpyxl뿐이고, 회귀·검정은 패키지 안에서
직접 계산합니다(외부 통계 패키지 없음). 아직 PyPI에 올리지 않았으므로 저장소에서 설치합니다.

## 저장소에서 쓰기(권장 — 이 저장소의 개발 환경)

[uv](https://docs.astral.sh/uv/)가 저장소의 `uv.lock`에 적힌 정확한 판으로 환경을 만듭니다.

```bash
uv sync
```

```bash
uv run python -c "import equion as eqn; print(eqn.__version__)"
```

노트북은 `uv run jupyter lab`(개발 의존성에 커널이 들어 있다), 명령줄은 `uv run equion …`으로 씁니다.
선택 기능(옛 워크파일을 읽는 pyarrow, plotly 그림 객체)까지 빼고 코어만 쓰려면 `uv sync --no-dev`.

## 다른 환경에 설치

```bash
pip install "equion @ git+https://github.com/samiblog/equion"
```

```bash
pip install "equion[all] @ git+https://github.com/samiblog/equion"
```

받아 둔 저장소가 있으면 경로로도 됩니다(`pip install "/path/to/equion[all]"`).

`[parquet]`은 0.6.0 이전에 저장한 워크파일을 읽을 때, `[plot]`은 plotly `Figure` 객체가 필요할 때입니다.
그래프 html은 plotly 없이도 만들어집니다(그래프 그리는 스크립트를 패키지에 넣어 두었다). 그림 파일(png·svg)로 저장하려면
plotly와 kaleido가 필요합니다.

## 확인

```bash
equion info
```

판과 실행 환경(numpy·pandas·scipy 판, BLAS, 스레드)이 나오면 됩니다. Python에서는:

```python
import equion as eqn

print(eqn.__version__)
print(eqn.datasets.names())        # 문서 예제가 쓰는 예제 자료
```
<!-- out -->
```text
0.9.0
['klein_like', 'toy_a', 'toy_m', 'toy_q']
```

## 다음

[30분 첫 모델](first-model.md)로 바로 시작하거나, [튜토리얼](../tutorial/README.md)을 차례로 따라가세요.
수치가 마지막 자리에서 다를 수 있다는 점(BLAS·CPU 차이)은 [검증 보고서](../explain/validation.md)를 보세요.
