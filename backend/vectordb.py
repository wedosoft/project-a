"""
벡터 데이터베이스 추상화 인터페이스

이 모듈은 여러 벡터 데이터베이스(ChromaDB, Qdrant 등)에 대한 통합 인터페이스를 제공합니다.
고객사별 데이터 분리와 메타데이터 필터링을 지원합니다.

프로젝트 규칙 및 가이드라인: /PROJECT_RULES.md 참조
"""

import os
import logging
import uuid
from typing import List, Dict, Any, Optional, Union
from abc import ABC, abstractmethod
import time

# Qdrant 클라이언트
from qdrant_client import QdrantClient
from qdrant_client.http.models import (
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    CollectionStatus,
)
from qdrant_client.models import VectorParams, Distance

# 로깅 설정
logger = logging.getLogger(__name__)

# 환경 변수
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
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


class QdrantAdapter(VectorDBInterface):
    """Qdrant 벡터 DB 어댑터 구현"""

    def __init__(self, collection_name: str = COLLECTION_NAME):
        """Qdrant 클라이언트 초기화"""
        self.collection_name = collection_name
        self.client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
        self._ensure_collection_exists()

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
            logger.info(f"컬렉션 '{self.collection_name}' 생성 완료")

    def add_documents(
        self, 
        texts: List[str], 
        embeddings: List[List[float]], 
        metadatas: List[Dict[str, Any]], 
        ids: List[str]
    ) -> bool:
        """
        문서 추가
        
        Args:
            texts: 문서 텍스트 목록
            embeddings: 문서 임베딩 목록
            metadatas: 문서 메타데이터 목록 (company_id 필수 포함)
            ids: 문서 ID 목록 (문자열, 변환되어 저장됨)
            
        Returns:
            성공 여부
        """
        if len(texts) != len(embeddings) or len(texts) != len(metadatas) or len(texts) != len(ids):
            raise ValueError("텍스트, 임베딩, 메타데이터, ID 목록의 길이가 일치해야 합니다")
        
        # 모든 메타데이터에 company_id가 포함되어 있는지 확인
        for i, metadata in enumerate(metadatas):
            if "company_id" not in metadata:
                raise ValueError(f"메타데이터 #{i}에 company_id가 없습니다")
        
        try:
            points = []
            for i, (text, embedding, metadata, id) in enumerate(zip(texts, embeddings, metadatas, ids)):
                # 원본 ID를 메타데이터에 저장
                payload = {**metadata, "text": text, "original_id": id}
                
                # 문자열 ID를 Qdrant 호환 형식으로 변환 (UUID)
                import uuid
                from hashlib import md5
                
                # 일관된 UUID 생성을 위해 문자열 ID를 해시하여 변환
                # 이 방식은 동일한 ID가 항상 동일한 UUID를 생성하도록 보장함
                uuid_id = uuid.UUID(md5(id.encode()).hexdigest())
                
                # Qdrant 포인트 생성
                point = PointStruct(
                    id=str(uuid_id),  # UUID 형식의 문자열로 변환
                    vector=embedding,
                    payload=payload
                )
                points.append(point)
            
            # 배치로 추가
            self.client.upsert(
                collection_name=self.collection_name,
                points=points
            )
            
            return True
        except Exception as e:
            logger.error(f"문서 추가 실패: {e}")
            return False

    def delete_documents(self, ids: List[str], company_id: Optional[str] = None) -> bool:
        """
        문서 삭제
        
        Args:
            ids: 삭제할 문서 ID 목록 (원본 문자열 ID)
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
        company_id: str
    ) -> Dict[str, Any]:
        """
        벡터 검색
        
        Args:
            query_embedding: 쿼리 임베딩
            top_k: 반환할 최대 문서 수
            company_id: 회사 ID (필수)
            
        Returns:
            검색 결과 딕셔너리
        """
        if not company_id:
            raise ValueError("company_id는 필수 매개변수입니다.")
        
        start_time = time.time()
        
        # 회사 ID 필터
        company_filter = Filter(
            must=[
                FieldCondition(
                    key="company_id",
                    match=MatchValue(value=company_id)
                )
            ]
        )
        
        # 검색 실행
        try:
            # Qdrant 2.x 버전에서는 filter 매개변수를 지원함
            search_results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                limit=top_k,
                filter=company_filter,
                with_payload=True
            )
        except Exception as e:
            # 'filter' 매개변수가 지원되지 않는 경우 대체 방법 사용
            logger.warning(f"filter 매개변수를 사용한 검색 실패: {e}, 대체 방법 시도 중...")
            
            # 전체 검색 후 메모리에서 필터링
            search_results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                limit=top_k * 10,  # 더 많은 결과를 가져와서 필터링
                with_payload=True
            )
            
            # company_id로 메모리 내 필터링
            search_results = [
                result for result in search_results 
                if result.payload.get("company_id") == company_id
            ][:top_k]  # top_k 개수만큼 자름
        
        # ChromaDB 형식과 호환되는 결과 포맷으로 변환
        documents = []
        metadatas = []
        distances = []
        ids = []
        
        for result in search_results:
            # 텍스트 추출
            text = result.payload.pop("text", "")  # 텍스트 추출 후 메타데이터에서 제거
            documents.append(text)
            
            # 메타데이터 추출 (text 제외한 나머지 payload)
            metadatas.append(result.payload)
            
            # 거리 및 ID 추출
            distances.append(result.score)
            ids.append(result.id)
        
        search_time = time.time() - start_time
        logger.info(f"벡터 검색 완료: {len(documents)}개 결과, {search_time:.2f}초 소요")
        
        return {
            "documents": documents,
            "metadatas": metadatas,
            "distances": distances,
            "ids": ids,
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

    def get_by_id(self, id: str, company_id: Optional[str] = None) -> Dict[str, Any]:
        """
        ID로 단일 문서 조회

        Args:
            id: 조회할 문서의 ID (원본 문자열 ID)
            company_id: 회사 ID 필터 (선택 사항)

        Returns:
            조회된 문서 정보 (메타데이터와 임베딩 포함)
        """
        try:
            # 문자열 ID를 UUID로 변환
            import uuid
            from hashlib import md5
            
            uuid_id = uuid.UUID(md5(id.encode()).hexdigest())
            
            # 회사 ID 필터링
            filter_condition = None
            if company_id:
                filter_condition = Filter(
                    must=[
                        FieldCondition(
                            key="company_id",
                            match=MatchValue(value=company_id),
                        )
                    ]
                )
            
            # 단일 포인트 조회 - filter 매개변수는 retrieve에서 지원되지 않음
            points = self.client.retrieve(
                collection_name=self.collection_name,
                ids=[str(uuid_id)],
                with_payload=True,
                with_vectors=True
            )
            
            # 결과가 있고 회사 ID 필터가 설정된 경우 수동으로 필터링
            if points and len(points) > 0 and company_id:
                # 회사 ID가 일치하는지 확인
                if points[0].payload.get("company_id") != company_id:
                    logger.warning(f"ID '{id}'에 해당하는 문서가 있지만 회사 ID '{company_id}'와 일치하지 않습니다.")
                    return {}
            
            # 결과가 있으면 첫 번째 포인트 반환
            if points and len(points) > 0:
                # 원본 ID를 반환 결과에 포함
                original_id = points[0].payload.get("original_id", id)
                return {
                    "id": original_id,  # 원본 ID 반환
                    "metadata": points[0].payload,
                    "embedding": points[0].vector
                }
            else:
                logger.warning(f"ID '{id}'로 문서를 찾을 수 없습니다.")
                return {}
                
        except Exception as e:
            logger.error(f"ID '{id}'로 문서 조회 중 오류 발생: {e}")
            return {}

    def get_collection_info(self) -> Dict[str, Any]:
        """
        컬렉션 정보 조회

        Returns:
            컬렉션 상태 정보
        """
        try:
            collection_info = self.client.get_collection(collection_name=self.collection_name)
            return {
                "name": collection_info.name,
                "status": collection_info.status,
                "vector_size": collection_info.config.params.vectors.size,
                "points_count": collection_info.vectors_count
            }
        except Exception as e:
            logger.error(f"컬렉션 정보 조회 중 오류 발생: {e}")
            return {"error": str(e)}


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
