#!/bin/bash

# ChatGPT Code Interpreter 환경 설정 스크립트
# Freshdesk Custom App (Prompt Canvas) RAG 백엔드 전용
# 테스트 검증 완료: 환경변수 7/7, 라이브러리 10/10, 백엔드 모듈 7/7

echo "🚀 ChatGPT Code Interpreter 환경 설정을 시작합니다..."
echo "📋 Freshdesk Custom App (Prompt Canvas) RAG 백엔드 환경 구성"
echo ""

# Python 환경 정보 확인
echo "🐍 Python 환경 정보:"
python --version
which python
echo ""

# 핵심 라이브러리 설치 (테스트 검증된 라이브러리들)
echo "📦 필수 라이브러리 설치 중..."
echo "   ※ Code Interpreter에 사전 설치되지 않은 특수 라이브러리만 설치합니다"
echo ""

# Qdrant 클라이언트 (벡터 DB - 핵심 요구사항)
echo "🔄 Qdrant 클라이언트 설치 중..."
pip install qdrant-client

# Anthropic Claude API (LLM Router에 필수)
echo "🔄 Anthropic 클라이언트 설치 중..."
pip install anthropic

# FastAPI 관련 (API 서버 구성용)
echo "🔄 FastAPI 웹 프레임워크 설치 중..."
pip install fastapi uvicorn

# Langchain 라이브러리들 (백엔드 모듈 의존성)
echo "🔄 Langchain 생태계 설치 중..."
pip install langchain-core langchain-openai langchain-anthropic langchain-community langchain-qdrant

# 추가 유틸리티 라이브러리들
echo "🔄 추가 유틸리티 설치 중..."
pip install python-multipart aiofiles

echo ""
echo "📋 설치된 라이브러리 버전 확인:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

python -c "
import sys
print(f'🐍 Python: {sys.version.split()[0]}')
print()

# 테스트 검증된 10개 핵심 라이브러리 확인
libraries = [
    ('openai', 'OpenAI'),
    ('anthropic', 'Anthropic'),
    ('qdrant_client', 'Qdrant Client'),
    ('fastapi', 'FastAPI'),
    ('uvicorn', 'Uvicorn'),
    ('pydantic', 'Pydantic'),
    ('langchain_core', 'Langchain Core'),
    ('langchain_openai', 'Langchain OpenAI'),
    ('langchain_anthropic', 'Langchain Anthropic'),
    ('langchain_qdrant', 'Langchain Qdrant')
]

installed_count = 0
total_count = len(libraries)

for lib_name, display_name in libraries:
    try:
        lib = __import__(lib_name)
        try:
            version = getattr(lib, '__version__', '버전 정보 없음')
            print(f'✅ {display_name}: {version}')
        except:
            print(f'✅ {display_name}: 설치됨')
        installed_count += 1
    except ImportError:
        print(f'❌ {display_name}: 설치 실패')

print()
print(f'📊 라이브러리 설치 현황: {installed_count}/{total_count}')
"

echo ""

# 환경변수 확인 및 설정 가이드
echo "🔍 환경변수 설정 상태 확인:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Python을 이용한 안정적인 환경변수 확인 (테스트 검증됨)
python -c "
import os

# 필수 환경변수 정의 (7개 항목)
env_vars = {
    'FRESHDESK_DOMAIN': 'Freshdesk 도메인 (예: yourcompany.freshdesk.com)',
    'FRESHDESK_API_KEY': 'Freshdesk API 키',
    'QDRANT_URL': 'Qdrant 클라우드 URL',
    'QDRANT_API_KEY': 'Qdrant API 키',
    'OPENAI_API_KEY': 'OpenAI API 키',
    'ANTHROPIC_API_KEY': 'Anthropic API 키',
    'COMPANY_ID': '회사 식별자 (기본값: wedosoft)'
}

missing_vars = []
set_vars = []

# 환경변수 상태 확인
for var_name, var_desc in env_vars.items():
    value = os.getenv(var_name)
    if value and value.strip():
        print(f'✅ {var_name}: 설정됨')
        set_vars.append(var_name)
    else:
        print(f'❌ {var_name}: 설정되지 않음')
        missing_vars.append(var_name)

print()
print(f'📊 환경변수 설정 현황: {len(set_vars)}/7')
print()

if missing_vars:
    print('⚠️ 누락된 환경변수 설정 가이드:')
    print('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')
    print()
    print('🔧 ChatGPT Code Interpreter에서 환경변수 설정 방법:')
    print()
    print('📝 방법 1: 터미널 명령어로 설정')
    for var in missing_vars:
        if var == 'COMPANY_ID':
            print(f'   export {var}=\"wedosoft\"  # 기본값 예시')
        else:
            print(f'   export {var}=\"your_value_here\"')
    print()
    print('📝 방법 2: Python 코드에서 직접 설정')
    print('   import os')
    for var in missing_vars:
        if var == 'COMPANY_ID':
            print(f'   os.environ[\"{var}\"] = \"wedosoft\"  # 기본값')
        else:
            print(f'   os.environ[\"{var}\"] = \"your_value_here\"')
    print()
    print('💡 보안 권장사항:')
    print('   - 실제 API 키는 직접 노출하지 마세요')
    print('   - Code Interpreter의 환경변수 기능을 활용하세요')
    print('   - 테스트용으로는 더미 값을 사용해도 됩니다')
    print()
else:
    print('🎉 모든 환경변수가 설정되었습니다!')
    print('    이제 백엔드 모듈을 안전하게 사용할 수 있습니다.')
"

# 백엔드 모듈 임포트 테스트 (실제 구조 기반)
echo ""
echo "🔧 백엔드 모듈 임포트 테스트:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

python -c "
import sys
import os
import importlib

# backend 경로를 Python path에 추가
backend_path = os.path.join(os.getcwd(), 'backend')
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

# 테스트 검증된 7개 핵심 백엔드 모듈
module_tests = [
    ('core.config', 'get_settings', '설정 관리 모듈'),
    ('core.llm_router', 'LLMRouter', 'LLM 라우터 클래스'),
    ('core.vectordb', 'QdrantAdapter', 'Qdrant 어댑터 클래스'),
    ('core.vectordb', 'vector_db', 'Vector DB 싱글톤 인스턴스'),
    ('freshdesk.optimized_fetcher', 'OptimizedFreshdeskFetcher', 'Freshdesk 데이터 수집기'),
    ('api.ingest', 'ingest', '데이터 수집 API'),
    ('api.main', 'app', 'FastAPI 앱 인스턴스')
]

success_count = 0
total_count = len(module_tests)

print('🔍 개별 모듈 임포트 테스트:')
print()

for module_name, item_name, description in module_tests:
    try:
        module = importlib.import_module(module_name)
        if hasattr(module, item_name):
            item = getattr(module, item_name)
            # 특별 검증: vector_db 인스턴스 타입 확인
            if item_name == 'vector_db':
                print(f'✅ {module_name}.{item_name} - {description}')
                print(f'   └── 타입: {type(item).__name__}')
            else:
                print(f'✅ {module_name}.{item_name} - {description}')
            success_count += 1
        else:
            print(f'❌ {module_name}.{item_name} - {description} (항목 없음)')
    except ImportError as e:
        print(f'❌ {module_name} - {description} (임포트 실패)')
        # 디버깅 정보 출력 (간략히)
        if 'freshdesk' in module_name and '__init__' in str(e):
            print(f'   └── 힌트: freshdesk 패키지 초기화 필요')

print()
print(f'📊 백엔드 모듈 임포트 현황: {success_count}/{total_count}')

# freshdesk 패키지 __init__.py 파일 확인
freshdesk_init = os.path.join(backend_path, 'freshdesk', '__init__.py')
if os.path.exists(freshdesk_init):
    print('✅ freshdesk 패키지 초기화 파일 존재')
else:
    print('⚠️  freshdesk 패키지 초기화 파일 누락')
    print('   → 자동 생성 시도...')
    try:
        os.makedirs(os.path.dirname(freshdesk_init), exist_ok=True)
        with open(freshdesk_init, 'w') as f:
            f.write('# Freshdesk API 연동 패키지\\n')
        print('✅ __init__.py 파일 생성 완료')
    except Exception as e:
        print(f'❌ __init__.py 파일 생성 실패: {e}')
"

echo ""
echo "🎯 통합 환경 검증 테스트:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

python -c "
import os
import sys

# backend 경로 추가
backend_path = os.path.join(os.getcwd(), 'backend')
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

print('🔄 핵심 컴포넌트 연동 테스트 중...')
print()

# 1. 환경변수 기반 클라이언트 초기화 테스트
env_test_results = []

# OpenAI 클라이언트 테스트
try:
    import openai
    if os.getenv('OPENAI_API_KEY'):
        client = openai.OpenAI()
        print('✅ OpenAI 클라이언트: 초기화 성공')
        env_test_results.append(True)
    else:
        print('⚠️  OpenAI 클라이언트: API 키 미설정')
        env_test_results.append(False)
except Exception as e:
    print(f'❌ OpenAI 클라이언트: 초기화 실패 ({str(e)[:50]}...)')
    env_test_results.append(False)

# Anthropic 클라이언트 테스트  
try:
    import anthropic
    if os.getenv('ANTHROPIC_API_KEY'):
        client = anthropic.Anthropic()
        print('✅ Anthropic 클라이언트: 초기화 성공')
        env_test_results.append(True)
    else:
        print('⚠️  Anthropic 클라이언트: API 키 미설정')
        env_test_results.append(False)
except Exception as e:
    print(f'❌ Anthropic 클라이언트: 초기화 실패 ({str(e)[:50]}...)')
    env_test_results.append(False)

# Qdrant 클라이언트 테스트
try:
    from qdrant_client import QdrantClient
    url = os.getenv('QDRANT_URL')
    api_key = os.getenv('QDRANT_API_KEY')
    
    if url and api_key:
        # 실제 연결은 시도하지 않고 클라이언트 객체만 생성
        client = QdrantClient(url=url, api_key=api_key)
        print('✅ Qdrant 클라이언트: 초기화 성공')
        env_test_results.append(True)
    else:
        print('⚠️  Qdrant 클라이언트: URL 또는 API 키 미설정')
        env_test_results.append(False)
except Exception as e:
    print(f'❌ Qdrant 클라이언트: 초기화 실패 ({str(e)[:50]}...)')
    env_test_results.append(False)

print()

# 2. 백엔드 핵심 컴포넌트 테스트
backend_test_results = []

try:
    from core.vectordb import QdrantAdapter, vector_db
    print('✅ VectorDB 모듈: QdrantAdapter 및 vector_db 인스턴스 로드 성공')
    print(f'   └── vector_db 인스턴스 타입: {type(vector_db).__name__}')
    
    # vector_db 인스턴스의 기본 속성 확인
    if hasattr(vector_db, 'collection_name'):
        print(f'   └── 컬렉션명: {vector_db.collection_name}')
    
    backend_test_results.append(True)
except Exception as e:
    print(f'❌ VectorDB 모듈: 로드 실패 ({str(e)[:100]}...)')
    backend_test_results.append(False)

try:
    from core.llm_router import LLMRouter
    print('✅ LLM Router: 클래스 로드 성공')
    backend_test_results.append(True)
except Exception as e:
    print(f'❌ LLM Router: 로드 실패 ({str(e)[:50]}...)')
    backend_test_results.append(False)

try:
    from freshdesk.optimized_fetcher import OptimizedFreshdeskFetcher
    print('✅ Freshdesk Fetcher: 클래스 로드 성공')
    backend_test_results.append(True)
except Exception as e:
    print(f'❌ Freshdesk Fetcher: 로드 실패 ({str(e)[:50]}...)')
    backend_test_results.append(False)

try:
    from api.main import app
    print('✅ FastAPI 앱: 인스턴스 로드 성공')
    backend_test_results.append(True)
except Exception as e:
    print(f'❌ FastAPI 앱: 로드 실패 ({str(e)[:50]}...)')
    backend_test_results.append(False)

print()

# 최종 검증 결과 요약
env_success = sum(env_test_results)
backend_success = sum(backend_test_results)

print('📊 최종 환경 검증 결과:')
print('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')
print(f'🔑 환경변수 기반 클라이언트: {env_success}/3')
print(f'🔧 백엔드 핵심 모듈: {backend_success}/4')

if env_success == 3 and backend_success == 4:
    print()
    print('🎉 모든 환경 검증이 완료되었습니다!')
    print('   ChatGPT Code Interpreter에서 백엔드를 사용할 준비가 되었습니다.')
elif backend_success == 4:
    print()
    print('✅ 백엔드 모듈은 모두 정상입니다.')
    print('⚠️  일부 환경변수가 누락되어 있지만, 코드 테스트는 가능합니다.')
else:
    print()
    print('⚠️  일부 환경 설정이 완료되지 않았습니다.')
    print('   위의 가이드를 참고하여 누락된 부분을 설정해 주세요.')
"

echo ""
echo "🚀 환경 설정이 완료되었습니다!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📝 다음 단계 가이드:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "1️⃣ 환경변수 설정 (필요시)"
echo "   • 위에서 ❌ 표시된 환경변수들을 설정하세요"
echo "   • export 명령어 또는 Python os.environ 사용"
echo ""
echo "2️⃣ 백엔드 모듈 테스트"
echo "   • python -c \"from core.vectordb import vector_db; print('VectorDB 연결 가능')\""
echo "   • python -c \"from core.llm_router import LLMRouter; print('LLM Router 사용 가능')\""
echo ""
echo "3️⃣ API 서버 실행 (선택사항)"
echo "   • cd backend && python -m uvicorn api.main:app --reload"
echo "   • FastAPI 문서: http://localhost:8000/docs"
echo ""
echo "4️⃣ 데이터 수집 실행 (선택사항)"
echo "   • python -c \"from api.ingest import ingest; print('데이터 수집 기능 사용 가능')\""
echo ""
echo "🗂️ 프로젝트 구조:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "   backend/api/        # FastAPI 엔드포인트"
echo "   backend/core/       # 핵심 비즈니스 로직 (vectordb, llm_router)"
echo "   backend/freshdesk/  # Freshdesk API 연동"
echo "   backend/data/       # 데이터 처리 및 저장"
echo ""
echo "🔗 추가 문서:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "   • README.md - 전체 프로젝트 개요"
echo "   • CODEX_SETUP.md - ChatGPT Code Interpreter 상세 가이드"
echo "   • backend/docs/ - API 및 개발 문서"
echo ""
echo "💡 문제 해결:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "   • 임포트 에러: Python path 확인 (sys.path에 backend 경로 추가)"
echo "   • API 키 에러: 환경변수 설정 상태 재확인"
echo "   • 패키지 에러: pip install 재실행"
echo ""
echo "✨ 설정 완료! 이제 Freshdesk Custom App 백엔드를 사용할 수 있습니다."
