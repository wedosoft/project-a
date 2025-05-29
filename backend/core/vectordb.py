"""
벡터 데이터베이스 추상화 인터페이스

이 모듈은 여러 벡터 데이터베이스(ChromaDB, Qdrant 등)에 대한 통합 인터페이스를 제공합니다.
고객사별 데이터 분리와 메타데이터 필터링을 지원합니다.

프로젝트 규칙 및 가이드라인: /PROJECT_RULES.md 참조
"""

import logging
import os
import time
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

# Qdrant 클라이언트
from qdrant_client import QdrantClient
from qdrant_client.http.models import (
    CollectionStatus,
    FieldCondition,
    Filter,
    MatchAny,
    MatchValue,
    PointStruct,
)
from qdrant_client.models import Distance, VectorParams

# 로깅 설정
logger = logging.getLogger(__name__)

# 환경 변수
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
VECTOR_SIZE = 1536  # OpenAI/Anthropic 임베딩 차원 수, 모델에 따라 조정 필요
COLLECTION_NAME = "documents"  # 기본 컬렉션명
FAQ_COLLECTION_NAME = "faqs" # FAQ 컬렉션명 추가


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
    def get_by_id(self, id: str, company_id: Optional[str] = None) -> Dict[str, Any]:
        """ID로 단일 문서 조회"""
        pass


class QdrantAdapter(VectorDBInterface):
    """Qdrant 벡터 DB 어댑터 구현"""

    def __init__(self, collection_name: str = COLLECTION_NAME):
        """Qdrant 클라이언트 초기화"""
        self.collection_name = collection_name
        self.client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
        self._ensure_collection_exists() # 기본 문서 컬렉션 확인 (인덱스 생성 포함)
        self._ensure_faq_collection_exists() # FAQ 컬렉션 확인

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
                # 문서 타입 인덱스 생성 - 키워드 및 정수 타입 모두 시도
                try:
                    self.client.create_payload_index(collection_name=self.collection_name, field_name="type", field_schema="keyword")
                    logger.info(f"type 인덱스(keyword) 생성 완료")
                except Exception as type_err:
                    logger.warning(f"type 키워드 인덱스 생성 실패: {type_err}, 정수 인덱스 시도...")
                    try:
                        self.client.create_payload_index(collection_name=self.collection_name, field_name="type", field_schema="integer")
                        logger.info(f"type 인덱스(integer) 생성 완료")
                    except Exception as int_err:
                        logger.warning(f"type 정수 인덱스 생성 실패: {int_err}")
                
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

    def _ensure_faq_collection_exists(self) -> None:
        """FAQ 컬렉션이 없으면 생성"""
        collections = self.client.get_collections()
        collection_names = [collection.name for collection in collections.collections]
        
        if FAQ_COLLECTION_NAME not in collection_names:
            logger.info(f"FAQ 컬렉션 '{FAQ_COLLECTION_NAME}' 생성 시작")
            self.client.create_collection(
                collection_name=FAQ_COLLECTION_NAME,
                vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
            )
            # 페이로드 인덱스 생성 (검색 성능 향상)
            self.client.create_payload_index(collection_name=FAQ_COLLECTION_NAME, field_name="company_id", field_schema="keyword")
            self.client.create_payload_index(collection_name=FAQ_COLLECTION_NAME, field_name="category", field_schema="keyword")
            logger.info(f"FAQ 컬렉션 '{FAQ_COLLECTION_NAME}' 생성 완료 및 페이로드 인덱스 설정")


    def add_faq_entry(self, faq_entry: Dict[str, Any]) -> bool:
        """
        단일 FAQ 항목을 FAQ 컬렉션에 추가/업데이트합니다.
        faq_entry 딕셔너리는 FAQEntry Pydantic 모델의 필드를 따라야 합니다.
        특히 'embedding' 필드가 포함되어야 합니다.
        """
        if "embedding" not in faq_entry or not faq_entry["embedding"]:
            logger.error("FAQ 항목 추가 실패: 임베딩이 없습니다.")
            return False
        if "company_id" not in faq_entry:
            logger.error("FAQ 항목 추가 실패: company_id가 없습니다.")
            return False

        try:
            # FAQ ID가 제공되지 않으면 UUID 생성
            faq_id = faq_entry.get("id") or str(uuid.uuid4())
            
            payload = {
                "question": faq_entry["question"],
                "answer": faq_entry["answer"],
                "category": faq_entry.get("category"),
                "source_doc_id": faq_entry.get("source_doc_id"),
                "company_id": faq_entry["company_id"],
                "last_updated": faq_entry.get("last_updated", datetime.utcnow().isoformat())
            }
            # None 값은 payload에서 제외
            payload = {k: v for k, v in payload.items() if v is not None}

            point = PointStruct(
                id=faq_id,
                vector=faq_entry["embedding"],
                payload=payload
            )
            
            self.client.upsert(
                collection_name=FAQ_COLLECTION_NAME,
                points=[point]
            )
            logger.info(f"FAQ 항목 ID '{faq_id}' 추가/업데이트 완료.")
            return True
        except Exception as e:
            logger.error(f"FAQ 항목 ID '{faq_entry.get('id', 'N/A')}' 추가/업데이트 실패: {e}")
            return False

    def add_faq_entries(self, faq_entries: List[Dict[str, Any]]) -> bool:
        """
        여러 FAQ 항목을 FAQ 컬렉션에 배치로 추가/업데이트합니다.
        각 faq_entry 딕셔너리는 FAQEntry Pydantic 모델의 필드를 따라야 합니다.
        """
        points_to_upsert = []
        for entry in faq_entries:
            if "embedding" not in entry or not entry["embedding"]:
                logger.warning(f"FAQ 항목 건너뜀 (ID: {entry.get('id', 'N/A')}): 임베딩 없음.")
                continue
            if "company_id" not in entry:
                logger.warning(f"FAQ 항목 건너뜀 (ID: {entry.get('id', 'N/A')}): company_id 없음.")
                continue

            faq_id = entry.get("id") or str(uuid.uuid4())
            payload = {
                "question": entry["question"],
                "answer": entry["answer"],
                "category": entry.get("category"),
                "source_doc_id": entry.get("source_doc_id"),
                "company_id": entry["company_id"],
                "last_updated": entry.get("last_updated", datetime.utcnow().isoformat())
            }
            payload = {k: v for k, v in payload.items() if v is not None}

            points_to_upsert.append(PointStruct(
                id=faq_id,
                vector=entry["embedding"],
                payload=payload
            ))

        if not points_to_upsert:
            logger.info("추가/업데이트할 유효한 FAQ 항목이 없습니다.")
            return False

        try:
            self.client.upsert(
                collection_name=FAQ_COLLECTION_NAME,
                points=points_to_upsert
            )
            logger.info(f"{len(points_to_upsert)}개의 FAQ 항목 배치 추가/업데이트 완료.")
            return True
        except Exception as e:
            logger.error(f"FAQ 항목 배치 추가/업데이트 실패: {e}")
            return False

    def search_faqs(
        self,
        query_embedding: List[float],
        top_k: int,
        company_id: str,
        category: Optional[str] = None,
        min_score: Optional[float] = None, # 최소 유사도 점수 필터
    ) -> List[Dict[str, Any]]:
        """
        FAQ 컬렉션에서 쿼리 임베딩과 유사한 FAQ를 검색합니다.
        company_id로 필터링하고, 선택적으로 category로 추가 필터링합니다.
        """
        if not company_id:
            raise ValueError("FAQ 검색 시 company_id는 필수입니다.")

        # 컬렉션이 존재하는지 확인
        try:
            collections = self.client.get_collections()
            collection_names = [collection.name for collection in collections.collections]
            if FAQ_COLLECTION_NAME not in collection_names:
                logger.warning(f"FAQ 컬렉션 '{FAQ_COLLECTION_NAME}'이 존재하지 않아 빈 결과 반환")
                return []
        except Exception as e:
            logger.error(f"FAQ 컬렉션 확인 실패: {e}")
            return []
        
        try:
            logger.info(f"FAQ 검색 시작 (company_id: {company_id}, category: {category}, min_score: {min_score})")
            
            # payload 기반 필터링을 위한 필터 조건 구성
            filter_conditions = [
                FieldCondition(key="company_id", match=MatchValue(value=company_id))
            ]
            if category:
                filter_conditions.append(
                    FieldCondition(key="category", match=MatchValue(value=category))
                )
            
            faq_filter = Filter(must=filter_conditions)

            try:
                # query_filter 매개변수로 검색 시도
                search_results = self.client.search(
                    collection_name=FAQ_COLLECTION_NAME,
                    query_vector=query_embedding,
                    query_filter=faq_filter, # query_filter 사용
                    limit=top_k,
                    with_payload=True,
                    score_threshold=min_score # 최소 점수 임계값 설정
                )
            except Exception as filter_err:
                logger.warning(f"query_filter를 사용한 FAQ 검색 실패: {filter_err}, filter로 다시 시도")
                # filter 매개변수로 다시 시도
                try:
                    search_results = self.client.search(
                        collection_name=FAQ_COLLECTION_NAME,
                        query_vector=query_embedding,
                        filter=faq_filter, # filter 사용
                        limit=top_k,
                        with_payload=True,
                        score_threshold=min_score
                    )
                except Exception as e:
                    logger.warning(f"filter를 사용한 FAQ 검색 실패: {e}, 필터링 없이 검색 후 메모리에서 처리")
                    
                    # 필터링 없이 검색 후 메모리에서 처리
                    raw_results = self.client.search(
                        collection_name=FAQ_COLLECTION_NAME,
                        query_vector=query_embedding,
                        limit=top_k * 3, # 더 많은 결과를 가져와서 필터링
                        with_payload=True,
                        score_threshold=min_score
                    )
                    
                    # 메모리에서 company_id 필터링
                    search_results = []
                    for result in raw_results:
                        if result.payload.get("company_id") == company_id:
                            # 카테고리 필터링 (설정된 경우)
                            if not category or result.payload.get("category") == category:
                                search_results.append(result)
                    
                    # 최대 개수 제한
                    search_results = search_results[:top_k]
            
            faqs = []
            for hit in search_results:
                # score가 min_score보다 낮으면 제외 (추가 안전 장치)
                if min_score and hit.score < min_score:
                    continue
                    
                faq_data = {
                    "id": hit.id,
                    "score": hit.score,
                    **hit.payload, # payload 내용을 faq_data에 직접 추가
                }
                faqs.append(faq_data)
            
            logger.info(f"FAQ 검색 완료: {len(faqs)}개 결과 (company_id: {company_id}, category: {category})")
            return faqs
        except Exception as e:
            logger.error(f"FAQ 검색 실패: {e}")
            return []

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
        company_id: str,
        doc_type: str = None  # 새로운 매개변수 추가 - 문서 타입 필터링 (ticket, kb)
    ) -> Dict[str, Any]:
        """
        벡터 검색
        
        Args:
            query_embedding: 쿼리 임베딩
            top_k: 반환할 최대 문서 수
            company_id: 회사 ID (필수)
            doc_type: 문서 타입 필터 (선택사항, "ticket" 또는 "kb")
            
        Returns:
            검색 결과 딕셔너리
        """
        if not company_id:
            raise ValueError("company_id는 필수 매개변수입니다.")
        
        start_time = time.time()
        
        # 회사 ID 필터 기본 설정
        filter_conditions = [
            FieldCondition(
                key="company_id",
                match=MatchValue(value=company_id)
            )
        ]
        
        # 문서 타입 필터 추가 (있는 경우)
        if doc_type:
            logger.info(f"문서 타입 필터 적용: {doc_type}")
            if doc_type == "ticket":
                # 티켓 타입의 경우 Freshdesk 티켓 유형들을 포함
                ticket_types = ["Problem", "Incident", "Question", "Task", "Change"]
                filter_conditions.append(
                    FieldCondition(
                        key="type",
                        match=MatchAny(any=ticket_types)
                    )
                )
            elif doc_type == "kb":
                # KB 문서의 경우 type이 "1" 또는 숫자 1, 또는 "kb" 값을 갖는 문서를 포함
                # type 필드에 "1"이나 "kb" 값이 없을 경우를 대비하여 source_type도 확인
                try:
                    # 필터를 리스트로 수정하여 Filter 생성 오류 방지
                    filter_conditions.append(
                        Filter(
                            should=[
                                FieldCondition(key="type", match=MatchValue(value="1")),
                                FieldCondition(key="type", match=MatchValue(value=1)),  # 숫자 값도 시도
                                FieldCondition(key="type", match=MatchValue(value="kb")),
                                FieldCondition(key="source_type", match=MatchValue(value="kb"))
                            ]
                        )
                    )
                    logger.info(f"KB 문서 복합 필터 성공적으로 생성됨")
                except Exception as e:
                    # 복합 필터 생성에 실패한 경우 메모리 내 필터링을 위한 플래그 설정
                    logger.warning(f"KB 복합 필터 생성 실패: {e}, 메모리 내 필터링 적용")
                    # 메모리 내 필터링을 위해 doc_type만 설정하고 필터에는 추가하지 않음
            else:
                # 기타 타입은 그대로 매칭
                filter_conditions.append(
                    FieldCondition(
                        key="type",
                        match=MatchValue(value=doc_type)
                    )
                )
        
        company_filter = Filter(must=filter_conditions)
        
        # 검색 실행
        try:
            # Qdrant 2.x 버전에서는 filter 매개변수를 지원함
            search_results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                limit=top_k * 3,  # 더 많은 결과를 가져와서 필터링 (KB 문서 확보)
                query_filter=company_filter,  # filter 대신 query_filter 사용
                with_payload=True
            )
            logger.info(f"query_filter를 사용한 검색 성공: {len(search_results)}개 결과")
        except Exception as e:
            # 'filter' 또는 'query_filter' 매개변수가 지원되지 않는 경우 대체 방법 사용
            logger.warning(f"필터를 사용한 검색 실패: {str(e)}\nRaw response content:\n{getattr(e, 'response', None) and e.response.content.decode('utf-8', errors='replace')[:200]} ...", exc_info=False)
            
            # 전체 검색 후 메모리에서 필터링
            logger.info(f"필터 없이 검색 후 메모리에서 필터링 시도")
            search_results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                limit=top_k * 20,  # 훨씬 더 많은 결과를 가져와서 필터링
                with_payload=True
            )
            
            # KB 문서를 찾기 위해 모든 결과 확인을 위한 로깅
            all_types = set()
            kb_types = set()
            for result in search_results:
                result_type = result.payload.get("type", "")
                result_source_type = result.payload.get("source_type", "")
                all_types.add(f"type:{result_type}")
                all_types.add(f"source_type:{result_source_type}")
                if result_type == "1" or result_type == "kb" or result_source_type == "kb":
                    kb_types.add(f"type:{result_type},source_type:{result_source_type}")
            
            logger.info(f"검색된 총 결과 {len(search_results)}개, 발견된 문서 타입들: {all_types}")
            if doc_type == "kb":
                logger.info(f"KB 문서로 판단되는 타입: {kb_types}")
            
            # 메모리 내 필터링 (company_id 및 선택적 doc_type)
            filtered_results = []
            for result in search_results:
                # company_id 필터링
                if result.payload.get("company_id") != company_id:
                    continue
                    
                # 문서 타입 필터링 (필요한 경우)
                if doc_type:
                    result_type = result.payload.get("type", "")
                    result_source_type = result.payload.get("source_type", "")
                    
                    if doc_type == "ticket":
                        # 티켓 타입의 경우 Freshdesk 티켓 유형들을 허용
                        ticket_types = ["Problem", "Incident", "Question", "Task", "Change"]
                        if result_type not in ticket_types:
                            continue
                    elif doc_type == "kb":
                        # KB 문서의 경우 type이 "1" 또는 숫자 1이거나 "kb", 또는 source_type이 "kb"인 경우 포함
                        # 문자열과 숫자 모두 처리할 수 있도록 함
                        if (result_type != "1" and result_type != 1 and result_type != "kb" and 
                            result_source_type != "kb"):
                            continue
                    else:
                        # 기타 타입은 정확히 매칭
                        if result_type != doc_type and result_source_type != doc_type:
                            continue
                    
                filtered_results.append(result)
            
            # 필터링된 결과 잘라내기
            search_results = filtered_results[:top_k]
            logger.info(f"메모리 내 필터링 후 결과: {len(search_results)}개 {'('+ doc_type + ')' if doc_type else ''}")
        
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
            id: 조회할 문서의 ID (원본 티켓 ID, 예: "4243")
            company_id: 회사 ID 필터 (선택 사항, None이면 "default" 사용)

        Returns:
            조회된 문서 정보 (메타데이터와 임베딩 포함)
        """
        try:
            # company_id가 None이면 "default"로 설정
            search_company_id = company_id if company_id else "default"
            logger.info(f"문서 조회 시작 (id: {id}, company_id: {search_company_id})")
            
            # 검색할 ID 값들 준비
            search_values = []
            
            # 1. 입력된 ID 그대로 (문자열)
            search_values.append(id)
            
            # 2. 숫자형 ID 변환 시도
            try:
                numeric_id = int(id)
                search_values.append(numeric_id)
            except ValueError:
                pass
            
            # 3. "ticket-" 접두사가 없다면 추가
            if not id.startswith("ticket-"):
                search_values.append(f"ticket-{id}")
            
            # 4. "ticket-" 접두사가 있다면 제거
            if id.startswith("ticket-"):
                search_values.append(id.replace("ticket-", ""))
                try:
                    clean_numeric = int(id.replace("ticket-", ""))
                    search_values.append(clean_numeric)
                except ValueError:
                    pass
            
            logger.info(f"ID '{id}' 검색 시도값들: {search_values}")
            
            # 각 검색값으로 payload 필터링 시도
            for search_value in search_values:
                # id 필드로 검색
                filter_conditions = []
                
                # company_id 필터 추가 (수정된 company_id 사용)
                filter_conditions.append(
                    FieldCondition(
                        key="company_id",
                        match=MatchValue(value=search_company_id)
                    )
                )
                
                # ID 필터 추가 (id 필드)
                filter_conditions.append(
                    FieldCondition(
                        key="id",
                        match=MatchValue(value=search_value)
                    )
                )
                
                try:
                    # scroll로 필터링된 결과 검색
                    scroll_result = self.client.scroll(
                        collection_name=self.collection_name,
                        scroll_filter=Filter(must=filter_conditions),
                        limit=1,
                        with_payload=True,
                        with_vectors=True
                    )
                    
                    if scroll_result[0]:  # 결과가 있으면
                        point = scroll_result[0][0]
                        logger.info(f"ID '{id}' 문서를 찾았습니다 (검색값: {search_value})")
                        return {
                            "id": point.payload.get("original_id", point.payload.get("id", id)),
                            "metadata": point.payload,
                            "embedding": point.vector
                        }
                        
                except Exception as search_error:
                    logger.debug(f"ID 필드 '{search_value}' 검색 실패: {search_error}")
                
                # original_id 필드로도 검색 시도
                try:
                    filter_conditions_orig = []
                    
                    # company_id 필터 추가 (수정된 company_id 사용)
                    filter_conditions_orig.append(
                        FieldCondition(
                            key="company_id",
                            match=MatchValue(value=search_company_id)
                        )
                    )
                    
                    # original_id 필터 추가
                    filter_conditions_orig.append(
                        FieldCondition(
                            key="original_id",
                            match=MatchValue(value=str(search_value))
                        )
                    )
                    
                    scroll_result_orig = self.client.scroll(
                        collection_name=self.collection_name,
                        scroll_filter=Filter(must=filter_conditions_orig),
                        limit=1,
                        with_payload=True,
                        with_vectors=True
                    )
                    
                    if scroll_result_orig[0]:  # 결과가 있으면
                        point = scroll_result_orig[0][0]
                        logger.info(f"ID '{id}' 문서를 찾았습니다 (original_id 검색값: {search_value})")
                        return {
                            "id": point.payload.get("original_id", point.payload.get("id", id)),
                            "metadata": point.payload,
                            "embedding": point.vector
                        }
                        
                except Exception as search_error:
                    logger.debug(f"original_id 필드 '{search_value}' 검색 실패: {search_error}")
            
            # 모든 방법으로 찾지 못한 경우
            logger.warning(f"ID '{id}'로 문서를 찾을 수 없습니다. 시도한 검색값들: {search_values}")
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

    def drop_collection(self, collection_name: str = None) -> bool:
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
            elif name == FAQ_COLLECTION_NAME:
                self._ensure_faq_collection_exists()
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
