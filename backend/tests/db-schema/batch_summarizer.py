"""
대량 데이터 요약 처리 시스템

100만건 이상의 대량 데이터를 처리하면서 품질을 최우선으로 하는 요약 시스템
"""

import asyncio
import logging
import time
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import json
from pathlib import Path

from .summarizer import generate_summary, validate_summary, _validate_summary_structure
from .manager import LLMManager

logger = logging.getLogger(__name__)


@dataclass
class BatchSummaryRequest:
    """배치 요약 요청 정보"""
    id: str
    content: str
    content_type: str = "ticket"
    subject: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    ui_language: str = "ko"
    priority: int = 0  # 0: 일반, 1: 높음, 2: 긴급
    retry_count: int = 0
    max_retries: int = 3
    
    
@dataclass 
class BatchSummaryResult:
    """배치 요약 결과"""
    id: str
    summary: str
    quality_score: float
    processing_time: float
    token_usage: Dict[str, int]
    model_used: str
    error: Optional[str] = None
    retry_count: int = 0
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class BatchProcessingStats:
    """배치 처리 통계"""
    total_requests: int = 0
    completed: int = 0
    failed: int = 0
    high_quality_count: int = 0  # 품질 점수 0.9 이상
    average_quality: float = 0.0
    average_processing_time: float = 0.0
    total_cost_estimate: float = 0.0
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None


class QualityAssuranceEngine:
    """품질 보장 엔진"""
    
    def __init__(self):
        self.quality_thresholds = {
            "structure_score": 0.95,  # 구조 점수 최소 95%
            "completion_info_score": 0.85,  # 완료 정보 점수 최소 85%
            "overall_quality": 0.90,  # 전체 품질 최소 90%
            "minimum_length": 100,  # 최소 길이
            "maximum_length": 2000   # 최대 길이
        }
    
    def evaluate_summary_quality(self, summary: str, original_content: str) -> Dict[str, float]:
        """요약 품질 상세 평가"""
        scores = {}
        
        # 1. 구조 점수 (4개 섹션 존재 여부)
        structure_score = self._evaluate_structure(summary)
        scores["structure_score"] = structure_score
        
        # 2. 완료 정보 추출 점수 
        completion_score = self._evaluate_completion_extraction(summary, original_content)
        scores["completion_info_score"] = completion_score
        
        # 3. 내용 충실도 점수
        content_fidelity_score = self._evaluate_content_fidelity(summary, original_content)
        scores["content_fidelity_score"] = content_fidelity_score
        
        # 4. 언어 품질 점수
        language_quality_score = self._evaluate_language_quality(summary)
        scores["language_quality_score"] = language_quality_score
        
        # 5. 길이 적정성 점수
        length_score = self._evaluate_length_appropriateness(summary)
        scores["length_score"] = length_score
        
        # 전체 점수 계산 (가중 평균)
        overall_score = (
            structure_score * 0.30 +
            completion_score * 0.25 +
            content_fidelity_score * 0.20 +
            language_quality_score * 0.15 +
            length_score * 0.10
        )
        scores["overall_quality"] = overall_score
        
        return scores
    
    def _evaluate_structure(self, summary: str) -> float:
        """구조 평가"""
        required_sections = [
            "🔍 **문제 상황**",
            "🎯 **근본 원인**", 
            "🔧 **해결 과정**",
            "💡 **핵심 포인트**"
        ]
        
        found_sections = sum(1 for section in required_sections if section in summary)
        return found_sections / len(required_sections)
    
    def _evaluate_completion_extraction(self, summary: str, original_content: str) -> float:
        """완료 정보 추출 평가"""
        # 원문에서 완료 패턴 찾기
        completion_patterns_ko = [
            r'처리했습니다', r'해드렸습니다', r'완료했습니다', r'복구했습니다',
            r'삭제했습니다', r'수정했습니다', r'발행했습니다', r'전송했습니다',
            r'확인했습니다', r'종료.*처리', r'입금.*확인'
        ]
        
        completion_patterns_en = [
            r'processed', r'completed', r'resolved', r'restored',
            r'deleted', r'modified', r'issued', r'sent', r'confirmed'
        ]
        
        import re
        
        # 원문에서 완료 패턴 수 계산
        original_completions = 0
        for pattern in completion_patterns_ko + completion_patterns_en:
            original_completions += len(re.findall(pattern, original_content, re.IGNORECASE))
        
        # 요약에서 완료 패턴 수 계산
        summary_completions = 0
        for pattern in completion_patterns_ko + completion_patterns_en:
            summary_completions += len(re.findall(pattern, summary, re.IGNORECASE))
        
        if original_completions == 0:
            return 1.0  # 원문에 완료 정보가 없으면 만점
        
        # 추출 비율 계산 (최대 1.0)
        extraction_ratio = min(summary_completions / original_completions, 1.0)
        return extraction_ratio
    
    def _evaluate_content_fidelity(self, summary: str, original_content: str) -> float:
        """내용 충실도 평가"""
        # 간단한 키워드 기반 충실도 측정
        original_words = set(original_content.lower().split())
        summary_words = set(summary.lower().split())
        
        # 공통 단어 비율
        if not original_words:
            return 0.0
        
        common_words = original_words.intersection(summary_words)
        fidelity_score = len(common_words) / len(original_words)
        
        # 0.3 ~ 1.0 범위로 정규화
        return min(max(fidelity_score * 2, 0.3), 1.0)
    
    def _evaluate_language_quality(self, summary: str) -> float:
        """언어 품질 평가"""
        # 기본적인 언어 품질 검사
        score = 1.0
        
        # 에러 메시지 확인
        error_indicators = ["[", "오류", "실패", "Error", "Failed"]
        if any(indicator in summary for indicator in error_indicators):
            score -= 0.5
        
        # 불완전한 문장 확인
        if summary.count("**") % 2 != 0:  # 마크다운 불균형
            score -= 0.2
        
        # 최소 길이 확인
        if len(summary.strip()) < 50:
            score -= 0.3
        
        return max(score, 0.0)
    
    def _evaluate_length_appropriateness(self, summary: str) -> float:
        """길이 적정성 평가"""
        length = len(summary.strip())
        
        if self.quality_thresholds["minimum_length"] <= length <= self.quality_thresholds["maximum_length"]:
            return 1.0
        elif length < self.quality_thresholds["minimum_length"]:
            return length / self.quality_thresholds["minimum_length"]
        else:
            # 너무 긴 경우 점수 감점
            excess = length - self.quality_thresholds["maximum_length"]
            penalty = min(excess / 1000, 0.5)  # 최대 50% 감점
            return max(1.0 - penalty, 0.5)
    
    def should_retry(self, quality_scores: Dict[str, float]) -> bool:
        """재시도 필요 여부 판단"""
        return (
            quality_scores.get("structure_score", 0) < self.quality_thresholds["structure_score"] or
            quality_scores.get("completion_info_score", 0) < self.quality_thresholds["completion_info_score"] or
            quality_scores.get("overall_quality", 0) < self.quality_thresholds["overall_quality"]
        )


class BatchSummarizer:
    """대량 데이터 요약 처리기"""
    
    def __init__(self, max_concurrent: int = 10, quality_first: bool = True):
        self.max_concurrent = max_concurrent
        self.quality_first = quality_first
        self.qa_engine = QualityAssuranceEngine()
        self.llm_manager = LLMManager()
        self.stats = BatchProcessingStats()
        
        # 요금 추정 (GPT-4o 기준)
        self.cost_per_1k_tokens = {
            "input": 0.005,   # $0.005 per 1K input tokens
            "output": 0.015   # $0.015 per 1K output tokens
        }
    
    async def process_batch(
        self, 
        requests: List[BatchSummaryRequest],
        progress_callback: Optional[callable] = None
    ) -> Tuple[List[BatchSummaryResult], BatchProcessingStats]:
        """배치 요약 처리"""
        
        logger.info(f"배치 요약 처리 시작: {len(requests)}건")
        self.stats.total_requests = len(requests)
        self.stats.start_time = datetime.now()
        
        # 우선순위별 정렬
        sorted_requests = sorted(requests, key=lambda x: x.priority, reverse=True)
        
        # 동시 처리 세마포어
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        # 결과 저장
        results = []
        
        # 배치 단위로 처리 (메모리 관리)
        batch_size = 100
        for i in range(0, len(sorted_requests), batch_size):
            batch = sorted_requests[i:i + batch_size]
            
            # 배치 내 동시 처리
            tasks = [
                self._process_single_request(request, semaphore)
                for request in batch
            ]
            
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 결과 처리
            for result in batch_results:
                if isinstance(result, Exception):
                    logger.error(f"배치 처리 중 예외: {result}")
                    self.stats.failed += 1
                else:
                    results.append(result)
                    self._update_stats(result)
            
            # 진행 상황 콜백
            if progress_callback:
                progress = (i + len(batch)) / len(sorted_requests)
                await progress_callback(progress, self.stats)
            
            # 메모리 정리를 위한 잠시 대기
            await asyncio.sleep(0.1)
        
        self.stats.end_time = datetime.now()
        
        # 최종 통계 계산
        self._finalize_stats()
        
        logger.info(f"배치 요약 처리 완료: 성공 {self.stats.completed}건, 실패 {self.stats.failed}건")
        logger.info(f"평균 품질 점수: {self.stats.average_quality:.3f}")
        logger.info(f"예상 비용: ${self.stats.total_cost_estimate:.2f}")
        
        return results, self.stats
    
    async def _process_single_request(
        self, 
        request: BatchSummaryRequest, 
        semaphore: asyncio.Semaphore
    ) -> BatchSummaryResult:
        """단일 요청 처리"""
        
        async with semaphore:
            start_time = time.time()
            
            try:
                # 고품질 요약 생성
                summary = await self._generate_high_quality_summary(request)
                
                # 품질 평가
                quality_scores = self.qa_engine.evaluate_summary_quality(
                    summary, request.content
                )
                
                # 토큰 사용량 추정
                token_usage = self._estimate_token_usage(request.content, summary)
                
                processing_time = time.time() - start_time
                
                result = BatchSummaryResult(
                    id=request.id,
                    summary=summary,
                    quality_score=quality_scores["overall_quality"],
                    processing_time=processing_time,
                    token_usage=token_usage,
                    model_used="gpt-4o",
                    retry_count=request.retry_count
                )
                
                logger.debug(f"요약 완료: {request.id} (품질: {quality_scores['overall_quality']:.3f})")
                return result
                
            except Exception as e:
                logger.error(f"요약 처리 실패: {request.id} - {e}")
                
                return BatchSummaryResult(
                    id=request.id,
                    summary=f"[요약 생성 실패: {str(e)}]",
                    quality_score=0.0,
                    processing_time=time.time() - start_time,
                    token_usage={"input": 0, "output": 0},
                    model_used="none",
                    error=str(e),
                    retry_count=request.retry_count
                )
    
    async def _generate_high_quality_summary(self, request: BatchSummaryRequest) -> str:
        """고품질 요약 생성 (재시도 로직 포함)"""
        
        for attempt in range(request.max_retries + 1):
            try:
                # 기본 요약 생성
                summary = await generate_summary(
                    content=request.content,
                    content_type=request.content_type,
                    subject=request.subject,
                    metadata=request.metadata,
                    ui_language=request.ui_language
                )
                
                # 품질 검증
                if self.quality_first:
                    quality_scores = self.qa_engine.evaluate_summary_quality(
                        summary, request.content
                    )
                    
                    # 품질 기준 미달 시 재시도
                    if attempt < request.max_retries and self.qa_engine.should_retry(quality_scores):
                        logger.warning(f"품질 기준 미달로 재시도: {request.id} (시도 {attempt + 1})")
                        request.retry_count += 1
                        
                        # 더 강력한 모델로 재시도
                        await asyncio.sleep(1.0)  # Rate limiting
                        continue
                
                return summary
                
            except Exception as e:
                if attempt < request.max_retries:
                    logger.warning(f"요약 생성 실패, 재시도: {request.id} (시도 {attempt + 1}) - {e}")
                    await asyncio.sleep(2.0 * (attempt + 1))  # 지수 백오프
                    continue
                else:
                    raise e
        
        # 최대 재시도 후에도 실패
        raise Exception(f"최대 재시도 {request.max_retries}회 후에도 요약 생성 실패")
    
    def _estimate_token_usage(self, content: str, summary: str) -> Dict[str, int]:
        """토큰 사용량 추정"""
        # 간단한 토큰 추정 (실제로는 tiktoken 라이브러리 사용 권장)
        input_tokens = len(content.split()) * 1.3  # 한국어 토큰 비율 고려
        output_tokens = len(summary.split()) * 1.3
        
        return {
            "input": int(input_tokens),
            "output": int(output_tokens)
        }
    
    def _update_stats(self, result: BatchSummaryResult):
        """통계 업데이트"""
        if result.error:
            self.stats.failed += 1
        else:
            self.stats.completed += 1
            
            if result.quality_score >= 0.9:
                self.stats.high_quality_count += 1
            
            # 비용 계산
            cost = (
                result.token_usage["input"] / 1000 * self.cost_per_1k_tokens["input"] +
                result.token_usage["output"] / 1000 * self.cost_per_1k_tokens["output"]
            )
            self.stats.total_cost_estimate += cost
    
    def _finalize_stats(self):
        """최종 통계 계산"""
        if self.stats.completed > 0:
            # 평균 품질 계산은 실제 결과에서 계산해야 함
            # 여기서는 임시로 high_quality_count 비율로 추정
            self.stats.average_quality = self.stats.high_quality_count / self.stats.completed
        
        # 처리 시간 계산
        if self.stats.end_time:
            total_time = (self.stats.end_time - self.stats.start_time).total_seconds()
            if self.stats.completed > 0:
                self.stats.average_processing_time = total_time / self.stats.completed


class BatchProgressTracker:
    """배치 처리 진행 상황 추적"""
    
    def __init__(self, log_file_path: Optional[str] = None):
        self.log_file_path = log_file_path
        self.progress_history = []
    
    async def track_progress(self, progress: float, stats: BatchProcessingStats):
        """진행 상황 추적"""
        progress_info = {
            "timestamp": datetime.now().isoformat(),
            "progress": progress,
            "completed": stats.completed,
            "failed": stats.failed,
            "high_quality_count": stats.high_quality_count,
            "estimated_cost": stats.total_cost_estimate
        }
        
        self.progress_history.append(progress_info)
        
        # 로그 출력
        logger.info(
            f"배치 처리 진행률: {progress:.1%} "
            f"(완료: {stats.completed}, 실패: {stats.failed}, "
            f"고품질: {stats.high_quality_count}, 예상비용: ${stats.total_cost_estimate:.2f})"
        )
        
        # 파일 저장
        if self.log_file_path:
            await self._save_progress_to_file(progress_info)
    
    async def _save_progress_to_file(self, progress_info: Dict[str, Any]):
        """진행 상황을 파일에 저장"""
        try:
            log_path = Path(self.log_file_path)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(progress_info, ensure_ascii=False) + '\n')
                
        except Exception as e:
            logger.error(f"진행 상황 파일 저장 실패: {e}")


# 사용 예시를 위한 헬퍼 함수들
def create_batch_requests_from_tickets(tickets: List[Dict[str, Any]]) -> List[BatchSummaryRequest]:
    """티켓 데이터에서 배치 요청 생성"""
    requests = []
    
    for ticket in tickets:
        # 우선순위 결정 (긴급도 기준)
        priority = 0
        if ticket.get('priority') == 'high':
            priority = 1
        elif ticket.get('priority') == 'urgent':
            priority = 2
        
        request = BatchSummaryRequest(
            id=str(ticket['id']),
            content=ticket.get('content', ''),
            content_type='ticket',
            subject=ticket.get('subject', ''),
            metadata={
                'status': ticket.get('status'),
                'priority': ticket.get('priority'),
                'category_id': ticket.get('category_id')
            },
            ui_language='ko',
            priority=priority,
            max_retries=3
        )
        requests.append(request)
    
    return requests


async def process_large_dataset_from_db(
    db_path: str,
    output_path: str,
    batch_size: int = 100,
    max_concurrent: int = 5,
    quality_first: bool = True
):
    """데이터베이스에서 대용량 데이터셋 처리"""
    
    import sqlite3
    
    # 배치 처리기 초기화
    batch_summarizer = BatchSummarizer(
        max_concurrent=max_concurrent,
        quality_first=quality_first
    )
    
    # 진행 상황 추적기
    progress_tracker = BatchProgressTracker(
        log_file_path=f"{output_path}/batch_progress.jsonl"
    )
    
    # 데이터베이스 연결
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 요약이 필요한 티켓 조회
        cursor.execute("""
        SELECT t.id, t.freshdesk_id, t.subject, t.description_text,
               GROUP_CONCAT(c.body_text, '\n---\n') as conversations
        FROM tickets t
        LEFT JOIN conversations c ON t.id = c.ticket_id
        LEFT JOIN summaries s ON t.id = s.ticket_id
        WHERE s.id IS NULL  -- 아직 요약이 없는 티켓
        AND t.description_text IS NOT NULL
        AND t.description_text != ''
        GROUP BY t.id, t.freshdesk_id, t.subject, t.description_text
        ORDER BY t.created_at DESC
        """)
        
        tickets = cursor.fetchall()
        logger.info(f"요약 대상 티켓: {len(tickets)}개")
        
        if not tickets:
            logger.info("요약할 티켓이 없습니다.")
            return [], None
        
        # 배치 단위로 처리
        all_results = []
        total_batches = (len(tickets) + batch_size - 1) // batch_size
        
        for batch_num in range(total_batches):
            start_idx = batch_num * batch_size
            end_idx = min(start_idx + batch_size, len(tickets))
            batch_tickets = tickets[start_idx:end_idx]
            
            logger.info(f"배치 {batch_num + 1}/{total_batches} 처리 중: {len(batch_tickets)}개 티켓")
            
            # 배치 요청 생성
            requests = []
            for ticket_id, freshdesk_id, subject, description, conversations in batch_tickets:
                # 전체 내용 결합
                full_content = description or ""
                if conversations:
                    full_content += f"\n\n=== 대화 내용 ===\n{conversations}"
                
                request = BatchSummaryRequest(
                    id=str(ticket_id),
                    content=full_content,
                    content_type="ticket",
                    subject=subject or "",
                    metadata={
                        'freshdesk_id': freshdesk_id,
                        'ticket_id': ticket_id
                    },
                    ui_language='ko',
                    priority=0,
                    max_retries=2
                )
                requests.append(request)
            
            # 배치 처리 실행
            async def progress_callback(progress, stats):
                await progress_tracker.track_progress(
                    (batch_num + progress) / total_batches, 
                    stats
                )
            
            batch_results, batch_stats = await batch_summarizer.process_batch(
                requests, progress_callback
            )
            
            # 결과를 데이터베이스에 저장
            await _save_summaries_to_db(cursor, batch_results)
            conn.commit()
            
            all_results.extend(batch_results)
            
            logger.info(f"배치 {batch_num + 1} 완료: 성공 {batch_stats.completed}개, 실패 {batch_stats.failed}개")
        
        logger.info(f"전체 처리 완료: 총 {len(all_results)}개 요약 생성")
        return all_results, progress_tracker
        
    finally:
        conn.close()


async def _save_summaries_to_db(cursor, batch_results):
    """배치 결과를 데이터베이스에 저장"""
    
    for result in batch_results:
        try:
            ticket_id = int(result.id)
            
            # 품질 세부사항 JSON 생성
            quality_details = {
                'overall_score': result.quality_score,
                'processing_time_ms': int(result.processing_time * 1000),
                'model_used': result.model_used,
                'retry_count': result.retry_count
            }
            
            # 토큰 사용량 JSON
            token_usage_json = json.dumps(result.token_usage)
            quality_details_json = json.dumps(quality_details)
            
            # 요약 길이 계산
            summary_length = len(result.summary)
            
            # 데이터베이스 삽입
            cursor.execute("""
            INSERT OR REPLACE INTO summaries (
                ticket_id, summary_text, quality_score, 
                quality_details_json, model_used, processing_time_ms,
                token_usage_json, cost_estimate, summary_length,
                retry_count, error_message, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ticket_id,
                result.summary,
                result.quality_score,
                quality_details_json,
                result.model_used,
                int(result.processing_time * 1000),
                token_usage_json,
                0.0,  # 비용 계산은 별도로
                summary_length,
                result.retry_count,
                result.error,
                datetime.now().isoformat(),
                datetime.now().isoformat()
            ))
            
        except Exception as e:
            logger.error(f"요약 저장 실패: {result.id} - {e}")


# 사용 예시 함수 업데이트
async def process_simplified_database():
    """단순화된 데이터베이스 처리 예시"""
    
    db_path = "core/data/wedosoft_freshdesk_data_simplified.db"
    output_path = "core/data/batch_results"
    
    results, tracker = await process_large_dataset_from_db(
        db_path=db_path,
        output_path=output_path,
        batch_size=50,  # 작은 배치로 안정성 확보
        max_concurrent=3,  # 동시 처리 수 제한
        quality_first=True
    )
    
    return results, tracker
