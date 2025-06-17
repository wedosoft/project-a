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
import random
import time
from datetime import datetime
from functools import partial
from typing import Any, Dict, List, Optional

import prometheus_client

# 첨부파일 API 라우터 import
from api.attachments import router as attachments_router

# 데이터 수집 함수 import
from api.ingest import ingest
from cachetools import TTLCache, cached
from cachetools.keys import hashkey
from core import llm_router, retriever
from core.context_builder import build_optimized_context
from core.embedder import embed_documents
from core.llm_router import LLMResponse, generate_text
from core.retriever import retrieve_top_k_docs
from core.vectordb import vector_db
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import StreamingResponse
from freshdesk import fetcher
from pydantic import BaseModel, Field, field_validator

# Prometheus 메트릭 정의
# LLM 관련 메트릭은 llm_router.py에서 정의되어 있으므로 중복 방지를 위해 여기서는 HTTP 요청 관련 메트릭만 정의
# HTTP 요청 관련 메트릭은 필요시 추후 추가 가능
# 현재는 /metrics 엔드포인트만 제공하여 llm_router에서 수집된 메트릭을 노출

# FastAPI 앱 생성
app = FastAPI()

# CORS 미들웨어 설정 - Freshdesk FDK 환경에서의 크로스 도메인 요청 허용
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 개발용: 모든 도메인 허용 (운영시에는 특정 도메인으로 제한)
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],  # OPTIONS 메서드 허용 (preflight 요청)
    allow_headers=["*"],  # 모든 헤더 허용
)

# 첨부파일 라우터 등록
app.include_router(attachments_router)

# 인메모리 캐시 설정 (환경변수에서 가져옴)
# 회사 ID와 요청 매개변수를 기반으로 캐시 키를 생성합니다.
cache = TTLCache(
    maxsize=int(os.getenv("CACHE_MAXSIZE", "100")), 
    ttl=int(os.getenv("CACHE_TTL", "600"))
)

# 🛡️ 안전한 티켓 요약 캐시 (구조화된 데이터로 관리)
ticket_summary_cache = {}

def cleanup_expired_cache():
    """
    만료된 캐시 엔트리를 정리하는 함수
    - 30분 이상 된 캐시 제거
    - 메모리 사용량 최적화
    """
    current_time = time.time()
    expired_keys = []
    
    for key, data in ticket_summary_cache.items():
        if isinstance(data, dict) and 'cache_timestamp' in data:
            cache_age_minutes = (current_time - data['cache_timestamp']) / 60
            if cache_age_minutes > 30:  # 30분 이상 된 캐시
                expired_keys.append(key)
        else:
            # 구조화되지 않은 레거시 캐시는 즉시 제거
            expired_keys.append(key)
    
    for key in expired_keys:
        del ticket_summary_cache[key]
    
    if expired_keys:
        logger.info(f"🧹 만료된 캐시 {len(expired_keys)}개 정리 완료")

def validate_cache_integrity(company_id: str):
    """
    특정 company_id에 대한 캐시 무결성 검증
    다른 회사 데이터가 섞였는지 확인
    """
    invalid_keys = []
    
    for key, data in ticket_summary_cache.items():
        if isinstance(data, dict) and 'company_id' in data:
            if data['company_id'] != company_id and company_id in key:
                # 캐시 키에는 해당 company_id가 있지만 데이터는 다른 회사
                invalid_keys.append(key)
                logger.error(f"🚨 캐시 무결성 오류 발견: {key} - 예상 company_id: {company_id}, 실제: {data['company_id']}")
    
    for key in invalid_keys:
        del ticket_summary_cache[key]
    
    if invalid_keys:
        logger.warning(f"🛡️ 무결성 오류 캐시 {len(invalid_keys)}개 제거됨")

# 정기적으로 캐시 정리 (요청마다 실행하지 않고 가끔씩만)
def periodic_cache_cleanup():
    """10% 확률로 캐시 정리 실행 (성능 영향 최소화)"""
    if random.random() < 0.1:  # 10% 확률
        cleanup_expired_cache()

# 성능 로깅을 위한 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
    handlers=[
        logging.StreamHandler()  # 표준 출력으로 로그 출력 (Docker에서 캡처됨)
    ]
)
logger = logging.getLogger(__name__)

# 애플리케이션 시작 로그
logger.info("FastAPI 백엔드 서버 초기화 완료")


# 헬스체크 응답 모델
class HealthResponse(BaseModel):
    """헬스체크 응답 모델"""
    status: str = Field(description="서버 상태 (healthy, unhealthy)")
    timestamp: str = Field(description="응답 생성 시간")
    version: str = Field(description="API 버전")
    services: Dict[str, Any] = Field(description="각 서비스 상태 정보")


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    백엔드 서버 및 연결된 서비스들의 상태를 확인하는 헬스체크 엔드포인트
    
    이 엔드포인트는 다음 서비스들의 상태를 확인합니다:
    - Qdrant Vector Database 연결 상태
    - LLM Router 서비스 상태
    - 캐시 시스템 상태
    
    Returns:
        HealthResponse: 서버 및 서비스 상태 정보
    """
    logger.info("헬스체크 요청 수신")
    
    services_status = {}
    overall_status = "healthy"
    
    try:
        # Qdrant Vector DB 상태 확인
        try:
            # vector_db 인스턴스가 정상적으로 연결되어 있는지 확인
            # get_collection_info는 인자가 필요없는 메서드입니다
            qdrant_info = vector_db.get_collection_info()
            services_status["qdrant"] = {
                "status": "healthy",
                "connected": True,
                "collection_exists": qdrant_info is not None
            }
            logger.info("Qdrant Vector DB 상태: 정상")
        except Exception as e:
            services_status["qdrant"] = {
                "status": "unhealthy",
                "connected": False,
                "error": str(e)
            }
            overall_status = "unhealthy"
            logger.warning(f"Qdrant Vector DB 상태: 비정상 - {str(e)}")
        
        # LLM Router 상태 확인
        try:
            # LLM Router가 초기화되어 있는지 확인 (간단한 API 키 체크)
            available_models = []
            if os.getenv("ANTHROPIC_API_KEY"):
                available_models.append("anthropic")
            if os.getenv("OPENAI_API_KEY"):
                available_models.append("openai")
            if os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"):
                available_models.append("google")
            
            services_status["llm_router"] = {
                "status": "healthy" if available_models else "unhealthy",
                "available_models": available_models,
                "initialized": len(available_models) > 0
            }
            logger.info(f"LLM Router 상태: 정상 (사용 가능한 모델: {available_models})")
        except Exception as e:
            services_status["llm_router"] = {
                "status": "unhealthy",
                "initialized": False,
                "error": str(e)
            }
            overall_status = "unhealthy"
            logger.warning(f"LLM Router 상태: 비정상 - {str(e)}")
        
        # 캐시 시스템 상태 확인
        try:
            cache_info = {
                "main_cache_size": len(cache),
                "main_cache_maxsize": cache.maxsize,
                "ticket_cache_size": len(ticket_context_cache),
                "ticket_cache_maxsize": ticket_context_cache.maxsize
            }
            services_status["cache"] = {
                "status": "healthy",
                "info": cache_info
            }
            logger.info("캐시 시스템 상태: 정상")
        except Exception as e:
            services_status["cache"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            overall_status = "unhealthy"
            logger.warning(f"캐시 시스템 상태: 비정상 - {str(e)}")
        
        return HealthResponse(
            status=overall_status,
            timestamp=datetime.now().isoformat(),
            version="1.0.0",
            services=services_status
        )
        
    except Exception as e:
        logger.error(f"헬스체크 중 예외 발생: {str(e)}")
        return HealthResponse(
            status="unhealthy",
            timestamp=datetime.now().isoformat(),
            version="1.0.0",
            services={
                "error": str(e)
            }
        )


# 티켓 초기화 컨텍스트 캐시 (티켓 ID를 키로 사용)
ticket_context_cache = TTLCache(
    maxsize=int(os.getenv("TICKET_CONTEXT_CACHE_MAXSIZE", "1000")), 
    ttl=int(os.getenv("TICKET_CONTEXT_CACHE_TTL", "3600"))
)  # 환경변수에서 설정 가져옴


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


class IngestRequest(BaseModel):
    """
    데이터 수집 요청 모델
    """
    incremental: bool = True  # 증분 업데이트 모드 여부
    purge: bool = False  # 기존 데이터 삭제 여부
    process_attachments: bool = True  # 첨부파일 처리 여부
    force_rebuild: bool = False  # 데이터베이스 강제 재구축 여부
    include_kb: bool = True  # 지식베이스 데이터 포함 여부


class IngestResponse(BaseModel):
    """
    데이터 수집 응답 모델
    """
    success: bool
    message: str
    start_time: str
    end_time: Optional[str] = None
    duration_seconds: Optional[float] = None
    documents_processed: Optional[int] = None
    error: Optional[str] = None


# 회사 ID 의존성 함수
async def get_company_id(
    x_freshdesk_domain: Optional[str] = Header(None, alias="X-Freshdesk-Domain"),
    x_company_id: Optional[str] = Header(None, alias="X-Company-ID")
) -> str:
    """
    현재 사용자의 회사 ID를 반환합니다.
    우선순위:
    1. X-Freshdesk-Domain 헤더에서 company_id 추출 (iparams에서 전달된 값)
    2. X-Company-ID 헤더 직접 사용
    3. 환경변수 COMPANY_ID (개발 환경용)
    
    Returns:
        추출된 company_id
        
    Raises:
        HTTPException: 모든 방법으로 company_id를 찾을 수 없는 경우
    """
    company_id = None
    
    # 1순위: X-Freshdesk-Domain에서 company_id 추출 (iparams 통합)
    if x_freshdesk_domain:
        try:
            from freshdesk.fetcher import extract_company_id_from_domain
            company_id = extract_company_id_from_domain(x_freshdesk_domain)
            logger.info(f"company_id를 Freshdesk 도메인에서 추출: {company_id}")
        except Exception as e:
            logger.warning(f"Freshdesk 도메인에서 company_id 추출 실패: {e}")
    
    # 2순위: X-Company-ID 헤더 직접 사용
    if not company_id and x_company_id:
        company_id = x_company_id
        logger.info(f"company_id를 X-Company-ID 헤더에서 사용: {company_id}")
    
    # 3순위: 환경변수 (개발 환경용)
    if not company_id:
        import os
        company_id = os.getenv("COMPANY_ID")
        if company_id:
            logger.info(f"company_id를 환경변수에서 사용: {company_id}")
    
    # 모든 방법으로 찾을 수 없는 경우
    if not company_id:
        raise HTTPException(
            status_code=400,
            detail=(
                "company_id를 찾을 수 없습니다. "
                "iparams에서 설정한 Freshdesk 도메인이 올바르게 전달되었는지 확인하거나, "
                "개발 환경의 경우 COMPANY_ID 환경변수를 설정해주세요."
            )
        )
    
    # 보안: 예시 company_id 차단
    invalid_company_ids = [
        "example", "test", "demo", "sample", "company", 
        "your-company", "default", "wedosoft-test"
    ]
    if company_id.lower() in invalid_company_ids:
        raise HTTPException(
            status_code=400,
            detail=f"유효하지 않은 company_id입니다: {company_id}. 실제 고객사 ID를 사용해주세요."
        )
    
    return company_id


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


# SimilarTicketItem과 RelatedDocumentItem을 먼저 정의
class SimilarTicketItem(BaseModel):
    """유사 티켓 정보 모델"""
    id: str = Field(description="유사 티켓의 ID")
    title: Optional[str] = Field(default=None, description="유사 티켓의 제목")
    issue: Optional[str] = Field(default=None, description="문제 상황 요약")
    solution: Optional[str] = Field(default=None, description="해결책 요약")
    ticket_url: Optional[str] = Field(default=None, description="원본 티켓 링크")
    similarity_score: Optional[float] = Field(default=None, description="유사도 점수 (0.0 ~ 1.0)")


class RelatedDocumentItem(BaseModel):
    """관련 문서 정보 모델"""
    id: str = Field(description="관련 문서의 고유 ID")
    title: Optional[str] = Field(default=None, description="관련 문서의 제목")
    doc_summary: Optional[str] = Field(default=None, description="관련 문서의 내용 요약")
    url: Optional[str] = Field(default=None, description="관련 문서의 URL (해당하는 경우)")
    source_type: Optional[str] = Field(default=None, description="문서 출처 유형 (예: 'kb')")
    similarity_score: Optional[float] = Field(default=None, description="유사도 점수 (0.0 ~ 1.0)")


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
    similar_tickets: List[SimilarTicketItem] = Field(default_factory=list, description="유사 티켓 목록")  # 유사 티켓 정보
    kb_documents: List[RelatedDocumentItem] = Field(default_factory=list, description="지식베이스 문서 목록")  # 관련 지식베이스 문서
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
    # 1. 검색 단계: 중복 임베딩 생성을 방지하여 성능 최적화
    # 티켓 ID가 있는 경우, 티켓 내용을 포함하여 임베딩할 쿼리 생성
    query_for_embedding_str = f"{ticket_context_for_query}\\n\\n사용자 질문: {req.query}" if req.ticket_id else req.query
    
    # 단일 임베딩 생성 (중복 방지로 성능 향상)
    logger.info(f"⚡ 통합 임베딩 생성 시작 (쿼리 길이: {len(query_for_embedding_str)})")
    embedding_start = time.time()
    query_embedding = embed_documents([query_for_embedding_str])[0]
    embedding_time = time.time() - embedding_start
    logger.info(f"⚡ 임베딩 생성 완료 ({embedding_time:.2f}초)")
    
    # 검색할 문서 타입 목록 생성 (성능 최적화)
    search_types = []
    if "tickets" in content_types:
        search_types.append("ticket")
    if "solutions" in content_types:
        search_types.append("kb")
    
    # 통합 검색 실행 (단일 검색으로 중복 호출 방지)
    if len(search_types) == 1:
        # 단일 타입 검색 (기존 방식)
        single_type = search_types[0]
        unified_results = retrieve_top_k_docs(
            query_embedding, 
            req.top_k, 
            company_id, 
            doc_type=single_type
        )
        logger.info(f"⚡ 통합 검색 완료 - {single_type}: {len(unified_results.get('documents', []))} 건")
        
        # 결과를 기존 형식으로 변환
        if single_type == "ticket":
            ticket_results = unified_results
            kb_results = {"documents": [], "metadatas": [], "ids": [], "distances": []}
        else:
            kb_results = unified_results
            ticket_results = {"documents": [], "metadatas": [], "ids": [], "distances": []}
    else:
        # 다중 타입 검색 (각 타입당 절반씩)
        top_k_per_type = max(1, req.top_k // len(search_types))
        
        # 병렬 검색으로 성능 최적화
        async def search_by_type(doc_type):
            return retrieve_top_k_docs(
                query_embedding, 
                top_k_per_type, 
                company_id, 
                doc_type=doc_type
            )
        
        search_tasks = []
        for doc_type in search_types:
            search_tasks.append(search_by_type(doc_type))
        
        # 병렬 실행
        search_results = await asyncio.gather(*search_tasks)
        
        # 결과 분배
        ticket_results = {"documents": [], "metadatas": [], "ids": [], "distances": []}
        kb_results = {"documents": [], "metadatas": [], "ids": [], "distances": []}
        
        for i, doc_type in enumerate(search_types):
            if doc_type == "ticket":
                ticket_results = search_results[i]
            elif doc_type == "kb":
                kb_results = search_results[i]
        
        logger.info(f"⚡ 병렬 검색 완료 - 티켓: {len(ticket_results.get('documents', []))} 건, KB: {len(kb_results.get('documents', []))} 건")

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

class SimilarTicketsResponse(BaseModel):
    """유사 티켓 검색 응답 모델"""
    ticket_id: str = Field(description="원본 티켓의 ID")
    similar_tickets: List[SimilarTicketItem] = Field(description="검색된 유사 티켓 목록")


class RelatedDocsResponse(BaseModel):
    """관련 문서 검색 응답 모델"""
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

# 캐시 설정: 티켓 요약 캐시 (환경변수에서 설정 가져옴)
ticket_summary_cache = TTLCache(
    maxsize=int(os.getenv("TICKET_SUMMARY_CACHE_MAXSIZE", "100")), 
    ttl=int(os.getenv("TICKET_SUMMARY_CACHE_TTL", "3600"))
)

@app.get("/init/{ticket_id}", response_model=InitResponse)
async def get_initial_context(
    ticket_id: str, 
    company_id: str = Depends(get_company_id),
    include_summary: bool = True,
    include_kb_docs: bool = True,
    include_similar_tickets: bool = True,
    x_freshdesk_domain: Optional[str] = Header(None, alias="X-Freshdesk-Domain"),
    x_freshdesk_api_key: Optional[str] = Header(None, alias="X-Freshdesk-API-Key")
):
    """
    티켓 초기화 컨텍스트를 제공합니다.
    티켓 요약, 유사 티켓, 관련 지식베이스 문서를 포함합니다.
    
    Args:
        ticket_id: 초기화할 티켓 ID
        company_id: 회사 ID (자동 추출)
        include_summary: 티켓 요약 포함 여부
        include_kb_docs: 지식베이스 문서 포함 여부
        include_similar_tickets: 유사 티켓 포함 여부
        x_freshdesk_domain: Freshdesk 도메인 (헤더에서 전달)
        x_freshdesk_api_key: Freshdesk API 키 (헤더에서 전달)
    """
    logger.info(f"티켓 {ticket_id} 초기화 요청 수신 - Domain: {x_freshdesk_domain}")
    
    # 디버깅 모드 확인
    debug_mode = os.getenv("DEBUG_INIT_ENDPOINT", "false").lower() == "true"
    debug_ticket_id = os.getenv("DEBUG_TICKET_ID")
    
    if debug_mode:
        logger.info(f"🔍 DEBUG MODE 활성화됨")
        logger.info(f"🎯 설정된 디버그 티켓 ID: {debug_ticket_id}")
        logger.info(f"📧 요청된 티켓 ID: {ticket_id}")
        logger.info(f"🏢 Company ID: {company_id}")
        logger.info(f"🌐 Freshdesk Domain: {x_freshdesk_domain}")
    
    # Freshdesk 설정값이 헤더로 전달된 경우 임시로 환경변수에 설정
    original_domain = os.getenv("FRESHDESK_DOMAIN")
    original_api_key = os.getenv("FRESHDESK_API_KEY")
    
    try:
        if x_freshdesk_domain:
            os.environ["FRESHDESK_DOMAIN"] = x_freshdesk_domain
            logger.info(f"Freshdesk 도메인을 '{x_freshdesk_domain}'으로 임시 설정")
            
        if x_freshdesk_api_key:
            os.environ["FRESHDESK_API_KEY"] = x_freshdesk_api_key
            logger.info("Freshdesk API 키를 헤더값으로 임시 설정")
        
        # Freshdesk API 호출을 위한 파라미터 준비
        company_id_from_header = x_freshdesk_domain  # iparams에서 받은 company_id
        api_key = x_freshdesk_api_key or os.getenv("FRESHDESK_API_KEY")
        
        # 개발 환경에서 헤더가 없는 경우 환경변수 폴백
        if not company_id_from_header:
            company_id_from_header = os.getenv("FRESHDESK_DOMAIN")
            logger.info(f"개발 환경: 환경변수에서 도메인 사용 - {company_id_from_header}")
        
        if not api_key:
            api_key = os.getenv("FRESHDESK_API_KEY")
            logger.info("개발 환경: 환경변수에서 API 키 사용")
        
        # Freshdesk API 호출을 위한 전체 도메인 구성
        if company_id_from_header:
            # 헤더값이 이미 전체 도메인인지 확인
            if company_id_from_header.endswith('.freshdesk.com'):
                full_domain = company_id_from_header
            else:
                # company_id만 있는 경우 전체 Freshdesk 도메인 구성
                full_domain = f"{company_id_from_header}.freshdesk.com"
        else:
            # 환경변수에서 전체 도메인 사용 (개발용)
            full_domain = os.getenv("FRESHDESK_DOMAIN")
        
        if not company_id_from_header or not api_key:
            raise HTTPException(
                status_code=400,
                detail="Freshdesk company_id와 API 키가 필요합니다. 헤더 또는 환경변수로 제공해주세요."
            )
        
        # 보안: company_id 추출 (도메인에서 서브도메인 부분만)
        if full_domain and full_domain.endswith('.freshdesk.com'):
            search_company_id = full_domain.replace('.freshdesk.com', '')
        else:
            search_company_id = company_id_from_header
        logger.info(f"company_id를 Freshdesk 도메인에서 추출: {search_company_id}")
        logger.info(f"사용할 API 도메인: '{full_domain}'")
    
        # Freshdesk API에서 티켓 정보 조회 (동적 설정 사용)
        ticket_data = None
        is_from_api = False
        
        try:
            ticket_data = await fetcher.fetch_ticket_details(int(ticket_id), domain=full_domain, api_key=api_key)
            if ticket_data:
                is_from_api = True
                logger.info(f"티켓 {ticket_id} 정보를 Freshdesk API에서 성공적으로 가져옴")
        except Exception as e:
            logger.warning(f"Freshdesk API에서 티켓 {ticket_id} 조회 실패: {e}")
        
        if not ticket_data:
            # API 조회 실패 시 벡터 검색 폴백
            logger.info(f"벡터 DB에서 티켓 {ticket_id} 검색 시도")
            ticket_data = vector_db.get_by_id(original_id_value=ticket_id, company_id=search_company_id, doc_type="ticket")
            
            if not ticket_data:
                raise HTTPException(status_code=404, detail=f"티켓 ID {ticket_id}를 찾을 수 없습니다. Freshdesk API와 벡터 DB 모두에서 조회 실패.")
            
            logger.info(f"벡터 DB에서 티켓 {ticket_id} 정보 조회 성공")
            
        # 메타데이터 추출 - API와 벡터 DB 데이터 형식을 모두 지원
        if is_from_api:
            # Freshdesk API 응답 구조 처리
            ticket_metadata = ticket_data
            ticket_title = ticket_metadata.get("subject", f"티켓 ID {ticket_id}")
            ticket_body = ticket_metadata.get("description_text", ticket_metadata.get("description", "티켓 본문 정보 없음"))
        else:
            # 벡터 DB 데이터 구조 처리
            ticket_metadata = ticket_data.get("metadata", {}) if isinstance(ticket_data, dict) else ticket_data
            ticket_title = ticket_metadata.get("subject", f"티켓 ID {ticket_id}")
            ticket_body = ticket_metadata.get("text", ticket_metadata.get("description_text", "티켓 본문 정보 없음"))
        
        # 대화 내용 처리 - API와 벡터 DB 데이터 구조를 모두 지원
        ticket_conversations = []
        
        if is_from_api:
            # Freshdesk API 응답에서 대화 내역 추출
            raw_conversations = ticket_data.get("conversations", [])
            if isinstance(raw_conversations, list):
                ticket_conversations = raw_conversations
            elif isinstance(raw_conversations, str):
                try:
                    parsed_convs = json.loads(raw_conversations)
                    if isinstance(parsed_convs, list):
                        ticket_conversations = parsed_convs
                    else:
                        ticket_conversations = [{"body_text": str(parsed_convs), "created_at": datetime.now().timestamp()}]
                except json.JSONDecodeError:
                    ticket_conversations = [{"body_text": raw_conversations, "created_at": datetime.now().timestamp()}]
        else:
            # 벡터 DB 데이터에서 대화 내역 추출
            raw_conversations = ticket_data.get("conversations", []) if isinstance(ticket_data, dict) else []
            
            if isinstance(raw_conversations, list):
                # 원본 형식 보존 (딕셔너리 형태 유지)
                ticket_conversations = raw_conversations
            elif isinstance(raw_conversations, str):
                try:
                    parsed_convs = json.loads(raw_conversations)
                    if isinstance(parsed_convs, list):
                        ticket_conversations = parsed_convs
                    else:
                        ticket_conversations = [{"body_text": str(parsed_convs), "created_at": datetime.now().timestamp()}]
                except json.JSONDecodeError:
                    ticket_conversations = [{"body_text": raw_conversations, "created_at": datetime.now().timestamp()}]
        
        # 대화 내역이 없는 경우 대화 요약 사용 (API와 벡터 DB 공통)
        if not ticket_conversations:
            conversation_summary = None
            if is_from_api:
                # API 데이터에서 기본 설명을 대화로 사용
                if ticket_body and ticket_body != "티켓 본문 정보 없음":
                    conversation_summary = ticket_body
            else:
                # 벡터 DB 데이터에서 대화 요약 사용
                conversation_summary = ticket_metadata.get("conversation_summary")
            
            if conversation_summary:
                ticket_conversations = [{"body_text": str(conversation_summary), 
                                        "created_at": datetime.now().timestamp()}]
        
        # 컨텍스트 ID 생성 (향후 요청을 위한 고유 식별자)
        context_id = f"ctx_{ticket_id}_{int(time.time())}"
        
        # 티켓 정보 구성을 위한 모든 텍스트
        # 대화 내용이 딕셔너리 목록인 경우 각 대화에서 본문을 추출하여 문자열로 변환
        conversation_texts = []
        for conv in ticket_conversations:
            if isinstance(conv, dict):
                # API와 벡터 DB 모든 형식을 지원하는 필드 순서
                for field in ["body_text", "body", "text", "content", "message", "description"]:
                    if field in conv and conv[field]:
                        # HTML 태그 제거 및 텍스트 정리
                        text_content = str(conv[field])
                        # 기본적인 HTML 태그 제거 (정규식 사용 피하고 간단한 replace 사용)
                        cleaned_text = text_content.replace('<br>', '\n').replace('<br/>', '\n').replace('<br />', '\n')
                        conversation_texts.append(cleaned_text)
                        break
                else:  # for-else: for 루프가 break 없이 완료되면 실행
                    # 적절한 필드를 찾지 못한 경우 전체 딕셔너리를 문자열로 변환 (제한된 길이)
                    conversation_texts.append(str(conv)[:500])
            else:
                conversation_texts.append(str(conv))
        
        # 성능 최적화: 단계별 데이터 로딩 전략
        # 1. 필수 데이터만 즉시 로드 (티켓 기본 정보)
        # 2. 나머지는 백그라운드에서 병렬 처리
        # 3. 캐시된 데이터 우선 사용
        
        logger.info(f"티켓 {ticket_id}: 대화 {len(ticket_conversations)}개 처리 완료, 텍스트 {len(conversation_texts)}개 추출")
        
        # 캐시 확인 및 성능 최적화
        cached_summary = None
        
        # 🛡️ 안전한 캐시 키 생성 (company_id + ticket_id + updated_at 포함)
        ticket_updated_at = ticket_metadata.get('updated_at', '')
        # 안전한 캐시 키: company_id_ticket_id_updated_timestamp
        safe_cache_key = f"{search_company_id}_{ticket_id}_{ticket_updated_at}"
        summary_cache_key = f"summary_{safe_cache_key}"
        
        # 🔍 캐시된 데이터 검증 및 무효화 로직
        cached_summary = None
        cache_is_valid = False
        
        if include_summary and summary_cache_key in ticket_summary_cache:
            cached_data = ticket_summary_cache[summary_cache_key]
            
            # 🛡️ 캐시 유효성 엄격 검증
            if isinstance(cached_data, dict):
                # 구조화된 캐시 데이터 검증
                cache_company_id = cached_data.get('company_id')
                cache_ticket_id = cached_data.get('ticket_id') 
                cache_updated_at = cached_data.get('updated_at')
                cache_content = cached_data.get('content')
                cache_timestamp = cached_data.get('cache_timestamp', 0)
                
                # 현재 시간과 캐시 시간 비교 (최대 30분 유효)
                current_time = time.time()
                cache_age_minutes = (current_time - cache_timestamp) / 60
                
                # 🔍 다중 검증 조건
                if (cache_company_id == search_company_id and 
                    cache_ticket_id == ticket_id and
                    cache_updated_at == ticket_updated_at and
                    cache_content and isinstance(cache_content, str) and
                    len(cache_content.strip()) > 100 and  # 최소 100자 이상
                    cache_age_minutes < 30):  # 30분 이내
                    
                    cached_summary = cache_content
                    cache_is_valid = True
                    logger.info(f"✅ 캐시 유효성 검증 통과 - 사용 (캐시 나이: {cache_age_minutes:.1f}분)")
                else:
                    logger.warning("⚠️ 캐시 유효성 검증 실패:")
                    logger.warning(f"  - Company ID 일치: {cache_company_id == search_company_id}")
                    logger.warning(f"  - Ticket ID 일치: {cache_ticket_id == ticket_id}")
                    logger.warning(f"  - Updated At 일치: {cache_updated_at == ticket_updated_at}")
                    logger.warning(f"  - 내용 유효성: {cache_content and len(cache_content.strip()) > 100}")
                    logger.warning(f"  - 캐시 나이: {cache_age_minutes:.1f}분 (< 30분)")
            else:
                # 레거시 문자열 캐시는 더 이상 신뢰하지 않음
                logger.warning("⚠️ 레거시 캐시 형식 발견 - 무효화")
            
            # 🗑️ 유효하지 않은 캐시 즉시 제거
            if not cache_is_valid:
                del ticket_summary_cache[summary_cache_key]
                logger.info("🗑️ 유효하지 않은 캐시 제거됨")
        
        # 🔍 요약 생성 조건 개선
        include_summary_chain = include_summary and not cache_is_valid

        # 컨텍스트 구축 시작 시간
        context_start_time = time.time()
        
        # 성능 최적화: 필수 작업과 선택적 작업 분리
        # 1. 기본 응답 구성 (즉시 반환 가능한 데이터)
        # 2. 추가 데이터는 백그라운드에서 처리
        
        # Phase 1: Langchain RunnableParallel로 병렬 작업 관리
        # 개별 태스크 정의 대신 Langchain 체인이 모든 작업을 처리
        # 기존 asyncio.gather 방식과 동일한 성능을 유지하면서 더 나은 아키텍처 제공
        
        # 작업별 데이터 초기화
        similar_tickets = []
        kb_documents = []
        ticket_summary = None
        
        # 🚀 병렬 처리 최적화: 티켓 요약과 벡터 검색을 동시에 실행
        try:
            logger.info(f"🚀 병렬 처리 시작 (ticket_id: {ticket_id})")
            parallel_start_time = time.time()
            
            # 병렬 태스크 정의
            async def generate_ticket_summary():
                """티켓 요약 생성 태스크"""
                if not include_summary_chain:
                    if cache_is_valid and cached_summary:
                        return cached_summary
                    else:
                        # 기본 요약 생성
                        return f"""## 📋 티켓 요약
**제목**: {ticket_title}  
**티켓 ID**: {ticket_id}  
**상태**: {ticket_metadata.get('status', '알 수 없음')}  
**우선순위**: {ticket_metadata.get('priority', '알 수 없음')}  

## 🔍 초기 문의 내용
{ticket_body[:500] + '...' if len(ticket_body) > 500 else ticket_body}

## 📈 다음 단계  
- 상세한 AI 분석을 위해 페이지를 새로고침하시거나
- 수동으로 티켓 내용을 검토해 주세요"""
                
                # 대화 내용 기반 상세 요약 생성
                # 대화 내용 기반 상세 요약 생성
                try:
                    logger.info(f"티켓 {ticket_id} 실시간 대화 분석 요약 시작")
                    
                    # 전체 대화 내용 분석 - 더 정교한 분석 로직
                    conversation_analysis = ""
                    key_customer_requests = []
                    agent_responses = []
                    recent_developments = []
                    unresolved_issues = []
                    
                    if ticket_conversations and len(ticket_conversations) > 0:
                        logger.info(f"전체 {len(ticket_conversations)}개 대화 분석 시작")
                        
                        # 대화를 시간순으로 정렬 (최신이 마지막)
                        sorted_conversations = sorted(ticket_conversations, 
                                                   key=lambda x: x.get('created_at', ''), 
                                                   reverse=False)
                        
                        # 최근 대화부터 분석 (최근 10개 중점 분석)
                        recent_convs = sorted_conversations[-10:] if len(sorted_conversations) > 10 else sorted_conversations
                        
                        for i, conv in enumerate(sorted_conversations):
                            if isinstance(conv, dict):
                                user_name = conv.get('user_name', '사용자')
                                created_at = conv.get('created_at', '')
                                body_text = conv.get('body_text', conv.get('body', ''))
                                
                                if body_text and len(body_text.strip()) > 10:  # 의미있는 내용만
                                    # 고객 vs 상담사 구분 (타입 안전성 확보)
                                    user_name_str = str(user_name).lower() if user_name else ''
                                    source_str = str(conv.get('source', '')).lower()
                                    from_email_str = str(conv.get('from_email', '')).lower()
                                    
                                    # 고객 식별 - 이메일 도메인이나 사용자명으로 판단
                                    is_customer = (
                                        'customer' in user_name_str or 
                                        'requester' in source_str or
                                        '@' in from_email_str and 'freshdesk' not in from_email_str and 'wedosoft' not in from_email_str
                                    )
                                    
                                    # 최근 대화인지 확인
                                    is_recent = conv in recent_convs
                                    
                                    if is_customer:
                                        # 고객 요청사항 분류
                                        if any(word in body_text.lower() for word in ['급하', '빨리', '문제', '오류', '안됨', '불편', '해결']):
                                            if is_recent:
                                                recent_developments.append(f"최근 고객 요청: {body_text[:120]}...")
                                        
                                        # 주요 요청사항 추출
                                        key_customer_requests.append({
                                            'content': body_text[:200],
                                            'is_recent': is_recent,
                                            'timestamp': created_at
                                        })
                                        
                                        # 미해결 문제 식별
                                        if any(word in body_text.lower() for word in ['아직', '여전히', '계속', '다시', '또', '재요청']):
                                            unresolved_issues.append(f"미해결 이슈: {body_text[:100]}...")
                                            
                                    else:
                                        # 상담사 응답/조치사항
                                        if is_recent:
                                            agent_responses.append({
                                                'content': body_text[:200],
                                                'timestamp': created_at
                                            })
                        
                        # 대화 분석 요약 구성
                        conversation_analysis = "=== 대화 흐름 분석 ===\n\n"
                        
                        # 최근 진행상황 (가장 중요)
                        if recent_developments:
                            conversation_analysis += f"📈 최근 진행상황 ({len(recent_developments)}건):\n"
                            for dev in recent_developments[-3:]:  # 최근 3개만
                                conversation_analysis += f"  • {dev}\n"
                            conversation_analysis += "\n"
                        
                        # 미해결 문제 (우선순위 높음)
                        if unresolved_issues:
                            conversation_analysis += f"⚠️ 미해결 문제 ({len(unresolved_issues)}건):\n"
                            for issue in unresolved_issues[-2:]:  # 최근 2개만
                                conversation_analysis += f"  • {issue}\n"
                            conversation_analysis += "\n"
                        
                        # 주요 고객 요청 요약
                        if key_customer_requests:
                            recent_requests = [req for req in key_customer_requests if req['is_recent']]
                            if recent_requests:
                                conversation_analysis += f"🔥 최근 주요 요청 ({len(recent_requests)}건):\n"
                                for req in recent_requests[-3:]:
                                    conversation_analysis += f"  • {req['content']}\n"
                                conversation_analysis += "\n"
                        
                        # 상담사 최근 조치
                        if agent_responses:
                            conversation_analysis += f"💬 상담사 최근 조치 ({len(agent_responses)}건):\n"
                            for resp in agent_responses[-2:]:  # 최근 2개만
                                conversation_analysis += f"  • {resp['content']}\n"
                            conversation_analysis += "\n"
                        
                        # 전체 요약 통계
                        conversation_analysis += "📊 대화 통계:\n"
                        conversation_analysis += f"  • 전체 대화: {len(ticket_conversations)}개\n"
                        conversation_analysis += f"  • 고객 요청: {len(key_customer_requests)}개\n"
                        conversation_analysis += f"  • 상담사 응답: {len(agent_responses)}개\n"
                        conversation_analysis += f"  • 미해결 이슈: {len(unresolved_issues)}개\n"
                    
                    # 🚀 최적화된 간소 프롬프트 - 속도 우선
                    optimized_summary_prompt = f"""티켓 요약 요청:

ID: {ticket_id}
제목: {ticket_title}
우선순위: {ticket_metadata.get('priority', '보통')}
대화수: {len(ticket_conversations)}개

초기 문의:
{ticket_body[:500]}

{conversation_analysis}

다음 형식으로 간결하게 요약하세요:

## 📋 상황 요약
## 🔍 핵심 문제  
## ⚡ 다음 조치
## 📊 분석"""
                    
                    # 🚀 초고속 요약 생성 - 경량 모델 사용
                    summary_response = await llm_router.generate(
                        prompt=optimized_summary_prompt,
                        operation="ticket_summary",  # 티켓 요약 작업으로 명시적 지정
                        system_prompt="고객 지원 티켓을 빠르게 요약하는 전문가입니다. 간결하고 핵심적인 정보만 제공합니다.",
                        max_tokens=800,  # 토큰 수 줄여서 속도 향상
                        temperature=0.1
                    )
                    
                    # 원본 LLM 마크다운 응답을 그대로 사용
                    llm_generated_summary = summary_response.text.strip()
                    
                    # 키 포인트 추출 개선 - 더 풍부한 정보 제공
                    key_points = []
                    import re
                    
                    # 1. 핵심 문제 섹션에서 키포인트 추출
                    problem_section = re.search(r'## 🔍 핵심 문제\n(.*?)(?=\n## |$)', llm_generated_summary, re.DOTALL)
                    if problem_section:
                        problem_content = problem_section.group(1).strip()
                        # 리스트 항목뿐만 아니라 문장도 추출
                        problem_items = re.findall(r'^\d+\.\s*(.+)$', problem_content, re.MULTILINE)
                        if problem_items:
                            key_points.extend([f"문제: {item}" for item in problem_items[:2]])
                        else:
                            # 리스트가 없으면 첫 문장 추출
                            first_sentence = problem_content.split('.')[0].strip()
                            if first_sentence and len(first_sentence) > 10:
                                key_points.append(f"핵심 문제: {first_sentence}")
                    
                    # 2. 다음 조치 섹션에서 키포인트 추출
                    action_section = re.search(r'## ⚡ 다음 조치\n(.*?)(?=\n## |$)', llm_generated_summary, re.DOTALL)
                    if action_section:
                        action_content = action_section.group(1).strip()
                        action_items = re.findall(r'^\d+\.\s*(.+)$', action_content, re.MULTILINE)
                        if action_items:
                            key_points.extend([f"조치: {item}" for item in action_items[:1]])
                        elif "없음" not in action_content.lower():
                            first_sentence = action_content.split('.')[0].strip()
                            if first_sentence and len(first_sentence) > 5:
                                key_points.append(f"조치사항: {first_sentence}")
                    
                    # 3. 분석 섹션에서 키포인트 추출
                    analysis_section = re.search(r'## 📊 분석\n(.*?)(?=\n## |$)', llm_generated_summary, re.DOTALL)
                    if analysis_section:
                        analysis_content = analysis_section.group(1).strip()
                        first_sentence = analysis_content.split('.')[0].strip()
                        if first_sentence and len(first_sentence) > 10:
                            key_points.append(f"분석: {first_sentence}")
                    
                    # 4. 상황 요약 섹션에서 키포인트 추출
                    summary_section = re.search(r'## 📋 상황 요약\n(.*?)(?=\n## |$)', llm_generated_summary, re.DOTALL)
                    if summary_section:
                        summary_content = summary_section.group(1).strip()
                        # 첫 번째 문장이 가장 중요한 정보
                        first_sentence = summary_content.split('.')[0].strip()
                        if first_sentence and len(first_sentence) > 15:
                            key_points.insert(0, first_sentence)  # 첫 번째로 배치
                    
                    # 키 포인트가 없으면 제목에서 추출 시도
                    if not key_points:
                        if ticket_title and len(ticket_title) > 10:
                            # 제목에서 키워드 추출
                            title_clean = re.sub(r'\[.*?\]', '', ticket_title).strip()
                            if title_clean:
                                key_points.append(f"주제: {title_clean[:50]}")
                        
                        # 여전히 없으면 대화 수 정보 사용 (최후 수단)
                        if not key_points:
                            key_points = [f'총 {len(ticket_conversations)}개 대화 내용 분석']
                    
                    # 🛡️ 안전한 캐시 저장
                    safe_cache_data = {
                        'company_id': search_company_id,
                        'ticket_id': ticket_id,
                        'updated_at': ticket_updated_at,
                        'content': llm_generated_summary,
                        'cache_timestamp': time.time(),
                        'content_length': len(llm_generated_summary),
                        'generation_method': 'llm_parallel_analysis'
                    }
                    ticket_summary_cache[summary_cache_key] = safe_cache_data
                    logger.info("🛡️ 병렬 처리 요약 캐시 저장 완료")
                    
                    return llm_generated_summary
                    
                except Exception as e:
                    logger.error(f"티켓 {ticket_id} 요약 생성 실패: {str(e)}")
                    return f"⚠️ 요약 생성 실패: {str(e)}"
            
            async def perform_vector_search():
                """고성능 별도 검색으로 유사 티켓과 KB 문서를 검색합니다."""
                if not (include_similar_tickets or include_kb_docs):
                    return [], []
                
                try:
                    # 검색 쿼리 생성 및 임베딩
                    search_text = f"{ticket_title} {ticket_body}"
                    
                    # 임베딩 생성
                    from core.embedder import generate_embedding
                    query_embedding = await generate_embedding(search_text[:800])  # 토큰 제한
                    
                    # 🚀 성능 최적화: 별도 검색으로 정확한 필터링과 병렬 처리
                    logger.info(f"🚀 별도 검색 시작: company_id={search_company_id}")
                    
                    # 병렬 검색 태스크 정의
                    async def search_tickets():
                        """유사 티켓 전용 검색"""
                        if not include_similar_tickets:
                            return []
                        
                        ticket_results = await asyncio.to_thread(
                            vector_db.search,
                            query_embedding=query_embedding,
                            top_k=5,  # 티켓은 최대 5개 검색 (필터링 후 3개 예상)
                            company_id=search_company_id,
                            doc_type="ticket"  # 티켓만 정확히 검색
                        )
                        
                        similar_tickets_temp = []
                        if ticket_results and ticket_results.get("results"):
                            for result in ticket_results["results"]:
                                similarity_score = result.get("score", 0)
                                
                                # 최소 유사도 및 현재 티켓 제외
                                if (similarity_score >= 0.3 and 
                                    str(result.get("id")) != str(ticket_id) and 
                                    len(similar_tickets_temp) < 3):
                                    
                                    title = result.get("title") or result.get("subject") or f"티켓 {result.get('id')}"
                                    ticket_text = result.get("text", result.get("description", ""))
                                    
                                    similar_tickets_temp.append({
                                        "id": str(result.get("id")),
                                        "title": title,
                                        "ticket_text": ticket_text,
                                        "status": result.get("status", ""),
                                        "priority": result.get("priority", ""),
                                        "similarity_score": similarity_score,
                                        "ticket_url": f"https://{search_company_id}.freshdesk.com/a/tickets/{result.get('id')}"
                                    })
                        
                        logger.info(f"✅ 티켓 검색 완료: {len(similar_tickets_temp)}개")
                        return similar_tickets_temp
                    
                    async def search_kb_docs():
                        """KB 문서 전용 검색"""
                        if not include_kb_docs:
                            return []
                        
                        kb_results = await asyncio.to_thread(
                            vector_db.search,
                            query_embedding=query_embedding,
                            top_k=8,  # KB는 최대 8개 검색 (status 필터링 후 5개 예상)
                            company_id=search_company_id,
                            doc_type="kb"  # KB 문서만 정확히 검색
                        )
                        
                        kb_documents_data = []
                        if kb_results and kb_results.get("results"):
                            for result in kb_results["results"]:
                                hit_status = result.get("status")
                                similarity_score = result.get("score", 0)
                                
                                # KB 문서 필터링 (status=2인 발행된 문서만)
                                if (similarity_score >= 0.3 and 
                                    hit_status in [2, "2"] and 
                                    len(kb_documents_data) < 5):
                                    
                                    logger.info(f"✅ KB 문서 발견: ID={result.get('id')}, title={result.get('title', '')[:50]}")
                                    
                                    title = result.get("title") or result.get("subject") or f"KB 문서 {result.get('id')}"
                                    kb_text = result.get("text", result.get("description", ""))
                                    doc_summary = kb_text[:300] + "..." if len(kb_text) > 300 else kb_text
                                    
                                    kb_documents_data.append({
                                        "id": str(result.get("id")),
                                        "title": title,
                                        "doc_summary": doc_summary,
                                        "url": result.get("url", f"https://{search_company_id}.freshdesk.com/solution/articles/{result.get('id')}"),
                                        "similarity_score": round(similarity_score, 3),
                                        "source_type": "kb"
                                    })
                        
                        logger.info(f"✅ KB 검색 완료: {len(kb_documents_data)}개")
                        return kb_documents_data
                    
                    # 🚀 병렬 검색 실행 (성능 대폭 향상)
                    search_start = time.time()
                    similar_tickets_temp, kb_documents_data = await asyncio.gather(
                        search_tickets(),
                        search_kb_docs()
                    )
                    search_duration = time.time() - search_start
                    
                    logger.info(f"⚡ 별도 병렬 검색 완료: {search_duration:.2f}초 - 유사 티켓: {len(similar_tickets_temp)}개, KB 문서: {len(kb_documents_data)}개")
                    return similar_tickets_temp, kb_documents_data
                    
                except Exception as e:
                    logger.error(f"벡터 검색 실패: {str(e)}")
                    return [], []
            
            # 🚀 병렬 실행: 티켓 요약과 벡터 검색을 동시에 수행
            logger.info("🚀 병렬 태스크 실행 시작")
            
            # 타임아웃 설정으로 병목 방지 (최적화된 설정)
            PARALLEL_TIMEOUT = 30  # 25초 → 30초로 연장하여 안정성 확보
            
            summary_task = generate_ticket_summary()
            vector_task = perform_vector_search()
            
            try:
                # asyncio.gather로 병렬 실행 (타임아웃 적용)
                ticket_summary, (similar_tickets_temp, kb_documents) = await asyncio.wait_for(
                    asyncio.gather(summary_task, vector_task),
                    timeout=PARALLEL_TIMEOUT
                )
                logger.info(f"✅ 병렬 처리 완료 (타임아웃 {PARALLEL_TIMEOUT}초 내)")
            except asyncio.TimeoutError:
                logger.warning(f"⚠️ 병렬 처리 타임아웃 ({PARALLEL_TIMEOUT}초 초과) - 부분 결과 사용")
                # 타임아웃 시 기본값 사용
                ticket_summary = f"⚠️ 요약 생성 시간 초과 (티켓 ID: {ticket_id})"
                similar_tickets_temp, kb_documents = [], []
            
            # 🚀 유사 티켓 배치 분석 최적화 (성능 대폭 개선)
            similar_tickets = []
            if similar_tickets_temp and include_similar_tickets:
                try:
                    # 배치 크기 확대로 처리량 증가 (3개 → 8개)
                    MAX_BATCH_SIZE = 8  # 최대 8개로 증가하여 더 많은 유사 티켓 제공
                    similar_tickets_temp = similar_tickets_temp[:MAX_BATCH_SIZE]
                    
                    logger.info(f"🔥 배치 분석 시작: {len(similar_tickets_temp)}개 유사 티켓 (성능 최적화 적용)")
                    
                    # 배치 분석을 위한 데이터 구성 (텍스트 길이 최적화)
                    tickets_for_analysis = []
                    for ticket in similar_tickets_temp:
                        tickets_for_analysis.append({
                            "id": ticket["id"],
                            "subject": ticket["title"],
                            "description_text": ticket["ticket_text"][:300],  # 500→300자로 단축하여 처리 속도 향상
                            "status": ticket["status"],
                            "priority": ticket["priority"]
                        })
                    
                    # 배치 LLM 분석 실행 (타임아웃 연장으로 안정성 확보)
                    BATCH_TIMEOUT = 20  # 15초 → 20초로 연장하여 배치 처리 안정성 향상
                    batch_start_time = time.time()
                    
                    batch_results = await asyncio.wait_for(
                        llm_router.analyze_multiple_tickets_batch(tickets_for_analysis),
                        timeout=BATCH_TIMEOUT
                    )
                    
                    batch_duration = time.time() - batch_start_time
                    logger.info(f"✅ 배치 분석 완료: {len(batch_results)}개 결과, 소요시간: {batch_duration:.1f}초")
                    
                    # 결과를 최종 데이터에 반영
                    for i, ticket in enumerate(similar_tickets_temp):
                        if i < len(batch_results):
                            analysis = batch_results[i]
                            issue = analysis.get("issue", "고객 문의사항 분석 중")
                            solution = analysis.get("solution", "해결 방안 검토 중")
                        else:
                            issue = "문제 상황 분석 중"
                            solution = "해결 방안 검토 중"
                        
                        similar_tickets.append({
                            "id": ticket["id"],
                            "title": ticket["title"],
                            "issue": issue,
                            "solution": solution,
                            "similarity_score": round(ticket["similarity_score"], 3),
                            "ticket_url": ticket["ticket_url"]
                        })
                        
                except asyncio.TimeoutError:
                    logger.warning(f"⚠️ 배치 분석 타임아웃 ({BATCH_TIMEOUT}초 초과) - 기본 데이터 사용")
                    # 타임아웃 시 기본 데이터 사용 (fallback 메커니즘)
                    for ticket in similar_tickets_temp:
                        similar_tickets.append({
                            "id": ticket["id"],
                            "title": ticket["title"],
                            "issue": "고객 문의사항 분석 중",
                            "solution": "해결 방안 검토 중",
                            "similarity_score": round(ticket["similarity_score"], 3),
                            "ticket_url": ticket["ticket_url"]
                        })
                except Exception as e:
                    logger.error(f"배치 분석 실패: {e}, 기본 데이터 사용")
                    # 배치 실패 시 기본 데이터 사용
                    for ticket in similar_tickets_temp:
                        similar_tickets.append({
                            "id": ticket["id"],
                            "title": ticket["title"],
                            "issue": "고객 문의사항 분석 중",
                            "solution": "해결 방안 검토 중",
                            "similarity_score": round(ticket["similarity_score"], 3),
                            "ticket_url": ticket["ticket_url"]
                        })
            
            parallel_execution_time = time.time() - parallel_start_time
            logger.info(f"🚀 병렬 처리 완료 (ticket_id: {ticket_id}, 총 실행시간: {parallel_execution_time:.2f}초)")
                            
            # 성능 메트릭 수집
            total_context_time = time.time() - context_start_time
            
            # 요약 데이터 처리 및 타입 안정성 확보 - 원본 마크다운 유지
            processed_summary = None
            

            
            if ticket_summary:
                if isinstance(ticket_summary, str):
                    # LLM이 생성한 마크다운 요약을 올바르게 사용
                    llm_markdown_summary = ticket_summary
                    
                    # 키 포인트를 마크다운 요약에서 더 지능적으로 추출
                    summary_key_points = []
                    import re
                    
                    # 1. 상황 요약 섹션에서 핵심 내용 추출
                    summary_section = re.search(r'## 📋 상황 요약\n(.*?)(?=\n## |$)', llm_markdown_summary, re.DOTALL)
                    if summary_section:
                        summary_content = summary_section.group(1).strip()
                        # 첫 문장이 가장 중요
                        first_sentence = summary_content.split('.')[0].strip()
                        if first_sentence and len(first_sentence) > 15:
                            summary_key_points.append(first_sentence[:80] + "..." if len(first_sentence) > 80 else first_sentence)
                    
                    # 2. 핵심 문제에서 키포인트 추출
                    problem_section = re.search(r'## 🔍 핵심 문제\n(.*?)(?=\n## |$)', llm_markdown_summary, re.DOTALL)
                    if problem_section:
                        problem_content = problem_section.group(1).strip()
                        if problem_content and len(problem_content) > 10:
                            clean_problem = problem_content.split('.')[0].strip()
                            if clean_problem and len(clean_problem) > 10:
                                summary_key_points.append(f"문제: {clean_problem[:60]}")
                    
                    # 3. 조치사항에서 키포인트 추출
                    action_section = re.search(r'## ⚡ 다음 조치\n(.*?)(?=\n## |$)', llm_markdown_summary, re.DOTALL)
                    if action_section:
                        action_content = action_section.group(1).strip()
                        if action_content and "없음" not in action_content.lower():
                            clean_action = action_content.split('.')[0].strip()
                            if clean_action and len(clean_action) > 5:
                                summary_key_points.append(f"조치: {clean_action[:60]}")
                    
                    # 키포인트가 없으면 제목에서 추출
                    if not summary_key_points:
                        if hasattr(ticket_data, 'get') and ticket_data.get('subject'):
                            title = ticket_data.get('subject', '')
                            title_clean = re.sub(r'\[.*?\]', '', title).strip()
                            if title_clean and len(title_clean) > 10:
                                summary_key_points.append(f"주제: {title_clean[:50]}")
                        
                        # 최후 수단으로 대화 수 정보
                        if not summary_key_points:
                            summary_key_points = [f'총 {len(ticket_conversations)}개 대화 내용 분석 완료']
                    
                    # 마크다운 요약에서 감정 상태 추출 시도
                    sentiment = "중립적"
                    if "부정적" in llm_markdown_summary or "불만족" in llm_markdown_summary or "긴급" in llm_markdown_summary:
                        sentiment = "부정적"
                    elif "긍정적" in llm_markdown_summary or "만족" in llm_markdown_summary:
                        sentiment = "긍정적"
                    
                    # 우선순위 추출 시도
                    priority = "보통"
                    if "높음" in llm_markdown_summary or "긴급" in llm_markdown_summary:
                        priority = "높음"
                    elif "낮음" in llm_markdown_summary:
                        priority = "낮음"
                    
                    # LLM 마크다운 요약을 ticket_summary 필드에 사용
                    processed_summary = TicketSummaryContent(
                        ticket_summary=llm_markdown_summary,  # LLM 생성 마크다운 유지
                        key_points=summary_key_points,
                        sentiment=sentiment,
                        priority_recommendation=priority,
                        urgency_level=priority
                    )

                elif isinstance(ticket_summary, TicketSummaryContent):
                    # 이미 올바른 타입인 경우 그대로 사용
                    processed_summary = ticket_summary
                elif isinstance(ticket_summary, dict):
                    # 딕셔너리 형태인 경우 TicketSummaryContent로 변환
                    try:
                        # LLM Router에서 반환하는 필드명을 TicketSummaryContent 필드에 매핑
                        processed_summary = TicketSummaryContent(
                            ticket_summary=ticket_summary.get("summary", "요약 정보 없음"),
                            key_points=ticket_summary.get("key_points", ["AI 생성 요약"]),
                            sentiment=ticket_summary.get("sentiment", "중립적"),
                            priority_recommendation=ticket_summary.get("priority_recommendation", "보통"),
                            urgency_level=ticket_summary.get("urgency_level", "보통")
                        )
                    except Exception as e:
                        logger.warning(f"딕셔너리를 TicketSummaryContent로 변환 실패: {e}")
                        # 매핑 실패 시 summary 필드를 ticket_summary로 사용
                        processed_summary = TicketSummaryContent(
                            ticket_summary=ticket_summary.get("summary", str(ticket_summary)),
                            key_points=["타입 변환 오류"],
                            sentiment="중립적"
                        )
                else:
                    # 기타 타입의 경우 문자열로 변환 후 처리
                    processed_summary = TicketSummaryContent(
                        ticket_summary=str(ticket_summary),
                        key_points=["알 수 없는 타입"],
                        sentiment="중립적"
                    )
            
            # 최종 응답 구성 - Freshdesk 티켓 메타데이터 포함
            ticket_data_for_response = {
                "company_id": search_company_id,
                "ticket_id": ticket_id,
                "subject": ticket_title,
                "description": ticket_body[:500] if ticket_body else "",  # 설명 일부만 포함
                "status": ticket_metadata.get("status"),
                "priority": ticket_metadata.get("priority"),
                "created_at": ticket_metadata.get("created_at"),
                "updated_at": ticket_metadata.get("updated_at"),
                "requester_id": ticket_metadata.get("requester_id"),
                "responder_id": ticket_metadata.get("responder_id"),
                "tags": ticket_metadata.get("tags", []),
                "type": ticket_metadata.get("type"),
                "source": ticket_metadata.get("source"),
                "has_conversations": len(ticket_conversations) > 0,
                "conversations_count": len(ticket_conversations)
            }
            
            response_data = {
                "context_id": context_id,
                "ticket_id": ticket_id,
                "ticket_data": ticket_data_for_response,  # 풍부한 티켓 메타데이터 포함
                "ticket_summary": processed_summary,  # 올바른 필드명 사용
                "similar_tickets": similar_tickets,
                "kb_documents": kb_documents,
                "metadata": {
                    "total_time": total_context_time,
                    "parallel_time": parallel_execution_time,
                    "cache_hits": {
                        "summary": cached_summary is not None,
                    },
                    "results_count": {
                        "similar_tickets": len(similar_tickets),
                        "kb_documents": len(kb_documents)
                    }
                }
            }
            
            logger.info(f"티켓 {ticket_id} 초기화 완료 - 총 처리시간: {total_context_time:.2f}초")
            
            return InitResponse(**response_data)
            
        except Exception as e:
            logger.error(f"최적화된 병렬 처리 중 예상치 못한 오류 발생: {str(e)}")
            
            # 폴백: 기본 응답 생성
            logger.warning("최적화된 처리 실패, 기본 응답 생성")
            
            # 기본 요약 생성 (타입 안정성 확보)
            fallback_summary = TicketSummaryContent(
                ticket_summary=f"티켓 제목: {ticket_title}. 처리 중 오류가 발생했습니다.",
                key_points=["시스템 오류", "수동 검토 필요"],
                sentiment="중립적",
                priority_recommendation="보통",
                urgency_level="보통"
            )
            
            return InitResponse(
                context_id=context_id,
                ticket_id=ticket_id,
                ticket_data={"company_id": search_company_id},
                ticket_summary=fallback_summary,
                similar_tickets=similar_tickets,
                kb_documents=kb_documents,
                metadata={
                    "total_time": time.time() - context_start_time,
                    "error": str(e),
                    "fallback_used": True
                }
            )
            
    except HTTPException as http_exc:
        logger.error(f"HTTP 예외 발생: {http_exc.detail}")
        raise http_exc
        
    except Exception as global_error:
        logger.error(f"전역 예외 발생: {str(global_error)}")
        raise HTTPException(
            status_code=500,
            detail=f"내부 서버 오류: {str(global_error)}"
        )
    
    finally:
        # 환경변수 복원
        if original_domain is not None:
            os.environ["FRESHDESK_DOMAIN"] = original_domain
        elif "FRESHDESK_DOMAIN" in os.environ:
            del os.environ["FRESHDESK_DOMAIN"]
            
        if original_api_key is not None:
            os.environ["FRESHDESK_API_KEY"] = original_api_key
        elif "FRESHDESK_API_KEY" in os.environ:
            del os.environ["FRESHDESK_API_KEY"]


# 🔄 시스템 캐시 클리어 함수 (관리자용)
@app.post("/admin/clear-cache")
async def clear_cache(company_id: str = Depends(get_company_id)):
    """
    관리자 전용: 시스템 캐시 클리어
    """
    try:
        # 캐시 클리어 로직
        cache.clear()
        ticket_summary_cache.clear()
        
        logger.info(f"캐시 클리어 완료 - company_id: {company_id}")
        return {"status": "success", "message": "캐시가 성공적으로 클리어되었습니다."}
    except Exception as e:
        logger.error(f"캐시 클리어 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"캐시 클리어 실패: {str(e)}")


# =====================================================================
# 아래는 다른 API 엔드포인트들이 계속됩니다
# =====================================================================


@app.get("/similar_tickets/{ticket_id}", response_model=SimilarTicketsResponse)
async def get_similar_tickets(
    ticket_id: str, 
    company_id: str = Depends(get_company_id),
    x_freshdesk_domain: Optional[str] = Header(None, alias="X-Freshdesk-Domain"),
    x_freshdesk_api_key: Optional[str] = Header(None, alias="X-Freshdesk-API-Key")
):
    """
    특정 티켓 ID와 유사한 과거 티켓 목록을 검색하여 반환합니다.
    
    Args:
        ticket_id: 검색 기준이 되는 티켓 ID
        company_id: 회사 ID (자동 추출)
        x_freshdesk_domain: Freshdesk 도메인 (헤더에서 전달)
        x_freshdesk_api_key: Freshdesk API 키 (헤더에서 전달)
    """
    logger.info(f"유사 티켓 검색 요청: ticket_id={ticket_id}, domain={x_freshdesk_domain}")
    
    # Freshdesk 설정값이 헤더로 전달된 경우 임시로 환경변수에 설정
    original_domain = os.getenv("FRESHDESK_DOMAIN")
    original_api_key = os.getenv("FRESHDESK_API_KEY")
    
    try:
        if x_freshdesk_domain:
            os.environ["FRESHDESK_DOMAIN"] = x_freshdesk_domain
            
        if x_freshdesk_api_key:
            os.environ["FRESHDESK_API_KEY"] = x_freshdesk_api_key
        
        logger.info(f"유사 티켓 검색 시작 (ticket_id: {ticket_id})")
        
        # 1. 현재 티켓 데이터 조회
        current_ticket_data = vector_db.get_by_id(original_id_value=ticket_id, company_id=company_id, doc_type="ticket")
        
        if not current_ticket_data or not current_ticket_data.get("metadata"):
            # Freshdesk API 호출을 위한 파라미터 준비
            domain = x_freshdesk_domain or os.getenv("FRESHDESK_DOMAIN")
            api_key = x_freshdesk_api_key or os.getenv("FRESHDESK_API_KEY")
            
            if not domain or not api_key:
                raise HTTPException(
                    status_code=400,
                    detail="Freshdesk 도메인과 API 키가 필요합니다. 헤더 또는 환경변수로 제공해주세요."
                )
            
            # Qdrant에서 찾을 수 없으면 Freshdesk API에서 가져오기
            current_ticket_data = await fetcher.fetch_ticket_details(int(ticket_id), domain=domain, api_key=api_key)
            if not current_ticket_data:
                raise HTTPException(status_code=404, detail=f"티켓 ID {ticket_id}를 찾을 수 없습니다.")
        else:
            # Qdrant에서 가져온 경우 metadata를 최상위로 올리기
            current_ticket_data = current_ticket_data["metadata"]
        
        # 2. 검색용 쿼리 텍스트 생성
        search_query = ""
        subject = current_ticket_data.get("subject", "")
        description = current_ticket_data.get("description", current_ticket_data.get("description_text", ""))
        
        if subject:
            search_query += subject
        if description:
            search_query += " " + description[:200]  # 처음 200자만 사용
            
        if not search_query.strip():
            logger.warning(f"티켓 {ticket_id}에 대한 검색 쿼리 텍스트가 비어있습니다.")
            return SimilarTicketsResponse(ticket_id=ticket_id, similar_tickets=[])
        
        # 3. 검색 쿼리 임베딩 생성
        try:
            from core.embedder import generate_embedding
            query_embedding = await generate_embedding(search_query)
        except Exception as e:
            logger.error(f"임베딩 생성 실패: {e}")
            # 임베딩 생성 실패 시 더미 임베딩 사용 (fallback)
            query_embedding = [0.1] * 1536  # OpenAI embedding 차원에 맞춤
        
        # 벡터 DB에서 유사 티켓 검색
        similar_tickets_result = retriever.retrieve_top_k_docs(
            query_embedding=query_embedding, 
            top_k=6,  # 3개 결과를 위해 6개 가져와서 필터링 (현재 티켓 제외)
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
                # Freshdesk 도메인이 없는 경우 오류 처리 (기본값 제공하지 않음)
                if not x_freshdesk_domain:
                    raise ValueError("Freshdesk 도메인을 찾을 수 없습니다. 환경변수 또는 헤더로 제공해주세요.")
                
                # 보안: 예시 도메인 거부
                invalid_domains = ["your-domain", "example", "test", "demo", "sample"]
                domain_base = x_freshdesk_domain.replace(".freshdesk.com", "").lower()
                if domain_base in invalid_domains:
                    raise ValueError(f"유효하지 않은 도메인입니다: {x_freshdesk_domain}")
                
                ticket_url = f"https://{x_freshdesk_domain}"
                if not x_freshdesk_domain.endswith(".freshdesk.com"):
                    ticket_url += ".freshdesk.com"
                ticket_url += f"/a/tickets/{ticket_number}"
                
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
                    similarity_score=round(similarity_score, 3)
                ))
                
                # 최대 3개까지만 반환 (성능 최적화)
                if len(similar_tickets_list) >= 3:
                    break
        
        logger.info(f"티켓 {ticket_id} 유사 티켓 검색 완료: {len(similar_tickets_list)}건")
        return SimilarTicketsResponse(ticket_id=str(ticket_id), similar_tickets=similar_tickets_list)
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"유사 티켓 검색 중 오류 발생 (티켓 ID: {ticket_id}): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"유사 티켓 검색 중 내부 서버 오류 발생: {str(e)}")
    finally:
        # 환경변수 복원
        if original_domain is not None:
            os.environ["FRESHDESK_DOMAIN"] = original_domain
        elif "FRESHDESK_DOMAIN" in os.environ:
            del os.environ["FRESHDESK_DOMAIN"]
            
        if original_api_key is not None:
            os.environ["FRESHDESK_API_KEY"] = original_api_key
        elif "FRESHDESK_API_KEY" in os.environ:
            del os.environ["FRESHDESK_API_KEY"]

@app.get("/related_docs/{ticket_id}", response_model=RelatedDocsResponse)
async def get_related_documents(
    ticket_id: str, 
    company_id: str = Depends(get_company_id),
    x_freshdesk_domain: Optional[str] = Header(None, alias="X-Freshdesk-Domain"),
    x_freshdesk_api_key: Optional[str] = Header(None, alias="X-Freshdesk-API-Key")
):
    """
    특정 티켓 ID와 관련된 기술 문서(KB)나 FAQ 목록을 검색하여 반환합니다.
    
    Args:
        ticket_id: 관련 문서를 검색할 기준이 되는 티켓의 고유 ID
        company_id: 회사 ID (헤더에서 자동 추출)
        x_freshdesk_domain: Freshdesk 도메인 (헤더에서 전달)
        x_freshdesk_api_key: Freshdesk API 키 (헤더에서 전달)
        
    Returns:
        RelatedDocsResponse: 관련 문서 목록
    """
    logger.info(f"관련 문서 검색 요청: ticket_id={ticket_id}, domain={x_freshdesk_domain}")
    
    # Freshdesk 설정값이 헤더로 전달된 경우 임시로 환경변수에 설정
    original_domain = os.getenv("FRESHDESK_DOMAIN")
    original_api_key = os.getenv("FRESHDESK_API_KEY")
    
    try:
        if x_freshdesk_domain:
            os.environ["FRESHDESK_DOMAIN"] = x_freshdesk_domain
            logger.info(f"Freshdesk 도메인을 '{x_freshdesk_domain}'으로 임시 설정")
            
        if x_freshdesk_api_key:
            os.environ["FRESHDESK_API_KEY"] = x_freshdesk_api_key
            logger.info("Freshdesk API 키를 헤더값으로 임시 설정")
            
        logger.info(f"관련 문서 검색 시작 (ticket_id: {ticket_id})")
        
        # 1. 현재 티켓 데이터 조회
        current_ticket_data = vector_db.get_by_id(original_id_value=ticket_id, company_id=company_id, doc_type="ticket")
        
        if not current_ticket_data or not current_ticket_data.get("metadata"):
            # Qdrant에서 찾을 수 없으면 Freshdesk API에서 가져오기
            try:
                current_ticket_data = await fetcher.fetch_ticket_details(int(ticket_id))
            except Exception as api_error:
                logger.error(f"Freshdesk API 조회 실패: {api_error}")
                current_ticket_data = None
                
            if not current_ticket_data:
                raise HTTPException(status_code=404, detail=f"티켓 ID {ticket_id}를 찾을 수 없습니다.")
        else:
            # Qdrant에서 가져온 경우 metadata를 최상위로 올리기
            current_ticket_data = current_ticket_data["metadata"]
        
        # 3. 검색용 쿼리 텍스트 생성 및 임베딩 (중복 방지 최적화)
        search_query = None
        query_embedding = None
        
        try:
            # 간단한 검색 쿼리 생성 (티켓 제목과 내용 조합)
            subject = current_ticket_data.get("subject", "")
            description = current_ticket_data.get("description", "") or current_ticket_data.get("description_text", "")
            search_query = ""
            if subject:
                search_query += subject
            if description:
                search_query += " " + description[:200]  # 처음 200자만 사용
            
            # 생성된 쿼리로 임베딩 생성
            if search_query and search_query.strip():
                logger.info(f"⚡ 검색 쿼리 임베딩 생성 시작: '{search_query[:100]}...'")
                from core.embedder import generate_embedding
                query_embedding = await generate_embedding(search_query)
                logger.info("⚡ 검색 쿼리 임베딩 생성 완료")
            else:
                logger.warning(f"티켓 {ticket_id}에 대한 검색 쿼리 텍스트가 비어있습니다.")
        except Exception as query_error:
            logger.error(f"검색 쿼리 생성 또는 임베딩 실패: {query_error}")
            # 최종 폴백: 더미 임베딩 사용
            query_embedding = [0.1] * 1536
            logger.warning("⚡ 더미 임베딩 사용")
        
        if not query_embedding:
            logger.warning(f"티켓 {ticket_id}에 대한 임베딩을 생성할 수 없어 빈 결과를 반환합니다.")
            return RelatedDocsResponse(ticket_id=ticket_id, related_documents=[])
        
        # 4. 벡터 DB에서 관련 문서 검색 (KB, FAQ 등)
        related_docs_result = None
        try:
            # KB 문서는 type이 1인 경우 (published 상태)
            # 또는 source_type이 "kb"인 경우로 식별
            related_docs_result = retriever.retrieve_top_k_docs(
                query_embedding=query_embedding, 
                top_k=10,  # 더 많이 가져와서 필터링
                doc_type="kb",  # "kb" 타입으로 검색
                company_id=company_id
            )
            
            # 🚀 KB 문서만 검색 (DB 레벨 필터링)
            all_results = vector_db.search(
                query_embedding=query_embedding,
                top_k=30,  # KB 문서를 더 많이 검색
                company_id=company_id,
                doc_type="kb"  # KB 타입 명시적 지정
            )
            
            # 검색 결과에서 KB 문서만 추출
            documents = []
            metadatas = []
            distances = []
            ids = []
            
            # 결과가 있는 경우 필터링
            if all_results and all_results.get("results"):
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
        except Exception as kb_error:
            logger.error(f"KB 문서 검색 실패: {kb_error}")
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
                            # 헤더에서 전달된 Freshdesk 도메인 사용 (iparams 값)
                            freshdesk_domain = x_freshdesk_domain or os.getenv("FRESHDESK_DOMAIN")
                            # 도메인 검증 및 URL 구성
                            if not freshdesk_domain:
                                logger.warning("Freshdesk 도메인이 헤더나 환경변수에 설정되지 않았습니다.")
                                url = None
                            elif freshdesk_domain in ["your-domain.freshdesk.com", "example.freshdesk.com"]:
                                logger.warning(f"유효하지 않은 기본 도메인 감지: {freshdesk_domain}")
                                url = None
                            else:
                                # 스마트 도메인 파싱 적용 (fetcher 모듈의 함수 사용)
                                try:
                                    from freshdesk.fetcher import smart_domain_parsing
                                    normalized_domain = smart_domain_parsing(freshdesk_domain)
                                    url = f"https://{normalized_domain}/support/solutions/articles/{article_id}"
                                except Exception as e:
                                    logger.warning(f"도메인 파싱 실패 ({freshdesk_domain}): {e}")
                                    url = None
                    
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
        
        # 너무 낮은 유사도 점수의 결과 필터링 - 임계값 0.25 (25%)
        min_similarity = 0.25
        filtered_docs = [doc for doc in related_docs_list if doc.similarity_score >= min_similarity]
        
        # 최대 반환 결과 수 제한 (상위 5개)
        if filtered_docs:
            related_docs_list = filtered_docs[:5]
        else:
            # 유사도가 낮더라도 검색 결과가 있으면 결과는 반환
            if related_docs_list:
                related_docs_list = related_docs_list[:3]
            else:
                # 결과가 전혀 없으면 빈 응답 반환
                logger.warning("관련 문서 검색 결과가 없습니다.")
        
        # 결과 통계 로깅
        docs_by_type = {}
        for doc in related_docs_list:
            doc_type = doc.source_type or "unknown"
            docs_by_type[doc_type] = docs_by_type.get(doc_type, 0) + 1
                
        logger.info(f"티켓 {ticket_id} 관련 문서 검색 완료: {len(related_docs_list)}건")
        return RelatedDocsResponse(ticket_id=ticket_id, related_documents=related_docs_list)
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"관련 문서 검색 중 오류 발생 (티켓 ID: {ticket_id}): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"관련 문서 검색 중 내부 서버 오류 발생: {str(e)}")
    finally:
        # 환경변수 복원
        if original_domain is not None:
            os.environ["FRESHDESK_DOMAIN"] = original_domain
        elif "FRESHDESK_DOMAIN" in os.environ:
            del os.environ["FRESHDESK_DOMAIN"]
            
        if original_api_key is not None:
            os.environ["FRESHDESK_API_KEY"] = original_api_key
        elif "FRESHDESK_API_KEY" in os.environ:
            del os.environ["FRESHDESK_API_KEY"]
        
        
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
    
    logger.info(f"티켓 ID {ticket_id}에 대한 응답 생성 시작")
    
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
        logger.info(f"자연어 검색 시작 (query: {req.query[:50]}...)")
        
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
        
        # 1. 검색 쿼리 임베딩 생성 (LLM Router 사용으로 중복 방지)
        logger.info(f"⚡ 검색 쿼리 임베딩 생성 시작: '{req.query[:50]}...'")
        try:
            query_embedding = await llm_router.generate_embedding(req.query)
            logger.info("⚡ 검색 쿼리 임베딩 생성 완료")
        except Exception as e:
            logger.error(f"임베딩 생성 실패: {e}")
            # 임베딩 생성 실패 시 더미 임베딩 사용 (fallback)
            query_embedding = [0.1] * 1536  # OpenAI embedding 차원에 맞춤
            logger.warning("⚡ 더미 임베딩 사용")
        
        # 2. 검색할 문서 유형 결정
        search_types = req.search_types if req.search_types and req.search_types != ["all"] else ["ticket", "kb"]
        
        all_results = []
        
        # 3. 통합 검색 수행 (병렬 처리로 성능 최적화)
        async def search_by_type(doc_type):
            try:
                return retriever.retrieve_top_k_docs(
                    query_embedding=query_embedding,
                    top_k=req.top_k,
                    doc_type=doc_type,
                    company_id=company_id
                )
            except Exception as e:
                logger.error(f"{doc_type} 검색 실패: {e}")
                return {"ids": [], "documents": [], "metadatas": [], "distances": []}
        
        # 병렬 검색 실행
        search_tasks = [search_by_type(doc_type) for doc_type in search_types]
        search_results = await asyncio.gather(*search_tasks)
        
        # 4. 검색 결과 통합 및 변환
        for doc_type, search_result in zip(search_types, search_results):
            if search_result and search_result.get("ids"):
                for i, doc_id in enumerate(search_result["ids"]):
                    try:
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
        
        logger.info(f"자연어 검색 완료: {len(final_results)}건 ({search_time_ms}ms)")
        
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


@app.post("/ingest", response_model=IngestResponse)
async def trigger_data_ingestion(
    request: IngestRequest,
    company_id: str = Depends(get_company_id),
    x_freshdesk_domain: Optional[str] = Header(None, alias="X-Freshdesk-Domain"),
    x_freshdesk_api_key: Optional[str] = Header(None, alias="X-Freshdesk-API-Key")
):
    """
    Freshdesk 데이터 수집을 트리거하는 엔드포인트
    
    헤더로 전달된 동적 Freshdesk 도메인과 API 키를 사용하거나
    환경변수에 설정된 기본값을 사용하여 데이터를 수집합니다.
    
    Args:
        request: 데이터 수집 옵션
        company_id: 회사 ID (헤더에서 자동 추출)
        x_freshdesk_domain: Freshdesk 도메인 (헤더에서 전달, 선택사항)
        x_freshdesk_api_key: Freshdesk API 키 (헤더에서 전달, 선택사항)
        
    Returns:
        IngestResponse: 수집 결과 정보
    """
    start_time = datetime.now()
    logger.info(f"데이터 수집 시작 - Company: {company_id}, Domain: {x_freshdesk_domain}")
    
    try:
        # 동적 Freshdesk 구성을 사용하여 데이터 수집 실행
        await ingest(
            incremental=request.incremental,
            purge=request.purge,
            process_attachments=request.process_attachments,
            force_rebuild=request.force_rebuild,
            local_data_dir=None,  # API 호출이므로 로컬 데이터 사용 안함
            include_kb=request.include_kb,
            domain=x_freshdesk_domain,
            api_key=x_freshdesk_api_key
        )
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        logger.info(f"데이터 수집 완료 - Company: {company_id}, 소요시간: {duration:.2f}초")
        
        return IngestResponse(
            success=True,
            message="데이터 수집이 성공적으로 완료되었습니다.",
            start_time=start_time.isoformat(),
            end_time=end_time.isoformat(),
            duration_seconds=duration
        )
        
    except HTTPException as e:
        raise e
    except Exception as e:
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        logger.error(f"데이터 수집 중 오류 발생 - Company: {company_id}: {e}", exc_info=True)
        
        return IngestResponse(
            success=False,
            message=f"데이터 수집 중 오류가 발생했습니다: {str(e)}",
            start_time=start_time.isoformat(),
            end_time=end_time.isoformat(),
            duration_seconds=duration,
            error=str(e)
        )


# SSE 스트리밍 지원 함수들

async def get_similar_tickets_data(ticket_id: str, company_id: str, top_k: int = 3) -> SimilarTicketsResponse:
    """
    유사 티켓 데이터를 가져오는 내부 함수
    
    Args:
        ticket_id: 기준 티켓 ID
        company_id: 회사 ID
        top_k: 반환할 최대 결과 수
        
    Returns:
        SimilarTicketsResponse: 유사 티켓 응답 객체
    """
    try:
        # 기존 get_similar_tickets 함수 로직을 재사용
        current_ticket_data = vector_db.get_by_id(original_id_value=ticket_id, company_id=company_id, doc_type="ticket")
        
        if not current_ticket_data or not current_ticket_data.get("metadata"):
            logger.warning(f"티켓 ID {ticket_id} 정보를 찾을 수 없습니다.")
            return SimilarTicketsResponse(ticket_id=ticket_id, similar_tickets=[])
        
        current_ticket_data = current_ticket_data["metadata"]
        
        # 검색용 쿼리 텍스트 생성
        search_query = await llm_router.generate_search_query(current_ticket_data)
        if not search_query.strip():
            return SimilarTicketsResponse(ticket_id=ticket_id, similar_tickets=[])
        
        # 검색 쿼리 임베딩 생성
        try:
            query_embedding = await llm_router.generate_embedding(search_query)
        except Exception as e:
            logger.error(f"임베딩 생성 실패: {e}")
            query_embedding = [0.1] * 1536
        
        # 벡터 DB에서 유사 티켓 검색
        similar_tickets_result = retriever.retrieve_top_k_docs(
            query_embedding=query_embedding, 
            top_k=min(6, top_k * 2),  # 3개 결과를 위해 6개 가져와서 필터링 (현재 티켓 제외)
            doc_type="ticket",
            company_id=company_id
        )
        
        # 검색 결과 처리 - Issue/Solution 분석을 위한 데이터 준비
        analysis_tasks = []
        base_infos = []
        
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
                similarity_score = max(0, 1 - distance)
                
                # 요약 정보
                summary_text = similar_tickets_result["documents"][i] if i < len(similar_tickets_result.get("documents", [])) else ""
                if not summary_text:
                    summary_text = metadata.get("description_text", "요약 정보 없음")
                
                summary = summary_text[:200] + "..." if len(summary_text) > 200 else summary_text
                
                # Issue/Solution 분석을 위한 티켓 데이터 구성
                ticket_data_for_analysis = {
                    "id": str(doc_id),
                    "subject": title,
                    "description_text": summary_text,
                    "status": metadata.get("status", ""),
                    "priority": metadata.get("priority", "")
                }
                
                # 병렬 분석을 위한 태스크 추가
                analysis_tasks.append(llm_router.analyze_ticket_issue_solution(ticket_data_for_analysis))
                base_infos.append({
                    "id": str(doc_id),
                    "title": title,
                    "similarity_score": round(similarity_score, 3),
                    "ticket_summary": summary
                })
                
                # 최대 결과 수 제한
                if len(base_infos) >= top_k:
                    break
        
        # Issue/Solution 분석을 병렬로 실행
        similar_tickets_list = []
        if analysis_tasks:
            logger.info(f"📊 {len(analysis_tasks)}개 티켓의 Issue/Solution 분석을 병렬로 시작...")
            analysis_start_time = time.time()
            
            results = await asyncio.gather(*analysis_tasks, return_exceptions=True)
            
            analysis_end_time = time.time()
            logger.info(f"✅ Issue/Solution 분석 완료: {analysis_end_time - analysis_start_time:.2f}초")
            
            for info, res in zip(base_infos, results):
                if isinstance(res, Exception):
                    logger.warning(f"티켓 {info['id']} Issue/Solution 분석 실패: {res}")
                    # 원본 티켓 요약과 동일한 형태로 마크다운 헤더와 이모지 추가
                    issue = "## 🔍 Issue\n\n문제 상황 분석 실패"
                    solution = "## ⚡ Solution\n\n해결책 분석 실패"
                else:
                    # res는 dict 타입인 경우에만 .get() 메서드 사용
                    if isinstance(res, dict):
                        # 원본 티켓 요약과 동일한 형태로 Issue와 Solution에 마크다운 헤더와 이모지 추가
                        raw_issue = res.get("issue", "문제 상황을 분석할 수 없습니다.")
                        raw_solution = res.get("solution", "해결책을 찾을 수 없습니다.")
                        
                        issue = f"## 🔍 Issue\n\n{raw_issue}"
                        solution = f"## ⚡ Solution\n\n{raw_solution}"
                    else:
                        issue = "## 🔍 Issue\n\n문제 상황을 분석할 수 없습니다."
                        solution = "## ⚡ Solution\n\n해결책을 찾을 수 없습니다."
                
                similar_tickets_list.append(SimilarTicketItem(
                    id=info["id"],
                    title=info["title"],
                    issue=issue,
                    solution=solution,
                    similarity_score=info["similarity_score"]
                ))
        
        return SimilarTicketsResponse(ticket_id=ticket_id, similar_tickets=similar_tickets_list)
        
    except Exception as e:
        logger.error(f"유사 티켓 데이터 가져오기 실패: {e}")
        return SimilarTicketsResponse(ticket_id=ticket_id, similar_tickets=[])


async def get_related_docs_data(ticket_id: str, company_id: str, top_k: int = 5) -> RelatedDocsResponse:
    """
    관련 문서 데이터를 가져오는 내부 함수
    
    Args:
        ticket_id: 기준 티켓 ID
        company_id: 회사 ID
        top_k: 반환할 최대 결과 수
        
    Returns:
        RelatedDocsResponse: 관련 문서 응답 객체
    """
    try:
        # 기존 get_related_documents 함수 로직을 재사용
        current_ticket_data = vector_db.get_by_id(original_id_value=ticket_id, company_id=company_id, doc_type="ticket")
        
        if not current_ticket_data or not current_ticket_data.get("metadata"):
            logger.warning(f"티켓 ID {ticket_id} 정보를 찾을 수 없습니다.")
            return RelatedDocsResponse(ticket_id=ticket_id, related_documents=[])
        
        current_ticket_data = current_ticket_data["metadata"]
        
        # 검색용 쿼리 텍스트 생성
        try:
            search_query = await llm_router.generate_search_query(current_ticket_data)
        except Exception as query_error:
            logger.error(f"검색 쿼리 생성 실패: {query_error}")
            subject = current_ticket_data.get("subject", "")
            description = current_ticket_data.get("description", "")
            search_query = f"{subject} {description[:200]}"
        
        if not search_query or not search_query.strip():
            return RelatedDocsResponse(ticket_id=ticket_id, related_documents=[])
        
        # 검색 쿼리 임베딩 생성
        try:
            query_embedding = await llm_router.generate_embedding(search_query)
        except Exception as e:
            logger.error(f"임베딩 생성 실패: {e}")
            query_embedding = [0.1] * 1536
        
        # 벡터 DB에서 관련 문서 검색
        related_docs_result = retriever.retrieve_top_k_docs(
            query_embedding=query_embedding, 
            top_k=min(10, top_k * 2),
            doc_type="kb",
            company_id=company_id
        )
        
        # 검색 결과 처리
        related_docs_list = []
        if related_docs_result and related_docs_result.get("ids"):
            doc_ids = related_docs_result.get("ids", [])
            metadatas = related_docs_result.get("metadatas", [])
            documents = related_docs_result.get("documents", [])
            distances = related_docs_result.get("distances", [])
            
            for i, doc_id in enumerate(doc_ids):
                metadata = metadatas[i] if i < len(metadatas) else {}
                
                title = metadata.get("title", f"문서 {doc_id}")
                
                # 문서 요약 생성
                summary_text = documents[i] if i < len(documents) else ""
                if not summary_text:
                    summary_text = metadata.get("description", "요약 정보 없음")
                
                summary = summary_text[:200] + "..." if len(summary_text) > 200 else summary_text
                
                # 거리/점수 정보 추가
                distance = distances[i] if i < len(distances) else 0
                similarity_score = max(0, 1 - distance)
                
                # URL 생성
                url = metadata.get("url", "")
                
                related_docs_list.append(RelatedDocumentItem(
                    id=str(doc_id),
                    title=title,
                    doc_summary=summary,
                    url=url,
                    source_type="kb",
                    similarity_score=round(similarity_score, 3)
                ))
                
                # 최대 결과 수 제한
                if len(related_docs_list) >= top_k:
                    break
        
        return RelatedDocsResponse(ticket_id=ticket_id, related_documents=related_docs_list)
        
    except Exception as e:
        logger.error(f"관련 문서 데이터 가져오기 실패: {e}")
        return RelatedDocsResponse(ticket_id=ticket_id, related_documents=[])


async def sse_generator(data_generator):
    """
    SSE(Server-Sent Events) 스트리밍을 위한 제너레이터
    
    Args:
        data_generator: 데이터를 생성하는 비동기 제너레이터
        
    Yields:
        SSE 형식의 문자열 데이터
    """
    try:
        async for data in data_generator:
            if data:
                # SSE 형식으로 데이터 전송
                yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
    except Exception as e:
        # 에러 발생 시 에러 정보를 SSE로 전송
        error_data = {
            "type": "error",
            "message": str(e),
            "timestamp": datetime.now().isoformat()
        }
        yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"
    finally:
        # 스트림 종료 신호
        yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"


async def streaming_query_generator(req: QueryRequest, company_id: str):
    """
    쿼리 처리를 스트리밍으로 수행하는 제너레이터
    
    Args:
        req: 쿼리 요청 객체
        company_id: 회사 ID
        
    Yields:
        각 단계별 진행 상황과 결과
    """
    try:
        start_time = time.time()
        
        # 1. 초기화 단계
        yield {
            "type": "progress",
            "stage": "initialization",
            "message": "쿼리 처리를 시작합니다...",
            "progress": 10
        }
        
        # 티켓 정보 조회 (있는 경우)
        ticket_context_for_query = ""
        ticket_context_for_llm = ""
        
        if req.ticket_id:
            yield {
                "type": "progress", 
                "stage": "ticket_loading",
                "message": f"티켓 ID {req.ticket_id} 정보를 조회하는 중...",
                "progress": 20
            }
            
            ticket_data = vector_db.get_by_id(original_id_value=req.ticket_id, company_id=company_id, doc_type="ticket")
            if ticket_data and ticket_data.get("metadata"):
                metadata = ticket_data["metadata"]
                ticket_title = metadata.get("subject", f"티켓 ID {req.ticket_id} 관련 문의")
                ticket_body = metadata.get("text", metadata.get("description_text", "티켓 본문 정보 없음"))
                ticket_context_for_query = f"현재 티켓 제목: {ticket_title}\n현재 티켓 본문: {ticket_body}"
                ticket_context_for_llm = f"\n[현재 티켓 정보]\n제목: {ticket_title}\n본문: {ticket_body}\n"
        
        # 2. 임베딩 생성 단계
        yield {
            "type": "progress",
            "stage": "embedding",
            "message": "쿼리 임베딩을 생성하는 중...",
            "progress": 30
        }
        
        query_for_embedding_str = f"{ticket_context_for_query}\n\n사용자 질문: {req.query}" if req.ticket_id else req.query
        # ⚡ LLM Router를 통한 최적화된 임베딩 생성 (중복 호출 방지)
        query_embedding = await llm_router.generate_embedding(query_for_embedding_str)
        
        # 3. 문서 검색 단계
        yield {
            "type": "progress",
            "stage": "searching",
            "message": "관련 문서를 검색하는 중...",
            "progress": 50
        }
        
        content_types = [t.lower() for t in req.type] if req.type else ["tickets", "solutions", "images", "attachments"]
        top_k_per_type = max(1, req.top_k // len([t for t in content_types if t in ["tickets", "solutions"]]))
        
        # ⚡ 병렬 검색 실행 (성능 최적화)
        search_tasks = []
        
        if "tickets" in content_types:
            search_tasks.append(asyncio.create_task(
                asyncio.to_thread(retrieve_top_k_docs, query_embedding, top_k_per_type, company_id, "ticket")
            ))
        else:
            search_tasks.append(asyncio.create_task(
                asyncio.sleep(0, result={"documents": [], "metadatas": [], "ids": [], "distances": []})
            ))
        
        if "solutions" in content_types:
            search_tasks.append(asyncio.create_task(
                asyncio.to_thread(retrieve_top_k_docs, query_embedding, top_k_per_type, company_id, "kb")
            ))
        else:
            search_tasks.append(asyncio.create_task(
                asyncio.sleep(0, result={"documents": [], "metadatas": [], "ids": [], "distances": []})
            ))
        
        # 병렬 검색 결과 수집
        ticket_results, kb_results = await asyncio.gather(*search_tasks)
        
        logger.info(f"⚡ 스트리밍 병렬 검색 완료 - 티켓: {len(ticket_results.get('documents', []))}건, KB: {len(kb_results.get('documents', []))}건")
        
        # 4. 컨텍스트 구성 단계
        yield {
            "type": "progress",
            "stage": "context_building",
            "message": "검색 결과를 분석하고 컨텍스트를 구성하는 중...",
            "progress": 70
        }
        
        # 검색 결과 병합 및 정렬
        all_docs_content = ticket_results["documents"] + kb_results["documents"]
        all_metadatas = ticket_results["metadatas"] + kb_results["metadatas"]
        all_distances = ticket_results["distances"] + kb_results["distances"]
        
        # 메타데이터에 source_type 추가
        for meta in ticket_results["metadatas"]:
            meta["source_type"] = "ticket"
        for meta in kb_results["metadatas"]:
            meta["source_type"] = "kb"
        # 문서 타입별 메타데이터 설정 완료

        combined = list(zip(all_docs_content, all_metadatas, all_distances))
        combined.sort(key=lambda x: x[2])
        combined = combined[:req.top_k]
        
        docs = [item[0] for item in combined]
        metadatas = [item[1] for item in combined]
        distances = [item[2] for item in combined]
        
        # 컨텍스트 최적화
        base_context, optimized_metadatas, context_meta = build_optimized_context(
            docs=docs,
            metadatas=metadatas,
            query=req.query,
            max_tokens=8000,
            top_k=req.top_k,
            enable_relevance_extraction=True
        )
        
        # 5. AI 응답 생성 단계
        yield {
            "type": "progress",
            "stage": "generating",
            "message": "AI 응답을 생성하는 중...",
            "progress": 85
        }
        
        final_context_for_llm = f"{ticket_context_for_llm}{base_context}"
        prompt = build_prompt(final_context_for_llm, req.query, answer_instructions=req.answer_instructions)
        
        # 시스템 프롬프트 설정
        search_intent = req.intent.lower() if req.intent else "search"
        base_system_prompt = "당신은 친절한 고객 지원 AI입니다."
        
        if search_intent == "recommend":
            base_system_prompt += " 고객의 질문에 대해 최적의 솔루션을 추천해 주세요."
        elif search_intent == "answer":
            base_system_prompt += " 고객의 질문에 직접적이고 명확하게 답변해 주세요."
        
        system_prompt = base_system_prompt
        if req.answer_instructions:
            system_prompt = f"{base_system_prompt} 다음 지침에 따라 응답해 주세요: {req.answer_instructions}"
        
        response = await call_llm(prompt, system_prompt=system_prompt)
        answer = response.text
        
        # 구조화된 문서 정보 생성
        structured_docs = []
        for i, (doc_content_item, metadata_item, distance_or_score_metric) in enumerate(zip(docs, metadatas, distances)):
            title = metadata_item.get("title", "")
            content = doc_content_item
            doc_type = metadata_item.get("source_type", "unknown")

            lines = doc_content_item.split("\n", 2)
            if len(lines) > 0 and lines[0].startswith("제목:"):
                title = lines[0].replace("제목:", "").strip()
                if len(lines) > 1:
                    content = "\n".join(lines[1:]).strip()
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
    
        # 6. 최종 결과 전송
        yield {
            "type": "progress",
            "stage": "complete",
            "message": "처리가 완료되었습니다.",
            "progress": 100
        }
        
        total_time = time.time() - start_time
        
        # 최종 결과 전송
        final_result = {
            "type": "result",
            "data": {
                "answer": answer,
                "context_docs": [doc.dict() for doc in structured_docs],
                "context_images": [],
                "metadata": {
                    "duration_ms": int(total_time * 1000),
                    "model_used": response.model_used,
                    "search_intent": search_intent,
                    "content_types": content_types,
                    "ticket_id": req.ticket_id,
                    "optimization": context_meta
                }
            }
        }
        
        yield final_result
        
    except Exception as e:
        logger.error(f"스트리밍 쿼리 처리 중 오류 발생: {e}")
        yield {
            "type": "error",
            "message": f"쿼리 처리 중 오류가 발생했습니다: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }


async def streaming_reply_generator(req: GenerateReplyRequest, company_id: str):
    """
    응답 생성을 스트리밍으로 수행하는 제너레이터
    
    Args:
        req: 응답 생성 요청 객체
        company_id: 회사 ID
        
    Yields:
        각 단계별 진행 상황과 결과
    """
    try:
        start_time = time.time()
        
        # 1. 컨텍스트 검증
        yield {
            "type": "progress",
            "stage": "context_validation",
            "message": f"컨텍스트 ID {req.context_id} 검증 중...",
            "progress": 20
        }
        
        # 컨텍스트 ID가 캐시에 있는지 확인
        if req.context_id not in ticket_context_cache:
            # 캐시에 없으면 기본 메시지 생성
            yield {
                "type": "error",
                "message": f"컨텍스트 ID {req.context_id}를 찾을 수 없습니다. 먼저 /init 엔드포인트를 호출해주세요.",
                "progress": 100
            }
            return
            
        context_data = ticket_context_cache[req.context_id]
        
        # 2. 컨텍스트에서 티켓 정보 추출
        yield {
            "type": "progress",
            "stage": "extracting_context",
            "message": "저장된 컨텍스트에서 티켓 정보를 추출하는 중...",
            "progress": 40
        }
        
        # 캐시된 컨텍스트에서 필요한 정보 추출
        ticket_summary = context_data.get("ticket_summary", {})
        similar_tickets = context_data.get("similar_tickets", [])
        related_docs = context_data.get("related_documents", [])
        
        # 3. 응답 생성 준비
        yield {
            "type": "progress",
            "stage": "preparing_generation",
            "message": "응답 생성을 준비하는 중...",
            "progress": 60
        }
        
        # 4. AI 응답 생성
        yield {
            "type": "progress",
            "stage": "generating_reply",
            "message": "AI 응답을 생성하는 중...",
            "progress": 80
        }
        
        # 컨텍스트 구성
        context_parts = []
        
        if ticket_summary:
            context_parts.append(f"현재 티켓 요약:\n{ticket_summary.get('ticket_summary', '')}")
        
        if similar_tickets:
            context_parts.append("유사 티켓들:")
            for ticket in similar_tickets[:3]:
                title = ticket.get('title', '')
                solution = ticket.get('solution', '') or ticket.get('issue', '')
                context_parts.append(f"- {title}: {solution}")
        
        if related_docs:
            context_parts.append("관련 문서들:")
            for doc in related_docs[:3]:
                title = doc.get('title', '')
                summary = doc.get('doc_summary', '')
                context_parts.append(f"- {title}: {summary}")
        
        context = "\n".join(context_parts)
        
        # 스타일과 톤 지침 적용
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
        
        style_instruction = style_guide.get(req.style or "professional", style_guide["professional"])
        tone_instruction = tone_guide.get(req.tone or "helpful", tone_guide["helpful"])
        
        # 응답 생성을 위한 프롬프트
        prompt = f"""다음 티켓에 대한 전문적인 응답을 작성해 주세요:

{context}

응답 지침:
1. {style_instruction}
2. {tone_instruction}"""

        if req.instructions:
            prompt += f"\n3. {req.instructions}"
            
        if req.include_greeting:
            prompt += "\n4. 적절한 인사말로 응답을 시작하세요."
            
        if req.include_signature:
            prompt += "\n5. 응답 끝에 적절한 서명을 포함하세요."
            
        prompt += """

응답 요구사항:
- 고객의 문제를 정확히 이해했음을 보여주세요
- 구체적이고 실행 가능한 해결책을 제시해 주세요
- 단계별 가이드가 필요한 경우 명확하게 설명해 주세요
- 추가 도움이 필요한 경우 연락 방법을 안내해 주세요

응답:"""
        
        system_prompt = "당신은 전문적이고 친절한 고객 지원 담당자입니다. 고객의 문제를 정확히 파악하고 최적의 해결책을 제공해 주세요."
        
        response = await call_llm(prompt, system_prompt=system_prompt)
        generated_reply = response.text
        
        # 5. 완료
        yield {
            "type": "progress",
            "stage": "complete",
            "message": "응답 생성이 완료되었습니다.",
            "progress": 100
        }
        
        total_time = time.time() - start_time
        
        # 최종 결과 전송
        final_result = {
            "type": "result",
            "data": {
                "reply": generated_reply,
                "context_id": req.context_id,
                "similar_tickets": similar_tickets[:3] if similar_tickets else [],
                "related_docs": related_docs[:3] if related_docs else [],
                "metadata": {
                    "duration_ms": int(total_time * 1000),
                    "model_used": response.model_used,
                    "style": req.style,
                    "tone": req.tone,
                    "generated_at": datetime.now().isoformat()
                }
            }
        }
        
        yield final_result
        
    except Exception as e:
        logger.error(f"스트리밍 응답 생성 중 오류 발생: {e}")
        yield {
            "type": "error",
            "message": f"응답 생성 중 오류가 발생했습니다: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }


# SSE 스트리밍 엔드포인트들

@app.post("/query/stream")
async def query_stream_endpoint(req: QueryRequest, company_id: str = Depends(get_company_id)):
    """
    SSE 스트리밍을 통한 실시간 쿼리 처리 엔드포인트
    
    프론트엔드에서 실시간으로 쿼리 처리 진행 상황을 받을 수 있습니다.
    각 단계별 진행률과 최종 결과를 스트리밍으로 전송합니다.
    
    Args:
        req: 쿼리 요청 객체
        company_id: 회사 ID (헤더에서 자동 추출)
        
    Returns:
        StreamingResponse: SSE 형식의 스트리밍 응답
    """
    logger.info(f"SSE 스트리밍 쿼리 시작: {req.query[:50]}...")
    
    return StreamingResponse(
        sse_generator(streaming_query_generator(req, company_id)),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
        }
    )


@app.post("/generate_reply/stream")
async def generate_reply_stream_endpoint(
    req: GenerateReplyRequest,
    company_id: str = Depends(get_company_id)
):
    """
    SSE 스트리밍을 통한 실시간 응답 생성 엔드포인트
    
    티켓에 대한 AI 응답을 실시간으로 생성하고 진행 상황을 스트리밍으로 전송합니다.
    
    Args:
        req: 응답 생성 요청 객체
        company_id: 회사 ID (헤더에서 자동 추출)
        
    Returns:
        StreamingResponse: SSE 형식의 스트리밍 응답
    """
    logger.info(f"SSE 스트리밍 응답 생성 시작: context_id={req.context_id}")
    
    return StreamingResponse(
        sse_generator(streaming_reply_generator(req, company_id)),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
        }
    )
