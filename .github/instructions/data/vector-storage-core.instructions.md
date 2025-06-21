---
applyTo: "**"
---

# 🔍 벡터 저장소 핵심 지침서

_AI 참조 최적화 버전 - 멀티테넌트 벡터 데이터베이스 핵심 패턴_

## 🎯 **TL;DR - 벡터 처리 핵심 요약**

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

---

## 🚀 **벡터 저장 핵심 패턴**

```python
async def store_document_embeddings(
    company_id: str,
    platform: str,  # 'freshdesk', 'zendesk', 'servicenow'
    documents: List[Dict],  # LLM 요약 완료된 문서들
    data_type: str = "ticket"  # 'ticket' or 'kb'
) -> Dict[str, Any]:
    """멀티플랫폼/멀티테넌트 벡터 저장 (단일 컬렉션 사용)"""
    
    client = QdrantClient(url=os.getenv("QDRANT_URL"), api_key=os.getenv("QDRANT_API_KEY"))
    collection_name = "documents"
    
    # 1. 임베딩 생성 (요약 텍스트만)
    texts_to_embed = []
    for doc in documents:
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
        point_id = f"{company_id}_{platform}_{doc.get('ticket_id', uuid.uuid4())}"
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
                wait=True
            )
            
            upload_results.append({
                'batch_index': i // batch_size,
                'batch_size': len(batch),
                'status': 'success'
            })
            
        except Exception as e:
            upload_results.append({
                'batch_index': i // batch_size,
                'batch_size': len(batch),
                'status': 'failed',
                'error': str(e)
            })
    
    return {
        'company_id': company_id,
        'platform': platform,
        'total_documents': len(documents),
        'uploaded': sum(r['batch_size'] for r in upload_results if r['status'] == 'success'),
        'failed': sum(r['batch_size'] for r in upload_results if r['status'] == 'failed'),
        'collection_name': collection_name
    }
```

---

## 🔍 **벡터 검색 핵심 패턴**

```python
async def search_similar_documents(
    company_id: str,
    platform: str,
    query_text: str,
    data_type: str = "ticket",
    limit: int = 10,
    score_threshold: float = 0.7
) -> List[Dict]:
    """테넌트/플랫폼별 격리된 벡터 검색"""
    
    client = QdrantClient(url=os.getenv("QDRANT_URL"), api_key=os.getenv("QDRANT_API_KEY"))
    
    # 1. 쿼리 임베딩 생성
    query_embedding = await generate_embedding(query_text)
    
    # 2. 멀티테넌트 필터 설정
    search_filter = Filter(
        must=[
            FieldCondition(key="company_id", match=MatchValue(value=company_id)),
            FieldCondition(key="platform", match=MatchValue(value=platform)),
            FieldCondition(key="data_type", match=MatchValue(value=data_type))
        ]
    )
    
    # 3. 벡터 검색 실행
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
        
        # 4. 결과 후처리
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
                'has_original_data': bool(point.payload.get('original_data'))
            }
            results.append(result)
        
        return results
        
    except Exception as e:
        logger.error(f"Vector search failed for {company_id}/{platform}: {e}")
        return []
```

---

## ⚡ **성능 최적화 체크리스트**

### ✅ **필수 최적화 항목**

- [ ] **단일 컬렉션 전략** 확인
- [ ] **배치 업로드** (100개 단위) 적용
- [ ] **페이로드 인덱스** 생성 (company_id, platform, data_type)
- [ ] **캐싱 전략** 구현 (검색 결과 5분 캐시)
- [ ] **임베딩 중복 제거** 로직 적용

### 📊 **모니터링 포인트**

- **문서 수**: 컬렉션당 문서 개수
- **검색 응답시간**: 평균 < 500ms 목표
- **캐시 적중률**: > 70% 목표
- **스토리지 사용량**: 월별 증가율 추적
- **테넌트별 분포**: 불균형 방지

---

## 🔗 **관련 지침서**

- **상세 구현**: `vector-search-advanced.instructions.md`
- **임베딩 최적화**: `embedding-optimization.instructions.md`
- **모니터링**: `vector-monitoring.instructions.md`
- **데이터 워크플로우**: `data-workflow.instructions.md`

> **참고**: 이 지침서는 벡터 저장소의 핵심 패턴만 다룹니다. 고급 기능은 관련 지침서를 참조하세요.
