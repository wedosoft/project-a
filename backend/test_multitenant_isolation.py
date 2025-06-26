#!/usr/bin/env python3
"""
멀티테넌트 데이터 격리 테스트 스크립트
"""

import os
import sys
import json
from datetime import datetime

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database.database import (
    get_database, 
    get_tenant_database, 
    DatabaseFactory,
    TenantDataManager,
    validate_multitenant_setup
)

def test_tenant_isolation():
    """테넌트 격리 테스트"""
    print("🧪 멀티테넌트 데이터 격리 테스트 시작")
    print("=" * 50)
    
    # 테스트 테넌트
    test_tenants = [
        {'company_id': 'acme_corp', 'platform': 'freshdesk'},
        {'company_id': 'beta_company', 'platform': 'freshdesk'},
        {'company_id': 'gamma_ltd', 'platform': 'zendesk'}
    ]
    
    # 1. 각 테넌트에 샘플 데이터 삽입
    print("\n1️⃣ 테넌트별 데이터 삽입 테스트")
    for tenant in test_tenants:
        db = get_tenant_database(tenant['company_id'], tenant['platform'], force_creation=True)
        
        # 샘플 티켓 데이터 삽입
        sample_ticket = {
            'original_id': f"TICKET-{tenant['company_id']}-001",
            'object_type': 'ticket',
            'original_data': {
                'id': 1001,
                'subject': f"Test ticket for {tenant['company_id']}",
                'description': f"This is a test ticket for tenant {tenant['company_id']}",
                'status': 'open',
                'priority': 'medium'
            },
            'integrated_content': f"Test ticket for {tenant['company_id']}",
            'summary': f"Test ticket for {tenant['company_id']}",
            'metadata': {
                'tenant_id': tenant['company_id'],
                'platform': tenant['platform'],
                'created_at': datetime.now().isoformat()
            }
        }
        
        try:
            result = db.insert_integrated_object(sample_ticket)
            print(f"   ✅ {tenant['company_id']} ({tenant['platform']}): 티켓 삽입 성공 (ID: {result})")
        except Exception as e:
            print(f"   ❌ {tenant['company_id']} ({tenant['platform']}): 티켓 삽입 실패 - {e}")
        
        db.disconnect()
    
    # 2. 데이터 격리 검증
    print("\n2️⃣ 데이터 격리 검증")
    for tenant in test_tenants:
        db = get_tenant_database(tenant['company_id'], tenant['platform'])
        
        try:
            # 현재 테넌트의 데이터만 조회되는지 확인
            objects = db.get_integrated_objects_by_type(tenant['company_id'], tenant['platform'], 'ticket')
            
            # 데이터 격리 검증
            isolated = True
            for obj in objects:
                if hasattr(db, 'company_id'):
                    # SQLite의 경우
                    if db.company_id != tenant['company_id']:
                        isolated = False
                        break
                else:
                    # PostgreSQL의 경우 - 메타데이터로 확인
                    if obj.get('metadata', {}).get('tenant_id') != tenant['company_id']:
                        isolated = False
                        break
            
            status = "✅ 격리됨" if isolated else "❌ 격리 실패"
            print(f"   {tenant['company_id']} ({tenant['platform']}): {len(objects)}개 객체, {status}")
            
        except Exception as e:
            print(f"   ❌ {tenant['company_id']} ({tenant['platform']}): 조회 실패 - {e}")
        
        db.disconnect()
    
    # 3. 크로스 테넌트 액세스 테스트
    print("\n3️⃣ 크로스 테넌트 액세스 방지 테스트")
    try:
        # acme_corp DB로 beta_company 데이터 조회 시도
        acme_db = get_tenant_database('acme_corp', 'freshdesk')
        beta_objects = acme_db.get_integrated_objects_by_type('beta_company', 'freshdesk', 'ticket')
        
        if len(beta_objects) == 0:
            print("   ✅ 크로스 테넌트 데이터 액세스 차단됨")
        else:
            print(f"   ❌ 크로스 테넌트 데이터 액세스 발생: {len(beta_objects)}개 객체")
        
        acme_db.disconnect()
        
    except Exception as e:
        print(f"   ✅ 크로스 테넌트 액세스 예외로 차단됨: {e}")
    
    # 4. 테넌트 검증 결과
    print("\n4️⃣ 테넌트 설정 검증")
    for tenant in test_tenants:
        validation = DatabaseFactory.validate_tenant_isolation(tenant['company_id'], tenant['platform'])
        print(f"   {tenant['company_id']}: {validation['isolation_method']} 방식, 격리: {validation['is_isolated']}")
        if validation['recommendations']:
            for rec in validation['recommendations']:
                print(f"     💡 권장사항: {rec}")


def test_multitenant_configuration():
    """멀티테넌트 설정 테스트"""
    print("\n🔧 멀티테넌트 설정 검증")
    print("=" * 50)
    
    validation = validate_multitenant_setup()
    
    print(f"데이터베이스 타입: {validation['database_type']}")
    print(f"격리 방식: {validation['isolation_method']}")
    print(f"프로덕션 준비: {'✅' if validation['is_production_ready'] else '❌'}")
    
    print("\n환경변수 상태:")
    for var, value in validation['environment_vars'].items():
        status = "✅" if value != "NOT_SET" else "❌"
        display_value = value if var != 'POSTGRES_PASSWORD' else "***"
        print(f"  {status} {var}: {display_value}")
    
    if validation['recommendations']:
        print("\n권장사항:")
        for rec in validation['recommendations']:
            print(f"  💡 {rec}")


def test_tenant_data_operations():
    """테넌트 데이터 운영 테스트"""
    print("\n📊 테넌트 데이터 운영 테스트")
    print("=" * 50)
    
    # 통계 조회
    for company_id in ['acme_corp', 'beta_company']:
        try:
            stats = TenantDataManager.get_tenant_statistics(company_id, 'freshdesk')
            print(f"\n{company_id} 통계:")
            print(f"  📄 객체 수: {stats['object_counts']}")
            if 'file_size_mb' in stats['storage_info']:
                print(f"  💾 파일 크기: {stats['storage_info']['file_size_mb']:.2f} MB")
        except Exception as e:
            print(f"  ❌ {company_id} 통계 조회 실패: {e}")


if __name__ == "__main__":
    print("🏢 멀티테넌트 SaaS 플랫폼 격리 테스트")
    print(f"실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # 설정 검증
        test_multitenant_configuration()
        
        # 데이터 격리 테스트
        test_tenant_isolation()
        
        # 운영 테스트
        test_tenant_data_operations()
        
        print("\n" + "=" * 50)
        print("✅ 모든 테스트 완료!")
        
    except Exception as e:
        print(f"\n❌ 테스트 실행 중 오류 발생: {e}")
        sys.exit(1)
