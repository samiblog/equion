#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""예제 자료 — 문서·튜토리얼·레시피가 함께 쓰는 작은 가상 자료(패키지에 들어 있어 어디서나 바로 연다).

    import equion as eqn
    wf = eqn.datasets.load("toy_q")        # 분기 거시 모형 자료 → 워크파일(설명·단위 메타데이터 포함)
    eqn.datasets.names()                   # ['klein_like', 'toy_a', 'toy_m', 'toy_q']
    print(eqn.datasets.describe("toy_q"))  # 만든 참 모형과 변수 설명

모든 자료는 알려진 '참 모형'에서 난수로 만든 가상 자료다(실제 경제 자료가 아니다) — 추정 결과를 참값과 견줄 수 있다.
만드는 코드는 `equion/datasets/_make.py`(고정 시드), 설명은 docs/reference/datasets.md.

실제 Klein 모형 I 자료(1920~1941)는 이용 조건이 분명하지 않아 넣지 않았다 — 직접 구한 파일을 `klein(path)`로 연다.
"""

import os
from typing import Dict, List

HERE = os.path.dirname(os.path.abspath(__file__))

_INFO: Dict[str, dict] = {
    "toy_q": {
        "title": "작은 거시 모형 — 분기(1970Q1~2019Q4, 200기)",
        "model": [
            "I  = 5 + 0.15·Y(-1) − 1.0·R + e₂                         (투자)",
            "CN = 10 + 0.5·Y + 0.3·CN(-1) + e₁                         (소비 — Y가 내생이라 OLS는 치우친다)",
            "Y  = CN + I + G                                            (국민소득 항등식)",
            "dlog(P) = 0.005 + 0.3·dlog(Y) + 0.02·dlog(POIL) + e₃      (물가)",
            "RL = 1 + R + u,  u = 0.7·u(-1) + ε                        (장기금리 — R과 공적분, 1980Q1부터)",
            "log(M2) = −2 + log(P) + 0.8·log(Y) − 0.03·RL + v,  v = 0.8·v(-1) + ε  (통화 — 공적분)",
            "CNNSA = CN × 계절 요인(1.03·0.98·1.01·0.98) × 잡음        (계절조정 전 소비)",
        ],
        "series": {
            "CN": ("소비", "조원(가상)", "sum"), "I": ("투자", "조원(가상)", "sum"),
            "G": ("정부지출(외생)", "조원(가상)", "sum"), "Y": ("국민소득 = CN + I + G", "조원(가상)", "sum"),
            "R": ("정책금리(외생)", "%", "mean"), "RL": ("장기금리(1980Q1부터)", "%", "mean"),
            "P": ("물가 지수", "지수", "mean"), "POIL": ("유가 지수(외생)", "지수", "mean"),
            "M2": ("통화량", "조원(가상)", "mean"), "CNNSA": ("소비(계절조정 전)", "조원(가상)", "sum"),
        },
    },
    "toy_a": {
        "title": "작은 거시 모형 — 연간(1970~2019, 50년). toy_q를 연간으로(흐름은 합, 금리·지수는 평균)",
        "model": ["toy_q와 같은 경제를 연간으로 본 자료 — 연간 식은 분기 식의 근사다"],
        "series": {
            "CN": ("소비", "조원(가상)", "sum"), "I": ("투자", "조원(가상)", "sum"),
            "G": ("정부지출(외생)", "조원(가상)", "sum"), "Y": ("국민소득 = CN + I + G", "조원(가상)", "sum"),
            "R": ("정책금리(외생)", "%", "mean"), "RL": ("장기금리(1980년부터)", "%", "mean"),
            "P": ("물가 지수", "지수", "mean"), "POIL": ("유가 지수(외생)", "지수", "mean"),
            "M2": ("통화량(연평균)", "조원(가상)", "mean"),
        },
    },
    "toy_m": {
        "title": "같은 경제의 월간 지표(2000M1~2019M12, 240개월)",
        "model": [
            "IP   = toy_q Y의 월간 경로 × 월별 계절 요인 × 잡음  (산업생산, 계절조정 전, 2000년 평균 = 100)",
            "CPIM = toy_q P의 월간 경로 × 약한 계절 요인 × 잡음  (소비자물가, 계절조정 전, 2000년 평균 = 100)",
            "RM   = toy_q R + 잡음                              (월평균 정책금리)",
        ],
        "series": {
            "IP": ("산업생산(계절조정 전)", "지수(2000 = 100)", "mean"),
            "CPIM": ("소비자물가(계절조정 전)", "지수(2000 = 100)", "mean"),
            "RM": ("월평균 정책금리", "%", "mean"),
        },
    },
    "klein_like": {
        "title": "Klein 모형 I의 구조로 만든 가상 자료 — 연간(1921~1990, 70년). 실제 Klein 자료가 아니다",
        "model": [
            "CONS = 16.4 + 0.125·PR + 0.163·PR(-1) + 0.79·(WP + WG) + e₁   (소비)",
            "I    = 28.2 − 0.013·PR + 0.756·PR(-1) − 0.195·K(-1) + e₂       (투자)",
            "WP   = 1.8 + 0.4·X + 0.181·X(-1) + 0.15·A + e₃                (민간 임금)",
            "X = CONS + I + G,  PR = X − T − WP,  K = K(-1) + I          (항등식)",
        ],
        "series": {
            "CONS": ("소비(Klein의 C — 이름 C는 상수항이라 CONS)", "가상", "sum"), "I": ("순투자", "가상", "sum"),
            "WP": ("민간 임금", "가상", "sum"), "X": ("총수요 = CONS + I + G", "가상", "sum"),
            "PR": ("이윤 = X − T − WP", "가상", "sum"), "K": ("자본스톡(연말) = K(-1) + I", "가상", "last"),
            "G": ("정부지출(외생)", "가상", "sum"), "T": ("세금(외생)", "가상", "sum"),
            "WG": ("정부 임금(외생)", "가상", "sum"), "A": ("추세 = 연도 − 1931(외생)", "년", "last"),
        },
    },
}


def names() -> List[str]:
    """들어 있는 예제 자료 이름.

    예
        >>> eqn.datasets.names()
        ['klein_like', 'toy_a', 'toy_m', 'toy_q']
    """
    return sorted(_INFO)


def path(name: str) -> str:
    """예제 자료 CSV 파일의 경로 — 파일로 직접 열거나 내용을 볼 때.

    예
        >>> p = eqn.datasets.path("toy_q")
        >>> p.endswith("toy_q.csv")
        True
        >>> eqn.wfopen(p).freq
        'Q'

    오류
        KeyError: 없는 이름
    """
    if name not in _INFO:
        raise KeyError(f"예제 자료 '{name}'이(가) 없습니다 — {names()}")
    return os.path.join(HERE, f"{name}.csv")


def describe(name: str) -> str:
    """예제 자료의 참 모형과 변수 설명(글).

    예
        >>> text = eqn.datasets.describe("toy_q")
        >>> print(text.splitlines()[0])
        작은 거시 모형 — 분기(1970Q1~2019Q4, 200기)
        >>> "Y  = CN + I + G" in text
        True
    """
    path(name)                     # 없는 이름이면 KeyError
    info = _INFO[name]
    lines = [info["title"], "", "참 모형:"] + [f"  {m}" for m in info["model"]] + ["", "변수:"]
    lines += [f"  {k:<6} {d} [{u}]" for k, (d, u, _) in info["series"].items()]
    return "\n".join(lines)


def load(name: str = "toy_q"):
    """예제 자료를 워크파일로 연다(시리즈 설명·단위·집계 방식 메타데이터 포함).

    매개변수
        name: 'toy_q'(분기 거시 모형) · 'toy_a'(같은 경제의 연간) · 'toy_m'(월간 지표) · 'klein_like'(Klein 구조 가상 자료)
    돌려주는 것
        Workfile — 이름은 자료 이름.
    예
        >>> wf = eqn.datasets.load("toy_q")
        >>> wf.freq, wf.smpl()
        ('Q', ('1970Q1', '2019Q4'))
    """
    from ..workfile.runtime import quiet
    from ..workfile.workfile import wfopen
    wf = wfopen(path(name), name=name)
    for col, (desc, unit, agg) in _INFO[name]["series"].items():
        quiet(wf.meta, col, desc=desc, unit=unit, agg=agg, source="Equion 예제 자료(가상)")
    return wf


# 실제 Klein 모형 I 자료의 열 이름 → Equion 이름(C는 상수항이라 CONS, P는 이윤 PR)
_KLEIN_COLUMNS = {
    "c": "CONS", "cons": "CONS", "consumption": "CONS",
    "p": "PR", "profit": "PR", "profits": "PR", "corpprof": "PR",
    "wp": "WP", "privwage": "WP", "pwage": "WP", "privatewages": "WP",
    "i": "I", "inv": "I", "invest": "I", "investment": "I",
    "k1": "K1", "k": "K1", "lcap": "K1", "capital": "K1", "capitallag": "K1",
    "x": "X", "gnp": "X", "output": "X",
    "wg": "WG", "pubwage": "WG", "gwage": "WG", "govtwages": "WG",
    "g": "G", "govspend": "G", "gexp": "G",
    "t": "T", "tax": "T", "taxe": "T", "taxes": "T",
}


def klein(file_path: str):
    """직접 구한 실제 Klein 모형 I 자료(1920~1941, Klein 1950 · Greene 『Econometric Analysis』 부록 표 등)를 연다.

    열 이름을 Equion 이름으로 바꾼다: C → CONS(이름 C는 상수항), P → PR, Wp → WP, I, K1(전년 말 자본), X, Wg → WG, G, T.
    추세 A = 연도 − 1931을 더한다. 첫 열은 연도여야 한다. 이 자료는 이용 조건이 분명하지 않아 패키지에 넣지 않았다.

    예
        >>> wf = eqn.datasets.klein("TableF10-3.csv")          # doctest: +SKIP
    """
    import numpy as np
    import pandas as pd
    from ..workfile.runtime import quiet
    from ..workfile.workfile import _from_frame
    from ..data.io import read_dataframe
    from ..data.periods import regularize

    df = read_dataframe(file_path)
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError(f"첫 열이 연도여야 합니다: {file_path}")
    ren, unknown = {}, []
    for c in df.columns:
        key = "".join(ch for ch in str(c).lower() if ch.isalnum())
        if key in _KLEIN_COLUMNS:
            ren[c] = _KLEIN_COLUMNS[key]
        elif key not in ("year", "a"):
            unknown.append(str(c))
    df = df.rename(columns=ren)
    df = df[[c for c in df.columns if c in set(_KLEIN_COLUMNS.values())]]
    need = {"CONS", "PR", "WP", "I", "X", "WG", "G", "T"}
    if not need <= set(df.columns):
        raise ValueError(f"Klein 자료의 열이 모자랍니다: {sorted(need - set(df.columns))} (읽은 열: {list(ren)})")
    df = regularize(df.astype(float), "A")
    df["A"] = np.asarray(df.index.year, dtype=float) - 1931.0
    if "K1" in df.columns:          # 전년 말 자본 K1 = K(-1) → 자본스톡 K = K1 + I
        df["K"] = df["K1"] + df["I"]
    return quiet(_from_frame, df, "A", "klein", check=True)


__all__ = ["names", "path", "describe", "load", "klein"]
