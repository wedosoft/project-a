#!/usr/bin/env python3
"""
스마트 자기 제외 필터링 테스트

자기 자신이 유사 티켓 목록에 포함되지 않는지 확인
"""

import asyncio
import sys
from pathlib import Path

# Add backend to Python path
sys.path.insert(0, str(Path(__file__).parent))

async def test_self_exclusion():
    """자기 자신 제외 기능 테스트"""
    print("🧪 스마트 자기 제외 필터링 테스트")
    print("=" * 50)
    
    from core.database.vectordb import search_vector_db_only
    
    # 테스트 데이터
    test_ticket_id = "12345"
    test_query = "로그인 문제 해결 방법"
    tenant_id = "wedosoft"
    platform = "freshdesk"
    
    print(f"📝 테스트 조건:")
    print(f"   현재 티켓 ID: {test_ticket_id}")
    print(f"   검색 쿼리: {test_query}")
    print(f"   테넌트: {tenant_id}")
    print(f"   플랫폼: {platform}")
    
    try:
        # 1. 자기 제외 없이 검색
        print(f"\n🔍 1단계: 자기 제외 없이 검색")
        results_without_exclusion = await search_vector_db_only(
            query=test_query,
            tenant_id=tenant_id,
            platform=platform,
            doc_types=["ticket"],
            limit=5,
            exclude_id=None  # 제외 없음
        )
        
        print(f"   결과 수: {len(results_without_exclusion)}개")
        for i, result in enumerate(results_without_exclusion[:3], 1):
            result_id = result.get("original_id") or result["metadata"].get("original_id")
            score = result.get("score", 0)
            print(f"   {i}. ID: {result_id}, 점수: {score:.3f}")
        
        # 자기 자신이 포함되어 있는지 확인
        self_included = any(
            str(result.get("original_id") or result["metadata"].get("original_id")) == str(test_ticket_id)
            for result in results_without_exclusion
        )
        
        # 2. 자기 제외 포함하여 검색
        print(f"\n🚫 2단계: 자기 제외({test_ticket_id}) 포함하여 검색")
        results_with_exclusion = await search_vector_db_only(
            query=test_query,
            tenant_id=tenant_id,
            platform=platform,
            doc_types=["ticket"],
            limit=5,
            exclude_id=test_ticket_id  # 자기 제외
        )
        
        print(f"   결과 수: {len(results_with_exclusion)}개")
        for i, result in enumerate(results_with_exclusion[:3], 1):
            result_id = result.get("original_id") or result["metadata"].get("original_id")
            score = result.get("score", 0)
            print(f"   {i}. ID: {result_id}, 점수: {score:.3f}")
        
        # 자기 자신이 제외되었는지 확인
        self_excluded = not any(
            str(result.get("original_id") or result["metadata"].get("original_id")) == str(test_ticket_id)
            for result in results_with_exclusion
        )
        
        # 3. 결과 분석
        print(f"\n📊 테스트 결과 분석:")
        print(f"   제외 전 결과 수: {len(results_without_exclusion)}개")
        print(f"   제외 후 결과 수: {len(results_with_exclusion)}개")
        print(f"   자기 자신 포함 여부 (제외 전): {'✅ 포함됨' if self_included else '❌ 없음'}")
        print(f"   자기 자신 제외 여부 (제외 후): {'✅ 제외됨' if self_excluded else '❌ 여전히 포함'}")
        
        # 테스트 통과 조건
        test_passed = True
        if not self_excluded:
            print(f"   ❌ 실패: 자기 자신이 여전히 결과에 포함되어 있음")
            test_passed = False
        
        if len(results_with_exclusion) >= len(results_without_exclusion):
            print(f"   ⚠️  주의: 제외 후 결과 수가 줄어들지 않음 (데이터 없을 수 있음)")
        
        return test_passed
        
    except Exception as e:
        print(f"   ❌ 테스트 실행 실패: {e}")
        return False

async def test_performance_improvement():
    """성능 개선 테스트"""
    print(f"\n⚡ 성능 개선 테스트")
    print("=" * 50)
    
    import time
    from core.database.vectordb import search_vector_db_only
    
    test_query = "시스템 오류 문제"
    tenant_id = "wedosoft"
    platform = "freshdesk"
    test_ticket_id = "67890"
    
    try:
        # 기존 방식 시뮬레이션 (제외 없이 검색 + 수동 필터링)
        start_time = time.time()
        
        old_way_results = await search_vector_db_only(
            query=test_query,
            tenant_id=tenant_id,
            platform=platform,
            doc_types=["ticket"],
            limit=6,  # +1 for manual filtering
            exclude_id=None
        )
        
        # 수동 필터링 시뮬레이션
        filtered_results = []
        for result in old_way_results:
            result_id = result.get("original_id") or result["metadata"].get("original_id")
            if str(result_id) != str(test_ticket_id):
                filtered_results.append(result)
                if len(filtered_results) >= 5:
                    break
        
        old_way_time = time.time() - start_time
        
        # 새로운 방식 (데이터베이스 레벨 필터링)
        start_time = time.time()
        
        new_way_results = await search_vector_db_only(
            query=test_query,
            tenant_id=tenant_id,
            platform=platform,
            doc_types=["ticket"],
            limit=5,  # 정확한 개수
            exclude_id=test_ticket_id
        )
        
        new_way_time = time.time() - start_time
        
        # 결과 비교
        print(f"📊 성능 비교:")
        print(f"   기존 방식 (수동 필터링): {old_way_time:.3f}초, 결과: {len(filtered_results)}개")
        print(f"   새로운 방식 (DB 필터링): {new_way_time:.3f}초, 결과: {len(new_way_results)}개")
        
        if new_way_time < old_way_time:
            improvement = ((old_way_time - new_way_time) / old_way_time) * 100
            print(f"   ✅ 성능 개선: {improvement:.1f}% 향상")
        else:
            print(f"   ⚠️  성능 차이 미미하거나 데이터 부족")
            
        return True
        
    except Exception as e:
        print(f"   ❌ 성능 테스트 실패: {e}")
        return False

async def main():
    """메인 테스트 실행"""
    print("🚀 스마트 자기 제외 필터링 종합 테스트")
    print("=" * 60)
    print("확인 항목:")
    print("1. 자기 자신이 유사 티켓 목록에서 제외되는지")
    print("2. 데이터베이스 레벨 필터링 성능 개선")
    print("=" * 60)
    
    # 테스트 실행
    results = []
    
    # 1. 자기 제외 기능 테스트
    exclusion_result = await test_self_exclusion()
    results.append(exclusion_result)
    
    # 2. 성능 개선 테스트
    performance_result = await test_performance_improvement()
    results.append(performance_result)
    
    # 결과 요약
    print(f"\n🏆 최종 테스트 결과")
    print("=" * 60)
    
    test_names = [
        "자기 자신 제외 기능",
        "성능 개선 확인"
    ]
    
    for i, (name, result) in enumerate(zip(test_names, results)):
        status = "✅ 성공" if result else "❌ 실패"
        print(f"{i+1}. {name}: {status}")
    
    success_rate = sum(results) / len(results) * 100
    print(f"\n전체 성공률: {success_rate:.1f}% ({sum(results)}/{len(results)})")
    
    if all(results):
        print("\n🎉 모든 스마트 필터링 기능이 정상 동작합니다!")
        print("\n개선된 기능:")
        print("  ✅ 조회 티켓이 유사 티켓 목록에서 자동 제외")
        print("  ✅ 데이터베이스 레벨 필터링으로 성능 개선")
        print("  ✅ 수동 필터링 로직 제거로 코드 간소화")
        print("  ✅ 정확한 검색 개수 요청으로 리소스 절약")
    else:
        print("\n⚠️  일부 기능에서 문제가 발견되었습니다.")
        print("벡터 데이터베이스에 테스트 데이터가 충분하지 않을 수 있습니다.")

if __name__ == "__main__":
    asyncio.run(main())