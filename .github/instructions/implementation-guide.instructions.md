---
applyTo: "**"
---

# 🛠️ 구현 가이드 & 코딩 패턴 지침서

*모델 참조 최적화 버전 - 구체적 구현/코딩/디버깅 가이드 전용*

## 🎯 구현 목표

**Freshdesk Custom App의 실무 중심 구현 방법론 및 코딩 패턴**

- **실용적 코딩 패턴**: MVP 원칙에 따른 간단하고 실용적인 구현
- **성능 최적화**: 비동기 처리 및 캐싱 전략
- **에러 처리**: 견고한 에러 처리 및 복구 로직
- **디버깅 지원**: 체계적인 디버깅 및 모니터링

---

## ⚠️ **코딩 철칙 (절대 준수 필수)**

### 기존 코드 재활용 의무
- **90% 이상 기존 코드 재활용**: 새로운 코딩은 최소한으로 제한
- **레거시 로직 보존**: 안정적으로 작동하던 기존 코드의 핵심 로직 유지
- **점진적 개선**: 전면 재작성 대신 기존 코드를 다듬어 사용
- **검증된 패턴 유지**: 기존 비즈니스 로직, 데이터 처리 방식 최대한 보존

### 리팩토링 접근 방식
```python
# ❌ 잘못된 접근 - 전면 재작성
def new_ticket_processor():
    # 완전히 새로운 로직으로 재작성
    pass

# ✅ 올바른 접근 - 기존 코드 개선
def improved_ticket_processor():
    # 기존 process_ticket() 함수 로직을 기반으로
    # 성능 최적화 요소만 추가
    existing_logic = process_ticket()  # 기존 함수 재사용
    # 최소한의 개선사항만 추가
    return enhanced_result
```

---

## 🎨 Freshdesk FDK (Frontend Development Kit) 구현

### FDK 개발 환경 구성

**환경 요구사항**:
- **Node.js**: v14.x ~ v18.x (최신 버전 호환성 주의)
- **FDK CLI**: `npm install -g @freshworks/fdk`
- **개발 명령어**: `fdk run` (로컬 서버), `fdk validate` (검증)

### FDK 주요 이슈 및 해결패턴

#### 1. JavaScript 구문 오류 해결

```javascript
// ❌ 잘못된 패턴 - 중괄호 매칭 오류
function smartDomainParsing(domain) {
  if (domain.includes(".freshdesk.com")) {
    return domain.split(".")[0];
  }
} // ← 추가 중괄호 시 오류

// ✅ 올바른 패턴 - 명확한 구조
function smartDomainParsing(domain) {
  if (domain.includes(".freshdesk.com")) {
    return domain.split(".")[0];
  }
  return domain;
}
```

#### 2. FDK 앱 초기화 패턴

```javascript
// app.js - 메인 앱 진입점
class AIAssistantApp {
  constructor() {
    this.config = null;
    this.ticketInfo = null;
    this.backendClient = null;
    this.isInitialized = false;
  }

  async initialize() {
    try {
      // 1. Freshdesk 설정 및 티켓 정보 병렬 로드
      const [config, ticketInfo] = await Promise.all([
        this.getFreshdeskConfig(),
        this.getCurrentTicketInfo(),
      ]);

      this.config = config;
      this.ticketInfo = ticketInfo;

      // 2. 백엔드 API 클라이언트 초기화
      this.backendClient = new BackendAPIClient(config);

      // 3. 초기 데이터 로드 (/init 호출)
      await this.loadInitialData();

      // 4. UI 렌더링
      this.renderUI();

      this.isInitialized = true;
      console.log("AI Assistant 앱 초기화 완료");
    } catch (error) {
      console.error("앱 초기화 실패:", error);
      this.renderErrorState(error);
    }
  }

  async getFreshdeskConfig() {
    const context = await window.parent.app.instance.context();
    return {
      domain: `${context.account.subdomain}.freshdesk.com`,
      apiKey: context.account.apiKey,
      userId: context.user.id,
      accountId: context.account.id,
    };
  }

  async getCurrentTicketInfo() {
    const ticketData = await window.parent.app.data.get("ticket");
    return {
      id: ticketData.ticket.id,
      subject: ticketData.ticket.subject,
      description: ticketData.ticket.description_text || ticketData.ticket.description,
      status: ticketData.ticket.status,
      priority: ticketData.ticket.priority,
    };
  }
}
```

#### 3. 백엔드 API 연동 클라이언트

```javascript
// api-client.js - 백엔드 통신 전담 클래스
class BackendAPIClient {
  constructor(freshdeskConfig) {
    this.config = freshdeskConfig;
    this.baseURL = this.getBackendURL();
    this.defaultHeaders = {
      "Content-Type": "application/json",
      "X-Freshdesk-Domain": this.config.domain,
      "X-Freshdesk-API-Key": this.config.apiKey,
      "X-User-ID": this.config.userId,
      "X-Account-ID": this.config.accountId,
    };
  }

  // 백엔드 API 호출 통합 메서드
  async apiCall(endpoint, options = {}) {
    const response = await fetch(`${this.baseURL}${endpoint}`, {
      headers: { ...this.defaultHeaders, ...options.headers },
      ...options
    });
    
    if (!response.ok) {
      throw new Error(`API 호출 실패: ${response.status} ${response.statusText}`);
    }
    
    return response.json();
  }

  // 초기 데이터 로드
  async init(ticketId) {
    return this.apiCall(`/init/${ticketId}`);
  }

  // AI 채팅 쿼리
  async query(ticketId, queryData) {
    return this.apiCall('/query', {
      method: 'POST',
      body: JSON.stringify({ ticket_id: ticketId, ...queryData })
    });
  }
}
```

#### 4. iparams.html 보안 패턴

```html
<!-- ❌ 보안 위험 - 하드코딩된 값 -->
<input
  type="text"
  id="freshdesk_domain"
  value="wedosoft.freshdesk.com"
  placeholder="your-domain.freshdesk.com"
/>

<!-- ✅ 안전한 패턴 - 빈 기본값과 검증 -->
<input
  type="text"
  id="freshdesk_domain"
  value=""
  placeholder="your-domain.freshdesk.com"
  required
  pattern="[a-zA-Z0-9-]+\.freshdesk\.com"
/>
```

#### 5. FDK 디버깅 명령어

```bash
# FDK 검증 및 상세 오류 확인
fdk validate --verbose

# 로그 레벨을 높여서 상세 디버그 정보 확인
fdk run --log-level debug

# 브라우저 개발자 도구에서 콘솔 오류 확인 (중요!)
```

---

## �🏗️ 핵심 구현 패턴

### 1. 비동기 프로그래밍 패턴

**기본 원칙**:
- **모든 I/O 작업은 비동기**로 처리
- **동시성 제한**으로 리소스 보호
- **에러 처리 중심** 설계

```python
# 비동기 HTTP 클라이언트 패턴
import asyncio
import aiohttp
from typing import List, Dict, Any, Optional
import logging

class AsyncHTTPClient:
    """
    비동기 HTTP 클라이언트 - 동시성 제한 및 에러 처리 포함
    """
    
    def __init__(self, max_concurrent: int = 10, timeout: int = 30):
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def __aenter__(self):
        """컨텍스트 매니저 진입 - 세션 생성"""
        self.session = aiohttp.ClientSession(timeout=self.timeout)
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """컨텍스트 매니저 종료 - 세션 정리"""
        if self.session:
            await self.session.close()
            
    async def fetch_with_retry(
        self, 
        url: str, 
        headers: Dict[str, str] = None,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        재시도 로직이 포함된 HTTP 요청
        
        Args:
            url: 요청 URL
            headers: HTTP 헤더
            max_retries: 최대 재시도 횟수
            
        Returns:
            JSON 응답 데이터
            
        Raises:
            aiohttp.ClientError: HTTP 요청 실패 시
        """
        async with self.semaphore:  # 동시성 제한
            for attempt in range(max_retries + 1):
                try:
                    async with self.session.get(url, headers=headers) as response:
                        response.raise_for_status()
                        return await response.json()
                        
                except aiohttp.ClientError as e:
                    if attempt == max_retries:
                        logging.error(f"HTTP 요청 최종 실패: {url}, 오류: {e}")
                        raise
                    
                    # 지수적 백오프
                    wait_time = 2 ** attempt
                    logging.warning(f"HTTP 요청 재시도 {attempt + 1}/{max_retries}: {url}, {wait_time}초 대기")
                    await asyncio.sleep(wait_time)

# 사용 예시
async def collect_freshdesk_tickets(api_key: str, domain: str) -> List[Dict[str, Any]]:
    """Freshdesk 티켓 수집 실제 구현"""
    headers = {"Authorization": f"Basic {api_key}"}
    
    async with AsyncHTTPClient(max_concurrent=5) as client:
        # 페이징 처리
        tickets = []
        page = 1
        
        while True:
            url = f"https://{domain}.freshdesk.com/api/v2/tickets?page={page}"
            
            try:
                response = await client.fetch_with_retry(url, headers)
                
                if not response:  # 빈 페이지이면 종료
                    break
                    
                tickets.extend(response)
                page += 1
                
                # Rate limit 대응 (Freshdesk API 제한)
                await asyncio.sleep(0.1)
                
            except aiohttp.ClientError:
                logging.error(f"티켓 수집 실패: 페이지 {page}")
                break
                
        return tickets
```

### 2. LLM 호출 최적화 패턴

**특징**:
- **배치 처리**로 비용 절약
- **캐싱**으로 중복 호출 방지
- **스트리밍** 지원

```python
# LLM 클라이언트 최적화 패턴
import openai
from typing import List, Dict, Any, Optional, AsyncGenerator
import hashlib
import json
from functools import wraps
import aioredis
import logging

class LLMManager:
    """
    LLM 호출 최적화 매니저 - 캐싱, 배치 처리, 스트리밍 지원
    """
    
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.client = openai.AsyncOpenAI()
        self.redis_client: Optional[aioredis.Redis] = None
        self.redis_url = redis_url
        
    async def __aenter__(self):
        """Redis 연결 설정"""
        self.redis_client = await aioredis.from_url(self.redis_url)
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Redis 연결 정리"""
        if self.redis_client:
            await self.redis_client.close()
            
    def _generate_cache_key(self, prompt: str, model: str) -> str:
        """캐시 키 생성 - 프롬프트와 모델 기반 해시"""
        content = f"{model}:{prompt}"
        return f"llm_cache:{hashlib.md5(content.encode()).hexdigest()}"
        
    async def _get_cached_response(self, cache_key: str) -> Optional[str]:
        """캐시된 응답 조회"""
        if not self.redis_client:
            return None
            
        try:
            cached = await self.redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception as e:
            logging.warning(f"캐시 조회 실패: {e}")
            
        return None
        
    async def _set_cached_response(self, cache_key: str, response: str, ttl: int = 3600):
        """응답 캐싱 - 1시간 TTL"""
        if not self.redis_client:
            return
            
        try:
            await self.redis_client.setex(
                cache_key, 
                ttl, 
                json.dumps(response)
            )
        except Exception as e:
            logging.warning(f"캐시 저장 실패: {e}")
            
    async def summarize_ticket(
        self, 
        ticket_content: str, 
        model: str = "gpt-3.5-turbo"
    ) -> Dict[str, Any]:
        """
        티켓 요약 생성 - 캐싱 적용
        
        Args:
            ticket_content: 티켓 내용 (병합된 데이터)
            model: 사용할 LLM 모델
            
        Returns:
            구조화된 요약 데이터
        """
        # 프롬프트 템플릿
        prompt = f"""
당신은 고객 지원 티켓을 분석하는 전문가입니다.
다음 티켓 내용을 분석하여 구조화된 요약을 생성해주세요.

티켓 내용:
{ticket_content}

다음 형식으로 요약해주세요:
1. 문제 (Problem): 고객이 겪고 있는 주요 문제
2. 원인 (Cause): 문제의 근본 원인 (파악된 경우)
3. 해결방법 (Solution): 제시된 해결 방법
4. 결과 (Result): 최종 해결 여부 및 결과

JSON 형식으로 응답해주세요:
{{
    "problem": "문제 설명",
    "cause": "원인 설명 (또는 '미파악')",
    "solution": "해결방법 설명",
    "result": "해결 결과",
    "keywords": ["키워드1", "키워드2", "키워드3"]
}}
"""
        
        # 캐시 확인
        cache_key = self._generate_cache_key(prompt, model)
        cached_response = await self._get_cached_response(cache_key)
        
        if cached_response:
            logging.info("캐시된 LLM 응답 사용")
            return cached_response
            
        # LLM 호출
        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "당신은 고객 지원 전문가입니다."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,  # 일관성을 위해 낮은 temperature
                max_tokens=1000
            )
            
            content = response.choices[0].message.content
            
            # JSON 파싱 시도
            try:
                summary = json.loads(content)
            except json.JSONDecodeError:
                # JSON 파싱 실패 시 기본 구조
                summary = {
                    "problem": "파싱 오류",
                    "cause": "미파악",
                    "solution": content,
                    "result": "처리 필요",
                    "keywords": []
                }
                
            # 캐시 저장
            await self._set_cached_response(cache_key, summary)
            
            return summary
            
        except Exception as e:
            logging.error(f"LLM 요약 생성 실패: {e}")
            return {
                "problem": "요약 생성 실패",
                "cause": "LLM 호출 오류",
                "solution": str(e),
                "result": "오류",
                "keywords": []
            }
            
    async def summarize_batch(
        self, 
        ticket_contents: List[str], 
        batch_size: int = 5
    ) -> List[Dict[str, Any]]:
        """
        배치 요약 처리 - 동시성 제한
        
        Args:
            ticket_contents: 티켓 내용 리스트
            batch_size: 동시 처리 배치 크기
            
        Returns:
            요약 결과 리스트
        """
        semaphore = asyncio.Semaphore(batch_size)
        
        async def process_single(content: str) -> Dict[str, Any]:
            async with semaphore:
                return await self.summarize_ticket(content)
                
        # 모든 티켓을 동시에 처리 (세마포어로 제한)
        tasks = [process_single(content) for content in ticket_contents]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 예외 처리
        summaries = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logging.error(f"배치 처리 오류 (인덱스 {i}): {result}")
                summaries.append({
                    "problem": "배치 처리 오류",
                    "cause": str(result),
                    "solution": "재처리 필요",
                    "result": "오류",
                    "keywords": []
                })
            else:
                summaries.append(result)
                
        return summaries

# 스트리밍 LLM 호출 패턴
async def stream_llm_response(
    prompt: str, 
    model: str = "gpt-3.5-turbo"
) -> AsyncGenerator[str, None]:
    """
    LLM 스트리밍 응답 - 실시간 UI 업데이트용
    
    Args:
        prompt: 입력 프롬프트
        model: LLM 모델
        
    Yields:
        스트리밍 응답 청크
    """
    client = openai.AsyncOpenAI()
    
    try:
        stream = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            stream=True
        )
        
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
                
    except Exception as e:
        logging.error(f"스트리밍 LLM 호출 실패: {e}")
        yield f"오류 발생: {e}"
```

### 3. 벡터 검색 최적화 패턴

**특징**:
- **멀티테넌트** 격리
- **하이브리드 검색** (벡터 + 키워드)
- **결과 재순위** (reranking)

```python
# 벡터 검색 최적화 패턴
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, ScoredPoint
from sentence_transformers import SentenceTransformer
import numpy as np
from typing import List, Dict, Any, Optional
import logging

class VectorSearchManager:
    """
    벡터 검색 최적화 매니저 - 멀티테넌트 지원
    """
    
    def __init__(
        self, 
        qdrant_url: str, 
        qdrant_api_key: str,
        collection_name: str = "tickets"
    ):
        self.client = AsyncQdrantClient(
            url=qdrant_url,
            api_key=qdrant_api_key
        )
        self.collection_name = collection_name
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        
    async def search_similar_tickets(
        self,
        query_text: str,
        company_id: str,
        limit: int = 10,
        score_threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        유사 티켓 검색 - company_id 기반 격리
        
        Args:
            query_text: 검색 쿼리
            company_id: 회사 ID (멀티테넌트 격리)
            limit: 반환할 결과 수
            score_threshold: 최소 유사도 임계값
            
        Returns:
            유사 티켓 리스트
        """
        try:
            # 쿼리 임베딩 생성
            query_embedding = self.embedding_model.encode(query_text).tolist()
            
            # company_id 필터 설정
            search_filter = Filter(
                must=[
                    FieldCondition(
                        key="company_id",
                        match=MatchValue(value=company_id)
                    )
                ]
            )
            
            # 벡터 검색 실행
            search_result = await self.client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                query_filter=search_filter,
                limit=limit,
                score_threshold=score_threshold
            )
            
            # 결과 변환
            tickets = []
            for hit in search_result:
                ticket_data = {
                    "ticket_id": hit.payload.get("ticket_id"),
                    "title": hit.payload.get("title"),
                    "summary": hit.payload.get("summary"),
                    "status": hit.payload.get("status"),
                    "similarity_score": hit.score,
                    "created_at": hit.payload.get("created_at")
                }
                tickets.append(ticket_data)
                
            logging.info(f"벡터 검색 완료: {len(tickets)}개 티켓 발견")
            return tickets
            
        except Exception as e:
            logging.error(f"벡터 검색 실패: {e}")
            return []
            
    async def hybrid_search(
        self,
        query_text: str,
        company_id: str,
        keywords: List[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        하이브리드 검색 - 벡터 검색 + 키워드 필터링
        
        Args:
            query_text: 검색 쿼리
            company_id: 회사 ID
            keywords: 추가 키워드 필터
            limit: 반환할 결과 수
            
        Returns:
            검색 결과 (재순위 적용)
        """
        # 기본 벡터 검색
        vector_results = await self.search_similar_tickets(
            query_text, 
            company_id, 
            limit * 2  # 재순위를 위해 더 많은 결과 가져오기
        )
        
        # 키워드 필터링 (옵션)
        if keywords:
            filtered_results = []
            for ticket in vector_results:
                summary_text = ticket.get("summary", {}).get("problem", "") + " " + \
                              ticket.get("summary", {}).get("solution", "")
                
                # 키워드 매칭 점수 계산
                keyword_score = 0
                for keyword in keywords:
                    if keyword.lower() in summary_text.lower():
                        keyword_score += 1
                        
                if keyword_score > 0:
                    ticket["keyword_score"] = keyword_score / len(keywords)
                    filtered_results.append(ticket)
                    
            vector_results = filtered_results
            
        # 재순위 적용 (벡터 유사도 + 키워드 점수)
        for ticket in vector_results:
            vector_score = ticket.get("similarity_score", 0)
            keyword_score = ticket.get("keyword_score", 0)
            
            # 가중 평균 (벡터 70%, 키워드 30%)
            combined_score = (vector_score * 0.7) + (keyword_score * 0.3)
            ticket["final_score"] = combined_score
            
        # 최종 점수로 정렬
        vector_results.sort(key=lambda x: x.get("final_score", 0), reverse=True)
        
        return vector_results[:limit]

# 사용 예시
async def search_and_recommend(
    user_query: str, 
    company_id: str,
    qdrant_config: Dict[str, str]
) -> Dict[str, Any]:
    """검색 및 추천 통합 함수"""
    
    search_manager = VectorSearchManager(
        qdrant_url=qdrant_config["url"],
        qdrant_api_key=qdrant_config["api_key"]
    )
    
    # 쿼리에서 키워드 추출 (간단한 예시)
    keywords = [word for word in user_query.split() if len(word) > 3]
    
    # 하이브리드 검색 실행
    recommendations = await search_manager.hybrid_search(
        query_text=user_query,
        company_id=company_id,
        keywords=keywords,
        limit=5
    )
    
    return {
        "query": user_query,
        "recommendations": recommendations,
        "total_found": len(recommendations),
        "search_metadata": {
            "company_id": company_id,
            "keywords": keywords,
            "timestamp": datetime.utcnow().isoformat()
        }
    }
```

---

## 🔧 실용적 유틸리티 함수

### 1. 설정 관리 패턴

```python
# 설정 관리 최적화
from pydantic import BaseSettings, Field
from typing import Optional
import os
from functools import lru_cache

class Settings(BaseSettings):
    """
    애플리케이션 설정 - 환경변수 기반
    """
    
    # Freshdesk 설정
    freshdesk_domain: str = Field(..., env="FRESHDESK_DOMAIN")
    freshdesk_api_key: str = Field(..., env="FRESHDESK_API_KEY")
    
    # Qdrant 설정
    qdrant_url: str = Field(..., env="QDRANT_URL")
    qdrant_api_key: str = Field(..., env="QDRANT_API_KEY")
    qdrant_collection: str = Field("tickets", env="QDRANT_COLLECTION")
    
    # LLM 설정
    openai_api_key: str = Field(..., env="OPENAI_API_KEY")
    openai_model: str = Field("gpt-3.5-turbo", env="OPENAI_MODEL")
    
    # Redis 설정
    redis_url: str = Field("redis://localhost:6379", env="REDIS_URL")
    
    # 애플리케이션 설정
    company_id: str = Field(..., env="COMPANY_ID")
    debug: bool = Field(False, env="DEBUG")
    log_level: str = Field("INFO", env="LOG_LEVEL")
    
    # 성능 설정
    max_concurrent_requests: int = Field(10, env="MAX_CONCURRENT_REQUESTS")
    cache_ttl: int = Field(3600, env="CACHE_TTL")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

@lru_cache()
def get_settings() -> Settings:
    """설정 싱글톤 - 캐싱 적용"""
    return Settings()

# 사용 예시
def get_database_url() -> str:
    """데이터베이스 URL 생성"""
    settings = get_settings()
    return f"postgresql://{settings.db_user}:{settings.db_password}@{settings.db_host}:{settings.db_port}/{settings.db_name}"
```

### 2. 로깅 최적화 패턴

```python
# 구조화된 로깅 시스템
import logging
import json
import sys
from datetime import datetime
from typing import Dict, Any, Optional
import traceback

class StructuredLogger:
    """
    구조화된 JSON 로깅 - 모니터링 최적화
    """
    
    def __init__(self, name: str, level: str = "INFO"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, level.upper()))
        
        # JSON 포맷터 설정
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(self._get_json_formatter())
        self.logger.addHandler(handler)
        
    def _get_json_formatter(self):
        """JSON 로그 포맷터"""
        class JSONFormatter(logging.Formatter):
            def format(self, record):
                log_entry = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "level": record.levelname,
                    "logger": record.name,
                    "message": record.getMessage(),
                    "module": record.module,
                    "function": record.funcName,
                    "line": record.lineno
                }
                
                # 예외 정보 추가
                if record.exc_info:
                    log_entry["exception"] = {
                        "type": record.exc_info[0].__name__,
                        "message": str(record.exc_info[1]),
                        "traceback": traceback.format_exception(*record.exc_info)
                    }
                
                # 추가 컨텍스트 정보
                if hasattr(record, 'extra_data'):
                    log_entry["context"] = record.extra_data
                    
                return json.dumps(log_entry, ensure_ascii=False)
                
        return JSONFormatter()
        
    def info(self, message: str, **kwargs):
        """정보 로그"""
        extra = {"extra_data": kwargs} if kwargs else {}
        self.logger.info(message, extra=extra)
        
    def error(self, message: str, error: Optional[Exception] = None, **kwargs):
        """에러 로그"""
        extra = {"extra_data": kwargs} if kwargs else {}
        self.logger.error(message, exc_info=error, extra=extra)
        
    def warning(self, message: str, **kwargs):
        """경고 로그"""
        extra = {"extra_data": kwargs} if kwargs else {}
        self.logger.warning(message, extra=extra)

# 글로벌 로거 인스턴스
logger = StructuredLogger("freshdesk_app")

# 사용 예시
def process_ticket_with_logging(ticket_id: str, company_id: str):
    """로깅이 포함된 티켓 처리"""
    logger.info(
        "티켓 처리 시작",
        ticket_id=ticket_id,
        company_id=company_id,
        timestamp=datetime.utcnow().isoformat()
    )
    
    try:
        # 티켓 처리 로직
        result = process_ticket(ticket_id)
        
        logger.info(
            "티켓 처리 완료",
            ticket_id=ticket_id,
            result_summary=result.get("summary"),
            processing_time=result.get("processing_time")
        )
        
        return result
        
    except Exception as e:
        logger.error(
            "티켓 처리 실패",
            error=e,
            ticket_id=ticket_id,
            company_id=company_id
        )
        raise
```

### 3. 에러 처리 및 재시도 패턴

```python
# 견고한 에러 처리 시스템
import asyncio
import functools
from typing import TypeVar, Callable, Type, Tuple, Any
from enum import Enum
import random

T = TypeVar('T')

class ErrorType(Enum):
    """에러 유형 분류"""
    NETWORK = "network"
    RATE_LIMIT = "rate_limit"
    AUTHENTICATION = "authentication"
    VALIDATION = "validation"
    UNKNOWN = "unknown"

class RetryStrategy:
    """재시도 전략 설정"""
    
    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_factor: float = 2.0,
        jitter: bool = True
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_factor = exponential_factor
        self.jitter = jitter
        
    def get_delay(self, attempt: int) -> float:
        """재시도 지연 시간 계산"""
        delay = self.base_delay * (self.exponential_factor ** attempt)
        delay = min(delay, self.max_delay)
        
        if self.jitter:
            # 지터 추가 (동시 재시도 방지)
            delay *= (0.5 + random.random() * 0.5)
            
        return delay

def with_retry(
    strategy: RetryStrategy = None,
    retriable_exceptions: Tuple[Type[Exception], ...] = (Exception,)
):
    """
    재시도 데코레이터
    
    Args:
        strategy: 재시도 전략
        retriable_exceptions: 재시도 가능한 예외 타입들
    """
    if strategy is None:
        strategy = RetryStrategy()
        
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> T:
            last_exception = None
            
            for attempt in range(strategy.max_attempts):
                try:
                    if asyncio.iscoroutinefunction(func):
                        return await func(*args, **kwargs)
                    else:
                        return func(*args, **kwargs)
                        
                except retriable_exceptions as e:
                    last_exception = e
                    
                    if attempt == strategy.max_attempts - 1:
                        # 최종 시도 실패
                        logger.error(
                            f"함수 {func.__name__} 최종 실패",
                            error=e,
                            attempt=attempt + 1,
                            max_attempts=strategy.max_attempts
                        )
                        raise
                    
                    # 재시도 대기
                    delay = strategy.get_delay(attempt)
                    logger.warning(
                        f"함수 {func.__name__} 재시도",
                        error=str(e),
                        attempt=attempt + 1,
                        delay=delay
                    )
                    
                    await asyncio.sleep(delay)
                    
            # 여기에 도달하면 안되지만 안전장치
            raise last_exception
            
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> T:
            # 동기 함수용 래퍼
            return asyncio.run(async_wrapper(*args, **kwargs))
            
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
            
    return decorator

# 사용 예시
@with_retry(
    strategy=RetryStrategy(max_attempts=5, base_delay=2.0),
    retriable_exceptions=(aiohttp.ClientError, asyncio.TimeoutError)
)
async def fetch_freshdesk_data(url: str, headers: Dict[str, str]) -> Dict[str, Any]:
    """재시도 로직이 적용된 Freshdesk API 호출"""
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            response.raise_for_status()
            return await response.json()
```

---

## 🐛 디버깅 & 모니터링 가이드

### 1. 성능 프로파일링 패턴

```python
# 성능 모니터링 시스템
import time
import asyncio
from typing import Dict, Any, Optional
from functools import wraps
from collections import defaultdict
import psutil
import threading

class PerformanceMonitor:
    """
    성능 모니터링 - 메모리, CPU, 응답 시간 추적
    """
    
    def __init__(self):
        self.metrics = defaultdict(list)
        self.active_operations = {}
        
    def start_operation(self, operation_name: str) -> str:
        """작업 시작 추적"""
        operation_id = f"{operation_name}_{int(time.time() * 1000)}"
        self.active_operations[operation_id] = {
            "name": operation_name,
            "start_time": time.time(),
            "start_memory": psutil.Process().memory_info().rss / 1024 / 1024  # MB
        }
        return operation_id
        
    def end_operation(self, operation_id: str) -> Dict[str, Any]:
        """작업 종료 및 메트릭 수집"""
        if operation_id not in self.active_operations:
            return {}
            
        operation = self.active_operations.pop(operation_id)
        end_time = time.time()
        end_memory = psutil.Process().memory_info().rss / 1024 / 1024
        
        metrics = {
            "operation": operation["name"],
            "duration": end_time - operation["start_time"],
            "memory_used": end_memory - operation["start_memory"],
            "cpu_percent": psutil.cpu_percent(),
            "timestamp": end_time
        }
        
        self.metrics[operation["name"]].append(metrics)
        return metrics
        
    def get_operation_stats(self, operation_name: str) -> Dict[str, Any]:
        """작업별 통계 조회"""
        if operation_name not in self.metrics:
            return {}
            
        operations = self.metrics[operation_name]
        durations = [op["duration"] for op in operations]
        memory_usage = [op["memory_used"] for op in operations]
        
        return {
            "operation": operation_name,
            "total_executions": len(operations),
            "avg_duration": sum(durations) / len(durations),
            "max_duration": max(durations),
            "min_duration": min(durations),
            "avg_memory": sum(memory_usage) / len(memory_usage),
            "max_memory": max(memory_usage)
        }

# 글로벌 모니터 인스턴스
performance_monitor = PerformanceMonitor()

def monitor_performance(operation_name: str = None):
    """성능 모니터링 데코레이터"""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            op_name = operation_name or func.__name__
            operation_id = performance_monitor.start_operation(op_name)
            
            try:
                result = await func(*args, **kwargs)
                metrics = performance_monitor.end_operation(operation_id)
                
                # 성능 경고 (5초 이상 소요)
                if metrics.get("duration", 0) > 5.0:
                    logger.warning(
                        f"성능 경고: {op_name} 실행 시간 초과",
                        duration=metrics["duration"],
                        memory_used=metrics["memory_used"]
                    )
                    
                return result
                
            except Exception as e:
                performance_monitor.end_operation(operation_id)
                raise
                
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # 동기 함수용
            op_name = operation_name or func.__name__
            operation_id = performance_monitor.start_operation(op_name)
            
            try:
                result = func(*args, **kwargs)
                performance_monitor.end_operation(operation_id)
                return result
            except Exception as e:
                performance_monitor.end_operation(operation_id)
                raise
                
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
            
    return decorator

# 사용 예시
@monitor_performance("llm_summarization")
async def summarize_ticket_with_monitoring(ticket_data: Dict[str, Any]) -> Dict[str, Any]:
    """성능 모니터링이 적용된 티켓 요약"""
    # LLM 요약 로직
    async with LLMManager() as llm:
        summary = await llm.summarize_ticket(ticket_data["content"])
        
    return summary
```

### 2. API 엔드포인트 디버깅 패턴

```python
# FastAPI 디버깅 최적화
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uuid
from typing import Dict, Any, Optional
import json

class DebugMiddleware:
    """
    디버깅 미들웨어 - 요청/응답 로깅
    """
    
    def __init__(self, app: FastAPI):
        self.app = app
        
    async def __call__(self, request: Request, call_next):
        # 요청 ID 생성
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        # 요청 로깅
        logger.info(
            "API 요청 시작",
            request_id=request_id,
            method=request.method,
            url=str(request.url),
            headers=dict(request.headers),
            client_ip=request.client.host
        )
        
        start_time = time.time()
        
        try:
            # 요청 본문 로깅 (POST/PUT)
            if request.method in ["POST", "PUT", "PATCH"]:
                body = await request.body()
                if body:
                    try:
                        body_json = json.loads(body)
                        logger.info(
                            "요청 본문",
                            request_id=request_id,
                            body=body_json
                        )
                    except json.JSONDecodeError:
                        logger.info(
                            "요청 본문 (텍스트)",
                            request_id=request_id,
                            body=body.decode('utf-8')[:1000]  # 최대 1000자
                        )
            
            # 실제 요청 처리
            response = await call_next(request)
            
            # 응답 로깅
            duration = time.time() - start_time
            logger.info(
                "API 요청 완료",
                request_id=request_id,
                status_code=response.status_code,
                duration=duration
            )
            
            return response
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                "API 요청 실패",
                error=e,
                request_id=request_id,
                duration=duration
            )
            
            # 에러 응답
            return JSONResponse(
                status_code=500,
                content={
                    "error": "내부 서버 오류",
                    "request_id": request_id,
                    "message": str(e) if app.debug else "서버 오류가 발생했습니다."
                }
            )

# FastAPI 앱 설정
def create_app() -> FastAPI:
    """디버깅 최적화된 FastAPI 앱 생성"""
    app = FastAPI(
        title="Freshdesk Custom App API",
        description="RAG 기반 고객지원 시스템",
        version="1.0.0",
        debug=get_settings().debug
    )
    
    # CORS 설정
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 프로덕션에서는 제한 필요
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # 디버깅 미들웨어 추가
    app.middleware("http")(DebugMiddleware(app))
    
    return app

# 의존성 주입 패턴
async def get_request_context(request: Request) -> Dict[str, Any]:
    """요청 컨텍스트 추출"""
    return {
        "request_id": getattr(request.state, "request_id", "unknown"),
        "company_id": request.headers.get("X-Company-ID"),
        "freshdesk_domain": request.headers.get("X-Freshdesk-Domain"),
        "api_key": request.headers.get("X-Freshdesk-API-Key"),
        "user_agent": request.headers.get("User-Agent")
    }

# 에러 핸들러
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """HTTP 예외 처리"""
    request_id = getattr(request.state, "request_id", "unknown")
    
    logger.warning(
        "HTTP 예외 발생",
        request_id=request_id,
        status_code=exc.status_code,
        detail=exc.detail
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "request_id": request_id,
            "status_code": exc.status_code
        }
    )

# API 엔드포인트 예시
@app.get("/debug/health")
async def debug_health_check(
    context: Dict[str, Any] = Depends(get_request_context)
) -> Dict[str, Any]:
    """디버깅 정보를 포함한 헬스 체크"""
    
    # 시스템 상태 확인
    system_info = {
        "cpu_percent": psutil.cpu_percent(),
        "memory_percent": psutil.virtual_memory().percent,
        "disk_usage": psutil.disk_usage('/').percent
    }
    
    # 성능 통계
    performance_stats = {}
    for operation in ["llm_summarization", "vector_search", "data_collection"]:
        stats = performance_monitor.get_operation_stats(operation)
        if stats:
            performance_stats[operation] = stats
    
    return {
        "status": "healthy",
        "request_id": context["request_id"],
        "timestamp": datetime.utcnow().isoformat(),
        "system": system_info,
        "performance": performance_stats,
        "active_operations": len(performance_monitor.active_operations)
    }
```

---

## 🚀 배포 및 운영 패턴

### 1. Docker 최적화

```dockerfile
# 최적화된 Python Docker 이미지
FROM python:3.10-slim

# 시스템 패키지 업데이트 및 필수 도구 설치
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 작업 디렉토리 설정
WORKDIR /app

# Python 의존성 먼저 복사 (캐시 최적화)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드 복사
COPY . .

# 비특권 사용자 생성
RUN adduser --disabled-password --gecos '' appuser
RUN chown -R appuser:appuser /app
USER appuser

# 헬스체크 설정
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 애플리케이션 실행
CMD ["python", "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 2. 환경별 설정 관리

```yaml
# docker-compose.yml - 개발환경
version: '3.8'

services:
  backend:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DEBUG=true
      - LOG_LEVEL=DEBUG
      - REDIS_URL=redis://redis:6379
    volumes:
      - ./data:/app/data
      - ./.env:/app/.env
    depends_on:
      - redis
      
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
      
  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
    volumes:
      - qdrant_data:/qdrant/storage

volumes:
  redis_data:
  qdrant_data:
```

이로써 **implementation-guide.instructions.md** 파일이 완성되었습니다. 

**다음 단계는 구버전 지침서들을 정리하는 것입니다:**

1. `backend.instructions.md` - 제거 또는 간소화
2. `frontend.instructions.md` - 필요한 FDK 내용만 보존하여 간소화

이 작업을 진행해도 될까요?
