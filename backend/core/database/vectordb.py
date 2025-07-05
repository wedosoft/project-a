"""
벡터 데이터베이스 추상화 인터페이스 (Freshdesk 전용)

이 모듈은 여러 벡터 데이터베이스(ChromaDB, Qdrant 등)에 대한 통합 인터페이스를 제공합니다.
Freshdesk 고객사별 데이터 분리와 메타데이터 필터링을 지원합니다.

프로젝트 규칙 및 가이드라인: /PROJECT_RULES.md 참조
"""

import logging
import os
import time
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from dotenv import load_dotenv
from core.config import get_settings

# Qdrant 클라이언트
from qdrant_client import QdrantClient
from qdrant_client.http.models import (
    CollectionStatus,
    FieldCondition,
    Filter,
    MatchAny,
    MatchValue,
)
from qdrant_client.models import Distance, PointStruct, VectorParams

# 로깅 설정
logger = logging.getLogger(__name__)

# 환경 변수
backend_dir = Path(__file__).parent.parent
load_dotenv(backend_dir / ".env")
settings = get_settings()
QDRANT_URL = settings.QDRANT_URL
QDRANT_API_KEY = settings.QDRANT_API_KEY
# 🌍 임베딩 시스템에 따른 벡터 차원 자동 설정
USE_MULTILINGUAL = os.getenv("USE_MULTILINGUAL_EMBEDDING", "false").lower() == "true"
if USE_MULTILINGUAL:
    VECTOR_SIZE = 3072  # text-embedding-3-large (다국어 최적화)
    logger.info("🌍 벡터 차원: 3072 (다국어 최적화 모드)")
else:
    VECTOR_SIZE = 1536  # text-embedding-3-small (기존 시스템)
    logger.info("🔄 벡터 차원: 1536 (기존 하이브리드 모드)")
COLLECTION_NAME = "documents"  # 기본 컬렉션명


class VectorDBInterface(ABC):
    """벡터 데이터베이스 인터페이스 추상 클래스"""

    @abstractmethod
    def add_documents(
        self, texts: List[str], embeddings: List[List[float]], metadatas: List[Dict[str, Any]], ids: List[str]
    ) -> bool:
        """문서 추가"""
        pass

    @abstractmethod
    def delete_documents(self, ids: List[str], tenant_id: Optional[str] = None) -> bool:
        """문서 삭제"""
        pass

    @abstractmethod
    def search(
        self, 
        query_embedding: List[float], 
        top_k: int, 
        tenant_id: str,
        platform: Optional[str] = None,
        doc_type: Optional[str] = None,
        has_attachments: Optional[bool] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """벡터 검색 (멀티플랫폼/멀티테넌트 지원, 첨부파일 필터링 포함)"""
        pass

    @abstractmethod
    def count(self, tenant_id: Optional[str] = None, platform: Optional[str] = None) -> int:
        """문서 수 반환 (멀티플랫폼/멀티테넌트 지원)"""
        pass
    
    @abstractmethod
    def get_by_id(self, original_id_value: str, doc_type: Optional[str] = None, tenant_id: Optional[str] = None, platform: Optional[str] = None) -> Dict[str, Any]:
        """원본 ID로 단일 문서 조회 (멀티플랫폼/멀티테넌트 지원)"""
        pass

    @abstractmethod
    def collection_exists(self) -> bool:
        """컬렉션 존재 여부 확인"""
        pass

    @abstractmethod
    def get_collection_info(self) -> Dict[str, Any]:
        """컬렉션 정보 조회"""
        pass

    @abstractmethod
    def drop_collection(self, collection_name: Optional[str] = None) -> bool:
        """컬렉션 삭제"""
        pass


class QdrantAdapter(VectorDBInterface):
    """Qdrant 벡터 DB 어댑터 구현"""

    def __init__(self, collection_name: str = COLLECTION_NAME):
        """Qdrant 클라이언트 초기화"""
        self.collection_name = collection_name
        # 타임아웃 설정 추가 (기본값: 60초)
        self.client = QdrantClient(
            url=QDRANT_URL,
            api_key=QDRANT_API_KEY,
            timeout=120,  # 타임아웃을 120초로 설정
            prefer_grpc=False  # HTTP/REST 사용 (더 안정적)
        )
        self._ensure_collection_exists() # 기본 문서 컬렉션 확인 (인덱스 생성 포함)

    def _ensure_collection_exists(self) -> None:
        """컬렉션이 없으면 생성"""
        collections = self.client.get_collections()
        collection_names = [collection.name for collection in collections.collections]
        
        if self.collection_name not in collection_names:
            logger.info(f"컬렉션 '{self.collection_name}' 생성 시작")
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
            )
            
            # 필수 인덱스 생성 (성능 및 필터링 향상)
            try:
                logger.info(f"필수 필드에 대한 인덱스 생성 중...")
                # 테넌트 ID 인덱스 생성 (멀티테넌트 지원)
                self.client.create_payload_index(collection_name=self.collection_name, field_name="tenant_id", field_schema="keyword")
                # 플랫폼 인덱스 생성 (멀티플랫폼 지원)
                self.client.create_payload_index(collection_name=self.collection_name, field_name="platform", field_schema="keyword")
                # 원본 ID 인덱스 생성
                try:
                    self.client.create_payload_index(collection_name=self.collection_name, field_name="original_id", field_schema="keyword")
                    logger.info(f"original_id 인덱스(keyword) 생성 완료")
                except Exception as original_id_err:
                    logger.warning(f"original_id 인덱스 생성 실패: {original_id_err}")
                # 문서 타입 인덱스 생성 - 키워드 타입만 사용
                try:
                    self.client.create_payload_index(collection_name=self.collection_name, field_name="doc_type", field_schema="keyword")
                    logger.info(f"doc_type 인덱스(keyword) 생성 완료")
                except Exception as doc_type_err:
                    logger.warning(f"doc_type 키워드 인덱스 생성 실패: {doc_type_err}")
                
                # 소스 타입 인덱스 생성
                self.client.create_payload_index(collection_name=self.collection_name, field_name="source_type", field_schema="keyword")
                
                # 상태 인덱스 생성 (KB published 상태 = 1)
                try:
                    self.client.create_payload_index(collection_name=self.collection_name, field_name="status", field_schema="integer")
                    logger.info(f"status 인덱스(integer) 생성 완료")
                except Exception as status_err:
                    logger.warning(f"status 인덱스 생성 실패: {status_err}")
                
                logger.info(f"멀티플랫폼/멀티테넌트 인덱스 생성 완료")
            except Exception as e:
                logger.warning(f"인덱스 생성 중 오류 발생 (비정상적인 동작이 예상될 수 있음): {e}")
                
            logger.info(f"컬렉션 '{self.collection_name}' 생성 완료")






    def add_documents(
        self, 
        texts: List[str], 
        embeddings: List[List[float]], 
        metadatas: List[Dict[str, Any]], 
        ids: List[str]
    ) -> bool:
        """
        문서 추가 (배치 단위로 처리)
        
        Args:
            texts: 문서 텍스트 목록
            embeddings: 문서 임베딩 목록
            metadatas: 문서 메타데이터 목록 (tenant_id, doc_type, id 필수)
            ids: 문서 ID 목록 (원본 숫자 ID, 문자열)
            
        Returns:
            성공 여부
        """
        if len(texts) != len(embeddings) or len(texts) != len(metadatas) or len(texts) != len(ids):
            raise ValueError("텍스트, 임베딩, 메타데이터, ID 목록의 길이가 일치해야 합니다")
        # Platform-Neutral 3-Tuple ID 시스템 유효성 검사 및 정규화
        for i, (metadata, id) in enumerate(zip(metadatas, ids)):
            # Platform-Neutral 3-Tuple 필수 필드 확인
            if "tenant_id" not in metadata:
                raise ValueError(f"메타데이터 #{i}에 tenant_id가 없습니다")
            if "platform" not in metadata:
                raise ValueError(f"메타데이터 #{i}에 platform이 없습니다")
            if "doc_type" not in metadata or not metadata["doc_type"]:
                raise ValueError(f"메타데이터 #{i}에 doc_type이 없습니다. Platform-Neutral 3-Tuple: (tenant_id={metadata.get('tenant_id')}, platform={metadata.get('platform')}, original_id={id})")
            
            # original_id 정규화: 접두어 제거하여 플랫폼 원본 ID만 사용
            if "original_id" not in metadata:
                # original_id가 없으면 id에서 추출 (하위 호환성)
                id_str = str(id)
                if id_str.startswith("ticket-"):
                    metadata["original_id"] = id_str[7:]
                elif id_str.startswith("kb-"):
                    metadata["original_id"] = id_str[3:]
                else:
                    metadata["original_id"] = id_str
            else:
                # 기존 original_id도 정규화
                original_id_str = str(metadata["original_id"])
                if original_id_str.startswith("ticket-"):
                    metadata["original_id"] = original_id_str[7:]
                elif original_id_str.startswith("kb-"):
                    metadata["original_id"] = original_id_str[3:]
                else:
                    metadata["original_id"] = original_id_str
            
            # Platform-Neutral ID를 문자열로 통일
            metadata["original_id"] = str(metadata["original_id"])
            
            # 하위 호환성을 위한 id 필드 유지 (deprecated, original_id와 동일)
            metadata["id"] = metadata["original_id"]
        try:
            # 배치 크기 설정 (25개씩 처리)
            BATCH_SIZE = 25
            success = True
            points = []
            for i, (text, embedding, metadata, id) in enumerate(zip(texts, embeddings, metadatas, ids)):
                # Platform-Neutral 3-Tuple 기반 Payload 구성 (원본 텍스트 + 풍부한 메타데이터)
                # 필수 검색 필드를 루트 레벨에 저장
                essential_fields = {
                    "tenant_id": metadata.get("tenant_id"),
                    "platform": metadata.get("platform"), 
                    "doc_type": metadata.get("doc_type"),
                    "original_id": metadata.get("original_id"),
                    "object_type": metadata.get("object_type", "unknown"),
                    "content": text,  # 문서 내용 (원본 텍스트)
                }
                
                # 검색에 자주 사용되는 필드들을 루트 레벨에 유지 (필터링 성능 향상)
                searchable_fields = {}
                if metadata.get("status") is not None:
                    searchable_fields["status"] = metadata.get("status")
                if metadata.get("priority") is not None:
                    searchable_fields["priority"] = metadata.get("priority")
                if metadata.get("subject"):
                    searchable_fields["subject"] = metadata.get("subject")
                if metadata.get("title"):
                    searchable_fields["title"] = metadata.get("title")
                if metadata.get("has_attachments") is not None:
                    searchable_fields["has_attachments"] = metadata.get("has_attachments")
                if metadata.get("created_at"):
                    searchable_fields["created_at"] = metadata.get("created_at")
                if metadata.get("updated_at"):
                    searchable_fields["updated_at"] = metadata.get("updated_at")
                
                # 이미지/첨부파일 관련 메타데이터 (최적화된 구조)
                if metadata.get("has_inline_images") is not None:
                    searchable_fields["has_inline_images"] = metadata.get("has_inline_images")
                if metadata.get("attachment_count") is not None:
                    searchable_fields["attachment_count"] = metadata.get("attachment_count")
                
                # 확장 메타데이터: 모든 원본 정보 포함 (첨부파일, 커스텀 필드 등)
                extended_metadata = {k: v for k, v in metadata.items() 
                                   if k not in essential_fields and k not in searchable_fields and v is not None}
                
                payload = {
                    **essential_fields,
                    **searchable_fields,  # 검색 최적화를 위해 루트 레벨에 배치
                    "extended_metadata": extended_metadata  # 확장 정보는 JSON 객체로 저장
                }
                
                # Platform-Neutral 3-Tuple 기반 유니크 Qdrant 포인트 ID 생성
                # (tenant_id, platform, original_id) 조합으로 결정론적 UUID 생성
                tenant_id = metadata["tenant_id"]
                platform = metadata["platform"] 
                original_id = metadata["original_id"]
                
                # 3-tuple 기반 유니크 키 생성
                unique_key = f"{tenant_id}:{platform}:{original_id}"
                
                # 결정론적 UUID 생성 (동일한 3-tuple은 항상 동일한 UUID)
                from hashlib import md5
                uuid_id = uuid.UUID(md5(unique_key.encode()).hexdigest())
                
                point = PointStruct(
                    id=str(uuid_id),
                    vector=embedding,
                    payload=payload
                )
                points.append(point)
                # 배치 크기에 도달하거나 마지막 항목이면 저장
                if len(points) >= BATCH_SIZE or i == len(texts) - 1:
                    try:
                        self.client.upsert(
                            collection_name=self.collection_name,
                            points=points,
                            wait=True
                        )
                        logger.debug(f"배치 저장 성공: {len(points)}개")
                        points = []
                    except Exception as batch_error:
                        logger.error(f"배치 저장 실패: {batch_error}")
                        
                        # 컬렉션이 없다는 404 오류인 경우 컬렉션 생성 후 재시도
                        error_str = str(batch_error).lower()
                        if "404" in error_str or "not found" in error_str or "doesn't exist" in error_str:
                            logger.warning(f"컬렉션 '{self.collection_name}'이 존재하지 않음. 자동 생성 시도...")
                            try:
                                # 먼저 컬렉션 존재 여부 확인
                                collections = self.client.get_collections()
                                collection_exists = any(col.name == self.collection_name for col in collections.collections)
                                
                                if not collection_exists:
                                    logger.info(f"컬렉션 '{self.collection_name}' 확인: 존재하지 않음, 생성 중...")
                                    # 컬렉션 재생성
                                    self._ensure_collection_exists()
                                    logger.info(f"컬렉션 '{self.collection_name}' 자동 생성 완료")
                                else:
                                    logger.info(f"컬렉션 '{self.collection_name}' 확인: 이미 존재함")
                                
                                # 잠시 대기 후 재시도 (컬렉션 생성 완료 대기)
                                import time
                                time.sleep(1)
                                
                                # 재시도
                                logger.info(f"컬렉션 확인 후 배치 저장 재시도 (크기: {len(points)})")
                                self.client.upsert(
                                    collection_name=self.collection_name,
                                    points=points,
                                    wait=True
                                )
                                logger.info(f"재시도 후 배치 저장 성공 (크기: {len(points)})")
                                points = []
                            except Exception as retry_error:
                                logger.error(f"컬렉션 재생성/재시도 실패: {retry_error}")
                                # 세부 오류 정보 로깅
                                logger.error(f"재시도 실패 상세: 컬렉션={self.collection_name}, 배치크기={len(points)}")
                                success = False
                                break
                        else:
                            logger.error(f"배치 저장 실패 (재시도 불가능한 오류): {batch_error}")
                            success = False
                            break
            return success
        except Exception as e:
            logger.error(f"문서 추가 실패: {e}")
            return False

    def delete_documents(self, ids: List[str], tenant_id: Optional[str] = None, platform: Optional[str] = None) -> bool:
        """
        Platform-Neutral 3-Tuple 기반 문서 삭제
        
        Args:
            ids: 삭제할 문서의 original_id 목록 (플랫폼 원본 ID)
            tenant_id: 테넌트 ID (필수, 테넌트 격리)
            platform: 플랫폼 ID (필수, 멀티플랫폼 지원)
            
        Returns:
            성공 여부
        """
        if not tenant_id:
            raise ValueError("tenant_id는 필수입니다 (테넌트 격리)")
        if not platform:
            raise ValueError("platform은 필수입니다 (멀티플랫폼 지원)")
            
        try:
            import uuid
            from hashlib import md5
            
            # Platform-Neutral 3-Tuple 기반 UUID 생성
            uuid_ids = []
            for original_id in ids:
                # original_id 정규화 (접두어 제거)
                clean_id = str(original_id)
                if clean_id.startswith("ticket-"):
                    clean_id = clean_id[7:]
                elif clean_id.startswith("kb-"):
                    clean_id = clean_id[3:]
                
                # 3-tuple 기반 유니크 키 생성
                unique_key = f"{tenant_id}:{platform}:{clean_id}"
                uuid_id = uuid.UUID(md5(unique_key.encode()).hexdigest())
                uuid_ids.append(str(uuid_id))
            
            # Platform-Neutral 필터 조건 구성
            filter_condition = Filter(
                must=[
                    FieldCondition(
                        key="tenant_id",
                        match=MatchValue(value=tenant_id)
                    ),
                    FieldCondition(
                        key="platform", 
                        match=MatchValue(value=platform)
                    )
                ]
            )
            
            # 테넌트 ID 필터와 문서 ID 목록을 함께 사용하여 삭제 시도
            try:
                self.client.delete(
                    collection_name=self.collection_name,
                    points_selector=uuid_ids,
                    wait=True,
                    filter=filter_condition
                )
            except Exception as filter_error:
                logger.warning(f"필터를 사용한 삭제 실패: {filter_error}, 대체 방법 시도 중...")
                
                # 대체 방법: 먼저 해당 문서들을 조회하여 테넌트 ID 확인 후 삭제
                for uuid_id in uuid_ids:
                    try:
                        # 문서 조회
                        point = self.client.retrieve(
                            collection_name=self.collection_name,
                            ids=[uuid_id],
                            with_payload=True
                        )
                        
                        # 문서가 존재하고 테넌트 ID가 일치하면 삭제
                        if point and len(point) > 0 and point[0].payload.get("tenant_id") == tenant_id:
                            self.client.delete(
                                collection_name=self.collection_name,
                                points_selector=[uuid_id],
                                wait=True
                            )
                            logger.info(f"문서 {uuid_id} 삭제 완료")
                        elif point and len(point) > 0:
                            logger.warning(f"문서 {uuid_id}의 테넌트 ID가 일치하지 않아 삭제하지 않습니다.")
                    except Exception as e:
                        logger.error(f"문서 {uuid_id} 삭제 중 오류 발생: {e}")
            else:
                # 관리자 모드: 모든 문서 삭제
                self.client.delete(
                    collection_name=self.collection_name,
                    points_selector=uuid_ids,
                    wait=True
                )
                
            return True
        except Exception as e:
            logger.error(f"문서 삭제 실패: {e}")
            return False

    def search(
        self, 
        query_embedding: List[float], 
        top_k: int, 
        tenant_id: str,
        platform: Optional[str] = None,  # 플랫폼 필터링 (freshdesk, zendesk 등)
        doc_type: str = None,  # 문서 타입 필터링 (ticket, article)
        has_attachments: Optional[bool] = None,  # 첨부파일 필터링
        **kwargs  # 추가 필터 파라미터들
    ) -> Dict[str, Any]:
        """
        벡터 검색 (멀티플랫폼/멀티테넌트 지원) - Qdrant 쿼리 레벨에서 모든 필터링 직접 처리
        
        Args:
            query_embedding: 쿼리 임베딩
            top_k: 반환할 최대 문서 수
            tenant_id: 테넌트 ID (필수)
            platform: 플랫폼 필터 (선택사항, "freshdesk", "zendesk" 등)
            doc_type: 문서 타입 필터 (선택사항, "ticket" 또는 "article")
            has_attachments: 첨부파일 존재 필터 (선택사항, True/False)
            **kwargs: 추가 필터 파라미터들
            
        Returns:
            검색 결과 딕셔너리
        """
        if not tenant_id:
            raise ValueError("tenant_id는 필수 매개변수입니다.")
            
        # 필터 조건 구성 - tenant_id는 필수
        filter_conditions = [
            FieldCondition(key="tenant_id", match=MatchValue(value=tenant_id))
        ]
        
        # 플랫폼 필터 추가 (멀티플랫폼 지원)
        if platform:
            filter_conditions.append(
                FieldCondition(key="platform", match=MatchValue(value=platform))
            )
        
        # doc_type 필터를 Qdrant 쿼리 레벨에서 직접 처리
        if doc_type:
            filter_conditions.append(
                FieldCondition(key="doc_type", match=MatchValue(value=doc_type))
            )
        
        # 첨부파일 필터 추가
        if has_attachments is not None:
            filter_conditions.append(
                FieldCondition(key="has_attachments", match=MatchValue(value=has_attachments))
            )
        
        # 추가 필터 처리 (kwargs)
        for key, value in kwargs.items():
            if value is not None and key not in ["tenant_id", "platform", "doc_type", "has_attachments"]:
                if isinstance(value, list):
                    # 리스트 값은 MatchAny로 처리
                    filter_conditions.append(
                        FieldCondition(key=key, match=MatchAny(any=value))
                    )
                else:
                    # 단일 값은 MatchValue로 처리
                    filter_conditions.append(
                        FieldCondition(key=key, match=MatchValue(value=value))
                    )
        
        logger.debug(f"검색 요청: tenant_id={tenant_id}, top_k={top_k}")
        
        # 모든 필터를 Qdrant 쿼리에 적용
        search_filter = Filter(must=filter_conditions)
        
        try:
            logger.debug(f"Qdrant 검색 시도: {top_k}개 문서")
            
            # 최신 API 사용: query_points (search는 deprecated)
            try:
                from qdrant_client.models import PointRequest
                
                search_results = self.client.query_points(
                    collection_name=self.collection_name,
                    query=query_embedding,
                    query_filter=search_filter,
                    limit=top_k,
                    with_payload=True,
                    with_vectors=False
                ).points
                logger.debug(f"query_points 검색 성공: {len(search_results)}개")
            except (ImportError, AttributeError) as api_error:
                logger.info(f"query_points API 미지원, search API 사용: {api_error}")
                # 이전 API 방식 (search) 사용
                search_results = self.client.search(
                    collection_name=self.collection_name,
                    query_vector=query_embedding,
                    query_filter=search_filter,  # 최신 API: query_filter 사용
                    limit=top_k,  # 정확한 top_k만 요청 (메모리 필터링 불필요)
                    with_payload=True,
                    with_vectors=False  # 성능 최적화: 벡터 반환 비활성화
                )
                logger.debug(f"search 검색 성공: {len(search_results)}개")
                
        except Exception as e:
            logger.warning(f"최신 API 검색 실패: {e}, 이전 API로 재시도...")
            
            try:
                # 이전 API 방식 (filter)으로 재시도
                search_results = self.client.search(
                    collection_name=self.collection_name,
                    query_vector=query_embedding,
                    filter=search_filter,  # 이전 API: filter 사용
                    limit=top_k,
                    with_payload=True,
                    with_vectors=False
                )
                logger.debug(f"filter 방식 검색 성공: {len(search_results)}개")
            except Exception as filter_error:
                logger.error(f"검색 실패: {filter_error}")
                # 오류 발생 시 빈 결과 반환
                return {
                    "results": [],
                    "total": 0,
                    "error": str(filter_error)
                }
        
        # Qdrant에서 이미 필터링된 결과 처리 (메모리 필터링 불필요)
        filtered_results = []
        
        for hit in search_results:
            # 결과 변환
            result = {
                "id": hit.id,
                "score": hit.score,
                **hit.payload
            }
            filtered_results.append(result)
        
        logger.debug(f"최종 검색 결과: {len(filtered_results)}개")
        
        # 호환성을 위해 필드 보정 처리
        for result in filtered_results:
            # 1. 문서 타입 일관성 확보
            if "doc_type" not in result:
                # 티켓인 경우
                if result.get("type") == "ticket" or result.get("source_type") == "ticket":
                    result["doc_type"] = "ticket"
                # 기본값은 원본 type 값 사용
                elif "type" in result:
                    result["doc_type"] = str(result["type"])
                    
            # 2. 아티클 문서의 경우 source_type 일관성 확보
            if result.get("doc_type") == "article":
                # source_type 표준화
                if "source_type" not in result:
                    result["source_type"] = "article"
            
            # 3. 티켓의 경우 source_type 일관성 확보
            if result.get("doc_type") == "ticket":
                if "source_type" not in result:
                    result["source_type"] = "ticket"
                    
            # 4. id 필드 일관성 확보
            if "original_id" in result and "id" not in result:
                result["id"] = result["original_id"]
            
        # 검색 결과를 retriever.py에서 기대하는 형식으로 변환
        # 이전에는 "results"에만 저장했으나, 결과를 "documents", "metadatas", "ids", "distances" 형식으로도 추가
        documents = []
        metadatas = []
        ids = []
        distances = []
        
        for result in filtered_results:
            # 문서 텍스트 (내용)
            if "content" in result:
                documents.append(result["content"])
            elif "text" in result:
                documents.append(result["text"])
            else:
                # 적절한 텍스트 필드가 없으면 빈 문자열 사용
                documents.append("")
                
            # 메타데이터 (전체 결과)
            metadatas.append(result)
            
            # ID
            if "id" in result:
                ids.append(result["id"])
            elif "original_id" in result:
                ids.append(result["original_id"])
            else:
                ids.append(str(uuid.uuid4()))  # 임의 ID 생성
                
            # 🔧 FIX: 유사도 점수 계산 수정 (COSINE 유사도는 그대로 사용)
            if "score" in result:
                # Qdrant COSINE 유사도는 1에 가까울수록 유사함 (그대로 사용)
                distances.append(result["score"])  # 기존: 1.0 - result["score"] (잘못된 계산)
            else:
                distances.append(0.0)  # 기본값
        
        # 검색 결과 반환 (원래 형식 + 호환성을 위한 추가 필드)
        return {
            "results": filtered_results,  # 기존 형식 (main.py에서 사용)
            "documents": documents,       # 호환성 형식 (retriever.py에서 사용)
            "metadatas": metadatas,       # 호환성 형식
            "ids": ids,                   # 호환성 형식
            "distances": distances,       # 호환성 형식
            "total": len(filtered_results),
            "filtered_by_doc_type": doc_type is not None,  # Qdrant 쿼리 필터링 사용
            "skipped_count": 0  # Qdrant 쿼리 필터링으로 메모리 스킵 없음
        }

    def count(self, tenant_id: Optional[str] = None, platform: Optional[str] = None) -> int:
        """
        문서 수 반환 (멀티플랫폼/멀티테넌트 지원)
        
        Args:
            tenant_id: 특정 회사의 문서만 카운트할 경우 테넌트 ID
            platform: 특정 플랫폼의 문서만 카운트할 경우 플랫폼 이름
            
        Returns:
            문서 수
        """
        try:
            # 필터 조건 구성
            filter_conditions = []
            if tenant_id:
                filter_conditions.append(
                    FieldCondition(key="tenant_id", match=MatchValue(value=tenant_id))
                )
            if platform:
                filter_conditions.append(
                    FieldCondition(key="platform", match=MatchValue(value=platform))
                )
            
            if filter_conditions:
                # 특정 조건의 문서 수 카운트
                try:
                    filter_obj = Filter(must=filter_conditions)
                    
                    # Qdrant 버전 호환성을 위해 여러 방법 시도
                    try:
                        # 방법 1: count_filter 파라미터 사용 (최신 버전)
                        count = self.client.count(
                            collection_name=self.collection_name,
                            count_filter=filter_obj
                        )
                        return count.count
                    except (TypeError, AttributeError) as e1:
                        logger.debug(f"count_filter 파라미터 사용 실패: {e1}")
                        try:
                            # 방법 2: filter 파라미터 사용 (이전 버전)
                            count = self.client.count(
                                collection_name=self.collection_name,
                                filter=filter_obj
                            )
                            return count.count
                        except (TypeError, AttributeError) as e2:
                            logger.debug(f"filter 파라미터 사용 실패: {e2}")
                            # 방법 3: 파라미터 없이 사용 후 별도 필터링
                            raise Exception("count 메서드에서 필터 파라미터를 지원하지 않습니다.")
                            
                except Exception as inner_e:
                    logger.warning(f"필터를 사용한 카운트 실패: {inner_e}, scroll API를 사용한 대체 방법 시도 중...")
                    
                    # 대체 방법: scroll API를 사용하여 모든 문서를 가져온 후 메모리에서 필터링
                    count = 0
                    offset = None
                    batch_size = 1000
                    total_scanned = 0
                    
                    while True:
                        # 배치로 문서 가져오기
                        batch, next_offset = self.client.scroll(
                            collection_name=self.collection_name,
                            limit=batch_size,
                            offset=offset,
                            with_payload=True,
                            with_vectors=False
                        )
                        
                        if not batch:
                            break
                            
                        # 조건에 맞는 문서 필터링하여 카운트
                        for point in batch:
                            payload = point.payload
                            matches = True
                            
                            # tenant_id 필터링
                            if tenant_id and payload.get("tenant_id") != tenant_id:
                                matches = False
                            
                            # platform 필터링
                            if platform and payload.get("platform") != platform:
                                matches = False
                            
                            if matches:
                                count += 1
                        
                        total_scanned += len(batch)
                        
                        # 다음 오프셋 설정
                        offset = next_offset
                        if offset is None:
                            break
                    
                    filter_desc = []
                    if tenant_id:
                        filter_desc.append(f"tenant_id='{tenant_id}'")
                    if platform:
                        filter_desc.append(f"platform='{platform}'")
                    
                    logger.info(f"{total_scanned}개 문서 중 {count}개가 필터 조건({', '.join(filter_desc)})과 일치합니다.")
                    return count
            else:
                # 전체 문서 수 카운트
                count = self.client.count(collection_name=self.collection_name)
                return count.count
        except Exception as e:
            logger.error(f"문서 수 카운트 실패: {e}")
            return 0

    def get_by_id(self, original_id_value: str, doc_type: Optional[str] = None, tenant_id: Optional[str] = None, platform: Optional[str] = None) -> Dict[str, Any]:
        """
        원본 ID로 단일 문서 조회 (멀티플랫폼/멀티테넌트 지원)

        Args:
            original_id_value: 조회할 문서의 원본 ID (Freshdesk 원본 숫자 ID의 문자열 형태, 예: "12345")
            doc_type: 문서 타입 필터 ("ticket" 또는 "article", None이거나 빈 문자열이면 예외 발생)
            tenant_id: 테넌트 ID 필터 (선택 사항, None이면 "default" 사용)
            platform: 플랫폼 필터 (선택 사항, "freshdesk", "zendesk" 등)

        Returns:
            조회된 문서 정보 (메타데이터와 임베딩 포함)

        Raises:
            ValueError: doc_type이 None 또는 빈 문자열인 경우
        """
        # doc_type이 반드시 명시되어야 함을 강제
        if not doc_type or not str(doc_type).strip():
            logger.error("get_by_id 호출 시 doc_type이 반드시 명시되어야 합니다. (ticket 또는 article)")
            raise ValueError("get_by_id 호출 시 doc_type 파라미터는 필수입니다. (예: doc_type='ticket' 또는 doc_type='article')")
        try:
            # tenant_id가 None이면 "default"로 설정
            search_tenant_id = tenant_id if tenant_id else "default"
            logger.info(f"문서 조회 시작 (original_id: {original_id_value}, doc_type: {doc_type}, tenant_id: {search_tenant_id}, platform: {platform})")
            
            # 필터 조건: tenant_id, original_id, doc_type 필수, platform 선택사항
            filter_conditions = [
                FieldCondition(
                    key="tenant_id",
                    match=MatchValue(value=search_tenant_id)
                ),
                FieldCondition(
                    key="original_id",
                    match=MatchValue(value=str(original_id_value))
                ),
                FieldCondition(
                    key="doc_type",
                    match=MatchValue(value=doc_type)
                )
            ]
            
            # platform 필터 추가 (멀티플랫폼 지원)
            if platform:
                filter_conditions.append(
                    FieldCondition(
                        key="platform",
                        match=MatchValue(value=platform)
                    )
                )
            
            filter_log_str = ", ".join([f"{c.key}='{c.match.value}'" for c in filter_conditions])
            logger.info(f"원본 ID '{original_id_value}'로 문서 검색 시도 (필터 조건: {filter_log_str})")
            
            # Qdrant에서 검색
            scroll_result = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=Filter(must=filter_conditions),
                limit=1,
                with_payload=True,
                with_vectors=True
            )
            if scroll_result and scroll_result[0]:
                point = scroll_result[0][0]
                payload = point.payload if hasattr(point, 'payload') else {}
                logger.info(f"검색 결과 - ID: {point.id}, original_id='{payload.get('original_id')}', doc_type='{payload.get('doc_type')}', type='{payload.get('tenant_id')}'")
                document_type = payload.get("doc_type", "") or payload.get("type", "")
                return {
                    "id": payload.get("original_id", ""),
                    "doc_type": document_type,
                    "metadata": payload,
                    "embedding": point.vector if hasattr(point, 'vector') else None
                }
            else:
                logger.warning(f"원본 ID '{original_id_value}', 타입 '{doc_type}', tenant_id '{search_tenant_id}'으로 문서를 찾을 수 없습니다.")
                logger.warning(f"적용된 필터 조건 (문자열): {filter_log_str}")
                return {}
        except Exception as e:
            logger.error(f"ID '{original_id_value}'로 문서 조회 중 오류 발생: {e}")
            return {}

    def get_collection_info(self) -> Dict[str, Any]:
        """
        컬렉션 정보 조회

        Returns:
            컬렉션 상태 정보
        """
        try:
            collection_info = self.client.get_collection(collection_name=self.collection_name)
            
            # CollectionInfo 객체의 실제 구조에 맞게 접근
            return {
                "name": self.collection_name,  # 컬렉션명 직접 사용
                "status": getattr(collection_info, 'status', 'unknown'),
                "vector_size": getattr(collection_info.config.params.vectors, 'size', VECTOR_SIZE),
                "points_count": getattr(collection_info, 'points_count', getattr(collection_info, 'vectors_count', 0))
            }
        except Exception as e:
            logger.error(f"컬렉션 정보 조회 중 오류 발생: {e}")
            return {"error": str(e)}

    def list_collections(self):
        """
        Qdrant의 모든 컬렉션 목록을 반환합니다.
        
        Returns:
            컬렉션 정보 객체들의 리스트
        """
        try:
            collections_response = self.client.get_collections()
            return collections_response.collections
        except Exception as e:
            logger.error(f"컬렉션 목록 조회 중 오류 발생: {e}")
            return []

    def collection_exists(self) -> bool:
        """
        컬렉션 존재 여부 확인
        
        Returns:
            bool: 컬렉션 존재 여부
        """
        try:
            self.client.get_collection(collection_name=self.collection_name)
            return True
        except Exception as e:
            logger.debug(f"컬렉션 존재 확인 중 오류 (정상적일 수 있음): {e}")
            return False

    def drop_collection(self, collection_name: Optional[str] = None) -> bool:
        """
        지정한 Qdrant 컬렉션을 완전히 삭제(drop)합니다.
        Args:
            collection_name: 삭제할 컬렉션 이름 (None이면 기본 컬렉션)
        Returns:
            성공 여부 (bool)
        """
        name = collection_name or self.collection_name
        try:
            self.client.delete_collection(collection_name=name)
            logger.info(f"Qdrant 컬렉션 삭제 완료: {name}")
            return True
        except Exception as e:
            logger.error(f"Qdrant 컬렉션 삭제 실패: {name}, 오류: {e}")
            return False

    def list_all_ids(self) -> List[str]:
        """
        Qdrant 컬렉션의 모든 original_id(또는 id) 목록 반환
        Returns:
            original_id(문서 원본 ID) 리스트
        """
        try:
            # Qdrant points 전체 조회 (batch로 나눠서 처리)
            all_ids = []
            offset = 0
            limit = 1000
            while True:
                points = self.client.scroll(
                    collection_name=self.collection_name,
                    offset=offset,
                    limit=limit,
                    with_payload=True,
                    with_vectors=False
                )
                if not points or len(points) == 0:
                    break
                for p in points:
                    # original_id가 있으면 사용, 없으면 id 사용
                    oid = p.payload.get("original_id") if p.payload else None
                    all_ids.append(oid or p.id)
                if len(points) < limit:
                    break
                offset += limit
            return all_ids
        except Exception as e:
            logger.error(f"Qdrant 전체 ID 목록 조회 실패: {e}")
            return []
            
    def backup_collection(self, collection_name: str = None, backup_path: str = None) -> bool:
        """
        Qdrant 컬렉션 데이터를 JSON 파일로 백업합니다.
        
        Args:
            collection_name: 백업할 컬렉션 이름 (None이면 기본 컬렉션)
            backup_path: 백업 파일 경로 (None이면 자동 생성)
            
        Returns:
            성공 여부 (bool)
        """
        import json
        import os
        from datetime import datetime
        
        name = collection_name or self.collection_name
        
        # 백업 파일 경로 설정
        if backup_path is None:
            backup_dir = os.path.join(os.getcwd(), "backups")
            os.makedirs(backup_dir, exist_ok=True)
            backup_path = os.path.join(backup_dir, f"{name}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        
        try:
            # 컬렉션 정보 조회
            collection_info = self.client.get_collection(collection_name=name)
            points_count = getattr(collection_info, 'points_count', getattr(collection_info, 'vectors_count', 0))
            
            if points_count == 0:
                logger.info(f"컬렉션 '{name}'에 백업할 데이터가 없습니다.")
                return True
                
            # 컬렉션 데이터 조회 (청크 단위로 처리)
            logger.info(f"컬렉션 '{name}' 백업 시작: 총 {points_count:,}개 포인트")
            backup_data = []
            offset = 0
            limit = 1000
            
            while True:
                points = self.client.scroll(
                    collection_name=name,
                    offset=offset,
                    limit=limit,
                    with_payload=True,
                    with_vectors=True  # 벡터 데이터 포함
                )
                
                if not points or len(points) == 0:
                    break
                    
                # 각 포인트를 직렬화 가능한 형태로 변환
                for point in points:
                    point_data = {
                        "id": point.id,
                        "payload": point.payload
                    }
                    
                    # 벡터 데이터가 있으면 추가
                    if hasattr(point, 'vector') and point.vector:
                        point_data["vector"] = point.vector
                    
                    backup_data.append(point_data)
                
                logger.info(f"컬렉션 '{name}' 백업 진행 중: {len(backup_data):,}/{points_count:,}개 포인트")
                
                if len(points) < limit:
                    break
                    
                offset += len(points)
            
            # JSON 파일로 저장
            with open(backup_path, 'w', encoding='utf-8') as f:
                json.dump(backup_data, f, ensure_ascii=False)
                
            logger.info(f"컬렉션 '{name}' 백업 완료: {len(backup_data):,}개 포인트, 파일: {backup_path}")
            return True
            
        except Exception as e:
            logger.error(f"컬렉션 '{name}' 백업 실패: {e}")
            return False
            
    def reset_collection(self, collection_name: str = None, confirm: bool = False, create_backup: bool = True, backup_path: str = None) -> bool:
        """
        벡터DB 컬렉션을 초기화합니다 (삭제 후 재생성)
        
        Args:
            collection_name: 초기화할 컬렉션 이름 (None이면 기본 컬렉션)
            confirm: 초기화 확인 여부 (False면 예외 발생)
            create_backup: 초기화 전 백업 생성 여부
            backup_path: 백업 파일 경로 (None이면 자동 생성)
            
        Returns:
            성공 여부 (bool)
            
        Raises:
            ValueError: confirm이 False인 경우
        """
        name = collection_name or self.collection_name
        
        if not confirm:
            raise ValueError("초기화 확인이 필요합니다. confirm=True로 설정하세요.")
        
        # 백업 생성
        if create_backup:
            logger.info(f"컬렉션 '{name}' 초기화 전 백업을 시작합니다.")
            if not self.backup_collection(name, backup_path):
                logger.error(f"컬렉션 '{name}' 백업 실패로 초기화를 중단합니다.")
                return False
        
        # 컬렉션 삭제
        if not self.drop_collection(name):
            logger.error(f"컬렉션 '{name}' 삭제 실패로 초기화를 중단합니다.")
            return False
        
        # 컬렉션 재생성
        try:
            if name == self.collection_name:
                self._ensure_collection_exists()
            else:
                logger.warning(f"알 수 없는 컬렉션 '{name}'은 자동 재생성되지 않습니다.")
                return False
            
            logger.info(f"컬렉션 '{name}' 초기화 완료 (삭제 후 재생성)")
            return True
        except Exception as e:
            logger.error(f"컬렉션 '{name}' 재생성 실패: {e}")
            return False


# 벡터 데이터베이스 팩토리
class VectorDBFactory:
    """벡터 데이터베이스 팩토리 클래스"""
    
    @staticmethod
    def get_vector_db(db_type: str = "qdrant", collection_name: str = COLLECTION_NAME) -> VectorDBInterface:
        """
        지정된 타입의 벡터 DB 인스턴스 반환
        
        Args:
            db_type: 벡터 DB 타입 ("qdrant")
            collection_name: 컬렉션 이름
            
        Returns:
            VectorDBInterface 인스턴스
        """
        if db_type.lower() == "qdrant":
            return QdrantAdapter(collection_name)
        else:
            raise ValueError(f"지원되지 않는 벡터 DB 타입: {db_type}")


# 싱글톤 벡터 DB 인스턴스
vector_db = VectorDBFactory.get_vector_db()

# 로깅 설정
logger = logging.getLogger(__name__)

# 참고: `freshdesk_client` 관련 함수들은 freshdesk/optimized_fetcher.py 파일에 위치해야 합니다.
# 이 파일은 벡터 데이터베이스 관련 기능만 포함합니다.

def migrate_type_to_doc_type():
    """
    기존 'type' 필드를 사용하는 문서들을 'doc_type' 필드로 마이그레이션하는 유틸리티 함수
    또한 doc_type과 source_type 필드의 일관성을 확보합니다.
    
    이 함수는 관리자가 필요한 경우 직접 호출하여 기존 데이터를 마이그레이션할 수 있습니다.
    """
    try:
        logger.info("기존 'type' 필드를 사용하는 데이터를 'doc_type' 필드로 마이그레이션 시작")
        logger.info("또한 doc_type과 source_type 필드의 일관성을 확보합니다")
        
        # 기존 벡터 DB 인스턴스 사용
        db = vector_db
        
        # 전체 컬렉션을 배치 단위로 스캔
        offset = 0
        batch_size = 100
        migrated_count = 0
        source_type_fixed = 0
        total_processed = 0
        
        while True:
            # 배치 조회
            scroll_result = db.client.scroll(
                collection_name=db.collection_name,
                offset=offset,
                limit=batch_size,
                with_payload=True,
                with_vectors=False
            )
            
            points = scroll_result[0]
            if not points:
                break  # 더 이상 문서가 없음
            
            total_processed += len(points)
            
            # 마이그레이션이 필요한 문서 필터링
            points_to_update = []
            
            for point in points:
                payload = point.payload
                update_needed = False
                updated_payload = dict(payload)
                
                # 1. type -> doc_type 마이그레이션
                if "type" in payload and ("doc_type" not in payload or not payload["doc_type"]):
                    doc_type_value = payload["type"]
                    
                    # doc_type 값이 유효한지 확인
                    if doc_type_value in ["ticket", "article"]:
                        # 원본 페이로드에 'doc_type' 필드 추가
                        updated_payload["doc_type"] = doc_type_value
                        update_needed = True
                
                # 2. source_type 일관성 확보
                current_doc_type = updated_payload.get("doc_type") or payload.get("type")
                
                if current_doc_type == "article" and "source_type" not in updated_payload:
                    # 아티클 문서에 source_type 추가
                    updated_payload["source_type"] = "article"  # 아티클 문서의 표준 source_type
                    update_needed = True
                    source_type_fixed += 1
                
                elif current_doc_type == "ticket" and "source_type" not in updated_payload:
                    # 티켓 문서에 source_type 추가
                    updated_payload["source_type"] = "ticket"
                    update_needed = True
                    source_type_fixed += 1
                
                # 3. id 일관성 확보
                if "original_id" in updated_payload and "id" not in updated_payload:
                    updated_payload["id"] = updated_payload["original_id"]
                    update_needed = True
                
                # 변경이 필요한 경우 포인트 추가
                if update_needed:
                    points_to_update.append(
                        PointStruct(
                            id=point.id,
                            payload=updated_payload,
                            vector=None  # 벡터는 업데이트하지 않음
                        )
                    )
            
            # 마이그레이션할 문서가 있으면 업데이트
            if points_to_update:
                db.client.upsert(
                    collection_name=db.collection_name,
                    points=points_to_update,
                    wait=True
                )
                migrated_count += len(points_to_update)
                logger.info(f"마이그레이션 진행: {len(points_to_update)}개 문서 업데이트 완료")
            
            # 다음 배치
            offset += batch_size
        
        logger.info(f"마이그레이션 완료: 총 {total_processed}개 중 {migrated_count}개 문서 마이그레이션됨")
        logger.info(f"source_type 필드 고정된 문서: {source_type_fixed}개")
        return {
            "total_processed": total_processed,
            "migrated_count": migrated_count,
            "source_type_fixed": source_type_fixed
        }
    except Exception as e:
        logger.error(f"마이그레이션 중 오류 발생: {e}")
        return {
            "error": str(e)
        }


# =================================================================
# 🚀 Vector DB 단독 모드 헬퍼 함수들 (processor.py에서 이동)
# =================================================================

async def purge_vector_db_data(tenant_id: str, platform: str) -> None:
    """
    Vector DB에서 특정 테넌트의 모든 데이터를 삭제합니다.
    
    Args:
        tenant_id: 테넌트 ID
        platform: 플랫폼 식별자
    """
    try:
        # 메타데이터 필터로 해당 테넌트의 모든 문서 삭제
        filter_conditions = {
            "must": [
                {"key": "tenant_id", "match": {"value": tenant_id}},
                {"key": "platform", "match": {"value": platform}}
            ]
        }
        
        # Vector DB에서 삭제
        vector_db.delete_by_filter(filter_conditions)
        logger.info(f"Vector DB 데이터 삭제 완료: {tenant_id}/{platform}")
        
    except Exception as e:
        logger.error(f"Vector DB 데이터 삭제 중 오류: {e}")
        raise

async def process_ticket_to_vector_db(
    ticket: Dict[str, Any], 
    tenant_id: str, 
    platform: str
) -> bool:
    """
    개별 티켓을 처리하여 Vector DB에 저장합니다.
    
    Args:
        ticket: 티켓 데이터
        tenant_id: 테넌트 ID  
        platform: 플랫폼 식별자
        
    Returns:
        bool: 처리 성공 여부
    """
    try:
        # LLM Manager import
        from core.llm.manager import LLMManager
        from core.search.embeddings import embed_documents
        from core.utils.image_metadata_extractor import extract_ticket_image_metadata, validate_image_metadata
        
        llm_manager = LLMManager()
        
        ticket_id = str(ticket.get('id', ''))
        subject = ticket.get('subject', '')
        
        # 디버깅: 티켓 처리 시작
        logger.info(f"🎫 티켓 처리 시작: ID={ticket_id}, 제목={subject[:50]}...")
        description = ticket.get('description_text', '') or ticket.get('description', '')
        
        # 대화 데이터 통합
        conversations = ticket.get('conversations', [])
        conversation_texts = []
        for conv in conversations:
            body = conv.get('body_text', '') or conv.get('body', '')
            if body and body.strip():
                conversation_texts.append(body.strip())
        
        # 전체 텍스트 조합 (임베딩 대상)
        full_text_parts = []
        if subject and subject.strip():
            full_text_parts.append(f"제목: {subject.strip()}")
        if description and description.strip():
            full_text_parts.append(f"설명: {description.strip()}")
        if conversation_texts:
            full_text_parts.append(f"대화: {' '.join(conversation_texts)}")
        
        full_text = ' '.join(full_text_parts)
        
        if not full_text.strip():
            logger.warning(f"티켓 {ticket_id}: 임베딩할 텍스트가 없음")
            return False
        
        # 🚀 Vector DB 단독 모드: 원본 텍스트 직접 사용 (LLM 요약 없음)
        content_for_vector = full_text  # 원본 텍스트를 그대로 사용
        
        # 🖼️ 이미지 메타데이터 추출
        image_metadata = extract_ticket_image_metadata(ticket)
        
        # 이미지 메타데이터 유효성 검증
        if not validate_image_metadata(image_metadata):
            logger.warning(f"티켓 {ticket_id}: 이미지 메타데이터 유효성 검증 실패")
            # 기본값으로 설정 (최적화된 구조)
            image_metadata = {
                "has_attachments": False,
                "has_inline_images": False,
                "attachment_count": 0,
                "attachments": []
            }
        
        # Vector DB용 메타데이터 구성 (풍부한 정보 포함)
        vector_metadata = {
            # 필수 식별 정보
            "tenant_id": tenant_id,
            "platform": platform,
            "original_id": ticket_id,
            "doc_type": "ticket",
            "object_type": "ticket",
            
            # 검색 최적화 필드 (루트 레벨)
            "subject": subject,
            "status": ticket.get('status', 2),
            "priority": ticket.get('priority', 1),
            "has_attachments": bool(ticket.get('all_attachments', []) or ticket.get('attachments', [])),
            "conversation_count": len(conversations),
            "created_at": ticket.get('created_at', ''),
            "updated_at": ticket.get('updated_at', ''),
            
            # 사용자/조직 정보
            "requester_id": ticket.get('requester_id'),
            "responder_id": ticket.get('responder_id'),
            "group_id": ticket.get('group_id'),
            "company_id": ticket.get('company_id'),
            
            # 첨부파일 정보 (상세)
            "attachments": ticket.get('all_attachments', []) or ticket.get('attachments', []),
            
            # 🖼️ 최적화된 이미지/첨부파일 정보
            "has_attachments": image_metadata.get("has_attachments", False),
            "has_inline_images": image_metadata.get("has_inline_images", False),
            "attachment_count": image_metadata.get("attachment_count", 0),
            "attachments": image_metadata.get("attachments", []),
            
            # 티켓 속성
            "type": ticket.get('type'),
            "source": ticket.get('source'),
            "fr_escalated": ticket.get('fr_escalated'),
            "spam": ticket.get('spam'),
            "is_escalated": ticket.get('is_escalated'),
            "due_by": ticket.get('due_by'),
            "fr_due_by": ticket.get('fr_due_by'),
            "product_id": ticket.get('product_id'),
            "custom_fields": ticket.get('custom_fields', {}),
            "tags": ticket.get('tags', []),
            
            # 타임스탬프 관련
            "resolved_at": ticket.get('resolved_at'),
            "closed_at": ticket.get('closed_at'),
            "first_responded_at": ticket.get('first_responded_at'),
            
            # 추가 시스템 정보
            "association_type": ticket.get('association_type'),
            "associated_tickets_count": ticket.get('associated_tickets_count'),
            "nr_escalated": ticket.get('nr_escalated'),
            "escalated_at": ticket.get('escalated_at'),
            
            # Vector DB 전용 메타데이터 (최소화됨)
        }
        
        # None 값 제거
        vector_metadata = {k: v for k, v in vector_metadata.items() 
                          if v is not None and v != "" and v != []}
        
        # 임베딩 생성 (원본 텍스트 사용)
        embeddings = embed_documents([content_for_vector])
        if not embeddings or len(embeddings) != 1:
            logger.error(f"티켓 {ticket_id}: 임베딩 생성 실패")
            return False
        
        # Vector DB에 저장 (원본 텍스트 사용)
        vector_id = f"{tenant_id}_{platform}_{ticket_id}"
        logger.info(f"🔍 벡터 DB 저장 시도: vector_id={vector_id}")
        vector_db.add_documents(
            texts=[content_for_vector],  # 원본 텍스트 저장
            embeddings=embeddings,
            metadatas=[vector_metadata],
            ids=[vector_id]
        )
        logger.info(f"✅ 벡터 DB 저장 완료: vector_id={vector_id}")
        
        # 저장 후 총 문서 수 확인
        total_count = vector_db.count(tenant_id=tenant_id, platform=platform)
        logger.info(f"📊 현재 총 문서 수: {total_count}개")
        
        logger.debug(f"티켓 {ticket_id} Vector DB 저장 완료")
        return True
        
    except Exception as e:
        logger.error(f"티켓 {ticket.get('id', 'unknown')} 처리 중 오류: {e}")
        return False

async def process_article_to_vector_db(
    article: Dict[str, Any], 
    tenant_id: str, 
    platform: str
) -> bool:
    """
    개별 KB 문서를 처리하여 Vector DB에 저장합니다.
    
    Args:
        article: KB 문서 데이터
        tenant_id: 테넌트 ID
        platform: 플랫폼 식별자
        
    Returns:
        bool: 처리 성공 여부
    """
    try:
        # LLM Manager import
        from core.llm.manager import LLMManager
        from core.search.embeddings import embed_documents
        from core.utils.image_metadata_extractor import extract_article_image_metadata, validate_image_metadata
        
        llm_manager = LLMManager()
        
        article_id = str(article.get('id', ''))
        title = article.get('title', '')
        description_text = article.get('description_text', '') or article.get('description', '')
        
        # 핵심 텍스트만 임베딩 대상으로 사용: title + description_text
        full_text_parts = []
        if title and title.strip():
            full_text_parts.append(f"제목: {title.strip()}")
        if description_text and description_text.strip():
            full_text_parts.append(f"내용: {description_text.strip()}")
        
        full_text = ' '.join(full_text_parts)
        
        if not full_text.strip():
            logger.warning(f"KB 문서 {article_id}: 임베딩할 텍스트가 없음")
            return False
        
        # KB 문서는 원본 텍스트를 그대로 사용 (요약하지 않음)
        display_content = full_text
        
        # 🖼️ 이미지 메타데이터 추출
        image_metadata = extract_article_image_metadata(article)
        
        # 이미지 메타데이터 유효성 검증
        if not validate_image_metadata(image_metadata):
            logger.warning(f"KB 문서 {article_id}: 이미지 메타데이터 유효성 검증 실패")
            # 기본값으로 설정 (최적화된 구조)
            image_metadata = {
                "has_attachments": False,
                "has_inline_images": False,
                "attachment_count": 0,
                "attachments": []
            }
        
        # Vector DB용 메타데이터 구성 (KB 문서의 모든 정보 포함)
        vector_metadata = {
            # 필수 식별 정보
            "tenant_id": tenant_id,
            "platform": platform,
            "original_id": article_id,
            "doc_type": "article",
            "object_type": "article",
            
            # 검색 최적화 필드 (루트 레벨)
            "title": title,
            "status": article.get('status', 2),
            "has_attachments": bool(article.get('all_attachments', []) or article.get('attachments', [])),
            "created_at": article.get('created_at', ''),
            "updated_at": article.get('updated_at', ''),
            
            
            # 분류 및 조직 정보
            "category": article.get('category', {}),
            "category_id": article.get('category_id'),
            "folder": article.get('folder', {}),
            "folder_id": article.get('folder_id'),
            "section_id": article.get('section_id'),
            
            # 작성자 및 관리 정보
            "agent_id": article.get('agent_id'),
            "author_id": article.get('author_id'),
            "reviewer_id": article.get('reviewer_id'),
            
            # 태그 및 레이블
            "tags": article.get('tags', []),
            "labels": article.get('labels', []),
            
            # 설정 및 권한
            "approval_status": article.get('approval_status'),
            "review_date": article.get('review_date'),
            "seo_data": article.get('seo_data', {}),
            
            # 사용 통계
            "hits": article.get('hits', 0),
            "thumbs_up": article.get('thumbs_up', 0),
            "thumbs_down": article.get('thumbs_down', 0),
            
            # 첨부파일 정보
            "attachments": article.get('all_attachments', []) or article.get('attachments', []),
            
            # 🖼️ 최적화된 이미지/첨부파일 정보
            "has_attachments": image_metadata.get("has_attachments", False),
            "has_inline_images": image_metadata.get("has_inline_images", False),
            "attachment_count": image_metadata.get("attachment_count", 0),
            "attachments": image_metadata.get("attachments", []),
            
            # 다국어 지원
            "language": article.get('language', 'ko'),
            "translated_articles": article.get('translated_articles', []),
            
            # 커스텀 필드
            "custom_fields": article.get('custom_fields', {}),
            
            # 발행 관련
            "published": article.get('published', True),
            "publish_date": article.get('publish_date'),
            "scheduled_date": article.get('scheduled_date'),
            
            # Vector DB 전용 메타데이터 (최소화됨)
        }
        
        # None 값 제거
        vector_metadata = {k: v for k, v in vector_metadata.items() 
                          if v is not None and v != "" and v != []}
        
        # 임베딩 생성 (원본 텍스트 사용)
        embeddings = embed_documents([display_content])
        if not embeddings or len(embeddings) != 1:
            logger.error(f"KB 문서 {article_id}: 임베딩 생성 실패")
            return False
        
        # Vector DB에 저장 (원본 텍스트로)
        vector_id = f"{tenant_id}_{platform}_{article_id}"
        vector_db.add_documents(
            texts=[display_content],  # 원본 텍스트 저장
            embeddings=embeddings,
            metadatas=[vector_metadata],
            ids=[vector_id]
        )
        
        logger.debug(f"KB 문서 {article_id} Vector DB 저장 완료")
        return True
        
    except Exception as e:
        logger.error(f"KB 문서 {article.get('id', 'unknown')} 처리 중 오류: {e}")
        return False

async def generate_realtime_summary(
    content: str, 
    content_type: str, 
    metadata: Dict[str, Any]
) -> str:
    """
    실시간 요약을 생성합니다.
    Vector DB 단독 모드에서는 원본 텍스트를 그대로 반환합니다.
    
    Args:
        content: 요약할 내용
        content_type: 콘텐츠 타입 ("ticket" 또는 "knowledge_base")
        metadata: 메타데이터
        
    Returns:
        str: 생성된 요약 또는 원본 텍스트
    """
    try:
        import os
        
        # Vector DB 단독 모드인 경우 원본 텍스트 반환
        enable_full_streaming = os.getenv('ENABLE_FULL_STREAMING_MODE', 'false').lower() == 'true'
        if enable_full_streaming:
            logger.debug(f"Vector DB 단독 모드: 원본 텍스트 반환 (content_type: {content_type})")
            return content  # 원본 텍스트 그대로 반환
        
        # 하이브리드 모드인 경우 기존 요약 로직 실행
        from core.llm.manager import LLMManager
        llm_manager = LLMManager()
        
        if content_type == "ticket":
            # 티켓 요약 생성
            ticket_data = {
                'id': metadata.get('id', ''),
                'subject': metadata.get('subject', ''),
                'integrated_text': content,
                'status': metadata.get('status', ''),
                'priority': metadata.get('priority', ''),
                'created_at': metadata.get('created_at', '')
            }
            summary_result = await llm_manager.generate_ticket_summary(ticket_data)
            return summary_result.get('summary', '요약 생성에 실패했습니다.') if summary_result else '요약 생성에 실패했습니다.'
            
        elif content_type == "knowledge_base":
            # KB 문서 요약 생성
            kb_data = {
                'id': metadata.get('id', ''),
                'title': metadata.get('title', ''),
                'content': content,
                'category': metadata.get('category', ''),
                'created_at': metadata.get('created_at', '')
            }
            summary_result = await llm_manager.generate_knowledge_base_summary(kb_data)
            return summary_result.get('summary', '요약 생성에 실패했습니다.') if summary_result else '요약 생성에 실패했습니다.'
            
        else:
            logger.warning(f"알 수 없는 content_type: {content_type}")
            return "지원하지 않는 콘텐츠 타입입니다."
        
    except Exception as e:
        logger.error(f"실시간 요약 생성 중 오류: {e}")
        return f"요약 생성 중 오류가 발생했습니다: {str(e)}"

async def search_vector_db_only(
    query: str,
    tenant_id: str,
    platform: str = "freshdesk", 
    doc_types: Optional[List[str]] = None,
    limit: int = 10,
    score_threshold: float = 0.7,
    exclude_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Vector DB에서만 검색을 수행합니다 (SQL 없음).
    
    Args:
        query: 검색 쿼리
        tenant_id: 테넌트 ID
        platform: 플랫폼 식별자
        doc_types: 문서 타입 필터 (["ticket", "article"] 등)
        limit: 최대 결과 수
        score_threshold: 최소 유사도 점수
        exclude_id: 제외할 문서 ID (자기 자신 제외용)
        
    Returns:
        List[Dict[str, Any]]: 검색 결과
    """
    try:
        from core.search.embeddings import embed_documents
        
        exclude_msg = f", 제외 ID: {exclude_id}" if exclude_id else ""
        logger.info(f"Vector DB 검색 시작 - 쿼리: '{query[:100]}...', 테넌트: {tenant_id}, 문서타입: {doc_types}, 제한: {limit}{exclude_msg}")
        
        # 검색 쿼리 임베딩 생성
        query_embeddings = embed_documents([query])
        if not query_embeddings or len(query_embeddings) != 1:
            logger.error("검색 쿼리 임베딩 생성 실패")
            return []
        
        query_embedding = query_embeddings[0]
        
        # 메타데이터 필터 구성
        filter_conditions = {
            "must": [
                {"key": "tenant_id", "match": {"value": tenant_id}},
                {"key": "platform", "match": {"value": platform}}
            ]
        }
        
        # 제외할 ID가 있으면 must_not 조건 추가 (자기 자신 제외)
        if exclude_id:
            filter_conditions["must_not"] = [
                {"key": "original_id", "match": {"value": str(exclude_id)}}
            ]
            logger.debug(f"🚫 제외 ID 설정: {exclude_id} (벡터 검색에서 자동 제외)")
        
        # 문서 타입 필터 추가
        if doc_types:
            if len(doc_types) == 1:
                filter_conditions["must"].append({
                    "key": "doc_type", 
                    "match": {"value": doc_types[0]}
                })
            else:
                filter_conditions["should"] = [
                    {"key": "doc_type", "match": {"value": doc_type}}
                    for doc_type in doc_types
                ]
        
        # Vector DB 검색 최적화 (단일 호출로 처리)
        all_results = []
        
        if not doc_types or len(doc_types) == 1:
            # 단일 검색으로 처리 (성능 최적화)
            doc_type_filter = doc_types[0] if doc_types else None
            search_response = vector_db.search(
                query_embedding=query_embedding,
                top_k=limit,
                tenant_id=tenant_id,
                platform=platform,
                doc_type=doc_type_filter
            )
            all_results = search_response.get("results", []) if isinstance(search_response, dict) else search_response
        else:
            # 다중 doc_type의 경우만 분할 검색 (메모리 효율성을 위해 limit 조정)
            results_per_type = max(1, limit // len(doc_types) + 1)  # 타입당 검색 수 최적화
            
            for doc_type in doc_types:
                search_response = vector_db.search(
                    query_embedding=query_embedding,
                    top_k=results_per_type,  # 타입별 제한으로 전체 성능 향상
                    tenant_id=tenant_id,
                    platform=platform,
                    doc_type=doc_type
                )
                doc_results = search_response.get("results", []) if isinstance(search_response, dict) else search_response
                all_results.extend(doc_results)
            
            # 유사도 점수로 정렬 후 상위 limit개만 선택
            all_results.sort(key=lambda x: x.get("score", 0.0), reverse=True)
            all_results = all_results[:limit]
        
        # 검색 결과 사용 (이미 all_results에 저장됨)
        search_results = all_results
        
        # 🔧 FIX: exclude_id로 지정된 티켓을 결과에서 제외 (자기 자신 제외)
        if exclude_id:
            original_count = len(search_results)
            search_results = [
                result for result in search_results 
                if str(result.get("original_id", "")) != str(exclude_id)
            ]
            filtered_count = len(search_results)
            if original_count != filtered_count:
                logger.debug(f"🚫 제외 ID {exclude_id} 필터링 완료: {original_count}건 → {filtered_count}건")
        
        # 결과 포맷팅 최적화 (불필요한 루프와 로깅 최소화)
        formatted_results = []
        
        # 첫 번째 결과만 디버깅 (성능 최적화)
        if search_results and logger.isEnabledFor(logging.DEBUG):
            first_result = search_results[0]
            logger.debug(f"Search result sample: doc_type='{first_result.get('doc_type')}', id='{first_result.get('original_id')}'")
        
        # 배치 처리로 포맷팅 최적화
        for result in search_results:
            # 필수 필드만 추출하여 메모리 효율성 향상
            formatted_result = {
                "id": result.get("id", ""),
                "content": result.get("content", ""),
                "score": result.get("score", 0.0),
                "metadata": result,  # 전체 result를 metadata로 제공
                "doc_type": result.get("doc_type", ""),
                "original_id": result.get("original_id", ""),
                "subject": result.get("subject", ""),
                "title": result.get("title", ""),
                "status": result.get("status"),
                "priority": result.get("priority"),
                "has_attachments": result.get("has_attachments", False),
                "created_at": result.get("created_at", ""),
                "updated_at": result.get("updated_at", ""),
                "extended_metadata": result.get("extended_metadata", {})
            }
            formatted_results.append(formatted_result)
        
        # 검색 결과 로깅 최적화 (성능 향상을 위해 간소화)
        search_type = "혼합" if not doc_types else "/".join(doc_types)
        logger.info(f"Vector DB 검색 완료 [{search_type}]: {len(formatted_results)}건 반환")
        
        # 성능이 중요한 경우 상세 로깅 생략, DEBUG 레벨에서만 실행
        if logger.isEnabledFor(logging.DEBUG) and formatted_results:
            # 상위 1개 결과만 간단히 로깅 (성능 최적화)
            first_result = formatted_results[0]
            title = (first_result.get("subject") or first_result.get("title", ""))[:25]
            if len(title) > 25:
                title += "..."
            logger.debug(f"상위 결과: {title} (ID: {first_result.get('original_id')}, {first_result.get('score', 0):.3f})")
        
        return formatted_results
        
    except Exception as e:
        logger.error(f"Vector DB 검색 중 오류: {e}")
        return []

async def get_vector_db_stats(tenant_id: str, platform: str) -> Dict[str, Any]:
    """
    Vector DB의 통계 정보를 가져옵니다.
    
    Args:
        tenant_id: 테넌트 ID
        platform: 플랫폼 식별자
        
    Returns:
        Dict[str, Any]: 통계 정보
    """
    try:
        # 메타데이터 필터로 해당 테넌트의 문서 수 조회
        filter_conditions = {
            "must": [
                {"key": "tenant_id", "match": {"value": tenant_id}},
                {"key": "platform", "match": {"value": platform}}
            ]
        }
        
        # 전체 문서 수
        total_count = vector_db.count_documents(filter=filter_conditions)
        
        # 티켓 문서 수
        ticket_filter = {
            "must": [
                {"key": "tenant_id", "match": {"value": tenant_id}},
                {"key": "platform", "match": {"value": platform}},
                {"key": "doc_type", "match": {"value": "ticket"}}
            ]
        }
        ticket_count = vector_db.count_documents(filter=ticket_filter)
        
        # KB 문서 수
        article_filter = {
            "must": [
                {"key": "tenant_id", "match": {"value": tenant_id}},
                {"key": "platform", "match": {"value": platform}},
                {"key": "doc_type", "match": {"value": "article"}}
            ]
        }
        article_count = vector_db.count_documents(filter=article_filter)
        
        return {
            "total_documents": total_count,
            "ticket_documents": ticket_count,
            "article_documents": article_count,
            "tenant_id": tenant_id,
            "platform": platform
        }
        
    except Exception as e:
        logger.error(f"Vector DB 통계 조회 중 오류: {e}")
        return {
            "total_documents": 0,
            "ticket_documents": 0,
            "article_documents": 0,
            "tenant_id": tenant_id,
            "platform": platform,
            "error": str(e)
        }
