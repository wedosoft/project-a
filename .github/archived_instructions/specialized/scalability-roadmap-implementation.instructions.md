````instructions
---
applyTo: "**"
---

# 🚀 확장성 로드맵 & 단계별 구현 지침서

_AI 참조 최적화 버전 - 확장성 전략과 단계별 로드맵 가이드_

## 📋 **TL;DR - 확장성 로드맵 핵심 요약**

### 🎯 **3단계 확장 전략**
- **Phase 1 (MVP)**: Freshdesk 어댑터, JSON 스토리지, 기본 최적화 (완료)
- **Phase 2 (SaaS)**: PostgreSQL, Redis Cluster, 멀티테넌트 완성 (3개월)

### 📊 **핵심 성능 목표**
- **동시 사용자**: 1,000명+ (Phase 2)
- **응답시간**: 평균 2초 이하 (Phase 2)
- **가용성**: 99.9% SLA (Phase 2)

---

## 🚀 **확장성 로드맵 & 단계별 구현 (AI 구현 필수 체크리스트)**

### ✅ **Phase 1: MVP (Freshdesk) - 현재 완료 상태**

**완료된 기능**:

- [x] **Freshdesk 어댑터**: 완전 구현 (`backend/core/platforms/freshdesk/`)
- [x] **파일 기반 스토리지**: JSON 기반 개발 환경
- [x] **기본 성능 최적화**: orjson, pydantic v2 적용
- [x] **company_id 자동 추출**: 도메인 기반 테넌트 식별
- [x] **LLM 모듈화**: `core/llm/` 하위 5개 모듈로 분리 완료
- [x] **데이터 수집 모듈화**: `core/ingest/` 하위 4개 모듈로 분리 완료

**현재 작업 중**:

- [ ] **langchain 통합**: LLM 체인 최적화 및 캐싱
- [ ] **Redis 캐싱**: LLM 응답 캐싱으로 비용 절감
- [ ] **성능 모니터링**: Prometheus 메트릭 수집

### ✅ **Phase 2: SaaS (멀티테넌트) - 향후 3개월**

#### 🎯 **필수 구현 목표**

**데이터베이스 마이그레이션**:

- [ ] **PostgreSQL 전환**: JSON 파일 → PostgreSQL
  ```sql
  -- Row-level Security 설정
  CREATE POLICY tenant_isolation ON tickets 
    FOR ALL TO authenticated_users 
    USING (company_id = current_setting('app.current_company_id'));
  ```

- [ ] **마이그레이션 스크립트**: 기존 데이터 무중단 이전
  ```python
  # scripts/migrate_to_postgresql.py
  async def migrate_json_to_postgres():
      for company_id in get_all_companies():
          json_data = load_json_data(company_id)
          await insert_postgres_data(company_id, json_data)
  ```

**캐싱 인프라**:

- [ ] **Redis Cluster**: 고가용성 캐싱
  ```yaml
  # docker-compose.redis-cluster.yml
  services:
    redis-node-1:
      image: redis:7-alpine
      command: redis-server --cluster-enabled yes
    redis-node-2:
      image: redis:7-alpine
      command: redis-server --cluster-enabled yes
  ```

- [ ] **캐시 전략**: LLM 응답, 벡터 검색 결과 캐싱
  ```python
  CACHE_STRATEGIES = {
      "llm_responses": {"ttl": 3600, "max_size": 10000},
      "vector_search": {"ttl": 1800, "max_size": 50000},
      "ticket_data": {"ttl": 600, "max_size": 100000}
  }
  ```

**보안 & 컴플라이언스**:

- [ ] **AWS Secrets Manager**: API 키 중앙화
  ```python
  import boto3
  
  async def get_secret(secret_name: str) -> dict:
      client = boto3.client('secretsmanager')
      response = client.get_secret_value(SecretId=secret_name)
      return json.loads(response['SecretString'])
  ```

- [ ] **GDPR 준수**: 개인정보 처리 완전 준수
  ```python
  # 개인정보 삭제 API
  @router.delete("/api/user/{user_id}/data")
  async def delete_user_data(user_id: str, company_id: str = Depends(get_company_id)):
      await anonymize_user_data(company_id, user_id)
      await delete_vector_embeddings(company_id, user_id)
  ```

#### 📊 **성능 목표**

- [ ] **동시 사용자**: 1,000명 이상 지원
- [ ] **응답시간**: 평균 2초 이하 달성
- [ ] **가용성**: 99.9% SLA 달성
- [ ] **처리량**: 100 RPS 이상 처리

#### 🏗️ **인프라 구성**

**로드 밸런싱**:

```yaml
# docker-compose.production.yml
services:
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
  
  backend-1:
    build: .
    environment:
      - REDIS_URL=redis://redis-cluster:6379
  
  backend-2:
    build: .
    environment:
      - REDIS_URL=redis://redis-cluster:6379
```

### ✅ **Phase 3: 글로벌 (다중 플랫폼) - 향후 6개월**

#### 🌍 **플랫폼 확장**


  ```python
      async def fetch_tickets(self, company_id: str) -> List[Ticket]:
          pass
      
      async def fetch_articles(self, company_id: str) -> List[Article]:
          pass
  ```

- [ ] **ServiceNow 플랫폼**: 향후 확장 고려
  ```python
  # backend/core/platforms/servicenow/adapter.py
  class ServiceNowAdapter(BasePlatformAdapter):
      # ServiceNow 특화 구현
      pass
  ```

**다국어 지원**:

- [ ] **i18n 완성**: 전체 UI/API 다국어 지원
  ```python
  # backend/core/i18n.py
  SUPPORTED_LANGUAGES = ["en", "ko", "ja", "zh", "de", "fr", "es"]
  
  async def get_localized_response(text: str, language: str) -> str:
      translations = await load_translations(language)
      return translations.get(text, text)
  ```

#### 🌐 **글로벌 인프라**

**멀티 리전 배포**:

- [ ] **AWS/GCP 글로벌 인프라**: 지역별 최적화
  ```yaml
  # terraform/global-infrastructure.tf
  regions = ["us-east-1", "eu-west-1", "ap-northeast-1"]
  
  resource "aws_instance" "backend" {
    for_each = toset(var.regions)
    # 각 리전별 인스턴스 생성
  }
  ```

- [ ] **CDN 최적화**: 정적 자산 글로벌 캐싱
  ```yaml
  # CloudFront 설정
  cloudfront_distribution:
    origins:
      - domain_name: api.example.com
        behaviors:
          - path_pattern: "/static/*"
            cache_policy: "CachingOptimized"
  ```

**컴플라이언스**:

- [ ] **지역별 데이터 거버넌스**: GDPR, CCPA 등 완전 준수
  ```python
  DATA_RESIDENCY_RULES = {
      "EU": {"region": "eu-west-1", "compliance": ["GDPR"]},
      "US": {"region": "us-east-1", "compliance": ["CCPA"]},
      "APAC": {"region": "ap-northeast-1", "compliance": ["PDPA"]}
  }
  ```

---

## 🎯 **AI 세션 간 일관성 보장 최종 체크리스트**

### ✅ **아키텍처 일관성 검증**

**코드 재활용 원칙**:

- [x] **기존 코드 90% 이상 재활용**: 임의 재작성 금지
- [x] **레거시 로직 보존**: 안정적인 기존 비즈니스 로직 유지
- [x] **점진적 개선**: 전면 재설계 대신 단계적 최적화
- [x] **검증된 패턴 활용**: 이미 검증된 아키텍처 패턴 재사용

**멀티테넌트 필수 요소**:

- [x] **company_id 필수**: 모든 데이터 작업에 테넌트 ID 포함
- [x] **격리 검증**: 테넌트 간 데이터 누출 방지 확인
- [x] **보안 헤더**: X-Company-ID 등 필수 헤더 검증
- [x] **네임스페이스**: 모든 저장소에서 테넌트별 분리

**성능 최적화 필수**:

- [x] **orjson 사용**: `import json` 대신 `import orjson` 필수
- [x] **pydantic v2**: 모든 데이터 모델에 적용
- [x] **비동기 패턴**: async/await 기반 I/O 처리
- [x] **Redis 캐싱**: LLM 응답 및 벡터 검색 캐싱

### 🚨 **절대 금지 사항 (AI 구현 시 필수 준수)**

- ❌ **기존 디렉터리 구조 변경**: `backend/api/`, `backend/core/` 구조 유지
- ❌ **company_id 없는 컴포넌트**: 모든 데이터 작업에 테넌트 ID 필수
- ❌ **플랫폼별 하드코딩**: 조건문 남발 대신 추상화 패턴 사용
- ❌ **동기 I/O 남용**: `requests` 대신 `httpx`, 비동기 패턴 선호
- ❌ **기존 코드 임의 삭제**: 90% 이상 기존 로직 재활용 원칙

### 📚 **AI 참조용 핵심 디렉터리 맵 (실제 파일 경로)**

```
MUST KNOW 핵심 파일 경로:
- backend/core/config.py               # 전체 시스템 설정 (company_id 자동 추출)
- backend/core/platforms/factory.py   # 플랫폼 어댑터 팩토리
- backend/api/main.py                  # FastAPI 앱 진입점
- backend/core/platforms/freshdesk/    # Freshdesk 완전 구현 예시
- backend/core/vectordb.py             # Qdrant 벡터 DB 연동
- backend/core/llm/router.py           # LLM 라우팅 로직 (모듈화 완료)
- backend/core/ingest/processor.py     # 데이터 수집 핵심 로직 (모듈화 완료)
- backend/api/routes/                  # 모든 API 엔드포인트
- scripts/collect_and_process.py       # company_id 자동 적용 예시
```

---

## 📈 **마일스톤 & 성공 지표**

### 🎯 **Phase 2 성공 지표 (3개월 목표)**

**성능 지표**:
- [ ] 평균 응답시간 2초 이하 달성
- [ ] 동시 사용자 1,000명 지원
- [ ] 99.9% 가용성 달성
- [ ] 캐시 적중률 70% 이상

**비즈니스 지표**:
- [ ] 월간 활성 사용자 500명 이상
- [ ] 사용자 만족도 4.5/5.0 이상
- [ ] 티켓 해결 시간 30% 단축
- [ ] 플랫폼 안정성 99.9% 달성

### 🌍 **Phase 3 성공 지표 (6개월 목표)**

**기술 지표**:
- [ ] 5개 언어 지원 (EN, KO, JA, ZH, DE)
- [ ] 3개 리전 배포 (US, EU, APAC)
- [ ] 글로벌 CDN 응답시간 1초 이하

**비즈니스 지표**:
- [ ] 월간 활성 사용자 5,000명 이상
- [ ] 글로벌 고객 100개 기업 이상
- [ ] 다국어 사용률 20% 이상
- [ ] 전체 매출 목표 달성

---

## 🔗 **관련 지침서 참조**

- 📚 [Quick Reference](quick-reference.instructions.md) - 즉시 참조용 핵심 패턴
- 🏗️ [API 아키텍처 & 파일 구조](api-architecture-file-structure.instructions.md) - 시스템 구조
- ⚡ [성능 최적화](performance-optimization.instructions.md) - 성능 향상 전략
- 🔒 [멀티테넌트 보안](multitenant-security.instructions.md) - 보안 구현 상세
- 📊 [모니터링 & 테스트](monitoring-testing-strategy.instructions.md) - 품질 보증

**이 확장성 로드맵은 AI가 세션 간 일관성을 유지하며 시스템을 단계적으로 확장할 수 있도록 모든 핵심 전략과 구현 방법을 포함합니다. 모든 기술적 결정은 이 문서를 기준으로 평가하고 구현하시기 바랍니다.**

**2025년 6월 21일 기준 - AI 세션 간 일관성 보장**
````
