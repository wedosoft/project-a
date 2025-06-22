#!/usr/bin/env python3
"""
SQLite 데이터베이스 내용을 확인하는 스크립트
"""

import sqlite3
import sys
import os
from pathlib import Path

def check_database(db_path: str):
    """데이터베이스 내용을 확인합니다."""
    
    if not os.path.exists(db_path):
        print(f"❌ 데이터베이스 파일을 찾을 수 없습니다: {db_path}")
        return
    
    print(f"📁 데이터베이스: {db_path}")
    print("=" * 80)
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 1. 테이블 목록
        print("\n📋 테이블 목록:")
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        for table in tables:
            print(f"  - {table[0]}")
        
        # 2. integrated_objects 테이블 확인
        if any('integrated_objects' in table for table in tables):
            print(f"\n📊 integrated_objects 테이블 통계:")
            
            # 전체 개수
            cursor.execute("SELECT COUNT(*) FROM integrated_objects;")
            total = cursor.fetchone()[0]
            print(f"  총 레코드 수: {total}")
            
            # company_id별 통계
            cursor.execute("""
                SELECT company_id, platform, object_type, COUNT(*) 
                FROM integrated_objects 
                GROUP BY company_id, platform, object_type
                ORDER BY company_id, platform, object_type;
            """)
            stats = cursor.fetchall()
            
            print(f"\n  📈 회사/플랫폼/타입별 통계:")
            for stat in stats:
                print(f"    {stat[0]} / {stat[1]} / {stat[2]}: {stat[3]}개")
            
            # 요약 상태 확인
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(summary) as with_summary,
                    COUNT(*) - COUNT(summary) as without_summary
                FROM integrated_objects;
            """)
            summary_stats = cursor.fetchone()
            print(f"\n  📝 요약 상태:")
            print(f"    요약 있음: {summary_stats[1]}개")
            print(f"    요약 없음: {summary_stats[2]}개")
            
            # 최근 데이터 확인
            print(f"\n  🕒 최근 데이터 (5개):")
            cursor.execute("""
                SELECT original_id, object_type, 
                       CASE WHEN summary IS NOT NULL THEN 'YES' ELSE 'NO' END as has_summary,
                       created_at
                FROM integrated_objects 
                ORDER BY created_at DESC 
                LIMIT 5;
            """)
            recent = cursor.fetchall()
            
            for row in recent:
                print(f"    ID: {row[0]}, Type: {row[1]}, Summary: {row[2]}, Created: {row[3]}")
        
        # 3. progress_logs 테이블 확인
        if any('progress_logs' in table for table in tables):
            print(f"\n📋 최근 진행상황 로그 (5개):")
            cursor.execute("""
                SELECT job_id, status, message, progress_percent, created_at
                FROM progress_logs 
                ORDER BY created_at DESC 
                LIMIT 5;
            """)
            logs = cursor.fetchall()
            
            for log in logs:
                print(f"    {log[0]}: {log[1]} - {log[2]} ({log[3]}%) at {log[4]}")
        
        conn.close()
        print(f"\n✅ 데이터베이스 확인 완료!")
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")

def main():
    """메인 함수"""
    
    # 기본 데이터베이스 경로들
    default_paths = [
        "/app/core/data",  # Docker 내부
        "../backend/core/data",  # 로컬 개발
        "./core/data",  # 현재 디렉토리
    ]
    
    # 명령행 인자가 있으면 해당 경로 사용
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
        check_database(db_path)
        return
    
    # 기본 경로에서 데이터베이스 파일 찾기
    print("🔍 데이터베이스 파일 검색 중...")
    
    found_dbs = []
    for base_path in default_paths:
        if os.path.exists(base_path):
            for file in os.listdir(base_path):
                if file.endswith('.db'):
                    full_path = os.path.join(base_path, file)
                    found_dbs.append(full_path)
                    print(f"  발견: {full_path}")
    
    if not found_dbs:
        print("❌ SQLite 데이터베이스 파일을 찾을 수 없습니다.")
        print("사용법: python check_sqlite.py [database_path]")
        return
    
    # 가장 최근 파일 선택
    latest_db = max(found_dbs, key=os.path.getmtime)
    print(f"\n📂 가장 최근 데이터베이스 선택: {latest_db}")
    
    check_database(latest_db)

if __name__ == "__main__":
    main()
