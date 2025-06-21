#!/usr/bin/env python3
"""
Qdrant Cloud 데이터 초기화 스크립트
"""

import logging

from core.database.vectordb import vector_db

logging.basicConfig(level=logging.INFO)

def main():
    print('🗑️ Qdrant Cloud 데이터 초기화 중...')
    try:
        # 기존 컬렉션 정보 확인
        info = vector_db.get_collection_info()
        if "error" not in info:
            points_count = info.get("points_count", 0)
            print(f'📊 초기화 전 포인트 수: {points_count:,}개')
        
        # 컬렉션 초기화 (삭제 후 재생성)
        success = vector_db.reset_collection(confirm=True, create_backup=False)
        
        if success:
            print('✅ Qdrant Cloud 데이터 초기화 완료')
            
            # 확인
            info = vector_db.get_collection_info()
            if "error" not in info:
                points_count = info.get("points_count", 0)
                print(f'📊 초기화 후 포인트 수: {points_count}개')
            else:
                print(f'⚠️ 초기화 후 컬렉션 정보 조회 실패: {info["error"]}')
        else:
            print('❌ 컬렉션 초기화 실패')
            
    except Exception as e:
        print(f'❌ 초기화 실패: {e}')

if __name__ == "__main__":
    main()
