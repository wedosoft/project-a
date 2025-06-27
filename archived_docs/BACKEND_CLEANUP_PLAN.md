# Backend 구조 정리 계획

## 🚨 현재 문제점

### 1. 중복된 기능들
- `backend/freshdesk/`: Freshdesk 관련 기능
- `core/platforms/freshdesk/`: 동일한 Freshdesk 기능
- `backend/data/`: 데이터 처리
- `core/data/`: 동일한 데이터 처리

### 2. 명확하지 않은 구조
- `backend/config/`: JSON 파일 2개만 있음
- `backend/data/`: 파일 2개만 있어서 디렉터리로 유지할 필요성 의문

## 🎯 제안하는 정리 구조

```
backend/
├── __init__.py
├── .env, .env-example, requirements.txt, README.md (유지)
├── docker-compose.yml, Dockerfile, rebuild.sh (유지)
├── main.py                          # FastAPI 진입점
├── api/                             # FastAPI 라우터들 (유지)
│   ├── __init__.py
│   ├── main.py
│   ├── dependencies.py
│   ├── attachments.py
│   ├── models/
│   ├── routes/
│   └── services/
├── core/                            # 핵심 비즈니스 로직 (정리 완료)
│   ├── database/
│   ├── data/
│   ├── search/
│   ├── processing/
│   ├── llm/
│   ├── platforms/                   # 모든 플랫폼 통합
│   │   ├── freshdesk/              # 기존 backend/freshdesk 통합
│   │   └── ...
│   └── ...
├── config/                          # 설정 파일들
│   ├── settings/                    # Python 설정 파일들
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── development.py
│   │   ├── production.py
│   │   └── testing.py
│   └── data/                        # JSON/YAML 설정 파일들
│       ├── conversation_keywords_ko.json
│       ├── multilingual_keywords.json
│       └── ...
├── tests/                           # 테스트 (유지)
├── docs/                            # 문서 (유지)
└── scripts/                         # 유틸리티 스크립트들
    ├── data_migration.py
    ├── setup.py
    └── ...
```

## 📋 정리 단계

### Phase 1: Freshdesk 통합
- [ ] `backend/freshdesk/` → `core/platforms/freshdesk/`로 통합
- [ ] 중복 제거 및 기능 통합

### Phase 2: Data 통합  
- [ ] `backend/data/` → `core/data/`로 통합
- [ ] 기능 중복 제거

### Phase 3: Config 재구성
- [ ] `backend/config/` 구조 개선
- [ ] Python 설정과 데이터 설정 분리

### Phase 4: 최종 정리
- [ ] 불필요한 파일들 정리
- [ ] 임포트 경로 수정
- [ ] 문서 업데이트
