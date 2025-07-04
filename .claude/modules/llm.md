# LLM 관리 모듈 가이드

## 🎯 모듈 목적
다중 LLM 제공자 관리, 프롬프트 최적화, AI 응답 생성을 담당하는 핵심 모듈

**핵심 기능:**
- 다중 LLM 제공자 (OpenAI, Anthropic, Google)
- 사용 사례별 모델 라우팅
- 프롬프트 템플릿 관리
- 응답 캐싱 및 성능 최적화
- LangChain 통합

## 🏗️ LLM 아키텍처
```
사용자 쿼리 → 프롬프트 템플릿 → LLM 제공자 → 응답 캐싱 → 최종 출력
```

## 🔧 개발 패턴

### 1. LLM 제공자 추상화
```python
class LLMProvider:
    async def generate(self, prompt: str, model: str) -> str:
        """LLM 제공자별 구현"""
        raise NotImplementedError
        
class OpenAIProvider(LLMProvider):
    async def generate(self, prompt: str, model: str) -> str:
        response = await self.client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
```

### 2. 사용 사례별 라우팅
```python
USE_CASE_MODELS = {
    "ticket_view": {"provider": "gemini", "model": "gemini-1.5-flash"},
    "ticket_similar": {"provider": "gemini", "model": "gemini-1.5-flash"},
    "summary": {"provider": "openai", "model": "gpt-4o-mini"}
}

async def route_request(use_case: str, prompt: str) -> str:
    config = USE_CASE_MODELS.get(use_case)
    provider = get_provider(config["provider"])
    return await provider.generate(prompt, config["model"])
```

### 3. 응답 캐싱 전략
```python
@ttl_cache(ttl_seconds=3600)  # 1시간 캐시
async def cached_llm_request(prompt_hash: str, model: str) -> str:
    """LLM 응답 캐싱으로 성능 최적화"""
    return await llm_provider.generate(prompt, model)
```

## 📊 성능 최적화

### 배치 처리
```python
async def batch_process_tickets(tickets: List[dict]) -> List[str]:
    """여러 티켓을 배치로 처리하여 성능 향상"""
    tasks = []
    for ticket in tickets:
        task = process_single_ticket(ticket)
        tasks.append(task)
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return [r for r in results if not isinstance(r, Exception)]
```

### 토큰 사용량 최적화
```python
def optimize_prompt_length(content: str, max_tokens: int = 4000) -> str:
    """프롬프트 길이 최적화"""
    if len(content.split()) <= max_tokens:
        return content
    
    # 중요 섹션 우선 유지
    sentences = content.split('.')
    important_parts = []
    token_count = 0
    
    for sentence in sentences:
        sentence_tokens = len(sentence.split())
        if token_count + sentence_tokens <= max_tokens:
            important_parts.append(sentence)
            token_count += sentence_tokens
        else:
            break
    
    return '.'.join(important_parts)
```

## 🚨 에러 처리

### LLM 장애 대응
```python
async def resilient_llm_call(prompt: str, use_case: str) -> str:
    """LLM 호출 시 장애 대응"""
    primary_config = USE_CASE_MODELS[use_case]
    fallback_configs = get_fallback_models(use_case)
    
    # 1차 시도
    try:
        return await call_llm(prompt, primary_config)
    except Exception as e:
        logger.warning(f"Primary LLM failed: {e}")
    
    # 폴백 시도
    for fallback_config in fallback_configs:
        try:
            result = await call_llm(prompt, fallback_config)
            logger.info(f"Fallback successful with {fallback_config}")
            return result
        except Exception as e:
            logger.warning(f"Fallback failed: {e}")
            continue
    
    raise Exception("All LLM providers failed")
```

## 🎯 현재 최적화 목표
- **응답 시간**: 평균 2초 이내
- **캐시 적중률**: 60% 이상
- **토큰 효율성**: 20% 절약
- **에러율**: 1% 이하
