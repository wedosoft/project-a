"""
데이터 병합 및 후처리 유틸리티

청크로 분할 저장된 Freshdesk 데이터를 병합하고 분석하는 도구
"""
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


class DataProcessor:
    """청크 데이터 병합 및 처리"""
    
    def __init__(self, data_dir: str):
        self.data_dir = Path(data_dir)
        
    def merge_chunks(self, output_file: str = "all_tickets.json") -> List[Dict]:
        """
        청크 파일들을 메모리에서만 병합하여 반환 (대용량 파일 생성 금지)
        대용량 시스템에서는 청크 단위로만 작업해야 하므로 전체 파일은 생성하지 않음
        """
        all_tickets = []
        
        # raw_data/tickets/ 디렉토리에서 청크 파일 검색
        tickets_dir = self.data_dir / "raw_data" / "tickets"
        if not tickets_dir.exists():
            logger.error(f"디렉토리를 찾을 수 없음: {tickets_dir}")
            return []
            
        chunk_files = sorted(tickets_dir.glob("tickets_chunk_*.json"))
        logger.info(f"raw_data/tickets에서 {len(chunk_files)}개 청크 파일 발견")
        
        logger.info(f"{len(chunk_files)}개 청크 파일을 메모리에서 병합 중...")
        
        for chunk_file in chunk_files:
            try:
                with open(chunk_file, 'r', encoding='utf-8') as f:
                    tickets = json.load(f)
                    all_tickets.extend(tickets)
                    logger.info(f"{chunk_file.name}: {len(tickets)}개 티켓 로드")
            except Exception as e:
                logger.error(f"청크 파일 읽기 실패 {chunk_file}: {e}")
        
        # 대용량 파일 생성 금지 - 메모리에서만 반환
        logger.info(f"메모리 병합 완료: 총 {len(all_tickets)}개 티켓 (파일 생성하지 않음)")
        return all_tickets
    
    def create_csv_export(self, tickets: Optional[List[Dict]] = None) -> str:
        """
        티켓 데이터를 CSV로 변환 (대용량 파일 생성 금지)
        CSV 내보내기 기능은 소규모 데이터셋에서만 사용하며, 대용량 시스템에서는 비활성화
        """
        logger.warning("CSV 내보내기는 대용량 시스템에서 비활성화되었습니다. 청크 단위로 작업하세요.")
        return ""
        
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
                'tenant_id': ticket.get('tenant_id'),
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
    
    def generate_summary_report(self, tickets: Optional[List[Dict]] = None) -> Dict:
        """수집된 데이터의 요약 리포트 생성"""
        if tickets is None:
            with open(self.data_dir / "all_tickets.json", 'r', encoding='utf-8') as f:
                tickets = json.load(f)
        
        # tickets가 None이거나 빈 리스트인 경우 처리
        if not tickets:
            return {
                'total_tickets': 0,
                'status_distribution': {},
                'priority_distribution': {},
                'type_distribution': {},
                'source_distribution': {},
                'conversation_stats': {
                    'avg_conversations_per_ticket': 0,
                    'max_conversations': 0,
                    'total_conversations': 0
                },
                'attachment_stats': {
                    'avg_attachments_per_ticket': 0,
                    'max_attachments': 0,
                    'total_attachments': 0
                }
            }
        
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
    
    # 진행 상황 파일은 더 이상 사용하지 않음 (DB 기반으로 변경됨)


async def process_collected_data(data_dir: str):
    """수집된 데이터 후처리 예제"""
    processor = DataProcessor(data_dir)
    
    # 1. 청크 병합
    tickets = processor.merge_chunks()
    
    # 2. CSV 내보내기
    csv_file = processor.create_csv_export(tickets)
    
    # 3. 요약 리포트 생성
    summary = processor.generate_summary_report(tickets)
    
    print("처리 완료:")
    print(f"- 총 티켓 수: {summary['total_tickets']:,}개")
    print(f"- CSV 파일: {csv_file}")
    print(f"- 평균 대화 수: {summary['conversation_stats']['avg_conversations_per_ticket']:.1f}")
    print(f"- 총 대화 수: {summary['conversation_stats']['total_conversations']:,}개")
    
    # 4. 임시 파일 정리 (선택적)
    # cleanup_temp_files(data_dir, keep_chunks=True)


"""
Langchain RunnableParallel 체인에서 사용하는 데이터 처리 함수들
"""

async def fetch_similar_tickets(ticket_data: Dict[str, Any], 
                               qdrant_client: Any, 
                               tenant_id: str, 
                               limit: int = 5) -> List[Any]:
    """
    유사 티켓 검색을 수행합니다.
    
    Langchain RunnableParallel 체인에서 호출되는 함수로,
    기존 main.py의 get_similar_tickets 엔드포인트와 동일한 로직을 수행합니다.
    
    Args:
        ticket_data: 티켓 데이터 딕셔너리
        qdrant_client: Qdrant 벡터 DB 클라이언트
        tenant_id: 회사 식별자
        limit: 반환할 최대 결과 수
        
    Returns:
        유사 티켓 목록 (DocumentInfo 형태)
    """
    from ..api.main import get_similar_tickets
    from ..models import DocumentInfo
    
    try:
        # 티켓 ID 추출
        ticket_id = str(ticket_data.get('id', ''))
        
        # API 엔드포인트와 동일한 로직 수행
        similar_tickets_response = await get_similar_tickets(ticket_id, tenant_id)
        
        # 응답 형식 변환: SimilarTicketItem[] -> DocumentInfo[]
        similar_tickets_list = []
        for item in similar_tickets_response.similar_tickets:
            # 구조화된 형식으로 content 생성
            content_parts = []
            
            # 문제 상황 추가
            if item.issue:
                content_parts.append(f"문제 상황: {item.issue}")
            
            # 해결책 추가
            if item.solution:
                content_parts.append(f"해결책: {item.solution}")
                
            # ticket_summary가 있으면 추가
            if item.ticket_summary:
                content_parts.append(f"요약: {item.ticket_summary}")
            
            # content 구성
            content = "\n\n".join(content_parts) if content_parts else f"티켓 {item.id} 관련 정보"
            
            similar_tickets_list.append(DocumentInfo(
                title=item.title or f"티켓 {item.id}",
                content=content,
                source_id=str(item.id),
                source_url=item.ticket_url or "",
                relevance_score=item.similarity_score or 0.0,
                doc_type="ticket"
            ))
        
        return similar_tickets_list[:limit]
        
    except Exception as e:
        logger.error(f"유사 티켓 검색 실패: {str(e)}")
        return []


async def fetch_kb_documents(ticket_data: Dict[str, Any], 
                            qdrant_client: Any, 
                            tenant_id: str, 
                            limit: int = 3) -> List[Any]:
    """
    지식베이스 문서 검색을 수행합니다.
    
    Langchain RunnableParallel 체인에서 호출되는 함수로,
    기존 main.py의 get_related_documents 엔드포인트와 동일한 로직을 수행합니다.
    
    Args:
        ticket_data: 티켓 데이터 딕셔너리
        qdrant_client: Qdrant 벡터 DB 클라이언트
        tenant_id: 회사 식별자
        limit: 반환할 최대 결과 수
        
    Returns:
        지식베이스 문서 목록 (DocumentInfo 형태)
    """
    from ..api.main import get_related_documents
    from ..models import DocumentInfo
    
    try:
        # 티켓 ID 추출
        ticket_id = str(ticket_data.get('id', ''))
        
        # API 엔드포인트와 동일한 로직 수행
        related_docs_response = await get_related_documents(ticket_id, tenant_id)
        
        # 응답 형식 변환: RelatedDocumentItem[] -> DocumentInfo[]
        kb_documents_list = []
        for item in related_docs_response.related_documents:
            # source_url이 None이면 빈 문자열로 설정하여 오류 방지
            source_url = item.url or ""
            
            kb_documents_list.append(DocumentInfo(
                title=item.title or f"문서 {item.id}",
                content=item.doc_summary or "내용 없음",
                source_id=str(item.id),
                source_url=source_url,
                relevance_score=item.similarity_score or 0.0,
                doc_type=item.source_type or "kb"
            ))
        
        return kb_documents_list[:limit]
        
    except Exception as e:
        logger.error(f"지식베이스 문서 검색 실패: {str(e)}")
        return []
