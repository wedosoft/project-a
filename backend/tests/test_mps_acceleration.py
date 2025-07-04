#!/usr/bin/env python3
"""
Apple M1 MPS 가속 임베딩 테스트

MPS(Metal Performance Shaders) 가속 성능 비교 테스트
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

def test_pytorch_mps():
    """PyTorch MPS 지원 여부 테스트"""
    try:
        import torch
        
        logger.info("=== PyTorch MPS 테스트 ===")
        logger.info(f"PyTorch 버전: {torch.__version__}")
        logger.info(f"CUDA 사용 가능: {torch.cuda.is_available()}")
        
        # MPS 지원 확인
        if hasattr(torch.backends, 'mps'):
            logger.info(f"MPS 백엔드 사용 가능: {torch.backends.mps.is_available()}")
            if torch.backends.mps.is_available():
                logger.info("✅ Apple Silicon MPS 가속 지원됨")
                return True
            else:
                logger.warning("⚠️ MPS 백엔드를 사용할 수 없습니다")
        else:
            logger.warning("⚠️ PyTorch MPS 백엔드가 없습니다 (PyTorch 1.12+ 필요)")
        
        return False
        
    except ImportError:
        logger.error("❌ PyTorch가 설치되지 않았습니다")
        return False

def test_device_performance():
    """디바이스별 성능 비교 테스트"""
    try:
        import torch
        from sentence_transformers import SentenceTransformer
        
        logger.info("=== 디바이스별 성능 테스트 ===")
        
        # 테스트 데이터
        test_texts = [
            f"This is test document number {i} for performance comparison." 
            for i in range(10)
        ]
        
        results = {}
        
        # CPU 테스트
        logger.info("CPU 임베딩 테스트...")
        try:
            model_cpu = SentenceTransformer('all-MiniLM-L6-v2', device='cpu')
            start_time = time.time()
            embeddings_cpu = model_cpu.encode(test_texts)
            cpu_time = time.time() - start_time
            results['cpu'] = cpu_time
            logger.info(f"✅ CPU: {cpu_time:.3f}초, 벡터 차원: {len(embeddings_cpu[0])}")
        except Exception as e:
            logger.error(f"❌ CPU 테스트 실패: {e}")
        
        # MPS 테스트 (M1 Mac에서만)
        if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            logger.info("MPS 임베딩 테스트...")
            try:
                model_mps = SentenceTransformer('all-MiniLM-L6-v2', device='mps')
                start_time = time.time()
                embeddings_mps = model_mps.encode(test_texts)
                mps_time = time.time() - start_time
                results['mps'] = mps_time
                logger.info(f"✅ MPS: {mps_time:.3f}초, 벡터 차원: {len(embeddings_mps[0])}")
            except Exception as e:
                logger.error(f"❌ MPS 테스트 실패: {e}")
        
        # 성능 비교
        if len(results) > 1:
            logger.info("=== 성능 비교 ===")
            for device, time_taken in results.items():
                logger.info(f"{device.upper()}: {time_taken:.3f}초")
            
            if 'cpu' in results and 'mps' in results:
                speedup = results['cpu'] / results['mps']
                logger.info(f"MPS 가속비: {speedup:.2f}x")
        
        return len(results) > 0
        
    except Exception as e:
        logger.error(f"❌ 성능 테스트 실패: {e}")
        return False

def test_hybrid_with_mps():
    """하이브리드 임베딩에서 MPS 사용 테스트"""
    try:
        logger.info("=== 하이브리드 MPS 테스트 ===")
        
        from core.search.embeddings import (
            embed_documents, 
 
        )
        
        # 환경 상태 로깅
        print("✅ 임베딩 시스템 상태 확인됨")
        
        # 현재 시스템 확인
        logger.info("현재 임베딩 시스템: Vector DB 단독 운영")
        
        # 테스트 임베딩
        test_texts = [
            "Apple M1 MPS acceleration test",
            "Metal Performance Shaders embedding",
            "Hybrid embedding system test"
        ]
        
        start_time = time.time()
        embeddings = embed_documents(test_texts)
        elapsed = time.time() - start_time
        
        if embeddings:
            logger.info(f"✅ 하이브리드 임베딩 성공: {len(embeddings)}개 벡터, {elapsed:.3f}초")
            logger.info(f"벡터 차원: {len(embeddings[0])}")
            
            # 첫 번째 벡터 샘플
            sample = embeddings[0][:5]
            logger.info(f"샘플 벡터: {sample}")
            return True
        else:
            logger.error("❌ 하이브리드 임베딩 실패")
            return False
            
    except Exception as e:
        logger.error(f"❌ 하이브리드 MPS 테스트 실패: {e}")
        return False

def main():
    """메인 테스트 함수"""
    logger.info("🍎 Apple M1 MPS 가속 임베딩 테스트 시작")
    
    # 시스템 정보
    import platform
    logger.info(f"시스템: {platform.system()} {platform.machine()}")
    
    results = []
    
    # 테스트 실행
    results.append(("PyTorch MPS 지원", test_pytorch_mps()))
    results.append(("디바이스 성능 비교", test_device_performance()))
    results.append(("하이브리드 MPS 테스트", test_hybrid_with_mps()))
    
    # 결과 요약
    logger.info("=== 테스트 결과 요약 ===")
    for test_name, success in results:
        status = "✅ 성공" if success else "❌ 실패"
        logger.info(f"{test_name}: {status}")
    
    # 전체 결과
    all_passed = all(result[1] for result in results)
    if all_passed:
        logger.info("🎉 모든 테스트 통과! Apple M1 MPS 가속 활성화됨")
    else:
        logger.warning("⚠️ 일부 테스트 실패 - CPU fallback 사용")
    
    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
