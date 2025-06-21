"""
응답 생성 관련 라우트
"""

import time
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from ..models.requests import GenerateReplyRequest
from ..models.responses import GenerateReplyResponse
from ..models.shared import DocumentInfo
from ..dependencies import get_company_id, get_platform, get_vector_db, get_llm_router

# 로거 설정
logger = logging.getLogger(__name__)

# 라우터 생성
router = APIRouter(prefix="", tags=["reply"])

# 전역 변수들 (의존성 주입으로 대체 예정)
ticket_context_cache = {}

async def get_context_cache():
    """컨텍스트 캐시 의존성"""
    return ticket_context_cache

@router.post("/reply", response_model=GenerateReplyResponse)
async def reply(
    request: GenerateReplyRequest,
    company_id: str = Depends(get_company_id),
    platform: str = Depends(get_platform),
    vector_db = Depends(get_vector_db),
    llm_router = Depends(get_llm_router),
    context_cache: Dict = Depends(get_context_cache)
):
    """
    고객 지원 티켓에 대한 응답을 생성하는 엔드포인트
    
    이 엔드포인트는 초기화된 티켓 컨텍스트를 기반으로 응답을 생성합니다.
    자연어 텍스트 기반 응답이 반환됩니다.
    
    Args:
        request: 응답 생성 요청
        company_id: 회사 ID (의존성 주입)
        platform: 플랫폼 (의존성 주입)
        vector_db: 벡터 데이터베이스 (의존성 주입)
        llm_router: LLM 라우터 (의존성 주입)
        context_cache: 컨텍스트 캐시 (의존성 주입)
        
    Returns:
        생성된 응답 텍스트 및 참조 문서
    """
    # 성능 측정 시작
    start_time = time.time()
    
    # 컨텍스트 ID 확인
    context_id = request.context_id
    if not context_id or context_id not in context_cache:
        raise HTTPException(
            status_code=404,
            detail=f"컨텍스트를 찾을 수 없습니다. context_id: {context_id}. /init 엔드포인트를 먼저 호출해주세요."
        )
    
    # 캐시에서 컨텍스트 검색
    context = context_cache[context_id]
    ticket_id = context["ticket_id"]
    ticket_data = context["ticket_data"]
    similar_tickets = context["similar_tickets"]
    kb_documents = context["kb_documents"]
    
    logger.info(f"티켓 ID {ticket_id}에 대한 응답 생성 시작")
    
    # 티켓 메타데이터 추출
    ticket_metadata = ticket_data.get("metadata", {})
    ticket_title = ticket_metadata.get("subject", f"티켓 ID {ticket_id}")
    ticket_body = ticket_metadata.get("text", ticket_metadata.get("description_text", "티켓 본문 정보 없음"))
    
    # 대화 추출
    raw_conversations = ticket_metadata.get("conversations", [])
    ticket_conversations = []
    
    if isinstance(raw_conversations, list):
        for conv in raw_conversations:
            if isinstance(conv, dict):
                body = conv.get("body_text", conv.get("body", ""))
                if body:
                    ticket_conversations.append(body)
            elif isinstance(conv, str):
                ticket_conversations.append(conv)
    elif isinstance(raw_conversations, str):
        ticket_conversations = [raw_conversations]
    
    if not ticket_conversations and ticket_metadata.get("conversation_summary"):
        ticket_conversations = [ticket_metadata["conversation_summary"]]
    
    # 컨텍스트 구축 (최적화된 컨텍스트 빌더 사용)
    context_start_time = time.time()
    
    # 티켓 기본 컨텍스트
    ticket_context = f"""티켓 제목: {ticket_title}

티켓 내용:
{ticket_body}

대화 내역:
{' '.join(ticket_conversations[:3])}  # 처음 3개 대화만 포함
"""
    
    # 문서들과 메타데이터 준비 (최적화된 컨텍스트 빌더를 위해)
    context_docs = []
    context_metadatas = []
    
    # 유사 티켓을 문서로 변환
    for idx, ticket in enumerate(similar_tickets[:5]):
        ticket_text = ""
        if isinstance(ticket, dict):
            metadata = ticket.get("metadata", {})
            ticket_text = f"제목: {metadata.get('subject', 'N/A')}\n"
            ticket_text += f"내용: {metadata.get('text', metadata.get('description_text', 'N/A'))}"
            context_docs.append(ticket_text)
            context_metadatas.append({
                "doc_type": "similar_ticket",
                "source": f"유사 티켓 {idx + 1}",
                "title": metadata.get('subject', 'N/A')
            })
    
    # 지식베이스 문서를 문서로 변환
    for idx, doc in enumerate(kb_documents[:5]):
        doc_text = ""
        if isinstance(doc, dict):
            metadata = doc.get("metadata", {})
            doc_text = f"제목: {metadata.get('title', 'N/A')}\n"
            doc_text += f"내용: {metadata.get('text', metadata.get('description', 'N/A'))}"
            context_docs.append(doc_text)
            context_metadatas.append({
                "doc_type": "kb_document", 
                "source": f"지식베이스 문서 {idx + 1}",
                "title": metadata.get('title', 'N/A')
            })
    
    # 최적화된 컨텍스트 구성 (쿼리는 티켓 제목으로 설정)
    from ..core.context_builder import build_optimized_context  # 로컬 임포트
    
    query_for_context = f"{ticket_title} {ticket_body[:200]}"  # 티켓 정보를 쿼리로 사용
    
    optimized_context = ""
    context_meta = {}
    
    if context_docs:
        optimized_context, optimized_metadatas, context_meta = build_optimized_context(
            docs=context_docs,
            metadatas=context_metadatas,
            query=query_for_context,
            max_tokens=6000,
            top_k=8,
            enable_relevance_extraction=True
        )
    
    # 스타일과 톤 지침
    style_guide = {
        "professional": "전문적이고 격식 있는 언어를 사용하세요.",
        "friendly": "친근하고 대화체로 응답하세요.",
        "technical": "기술적 용어와 자세한 설명을 포함하세요."
    }
    
    tone_guide = {
        "helpful": "도움을 주는 태도로 응답하세요.",
        "empathetic": "고객의 감정에 공감하는 태도로 응답하세요.",
        "direct": "간결하고 직접적으로 핵심 정보를 제공하세요."
    }
    
    style_instruction = style_guide.get(request.style or "professional", style_guide["professional"])
    tone_instruction = tone_guide.get(request.tone or "helpful", tone_guide["helpful"])
    
    # 프롬프트 구성 (최적화된 컨텍스트 사용)
    prompt = f"""다음 고객 지원 티켓에 대한 응답을 생성해주세요.

[티켓 정보]
{ticket_context}

[참고 자료]
{optimized_context}

[응답 지침]
1. {style_instruction}
2. {tone_instruction}"""

    if request.instructions:
        prompt += f"\n3. {request.instructions}"
        
    if request.include_greeting:
        prompt += "\n4. 적절한 인사말로 응답을 시작하세요."
        
    if request.include_signature:
        prompt += "\n5. 응답 끝에 적절한 서명을 포함하세요."
        
    prompt += """
6. 필요한 경우 각 문단마다 참고한 문서 출처를 표시해주세요 (예: "~입니다. (출처: 문서 제목)")

이제 위 정보를 바탕으로 고객에게 보낼 응답을 생성해주세요. 응답은 명확하게 구분된 단락으로 구성해주세요.
"""
    
    context_time = time.time() - context_start_time
    
    # LLM 호출
    llm_start_time = time.time()
    try:
        system_prompt = f"당신은 {company_id} 회사의 전문적인 고객 지원 담당자입니다. 정확하고 도움이 되는 응답을 제공하세요."
        # 실시간 상담원 쿼리용으로 용도 지정하여 호출
        response = await llm_router.generate(
            prompt=prompt, 
            system_prompt=system_prompt,
            use_case="realtime"  # 실시간 상담원 쿼리용 모델 사용
        )
        llm_time = time.time() - llm_start_time
        
        # 응답 텍스트 정리
        reply_text = response.text.strip()
        
        # 총 처리 시간
        total_time = time.time() - start_time
        
        # 메타데이터 구성 (최적화 정보 포함)
        metadata = {
            "duration_ms": int(total_time * 1000),
            "context_time_ms": int(context_time * 1000),
            "llm_time_ms": int(llm_time * 1000),
            "model_used": response.model_used,
            "paragraph_count": len(reply_text.split("\n\n")),
            "context_optimization": context_meta,
            "token_count": context_meta.get("token_count", 0),
            "optimized_docs_count": context_meta.get("final_optimized_docs_count", 0)
        }
        
        # 결과 반환
        return GenerateReplyResponse(
            reply_text=reply_text,
            context_docs=kb_documents + similar_tickets,
            metadata=metadata
        )
        
    except Exception as e:
        logger.error(f"응답 생성 중 오류 발생: {str(e)}")
        # 오류 발생 시 오류 메시지가 포함된 응답 반환
        error_message = f"응답 생성 중 오류가 발생했습니다: {str(e)}"
        
        return GenerateReplyResponse(
            reply_text=error_message,
            context_docs=kb_documents + similar_tickets,
            metadata={"error": str(e)}
        )


@router.post("/reply/stream")
async def reply_stream(
    request: GenerateReplyRequest,
    company_id: str = Depends(get_company_id),
    platform: str = Depends(get_platform),
    vector_db = Depends(get_vector_db),
    llm_router = Depends(get_llm_router),
    context_cache: Dict = Depends(get_context_cache)
):
    """
    스트리밍 방식으로 응답을 생성하는 엔드포인트
    실시간으로 응답을 생성하여 프론트엔드에서 점진적으로 표시할 수 있습니다.
    
    Args:
        request: 응답 생성 요청
        company_id: 회사 ID (의존성 주입)
        platform: 플랫폼 (의존성 주입)
        vector_db: 벡터 데이터베이스 (의존성 주입)
        llm_router: LLM 라우터 (의존성 주입)
        context_cache: 컨텍스트 캐시 (의존성 주입)
        
    Returns:
        StreamingResponse: 스트리밍 응답
    """
    async def generate_streaming_response() -> AsyncGenerator[str, None]:
        try:
            # 컨텍스트 ID 확인
            context_id = request.context_id
            if not context_id or context_id not in context_cache:
                yield f"data: {{'error': '컨텍스트를 찾을 수 없습니다. context_id: {context_id}'}}\n\n"
                return
            
            # 캐시에서 컨텍스트 검색
            context = context_cache[context_id]
            ticket_id = context["ticket_id"]
            ticket_data = context["ticket_data"]
            similar_tickets = context["similar_tickets"]
            kb_documents = context["kb_documents"]
            
            yield f"data: {{'status': 'processing', 'message': '응답 생성을 시작합니다...'}}\n\n"
            
            # 티켓 메타데이터 추출 (reply 엔드포인트와 동일한 로직)
            ticket_metadata = ticket_data.get("metadata", {})
            ticket_title = ticket_metadata.get("subject", f"티켓 ID {ticket_id}")
            ticket_body = ticket_metadata.get("text", ticket_metadata.get("description_text", "티켓 본문 정보 없음"))
            
            # 대화 추출
            raw_conversations = ticket_metadata.get("conversations", [])
            ticket_conversations = []
            
            if isinstance(raw_conversations, list):
                for conv in raw_conversations:
                    if isinstance(conv, dict):
                        body = conv.get("body_text", conv.get("body", ""))
                        if body:
                            ticket_conversations.append(body)
                    elif isinstance(conv, str):
                        ticket_conversations.append(conv)
            elif isinstance(raw_conversations, str):
                ticket_conversations = [raw_conversations]
            
            if not ticket_conversations and ticket_metadata.get("conversation_summary"):
                ticket_conversations = [ticket_metadata["conversation_summary"]]
            
            yield f"data: {{'status': 'context_building', 'message': '컨텍스트를 구성하고 있습니다...'}}\n\n"
            
            # 컨텍스트 구축 (reply 엔드포인트와 동일한 로직)
            ticket_context = f"""티켓 제목: {ticket_title}

티켓 내용:
{ticket_body}

대화 내역:
{' '.join(ticket_conversations[:3])}
"""
            
            # 문서들과 메타데이터 준비
            context_docs = []
            context_metadatas = []
            
            # 유사 티켓을 문서로 변환
            for idx, ticket in enumerate(similar_tickets[:5]):
                ticket_text = ""
                if isinstance(ticket, dict):
                    metadata = ticket.get("metadata", {})
                    ticket_text = f"제목: {metadata.get('subject', 'N/A')}\n"
                    ticket_text += f"내용: {metadata.get('text', metadata.get('description_text', 'N/A'))}"
                    context_docs.append(ticket_text)
                    context_metadatas.append({
                        "doc_type": "similar_ticket",
                        "source": f"유사 티켓 {idx + 1}",
                        "title": metadata.get('subject', 'N/A')
                    })
            
            # 지식베이스 문서를 문서로 변환
            for idx, doc in enumerate(kb_documents[:5]):
                doc_text = ""
                if isinstance(doc, dict):
                    metadata = doc.get("metadata", {})
                    doc_text = f"제목: {metadata.get('title', 'N/A')}\n"
                    doc_text += f"내용: {metadata.get('text', metadata.get('description', 'N/A'))}"
                    context_docs.append(doc_text)
                    context_metadatas.append({
                        "doc_type": "kb_document", 
                        "source": f"지식베이스 문서 {idx + 1}",
                        "title": metadata.get('title', 'N/A')
                    })
            
            # 최적화된 컨텍스트 구성
            from ..core.context_builder import build_optimized_context  # 로컬 임포트
            
            query_for_context = f"{ticket_title} {ticket_body[:200]}"
            
            optimized_context = ""
            context_meta = {}
            
            if context_docs:
                optimized_context, optimized_metadatas, context_meta = build_optimized_context(
                    docs=context_docs,
                    metadatas=context_metadatas,
                    query=query_for_context,
                    max_tokens=6000,
                    top_k=8,
                    enable_relevance_extraction=True
                )
            
            yield f"data: {{'status': 'llm_calling', 'message': 'AI 모델에 응답을 요청하고 있습니다...'}}\n\n"
            
            # 스타일과 톤 지침 (reply 엔드포인트와 동일)
            style_guide = {
                "professional": "전문적이고 격식 있는 언어를 사용하세요.",
                "friendly": "친근하고 대화체로 응답하세요.",
                "technical": "기술적 용어와 자세한 설명을 포함하세요."
            }
            
            tone_guide = {
                "helpful": "도움을 주는 태도로 응답하세요.",
                "empathetic": "고객의 감정에 공감하는 태도로 응답하세요.",
                "direct": "간결하고 직접적으로 핵심 정보를 제공하세요."
            }
            
            style_instruction = style_guide.get(request.style or "professional", style_guide["professional"])
            tone_instruction = tone_guide.get(request.tone or "helpful", tone_guide["helpful"])
            
            # 프롬프트 구성
            prompt = f"""다음 고객 지원 티켓에 대한 응답을 생성해주세요.

[티켓 정보]
{ticket_context}

[참고 자료]
{optimized_context}

[응답 지침]
1. {style_instruction}
2. {tone_instruction}"""

            if request.instructions:
                prompt += f"\n3. {request.instructions}"
                
            if request.include_greeting:
                prompt += "\n4. 적절한 인사말로 응답을 시작하세요."
                
            if request.include_signature:
                prompt += "\n5. 응답 끝에 적절한 서명을 포함하세요."
                
            prompt += """
6. 필요한 경우 각 문단마다 참고한 문서 출처를 표시해주세요 (예: "~입니다. (출처: 문서 제목)")

이제 위 정보를 바탕으로 고객에게 보낼 응답을 생성해주세요. 응답은 명확하게 구분된 단락으로 구성해주세요.
"""
            
            # 스트리밍 LLM 호출
            system_prompt = f"당신은 {company_id} 회사의 전문적인 고객 지원 담당자입니다. 정확하고 도움이 되는 응답을 제공하세요."
            
            # 응답 텍스트 누적용
            full_response = ""
            
            async for chunk in llm_router.generate_stream(prompt, system_prompt=system_prompt):
                if chunk.strip():
                    full_response += chunk
                    # 실시간으로 청크 전송
                    escaped_chunk = chunk.replace('\n', '\\n').replace('"', '\\"')
                    yield f"data: {{'type': 'chunk', 'content': '{escaped_chunk}'}}\n\n"
            
            # 완료 신호 전송
            escaped_response = full_response.replace('\n', '\\n').replace('"', '\\"')
            yield f"data: {{'type': 'complete', 'full_response': '{escaped_response}', 'metadata': {{'docs_count': {len(context_docs)}, 'optimization': {context_meta}}}}}\n\n"
            
        except Exception as e:
            logger.error(f"스트리밍 응답 생성 중 오류 발생: {str(e)}")
            yield f"data: {{'error': '응답 생성 중 오류가 발생했습니다: {str(e)}'}}\n\n"
    
    return StreamingResponse(
        generate_streaming_response(),
        media_type="text/plain",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
    )
