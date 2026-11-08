#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
test_error_equations.py

사용자가 수식을 작성할 때 흔히 할 수 있는 실수를 시뮬레이션하고,
문제가 발생할 경우 어떤 부분에서 오류가 났는지 정확하게 짚어주는 검증 로직 모듈입니다.
"""

import ast
import traceback

def verify_expression(expr: str) -> bool:
    """
    개별 수식(표현식)에 대해 문법(AST) 구조를 검증하고, 
    오류 발생 시 위치를 시각적으로 출력합니다.
    """
    print(f"{'='*60}")
    print(f"검증 대상 수식: '{expr}'")
    
    # 1단계: 기본적인 괄호 개수 비교 (ast.parse 전 직관적 피드백 제공)
    open_p = expr.count('(')
    close_p = expr.count(')')
    if open_p != close_p:
        print(f"[에러 종류: 괄호 불균형]")
        print(f"   - 설명: 열린 괄호 '('는 {open_p}개, 닫힌 괄호 ')'는 {close_p}개입니다.")
        # 이 경우에는 파서 에러 이전에 짚어줄 수 있음
        # 뒤이은 ast.parse에서 위치까지 잡아냄

    # 2단계: Python AST 파서(eval 모드)를 이용한 정밀 문법 검증
    try:
        ast.parse(expr, mode='eval')
        print("[결과: 정상 통과] 문법적으로 완벽한 수식입니다.")
        return True
    
    except SyntaxError as e:
        print(f"[에러 종류: 구문 오류 (SyntaxError)]")
        print(f"   - 원인: {e.msg}")
        
        if e.text and e.offset is not None:
            # 공백, 줄바꿈 등 제거
            line = e.text.strip('\n')
            # 위치 보정 (offset은 1부터 시작하므로 0부터 시작하게 맞춤)
            offset = e.offset - 1
            
            print("   - 오류 발생 위치 시각화:")
            print(f"     수식: {line}")
            # 화살표(^)로 해당 offset 위치를 가리킴
            pointer = " " * offset + "^"
            print(f"     위치: {pointer}")
            print("   - 조치 제안: 화살표(^)가 가리키는 위치 또는 그 직전의 연산자, 괄호, 오타 등을 확인하세요.")
        else:
            print("   - 조치 제안: 수식 끝부분이나 괄호 닫기 부분을 전체적으로 재확인해야 합니다.")
            
        return False
    except Exception as e:
        print(f"[에러 종류: 알 수 없는 시스템 오류]")
        print(f"   - 원인: {e}")
        return False
    finally:
        print(f"{'='*60}\n")


def run_error_scenarios():
    """사용자가 자주 하는 실수 시나리오를 정의하고 실행합니다."""
    
    scenarios = [
        # 실수 1: 닫는 괄호 누락
        "log(CPI.t(-1)",
        
        # 실수 2: 여는 괄호 누락
        "log CPI.t(-1))",
        
        # 실수 3: 연산자(+, -, *, /) 누락 (변수 사이 공백)
        "RCPSA.t(-1) WAGE",
        
        # 실수 4: 연산자 연속(중복) 입력 오타
        "RCPSA + * CPI",
        
        # 실수 5: 마침표(.) 중복 입력
        "CPI..t(-1)",
        
        # 실수 6: 파이썬 구문에 맞지 않는 특수문자 사용
        "log(CPI $ KRW)",
        
        # 실수 7: 표현식(eval) 안에서 대입 연산자(=) 사용 (항등식 작성 시 c 대신 =를 쓴 경우 부분 파싱 에러)
        "RCPSA = WAGE",
        
        # 번외: 정상적인 수식 (비교용)
        "log((CPI.t(-1)/KRW.t(-1)).ma(4))"
    ]
    
    print("사용자 방정식 작성 오류 시뮬레이션 시작...\n")
    
    fail_count = 0
    for scenario in scenarios:
        is_valid = verify_expression(scenario)
        if not is_valid:
            fail_count += 1
            
    print(f"총 {len(scenarios)}개의 시나리오 중 {fail_count}개의 에러를 정확히 식별했습니다.")


if __name__ == "__main__":
    run_error_scenarios()
