"""
벡터 데이터베이스 추상화 인터페이스

이 모듈은 여러 벡터 데이터베이스(ChromaDB, Qdrant 등)에 대한 통합 인터페이스를 제공합니다.
고객사별 데이터 분리와 메타데이터 필터링을 지원합니다.

프로젝트 규칙 및 가이드라인: /PROJECT_RULES.md 참조
"""
# flake8: noqa
# isort: skip_file
# fmt: off

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
VECTOR_SIZE = 1536  # OpenAI/Anthropic 임베딩 차원 수, 모델에 따라 조정 필요
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
    def delete_documents(self, ids: List[str], company_id: Optional[str] = None) -> bool:
        """문서 삭제"""
        pass

    @abstractmethod
    def search(
        self,
        query_embedding: List[float],
        top_k: int,
        company_id: str
    ) -> Dict[str, Any]:
        """벡터 검색"""
        pass

    @abstractmethod
    def count(self, company_id: Optional[str] = None) -> int:
        """문서 수 반환"""
        pass

    @abstractmethod
    def get_by_id(self, original_id_value: str, doc_type: Optional[str] = None, company_id: Optional[str] = None) -> Dict[str, Any]:
        """원본 ID로 단일 문서 조회"""
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
        client_opts = {
            "api_key": QDRANT_API_KEY,
            "timeout": 120,
            "prefer_grpc": False,
        }
        if QDRANT_URL == ":memory:":
            self.client = QdrantClient(location=":memory:", **client_opts)
        else:
            self.client = QdrantClient(url=QDRANT_URL, **client_opts)
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
                # 회사 ID 인덱스 생성
                self.client.create_payload_index(collection_name=self.collection_name, field_name="company_id", field_schema="keyword")
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

                logger.info(f"인덱스 생성 완료")
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
            metadatas: 문서 메타데이터 목록 (company_id, doc_type, id 필수)
            ids: 문서 ID 목록 (원본 숫자 ID, 문자열)

        Returns:
            성공 여부
        """
        if len(texts) != len(embeddings) or len(texts) != len(metadatas) or len(texts) != len(ids):
            raise ValueError("텍스트, 임베딩, 메타데이터, ID 목록의 길이가 일치해야 합니다")
        # 모든 메타데이터에 company_id, doc_type, id, original_id가 포함되어 있는지 확인 및 보정
        for i, (metadata, id) in enumerate(zip(metadatas, ids)):
            if "company_id" not in metadata:
                raise ValueError(f"메타데이터 #{i}에 company_id가 없습니다")
            # doc_type 필수 보정: 없으면 예외
            if "doc_type" not in metadata or not metadata["doc_type"]:
                raise ValueError(f"메타데이터 #{i}에 doc_type이 없습니다. id={id}, metadata={metadata}")
            # id, original_id 필수 보정: 접두어 제거, 숫자 ID(문자열)만 사용
            # id가 ticket-xxxx, kb-xxxx 등 접두어가 붙어 있으면 제거
            id_str = str(id)
            if id_str.startswith("ticket-"):
                id_str = id_str[7:]
            elif id_str.startswith("kb-"):
                id_str = id_str[3:]
            metadata["id"] = id_str
            metadata["original_id"] = id_str
        try:
            # 배치 크기 설정 (25개씩 처리)
            BATCH_SIZE = 25
            success = True
            points = []
            for i, (text, embedding, metadata, id) in enumerate(zip(texts, embeddings, metadatas, ids)):
                # id, original_id는 항상 접두어 없는 숫자 ID(문자열)만 사용
                id_str = str(id)
                if id_str.startswith("ticket-"):
                    id_str = id_str[7:]
                elif id_str.startswith("kb-"):
                    id_str = id_str[3:]
                # doc_type은 별도 필드로만 사용
                doc_type = metadata.get("doc_type")
                # 메타데이터에 id, original_id, doc_type 저장
                payload = {
                    **metadata,
                    "text": text,
                    "id": id_str,
                    "original_id": id_str,
                    "doc_type": doc_type
                }
                # Qdrant 포인트의 UUID는 id_str 기준으로 생성
                from hashlib import md5
                uuid_id = uuid.UUID(md5(id_str.encode()).hexdigest())
                point = PointStruct(
                    id=str(uuid_id),
                    vector=embedding,
                    payload=payload
                )
                points.append(point)
                # 배치 크기에 도달하거나 마지막 항목이면 저장
                if len(points) >= BATCH_SIZE or i == len(texts) - 1:
                    try:
                        logger.info(f"배치 저장 시도 (크기: {len(points)})")
                        self.client.upsert(
                            collection_name=self.collection_name,
                            points=points,
                            wait=True
                        )
                        logger.info(f"배치 저장 성공 (크기: {len(points)})")
                        points = []
                    except Exception as batch_error:
                        logger.error(f"배치 저장 실패: {batch_error}")
                        success = False
                        break
            return success
        except Exception as e:
            logger.error(f"문서 추가 실패: {e}")
            return False

    def delete_documents(self, ids: List[str], company_id: Optional[str] = None) -> bool:
        """
        문서 삭제

        Args:
            ids: 삭제할 문서 ID 목록 (접두어가 포함된 문자열 ID, 예: "ticket-12345")
            company_id: 회사 ID (보안 검증용)

        Returns:
            성공 여부
        """
        try:
            # 문자열 ID를 UUID로 변환
            import uuid
            from hashlib import md5

            uuid_ids = []
            for id in ids:
                # 접두어가 포함된 ID 그대로 사용하여 UUID 생성 (일관성 유지)
                uuid_id = uuid.UUID(md5(id.encode()).hexdigest())
                uuid_ids.append(str(uuid_id))

            # company_id가 지정된 경우 해당 회사의 문서만 삭제
            if company_id:
                try:
                    filter_condition = Filter(
                        must=[
                            FieldCondition(
                                key="company_id",
                                match=MatchValue(value=company_id)
                            )
                        ]
                    )

                    # 회사 ID 필터와 문서 ID 목록을 함께 사용하여 삭제 시도
                    self.client.delete(
                        collection_name=self.collection_name,
                        points_selector=uuid_ids,
                        wait=True,
                        filter=filter_condition
                    )
                except Exception as filter_error:
                    logger.warning(f"필터를 사용한 삭제 실패: {filter_error}, 대체 방법 시도 중...")

                    # 대체 방법: 먼저 해당 문서들을 조회하여 회사 ID 확인 후 삭제
                    for uuid_id in uuid_ids:
                        try:
                            # 문서 조회
                            point = self.client.retrieve(
                                collection_name=self.collection_name,
                                ids=[uuid_id],
                                with_payload=True
                            )

                            # 문서가 존재하고 회사 ID가 일치하면 삭제
                            if point and len(point) > 0 and point[0].payload.get("company_id") == company_id:
                                self.client.delete(
                                    collection_name=self.collection_name,
                                    points_selector=[uuid_id],
                                    wait=True
                                )
                                logger.info(f"문서 {uuid_id} 삭제 완료")
                            elif point and len(point) > 0:
                                logger.warning(f"문서 {uuid_id}의 회사 ID가 일치하지 않아 삭제하지 않습니다.")
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
        company_id: str,
        doc_type: str = None  # 문서 타입 필터링 (권장: "ticket" 또는 "kb")
    ) -> Dict[str, Any]:
        """
        벡터 검색 (DB 레벨 필터링 전용)

        Args:
            query_embedding: 쿼리 임베딩
            top_k: 반환할 최대 문서 수
            company_id: 회사 ID (필수)
            doc_type: 문서 타입 필터 (권장, "ticket" 또는 "kb")
                     None인 경우 경고 후 전체 검색 수행 (성능 저하)

        Returns:
            검색 결과 딕셔너리
            
        Raises:
            ValueError: company_id가 누락된 경우
        """
        if not company_id:
            raise ValueError("company_id는 필수 매개변수입니다.")
            
        # doc_type이 None인 경우 경고 출력 (에러는 발생시키지 않음)
        if not doc_type or not str(doc_type).strip():
            logger.warning(f"⚠️ doc_type이 명시되지 않았습니다. 성능 최적화를 위해 'ticket' 또는 'kb'를 지정하는 것을 권장합니다. (company_id={company_id})")
            filter_conditions = [
                FieldCondition(key="company_id", match=MatchValue(value=company_id))
            ]
            logger.info(f"🔍 전체 검색: company_id={company_id}, top_k={top_k}")
        else:
            if doc_type not in ["ticket", "kb"]:
                logger.warning(f"⚠️ 알 수 없는 doc_type: {doc_type}. 'ticket' 또는 'kb'를 권장합니다.")
            
            # DB 레벨 필터링 조건 구성 - company_id와 doc_type 모두 포함
            filter_conditions = [
                FieldCondition(key="company_id", match=MatchValue(value=company_id)),
                FieldCondition(key="doc_type", match=MatchValue(value=doc_type))
            ]
            logger.info(f"🎯 DB 레벨 필터링: company_id={company_id}, doc_type={doc_type}, top_k={top_k}")
        
        search_filter = Filter(must=filter_conditions)

        try:
            # 🚀 DB 레벨 필터링으로 정확한 결과만 요청 (메모리 내 필터링 완전 제거)
            logger.info(f"⚡ Qdrant 검색 시도 (DB 레벨 필터링, 검색 크기={top_k})")

            search_results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                query_filter=search_filter,  # 최신 API: query_filter 사용
                limit=top_k,  # DB 레벨 필터링으로 정확한 수량 요청
                with_payload=True,
                with_vectors=False  # 성능 최적화: 벡터 반환 비활성화
            )
            logger.info(f"✅ Qdrant 검색 성공: {len(search_results)}개 결과 (DB 레벨 필터링 완료)")
        except Exception as e:
            logger.warning(f"query_filter를 사용한 검색 실패: {e}, filter로 재시도...")

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
                logger.info(f"✅ filter 방식으로 검색 성공: {len(search_results)}개 결과")
            except Exception as filter_error:
                logger.error(f"검색 실패: {filter_error}")
                return {
                    "results": [],
                    "total": 0,
                    "error": str(filter_error)
                }

        # 🚀 DB 레벨 필터링 완료 - 단순한 결과 변환만 수행 (메모리 필터링 완전 제거)
        final_results = []

        for hit in search_results:
            # 기본 결과 변환 (ID, 점수, 페이로드)
            result = {
                "id": hit.id,
                "score": hit.score,
                **hit.payload
            }
            final_results.append(result)

        logger.info(f"✅ DB 레벨 필터링 완료: {len(final_results)}개 결과 반환")

        # 간소화된 결과 반환 (DB 레벨 필터링으로 정확한 결과만 포함)
        return {
            "results": final_results,
            "total": len(final_results)
        }

    def count(self, company_id: Optional[str] = None) -> int:
        """
        문서 수 반환

        Args:
            company_id: 특정 회사의 문서만 카운트할 경우 회사 ID

        Returns:
            문서 수
        """
        try:
            if company_id:
                # 특정 회사의 문서 수 카운트
                # Qdrant 2.x 버전에서는 filter를 지원하지 않을 수 있음
                # 대체 방법으로 검색을 사용하여 카운트
                try:
                    company_filter = Filter(
                        must=[
                            FieldCondition(
                                key="company_id",
                                match=MatchValue(value=company_id)
                            )
                        ]
                    )

                    # 검색 결과로 카운트
                    count = self.client.count(
                        collection_name=self.collection_name,
                        filter=company_filter  # Qdrant 버전에 따라 filter 또는 count_filter 사용
                    )
                    return count.count
                except Exception as inner_e:
                    logger.warning(f"필터를 사용한 카운트 실패: {inner_e}, 대체 방법 시도 중...")

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

                        # company_id로 필터링하여 카운트
                        company_matches = sum(1 for point in batch if point.payload.get("company_id") == company_id)
                        count += company_matches
                        total_scanned += len(batch)

                        # 다음 오프셋 설정
                        offset = next_offset
                        if offset is None:
                            break

                    logger.info(f"{total_scanned}개 문서 중 {count}개가 company_id '{company_id}'와 일치합니다.")
                    return count
            else:
                # 전체 문서 수 카운트
                count = self.client.count(collection_name=self.collection_name)
                return count.count
        except Exception as e:
            logger.error(f"문서 수 카운트 실패: {e}")
            return 0

    def get_by_id(self, original_id_value: str, doc_type: Optional[str] = None, company_id: Optional[str] = None) -> Dict[str, Any]:
        """
        원본 ID로 단일 문서 조회

        Args:
            original_id_value: 조회할 문서의 원본 ID (Freshdesk 원본 숫자 ID의 문자열 형태, 예: "12345")
            doc_type: 문서 타입 필터 ("ticket" 또는 "kb", None이거나 빈 문자열이면 예외 발생)
            company_id: 회사 ID 필터 (선택 사항, None이면 "default" 사용)

        Returns:
            조회된 문서 정보 (메타데이터와 임베딩 포함)

        Raises:
            ValueError: doc_type이 None 또는 빈 문자열인 경우
        """
        # doc_type이 반드시 명시되어야 함을 강제
        if not doc_type or not str(doc_type).strip():
            logger.error("get_by_id 호출 시 doc_type이 반드시 명시되어야 합니다. (ticket 또는 kb)")
            raise ValueError("get_by_id 호출 시 doc_type 파라미터는 필수입니다. (예: doc_type='ticket' 또는 doc_type='kb')")
        try:
            # company_id가 None이면 "default"로 설정
            search_company_id = company_id if company_id else "default"
            logger.info(f"문서 조회 시작 (original_id: {original_id_value}, doc_type: {doc_type}, company_id: {search_company_id})")

            # 필터 조건: company_id, original_id, doc_type 모두 필수
            filter_conditions = [
                FieldCondition(
                    key="company_id",
                    match=MatchValue(value=search_company_id)
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
                logger.info(f"검색 결과 - ID: {point.id}, original_id='{payload.get('original_id')}', doc_type='{payload.get('doc_type')}', type='{payload.get('type')}', company_id='{payload.get('company_id')}'")
                document_type = payload.get("doc_type", "") or payload.get("type", "")
                return {
                    "id": payload.get("original_id", ""),
                    "doc_type": document_type,
                    "metadata": payload,
                    "embedding": point.vector if hasattr(point, 'vector') else None
                }
            else:
                logger.warning(f"원본 ID '{original_id_value}', 타입 '{doc_type}', company_id '{search_company_id}'으로 문서를 찾을 수 없습니다.")
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
                    if doc_type_value in ["ticket", "kb"]:
                        # 원본 페이로드에 'doc_type' 필드 추가
                        updated_payload["doc_type"] = doc_type_value
                        update_needed = True

                # 2. source_type 일관성 확보
                current_doc_type = updated_payload.get("doc_type") or payload.get("type")

                if current_doc_type == "kb" and "source_type" not in updated_payload:
                    # KB 문서에 source_type 추가
                    updated_payload["source_type"] = "1"  # KB 문서의 표준 source_type
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
