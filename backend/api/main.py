"""
Freshdesk Custom App 백엔드 서비스

이 프로젝트는 Freshdesk Custom App(Prompt Canvas)을 위한 백엔드 서비스입니다.
RAG(Retrieval-Augmented Generation) 기술을 활용하여 Freshdesk 티켓과 지식베이스를 기반으로
AI 기반 응답 생성 기능을 제공합니다.

프로젝트 규칙 및 가이드라인: /PROJECT_@app.post("/query", response_model=QueryResponse)
async def query_endpoint(req: QueryRequest, company_id: str = Depends(get_company_id)):
    # 성능 측정 시작
    start_time = time.time()
    search_start = time.time()
    
    # 1. 검색 단계
    query_embedding = embed_documents([req.query])[0]
    results = retrieve_top_k_docs(query_embedding, req.top_k, company_id)
    search_time = time.time() - search_start조
"""

import uuid
import time
from fastapi import FastAPI, HTTPException, Depends, Header
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Union
import re
from cachetools import TTLCache, cached
from cachetools.keys import hashkey
from functools import partial
import logging
import prometheus_client
from prometheus_client import Counter, Histogram
from datetime import datetime
import json

from core.embedder import embed_documents
from core.retriever import retrieve_top_k_docs, retrieve_faqs
from core.llm_router import generate_text, LLMResponse
from core.context_builder import build_optimized_context
from core.vectordb import vector_db
from freshdesk import fetcher
from core import llm_router, context_builder, retriever

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


# 요청/응답 모델 정의를 _query_cache_key 함수보다 위로 이동
class QueryRequest(BaseModel):
    query: str
    top_k: int = 3
    use_blocks: bool = False  # 블록 기반 응답 포맷 사용 여부
    answer_instructions: Optional[str] = None  # 사용자가 제공하는 답변 지침
    ticket_id: Optional[str] = None # 현재 처리 중인 티켓 ID (선택 사항)
    # faq_top_k: int = FAQ_TOP_K # 요청별 FAQ top_k 설정 (필요시)


# 회사 ID 의존성 함수
async def get_company_id(
    x_company_id: Optional[str] = Header(None, alias="X-Company-ID")
) -> str:
    """
    현재 사용자의 회사 ID를 반환합니다.
    실제 환경에서는 인증 토큰에서 추출하는 방식으로 변경해야 합니다.
    이 예제에서는 X-Company-ID 헤더를 사용합니다.
    """
    if not x_company_id:
        # 사용자에게 보여지는 오류 메시지는 한글로 작성합니다.
        raise HTTPException(status_code=400, detail="X-Company-ID 헤더가 필요합니다.")
    return x_company_id


# 캐시 키 생성을 위한 헬퍼 함수
def _query_cache_key(func_name: str, req: QueryRequest, company_id: str):
    # 함수 이름, 회사 ID, 쿼리 내용, top_k, 블록 사용 여부, 답변 지침, 티켓 ID를 기반으로 해시 키를 생성합니다.
    return hashkey(func_name, company_id, req.query, req.top_k, req.use_blocks, req.answer_instructions, req.ticket_id)


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


class Block(BaseModel):
    """응답 블록 기본 모델"""

    id: str = Field(default_factory=lambda: f"blk_{uuid.uuid4().hex[:6]}")
    type: str
    content: str
    source: Optional[Source] = None


class TextBlock(Block):
    """텍스트 블록"""

    type: str = "text"


class ImageBlock(Block):
    """이미지 블록"""

    type: str = "image"
    url: str
    content: str = ""  # 이미지 설명으로 사용
    description: str = ""


class BlockBasedResponse(BaseModel):
    """블록 기반 응답 모델"""

    blocks: List[Union[TextBlock, ImageBlock]]
    context_docs: List[DocumentInfo]
    metadata: Dict[str, Any] = Field(default_factory=dict)


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


def build_prompt(context: str, query: str, use_blocks: bool = False, answer_instructions: Optional[str] = None) -> str:
    """
    LLM에 입력할 프롬프트를 생성합니다.
    
    Args:
        context: 검색된 문서 컨텍스트
        query: 사용자 질문
        use_blocks: 블록 기반 응답 여부
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

    if use_blocks:
        # 블록 기반 응답을 위한 확장 프롬프트를 구성합니다.
        extended_prompt = (
            base_prompt
            + """

답변은 관련 문서의 출처를 문단별로 명시해주세요. 예를 들어:

1. 첫 번째 문단 내용... (출처: 문서 제목)
2. 두 번째 문단 내용... (출처: 다른 문서 제목)

이렇게 구성하면 저는 응답을 개별 블록으로 구성할 수 있습니다."""
        )
        return extended_prompt

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


def parse_llm_response_to_blocks(
    answer: str, structured_docs: List[DocumentInfo]
) -> List[Union[TextBlock, ImageBlock]]:
    """
    LLM 응답을 블록 단위로 분리하고 출처 정보를 연결합니다.
    """
    blocks = []

    # 문단별로 나눕니다.
    paragraphs = [p for p in answer.split("\n\n") if p.strip()]

    # 문서 제목을 문서 정보에 매핑하는 딕셔너리를 생성합니다.
    title_to_doc = {doc.title: doc for doc in structured_docs if doc.title}

    for i, paragraph in enumerate(paragraphs):
        # 출처 정보 추출을 위한 정규 표현식 패턴 - "(출처: 문서 제목)" 형식을 찾습니다.
        source_match = re.search(r"\(출처:\s*([^)]+)\)", paragraph)
        source = None
        content = paragraph

        if source_match:
            source_title = source_match.group(1).strip()
            # 출처 정보를 제거한 내용만 저장합니다.
            content = paragraph.replace(source_match.group(0), "").strip()

            # 출처 문서를 찾습니다.
            if source_title in title_to_doc:
                doc = title_to_doc[source_title]
                source = Source(title=doc.title, url=doc.source_url)

        # 텍스트 블록을 생성합니다.
        text_block = TextBlock(content=content, source=source)
        blocks.append(text_block)

    return blocks


def convert_image_info_to_blocks(context_images: List[dict]) -> List[ImageBlock]:
    """
    이미지 정보를 이미지 블록으로 변환합니다.
    """
    image_blocks = []

    for img in context_images:
        if img.get("url"):
            image_block = ImageBlock(
                url=img["url"],
                description=img.get("name", "이미지"), # 이미지 이름이 없으면 '이미지'로 기본 설정
                content=img.get("title", ""), # 이미지 제목이 없으면 빈 문자열로 설정
            )
            image_blocks.append(image_block)

    return image_blocks


@app.get("/metrics")
async def metrics():
    return prometheus_client.generate_latest()


@app.post("/query", response_model=QueryResponse)
@cached(cache, key=partial(_query_cache_key, "query_endpoint"))
async def query_endpoint(req: QueryRequest, company_id: str = Depends(get_company_id)):
    # 성능 측정을 시작합니다.
    start_time = time.time()
    
    ticket_title = ""
    ticket_body = ""
    ticket_conversations = []
    ticket_context_for_query = ""
    ticket_context_for_llm = ""

    if req.ticket_id:
        logger.info(f"티켓 ID {req.ticket_id}에 대한 정보 조회를 시도합니다.")
        # vector_db.get_by_id를 사용하여 티켓 정보 조회
        ticket_data = vector_db.get_by_id(id=req.ticket_id, company_id=company_id)
        
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
    
    # 티켓 데이터와 지식베이스 문서를 모두 검색합니다.
    top_k_per_type = max(1, req.top_k // 2)
    
    ticket_results = retrieve_top_k_docs(
        query_embedding, 
        top_k_per_type, 
        company_id, 
        doc_type="ticket"
    )
    
    kb_results = retrieve_top_k_docs(
        query_embedding, 
        top_k_per_type, 
        company_id, 
        doc_type="kb"
    )

    # FAQ를 검색합니다.
    faq_items = retrieve_faqs(
        query_embedding=query_embedding,
        top_k=FAQ_TOP_K, # 전역 상수 사용
        company_id=company_id,
        min_score=FAQ_MIN_SCORE # 전역 상수 사용
    )

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
    for i, metadata in enumerate(optimized_metadatas): # optimized_metadatas 사용
        # 'image_attachments' 또는 'attachments' 키에서 이미지 정보 가져오기
        image_attachments = metadata.get("image_attachments", metadata.get("attachments", ""))
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
        # 사용자 지정 답변 지침이 있는 경우 시스템 프롬프트에 추가합니다.
        system_prompt = None
        if req.answer_instructions:
            system_prompt = f"당신은 친절한 고객 지원 AI입니다. 다음 지침에 따라 응답해 주세요: {req.answer_instructions}"
            
        response = await call_llm(prompt, system_prompt=system_prompt)
        answer = response.text
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
        "context_docs_count": len(structured_docs) # 사용된 컨텍스트 문서 수
    }

    return QueryResponse(
        answer=answer, 
        context_docs=structured_docs, 
        context_images=context_images,
        metadata=metadata
    )


@app.post("/query/blocks", response_model=BlockBasedResponse)
@cached(cache, key=partial(_query_cache_key, "query_blocks_endpoint"))
async def query_blocks_endpoint(req: QueryRequest, company_id: str = Depends(get_company_id)):
    # 성능 측정을 시작합니다.
    start_time = time.time()

    ticket_title = ""
    ticket_body = ""
    ticket_conversations = []
    ticket_context_for_query = ""
    ticket_context_for_llm = ""

    if req.ticket_id:
        logger.info(f"티켓 ID {req.ticket_id}에 대한 정보 조회를 시도합니다 (블록).")
        ticket_data = vector_db.get_by_id(id=req.ticket_id, company_id=company_id)
        
        if ticket_data and ticket_data.get("metadata"):
            metadata = ticket_data["metadata"]
            ticket_title = metadata.get("subject", f"티켓 ID {req.ticket_id} 관련 문의 (블록)")
            ticket_body = metadata.get("text", metadata.get("description_text", "티켓 본문 정보 없음 (블록)"))
            raw_conversations = metadata.get("conversations", [])

            if isinstance(raw_conversations, list):
                ticket_conversations = [str(conv) for conv in raw_conversations]
            elif isinstance(raw_conversations, str):
                try:
                    parsed_convs = json.loads(raw_conversations)
                    if isinstance(parsed_convs, list):
                        ticket_conversations = [str(conv) for conv in parsed_convs]
                except json.JSONDecodeError:
                    ticket_conversations = [raw_conversations]
            
            if not ticket_conversations and metadata.get("conversation_summary"):
                 ticket_conversations = [str(metadata.get("conversation_summary"))]

            logger.info(f"티켓 ID {req.ticket_id} 정보 조회 완료 (블록): 제목='{ticket_title[:50]}...'")
        else:
            logger.warning(f"티켓 ID {req.ticket_id} 정보를 Qdrant에서 찾을 수 없거나 메타데이터가 없습니다 (블록).")
            ticket_title = f"티켓 ID {req.ticket_id} 정보 없음 (블록)"
            ticket_body = "해당 티켓 정보를 찾을 수 없습니다 (블록)."
        
        ticket_context_for_query = f"현재 티켓 제목: {ticket_title}\\n현재 티켓 본문: {ticket_body}\\n\\n대화 내용:\\n" + "\\n".join(ticket_conversations)
        ticket_context_for_llm = f"\\n[현재 티켓 정보]\\n제목: {ticket_title}\\n본문: {ticket_body}\\n대화 요약:\\n" + "\\n".join(ticket_conversations) + "\\n"

    search_start = time.time()
    # 1. 검색 단계
    query_for_embedding_str = f"{ticket_context_for_query}\\n\\n사용자 질문: {req.query}" if req.ticket_id else req.query
    query_embedding = embed_documents([query_for_embedding_str])[0]
    
    top_k_per_type = max(1, req.top_k // 2)
    
    ticket_results = retrieve_top_k_docs(
        query_embedding, top_k_per_type, company_id, doc_type="ticket"
    )
    kb_results = retrieve_top_k_docs(
        query_embedding, top_k_per_type, company_id, doc_type="kb"
    )
    faq_items = retrieve_faqs(
        query_embedding=query_embedding, top_k=FAQ_TOP_K, company_id=company_id, min_score=FAQ_MIN_SCORE
    )

    faq_docs_content = []
    faq_metadatas_list = []
    faq_distances = []

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
        faq_distances.append(1.0 - faq.get("score", 0.0))

    for meta in ticket_results["metadatas"]:
        meta["source_type"] = "ticket"
    for meta in kb_results["metadatas"]:
        meta["source_type"] = "kb"

    all_docs_content = ticket_results["documents"] + kb_results["documents"] + faq_docs_content
    all_metadatas = ticket_results["metadatas"] + kb_results["metadatas"] + faq_metadatas_list
    all_distances = ticket_results["distances"] + kb_results["distances"] + faq_distances
    
    # 유사도 기준으로 정렬합니다.
    # combined = list(zip(all_docs_content, all_metadatas, all_distances)) # 변수명 변경
    sorted_results_combined = sorted(zip(all_docs_content, all_metadatas, all_distances), key=lambda x: x[2])
    
    final_top_k = req.top_k # 필요시 이 값을 조정
    if len(sorted_results_combined) > final_top_k:
        sorted_results_combined = sorted_results_combined[:final_top_k]
        
    docs, metadatas, distances = zip(*sorted_results_combined) if sorted_results_combined else ([], [], [])
    docs, metadatas, distances = list(docs), list(metadatas), list(distances)
    
    search_time = time.time() - search_start
    
    # 2. 컨텍스트 최적화 단계: 검색된 문서를 LLM 입력에 적합하도록 가공합니다.
    context_start = time.time()
    
    # 최적화된 컨텍스트를 구성합니다. (검색된 문서들로부터)
    base_context, optimized_metadatas, context_meta = build_optimized_context(docs, metadatas)
    
    # LLM에 전달할 최종 컨텍스트 (티켓 정보 + 검색된 문서 정보)
    final_context_for_llm = f"{ticket_context_for_llm}{base_context}"

    # 블록 기반 응답을 위한 프롬프트를 생성합니다.
    prompt = build_prompt(final_context_for_llm, req.query, use_blocks=True, answer_instructions=req.answer_instructions)
    
    context_time = time.time() - context_start # context_time 계산 추가

    # 구조화된 문서 정보를 생성합니다.
    structured_docs = []
    for i, (doc_content_item, metadata_item, distance_or_score_metric) in enumerate(zip(docs, metadatas, distances)):
        title = metadata_item.get("title", "")
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
            relevance_score = round(metadata_item.get("original_score", 0.0) * 100, 1)
        else:
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

    context_images = []
    for i, metadata in enumerate(optimized_metadatas): # optimized_metadatas 사용
        # 'image_attachments' 또는 'attachments' 키에서 이미지 정보 가져오기
        image_attachments = metadata.get("image_attachments", metadata.get("attachments", ""))
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
        # 사용자 지정 답변 지침이 있는 경우 시스템 프롬프트에 추가합니다.
        system_prompt = None
        if req.answer_instructions:
            system_prompt = f"당신은 친절한 고객 지원 AI입니다. 다음 지침에 따라 응답해 주세요: {req.answer_instructions}"
            
        response = await call_llm(prompt, system_prompt=system_prompt)
        answer = response.text
    except Exception as e:
        logger.error(f"LLM 호출 중 오류 발생: {str(e)}") # 오류 로깅 메시지를 한글로 변경합니다.
        # 사용자에게 보여지는 오류 메시지는 한글로 작성합니다.
        raise HTTPException(status_code=500, detail=f"LLM 호출 중 오류가 발생했습니다: {str(e)}")
    llm_time = time.time() - llm_start # LLM 호출 소요 시간을 계산합니다.

    # 텍스트 응답을 블록으로 변환합니다.
    text_blocks = parse_llm_response_to_blocks(answer, structured_docs)

    # 이미지 정보를 이미지 블록으로 변환합니다.
    image_blocks = convert_image_info_to_blocks(context_images)

    # 모든 블록을 하나의 리스트로 합칩니다.
    all_blocks = text_blocks + image_blocks
    
    # 총 처리 시간을 계산합니다.
    total_time = time.time() - start_time
    
    # 성능을 로깅합니다.
    logger.info(f"성능(블록): company_id=\'{company_id}\', query=\'{req.query[:50]}...\', 검색시간={search_time:.2f}s, 컨텍스트생성시간={context_time:.2f}s, LLM호출시간={llm_time:.2f}s, 총시간={total_time:.2f}s")
    
    # 메타데이터를 구성합니다.
    metadata = {
        "duration_ms": int(total_time * 1000), # 총 소요 시간 (밀리초)
        "search_time_ms": int(search_time * 1000), # 검색 소요 시간 (밀리초)
        "context_time_ms": int(context_time * 1000), # 컨텍스트 생성 소요 시간 (밀리초)
        "llm_time_ms": int(llm_time * 1000), # LLM 호출 소요 시간 (밀리초)
        "model_used": response.model_used, # 사용된 LLM 모델
        "token_count": context_meta.get("token_count", 0), # 컨텍스트 토큰 수
        "blocks_count": len(all_blocks), # 생성된 블록 수
        "context_docs_count": len(structured_docs) # 사용된 컨텍스트 문서 수
    }

    return BlockBasedResponse(blocks=all_blocks, context_docs=structured_docs, metadata=metadata)


# --- 추가: 티켓 요약, 유사 티켓, 관련 문서용 모델 및 엔드포인트 복구 ---
# Pydantic Models for New Endpoints
class TicketSummaryContent(BaseModel):
    customer_summary: Optional[str] = Field(default=None, description="고객 관련 주요 내용 요약")
    request_summary: Optional[str] = Field(default=None, description="고객의 주요 요청 사항 요약")
    urgency_level: Optional[str] = Field(default=None, description="티켓의 긴급도 (예: 높음, 보통, 낮음)")

class InitResponse(BaseModel):
    ticket_id: str = Field(description="처리 대상 티켓의 ID")
    ticket_summary: TicketSummaryContent = Field(description="티켓 내용에 대한 AI 생성 요약")

class SimilarTicketItem(BaseModel):
    id: str = Field(description="유사 티켓의 ID")
    title: Optional[str] = Field(default=None, description="유사 티켓의 제목")
    summary: Optional[str] = Field(default=None, description="유사 티켓의 내용 요약")

class SimilarTicketsResponse(BaseModel):
    ticket_id: str = Field(description="원본 티켓의 ID")
    similar_tickets: List[SimilarTicketItem] = Field(description="검색된 유사 티켓 목록")

class RelatedDocumentItem(BaseModel):
    id: str = Field(description="관련 문서의 고유 ID")
    title: Optional[str] = Field(default=None, description="관련 문서의 제목")
    summary: Optional[str] = Field(default=None, description="관련 문서의 내용 요약")
    url: Optional[str] = Field(default=None, description="관련 문서의 URL (해당하는 경우)")
    source_type: Optional[str] = Field(default=None, description="문서 출처 유형 (예: 'kb', 'faq')")

class RelatedDocsResponse(BaseModel):
    ticket_id: str = Field(description="원본 티켓의 ID")
    related_documents: List[RelatedDocumentItem] = Field(description="검색된 관련 문서 목록")

# 캐시 설정: 티켓 요약 캐시 (최대 100개, 1시간 TTL)
ticket_summary_cache = TTLCache(maxsize=100, ttl=3600)

@app.get("/init/{ticket_id}", response_model=InitResponse)
async def get_initial_context(ticket_id: str):
    cached_summary_content = ticket_summary_cache.get(ticket_id)
    if cached_summary_content:
        logger.info(f"캐시에서 티켓 {ticket_id}의 요약 정보를 반환합니다.")
        return InitResponse(ticket_id=ticket_id, ticket_summary=cached_summary_content)
    logger.info(f"티켓 {ticket_id}의 요약 정보를 생성합니다.")
    try:
        ticket_data = await fetcher.fetch_ticket_details(ticket_id)
        if not ticket_data:
            raise HTTPException(status_code=404, detail=f"티켓 {ticket_id}를 찾을 수 없습니다.")
        summary_dict = await llm_router.generate_ticket_summary(ticket_data)
        ticket_summary = TicketSummaryContent(**summary_dict)
        ticket_summary_cache[ticket_id] = ticket_summary
        logger.info(f"티켓 {ticket_id}의 요약 정보를 생성하고 캐시에 저장했습니다.")
        return InitResponse(ticket_id=ticket_id, ticket_summary=ticket_summary)
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"티켓 {ticket_id} 초기 컨텍스트 생성 중 오류 발생: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"티켓 {ticket_id} 처리 중 내부 서버 오류 발생")

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
                similar_tickets_list.append(SimilarTicketItem(id=str(doc_id), title=title, summary=summary))
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
                related_docs_list.append(RelatedDocumentItem(id=str(doc_id), title=title, summary=summary, url=url, source_type=source_type))
        logger.info(f"티켓 {ticket_id}에 대한 관련 문서 {len(related_docs_list)}건 검색 완료")
        return RelatedDocsResponse(ticket_id=ticket_id, related_documents=related_docs_list)
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"관련 문서 검색 중 오류 발생 (티켓 ID: {ticket_id}): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"관련 문서 검색 중 내부 서버 오류 발생: {str(e)}")
