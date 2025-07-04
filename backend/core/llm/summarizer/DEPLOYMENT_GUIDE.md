# 🚀 Anthropic 프롬프트 엔지니어링 시스템 배포 가이드

> **운영 환경 배포를 위한 종합 가이드**
> 
> 개발에서 운영까지 안전하고 효율적인 배포 절차와 운영 방안을 제공합니다.

## 📋 목차

- [📋 배포 전 체크리스트](#-배포-전-체크리스트)
- [🏗️ 환경별 배포 절차](#️-환경별-배포-절차)
- [⚙️ 환경변수 설정](#️-환경변수-설정)
- [🔒 보안 구성](#-보안-구성)
- [📊 모니터링 설정](#-모니터링-설정)
- [🔄 롤백 절차](#-롤백-절차)
- [📈 성능 튜닝](#-성능-튜닝)
- [🛠️ 운영 가이드](#️-운영-가이드)

## 📋 배포 전 체크리스트

### 개발 완료 확인
- [ ] **모든 Phase 완료**: Phase 1-6 구현 완료
- [ ] **단위 테스트 통과**: 85% 이상 코드 커버리지
- [ ] **통합 테스트 통과**: 모든 시나리오 성공
- [ ] **성능 테스트 통과**: 응답 시간 < 2초
- [ ] **품질 검증 통과**: 평균 품질 점수 > 0.8

### 코드 품질 확인
- [ ] **Lint 검사 통과**: 코딩 스타일 준수
- [ ] **타입 체크 통과**: 타입 힌팅 완성
- [ ] **보안 스캔 통과**: 취약점 없음
- [ ] **종속성 검토**: 최신 버전 및 보안 패치 적용
- [ ] **문서화 완료**: README, API 문서 업데이트

### 환경 준비 확인
- [ ] **API 키 발급**: Anthropic, OpenAI 등 모든 LLM API 키
- [ ] **인프라 구성**: 서버, 데이터베이스, 캐시 준비
- [ ] **모니터링 도구**: 로그, 메트릭, 알림 시스템 구성
- [ ] **백업 시스템**: 설정 및 데이터 백업 체계 구축
- [ ] **CI/CD 파이프라인**: 자동화 배포 시스템 구성

## 🏗️ 환경별 배포 절차

### 1. 개발 환경 (Development)

```bash
# 1. 코드 업데이트
git checkout develop
git pull origin develop

# 2. 의존성 설치
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. 환경변수 설정
cp .env.development .env
# .env 파일 편집

# 4. 테스트 실행
cd core/llm/summarizer/tests
python run_tests.py --quick

# 5. 서비스 시작
cd ../../../..
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

### 2. 스테이징 환경 (Staging)

```bash
# 1. 배포 준비
git checkout staging
git merge develop
git push origin staging

# 2. Docker 빌드
docker build -t freshdesk-ai-backend:staging .

# 3. 환경변수 검증
docker run --env-file .env.staging freshdesk-ai-backend:staging \
  python -c "
from core.llm.summarizer.config.settings import anthropic_settings
status = anthropic_settings.get_status()
assert status['config_loaded'] == True
print('✅ 환경변수 설정 완료')
"

# 4. 통합 테스트 실행
docker run --env-file .env.staging freshdesk-ai-backend:staging \
  bash -c "cd core/llm/summarizer/tests && python run_tests.py --coverage --performance"

# 5. 배포 실행
docker-compose -f docker-compose.staging.yml up -d

# 6. 헬스 체크
curl -f http://staging-api.company.com/health || exit 1
```

### 3. 운영 환경 (Production)

```bash
# 1. 최종 검증
git checkout main
git merge staging
git tag v1.0.0

# 2. 프로덕션 빌드
docker build -t freshdesk-ai-backend:v1.0.0 .
docker tag freshdesk-ai-backend:v1.0.0 freshdesk-ai-backend:latest

# 3. 보안 스캔
trivy image freshdesk-ai-backend:v1.0.0

# 4. 블루-그린 배포
# 4.1. 새 버전 배포 (Green)
docker-compose -f docker-compose.prod-green.yml up -d

# 4.2. 헬스 체크
./scripts/health-check.sh green

# 4.3. 트래픽 전환
./scripts/switch-traffic.sh green

# 4.4. 기존 버전 종료 (Blue)
docker-compose -f docker-compose.prod-blue.yml down

# 5. 배포 완료 확인
curl -f https://api.company.com/health
./scripts/post-deployment-tests.sh
```

## ⚙️ 환경변수 설정

### 개발 환경 (`.env.development`)
```bash
# 기본 설정
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=DEBUG

# Anthropic 설정
ENABLE_ANTHROPIC_PROMPTS=true
ANTHROPIC_QUALITY_THRESHOLD=0.7  # 개발용 낮은 임계값
ANTHROPIC_MAX_RETRIES=1

# 성능 설정 (개발용)
ANTHROPIC_PERFORMANCE_ENABLE_CACHING=false  # 개발 중 캐시 비활성화
ANTHROPIC_TIMEOUT=60  # 디버깅을 위한 긴 타임아웃

# 모니터링 (상세)
ANTHROPIC_MONITORING_LOG_LEVEL=DEBUG
ANTHROPIC_MONITORING_ENABLE_METRICS=true
```

### 스테이징 환경 (`.env.staging`)
```bash
# 기본 설정
ENVIRONMENT=staging
DEBUG=false
LOG_LEVEL=INFO

# Anthropic 설정
ENABLE_ANTHROPIC_PROMPTS=true
ANTHROPIC_QUALITY_THRESHOLD=0.8
ANTHROPIC_MAX_RETRIES=2

# 성능 설정 (운영 유사)
ANTHROPIC_PERFORMANCE_ENABLE_CACHING=true
ANTHROPIC_PERFORMANCE_CACHE_TTL=1800  # 30분
ANTHROPIC_TIMEOUT=30

# 모니터링
ANTHROPIC_MONITORING_LOG_LEVEL=INFO
ANTHROPIC_MONITORING_ENABLE_ALERTS=true
ANTHROPIC_NOTIFICATIONS_CHANNELS=slack
```

### 운영 환경 (`.env.production`)
```bash
# 기본 설정
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO

# Anthropic 설정 (엄격한 품질 관리)
ENABLE_ANTHROPIC_PROMPTS=true
ANTHROPIC_QUALITY_THRESHOLD=0.8
ANTHROPIC_RETRY_THRESHOLD=0.6
ANTHROPIC_FALLBACK_THRESHOLD=0.4
ANTHROPIC_MAX_RETRIES=3

# 성능 최적화
ANTHROPIC_PERFORMANCE_ENABLE_CACHING=true
ANTHROPIC_PERFORMANCE_CACHE_TTL=3600  # 1시간
ANTHROPIC_PERFORMANCE_ENABLE_PARALLEL=true
ANTHROPIC_PERFORMANCE_MAX_CONCURRENT=10
ANTHROPIC_TIMEOUT=30

# 모니터링 및 알림
ANTHROPIC_MONITORING_ENABLE_ALERTS=true
ANTHROPIC_MONITORING_ALERT_QUALITY_THRESHOLD=0.7
ANTHROPIC_MONITORING_ALERT_RESPONSE_TIME_THRESHOLD=30.0
ANTHROPIC_MONITORING_ALERT_ERROR_RATE_THRESHOLD=0.05
ANTHROPIC_NOTIFICATIONS_CHANNELS=email,slack,webhook

# 관리자 설정 (운영용)
ANTHROPIC_ADMIN_BACKUP_ON_CHANGE=true
ANTHROPIC_ADMIN_ENABLE_VERSION_CONTROL=true
ANTHROPIC_ADMIN_AUTO_VALIDATE_CHANGES=true
ANTHROPIC_ADMIN_TEST_BEFORE_APPLY=true
ANTHROPIC_ADMIN_ROLLBACK_ON_FAILURE=true
ANTHROPIC_ADMIN_RETENTION_PERIOD=180  # 6개월
```

## 🔒 보안 구성

### API 키 관리

#### AWS Secrets Manager 사용 (권장)
```python
# backend/core/config/secrets.py
import boto3
from botocore.exceptions import ClientError

class SecretsManager:
    def __init__(self):
        self.client = boto3.client('secretsmanager')
    
    def get_secret(self, secret_name: str) -> str:
        try:
            response = self.client.get_secret_value(SecretId=secret_name)
            return response['SecretString']
        except ClientError as e:
            logger.error(f"Secret 조회 실패: {e}")
            raise

# 사용법
secrets = SecretsManager()
anthropic_api_key = secrets.get_secret("prod/anthropic/api-key")
```

#### 환경변수 암호화
```bash
# 1. API 키 암호화
echo "sk-ant-api03-..." | gpg --symmetric --armor > anthropic_key.gpg

# 2. 배포 시 복호화
gpg --decrypt anthropic_key.gpg | export ANTHROPIC_API_KEY

# 3. 런타임에 마스킹
export ANTHROPIC_API_KEY_MASKED="sk-ant-***${ANTHROPIC_API_KEY: -6}"
```

### 네트워크 보안
```yaml
# docker-compose.prod.yml
version: '3.8'
services:
  freshdesk-ai:
    networks:
      - internal
    ports:
      - "127.0.0.1:8000:8000"  # 내부 접근만 허용
    environment:
      - ALLOWED_HOSTS=api.company.com
      - CORS_ORIGINS=https://company.freshdesk.com

networks:
  internal:
    driver: bridge
    internal: true
```

### 데이터 보안
```python
# 개인정보 마스킹
import re

class DataMasker:
    @staticmethod
    def mask_email(text: str) -> str:
        return re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', 
                     '***@***.***', text)
    
    @staticmethod
    def mask_phone(text: str) -> str:
        return re.sub(r'\b\d{2,3}-\d{3,4}-\d{4}\b', '***-****-****', text)
    
    @staticmethod
    def mask_sensitive_data(text: str) -> str:
        text = DataMasker.mask_email(text)
        text = DataMasker.mask_phone(text)
        return text
```

## 📊 모니터링 설정

### 1. 애플리케이션 메트릭

#### Prometheus 메트릭 설정
```python
# backend/core/monitoring/metrics.py
from prometheus_client import Counter, Histogram, Gauge

# Anthropic 관련 메트릭
anthropic_requests_total = Counter(
    'anthropic_requests_total',
    'Total number of Anthropic requests',
    ['model', 'content_type', 'status']
)

anthropic_quality_score = Histogram(
    'anthropic_quality_score',
    'Quality scores from Anthropic validator',
    buckets=[0.4, 0.6, 0.7, 0.8, 0.9, 1.0]
)

anthropic_response_time = Histogram(
    'anthropic_response_time_seconds',
    'Response time for Anthropic summarization',
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0]
)

anthropic_active_connections = Gauge(
    'anthropic_active_connections',
    'Number of active Anthropic API connections'
)
```

#### Grafana 대시보드 설정
```json
{
  "dashboard": {
    "title": "Anthropic 프롬프트 엔지니어링 모니터링",
    "panels": [
      {
        "title": "요청 처리량",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(anthropic_requests_total[5m])",
            "legendFormat": "{{status}} - {{model}}"
          }
        ]
      },
      {
        "title": "품질 점수 분포",
        "type": "histogram",
        "targets": [
          {
            "expr": "anthropic_quality_score",
            "legendFormat": "Quality Score"
          }
        ]
      },
      {
        "title": "응답 시간",
        "type": "graph",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, anthropic_response_time_seconds_bucket)",
            "legendFormat": "95th percentile"
          }
        ]
      }
    ]
  }
}
```

### 2. 로그 모니터링

#### ELK Stack 설정
```yaml
# logstash/anthropic.conf
input {
  beats {
    port => 5044
  }
}

filter {
  if [fields][service] == "anthropic" {
    grok {
      match => { 
        "message" => "%{TIMESTAMP_ISO8601:timestamp} - %{WORD:component} - %{WORD:level} - %{GREEDYDATA:content}"
      }
    }
    
    if [component] == "AnthropicSummarizer" {
      grok {
        match => {
          "content" => "quality_score=(?<quality_score>[0-9.]+)"
        }
      }
      mutate {
        convert => { "quality_score" => "float" }
      }
    }
  }
}

output {
  elasticsearch {
    hosts => ["elasticsearch:9200"]
    index => "anthropic-logs-%{+YYYY.MM.dd}"
  }
}
```

### 3. 알림 설정

#### Slack 알림
```python
# backend/core/monitoring/alerts.py
import requests
import json

class SlackAlerter:
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
    
    def send_quality_alert(self, quality_score: float, threshold: float):
        message = {
            "text": f"🚨 품질 점수 경고",
            "attachments": [
                {
                    "color": "danger",
                    "fields": [
                        {"title": "현재 품질 점수", "value": f"{quality_score:.2f}", "short": True},
                        {"title": "임계값", "value": f"{threshold:.2f}", "short": True},
                        {"title": "시간", "value": datetime.now().isoformat(), "short": False}
                    ]
                }
            ]
        }
        
        requests.post(self.webhook_url, json=message)
    
    def send_performance_alert(self, response_time: float, threshold: float):
        message = {
            "text": f"⚡ 성능 경고",
            "attachments": [
                {
                    "color": "warning", 
                    "fields": [
                        {"title": "응답 시간", "value": f"{response_time:.2f}초", "short": True},
                        {"title": "임계값", "value": f"{threshold:.2f}초", "short": True}
                    ]
                }
            ]
        }
        
        requests.post(self.webhook_url, json=message)
```

#### 이메일 알림
```python
# backend/core/monitoring/email_alerts.py
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

class EmailAlerter:
    def __init__(self, smtp_host: str, smtp_port: int, username: str, password: str):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
    
    def send_system_alert(self, subject: str, body: str, recipients: list):
        msg = MIMEMultipart()
        msg['From'] = self.username
        msg['To'] = ', '.join(recipients)
        msg['Subject'] = f"[Anthropic System] {subject}"
        
        msg.attach(MIMEText(body, 'html'))
        
        with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
            server.starttls()
            server.login(self.username, self.password)
            server.send_message(msg)
```

## 🔄 롤백 절차

### 1. 긴급 롤백 (5분 내)

```bash
#!/bin/bash
# scripts/emergency-rollback.sh

echo "🚨 긴급 롤백 시작..."

# 1. 이전 버전으로 즉시 전환
docker-compose -f docker-compose.prod-blue.yml up -d
./scripts/switch-traffic.sh blue

# 2. 문제 버전 중지
docker-compose -f docker-compose.prod-green.yml down

# 3. 헬스 체크
if curl -f https://api.company.com/health; then
    echo "✅ 롤백 성공"
    # 팀에 알림
    curl -X POST -H 'Content-type: application/json' \
        --data '{"text":"🚨 긴급 롤백 완료 - 서비스 정상화"}' \
        $SLACK_WEBHOOK_URL
else
    echo "❌ 롤백 실패 - 수동 개입 필요"
    exit 1
fi
```

### 2. 설정 롤백

```python
# 프롬프트 템플릿 롤백
from core.llm.summarizer.admin.prompt_manager import prompt_manager

async def rollback_templates():
    # 문제가 된 템플릿들을 이전 버전으로 롤백
    critical_templates = [
        ("anthropic_ticket_view", "system"),
        ("realtime_summary", "system"),
        ("attachment_selection", "system")
    ]
    
    for template_name, template_type in critical_templates:
        result = await prompt_manager.rollback_template(
            template_name=template_name,
            template_type=template_type,
            target_version="1.0.0",  # 안정된 버전
            user_id="emergency_rollback"
        )
        
        if result['success']:
            print(f"✅ {template_name} 롤백 성공")
        else:
            print(f"❌ {template_name} 롤백 실패: {result['error']}")

# 설정 롤백
from core.llm.summarizer.config.settings import anthropic_settings

def rollback_settings():
    # 안전한 기본값으로 복원
    safe_settings = {
        'quality_threshold': 0.6,  # 낮은 임계값으로 설정
        'max_retries': 1,         # 재시도 최소화
        'timeout': 60             # 넉넉한 타임아웃
    }
    
    anthropic_settings.update_config(safe_settings)
```

### 3. 데이터 백업 복원

```bash
# 템플릿 백업 복원
cp backups/templates_$(date -d '1 hour ago' '+%Y%m%d_%H').tar.gz /tmp/
cd /tmp && tar -xzf templates_*.tar.gz
cp -r templates/* /app/core/llm/summarizer/prompt/templates/

# 설정 백업 복원  
cp backups/config_$(date -d '1 hour ago' '+%Y%m%d_%H').json /app/config/anthropic_config.json
```

## 📈 성능 튜닝

### 1. 모델 선택 최적화

```python
# config/model_optimization.py
MODEL_PERFORMANCE_MAP = {
    # 속도 우선 (응답 시간 < 1초)
    "fast": {
        "provider": "anthropic",
        "model": "claude-3-haiku-20240307",
        "temperature": 0.05,
        "max_tokens": 800
    },
    
    # 균형 (응답 시간 < 2초, 품질 중상급)
    "balanced": {
        "provider": "anthropic", 
        "model": "claude-3-sonnet-20240229",
        "temperature": 0.1,
        "max_tokens": 1200
    },
    
    # 품질 우선 (응답 시간 < 5초, 최고 품질)
    "quality": {
        "provider": "anthropic",
        "model": "claude-3-opus-20240229", 
        "temperature": 0.05,
        "max_tokens": 1500
    }
}

def get_optimal_model(priority: str, content_size: int) -> dict:
    """컨텐츠 크기와 우선순위에 따른 최적 모델 선택"""
    if content_size > 20000:  # 대용량
        return MODEL_PERFORMANCE_MAP["fast"]
    elif priority in ["urgent", "high"]:
        return MODEL_PERFORMANCE_MAP["balanced"]
    else:
        return MODEL_PERFORMANCE_MAP["quality"]
```

### 2. 캐싱 전략

```python
# core/cache/anthropic_cache.py
import redis
import hashlib
import json
from typing import Optional

class AnthropicCache:
    def __init__(self, redis_url: str, ttl: int = 3600):
        self.redis = redis.from_url(redis_url)
        self.ttl = ttl
    
    def _generate_key(self, content: str, content_type: str, model: str) -> str:
        """컨텐츠 기반 캐시 키 생성"""
        content_hash = hashlib.md5(content.encode()).hexdigest()
        return f"anthropic:{content_type}:{model}:{content_hash}"
    
    def get_summary(self, content: str, content_type: str, model: str) -> Optional[str]:
        """캐시된 요약 조회"""
        key = self._generate_key(content, content_type, model)
        cached = self.redis.get(key)
        
        if cached:
            return json.loads(cached)['summary']
        return None
    
    def set_summary(self, content: str, content_type: str, model: str, 
                   summary: str, quality_score: float):
        """요약 결과 캐싱 (고품질만)"""
        if quality_score < 0.8:  # 고품질만 캐싱
            return
            
        key = self._generate_key(content, content_type, model)
        value = {
            'summary': summary,
            'quality_score': quality_score,
            'timestamp': datetime.now().isoformat()
        }
        
        self.redis.setex(key, self.ttl, json.dumps(value))
```

### 3. 병렬 처리 최적화

```python
# core/processing/parallel_processor.py
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any

class ParallelAnthropicProcessor:
    def __init__(self, max_workers: int = 5):
        self.max_workers = max_workers
        self.semaphore = asyncio.Semaphore(max_workers)
    
    async def process_batch(self, requests: List[Dict[str, Any]]) -> List[str]:
        """배치 요청 병렬 처리"""
        tasks = [
            self._process_single(request) 
            for request in requests
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 예외 처리
        summaries = []
        for result in results:
            if isinstance(result, Exception):
                summaries.append(f"Error: {str(result)}")
            else:
                summaries.append(result)
        
        return summaries
    
    async def _process_single(self, request: Dict[str, Any]) -> str:
        """단일 요청 처리 (세마포어로 동시 실행 제한)"""
        async with self.semaphore:
            summarizer = AnthropicSummarizer()
            return await summarizer.generate_anthropic_summary(**request)
```

### 4. 메모리 최적화

```python
# core/optimization/memory_optimizer.py
import gc
import psutil
from typing import Optional

class MemoryOptimizer:
    def __init__(self, max_memory_mb: int = 1024):
        self.max_memory_mb = max_memory_mb
    
    def check_memory_usage(self) -> float:
        """현재 메모리 사용률 확인"""
        process = psutil.Process()
        memory_mb = process.memory_info().rss / 1024 / 1024
        return memory_mb / self.max_memory_mb
    
    def optimize_if_needed(self) -> bool:
        """필요시 메모리 최적화 실행"""
        usage_ratio = self.check_memory_usage()
        
        if usage_ratio > 0.8:  # 80% 이상 사용시
            gc.collect()  # 가비지 컬렉션 강제 실행
            
            # 캐시 정리
            if hasattr(self, 'cache'):
                self.cache.clear_old_entries()
            
            return True
        return False
    
    def get_memory_stats(self) -> Dict[str, float]:
        """메모리 사용 통계"""
        process = psutil.Process()
        memory_info = process.memory_info()
        
        return {
            'rss_mb': memory_info.rss / 1024 / 1024,
            'vms_mb': memory_info.vms / 1024 / 1024,
            'usage_ratio': self.check_memory_usage(),
            'available_mb': psutil.virtual_memory().available / 1024 / 1024
        }
```

## 🛠️ 운영 가이드

### 1. 일상 운영 체크리스트

#### 매일 확인사항
- [ ] **시스템 상태**: 모든 서비스 정상 동작
- [ ] **성능 지표**: 응답 시간 < 2초 유지
- [ ] **품질 지표**: 평균 품질 점수 > 0.8
- [ ] **오류율**: 에러율 < 5%
- [ ] **API 사용량**: 할당량 대비 사용률 확인

#### 매주 확인사항
- [ ] **로그 분석**: 이상 패턴 탐지
- [ ] **성능 트렌드**: 응답 시간 추이 분석
- [ ] **품질 트렌드**: 품질 점수 변화 분석
- [ ] **리소스 사용률**: CPU, 메모리, 디스크 사용률
- [ ] **백업 검증**: 백업 데이터 무결성 확인

#### 매월 확인사항
- [ ] **보안 업데이트**: 의존성 보안 패치 적용
- [ ] **성능 튜닝**: 모델 및 설정 최적화
- [ ] **비용 분석**: API 사용 비용 분석 및 최적화
- [ ] **사용자 피드백**: 품질 개선 사항 수집
- [ ] **용량 계획**: 향후 확장 계획 수립

### 2. 문제 해결 플레이북

#### 응답 시간 증가 시
```bash
# 1. 시스템 리소스 확인
top -p $(pgrep -f "anthropic")
free -h
df -h

# 2. 네트워크 상태 확인
ping api.anthropic.com
curl -w "@curl-format.txt" -s -o /dev/null https://api.anthropic.com/v1/models

# 3. 데이터베이스 성능 확인
psql -c "SELECT * FROM pg_stat_activity WHERE state = 'active';"

# 4. 캐시 상태 확인
redis-cli info memory
redis-cli info stats

# 5. 임시 조치
# - 빠른 모델로 전환
# - 동시 처리 수 제한
# - 캐시 정리
```

#### 품질 점수 하락 시
```python
# 1. 품질 분석
from core.llm.summarizer.quality.anthropic_validator import AnthropicQualityValidator

validator = AnthropicQualityValidator()

# 최근 응답들의 품질 분석
recent_responses = get_recent_responses(limit=100)
quality_scores = []

for response in recent_responses:
    validation = validator.validate_constitutional_ai_compliance(
        response.content, response.principles
    )
    quality_scores.append(validation['overall_score'])

avg_quality = sum(quality_scores) / len(quality_scores)
print(f"평균 품질 점수: {avg_quality:.2f}")

# 2. 문제 패턴 분석
low_quality_responses = [r for r, s in zip(recent_responses, quality_scores) if s < 0.6]
print(f"저품질 응답 수: {len(low_quality_responses)}")

# 3. 임시 조치
# - 품질 임계값 일시 하향 조정
# - 더 강력한 모델로 전환
# - 프롬프트 템플릿 점검
```

#### API 오류 증가 시
```python
# 1. 오류 분석
import logging
from collections import Counter

# 최근 로그에서 오류 패턴 분석
error_patterns = Counter()
with open('/app/logs/anthropic.log', 'r') as f:
    for line in f:
        if 'ERROR' in line and 'anthropic' in line.lower():
            # 오류 패턴 추출
            if 'rate_limit' in line:
                error_patterns['rate_limit'] += 1
            elif 'timeout' in line:
                error_patterns['timeout'] += 1
            elif 'auth' in line:
                error_patterns['auth'] += 1

print("오류 패턴 분석:", error_patterns)

# 2. 대응 조치
if error_patterns['rate_limit'] > 10:
    # Rate limit 대응: 요청 간격 조정
    print("Rate limit 증가 - 요청 간격 조정 필요")
elif error_patterns['timeout'] > 5:
    # Timeout 대응: 타임아웃 증가 또는 모델 변경
    print("Timeout 증가 - 타임아웃 설정 조정 필요")
```

### 3. 모니터링 대시보드

#### Grafana 대시보드 구성
```json
{
  "dashboard": {
    "title": "Anthropic 운영 대시보드",
    "time": {
      "from": "now-1h",
      "to": "now"
    },
    "panels": [
      {
        "title": "시스템 건강성",
        "type": "stat",
        "targets": [
          {
            "expr": "up{job='anthropic-api'}",
            "legendFormat": "서비스 상태"
          }
        ]
      },
      {
        "title": "응답 시간 추이",
        "type": "graph",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, anthropic_response_time_seconds_bucket)",
            "legendFormat": "95th percentile"
          },
          {
            "expr": "histogram_quantile(0.50, anthropic_response_time_seconds_bucket)", 
            "legendFormat": "Median"
          }
        ]
      },
      {
        "title": "품질 점수 분포",
        "type": "histogram",
        "targets": [
          {
            "expr": "anthropic_quality_score",
            "legendFormat": "Quality Distribution"
          }
        ]
      },
      {
        "title": "오류율",
        "type": "stat",
        "targets": [
          {
            "expr": "rate(anthropic_requests_total{status='error'}[5m]) / rate(anthropic_requests_total[5m]) * 100",
            "legendFormat": "Error Rate %"
          }
        ]
      }
    ]
  }
}
```

### 4. 백업 및 복구

#### 자동 백업 스크립트
```bash
#!/bin/bash
# scripts/backup-anthropic-system.sh

BACKUP_DIR="/backups/anthropic/$(date +%Y%m%d_%H%M%S)"
mkdir -p $BACKUP_DIR

echo "🔄 Anthropic 시스템 백업 시작..."

# 1. 프롬프트 템플릿 백업
tar -czf $BACKUP_DIR/templates.tar.gz \
    core/llm/summarizer/prompt/templates/

# 2. 설정 파일 백업
cp .env $BACKUP_DIR/
cp config/*.yaml $BACKUP_DIR/

# 3. 백업 로그 백업
tar -czf $BACKUP_DIR/logs.tar.gz \
    core/llm/summarizer/logs/

# 4. 데이터베이스 백업 (설정 및 메타데이터)
pg_dump anthropic_configs > $BACKUP_DIR/configs.sql

# 5. 백업 검증
if [ -f "$BACKUP_DIR/templates.tar.gz" ]; then
    echo "✅ 백업 완료: $BACKUP_DIR"
    
    # S3에 업로드 (선택사항)
    if command -v aws &> /dev/null; then
        aws s3 cp $BACKUP_DIR s3://company-backups/anthropic/ --recursive
    fi
else
    echo "❌ 백업 실패"
    exit 1
fi

# 6. 오래된 백업 정리 (30일 이상)
find /backups/anthropic/ -type d -mtime +30 -exec rm -rf {} +
```

#### 복구 스크립트
```bash
#!/bin/bash
# scripts/restore-anthropic-system.sh

BACKUP_DATE=$1
if [ -z "$BACKUP_DATE" ]; then
    echo "사용법: $0 <YYYYMMDD_HHMMSS>"
    exit 1
fi

BACKUP_DIR="/backups/anthropic/$BACKUP_DATE"

if [ ! -d "$BACKUP_DIR" ]; then
    echo "❌ 백업을 찾을 수 없습니다: $BACKUP_DIR"
    exit 1
fi

echo "🔄 Anthropic 시스템 복구 시작..."

# 1. 서비스 중지
docker-compose down

# 2. 현재 설정 백업
cp -r core/llm/summarizer/prompt/templates/ /tmp/templates_backup_$(date +%s)
cp .env /tmp/env_backup_$(date +%s)

# 3. 템플릿 복구
tar -xzf $BACKUP_DIR/templates.tar.gz -C ./

# 4. 설정 복구
cp $BACKUP_DIR/.env ./

# 5. 로그 복구 (선택사항)
if [ -f "$BACKUP_DIR/logs.tar.gz" ]; then
    tar -xzf $BACKUP_DIR/logs.tar.gz -C ./
fi

# 6. 데이터베이스 복구
if [ -f "$BACKUP_DIR/configs.sql" ]; then
    psql anthropic_configs < $BACKUP_DIR/configs.sql
fi

# 7. 서비스 재시작
docker-compose up -d

# 8. 복구 검증
sleep 30
if curl -f http://localhost:8000/health; then
    echo "✅ 복구 완료"
else
    echo "❌ 복구 후 서비스 상태 이상"
    exit 1
fi
```

---

## 🎯 배포 성공 기준

### 기능 요구사항
- [ ] **요약 품질**: 평균 품질 점수 > 0.8
- [ ] **응답 시간**: 95% 요청이 2초 이내 처리
- [ ] **가용성**: 99.9% 업타임 달성
- [ ] **확장성**: 동시 100명 사용자 지원

### 비기능 요구사항
- [ ] **보안**: 개인정보 누출 0건
- [ ] **모니터링**: 실시간 메트릭 수집
- [ ] **운영성**: 관리자 도구 정상 동작
- [ ] **복구 시간**: 5분 이내 긴급 롤백 가능

### 사용자 만족도
- [ ] **상담원 피드백**: 평균 4.0/5.0 이상
- [ ] **업무 효율성**: 티켓 처리 시간 30% 단축
- [ ] **오류 신고**: 주간 1건 이하
- [ ] **교육 필요성**: 추가 교육 없이 사용 가능

---

**🚀 성공적인 배포를 위해 모든 단계를 체계적으로 진행하세요!**

> 💡 **핵심**: 안전한 배포 → 철저한 모니터링 → 지속적인 개선