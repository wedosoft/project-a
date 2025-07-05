#!/usr/bin/env python3
"""
간단한 에이전트 수집 테스트 - 데이터베이스 저장까지 확인
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# 프로젝트 루트를 Python path에 추가
backend_root = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_root))

from dotenv import load_dotenv
from core.platforms.freshdesk.adapter import FreshdeskAdapter
from core.database.manager import DatabaseManager
from core.database.models.base import Base
from core.database.models.company import Company
from core.database.models.agent import Agent
from core.repositories.agent_repository import AgentRepository

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def simple_test():
    """간단한 에이전트 수집 및 저장 테스트"""
    
    config = {
        "domain": os.getenv("FRESHDESK_DOMAIN"),
        "api_key": os.getenv("FRESHDESK_API_KEY"),
        "tenant_id": "wedosoft"
    }
    
    if not config["domain"] or not config["api_key"]:
        logger.error("환경변수 설정 필요")
        return
    
    # 1. 데이터베이스 설정
    database_url = "sqlite:///simple_test.db"
    db_manager = DatabaseManager(database_url)
    
    # 2. 테이블 생성
    Base.metadata.create_all(bind=db_manager.engine)
    logger.info("테이블 생성 완료")
    
    # 3. 테스트 회사 생성
    with db_manager.get_session() as session:
        company = Company(
            tenant_id="wedosoft",
            freshdesk_domain=config["domain"],
            company_name="Test Company",
            platform="freshdesk"
        )
        session.add(company)
        session.commit()
        company_id = company.id
        logger.info(f"회사 생성 완료: ID={company_id}")
    
    # 4. 에이전트 데이터 수집
    async with FreshdeskAdapter(config) as adapter:
        agents = await adapter.fetch_agents()
        logger.info(f"에이전트 수집 완료: {len(agents)}개")
        
        if agents:
            logger.info(f"첫 번째 에이전트: {agents[0]}")
    
    # 5. 에이전트 데이터베이스 저장
    with db_manager.get_session() as session:
        agent_repo = AgentRepository(session)
        saved_agents = agent_repo.bulk_upsert_agents(agents, company_id)
        logger.info(f"에이전트 저장 완료: {len(saved_agents)}개")
    
    # 6. 저장된 데이터 확인
    with db_manager.get_session() as session:
        saved_count = session.query(Agent).count()
        logger.info(f"데이터베이스에 저장된 에이전트 수: {saved_count}")
        
        first_agent = session.query(Agent).first()
        if first_agent:
            logger.info(f"첫 번째 저장된 에이전트: ID={first_agent.id}, 이름={first_agent.name}, 이메일={first_agent.email}")

if __name__ == "__main__":
    asyncio.run(simple_test())