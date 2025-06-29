"""
티켓 초기화 라우트 - 순차 실행 패턴

티켓 ID를 받아 초기 컨텍스트를 생성하는 엔드포인트를 처리합니다.
순차적으로 티켓 요약 생성과 벡터 검색(유사 티켓 + KB 문서)을 수행합니다.
"""

import json
import time
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from core.llm.manager import get_llm_manager
from core.database.vectordb import vector_db
from ..dependencies import (
    get_tenant_id,
    get_platform, 
    get_domain,
    get_api_key
)

# 로거 설정
logger = logging.getLogger(__name__)

router = APIRouter()

# 응답 모델
class InitResponse(BaseModel):
    """Init 엔드포인트 응답 모델"""
    success: bool
    ticket_id: str
    tenant_id: str
    summary: Optional[str] = None
    similar_tickets: Optional[List[Dict[str, Any]]] = None
    kb_documents: Optional[List[Dict[str, Any]]] = None
    performance: Optional[Dict[str, float]] = None
    error: Optional[str] = None


@router.get("/init/{ticket_id}", response_model=InitResponse)
async def get_initial_context(
    ticket_id: str,
    tenant_id: str = Depends(get_tenant_id),
    platform: str = Depends(get_platform),
    api_key: str = Depends(get_api_key),
    domain: str = Depends(get_domain),
    include_summary: bool = True,
    include_kb_docs: bool = True,
    include_similar_tickets: bool = True,
    top_k_tickets: int = Query(default=3, ge=1, le=10, description="유사 티켓 검색 결과 수"),
    top_k_kb: int = Query(default=3, ge=1, le=10, description="지식베이스 문서 검색 결과 수"),
):
    """
    티켓 초기화 및 컨텍스트 생성 - 순차 실행 패턴
    
    주어진 티켓 ID에 대해 순차적으로 분석을 수행하고 컨텍스트를 생성합니다:
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
        include_summary: 티켓 요약 생성 여부
        include_kb_docs: 지식베이스 문서 포함 여부
        include_similar_tickets: 유사 티켓 포함 여부
        top_k_tickets: 유사 티켓 검색 결과 수
        top_k_kb: 지식베이스 문서 검색 결과 수
        
    Returns:
        InitResponse: 초기화된 컨텍스트 정보
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
        structured_ticket_data = {
            "id": ticket_id,
            "subject": ticket_metadata.get("subject", f"티켓 ID {ticket_id}"),
            "description_text": ticket_metadata.get("text", ticket_metadata.get("description_text", "티켓 본문 정보 없음")),
            "conversations": ticket_data.get("conversations", []) if isinstance(ticket_data, dict) else [],
            "tenant_id": tenant_id,
            "platform": platform,
            "metadata": ticket_metadata
        }
        
        # 순차 실행으로 초기화 처리
        result = await llm_manager.execute_init_sequential(
            ticket_data=structured_ticket_data,
            qdrant_client=qdrant_client,
            tenant_id=tenant_id,
            top_k_tickets=top_k_tickets if include_similar_tickets else 0,
            top_k_kb=top_k_kb if include_kb_docs else 0,
            include_summary=include_summary
        )
        
        sequential_execution_time = time.time() - sequential_start_time
        logger.info(f"순차 실행 완료 - ticket_id: {ticket_id}, 총 실행시간: {sequential_execution_time:.2f}초")
        
        # 결과 구조 디버깅
        logger.debug(f"LLM Manager 실행 결과 구조: {result}")
        
        # summary 결과 상세 디버깅
        if result.get("summary"):
            logger.debug(f"Summary 결과 타입: {type(result['summary'])}")
            logger.debug(f"Summary 결과 내용: {result['summary']}")
            # JSON 직렬화 가능한지 확인
            try:
                import json
                logger.debug(f"Summary JSON: {json.dumps(result['summary'], ensure_ascii=False, indent=2)}")
            except Exception as e:
                logger.debug(f"Summary JSON 직렬화 실패: {e}")
        
        # 응답 구성
        response_data = {
            "success": result.get("success", True),
            "ticket_id": ticket_id,
            "tenant_id": tenant_id,
            "performance": {
                "total_time": sequential_execution_time,
                "summary_time": result.get("summary_time", 0),
                "search_time": result.get("search_time", 0)
            }
        }
        
        # 요약 결과 추가 - 실제 구조에 맞게 강화된 처리
        if include_summary and result.get("summary"):
            summary_result = result["summary"]
            summary_text = None
            
            # 다양한 형태의 summary 결과 처리
            if isinstance(summary_result, dict):
                # 패턴 1: task_type 기반 처리 (실제 로그에서 확인된 구조)
                if summary_result.get("task_type") == "summary":
                    if summary_result.get("success"):
                        # 성공한 요약 작업에서 실제 요약 텍스트 추출
                        if "result" in summary_result:
                            summary_text = summary_result["result"]
                        elif "summary" in summary_result:
                            summary_text = summary_result["summary"]
                        elif "content" in summary_result:
                            summary_text = summary_result["content"]
                        else:
                            # task_type이 summary이고 success가 True인 경우, 전체를 요약으로 처리
                            summary_text = f"요약 생성 완료 (실행시간: {summary_result.get('execution_time', 'N/A')}초)"
                    else:
                        summary_text = f"요약 생성 실패: {summary_result.get('error', '알 수 없는 오류')}"
                
                # 패턴 2: 기존 성공/실패 구조
                elif summary_result.get("success") and summary_result.get("summary"):
                    summary_text = summary_result["summary"]
                    
                # 패턴 3: 직접 텍스트 필드들
                elif summary_result.get("content"):
                    summary_text = summary_result["content"]
                elif summary_result.get("result"):
                    summary_text = summary_result["result"]
                elif summary_result.get("text"):
                    summary_text = summary_result["text"]
                elif summary_result.get("response"):
                    summary_text = summary_result["response"]
                
                # 마지막 수단: 딕셔너리 전체를 문자열로 변환
                if not summary_text:
                    summary_text = str(summary_result)
                
            elif isinstance(summary_result, str):
                summary_text = summary_result
            else:
                # 기타 타입은 문자열로 변환
                summary_text = str(summary_result)
            
            # 최종 검증 및 할당
            response_data["summary"] = summary_text if summary_text else "요약 생성에 실패했습니다."
            logger.debug(f"최종 summary 텍스트: {response_data['summary'][:100]}..." if len(str(response_data['summary'])) > 100 else response_data['summary'])
        
        # 유사 티켓 결과 추가 - 안전한 처리
        if include_similar_tickets and result.get("similar_tickets"):
            try:
                similar_tickets = result["similar_tickets"]
                if isinstance(similar_tickets, list):
                    response_data["similar_tickets"] = similar_tickets[:top_k_tickets]
                elif isinstance(similar_tickets, dict) and similar_tickets.get("success"):
                    # unified_search 결과에서 추출
                    tickets = similar_tickets.get("similar_tickets", [])
                    response_data["similar_tickets"] = tickets[:top_k_tickets] if isinstance(tickets, list) else []
                else:
                    logger.warning(f"유사 티켓 결과가 예상 형식이 아닙니다: {type(similar_tickets)}")
                    response_data["similar_tickets"] = []
            except Exception as e:
                logger.error(f"유사 티켓 처리 중 오류: {e}")
                response_data["similar_tickets"] = []
        
        # KB 문서 결과 추가 - 안전한 처리
        if include_kb_docs and result.get("kb_documents"):
            try:
                kb_documents = result["kb_documents"]
                if isinstance(kb_documents, list):
                    response_data["kb_documents"] = kb_documents[:top_k_kb]
                elif isinstance(kb_documents, dict) and kb_documents.get("success"):
                    # unified_search 결과에서 추출
                    docs = kb_documents.get("kb_documents", [])
                    response_data["kb_documents"] = docs[:top_k_kb] if isinstance(docs, list) else []
                else:
                    logger.warning(f"KB 문서 결과가 예상 형식이 아닙니다: {type(kb_documents)}")
                    response_data["kb_documents"] = []
            except Exception as e:
                logger.error(f"KB 문서 처리 중 오류: {e}")
                response_data["kb_documents"] = []
        
        logger.info(f"Init 엔드포인트 성공 - ticket_id: {ticket_id}")
        return InitResponse(**response_data)
        
    except Exception as e:
        sequential_execution_time = time.time() - sequential_start_time
        logger.error(f"Init 엔드포인트 실패 - ticket_id: {ticket_id}, 오류: {str(e)}, 실행시간: {sequential_execution_time:.2f}초")
        
        # 오류 응답
        return InitResponse(
            success=False,
            ticket_id=ticket_id,
            tenant_id=tenant_id,
            error=str(e),
            performance={
                "total_time": sequential_execution_time
            }
        )


@router.get("/init/{ticket_id}/health")
async def init_health_check(
    ticket_id: str,
    tenant_id: str = Depends(get_tenant_id)
):
    """Init 엔드포인트 헬스체크"""
    try:
        return {
            "status": "healthy",
            "ticket_id": ticket_id,
            "tenant_id": tenant_id,
            "timestamp": datetime.utcnow().isoformat(),
            "pattern": "sequential_execution"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"헬스체크 실패: {str(e)}")
