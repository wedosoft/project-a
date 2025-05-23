# Prompt Canvas 백엔드 프로젝트 구조

이 문서는 Prompt Canvas 백엔드 프로젝트의 폴더 구조와 주요 파일들을 설명합니다.

## 시작하기

### Freshdesk 티켓 수집 실행
```bash
# 간편 실행 스크립트
./freshdesk/scripts/collect_freshdesk.sh
```

이 스크립트는 다음 기능을 제공합니다:
1. 전체 수집(무제한) 실행
2. 수집 모니터링
3. 수집 가이드 문서 열기

## 폴더 구조

```
backend/
├── api/             # API 관련 코드
│   ├── main.py      # 메인 API 엔드포인트
│   └── ingest.py    # 데이터 수집 API
│
├── core/            # 핵심 AI 기능
│   ├── context_builder.py  # 컨텍스트 구성
│   ├── llm_router.py       # LLM 호출 및 라우팅
│   ├── embedder.py         # 임베딩 기능
│   ├── retriever.py        # 벡터 검색
│   └── vectordb.py         # 벡터 DB 연동
│
├── data/            # 데이터 처리 관련
│   ├── data_processor.py      # 데이터 전처리/후처리
│   └── attachment_processor.py # 첨부파일 처리
│
├── freshdesk/       # Freshdesk 티켓 수집 관련
│   ├── run_collection.py       # 수집 실행 스크립트
│   ├── optimized_fetcher.py    # 최적화된 티켓 수집기
│   ├── large_scale_config.py   # 대용량 설정
├── freshdesk/       # Freshdesk 티켓 수집 관련
│   ├── run_collection.py       # 수집 실행 스크립트
│   ├── optimized_fetcher.py    # 최적화된 티켓 수집기
│   ├── large_scale_config.py   # 대용량 설정
│   ├── scripts/                # 백그라운드 실행 스크립트
│   │   ├── collect_freshdesk.sh    # 수집 메뉴 인터페이스
│   │   ├── run_full_collection.sh  # 대용량 수집 실행
│   │   └── monitor_collection.sh   # 수집 모니터링
│   └── docs/                   # 문서
│       └── ...
│
├── docs/            # 문서 파일
│   ├── FRESHDESK_COLLECTION_GUIDE_INTEGRATED.md  # 통합 수집 가이드
│   ├── UNLIMITED_COLLECTION_GUIDE.md             # 무제한 수집 가이드
│   ├── FOLDER_STRUCTURE_GUIDE.md                 # 폴더 구조 가이드
│   └── response_format_design.md                 # 응답 포맷 설계
│
├── scripts/         # 유틸리티 스크립트
│   └── activate.sh  # 가상환경 활성화 스크립트
│
├── tests/           # 테스트 코드
│   ├── test_search.py
│   └── test_vectordb.py
│
├── config/          # 설정 파일
│   └── ...
│
└── ... (기타 파일들)
```

## 주요 파일 설명

### 핵심 AI 기능
- `context_builder.py`: 티켓 요약, 관련 문서, 유사 티켓 등 컨텍스트 구성
- `llm_router.py`: 프롬프트 구성 및 LLM 호출 관리
- `embedder.py`: 문서와 쿼리 임베딩 생성
- `retriever.py`: 벡터 DB에서 유사 문서/티켓 검색
- `vectordb.py`: 벡터 DB 연동 및 관리

### Freshdesk 티켓 수집
- `run_collection.py`: 티켓 수집 실행 스크립트
- `optimized_fetcher.py`: 대용량 티켓 수집 최적화 로직
- `large_scale_config.py`: 대용량 수집 설정

### 스크립트
- `freshdesk/scripts/run_full_collection.sh`: 500만건 이상 대용량 수집 백그라운드 실행
- `freshdesk/scripts/monitor_collection.sh`: 수집 진행 상황 모니터링
- `freshdesk/scripts/collect_freshdesk.sh`: 간편 실행 메뉴 인터페이스

## 참고 문서
- `docs/FRESHDESK_COLLECTION_GUIDE_INTEGRATED.md`: 티켓 수집 통합 가이드
- `docs/UNLIMITED_COLLECTION_GUIDE.md`: 무제한 수집 상세 가이드
- `docs/response_format_design.md`: 응답 포맷 설계 문서
