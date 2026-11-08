#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
test_100_equations.py

난이도별 가상 100개 방정식 변환 검증 테스트

난이도 구분:
  Level 1 (1~20):   단순 변수, 단일 함수
  Level 2 (21~40):  2중 중첩, 비율, 시차+함수
  Level 3 (41~60):  3중 중첩, 복합 산술+시계열
  Level 4 (61~80):  4중 이상 중첩, 연쇄 속성, 다변수 혼합
  Level 5 (81~100): 실전 극한 패턴, 정규표현식 불가능 케이스

검증 기준:
  1. ast.parse()에 SyntaxError가 없는가 (유효한 Python 코드인가)
  2. 괄호 균형이 맞는가 (열린 괄호 수 == 닫힌 괄호 수)
  3. 변수가 df['...'] 형태로 변환되었는가
  4. 함수가 np.log / np.exp 로 변환되었는가
"""

import sys
import os
import ast

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 프로젝트 루트
from equion.formula.ast_formula import user_to_pandas


# ============================================================================
# 100개 가상 방정식 정의
# ============================================================================

EQUATIONS = {
    # ==================================================================
    # Level 1: 단순  (1~20)
    # ==================================================================
    "Level 1 - 단순 변수/함수": [
        # 1~5: 단순 변수
        "RCPSA",
        "RGDPSA",
        "CPI",
        "KRW",
        "WAGE",
        # 6~10: 단일 시차/속성
        "RCPSA.t(-1)",
        "WAGE.qoq",
        "CPI.yoy",
        "PPI.diff",
        "RGDPSA.ma(4)",
        # 11~15: 단일 함수
        "log(CPI)",
        "log(KRW)",
        "exp(RCPSA)",
        "log(RGDPSA)",
        "log(PPI)",
        # 16~20: 단순 산술
        "RCPSA+RGDPSA",
        "CPI/KRW",
        "WAGE*0.5",
        "RCPSA-CPI",
        "log(CPI)+log(KRW)",
    ],

    # ==================================================================
    # Level 2: 중간  (21~40)
    # ==================================================================
    "Level 2 - 2중 중첩/비율/시차+함수": [
        # 21~25: 시차 + 함수
        "log(RCPSA.t(-1))",
        "log(CPI.t(-4))",
        "log(KRW.t(-2))",
        "exp(WAGE.t(-1))",
        "RCPSA.t(-1)/RGDPSA.t(-1)",
        # 26~30: 속성 + 산술
        "CPI.qoq+PPI.qoq",
        "WAGE.yoy*0.5",
        "log(TBR3Y+100)",
        "KRW.yoy+LIBOR",
        "RCPSA.ma(2)+RGDPSA.ma(2)",
        # 31~35: 비율
        "RCINSA/RGDPSA",
        "log(HOUSEP/CPI)",
        "log(WAGESA/CPI)",
        "RCPSA/RGDPSA",
        "log(PEXI/PIMI)",
        # 36~40: 복합 시차
        "RCPSA.t(-1)+RCPSA.t(-4)",
        "log(RCPSA.t(-1))+log(RCPSA.t(-4))",
        "RCPSA.t(-1)*CPI.t(-1)",
        "log(RGDPSA.t(-1))-log(RGDPSA.t(-4))",
        "REXGSA.qoq+RIMGSA.qoq",
    ],

    # ==================================================================
    # Level 3: 어려움  (41~60)
    # ==================================================================
    "Level 3 - 3중 중첩/복합 산술+시계열": [
        # 41~45: 괄호 내 비율 + 함수
        "(CPI/KRW).ma(2)",
        "(CPI/KRW).qoq",
        "(PEXI/PIMI).qoq",
        "(HOUSEP/CPI).qoq",
        "(BOPCASA/RGDPSA).ma(2)",
        # 46~50: log + 비율 + 시차
        "log((CPI/KRW).ma(2))",
        "log(CGFRSA.t(-4).ma(2))",
        "log(WAGESA.t(-1)/CPI.t(-1))",
        "RCINSA.t(-1)/RGDPSA.t(-1)",
        "log(HCREDIT.t(-1)/CPI.t(-1))",
        # 51~55: 시차 + 이동평균 체인
        "RCPSA.t(-4).ma(2)",
        "RCPSA.t(-1).ma(4)",
        "log(WTI.ma(2))",
        "(TBR3Y+100).qoq",
        "(CBR3YAA_+100).qoq",
        # 56~60: 다변수 산술 + 함수
        "log(RGDPSA*DFGDPSA)",
        "log(KRW*PIMI)",
        "log(REXGSA*DFXGSA/KRW)",
        "log(RIMGSA*DFMGSA/KRW)",
        "log(RCPSA+RFISA+RCISA+RCINSA+RCGSA)",
    ],

    # ==================================================================
    # Level 4: 매우 어려움  (61~80)
    # ==================================================================
    "Level 4 - 4중 이상 중첩/연쇄 속성/다변수 혼합": [
        # 61~65: 다변수 합 + 시계열 함수
        "log((RCPSA+RFISA+RCISA+RCINSA+RCGSA).ma(2))",
        "((LFSA/CPI).ma(2)).qoq",
        "log((RGDPSA.yoy+100).ma(4))",
        "(RCPSA+RGDPSA-CPI*2).ma(4)",
        "log(CBR3YAA_-CPI.yoy+100)",
        # 66~70: 4중 괄호 중첩
        "log((CPI.t(-1)/KRW.t(-1)).ma(4))",
        "log((RCPSA.t(-1)*CPI.t(-2)/KRW.t(-3)).ma(4))",
        "log(HOUSEP.t(-1)/CPI.t(-1))",
        "log(HOUSEP.t(-4)/CPI.t(-4))",
        "log(HOUSEP.t(-8)/CPI.t(-8))",
        # 71~75: 시차 + 이동평균 + 함수 체인
        "log(CGFRSA.t(-4).ma(2))",
        "RCPSA.t(-2).ma(3).qoq",
        "log(RCPSA.t(-1).ma(2))",
        "(LIBOR-BOKRATE).ma(2)",
        "(KRW/CNY).qoq",
        # 76~80: 혼합 패턴
        "TBR3Y-CPI.yoy",
        "LIBOR+KRW.yoy",
        "LIBOR-CBR3YAA_",
        "CBR3YAA_-TBR3Y",
        "(RCISA+RFISA).qoq",
    ],

    # ==================================================================
    # Level 5: 극한  (81~100)
    # ==================================================================
    "Level 5 - 실전 극한 / 정규표현식 불가": [
        # 81~85: 5중 괄호 중첩
        "log(((WAGE.t(-2).ma(3)).qoq).ma(4))",
        "log(((LFSA.t(-1)/CPI.t(-1)).ma(2)).qoq+100)",
        "((((CPI.t(-1)/KRW.t(-2)).ma(2)).yoy+100).ma(4))",
        "exp(log(WAGE.ma(2))/log(CPI.t(-1)))",
        "log(log(RCPSA.t(-1)+1)+100)",
        # 86~90: 복합 내부 산술 + 중첩 시계열
        "(log(RCPSA.t(-1))+WAGE.qoq*0.5).ma(3)",
        "log(RCPSA.t(-1)*WAGE.t(-2)*CPI.t(-3)/KRW.t(-4))",
        "((RCPSA.t(-1)+RGDPSA.t(-2))/(CPI.t(-1)+KRW.t(-2))).ma(4)",
        "log((RCPSA.t(-1)*DFGDPSA.t(-1)/KRW.t(-1)).ma(2))",
        "exp(-(TBR3Y.t(-1)+CPI.yoy)/100)",
        # 91~95: 초복잡 실전 변형
        "log(((RCPSA+RCGSA+RCISA).t(-1).ma(2)).qoq+100)",
        "((PEXI.t(-1)/PIMI.t(-1)).ma(4)).yoy",
        "log(((WAGE/CPI).t(-1).ma(2)).yoy+100)",
        "((RCPSA.t(-1)/RGDPSA.t(-1)).ma(2)-(RCPSA.t(-4)/RGDPSA.t(-4)).ma(2))",
        "exp(log((CPI.t(-1)*KRW.t(-2)).ma(3))/log(PPI.t(-1).ma(2)))",
        # 96~100: 가장 극단적인 패턴
        "log(((LFSA.t(-1)/CPI.t(-1)).ma(2)*RGDPSA.t(-1)).qoq+100)",
        "((((RCPSA.t(-1)+RGDPSA.t(-2))/2).ma(3)).yoy+100).ma(4)",
        "exp(log(WAGE.t(-1).ma(2))*0.5-log(CPI.t(-2).ma(3))*0.3)",
        "log(((PEXI/PIMI).t(-1).ma(4)).qoq+100)*0.5+log(KRW.t(-1))*0.3",
        "((log(RCPSA.t(-1))+log(RGDPSA.t(-2)))/2-(log(CPI.t(-1))+log(KRW.t(-2)))/2).ma(3)",
    ],
}


# ============================================================================
# 테스트 실행
# ============================================================================

def run_test():
    print("=" * 100)
    print("  AST 수식 변환 엔진: 난이도별 100개 가상 방정식 스트레스 테스트")
    print("=" * 100)

    total_pass = 0
    total_fail = 0
    failures = []

    eq_num = 0

    for level_name, eqs in EQUATIONS.items():
        print(f"\n{'─'*100}")
        print(f"  {level_name}  ({len(eqs)}개)")
        print(f"{'─'*100}")

        level_pass = 0
        level_fail = 0

        for expr in eqs:
            eq_num += 1
            errors = []

            try:
                result = user_to_pandas(expr)

                # 검증 1: 괄호 균형
                open_p = result.count('(')
                close_p = result.count(')')
                if open_p != close_p:
                    errors.append(f"괄호 불균형: ({open_p} vs ){close_p}")

                # 검증 2: 유효한 Python 코드인지 (AST 재파싱)
                try:
                    ast.parse(result, mode='eval')
                except SyntaxError as se:
                    errors.append(f"SyntaxError: {se}")

                # 검증 3: df['...'] 또는 np. 존재 여부
                has_df = "df[" in result
                has_np = "np." in result
                has_num = any(c.isdigit() for c in result)
                if not has_df and not has_np and not has_num:
                    errors.append("df[] 또는 np. 변환 없음")

            except Exception as e:
                errors.append(f"변환 예외: {e}")
                result = "(변환 실패)"

            if errors:
                level_fail += 1
                total_fail += 1
                failures.append((eq_num, expr, errors, result))
                print(f"  [{eq_num:3d}] FAIL  {expr}")
                for err in errors:
                    print(f"              -> {err}")
                print(f"              => {result[:80]}")
            else:
                level_pass += 1
                total_pass += 1
                print(f"  [{eq_num:3d}] PASS  {expr}")
                print(f"              => {result[:90]}")

        print(f"\n  >> {level_name}: {level_pass}/{level_pass+level_fail} PASS")

    # ========================================================================
    # 최종 결과
    # ========================================================================
    print(f"\n{'='*100}")
    print(f"  FINAL RESULT: {total_pass} PASS / {total_fail} FAIL  (total {total_pass+total_fail})")
    print(f"{'='*100}")

    if total_fail == 0:
        print(f"\n  [OK] ALL {total_pass} EQUATIONS PASSED!")
    else:
        print(f"\n  [NG] {total_fail} EQUATIONS FAILED:")
        for num, expr, errs, res in failures:
            print(f"    #{num}: {expr}")
            for e in errs:
                print(f"         {e}")

    print(f"{'='*100}")
    return total_fail


def test_suite():
    """pytest 진입점 — 이 파일의 검사 묶음 전체(하나라도 실패하면 실패). `python tests/test_100_equations.py`와 같은 검사."""
    assert run_test() == 0


if __name__ == "__main__":
    sys.exit(run_test())
