# 📂 Git 브랜치별 파일 관리 가이드

## 🎯 개요

이 프로젝트는 main과 dev 브랜치에서 서로 다른 파일 세트를 관리합니다.

## 📋 브랜치별 파일 구조

### main 브랜치
- 운영 환경용 파일들만 포함
- tasks/ 폴더 및 관련 파일들 제외
- 깔끔한 .gitignore 설정

### dev 브랜치
- 개발 환경 전용 파일들 포함
- Task Master 관련 파일들 (tasks/, tasks.json)
- 개발용 로그, 임시 파일들
- .gitignore.dev 활용

## 🛠️ 사용 방법

### dev 브랜치에서 작업할 때

1. **gitignore 설정 적용**
   ```bash
   # dev 브랜치로 전환
   git checkout dev
   
   # 개발용 gitignore 설정 병합 (선택사항)
   cat .gitignore.dev >> .gitignore
   ```

2. **Task Master 사용**
   ```bash
   # tasks 폴더의 파일들은 자동으로 무시됨
   # Task Master 명령어들 정상 사용 가능
   ```

### main 브랜치로 병합할 때

1. **병합 전 확인**
   ```bash
   # dev 브랜치의 변경사항 중 main에 필요한 것만 선별
   git checkout main
   git merge dev
   ```

2. **충돌 해결**
   - .gitignore 충돌 시: main 브랜치 버전 유지
   - tasks 관련 파일들: 무시 (dev에만 존재)

## ⚙️ 자동화 스크립트 (선택사항)

### dev 환경 설정 스크립트

```bash
#!/bin/bash
# filepath: scripts/setup-dev-env.sh

if [ "$(git branch --show-current)" = "dev" ]; then
    echo "🔧 dev 브랜치 환경 설정 중..."
    
    # dev 전용 gitignore 설정 임시 적용
    if [ -f .gitignore.dev ]; then
        echo "📂 개발용 gitignore 설정 적용"
        cat .gitignore.dev >> .gitignore.temp
        mv .gitignore.temp .gitignore
    fi
    
    echo "✅ dev 브랜치 환경 설정 완료"
else
    echo "❌ dev 브랜치에서만 실행 가능합니다"
fi
```

## 🚨 주의사항

1. **main 브랜치에서는 tasks/ 폴더 생성 금지**
2. **dev에서 main으로 병합 시 .gitignore 충돌 주의**
3. **운영 배포는 main 브랜치에서만 수행**

## 🔍 문제 해결

### 병합 충돌 발생 시
```bash
# .gitignore 충돌 해결
git checkout --ours .gitignore
git add .gitignore

# tasks 파일들 무시
git rm --cached tasks/ -r
```

### 실수로 tasks 파일이 main에 추가된 경우
```bash
# main 브랜치에서 tasks 폴더 제거
git rm -r tasks/
git rm tasks.json
echo "tasks/" >> .gitignore
echo "tasks.json" >> .gitignore
git add .gitignore
git commit -m "Remove dev-only files from main branch"
```
