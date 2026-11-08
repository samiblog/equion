# 이 파일은 docs/howto/troubleshooting.md에서 만든다(python docs/build_docs.py) — 고치려면 문서를 고친다.
"""문제 해결 — 문서: docs/howto/troubleshooting.md"""


# %% 문제 해결
import equion as eqn

wf = eqn.datasets.load("toy_q")
eq_i = wf.equation("eq_i").ls("I c Y(-1) R")
eq_cn = wf.equation("eq_cn").ls("CN c Y CN(-1)")

# %% T1. "데이터에도 없고 어떤 식도 결정하지 않는 변수가 있습니다"
try:  # 이 예는 일부러 오류를 보인다
    wf.model("t1").merge(eq_i, eq_cn).append("Y = CN + I + GOV").endogenous
except Exception as e:
    print(f"{type(e).__name__}: {e}")

# %% T2. "같은 변수를 결정하는 식이 둘 이상입니다"
try:  # 이 예는 일부러 오류를 보인다
    eq_cn2 = wf.equation("eq_cn2").ls("CN c Y")
    wf.model("t2").merge(eq_cn, eq_cn2).append("Y = CN + I + G").endogenous
except Exception as e:
    print(f"{type(e).__name__}: {e}")

# %% T3. 상태가 '일부식 제외'(partial)
m = wf.model("t3").merge(eq_i, eq_cn).append("Y = CN + I + G")
r = m.solve("1970Q1", "1970Q4")
print(r.status()[["status", "excluded"]].head(2))
eqn.show(m.gaps("1970Q1", "1970Q1"))

# %% T5. 시나리오 결과가 기준선과 같다
m.scenario("check").shock("G", 10, "2015Q1")
print(m.scenario().name, m.scenario().alias)

# %% T6. "'…'은(는) 이미 시리즈 이름입니다"
try:  # 이 예는 일부러 오류를 보인다
    wf.equation("i").ls("I c Y(-1) R")
except Exception as e:
    print(f"{type(e).__name__}: {e}")

# %% T7. "시점 표기 오류"
try:  # 이 예는 일부러 오류를 보인다
    wf.smpl("2010M3", "2012M1")
except Exception as e:
    print(f"{type(e).__name__}: {e}")
