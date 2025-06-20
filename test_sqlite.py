#!/usr/bin/env python3
"""
SQLite 데이터베이스 테스트 스크립트

database.py의 기능을 테스트하고 실제 데이터 저장이 동작하는지 확인합니다.
"""

import os
import sys
from pathlib import Path

# 백엔드 경로 추가
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

from datetime import datetime

from core.database import SQLiteDatabase


def test_sqlite_database():
    """SQLite 데이터베이스 기본 기능 테스트"""
    
    print("🔍 SQLite 데이터베이스 테스트 시작...")
    
    # 테스트용 데이터베이스 생성
    db = SQLiteDatabase("test_database.db")
    db.connect()
    db.create_tables()
    
    # 테스트 데이터
    test_company_id = "wedosoft"
    
    # 1. 티켓 데이터 저장 테스트
    test_ticket = {
        'id': 12345,
        'company_id': test_company_id,
        'platform': 'freshdesk',
        'subject': '테스트 티켓',
        'description': '이것은 테스트용 티켓입니다.',
        'status': 'open',
        'priority': 'medium',
        'created_at': datetime.now().isoformat()
    }
    
    try:
        ticket_id = db.insert_ticket(test_ticket)
        print(f"✅ 티켓 저장 성공: ID {ticket_id}")
    except Exception as e:
        print(f"❌ 티켓 저장 실패: {e}")
        return False
    
    # 2. 지식베이스 문서 저장 테스트
    test_article = {
        'id': 67890,
        'company_id': test_company_id,
        'platform': 'freshdesk',
        'title': '테스트 KB 문서',
        'description': '이것은 테스트용 지식베이스 문서입니다.',
        'status': 'published',
        'created_at': datetime.now().isoformat()
    }
    
    try:
        article_id = db.insert_article(test_article)
        print(f"✅ 지식베이스 문서 저장 성공: ID {article_id}")
    except Exception as e:
        print(f"❌ 지식베이스 문서 저장 실패: {e}")
        return False
    
    # 3. 수집 작업 로그 테스트
    test_job = {
        'job_id': 'test_job_001',
        'company_id': test_company_id,
        'job_type': 'ingest',
        'status': 'completed',
        'start_time': datetime.now().isoformat(),
        'end_time': datetime.now().isoformat(),
        'tickets_collected': 1,
        'articles_collected': 1,
        'errors_count': 0
    }
    
    try:
        log_id = db.log_collection_job(test_job)
        print(f"✅ 작업 로그 저장 성공: ID {log_id}")
    except Exception as e:
        print(f"❌ 작업 로그 저장 실패: {e}")
        return False
    
    # 4. 통계 조회 테스트
    try:
        stats = db.get_collection_stats(test_company_id)
        print(f"✅ 통계 조회 성공: {stats}")
    except Exception as e:
        print(f"❌ 통계 조회 실패: {e}")
        return False
    
    # 정리
    db.disconnect()
    
    # 테스트 파일 삭제
    test_db_path = Path(backend_path) / "data" / "test_database.db"
    if test_db_path.exists():
        test_db_path.unlink()
        print("🧹 테스트 데이터베이스 파일 삭제 완료")
    
    print("✅ 모든 SQLite 데이터베이스 테스트 통과!")
    return True

if __name__ == "__main__":
    success = test_sqlite_database()
    sys.exit(0 if success else 1)
