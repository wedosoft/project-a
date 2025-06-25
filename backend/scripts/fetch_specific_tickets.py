#!/usr/bin/env python3
"""
특정 티켓을 Freshdesk API에서 가져와서 SQL DB에만 저장하는 스크립트

지정된 티켓 ID들을 Freshdesk API에서 직접 가져와서:
1. LLM을 사용해 티켓과 대화 내용을 요약
2. SQL 데이터베이스에만 저장 (벡터 DB는 제외)

이 스크립트는 실제 데이터가 어떻게 요약되는지 테스트하는 용도입니다.

Usage:
    python scripts/fetch_specific_tickets.py --ticket-ids 12345 67890
    python scripts/fetch_specific_tickets.py --file ticket_ids.txt
    python scripts/fetch_specific_tickets.py --ticket-ids 12345 --domain mydomain --api-key mykey
"""

import asyncio
import argparse
import sys
import os
from pathlib import Path
from typing import List, Optional
from datetime import datetime
import logging

# 프로젝트 루트를 Python 패스에 추가
script_dir = Path(__file__).parent
backend_dir = script_dir.parent
sys.path.insert(0, str(backend_dir))

# .env 파일 로드
from dotenv import load_dotenv
load_dotenv(backend_dir / '.env')

from core.platforms.freshdesk.fetcher import fetch_ticket_details
from core.database.database import get_database
from core.ingest.integrator import create_integrated_ticket_object
from core.ingest.storage import store_integrated_object_to_sqlite
from core.llm.summarizer import generate_summary

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SpecificTicketIngester:
    """특정 티켓들을 Freshdesk API에서 가져와서 LLM 요약 후 SQL DB에만 저장하는 클래스"""
    
    def __init__(self, domain: Optional[str] = None, api_key: Optional[str] = None, 
                 company_id: Optional[str] = None, platform: str = "freshdesk"):
        self.domain = domain
        self.api_key = api_key
        self.company_id = company_id or "default"
        self.platform = platform
        self.db = None
        
    async def fetch_and_store_tickets(self, ticket_ids: List[int]) -> dict:
        """
        지정된 티켓 ID들을 Freshdesk API에서 가져와서 LLM 요약 후 SQL DB에 저장
        
        Args:
            ticket_ids: 가져올 티켓 ID 리스트
            
        Returns:
            dict: 처리 결과 요약
        """
        logger.info(f"🎯 특정 티켓 수집 시작: {len(ticket_ids)}개 티켓")
        logger.info(f"📋 티켓 ID 목록: {ticket_ids}")
        
        # DB 연결
        self.db = get_database(self.company_id, self.platform)
        logger.info(f"💾 SQL DB 연결 완료: {self.db.db_path}")
        
        results = {
            "total_requested": len(ticket_ids),
            "success": 0,
            "failed": 0,
            "already_exists": 0,
            "failed_tickets": [],
            "success_tickets": []
        }
        
        for i, ticket_id in enumerate(ticket_ids, 1):
            logger.info(f"\n📋 처리 중: 티켓 {ticket_id} ({i}/{len(ticket_ids)})")
            
            try:
                # 이미 DB에 존재하는지 확인
                if await self._check_ticket_exists(ticket_id):
                    logger.info(f"⏭️  티켓 {ticket_id}이 이미 SQL DB에 존재합니다. 건너뜀")
                    results["already_exists"] += 1
                    continue
                
                # Freshdesk API에서 티켓 상세 정보 가져오기
                logger.info(f"🔄 Freshdesk API에서 티켓 {ticket_id} 가져오는 중...")
                ticket_data = await fetch_ticket_details(
                    ticket_id=ticket_id,
                    domain=self.domain,
                    api_key=self.api_key
                )
                
                if not ticket_data:
                    logger.warning(f"❌ 티켓 {ticket_id}를 찾을 수 없습니다 (404 또는 API 오류)")
                    results["failed"] += 1
                    results["failed_tickets"].append({"id": ticket_id, "reason": "Not found or API error"})
                    continue
                
                logger.info(f"✅ 티켓 {ticket_id} API 응답 수신 완료")
                
                # 통합 객체 생성
                logger.info(f"🤖 티켓 {ticket_id} 통합 객체 생성 중...")
                integrated_ticket = create_integrated_ticket_object(
                    ticket_data, 
                    company_id=self.company_id
                )
                logger.info(f"🔧 통합 티켓 객체 생성 완료: ID={integrated_ticket.get('id')}")
                
                # LLM을 사용해 요약 생성
                logger.info(f"🧠 티켓 {ticket_id} LLM 요약 생성 중...")
                try:
                    # 티켓 내용 추출
                    content_parts = []
                    
                    # 티켓 제목과 설명
                    subject = integrated_ticket.get('subject', '')
                    description = integrated_ticket.get('description_text', '')
                    if subject:
                        content_parts.append(f"제목: {subject}")
                    if description:
                        content_parts.append(f"설명: {description}")
                    
                    # 대화 내용 추가
                    conversations = integrated_ticket.get('conversations', [])
                    if conversations:
                        content_parts.append("대화 내용:")
                        for conv in conversations[:10]:  # 최근 10개만
                            if isinstance(conv, dict):
                                sender = "고객" if conv.get('user_id') else "상담원"
                                body = conv.get('body_text', conv.get('body', ''))
                                if body:
                                    content_parts.append(f"- {sender}: {body[:200]}...")
                    
                    full_content = "\n".join(content_parts)
                    
                    # 첨부파일 메타데이터 추가
                    attachments = integrated_ticket.get('attachments', [])
                    metadata = {'attachments': attachments} if attachments else None
                    
                    # 요약 생성
                    summary = await generate_summary(
                        content=full_content,
                        content_type="ticket",
                        subject=subject,
                        metadata=metadata,
                        ui_language="ko"
                    )
                    
                    # 통합 객체에 요약 추가
                    integrated_ticket['ai_summary'] = summary
                    integrated_ticket['summary_generated_at'] = datetime.now().isoformat()
                    
                    logger.info(f"✅ 티켓 {ticket_id} LLM 요약 생성 완료 (길이: {len(summary)} 문자)")
                    
                except Exception as e:
                    logger.warning(f"⚠️  티켓 {ticket_id} 요약 생성 실패: {e}")
                    integrated_ticket['ai_summary'] = "요약 생성에 실패했습니다."
                    integrated_ticket['summary_error'] = str(e)
                
                # SQL DB에만 저장 (벡터 DB 제외)
                store_result = store_integrated_object_to_sqlite(
                    self.db, 
                    integrated_ticket, 
                    self.company_id, 
                    self.platform
                )
                
                if store_result:
                    logger.info(f"💾 ✅ 티켓 {ticket_id} SQL DB 저장 성공")
                    results["success"] += 1
                    results["success_tickets"].append(ticket_id)
                else:
                    logger.error(f"💾 ❌ 티켓 {ticket_id} SQL DB 저장 실패")
                    results["failed"] += 1
                    results["failed_tickets"].append({"id": ticket_id, "reason": "SQL storage failed"})
                    
            except Exception as e:
                logger.error(f"❌ 티켓 {ticket_id} 처리 중 오류 발생: {e}", exc_info=True)
                results["failed"] += 1
                results["failed_tickets"].append({"id": ticket_id, "reason": str(e)})
        
        # DB 연결 해제
        if self.db:
            self.db.disconnect()
            logger.info("💾 SQL DB 연결 해제")
        
        return results
    
    async def _check_ticket_exists(self, ticket_id: int) -> bool:
        """SQL DB에 티켓이 이미 존재하는지 확인"""
        try:
            cursor = self.db.connection.cursor()
            cursor.execute("SELECT id FROM tickets WHERE original_id = ? LIMIT 1", (str(ticket_id),))
            result = cursor.fetchone()
            return result is not None
        except Exception as e:
            logger.warning(f"티켓 {ticket_id} 존재 여부 확인 중 오류: {e}")
            return False


def parse_ticket_ids_from_file(file_path: str) -> List[int]:
    """파일에서 티켓 ID 목록을 읽어옴"""
    ticket_ids = []
    try:
        with open(file_path, 'r') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith('#'):  # 빈 줄이나 주석 건너뜀
                    continue
                try:
                    ticket_id = int(line)
                    ticket_ids.append(ticket_id)
                except ValueError:
                    logger.warning(f"파일 {file_path} 라인 {line_num}: 유효하지 않은 티켓 ID '{line}' 건너뜀")
        
        logger.info(f"📄 파일에서 {len(ticket_ids)}개 티켓 ID 읽음: {file_path}")
        return ticket_ids
        
    except FileNotFoundError:
        logger.error(f"❌ 파일을 찾을 수 없습니다: {file_path}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ 파일 읽기 오류: {e}")
        sys.exit(1)


async def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(
        description="특정 티켓을 Freshdesk API에서 가져와서 SQL DB에만 저장",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  python scripts/fetch_specific_tickets.py --ticket-ids 12345 67890
  python scripts/fetch_specific_tickets.py --file ticket_ids.txt
  python scripts/fetch_specific_tickets.py --ticket-ids 12345 --domain mydomain --api-key mykey
        """
    )
    
    # 티켓 ID 지정 방법 (둘 중 하나 선택)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--ticket-ids", 
        nargs="+", 
        type=int, 
        help="가져올 티켓 ID들 (공백으로 구분)"
    )
    group.add_argument(
        "--file", 
        help="티켓 ID가 포함된 텍스트 파일 경로 (한 줄에 하나씩)"
    )
    
    # 선택적 파라미터
    parser.add_argument("--domain", help="Freshdesk 도메인 (환경변수 사용하지 않을 경우)")
    parser.add_argument("--api-key", help="Freshdesk API 키 (환경변수 사용하지 않을 경우)")
    parser.add_argument("--company-id", default="default", help="회사 ID (기본값: default)")
    parser.add_argument("--platform", default="freshdesk", help="플랫폼 (기본값: freshdesk)")
    parser.add_argument("--dry-run", action="store_true", help="실제 저장하지 않고 테스트만 실행")
    
    args = parser.parse_args()
    
    # 티켓 ID 목록 가져오기
    if args.file:
        ticket_ids = parse_ticket_ids_from_file(args.file)
    else:
        # argparse는 --ticket-ids를 ticket_ids 속성으로 변환
        ticket_ids = getattr(args, 'ticket_ids', None) or []
    
    if not ticket_ids:
        logger.error("❌ 처리할 티켓 ID가 없습니다.")
        sys.exit(1)
    
    # 중복 제거 및 정렬
    ticket_ids = sorted(list(set(ticket_ids)))
    logger.info(f"🎯 처리할 고유 티켓 수: {len(ticket_ids)}개")
    
    if args.dry_run:
        logger.info("🧪 DRY RUN 모드: 실제 저장하지 않고 테스트만 실행")
        logger.info(f"📋 처리 예정 티켓 ID: {ticket_ids}")
        return
    
    # 티켓 수집 및 저장 실행
    ingester = SpecificTicketIngester(
        domain=args.domain,
        api_key=args.api_key,
        company_id=args.company_id,
        platform=args.platform
    )
    
    try:
        results = await ingester.fetch_and_store_tickets(ticket_ids)
        
        # 결과 요약 출력
        print("\n" + "="*60)
        print("📊 처리 결과 요약")
        print("="*60)
        print(f"📋 요청된 티켓 수:      {results['total_requested']}개")
        print(f"✅ 성공:               {results['success']}개")
        print(f"❌ 실패:               {results['failed']}개")
        print(f"⏭️  이미 존재:          {results['already_exists']}개")
        
        if results["success_tickets"]:
            print(f"\n✅ 성공한 티켓 ID: {results['success_tickets']}")
        
        if results["failed_tickets"]:
            print(f"\n❌ 실패한 티켓:")
            for failed in results["failed_tickets"]:
                print(f"   - 티켓 {failed['id']}: {failed['reason']}")
        
        print("="*60)
        
        if results["failed"] > 0:
            sys.exit(1)  # 실패가 있으면 비정상 종료
            
    except KeyboardInterrupt:
        logger.info("\n⚠️  사용자에 의해 중단되었습니다.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ 처리 중 예상치 못한 오류 발생: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
