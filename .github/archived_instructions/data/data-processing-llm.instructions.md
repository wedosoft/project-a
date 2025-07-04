---
applyTo: "**"
---

# 🧠 LLM 데이터 처리 & 요약 생성 지침서

_AI 참조 최적화 버전 - LLM 기반 데이터 처리 및 비용 최적화 전략_

## 🎯 LLM 처리 목표

**비용 효율적인 LLM 기반 고객 지원 데이터 요약 및 구조화**

- **비용 최적화**: 필터링 + 캐싱 + 배치 처리로 LLM 비용 80% 절감
- **구조화된 요약**: 문제-원인-해결방법-결과 구조로 일관된 요약
- **실시간 캐싱**: Redis 기반 중복 요약 방지
- **배치 처리**: 여러 티켓 동시 처리로 처리량 향상

---

## 🚀 **TL;DR - 핵심 LLM 처리 요약**

### 💡 **즉시 참조용 핵심 포인트**

**LLM 처리 흐름**:
```
데이터 필터링 → 배치 그룹핑 → 캐시 확인 → LLM 요약 생성 → 결과 캐싱 → 구조화된 저장
```

**비용 최적화 핵심**:
- **선택적 처리**: 해결된 티켓만 요약 (미해결 티켓 제외)
- **중복 제거**: 동일 내용 재요약 방지 (Redis 캐싱)
- **배치 처리**: 10개씩 묶어서 병렬 처리
- **모델 선택**: GPT-3.5-turbo 우선 사용 (비용 효율적)

**구조화된 요약 형식**:
```json
{
    "problem": "고객이 겪고 있는 주요 문제",
    "cause": "문제의 근본 원인 (또는 '미파악')",
    "solution": "제시된 해결 방법",
    "result": "최종 해결 여부 및 결과",
    "tags": ["키워드1", "키워드2", "키워드3"]
}
```

### 🚨 **LLM 처리 주의사항**

- ⚠️ LLM 비용 폭증 방지 → 필터링 + 캐싱 + 배치 처리 필수
- ⚠️ company_id 격리 → 모든 LLM 처리에 테넌트 정보 포함
- ⚠️ 무분별한 재요약 금지 → 캐시 확인 후 LLM 호출

---

## 🔧 **LLM 요약 생성 패턴**

### 🎯 **구조화된 요약 프롬프트**

```python
TICKET_SUMMARY_PROMPT = """
당신은 고객 지원 티켓을 분석하는 전문가입니다.
다음 티켓 내용을 분석하여 구조화된 요약을 생성해주세요.

티켓 내용: {ticket_content}

다음 형식으로 요약해주세요:
1. 문제 (Problem): 고객이 겪고 있는 주요 문제 (1-2줄)
2. 원인 (Cause): 문제의 근본 원인 (파악된 경우, 없으면 '미파악')
3. 해결방법 (Solution): 제시된 해결 방법 (구체적인 단계)
4. 결과 (Result): 최종 해결 여부 및 결과
5. 태그 (Tags): 관련 키워드 (최대 5개, 검색 최적화용)

JSON 형식으로 응답해주세요:
{{
    "problem": "문제 설명",
    "cause": "원인 설명 (또는 '미파악')",
    "solution": "해결방법 설명",
    "result": "해결 결과",
    "tags": ["키워드1", "키워드2", "키워드3", "키워드4", "키워드5"]
}}

주의사항:
- 고객의 개인정보는 제외하고 요약하세요
- 기술적 용어는 이해하기 쉽게 설명하세요
- 해결되지 않은 경우 result에 "미해결"로 표기하세요
"""

KB_SUMMARY_PROMPT = """
당신은 기술 문서를 분석하는 전문가입니다.
다음 기술 문서를 분석하여 구조화된 요약을 생성해주세요.

문서 내용: {document_content}

다음 형식으로 요약해주세요:
1. 주제 (Topic): 문서의 주요 주제
2. 해결 영역 (Scope): 어떤 문제/영역을 다루는지
3. 핵심 내용 (Content): 주요 내용 요약
4. 적용 조건 (Conditions): 언제 사용할 수 있는지
5. 태그 (Tags): 관련 키워드 (최대 5개)

JSON 형식으로 응답해주세요:
{{
    "topic": "문서 주제",
    "scope": "해결 영역",
    "content": "핵심 내용 요약",
    "conditions": "적용 조건",
    "tags": ["키워드1", "키워드2", "키워드3", "키워드4", "키워드5"]
}}
"""
```

### ⚡ **배치 처리 및 캐싱 패턴**

```python
@cache_llm_response(ttl=86400)  # 24시간 캐싱
async def process_tickets_batch(
    company_id: str,
    tickets: List[Dict],
    batch_size: int = 10,
    cost_filter: bool = True
) -> List[Dict]:
    """
    티켓 배치 처리 및 LLM 비용 최적화
    """
    # 1. 비용 필터링 (해결된 티켓만 처리)
    if cost_filter:
        tickets = [t for t in tickets if t.get('status') in ['resolved', 'closed']]
        logger.info(f"Filtered {len(tickets)} resolved tickets for processing")

    # 2. 배치 단위로 묶어서 처리
    all_summaries = []
    
    for i in range(0, len(tickets), batch_size):
        batch = tickets[i:i + batch_size]
        logger.info(f"Processing batch {i//batch_size + 1}/{len(tickets)//batch_size + 1}")

        # 3. 병렬 LLM 요청 (동시성 제어)
        semaphore = asyncio.Semaphore(5)  # 최대 5개 동시 요청
        
        async def process_with_semaphore(ticket):
            async with semaphore:
                return await summarize_single_ticket(company_id, ticket)

        tasks = [process_with_semaphore(ticket) for ticket in batch]
        summaries = await asyncio.gather(*tasks, return_exceptions=True)

        # 4. 예외 처리 및 결과 수집
        valid_summaries = []
        for i, summary in enumerate(summaries):
            if isinstance(summary, Exception):
                logger.error(f"Failed to process ticket {batch[i].get('id')}: {summary}")
                continue
            valid_summaries.append(summary)

        all_summaries.extend(valid_summaries)

        # 5. 배치 간 지연 (Rate Limit 방지)
        await asyncio.sleep(1)

    # 6. 결과 저장 (company_id별 분리)
    await save_ticket_summaries(company_id, all_summaries)
    
    return all_summaries

async def summarize_single_ticket(company_id: str, ticket: dict) -> dict:
    """단일 티켓 요약 (캐싱 적용)"""

    # 1. 캐시 키 생성 (company_id 포함)
    content_text = ticket.get("full_conversation", "") + ticket.get("description", "")
    content_hash = hashlib.md5(content_text.encode()).hexdigest()
    cache_key = f"summary:{company_id}:{content_hash}"

    # 2. 캐시 확인
    cached_summary = await redis_client.get(cache_key)
    if cached_summary:
        logger.info(f"Cache hit for ticket {ticket.get('id')}")
        return orjson.loads(cached_summary)

    # 3. LLM 호출
    try:
        response = await llm_client.chat.completions.create(
            model="gpt-3.5-turbo",  # 비용 효율적 모델
            messages=[{
                "role": "user",
                "content": TICKET_SUMMARY_PROMPT.format(
                    ticket_content=content_text[:4000]  # 토큰 제한
                )
            }],
            temperature=0.1,  # 일관된 결과를 위해 낮은 온도
            max_tokens=500    # 응답 길이 제한
        )

        summary_text = response.choices[0].message.content
        summary = orjson.loads(summary_text)

        # 4. 메타데이터 추가
        summary.update({
            'company_id': company_id,
            'platform': ticket.get('platform'),
            'ticket_id': ticket.get('id'),
            'processed_at': datetime.utcnow().isoformat(),
            'model_used': 'gpt-3.5-turbo',
            'processing_cost': calculate_processing_cost(response.usage)
        })

        # 5. 캐시 저장
        await redis_client.setex(cache_key, 86400, orjson.dumps(summary))
        
        logger.info(f"Processed ticket {ticket.get('id')} for {company_id}")
        return summary

    except Exception as e:
        logger.error(f"Failed to summarize ticket {ticket.get('id')}: {e}")
        # 기본 요약 반환
        return {
            'problem': ticket.get('subject', 'Unknown problem'),
            'cause': '미파악',
            'solution': '처리 실패',
            'result': '요약 생성 실패',
            'tags': ['processing_error'],
            'error': str(e)
        }
```

### 💰 **비용 최적화 전략**

```python
def calculate_processing_cost(usage_info: dict) -> float:
    """LLM 처리 비용 계산"""
    # GPT-3.5-turbo 가격 (2024년 기준)
    INPUT_COST_PER_1K = 0.0015  # $0.0015 per 1K tokens
    OUTPUT_COST_PER_1K = 0.002  # $0.002 per 1K tokens
    
    input_tokens = usage_info.get('prompt_tokens', 0)
    output_tokens = usage_info.get('completion_tokens', 0)
    
    input_cost = (input_tokens / 1000) * INPUT_COST_PER_1K
    output_cost = (output_tokens / 1000) * OUTPUT_COST_PER_1K
    
    return input_cost + output_cost

async def optimize_processing_cost(
    company_id: str,
    tickets: List[Dict],
    budget_limit: float = 10.0  # $10 per batch
) -> List[Dict]:
    """예산 제한 내에서 최적화된 처리"""
    
    # 1. 우선순위 기반 정렬 (중요도, 최신 순)
    priority_scores = []
    for ticket in tickets:
        score = 0
        
        # 우선순위 가중치
        if ticket.get('priority', '').lower() == 'high':
            score += 10
        elif ticket.get('priority', '').lower() == 'medium':
            score += 5
        
        # 최신 티켓 가중치
        created_at = datetime.fromisoformat(ticket.get('created_at', ''))
        days_old = (datetime.utcnow() - created_at).days
        score += max(0, 30 - days_old)  # 30일 이내 티켓 우선
        
        # 대화 길이 (더 복잡한 티켓 우선)
        conversation_length = len(ticket.get('full_conversation', ''))
        score += min(conversation_length / 1000, 10)  # 최대 10점
        
        priority_scores.append((score, ticket))
    
    # 2. 우선순위 정렬
    priority_scores.sort(key=lambda x: x[0], reverse=True)
    
    # 3. 예산 내에서 처리
    processed_tickets = []
    estimated_cost = 0.0
    
    for score, ticket in priority_scores:
        # 예상 비용 계산
        content_length = len(ticket.get('full_conversation', '') + ticket.get('description', ''))
        estimated_tokens = content_length / 4  # 대략적인 토큰 수
        ticket_cost = (estimated_tokens / 1000) * 0.0035  # GPT-3.5 평균 비용
        
        if estimated_cost + ticket_cost <= budget_limit:
            processed_tickets.append(ticket)
            estimated_cost += ticket_cost
        else:
            break
    
    logger.info(f"Selected {len(processed_tickets)} tickets within budget ${budget_limit:.2f}")
    return processed_tickets
```

---

## 🔄 **LLM 라우팅 & 대체 전략**

### 🌐 **멀티 모델 라우팅**

```python
class LLMRouter:
    def __init__(self):
        self.models = {
            'gpt-3.5-turbo': {
                'cost_per_1k': 0.0035,
                'quality_score': 8,
                'max_tokens': 4096,
                'available': True
            },
            'gpt-4o-mini': {
                'cost_per_1k': 0.0025,
                'quality_score': 9,
                'max_tokens': 8192,
                'available': True
            },
            'claude-3-haiku': {
                'cost_per_1k': 0.0015,
                'quality_score': 7,
                'max_tokens': 4096,
                'available': False  # 대체 모델
            }
        }
    
    async def route_request(
        self, 
        content: str, 
        quality_requirement: str = 'standard',
        budget_constraint: float = None
    ) -> str:
        """요구사항에 따른 최적 모델 선택"""
        
        content_length = len(content)
        estimated_tokens = content_length / 4
        
        # 1. 품질 요구사항 필터링
        quality_thresholds = {
            'basic': 6,
            'standard': 7,
            'high': 8,
            'premium': 9
        }
        
        min_quality = quality_thresholds.get(quality_requirement, 7)
        suitable_models = {
            name: info for name, info in self.models.items()
            if info['quality_score'] >= min_quality and info['available']
        }
        
        # 2. 예산 제약 필터링
        if budget_constraint:
            suitable_models = {
                name: info for name, info in suitable_models.items()
                if (estimated_tokens / 1000) * info['cost_per_1k'] <= budget_constraint
            }
        
        # 3. 비용 효율성 기준 선택
        if not suitable_models:
            return 'gpt-3.5-turbo'  # 기본 모델
        
        best_model = min(
            suitable_models.items(),
            key=lambda x: x[1]['cost_per_1k']
        )
        
        return best_model[0]

# 사용 예시
llm_router = LLMRouter()

async def smart_summarize(company_id: str, ticket: dict) -> dict:
    """스마트 모델 선택 기반 요약"""
    
    content = ticket.get('full_conversation', '') + ticket.get('description', '')
    
    # 품질 요구사항 결정
    quality_requirement = 'high' if ticket.get('priority') == 'high' else 'standard'
    
    # 최적 모델 선택
    selected_model = await llm_router.route_request(
        content=content,
        quality_requirement=quality_requirement,
        budget_constraint=0.01  # $0.01 per request
    )
    
    # LLM 호출
    response = await llm_client.chat.completions.create(
        model=selected_model,
        messages=[{
            "role": "user",
            "content": TICKET_SUMMARY_PROMPT.format(ticket_content=content)
        }],
        temperature=0.1
    )
    
    return orjson.loads(response.choices[0].message.content)
```

---

## 📊 **LLM 성능 모니터링**

### 📈 **처리 메트릭 추적**

```python
class LLMMetrics:
    def __init__(self):
        self.metrics = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'total_cost': 0.0,
            'cache_hits': 0,
            'cache_misses': 0,
            'average_response_time': 0.0,
            'model_usage': {}
        }
    
    async def track_request(
        self, 
        model: str, 
        tokens_used: int, 
        cost: float, 
        response_time: float, 
        success: bool,
        cache_hit: bool = False
    ):
        """LLM 요청 메트릭 추적"""
        
        self.metrics['total_requests'] += 1
        
        if success:
            self.metrics['successful_requests'] += 1
        else:
            self.metrics['failed_requests'] += 1
        
        self.metrics['total_cost'] += cost
        
        if cache_hit:
            self.metrics['cache_hits'] += 1
        else:
            self.metrics['cache_misses'] += 1
        
        # 모델별 사용량 추적
        if model not in self.metrics['model_usage']:
            self.metrics['model_usage'][model] = {
                'requests': 0,
                'tokens': 0,
                'cost': 0.0
            }
        
        self.metrics['model_usage'][model]['requests'] += 1
        self.metrics['model_usage'][model]['tokens'] += tokens_used
        self.metrics['model_usage'][model]['cost'] += cost
        
        # 평균 응답 시간 업데이트
        self.metrics['average_response_time'] = (
            (self.metrics['average_response_time'] * (self.metrics['total_requests'] - 1) + response_time)
            / self.metrics['total_requests']
        )
    
    def get_daily_report(self) -> dict:
        """일일 사용량 리포트"""
        cache_hit_rate = (
            self.metrics['cache_hits'] / 
            (self.metrics['cache_hits'] + self.metrics['cache_misses'])
            if (self.metrics['cache_hits'] + self.metrics['cache_misses']) > 0 else 0
        )
        
        return {
            'summary': {
                'total_requests': self.metrics['total_requests'],
                'success_rate': self.metrics['successful_requests'] / self.metrics['total_requests'] if self.metrics['total_requests'] > 0 else 0,
                'cache_hit_rate': cache_hit_rate,
                'total_cost': self.metrics['total_cost'],
                'average_response_time': self.metrics['average_response_time']
            },
            'model_breakdown': self.metrics['model_usage'],
            'cost_efficiency': {
                'cost_per_request': self.metrics['total_cost'] / self.metrics['total_requests'] if self.metrics['total_requests'] > 0 else 0,
                'savings_from_cache': cache_hit_rate * self.metrics['total_cost']
            }
        }

# 전역 메트릭 인스턴스
llm_metrics = LLMMetrics()
```

---

## 🔧 **실시간 피드백 루프**

### 🔄 **요약 품질 개선**

```python
async def collect_feedback(
    company_id: str,
    ticket_id: str,
    summary_id: str,
    feedback_type: str,  # 'helpful', 'not_helpful', 'incorrect'
    feedback_details: dict = None
):
    """요약에 대한 사용자 피드백 수집"""
    
    feedback_data = {
        'company_id': company_id,
        'ticket_id': ticket_id,
        'summary_id': summary_id,
        'feedback_type': feedback_type,
        'feedback_details': feedback_details or {},
        'created_at': datetime.utcnow().isoformat()
    }
    
    # 피드백 저장
    await save_feedback(feedback_data)
    
    # 부정적 피드백에 대한 즉시 재처리
    if feedback_type in ['not_helpful', 'incorrect']:
        await reprocess_with_feedback(company_id, ticket_id, feedback_details)

async def reprocess_with_feedback(
    company_id: str,
    ticket_id: str,
    feedback_details: dict
):
    """피드백 기반 요약 재생성"""
    
    # 원본 티켓 데이터 조회
    ticket = await get_ticket_data(company_id, ticket_id)
    
    # 피드백 반영 프롬프트
    improved_prompt = f"""
    {TICKET_SUMMARY_PROMPT}
    
    이전 요약에 대한 피드백:
    {feedback_details.get('comments', '')}
    
    특히 다음 사항에 주의하여 개선된 요약을 생성해주세요:
    - {feedback_details.get('improvement_areas', [])}
    """
    
    # 개선된 요약 생성
    response = await llm_client.chat.completions.create(
        model="gpt-4o-mini",  # 더 높은 품질 모델 사용
        messages=[{
            "role": "user",
            "content": improved_prompt.format(
                ticket_content=ticket.get('full_conversation', '')
            )
        }],
        temperature=0.1
    )
    
    improved_summary = orjson.loads(response.choices[0].message.content)
    
    # 개선된 요약 저장
    await save_improved_summary(company_id, ticket_id, improved_summary)
```

---

## 📚 **관련 참조 지침서**

- **data-collection-patterns.instructions.md** - 데이터 수집 및 전처리
- **vector-storage-search.instructions.md** - 벡터 저장 및 검색 전략
- **multitenant-security.instructions.md** - 멀티테넌트 보안 및 격리
- **error-handling-debugging.instructions.md** - LLM 처리 오류 대응
- **quick-reference.instructions.md** - 핵심 패턴 즉시 참조

---

## 🔗 **크로스 참조**

이 지침서는 다음과 연계됩니다:
- **데이터 수집**: 수집된 원본 데이터의 LLM 처리
- **벡터 검색**: 요약된 데이터의 임베딩 및 검색
- **멀티테넌트**: company_id 기반 LLM 처리 격리
- **성능 최적화**: 캐싱 및 배치 처리 전략

**세션 간 일관성**: 이 LLM 처리 패턴들은 AI 세션이 바뀌어도 동일하게 적용되어야 합니다.
