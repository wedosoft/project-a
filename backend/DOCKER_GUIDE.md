# Docker 환경별 실행 가이드

## 🎯 자동 환경 감지 (권장)

```bash
# 환경을 자동 감지하여 최적 설정으로 실행
./scripts/smart-docker-start.sh

# 백그라운드 실행
./scripts/smart-docker-start.sh -d
```

## 🛠 수동 환경 선택

### 1. 로컬 개발 (macOS)
```bash
# Apple Silicon MPS 지원, hot reload
docker-compose -f docker-compose.yml -f docker-compose.local.yml up
```

### 2. AWS EC2 배포
```bash
# EC2 최적화, 헬스체크 포함
docker-compose -f docker-compose.yml -f docker-compose.aws.yml up -d
```

### 3. EC2 GPU 인스턴스
```bash
# NVIDIA GPU 전용 (g4dn, g5, p3 등)
docker-compose -f docker-compose.gpu.yml up -d
```

### 4. 기본 설정 (어디서나)
```bash
# 기본 CPU 모드
docker-compose up
```

## 🔍 환경별 특징

| 환경 | GPU 지원 | 설정 파일 | 특징 |
|------|---------|-----------|------|
| **로컬 macOS** | MPS | `docker-compose.local.yml` | Hot reload, 디버그 모드 |
| **AWS EC2** | 자동감지 | `docker-compose.aws.yml` | 헬스체크, 프로덕션 최적화 |
| **EC2 GPU** | CUDA | `docker-compose.gpu.yml` | NVIDIA GPU 전용 |
| **기본** | CPU | `docker-compose.yml` | 범용 호환성 |

## 🚀 GPU 가속 확인

```bash
# 컨테이너 내에서 GPU 상태 확인
docker exec project-a python -c "
from core.search.embeddings import log_embedding_status
log_embedding_status()
"

# NVIDIA GPU 상태 (GPU 인스턴스만)
docker exec project-a nvidia-smi
```

## 🔧 트러블슈팅

### 문제: `unknown runtime name: nvidia`
**원인**: NVIDIA Docker runtime 미설치
**해결**: 
```bash
# Ubuntu/Debian
sudo apt-get install nvidia-docker2
sudo systemctl restart docker

# Amazon Linux 2
sudo yum install nvidia-docker2
sudo systemctl restart docker
```

### 문제: MPS 가속 안됨 (macOS)
**원인**: PyTorch MPS 지원 버전 필요
**해결**: 
```bash
pip install torch>=1.12.0
```

### 문제: 임베딩 속도 느림
**확인**: 
1. GPU 감지 상태: `log_embedding_status()`
2. 환경변수: `USE_GPU_FIRST=true`
3. 메모리 사용량: `nvidia-smi` (GPU) 또는 `htop` (CPU)

## 📊 성능 비교

| 환경 | 임베딩 속도 | 메모리 | 비용 |
|------|-------------|--------|------|
| **EC2 GPU (g4dn.xlarge)** | ~30x | 16GB VRAM | $$$ |
| **Apple Silicon MPS** | ~5x | 공유 메모리 | 개발용 |
| **EC2 CPU (c5.xlarge)** | 1x | 8GB RAM | $$ |
| **OpenAI API** | ∞ | 0GB | $/token |

## 🎯 권장 사용법

### 개발 단계
```bash
./scripts/smart-docker-start.sh  # 자동 감지
```

### 프로덕션 배포
```bash
# EC2 GPU 인스턴스
docker-compose -f docker-compose.gpu.yml up -d

# EC2 CPU 인스턴스  
docker-compose -f docker-compose.aws.yml up -d
```