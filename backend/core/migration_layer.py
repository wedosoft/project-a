"""
점진적 마이그레이션 레이어

기존 SQLite 코드와 새로운 ORM 코드 간의 브릿지 역할
"""

import os
import logging
from typing import Dict, Any, List, Optional

from .repositories.integrated_object_repository import IntegratedObjectRepository
from .database.manager import get_db_manager

logger = logging.getLogger(__name__)


class MigrationLayer:
    """기존 SQLite와 새 ORM 간의 브릿지"""
    
    def __init__(self, use_orm: bool = None):
        # 환경변수로 ORM 사용 여부 결정
        if use_orm is None:
            use_orm = os.getenv('USE_ORM', 'false').lower() == 'true'
        
        self.use_orm = use_orm
        logger.info(f"MigrationLayer 초기화: use_orm={self.use_orm}")
    
    def store_integrated_object(
        self, 
        integrated_object: Dict[str, Any], 
        tenant_id: str, 
        platform: str = "freshdesk"
    ) -> bool:
        """통합 객체 저장 (ORM/SQLite 선택적 사용)"""
        
        if self.use_orm:
            return self._store_integrated_object_orm(integrated_object, tenant_id, platform)
        else:
            return self._store_integrated_object_sqlite(integrated_object, tenant_id, platform)
    
    def _store_integrated_object_orm(
        self, 
        integrated_object: Dict[str, Any], 
        tenant_id: str, 
        platform: str = "freshdesk"
    ) -> bool:
        """ORM 기반 통합 객체 저장"""
        
        try:
            db_manager = get_db_manager(tenant_id)
            logger.info(f"🔗 DB 매니저 생성: {db_manager.database_url}")
            
            # 테이블 생성 보장
            try:
                # 데이터베이스 생성 (테이블 포함)
                db_manager.create_database()
                logger.info("✅ ORM 테이블 생성/검증 완료")
                
                # IntegratedObject 테이블 존재 확인
                from sqlalchemy import inspect
                inspector = inspect(db_manager.engine)
                existing_tables = inspector.get_table_names()
                
                if 'integrated_objects' not in existing_tables:
                    logger.error("❌ integrated_objects 테이블이 생성되지 않음")
                    # 강제로 IntegratedObject 테이블만 생성
                    from .database.models import IntegratedObject
                    IntegratedObject.__table__.create(bind=db_manager.engine, checkfirst=True)
                    logger.info("🔧 integrated_objects 테이블 강제 생성 완료")
                else:
                    logger.info("✅ integrated_objects 테이블 존재 확인")
                    
            except Exception as table_error:
                logger.error(f"❌ 테이블 생성 실패: {table_error}")
                return False
            
            with db_manager.get_session() as session:
                repo = IntegratedObjectRepository(session)
                
                # 기존 객체 확인
                original_id = str(integrated_object.get('id'))
                object_type = integrated_object.get('object_type', 'integrated_ticket')
                
                logger.info(f"🔍 마이그레이션 저장 정보: original_id={original_id}, object_type={object_type}, tenant_id={tenant_id}, platform={platform}")
                
                existing = repo.get_by_original_id(
                    tenant_id=tenant_id,
                    original_id=original_id,
                    object_type=object_type,
                    platform=platform
                )
                
                # 데이터 준비
                data = {
                    'original_id': original_id,
                    'tenant_id': tenant_id,
                    'platform': platform,
                    'object_type': object_type,
                    'original_data': integrated_object,
                    'integrated_content': integrated_object.get('integrated_text', ''),
                    'summary': integrated_object.get('summary'),
                    'tenant_metadata': self._create_tenant_metadata(integrated_object)
                }
                
                logger.info(f"📋 저장할 데이터: original_id={data['original_id']}, tenant_id={data['tenant_id']}")
                
                if existing:
                    # 업데이트
                    for key, value in data.items():
                        if key != 'id':  # ID는 업데이트하지 않음
                            setattr(existing, key, value)
                    session.flush()  # 세션 플러시
                    result_obj = existing
                else:
                    # 새로 생성
                    created_obj = repo.create(data)
                    session.flush()  # 세션 플러시 (ID 할당 보장)
                    result_obj = created_obj
                    logger.info(f"✅ ORM 통합 객체 생성: {original_id}, DB ID: {created_obj.id}")
                    logger.info(f"🔍 생성된 객체 정보: tenant_id={created_obj.tenant_id}, platform={created_obj.platform}")
                
                # 명시적 커밋
                session.commit()
                logger.info(f"✅ 트랜잭션 커밋 완료: {original_id}")
                
                # 저장 직후 검증
                logger.info("🔍 저장 직후 검증...")
                verification = repo.get_by_original_id(
                    tenant_id=tenant_id,
                    original_id=original_id,
                    object_type=object_type,
                    platform=platform
                )
                
                if verification:
                    logger.info(f"✅ 저장 직후 검증 성공: {verification.id}")
                else:
                    logger.warning("⚠️ 저장 직후 검증 실패 - 객체를 찾을 수 없음")
                    return False
                
                return True
                
        except Exception as e:
            logger.error(f"❌ ORM 저장 실패: {e}")
            return False
    
    def _store_integrated_object_sqlite(
        self, 
        integrated_object: Dict[str, Any], 
        tenant_id: str, 
        platform: str = "freshdesk"
    ) -> bool:
        """기존 SQLite 기반 저장 (호환성 유지)"""
        
        try:
            # 기존 storage.py 함수 호출
            from .ingest.storage import store_integrated_object_to_sqlite
            from .database.database import get_database
            
            db = get_database(tenant_id, platform)
            return store_integrated_object_to_sqlite(db, integrated_object, tenant_id, platform)
            
        except Exception as e:
            logger.error(f"❌ SQLite 저장 실패: {e}")
            return False
    
    def _create_tenant_metadata(self, integrated_object: Dict[str, Any]) -> Dict[str, Any]:
        """메타데이터 생성"""
        
        # 첨부파일 메타데이터
        attachments = integrated_object.get("all_attachments", [])
        attachments_metadata = []
        
        for att in attachments:
            att_meta = {
                'id': att.get('id'),
                'name': att.get('name'),
                'content_type': att.get('content_type'),
                'size': att.get('size'),
                'created_at': att.get('created_at'),
                'conversation_id': att.get('conversation_id'),
            }
            # None 값 제거
            attachments_metadata.append({k: v for k, v in att_meta.items() if v is not None})
        
        # 대화 메타데이터
        conversations = integrated_object.get("conversations", [])
        conversations_metadata = []
        
        for conv in conversations:
            conv_meta = {
                'id': conv.get('id'),
                'body_text': conv.get('body_text', '')[:100] + '...' if conv.get('body_text') else '',
                'from_email': conv.get('from_email'),
                'private': conv.get('private', False),
                'attachments_count': len(conv.get('attachments', []))
            }
            conversations_metadata.append({k: v for k, v in conv_meta.items() if v is not None})
        
        return {
            'has_conversations': bool(conversations),
            'has_attachments': bool(attachments),
            'conversation_count': len(conversations),
            'attachment_count': len(attachments),
            'attachments': attachments_metadata,
            'conversations': conversations_metadata,
            'subject': integrated_object.get('subject'),
            'status': integrated_object.get('status'),
            'priority': integrated_object.get('priority'),
            'created_at': integrated_object.get('created_at'),
            'updated_at': integrated_object.get('updated_at'),
        }


# 전역 마이그레이션 레이어 인스턴스 (지연 생성)
_migration_layer: Optional[MigrationLayer] = None


def get_migration_layer() -> MigrationLayer:
    """마이그레이션 레이어 싱글톤 인스턴스 반환"""
    global _migration_layer
    if _migration_layer is None:
        _migration_layer = MigrationLayer()
    return _migration_layer


def store_integrated_object_with_migration(
    integrated_object: Dict[str, Any], 
    tenant_id: str, 
    platform: str = "freshdesk"
) -> bool:
    """마이그레이션 레이어를 통한 통합 객체 저장"""
    migration_layer = get_migration_layer()
    return migration_layer.store_integrated_object(integrated_object, tenant_id, platform)
