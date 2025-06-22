#!/usr/bin/env python3
"""
저장 함수 수정 후 테스트
"""

import sys
import logging
from pathlib import Path

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    from core.database.database import SQLiteDatabase
    from core.ingest.storage import store_integrated_object_to_sqlite

    # 테스트용 데이터
    test_company_id = 'test_company'
    test_platform = 'freshdesk'

    print('=== 저장 함수 수정 후 테스트 시작 ===')

    # DB 초기화
    db = SQLiteDatabase(test_company_id, test_platform)
    db.connect()

    # 테스트용 통합 객체
    test_integrated_object = {
        'id': '12345',
        'object_type': 'integrated_ticket',
        'subject': 'Test Ticket',
        'description': 'This is a test ticket',
        'conversations': [],
        'all_attachments': []
    }

    print('1. 저장 함수 호출...')
    result = store_integrated_object_to_sqlite(
        db=db, 
        integrated_object=test_integrated_object, 
        company_id=test_company_id, 
        platform=test_platform
    )
    print(f'저장 결과: {result}')
    
    print('2. 저장된 데이터 확인...')
    cursor = db.connection.cursor()
    
    # integrated_objects 테이블 확인
    cursor.execute('SELECT COUNT(*) FROM integrated_objects WHERE company_id = ?', (test_company_id,))
    integrated_count = cursor.fetchone()[0]
    print(f'integrated_objects 테이블: {integrated_count}개')
    
    # tickets 테이블 확인
    cursor.execute('SELECT COUNT(*) FROM tickets WHERE company_id = ?', (test_company_id,))
    tickets_count = cursor.fetchone()[0]
    print(f'tickets 테이블: {tickets_count}개')
    
    if integrated_count > 0 and tickets_count > 0:
        print('✅ 저장 성공!')
    else:
        print('❌ 저장 실패')
        
        # 상세 확인
        cursor.execute('SELECT * FROM integrated_objects WHERE company_id = ?', (test_company_id,))
        rows = cursor.fetchall()
        print(f'integrated_objects 데이터: {rows}')
        
        cursor.execute('SELECT * FROM tickets WHERE company_id = ?', (test_company_id,))
        rows = cursor.fetchall()
        print(f'tickets 데이터: {rows}')

except Exception as e:
    print(f'❌ 오류 발생: {e}')
    import traceback
    traceback.print_exc()
finally:
    try:
        db.disconnect()
    except:
        pass

print('=== 테스트 완료 ===')
