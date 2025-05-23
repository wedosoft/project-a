# 🔐 환경변수 설정 가이드

## ⚠️ 보안 주의사항

**절대로 실제 API 키나 민감한 정보를 GitHub에 업로드하지 마세요!**

## 📋 설정 방법

### 1. 로컬 개발 환경 설정

```bash
# 1. 템플릿 파일 복사
cp .env.example .env

# 2. .env 파일 편집 (실제 값으로 수정)
# VS Code에서 .env 파일을 열어서 실제 API 키로 수정하세요
```

### 2. 필수 환경변수 획득 방법

#### 🎫 Freshdesk API 키
1. Freshdesk 관리자 계정으로 로그인
2. **Admin** → **Developer Console** → **API Key** 생성
3. `FRESHDESK_DOMAIN`: `your-company.freshdesk.com`
4. `FRESHDESK_API_KEY`: 생성된 API 키

#### 🗄️ Qdrant Cloud 설정
1. [Qdrant Cloud](https://cloud.qdrant.io) 계정 생성
2. 새 클러스터 생성
3. `QDRANT_URL`: 클러스터 URL (`https://xxx.cloud.qdrant.io`)
4. `QDRANT_API_KEY`: 클러스터 API 키

#### 🤖 LLM API 키
- **Anthropic Claude**: [console.anthropic.com](https://console.anthropic.com)
- **OpenAI GPT**: [platform.openai.com](https://platform.openai.com)
- **Google Gemini**: [ai.google.dev](https://ai.google.dev)

### 3. GitHub Actions Secrets 설정 (CI/CD용)

GitHub Repository → **Settings** → **Secrets and variables** → **Actions**

필요한 Secrets:
```
FRESHDESK_DOMAIN
FRESHDESK_API_KEY
QDRANT_URL
QDRANT_API_KEY
ANTHROPIC_API_KEY
OPENAI_API_KEY
GOOGLE_API_KEY
```

### 4. 환경변수 검증

```bash
# 백엔드 디렉토리에서 환경변수 확인
cd backend
python check_env.sh
```

## 📁 파일 구조

```
project-a/
├── .env.example          # ✅ GitHub에 포함 (템플릿)
├── .env                  # ❌ GitHub에서 제외 (실제 값)
├── .gitignore           # .env 제외 설정 포함
└── backend/
    ├── .env             # ❌ GitHub에서 제외 (실제 값)
    └── check_env.sh     # 환경변수 검증 스크립트
```

## 🛡️ 보안 체크리스트

- [ ] `.env` 파일이 `.gitignore`에 포함되어 있음
- [ ] 실제 API 키가 GitHub에 업로드되지 않았음
- [ ] 모든 민감한 정보는 환경변수로 관리
- [ ] 프로덕션과 개발 환경 분리
- [ ] API 키 권한을 최소한으로 설정

## 🔄 환경변수 업데이트

환경변수가 변경되면:

1. `.env.example` 업데이트 (새로운 변수 추가)
2. 팀원들에게 변경사항 공지
3. GitHub Actions Secrets 업데이트
4. 프로덕션 환경 설정 업데이트

## 🆘 문제 해결

### "환경변수를 찾을 수 없음" 에러
```bash
# 환경변수 파일 존재 확인
ls -la .env

# 환경변수 로드 확인
source .env && echo $FRESHDESK_API_KEY
```

### API 키 유효성 테스트
```bash
# Freshdesk API 테스트
curl -u $FRESHDESK_API_KEY:X https://$FRESHDESK_DOMAIN/api/v2/tickets?per_page=1

# Qdrant 연결 테스트
python -c "from core.vectordb import vector_db; print(vector_db.client.get_collections())"
```

## 📞 지원

환경변수 설정에 문제가 있으면:
1. 이 문서의 단계별 확인
2. API 키 유효성 검증
3. 네트워크 연결 상태 확인
4. 프로젝트 이슈 트래커에 문의
