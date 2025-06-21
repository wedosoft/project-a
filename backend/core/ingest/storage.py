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
    platform: str = "freshdesk"
) -> bool:
    """
    통합 객체를 SQLite 데이터베이스에 저장합니다.
    
    Args:
        db: SQLite 데이터베이스 인스턴스
        integrated_object: 통합 객체
        company_id: 회사 ID (멀티테넌트 필수)
        platform: 플랫폼명 (기본: freshdesk)
        
    Returns:
        bool: 저장 성공 여부
    """
    try:
        # 지침서 준수: company_id 필수 검증
        if not company_id:
            raise ValueError("company_id는 멀티테넌트 지원을 위해 필수입니다")
            
        object_type = integrated_object.get("object_type", "unknown")
        
        # 1. integrated_objects 테이블에 저장
        integrated_data = {
            'object_id': integrated_object.get("id"),
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
        
        db.insert_integrated_object(integrated_data)
        logger.info(f"통합 객체 저장 완료: ID={integrated_data['object_id']}, Type={object_type}, company_id={company_id}")
        
        # 2. 기존 테이블에도 저장 (호환성 유지)
        if object_type == "integrated_ticket":
            return _store_ticket_compatibility(db, integrated_object, company_id, platform)
        elif object_type == "integrated_article":
            return _store_article_compatibility(db, integrated_object, company_id, platform)
        else:
            logger.error(f"알 수 없는 객체 타입: {object_type}")
            return False
            
    except Exception as e:
        logger.error(f"통합 객체 저장 실패 (company_id={company_id}): {e}")
        return False


def _store_ticket_compatibility(db, integrated_object: Dict[str, Any], company_id: str, platform: str) -> bool:
    """티켓 호환성 저장"""
    try:
        ticket_id = integrated_object.get("id")
        if not ticket_id:
            logger.error("티켓 ID가 없습니다.")
            return False
            
        # 통합 객체를 ticket_data 형식으로 변환
        ticket_data = integrated_object.copy()
        ticket_data.update({
            'company_id': company_id,
            'platform': platform
        })
            
        # insert_ticket은 딕셔너리를 받아서 raw_data에 저장
        result = db.insert_ticket(ticket_data)
        
        # 대화내역도 개별적으로 저장 (옵션)
        conversations = integrated_object.get("conversations", [])
        for conv in conversations:
            conversation_data = conv.copy()
            conversation_data.update({
                'ticket_id': ticket_id,
                'company_id': company_id,
                'platform': platform
            })
            
            # insert_conversation은 딕셔너리를 받아서 raw_data에 저장
            db.insert_conversation(conversation_data)
        
        logger.info(f"통합 티켓 객체 저장 완료: ID={ticket_id}, 대화={len(conversations)}개, company_id={company_id}")
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
        
        logger.info(f"통합 문서 객체 저장 완료: ID={article_id}, company_id={company_id}")
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
    platform: str = "freshdesk"
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
            WHERE object_id = ? AND company_id = ? AND object_type = ? AND platform = ?
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
    platform: str = "freshdesk",
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
