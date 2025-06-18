#!/usr/bin/env python3
"""
Qdrant 컬렉션에 ticket_id 필드의 키워드 인덱스를 추가하는 스크립트

에러 해결: Index required but not found for "ticket_id" of one of the following types: [keyword]
"""

import os
import asyncio
from qdrant_client import QdrantClient
from qdrant_client.models import PayloadSchemaType, CreateFieldIndex

async def add_ticket_id_index():
    """
    Qdrant 컬렉션에 ticket_id 필드의 키워드 인덱스를 추가합니다.
    """
    # 환경변수에서 Qdrant 설정 가져오기
    qdrant_url = os.getenv("QDRANT_URL")
    qdrant_api_key = os.getenv("QDRANT_API_KEY")
    collection_name = "documents"
    
    if not qdrant_url or not qdrant_api_key:
        print("❌ QDRANT_URL 또는 QDRANT_API_KEY 환경변수가 설정되지 않았습니다.")
        return False
    
    try:
        # Qdrant 클라이언트 생성
        client = QdrantClient(
            url=qdrant_url,
            api_key=qdrant_api_key,
            timeout=30
        )
        
        print(f"🔍 Qdrant 연결 확인 (URL: {qdrant_url})")
        
        # 컬렉션 존재 확인
        collections = client.get_collections()
        collection_exists = any(col.name == collection_name for col in collections.collections)
        
        if not collection_exists:
            print(f"❌ 컬렉션 '{collection_name}'이 존재하지 않습니다.")
            return False
        
        print(f"✅ 컬렉션 '{collection_name}' 확인 완료")
        
        # 현재 컬렉션 정보 조회
        collection_info = client.get_collection(collection_name)
        print(f"📊 컬렉션 정보:")
        print(f"   - 벡터 수: {collection_info.points_count}")
        print(f"   - 벡터 차원: {collection_info.config.params.vectors.size}")
        
        # 기존 페이로드 스키마 확인
        if collection_info.payload_schema:
            print(f"📋 기존 페이로드 스키마:")
            for field_name, field_info in collection_info.payload_schema.items():
                print(f"   - {field_name}: {field_info}")
        else:
            print("📋 기존 페이로드 스키마: 없음")
        
        # ticket_id 인덱스가 이미 있는지 확인
        if (collection_info.payload_schema and 
            "ticket_id" in collection_info.payload_schema and
            collection_info.payload_schema["ticket_id"].data_type == PayloadSchemaType.KEYWORD):
            print("✅ ticket_id 키워드 인덱스가 이미 존재합니다.")
            return True
        
        print("🔧 ticket_id 필드의 키워드 인덱스 추가 중...")
        
        # ticket_id 필드에 키워드 인덱스 생성
        client.create_payload_index(
            collection_name=collection_name,
            field_name="ticket_id",
            field_schema=PayloadSchemaType.KEYWORD
        )
        
        print("✅ ticket_id 키워드 인덱스 추가 완료!")
        
        # 인덱스 추가 후 컬렉션 정보 다시 확인
        updated_collection_info = client.get_collection(collection_name)
        print(f"📋 업데이트된 페이로드 스키마:")
        if updated_collection_info.payload_schema:
            for field_name, field_info in updated_collection_info.payload_schema.items():
                print(f"   - {field_name}: {field_info}")
        
        return True
        
    except Exception as e:
        print(f"❌ 인덱스 추가 중 오류 발생: {e}")
        return False

async def main():
    """메인 실행 함수"""
    print("🚀 Qdrant ticket_id 키워드 인덱스 추가 시작")
    print("=" * 50)
    
    success = await add_ticket_id_index()
    
    print("=" * 50)
    if success:
        print("✅ ticket_id 키워드 인덱스 추가 성공!")
        print("💡 이제 /init 엔드포인트에서 ticket_id 필터링이 정상 작동합니다.")
    else:
        print("❌ ticket_id 키워드 인덱스 추가 실패")
        print("💡 환경변수 설정과 Qdrant 연결 상태를 확인해주세요.")

if __name__ == "__main__":
    asyncio.run(main())
