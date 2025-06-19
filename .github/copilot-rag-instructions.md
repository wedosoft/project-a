---
applyTo: "**"
---

# 🧠 Copilot RAG 시스템 최종 지침서

이 문서는 Freshdesk 기반 Copilot 시스템에서 유사 티켓 추천 및 LLM 요약 기능의 구조, 피드백 처리, 추천 개선 방식 등을 정리한 최종 개발 지침서입니다.

---

## 📌 시스템 전체 흐름

```
[Step 1] 데이터 수집 →
[Step 2] 티켓 + 컨버세이션 병합 →
[Step 3] LLM 요약 (이슈/해결 요약) →
[Step 4] 임베딩 → Vector DB 저장 →
[Step 5] Copilot UI에서 추천 →
[Step 6] 피드백 수집 및 반영
```

---

## 1. 데이터 수집 및 병합

- 티켓, 컨버세이션, 첨부파일 별도 수집
- 수집 시 `티켓 본문 + 컨버세이션`을 병합하여 하나의 문서로 구성
- JSON 형태로 로컬 저장 및 해시값으로 중복/변경 감지
- 이후 요약 및 벡터화 작업 수행

---

## 2. LLM 요약 및 벡터 저장

- Claude/OpenAI 등으로 이슈/솔루션 요약
- 요약된 결과만 VectorDB에 저장
- 원본 텍스트는 메타데이터로만 저장 (텍스트/HTML 불필요)
- 유사도 검색 시 요약 텍스트 기준으로 유사도 계산

---

## 3. 실시간 요약

- 상담사가 티켓을 열었을 때, 실시간으로 해당 티켓만 요약 요청
- 이 결과는 캐싱 가능 (선택)

---

## 4. 피드백 수집 설계

- 추천된 유사 티켓 전체 묶음에 대해 👍 / 👎 피드백 수집
- 프론트에서 아래 형태로 전송:

```json
{
  "type": "related_ticket_group",
  "feedback": "up",
  "ticket_context": 112345,
  "related_ticket_ids": [9876, 9855, 9822],
  "user_id": "agent_007",
  "source": "copilot_modal",
  "timestamp": "2025-06-18T17:30:00Z"
}
```

- 백엔드 `/feedback` API에 저장
- 이후 개선 알고리즘에 활용

---

## 5. 추천 정확도 개선 전략

### ✅ Step 1. 피드백 저장 및 정제

- query_id, 추천된 ticket ID, feedback (up/down) 저장
- 수천 건 단위로 정제된 학습셋 확보

---

### ✅ Step 2. 스코어 후처리 기반 개선

- 추천 결과 Top-K를 가져온 후, feedback 기반 가중치 조정

```python
def rerank(query_id, candidates):
    for c in candidates:
        if c.id in positive_feedback[query_id]:
            c.score += 0.1
        elif c.id in negative_feedback[query_id]:
            c.score -= 0.15
    return sorted(candidates, key=lambda x: x.score, reverse=True)
```

---

### ✅ Step 3. 임베딩 모델 개선

- BGE-M3, Instructor, E5 등 모델로 교체 시 feedback 기반 contrastive 학습 가능
- 또는 LLM reranking 적용

---

## 6. 추천 근거 처리

- 유사 티켓 또는 문서를 AI 응답의 “출처”로 명시할 수 있도록 저장
- 근거 클릭 시 HTML이 아닌 Freshdesk 원본 티켓 링크로 연결

---

## ✅ 요약 정리

| 항목           | 처리 방식                                      |
| -------------- | ---------------------------------------------- |
| 유사 티켓 수집 | 티켓+컨버세이션 병합, 해시값 기준 중복 방지    |
| 요약 처리      | LLM을 통해 이슈/해결 요약 생성                 |
| 저장 구조      | 요약 → 벡터 저장, 원본 → 메타데이터 저장       |
| 추천 알고리즘  | Vector 유사도 + rerank 가능                    |
| 피드백 반영    | 추천 묶음 단위로 👍/👎 수집 후 score 조정      |
| 개선 로드맵    | 학습셋 축적 → 임베딩 튜닝 or LLM reranker 도입 |

---

본 문서는 `.github/instructions/copilot_rag_instruction.md` 또는 `docs/dev/ai/copilot_rag.md` 경로에 배치하여 Copilot에서 참조하도록 설정할 수 있습니다.
