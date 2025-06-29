#!/usr/bin/env python3
"""
하이브리드 임베딩 테스트

GPU/CPU sentence-transformers 및 OpenAI fallback 테스트
"""

import os
import sys
import time
import logging
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

# 환경변수 로드
from dotenv import load_dotenv
load_dotenv(dotenv_path=os.path.join(backend_dir, ".env"))

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_hybrid_embedding():
    """하이브리드 임베딩 테스트"""
    try:
        logger.info("=== 하이브리드 임베딩 테스트 시작 ===")
        
        # 임베딩 모듈 import
        from core.search.embeddings import (
            embed_documents, 
            log_embedding_status, 
            get_embedding_method,
            GPU_AVAILABLE
        )
        
        # 현재 환경 상태 로깅
        log_embedding_status()
        
        # 테스트 텍스트
        test_texts = [
            "This is a test document for embedding.",
            "Another sample text for vector embedding.",
            "GPU acceleration test for sentence transformers."
        ]
        
        logger.info(f"테스트 텍스트: {len(test_texts)}개")
        
        # 임베딩 생성
        start_time = time.time()
        embeddings = embed_documents(test_texts)
        elapsed = time.time() - start_time
        
        # 결과 검증
        if embeddings:
            logger.info(f"✅ 임베딩 성공: {len(embeddings)}개 벡터, {elapsed:.2f}초")
            logger.info(f"벡터 차원: {len(embeddings[0]) if embeddings else 'N/A'}")
            
            # 첫 번째 벡터의 일부 출력
            if embeddings[0]:
                sample_vector = embeddings[0][:5]  # 첫 5개 값만
                logger.info(f"샘플 벡터 (첫 5개): {sample_vector}")
        else:
            logger.error("❌ 임베딩 실패")
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 테스트 실패: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def test_gpu_specific():
    """GPU 임베딩 직접 테스트"""
    try:
        logger.info("=== GPU 임베딩 직접 테스트 ===")
        
        from core.search.embeddings.embedder_gpu import (
            setup_gpu_embedder,
            embed_documents_gpu,
            GPU_AVAILABLE,
            DEVICE
        )
        
        logger.info(f"GPU 사용 가능: {GPU_AVAILABLE}")
        logger.info(f"디바이스: {DEVICE}")
        
        # GPU 임베더 초기화
        embedder = setup_gpu_embedder()
        if embedder:
            logger.info("✅ sentence-transformers 임베더 초기화 성공")
            
            # 테스트 임베딩
            test_texts = ["GPU test document", "Another test"]
            embeddings = embed_documents_gpu(test_texts)
            
            if embeddings:
                logger.info(f"✅ GPU 임베딩 성공: {len(embeddings)}개 벡터")
                return True
            else:
                logger.error("❌ GPU 임베딩 실패")
                return False
        else:
            logger.warning("⚠️ sentence-transformers 임베더 초기화 실패")
            return False
            
    except Exception as e:
        logger.error(f"❌ GPU 테스트 실패: {e}")
        return False

def test_openai_fallback():
    """OpenAI fallback 테스트"""
    try:
        logger.info("=== OpenAI fallback 테스트 ===")
        
        from core.search.embeddings.embedder import embed_documents as openai_embed
        
        # OpenAI API 키 확인
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.warning("⚠️ OpenAI API 키가 없어 테스트 스킵")
            return True
        
        # 테스트 텍스트
        test_texts = ["OpenAI embedding test document"]
        
        start_time = time.time()
        embeddings = openai_embed(test_texts)
        elapsed = time.time() - start_time
        
        if embeddings:
            logger.info(f"✅ OpenAI 임베딩 성공: {len(embeddings)}개 벡터, {elapsed:.2f}초")
            logger.info(f"벡터 차원: {len(embeddings[0]) if embeddings else 'N/A'}")
            return True
        else:
            logger.error("❌ OpenAI 임베딩 실패")
            return False
            
    except Exception as e:
        logger.error(f"❌ OpenAI 테스트 실패: {e}")
        return False

if __name__ == "__main__":
    logger.info("하이브리드 임베딩 시스템 테스트 시작")
    
    results = []
    
    # 테스트 실행
    results.append(("GPU 직접 테스트", test_gpu_specific()))
    results.append(("OpenAI fallback 테스트", test_openai_fallback()))
    results.append(("하이브리드 임베딩 테스트", test_hybrid_embedding()))
    
    # 결과 요약
    logger.info("=== 테스트 결과 요약 ===")
    for test_name, success in results:
        status = "✅ 성공" if success else "❌ 실패"
        logger.info(f"{test_name}: {status}")
    
    # 전체 결과
    all_passed = all(result[1] for result in results)
    if all_passed:
        logger.info("🎉 모든 테스트 통과!")
    else:
        logger.warning("⚠️ 일부 테스트 실패")
    
    sys.exit(0 if all_passed else 1)
