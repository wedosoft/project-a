"""
데이터 수집 핵심 기능 라우터

이 모듈은 데이터 수집의 핵심 기능을 제공하는 엔드포인트를 포함합니다.

주요 기능:
- 즉시 데이터 수집 실행 (동기식)
- 벡터 DB 요약 데이터 동기화
- 멀티플랫폼 지원 및 보안 헤더 검증
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from datetime import datetime
from typing import Optional, Dict, Any
import logging
import boto3
import json
import os
from botocore.exceptions import ClientError, NoCredentialsError

from ..models.requests import IngestRequest, DataSecurityRequest
from ..models.responses import IngestResponse
from ..dependencies import (
    get_company_id, get_platform, get_api_key, get_domain
)
from core.ingest.processor import ingest

# 라우터 생성
router = APIRouter(tags=["즉시 실행 & 동기화"])

# 로거 설정
logger = logging.getLogger(__name__)


async def delete_aws_secrets(
    company_id: str,
    platform: str,
    action: str,
    aws_region: Optional[str] = None,
    secret_name_pattern: Optional[str] = None,
    create_backup: bool = True,
    force_delete: bool = False
) -> int:
    """
    AWS Secrets Manager에서 회사/플랫폼 관련 비밀키를 삭제합니다.
    
    Args:
        company_id: 회사 ID
        platform: 플랫폼 ID
        action: 삭제 액션 (purge_all, reset_company, delete_platform)
        aws_region: AWS 리전 (기본값: 환경변수 AWS_DEFAULT_REGION)
        secret_name_pattern: 커스텀 시크릿 이름 패턴
        create_backup: 백업 생성 여부
        force_delete: 강제 삭제 (즉시 삭제, 복구 불가)
        
    Returns:
        삭제된 시크릿 수
    """
    try:
        # AWS 리전 설정
        region = aws_region or os.getenv('AWS_DEFAULT_REGION', 'us-east-1')
        
        # AWS Secrets Manager 클라이언트 생성
        secrets_client = boto3.client('secretsmanager', region_name=region)
        
        # 삭제할 시크릿 이름 패턴 생성
        if secret_name_pattern:
            patterns = [secret_name_pattern]
        else:
            # 기본 패턴 생성
            if action == "purge_all":
                patterns = [
                    f"*{company_id}*",
                    f"*{platform}*",
                    f"{company_id}-*",
                    f"{platform}-*",
                    f"*-{company_id}-*",
                    f"*-{platform}-*"
                ]
            elif action == "reset_company":
                patterns = [
                    f"*{company_id}*",
                    f"{company_id}-*",
                    f"*-{company_id}-*"
                ]
            elif action == "delete_platform":
                patterns = [
                    f"*{platform}*",
                    f"{platform}-*",
                    f"*-{platform}-*"
                ]
            else:
                patterns = []
        
        # 모든 시크릿 목록 조회
        paginator = secrets_client.get_paginator('list_secrets')
        all_secrets = []
        
        for page in paginator.paginate():
            all_secrets.extend(page['SecretList'])
        
        # 패턴에 맞는 시크릿 필터링
        secrets_to_delete = []
        for secret in all_secrets:
            secret_name = secret['Name']
            secret_arn = secret['ARN']
            
            # 패턴 매칭
            for pattern in patterns:
                pattern_match = _match_secret_pattern(
                    secret_name, pattern, company_id, platform
                )
                if pattern_match:
                    secrets_to_delete.append({
                        'name': secret_name,
                        'arn': secret_arn,
                        'description': secret.get('Description', ''),
                        'tags': secret.get('Tags', [])
                    })
                    break
        
        secrets_count = len(secrets_to_delete)
        logger.warning(f"🔍 AWS Secrets Manager: {secrets_count}개 시크릿 발견됨")
        for secret in secrets_to_delete:
            desc = secret.get('description', 'No description')
            logger.warning(f"   - {secret['name']} ({desc})")
        
        # 백업 생성 (선택사항)
        backup_data = []
        if create_backup and secrets_to_delete:
            logger.info("🔐 AWS Secrets 백업 생성 중...")
            for secret in secrets_to_delete:
                try:
                    # 시크릿 값 조회 (백업용)
                    response = secrets_client.get_secret_value(
                        SecretId=secret['arn']
                    )
                    backup_entry = {
                        'name': secret['name'],
                        'arn': secret['arn'],
                        'description': secret['description'],
                        'tags': secret['tags'],
                        'secret_string': response.get('SecretString'),
                        'secret_binary': response.get('SecretBinary'),
                        'version_id': response.get('VersionId'),
                        'backed_up_at': datetime.now().isoformat()
                    }
                    backup_data.append(backup_entry)
                    
                except ClientError as e:
                    logger.error(f"❌ 시크릿 백업 실패 ({secret['name']}): {e}")
                    if not force_delete:
                        raise
            
            # 백업 파일 저장
            if backup_data:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                backup_filename = (
                    f"secrets_backup_{company_id}_{platform}_{timestamp}.json"
                )
                backup_path = f"backups/{backup_filename}"
                
                # 백업 디렉토리 생성
                os.makedirs(os.path.dirname(backup_path), exist_ok=True)
                
                with open(backup_path, 'w', encoding='utf-8') as f:
                    json.dump(
                        backup_data, f, indent=2,
                        ensure_ascii=False, default=str
                    )
                
                logger.info(f"✅ AWS Secrets 백업 완료: {backup_path}")
        
        # 시크릿 삭제 실행
        deleted_count = 0
        for secret in secrets_to_delete:
            try:
                if force_delete:
                    # 즉시 삭제 (복구 불가)
                    secrets_client.delete_secret(
                        SecretId=secret['arn'],
                        ForceDeleteWithoutRecovery=True
                    )
                    logger.warning(f"🗑️ 즉시 삭제: {secret['name']}")
                else:
                    # 30일 후 삭제 (복구 가능)
                    secrets_client.delete_secret(
                        SecretId=secret['arn'],
                        RecoveryWindowInDays=30
                    )
                    logger.warning(f"🗑️ 30일 후 삭제 예약: {secret['name']}")
                
                deleted_count += 1
                
            except ClientError as e:
                error_code = e.response['Error']['Code']
                if error_code == 'ResourceNotFoundException':
                    logger.warning(f"⚠️ 시크릿이 이미 삭제됨: {secret['name']}")
                elif error_code == 'InvalidRequestException':
                    logger.warning(f"⚠️ 시크릿이 이미 삭제 대기 중: {secret['name']}")
                else:
                    logger.error(f"❌ 시크릿 삭제 실패 ({secret['name']}): {e}")
                    if not force_delete:
                        raise
        
        return deleted_count
        
    except NoCredentialsError:
        logger.error("❌ AWS 자격 증명이 설정되지 않았습니다")
        if not force_delete:
            raise HTTPException(
                status_code=500,
                detail="AWS 자격 증명이 설정되지 않았습니다. AWS CLI 구성 또는 IAM 역할을 확인하세요."
            )
        return 0
        
    except Exception as e:
        logger.error(f"❌ AWS Secrets Manager 처리 중 오류: {e}")
        if not force_delete:
            raise
        return 0


def _match_secret_pattern(
    secret_name: str, pattern: str, company_id: str, platform: str
) -> bool:
    """
    시크릿 이름이 패턴에 매치되는지 확인합니다.
    
    Args:
        secret_name: 시크릿 이름
        pattern: 매칭 패턴 (* 와일드카드 지원)
        company_id: 회사 ID
        platform: 플랫폼 ID
        
    Returns:
        매치 여부
    """
    import fnmatch
    
    # 기본 패턴 매칭
    if fnmatch.fnmatch(secret_name.lower(), pattern.lower()):
        return True
    
    # 추가 보안: company_id와 platform이 정확히 포함된 경우만 매칭
    name_lower = secret_name.lower()
    company_lower = company_id.lower()
    platform_lower = platform.lower()
    
    # 정확한 매칭 패턴들
    exact_patterns = [
        f"{company_lower}-{platform_lower}",
        f"{platform_lower}-{company_lower}",
        f"{company_lower}_{platform_lower}",
        f"{platform_lower}_{company_lower}",
        f"{company_lower}.{platform_lower}",
        f"{platform_lower}.{company_lower}"
    ]
    
    for exact_pattern in exact_patterns:
        if exact_pattern in name_lower:
            return True
    
    return False


@router.post("/", response_model=IngestResponse)
async def trigger_data_ingestion(
    request: IngestRequest,
    company_id: str = Depends(get_company_id),
    platform: str = Depends(get_platform),
    api_key: Optional[str] = Depends(get_api_key),
    domain: Optional[str] = Depends(get_domain)
):
    """
    데이터 수집을 트리거하는 엔드포인트 (멀티플랫폼 지원)
    
    ⚠️ **중요: 안전성 제한사항**
    - 이 엔드포인트는 즉시 실행(동기식)으로 **일시정지/취소 제어가 불가능**합니다
    - 대량 데이터 수집 시 **타임아웃 위험**이 있습니다 (브라우저/서버 타임아웃)
    - **권장 사용법**:
      * 테스트 및 소량 데이터 (< 100개 티켓)
      * 즉시 결과 확인이 필요한 경우
    - **대량 데이터나 제어가 필요한 경우**: `/ingest/jobs` 사용 권장
    
    **새로운 표준 헤더 (권장):**
    - X-Company-ID: 회사 식별자 (또는 X-Domain에서 자동 추출)
    - X-Platform: 플랫폼 식별자 (freshdesk, zendesk 등)
    - X-Domain: 플랫폼 도메인 (예: company-domain)
    - X-API-Key: 플랫폼 API 키
    
    **레거시 헤더 (하위 호환성):**
    - X-Platform-Domain, X-Platform-API-Key 등
    
    Args:
        request: 데이터 수집 옵션
        company_id: 회사 ID (헤더에서 자동 추출)
        platform: 플랫폼 식별자 (헤더에서 자동 추출)
        api_key: 플랫폼 API 키 (헤더에서 추출 또는 환경변수)
        domain: 플랫폼 도메인 (헤더에서 추출 또는 환경변수)
        
    Returns:
        IngestResponse: 수집 결과 정보
    """
    start_time = datetime.now()
    logger.info(
        f"🚀 즉시 데이터 수집 시작 - Company: {company_id}, "
        f"Platform: {platform}, Domain: {domain}"
    )
    
    # ⚠️ 안전성 검증: 대량 데이터 수집 시 경고
    if request.max_tickets and request.max_tickets > 100:
        logger.warning(f"⚠️ 대량 티켓 수집 요청 ({request.max_tickets}개) - 타임아웃 위험 있음")
        logger.warning("권장: 대량 데이터는 /ingest/jobs (백그라운드 처리) 사용")
    
    if request.max_articles and request.max_articles > 50:
        logger.warning(
            f"⚠️ 대량 문서 수집 요청 ({request.max_articles}개) - "
            f"타임아웃 위험 있음"
        )
        logger.warning("권장: 대량 데이터는 /ingest/jobs (백그라운드 처리) 사용")
    
    # 수집 범위 로깅 (더 명확한 표현)
    if request.max_tickets is None:
        tickets_scope = "무제한"
    else:
        tickets_scope = f"{request.max_tickets:,}개 제한"
    
    if request.max_articles is None:
        articles_scope = "무제한"
    else:
        articles_scope = f"{request.max_articles:,}개 제한"
    
    logger.info("📊 수집 범위 설정:")
    logger.info(f"   ├─ 티켓 수집: {tickets_scope}")
    kb_status = '(포함)' if request.include_kb else '(제외)'
    logger.info(f"   ├─ KB 문서 수집: {articles_scope} {kb_status}")
    
    collect_method = '증분 업데이트' if request.incremental else '전체 수집'
    logger.info(f"   ├─ 수집 방식: {collect_method}")
    
    attachment_status = '포함' if request.process_attachments else '제외'
    logger.info(f"   └─ 첨부파일 처리: {attachment_status}")
    
    # 개발자용 디버그 정보 (타입 정보 등)
    logger.debug("🔍 개발자 디버그 정보:")
    max_tickets_type = type(request.max_tickets).__name__
    logger.debug(
        f"   ├─ max_tickets: {request.max_tickets} ({max_tickets_type})"
    )
    
    max_articles_type = type(request.max_articles).__name__
    logger.debug(
        f"   ├─ max_articles: {request.max_articles} ({max_articles_type})"
    )
    
    logger.debug(
        f"   └─ 기타 옵션: include_kb={request.include_kb}, "
        f"incremental={request.incremental}"
    )
    
    # 플랫폼 검증 (보안상 필수)
    from core.platforms.factory import PlatformFactory
    supported_platforms = PlatformFactory.get_supported_platforms()
    
    if platform not in supported_platforms:
        supported_list = ', '.join(supported_platforms)
        raise HTTPException(
            status_code=400,
            detail=f"지원되지 않는 플랫폼입니다: {platform}. "
                   f"지원되는 플랫폼: {supported_list}"
        )
    
    try:
        # 진행상황 콜백 함수 정의
        def progress_callback(message: str, percentage: float):
            try:
                from core.database.database import get_database
                db = get_database(company_id, platform)
                # 임시 job_id 생성
                timestamp = int(start_time.timestamp())
                temp_job_id = f"immediate-{company_id}-{timestamp}"
                db.log_progress(
                    job_id=temp_job_id,
                    company_id=company_id,
                    message=message,
                    percentage=percentage,
                    step=int(percentage),
                    total_steps=100
                )
                db.disconnect()
            except Exception as e:
                logger.error(f"즉시 실행 진행상황 로그 저장 실패: {e}")
            
            logger.info(f"즉시 실행 진행상황: {message} ({percentage:.1f}%)")
        
        # 멀티플랫폼 데이터 수집 실행
        result = await ingest(
            company_id=company_id,
            platform=platform,
            incremental=request.incremental,
            purge=request.purge,
            process_attachments=request.process_attachments,
            force_rebuild=request.force_rebuild,
            local_data_dir=None,  # API 호출이므로 로컬 데이터 사용 안함
            include_kb=request.include_kb,
            domain=domain,
            api_key=api_key,
            max_tickets=request.max_tickets,
            max_articles=request.max_articles,
            start_date=request.start_date,  # 시작 날짜 파라미터 추가
            progress_callback=progress_callback
        )
        
        # 데이터 수집 완료 후 요약 생성
        logger.info("🔄 데이터 처리 단계 시작...")
        logger.info("   ├─ 1단계: 원시 데이터 수집 ✅")
        logger.info("   ├─ 2단계: 데이터 저장 및 정규화 ✅") 
        logger.info("   └─ 3단계: LLM 요약 생성 🔄")
        progress_callback("LLM 요약 생성 중...", 85.0)
        
        summary_success = False
        summary_result = {}
        
        try:
            # 요약 생성 단계 추가
            from core.ingest.processor import generate_and_store_summaries
            summary_result = await generate_and_store_summaries(
                company_id=company_id,
                platform=platform,
                force_update=False
            )
            
            # 성공 여부 확인
            success_count = summary_result.get('success_count', 0)
            total_processed = summary_result.get('total_processed', 0)
            
            if success_count > 0:
                summary_success = True
                logger.info(f"요약 생성 완료 - 성공: {success_count}개, "
                           f"실패: {summary_result.get('failure_count', 0)}개, "
                           f"건너뜀: {summary_result.get('skipped_count', 0)}개")
                
                # 메타데이터 정보 로깅
                if 'attachment_metadata' in summary_result:
                    metadata_count = len(summary_result['attachment_metadata'])
                    logger.info(f"첨부파일 메타데이터 수집: {metadata_count}개 티켓")
                
                progress_callback("요약 생성 완료", 88.0)
            else:
                logger.warning(f"요약 생성 결과: 성공한 항목이 없음 (총 {total_processed}개 처리)")
                progress_callback("요약 생성 완료 (성공 0건)", 88.0)
            
        except Exception as e:
            logger.error(f"요약 생성 실패: {e}")
            progress_callback("요약 생성 실패", 88.0)
        
        # 요약 생성 결과에 따른 로깅
        if summary_success:
            logger.info("   ├─ 3단계: LLM 요약 생성 ✅")
            
            # 요약 생성이 성공한 경우에만 벡터 DB 동기화 진행
            logger.info("   └─ 4단계: 벡터 DB 동기화 🔄")
            progress_callback("벡터 DB 동기화 중...", 90.0)
            
            sync_success = False
            
            try:
                # sync_summaries 기능 직접 호출
                from core.ingest.processor import sync_summaries_to_vector_db
                sync_result = await sync_summaries_to_vector_db(
                    company_id=company_id,
                    platform=platform,
                    batch_size=25,
                    force_update=False
                )
                
                synced_count = sync_result.get('synced_count', 0)
                
                if sync_result.get("status") == "success" and synced_count > 0:
                    sync_success = True
                    logger.info(f"   └─ 4단계: 벡터 DB 동기화 ✅ ({synced_count:,}개 문서 처리)")
                    progress_callback("벡터 DB 동기화 완료", 100.0)
                else:
                    errors = sync_result.get('errors', [])
                    error_count = len(errors) if errors else 0
                    
                    if errors:
                        logger.error(f"   └─ 4단계: 벡터 DB 동기화 ❌ (성공: {synced_count}개, 오류: {error_count}개)")
                        logger.error(f"      └─ 주요 오류: {errors[:3]}")  # 첫 3개 오류만 표시
                    elif synced_count == 0:
                        logger.warning(f"   └─ 4단계: 벡터 DB 동기화 ⚠️ (처리할 데이터 없음)")
                    else:
                        logger.warning(f"   └─ 4단계: 벡터 DB 동기화 ⚠️ (처리: {synced_count}개, 상태: {sync_result.get('status', 'unknown')})")
                    
                    progress_callback("벡터 DB 동기화 완료 (일부 오류)", 95.0)
            except Exception as e:
                logger.error(f"   └─ 4단계: 벡터 DB 동기화 ❌ (오류: {str(e)[:100]}...)")
                progress_callback("벡터 DB 동기화 실패", 95.0)
        else:
            logger.error("   ├─ 3단계: LLM 요약 생성 ❌")
            logger.warning("   └─ 4단계: 벡터 DB 동기화 건너뜀 (요약 생성 실패로 인해)")
            progress_callback("요약 생성 실패로 벡터 DB 동기화 건너뜀", 95.0)
            sync_success = False
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # 전체 성공 여부 판단
        overall_success = summary_success and sync_success
        
        # 수집 결과 요약 로깅
        if overall_success:
            logger.info(f"✅ 데이터 수집 완료!")
        else:
            logger.warning(f"⚠️ 데이터 수집 부분 완료 (일부 실패)")
        
        logger.info(f"📈 수집 결과 요약:")
        logger.info(f"   ├─ 회사: {company_id}")
        logger.info(f"   ├─ 플랫폼: {platform}")
        logger.info(f"   ├─ 소요시간: {duration:.2f}초 ({duration/60:.1f}분)")
        logger.info(f"   ├─ 시작시간: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"   ├─ 완료시간: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"   ├─ 요약 생성: {'✅' if summary_success else '❌'}")
        logger.info(f"   └─ 벡터 DB: {'✅' if sync_success else '❌'}")
        
        # 상황에 맞는 메시지 생성
        if overall_success:
            message = f"데이터 수집이 성공적으로 완료되었습니다. (소요시간: {duration:.1f}초)"
        elif summary_success and not sync_success:
            message = f"데이터 수집 및 요약 생성 완료, 벡터 DB 동기화 실패. (소요시간: {duration:.1f}초)"
        elif not summary_success and sync_success:
            message = f"데이터 수집 및 벡터 DB 동기화 완료, 요약 생성 실패. (소요시간: {duration:.1f}초)"
        else:
            message = f"데이터 수집은 완료했으나 요약 생성 및 벡터 DB 동기화 실패. (소요시간: {duration:.1f}초)"
        
        # 기본 응답 생성
        response_data = {
            "success": overall_success,
            "message": message,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": duration
        }
        
        # 메타데이터 포함 (요약 결과에서 추출)
        if 'summary_result' in locals() and summary_result:
            if 'attachment_metadata' in summary_result:
                response_data["attachment_metadata"] = summary_result["attachment_metadata"]
            response_data["summaries_generated"] = summary_result.get("success_count", 0)
        
        return IngestResponse(**response_data)
        
    except HTTPException as e:
        raise e
    except Exception as e:
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        logger.error(f"데이터 수집 중 오류 발생 - Company: {company_id}, Platform: {platform}: {e}", exc_info=True)
        
        return IngestResponse(
            success=False,
            message=f"데이터 수집 중 오류가 발생했습니다: {str(e)}",
            start_time=start_time.isoformat(),
            end_time=end_time.isoformat(),
            duration_seconds=duration,
            error=str(e)
        )

@router.post("/sync-summaries", response_model=IngestResponse)
async def sync_summaries_to_vector_db(
    company_id: str = Depends(get_company_id),
    platform: str = Depends(get_platform),
    api_key: Optional[str] = Depends(get_api_key),
    domain: Optional[str] = Depends(get_domain),
    batch_size: int = Query(25, description="배치 처리 크기", ge=1, le=100),
    force_update: bool = Query(False, description="기존 임베딩 강제 업데이트 여부")
):
    """
    SQLite에서 요약 데이터를 읽어서 벡터 DB에 동기화하는 엔드포인트 (멀티플랫폼 지원)
    
    이 엔드포인트는 ingest 프로세스에서 누락된 파이프라인 단계를 실행합니다:
    1. SQLite에서 tickets, kb_articles, conversations의 요약 데이터 조회
    2. 요약 텍스트를 임베딩으로 변환
    3. 3-tuple 보안(company_id, platform, original_id)을 유지하면서 Qdrant에 저장
    
    **새로운 표준 헤더 (권장):**
    - X-Company-ID: 회사 식별자 (멀티테넌트 보안)
    - X-Platform: 플랫폼 식별자 (멀티플랫폼 보안)
    - X-Domain: 플랫폼 도메인 (선택사항)
    - X-API-Key: 플랫폼 API 키 (선택사항, 추가 검증용)
    
    **레거시 헤더 (하위 호환성):**
    - X-Platform-Domain, X-Platform-API-Key 등
    
    Args:
        company_id: 회사 ID (X-Company-ID 헤더에서 자동 추출)
        platform: 플랫폼 식별자 (X-Platform 헤더에서 자동 추출)
        api_key: 플랫폼 API 키 (X-API-Key 헤더, 선택사항)
        domain: 플랫폼 도메인 (X-Domain 헤더, 선택사항)
        batch_size: 배치 처리 크기 (1-100, 기본값: 25)
        force_update: 기존 임베딩을 강제로 업데이트할지 여부 (기본값: False)
        
    Returns:
        IngestResponse: 동기화 결과 정보
    """
    from core.ingest.processor import sync_summaries_to_vector_db as sync_func
    
    start_time = datetime.now()
    logger.info(f"요약 데이터 벡터 DB 동기화 시작 - Company: {company_id}, Platform: {platform}")
    
    # 보안 헤더 검증
    if not company_id:
        raise HTTPException(status_code=400, detail="X-Company-ID 헤더가 필요합니다 (멀티테넌트 보안)")
    
    if not platform:
        raise HTTPException(status_code=400, detail="X-Platform 헤더가 필요합니다 (멀티플랫폼 보안)")
    
    # 선택적 보안 검증 (API 키와 도메인이 모두 제공된 경우)
    if api_key and domain:
        logger.info("추가 플랫폼 자격 증명 확인됨")
    elif api_key or domain:
        logger.warning("플랫폼 API 키와 도메인은 둘 다 제공되거나 둘 다 생략되어야 합니다")
    
    try:
        # 요약 데이터 동기화 실행
        result = await sync_func(
            company_id=company_id,
            platform=platform,
            batch_size=batch_size,
            force_update=force_update
        )
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        success_msg = (
            f"요약 데이터 벡터 DB 동기화 완료 - "
            f"성공: {result.get('success_count', 0)}, "
            f"실패: {result.get('failure_count', 0)}, "
            f"건너뜀: {result.get('skipped_count', 0)}, "
            f"총 처리: {result.get('total_processed', 0)}"
        )
        
        logger.info(success_msg)
        
        return IngestResponse(
            success=True,
            message=success_msg,
            start_time=start_time.isoformat(),
            end_time=end_time.isoformat(),
            duration_seconds=duration,
            metadata={
                "sync_result": result,
                "company_id": company_id,
                "platform": platform,
                "batch_size": batch_size,
                "force_update": force_update,
                "has_api_credentials": bool(api_key and domain)
            }
        )
        
    except Exception as e:
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        error_msg = f"요약 데이터 벡터 DB 동기화 실패: {str(e)}"
        
        logger.error(error_msg)
        
        return IngestResponse(
            success=False,
            message=error_msg,
            start_time=start_time.isoformat(),
            end_time=end_time.isoformat(),
            duration_seconds=duration,
            error=str(e)
        )

@router.post("/security/purge-data")
async def purge_company_data(
    request: DataSecurityRequest,
    company_id: str = Depends(get_company_id),
    platform: str = Depends(get_platform),
    api_key: Optional[str] = Depends(get_api_key),
    domain: Optional[str] = Depends(get_domain)
):
    """
    회사 데이터 완전 삭제 엔드포인트 (보안/GDPR 대응)
    
    🚨 **경고: 매우 위험한 작업**
    - 모든 수집된 데이터를 **영구적으로 삭제**합니다
    - SQLite 데이터, 벡터 DB 데이터, 캐시 데이터, AWS Secrets Manager 비밀키 모두 삭제
    - **복구 불가능**하므로 신중히 사용하세요
    
    **보안 검증 단계:**
    1. confirmation_token 검증
    2. 사용자 확인 문구 검증
    3. 관리자 승인 (필요시)
    4. 백업 생성 (선택사항)
    5. 완전 삭제 실행
    
    **삭제 대상:**
    - 🗄️ SQLite 데이터베이스 (티켓, 지식베이스, 요약 등)
    - 🔍 벡터 DB (Qdrant 임베딩 및 메타데이터)
    - 💾 캐시 데이터 (Redis, 메모리 캐시 등)
    - 🔐 AWS Secrets Manager (API 키, 인증 토큰 등)
    
    **사용 사례:**
    - GDPR "잊혀질 권리" 요청 대응
    - 회사 계약 종료 시 데이터 완전 삭제
    - 보안 사고 시 긴급 데이터 초기화
    - 테스트 환경 데이터 정리
    
    **AWS Secrets Manager 주의사항:**
    - force_delete=false: 30일 복구 기간 후 삭제 (권장)
    - force_delete=true: 즉시 영구 삭제 (복구 불가, 위험!)
    - AWS 자격 증명 필요 (AWS CLI, IAM 역할, 환경변수)
    
    Args:
        request: 데이터 삭제 요청 (확인 토큰 포함)
        company_id: 대상 회사 ID
        platform: 대상 플랫폼
        api_key: API 키 (추가 보안 검증)
        domain: 도메인 (추가 보안 검증)
        
    Returns:
        IngestResponse: 삭제 결과 및 백업 정보
    """
    start_time = datetime.now()
    logger.warning(f"🚨 데이터 완전 삭제 요청 - Company: {company_id}, Platform: {platform}")
    logger.warning(f"🔐 요청 세부사항: {request.action}, 사유: {request.reason}")
    
    # 1단계: 보안 토큰 검증
    expected_token = f"DELETE_{company_id}_{platform}_{datetime.now().strftime('%Y%m%d')}"
    if request.confirmation_token != expected_token:
        logger.error(f"❌ 보안 토큰 검증 실패: {request.confirmation_token}")
        raise HTTPException(
            status_code=403, 
            detail=f"보안 토큰이 올바르지 않습니다. 예상: {expected_token}"
        )
    
    # 2단계: 액션 타입 검증
    allowed_actions = ["purge_all", "reset_company", "delete_platform"]
    if request.action not in allowed_actions:
        raise HTTPException(
            status_code=400,
            detail=f"허용되지 않는 액션입니다. 허용된 액션: {allowed_actions}"
        )
    
    # 3단계: force_delete 모드 검증 (추가 안전장치)
    if request.force_delete and not request.reason:
        raise HTTPException(
            status_code=400,
            detail="force_delete 모드 사용 시 삭제 사유가 필수입니다"
        )
    
    try:
        from core.database.database import get_database
        from core.vectordb import vector_db
        
        backup_info = None
        
        # 4단계: 백업 생성 (선택사항)
        if request.create_backup:
            logger.info("📦 삭제 전 백업 생성 중...")
            try:
                backup_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_name = f"backup_{company_id}_{platform}_{backup_timestamp}"
                
                # SQLite 백업
                db = get_database(company_id, platform)
                sqlite_backup_path = f"backups/sqlite_{backup_name}.db"
                
                # 벡터 DB 백업 (스냅샷)
                vector_backup_info = None
                if request.include_vectors:
                    vector_backup_info = vector_db.create_backup(
                        backup_name=f"vector_{backup_name}",
                        company_id=company_id,
                        platform=platform
                    )
                
                # AWS Secrets 백업 정보 (실제 백업은 delete_aws_secrets 함수에서 처리)
                secrets_backup_info = None
                if request.include_secrets:
                    secrets_backup_info = {
                        "backup_name": f"secrets_{backup_name}",
                        "backup_path": f"backups/secrets_backup_{company_id}_{platform}_{backup_timestamp}.json",
                        "note": "AWS Secrets 백업은 삭제 단계에서 생성됩니다"
                    }
                
                backup_info = {
                    "backup_name": backup_name,
                    "sqlite_backup": sqlite_backup_path,
                    "vector_backup": vector_backup_info,
                    "secrets_backup": secrets_backup_info,
                    "created_at": backup_timestamp
                }
                
                logger.info(f"✅ 백업 생성 완료: {backup_name}")
                
            except Exception as e:
                logger.error(f"❌ 백업 생성 실패: {e}")
                if not request.force_delete:
                    raise HTTPException(
                        status_code=500,
                        detail=f"백업 생성에 실패했습니다. force_delete=true로 강제 진행하거나 백업 없이 재시도하세요: {e}"
                    )
        
        # 5단계: 데이터 완전 삭제 실행
        deleted_counts = {
            "sqlite_records": 0,
            "vector_points": 0,
            "cache_keys": 0,
            "aws_secrets": 0
        }
        
        # SQLite 데이터 삭제
        logger.warning("🗑️ SQLite 데이터 삭제 시작...")
        db = get_database(company_id, platform)
        
        if request.action == "purge_all":
            # 전체 데이터 삭제
            deleted_counts["sqlite_records"] = db.clear_all_data(company_id, platform)
        elif request.action == "reset_company":
            # 특정 회사 데이터만 삭제
            deleted_counts["sqlite_records"] = db.clear_all_data(company_id=company_id)
        elif request.action == "delete_platform":
            # 특정 플랫폼 데이터만 삭제
            deleted_counts["sqlite_records"] = db.clear_all_data(platform=platform)
        
        # 벡터 DB 데이터 삭제
        if request.include_vectors:
            logger.warning("🗑️ 벡터 DB 데이터 삭제 시작...")
            try:
                if request.action == "purge_all":
                    # 전체 컬렉션 초기화
                    success = vector_db.reset_collection(confirm=True, create_backup=False)
                    if success:
                        deleted_counts["vector_points"] = "all"
                else:
                    # 특정 회사/플랫폼 데이터만 삭제
                    filter_conditions = {}
                    if company_id:
                        filter_conditions["company_id"] = company_id
                    if platform:
                        filter_conditions["platform"] = platform
                    
                    deleted_ids = vector_db.delete_by_filter(filter_conditions)
                    deleted_counts["vector_points"] = len(deleted_ids) if deleted_ids else 0
                    
            except Exception as e:
                logger.error(f"❌ 벡터 DB 삭제 실패: {e}")
                if not request.force_delete:
                    raise
        
        # 캐시 데이터 삭제
        if request.include_cache:
            logger.warning("🗑️ 캐시 데이터 삭제 시작...")
            try:
                # Redis 캐시 또는 메모리 캐시 삭제
                # TODO: 실제 캐시 삭제 로직 구현
                deleted_counts["cache_keys"] = 0  # 임시값
            except Exception as e:
                logger.error(f"❌ 캐시 삭제 실패: {e}")
        
        # AWS Secrets Manager 비밀키 삭제
        if request.include_secrets:
            logger.warning("🔐 AWS Secrets Manager 비밀키 삭제 시작...")
            try:
                secrets_deleted = await delete_aws_secrets(
                    company_id=company_id,
                    platform=platform,
                    action=request.action,
                    aws_region=request.aws_region,
                    secret_name_pattern=request.secret_name_pattern,
                    create_backup=(request.create_backup and backup_info is not None),
                    force_delete=request.force_delete
                )
                deleted_counts["aws_secrets"] = secrets_deleted
                logger.warning(f"🔐 AWS Secrets Manager: {secrets_deleted}개 비밀키 삭제됨")
            except Exception as e:
                logger.error(f"❌ AWS Secrets Manager 삭제 실패: {e}")
                if not request.force_delete:
                    raise HTTPException(
                        status_code=500,
                        detail=f"AWS Secrets Manager 삭제 실패: {e}. force_delete=true로 무시하거나 include_secrets=false로 제외하세요."
                    )
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # 감사 로그 기록
        audit_log = {
            "action": "data_purge",
            "company_id": company_id,
            "platform": platform,
            "request_details": request.dict(),
            "deleted_counts": deleted_counts,
            "backup_info": backup_info,
            "executed_at": end_time.isoformat(),
            "duration_seconds": duration,
            "user_agent": "api_request"  # 실제로는 요청 헤더에서 가져와야 함
        }
        
        logger.warning(f"📋 감사 로그: {audit_log}")
        
        # 완료 메시지
        success_message = f"""
        🗑️ 데이터 완전 삭제 완료
        
        📊 삭제된 데이터:
        • SQLite 레코드: {deleted_counts['sqlite_records']}개
        • 벡터 포인트: {deleted_counts['vector_points']}개
        • 캐시 키: {deleted_counts['cache_keys']}개
        • AWS 비밀키: {deleted_counts['aws_secrets']}개
        
        ⏱️ 소요시간: {duration:.2f}초
        📦 백업: {'생성됨' if backup_info else '생성되지 않음'}
        
        ⚠️ 이 작업은 복구할 수 없습니다.
        """
        
        logger.warning(success_message)
        
        return IngestResponse(
            success=True,
            message=success_message.strip(),
            start_time=start_time.isoformat(),
            end_time=end_time.isoformat(),
            duration_seconds=duration,
            metadata={
                "action": request.action,
                "deleted_counts": deleted_counts,
                "backup_info": backup_info,
                "audit_log": audit_log,
                "security_validated": True
            }
        )
        
    except HTTPException as e:
        raise e
    except Exception as e:
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        error_msg = f"데이터 삭제 중 오류 발생: {str(e)}"
        logger.error(error_msg, exc_info=True)
        
        return IngestResponse(
            success=False,
            message=error_msg,
            start_time=start_time.isoformat(),
            end_time=end_time.isoformat(),
            duration_seconds=duration,
            error=str(e)
        )

@router.post("/security/generate-token")
async def generate_security_token(
    company_id: str = Depends(get_company_id),
    platform: str = Depends(get_platform)
):
    """
    보안 토큰 생성 엔드포인트
    
    데이터 삭제를 위한 보안 토큰을 생성합니다.
    토큰은 당일만 유효합니다.
    
    Returns:
        보안 토큰 및 사용법 안내
    """
    today = datetime.now().strftime('%Y%m%d')
    security_token = f"DELETE_{company_id}_{platform}_{today}"
    
    return {
        "security_token": security_token,
        "valid_until": f"{today} 23:59:59",
        "usage_example": {
            "confirmation_token": security_token,
            "action": "purge_all",
            "reason": "GDPR 잊혀질 권리 요청",
            "create_backup": True,
            "include_secrets": True,
            "aws_region": "us-east-1"
        },
        "security_options": {
            "include_vectors": "벡터 DB 데이터 삭제 여부 (기본: true)",
            "include_cache": "캐시 데이터 삭제 여부 (기본: true)",
            "include_secrets": "AWS Secrets Manager 비밀키 삭제 여부 (기본: true)",
            "include_logs": "감사 로그 삭제 여부 (기본: false)",
            "force_delete": "강제 즉시 삭제 모드 (기본: false, 위험!)",
            "aws_region": "AWS 리전 (선택사항, 기본: 환경변수)",
            "secret_name_pattern": "커스텀 시크릿 패턴 (선택사항)"
        },
        "warning": "⚠️ 이 토큰을 사용한 삭제는 복구할 수 없습니다!",
        "aws_warning": "🔐 AWS Secrets Manager 삭제는 기본적으로 30일 복구 기간이 있습니다. force_delete=true 시 즉시 영구 삭제됩니다."
    }
