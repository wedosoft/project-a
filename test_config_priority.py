#!/usr/bin/env python3
"""환경변수 vs config.py 기본값 테스트"""

import os
import sys

sys.path.append('/Users/alan/GitHub/project-a/backend')

from core.config import get_settings


def test_config_priority():
    print("🔍 환경변수 우선순위 테스트")
    print("=" * 50)
    
    settings = get_settings()
    
    # .env 파일의 값들
    env_values = {
        'LLM_GLOBAL_TIMEOUT': os.getenv('LLM_GLOBAL_TIMEOUT'),
        'LLM_GEMINI_TIMEOUT': os.getenv('LLM_GEMINI_TIMEOUT'), 
        'LLM_ANTHROPIC_TIMEOUT': os.getenv('LLM_ANTHROPIC_TIMEOUT'),
        'HOST': os.getenv('HOST'),
        'PORT': os.getenv('PORT')
    }
    
    # 실제 로드된 값들
    actual_values = {
        'LLM_GLOBAL_TIMEOUT': settings.LLM_GLOBAL_TIMEOUT,
        'LLM_GEMINI_TIMEOUT': settings.LLM_GEMINI_TIMEOUT,
        'LLM_ANTHROPIC_TIMEOUT': settings.LLM_ANTHROPIC_TIMEOUT,
        'HOST': settings.HOST,
        'PORT': settings.PORT
    }
    
    # config.py 기본값들
    default_values = {
        'LLM_GLOBAL_TIMEOUT': 10.0,
        'LLM_GEMINI_TIMEOUT': 12.0,
        'LLM_ANTHROPIC_TIMEOUT': 8.0,
        'HOST': '0.0.0.0',
        'PORT': 8000
    }
    
    for key in env_values:
        print(f"\n📝 {key}:")
        print(f"   .env 파일: {env_values[key]}")
        print(f"   config.py 기본값: {default_values[key]}")
        print(f"   ✅ 실제 사용값: {actual_values[key]}")
        
        if env_values[key]:
            if str(actual_values[key]) == str(env_values[key]):
                print(f"   ✅ 환경변수 우선 적용됨")
            else:
                print(f"   ❌ 환경변수가 무시됨")
        else:
            if actual_values[key] == default_values[key]:
                print(f"   ✅ 기본값 적용됨")
            else:
                print(f"   ❌ 예상과 다른 값")

if __name__ == "__main__":
    test_config_priority()
