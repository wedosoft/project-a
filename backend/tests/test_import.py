#!/usr/bin/env python3
"""LLMRouter 임포트 테스트 스크립트"""

try:
    from core.llm_router import LLMRouter
    print('✅ LLMRouter import successful')
except Exception as e:
    print(f'❌ Import error: {e}')
    import traceback
    traceback.print_exc()
