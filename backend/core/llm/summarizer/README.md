# 🎯 Anthropic 프롬프트 엔지니어링 시스템

> **Freshdesk 티켓 요약을 위한 고품질 AI 시스템**
> 
> Constitutional AI, XML 구조화, Chain-of-Thought 추론 등 Anthropic의 최첨단 프롬프트 엔지니어링 기법을 적용한 티켓 요약 시스템입니다.

## 📋 목차

- [🎯 시스템 개요](#-시스템-개요)
- [✨ 핵심 기능](#-핵심-기능)
- [🏗️ 아키텍처](#️-아키텍처)
- [🚀 빠른 시작](#-빠른-시작)
- [⚙️ 설정 관리](#️-설정-관리)
- [📊 품질 관리](#-품질-관리)
- [🔧 관리자 도구](#-관리자-도구)
- [📈 성능 최적화](#-성능-최적화)
- [🔍 모니터링](#-모니터링)
- [🛠️ 문제 해결](#️-문제-해결)

## 🎯 시스템 개요

### 핵심 목표
- **상담원 생산성 향상**: 5초 내 파악 가능한 고품질 요약 제공
- **정보 보안 강화**: 개인정보 노출 방지 및 Constitutional AI 준수
- **운영 효율성**: 코드 수정 없는 프롬프트 관리 및 실시간 품질 모니터링

### 주요 특징
- 🧠 **Constitutional AI**: Helpful, Harmless, Honest 원칙 적용
- 📝 **XML 구조화**: 일관된 응답 형식 보장
- 🔗 **Chain-of-Thought**: 논리적 추론 과정 포함
- ⚡ **실시간 처리**: 2초 이내 응답 시간 목표
- 🛡️ **품질 검증**: 다차원 품질 평가 및 자동 폴백
- 🎨 **관리자 친화적**: 웹 인터페이스를 통한 프롬프트 편집

A comprehensive, modular summarization system designed for scalability, maintainability, and high-quality output.

## Architecture Overview

The system is organized into specialized modules, each handling a specific aspect of the summarization process:

```
backend/core/llm/summarizer/
├── core/                    # Main summarization logic
│   └── summarizer.py       # CoreSummarizer class
├── prompt/                 # Prompt management
│   ├── templates/          # YAML templates
│   ├── loader.py          # Template loader
│   └── builder.py         # Prompt builder
├── attachment/            # Attachment handling
│   ├── config.py         # Configuration
│   └── selector.py       # LLM-based selection
├── quality/              # Quality validation
│   └── validator.py      # Quality metrics
├── context/              # Context optimization
│   └── optimizer.py      # Content optimization
├── email/                # Email processing
│   └── processor.py      # Email-specific handling
├── hybrid/               # Large content handling
│   └── summarizer.py     # Adaptive strategies
├── utils/                # Utilities
│   └── language.py       # Language detection
└── tests/                # Test suite
    └── test_summarizer.py
```

## Key Features

### 1. **LLM-Selected Attachments Only**
- Uses intelligent scoring to select 1-3 most relevant attachments
- Prevents information overload for agents
- Policy-driven selection criteria

### 2. **Prompt Template Management**
- YAML-based templates for easy editing
- Jinja2 template engine with fallback logic
- Version control friendly
- Language-specific prompts

### 3. **Quality Validation**
- Multi-dimensional quality scoring
- Structural completeness verification  
- Language consistency checks
- Automatic regeneration for low-quality outputs

### 4. **Adaptive Content Handling**
- Small content: Standard processing
- Medium content: Chunked processing
- Large content: Rolling summarization
- Email-specific preprocessing

### 5. **Advanced Language Support**
- Automatic language detection
- Multilingual section titles
- Cultural context awareness
- Mixed language content handling

## Usage Examples

### Basic Usage

```python
from backend.core.llm.summarizer import generate_optimized_summary

# Simple summarization
summary = await generate_optimized_summary(
    content="Your content here",
    content_type="ticket",
    subject="Issue subject",
    metadata={
        'attachments': [
            {'name': 'error.log', 'content_type': 'text/plain'},
            {'name': 'screenshot.png', 'content_type': 'image/png'}  
        ]
    },
    ui_language="ko"
)
```

### Advanced Usage with Hybrid Summarizer

```python
from backend.core.llm.summarizer import HybridSummarizer

hybrid = HybridSummarizer()

# Automatically adapts strategy based on content size
summary = await hybrid.generate_hybrid_summary(
    content=large_content,
    content_type="email",
    subject="Long email thread",
    ui_language="en"
)
```

### Custom Prompt Building

```python
from backend.core.llm.summarizer import PromptBuilder

builder = PromptBuilder()

# Build custom system prompt
system_prompt = builder.build_system_prompt(
    content_type="knowledge_base",
    content_language="ko", 
    ui_language="ko"
)

# Build user prompt with context
user_prompt = builder.build_user_prompt(
    content="Content to analyze",
    content_type="ticket",
    subject="Custom subject",
    metadata={'priority': 'high'},
    content_language="ko",
    ui_language="ko"
)
```

## Module Details

### Core Summarizer (`core/summarizer.py`)
- Main orchestration logic
- Component integration
- Backward compatibility interface
- Error handling and fallbacks

### Prompt Management (`prompt/`)
- **loader.py**: YAML template loading with caching
- **builder.py**: Dynamic prompt generation with Jinja2
- **templates/**: Organized YAML templates by type and language

### Attachment Selection (`attachment/`)
- **selector.py**: LLM-based relevance scoring
- **config.py**: Selection policies and thresholds
- Smart filtering prevents irrelevant attachments

### Quality Validation (`quality/`)
- **validator.py**: Multi-criteria quality assessment
- Structure, content, language, and format validation
- Automatic regeneration triggers

### Context Optimization (`context/`)
- **optimizer.py**: Content size and relevance optimization  
- Section prioritization
- Smart truncation
- Content-type specific optimizations

### Email Processing (`email/`)
- **processor.py**: Email-specific content handling
- Thread deduplication
- Header/signature removal
- Action item extraction

### Hybrid Summarization (`hybrid/`)
- **summarizer.py**: Adaptive strategy selection
- Rolling summarization for large content
- Chunked processing for medium content
- Context preservation across chunks

### Language Utilities (`utils/`)
- **language.py**: Advanced language detection
- Multilingual section titles
- Text complexity analysis
- Key phrase extraction

## Configuration

### Attachment Selection Policy

The system uses a sophisticated scoring algorithm:

```python
# High relevance (score ≥ 10): Directly mentioned files
# Medium relevance (score 7-9): Images, configs with keywords  
# Low relevance (score 5-6): Log files with content correlation
# Rejected (score < 5): Unrelated files
```

### Quality Thresholds

```python
QUALITY_THRESHOLDS = {
    'minimum_acceptable': 0.5,
    'good_quality': 0.7, 
    'excellent_quality': 0.9,
    'regeneration_threshold': 0.6
}
```

### Content Size Strategies

```python
CONTENT_STRATEGIES = {
    'small': '≤ 15K chars - Standard processing',
    'medium': '15K-35K chars - Chunked processing', 
    'large': '> 35K chars - Rolling summarization'
}
```

## Migration from Legacy System

The new system maintains backward compatibility:

```python
# Legacy code continues to work
from backend.core.llm.optimized_summarizer import generate_optimized_summary

# New modular approach  
from backend.core.llm.summarizer import generate_optimized_summary
```

Both imports resolve to the same function, ensuring seamless migration.

## Testing

Run the test suite:

```bash
cd backend/core/llm/summarizer
python -m pytest tests/ -v
```

## Performance Optimizations

1. **Template Caching**: YAML templates cached after first load
2. **Attachment Pre-filtering**: Quick elimination of irrelevant files
3. **Context Optimization**: Reduces LLM token usage by 30-70%  
4. **Quality-based Early Termination**: Skips regeneration for high-quality outputs
5. **Adaptive Chunking**: Optimal chunk sizes based on content type

## Future Enhancements

- [ ] Integration with vector similarity for attachment selection
- [ ] Custom prompt templates per customer/domain
- [ ] Advanced caching for repeated content patterns
- [ ] Real-time quality feedback learning
- [ ] Multi-agent summarization for complex scenarios

## Dependencies

- `jinja2`: Template rendering
- `pyyaml`: YAML template parsing  
- `backend.core.llm.llm_manager`: LLM integration
- `logging`: Comprehensive logging
- `dataclasses`: Type-safe data structures

## Contributing

When adding new features:

1. Follow the modular architecture pattern
2. Add comprehensive tests
3. Update YAML templates for prompt changes
4. Maintain backward compatibility
5. Document configuration options

## License

Internal project - Follow company guidelines for code usage and distribution.
