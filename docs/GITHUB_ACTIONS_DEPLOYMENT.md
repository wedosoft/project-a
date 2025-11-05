# GitHub Actions 자동 배포 설정 가이드

## 개요

main 브랜치에 push할 때마다 자동으로 Fly.io에 배포되도록 GitHub Actions가 설정되어 있습니다.

## 1. Fly.io API Token 생성

### Token 생성 방법
```bash
# 터미널에서 실행
flyctl auth token
```

이 명령은 API 토큰을 출력합니다. 이 토큰을 복사하세요.

## 2. GitHub Repository Secrets 설정

### 단계별 가이드

1. **GitHub 저장소로 이동**
   - https://github.com/wedosoft/project-a-spinoff

2. **Settings 탭 클릭**

3. **왼쪽 메뉴에서 "Secrets and variables" > "Actions" 선택**

4. **"New repository secret" 클릭**

5. **Secret 추가**
   - Name: `FLY_API_TOKEN`
   - Secret: (위에서 복사한 Fly.io API 토큰 붙여넣기)
   - "Add secret" 클릭

## 3. 자동 배포 동작 방식

### 트리거 조건
- `main` 브랜치에 push할 때 자동 실행
- 수동 실행 가능 (Actions 탭에서 "Run workflow" 클릭)

### 배포 프로세스
```
1. 코드 체크아웃
2. Flyctl 설치
3. Docker 이미지 빌드 (Fly.io 원격 빌더 사용)
4. Fly.io에 배포 (단일 머신, HA 비활성화)
```

## 4. 배포 확인

### GitHub Actions에서 확인
1. GitHub 저장소의 "Actions" 탭 방문
2. 최근 워크플로우 실행 확인
3. 로그 확인하여 배포 성공 여부 확인

### Fly.io에서 확인
```bash
# 배포 상태 확인
flyctl status

# 로그 확인
flyctl logs

# 앱 URL 방문
# https://ai-contact-center-os.fly.dev/health
```

## 5. 배포 워크플로우 파일

워크플로우는 `.github/workflows/deploy.yml`에 정의되어 있습니다.

### 주요 설정
- **Remote-only build**: Fly.io의 원격 빌더 사용 (로컬 Docker 불필요)
- **HA disabled**: 단일 머신 배포 (개발용)
- **Auto-trigger**: main 브랜치 push 시 자동 실행

## 6. 수동 배포 (필요시)

GitHub Actions를 사용하지 않고 로컬에서 배포하려면:

```bash
# 간편 배포 스크립트
./scripts/deploy.sh

# 또는 직접 flyctl 사용
flyctl deploy --ha=false
```

## 7. 트러블슈팅

### 배포 실패 시

1. **Secret 확인**
   - `FLY_API_TOKEN`이 올바르게 설정되었는지 확인
   - 토큰이 만료되지 않았는지 확인

2. **로그 확인**
   - GitHub Actions 탭에서 실패한 워크플로우 로그 확인
   - Fly.io에서 `flyctl logs` 실행

3. **토큰 재생성** (필요시)
   ```bash
   flyctl auth token
   ```
   새 토큰으로 GitHub Secret 업데이트

### 일반적인 문제

| 문제 | 해결 방법 |
|------|----------|
| "unauthorized" 에러 | FLY_API_TOKEN Secret 확인 및 재설정 |
| 빌드 실패 | Dockerfile 및 requirements.txt 확인 |
| 메모리 부족 | fly.toml의 memory 설정 증가 (512mb) |

## 8. 배포 알림 (선택사항)

배포 성공/실패 알림을 받으려면:

1. **Slack 통합** (선택사항)
   - GitHub Actions Slack 앱 설치
   - Webhook URL을 Secret에 추가

2. **이메일 알림**
   - GitHub 계정 설정에서 자동 활성화됨

## 9. 비용 최적화

- **Auto-suspend**: 유휴 시 자동 중지 (활성화됨)
- **Single machine**: 1개 머신만 실행 (설정됨)
- **Shared CPU**: 저비용 CPU 사용 (설정됨)

현재 설정으로 월 $1-5 예상 (저사용량 기준)

## 10. 다음 단계

배포가 완료되면:

1. **헬스 체크 확인**
   ```bash
   curl https://ai-contact-center-os.fly.dev/health
   ```

2. **API 테스트**
   ```bash
   curl https://ai-contact-center-os.fly.dev/api/v1/assist/propose \
     -H "Content-Type: application/json" \
     -d '{...}'
   ```

3. **모니터링 설정**
   - Fly.io 대시보드에서 메트릭 확인
   - 필요시 알림 설정

---

## 참고 링크

- [Fly.io 공식 문서](https://fly.io/docs/)
- [GitHub Actions 문서](https://docs.github.com/en/actions)
- [Fly.io GitHub Actions](https://fly.io/docs/app-guides/continuous-deployment-with-github-actions/)
