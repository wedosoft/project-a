#!/usr/bin/env python3
"""
벡터 DB 및 요약 시스템 테스트 스크립트

1. 벡터 DB 컬렉션 자동 생성 테스트
2. 지식베이스 요약 언어 문제 테스트
"""

import asyncio
import logging
import os
import sys

# 프로젝트 루트 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.llm.optimized_summarizer import generate_optimized_summary
from core.database.vectordb import QdrantAdapter

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_knowledge_base_summary_korean():
    """지식베이스 한국어 요약 테스트"""
    
    logger.info("=== 지식베이스 한국어 요약 테스트 ===")
    
    kb_content = """
    고객 계정 비밀번호 재설정 가이드
    
    이 문서는 고객이 비밀번호를 잊어버렸을 때 재설정하는 방법을 설명합니다.
    
    절차:
    1. 로그인 페이지에서 "비밀번호 찾기" 클릭
    2. 등록된 이메일 주소 입력
    3. 이메일로 전송된 재설정 링크 클릭
    4. 새로운 비밀번호 입력 (8자 이상, 특수문자 포함)
    5. 새 비밀번호로 로그인 확인
    
    기술 요구사항:
    - HTTPS 연결 필수
    - 재설정 링크 유효시간: 30분
    - 비밀번호 정책: 최소 8자, 대소문자, 숫자, 특수문자 각 1개 이상
    """
    
    try:
        summary = await generate_optimized_summary(
            content=kb_content,
            content_type="knowledge_base",
            subject="비밀번호 재설정 가이드",
            ui_language="ko"
        )
        
        logger.info("✅ 지식베이스 요약 생성 성공")
        logger.info("=== 생성된 요약 ===")
        print(summary)
        
        # 언어 확인
        if "문서 목적" in summary or "처리 절차" in summary:
            logger.info("✅ 한국어 요약 확인됨")
            return True
        else:
            logger.warning("⚠️ 한국어 요약이 아닐 수 있음")
            return False
            
    except Exception as e:
        logger.error(f"❌ 지식베이스 요약 실패: {e}")
        return False


async def test_knowledge_base_summary_english():
    """지식베이스 영어 요약 테스트"""
    
    logger.info("=== 지식베이스 영어 요약 테스트 ===")
    
    kb_content = """
    Customer Account Password Reset Guide
    
    This document explains how to reset a password when a customer forgets it.
    
    Procedure:
    1. Click "Forgot Password" on the login page
    2. Enter registered email address
    3. Click the reset link sent via email
    4. Enter new password (8+ characters, include special characters)
    5. Confirm login with new password
    
    Technical Requirements:
    - HTTPS connection required
    - Reset link validity: 30 minutes
    - Password policy: Minimum 8 characters, uppercase, lowercase, numbers, special characters
    """
    
    try:
        summary = await generate_optimized_summary(
            content=kb_content,
            content_type="knowledge_base",
            subject="Password Reset Guide",
            ui_language="en"
        )
        
        logger.info("✅ 영어 지식베이스 요약 생성 성공")
        logger.info("=== 생성된 요약 ===")
        print(summary)
        
        # 언어 확인
        if "Document Purpose" in summary or "Procedures" in summary:
            logger.info("✅ 영어 요약 확인됨")
            return True
        else:
            logger.warning("⚠️ 영어 요약이 아닐 수 있음")
            return False
            
    except Exception as e:
        logger.error(f"❌ 영어 지식베이스 요약 실패: {e}")
        return False


def test_vector_db_collection_recovery():
    """벡터 DB 컬렉션 복구 테스트"""
    
    logger.info("=== 벡터 DB 컬렉션 자동 생성 테스트 ===")
    
    try:
        # QdrantAdapter 초기화
        adapter = QdrantAdapter()
        
        # 테스트용 임시 컬렉션명 사용
        original_collection = adapter.collection_name
        adapter.collection_name = "test_auto_create"
        
        # 컬렉션이 존재하는지 확인
        try:
            collections = adapter.client.get_collections()
            collection_exists = any(col.name == adapter.collection_name for col in collections.collections)
            
            if collection_exists:
                logger.info(f"테스트 컬렉션 '{adapter.collection_name}' 삭제 중...")
                adapter.client.delete_collection(adapter.collection_name)
                logger.info("테스트 컬렉션 삭제 완료")
        except Exception as e:
            logger.info(f"컬렉션 삭제 중 오류 (무시): {e}")
        
        # 테스트 데이터
        test_texts = ["테스트 문서 1", "테스트 문서 2"]
        test_embeddings = [[0.1, 0.2, 0.3] * 512, [0.4, 0.5, 0.6] * 512]  # 1536 차원
        test_metadatas = [
            {
                "company_id": "test_company",
                "platform": "test_platform", 
                "doc_type": "ticket",
                "original_id": "test_1"
            },
            {
                "company_id": "test_company",
                "platform": "test_platform",
                "doc_type": "ticket", 
                "original_id": "test_2"
            }
        ]
        test_ids = ["test_1", "test_2"]
        
        # 문서 추가 시도 (컬렉션이 없으므로 자동 생성되어야 함)
        logger.info("존재하지 않는 컬렉션에 문서 추가 시도...")
        success = adapter.add_documents(
            texts=test_texts,
            embeddings=test_embeddings,
            metadatas=test_metadatas,
            ids=test_ids
        )
        
        if success:
            logger.info("✅ 컬렉션 자동 생성 및 문서 추가 성공")
            
            # 정리: 테스트 컬렉션 삭제
            try:
                adapter.client.delete_collection(adapter.collection_name)
                logger.info("테스트 컬렉션 정리 완료")
            except:
                pass
            
            # 원래 컬렉션명 복구
            adapter.collection_name = original_collection
            return True
        else:
            logger.error("❌ 컬렉션 자동 생성 실패")
            adapter.collection_name = original_collection
            return False
            
    except Exception as e:
        logger.error(f"❌ 벡터 DB 테스트 실패: {e}")
        return False


async def main():
    """메인 테스트 실행"""
    
    logger.info("🚀 벡터 DB 및 요약 시스템 테스트 시작")
    
    results = []
    
    # 1. 지식베이스 한국어 요약 테스트
    results.append(await test_knowledge_base_summary_korean())
    
    # 2. 지식베이스 영어 요약 테스트  
    results.append(await test_knowledge_base_summary_english())
    
    # 3. 벡터 DB 컬렉션 자동 생성 테스트
    results.append(test_vector_db_collection_recovery())
    
    # 결과 요약
    logger.info("\n" + "="*50)
    logger.info("🎯 테스트 결과 요약")
    logger.info("="*50)
    
    test_names = [
        "지식베이스 한국어 요약",
        "지식베이스 영어 요약", 
        "벡터 DB 컬렉션 자동 생성"
    ]
    
    passed = 0
    for i, (name, result) in enumerate(zip(test_names, results)):
        status = "✅ 통과" if result else "❌ 실패"
        logger.info(f"{i+1}. {name}: {status}")
        if result:
            passed += 1
    
    logger.info(f"\n총 {passed}/{len(results)}개 테스트 통과")
    
    if passed == len(results):
        logger.info("🎉 모든 테스트 통과! 시스템이 정상적으로 작동합니다.")
        return True
    else:
        logger.warning("⚠️ 일부 테스트 실패. 시스템 설정을 확인해주세요.")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
