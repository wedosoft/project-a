# 🏗️ 중앙집중식 설정 관리 시스템 가이드

이 가이드는 개발 환경에서 클라우드 배포까지 일관되고 안전한 설정 관리 방법을 제공합니다.

## 🎯 개요

### 문제점
- ❌ 환경변수와 YAML 파일이 여러 곳에 분산
- ❌ 개발/스테이징/프로덕션 환경별 설정 불일치
- ❌ 민감한 정보 평문 저장
- ❌ 설정 변경 시 수동 동기화 필요

### 해결책
- ✅ 중앙집중식 설정 관리
- ✅ 환경별 자동 설정 적용
- ✅ 민감 정보 암호화 저장
- ✅ 자동 동기화 및 검증

## 🏗️ 시스템 아키텍처

```
개발 환경                클라우드 환경
┌─────────────────┐     ┌─────────────────┐
│ YAML 파일       │────▶│ AWS Secrets     │
│ 환경변수        │     │ K8s ConfigMap   │
│                 │     │ Azure KeyVault  │
└─────────────────┘     └─────────────────┘
         │                       │
         ▼                       ▼
┌─────────────────────────────────────────┐
│      중앙집중 설정 관리자               │
│  ┌─────────────┬─────────────────────┐  │
│  │ 보안 관리자 │ 동기화 & 검증 도구  │  │
│  └─────────────┴─────────────────────┘  │
└─────────────────────────────────────────┘
```

## 📁 디렉토리 구조

```
backend/core/llm/config/
├── centralized/                    # 중앙 집중 설정
│   ├── model_registry.yaml         # 모델 레지스트리
│   ├── environment_configs.yaml    # 환경별 설정
│   └── secrets_template.yaml       # 보안 정보 템플릿
├── centralized_config.py          # 중앙 설정 관리자
├── security_manager.py            # 보안 관리자
└── environments/                   # 환경별 설정 (레거시)

scripts/
├── deploy/
│   ├── aws_deploy.py              # AWS 배포 스크립트
│   └── k8s_deploy.py              # Kubernetes 배포 스크립트
└── config_sync_validator.py       # 동기화 검증 도구
```

## 🚀 사용 방법

### 1. 로컬 개발 환경 설정

#### 환경변수 설정
```bash
# 기본 배포 환경
export DEPLOYMENT_ENVIRONMENT=local

# API 키 설정 (개발용)
export OPENAI_API_KEY=sk-dev-your-key
export ANTHROPIC_API_KEY=ant-dev-your-key
export GEMINI_API_KEY=your-gemini-dev-key

# LLM 모델 오버라이드 (선택사항)
export SUMMARIZATION_MODEL_PROVIDER=gemini
export SUMMARIZATION_MODEL_NAME=gemini-1.5-flash
export CHAT_MODEL_PROVIDER=anthropic
export CHAT_MODEL_NAME=claude-3-5-haiku-20241022
```

#### 코드에서 사용
```python
from backend.core.llm.config.centralized_config import get_centralized_config_manager

# 설정 관리자 초기화
config_manager = get_centralized_config_manager()

# 설정 조회
model_registry = await config_manager.get_config("model_registry")
environment_configs = await config_manager.get_config("environment_configs")

# 현재 환경의 기본 모델 가져오기
current_env = environment_configs['deployment_environments']['local']
default_provider = current_env['default_provider']
default_model = current_env['default_chat_model']

print(f"사용할 모델: {default_provider}:{default_model}")
```

### 2. AWS 클라우드 배포

#### AWS Secrets Manager 배포
```bash
# AWS 계정 설정
export AWS_REGION=us-east-1
export AWS_PROFILE=your-profile

# 개발 환경 배포
python scripts/deploy/aws_deploy.py \
  --region us-east-1 \
  --environment dev \
  --output-dir ./aws-configs

# 프로덕션 환경 배포
python scripts/deploy/aws_deploy.py \
  --region us-east-1 \
  --environment prod \
  --output-dir ./aws-configs
```

#### 애플리케이션 환경변수 설정
```bash
# AWS 배포 환경
export DEPLOYMENT_ENVIRONMENT=aws
export AWS_REGION=us-east-1
export ENVIRONMENT=prod

# Secrets Manager 설정은 자동으로 로드됨
# API 키는 Secrets Manager에서 자동 조회
```

#### Docker Compose 예시
```yaml
# docker-compose.aws.yml
version: '3.8'
services:
  llm-application:
    image: llm-application:latest
    environment:
      DEPLOYMENT_ENVIRONMENT: aws
      AWS_REGION: us-east-1
      ENVIRONMENT: prod
    env_file:
      - .env.aws  # aws_deploy.py에서 생성된 파일
    depends_on:
      - qdrant
    networks:
      - llm-network
```

### 3. Kubernetes 배포

#### ConfigMap과 Secret 배포
```bash
# Kubernetes 배포
export K8S_NAMESPACE=llm-prod

python scripts/deploy/k8s_deploy.py \
  --namespace llm-prod \
  --environment prod \
  --output-dir ./k8s-configs

# 생성된 YAML 적용
kubectl apply -f k8s-configs/rbac.yaml
kubectl apply -f k8s-configs/deployment.yaml
```

#### Kubernetes Manifest 예시
```yaml
# k8s-configs/deployment.yaml (자동 생성됨)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: llm-application-prod
  namespace: llm-prod
spec:
  replicas: 3
  template:
    spec:
      containers:
      - name: llm-application
        image: llm-application:latest
        env:
        - name: DEPLOYMENT_ENVIRONMENT
          value: "kubernetes"
        - name: K8S_NAMESPACE
          value: "llm-prod"
        - name: OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: llm-secrets-template-prod
              key: OPENAI_PROD_KEY_API_KEY
        volumeMounts:
        - name: model-registry-config
          mountPath: /etc/llm/config/model_registry.yaml
          subPath: model_registry.yaml
          readOnly: true
      volumes:
      - name: model-registry-config
        configMap:
          name: llm-model-registry-prod
```

### 4. 설정 동기화 및 검증

#### 동기화 상태 확인
```bash
# 일회성 검증
python scripts/config_sync_validator.py \
  --environment prod \
  --output-file validation_report.json

# 지속적인 모니터링
python scripts/config_sync_validator.py \
  --environment prod \
  --watch \
  --watch-interval 300

# 백업 생성
python scripts/config_sync_validator.py \
  --environment prod \
  --backup-dir ./config-backups
```

#### 검증 결과 예시
```
🔍 설정 동기화 검증 보고서
============================================================
검증 일시: 2024-07-04T10:30:00
환경: prod

📊 요약:
  총 설정: 9개
  로컬 설정: 3개
  AWS 설정: 6개
  K8s 설정: 0개

🔄 동기화 상태:
  ✅ 동기화됨: 6개
  ❌ 불일치: 0개
  ⚠️  누락: 0개
  🚨 검증 오류: 0개
```

## 🔐 보안 관리

### 민감 정보 암호화
```python
from backend.core.llm.config.security_manager import get_secure_config_manager
from backend.core.llm.config.security_manager import SecurityLevel

# 보안 관리자 초기화
security_manager = get_secure_config_manager()

# 민감 데이터 암호화
sensitive_config = {
    "api_keys": {
        "openai": {"prod_key": "sk-real-production-key"},
        "anthropic": {"prod_key": "ant-real-production-key"}
    }
}

encrypted_config = security_manager.encrypt_sensitive_data(
    sensitive_config, 
    SecurityLevel.SECRET
)

# 암호화된 데이터는 안전하게 저장
print(encrypted_config)
# {
#   "api_keys": {
#     "openai": {"prod_key": "ENC[gAAAAABh...]"},
#     "anthropic": {"prod_key": "ENC[gAAAAABh...]"}
#   },
#   "_encryption_metadata": {...}
# }
```

### 접근 권한 제어
```python
# 사용자 역할 설정
export LLM_USER_ROLE=admin  # admin, developer, readonly

# 권한 확인
if security_manager.check_access_permission("api_keys", "read"):
    # API 키 조회 허용
    decrypted_config = security_manager.decrypt_sensitive_data(encrypted_config)
else:
    # 접근 거부
    print("접근 권한이 없습니다")
```

### 시크릿 로테이션
```bash
# API 키 로테이션 (시뮬레이션)
python -c "
from backend.core.llm.config.security_manager import get_secure_config_manager
manager = get_secure_config_manager()
result = manager.rotate_secrets('api_keys')
print(result)
"
```

## 🛠️ 환경별 설정 관리

### 환경 정의
```yaml
# environment_configs.yaml
deployment_environments:
  local:          # 로컬 개발
    default_provider: "gemini"
    default_chat_model: "gemini-1.5-flash"
    cost_limit: "low"
    
  aws_dev:        # AWS 개발 환경
    default_provider: "anthropic"
    default_chat_model: "claude-3-5-haiku-20241022"
    cost_limit: "medium"
    
  aws_prod:       # AWS 프로덕션
    default_provider: "anthropic"
    default_chat_model: "claude-3-sonnet-20240229"
    cost_limit: "high"
    
  kubernetes:     # Kubernetes 환경
    default_provider: "anthropic"
    default_chat_model: "claude-3-5-haiku-20241022"
    cost_limit: "medium"
```

### 환경별 모델 오버라이드
```yaml
# AWS 프로덕션 환경의 모델 오버라이드
aws_prod:
  model_overrides:
    summarization:
      provider: "anthropic"
      model: "claude-3-5-haiku-20241022"
      reason: "프로덕션 - 속도 최적화"
    
    analysis:
      provider: "anthropic"
      model: "claude-3-opus-20240229"
      reason: "프로덕션 - 최고 품질"
```

## 📊 모니터링 및 알림

### 헬스체크
```python
# 설정 소스들의 상태 확인
health_status = await config_manager.health_check()
print(health_status)
# {
#   "yaml_file": True,
#   "aws_secrets_manager": True,
#   "kubernetes_configmap": False
# }
```

### 메트릭 수집
```python
# 보안 상태 요약
security_status = security_manager.get_security_status()
print(security_status)
# {
#   "security_level": "HIGH",
#   "failed_attempts_24h": 0,
#   "expiring_secrets": [],
#   "encryption_enabled": True
# }
```

## 🔧 문제해결

### 자주 발생하는 문제들

#### 1. 설정 불일치
```bash
# 문제: 로컬과 클라우드 설정이 다름
# 해결: 동기화 도구로 차이점 확인
python scripts/config_sync_validator.py --environment prod

# 차이점이 발견되면 수동으로 동기화하거나 재배포
python scripts/deploy/aws_deploy.py --environment prod
```

#### 2. 암호화 키 분실
```bash
# 문제: 마스터 키를 잃어버림
# 해결: 백업에서 복원하거나 새 키로 재암호화
export CONFIG_MASTER_KEY=new-master-key
python -c "
from backend.core.llm.config.security_manager import SecureConfigManager
manager = SecureConfigManager()
# 데이터 재암호화 로직...
"
```

#### 3. 권한 오류
```bash
# 문제: 설정 접근 권한 없음
# 해결: 사용자 역할 확인 및 설정
export LLM_USER_ROLE=admin
export CLIENT_IP=127.0.0.1
```

### 디버깅 팁

#### 로그 활성화
```bash
export LOG_LEVEL=DEBUG
python your_application.py
```

#### 설정 소스 우선순위 확인
```python
# 설정 소스들의 우선순위 확인
priority_info = config_manager.get_source_priority()
print(priority_info)
# [
#   {"source": "environment_vars", "priority": 1, "enabled": True},
#   {"source": "aws_secrets_manager", "priority": 2, "enabled": True}
# ]
```

## 🔄 마이그레이션 가이드

### 기존 시스템에서 이전

#### 1단계: 현재 설정 백업
```bash
# 기존 환경변수와 설정 파일 백업
env > current_env_backup.txt
cp -r config/ config_backup/
```

#### 2단계: 중앙집중 설정으로 변환
```python
# 기존 설정을 중앙집중 형태로 변환
from backend.core.llm.config.centralized_config import get_centralized_config_manager

# 기존 설정 로드
old_config = load_old_config()

# 새 형태로 변환
new_config = convert_to_centralized_format(old_config)

# 새 시스템에 저장
config_manager = get_centralized_config_manager()
await config_manager.set_config("model_registry", new_config)
```

#### 3단계: 점진적 적용
```python
# 기존 코드 (점진적으로 변경)
if use_new_config_system:
    provider, model = get_model_from_centralized_config(use_case)
else:
    provider, model = get_model_from_old_config(use_case)
```

## 📚 추가 자료

### API 문서
- [중앙집중 설정 관리자 API](./backend/core/llm/config/centralized_config.py)
- [보안 관리자 API](./backend/core/llm/config/security_manager.py)
- [동기화 검증 도구 API](./scripts/config_sync_validator.py)

### 클라우드별 가이드
- [AWS 배포 가이드](./scripts/deploy/aws_deploy.py)
- [Kubernetes 배포 가이드](./scripts/deploy/k8s_deploy.py)

### 보안 베스트 프랙티스
1. **마스터 키 관리**: 환경변수나 전용 키 관리 서비스 사용
2. **접근 제어**: 최소 권한 원칙 적용
3. **감사 로깅**: 모든 설정 변경 기록
4. **정기 로테이션**: API 키 등 민감 정보 정기 교체
5. **백업 및 복원**: 정기적인 설정 백업 및 무결성 검증

---

이제 여러분의 설정 관리 시스템은 **개발부터 프로덕션까지 완전히 중앙화되고 보안이 강화된** 시스템이 되었습니다! 🎉