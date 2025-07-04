"""
SQLite 데이터베이스 저장 및 검색 기능

통합 객체 (integrated_objects) 중심의 데이터 저장소 관리
"""

import sqlite3
import json
import logging
from datetime import datetime
from typing import Dict, List, Any
import traceback

logger = logging.getLogger(__name__)

# ORM 마이그레이션 레이어 import (선택적)
try:
    from ..migration_layer import store_integrated_object_with_migration
    ORM_AVAILABLE = True
    logger.info("✅ ORM 마이그레이션 레이어 사용 가능")
except ImportError:
    ORM_AVAILABLE = False
    logger.info("⚠️ ORM 마이그레이션 레이어 사용 불가, SQLite 모드로 실행")

"""
데이터 저장 모듈 - SQLite 및 벡터 DB 저장

지침서 준수: 멀티테넌트 격리 및 성능 최적화
"""

from typing import Any, Dict

# integrated_object 저장 기능 제거됨 - Vector DB 단독 모드로 전환
# 이 함수는 더 이상 사용되지 않습니다.
def store_integrated_object_to_sqlite(
    db, 
    integrated_object: Dict[str, Any], 
    tenant_id: str, 
    platform: str = None
) -> bool:
    """
    [DEPRECATED] 통합 객체 저장 기능이 제거되었습니다.
    Vector DB 단독 모드로 전환되어 이 함수는 더 이상 사용되지 않습니다.
    
    Returns:
        bool: 항상 True 반환 (호환성 유지)
    """
    logger.debug("store_integrated_object_to_sqlite 함수는 deprecated됨 - Vector DB 단독 모드 사용")
    return True
    # 기존 복잡한 저장 로직 제거됨 - Vector DB 단독 모드 사용
    return True

# 호환성 저장 함수들 제거됨 - Vector DB 단독 모드로 전환
def _store_ticket_compatibility(db, integrated_object: Dict[str, Any], tenant_id: str, platform: str) -> bool:
    """[DEPRECATED] 티켓 호환성 저장 기능 제거됨"""
    logger.warning("_store_ticket_compatibility 기능이 제거되었습니다 - Vector DB 단독 모드 사용")
    return True
    
    # 이하 기존 코드 주석 처리됨
    """
    try:
        ticket_id = integrated_object.get("object_id")
        if not ticket_id:
            logger.error("티켓 object_id가 없습니다.")
            return False
        
        logger.info(f"티켓 호환성 저장 시작: ticket_id={ticket_id}")
        
        # 아이디 체계 명확화:
        # - ticket_id는 우리 DB의 내부 ID가 될 수 있음
        # - ticket_original_id는 티켓의 플랫폼 원본 ID (parent_original_id에 사용)
        ticket_original_id = integrated_object.get("original_id") or integrated_object.get("id")
        
        # 🔍 디버깅: original_id 확인
        logger.debug(f"🔍 integrated_object에서 original_id: {integrated_object.get('original_id')}")
        logger.debug(f"🔍 integrated_object에서 id: {integrated_object.get('id')}")
        logger.debug(f"🔍 최종 ticket_original_id: {ticket_original_id}")
        
        if not ticket_original_id:
            logger.error("original_id는 필수입니다")
            return False
        
        # 통합 객체를 ticket_data 형식으로 변환
        ticket_data = integrated_object.copy()
        ticket_data.update({
            'tenant_id': tenant_id,
            'platform': platform,
            'original_id': str(ticket_original_id)  # 명시적으로 original_id 설정
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
        if conversations:
            logger.debug(f"대화내역 저장: {len(conversations)}개")
            for i, conv in enumerate(conversations):
                conversation_data = conv.copy()
                conversation_data.update({
                    'ticket_id': ticket_id,
                    'tenant_id': tenant_id,
                    'platform': platform
                })
                
                # insert_conversation은 딕셔너리를 받아서 raw_data에 저장
                db.insert_conversation(conversation_data)
                
                # 대화 첨부파일 저장
                conv_attachments = conv.get("attachments", [])
                for attachment in conv_attachments:
                    attachment_data = attachment.copy()
                    
                    # 🔍 디버깅: 대화 첨부파일 원본 데이터 구조 확인
                    logger.debug(f"🔍 대화 첨부파일 원본 데이터: {attachment}")
                    
                    # 아이디 체계 명확화:
                    # - 대화 첨부파일의 parent_original_id는 소속 티켓의 플랫폼 원본 ID
                    # - conv.get("ticket_id")는 대화가 소속된 티켓의 플랫폼 원본 ID
                    parent_ticket_id = conv.get("ticket_id") or ticket_original_id
                    
                    # 첨부파일 자체의 ID 확인
                    attachment_id = attachment.get('id') or attachment.get('attachment_id')
                    
                    attachment_data.update({
                        'original_id': str(attachment_id),  # 첨부파일 자체의 원본 ID
                        'parent_type': 'conversation',
                        'parent_original_id': str(parent_ticket_id),  # 문자열로 변환
                        'conversation_id': conv.get("id"),  # 대화 자체의 ID (추가 정보)
                        'tenant_id': tenant_id,
                        'platform': platform
                    })
                    
                    # 🔍 최종 저장 데이터 확인
                    logger.debug(f"🔍 대화 첨부파일 최종 저장 데이터: {attachment_data}")
                    
                    # 첨부파일 개별 저장
                    try:
                        db.insert_attachment(attachment_data)
                        logger.debug(f"🔍 대화 첨부파일 저장 성공: {attachment_id}")
                    except Exception as e:
                        logger.error(f"대화 첨부파일 저장 실패: {attachment_id}, error: {e}")
                        # 첨부파일 하나 실패해도 전체는 계속 진행
        
        # 첨부파일도 개별적으로 저장
        attachments = integrated_object.get("all_attachments", [])
        logger.debug(f"🔍 저장할 첨부파일 수: {len(attachments)}개")
        for attachment in attachments:
            attachment_data = attachment.copy()
            
            # 🔍 디버깅: 첨부파일 원본 데이터 구조 확인
            logger.debug(f"🔍 첨부파일 원본 데이터: {attachment}")
            
            # 아이디 체계 명확화:
            # - ticket_id는 우리 DB의 내부 ID
            # - original_id는 티켓의 플랫폼 원본 ID (parent_original_id에 사용)
            ticket_original_id = integrated_object.get("original_id") or integrated_object.get("id")
            
            # 첨부파일 자체의 ID 확인
            attachment_id = attachment.get('id') or attachment.get('attachment_id')
            
            # 🔍 디버깅: 첨부파일 저장 정보
            logger.debug(f"🔍 첨부파일 저장: attachment_id={attachment_id}, parent_original_id={ticket_original_id}")
            
            # 첨부파일에 original_id 필드 추가 (첨부파일 자체의 ID)
            attachment_data.update({
                'original_id': str(attachment_id),  # 첨부파일 자체의 원본 ID
                'parent_type': 'ticket',
                'parent_original_id': str(ticket_original_id),  # 문자열로 변환
                'tenant_id': tenant_id,
                'platform': platform
            })
            
            # 🔍 최종 저장 데이터 확인
            logger.debug(f"🔍 첨부파일 최종 저장 데이터: {attachment_data}")
            
            # 첨부파일 개별 저장
            try:
                db.insert_attachment(attachment_data)
                logger.debug(f"🔍 첨부파일 저장 성공: {attachment_id}")
            except Exception as e:
                logger.error(f"첨부파일 저장 실패: {attachment_id}, error: {e}")
                # 첨부파일 하나 실패해도 전체는 계속 진행
        
        logger.info(f"티켓 저장 완료: ID={ticket_id}, 대화={len(conversations)}개, 첨부파일={len(attachments)}개")
        return True
        
    except Exception as e:
        logger.error(f"티켓 호환성 저장 실패: {e}")
        return False
    """


def _store_article_compatibility(db, integrated_object: Dict[str, Any], tenant_id: str, platform: str) -> bool:
    """[DEPRECATED] 문서 호환성 저장 기능 제거됨"""
    logger.warning("_store_article_compatibility 기능이 제거되었습니다 - Vector DB 단독 모드 사용")
    return True
    
    # 이하 기존 코드 주석 처리됨
    """
    try:
        article_id = integrated_object.get("object_id")
        if not article_id:
            logger.error("문서 object_id가 없습니다.")
            return False
            
        # 통합 객체를 article_data 형식으로 변환
        article_data = integrated_object.copy()
        article_data.update({
            'tenant_id': tenant_id,
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
                'tenant_id': tenant_id,
                'platform': platform
            })
            
            # 첨부파일 개별 저장
            db.insert_attachment(attachment_data)
        
        logger.info(f"문서 저장 완료: ID={article_id}, 첨부파일={len(attachments)}개")
        return True
        
    except Exception as e:
        logger.error(f"문서 호환성 저장 실패: {e}")
        return False
    """


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
    tenant_id: str, 
    object_type: str = "integrated_ticket", 
    platform: str = None
) -> Dict[str, Any]:
    """
    SQLite에서 통합 객체를 조회합니다.
    
    Args:
        db: SQLite 데이터베이스 인스턴스
        object_id: 객체 ID
        tenant_id: 테넌트 ID (멀티테넌트 필수)
        object_type: 객체 타입
        platform: 플랫폼명
        
    Returns:
        Dict: 통합 객체 또는 빈 딕셔너리
    """
    try:
        # 지침서 준수: tenant_id 필수 검증
        if not tenant_id:
            raise ValueError("tenant_id는 멀티테넌트 지원을 위해 필수입니다")
        
        cursor = db.connection.cursor()
        cursor.execute("""
            SELECT * FROM integrated_objects 
            WHERE original_id = ? AND tenant_id = ? AND object_type = ? AND platform = ?
        """, (object_id, tenant_id, object_type, platform))
        
        row = cursor.fetchone()
        if row:
            import json
            result = dict(row)
            # JSON 문자열 필드들을 딕셔너리로 변환
            if result.get('original_data'):
                result['original_data'] = json.loads(result['original_data'])
            if result.get('tenant_metadata'):
                result['tenant_metadata'] = json.loads(result['tenant_metadata'])
            return result
        
        return {}
        
    except Exception as e:
        logger.error(f"통합 객체 조회 실패: {e}")
        return {}


def search_integrated_objects_from_sqlite(
    db, 
    tenant_id: str, 
    object_type: str = None, 
    platform: str = None,
    limit: int = 100
) -> list:
    """
    SQLite에서 통합 객체들을 검색합니다.
    
    Args:
        db: SQLite 데이터베이스 인스턴스
        tenant_id: 테넌트 ID (멀티테넌트 필수)
        object_type: 객체 타입 (선택사항)
        platform: 플랫폼명
        limit: 결과 제한 수
        
    Returns:
        List: 통합 객체 리스트
    """
    try:
        # 지침서 준수: tenant_id 필수 검증
        if not tenant_id:
            raise ValueError("tenant_id는 멀티테넌트 지원을 위해 필수입니다")
        
        cursor = db.connection.cursor()
        
        if object_type:
            cursor.execute("""
                SELECT * FROM integrated_objects 
                WHERE tenant_id = ? AND object_type = ? AND platform = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (tenant_id, object_type, platform, limit))
        else:
            cursor.execute("""
                SELECT * FROM integrated_objects 
                WHERE tenant_id = ? AND platform = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (tenant_id, platform, limit))
        
        rows = cursor.fetchall()
        results = []
        
        import json
        for row in rows:
            result = dict(row)
            # JSON 문자열 필드들을 딕셔너리로 변환
            if result.get('original_data'):
                result['original_data'] = json.loads(result['original_data'])
            if result.get('tenant_metadata'):
                result['tenant_metadata'] = json.loads(result['tenant_metadata'])
            results.append(result)
        
        return results
        
    except Exception as e:
        logger.error(f"통합 객체 검색 실패: {e}")
        return []
