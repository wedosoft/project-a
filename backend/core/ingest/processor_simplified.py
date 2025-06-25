"""
간소화된 요약 생성 함수 - 통합 객체만 사용
"""

import json
import logging
import time
from typing import Dict, Any
from core.llm.summarizer import generate_summary

logger = logging.getLogger(__name__)

def get_kst_time() -> str:
    """현재 시간을 KST로 반환합니다."""
    from datetime import datetime
    import pytz
    kst = pytz.timezone('Asia/Seoul')
    return datetime.now(kst).isoformat()

async def generate_and_store_summaries_simplified(
    company_id: str,
    platform: str = "freshdesk",
    force_update: bool = False
) -> Dict[str, Any]:
    """
    통합 객체에서 직접 요약을 생성하고 저장합니다 (간소화된 버전)
    
    Args:
        company_id: 회사 식별자
        platform: 플랫폼 식별자
        force_update: 기존 요약 강제 업데이트 여부
        
    Returns:
        Dict[str, Any]: 처리 결과
    """
    logger.info(f"간소화된 LLM 요약 생성 시작 (company_id: {company_id}, platform: {platform})")
    start_time = time.time()
    
    result = {
        "success_count": 0,
        "failure_count": 0,
        "skipped_count": 0,
        "total_processed": 0,
        "processing_time": 0,
        "errors": []
    }
    
    # 멀티테넌트 데이터베이스 연결
    from core.database.database import get_database
    db = get_database(company_id, platform)
    
    try:
        cursor = db.connection.cursor()
        
        # 요약이 없는 통합 객체들 조회 (티켓 + KB 문서)
        if force_update:
            # 강제 업데이트: 모든 통합 객체
            cursor.execute("""
                SELECT original_id, object_type, original_data, integrated_content, metadata 
                FROM integrated_objects 
                WHERE company_id = ? AND platform = ? 
                AND object_type IN ('integrated_ticket', 'integrated_article')
                AND integrated_content IS NOT NULL AND integrated_content != ''
            """, (company_id, platform))
        else:
            # 일반 모드: 요약이 없는 것만
            cursor.execute("""
                SELECT original_id, object_type, original_data, integrated_content, metadata 
                FROM integrated_objects 
                WHERE company_id = ? AND platform = ? 
                AND object_type IN ('integrated_ticket', 'integrated_article')
                AND (summary IS NULL OR summary = '')
                AND integrated_content IS NOT NULL AND integrated_content != ''
            """, (company_id, platform))
        
        rows = cursor.fetchall()
        logger.info(f"처리할 통합 객체 수: {len(rows)}개")
        
        for row in rows:
            try:
                original_id, object_type, original_data_str, integrated_content, metadata_str = row
                
                # 디버깅 로그
                logger.debug(f"{object_type} {original_id}: integrated_content 길이 = {len(integrated_content) if integrated_content else 0}")
                
                # 데이터 파싱
                try:
                    original_data = json.loads(original_data_str) if original_data_str else {}
                    metadata = json.loads(metadata_str) if metadata_str else {}
                except json.JSONDecodeError:
                    logger.warning(f"{object_type} {original_id}: 데이터 파싱 실패")
                    original_data = {}
                    metadata = {}
                
                # integrated_content 확인
                if not integrated_content or not integrated_content.strip():
                    logger.warning(f"{object_type} {original_id}: integrated_content가 없거나 비어있음 - 요약 생성 불가")
                    result["skipped_count"] += 1
                    continue

                # 객체 타입에 따른 요약 생성
                if object_type == 'integrated_ticket':
                    # 티켓 요약 생성
                    content_type = "ticket"
                    subject = original_data.get('subject', '')
                    
                    # 첨부파일 정보 추가
                    ticket_metadata = {
                        'status': original_data.get('status', ''),
                        'priority': original_data.get('priority', ''),
                        'created_at': original_data.get('created_at', ''),
                        'ticket_id': original_id
                    }
                    
                    # DB에서 첨부파일 정보 가져오기
                    attachments = db.get_attachments_by_ticket(original_id)
                    if attachments:
                        ticket_metadata['attachments'] = [
                            {
                                'id': att.get('attachment_id'),
                                'name': att.get('name'),
                                'content_type': att.get('content_type'),
                                'size': att.get('size'),
                                'ticket_id': original_id,
                                'conversation_id': att.get('conversation_id'),
                                'attachment_url': att.get('download_url')
                            }
                            for att in attachments
                        ]
                        logger.debug(f"티켓 {original_id}: 첨부파일 메타데이터 설정 완료 - {len(ticket_metadata['attachments'])}개")
                    else:
                        ticket_metadata['attachments'] = []
                    
                    summary_metadata = ticket_metadata
                    
                elif object_type == 'integrated_article':
                    # KB 문서 요약 생성
                    content_type = "knowledge_base"
                    subject = original_data.get('title', '')
                    
                    summary_metadata = {
                        'status': original_data.get('status', ''),
                        'category_id': original_data.get('category_id', ''),
                        'created_at': original_data.get('created_at', '')
                    }
                else:
                    logger.warning(f"알 수 없는 객체 타입: {object_type}")
                    result["skipped_count"] += 1
                    continue

                # LLM 요약 생성
                summary = await generate_summary(
                    content=integrated_content,
                    content_type=content_type,
                    subject=subject,
                    metadata=summary_metadata
                )
                
                # 요약만 업데이트 (기존 데이터는 보존)
                cursor.execute("""
                    UPDATE integrated_objects 
                    SET summary = ? 
                    WHERE company_id = ? AND platform = ? AND object_type = ? AND original_id = ?
                """, (summary, company_id, platform, object_type, original_id))
                db.connection.commit()
                
                result["success_count"] += 1
                logger.debug(f"{object_type} {original_id}: 요약 생성 및 저장 완료")
                
            except Exception as e:
                logger.error(f"{object_type} {original_id} 요약 생성 중 오류: {e}")
                result["failure_count"] += 1
                result["errors"].append(f"{object_type} {original_id}: {str(e)}")
        
        result["total_processed"] = result["success_count"] + result["failure_count"] + result["skipped_count"]
        result["processing_time"] = time.time() - start_time
        
        logger.info(f"✅ 간소화된 LLM 요약 생성 완료:")
        logger.info(f"  - 성공: {result['success_count']}")
        logger.info(f"  - 실패: {result['failure_count']}")
        logger.info(f"  - 건너뜀: {result['skipped_count']}")
        logger.info(f"  - 총 처리: {result['total_processed']}")
        logger.info(f"  - 소요 시간: {result['processing_time']:.2f}초")
        
        return result
        
    except Exception as e:
        logger.error(f"간소화된 LLM 요약 생성 중 오류 발생: {e}")
        result["errors"].append(str(e))
        result["processing_time"] = time.time() - start_time
        raise
    finally:
        db.disconnect()
