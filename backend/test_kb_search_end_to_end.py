#!/usr/bin/env python3
"""
KB 검색 및 doc_type 스키마 테스트 스크립트

/init 엔드포인트에서 유사티켓/지식베이스 벡터 검색이 
최신 doc_type 스키마(ticket/article)로 정상 동작하는지 end-to-end 테스트합니다.
"""

import asyncio
import json
import logging
import os
import sys
import time
from typing import Dict, Any, List

# 백엔드 경로 추가
sys.path.append('/Users/alan/GitHub/project-a/backend')

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_vectordb_doc_type_filtering():
    """벡터DB의 doc_type 필터링이 올바르게 작동하는지 테스트"""
    try:
        from core.database.vectordb import QdrantAdapter
        from core.search.retriever import retrieve_top_k_docs
        
        # 벡터DB 초기화
        vector_db = QdrantAdapter()
        
        # 테스트 쿼리 임베딩 (간단한 예시)
        test_query = "고객 문의 처리 방법"
        
        logger.info("=== 벡터DB doc_type 필터링 테스트 시작 ===")
        
        # 1. 티켓 검색 (doc_type="ticket")
        logger.info("1. 티켓 검색 테스트 (doc_type='ticket')")
        try:
            # 임베딩 생성을 위해 search optimizer 사용
            from core.search.optimizer import VectorSearchOptimizer
            search_optimizer = VectorSearchOptimizer()
            query_embedding = await search_optimizer.generate_embedding(test_query)
            
            ticket_results = retrieve_top_k_docs(
                query_embedding=query_embedding,
                top_k=3,
                doc_type="ticket",
                tenant_id="test_tenant"
            )
            
            logger.info(f"티켓 검색 결과: {len(ticket_results.get('ids', []))}개")
            if ticket_results.get('metadatas'):
                for i, metadata in enumerate(ticket_results['metadatas'][:2]):
                    logger.info(f"  티켓 {i+1}: doc_type={metadata.get('doc_type', 'N/A')}, source_type={metadata.get('source_type', 'N/A')}")
                    
        except Exception as e:
            logger.error(f"티켓 검색 테스트 실패: {e}")
        
        # 2. 지식베이스 검색 (doc_type="article")
        logger.info("2. 지식베이스 검색 테스트 (doc_type='article')")
        try:
            article_results = retrieve_top_k_docs(
                query_embedding=query_embedding,
                top_k=3,
                doc_type="article",
                tenant_id="test_tenant"
            )
            
            logger.info(f"지식베이스 검색 결과: {len(article_results.get('ids', []))}개")
            if article_results.get('metadatas'):
                for i, metadata in enumerate(article_results['metadatas'][:2]):
                    logger.info(f"  지식베이스 {i+1}: doc_type={metadata.get('doc_type', 'N/A')}, type={metadata.get('type', 'N/A')}")
                    
        except Exception as e:
            logger.error(f"지식베이스 검색 테스트 실패: {e}")
        
        # 3. 레거시 "kb" 검색 테스트 (하위 호환성)
        logger.info("3. 레거시 KB 검색 테스트 (doc_type='kb')")
        try:
            kb_results = retrieve_top_k_docs(
                query_embedding=query_embedding,
                top_k=3,
                doc_type="kb",
                tenant_id="test_tenant"
            )
            
            logger.info(f"레거시 KB 검색 결과: {len(kb_results.get('ids', []))}개")
            if kb_results.get('metadatas'):
                for i, metadata in enumerate(kb_results['metadatas'][:2]):
                    logger.info(f"  레거시 KB {i+1}: doc_type={metadata.get('doc_type', 'N/A')}, type={metadata.get('type', 'N/A')}")
                    
        except Exception as e:
            logger.error(f"레거시 KB 검색 테스트 실패: {e}")
            
        logger.info("=== 벡터DB doc_type 필터링 테스트 완료 ===")
        
    except Exception as e:
        logger.error(f"벡터DB 테스트 전체 실패: {e}")
        return False
    
    return True

async def test_search_chain_integration():
    """SearchChain과 통합 검색의 doc_type 사용 테스트"""
    try:
        logger.info("=== SearchChain 통합 테스트 시작 ===")
        
        from core.llm.integrations.langchain.chains.search_chain import SearchChain
        from core.llm.manager import LLMManager
        
        # SearchChain 초기화
        llm_manager = LLMManager()
        search_chain = SearchChain(llm_manager)
        
        # 테스트 티켓 데이터
        test_ticket = {
            "id": "12345",
            "subject": "결제 오류 문의",
            "description_text": "결제 처리 중 오류가 발생했습니다. 도움이 필요합니다.",
            "metadata": {"priority": "high"}
        }
        
        # 유사 티켓 검색 테스트
        logger.info("1. SearchChain을 통한 유사 티켓 검색 테스트")
        try:
            similar_tickets = await search_chain.run(
                ticket_data=test_ticket,
                tenant_id="test_tenant",
                top_k=3
            )
            
            logger.info(f"SearchChain 유사 티켓 검색 결과: {len(similar_tickets)}개")
            for i, ticket in enumerate(similar_tickets[:2]):
                logger.info(f"  유사 티켓 {i+1}: ID={ticket.get('id')}, 제목={ticket.get('title', '')[:50]}...")
                
        except Exception as e:
            logger.error(f"SearchChain 유사 티켓 검색 실패: {e}")
        
        logger.info("=== SearchChain 통합 테스트 완료 ===")
        
    except Exception as e:
        logger.error(f"SearchChain 테스트 전체 실패: {e}")
        return False
        
    return True

async def test_init_endpoint_simulation():
    """실제 /init 엔드포인트 로직을 시뮬레이션하여 KB 검색 테스트"""
    try:
        logger.info("=== /init 엔드포인트 시뮬레이션 테스트 시작 ===")
        
        from core.llm.integrations.langchain.chains import execute_init_parallel_chain
        from core.llm.manager import LLMManager
        from core.database.vectordb import QdrantAdapter
        
        # 의존성 초기화
        llm_manager = LLMManager()
        vector_db = QdrantAdapter()
        
        # 테스트 티켓 데이터
        test_ticket = {
            "id": "test_12345",
            "subject": "시스템 로그인 문제",
            "description": "사용자가 시스템에 로그인할 수 없는 문제 발생",
            "conversations": [
                {"body_text": "로그인 시도 시 오류 메시지가 표시됩니다.", "created_at": time.time()}
            ],
            "metadata": {
                "priority": "medium",
                "status": "open",
                "requester_email": "test@example.com"
            }
        }
        
        # InitChain 병렬 실행 테스트
        logger.info("1. InitChain 병렬 처리 실행")
        try:
            chain_results = await execute_init_parallel_chain(
                ticket_data=test_ticket,
                qdrant_client=vector_db.client,
                tenant_id="test_tenant",
                llm_router=llm_manager,
                include_summary=False,  # 요약은 제외하고 검색만 테스트
                include_similar_tickets=True,
                include_kb_docs=True,
                top_k_tickets=3,
                top_k_kb=3
            )
            
            logger.info("InitChain 실행 완료")
            logger.info(f"체인 결과 키: {list(chain_results.keys()) if chain_results else 'None'}")
            
            # 통합 검색 결과 분석
            if chain_results and 'unified_search' in chain_results:
                unified_result = chain_results['unified_search']
                
                if unified_result and unified_result.get('success'):
                    similar_tickets = unified_result.get('similar_tickets', [])
                    kb_documents = unified_result.get('kb_documents', [])
                    
                    logger.info(f"유사 티켓 검색 결과: {len(similar_tickets)}개")
                    for i, ticket in enumerate(similar_tickets[:2]):
                        logger.info(f"  유사 티켓 {i+1}: ID={ticket.get('id')}, 제목={ticket.get('title', '')[:50]}...")
                    
                    logger.info(f"지식베이스 검색 결과: {len(kb_documents)}개")
                    for i, doc in enumerate(kb_documents[:2]):
                        logger.info(f"  지식베이스 문서 {i+1}: ID={doc.get('id')}, 제목={doc.get('title', '')[:50]}...")
                        
                else:
                    logger.warning(f"통합 검색 실패: {unified_result.get('error') if unified_result else 'unified_result is None'}")
            else:
                logger.warning("통합 검색 결과가 없습니다.")
                
        except Exception as e:
            logger.error(f"InitChain 실행 실패: {e}")
            import traceback
            logger.error(f"상세 오류:\n{traceback.format_exc()}")
        
        logger.info("=== /init 엔드포인트 시뮬레이션 테스트 완료 ===")
        
    except Exception as e:
        logger.error(f"/init 시뮬레이션 테스트 전체 실패: {e}")
        return False
        
    return True

async def main():
    """메인 테스트 실행"""
    logger.info("KB 검색 및 doc_type 스키마 End-to-End 테스트 시작")
    
    # 환경 변수 확인
    required_env_vars = ["QDRANT_API_KEY", "OPENAI_API_KEY"]
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    if missing_vars:
        logger.error(f"필수 환경 변수가 없습니다: {missing_vars}")
        return
    
    test_results = []
    
    # 1. 벡터DB doc_type 필터링 테스트
    logger.info("\n" + "="*60)
    result1 = await test_vectordb_doc_type_filtering()
    test_results.append(("벡터DB doc_type 필터링", result1))
    
    # 2. SearchChain 통합 테스트
    logger.info("\n" + "="*60)
    result2 = await test_search_chain_integration()
    test_results.append(("SearchChain 통합", result2))
    
    # 3. /init 엔드포인트 시뮬레이션 테스트
    logger.info("\n" + "="*60)
    result3 = await test_init_endpoint_simulation()
    test_results.append(("/init 엔드포인트 시뮬레이션", result3))
    
    # 결과 요약
    logger.info("\n" + "="*60)
    logger.info("테스트 결과 요약:")
    for test_name, result in test_results:
        status = "✅ 성공" if result else "❌ 실패"
        logger.info(f"  {test_name}: {status}")
    
    all_passed = all(result for _, result in test_results)
    if all_passed:
        logger.info("🎉 모든 테스트 통과!")
    else:
        logger.warning("⚠️ 일부 테스트 실패")
    
    return all_passed

if __name__ == "__main__":
    asyncio.run(main())
