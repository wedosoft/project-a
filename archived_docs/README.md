# 📁 아카이브된 문서들

> **아카이브 날짜**: 2025-06-27  
> **사유**: docs 폴더 정리 - 45개 → 10개 핵심 문서로 축소

## 📋 아카이브 분류

### 🗂️ 완료된 작업 보고서 (ORM 통합 관련)

- `ORM_INTEGRATION_COMPLETE.md`
- `ORM_INTEGRATION_SUCCESS_REPORT.md`
- `ORM_CLOUD_MIGRATION_PLAN.md`
- `INTEGRATED_ARCHITECTURE_COMPLETION_REPORT.md`

### 📚 구버전 가이드 및 계획서

- `BACKEND_CLEANUP_PLAN.md`
- `CORE_CLEANUP_PLAN.md`
- `INTEGRATION_PLAN.md`
- `SQLITE_POSTGRESQL_MIGRATION_GUIDE.md`
- `ENHANCED_COLLECTION_GUIDE.md`
- `LARGE_SCALE_SUMMARIZATION_GUIDE.md`

### 🔧 특정 기능 구현 가이드

- `INLINE_IMAGES_IMPLEMENTATION.md`
- `LANGUAGE_ARCHITECTURE_DESIGN.md`
- `MULTITENANT_ARCHITECTURE_GUIDE.md`
- `MULTITENANT_ISOLATION_GUIDE.md`
- `SCALABLE_API_KEY_MANAGEMENT.md`
- `SAAS_LICENSE_SCHEMA_DESIGN.md`

### 🛠️ 설정 및 설치 가이드

- `COPILOT_MCP_GUIDE.md`
- `GITHUB_COPILOT_MCP_SETUP.md`
- `MCP_INSTALLATION_GUIDE.md`
- `MCP_SECURITY_GUIDE.md`
- `SETUP.md`

### 📝 세션 및 워크플로우 문서

- `NEW_SESSION_INSTRUCTIONS.md`
- `NEXT_SESSION_GUIDE-20250627-2118.md`
- `SESSION_HANDOVER_GUIDE.md`

### 🤖 AI 지침서 (중복)

- `copilot-instructions.md`
- `copilot-rag-instructions.md`
- `copilot-setup-complete.md`
- `enhance-id.instructions.md`
- `implementation-guide-legacy.instructions.md`
- `langchain-guide.instructions.md`
- `revison-details.instructions.md`

### 🧠 LLM 개선 문서

- `llm-conversation-filtering-improvement.md`
- `smart-filtering-implementation.md`

### 🔧 기타 설정 파일들

- `mcp-servers-config.md`
- `task-master-command.txt`
- `CLAUDE.md`
- `CLOUD_POSTGRESQL_ISSUES.md`

## 🔄 복원 방법

### Git에서 복원

```bash
# 특정 파일 복원 (커밋 히스토리에서)
git log --oneline -- docs/[파일명]
git checkout [커밋해시] -- docs/[파일명]
```

### 아카이브에서 복원

```bash
# 아카이브에서 docs로 다시 이동
mv archived_docs/[파일명] docs/
```

## 🎯 현재 활성 문서 (10개)

### 📊 프로젝트 관리

- `MASTER_STATUS.md` - 프로젝트 마스터 현황
- `CURRENT_ISSUES.md` - 현재 이슈 관리
- `ROADMAP.md` - 프로젝트 로드맵

### 🔧 개발 가이드

- `DEVELOPMENT_GUIDE.md` - 개발 가이드
- `PROJECT_RULES.md` - 프로젝트 규칙
- `ENVIRONMENT_SETUP.md` - 환경 설정
- `SECRETS_SETUP.md` - 시크릿 설정

### 📄 스키마 및 설정

- `INTEGRATED_OBJECT_SCHEMA.sql` - 현재 데이터베이스 스키마
- `SAAS_SCHEMA.sql` - SaaS 스키마
- `github-copilot-mcp-config.json` - GitHub Copilot 설정

---

> 💡 **정리 원칙**: 현재 활발히 사용 중이거나 즉시 필요한 문서만 유지하고,
> 완료된 작업이나 구버전 정보는 과감히 아카이브하여 혼란을 방지합니다.

> 🔄 **언제든 복원 가능**: Git 히스토리나 archived_docs 폴더에서
> 필요 시 언제든지 복원할 수 있습니다.
