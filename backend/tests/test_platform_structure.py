# -*- coding: utf-8 -*-
"""
Freshdesk 플랫폼 구조 테스트 스크립트

Freshdesk 전용 아키텍처가 올바르게 작동하는지 확인합니다.
"""

import asyncio
import logging
import os
from pathlib import Path
import sys

# backend 디렉토리를 Python 경로에 추가
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from core.platforms.factory import PlatformFactory
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_platform_factory():
    """플랫폼 팩토리 테스트 (Freshdesk 전용)"""
    logger.info("=== Freshdesk 플랫폼 팩토리 테스트 시작 ===")
    
    # 1. 지원 플랫폼 목록 확인 (Freshdesk만 지원)
    supported_platforms = PlatformFactory.get_supported_platforms()
    logger.info(f"지원 플랫폼: {supported_platforms}")
    
    # 2. Freshdesk 어댑터 테스트
    try:
        config = {
            "domain": os.getenv("FRESHDESK_DOMAIN", "test.freshdesk.com"),
            "api_key": os.getenv("FRESHDESK_API_KEY", "test_key"),
            "company_id": os.getenv("COMPANY_ID", "test_company")
        }
        
        freshdesk_adapter = PlatformFactory.create_adapter("freshdesk", config)
        logger.info(f"Freshdesk 어댑터 생성 성공: {freshdesk_adapter.get_platform_name()}")
        
    except Exception as e:
        logger.error(f"Freshdesk 어댑터 생성 실패: {e}")
    
    # 3. 지원하지 않는 플랫폼 테스트 (Zendesk 등)
    try:
        invalid_adapter = PlatformFactory.create_adapter("zendesk", {})
        logger.error("Zendesk 플랫폼이 생성되었습니다 (버그 - Freshdesk 전용이어야 함)")
    except ValueError as e:
        logger.info(f"비지원 플랫폼 정상 거부: {e}")
    
    logger.info("=== Freshdesk 플랫폼 팩토리 테스트 완료 ===")


async def test_freshdesk_collector():
    """Freshdesk 수집기 테스트"""
    logger.info("=== Freshdesk 수집기 테스트 시작 ===")
    
    try:
        from core.platforms.freshdesk.collector import FreshdeskCollector
        
        config = {
            "domain": os.getenv("FRESHDESK_DOMAIN", "test.freshdesk.com"),
            "api_key": os.getenv("FRESHDESK_API_KEY", "test_key"),
            "company_id": os.getenv("COMPANY_ID", "test_company")
        }
        
        collector = FreshdeskCollector(config, "test_output")
        logger.info(f"Freshdesk 수집기 생성 성공: {collector.company_id}")
        
        # async context manager 테스트 (실제 API 호출은 하지 않음)
        # async with collector as c:
        #     logger.info("Freshdesk 수집기 async context 성공")
        
    except Exception as e:
        logger.error(f"Freshdesk 수집기 테스트 실패: {e}")
    
    logger.info("=== Freshdesk 수집기 테스트 완료 ===")


async def main():
    """메인 테스트 함수"""
    logger.info("Freshdesk 전용 플랫폼 구조 테스트 시작")
    
    await test_platform_factory()
    await test_freshdesk_collector()
    
    logger.info("Freshdesk 전용 플랫폼 구조 테스트 완료")


if __name__ == "__main__":
    asyncio.run(main())
