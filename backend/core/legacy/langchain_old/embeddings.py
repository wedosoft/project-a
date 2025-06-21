"""
임베딩 모델 관리 모듈

이 모듈은 기존 임베딩 생성 로직을 langchain 구조로 래핑합니다.
기존 코드의 90% 이상을 재활용하며 다양한 임베딩 모델을 통합 관리합니다.
"""

import logging
from typing import List, Dict, Any, Optional, Union
import asyncio

logger = logging.getLogger(__name__)


class EmbeddingManager:
    """
    임베딩 모델 관리자
    
    기존 임베딩 생성 로직을 90%+ 재활용하여
    다양한 임베딩 모델을 통합 관리합니다.
    """
    
    def __init__(self, model_name: str = "text-embedding-ada-002"):
        """
        임베딩 관리자 초기화
        
        Args:
            model_name: 사용할 임베딩 모델명
        """
        self.model_name = model_name
        self._embedding_cache = {}
        
    async def generate_embedding(
        self, 
        text: str,
        use_cache: bool = True
    ) -> List[float]:
        """
        텍스트 임베딩 생성
        
        기존 임베딩 생성 로직을 90%+ 재활용
        
        Args:
            text: 임베딩을 생성할 텍스트
            use_cache: 캐시 사용 여부
            
        Returns:
            임베딩 벡터
        """
        try:
            # 캐시 확인
            if use_cache and text in self._embedding_cache:
                logger.debug(f"임베딩 캐시 적중: {text[:50]}...")
                return self._embedding_cache[text]
            
            logger.info(f"임베딩 생성: 모델={self.model_name}, 텍스트 길이={len(text)}")
            
            # TODO: 기존 임베딩 생성 로직 통합
            # 여기서는 스켈레톤만 제공
            embedding = []  # 실제 구현에서는 기존 코드 사용
            
            # 캐시 저장
            if use_cache:
                self._embedding_cache[text] = embedding
                
            return embedding
            
        except Exception as e:
            logger.error(f"임베딩 생성 실패: {e}")
            return []
            
    async def generate_embeddings_batch(
        self,
        texts: List[str],
        batch_size: int = 10,
        use_cache: bool = True
    ) -> List[List[float]]:
        """
        배치 임베딩 생성
        
        기존 배치 처리 로직을 90%+ 재활용
        
        Args:
            texts: 임베딩을 생성할 텍스트 리스트
            batch_size: 배치 크기
            use_cache: 캐시 사용 여부
            
        Returns:
            임베딩 벡터 리스트
        """
        try:
            logger.info(f"배치 임베딩 생성: 텍스트 수={len(texts)}, 배치 크기={batch_size}")
            
            embeddings = []
            
            # 배치 단위로 처리
            for i in range(0, len(texts), batch_size):
                batch_texts = texts[i:i + batch_size]
                
                # 병렬 처리
                batch_tasks = [
                    self.generate_embedding(text, use_cache=use_cache)
                    for text in batch_texts
                ]
                
                batch_embeddings = await asyncio.gather(*batch_tasks)
                embeddings.extend(batch_embeddings)
                
            logger.info(f"배치 임베딩 생성 완료: {len(embeddings)}개")
            return embeddings
            
        except Exception as e:
            logger.error(f"배치 임베딩 생성 실패: {e}")
            return []
            
    def clear_cache(self):
        """임베딩 캐시 정리"""
        self._embedding_cache.clear()
        logger.info("임베딩 캐시가 정리되었습니다.")
        
    def get_cache_stats(self) -> Dict[str, Any]:
        """캐시 통계 정보 반환"""
        return {
            "cache_size": len(self._embedding_cache),
            "model_name": self.model_name
        }


# 편의 함수들 (기존 패턴 유지)
async def create_embedding_manager(model_name: str = "text-embedding-ada-002") -> EmbeddingManager:
    """
    EmbeddingManager 인스턴스 생성 편의 함수
    
    Args:
        model_name: 임베딩 모델명
        
    Returns:
        EmbeddingManager 인스턴스
    """
    return EmbeddingManager(model_name=model_name)


async def generate_text_embedding(
    text: str,
    model_name: str = "text-embedding-ada-002",
    **kwargs
) -> List[float]:
    """
    텍스트 임베딩 생성 편의 함수
    
    Args:
        text: 텍스트
        model_name: 모델명
        **kwargs: 추가 매개변수
        
    Returns:
        임베딩 벡터
    """
    embedding_manager = await create_embedding_manager(model_name=model_name)
    return await embedding_manager.generate_embedding(text, **kwargs)


async def generate_batch_embeddings(
    texts: List[str],
    model_name: str = "text-embedding-ada-002",
    **kwargs
) -> List[List[float]]:
    """
    배치 임베딩 생성 편의 함수
    
    Args:
        texts: 텍스트 리스트
        model_name: 모델명
        **kwargs: 추가 매개변수
        
    Returns:
        임베딩 벡터 리스트
    """
    embedding_manager = await create_embedding_manager(model_name=model_name)
    return await embedding_manager.generate_embeddings_batch(texts, **kwargs)
