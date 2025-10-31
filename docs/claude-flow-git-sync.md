# Claude-Flow Git 동기화 가이드

## 📦 동기화 파일 목록

### 필수 (메모리 상태)
- `.swarm/memory.db` - 모든 학습 및 메모리
- `.hive-mind/hive.db` - Hive-Mind 상태
- `.hive-mind/sessions/` - 세션 정보 (활성 세션 제외)
- `.hive-mind/memory/` - 프로젝트 메모리

### 권장 (설정)
- `.mcp.json` - MCP 서버 설정
- `claude-flow` - 실행 파일
- `memory/` - 추가 메모리

## 🔄 워크플로우

### 작업 시작 전
```bash
# 항상 최신 메모리 가져오기
git pull

# Claude-Flow 상태 확인
npx claude-flow@alpha memory status --reasoningbank
npx claude-flow@alpha hive-mind status
```

### 작업 중
```bash
# Claude와 대화하며 작업
# 메모리가 자동으로 .swarm/memory.db에 저장됨
```

### 작업 완료 후
```bash
# 메모리 동기화
git add .swarm/memory.db .hive-mind/
git commit -m "feat: Update memory - [작업 내용]"
git push
```

## ⚠️ 충돌 방지

### 규칙 1: Pull First
```bash
# 항상 작업 전에 pull
git pull
```

### 규칙 2: 한 곳에서만
```bash
# 동시에 여러 곳에서 작업하지 않기
# SQLite는 바이너리 파일이라 충돌 해결 어려움
```

### 규칙 3: 자주 커밋
```bash
# 중요한 학습 후 즉시 커밋
git add .swarm/memory.db && git commit -m "Save important knowledge" && git push
```

## 🔧 충돌 발생 시

### 옵션 1: 한쪽 선택
```bash
# 원격(remote) 버전 사용
git checkout --theirs .swarm/memory.db
git add .swarm/memory.db
git commit

# 또는 로컬(local) 버전 사용
git checkout --ours .swarm/memory.db
git add .swarm/memory.db
git commit
```

### 옵션 2: Export/Import
```bash
# 컴퓨터 A에서
npx claude-flow@alpha memory export --output memory-backup-a.json

# 컴퓨터 B에서
npx claude-flow@alpha memory export --output memory-backup-b.json

# 두 파일을 수동으로 병합 후
npx claude-flow@alpha memory import --input merged-memory.json
```

## 📊 메모리 백업 전략

### 정기 백업
```bash
# 주간 백업 스크립트
#!/bin/bash
DATE=$(date +%Y%m%d)
cp .swarm/memory.db ".swarm/backups/memory-${DATE}.db"
cp .hive-mind/hive.db ".hive-mind/backups/hive-${DATE}.db"

# Git에 백업 커밋
git add .swarm/backups/ .hive-mind/backups/
git commit -m "backup: Weekly memory backup ${DATE}"
git push
```

### Export 백업
```bash
# JSON으로 백업 (사람이 읽을 수 있음)
npx claude-flow@alpha memory export --output "backups/memory-$(date +%Y%m%d).json"
```

## 🌐 팀 협업 시나리오

### 시나리오 1: 개인 프로젝트
```bash
# 간단: 그냥 pull/push
git pull
# 작업
git add .swarm/ .hive-mind/
git commit -m "Update memory"
git push
```

### 시나리오 2: 팀 프로젝트
```bash
# 네임스페이스 분리 사용
"이 내용을 'frontend' 네임스페이스에 저장해줘"
"저 내용을 'backend' 네임스페이스에 저장해줘"

# 각자 담당 영역만 수정
# 충돌 가능성 감소
```

### 시나리오 3: 지식 공유만
```bash
# DB 파일은 제외하고 export만 공유
npx claude-flow@alpha memory export --output docs/shared-knowledge.json

git add docs/shared-knowledge.json
git commit -m "docs: Share project knowledge"
git push
```

## ✅ 체크리스트

### 하루 시작
- [ ] `git pull` 실행
- [ ] `npx claude-flow@alpha memory status` 확인
- [ ] 최신 메모리 상태 확인됨

### 하루 종료
- [ ] 중요한 학습/설계 저장 확인
- [ ] `git add .swarm/ .hive-mind/` 실행
- [ ] 의미있는 커밋 메시지 작성
- [ ] `git push` 실행

### 컴퓨터 전환 시
- [ ] 기존 컴퓨터에서 push 완료
- [ ] 새 컴퓨터에서 pull 실행
- [ ] Claude-Flow 상태 확인

## 🎯 Best Practices

1. **자주 동기화**: 중요한 작업 후 즉시 push
2. **명확한 커밋**: 무엇을 학습/저장했는지 메시지에 기록
3. **충돌 방지**: 항상 pull first
4. **백업 유지**: 주기적으로 export 백업
5. **네임스페이스 활용**: 팀 작업 시 영역 분리
