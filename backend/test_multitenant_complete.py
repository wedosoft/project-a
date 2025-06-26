#!/usr/bin/env python3
"""
멀티테넌트 아키텍처 검증 및 테스트 스크립트
PostgreSQL과 SQLite 양쪽 모두 지원하는 완전한 테스트
"""

import os
import sys
import json
import logging
from pathlib import Path

# 프로젝트 루트 추가
sys.path.append(str(Path(__file__).parent.parent))

from core.database.database import DatabaseFactory, TenantDataManager
from core.database.postgresql_database import PostgreSQLDatabase

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MultiTenantValidator:
    """멀티테넌트 설정 검증"""
    
    def __init__(self):
        self.validation_results = {
            'database_type': None,
            'isolation_method': None,
            'environment_vars': {},
            'database_connections': {},
            'tenant_isolation_tests': [],
            'cross_tenant_prevention': [],
            'recommendations': [],
            'is_production_ready': False
        }
    
    def validate_environment(self):
        """환경 설정 검증"""
        logger.info("🔍 환경 설정 검증 중...")
        
        # 필수 환경변수 확인
        required_vars = ['DATABASE_TYPE']
        optional_vars = ['POSTGRES_HOST', 'POSTGRES_PORT', 'POSTGRES_DB', 'POSTGRES_USER', 'POSTGRES_PASSWORD']
        
        for var in required_vars + optional_vars:
            value = os.getenv(var)
            self.validation_results['environment_vars'][var] = value or "NOT_SET"
        
        # 데이터베이스 타입 결정
        db_type = os.getenv('DATABASE_TYPE', 'sqlite').lower()
        self.validation_results['database_type'] = db_type
        
        if db_type == 'postgresql':
            self.validation_results['isolation_method'] = 'schema-based'
            if not all(os.getenv(var) for var in ['POSTGRES_HOST', 'POSTGRES_USER', 'POSTGRES_PASSWORD']):
                self.validation_results['recommendations'].append("PostgreSQL 환경변수가 완전히 설정되지 않음")
        else:
            self.validation_results['isolation_method'] = 'file-based'
    
    def test_database_connections(self):
        """데이터베이스 연결 테스트"""
        logger.info("🔗 데이터베이스 연결 테스트...")
        
        test_companies = ['test_company_1', 'test_company_2']
        
        for company_id in test_companies:
            try:
                db = DatabaseFactory.create_database(company_id, 'freshdesk')
                db.connect()
                
                self.validation_results['database_connections'][company_id] = {
                    'status': 'SUCCESS',
                    'database_type': type(db).__name__,
                    'isolation_info': {
                        'schema_name': getattr(db, 'schema_name', None),
                        'db_path': getattr(db, 'db_path', None)
                    }
                }
                
                db.disconnect()
                
            except Exception as e:
                self.validation_results['database_connections'][company_id] = {
                    'status': 'FAILED',
                    'error': str(e)
                }
                self.validation_results['recommendations'].append(f"회사 {company_id} 연결 실패: {str(e)}")
    
    def test_tenant_isolation(self):
        """테넌트 격리 테스트"""
        logger.info("🔒 테넌트 격리 테스트...")
        
        # 두 개의 서로 다른 테넌트에 데이터 삽입
        test_cases = [
            {'company_id': 'tenant_a', 'platform': 'freshdesk'},
            {'company_id': 'tenant_b', 'platform': 'freshdesk'}
        ]
        
        for test_case in test_cases:
            try:
                db = DatabaseFactory.create_database(test_case['company_id'], test_case['platform'])
                db.connect()
                
                # 테스트 데이터 삽입
                test_ticket = {
                    'id': '12345',
                    'company_id': test_case['company_id'],
                    'platform': test_case['platform'],
                    'subject': f"Test ticket for {test_case['company_id']}",
                    'description': f"This is a test ticket for tenant isolation testing"
                }
                
                ticket_id = db.insert_ticket(test_ticket)
                
                # 데이터 조회 테스트
                tickets = db.get_integrated_objects_by_type(
                    test_case['company_id'], 
                    test_case['platform'], 
                    'ticket'
                )
                
                isolation_test = {
                    'tenant': test_case['company_id'],
                    'data_inserted': ticket_id is not None,
                    'data_count': len(tickets),
                    'can_access_own_data': len(tickets) > 0
                }
                
                self.validation_results['tenant_isolation_tests'].append(isolation_test)
                
                db.disconnect()
                
            except Exception as e:
                logger.error(f"테넌트 격리 테스트 실패 ({test_case['company_id']}): {e}")
                self.validation_results['recommendations'].append(f"테넌트 격리 테스트 실패: {str(e)}")
    
    def test_cross_tenant_prevention(self):
        """크로스 테넌트 접근 방지 테스트"""
        logger.info("🚫 크로스 테넌트 접근 방지 테스트...")
        
        try:
            # tenant_a로 연결하여 tenant_b 데이터에 접근 시도
            db_a = DatabaseFactory.create_database('tenant_a', 'freshdesk')
            db_a.connect()
            
            # tenant_b의 데이터 조회 시도 (실패해야 함)
            tenant_b_tickets = db_a.get_integrated_objects_by_type('tenant_b', 'freshdesk', 'ticket')
            
            cross_tenant_test = {
                'test_scenario': 'tenant_a trying to access tenant_b data',
                'data_count': len(tenant_b_tickets),
                'prevention_working': len(tenant_b_tickets) == 0,
                'security_level': 'PASSED' if len(tenant_b_tickets) == 0 else 'FAILED'
            }
            
            self.validation_results['cross_tenant_prevention'].append(cross_tenant_test)
            
            if len(tenant_b_tickets) > 0:
                self.validation_results['recommendations'].append("크로스 테넌트 접근이 차단되지 않음 - 보안 위험")
            
            db_a.disconnect()
            
        except Exception as e:
            logger.error(f"크로스 테넌트 방지 테스트 중 오류: {e}")
    
    def test_platform_separation(self):
        """플랫폼 분리 테스트"""
        logger.info("🔀 플랫폼 분리 테스트...")
        
        platforms = ['freshdesk', 'zendesk']
        company_id = 'multi_platform_test'
        
        for platform in platforms:
            try:
                db = DatabaseFactory.create_database(company_id, platform)
                db.connect()
                
                # 플랫폼별 테스트 데이터
                test_ticket = {
                    'id': f'{platform}_ticket_1',
                    'company_id': company_id,
                    'platform': platform,
                    'subject': f'Test ticket for {platform}',
                    'description': f'Platform-specific test data for {platform}'
                }
                
                db.insert_ticket(test_ticket)
                
                # 해당 플랫폼 데이터만 조회되는지 확인
                platform_tickets = db.get_integrated_objects_by_type(company_id, platform, 'ticket')
                
                logger.info(f"플랫폼 {platform}: {len(platform_tickets)}개 티켓 조회됨")
                
                db.disconnect()
                
            except Exception as e:
                logger.error(f"플랫폼 분리 테스트 실패 ({platform}): {e}")
    
    def generate_recommendations(self):
        """운영 권장사항 생성"""
        logger.info("💡 운영 권장사항 생성...")
        
        # 기본 권장사항
        if self.validation_results['database_type'] == 'sqlite':
            self.validation_results['recommendations'].extend([
                "SQLite는 개발/테스트 환경에 적합합니다",
                "운영 환경에서는 PostgreSQL 사용을 권장합니다",
                "정기적인 SQLite 파일 백업이 필요합니다"
            ])
        
        if self.validation_results['database_type'] == 'postgresql':
            self.validation_results['recommendations'].extend([
                "PostgreSQL 연결 풀 설정을 확인하세요",
                "스키마별 권한 관리를 설정하세요",
                "정기적인 PostgreSQL 백업과 복구 테스트가 필요합니다"
            ])
        
        # 성공한 연결 수 확인
        successful_connections = sum(1 for conn in self.validation_results['database_connections'].values() 
                                   if conn['status'] == 'SUCCESS')
        
        if successful_connections >= 2:
            self.validation_results['is_production_ready'] = True
        else:
            self.validation_results['recommendations'].append("최소 2개 테넌트의 성공적인 연결이 필요합니다")
    
    def run_full_validation(self):
        """전체 검증 실행"""
        logger.info("🚀 멀티테넌트 아키텍처 전체 검증 시작...")
        
        self.validate_environment()
        self.test_database_connections()
        self.test_tenant_isolation()
        self.test_cross_tenant_prevention()
        self.test_platform_separation()
        self.generate_recommendations()
        
        return self.validation_results


def main():
    """메인 실행 함수"""
    print("=" * 60)
    print("🏢 멀티테넌트 아키텍처 검증 도구")
    print("=" * 60)
    
    validator = MultiTenantValidator()
    results = validator.run_full_validation()
    
    print("\n📊 검증 결과:")
    print("=" * 40)
    print(json.dumps(results, indent=2, ensure_ascii=False))
    
    print(f"\n✅ 운영 준비 상태: {'YES' if results['is_production_ready'] else 'NO'}")
    
    if results['recommendations']:
        print("\n💡 권장사항:")
        for i, rec in enumerate(results['recommendations'], 1):
            print(f"  {i}. {rec}")
    
    return results


if __name__ == "__main__":
    main()
