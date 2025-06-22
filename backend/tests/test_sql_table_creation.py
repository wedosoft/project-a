#!/usr/bin/env python3
"""
SQLite 테이블 자동 생성 테스트 스크립트
"""

from core.database.database import SQLiteDatabase
import logging
import os

logging.basicConfig(level=logging.INFO)

def test_sql_table_creation():
    """SQL 테이블 자동 생성 테스트"""
    
    # 기존 테스트 DB 파일 삭제
    test_db_path = './core/data/test_data.db'
    if os.path.exists(test_db_path):
        os.remove(test_db_path)
        print(f'기존 테스트 DB 파일 삭제: {test_db_path}')

    # 테스트 데이터베이스 생성
    print('=== SQLite 테이블 자동 생성 테스트 ===')
    db = SQLiteDatabase('test')
    print(f'1. 데이터베이스 인스턴스 생성 완료: {db.db_path}')

    db.connect()
    print('2. 데이터베이스 연결 및 테이블 생성 완료')

    # 테이블 목록 확인
    cursor = db.connection.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    print(f'3. 생성된 테이블 목록: {[t[0] for t in tables]}')

    # 테스트 데이터 삽입
    test_ticket = {
        'original_id': 'test_001',
        'company_id': 'test_company',
        'platform': 'freshdesk',
        'subject': '테스트 티켓',
        'description': '테스트 내용입니다.',
        'status': 'open',
        'priority': 'medium',
        'created_at': '2024-01-01T10:00:00Z',
        'raw_data': '{"test": true}'
    }

    try:
        ticket_id = db.insert_ticket(test_ticket)
        print(f'4. 테스트 티켓 삽입 성공: ID={ticket_id}')
    except Exception as e:
        print(f'4. 테스트 티켓 삽입 실패: {e}')

    # 테스트 지식베이스 문서 삽입
    test_article = {
        'original_id': 'kb_test_001',
        'company_id': 'test_company',
        'platform': 'freshdesk',
        'title': '테스트 KB 문서',
        'description': '테스트 KB 내용입니다.',
        'status': 1,
        'created_at': '2024-01-01T10:00:00Z',
        'raw_data': '{"test_kb": true}'
    }

    try:
        article_id = db.insert_knowledge_base(test_article)
        print(f'5. 테스트 KB 문서 삽입 성공: ID={article_id}')
    except Exception as e:
        print(f'5. 테스트 KB 문서 삽입 실패: {e}')

    # 테스트 첨부파일 삽입
    test_attachment = {
        'original_id': 'att_test_001',
        'company_id': 'test_company',
        'platform': 'freshdesk',
        'parent_type': 'ticket',
        'parent_original_id': 'test_001',
        'name': 'test_file.txt',
        'content_type': 'text/plain',
        'size': 1024,
        'created_at': '2024-01-01T10:00:00Z',
        'raw_data': '{"test_attachment": true}'
    }

    try:
        attachment_id = db.insert_attachment(test_attachment)
        print(f'6. 테스트 첨부파일 삽입 성공: ID={attachment_id}')
    except Exception as e:
        print(f'6. 테스트 첨부파일 삽입 실패: {e}')

    # 수집 작업 로그 테스트
    test_log = {
        'job_id': 'test_job_001',
        'company_id': 'test_company',
        'job_type': 'ingest',
        'status': 'completed',
        'start_time': '2024-01-01T10:00:00Z',
        'end_time': '2024-01-01T10:05:00Z',
        'tickets_collected': 1,
        'articles_collected': 1,
        'attachments_collected': 1
    }

    try:
        db.log_collection_job(test_log)
        print(f'7. 테스트 수집 작업 로그 기록 성공')
    except Exception as e:
        print(f'7. 테스트 수집 작업 로그 기록 실패: {e}')

    # 통계 확인
    try:
        stats = db.get_data_stats('test_company', 'freshdesk')
        print(f'8. 데이터 통계: {stats}')
    except Exception as e:
        print(f'8. 데이터 통계 조회 실패: {e}')

    db.disconnect()
    print('9. 테스트 완료 ✅')


if __name__ == "__main__":
    test_sql_table_creation()
