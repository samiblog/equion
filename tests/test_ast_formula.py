#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
test_ast_formula.py

ast_formula 모듈의 완전성을 검증하는 테스트 스크립트입니다.

(A) 단순~복잡한 가상 수식들의 user_to_pandas() 변환 정확성
(B) 여러 꼴의 추정식(예제 자료 변수 이름) 각 항 변환
(C) user_to_solver() 내생/외생 치환 정확성
(D) pandas_formula_to_solver() 통합 테스트
"""

import sys
import os
import ast
import traceback
import numpy as np
import pandas as pd

# 같은 폴더의 ast_formula 모듈 임포트
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 프로젝트 루트
from equion.formula.ast_formula import (
    user_to_pandas,
    user_to_solver,
    pandas_formula_to_solver,
    extract_variables,
    validate_user_expression,
    normalize_user_input,
)


# ============================================================================
# 색상 유틸
# ============================================================================
def ok(msg):   print(f"  [PASS] {msg}")
def fail(msg): print(f"  [FAIL] {msg}")
def info(msg): print(f"  [INFO] {msg}")


# ============================================================================
# (A) user_to_pandas 단위 테스트
# ============================================================================
def test_user_to_pandas():
    """단순~극복잡 수식에 대한 pandas 변환 테스트"""
    print("\n" + "=" * 80)
    print("(A) user_to_pandas() 변환 테스트")
    print("=" * 80)

    cases = [
        # (입력, 기대 출력에 포함되어야 할 핵심 패턴)
        # ---- 단순 ----
        ("RCPSA",               "df['RCPSA']"),
        ("RCPSA.t(-1)",         ".shift(1)"),
        ("WAGE.qoq",            ".pct_change()"),
        ("WAGE.yoy",            ".pct_change(4)"),
        ("PPI.diff",            ".diff()"),
        ("RCPSA.ma(4)",         ".rolling(4).mean()"),
        ("log(CPI)",            "np.log("),

        # ---- 중첩 ----
        ("log(RCPSA.t(-1))",                "np.log(df['RCPSA'].shift(1))"),
        ("log(RCPSA.t(-4))",                ".shift(4)"),
        ("(CPI/KRW).ma(2)",                 ".rolling(2).mean()"),
        ("(CPI/KRW).qoq",                   ".pct_change()"),
        ("CPI.t(-1)/KRW.t(-1)",             "df['CPI'].shift(1) / df['KRW'].shift(1)"),

        # ---- 실제 방정식에서 추출한 복잡 패턴 ----
        ("log(TBR3Y.t(-1)+100)",            "np.log("),
        ("log((CPI/KRW).ma(2))",            "np.log("),
        ("log(CBR3YAA_-CPI.yoy+100)",       "np.log("),
        ("log(CGFRSA.t(-4).ma(2))",         ".shift(4)"),
        ("log((RGDPSA.yoy+100).ma(4))",     ".rolling(4).mean()"),
        ("((LFSA/CPI).ma(2)).qoq",          ".pct_change()"),
        ("RCINSA/RGDPSA",                   "df['RCINSA'] / df['RGDPSA']"),
        ("RCINSA.t(-1)/RGDPSA.t(-1)",       ".shift(1)"),
        ("(BOPCASA/RGDPSA).ma(2)",          ".rolling(2).mean()"),
        ("log(REXGSA*DFXGSA/KRW)",          "np.log("),

        # ---- 극도로 복잡한 가상 수식 (괄호 4중 중첩) ----
        (
            "log((CPI.t(-1)/KRW.t(-1)).ma(4))",
            "np.log((df['CPI'].shift(1) / df['KRW'].shift(1)).rolling(4).mean())"
        ),
        (
            "log(((WAGE.yoy+100).ma(2)).t(-1))",
            "np.log("
        ),
        (
            "(log(RCPSA.t(-1))+WAGE.qoq*0.5).ma(3)",
            ".rolling(3).mean()"
        ),
        (
            "log((RCPSA.t(-1)*CPI.t(-2)/KRW.t(-3)).ma(4))",
            ".rolling(4).mean()"
        ),
        (
            "exp(log(RCPSA.t(-1).ma(2)))",
            "np.exp("
        ),
    ]

    passed = 0
    failed = 0

    for user_expr, expected_pattern in cases:
        try:
            result = user_to_pandas(user_expr)
            # 기대 패턴이 결과에 있는지
            if expected_pattern in result:
                ok(f"{user_expr:50s} → {result}")
                passed += 1
            else:
                fail(f"{user_expr:50s}")
                info(f"  결과 : {result}")
                info(f"  기대 : '{expected_pattern}' 포함")
                failed += 1
        except Exception as e:
            fail(f"{user_expr:50s} → 예외: {e}")
            failed += 1

    print(f"\n  결과: {passed}/{passed+failed} 통과")
    return passed, failed


# ============================================================================
# (B) 여러 꼴의 추정식 파싱 테스트(예제 자료 변수 이름)
# ============================================================================
# 시계열 연산·함수·괄호·비율·지시자를 고루 담은 식 — 저장소 밖에서도 도는 고정 목록(옛 변환기가 받는 꼴만:
# 괄호 안 공백·시차 범위·@함수 좌변은 엔진 v3 파서만 받는다)
SAMPLE_EQUATIONS = [
    "log(CN) c log(Y-G/(P/100)) log(M2/P) log(R.t(-1)+100) log(CN.t(-1)) log((P/POIL).ma(2)) log(CN.t(-4))",
    "log(CN) c log(Y) log(CN(-1))",
    "log(I) c log(Y) log(I(-1)) R @seas",
    "log(I) c log(Y.t(-1)) R.t(-1) log(I.t(-1))",
    "dlog(P) c dlog(Y) dlog(POIL) dlog(P(-1))",
    "log(P) c log(POIL.t(-1)) log(P.t(-1)) Y.qoq",
    "RL c R RL.t(-1)",
    "RL c R.t(-1) R.t(-2) RL.t(-1)",
    "log(M2) c log(P) log(Y) RL log(M2.t(-1))",
    "log(M2/P) c log(Y) RL.diff log(M2.t(-1)/P.t(-1))",
    "CN.yoy c Y.yoy P.yoy",
    "log(CNNSA) c log(CN) @seas",
    "d(log(CNNSA),1,4) c d(log(CN),1,4)",
    "log(Y) c log(CN+I) log(G) log(Y.t(-1))",
    "log(I/Y) c R RL log(I.t(-1)/Y.t(-1))",
    "Y.gr(4) c CN.gr(4) I.gr(4)",
    "log(P) c log(POIL.ma(4)) log(P.t(-1)) R.ma(2)",
    "log(CN) c @trend @d(2008Q4) @step(2010Q1)",
    "log(CN) c log(Y) @smpl 1980Q1 2019Q4",
    "log((CN+I)/2) c log(Y.ma(4)) (R-RL).t(-1)",
]


def test_real_equations():
    """여러 꼴의 추정식 각 항을 user_to_pandas()로 변환"""
    print("\n" + "=" * 80)
    print("(B) 여러 꼴의 추정식 파싱 테스트")
    print("=" * 80)

    equations = list(SAMPLE_EQUATIONS)

    passed = 0
    failed = 0

    import re as _re
    for i, eq_str in enumerate(equations, 1):
        eq_str = normalize_user_input(eq_str)
        # @smpl/@seas/@d/@step/@trend 등 전처리 지시자는 Equation 단계에서
        # 처리되므로(저수준 user_to_pandas 대상 아님) 이 테스트에서는 제외한다.
        eq_str = _re.sub(r'@smpl\s+\S+\s+\S+', ' ', eq_str)
        parts = eq_str.split()
        dep_var = parts[0]

        # 상수항 c 및 @-지시자 토큰 제외
        indep_vars = [p for p in parts[1:] if p != 'c' and not p.startswith('@')]

        all_ok = True
        fail_details = []

        # 종속변수 변환 테스트
        try:
            user_to_pandas(dep_var)
        except Exception as e:
            all_ok = False
            fail_details.append(f"종속변수 '{dep_var}': {e}")

        # 독립변수 변환 테스트
        for var in indep_vars:
            try:
                result = user_to_pandas(var)
                # 결과에 df[ 가 있거나 np. 가 있어야 정상
                if 'df[' not in result and 'np.' not in result and not result.replace('.', '').replace('-','').lstrip('-').isdigit():
                    # 숫자만으로 된 결과가 아닌 경우에만 경고
                    if not any(c.isalpha() for c in result):
                        pass  # 순수 숫자
                    else:
                        fail_details.append(f"'{var}' → '{result}' (df[ 또는 np. 없음)")
                        all_ok = False
            except Exception as e:
                all_ok = False
                fail_details.append(f"'{var}': {e}")

        if all_ok:
            ok(f"방정식 {i:2d}: {eq_str[:65]}...")
            passed += 1
        else:
            fail(f"방정식 {i:2d}: {eq_str[:65]}...")
            for d in fail_details:
                info(f"    {d}")
            failed += 1

    print(f"\n  결과: {passed}/{passed+failed} 방정식 통과")
    return passed, failed


# ============================================================================
# (C) user_to_solver 테스트 (가상 데이터)
# ============================================================================
def test_user_to_solver():
    """내생/외생 변수 치환 정확성 테스트"""
    print("\n" + "=" * 80)
    print("(C) user_to_solver() 내생/외생 치환 테스트")
    print("=" * 80)

    # 가상 데이터 생성 (10행)
    n = 10
    df = pd.DataFrame({
        'RCPSA':  np.linspace(100, 200, n),
        'WAGE':   np.linspace(3000, 4000, n),
        'CPI':    np.linspace(100, 110, n),
        'KRW':    np.linspace(1200, 1400, n),
        'RGDPSA': np.linspace(500, 600, n),
        'PPI':    np.linspace(100, 105, n),
        'TBR3Y':  np.linspace(2.0, 3.5, n),
        'KOSPI':  np.linspace(2000, 2500, n),
    })

    endogenous = ['RCPSA', 'RGDPSA']
    ti = 5  # 중간 시점

    cases = [
        # 1. 외생변수 → 수치로 치환되어야
        ("WAGE", True),
        # 2. 내생변수 → RCPSA 기호가 남아야
        ("RCPSA", False),
        # 3. 외생 과거시점 → 수치 치환
        ("CPI.t(-1)", True),
        # 4. 내생 과거시점 → 수치 치환 (과거값이므로)
        ("RCPSA.t(-1)", True),
        # 5. 외생 이동평균 → 수치 치환
        ("WAGE.ma(2)", True),
        # 6. 내생 현시점에 함수 적용 → 기호 유지
        ("log(RCPSA)", False),
        # 7. 복합: 외생/내생 혼합
        ("log(RCPSA) + WAGE.t(-1)", False),  # RCPSA 기호가 남아 있어야
    ]

    passed = 0
    failed = 0

    for expr, should_be_all_numeric in cases:
        try:
            result = user_to_solver(expr, df, ti, endogenous)

            # 내생변수 기호가 남아있는지 확인
            has_endo_symbol = any(v in result for v in endogenous)

            if should_be_all_numeric:
                # 내생변수 기호가 없어야 함 (괄호/함수 제외 순수 수치)
                if not has_endo_symbol:
                    ok(f"{expr:40s} → {result[:60]}")
                    passed += 1
                else:
                    fail(f"{expr:40s} → {result[:60]}  (수치화 안 됨)")
                    failed += 1
            else:
                # 내생변수 기호가 남아 있어야 함
                if has_endo_symbol:
                    ok(f"{expr:40s} → {result[:60]}  (내생변수 기호 유지)")
                    passed += 1
                else:
                    fail(f"{expr:40s} → {result[:60]}  (내생변수 기호 사라짐)")
                    failed += 1
        except Exception as e:
            fail(f"{expr:40s} → 예외: {e}")
            traceback.print_exc()
            failed += 1

    print(f"\n  결과: {passed}/{passed+failed} 통과")
    return passed, failed


# ============================================================================
# (D) pandas_formula_to_solver 통합 테스트
# ============================================================================
def test_pandas_formula_to_solver():
    """pandas_formula → solver 수식 변환 통합 테스트"""
    print("\n" + "=" * 80)
    print("(D) pandas_formula_to_solver() 통합 테스트")
    print("=" * 80)

    n = 20
    df = pd.DataFrame({
        'RCPSA':  np.linspace(100, 200, n),
        'WAGE':   np.linspace(3000, 4000, n),
        'CPI':    np.linspace(100, 110, n),
        'KRW':    np.linspace(1200, 1400, n),
        'RGDPSA': np.linspace(500, 600, n),
        'PPI':    np.linspace(100, 105, n),
    })

    endogenous = ['RCPSA', 'RGDPSA']
    ti = 10

    # 시뮬레이션할 pandas_formula 예시
    formulas = [
        # 간단한 경우
        "np.log(df['RCPSA']) = 1.23 + 0.85 * (np.log(df['RCPSA'].shift(1))) + 0.12 * (df['WAGE'].pct_change() * 100)",
        # 좀 더 복잡한 경우
        "df['RCPSA'] / df['RGDPSA'] = 0.5 + 0.3 * (df['RCPSA'].shift(1) / df['RGDPSA'].shift(1)) + 0.1 * (df['CPI'].pct_change() * 100)",
    ]

    passed = 0
    failed = 0

    for formula in formulas:
        try:
            result = pandas_formula_to_solver(formula, df, ti, endogenous)

            # 기본 검증: 결과에 ' = '가 있어야 함
            assert ' = ' in result, "결과에 ' = '가 없음"

            # 내생변수 기호가 유지되어야
            has_endo = any(v in result for v in endogenous)
            assert has_endo, "내생변수 기호가 사라짐"

            # df['...'] 패턴이 남아있으면 안 됨
            assert "df[" not in result, f"df[ 패턴이 남아있음: {result}"

            ok(f"변환 성공")
            info(f"  입력: {formula[:70]}...")
            info(f"  결과: {result[:70]}...")
            passed += 1
        except Exception as e:
            fail(f"변환 실패: {e}")
            info(f"  입력: {formula[:70]}...")
            traceback.print_exc()
            failed += 1

    print(f"\n  결과: {passed}/{passed+failed} 통과")
    return passed, failed


# ============================================================================
# (E) 극한 중첩 괄호 스트레스 테스트
# ============================================================================
def test_extreme_nesting():
    """정규표현식으로는 절대 불가능한 극한 중첩 수식 테스트"""
    print("\n" + "=" * 80)
    print("(E) 극한 중첩 괄호 스트레스 테스트")
    print("=" * 80)

    extreme_cases = [
        # 1. 4중 괄호 + 시차 + 이동평균 + 로그
        "log((CPI.t(-1)/KRW.t(-1)).ma(4))",

        # 2. 5중 괄호: 시차 → 이동평균 → 변화율 → 이동평균 → 로그
        "log(((WAGE.t(-2).ma(3)).qoq).ma(4))",

        # 3. 나눗셈 체인 + 복합 함수
        "log(RCPSA.t(-1)*CPI.t(-2)/KRW.t(-3))",

        # 4. 내생변수 혼합 비율
        "RCPSA/RGDPSA + log(CPI.t(-1)/KRW.t(-1))",

        # 5. 괄호 내부 산술 + 시계열 함수
        "(RCPSA+RGDPSA-CPI*2).ma(4)",

        # 6. 연쇄 속성
        "((((CPI.t(-1)/KRW.t(-2)).ma(2)).yoy+100).ma(4))",

        # 7. log 중첩
        "log(log(RCPSA.t(-1)+1)+100)",

        # 8. exp + log 혼합
        "exp(log(WAGE.ma(2))/log(CPI.t(-1)))",

        # 9. 곱하기 체인 + 시차 + 로그
        "log(RCPSA.t(-1)*WAGE.t(-2)*CPI.t(-3)/KRW.t(-4))",

        # 10. 실제 방정식에서 가장 복잡했던 패턴 변형
        "log(((LFSA.t(-1)/CPI.t(-1)).ma(2)).qoq+100)",
    ]

    passed = 0
    failed = 0

    for expr in extreme_cases:
        try:
            result = user_to_pandas(expr)

            # 괄호 균형 확인
            open_p = result.count('(')
            close_p = result.count(')')
            assert open_p == close_p, f"괄호 불균형! ( = {open_p}, ) = {close_p}"

            # AST로 다시 파싱 가능한지 확인 (유효한 Python 코드인지)
            ast.parse(result, mode='eval')

            ok(f"성공: {expr}")
            info(f"  → {result}")
            passed += 1
        except Exception as e:
            fail(f"실패: {expr}")
            info(f"  → 에러: {e}")
            failed += 1

    print(f"\n  결과: {passed}/{passed+failed} 통과")
    return passed, failed


# ============================================================================
# 메인
# ============================================================================
def main():
    print("=" * 80)
    print("  ast_formula.py 종합 검증 테스트")
    print("  (정규표현식 → AST 변환 엔진 완전성 검증)")
    print("=" * 80)

    total_pass = 0
    total_fail = 0

    p, f = test_user_to_pandas()
    total_pass += p; total_fail += f

    p, f = test_real_equations()
    total_pass += p; total_fail += f

    p, f = test_user_to_solver()
    total_pass += p; total_fail += f

    p, f = test_pandas_formula_to_solver()
    total_pass += p; total_fail += f

    p, f = test_extreme_nesting()
    total_pass += p; total_fail += f

    print("\n" + "=" * 80)
    print(f"  최종 결과: {total_pass} 통과 / {total_fail} 실패  "
          f"(총 {total_pass+total_fail} 케이스)")

    if total_fail == 0:
        print("  [OK] ALL TESTS PASSED!")
    else:
        print(f"  [NG] {total_fail} FAILED")
    print("=" * 80)

    return total_fail


def test_suite():
    """pytest 진입점 — 이 파일의 검사 묶음 전체(하나라도 실패하면 실패). `python tests/test_ast_formula.py`와 같은 검사."""
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
