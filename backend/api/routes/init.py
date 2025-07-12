"""
티켓 초기화 라우트 - 순차 실행 패턴

티켓 ID를 받아 초기 컨텍스트를 생성하는 엔드포인트를 처리합니다.
순차적으로 티켓 요약 생성과 벡터 검색(유사 티켓 + KB 문서)을 수행합니다.
"""

import json
import time
import logging
import os
from datetime import datetime
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from core.llm.manager import get_llm_manager
from core.database.vectordb import vector_db
from core.utils.smart_conversation_filter import SmartConversationFilter
from ..dependencies import (
    get_tenant_id,
    get_platform,
    get_domain,
    get_api_key
)
from ..rate_limit import heavy_limiter

# 로거 설정
logger = logging.getLogger(__name__)

router = APIRouter()

# 응답 모델
class InitResponse(BaseModel):
    """Init 엔드포인트 응답 모델 - 최적화된 구조"""
    success: bool
    ticket_id: str
    tenant_id: str
    platform: str
    
    # 핵심 결과
    summary: Optional[str] = None  # 단순화: 문자열로 직접 반환
    similar_tickets: Optional[List[Dict[str, Any]]] = None
    kb_documents: Optional[List[Dict[str, Any]]] = None
    
    # 성능 메트릭 (단순화)
    execution_time: Optional[float] = None
    search_quality_score: Optional[float] = None
    
    # 오류 정보 (필요시에만)
    error: Optional[str] = None


@router.get("/init/{ticket_id}")
async def get_initial_context(
    ticket_id: str,
    tenant_id: str = Depends(get_tenant_id),
    platform: str = Depends(get_platform),
    api_key: str = Depends(get_api_key),
    domain: str = Depends(get_domain),
    stream: bool = Query(default=True, description="스트리밍 응답 여부"),
    include_summary: bool = True,
    include_kb_docs: bool = True,
    include_similar_tickets: bool = True,
    top_k_tickets: int = Query(default=3, ge=1, le=10, description="유사 티켓 검색 결과 수"),
    top_k_kb: int = Query(default=3, ge=1, le=10, description="지식베이스 문서 검색 결과 수"),
    retry_reason: Optional[str] = Query(None, description="재시도 이유"),
    ui_language: str = Query(default="ko", description="UI 언어 (ko, en, ja, zh)"),
):
    """
    티켓 초기화 및 컨텍스트 생성 (통합 엔드포인트)
    
    스트리밍/비스트리밍을 stream 파라미터로 제어합니다 (기본값: true)
    
    ⚠️ 환경변수 ENABLE_FULL_STREAMING_MODE에 따라 다른 로직을 사용합니다:
    - true (기본값): Vector DB 단독 + 풀 스트리밍 모드 (신규)
    - false: 기존 하이브리드 모드 (100% 보존)
    
    주어진 티켓 ID에 대해 분석을 수행하고 컨텍스트를 생성합니다:
    1. 실시간 요약 생성 (Freshdesk API)
    2. 유사 티켓 검색 (벡터 유사도)
    3. 관련 지식베이스 문서 검색
    
    표준 헤더 (필수):
    - X-Tenant-ID: 테넌트 ID
    - X-Platform: 플랫폼 식별자 (freshdesk)
    - X-API-Key: API 키
    - X-Domain: 플랫폼 도메인 (예: wedosoft.freshdesk.com)
    
    Args:
        ticket_id: 분석할 티켓 ID
        tenant_id: 테넌트 ID (X-Tenant-ID 헤더에서 추출)
        platform: 플랫폼 타입 (X-Platform 헤더에서 추출)
        api_key: API 키 (X-API-Key 헤더에서 추출)
        domain: 플랫폼 도메인 (X-Domain 헤더에서 추출)
        stream: 스트리밍 응답 여부 (기본값: true)
        include_summary: 티켓 요약 생성 여부
        include_kb_docs: 지식베이스 문서 포함 여부
        include_similar_tickets: 유사 티켓 포함 여부
        top_k_tickets: 유사 티켓 검색 결과 수
        top_k_kb: 지식베이스 문서 검색 결과 수
        retry_reason: 재시도 이유 (스트리밍 모드에서 사용)
        
    Returns:
        StreamingResponse (stream=true) 또는 InitResponse (stream=false)
    """
    import os
    
    # 스트리밍 모드 처리
    if stream:
        # 스트리밍 응답
        return await init_streaming_mode(
            ticket_id=ticket_id,
            tenant_id=tenant_id,
            platform=platform,
            domain=domain,
            api_key=api_key,
            include_similar=include_similar_tickets,
            include_kb=include_kb_docs,
            retry_reason=retry_reason,
            ui_language=ui_language
        )
    else:
        # 일반 JSON 응답
        logger.info(f"🚀 초기화 시작: {ticket_id}")
        return await init_endpoint(
            ticket_id=ticket_id,
            tenant_id=tenant_id,
            platform=platform,
            api_key=api_key,
            domain=domain,
            include_summary=include_summary,
            include_kb_docs=include_kb_docs,
            include_similar_tickets=include_similar_tickets,
            top_k_tickets=top_k_tickets,
            top_k_kb=top_k_kb,
            ui_language=ui_language
        )

async def init_endpoint(
    ticket_id: str,
    tenant_id: str,
    platform: str,
    api_key: str,
    domain: str,
    include_summary: bool = True,
    include_kb_docs: bool = True,
    include_similar_tickets: bool = True,
    top_k_tickets: int = 3,
    top_k_kb: int = 3,
    ui_language: str = "ko",
) -> InitResponse:
    """
    티켓 초기화 엔드포인트 - 서비스 클래스로 리팩토링됨
    
    복잡한 로직을 TicketInitializationService로 위임합니다.
    """
    start_time = time.time()
    
    try:
        # 서비스 클래스 사용으로 리팩토링
        from core.services.init_service import ticket_init_service, InitializationRequest
        
        logger.info(f"티켓 {ticket_id} 초기화 시작 - 서비스 레이어 사용")
        
        # 요청 객체 생성
        request = InitializationRequest(
            ticket_id=ticket_id,
            tenant_id=tenant_id,
            platform=platform,
            domain=domain,
            api_key=api_key,
            include_summary=include_summary,
            include_kb_docs=include_kb_docs,
            include_similar_tickets=include_similar_tickets,
            top_k_tickets=top_k_tickets,
            top_k_kb=top_k_kb,
            ui_language=ui_language
        )
        
        # 서비스 레이어에서 처리
        result = await ticket_init_service.initialize_ticket(request)
        
        # InitResponse 객체로 변환 (현재 구조에 맞게)
        summary_text = None
        if result.ticket_summary:
            summary_text = result.ticket_summary.summary if hasattr(result.ticket_summary, 'summary') else str(result.ticket_summary)
        
        # 유사 티켓을 Dict 형태로 변환
        similar_tickets_dict = []
        if result.similar_tickets:
            for ticket in result.similar_tickets:
                if hasattr(ticket, '__dict__'):
                    similar_tickets_dict.append(ticket.__dict__)
                else:
                    similar_tickets_dict.append(ticket)
        
        # KB 문서를 Dict 형태로 변환  
        kb_docs_dict = []
        if result.kb_documents:
            for doc in result.kb_documents:
                if hasattr(doc, '__dict__'):
                    kb_docs_dict.append(doc.__dict__)
                else:
                    kb_docs_dict.append(doc)
        
        processing_time = time.time() - start_time
        
        response = InitResponse(
            success=True,
            ticket_id=ticket_id,
            tenant_id=tenant_id,
            platform=platform,
            summary=summary_text,
            similar_tickets=similar_tickets_dict,
            kb_documents=kb_docs_dict,
            execution_time=processing_time,
            search_quality_score=0.8  # 기본값
        )
        
        logger.info(f"티켓 초기화 완료 - ID: {ticket_id}, 소요시간: {processing_time:.2f}초")
        
        return response
        
    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(f"티켓 초기화 실패 - ID: {ticket_id}, 오류: {e}, 소요시간: {processing_time:.2f}초")
        
        # 오류 응답 생성
        return InitResponse(
            success=False,
            ticket_id=ticket_id,
            tenant_id=tenant_id,
            platform=platform,
            summary=None,
            similar_tickets=[],
            kb_documents=[],
            execution_time=processing_time,
            error=str(e)
        )
async def init_legacy_hybrid_mode(
    ticket_id: str,
    tenant_id: str,
    platform: str,
    api_key: str,
    domain: str,
    include_summary: bool = True,
    include_kb_docs: bool = True,
    include_similar_tickets: bool = True,
    top_k_tickets: int = 3,
    top_k_kb: int = 3,
) -> InitResponse:
    """
    🔒 기존 하이브리드 초기화 모드 (100% 보존)
    
    기존 SQL + Vector DB 하이브리드 로직을 그대로 사용합니다.
    이 함수는 절대 수정하지 않습니다.
    """
    sequential_start_time = time.time()
    
    try:
        logger.info(f"순차 실행 시작 - ticket_id: {ticket_id}, tenant_id: {tenant_id}")
        
        # LLM Manager 및 Qdrant 클라이언트 초기화
        llm_manager = get_llm_manager()
        qdrant_client = vector_db.client
        
        # 실제 Freshdesk API에서 티켓 데이터 가져오기
        ticket_data = None
        try:
            from core.platforms.freshdesk.fetcher import fetch_ticket_details
            # Freshdesk API를 통해 티켓 정보 조회
            ticket_data = await fetch_ticket_details(int(ticket_id), domain=domain, api_key=api_key)
        except Exception as e:
            logger.warning(f"Freshdesk API 호출 실패: {e}")
        
        if not ticket_data:
            # API 조회 실패 시 벡터 검색 폴백 (이미 import된 vector_db 사용)
            try:
                ticket_data = vector_db.get_by_id(original_id_value=ticket_id, tenant_id=tenant_id, doc_type="ticket")
            except Exception as e:
                logger.warning(f"벡터 DB 조회 실패: {e}")
            
            if not ticket_data:
                raise HTTPException(status_code=404, detail=f"티켓 ID {ticket_id}를 찾을 수 없습니다.")
        
        # 메타데이터 추출 및 정규화
        ticket_metadata = ticket_data.get("metadata", {}) if isinstance(ticket_data, dict) else ticket_data
        
        # 티켓 정보 구성 (main 브랜치와 동일한 구조)
        # Freshdesk API 응답에서 description 필드 추출
        description_text = (
            ticket_metadata.get("text") or 
            ticket_metadata.get("description_text") or 
            ticket_metadata.get("description") or
            "티켓 본문 정보 없음"
        )
        
        structured_ticket_data = {
            "id": ticket_id,
            "subject": ticket_metadata.get("subject", f"티켓 ID {ticket_id}"),
            "description_text": description_text,
            "conversations": ticket_data.get("conversations", []) if isinstance(ticket_data, dict) else [],
            "tenant_id": tenant_id,
            "platform": platform,
            "metadata": ticket_metadata
        }
        
        # 디버깅 로그 추가
        logger.info(f"🔍 티켓 메타데이터 구조: {list(ticket_metadata.keys())}")
        logger.info(f"🔍 추출된 description_text: {description_text[:100]}...")
        
        # 벡터 단독 검색 실행
        from core.database.vectordb import search_vector_db
        
        # 티켓 내용 구성
        ticket_content_parts = []
        if structured_ticket_data.get("subject"):
            ticket_content_parts.append(f"제목: {structured_ticket_data['subject']}")
        if structured_ticket_data.get("description_text"):
            ticket_content_parts.append(f"설명: {structured_ticket_data['description_text']}")
        
        # 대화내역 추가
        if structured_ticket_data.get("conversations"):
            conversations = structured_ticket_data["conversations"]
            ticket_content_parts.append(f"대화내역 (총 {len(conversations)}개):")
            for i, conv in enumerate(conversations[:10]):  # 최대 10개만
                if conv.get("body_text"):
                    content = conv['body_text'][:300]  # 300자로 제한
                    ticket_content_parts.append(f"대화 {i+1}: {content}{'...' if len(conv['body_text']) > 300 else ''}")
        
        ticket_content = "\n".join(ticket_content_parts)
        
        # 병렬 검색 실행
        import asyncio
        
        async def generate_summary():
            if not include_summary:
                return None
            summary_result = await llm_manager.generate_ticket_summary(structured_ticket_data)
            return summary_result.get("summary", "요약 생성 실패")
        
        async def search_similar_tickets():
            if not include_similar_tickets:
                return []
            similar_results = await search_vector_db(
                query=ticket_content,
                tenant_id=tenant_id,
                platform=platform,
                doc_types=["ticket"],
                limit=top_k_tickets,
                exclude_id=ticket_id
            )
            return [
                {
                    "id": result.get("original_id") or result["metadata"].get("original_id"),
                    "subject": result.get("subject") or result["metadata"].get("subject", ""),
                    "content": result.get("content", ""),
                    "score": result["score"],
                    "metadata": result.get("metadata", {})
                }
                for result in similar_results
            ]
        
        async def search_kb_documents():
            if not include_kb_docs:
                return []
            kb_results = await search_vector_db(
                query=ticket_content,
                tenant_id=tenant_id,
                platform=platform,
                doc_types=["article"],
                limit=top_k_kb
            )
            return [
                {
                    "id": result.get("original_id") or result["metadata"].get("original_id"),
                    "title": result.get("title") or result["metadata"].get("title", ""),
                    "url": f"https://{domain}/a/solutions/articles/{result.get('original_id')}",
                    "score": result["score"],
                    "created_at": result.get("created_at", ""),
                    "updated_at": result.get("updated_at", ""),
                }
                for result in kb_results
            ]
        
        # 병렬 실행
        summary_text, similar_tickets, kb_documents = await asyncio.gather(
            generate_summary(),
            search_similar_tickets(),
            search_kb_documents()
        )
        
        # 결과 구성
        result = {
            "summary": summary_text,
            "similar_tickets": similar_tickets,
            "kb_documents": kb_documents,
            "execution_time": time.time() - sequential_start_time
        }
        
        sequential_execution_time = time.time() - sequential_start_time
        logger.info(f"하이브리드 순차 실행 완료 - ticket_id: {ticket_id}, 총 실행시간: {sequential_execution_time:.2f}초")
        
        # 하이브리드 검색 품질 메트릭 로깅
        if result.get("unified_search", {}).get("search_quality_score"):
            quality_score = result["unified_search"]["search_quality_score"]
            search_method = result["unified_search"].get("search_method", "unknown")
            logger.info(f"검색 품질: {quality_score:.3f} (방법: {search_method})")
        
        # 결과 구조 디버깅
        logger.debug(f"하이브리드 검색 실행 결과 구조: {result}")
        
        # summary 결과 상세 디버깅
        if result.get("summary"):
            logger.info(f"[SUMMARY DEBUG] 원본 결과 타입: {type(result['summary'])}")
            logger.info(f"[SUMMARY DEBUG] 원본 결과 길이: {len(str(result['summary']))}")
            
            # 구조 상세 분석
            summary_result = result['summary']
            if isinstance(summary_result, dict):
                logger.info(f"[SUMMARY DEBUG] Dict 키들: {list(summary_result.keys())}")
                
                # 각 주요 필드 확인
                for key in ['task_type', 'success', 'result', 'summary', 'content', 'error', 'execution_time']:
                    if key in summary_result:
                        value = summary_result[key]
                        logger.info(f"[SUMMARY DEBUG] {key}: {type(value)} = {str(value)[:200]}...")
                
                # task_type이 summary인 경우 전체 구조 로깅
                if summary_result.get("task_type") == "summary":
                    logger.info(f"[SUMMARY DEBUG] Task Summary 전체 구조:")
                    try:
                        import json
                        logger.info(f"[SUMMARY DEBUG] {json.dumps(summary_result, ensure_ascii=False, indent=2)}")
                    except Exception as e:
                        logger.info(f"[SUMMARY DEBUG] JSON 직렬화 실패, 원본: {summary_result}")
            else:
                logger.info(f"[SUMMARY DEBUG] 비-Dict 타입 내용: {str(summary_result)[:500]}...")
        else:
            logger.warning(f"[SUMMARY DEBUG] Summary 결과가 없습니다. 전체 결과 키들: {list(result.keys()) if isinstance(result, dict) else 'Not a dict'}")
        
        # 응답 구성 - 단순화된 처리
        try:
            # 기본 응답 데이터
            response_data = {
                "success": result.get("success", True),
                "ticket_id": ticket_id,
                "tenant_id": tenant_id,
                "platform": platform,
                "execution_time": float(sequential_execution_time),
                "search_quality_score": 0.0
            }
            
            # 검색 품질 점수 추출
            unified_search = result.get("unified_search", {})
            if isinstance(unified_search, dict):
                quality_score = unified_search.get("search_quality_score", 0.0)
                if isinstance(quality_score, (int, float)):
                    response_data["search_quality_score"] = float(quality_score)
            
        except Exception as e:
            logger.error(f"응답 데이터 구성 중 오류: {e}")
            response_data = {
                "success": False,
                "ticket_id": ticket_id,
                "tenant_id": tenant_id,
                "platform": platform,
                "execution_time": float(sequential_execution_time),
                "search_quality_score": 0.0,
                "error": f"응답 구성 오류: {str(e)}"
            }
        
        # 요약 결과 처리 - 단순화
        if include_summary and result.get("summary"):
            summary_result = result["summary"]
            summary_text = None
            
            # 간단한 요약 추출 로직
            if isinstance(summary_result, dict):
                # 순서대로 필드 확인
                for field in ["summary", "result", "content", "text", "response"]:
                    if field in summary_result and summary_result[field]:
                        # 딕셔너리인 경우 내부 요약 텍스트 추출
                        if isinstance(summary_result[field], dict):
                            nested_summary = summary_result[field]
                            for nested_field in ["ticket_summary", "summary", "content", "text"]:
                                if nested_field in nested_summary:
                                    summary_text = nested_summary[nested_field]
                                    break
                        else:
                            summary_text = str(summary_result[field])
                        break
                        
                # 마지막 수단
                if not summary_text and summary_result.get("success"):
                    summary_text = "요약이 성공적으로 생성되었습니다."
                    
            elif isinstance(summary_result, str):
                summary_text = summary_result
            
            # 최종 할당
            response_data["summary"] = summary_text if summary_text else "요약 생성에 실패했습니다."
        else:
            logger.info(f"[SUMMARY PROCESSING] Summary 생성 비활성화됨")
        
        # 검색 결과 처리 - 단순화
        if include_similar_tickets:
            similar_tickets = result.get("similar_tickets", [])
            if isinstance(similar_tickets, list):
                response_data["similar_tickets"] = similar_tickets[:top_k_tickets] if similar_tickets else []
            else:
                response_data["similar_tickets"] = []
        
        if include_kb_docs:
            kb_documents = result.get("kb_documents", [])
            if isinstance(kb_documents, list):
                response_data["kb_documents"] = kb_documents[:top_k_kb] if kb_documents else []
            else:
                response_data["kb_documents"] = []
        
        return InitResponse(**response_data)
        
    except Exception as e:
        sequential_execution_time = time.time() - sequential_start_time
        logger.error(f"Init 엔드포인트 실패 - ticket_id: {ticket_id}, 오류: {str(e)}, 실행시간: {sequential_execution_time:.2f}초")
        
        # 오류 응답 - 단순화
        return InitResponse(
            success=False,
            ticket_id=ticket_id,
            tenant_id=tenant_id,
            platform=platform,
            error=str(e),
            execution_time=sequential_execution_time
        )






async def init_streaming_mode(
    ticket_id: str,
    tenant_id: str,
    platform: str,
    domain: str,
    api_key: str,
    include_similar: bool,
    include_kb: bool,
    retry_reason: Optional[str],
    ui_language: str = "ko"
) -> StreamingResponse:
    """
    스트리밍 모드 초기화 함수
    - Vector DB에서 데이터 검색
    - 실시간 요약 생성 (단계별 스트리밍)
    """
    
    async def generate_stream():
        try:
            start_time = time.time()
            logger.info(f"스트리밍 초기화 시작 - ticket_id: {ticket_id}, tenant_id: {tenant_id}")
            
            # 스트리밍 초기화 실행
            from core.database.vectordb import search_vector_db
            from core.llm.manager import get_llm_manager
            
            # 진행률 업데이트 함수 (예상시간 계산 포함)
            def send_progress(stage: str, progress: float, message: str = "", start_time_ref: float = None):
                result = {
                    "type": "progress",
                    "stage": stage,
                    "progress": progress,
                    "message": message
                }
                
                # 예상시간 계산 (시작 시간이 제공된 경우)
                if start_time_ref and progress > 0:
                    elapsed_time = time.time() - start_time_ref
                    if progress < 100:
                        # 남은 진행률을 기반으로 예상시간 계산
                        estimated_total_time = (elapsed_time / progress) * 100
                        remaining_time = max(0, estimated_total_time - elapsed_time)
                        result["remaining_time"] = int(remaining_time)
                    else:
                        result["remaining_time"] = 0
                
                return result
            
            # 시작
            yield f"data: {json.dumps(send_progress('init', 0, '초기화 시작'))}\n\n"
            
            # 1. 실시간 Freshdesk API로 현재 티켓 정보 조회
            yield f"data: {json.dumps(send_progress('ticket_fetch', 10, '현재 티켓 정보 조회 중', start_time))}\n\n"
            
            from core.platforms.freshdesk.fetcher import fetch_ticket_details
            
            # 실시간 Freshdesk API 호출 (에러 처리 개선)
            ticket_data = None
            try:
                ticket_data = await fetch_ticket_details(
                    ticket_id=int(ticket_id),
                    domain=domain,
                    api_key=api_key
                )
            except Exception as e:
                logger.warning(f"Freshdesk API 호출 실패, 기본 티켓 데이터로 진행: {str(e)}")
                # Freshdesk API 실패 시 기본 티켓 데이터 생성
                ticket_data = {
                    "id": int(ticket_id),
                    "subject": f"티켓 #{ticket_id}",
                    "description_text": "Freshdesk 연결 오류로 인해 상세 정보를 가져올 수 없습니다.",
                    "status": "open",
                    "priority": "medium",
                    "conversations": [],
                    "attachments": []
                }
                
                # 사용자에게 상황 알림
                yield f"data: {json.dumps(send_progress('ticket_fetch', 25, 'Freshdesk 연결 오류 - 기본 데이터로 진행'))}\n\n"
            
            if not ticket_data:
                error_chunk = {"type": "error", "message": f"티켓 ID {ticket_id} 데이터를 처리할 수 없습니다."}
                yield f"data: {json.dumps(error_chunk)}\n\n"
                return
            
            # 티켓 내용 구성 (제목 + 설명 + 대화내역)
            ticket_content_parts = []
            if ticket_data.get("subject"):
                ticket_content_parts.append(f"제목: {ticket_data['subject']}")
            if ticket_data.get("description_text"):
                ticket_content_parts.append(f"설명: {ticket_data['description_text']}")
            elif ticket_data.get("description"):
                ticket_content_parts.append(f"설명: {ticket_data['description']}")
            
            # 대화내역 추가 (스트리밍에서도 스마트 필터링 사용)
            if ticket_data.get("conversations"):
                conversations = ticket_data["conversations"]
                total_conversations = len(conversations)
                ticket_content_parts.append(f"대화내역 (총 {total_conversations}개):")
                
                # 스마트 필터 사용 (스트리밍용은 경량화)
                smart_filter = SmartConversationFilter(max_conversations=15, max_chars_per_conv=500)
                selected_indices, filter_metadata = smart_filter.filter_conversations(
                    conversations,
                    ticket_metadata=ticket_data.get("metadata", {})
                )
                
                # 포맷팅된 대화 추가
                formatted_conversations = smart_filter.format_conversations(conversations, selected_indices)
                ticket_content_parts.extend(formatted_conversations)
            
            ticket_content = "\n".join(ticket_content_parts)
            
            # 2. 스트리밍 버전도 병렬 처리 적용
            import asyncio
            llm_manager = get_llm_manager()
            
            # 병렬 실행할 작업들 정의 (스트리밍 버전)
            async def streaming_summary_task():
                """스트리밍용 티켓 요약 생성 작업"""
                try:
                    logger.info("🎯 [조회 티켓 최우선] ticket_view 템플릿 사용 시작")
                    
                    summary_result_dict = await llm_manager.generate_ticket_summary(ticket_data)
                    summary_text = summary_result_dict.get("summary", "요약 생성 실패")
                    
                    # 템플릿 구조 확인
                    if summary_text and len(summary_text) > 100:
                        korean_sections = any(section in summary_text for section in ["🔍 문제 현황", "💡 원인 분석", "⚡ 해결 진행상황", "🎯 중요 인사이트"])
                        english_sections = any(section in summary_text for section in ["🔍 Problem Overview", "💡 Root Cause", "⚡ Resolution Progress", "🎯 Key Insights"])
                        has_sections = korean_sections or english_sections
                        if has_sections:
                            lang = "한국어" if korean_sections else "영어"
                            logger.info(f"✅ [조회 티켓] ticket_view 4개 섹션 구조 정상 생성 ({lang})")
                    
                    logger.info(f"✅ [조회 티켓 최우선] ticket_view 템플릿 기반 요약 생성 완료 ({len(summary_text)}문자)")
                    
                    return summary_text
                    
                except Exception as e:
                    logger.error(f"❌ [조회 티켓 최우선] ticket_view 템플릿 사용 실패: {e}")
                    # 폴백
                    subject = ticket_data.get("subject", "제목 없음")
                    description = ticket_data.get("description_text") or ticket_data.get("description", "")
                    fallback_summary = f"## 🎫 {subject}\n\n**문제 상황**: {description[:200]}...\n\n**오류**: {str(e)}"
                    logger.debug(f"폴백 요약 사용")
                    return fallback_summary

            async def streaming_search_similar_task():
                """스트리밍용 유사 티켓 검색 작업"""
                if not include_similar:
                    return []
                    
                # 스마트 벡터 검색 - 자기 자신 자동 제외 (스트리밍용)
                similar_results = await search_vector_db(
                    query=ticket_content,
                    tenant_id=tenant_id,
                    platform=platform,
                    doc_types=["ticket"],
                    limit=3,  # 스트리밍 모드에서는 3개 고정
                    exclude_id=ticket_id  # 자기 자신 제외 (벡터 DB 레벨에서 처리)
                )
                
                logger.info(f"🔍 유사 티켓 검색 결과: {len(similar_results)}개")
                
                raw_similar_tickets = []
                for result in similar_results:
                    # metadata에 기본 정보들을 포함
                    metadata = result.get("extended_metadata", result.get("metadata", {})).copy()
                    
                    # created_at과 status를 metadata에 추가 (벡터DB에서 직접 가져오기)
                    if result.get("created_at"):
                        metadata["created_at"] = result.get("created_at")
                    if result.get("status"):
                        metadata["status"] = result.get("status")
                    if result.get("priority"):
                        metadata["priority"] = result.get("priority")
                    
                    # 불필요한 source 필드 제거
                    metadata.pop("source", None)
                    
                    raw_similar_tickets.append({
                        "id": result.get("original_id") or result["metadata"].get("original_id"),
                        "subject": result.get("subject") or result["metadata"].get("subject", ""),
                        "content": result.get("content", ""),
                        "score": result["score"],
                        "has_attachments": result.get("has_attachments", False),
                        "has_inline_images": result.get("has_inline_images", False),
                        "attachment_count": result.get("attachment_count", 0),
                        "metadata": metadata
                    })
                
                return raw_similar_tickets

            async def streaming_search_kb_task():
                """스트리밍용 KB 문서 검색 작업"""
                if not include_kb:
                    return []
                    
                kb_results = await search_vector_db(
                    query=ticket_content,
                    tenant_id=tenant_id,
                    platform=platform,
                    doc_types=["article"],
                    limit=3
                )
                
                kb_documents = []
                for result in kb_results:
                    kb_documents.append({
                        "id": result.get("original_id") or result["metadata"].get("original_id"),
                        "title": result.get("title") or result["metadata"].get("title", ""),
                        "url": f"https://{domain}/a/solutions/articles/{result.get('original_id')}",
                        "score": result["score"],
                        "created_at": result.get("created_at", ""),
                        "updated_at": result.get("updated_at", ""),
                    })
                
                return kb_documents
            
            async def streaming_similar_summaries_task(raw_tickets):
                """스트리밍용 유사 티켓 요약 생성 작업"""
                if not raw_tickets:
                    logger.info("📭 유사 티켓이 없어 요약 생성 건너뜀")
                    return []
                
                logger.info(f"📝 유사 티켓 {len(raw_tickets)}개 요약 생성 시작")
                    
                # 플랫폼 설정 구성
                platform_config = {
                    "platform": platform,
                    "domain": domain,
                    "api_key": api_key,
                    "tenant_id": tenant_id
                }
                
                summaries = await llm_manager.generate_similar_ticket_summaries(raw_tickets, ui_language, platform_config)
                logger.info(f"✅ 유사 티켓 요약 생성 완료: {len(summaries)}개")
                return summaries

            # 요약 생성 시작 알림
            yield f"data: {json.dumps(send_progress('analysis', 30, 'AI 요약 생성 중...', start_time))}\n\n"
            
            # 모든 작업을 동시에 시작 (진정한 병렬 처리)
            # 1. 티켓 요약
            summary_task = asyncio.create_task(streaming_summary_task())
            
            # 2. 유사 티켓 검색 및 요약
            async def search_and_summarize_similar():
                raw_tickets = await streaming_search_similar_task()
                if raw_tickets:
                    return await streaming_similar_summaries_task(raw_tickets), raw_tickets
                return [], []
            
            similar_task = asyncio.create_task(search_and_summarize_similar())
            
            # 3. KB 문서 검색
            kb_task = asyncio.create_task(streaming_search_kb_task())
            
            # 티켓 요약 먼저 완료 대기
            summary_text = await summary_task
            
            # 요약 완료 진행률
            yield f"data: {json.dumps(send_progress('analysis_complete', 50, 'AI 요약 생성 완료', start_time))}\n\n"
            
            # 요약 결과 전송
            summary_chunk = {
                "type": "summary", 
                "content": summary_text,
                "ticket_id": ticket_id
            }
            yield f"data: {json.dumps(summary_chunk)}\n\n"
            
            # 나머지 작업들 완료 대기
            (similar_tickets, raw_similar_tickets), kb_documents = await asyncio.gather(
                similar_task,
                kb_task
            )
            
            # 유사 티켓 결과 전송
            if similar_tickets:
                yield f"data: {json.dumps(send_progress('similar_tickets', 70, f'유사 티켓 검색 완료 ({len(raw_similar_tickets)}건)', start_time))}\n\n"
                yield f"data: {json.dumps(send_progress('similar_processing', 85, '유사 티켓 요약 생성 완료', start_time))}\n\n"
                
                similar_chunk = {
                    "type": "similar_tickets",
                    "content": similar_tickets
                }
                yield f"data: {json.dumps(similar_chunk)}\n\n"
            
            # KB 문서 결과 전송
            if kb_documents:
                yield f"data: {json.dumps(send_progress('kb_documents', 95, f'지식베이스 검색 완료 ({len(kb_documents)}건)', start_time))}\n\n"
                
                kb_chunk = {
                    "type": "kb_documents",
                    "content": kb_documents
                }
                yield f"data: {json.dumps(kb_chunk)}\n\n"
            
            # 완료
            yield f"data: {json.dumps({'type': 'complete', 'progress': 100, 'message': '모든 분석 완료!'})}\n\n"
            
            # 완료 로깅
            streaming_execution_time = time.time() - start_time
            logger.info(f"스트리밍 초기화 완료 - ticket_id: {ticket_id}, 총 실행시간: {streaming_execution_time:.2f}초")
                
        except Exception as e:
            logger.error(f"스트리밍 초기화 실패: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control"
        }
    )


