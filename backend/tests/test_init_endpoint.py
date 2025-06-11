#!/usr/bin/env python3
"""
/init 엔드포인트 최종 통합 테스트
실시간 티켓 요약 + 벡터 검색 조합 검증
"""

import asyncio
import json
import time
from typing import Any, Dict

import httpx

# 테스트 설정
BASE_URL = "http://localhost:8000"
TEST_TICKET_ID = "123"  # 실제 티켓 ID로 변경 필요
TEST_COMPANY_ID = "pixeline"  # 실제 company_id로 변경 필요

async def test_init_endpoint():
    """
    /init 엔드포인트 최종 통합 테스트
    """
    print("🚀 /init 엔드포인트 최종 통합 테스트 시작")
    print(f"🎯 목표: 실시간 티켓 요약 + 벡터 검색 조합 검증")
    print(f"⏱️  속도 목표: 5초 이내 응답")
    print("-" * 60)
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            # 1. 헬스체크 먼저 확인
            print("1️⃣ 헬스체크 확인...")
            health_start = time.time()
            health_response = await client.get(f"{BASE_URL}/health")
            health_time = time.time() - health_start
            
            if health_response.status_code == 200:
                health_data = health_response.json()
                print(f"✅ 헬스체크 성공 ({health_time:.2f}초)")
                print(f"   - 전체 상태: {health_data.get('status')}")
                print(f"   - LLM Router: {health_data.get('services', {}).get('llm_router', {}).get('status')}")
                print(f"   - Vector DB: {health_data.get('services', {}).get('vector_db', {}).get('status')}")
            else:
                print(f"❌ 헬스체크 실패: {health_response.status_code}")
                return
                
            print()
            
            # 2. /init 엔드포인트 테스트
            print("2️⃣ /init 엔드포인트 테스트...")
            init_start = time.time()
            
            # 헤더 설정 (실제 Freshdesk 설정)
            headers = {
                "X-Freshdesk-Domain": TEST_COMPANY_ID,
                "X-Freshdesk-API-Key": "dummy-key-for-test",  # 실제 API 키로 변경 필요
                "Content-Type": "application/json"
            }
            
            # 쿼리 파라미터
            params = {
                "include_summary": True,
                "include_kb_docs": True, 
                "include_similar_tickets": True
            }
            
            print(f"   📋 요청 정보:")
            print(f"      - 티켓 ID: {TEST_TICKET_ID}")
            print(f"      - Company ID: {TEST_COMPANY_ID}")
            print(f"      - 실시간 요약: 활성화")
            print(f"      - 벡터 검색: 활성화 (유사 티켓 + KB 문서)")
            
            # API 호출
            init_response = await client.get(
                f"{BASE_URL}/init/{TEST_TICKET_ID}",
                headers=headers,
                params=params
            )
            
            init_time = time.time() - init_start
            
            # 3. 응답 분석
            print(f"\n3️⃣ 응답 분석:")
            print(f"   ⏱️  응답 시간: {init_time:.2f}초 {'✅' if init_time <= 5.0 else '⚠️'}")
            print(f"   📊 상태 코드: {init_response.status_code}")
            
            if init_response.status_code == 200:
                try:
                    response_data = init_response.json()
                    
                    # 응답 구조 분석
                    print(f"   📋 응답 구조:")
                    print(f"      - Context ID: {response_data.get('context_id')}")
                    print(f"      - 티켓 ID: {response_data.get('ticket_id')}")
                    
                    # 티켓 요약 확인
                    ticket_summary = response_data.get('ticket_summary')
                    if ticket_summary:
                        print(f"      ✅ 실시간 티켓 요약: 생성됨")
                        if isinstance(ticket_summary, dict):
                            summary_text = ticket_summary.get('ticket_summary', '')
                            print(f"         📝 요약 길이: {len(summary_text)}자")
                        elif isinstance(ticket_summary, str):
                            print(f"         📝 요약 길이: {len(ticket_summary)}자")
                    else:
                        print(f"      ❌ 실시간 티켓 요약: 누락")
                    
                    # 벡터 검색 결과 확인
                    similar_tickets = response_data.get('similar_tickets', [])
                    kb_documents = response_data.get('kb_documents', [])
                    
                    print(f"      🔍 벡터 검색 결과:")
                    print(f"         - 유사 티켓: {len(similar_tickets)}개 {'✅' if len(similar_tickets) > 0 else '⚠️'}")
                    print(f"         - KB 문서: {len(kb_documents)}개 {'✅' if len(kb_documents) > 0 else '⚠️'}")
                    
                    # 성능 메트릭 확인
                    metadata = response_data.get('metadata', {})
                    if metadata:
                        total_time = metadata.get('total_time', 0)
                        cache_hits = metadata.get('cache_hits', {})
                        print(f"      📈 성능 메트릭:")
                        print(f"         - 총 처리 시간: {total_time:.2f}초")
                        print(f"         - 캐시 히트: {cache_hits}")
                    
                    # 4. 결과 종합
                    print(f"\n4️⃣ 최종 결과:")
                    
                    success_criteria = {
                        "응답 시간 (≤5초)": init_time <= 5.0,
                        "실시간 요약 생성": ticket_summary is not None,
                        "벡터 검색 (유사 티켓)": len(similar_tickets) > 0,
                        "벡터 검색 (KB 문서)": len(kb_documents) > 0,
                        "API 응답 성공": init_response.status_code == 200
                    }
                    
                    passed = sum(success_criteria.values())
                    total = len(success_criteria)
                    
                    print(f"   📊 테스트 통과율: {passed}/{total} ({passed/total*100:.1f}%)")
                    for criterion, status in success_criteria.items():
                        status_icon = "✅" if status else "❌"
                        print(f"      {status_icon} {criterion}")
                    
                    if passed == total:
                        print(f"\n🎉 완벽! 모든 테스트 통과!")
                        print(f"   💡 실시간 티켓 요약 + 벡터 검색 조합이 정상 작동합니다.")
                        print(f"   ⚡ 속도 최우선 목표 달성: {init_time:.2f}초")
                    else:
                        print(f"\n⚠️  일부 테스트 실패, 추가 최적화 필요")
                        
                except json.JSONDecodeError as e:
                    print(f"   ❌ JSON 디코딩 실패: {e}")
                    print(f"   📝 응답 내용: {init_response.text[:500]}...")
                    
            else:
                print(f"   ❌ API 호출 실패")
                print(f"   📝 오류 내용: {init_response.text}")
                
        except Exception as e:
            print(f"❌ 테스트 실행 중 오류 발생: {e}")
            import traceback
            traceback.print_exc()

async def main():
    """메인 실행 함수"""
    print("=" * 60)
    print("🎯 PROJECT-A: LLM Router + 벡터 검색 최종 통합 테스트")
    print("=" * 60)
    
    await test_init_endpoint()
    
    print("\n" + "=" * 60)
    print("🏁 테스트 완료")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
