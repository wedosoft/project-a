# 🎯 Freddy UI Reference - 유사 티켓 & 지식베이스 UI 패턴

> **목적**: Freshdesk Freddy AI의 유사 티켓/지식베이스 UI 패턴을 분석하여 프론트엔드 설계 시 참조할 수 있도록 상세히 문서화
> **업데이트**: 2025-01-05 - Vector DB 단독 아키텍처 완성, 원본 텍스트 중심 구조 반영

## 📋 **Freddy 유사 티켓 UI 구조**

### **Vector DB 데이터 구조 (2025-01-05 최신)**

#### **검색 결과 데이터 형태 (Vector DB 단독 모드):**
```json
{
  "id": "104",
  "content": "제목: 전자결재 결재 완료시 PDF 파일 수신 오류의 건 설명: 안녕하세요. 전자결재 완료 후 PDF 파일을 수신하는 과정에서 문제가 발생했습니다... 대화: 고객님, 확인해보겠습니다...",
  "score": 0.92,
  "original_id": "104",
  "doc_type": "ticket",
  "tenant_id": "default",
  "platform": "freshdesk",
  "subject": "전자결재 결재 완료시 PDF 파일 수신 오류의 건",
  "status": 5,
  "priority": 1,
  "has_attachments": false,
  "conversation_count": 3,
  "created_at": "2015-04-10T08:42:14Z",
  "updated_at": "2015-09-03T01:08:49Z",
  "extended_metadata": {
    "requester_id": 5009265402,
    "company_id": 500051717,
    "responder_id": 5001625134,
    "group_id": 5000271523,
    "attachments": [],
    "conversations": [
      {
        "id": 27002697075,
        "body_text": "고객님, 전자결재 PDF 파일 수신 문제를 확인해보겠습니다...",
        "from_email": "support@company.com",
        "created_at": "2015-04-10T09:15:23Z"
      }
    ],
    "custom_fields": {
      "department": "IT",
      "issue_category": "system_error"
    },
    "tags": ["pdf", "electronic_approval", "email"],
    "description": "안녕하세요. 전자결재 완료 후 PDF 파일을 수신하는 과정에서...",
    "description_text": "안녕하세요. 전자결재 완료 후 PDF 파일을 수신하는 과정에서...",
    "type": "incident",
    "source": 2,
    "fr_escalated": false,
    "spam": false
  }
}
```

#### **UI 매핑 규칙 (Vector DB 단독 모드):**
- **Confidence Score**: `Math.round(score * 100)%` (예: 0.92 → 92%)
- **티켓 번호**: `original_id` 필드 사용 (플랫폼 원본 ID)
- **제목**: `subject` 필드 사용
- **원본 내용**: `content` 필드 사용 (요약이 아닌 원본 텍스트, title+description+conversations 통합)
- **메타데이터**: `extended_metadata`에서 필요한 정보 추출
- **상태 정보**: `status`, `priority`, `has_attachments`, `conversation_count` 등 루트 레벨 필드 활용
- **대화 정보**: `extended_metadata.conversations` 배열에서 상세 대화 내역 추출
- **첨부파일**: `extended_metadata.attachments` 배열에서 첨부파일 정보 추출
- **커스텀 필드**: `extended_metadata.custom_fields` 객체에서 사용자 정의 필드 추출

### **1단계: 목록 화면 (List View)**

#### **레이아웃 구조:**
```
┌─────────────────────────────────────────┐
│ Similar Tickets (3)                     │ ← 헤더: 개수 표시
├─────────────────────────────────────────┤
│ ┌─────────────────────────────────────┐ │
│ │ [92%] Ticket #104                   │ │ ← score * 100 + original_id
│ │ 전자결재 결재 완료시 PDF 파일 수신 오류  │ │ ← subject 필드
│ │ 첨부파일: 없음 • 우선순위: 낮음        │ │ ← has_attachments, priority
│ │ 상태: 해결됨 • 작성: 2015-04-10      │ │ ← status, created_at
│ └─────────────────────────────────────┘ │
│ ┌─────────────────────────────────────┐ │
│ │ [89%] Ticket #105                   │ │ ← 두 번째 유사 티켓
│ │ 로그인 문제 해결 요청                 │ │
│ │ 첨부파일: 2개 • 우선순위: 높음        │ │
│ │ 상태: 진행중 • 작성: 2015-04-11      │ │
│ └─────────────────────────────────────┘ │
│ ┌─────────────────────────────────────┐ │
│ │ [85%] Ticket #106                   │ │ ← 세 번째 유사 티켓
│ │ 비밀번호 재설정 요청                  │ │
│ │ 첨부파일: 1개 • 우선순위: 보통        │ │
│ │ 상태: 대기중 • 작성: 2015-04-12      │ │
│ └─────────────────────────────────────┘ │
└─────────────────────────────────────────┘
```

#### **UI 컴포넌트 상세:**

**카드 구조:**
- **Confidence Badge**: `[92%]` - 왼쪽 상단, 파란색 배경
- **티켓 번호**: `Ticket #104` - 굵은 글씨, 클릭 가능 (original_id 사용)
- **제목**: `subject` 필드, 일반 글씨, 2줄 제한
- **메타데이터 1줄**: 첨부파일 유무, 우선순위 (has_attachments, priority)
- **메타데이터 2줄**: 상태, 작성일 (status, created_at)

**상호작용:**
- **클릭**: 전체 카드 영역 클릭 가능
- **호버**: 미세한 그림자 효과
- **선택**: 카드 배경색 변경 (연한 파란색)

### **2단계: 상세 화면 (Detail View)**

#### **레이아웃 구조:**
```
┌─────────────────────────────────────────┐
│ ← Back    Similar Tickets    → Next     │ ← 네비게이션 바
├─────────────────────────────────────────┤
│ Ticket #104                             │ ← original_id (큰 제목)
│ 전자결재 결재 완료시 PDF 파일 수신 오류     │ ← subject 필드
├─────────────────────────────────────────┤
│ 원본 내용 (Original Content)            │ ← Vector DB content 필드 헤더
│ ┌─────────────────────────────────────┐ │
│ │ 제목: 전자결재 결재 완료시 PDF 파일   │ │ ← content 필드 (원본 텍스트)
│ │ 수신 오류의 건                       │ │
│ │ 설명: 안녕하세요. 전자결재를 완료한  │ │
│ │ 후 PDF 파일이 수신되지 않는 문제가   │ │
│ │ 있습니다. 확인 부탁드립니다.         │ │
│ │ 대화: 고객센터에서 안내드린 방법으로  │ │
│ │ 해결되었습니다.                     │ │
│ └─────────────────────────────────────┘ │
├─────────────────────────────────────────┤
│ 상세 정보 (Extended Metadata)           │ ← extended_metadata 활용
│ ┌─────────────────────────────────────┐ │
│ │ • 요청자: ID 5009265402             │ │
│ │ • 회사: ID 500051717                │ │
│ │ • 첨부파일: 없음                    │ │
│ │ • 커스텀 필드: {...}                │ │
│ │ • 태그: [...]                      │ │
│ │ • 해결일: 2015-09-03                │ │
│ └─────────────────────────────────────┘ │
└─────────────────────────────────────────┘
```

#### **네비게이션 컴포넌트:**
- **Back 버튼**: `← Back` - 목록으로 돌아가기
- **제목**: `Similar Tickets` - 중앙 정렬
- **Next/Prev**: `→ Next` / `← Prev` - 다음/이전 유사 티켓으로 이동

#### **컨텐츠 섹션:**
1. **티켓 헤더**: original_id + subject
2. **원본 내용**: Vector DB `content` 필드 표시 (요약 없이 원본 텍스트)
3. **상세 정보**: `extended_metadata`에서 추출한 풍부한 정보
4. **첨부파일 정보**: attachments 배열 정보 (있는 경우)

> **중요**: Vector DB 단독 모드에서는 LLM 요약이 없으므로 `content` 필드의 원본 텍스트를 그대로 표시

## 📚 **Freddy 지식베이스 UI 구조 (Vector DB 단독 모드)**

### **KB 문서 데이터 형태:**
```json
{
  "id": "5007594526",
  "content": "제목: How to Reset Customer Password 설명: This article explains step by step process for resetting customer passwords...",
  "score": 0.89,
  "original_id": "5007594526",
  "doc_type": "article",
  "tenant_id": "default",
  "platform": "freshdesk",
  "title": "How to Reset Customer Password",
  "status": 2,
  "has_attachments": false,
  "created_at": "2020-01-15T14:30:00Z",
  "updated_at": "2024-12-15T09:45:00Z",
  "extended_metadata": {
    "category_name": "Authentication",
    "category_id": 5000271523,
    "folder_id": 5000045722,
    "views": 1200,
    "thumbs_up": 45,
    "thumbs_down": 3,
    "author_id": 5001234567,
    "description": "This article explains step by step process for resetting customer passwords in our system. It covers both admin reset and self-service options...",
    "description_text": "This article explains step by step process for resetting customer passwords...",
    "seo_data": {
      "meta_title": "Password Reset Guide",
      "meta_description": "Complete guide for password reset procedures"
    },
    "tags": ["password", "reset", "authentication", "security"],
    "attachments": [],
    "art_type": 1,
    "thumbs_up": 45,
    "thumbs_down": 3
  }
}
```

### **KB UI 매핑 규칙:**
- **문서 제목**: `title` 필드 사용
- **원본 내용**: `content` 필드 사용 (요약이 아닌 원본 텍스트)
- **카테고리**: `extended_metadata.category_name` 사용
- **조회수**: `extended_metadata.views` 사용
- **평가**: `extended_metadata.thumbs_up`, `thumbs_down` 사용
- **태그**: `extended_metadata.tags` 배열 사용
- **SEO 정보**: `extended_metadata.seo_data` 객체 사용

### **1단계: 목록 화면 (List View)**

#### **레이아웃 구조:**
```
┌─────────────────────────────────────────┐
│ Knowledge Base Articles (5)             │ ← 헤더: 개수 표시
├─────────────────────────────────────────┤
│ ┌─────────────────────────────────────┐ │
│ │ 📄 How to Reset Customer Password   │ │ ← 아이콘 + 제목
│ │ Category: Authentication            │ │ ← 카테고리
│ │ Updated: 2 days ago • Views: 1.2K   │ │ ← 메타데이터
│ └─────────────────────────────────────┘ │
│ ┌─────────────────────────────────────┐ │
│ │ 📄 Browser Compatibility Issues     │ │
│ │ Category: Technical Support        │ │
│ │ Updated: 1 week ago • Views: 856    │ │
│ └─────────────────────────────────────┘ │
│ ┌─────────────────────────────────────┐ │
│ │ 📄 Portal Access Troubleshooting   │ │
│ │ Category: Login Issues             │ │
│ │ Updated: 3 days ago • Views: 2.1K   │ │
│ └─────────────────────────────────────┘ │
└─────────────────────────────────────────┘
```

### **2단계: 상세 화면 (Detail View)**

#### **레이아웃 구조:**
```
┌─────────────────────────────────────────┐
│ ← Back    Knowledge Base    → Next      │ ← 네비게이션 바
├─────────────────────────────────────────┤
│ 📄 How to Reset Customer Password       │ ← 문서 제목
│ Category: Authentication                │ ← 카테고리
│ Last Updated: 2 days ago                │ ← 업데이트 정보
├─────────────────────────────────────────┤
│ ┌─────────────────────────────────────┐ │
│ │                                     │ │
│ │     KB 문서 원문 내용 전체          │ │ ← 원본 HTML/텍스트 그대로 표시
│ │     (HTML 형태로 렌더링)            │ │
│ │                                     │ │
│ │     - 이미지, 링크, 포맷팅 유지     │ │
│ │     - 스크롤 가능한 영역             │ │
│ │     - 원본 스타일 보존              │ │
│ │                                     │ │
│ └─────────────────────────────────────┘ │
└─────────────────────────────────────────┘
```

#### **구현 방식:**
- **원문 표시**: DB 또는 실시간 API에서 가져온 KB 문서 원본 HTML/텍스트
- **스타일 보존**: Freshdesk KB 원본 포맷팅 유지
- **스크롤**: 긴 문서의 경우 세로 스크롤 지원

## � **UI/UX 기본 패턴 (참고용)**

### **레이아웃 기준:**
- **고정 영역**: Freshdesk 티켓 페이지 우측 사이드바 영역
- **너비**: 고정폭 (약 400-500px)
- **높이**: 가변 (스크롤 지원)

### **기본 스타일 참고:**
- **카드 간격**: `12px`
- **카드 패딩**: `16px` 
- **내부 요소 간격**: `8px`

### **상호작용:**
- **호버**: 미세한 그림자 효과
- **클릭**: 배경색 변경
- **전환**: `transition: all 0.2s ease`

## 🔄 **사용자 플로우 (User Flow)**

### **유사 티켓 플로우:**
```
모달 열기 → 목록 보기 → 카드 클릭 → 상세 보기 → 다음/이전 또는 뒤로가기
    ↓           ↓           ↓           ↓
  로딩      즉시 표시    0.1초      캐시된 데이터
```

### **지식베이스 플로우:**
```
모달 열기 → 목록 보기 → 문서 클릭 → 원문 보기 → 다음/이전 또는 뒤로가기
    ↓           ↓           ↓           ↓
  로딩      즉시 표시   원문 로딩   캐시된 원문
```

## 📱 **구현 고려사항**

### **고정 영역 특성:**
- Freshdesk 티켓 페이지 우측 사이드바에 고정 배치
- 반응형 디자인 불필요 (고정 너비 영역)
- 세로 스크롤만 고려하면 됨

### **접근성 (Accessibility):**
- 키보드 네비게이션 지원
- 스크린 리더 호환
- focus 표시자 명확히

## 🚀 **프론트엔드 구현 가이드라인 (Vector DB 단독 모드)**

### **컴포넌트 구조:**
```
SimilarTicketsContainer
├── ListView
│   ├── Header (제목 + 개수)
│   ├── TicketCard[] (반복)
│   └── LoadingState
└── DetailView
    ├── NavigationBar
    ├── TicketHeader
    └── OriginalContent (원본 텍스트 표시 - content 필드)

KnowledgeBaseContainer  
├── ListView
│   ├── Header (제목 + 개수)
│   ├── ArticleCard[] (반복)
│   └── LoadingState
└── DetailView
    ├── NavigationBar
    ├── ArticleHeader
    └── OriginalContent (원본 HTML 렌더링 - content 필드)
```

### **상태 관리 (Vector DB 단독 모드):**
```javascript
// 유사 티켓 (Vector DB 기반)
const similarTicketsState = {
  view: 'list' | 'detail',
  selectedIndex: number,
  tickets: VectorDBTicket[],
  loading: boolean,
  error: string | null
}

// Vector DB 티켓 타입
interface VectorDBTicket {
  id: string;
  content: string;          // 원본 텍스트 (title + description + conversations)
  score: number;
  original_id: string;
  doc_type: 'ticket';
  subject: string;
  status: number;
  priority: number;
  has_attachments: boolean;
  conversation_count: number;
  created_at: string;
  updated_at: string;
  extended_metadata: {
    requester_id: number;
    company_id: number;
    conversations: Conversation[];
    attachments: Attachment[];
    custom_fields: Record<string, any>;
    tags: string[];
    [key: string]: any;
  };
}

// 지식베이스 (Vector DB 기반)
const kbState = {
  view: 'list' | 'detail',
  selectedIndex: number,
  articles: VectorDBArticle[],
  loading: boolean,
  error: string | null
}

// Vector DB KB 문서 타입
interface VectorDBArticle {
  id: string;
  content: string;          // 원본 텍스트 (title + description)
  score: number;
  original_id: string;
  doc_type: 'article';
  title: string;
  status: number;
  has_attachments: boolean;
  created_at: string;
  updated_at: string;
  extended_metadata: {
    category_name: string;
    category_id: number;
    views: number;
    thumbs_up: number;
    thumbs_down: number;
    description: string;
    description_text: string;
    tags: string[];
    attachments: Attachment[];
    seo_data: {
      meta_title: string;
      meta_description: string;
    };
    [key: string]: any;
  };
}
  view: 'list' | 'detail', 
  selectedIndex: number,
  articles: KBArticle[],
  loading: boolean,
  error: string | null
}
```

### **데이터 구조:**
```javascript
// 유사 티켓 (YAML 템플릿 기반 요약 포함)
interface SimilarTicket {
  id: string;
  title: string;
  summary: string;        // YAML 템플릿으로 생성된 AI 요약
  description: string;    // 원본 설명
  resolution?: string;    // 해결 방법 (있는 경우)
  confidence: number;     // 0-1 점수
  metadata: {
    groups: string[];
    agents: string[];
    status: string;
    created: string;
    resolved?: string;
  }
}

// 지식베이스 (원문 내용 포함)
interface KBArticle {
  id: string;
  title: string;
  content: string;        // 원본 HTML/텍스트 내용
  category: string;
  metadata: {
    updated: string;
    views?: number;
    author?: string;
  }
}
```

---

**💡 이 문서는 Freddy UI 패턴을 참조하여 일관된 사용자 경험을 제공하기 위한 가이드라인입니다.**

**주요 구현 방향:**
- **유사 티켓**: YAML 템플릿 기반 AI 요약 표시
- **지식베이스**: 원본 HTML/텍스트 내용 그대로 표시
- **레이아웃**: Freshdesk 우측 사이드바 고정 영역에 최적화
