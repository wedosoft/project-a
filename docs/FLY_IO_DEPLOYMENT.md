# Fly.io 배포 가이드

## 1. 사전 준비

### Fly.io CLI 설치
```bash
# macOS
brew install flyctl

# 로그인
flyctl auth login
```

## 2. 환경 변수 설정

Fly.io Secrets를 사용하여 환경 변수를 안전하게 설정합니다.

### 필수 환경 변수 설정
```bash
# LLM API Keys
flyctl secrets set OPENAI_API_KEY="your-openai-key"
flyctl secrets set GEMINI_API_KEY="your-google-key"

# Qdrant
flyctl secrets set QDRANT_HOST="your-qdrant-host"
flyctl secrets set QDRANT_PORT="6333"
flyctl secrets set QDRANT_USE_HTTPS="true"
flyctl secrets set QDRANT_API_KEY="your-qdrant-key"

# Supabase
flyctl secrets set SUPABASE_URL="your-supabase-url"
flyctl secrets set SUPABASE_KEY="your-supabase-anon-key"
flyctl secrets set SUPABASE_SERVICE_ROLE_KEY="your-service-role-key"
flyctl secrets set SUPABASE_DB_PASSWORD="your-db-password"
flyctl secrets set SUPABASE_DB_HOST="your-db-host"
flyctl secrets set SUPABASE_DB_PORT="6543"
flyctl secrets set SUPABASE_DB_NAME="postgres"
flyctl secrets set SUPABASE_DB_USER="your-db-user"

# Models
flyctl secrets set EMBEDDING_MODEL="BAAI/bge-m3"
flyctl secrets set RERANKER_MODEL="jinaai/jina-reranker-v2-base-multilingual"

# Freshdesk
flyctl secrets set FRESHDESK_DOMAIN="your-domain.freshdesk.com"
flyctl secrets set FRESHDESK_API_KEY="your-freshdesk-key"
```

### 모든 환경 변수 한 번에 설정 (편의용 스크립트)
로컬 `.env` 파일의 값을 복사하여 사용하되, **절대 .env 파일을 커밋하지 마세요**.

```bash
# .env 파일 기반으로 secrets 설정 (scripts/deploy_secrets.sh 사용)
./scripts/deploy_secrets.sh
```

### 설정된 Secrets 확인
```bash
flyctl secrets list
```

### Secret 삭제 (필요시)
```bash
flyctl secrets unset SECRET_NAME
```

## 3. 앱 생성 및 배포

### 앱 생성
```bash
# fly.toml에 정의된 앱 이름으로 생성
flyctl apps create ai-contact-center-os
```

### 초기 배포
```bash
flyctl deploy
```

### 배포 상태 확인
```bash
flyctl status
```

### 로그 확인
```bash
# 실시간 로그
flyctl logs

# 최근 로그만 보기
flyctl logs --recent
```

## 4. 앱 관리

### 앱 재시작
```bash
flyctl apps restart ai-contact-center-os
```

### 스케일링 (필요시 메모리 증가)
```bash
# 512MB로 증가
flyctl scale memory 512

# VM 개수 조정 (최소 사양으로는 1개 권장)
flyctl scale count 1
```

### 헬스 체크 확인
```bash
flyctl checks list
```

### 앱 정보 확인
```bash
flyctl info
```

## 5. 개발용 최소 사양 설정

현재 `fly.toml`에 다음과 같이 설정되어 있습니다:

- **리전**: `nrt` (Tokyo, 한국과 가장 가까움)
- **메모리**: 256MB (최소)
- **CPU**: shared-cpu-1x (공유 CPU 1개)
- **Auto-suspend**: 유휴 시 자동 일시중지 (비용 절감)
- **최소 실행 머신**: 0 (완전히 유휴 시 모두 중지 가능)

### 비용 절감 팁
- `auto_stop_machines = "suspend"`: 요청이 없을 때 자동 중지
- `min_machines_running = 0`: 모든 머신 중지 허용
- 첫 요청 시 자동으로 시작되며, 약 1-2초 정도 지연될 수 있음

## 6. URL 및 접근

배포 후 앱 URL:
```
https://ai-contact-center-os.fly.dev
```

### API 테스트
```bash
# 헬스 체크
curl https://ai-contact-center-os.fly.dev/health

# API 엔드포인트 테스트
curl https://ai-contact-center-os.fly.dev/api/v1/assist/propose \
  -H "Content-Type: application/json" \
  -d '{...}'
```

## 7. 문제 해결

### 배포 실패 시
```bash
# 상세 로그 확인
flyctl logs

# VM 셸 접속
flyctl ssh console

# 앱 재배포
flyctl deploy --force
```

### 메모리 부족 시
```bash
# 메모리 증가 (512MB)
flyctl scale memory 512
```

### 환경 변수 누락 시
```bash
# Secrets 확인
flyctl secrets list

# 누락된 Secret 추가
flyctl secrets set KEY="value"
```

## 8. 보안 주의사항

1. **절대 .env 파일을 Git에 커밋하지 마세요**
2. **Fly.io Secrets만 사용**하여 민감한 정보 관리
3. **API 키는 정기적으로 로테이션**
4. **프로덕션 환경에서는 별도의 API 키 사용** 권장

## 9. 추가 리소스

- [Fly.io 공식 문서](https://fly.io/docs/)
- [Fly.io Python 가이드](https://fly.io/docs/languages-and-frameworks/python/)
- [Fly.io Pricing](https://fly.io/docs/about/pricing/)

## 10. 비용 예상 (최소 사양)

- **Compute**: shared-cpu-1x, 256MB RAM
  - 약 $0.0000008/초 (사용 시간만 과금)
  - Auto-suspend 활성화 시 유휴 시간 무과금
- **네트워크**: 처음 100GB/월 무료
- **예상 월 비용**: $1-5 (개발용, 저사용량 기준)

**참고**: 실제 비용은 사용량에 따라 다를 수 있으므로 Fly.io 대시보드에서 정기적으로 확인하세요.
