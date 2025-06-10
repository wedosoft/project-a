# ChatGPT Code Interpreter 환경 설정 가이드

이 문서는 ChatGPT Code Interpreter에서 Freshdesk Custom App 백엔드를 실행하기 위한 환경 설정 가이드입니다.

## 🚀 빠른 시작

### 1. 설정 스크립트 실행

```bash
# 프로젝트 루트에서 실행
./setup_codex_env.sh
```

### 2. 환경변수 설정

ChatGPT Code Interpreter에서는 다음과 같이 환경변수를 설정하세요:

```bash
# 필수 환경변수 설정
export FRESHDESK_DOMAIN="yourcompany.freshdesk.com"
export FRESHDESK_API_KEY="your_freshdesk_api_key"
export QDRANT_URL="https://your-cluster.cloud.qdrant.io"
export QDRANT_API_KEY="your_qdrant_api_key"
export ANTHROPIC_API_KEY="your_anthropic_api_key"
export COMPANY_ID="your_company_id"

# OPENAI_API_KEY는 Code Interpreter에서 자동 제공됩니다
```

### 3. Python에서 직접 설정 (선택사항)

```python
import os

# 환경변수 직접 설정
os.environ['FRESHDESK_DOMAIN'] = 'yourcompany.freshdesk.com'
os.environ['FRESHDESK_API_KEY'] = 'your_api_key'
os.environ['QDRANT_URL'] = 'https://your-cluster.cloud.qdrant.io'
os.environ['QDRANT_API_KEY'] = 'your_api_key'
os.environ['ANTHROPIC_API_KEY'] = 'your_api_key'
os.environ['COMPANY_ID'] = 'your_company_id'

print("✅ 환경변수 설정 완료")
```

## 🔧 Code Interpreter 환경 특성

### 장점
- **가상환경 불필요**: 컨테이너 기반으로 격리된 환경 제공
- **사전 설치된 라이브러리**: NumPy, Pandas, Matplotlib 등 기본 제공
- **OpenAI API 자동 연결**: OPENAI_API_KEY 자동 설정
- **일회성 환경**: 매번 깨끗한 환경으로 시작

### 고려사항
- **세션 종료 시 초기화**: 파일과 환경변수가 초기화됨
- **네트워크 제한**: 일부 외부 API 호출 제한 가능
- **패키지 설치**: 매 세션마다 특수 패키지 재설치 필요

## 📦 설치되는 라이브러리

`setup_codex_env.sh` 스크립트는 다음 라이브러리를 설치합니다:

### 🔧 핵심 백엔드 라이브러리
- **qdrant-client**: 벡터 데이터베이스 연결
- **anthropic**: Claude API 클라이언트
- **fastapi**: 웹 API 프레임워크
- **uvicorn**: ASGI 서버
- **python-multipart**: 파일 업로드 지원
- **aiofiles**: 비동기 파일 처리

### 🔗 Langchain 생태계
- **langchain-core**: Langchain 핵심 기능
- **langchain-openai**: OpenAI 모델 연동
- **langchain-anthropic**: Anthropic 모델 연동
- **langchain-qdrant**: Qdrant 벡터 저장소 연동

### 📊 데이터 처리
- **requests**: HTTP 클라이언트
- **numpy**: 수치 계산
- **python-dotenv**: 환경변수 관리

## 🧪 환경 설정 및 검증

### 자동 환경 검증

`setup_codex_env.sh` 스크립트는 다음과 같은 포괄적인 환경 검증을 수행합니다:

```bash
# 스크립트 실행
./setup_codex_env.sh

# 검증 항목:
# ✅ 환경변수 설정 상태 (7개 항목)
# ✅ 라이브러리 설치 상태 (13개 항목)  
# ✅ 백엔드 모듈 임포트 (7개 항목)
# ✅ 클라이언트 연결 테스트 (Qdrant, Anthropic)
```

### 수동 라이브러리 확인

```python
# 필수 라이브러리 import 테스트
try:
    import qdrant_client
    import anthropic
    import fastapi
    from langchain_core.runnables import Runnable
    from langchain_openai import ChatOpenAI
    print("✅ 모든 라이브러리 설치 확인 완료")
except ImportError as e:
    print(f"❌ 라이브러리 설치 오류: {e}")
```

### 백엔드 모듈 테스트

```python
# 백엔드 모듈 import 테스트
import sys
import os
sys.path.append(os.path.abspath('.'))

try:
    from backend.core.vectordb import QdrantAdapter
    from backend.freshdesk.fetcher import OptimizedFreshdeskFetcher
    from backend.api.ingest import ingest_data
    print("✅ 백엔드 모듈 임포트 성공")
except ImportError as e:
    print(f"❌ 백엔드 모듈 오류: {e}")
```

## 🔗 프로젝트 구조

Code Interpreter에서 실행할 수 있는 주요 스크립트:

```
backend/
├── api/main.py              # FastAPI 서버 실행
├── core/
│   ├── llm_router.py       # LLM 라우팅 로직
│   ├── vectordb.py         # Qdrant 연결
│   └── embedder.py         # 임베딩 생성
├── freshdesk/fetcher.py     # Freshdesk 데이터 수집
└── test_import.py          # 라이브러리 import 테스트
```

## 🚨 보안 주의사항

- **API 키 보안**: 실제 API 키는 환경변수로만 설정하고 코드에 하드코딩 금지
- **로그 출력 주의**: API 키가 로그에 출력되지 않도록 마스킹 처리
- **임시 파일 정리**: 민감한 데이터가 포함된 임시 파일은 사용 후 삭제

## 📝 사용 예시

### 1. 환경 설정 및 서버 실행

```python
# 1. 환경변수 설정
import os
os.environ['COMPANY_ID'] = 'wedosoft'

# 2. 모듈 import
import sys
sys.path.append('/path/to/backend')

from api.main import app
from core.settings import Settings

# 3. 설정 확인
settings = Settings()
print(f"✅ 설정 로드 완료: {settings.company_id}")
```

### 2. 백엔드 시스템 실행

```python
# 백엔드 모듈 경로 추가
import sys
import os
sys.path.append(os.path.abspath('.'))

# FastAPI 서버 시작
from backend.api.main import app
import uvicorn

# 개발 서버 실행 (백그라운드)
uvicorn.run(app, host="0.0.0.0", port=8000)
```

### 3. 벡터 검색 및 LLM 테스트

```python
# 벡터 DB 및 LLM 연동 테스트
from backend.core.vectordb import vector_db
from backend.core.llm_router import LLM_ROUTER

# 벡터 검색 테스트  
query = "사용자 로그인 문제"
search_results = vector_db.search(
    query_text=query,
    collection_name="tickets",
    company_id="wedosoft",
    limit=5
)

print(f"✅ 벡터 검색 결과: {len(search_results)}개 문서 발견")

# LLM 응답 생성 테스트
llm_router = LLM_ROUTER()
response = llm_router.generate_response(
    prompt="티켓 요약을 생성해주세요",
    model="claude-3-sonnet"
)

print(f"✅ LLM 응답 생성: {response[:100]}...")
```

## 🎯 Langchain 아키텍처 활용

Code Interpreter 환경에서는 Langchain을 활용한 고급 LLM 기능을 바로 테스트할 수 있습니다:

### Langchain Expression Language (LCEL) 테스트

```python
from langchain_core.runnables import RunnableParallel, RunnableSequence
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic

# 병렬 LLM 체인 구성
def create_parallel_chain():
    llm_openai = ChatOpenAI(model="gpt-4")
    llm_claude = ChatAnthropic(model="claude-3-sonnet-20240229")
    
    parallel_chain = RunnableParallel({
        "openai_response": llm_openai,
        "claude_response": llm_claude
    })
    
    return parallel_chain

# 사용 예시
chain = create_parallel_chain()
result = chain.invoke({"input": "티켓 요약을 생성해주세요"})
print(f"OpenAI: {result['openai_response']}")
print(f"Claude: {result['claude_response']}")
```

### Qdrant 벡터 저장소 연동

```python
from langchain_qdrant import QdrantVectorStore
from langchain_openai import OpenAIEmbeddings
from qdrant_client import QdrantClient

# Langchain-Qdrant 연동
def setup_langchain_qdrant():
    client = QdrantClient(
        url=os.getenv("QDRANT_URL"),
        api_key=os.getenv("QDRANT_API_KEY")
    )
    
    embeddings = OpenAIEmbeddings()
    
    vector_store = QdrantVectorStore(
        client=client,
        collection_name="tickets",
        embeddings=embeddings
    )
    
    return vector_store

# 벡터 검색 및 유사도 검색
vector_store = setup_langchain_qdrant()
docs = vector_store.similarity_search("로그인 문제", k=5)
print(f"검색된 문서: {len(docs)}개")
```

## 🆘 문제 해결

### 1. 라이브러리 설치 실패
```bash
# pip 업그레이드 후 재시도
pip install --upgrade pip

# 개별 라이브러리 설치 테스트
pip install qdrant-client anthropic fastapi uvicorn
pip install langchain-core langchain-openai langchain-anthropic langchain-qdrant

# 네트워크 문제 시 미러 서버 사용
pip install -i https://pypi.org/simple/ qdrant-client
```

### 2. 환경변수 설정 확인
```bash
# 현재 설정된 환경변수 확인
env | grep -E "(FRESHDESK|QDRANT|ANTHROPIC|COMPANY_ID|OPENAI)"

# Python에서 환경변수 확인
python -c "import os; print({k:v for k,v in os.environ.items() if any(x in k for x in ['FRESHDESK','QDRANT','ANTHROPIC','COMPANY_ID','OPENAI'])})"
```

### 3. 백엔드 모듈 임포트 실패
```python
# 모듈 경로 확인 및 추가
import sys
import os

# 프로젝트 루트를 Python 경로에 추가
project_root = os.path.abspath('.')
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# __init__.py 파일 존재 확인
required_files = [
    'backend/__init__.py',
    'backend/core/__init__.py', 
    'backend/freshdesk/__init__.py',
    'backend/api/__init__.py'
]

for file_path in required_files:
    if not os.path.exists(file_path):
        print(f"❌ 누락된 파일: {file_path}")
        # 빈 __init__.py 파일 생성
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        open(file_path, 'a').close()
        print(f"✅ 생성됨: {file_path}")
```

### 4. API 연결 테스트
```python
# 기본 네트워크 연결 테스트
import requests

try:
    response = requests.get("https://httpbin.org/get", timeout=10)
    print(f"✅ 네트워크 연결: {response.status_code}")
except Exception as e:
    print(f"❌ 네트워크 오류: {e}")

# Qdrant 클라우드 연결 테스트
try:
    from qdrant_client import QdrantClient
    
    client = QdrantClient(
        url=os.getenv("QDRANT_URL"),
        api_key=os.getenv("QDRANT_API_KEY"),
        timeout=30
    )
    
    collections = client.get_collections()
    print(f"✅ Qdrant 연결: {len(collections.collections)}개 컬렉션")
except Exception as e:
    print(f"❌ Qdrant 연결 실패: {e}")
```

## 🔄 업데이트 주기

- **스크립트 개선**: 새로운 라이브러리 추가 시 스크립트 업데이트
- **환경변수 추가**: 새로운 API 연동 시 환경변수 목록 업데이트
- **문서 동기화**: 프로젝트 구조 변경 시 문서 업데이트

---

💡 **팁**: Code Interpreter에서는 매 세션마다 환경 설정이 초기화되므로, 자주 사용하는 설정은 스크립트로 저장해두시기 바랍니다.
