# GitHub Actions Secrets 설정 가이드

## 📋 필수 Secrets

GitHub Repository → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

다음 환경변수들을 Repository Secrets로 등록하세요:

### 🎫 Freshdesk API
```
Name: FRESHDESK_DOMAIN
Value: your-company.freshdesk.com

Name: FRESHDESK_API_KEY  
Value: your-actual-api-key
```

### 🗄️ Qdrant Vector Database
```
Name: QDRANT_URL
Value: https://your-cluster.cloud.qdrant.io

Name: QDRANT_API_KEY
Value: your-actual-qdrant-key
```

### 🤖 LLM API Keys
```
Name: ANTHROPIC_API_KEY
Value: your-actual-anthropic-key

Name: OPENAI_API_KEY
Value: your-actual-openai-key

Name: GOOGLE_API_KEY
Value: your-actual-google-key
```

### ⚙️ 애플리케이션 설정
```
Name: COMPANY_ID
Value: kyexpert

Name: EMBEDDING_MODEL
Value: text-embedding-3-small
```

## 🔧 GitHub Actions에서 사용법

워크플로우 파일에서 secrets 사용 예시:

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    
    env:
      FRESHDESK_DOMAIN: ${{ secrets.FRESHDESK_DOMAIN }}
      FRESHDESK_API_KEY: ${{ secrets.FRESHDESK_API_KEY }}
      QDRANT_URL: ${{ secrets.QDRANT_URL }}
      QDRANT_API_KEY: ${{ secrets.QDRANT_API_KEY }}
      ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
      OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
      GOOGLE_API_KEY: ${{ secrets.GOOGLE_API_KEY }}
      COMPANY_ID: ${{ secrets.COMPANY_ID }}
      EMBEDDING_MODEL: ${{ secrets.EMBEDDING_MODEL }}
    
    steps:
      - name: Test API connections
        run: |
          python backend/check_env.sh
```

## 🛡️ 보안 주의사항

1. **Secrets는 로그에 출력되지 않음**: GitHub이 자동으로 마스킹 처리
2. **Fork된 저장소에서는 접근 불가**: 보안을 위한 제한
3. **Pull Request에서는 제한적 접근**: 외부 기여자로부터 보호
4. **Secrets 값 확인 불가**: 설정 후에는 값을 볼 수 없음

## 🔄 Secrets 업데이트

환경변수 변경 시:
1. GitHub Repository Settings에서 해당 Secret 수정
2. 새로운 워크플로우 실행에서 자동 적용
3. 캐시된 값은 없으므로 즉시 반영됨

## 📞 문제 해결

### "Secret not found" 에러
- Secret 이름이 정확한지 확인
- Repository 권한이 있는지 확인
- Organization level secrets인지 확인

### API 연결 실패
- Secret 값이 올바른지 재확인
- API 키 유효기간 확인
- 네트워크 제한 사항 확인
