#!/usr/bin/env python3
"""
매우 간단한 log_progress 테스트 스크립트
"""
import os
import sys
from pathlib import Path

# backend 디렉토리를 Python 경로에 추가
current_dir = Path(__file__).resolve().parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

def test_simple_log_progress():
    """매우 간단한 log_progress 테스트"""
    print("=== 간단한 log_progress 테스트 ===")
    
    try:
        from core.database.database import get_database
        
        # 테스트용 tenant_id
        tenant_id = "simple_test"
        platform = "freshdesk"
        
        # 데이터베이스 연결
        db = get_database(tenant_id, platform)
        print(f"데이터베이스 연결 성공: {db.db_path}")
        
        if not db.connection:
            db.connect()
        print("데이터베이스 연결 완료")
        
        # 테이블 구조 확인
        cursor = db.connection.cursor()
        cursor.execute("PRAGMA table_info(progress_logs)")
        columns = cursor.fetchall()
        print(f"progress_logs 테이블 컬럼: {[col[1] for col in columns]}")
        
        # 간단한 log_progress 호출
        print("log_progress 호출 시작...")
        log_id = db.log_progress(
            job_id="simple_test_job",
            tenant_id=tenant_id,
            message="간단한 테스트 메시지",
            percentage=75.5,
            step=3,
            total_steps=4
        )
        print(f"✅ log_progress 성공! log_id={log_id}")
        
        # 저장된 로그 확인
        cursor.execute("SELECT * FROM progress_logs WHERE job_id = ?", ("simple_test_job",))
        logs = cursor.fetchall()
        print(f"저장된 로그: {logs}")
        
        if logs:
            print("✅ 진행 상황 로깅이 정상적으로 작동합니다!")
            return True
        else:
            print("❌ 로그가 저장되지 않았습니다.")
            return False
        
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if 'db' in locals() and db:
            db.disconnect()

if __name__ == "__main__":
    success = test_simple_log_progress()
    sys.exit(0 if success else 1)
