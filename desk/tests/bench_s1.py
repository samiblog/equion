"""성공 기준 S1(식을 고치고 추정 결과를 보기까지 1초 안)을 잰다 — 예제 프로젝트와 합성 큰 모형.

    uv run --package equion-desk python desk/tests/bench_s1.py [식 수=300]

앱과 같은 길로 잰다: 로컬 서버(`/api/est`·`/api/hs`) → 띄워 둔 작업 프로세스 → `eqn.project`. 자료는 코드로 만든 합성 자료다.
"""
from __future__ import annotations

import os
import sys
import tempfile
import time

import numpy as np
import pandas as pd


def make_big(folder: str, n_eq: int = 300, n_obs: int = 200, block: int = 5, seed: int = 20261111) -> str:
    """합성 큰 모형 프로젝트. 식 n_eq개 — `block`개씩 서로 물린 동시 블록, 블록 사이는 시차로 이어진다. 블록마다 소계 항등식."""
    rng = np.random.default_rng(seed)
    idx = pd.period_range("1970Q1", periods=n_obs, freq="Q").strftime("%YQ%q")
    data: dict[str, np.ndarray] = {}
    lines: list[str] = []
    x = np.zeros((n_obs, n_eq))
    z = rng.normal(0, 1, (n_obs, n_eq)).cumsum(axis=0) * 0.1 + 10
    for t in range(1, n_obs):
        prev = x[t - 1]
        cur = np.zeros(n_eq)
        for _ in range(30):      # 동시 블록을 되풀이로 푼다(자료를 만드는 쪽)
            for i in range(n_eq):
                j = i + 1 if (i + 1) % block else i + 1 - block      # 같은 블록 안의 다음 식
                k = (i - block) % n_eq                                # 앞 블록(시차로)
                cur[i] = 1.0 + 0.5 * prev[i] + 0.3 * z[t, i] + 0.1 * cur[j] + 0.05 * prev[k]
        x[t] = cur + rng.normal(0, 0.05, n_eq)
    for i in range(n_eq):
        j = i + 1 if (i + 1) % block else i + 1 - block
        k = (i - block) % n_eq
        data[f"X{i}"], data[f"Z{i}"] = x[:, i], z[:, i]
        lines.append(f"X{i} c X{i}(-1) Z{i} X{j} X{k}(-1)")
    # 항등식: 블록마다 소계 — 긴 합 하나는 엔진의 식 깊이 한도(250)에 걸린다
    for b in range(n_eq // block):
        members = range(b * block, (b + 1) * block)
        data[f"S{b}"] = x[:, list(members)].sum(axis=1)
        lines.append(f"S{b} = " + " + ".join(f"X{i}" for i in members))
    os.makedirs(os.path.join(folder, "DATA"), exist_ok=True)
    os.makedirs(os.path.join(folder, "EQUATIONS"), exist_ok=True)
    df = pd.DataFrame(data, index=idx).iloc[1:]
    df.index.name = "date"
    df.to_csv(os.path.join(folder, "DATA", "data.csv"), encoding="utf-8", lineterminator="\n")
    with open(os.path.join(folder, "EQUATIONS", "big.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    with open(os.path.join(folder, "equion.toml"), "w", encoding="utf-8", newline="\n") as f:
        f.write('[project]\nname = "big"\nformat = "equion-project"\nformat_version = 1\n\n[data]\nfile = "DATA/data.csv"\n\n'
                '[block]\nbig = "EQUATIONS/big.txt"\n\n[model.main]\nblocks = ["big"]\n\n'
                '[hs]\nmodel = "main"\nrange = "2005Q1:last"\nmode = "dynamic"\n')
    return folder


def bench(folder: str, target: str, repeat: int = 5) -> dict:
    """서버를 거쳐 추정을 `repeat`번, 과거 재현을 두 번 하고 걸린 시간(초)을 돌려준다."""
    from equion_desk.server import AppState, create_app

    state = AppState(folder, mode="browser")
    client = create_app(state).test_client()
    try:
        t = time.perf_counter()
        r = client.get("/api/project")
        assert r.status_code == 200, r.json
        out = {"parts": len(r.json["parts"]), "start": time.perf_counter() - t, "est": [], "hs": []}
        for _ in range(repeat):
            t = time.perf_counter()
            r = client.post("/api/est", json={"target": target})
            assert r.status_code == 200, r.json
            out["est"].append(time.perf_counter() - t)
        for _ in range(2):
            t = time.perf_counter()
            r = client.post("/api/hs", json={})
            assert r.status_code == 200, r.json
            out["hs"].append(time.perf_counter() - t)
        return out
    finally:
        state.close()




if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    with tempfile.TemporaryDirectory() as tmp:
        t0 = time.perf_counter()
        big = make_big(os.path.join(tmp, "big"), n)
        print(f"합성 모형 만들기 {time.perf_counter() - t0:.1f}초 — 추정식 {n}개 + 소계 항등식")
        res = bench(big, "big:X0")
        print(f"부품 {res['parts']} · 작업 프로세스 뜨기+조립 {res['start']:.2f}초")
        print("추정(누른 뒤 응답까지, 초): " + " ".join(f"{v:.3f}" for v in res["est"]))
        print("과거 재현 2005Q1~끝(초): " + " ".join(f"{v:.2f}" for v in res["hs"]))
