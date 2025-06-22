"""
데이터 저장 모듈 - SQLite 및 벡터 DB 저장

지침서 준수: 멀티테넌트 격리 및 성능 최적화
"""

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

def store_integrated_object_to_sqlite(
    db, 
    integrated_object: Dict[str, Any], 
    company_id: str, 
    platform: str = None
) -> bool:
    """
    통합 객체를 SQLite 데이터베이스에 저장합니다.
    
    Args:
        db: SQLite 데이터베이스 인스턴스
        integrated_object: 통합 객체
        company_id: 회사 ID (멀티테넌트 필수)
        platform: 플랫폼명
        
    Returns:
        bool: 저장 성공 여부
    """
    try:
        logger.info(f"[DEBUG] store_integrated_object_to_sqlite 함수 시작")
        logger.info(f"[DEBUG] 매개변수 - company_id: {company_id}, platform: {platform}")
        logger.info(f"[DEBUG] integrated_object keys: {list(integrated_object.keys()) if integrated_object else 'None'}")
        
        # 지침서 준수: company_id 필수 검증
        if not company_id:
            raise ValueError("company_id는 멀티테넌트 지원을 위해 필수입니다")
            
        object_type = integrated_object.get("object_type", "unknown")
        object_id = integrated_object.get("id")
        
        logger.info(f"[DEBUG] 객체 정보 - object_type: {object_type}, object_id: {object_id}")
        
        if not object_id:
            logger.error(f"[DEBUG] 객체 ID가 없음: {integrated_object}")
            return False
        
        logger.info(f"[DEBUG] 통합 객체 저장 시작: ID={object_id}, Type={object_type}, company_id={company_id}")
        
        # 1. integrated_objects 테이블에 저장
        integrated_data = {
            'original_id': object_id,  # 필드명 수정: object_id → original_id
            'company_id': company_id,
            'platform': platform,
            'object_type': object_type,
            'original_data': integrated_object,
            'integrated_content': integrated_object.get("integrated_text", ""),
            'summary': integrated_object.get("summary"),
            'metadata': {
                'has_conversations': integrated_object.get("has_conversations", False),
                'has_attachments': integrated_object.get("has_attachments", False),
                'conversation_count': len(integrated_object.get("conversations", [])),
                'attachment_count': len(integrated_object.get("all_attachments", []))
            }
        }
        
        logger.info(f"[DEBUG] integrated_objects 테이블 저장 시도: object_id={object_id}")
        logger.debug(f"[DEBUG] 저장할 integrated_data: {integrated_data}")
        try:
            # DB 연결 상태 확인 및 재연결
            if not db or not hasattr(db, 'connection') or not db.connection:
                logger.warning(f"[DEBUG] DB 연결이 없습니다. 재연결 시도...")
                from core.database.database import get_database
                db = get_database(company_id, platform or "freshdesk")
                logger.info(f"[DEBUG] DB 재연결 완료: {db.db_path}")
            
            result = db.insert_integrated_object(integrated_data)
            logger.info(f"[DEBUG] integrated_objects 테이블 저장 성공: object_id={object_id}, result={result}")
        except Exception as e:
            logger.error(f"[DEBUG] integrated_objects 테이블 저장 실패: {e}", exc_info=True)
            raise
        
        # 2. 기존 테이블에도 저장 (호환성 유지)
        logger.info(f"[DEBUG] 호환성 저장 시작: object_type={object_type}")
        if object_type == "integrated_ticket":
            result = _store_ticket_compatibility(db, integrated_object, company_id, platform)
            logger.info(f"[DEBUG] 티켓 호환성 저장 결과: {result}")
            return result
        elif object_type == "integrated_article":
            result = _store_article_compatibility(db, integrated_object, company_id, platform)
            logger.info(f"[DEBUG] 아티클 호환성 저장 결과: {result}")
            return result
        else:
            logger.error(f"[DEBUG] 알 수 없는 객체 타입: {object_type}")
            return False
            
    except Exception as e:
        logger.error(f"[DEBUG] 통합 객체 저장 실패 (company_id={company_id}, object_id={integrated_object.get('id')}): {e}", exc_info=True)
        return False


def _store_ticket_compatibility(db, integrated_object: Dict[str, Any], company_id: str, platform: str) -> bool:
    """티켓 호환성 저장"""
    try:
        ticket_id = integrated_object.get("id")
        if not ticket_id:
            logger.error("티켓 ID가 없습니다.")
            return False
        
        logger.info(f"티켓 호환성 저장 시작: ticket_id={ticket_id}")
        
        # 아이디 체계 명확화:
        # - ticket_id는 우리 DB의 내부 ID가 될 수 있음
        # - ticket_original_id는 티켓의 플랫폼 원본 ID (parent_original_id에 사용)
        ticket_original_id = integrated_object.get("original_id") or integrated_object.get("id")
        
        # 통합 객체를 ticket_data 형식으로 변환
        ticket_data = integrated_object.copy()
        ticket_data.update({
            'company_id': company_id,
            'platform': platform
        })
        
        logger.info(f"tickets 테이블 insert 시도: ticket_id={ticket_id}, original_id={ticket_original_id}")
        logger.debug(f"저장할 ticket_data: {ticket_data}")
        # insert_ticket은 딕셔너리를 받아서 raw_data에 저장
        try:
            result = db.insert_ticket(ticket_data)
            logger.info(f"tickets 테이블 insert 성공: result={result}")
        except Exception as e:
            logger.error(f"tickets 테이블 insert 실패: {e}", exc_info=True)
            raise
        
        # 대화내역도 개별적으로 저장 (옵션)
        conversations = integrated_object.get("conversations", [])
        logger.info(f"대화내역 저장 시작: {len(conversations)}개")
        for i, conv in enumerate(conversations):
            conversation_data = conv.copy()
            conversation_data.update({
                'ticket_id': ticket_id,
                'company_id': company_id,
                'platform': platform
            })
            
            # insert_conversation은 딕셔너리를 받아서 raw_data에 저장
            db.insert_conversation(conversation_data)
            
            # 대화 첨부파일 저장
            conv_attachments = conv.get("attachments", [])
            for attachment in conv_attachments:
                attachment_data = attachment.copy()
                
                # 아이디 체계 명확화:
                # - 대화 첨부파일의 parent_original_id는 소속 티켓의 플랫폼 원본 ID
                # - conv.get("ticket_id")는 대화가 소속된 티켓의 플랫폼 원본 ID
                parent_ticket_id = conv.get("ticket_id") or ticket_original_id
                
                attachment_data.update({
                    'parent_type': 'conversation',
                    'parent_original_id': parent_ticket_id,  # 소속 티켓의 플랫폼 원본 ID
                    'conversation_id': conv.get("id"),  # 대화 자체의 ID (추가 정보)
                    'company_id': company_id,
                    'platform': platform
                })
                
                # 첨부파일 개별 저장
                db.insert_attachment(attachment_data)
        
        # 첨부파일도 개별적으로 저장
        attachments = integrated_object.get("all_attachments", [])
        for attachment in attachments:
            attachment_data = attachment.copy()
            
            # 아이디 체계 명확화:
            # - ticket_id는 우리 DB의 내부 ID
            # - original_id는 티켓의 플랫폼 원본 ID (parent_original_id에 사용)
            ticket_original_id = integrated_object.get("original_id") or integrated_object.get("id")
            
            attachment_data.update({
                'parent_type': 'ticket',
                'parent_original_id': ticket_original_id,  # 티켓의 플랫폼 원본 ID
                'company_id': company_id,
                'platform': platform
            })
            
            # 첨부파일 개별 저장
            db.insert_attachment(attachment_data)
        
        logger.info(f"통합 티켓 객체 저장 완료: ID={ticket_id}, 대화={len(conversations)}개, 첨부파일={len(attachments)}개, company_id={company_id}")
        return True
        
    except Exception as e:
        logger.error(f"티켓 호환성 저장 실패: {e}")
        return False


def _store_article_compatibility(db, integrated_object: Dict[str, Any], company_id: str, platform: str) -> bool:
    """문서 호환성 저장"""
    try:
        article_id = integrated_object.get("id")
        if not article_id:
            logger.error("문서 ID가 없습니다.")
            return False
            
        # 통합 객체를 article_data 형식으로 변환
        article_data = integrated_object.copy()
        article_data.update({
            'company_id': company_id,
            'platform': platform
        })
            
        # insert_article은 딕셔너리를 받아서 raw_data에 저장
        db.insert_article(article_data)
        
        # 첨부파일도 개별적으로 저장
        attachments = integrated_object.get("attachments", [])
        for attachment in attachments:
            attachment_data = attachment.copy()
            
            # 아이디 체계 명확화:
            # - article_id는 우리 DB의 내부 ID
            # - original_id는 문서의 플랫폼 원본 ID (parent_original_id에 사용)
            article_original_id = integrated_object.get("original_id") or integrated_object.get("id")
            
            attachment_data.update({
                'parent_type': 'article',
                'parent_original_id': article_original_id,  # 문서의 플랫폼 원본 ID
                'company_id': company_id,
                'platform': platform
            })
            
            # 첨부파일 개별 저장
            db.insert_attachment(attachment_data)
        
        logger.info(f"통합 문서 객체 저장 완료: ID={article_id}, 첨부파일={len(attachments)}개, company_id={company_id}")
        return True
        
    except Exception as e:
        logger.error(f"문서 호환성 저장 실패: {e}")
        return False


def sanitize_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    메타데이터 값을 Qdrant 호환 형식으로 변환합니다.
    
    지침서 준수: 벡터 DB 최적화
    """
    sanitized = {}
    for key, value in metadata.items():
        if value is None:
            sanitized[key] = ""
        elif isinstance(value, list):
            sanitized[key] = str(value)  # JSON 문자열로 변환
        elif isinstance(value, dict):
            sanitized[key] = str(value)  # JSON 문자열로 변환
        elif isinstance(value, (str, int, float, bool)):
            sanitized[key] = value
        else:
            sanitized[key] = str(value)
    return sanitized


def get_integrated_object_from_sqlite(
    db, 
    object_id: int, 
    company_id: str, 
    object_type: str = "integrated_ticket", 
    platform: str = None
) -> Dict[str, Any]:
    """
    SQLite에서 통합 객체를 조회합니다.
    
    Args:
        db: SQLite 데이터베이스 인스턴스
        object_id: 객체 ID
        company_id: 회사 ID (멀티테넌트 필수)
        object_type: 객체 타입
        platform: 플랫폼명
        
    Returns:
        Dict: 통합 객체 또는 빈 딕셔너리
    """
    try:
        # 지침서 준수: company_id 필수 검증
        if not company_id:
            raise ValueError("company_id는 멀티테넌트 지원을 위해 필수입니다")
        
        cursor = db.connection.cursor()
        cursor.execute("""
            SELECT * FROM integrated_objects 
            WHERE original_id = ? AND company_id = ? AND object_type = ? AND platform = ?
        """, (object_id, company_id, object_type, platform))
        
        row = cursor.fetchone()
        if row:
            import json
            result = dict(row)
            # JSON 문자열 필드들을 딕셔너리로 변환
            if result.get('original_data'):
                result['original_data'] = json.loads(result['original_data'])
            if result.get('metadata'):
                result['metadata'] = json.loads(result['metadata'])
            return result
        
        return {}
        
    except Exception as e:
        logger.error(f"통합 객체 조회 실패: {e}")
        return {}


def search_integrated_objects_from_sqlite(
    db, 
    company_id: str, 
    object_type: str = None, 
    platform: str = None,
    limit: int = 100
) -> list:
    """
    SQLite에서 통합 객체들을 검색합니다.
    
    Args:
        db: SQLite 데이터베이스 인스턴스
        company_id: 회사 ID (멀티테넌트 필수)
        object_type: 객체 타입 (선택사항)
        platform: 플랫폼명
        limit: 결과 제한 수
        
    Returns:
        List: 통합 객체 리스트
    """
    try:
        # 지침서 준수: company_id 필수 검증
        if not company_id:
            raise ValueError("company_id는 멀티테넌트 지원을 위해 필수입니다")
        
        cursor = db.connection.cursor()
        
        if object_type:
            cursor.execute("""
                SELECT * FROM integrated_objects 
                WHERE company_id = ? AND object_type = ? AND platform = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (company_id, object_type, platform, limit))
        else:
            cursor.execute("""
                SELECT * FROM integrated_objects 
                WHERE company_id = ? AND platform = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (company_id, platform, limit))
        
        rows = cursor.fetchall()
        results = []
        
        import json
        for row in rows:
            result = dict(row)
            # JSON 문자열 필드들을 딕셔너리로 변환
            if result.get('original_data'):
                result['original_data'] = json.loads(result['original_data'])
            if result.get('metadata'):
                result['metadata'] = json.loads(result['metadata'])
            results.append(result)
        
        return results
        
    except Exception as e:
        logger.error(f"통합 객체 검색 실패: {e}")
        return []
