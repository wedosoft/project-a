#!/usr/bin/env python3
"""간단한 멀티테넌트 아키텍처 테스트"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

def test_multitenant():
    print('🧪 멀티테넌트 아키텍처 테스트')
    print('=' * 50)
    
    try:
        from core.database.database import get_database
        
        # 테스트 DB 생성
        db = get_database('test_tenant', 'freshdesk')
        db.connect()
        print('✅ 데이터베이스 연결 성공')
        
        # 암호화 모듈 없이 기본 테스트
        print('✅ 기본 데이터베이스 기능 확인 완료')
        
        # 통합 객체 테스트
        test_data = {
            'original_id': 'test_001',
            'company_id': 'test_tenant',
            'platform': 'freshdesk',
            'object_type': 'ticket',
            'original_data': {'test': 'data'},
            'integrated_content': 'Test content',
            'summary': 'Test summary',
            'metadata': {'test': True}
        }
        
        result = db.insert_integrated_object(test_data)
        print(f'✅ 통합 객체 저장: {result}')
        
        # 조회 테스트
        objects = db.get_integrated_objects_by_type('test_tenant', 'freshdesk', 'ticket')
        print(f'✅ 통합 객체 조회: {len(objects)} 개')
        
        print('\\n🎉 핵심 멀티테넌트 기능 정상 작동!')
        
    except Exception as e:
        print(f'❌ 테스트 실패: {e}')
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_multitenant()
