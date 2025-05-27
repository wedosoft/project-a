"""
Freshdesk Custom App 백엔드 서비스

이 프로젝트는 Freshdesk Custom App(Prompt Canvas)을 위한 백엔드 서비스입니다.
RAG(Retrieval-Augmented Generation) 기술을 활용하여 Freshdesk 티켓과 지식베이스를 기반으로
AI 기반 응답 생성 기능을 제공합니다.
"""

import asyncio
import json
import logging
import re
import time
import uuid
from datetime import datetime
from functools import partial
from typing import Any, Dict, List, Optional, Union

import prometheus_client
from cachetools import TTLCache, cached
from cachetools.keys import hashkey
from core import context_builder, llm_router, retriever
from core.context_builder import build_optimized_context
from core.embedder import embed_documents
from core.llm_router import LLMResponse, generate_text
from core.retriever import retrieve_faqs, retrieve_top_k_docs
from core.vectordb import vector_db
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from freshdesk import fetcher
from prometheus_client import Counter, Histogram
from pydantic import BaseModel, Field

# Prometheus 메트릭 정의
# LLM 라우터에서 정의된 메트릭을 여기서도 사용할 수 있도록 공유하거나,
# 애플리케이션 레벨의 메트릭을 정의합니다.
# 예시: HTTP 요청 관련 메트릭
http_requests_total = Counter('http_requests_total', 'Total HTTP Requests', ['method', 'endpoint', 'http_status'])
http_request_duration_seconds = Histogram('http_request_duration_seconds', 'HTTP request duration, in seconds', ['method', 'endpoint'])
# LLM 관련 메트릭 (llm_router.py와 공유 또는 여기서 직접 정의)
# llm_router.py에서 직접 Prometheus 클라이언트를 사용하도록 수정했으므로 여기서는 중복 정의하지 않음.
# 대신, llm_router에서 사용할 메트릭 객체들을 여기서 생성하고 라우터에 전달하는 방식을 고려할 수 있으나,
# 현재 llm_router.py에서 직접 메트릭을 정의하고 업데이트하도록 되어 있음.
# 따라서 main.py에서는 /metrics 엔드포인트만 제공.

# FastAPI 앱 생성
app = FastAPI()

# 인메모리 캐시 설정 (TTL: 10분, 최대 100개 항목)
# 회사 ID와 요청 매개변수를 기반으로 캐시 키를 생성합니다.
cache = TTLCache(maxsize=100, ttl=600)

# 성능 로깅을 위한 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FAQ 검색 관련 상수
FAQ_TOP_K = 2 # 검색할 최대 FAQ 개수
FAQ_MIN_SCORE = 0.7 # FAQ 검색 시 최소 유사도 점수

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
    # faq_top_k: int = FAQ_TOP_K # 요청별 FAQ top_k 설정 (필요시)


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
    source_url: str = ""
    relevance_score: float = 0.0
    doc_type: Optional[str] = None # 문서 타입을 명시 (예: "ticket", "kb", "faq")


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


class FAQEntry(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    question: str
    answer: str
    category: Optional[str] = None
    source_doc_id: Optional[str] = None # 원본 문서 ID (있을 경우)
    company_id: str # 데이터 격리를 위한 회사 ID
    embedding: Optional[List[float]] = None # 질문 임베딩 벡터
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    score: Optional[float] = None # 검색 시 유사도 점수


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


async def call_llm(prompt: str, system_prompt: str = None) -> LLMResponse:
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
        # 비동기 메서드 호출로 수정
        ticket_data = await vector_db.get_by_id(id=req.ticket_id, company_id=company_id)
        
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

    # FAQ 검색 (콘텐츠 타입에 "solutions"가 포함된 경우만)
    faq_items = []
    if "solutions" in content_types:
        faq_items = retrieve_faqs(
            query_embedding=query_embedding,
            top_k=FAQ_TOP_K, # 전역 상수 사용
            company_id=company_id,
            min_score=FAQ_MIN_SCORE # 전역 상수 사용
        )
        logger.info(f"FAQ 검색 결과: {len(faq_items)} 건")

    faq_docs_content = []
    faq_metadatas_list = []
    faq_distances = [] # FAQ 점수를 거리로 변환하여 저장

    for faq in faq_items:
        # doc_content = f"FAQ 질문: {faq.get('question', '')}\\\nFAQ 답변: {faq.get('answer', '')}"
        faq_question = faq.get('question', '')
        faq_answer = faq.get('answer', '')
        doc_content = f"FAQ 질문: {faq_question}\\nFAQ 답변: {faq_answer}"
        meta = {
            "source_type": "faq", 
            "id": faq.get("id"), 
            "category": faq.get("category"), 
            "original_score": faq.get("score", 0.0),
            "title": f"FAQ: {faq.get('question', '')[:50]}..." # DocumentInfo용 임시 제목
        }
        faq_docs_content.append(doc_content)
        faq_metadatas_list.append(meta)
        # FAQ 점수(유사도)를 거리로 변환 (1 - score), 점수가 없을 경우 최대 거리(1.0) 부여
        faq_distances.append(1.0 - faq.get("score", 0.0))

    # 검색 결과를 병합합니다.
    all_docs_content = ticket_results["documents"] + kb_results["documents"] + faq_docs_content
    all_metadatas = ticket_results["metadatas"] + kb_results["metadatas"] + faq_metadatas_list
    all_distances = ticket_results["distances"] + kb_results["distances"] + faq_distances
    
    # 통합된 결과를 유사도 기준으로 재정렬합니다 (거리가 작을수록 유사도가 높음).
    # 각 메타데이터에 doc_type을 명시적으로 추가합니다.
    for meta in ticket_results["metadatas"]:
        meta["source_type"] = "ticket"
    for meta in kb_results["metadatas"]:
        meta["source_type"] = "kb"
    # FAQ 메타데이터에는 이미 source_type="faq"가 설정되어 있습니다.

    combined = list(zip(all_docs_content, all_metadatas, all_distances))
    combined.sort(key=lambda x: x[2]) # 거리(distance) 기준으로 오름차순 정렬
    
    # 최대 top_k 개수만큼 잘라냅니다. (FAQ가 추가되었으므로, 전체 top_k를 고려)
    # req.top_k는 원래 문서에 대한 것이므로, FAQ를 포함한 전체 개수를 어떻게 할지 결정 필요.
    # 여기서는 단순 합산 후 req.top_k + FAQ_TOP_K 만큼 자르거나, 혹은 기존 req.top_k를 유지.
    # 우선은 req.top_k를 유지하고, FAQ는 추가적인 정보로 활용될 수 있도록 합니다.
    # 만약 FAQ가 매우 관련 높으면 우선적으로 포함되도록 정렬은 이미 처리됨.
    final_top_k = req.top_k # 필요시 이 값을 조정 (예: req.top_k + len(faq_items))
    combined = combined[:final_top_k]
    
    # 다시 분리합니다.
    docs = [item[0] for item in combined]
    metadatas = [item[1] for item in combined]
    distances = [item[2] for item in combined] # 이 distances는 실제 거리 또는 1-score 값임
    
    search_time = time.time() - search_start
    
    # 2. 컨텍스트 최적화 단계: 검색된 문서를 LLM 입력에 적합하도록 가공합니다.
    context_start = time.time()
    
    # 최적화된 컨텍스트를 구성합니다. (검색된 문서들로부터)
    base_context, optimized_metadatas, context_meta = build_optimized_context(docs, metadatas)
    
    # LLM에 전달할 최종 컨텍스트 (티켓 정보 + 검색된 문서 정보)
    final_context_for_llm = f"{ticket_context_for_llm}{base_context}"
    
    prompt = build_prompt(final_context_for_llm, req.query, answer_instructions=req.answer_instructions)
    
    structured_docs = []
    for i, (doc_content_item, metadata_item, distance_or_score_metric) in enumerate(zip(docs, metadatas, distances)):
        title = metadata_item.get("title", "") # FAQ의 경우 임시 제목 사용, 다른 경우 기존 로직 따름
        content = doc_content_item
        doc_type = metadata_item.get("source_type", "unknown")

        if doc_type != "faq":
            lines = doc_content_item.split("\\n", 2)
            if len(lines) > 0 and lines[0].startswith("제목:"):
                title = lines[0].replace("제목:", "").strip()
                if len(lines) > 1:
                    content = "\\n".join(lines[1:]).strip()
                    if content.startswith("설명:"):
                        content = content.replace("설명:", "", 1).strip()
        
        relevance_score = 0.0
        if doc_type == "faq":
            # FAQ의 경우 original_score (0~1)를 백분율로 변환
            relevance_score = round(metadata_item.get("original_score", 0.0) * 100, 1)
        else:
            # 기존 문서의 경우 코사인 거리 (0~2)를 백분율로 변환
            relevance_score = round(((2 - distance_or_score_metric) / 2) * 100, 1)


        doc_info = DocumentInfo(
            title=title,
            content=content,
            source_id=metadata_item.get("source_id", metadata_item.get("id", "")), # FAQ는 id 사용
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
    
    # 성능을 로깅합니다.
    logger.info(f"성능: company_id=\'{company_id}\', query=\'{req.query[:50]}...\', 검색시간={search_time:.2f}s, 컨텍스트생성시간={context_time:.2f}s, LLM호출시간={llm_time:.2f}s, 총시간={total_time:.2f}s")
    
    # 메타데이터를 구성합니다.
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
        "ticket_id": req.ticket_id # 연관된 티켓 ID (있는 경우)
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
    ticket_summary: Optional[str] = Field(default=None, description="유사 티켓의 내용 요약")  # summary → ticket_summary로 필드명 변경 (일관성)

class SimilarTicketsResponse(BaseModel):
    ticket_id: str = Field(description="원본 티켓의 ID")
    similar_tickets: List[SimilarTicketItem] = Field(description="검색된 유사 티켓 목록")

class RelatedDocumentItem(BaseModel):
    id: str = Field(description="관련 문서의 고유 ID")
    title: Optional[str] = Field(default=None, description="관련 문서의 제목")
    doc_summary: Optional[str] = Field(default=None, description="관련 문서의 내용 요약")  # summary → doc_summary로 필드명 변경 (일관성)
    url: Optional[str] = Field(default=None, description="관련 문서의 URL (해당하는 경우)")
    source_type: Optional[str] = Field(default=None, description="문서 출처 유형 (예: 'kb', 'faq')")

class RelatedDocsResponse(BaseModel):
    ticket_id: str = Field(description="원본 티켓의 ID")
    related_documents: List[RelatedDocumentItem] = Field(description="검색된 관련 문서 목록")


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
    cached_data = ticket_context_cache.get(f"ctx_{ticket_id}")
    if cached_data:
        logger.info(f"티켓 ID {ticket_id} 캐시된 컨텍스트 데이터를 반환합니다.")
        return cached_data
        
    # 성능 측정 시작
    start_time = time.time()
    
    # company_id가 None이면 기본값 설정
    search_company_id = company_id if company_id else "default"
    logger.info(f"티켓 ID {ticket_id} 초기화 요청 (회사 ID: {search_company_id})")
    
    # 티켓 데이터 조회
    try:
        
        # 동기 메서드 호출로 수정
        ticket_data = vector_db.get_by_id(id=ticket_id, company_id=search_company_id)
        if not ticket_data:
            # Freshdesk API에서 직접 조회 시도
            try:
                ticket_data = await fetcher.fetch_ticket_details(ticket_id)
                if not ticket_data:
                    raise HTTPException(status_code=404, detail=f"티켓 ID {ticket_id}를 찾을 수 없습니다.")
            except Exception as fetch_error:
                logger.error(f"Freshdesk API에서 티켓 조회 중 오류: {fetch_error}")
                raise HTTPException(status_code=404, detail=f"티켓 ID {ticket_id}를 찾을 수 없습니다.")
        
        # 메타데이터 추출
        ticket_metadata = ticket_data.get("metadata", {}) if isinstance(ticket_data, dict) else ticket_data
        ticket_title = ticket_metadata.get("subject", f"티켓 ID {ticket_id}")
        ticket_body = ticket_metadata.get("text", ticket_metadata.get("description_text", "티켓 본문 정보 없음"))
        
        # 대화 내용 처리
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
            
        logger.info(f"티켓 ID {ticket_id} 정보 조회 완료: 제목='{ticket_title[:50]}...'")
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"티켓 데이터 조회 중 오류 발생: {str(e)}")
        raise HTTPException(status_code=500, detail=f"티켓 데이터 조회 중 오류가 발생했습니다: {str(e)}")
    
    # 컨텍스트 ID 생성 (향후 요청을 위한 고유 식별자)
    context_id = f"ctx_{ticket_id}_{int(time.time())}"
    
    # 티켓 정보 구성을 위한 모든 텍스트
    ticket_full_text = f"{ticket_title}\n\n{ticket_body}\n\n" + "\n\n".join(ticket_conversations)
    
    similar_tickets = []
    kb_documents = []
    ticket_summary = None
    
    # 컨텍스트 구축 시작 시간
    context_start_time = time.time()
    
    # 작업 병렬 처리를 위한 태스크 준비
    tasks = []
    
    # 1. 유사 티켓 검색 태스크
    if include_similar_tickets:
        async def fetch_similar_tickets():
            try:
                # 티켓 임베딩 생성
                ticket_embedding = embed_documents([ticket_full_text])[0]
                
                # 유사 티켓 검색 (현재 티켓은 별도로 필터링 처리)
                similar_tickets_raw = retrieve_top_k_docs(
                    ticket_embedding, 5, search_company_id, doc_type="ticket"  # 조금 더 많이 가져와서 현재 티켓 제외
                )
                
                # 검색 결과를 DocumentInfo 형식으로 변환하며 현재 티켓 제외
                st_results = []
                for i, doc_id in enumerate(similar_tickets_raw.get("ids", [])):
                    # 현재 티켓 ID와 동일한 경우 스킵
                    if str(doc_id) == str(ticket_id) or str(doc_id) == f"ticket-{ticket_id}":
                        continue
                    
                    metadata = similar_tickets_raw.get("metadatas", [])[i] if i < len(similar_tickets_raw.get("metadatas", [])) else {}
                    title = metadata.get("subject", metadata.get("title", f"유사 티켓 {doc_id}"))
                    content = similar_tickets_raw.get("documents", [])[i] if i < len(similar_tickets_raw.get("documents", [])) else "내용 없음"
                    
                    st_results.append(DocumentInfo(
                        title=title,
                        content=content[:500] + "..." if len(content) > 500 else content,
                        source_id=str(doc_id),
                        relevance_score=round(((2 - similar_tickets_raw.get("distances", [])[i]) / 2) * 100, 1) if i < len(similar_tickets_raw.get("distances", [])) else 0.0,
                        doc_type="ticket"
                    ))
                    
                    # 최대 3개까지만 수집
                    if len(st_results) >= 3:
                        break
                
                logger.info(f"유사 티켓 {len(st_results)}개 검색됨")
                return st_results
            except Exception as e:
                logger.error(f"유사 티켓 검색 중 오류 발생: {str(e)}")
                return []  # 오류 시 빈 리스트 반환
                
        tasks.append(fetch_similar_tickets())
    
    # 2. 지식베이스 문서 검색 태스크
    if include_kb_docs:
        async def fetch_kb_documents():
            try:
                # 티켓 임베딩 생성 (이미 생성한 경우 재사용)
                ticket_embedding = embed_documents([ticket_full_text])[0]
                
                # 지식베이스 문서 검색
                kb_docs_raw = retrieve_top_k_docs(
                    ticket_embedding, 3, search_company_id, doc_type="kb"
                )
                
                # 검색 결과를 DocumentInfo 형식으로 변환
                kb_results = []
                for i, doc_id in enumerate(kb_docs_raw.get("ids", [])):
                    metadata = kb_docs_raw.get("metadatas", [])[i] if i < len(kb_docs_raw.get("metadatas", [])) else {}
                    title = metadata.get("title", metadata.get("subject", f"문서 {doc_id}"))
                    content = kb_docs_raw.get("documents", [])[i] if i < len(kb_docs_raw.get("documents", [])) else "내용 없음"
                    
                    kb_results.append(DocumentInfo(
                        title=title,
                        content=content[:500] + "..." if len(content) > 500 else content,
                        source_id=str(doc_id),
                        source_url=metadata.get("url", ""),
                        relevance_score=round(((2 - kb_docs_raw.get("distances", [])[i]) / 2) * 100, 1) if i < len(kb_docs_raw.get("distances", [])) else 0.0,
                        doc_type="kb"
                    ))
                
                logger.info(f"지식베이스 문서 {len(kb_results)}개 검색됨")
                return kb_results
            except Exception as e:
                logger.error(f"지식베이스 문서 검색 중 오류 발생: {str(e)}")
                return []  # 오류 시 빈 리스트 반환
                
        tasks.append(fetch_kb_documents())
    
    # 3. 티켓 요약 생성 태스크
    if include_summary:
        async def generate_summary():
            try:
                logger.info(f"티켓 {ticket_id} 요약 생성 시작")
                
                # 티켓 데이터 유효성 검사
                if not ticket_title and not ticket_body:
                    logger.warning(f"티켓 {ticket_id} 데이터가 부족함 (제목: {bool(ticket_title)}, 내용: {bool(ticket_body)})")
                    return TicketSummaryContent(
                        ticket_summary="티켓 데이터가 부족하여 요약을 생성할 수 없습니다.",
                        key_points=["데이터 부족"],
                        sentiment="중립적",
                        urgency_level="보통"
                    )
                
                # 대화 내역을 안전하게 처리
                conversation_text = ""
                if ticket_conversations:
                    conversation_text = "\n".join(ticket_conversations[:3])
                else:
                    conversation_text = "대화 내역 없음"
                
                # 프롬프트 길이 제한 (토큰 초과 방지)
                max_content_length = 2000
                
                truncated_body = ticket_body[:max_content_length] if ticket_body else "내용 없음"
                if len(ticket_body or "") > max_content_length:
                    truncated_body += "... (내용 축약됨)"
                
                truncated_conversations = conversation_text[:max_content_length]
                if len(conversation_text) > max_content_length:
                    truncated_conversations += "... (대화 내역 축약됨)"
                
                # 간소화된 요약용 프롬프트 생성
                prompt = f"""다음 고객 지원 티켓을 분석하여 JSON 형식으로 응답해주세요:

티켓 제목: {ticket_title or '제목 없음'}

티켓 내용: {truncated_body}

대화 내역: {truncated_conversations}

다음 JSON 형식으로만 응답해주세요:
{{
  "summary": "티켓의 핵심 내용을 3-4줄로 요약",
  "key_points": ["주요 포인트 1", "주요 포인트 2", "주요 포인트 3"],
  "sentiment": "긍정적 또는 중립적 또는 부정적",
  "priority_recommendation": "높음 또는 보통 또는 낮음",
  "category_suggestion": ["기술지원", "문의"],
  "customer_summary": "고객 상황 요약",
  "request_summary": "고객이 요청한 내용",
  "urgency_level": "높음 또는 보통 또는 낮음"
}}"""
                
                logger.info(f"티켓 {ticket_id} LLM 호출 시작 (프롬프트 길이: {len(prompt)} 문자)")
                
                # LLM 호출을 통한 요약 생성
                response = await call_llm(
                    prompt, 
                    system_prompt="당신은 고객 지원 티켓을 분석하는 AI입니다. 반드시 유효한 JSON만 응답하세요."
                )
                
                logger.info(f"티켓 {ticket_id} LLM 응답 받음 (길이: {len(response.text)} 문자)")
                
                # 응답에서 JSON 부분 추출 시도
                summary_data = None
                
                # 1. JSON 코드 블록에서 추출 시도
                json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response.text)
                if json_match:
                    json_str = json_match.group(1).strip()
                    try:
                        summary_data = json.loads(json_str)
                        logger.info(f"티켓 {ticket_id} JSON 코드 블록에서 파싱 성공")
                    except json.JSONDecodeError as e:
                        logger.warning(f"티켓 {ticket_id} JSON 코드 블록 파싱 실패: {e}")
                
                # 2. 직접 JSON 파싱 시도
                if not summary_data:
                    try:
                        # 중괄호로 시작하고 끝나는 부분 찾기
                        json_match = re.search(r'\{[\s\S]*\}', response.text)
                        if json_match:
                            json_str = json_match.group(0)
                            summary_data = json.loads(json_str)
                            logger.info(f"티켓 {ticket_id} 직접 JSON 파싱 성공")
                    except json.JSONDecodeError as e:
                        logger.warning(f"티켓 {ticket_id} 직접 JSON 파싱 실패: {e}")
                
                # 3. JSON 파싱이 모두 실패한 경우 기본값으로 요약 생성
                if not summary_data:
                    logger.warning(f"티켓 {ticket_id} JSON 파싱 실패, 텍스트 기반 요약 생성")
                    summary_data = {
                        "summary": f"티켓 제목: {ticket_title}. {truncated_body[:200]}",
                        "key_points": ["요약 생성 중 오류 발생", "수동 처리 필요"],
                        "sentiment": "중립적",
                        "priority_recommendation": "보통",
                        "category_suggestion": ["기술지원"],
                        "customer_summary": truncated_body[:100] if truncated_body != "내용 없음" else "고객 정보 부족",
                        "request_summary": "명확한 요청 내용 파악 필요",
                        "urgency_level": "보통"
                    }
                
                # 티켓 요약 객체 생성
                ticket_summary = TicketSummaryContent(
                    ticket_summary=summary_data.get("summary", "요약 생성 실패"),
                    key_points=summary_data.get("key_points", []),
                    sentiment=summary_data.get("sentiment", "중립적"),
                    priority_recommendation=summary_data.get("priority_recommendation", "보통"),
                    category_suggestion=summary_data.get("category_suggestion", []),
                    customer_summary=summary_data.get("customer_summary", None),
                    request_summary=summary_data.get("request_summary", None),
                    urgency_level=summary_data.get("urgency_level", "보통")
                )
                
                logger.info(f"티켓 {ticket_id} 요약 생성 완료: {ticket_summary.ticket_summary[:100]}...")
                
                # 캐시에 저장
                ticket_summary_cache[ticket_id] = ticket_summary
                
                return ticket_summary
                
            except Exception as e:
                logger.error(f"티켓 {ticket_id} 요약 생성 중 오류 발생: {str(e)}", exc_info=True)
                # 오류 시 기본 요약 반환
                return TicketSummaryContent(
                    ticket_summary=f"오류로 인해 요약 생성에 실패했습니다. 티켓 제목: {ticket_title or '제목 없음'}",
                    key_points=["요약 생성 오류", "수동 검토 필요"],
                    sentiment="중립적",
                    priority_recommendation="보통",
                    urgency_level="보통"
                )
                
        tasks.append(generate_summary())
    
    # 모든 태스크 병렬 실행
    results = await asyncio.gather(*tasks)
    
    # 결과 처리
    result_idx = 0
    if include_similar_tickets:
        similar_tickets = results[result_idx]
        result_idx += 1
    
    if include_kb_docs:
        kb_documents = results[result_idx]
        result_idx += 1
    
    if include_summary:
        ticket_summary = results[result_idx]
    
    # 컨텍스트 구축 소요 시간
    context_time = time.time() - context_start_time        # 컨텍스트 캐싱 (향후 요청에서 재사용할 수 있도록)
    result = InitResponse(
        ticket_id=ticket_id,
        ticket_data=ticket_metadata,
        ticket_summary=ticket_summary,  # 일관된 필드명 사용
        similar_tickets=similar_tickets,
        kb_documents=kb_documents,
        context_id=context_id,
        metadata={
            "duration_ms": int((time.time() - start_time) * 1000),
            "context_time_ms": int(context_time * 1000),
            "model_used": response.model_used if 'response' in locals() else None,
            "similar_tickets_count": len(similar_tickets),
            "kb_docs_count": len(kb_documents)
        }
    )
    
    # 결과 캐싱
    ticket_context_cache[context_id] = {
        "ticket_id": ticket_id,
        "company_id": search_company_id,
        "ticket_data": ticket_data,
        "similar_tickets": similar_tickets,
        "kb_documents": kb_documents,
        "created_at": time.time()
    }
    
    return result

@app.get("/similar_tickets/{ticket_id}", response_model=SimilarTicketsResponse)
async def get_similar_tickets(ticket_id: str):
    try:
        current_ticket_data = await fetcher.fetch_ticket_details(ticket_id)
        if not current_ticket_data:
            raise HTTPException(status_code=404, detail=f"티켓 ID {ticket_id}를 찾을 수 없습니다.")
        query_text = f"{current_ticket_data.get('subject', '')} {current_ticket_data.get('description_text', '')}"
        if not query_text.strip():
            logger.warning(f"티켓 {ticket_id}에 대한 검색 쿼리 텍스트가 비어있습니다.")
            return SimilarTicketsResponse(ticket_id=ticket_id, similar_tickets=[])
        # 실제 구현에서는 llm_router.generate_embedding 등으로 임베딩 생성 필요
        query_embedding = [0.1] * 768
        logger.info(f"티켓 {ticket_id} 유사 티켓 검색을 위한 임베딩 생성 (더미)")
        similar_tickets_result = retriever.retrieve_top_k_docs(query_embedding=query_embedding, top_k=5, doc_type="ticket")
        similar_tickets_list = []
        if similar_tickets_result and similar_tickets_result.get("ids"):
            for i, doc_id in enumerate(similar_tickets_result["ids"]):
                metadata = similar_tickets_result["metadatas"][i] if i < len(similar_tickets_result.get("metadatas", [])) else {}
                title = metadata.get("title", metadata.get("subject", f"유사 티켓 {doc_id}"))
                summary_text = similar_tickets_result["documents"][i] if i < len(similar_tickets_result.get("documents", [])) else "요약 정보 없음"
                summary = summary_text[:150] + "..." if len(summary_text) > 150 else summary_text
                similar_tickets_list.append(SimilarTicketItem(id=str(doc_id), title=title, ticket_summary=summary))
        logger.info(f"티켓 {ticket_id}에 대한 유사 티켓 {len(similar_tickets_list)}건 검색 완료")
        return SimilarTicketsResponse(ticket_id=ticket_id, similar_tickets=similar_tickets_list)
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"유사 티켓 검색 중 오류 발생 (티켓 ID: {ticket_id}): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"유사 티켓 검색 중 내부 서버 오류 발생: {str(e)}")

@app.get("/related_docs/{ticket_id}", response_model=RelatedDocsResponse)
async def get_related_documents(ticket_id: str):
    try:
        current_ticket_data = await fetcher.fetch_ticket_details(ticket_id)
        if not current_ticket_data:
            raise HTTPException(status_code=404, detail=f"티켓 ID {ticket_id}를 찾을 수 없습니다.")
        query_text = f"{current_ticket_data.get('subject', '')} {current_ticket_data.get('description_text', '')}"
        if not query_text.strip():
            logger.warning(f"티켓 {ticket_id}에 대한 검색 쿼리 텍스트가 비어있습니다.")
            return RelatedDocsResponse(ticket_id=ticket_id, related_documents=[])
        query_embedding = [0.1] * 768
        logger.info(f"티켓 {ticket_id} 관련 문서 검색을 위한 임베딩 생성 (더미)")
        related_docs_result = retriever.retrieve_top_k_docs(query_embedding=query_embedding, top_k=5, doc_type="kb")
        related_docs_list = []
        if related_docs_result and related_docs_result.get("ids"):
            for i, doc_id in enumerate(related_docs_result["ids"]):
                metadata = related_docs_result["metadatas"][i] if i < len(related_docs_result.get("metadatas", [])) else {}
                title = metadata.get("title", f"관련 문서 {doc_id}")
                url = metadata.get("url", None)
                summary_text = related_docs_result["documents"][i] if i < len(related_docs_result.get("documents", [])) else "요약 정보 없음"
                summary = summary_text[:150] + "..." if len(summary_text) > 150 else summary_text
                source_type = metadata.get("source_type", "kb")
                related_docs_list.append(RelatedDocumentItem(id=str(doc_id), title=title, doc_summary=summary, url=url, source_type=source_type))
        logger.info(f"티켓 {ticket_id}에 대한 관련 문서 {len(related_docs_list)}건 검색 완료")
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
    
    # 컨텍스트 구축
    context_start_time = time.time()
    
    # 티켓 기본 컨텍스트
    ticket_context = f"""티켓 제목: {ticket_title}

티켓 내용:
{ticket_body}

대화 내역:
{' '.join(ticket_conversations[:3])}  # 처음 3개 대화만 포함
"""
    
    # 유사 티켓 컨텍스트
    similar_tickets_context = ""
    if similar_tickets:
        similar_tickets_context = "유사 티켓 정보:\n\n"
        for idx, ticket in enumerate(similar_tickets[:2]):  # 최대 2개만 포함
            similar_tickets_context += f"[유사 티켓 {idx+1}]\n"
            similar_tickets_context += f"제목: {ticket.title}\n"
            similar_tickets_context += f"내용: {ticket.content[:300]}...\n\n"
    
    # 지식베이스 문서 컨텍스트
    kb_docs_context = ""
    if kb_documents:
        kb_docs_context = "관련 지식베이스 문서:\n\n"
        for idx, doc in enumerate(kb_documents):
            kb_docs_context += f"[문서 {idx+1}: {doc.title}]\n"
            kb_docs_context += f"{doc.content[:500]}...\n\n"
            if doc.source_url:
                kb_docs_context += f"URL: {doc.source_url}\n\n"
    
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
    
    style_instruction = style_guide.get(request.style, style_guide["professional"])
    tone_instruction = tone_guide.get(request.tone, tone_guide["helpful"])
    
    # 프롬프트 구성
    prompt = f"""다음 고객 지원 티켓에 대한 응답을 생성해주세요.

[티켓 정보]
{ticket_context}

[참고 자료]
{kb_docs_context}
{similar_tickets_context}

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
        
        # 메타데이터 구성
        metadata = {
            "duration_ms": int(total_time * 1000),
            "context_time_ms": int(context_time * 1000),
            "llm_time_ms": int(llm_time * 1000),
            "model_used": response.model_used,
            "paragraph_count": len(reply_text.split("\n\n"))
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
