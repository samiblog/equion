#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""예제 자료 만들기 — `python -m equion.datasets._make`(같은 시드면 언제나 같은 CSV).

모든 자료는 아래에 적은 '참 모형'에서 난수로 만든 가상 자료다(실제 경제 자료가 아니다). 참 계수를 알고 있으므로
추정 결과를 참값과 견주며 배울 수 있다. 모형 설명은 docs/reference/datasets.md와 같다.

toy_q (분기, 1970Q1~2019Q4) — 작은 거시 모형
    I  = 5 + 0.15·Y(-1) − 1.0·R + e₂                       투자
    CN = 10 + 0.5·Y + 0.3·CN(-1) + e₁                       소비
    Y  = CN + I + G                                          국민소득(항등식)
    dlog(P) = 0.005 + 0.3·dlog(Y) + 0.02·dlog(POIL) + e₃    물가
    RL = 1 + R + u,  u = 0.7·u(-1) + ε                      장기금리(R과 공적분, 1980Q1부터)
    log(M2) = −2 + log(P) + 0.8·log(Y) − 0.03·RL + v,  v = 0.8·v(-1) + ε   통화(공적분)
    CNNSA = CN · 계절 요인(1.03·0.98·1.01·0.98) · 잡음        계절조정 전 소비
    외생: G(정부지출), R(정책금리 %), POIL(유가 지수)
toy_a (연간, 1970~2019) — toy_q를 연간으로(흐름은 합, 금리·물가는 평균, 지수는 평균)
toy_m (월간, 2000M1~2019M12) — 같은 경제의 월간 지표
    IP   산업생산(계절조정 전): Y의 월간 경로 × 월별 계절 요인 × 잡음(2000년 평균 = 100)
    CPIM 소비자물가(계절조정 전, 약한 계절성, 2000년 평균 = 100), RM 월평균 정책금리
klein_like (연간, 1921~1990) — Klein 모형 I의 구조로 만든 가상 자료(실제 Klein 자료가 아니다)
    CONS = 16.4 + 0.125·PR + 0.163·PR(-1) + 0.79·(WP + WG) + e₁
    I    = 28.2 − 0.013·PR + 0.756·PR(-1) − 0.195·K(-1) + e₂
    WP   = 1.8 + 0.4·X + 0.181·X(-1) + 0.15·A + e₃     (A = 연도 − 1931)
    X = CONS + I + G,  PR = X − T − WP,  K = K(-1) + I
    외생: G(정부지출), T(세금), WG(정부 임금), A(추세)
"""

import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))


def _labels(start_year, n, per):
    if per == 4:
        return [f"{start_year + k // 4}Q{k % 4 + 1}" for k in range(n)]
    if per == 12:
        return [f"{start_year + k // 12}M{k % 12 + 1}" for k in range(n)]
    return [f"{start_year + k}" for k in range(n)]


def make_toy_q(seed=20261030):
    rng = np.random.default_rng(seed)
    T = 240                                            # 1960Q1~2019Q4을 만들고 앞 10년(초기값 영향)은 버린다
    t = np.arange(T)
    G = 20 + 0.2 * t + 1.5 * np.sin(t / 7) + rng.normal(scale=0.8, size=T)
    R = np.empty(T)
    R[0] = 5.0
    for k in range(1, T):                              # 평균회귀하는 정책금리, 1990년대 이후 낮아짐
        target = 6.0 if k < 140 else 3.0
        R[k] = R[k - 1] + 0.08 * (target - R[k - 1]) + rng.normal(scale=0.25)
    POIL = 100 * np.exp(np.cumsum(rng.normal(0.004, 0.06, size=T)))
    CN, I, Y, P = (np.zeros(T) for _ in range(4))
    I[0] = 45.0
    CN[0] = 140.0
    Y[0] = CN[0] + I[0] + G[0]
    P[0] = 40.0
    for k in range(1, T):
        e1, e2, e3 = rng.normal(scale=[0.6, 0.6, 0.003])
        I[k] = 5 + 0.15 * Y[k - 1] - 1.0 * R[k] + e2
        Y[k] = (10 + 0.3 * CN[k - 1] + e1 + I[k] + G[k]) / 0.5
        CN[k] = Y[k] - I[k] - G[k]
        P[k] = P[k - 1] * np.exp(0.005 + 0.3 * np.log(Y[k] / Y[k - 1]) + 0.02 * np.log(POIL[k] / POIL[k - 1]) + e3)
    u = np.zeros(T)
    v = np.zeros(T)
    for k in range(1, T):
        u[k] = 0.7 * u[k - 1] + rng.normal(scale=0.2)
        v[k] = 0.8 * v[k - 1] + rng.normal(scale=0.01)
    RL = 1 + R + u
    RL[:80] = np.nan                                   # 장기금리는 1980Q1부터
    M2 = np.exp(-2.0 + np.log(P) + 0.8 * np.log(Y) - 0.03 * np.nan_to_num(1 + R + u) + v)
    seas = np.tile([1.03, 0.98, 1.01, 0.98], T // 4)
    CNNSA = CN * seas * np.exp(rng.normal(scale=0.003, size=T))
    df = pd.DataFrame({"CN": CN, "I": I, "G": G, "Y": Y, "R": R, "RL": RL, "P": P, "POIL": POIL, "M2": M2,
                       "CNNSA": CNNSA}, index=pd.Index(_labels(1960, T, 4), name="period"))
    return df.iloc[40:]


def make_toy_a(q: pd.DataFrame):
    years = [lab[:4] for lab in q.index]
    g = q.groupby(years)
    out = pd.DataFrame(index=pd.Index(sorted(set(years)), name="period"))
    for c in ("CN", "I", "G", "Y", "CNNSA"):
        out[c] = g[c].sum(min_count=4)
    for c in ("R", "RL", "P", "POIL", "M2"):
        out[c] = g[c].mean()
    out["RL"] = g["RL"].apply(lambda s: s.mean() if s.notna().all() else np.nan)
    return out.drop(columns=["CNNSA"])


def make_toy_m(q: pd.DataFrame, seed=20261031):
    rng = np.random.default_rng(seed)
    qq = q.loc["2000Q1":"2019Q4"]
    n = len(qq) * 3
    ly = np.log(qq["Y"].to_numpy())
    lm = np.interp(np.arange(n) / 3.0, np.arange(len(ly)), ly)
    lm = lm + np.cumsum(rng.normal(scale=0.004, size=n)) * 0.3
    seas = np.tile([0.94, 0.96, 1.05, 1.00, 1.02, 1.01, 0.97, 0.95, 1.03, 1.04, 1.01, 1.02], n // 12)
    ip = np.exp(lm - lm[0]) * seas * np.exp(rng.normal(scale=0.008, size=n))
    IP = 100 * ip / ip[:12].mean()
    lp = np.interp(np.arange(n) / 3.0, np.arange(len(qq)), np.log(qq["P"].to_numpy()))
    cp = np.exp(lp - lp[0]) * np.tile([0.998, 0.999, 1.001, 1.0, 1.0, 1.0, 1.002, 1.002, 1.0, 0.999, 0.999, 1.0], n // 12) \
        * np.exp(rng.normal(scale=0.0015, size=n))
    CPIM = 100 * cp / cp[:12].mean()
    RM = np.repeat(qq["R"].to_numpy(), 3) + rng.normal(scale=0.05, size=n)
    return pd.DataFrame({"IP": IP, "CPIM": CPIM, "RM": RM}, index=pd.Index(_labels(2000, n, 12), name="period"))


def make_klein_like(seed=19500101):
    rng = np.random.default_rng(seed)
    years = np.arange(1911, 1991)                      # 앞 10년(초기값 영향)은 버린다
    T = len(years)
    A = years - 1931.0
    G = 4 + 0.12 * (years - 1921) + 2.0 * np.sin((years - 1911) / 3.0) + rng.normal(scale=1.5, size=T)   # 경기 순환을 넣어
    TX = 3.5 + 0.09 * (years - 1921) + 1.2 * np.cos((years - 1911) / 4.0) + rng.normal(scale=1.0, size=T)  # 식별을 돕는다
    WG = np.maximum(2 + 0.08 * (years - 1921) + rng.normal(scale=0.5, size=T), 0.5)
    a = (16.4, 0.125, 0.163, 0.79)
    b = (28.2, -0.013, 0.756, -0.195)
    c = (1.8, 0.4, 0.181, 0.15)
    CONS, I, WP, X, PR, K = (np.zeros(T) for _ in range(6))
    X0, PR0, K0 = 60.0, 12.0, 180.0
    for k in range(T):
        e1, e2, e3 = rng.normal(scale=[1.0, 1.0, 0.8])
        Xl = X[k - 1] if k else X0
        Pl = PR[k - 1] if k else PR0
        Kl = K[k - 1] if k else K0
        # 동시 체계를 선형으로 푼다: 미지수 [CONS, I, WP, X, PR]
        M_ = np.array([[1, 0, -a[3], 0, -a[1]],
                       [0, 1, 0, 0, -b[1]],
                       [0, 0, 1, -c[1], 0],
                       [-1, -1, 0, 1, 0],
                       [0, 0, 1, -1, 1]], dtype=float)
        rhs = np.array([a[0] + a[2] * Pl + a[3] * WG[k] + e1,
                        b[0] + b[2] * Pl + b[3] * Kl + e2,
                        c[0] + c[2] * Xl + c[3] * A[k] + e3,
                        G[k],
                        -TX[k]])
        CONS[k], I[k], WP[k], X[k], PR[k] = np.linalg.solve(M_, rhs)
        K[k] = Kl + I[k]
    return pd.DataFrame({"CONS": CONS, "I": I, "WP": WP, "X": X, "PR": PR, "K": K, "G": G, "T": TX, "WG": WG,
                         "A": A}, index=pd.Index([str(y) for y in years], name="period")).iloc[10:]


def build(out_dir=HERE):
    q = make_toy_q()
    frames = {"toy_q": q, "toy_a": make_toy_a(q), "toy_m": make_toy_m(q), "klein_like": make_klein_like()}
    paths = {}
    for name, df in frames.items():
        p = os.path.join(out_dir, f"{name}.csv")
        df.to_csv(p, float_format="%.6f", lineterminator="\n")
        paths[name] = p
    return paths


if __name__ == "__main__":
    for k, p in build().items():
        print(k, p)
