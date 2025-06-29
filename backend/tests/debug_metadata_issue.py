#!/usr/bin/env python3
"""
메타데이터 문제 디버깅 스크립트
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

def debug_metadata_issue():
    try:
        tenant_id = "wedosoft"
        platform = "freshdesk"
        
        db_manager = get_db_manager(tenant_id=tenant_id)
        
        with db_manager.get_session() as session:
            repo = IntegratedObjectRepository(session)
            
            # 첫 번째 KB 문서 확인
            objects = repo.get_by_company(tenant_id=tenant_id, platform=platform)
            kb_articles = [obj for obj in objects if obj.object_type == "integrated_article"]
            
            if kb_articles:
                obj = kb_articles[0]
                print(f"=== KB 문서 디버깅 ===")
                print(f"Original ID: {obj.original_id}")
                print(f"Object Type: {obj.object_type}")
                
                # tenant_metadata 확인
                print(f"\n=== tenant_metadata ===")
                print(f"Type: {type(obj.tenant_metadata)}")
                if obj.tenant_metadata:
                    if isinstance(obj.tenant_metadata, str):
                        try:
                            parsed_tenant = json.loads(obj.tenant_metadata)
                            print(f"Keys: {list(parsed_tenant.keys())}")
                            print(f"Subject: {parsed_tenant.get('subject')}")
                            print(f"Title: {parsed_tenant.get('title')}")
                            print(f"ID: {parsed_tenant.get('id')}")
                            print(f"Status: {parsed_tenant.get('status')} (type: {type(parsed_tenant.get('status'))})")
                        except json.JSONDecodeError as e:
                            print(f"JSON 파싱 실패: {e}")
                
                # original_data 확인
                print(f"\n=== original_data ===")
                print(f"Type: {type(obj.original_data)}")
                if obj.original_data:
                    if isinstance(obj.original_data, str):
                        try:
                            parsed_orig = json.loads(obj.original_data)
                            print(f"Keys: {list(parsed_orig.keys())}")
                            print(f"Title: {parsed_orig.get('title')}")
                            print(f"Subject: {parsed_orig.get('subject')}")
                            print(f"ID: {parsed_orig.get('id')}")
                            print(f"Description: {parsed_orig.get('description', '')[:100]}...")
                        except json.JSONDecodeError as e:
                            print(f"JSON 파싱 실패: {e}")
                    elif isinstance(obj.original_data, dict):
                        print(f"Keys: {list(obj.original_data.keys())}")
                        print(f"Title: {obj.original_data.get('title')}")
                        print(f"Subject: {obj.original_data.get('subject')}")
                        print(f"ID: {obj.original_data.get('id')}")
                        
                        # metadata 필드 확인 (실제 Freshdesk 데이터가 여기에 있을 수 있음)
                        if 'metadata' in obj.original_data:
                            metadata = obj.original_data['metadata']
                            print(f"\n=== original_data.metadata ===")
                            print(f"Type: {type(metadata)}")
                            if isinstance(metadata, dict):
                                print(f"Keys: {list(metadata.keys())}")
                                print(f"Title: {metadata.get('title')}")
                                print(f"Subject: {metadata.get('subject')}")
                                print(f"Name: {metadata.get('name')}")
                                print(f"Description: {metadata.get('description', '')[:100]}...")
                            elif isinstance(metadata, str):
                                try:
                                    parsed_meta = json.loads(metadata)
                                    print(f"Keys: {list(parsed_meta.keys())}")
                                    print(f"Title: {parsed_meta.get('title')}")
                                    print(f"Subject: {parsed_meta.get('subject')}")
                                except json.JSONDecodeError:
                                    print(f"Raw metadata: {metadata[:200]}...")
            
            # 티켓도 하나 확인
            tickets = [obj for obj in objects if obj.object_type == "integrated_ticket"]
            if tickets:
                obj = tickets[0]
                print(f"\n=== 티켓 디버깅 ===")
                print(f"Original ID: {obj.original_id}")
                print(f"Object Type: {obj.object_type}")
                
                # original_data 확인
                if obj.original_data:
                    if isinstance(obj.original_data, str):
                        try:
                            parsed_orig = json.loads(obj.original_data)
                            print(f"Original Data Keys: {list(parsed_orig.keys())}")
                            print(f"Subject: {parsed_orig.get('subject')}")
                            print(f"ID: {parsed_orig.get('id')}")
                            print(f"Description: {parsed_orig.get('description', '')[:100]}...")
                        except json.JSONDecodeError as e:
                            print(f"JSON 파싱 실패: {e}")
                    
        
    except Exception as e:
        print(f"오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_metadata_issue()
