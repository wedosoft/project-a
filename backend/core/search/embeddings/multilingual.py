"""
다국어 고품질 임베딩 시스템

장기적 글로벌 서비스를 위한 다국어 최적화 임베딩 시스템입니다.
언어별 최적 모델 선택과 품질 최적화를 제공합니다.

프로젝트 규칙 및 가이드라인: /PROJECT_RULES.md 참조
"""

import logging
import asyncio
import time
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class EmbeddingQuality(Enum):
    """임베딩 품질 레벨"""
    ULTRA = "ultra"      # 최고 품질 (text-embedding-3-large)
    HIGH = "high"        # 고품질 (text-embedding-3-small)
    STANDARD = "standard" # 표준 (로컬 모델)


@dataclass
class EmbeddingConfig:
    """임베딩 설정"""
    model_name: str
    dimension: int
    quality: EmbeddingQuality
    cost_per_1k_tokens: float
    languages_optimized: List[str]
    max_tokens: int


# 장기적 다국어 모델 전략
MULTILINGUAL_EMBEDDING_MODELS = {
    # OpenAI 모델 (최고 품질)
    "text-embedding-3-large": EmbeddingConfig(
        model_name="text-embedding-3-large",
        dimension=3072,
        quality=EmbeddingQuality.ULTRA,
        cost_per_1k_tokens=0.00013,
        languages_optimized=["ko", "en", "ja", "zh", "es", "fr", "de"],
        max_tokens=8191
    ),
    
    "text-embedding-3-small": EmbeddingConfig(
        model_name="text-embedding-3-small", 
        dimension=1536,
        quality=EmbeddingQuality.HIGH,
        cost_per_1k_tokens=0.00002,
        languages_optimized=["ko", "en", "ja", "zh", "es", "fr", "de"],
        max_tokens=8191
    ),
    
    # 미래 확장: 다국어 특화 모델들
    "multilingual-e5-large": EmbeddingConfig(
        model_name="intfloat/multilingual-e5-large",
        dimension=1024,
        quality=EmbeddingQuality.STANDARD,
        cost_per_1k_tokens=0.0,  # 로컬 실행
        languages_optimized=["ko", "en", "ja", "zh", "es", "fr", "de", "ru"],
        max_tokens=512
    )
}


class LanguageDetector:
    """고급 언어 감지기"""
    
    def __init__(self):
        self.language_patterns = {
            "ko": r'[가-힣]',
            "ja": r'[ひらがなカタカナ]|[一-龯]',
            "zh": r'[一-龯]',
            "en": r'[a-zA-Z]'
        }
    
    async def detect_language(self, text: str) -> str:
        """텍스트 언어 감지"""
        import re
        
        if not text or len(text.strip()) < 3:
            return "en"  # 기본값
        
        # 간단한 패턴 기반 감지
        korean_chars = len(re.findall(r'[가-힣]', text))
        japanese_chars = len(re.findall(r'[ひらがなカタカナ]', text))
        chinese_chars = len(re.findall(r'[一-龯]', text))
        english_chars = len(re.findall(r'[a-zA-Z]', text))
        
        total_chars = korean_chars + japanese_chars + chinese_chars + english_chars
        if total_chars == 0:
            return "en"
        
        # 비율 기반 판단
        if korean_chars / len(text) > 0.3:
            return "ko"
        elif japanese_chars / len(text) > 0.2:
            return "ja"
        elif chinese_chars / len(text) > 0.3:
            return "zh"
        elif english_chars / len(text) > 0.5:
            return "en"
        else:
            return "multilingual"  # 혼합 언어


class MultilingualEmbedder:
    """다국어 최적화 임베딩 시스템"""
    
    def __init__(self, 
                 quality_level: EmbeddingQuality = EmbeddingQuality.ULTRA,
                 fallback_enabled: bool = True):
        self.quality_level = quality_level
        self.fallback_enabled = fallback_enabled
        self.language_detector = LanguageDetector()
        
        # 품질 레벨별 모델 선택
        self.primary_model = self._select_primary_model()
        self.fallback_model = self._select_fallback_model()
        
        logger.info(f"다국어 임베딩 시스템 초기화: {self.primary_model}, fallback: {self.fallback_model}")
    
    def _select_primary_model(self) -> str:
        """품질 레벨에 따른 주 모델 선택"""
        if self.quality_level == EmbeddingQuality.ULTRA:
            return "text-embedding-3-large"
        elif self.quality_level == EmbeddingQuality.HIGH:
            return "text-embedding-3-small"
        else:
            return "multilingual-e5-large"
    
    def _select_fallback_model(self) -> str:
        """폴백 모델 선택 (같은 모델 사용하여 차원 일관성 유지)"""
        return self.primary_model  # 같은 모델 사용, 토큰만 더 적극적으로 자름
    
    async def embed_documents_optimized(self, 
                                      texts: List[str],
                                      force_language: Optional[str] = None) -> List[List[float]]:
        """
        다국어 최적화 임베딩 생성
        
        Args:
            texts: 임베딩할 텍스트 리스트
            force_language: 강제 언어 설정 (자동 감지 무시)
            
        Returns:
            통일된 차원의 임베딩 벡터 리스트
        """
        if not texts:
            return []
        
        start_time = time.time()
        target_config = MULTILINGUAL_EMBEDDING_MODELS[self.primary_model]
        
        logger.info(f"다국어 임베딩 시작: {len(texts)}개 문서, 모델: {self.primary_model}, 목표 차원: {target_config.dimension}")
        
        try:
            # 언어별 배치 처리
            language_batches = await self._group_by_language(texts, force_language)
            
            # 병렬 처리로 성능 최적화
            all_embeddings = []
            tasks = []
            
            for language, batch_texts in language_batches.items():
                task = self._process_language_batch(language, batch_texts, target_config)
                tasks.append(task)
            
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 결과 병합 (원래 순서 유지)
            text_to_embedding = {}
            for batch_result in batch_results:
                if isinstance(batch_result, dict):
                    text_to_embedding.update(batch_result)
                elif isinstance(batch_result, Exception):
                    logger.error(f"배치 처리 오류: {batch_result}")
            
            # 원래 순서로 재정렬
            for text in texts:
                if text in text_to_embedding:
                    all_embeddings.append(text_to_embedding[text])
                else:
                    # 폴백: 개별 처리
                    logger.warning(f"배치 처리 실패한 텍스트 개별 처리: {text[:50]}...")
                    embedding = await self._embed_single_text(text, target_config)
                    all_embeddings.append(embedding)
            
            elapsed = time.time() - start_time
            logger.info(f"다국어 임베딩 완료: {len(all_embeddings)}개, 차원: {target_config.dimension}, {elapsed:.2f}초")
            
            return all_embeddings
            
        except Exception as e:
            logger.error(f"다국어 임베딩 실패: {e}")
            # 단순 폴백
            return await self._fallback_embedding(texts)
    
    async def _group_by_language(self, 
                               texts: List[str], 
                               force_language: Optional[str] = None) -> Dict[str, List[str]]:
        """언어별 텍스트 그룹화"""
        if force_language:
            return {force_language: texts}
        
        language_batches = {}
        
        for text in texts:
            language = await self.language_detector.detect_language(text)
            if language not in language_batches:
                language_batches[language] = []
            language_batches[language].append(text)
        
        logger.debug(f"언어별 배치: {[(lang, len(batch)) for lang, batch in language_batches.items()]}")
        return language_batches
    
    async def _process_language_batch(self, 
                                    language: str, 
                                    texts: List[str], 
                                    config: EmbeddingConfig) -> Dict[str, List[float]]:
        """언어별 배치 처리"""
        try:
            # 언어별 전처리
            processed_texts = [self._preprocess_text(text, language) for text in texts]
            
            # OpenAI API 호출 (다국어 모델 사용)
            from .embedder import embed_documents_with_model
            embeddings = embed_documents_with_model(processed_texts, config.model_name)
            
            if not embeddings or len(embeddings) != len(texts):
                raise ValueError(f"임베딩 결과 불일치: {len(embeddings) if embeddings else 0}/{len(texts)}")
            
            # 차원 검증 및 정규화
            validated_embeddings = []
            for embedding in embeddings:
                if len(embedding) != config.dimension:
                    logger.warning(f"차원 불일치: {len(embedding)} != {config.dimension}")
                    # 차원 조정 (패딩/트렁케이션 대신 오류 처리)
                    raise ValueError(f"임베딩 차원 불일치: {len(embedding)} != {config.dimension}")
                validated_embeddings.append(embedding)
            
            # 텍스트-임베딩 매핑 반환
            return {text: embedding for text, embedding in zip(texts, validated_embeddings)}
            
        except Exception as e:
            logger.error(f"언어 '{language}' 배치 처리 실패: {e}")
            raise
    
    def _preprocess_text(self, text: str, language: str) -> str:
        """언어별 텍스트 전처리"""
        if not text:
            return ""
        
        # 기본 정리
        cleaned = text.strip()
        
        # 언어별 특수 처리
        if language == "ko":
            # 한국어 특수 문자 정리
            import re
            cleaned = re.sub(r'[^\w\s가-힣]', ' ', cleaned)
        elif language == "ja":
            # 일본어 특수 처리
            pass
        elif language == "zh":
            # 중국어 특수 처리  
            pass
        
        return cleaned
    
    async def _embed_single_text(self, text: str, config: EmbeddingConfig) -> List[float]:
        """단일 텍스트 임베딩 (폴백용)"""
        try:
            from .embedder import embed_documents_with_model
            embeddings = embed_documents_with_model([text], config.model_name)
            
            if embeddings and len(embeddings) == 1:
                embedding = embeddings[0]
                # 차원 검증
                if len(embedding) != config.dimension:
                    logger.error(f"단일 텍스트 임베딩 차원 불일치: {len(embedding)} != {config.dimension}")
                    return [0.0] * config.dimension
                return embedding
            else:
                raise ValueError("단일 텍스트 임베딩 실패")
                
        except Exception as e:
            logger.error(f"단일 텍스트 임베딩 실패: {e}")
            # 최종 폴백: 0 벡터
            return [0.0] * config.dimension
    
    async def _fallback_embedding(self, texts: List[str]) -> List[List[float]]:
        """최종 폴백 임베딩 (같은 모델, 더 짧은 텍스트)"""
        logger.warning("최종 폴백 임베딩 실행")
        
        try:
            # 텍스트를 더 적극적으로 자름 (토큰 제한의 50%만 사용)
            from .embedder import embed_documents_with_model
            config = MULTILINGUAL_EMBEDDING_MODELS[self.primary_model]
            max_tokens = 4000  # 8191의 절반 정도로 제한
            
            # 텍스트 자르기
            truncated_texts = []
            for text in texts:
                if len(text) > max_tokens * 3:  # 대략적인 문자-토큰 비율
                    truncated_text = text[:max_tokens * 3] + "..."
                    logger.warning(f"폴백에서 텍스트 자름: {len(text)} -> {len(truncated_text)} 문자")
                    truncated_texts.append(truncated_text)
                else:
                    truncated_texts.append(text)
            
            embeddings = embed_documents_with_model(truncated_texts, config.model_name)
            
            if embeddings:
                # 차원 검증
                for i, embedding in enumerate(embeddings):
                    if len(embedding) != config.dimension:
                        logger.error(f"폴백 임베딩 차원 불일치: {len(embedding)} != {config.dimension}")
                        embeddings[i] = [0.0] * config.dimension
                
                return embeddings
            else:
                raise ValueError("폴백 임베딩도 실패")
                
        except Exception as e:
            logger.error(f"폴백 임베딩도 실패: {e}")
            # 0 벡터 반환
            config = MULTILINGUAL_EMBEDDING_MODELS[self.primary_model]
            return [[0.0] * config.dimension for _ in texts]


# 전역 인스턴스 (싱글톤)
_multilingual_embedder = None


def get_multilingual_embedder(quality_level: EmbeddingQuality = EmbeddingQuality.ULTRA) -> MultilingualEmbedder:
    """다국어 임베딩 시스템 싱글톤 인스턴스"""
    global _multilingual_embedder
    if _multilingual_embedder is None:
        _multilingual_embedder = MultilingualEmbedder(quality_level)
    return _multilingual_embedder


async def embed_documents_multilingual(texts: List[str], 
                                     quality: EmbeddingQuality = EmbeddingQuality.ULTRA,
                                     force_language: Optional[str] = None) -> List[List[float]]:
    """
    다국어 최적화 임베딩 생성 (메인 함수)
    
    Args:
        texts: 임베딩할 텍스트 리스트
        quality: 품질 레벨 (ULTRA, HIGH, STANDARD)
        force_language: 강제 언어 설정
        
    Returns:
        통일된 차원의 임베딩 벡터 리스트
    """
    embedder = get_multilingual_embedder(quality)
    return await embedder.embed_documents_optimized(texts, force_language)