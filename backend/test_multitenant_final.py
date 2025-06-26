#!/usr/bin/env python3
"""멀티테넌트 데이터베이스 최종 검증"""

import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()

# 프로젝트 루트를 Python 경로에 추가
backend_path = Path(__file__).parent
sys.path.insert(0, str(backend_path))

from core.database.database import (
    get_database, 
    get_tenant_database,
    DatabaseFactory,
    TenantDataManager,
    validate_multitenant_setup
)
from core.database.tenant_config import TenantConfigManager

def test_multitenant_database_separation():
    """멀티테넌트 데이터베이스 분리 테스트"""
    print('🏢 멀티테넌트 데이터베이스 분리 테스트')
    print('=' * 60)
    
    # 여러 테넌트로 테스트
    test_tenants = [
        {'company_id': 'acme_corp', 'platform': 'freshdesk'},
        {'company_id': 'beta_company', 'platform': 'zendesk'},
        {'company_id': 'gamma_ltd', 'platform': 'freshdesk'},
        {'company_id': 'delta_inc', 'platform': 'servicenow'}
    ]
    
    tenant_data = {}
    
    for tenant in test_tenants:
        try:
            company_id = tenant['company_id']
            platform = tenant['platform']
            
            # 테넌트별 데이터베이스 연결
            db = get_tenant_database(company_id, platform)
            db.connect()
            
            # 테스트 데이터 삽입
            test_ticket = {
                'original_id': f'TICKET-{company_id.upper()}-001',
                'company_id': company_id,
                'platform': platform,
                'object_type': 'ticket',
                'original_data': {
                    'id': f'TICKET-{company_id.upper()}-001',
                    'subject': f'{company_id} 테스트 티켓',
                    'description': f'{company_id}의 고유 테스트 데이터입니다.',
                    'status': 'open',
                    'priority': 'high'
                },
                'integrated_content': f'{company_id}의 고유 테스트 데이터입니다.',
                'summary': f'{company_id} 테스트 티켓',
                'metadata': {
                    'status': 'open',
                    'priority': 'high',
                    'created_at': '2025-06-26T12:00:00Z'
                }
            }
            
            # 데이터 삽입
            ticket_id = db.insert_integrated_object(test_ticket)
            
            # 데이터 조회
            tickets = db.get_integrated_objects_by_type(company_id, platform, 'ticket')
            
            tenant_data[company_id] = {
                'platform': platform,
                'ticket_count': len(tickets),
                'db_type': type(db).__name__,
                'db_path': getattr(db, 'db_path', None),
                'schema_name': getattr(db, 'schema_name', None)
            }
            
            print(f'✅ {company_id} ({platform}):')
            print(f'   DB 타입: {type(db).__name__}')
            print(f'   티켓 수: {len(tickets)}')
            if hasattr(db, 'db_path'):
                print(f'   DB 파일: {db.db_path}')
            if hasattr(db, 'schema_name'):
                print(f'   스키마: {db.schema_name}')
            
            db.disconnect()
            
        except Exception as e:
            print(f'❌ {company_id} 테스트 실패: {e}')
            import traceback
            traceback.print_exc()
    
    return tenant_data

def test_tenant_isolation():
    """테넌트 격리 검증"""
    print('\n🔒 테넌트 격리 검증')
    print('=' * 60)
    
    # 서로 다른 테넌트에서 데이터 조회 시도
    company_a = 'isolation_test_a'
    company_b = 'isolation_test_b'
    platform = 'freshdesk'
    
    try:
        # Company A에 데이터 삽입
        db_a = get_tenant_database(company_a, platform)
        db_a.connect()
        
        test_data_a = {
            'original_id': 'SECRET-TICKET-A',
            'company_id': company_a,
            'platform': platform,
            'object_type': 'ticket',
            'original_data': {'secret': 'Company A 기밀 데이터'},
            'integrated_content': 'Company A 기밀 데이터',
            'summary': 'Company A 기밀 티켓',
            'metadata': {'confidential': True}
        }
        
        db_a.insert_integrated_object(test_data_a)
        tickets_a = db_a.get_integrated_objects_by_type(company_a, platform, 'ticket')
        print(f'✅ Company A: {len(tickets_a)}개 티켓 저장')
        db_a.disconnect()
        
        # Company B에서 Company A 데이터 조회 시도
        db_b = get_tenant_database(company_b, platform)
        db_b.connect()
        
        tickets_b_own = db_b.get_integrated_objects_by_type(company_b, platform, 'ticket')
        tickets_b_cross = db_b.get_integrated_objects_by_type(company_a, platform, 'ticket')
        
        print(f'✅ Company B: {len(tickets_b_own)}개 자체 티켓')
        print(f'🔍 Company B에서 Company A 데이터 조회: {len(tickets_b_cross)}개')
        
        if len(tickets_b_cross) == 0:
            print('✅ 테넌트 격리 성공: Company B에서 Company A 데이터에 접근할 수 없음')
        else:
            print('❌ 테넌트 격리 실패: 크로스 테넌트 데이터 접근 가능')
        
        db_b.disconnect()
        
    except Exception as e:
        print(f'❌ 격리 테스트 실패: {e}')

def test_tenant_config_management():
    """테넌트별 설정 관리 테스트"""
    print('\n⚙️ 테넌트별 설정 관리 테스트')
    print('=' * 60)
    
    try:
        # 테스트 테넌트별 설정
        test_configs = [
            {
                'company_id': 'config_test_1',
                'platform': 'freshdesk',
                'settings': {
                    'freshdesk_domain': 'config-test-1.freshdesk.com',
                    'freshdesk_api_key': 'test-api-key-1',
                    'ai_summary_enabled': True,
                    'max_attachments': 10
                }
            },
            {
                'company_id': 'config_test_2', 
                'platform': 'zendesk',
                'settings': {
                    'zendesk_domain': 'config-test-2.zendesk.com',
                    'zendesk_api_key': 'test-api-key-2',
                    'ai_summary_enabled': False,
                    'max_attachments': 5
                }
            }
        ]
        
        for config in test_configs:
            company_id = config['company_id']
            platform = config['platform']
            settings = config['settings']
            
            # 테넌트 설정 관리자 생성
            db = get_tenant_database(company_id, platform)
            config_manager = TenantConfigManager(db)
            
            # 설정 저장
            for key, value in settings.items():
                config_manager.set_tenant_setting(1, key, value, encrypted=(key == 'api_key'))
            
            # 설정 조회
            retrieved_settings = {}
            for key in settings.keys():
                retrieved_settings[key] = config_manager.get_tenant_setting(1, key)
            
            print(f'✅ {company_id} ({platform}):')
            for key, value in retrieved_settings.items():
                original_value = settings[key]
                status = '✅' if value == original_value else '❌'
                print(f'   {status} {key}: {value}')
        
    except Exception as e:
        print(f'❌ 테넌트 설정 관리 테스트 실패: {e}')
        import traceback
        traceback.print_exc()

def test_database_factory():
    """데이터베이스 팩토리 테스트"""
    print('\n🏭 데이터베이스 팩토리 테스트')
    print('=' * 60)
    
    try:
        # 현재 환경 확인
        db_type = os.getenv('DATABASE_TYPE', 'sqlite')
        print(f'현재 DATABASE_TYPE: {db_type}')
        
        # SQLite 강제 생성
        db_sqlite = DatabaseFactory.create_database('factory_test', 'freshdesk', 'sqlite')
        print(f'✅ SQLite DB 생성: {type(db_sqlite).__name__}')
        
        # PostgreSQL 시도 (실패해도 괜찮음)
        try:
            db_pg = DatabaseFactory.create_database('factory_test', 'freshdesk', 'postgresql')
            print(f'✅ PostgreSQL DB 생성: {type(db_pg).__name__}')
        except Exception as e:
            print(f'⚠️ PostgreSQL DB 생성 실패 (예상됨): {type(e).__name__}')
        
        # 자동 선택 테스트
        db_auto = DatabaseFactory.create_database('factory_test', 'freshdesk')
        print(f'✅ 자동 선택 DB: {type(db_auto).__name__}')
        
    except Exception as e:
        print(f'❌ 데이터베이스 팩토리 테스트 실패: {e}')

def main():
    print('🧪 멀티테넌트 데이터베이스 최종 검증')
    print('=' * 80)
    
    # 환경변수 확인
    print(f'📊 현재 환경:')
    print(f'   DATABASE_TYPE: {os.getenv("DATABASE_TYPE", "NOT_SET")}')
    print(f'   TENANT_ISOLATION: {os.getenv("TENANT_ISOLATION", "NOT_SET")}')
    print(f'   MAX_TENANTS: {os.getenv("MAX_TENANTS", "NOT_SET")}')
    print(f'   SUPPORTED_PLATFORMS: {os.getenv("SUPPORTED_PLATFORMS", "NOT_SET")}')
    print()
    
    # 멀티테넌트 설정 검증
    validation = validate_multitenant_setup()
    print(f'🔍 설정 검증: {"✅ 통과" if validation["is_production_ready"] else "❌ 실패"}')
    if validation['recommendations']:
        for rec in validation['recommendations']:
            print(f'   ⚠️ {rec}')
    print()
    
    # 테스트 실행
    tenant_data = test_multitenant_database_separation()
    test_tenant_isolation()
    test_tenant_config_management()
    test_database_factory()
    
    # 요약
    print('\n📊 테스트 결과 요약')
    print('=' * 60)
    if tenant_data:
        print(f'✅ 성공적으로 테스트된 테넌트: {len(tenant_data)}개')
        for company_id, info in tenant_data.items():
            print(f'   - {company_id} ({info["platform"]}): {info["ticket_count"]}개 티켓')
    else:
        print('❌ 테넌트 테스트 실패')
    
    print(f'\n🎯 멀티테넌트 아키텍처: {"✅ 정상 작동" if len(tenant_data) > 0 else "❌ 문제 있음"}')

if __name__ == '__main__':
    main()
