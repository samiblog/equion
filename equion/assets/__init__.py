"""내장 자료 — plotly.js(MIT, gzip으로 줄여 내장). 고지는 THIRD-PARTY-NOTICES.md."""
import gzip
import os

PLOTLY_JS_VERSION = "3.4.0"
_HERE = os.path.dirname(os.path.abspath(__file__))


def plotly_js() -> bytes:
    """내장한 plotly.min.js 내용."""
    with gzip.open(os.path.join(_HERE, f"plotly-{PLOTLY_JS_VERSION}.min.js.gz"), "rb") as f:
        return f.read()


def plotly_cdn() -> str:
    return f"https://cdn.plot.ly/plotly-{PLOTLY_JS_VERSION}.min.js"
