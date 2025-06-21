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
    get_company_id,
    get_platform,
    get_vector_db,
    get_fetcher,
    get_llm_router,
    get_hybrid_search_manager
)
from ..models.requests import QueryRequest
from ..models.responses import QueryResponse
from ..models.shared import DocumentInfo

# 로거
import logging
logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/query", response_model=QueryResponse)
# @cached(cache, key=partial(_query_cache_key, "query_endpoint"))  # 캐시는 나중에 추가
async def query_endpoint(
    req: QueryRequest,
    company_id: str = Depends(get_company_id),
    platform: str = Depends(get_platform),
    vector_db = Depends(get_vector_db),
    fetcher = Depends(get_fetcher),
    llm_router = Depends(get_llm_router),
    hybrid_search_manager = Depends(get_hybrid_search_manager)  # 하이브리드 검색 매니저 추가
):
    """
    사용자 쿼리에 대한 AI 응답을 생성하는 엔드포인트 (멀티플랫폼 지원)

    Args:
        req: 쿼리 요청 객체 (QueryRequest)
        company_id: 회사 ID (의존성 함수를 통해 헤더에서 자동 추출)
        platform: 플랫폼 (X-Platform, X-Freshdesk-Domain,
                  X-Zendesk-Domain 헤더에서 자동 추출)

    Returns:
        검색 결과와 AI 응답을 포함한 QueryResponse 객체
    """
    # 성능 측정을 시작합니다.
    start_time = time.time()
    
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
            company_id=company_id,
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
    
    # 하이브리드 검색 활성화 여부 확인
    if req.use_hybrid_search:
        logger.info(f"하이브리드 검색 활성화: {effective_platform}")
        
        # 하이브리드 검색 실행
        hybrid_results = await hybrid_search_manager.hybrid_search(
            query=req.query,
            company_id=company_id,
            platform=effective_platform,
            top_k=req.top_k,
            doc_types=req.search_types or ["ticket", "kb"],
            custom_fields=req.custom_fields,
            search_filters=req.search_filters,
            enable_intent_analysis=req.enable_intent_analysis,
            enable_llm_enrichment=req.enable_llm_enrichment,
            rerank_results=req.rerank_results,
            ticket_context=ticket_context_for_query if req.ticket_id else None
        )
        
        # 하이브리드 검색 결과에서 기존 형식으로 변환
        docs = hybrid_results["documents"]
        metadatas = hybrid_results["metadatas"] 
        distances = hybrid_results["distances"]
        
        # 추가 정보 저장
        search_analysis = hybrid_results.get("search_analysis", {})
        custom_field_matches = hybrid_results.get("custom_field_matches", [])
        llm_insights = hybrid_results.get("llm_insights", {})
        search_quality_score = hybrid_results.get("search_quality_score", 0.0)
        
        logger.info(f"하이브리드 검색 완료: {len(docs)} 문서, 품질점수: {search_quality_score:.3f}")
        
    else:
        # 기존 벡터 검색 로직 유지
        # 임베딩 생성 (TODO: embed_documents 함수를 llm_router에서 가져와야 함)
        # query_embedding = embed_documents([query_for_embedding_str])[0]
        query_embedding = await llm_router.generate_embedding(
            query_for_embedding_str
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
            # TODO: retrieve_top_k_docs 함수를 vector_db에서 가져와야 함
            ticket_results = vector_db.retrieve_top_k_docs(
                query_embedding,
                top_k_per_type,
                company_id,
                doc_type="ticket",
                platform=effective_platform
            )
            logger.info(
                f"플랫폼 {effective_platform} 티켓 검색 결과: "
                f"{len(ticket_results.get('documents', []))} 건"
            )
        
        # 지식베이스 문서 검색 (콘텐츠 타입에 "solutions"가 포함된 경우만)
        kb_results = {
            "documents": [], "metadatas": [], "ids": [], "distances": []
        }
        if "solutions" in content_types:
            kb_results = vector_db.retrieve_top_k_docs(
                query_embedding,
                top_k_per_type,
                company_id,
                doc_type="kb",
                platform=effective_platform
            )
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
    # 새로운 최적화 매개변수들을 활용하여 품질과 성능을 향상시킵니다.
    # TODO: build_optimized_context 함수를 llm_router에서 가져와야 함
    base_context, optimized_metadatas, context_meta = await llm_router.build_optimized_context(
        docs=docs,
        metadatas=metadatas,
        query=req.query,  # 쿼리 기반 관련성 추출을 위해 전달
        max_tokens=8000,  # 컨텍스트 토큰 제한 (기본값 사용 가능)
        top_k=req.top_k,  # 품질 기반 문서 선별
        enable_relevance_extraction=True  # 관련성 추출 활성화
    )
    
    # LLM에 전달할 최종 컨텍스트 (티켓 정보 + 검색된 문서 정보)
    final_context_for_llm = f"{ticket_context_for_llm}{base_context}"
    
    # TODO: build_prompt 함수를 llm_router에서 가져와야 함
    prompt = await llm_router.build_prompt(final_context_for_llm, req.query, answer_instructions=req.answer_instructions)
    
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

        doc_info = DocumentInfo(
            title=title,
            content=content,
            source_id=metadata_item.get("source_id", metadata_item.get("id", "")),
            source_url=metadata_item.get("source_url", ""),
            relevance_score=relevance_score,
            doc_type=doc_type
        )
        structured_docs.append(doc_info)
    
    context_time = time.time() - context_start

    context_images = []
    # 콘텐츠 타입에 "images" 또는 "attachments"가 포함된 경우만 이미지 정보 추출
    if any(t in ["images", "attachments"] for t in content_types):
        for i, metadata in enumerate(optimized_metadatas): # optimized_metadatas 사용
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
                                    "source_type": img.get("source_type", ""),
                                    "source_id": metadata.get("source_id", ""),
                                    "title": (
                                        structured_docs[i].title
                                        if i < len(structured_docs)
                                        else ""
                                    ),
                                }
                            )
                except Exception as e:
                    logger.error(f"이미지 정보 파싱 중 오류 발생: {e}") # 오류 로깅 메시지를 한글로 변경합니다.

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
        response = await llm_router.generate(
            prompt=prompt, 
            system_prompt=system_prompt,
            use_case="realtime"  # 실시간 상담원 쿼리용 모델 사용
        )
        answer = response.text
        
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
        f"성능: company_id='{company_id}', query='{req.query[:50]}...', "
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
        "model_used": response.model_used, # 사용된 LLM 모델
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
        metadata=metadata,
        # 하이브리드 검색 결과 추가
        search_analysis=search_analysis if req.use_hybrid_search else None,
        custom_field_matches=custom_field_matches if req.use_hybrid_search else None,
        llm_insights=llm_insights if req.use_hybrid_search else None,
        search_quality_score=search_quality_score if req.use_hybrid_search else None
    )


@router.post("/query/stream")
async def query_stream(
    req: QueryRequest, 
    company_id: str = Depends(get_company_id),
    platform: str = Depends(get_platform),
    vector_db = Depends(get_vector_db),
    llm_router = Depends(get_llm_router)
):
    """
    스트리밍 방식으로 쿼리 응답을 제공하는 엔드포인트
    실시간으로 검색 결과를 스트리밍하여 프론트엔드에서 점진적으로 표시할 수 있습니다.
    """
    async def generate_streaming_response():
        try:
            # 기본 쿼리 처리
            yield f"data: {json.dumps({'type': 'status', 'message': '검색을 시작합니다...', 'progress': 10})}\n\n"
            
            # 임베딩 생성
            yield f"data: {json.dumps({'type': 'status', 'message': '쿼리 분석 중...', 'progress': 30})}\n\n"
            query_embedding = await llm_router.generate_embedding(req.query)
            
            # 검색 실행
            yield f"data: {json.dumps({'type': 'status', 'message': '관련 문서 검색 중...', 'progress': 50})}\n\n"
            
            # 유사한 티켓 검색
            if req.include_similar_tickets:
                similar_tickets_result = vector_db.retrieve_top_k_docs(
                    query_embedding=query_embedding,
                    top_k=req.top_k_tickets,
                    doc_type="ticket",
                    company_id=company_id,
                    platform=platform
                )
                
                # 결과를 스트리밍으로 전송
                for i, ticket in enumerate(similar_tickets_result.get("metadatas", [])):
                    ticket_data = {
                        'type': 'ticket',
                        'id': similar_tickets_result["ids"][i],
                        'title': ticket.get("subject", "제목 없음"),
                        'content': similar_tickets_result["documents"][i][:200] + "...",
                        'progress': 50 + (i / len(similar_tickets_result.get("metadatas", []))) * 25
                    }
                    yield f"data: {json.dumps(ticket_data)}\n\n"
            
            # KB 문서 검색
            yield f"data: {json.dumps({'type': 'status', 'message': 'KB 문서 검색 중...', 'progress': 75})}\n\n"
            
            kb_result = vector_db.retrieve_top_k_docs(
                query_embedding=query_embedding,
                top_k=req.top_k_kb,
                doc_type="kb",
                company_id=company_id,
                platform=platform
            )
            
            # KB 결과를 스트리밍으로 전송
            for i, kb_doc in enumerate(kb_result.get("metadatas", [])):
                kb_data = {
                    'type': 'kb',
                    'id': kb_result["ids"][i],
                    'title': kb_doc.get("title", "제목 없음"),
                    'content': kb_result["documents"][i][:200] + "...",
                    'progress': 75 + (i / len(kb_result.get("metadatas", []))) * 20
                }
                yield f"data: {json.dumps(kb_data)}\n\n"
            
            # 완료
            yield f"data: {json.dumps({'type': 'complete', 'message': '검색이 완료되었습니다.', 'progress': 100})}\n\n"
            
        except Exception as e:
            logger.error(f"스트리밍 쿼리 중 오류: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': f'오류가 발생했습니다: {str(e)}'})}\n\n"

    return StreamingResponse(
        generate_streaming_response(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*"
        }
    )


@router.post("/query/hybrid", response_model=QueryResponse)
async def hybrid_query_endpoint(
    req: QueryRequest,
    company_id: str = Depends(get_company_id),
    platform: str = Depends(get_platform),
    hybrid_search_manager = Depends(get_hybrid_search_manager)
):
    """
    하이브리드 검색 전용 엔드포인트
    
    벡터 검색 + SQL 검색 + LLM 기반 인사이트를 결합한 고급 검색 기능을 제공합니다.
    커스텀 필드 검색, 의도 분석, LLM 컨텍스트 강화 등을 지원합니다.
    
    Args:
        req: 쿼리 요청 객체 (QueryRequest)
        company_id: 회사 ID
        platform: 플랫폼
        
    Returns:
        하이브리드 검색 결과를 포함한 QueryResponse 객체
    """
    start_time = time.time()
    effective_platform = req.platform or platform
    
    logger.info(
        f"하이브리드 검색 요청: platform={effective_platform}, "
        f"query='{req.query[:100]}...', custom_fields={req.custom_fields}, "
        f"search_filters={req.search_filters}"
    )
    
    try:
        # 하이브리드 검색 실행
        hybrid_results = await hybrid_search_manager.hybrid_search(
            query=req.query,
            company_id=company_id,
            platform=effective_platform,
            top_k=req.top_k,
            doc_types=req.search_types or ["ticket", "kb"],
            custom_fields=req.custom_fields,
            search_filters=req.search_filters,
            enable_intent_analysis=req.enable_intent_analysis,
            enable_llm_enrichment=req.enable_llm_enrichment,
            rerank_results=req.rerank_results,
            min_similarity=req.min_similarity
        )
        
        # 문서 정보 구조화
        structured_docs = []
        for i, (doc_content, metadata, distance) in enumerate(zip(
            hybrid_results["documents"], 
            hybrid_results["metadatas"], 
            hybrid_results["distances"]
        )):
            title = metadata.get("title", metadata.get("subject", ""))
            content = doc_content
            doc_type = metadata.get("source_type", metadata.get("doc_type", "unknown"))
            
            # 제목과 내용 파싱
            lines = doc_content.split("\\n", 2)
            if len(lines) > 0 and lines[0].startswith("제목:"):
                title = lines[0].replace("제목:", "").strip()
                if len(lines) > 1:
                    content = "\\n".join(lines[1:]).strip()
                    if content.startswith("설명:"):
                        content = content.replace("설명:", "", 1).strip()
            
            # 유사도 점수 계산 (거리를 백분율로 변환)
            relevance_score = round(((2 - distance) / 2) * 100, 1) if distance <= 2 else 0.0
            
            doc_info = DocumentInfo(
                title=title,
                content=content,
                source_id=metadata.get("source_id", metadata.get("id", "")),
                source_url=metadata.get("source_url", ""),
                relevance_score=relevance_score,
                doc_type=doc_type
            )
            structured_docs.append(doc_info)
        
        # 총 처리 시간
        total_time = time.time() - start_time
        
        # 메타데이터 구성
        metadata = {
            "duration_ms": int(total_time * 1000),
            "search_method": "hybrid",
            "documents_found": len(structured_docs),
            "search_quality_score": hybrid_results.get("search_quality_score", 0.0),
            "intent_detected": hybrid_results.get("search_analysis", {}).get("intent", "unknown"),
            "custom_field_matches": len(hybrid_results.get("custom_field_matches", [])),
            "llm_enrichment_enabled": req.enable_llm_enrichment,
            "rerank_enabled": req.rerank_results
        }
        
        logger.info(
            f"하이브리드 검색 완료: {len(structured_docs)} 문서, "
            f"품질점수: {hybrid_results.get('search_quality_score', 0.0):.3f}, "
            f"소요시간: {total_time:.2f}s"
        )
        
        return QueryResponse(
            answer=hybrid_results.get("enhanced_response", "하이브리드 검색이 완료되었습니다."),
            context_docs=structured_docs,
            context_images=[],
            metadata=metadata,
            search_analysis=hybrid_results.get("search_analysis"),
            custom_field_matches=hybrid_results.get("custom_field_matches"),
            llm_insights=hybrid_results.get("llm_insights"),
            search_quality_score=hybrid_results.get("search_quality_score")
        )
        
    except Exception as e:
        logger.error(f"하이브리드 검색 중 오류 발생: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"하이브리드 검색 중 오류가 발생했습니다: {str(e)}"
        )
