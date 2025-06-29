#!/usr/bin/env python3
"""
진행 상황 로깅 테스트 스크립트

이 스크립트는 progress_logs 테이블에 진행 상황이 제대로 로그되는지 확인합니다.
"""
import os
import sys
import asyncio
from pathlib import Path

# backend 디렉토리를 Python 경로에 추가
current_dir = Path(__file__).resolve().parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

from core.database.database import get_database
from core.ingest.processor import ingest

async def test_progress_logging():
    """진행 상황 로깅을 테스트합니다."""
    print("=== 진행 상황 로깅 테스트 시작 ===")
    
    # 테스트용 tenant_id
    tenant_id = "test_company"
    platform = "freshdesk"
    
    try:
        # 데이터베이스 연결
        db = get_database(tenant_id, platform)
        if not db.connection:
            db.connect()
        
        # 기존 진행 로그 삭제 (테스트를 위해)
        cursor = db.connection.cursor()
        cursor.execute("DELETE FROM progress_logs WHERE tenant_id = ?", 
                      (tenant_id,))
        db.connection.commit()
        print(f"기존 진행 로그 삭제 완료")
        
        # 진행 상황 콜백 함수 정의
        def progress_callback(progress_data):
            stage = progress_data.get("stage", "unknown")
            progress = progress_data.get("progress", 0)
            print(f"콜백 수신: {stage} - {progress:.1f}%")
        
        # 먼저 간단한 log_progress 테스트
        print("1. 간단한 log_progress 테스트...")
        try:
            log_id = db.log_progress(
                job_id="test_job",
                tenant_id=tenant_id,
                message="테스트 메시지",
                percentage=50.0,
                step=1,
                total_steps=2
            )
            print(f"   ✅ log_progress 성공: log_id={log_id}")
        except Exception as e:
            print(f"   ❌ log_progress 실패: {e}")
            raise e
        
        # 데이터 수집 실행 (최소한의 데이터만)
        print("2. 데이터 수집 시작...")
        result = await ingest(
            tenant_id=tenant_id,
            platform=platform,
            max_tickets=2,  # 최소한의 티켓만
            max_articles=2,  # 최소한의 문서만
            skip_summaries=True,  # 요약 생성 건너뛰기
            skip_embeddings=True,  # 임베딩 생성 건너뛰기
            progress_callback=progress_callback
        )
        
        print(f"데이터 수집 결과: {result}")
        
        # 진행 로그 확인
        cursor.execute("""
            SELECT * FROM progress_logs 
            WHERE tenant_id = ?
            ORDER BY created_at
        """, (tenant_id,))
        
        logs = cursor.fetchall()
        
        print(f"\n=== 저장된 진행 로그 ({len(logs)}개) ===")
        for log in logs:
            print(f"시간: {log[5]}, 단계: {log[3]}, 진행률: {log[4]}%, 메시지: {log[6]}")
        
        if len(logs) > 0:
            print("\n✅ 진행 상황 로깅이 정상적으로 작동합니다!")
        else:
            print("\n❌ 진행 상황 로그가 저장되지 않았습니다.")
        
        return len(logs) > 0
        
    except Exception as e:
        print(f"❌ 테스트 중 오류 발생: {e}")
        return False
    finally:
        if 'db' in locals() and db:
            db.disconnect()

if __name__ == "__main__":
    # 환경변수 확인
    if not os.getenv("FRESHDESK_DOMAIN") or not os.getenv("FRESHDESK_API_KEY"):
        print("❌ FRESHDESK_DOMAIN과 FRESHDESK_API_KEY 환경변수가 설정되지 않았습니다.")
        print("테스트를 위해 .env 파일을 확인하세요.")
        sys.exit(1)
    
    # 테스트 실행
    result = asyncio.run(test_progress_logging())
    sys.exit(0 if result else 1)
