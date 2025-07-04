# LLM Management - CLAUDE.md

## 🎯 Context & Purpose

This is the **LLM Management** worktree focused on Language Model orchestration, prompt management, and AI response generation for Copilot Canvas. This handles all LLM providers, response caching, and AI workflow coordination.

**Primary Focus Areas:**
- Multi-provider LLM management (OpenAI, Anthropic, Google, etc.)
- Use-case specific model routing and optimization
- Prompt template management and engineering
- Response caching and performance optimization
- LangChain integration and custom chains

## 🏗️ LLM Architecture

### System Overview
```
User Query → Prompt Template → LLM Provider → Response Caching → Final Output
     ↓             ↓              ↓              ↓               ↓
  Context      Use-case      Model Selection   Performance    User/API
 Enrichment    Routing                        Optimization
```

### Core Components

1. **LLM Manager** (`llm/manager.py`)
   - Centralized LLM provider management
   - Use-case based model routing
   - Response caching with TTL
   - Fallback and retry logic

2. **Provider Integrations** (`llm/integrations/`)
   - **langchain/**: LangChain framework integration
   - **direct/**: Direct API integrations
   - Provider-specific configurations
   - Custom chains and workflows

3. **Summarization System** (`llm/summarizer/`)
   - **core/**: Main summarization logic
   - **prompt/**: Template management
   - **attachment/**: File processing
   - **quality/**: Output validation

4. **Prompt Management**
   - YAML-based template system
   - Dynamic prompt building
   - Context optimization
   - Multi-language support

### Key Design Patterns

- **Strategy Pattern**: Pluggable LLM providers
- **Factory Pattern**: Provider and chain creation
- **Template Method**: Consistent prompt workflows
- **Caching**: Response and embedding caching
- **Circuit Breaker**: Fallback for provider failures

## 🚀 Development Commands

### Environment Setup
```bash
# Virtual environment (from backend directory)
source venv/bin/activate

# Verify LLM providers
python -c "from core.llm.manager import LLMManager; print('✅ LLM Manager OK')"

# Test specific provider
python -c "
from core.llm.manager import LLMManager
manager = LLMManager()
response = manager.generate_text('Hello, world!', 'gemini-1.5-flash')
print('✅ LLM Response:', response[:50])
"
```

### LLM Testing
```bash
# Test LLM manager
python -c "
from core.llm.manager import LLMManager
manager = LLMManager()
print('Available providers:', manager.get_available_providers())
"

# Test summarization
python -c "
from core.llm.summarizer import generate_optimized_summary
summary = generate_optimized_summary('Long text content here...')
print('Summary:', summary)
"

# Test LangChain integration
python -c "
from core.llm.integrations.langchain import LLMManager
llm = LLMManager()
response = llm.generate_response('Test query', use_case='ticket_view')
print('LangChain response:', response)
"
```

## 🔧 Key Environment Variables

```bash
# LLM API Keys
ANTHROPIC_API_KEY=sk-ant-api03-...
OPENAI_API_KEY=sk-proj-...
GOOGLE_API_KEY=AIzaSy...
DEEPSEEK_API_KEY=sk-...
PERPLEXITY_API_KEY=pplx-...
OPENROUTER_API_KEY=sk-or-v1-...

# LLM Timeouts (seconds)
LLM_GLOBAL_TIMEOUT=15.0
LLM_GEMINI_TIMEOUT=12.0
LLM_DEEPSEEK_TIMEOUT=15.0
LLM_ANTHROPIC_TIMEOUT=15.0
LLM_OPENAI_TIMEOUT=15.0

# Model Configuration
LLM_LIGHT_MODEL=gemini-1.5-flash      # Fast operations
LLM_HEAVY_MODEL=gemini-1.5-pro        # Complex tasks
LLM_MAX_RETRIES=1
MAX_TOKENS=4096

# Use-case Specific Models
TICKET_VIEW_MODEL_PROVIDER=gemini
TICKET_VIEW_MODEL_NAME=gemini-1.5-flash
TICKET_SIMILAR_MODEL_PROVIDER=gemini
TICKET_SIMILAR_MODEL_NAME=gemini-1.5-flash

# Caching
LLM_CACHE_TTL=3600
ENABLE_LLM_CACHE=true
```

## 📁 Directory Structure

```
core/llm/
├── __init__.py
├── manager.py              # Main LLM manager
├── integrations/           # Provider integrations
│   ├── __init__.py
│   ├── langchain/         # LangChain integration
│   │   ├── __init__.py
│   │   ├── llm_manager.py # LangChain LLM manager
│   │   └── chains/        # Custom chains
│   └── direct/            # Direct API integrations
└── summarizer/            # Summarization system
    ├── __init__.py
    ├── core/              # Main logic
    │   └── summarizer.py  # Core summarizer
    ├── prompt/            # Template management
    │   ├── templates/     # YAML templates
    │   ├── loader.py      # Template loader
    │   └── builder.py     # Prompt builder
    ├── attachment/        # File processing
    ├── quality/           # Quality validation
    ├── context/           # Context optimization
    └── email/             # Email processing
```

## 🔍 Common Tasks

### Basic LLM Operations
```python
# Initialize LLM manager
from core.llm.manager import LLMManager

manager = LLMManager()

# Generate simple text response
response = await manager.generate_text(
    prompt="Summarize this customer issue: ...",
    model="gemini-1.5-flash",
    max_tokens=500,
    temperature=0.1
)

# Use-case specific generation
response = await manager.generate_response(
    query="Customer login problem",
    context="Previous tickets and solutions...",
    use_case="ticket_view"  # Routes to appropriate model
)

# Get provider status
status = manager.get_provider_status()
print("Available providers:", status["available"])
print("Failed providers:", status["failed"])
```

### Summarization System
```python
# Generate optimized summary
from core.llm.summarizer import generate_optimized_summary

summary = await generate_optimized_summary(
    content="Long customer conversation...",
    summary_type="ticket",
    max_length=200,
    focus="resolution"
)

# Batch summarization
from core.llm.summarizer.core import CoreSummarizer

summarizer = CoreSummarizer()
summaries = await summarizer.batch_summarize([
    {"content": "Ticket 1 content", "type": "ticket"},
    {"content": "Article 1 content", "type": "article"},
    {"content": "Conversation 1", "type": "conversation"}
])
```

### Prompt Template Management
```python
# Load prompt templates
from core.llm.summarizer.prompt.loader import PromptLoader

loader = PromptLoader()
templates = loader.load_all_templates()

# Build dynamic prompt
from core.llm.summarizer.prompt.builder import PromptBuilder

builder = PromptBuilder()
prompt = builder.build_prompt(
    template_name="ticket_analysis",
    variables={
        "ticket_content": "Customer reported login issues...",
        "previous_solutions": "Try password reset, clear cache...",
        "urgency": "high"
    }
)

# Use built prompt
response = await manager.generate_text(prompt, "gemini-1.5-flash")
```

### LangChain Integration
```python
# Use LangChain LLM manager
from core.llm.integrations.langchain import LLMManager as LangChainLLM

llm = LangChainLLM()

# Execute custom chain
from core.llm.integrations.langchain.chains import execute_init_parallel_chain

result = await execute_init_parallel_chain(
    ticket_data={"id": 123, "subject": "Login issues"},
    tenant_id="wedosoft",
    platform="freshdesk"
)

# Use streaming response
async for chunk in llm.stream_response(
    query="Analyze this ticket",
    use_case="ticket_view"
):
    print(chunk, end="", flush=True)
```

### Provider Management
```python
# Add new provider
from core.llm.manager import LLMManager

manager = LLMManager()

# Register custom provider
manager.register_provider(
    name="custom_provider",
    api_key="your-api-key",
    base_url="https://api.custom.com/v1",
    models=["custom-model-1", "custom-model-2"]
)

# Set provider preferences
manager.set_provider_preference(
    use_case="ticket_view",
    preferred_providers=["gemini", "openai", "custom_provider"]
)

# Handle provider failures
try:
    response = await manager.generate_text(prompt, "primary-model")
except ProviderError:
    response = await manager.generate_text(prompt, "fallback-model")
```

## 🎯 Use-Case Specific Routing

### Model Selection Strategy
```python
# Configure models for different use cases
USE_CASE_MODELS = {
    "ticket_view": {
        "provider": "gemini",
        "model": "gemini-1.5-flash",
        "max_tokens": 1200,
        "temperature": 0.05
    },
    "ticket_similar": {
        "provider": "gemini", 
        "model": "gemini-1.5-flash",
        "max_tokens": 800,
        "temperature": 0.1
    },
    "reply_generation": {
        "provider": "anthropic",
        "model": "claude-3-haiku",
        "max_tokens": 1000,
        "temperature": 0.3
    },
    "summarization": {
        "provider": "openai",
        "model": "gpt-3.5-turbo",
        "max_tokens": 500,
        "temperature": 0.1
    }
}

# Route based on use case
async def route_llm_request(query: str, use_case: str):
    config = USE_CASE_MODELS.get(use_case)
    if not config:
        raise ValueError(f"Unknown use case: {use_case}")
    
    return await manager.generate_text(
        prompt=query,
        model=config["model"],
        max_tokens=config["max_tokens"],
        temperature=config["temperature"]
    )
```

### Performance Optimization
```python
# Implement response caching
from functools import lru_cache
import hashlib

class CachedLLMManager:
    def __init__(self):
        self.manager = LLMManager()
        self.cache = {}
        self.cache_ttl = 3600  # 1 hour
    
    async def cached_generate(self, prompt: str, model: str, **kwargs):
        # Generate cache key
        cache_key = hashlib.md5(
            f"{prompt}:{model}:{kwargs}".encode()
        ).hexdigest()
        
        # Check cache
        if cache_key in self.cache:
            cached_result, timestamp = self.cache[cache_key]
            if time.time() - timestamp < self.cache_ttl:
                return cached_result
        
        # Generate new response
        response = await self.manager.generate_text(prompt, model, **kwargs)
        
        # Cache result
        self.cache[cache_key] = (response, time.time())
        
        return response
```

## 🚨 Important Notes

### API Cost Management
- Use light models (gemini-1.5-flash) for simple tasks
- Cache responses to avoid duplicate API calls
- Monitor token usage across providers
- Implement rate limiting for cost control

### Performance Considerations
- Async/await for all LLM operations
- Batch requests when possible
- Use streaming for long responses
- Implement timeout and retry logic

### Error Handling
- Always have fallback providers configured
- Handle API rate limits gracefully
- Log failed requests for debugging
- Provide meaningful error messages to users

## 🔗 Integration Points

### Vector Search Integration
```python
# LLM uses vector search results as context
from core.database.vectordb import vector_db
from core.llm.manager import LLMManager

async def generate_contextual_response(query: str, tenant_id: str):
    # Get relevant context from vector search
    search_results = await vector_db.search(
        collection_name="documents",
        query_text=query,
        filters={"tenant_id": tenant_id},
        limit=5
    )
    
    # Build context from search results
    context = "\n".join([
        f"Document {i+1}: {result.metadata['content'][:200]}..."
        for i, result in enumerate(search_results)
    ])
    
    # Generate response with context
    manager = LLMManager()
    response = await manager.generate_response(
        query=query,
        context=context,
        use_case="ticket_view"
    )
    
    return response
```

### API Layer Integration
```python
# API endpoints use LLM manager
from fastapi import APIRouter
from core.llm.manager import LLMManager

@router.post("/api/analyze")
async def analyze_ticket(ticket_data: dict):
    manager = LLMManager()
    
    analysis = await manager.generate_response(
        query=f"Analyze this ticket: {ticket_data['subject']}",
        context=ticket_data['description'],
        use_case="ticket_view"
    )
    
    return {"analysis": analysis}

@router.post("/api/suggest-reply")
async def suggest_reply(conversation: dict):
    manager = LLMManager()
    
    reply = await manager.generate_response(
        query="Generate professional reply",
        context=conversation['messages'],
        use_case="reply_generation"
    )
    
    return {"suggested_reply": reply}
```

### Data Pipeline Integration
```python
# Summarization during data ingestion
from core.llm.summarizer import generate_optimized_summary

async def process_ticket_with_summary(ticket_data: dict):
    # Generate summary for vector storage
    summary = await generate_optimized_summary(
        content=ticket_data['description'],
        summary_type="ticket",
        max_length=150
    )
    
    # Store both original and summary
    return {
        "original_content": ticket_data['description'],
        "summary": summary,
        "metadata": ticket_data
    }
```

## 📚 Key Files to Know

- `core/llm/manager.py` - Main LLM manager and provider coordination
- `core/llm/integrations/langchain/llm_manager.py` - LangChain integration
- `core/llm/summarizer/core/summarizer.py` - Core summarization logic
- `core/llm/summarizer/prompt/templates/` - YAML prompt templates
- `core/llm/integrations/langchain/chains/` - Custom LangChain chains

## 🔄 Development Workflow

1. **Start Development**: Verify API keys are configured
2. **Test Providers**: Check all LLM providers are accessible
3. **Implement Feature**: Add new prompts or use cases
4. **Test Responses**: Verify output quality and consistency
5. **Optimize Performance**: Add caching and fallbacks
6. **Monitor Usage**: Track API costs and response times

## 🚀 Advanced Features

### Custom Chain Development
```python
# Create custom LangChain chain
from langchain.chains.base import Chain
from langchain.schema import LLMResult

class CustomAnalysisChain(Chain):
    llm_manager: LLMManager
    
    @property
    def input_keys(self):
        return ["ticket_data", "context"]
    
    @property 
    def output_keys(self):
        return ["analysis", "suggestions", "priority"]
    
    def _call(self, inputs):
        ticket_data = inputs["ticket_data"]
        context = inputs["context"]
        
        # Multi-step analysis
        analysis = self.llm_manager.generate_text(
            f"Analyze this ticket: {ticket_data}",
            model="gemini-1.5-pro"
        )
        
        suggestions = self.llm_manager.generate_text(
            f"Based on analysis: {analysis}, suggest solutions",
            model="gemini-1.5-flash"
        )
        
        priority = self.llm_manager.generate_text(
            f"Determine priority for: {ticket_data}",
            model="gemini-1.5-flash"
        )
        
        return {
            "analysis": analysis,
            "suggestions": suggestions,
            "priority": priority
        }
```

### Streaming Responses
```python
# Implement streaming for real-time responses
async def stream_llm_response(query: str, use_case: str):
    manager = LLMManager()
    
    async for chunk in manager.stream_response(query, use_case):
        # Process chunk
        yield {
            "type": "chunk",
            "content": chunk,
            "timestamp": time.time()
        }
    
    # Send completion signal
    yield {
        "type": "complete",
        "timestamp": time.time()
    }

# Use in API endpoint
@router.post("/api/stream-analysis")
async def stream_analysis(query: str):
    return StreamingResponse(
        stream_llm_response(query, "ticket_view"),
        media_type="application/x-ndjson"
    )
```

### Quality Assurance
```python
# Implement response quality validation
class ResponseValidator:
    def __init__(self):
        self.min_length = 50
        self.max_length = 2000
        self.forbidden_phrases = ["I don't know", "Sorry, I can't"]
    
    def validate_response(self, response: str, context: str) -> dict:
        issues = []
        
        # Length validation
        if len(response) < self.min_length:
            issues.append("Response too short")
        if len(response) > self.max_length:
            issues.append("Response too long")
        
        # Content validation
        for phrase in self.forbidden_phrases:
            if phrase.lower() in response.lower():
                issues.append(f"Contains forbidden phrase: {phrase}")
        
        # Relevance check (simplified)
        relevance_score = self.calculate_relevance(response, context)
        if relevance_score < 0.5:
            issues.append("Low relevance to context")
        
        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "relevance_score": relevance_score
        }
```

---

*This worktree focuses exclusively on LLM management and AI response generation. For vector search context, use the vector-db worktree. For data processing, use the data-pipeline worktree.*
