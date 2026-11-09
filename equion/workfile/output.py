#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""출력 수집기(스풀) — 표·그래프·글을 실행 환경에 맞게 보이고 모은다.

- 스크립트: 글자로 출력
- 노트북: HTML 표 / 그래프(plotly.js — plotly 파이썬 패키지는 선택)
- CLI(`equion run`): 글자로 보이면서 모아 보고서 폴더로(-q면 mode='collect': 모으기만)
- 데스크톱(P3): 모아서 객체 창으로

모든 출력 객체는 `.text()` / `.html()` / `.data` 를 가지고, `eqn.show(x)` 또는 `x.show()`로 보인다.
"""

import html as _html
import math
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# 말하기 수준
# ---------------------------------------------------------------------------
_VERBOSITY = {"level": 1}


def verbose(level: Optional[int] = None) -> int:
    """출력 수준: 0 조용히 · 1 요약 한 줄(기본) · 2 엔진 상세 로그까지. 인자 없이 부르면 현재 값.

    예
        >>> old = eqn.verbose()
        >>> eqn.verbose(0)
        0
        >>> eqn.verbose(old) == old
        True

    관련: log.use_own_handler(파이썬 logging 설정을 쓸 때)
    """
    if level is not None:
        _VERBOSITY["level"] = int(level)
    return _VERBOSITY["level"]


def say(msg: str):
    """워크파일 요약 한 줄 — 'equion.workfile' 로거(eqn.verbose(1) 이상에서)."""
    if _VERBOSITY["level"] >= 1:
        from ..log import workfile
        workfile.info(msg)


def in_notebook() -> bool:
    try:
        from IPython import get_ipython
        shell = get_ipython()
        return shell is not None and shell.__class__.__name__ == "ZMQInteractiveShell"
    except Exception:
        return False


# ---------------------------------------------------------------------------
# 출력 객체
# ---------------------------------------------------------------------------
def _fmt(v, digits=4):
    if v is None:
        return ""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    if math.isnan(f):
        return "NA"
    if f != 0 and (abs(f) >= 1e6 or abs(f) < 1e-3):
        return f"{f:.{digits}e}"
    return f"{f:,.{digits}f}"


class Output:
    kind = "output"

    def __init__(self, title: str = "", name: str = None):
        self.title = title
        self.name = name

    def text(self) -> str:
        raise NotImplementedError

    def html(self) -> str:
        return f"<pre>{_html.escape(self.text())}</pre>"

    def __str__(self):
        return self.text()

    def __repr__(self):
        return self.text()

    def _repr_html_(self):
        return self.html()

    def show(self):
        spool.show(self)
        return None


class TextOutput(Output):
    kind = "text"

    def __init__(self, body: str, title: str = "", name: str = None):
        super().__init__(title, name)
        self.body = body

    @property
    def data(self):
        return self.body

    def text(self):
        return (f"{self.title}\n" if self.title else "") + self.body

    def md(self) -> str:
        """md(작업 기록 카드·노트·보고서용) — 글은 코드 블록으로."""
        from ..reporting.markdown import output_md
        return output_md(self)


class TableOutput(Output):
    """제목·머리 줄·표·꼬리 줄로 된 출력 (방정식 결과표, 블록 구조, 객체 목록 등)."""
    kind = "table"

    def __init__(self, df: pd.DataFrame, title: str = "", head: List[str] = None,
                 foot: List[str] = None, name: str = None, digits: int = 4, index: bool = True):
        super().__init__(title, name)
        self.df = df
        self.head = head or []
        self.foot = foot or []
        self.digits = digits
        self.index = index

    @property
    def data(self) -> pd.DataFrame:
        """표의 DataFrame."""
        return self.df

    def _formatted(self) -> pd.DataFrame:
        out = self.df.copy()
        for c in out.columns:
            if pd.api.types.is_float_dtype(out[c]):
                out[c] = out[c].map(lambda v: _fmt(v, self.digits))
        return out

    def text(self) -> str:
        """글자 표(머리말·꼬리 줄 포함 — 스크립트·로그용)."""
        body = self._formatted().to_string(index=self.index) if len(self.df) else "(없음)"
        width = max([len(line) for line in body.splitlines()] + [len(h) for h in self.head] + [40])
        rule = "─" * min(width, 110)
        lines = []
        if self.title:
            lines.append(self.title)
        lines += self.head
        lines += [rule, body, rule]
        lines += self.foot
        return "\n".join(lines)

    def md(self) -> str:
        """md 표(작업 기록 카드·노트·보고서용) — 제목은 굵게, 머리·꼬리 줄은 문단.

        예
            >>> wf = eqn.datasets.load("toy_q")
            >>> print(wf.equation("eq_i").ls("I c Y(-1) R").output().md().splitlines()[0])
            **방정식 eq_i**
        """
        from ..reporting.markdown import output_md
        return output_md(self)

    def html(self) -> str:
        """HTML 표(노트북·보고서용)."""
        parts = ['<div class="eqn-out" style="font-family:system-ui,sans-serif;font-size:13px">']
        if self.title:
            parts.append(f"<div style='font-weight:700;margin:4px 0'>{_html.escape(self.title)}</div>")
        for h in self.head:
            parts.append(f"<div style='color:#555'>{_html.escape(h)}</div>")
        parts.append(self._formatted().to_html(index=self.index, border=0, escape=True,
                                               classes="eqn-table"))
        for f in self.foot:
            parts.append(f"<div style='color:#555'>{_html.escape(f)}</div>")
        parts.append("</div>")
        return "".join(parts)


# plotly_white 서식과 기본 색 — plotly 패키지 없이도 같은 모양으로 그린다(plotly.js만 있으면 됨).
_COLORWAY = ["#636efa", "#EF553B", "#00cc96", "#ab63fa", "#FFA15A",
             "#19d3f3", "#FF6692", "#B6E880", "#FF97FF", "#FECB52"]
_AXIS = {"gridcolor": "#EBF0F8", "linecolor": "#EBF0F8", "zerolinecolor": "#EBF0F8",
         "zerolinewidth": 2, "automargin": True, "ticks": ""}


def _json_for_script(obj) -> str:
    """<script> 안에 넣어도 안전한 JSON(제목 등의 '</script>'·'<!--'가 태그를 끝내지 못하게)."""
    import json
    return (json.dumps(obj, ensure_ascii=False, allow_nan=False)
            .replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
            .replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))


def _js_tag(include_js) -> str:
    """include_js: 'cdn'(기본) · 'inline'(내장 plotly.js를 파일에 넣음) · 그 밖의 문자열은 스크립트 주소 · None/False는 넣지 않음."""
    if not include_js:
        return ""
    from ..assets import plotly_cdn, plotly_js
    if include_js == "inline":
        return "<script>" + plotly_js().decode("utf-8") + "</script>"
    src = plotly_cdn() if include_js == "cdn" else str(include_js)
    return f"<script charset='utf-8' src='{_html.escape(src, quote=True)}'></script>"


class GraphOutput(Output):
    """그래프. 그림 정의(spec)를 직접 만들어 plotly.js로 그린다 — plotly 파이썬 패키지는 선택(`figure()`·이미지 저장).
    kind: 'line' · 'bar'(나란히) · 'stacked'(쌓은 막대 — 기여도). 노트북에서는 그래프로, 글자 환경에서는 요약 한 줄로."""
    kind = "graph"

    def __init__(self, data: pd.DataFrame, title: str = "", kind: str = "line",
                 name: str = None, labels: Dict[str, str] = None):
        super().__init__(title, name)
        self.frame = data
        self.chart = kind
        self.labels = labels or {}

    @property
    def data(self) -> pd.DataFrame:
        """그림의 자료(DataFrame)."""
        return self.frame

    def spec(self) -> dict:
        """plotly.js 그림 정의 {"data": [...], "layout": {...}} — JSON으로 바로 쓸 수 있는 순수 dict(결측은 None)."""
        x = [str(i.date()) if hasattr(i, "date") else str(i) for i in self.frame.index]
        traces = []
        for col in self.frame.columns:
            y = [float(v) if np.isfinite(v) else None for v in self.frame[col].to_numpy(dtype=float)]
            t = {"type": "bar" if self.chart in ("bar", "stacked") else "scatter", "x": x, "y": y,
                 "name": str(self.labels.get(col, col))}
            if t["type"] == "scatter":
                t["mode"] = "lines"
            traces.append(t)
        layout = {"title": {"text": str(self.title or self.name or ""), "x": 0.05},
                  "margin": {"l": 40, "r": 20, "t": 50, "b": 40}, "legend": {"orientation": "h"},
                  "paper_bgcolor": "white", "plot_bgcolor": "white", "colorway": list(_COLORWAY),
                  "font": {"color": "#2a3f5f"}, "hovermode": "closest",
                  "xaxis": dict(_AXIS), "yaxis": dict(_AXIS)}
        if self.chart == "stacked":                     # 기여도: 양수는 위로, 음수는 아래로 쌓는다
            layout["barmode"] = "relative"
        return {"data": traces, "layout": layout}

    def figure(self):
        """plotly Figure(plotly 패키지가 있을 때: pip install 'equion[plot]')."""
        try:
            import plotly.graph_objects as go
        except ImportError as e:
            raise ImportError("figure()에는 plotly가 필요합니다: pip install plotly (선택 기능 equion[plot]) "
                              "(그리기·html·save('.html')는 plotly 없이 됩니다)") from e
        sp = self.spec()
        fig = go.Figure(data=sp["data"], layout=sp["layout"])
        fig.update_layout(template="plotly_white")
        return fig

    def text(self) -> str:
        """글로 된 요약(스크립트·로그용)."""
        idx = self.frame.index
        span = f"{idx[0]:%Y-%m}~{idx[-1]:%Y-%m}" if len(idx) and hasattr(idx[0], "strftime") else ""
        return (f"[그래프] {self.title or self.name or ''} — {', '.join(map(str, self.frame.columns))}"
                f" {span} ({len(idx)}기)")

    def html(self, include_js="cdn", height: str = "420px") -> str:
        """그래프 조각(div + 그리기 스크립트). include_js는 `_js_tag` 참조 — 페이지가 이미 plotly.js를 부르면 None."""
        import uuid
        div = f"eqn-{uuid.uuid4().hex[:12]}"
        sp = self.spec()
        return (_js_tag(include_js)
                + f"<div id='{div}' class='eqn-graph' style='height:{_html.escape(height, quote=True)};width:100%'></div>"
                + f"<script>Plotly.newPlot('{div}', {_json_for_script(sp['data'])}, "
                  f"{_json_for_script(sp['layout'])}, {{\"responsive\": true}});</script>")

    def page(self, include_js="cdn") -> str:
        """그래프 하나짜리 HTML 문서."""
        title = _html.escape(str(self.title or self.name or "graph"))
        return (f"<!doctype html><html><head><meta charset='utf-8'><title>{title}</title>{_js_tag(include_js)}"
                f"</head><body style='margin:0'>{self.html(include_js=None, height='100vh')}</body></html>")

    def _repr_mimebundle_(self, include=None, exclude=None):
        try:
            return self.figure()._repr_mimebundle_(include, exclude)
        except ImportError:
            return {"text/html": self.html(), "text/plain": self.text()}

    def save(self, path: str, include_js="cdn") -> str:
        """.html — plotly 없이(include_js='inline'이면 인터넷 없이 열림). png·svg·pdf — plotly와 kaleido가 필요."""
        import os
        ext = os.path.splitext(path)[1].lower()
        if ext not in (".html", ".htm", ".png", ".svg", ".pdf", ".jpg", ".jpeg", ".webp"):
            raise ValueError(f"그래프는 .html(또는 plotly·kaleido가 있으면 .png·.svg·.pdf)로 저장합니다(받은 것: {ext or '확장자 없음'})")
        if os.path.dirname(path):
            os.makedirs(os.path.dirname(path), exist_ok=True)
        if ext in (".html", ".htm"):
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.page(include_js))
        else:
            self.figure().write_image(path)
        from .runtime import record_output
        record_output(path, "graph")
        return path


# ---------------------------------------------------------------------------
# 스풀
# ---------------------------------------------------------------------------
class Spool:
    """보인 출력을 모은다. mode: 'auto'(바로 보임) · 'collect'(모으기만, CLI/앱) · 'silent'."""

    def __init__(self):
        self.items: List[Output] = []
        self.mode = "auto"

    def show(self, out: Output):
        self.items.append(out)
        if self.mode != "auto":
            return
        if in_notebook():
            from IPython.display import display
            display(out)
        else:
            print(out.text())

    def clear(self):
        self.items.clear()


spool = Spool()


def as_output(obj: Any) -> Output:
    if isinstance(obj, Output):
        return obj
    if hasattr(obj, "output") and callable(obj.output):
        return obj.output()
    if isinstance(obj, pd.DataFrame):
        return TableOutput(obj)
    if isinstance(obj, pd.Series):
        return TableOutput(obj.to_frame())
    return TextOutput(str(obj))


def show(*objs):
    """출력 객체·워크파일 객체·DataFrame을 실행 환경에 맞게 보이고 스풀에 남긴다."""
    for obj in objs:
        spool.show(as_output(obj))
