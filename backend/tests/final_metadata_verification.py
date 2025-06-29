#!/usr/bin/env python3
"""
벡터 DB에 저장된 메타데이터의 정확성 최종 검증 스크립트

실제 Qdrant에 저장된 각 문서의 메타데이터 구조와 값들을 확인하여
title/subject, status, priority 등 주요 필드가 올바르게 저장되었는지 검증합니다.
"""

import os
import sys
import json
import logging
from pathlib import Path

# 프로젝트 루트를 Python path에 추가
current_dir = Path(__file__).resolve().parent
if str(current_dir) not in sys.path:
    sys.path.append(str(current_dir))

from core.database.vectordb import vector_db

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def verify_vector_metadata(limit: int = 10):
    """벡터 DB에 저장된 메타데이터 상세 검증"""
    print("=== 벡터 DB 메타데이터 최종 검증 ===\n")
    
    try:
        # Qdrant에서 모든 점 조회
        response = vector_db.client.scroll(
            collection_name="documents",
            limit=limit,
            with_payload=True,
            with_vectors=False
        )
        
        if not response or not hasattr(response, 'points') or not response.points:
            print("❌ 저장된 벡터가 없습니다.")
            return
        
        points = response.points
        print(f"✅ 총 {len(points)}개 벡터 발견\n")
        
        # 각 문서별 상세 검증
        for i, point in enumerate(points, 1):
            point_id = point.id
            metadata = point.payload if point.payload else {}
            
            print(f"📄 문서 {i}: {point_id}")
            print("-" * 50)
            
            # 기본 정보
            tenant_id = metadata.get('tenant_id', 'N/A')
            platform = metadata.get('platform', 'N/A')
            original_id = metadata.get('original_id', 'N/A')
            doc_type = metadata.get('doc_type', 'N/A')
            
            print(f"  🏷️  기본 정보:")
            print(f"     - tenant_id: {tenant_id}")
            print(f"     - platform: {platform}")
            print(f"     - original_id: {original_id}")
            print(f"     - doc_type: {doc_type}")
            
            # 문서 타입별 특화 메타데이터 검증
            if doc_type == "integrated_ticket":
                print(f"  🎫 티켓 메타데이터:")
                print(f"     - subject: {metadata.get('subject', 'N/A')}")
                print(f"     - status: {metadata.get('status', 'N/A')} (타입: {type(metadata.get('status'))})")
                print(f"     - priority: {metadata.get('priority', 'N/A')} (타입: {type(metadata.get('priority'))})")
                print(f"     - requester_name: {metadata.get('requester_name', 'N/A')}")
                print(f"     - agent_name: {metadata.get('agent_name', 'N/A')}")
                print(f"     - company_name: {metadata.get('company_name', 'N/A')}")
                print(f"     - has_attachments: {metadata.get('has_attachments', 'N/A')}")
                print(f"     - complexity_level: {metadata.get('complexity_level', 'N/A')}")
                
            elif doc_type == "integrated_article":
                print(f"  📚 KB 문서 메타데이터:")
                print(f"     - title: {metadata.get('title', 'N/A')}")
                print(f"     - status: {metadata.get('status', 'N/A')} (타입: {type(metadata.get('status'))})")
                print(f"     - category: {metadata.get('category', 'N/A')}")
                print(f"     - folder: {metadata.get('folder', 'N/A')}")
                print(f"     - article_type: {metadata.get('article_type', 'N/A')}")
                print(f"     - agent_name: {metadata.get('agent_name', 'N/A')}")
                print(f"     - tags: {metadata.get('tags', 'N/A')}")
                print(f"     - view_count: {metadata.get('view_count', 'N/A')}")
                print(f"     - has_attachments: {metadata.get('has_attachments', 'N/A')}")
                print(f"     - complexity_level: {metadata.get('complexity_level', 'N/A')}")
            
            # 시간 정보
            print(f"  ⏰ 시간 정보:")
            print(f"     - created_at: {metadata.get('created_at', 'N/A')}")
            print(f"     - updated_at: {metadata.get('updated_at', 'N/A')}")
            
            # 전체 메타데이터 필드 수
            print(f"  📊 총 메타데이터 필드 수: {len(metadata)}")
            
            # None/빈 값 검증
            none_fields = [k for k, v in metadata.items() if v is None or v == ""]
            if none_fields:
                print(f"  ⚠️  None/빈 값 필드: {none_fields}")
            else:
                print(f"  ✅ 모든 필드에 유효한 값 존재")
            
            print()
        
        # 요약 통계
        print("📈 메타데이터 품질 요약:")
        print("-" * 30)
        
        total_points = len(points)
        ticket_count = sum(1 for p in points if p.payload.get('doc_type') == 'integrated_ticket')
        article_count = sum(1 for p in points if p.payload.get('doc_type') == 'integrated_article')
        
        print(f"총 문서 수: {total_points}")
        print(f"티켓: {ticket_count}개")
        print(f"KB 문서: {article_count}개")
        
        # status 필드 타입 검증
        status_types = {}
        for point in points:
            status = point.payload.get('status')
            status_type = type(status).__name__
            status_types[status_type] = status_types.get(status_type, 0) + 1
        
        print(f"Status 필드 타입 분포: {status_types}")
        
        # priority 필드 타입 검증 (티켓만)
        priority_types = {}
        for point in points:
            if point.payload.get('doc_type') == 'integrated_ticket':
                priority = point.payload.get('priority')
                priority_type = type(priority).__name__
                priority_types[priority_type] = priority_types.get(priority_type, 0) + 1
        
        if priority_types:
            print(f"Priority 필드 타입 분포 (티켓): {priority_types}")
        
        print("\n✅ 메타데이터 검증 완료!")
        
    except Exception as e:
        logger.error(f"메타데이터 검증 중 오류: {e}")
        print(f"❌ 오류: {e}")

if __name__ == "__main__":
    verify_vector_metadata()
