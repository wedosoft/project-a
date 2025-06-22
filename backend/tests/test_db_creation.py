#!/usr/bin/env python3
"""
데이터베이스 생성 테스트 스크립트

멀티테넌트 데이터베이스가 제대로 생성되는지 확인합니다.
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.database.database import get_database
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_database_creation():
    """데이터베이스 생성 테스트"""
    
    print("🧪 멀티테넌트 데이터베이스 생성 테스트 시작")
    print("=" * 50)
    
    # 테스트 회사들
    test_companies = [
        ("testcompany1", "freshdesk"),
        ("testcompany2", "freshdesk"),
        ("acme", "freshdesk")
    ]
    
    for company_id, platform in test_companies:
        try:
            print(f"\n📋 테스트 중: {company_id} ({platform})")
            
            # 데이터베이스 인스턴스 생성
            db = get_database(company_id, platform)
            print(f"✅ 데이터베이스 인스턴스 생성: {db.db_path}")
            
            # 연결 및 테이블 생성
            db.connect()
            print(f"✅ 데이터베이스 연결 완료")
            
            # 테이블 존재 확인
            cursor = db.connection.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            
            table_names = [table[0] for table in tables]
            print(f"📊 생성된 테이블: {table_names}")
            
            # 간단한 데이터 삽입 테스트
            cursor.execute("""
                INSERT OR IGNORE INTO tickets (original_id, company_id, platform, subject, status, created_at)
                VALUES (?, ?, ?, ?, ?, datetime('now'))
            """, (f"test-{company_id}-001", company_id, platform, f"테스트 티켓 - {company_id}", "open"))
            
            db.connection.commit()
            
            # 데이터 확인
            cursor.execute("SELECT COUNT(*) FROM tickets WHERE company_id = ?", (company_id,))
            count = cursor.fetchone()[0]
            print(f"✅ 테스트 데이터 삽입 완료: {count}건")
            
            db.disconnect()
            
        except Exception as e:
            print(f"❌ 오류 발생: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 50)
    print("🎯 테스트 결과 확인")
    
    # 생성된 데이터베이스 파일 확인
    data_dir = "/Users/alan/GitHub/project-a/backend/core/data"
    if os.path.exists(data_dir):
        db_files = [f for f in os.listdir(data_dir) if f.endswith('.db')]
        print(f"📁 생성된 데이터베이스 파일들:")
        for db_file in db_files:
            file_path = os.path.join(data_dir, db_file)
            file_size = os.path.getsize(file_path)
            print(f"  - {db_file} ({file_size:,} bytes)")
    else:
        print("❌ 데이터 디렉토리가 존재하지 않습니다")

if __name__ == "__main__":
    test_database_creation()
