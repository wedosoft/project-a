---
applyTo: "**"
---

# 🛠️ 구현 가이드 & 코딩 패턴 지침서

_AI 참조 최적화 버전 - 세션 간 일관성 보장을 위한 구현 가이드_

## 🎯 구현 목표

**Freshdesk Custom App의 실무 중심 구현 방법론 및 코딩 패턴**

- **실용적 코딩 패턴**: MVP 원칙에 따른 간단하고 실용적인 구현
- **성능 최적화**: 비동기 처리 및 캐싱 전략
- **에러 처리**: 견고한 에러 처리 및 복구 로직
- **디버깅 지원**: 체계적인 디버깅 및 모니터링

---

## 🚀 **TL;DR - 핵심 패턴 요약**

### 💡 **즉시 참조용 핵심 포인트**

**FDK 환경**:

- Node.js v14-v18만 지원, `fdk validate --verbose`로 디버깅
- iparams.html에서 company_id 자동 추출: `domain.split('.')[0]`
- 플랫폼은 항상 "freshdesk" (FDK 자체가 Freshdesk 전용)

**멀티테넌트 보안**:

- 모든 데이터에 company_id 자동 태깅 필수
- Row-level Security + Qdrant 필터링 조합
- API 키는 secrets manager 참조만 저장

**비동기 패턴**:

- 동시성 제한: `asyncio.Semaphore(max_concurrent)`
- 재시도 로직: 지수 백오프 + 최대 3회
- 컨텍스트 매니저로 리소스 관리

**주의사항**:

- ⚠️ FDK 중괄호 매칭 오류 빈발 → 구문 검증 필수
- ⚠️ company_id 없는 데이터 절대 금지 → 자동 추출 실패 시 에러
- ⚠️ LLM 캐싱 필수 → Redis 없으면 비용 폭증

---

## ⚠️ **코딩 철칙 & 설계 원칙**

### 🔄 **기존 코드 재활용 의무 (AI 세션 간 일관성 핵심)**

**목적**: 세션이 바뀌어도 동일한 아키텍처 패턴 유지

- **90% 이상 기존 코드 재활용**: 새로운 코딩은 최소한으로 제한
- **레거시 로직 보존**: 안정적으로 작동하던 기존 코드의 핵심 로직 유지
- **점진적 개선**: 전면 재작성 대신 기존 코드를 다듬어 사용
- **검증된 패턴 유지**: 기존 비즈니스 로직, 데이터 처리 방식 최대한 보존

### 📋 **AI 작업 시 필수 체크포인트**

1. **기존 파일 구조 확인** → `file_search` 또는 `read_file`로 현재 상태 파악
2. **company_id 자동 추출 패턴** → 모든 멀티테넌트 로직에 필수 적용
3. **플랫폼별 추상화** → Freshdesk 중심이지만 확장 가능하게 설계
4. **에러 처리 패턴** → 재시도 + 로깅 + 사용자 친화적 메시지

**리팩토링 접근법**:

```python
# ✅ AI가 따라야 할 패턴 - 기존 코드 개선
def improved_ticket_processor():
    # 기존 process_ticket() 함수 로직을 기반으로
    existing_logic = process_ticket()  # 기존 함수 재사용
    # 성능 최적화나 company_id 태깅만 추가
    return enhanced_result

# ❌ 피해야 할 패턴 - 전면 재작성
def new_ticket_processor():
    # 완전히 새로운 로직으로 재작성 (금지)
    pass
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
      description:
        ticketData.ticket.description_text || ticketData.ticket.description,
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
      ...options,
    });

    if (!response.ok) {
      throw new Error(
        `API 호출 실패: ${response.status} ${response.statusText}`
      );
    }

    return response.json();
  }

  // 초기 데이터 로드
  async init(ticketId) {
    return this.apiCall(`/init/${ticketId}`);
  }

  // AI 채팅 쿼리
  async query(ticketId, queryData) {
    return this.apiCall("/query", {
      method: "POST",
      body: JSON.stringify({ ticket_id: ticketId, ...queryData }),
    });
  }
}
```

#### 4. iparams.html 최적화 패턴 (Freshdesk)

```html
<!-- ✅ Freshdesk 전용 최적화 패턴 - company_id 자동 추출 -->
<script>
  class FreshdeskInstallSetup {
    constructor() {
      // Freshdesk 환경이므로 플랫폼은 자동으로 "freshdesk"
      this.platform = "freshdesk";
      this.setupEventListeners();
    }

    validateFreshdeskDomain() {
      const domain = document.getElementById("freshdesk_domain").value;
      const statusEl = document.getElementById("domain_status");

      if (!domain) return;

      // Freshdesk 도메인 패턴 검증
      const freshdeskPattern = /^[a-zA-Z0-9-]+\.freshdesk\.com$/;

      if (freshdeskPattern.test(domain)) {
        // company_id 자동 추출 및 표시
        const companyId = domain.split(".")[0];

        statusEl.innerHTML = `✅ Freshdesk 도메인이 확인되었습니다.`;
        statusEl.className = "status-success";

        // company_id 표시
        this.displayCompanyId(companyId, domain);

        // 도메인 유효성 검사 추가
        this.validateCompanyId(companyId);
      } else {
        statusEl.innerHTML =
          "❌ 올바른 Freshdesk 도메인 형식이 아닙니다. (예: company.freshdesk.com)";
        statusEl.className = "status-error";
        this.clearCompanyId();
      }
    }

    displayCompanyId(companyId, domain) {
      const companyIdEl = document.getElementById("company_id_display");
      if (companyIdEl) {
        companyIdEl.innerHTML = `
        <div class="company-info">
          <h4>🏢 추출된 고객사 정보</h4>
          <p><strong>Company ID:</strong> <code>${companyId}</code></p>
          <p><strong>Full Domain:</strong> <code>${domain}</code></p>
          <p class="note">이 Company ID로 데이터가 격리되어 저장됩니다.</p>
        </div>
      `;
      }
    }

    async testFreshdeskConnection() {
      const domain = document.getElementById("freshdesk_domain").value;
      const apiKey = document.getElementById("api_key").value;
      const statusEl = document.getElementById("connection_status");

      if (!domain || !apiKey) return;

      // 도메인에서 company_id 추출
      const companyId = domain.split(".")[0];

      statusEl.innerHTML = `🔄 ${companyId} Freshdesk 연결을 테스트하는 중...`;
      statusEl.className = "status-loading";

      try {
        const response = await fetch("/api/setup/test-freshdesk-connection", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            domain,
            api_key: apiKey,
            platform: "freshdesk",
          }),
        });

        const result = await response.json();

        if (result.success) {
          statusEl.innerHTML = `
          ✅ ${companyId} Freshdesk 연결 성공<br>
          📊 확인된 티켓: ${result.ticket_count}개<br>
          🏢 Company ID: <strong>${result.company_id}</strong>
        `;
          statusEl.className = "status-success";
        } else {
          statusEl.innerHTML = "❌ 연결 실패: API 키를 확인해주세요.";
          statusEl.className = "status-error";
        }
      } catch (error) {
        statusEl.innerHTML = "❌ 연결 테스트 중 오류가 발생했습니다.";
        statusEl.className = "status-error";
      }
    }
  }

  // Freshdesk 환경에서 자동 초기화
  document.addEventListener("DOMContentLoaded", () => {
    new FreshdeskInstallSetup();
  });
</script>
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
                        response.raise_for_status();
                        return await response.json();

                except aiohttp.ClientError as e:
                    if attempt == max_retries:
                        logging.error(f"HTTP 요청 최종 실패: {url}, 오류: {e}");
                        raise;

                    # 지수적 백오프
                    wait_time = 2 ** attempt;
                    logging.warning(f"HTTP 요청 재시도 {attempt + 1}/{max_retries}: {url}, {wait_time}초 대기");
                    await asyncio.sleep(wait_time);

# 사용 예시
async def collect_freshdesk_tickets(api_key: str, domain: str) -> List[Dict[str, Any]]:
    """Freshdesk 티켓 수집 실제 구현"""
    headers = {"Authorization": f"Basic {api_key}"};

    async with AsyncHTTPClient(max_concurrent=5) as client:
        # 페이징 처리
        tickets = [];
        page = 1;

        while True {
            url = f"https://{domain}.freshdesk.com/api/v2/tickets?page={page}";

            try {
                response = await client.fetch_with_retry(url, headers);

                if not response:  # 빈 페이지이면 종료
                    break;

                tickets.extend(response);
                page += 1;

                # Rate limit 대응 (Freshdesk API 제한)
                await asyncio.sleep(0.1);

            } catch (aiohttp.ClientError) {
                logging.error(f"티켓 수집 실패: 페이지 {page}");
                break;
            }

        return tickets;
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
        self.client = openai.AsyncOpenAI();
        self.redis_client: Optional[aioredis.Redis] = None
        self.redis_url = redis_url

    async def __aenter__(self):
        """Redis 연결 설정"""
        self.redis_client = await aioredis.from_url(self.redis_url);
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Redis 연결 정리"""
        if self.redis_client:
            await self.redis_client.close()

    def _generate_cache_key(self, prompt: str, model: str) -> str:
        """캐시 키 생성 - 프롬프트와 모델 기반 해시"""
        content = f"{model}:{prompt}";
        return f"llm_cache:{hashlib.md5(content.encode()).hexdigest()}";

    async def _get_cached_response(self, cache_key: str) -> Optional[str]:
        """캐시된 응답 조회"""
        if not self.redis_client:
            return None

        try {
            cached = await self.redis_client.get(cache_key);
            if cached {
                return json.loads(cached);
            }
        } catch (Exception as e) {
            logging.warning(f"캐시 조회 실패: {e}");
        }

        return None;
    }

    async def _set_cached_response(self, cache_key: str, response: str, ttl: int = 3600):
        """응답 캐싱 - 1시간 TTL"""
        if not self.redis_client:
            return

        try {
            await self.redis_client.setex(
                cache_key,
                ttl,
                json.dumps(response)
            );
        } catch (Exception as e) {
            logging.warning(f"캐시 저장 실패: {e}");
        }
    }

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
        cache_key = self._generate_cache_key(prompt, model);
        cached_response = await self._get_cached_response(cache_key);

        if cached_response {
            logging.info("캐시된 LLM 응답 사용");
            return cached_response;
        }

        # LLM 호출
        try {
            response = await self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "당신은 고객 지원 전문가입니다."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,  # 일관성을 위해 낮은 temperature
                max_tokens=1000
            );

            content = response.choices[0].message.content;

            # JSON 파싱 시도
            try {
                summary = json.loads(content);
            } catch (json.JSONDecodeError) {
                # JSON 파싱 실패 시 기본 구조
                summary = {
                    "problem": "파싱 오류",
                    "cause": "미파악",
                    "solution": content,
                    "result": "처리 필요",
                    "keywords": []
                };
            }

            # 캐시 저장
            await self._set_cached_response(cache_key, summary);

            return summary;

        } catch (Exception as e) {
            logging.error(f"LLM 요약 생성 실패: {e}");
            return {
                "problem": "요약 생성 실패",
                "cause": "LLM 호출 오류",
                "solution": str(e),
                "result": "오류",
                "keywords": []
            };
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
        semaphore = asyncio.Semaphore(batch_size);

        async def process_single(content: str) -> Dict[str, Any]:
            async with semaphore:
                return await self.summarize_ticket(content);

        # 모든 티켓을 동시에 처리 (세마포어로 제한)
        tasks = [process_single(content) for content in ticket_contents];
        results = await asyncio.gather(*tasks, return_exceptions=True);

        # 예외 처리
        summaries = [];
        for i, result in enumerate(results) {
            if isinstance(result, Exception) {
                logging.error(f"배치 처리 오류 (인덱스 {i}): {result}");
                summaries.append({
                    "problem": "배치 처리 오류",
                    "cause": str(result),
                    "solution": "재처리 필요",
                    "result": "오류",
                    "keywords": []
                });
            } else {
                summaries.append(result);
            }
        }

        return summaries;
    }

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
    client = openai.AsyncOpenAI();

    try {
        stream = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            stream=True
        );

        async for chunk in stream {
            if chunk.choices[0].delta.content {
                yield chunk.choices[0].delta.content;
            }
        }

    } catch (Exception as e) {
        logging.error(f"스트리밍 LLM 호출 실패: {e}");
        yield f"오류 발생: {e}";
    }
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
        );
        self.collection_name = collection_name;
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2');

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
        try {
            # 쿼리 임베딩 생성
            query_embedding = self.embedding_model.encode(query_text).tolist();

            # company_id 필터 설정
            search_filter = Filter(
                must=[
                    FieldCondition(
                        key="company_id",
                        match=MatchValue(value=company_id)
                    )
                ]
            );

            # 벡터 검색 실행
            search_result = await self.client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                query_filter=search_filter,
                limit=limit,
                score_threshold=score_threshold
            );

            # 결과 변환
            tickets = [];
            for hit in search_result {
                ticket_data = {
                    "ticket_id": hit.payload.get("ticket_id"),
                    "title": hit.payload.get("title"),
                    "summary": hit.payload.get("summary"),
                    "status": hit.payload.get("status"),
                    "similarity_score": hit.score,
                    "created_at": hit.payload.get("created_at")
                };
                tickets.append(ticket_data);
            }

            logging.info(f"벡터 검색 완료: {len(tickets)}개 티켓 발견");
            return tickets;

        } catch (Exception as e) {
            logging.error(f"벡터 검색 실패: {e}");
            return [];
        }
    }

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
        );

        # 키워드 필터링 (옵션)
        if keywords {
            filtered_results = [];
            for ticket in vector_results {
                summary_text = ticket.get("summary", {}).get("problem", "") + " " + \
                              ticket.get("summary", {}).get("solution", "");

                # 키워드 매칭 점수 계산
                keyword_score = 0;
                for keyword in keywords {
                    if keyword.lower() in summary_text.lower() {
                        keyword_score += 1;
                    }
                }

                if keyword_score > 0 {
                    ticket["keyword_score"] = keyword_score / len(keywords);
                    filtered_results.append(ticket);
                }
            }

            vector_results = filtered_results;
        }

        # 재순위 적용 (벡터 유사도 + 키워드 점수)
        for ticket in vector_results {
            vector_score = ticket.get("similarity_score", 0);
            keyword_score = ticket.get("keyword_score", 0);

            # 가중 평균 (벡터 70%, 키워드 30%)
            combined_score = (vector_score * 0.7) + (keyword_score * 0.3);
            ticket["final_score"] = combined_score;
        }

        # 최종 점수로 정렬
        vector_results.sort(key=lambda x: x.get("final_score", 0), reverse=True);

        return vector_results[:limit];
    }
}

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
    );

    # 쿼리에서 키워드 추출 (간단한 예시)
    keywords = [word for word in user_query.split() if len(word) > 3];

    # 하이브리드 검색 실행
    recommendations = await search_manager.hybrid_search(
        query_text=user_query,
        company_id=company_id,
        keywords=keywords,
        limit=5
    );

    return {
        "query": user_query,
        "recommendations": recommendations,
        "total_found": len(recommendations),
        "search_metadata": {
            "company_id": company_id,
            "keywords": keywords,
            "timestamp": datetime.utcnow().isoformat()
        }
    };
```

---

## 🌐 플랫폼 감지 및 관리 패턴

### 플랫폼별 설치 화면 추상화

**플랫폼별 특성**:

- **Freshdesk**: `iparams.html` 사용, 도메인에서 company_id 자동 추출
- **Zendesk**: `manifest.json` 사용 (추정), 유사한 도메인 구조
- **ServiceNow**: 별도 설정 방식 (향후 확장)

```python
# backend/core/platform_manager.py
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from enum import Enum

class PlatformType(Enum):
    FRESHDESK = "freshdesk"
    ZENDESK = "zendesk"
    SERVICENOW = "servicenow"

class PlatformInstallConfig(ABC):
    """플랫폼별 설치 설정 추상화"""

    @abstractmethod
    async def validate_credentials(self, domain: str, api_key: str) -> Dict[str, Any]:
        """플랫폼별 인증 정보 검증"""
        pass

    @abstractmethod
    def get_company_id(self, domain: str) -> str:
        """도메인에서 company_id 추출"""
        pass

    @abstractmethod
    def get_recommended_settings(self) -> Dict[str, Any]:
        """플랫폼별 권장 설정값"""
        pass

class FreshdeskInstallConfig(PlatformInstallConfig):
    """Freshdesk 설치 설정"""

    def get_company_id(self, domain: str) -> str:
        """Freshdesk 도메인에서 company_id 추출

        Args:
            domain: "wedosoft.freshdesk.com" 형태

        Returns:
            company_id: "wedosoft"
        """
        if not domain.endswith('.freshdesk.com'):
            raise ValueError(f"올바르지 않은 Freshdesk 도메인: {domain}")

        company_id = domain.split('.')[0]
        if not company_id or len(company_id) < 2:
            raise ValueError(f"유효하지 않은 company_id: {company_id}")

        return company_id

    async def validate_credentials(self, domain: str, api_key: str) -> Dict[str, Any]:
        """Freshdesk API 연결 테스트 및 company_id 확인"""
        import aiohttp
        import base64

        try {
            company_id = self.get_company_id(domain);
            auth_string = base64.b64encode(f"{api_key}:X".encode()).decode();

            async with aiohttp.ClientSession() as session {
                url = `https://${domain}/api/v2/tickets?per_page=1`;
                headers = {"Authorization": `Basic ${auth_string}`};

                async with session.get(url, headers=headers) as response {
                    if response.status == 200 {
                        data = await response.json();
                        return {
                            "success": True,
                            "platform": "freshdesk",
                            "company_id": company_id,
                            "domain": domain,
                            "ticket_count": len(data)
                        };
                    } else {
                        return {"success": False, "error": "인증 실패"};
                    }
                }
            }

        } catch (Exception as e) {
            return {"success": False, "error": str(e)};
        }
    }

    def get_recommended_settings(self) -> Dict[str, Any]:
        """Freshdesk 권장 설정값"""
        return {
            "collection_period": 6,  # 6개월
            "similar_tickets_count": 3,
            "kb_documents_count": 3,
            "auto_summary": True,
            "processing_batch_size": 50
        };
    }

# 플랫폼 설정 팩토리
class PlatformConfigFactory:
    """플랫폼별 설정 팩토리"""

    _configs = {
        PlatformType.FRESHDESK: FreshdeskInstallConfig,
        # PlatformType.ZENDESK: ZendeskInstallConfig,  # 향후 추가
    }

    @classmethod
    def get_config(cls, platform: PlatformType) -> PlatformInstallConfig:
        config_class = cls._configs.get(platform);
        if not config_class:
            raise ValueError(f"지원하지 않는 플랫폼: {platform}");
        return config_class();

    @classmethod
    def detect_platform_from_domain(cls, domain: str) -> PlatformType:
        """도메인으로 플랫폼 자동 감지"""
        if '.freshdesk.com' in domain:
            return PlatformType.FRESHDESK;
        elif '.zendesk.com' in domain:
            return PlatformType.ZENDESK;
        elif '.service-now.com' in domain:
            return PlatformType.SERVICENOW;
        else:
            raise ValueError(f"지원하지 않는 도메인: {domain}");
    }
}
```

### 백엔드 설치 API 패턴

```python
# backend/api/routes/setup.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from core.platform_manager import PlatformConfigFactory, PlatformType

router = APIRouter(prefix="/setup", tags=["setup"])

class InstallRequest(BaseModel):
    domain: str
    api_key: str
    platform: str = None  # iparams에서는 자동 설정
    collection_period: int = 6
    similar_tickets_count: int = 3
    kb_documents_count: int = 3
    auto_summary: bool = True

@router.post("/test-freshdesk-connection")
async def test_freshdesk_connection(request: InstallRequest) -> Dict[str, Any]:
    """Freshdesk 연결 테스트 (iparams 전용) - company_id 자동 추출"""

    try {
        freshdesk_config = PlatformConfigFactory.get_config(PlatformType.FRESHDESK);
        company_id = freshdesk_config.get_company_id(request.domain);

        validation_result = await freshdesk_config.validate_credentials(
            request.domain,
            request.api_key
        );

        if validation_result["success"] {
            recommended = freshdesk_config.get_recommended_settings();

            return {
                "success": True,
                "platform": "freshdesk",
                "company_id": company_id,  # 자동 추출된 값
                "domain": request.domain,
                "ticket_count": validation_result.get("ticket_count", 0),
                "recommended_settings": recommended,
                "message": `Company '${company_id}' Freshdesk 연결이 성공했습니다.`
            };
        } else {
            raise HTTPException(
                status_code=400,
                detail=`Company '${company_id}' 연결 실패: ${validation_result['error']}`
            );
        }

    } catch (Exception as e) {
        raise HTTPException(status_code=500, detail=str(e));
    }
}

@router.post("/install")
async def install_platform(request: InstallRequest) -> Dict[str, Any]:
    """플랫폼 설치 - company_id 자동 관리"""

    try {
        # 도메인으로 플랫폼 및 company_id 자동 감지
        platform_type = PlatformConfigFactory.detect_platform_from_domain(request.domain);
        platform_config = PlatformConfigFactory.get_config(platform_type);

        # company_id 자동 추출
        company_id = platform_config.get_company_id(request.domain);

        # 인증 검증
        validation_result = await platform_config.validate_credentials(
            request.domain,
            request.api_key
        );

        if not validation_result["success"] {
            raise HTTPException(status_code=400, detail=validation_result["error"]);
        }

        # 설치 설정 저장 (company_id 자동 설정)
        install_config = {
            "company_id": company_id,  # 도메인에서 자동 추출
            "platform": platform_type.value,
            "domain": request.domain,
            "api_key_hash": hash_api_key(request.api_key),
            "settings": {
                "collection_period": request.collection_period,
                "similar_tickets_count": request.similar_tickets_count,
                "kb_documents_count": request.kb_documents_count,
                "auto_summary": request.auto_summary
            },
            "installed_at": datetime.now().isoformat()
        };

        return {
            "status": "success",
            "message": `Company '${company_id}' ${platform_type.value.title()} 플랫폼이 성공적으로 설치되었습니다.`,
            "company_id": company_id,
            "platform": platform_type.value,
            "domain": request.domain,
            "data_isolation": `모든 데이터는 '${company_id}' 고유 영역에 저장됩니다.`,
            "next_steps": [
                `${company_id} 데이터 수집을 시작합니다.`,
                `약 10-30분 소요될 예정입니다.`,
                `완료 후 알림을 받으실 수 있습니다.`
            ]
        };

    } catch (Exception as e) {
        raise HTTPException(status_code=500, detail=str(e));
    }
}
```

### 환경 변수 관리 패턴

```bash
# .env 파일 구조 (company_id 자동 관리)
# 기본 설정
FRESHDESK_DOMAIN=wedosoft.freshdesk.com  # company_id는 자동 추출: "wedosoft"
FRESHDESK_API_KEY=your-api-key
PLATFORM=freshdesk  # iparams 자체가 Freshdesk이므로 자동 설정

# 벡터 DB 설정
QDRANT_URL=https://your-cluster.qdrant.io
QDRANT_API_KEY=your-qdrant-key
QDRANT_COLLECTION=documents

# LLM 설정
OPENAI_API_KEY=your-openai-key
OPENAI_MODEL=gpt-3.5-turbo

# 자동 추출 검증
# COMPANY_ID는 환경변수로 설정하지 않고 도메인에서 자동 추출
```

### 데이터 파이프라인 company_id 통합

```python
# scripts/collect_and_process.py (company_id 자동 적용)
async def main():
    # 환경변수에서 도메인 읽기
    freshdesk_domain = os.getenv("FRESHDESK_DOMAIN")  # "wedosoft.freshdesk.com"

    # 도메인에서 company_id 자동 추출
    company_id = freshdesk_domain.split('.')[0]  # "wedosoft"

    print(f"🏢 Company ID: {company_id}");
    print(f"🌐 Freshdesk Domain: {freshdesk_domain}");

    # 1. Freshdesk API에서 데이터 수집
    collector = FreshdeskDataCollector(
        domain=freshdesk_domain,
        api_key=os.getenv("FRESHDESK_API_KEY"),
        company_id=company_id  # 자동 추출된 값 사용
    );

    # 2. 티켓 데이터 수집 (company_id 포함)
    tickets = await collector.collect_tickets_with_conversations(
        start_date="2024-01-01",
        platform="freshdesk",
        company_id=company_id
    );

    # 3. KB 문서 수집 (company_id 포함)
    kb_docs = await collector.collect_knowledge_base(
        platform="freshdesk",
        company_id=company_id,
        status="published"
    );

    # 4. 모든 데이터에 company_id 태깅
    for item in tickets + kb_docs {
        item["company_id"] = company_id;
        item["platform"] = "freshdesk";
    }

    print(f"✅ {company_id} 데이터 수집 완료: 티켓 {len(tickets)}개, KB {len(kb_docs)}개");

    # 5. 나머지 처리 과정...
}
```

---

## 🎯 **AI 세션 간 일관성 보장 체크리스트**

### ✅ **필수 확인사항 (모든 구현 시)**

1. **company_id 자동 추출**

   - Freshdesk: `domain.split('.')[0]`
   - 모든 데이터에 company_id 태깅 필수
   - 누락 시 멀티테넌트 격리 실패

2. **플랫폼 식별**

   - FDK = Freshdesk 전용 (platform: "freshdesk")
   - 헤더에 X-Platform, X-Company-ID 포함
   - 향후 Zendesk 확장 대비 추상화

3. **에러 처리**

   - 재시도 로직: 지수 백오프 + 최대 3회
   - 로깅: 구조화된 로그 + 사용자 친화적 메시지
   - 리소스 정리: 컨텍스트 매니저 사용

4. **성능 최적화**
   - 비동기: asyncio.Semaphore로 동시성 제한
   - 캐싱: Redis 기반 LLM 응답 캐싱
   - 배치 처리: 대용량 데이터 청크 단위

### 🚨 **자주 발생하는 함정들**

- **FDK 구문 오류**: 중괄호 매칭, 세미콜론 누락
- **company_id 누락**: 멀티테넌트 데이터 격리 실패
- **API Rate Limit**: Freshdesk API 제한 초과
- **메모리 누수**: aiohttp 세션 정리 누락
- **캐싱 미적용**: LLM 비용 폭증

### 📋 **AI 작업 시 표준 프로세스**

1. **기존 코드 확인**: `file_search` → `read_file`로 현재 상태 파악
2. **패턴 적용**: 위 체크리스트 기반 구현
3. **테스트**: `fdk validate` + 브라우저 개발자 도구
4. **company_id 검증**: 모든 API 호출에 포함 확인
5. **문서 업데이트**: 주요 변경사항 기록

### 🎨 **프론트엔드 개발 우선순위 원칙**

**스타일 파일 관리**:

- **단일 스타일 파일**: `app/styles/styles.css`만 사용
- **UI 분할 금지**: 별도 UI 컴포넌트 파일 생성 지양
- **기존 스타일 활용**: 이미 잘 구성된 스타일 최대한 재사용

**개발 우선순위**:

1. **백엔드 우선**: 데이터 파이프라인, API 엔드포인트 완성도 우선
2. **프론트 지연**: UI/UX 개선은 백엔드 안정화 후 진행
3. **지침서 명시**: 프론트엔드 예정 작업은 지침서에 상세히 기록

---

## 🎯 **AI 참조용 핵심 코드 패턴 라이브러리**

### **1. company_id 자동 추출 (멀티테넌트 핵심)**

```python
# Python 버전
def extract_company_id(domain: str) -> str:
    if domain.endswith(".freshdesk.com"):
        return domain.split(".")[0]
    raise ValueError(f"Unsupported domain: {domain}")

# JavaScript 버전 (FDK)
function extractCompanyId(domain) {
    if (domain.includes(".freshdesk.com")) {
        return domain.split(".")[0];
    }
    throw new Error(`Unsupported domain: ${domain}`);
}
```

### **2. 멀티테넌트 API 호출 패턴**

```python
# 백엔드 API 호출 시 필수 헤더
headers = {
    "X-Company-ID": company_id,  # 멀티테넌트 격리 핵심
    "X-Platform": "freshdesk",   # 플랫폼 식별
    "Content-Type": "application/json"
}

# Qdrant 필터링
search_filter = Filter(
    must=[
        FieldCondition(key="company_id", match=MatchValue(value=company_id)),
        FieldCondition(key="platform", match=MatchValue(value="freshdesk"))
    ]
)
```

### **3. 에러 처리 표준 패턴**

```python
# 재시도 로직 with 지수 백오프
async def retry_with_backoff(func, max_retries=3):
    for attempt in range(max_retries + 1):
        try:
            return await func()
        except Exception as e:
            if attempt == max_retries:
                raise
            await asyncio.sleep(2 ** attempt)  # 1, 2, 4초

# 사용자 친화적 에러 메시지
def format_user_error(error: Exception) -> str:
    if "401" in str(error):
        return "❌ API 키를 확인해주세요."
    elif "rate limit" in str(error).lower():
        return "⏳ 요청이 많습니다. 잠시 후 다시 시도해주세요."
    else:
        return "❌ 연결 중 오류가 발생했습니다."
```

### **4. 리소스 관리 패턴**

```python
# 컨텍스트 매니저 사용 (리소스 정리 보장)
async with AsyncHTTPClient(max_concurrent=5) as client:
    results = await client.fetch_multiple(urls)
    # 자동으로 client.close() 호출됨

# Redis 연결 관리
async with aioredis.from_url("redis://localhost") as redis:
    await redis.setex("key", 3600, "value")
    # 자동으로 연결 해제
```

### **5. FDK 특수 패턴**

```javascript
// Freshdesk 앱 컨텍스트 접근
const context = await window.parent.app.instance.context();
const companyId = context.account.subdomain; // 자동 추출

// 티켓 데이터 접근
const ticketData = await window.parent.app.data.get("ticket");
const ticketInfo = {
  id: ticketData.ticket.id,
  subject: ticketData.ticket.subject,
  description:
    ticketData.ticket.description_text || ticketData.ticket.description,
};

// 백엔드 API 호출 헤더
const headers = {
  "Content-Type": "application/json",
  "X-Company-ID": companyId,
  "X-Platform": "freshdesk",
};
```

---

## 🎨 **프론트엔드 개발 원칙 (UI 분할 금지)**

### **스타일 관리 원칙**

- **단일 스타일 파일 사용**: `app/styles/styles.css` 파일만 사용
- **UI 분할 금지**: 별도 UI 컴포넌트 파일 생성 금지 (복잡도 증가 방지)
- **백엔드 우선**: 현재는 백엔드 구현에 집중, 프론트엔드는 최소한의 기능만 유지

### **프론트엔드 예정 작업 (지침서 명시용)**

다음 작업들은 백엔드 안정화 후 진행 예정:

1. **데이터 수집 상태 관리 UI**

   - 수집 진행률 표시
   - 일시정지/재시작 버튼
   - 실시간 상태 업데이트

2. **향상된 검색 인터페이스**

   - 필터링 옵션 추가
   - 검색 결과 정렬 기능
   - 키워드 하이라이팅

3. **설정 관리 화면**

   - LLM 모델 선택
   - 임계값 조정
   - 캐시 관리

4. **분석 대시보드**

   - 티켓 처리 통계
   - 응답 품질 메트릭
   - 사용량 분석

5. **프론트엔드 파일 간소화 및 최적화**
   - 불필요한 UI 모듈 파일 제거 완료 (`ingest-job-ui.js` 등)
   - 기존 `app.js`, `api.js`, `ui.js` 등 핵심 파일만 유지
   - `styles.css` 단일 파일로 스타일 통합 관리
   - JavaScript 모듈 통합 및 중복 코드 정리
   - FDK 호환성 최적화 및 성능 개선

**현재 단계에서는 위 기능들을 구현하지 않고, 백엔드 API 완성에 집중합니다.**

---

**이 지침서는 AI 세션 간 일관성을 보장하기 위한 참조 자료입니다. 모든 구현 작업 전에 TL;DR 섹션과 체크리스트를 필수 확인하세요.**
