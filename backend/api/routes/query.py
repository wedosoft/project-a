"""
쿼리 처리 라우트

사용자 쿼리에 대한 AI 응답 생성 및 스트리밍 응답을 처리하는 엔드포인트들입니다.
벡터 검색, 컨텍스트 최적화, LLM 호출을 통한 응답 생성을 담당합니다.
"""

import json
import time
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from ..dependencies import (
    get_tenant_id,
    get_platform,
    get_vector_db,
    get_fetcher,
    get_llm_router
)
from core.search.anthropic.search_orchestrator import AnthropicSearchOrchestrator
from core.search.enhanced_search import EnhancedSearchEngine
from ..models.requests import QueryRequest
from ..models.responses import QueryResponse
from ..models.shared import DocumentInfo
from ..models.streaming import (
    StreamEventBuilder, 
    StreamStage, 
    ResultType, 
    format_sse_event, 
    format_sse_done,
    create_ticket_result_event,
    create_kb_result_event
)

# 로거
import logging
logger = logging.getLogger(__name__)

router = APIRouter()


def get_anthropic_orchestrator(
    vector_db=Depends(get_vector_db),
    llm_router=Depends(get_llm_router)
) -> AnthropicSearchOrchestrator:
    """AnthropicSearchOrchestrator 의존성 주입"""
    return AnthropicSearchOrchestrator(
        vector_db=vector_db,
        llm_manager=llm_router
    )


def get_enhanced_search_engine(
    vector_db=Depends(get_vector_db),
    llm_router=Depends(get_llm_router)
) -> EnhancedSearchEngine:
    """EnhancedSearchEngine 의존성 주입"""
    return EnhancedSearchEngine(
        vector_db=vector_db,
        llm_manager=llm_router
    )


@router.post("/query", response_model=QueryResponse)
# @cached(cache, key=partial(_query_cache_key, "query_endpoint"))  # 캐시는 나중에 추가
async def query_endpoint(
    req: QueryRequest,
    tenant_id: str = Depends(get_tenant_id),
    platform: str = Depends(get_platform),
    vector_db = Depends(get_vector_db),
    fetcher = Depends(get_fetcher),
    llm_router = Depends(get_llm_router),
    anthropic_orchestrator: AnthropicSearchOrchestrator = Depends(get_anthropic_orchestrator),
    enhanced_search: EnhancedSearchEngine = Depends(get_enhanced_search_engine)
):
    """
    사용자 쿼리에 대한 AI 응답을 생성하는 엔드포인트 (멀티플랫폼 지원)
    
    상담원 모드(agent_mode=True)일 때는 Anthropic Constitutional AI를 적용하여
    안전하고 유용한 검색 결과를 제공합니다.
    
    고급 검색 모드(enhanced_search=True)일 때는 첨부파일, 카테고리, 
    문제 해결 중심의 전문 검색을 제공합니다.

    Args:
        req: 쿼리 요청 객체 (QueryRequest)
        tenant_id: 테넌트 ID (의존성 함수를 통해 헤더에서 자동 추출)
        platform: 플랫폼 (X-Platform, X-Freshdesk-Domain,
                  X-Zendesk-Domain 헤더에서 자동 추출)

    Returns:
        검색 결과와 AI 응답을 포함한 QueryResponse 객체 또는 StreamingResponse
        
    고급 검색 사용 예시:
        POST /api/query
        {
            "query": "엑셀 파일이 있는 결제 문제",
            "enhanced_search": true,
            "enhanced_search_type": "attachment",
            "file_types": ["excel"],
            "categories": ["결제"]
        }
    """
    # 성능 측정을 시작합니다.
    start_time = time.time()
    
    # 고급 자연어 검색 모드 처리
    if req.enhanced_search:
        logger.info(f"고급 검색 모드 활성화: '{req.query[:50]}...' (tenant: {tenant_id})")
        
        try:
            # Enhanced Search Context 생성
            context = await enhanced_search.analyze_enhanced_query(req.query)
            
            # 요청에서 지정된 검색 타입이 있으면 우선 적용
            if req.enhanced_search_type and req.enhanced_search_type != "auto":
                context.search_type = req.enhanced_search_type
            
            # 요청 옵션을 컨텍스트에 반영
            if req.file_types and context.search_type == "attachment":
                if not context.attachment_filters:
                    context.attachment_filters = {}
                
                # 파일 타입을 MIME 타입으로 변환
                content_types = []
                for file_type in req.file_types:
                    if file_type.lower() in ["pdf"]:
                        content_types.append("application/pdf")
                    elif file_type.lower() in ["excel", "xlsx"]:
                        content_types.extend([
                            "application/vnd.ms-excel",
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        ])
                    elif file_type.lower() in ["image", "png", "jpg", "jpeg"]:
                        content_types.extend(["image/png", "image/jpeg", "image/gif"])
                    elif file_type.lower() in ["word", "docx"]:
                        content_types.extend([
                            "application/msword",
                            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                        ])
                
                if content_types:
                    context.attachment_filters["content_types"] = content_types
            
            # 파일 크기 필터
            if req.max_file_size_mb and context.search_type == "attachment":
                if not context.attachment_filters:
                    context.attachment_filters = {}
                context.attachment_filters["max_size"] = int(req.max_file_size_mb * 1024 * 1024)
            
            if req.min_file_size_mb and context.search_type == "attachment":
                if not context.attachment_filters:
                    context.attachment_filters = {}
                context.attachment_filters["min_size"] = int(req.min_file_size_mb * 1024 * 1024)
            
            # 카테고리 필터
            if req.categories and context.search_type == "category":
                context.category_hints = req.categories
            
            # 해결책 필터
            if req.solution_type and context.search_type == "solution":
                if not context.solution_requirements:
                    context.solution_requirements = {}
                
                if req.solution_type == "quick_fix":
                    context.solution_requirements["해결책"] = True
                elif req.solution_type == "step_by_step":
                    context.solution_requirements["단계별"] = True
                elif req.solution_type == "similar_case":
                    context.solution_requirements["유사사례"] = True
            
            if req.include_resolved_only:
                context.filters["status"] = ["solved", "closed"]
            
            # 고급 검색 실행
            search_results = await enhanced_search.execute_enhanced_search(
                context=context,
                tenant_id=tenant_id,
                platform=platform,
                top_k=req.top_k
            )
            
            # AI 요약 생성
            ai_summary = ""
            if search_results.get("total_results", 0) > 0:
                ai_summary = await enhanced_search.generate_enhanced_response(search_results, context)
            
            # 결과 매핑 (QueryResponse 형식에 맞춰서)
            processing_time = (time.time() - start_time) * 1000
            
            # DocumentInfo 목록 생성
            from ..models.shared import DocumentInfo
            document_infos = []
            
            documents = search_results.get("documents", [])
            metadatas = search_results.get("metadatas", [])
            ids = search_results.get("ids", [])
            distances = search_results.get("distances", [])
            
            for i, (doc, meta, doc_id, distance) in enumerate(zip(documents, metadatas, ids, distances)):
                doc_info = DocumentInfo(
                    id=doc_id,
                    content=doc[:500] + "..." if len(doc) > 500 else doc,
                    metadata=meta,
                    score=round((1 - distance/2) * 100, 1) if distance else None,
                    source=meta.get("doc_type", "unknown")
                )
                document_infos.append(doc_info)
            
            return QueryResponse(
                query=req.query,
                response=ai_summary or "검색 결과를 확인해주세요.",
                documents=document_infos,
                search_metadata={
                    "search_type": context.search_type,
                    "intent": context.intent,
                    "keywords": context.keywords,
                    "filters_applied": context.filters,
                    "attachment_filters": context.attachment_filters,
                    "category_hints": context.category_hints,
                    "solution_requirements": context.solution_requirements,
                    "enhanced_search": True
                },
                processing_time_ms=processing_time,
                total_results=search_results.get("total_results", 0)
            )
            
        except Exception as e:
            logger.error(f"고급 검색 실패: {e}")
            # 고급 검색 실패 시 기본 검색으로 폴백
            logger.info("고급 검색 실패, 기본 모드로 폴백")
    
    # 상담원 모드 처리
    if req.agent_mode:
        logger.info(f"상담원 모드 활성화: '{req.query[:50]}...' (tenant: {tenant_id})")
        
        # 스트리밍 응답 처리
        if req.stream_response:
            async def stream_agent_response():
                try:
                    async for chunk in anthropic_orchestrator.execute_agent_search(
                        query=req.query,
                        tenant_id=tenant_id,
                        platform=platform,
                        stream=True
                    ):
                        # 표준 스트리밍 이벤트 구조로 변환
                        if chunk.get("type") == "final":
                            # 최종 결과를 완료 이벤트로 변환
                            complete_event = StreamEventBuilder.create_complete_event(
                                message="AI 분석이 완료되었습니다",
                                final_data=chunk
                            )
                            yield format_sse_event(complete_event)
                            yield format_sse_done()
                            break
                        else:
                            # 기타 청크를 표준 형식으로 변환
                            if chunk.get("type") == "progress":
                                progress_event = StreamEventBuilder.create_progress_event(
                                    stage=StreamStage.LLM_PROCESSING,
                                    message=chunk.get("message", "AI 처리 중..."),
                                    progress=chunk.get("progress", 50)
                                )
                                yield format_sse_event(progress_event)
                            else:
                                # 원본 청크를 그대로 전송 (하위 호환성)
                                chunk_data = json.dumps(chunk, ensure_ascii=False)
                                yield f"data: {chunk_data}\n\n"
                            
                except Exception as e:
                    logger.error(f"상담원 스트리밍 중 오류: {e}")
                    error_event = StreamEventBuilder.create_error_event(
                        error=str(e),
                        error_code="AGENT_STREAMING_ERROR",
                        stage=StreamStage.LLM_PROCESSING
                    )
                    yield format_sse_event(error_event)
                    yield format_sse_done()
                finally:
                    yield format_sse_done()
            
            return StreamingResponse(
                stream_agent_response(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Headers": "*"
                }
            )
        
        # 일반 상담원 응답 처리 (non-streaming)
        else:
            result_generator = anthropic_orchestrator.execute_agent_search(
                query=req.query,
                tenant_id=tenant_id,
                platform=platform,
                stream=False
            )
            
            # 최종 결과만 추출
            final_result = None
            async for chunk in result_generator:
                if chunk.get("type") == "final":
                    final_result = chunk
                    break
            
            if not final_result:
                raise HTTPException(
                    status_code=500,
                    detail="상담원 검색 결과를 가져올 수 없습니다."
                )
            
            # QueryResponse 형식으로 변환하여 반환
            response_time = (time.time() - start_time) * 1000
            
            # 검색 결과를 DocumentInfo 형식으로 변환
            search_results = final_result.get("search_results", {})
            document_infos = _convert_agent_results_to_document_info(search_results)
            
            return QueryResponse(
                answer=final_result.get("ai_summary", "검색 결과를 처리할 수 없습니다."),
                context_docs=document_infos,
                context_images=[],
                metadata={
                    "agent_mode": True,
                    "search_context": final_result.get("search_context", {}),
                    "action_items": final_result.get("action_items", []),
                    "related_suggestions": final_result.get("related_suggestions", []),
                    "quality_score": final_result.get("quality_score", 0.0),
                    "response_time_ms": response_time
                }
            )
    
    # 요청에서 플랫폼이 명시적으로 지정된 경우 우선 사용
    effective_platform = req.platform or platform
    
    # 검색 의도(intent) 처리
    search_intent = req.intent.lower() if req.intent else "search"
    logger.info(
        f"플랫폼: {effective_platform}, 검색 의도: '{search_intent}', "
        f"검색 타입: {req.type}"
    )

    # 콘텐츠 타입 필터링
    content_types = (
        [t.lower() for t in req.type] if req.type
        else ["tickets", "solutions", "images", "attachments"]
    )
    
    ticket_title = ""
    ticket_body = ""
    ticket_conversations = []
    ticket_context_for_query = ""
    ticket_context_for_llm = ""

    if req.ticket_id:
        logger.info(
            f"플랫폼 {effective_platform}에서 티켓 ID {req.ticket_id}에 대한 "
            "정보 조회를 시도합니다."
        )
        # doc_type='ticket'과 platform 필터를 명시적으로 지정하여 멀티플랫폼 지원
        ticket_data = vector_db.get_by_id(
            original_id_value=req.ticket_id,
            tenant_id=tenant_id,
            doc_type="ticket",
            platform=effective_platform
        )
        
        if ticket_data and ticket_data.get("metadata"):
            metadata = ticket_data["metadata"]
            ticket_title = metadata.get(
                "subject", f"티켓 ID {req.ticket_id} 관련 문의"
            )
            # 본문은 'text' 필드를 우선 사용하고, 없다면 'description_text' 사용
            ticket_body = metadata.get(
                "text", metadata.get("description_text", "티켓 본문 정보 없음")
            )
            # 대화 내용은 'conversations' 필드에서 가져오며, 리스트 형태를 기대
            raw_conversations = metadata.get("conversations", [])
            if isinstance(raw_conversations, list):
                # 문자열로 변환
                ticket_conversations = [
                    str(conv) for conv in raw_conversations
                ]
            # 문자열로 저장된 경우 (예: JSON 문자열)
            elif isinstance(raw_conversations, str):
                try:
                    parsed_convs = json.loads(raw_conversations)
                    if isinstance(parsed_convs, list):
                        ticket_conversations = [
                            str(conv) for conv in parsed_convs
                        ]
                except json.JSONDecodeError:
                    # 파싱 실패 시 통째로 사용
                    ticket_conversations = [raw_conversations]

            # 요약 필드가 있다면 활용
            if not ticket_conversations and metadata.get("conversation_summary"):
                ticket_conversations = [
                    str(metadata.get("conversation_summary"))
                ]

            logger.info(
                f"티켓 ID {req.ticket_id} 정보 조회 완료: "
                f"제목='{ticket_title[:50]}...'"
            )
        else:
            logger.warning(
                f"티켓 ID {req.ticket_id} 정보를 Qdrant에서 찾을 수 없거나 "
                "메타데이터가 없습니다."
            )
            ticket_title = f"티켓 ID {req.ticket_id} 정보 없음"
            ticket_body = "해당 티켓 정보를 찾을 수 없습니다."
            # ticket_conversations는 빈 리스트로 유지

        # 임베딩 및 검색을 위한 티켓 컨텍스트
        ticket_context_for_query = (
            f"현재 티켓 제목: {ticket_title}\\n현재 티켓 본문: {ticket_body}"
            f"\\n\\n대화 내용:\\n" + "\\n".join(ticket_conversations)
        )
        # LLM 프롬프트에 포함될 티켓 컨텍스트
        ticket_context_for_llm = (
            f"\\n[현재 티켓 정보]\\n제목: {ticket_title}\\n본문: {ticket_body}"
            f"\\n대화 요약:\\n" + "\\n".join(ticket_conversations) + "\\n"
        )

    search_start = time.time()
    # 1. 검색 단계: 사용자 쿼리를 임베딩하고 관련 문서를 검색합니다.
    # 티켓 ID가 있는 경우, 티켓 내용을 포함하여 임베딩할 쿼리 생성
    query_for_embedding_str = (
        f"{ticket_context_for_query}\\n\\n사용자 질문: {req.query}"
        if req.ticket_id else req.query
    )
    
    # 벡터 검색 로직
    # 임베딩 생성
    embeddings = await llm_router.get_embeddings([query_for_embedding_str])
    query_embedding = embeddings[0] if embeddings else None
    
    if not query_embedding:
        raise HTTPException(
            status_code=500,
            detail="임베딩 생성에 실패했습니다"
        )

    # 콘텐츠 타입에 따라 검색할 문서 타입 결정
    top_k_per_type = max(
        1, req.top_k // len([
            t for t in content_types 
            if t in ["tickets", "solutions"]
        ])
    )

    # 티켓 검색 (콘텐츠 타입에 "tickets"가 포함된 경우만)
    ticket_results = {
        "documents": [], "metadatas": [], "ids": [], "distances": []
    }
    if "tickets" in content_types:
        try:
            ticket_results = vector_db.search(
                query_embedding,
                top_k_per_type,
                tenant_id,
                doc_type="ticket",
                platform=effective_platform
            )
            # 검색 결과가 올바르지 않으면 기본값 사용
            if not isinstance(ticket_results, dict) or 'documents' not in ticket_results:
                ticket_results = {
                    "documents": [], "metadatas": [], "ids": [], "distances": []
                }
        except Exception as e:
            logger.error(f"티켓 검색 중 오류: {e}")
            ticket_results = {
                "documents": [], "metadatas": [], "ids": [], "distances": []
            }
    logger.info(
        f"플랫폼 {effective_platform} 티켓 검색 결과: "
        f"{len(ticket_results.get('documents', []))} 건"
    )

    # 지식베이스 문서 검색 (콘텐츠 타입에 "solutions"가 포함된 경우만)
    kb_results = {
        "documents": [], "metadatas": [], "ids": [], "distances": []
    }
    if "solutions" in content_types:
        try:
            kb_results = vector_db.search(
                query_embedding,
                top_k_per_type,
                tenant_id,
                doc_type="kb",
                platform=effective_platform
            )
            # 검색 결과가 올바르지 않으면 기본값 사용
            if not isinstance(kb_results, dict) or 'documents' not in kb_results:
                kb_results = {
                    "documents": [], "metadatas": [], "ids": [], "distances": []
                }
        except Exception as e:
            logger.error(f"KB 검색 중 오류: {e}")
            kb_results = {
                "documents": [], "metadatas": [], "ids": [], "distances": []
            }
        logger.info(
            f"플랫폼 {effective_platform} 솔루션 검색 결과: "
            f"{len(kb_results.get('documents', []))} 건"
        )

    # 검색 결과를 병합합니다.
    all_docs_content = (
        ticket_results["documents"] + kb_results["documents"]
    )
    all_metadatas = (
        ticket_results["metadatas"] + kb_results["metadatas"]
    )
    all_distances = (
        ticket_results["distances"] + kb_results["distances"]
    )
    
    # 통합된 결과를 유사도 기준으로 재정렬합니다 (거리가 작을수록 유사도가 높음).
    # 각 메타데이터에 doc_type을 명시적으로 추가합니다.
    for meta in ticket_results["metadatas"]:
        meta["source_type"] = "ticket"
    for meta in kb_results["metadatas"]:
        meta["source_type"] = "kb"
    # 문서 타입별 메타데이터 설정 완료

    combined = list(zip(all_docs_content, all_metadatas, all_distances))
    # 거리(distance) 기준으로 오름차순 정렬
    combined.sort(key=lambda x: x[2])
    
    # 최대 top_k 개수만큼 잘라냅니다.
    final_top_k = req.top_k
    combined = combined[:final_top_k]
    
    # 다시 분리합니다.
    docs = [item[0] for item in combined]
    metadatas = [item[1] for item in combined]
    # 이 distances는 실제 거리 또는 1-score 값임
    distances = [item[2] for item in combined]
    
    # 기존 검색에서는 추가 정보 없음
    search_analysis = {}
    custom_field_matches = []
    llm_insights = {}
    search_quality_score = None
    
    search_time = time.time() - search_start
    
    # 2. 컨텍스트 최적화 단계: 검색된 문서를 LLM 입력에 적합하도록 가공합니다.
    context_start = time.time()
    
    # 최적화된 컨텍스트를 구성합니다. (검색된 문서들로부터)
    # 간단한 컨텍스트 구성 (임시)
    base_context = "\n\n".join([str(doc) for doc in docs[:req.top_k]])
    optimized_metadatas = metadatas[:req.top_k]
    context_meta = {
        "total_docs": len(docs),
        "selected_docs": min(len(docs), req.top_k),
        "context_length": len(base_context)
    }
    
    # LLM에 전달할 최종 컨텍스트 (티켓 정보 + 검색된 문서 정보)
    final_context_for_llm = f"{ticket_context_for_llm}{base_context}"
    
    prompt = llm_router.build_prompt(final_context_for_llm, req.query, agent_mode=False)
    
    structured_docs = []
    for i, (doc_content_item, metadata_item, distance_or_score_metric) in enumerate(zip(docs, metadatas, distances)):
        title = metadata_item.get("title", "")
        content = doc_content_item
        doc_type = metadata_item.get("source_type", "unknown")

        lines = doc_content_item.split("\\n", 2)
        if len(lines) > 0 and lines[0].startswith("제목:"):
            title = lines[0].replace("제목:", "").strip()
            if len(lines) > 1:
                content = "\\n".join(lines[1:]).strip()
                if content.startswith("설명:"):
                    content = content.replace("설명:", "", 1).strip()
        
        # 코사인 거리 (0~2)를 백분율로 변환
        relevance_score = round(((2 - distance_or_score_metric) / 2) * 100, 1)

        # Platform-Neutral 메타데이터 구성
        platform_metadata = {}
        
        # 티켓 상태 정보 추가 - 원본 값 그대로 사용
        platform_metadata["ticket_status"] = metadata_item.get("status")
        
        # 우선순위 정보 추가 - 원본 값 그대로 사용
        platform_metadata["priority"] = metadata_item.get("priority")
        
        # 요청자 정보 추가 - 원본 값 그대로 사용
        requester = (metadata_item.get("requester_id") or 
                    metadata_item.get("customer_email") or 
                    metadata_item.get("extended_metadata", {}).get("requester_id"))
        platform_metadata["requester"] = requester
        
        # 담당자 정보 추가 - 원본 값 그대로 사용
        assignee = (metadata_item.get("agent_name") or 
                   metadata_item.get("extended_metadata", {}).get("responder_id") or 
                   metadata_item.get("extended_metadata", {}).get("agent_id"))
        platform_metadata["assignee"] = assignee
        
        # 기타 유용한 메타데이터 추가
        if metadata_item.get("company_name"):
            platform_metadata["company_name"] = metadata_item.get("company_name")
        elif metadata_item.get("extended_metadata", {}).get("company_id"):
            platform_metadata["company_id"] = metadata_item.get("extended_metadata", {}).get("company_id")
        
        if metadata_item.get("ticket_category"):
            platform_metadata["category"] = metadata_item.get("ticket_category")
        elif metadata_item.get("extended_metadata", {}).get("custom_fields", {}).get("category"):
            platform_metadata["category"] = metadata_item.get("extended_metadata", {}).get("custom_fields", {}).get("category")
        
        if metadata_item.get("created_at"):
            platform_metadata["created_at"] = metadata_item.get("created_at")
        if metadata_item.get("updated_at"):
            platform_metadata["updated_at"] = metadata_item.get("updated_at")
        
        # 첨부파일 정보 추가 (최적화된 구조)
        if metadata_item.get("has_attachments"):
            platform_metadata["has_attachments"] = metadata_item.get("has_attachments")
        if metadata_item.get("attachment_count"):
            platform_metadata["attachment_count"] = metadata_item.get("attachment_count")
        if metadata_item.get("has_inline_images"):
            platform_metadata["has_inline_images"] = metadata_item.get("has_inline_images")
        
        doc_info = DocumentInfo(
            title=title,
            content=content,
            source_id=metadata_item.get("source_id", metadata_item.get("id", "")),
            tenant_id=metadata_item.get("tenant_id"),
            platform=metadata_item.get("platform"),
            platform_neutral_key=metadata_item.get("platform_neutral_key"),
            source_url=metadata_item.get("source_url", ""),
            relevance_score=relevance_score,
            doc_type=doc_type,
            platform_metadata=platform_metadata if platform_metadata else None
        )
        structured_docs.append(doc_info)
    
    context_time = time.time() - context_start

    context_images = []
    # 콘텐츠 타입에 "images" 또는 "attachments"가 포함된 경우만 이미지 정보 추출
    if any(t in ["images", "attachments"] for t in content_types):
        for i, metadata in enumerate(optimized_metadatas): # optimized_metadatas 사용
            # 1. 기존 image_attachments 처리 (하위 호환성)
            image_attachments = metadata.get("image_attachments", "")
            if image_attachments:
                try:
                    if isinstance(image_attachments, str):
                        image_attachments = json.loads(image_attachments)

                    if isinstance(image_attachments, list):
                        for img in image_attachments:
                            context_images.append(
                                {
                                    "name": img.get("name", ""),
                                    "url": img.get("url", ""),
                                    "content_type": img.get("content_type", ""),
                                    "doc_index": i,  # 어떤 문서에서 이미지가 왔는지 추적하기 위한 인덱스입니다.
                                    "source_type": "attachment",  # 기존 방식
                                    "source_id": metadata.get("source_id", ""),
                                    "title": (
                                        structured_docs[i].title
                                        if i < len(structured_docs)
                                        else ""
                                    ),
                                }
                            )
                except Exception as e:
                    logger.error(f"기존 이미지 정보 파싱 중 오류 발생: {e}")
            
            # 2. 새로운 통합 이미지 처리 (all_images)
            all_images = metadata.get("all_images", [])
            if all_images and isinstance(all_images, list):
                for img in all_images:
                    # 중복 방지를 위해 attachment_id 확인
                    attachment_id = img.get("attachment_id")
                    if attachment_id:
                        # 이미 추가된 이미지인지 확인
                        existing = any(
                            ctx_img.get("attachment_id") == attachment_id 
                            for ctx_img in context_images
                        )
                        
                        if not existing:
                            image_type = img.get("type", "unknown")  # "attachment" 또는 "inline"
                            
                            context_images.append({
                                "attachment_id": attachment_id,
                                "name": img.get("name", ""),
                                "content_type": img.get("content_type", ""),
                                "size": img.get("size", 0),
                                "alt_text": img.get("alt_text", ""),  # 인라인 이미지용
                                "doc_index": i,
                                "source_type": image_type,  # "attachment" 또는 "inline"
                                "source_id": metadata.get("source_id", ""),
                                "title": (
                                    structured_docs[i].title
                                    if i < len(structured_docs)
                                    else ""
                                ),
                                "position": img.get("position", 0),  # 인라인 이미지 위치
                                "conversation_id": img.get("conversation_id"),  # 대화 ID (있는 경우)
                                # URL은 포함하지 않음 (보안상 이유로 실시간 발급 필요)
                            })
            
            # 3. 인라인 이미지만 별도 처리 (선택적)
            inline_images = metadata.get("inline_images", [])
            if inline_images and isinstance(inline_images, list):
                try:
                    for img in inline_images:
                        attachment_id = img.get("attachment_id")
                        if attachment_id:
                            # 이미 all_images에서 처리되었는지 확인
                            existing = any(
                                ctx_img.get("attachment_id") == attachment_id and 
                                ctx_img.get("source_type") == "inline"
                                for ctx_img in context_images
                            )
                            
                            if not existing:
                                context_images.append({
                                    "attachment_id": attachment_id,
                                    "alt_text": img.get("alt_text", ""),
                                    "doc_index": i,
                                    "source_type": "inline",
                                    "source_id": metadata.get("source_id", ""),
                                    "title": (
                                        structured_docs[i].title
                                        if i < len(structured_docs)
                                        else ""
                                    ),
                                    "position": img.get("position", 0),
                                    "conversation_id": img.get("conversation_id"),
                                    # URL은 포함하지 않음 (실시간 발급 필요)
                                })
                except Exception as e:
                    logger.error(f"인라인 이미지 정보 파싱 중 오류 발생: {e}")

    logger.info(f"검색 결과에서 총 {len(context_images)}개의 이미지 정보 추출됨")

    # 3. LLM 호출 단계: 생성된 프롬프트를 LLM에 전달하여 답변을 생성합니다.
    llm_start = time.time()
    try:
        # 검색 의도에 따라 시스템 프롬프트 조정
        base_system_prompt = "당신은 친절한 고객 지원 AI입니다."
        
        if search_intent == "recommend":
            base_system_prompt += " 고객의 질문에 대해 최적의 솔루션을 추천해 주세요."
        elif search_intent == "answer":
            base_system_prompt += " 고객의 질문에 직접적이고 명확하게 답변해 주세요."
        elif search_intent == "summarize":
            base_system_prompt += " 검색된 정보를 간결하게 요약해서 제공해 주세요."
        
        # 사용자 지정 답변 지침이 있는 경우 추가
        system_prompt = base_system_prompt
        if req.answer_instructions:
            system_prompt = f"{base_system_prompt} 다음 지침에 따라 응답해 주세요: {req.answer_instructions}"
            
        # 실시간 상담원 쿼리용으로 용도 지정하여 호출
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]
        response = await llm_router.generate_for_use_case(
            use_case="realtime",
            messages=messages
        )
        answer = response.content
        
        # 콘텐츠 타입이 "attachments"나 "images"만 포함되어 있으면 이미지에 대한 설명 추가
        if len(content_types) == 1 and content_types[0] in ["attachments", "images"]:
            answer = "첨부 파일 및 이미지 정보만 요청하셨습니다.\n" + answer
            
    except Exception as e:
        logger.error(f"LLM 호출 중 오류 발생: {str(e)}") # 오류 로깅 메시지를 한글로 변경합니다.
        # 사용자에게 보여지는 오류 메시지는 한글로 작성합니다.
        raise HTTPException(status_code=500, detail=f"LLM 호출 중 오류가 발생했습니다: {str(e)}")
    llm_time = time.time() - llm_start # LLM 호출 소요 시간을 계산합니다.
    
    # 총 처리 시간을 계산합니다.
    total_time = time.time() - start_time
    
    # 성능을 로깅합니다. (최적화 정보 포함)
    optimization_info = (
        f"원본문서:{context_meta.get('original_docs_count', 0)} -> "
        f"top_k:{context_meta.get('after_top_k_count', 0)} -> "
        f"중복제거:{context_meta.get('after_deduplication_count', 0)} -> "
        f"관련성추출:{context_meta.get('after_relevance_extraction_count', 0)} -> "
        f"최종:{context_meta.get('final_optimized_docs_count', 0)}"
    )
    logger.info(
        f"성능: tenant_id='{tenant_id}', query='{req.query[:50]}...', "
        f"검색시간={search_time:.2f}s, 컨텍스트생성시간={context_time:.2f}s, "
        f"LLM호출시간={llm_time:.2f}s, 총시간={total_time:.2f}s, "
        f"최적화정보=({optimization_info})"
    )
    
    # 메타데이터를 구성합니다. (최적화 메타데이터 포함)
    metadata = {
        "duration_ms": int(total_time * 1000), # 총 소요 시간 (밀리초)
        "search_time_ms": int(search_time * 1000), # 검색 소요 시간 (밀리초)
        "context_time_ms": int(context_time * 1000), # 컨텍스트 생성 소요 시간 (밀리초)
        "llm_time_ms": int(llm_time * 1000), # LLM 호출 소요 시간 (밀리초)
        "model_used": response.model, # 사용된 LLM 모델
        "token_count": context_meta.get("token_count", 0), # 컨텍스트 토큰 수
        "context_docs_count": len(structured_docs), # 사용된 컨텍스트 문서 수
        "search_intent": search_intent, # 검색 의도
        "content_types": content_types, # 검색된 콘텐츠 타입
        "ticket_id": req.ticket_id, # 연관된 티켓 ID (있는 경우)
        # 새로운 최적화 메타데이터 추가
        "optimization": context_meta  # 전체 최적화 정보 포함
    }

    return QueryResponse(
        answer=answer, 
        context_docs=structured_docs, 
        context_images=context_images,
        metadata=metadata
    )


# 기존 별도 스트리밍 엔드포인트 제거됨 - 이제 /query?stream=true 형태로 통합됨
# 하위 호환성을 위해 유지되지만, 메인 엔드포인트로 리다이렉트
@router.post("/query/stream")
async def query_stream_deprecated(
    req: QueryRequest, 
    tenant_id: str = Depends(get_tenant_id),
    platform: str = Depends(get_platform),
    vector_db = Depends(get_vector_db),
    llm_router = Depends(get_llm_router)
):
    """
    [DEPRECATED] 스트리밍 방식 쿼리 엔드포인트
    
    ⚠️ 이 엔드포인트는 하위 호환성을 위해 유지되지만 deprecated입니다.
    새로운 코드에서는 /query?stream=true를 사용해주세요.
    """
    logger.warning("DEPRECATED: /query/stream 엔드포인트 사용됨. /query?stream=true 사용 권장")
    
    # 메인 엔드포인트로 리다이렉트
    return await query_endpoint(
        req=req,
        tenant_id=tenant_id,
        platform=platform,
        vector_db=vector_db,
        fetcher=None,  # 기본값 사용
        llm_router=llm_router,
        anthropic_orchestrator=AnthropicSearchOrchestrator(vector_db=vector_db, llm_manager=llm_router),
        enhanced_search=EnhancedSearchEngine(vector_db=vector_db, llm_manager=llm_router),
        stream=True  # 스트리밍 모드 강제 활성화
    )


# 하이브리드 검색 전용 엔드포인트 - 비활성화됨
# @router.post("/query/hybrid", response_model=QueryResponse)
# async def hybrid_query_endpoint(
#     req: QueryRequest,
#     tenant_id: str = Depends(get_tenant_id),
#     platform: str = Depends(get_platform),
#     hybrid_search_manager = Depends(get_hybrid_search_manager)
# ):
#     """
#     하이브리드 검색 전용 엔드포인트 - 현재 비활성화됨
#     
#     벡터 검색만 사용하는 모드로 변경되어 하이브리드 검색은 비활성화되었습니다.
#     """
#     pass


def _convert_agent_results_to_document_info(search_results: Dict[str, Any]) -> List[DocumentInfo]:
    """
    Anthropic 검색 결과를 DocumentInfo 리스트로 변환
    
    Args:
        search_results: AnthropicSearchOrchestrator의 검색 결과
        
    Returns:
        List[DocumentInfo]: 변환된 문서 정보 리스트
    """
    document_list = []
    
    documents = search_results.get("documents", [])
    metadatas = search_results.get("metadatas", [])
    ids = search_results.get("ids", [])
    distances = search_results.get("distances", [])
    
    for i, (doc, metadata, doc_id, distance) in enumerate(zip(
        documents, metadatas, ids, distances
    )):
        try:
            # 유사도 점수 계산 (거리를 유사도로 변환)
            similarity_score = max(0.0, (2.0 - distance) / 2.0)
            
            document_info = DocumentInfo(
                source_id=doc_id,  # id -> source_id로 변경
                title=metadata.get("title", metadata.get("subject", f"Document {i+1}")),
                content=doc[:500] + "..." if len(doc) > 500 else doc,  # 내용 제한
                relevance_score=similarity_score,
                doc_type=metadata.get("doc_type", "unknown"),
                tenant_id=metadata.get("tenant_id"),
                platform=metadata.get("platform"),
                platform_metadata=metadata  # 전체 메타데이터 포함
            )
            
            document_list.append(document_info)
            
        except Exception as e:
            logger.error(f"문서 {i} 변환 실패: {e}")
            logger.error(f"문서 데이터: doc_id={doc_id}, metadata keys={list(metadata.keys()) if metadata else 'None'}")
            # 변환 실패해도 기본 정보로 추가
            try:
                fallback_doc = DocumentInfo(
                    source_id=str(doc_id) if doc_id else f"doc_{i}",
                    title=metadata.get("title", metadata.get("subject", f"Document {i+1}")) if metadata else f"Document {i+1}",
                    content=doc[:200] + "..." if len(doc) > 200 else doc,
                    relevance_score=max(0.0, (2.0 - distance) / 2.0),
                    doc_type="unknown"
                )
                document_list.append(fallback_doc)
                logger.info(f"문서 {i} fallback 변환 성공")
            except Exception as fallback_error:
                logger.error(f"문서 {i} fallback 변환도 실패: {fallback_error}")
            continue
    
    return document_list
