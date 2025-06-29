#!/usr/bin/env python3
"""
original_data 구조 확인 스크립트
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

def debug_original_data():
    try:
        tenant_id = "wedosoft"
        platform = "freshdesk"
        
        db_manager = get_db_manager(tenant_id=tenant_id)
        
        with db_manager.get_session() as session:
            repo = IntegratedObjectRepository(session)
            
            # 몇 개 객체만 조회
            all_objects = repo.get_by_company(
                tenant_id=tenant_id,
                platform=platform
            )
            
            print(f"전체 객체 수: {len(all_objects)}")
            
            # 첫 번째 티켓과 첫 번째 KB 문서 확인
            ticket_example = None
            article_example = None
            
            for obj in all_objects:
                if obj.object_type == "integrated_ticket" and ticket_example is None:
                    ticket_example = obj
                elif obj.object_type == "integrated_article" and article_example is None:
                    article_example = obj
                
                if ticket_example and article_example:
                    break
            
            # 티켓 데이터 구조 확인
            if ticket_example:
                print(f"\n=== 티켓 예시 (ID: {ticket_example.original_id}) ===")
                try:
                    if isinstance(ticket_example.original_data, str):
                        original_data = json.loads(ticket_example.original_data)
                    else:
                        original_data = ticket_example.original_data
                    
                    print("original_data 키들:")
                    for key in sorted(original_data.keys()):
                        value = original_data[key]
                        if isinstance(value, str) and len(value) > 100:
                            print(f"  {key}: {type(value).__name__} (길이: {len(value)})")
                        else:
                            print(f"  {key}: {value}")
                            
                except Exception as e:
                    print(f"original_data 파싱 실패: {e}")
            
            # KB 문서 데이터 구조 확인
            if article_example:
                print(f"\n=== KB 문서 예시 (ID: {article_example.original_id}) ===")
                try:
                    if isinstance(article_example.original_data, str):
                        original_data = json.loads(article_example.original_data)
                    else:
                        original_data = article_example.original_data
                    
                    print("original_data 키들:")
                    for key in sorted(original_data.keys()):
                        value = original_data[key]
                        if isinstance(value, str) and len(value) > 100:
                            print(f"  {key}: {type(value).__name__} (길이: {len(value)})")
                        else:
                            print(f"  {key}: {value}")
                            
                except Exception as e:
                    print(f"original_data 파싱 실패: {e}")
                    
    except Exception as e:
        print(f"오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_original_data()
