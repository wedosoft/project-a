#!/usr/bin/env python3
"""
Qdrant Cloud 저장 상태 확인 스크립트 (수정 버전)

실제 Qdrant Cloud에 저장된 데이터 현황을 확인하고 리포트
환경변수 로딩 순서를 수정하여 안정성 향상
"""

import logging
import os
import sys
from pathlib import Path

# 프로젝트 루트를 Python path에 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 환경변수를 먼저 로드
from dotenv import load_dotenv

# .env 파일 경로 명시적 지정
env_path = project_root / ".env"
print(f"📂 .env 파일 경로: {env_path}")
print(f"📁 .env 파일 존재 여부: {env_path.exists()}")

# 환경변수 로드
load_dotenv(dotenv_path=env_path)

# 환경변수 로드 확인
qdrant_url = os.getenv("QDRANT_URL")
openai_key = os.getenv("OPENAI_API_KEY")

print(f"🔍 기본 환경변수 확인:")
print(f"   QDRANT_URL: {'설정됨' if qdrant_url else '❌ 미설정'}")
print(f"   OPENAI_API_KEY: {'설정됨' if openai_key else '❌ 미설정'}")
print()

# 환경변수 로드 후에만 core 모듈 import
if qdrant_url and openai_key:
    try:
        from core.vectordb import QdrantAdapter
        print("✅ core.vectordb 모듈 로드 성공")
    except Exception as e:
        print(f"❌ core.vectordb 모듈 로드 실패: {e}")
        sys.exit(1)
else:
    print("❌ 필수 환경변수가 설정되지 않아 종료합니다.")
    sys.exit(1)

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def main():
    """Qdrant Cloud 저장 상태 확인"""
    
    print("=" * 60)
    print("🔍 Qdrant Cloud 저장 상태 확인")
    print("=" * 60)
    
    # 환경변수 확인
    print(f"🔧 환경변수 디버깅 정보:")
    print(f"   현재 작업 디렉터리: {os.getcwd()}")
    print(f"   스크립트 위치: {project_root}")
    print(f"   .env 파일 경로: {env_path}")
    print()
    
    qdrant_url = os.getenv("QDRANT_URL")
    qdrant_api_key = os.getenv("QDRANT_API_KEY")
    
    print(f"🔍 환경변수 로드 결과:")
    print(f"   QDRANT_URL: {qdrant_url[:50] if qdrant_url else 'None'}...")
    print(f"   QDRANT_API_KEY: {'설정됨' if qdrant_api_key else 'None'}")
    print()
    
    if not qdrant_url or not qdrant_api_key:
        print("❌ 환경변수가 설정되지 않았습니다:")
        print(f"   QDRANT_URL: {'✓ 설정됨' if qdrant_url else '❌ 미설정'}")
        print(f"   QDRANT_API_KEY: {'✓ 설정됨' if qdrant_api_key else '❌ 미설정'}")
        return False
    
    print(f"✅ 환경변수 확인 완료")
    print(f"   Qdrant URL: {qdrant_url[:50]}...")
    print(f"   API Key: {'*' * 20}")
    print()
    
    # 각 컬렉션 확인
    collections = ["documents", "faqs"]
    
    total_points = 0
    
    for collection_name in collections:
        try:
            print(f"📊 컬렉션 '{collection_name}' 확인 중...")
            
            # QdrantAdapter 초기화
            vector_db = QdrantAdapter(collection_name=collection_name)
            
            # 컬렉션 정보 조회
            info = vector_db.get_collection_info()
            
            if "error" in info:
                print(f"   ❌ 오류 발생: {info['error']}")
                continue
            
            points_count = info.get("points_count", 0)
            total_points += points_count
            
            print(f"   ✅ 컬렉션명: {info['name']}")
            print(f"   📈 저장된 포인트 수: {points_count:,}개")
            print(f"   🔧 벡터 크기: {info['vector_size']}")
            print(f"   📊 상태: {info['status']}")
            
            if points_count > 0:
                print(f"   ✅ 데이터가 정상적으로 저장되어 있습니다!")
                
                # 샘플 데이터 몇 개 조회해보기
                try:
                    from core.embedder import Embedder
                    
                    # 임베딩 생성 후 검색
                    embedder = Embedder()
                    query_text = "티켓 문의"
                    query_embedding = embedder.generate_embedding(query_text)
                    
                    # 올바른 파라미터로 search 메서드 호출
                    sample_data = vector_db.search(
                        query_embedding=query_embedding,
                        top_k=3,
                        company_id="kyexpert"
                    )
                    
                    if sample_data and len(sample_data) > 0:
                        print(f"   📋 샘플 데이터 미리보기:")
                        for i, doc in enumerate(sample_data[:2], 1):
                            content = doc.get('content', '')[:100]
                            score = doc.get('score', 0)
                            print(f"      {i}. Score: {score:.3f} | {content}...")
                    else:
                        print(f"   ⚠️  검색 테스트 실패 - 데이터 접근 불가")
                        
                except Exception as search_error:
                    print(f"   ⚠️  검색 테스트 중 오류: {search_error}")
            else:
                print(f"   ⚠️  저장된 데이터가 없습니다.")
            
            print()
            
        except Exception as e:
            print(f"   ❌ 컬렉션 '{collection_name}' 확인 중 오류 발생: {e}")
            print()
    
    print("=" * 60)
    print(f"📊 전체 요약")
    print(f"   총 저장된 포인트 수: {total_points:,}개")
    
    if total_points > 0:
        print("   ✅ Qdrant Cloud에 데이터가 정상적으로 저장되어 있습니다!")
        print("   💡 RAG 시스템을 사용할 준비가 완료되었습니다.")
    else:
        print("   ⚠️  Qdrant Cloud에 저장된 데이터가 없습니다.")
        print("   💡 데이터 수집 및 임베딩 저장을 실행해주세요.")
        print()
        print("   🚀 데이터 수집 명령어:")
        print("      python -m data.freshdesk_fetcher")
        print("      또는")
        print("      python freshdesk_full_data/run_collection.py")
    
    print("=" * 60)
    
    return total_points > 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
