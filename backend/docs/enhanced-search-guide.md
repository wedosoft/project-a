# 고급 자연어 검색 기능 가이드

## 📋 개요

기존 `/api/query` 엔드포인트에 고급 자연어 검색 기능이 통합되었습니다. 상담원이 자연어로 구체적인 요구사항을 표현하면 이를 정확한 검색 조건으로 변환하여 결과를 반환합니다.

## 🚀 사용법

### 기본 구조

```bash
POST /query
```

```json
{
  "query": "자연어 검색 쿼리",
  "enhanced_search": true,  // 고급 검색 활성화
  "enhanced_search_type": "auto",  // 또는 "attachment", "category", "solution"
  // 추가 옵션들...
}
```

## 🎯 검색 타입별 사용 예시

### 1. 첨부파일 전용 검색

```json
{
  "query": "엑셀 파일이 있는 결제 문제",
  "enhanced_search": true,
  "enhanced_search_type": "attachment",
  "file_types": ["excel", "pdf"],
  "max_file_size_mb": 10.0,
  "min_file_size_mb": 0.1
}
```

**지원 파일 타입:**
- `"pdf"` - PDF 문서
- `"excel"`, `"xlsx"` - 엑셀 스프레드시트
- `"image"`, `"png"`, `"jpg"`, `"jpeg"` - 이미지 파일
- `"word"`, `"docx"` - 워드 문서
- `"text"`, `"txt"` - 텍스트 파일

**자연어 패턴:**
- "엑셀 파일", "PDF 문서", "스크린샷"
- "큰 파일", "작은 파일"
- "이미지가 있는", "첨부파일이 포함된"

### 2. 카테고리별 검색

```json
{
  "query": "로그인 관련 문제 해결 가이드",
  "enhanced_search": true,
  "enhanced_search_type": "category",
  "categories": ["로그인", "인증"]
}
```

**지원 카테고리:**
- `"결제"` - 결제, billing, payment 관련
- `"로그인"` - 로그인, 인증, 계정 관련
- `"API"` - API 연동, 토큰 관련
- `"기술지원"` - 오류, 버그, 기술 문제
- `"네트워크"` - 연결, 네트워크 관련
- `"보안"` - 보안, 해킹, 바이러스 관련
- `"사용법"` - 가이드, 튜토리얼 관련
- `"설정"` - 설정, 구성 관련

**자연어 패턴:**
- "결제 관련 문서", "로그인 문제"
- "API 오류", "기술 지원"
- "어떤 카테고리의 문서"

### 3. 문제 해결 중심 검색

```json
{
  "query": "비슷한 문제 해결방법 단계별로",
  "enhanced_search": true,
  "enhanced_search_type": "solution",
  "solution_type": "step_by_step",
  "include_resolved_only": true
}
```

**해결책 타입:**
- `"quick_fix"` - 빠른 해결방법
- `"step_by_step"` - 단계별 가이드
- `"similar_case"` - 유사 사례

**자연어 패턴:**
- "해결방법", "어떻게 해결"
- "비슷한 케이스", "유사한 문제"
- "단계별 가이드", "절차"

### 4. 자동 감지 (권장)

```json
{
  "query": "결제 실패 관련 엑셀 파일 찾아줘",
  "enhanced_search": true,
  "enhanced_search_type": "auto"  // 또는 생략
}
```

시스템이 자동으로 쿼리를 분석하여 최적의 검색 타입을 선택합니다.

## 📊 응답 구조

```json
{
  "query": "사용자 쿼리",
  "response": "AI 생성 요약 응답",
  "documents": [
    {
      "id": "문서 ID",
      "content": "문서 내용 미리보기",
      "metadata": {
        "title": "문서 제목",
        "doc_type": "ticket|article",
        "attachment_summary": {  // 첨부파일 검색 시만
          "file_types": ["이미지", "PDF"],
          "file_count": 3,
          "total_size_mb": 2.5
        }
      },
      "score": 95.3,
      "source": "ticket"
    }
  ],
  "search_metadata": {
    "search_type": "attachment|category|solution|general",
    "intent": "problem_solving|info_gathering|learning|analysis",
    "keywords": ["추출된", "키워드들"],
    "enhanced_search": true,
    "attachment_filters": { /* 적용된 첨부파일 필터 */ },
    "category_hints": ["결제", "로그인"],
    "solution_requirements": { "해결책": true }
  },
  "total_results": 5,
  "processing_time_ms": 234.5
}
```

## 🎯 상담원 자연어 쿼리 예시

### ✅ 첨부파일 검색
```
"엑셀 파일이 있는 결제 문제"
"PDF 문서 찾아줘"
"스크린샷이 포함된 버그 리포트"
"큰 파일이 첨부된 티켓"
"로그 파일이 있는 기술 문의"
```

### ✅ 카테고리별 검색
```
"로그인 오류 관련 문서"
"API 연동 실패 케이스"
"결제 문제 해결 가이드"
"네트워크 연결 이슈"
"보안 관련 정책 문서"
```

### ✅ 문제 해결 검색
```
"비슷한 문제 해결방법"
"단계별 해결 가이드"
"유사한 케이스 사례"
"빠른 수정 방법"
"이런 오류 해결책"
```

### ✅ 복합 검색
```
"긴급한 결제 문제의 첨부파일"
"로그인 오류 해결 단계별 가이드"
"API 연동 실패 스크린샷"
```

## 🔧 기존 기능과의 호환성

### 상담원 모드와 함께 사용

```json
{
  "query": "결제 문제 관련 첨부파일",
  "agent_mode": true,           // 상담원 모드
  "enhanced_search": true,      // 고급 검색
  "stream_response": true,      // 스트리밍
  "enhanced_search_type": "attachment",
  "file_types": ["excel", "pdf"]
}
```

### 기본 검색 파라미터와 조합

```json
{
  "query": "로그인 문제",
  "enhanced_search": true,
  "categories": ["로그인"],
  "top_k": 10,                 // 기존 파라미터
  "search_filters": {          // 기존 필터
    "status": ["open", "pending"]
  }
}
```

## ⚡ 성능 최적화

1. **벡터 DB 레벨 필터링**: Qdrant 쿼리 레벨에서 직접 필터링하여 속도 향상
2. **지능형 라우팅**: 쿼리 의도에 따라 최적 검색 방식 자동 선택
3. **결과 캐싱**: 동일한 검색 조건에 대한 결과 캐싱
4. **배치 처리**: 대량 검색 시 배치 단위로 처리

## 🚀 프론트엔드 통합 예시

### JavaScript/TypeScript

```typescript
// 고급 검색 API 호출
const searchAdvanced = async (query: string, options = {}) => {
  const response = await fetch('/query', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Tenant-ID': 'your-tenant-id',
      'X-Platform': 'freshdesk'
    },
    body: JSON.stringify({
      query,
      enhanced_search: true,
      enhanced_search_type: 'auto',
      ...options
    })
  });
  
  return await response.json();
};

// 사용 예시
const results = await searchAdvanced("엑셀 파일이 있는 결제 문제", {
  file_types: ["excel"],
  categories: ["결제"]
});
```

### React 컴포넌트 예시

```jsx
const EnhancedSearchForm = () => {
  const [searchType, setSearchType] = useState('auto');
  const [fileTypes, setFileTypes] = useState([]);
  const [categories, setCategories] = useState([]);
  
  const handleSearch = async (query) => {
    const options = {
      enhanced_search_type: searchType,
      ...(fileTypes.length > 0 && { file_types: fileTypes }),
      ...(categories.length > 0 && { categories: categories })
    };
    
    const results = await searchAdvanced(query, options);
    // 결과 처리...
  };
  
  return (
    <form onSubmit={handleSearch}>
      <input type="text" placeholder="자연어로 검색하세요..." />
      
      <select value={searchType} onChange={(e) => setSearchType(e.target.value)}>
        <option value="auto">자동 감지</option>
        <option value="attachment">첨부파일 검색</option>
        <option value="category">카테고리 검색</option>
        <option value="solution">해결책 검색</option>
      </select>
      
      {/* 추가 옵션들... */}
    </form>
  );
};
```

## 🔍 디버깅 및 모니터링

### 검색 메타데이터 확인

응답의 `search_metadata` 필드를 통해 다음 정보를 확인할 수 있습니다:

- `search_type`: 실제 사용된 검색 타입
- `intent`: 분석된 사용자 의도
- `keywords`: 추출된 키워드들
- `filters_applied`: 적용된 필터들

### 로그 모니터링

```bash
# 고급 검색 로그 확인
grep "고급 검색" /var/log/app.log

# 성능 모니터링
grep "processing_time_ms" /var/log/app.log
```

## 🎯 베스트 프랙티스

1. **자연어 쿼리 작성**:
   - 구체적인 파일 형식 언급 시 첨부파일 검색 활성화
   - 카테고리명 포함 시 카테고리 검색 우선
   - "해결", "방법" 등 키워드로 해결책 검색 유도

2. **성능 최적화**:
   - `top_k` 값을 적절히 설정 (기본값: 3)
   - 불필요한 필터는 생략
   - 스트리밍 모드 활용 시 사용자 경험 개선

3. **에러 처리**:
   - 고급 검색 실패 시 자동으로 기본 검색으로 폴백
   - 타임아웃 설정으로 응답성 보장

이제 상담원들이 하나의 엔드포인트에서 모든 고급 검색 기능을 활용할 수 있습니다! 🎉