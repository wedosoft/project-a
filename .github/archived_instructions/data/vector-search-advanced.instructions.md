---
applyTo: "**"
---

# 🔍 벡터 검색 고급 기능 지침서

_AI 참조 최적화 버전 - 하이브리드 검색, 컨텍스트 확장, 성능 튜닝_

## 🎯 **고급 검색 패턴**

### 🔄 **하이브리드 검색 (벡터 + 키워드)**

```python
async def hybrid_search(
    company_id: str,
    platform: str,
    query_text: str,
    keyword_filters: Dict = None,
    limit: int = 10
) -> List[Dict]:
    """벡터 검색 + 키워드 필터링 조합"""
    
    # 1. 기본 벡터 검색 (더 많은 후보 확보)
    vector_results = await search_similar_documents(
        company_id=company_id,
        platform=platform,
        query_text=query_text,
        limit=limit * 2,
        score_threshold=0.5  # 낮은 임계값
    )
    
    # 2. 키워드 기반 후처리 필터링
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
```

### 🌐 **컨텍스트 확장 검색**

```python
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
            query_text=' '.join(top_tag_names),
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

## ⚡ **성능 최적화 클래스**

### 📈 **검색 캐싱 최적화**

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
async def batch_vector_operations(operations: List[Dict]) -> Dict:
    """배치 벡터 작업 최적화"""
    
    client = QdrantClient(url=os.getenv("QDRANT_URL"), api_key=os.getenv("QDRANT_API_KEY"))
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

### 🚀 **배치 임베딩 처리**

```python
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
                encoding_format="float"
            )
            
            # 임베딩 추출
            batch_embeddings = [data.embedding for data in response.data]
            all_embeddings.extend(batch_embeddings)
            
            # Rate limit 준수
            await asyncio.sleep(0.1)
            
        except Exception as e:
            # 실패한 배치는 기본 임베딩으로 대체
            dummy_embedding = [0.0] * 1536
            for _ in range(len(batch_texts)):
                all_embeddings.append(dummy_embedding)
    
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
            input=text[:32000],
            encoding_format="float"
        )
        
        embedding = response.data[0].embedding
        
        # 캐시 저장 (7일)
        await redis_client.setex(cache_key, 604800, orjson.dumps(embedding))
        
        return embedding
        
    except Exception as e:
        return [0.0] * 1536  # 기본 임베딩
```

---

## 📊 **벡터 DB 모니터링**

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
        
        client = QdrantClient(url=os.getenv("QDRANT_URL"), api_key=os.getenv("QDRANT_API_KEY"))
        
        try:
            # 컬렉션 정보 조회
            collection_info = await client.get_collection("documents")
            
            self.metrics.update({
                'total_documents': collection_info.points_count,
                'storage_size_mb': collection_info.disk_usage / (1024 * 1024),
                'vector_dimensions': collection_info.config.params.vectors.size,
                'distance_metric': collection_info.config.params.vectors.distance.value
            })
            
            return self.metrics
            
        except Exception as e:
            logger.error(f"Failed to collect vector DB metrics: {e}")
            return self.metrics

# 전역 메트릭 인스턴스
vector_metrics = VectorDBMetrics()
```

---

## ✅ **고급 기능 체크리스트**

### 🔄 **하이브리드 검색**

- [ ] 벡터 + 키워드 필터링 구현
- [ ] 날짜 범위 필터링 지원
- [ ] 태그 기반 필터링 지원
- [ ] 점수 기반 재정렬 로직

### 🌐 **컨텍스트 확장**

- [ ] 관련 문서 자동 발견
- [ ] 태그 기반 연관 검색
- [ ] 중복 제거 로직
- [ ] 컨텍스트 윈도우 최적화

### ⚡ **성능 최적화**

- [ ] 검색 결과 캐싱 (5분)
- [ ] 배치 작업 최적화
- [ ] 임베딩 캐싱 (7일)
- [ ] 메모리 사용량 제한

### 📊 **모니터링**

- [ ] 성능 메트릭 수집
- [ ] 검색 응답시간 추적
- [ ] 캐시 적중률 측정
- [ ] 스토리지 사용량 모니터링

---

## 🔗 **관련 지침서**

- **핵심 패턴**: `vector-storage-core.instructions.md`
- **데이터 워크플로우**: `data-workflow.instructions.md`
- **모니터링**: `monitoring-testing-strategy.instructions.md`

> **참고**: 이 지침서는 벡터 검색의 고급 기능을 다룹니다. 기본 패턴은 core 지침서를 참조하세요.
