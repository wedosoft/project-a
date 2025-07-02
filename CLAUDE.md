# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a RAG (Retrieval-Augmented Generation) powered Freshdesk Custom App backend service. It provides AI-based response generation using Freshdesk tickets and knowledge base documents.

**Tech Stack:**
- FastAPI backend with async/await patterns
- Qdrant vector database for document storage and similarity search
- Multiple LLM providers (OpenAI, Anthropic, Gemini) with intelligent routing
- Docker containerization with docker-compose

## Common Development Commands

### Environment Setup
```bash
# Virtual environment setup (first time only)
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Daily development workflow
cd backend
source venv/bin/activate  # Always activate before running Python code

# Alternative activation script (if available)
cd backend && ./activate.sh

# For Code Interpreter/ChatGPT environment
./setup_codex_env.sh
```

**⚠️ CRITICAL**: Always run Python commands from the `backend/` directory with the virtual environment activated. Never run Python scripts from the project root.

### Running the Application
```bash
# Development server
cd backend && python -m api.main

# Docker environment
cd backend && docker-compose up -d

# View logs
docker logs -f project-a
```

### Testing
```bash
# Run tests with pytest
pytest backend/tests/

# Specific test examples
cd backend && python tests/test_vectordb.py
cd backend && python tests/test_llm_simple.py
```

### Data Collection
```bash
# Freshdesk data collection
cd backend/platforms/freshdesk && python run_collection.py

# Monitor collection progress
cd backend/platforms/freshdesk && bash scripts/monitor_collection.sh
```

## High-Level Architecture

### Core Components

1. **API Layer** (`backend/api/`)
   - FastAPI application with IoC container for dependency injection
   - Multiple routers: init, query, reply, ingest, health, metrics
   - Middleware for CORS, performance monitoring, error handling

2. **Vector Database** (`backend/core/database/vectordb.py`)
   - Abstract interface with Qdrant adapter implementation
   - Multi-tenant support with complete data isolation
   - Platform-neutral 3-tuple ID system: `(tenant_id, platform, original_id)`

3. **LLM Management** (`backend/core/llm/manager.py`)
   - Centralized management of multiple LLM providers
   - Use-case based routing (ticket_view, ticket_similar, summary)
   - Response and embedding caching with TTL

4. **Data Processing** (`backend/core/ingest/`)
   - Supports vector-only and hybrid (SQL+Vector) modes
   - Batch processing with progress tracking
   - Attachment processing with OCR support

### Key Design Patterns

- **Singleton**: LLM Manager for resource efficiency
- **Factory**: Vector DB adapter creation
- **Adapter**: Uniform interface for different vector DBs
- **IoC/DI**: Dependency injection in FastAPI
- **Strategy**: LLM routing based on use cases

### Data Flow

1. **Ingestion**: Freshdesk → Processor → Embeddings → Vector DB
2. **Query**: Request → Vector Search → LLM Processing → Response
3. **Real-time**: Streaming responses for better UX

### Environment Variables

Essential environment variables:
```bash
# Platform settings
FRESHDESK_DOMAIN=yourcompany.freshdesk.com
FRESHDESK_API_KEY=your_api_key
QDRANT_URL=https://your-cluster.cloud.qdrant.io
QDRANT_API_KEY=your_api_key
COMPANY_ID=your_company_id

# LLM configuration (template-based naming)
TICKET_VIEW_MODEL_PROVIDER=openai
TICKET_VIEW_MODEL_NAME=gpt-4-turbo
TICKET_SIMILAR_MODEL_PROVIDER=anthropic
TICKET_SIMILAR_MODEL_NAME=claude-3-haiku-20240307
SUMMARY_LLM_PROVIDER=openai
SUMMARY_LLM_MODEL=gpt-3.5-turbo

# API keys
ANTHROPIC_API_KEY=your_api_key
OPENAI_API_KEY=your_api_key
```

## Important Conventions

### Multi-tenancy
- All operations include `tenant_id` for data isolation
- Use `X-Company-ID` header in API requests

### Document Types
- `ticket`: Support tickets with conversations
- `kb`: Knowledge base articles
- `faq`: FAQ documents with separate scoring

### Language Requirements
- All internal documentation and comments must be in Korean (한글)
- User-facing error messages in Korean
- API responses can be in English or Korean based on request

### Performance Considerations
- Monitor LLM token usage
- Implement request timeouts and retries
- Use prometheus metrics for monitoring
- Optimize vector searches with appropriate top_k values

## Known Issues and Debugging

### Similar Ticket Summarization Issues

**Language Mixing (Korean → English):**
- **Location**: `backend/core/llm/summarizer/prompt/builder.py:126-129`
- **Issue**: Language instruction selection may not properly use `ui_language` parameter
- **Root Cause**: Check if `ui_language` is correctly passed through the entire chain from API → LLM Manager → Summarizer → Prompt Builder
- **Template**: `ticket_similar.yaml` has proper language instructions for all languages
- **Fix**: Verify `ui_language` parameter flow and ensure it reaches the prompt building stage
- **Test**: `pytest backend/tests/test_summary_quality.py -v`

**Current Template Structure (Post-Refactor):**
- **Location**: `backend/core/llm/summarizer/prompt/templates/`
- **Templates**: 
  - `ticket_view.yaml` - Premium quality for real-time ticket viewing (4-section structure: 🔍 Problem, 💡 Root Cause, ⚡ Resolution, 🎯 Insights)
  - `ticket_similar.yaml` - Standard quality for similar ticket analysis (simpler structure)
  - `knowledge_base.yaml` - Dedicated KB article processing
- **Status**: Migration completed from old `realtime_ticket.yaml` and `ticket.yaml` to new structure
- **Language Support**: All templates support ko/en/ja/zh with proper language instructions

**LLM Manager Routing:**
- **Location**: `backend/core/llm/manager.py:220-226`
- **Ticket View**: Uses `content_type="ticket_view"` with hardcoded `ui_language="ko"`
- **Similar Tickets**: Uses `content_type="ticket_similar"` with configurable language
- **Issue**: Ticket view endpoint may have hardcoded Korean language preference

### Debugging Commands

**IMPORTANT**: All Python tests and debugging must be run from the backend directory with the virtual environment activated:

```bash
# Always start with this setup
cd backend
source venv/bin/activate

# Test specific summarization quality
python tests/test_summary_quality.py

# Test template structure (verify sections)
python -c "
from core.llm.summarizer.prompt.builder import PromptBuilder
builder = PromptBuilder()
ticket_view_prompt = builder.build_system_prompt('ticket_view', 'ko', 'ko')
ticket_similar_prompt = builder.build_system_prompt('ticket_similar', 'ko', 'ko')
kb_prompt = builder.build_system_prompt('knowledge_base', 'ko', 'ko')
print('Ticket View sections:', '🔍' in ticket_view_prompt and '🎯' in ticket_view_prompt)
print('Ticket Similar language:', '한국어로만 응답하세요' in ticket_similar_prompt)
print('KB sections:', '📚' in kb_prompt and '🔧' in kb_prompt)
"

# Debug language detection
python -c "from core.llm.summarizer.utils.language import detect_content_language; print(detect_content_language('한국어 텍스트 예시'))"

# Check template loading
python -c "from core.llm.summarizer.prompt.loader import get_prompt_loader; loader = get_prompt_loader(); print(loader.get_system_prompt_template('ticket_similar')['language_instructions'])"

# Monitor prompt building process
python tests/test_realtime_separation.py

# Test language consistency fix
python -c "
from core.llm.summarizer.prompt.builder import PromptBuilder
builder = PromptBuilder()
prompt_ko = builder.build_system_prompt('ticket_similar', 'ko', 'ko')
prompt_en = builder.build_system_prompt('ticket_similar', 'en', 'en')
print('Korean UI language used:', '한국어로만 응답하세요' in prompt_ko)
print('English UI language used:', '영어로만 응답하세요' in prompt_en)
print('Template supports multilingual:', prompt_ko != prompt_en)
"

# Debug specific similar ticket endpoint language flow
python -c "
import asyncio
from core.llm.manager import LLMManager
async def test_language():
    manager = LLMManager()
    # Test Korean content
    result = await manager.summarize_similar_tickets(
        [{'content': '한국어 티켓 내용', 'subject': '한국어 제목'}],
        ui_language='ko'
    )
    print('Similar ticket Korean test:', '한국어' in str(result))
test = asyncio.run(test_language())
"
```

### Template Quality Verification
- **Ticket View**: Use `ticket_view.yaml` template for premium real-time viewing (4-section structure)
- **Similar Tickets**: Use `ticket_similar.yaml` template for efficient comparison summaries
- **Knowledge Base**: Use `knowledge_base.yaml` template for KB article processing
- Content language detection should match UI language instructions
- Section titles should match UI language preference
- All templates support ko/en/ja/zh with proper language-specific instructions

### Endpoint-Specific Language Issues
- **Similar Tickets Endpoint**: Check `ui_language` parameter flow from API request to prompt generation
- **Ticket View Endpoint**: Currently hardcoded to Korean (`ui_language="ko"`) in LLM Manager
- **Language Detection**: Automatic detection available but may need manual override for UI preferences