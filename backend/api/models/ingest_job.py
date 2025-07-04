"""
데이터 수집 작업 관리 모델

데이터 수집 작업의 상태 추적, 제어, 진행상황 모니터링을 위한 모델들을 정의합니다.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
import uuid


class JobStatus(str, Enum):
    """작업 상태 열거형"""
    PENDING = "pending"      # 대기 중
    RUNNING = "running"      # 실행 중
    PAUSED = "paused"       # 일시정지
    CANCELLED = "cancelled"  # 취소됨
    COMPLETED = "completed"  # 완료
    FAILED = "failed"       # 실패


class JobType(str, Enum):
    """작업 타입 열거형"""
    FULL_INGEST = "full_ingest"           # 전체 데이터 수집
    INCREMENTAL_INGEST = "incremental_ingest"  # 증분 데이터 수집
    KB_ONLY = "kb_only"                   # 지식베이스만
    TICKETS_ONLY = "tickets_only"         # 티켓만
    ATTACHMENTS_ONLY = "attachments_only" # 첨부파일만


class JobProgress(BaseModel):
    """작업 진행상황 모델"""
    total_steps: int = Field(description="전체 단계 수")
    current_step: int = Field(description="현재 단계")
    current_step_name: str = Field(description="현재 단계명")
    tickets_processed: int = Field(default=0, description="처리된 티켓 수")
    kb_articles_processed: int = Field(default=0, description="처리된 지식베이스 문서 수")
    attachments_processed: int = Field(default=0, description="처리된 첨부파일 수")
    vectors_created: int = Field(default=0, description="생성된 벡터 수")
    errors_count: int = Field(default=0, description="오류 수")
    estimated_remaining_seconds: Optional[float] = Field(default=None, description="예상 남은 시간(초)")


class IngestJobConfig(BaseModel):
    """데이터 수집 작업 설정"""
    incremental: bool = Field(default=True, description="증분 업데이트 모드")
    purge: bool = Field(default=False, description="기존 데이터 삭제")
    process_attachments: bool = Field(default=True, description="첨부파일 처리")
    force_rebuild: bool = Field(default=False, description="강제 재구축")
    include_kb: bool = Field(default=True, description="지식베이스 포함")
    start_date: Optional[str] = Field(default=None, description="티켓 수집 시작 날짜 (YYYY-MM-DD 형식)")
    
    # 고급 옵션
    batch_size: int = Field(default=50, description="배치 크기")
    max_retries: int = Field(default=3, description="최대 재시도 횟수")
    parallel_workers: int = Field(default=4, description="병렬 작업자 수")
    
    # Freshdesk 설정
    domain: Optional[str] = Field(default=None, description="Freshdesk 도메인")
    api_key: Optional[str] = Field(default=None, description="Freshdesk API 키")


class IngestJob(BaseModel):
    """데이터 수집 작업 모델"""
    job_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="작업 ID")
    tenant_id: str = Field(description="테넌트 ID")
    job_type: JobType = Field(description="작업 타입")
    status: JobStatus = Field(default=JobStatus.PENDING, description="작업 상태")
    config: IngestJobConfig = Field(description="작업 설정")
    progress: JobProgress = Field(description="진행상황")
    
    # 시간 정보
    created_at: datetime = Field(default_factory=datetime.now, description="생성 시각")
    started_at: Optional[datetime] = Field(default=None, description="시작 시각")
    paused_at: Optional[datetime] = Field(default=None, description="일시정지 시각")
    completed_at: Optional[datetime] = Field(default=None, description="완료 시각")
    
    # 결과 정보
    error_message: Optional[str] = Field(default=None, description="오류 메시지")
    result_summary: Dict[str, Any] = Field(default_factory=dict, description="결과 요약")
    logs: List[str] = Field(default_factory=list, description="작업 로그")
    
    class Config:
        json_encoders = {
            datetime: lambda dt: dt.isoformat()
        }


class JobControlRequest(BaseModel):
    """작업 제어 요청 모델"""
    action: str = Field(description="수행할 액션 (pause, resume, cancel)")
    reason: Optional[str] = Field(default=None, description="액션 사유")


class JobListResponse(BaseModel):
    """작업 목록 응답 모델"""
    jobs: List[IngestJob] = Field(description="작업 목록")
    total: int = Field(description="전체 작업 수")
    page: int = Field(description="현재 페이지")
    per_page: int = Field(description="페이지당 항목 수")


class JobStatusResponse(BaseModel):
    """작업 상태 응답 모델"""
    job: IngestJob = Field(description="작업 정보")
    is_active: bool = Field(description="활성 상태 여부")
    can_pause: bool = Field(description="일시정지 가능 여부")
    can_resume: bool = Field(description="재개 가능 여부")
    can_cancel: bool = Field(description="취소 가능 여부")


class JobMetrics(BaseModel):
    """작업 메트릭스 모델"""
    total_jobs: int = Field(description="전체 작업 수")
    active_jobs: int = Field(description="활성 작업 수")
    completed_jobs: int = Field(description="완료 작업 수")
    failed_jobs: int = Field(description="실패 작업 수")
    average_duration_seconds: Optional[float] = Field(default=None, description="평균 소요 시간")
    success_rate: float = Field(description="성공률")
