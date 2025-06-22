"""
데이터 수집 작업 관리 서비스

데이터 수집 작업의 생성, 실행, 상태 관리, 제어를 담당하는 서비스입니다.
기존 ingest.py의 함수들을 재활용하면서 작업 상태 관리 기능을 추가합니다.
"""

import asyncio
import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
from concurrent.futures import ThreadPoolExecutor
import uuid

from ..models.ingest_job import (
    IngestJob, 
    IngestJobConfig, 
    JobStatus, 
    JobType, 
    JobProgress,
    JobMetrics
)
from core.ingest.processor import ingest

logger = logging.getLogger(__name__)


class JobManager:
    """데이터 수집 작업 관리자
    
    싱글톤 패턴으로 구현되어 애플리케이션 전체에서 하나의 인스턴스만 존재합니다.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
            
        self._initialized = True
        self.jobs: Dict[str, IngestJob] = {}
        self.running_jobs: Set[str] = set()
        self.paused_jobs: Set[str] = set()
        self.cancel_signals: Dict[str, asyncio.Event] = {}
        self.pause_signals: Dict[str, asyncio.Event] = {}
        self.job_threads: Dict[str, threading.Thread] = {}
        self.executor = ThreadPoolExecutor(max_workers=2)  # 최대 2개 동시 실행
        
        # 주기적으로 작업 상태 정리 (완료/실패된 작업 정리)
        self._cleanup_thread = threading.Thread(target=self._cleanup_old_jobs, daemon=True)
        self._cleanup_thread.start()
    
    def create_job(
        self,
        company_id: str,
        config: IngestJobConfig,
        job_type: Optional[JobType] = None
    ) -> IngestJob:
        """새로운 데이터 수집 작업 생성"""
        
        # 작업 타입 자동 결정
        if job_type is None:
            if config.purge or config.force_rebuild:
                job_type = JobType.FULL_INGEST
            elif config.incremental:
                job_type = JobType.INCREMENTAL_INGEST
            elif config.include_kb and not config.process_attachments:
                job_type = JobType.KB_ONLY
            else:
                job_type = JobType.FULL_INGEST
        
        # 진행상황 초기화
        progress = JobProgress(
            total_steps=self._calculate_total_steps(config),
            current_step=0,
            current_step_name="준비 중"
        )
        
        job = IngestJob(
            company_id=company_id,
            job_type=job_type,
            config=config,
            progress=progress
        )
        
        self.jobs[job.job_id] = job
        logger.info(f"새 작업 생성: {job.job_id} (회사: {company_id}, 타입: {job_type})")
        
        return job
    
    def start_job(self, job_id: str) -> bool:
        """작업 시작"""
        if job_id not in self.jobs:
            logger.error(f"작업을 찾을 수 없음: {job_id}")
            return False
        
        job = self.jobs[job_id]
        
        if job.status != JobStatus.PENDING:
            logger.warning(f"시작할 수 없는 작업 상태: {job.status}")
            return False
        
        # 동시 실행 제한 체크
        if len(self.running_jobs) >= 2:
            logger.warning(f"최대 동시 실행 작업 수 초과: {len(self.running_jobs)}")
            return False
        
        # 🚨 자동 재수집 방지: 같은 회사의 최근 완료된 작업이 있는지 확인
        # 단, force_rebuild가 True인 경우에는 무시
        if not job.config.force_rebuild:
            recent_completed_jobs = [
                j for j in self.jobs.values() 
                if j.company_id == job.company_id 
                and j.status == JobStatus.COMPLETED 
                and j.completed_at
                and (datetime.now() - j.completed_at).total_seconds() < 300  # 5분 이내
            ]
            
            if recent_completed_jobs:
                logger.warning(f"⚠️  자동 재수집 방지: 회사 {job.company_id}의 최근 완료된 작업이 있습니다.")
                logger.warning(f"최근 완료된 작업: {[j.job_id for j in recent_completed_jobs]}")
                logger.warning("5분 후에 다시 시도하거나 force_rebuild=True를 사용하세요.")
                return False
        else:
            logger.info(f"🔧 강제 재구축 모드: 최근 작업 완료 여부를 무시하고 시작합니다.")
        
        # 작업 상태 업데이트
        job.status = JobStatus.RUNNING
        job.started_at = datetime.now()
        self.running_jobs.add(job_id)
        
        # 제어 신호 초기화
        self.cancel_signals[job_id] = asyncio.Event()
        self.pause_signals[job_id] = asyncio.Event()
        
        # 백그라운드에서 작업 실행
        thread = threading.Thread(target=self._run_job, args=(job_id,), daemon=True)
        self.job_threads[job_id] = thread
        thread.start()
        
        logger.info(f"작업 시작: {job_id}")
        return True
    
    def pause_job(self, job_id: str) -> bool:
        """작업 일시정지"""
        if job_id not in self.jobs:
            return False
        
        job = self.jobs[job_id]
        
        if job.status != JobStatus.RUNNING:
            return False
        
        job.status = JobStatus.PAUSED
        job.paused_at = datetime.now()
        self.paused_jobs.add(job_id)
        
        # 일시정지 신호 발송
        if job_id in self.pause_signals:
            # asyncio.Event를 스레드에서 설정할 때는 call_soon_threadsafe 사용
            try:
                loop = asyncio.get_event_loop()
                loop.call_soon_threadsafe(self.pause_signals[job_id].set)
            except RuntimeError:
                # 이벤트 루프가 없는 경우 직접 설정
                asyncio.create_task(self._set_pause_signal(job_id))
        
        logger.info(f"작업 일시정지: {job_id}")
        return True
    
    async def _set_pause_signal(self, job_id: str):
        """일시정지 신호 설정 (async 헬퍼)"""
        if job_id in self.pause_signals:
            self.pause_signals[job_id].set()
    
    async def _clear_pause_signal(self, job_id: str):
        """일시정지 신호 해제 (async 헬퍼)"""
        if job_id in self.pause_signals:
            self.pause_signals[job_id].clear()
    
    def resume_job(self, job_id: str) -> bool:
        """작업 재개"""
        if job_id not in self.jobs:
            return False
        
        job = self.jobs[job_id]
        
        if job.status != JobStatus.PAUSED:
            return False
        
        job.status = JobStatus.RUNNING
        job.paused_at = None
        self.paused_jobs.discard(job_id)
        
        # 일시정지 신호 해제
        if job_id in self.pause_signals:
            try:
                loop = asyncio.get_event_loop()
                loop.call_soon_threadsafe(self.pause_signals[job_id].clear)
            except RuntimeError:
                asyncio.create_task(self._clear_pause_signal(job_id))
        
        logger.info(f"작업 재개: {job_id}")
        return True
    
    def cancel_job(self, job_id: str) -> bool:
        """작업 취소"""
        if job_id not in self.jobs:
            return False
        
        job = self.jobs[job_id]
        
        if job.status not in [JobStatus.RUNNING, JobStatus.PAUSED, JobStatus.PENDING]:
            return False
        
        job.status = JobStatus.CANCELLED
        job.completed_at = datetime.now()
        
        # 취소 신호 발송
        if job_id in self.cancel_signals:
            try:
                loop = asyncio.get_event_loop()
                loop.call_soon_threadsafe(self.cancel_signals[job_id].set)
            except RuntimeError:
                asyncio.create_task(self._set_cancel_signal(job_id))
        
        self._cleanup_job_resources(job_id)
        
        logger.info(f"작업 취소: {job_id}")
        return True
    
    async def _set_cancel_signal(self, job_id: str):
        """취소 신호 설정 (async 헬퍼)"""
        if job_id in self.cancel_signals:
            self.cancel_signals[job_id].set()
    
    def get_job(self, job_id: str) -> Optional[IngestJob]:
        """작업 정보 조회"""
        return self.jobs.get(job_id)
    
    def list_jobs(
        self,
        company_id: Optional[str] = None,
        status: Optional[JobStatus] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[IngestJob]:
        """작업 목록 조회"""
        jobs = list(self.jobs.values())
        
        # 필터링
        if company_id:
            jobs = [j for j in jobs if j.company_id == company_id]
        
        if status:
            jobs = [j for j in jobs if j.status == status]
        
        # 정렬 (최신순)
        jobs.sort(key=lambda x: x.created_at, reverse=True)
        
        # 페이징
        return jobs[offset:offset + limit]
    
    def get_job_metrics(self, company_id: Optional[str] = None) -> JobMetrics:
        """작업 메트릭스 조회"""
        jobs = list(self.jobs.values())
        
        if company_id:
            jobs = [j for j in jobs if j.company_id == company_id]
        
        total_jobs = len(jobs)
        active_jobs = len([j for j in jobs if j.status in [JobStatus.RUNNING, JobStatus.PAUSED]])
        completed_jobs = len([j for j in jobs if j.status == JobStatus.COMPLETED])
        failed_jobs = len([j for j in jobs if j.status == JobStatus.FAILED])
        
        # 평균 소요 시간 계산
        completed = [j for j in jobs if j.status == JobStatus.COMPLETED and j.started_at and j.completed_at]
        avg_duration = None
        if completed:
            durations = [(j.completed_at - j.started_at).total_seconds() for j in completed]
            avg_duration = sum(durations) / len(durations)
        
        # 성공률 계산
        finished_jobs = completed_jobs + failed_jobs
        success_rate = (completed_jobs / finished_jobs * 100) if finished_jobs > 0 else 0
        
        return JobMetrics(
            total_jobs=total_jobs,
            active_jobs=active_jobs,
            completed_jobs=completed_jobs,
            failed_jobs=failed_jobs,
            average_duration_seconds=avg_duration,
            success_rate=success_rate
        )
    
    def _run_job(self, job_id: str):
        """작업 실행 (백그라운드 스레드에서 호출)"""
        job = self.jobs[job_id]
        
        try:
            # 1단계: 설정 검증
            self._update_job_progress(job_id, 1, "설정 검증 중")
            self._check_signals(job_id)  # 취소/일시정지 확인
            
            # 2단계: 데이터 수집 준비
            self._update_job_progress(job_id, 2, "데이터 수집 준비 중")
            self._check_signals(job_id)
            
            # 3단계: 실제 데이터 수집 실행 (기존 ingest 함수 사용)
            self._update_job_progress(job_id, 3, "데이터 수집 실행 중")
            
            # 기존 ingest 함수를 비동기로 실행
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                loop.run_until_complete(self._execute_legacy_ingest(job_id))
            finally:
                loop.close()
            
            # 4단계: 결과 정리
            self._update_job_progress(job_id, 4, "결과 정리 중")
            self._check_signals(job_id)
            
            # 완료 처리
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.now()
            job.progress.current_step = job.progress.total_steps
            job.progress.current_step_name = "완료"
            
            logger.info(f"작업 완료: {job_id}")
            
        except asyncio.CancelledError:
            job.status = JobStatus.CANCELLED
            job.completed_at = datetime.now()
            logger.info(f"작업 취소됨: {job_id}")
            
        except Exception as e:
            job.status = JobStatus.FAILED
            job.error_message = str(e)
            job.completed_at = datetime.now()
            logger.error(f"작업 실패: {job_id}, 오류: {e}", exc_info=True)
            
        finally:
            self._cleanup_job_resources(job_id)
    
    async def _execute_legacy_ingest(self, job_id: str):
        """기존 ingest 함수 실행"""
        job = self.jobs[job_id]
        config = job.config
        
        # 취소/일시정지 이벤트 생성
        cancel_event = self.cancel_signals.get(job_id, asyncio.Event())
        pause_event = self.pause_signals.get(job_id, asyncio.Event())
        
        # 진행상황 콜백 함수
        def progress_callback(message: str, percentage: float):
            job.progress.current_step_name = message
            # percentage를 current_step으로 변환 (0-100% → 0-total_steps)
            if job.progress.total_steps > 0:
                job.progress.current_step = int((percentage / 100.0) * job.progress.total_steps)
            logger.info(f"작업 {job_id} 진행상황: {message} ({percentage:.1f}%)")
        
        try:
            # 기존 ingest 함수 호출 (신호 전달)
            result = await ingest(
                company_id=job.company_id,
                platform="freshdesk",  # TODO: config에서 가져오기
                incremental=config.incremental,
                purge=config.purge,
                process_attachments=config.process_attachments,
                force_rebuild=config.force_rebuild,
                local_data_dir=None,
                include_kb=config.include_kb,
                domain=config.domain,
                api_key=config.api_key,
                cancel_event=cancel_event,
                pause_event=pause_event,
                progress_callback=progress_callback
            )
            
            # 결과 업데이트
            job.result_summary = result
            
            if result.get("success"):
                job.status = JobStatus.COMPLETED
                job.progress.current_step_name = "완료"
                job.progress.percentage = 100.0
            else:
                job.status = JobStatus.FAILED
                job.error_message = result.get("error", "알 수 없는 오류")
                
        except Exception as e:
            logger.error(f"작업 {job_id} 실행 중 오류: {e}")
            job.status = JobStatus.FAILED
            job.error_message = str(e)
            job.result_summary = {"success": False, "error": str(e)}
        
        finally:
            job.completed_at = datetime.now()
            self._cleanup_job_resources(job_id)
    
    def _check_signals(self, job_id: str):
        """취소/일시정지 신호 확인"""
        # 취소 신호 확인
        if job_id in self.cancel_signals and self.cancel_signals[job_id].is_set():
            raise asyncio.CancelledError("작업이 취소되었습니다")
        
        # 일시정지 신호 확인
        while (job_id in self.pause_signals and 
               self.pause_signals[job_id].is_set() and 
               self.jobs[job_id].status == JobStatus.PAUSED):
            time.sleep(0.5)  # 일시정지 상태에서 대기
    
    def _update_job_progress(self, job_id: str, step: int, step_name: str):
        """작업 진행상황 업데이트"""
        if job_id in self.jobs:
            job = self.jobs[job_id]
            job.progress.current_step = step
            job.progress.current_step_name = step_name
            
            # 예상 남은 시간 계산
            if job.started_at and step > 0:
                elapsed = (datetime.now() - job.started_at).total_seconds()
                progress_ratio = step / job.progress.total_steps
                if progress_ratio > 0:
                    estimated_total = elapsed / progress_ratio
                    job.progress.estimated_remaining_seconds = max(0, estimated_total - elapsed)
    
    def _calculate_total_steps(self, config: IngestJobConfig) -> int:
        """작업 설정에 따른 총 단계 수 계산"""
        steps = 4  # 기본 단계: 설정검증, 준비, 실행, 정리
        
        if config.purge:
            steps += 1  # 기존 데이터 삭제
        
        if config.process_attachments:
            steps += 1  # 첨부파일 처리
        
        if config.include_kb:
            steps += 1  # 지식베이스 처리
        
        return steps
    
    def _cleanup_job_resources(self, job_id: str):
        """작업 리소스 정리"""
        self.running_jobs.discard(job_id)
        self.paused_jobs.discard(job_id)
        
        if job_id in self.cancel_signals:
            del self.cancel_signals[job_id]
        
        if job_id in self.pause_signals:
            del self.pause_signals[job_id]
        
        if job_id in self.job_threads:
            del self.job_threads[job_id]
    
    def _cleanup_old_jobs(self):
        """오래된 작업 정리 (백그라운드 스레드)"""
        while True:
            try:
                current_time = datetime.now()
                cutoff_time = current_time - timedelta(hours=24)  # 24시간 이전 작업 정리
                
                jobs_to_remove = []
                for job_id, job in self.jobs.items():
                    if (job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED] and
                        job.completed_at and job.completed_at < cutoff_time):
                        jobs_to_remove.append(job_id)
                
                for job_id in jobs_to_remove:
                    del self.jobs[job_id]
                    logger.debug(f"오래된 작업 정리: {job_id}")
                
                time.sleep(3600)  # 1시간마다 정리 작업 실행
                
            except Exception as e:
                logger.error(f"작업 정리 중 오류: {e}", exc_info=True)
                time.sleep(3600)


# 전역 작업 관리자 인스턴스
job_manager = JobManager()
