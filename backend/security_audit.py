#!/usr/bin/env python3
"""
데이터베이스 보안 감사 및 민감한 정보 정리 스크립트

이 스크립트는:
1. 모든 테넌트 DB에서 민감한 정보를 탐지
2. 보안 위반 사항을 리포트
3. 자동으로 민감한 정보를 제거 (옵션)
4. 환경변수 마이그레이션 가이드 제공
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, List, Any
import sqlite3

# 프로젝트 루트를 Python path에 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    from core.database.database import SQLiteDatabase
    from core.database.factory import DatabaseFactory
except ImportError as e:
    print(f"❌ Import 오류: {e}")
    print("📍 현재 디렉토리에서 실행하세요: cd backend && python security_audit.py")
    sys.exit(1)


class DatabaseSecurityAuditor:
    """데이터베이스 보안 감사 클래스"""
    
    def __init__(self):
        self.data_dir = project_root / "core" / "data"
        self.sensitive_violations = []
        self.recommendations = []
    
    def scan_all_databases(self) -> Dict[str, Any]:
        """모든 테넌트 데이터베이스 스캔"""
        print("🔍 데이터베이스 보안 감사 시작...")
        
        audit_report = {
            'timestamp': '2025-01-27',
            'scanned_databases': [],
            'security_violations': [],
            'safe_settings': [],
            'environment_recommendations': [],
            'summary': {}
        }
        
        # 데이터 디렉토리의 모든 DB 파일 스캔
        if self.data_dir.exists():
            for db_file in self.data_dir.glob("*_data.db"):
                print(f"📊 스캔 중: {db_file.name}")
                db_audit = self.audit_database(db_file)
                audit_report['scanned_databases'].append(db_file.name)
                audit_report['security_violations'].extend(db_audit['violations'])
                audit_report['safe_settings'].extend(db_audit['safe_settings'])
        
        # 요약 통계
        audit_report['summary'] = {
            'total_databases': len(audit_report['scanned_databases']),
            'total_violations': len(audit_report['security_violations']),
            'safe_settings_count': len(audit_report['safe_settings']),
            'critical_issues': sum(1 for v in audit_report['security_violations'] if v['severity'] == 'CRITICAL'),
            'high_issues': sum(1 for v in audit_report['security_violations'] if v['severity'] == 'HIGH')
        }
        
        # 환경변수 마이그레이션 권장사항 생성
        audit_report['environment_recommendations'] = self.generate_env_recommendations(
            audit_report['security_violations']
        )
        
        return audit_report
    
    def audit_database(self, db_path: Path) -> Dict[str, Any]:
        """개별 데이터베이스 감사"""
        violations = []
        safe_settings = []
        
        try:
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # 테이블 존재 확인
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            # system_settings 테이블 검사
            if 'system_settings' in tables:
                cursor.execute("SELECT setting_key, setting_value, description FROM system_settings")
                for row in cursor.fetchall():
                    setting_key = row['setting_key']
                    setting_value = row['setting_value']
                    
                    violation = self.check_sensitive_setting(
                        setting_key, setting_value, 'system_settings', str(db_path)
                    )
                    if violation:
                        violations.append(violation)
                    else:
                        safe_settings.append({
                            'database': str(db_path),
                            'table': 'system_settings',
                            'key': setting_key,
                            'description': row['description']
                        })
            
            # company_settings 테이블 검사
            if 'company_settings' in tables:
                cursor.execute("SELECT setting_key, setting_value, description FROM company_settings")
                for row in cursor.fetchall():
                    setting_key = row['setting_key']
                    setting_value = row['setting_value']
                    
                    violation = self.check_sensitive_setting(
                        setting_key, setting_value, 'company_settings', str(db_path)
                    )
                    if violation:
                        violations.append(violation)
                    else:
                        safe_settings.append({
                            'database': str(db_path),
                            'table': 'company_settings',
                            'key': setting_key,
                            'description': row['description']
                        })
            
            conn.close()
            
        except Exception as e:
            print(f"⚠️ DB 스캔 오류 ({db_path}): {e}")
        
        return {
            'violations': violations,
            'safe_settings': safe_settings
        }
    
    def check_sensitive_setting(self, key: str, value: str, table: str, db_path: str) -> Dict[str, Any]:
        """설정이 민감한 정보인지 확인"""
        sensitive_keywords = [
            'api_key', 'api-key', 'apikey',
            'password', 'passwd', 'pwd',
            'secret', 'token', 'credential',
            'domain', 'freshdesk_domain',
            'private_key', 'certificate', 'cert'
        ]
        
        key_lower = key.lower()
        for keyword in sensitive_keywords:
            if keyword in key_lower:
                severity = 'CRITICAL' if any(x in key_lower for x in ['api_key', 'password', 'secret']) else 'HIGH'
                return {
                    'database': db_path,
                    'table': table,
                    'setting_key': key,
                    'setting_value': value[:20] + "..." if len(value) > 20 else value,
                    'matched_keyword': keyword,
                    'severity': severity,
                    'recommendation': self.get_recommendation_for_setting(key)
                }
        return None
    
    def get_recommendation_for_setting(self, setting_key: str) -> str:
        """설정별 권장사항 반환"""
        key_lower = setting_key.lower()
        
        if 'freshdesk' in key_lower and 'domain' in key_lower:
            return "X-Freshdesk-Domain 헤더나 FRESHDESK_DOMAIN 환경변수로 이전"
        elif 'freshdesk' in key_lower and 'api' in key_lower:
            return "X-Freshdesk-API-Key 헤더나 FRESHDESK_API_KEY 환경변수로 이전"
        elif 'api_key' in key_lower:
            return "해당 플랫폼의 API 키 헤더나 환경변수로 이전"
        elif 'domain' in key_lower:
            return "플랫폼별 도메인 헤더나 환경변수로 이전"
        else:
            return "환경변수나 보안 설정 파일로 이전"
    
    def generate_env_recommendations(self, violations: List[Dict]) -> List[str]:
        """환경변수 마이그레이션 권장사항 생성"""
        recommendations = []
        
        if any('freshdesk' in v['setting_key'].lower() for v in violations):
            recommendations.append("""
🔧 Freshdesk 설정 마이그레이션:
   - .env 파일에 추가:
     FRESHDESK_DOMAIN=your_company.freshdesk.com
     FRESHDESK_API_KEY=your_api_key_here
   - API 헤더로 전달:
     X-Freshdesk-Domain: your_company.freshdesk.com
     X-Freshdesk-API-Key: your_api_key_here""")
        
        if violations:
            recommendations.append("""
🛡️ 보안 정책:
   - API 키, 도메인은 절대 DB에 저장하지 마세요
   - 환경변수나 Freshdesk iparams 사용
   - 민감한 정보는 암호화된 설정 관리 도구 사용""")
        
        return recommendations
    
    def clean_sensitive_data(self, db_path: Path, dry_run: bool = True) -> Dict[str, Any]:
        """민감한 데이터 정리 (dry_run=False일 때 실제 삭제)"""
        print(f"🧹 민감한 데이터 정리 {'(시뮬레이션)' if dry_run else '(실제 실행)'}: {db_path}")
        
        cleaned_items = []
        
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            
            # system_settings에서 민감한 설정 제거
            cursor.execute("SELECT setting_key FROM system_settings")
            for row in cursor.fetchall():
                setting_key = row[0]
                if self.is_sensitive_key(setting_key):
                    if not dry_run:
                        cursor.execute("DELETE FROM system_settings WHERE setting_key = ?", (setting_key,))
                    cleaned_items.append(f"system_settings.{setting_key}")
            
            # company_settings에서 민감한 설정 제거
            cursor.execute("SELECT setting_key FROM company_settings")
            for row in cursor.fetchall():
                setting_key = row[0]
                if self.is_sensitive_key(setting_key):
                    if not dry_run:
                        cursor.execute("DELETE FROM company_settings WHERE setting_key = ?", (setting_key,))
                    cleaned_items.append(f"company_settings.{setting_key}")
            
            if not dry_run:
                conn.commit()
            conn.close()
            
        except Exception as e:
            print(f"⚠️ 정리 중 오류: {e}")
        
        return {
            'database': str(db_path),
            'cleaned_items': cleaned_items,
            'dry_run': dry_run
        }
    
    def is_sensitive_key(self, key: str) -> bool:
        """키가 민감한 정보인지 판단"""
        sensitive_keywords = [
            'api_key', 'api-key', 'apikey',
            'password', 'passwd', 'pwd',
            'secret', 'token', 'credential',
            'domain', 'freshdesk_domain',
            'private_key', 'certificate', 'cert'
        ]
        
        key_lower = key.lower()
        return any(keyword in key_lower for keyword in sensitive_keywords)
    
    def print_audit_report(self, report: Dict[str, Any]):
        """감사 보고서 출력"""
        print("\n" + "="*60)
        print("🔐 데이터베이스 보안 감사 보고서")
        print("="*60)
        
        summary = report['summary']
        print(f"📊 요약:")
        print(f"   • 스캔된 데이터베이스: {summary['total_databases']}개")
        print(f"   • 보안 위반 사항: {summary['total_violations']}개")
        print(f"   • 안전한 설정: {summary['safe_settings_count']}개")
        print(f"   • 치명적 문제: {summary['critical_issues']}개")
        print(f"   • 높은 위험 문제: {summary['high_issues']}개")
        
        if report['security_violations']:
            print(f"\n🚨 보안 위반 사항:")
            for violation in report['security_violations']:
                print(f"   ❌ {violation['severity']}: {violation['table']}.{violation['setting_key']}")
                print(f"      📂 DB: {Path(violation['database']).name}")
                print(f"      💡 권장: {violation['recommendation']}")
                print()
        
        if report['environment_recommendations']:
            print("💡 마이그레이션 가이드:")
            for recommendation in report['environment_recommendations']:
                print(recommendation)
        
        if not report['security_violations']:
            print("\n✅ 축하합니다! 모든 설정이 보안 정책을 준수합니다.")


def main():
    """메인 실행 함수"""
    print("🔐 데이터베이스 보안 감사 도구")
    print("=" * 50)
    
    auditor = DatabaseSecurityAuditor()
    
    # 감사 실행
    report = auditor.scan_all_databases()
    
    # 보고서 출력
    auditor.print_audit_report(report)
    
    # JSON 보고서 저장
    report_path = project_root / "security_audit_report.json"
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\n💾 상세 보고서 저장: {report_path}")
    
    # 정리 옵션 제공
    if report['security_violations']:
        print("\n🧹 민감한 데이터 정리 옵션:")
        print("   1. 시뮬레이션 모드 (삭제 미리보기)")
        print("   2. 실제 삭제 (주의: 되돌릴 수 없음)")
        print("   3. 건너뛰기")
        
        while True:
            choice = input("\n선택 (1-3): ").strip()
            if choice == '1':
                print("\n🔍 시뮬레이션 모드로 정리 미리보기...")
                for db_file in auditor.data_dir.glob("*_data.db"):
                    clean_result = auditor.clean_sensitive_data(db_file, dry_run=True)
                    if clean_result['cleaned_items']:
                        print(f"   📂 {Path(clean_result['database']).name}:")
                        for item in clean_result['cleaned_items']:
                            print(f"      🗑️ 삭제 예정: {item}")
                break
            elif choice == '2':
                confirm = input("⚠️ 정말로 민감한 데이터를 삭제하시겠습니까? (yes/no): ").strip().lower()
                if confirm == 'yes':
                    print("\n🧹 민감한 데이터 실제 삭제 중...")
                    for db_file in auditor.data_dir.glob("*_data.db"):
                        clean_result = auditor.clean_sensitive_data(db_file, dry_run=False)
                        if clean_result['cleaned_items']:
                            print(f"   ✅ {Path(clean_result['database']).name}: {len(clean_result['cleaned_items'])}개 항목 삭제")
                    print("✅ 민감한 데이터 정리 완료!")
                break
            elif choice == '3':
                print("정리 작업을 건너뛰었습니다.")
                break
            else:
                print("잘못된 선택입니다. 1, 2, 또는 3을 입력하세요.")


if __name__ == "__main__":
    main()
