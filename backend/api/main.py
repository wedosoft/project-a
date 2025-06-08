"""
Freshdesk Custom App 백엔드 서비스

이 프로젝트는 Freshdesk Custom App(Prompt Canvas)을 위한 백엔드 서비스입니다.
RAG(Retrieval-Augmented Generation) 기술을 활용하여 Freshdesk 티켓과 지식베이스를 기반으로
AI 기반 응답 생성 기능을 제공합니다.
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime
from functools import partial
from typing import Any, Dict, List, Optional

import prometheus_client
from cachetools import TTLCache, cached
from cachetools.keys import hashkey
from core import llm_router, retriever
from core.context_builder import build_optimized_context
from core.embedder import embed_documents
from core.llm_router import LLMResponse, generate_text
from core.retriever import retrieve_top_k_docs
from core.vectordb import vector_db
from fastapi import Depends, FastAPI, Header, HTTPException
from freshdesk import fetcher
from pydantic import BaseModel, Field, field_validator

# 첨부파일 API 라우터 import
from api.attachments import router as attachments_router

# Prometheus 메트릭 정의
# LLM 관련 메트릭은 llm_router.py에서 정의되어 있으므로 중복 방지를 위해 여기서는 HTTP 요청 관련 메트릭만 정의
# HTTP 요청 관련 메트릭은 필요시 추후 추가 가능
# 현재는 /metrics 엔드포인트만 제공하여 llm_router에서 수집된 메트릭을 노출

# FastAPI 앱 생성
app = FastAPI()

# 첨부파일 라우터 등록
app.include_router(attachments_router)

# 인메모리 캐시 설정 (TTL: 10분, 최대 100개 항목)
# 회사 ID와 요청 매개변수를 기반으로 캐시 키를 생성합니다.
cache = TTLCache(maxsize=100, ttl=600)

# 성능 로깅을 위한 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)



# 티켓 초기화 컨텍스트 캐시 (티켓 ID를 키로 사용)
ticket_context_cache = TTLCache(maxsize=1000, ttl=3600)  # 1시간 유효


# 요청/응답 모델 정의를 _query_cache_key 함수보다 위로 이동
class QueryRequest(BaseModel):
    query: str
    top_k: int = 3
    answer_instructions: Optional[str] = None  # 사용자가 제공하는 답변 지침
    ticket_id: Optional[str] = None # 현재 처리 중인 티켓 ID (선택 사항)
    type: List[str] = Field(default_factory=lambda: ["tickets", "solutions", "images", "attachments"])  # 검색할 콘텐츠 타입
    intent: Optional[str] = "search"  # 검색 의도 (예: "search", "recommend", "answer")
    company_id: Optional[str] = None  # 회사 ID (헤더에서 가져오는 경우 선택 사항)
    search_types: Optional[List[str]] = Field(default_factory=lambda: ["ticket", "kb"])  # 검색할 데이터 타입
    min_similarity: float = 0.5  # 최소 유사도 임계값


# 회사 ID 의존성 함수
async def get_company_id(
    x_company_id: Optional[str] = Header(None, alias="X-Company-ID")
) -> str:
    """
    현재 사용자의 회사 ID를 반환합니다.
    X-Company-ID 헤더가 제공되지 않으면 "default" 값을 사용합니다.
    실제 환경에서는 인증 토큰에서 추출하는 방식으로 변경해야 합니다.
    """
    if not x_company_id:
        # X-Company-ID 헤더가 없으면 기본값 "default" 사용
        return "default"
    return x_company_id


# 캐시 키 생성을 위한 헬퍼 함수
def _query_cache_key(func_name: str, req: QueryRequest, company_id: str):
    # 함수 이름, 회사 ID, 쿼리 내용, top_k, 답변 지침, 티켓 ID를 기반으로 해시 키를 생성합니다.
    return hashkey(func_name, company_id, req.query, req.top_k, req.answer_instructions, req.ticket_id)


class DocumentInfo(BaseModel):
    """검색된 문서 정보를 담는 모델"""

    title: str
    content: str
    source_id: str = ""
    source_url: str = ""  # 빈 문자열을 기본값으로 설정
    relevance_score: float = 0.0
    doc_type: Optional[str] = None # 문서 타입을 명시 (예: "ticket", "kb", "faq")
    
    @field_validator('source_url')
    def ensure_source_url_is_str(cls, v):
        """URL이 None이면 빈 문자열로 변환"""
        return v or ""


# 블록 기반 응답 형식을 위한 모델
class Source(BaseModel):
    """출처 정보"""

    title: str = ""
    url: str = ""


# --- 티켓 요약에 대한 모델 ---
class TicketSummaryContent(BaseModel):
    """티켓 요약을 위한 통합 모델"""
    ticket_summary: str = Field(description="티켓의 전체 요약")  # summary → ticket_summary로 필드명 변경 (일관성)
    key_points: List[str] = Field(default_factory=list, description="주요 포인트 목록")
    sentiment: str = Field(default="중립적", description="감정 분석 결과 (긍정적, 중립적, 부정적)")
    priority_recommendation: Optional[str] = Field(default=None, description="권장 우선순위")
    category_suggestion: Optional[List[str]] = Field(default=None, description="추천 카테고리")
    customer_summary: Optional[str] = Field(default=None, description="고객 관련 주요 내용 요약")
    request_summary: Optional[str] = Field(default=None, description="고객의 주요 요청 사항 요약")
    urgency_level: Optional[str] = Field(default=None, description="티켓의 긴급도 (예: 높음, 보통, 낮음)")


# 티켓 초기화 요청/응답 모델
class TicketInitRequest(BaseModel):
    """티켓 초기화 요청 모델"""
    
    ticket_id: str
    company_id: str
    include_summary: bool = True  # 티켓 요약 생성 여부
    include_kb_docs: bool = True  # 관련 지식베이스 문서 포함 여부
    include_similar_tickets: bool = True  # 유사 티켓 포함 여부


class InitResponse(BaseModel):
    """통합된 티켓 초기화 응답 모델"""
    
    ticket_id: str = Field(description="처리 대상 티켓의 ID")  # 처리된 티켓 ID
    ticket_data: Dict[str, Any] = Field(default_factory=dict, description="티켓 원본 데이터")  # 티켓 원본 데이터
    ticket_summary: Optional[TicketSummaryContent] = Field(default=None, description="티켓 요약 정보")  # 티켓 요약 정보
    similar_tickets: List[DocumentInfo] = Field(default_factory=list, description="유사 티켓 목록")  # 유사 티켓 정보
    kb_documents: List[DocumentInfo] = Field(default_factory=list, description="지식베이스 문서 목록")  # 관련 지식베이스 문서
    context_id: str = Field(description="컨텍스트 ID")  # 향후 요청을 위한 컨텍스트 ID 
    metadata: Dict[str, Any] = Field(default_factory=dict, description="메타데이터")  # 메타데이터


class QueryResponse(BaseModel):
    answer: str
    context_docs: List[DocumentInfo]
    context_images: List[dict] = []
    metadata: Dict[str, Any] = Field(default_factory=dict)


# FAQ 기능은 제거되었습니다 (2025.06.03)


def build_prompt(context: str, query: str, answer_instructions: Optional[str] = None) -> str:
    """
    LLM에 입력할 프롬프트를 생성합니다.
    
    Args:
        context: 검색된 문서 컨텍스트
        query: 사용자 질문
        answer_instructions: 사용자가 제공한 답변 지침
        
    Returns:
        LLM에 입력할 프롬프트
    """
    # 사용자 지정 지침이 있는 경우 추가합니다.
    instructions = ""
    if answer_instructions:
        instructions = f"""
[답변 지침]
{answer_instructions}
"""

    base_prompt = f"""
다음은 고객 지원 티켓에 대한 질문입니다. 아래의 참고 문서를 바탕으로 친절하고 명확하게 답변해 주세요.
{instructions}
[참고 문서]
{context}

[질문]
{query}

[답변]"""

    return base_prompt


async def call_llm(prompt: str, system_prompt: Optional[str] = None) -> LLMResponse:
    """
    LLM Router를 사용하여 답변을 생성합니다.
    여러 LLM 모델 간 자동 선택 및 fallback 기능을 제공합니다.
    """
    default_system = "당신은 친절한 고객 지원 AI입니다."
    system = default_system if system_prompt is None else system_prompt
    
    # LLM 호출 파라미터를 설정합니다.
    return await generate_text(
        prompt=prompt,
        system_prompt=system,
        max_tokens=1024,  # 최대 토큰 수 설정
        temperature=0.2 # 답변의 창의성 조절 (낮을수록 결정적)
    )





@app.get("/metrics")
async def metrics():
    return prometheus_client.generate_latest()


@app.post("/query", response_model=QueryResponse)
@cached(cache, key=partial(_query_cache_key, "query_endpoint"))
async def query_endpoint(req: QueryRequest, company_id: str = Depends(get_company_id)):
    """
    사용자 쿼리에 대한 AI 응답을 생성하는 엔드포인트
    
    Args:
        req: 쿼리 요청 객체 (QueryRequest)
        company_id: 회사 ID (의존성 함수를 통해 헤더에서 자동 추출)
        
    Returns:
        검색 결과와 AI 응답을 포함한 QueryResponse 객체
    """
    # 성능 측정을 시작합니다.
    start_time = time.time()
    
    # 검색 의도(intent) 처리
    search_intent = req.intent.lower() if req.intent else "search"
    logger.info(f"검색 의도: '{search_intent}', 검색 타입: {req.type}")
    
    # 콘텐츠 타입 필터링
    content_types = [t.lower() for t in req.type] if req.type else ["tickets", "solutions", "images", "attachments"]
    
    ticket_title = ""
    ticket_body = ""
    ticket_conversations = []
    ticket_context_for_query = ""
    ticket_context_for_llm = ""

    if req.ticket_id:
        logger.info(f"티켓 ID {req.ticket_id}에 대한 정보 조회를 시도합니다.")
        # doc_type='ticket'을 명시적으로 지정하여 예외 방지 및 일관성 확보
        ticket_data = vector_db.get_by_id(original_id_value=req.ticket_id, company_id=company_id, doc_type="ticket")
        
        if ticket_data and ticket_data.get("metadata"):
            metadata = ticket_data["metadata"]
            ticket_title = metadata.get("subject", f"티켓 ID {req.ticket_id} 관련 문의")
            # 본문은 'text' 필드를 우선 사용하고, 없다면 'description_text' 사용
            ticket_body = metadata.get("text", metadata.get("description_text", "티켓 본문 정보 없음"))
            # 대화 내용은 'conversations' 필드에서 가져오며, 리스트 형태를 기대
            raw_conversations = metadata.get("conversations", [])
            if isinstance(raw_conversations, list):
                ticket_conversations = [str(conv) for conv in raw_conversations] # 문자열로 변환
            elif isinstance(raw_conversations, str): # 문자열로 저장된 경우 (예: JSON 문자열)
                try:
                    parsed_convs = json.loads(raw_conversations)
                    if isinstance(parsed_convs, list):
                        ticket_conversations = [str(conv) for conv in parsed_convs]
                except json.JSONDecodeError:
                    ticket_conversations = [raw_conversations] # 파싱 실패 시 통째로 사용
            
            if not ticket_conversations and metadata.get("conversation_summary"): # 요약 필드가 있다면 활용
                 ticket_conversations = [str(metadata.get("conversation_summary"))]

            logger.info(f"티켓 ID {req.ticket_id} 정보 조회 완료: 제목='{ticket_title[:50]}...'")
        else:
            logger.warning(f"티켓 ID {req.ticket_id} 정보를 Qdrant에서 찾을 수 없거나 메타데이터가 없습니다.")
            ticket_title = f"티켓 ID {req.ticket_id} 정보 없음"
            ticket_body = "해당 티켓 정보를 찾을 수 없습니다."
            # ticket_conversations는 빈 리스트로 유지
        
        # 임베딩 및 검색을 위한 티켓 컨텍스트
        ticket_context_for_query = f"현재 티켓 제목: {ticket_title}\\n현재 티켓 본문: {ticket_body}\\n\\n대화 내용:\\n" + "\\n".join(ticket_conversations)
        # LLM 프롬프트에 포함될 티켓 컨텍스트
        ticket_context_for_llm = f"\\n[현재 티켓 정보]\\n제목: {ticket_title}\\n본문: {ticket_body}\\n대화 요약:\\n" + "\\n".join(ticket_conversations) + "\\n"

    search_start = time.time()
    # 1. 검색 단계: 사용자 쿼리를 임베딩하고 관련 문서를 검색합니다.
    # 티켓 ID가 있는 경우, 티켓 내용을 포함하여 임베딩할 쿼리 생성
    query_for_embedding_str = f"{ticket_context_for_query}\\n\\n사용자 질문: {req.query}" if req.ticket_id else req.query
    query_embedding = embed_documents([query_for_embedding_str])[0]
    
    # 콘텐츠 타입에 따라 검색할 문서 타입 결정
    top_k_per_type = max(1, req.top_k // len([t for t in content_types if t in ["tickets", "solutions"]]))
    
    # 티켓 검색 (콘텐츠 타입에 "tickets"가 포함된 경우만)
    ticket_results = {"documents": [], "metadatas": [], "ids": [], "distances": []}
    if "tickets" in content_types:
        ticket_results = retrieve_top_k_docs(
            query_embedding, 
            top_k_per_type, 
            company_id, 
            doc_type="ticket"
        )
        logger.info(f"티켓 검색 결과: {len(ticket_results.get('documents', []))} 건")
    
    # 지식베이스 문서 검색 (콘텐츠 타입에 "solutions"가 포함된 경우만)
    kb_results = {"documents": [], "metadatas": [], "ids": [], "distances": []}
    if "solutions" in content_types:
        kb_results = retrieve_top_k_docs(
            query_embedding, 
            top_k_per_type, 
            company_id, 
            doc_type="kb"
        )
        logger.info(f"솔루션 검색 결과: {len(kb_results.get('documents', []))} 건")

    # 검색 결과를 병합합니다.
    all_docs_content = ticket_results["documents"] + kb_results["documents"]
    all_metadatas = ticket_results["metadatas"] + kb_results["metadatas"]
    all_distances = ticket_results["distances"] + kb_results["distances"]
    
    # 통합된 결과를 유사도 기준으로 재정렬합니다 (거리가 작을수록 유사도가 높음).
    # 각 메타데이터에 doc_type을 명시적으로 추가합니다.
    for meta in ticket_results["metadatas"]:
        meta["source_type"] = "ticket"
    for meta in kb_results["metadatas"]:
        meta["source_type"] = "kb"
    # 문서 타입별 메타데이터 설정 완료

    combined = list(zip(all_docs_content, all_metadatas, all_distances))
    combined.sort(key=lambda x: x[2]) # 거리(distance) 기준으로 오름차순 정렬
    
    # 최대 top_k 개수만큼 잘라냅니다.
    final_top_k = req.top_k
    combined = combined[:final_top_k]
    
    # 다시 분리합니다.
    docs = [item[0] for item in combined]
    metadatas = [item[1] for item in combined]
    distances = [item[2] for item in combined] # 이 distances는 실제 거리 또는 1-score 값임
    
    search_time = time.time() - search_start
    
    # 2. 컨텍스트 최적화 단계: 검색된 문서를 LLM 입력에 적합하도록 가공합니다.
    context_start = time.time()
    
    # 최적화된 컨텍스트를 구성합니다. (검색된 문서들로부터)
    # 새로운 최적화 매개변수들을 활용하여 품질과 성능을 향상시킵니다.
    base_context, optimized_metadatas, context_meta = build_optimized_context(
        docs=docs, 
        metadatas=metadatas,
        query=req.query,  # 쿼리 기반 관련성 추출을 위해 전달
        max_tokens=8000,  # 컨텍스트 토큰 제한 (기본값 사용 가능)
        top_k=req.top_k,  # 품질 기반 문서 선별
        enable_relevance_extraction=True  # 관련성 추출 활성화
    )
    
    # LLM에 전달할 최종 컨텍스트 (티켓 정보 + 검색된 문서 정보)
    final_context_for_llm = f"{ticket_context_for_llm}{base_context}"
    
    prompt = build_prompt(final_context_for_llm, req.query, answer_instructions=req.answer_instructions)
    
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
                        # import json # 이미 최상단으로 이동
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
            
        response = await call_llm(prompt, system_prompt=system_prompt)
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
        f"성능: company_id=\'{company_id}\', query=\'{req.query[:50]}...\', "
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
        metadata=metadata
    )


# @app.post("/init") 엔드포인트는 @app.get("/init/{ticket_id}")로 통합되었습니다.
# 모든 기능은 GET 방식의 엔드포인트에서 제공됩니다.





# --- 통합된 Pydantic 모델 ---
# 티켓 요약에 대한 상세 정보를 담는 모델
class SimilarTicketItem(BaseModel):
    id: str = Field(description="유사 티켓의 ID")
    title: Optional[str] = Field(default=None, description="유사 티켓의 제목")
    issue: Optional[str] = Field(default=None, description="문제 상황 요약")
    solution: Optional[str] = Field(default=None, description="해결책 요약")
    ticket_url: Optional[str] = Field(default=None, description="원본 티켓 링크")
    similarity_score: Optional[float] = Field(default=None, description="유사도 점수 (0.0 ~ 1.0)")
    
    # 기존 호환성을 위한 필드 (deprecated)
    ticket_summary: Optional[str] = Field(default=None, description="유사 티켓의 내용 요약 (deprecated)")  

class SimilarTicketsResponse(BaseModel):
    ticket_id: str = Field(description="원본 티켓의 ID")
    similar_tickets: List[SimilarTicketItem] = Field(description="검색된 유사 티켓 목록")

class RelatedDocumentItem(BaseModel):
    id: str = Field(description="관련 문서의 고유 ID")
    title: Optional[str] = Field(default=None, description="관련 문서의 제목")
    doc_summary: Optional[str] = Field(default=None, description="관련 문서의 내용 요약")  # summary → doc_summary로 필드명 변경 (일관성)
    url: Optional[str] = Field(default=None, description="관련 문서의 URL (해당하는 경우)")
    source_type: Optional[str] = Field(default=None, description="문서 출처 유형 (예: 'kb')")
    similarity_score: Optional[float] = Field(default=None, description="유사도 점수 (0.0 ~ 1.0)")

class RelatedDocsResponse(BaseModel):
    ticket_id: str = Field(description="원본 티켓의 ID")
    related_documents: List[RelatedDocumentItem] = Field(description="검색된 관련 문서 목록")


class QueryResultItem(BaseModel):
    """자연어 기반 검색 결과 항목"""
    
    id: str = Field(description="문서 고유 ID")
    title: Optional[str] = Field(default=None, description="문서 제목")
    content_summary: str = Field(description="문서 내용 요약")
    source_type: str = Field(description="문서 유형 (ticket, kb)")
    url: Optional[str] = Field(default=None, description="문서 URL")
    similarity_score: float = Field(description="유사도 점수 (0.0 ~ 1.0)")
    created_at: Optional[str] = Field(default=None, description="문서 생성일")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="추가 메타데이터")


class SearchQueryResponse(BaseModel):
    """자연어 기반 검색 응답 모델"""
    
    query: str = Field(description="검색 질의")
    results: List[QueryResultItem] = Field(description="검색 결과 목록")
    total_results: int = Field(description="검색된 총 결과 수")
    search_time_ms: int = Field(description="검색 소요 시간 (밀리초)")

# 응답 생성 요청/응답 모델
class GenerateReplyRequest(BaseModel):
    """응답 생성 요청 모델"""
    
    context_id: str  # 초기화에서 생성된 컨텍스트 ID
    style: Optional[str] = "professional"  # 응답 스타일 (professional, friendly, technical)
    tone: Optional[str] = "helpful"  # 응답 톤 (helpful, empathetic, direct)
    instructions: Optional[str] = None  # 추가 응답 생성 지침
    include_greeting: bool = True  # 인사말 포함 여부
    include_signature: bool = True  # 서명 포함 여부

# 캐시 설정: 티켓 요약 캐시 (최대 100개, 1시간 TTL)
ticket_summary_cache = TTLCache(maxsize=100, ttl=3600)

@app.get("/init/{ticket_id}", response_model=InitResponse)
async def get_initial_context(
    ticket_id: str, 
    company_id: str = Depends(get_company_id),
    include_summary: bool = True,
    include_kb_docs: bool = True,
    include_similar_tickets: bool = True
):
    """
    티켓 초기화 엔드포인트 - 티켓 요약, 유사 티켓, 추천 솔루션 등 초기 데이터 제공
    
    Args:
        ticket_id: 티켓 ID
        company_id: 회사 ID (의존성 함수를 통해 헤더에서 자동 추출)
        include_summary: 요약 정보 포함 여부 (기본값: True)
        include_kb_docs: 지식베이스 문서 포함 여부 (기본값: True)
        include_similar_tickets: 유사 티켓 포함 여부 (기본값: True)
    
    Returns:
        통합된 초기 데이터 (요약, 유사 티켓, 추천 솔루션 등)
    """
    # 캐시된 데이터가 있는지 확인
    context_cache_key = f"ctx_{ticket_id}"
    cached_data = ticket_context_cache.get(context_cache_key)
    if cached_data:
        logger.info(f"티켓 ID {ticket_id} 캐시된 컨텍스트 데이터를 반환합니다.")
        return cached_data
        
    # company_id가 None이면 기본값 설정
    search_company_id = company_id if company_id else "default"
    logger.info(f"티켓 ID {ticket_id} 초기화 요청 (회사 ID: {search_company_id})")
    
    # 티켓 데이터 조회
    try:
        # doc_type='ticket'을 명시적으로 지정하여 예외 방지 및 일관성 확보
        ticket_data = vector_db.get_by_id(original_id_value=ticket_id, company_id=search_company_id, doc_type="ticket")
        if not ticket_data:
            # Freshdesk API에서 직접 조회 시도
            try:
                ticket_data = await fetcher.fetch_ticket_details(int(ticket_id))
                if not ticket_data:
                    raise HTTPException(status_code=404, detail=f"티켓 ID {ticket_id}를 찾을 수 없습니다.")
            except Exception as fetch_error:
                logger.error(f"Freshdesk API에서 티켓 조회 중 오류: {fetch_error}")
                raise HTTPException(status_code=404, detail=f"티켓 ID {ticket_id}를 찾을 수 없습니다.")
        
        # 메타데이터 추출
        ticket_metadata = ticket_data.get("metadata", {}) if isinstance(ticket_data, dict) else ticket_data
        ticket_title = ticket_metadata.get("subject", f"티켓 ID {ticket_id}")
        ticket_body = ticket_metadata.get("text", ticket_metadata.get("description_text", "티켓 본문 정보 없음"))
        
        # 대화 내용 처리 - 전체 대화 내역 보존하여 요약 품질 개선
        raw_conversations = ticket_metadata.get("conversations", [])
        ticket_conversations = []
        
        if isinstance(raw_conversations, list):
            # 원본 형식 보존 (가능한 경우 딕셔너리 형태 유지)
            ticket_conversations = raw_conversations
        elif isinstance(raw_conversations, str):
            try:
                parsed_convs = json.loads(raw_conversations)
                if isinstance(parsed_convs, list):
                    ticket_conversations = parsed_convs  # 딕셔너리 형태 유지
                else:
                    ticket_conversations = [{"body_text": str(parsed_convs), "created_at": datetime.now().timestamp()}]
            except json.JSONDecodeError:
                ticket_conversations = [{"body_text": raw_conversations, "created_at": datetime.now().timestamp()}]
        
        # 대화 내역이 없는 경우 대화 요약 사용 (최후의 대안)
        if not ticket_conversations and ticket_metadata.get("conversation_summary"):
            ticket_conversations = [{"body_text": str(ticket_metadata.get("conversation_summary")), 
                                    "created_at": datetime.now().timestamp()}]
            
        logger.info(f"티켓 ID {ticket_id} 대화 내역 {len(ticket_conversations)}개 로드됨")
            
        logger.info(f"티켓 ID {ticket_id} 정보 조회 완료: 제목='{ticket_title[:50]}...'")
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"티켓 데이터 조회 중 오류 발생: {str(e)}")
        raise HTTPException(status_code=500, detail=f"티켓 데이터 조회 중 오류가 발생했습니다: {str(e)}")
    
    # 컨텍스트 ID 생성 (향후 요청을 위한 고유 식별자)
    context_id = f"ctx_{ticket_id}_{int(time.time())}"
    
    # 티켓 정보 구성을 위한 모든 텍스트
    # 대화 내용이 딕셔너리 목록인 경우 각 대화에서 본문을 추출하여 문자열로 변환
    conversation_texts = []
    for conv in ticket_conversations:
        if isinstance(conv, dict):
            # body_text, body, text 등의 필드를 순서대로 시도
            for field in ["body_text", "body", "text", "content", "message"]:
                if field in conv and conv[field]:
                    conversation_texts.append(str(conv[field]))
                    break
            else:  # for-else: for 루프가 break 없이 완료되면 실행
                conversation_texts.append(str(conv)[:300])  # 필드를 못 찾은 경우 전체 딕셔너리
        else:
            conversation_texts.append(str(conv))
    
    # 작업별 데이터 초기화
    similar_tickets = []
    kb_documents = []
    ticket_summary = None
    task_times = {}  # 각 작업별 소요 시간 저장
    
    # 컨텍스트 구축 시작 시간
    context_start_time = time.time()
    
    # 모든 작업을 병렬로 실행하기 위한 태스크 목록 
    all_tasks = []
    task_names = []
    
    # 유사 티켓 검색 태스크 (벡터 검색)
    if include_similar_tickets:
        async def fetch_similar_tickets():
            start_time = time.time()
            try:
                logger.info("🔍 유사 티켓 검색 시작...")
                # /similar_tickets/{ticket_id} 엔드포인트 직접 호출
                similar_tickets_response = await get_similar_tickets(ticket_id, company_id)
                
                # 응답 형식 변환: SimilarTicketItem[] -> DocumentInfo[]
                st_results = []
                for item in similar_tickets_response.similar_tickets:
                    # 구조화된 형식으로 content 생성
                    content_parts = []
                    
                    # 문제 상황 추가
                    if item.issue:
                        content_parts.append(f"문제 상황: {item.issue}")
                    
                    # 해결책 추가
                    if item.solution:
                        content_parts.append(f"해결책: {item.solution}")
                        
                    # ticket_summary가 있으면 추가
                    if item.ticket_summary:
                        content_parts.append(f"요약: {item.ticket_summary}")
                    
                    # content 구성
                    content = "\n\n".join(content_parts) if content_parts else f"티켓 {item.id} 관련 정보"
                    
                    st_results.append(DocumentInfo(
                        title=item.title or f"티켓 {item.id}",
                        content=content,
                        source_id=str(item.id),
                        source_url=item.ticket_url or "",
                        relevance_score=item.similarity_score or 0.0,  # 원래 유사도 값 그대로 유지
                        doc_type="ticket"
                    ))
                
                elapsed_time = time.time() - start_time
                logger.info(f"✅ 유사 티켓 검색 완료: {elapsed_time:.3f}초, {len(st_results)}건")
                return st_results, elapsed_time
            except Exception as e:
                elapsed_time = time.time() - start_time
                logger.error(f"❌ 유사 티켓 검색 중 오류 발생: {str(e)}")
                return [], elapsed_time  # 오류 시 빈 리스트와 소요 시간 반환
        
        all_tasks.append(fetch_similar_tickets())
        task_names.append('similar_tickets')
    
    # 지식베이스 문서 검색 태스크 (벡터 검색)
    if include_kb_docs:
        async def fetch_kb_documents():
            start_time = time.time()
            try:
                logger.info("📚 지식베이스 문서 검색 시작...")
                # /related_docs/{ticket_id} 엔드포인트 직접 호출
                related_docs_response = await get_related_documents(ticket_id, company_id)
                
                # 응답 형식 변환: RelatedDocumentItem[] -> DocumentInfo[]
                kb_results = []
                for item in related_docs_response.related_documents:
                    # source_url이 None이면 빈 문자열로 설정하여 오류 방지
                    source_url = item.url or ""
                    
                    kb_results.append(DocumentInfo(
                        title=item.title or f"문서 {item.id}",
                        content=item.doc_summary or "내용 없음",
                        source_id=str(item.id),
                        source_url=source_url,
                        relevance_score=item.similarity_score or 0.0,  # 원래 유사도 값 그대로 유지
                        doc_type=item.source_type or "kb"
                    ))
                
                elapsed_time = time.time() - start_time
                logger.info(f"✅ 지식베이스 문서 검색 완료: {elapsed_time:.3f}초, {len(kb_results)}건")
                return kb_results, elapsed_time
            except Exception as e:
                elapsed_time = time.time() - start_time
                logger.error(f"❌ 지식베이스 문서 검색 중 오류 발생: {str(e)}")
                return [], elapsed_time  # 오류 시 빈 리스트와 소요 시간 반환
        
        all_tasks.append(fetch_kb_documents())
        task_names.append('kb_documents')
    
    # 티켓 요약 생성 태스크 (LLM 호출)
    if include_summary:
        async def generate_summary():
            start_time = time.time()
            try:
                logger.info("🟢 티켓 요약 생성 시작...")
                
                # 티켓 데이터 유효성 검사
                if not ticket_title and not ticket_body:
                    logger.warning(f"티켓 {ticket_id} 데이터가 부족함 (제목: {bool(ticket_title)}, 내용: {bool(ticket_body)})")
                    elapsed_time = time.time() - start_time
                    summary = TicketSummaryContent(
                        ticket_summary="티켓 데이터가 부족하여 요약을 생성할 수 없습니다.",
                        key_points=["데이터 부족"],
                        sentiment="중립적",
                        urgency_level="보통"
                    )
                    return summary, elapsed_time
                
                # 대화 내역을 안전하게 처리
                conversations = ticket_conversations or []
                
                # 티켓 정보 수집
                ticket_info = {
                    "id": ticket_id,
                    "subject": ticket_title,
                    "description": ticket_body,
                    "conversations": conversations,
                    "metadata": ticket_metadata
                }
                
                # LLM 호출하여 요약 생성
                response = await llm_router.generate_ticket_summary(ticket_info)
                
                # LLM 응답 파싱
                summary = TicketSummaryContent(
                    ticket_summary=response.get('summary', '요약 생성에 실패했습니다.'),
                    key_points=response.get('key_points', []),
                    sentiment=response.get('sentiment', '중립적'),
                    priority_recommendation=response.get('priority_recommendation', '보통'),
                    urgency_level=response.get('urgency_level', '보통')
                )
                
                # 캐시에 저장
                ticket_summary_cache[ticket_id] = summary
                
                elapsed_time = time.time() - start_time
                logger.info(f"✅ 티켓 요약 생성 완료: {elapsed_time:.3f}초")
                return summary, elapsed_time
                
            except Exception as e:
                elapsed_time = time.time() - start_time
                logger.error(f"❌ 티켓 {ticket_id} 요약 생성 중 오류 발생: {str(e)}", exc_info=True)
                # 오류 시 기본 요약 반환
                summary = TicketSummaryContent(
                    ticket_summary=f"오류로 인해 요약 생성에 실패했습니다. 티켓 제목: {ticket_title or '제목 없음'}",
                    key_points=["요약 생성 오류", "수동 검토 필요"],
                    sentiment="중립적",
                    priority_recommendation="보통",
                    urgency_level="보통"
                )
                return summary, elapsed_time
        
        all_tasks.append(generate_summary())
        task_names.append('summary')
    
    # 모든 작업을 병렬로 실행
    if all_tasks:
        logger.info(f"🚀 모든 태스크 {len(all_tasks)}개 병렬 실행 시작... (순서: {', '.join(task_names)})")
        results = await asyncio.gather(*all_tasks)
        
        # 결과 처리
        for i, task_name in enumerate(task_names):
            result, elapsed_time = results[i]
            task_times[task_name] = elapsed_time
            
            if task_name == 'similar_tickets':
                similar_tickets = result
            elif task_name == 'kb_documents':
                kb_documents = result
            elif task_name == 'summary':
                ticket_summary = result
    
    # 전체 요청 처리 총 소요 시간 계산
    total_time = time.time() - context_start_time
    
    # 타이밍 로그 출력 (모든 처리 완료 후 한 번에)
    logger.info("=== /init/{} 처리 시간 분석 (병렬 처리) ===".format(ticket_id))
    if 'summary' in task_times:
        logger.info(f"🟢 티켓 요약 생성: {task_times['summary']:.3f}초")
    if 'similar_tickets' in task_times:
        logger.info(f"🔍 유사 티켓 검색: {task_times['similar_tickets']:.3f}초")
    if 'kb_documents' in task_times:
        logger.info(f"📚 추천 솔루션 검색: {task_times['kb_documents']:.3f}초")
    
    # 개별 작업 시간의 합계 계산 (참고용)
    total_individual_time = sum(task_times.values())
    logger.info(f"📊 개별 작업 시간 합계: {total_individual_time:.3f}초 (순차 처리시 예상 시간)")
    logger.info(f"⏱️ 실제 총 소요시간: {total_time:.3f}초 (병렬 처리)")
    
    # 성능 개선 효과 계산
    if total_individual_time > 0:
        improvement_ratio = total_individual_time / total_time
        time_saved = total_individual_time - total_time
        logger.info(f"🚀 병렬 처리 효과: {improvement_ratio:.1f}배 빠름 ({time_saved:.3f}초 단축)")
    
    logger.info("=========================")
    
    # 결과 구성
    # 티켓 메타데이터에 id가 없으면 ticket_id로 추가
    if isinstance(ticket_metadata, dict) and "id" not in ticket_metadata:
        ticket_metadata["id"] = ticket_id
        
    result = InitResponse(
        ticket_id=ticket_id,
        ticket_data=ticket_metadata,
        ticket_summary=ticket_summary,  # 일관된 필드명 사용
        similar_tickets=similar_tickets,
        kb_documents=kb_documents,
        context_id=context_id,
        metadata={
            "duration_ms": int(total_time * 1000),
            "similar_tickets_count": len(similar_tickets),
            "kb_docs_count": len(kb_documents),
            "task_times": {k: round(v, 3) for k, v in task_times.items()}  # 각 작업별 시간 포함
        }
    )
    
    # 결과 캐싱
    ticket_context_cache[context_id] = {
        "ticket_id": ticket_id,
        "company_id": search_company_id,
        "ticket_data": ticket_metadata,
        "similar_tickets": similar_tickets,
        "kb_documents": kb_documents,
        "created_at": time.time()
    }
    
    return result

@app.get("/similar_tickets/{ticket_id}", response_model=SimilarTicketsResponse)
async def get_similar_tickets(ticket_id: str, company_id: str = Depends(get_company_id)):
    """
    특정 티켓 ID와 유사한 과거 티켓 목록을 검색하여 반환합니다.
    
    Args:
        ticket_id: 유사 티켓을 검색할 기준이 되는 티켓의 고유 ID
        company_id: 회사 ID (헤더에서 자동 추출)
        
    Returns:
        SimilarTicketsResponse: 유사 티켓 목록
    """
    try:
        logger.info(f"유사 티켓 검색 시작 (ticket_id: {ticket_id}, company_id: {company_id})")
        
        # 1. 현재 티켓 데이터를 Qdrant에서 가져오기 시도
        # doc_type='ticket'을 명시적으로 지정하여 예외 방지 및 일관성 확보
        current_ticket_data = vector_db.get_by_id(original_id_value=ticket_id, company_id=company_id, doc_type="ticket")
        
        if not current_ticket_data or not current_ticket_data.get("metadata"):
            # Qdrant에서 찾을 수 없으면 Freshdesk API에서 가져오기
            logger.info(f"Qdrant에서 티켓 {ticket_id}를 찾을 수 없어 Freshdesk API를 호출합니다.")
            current_ticket_data = await fetcher.fetch_ticket_details(int(ticket_id))
            if not current_ticket_data:
                raise HTTPException(status_code=404, detail=f"티켓 ID {ticket_id}를 찾을 수 없습니다.")
        else:
            # Qdrant에서 가져온 경우 metadata를 최상위로 올리기
            current_ticket_data = current_ticket_data["metadata"]
            logger.info(f"Qdrant에서 티켓 {ticket_id} 데이터를 성공적으로 가져왔습니다.")
        
        # 2. 검색용 쿼리 텍스트 생성
        search_query = await llm_router.generate_search_query(current_ticket_data)
        if not search_query.strip():
            logger.warning(f"티켓 {ticket_id}에 대한 검색 쿼리 텍스트가 비어있습니다.")
            return SimilarTicketsResponse(ticket_id=ticket_id, similar_tickets=[])
        
        # 3. 검색 쿼리 임베딩 생성
        try:
            query_embedding = await llm_router.generate_embedding(search_query)
            logger.info(f"검색 쿼리 임베딩 생성 완료 (vector_size: {len(query_embedding)})")
        except Exception as e:
            logger.error(f"임베딩 생성 실패, 더미 임베딩 사용: {e}")
            # 임베딩 생성 실패 시 더미 임베딩 사용 (fallback)
            query_embedding = [0.1] * 1536  # OpenAI embedding 차원에 맞춤
        
        # 4. 벡터 DB에서 유사 티켓 검색
        similar_tickets_result = retriever.retrieve_top_k_docs(
            query_embedding=query_embedding, 
            top_k=10,  # 더 많이 가져와서 필터링
            doc_type="ticket",
            company_id=company_id
        )
        
        # 5. 검색 결과 처리
        similar_tickets_list = []
        if similar_tickets_result and similar_tickets_result.get("ids"):
            for i, doc_id in enumerate(similar_tickets_result["ids"]):
                # 현재 티켓과 동일한 ID는 제외
                if str(doc_id) == str(ticket_id):
                    continue
                    
                metadata = similar_tickets_result["metadatas"][i] if i < len(similar_tickets_result.get("metadatas", [])) else {}
                
                # 티켓 제목 추출
                title = (
                    metadata.get("title") or 
                    metadata.get("subject") or 
                    f"티켓 {doc_id}"
                )
                
                # 거리/점수 정보 추가
                distance = similar_tickets_result.get("distances", [0])[i] if i < len(similar_tickets_result.get("distances", [])) else 0
                similarity_score = max(0, 1 - distance)  # 거리를 유사도로 변환
                
                # 티켓 ID 추출 (original_id 또는 doc_id 사용)
                original_ticket_id = metadata.get("original_id", str(doc_id))
                
                # "ticket-xxxx" 형식에서 숫자 부분만 추출
                ticket_number = original_ticket_id
                if isinstance(original_ticket_id, str) and original_ticket_id.startswith("ticket-"):
                    ticket_number = original_ticket_id.replace("ticket-", "")
                
                # Freshdesk 원본 티켓 링크 생성
                freshdesk_domain = os.getenv("FRESHDESK_DOMAIN", "your-domain.freshdesk.com")
                ticket_url = f"https://{freshdesk_domain}.freshdesk.com/a/tickets/{ticket_number}"
                
                # Issue/Solution 분석을 위한 티켓 데이터 구성
                ticket_data_for_analysis = {
                    "id": ticket_number,
                    "subject": title,
                    "description_text": similar_tickets_result["documents"][i] if i < len(similar_tickets_result.get("documents", [])) else "",
                    "status": metadata.get("status", ""),
                    "priority": metadata.get("priority", "")
                }
                
                # LLM을 사용한 Issue/Solution 분석 수행
                try:
                    analysis_result = await llm_router.analyze_ticket_issue_solution(ticket_data_for_analysis)
                    issue = analysis_result.get("issue", "문제 상황을 분석할 수 없습니다.")
                    solution = analysis_result.get("solution", "해결책을 찾을 수 없습니다.")
                except Exception as e:
                    logger.warning(f"티켓 {doc_id} Issue/Solution 분석 실패: {e}")
                    issue = "문제 상황 분석 실패"
                    solution = "해결책 분석 실패"
                
                # 기존 호환성을 위한 요약 생성
                summary_text = similar_tickets_result["documents"][i] if i < len(similar_tickets_result.get("documents", [])) else ""
                if not summary_text:
                    summary_text = metadata.get("description_text", "요약 정보 없음")
                summary = summary_text[:200] + "..." if len(summary_text) > 200 else summary_text
                
                similar_tickets_list.append(SimilarTicketItem(
                    id=str(ticket_number),  # 순수 티켓 번호만 사용
                    title=title,
                    issue=issue,
                    solution=solution,
                    ticket_url=ticket_url,
                    similarity_score=round(similarity_score, 3),
                    ticket_summary=summary  # 기존 호환성을 위해 유지
                ))
                
                # 최대 5개까지만 반환
                if len(similar_tickets_list) >= 5:
                    break
        
        logger.info(f"티켓 {ticket_id}에 대한 유사 티켓 {len(similar_tickets_list)}건 검색 완료")
        return SimilarTicketsResponse(ticket_id=str(ticket_id), similar_tickets=similar_tickets_list)
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"유사 티켓 검색 중 오류 발생 (티켓 ID: {ticket_id}): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"유사 티켓 검색 중 내부 서버 오류 발생: {str(e)}")

@app.get("/related_docs/{ticket_id}", response_model=RelatedDocsResponse)
async def get_related_documents(ticket_id: str, company_id: str = Depends(get_company_id)):
    """
    특정 티켓 ID와 관련된 기술 문서(KB)나 FAQ 목록을 검색하여 반환합니다.
    
    Args:
        ticket_id: 관련 문서를 검색할 기준이 되는 티켓의 고유 ID
        company_id: 회사 ID (헤더에서 자동 추출)
        
    Returns:
        RelatedDocsResponse: 관련 문서 목록
    """
    try:
        logger.info(f"관련 문서 검색 시작 (ticket_id: {ticket_id}, company_id: {company_id})")
        
        # 1. 현재 티켓 데이터를 Qdrant에서 가져오기 시도
        # doc_type='ticket'을 명시적으로 지정하여 예외 방지 및 일관성 확보
        current_ticket_data = vector_db.get_by_id(original_id_value=ticket_id, company_id=company_id, doc_type="ticket")
        
        if not current_ticket_data or not current_ticket_data.get("metadata"):
            # Qdrant에서 찾을 수 없으면 Freshdesk API에서 가져오기
            logger.info(f"Qdrant에서 티켓 {ticket_id}를 찾을 수 없어 Freshdesk API를 호출합니다.")
            try:
                current_ticket_data = await fetcher.fetch_ticket_details(int(ticket_id))
            except Exception as api_error:
                logger.error(f"Freshdesk API에서 티켓 {ticket_id} 조회 실패: {api_error}")
                current_ticket_data = None
                
            if not current_ticket_data:
                raise HTTPException(status_code=404, detail=f"티켓 ID {ticket_id}를 찾을 수 없습니다.")
        else:
            # Qdrant에서 가져온 경우 metadata를 최상위로 올리기
            current_ticket_data = current_ticket_data["metadata"]
            logger.info(f"Qdrant에서 티켓 {ticket_id} 데이터를 성공적으로 가져왔습니다.")
        
        # 2. 검색용 쿼리 텍스트 생성
        search_query = None
        try:
            search_query = await llm_router.generate_search_query(current_ticket_data)
        except Exception as query_error:
            logger.error(f"검색 쿼리 생성 실패: {query_error}")
            # 쿼리 생성 실패 시 티켓 제목과 내용을 사용
            subject = current_ticket_data.get("subject", "")
            description = current_ticket_data.get("description", "")
            search_query = f"{subject} {description[:200]}"
            
        if not search_query or not search_query.strip():
            logger.warning(f"티켓 {ticket_id}에 대한 검색 쿼리 텍스트가 비어있습니다.")
            return RelatedDocsResponse(ticket_id=ticket_id, related_documents=[])
        
        # 3. 검색 쿼리 임베딩 생성
        try:
            query_embedding = await llm_router.generate_embedding(search_query)
            logger.info(f"검색 쿼리 임베딩 생성 완료 (vector_size: {len(query_embedding)})")
        except Exception as e:
            logger.error(f"임베딩 생성 실패, 더미 임베딩 사용: {e}")
            # 임베딩 생성 실패 시 더미 임베딩 사용 (fallback)
            query_embedding = [0.1] * 1536  # OpenAI embedding 차원에 맞춤
        
        # 4. 벡터 DB에서 관련 문서 검색 (KB, FAQ 등)
        related_docs_result = None
        try:
            # KB 문서는 type이 1인 경우 (published 상태)
            # 또는 source_type이 "kb"인 경우로 식별
            related_docs_result = retriever.retrieve_top_k_docs(
                query_embedding=query_embedding, 
                top_k=10,  # 더 많이 가져와서 필터링
                doc_type="kb",  # "kb" 타입으로 검색 (vectordb.py에서 1과 "1"도 함께 처리)
                company_id=company_id
            )
            logger.info(f"KB 검색 완료: {len(related_docs_result.get('documents', []))}개 결과")
            
            # 결과가 없으면 메모리 내 필터링 방식으로 시도
            if not related_docs_result.get('documents'):
                logger.info("KB 문서(type=1) 검색 결과가 없어 직접 검색 시도")
                
                # 필터 없이 검색 후 메모리에서 필터링
                all_results = vector_db.search(
                    query_embedding=query_embedding,
                    top_k=30,  # 더 많은 결과에서 필터링
                    company_id=company_id
                )
                
                # 검색 결과에서 KB 문서만 추출
                documents = []
                metadatas = []
                distances = []
                ids = []
                
                # 결과가 있는 경우 필터링
                if all_results and all_results.get("results"):
                    logger.info(f"벡터DB에서 반환된 전체 결과: {len(all_results['results'])}개")
                    for i, result in enumerate(all_results.get("results", [])):
                        # KB 문서 타입 필드들 (여러 필드 확인)
                        doc_type = result.get("doc_type")
                        result_type = result.get("type")
                        source_type = result.get("source_type")
                        status = result.get("status")
                        
                        # KB 문서 판별 조건 확장:
                        # 1. doc_type이 "kb"인 경우
                        # 2. type이 "kb", "1" 또는 1인 경우
                        # 3. source_type이 "kb", "1" 또는 1인 경우
                        # 4. status가 1(published) 또는 "1"인 경우
                        if (doc_type == "kb" or 
                            result_type in ["kb", "1", 1] or 
                            source_type in ["kb", "1", 1] or 
                            status in [1, "1"]):
                            
                            # 문서 텍스트 추가
                            if "documents" in all_results and i < len(all_results.get("documents", [])):
                                documents.append(all_results["documents"][i])
                            else:
                                # 문서 텍스트가 없으면 description 또는 빈 문자열 사용
                                documents.append(result.get("description", ""))
                            
                            # 메타데이터 추가 (결과 전체를 메타데이터로 사용)
                            metadatas.append(result)
                            
                            # 거리(유사도) 추가
                            if "distances" in all_results and i < len(all_results.get("distances", [])):
                                distances.append(all_results["distances"][i])
                            else:
                                # 거리 정보가 없으면 score 사용
                                distances.append(1.0 - result.get("score", 0))
                            
                            # ID 추가
                            if "ids" in all_results and i < len(all_results.get("ids", [])):
                                ids.append(all_results["ids"][i])
                            else:
                                # ID 정보가 없으면 result의 id 필드 사용
                                ids.append(result.get("id", f"unknown-{i}"))
                
                # 필터링된 결과 구성
                related_docs_result = {
                    "documents": documents,
                    "metadatas": metadatas, 
                    "distances": distances,
                    "ids": ids
                }
                logger.info(f"메모리 내 필터링 후 KB 문서(type=1) 검색 결과: {len(documents)}개")
        except Exception as kb_error:
            logger.error(f"KB 문서 검색 실패: {kb_error}", exc_info=True)
            related_docs_result = {
                "documents": [],
                "metadatas": [],
                "distances": [],
                "ids": []
            }
        
        # FAQ 기능은 제거되었으므로 FAQ 검색 코드도 제거됨 (2025.06.03)
        
        # 6. 검색 결과 처리 및 병합
        related_docs_list = []
        
        # KB 문서 처리
        if related_docs_result and (related_docs_result.get("ids") or related_docs_result.get("results")):
            # 결과 목록 확인
            doc_ids = related_docs_result.get("ids", [])
            metadatas = related_docs_result.get("metadatas", [])
            documents = related_docs_result.get("documents", [])
            distances = related_docs_result.get("distances", [])
            results = related_docs_result.get("results", [])
            
            # 결과가 results 목록에 있는 경우
            if not doc_ids and results:
                logger.info("결과가 results 목록에 있습니다. results 기준으로 처리합니다.")
                for i, result in enumerate(results):
                    metadata = result  # result 자체가 메타데이터
                    doc_id = result.get("id", f"unknown-{i}")
                    
                    title = metadata.get("title", f"문서 {doc_id}")
                    url = metadata.get("url", None)
                    
                    # 문서 텍스트/내용 가져오기
                    summary_text = ""
                    if i < len(documents):
                        summary_text = documents[i]
                    elif "description" in metadata:
                        summary_text = metadata.get("description", "")
                    elif "content" in metadata:
                        summary_text = metadata.get("content", "")
                    
                    if not summary_text:
                        summary_text = "요약 정보 없음"
                    
                    summary = summary_text[:200] + "..." if len(summary_text) > 200 else summary_text
                    
                    # 문서 타입 정보 확인 (여러 필드 확인)
                    source_type = "kb"  # 기본값은 KB
                    if "source_type" in metadata:
                        source_type = metadata["source_type"]
                    elif "type" in metadata:
                        if metadata["type"] in ["kb", "1", 1]:
                            source_type = "kb"
                    
                    # 거리/점수 정보 추가
                    distance = 0
                    if i < len(distances):
                        distance = distances[i]
                    elif "score" in result:
                        # score가 있으면 1-score를 거리로 사용
                        distance = 1 - result["score"]
                    
                    # 거리를 유사도로 변환
                    similarity_score = max(0, 1 - distance)
                    
                    related_docs_list.append(RelatedDocumentItem(
                        id=str(doc_id),
                        title=title,
                        doc_summary=summary,
                        url=url,
                        source_type="kb",  # 명시적으로 'kb'로 설정
                        similarity_score=round(similarity_score, 3)
                    ))
            
            # 기존 방식 (ids 기반)
            else:
                for i, doc_id in enumerate(doc_ids):
                    metadata = metadatas[i] if i < len(metadatas) else {}
                    
                    title = metadata.get("title", f"문서 {doc_id}")
                    url = metadata.get("url", None)
                    
                    # 문서 요약 생성
                    summary_text = documents[i] if i < len(documents) else ""
                    if not summary_text:
                        summary_text = metadata.get("description", "요약 정보 없음")
                    
                    summary = summary_text[:200] + "..." if len(summary_text) > 200 else summary_text
                    source_type = metadata.get("source_type", metadata.get("type", "kb"))
                    
                    # 거리/점수 정보 추가
                    distance = distances[i] if i < len(distances) else 0
                    similarity_score = max(0, 1 - distance)  # 거리를 유사도로 변환
                
                # KB 문서 URL 생성 또는 개선
                if not url and (source_type == "kb" or source_type == "1"):
                    # 원본 문서 ID 추출 (필요한 경우)
                    article_id = metadata.get("article_id", metadata.get("original_id", doc_id))
                    if isinstance(article_id, str) and article_id.startswith("kb-"):
                        article_id = article_id.replace("kb-", "")
                    
                    # 생성된 URL이 있는지 먼저 확인
                    url = metadata.get("url", None)
                    if not url:
                        # Freshdesk 도메인을 사용하여 URL 생성
                        freshdesk_domain = os.getenv("FRESHDESK_DOMAIN", "your-domain.freshdesk.com")
                        # 도메인 검증 및 URL 구성
                        if not freshdesk_domain:
                            logger.warning("FRESHDESK_DOMAIN 환경 변수가 설정되지 않았습니다.")
                            url = None
                        else:
                            # 도메인 값에 이미 .freshdesk.com이 포함되어 있는지 확인
                            if ".freshdesk.com" in freshdesk_domain:
                                domain_base = freshdesk_domain
                            else:
                                domain_base = f"{freshdesk_domain}.freshdesk.com"
                                
                            # URL 생성
                            url = f"https://{domain_base}/support/solutions/articles/{article_id}"
                
                related_docs_list.append(RelatedDocumentItem(
                    id=str(doc_id), 
                    title=title, 
                    doc_summary=summary, 
                    url=url, 
                    source_type="kb",  # 명시적으로 'kb'로 설정
                    similarity_score=round(similarity_score, 3)
                ))
        
        # FAQ 기능이 제거되었습니다 (2025.06.03)
        # 아래 FAQ 관련 코드는 더 이상 사용되지 않으므로 주석 처리
        
        # 유사도 점수 기준으로 정렬하고 상위 결과만 반환
        related_docs_list.sort(key=lambda x: x.similarity_score, reverse=True)
        
        # 너무 낮은 유사도 점수의 결과 필터링 - 임계값 0.3에서 0.25로 더 낮춤 (25%)
        min_similarity = 0.25  # 더 많은 결과를 얻기 위해 임계값을 25%로 낮춤
        filtered_docs = [doc for doc in related_docs_list if doc.similarity_score >= min_similarity]
        
        # 최대 반환 결과 수 제한 (상위 5개)
        if filtered_docs:
            logger.info(f"임계값 {min_similarity} 이상의 관련 문서 {len(filtered_docs)}건 발견")
            related_docs_list = filtered_docs[:5]
        else:
            # 유사도가 낮더라도 검색 결과가 있으면 결과는 반환
            if related_docs_list:
                logger.info("임계값보다 낮은 문서만 발견되어 상위 3개 반환")
                related_docs_list = related_docs_list[:3]
            else:
                # 결과가 전혀 없으면 빈 응답 반환
                logger.warning("관련 문서 검색 결과가 없습니다.")
        
        # 관련 문서 유형별 카운팅을 위한 통계 계산
        docs_by_type = {}
        for doc in related_docs_list:
            doc_type = doc.source_type or "unknown"
            if doc_type in docs_by_type:
                docs_by_type[doc_type] += 1
            else:
                docs_by_type[doc_type] = 1
                
        # 결과 통계 로깅
        type_counts = ", ".join([f"{k}: {v}" for k, v in docs_by_type.items()])
        logger.info(f"티켓 {ticket_id}에 대한 관련 문서 검색 완료: 총 {len(related_docs_list)}건 (유형별: {type_counts})")
        return RelatedDocsResponse(ticket_id=ticket_id, related_documents=related_docs_list)
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"관련 문서 검색 중 오류 발생 (티켓 ID: {ticket_id}): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"관련 문서 검색 중 내부 서버 오류 발생: {str(e)}")
        
        
class GenerateReplyResponse(BaseModel):
    """응답 생성 응답 모델"""
    
    reply_text: str  # 생성된 응답 텍스트
    context_docs: List[DocumentInfo]  # 참조된 문서 목록
    metadata: Dict[str, Any] = Field(default_factory=dict)  # 메타데이터

@app.post("/generate_reply", response_model=GenerateReplyResponse)
async def generate_reply(request: GenerateReplyRequest):
    """
    고객 지원 티켓에 대한 응답을 생성하는 엔드포인트
    
    이 엔드포인트는 초기화된 티켓 컨텍스트를 기반으로 응답을 생성합니다.
    자연어 텍스트 기반 응답이 반환됩니다.
    
    Args:
        request: 응답 생성 요청
        
    Returns:
        생성된 응답 텍스트 및 참조 문서
    """
    # 성능 측정 시작
    start_time = time.time()
    
    # 컨텍스트 ID 확인
    context_id = request.context_id
    if not context_id or context_id not in ticket_context_cache:
        raise HTTPException(status_code=400, detail="유효하지 않은 컨텍스트 ID입니다. 먼저 /init 엔드포인트를 호출해주세요.")
    
    # 캐시에서 컨텍스트 검색
    context = ticket_context_cache[context_id]
    ticket_id = context["ticket_id"]
    company_id = context["company_id"]
    ticket_data = context["ticket_data"]
    similar_tickets = context["similar_tickets"]
    kb_documents = context["kb_documents"]
    
    logger.info(f"티켓 ID {ticket_id}에 대한 응답 생성 시작 (회사 ID: {company_id})")
    
    # 티켓 메타데이터 추출
    ticket_metadata = ticket_data.get("metadata", {})
    ticket_title = ticket_metadata.get("subject", f"티켓 ID {ticket_id}")
    ticket_body = ticket_metadata.get("text", ticket_metadata.get("description_text", "티켓 본문 정보 없음"))
    
    # 대화 추출
    raw_conversations = ticket_metadata.get("conversations", [])
    ticket_conversations = []
    
    if isinstance(raw_conversations, list):
        ticket_conversations = [str(conv) for conv in raw_conversations]
    elif isinstance(raw_conversations, str):
        try:
            parsed_convs = json.loads(raw_conversations)
            if isinstance(parsed_convs, list):
                ticket_conversations = [str(conv) for conv in parsed_convs]
        except json.JSONDecodeError:
            ticket_conversations = [raw_conversations]
    
    if not ticket_conversations and ticket_metadata.get("conversation_summary"):
        ticket_conversations = [str(ticket_metadata.get("conversation_summary"))]
    
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
    for idx, ticket in enumerate(similar_tickets[:5]):  # 최대 5개까지 고려
        doc_content = f"제목: {ticket.title}\n내용: {ticket.content}"
        context_docs.append(doc_content)
        context_metadatas.append({
            "title": ticket.title,
            "source_type": "similar_ticket",
            "source_id": ticket.source_id,
            "relevance_score": ticket.relevance_score,
            "doc_type": "ticket"
        })
    
    # 지식베이스 문서를 문서로 변환
    for idx, doc in enumerate(kb_documents[:5]):  # 최대 5개까지 고려
        doc_content = f"제목: {doc.title}\n내용: {doc.content}"
        context_docs.append(doc_content)
        context_metadatas.append({
            "title": doc.title,
            "source_type": "kb",
            "source_id": doc.source_id,
            "source_url": doc.source_url,
            "relevance_score": doc.relevance_score,
            "doc_type": "kb"
        })
    
    # 최적화된 컨텍스트 구성 (쿼리는 티켓 제목으로 설정)
    query_for_context = f"{ticket_title} {ticket_body[:200]}"  # 티켓 정보를 쿼리로 사용
    
    optimized_context = ""
    context_meta = {}
    
    if context_docs:
        optimized_context, optimized_metadatas, context_meta = build_optimized_context(
            docs=context_docs,
            metadatas=context_metadatas,
            query=query_for_context,
            max_tokens=6000,  # 응답 생성용이므로 조금 더 작게 설정
            top_k=8,  # 충분한 정보 제공을 위해 조금 더 많이
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
        response = await call_llm(prompt, system_prompt=system_prompt)
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
            # 최적화 컨텍스트 정보 추가
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


@app.post("/search_query", response_model=SearchQueryResponse)
async def search_query(req: QueryRequest, company_id: str = Depends(get_company_id)):
    """
    자연어 기반 검색 엔드포인트 - 사용자의 질문에 대해 관련 문서들을 검색합니다.
    
    프론트엔드의 "OO와 대화하기" 탭에서 사용되는 엔드포인트로,
    티켓, KB 문서, FAQ를 통합 검색하여 관련성 높은 결과를 반환합니다.
    
    Args:
        req: 검색 요청 (질문, 검색 옵션 등)
        company_id: 회사 ID (헤더에서 자동 추출)
        
    Returns:
        QueryResponse: 검색 결과 목록
    """
    start_time = time.time()
    
    try:
        logger.info(f"자연어 검색 시작 (query: {req.query[:50]}..., company_id: {company_id})")
        
        # 회사 ID 오버라이드 (요청에 명시된 경우)
        if req.company_id:
            company_id = req.company_id
        
        # 검색 질의가 비어있는 경우 처리
        if not req.query.strip():
            logger.warning("빈 검색 질의가 제공되었습니다.")
            return SearchQueryResponse(
                query=req.query,
                results=[],
                total_results=0,
                search_time_ms=0
            )
        
        # 1. 검색 쿼리 임베딩 생성
        try:
            query_embedding = await llm_router.generate_embedding(req.query)
            logger.info(f"검색 쿼리 임베딩 생성 완료 (vector_size: {len(query_embedding)})")
        except Exception as e:
            logger.error(f"임베딩 생성 실패, 더미 임베딩 사용: {e}")
            # 임베딩 생성 실패 시 더미 임베딩 사용 (fallback)
            query_embedding = [0.1] * 1536  # OpenAI embedding 차원에 맞춤
        
        # 2. 검색할 문서 유형 결정
        search_types = req.search_types if req.search_types and req.search_types != ["all"] else ["ticket", "kb"]
        
        all_results = []
        
        # 3. 각 문서 유형별로 검색 수행
        for doc_type in search_types:
            try:
                # 티켓 또는 KB 문서 검색
                    search_result = retriever.retrieve_top_k_docs(
                        query_embedding=query_embedding,
                        top_k=req.top_k,
                        doc_type=doc_type,
                        company_id=company_id
                    )
                    
                    # 검색 결과 변환
                    if search_result and search_result.get("ids"):
                        for i, doc_id in enumerate(search_result["ids"]):
                            # 유사도 계산
                            distance = search_result.get("distances", [0])[i] if i < len(search_result.get("distances", [])) else 0
                            similarity_score = max(0, 1 - distance)  # 거리를 유사도로 변환
                            
                            # 최소 유사도 임계값 확인
                            if similarity_score < req.min_similarity:
                                continue
                            
                            metadata = search_result["metadatas"][i] if i < len(search_result.get("metadatas", [])) else {}
                            content = search_result["documents"][i] if i < len(search_result.get("documents", [])) else ""
                            
                            # 제목 추출
                            title = (
                                metadata.get("title") or 
                                metadata.get("subject") or 
                                f"{doc_type.upper()} {doc_id}"
                            )
                            
                            # URL 생성
                            url = metadata.get("url", "")
                            
                            # 내용 요약 (300자 제한)
                            content_summary = content[:300] + ("..." if len(content) > 300 else "")
                            
                            all_results.append(QueryResultItem(
                                id=str(doc_id),
                                title=title,
                                content_summary=content_summary,
                                source_type=doc_type,
                                url=url,
                                similarity_score=round(similarity_score, 3),
                                created_at=metadata.get("created_at"),
                                metadata=metadata
                            ))
                        
            except Exception as e:
                logger.error(f"{doc_type} 검색 중 오류 발생: {e}")
                continue
        
        # 4. 결과 정렬 및 필터링
        # 유사도 점수 기준 내림차순 정렬
        all_results.sort(key=lambda x: x.similarity_score, reverse=True)
        
        # 상위 결과만 반환 (top_k 제한)
        final_results = all_results[:req.top_k]
        
        # 5. 응답 생성
        search_time_ms = int((time.time() - start_time) * 1000)
        
        logger.info(f"자연어 검색 완료 (총 {len(final_results)}건, {search_time_ms}ms 소요)")
        
        return SearchQueryResponse(
            query=req.query,
            results=final_results,
            total_results=len(final_results),
            search_time_ms=search_time_ms
        )
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"자연어 검색 중 예상치 못한 오류 발생: {e}")
        raise HTTPException(status_code=500, detail=f"검색 중 오류가 발생했습니다: {str(e)}")


if __name__ == "__main__":
    import argparse

    import uvicorn
    
    # 명령행 인자 처리
    parser = argparse.ArgumentParser(description="Freshdesk Custom App 백엔드 서버")
    parser.add_argument("--host", default="0.0.0.0", help="서버 호스트 주소 (기본값: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="서버 포트 (기본값: 8000)")
    parser.add_argument("--reload", action="store_true", help="개발 모드 - 파일 변경 시 자동 재시작")
    parser.add_argument("--debug", action="store_true", help="디버그 모드 활성화")
    args = parser.parse_args()
    
    # 로그 레벨 설정
    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
        logger.info("디버그 모드로 서버를 시작합니다")
    else:
        logging.basicConfig(level=logging.INFO)
    
    logger.info(f"FastAPI 백엔드 서버를 시작합니다 - http://{args.host}:{args.port}")
    
    # uvicorn 서버 실행
    # 디버거에서 실행할 때는 app 객체를 직접 전달
    uvicorn.run(
        app,  # FastAPI 앱 객체 직접 전달 (디버거 호환성)
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info" if not args.debug else "debug"
    )
