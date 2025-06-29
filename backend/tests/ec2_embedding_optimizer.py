#!/usr/bin/env python3
"""
EC2 환경 감지 및 임베딩 최적화 테스트

다양한 EC2 인스턴스 타입에서의 임베딩 동작을 시뮬레이션
"""

import os
import platform
import subprocess
import sys
from pathlib import Path

def detect_ec2_environment():
    """EC2 환경 정보를 감지합니다."""
    info = {
        "platform": platform.system(),
        "architecture": platform.machine(),
        "python_version": sys.version,
        "is_ec2": False,
        "instance_type": "unknown",
        "gpu_available": False,
        "mps_available": False
    }
    
    # EC2 메타데이터 확인
    try:
        result = subprocess.run(
            ["curl", "-s", "--connect-timeout", "2", 
             "http://169.254.169.254/latest/meta-data/instance-type"],
            capture_output=True, text=True, timeout=3
        )
        if result.returncode == 0 and result.stdout:
            info["is_ec2"] = True
            info["instance_type"] = result.stdout.strip()
    except:
        pass
    
    # GPU 감지
    try:
        import torch
        info["gpu_available"] = torch.cuda.is_available()
        if hasattr(torch.backends, 'mps'):
            info["mps_available"] = torch.backends.mps.is_available()
    except ImportError:
        pass
    
    return info

def get_recommended_embedding_strategy(env_info):
    """환경에 따른 권장 임베딩 전략을 반환합니다."""
    
    if env_info["gpu_available"]:
        return {
            "method": "cuda",
            "description": "NVIDIA GPU 가속 임베딩",
            "performance": "최고",
            "cost": "높음 (GPU 인스턴스)",
            "use_case": "대용량 배치 처리, 실시간 고성능"
        }
    
    elif env_info["mps_available"]:
        return {
            "method": "mps", 
            "description": "Apple Silicon MPS 가속",
            "performance": "높음",
            "cost": "중간",
            "use_case": "Mac 기반 개발/테스트 환경"
        }
    
    elif env_info["is_ec2"]:
        # EC2 인스턴스 타입별 최적화
        instance_type = env_info["instance_type"]
        
        if instance_type.startswith(('c5', 'c6i')):  # Compute Optimized
            return {
                "method": "cpu",
                "description": "CPU 최적화 sentence-transformers", 
                "performance": "높음",
                "cost": "중간",
                "use_case": "CPU 집약적 워크로드"
            }
        
        elif instance_type.startswith(('t3', 't4g')):  # Burstable
            return {
                "method": "openai",
                "description": "OpenAI API (CPU 절약)",
                "performance": "중간",
                "cost": "낮음 (인스턴스) + API 비용",
                "use_case": "소규모 처리, 간헐적 사용"
            }
        
        elif instance_type.startswith('m'):  # General Purpose
            return {
                "method": "cpu",
                "description": "CPU sentence-transformers",
                "performance": "중간",
                "cost": "중간",
                "use_case": "일반적인 프로덕션 환경"
            }
    
    # 기본값: 로컬 환경
    return {
        "method": "cpu",
        "description": "CPU sentence-transformers",
        "performance": "중간",
        "cost": "낮음",
        "use_case": "개발 환경, 소규모 처리"
    }

def main():
    """EC2 환경 분석 및 권장사항 출력"""
    print("🔍 EC2 환경 분석 및 임베딩 최적화 가이드\n")
    
    # 환경 감지
    env_info = detect_ec2_environment()
    
    print("📊 환경 정보:")
    print(f"  플랫폼: {env_info['platform']} {env_info['architecture']}")
    print(f"  EC2 여부: {'Yes' if env_info['is_ec2'] else 'No'}")
    if env_info['is_ec2']:
        print(f"  인스턴스 타입: {env_info['instance_type']}")
    print(f"  GPU 사용 가능: {env_info['gpu_available']}")
    print(f"  MPS 사용 가능: {env_info['mps_available']}")
    
    # 권장 전략
    strategy = get_recommended_embedding_strategy(env_info)
    
    print(f"\n🎯 권장 임베딩 전략:")
    print(f"  방법: {strategy['method'].upper()}")
    print(f"  설명: {strategy['description']}")
    print(f"  성능: {strategy['performance']}")
    print(f"  비용: {strategy['cost']}")
    print(f"  적용 사례: {strategy['use_case']}")
    
    # 환경변수 권장사항
    print(f"\n⚙️ 권장 환경변수 설정:")
    if strategy['method'] == 'cuda':
        print("  USE_GPU_FIRST=true")
        print("  GPU_FALLBACK_TO_OPENAI=true")
    elif strategy['method'] in ['cpu', 'mps']:
        print("  USE_GPU_FIRST=true")
        print("  GPU_FALLBACK_TO_OPENAI=true")
    else:
        print("  USE_GPU_FIRST=false")
        print("  GPU_FALLBACK_TO_OPENAI=true")
    
    print(f"\n✅ 현재 하이브리드 임베딩 시스템은 이 환경에서 자동으로 최적화됩니다!")

if __name__ == "__main__":
    main()
