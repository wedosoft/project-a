"""
대용량 요약 처리를 위한 스케일링 최적화 모듈

100만건+ 규모의 데이터를 안정적으로 처리하면서 품질을 보장하는 
최적화된 배치 처리 시스템입니다.
"""

import asyncio
import logging
import time
from typing import Dict, Any, List, Optional, Tuple, AsyncGenerator
from dataclasses import dataclass, field
from datetime import datetime
import json
from pathlib import Path
import gc
import psutil
import threading

from .optimized_summarizer import OptimizedSummarizer
from .manager import LLMManager, LLMProvider

logger = logging.getLogger(__name__)


@dataclass
class ScalabilityConfig:
    """스케일링 설정"""
    # 메모리 관리
    max_memory_usage_percent: float = 80.0
    memory_check_interval: int = 100  # 처리 건수마다 메모리 확인
    gc_threshold: float = 70.0  # GC 실행 임계값
    
    # 배치 크기 조정
    initial_batch_size: int = 50
    min_batch_size: int = 10
    max_batch_size: int = 200
    batch_size_adjustment_factor: float = 1.2
    
    # 동시성 제어
    base_concurrency: int = 5
    max_concurrency: int = 20
    concurrency_scale_factor: float = 1.5
    
    # 품질 vs 처리량 균형
    quality_priority_mode: bool = True
    quality_check_frequency: int = 10  # 매 N건마다 품질 확인
    min_quality_threshold: float = 0.85
    
    # 오류 처리
    max_retry_attempts: int = 3
    retry_delay_base: float = 1.0
    error_threshold_percent: float = 10.0  # 10% 이상 실패 시 중단


@dataclass
class ProcessingMetrics:
    """처리 지표"""
    total_processed: int = 0
    successful: int = 0
    failed: int = 0
    retried: int = 0
    average_processing_time: float = 0.0
    average_quality_score: float = 0.0
    memory_usage_peak: float = 0.0
    current_batch_size: int = 0
    current_concurrency: int = 0
    error_rate: float = 0.0
    throughput_per_minute: float = 0.0
    estimated_time_remaining: Optional[float] = None


class ResourceMonitor:
    """리소스 모니터링"""
    
    def __init__(self, config: ScalabilityConfig):
        self.config = config
        self.process = psutil.Process()
        self.monitoring_active = False
        self._stop_event = threading.Event()
        
    def start_monitoring(self):
        """모니터링 시작"""
        self.monitoring_active = True
        self._stop_event.clear()
        
    def stop_monitoring(self):
        """모니터링 중지"""
        self.monitoring_active = False
        self._stop_event.set()
        
    def get_memory_usage_percent(self) -> float:
        """현재 메모리 사용률 반환"""
        try:
            memory_info = self.process.memory_info()
            system_memory = psutil.virtual_memory()
            usage_percent = (memory_info.rss / system_memory.total) * 100
            return usage_percent
        except Exception as e:
            logger.warning(f"메모리 사용률 확인 실패: {e}")
            return 0.0
    
    def should_trigger_gc(self) -> bool:
        """GC 실행 필요 여부 확인"""
        return self.get_memory_usage_percent() > self.config.gc_threshold
    
    def is_memory_critical(self) -> bool:
        """메모리 위험 수준 확인"""
        return self.get_memory_usage_percent() > self.config.max_memory_usage_percent


class AdaptiveBatchSizer:
    """적응형 배치 크기 조정"""
    
    def __init__(self, config: ScalabilityConfig):
        self.config = config
        self.current_batch_size = config.initial_batch_size
        self.performance_history = []
        self.max_history_size = 10
        
    def adjust_batch_size(self, processing_time: float, memory_usage: float, error_count: int):
        """배치 크기 동적 조정"""
        
        # 성능 지표 기록
        self.performance_history.append({
            'batch_size': self.current_batch_size,
            'processing_time': processing_time,
            'memory_usage': memory_usage,
            'error_count': error_count
        })
        
        # 이력 크기 제한
        if len(self.performance_history) > self.max_history_size:
            self.performance_history.pop(0)
        
        # 조정 로직
        if len(self.performance_history) >= 3:
            recent_performance = self.performance_history[-3:]
            
            # 에러율이 높으면 배치 크기 감소
            if error_count > 0:
                self.current_batch_size = max(
                    int(self.current_batch_size / self.config.batch_size_adjustment_factor),
                    self.config.min_batch_size
                )
                logger.info(f"에러 발생으로 배치 크기 감소: {self.current_batch_size}")
                
            # 메모리 사용량이 높으면 배치 크기 감소
            elif memory_usage > self.config.max_memory_usage_percent * 0.9:
                self.current_batch_size = max(
                    int(self.current_batch_size * 0.8),
                    self.config.min_batch_size
                )
                logger.info(f"메모리 부담으로 배치 크기 감소: {self.current_batch_size}")
                
            # 성능이 안정적이면 배치 크기 증가
            elif all(p['error_count'] == 0 for p in recent_performance):
                avg_processing_time = sum(p['processing_time'] for p in recent_performance) / len(recent_performance)
                if avg_processing_time < 30.0:  # 30초 미만이면 증가 고려
                    self.current_batch_size = min(
                        int(self.current_batch_size * self.config.batch_size_adjustment_factor),
                        self.config.max_batch_size
                    )
                    logger.info(f"성능 양호로 배치 크기 증가: {self.current_batch_size}")
        
        return self.current_batch_size


class ScalableSummarizer:
    """대용량 처리 최적화 요약기"""
    
    def __init__(self, config: Optional[ScalabilityConfig] = None):
        self.config = config or ScalabilityConfig()
        self.summarizer = OptimizedSummarizer()
        self.resource_monitor = ResourceMonitor(self.config)
        self.batch_sizer = AdaptiveBatchSizer(self.config)
        self.metrics = ProcessingMetrics()
        self.processing_start_time = None
        
    async def process_large_dataset(
        self,
        data_generator: AsyncGenerator[Dict[str, Any], None],
        total_count: int,
        progress_callback: Optional[callable] = None
    ) -> Tuple[List[Dict[str, Any]], ProcessingMetrics]:
        """대용량 데이터셋 처리"""
        
        logger.info(f"대용량 데이터셋 처리 시작: {total_count}건")
        
        # 대용량 모드 활성화
        self.summarizer.enable_large_scale_mode(total_count)
        
        # 모니터링 시작
        self.resource_monitor.start_monitoring()
        self.processing_start_time = time.time()
        
        # 초기 설정
        self.metrics.current_batch_size = self.config.initial_batch_size
        self.metrics.current_concurrency = self.config.base_concurrency
        
        results = []
        current_batch = []
        batch_start_time = time.time()
        
        try:
            async for item in data_generator:
                current_batch.append(item)
                
                # 배치 크기에 도달하면 처리
                if len(current_batch) >= self.metrics.current_batch_size:
                    batch_results = await self._process_batch(current_batch)
                    results.extend(batch_results)
                    
                    # 성능 지표 업데이트
                    await self._update_metrics(
                        len(current_batch), 
                        time.time() - batch_start_time,
                        batch_results
                    )
                    
                    # 리소스 상태 확인 및 조정
                    await self._adaptive_adjustment()
                    
                    # 진행 상황 보고
                    if progress_callback:
                        await progress_callback(self.metrics.total_processed, total_count, self.metrics)
                    
                    # 다음 배치 준비
                    current_batch = []
                    batch_start_time = time.time()
                    
                    # 메모리 위험 수준 확인
                    if self.resource_monitor.is_memory_critical():
                        logger.warning("메모리 임계점 도달, 대기 중...")
                        await asyncio.sleep(2.0)
                        gc.collect()
            
            # 마지막 배치 처리
            if current_batch:
                batch_results = await self._process_batch(current_batch)
                results.extend(batch_results)
                await self._update_metrics(len(current_batch), time.time() - batch_start_time, batch_results)
            
            logger.info(f"대용량 처리 완료: {self.metrics.successful}건 성공, {self.metrics.failed}건 실패")
            
        except Exception as e:
            logger.error(f"대용량 처리 중 오류: {e}")
            raise
        finally:
            self.resource_monitor.stop_monitoring()
        
        return results, self.metrics
    
    async def _process_batch(self, batch: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """배치 처리"""
        
        # 동시성 제한
        semaphore = asyncio.Semaphore(self.metrics.current_concurrency)
        
        async def process_single_item(item: Dict[str, Any]) -> Dict[str, Any]:
            async with semaphore:
                return await self._process_single_item_with_retry(item)
        
        # 배치 내 병렬 처리
        tasks = [process_single_item(item) for item in batch]
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 예외 처리
        processed_results = []
        for i, result in enumerate(batch_results):
            if isinstance(result, Exception):
                logger.error(f"배치 아이템 처리 실패: {result}")
                processed_results.append({
                    'id': batch[i].get('id', 'unknown'),
                    'summary': '[처리 실패]',
                    'error': str(result),
                    'quality_score': 0.0
                })
            else:
                processed_results.append(result)
        
        return processed_results
    
    async def _process_single_item_with_retry(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """재시도 로직이 포함된 단일 아이템 처리"""
        
        last_error = None
        
        for attempt in range(self.config.max_retry_attempts):
            try:
                start_time = time.time()
                
                # 요약 생성
                summary = await self.summarizer.generate_summary(
                    content=item.get('content', ''),
                    content_type=item.get('content_type', 'ticket'),
                    subject=item.get('subject', ''),
                    metadata=item.get('metadata', {}),
                    ui_language=item.get('ui_language', 'ko'),
                    context=item.get('context', '')
                )
                
                processing_time = time.time() - start_time
                
                # 품질 점수 계산 (간단한 휴리스틱)
                quality_score = self._estimate_quality_score(summary)
                
                result = {
                    'id': item.get('id', 'unknown'),
                    'summary': summary,
                    'quality_score': quality_score,
                    'processing_time': processing_time,
                    'retry_count': attempt,
                    'error': None
                }
                
                # 품질 확인 (품질 우선 모드인 경우)
                if self.config.quality_priority_mode and quality_score < self.config.min_quality_threshold:
                    if attempt < self.config.max_retry_attempts - 1:
                        logger.warning(f"품질 기준 미달로 재시도: {item.get('id')} (점수: {quality_score:.3f})")
                        await asyncio.sleep(self.config.retry_delay_base * (attempt + 1))
                        continue
                
                return result
                
            except Exception as e:
                last_error = e
                if attempt < self.config.max_retry_attempts - 1:
                    delay = self.config.retry_delay_base * (2 ** attempt)  # 지수 백오프
                    logger.warning(f"처리 실패, {delay}초 후 재시도: {item.get('id')} - {e}")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"최대 재시도 횟수 초과: {item.get('id')} - {e}")
        
        # 최종 실패
        return {
            'id': item.get('id', 'unknown'),
            'summary': '[처리 실패]',
            'quality_score': 0.0,
            'processing_time': 0.0,
            'retry_count': self.config.max_retry_attempts,
            'error': str(last_error)
        }
    
    def _estimate_quality_score(self, summary: str) -> float:
        """요약 품질 점수 추정"""
        score = 1.0
        
        # 길이 확인
        if len(summary.strip()) < 100:
            score -= 0.3
        
        # 구조 확인 (섹션 헤더)
        required_sections = ["문제 상황", "근본 원인", "해결 과정", "핵심 포인트"]
        found_sections = sum(1 for section in required_sections if section in summary)
        structure_score = found_sections / len(required_sections)
        score *= structure_score
        
        # 에러 메시지 확인
        if any(error in summary for error in ['[처리 실패]', 'Error', '오류']):
            score = 0.0
        
        return max(score, 0.0)
    
    async def _update_metrics(self, batch_size: int, processing_time: float, results: List[Dict[str, Any]]):
        """지표 업데이트"""
        
        # 성공/실패 집계
        successful_in_batch = sum(1 for r in results if r.get('error') is None)
        failed_in_batch = batch_size - successful_in_batch
        
        self.metrics.total_processed += batch_size
        self.metrics.successful += successful_in_batch
        self.metrics.failed += failed_in_batch
        
        # 평균 처리 시간 업데이트
        if self.metrics.total_processed > 0:
            total_time = time.time() - self.processing_start_time
            self.metrics.average_processing_time = total_time / self.metrics.total_processed
        
        # 평균 품질 점수 업데이트
        quality_scores = [r.get('quality_score', 0.0) for r in results if r.get('error') is None]
        if quality_scores:
            current_avg = self.metrics.average_quality_score
            current_count = self.metrics.successful - successful_in_batch
            new_avg = sum(quality_scores) / len(quality_scores)
            
            # 누적 평균 계산
            if current_count > 0:
                self.metrics.average_quality_score = (
                    (current_avg * current_count + new_avg * successful_in_batch) /
                    self.metrics.successful
                )
            else:
                self.metrics.average_quality_score = new_avg
        
        # 에러율 계산
        self.metrics.error_rate = (self.metrics.failed / self.metrics.total_processed) * 100
        
        # 처리량 계산 (분당)
        if self.processing_start_time:
            elapsed_minutes = (time.time() - self.processing_start_time) / 60
            if elapsed_minutes > 0:
                self.metrics.throughput_per_minute = self.metrics.total_processed / elapsed_minutes
        
        # 메모리 사용량 업데이트
        current_memory = self.resource_monitor.get_memory_usage_percent()
        self.metrics.memory_usage_peak = max(self.metrics.memory_usage_peak, current_memory)
    
    async def _adaptive_adjustment(self):
        """적응형 조정"""
        
        # 메모리 사용량 확인
        memory_usage = self.resource_monitor.get_memory_usage_percent()
        
        # GC 실행 결정
        if self.resource_monitor.should_trigger_gc():
            logger.debug("메모리 정리 실행")
            gc.collect()
        
        # 배치 크기 조정
        error_count = self.metrics.failed if self.metrics.total_processed > 0 else 0
        self.metrics.current_batch_size = self.batch_sizer.adjust_batch_size(
            self.metrics.average_processing_time,
            memory_usage,
            error_count
        )
        
        # 동시성 조정
        if memory_usage > self.config.max_memory_usage_percent * 0.8:
            # 메모리 부담 시 동시성 감소
            self.metrics.current_concurrency = max(
                int(self.metrics.current_concurrency * 0.8),
                1
            )
        elif self.metrics.error_rate < 5.0 and memory_usage < 60.0:
            # 안정적이면 동시성 증가
            self.metrics.current_concurrency = min(
                int(self.metrics.current_concurrency * 1.2),
                self.config.max_concurrency
            )
        
        # 에러율이 임계값을 초과하면 중단 검토
        if self.metrics.error_rate > self.config.error_threshold_percent:
            logger.error(f"에러율 임계값 초과: {self.metrics.error_rate:.1f}%")
            # 여기서 중단하거나 추가 조치를 취할 수 있음


# 사용 예시를 위한 헬퍼 함수
async def create_data_generator_from_db(db_path: str, batch_size: int = 1000) -> AsyncGenerator[Dict[str, Any], None]:
    """데이터베이스에서 데이터 생성기 생성"""
    
    import sqlite3
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 총 개수 확인
        cursor.execute("SELECT COUNT(*) FROM tickets WHERE description_text IS NOT NULL")
        total_count = cursor.fetchone()[0]
        
        # 배치 단위로 데이터 조회
        offset = 0
        while offset < total_count:
            cursor.execute("""
            SELECT id, subject, description_text, 
                   GROUP_CONCAT(c.body_text, '\n---\n') as conversations
            FROM tickets t
            LEFT JOIN conversations c ON t.id = c.ticket_id
            WHERE t.description_text IS NOT NULL
            GROUP BY t.id, t.subject, t.description_text
            LIMIT ? OFFSET ?
            """, (batch_size, offset))
            
            rows = cursor.fetchall()
            if not rows:
                break
            
            for row in rows:
                ticket_id, subject, description, conversations = row
                
                # 전체 내용 구성
                content = description or ""
                if conversations:
                    content += f"\n\n=== 대화 내용 ===\n{conversations}"
                
                yield {
                    'id': str(ticket_id),
                    'content': content,
                    'content_type': 'ticket',
                    'subject': subject or "",
                    'metadata': {'ticket_id': ticket_id},
                    'ui_language': 'ko'
                }
            
            offset += batch_size
            
    finally:
        conn.close()


async def process_million_scale_dataset(db_path: str, output_path: str) -> ProcessingMetrics:
    """100만건 규모 데이터셋 처리 예시"""
    
    # 최적화된 설정
    config = ScalabilityConfig(
        initial_batch_size=30,       # 보수적 시작
        max_batch_size=100,          # 제한된 최대 크기
        base_concurrency=3,          # 낮은 동시성으로 시작
        max_concurrency=10,          # 제한된 최대 동시성
        quality_priority_mode=True,  # 품질 우선
        min_quality_threshold=0.80,  # 품질 기준 완화
        max_memory_usage_percent=75.0, # 메모리 여유 확보
        error_threshold_percent=15.0   # 에러율 허용치 증가
    )
    
    # 스케일러블 요약기 생성
    summarizer = ScalableSummarizer(config)
    
    # 데이터 생성기 생성
    data_gen = create_data_generator_from_db(db_path)
    
    # 총 개수 확인 (별도 쿼리)
    import sqlite3
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM tickets WHERE description_text IS NOT NULL")
    total_count = cursor.fetchone()[0]
    conn.close()
    
    # 진행 상황 콜백
    async def progress_callback(processed: int, total: int, metrics: ProcessingMetrics):
        progress_percent = (processed / total) * 100 if total > 0 else 0
        logger.info(
            f"진행률: {progress_percent:.1f}% ({processed}/{total}) | "
            f"성공: {metrics.successful} | 실패: {metrics.failed} | "
            f"평균 품질: {metrics.average_quality_score:.3f} | "
            f"처리량: {metrics.throughput_per_minute:.1f}/min | "
            f"메모리: {metrics.memory_usage_peak:.1f}%"
        )
    
    # 대용량 처리 실행
    results, final_metrics = await summarizer.process_large_dataset(
        data_gen, total_count, progress_callback
    )
    
    # 결과 저장
    output_file = Path(output_path) / f"large_scale_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'metrics': {
                'total_processed': final_metrics.total_processed,
                'successful': final_metrics.successful,
                'failed': final_metrics.failed,
                'average_quality_score': final_metrics.average_quality_score,
                'average_processing_time': final_metrics.average_processing_time,
                'throughput_per_minute': final_metrics.throughput_per_minute,
                'memory_usage_peak': final_metrics.memory_usage_peak,
                'error_rate': final_metrics.error_rate
            },
            'sample_results': results[:10]  # 샘플 결과만 저장
        }, ensure_ascii=False, indent=2)
    
    logger.info(f"대용량 처리 완료: {output_file}")
    return final_metrics
