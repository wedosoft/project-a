#!/usr/bin/env python3
"""멀티테넌트 설정 상태 검증"""

import os
import sys
import json
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
backend_path = Path(__file__).parent
sys.path.insert(0, str(backend_path))

from core.database.database import validate_multitenant_setup, DatabaseFactory

def main():
    print('🔍 멀티테넌트 설정 검증 중...')
    print('=' * 50)
    
    # 설정 검증
    validation = validate_multitenant_setup()
    print(json.dumps(validation, indent=2, ensure_ascii=False))
    
    print('\n🧪 데이터베이스 팩토리 테스트...')
    print('=' * 50)
    
    try:
        # SQLite 테스트
        db_sqlite = DatabaseFactory.create_database('test_company', 'freshdesk', 'sqlite')
        print(f'✅ SQLite DB: {type(db_sqlite).__name__}')
        print(f'   경로: {getattr(db_sqlite, "db_path", "경로 없음")}')
        print(f'   회사ID: {getattr(db_sqlite, "company_id", "없음")}')
        print(f'   플랫폼: {getattr(db_sqlite, "platform", "없음")}')
        
        # PostgreSQL 테스트 (실패해도 괜찮음)
        print('\n🐘 PostgreSQL 테스트...')
        try:
            db_pg = DatabaseFactory.create_database('test_company', 'freshdesk', 'postgresql')
            print(f'✅ PostgreSQL DB: {type(db_pg).__name__}')
            print(f'   스키마: {getattr(db_pg, "schema_name", "스키마 없음")}')
            print(f'   회사ID: {getattr(db_pg, "company_id", "없음")}')
            print(f'   플랫폼: {getattr(db_pg, "platform", "없음")}')
        except Exception as e:
            print(f'❌ PostgreSQL 테스트 실패: {e}')
            
    except Exception as e:
        print(f'❌ 데이터베이스 팩토리 오류: {e}')
        import traceback
        traceback.print_exc()

    print('\n📊 테넌트 격리 검증...')
    print('=' * 50)
    
    # 여러 테넌트로 격리 테스트
    test_tenants = [
        {'company_id': 'wedosoft', 'platform': 'freshdesk'},
        {'company_id': 'acme_corp', 'platform': 'zendesk'},
        {'company_id': 'startup123', 'platform': 'freshdesk'}
    ]
    
    for tenant in test_tenants:
        try:
            validation = DatabaseFactory.validate_tenant_isolation(
                tenant['company_id'], 
                tenant['platform']
            )
            isolation_status = "✅ 격리됨" if validation['is_isolated'] else "❌ 격리 실패"
            print(f"{isolation_status} - {tenant['company_id']} ({tenant['platform']})")
            if validation['recommendations']:
                for rec in validation['recommendations']:
                    print(f"   ⚠️  {rec}")
        except Exception as e:
            print(f"❌ {tenant['company_id']} 검증 실패: {e}")

if __name__ == '__main__':
    main()
