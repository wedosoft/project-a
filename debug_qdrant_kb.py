#!/usr/bin/env python3
"""
Qdrant에 저장된 KB 문서들의 메타데이터를 직접 조회하여 디버깅
"""

import os
import sys
from pathlib import Path

# 백엔드 경로 추가
backend_dir = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_dir))

from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.http.models import FieldCondition, Filter, MatchValue

# 환경변수 로드
load_dotenv(backend_dir / ".env")

def debug_kb_documents():
    """KB 문서들의 메타데이터 확인"""
    
    # Qdrant 클라이언트 초기화
    client = QdrantClient(
        url=os.getenv("QDRANT_URL"),
        api_key=os.getenv("QDRANT_API_KEY")
    )
    
    collection_name = "documents"
    company_id = os.getenv("COMPANY_ID", "nextfirm")
    
    print(f"🔍 KB 문서 메타데이터 디버깅")
    print(f"Collection: {collection_name}")
    print(f"Company ID: {company_id}")
    print("-" * 50)
    
    try:
        # 1. 전체 문서 수 확인
        collection_info = client.get_collection(collection_name)
        print(f"전체 컬렉션 크기: {collection_info.points_count}개 문서")
        
        # 2. company_id로 필터링된 전체 문서 조회 (상위 20개)
        company_filter = Filter(
            must=[
                FieldCondition(key="company_id", match=MatchValue(value=company_id))
            ]
        )
        
        results = client.scroll(
            collection_name=collection_name,
            scroll_filter=company_filter,
            limit=20,
            with_payload=True,
            with_vectors=False
        )[0]  # (points, next_page_offset)
        
        print(f"\n📊 {company_id} 회사의 문서 (상위 20개):")
        
        # 문서 타입별 분류
        kb_docs = []
        ticket_docs = []
        unknown_docs = []
        
        for point in results:
            payload = point.payload
            doc_type = payload.get("doc_type")
            doc_id = payload.get("id") or payload.get("original_id")
            title = payload.get("title", "제목 없음")[:50]
            status = payload.get("status")
            source_type = payload.get("source_type") 
            type_field = payload.get("type")
            
            print(f"\n문서 ID: {doc_id}")
            print(f"  doc_type: {doc_type}")
            print(f"  type: {type_field}")
            print(f"  source_type: {source_type}")
            print(f"  status: {status}")
            print(f"  title: {title}")
            
            # 분류
            if doc_type == "kb":
                kb_docs.append(point)
            elif doc_type == "ticket":
                ticket_docs.append(point)
            else:
                unknown_docs.append(point)
        
        print(f"\n📈 문서 타입별 통계:")
        print(f"  KB 문서 (doc_type='kb'): {len(kb_docs)}개")
        print(f"  티켓 문서 (doc_type='ticket'): {len(ticket_docs)}개")
        print(f"  알 수 없는 타입: {len(unknown_docs)}개")
        
        # 3. KB 문서 상세 분석
        if kb_docs:
            print(f"\n🔍 KB 문서 상세 분석:")
            for i, point in enumerate(kb_docs[:5]):
                payload = point.payload
                print(f"\n  KB 문서 #{i+1}:")
                print(f"    ID: {payload.get('id')}")
                print(f"    status: {payload.get('status')}")
                print(f"    type: {payload.get('type')}")
                print(f"    category_id: {payload.get('category_id')}")
                print(f"    folder_id: {payload.get('folder_id')}")
                print(f"    title: {payload.get('title', '')[:100]}")
        
        # 4. doc_type 필드 검증 - KB로 필터링 시도
        try:
            kb_filter = Filter(
                must=[
                    FieldCondition(key="company_id", match=MatchValue(value=company_id)),
                    FieldCondition(key="doc_type", match=MatchValue(value="kb"))
                ]
            )
            
            kb_results = client.scroll(
                collection_name=collection_name,
                scroll_filter=kb_filter,
                limit=10,
                with_payload=True,
                with_vectors=False
            )[0]
            
            print(f"\n✅ doc_type='kb' 필터링 테스트: {len(kb_results)}개 문서 발견")
            
        except Exception as e:
            print(f"\n❌ doc_type='kb' 필터링 실패: {e}")
            
        # 5. status 필드로 KB 문서 찾기 시도
        try:
            status_filter = Filter(
                must=[
                    FieldCondition(key="company_id", match=MatchValue(value=company_id)),
                    FieldCondition(key="status", match=MatchValue(value=2))  # published KB
                ]
            )
            
            status_results = client.scroll(
                collection_name=collection_name,
                scroll_filter=status_filter,
                limit=10,
                with_payload=True,
                with_vectors=False
            )[0]
            
            print(f"\n✅ status=2 필터링 테스트: {len(status_results)}개 문서 발견")
            
            if status_results:
                sample = status_results[0].payload
                print(f"    샘플 문서 doc_type: {sample.get('doc_type')}")
                
        except Exception as e:
            print(f"\n❌ status=2 필터링 실패: {e}")
            
    except Exception as e:
        print(f"❌ 오류 발생: {e}")

if __name__ == "__main__":
    debug_kb_documents()
