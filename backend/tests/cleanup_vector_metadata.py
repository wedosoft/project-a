#!/usr/bin/env python3
"""
메타데이터 정리 및 재처리 도구

기존 벡터 DB의 메타데이터를 개선된 버전으로 업데이트
"""

import os
import sys
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional

# 프로젝트 루트를 Python 경로에 추가
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

# 환경변수 로드
from dotenv import load_dotenv
load_dotenv(dotenv_path=os.path.join(backend_dir, ".env"))

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def clean_and_validate_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """메타데이터 정리 및 검증"""
    
    # 필수 필드 확인 및 기본값 설정
    required_fields = {
        "tenant_id": "unknown",
        "platform": "freshdesk", 
        "doc_type": "unknown",
        "original_id": "",
        "subject": "제목 없음",
        "status": "unknown",
        "priority": "normal",
        "created_at": "",
        "updated_at": "",
        "company_name": "",
        "agent_name": "",
        "customer_email": "",
        "complexity_level": "simple"
    }
    
    # 기본값으로 누락된 필드 채우기
    for field, default_value in required_fields.items():
        if field not in metadata or metadata[field] is None:
            metadata[field] = default_value
        elif metadata[field] == "":
            metadata[field] = default_value
    
    # 데이터 타입 정규화
    if "conversation_count" in metadata:
        metadata["conversation_count"] = int(metadata.get("conversation_count", 0))
    
    if "attachment_count" in metadata:
        metadata["attachment_count"] = int(metadata.get("attachment_count", 0))
    
    # boolean 필드 정리
    boolean_fields = ["has_conversations", "has_attachments", "is_detailed"]
    for field in boolean_fields:
        if field in metadata:
            metadata[field] = bool(metadata[field])
    
    # 문자열 필드 정리 (공백 제거)
    string_fields = ["subject", "company_name", "agent_name", "customer_email"]
    for field in string_fields:
        if field in metadata and isinstance(metadata[field], str):
            metadata[field] = metadata[field].strip()
    
    return metadata

def upgrade_metadata_schema(old_metadata: Dict[str, Any]) -> Dict[str, Any]:
    """기존 메타데이터를 새로운 스키마로 업그레이드"""
    
    upgraded = {}
    
    # 기존 필드 매핑
    field_mapping = {
        # 기본 필드 유지
        "tenant_id": "tenant_id",
        "platform": "platform", 
        "doc_type": "doc_type",
        "original_id": "original_id",
        
        # 기존 필드 변환
        "id": "original_id",
        "subject": "subject",
        "status": "status",
        "priority": "priority",
        "created_at": "created_at",
        "updated_at": "updated_at",
        
        # 통계 필드
        "conversation_count": "conversation_count",
        "attachment_count": "attachment_count"
    }
    
    # 매핑된 필드 복사
    for old_field, new_field in field_mapping.items():
        if old_field in old_metadata:
            upgraded[new_field] = old_metadata[old_field]
    
    # 누락된 필드는 기본값으로 설정
    defaults = {
        "company_name": "",
        "agent_name": "",
        "customer_email": "",
        "complexity_level": "simple",
        "has_conversations": False,
        "has_attachments": False
    }
    
    for field, default_value in defaults.items():
        if field not in upgraded:
            upgraded[field] = default_value
    
    return clean_and_validate_metadata(upgraded)

def batch_update_vector_metadata(limit: int = 100):
    """벡터 DB의 메타데이터를 일괄 업데이트"""
    
    try:
        from core.database.vectordb import vector_db
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        
        logger.info(f"=== 메타데이터 일괄 업데이트 시작 (최대 {limit}개) ===")
        
        # 기존 포인트들 조회
        scroll_result = vector_db.client.scroll(
            collection_name=vector_db.collection_name,
            limit=limit,
            with_payload=True,
            with_vectors=False
        )
        
        points = scroll_result[0] if scroll_result else []
        logger.info(f"업데이트 대상: {len(points)}개 문서")
        
        updated_count = 0
        error_count = 0
        
        for point in points:
            try:
                point_id = point.id
                old_metadata = point.payload if hasattr(point, 'payload') else {}
                
                # 메타데이터 업그레이드
                new_metadata = upgrade_metadata_schema(old_metadata)
                
                # 변경사항이 있는지 확인
                if new_metadata != old_metadata:
                    # 메타데이터 업데이트
                    vector_db.client.set_payload(
                        collection_name=vector_db.collection_name,
                        points=[point_id],
                        payload=new_metadata
                    )
                    updated_count += 1
                    
                    if updated_count % 10 == 0:
                        logger.info(f"진행률: {updated_count}/{len(points)} 업데이트 완료")
                
            except Exception as e:
                logger.error(f"포인트 {point.id} 업데이트 실패: {e}")
                error_count += 1
        
        logger.info(f"✅ 메타데이터 업데이트 완료")
        logger.info(f"  업데이트됨: {updated_count}개")
        logger.info(f"  실패: {error_count}개")
        
        return {"updated": updated_count, "errors": error_count}
        
    except Exception as e:
        logger.error(f"❌ 일괄 업데이트 실패: {e}")
        return None

def validate_metadata_consistency():
    """메타데이터 일관성 검증"""
    
    try:
        from core.database.vectordb import vector_db
        
        logger.info("=== 메타데이터 일관성 검증 ===")
        
        # 샘플 검증
        scroll_result = vector_db.client.scroll(
            collection_name=vector_db.collection_name,
            limit=20,
            with_payload=True,
            with_vectors=False
        )
        
        points = scroll_result[0] if scroll_result else []
        
        validation_results = {
            "total_checked": len(points),
            "missing_required": 0,
            "invalid_types": 0,
            "empty_values": 0,
            "valid_count": 0
        }
        
        required_fields = ["tenant_id", "platform", "doc_type", "original_id"]
        
        for point in points:
            metadata = point.payload if hasattr(point, 'payload') else {}
            is_valid = True
            
            # 필수 필드 확인
            for field in required_fields:
                if field not in metadata or not metadata[field]:
                    validation_results["missing_required"] += 1
                    is_valid = False
                    break
            
            # 데이터 타입 확인
            if "conversation_count" in metadata:
                if not isinstance(metadata["conversation_count"], int):
                    validation_results["invalid_types"] += 1
                    is_valid = False
            
            # 빈 값 확인
            empty_count = sum(1 for v in metadata.values() if v == "" or v is None)
            if empty_count > len(metadata) * 0.5:  # 50% 이상이 비어있으면
                validation_results["empty_values"] += 1
                is_valid = False
            
            if is_valid:
                validation_results["valid_count"] += 1
        
        logger.info(f"검증 결과:")
        logger.info(f"  총 확인: {validation_results['total_checked']}개")
        logger.info(f"  유효: {validation_results['valid_count']}개")
        logger.info(f"  필수 필드 누락: {validation_results['missing_required']}개")
        logger.info(f"  타입 오류: {validation_results['invalid_types']}개")
        logger.info(f"  빈 값 과다: {validation_results['empty_values']}개")
        
        return validation_results
        
    except Exception as e:
        logger.error(f"❌ 일관성 검증 실패: {e}")
        return None

def main():
    """메인 실행 함수"""
    
    logger.info("🔧 벡터 DB 메타데이터 정리 도구 시작")
    
    # 1. 업데이트 전 분석
    logger.info("1️⃣ 업데이트 전 메타데이터 분석")
    from analyze_vector_metadata import analyze_vector_metadata
    before_analysis = analyze_vector_metadata()
    
    if not before_analysis:
        logger.error("❌ 분석 실패로 업데이트를 중단합니다")
        return False
    
    # 2. 메타데이터 업데이트
    logger.info("\n2️⃣ 메타데이터 일괄 업데이트")
    update_result = batch_update_vector_metadata(limit=50)
    
    if not update_result:
        logger.error("❌ 업데이트 실패")
        return False
    
    # 3. 일관성 검증
    logger.info("\n3️⃣ 업데이트 후 일관성 검증")
    validation_result = validate_metadata_consistency()
    
    # 4. 결과 요약
    logger.info("\n=== 메타데이터 정리 결과 요약 ===")
    logger.info(f"📊 업데이트 전 문서 수: {before_analysis['total_documents']}")
    logger.info(f"🔧 업데이트된 문서: {update_result['updated']}개")
    logger.info(f"❌ 실패: {update_result['errors']}개")
    
    if validation_result:
        logger.info(f"✅ 검증 통과: {validation_result['valid_count']}/{validation_result['total_checked']}")
    
    logger.info("🎉 메타데이터 정리 완료!")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
