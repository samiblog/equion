# 이 파일은 docs/tutorial/03-diagnostics.md에서 만든다(python docs/build_docs.py) — 고치려면 문서를 고친다.
"""3. 진단 검정 — 문서: docs/tutorial/03-diagnostics.md"""


# %% 3. 진단 검정
import equion as eqn

wf = eqn.datasets.load("toy_q")
eq = wf.equation("eq_i").ls("I c Y(-1) R")          # 참 모형과 같은 꼴의 투자식

# %% 3.1 표준 진단 한 표
eqn.show(eq.diagnostics())

# %% 3.2 검정 결과 다루기
lm = eq.serial_lm(4)                    # Breusch-Godfrey LM, 시차 4까지
print(round(lm.statistic, 4), round(lm.pvalue, 4), lm.null)
print(lm.reject(0.05))                  # 5%에서 기각하는가
eqn.show(lm)                            # 표로 보기

# %% 3.3 잔차 — 자기상관·이분산·정규성·함수 형태
q = eq.ljungbox(8)                      # Ljung-Box Q(시차별 표는 q.table)
eq.white()                              # White 이분산(교차항 포함, cross=False면 빼고)
eq.breusch_pagan()                      # Breusch-Pagan-Godfrey
eq.arch(4)                              # ARCH LM — 분산의 자기상관
eq.normality()                          # Jarque-Bera
eq.reset(2)                             # Ramsey RESET — 적합값 제곱·세제곱을 더하면 나아지는가
print(q.table.round(3).head(3))
bad = wf.equation("bad").ls("CN c G")
bad.serial_lm(4)
bad.reset(1)
print(round(bad.stats["durbin_watson"], 3))

# %% 3.4 구조 변화와 안정성
eq.chow("1995Q1")
cs = eq.cusum()                         # 통계량 = 누적합이 경계에 가장 가까이 간 비율(1보다 작으면 경계 안 — 안정)
rc = eq.recursive()                     # 재귀 계수: 처음 몇 기로 시작해 한 기씩 늘려 추정
print(rc.iloc[[20, 100, -1]].round(3))

# %% 3.5 계수 제약
eq.wald("c(2) = 0.15", "c(3) = -1")
eq.wald("c(2) = 0.2")                   # 틀린 값은 기각된다

# %% 3.6 변수를 더하거나 빼도 되는가
eq.omitted("R(-1)", "G")                # 더하면 설명력이 유의하게 느는가(참 모형에는 없다)
eq.redundant("R")                       # 빼도 되는가(참 모형에 있다 — 기각)

# %% 3.7 단위근
wf.adf("log(Y)", trend="ct")            # 상수 + 추세 — 단위근을 기각하지 못한다
wf.adf("dlog(Y)")                       # 차분하면 정상(기각)
wf.kpss("dlog(Y)")                      # 정상을 기각하지 못한다

# %% 3.8 공적분
wf.coint("RL", "R")                     # Engle-Granger: 장기 회귀 잔차의 단위근 검정
eqn.show(wf.johansen("log(M2) log(P) log(Y) RL"))     # Johansen: 여러 변수의 공적분 순위

# %% 3.9 오차수정모형
ecm = wf.ecm("ecm_rl", "RL", ["R"])
eqn.show(ecm)
print(round(ecm.adjustment["계수"], 3), round(ecm.half_life, 2))
