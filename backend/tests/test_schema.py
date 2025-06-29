#!/usr/bin/env python3
"""
데이터베이스 스키마 테스트 - 최신 컬럼명(tenant_id, tenant_metadata) 확인
"""

import sys
import os
import sqlite3
import json

# 백엔드 모듈 경로 추가
sys.path.insert(0, '/Users/alan/GitHub/project-a/backend')

# PostgreSQL 의존성 없이 직접 SQLiteDatabase import
from core.database.database import SQLiteDatabase

def test_schema():
    print("🔍 데이터베이스 스키마 테스트 시작...")
    
    # 테스트용 데이터베이스 생성
    test_tenant_id = "test_tenant"
    db = SQLiteDatabase(tenant_id=test_tenant_id)
    
    try:
        # 데이터베이스 연결 및 테이블 생성
        db.connect()
        print(f"✅ 데이터베이스 생성 완료: {db.db_path}")
        
        # 테이블 스키마 확인
        cursor = db.connection.cursor()
        
        # integrated_objects 테이블 스키마 확인
        cursor.execute("PRAGMA table_info(integrated_objects)")
        columns = cursor.fetchall()
        
        print("\n📊 integrated_objects 테이블 컬럼 정보:")
        for col in columns:
            cid, name, type_, notnull, default, pk = col
            print(f"  - {name}: {type_} (pk={pk}, notnull={notnull}, default={default})")
        
        # 필수 컬럼 확인
        column_names = [col[1] for col in columns]
        
        required_columns = ['tenant_id', 'tenant_metadata']
        legacy_columns = ['company_id', 'metadata']
        
        print("\n✅ 최신 컬럼명 확인:")
        for col in required_columns:
            if col in column_names:
                print(f"  ✅ {col}: 존재")
            else:
                print(f"  ❌ {col}: 누락")
        
        print("\n🚫 레거시 컬럼명 확인:")
        for col in legacy_columns:
            if col in column_names:
                print(f"  ❌ {col}: 아직 존재 (제거 필요)")
            else:
                print(f"  ✅ {col}: 제거됨")
        
        # 샘플 데이터 삽입 테스트
        print("\n📝 샘플 데이터 삽입 테스트...")
        
        sample_ticket = {
            'id': 12345,
            'tenant_id': test_tenant_id,
            'platform': 'freshdesk',
            'subject': 'Test Ticket',
            'description': 'This is a test ticket',
            'status': 2,
            'priority': 1,
            'created_at': '2024-01-01T00:00:00Z'
        }
        
        result = db.insert_ticket(sample_ticket)
        print(f"  ✅ 티켓 삽입 완료: ID={result}")
        
        # 데이터 조회 테스트
        tickets = db.get_tickets(test_tenant_id)
        print(f"  ✅ 티켓 조회 완료: {len(tickets)}개")
        
        if tickets:
            print(f"  📋 첫 번째 티켓: {tickets[0]['subject']}")
        
        print("\n🎉 스키마 테스트 완료!")
        
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.disconnect()
        # 테스트 데이터베이스 파일 삭제
        if os.path.exists(db.db_path):
            os.remove(db.db_path)
            print(f"🗑️ 테스트 데이터베이스 삭제: {db.db_path}")

if __name__ == "__main__":
    test_schema()
