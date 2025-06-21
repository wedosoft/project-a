#!/usr/bin/env python3
"""벡터DB 상태 확인 스크립트"""

from core.database.vectordb import QdrantAdapter
from core.config import get_settings

def main():
    try:
        settings = get_settings()
        print(f'Qdrant URL: {settings.QDRANT_URL}')
        print(f'Qdrant API Key: {settings.QDRANT_API_KEY[:10]}...')

        # QdrantAdapter 인스턴스 생성
        db = QdrantAdapter()

        # 컬렉션 정보 확인
        info = db.get_collection_info()
        print(f'Collection info: {info}')

        # 문서 수 확인
        total_count = db.count()
        print(f'Total documents: {total_count}')

        # default 회사의 문서 수 확인
        default_count = db.count(company_id='default')
        print(f'Default company documents: {default_count}')

        # freshdesk 플랫폼의 문서 수 확인
        freshdesk_count = db.count(company_id='default', platform='freshdesk')
        print(f'Freshdesk platform documents: {freshdesk_count}')
        
        # 티켓과 KB 문서 수 별도 확인
        ticket_count = db.count(company_id='default', platform='freshdesk')
        print(f'Freshdesk ticket documents: {ticket_count}')
        
        # 샘플 검색 테스트 - 빈 임베딩으로 테스트
        print("\n=== 샘플 검색 테스트 ===")
        dummy_embedding = [0.0] * 1536  # OpenAI 임베딩 차원
        
        # KB 검색 테스트
        kb_results = db.search(
            query_embedding=dummy_embedding,
            top_k=3,
            company_id='default',
            platform='freshdesk',
            doc_type='kb'
        )
        print(f'KB search results: {len(kb_results.get("results", []))} documents')
        if kb_results.get("results"):
            sample_kb = kb_results["results"][0]
            print(f'Sample KB doc: title={sample_kb.get("title", "N/A")}, doc_type={sample_kb.get("doc_type", "N/A")}')
        
        # 티켓 검색 테스트  
        ticket_results = db.search(
            query_embedding=dummy_embedding,
            top_k=3,
            company_id='default',
            platform='freshdesk',
            doc_type='ticket'
        )
        print(f'Ticket search results: {len(ticket_results.get("results", []))} documents')
        if ticket_results.get("results"):
            sample_ticket = ticket_results["results"][0]
            print(f'Sample ticket: title={sample_ticket.get("subject", "N/A")}, doc_type={sample_ticket.get("doc_type", "N/A")}')

    except Exception as e:
        print(f'Error: {e}')
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
