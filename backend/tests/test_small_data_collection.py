#!/usr/bin/env python3
"""
소량 데이터 수집 및 통합 객체 파이프라인 테스트 스크립트
- 3~5개 티켓만 수집하여 통합 객체 생성
- SQLite 저장 및 결과 확인
- 기존 코드 90% 재활용
"""

import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path

# 프로젝트 경로 설정
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "backend"))

import sqlite3

from backend.core.ingest import (
    create_integrated_ticket_object,
    store_integrated_object_to_sqlite,
)
from backend.freshdesk.fetcher import fetch_tickets
from backend.core.database import get_database
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

async def test_small_data_collection():
    """소량 데이터 수집 및 통합 객체 테스트"""
    print("🧪 소량 데이터 수집 및 통합 객체 파이프라인 테스트 시작")
    print("=" * 60)
    
    # 1. 환경 설정 확인
    freshdesk_domain = os.getenv("FRESHDESK_DOMAIN")
    freshdesk_api_key = os.getenv("FRESHDESK_API_KEY")
    
    if not freshdesk_domain or not freshdesk_api_key:
        print("❌ 환경 변수 누락: FRESHDESK_DOMAIN 또는 FRESHDESK_API_KEY")
        return
    
    # company_id 자동 추출
    company_id = freshdesk_domain.split('.')[0]
    print(f"🏢 Company ID: {company_id}")
    print(f"🌐 Freshdesk Domain: {freshdesk_domain}")
    print()
    
    # 2. 테스트 데이터베이스 초기화
    test_db_path = "test_small_data_collection.db"
    print(f"📊 테스트 데이터베이스 초기화: {test_db_path}")
    
    # 기존 테스트 DB 삭제 (클린 테스트)
    if os.path.exists(test_db_path):
        os.remove(test_db_path)
        print("🗑️ 기존 테스트 DB 삭제됨")
    
    # 테스트 데이터베이스 연결 확인 (SQLiteDatabase 인스턴스 직접 생성)
    from backend.core.database import SQLiteDatabase
    test_db = SQLiteDatabase(test_db_path)
    test_db.connect()
    test_db.create_tables()
    print("✅ 테스트 데이터베이스 초기화 완료")
    print()
    
    # 3. 소량 티켓 데이터 수집 (최대 5개)
    print("🎯 소량 티켓 데이터 수집 시작 (최대 5개)")
    try:
        # 기존 fetch_tickets 함수 사용 (per_page=5로 제한)
        tickets = await fetch_tickets(
            domain=freshdesk_domain,
            api_key=freshdesk_api_key,
            per_page=5,  # 최대 5개만 수집
            max_tickets=5  # 최대 5개 제한
        )
        
        print(f"✅ 수집된 티켓 수: {len(tickets)}")
        
        if not tickets:
            print("⚠️ 수집된 티켓이 없습니다.")
            return
            
        # 첫 번째 티켓 정보 출력
        first_ticket = tickets[0]
        print(f"📋 첫 번째 티켓 정보:")
        print(f"   - ID: {first_ticket.get('id')}")
        print(f"   - Subject: {first_ticket.get('subject', 'N/A')[:50]}...")
        print(f"   - Status: {first_ticket.get('status')}")
        print()
        
    except Exception as e:
        print(f"❌ 티켓 수집 중 오류: {e}")
        return
    
    # 4. 통합 객체 생성 및 저장 테스트
    print("🔄 통합 객체 생성 및 저장 테스트")
    success_count = 0
    
    for i, ticket in enumerate(tickets, 1):
        print(f"📝 티켓 {i}/{len(tickets)} 처리 중...")
        
        try:
            # 통합 객체 생성 (기존 함수 재활용)
            integrated_object = create_integrated_ticket_object(
                ticket=ticket
            )
            
            # SQLite 저장 (기존 함수 재활용)
            store_integrated_object_to_sqlite(
                db=test_db,
                integrated_object=integrated_object,
                company_id=company_id,
                platform="freshdesk"
            )
            
            success_count += 1
            print(f"   ✅ 티켓 ID {ticket.get('id')} 통합 객체 저장 완료")
            
        except Exception as e:
            print(f"   ❌ 티켓 ID {ticket.get('id')} 처리 오류: {e}")
    
    print()
    print(f"🎯 통합 객체 생성 및 저장 완료: {success_count}/{len(tickets)} 성공")
    print()
    
    # 5. 저장된 데이터 검증
    print("🔍 저장된 데이터 검증")
    try:
        conn = sqlite3.connect(test_db_path)
        cursor = conn.cursor()
        
        # 저장된 레코드 수 확인
        cursor.execute("SELECT COUNT(*) FROM integrated_objects")
        record_count = cursor.fetchone()[0]
        print(f"📊 저장된 통합 객체 수: {record_count}")
        
        # 샘플 데이터 조회
        cursor.execute("""
            SELECT id, company_id, platform, ticket_id, created_at 
            FROM integrated_objects 
            LIMIT 3
        """)
        
        sample_records = cursor.fetchall()
        print(f"📋 샘플 레코드 (상위 3개):")
        for record in sample_records:
            print(f"   - ID: {record[0]}, Company: {record[1]}, Platform: {record[2]}, Ticket: {record[3]}, Created: {record[4]}")
        
        # 통합 객체 데이터 구조 확인
        cursor.execute("SELECT integrated_data FROM integrated_objects LIMIT 1")
        sample_data = cursor.fetchone()
        
        if sample_data:
            import json
            integrated_data = json.loads(sample_data[0])
            print(f"🔍 통합 객체 구조 확인:")
            print(f"   - Keys: {list(integrated_data.keys())}")
            print(f"   - Ticket ID: {integrated_data.get('ticket_id')}")
            print(f"   - Subject: {integrated_data.get('subject', 'N/A')[:50]}...")
            print(f"   - Conversations: {len(integrated_data.get('conversations', []))}")
            print(f"   - Attachments: {len(integrated_data.get('attachments', []))}")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ 데이터 검증 중 오류: {e}")
    
    print()
    print("=" * 60)
    print("🎉 소량 데이터 수집 및 통합 객체 파이프라인 테스트 완료!")
    print(f"📁 테스트 결과는 {test_db_path}에 저장되었습니다.")
    print()
    print("✅ 다음 단계 제안:")
    print("   1. 통합 객체 기반 LLM 요약 생성 테스트")
    print("   2. 임베딩 생성 및 벡터 저장 테스트")
    print("   3. 검색 및 추천 기능 테스트")
    print("   4. 성능 최적화 및 대량 데이터 처리 준비")

if __name__ == "__main__":
    asyncio.run(test_small_data_collection())
