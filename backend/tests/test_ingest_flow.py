#!/usr/bin/env python3
"""
ingest 파이프라인 테스트 스크립트
실제로 어디까지 진행되는지 확인
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# 백엔드 모듈 경로 추가
sys.path.insert(0, str(Path(__file__).parent))

# 로깅 설정
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger(__name__)

async def test_ingest_flow():
    """ingest 흐름 테스트"""
    logger.info("=== ingest 파이프라인 테스트 시작 ===")
    
    # 환경변수 설정 (테스트용)
    test_domain = os.getenv("DOMAIN", "wedosoft")
    test_api_key = os.getenv("API_KEY")
    
    if not test_api_key:
        logger.error("API_KEY 환경변수가 설정되지 않았습니다")
        return
    
    logger.info(f"테스트 도메인: {test_domain}")
    logger.info(f"API 키 존재: {'Yes' if test_api_key else 'No'}")
    
    try:
        from core.ingest.processor import ingest
        
        # 테스트 파라미터
        company_id = "wedosoft"
        platform = "freshdesk"
        
        logger.info(f"ingest 함수 호출 - company_id: {company_id}, platform: {platform}")
        
        # ingest 실행
        result = await ingest(
            company_id=company_id,
            platform=platform,
            incremental=True,
            purge=False,
            process_attachments=False,
            force_rebuild=False,
            local_data_dir=None,
            include_kb=True,
            domain=test_domain,
            api_key=test_api_key,
            max_tickets=5,  # 테스트용으로 적은 수
            max_articles=3
        )
        
        logger.info(f"=== ingest 결과 ===")
        logger.info(f"성공: {result.get('success')}")
        logger.info(f"메시지: {result.get('message')}")
        logger.info(f"처리된 티켓: {result.get('tickets_processed')}")
        logger.info(f"처리된 문서: {result.get('articles_processed')}")
        logger.info(f"소요시간: {result.get('duration_seconds'):.2f}초")
        
        if result.get('error'):
            logger.error(f"오류: {result['error']}")
            
    except Exception as e:
        logger.error(f"테스트 중 오류 발생: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(test_ingest_flow())
