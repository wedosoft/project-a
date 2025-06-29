#!/usr/bin/env python3
"""
개선된 메타데이터 시스템 테스트

새로운 integrator.py의 메타데이터 추출 기능을 테스트
"""

import os
import sys
import json
import logging
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

# 환경변수 로드
from dotenv import load_dotenv
load_dotenv(dotenv_path=os.path.join(backend_dir, ".env"))

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_sample_ticket_data():
    """테스트용 샘플 티켓 데이터 생성"""
    
    return {
        "id": 12345,
        "subject": "결제 시스템 오류 문의",
        "description_text": "결제 진행 시 오류가 발생하여 문의드립니다. 카드 결제가 되지 않아 주문을 완료할 수 없습니다.",
        "status": 2,
        "status_name": "Open",
        "priority": 3,
        "priority_name": "High",
        "type": "incident",
        "created_at": "2025-06-28T14:00:00Z",
        "updated_at": "2025-06-28T14:30:00Z",
        "company": {
            "id": 567,
            "name": "ABC 쇼핑몰"
        },
        "responder": {
            "id": 789,
            "name": "김지원",
            "email": "jiwon.kim@company.com"
        },
        "requester": {
            "id": 101112,
            "name": "이고객",
            "email": "customer@abc-shop.com"
        },
        "group": {
            "id": 13,
            "name": "기술지원팀"
        },
        "product": {
            "id": 14,
            "name": "결제시스템"
        }
    }

def create_sample_conversations():
    """테스트용 샘플 대화 데이터 생성"""
    
    return [
        {
            "id": 1001,
            "body_text": "안녕하세요. 결제 오류 관련하여 확인해드리겠습니다. 어떤 카드를 사용하셨나요?",
            "user_id": 789,
            "created_at": "2025-06-28T14:05:00Z"
        },
        {
            "id": 1002, 
            "body_text": "신한카드 체크카드를 사용했습니다. 여러 번 시도했지만 계속 오류가 발생합니다.",
            "user_id": 101112,
            "created_at": "2025-06-28T14:10:00Z"
        },
        {
            "id": 1003,
            "body_text": "카드사에 확인해본 결과 한도는 충분합니다. 시스템 오류인 것 같습니다.",
            "user_id": 101112,
            "created_at": "2025-06-28T14:15:00Z"
        }
    ]

def create_sample_attachments():
    """테스트용 샘플 첨부파일 데이터 생성"""
    
    return [
        {
            "id": 2001,
            "name": "payment_error_screenshot.png",
            "content_type": "image/png",
            "size": 245760,
            "ticket_id": 12345
        },
        {
            "id": 2002,
            "name": "error_log.txt", 
            "content_type": "text/plain",
            "size": 1024,
            "conversation_id": 1002
        }
    ]

def create_sample_article_data():
    """테스트용 샘플 KB 문서 데이터 생성"""
    
    return {
        "id": 98765,
        "title": "결제 오류 해결 가이드",
        "description_text": "고객이 결제 진행 시 발생할 수 있는 다양한 오류와 해결 방법을 안내합니다. 1. 카드 정보 확인 2. 브라우저 캐시 삭제 3. 다른 결제 수단 시도",
        "status": 2,
        "status_name": "Published",
        "type": "permanent",
        "created_at": "2025-06-01T09:00:00Z",
        "updated_at": "2025-06-25T16:30:00Z",
        "category": {
            "id": 21,
            "name": "결제/주문"
        },
        "folder": {
            "id": 22,
            "name": "FAQ"
        },
        "agent": {
            "id": 789,
            "name": "김지원",
            "email": "jiwon.kim@company.com"
        },
        "hits": 1250,
        "thumbs_up": 45,
        "thumbs_down": 3,
        "tags": ["결제", "오류", "FAQ"]
    }

def test_ticket_metadata_extraction():
    """티켓 메타데이터 추출 테스트"""
    
    logger.info("=== 티켓 메타데이터 추출 테스트 ===")
    
    try:
        from core.ingest.integrator import create_integrated_ticket_object
        
        # 샘플 데이터 준비
        ticket = create_sample_ticket_data()
        conversations = create_sample_conversations()
        attachments = create_sample_attachments()
        tenant_id = "test_company"
        
        # 통합 객체 생성
        integrated_object = create_integrated_ticket_object(
            ticket=ticket,
            conversations=conversations,
            attachments=attachments,
            tenant_id=tenant_id
        )
        
        # 메타데이터 확인
        metadata = integrated_object.get("metadata", {})
        
        logger.info("📊 추출된 메타데이터:")
        for key, value in metadata.items():
            logger.info(f"  {key}: {value}")
        
        # 중요 필드 검증
        essential_fields = [
            "tenant_id", "platform", "doc_type", "original_id",
            "subject", "status", "priority", "company_name", 
            "agent_name", "customer_email", "complexity_level"
        ]
        
        missing_fields = [field for field in essential_fields if field not in metadata]
        
        if missing_fields:
            logger.warning(f"⚠️ 누락된 필수 필드: {missing_fields}")
            return False
        else:
            logger.info("✅ 모든 필수 필드가 추출되었습니다")
        
        # 통계 확인
        logger.info(f"📈 통계 정보:")
        logger.info(f"  대화 수: {metadata.get('conversation_count')}")
        logger.info(f"  첨부파일 수: {metadata.get('attachment_count')}")
        logger.info(f"  복잡도: {metadata.get('complexity_level')}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 티켓 메타데이터 추출 실패: {e}")
        return False

def test_article_metadata_extraction():
    """KB 문서 메타데이터 추출 테스트"""
    
    logger.info("\n=== KB 문서 메타데이터 추출 테스트 ===")
    
    try:
        from core.ingest.integrator import create_integrated_article_object
        
        # 샘플 데이터 준비
        article = create_sample_article_data()
        tenant_id = "test_company"
        
        # 통합 객체 생성
        integrated_object = create_integrated_article_object(
            article=article,
            tenant_id=tenant_id
        )
        
        # 메타데이터 확인
        metadata = integrated_object.get("metadata", {})
        
        logger.info("📊 추출된 메타데이터:")
        for key, value in metadata.items():
            logger.info(f"  {key}: {value}")
        
        # 문서 전용 필드 검증
        article_fields = [
            "category", "folder", "view_count", 
            "thumbs_up", "thumbs_down", "content_length"
        ]
        
        logger.info(f"📚 문서 전용 정보:")
        for field in article_fields:
            if field in metadata:
                logger.info(f"  {field}: {metadata[field]}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ KB 문서 메타데이터 추출 실패: {e}")
        return False

def test_metadata_validation():
    """메타데이터 검증 테스트"""
    
    logger.info("\n=== 메타데이터 검증 테스트 ===")
    
    try:
        from cleanup_vector_metadata import clean_and_validate_metadata, upgrade_metadata_schema
        
        # 불완전한 메타데이터 샘플
        incomplete_metadata = {
            "tenant_id": "test",
            "original_id": "12345",
            "subject": "",  # 빈 값
            "status": None,  # null 값
            "conversation_count": "5",  # 잘못된 타입
            # 누락된 필드들...
        }
        
        logger.info("📋 원본 메타데이터:")
        logger.info(json.dumps(incomplete_metadata, indent=2, ensure_ascii=False))
        
        # 정리 및 검증
        cleaned_metadata = clean_and_validate_metadata(incomplete_metadata.copy())
        
        logger.info("\n🧹 정리된 메타데이터:")
        logger.info(json.dumps(cleaned_metadata, indent=2, ensure_ascii=False))
        
        # 스키마 업그레이드 테스트
        upgraded_metadata = upgrade_metadata_schema(incomplete_metadata.copy())
        
        logger.info("\n⬆️ 업그레이드된 메타데이터:")
        logger.info(json.dumps(upgraded_metadata, indent=2, ensure_ascii=False))
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 메타데이터 검증 실패: {e}")
        return False

def main():
    """메인 테스트 실행"""
    
    logger.info("🧪 개선된 메타데이터 시스템 테스트 시작")
    
    results = []
    
    # 테스트 실행
    results.append(("티켓 메타데이터 추출", test_ticket_metadata_extraction()))
    results.append(("KB 문서 메타데이터 추출", test_article_metadata_extraction()))
    results.append(("메타데이터 검증", test_metadata_validation()))
    
    # 결과 요약
    logger.info("\n=== 테스트 결과 요약 ===")
    for test_name, success in results:
        status = "✅ 성공" if success else "❌ 실패"
        logger.info(f"{test_name}: {status}")
    
    # 전체 결과
    all_passed = all(result[1] for result in results)
    if all_passed:
        logger.info("🎉 모든 테스트 통과! 메타데이터 추출 시스템이 개선되었습니다.")
    else:
        logger.warning("⚠️ 일부 테스트 실패")
    
    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
