# 🌍 다국어 UI와 정적 요약 아키텍처 설계

## 🔥 **업데이트 완료: FDK 기반 간소화된 언어 감지**

### ✅ **구현 완료 사항**

**프론트엔드 리팩토링 (2025년 6월 23일):**
- ❌ **제거됨**: 복잡한 브라우저 언어 감지 로직
- ❌ **제거됨**: FDK 컨텍스트 우선순위 판단 로직
- ✅ **추가됨**: `client.data.get("loggedInUser")` 직접 사용
- ✅ **개선됨**: `contact.language` 필드로 에이전트 언어 직접 획득
- ✅ **개선됨**: 기본값을 `'en'` (영어)로 설정 - 국제 표준

### 📋 **새로운 언어 감지 로직**

```javascript
// 🎯 간소화된 FDK 기반 언어 감지
async function detectAgentLanguage(client) {
  try {
    const data = await client.data.get("loggedInUser");
    const agentLanguage = data.loggedInUser.contact.language; // "en", "ko", "ja", "zh"
    
    // 지원 언어 매핑
    if (agentLanguage === 'ko') return 'ko';
    if (agentLanguage === 'en') return 'en';
    if (agentLanguage === 'ja') return 'ja';
    if (agentLanguage === 'zh') return 'zh';
    
    return 'en'; // 기본값: 영어 (국제 표준)
  } catch (error) {
    return 'en'; // 에러 시 기본값: 영어
  }
}
```

### 🎯 **이 방법의 장점**

1. **신뢰성**: Freshdesk에서 직접 제공하는 사용자 언어 정보
2. **단순성**: 브라우저 언어 감지 복잡성 완전 제거
3. **정확성**: 상담원이 Freshdesk에서 설정한 실제 언어
4. **유지보수**: 하드코딩된 우선순위 로직 없음
5. **확장성**: 새로운 언어 추가 시 매핑만 추가하면 됨

### 🚀 **API 호출 플로우**

```
에이전트 로그인 → FDK loggedInUser 조회 → contact.language 추출 → 
백엔드 API 호출 (/init/{ticket_id}?agent_language=ko) → 
현지화된 응답 수신 → UI 표시
```

**이제 시스템이 훨씬 더 간단하고 안정적으로 동작합니다!** 🎉

## 📋 **두 가지 요약 시스템 구분**

### **1️⃣ 실시간 요약 (현재 티켓)**
- **생성 시점**: 상담원이 티켓을 열 때 **즉시 실시간** 생성
- **목적**: 현재 보고 있는 티켓의 빠른 이해
- **생성 위치**: `/init/{ticket_id}` API 호출 시 `summarizer.py`
- **언어 처리**: 원문 언어 감지 + UI 언어 섹션 타이틀 ✅ **이미 완료**

### **2️⃣ 정적 요약 (유사 티켓용)**
- **생성 시점**: 데이터 수집 단계에서 **사전 생성** 후 저장
- **목적**: 유사 티켓 검색 시 빠른 표시 (캐시된 요약)
- **생성 위치**: `processor.py`의 `generate_and_store_summaries()` 함수
- **언어 처리**: 원문 언어로 생성 후 실시간 섹션 타이틀 번역 ✅ **이미 완료**

## 📋 **현재 문제 정의**

**핵심 딜레마**: 
- 유사 티켓 요약(정적)은 데이터 수집 시점에 **사전 생성** 
- 에이전트 UI 언어는 로그인 시점에 **동적 결정** 필요
- 두 시점 간의 불일치로 인한 UX 일관성 문제

## 🎯 **현재 구현 상태 확인**

### ✅ **실시간 요약 (완전 구현됨)**
- **위치**: `backend/core/llm/summarizer.py`
- **구조**: Problem Analysis → Root Cause → Solution Process → Key Insights
- **다국어**: 원문 언어 감지 + UI 언어 섹션 타이틀 지원
- **API**: `/init/{ticket_id}?agent_language=ko` ✅ 완료

### ✅ **정적 요약 (생성 완료, 현지화 완료)**  
- **위치**: `backend/core/ingest/processor.py`의 `generate_and_store_summaries()`
- **구조**: 동일한 Problem/Cause/Solution/Insights 구조
- **저장**: `integrated_objects` 테이블에 사전 생성된 요약 저장
- **현지화**: `/init/{ticket_id}` 응답 시 `get_agent_localized_summary()` 적용 ✅ 완료

### ✅ **언어 처리 흐름 (완전 구현됨)**

1. **정적 요약 생성**: 
   ```
   수집 시점 → 원문 언어로 요약 생성 → DB 저장
   ```

2. **실시간 현지화**:
   ```
   상담원 로그인 → agent_language 감지 → 섹션 타이틀만 번역 → UI 표시
   ```

## 🎯 **권장 솔루션: 하이브리드 접근법**

### **1단계: 현재 MVP를 위한 현실적 해결책**

#### 🔄 **Dynamic Section Title Translation**
```python
# 사전 생성된 요약의 섹션 타이틀만 실시간 번역
def translate_section_titles(summary_markdown: str, target_ui_language: str) -> str:
    """
    기존 요약의 섹션 타이틀을 대상 UI 언어로 실시간 변환
    - 요약 본문은 그대로 유지 (원문 언어)
    - 섹션 타이틀만 UI 언어로 변환
    """
    translations = {
        'ko_to_en': {
            '🔍 **문제 상황**': '🔍 **Problem Analysis**',
            '🎯 **근본 원인**': '🎯 **Root Cause**',
            '🔧 **해결 과정**': '🔧 **Solution Process**',
            '💡 **핵심 포인트**': '💡 **Key Insights**'
        },
        'en_to_ko': {
            '🔍 **Problem Analysis**': '🔍 **문제 상황**',
            '🎯 **Root Cause**': '🎯 **근본 원인**',
            '🔧 **Solution Process**': '🔧 **해결 과정**',
            '💡 **Key Insights**': '💡 **핵심 포인트**'
        }
    }
    
    # 패턴 매칭으로 실시간 변환
    if target_ui_language == 'en' and '**문제 상황**' in summary_markdown:
        # 한국어 → 영어 변환
        for ko_title, en_title in translations['ko_to_en'].items():
            summary_markdown = summary_markdown.replace(ko_title, en_title)
    elif target_ui_language == 'ko' and '**Problem Analysis**' in summary_markdown:
        # 영어 → 한국어 변환
        for en_title, ko_title in translations['en_to_ko'].items():
            summary_markdown = summary_markdown.replace(en_title, ko_title)
    
    return summary_markdown
```

#### 💾 **에이전트 언어 우선순위 결정 로직**
```python
def determine_agent_ui_language(agent_profile: Dict[str, Any], company_settings: Dict[str, Any]) -> str:
    """
    에이전트 UI 언어 결정 우선순위:
    1. 에이전트 개인 설정 (agent.profile.language)
    2. 회사 기본 언어 (company.default_language) 
    3. 시스템 기본값 ('ko')
    """
    # 1순위: 에이전트 개인 설정
    if agent_profile.get('language') in ['ko', 'en']:
        return agent_profile['language']
    
    # 2순위: 회사 기본 언어
    if company_settings.get('default_language') in ['ko', 'en']:
        return company_settings['default_language']
    
    # 3순위: 시스템 기본값
    return 'ko'
```

### **2단계: 중장기 확장성을 위한 설계**

#### 🗄️ **멀티 랭귀지 요약 저장 구조**
```sql
-- 기존 테이블 확장
CREATE TABLE similar_ticket_summaries (
    id SERIAL PRIMARY KEY,
    ticket_id INTEGER NOT NULL,
    company_id VARCHAR(100) NOT NULL,
    
    -- 원문 정보
    original_language VARCHAR(10) NOT NULL,  -- 'ko', 'en', 'ja', 'zh'
    
    -- 다국어 요약 저장
    summary_ko TEXT,  -- 한국어 UI용 요약 (섹션 타이틀 한국어)
    summary_en TEXT,  -- 영어 UI용 요약 (섹션 타이틀 영어)
    
    -- 원본 요약 (언어 중립적)
    summary_raw TEXT NOT NULL,  -- 섹션 타이틀 없는 순수 내용
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

#### 🔄 **배치 생성 vs 온디맨드 생성**
```python
class SummaryLanguageManager:
    def __init__(self):
        self.supported_ui_languages = ['ko', 'en']
    
    async def get_summary_for_agent(
        self, 
        ticket_id: str, 
        agent_ui_language: str
    ) -> str:
        """
        에이전트 UI 언어에 맞는 요약 반환
        """
        # 1. 캐시된 번역 확인
        cached_summary = await self.get_cached_translated_summary(
            ticket_id, agent_ui_language
        )
        if cached_summary:
            return cached_summary
        
        # 2. 원본 요약 가져오기
        original_summary = await self.get_original_summary(ticket_id)
        if not original_summary:
            return "요약을 찾을 수 없습니다."
        
        # 3. 실시간 섹션 타이틀 번역
        translated_summary = translate_section_titles(
            original_summary, agent_ui_language
        )
        
        # 4. 번역 결과 캐싱 (24시간)
        await self.cache_translated_summary(
            ticket_id, agent_ui_language, translated_summary
        )
        
        return translated_summary
    
    async def pregenerate_ui_variations(self, ticket_id: str):
        """
        선택적: 인기 티켓의 경우 UI 언어별 사전 생성
        """
        original_summary = await self.get_original_summary(ticket_id)
        
        for ui_lang in self.supported_ui_languages:
            translated = translate_section_titles(original_summary, ui_lang)
            await self.save_ui_language_variant(ticket_id, ui_lang, translated)
```

## 🚀 **구현 단계별 로드맵**

### **Phase 1: MVP 단계 (즉시 구현)**
✅ **완전 구현됨** - 양쪽 요약 시스템 모두 완료
- [x] **실시간 요약**: content_language 자동 감지 + ui_language 매개변수 지원
- [x] **정적 요약**: 사전 생성 + 실시간 섹션 타이틀 현지화
- [x] 프론트엔드 에이전트 언어 감지 및 전달
- [x] 백엔드 `/init/{ticket_id}` API에서 현지화 적용

### **Phase 2: 동적 번역 레이어 (2주 내)**
✅ **완료됨** - 하드코딩 기반 (유지보수성 제한)
- [x] **실시간 요약**: `summarizer.py`에서 직접 UI 언어 지원  
- [x] **정적 요약**: `get_agent_localized_summary()` 함수로 섹션 타이틀 번역
- [x] 에이전트 언어 설정 API 연동 (브라우저 감지)
- [x] 프론트엔드에서 에이전트 언어 감지 및 전달

⚠️ **개선 필요사항:**
- [ ] 구조화된 번역 시스템으로 리팩토링
- [ ] 에이전트 프로필 DB 구축
- [ ] 라이센스 관리 시스템 연동

### **Phase 3: 캐싱 최적화 (1개월 내)**
- [ ] Redis 기반 번역 캐싱
- [ ] 자주 조회되는 티켓의 다국어 변형 사전 생성
- [ ] 캐시 hit ratio 모니터링

### **Phase 4: 라이센스 관리 통합 (2-3개월)**
- [ ] 에이전트 프로필 데이터베이스 구축
- [ ] 회사별 기본 언어 설정
- [ ] 에이전트별 개인 언어 설정 지원

## 💡 **권장 결정사항**

### **현재 시점 (MVP) 권장 방향:**
1. **기본 UI 언어**: 한국어 고정 (회사 기본값)
2. **동적 번역**: 섹션 타이틀만 실시간 변환
3. **우선 지원 언어**: 한국어/영어 2개 언어만
4. **장기 계획**: 에이전트 프로필 시스템 구축 후 개인화

### **이유:**
- **실용성**: 대부분의 고객사가 단일 언어 환경
- **성능**: 섹션 타이틀만 번역하므로 빠름
- **비용**: LLM 재생성 없이 단순 텍스트 치환
- **확장성**: 나중에 멀티 랭귀지 저장으로 업그레이드 가능

## 🔧 **구현 우선순위**

### **높음 (즉시)**
- 에이전트 언어 감지 API
- 섹션 타이틀 번역 함수
- 프론트엔드 언어 전달 로직

### **중간 (2-4주)**
- 번역 캐싱 시스템
- 회사별 기본 언어 설정
- 에이전트 언어 설정 UI

### **낮음 (장기)**
- 멀티 랭귀지 DB 스키마
- 배치 사전 생성
- 언어별 품질 최적화

## 📊 **성능 및 비용 영향**

### **현재 권장 방안 (동적 번역):**
- **지연시간**: +5ms (텍스트 치환)
- **메모리**: +1KB per request (번역 맵)
- **LLM 비용**: 추가 비용 없음 (재생성 없음)
- **캐시 효율성**: 매우 높음 (단순 텍스트)

### **대안 방안 (LLM 재생성) 비교:**
- **지연시간**: +2000ms (LLM 호출)
- **LLM 비용**: 기존 대비 2-3배 증가
- **품질**: 더 자연스러운 번역
- **확장성**: 언어 추가 시 복잡도 증가

## 🎯 **최종 권장사항**

**✅ 현재 요약 프롬프트 구조가 이미 완벽하게 적용되어 있습니다!**

### **📋 적용된 요약 구조:**
- 🔍 **문제 상황** / **Problem Analysis** 
- 🎯 **근본 원인** / **Root Cause**
- 🔧 **해결 과정** / **Solution Process** 
- 💡 **핵심 포인트** / **Key Insights**

### **🌍 다국어 지원 현황:**
- ✅ **실시간 요약**: `summarizer.py`에서 원문 언어 감지 + UI 언어 섹션 타이틀
- ✅ **정적 요약**: 사전 생성 후 API 응답 시 실시간 현지화
- ✅ **프론트엔드**: FDK `loggedInUser.contact.language` 직접 사용 (간소화 완료!)
- ✅ **백엔드**: `/init/{ticket_id}?agent_language=ko` 지원

### **🔄 동작 흐름:**
1. **수집 단계**: 정적 요약 사전 생성 (`processor.py`)
2. **상담원 접근**: FDK에서 `loggedInUser.contact.language` 직접 획득 → 백엔드 전송 ✅
3. **백엔드 처리**: 실시간 요약 생성 + 정적 요약 현지화 (`init.py`)
4. **UI 표시**: 모든 요약이 에이전트 언어로 통일된 섹션 타이틀로 표시

**✨ 간소화된 구조로 브라우저 언어 감지의 복잡성 제거, FDK 네이티브 기능 활용!** 🎉

## 📱 프론트엔드 다국어 지원 구현 완료

### 🔄 변경 사항

#### 1. API 모듈 업데이트 (`frontend/app/scripts/api.js`)

**✅ FDK 기반 간소화된 에이전트 언어 감지:**
- `detectAgentLanguage(client)`: 복잡한 브라우저 언어 감지 로직 제거
- **FDK `loggedInUser.contact.language` 직접 사용** ⭐
- 지원 언어: Korean (ko), English (en), Japanese (ja), Chinese (zh)
- 기본값: `en` (국제 표준)

**API 호출 함수 업데이트:**
- `loadInitData(client, ticketId, agentLanguage)`: agent_language 쿼리 매개변수 지원
- 자동 언어 감지 및 백엔드 전송

**테스트 유틸리티 업데이트:**
- `getCurrentAgentLanguage(client)`: FDK 기반 언어 확인
- `testLanguageLocalization(client, testLanguage)`: 특정 언어로 API 테스트
- `window.testMultiLanguageSupport(language)`: 브라우저 콘솔 테스트 함수 (FDK 기반)

#### 2. 데이터 모듈 업데이트 (`frontend/app/scripts/data.js`)

**백엔드 호출 함수 업데이트:**
- `loadInitialDataFromBackend(client, ticket, agentLanguage)`: 에이전트 언어 매개변수 추가
- 자동 언어 감지 및 백엔드 API 호출 시 전달

### 🌍 동작 원리

1. **언어 감지**: 프론트엔드에서 FDK `loggedInUser.contact.language` 직접 획득 ⭐
2. **API 호출**: `/init/{ticket_id}?agent_language={detected_language}` 형태로 백엔드 호출
3. **백엔드 처리**: 에이전트 언어에 따라 유사 티켓 요약의 섹션 제목 현지화
4. **UI 표시**: 현지화된 데이터를 프론트엔드에서 그대로 표시

**💡 주요 개선사항:**
- 복잡한 브라우저 언어 감지 로직 완전 제거
- FDK 네이티브 API를 통한 신뢰성 높은 언어 정보 획득
- 에러 처리 간소화 및 안정성 향상

### 🧪 테스트 방법

브라우저 개발자 도구 콘솔에서 다음 함수들을 사용하여 테스트:

```javascript
// FDK에서 현재 감지된 언어 확인
await API.getCurrentAgentLanguage(GlobalState.getClient());

// 특정 언어로 테스트 (FDK 기반)
testMultiLanguageSupport("ko");  // 한국어
testMultiLanguageSupport("en");  // 영어
testMultiLanguageSupport("ja");  // 일본어
testMultiLanguageSupport("zh");  // 중국어
```

### 📋 사용 예시

**한국어 에이전트의 경우:**
- 감지된 언어: `ko`
- API 호출: `/init/12345?agent_language=ko`
- 유사 티켓 섹션 제목: "🔍 **문제:**", "💡 **해결책:**"

**영어 에이전트의 경우:**
- 감지된 언어: `en`  
- API 호출: `/init/12345?agent_language=en`
- 유사 티켓 섹션 제목: "🔍 **Problem:**", "💡 **Solution:**"

### 🔗 연동 상태

- ✅ **백엔드**: 다국어 요약 및 현지화 완료
- ✅ **프론트엔드**: 언어 감지 및 API 호출 완료
- ✅ **UI**: 현지화된 데이터 표시 완료
- ✅ **테스트**: 개발자 콘솔 테스트 도구 제공

### 🚀 다음 단계

1. **에이전트 프로필 DB 구축**: 사용자별 언어 설정 저장
2. **라이센스 관리 시스템**: 회사별 기본 언어 설정
3. **캐싱 최적화**: 언어별 요약 캐싱 전략
4. **UI 다국어화**: 프론트엔드 UI 텍스트 전체 현지화

## 🔧 **개선된 아키텍처 설계**

### **1. 구조화된 섹션 정의 시스템**

#### 📋 **섹션 구조를 코드에서 분리**
```python
# config/summary_sections.yaml
summary_sections:
  structure:
    - key: "problem"
      icon: "🔍"
      order: 1
    - key: "root_cause" 
      icon: "🎯"
      order: 2
    - key: "solution_process"
      icon: "🔧"
      order: 3
    - key: "key_insights"
      icon: "💡"
      order: 4

translations:
  ko:
    problem: "문제 상황"
    root_cause: "근본 원인"
    solution_process: "해결 과정"
    key_insights: "핵심 포인트"
  en:
    problem: "Problem Analysis"
    root_cause: "Root Cause"
    solution_process: "Solution Process"
    key_insights: "Key Insights"
  ja:
    problem: "問題状況"
    root_cause: "根本原因"
    solution_process: "解決プロセス"
    key_insights: "重要なポイント"
```

#### 🏗️ **동적 섹션 생성 시스템**
```python
class SummarySectionManager:
    def __init__(self):
        self.sections_config = self.load_sections_config()
    
    def generate_section_header(self, section_key: str, ui_language: str) -> str:
        """섹션 헤더를 동적으로 생성"""
        section = self.sections_config['structure'][section_key]
        translation = self.sections_config['translations'][ui_language][section_key]
        
        return f"{section['icon']} **{translation}:**"
    
    def localize_summary(self, summary_content: str, ui_language: str) -> str:
        """요약 내용의 섹션 헤더만 현지화"""
        for section in self.sections_config['structure']:
            for lang, translations in self.sections_config['translations'].items():
                if lang == ui_language:
                    continue
                    
                # 기존 헤더를 찾아서 대상 언어로 변경
                old_header = f"{section['icon']} **{translations[section['key']]}:**"
                new_header = self.generate_section_header(section['key'], ui_language)
                summary_content = summary_content.replace(old_header, new_header)
        
        return summary_content
```

### **2. 에이전트 프로필 & 라이센스 DB 설계**

#### 🗄️ **데이터베이스 스키마**
```sql
-- 회사/라이센스 테이블
CREATE TABLE companies (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    subdomain VARCHAR(100) UNIQUE NOT NULL,  -- freshdesk subdomain
    license_type VARCHAR(50) NOT NULL,       -- 'basic', 'pro', 'enterprise'
    max_agents INTEGER DEFAULT 10,
    default_language VARCHAR(10) DEFAULT 'ko',
    created_at TIMESTAMP DEFAULT NOW()
);

-- 에이전트 프로필 테이블
CREATE TABLE agents (
    id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES companies(id),
    freshdesk_agent_id BIGINT,              -- Freshdesk API에서 가져온 ID
    email VARCHAR(255) NOT NULL,
    name VARCHAR(255),
    role VARCHAR(100),                       -- 'admin', 'agent', 'supervisor'
    
    -- 개인화 설정
    preferred_language VARCHAR(10) DEFAULT NULL,  -- 개인 언어 설정
    timezone VARCHAR(50) DEFAULT 'Asia/Seoul',
    
    -- 상태 관리
    is_active BOOLEAN DEFAULT true,
    last_login_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 에이전트 세션 테이블 (현재 활성 세션 추적)
CREATE TABLE agent_sessions (
    id SERIAL PRIMARY KEY,
    agent_id INTEGER REFERENCES agents(id),
    session_token VARCHAR(255) UNIQUE,
    current_language VARCHAR(10),           -- 현재 세션의 언어
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);
```

#### 🔌 **에이전트 언어 결정 로직 개선**
```python
class AgentLanguageService:
    def __init__(self, db_session):
        self.db = db_session
    
    async def determine_agent_language(
        self, 
        freshdesk_domain: str,
        freshdesk_agent_id: str,
        session_token: str = None,
        browser_language: str = None
    ) -> str:
        """
        에이전트 언어 결정 우선순위:
        1. 현재 세션 언어 (사용자가 수동 변경한 경우)
        2. 에이전트 개인 설정
        3. 회사 기본 언어
        4. 브라우저 언어
        5. 시스템 기본값 ('ko')
        """
        
        # 1. 현재 세션 언어 확인
        if session_token:
            session_lang = await self.get_session_language(session_token)
            if session_lang:
                return session_lang
        
        # 2. 에이전트 개인 설정 확인
        agent = await self.get_agent_profile(freshdesk_domain, freshdesk_agent_id)
        if agent and agent.preferred_language:
            return agent.preferred_language
        
        # 3. 회사 기본 언어 확인
        company = await self.get_company_by_domain(freshdesk_domain)
        if company and company.default_language:
            return company.default_language
        
        # 4. 브라우저 언어 매핑
        if browser_language:
            mapped_lang = self.map_browser_language(browser_language)
            if mapped_lang:
                return mapped_lang
        
        # 5. 시스템 기본값
        return 'ko'
    
    async def get_agent_profile(self, domain: str, agent_id: str) -> Agent:
        """Freshdesk domain과 agent ID로 프로필 조회"""
        return await self.db.query(Agent).join(Company).filter(
            Company.subdomain == domain,
            Agent.freshdesk_agent_id == agent_id
        ).first()
```

### **3. 프론트엔드 통합 전략**

#### 🎯 **구현 우선순위 재조정**

**즉시 구현 (프론트엔드 작업 시):**
1. **에이전트 프로필 API 연동**
   - 현재 로그인한 에이전트 정보 가져오기
   - 개인 언어 설정 저장/불러오기
   - 세션 기반 언어 변경

2. **개선된 언어 감지 로직**
   ```javascript
   async function getAgentLanguage(client) {
     try {
       // 1. 서버에서 에이전트 프로필 조회
       const agentProfile = await API.getAgentProfile(client);
       if (agentProfile.preferredLanguage) {
         return agentProfile.preferredLanguage;
       }
       
       // 2. 회사 기본 언어 사용
       if (agentProfile.company.defaultLanguage) {
         return agentProfile.company.defaultLanguage;
       }
       
       // 3. 기존 브라우저 감지 로직 사용
       return await API.detectAgentLanguage(client);
     } catch (error) {
       return 'en'; // 기본값: 영어
     }
   }
   ```

3. **언어 변경 UI 추가**
   - 설정 메뉴에 언어 선택 옵션
   - 실시간 언어 변경 (페이지 새로고침 없이)

**백엔드 리팩토링 (프론트엔드 완료 후):**
1. 하드코딩된 번역 맵을 YAML 설정으로 이전
2. 에이전트 프로필 API 구현
3. 라이센스 관리 시스템 통합

### **4. 마이그레이션 전략**

#### 📈 **단계별 전환**
```python
# Phase 1: 기존 시스템 유지하며 DB 구축
class HybridLanguageService:
    def __init__(self):
        self.legacy_detector = BrowserLanguageDetector()
        self.new_service = AgentLanguageService()
    
    async def get_agent_language(self, request_data):
        try:
            # 새로운 시스템 시도
            if self.has_agent_profile(request_data):
                return await self.new_service.determine_agent_language(request_data)
        except Exception as e:
            logger.warning(f"새로운 언어 시스템 실패, 기존 방식 사용: {e}")
        
        # 기존 시스템 폴백
        return await self.legacy_detector.detect(request_data)
```
