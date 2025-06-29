#!/usr/bin/env python3
"""
간단한 메타데이터 확인 스크립트
"""
import sys
import json
from pathlib import Path

# backend 디렉토리를 Python 경로에 추가
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.append(str(backend_dir))

def check_original_data():
    try:
        from core.database.manager import get_db_manager
        from core.repositories.integrated_object_repository import IntegratedObjectRepository
        
        tenant_id = "wedosoft"
        platform = "freshdesk"
        
        db_manager = get_db_manager(tenant_id=tenant_id)
        
        with db_manager.get_session() as session:
            repo = IntegratedObjectRepository(session)
            objects = repo.get_by_company(tenant_id=tenant_id, platform=platform)
            
            if objects:
                obj = objects[0]
                print(f"Original ID: {obj.original_id}")
                print(f"Object Type: {obj.object_type}")
                
                # original_data 체크
                if obj.original_data:
                    if isinstance(obj.original_data, str):
                        try:
                            data = json.loads(obj.original_data)
                            print(f"Original Data Keys: {list(data.keys())[:10]}")
                            print(f"Title: {data.get('title', 'N/A')}")
                            print(f"Subject: {data.get('subject', 'N/A')}")
                            print(f"ID: {data.get('id', 'N/A')}")
                        except:
                            print("Original data 파싱 실패")
                    else:
                        print("Original data가 딕셔너리 형태")
                else:
                    print("Original data 없음")
                    
                # tenant_metadata 체크  
                if obj.tenant_metadata:
                    if isinstance(obj.tenant_metadata, str):
                        try:
                            metadata = json.loads(obj.tenant_metadata)
                            print(f"Tenant Metadata에서 subject: {metadata.get('subject', 'N/A')}")
                            print(f"Tenant Metadata에서 status: {metadata.get('status', 'N/A')}")
                        except:
                            print("Tenant metadata 파싱 실패")
                
    except Exception as e:
        print(f"오류: {e}")

if __name__ == "__main__":
    check_original_data()
