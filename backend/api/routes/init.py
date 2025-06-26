"""
티켓 초기화 라우트

티켓 ID를 받아 초기 컨텍스트를 생성하는 엔드포인트를 처리합니다.
유사 티켓 검색, KB 문서 검색, 티켓 요약 생성을 병렬로 수행합니다.
"""

import json
import time
import os
from datetime import datetime
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import JSONResponse

from ..dependencies import (
    get_company_id, 
    get_platform,
    get_vector_db,
    get_fetcher,
    get_llm_router,
    get_ticket_context_cache,
    get_ticket_summary_cache
)
from ..models.requests import QueryRequest
from ..models.responses import InitResponse
from ..models.shared import TicketSummaryContent, SimilarTicketItem, DocumentInfo

# Langchain 기반 init_chain import
from core.llm.integrations.langchain.chains import execute_init_parallel_chain

# 언어 현지화를 위한 summarizer 모듈 import
from core.llm.summarizer import get_agent_localized_summary, determine_agent_ui_language

# 로거
import logging
logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/init/{ticket_id}", response_model=InitResponse)
async def get_initial_context(
    ticket_id: str, 
    company_id: str = Depends(get_company_id),
    platform: str = Depends(get_platform),
    vector_db = Depends(get_vector_db),
    fetcher = Depends(get_fetcher),
    llm_router = Depends(get_llm_router),
    ticket_context_cache = Depends(get_ticket_context_cache),
    ticket_summary_cache = Depends(get_ticket_summary_cache),
    include_summary: bool = True,
    include_kb_docs: bool = True,
    include_similar_tickets: bool = True,
    top_k_tickets: int = Query(default=5, ge=1, le=5, description="유사 티켓 검색 결과 수 (1-5)"),
    top_k_kb: int = Query(default=5, ge=1, le=5, description="지식베이스 문서 검색 결과 수 (1-5)"),
    agent_language: Optional[str] = Query(default=None, description="에이전트 UI 언어 (ko, en)"),
    x_freshdesk_domain: Optional[str] = Header(None, alias="X-Freshdesk-Domain"),
    x_freshdesk_api_key: Optional[str] = Header(None, alias="X-Freshdesk-API-Key")
):
    """
    티켓 초기화 및 컨텍스트 생성
    
    주어진 티켓 ID에 대해 초기 분석을 수행하고 컨텍스트를 생성합니다.
    다음 작업들이 병렬로 실행됩니다:
    1. 티켓 요약 생성 (LLM 기반)
    2. 유사 티켓 검색 (벡터 유사도)
    3. 관련 지식베이스 문서 검색
    
    Args:
        ticket_id: 분석할 티켓 ID
        company_id: 회사 ID (헤더에서 추출)
        platform: 플랫폼 타입 (헤더에서 추출)
        include_summary: 티켓 요약 생성 여부
        include_kb_docs: 지식베이스 문서 포함 여부
        include_similar_tickets: 유사 티켓 포함 여부
        top_k_tickets: 유사 티켓 검색 결과 수
        top_k_kb: 지식베이스 문서 검색 결과 수
        agent_language: 에이전트 UI 언어 (ko, en) - 유사 티켓 요약 현지화에 사용
        
    Returns:
        InitResponse: 초기화된 컨텍스트 정보
    """
    try:
        # 환경변수 백업 (동적 설정을 위해)
        original_domain = os.getenv("FRESHDESK_DOMAIN")
        original_api_key = os.getenv("FRESHDESK_API_KEY")
        
        logger.info(f"티켓 ID {ticket_id} 초기화 시작 (company_id: {company_id}, platform: {platform})")
        
        # Freshdesk 전용 처리 (platform은 항상 "freshdesk")
        search_company_id = company_id
        
        # Freshdesk API 설정 (헤더 기반)
        domain = x_freshdesk_domain or os.getenv("FRESHDESK_DOMAIN")
        api_key = x_freshdesk_api_key or os.getenv("FRESHDESK_API_KEY")
        
        if not domain or not api_key:
                raise HTTPException(
                    status_code=400,
                    detail="Freshdesk 도메인과 API 키가 필요합니다. 헤더 또는 환경변수로 제공해주세요."
                )
        
            # Freshdesk API에서 티켓 정보 조회 (동적 설정 사용)
            ticket_data = await fetcher.fetch_ticket_details(int(ticket_id), domain=domain, api_key=api_key)
        else:
            # 다른 플랫폼의 경우 벡터 검색만 사용
            ticket_data = None
        
        if not ticket_data:
            # API 조회 실패 시 또는 다른 플랫폼인 경우 벡터 검색 폴백
            ticket_data = vector_db.get_by_id(
                original_id_value=ticket_id, 
                company_id=search_company_id, 
                doc_type="ticket",
                platform=platform
            )
            
            if not ticket_data:
                raise HTTPException(
                    status_code=404, 
                    detail=f"플랫폼 {platform}에서 티켓 ID {ticket_id}를 찾을 수 없습니다."
                )
            
        # 메타데이터 추출
        ticket_metadata = ticket_data.get("metadata", {}) if isinstance(ticket_data, dict) else ticket_data
        ticket_title = ticket_metadata.get("subject", f"티켓 ID {ticket_id}")
        ticket_body = ticket_metadata.get("text", ticket_metadata.get("description_text", "티켓 본문 정보 없음"))
        
        # 대화 내용 처리 - 원본 대화 내역 추출
        raw_conversations = ticket_data.get("conversations", []) if isinstance(ticket_data, dict) else []
        
        ticket_conversations = []
        
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
        
        # 대화 내역이 없는 경우 대화 요약 사용
        if not ticket_conversations and ticket_metadata.get("conversation_summary"):
            ticket_conversations = [{"body_text": str(ticket_metadata.get("conversation_summary")), 
                                    "created_at": datetime.now().timestamp()}]
        
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
        
        # 캐시 확인
        cached_summary = None
        include_summary_chain = include_summary
        if include_summary and ticket_id in ticket_summary_cache:
            cached_summary = ticket_summary_cache[ticket_id]
            include_summary_chain = False

        # 컨텍스트 구축 시작 시간
        context_start_time = time.time()
        
        # Phase 1: Langchain RunnableParallel로 병렬 작업 관리
        # 개별 태스크 정의 대신 Langchain 체인이 모든 작업을 처리
        # 기존 asyncio.gather 방식과 동일한 성능을 유지하면서 더 나은 아키텍처 제공
        
        # 작업별 데이터 초기화
        similar_tickets = []
        kb_documents = []
        ticket_summary = None
        task_times = {}  # 각 작업별 소요 시간 저장
        
        # Phase 1: Langchain RunnableParallel로 병렬 작업 실행
        # 기존 asyncio.gather 방식에서 Langchain의 RunnableParallel로 전환
        try:
            logger.info(f"Langchain RunnableParallel을 사용한 병렬 처리 시작 (ticket_id: {ticket_id})")
            parallel_start_time = time.time()
            
            # 티켓 정보 구성
            ticket_info = {
                "id": ticket_id,
                "subject": ticket_title,
                "description": ticket_body,
                "conversations": ticket_conversations or [],
                "metadata": ticket_metadata
            }
            
            # Langchain 기반 InitChain 실행 (기존 함수 시그니처에 맞춤)
            chain_results = await execute_init_parallel_chain(
                ticket_data=ticket_info,
                qdrant_client=vector_db.client,  # QdrantAdapter의 client 속성 사용
                company_id=search_company_id,
                llm_router=llm_router,  # LLM Router 전달
                include_summary=include_summary_chain,
                include_similar_tickets=include_similar_tickets,
                include_kb_docs=include_kb_docs,
                top_k_tickets=top_k_tickets,  # 사용자 설정 유사 티켓 수
                top_k_kb=top_k_kb,  # 사용자 설정 KB 문서 수
            )
            
            parallel_execution_time = time.time() - parallel_start_time
            logger.info(f"Langchain RunnableParallel 실행 완료 (ticket_id: {ticket_id}, 총 실행시간: {parallel_execution_time:.2f}초)")
            
            # 체인 결과를 기존 형식으로 변환
            results = []
            task_names_ordered = []
            
            # chain_results 안전성 검증 강화
            if chain_results is None:
                logger.error("chain_results가 None입니다. 기본값으로 응답 생성합니다.")
                chain_results = {}
            elif not isinstance(chain_results, dict):
                logger.error(f"chain_results가 예상 형식이 아닙니다 (타입: {type(chain_results)}). 기본값으로 응답 생성합니다.")
                chain_results = {}
            
            # 요약 결과 처리 (안전성 향상)
            if cached_summary is not None:
                ticket_summary = cached_summary
            elif include_summary and 'summary' in chain_results:
                summary_result = chain_results.get('summary', {})
                if summary_result is not None and summary_result.get('success', False):
                    summary_data = summary_result.get('result', {})
                    if summary_data:  # summary_data가 None이 아닌지 확인
                        summary = TicketSummaryContent(
                            ticket_summary=summary_data.get('summary', '요약 생성에 실패했습니다.'),
                            key_points=summary_data.get('key_points', []),
                            sentiment=summary_data.get('sentiment', '중립적'),
                            priority_recommendation=summary_data.get('priority_recommendation', '보통'),
                            urgency_level=summary_data.get('urgency_level', '보통')
                        )
                        ticket_summary_cache[ticket_id] = summary
                        ticket_summary = summary
                    else:
                        logger.warning("summary_data가 비어있습니다. 기본 요약을 생성합니다.")
                        summary = TicketSummaryContent(
                            ticket_summary=f"티켓 제목: {ticket_title or '제목 없음'}",
                            key_points=["요약 데이터 없음", "수동 검토 필요"],
                            sentiment="중립적",
                            priority_recommendation="보통",
                            urgency_level="보통"
                        )
                        ticket_summary = summary
                else:
                    error_msg = summary_result.get('error', '알 수 없는 오류') if summary_result is not None else 'summary_result is None'
                    logger.warning(f"요약 생성 실패: {error_msg}")
                    summary = TicketSummaryContent(
                        ticket_summary=f"오류로 인해 요약 생성에 실패했습니다. 티켓 제목: {ticket_title or '제목 없음'}",
                        key_points=["요약 생성 오류", "수동 검토 필요"],
                        sentiment="중립적",
                        priority_recommendation="보통",
                        urgency_level="보통"
                    )
                    ticket_summary = summary

                results.append((summary, summary_result.get('execution_time', 0) if summary_result is not None else 0))
                task_names_ordered.append('summary')
                task_times['summary'] = summary_result.get('execution_time', 0) if summary_result is not None else 0
            
            # 통합 검색 결과 처리 (안전성 대폭 향상)
            if 'unified_search' in chain_results:
                unified_result = chain_results.get('unified_search')
                
                # unified_result 안전성 검증 강화
                if unified_result is None:
                    logger.warning("unified_result가 None입니다. 빈 검색 결과로 처리합니다.")
                    unified_result = {"success": False, "similar_tickets": [], "kb_documents": [], "execution_time": 0}
                elif not isinstance(unified_result, dict):
                    logger.warning(f"unified_result가 딕셔너리가 아닙니다 (타입: {type(unified_result)}). 빈 검색 결과로 처리합니다.")
                    unified_result = {"success": False, "similar_tickets": [], "kb_documents": [], "execution_time": 0}
                
                if unified_result.get('success', False):
                    # 유사 티켓 결과 추출 (안전성 향상)
                    if include_similar_tickets:
                        similar_tickets_data = unified_result.get('similar_tickets', [])
                        similar_tickets = similar_tickets_data if isinstance(similar_tickets_data, list) else []
                        
                        # 🌍 에이전트 언어 기반 유사 티켓 요약 현지화
                        if similar_tickets and agent_language:
                            try:
                                localized_tickets = []
                                agent_profile = {"language": agent_language}
                                
                                for ticket in similar_tickets:
                                    # SimilarTicketItem 객체인 경우 처리
                                    if hasattr(ticket, 'issue') and ticket.issue:
                                        localized_issue = await get_agent_localized_summary(
                                            ticket_id=str(ticket.id),
                                            original_summary=ticket.issue,
                                            agent_profile=agent_profile
                                        )
                                        ticket.issue = localized_issue
                                    
                                    if hasattr(ticket, 'solution') and ticket.solution:
                                        localized_solution = await get_agent_localized_summary(
                                            ticket_id=str(ticket.id),
                                            original_summary=ticket.solution,
                                            agent_profile=agent_profile
                                        )
                                        ticket.solution = localized_solution
                                    
                                    if hasattr(ticket, 'ticket_summary') and ticket.ticket_summary:
                                        localized_summary = await get_agent_localized_summary(
                                            ticket_id=str(ticket.id),
                                            original_summary=ticket.ticket_summary,
                                            agent_profile=agent_profile
                                        )
                                        ticket.ticket_summary = localized_summary
                                    
                                    localized_tickets.append(ticket)
                                
                                similar_tickets = localized_tickets
                                logger.debug(f"유사 티켓 {len(similar_tickets)}개 현지화 완료 (언어: {agent_language})")
                                
                            except Exception as e:
                                logger.warning(f"유사 티켓 현지화 중 오류 (계속 진행): {e}")
                                # 오류 발생 시 원본 유지
                        
                        task_times['similar_tickets'] = unified_result.get('execution_time', 0)
                        task_names_ordered.append('similar_tickets')
                    
                    # KB 문서 결과 추출 (안전성 향상)
                    if include_kb_docs:
                        kb_documents_data = unified_result.get('kb_documents', [])
                        kb_documents = kb_documents_data if isinstance(kb_documents_data, list) else []
                        task_times['kb_documents'] = unified_result.get('execution_time', 0)
                        task_names_ordered.append('kb_documents')
                    
                    # 통합 검색 성능 정보 로깅
                    cache_used = unified_result.get('cache_used', False)
                    performance_metrics = unified_result.get('search_performance', {})
                    logger.info(f"통합 검색 완료 - 캐시 사용: {cache_used}, 성능: {performance_metrics}")
                    
                else:
                    # 통합 검색 실패 시 빈 결과로 폴백
                    error_msg = unified_result.get('error', 'Unknown error')
                    logger.warning(f"통합 검색 실패: {error_msg}")
                    if include_similar_tickets:
                        similar_tickets = []
                        task_times['similar_tickets'] = unified_result.get('execution_time', 0)
                        task_names_ordered.append('similar_tickets')
                    if include_kb_docs:
                        kb_documents = []
                        task_times['kb_documents'] = unified_result.get('execution_time', 0)
                        task_names_ordered.append('kb_documents')
            
            else:
                # 레거시 방식으로 개별 결과 처리 (통합 검색이 비활성화된 경우)
                # 유사 티켓 결과 처리  
                if include_similar_tickets and 'similar_tickets' in chain_results:
                    similar_result = chain_results['similar_tickets']
                    if similar_result.get('success', False):
                        similar_tickets = similar_result.get('result', [])
                    else:
                        similar_tickets = []
                        logger.warning(f"유사 티켓 검색 실패: {similar_result.get('error', 'Unknown error')}")
                    
                    results.append((similar_tickets, similar_result.get('execution_time', 0)))
                    task_names_ordered.append('similar_tickets')
                    task_times['similar_tickets'] = similar_result.get('execution_time', 0)
                
                # 지식베이스 문서 결과 처리
                if include_kb_docs and 'kb_documents' in chain_results:
                    kb_result = chain_results['kb_documents']
                    if kb_result.get('success', False):
                        kb_documents = kb_result.get('result', [])
                    else:
                        kb_documents = []
                        logger.warning(f"지식베이스 문서 검색 실패: {kb_result.get('error', 'Unknown error')}")
                    
                    results.append((kb_documents, kb_result.get('execution_time', 0)))
                    task_names_ordered.append('kb_documents')
                    task_times['kb_documents'] = kb_result.get('execution_time', 0)
            
            # task_names를 정렬된 순서로 업데이트
            task_names = task_names_ordered
            
        except Exception as e:
            logger.error(f"Langchain RunnableParallel 실행 중 예상치 못한 오류 발생: {str(e)}")
            # 폴백으로 기존 asyncio.gather 방식 사용 (현재는 비활성화)
            logger.warning("Langchain 체인 실행 실패, 기본값으로 응답 생성")
            
            # 기본값 설정
            if include_summary and not ticket_summary:
                ticket_summary = TicketSummaryContent(
                    ticket_summary=f"티켓 제목: {ticket_title or '제목 없음'}",
                    key_points=["Langchain 처리 오류로 인한 기본 요약"],
                    sentiment="중립적",
                    priority_recommendation="보통",
                    urgency_level="보통"
                )
            
            if include_similar_tickets and not similar_tickets:
                similar_tickets = []
                
            if include_kb_docs and not kb_documents:
                kb_documents = []
            
            task_names = []
            if include_summary:
                task_names.append('summary')
            if include_similar_tickets:
                task_names.append('similar_tickets')
            if include_kb_docs:
                task_names.append('kb_documents')
        
        # 전체 요청 처리 총 소요 시간 계산
        total_time = time.time() - context_start_time
        
        # 성능 향상 효과 계산 및 로깅
        if task_times:
            total_individual_time = sum(task_times.values())
            if total_individual_time > 0:
                improvement_ratio = total_individual_time / total_time
                time_saved = total_individual_time - total_time
                logger.info(f"🚀 병렬 처리 효과 - 총 시간: {total_time:.3f}초 ({improvement_ratio:.1f}배 빠름, {time_saved:.3f}초 단축)")
            else:
                logger.info(f"⏱️ 총 소요 시간: {total_time:.3f}초")
        
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
        
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"전체 초기화 프로세스 중 오류 발생: {str(e)}")
        raise HTTPException(status_code=500, detail=f"초기화 중 오류가 발생했습니다: {str(e)}")
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
