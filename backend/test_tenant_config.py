#!/usr/bin/env python3
"""
멀티테넌트 설정 관리 테스트
테넌트별 설정이 올바르게 분리되는지 확인
"""

import os
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
backend_path = Path(__file__).parent
sys.path.insert(0, str(backend_path))

from core.database.database import get_database
from core.database.tenant_config import TenantConfigManager

def test_multitenant_settings():
    """멀티테넌트 설정 테스트"""
    print("🧪 멀티테넌트 설정 관리 테스트")
    print("=" * 50)
    
    # 테스트 테넌트들
    tenants = [
        {'company_id': 'wedosoft', 'platform': 'freshdesk'},
        {'company_id': 'acme_corp', 'platform': 'zendesk'},
        {'company_id': 'startup123', 'platform': 'freshdesk'}
    ]
    
    # 각 테넌트별 설정 테스트
    for tenant in tenants:
        print(f"\n📋 테넌트: {tenant['company_id']} ({tenant['platform']})")
        
        try:
            # 데이터베이스 연결
            db = get_database(tenant['company_id'], tenant['platform'])
            db.connect()
            
            # 설정 관리자 생성
            config_manager = TenantConfigManager(db)
            
            # 테넌트별 고유 설정 저장
            settings = {
                'api_key': f"api_key_for_{tenant['company_id']}",
                'domain': f"{tenant['company_id']}.{tenant['platform']}.com",
                'webhook_url': f"https://{tenant['company_id']}.example.com/webhook",
                'max_tickets_per_day': 1000 + hash(tenant['company_id']) % 5000,
                'features': {
                    'ai_summary': True,
                    'auto_routing': tenant['company_id'] != 'startup123',
                    'advanced_analytics': tenant['company_id'] == 'wedosoft'
                }
            }
            
            # 설정 저장
            for key, value in settings.items():
                is_sensitive = key in ['api_key', 'webhook_url']
                config_manager.set_tenant_setting(
                    key, 
                    value if not isinstance(value, dict) else value,
                    encrypted=is_sensitive
                )
                print(f"  ✅ 저장: {key} = {value if not is_sensitive else '[암호화됨]'}")
            
            # 설정 조회 테스트
            print(f"  🔍 조회 테스트:")
            for key in settings.keys():
                retrieved_value = config_manager.get_tenant_setting(key)
                print(f"    {key}: {retrieved_value}")
            
            db.disconnect()
            
        except Exception as e:
            print(f"  ❌ 오류: {e}")
            import traceback
            traceback.print_exc()
    
    print(f"\n🔒 테넌트 격리 검증")
    print("=" * 50)
    
    # 격리 검증: 다른 테넌트의 설정에 접근 시도
    try:
        db1 = get_database('wedosoft', 'freshdesk')
        db1.connect()
        config1 = TenantConfigManager(db1)
        
        db2 = get_database('acme_corp', 'zendesk')
        db2.connect()
        config2 = TenantConfigManager(db2)
        
        # wedosoft의 API 키
        wedosoft_api_key = config1.get_tenant_setting('api_key')
        print(f"wedosoft API 키: {wedosoft_api_key}")
        
        # acme_corp의 API 키
        acme_api_key = config2.get_tenant_setting('api_key')
        print(f"acme_corp API 키: {acme_api_key}")
        
        # 서로 다른지 확인
        if wedosoft_api_key != acme_api_key:
            print("✅ 테넌트 격리 성공: 각 테넌트는 독립적인 설정을 가짐")
        else:
            print("❌ 테넌트 격리 실패: 설정이 공유됨")
        
        db1.disconnect()
        db2.disconnect()
        
    except Exception as e:
        print(f"❌ 격리 검증 실패: {e}")

def test_encryption():
    """암호화 기능 테스트"""
    print(f"\n🔐 암호화 기능 테스트")
    print("=" * 50)
    
    try:
        db = get_database('test_encryption', 'freshdesk')
        db.connect()
        
        config_manager = TenantConfigManager(db)
        
        # 민감한 정보 저장 (암호화)
        sensitive_data = "super_secret_api_key_12345"
        config_manager.set_tenant_setting('secret_key', sensitive_data, encrypted=True)
        
        # 일반 정보 저장 (비암호화)
        normal_data = "public_domain_name"
        config_manager.set_tenant_setting('domain_name', normal_data, encrypted=False)
        
        # 조회
        retrieved_secret = config_manager.get_tenant_setting('secret_key')
        retrieved_domain = config_manager.get_tenant_setting('domain_name')
        
        print(f"원본 비밀 키: {sensitive_data}")
        print(f"조회된 비밀 키: {retrieved_secret}")
        print(f"원본 도메인: {normal_data}")
        print(f"조회된 도메인: {retrieved_domain}")
        
        if retrieved_secret == sensitive_data and retrieved_domain == normal_data:
            print("✅ 암호화/복호화 성공")
        else:
            print("❌ 암호화/복호화 실패")
        
        db.disconnect()
        
    except Exception as e:
        print(f"❌ 암호화 테스트 실패: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_multitenant_settings()
    test_encryption()
