#!/usr/bin/env python3
"""
최적화된 스키마용 대량 요약 처리 시스템

새로운 정규화된 스키마에서 100만건 이상의 데이터를 고품질로 요약 처리
"""

import asyncio
import sqlite3
import logging
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
import argparse

# 프로젝트 경로 추가
sys.path.append(str(Path(__file__).parent))

from core.llm.batch_summarizer import (
    BatchSummarizer, 
    BatchSummaryRequest, 
    BatchProgressTracker,
    QualityAssuranceEngine
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('optimized_batch_summarization.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class OptimizedLargeScaleSummarizer:
    """최적화된 대규모 요약 처리 엔진"""
    
    def __init__(
        self,
        db_path: str,
        output_dir: str,
        batch_size: int = 200,
        max_concurrent: int = 6,
        quality_threshold: float = 0.9
    ):
        self.db_path = db_path
        self.output_dir = Path(output_dir)
        self.batch_size = batch_size
        self.max_concurrent = max_concurrent
        self.quality_threshold = quality_threshold
        
        # 출력 디렉토리 생성
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 배치 처리기 초기화
        self.batch_summarizer = BatchSummarizer(
            max_concurrent=max_concurrent,
            quality_first=True
        )
        
        # 진행 상황 추적기
        self.progress_tracker = BatchProgressTracker(
            log_file_path=str(self.output_dir / "progress.jsonl")
        )
        
        # 처리 통계
        self.total_processed = 0
        self.total_high_quality = 0
        self.total_cost = 0.0
        self.start_time = datetime.now()
    
    async def process_all_pending_tickets(self, limit: Optional[int] = None):
        """처리 대기 중인 모든 티켓 요약"""
        
        logger.info("=== 최적화된 대규모 티켓 요약 처리 시작 ===")
        logger.info(f"데이터베이스: {self.db_path}")
        logger.info(f"배치 크기: {self.batch_size}")
        logger.info(f"동시 처리 수: {self.max_concurrent}")
        logger.info(f"품질 임계값: {self.quality_threshold}")
        
        try:
            # 처리 대상 티켓 수 확인
            total_pending = await self._count_pending_tickets(limit)
            logger.info(f"처리 대상 티켓: {total_pending:,}건")
            
            if total_pending == 0:
                logger.warning("처리할 티켓이 없습니다.")
                return
            
            # 배치 단위로 처리
            processed_count = 0
            batch_num = 0
            
            while processed_count < total_pending:
                batch_num += 1
                
                # 배치 데이터 로드
                tickets = await self._load_pending_ticket_batch(
                    offset=processed_count,
                    limit=min(self.batch_size, total_pending - processed_count)
                )
                
                if not tickets:
                    break
                
                logger.info(f"=== 배치 {batch_num} 처리 시작 ({len(tickets)}건) ===")
                
                # 배치 요약 처리
                await self._process_ticket_batch(tickets, batch_num)
                
                processed_count += len(tickets)
                self.total_processed += len(tickets)
                
                progress = processed_count / total_pending
                logger.info(f"배치 {batch_num} 완료. 전체 진행률: {progress:.1%}")
                
                # 메모리 정리를 위한 잠시 대기
                await asyncio.sleep(1.0)
            
            # 최종 통계 출력
            await self._generate_final_report()
            
        except Exception as e:
            logger.error(f"처리 중 오류 발생: {e}")
            raise
    
    async def _count_pending_tickets(self, limit: Optional[int]) -> int:
        """처리 대기 중인 티켓 수 조회"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # 뷰를 사용하여 효율적으로 조회
            query = "SELECT COUNT(*) FROM v_pending_summaries"
            
            if limit:
                query += f" LIMIT {limit}"
            
            cursor.execute(query)
            result = cursor.fetchone()
            return result[0] if result else 0
            
        finally:
            conn.close()
    
    async def _load_pending_ticket_batch(self, offset: int, limit: int) -> List[Dict[str, Any]]:
        """배치 단위 대기 티켓 로드"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # 최적화된 쿼리 - 조인을 통해 한 번에 모든 정보 로드
            query = """
            SELECT 
                t.id,
                t.freshdesk_id,
                t.subject,
                t.description_text,
                t.status_id,
                t.priority_id,
                t.created_at,
                c.company_name,
                -- 대화 내용 집계 (최근 20개만)
                GROUP_CONCAT(
                    conv.body_text, 
                    ' | ' 
                    ORDER BY conv.created_at DESC 
                    LIMIT 20
                ) as conversation_texts
            FROM tickets t
            LEFT JOIN companies c ON t.company_id = c.id
            LEFT JOIN summaries s ON t.id = s.ticket_id AND s.is_active = 1
            LEFT JOIN conversations conv ON t.id = conv.ticket_id
            WHERE s.id IS NULL 
            AND t.conversation_count > 0
            GROUP BY t.id, t.freshdesk_id, t.subject, t.description_text, t.status_id, t.priority_id, t.created_at, c.company_name
            ORDER BY t.created_at DESC
            LIMIT ? OFFSET ?
            """
            
            cursor.execute(query, (limit, offset))
            results = cursor.fetchall()
            
            # 딕셔너리로 변환
            tickets = []
            for row in results:
                # 내용 조합
                content_parts = []
                
                # 제목
                if row[2]:  # subject
                    content_parts.append(f"제목: {row[2]}")
                
                # 설명
                if row[3]:  # description_text
                    content_parts.append(f"설명: {row[3]}")
                
                # 대화 내용
                if row[8]:  # conversation_texts
                    content_parts.append("대화 내용:")
                    conversations = row[8].split(' | ')
                    for i, conv in enumerate(conversations[:15]):  # 최대 15개만
                        if conv.strip():
                            content_parts.append(f"- {conv.strip()}")
                
                content = '\n'.join(content_parts)
                
                # 우선순위 매핑
                priority_map = {1: 'low', 2: 'medium', 3: 'high', 4: 'urgent'}
                priority_text = priority_map.get(row[5], 'medium')
                
                ticket = {
                    'id': row[0],
                    'freshdesk_id': row[1],
                    'subject': row[2] or '',
                    'content': content,
                    'priority': priority_text,
                    'status_id': row[4],
                    'created_at': row[6],
                    'company_name': row[7] or 'Unknown'
                }
                
                tickets.append(ticket)
            
            return tickets
            
        finally:
            conn.close()
    
    async def _process_ticket_batch(self, tickets: List[Dict[str, Any]], batch_num: int):
        """배치 단위 티켓 요약 처리"""
        
        # 배치 요청 생성
        requests = self._create_batch_requests(tickets)
        
        # 처리 로그 기록 시작
        await self._log_batch_start(batch_num, len(requests))
        
        try:
            # 배치 처리
            results, stats = await self.batch_summarizer.process_batch(
                requests=requests,
                progress_callback=self.progress_tracker.track_progress
            )
            
            # 결과 저장
            await self._save_batch_results(results, batch_num)
            
            # 데이터베이스 업데이트
            await self._update_database_with_summaries(results)
            
            # 통계 업데이트
            self.total_high_quality += stats.high_quality_count
            self.total_cost += stats.total_cost_estimate
            
            # 배치 완료 로그
            await self._log_batch_completion(batch_num, stats)
            
        except Exception as e:
            logger.error(f"배치 {batch_num} 처리 실패: {e}")
            await self._log_batch_error(batch_num, str(e))
            raise
    
    def _create_batch_requests(self, tickets: List[Dict[str, Any]]) -> List[BatchSummaryRequest]:
        """배치 요청 생성"""
        
        requests = []
        
        for ticket in tickets:
            # 우선순위 매핑
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
                    'freshdesk_id': ticket.get('freshdesk_id'),
                    'status_id': ticket.get('status_id'),
                    'priority': ticket.get('priority'),
                    'company_name': ticket.get('company_name')
                },
                ui_language='ko',
                priority=priority,
                max_retries=3
            )
            requests.append(request)
        
        return requests
    
    async def _save_batch_results(self, results, batch_num: int):
        """배치 결과 파일 저장"""
        
        batch_file = self.output_dir / f"optimized_batch_{batch_num:04d}_results.json"
        
        # 결과 직렬화
        serialized_results = []
        for result in results:
            serialized_results.append({
                'ticket_id': result.id,
                'summary': result.summary,
                'quality_score': result.quality_score,
                'processing_time': result.processing_time,
                'token_usage': result.token_usage,
                'model_used': result.model_used,
                'error': result.error,
                'retry_count': result.retry_count,
                'timestamp': result.timestamp.isoformat()
            })
        
        with open(batch_file, 'w', encoding='utf-8') as f:
            json.dump(serialized_results, f, ensure_ascii=False, indent=2)
        
        logger.info(f"배치 {batch_num} 결과 저장: {batch_file}")
    
    async def _update_database_with_summaries(self, results):
        """데이터베이스에 요약 결과 저장"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            for result in results:
                if not result.error and result.quality_score >= self.quality_threshold:
                    # 고품질 요약을 summaries 테이블에 저장
                    cursor.execute(
                        """
                        INSERT INTO summaries (
                            ticket_id, summary_text, summary_type,
                            quality_score, model_used,
                            tokens_input, tokens_output,
                            processing_time_ms, cost_estimate,
                            ui_language, content_language,
                            retry_count, version, is_active,
                            created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                        """,
                        (
                            int(result.id),
                            result.summary,
                            'ticket',
                            result.quality_score,
                            result.model_used,
                            result.token_usage.get('input', 0),
                            result.token_usage.get('output', 0),
                            int(result.processing_time * 1000),  # ms로 변환
                            result.token_usage.get('input', 0) / 1000 * 0.005 + 
                            result.token_usage.get('output', 0) / 1000 * 0.015,  # 비용 계산
                            'ko',
                            'ko',
                            result.retry_count,
                            1,
                            True
                        )
                    )
                    
                    # 처리 로그 기록
                    cursor.execute(
                        """
                        INSERT INTO processing_logs (
                            table_name, record_id, process_type, status,
                            result_message, processing_time_ms,
                            started_at, completed_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                        """,
                        (
                            'summaries',
                            int(result.id),
                            'summary_generation',
                            'completed',
                            f'High quality summary generated (score: {result.quality_score:.3f})',
                            int(result.processing_time * 1000),
                            datetime.now().isoformat()
                        )
                    )
                else:
                    # 실패 또는 저품질 요약 로그
                    error_msg = result.error or f"Low quality score: {result.quality_score:.3f}"
                    cursor.execute(
                        """
                        INSERT INTO processing_logs (
                            table_name, record_id, process_type, status,
                            error_message, processing_time_ms,
                            started_at, completed_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                        """,
                        (
                            'summaries',
                            int(result.id),
                            'summary_generation',
                            'failed',
                            error_msg,
                            int(result.processing_time * 1000),
                            datetime.now().isoformat()
                        )
                    )
            
            conn.commit()
            logger.info(f"데이터베이스 업데이트 완료: {len(results)}건 처리")
            
        except Exception as e:
            logger.error(f"데이터베이스 업데이트 실패: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()
    
    async def _log_batch_start(self, batch_num: int, count: int):
        """배치 시작 로그"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                """
                INSERT INTO processing_logs (
                    table_name, record_id, process_type, status,
                    result_message, batch_id, batch_size,
                    started_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    'summaries',
                    0,
                    'batch_processing',
                    'processing',
                    f'Batch {batch_num} started',
                    f'batch_{batch_num:04d}',
                    count
                )
            )
            conn.commit()
        finally:
            conn.close()
    
    async def _log_batch_completion(self, batch_num: int, stats):
        """배치 완료 로그"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                """
                INSERT INTO processing_logs (
                    table_name, record_id, process_type, status,
                    result_message, batch_id, batch_size,
                    started_at, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    'summaries',
                    0,
                    'batch_processing',
                    'completed',
                    f'Batch {batch_num} completed: {stats.completed}/{stats.total_requests} successful, {stats.high_quality_count} high quality',
                    f'batch_{batch_num:04d}',
                    stats.total_requests,
                    datetime.now().isoformat()
                )
            )
            conn.commit()
        finally:
            conn.close()
    
    async def _log_batch_error(self, batch_num: int, error_msg: str):
        """배치 오류 로그"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                """
                INSERT INTO processing_logs (
                    table_name, record_id, process_type, status,
                    error_message, batch_id,
                    started_at, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    'summaries',
                    0,
                    'batch_processing',
                    'failed',
                    error_msg,
                    f'batch_{batch_num:04d}',
                    datetime.now().isoformat()
                )
            )
            conn.commit()
        finally:
            conn.close()
    
    async def _generate_final_report(self):
        """최종 처리 보고서 생성"""
        
        end_time = datetime.now()
        total_time = (end_time - self.start_time).total_seconds()
        
        final_report = {
            "summary": {
                "start_time": self.start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "total_processing_time_seconds": total_time,
                "total_processed": self.total_processed,
                "total_high_quality": self.total_high_quality,
                "high_quality_rate": self.total_high_quality / self.total_processed if self.total_processed > 0 else 0,
                "total_estimated_cost": self.total_cost,
                "average_cost_per_ticket": self.total_cost / self.total_processed if self.total_processed > 0 else 0,
                "tickets_per_second": self.total_processed / total_time if total_time > 0 else 0
            },
            "configuration": {
                "batch_size": self.batch_size,
                "max_concurrent": self.max_concurrent,
                "quality_threshold": self.quality_threshold,
                "database_path": self.db_path
            }
        }
        
        # 최종 보고서 저장
        final_report_file = self.output_dir / "optimized_final_report.json"
        with open(final_report_file, 'w', encoding='utf-8') as f:
            json.dump(final_report, f, ensure_ascii=False, indent=2)
        
        # 로그 출력
        logger.info("=== 최종 처리 보고서 ===")
        logger.info(f"총 처리 시간: {total_time/3600:.2f}시간")
        logger.info(f"총 처리 건수: {self.total_processed:,}건")
        logger.info(f"고품질 요약: {self.total_high_quality:,}건 ({self.total_high_quality/self.total_processed*100:.1f}%)")
        logger.info(f"총 예상 비용: ${self.total_cost:.2f}")
        logger.info(f"건당 평균 비용: ${self.total_cost/self.total_processed:.4f}")
        logger.info(f"처리 속도: {self.total_processed/total_time:.2f}건/초")
        logger.info(f"최종 보고서: {final_report_file}")


async def main():
    """메인 함수"""
    
    parser = argparse.ArgumentParser(description="최적화된 대량 티켓 요약 처리")
    parser.add_argument("--db-path", default="core/data/wedosoft_freshdesk_data_optimized.db", help="최적화된 데이터베이스 경로")
    parser.add_argument("--output-dir", default="./optimized_batch_results", help="결과 출력 디렉토리")
    parser.add_argument("--batch-size", type=int, default=200, help="배치 크기 (기본: 200)")
    parser.add_argument("--max-concurrent", type=int, default=6, help="최대 동시 처리 수 (기본: 6)")
    parser.add_argument("--quality-threshold", type=float, default=0.9, help="품질 임계값 (기본: 0.9)")
    parser.add_argument("--limit", type=int, help="처리할 최대 티켓 수 (테스트용)")
    parser.add_argument("--dry-run", action="store_true", help="실제 처리 없이 계획만 출력")
    
    args = parser.parse_args()
    
    # 데이터베이스 존재 확인
    if not Path(args.db_path).exists():
        logger.error(f"데이터베이스 파일이 존재하지 않습니다: {args.db_path}")
        logger.error("먼저 create_optimized_schema.py를 실행해주세요.")
        sys.exit(1)
    
    # 처리 엔진 초기화
    engine = OptimizedLargeScaleSummarizer(
        db_path=args.db_path,
        output_dir=args.output_dir,
        batch_size=args.batch_size,
        max_concurrent=args.max_concurrent,
        quality_threshold=args.quality_threshold
    )
    
    if args.dry_run:
        logger.info("=== DRY RUN 모드 ===")
        total_pending = await engine._count_pending_tickets(args.limit)
        
        estimated_batches = (total_pending + args.batch_size - 1) // args.batch_size
        estimated_cost = total_pending * 0.008  # 더 정확한 추정
        estimated_time = total_pending / (args.max_concurrent * 1.5)  # 초당 처리량 추정
        
        logger.info(f"처리 대상: {total_pending:,}건")
        logger.info(f"예상 배치 수: {estimated_batches:,}개")
        logger.info(f"예상 비용: ${estimated_cost:.2f}")
        logger.info(f"예상 시간: {estimated_time/3600:.2f}시간")
        
        return
    
    # 실제 처리 실행
    try:
        await engine.process_all_pending_tickets(limit=args.limit)
        logger.info("🎉 처리 완료!")
        
    except KeyboardInterrupt:
        logger.info("사용자에 의해 중단되었습니다.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"처리 중 오류: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
