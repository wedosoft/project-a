#!/usr/bin/env python3
"""
환경변수 디버깅 스크립트

.env 파일과 실제 환경변수 값이 다른 이유를 진단합니다.
"""

import os
import sys

# 백엔드 경로 추가
sys.path.append('/Users/alan/GitHub/project-a/backend')

def debug_environment_variables():
    """환경변수 디버깅"""
    
    print("🔍 환경변수 디버깅 시작\n")
    
    # 1. .env 파일 존재 확인
    env_file_path = "/Users/alan/GitHub/project-a/backend/.env"
    if os.path.exists(env_file_path):
        print(f"✅ .env 파일 존재: {env_file_path}")
    else:
        print(f"❌ .env 파일 없음: {env_file_path}")
        return
    
    # 2. .env 파일 내용에서 USE_ORM 찾기
    print("\n📋 .env 파일 내용 확인:")
    with open(env_file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        for i, line in enumerate(lines, 1):
            if 'USE_ORM' in line and not line.strip().startswith('#'):
                print(f"   라인 {i}: {line.strip()}")
    
    # 3. 시스템 환경변수 확인
    print("\n🖥️ 시스템 환경변수 확인:")
    use_orm_env = os.getenv('USE_ORM')
    print(f"   os.getenv('USE_ORM'): {use_orm_env}")
    print(f"   타입: {type(use_orm_env)}")
    
    # 4. python-dotenv 로딩 테스트
    print("\n📦 python-dotenv 로딩 테스트:")
    try:
        from dotenv import load_dotenv
        
        # 기존 환경변수 백업
        original_use_orm = os.environ.get('USE_ORM')
        print(f"   로딩 전 USE_ORM: {original_use_orm}")
        
        # .env 파일 로딩
        result = load_dotenv(env_file_path, override=True)
        print(f"   load_dotenv 결과: {result}")
        
        # 로딩 후 확인
        after_use_orm = os.environ.get('USE_ORM')
        print(f"   로딩 후 USE_ORM: {after_use_orm}")
        
    except ImportError:
        print("   ❌ python-dotenv가 설치되지 않음")
    except Exception as e:
        print(f"   ❌ dotenv 로딩 오류: {e}")
    
    # 5. MigrationLayer 초기화 과정 확인
    print("\n🔧 MigrationLayer 초기화 과정:")
    try:
        # 환경변수 설정 전
        print(f"   초기화 전 USE_ORM: {os.getenv('USE_ORM')}")
        
        # MigrationLayer 초기화
        from core.migration_layer import MigrationLayer
        migration = MigrationLayer()
        print(f"   MigrationLayer.use_orm: {migration.use_orm}")
        
        # 직접 계산해보기
        use_orm_calc = os.getenv('USE_ORM', 'false').lower() == 'true'
        print(f"   직접 계산 결과: {use_orm_calc}")
        
    except Exception as e:
        print(f"   ❌ MigrationLayer 테스트 오류: {e}")
    
    # 6. 테스트 스크립트 환경변수 설정 확인
    print("\n🧪 테스트 스크립트 환경변수 설정:")
    print("   test_orm_compatibility.py에서 설정:")
    print("   os.environ['USE_ORM'] = 'true'")
    print("   이것이 .env 파일 설정을 override했을 가능성!")

if __name__ == "__main__":
    debug_environment_variables()
