#!/usr/bin/env python3
"""
에이전트 수집 단독 테스트
"""

import asyncio
import json
import logging
import os
from pathlib import Path
from dotenv import load_dotenv

# 프로젝트 루트를 Python path에 추가
import sys
backend_root = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_root))

from core.platforms.freshdesk.collector import FreshdeskCollector
from core.database.manager import DatabaseManager
from core.database.models.company import Company
from core.database.models.base import Base

# .env 파일 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def setup_test_database(tenant_id: str, domain: str):
    """테스트용 데이터베이스 설정"""
    database_url = f"sqlite:///{tenant_id}_data.db"
    db_manager = DatabaseManager(database_url)
    
    # 테이블 생성
    Base.metadata.create_all(bind=db_manager.engine)
    
    # 테스트용 회사 데이터 생성
    with db_manager.get_session() as session:
        existing_company = session.query(Company).filter(Company.tenant_id == tenant_id).first()
        if not existing_company:
            test_company = Company(
                tenant_id=tenant_id,
                freshdesk_domain=domain,
                company_name=f"Test Company ({tenant_id})",
                platform="freshdesk"
            )
            session.add(test_company)
            session.commit()
            logger.info(f"테스트용 회사 생성: {test_company.company_name}")
        else:
            logger.info(f"기존 회사 사용: {existing_company.company_name}")

async def test_agent_collection():
    """에이전트 수집 테스트"""
    
    # 설정 정보
    config = {
        "domain": os.getenv("FRESHDESK_DOMAIN"),
        "api_key": os.getenv("FRESHDESK_API_KEY"),
        "tenant_id": os.getenv("TENANT_ID", "test_company"),
        "max_retries": 3,
        "per_page": 50,  # 테스트이므로 적은 수로
        "request_delay": 0.5
    }
    
    # 필수 설정 확인
    if not config["domain"] or not config["api_key"]:
        logger.error("FRESHDESK_DOMAIN과 FRESHDESK_API_KEY 환경변수가 필요합니다")
        return
    
    logger.info(f"에이전트 수집 테스트 시작")
    logger.info(f"도메인: {config['domain']}")
    logger.info(f"테넌트: {config['tenant_id']}")
    
    # 테스트용 데이터베이스 설정
    setup_test_database(config["tenant_id"], config["domain"])
    
    try:
        async with FreshdeskCollector(config, "agent_test_data") as collector:
            # 에이전트만 수집
            logger.info("=== 에이전트 데이터 수집 시작 ===")
            result = await collector.collect_agents()
            
            # 결과 출력
            logger.info("=== 수집 결과 ===")
            logger.info(f"수집된 에이전트 수: {result.get('total_agents', 0)}")
            logger.info(f"저장된 에이전트 수: {result.get('saved_agents', 0)}")
            logger.info(f"소요 시간: {result.get('duration_seconds', 0):.2f}초")
            
            # 상세 결과를 JSON으로 출력
            print("\n=== 상세 결과 ===")
            print(json.dumps(result, ensure_ascii=False, indent=2))
            
    except Exception as e:
        logger.error(f"에이전트 수집 테스트 실패: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(test_agent_collection())