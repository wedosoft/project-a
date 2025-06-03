#!/usr/bin/env python3
"""
Qdrant Cloud 저장 상태 확인 스크립트

실제 Qdrant Cloud에 저장된 데이터 현황을 확인하고 리포트
"""

import os
import sys
from pathlib import Path

# 프로젝트 루트를 Python path에 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import logging

from dotenv import load_dotenv

# 환경변수 로드 - 명시적으로 .env 파일 경로를 지정
dotenv_path = os.path.join(project_root, ".env")
load_dotenv(dotenv_path=dotenv_path)

# .env가 로드된 후 QdrantAdapter 임포트
from core.vectordb import QdrantAdapter

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
    qdrant_url = os.getenv("QDRANT_URL")
    qdrant_api_key = os.getenv("QDRANT_API_KEY")
    
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
    collections = ["documents"]
    
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
    else:
        print("   ⚠️  Qdrant Cloud에 저장된 데이터가 없습니다.")
        print("   💡 데이터 수집 및 임베딩 저장을 실행해주세요.")
    
    print("=" * 60)
    
    return total_points > 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
