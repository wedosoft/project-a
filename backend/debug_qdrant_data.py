#!/usr/bin/env python3
"""
Qdrant 데이터 구조 디버깅 스크립트
저장된 데이터의 메타데이터 구조와 필터링 조건을 확인합니다.

이 스크립트는 Qdrant 벡터 데이터베이스의 컬렉션 정보, 메타데이터 구조,
필드 분포 등을 분석하고 JSON 파일로 결과를 저장할 수 있습니다.
"""

import argparse
import asyncio
import datetime
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path
from pprint import pprint
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.models import FieldCondition, Filter, MatchValue

# 환경변수 로드
load_dotenv()

async def debug_qdrant_data(
    collection_name: str = "documents",
    company_id: Optional[str] = None,
    limit: int = 50,
    save_to_json: bool = False,
    output_dir: str = "./debug_output",
    analyze_field_relationships: bool = True,
    verbose: bool = False
) -> Dict[str, Any]:
    """
    Qdrant에 저장된 데이터의 메타데이터 구조와 필드 분포를 분석합니다.
    
    Args:
        collection_name: 분석할 Qdrant 컬렉션 이름 
        company_id: 특정 회사 ID로 필터링 (None이면 전체 데이터)
        limit: 분석에 사용할 데이터 개수
        save_to_json: 분석 결과를 JSON 파일로 저장할지 여부
        output_dir: JSON 파일 저장 디렉토리
        analyze_field_relationships: 필드 간 관계를 분석할지 여부
        verbose: 상세한 출력 활성화 여부
        
    Returns:
        분석 결과를 포함하는 딕셔너리
    """
    # 결과 저장용 딕셔너리
    results = {
        "timestamp": datetime.datetime.now().isoformat(),
        "collection": collection_name,
        "filtered_by_company": company_id,
        "sample_limit": limit,
        "collection_info": {},
        "field_distribution": {},
        "field_relationships": {},
        "samples": [],
        "filtering_tests": {}
    }
    
    try:
        client = QdrantClient(
            url=os.getenv("QDRANT_URL"),
            api_key=os.getenv("QDRANT_API_KEY")
        )
    except Exception as e:
        print(f"❌ Qdrant 클라이언트 초기화 실패: {str(e)}")
        return {"error": str(e)}
    
    print("🔍 Qdrant 데이터 구조 분석")
    print("=" * 60)
    
    # 0. 컬렉션 정보 확인
    print("\n📁 컬렉션 정보:")
    try:
        collection_info = client.get_collection(collection_name=collection_name)
        results["collection_info"] = {
            "name": collection_info.name,
            "vectors_count": collection_info.vectors_count,
            "points_count": collection_info.points_count,
            "status": collection_info.status,
            "vector_size": collection_info.config.params.vectors.size,
            "indexed_fields": [f.name for f in collection_info.payload_schema.values()]
        }
        
        print(f"컬렉션 이름: {collection_info.name}")
        print(f"벡터 수: {collection_info.vectors_count}")
        print(f"포인트 수: {collection_info.points_count}")
        print(f"상태: {collection_info.status}")
        print(f"벡터 크기: {collection_info.config.params.vectors.size}")
        print("인덱스된 필드:")
        for field in collection_info.payload_schema.values():
            print(f"  - {field.name} (타입: {field.dtype})")
    except Exception as e:
        print(f"❌ 컬렉션 정보 조회 실패: {str(e)}")
        results["collection_info"] = {"error": str(e)}
    
    # 필터 설정
    search_filter = None
    if company_id:
        search_filter = Filter(
            must=[
                FieldCondition(
                    key="company_id",
                    match=MatchValue(value=company_id)
                )
            ]
        )
        print(f"\n🏢 company_id='{company_id}' 필터 적용됨")
    
    # 1. 전체 데이터 샘플 확인
    print("\n📊 데이터 샘플 (처음 10개):")
    
    try:
        search_result = client.search(
            collection_name=collection_name,
            query_vector=[0.0] * 1536,  # 더미 벡터
            limit=min(10, limit),
            query_filter=search_filter,
            with_payload=True
        )
        
        results["samples"] = []
        
        for i, point in enumerate(search_result):
            print(f"\n--- 포인트 {i+1} ---")
            print(f"ID: {point.id}")
            print(f"Score: {point.score}")
            print("Payload:")
            
            if verbose:
                for key, value in point.payload.items():
                    print(f"  {key}: {value}")
            else:
                # 중요 필드만 출력
                important_fields = ["company_id", "doc_type", "source_type", "title", "id", "url"]
                for field in important_fields:
                    if field in point.payload:
                        print(f"  {field}: {point.payload[field]}")
            
            # 결과에 샘플 저장
            results["samples"].append({
                "id": point.id,
                "score": point.score,
                "payload": point.payload
            })
    
    except Exception as e:
        print(f"❌ 데이터 샘플 조회 실패: {str(e)}")
    
    # 2. 필드 분포 분석
    print("\n📊 필드 분포 분석:")
    
    try:
        # 더 많은 데이터 가져오기
        all_result = client.search(
            collection_name=collection_name,
            query_vector=[0.0] * 1536,
            limit=limit,
            query_filter=search_filter,
            with_payload=True
        )
        
        print(f"분석 대상 데이터 수: {len(all_result)}개")
        
        # 각 필드별 분포 분석
        field_distribution = {}
        field_keys_counts = Counter()
        
        # 필드 간 관계 분석을 위한 데이터
        doc_type_to_source_type = defaultdict(Counter)
        source_type_to_doc_type = defaultdict(Counter)
        
        for point in all_result:
            # 각 포인트의 필드 키 수집
            for key in point.payload.keys():
                field_keys_counts[key] += 1
            
            # 자주 사용되는 필드 분석
            for field_name in ["doc_type", "source_type", "company_id"]:
                if field_name not in field_distribution:
                    field_distribution[field_name] = Counter()
                
                field_value = str(point.payload.get(field_name, "None"))
                field_distribution[field_name][field_value] += 1
            
            # 필드 관계 분석
            if analyze_field_relationships:
                doc_type = str(point.payload.get("doc_type", "None"))
                source_type = str(point.payload.get("source_type", "None"))
                
                doc_type_to_source_type[doc_type][source_type] += 1
                source_type_to_doc_type[source_type][doc_type] += 1
        
        # 필드 키 존재 비율 출력
        print("\n필드 키 존재 비율:")
        for key, count in field_keys_counts.most_common():
            percentage = (count / len(all_result)) * 100
            print(f"  {key}: {count}/{len(all_result)} ({percentage:.1f}%)")
        
        # 자주 사용되는 필드 값 분포 출력
        for field_name, counter in field_distribution.items():
            print(f"\n{field_name} 값 분포:")
            for value, count in counter.most_common():
                percentage = (count / len(all_result)) * 100
                print(f"  {value}: {count}/{len(all_result)} ({percentage:.1f}%)")
        
        # 결과에 저장
        results["field_distribution"] = {
            "field_keys": dict(field_keys_counts),
            **{k: dict(v) for k, v in field_distribution.items()}
        }
        
        # 필드 관계 분석 결과 출력 및 저장
        if analyze_field_relationships:
            print("\n🔄 필드 관계 분석:")
            
            print("\ndoc_type → source_type 관계:")
            for doc_type, source_types in doc_type_to_source_type.items():
                print(f"  {doc_type}:")
                for source_type, count in source_types.most_common():
                    percentage = (count / sum(source_types.values())) * 100
                    print(f"    → {source_type}: {count} ({percentage:.1f}%)")
            
            print("\nsource_type → doc_type 관계:")
            for source_type, doc_types in source_type_to_doc_type.items():
                print(f"  {source_type}:")
                for doc_type, count in doc_types.most_common():
                    percentage = (count / sum(doc_types.values())) * 100
                    print(f"    → {doc_type}: {count} ({percentage:.1f}%)")
            
            # 관계 결과 저장
            results["field_relationships"] = {
                "doc_type_to_source_type": {k: dict(v) for k, v in doc_type_to_source_type.items()},
                "source_type_to_doc_type": {k: dict(v) for k, v in source_type_to_doc_type.items()}
            }
    
    except Exception as e:
        print(f"❌ 필드 분포 분석 실패: {str(e)}")
    
    # 3. 필터링 테스트
    print("\n🔍 필터링 테스트:")
    filtering_tests = {}
    
    # 테스트 대상 필드와 값 (doc_type과 source_type에 초점)
    test_fields = []
    
    # doc_type 테스트
    if "doc_type" in field_distribution:
        for doc_type in field_distribution["doc_type"].keys():
            if doc_type != "None":
                test_fields.append(("doc_type", doc_type))
    
    # source_type 테스트 (문자열 및 숫자)
    if "source_type" in field_distribution:
        for source_type in field_distribution["source_type"].keys():
            if source_type != "None":
                # source_type이 숫자 문자열이면 정수로도 테스트
                if source_type.isdigit():
                    test_fields.append(("source_type", source_type))
                    test_fields.append(("source_type", int(source_type)))
                else:
                    test_fields.append(("source_type", source_type))
    
    # 각 필드 값에 대한 필터링 테스트
    for field_name, field_value in test_fields:
        test_name = f"{field_name}={field_value}"
        print(f"\n테스트: {test_name}")
        
        try:
            # 필드에 대한 필터 생성
            field_filter = Filter(
                must=[
                    FieldCondition(
                        key=field_name,
                        match=MatchValue(value=field_value)
                    )
                ]
            )
            
            # company_id 필터가 있으면 추가
            if company_id:
                field_filter.must.append(
                    FieldCondition(
                        key="company_id",
                        match=MatchValue(value=company_id)
                    )
                )
            
            # 필터링 검색 실행
            filter_result = client.search(
                collection_name=collection_name,
                query_vector=[0.0] * 1536,
                limit=10,
                query_filter=field_filter,
                with_payload=True
            )
            
            # 결과 출력
            print(f"  결과: {len(filter_result)}개")
            
            # 몇 개 샘플 출력
            for i, point in enumerate(filter_result[:3]):
                print(f"  [{i+1}] ID: {point.id}")
                if point.payload:
                    field_value_in_result = point.payload.get(field_name, "Not found")
                    print(f"      {field_name}: {field_value_in_result}")
                    print(f"      company_id: {point.payload.get('company_id', 'None')}")
                    if field_name != "doc_type":
                        print(f"      doc_type: {point.payload.get('doc_type', 'None')}")
                    if field_name != "source_type":
                        print(f"      source_type: {point.payload.get('source_type', 'None')}")
            
            # 테스트 결과 저장
            filtering_tests[test_name] = {
                "field": field_name,
                "value": field_value,
                "count": len(filter_result),
                "samples": [
                    {
                        "id": p.id,
                        "payload": {
                            field_name: p.payload.get(field_name, None),
                            "company_id": p.payload.get("company_id", None),
                            "doc_type": p.payload.get("doc_type", None) if field_name != "doc_type" else None,
                            "source_type": p.payload.get("source_type", None) if field_name != "source_type" else None
                        }
                    }
                    for p in filter_result[:3]
                ]
            }
            
        except Exception as e:
            print(f"❌ {field_name}={field_value} 필터링 실패: {str(e)}")
            filtering_tests[test_name] = {"error": str(e)}
    
    # 4. KB 문서 복합 필터링 테스트
    print(f"\n🔍 KB 문서 복합 필터링 테스트:")
    
    # doc_type="kb" 테스트
    kb_filters = []
    
    # 테스트 1: doc_type="kb"
    kb_filters.append({
        "name": "doc_type='kb'",
        "filter": Filter(
            must=[
                FieldCondition(
                    key="doc_type",
                    match=MatchValue(value="kb")
                )
            ]
        )
    })
    
    # 테스트 2: source_type="1" 또는 source_type=1
    kb_filters.append({
        "name": "source_type='1'",
        "filter": Filter(
            must=[
                FieldCondition(
                    key="source_type",
                    match=MatchValue(value="1")
                )
            ]
        )
    })
    
    kb_filters.append({
        "name": "source_type=1",
        "filter": Filter(
            must=[
                FieldCondition(
                    key="source_type",
                    match=MatchValue(value=1)
                )
            ]
        )
    })
    
    # 각 필터 테스트
    for filter_test in kb_filters:
        filter_name = filter_test["name"]
        test_filter = filter_test["filter"]
        
        # company_id 필터가 있으면 추가
        if company_id:
            test_filter.must.append(
                FieldCondition(
                    key="company_id",
                    match=MatchValue(value=company_id)
                )
            )
        
        print(f"\n테스트: {filter_name}")
        try:
            kb_result = client.search(
                collection_name=collection_name,
                query_vector=[0.0] * 1536,
                limit=10,
                query_filter=test_filter,
                with_payload=True
            )
            
            print(f"  결과: {len(kb_result)}개")
            
            # 결과 저장
            filtering_tests[filter_name] = {
                "count": len(kb_result),
                "samples": []
            }
            
            # 결과 샘플 출력
            if kb_result:
                for i, point in enumerate(kb_result[:3]):
                    print(f"  [{i+1}] ID: {point.id}")
                    if point.payload:
                        print(f"      doc_type: {point.payload.get('doc_type', 'None')}")
                        print(f"      source_type: {point.payload.get('source_type', 'None')}")
                        print(f"      company_id: {point.payload.get('company_id', 'None')}")
                        print(f"      title: {point.payload.get('title', 'No title')[:50]}...")
                        
                        # 결과 저장
                        filtering_tests[filter_name]["samples"].append({
                            "id": point.id,
                            "doc_type": point.payload.get('doc_type', None),
                            "source_type": point.payload.get('source_type', None),
                            "company_id": point.payload.get('company_id', None),
                            "title": point.payload.get('title', None)
                        })
                        
        except Exception as e:
            print(f"❌ {filter_name} 테스트 실패: {str(e)}")
            filtering_tests[filter_name] = {"error": str(e)}
    
    # 결과에 필터링 테스트 저장
    results["filtering_tests"] = filtering_tests
    
    # JSON 파일로 저장
    if save_to_json:
        try:
            # 출력 디렉토리 생성
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            
            # 타임스탬프를 포함한 파일명
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            company_suffix = f"_{company_id}" if company_id else ""
            filename = f"qdrant_debug_{collection_name}{company_suffix}_{timestamp}.json"
            filepath = output_path / filename
            
            # JSON 저장
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            
            print(f"\n✅ 분석 결과가 다음 파일에 저장되었습니다: {filepath}")
        
        except Exception as e:
            print(f"❌ JSON 파일 저장 실패: {str(e)}")
    
    print("\n" + "=" * 60)
    print("✅ 분석 완료")
    
    return results

def parse_args():
    """커맨드 라인 인수를 파싱합니다."""
    parser = argparse.ArgumentParser(description="Qdrant 벡터 데이터베이스 구조 분석 도구")
    
    parser.add_argument(
        "-c", "--collection",
        default="documents",
        help="분석할 Qdrant 컬렉션 이름 (기본값: documents)"
    )
    
    parser.add_argument(
        "--company",
        help="특정 회사 ID로 필터링"
    )
    
    parser.add_argument(
        "-l", "--limit",
        type=int,
        default=50,
        help="분석에 사용할 최대 데이터 개수 (기본값: 50)"
    )
    
    parser.add_argument(
        "--save",
        action="store_true",
        help="분석 결과를 JSON 파일로 저장"
    )
    
    parser.add_argument(
        "--output-dir",
        default="./debug_output",
        help="JSON 파일 저장 디렉토리 (기본값: ./debug_output)"
    )
    
    parser.add_argument(
        "--no-relationships",
        action="store_true",
        help="필드 간 관계 분석 비활성화"
    )
    
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="상세한 출력 활성화"
    )
    
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    
    asyncio.run(debug_qdrant_data(
        collection_name=args.collection,
        company_id=args.company,
        limit=args.limit,
        save_to_json=args.save,
        output_dir=args.output_dir,
        analyze_field_relationships=not args.no_relationships,
        verbose=args.verbose
    ))
