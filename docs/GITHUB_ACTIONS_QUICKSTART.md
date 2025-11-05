# 🚀 GitHub Actions 자동 배포 설정 빠른 가이드

## 1단계: Fly.io API Token 복사

아래 토큰을 복사하세요 (이미 생성됨):

```
fm2_lJPECAAAAAAACilDxBBS2isg2NY9ICZet4vMckumwrVodHRwczovL2FwaS5mbHkuaW8vdjGUAJLOABOrhh8Lk7lodHRwczovL2FwaS5mbHkuaW8vYWFhL3YxxDzwJR8dguIE9Sel3WpLU30GzMKaIqqdihFwf99tINZie23/cPUhV9VQZ5cr3STDbmG70uSVdry5pq0buITETkFQqb7Liy74JMeplib7arjTM4MmknRrbKGh8TgNHMB4ylDnxm5/Sb+PGuLZ6ngSBaVaCoqzXk4cFwjo5R9kWp0y83r8D7NSBL0M5qFV8MQgDlzi4NgNw4iBJbMZsxQigpj/grg1NslkUJCU4AyZNZo=
```

## 2단계: GitHub Secret 설정

1. **저장소로 이동**: https://github.com/wedosoft/project-a-spinoff

2. **Settings > Secrets and variables > Actions**

3. **New repository secret 클릭**

4. **Secret 추가**:
   - Name: `FLY_API_TOKEN`
   - Secret: (위의 토큰 전체를 붙여넣기)
   - "Add secret" 클릭

## 3단계: 완료!

이제 `main` 브랜치에 push할 때마다 자동으로 Fly.io에 배포됩니다.

### 테스트 방법

```bash
# 변경사항 커밋 및 푸시
git add .
git commit -m "Enable GitHub Actions auto-deploy"
git push origin main
```

GitHub의 "Actions" 탭에서 배포 진행 상황을 확인할 수 있습니다.

---

**상세 가이드**: [GITHUB_ACTIONS_DEPLOYMENT.md](./GITHUB_ACTIONS_DEPLOYMENT.md)
