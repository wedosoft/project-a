# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 개요

이 프로젝트는 RAG(Retrieval-Augmented Generation) 기술을 활용한 Freshdesk Custom App 백엔드 서비스입니다. Freshdesk 티켓과 지식베이스 문서를 기반으로 AI 기반 응답 생성 기능을 제공합니다.

**기술 스택:**
- FastAPI 백엔드 (async/await 패턴 사용)
- Qdrant 벡터 데이터베이스 (문서 저장 및 유사도 검색)
- OpenAI/Anthropic API (임베딩 및 LLM 응답)
- Docker 컨테이너화 (docker-compose 사용)

## 핵심 아키텍처 구성요소

### 코어 모듈 (backend/core/)
- `vectordb.py` - 회사별 데이터 격리가 가능한 Qdrant 벡터 데이터베이스 어댑터
- `embedder.py` - OpenAI 등을 활용한 문서 임베딩
- `retriever.py` - 문서 검색 및 FAQ 검색 (점수 설정 가능)
- `llm_router.py` - 다중 LLM 라우팅 및 fallback 지원 (Anthropic, OpenAI, Gemini)
- `context_builder.py` - LLM 컨텍스트 윈도우에 맞춘 문서 최적화

### 데이터 처리 (backend/data/)
- `data_processor.py` - 다양한 문서 형식 처리 (PDF, DOCX, 이미지)
- `attachment_processor.py` - OCR 지원 파일 첨부 처리

### Freshdesk 연동 (backend/freshdesk/)
- `fetcher.py` - 티켓 및 지식베이스용 Freshdesk API 클라이언트
- `optimized_fetcher.py` - 속도 제한이 있는 대규모 데이터 수집
- `run_collection.py` - 자동화된 데이터 수집 오케스트레이션

### API 레이어 (backend/api/)
- `main.py` - 쿼리 엔드포인트가 있는 FastAPI 애플리케이션
- `ingest.py` - 데이터 수집 및 처리 엔드포인트

## 주요 개발 명령어

### 환경 설정
```bash
# 가상환경 생성 및 활성화
python -m venv backend/venv
source backend/venv/bin/activate  # 또는 backend/activate.sh

# 의존성 설치
pip install -r backend/requirements.txt
```

### 애플리케이션 실행
```bash
# 개발 서버 (가상환경)
cd backend && python main.py

# Docker 환경
cd backend && docker-compose up -d

# 로그 확인
docker logs -f project-a
```

### 테스트
```bash
# 벡터 데이터베이스 테스트
cd backend && python tests/test_vectordb.py

# 검색 기능 테스트
cd backend && python tests/test_search.py

# Qdrant 연결 상태 확인
cd backend && python check_qdrant_status.py
```

### 데이터 수집
```bash
# 수동 데이터 수집
cd backend && python ingest.py

# Freshdesk 데이터 수집
cd backend/freshdesk && python run_collection.py

# 수집 진행 상황 모니터링
cd backend/freshdesk && bash scripts/monitor_collection.sh
```

## 환경 변수

필수 환경 변수 (`backend/.env` 파일 생성):
```
ANTHROPIC_API_KEY=your_anthropic_key
OPENAI_API_KEY=your_openai_key
FRESHDESK_DOMAIN=your_domain
FRESHDESK_API_KEY=your_freshdesk_key
```

## 아키텍처 참고사항

### 멀티테넌시
- 모든 벡터 작업에 데이터 격리를 위한 `company_id` 포함
- API 요청에서 `X-Company-ID` 헤더를 통해 회사 ID 전달

### 문서 타입
- `ticket` - 대화 내용이 포함된 Freshdesk 지원 티켓
- `kb` - 지식베이스 문서
- `faq` - 별도 점수 체계를 가진 자주 묻는 질문

### 캐싱 전략
- 쿼리 응답용 인메모리 TTL 캐시 (10분)
- 티켓 요약 캐시 (1시간)
- 성능 향상을 위한 파일 첨부 캐싱

### 검색 및 검색
- 티켓, KB 문서, FAQ를 결합한 하이브리드 검색
- 설정 가능한 유사도 임계값 및 결과 수
- LLM 토큰 제한에 맞춘 컨텍스트 최적화

## 주요 API 엔드포인트

- `POST /query` - 컨텍스트 검색이 포함된 메인 쿼리 엔드포인트
- `POST /query/blocks` - 프론트엔드용 블록 기반 응답 형식
- `GET /init/{ticket_id}` - 티켓 요약으로 컨텍스트 초기화
- `GET /similar_tickets/{ticket_id}` - 유사한 지원 티켓 찾기
- `GET /related_docs/{ticket_id}` - 관련 문서 검색
- `GET /metrics` - 모니터링용 Prometheus 메트릭

## 개발 가이드라인

### 코드 표준
- Python PEP 8 스타일 가이드 준수
- 모든 함수와 메서드에 타입 힌트 사용
- 내부 함수용 한국어 docstring 작성
- 외부 API 호출을 위한 async/await 패턴 구현

### 오류 처리
- 사용자 대상 오류 메시지는 한국어로 작성
- 구조화된 형식의 포괄적인 로깅
- LLM 및 검색 실패에 대한 우아한 fallback

### 성능 고려사항
- LLM 호출의 토큰 사용량 모니터링
- 요청 타임아웃 및 재시도 구현
- API 모니터링을 위한 prometheus 메트릭 사용
- 적절한 top_k 값으로 벡터 검색 최적화