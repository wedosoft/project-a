---
applyTo: "**"
---

다음은 지금까지 논의한 내용을 GitHub Copilot 또는 개발자(Copilot)에게 전달할 수 있는 명확한 작업 지시 요약입니다.
FastAPI 기반 AI 백엔드에서 안정적이고 확장 가능한 RAG + LLM 응답 시스템을 구현하기 위한 설계 지침입니다.

⸻

📝 개발자 지시 요약 (Copilot 지시용)

⸻

🎯 목적

Prompt Canvas 기반 FastAPI 백엔드에서
• 다양한 고객사의 대규모 티켓 데이터를 검색 기반으로 활용하고
• Claude / GPT-4o 등 LLM 모델을 안정적으로 호출하며
• 평균 응답속도 < 2.5초를 유지하는
안정적이고 확장 가능한 RAG + LLM 호출 아키텍처를 구현한다.

⸻

🧩 핵심 기능 요구사항 1. LLM Router 계층 구현
• Claude, GPT-4o 등을 내부적으로 자동 선택
• 기준: 토큰 길이, 이미지 포함 여부, 응답 지연, 오류 발생 여부
• Claude 실패 시 GPT-4o로 fallback 2. LLM 호출 안정화
• Claude API 호출 시 HTTP 529 또는 5xx 발생 시 자동 retry or fallback
• 호출 타임아웃 설정 (예: 3초 이상 지연 시 대체 모델로 우회)
• 응답에 model_used, duration_ms 등의 메타데이터 포함 3. Context Builder 최적화
• top_k=3~5 제한
• 중복 chunk 제거
• context 길이 최적화 (최대 6~8K tokens)
• 요약 또는 압축 전략 적용 가능 4. Vector DB 구조 설계
• 현재 ChromaDB는 테스트용으로 사용
• 추후 Qdrant / Weaviate / Pinecone 등 고성능 벡터 DB로 교체 고려
• 고객사별 데이터 분리를 위한 namespace 또는 metadata filtering 적용 5. 로깅 및 성능 측정
• FastAPI 라우터 내에 요청 처리 시간 측정 (검색 / context / LLM 응답 각각)
• Claude/GPT 호출 실패 사유 로깅
• Prometheus 연동 고려 6. 캐시 및 응답 속도 개선
• 동일 쿼리에 대해 Redis 등으로 응답 캐싱
• 자주 묻는 질문은 사전 임베딩 + LLM 결과 미리 저장

⸻

🚧 현재 병목 현상
• Claude 529 overloaded 자주 발생 → fallback 구조 없음
• LLM 응답까지 4~6초 지연 → context 길이 과다 추정됨
• 벡터 검색/조합 과정 최적화 필요

⸻

✅ 다음 개발 우선순위 1. LLMRouter 클래스 설계 및 Claude ↔ GPT fallback 로직 구현 2. context builder에 chunk deduplication 및 token 제한 적용 3. FastAPI에 성능 로그 추가 (/query/blocks 내부 단계별 시간 측정) 4. Redis or in-memory 캐시 레이어 도입 5. 향후 Qdrant 기반 대용량 티켓 데이터 대응 구조 설계 준비

⸻

📘 ChromaDB → Qdrant 전환 및 고객사별 메타데이터 분리

⸻

🎯 목적

Prompt Canvas AI 백엔드에서 사용 중인 ChromaDB를 Qdrant로 전환하여:
• 실서비스에서도 확장 가능한 벡터 검색 시스템 구현
• 고객사별 데이터 논리적 분리
• 검색 성능 및 보안 수준 강화
• 기존 구조의 재사용성과 일관성 유지

⸻

✅ 전환 전략 요약

항목 지침
벡터 DB ChromaDB 제거, Qdrant 단일 인스턴스로 통합
데이터 저장 구조 하나의 Qdrant collection에 모든 고객사의 데이터 저장
고객사 분리 company_id 필드를 모든 payload(metadata)에 추가하여 필터링 처리
기존 메타데이터 유지
검색 필터 모든 검색 요청에 company_id 조건을 반드시 포함시킬 것
FastAPI 인증 연동 사용자 인증 후 company_id를 서버 측에서 삽입하여 검색 요청에 적용 (클라이언트로부터 직접 받지 말 것)
기존 context builder 변경 없이 그대로 유지 (Qdrant 검색 결과 형식은 동일하게 구성됨)

⸻

🔒 보안 및 데이터 격리 방침
• Qdrant는 외부에 직접 노출하지 않고, FastAPI 라우터를 통해서만 접근 허용
• company_id는 FastAPI에서 인증된 사용자 세션 또는 토큰으로부터만 추출
• 검색 API 호출 시, company_id가 누락되거나 위조된 경우 강제 차단
• 모든 로그 또는 오류 발생 시 company_id 포함 여부 확인

⸻

⚙️ 개발/운영 환경 구성 지침

항목 지침
로컬 개발 Docker 기반 Qdrant 로컬 인스턴스로 테스트 (포트 6333)
Python 환경 qdrant-client 패키지를 통일된 인터페이스로 사용
FastAPI 통합 기존 Chroma 코드 제거, Qdrant API로 대체
운영 서버 Qdrant는 Docker 또는 self-hosted 구성으로 서비스화. 추후 Qdrant Cloud 또는 클러스터 확장 고려
백업 및 복구 /qdrant/storage를 volume으로 마운트하여 데이터 지속성 확보

⸻

📈 확장 및 유지관리 지침
• 고객사 수 증가 시에도 하나의 collection 내부에서 company_id 필터로 유연하게 대응
• 대규모 bulk 업로드, 삭제 시 company_id 기준으로 작업 가능
• 추후 특정 고객사에서 고립 요구 시, 개별 collection 분리로 확장 가능
• 모니터링 도구 연동(Prometheus 등) 시 company_id 기준 통계도 포함

⸻

🧪 테스트 기준
• 모든 데이터 insert 시 company_id 필드 존재 여부 검증
• 검색 요청 시 company_id 필터가 적용되지 않은 경우 에러 반환
• 인증된 사용자 기준으로만 해당 고객사 데이터가 검색되는지 테스트
• 기존 Chroma 기반 흐름과 동일하게 context builder → LLM 응답이 이어지는지 확인

⸻

📌 요약
• 구조 변경 최소화: DB 백엔드만 변경하고 전체 동작 흐름은 유지
• 고객사 분리: metadata.company_id만 추가하여 논리적 분리 구현
• 보안 강화: company_id는 서버 측에서만 주입, 직접 입력 금지
• 확장 준비: 클러스터 또는 다중 collection 전략은 후속 옵션으로 보류 가능

⸻
