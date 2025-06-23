#!/usr/bin/env python3
"""
데이터베이스 파일 생성 디버깅 스크립트
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from pathlib import Path
from core.database.database import get_database
import logging

# 로깅 설정
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def debug_database_creation():
    """데이터베이스 생성 디버깅"""
    
    print("🔍 데이터베이스 생성 디버깅 시작")
    print("=" * 50)
    
    company_id = "wedosoft"
    platform = "freshdesk"
    
    try:
        print(f"📋 테스트 파라미터: company_id={company_id}, platform={platform}")
        
        # 데이터베이스 인스턴스 생성
        db = get_database(company_id, platform)
        
        print(f"✅ 데이터베이스 인스턴스 생성됨")
        print(f"📁 예상 파일 경로: {db.db_path}")
        print(f"📂 디렉토리 존재 여부: {db.db_path.parent.exists()}")
        print(f"📄 파일 존재 여부 (연결 전): {db.db_path.exists()}")
        
        # 연결 시도
        print("\n🔗 데이터베이스 연결 시도...")
        db.connect()
        
        print(f"✅ 데이터베이스 연결 완료")
        print(f"📄 파일 존재 여부 (연결 후): {db.db_path.exists()}")
        
        if db.db_path.exists():
            file_size = db.db_path.stat().st_size
            print(f"📊 파일 크기: {file_size:,} bytes")
        
        # 테이블 확인
        cursor = db.connection.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        table_names = [table[0] for table in tables]
        print(f"📊 생성된 테이블: {table_names}")
        
        # 간단한 데이터 삽입
        cursor.execute("""
            INSERT OR IGNORE INTO tickets (original_id, company_id, platform, subject, status, created_at)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
        """, (f"debug-test-001", company_id, platform, f"디버그 테스트 티켓", "open"))
        
        db.connection.commit()
        
        # 데이터 확인
        cursor.execute("SELECT COUNT(*) FROM tickets WHERE company_id = ?", (company_id,))
        count = cursor.fetchone()[0]
        print(f"✅ 테스트 데이터 삽입 완료: {count}건")
        
        db.disconnect()
        
        # 최종 파일 상태 확인
        print(f"\n📄 최종 파일 존재 여부: {db.db_path.exists()}")
        if db.db_path.exists():
            final_size = db.db_path.stat().st_size
            print(f"📊 최종 파일 크기: {final_size:,} bytes")
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 50)
    print("📁 현재 data 디렉토리 내용:")
    data_dir = Path("/Users/alan/GitHub/project-a/backend/core/data")
    if data_dir.exists():
        for item in data_dir.iterdir():
            if item.is_file():
                size = item.stat().st_size
                print(f"  📄 {item.name} ({size:,} bytes)")
            else:
                print(f"  📂 {item.name}/")
    else:
        print("❌ 데이터 디렉토리가 존재하지 않습니다")

if __name__ == "__main__":
    debug_database_creation()
