---
applyTo: "**"
---

# 🔍 벡터 저장 & 검색 최적화 지침서

_AI 참조 최적화 버전 - 멀티테넌트 벡터 데이터베이스 전략_

## 🎯 벡터 처리 목표

**효율적인 멀티테넌트 벡터 검색 시스템 구축**

- **단일 컬렉션 전략**: Qdrant `documents` 컬렉션으로 모든 테넌트 데이터 통합
- **완벽한 데이터 격리**: company_id + platform 필터링으로 테넌트 분리
- **비용 최적화**: 요약 텍스트만 임베딩, 원본은 메타데이터로 저장
- **검색 성능**: 복합 인덱스 및 캐싱으로 응답 속도 향상

---

## 🚀 **TL;DR - 핵심 벡터 처리 요약**

### 💡 **즉시 참조용 핵심 포인트**

**벡터 처리 흐름**:
```
LLM 요약 완료 → 임베딩 생성 → 메타데이터 구성 → Qdrant 저장 → 인덱스 최적화 → 검색 준비
```

**단일 컬렉션 전략**:
- **컬렉션명**: `documents` (모든 테넌트 공유)
- **벡터 크기**: 1536 (OpenAI text-embedding-3-small)
- **거리 측정**: COSINE (코사인 유사도)
- **격리 방식**: payload 필터링 (company_id + platform)

**멀티테넌트 필터링**:
```python
search_filter = Filter(
    must=[
        FieldCondition(key="company_id", match=MatchValue(value=company_id)),
        FieldCondition(key="platform", match=MatchValue(value=platform)),
        FieldCondition(key="data_type", match=MatchValue(value="ticket"))
    ]
)
```

**비용 최적화 전략**:
- **요약만 임베딩**: 원본 대화는 payload에만 저장
- **배치 처리**: 100개씩 묶어서 업로드
- **중복 제거**: 동일 요약 중복 임베딩 방지

### 🚨 **벡터 처리 주의사항**

- ⚠️ company_id 없는 벡터 절대 금지 → 완벽한 테넌트 격리 필수
- ⚠️ 원본 텍스트 임베딩 금지 → 요약 텍스트만 벡터화 (비용 절감)
- ⚠️ 단일 컬렉션 원칙 → 테넌트별 컬렉션 생성 금지

---

## 💾 **Qdrant 저장 패턴**

### 🏗️ **컬렉션 설정 및 초기화**

```python
from qdrant_client import QdrantClient
from qdrant_client.models import (
    VectorParams, Distance, PointStruct, Filter, 
    FieldCondition, MatchValue, CreateCollection
)

async def initialize_qdrant_collection():
    """Qdrant 컬렉션 초기화 (최초 1회만 실행)"""
    
    client = QdrantClient(
        url=os.getenv("QDRANT_URL"),
        api_key=os.getenv("QDRANT_API_KEY")
    )
    
    collection_name = "documents"
    
    try:
        # 컬렉션 생성
        await client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=1536,  # OpenAI text-embedding-3-small
                distance=Distance.COSINE
            ),
            # 성능 최적화 설정
            optimizers_config={
                "default_segment_number": 2,
                "max_segment_size": 20000,
                "memmap_threshold": 20000,
                "indexing_threshold": 10000,
                "flush_interval_sec": 5
            },
            # HNSW 인덱스 최적화
            hnsw_config={
                "m": 16,
                "ef_construct": 100,
                "full_scan_threshold": 10000
            }
        )
        
        logger.info(f"Created Qdrant collection: {collection_name}")
        
        # 인덱스 생성 (검색 성능 향상)
        await create_payload_indexes(client, collection_name)
        
    except Exception as e:
        if "already exists" in str(e).lower():
            logger.info(f"Collection {collection_name} already exists")
        else:
            raise e

async def create_payload_indexes(client: QdrantClient, collection_name: str):
    """페이로드 필드 인덱스 생성"""
    
    # 멀티테넌트 필터링용 인덱스
    index_fields = [
        "company_id",      # 테넌트 식별
        "platform",        # 플랫폼 구분
        "data_type",       # 데이터 타입 구분
        "tenant_key",      # 복합 키
        "status",          # 티켓 상태
        "priority",        # 우선순위
        "tags"             # 태그 배열
    ]
    
    for field in index_fields:
        try:
            await client.create_payload_index(
                collection_name=collection_name,
                field_name=field,
                field_schema="keyword"  # 정확한 매칭용
            )
            logger.info(f"Created index for field: {field}")
        except Exception as e:
            logger.warning(f"Failed to create index for {field}: {e}")
```

### 📦 **벡터 저장 핵심 패턴**

```python
async def store_document_embeddings(
    company_id: str,
    platform: str,  # 'freshdesk', 'zendesk', 'servicenow'
    documents: List[Dict],  # LLM 요약 완료된 문서들
    data_type: str = "ticket"  # 'ticket' or 'kb'
) -> Dict[str, Any]:
    """
    멀티플랫폼/멀티테넌트 벡터 저장 (단일 컬렉션 사용)
    """
    client = QdrantClient(
        url=os.getenv("QDRANT_URL"),
        api_key=os.getenv("QDRANT_API_KEY")
    )
    
    collection_name = "documents"
    
    # 1. 임베딩 생성 (요약 텍스트만)
    texts_to_embed = []
    for doc in documents:
        # 구조화된 요약을 검색용 텍스트로 변환
        summary = doc.get('summary', {})
        search_text = f"""
        문제: {summary.get('problem', '')}
        원인: {summary.get('cause', '')}
        해결방법: {summary.get('solution', '')}
        결과: {summary.get('result', '')}
        태그: {', '.join(summary.get('tags', []))}
        """.strip()
        texts_to_embed.append(search_text)
    
    # 2. 배치 임베딩 생성
    embeddings = await generate_embeddings_batch(texts_to_embed)
    
    # 3. 벡터 포인트 생성
    points = []
    for i, doc in enumerate(documents):
        # 고유 ID 생성
        point_id = f"{company_id}_{platform}_{doc.get('ticket_id', uuid.uuid4())}"
        
        # 복합 검색 키 생성
        tenant_key = f"{company_id}_{platform}_{data_type}"
        
        point = PointStruct(
            id=point_id,
            vector=embeddings[i],
            payload={
                # === 멀티테넌트 필수 필드 ===
                "company_id": company_id,
                "platform": platform,
                "data_type": data_type,
                "tenant_key": tenant_key,
                
                # === 검색 최적화 필드 ===
                "item_id": doc.get('ticket_id') or doc.get('kb_id'),
                "title": doc.get('subject') or doc.get('title', ''),
                "status": doc.get('status', '').lower(),
                "priority": doc.get('priority', '').lower(),
                "tags": doc.get('summary', {}).get('tags', []),
                
                # === 구조화된 요약 (검색용) ===
                "summary": doc.get('summary', {}),
                "search_text": texts_to_embed[i],
                
                # === 메타데이터 ===
                "created_at": doc.get('created_at'),
                "updated_at": doc.get('updated_at'),
                "processed_at": datetime.utcnow().isoformat(),
                
                # === 원본 데이터 (메타데이터로만 저장) ===
                "original_data": {
                    "ticket": doc.get('original_data', {}),
                    "full_conversation": doc.get('full_conversation', ''),
                    "description": doc.get('description', ''),
                    "attachments_info": doc.get('attachments_info', [])
                }
            }
        )
        points.append(point)
    
    # 4. 배치 업로드 (성능 최적화)
    batch_size = 100
    upload_results = []
    
    for i in range(0, len(points), batch_size):
        batch = points[i:i + batch_size]
        
        try:
            result = await client.upsert(
                collection_name=collection_name,
                points=batch,
                wait=True  # 업로드 완료 대기
            )
            
            upload_results.append({
                'batch_index': i // batch_size,
                'batch_size': len(batch),
                'status': 'success',
                'operation_id': result.operation_id if hasattr(result, 'operation_id') else None
            })
            
            logger.info(f"Uploaded batch {i//batch_size + 1}/{len(points)//batch_size + 1} for {company_id}/{platform}")
            
        except Exception as e:
            logger.error(f"Failed to upload batch {i//batch_size + 1}: {e}")
            upload_results.append({
                'batch_index': i // batch_size,
                'batch_size': len(batch),
                'status': 'failed',
                'error': str(e)
            })
    
    # 5. 업로드 결과 반환
    total_uploaded = sum(r['batch_size'] for r in upload_results if r['status'] == 'success')
    total_failed = sum(r['batch_size'] for r in upload_results if r['status'] == 'failed')
    
    return {
        'company_id': company_id,
        'platform': platform,
        'data_type': data_type,
        'total_documents': len(documents),
        'uploaded': total_uploaded,
        'failed': total_failed,
        'batch_results': upload_results,
        'collection_name': collection_name
    }
```

---

## 🔍 **벡터 검색 패턴**

### 🎯 **멀티테넌트 검색 최적화**

```python
async def search_similar_documents(
    company_id: str,
    platform: str,
    query_text: str,
    data_type: str = "ticket",
    limit: int = 10,
    score_threshold: float = 0.7,
    filters: Dict = None
) -> List[Dict]:
    """
    테넌트/플랫폼별 격리된 벡터 검색
    """
    client = QdrantClient(
        url=os.getenv("QDRANT_URL"),
        api_key=os.getenv("QDRANT_API_KEY")
    )
    
    # 1. 쿼리 임베딩 생성
    query_embedding = await generate_embedding(query_text)
    
    # 2. 멀티테넌트 필터 설정
    search_filter = Filter(
        must=[
            FieldCondition(
                key="company_id",
                match=MatchValue(value=company_id)
            ),
            FieldCondition(
                key="platform",
                match=MatchValue(value=platform)
            ),
            FieldCondition(
                key="data_type",
                match=MatchValue(value=data_type)
            )
        ]
    )
    
    # 3. 추가 필터 적용
    if filters:
        for field, value in filters.items():
            if isinstance(value, list):
                # 배열 필드 (tags 등)
                search_filter.must.append(
                    FieldCondition(
                        key=field,
                        match=MatchAny(any=value)
                    )
                )
            else:
                # 단일 값 필드
                search_filter.must.append(
                    FieldCondition(
                        key=field,
                        match=MatchValue(value=value)
                    )
                )
    
    # 4. 벡터 검색 실행
    try:
        search_result = await client.search(
            collection_name="documents",
            query_vector=query_embedding,
            query_filter=search_filter,
            limit=limit,
            score_threshold=score_threshold,
            with_payload=True,
            with_vectors=False  # 벡터는 반환하지 않음 (용량 절약)
        )
        
        # 5. 결과 후처리
        results = []
        for point in search_result:
            result = {
                'id': point.id,
                'score': point.score,
                'item_id': point.payload.get('item_id'),
                'title': point.payload.get('title'),
                'summary': point.payload.get('summary', {}),
                'status': point.payload.get('status'),
                'priority': point.payload.get('priority'),
                'tags': point.payload.get('tags', []),
                'created_at': point.payload.get('created_at'),
                'platform': point.payload.get('platform'),
                # 원본 데이터는 필요시에만 포함
                'has_original_data': bool(point.payload.get('original_data'))
            }
            results.append(result)
        
        logger.info(f"Vector search completed: {len(results)} results for {company_id}/{platform}")
        return results
        
    except Exception as e:
        logger.error(f"Vector search failed for {company_id}/{platform}: {e}")
        return []

async def get_document_details(
    company_id: str,
    platform: str,
    document_id: str
) -> Dict:
    """특정 문서의 상세 정보 조회 (원본 데이터 포함)"""
    
    client = QdrantClient(
        url=os.getenv("QDRANT_URL"),
        api_key=os.getenv("QDRANT_API_KEY")
    )
    
    # 보안 검증: company_id + platform 일치 확인
    search_filter = Filter(
        must=[
            FieldCondition(key="company_id", match=MatchValue(value=company_id)),
            FieldCondition(key="platform", match=MatchValue(value=platform))
        ]
    )
    
    try:
        result = await client.retrieve(
            collection_name="documents",
            ids=[document_id],
            with_payload=True,
            with_vectors=False
        )
        
        if not result or not result[0].payload:
            return None
        
        point = result[0]
        
        # 테넌트 권한 검증
        if (point.payload.get('company_id') != company_id or 
            point.payload.get('platform') != platform):
            logger.warning(f"Unauthorized access attempt: {company_id}/{platform} to {document_id}")
            return None
        
        return {
            'id': point.id,
            'item_id': point.payload.get('item_id'),
            'title': point.payload.get('title'),
            'summary': point.payload.get('summary', {}),
            'status': point.payload.get('status'),
            'priority': point.payload.get('priority'),
            'tags': point.payload.get('tags', []),
            'created_at': point.payload.get('created_at'),
            'updated_at': point.payload.get('updated_at'),
            'processed_at': point.payload.get('processed_at'),
            'platform': point.payload.get('platform'),
            'original_data': point.payload.get('original_data', {})
        }
        
    except Exception as e:
        logger.error(f"Failed to get document details {document_id}: {e}")
        return None
```

### 🔄 **하이브리드 검색 패턴**

```python
async def hybrid_search(
    company_id: str,
    platform: str,
    query_text: str,
    keyword_filters: Dict = None,
    limit: int = 10
) -> List[Dict]:
    """벡터 검색 + 키워드 필터링 조합"""
    
    # 1. 기본 벡터 검색
    vector_results = await search_similar_documents(
        company_id=company_id,
        platform=platform,
        query_text=query_text,
        limit=limit * 2,  # 더 많은 결과 가져와서 후처리
        score_threshold=0.5  # 낮은 임계값으로 더 많은 후보 확보
    )
    
    # 2. 키워드 기반 필터링
    if keyword_filters:
        filtered_results = []
        
        for result in vector_results:
            include = True
            
            # 상태 필터
            if 'status' in keyword_filters:
                if result.get('status') not in keyword_filters['status']:
                    include = False
            
            # 우선순위 필터
            if 'priority' in keyword_filters:
                if result.get('priority') not in keyword_filters['priority']:
                    include = False
            
            # 태그 필터
            if 'tags' in keyword_filters:
                result_tags = set(result.get('tags', []))
                filter_tags = set(keyword_filters['tags'])
                if not result_tags.intersection(filter_tags):
                    include = False
            
            # 날짜 범위 필터
            if 'date_range' in keyword_filters:
                created_at = result.get('created_at')
                if created_at:
                    created_date = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    start_date = datetime.fromisoformat(keyword_filters['date_range']['start'])
                    end_date = datetime.fromisoformat(keyword_filters['date_range']['end'])
                    
                    if not (start_date <= created_date <= end_date):
                        include = False
            
            if include:
                filtered_results.append(result)
        
        vector_results = filtered_results
    
    # 3. 점수 기반 재정렬 및 제한
    final_results = sorted(vector_results, key=lambda x: x['score'], reverse=True)[:limit]
    
    return final_results

async def semantic_search_with_context(
    company_id: str,
    platform: str,
    query_text: str,
    context_window: int = 5
) -> Dict:
    """의미론적 검색 + 컨텍스트 확장"""
    
    # 1. 기본 검색 결과
    main_results = await search_similar_documents(
        company_id=company_id,
        platform=platform,
        query_text=query_text,
        limit=context_window
    )
    
    if not main_results:
        return {'main_results': [], 'related_results': []}
    
    # 2. 관련 태그 추출
    all_tags = []
    for result in main_results:
        all_tags.extend(result.get('tags', []))
    
    # 가장 빈번한 태그들
    tag_counts = {}
    for tag in all_tags:
        tag_counts[tag] = tag_counts.get(tag, 0) + 1
    
    top_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:3]
    top_tag_names = [tag[0] for tag in top_tags]
    
    # 3. 태그 기반 관련 문서 검색
    related_results = []
    if top_tag_names:
        related_results = await search_similar_documents(
            company_id=company_id,
            platform=platform,
            query_text=' '.join(top_tag_names),  # 태그를 쿼리로 사용
            limit=context_window,
            filters={'tags': top_tag_names}
        )
        
        # 중복 제거
        main_ids = {r['id'] for r in main_results}
        related_results = [r for r in related_results if r['id'] not in main_ids]
    
    return {
        'main_results': main_results,
        'related_results': related_results[:context_window],
        'context_tags': top_tag_names,
        'total_found': len(main_results) + len(related_results)
    }
```

---

## ⚡ **성능 최적화 전략**

### 📈 **검색 성능 향상**

```python
class VectorSearchOptimizer:
    def __init__(self):
        self.search_cache = {}
        self.cache_ttl = 300  # 5분 캐시
    
    async def optimized_search(
        self,
        company_id: str,
        platform: str,
        query_text: str,
        **kwargs
    ) -> List[Dict]:
        """캐싱 및 최적화가 적용된 검색"""
        
        # 1. 캐시 키 생성
        cache_key = self._generate_cache_key(company_id, platform, query_text, kwargs)
        
        # 2. 캐시 확인
        if cache_key in self.search_cache:
            cache_entry = self.search_cache[cache_key]
            if datetime.utcnow().timestamp() - cache_entry['timestamp'] < self.cache_ttl:
                logger.info(f"Cache hit for search: {cache_key[:20]}...")
                return cache_entry['results']
        
        # 3. 실제 검색 실행
        results = await search_similar_documents(
            company_id=company_id,
            platform=platform,
            query_text=query_text,
            **kwargs
        )
        
        # 4. 결과 캐싱
        self.search_cache[cache_key] = {
            'results': results,
            'timestamp': datetime.utcnow().timestamp()
        }
        
        # 5. 캐시 크기 제한 (메모리 관리)
        if len(self.search_cache) > 1000:
            # 가장 오래된 항목들 제거
            oldest_keys = sorted(
                self.search_cache.keys(),
                key=lambda k: self.search_cache[k]['timestamp']
            )[:100]
            
            for key in oldest_keys:
                del self.search_cache[key]
        
        return results
    
    def _generate_cache_key(self, company_id: str, platform: str, query_text: str, kwargs: Dict) -> str:
        """검색 매개변수 기반 캐시 키 생성"""
        key_data = {
            'company_id': company_id,
            'platform': platform,
            'query': query_text,
            **kwargs
        }
        
        key_string = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_string.encode()).hexdigest()

# 전역 최적화 인스턴스
search_optimizer = VectorSearchOptimizer()
```

### 🔄 **배치 작업 최적화**

```python
async def batch_vector_operations(
    operations: List[Dict]  # [{'type': 'upsert|delete', 'data': ...}, ...]
) -> Dict:
    """배치 벡터 작업 최적화"""
    
    client = QdrantClient(
        url=os.getenv("QDRANT_URL"),
        api_key=os.getenv("QDRANT_API_KEY")
    )
    
    collection_name = "documents"
    
    # 작업 유형별 그룹핑
    upsert_operations = []
    delete_operations = []
    
    for op in operations:
        if op['type'] == 'upsert':
            upsert_operations.extend(op['data'])
        elif op['type'] == 'delete':
            delete_operations.extend(op['data'])
    
    results = []
    
    # 1. 배치 업서트
    if upsert_operations:
        batch_size = 100
        for i in range(0, len(upsert_operations), batch_size):
            batch = upsert_operations[i:i + batch_size]
            
            try:
                result = await client.upsert(
                    collection_name=collection_name,
                    points=batch,
                    wait=True
                )
                
                results.append({
                    'operation': 'upsert',
                    'batch_index': i // batch_size,
                    'count': len(batch),
                    'status': 'success'
                })
                
            except Exception as e:
                results.append({
                    'operation': 'upsert',
                    'batch_index': i // batch_size,
                    'count': len(batch),
                    'status': 'failed',
                    'error': str(e)
                })
    
    # 2. 배치 삭제
    if delete_operations:
        try:
            await client.delete(
                collection_name=collection_name,
                points_selector=delete_operations,
                wait=True
            )
            
            results.append({
                'operation': 'delete',
                'count': len(delete_operations),
                'status': 'success'
            })
            
        except Exception as e:
            results.append({
                'operation': 'delete',
                'count': len(delete_operations),
                'status': 'failed',
                'error': str(e)
            })
    
    return {
        'total_operations': len(operations),
        'upsert_count': len(upsert_operations),
        'delete_count': len(delete_operations),
        'results': results
    }
```

---

## 🔧 **임베딩 생성 최적화**

### 🚀 **배치 임베딩 생성**

```python
import openai
from typing import List
import asyncio

async def generate_embeddings_batch(
    texts: List[str],
    model: str = "text-embedding-3-small",
    batch_size: int = 100
) -> List[List[float]]:
    """배치 단위 임베딩 생성 (비용 및 성능 최적화)"""
    
    all_embeddings = []
    
    # 텍스트 전처리
    processed_texts = []
    for text in texts:
        # 길이 제한 (8192 토큰 = 약 32,000 문자)
        if len(text) > 32000:
            text = text[:32000] + "..."
        
        # 빈 텍스트 처리
        if not text.strip():
            text = "빈 문서"
        
        processed_texts.append(text)
    
    # 배치 단위 처리
    for i in range(0, len(processed_texts), batch_size):
        batch_texts = processed_texts[i:i + batch_size]
        
        try:
            # OpenAI API 호출
            response = await openai.embeddings.create(
                model=model,
                input=batch_texts,
                encoding_format="float"  # 효율적인 인코딩
            )
            
            # 임베딩 추출
            batch_embeddings = [data.embedding for data in response.data]
            all_embeddings.extend(batch_embeddings)
            
            logger.info(f"Generated embeddings for batch {i//batch_size + 1}/{len(processed_texts)//batch_size + 1}")
            
            # Rate limit 준수 (TPM 제한)
            await asyncio.sleep(0.1)
            
        except Exception as e:
            logger.error(f"Failed to generate embeddings for batch {i//batch_size + 1}: {e}")
            
            # 실패한 배치는 기본 임베딩으로 대체
            dummy_embedding = [0.0] * 1536  # text-embedding-3-small 크기
            for _ in range(len(batch_texts)):
                all_embeddings.append(dummy_embedding)
    
    logger.info(f"Generated {len(all_embeddings)} embeddings total")
    return all_embeddings

async def generate_embedding(text: str, model: str = "text-embedding-3-small") -> List[float]:
    """단일 텍스트 임베딩 생성 (캐싱 적용)"""
    
    # 캐시 키 생성
    text_hash = hashlib.md5(text.encode()).hexdigest()
    cache_key = f"embedding:{model}:{text_hash}"
    
    # Redis 캐시 확인
    cached_embedding = await redis_client.get(cache_key)
    if cached_embedding:
        return orjson.loads(cached_embedding)
    
    # 임베딩 생성
    try:
        response = await openai.embeddings.create(
            model=model,
            input=text[:32000],  # 길이 제한
            encoding_format="float"
        )
        
        embedding = response.data[0].embedding
        
        # 캐시 저장 (7일)
        await redis_client.setex(cache_key, 604800, orjson.dumps(embedding))
        
        return embedding
        
    except Exception as e:
        logger.error(f"Failed to generate embedding: {e}")
        return [0.0] * 1536  # 기본 임베딩
```

---

## 📊 **벡터 데이터베이스 모니터링**

### 📈 **성능 메트릭 추적**

```python
class VectorDBMetrics:
    def __init__(self):
        self.metrics = {
            'total_documents': 0,
            'total_searches': 0,
            'average_search_time': 0.0,
            'cache_hit_rate': 0.0,
            'storage_size_mb': 0.0,
            'tenant_distribution': {},
            'platform_distribution': {}
        }
    
    async def collect_metrics(self) -> Dict:
        """Qdrant 메트릭 수집"""
        
        client = QdrantClient(
            url=os.getenv("QDRANT_URL"),
            api_key=os.getenv("QDRANT_API_KEY")
        )
        
        try:
            # 컬렉션 정보 조회
            collection_info = await client.get_collection("documents")
            
            self.metrics.update({
                'total_documents': collection_info.points_count,
                'storage_size_mb': collection_info.disk_usage / (1024 * 1024),
                'vector_dimensions': collection_info.config.params.vectors.size,
                'distance_metric': collection_info.config.params.vectors.distance.value
            })
            
            # 테넌트별 분포 조회 (샘플링)
            await self._collect_tenant_distribution(client)
            
        except Exception as e:
            logger.error(f"Failed to collect vector DB metrics: {e}")
        
        return self.metrics
    
    async def _collect_tenant_distribution(self, client: QdrantClient):
        """테넌트별 문서 분포 수집"""
        
        try:
            # 전체 문서의 10% 샘플링
            sample_size = max(100, self.metrics['total_documents'] // 10)
            
            scroll_result = await client.scroll(
                collection_name="documents",
                limit=sample_size,
                with_payload=["company_id", "platform"]
            )
            
            tenant_counts = {}
            platform_counts = {}
            
            for point in scroll_result[0]:  # points
                company_id = point.payload.get('company_id', 'unknown')
                platform = point.payload.get('platform', 'unknown')
                
                tenant_counts[company_id] = tenant_counts.get(company_id, 0) + 1
                platform_counts[platform] = platform_counts.get(platform, 0) + 1
            
            self.metrics['tenant_distribution'] = tenant_counts
            self.metrics['platform_distribution'] = platform_counts
            
        except Exception as e:
            logger.error(f"Failed to collect tenant distribution: {e}")

# 전역 메트릭 인스턴스
vector_metrics = VectorDBMetrics()
```

---

## 📚 **관련 참조 지침서**

- **data-collection-patterns.instructions.md** - 데이터 수집 및 전처리
- **data-processing-llm.instructions.md** - LLM 요약 및 구조화
- **multitenant-security.instructions.md** - 멀티테넌트 보안 및 격리
- **backend-implementation-patterns.instructions.md** - 백엔드 성능 최적화
- **quick-reference.instructions.md** - 핵심 패턴 즉시 참조

---

## 🔗 **크로스 참조**

이 지침서는 다음과 연계됩니다:
- **데이터 수집**: 수집된 데이터의 벡터화 준비
- **LLM 처리**: 요약된 데이터의 임베딩 생성  
- **멀티테넌트**: company_id 기반 벡터 데이터 격리
- **API 서비스**: 검색 결과의 클라이언트 제공

**세션 간 일관성**: 이 벡터 처리 패턴들은 AI 세션이 바뀌어도 동일하게 적용되어야 합니다.
