#!/usr/bin/env python3
"""
개선된 요약 테스트
"""

import asyncio
import sys
sys.path.append('.')
from core.llm.summarizer import generate_summary

async def test_improved_summary():
    test_content = '''제목: 마크애니 co.kr계정 복구요청

설명: 금일 오전 당사에서 markany.co.kr 계정에 대한 계정중 ikkim@markany.co.kr 계정이 삭제되었습니다. 백업후 삭제한다는것이 그냥 삭제가되었습니다. 계정 복구 부탁드립니다.

대화: 안녕하세요 이대영 차장 님, 위두소프트 고객 지원팀입니다. 요청하신 김인규(ikkim@markany.co.kr) 계정에 대해서 복구처리 해드렸습니다. markany.co.kr 계정은 무료 계정이기에 저희 콘솔에서 접근할 수 없어 부득이하게 일전 제공해주신 비밀번호로 로그인하여 처리하였음을 말씀드립니다. 확인하시고 상이한 점은 회신 주시기 바랍니다.

대화: 처리 감사드립니다 잘확인했습니다.'''
    
    print('🔍 개선된 요약 테스트 시작...')
    summary = await generate_summary(
        content=test_content,
        content_type='ticket',
        subject='마크애니 co.kr계정 복구요청'
    )
    print('\n📋 개선된 요약 결과:')
    print('=' * 50)
    print(summary)
    print('=' * 50)

if __name__ == "__main__":
    asyncio.run(test_improved_summary())
