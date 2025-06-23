#!/usr/bin/env python3
"""
단순화된 스키마용 데이터 수집

기존 데이터를 단순화된 최적화 스키마로 마이그레이션
"""

import sqlite3
import json
import logging
from datetime import datetime
from pathlib import Path
import re
from typing import Dict, Any, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SimplifiedDataCollector:
    """단순화된 데이터 수집기"""
    
    def __init__(self, source_db: str, target_db: str):
        self.source_db = source_db
        self.target_db = target_db
        
    def migrate_data(self):
        """데이터 마이그레이션 실행"""
        
        logger.info(f"데이터 마이그레이션 시작: {self.source_db} -> {self.target_db}")
        
        source_conn = sqlite3.connect(self.source_db)
        target_conn = sqlite3.connect(self.target_db)
        
        try:
            source_cursor = source_conn.cursor()
            target_cursor = target_conn.cursor()
            
            # 1. 티켓 데이터 마이그레이션
            tickets_migrated = self._migrate_tickets(source_cursor, target_cursor)
            target_conn.commit()
            
            # 2. 대화 데이터 마이그레이션
            conversations_migrated = self._migrate_conversations(source_cursor, target_cursor)
            target_conn.commit()
            
            # 3. 첨부파일 데이터 마이그레이션 (있다면)
            attachments_migrated = self._migrate_attachments(source_cursor, target_cursor)
            target_conn.commit()
            
            # 4. 기존 요약 데이터 마이그레이션 (있다면)
            summaries_migrated = self._migrate_summaries(source_cursor, target_cursor)
            target_conn.commit()
            
            logger.info("✅ 데이터 마이그레이션 완료")
            logger.info(f"   - 티켓: {tickets_migrated}건")
            logger.info(f"   - 대화: {conversations_migrated}건")
            logger.info(f"   - 첨부파일: {attachments_migrated}건")
            logger.info(f"   - 요약: {summaries_migrated}건")
            
        except Exception as e:
            logger.error(f"❌ 마이그레이션 실패: {e}")
            target_conn.rollback()
            raise
        finally:
            source_conn.close()
            target_conn.close()
    
    def _migrate_tickets(self, source_cursor, target_cursor) -> int:
        """티켓 데이터 마이그레이션"""
        
        logger.info("티켓 데이터 마이그레이션 시작...")
        
        # 기존 티켓 데이터 조회
        source_cursor.execute("""
        SELECT original_id, company_id, original_data, raw_data, created_at, updated_at
        FROM integrated_objects 
        WHERE object_type = 'integrated_ticket'
        AND original_data IS NOT NULL
        """)
        
        tickets = source_cursor.fetchall()
        migrated = 0
        
        for original_id, company_id, original_data, raw_data, created_at, updated_at in tickets:
            try:
                # JSON 데이터 파싱
                data = json.loads(raw_data if raw_data else original_data)
                
                # 필수 필드 추출
                freshdesk_id = self._extract_freshdesk_id(data, original_id)
                subject = self._clean_text(data.get('subject', ''))
                description = self._extract_description(data)
                
                # 상태 정보 추출
                status = self._normalize_status(data.get('status'))
                priority = self._normalize_priority(data.get('priority'))
                
                # 담당자 정보 추출
                requester_info = self._extract_requester_info(data)
                agent_info = self._extract_agent_info(data)
                
                # 분류 정보 추출
                category = self._extract_category(data)
                tags = self._extract_tags(data)
                
                # 시간 정보 처리
                created_at_dt = self._parse_datetime(data.get('created_at', created_at))
                updated_at_dt = self._parse_datetime(data.get('updated_at', updated_at))
                
                # 티켓 삽입
                target_cursor.execute("""
                INSERT OR REPLACE INTO tickets (
                    freshdesk_id, company_domain, subject, description_text, description_html,
                    status, priority, ticket_type, source,
                    requester_email, requester_name, agent_email, agent_name,
                    category, subcategory, tags_json,
                    due_by, is_escalated, spam,
                    custom_fields_json, conversation_count, attachment_count,
                    created_at, updated_at, processed_for_summary
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    freshdesk_id,
                    company_id or 'wedosoft',
                    subject,
                    description.get('text', ''),
                    description.get('html', ''),
                    status,
                    priority,
                    data.get('type', ''),
                    data.get('source', ''),
                    requester_info.get('email', ''),
                    requester_info.get('name', ''),
                    agent_info.get('email', ''),
                    agent_info.get('name', ''),
                    category.get('primary', ''),
                    category.get('secondary', ''),
                    json.dumps(tags, ensure_ascii=False) if tags else None,
                    self._parse_datetime(data.get('due_by')),
                    bool(data.get('is_escalated', False)),
                    bool(data.get('spam', False)),
                    json.dumps(data.get('custom_fields', {}), ensure_ascii=False) if data.get('custom_fields') else None,
                    0,  # conversation_count - 나중에 업데이트
                    0,  # attachment_count - 나중에 업데이트
                    created_at_dt,
                    updated_at_dt,
                    False  # processed_for_summary
                ))
                
                migrated += 1
                
            except Exception as e:
                logger.error(f"티켓 마이그레이션 실패: {original_id} - {e}")
                continue
        
        logger.info(f"✓ 티켓 마이그레이션 완료: {migrated}건")
        return migrated
    
    def _migrate_conversations(self, source_cursor, target_cursor) -> int:
        """대화 데이터 마이그레이션"""
        
        logger.info("대화 데이터 마이그레이션 시작...")
        
        # 기존 대화 데이터 조회 (conversations 테이블에서)
        source_cursor.execute("""
        SELECT original_id, ticket_original_id, company_id, body, body_text, 
               incoming, private, created_at, updated_at, attachments, raw_data
        FROM conversations 
        WHERE raw_data IS NOT NULL
        """)
        
        conversations = source_cursor.fetchall()
        migrated = 0
        
        for row in conversations:
            try:
                (original_id, ticket_original_id, company_id, body, body_text, 
                 incoming, private, created_at, updated_at, attachments, raw_data) = row
                
                # JSON 데이터 파싱
                if raw_data:
                    data = json.loads(raw_data)
                else:
                    # raw_data가 없으면 기본 필드들로 데이터 구성
                    data = {
                        'id': original_id,
                        'ticket_id': ticket_original_id,
                        'body': body,
                        'body_text': body_text,
                        'incoming': incoming,
                        'private': private,
                        'created_at': created_at,
                        'updated_at': updated_at,
                        'attachments': json.loads(attachments) if attachments else []
                    }
                
                # 티켓 ID 찾기 (ticket_original_id 사용)
                ticket_id = None
                if ticket_original_id:
                    # original_id에서 숫자 추출
                    ticket_freshdesk_id = self._extract_id_from_original(ticket_original_id)
                    target_cursor.execute("SELECT id FROM tickets WHERE freshdesk_id = ?", (ticket_freshdesk_id,))
                    result = target_cursor.fetchone()
                    if result:
                        ticket_id = result[0]
                
                if not ticket_id:
                    continue
                
                # 대화 내용 추출 (실제 컬럼 데이터 사용)
                conversation_body_text = body_text or self._clean_text(body or '')
                conversation_body_html = body or ''
                
                # from_info는 raw_data에서 추출 시도
                from_email = data.get('from_email', '')
                from_name = data.get('from_name', '')
                
                # 시간 정보 처리
                created_at_dt = self._parse_datetime(created_at)
                updated_at_dt = self._parse_datetime(updated_at)
                
                # 첨부파일 정보
                attachment_list = []
                if attachments:
                    try:
                        attachment_list = json.loads(attachments)
                    except:
                        attachment_list = []
                
                # 대화 삽입
                target_cursor.execute("""
                INSERT OR REPLACE INTO conversations (
                    ticket_id, freshdesk_id, body_text, body_html,
                    from_email, from_name, to_emails_json, cc_emails_json,
                    incoming, private, has_attachments, attachment_count,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    ticket_id,
                    self._extract_id_from_original(original_id),
                    conversation_body_text,
                    conversation_body_html,
                    from_email,
                    from_name,
                    json.dumps(data.get('to_emails', []), ensure_ascii=False),
                    json.dumps(data.get('cc_emails', []), ensure_ascii=False),
                    bool(incoming),
                    bool(private),
                    len(attachment_list) > 0,
                    len(attachment_list),
                    created_at_dt,
                    updated_at_dt
                ))
                
                migrated += 1
                
            except Exception as e:
                logger.error(f"대화 마이그레이션 실패: {original_id} - {e}")
                continue
        
        # 티켓별 대화 수 업데이트
        target_cursor.execute("""
        UPDATE tickets SET conversation_count = (
            SELECT COUNT(*) FROM conversations WHERE ticket_id = tickets.id
        )
        """)
        
        logger.info(f"✓ 대화 마이그레이션 완료: {migrated}건")
        return migrated
    
    def _migrate_attachments(self, source_cursor, target_cursor) -> int:
        """첨부파일 데이터 마이그레이션"""
        
        logger.info("첨부파일 데이터 마이그레이션 시작...")
        
        # 원본 첨부파일 데이터 조회
        source_cursor.execute("""
        SELECT original_id, parent_type, parent_original_id, name, content_type, 
               size, created_at, updated_at, attachment_url, raw_data
        FROM attachments 
        """)
        
        attachments = source_cursor.fetchall()
        migrated = 0
        
        for row in attachments:
            try:
                (original_id, parent_type, parent_original_id, name, content_type,
                 size, created_at, updated_at, attachment_url, raw_data) = row
                
                # 부모 타입에 따라 관련 ID 찾기
                ticket_id = None
                conversation_id = None
                
                if parent_type == 'ticket':
                    # 티켓 첨부파일 - parent_original_id가 직접 ticket의 freshdesk_id
                    target_cursor.execute("SELECT id FROM tickets WHERE freshdesk_id = ?", (parent_original_id,))
                    result = target_cursor.fetchone()
                    if result:
                        ticket_id = result[0]
                
                elif parent_type == 'conversation':
                    # 대화 첨부파일 - parent_original_id가 직접 conversation의 freshdesk_id  
                    target_cursor.execute("SELECT id FROM conversations WHERE freshdesk_id = ?", (parent_original_id,))
                    result = target_cursor.fetchone()
                    if result:
                        conversation_id = result[0]
                
                elif parent_type == 'article':
                    # knowledge_base 첨부파일 - ticket_id, conversation_id는 NULL로 하고 별도 관리
                    # 이 경우 ticket_id와 conversation_id는 모두 None으로 유지
                
                # article 타입의 경우 ticket_id, conversation_id 모두 NULL이어도 처리
                # 다른 타입의 경우 ticket_id 또는 conversation_id가 있어야 함
                if parent_type != 'article' and not ticket_id and not conversation_id:
                    continue
                
                # JSON 데이터 파싱
                data = {}
                if raw_data:
                    try:
                        data = json.loads(raw_data)
                    except:
                        pass
                
                # 첨부파일 정보 추출
                file_name = name or data.get('name', 'unknown')
                file_size = size or data.get('size', 0)
                file_type = content_type or data.get('content_type', 'application/octet-stream')
                file_url = attachment_url or data.get('attachment_url', '')
                
                # 시간 정보 처리
                created_at_dt = self._parse_datetime(created_at)
                updated_at_dt = self._parse_datetime(updated_at)
                
                # 첨부파일 삽입 (단순화된 스키마에 맞게)
                target_cursor.execute("""
                INSERT OR REPLACE INTO attachments (
                    ticket_id, conversation_id, freshdesk_id, name, 
                    content_type, size_bytes, attachment_url, 
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    ticket_id,
                    conversation_id,
                    self._extract_id_from_original(original_id),
                    file_name,
                    file_type,
                    file_size,
                    file_url,
                    created_at_dt or datetime.now().isoformat(),
                    updated_at_dt or datetime.now().isoformat()
                ))
                
                migrated += 1
                
            except Exception as e:
                logger.error(f"첨부파일 마이그레이션 실패: {original_id} - {e}")
                continue
        
        # 티켓별 첨부파일 수 업데이트
        target_cursor.execute("""
        UPDATE tickets SET attachment_count = (
            SELECT COUNT(*) FROM attachments WHERE ticket_id = tickets.id
        )
        """)
        
        logger.info(f"✓ 첨부파일 마이그레이션 완료: {migrated}건")
        return migrated
    
    def _migrate_summaries(self, source_cursor, target_cursor) -> int:
        """요약 데이터 마이그레이션"""
        
        logger.info("기존 요약 데이터 마이그레이션 시작...")
        
        # 기존 요약이 있는 티켓 조회
        source_cursor.execute("""
        SELECT original_id, summary, summary_quality_score, summary_updated_at
        FROM integrated_objects 
        WHERE object_type = 'integrated_ticket'
        AND summary IS NOT NULL
        AND summary != ''
        """)
        
        summaries = source_cursor.fetchall()
        migrated = 0
        
        for original_id, summary, quality_score, updated_at in summaries:
            try:
                # 해당 티켓 ID 찾기
                target_cursor.execute("""
                SELECT id FROM tickets WHERE freshdesk_id = ?
                """, (self._extract_id_from_original(original_id),))
                
                result = target_cursor.fetchone()
                if not result:
                    continue
                
                ticket_id = result[0]
                
                # 요약 삽입
                target_cursor.execute("""
                INSERT OR REPLACE INTO summaries (
                    ticket_id, summary_text, quality_score, model_used,
                    summary_length, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    ticket_id,
                    summary,
                    quality_score or 0.0,
                    'legacy',  # 기존 모델
                    len(summary),
                    updated_at or datetime.now().isoformat(),
                    updated_at or datetime.now().isoformat()
                ))
                
                migrated += 1
                
            except Exception as e:
                logger.error(f"요약 마이그레이션 실패: {original_id} - {e}")
                continue
        
        logger.info(f"✓ 요약 마이그레이션 완료: {migrated}건")
        return migrated
    
    # 헬퍼 메서드들
    def _extract_freshdesk_id(self, data: Dict[str, Any], original_id: str) -> int:
        """Freshdesk ID 추출"""
        if 'id' in data:
            return int(data['id'])
        
        # original_id에서 숫자 추출
        match = re.search(r'\d+', original_id)
        if match:
            return int(match.group())
        
        return hash(original_id) % 1000000  # 임시 ID
    
    def _clean_text(self, text: str) -> str:
        """텍스트 정리"""
        if not text:
            return ''
        
        # HTML 태그 제거
        text = re.sub(r'<[^>]+>', '', text)
        # 여러 공백을 하나로
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def _extract_description(self, data: Dict[str, Any]) -> Dict[str, str]:
        """설명 추출"""
        description = data.get('description', '')
        description_text = data.get('description_text', '')
        
        if not description_text:
            description_text = self._clean_text(description)
        
        return {
            'text': description_text,
            'html': description
        }
    
    def _normalize_status(self, status: Any) -> str:
        """상태 정규화"""
        if not status:
            return 'Open'
        
        status_str = str(status).lower()
        
        mapping = {
            '2': 'Open',
            '3': 'Pending',
            '4': 'Resolved',
            '5': 'Closed',
            'open': 'Open',
            'pending': 'Pending',
            'resolved': 'Resolved',
            'closed': 'Closed'
        }
        
        return mapping.get(status_str, str(status))
    
    def _normalize_priority(self, priority: Any) -> str:
        """우선순위 정규화"""
        if not priority:
            return 'Medium'
        
        priority_str = str(priority).lower()
        
        mapping = {
            '1': 'Low',
            '2': 'Medium',
            '3': 'High',
            '4': 'Urgent',
            'low': 'Low',
            'medium': 'Medium',
            'high': 'High',
            'urgent': 'Urgent'
        }
        
        return mapping.get(priority_str, str(priority))
    
    def _extract_requester_info(self, data: Dict[str, Any]) -> Dict[str, str]:
        """요청자 정보 추출"""
        requester = data.get('requester', {})
        if isinstance(requester, dict):
            return {
                'email': requester.get('email', ''),
                'name': requester.get('name', '')
            }
        return {'email': '', 'name': ''}
    
    def _extract_agent_info(self, data: Dict[str, Any]) -> Dict[str, str]:
        """담당자 정보 추출"""
        agent = data.get('responder', {})
        if isinstance(agent, dict):
            return {
                'email': agent.get('email', ''),
                'name': agent.get('name', '')
            }
        return {'email': '', 'name': ''}
    
    def _extract_category(self, data: Dict[str, Any]) -> Dict[str, str]:
        """카테고리 정보 추출"""
        category = data.get('category', '')
        sub_category = data.get('sub_category', '')
        
        return {
            'primary': str(category) if category else '',
            'secondary': str(sub_category) if sub_category else ''
        }
    
    def _extract_tags(self, data: Dict[str, Any]) -> list:
        """태그 추출"""
        tags = data.get('tags', [])
        if isinstance(tags, list):
            return [str(tag) for tag in tags]
        return []
    
    def _parse_datetime(self, dt_str: Any) -> Optional[str]:
        """날짜 시간 파싱"""
        if not dt_str:
            return None
        
        try:
            # 이미 ISO 형식인 경우
            if isinstance(dt_str, str) and 'T' in dt_str:
                return dt_str
            
            # 다른 형식의 경우 파싱 시도
            # 실제 데이터에 맞게 조정 필요
            return str(dt_str)
            
        except:
            return None
    
    def _find_ticket_id(self, cursor, data: Dict[str, Any]) -> Optional[int]:
        """대화의 티켓 ID 찾기"""
        # ticket_id 직접 확인
        ticket_id = data.get('ticket_id')
        if ticket_id:
            cursor.execute("SELECT id FROM tickets WHERE freshdesk_id = ?", (ticket_id,))
            result = cursor.fetchone()
            if result:
                return result[0]
        
        return None
    
    def _extract_conversation_body(self, data: Dict[str, Any]) -> Dict[str, str]:
        """대화 본문 추출"""
        body = data.get('body', '')
        body_text = data.get('body_text', '')
        
        if not body_text:
            body_text = self._clean_text(body)
        
        return {
            'text': body_text,
            'html': body
        }
    
    def _extract_from_info(self, data: Dict[str, Any]) -> Dict[str, str]:
        """발신자 정보 추출"""
        from_email = data.get('from_email', '')
        from_name = data.get('from_name', '')
        
        # user_id로부터 정보 추출 시도
        if not from_email and 'user_id' in data:
            # 실제로는 사용자 정보를 별도로 조회해야 함
            pass
        
        return {
            'email': from_email,
            'name': from_name
        }
    
    def _extract_id_from_original(self, original_id: str) -> int:
        """original_id에서 숫자 ID 추출"""
        match = re.search(r'\d+', original_id)
        if match:
            return int(match.group())
        return 0


def main():
    """메인 함수"""
    
    print("🚀 단순화된 스키마 데이터 마이그레이션")
    print("📊 기존 데이터 -> 최적화된 스키마")
    
    source_db = "core/data/wedosoft_freshdesk_data.db"
    target_db = "core/data/wedosoft_freshdesk_data_simplified.db"
    
    # 소스 데이터베이스 존재 확인
    if not Path(source_db).exists():
        print(f"❌ 소스 데이터베이스가 없습니다: {source_db}")
        return
    
    # 타겟 데이터베이스 존재 확인
    if not Path(target_db).exists():
        print(f"❌ 타겟 데이터베이스가 없습니다: {target_db}")
        print("먼저 create_simplified_schema.py를 실행하세요.")
        return
    
    # 마이그레이션 실행
    collector = SimplifiedDataCollector(source_db, target_db)
    collector.migrate_data()
    
    print("\n✨ 데이터 마이그레이션 완료!")
    print("이제 batch_summarizer.py로 요약을 생성할 수 있습니다.")


if __name__ == "__main__":
    main()
