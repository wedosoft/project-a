# Fly.io 배포 빠른 시작 가이드

## 🚀 한 번에 배포하기

```bash
# 1. 배포 스크립트 실행 (앱 생성 + Secrets 설정 + 배포)
./scripts/deploy.sh
```

이 스크립트는 자동으로:
- Flyctl 설치 및 로그인 확인
- 앱 생성 (없는 경우)
- Secrets 설정 여부 확인 및 설정
- Docker 이미지 빌드 및 배포
- 헬스 체크 수행

## 📋 수동 배포 단계

### 1단계: Flyctl 설치 및 로그인
```bash
# Flyctl 설치
brew install flyctl

# 로그인
flyctl auth login
```

### 2단계: 앱 생성
```bash
flyctl apps create ai-contact-center-os
```

### 3단계: Secrets 설정
```bash
# 자동 설정 (권장)
./scripts/deploy_secrets.sh
flyctl secrets deploy

# 또는 수동 설정
flyctl secrets set OPENAI_API_KEY="your-key"
flyctl secrets set GOOGLE_API_KEY="your-key"
# ... (나머지 secrets)
```

### 4단계: 배포
```bash
flyctl deploy
```

## 🔍 배포 후 확인

```bash
# 앱 상태
flyctl status

# 로그 확인
flyctl logs

# 헬스 체크
curl https://ai-contact-center-os.fly.dev/health
```

## ⚙️ 최소 사양 설정 (현재 구성)

- **리전**: Tokyo (nrt) - 한국과 가장 가까움
- **메모리**: 256MB
- **CPU**: shared-cpu-1x
- **Auto-suspend**: 활성화 (유휴 시 자동 중지로 비용 절감)
- **예상 비용**: 월 $1-5 (저사용량 기준)

## 📚 상세 가이드

더 자세한 내용은 [Fly.io 배포 가이드](./FLY_IO_DEPLOYMENT.md)를 참조하세요.

## ⚠️ 주의사항

1. `.env` 파일은 절대 Git에 커밋하지 마세요
2. Fly.io Secrets만 사용하여 환경 변수 관리
3. 배포 전 Secrets가 모두 설정되었는지 확인하세요
