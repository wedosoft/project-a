# 🚀 복잡한 조건 검색을 위한 최적 VectorDB 저장 구조 설계 워크플로우

## 📋 Executive Summary

사용자가 채팅을 통해 복잡한 조건의 문서를 찾을 때 효과적으로 처리할 수 있는 Qdrant 기반 최적 저장 구조를 설계합니다. 자연어 쿼리를 구조화된 필터로 변환하고, 다차원 검색을 지원하는 고성능 시스템을 구축합니다.

## 🎯 요구사항 분석

### 복잡한 조건의 정의
1. **다중 필터링 조합**
   - 시간 범위: "지난 주에 생성된 티켓"
   - 카테고리/태그: "결제 관련이면서 환불 태그가 있는"
   - 상태/우선순위: "긴급하고 미해결된"
   - 사용자/담당자: "김철수가 담당하는"

2. **의미 기반 + 메타데이터 혼합**
   - "결제 오류와 유사하면서 최근 일주일 내 해결된 티켓"
   - "고객 만족도가 낮은 환불 관련 문서"

3. **계층적 조건**
   - "VIP 고객의 긴급 티켓 중 24시간 이상 미응답"

## 🏗️ 최적화된 VectorDB 스키마 설계

### 1. 계층적 Payload 구조
```python
{
    "id": "ticket_123",
    "tenant_id": "company_456",
    
    # 핵심 메타데이터 (인덱싱됨)
    "core": {
        "doc_type": "ticket",  # ticket/article/kb
        "platform": "freshdesk",
        "created_at": 1704067200,  # Unix timestamp
        "updated_at": 1704153600,
        "status": "open",  # open/pending/resolved/closed
        "priority": 3,  # 1:low, 2:medium, 3:high, 4:urgent
    },
    
    # 분류 정보 (인덱싱됨)
    "classification": {
        "category": "billing",
        "subcategory": "refund",
        "tags": ["payment", "refund", "urgent"],
        "topics": ["payment_error", "refund_request"]
    },
    
    # 관계 정보
    "relations": {
        "customer_id": "cust_789",
        "customer_tier": "vip",  # vip/premium/standard
        "agent_id": "agent_012",
        "team": "support_team_a"
    },
    
    # 메트릭 (범위 검색용)
    "metrics": {
        "response_time_hours": 2.5,
        "resolution_time_hours": 48,
        "interaction_count": 5,
        "satisfaction_score": 4.2,
        "sentiment_score": 0.8  # -1 to 1
    },
    
    # 콘텐츠 정보
    "content": {
        "title": "결제 오류 발생",
        "language": "ko",
        "word_count": 250,
        "has_attachments": true,
        "attachment_types": ["pdf", "image"]
    },
    
    # 검색 증강 정보
    "search_hints": {
        "keywords": ["결제", "오류", "환불"],
        "entities": ["Visa", "2024-01-01"],
        "intent": "refund_request"
    }
}
```

### 2. 다중 벡터 구조 (Named Vectors)
```python
{
    "vectors": {
        "content": [...],  # 본문 임베딩 (dense)
        "title": [...],    # 제목 임베딩 (dense)
        "keywords": {...}  # 키워드 임베딩 (sparse)
    }
}
```

### 3. 인덱싱 전략
```python
# Qdrant 컬렉션 생성 시 payload 인덱싱
indexes = [
    {"field": "core.created_at", "type": "integer"},
    {"field": "core.status", "type": "keyword"},
    {"field": "core.priority", "type": "integer"},
    {"field": "classification.category", "type": "keyword"},
    {"field": "classification.tags", "type": "keyword[]"},
    {"field": "relations.customer_tier", "type": "keyword"},
    {"field": "metrics.satisfaction_score", "type": "float"},
    {"field": "metrics.response_time_hours", "type": "float"}
]
```

## 📊 구현 워크플로우

### Phase 1: 기반 구조 구축 (Week 1)

#### Task 1.1: 스키마 정의 및 마이그레이션
**담당**: Backend Developer  
**예상 시간**: 16시간  
**MCP Context**: Qdrant collection 설정, payload 구조 설계

```python
# backend/core/database/schemas/vector_schema.py
from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime

class CoreMetadata(BaseModel):
    doc_type: str
    platform: str
    created_at: datetime
    updated_at: datetime
    status: str
    priority: int

class Classification(BaseModel):
    category: str
    subcategory: Optional[str]
    tags: List[str]
    topics: List[str]

class VectorDocument(BaseModel):
    id: str
    tenant_id: str
    core: CoreMetadata
    classification: Classification
    relations: Dict[str, Any]
    metrics: Dict[str, float]
    content: Dict[str, Any]
    search_hints: Dict[str, List[str]]
```

#### Task 1.2: Qdrant 컬렉션 최적화
**담당**: Backend Developer  
**예상 시간**: 12시간

```python
# backend/core/database/qdrant_optimizer.py
from qdrant_client import QdrantClient
from qdrant_client.models import (
    VectorParams, Distance, PayloadIndexParams,
    PayloadSchemaType, TextIndexParams
)

class QdrantOptimizer:
    def create_optimized_collection(self):
        self.client.create_collection(
            collection_name="documents_v2",
            vectors_config={
                "content": VectorParams(size=3072, distance=Distance.COSINE),
                "title": VectorParams(size=3072, distance=Distance.COSINE)
            },
            sparse_vectors_config={
                "keywords": SparseVectorParams()
            }
        )
        
        # Payload 인덱싱
        self.create_payload_indexes()
    
    def create_payload_indexes(self):
        indexes = [
            ("core.created_at", PayloadSchemaType.INTEGER),
            ("core.status", PayloadSchemaType.KEYWORD),
            ("core.priority", PayloadSchemaType.INTEGER),
            ("classification.category", PayloadSchemaType.KEYWORD),
            ("classification.tags", PayloadSchemaType.KEYWORD),
            ("relations.customer_tier", PayloadSchemaType.KEYWORD),
            ("metrics.satisfaction_score", PayloadSchemaType.FLOAT)
        ]
        
        for field_path, schema_type in indexes:
            self.client.create_payload_index(
                collection_name="documents_v2",
                field_name=field_path,
                field_schema=schema_type
            )
```

### Phase 2: 고급 검색 파이프라인 (Week 2)

#### Task 2.1: 복합 필터 빌더 구현
**담당**: Backend Developer  
**예상 시간**: 20시간

```python
# backend/core/search/filter_builder.py
from qdrant_client.models import Filter, FieldCondition, Range, MatchAny
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

class AdvancedFilterBuilder:
    """복잡한 조건을 Qdrant Filter로 변환"""
    
    def build_filter(self, conditions: Dict[str, Any]) -> Filter:
        must_conditions = []
        should_conditions = []
        must_not_conditions = []
        
        # 시간 범위 필터
        if "date_range" in conditions:
            must_conditions.append(self._build_date_filter(conditions["date_range"]))
        
        # 상태 필터
        if "status" in conditions:
            must_conditions.append(
                FieldCondition(
                    key="core.status",
                    match=MatchAny(any=conditions["status"])
                )
            )
        
        # 우선순위 필터
        if "priority" in conditions:
            must_conditions.append(
                FieldCondition(
                    key="core.priority",
                    range=Range(gte=conditions["priority"]["min"])
                )
            )
        
        # 카테고리 필터
        if "categories" in conditions:
            must_conditions.append(
                FieldCondition(
                    key="classification.category",
                    match=MatchAny(any=conditions["categories"])
                )
            )
        
        # 태그 필터 (ANY match)
        if "tags" in conditions:
            should_conditions.append(
                FieldCondition(
                    key="classification.tags",
                    match=MatchAny(any=conditions["tags"])
                )
            )
        
        # 감정 점수 필터
        if "sentiment_range" in conditions:
            must_conditions.append(
                FieldCondition(
                    key="metrics.sentiment_score",
                    range=Range(
                        gte=conditions["sentiment_range"]["min"],
                        lte=conditions["sentiment_range"]["max"]
                    )
                )
            )
        
        return Filter(
            must=must_conditions if must_conditions else None,
            should=should_conditions if should_conditions else None,
            must_not=must_not_conditions if must_not_conditions else None
        )
    
    def _build_date_filter(self, date_range: Dict) -> FieldCondition:
        """날짜 범위 필터 생성"""
        if "relative" in date_range:
            # "지난 7일" 같은 상대적 날짜
            days = date_range["relative"]["days"]
            start_timestamp = int((datetime.now() - timedelta(days=days)).timestamp())
            return FieldCondition(
                key="core.created_at",
                range=Range(gte=start_timestamp)
            )
        else:
            # 절대 날짜 범위
            return FieldCondition(
                key="core.created_at",
                range=Range(
                    gte=int(date_range["start"].timestamp()),
                    lte=int(date_range["end"].timestamp())
                )
            )
```

#### Task 2.2: 하이브리드 검색 엔진
**담당**: Backend Developer  
**예상 시간**: 24시간

```python
# backend/core/search/hybrid_search_engine.py
from typing import List, Dict, Any, Optional
import numpy as np

class HybridSearchEngine:
    """의미 검색 + 필터링 + 키워드 매칭 통합"""
    
    async def search(
        self,
        query: str,
        filters: Dict[str, Any],
        search_config: Dict[str, Any]
    ) -> List[Dict]:
        
        # 1. 쿼리 임베딩 생성
        query_vectors = {
            "content": await self.get_embedding(query, model="content"),
            "title": await self.get_embedding(query, model="title")
        }
        
        # 2. 키워드 추출 (sparse vector용)
        keywords = self.extract_keywords(query)
        sparse_vector = self.create_sparse_vector(keywords)
        
        # 3. 필터 구성
        qdrant_filter = self.filter_builder.build_filter(filters)
        
        # 4. 멀티 스테이지 검색
        results = []
        
        # Stage 1: Dense vector 검색 (의미 기반)
        semantic_results = await self.client.search(
            collection_name="documents_v2",
            query_vector=("content", query_vectors["content"]),
            query_filter=qdrant_filter,
            limit=search_config.get("semantic_limit", 50),
            with_payload=True
        )
        
        # Stage 2: Sparse vector 검색 (키워드 기반)
        if sparse_vector:
            keyword_results = await self.client.search(
                collection_name="documents_v2",
                query_vector=("keywords", sparse_vector),
                query_filter=qdrant_filter,
                limit=search_config.get("keyword_limit", 30),
                with_payload=True
            )
        
        # Stage 3: 결과 융합 및 리랭킹
        fused_results = self.fuse_results(
            semantic_results,
            keyword_results,
            weights=search_config.get("fusion_weights", {"semantic": 0.7, "keyword": 0.3})
        )
        
        # Stage 4: 후처리 및 메타데이터 증강
        enriched_results = self.enrich_results(fused_results)
        
        return enriched_results
    
    def fuse_results(
        self,
        semantic_results: List,
        keyword_results: List,
        weights: Dict[str, float]
    ) -> List[Dict]:
        """Reciprocal Rank Fusion"""
        scores = {}
        
        # Semantic 점수 계산
        for i, result in enumerate(semantic_results):
            doc_id = result.id
            scores[doc_id] = weights["semantic"] / (i + 1)
        
        # Keyword 점수 추가
        for i, result in enumerate(keyword_results):
            doc_id = result.id
            if doc_id in scores:
                scores[doc_id] += weights["keyword"] / (i + 1)
            else:
                scores[doc_id] = weights["keyword"] / (i + 1)
        
        # 점수별 정렬
        sorted_docs = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        return [self.get_document(doc_id) for doc_id, _ in sorted_docs]
```

### Phase 3: 자연어 쿼리 처리 (Week 3)

#### Task 3.1: NLU 파서 구현
**담당**: Backend Developer + AI Engineer  
**예상 시간**: 24시간

```python
# backend/core/nlp/query_parser.py
from typing import Dict, Any, List
import re
from datetime import datetime, timedelta

class NaturalLanguageQueryParser:
    """자연어를 구조화된 검색 조건으로 변환"""
    
    def __init__(self):
        self.time_patterns = {
            r"지난\s*(\d+)일": lambda x: {"relative": {"days": int(x.group(1))}},
            r"오늘": lambda x: {"relative": {"days": 0}},
            r"어제": lambda x: {"relative": {"days": 1}},
            r"이번\s*주": lambda x: {"relative": {"days": 7}},
            r"지난\s*주": lambda x: {"relative": {"days": 7, "offset": 7}},
            r"이번\s*달": lambda x: {"relative": {"days": 30}},
        }
        
        self.priority_patterns = {
            r"긴급": {"min": 4, "max": 4},
            r"높은\s*우선순위": {"min": 3, "max": 4},
            r"중요": {"min": 3, "max": 4},
            r"낮은\s*우선순위": {"min": 1, "max": 2}
        }
        
        self.status_keywords = {
            "미해결": ["open", "pending"],
            "해결된": ["resolved", "closed"],
            "진행중": ["pending"],
            "대기중": ["pending"],
            "완료": ["closed"]
        }
        
        self.category_mappings = {
            "결제": "billing",
            "환불": "refund",
            "기술": "technical",
            "계정": "account",
            "배송": "shipping"
        }
    
    async def parse(self, query: str) -> Dict[str, Any]:
        """자연어 쿼리를 구조화된 조건으로 파싱"""
        
        conditions = {
            "original_query": query,
            "filters": {},
            "search_text": query  # 필터 키워드 제거 후 남은 텍스트
        }
        
        # 1. 시간 조건 추출
        for pattern, extractor in self.time_patterns.items():
            match = re.search(pattern, query)
            if match:
                conditions["filters"]["date_range"] = extractor(match)
                query = re.sub(pattern, "", query)
        
        # 2. 우선순위 추출
        for pattern, priority_range in self.priority_patterns.items():
            if re.search(pattern, query):
                conditions["filters"]["priority"] = priority_range
                query = re.sub(pattern, "", query)
        
        # 3. 상태 추출
        for keyword, statuses in self.status_keywords.items():
            if keyword in query:
                conditions["filters"]["status"] = statuses
                query = query.replace(keyword, "")
        
        # 4. 카테고리 추출
        categories = []
        for ko_term, en_term in self.category_mappings.items():
            if ko_term in query:
                categories.append(en_term)
                query = query.replace(ko_term, "")
        
        if categories:
            conditions["filters"]["categories"] = categories
        
        # 5. 고객 등급 추출
        if "VIP" in query or "vip" in query:
            conditions["filters"]["customer_tier"] = ["vip"]
            query = re.sub(r"[Vv][Ii][Pp]", "", query)
        
        # 6. 감정 분석 조건
        if "불만" in query or "화난" in query:
            conditions["filters"]["sentiment_range"] = {"min": -1.0, "max": -0.3}
        elif "만족" in query or "긍정" in query:
            conditions["filters"]["sentiment_range"] = {"min": 0.3, "max": 1.0}
        
        # 7. LLM 기반 의도 분류 (선택사항)
        if self.use_llm_parsing:
            llm_conditions = await self.llm_parse(query)
            conditions["filters"].update(llm_conditions)
        
        # 8. 정제된 검색 텍스트
        conditions["search_text"] = query.strip()
        
        return conditions
    
    async def llm_parse(self, query: str) -> Dict[str, Any]:
        """LLM을 사용한 고급 쿼리 파싱"""
        prompt = f"""
        다음 자연어 쿼리를 구조화된 검색 조건으로 변환하세요:
        쿼리: "{query}"
        
        추출할 정보:
        - 시간 범위 (date_range)
        - 카테고리 (categories)
        - 태그 (tags)
        - 우선순위 (priority)
        - 상태 (status)
        - 감정 (sentiment)
        - 의도 (intent)
        
        JSON 형식으로 반환:
        """
        
        # LLM 호출 및 파싱
        response = await self.llm_client.generate(prompt)
        return self.parse_llm_response(response)
```

#### Task 3.2: 쿼리 최적화기
**담당**: Backend Developer  
**예상 시간**: 16시간

```python
# backend/core/search/query_optimizer.py
class QueryOptimizer:
    """검색 쿼리 최적화 및 캐싱"""
    
    def optimize_query(self, parsed_query: Dict) -> Dict:
        """쿼리 최적화"""
        optimized = parsed_query.copy()
        
        # 1. 필터 순서 최적화 (선택도가 높은 필터 우선)
        if "filters" in optimized:
            optimized["filters"] = self.reorder_filters(optimized["filters"])
        
        # 2. 검색 전략 결정
        optimized["search_strategy"] = self.determine_strategy(optimized)
        
        # 3. 캐시 키 생성
        optimized["cache_key"] = self.generate_cache_key(optimized)
        
        # 4. 검색 파라미터 최적화
        optimized["search_params"] = {
            "semantic_limit": self.calculate_limit(optimized, "semantic"),
            "keyword_limit": self.calculate_limit(optimized, "keyword"),
            "fusion_weights": self.calculate_fusion_weights(optimized)
        }
        
        return optimized
    
    def determine_strategy(self, query: Dict) -> str:
        """최적 검색 전략 결정"""
        filters = query.get("filters", {})
        
        # 필터가 많으면 필터 우선 전략
        if len(filters) > 3:
            return "filter_first"
        
        # 시간 범위가 좁으면 시간 우선 전략
        if "date_range" in filters:
            if filters["date_range"].get("relative", {}).get("days", 30) < 7:
                return "recent_first"
        
        # 기본: 하이브리드 전략
        return "hybrid"
```

### Phase 4: 성능 최적화 (Week 4)

#### Task 4.1: 인덱싱 최적화
**담당**: Backend Developer  
**예상 시간**: 16시간

```python
# backend/core/database/index_optimizer.py
class IndexOptimizer:
    """Qdrant 인덱스 최적화"""
    
    async def optimize_collection(self):
        # 1. HNSW 파라미터 튜닝
        await self.client.update_collection(
            collection_name="documents_v2",
            optimizer_config={
                "indexing_threshold": 20000,
                "flush_interval_sec": 5,
                "max_optimization_threads": 4
            },
            hnsw_config={
                "m": 16,  # 연결 수
                "ef_construct": 200,  # 구축 시 탐색 깊이
                "full_scan_threshold": 10000
            }
        )
        
        # 2. Quantization 설정
        await self.client.update_collection(
            collection_name="documents_v2",
            quantization_config={
                "scalar": {
                    "type": "int8",
                    "quantile": 0.99,
                    "always_ram": True
                }
            }
        )
```

#### Task 4.2: 캐싱 레이어
**담당**: Backend Developer  
**예상 시간**: 12시간

```python
# backend/core/cache/search_cache.py
from typing import Optional, Dict, Any
import hashlib
import json
import redis.asyncio as redis

class SearchCache:
    """검색 결과 캐싱"""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.ttl = 3600  # 1시간
    
    async def get(self, query: Dict) -> Optional[Dict]:
        """캐시된 결과 조회"""
        cache_key = self.generate_key(query)
        cached = await self.redis.get(cache_key)
        
        if cached:
            return json.loads(cached)
        return None
    
    async def set(self, query: Dict, results: Dict):
        """결과 캐싱"""
        cache_key = self.generate_key(query)
        await self.redis.setex(
            cache_key,
            self.ttl,
            json.dumps(results)
        )
    
    def generate_key(self, query: Dict) -> str:
        """캐시 키 생성"""
        # 쿼리를 정규화하여 일관된 키 생성
        normalized = {
            "text": query.get("search_text", ""),
            "filters": sorted(json.dumps(query.get("filters", {})))
        }
        
        key_string = json.dumps(normalized, sort_keys=True)
        return f"search:v2:{hashlib.md5(key_string.encode()).hexdigest()}"
```

### Phase 5: 통합 및 테스트 (Week 5)

#### Task 5.1: API 엔드포인트 구현
**담당**: Backend Developer  
**예상 시간**: 16시간

```python
# backend/api/routes/advanced_search.py
from fastapi import APIRouter, Depends, Query
from typing import Optional, Dict, Any

router = APIRouter(prefix="/api/v2/search")

@router.post("/natural")
async def natural_language_search(
    query: str,
    tenant_id: str,
    options: Optional[Dict] = None
):
    """자연어 검색 엔드포인트"""
    
    # 1. 쿼리 파싱
    parsed = await query_parser.parse(query)
    
    # 2. 쿼리 최적화
    optimized = query_optimizer.optimize_query(parsed)
    
    # 3. 캐시 확인
    cached = await search_cache.get(optimized)
    if cached:
        return cached
    
    # 4. 검색 실행
    results = await hybrid_search_engine.search(
        query=optimized["search_text"],
        filters=optimized["filters"],
        search_config=optimized["search_params"]
    )
    
    # 5. 결과 캐싱
    await search_cache.set(optimized, results)
    
    # 6. 응답 포맷팅
    return {
        "query": query,
        "parsed_conditions": parsed,
        "results": results,
        "total": len(results),
        "search_strategy": optimized["search_strategy"]
    }

@router.post("/advanced")
async def advanced_search(
    conditions: Dict[str, Any],
    tenant_id: str
):
    """구조화된 고급 검색"""
    
    # 필터 빌더로 직접 검색
    filter_obj = filter_builder.build_filter(conditions)
    
    results = await client.search(
        collection_name="documents_v2",
        query_filter=filter_obj,
        limit=conditions.get("limit", 100)
    )
    
    return {
        "conditions": conditions,
        "results": results,
        "total": len(results)
    }
```

#### Task 5.2: 테스트 스위트
**담당**: QA Engineer  
**예상 시간**: 20시간

```python
# tests/test_advanced_search.py
import pytest
from datetime import datetime, timedelta

class TestAdvancedSearch:
    
    @pytest.mark.asyncio
    async def test_natural_language_parsing(self):
        """자연어 파싱 테스트"""
        test_cases = [
            {
                "query": "지난 7일간 긴급한 결제 문제",
                "expected_filters": {
                    "date_range": {"relative": {"days": 7}},
                    "priority": {"min": 4, "max": 4},
                    "categories": ["billing"]
                }
            },
            {
                "query": "VIP 고객의 미해결 환불 요청",
                "expected_filters": {
                    "customer_tier": ["vip"],
                    "status": ["open", "pending"],
                    "categories": ["refund"]
                }
            }
        ]
        
        for case in test_cases:
            result = await query_parser.parse(case["query"])
            assert result["filters"] == case["expected_filters"]
    
    @pytest.mark.asyncio
    async def test_complex_filter_building(self):
        """복합 필터 생성 테스트"""
        conditions = {
            "date_range": {"relative": {"days": 30}},
            "status": ["open", "pending"],
            "priority": {"min": 3},
            "categories": ["billing", "refund"],
            "tags": ["urgent", "vip"],
            "sentiment_range": {"min": -1.0, "max": -0.5}
        }
        
        filter_obj = filter_builder.build_filter(conditions)
        
        assert len(filter_obj.must) >= 4
        assert len(filter_obj.should) >= 1
    
    @pytest.mark.asyncio
    async def test_search_performance(self):
        """검색 성능 테스트"""
        import time
        
        query = "최근 일주일 내 긴급한 기술 문제"
        
        start = time.time()
        results = await natural_language_search(
            query=query,
            tenant_id="test_tenant"
        )
        elapsed = time.time() - start
        
        assert elapsed < 1.0  # 1초 이내 응답
        assert len(results["results"]) > 0
```

## 📊 검증 메트릭

### 성능 목표
- **검색 지연시간**: < 500ms (P95)
- **쿼리 파싱 시간**: < 50ms
- **캐시 히트율**: > 60%
- **인덱스 크기**: < 원본 데이터의 150%

### 정확도 목표
- **자연어 파싱 정확도**: > 90%
- **검색 관련성 (nDCG)**: > 0.85
- **필터 정확도**: 100%

## 🚀 배포 전략

### Stage 1: 개발 환경 (Week 1-4)
- 새 컬렉션 생성 및 테스트
- 기존 데이터 마이그레이션

### Stage 2: 스테이징 환경 (Week 5)
- A/B 테스트 설정
- 성능 벤치마킹

### Stage 3: 프로덕션 배포 (Week 6)
- 점진적 롤아웃 (10% → 50% → 100%)
- 실시간 모니터링

## 🎯 성공 기준

### 기술적 성공 지표
- ✅ 복잡한 조건 처리 가능
- ✅ 자연어 쿼리 지원
- ✅ 500ms 이내 응답
- ✅ 90% 이상 파싱 정확도

### 비즈니스 성공 지표
- 📈 검색 만족도 30% 향상
- 📈 평균 검색 시간 50% 단축
- 📈 지원 티켓 해결 시간 20% 감소

## 📚 참고 자료

### Qdrant 문서
- [Filtering Documentation](https://qdrant.tech/documentation/concepts/filtering/)
- [Payload Indexing](https://qdrant.tech/documentation/concepts/indexing/)
- [Hybrid Search](https://qdrant.tech/documentation/tutorials/hybrid-search/)

### 구현 예제
- [Natural Language Search](https://github.com/qdrant/examples/nlp-search)
- [Multi-Stage Retrieval](https://github.com/qdrant/examples/multi-stage)

---

*Generated with Qdrant Optimization Expertise + Sequential Analysis*  
*최종 업데이트: 2025년 1월*