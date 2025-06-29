#!/usr/bin/env python3
"""
간단한 요약 생성 테스트
"""

import os
import sys
import asyncio
import logging

# Add the backend directory to the Python path
sys.path.insert(0, '/Users/alan/GitHub/project-a/backend')

# Load environment variables first
from dotenv import load_dotenv
load_dotenv('/Users/alan/GitHub/project-a/backend/.env')

from core.llm.manager import LLMManager, get_llm_manager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_llm_manager():
    """LLMManager 기본 테스트"""
    try:
        logger.info("🧪 LLMManager 테스트 시작")
        
        # LLMManager 인스턴스 생성
        llm_manager = get_llm_manager()
        logger.info("✅ LLMManager 생성 완료")
        
        # 티켓 요약 테스트
        test_ticket_data = {
            'id': 'test-123',
            'subject': '웹사이트 로그인 문제',
            'description': '사용자가 로그인할 수 없다고 신고했습니다.',
            'status': 'open',
            'priority': 'high',
            'integrated_text': '고객이 로그인 페이지에서 비밀번호를 입력해도 로그인이 되지 않는다고 합니다.',
            'conversations': [],
            'attachments': []
        }
        
        logger.info("🎫 티켓 요약 테스트 중...")
        ticket_summary = await llm_manager.generate_ticket_summary(test_ticket_data)
        logger.info(f"✅ 티켓 요약 결과: {ticket_summary}")
        
        # KB 문서 요약 테스트
        test_kb_data = {
            'title': '비밀번호 재설정 방법',
            'content': '사용자가 비밀번호를 잊어버린 경우 다음 단계를 따라 재설정할 수 있습니다. 1. 로그인 페이지에서 비밀번호 찾기를 클릭합니다. 2. 이메일 주소를 입력합니다. 3. 이메일로 발송된 링크를 클릭합니다.'
        }
        
        logger.info("📚 KB 문서 요약 테스트 중...")
        kb_summary = await llm_manager.generate_knowledge_base_summary(test_kb_data)
        logger.info(f"✅ KB 요약 결과: {kb_summary}")
        
        logger.info("🎉 모든 테스트 완료!")
        
    except Exception as e:
        logger.error(f"❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_llm_manager())
