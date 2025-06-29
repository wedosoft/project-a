#!/usr/bin/env python3
"""
벡터 데이터베이스 메타데이터 최적화 도구

Qdrant에 저장된 메타데이터 필드들의 상태를 분석하고
누락된 데이터를 채우는 최적화 작업을 수행합니다.
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional

# 프로젝트 루트를 Python 경로에 추가
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

# 환경변수 로드
from dotenv import load_dotenv
load_dotenv(dotenv_path=os.path.join(backend_dir, ".env"))

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def analyze_vector_metadata():
    """벡터 DB의 메타데이터 현황 분석"""
    try:
        from core.database.vectordb import vector_db
        
        logger.info("=== 벡터 DB 메타데이터 분석 시작 ===")
        
        # 컬렉션 정보 확인
        if not vector_db.collection_exists():
            logger.error("❌ 벡터 컬렉션이 존재하지 않습니다")
            return None
        
        info = vector_db.get_collection_info()
        logger.info(f"컬렉션 정보: {info}")
        
        # 전체 문서 수 확인
        total_count = vector_db.count()
        logger.info(f"총 문서 수: {total_count}")
        
        if total_count == 0:
            logger.warning("⚠️ 저장된 문서가 없습니다")
            return None
        
        # 샘플 문서들 조회하여 메타데이터 분석
        try:
            # Qdrant에서 직접 샘플 데이터 조회
            from qdrant_client.models import Filter, FieldCondition, MatchValue
            
            # 모든 테넌트의 문서 샘플 조회
            sample_size = min(50, total_count)
            
            # Qdrant 클라이언트로 직접 조회
            scroll_result = vector_db.client.scroll(
                collection_name=vector_db.collection_name,
                limit=sample_size,
                with_payload=True,
                with_vectors=False
            )
            
            points = scroll_result[0] if scroll_result else []
            logger.info(f"샘플 조회 결과: {len(points)}개 문서")
            
            return analyze_metadata_fields(points)
            
        except Exception as e:
            logger.error(f"샘플 데이터 조회 실패: {e}")
            return None
            
    except Exception as e:
        logger.error(f"벡터 DB 메타데이터 분석 실패: {e}")
        return None

def analyze_metadata_fields(points: List[Any]) -> Dict[str, Any]:
    """메타데이터 필드별 채우기 현황 분석"""
    
    field_stats = {}
    total_count = len(points)
    
    logger.info(f"=== {total_count}개 문서의 메타데이터 분석 ===")
    
    # 모든 필드 수집
    all_fields = set()
    for point in points:
        if hasattr(point, 'payload') and point.payload:
            all_fields.update(point.payload.keys())
    
    logger.info(f"발견된 메타데이터 필드: {len(all_fields)}개")
    logger.info(f"필드 목록: {sorted(all_fields)}")
    
    # 필드별 통계 계산
    for field in all_fields:
        filled_count = 0
        empty_count = 0
        null_count = 0
        sample_values = []
        
        for point in points:
            payload = point.payload if hasattr(point, 'payload') else {}
            
            if field in payload:
                value = payload[field]
                if value is None:
                    null_count += 1
                elif value == "" or value == [] or value == {}:
                    empty_count += 1
                else:
                    filled_count += 1
                    if len(sample_values) < 3:
                        sample_values.append(str(value)[:50])
            else:
                null_count += 1
        
        fill_rate = (filled_count / total_count) * 100
        
        field_stats[field] = {
            "filled_count": filled_count,
            "empty_count": empty_count,
            "null_count": null_count,
            "fill_rate": fill_rate,
            "sample_values": sample_values
        }
    
    # 결과 출력
    logger.info("\n=== 메타데이터 필드별 채우기 현황 ===")
    
    # 채우기 비율로 정렬
    sorted_fields = sorted(field_stats.items(), key=lambda x: x[1]['fill_rate'], reverse=True)
    
    for field, stats in sorted_fields:
        status = "✅" if stats['fill_rate'] > 80 else "⚠️" if stats['fill_rate'] > 20 else "❌"
        logger.info(f"{status} {field}: {stats['fill_rate']:.1f}% 채움 "
                   f"({stats['filled_count']}/{total_count})")
        
        if stats['sample_values']:
            logger.info(f"   샘플: {', '.join(stats['sample_values'])}")
    
    # 문제 필드 식별
    critical_fields = [field for field, stats in field_stats.items() 
                      if stats['fill_rate'] < 20]
    
    if critical_fields:
        logger.warning(f"\n⚠️ 심각하게 비어있는 필드 ({len(critical_fields)}개):")
        for field in critical_fields:
            logger.warning(f"  - {field}: {field_stats[field]['fill_rate']:.1f}%")
    
    # 필수 필드 체크
    required_fields = ['tenant_id', 'platform', 'doc_type', 'original_id']
    missing_required = [field for field in required_fields if field not in field_stats]
    
    if missing_required:
        logger.error(f"❌ 누락된 필수 필드: {missing_required}")
    
    return {
        "total_documents": total_count,
        "total_fields": len(all_fields),
        "field_stats": field_stats,
        "critical_fields": critical_fields,
        "missing_required": missing_required
    }

def suggest_metadata_optimization(analysis_result: Dict[str, Any]):
    """메타데이터 최적화 제안"""
    
    if not analysis_result:
        return
    
    logger.info("\n=== 메타데이터 최적화 제안 ===")
    
    field_stats = analysis_result['field_stats']
    critical_fields = analysis_result['critical_fields']
    
    # 1. 누락된 필수 데이터 채우기
    logger.info("1️⃣ 필수 메타데이터 보강:")
    
    essential_fields = {
        'tenant_id': '고객사 구분을 위한 필수 필드',
        'platform': '플랫폼 구분 (freshdesk 등)',
        'doc_type': '문서 타입 (ticket/article)',
        'original_id': '원본 시스템 ID',
        'status': '상태 정보',
        'priority': '우선순위',
        'created_at': '생성 날짜',
        'updated_at': '수정 날짜',
        'subject': '제목/요약',
        'company_name': '고객사명',
        'agent_name': '담당자명',
        'customer_email': '고객 이메일'
    }
    
    for field, description in essential_fields.items():
        if field in field_stats:
            fill_rate = field_stats[field]['fill_rate']
            if fill_rate < 50:
                logger.info(f"  ⚠️ {field}: {fill_rate:.1f}% - {description}")
        else:
            logger.info(f"  ❌ {field}: 누락 - {description}")
    
    # 2. 데이터 소스별 매핑 개선
    logger.info("\n2️⃣ 데이터 소스 매핑 개선:")
    logger.info("  - Freshdesk API 응답에서 메타데이터 추출 강화")
    logger.info("  - 티켓/문서 통합 시 메타데이터 보존")
    logger.info("  - 기본값 설정으로 null 값 방지")
    
    # 3. 인덱싱 최적화
    logger.info("\n3️⃣ 검색 성능 최적화:")
    high_fill_fields = [field for field, stats in field_stats.items() 
                       if stats['fill_rate'] > 80]
    logger.info(f"  인덱싱 권장 필드: {', '.join(high_fill_fields)}")
    
    # 4. 정리 대상 필드
    logger.info("\n4️⃣ 정리 권장 필드:")
    if critical_fields:
        logger.info(f"  제거 고려: {', '.join(critical_fields)}")
    
    return {
        "essential_missing": [f for f in essential_fields.keys() 
                             if f not in field_stats or field_stats[f]['fill_rate'] < 50],
        "indexing_candidates": high_fill_fields,
        "cleanup_candidates": critical_fields
    }

def create_metadata_enhancement_plan():
    """메타데이터 개선 계획 생성"""
    
    enhancement_plan = {
        "immediate_actions": [
            "processor.py에서 메타데이터 추출 로직 강화",
            "integrator.py에서 티켓/문서 메타데이터 보존",
            "기본값 설정으로 null 필드 방지"
        ],
        "data_mapping_improvements": {
            "freshdesk_ticket": {
                "subject": "ticket.subject",
                "status": "ticket.status",
                "priority": "ticket.priority",
                "created_at": "ticket.created_at",
                "updated_at": "ticket.updated_at",
                "company_name": "ticket.company.name",
                "agent_name": "ticket.responder.name",
                "customer_email": "ticket.requester.email"
            },
            "freshdesk_article": {
                "subject": "article.title",
                "status": "article.status",
                "created_at": "article.created_at",
                "updated_at": "article.updated_at",
                "category": "article.category.name",
                "folder": "article.folder.name"
            }
        },
        "code_changes_needed": [
            "core/ingest/integrator.py - 메타데이터 추출 강화",
            "core/ingest/processor.py - 벡터 저장 시 메타데이터 검증",
            "core/platforms/freshdesk/fetcher.py - API 응답 파싱 개선"
        ]
    }
    
    return enhancement_plan

def main():
    """메인 실행 함수"""
    logger.info("🔍 벡터 데이터베이스 메타데이터 최적화 도구 시작")
    
    # 1. 현황 분석
    analysis_result = analyze_vector_metadata()
    
    if analysis_result:
        # 2. 최적화 제안
        optimization_suggestions = suggest_metadata_optimization(analysis_result)
        
        # 3. 개선 계획
        enhancement_plan = create_metadata_enhancement_plan()
        
        # 4. 결과 요약
        logger.info("\n=== 최적화 작업 요약 ===")
        logger.info(f"📊 분석 문서 수: {analysis_result['total_documents']}")
        logger.info(f"📝 메타데이터 필드: {analysis_result['total_fields']}")
        logger.info(f"⚠️ 문제 필드: {len(analysis_result['critical_fields'])}")
        
        if optimization_suggestions:
            logger.info(f"🔧 개선 필요 필드: {len(optimization_suggestions['essential_missing'])}")
            logger.info(f"🚀 인덱싱 권장: {len(optimization_suggestions['indexing_candidates'])}")
        
        logger.info("\n✅ 분석 완료! 메타데이터 개선이 필요합니다.")
        return True
    else:
        logger.error("❌ 메타데이터 분석 실패")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
