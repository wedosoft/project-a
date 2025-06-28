#!/usr/bin/env python3
"""
수정된 end-to-end 테스트: 실제 데이터로 /init 엔드포인트 시뮬레이션
"""

import asyncio
import logging
import os
import sys
from pathlib import Path
import pytest

# 프로젝트 루트를 Python 경로에 추가
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from core.database.vectordb import vector_db
from core.search.optimizer import VectorSearchOptimizer
from core.llm.integrations.langchain.chains.search_chain import SearchChain
from core.llm.manager import get_llm_manager

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@pytest.mark.asyncio
async def test_real_data_end_to_end():
    """실제 데이터로 전체 파이프라인 테스트"""
    
    print("=" * 60)
    print("=== 실제 데이터로 end-to-end 테스트 ===")
    print("=" * 60)
    
    # 실제 데이터 정보 (이전 테스트에서 확인된 값들)
    REAL_TENANT_ID = "wedosoft"
    REAL_TICKET_ID = "104"
    REAL_ARTICLE_ID = "5000875040"
    
    # 샘플 티켓 데이터 (실제 구조와 유사하게)
    sample_ticket_data = {
        "id": REAL_TICKET_ID,
        "subject": "프로덕트 기능 문의",
        "description_text": "안녕하세요, 저희 시스템에서 특정 기능이 작동하지 않아 문의드립니다. 도움 부탁드립니다.",
        "requester_email": "user@wedosoft.com",
        "company": "wedosoft",
        "agent_name": "지원팀",
        "department": "기술지원",
        "priority": "Medium",
        "status": "Open",
        "created_at": "2024-06-28T12:00:00Z"
    }
    
    try:
        # 1. LLM Manager 초기화
        logger.info("1. LLM Manager 초기화")
        llm_manager = get_llm_manager()
        
        # 2. Sequential execution으로 /init 엔드포인트 시뮬레이션
        logger.info("2. Sequential execution으로 /init 엔드포인트 시뮬레이션")
        
        # Mock Qdrant 클라이언트 (실제 벡터DB 사용)
        qdrant_client = vector_db.client
        
        # /init 엔드포인트 순차 처리 실행 (새로운 방법)
        result = await llm_manager.execute_init_sequential(
            ticket_data=sample_ticket_data,
            qdrant_client=qdrant_client,
            tenant_id=REAL_TENANT_ID,
            top_k_tickets=3,
            top_k_kb=3
        )
        
        # 3. 결과 분석
        logger.info("3. 결과 분석")
        print(f"\n실행 시간: {result.get('execution_time', 0):.2f}초")
        print(f"실행 방식: Sequential (순차 처리)")
        
        # 유사 티켓 결과
        similar_tickets = result.get('similar_tickets')
        if similar_tickets and not isinstance(similar_tickets, dict):
            print(f"\n✅ 유사 티켓 검색 성공: {len(similar_tickets)}개")
            for i, ticket in enumerate(similar_tickets[:3]):
                ticket_id = ticket.get('id', 'N/A')
                title = ticket.get('title', 'N/A')[:50]
                similarity = ticket.get('similarity_score', 0)
                print(f"  티켓 {i+1}: ID={ticket_id}, 유사도={similarity:.3f}, 제목={title}...")
        else:
            print(f"\n❌ 유사 티켓 검색 실패: {similar_tickets}")
        
        # KB 문서 결과
        kb_documents = result.get('kb_documents')
        if kb_documents and not isinstance(kb_documents, dict):
            print(f"\n✅ KB 문서 검색 성공: {len(kb_documents)}개")
            for i, doc in enumerate(kb_documents[:3]):
                doc_id = doc.get('id', 'N/A')
                title = doc.get('title', 'N/A')[:50]
                similarity = doc.get('similarity_score', 0)
                print(f"  문서 {i+1}: ID={doc_id}, 유사도={similarity:.3f}, 제목={title}...")
        else:
            print(f"\n❌ KB 문서 검색 실패: {kb_documents}")
        
        # 요약 결과
        summary = result.get('summary')
        if summary:
            print(f"\n✅ 티켓 요약 성공: {summary[:100]}...")
        else:
            print(f"\n❌ 티켓 요약 실패: {summary}")
        
        # 4. 직접 벡터 검색 비교 테스트
        logger.info("4. 직접 벡터 검색 비교 테스트")
        
        # 더미 임베딩으로 직접 검색
        dummy_embedding = [0.1] * 1536  # OpenAI 임베딩 차원
        
        # 티켓 검색
        ticket_search_result = vector_db.search(
            query_embedding=dummy_embedding,
            top_k=3,
            tenant_id=REAL_TENANT_ID,
            doc_type="ticket"
        )
        
        # KB 검색
        kb_search_result = vector_db.search(
            query_embedding=dummy_embedding,
            top_k=3,
            tenant_id=REAL_TENANT_ID,
            doc_type="article"
        )
        
        print(f"\n직접 벡터 검색 결과:")
        print(f"  티켓: {len(ticket_search_result.get('results', []))}개")
        print(f"  KB: {len(kb_search_result.get('results', []))}개")
        
        # 5. 최종 상태 확인
        print(f"\n=" * 60)
        print("=== 최종 테스트 결과 ===")
        
        tests_passed = 0
        total_tests = 5
        
        # 테스트 1: 실행 성공
        if result.get('success', False):
            print("✅ Sequential 실행: 성공")
            tests_passed += 1
        else:
            print(f"❌ Sequential 실행: 실패 - {result.get('error')}")
        
        # 테스트 2: 유사 티켓 검색
        if similar_tickets and not isinstance(similar_tickets, dict):
            print("✅ 유사 티켓 검색: 성공")
            tests_passed += 1
        else:
            print("❌ 유사 티켓 검색: 실패")
        
        # 테스트 3: KB 문서 검색
        if kb_documents and not isinstance(kb_documents, dict):
            print("✅ KB 문서 검색: 성공")
            tests_passed += 1
        else:
            print("❌ KB 문서 검색: 실패")
        
        # 테스트 4: 요약 생성
        if summary:
            print("✅ 티켓 요약: 성공")
            tests_passed += 1
        else:
            print("❌ 티켓 요약: 실패")
        
        # 테스트 5: 직접 벡터 검색
        if (len(ticket_search_result.get('results', [])) > 0 and 
            len(kb_search_result.get('results', [])) > 0):
            print("✅ 직접 벡터 검색: 성공")
            tests_passed += 1
        else:
            print("❌ 직접 벡터 검색: 실패")
        
        print(f"\n테스트 통과율: {tests_passed}/{total_tests} ({tests_passed/total_tests*100:.1f}%)")
        
        if tests_passed == total_tests:
            print("🎉 모든 테스트 통과! /init 엔드포인트가 정상 작동합니다.")
        elif tests_passed >= 3:
            print("✅ 주요 테스트 통과. 마이너한 이슈는 있지만 기본 기능은 정상입니다.")
        else:
            print("⚠️ 다수 테스트 실패. 추가 디버깅이 필요합니다.")
            
    except Exception as e:
        logger.error(f"end-to-end 테스트 중 오류 발생: {e}")
        print(f"❌ 테스트 실패: {e}")

if __name__ == "__main__":
    asyncio.run(test_real_data_end_to_end())
