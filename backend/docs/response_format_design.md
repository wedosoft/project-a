# Prompt Canvas 연동을 위한 RAG + LLM 응답 포맷 설계안

## 목적

FastAPI → Prompt Canvas 연동 단계에서, AI 응답을 **의미 단위 블록**으로 구성하고 프론트엔드에서 쉽게 처리 가능하도록 응답 포맷을 설계한다.

이 설계는 향후 다음 기능까지 염두에 둔다:

* 블록 단위 응답 생성 및 렌더링
* AI 개선 (재작성) 기능
* 출처 및 관련 문서 링크 제공
* 이미지 블록 통합

---

## 응답 포맷 설계 (예시 JSON)

```json
{
  "blocks": [
    {
      "id": "blk_001",
      "type": "text",
      "content": "상위 티켓은 더 큰 범위의 문제나 요청을 나타내며...",
      "source": {
        "title": "부모 하위 티켓 보기",
        "url": "https://wedosoft.freshdesk.com/solution/articles/5000894916"
      }
    },
    {
      "id": "blk_002",
      "type": "text",
      "content": "하위 티켓은 상위 티켓에 포함되는 더 세부적인 문제나 요청입니다...",
      "source": {
        "title": "부모 및 자녀 티켓을 만드는 방법은 무엇인가요?",
        "url": "https://wedosoft.freshdesk.com/solution/articles/5000895289"
      }
    },
    {
      "id": "blk_003",
      "type": "image",
      "url": "https://wedosoft.freshdesk.com/images/ticket_hierarchy.png",
      "description": "상위/하위 티켓 관계 다이어그램"
    }
  ]
}
```

---

## 블록 타입 정의

| type             | 설명                          |
| ---------------- | --------------------------- |
| text             | 일반 텍스트 응답 블록                |
| image            | 이미지 블록 (context\_images 기반) |
| quote (optional) | 문서 원문 인용 (선택사항)             |
| list (optional)  | 목록 형태 응답 (선택사항)             |

---

## 향후 확장 고려 사항

* `style` 필드 추가 가능 → 재작성시 스타일 지정 (예: "친근하게", "공식적으로")
* `ai_generated` 플래그 → AI 개선 블록 구분
* `timestamp` → 생성 시점 관리 (히스토리용)

---

## 이미지/첨부파일 응답 설계 정책
- 벡터DB에는 pre-signed URL(attachment_url)을 저장하지 않고, attachment_id, name, content_type, size, updated_at 등 메타데이터만 저장합니다.
- 프론트엔드에서 이미지를 표시할 때마다 Freshdesk API로 최신 pre-signed URL을 발급받아야 합니다.
- description(HTML) 내 인라인 이미지도 URL이 아닌 id 등만 별도 필드에 저장하며, 실제 URL은 표시 시점에 발급받아야 합니다.

---

## 결론

프론트엔드가 별도의 로직 없이 블록을 렌더링하고, 이후 재작성 기능도 쉽게 붙일 수 있도록 **백엔드에서 블록 기반 응답 포맷으로 전환**하는 것이 최적 경로이다.

이 설계를 기반으로 FastAPI 응답 구조를 개선 후 프론트엔드 연동을 진행한다.