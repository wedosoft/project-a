#!/usr/bin/env python3
"""
최적화된 스키마용 Freshdesk 데이터 수집기

새로운 정규화된 스키마에 맞춰 데이터를 효율적으로 수집하고 저장
"""

import asyncio
import sqlite3
import json
import gzip
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import aiohttp
import time
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OptimizedFreshdeskCollector:
    """최적화된 Freshdesk 데이터 수집기"""
    
    def __init__(self, db_path: str, api_key: str, domain: str):
        self.db_path = db_path
        self.api_key = api_key
        self.domain = domain
        self.base_url = f"https://{domain}.freshdesk.com/api/v2"
        self.company_id = None
        
        # 수집 통계
        self.stats = {
            'tickets_collected': 0,
            'conversations_collected': 0,
            'attachments_collected': 0,
            'errors': 0,
            'start_time': None,
            'end_time': None
        }
    
    async def collect_all_data(self, limit: Optional[int] = None):
        """전체 데이터 수집"""
        
        logger.info("🚀 최적화된 Freshdesk 데이터 수집 시작")
        self.stats['start_time'] = datetime.now()
        
        try:
            # 1. 회사 정보 설정
            await self._setup_company()
            
            # 2. 마스터 데이터 수집 (상담원, 카테고리 등)
            await self._collect_master_data()
            
            # 3. 티켓 데이터 수집
            await self._collect_tickets(limit)
            
            # 4. 대화 및 첨부파일 수집
            await self._collect_conversations_and_attachments()
            
            # 5. 통계 업데이트
            await self._update_statistics()
            
            self.stats['end_time'] = datetime.now()
            
            # 최종 리포트
            self._print_collection_report()
            
        except Exception as e:
            logger.error(f"❌ 데이터 수집 실패: {e}")
            raise
    
    async def _setup_company(self):
        """회사 정보 설정"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # 기존 회사 정보 확인
            cursor.execute(
                "SELECT id FROM companies WHERE freshdesk_domain = ?",
                (self.domain,)
            )
            
            result = cursor.fetchone()
            if result:
                self.company_id = result[0]
                logger.info(f"✓ 기존 회사 정보 사용: {self.domain} (ID: {self.company_id})")
            else:
                # 새 회사 정보 생성
                cursor.execute(
                    """
                    INSERT INTO companies (freshdesk_domain, company_name, api_key_hash, created_at)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                    (self.domain, self.domain, hash(self.api_key))
                )
                self.company_id = cursor.lastrowid
                conn.commit()
                logger.info(f"✓ 새 회사 정보 생성: {self.domain} (ID: {self.company_id})")
                
        finally:
            conn.close()
    
    async def _collect_master_data(self):
        """마스터 데이터 수집 (상담원, 카테고리)"""
        
        logger.info("📋 마스터 데이터 수집 중...")
        
        async with aiohttp.ClientSession() as session:
            # 상담원 정보 수집
            await self._collect_agents(session)
            
            # 카테고리 정보 수집
            await self._collect_categories(session)
    
    async def _collect_agents(self, session: aiohttp.ClientSession):
        """상담원 정보 수집"""
        
        try:
            url = f"{self.base_url}/agents"
            async with session.get(url, auth=aiohttp.BasicAuth(self.api_key, 'X')) as response:
                if response.status == 200:
                    agents = await response.json()
                    
                    conn = sqlite3.connect(self.db_path)
                    cursor = conn.cursor()
                    
                    try:
                        for agent in agents:
                            cursor.execute(
                                """
                                INSERT OR REPLACE INTO agents 
                                (company_id, freshdesk_id, email, name, role, active, created_at, updated_at)
                                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                                """,
                                (
                                    self.company_id,
                                    agent['id'],
                                    agent.get('email', ''),
                                    agent.get('name', ''),
                                    agent.get('role', ''),
                                    agent.get('available', True)
                                )
                            )
                        
                        conn.commit()
                        logger.info(f"✓ 상담원 {len(agents)}명 수집 완료")
                        
                    finally:
                        conn.close()
                        
        except Exception as e:
            logger.error(f"❌ 상담원 정보 수집 실패: {e}")
            self.stats['errors'] += 1
    
    async def _collect_categories(self, session: aiohttp.ClientSession):
        """카테고리 정보 수집"""
        
        try:
            url = f"{self.base_url}/ticket_fields"
            async with session.get(url, auth=aiohttp.BasicAuth(self.api_key, 'X')) as response:
                if response.status == 200:
                    fields = await response.json()
                    
                    # 카테고리 필드 찾기
                    category_field = None
                    for field in fields:
                        if field.get('name') == 'category':
                            category_field = field
                            break
                    
                    if category_field and 'choices' in category_field:
                        conn = sqlite3.connect(self.db_path)
                        cursor = conn.cursor()
                        
                        try:
                            for choice in category_field['choices']:
                                cursor.execute(
                                    """
                                    INSERT OR REPLACE INTO categories 
                                    (company_id, freshdesk_id, name, created_at)
                                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                                    """,
                                    (
                                        self.company_id,
                                        choice['id'],
                                        choice['value']
                                    )
                                )
                            
                            conn.commit()
                            logger.info(f"✓ 카테고리 {len(category_field['choices'])}개 수집 완료")
                            
                        finally:
                            conn.close()
                            
        except Exception as e:
            logger.error(f"❌ 카테고리 정보 수집 실패: {e}")
            self.stats['errors'] += 1
    
    async def _collect_tickets(self, limit: Optional[int] = None):
        """티켓 데이터 수집"""
        
        logger.info("🎫 티켓 데이터 수집 중...")
        
        async with aiohttp.ClientSession() as session:
            page = 1
            collected = 0
            
            while True:
                try:
                    # API 요청
                    url = f"{self.base_url}/tickets"
                    params = {
                        'page': page,
                        'per_page': 100,
                        'include': 'description,requester'
                    }
                    
                    async with session.get(
                        url, 
                        params=params,
                        auth=aiohttp.BasicAuth(self.api_key, 'X')
                    ) as response:
                        
                        if response.status == 200:
                            tickets = await response.json()
                            
                            if not tickets:
                                break
                            
                            # 데이터베이스에 저장
                            await self._save_tickets(tickets)
                            
                            collected += len(tickets)
                            self.stats['tickets_collected'] = collected
                            
                            logger.info(f"📦 페이지 {page}: {len(tickets)}개 티켓 수집 (총 {collected:,}개)")
                            
                            # 제한 확인
                            if limit and collected >= limit:
                                logger.info(f"🎯 제한에 도달: {limit:,}개")
                                break
                            
                            page += 1
                            
                            # Rate limiting
                            await asyncio.sleep(0.5)
                            
                        elif response.status == 429:
                            # Rate limit 대기
                            wait_time = int(response.headers.get('Retry-After', 60))
                            logger.warning(f"⏳ Rate limit 대기: {wait_time}초")
                            await asyncio.sleep(wait_time)
                            
                        else:
                            logger.error(f"❌ API 오류: {response.status}")
                            break
                            
                except Exception as e:
                    logger.error(f"❌ 티켓 수집 오류 (페이지 {page}): {e}")
                    self.stats['errors'] += 1
                    await asyncio.sleep(5)  # 에러 후 대기
                    continue
        
        logger.info(f"✅ 티켓 수집 완료: {self.stats['tickets_collected']:,}개")
    
    async def _save_tickets(self, tickets: List[Dict[str, Any]]):
        """티켓 데이터 저장"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            for ticket in tickets:
                # HTML에서 텍스트 추출
                description_text = self._extract_text_from_html(
                    ticket.get('description', '')
                )
                
                # 태그 JSON 압축
                tags_json = json.dumps(ticket.get('tags', []), ensure_ascii=False)
                
                # 커스텀 필드 JSON 압축
                custom_fields = ticket.get('custom_fields', {})
                custom_fields_json = json.dumps(custom_fields, ensure_ascii=False)
                
                # 티켓 저장
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO tickets (
                        company_id, freshdesk_id, subject, description_text, description_html,
                        status_id, priority_id, category_id, type_id, source_id,
                        requester_id, agent_id, group_id,
                        due_by, fr_due_by, is_escalated, spam,
                        tags_json, custom_fields_json,
                        created_at, updated_at, resolved_at, closed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        self.company_id,
                        ticket['id'],
                        ticket.get('subject', ''),
                        description_text,
                        ticket.get('description', ''),
                        ticket.get('status', 2),
                        ticket.get('priority', 1),
                        ticket.get('category_id'),
                        ticket.get('type'),
                        ticket.get('source'),
                        ticket.get('requester_id'),
                        ticket.get('responder_id'),
                        ticket.get('group_id'),
                        self._parse_datetime(ticket.get('due_by')),
                        self._parse_datetime(ticket.get('fr_due_by')),
                        ticket.get('is_escalated', False),
                        ticket.get('spam', False),
                        tags_json,
                        custom_fields_json,
                        self._parse_datetime(ticket.get('created_at')),
                        self._parse_datetime(ticket.get('updated_at')),
                        self._parse_datetime(ticket.get('stats', {}).get('resolved_at')),
                        self._parse_datetime(ticket.get('stats', {}).get('closed_at'))
                    )
                )
            
            conn.commit()
            
        finally:
            conn.close()
    
    async def _collect_conversations_and_attachments(self):
        """대화 및 첨부파일 수집"""
        
        logger.info("💬 대화 및 첨부파일 수집 중...")
        
        # 데이터베이스에서 티켓 ID 목록 조회
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT id, freshdesk_id FROM tickets WHERE company_id = ? ORDER BY created_at DESC",
            (self.company_id,)
        )
        
        tickets = cursor.fetchall()
        conn.close()
        
        logger.info(f"📊 대화 수집 대상: {len(tickets):,}개 티켓")
        
        async with aiohttp.ClientSession() as session:
            # 동시 처리를 위한 세마포어
            semaphore = asyncio.Semaphore(5)
            
            # 배치 단위로 처리
            batch_size = 50
            for i in range(0, len(tickets), batch_size):
                batch = tickets[i:i + batch_size]
                
                tasks = [
                    self._collect_ticket_conversations(session, semaphore, ticket_id, freshdesk_id)
                    for ticket_id, freshdesk_id in batch
                ]
                
                await asyncio.gather(*tasks, return_exceptions=True)
                
                # 진행 상황 출력
                processed = min(i + batch_size, len(tickets))
                logger.info(f"📈 진행률: {processed:,}/{len(tickets):,} ({processed/len(tickets)*100:.1f}%)")
                
                # 배치 간 잠시 대기
                await asyncio.sleep(1)
        
        logger.info(f"✅ 대화 수집 완료: {self.stats['conversations_collected']:,}개")
        logger.info(f"✅ 첨부파일 수집 완료: {self.stats['attachments_collected']:,}개")
    
    async def _collect_ticket_conversations(
        self, 
        session: aiohttp.ClientSession, 
        semaphore: asyncio.Semaphore,
        ticket_id: int, 
        freshdesk_id: int
    ):
        """개별 티켓의 대화 수집"""
        
        async with semaphore:
            try:
                url = f"{self.base_url}/tickets/{freshdesk_id}/conversations"
                
                async with session.get(url, auth=aiohttp.BasicAuth(self.api_key, 'X')) as response:
                    if response.status == 200:
                        conversations = await response.json()
                        
                        if conversations:
                            await self._save_conversations(ticket_id, conversations)
                            self.stats['conversations_collected'] += len(conversations)
                            
                    elif response.status == 429:
                        # Rate limit 대기
                        wait_time = int(response.headers.get('Retry-After', 10))
                        await asyncio.sleep(wait_time)
                        
            except Exception as e:
                logger.error(f"❌ 티켓 {freshdesk_id} 대화 수집 실패: {e}")
                self.stats['errors'] += 1
    
    async def _save_conversations(self, ticket_id: int, conversations: List[Dict[str, Any]]):
        """대화 데이터 저장"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            for conv in conversations:
                # HTML에서 텍스트 추출
                body_text = self._extract_text_from_html(conv.get('body', ''))
                
                # 대화 저장
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO conversations (
                        ticket_id, freshdesk_id, body_text, body_html,
                        user_id, from_email, incoming, private, source_id,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        ticket_id,
                        conv['id'],
                        body_text,
                        conv.get('body', ''),
                        conv.get('user_id'),
                        conv.get('from_email', ''),
                        conv.get('incoming', True),
                        conv.get('private', False),
                        conv.get('source'),
                        self._parse_datetime(conv.get('created_at')),
                        self._parse_datetime(conv.get('updated_at'))
                    )
                )
                
                conversation_id = cursor.lastrowid
                
                # 첨부파일 저장
                attachments = conv.get('attachments', [])
                if attachments:
                    await self._save_attachments(cursor, conversation_id, attachments)
                    self.stats['attachments_collected'] += len(attachments)
            
            conn.commit()
            
        finally:
            conn.close()
    
    async def _save_attachments(self, cursor, conversation_id: int, attachments: List[Dict[str, Any]]):
        """첨부파일 저장"""
        
        for att in attachments:
            cursor.execute(
                """
                INSERT OR REPLACE INTO attachments (
                    conversation_id, freshdesk_id, name, content_type, size_bytes,
                    attachment_url, download_url, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    conversation_id,
                    att['id'],
                    att.get('name', ''),
                    att.get('content_type', ''),
                    att.get('size', 0),
                    att.get('attachment_url', ''),
                    att.get('download_url', '')
                )
            )
    
    async def _update_statistics(self):
        """통계 정보 업데이트"""
        
        logger.info("📊 통계 정보 업데이트 중...")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # 티켓별 대화 수 업데이트
            cursor.execute(
                """
                UPDATE tickets 
                SET conversation_count = (
                    SELECT COUNT(*) 
                    FROM conversations 
                    WHERE ticket_id = tickets.id
                )
                WHERE company_id = ?
                """,
                (self.company_id,)
            )
            
            # 대화별 첨부파일 수 업데이트
            cursor.execute(
                """
                UPDATE conversations 
                SET attachment_count = (
                    SELECT COUNT(*) 
                    FROM attachments 
                    WHERE conversation_id = conversations.id
                )
                """)
            
            conn.commit()
            logger.info("✓ 통계 정보 업데이트 완료")
            
        finally:
            conn.close()
    
    def _extract_text_from_html(self, html_content: str) -> str:
        """HTML에서 순수 텍스트 추출"""
        if not html_content:
            return ""
        
        # 간단한 HTML 태그 제거 (실제로는 BeautifulSoup 사용 권장)
        import re
        text = re.sub(r'<[^>]+>', '', html_content)
        text = text.replace('&nbsp;', ' ').replace('&amp;', '&')
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    
    def _parse_datetime(self, dt_string: Optional[str]) -> Optional[str]:
        """날짜/시간 문자열 파싱"""
        if not dt_string:
            return None
        
        try:
            # ISO 형식 날짜 파싱
            dt = datetime.fromisoformat(dt_string.replace('Z', '+00:00'))
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        except:
            return dt_string
    
    def _print_collection_report(self):
        """수집 리포트 출력"""
        
        duration = self.stats['end_time'] - self.stats['start_time']
        
        print("\n" + "="*60)
        print("📊 Freshdesk 데이터 수집 완료 리포트")
        print("="*60)
        
        print(f"\n🏢 회사: {self.domain} (ID: {self.company_id})")
        print(f"⏱️  소요 시간: {duration}")
        
        print(f"\n📈 수집 통계:")
        print(f"  🎫 티켓: {self.stats['tickets_collected']:,}개")
        print(f"  💬 대화: {self.stats['conversations_collected']:,}개")
        print(f"  📎 첨부파일: {self.stats['attachments_collected']:,}개")
        print(f"  ❌ 오류: {self.stats['errors']:,}개")
        
        # 성능 통계
        if duration.total_seconds() > 0:
            tickets_per_sec = self.stats['tickets_collected'] / duration.total_seconds()
            print(f"\n⚡ 성능:")
            print(f"  초당 티켓 처리: {tickets_per_sec:.2f}개/초")
        
        print(f"\n💾 데이터베이스: {self.db_path}")
        print("="*60)


async def main():
    """메인 함수"""
    
    import argparse
    
    parser = argparse.ArgumentParser(description="최적화된 Freshdesk 데이터 수집")
    parser.add_argument("--db-path", default="core/data/wedosoft_freshdesk_data_optimized.db", help="데이터베이스 경로")
    parser.add_argument("--api-key", required=True, help="Freshdesk API 키")
    parser.add_argument("--domain", required=True, help="Freshdesk 도메인")
    parser.add_argument("--limit", type=int, help="수집할 최대 티켓 수")
    
    args = parser.parse_args()
    
    # 데이터베이스 존재 확인
    if not Path(args.db_path).exists():
        print(f"❌ 데이터베이스가 존재하지 않습니다: {args.db_path}")
        print("먼저 create_optimized_schema.py를 실행해주세요.")
        return
    
    # 수집기 실행
    collector = OptimizedFreshdeskCollector(args.db_path, args.api_key, args.domain)
    await collector.collect_all_data(args.limit)


if __name__ == "__main__":
    asyncio.run(main())
