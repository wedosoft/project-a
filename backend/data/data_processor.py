"""
데이터 병합 및 후처리 유틸리티

청크로 분할 저장된 Freshdesk 데이터를 병합하고 분석하는 도구
"""
import json
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class DataProcessor:
    """청크 데이터 병합 및 처리"""
    
    def __init__(self, data_dir: str):
        self.data_dir = Path(data_dir)
        
    def merge_chunks(self, output_file: str = "all_tickets.json") -> List[Dict]:
        """모든 청크 파일을 하나로 병합"""
        all_tickets = []
        chunk_files = sorted(self.data_dir.glob("tickets_chunk_*.json"))
        
        logger.info(f"{len(chunk_files)}개 청크 파일 병합 시작")
        
        for chunk_file in chunk_files:
            with open(chunk_file, 'r', encoding='utf-8') as f:
                tickets = json.load(f)
                all_tickets.extend(tickets)
                logger.info(f"{chunk_file.name}: {len(tickets)}개 티켓 추가")
        
        # 병합된 데이터 저장
        output_path = self.data_dir / output_file
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(all_tickets, f, ensure_ascii=False, indent=2)
        
        logger.info(f"병합 완료: 총 {len(all_tickets)}개 티켓 → {output_file}")
        return all_tickets
    
    def create_csv_export(self, tickets: List[Dict] = None) -> str:
        """티켓 데이터를 CSV로 변환"""
        if tickets is None:
            with open(self.data_dir / "all_tickets.json", 'r', encoding='utf-8') as f:
                tickets = json.load(f)
        
        # 기본 티켓 정보 추출
        csv_data = []
        for ticket in tickets:
            row = {
                'id': ticket.get('id'),
                'subject': ticket.get('subject'),
                'description_text': ticket.get('description_text'),
                'status': ticket.get('status'),
                'priority': ticket.get('priority'),
                'type': ticket.get('type'),
                'created_at': ticket.get('created_at'),
                'updated_at': ticket.get('updated_at'),
                'requester_id': ticket.get('requester_id'),
                'responder_id': ticket.get('responder_id'),
                'company_id': ticket.get('company_id'),
                'product_id': ticket.get('product_id'),
                'source': ticket.get('source'),
                'tags': ','.join(ticket.get('tags', [])),
                'conversations_count': len(ticket.get('conversations', [])),
                'attachments_count': len(ticket.get('attachments', []))
            }
            csv_data.append(row)
        
        df = pd.DataFrame(csv_data)
        csv_file = self.data_dir / "tickets_export.csv"
        df.to_csv(csv_file, index=False, encoding='utf-8-sig')
        
        logger.info(f"CSV 내보내기 완료: {csv_file}")
        return str(csv_file)
    
    def generate_summary_report(self, tickets: List[Dict] = None) -> Dict:
        """수집된 데이터의 요약 리포트 생성"""
        if tickets is None:
            with open(self.data_dir / "all_tickets.json", 'r', encoding='utf-8') as f:
                tickets = json.load(f)
        
        # 기본 통계
        total_tickets = len(tickets)
        
        # 상태별 분포
        status_counts = {}
        priority_counts = {}
        type_counts = {}
        source_counts = {}
        
        conversation_counts = []
        attachment_counts = []
        
        for ticket in tickets:
            # 상태 분포
            status = ticket.get('status', 'Unknown')
            status_counts[status] = status_counts.get(status, 0) + 1
            
            # 우선순위 분포
            priority = ticket.get('priority', 'Unknown')
            priority_counts[priority] = priority_counts.get(priority, 0) + 1
            
            # 타입 분포
            ticket_type = ticket.get('type', 'Unknown')
            type_counts[ticket_type] = type_counts.get(ticket_type, 0) + 1
            
            # 소스 분포
            source = ticket.get('source', 'Unknown')
            source_counts[source] = source_counts.get(source, 0) + 1
            
            # 대화 및 첨부파일 수
            conversation_counts.append(len(ticket.get('conversations', [])))
            attachment_counts.append(len(ticket.get('attachments', [])))
        
        summary = {
            'total_tickets': total_tickets,
            'status_distribution': status_counts,
            'priority_distribution': priority_counts,
            'type_distribution': type_counts,
            'source_distribution': source_counts,
            'conversation_stats': {
                'avg_conversations_per_ticket': sum(conversation_counts) / len(conversation_counts) if conversation_counts else 0,
                'max_conversations': max(conversation_counts) if conversation_counts else 0,
                'total_conversations': sum(conversation_counts)
            },
            'attachment_stats': {
                'avg_attachments_per_ticket': sum(attachment_counts) / len(attachment_counts) if attachment_counts else 0,
                'max_attachments': max(attachment_counts) if attachment_counts else 0,
                'total_attachments': sum(attachment_counts)
            }
        }
        
        # 리포트 저장
        report_file = self.data_dir / "summary_report.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        
        logger.info(f"요약 리포트 생성 완료: {report_file}")
        return summary


def cleanup_temp_files(data_dir: str, keep_chunks: bool = False):
    """임시 파일 정리"""
    data_path = Path(data_dir)
    
    if not keep_chunks:
        # 청크 파일들 삭제
        chunk_files = list(data_path.glob("tickets_chunk_*.json"))
        for chunk_file in chunk_files:
            chunk_file.unlink()
        logger.info(f"{len(chunk_files)}개 청크 파일 삭제")
    
    # 진행 상황 파일 삭제
    progress_file = data_path / "progress.json"
    if progress_file.exists():
        progress_file.unlink()
        logger.info("진행 상황 파일 삭제")


async def process_collected_data(data_dir: str):
    """수집된 데이터 후처리 예제"""
    processor = DataProcessor(data_dir)
    
    # 1. 청크 병합
    tickets = processor.merge_chunks()
    
    # 2. CSV 내보내기
    csv_file = processor.create_csv_export(tickets)
    
    # 3. 요약 리포트 생성
    summary = processor.generate_summary_report(tickets)
    
    print(f"처리 완료:")
    print(f"- 총 티켓 수: {summary['total_tickets']:,}개")
    print(f"- CSV 파일: {csv_file}")
    print(f"- 평균 대화 수: {summary['conversation_stats']['avg_conversations_per_ticket']:.1f}")
    print(f"- 총 대화 수: {summary['conversation_stats']['total_conversations']:,}개")
    
    # 4. 임시 파일 정리 (선택적)
    # cleanup_temp_files(data_dir, keep_chunks=True)


if __name__ == "__main__":
    import asyncio
    asyncio.run(process_collected_data("freshdesk_100k_data"))
