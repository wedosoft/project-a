#!/usr/bin/env python3
"""
데이터베이스 상태 진단 스크립트

데이터 수집 후 실제 저장된 데이터를 확인합니다.
"""

import os
import sys
import sqlite3
import logging

# 백엔드 경로 추가
sys.path.append('/Users/alan/GitHub/project-a/backend')

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def check_database_status():
    """데이터베이스 상태 확인"""
    
    logger.info("🔍 데이터베이스 상태 진단 시작")
    
    # 데이터베이스 파일 경로들
    db_paths = [
        "/Users/alan/GitHub/project-a/backend/core/data/wedosoft_data.db",
        "/Users/alan/GitHub/project-a/backend/data/wedosoft_freshdesk_data.db",
        "/Users/alan/GitHub/project-a/backend/core/data/wedosoft_freshdesk_data.db"
    ]
    
    found_dbs = []
    
    # 1. 데이터베이스 파일 존재 확인
    logger.info("\n📁 데이터베이스 파일 확인:")
    for db_path in db_paths:
        if os.path.exists(db_path):
            size = os.path.getsize(db_path)
            logger.info(f"   ✅ 발견: {db_path} (크기: {size:,} bytes)")
            found_dbs.append(db_path)
        else:
            logger.info(f"   ❌ 없음: {db_path}")
    
    if not found_dbs:
        logger.error("❌ 데이터베이스 파일을 찾을 수 없습니다!")
        return False
    
    # 2. 각 데이터베이스 내용 확인
    for db_path in found_dbs:
        logger.info(f"\n🔍 데이터베이스 분석: {db_path}")
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # 테이블 목록 확인
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            logger.info(f"   📋 테이블 목록: {[table[0] for table in tables]}")
            
            # 각 테이블 레코드 수 확인
            for table in tables:
                table_name = table[0]
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                    count = cursor.fetchone()[0]
                    logger.info(f"   📊 {table_name}: {count}개 레코드")
                    
                    # integrated_objects 테이블 상세 확인
                    if table_name == 'integrated_objects' and count > 0:
                        cursor.execute(f"SELECT original_id, tenant_id, object_type, created_at FROM {table_name} LIMIT 5")
                        rows = cursor.fetchall()
                        logger.info(f"   🔍 {table_name} 샘플 데이터:")
                        for row in rows:
                            logger.info(f"      - ID: {row[0]}, Tenant: {row[1]}, Type: {row[2]}, Created: {row[3]}")
                    
                    # progress_logs 테이블 상세 확인
                    if table_name == 'progress_logs' and count > 0:
                        cursor.execute(f"SELECT message, percentage, created_at FROM {table_name} ORDER BY created_at DESC LIMIT 10")
                        rows = cursor.fetchall()
                        logger.info(f"   📈 최근 진행상황 로그:")
                        for row in rows:
                            logger.info(f"      - {row[0]} ({row[1]}%) - {row[2]}")
                    
                except Exception as e:
                    logger.warning(f"   ⚠️ {table_name} 테이블 조회 오류: {e}")
            
            conn.close()
            
        except Exception as e:
            logger.error(f"   ❌ 데이터베이스 연결 오류: {e}")
    
    # 3. ORM 방식으로도 확인
    logger.info("\n🔧 ORM 방식으로 데이터 확인:")
    try:
        from core.database.manager import get_db_manager
        from core.repositories.integrated_object_repository import IntegratedObjectRepository
        
        db_manager = get_db_manager(tenant_id="wedosoft")
        logger.info(f"   🔗 ORM DB 매니저: {db_manager.database_url}")
        
        with db_manager.get_session() as session:
            repo = IntegratedObjectRepository(session)
            
            # 모든 통합 객체 조회
            objects = repo.get_by_company(tenant_id="wedosoft")
            logger.info(f"   📊 ORM으로 조회한 통합 객체: {len(objects)}개")
            
            for obj in objects[:5]:  # 최대 5개만 표시
                logger.info(f"      - ID: {obj.original_id}, Type: {obj.object_type}, Created: {obj.created_at}")
                
    except Exception as e:
        logger.error(f"   ❌ ORM 조회 오류: {e}")
    
    # 4. 환경변수 확인
    logger.info("\n⚙️ 환경변수 확인:")
    logger.info(f"   USE_ORM: {os.getenv('USE_ORM')}")
    logger.info(f"   TENANT_ID: {os.getenv('TENANT_ID')}")
    logger.info(f"   LOG_LEVEL: {os.getenv('LOG_LEVEL')}")
    
    return True

if __name__ == "__main__":
    success = check_database_status()
    if success:
        print("\n✅ 데이터베이스 상태 진단 완료!")
    else:
        print("\n❌ 데이터베이스 상태 진단 실패!")
    
    sys.exit(0 if success else 1)
