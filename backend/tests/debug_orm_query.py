#!/usr/bin/env python3
"""
ORM 쿼리와 메타데이터 파싱 디버깅 스크립트
"""
import sys
import json
from pathlib import Path

# backend 디렉토리를 Python 경로에 추가
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.append(str(backend_dir))

from core.database.manager import get_db_manager
from core.repositories.integrated_object_repository import IntegratedObjectRepository

def debug_orm_query():
    try:
        tenant_id = "wedosoft"
        platform = "freshdesk"
        
        db_manager = get_db_manager(tenant_id=tenant_id)
        
        with db_manager.get_session() as session:
            repo = IntegratedObjectRepository(session)
            
            # 모든 객체 조회 (필터링 없이)
            all_objects = repo.get_by_company(
                tenant_id=tenant_id,
                platform=platform
            )
            
            print(f"전체 객체 수: {len(all_objects)}")
            
            for i, obj in enumerate(all_objects):
                print(f"\n{i+1}. original_id: {obj.original_id}")
                print(f"   object_type: {obj.object_type}")
                print(f"   summary 존재: {bool(obj.summary)}")
                print(f"   summary 길이: {len(obj.summary) if obj.summary else 0}")
                print(f"   summary 내용: {obj.summary[:100] if obj.summary else 'None'}...")
                
                # 메타데이터 타입과 내용 확인
                print(f"   tenant_metadata 타입: {type(obj.tenant_metadata)}")
                
                if obj.tenant_metadata:
                    if isinstance(obj.tenant_metadata, str):
                        print(f"   tenant_metadata (문자열): {obj.tenant_metadata[:200]}...")
                        try:
                            parsed_metadata = json.loads(obj.tenant_metadata)
                            print(f"   파싱 성공: {len(parsed_metadata)} 키")
                            # 주요 필드 확인
                            key_fields = ['subject', 'status', 'priority', 'original_id']
                            for field in key_fields:
                                if field in parsed_metadata:
                                    print(f"     {field}: {parsed_metadata[field]}")
                        except json.JSONDecodeError as e:
                            print(f"   JSON 파싱 실패: {e}")
                    elif isinstance(obj.tenant_metadata, dict):
                        print(f"   tenant_metadata (딕셔너리): {len(obj.tenant_metadata)} 키")
                        # 주요 필드 확인
                        key_fields = ['subject', 'status', 'priority', 'original_id']
                        for field in key_fields:
                            if field in obj.tenant_metadata:
                                print(f"     {field}: {obj.tenant_metadata[field]}")
                    else:
                        print(f"   tenant_metadata: {obj.tenant_metadata}")
                else:
                    print(f"   tenant_metadata: None")
                
                # 요약이 있는지 확인
                if obj.summary and obj.summary.strip():
                    print(f"   ✅ 벡터 DB 동기화 대상")
                else:
                    print(f"   ❌ 벡터 DB 동기화 제외 (요약 없음)")
                    
    except Exception as e:
        print(f"오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_orm_query()
