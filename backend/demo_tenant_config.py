#!/usr/bin/env python3
"""
멀티테넌트 설정 관리 데모 및 테스트
테넌트별 설정이 어떻게 관리되는지 보여주는 예시
"""

import sys
import json
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
backend_path = Path(__file__).parent
sys.path.insert(0, str(backend_path))

from core.database.database import get_database
from core.database.tenant_config import TenantConfigManager, setup_new_tenant

def demo_multitenant_config():
    """멀티테넌트 설정 관리 데모"""
    
    print("🏢 멀티테넌트 설정 관리 데모")
    print("=" * 60)
    
    # 1. 가상의 테넌트들 설정
    tenants = [
        {
            'company_id': 1,
            'company_name': 'WedoSoft',
            'platform': 'freshdesk',
            'config': {
                'domain': 'wedosoft.freshdesk.com',
                'api_key': 'fd_api_key_wedosoft_secure_123',
                'rate_limit': 200,
                'collect_attachments': True
            }
        },
        {
            'company_id': 2,
            'company_name': 'ACME Corp',
            'platform': 'freshdesk',
            'config': {
                'domain': 'acme.freshdesk.com',
                'api_key': 'fd_api_key_acme_secure_456',
                'rate_limit': 500,  # 더 높은 제한
                'collect_private_notes': False  # 다른 설정
            }
        },
        {
            'company_id': 3,
            'company_name': 'StartupXYZ',
            'platform': 'zendesk',
            'config': {
                'domain': 'startupxyz.zendesk.com',
                'api_key': 'zd_api_key_startup_secure_789',
                'rate_limit': 100
            }
        }
    ]
    
    # 2. 각 테넌트별로 설정 저장
    print("\n📝 테넌트별 설정 저장 중...")
    for tenant in tenants:
        try:
            # 시스템 DB 사용 (실제로는 각 테넌트의 DB에 저장)
            db = get_database("system", "master")
            config_manager = TenantConfigManager(db)
            db.connect()
            
            company_id = tenant['company_id']
            
            # 기본 정보 저장
            config_manager.set_tenant_setting(
                company_id, 
                'company_name', 
                tenant['company_name']
            )
            
            config_manager.set_tenant_setting(
                company_id,
                'primary_platform',
                tenant['platform']
            )
            
            # 플랫폼별 설정 저장 (암호화됨)
            config_manager.set_platform_config(
                company_id,
                tenant['platform'],
                tenant['config']
            )
            
            # 추가 설정들
            config_manager.set_tenant_setting(
                company_id,
                'timezone',
                'Asia/Seoul'
            )
            
            config_manager.set_tenant_setting(
                company_id,
                'features',
                {
                    'ai_summary': True,
                    'advanced_analytics': tenant['company_id'] > 1,  # ACME와 StartupXYZ만
                    'custom_fields': True
                }
            )
            
            print(f"✅ {tenant['company_name']} 설정 완료")
            
        except Exception as e:
            print(f"❌ {tenant['company_name']} 설정 실패: {e}")
    
    # 3. 설정 조회 및 검증
    print("\n🔍 테넌트별 설정 조회...")
    for tenant in tenants:
        try:
            db = get_database("system", "master")
            config_manager = TenantConfigManager(db)
            db.connect()
            
            company_id = tenant['company_id']
            
            print(f"\n--- {tenant['company_name']} (ID: {company_id}) ---")
            
            # 기본 정보
            company_name = config_manager.get_tenant_setting(company_id, 'company_name')
            platform = config_manager.get_tenant_setting(company_id, 'primary_platform')
            timezone = config_manager.get_tenant_setting(company_id, 'timezone')
            
            print(f"회사명: {company_name}")
            print(f"플랫폼: {platform}")
            print(f"타임존: {timezone}")
            
            # 플랫폼 설정 (복호화됨)
            platform_config = config_manager.get_platform_config(company_id, platform)
            print(f"플랫폼 설정:")
            for key, value in platform_config.items():
                if 'api_key' in key:
                    # API 키는 마스킹하여 표시
                    print(f"  {key}: {value[:10]}***")
                else:
                    print(f"  {key}: {value}")
            
            # 기능 설정
            features = config_manager.get_tenant_setting(company_id, 'features', {})
            print(f"기능 설정: {features}")
            
            # 설정 유효성 검증
            validation = config_manager.validate_tenant_config(company_id, platform)
            status = "✅ 유효" if validation['is_valid'] else "❌ 무효"
            print(f"설정 상태: {status}")
            
            if validation['missing_settings']:
                print(f"누락된 설정: {validation['missing_settings']}")
            if validation['warnings']:
                print(f"경고: {validation['warnings']}")
                
        except Exception as e:
            print(f"❌ {tenant['company_name']} 조회 실패: {e}")
            import traceback
            traceback.print_exc()
    
    # 4. 동적 설정 변경 데모
    print("\n🔄 동적 설정 변경 데모...")
    try:
        db = get_database("system", "master")
        config_manager = TenantConfigManager(db)
        db.connect()
        
        # ACME Corp의 API 제한 증가
        company_id = 2
        current_config = config_manager.get_platform_config(company_id, 'freshdesk')
        current_config['rate_limit'] = 1000  # 500 -> 1000으로 증가
        
        config_manager.set_platform_config(company_id, 'freshdesk', current_config)
        
        # 변경 확인
        updated_config = config_manager.get_platform_config(company_id, 'freshdesk')
        print(f"✅ ACME Corp API 제한 변경: {updated_config['rate_limit']}")
        
    except Exception as e:
        print(f"❌ 동적 설정 변경 실패: {e}")
    
    # 5. 테넌트 간 격리 확인
    print("\n🔒 테넌트 간 설정 격리 확인...")
    try:
        db = get_database("system", "master")
        config_manager = TenantConfigManager(db)
        db.connect()
        
        # 각 테넌트의 API 키가 다른지 확인
        api_keys = {}
        for tenant in tenants:
            company_id = tenant['company_id']
            platform = tenant['platform']
            config = config_manager.get_platform_config(company_id, platform)
            api_keys[company_id] = config.get('api_key', 'N/A')
        
        print("테넌트별 API 키 격리 상태:")
        for company_id, api_key in api_keys.items():
            masked_key = api_key[:10] + "***" if len(api_key) > 10 else "N/A"
            print(f"  테넌트 {company_id}: {masked_key}")
        
        # 중복 확인
        unique_keys = set(api_keys.values())
        if len(unique_keys) == len(api_keys):
            print("✅ 모든 테넌트가 고유한 설정을 가지고 있습니다.")
        else:
            print("❌ 설정 중복이 발견되었습니다!")
            
    except Exception as e:
        print(f"❌ 격리 확인 실패: {e}")

if __name__ == '__main__':
    demo_multitenant_config()
