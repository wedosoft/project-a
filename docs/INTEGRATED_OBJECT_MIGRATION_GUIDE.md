# 🗂️ 통합 객체 중심 마이그레이션 가이드

## 📋 개요

기존의 분산된 테이블 구조(`tickets`, `conversations`, `attachments`)에서 **통합 객체 중심 구조**(`integrated_objects`)로 완전히 마이그레이션하는 가이드입니다.

## 🎯 마이그레이션 목표

### Before (기존 구조)
```
tickets (기본 정보)
├── conversations (대화내역) 
└── attachments (첨부파일)
```

### After (통합 객체 구조)
```
integrated_objects (모든 데이터 통합)
├── original_data: 완전한 JSON 데이터
├── integrated_content: LLM 처리용 통합 텍스트  
├── summary: AI 생성 요약
└── metadata: 검색/필터링용 구조화 데이터
```

## 🔄 마이그레이션 단계

### 1단계: 통합 객체 스키마 배포

```sql
-- 새로운 통합 스키마 적용
-- docs/INTEGRATED_OBJECT_SCHEMA.sql 실행
```

### 2단계: 기존 데이터 통합 객체로 변환

#### A. 티켓 데이터 통합

```python
import json
from datetime import datetime

def migrate_tickets_to_integrated_objects(db):
    """기존 티켓을 통합 객체로 마이그레이션"""
    
    cursor = db.cursor()
    
    # 1. 모든 티켓 조회 (대화, 첨부파일 포함)
    cursor.execute("""
        SELECT DISTINCT t.id, t.company_id, t.platform
        FROM tickets t
        WHERE t.company_id IS NOT NULL
        ORDER BY t.id
    """)
    
    tickets = cursor.fetchall()
    
    for ticket_row in tickets:
        ticket_id, company_id, platform = ticket_row
        
        try:
            # 2. 티켓 상세 정보 수집
            ticket_data = get_full_ticket_data(db, ticket_id)
            conversations = get_ticket_conversations(db, ticket_id)
            attachments = get_ticket_attachments(db, ticket_id)
            
            # 3. 통합 객체 생성
            integrated_object = create_integrated_ticket_object(
                ticket=ticket_data,
                conversations=conversations,
                attachments=attachments,
                company_id=company_id
            )
            
            # 4. integrated_objects 테이블에 저장
            insert_integrated_object(db, {
                'original_id': str(ticket_id),
                'company_id': company_id,
                'platform': platform or 'freshdesk',
                'object_type': 'integrated_ticket',
                'original_data': integrated_object,
                'integrated_content': integrated_object.get('integrated_text', ''),
                'metadata': create_ticket_metadata(integrated_object)
            })
            
            print(f"✅ 티켓 {ticket_id} 마이그레이션 완료")
            
        except Exception as e:
            print(f"❌ 티켓 {ticket_id} 마이그레이션 실패: {e}")

def create_ticket_metadata(integrated_object):
    """티켓 메타데이터 생성"""
    return {
        'subject': integrated_object.get('subject'),
        'status': integrated_object.get('status'),
        'priority': integrated_object.get('priority'),
        'has_conversations': integrated_object.get('has_conversations', False),
        'has_attachments': integrated_object.get('has_attachments', False),
        'conversation_count': integrated_object.get('conversation_count', 0),
        'attachment_count': integrated_object.get('attachment_count', 0),
        'created_at': integrated_object.get('created_at'),
        'updated_at': integrated_object.get('updated_at'),
        'requester_email': integrated_object.get('requester_email'),
        'agent_email': integrated_object.get('agent_email')
    }
```

#### B. 지식베이스 문서 통합

```python
def migrate_articles_to_integrated_objects(db):
    """기존 문서를 통합 객체로 마이그레이션"""
    
    cursor = db.cursor()
    
    # articles 테이블이 있다면
    cursor.execute("""
        SELECT id, company_id, platform, title, description, status
        FROM articles
        WHERE company_id IS NOT NULL
    """)
    
    articles = cursor.fetchall()
    
    for article in articles:
        article_id, company_id, platform, title, description, status = article
        
        try:
            # 문서 상세 정보 수집
            article_data = get_full_article_data(db, article_id)
            attachments = get_article_attachments(db, article_id)
            
            # 통합 객체 생성
            integrated_object = create_integrated_article_object(
                article=article_data,
                attachments=attachments
            )
            
            # 저장
            insert_integrated_object(db, {
                'original_id': str(article_id),
                'company_id': company_id,
                'platform': platform or 'freshdesk',
                'object_type': 'integrated_article',
                'original_data': integrated_object,
                'integrated_content': integrated_object.get('integrated_text', ''),
                'metadata': create_article_metadata(integrated_object)
            })
            
            print(f"✅ 문서 {article_id} 마이그레이션 완료")
            
        except Exception as e:
            print(f"❌ 문서 {article_id} 마이그레이션 실패: {e}")
```

### 3단계: 데이터 검증

```python
def validate_migration(db):
    """마이그레이션 결과 검증"""
    
    cursor = db.cursor()
    
    # 1. 통합 객체 수 확인
    cursor.execute("SELECT COUNT(*) FROM integrated_objects")
    integrated_count = cursor.fetchone()[0]
    
    # 2. 기존 테이블 수 확인
    cursor.execute("SELECT COUNT(*) FROM tickets")
    tickets_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM articles")
    articles_count = cursor.fetchone()[0]
    
    print(f"📊 마이그레이션 결과:")
    print(f"   - 통합 객체: {integrated_count}개")
    print(f"   - 기존 티켓: {tickets_count}개")
    print(f"   - 기존 문서: {articles_count}개")
    
    # 3. 샘플 데이터 검증
    cursor.execute("""
        SELECT original_id, object_type, 
               JSON_EXTRACT(metadata, '$.subject') as subject,
               LENGTH(integrated_content) as content_length
        FROM integrated_objects 
        LIMIT 5
    """)
    
    samples = cursor.fetchall()
    print(f"\n📝 샘플 데이터:")
    for sample in samples:
        print(f"   - ID: {sample[0]}, Type: {sample[1]}, Subject: {sample[2]}, Content: {sample[3]} chars")
```

### 4단계: 코드베이스 업데이트

#### A. 기존 쿼리 수정

```python
# ❌ Before: 분산된 테이블 조회
def get_ticket_with_details(ticket_id, company_id):
    ticket = db.query("SELECT * FROM tickets WHERE id = ? AND company_id = ?", 
                     (ticket_id, company_id))
    conversations = db.query("SELECT * FROM conversations WHERE ticket_id = ?", 
                           (ticket_id,))
    attachments = db.query("SELECT * FROM attachments WHERE ticket_id = ?", 
                          (ticket_id,))
    return ticket, conversations, attachments

# ✅ After: 통합 객체 조회
def get_integrated_ticket(ticket_id, company_id):
    result = db.query("""
        SELECT original_data, integrated_content, summary, metadata
        FROM integrated_objects 
        WHERE original_id = ? AND company_id = ? AND object_type = 'integrated_ticket'
    """, (str(ticket_id), company_id))
    
    if result:
        return json.loads(result[0]['original_data'])  # 완전한 티켓 데이터
    return None
```

#### B. 요약 생성 로직 수정

```python
# ❌ Before: 분산된 데이터 수집
def generate_ticket_summary(ticket_id):
    ticket = get_ticket(ticket_id)
    conversations = get_conversations(ticket_id)
    attachments = get_attachments(ticket_id)
    
    # 텍스트 조합
    text = f"{ticket['subject']}\n{ticket['description']}"
    for conv in conversations:
        text += f"\n{conv['body_text']}"
    
    return llm_summarize(text)

# ✅ After: 통합 객체 활용
def generate_integrated_summary(ticket_id, company_id):
    integrated_obj = get_integrated_ticket(ticket_id, company_id)
    
    if integrated_obj:
        # integrated_content는 이미 LLM 처리에 최적화된 텍스트
        summary = llm_summarize(integrated_obj['integrated_text'])
        
        # 요약을 통합 객체에 저장
        update_integrated_object_summary(ticket_id, company_id, summary)
        
        return summary
    return None
```

#### C. 검색 로직 수정

```python
# ❌ Before: 여러 테이블 조인 검색
def search_tickets(query, company_id):
    return db.query("""
        SELECT t.*, c.body_text, a.name as attachment_name
        FROM tickets t
        LEFT JOIN conversations c ON t.id = c.ticket_id
        LEFT JOIN attachments a ON t.id = a.ticket_id
        WHERE t.company_id = ? 
          AND (t.subject LIKE ? OR t.description LIKE ? OR c.body_text LIKE ?)
    """, (company_id, f"%{query}%", f"%{query}%", f"%{query}%"))

# ✅ After: 통합 객체 검색
def search_integrated_tickets(query, company_id):
    return db.query("""
        SELECT original_id, 
               JSON_EXTRACT(metadata, '$.subject') as subject,
               summary,
               metadata
        FROM integrated_objects
        WHERE company_id = ? 
          AND object_type = 'integrated_ticket'
          AND (integrated_content LIKE ? OR summary LIKE ?)
    """, (company_id, f"%{query}%", f"%{query}%"))
```

### 5단계: 기존 테이블 정리

```sql
-- ⚠️ 주의: 마이그레이션과 검증이 완료된 후에만 실행

-- 1. 백업 생성 (안전장치)
DROP TABLE IF EXISTS tickets_backup;
CREATE TABLE tickets_backup AS SELECT * FROM tickets;

DROP TABLE IF EXISTS conversations_backup;
CREATE TABLE conversations_backup AS SELECT * FROM conversations;

DROP TABLE IF EXISTS attachments_backup;
CREATE TABLE attachments_backup AS SELECT * FROM attachments;

-- 2. 기존 테이블 삭제
DROP TABLE IF EXISTS attachments;
DROP TABLE IF EXISTS conversations;
DROP TABLE IF EXISTS tickets;
DROP TABLE IF EXISTS articles;

-- 3. 관련 인덱스도 정리됨 (CASCADE)
```

## 🧪 마이그레이션 스크립트

```python
#!/usr/bin/env python3
"""
통합 객체 마이그레이션 스크립트
사용법: python migrate_to_integrated_objects.py --company wedosoft --verify
"""

import argparse
import json
import sys
from datetime import datetime

def main():
    parser = argparse.ArgumentParser(description='통합 객체 마이그레이션')
    parser.add_argument('--company', required=True, help='회사 ID')
    parser.add_argument('--verify', action='store_true', help='마이그레이션 후 검증')
    parser.add_argument('--cleanup', action='store_true', help='기존 테이블 정리')
    
    args = parser.parse_args()
    
    # 데이터베이스 연결
    db = get_database(args.company)
    
    try:
        print(f"🚀 {args.company} 통합 객체 마이그레이션 시작...")
        
        # 1. 티켓 마이그레이션
        print("📧 티켓 마이그레이션 중...")
        migrate_tickets_to_integrated_objects(db)
        
        # 2. 문서 마이그레이션  
        print("📚 문서 마이그레이션 중...")
        migrate_articles_to_integrated_objects(db)
        
        # 3. 검증
        if args.verify:
            print("🔍 마이그레이션 검증 중...")
            validate_migration(db)
        
        # 4. 정리
        if args.cleanup:
            print("🧹 기존 테이블 정리 중...")
            cleanup_old_tables(db)
        
        print("✅ 마이그레이션 완료!")
        
    except Exception as e:
        print(f"❌ 마이그레이션 실패: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
```

## 📊 마이그레이션 체크리스트

### 마이그레이션 전
- [ ] 현재 데이터베이스 전체 백업
- [ ] 통합 객체 스키마 검토 및 테스트
- [ ] 마이그레이션 스크립트 테스트 (샘플 데이터로)
- [ ] 다운타임 계획 수립

### 마이그레이션 중
- [ ] 통합 객체 스키마 배포
- [ ] 티켓 데이터 마이그레이션
- [ ] 문서 데이터 마이그레이션  
- [ ] 데이터 검증 (수량, 샘플 확인)

### 마이그레이션 후
- [ ] 애플리케이션 코드 업데이트 배포
- [ ] API 엔드포인트 테스트
- [ ] 성능 테스트 (검색, 조회 속도)
- [ ] 사용자 기능 테스트
- [ ] 기존 테이블 정리 (충분한 검증 후)

## 🔧 롤백 계획

만약 문제가 생기면:

```sql
-- 1. 기존 테이블 복구
CREATE TABLE tickets AS SELECT * FROM tickets_backup;
CREATE TABLE conversations AS SELECT * FROM conversations_backup;  
CREATE TABLE attachments AS SELECT * FROM attachments_backup;

-- 2. 통합 객체 테이블 비우기 (필요시)
DELETE FROM integrated_objects WHERE company_id = 'your_company';

-- 3. 애플리케이션 코드 이전 버전으로 롤백
```

## 🎯 기대 효과

### 성능 향상
- 단일 테이블 조회로 JOIN 연산 제거
- 통합 텍스트로 검색 성능 향상
- 인덱스 최적화 효과

### 개발 효율성
- 단순한 데이터 모델
- 일관된 API 구조
- 쉬운 신규 기능 개발

### 유지보수성
- 스키마 변경 최소화
- 데이터 일관성 보장
- 버그 발생 지점 감소

이제 **완전한 통합 객체 중심 아키텍처**로 전환할 준비가 되었습니다! 🚀
