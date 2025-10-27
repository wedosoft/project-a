# RAG Search Quality Improvement Implementation Plan

## 🎯 Executive Summary

Based on comprehensive analysis of the poor RAG search results (Image showing 72-73% scores for irrelevant results like "#4278 후라후라", "#500895324 관련 티켓을 못보", "#5277 티켓 등록 문의" for query "유사한 티켓 찾아줘"), this document outlines the root cause and systematic improvements following CLAUDE.md principles.

## 🔍 Root Cause Analysis

### Primary Issue: **Query Intent Misclassification**
- Query "유사한 티켓 찾아줘" treated as content search instead of functional similarity request
- System searches for documents containing words "similar" + "tickets" rather than performing similarity operation
- No context provided for what tickets should be similar to

### Secondary Issues:
1. **Score Inflation**: RRF fusion producing misleading 72-73% confidence scores
2. **Missing Korean Language Support**: Limited synonym expansion and semantic understanding
3. **No Complex Query Processing**: Cannot handle multi-conditional queries like "한달 전에 누가 제출한 우선순위가 높은 티켓 찾아줘"
4. **Inadequate Quality Thresholds**: Min score of 0.6 too low for meaningful results

## 📋 Implementation Strategy

### Phase 1: YAML Configuration Setup (Following CLAUDE.md Rules)

**Files Created/Modified:**
1. ✅ `/backend/config/search_intents.yaml` - Updated with complex intent detection
2. ✅ `/backend/config/complex_query_processing.yaml` - New comprehensive query processing
3. 🔄 `/backend/core/search/chat_search.py` - Remove hardcoded patterns, use YAML configs

### Phase 2: Core Architecture Improvements

#### A. Intent Detection Enhancement
```yaml
# config/search_intents.yaml
search_intent_detection:
  intent_detection_prompt: |
    # LLM-based classification for:
    - simple_keyword: "로그인", "John Smith"
    - simple_semantic: "help with login"  
    - complex_conditional: "한달 전에 누가 제출한 우선순위가 높은..."
    - similarity_search: "유사한 티켓", "similar tickets"
    - functional: "내 티켓", "recent tickets"
```

#### B. Complex Query Processing
```yaml
# config/complex_query_processing.yaml
complex_query_processing:
  query_analysis_prompt: |
    # Extract time, person, priority, status, content filters
    # Generate structured JSON with conditions
  
  search_strategy_prompt: |
    # Determine optimal search approach based on conditions
    # metadata_filter vs content_search vs hybrid_search
```

### Phase 3: Search Quality Improvements

#### A. Dynamic Score Thresholds
```python
quality_thresholds:
  metadata_filter: 0.5   # Lower for filtered results
  content_search: 0.75   # Higher for content matching
  similarity_search: 0.7 # High for similarity
```

#### B. Context-Aware Processing
- **Similarity Search**: Request clarification or use conversation context
- **Complex Conditions**: Parse multiple filters and apply strategically
- **Metadata-Heavy**: Prioritize sparse search (0.6 weight vs 0.4 dense)

### Phase 4: Response Quality Enhancement

#### A. Structured Response Templates
```yaml
response_templates:
  metadata_heavy:
    success: |
      {filter_summary}에 해당하는 {doc_type} {count}개를 찾았습니다:
      📊 필터 적용 결과: {applied_filters}
      🎯 상위 결과: {results}
```

#### B. Fallback Strategies  
```yaml
fallback_patterns:
  time_keywords: ["전", "ago", "최근", "한달"]
  person_keywords: ["누가", "who", "담당", "제출"]
  priority_keywords: ["우선순위", "긴급", "높은", "urgent"]
```

## 🚀 Expected Improvements

### Immediate Impact (Phase 1-2):
- **Query "유사한 티켓 찾아줘"**: Properly classified as `similarity_search` intent
- **Context Request**: System asks for clarification or uses conversation context  
- **Score Quality**: Improved thresholds reduce false positives
- **Korean Support**: Better synonym expansion and semantic understanding

### Medium-term Benefits (Phase 3-4):
- **Complex Queries**: Handle "한달 전에 누가 제출한 우선순위가 높은 티켓" with proper filter extraction
- **Search Strategy**: Metadata-heavy queries use sparse search weighting
- **Response Quality**: Structured, informative responses with filter summaries

### Long-term Enhancements:
- **Learning System**: Track query success rates and adapt thresholds
- **Multi-language**: Expand beyond Korean/English to Japanese/Chinese
- **Advanced Similarity**: Document-to-document similarity recommendations

## 📊 Success Metrics

### Before (Current State):
- Query "유사한 티켓 찾아줘" returns irrelevant results with 72-73% scores
- No complex query support  
- Limited Korean language processing

### After (Target State):
- Similarity queries properly classified and handled
- Complex conditional queries parsed and executed
- Relevant results with appropriate confidence scores
- Structured, informative responses

### Measurable KPIs:
1. **Relevance Score Accuracy**: Reduce false positives by 60%
2. **Query Intent Classification**: 95% accuracy for test queries
3. **Complex Query Support**: Handle 5+ filter combinations
4. **User Satisfaction**: Improved response quality metrics

## 🔧 Implementation Timeline

### Week 1: Configuration Foundation
- ✅ Complete YAML configuration files
- ✅ Remove hardcoded patterns from chat_search.py  
- ✅ Implement configuration loading mechanisms

### Week 2: Core Logic Implementation
- 🔄 LLM-based intent detection integration
- 🔄 Complex query analysis pipeline
- 🔄 Dynamic search strategy selection

### Week 3: Testing & Refinement  
- 🔄 Test with representative query samples
- 🔄 Tune thresholds and weights based on results
- 🔄 Validate Korean language support

### Week 4: Production Deployment
- 🔄 A/B testing with existing system
- 🔄 Monitor performance metrics
- 🔄 Gradual rollout with fallback capability

## 🛡️ Risk Mitigation

### Technical Risks:
- **LLM Dependency**: Fallback patterns for offline operation
- **Performance Impact**: Caching and parallel processing
- **Configuration Errors**: Validation and testing frameworks

### Business Risks:  
- **User Experience**: Gradual rollout with A/B testing
- **Search Quality**: Continuous monitoring and adjustment
- **Backward Compatibility**: Fallback to current system if needed

## 📝 Next Steps

1. **Complete YAML Integration**: Remove remaining hardcoded patterns
2. **Implement LLM Integration**: Connect to existing LLM infrastructure  
3. **Testing Framework**: Create comprehensive test suite
4. **Performance Optimization**: Ensure response time targets met
5. **Documentation**: Update user guides and API documentation

This implementation follows CLAUDE.md principles of YAML-managed prompts and systematic, evidence-based improvements to dramatically enhance RAG search quality.