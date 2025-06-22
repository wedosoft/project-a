#!/usr/bin/env python3
"""
새로운 LLM 요약 파이프라인 테스트
"""

import asyncio
import logging
import sys
import json
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, str(Path(__file__).parent))

from core.ingest.processor import ingest, generate_and_store_summaries
from core.database import SQLiteDatabase
from core.database.vectordb import vector_db

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_new_pipeline():
    """새로운 파이프라인 테스트"""
    logger.info("🚀 새로운 LLM 요약 파이프라인 테스트 시작")
    
    company_id = "test_company"
    platform = "freshdesk"
    
    try:
        # 1. 기존 벡터 DB 데이터 확인
        existing_count = vector_db.count(company_id=company_id)
        logger.info(f"기존 벡터 DB 문서 수 (company_id={company_id}): {existing_count}")
        
        # 2. 테스트 데이터 생성
        test_data_dir = Path("test_data")
        test_data_dir.mkdir(exist_ok=True)
        
        # 샘플 티켓 데이터
        sample_tickets = [
            {
                "id": 1,
                "subject": "로그인 문제",
                "description": "<p>사용자가 로그인할 수 없다고 합니다. 비밀번호를 재설정해도 문제가 계속 발생합니다.</p>",
                "description_text": "사용자가 로그인할 수 없다고 합니다. 비밀번호를 재설정해도 문제가 계속 발생합니다.",
                "status": "Open",
                "priority": "High",
                "created_at": "2024-01-01T10:00:00Z",
                "updated_at": "2024-01-01T10:00:00Z"
            },
            {
                "id": 2,
                "subject": "결제 오류",
                "description": "<p>고객이 신용카드로 결제를 시도했지만 오류가 발생했습니다. 은행에서는 문제없다고 합니다.</p>",
                "description_text": "고객이 신용카드로 결제를 시도했지만 오류가 발생했습니다. 은행에서는 문제없다고 합니다.",
                "status": "In Progress",
                "priority": "Medium",
                "created_at": "2024-01-01T11:00:00Z",
                "updated_at": "2024-01-01T11:30:00Z"
            }
        ]
        
        # 샘플 KB 문서 데이터 (Freshdesk API 구조 반영)
        sample_articles = [
            {
                "id": 101,
                "type": 1,  # 1=permanent, 2=workaround
                "title": "로그인 문제 해결 방법",
                "description": "<p>로그인 문제가 발생하는 경우 다음 단계를 따라주세요:</p><ol><li>브라우저 캐시 삭제</li><li>비밀번호 재설정</li><li>다른 브라우저 사용</li></ol>",
                "description_text": "로그인 문제가 발생하는 경우 다음 단계를 따라주세요: 1. 브라우저 캐시 삭제 2. 비밀번호 재설정 3. 다른 브라우저 사용",
                "status": 2,  # 2=published (수집됨)
                "category_id": 3,
                "folder_id": 4,
                "agent_id": 2,
                "hierarchy": [
                    {
                        "level": 0,
                        "type": "category",
                        "data": {
                            "id": 3,
                            "name": "일반문의",
                            "language": "ko"
                        }
                    },
                    {
                        "level": 1,
                        "type": "folder",
                        "data": {
                            "id": 4,
                            "name": "로그인관련",
                            "language": "ko"
                        }
                    }
                ],
                "thumbs_up": 5,
                "thumbs_down": 1,
                "hits": 127,  # 조회수
                "tags": ["로그인", "문제해결", "가이드"],
                "seo_data": {
                    "meta_title": "로그인 문제 해결 방법",
                    "meta_description": "로그인 문제 발생 시 단계별 해결 방법"
                },
                "created_at": "2024-01-01T09:00:00Z",
                "updated_at": "2024-01-01T09:00:00Z"
            },
            {
                "id": 102,
                "type": 1,  # 1=permanent, 2=workaround
                "title": "결제 문제 해결 가이드 (임시저장)",
                "description": "<p>결제 문제 해결 방법을 작성 중입니다...</p>",
                "description_text": "결제 문제 해결 방법을 작성 중입니다...",
                "status": 1,  # 1=draft (수집되지 않음)
                "category_id": 5,
                "folder_id": 6,
                "agent_id": 3,
                "hierarchy": [
                    {
                        "level": 0,
                        "type": "category",
                        "data": {
                            "id": 5,
                            "name": "결제문의",
                            "language": "ko"
                        }
                    },
                    {
                        "level": 1,
                        "type": "folder",
                        "data": {
                            "id": 6,
                            "name": "결제오류",
                            "language": "ko"
                        }
                    }
                ],
                "thumbs_up": 0,
                "thumbs_down": 0,
                "hits": 0,
                "tags": ["결제", "문제해결"],
                "seo_data": {
                    "meta_title": "결제 문제 해결 가이드",
                    "meta_description": "결제 문제 발생 시 해결 방법"
                },
                "created_at": "2024-01-01T10:00:00Z",
                "updated_at": "2024-01-01T10:30:00Z"
            },
            {
                "id": 103,
                "type": 2,  # 1=permanent, 2=workaround
                "title": "브라우저 호환성 문제 해결",
                "description": "<p>특정 브라우저에서 발생하는 호환성 문제 해결 방법입니다.</p>",
                "description_text": "특정 브라우저에서 발생하는 호환성 문제 해결 방법입니다.",
                "status": 2,  # 2=published (수집됨)
                "category_id": 3,
                "folder_id": 4,
                "agent_id": 2,
                "hierarchy": [
                    {
                        "level": 0,
                        "type": "category",
                        "data": {
                            "id": 3,
                            "name": "일반문의",
                            "language": "ko"
                        }
                    },
                    {
                        "level": 1,
                        "type": "folder",
                        "data": {
                            "id": 4,
                            "name": "로그인관련",
                            "language": "ko"
                        }
                    }
                ],
                "thumbs_up": 3,
                "thumbs_down": 0,
                "hits": 45,
                "tags": ["브라우저", "호환성", "해결방법"],
                "seo_data": {
                    "meta_title": "브라우저 호환성 문제 해결",
                    "meta_description": "브라우저 호환성 문제 해결 방법"
                },
                "created_at": "2024-01-01T12:00:00Z",
                "updated_at": "2024-01-01T12:00:00Z"
            }
        ]
        
        # 테스트 데이터 파일 저장
        with open(test_data_dir / "tickets.json", "w", encoding="utf-8") as f:
            json.dump(sample_tickets, f, ensure_ascii=False, indent=2)
        
        with open(test_data_dir / "kb_articles.json", "w", encoding="utf-8") as f:
            json.dump(sample_articles, f, ensure_ascii=False, indent=2)
        
        logger.info("✅ 테스트 데이터 파일 생성 완료")
        
        # 테스트 데이터 검증 로그 추가
        logger.info(f"📝 생성된 테스트 데이터:")
        logger.info(f"  - 티켓: {len(sample_tickets)}개")
        logger.info(f"  - KB 문서: {len(sample_articles)}개")
        logger.info("  - KB 문서 상세:")
        for article in sample_articles:
            status_text = "published" if article["status"] == 2 else "draft"
            logger.info(f"    ID {article['id']}: {article['title']} (status={article['status']}/{status_text}, type={article['type']})")
        
        # 3. 새로운 파이프라인 실행
        logger.info("🔄 새로운 파이프라인 실행 중...")
        await ingest(
            company_id=company_id,
            platform=platform,
            local_data_dir=str(test_data_dir),
            incremental=False,
            purge=False,
            force_rebuild=True,
            include_kb=True
        )
        
        # 4. 결과 확인
        logger.info("📊 결과 확인 중...")
        
        # 플랫폼별 데이터베이스 확인
        from core.database.database import get_database
        db = get_database(platform)
        
        # integrated_objects 테이블 확인
        cursor = db.connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM integrated_objects WHERE company_id = ? AND platform = ?", 
                      (company_id, platform))
        integrated_count = cursor.fetchone()[0]
        logger.info(f"integrated_objects 테이블 레코드 수: {integrated_count}")
        
        # 요약 데이터 샘플 조회
        cursor.execute("""
            SELECT original_id, object_type, summary 
            FROM integrated_objects 
            WHERE company_id = ? AND platform = ? 
            LIMIT 3
        """, (company_id, platform))
        
        samples = cursor.fetchall()
        logger.info("📝 요약 샘플:")
        for original_id, object_type, summary in samples:
            if summary:
                logger.info(f"  - {object_type} {original_id}: {summary[:100]}...")
            else:
                logger.info(f"  - {object_type} {original_id}: [요약 없음]")
        
        db.disconnect()
        
        # 벡터 DB 확인
        new_count = vector_db.count(company_id=company_id)
        logger.info(f"벡터 DB 문서 수 (company_id={company_id}): {new_count}")
        
        # 검색 테스트
        logger.info("🔍 검색 테스트 중...")
        
        # 검색 쿼리를 임베딩으로 변환
        from core.search.embeddings.embedder import embed_documents
        query_text = "로그인 문제"
        query_embedding = embed_documents([query_text])[0]
        
        search_results = vector_db.search(
            query_embedding=query_embedding,
            top_k=3,
            company_id=company_id
        )
        
        logger.info(f"검색 결과 수: {len(search_results)}")
        for i, result in enumerate(search_results):
            # 검색 결과가 문자열인지 딕셔너리인지 확인
            if isinstance(result, str):
                text_content = result[:100] + "..." if len(result) > 100 else result
                logger.info(f"  결과 {i+1}: {text_content}")
            elif isinstance(result, dict):
                result_id = result.get('id', 'N/A')
                score = result.get('score', 0)
                logger.info(f"  결과 {i+1}: ID={result_id}, 스코어: {score:.3f}")
            else:
                logger.info(f"  결과 {i+1}: {str(result)}")
        
        logger.info("✅ 새로운 파이프라인 테스트 완료!")
        
    except Exception as e:
        logger.error(f"❌ 파이프라인 테스트 실패: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(test_new_pipeline())
