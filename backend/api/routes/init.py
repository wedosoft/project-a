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

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from core.llm.manager import get_llm_manager
from core.database.vectordb import vector_db
from core.search.adapters import InitHybridAdapter
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
        enable_full_streaming = os.getenv("ENABLE_FULL_STREAMING_MODE", "true") == "true"
        
        if enable_full_streaming:
            return await init_streaming_vector_only_mode(
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
            return await init_streaming_hybrid_mode(
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
        enable_full_streaming = os.getenv("ENABLE_FULL_STREAMING_MODE", "true") == "true"
        
        if enable_full_streaming:
            # 🚀 신규: Vector DB 단독 + 풀 스트리밍 모드
            logger.info(f"🚀 Vector DB 단독 모드로 초기화 시작: {ticket_id}")
            return await init_vector_only_mode(
                ticket_id=ticket_id,
                tenant_id=tenant_id,
                platform=platform,
                api_key=api_key,
                domain=domain,
                include_summary=include_summary,
                include_kb_docs=include_kb_docs,
                include_similar_tickets=include_similar_tickets,
                top_k_tickets=top_k_tickets,
                top_k_kb=top_k_kb
            )
        else:
            # 🔒 기존: 하이브리드 모드 (100% 보존)
            logger.info(f"🔒 하이브리드 모드로 초기화 시작: {ticket_id}")
            return await init_legacy_hybrid_mode(
                ticket_id=ticket_id,
                tenant_id=tenant_id,
                platform=platform,
                api_key=api_key,
                domain=domain,
                include_summary=include_summary,
                include_kb_docs=include_kb_docs,
                include_similar_tickets=include_similar_tickets,
                top_k_tickets=top_k_tickets,
                top_k_kb=top_k_kb
            )

async def init_vector_only_mode(
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
    🚀 신규 Vector DB 단독 + 풀 스트리밍 초기화 모드
    
    Vector DB에서만 검색하고 모든 요약을 실시간으로 생성합니다.
    """
    start_time = time.time()
    
    try:
        # 1. 실시간 Freshdesk API로 현재 티켓 정보 조회
        from core.platforms.freshdesk.fetcher import fetch_ticket_details
        from core.database.vectordb import search_vector_db_only
        
        logger.info(f"티켓 {ticket_id} 실시간 조회 시작 (도메인: {domain})")
        
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
        
        if not ticket_data:
            raise HTTPException(status_code=404, detail=f"티켓 ID {ticket_id} 데이터를 처리할 수 없습니다.")
        
        logger.info(f"티켓 {ticket_id} 실시간 조회 완료 - 제목: {ticket_data.get('subject', 'N/A')}")
        
        # 티켓 내용 구성 (제목 + 설명 + 대화내역)
        ticket_content_parts = []
        if ticket_data.get("subject"):
            ticket_content_parts.append(f"제목: {ticket_data['subject']}")
        if ticket_data.get("description_text"):
            ticket_content_parts.append(f"설명: {ticket_data['description_text']}")
        elif ticket_data.get("description"):
            ticket_content_parts.append(f"설명: {ticket_data['description']}")
        
        # LLM 기반 통합 지능형 처리 (Beta)
        use_intelligent_processing = ticket_data.get("conversations") and len(ticket_data.get("conversations", [])) > 10
        
        if use_intelligent_processing:
            try:
                from core.llm.intelligent_ticket_processor import get_intelligent_processor
                
                logger.info(f"🧠 LLM 통합 지능형 처리 시작 - 대화 수: {len(ticket_data.get('conversations', []))}")
                
                # 통합 분석 수행
                intelligent_processor = get_intelligent_processor()
                analysis = await intelligent_processor.process_ticket_intelligently(ticket_data, ui_language)
                
                # 최적화된 콘텐츠 생성
                ticket_content = intelligent_processor.get_optimized_ticket_content(ticket_data, analysis)
                
                logger.info(f"✅ 지능형 처리 완료 - 언어: {analysis.language}, "
                           f"선별 대화: {len(analysis.important_conversation_indices)}개, "
                           f"관련 첨부파일: {len(analysis.relevant_attachments)}개")
                
                # 분석 결과를 메타데이터에 추가
                if "metadata" not in ticket_data:
                    ticket_data["metadata"] = {}
                
                ticket_data["metadata"]["intelligent_analysis"] = {
                    "language": analysis.language,
                    "selected_conversations": len(analysis.important_conversation_indices),
                    "relevant_attachments": len(analysis.relevant_attachments)
                }
                
                # 관련 첨부파일을 메타데이터에 설정 (기존 첨부파일 선별 로직 대체)
                if analysis.relevant_attachments:
                    ticket_data["metadata"]["relevant_attachments"] = analysis.relevant_attachments
                
            except Exception as e:
                logger.warning(f"⚠️ 지능형 처리 실패, 기존 방식으로 폴백: {e}")
                use_intelligent_processing = False
        
        # 기존 방식 (폴백 또는 짧은 대화)
        if not use_intelligent_processing:
            # 대화내역 추가 (기존 로직 유지)
            if ticket_data.get("conversations"):
                conversations = ticket_data["conversations"]
                total_conversations = len(conversations)
                
                ticket_content_parts.append(f"대화내역 (총 {total_conversations}개):")
                
                # 개선된 선별 로직 (해결과정 중심)
                if total_conversations <= 15:
                    # 15개 이하: 모든 대화 포함 (문자 제한만 확장)
                    for i, conv in enumerate(conversations, 1):
                        if conv.get("body_text"):
                            content = conv['body_text'][:1000]  # 800→1000자로 확장
                            ticket_content_parts.append(f"대화 {i}: {content}{'...' if len(conv['body_text']) > 1000 else ''}")
                else:
                    # 15개 초과: 구간별 스마트 선별
                    selected_indices = []
                    
                    # 1. 초반 3개 (문제 제기)
                    selected_indices.extend(list(range(min(3, total_conversations))))
                    
                    # 2. 해결 키워드 포함 대화 우선 선별
                    resolution_keywords = ["해결", "완료", "수정", "배포", "진행", "확인", "solved", "completed", "fixed", "deployed", "resolved", "confirmed"]
                    for idx, conv in enumerate(conversations):
                        if idx not in selected_indices and len(selected_indices) < 20:  # 최대 20개
                            body = conv.get("body_text", "").lower()
                            if any(keyword in body for keyword in resolution_keywords):
                                selected_indices.append(idx)
                    
                    # 3. 후반 5개 (최종 결과)
                    final_indices = list(range(max(0, total_conversations - 5), total_conversations))
                    for idx in final_indices:
                        if idx not in selected_indices:
                            selected_indices.append(idx)
                    
                    # 4. 인덱스 정렬 후 대화 구성
                    selected_indices = sorted(set(selected_indices))
                    for idx in selected_indices:
                        conv = conversations[idx]
                        if conv.get("body_text"):
                            content = conv['body_text'][:1000]  # 700→1000자로 확장
                            ticket_content_parts.append(f"대화 {idx+1}: {content}{'...' if len(conv['body_text']) > 1000 else ''}")
            
            ticket_content = "\n".join(ticket_content_parts)
        
        # 병렬 처리를 위한 작업 정의
        import asyncio
        
        llm_manager = get_llm_manager()
        
        # 2. 병렬 실행할 작업들 정의
        async def generate_summary_task():
            """티켓 요약 생성 작업"""
            if not include_summary:
                return None
                
            logger.info(f"🎯 [실시간 티켓 요약] 티켓 {ticket_id} AI 요약 생성 시작")
            logger.info(f"    제목: {ticket_data.get('subject', 'N/A')}")
            logger.info(f"    대화수: {len(ticket_data.get('conversations', []))}개, 첨부파일: {len(ticket_data.get('attachments', []))}개")
            
            try:
                summary_result_dict = await llm_manager.generate_ticket_summary(ticket_data)
                summary_result = summary_result_dict.get("summary", "요약 생성 실패")
                
                logger.info(f"✅ [실시간 티켓 요약] 티켓 {ticket_id} YAML 템플릿 기반 요약 완료 ({len(summary_result)}자)")
                logger.info(f"\n📄 [조회 티켓 요약] \n{summary_result}")
                
                return summary_result
                
            except Exception as e:
                error_msg = f"YAML 템플릿 기반 요약 생성 중 오류 발생: {str(e)}"
                logger.error(f"❌ [실시간 티켓 요약] 티켓 {ticket_id} YAML 템플릿 요약 생성 실패: {e}")
                return error_msg

        async def search_similar_tickets_task():
            """유사 티켓 검색 작업 (멀티테넌트 Redis 캐시 적용)"""
            if not include_similar_tickets:
                return []
            
            # 멀티테넌트 캐시 키 생성 (테넌트 격리)
            import hashlib
            search_content_hash = hashlib.md5(ticket_content.encode()).hexdigest()[:16]
            cache_key = f"{tenant_id}:similar_tickets:{platform}:{ticket_id}:{search_content_hash}:{top_k_tickets}"
            
            # Redis 캐시 확인 (환경변수 기반 URL 사용)
            import redis.asyncio as redis
            import json
            redis_url = os.getenv("REDIS_URL")
            redis_client = None
            
            if redis_url:
                try:
                    redis_client = redis.from_url(redis_url, decode_responses=True)
                    cached_result = await redis_client.get(cache_key)
                    if cached_result:
                        cached_data = json.loads(cached_result)
                        logger.info(f"🎯 [Redis 캐시 히트] 테넌트 {tenant_id} 유사 티켓: {len(cached_data)}건")
                        await redis_client.close()
                        return cached_data
                except Exception as e:
                    logger.warning(f"Redis 캐시 조회 실패: {e}")
                    redis_client = None
                
            logger.info(f"🔍 [Redis 캐시 미스] 테넌트 {tenant_id} 유사 티켓 검색 시작 (최대 {top_k_tickets}건)")
            # 스마트 벡터 검색 - 자기 자신 자동 제외
            similar_results = await search_vector_db_only(
                query=ticket_content,
                tenant_id=tenant_id,
                platform=platform,
                doc_types=["ticket"],
                limit=top_k_tickets,  # 정확한 개수만 요청 (데이터베이스 레벨에서 필터링됨)
                exclude_id=ticket_id  # 자기 자신 제외 (벡터 DB 레벨에서 처리)
            )
            
            # 검색 결과를 유사 티켓 형식으로 변환 (수동 필터링 불필요)
            raw_similar_tickets = []
            for result in similar_results:
                raw_similar_tickets.append({
                    "id": result.get("original_id") or result["metadata"].get("original_id"),
                    "subject": result.get("subject") or result["metadata"].get("subject", ""),
                    "content": result.get("content", ""),
                    "score": result["score"],
                    "has_attachments": result.get("has_attachments", False),
                    "has_inline_images": result.get("has_inline_images", False),
                    "attachment_count": result.get("attachment_count", 0),
                    "metadata": result.get("extended_metadata", result.get("metadata", {}))
                })
                
            logger.info(f"✅ 유사 티켓 검색 완료: {len(raw_similar_tickets)}개 (현재 티켓 {ticket_id} 자동 제외됨)")
            
            # Redis 캐시에 결과 저장 (1시간 TTL)
            if redis_client and raw_similar_tickets:
                try:
                    cache_ttl = 3600  # 1시간
                    await redis_client.setex(
                        cache_key,
                        cache_ttl,
                        json.dumps(raw_similar_tickets, default=str)
                    )
                    logger.info(f"💾 [Redis 캐시 저장] 테넌트 {tenant_id} 유사 티켓 캐시됨 (TTL: {cache_ttl}초)")
                except Exception as e:
                    logger.warning(f"Redis 캐시 저장 실패: {e}")
                finally:
                    await redis_client.close()
            
            return raw_similar_tickets

        async def search_kb_documents_task():
            """KB 문서 검색 작업 (멀티테넌트 Redis 캐시 적용)"""
            if not include_kb_docs:
                return []
            
            # 멀티테넌트 캐시 키 생성 (테넌트 격리)
            import hashlib
            search_content_hash = hashlib.md5(ticket_content.encode()).hexdigest()[:16]
            cache_key = f"{tenant_id}:kb_documents:{platform}:{search_content_hash}:{top_k_kb}"
            
            # Redis 캐시 확인
            import redis.asyncio as redis
            import json
            redis_url = os.getenv("REDIS_URL")
            redis_client = None
            
            if redis_url:
                try:
                    redis_client = redis.from_url(redis_url, decode_responses=True)
                    cached_result = await redis_client.get(cache_key)
                    if cached_result:
                        cached_data = json.loads(cached_result)
                        logger.info(f"🎯 [Redis 캐시 히트] 테넌트 {tenant_id} KB 문서: {len(cached_data)}건")
                        await redis_client.close()
                        return cached_data
                except Exception as e:
                    logger.warning(f"Redis 캐시 조회 실패: {e}")
                    redis_client = None
                
            logger.info(f"🔍 [Redis 캐시 미스] 테넌트 {tenant_id} KB 문서 검색 시작 (최대 {top_k_kb}건)")
            kb_results = await search_vector_db_only(
                query=ticket_content,
                tenant_id=tenant_id,
                platform=platform,
                doc_types=["article"],
                limit=top_k_kb
            )
            
            # KB 문서는 메타데이터만 반환
            kb_documents = []
            for result in kb_results:
                kb_documents.append({
                    "id": result.get("original_id") or result["metadata"].get("original_id"),
                    "title": result.get("title") or result["metadata"].get("title", ""),
                    "url": f"/kb/articles/{result.get('original_id')}",
                    "score": result["score"],
                    "created_at": result.get("created_at", ""),
                    "updated_at": result.get("updated_at", ""),
                })
            logger.info(f"✅ KB 문서 검색 완료: {len(kb_documents)}건")
            
            # Redis 캐시에 결과 저장 (2시간 TTL - KB는 변경이 적음)
            if redis_client and kb_documents:
                try:
                    cache_ttl = 7200  # 2시간
                    await redis_client.setex(
                        cache_key,
                        cache_ttl,
                        json.dumps(kb_documents, default=str)
                    )
                    logger.info(f"💾 [Redis 캐시 저장] 테넌트 {tenant_id} KB 문서 캐시됨 (TTL: {cache_ttl}초)")
                except Exception as e:
                    logger.warning(f"Redis 캐시 저장 실패: {e}")
                finally:
                    await redis_client.close()
            
            return kb_documents

        # 3. 1단계: 티켓 요약과 벡터 검색을 병렬로 실행
        logger.info("🚀 [병렬 처리] 1단계: 티켓 요약 + 벡터 검색 병렬 실행 시작")
        parallel_stage1_start = time.time()
        
        summary_text, raw_similar_tickets, kb_documents = await asyncio.gather(
            generate_summary_task(),
            search_similar_tickets_task(), 
            search_kb_documents_task()
        )
        
        parallel_stage1_time = time.time() - parallel_stage1_start
        logger.info(f"⏱️ [병렬 처리] 1단계 완료 - 소요시간: {parallel_stage1_time:.2f}초")
        
        # 성능 최적화: 조회 티켓 요약본 로깅을 DEBUG 레벨로 제한
        if summary_text and summary_text.strip():
            logger.info(f"✅ [조회 티켓 요약] 완료 - {len(summary_text)}자")
            # DEBUG 레벨에서만 전체 요약 내용 로깅
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"📄 [조회 티켓 최종 요약본] \n{summary_text[:500]}...")

        # 4. 2단계: 유사 티켓 요약 생성 (병렬 처리)
        similar_tickets = []
        if raw_similar_tickets:
            logger.info("🚀 [병렬 처리] 2단계: 유사 티켓 요약 병렬 생성 시작")
            parallel_stage2_start = time.time()
            
            # 플랫폼 설정 구성
            platform_config = {
                "platform": platform,
                "domain": domain,
                "api_key": api_key,
                "tenant_id": tenant_id
            }
            
            similar_tickets = await llm_manager.generate_similar_ticket_summaries(raw_similar_tickets, ui_language, platform_config)
            
            parallel_stage2_time = time.time() - parallel_stage2_start
            logger.info(f"⏱️ [병렬 처리] 2단계 완료 - 유사 티켓 {len(similar_tickets)}건, 소요시간: {parallel_stage2_time:.2f}초")
            
            # 성능 최적화: 상세 요약 로깅을 DEBUG 레벨로 제한
            logger.info(f"✅ [유사 티켓 요약] {len(similar_tickets)}건 완료")
            
            # DEBUG 레벨에서만 상세 로깅
            if logger.isEnabledFor(logging.DEBUG):
                for i, ticket in enumerate(similar_tickets, 1):
                    ticket_summary = ticket.get('content', '요약없음')[:100] + "..."  # 요약 내용 제한
                    logger.debug(f"📄 [유사 티켓 {i}] ID: {ticket.get('id')} - {ticket_summary}")
        
        execution_time = time.time() - start_time
        
        logger.info(f"✅ Vector DB 단독 초기화 완료: {ticket_id}, 실행시간: {execution_time:.2f}초")
        
        return InitResponse(
            success=True,
            ticket_id=ticket_id,
            tenant_id=tenant_id,
            platform=platform,
            summary=summary_text,
            similar_tickets=similar_tickets,
            kb_documents=kb_documents,
            execution_time=execution_time,
            search_quality_score=0.95  # Vector DB 단독은 일관된 품질
        )
        
    except Exception as e:
        execution_time = time.time() - start_time
        logger.error(f"Vector DB 단독 초기화 실패: {ticket_id}, 오류: {str(e)}")
        
        return InitResponse(
            success=False,
            ticket_id=ticket_id,
            tenant_id=tenant_id,
            platform=platform,
            error=str(e),
            execution_time=execution_time
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
        from core.database.vectordb import search_vector_db_only
        
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
            similar_results = await search_vector_db_only(
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
            kb_results = await search_vector_db_only(
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
                    "url": f"/kb/articles/{result.get('original_id')}",
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






async def init_streaming_vector_only_mode(
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
    신규: Vector DB 단독 + 풀 스트리밍 모드
    - Vector DB에서만 데이터 검색
    - 실시간 요약 생성 (단계별 스트리밍)
    - SQL DB 접근 없음
    """
    
    async def generate_stream():
        try:
            start_time = time.time()
            logger.info(f"Vector DB 단독 스트리밍 초기화 시작 - ticket_id: {ticket_id}, tenant_id: {tenant_id}")
            
            # Vector DB 단독 스트리밍 초기화 실행
            from core.database.vectordb import search_vector_db_only
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
            yield f"data: {json.dumps(send_progress('init', 0, 'Vector DB 단독 초기화 시작'))}\n\n"
            
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
            
            # 대화내역 추가 (스트리밍에서도 개선된 로직 적용)
            if ticket_data.get("conversations"):
                conversations = ticket_data["conversations"]
                total_conversations = len(conversations)
                ticket_content_parts.append(f"대화내역 (총 {total_conversations}개):")
                
                # 스트리밍용 간소화된 선별 (성능 고려)
                if total_conversations <= 10:
                    for i, conv in enumerate(conversations[:10], 1):  # 최대 10개
                        if conv.get("body_text"):
                            content = conv['body_text'][:500]  # 스트리밍은 500자로 제한
                            ticket_content_parts.append(f"대화 {i}: {content}{'...' if len(conv['body_text']) > 500 else ''}")
                else:
                    # 초반 2개 + 후반 8개 (빠른 처리를 위해 단순화)
                    selected_indices = list(range(2)) + list(range(max(0, total_conversations - 8), total_conversations))
                    selected_indices = sorted(set(selected_indices))
                    for idx in selected_indices:
                        conv = conversations[idx]
                        if conv.get("body_text"):
                            content = conv['body_text'][:500]
                            ticket_content_parts.append(f"대화 {idx+1}: {content}{'...' if len(conv['body_text']) > 500 else ''}")
            
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
                    logger.info(f"\n📄 [조회 티켓 요약] \n{summary_text}")
                    
                    return summary_text
                    
                except Exception as e:
                    logger.error(f"❌ [조회 티켓 최우선] ticket_view 템플릿 사용 실패: {e}")
                    # 폴백
                    subject = ticket_data.get("subject", "제목 없음")
                    description = ticket_data.get("description_text") or ticket_data.get("description", "")
                    fallback_summary = f"## 🎫 {subject}\n\n**문제 상황**: {description[:200]}...\n\n**오류**: {str(e)}"
                    logger.info(f"\n📄 [조회 티켓 요약 - 폴백] \n{fallback_summary}")
                    return fallback_summary

            async def streaming_search_similar_task():
                """스트리밍용 유사 티켓 검색 작업"""
                if not include_similar:
                    return []
                    
                # 스마트 벡터 검색 - 자기 자신 자동 제외 (스트리밍용)
                similar_results = await search_vector_db_only(
                    query=ticket_content,
                    tenant_id=tenant_id,
                    platform=platform,
                    doc_types=["ticket"],
                    limit=3,  # 정확한 개수만 요청 (데이터베이스 레벨에서 필터링됨)
                    exclude_id=ticket_id  # 자기 자신 제외 (벡터 DB 레벨에서 처리)
                )
                
                raw_similar_tickets = []
                for result in similar_results:
                    raw_similar_tickets.append({
                        "id": result.get("original_id") or result["metadata"].get("original_id"),
                        "subject": result.get("subject") or result["metadata"].get("subject", ""),
                        "content": result.get("content", ""),
                        "score": result["score"],
                        "has_attachments": result.get("has_attachments", False),
                        "has_inline_images": result.get("has_inline_images", False),
                        "attachment_count": result.get("attachment_count", 0),
                        "metadata": result.get("extended_metadata", result.get("metadata", {}))
                    })
                
                return raw_similar_tickets

            async def streaming_search_kb_task():
                """스트리밍용 KB 문서 검색 작업"""
                if not include_kb:
                    return []
                    
                kb_results = await search_vector_db_only(
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
                        "url": f"/kb/articles/{result.get('original_id')}",
                        "score": result["score"],
                        "created_at": result.get("created_at", ""),
                        "updated_at": result.get("updated_at", ""),
                    })
                
                return kb_documents

            # 1단계: 요약 생성 시작 알림
            yield f"data: {json.dumps(send_progress('analysis', 30, 'AI 요약 생성 중...', start_time))}\n\n"
            
            # 1단계: 요약과 검색을 병렬로 실행
            summary_text, raw_similar_tickets, kb_documents = await asyncio.gather(
                streaming_summary_task(),
                streaming_search_similar_task(),
                streaming_search_kb_task()
            )
            
            # 요약 완료 진행률
            yield f"data: {json.dumps(send_progress('analysis_complete', 50, 'AI 요약 생성 완료', start_time))}\n\n"
            
            # 요약 결과 전송
            summary_chunk = {
                "type": "summary", 
                "content": summary_text,
                "ticket_id": ticket_id
            }
            yield f"data: {json.dumps(summary_chunk)}\n\n"
            
            # 2단계: 유사 티켓 요약 생성 (병렬 처리)
            if raw_similar_tickets:
                yield f"data: {json.dumps(send_progress('similar_tickets', 70, f'유사 티켓 검색 완료 ({len(raw_similar_tickets)}건)', start_time))}\n\n"
                
                # 플랫폼 설정 구성
            platform_config = {
                "platform": platform,
                "domain": domain,
                "api_key": api_key,
                "tenant_id": tenant_id
            }
            
            similar_tickets = await llm_manager.generate_similar_ticket_summaries(raw_similar_tickets, ui_language, platform_config)
            
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
            logger.info(f"Vector DB 단독 스트리밍 초기화 완료 - ticket_id: {ticket_id}, 총 실행시간: {streaming_execution_time:.2f}초")
                
        except Exception as e:
            logger.error(f"Vector DB 단독 스트리밍 초기화 실패: {e}")
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


async def init_streaming_hybrid_mode(
    ticket_id: str,
    tenant_id: str,
    platform: str,
    domain: str,
    api_key: str,
    include_similar: bool,
    include_kb: bool,
    retry_reason: Optional[str]
) -> StreamingResponse:
    """
    기존: 하이브리드 검색 + 스트리밍 요약 모드 (legacy)
    - 기존 하이브리드 검색 로직 사용
    - SQL + Vector DB 조합
    - 100% 기존 로직 보존
    """
    
    async def generate_stream():
        try:
            start_time = time.time()
            logger.info(f"하이브리드 스트리밍 초기화 시작 - ticket_id: {ticket_id}, tenant_id: {tenant_id}")
            
            # 티켓 데이터 조회 (기존 엔드포인트와 동일한 방식)
            from core.platforms.freshdesk.fetcher import fetch_ticket_details
            ticket_data = None
            try:
                # Freshdesk API를 통해 티켓 정보 조회
                ticket_data = await fetch_ticket_details(int(ticket_id), domain=domain, api_key=api_key)
            except Exception as e:
                logger.warning(f"Freshdesk API 호출 실패: {e}")
            
            if not ticket_data:
                # API 조회 실패 시 벡터 검색 폴백
                try:
                    ticket_data = vector_db.get_by_id(original_id_value=ticket_id, tenant_id=tenant_id, doc_type="ticket")
                except Exception as e:
                    logger.warning(f"벡터 DB 조회 실패: {e}")
            
            if not ticket_data:
                yield f"data: {json.dumps({'type': 'error', 'message': '티켓을 찾을 수 없습니다'})}\n\n"
                return
            
            # 메타데이터 추출 및 정규화 (기존 엔드포인트와 완전히 동일)
            ticket_metadata = ticket_data.get("metadata", {}) if isinstance(ticket_data, dict) else ticket_data
            
            # 디버깅: 실제 데이터 구조 확인
            logger.info(f"🔍 디버깅 - 티켓 데이터 구조: {list(ticket_data.keys()) if isinstance(ticket_data, dict) else 'Not a dict'}")
            logger.info(f"🔍 디버깅 - 메타데이터 구조: {list(ticket_metadata.keys()) if isinstance(ticket_metadata, dict) else 'Not a dict'}")
            
            # description_text 필드 우선 사용
            description_text = (
                ticket_metadata.get("description_text") or 
                ticket_data.get("description_text") or
                ticket_metadata.get("description") or
                ticket_data.get("description") or
                "티켓 본문 정보 없음"
            )
            
            # 티켓 정보 구성 (description_text 필드 우선 사용)
            structured_ticket_data = {
                "id": ticket_id,
                "subject": ticket_metadata.get("subject", f"티켓 ID {ticket_id}"),
                "description_text": description_text,
                "conversations": ticket_data.get("conversations", []) if isinstance(ticket_data, dict) else [],
                "tenant_id": tenant_id,
                "platform": platform,
                "metadata": ticket_metadata
            }
            
            # 디버깅: 최종 구조화된 데이터 확인
            logger.info(f"🔍 디버깅 - description_text: {description_text[:100]}..." if description_text else "None")  
            logger.info(f"🔍 디버깅 - 구조화된 티켓 제목: {structured_ticket_data['subject']}")
            logger.info(f"🔍 디버깅 - 구조화된 티켓 본문: {structured_ticket_data['description_text'][:100]}...")
            
            # 스트리밍 벡터 검색 실행
            llm_manager = get_llm_manager()
            adapter = InitHybridAdapter()
            
            async for chunk in adapter.execute_vector_init_streaming(
                llm_manager=llm_manager,
                ticket_data=structured_ticket_data,
                tenant_id=tenant_id,
                platform=platform,
                include_summary=True,
                include_similar_tickets=include_similar,
                include_kb_docs=include_kb,
                top_k_tickets=3,
                top_k_kb=3,
                retry_reason=retry_reason
            ):
                yield f"data: {json.dumps(chunk)}\n\n"
            
            # 완료 로깅
            streaming_execution_time = time.time() - start_time
            logger.info(f"하이브리드 스트리밍 초기화 완료 - ticket_id: {ticket_id}, 총 실행시간: {streaming_execution_time:.2f}초")
                
        except Exception as e:
            logger.error(f"하이브리드 스트리밍 초기화 실패: {e}")
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
