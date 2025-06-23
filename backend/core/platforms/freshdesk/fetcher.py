"""
플랫폼 데이터 가져오기 모듈

이 모듈은 외부 API를 통해 티켓과 지식베이스 문서를 가져오는 기능을 제공합니다.
비동기 HTTP 요청을 사용하여 데이터를 효율적으로 조회합니다.

프로젝트 규칙 및 가이드라인: /PROJECT_RULES.md 참조
"""
import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import httpx
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 환경변수에서 기본값을 가져오되, 파라미터로 오버라이드 가능하도록 수정
DEFAULT_DOMAIN = os.getenv("FRESHDESK_DOMAIN")
DEFAULT_API_KEY = os.getenv("FRESHDESK_API_KEY")

def extract_company_id_from_domain(domain: str) -> str:
    """
    도메인에서 company_id를 추출합니다.
    
    Args:
        domain: 플랫폼 도메인 (예: "your-company.freshdesk.com" 또는 "your-company")
        
    Returns:
        str: 추출된 company_id
    """
    if not domain:
        raise ValueError("도메인이 비어있습니다.")
    
    # .freshdesk.com이 포함된 경우 제거
    if ".freshdesk.com" in domain:
        company_id = domain.replace(".freshdesk.com", "")
    else:
        company_id = domain
    
    # https:// 또는 http://가 포함된 경우 제거
    if company_id.startswith(("https://", "http://")):
        from urllib.parse import urlparse
        parsed_url = urlparse(company_id)
        company_id = parsed_url.netloc.replace(".freshdesk.com", "")
    
    return company_id

def get_platform_config(domain: Optional[str] = None, api_key: Optional[str] = None) -> Tuple[str, str, str, Dict[str, str], Tuple[str, str]]:
    """
    플랫폼 설정을 가져오거나 파라미터로 오버라이드합니다.
    
    Args:
        domain: 플랫폼 도메인 (파라미터로 전달된 경우 우선 사용)
        api_key: 플랫폼 API 키 (파라미터로 전달된 경우 우선 사용)
        
    Returns:
        tuple: (company_id, base_url, api_key, headers, auth)
    """
    # 파라미터가 제공되지 않은 경우 환경변수에서 가져오기
    final_domain = domain or DEFAULT_DOMAIN
    final_api_key = api_key or DEFAULT_API_KEY
    
    if not final_domain or not final_api_key:
        raise ValueError("도메인과 API 키가 필요합니다.")
    
    # company_id 추출
    company_id = extract_company_id_from_domain(final_domain)
    
    # base_url 생성
    base_url = f"https://{final_domain}" if ".freshdesk.com" in final_domain else f"https://{final_domain}.freshdesk.com"
    base_url += "/api/v2"
    
    # 헤더 및 인증 정보 생성
    headers = {
        "Content-Type": "application/json",
        "X-Company-ID": company_id
    }
    auth = (final_api_key, "X")
    
    logger.debug(f"플랫폼 설정 - 도메인: {final_domain}, company_id: {company_id}")
    
    return company_id, base_url, final_api_key, headers, auth

# 이전 함수명과의 호환성을 위한 별칭
get_freshdesk_config = get_platform_config

# API 호출 시 사용할 재시도 횟수 및 대기 시간
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds - 지연 시간 증가

# 요청 간격 및 페이지 크기 설정 (토큰 한도 초과 방지)
REQUEST_DELAY = 0.2  # seconds - 성능 최적화 (1.5초 → 0.2초)
PER_PAGE = 50  # 페이지당 항목 수 감소

async def fetch_with_retry(client: httpx.AsyncClient, url: str, headers: Dict[str, str], auth: Tuple[str, str], params: Optional[Dict[str, Any]] = None) -> Any:
    """
    재시도 로직을 포함한 API 호출 함수
    
    Args:
        client: httpx 클라이언트 객체
        url: 요청할 URL
        headers: 요청 헤더
        auth: 인증 정보 (api_key, "X") 튜플
        params: 요청 파라미터
        
    Returns:
        Any: API 응답 데이터 (일반적으로 딕셔너리 또는 리스트)
    """
    retries = 0
    while retries < MAX_RETRIES:
        try:
            logger.debug(f"API 요청: {url} (params: {params})")
            resp = await client.get(url, headers=headers, auth=auth, params=params)
            resp.raise_for_status()
            
            # JSON 응답 파싱 및 None 체크
            try:
                json_data = resp.json()
                if json_data is None:
                    logger.warning(f"API 응답이 None입니다. URL: {url}")
                    return []  # None 대신 빈 리스트 반환
                
                # 응답 데이터 크기 로깅
                if isinstance(json_data, list):
                    logger.debug(f"API 응답 수신: {len(json_data)}개 항목")
                else:
                    logger.debug(f"API 응답 수신: {type(json_data)}")
                    
                return json_data
            except ValueError as json_error:
                logger.error(f"JSON 파싱 오류: {json_error}. URL: {url}, 응답 텍스트: {resp.text[:200]}")
                return []  # JSON 파싱 실패 시 빈 리스트 반환
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:  # Rate limit 초과
                retry_after = int(e.response.headers.get('Retry-After', RETRY_DELAY))
                logger.warning(f"Rate limit 초과. {retry_after}초 후 재시도합니다. (URL: {url})")
                await asyncio.sleep(retry_after)
                retries += 1
                continue
            elif e.response.status_code >= 500:  # 서버 오류
                logger.warning(f"서버 오류 발생: {e.response.status_code}. 재시도 중... (URL: {url})")
                await asyncio.sleep(RETRY_DELAY * (retries + 1))
                retries += 1
                continue
            else:
                logger.error(f"HTTP 오류: {e.response.status_code} - {e.response.text[:200]} (URL: {url})")
                raise
        except httpx.RequestError as e:
            logger.warning(f"요청 오류: {e}. 재시도 중... (URL: {url})")
            await asyncio.sleep(RETRY_DELAY * (retries + 1))
            retries += 1
            continue
        except Exception as e:
            logger.error(f"예상하지 못한 오류: {e} (URL: {url})")
            raise
    
    logger.error(f"최대 재시도 횟수({MAX_RETRIES})를 초과했습니다. (URL: {url})")
    raise Exception(f"최대 재시도 횟수({MAX_RETRIES})를 초과했습니다.")

async def fetch_ticket_conversations(client: httpx.AsyncClient, ticket_id: int, base_url: str, headers: Dict[str, str], auth: Tuple[str, str]) -> List[Dict[str, Any]]:
    """
    특정 티켓의 대화(conversation) 내역을 가져옵니다.
    
    Args:
        client: httpx 클라이언트 객체
        ticket_id: 티켓 ID
        base_url: API 베이스 URL
        headers: 요청 헤더
        auth: 인증 정보
        
    Returns:
        List[Dict[str, Any]]: 대화 내역 목록
    """
    try:
        logger.info(f"티켓 {ticket_id}의 대화 내역 요청 중...")
        conversations = await fetch_with_retry(client, f"{base_url}/tickets/{ticket_id}/conversations", headers, auth)
        if isinstance(conversations, list):
            logger.info(f"티켓 {ticket_id}의 대화 내역 {len(conversations)}개 수신 완료")
            return conversations
        else:
            logger.warning(f"티켓 {ticket_id}의 대화 내역이 예상된 형식이 아닙니다.")
            return []
    except Exception as e:
        logger.error(f"티켓 {ticket_id}의 대화 내역 가져오기 오류: {e}")
        return []

async def fetch_ticket_attachments(client: httpx.AsyncClient, ticket_id: int, base_url: str, headers: Dict[str, str], auth: Tuple[str, str], ticket_detail: Optional[Dict[str, Any]] = None, conversations: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    """
    특정 티켓의 첨부파일 정보를 가져옵니다.
    ticket_detail과 conversations가 제공되면 재사용하여 API 호출을 줄입니다.
    
    Args:
        client: httpx 클라이언트 객체
        ticket_id: 티켓 ID
        base_url: API 베이스 URL
        headers: 요청 헤더
        auth: 인증 정보
        ticket_detail: 이미 가져온 티켓 상세 정보 (옵션)
        conversations: 이미 가져온 대화 내역 (옵션)
        
    Returns:
        List[Dict[str, Any]]: 첨부파일 정보 목록
    """
    attachments = []
    try:
        # 티켓 상세 정보가 제공되지 않은 경우에만 가져오기
        if ticket_detail is None:
            logger.info(f"티켓 {ticket_id}의 상세 정보 요청 중...")
            ticket_detail = await fetch_with_retry(client, f"{base_url}/tickets/{ticket_id}", headers, auth)
        
        # 티켓 자체의 첨부파일 정보 추출
        if ticket_detail and "attachments" in ticket_detail and ticket_detail["attachments"]:
            for attachment in ticket_detail["attachments"]:
                attachments.append({
                    "id": attachment.get("id"),
                    "name": attachment.get("name"),
                    "content_type": attachment.get("content_type"),
                    "size": attachment.get("size"),
                    "attachment_url": attachment.get("attachment_url"),
                    "created_at": attachment.get("created_at"),
                    "updated_at": attachment.get("updated_at"),
                    "ticket_id": ticket_id,
                    "conversation_id": None  # 티켓 자체 첨부파일
                })
        
        # 대화 내역이 제공되지 않은 경우에만 가져오기
        if conversations is None:
            conversations = await fetch_ticket_conversations(client, ticket_id, base_url, headers, auth)
        for conv in conversations:
            # conv가 None이 아니고 딕셔너리 타입인지 확인
            if conv is not None and isinstance(conv, dict) and "attachments" in conv and conv["attachments"]:
                for attachment in conv["attachments"]:
                    attachments.append({
                        "id": attachment.get("id"),
                        "name": attachment.get("name"),
                        "content_type": attachment.get("content_type"),
                        "size": attachment.get("size"),
                        "attachment_url": attachment.get("attachment_url"),
                        "created_at": attachment.get("created_at"),
                        "updated_at": attachment.get("updated_at"),
                        "ticket_id": ticket_id,
                        "conversation_id": conv.get("id")  # 대화 ID
                    })
        
        logger.info(f"티켓 {ticket_id}의 첨부파일 {len(attachments)}개 수신 완료")
        return attachments
    except Exception as e:
        logger.error(f"티켓 {ticket_id}의 첨부파일 가져오기 오류: {e}")
        return []

async def fetch_article_attachments(client: httpx.AsyncClient, article_id: int, base_url: str, headers: Dict[str, str], auth: Tuple[str, str]) -> List[Dict[str, Any]]:
    """
    지식베이스 문서의 첨부파일 정보를 가져옵니다.
    
    Args:
        client: httpx 클라이언트 객체
        article_id: 아티클 ID
        base_url: API 베이스 URL
        headers: 요청 헤더
        auth: 인증 정보
        
    Returns:
        List[Dict[str, Any]]: 첨부파일 정보 목록
    """
    try:
        logger.info(f"지식베이스 문서 {article_id}의 상세 정보 요청 중...")
        
        # 아티클 상세 정보를 가져옴
        article_detail = await fetch_with_retry(client, f"{base_url}/solutions/articles/{article_id}", headers, auth)
        
        # 첨부파일 추출
        attachments = []
        if "attachments" in article_detail and article_detail["attachments"]:
            for attachment in article_detail["attachments"]:
                attachments.append({
                    "id": attachment.get("id"),
                    "name": attachment.get("name"),
                    "content_type": attachment.get("content_type"),
                    "size": attachment.get("size"),
                    "attachment_url": attachment.get("attachment_url"),
                    "created_at": attachment.get("created_at"),
                    "updated_at": attachment.get("updated_at"),
                    "article_id": article_id,
                    "folder_id": article_detail.get("folder_id"),  # 폴더 ID 추가
                    "category_id": article_detail.get("category_id")  # 카테고리 ID 추가
                })
        
        logger.info(f"지식베이스 문서 {article_id}의 첨부파일 {len(attachments)}개 수신 완료")
        return attachments
    except Exception as e:
        logger.error(f"지식베이스 문서 {article_id}의 첨부파일 가져오기 오류: {e}")
        return []

async def fetch_tickets(domain: Optional[str] = None, api_key: Optional[str] = None, per_page: int = 50, max_tickets: Optional[int] = None, company_id: Optional[str] = None, platform: str = "freshdesk", store_immediately: bool = True, start_date: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    티켓 목록을 비동기로 가져옵니다.
    페이지네이션을 처리하여 모든 티켓을 가져옵니다.
    updated_since 파라미터를 사용하여 지정된 날짜 또는 10년 전부터 모든 티켓을 가져옵니다.
    티켓의 대화 내역과 첨부파일도 함께 가져옵니다.
    
    Args:
        domain: 도메인 (파라미터로 전달되지 않으면 환경변수 사용)
        api_key: API 키 (파라미터로 전달되지 않으면 환경변수 사용)
        per_page: 페이지당 가져올 티켓 수 (기본값: 50)
        max_tickets: 최대 가져올 티켓 수 (None이면 무제한, 기본값: None)
        company_id: 회사 ID (멀티테넌트용)
        platform: 플랫폼명
        store_immediately: 즉시 저장 여부 (기본값: True)
        start_date: 수집 시작 날짜 (YYYY-MM-DD 형식, None이면 현재부터 10년 전)
        
    Returns:
        List[Dict[str, Any]]: 티켓 목록
    """
    # start_date가 None이면 현재부터 10년 전으로 설정
    if start_date is None:
        ten_years_ago = datetime.now() - timedelta(days=365 * 10)
        start_date = ten_years_ago.strftime("%Y-%m-%d")
        logger.info(f"start_date가 지정되지 않아 기본값으로 10년 전 날짜를 사용합니다: {start_date}")
    else:
        logger.info(f"지정된 시작 날짜 사용: {start_date}")
    
    # 설정 가져오기
    extracted_company_id, base_url, final_api_key, headers, auth = get_platform_config(domain, api_key)
    
    # company_id가 별도로 제공되지 않으면 domain에서 추출한 값 사용
    final_company_id = company_id or extracted_company_id
    
    # max_tickets 처리: None이면 무제한, 그렇지 않으면 지정된 값 사용
    if max_tickets is None:
        effective_max_tickets = float('inf')  # 무제한
        logger.info("최대 티켓 수 제한 없음 (무제한 수집)")
    else:
        effective_max_tickets = max_tickets
        logger.info(f"최대 티켓 수 제한: {max_tickets}개")
    
    # 즉시 저장 모드인 경우 DB 연결 초기화
    db = None
    if store_immediately:
        from core.database.database import get_database
        db = get_database(final_company_id, platform)
        logger.info(f"즉시 저장 모드: DB 연결 완료 - {db.db_path}")
    
    all_tickets = []
    page = 1
    max_pages = 100  # 최대 페이지 수 설정 - 안전 장치
    total_count = 0
    include_conversations = True  # 대화 내역 포함 여부
    include_attachments = True    # 첨부파일 포함 여부

    logger.info(f"티켓 데이터 가져오기 시작 - 도메인: {domain or DEFAULT_DOMAIN}")
    
    async with httpx.AsyncClient() as client:
        # 먼저 총 티켓 수를 확인
        try:
            params = {"page": 1, "per_page": 1, "include": "description"}
            tickets = await fetch_with_retry(client, f"{base_url}/tickets", headers, auth, params)
            # 헤더에서 총 티켓 수 확인 시도
            total_count = int(client.headers.get('X-Total-Count', 0))
            if total_count > 0:
                logger.info(f"총 티켓 수: {total_count}개")
                estimated_pages = (total_count // per_page) + (1 if total_count % per_page > 0 else 0)
                logger.info(f"예상 페이지 수: {estimated_pages}페이지")
        except Exception as e:
            logger.warning(f"총 티켓 수 확인 실패: {e}. 전체 티켓을 가져옵니다.")
            
        # 페이지별로 티켓 가져오기
        while page <= max_pages:
            try:
                # max_tickets에 따라 per_page 동적 조정
                if max_tickets is not None:
                    # 남은 티켓 수 계산
                    remaining_tickets = max_tickets - len(all_tickets)
                    if remaining_tickets <= 0:
                        logger.info(f"max_tickets({max_tickets})에 도달하여 수집을 중단합니다.")
                        break
                    # per_page를 남은 티켓 수와 기본 per_page 중 작은 값으로 설정
                    effective_per_page = min(per_page, remaining_tickets)
                    logger.info(f"남은 티켓 수: {remaining_tickets}개, 이번 페이지 요청 수: {effective_per_page}개")
                else:
                    effective_per_page = per_page
                
                # updated_since 파라미터 추가 (지정된 날짜 또는 10년 전부터 모든 티켓)
                params = {
                    "page": page, 
                    "per_page": effective_per_page,  # 동적으로 조정된 per_page 사용
                    "order_type": "asc", 
                    "order_by": "created_at",
                    "updated_since": f"{start_date}T00:00:00Z",  # 계산된 시작 날짜 사용
                    "include": "description"  # description 필드 포함
                }
                logger.info(f"티켓 데이터 페이지 {page} 요청 중...")
                
                tickets = await fetch_with_retry(client, f"{base_url}/tickets", headers, auth, params)
                
                # 디버깅을 위한 상세 로깅
                logger.info(f"페이지 {page} 응답: {type(tickets)}, 길이: {len(tickets) if isinstance(tickets, list) else 'N/A'}")
                
                # tickets가 None이거나 빈 리스트인 경우 처리
                if tickets is None:
                    logger.warning(f"페이지 {page}에서 None 응답을 받았습니다. 빈 리스트로 처리합니다.")
                    tickets = []
                elif not isinstance(tickets, list):
                    logger.warning(f"페이지 {page}에서 예상하지 못한 타입 응답: {type(tickets)}. 빈 리스트로 처리합니다.")
                    tickets = []
                
                if len(tickets) == 0:
                    logger.info(f"더 이상 티켓이 없습니다. (페이지 {page})")
                    break
                
                # 각 티켓에 대한 추가 정보 가져오기
                for i, ticket in enumerate(tickets):
                    if not isinstance(ticket, dict):
                        continue
                    ticket_id = ticket.get("id")
                    if not ticket_id:
                        continue
                    
                    try:
                        logger.info(f"티켓 {ticket_id} 처리 시작 ({i+1}/{len(tickets)})")
                        
                        # 대화 내역 가져오기
                        if include_conversations:
                            try:
                                conversations = await fetch_ticket_conversations(client, ticket_id, base_url, headers, auth)
                                ticket["conversations"] = conversations
                                logger.info(f"티켓 {ticket_id} 대화 내역 완료: {len(conversations)}개")
                            except Exception as e:
                                logger.error(f"티켓 {ticket_id} 대화 내역 수집 실패: {e}")
                                ticket["conversations"] = []
                        
                        # 첨부파일 가져오기
                        if include_attachments:
                            try:
                                # 이미 가져온 대화 내역을 재사용하여 중복 API 호출 방지
                                conversations_for_attachments = ticket.get("conversations", [])
                                attachments = await fetch_ticket_attachments(
                                    client, ticket_id, base_url, headers, auth,
                                    conversations=conversations_for_attachments  # 기존 대화 재사용
                                )
                                ticket["all_attachments"] = attachments
                                logger.info(f"티켓 {ticket_id} 첨부파일 완료: {len(attachments)}개")
                            except Exception as e:
                                logger.error(f"티켓 {ticket_id} 첨부파일 수집 실패: {e}")
                                ticket["all_attachments"] = []
                        
                        logger.info(f"티켓 {ticket_id} 처리 완료")
                        
                        # 즉시 저장 모드인 경우 DB에 저장
                        if store_immediately and db:
                            try:
                                logger.info(f"[STORE] 티켓 {ticket_id} 즉시 저장 시작")
                                
                                # 통합 객체 생성
                                from core.ingest.integrator import create_integrated_ticket_object
                                integrated_ticket = create_integrated_ticket_object(ticket, company_id=final_company_id)
                                logger.info(f"[STORE] 통합 티켓 객체 생성 완료: ID={integrated_ticket.get('id')}")
                                
                                # DB에 저장
                                from core.ingest.storage import store_integrated_object_to_sqlite
                                store_result = store_integrated_object_to_sqlite(db, integrated_ticket, final_company_id, platform)
                                
                                if store_result:
                                    logger.info(f"[STORE] ✅ 티켓 {ticket_id} 저장 성공")
                                else:
                                    logger.error(f"[STORE] ❌ 티켓 {ticket_id} 저장 실패")
                                    
                            except Exception as e:
                                logger.error(f"[STORE] 티켓 {ticket_id} 저장 중 오류: {e}", exc_info=True)
                        
                    except Exception as e:
                        logger.error(f"티켓 {ticket_id} 전체 처리 실패: {e}")
                        # 에러가 발생해도 계속 진행
                        if "conversations" not in ticket:
                            ticket["conversations"] = []
                        if "all_attachments" not in ticket:
                            ticket["all_attachments"] = []
                    
                all_tickets.extend(tickets)
                logger.info(f"티켓 {len(tickets)}개 수신 완료 (총 {len(all_tickets)}개)")
                
                # 최대 티켓 수 제한에 도달했는지 확인 (무제한이 아닌 경우에만)
                if max_tickets is not None and len(all_tickets) >= effective_max_tickets:
                    logger.info(f"최대 티켓 수 제한({max_tickets}개)에 도달했습니다.")
                    all_tickets = all_tickets[:max_tickets]  # 정확히 max_tickets개로 자르기
                    break
                
                # 마지막 페이지 확인 (받은 티켓 수가 요청한 effective_per_page보다 적으면 마지막 페이지)
                if len(tickets) < effective_per_page:
                    logger.info(f"마지막 페이지 도달 - 받은 티켓 수: {len(tickets)}, 요청 수: {effective_per_page}")
                    break  # 마지막 페이지
                
                # 총 티켓 수를 알고 있고, 모든 티켓을 가져왔다면 종료
                if total_count > 0 and len(all_tickets) >= total_count:
                    logger.info(f"모든 티켓을 가져왔습니다. ({len(all_tickets)}/{total_count})")
                    break
                
                # 다음 페이지로 이동
                page += 1
                logger.info(f"다음 페이지로 이동: {page}")
                
                # API 요청 사이에 지연 추가
                await asyncio.sleep(REQUEST_DELAY)
                
            except Exception as e:
                logger.error(f"티켓 데이터 가져오기 오류 (페이지 {page}): {e}")
                # 오류 발생 시 더 긴 지연 후 다음 페이지로 넘어감
                await asyncio.sleep(RETRY_DELAY * 2)
                
                # 최대 재시도 횟수 체크를 위한 변수 (옵션)
                page += 1  # 에러 발생 시에도 페이지 증가
                logger.warning(f"에러로 인해 페이지 {page-1}를 건너뜁니다. 다음 페이지: {page}")
                
                # 최대 페이지 수 체크 (무한 루프 방지)
                if page > max_pages:
                    logger.error(f"최대 페이지 수({max_pages})에 도달하여 중단합니다.")
                    break
        
        if page > max_pages:
            logger.warning(f"최대 페이지 수({max_pages})에 도달했습니다. 일부 티켓만 가져왔을 수 있습니다.")
    
    # DB 연결 정리
    if store_immediately and db:
        db.disconnect()
        logger.info("즉시 저장 모드: DB 연결 해제")
    
    logger.info(f"🎉 티켓 데이터 수집 완전 완료! 총 {len(all_tickets)}개 티켓")
    logger.info(f"[DEBUG] ===== fetch_tickets 함수 종료 준비 =====")
    logger.info(f"[DEBUG] 수집된 티켓 수: {len(all_tickets)}")
    logger.info(f"[DEBUG] 티켓 ID 목록 (처음 10개): {[t.get('id') for t in all_tickets[:10]]}")
    logger.info(f"[DEBUG] 각 티켓의 conversations/attachments 여부:")
    for i, ticket in enumerate(all_tickets[:5]):  # 처음 5개만 확인
        conv_count = len(ticket.get('conversations', []))
        att_count = len(ticket.get('all_attachments', []))
        logger.info(f"[DEBUG]   티켓 {ticket.get('id')}: conversations={conv_count}, attachments={att_count}")
    
    if store_immediately:
        logger.info(f"[DEBUG] 즉시 저장 모드로 실행되었습니다 - 모든 티켓이 개별적으로 저장되었습니다")
    else:
        logger.info(f"[DEBUG] 배치 저장 모드 - processor.py로 반환 시작...")
        
    logger.info("fetch_tickets 함수 정상 종료 - processor로 복귀합니다.")
    return all_tickets

async def fetch_kb_articles(
    domain: Optional[str] = None, 
    api_key: Optional[str] = None, 
    max_articles: Optional[int] = None,
    company_id: Optional[str] = None,
    platform: str = "freshdesk",
    store_immediately: bool = True
) -> List[Dict[str, Any]]:
    """
    지식베이스(솔루션) 문서 전체를 비동기로 가져옵니다.
    카테고리 → 폴더 → 문서 순으로 전체를 순회합니다.
    페이지네이션을 적용하여 모든 문서를 가져옵니다.
    문서의 첨부파일도 함께 가져옵니다.
    
    Args:
        domain: 도메인 (파라미터로 전달되지 않으면 환경변수 사용)
        api_key: API 키 (파라미터로 전달되지 않으면 환경변수 사용)
        max_articles: 최대 수집할 문서 수 (None이면 무제한)
        company_id: 회사 ID (멀티테넌트용)
        platform: 플랫폼명
        store_immediately: 즉시 저장 여부 (기본값: True)
        
    Returns:
        List[Dict[str, Any]]: 지식베이스 문서 목록
    """
    # 설정 가져오기
    extracted_company_id, base_url, final_api_key, headers, auth = get_platform_config(domain, api_key)
    
    # company_id가 별도로 제공되지 않으면 domain에서 추출한 값 사용
    final_company_id = company_id or extracted_company_id
    
    # 즉시 저장 모드인 경우 DB 연결 초기화
    db = None
    if store_immediately:
        from core.database.database import get_database
        db = get_database(final_company_id, platform)
        logger.info(f"[KB] 즉시 저장 모드: DB 연결 완료 - {db.db_path}")
    
    articles: List[Dict[str, Any]] = []
    include_attachments = True  # 첨부파일 포함 여부
    
    logger.info(f"지식베이스 문서 가져오기 시작 - 도메인: {domain or DEFAULT_DOMAIN}")
    
    async with httpx.AsyncClient() as client:
        try:
            # 1. 카테고리 목록 조회
            logger.info("지식베이스 카테고리 목록 요청 중...")
            categories_response = await fetch_with_retry(client, f"{base_url}/solutions/categories", headers, auth)
            
            if not isinstance(categories_response, list):
                logger.error("카테고리 응답이 예상된 형식이 아닙니다.")
                return []
                
            categories = categories_response
            logger.info(f"카테고리 {len(categories)}개 수신 완료")
            
            for cat in categories:
                if not isinstance(cat, dict):
                    continue
                cat_id = cat.get("id")
                cat_name = cat.get("name", "Unknown")
                logger.info(f"카테고리 '{cat_name}' (ID: {cat_id}) 처리 중...")
                
                # 2. 폴더 목록 조회
                folders_response = await fetch_with_retry(client, f"{base_url}/solutions/categories/{cat_id}/folders", headers, auth)
                
                if not isinstance(folders_response, list):
                    logger.warning(f"카테고리 '{cat_name}'의 폴더 응답이 예상된 형식이 아닙니다.")
                    continue
                    
                folders = folders_response
                logger.info(f"카테고리 '{cat_name}'에서 폴더 {len(folders)}개 수신 완료")
                
                for folder in folders:
                    if not isinstance(folder, dict):
                        continue
                    folder_id = folder.get("id")
                    folder_name = folder.get("name", "Unknown")
                    logger.info(f"폴더 '{folder_name}' (ID: {folder_id}) 처리 중...")
                    
                    # 3. 폴더별 문서 목록 조회 (페이지네이션 적용)
                    page = 1
                    
                    while True:
                        # max_articles에 따라 per_page 동적 조정
                        if max_articles is not None:
                            # 남은 문서 수 계산
                            remaining_articles = max_articles - len(articles)
                            if remaining_articles <= 0:
                                logger.info(f"max_articles({max_articles})에 도달하여 수집을 중단합니다.")
                                break
                            # per_page를 남은 문서 수와 기본 PER_PAGE 중 작은 값으로 설정
                            effective_per_page = min(PER_PAGE, remaining_articles)
                            logger.info(f"남은 문서 수: {remaining_articles}개, 이번 페이지 요청 수: {effective_per_page}개")
                        else:
                            effective_per_page = PER_PAGE
                        
                        params = {"page": page, "per_page": effective_per_page}
                        logger.info(f"폴더 '{folder_name}'의 문서 페이지 {page} 요청 중...")
                        
                        folder_articles = await fetch_with_retry(
                            client, 
                            f"{base_url}/solutions/folders/{folder_id}/articles",
                            headers,
                            auth,
                            params
                        )
                        
                        if not folder_articles:
                            logger.info(f"폴더 '{folder_name}' 페이지 {page}: 더 이상 문서가 없음")
                            break
                        elif not isinstance(folder_articles, list):
                            logger.warning(f"폴더 '{folder_name}' 페이지 {page}: 예상하지 못한 응답 형식 - {type(folder_articles)}")
                            break
                            
                        # 카테고리 및 폴더 정보 추가와 필터링된 문서만 수집
                        valid_articles = []
                        for article in folder_articles:
                            if not isinstance(article, dict):
                                continue
                            
                            # KB 문서 status 필터링: draft 상태(status=1)는 제외하고 published 상태(status=2)만 수집
                            article_status = article.get("status")
                            if article_status == 1:  # draft 상태는 건너뛰기
                                continue
                            elif article_status != 2:  # published 상태가 아닌 다른 상태도 로그에 기록
                                logger.warning(f"예상하지 못한 status 값 ({article_status}) - ID: {article.get('id')}, 제목: {article.get('title', 'Unknown')}")
                                continue
                            
                            # max_articles 제한 체크
                            if max_articles is not None and len(articles) + len(valid_articles) >= max_articles:
                                logger.info(f"최대 문서 수 제한 ({max_articles}개)에 도달하여 수집을 중단합니다.")
                                break
                                
                            article["category_id"] = cat_id
                            article["category_name"] = cat_name
                            article["folder_id"] = folder_id
                            article["folder_name"] = folder_name
                            
                            # 각 문서에 대한 첨부파일 정보 가져오기
                            if include_attachments:
                                article_id = article.get("id")
                                if article_id:
                                    attachments = await fetch_article_attachments(client, article_id, base_url, headers, auth)
                                    article["attachments"] = attachments
                                    
                            # 즉시 저장 모드인 경우 개별 문서를 바로 저장
                            if store_immediately and db:
                                article_id = article.get("id")
                                try:
                                    logger.info(f"[KB STORE] KB 문서 {article_id} 즉시 저장 시작")
                                    
                                    # 통합 객체 생성
                                    from core.ingest.integrator import create_integrated_article_object
                                    integrated_article = create_integrated_article_object(article, company_id=final_company_id)
                                    logger.info(f"[KB STORE] 통합 KB 문서 객체 생성 완료: ID={integrated_article.get('id')}")
                                    
                                    # DB에 저장
                                    from core.ingest.storage import store_integrated_object_to_sqlite
                                    store_result = store_integrated_object_to_sqlite(db, integrated_article, final_company_id, platform)
                                    
                                    if store_result:
                                        logger.info(f"[KB STORE] ✅ KB 문서 {article_id} 저장 성공")
                                    else:
                                        logger.error(f"[KB STORE] ❌ KB 문서 {article_id} 저장 실패")
                                        
                                except Exception as e:
                                    logger.error(f"[KB STORE] KB 문서 {article_id} 저장 중 오류: {e}", exc_info=True)
                            
                            valid_articles.append(article)
                        
                        articles.extend(valid_articles)
                        logger.info(f"폴더 '{folder_name}' 페이지 {page}: 원본 {len(folder_articles)}개 → 필터링 후 {len(valid_articles)}개 → 누적 총 {len(articles)}개")
                        
                        # max_articles 제한 체크 (extend 후)
                        if max_articles is not None and len(articles) >= max_articles:
                            logger.info(f"최대 문서 수 제한 ({max_articles}개)에 도달하여 수집을 중단합니다.")
                            return articles[:max_articles]  # 정확히 제한 수만큼 반환
                        
                        if len(valid_articles) < effective_per_page:
                            logger.info(f"폴더 '{folder_name}' 페이지 {page}: 유효 문서 {len(valid_articles)}개 < 요청 크기 {effective_per_page} → 마지막 페이지로 판단")
                            break  # 마지막 페이지
                            
                        page += 1
                        
                        # API 요청 사이에 짧은 지연 추가
                        await asyncio.sleep(REQUEST_DELAY)
                        
        except Exception as e:
            logger.error(f"지식베이스 문서 가져오기 오류: {e}")
            raise
            
    logger.info(f"지식베이스 문서 가져오기 완료. 총 {len(articles)}개 문서")
    
    # max_articles 제한 적용 (최종 체크)
    if max_articles is not None and len(articles) > max_articles:
        logger.info(f"최대 문서 수 제한 ({max_articles}개) 적용하여 {len(articles)}개에서 {max_articles}개로 제한")
        return articles[:max_articles]
    
    return articles

async def fetch_ticket_details(ticket_id: int, domain: Optional[str] = None, api_key: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    특정 티켓의 상세 정보를 비동기로 가져옵니다.
    대화 내역과 첨부파일도 함께 가져옵니다.
    
    Args:
        ticket_id: 티켓 ID
        domain: 플랫폼 도메인 (파라미터로 전달되지 않으면 환경변수 사용)
        api_key: 플랫폼 API 키 (파라미터로 전달되지 않으면 환경변수 사용)
        
    Returns:
        Optional[Dict[str, Any]]: 티켓 상세 정보 (대화내역, 첨부파일 포함) 또는 None (티켓이 없는 경우)
    """
    # 플랫폼 설정 가져오기
    company_id, base_url, final_api_key, headers, auth = get_platform_config(domain, api_key)
    
    logger.info(f"티켓 {ticket_id} 상세 정보 가져오기 시작 - 도메인: {domain or DEFAULT_DOMAIN}")
    
    async with httpx.AsyncClient() as client:
        try:
            # 티켓 기본 정보 가져오기
            ticket_url = f"{base_url}/tickets/{ticket_id}"
            logger.info(f"티켓 {ticket_id} 기본 정보 요청 중: {ticket_url}")
            ticket_data = await fetch_with_retry(client, ticket_url, headers, auth)
            logger.info(f"티켓 {ticket_id} 기본 정보 수신 완료")

            # 대화 내역 포함 (기존 함수 활용)
            conversations = await fetch_ticket_conversations(client, ticket_id, base_url, headers, auth)
            ticket_data["conversations"] = conversations
            
            # 첨부파일 포함 (이미 가져온 대화 내역을 재사용하여 API 호출 최적화)
            ticket_data["all_attachments"] = await fetch_ticket_attachments(
                client, ticket_id, base_url, headers, auth, ticket_detail=ticket_data, conversations=conversations
            )
            
            logger.info(f"티켓 {ticket_id} 상세 정보 (대화, 첨부파일 포함) 가져오기 완료")
            return ticket_data
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(f"티켓 {ticket_id}를 찾을 수 없습니다 (404).")
                return None
            logger.error(f"티켓 {ticket_id} 상세 정보 가져오기 HTTP 오류: {e}")
            raise
        except Exception as e:
            logger.error(f"티켓 {ticket_id} 상세 정보 가져오기 중 예외 발생: {e}")
            raise