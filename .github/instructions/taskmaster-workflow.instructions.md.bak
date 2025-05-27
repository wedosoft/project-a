# 🚀 Task Master 개발 워크플로우 가이드

> Cursor와 Roo Code의 규칙 파일에서 추출한 Task Master 워크플로우 가이드입니다.

## 📝 Task Master 작업 관리 방법

Task Master는 두 가지 방식으로 상호작용할 수 있습니다:

1. **MCP 서버 (권장)**: 
   - Cursor, VS Code 등 통합 개발 환경에서 사용
   - MCP 서버를 통해 구조화된 데이터와 오류 처리 제공
   - 더 나은 성능과 통합성 제공

2. **CLI 명령어**:
   - 터미널에서 직접 명령어 입력 방식
   - `npm install -g task-master-ai`로 전역 설치하거나
   - `npx task-master-ai` 명령어로 로컬 실행

## 🔄 표준 개발 워크플로우

### 1. 프로젝트 초기화
- **MCP**: `initialize_project` 도구 사용
- **CLI**: `task-master init` 또는 `task-master parse-prd --input='<prd-file.txt>'`
- PRD 문서를 기반으로 초기 tasks.json 생성

### 2. 작업 조회 및 선택
- **MCP**: `get_tasks`, `next_task` 도구 사용
- **CLI**: `task-master list`, `task-master next`
- 상태, ID, 우선순위 등을 확인하여 다음 작업 선택

### 3. 작업 복잡도 분석
- **MCP**: `analyze_project_complexity`, `complexity_report` 도구 사용
- **CLI**: `task-master analyze-complexity --research`, `task-master complexity-report`
- 복잡한 작업은 하위 작업으로 분할 필요 여부 판단

### 4. 작업 세분화
- **MCP**: `expand_task`, `clear_subtasks` 도구 사용
- **CLI**: `task-master expand --id=<id> --force --research`, `task-master clear-subtasks --id=<id>`
- 복잡한 작업을 관리하기 쉬운 하위 작업으로 분해

### 5. 코드 구현
- 작업 파일(`tasks/`)에 명시된 상세 요구사항에 따라 구현
- 모든 의존성 작업(`dependencies`)이 완료되었는지 확인
- 프로젝트 표준과 지침 준수

### 6. 작업 상태 관리
- **MCP**: `set_task_status` 도구 사용
- **CLI**: `task-master set-status --id=<id> --status=done`
- 완료된 작업은 'done' 상태로 표시

### 7. 작업 업데이트 및 추가
- **MCP**: `update`, `update_task`, `add_task`, `add_subtask` 도구 사용
- **CLI**: 
  - `task-master update --from=<id> --prompt="..."`
  - `task-master update-task --id=<id> --prompt="..."`
  - `task-master add-task --prompt="..." --research`
  - `task-master add-subtask --parent=<id> --title="..."`
- 구현 중 발견된 변경사항이나 추가 작업 반영

### 8. 의존성 관리
- **MCP**: `add_dependency`, `remove_dependency`, `validate_dependencies`, `fix_dependencies` 도구 사용
- **CLI**: 
  - `task-master add-dependency --id=<id> --dependsOn=<otherId>`
  - `task-master remove-dependency --id=<id> --dependsOn=<otherId>`
  - `task-master validate-dependencies`
  - `task-master fix-dependencies`
- 작업 간 의존성 관계를 명확히 하고 유효성 검증

### 9. 작업 파일 생성
- **MCP**: `generate` 도구 사용
- **CLI**: `task-master generate`
- tasks.json 파일을 기반으로 개별 작업 파일 생성

## 🔍 참고할 만한 명령어

| 기능 | MCP 도구 | CLI 명령어 |
|------|---------|-----------|
| 작업 목록 조회 | `get_tasks` | `task-master list` |
| 다음 작업 추천 | `next_task` | `task-master next` |
| 작업 상세 조회 | `get_task` | `task-master show <id>` |
| 작업 완료 처리 | `set_task_status` | `task-master set-status --id=<id> --status=done` |
| 하위 작업 추가 | `add_subtask` | `task-master add-subtask --parent=<id> --title="..."` |
| 새 작업 추가 | `add_task` | `task-master add-task --prompt="..."` |
| 작업 확장 | `expand_task` | `task-master expand --id=<id> --research` |
| 복잡도 분석 | `analyze_project_complexity` | `task-master analyze-complexity` |

이 문서는 Cursor와 Roo Code에서 사용하던 Task Master 관련 규칙을 VS Code에서도 활용할 수 있도록 정리한 것입니다.
