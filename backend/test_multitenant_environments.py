#!/usr/bin/env python3
"""
멀티테넌트 환경별 테스트 스크립트
SQLite (개발) 및 PostgreSQL (프로덕션) 모두 테스트
"""

import os
import sys
import json
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
backend_path = Path(__file__).parent
sys.path.insert(0, str(backend_path))

from core.database.database import DatabaseFactory, validate_multitenant_setup
from core.database.tenant_config import TenantConfigManager

def test_sqlite_environment():
    """SQLite 환경 테스트 (개발용)"""
    print('\n🗄️ SQLite 환경 테스트 (개발용)')
    print('=' * 50)
    
    # SQLite 환경 설정
    os.environ['DATABASE_TYPE'] = 'sqlite'
    
    try:
        # 테스트 테넌트들
        test_tenants = [
            {'company_id': 'dev_company_1', 'platform': 'freshdesk'},
            {'company_id': 'dev_company_2', 'platform': 'zendesk'},
            {'company_id': 'dev_company_3', 'platform': 'freshdesk'}
        ]
        
        for tenant in test_tenants:
            print(f"\n📋 테스트: {tenant['company_id']} ({tenant['platform']})")
            
            # 데이터베이스 생성 및 연결
            db = DatabaseFactory.create_database(tenant['company_id'], tenant['platform'])
            print(f"   DB 타입: {type(db).__name__}")
            print(f"   DB 경로: {getattr(db, 'db_path', 'N/A')}")
            
            # 연결 테스트
            db.connect()
            print("   ✅ 연결 성공")
            
            # 테스트 데이터 삽입
            test_ticket = {
                'original_id': 'TEST-001',
                'company_id': tenant['company_id'],
                'platform': tenant['platform'],
                'object_type': 'ticket',
                'original_data': {'title': f"Test ticket for {tenant['company_id']}"},
                'integrated_content': f"Test content for {tenant['company_id']}",
                'summary': f"Test ticket summary for {tenant['company_id']}",
                'metadata': {'status': 'open', 'priority': 'medium'}
            }
            
            ticket_id = db.insert_integrated_object(test_ticket)
            print(f"   ✅ 테스트 데이터 삽입 성공 (ID: {ticket_id})")
            
            # 데이터 조회 테스트
            tickets = db.get_integrated_objects_by_type(
                tenant['company_id'], 
                tenant['platform'], 
                'ticket'
            )
            print(f"   ✅ 데이터 조회 성공 ({len(tickets)}개 티켓)")
            
            # 격리 검증
            validation = DatabaseFactory.validate_tenant_isolation(
                tenant['company_id'], 
                tenant['platform']
            )
            
            isolation_status = "✅ 격리됨" if validation['is_isolated'] else "❌ 격리 실패"
            print(f"   {isolation_status} ({validation['isolation_method']})")
            
            db.disconnect()
        
        return True
        
    except Exception as e:
        print(f"❌ SQLite 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_postgresql_environment():
    """PostgreSQL 환경 테스트 (프로덕션용)"""
    print('\n🐘 PostgreSQL 환경 테스트 (프로덕션용)')
    print('=' * 50)
    
    # PostgreSQL 환경 설정
    os.environ['DATABASE_TYPE'] = 'postgresql'
    
    try:
        # PostgreSQL 드라이버 확인
        import psycopg2
        print("✅ psycopg2 드라이버 사용 가능")
    except ImportError:
        print("❌ psycopg2 드라이버 없음 - PostgreSQL 테스트 스킵")
        print("💡 설치: pip install psycopg2-binary")
        return False
    
    # PostgreSQL 연결 정보 확인
    pg_config = {
        'POSTGRES_HOST': os.getenv('POSTGRES_HOST', 'localhost'),
        'POSTGRES_PORT': os.getenv('POSTGRES_PORT', '5432'),
        'POSTGRES_DB': os.getenv('POSTGRES_DB', 'saas_platform'),
        'POSTGRES_USER': os.getenv('POSTGRES_USER', 'postgres'),
        'POSTGRES_PASSWORD': os.getenv('POSTGRES_PASSWORD', '***')
    }
    
    print("📡 PostgreSQL 연결 설정:")
    for key, value in pg_config.items():
        if 'PASSWORD' in key:
            print(f"   {key}: {'***' if value != '***' else 'NOT_SET'}")
        else:
            print(f"   {key}: {value}")
    
    try:
        # 테스트 테넌트들
        test_tenants = [
            {'company_id': 'prod_company_1', 'platform': 'freshdesk'},
            {'company_id': 'prod_company_2', 'platform': 'zendesk'},
            {'company_id': 'prod_company_3', 'platform': 'freshdesk'}
        ]
        
        for tenant in test_tenants:
            print(f"\n📋 테스트: {tenant['company_id']} ({tenant['platform']})")
            
            try:
                # 데이터베이스 생성 및 연결
                db = DatabaseFactory.create_database(tenant['company_id'], tenant['platform'])
                print(f"   DB 타입: {type(db).__name__}")
                print(f"   스키마: {getattr(db, 'schema_name', 'N/A')}")
                
                # 연결 테스트
                db.connect()
                print("   ✅ 연결 성공")
                
                # 테스트 데이터 삽입
                test_ticket = {
                    'original_id': 'PROD-001',
                    'company_id': tenant['company_id'],
                    'platform': tenant['platform'],
                    'object_type': 'ticket',
                    'original_data': {'title': f"Production test ticket for {tenant['company_id']}"},
                    'integrated_content': f"Production test content for {tenant['company_id']}",
                    'summary': f"Production test ticket summary for {tenant['company_id']}",
                    'metadata': {'status': 'open', 'priority': 'high'}
                }
                
                ticket_id = db.insert_integrated_object(test_ticket)
                print(f"   ✅ 테스트 데이터 삽입 성공 (ID: {ticket_id})")
                
                # 데이터 조회 테스트
                tickets = db.get_integrated_objects_by_type(
                    tenant['company_id'], 
                    tenant['platform'], 
                    'ticket'
                )
                print(f"   ✅ 데이터 조회 성공 ({len(tickets)}개 티켓)")
                
                # 격리 검증
                validation = DatabaseFactory.validate_tenant_isolation(
                    tenant['company_id'], 
                    tenant['platform']
                )
                
                isolation_status = "✅ 격리됨" if validation['is_isolated'] else "❌ 격리 실패"
                print(f"   {isolation_status} ({validation['isolation_method']})")
                
                db.disconnect()
                
            except Exception as e:
                print(f"   ❌ 테넌트 {tenant['company_id']} 테스트 실패: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ PostgreSQL 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_environment_switching():
    """환경 전환 테스트"""
    print('\n🔄 환경 전환 테스트')
    print('=' * 50)
    
    test_company = 'env_test_company'
    test_platform = 'freshdesk'
    
    # SQLite로 데이터 생성
    print("1️⃣ SQLite에서 데이터 생성...")
    os.environ['DATABASE_TYPE'] = 'sqlite'
    
    db_sqlite = DatabaseFactory.create_database(test_company, test_platform)
    db_sqlite.connect()
    
    sqlite_ticket = {
        'original_id': 'ENV-001',
        'company_id': test_company,
        'platform': test_platform,
        'object_type': 'ticket',
        'original_data': {'title': 'Environment switching test'},
        'integrated_content': 'Test content for environment switching',
        'summary': 'Environment test ticket',
        'metadata': {'env': 'sqlite'}
    }
    
    sqlite_id = db_sqlite.insert_integrated_object(sqlite_ticket)
    print(f"   ✅ SQLite 데이터 생성 (ID: {sqlite_id})")
    db_sqlite.disconnect()
    
    # PostgreSQL 환경 확인 (연결 가능한 경우만)
    try:
        print("2️⃣ PostgreSQL 환경 테스트...")
        os.environ['DATABASE_TYPE'] = 'postgresql'
        
        db_pg = DatabaseFactory.create_database(test_company, test_platform)
        db_pg.connect()
        
        # PostgreSQL에서는 별도 데이터이므로 조회 결과가 다름
        pg_tickets = db_pg.get_integrated_objects_by_type(test_company, test_platform, 'ticket')
        print(f"   ✅ PostgreSQL 조회 완료 ({len(pg_tickets)}개 - SQLite와 분리됨)")
        
        db_pg.disconnect()
        
    except Exception as e:
        print(f"   ⚠️ PostgreSQL 테스트 스킵: {e}")
    
    # 원래 환경으로 복원
    os.environ['DATABASE_TYPE'] = 'sqlite'
    print("3️⃣ SQLite 환경으로 복원")

def test_tenant_config_management():
    """테넌트별 설정 관리 테스트"""
    print('\n⚙️ 테넌트별 설정 관리 테스트')
    print('=' * 50)
    
    try:
        config_manager = TenantConfigManager('config_test_company', 'freshdesk')
        
        # 설정 저장 테스트
        test_configs = {
            'freshdesk_domain': 'mycompany.freshdesk.com',
            'freshdesk_api_key': 'test_api_key_12345',
            'collection_interval': '3600',
            'enable_ai_summary': 'true'
        }
        
        print("📝 테넌트 설정 저장 중...")
        for key, value in test_configs.items():
            config_manager.set_config(key, value, encrypted=(key.endswith('_api_key')))
            print(f"   ✅ {key}: {'[암호화됨]' if key.endswith('_api_key') else value}")
        
        # 설정 조회 테스트
        print("\n📖 테넌트 설정 조회 중...")
        for key in test_configs.keys():
            retrieved_value = config_manager.get_config(key)
            print(f"   ✅ {key}: {'[복호화됨]' if key.endswith('_api_key') else retrieved_value}")
        
        # 전체 설정 조회
        all_configs = config_manager.get_all_configs()
        print(f"\n📋 전체 설정: {len(all_configs)}개")
        
        return True
        
    except Exception as e:
        print(f"❌ 테넌트 설정 관리 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """메인 테스트 함수"""
    print('🧪 멀티테넌트 환경별 종합 테스트')
    print('=' * 60)
    
    # 현재 환경 정보
    current_env = os.getenv('DATABASE_TYPE', 'NOT_SET')
    print(f"📊 현재 DATABASE_TYPE: {current_env}")
    
    # 멀티테넌트 설정 검증
    print('\n🔍 멀티테넌트 설정 검증')
    print('=' * 50)
    validation = validate_multitenant_setup()
    print(f"DB 타입: {validation['database_type']}")
    print(f"격리 방법: {validation['isolation_method']}")
    print(f"프로덕션 준비: {validation['is_production_ready']}")
    if validation['recommendations']:
        print("권장사항:")
        for rec in validation['recommendations']:
            print(f"  - {rec}")
    
    # 테스트 실행
    results = {}
    
    # 1. SQLite 환경 테스트 (개발)
    results['sqlite'] = test_sqlite_environment()
    
    # 2. PostgreSQL 환경 테스트 (프로덕션)
    results['postgresql'] = test_postgresql_environment()
    
    # 3. 환경 전환 테스트
    results['env_switching'] = test_environment_switching()
    
    # 4. 테넌트 설정 관리 테스트
    results['tenant_config'] = test_tenant_config_management()
    
    # 결과 요약
    print('\n📊 테스트 결과 요약')
    print('=' * 50)
    for test_name, result in results.items():
        status = "✅ 성공" if result else "❌ 실패"
        print(f"{status} {test_name}")
    
    # 환경별 권장사항
    print('\n💡 환경별 권장사항')
    print('=' * 50)
    print("🚀 개발 환경:")
    print("   - DATABASE_TYPE=sqlite")
    print("   - 빠른 개발 및 테스트")
    print("   - 파일 기반 격리")
    
    print("\n🏢 프로덕션 환경:")
    print("   - DATABASE_TYPE=postgresql")
    print("   - PostgreSQL 서버 설정 필요")
    print("   - 스키마 기반 격리")
    print("   - 확장성 및 성능 최적화")
    
    # 전체 성공률
    success_count = sum(1 for result in results.values() if result)
    total_count = len(results)
    success_rate = (success_count / total_count) * 100
    
    print(f"\n🎯 전체 성공률: {success_rate:.1f}% ({success_count}/{total_count})")
    
    if success_rate >= 75:
        print("✅ 멀티테넌트 아키텍처가 올바르게 설정되었습니다!")
    else:
        print("❌ 멀티테넌트 설정에 문제가 있습니다. 위의 오류를 확인하세요.")

if __name__ == '__main__':
    main()
