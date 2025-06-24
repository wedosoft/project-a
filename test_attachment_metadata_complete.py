#!/usr/bin/env python3
"""
첨부파일 메타데이터 완전 테스트 스크립트

이 스크립트는 다음을 테스트합니다:
1. 첨부파일이 있는 티켓의 요약 생성
2. integrated_objects.metadata에 attachments 필드가 올바르게 저장되는지 확인
3. 첨부파일 메타데이터의 상세 정보 (ID, 이름, URL 등) 확인
"""

import asyncio
import sys
import os
import json
from datetime import datetime

# 프로젝트 루트를 Python path에 추가
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.append(project_root)

# 백엔드 디렉토리를 Python path에 추가
backend_path = os.path.join(project_root, 'backend')
if backend_path not in sys.path:
    sys.path.append(backend_path)

from core.database.database import get_database
from core.ingest.processor import generate_and_store_summaries


def get_kst_time():
    """KST 시간 반환"""
    from datetime import datetime, timezone, timedelta
    kst = timezone(timedelta(hours=9))
    return datetime.now(kst).strftime('%Y-%m-%d %H:%M:%S')


async def test_attachment_metadata():
    """첨부파일 메타데이터 전체 테스트"""
    
    print("🔍 첨부파일 메타데이터 완전 테스트 시작")
    print("=" * 60)
    
    # 1. 데이터베이스 연결
    company_id = "test"
    platform = "freshdesk"
    
    try:
        db = get_database(company_id, platform)
        print(f"✅ 데이터베이스 연결 성공: {company_id}/{platform}")
    except Exception as e:
        print(f"❌ 데이터베이스 연결 실패: {e}")
        return
    
    # 2. 현재 상태 확인
    print("\n📊 현재 데이터베이스 상태:")
    cursor = db.connection.cursor()
    
    # integrated_objects 테이블 상태
    cursor.execute("SELECT COUNT(*) FROM integrated_objects WHERE company_id = ? AND platform = ?", (company_id, platform))
    integrated_count = cursor.fetchone()[0]
    print(f"  - integrated_objects: {integrated_count}개")
    
    # 첨부파일이 있는 티켓 확인
    cursor.execute("""
        SELECT COUNT(*) FROM integrated_objects 
        WHERE company_id = ? AND platform = ? 
        AND JSON_EXTRACT(metadata, '$.has_attachments') = 1
    """, (company_id, platform))
    tickets_with_attachments = cursor.fetchone()[0]
    print(f"  - 첨부파일이 있는 티켓: {tickets_with_attachments}개")
    
    # 3. 메타데이터에 attachments 필드가 있는 티켓 확인
    cursor.execute("""
        SELECT original_id, metadata FROM integrated_objects 
        WHERE company_id = ? AND platform = ? 
        AND JSON_EXTRACT(metadata, '$.has_attachments') = 1
        LIMIT 3
    """, (company_id, platform))
    
    sample_tickets = cursor.fetchall()
    
    print(f"\n📋 첨부파일이 있는 티켓 샘플 ({len(sample_tickets)}개):")
    for i, (original_id, metadata_json) in enumerate(sample_tickets):
        print(f"  {i+1}. 티켓 ID: {original_id}")
        
        if metadata_json:
            try:
                metadata = json.loads(metadata_json)
                print(f"     - has_attachments: {metadata.get('has_attachments', False)}")
                print(f"     - attachment_count: {metadata.get('attachment_count', 0)}")
                
                # attachments 필드 확인
                attachments = metadata.get('attachments', [])
                if attachments:
                    print(f"     - attachments 메타데이터: {len(attachments)}개")
                    for j, att in enumerate(attachments[:2]):  # 처음 2개만 출력
                        print(f"       {j+1}) ID: {att.get('id', 'N/A')}, 이름: {att.get('name', 'N/A')}")
                else:
                    print(f"     - ❌ attachments 메타데이터 없음 (has_attachments는 True이지만)")
                    
            except Exception as e:
                print(f"     - ❌ 메타데이터 파싱 오류: {e}")
        else:
            print(f"     - ❌ 메타데이터 null")
        print()
    
    if not sample_tickets:
        print("  ⚠️  첨부파일이 있는 티켓이 없습니다.")
        return
    
    # 4. 요약 재생성 테스트 (첫 번째 티켓)
    test_ticket_id = sample_tickets[0][0]
    print(f"🧪 테스트 티켓 {test_ticket_id}의 요약 재생성:")
    
    try:
        # 요약 재생성 (force_update=True)
        result = await generate_and_store_summaries(
            company_id=company_id,
            platform=platform,
            force_update=True
        )
        
        print(f"  - 성공: {result.get('success_count', 0)}개")
        print(f"  - 실패: {result.get('failure_count', 0)}개")
        
        if result.get('errors'):
            print(f"  - 오류: {result['errors']}")
            
    except Exception as e:
        print(f"  - ❌ 요약 생성 오류: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 5. 결과 확인
    print(f"\n✅ 요약 재생성 후 메타데이터 확인:")
    
    cursor.execute("""
        SELECT metadata FROM integrated_objects 
        WHERE company_id = ? AND platform = ? AND original_id = ?
    """, (company_id, platform, test_ticket_id))
    
    result_row = cursor.fetchone()
    if result_row and result_row[0]:
        try:
            updated_metadata = json.loads(result_row[0])
            
            print(f"  - has_attachments: {updated_metadata.get('has_attachments', False)}")
            print(f"  - attachment_count: {updated_metadata.get('attachment_count', 0)}")
            print(f"  - summary_generated_at: {updated_metadata.get('summary_generated_at', 'N/A')}")
            print(f"  - summary_length: {updated_metadata.get('summary_length', 0)}")
            
            # 핵심 확인: attachments 필드
            attachments = updated_metadata.get('attachments', [])
            if attachments:
                print(f"  - ✅ attachments 메타데이터: {len(attachments)}개")
                print(f"    상세:")
                for i, att in enumerate(attachments):
                    print(f"      {i+1}. ID: {att.get('id', 'N/A')}")
                    print(f"         이름: {att.get('name', 'N/A')}")
                    print(f"         타입: {att.get('content_type', 'N/A')}")
                    print(f"         크기: {att.get('size', 'N/A')} bytes")
                    if att.get('ticket_id'):
                        print(f"         티켓 ID: {att.get('ticket_id')}")
                    if att.get('conversation_id'):
                        print(f"         대화 ID: {att.get('conversation_id')}")
                    print()
            else:
                print(f"  - ❌ attachments 메타데이터가 여전히 없음!")
                
        except Exception as e:
            print(f"  - ❌ 메타데이터 파싱 오류: {e}")
    else:
        print(f"  - ❌ 업데이트된 데이터를 찾을 수 없음")
    
    # 6. 최종 통계
    print(f"\n📈 최종 통계:")
    cursor.execute("""
        SELECT COUNT(*) FROM integrated_objects 
        WHERE company_id = ? AND platform = ? 
        AND JSON_EXTRACT(metadata, '$.attachments') IS NOT NULL
        AND JSON_LENGTH(JSON_EXTRACT(metadata, '$.attachments')) > 0
    """, (company_id, platform))
    
    tickets_with_attachment_metadata = cursor.fetchone()[0]
    print(f"  - attachments 메타데이터가 있는 티켓: {tickets_with_attachment_metadata}개")
    
    # 전체 첨부파일 있는 티켓과 비교
    if tickets_with_attachments > 0:
        completion_rate = (tickets_with_attachment_metadata / tickets_with_attachments) * 100
        print(f"  - 메타데이터 완성도: {completion_rate:.1f}%")
        
        if completion_rate < 100:
            print(f"  - ⚠️  {tickets_with_attachments - tickets_with_attachment_metadata}개 티켓의 첨부파일 메타데이터가 누락됨")
        else:
            print(f"  - ✅ 모든 첨부파일 메타데이터가 정상적으로 저장됨")
    
    print("\n" + "=" * 60)
    print("🏁 테스트 완료")


if __name__ == "__main__":
    asyncio.run(test_attachment_metadata())
