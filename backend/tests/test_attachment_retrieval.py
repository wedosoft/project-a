#!/usr/bin/env python
"""
이미지 첨부파일 검색 테스트 스크립트

이 스크립트는 Qdrant에서 검색 결과에 이미지 첨부파일 정보가 올바르게 포함되는지 테스트합니다.
"""

import os
import sys
import logging
import random

# 현재 디렉토리를 모듈 검색 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 필요한 모듈 임포트
from core import vectordb
from core.vectordb import vector_db

# 로깅 설정
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def test_image_attachments():
    """벡터 DB 검색 결과에 첨부파일 정보가 포함되는지 확인합니다."""
    try:
        # 임의의 쿼리 임베딩 생성
        dummy_embedding = [random.random() for _ in range(1536)]
        
        # 검색 수행
        DEFAULT_COMPANY_ID = "default"
        results = vector_db.search(
            query_embedding=dummy_embedding,
            top_k=5,  # 더 많은 결과를 가져와 첨부파일이 있는 문서를 찾을 확률을 높입니다
            company_id=DEFAULT_COMPANY_ID
        )
        
        # 결과 출력 및 첨부파일 정보 확인
        if results and "documents" in results and len(results["documents"]) > 0:
            logger.info(f"검색 결과: {len(results['documents'])}개 문서 찾음")
            
            attachments_found = False
            for i, meta in enumerate(results["metadatas"]):
                # "attachments" 키로 첨부파일 정보 확인
                attachments = meta.get("attachments")
                if attachments:
                    logger.info(f"결과 #{i+1}에서 첨부파일 정보를 찾았습니다!")
                    
                    if isinstance(attachments, str):
                        logger.info(f"  첨부파일 정보(문자열): {attachments[:100]}...")
                    elif isinstance(attachments, list):
                        logger.info(f"  첨부파일 개수: {len(attachments)}")
                        for j, attachment in enumerate(attachments[:3]):  # 최대 3개만 출력
                            logger.info(f"  첨부파일 #{j+1}:")
                            logger.info(f"    이름: {attachment.get('name', 'N/A')}")
                            logger.info(f"    URL: {attachment.get('url', 'N/A')}")
                            logger.info(f"    타입: {attachment.get('content_type', 'N/A')}")
                    
                    attachments_found = True
            
            if not attachments_found:
                logger.warning("검색 결과에 첨부파일 정보가 없습니다.")
            
            return attachments_found
        else:
            logger.warning("검색 결과가 없습니다.")
            return False
            
    except Exception as e:
        logger.error(f"첨부파일 검색 테스트 중 오류 발생: {e}")
        return False

if __name__ == "__main__":
    logger.info("이미지 첨부파일 검색 테스트 시작")
    
    if test_image_attachments():
        logger.info("테스트 성공: 첨부파일 정보를 검색 결과에서 찾았습니다.")
    else:
        logger.warning("테스트 불완전: 검색 결과에서 첨부파일 정보를 찾지 못했습니다. 데이터에 첨부파일이 없을 수 있습니다.")
    
    logger.info("테스트 완료")