# 브랜치 2: 상담원 채팅 기능 간소화 가이드

## 🎯 목표
상담원이 "특정 티켓/KB/첨부파일을 찾아줘"라고 자연어로 요청하면, Anthropic 프롬프트 엔지니어링으로 정확한 검색 결과를 제공하는 기능

## 📋 Phase 1: 기본 구조 설계 (30분)

### 1.1 현재 검색 시스템 분석
```bash
# 기존 검색 코드 위치 확인
find backend/core/search -name "*.py"
grep -r "process_request\|search" backend/api/routes/
```

### 1.2 지원할 검색 패턴 정의
```python
# 지원 패턴들
PATTERNS = {
    "시간": ["오늘 생성된 티켓", "이번 주 해결된 케이스"],
    "카테고리": ["결제 문제", "API 오류"], 
    "복합": ["긴급한 VIP 고객 API 문제"]
}
```

## 📋 Phase 2: 의도 분석기 구현 (45분)

### 2.1 의도 분석기 생성
```python
# backend/core/search/anthropic/intent_analyzer.py
class AnthropicIntentAnalyzer:
    def __init__(self):
        self.intents = ["problem_solving", "info_gathering", "learning", "analysis"]
        self.urgency = ["immediate", "today", "general", "reference"]
    
    async def analyze_search_intent(self, query: str, context: dict = None):
        # 의도 분류
        intent = self._classify_intent(query)
        urgency = self._assess_urgency(query)
        keywords = self._extract_keywords(query)
        filters = self._parse_filters(query)
        
        return SearchContext(intent, urgency, keywords, filters)
```

### 2.2 Constitutional AI 프롬프트 템플릿
```yaml
# backend/core/search/prompts/constitutional_search.yaml
constitutional_principles:
  helpful: "상담원 업무에 즉시 도움되는 정보 제공"
  harmless: "개인정보 노출 절대 방지"
  honest: "검색 한계와 신뢰도 명시"

system_prompt: |
  당신은 상담원을 위한 전문 검색 어시스턴트입니다.
  Constitutional AI 원칙을 준수하여 도움되고 안전한 검색을 제공하세요.
  
  <response_format>
  <search_analysis>검색 의도 분석</search_analysis>
  <search_strategy>검색 전략</search_strategy>
  <primary_results>주요 결과</primary_results>
  <related_suggestions>관련 제안</related_suggestions>
  </response_format>
```

## 📋 Phase 3: 검색 오케스트레이터 구현 (60분)

### 3.1 메인 검색 오케스트레이터
```python
# backend/core/search/anthropic/search_orchestrator.py
class AnthropicSearchOrchestrator:
    def __init__(self):
        self.intent_analyzer = AnthropicIntentAnalyzer()
        self.hybrid_search = HybridSearchManager()
        self.llm_manager = LLMManager()
    
    async def execute_agent_search(self, query: str, tenant_id: str):
        # 1. 의도 분석
        context = await self.intent_analyzer.analyze_search_intent(query)
        
        # 2. 검색 실행
        results = await self.hybrid_search.hybrid_search(
            query=" ".join(context.keywords),
            tenant_id=tenant_id,
            filters=context.filters
        )
        
        # 3. 결과 최적화
        enhanced_results = await self._enhance_results(results, context)
        
        # 4. 구조화된 응답 생성
        structured_response = await self._generate_response(enhanced_results, context)
        
        return structured_response
```

### 3.2 프롬프트 빌더
```python
# backend/core/search/anthropic/prompt_builder.py
class AnthropicSearchPromptBuilder:
    def build_search_prompt(self, results: list, context, query: str):
        return f"""
상담원 요청: {query}
검색 의도: {context.intent}
시급성: {context.urgency}

검색 결과:
{self._format_results(results)}

위 결과를 XML 구조로 정리하여 상담원에게 유용한 응답을 생성하세요.
Constitutional AI 원칙을 준수하세요.
"""
```

## 📋 Phase 4: API 엔드포인트 구현 (30분)

### 4.1 REST API
```python
# backend/api/routes/agent_chat.py
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/agent-chat")

@router.post("/search")
async def agent_search(request: AgentChatRequest, tenant_id: str = Depends(get_tenant)):
    orchestrator = AnthropicSearchOrchestrator()
    
    async def stream_response():
        async for chunk in orchestrator.execute_agent_search(
            query=request.query,
            tenant_id=tenant_id
        ):
            yield f"data: {json.dumps(chunk)}\n\n"
    
    return StreamingResponse(stream_response(), media_type="text/event-stream")

@router.get("/suggestions")
async def get_suggestions(category: str = None, role: str = None):
    return {
        "quick_searches": ["오늘 생성된 긴급 티켓", "미해결 API 오류"],
        "role_based": ["L1용 빠른 해결책", "L2용 기술 분석"]
    }
```

### 4.2 요청/응답 모델
```python
class AgentChatRequest(BaseModel):
    query: str
    agent_context: Optional[dict] = None
    max_results: int = 10
    stream: bool = True

class SearchResult(BaseModel):
    id: str
    title: str
    content_preview: str
    relevance_score: float
    source_type: str
    actionable_insights: List[str]
```

## 📋 Phase 5: 프론트엔드 컴포넌트 (45분)

### 5.1 React 채팅 컴포넌트
```typescript
// frontend/src/components/AgentChat.tsx
const AgentChat: React.FC = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);

  const executeSearch = async (query: string) => {
    setLoading(true);
    
    const response = await fetch('/api/agent-chat/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, stream: true })
    });

    const reader = response.body?.getReader();
    // 스트리밍 응답 처리
    
    setLoading(false);
  };

  return (
    <div className="flex flex-col h-full">
      {/* 메시지 영역 */}
      <div className="flex-1 overflow-y-auto p-4">
        {messages.map(msg => (
          <MessageBubble key={msg.id} message={msg} />
        ))}
      </div>
      
      {/* 입력 영역 */}
      <div className="p-4 border-t">
        <div className="flex space-x-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="티켓/KB 검색..."
            className="flex-1 border rounded px-3 py-2"
          />
          <button
            onClick={() => executeSearch(input)}
            disabled={loading}
            className="bg-blue-600 text-white px-4 py-2 rounded"
          >
            검색
          </button>
        </div>
      </div>
    </div>
  );
};
```

## 📋 Phase 6: 테스트 및 검증 (30분)

### 6.1 통합 테스트
```python
# backend/test_agent_chat.py
async def test_anthropic_agent_chat():
    orchestrator = AnthropicSearchOrchestrator()
    
    test_cases = [
        "API 연동 오류 티켓 찾아줘",
        "이번 주 해결된 VIP 고객 케이스",
        "로그인 문제 해결 가이드"
    ]
    
    for query in test_cases:
        result = await orchestrator.execute_agent_search(
            query=query,
            tenant_id="test_tenant"
        )
        assert result is not None
        print(f"✅ {query}: 성공")
```

### 6.2 API 테스트
```python
async def test_api_endpoints():
    async with httpx.AsyncClient() as client:
        # 검색 API 테스트
        response = await client.post("/agent-chat/search", json={
            "query": "결제 문제 티켓들",
            "stream": False
        })
        assert response.status_code == 200
        
        # 제안 API 테스트
        response = await client.get("/agent-chat/suggestions")
        assert response.status_code == 200
```

## 📋 Phase 7: 환경 설정 및 배포 (15분)

### 7.1 환경변수 설정
```bash
# .env 추가
ENABLE_ANTHROPIC_AGENT_CHAT=true
AGENT_CHAT_MODEL_PROVIDER=anthropic
AGENT_CHAT_MODEL_NAME=claude-3-haiku-20240307
AGENT_CHAT_MAX_RESULTS=10
```

### 7.2 라우터 등록
```python
# backend/api/main.py
from api.routes.agent_chat import router as agent_chat_router

app.include_router(agent_chat_router, prefix="/api")
```

## 🔍 최종 체크리스트

- [ ] AnthropicIntentAnalyzer 구현
- [ ] Constitutional AI 프롬프트 템플릿 작성
- [ ] AnthropicSearchOrchestrator 구현
- [ ] API 엔드포인트 구현
- [ ] React 컴포넌트 구현
- [ ] 테스트 작성 및 실행
- [ ] 환경 설정 완료
- [ ] 라우터 등록

## 💡 Claude Code 사용법

1. 새 브랜치 생성: `feature/agent-chat-anthropic`
2. Phase별로 순차 진행
3. 각 Phase 완료 후 테스트
4. 문제 발생시 이전 단계로 롤백

각 Phase는 독립적으로 테스트 가능하며, 문제 발생시 해당 단계만 수정하면 됩니다.