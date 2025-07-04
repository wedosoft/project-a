---
applyTo: "**"
---

# 🎨 FDK 개발 패턴 지침서

_Freshdesk FDK (Frontend Development Kit) 구현 전문 가이드_

## 🎯 **FDK 개발 목표**

**Freshdesk Custom App의 프론트엔드 구현 방법론**

- **FDK 환경 최적화**: Node.js 버전 호환성 및 개발 환경 구성
- **company_id 자동 추출**: 멀티테넌트 보안을 위한 도메인 기반 식별
- **백엔드 API 연동**: 효율적인 FastAPI 백엔드 통신
- **디버깅 및 검증**: FDK 특수 환경에서의 효과적인 개발 프로세스

---

## 🚀 **FDK 핵심 포인트 요약**

### 💡 **즉시 참조용 FDK 핵심**

**환경 제약사항**:

- Node.js v14-v18만 지원 (v19+ 비호환)
- 플랫폼은 항상 "freshdesk" (FDK 자체가 Freshdesk 전용)
- 디버깅: `fdk validate --verbose`로 상세 오류 확인

**필수 패턴**:

- `domain.split('.')[0]`로 company_id 자동 추출
- iparams.html에서 설정 값 관리
- 백엔드 API 호출 시 company_id 헤더 포함

**주의사항**:

- ⚠️ JavaScript 중괄호 매칭 오류 빈발
- ⚠️ FDK 런타임 환경과 브라우저 환경 차이
- ⚠️ 비동기 처리 시 FDK API 컨텍스트 유지 필요

---

## 🔧 **FDK 개발 환경 구성**

### **환경 요구사항**

```bash
# Node.js 버전 확인 및 설정
node --version  # v14.x ~ v18.x 확인
npm --version   # 6.x 이상 확인

# FDK CLI 설치 (글로벌)
npm install -g @freshworks/fdk

# FDK 버전 확인
fdk --version
```

### **개발 명령어**

```bash
# FDK 앱 실행 (로컬 개발 서버)
fdk run

# FDK 앱 검증 (구문 및 설정 검사)
fdk validate

# 상세 디버깅 모드
fdk validate --verbose
fdk run --log-level debug
```

### **프로젝트 구조**

```
frontend/
├── manifest.json        # FDK 앱 설정
├── app/
│   ├── index.html      # 메인 앱 HTML
│   ├── scripts/        # JavaScript 파일들
│   │   ├── app.js      # 메인 앱 로직
│   │   ├── api.js      # 백엔드 API 클라이언트
│   │   └── utils.js    # 유틸리티 함수들
│   └── styles/
│       └── styles.css  # 스타일 (단일 파일 원칙)
└── config/
    ├── iparams.html    # 설치 시 설정 화면
    └── requests.json   # API 요청 권한 설정
```

---

## 🏗️ **FDK 핵심 구현 패턴**

### **1. JavaScript 구문 오류 해결**

```javascript
// ❌ 잘못된 패턴 - 중괄호 매칭 오류
function smartDomainParsing(domain) {
  const parts = domain.split(".");
  return parts[0];
} // ← 추가 중괄호나 세미콜론 누락 시 오류

// ✅ 올바른 패턴 - 명확한 구조
function smartDomainParsing(domain) {
  try {
    const parts = domain.split(".");
    if (parts.length === 0) {
      throw new Error("Invalid domain format");
    }
    return parts[0];
  } catch (error) {
    console.error("Domain parsing error:", error);
    return "demo"; // 기본값 반환
  }
}
```

### **2. FDK 앱 초기화 패턴**

```javascript
// app.js - 메인 앱 진입점
class AIAssistantApp {
  constructor() {
    this.isInitialized = false;
    this.companyId = null;
    this.ticketData = null;
    this.apiClient = null;
  }

  async initialize() {
    try {
      // FDK 컨텍스트 정보 로드
      await this.loadFDKContext();

      // company_id 자동 추출
      await this.extractCompanyId();

      // API 클라이언트 초기화
      this.apiClient = new BackendAPIClient(this.companyId);

      // UI 초기화
      await this.initializeUI();

      this.isInitialized = true;
      console.log("AI Assistant App 초기화 완료:", this.companyId);
    } catch (error) {
      console.error("앱 초기화 실패:", error);
      this.showError("앱을 초기화할 수 없습니다.");
    }
  }

  async loadFDKContext() {
    // Freshdesk 앱 컨텍스트 접근
    const context = await window.parent.app.instance.context();
    this.companyId = context.account.subdomain;

    // 티켓 데이터 로드
    this.ticketData = await window.parent.app.data.get("ticket");
  }

  async extractCompanyId() {
    if (!this.companyId) {
      // 도메인에서 company_id 추출 (백업 방법)
      const domain = window.location.hostname;
      this.companyId = domain.split(".")[0];
    }

    if (!this.companyId || this.companyId === "localhost") {
      this.companyId = "demo"; // 개발 환경 기본값
    }
  }

  async initializeUI() {
    // UI 이벤트 핸들러 등록
    document
      .getElementById("recommend-button")
      .addEventListener("click", () => this.getRecommendations());

    document
      .getElementById("refresh-button")
      .addEventListener("click", () => this.refreshData());
  }

  showError(message) {
    document.getElementById("error-message").textContent = message;
    document.getElementById("error-container").style.display = "block";
  }
}

// 앱 초기화
document.addEventListener("DOMContentLoaded", async () => {
  const app = new AIAssistantApp();
  await app.initialize();
});
```

### **3. 백엔드 API 연동 클라이언트**

```javascript
// api.js - 백엔드 통신 전담 클래스
class BackendAPIClient {
  constructor(companyId) {
    this.companyId = companyId;
    this.baseUrl = this.getBackendUrl();
    this.defaultHeaders = {
      "Content-Type": "application/json",
      "X-Company-ID": this.companyId,
      "X-Platform": "freshdesk",
    };
  }

  getBackendUrl() {
    // iparams에서 백엔드 URL 가져오기
    const iparams = this.getIparams();
    return iparams.backend_url || "http://localhost:8000";
  }

  getIparams() {
    // FDK iparams 접근
    try {
      return window.parent.app.iparams.get();
    } catch (error) {
      console.warn("iparams 접근 실패, 기본값 사용");
      return { backend_url: "http://localhost:8000" };
    }
  }

  async makeRequest(endpoint, options = {}) {
    const url = `${this.baseUrl}/api/v1${endpoint}`;

    const config = {
      headers: {
        ...this.defaultHeaders,
        ...options.headers,
      },
      ...options,
    };

    try {
      const response = await fetch(url, config);

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      return await response.json();
    } catch (error) {
      console.error(`API 요청 실패 [${endpoint}]:`, error);
      throw new Error(`백엔드 통신 오류: ${error.message}`);
    }
  }

  async getRecommendations(ticketData) {
    return await this.makeRequest("/recommendations", {
      method: "POST",
      body: JSON.stringify({
        company_id: this.companyId,
        ticket_data: ticketData,
        limit: 5,
      }),
    });
  }

  async submitFeedback(recommendationId, rating, comment) {
    return await this.makeRequest("/feedback", {
      method: "POST",
      body: JSON.stringify({
        company_id: this.companyId,
        recommendation_id: recommendationId,
        rating: rating,
        comment: comment,
      }),
    });
  }

  async getHealth() {
    return await this.makeRequest("/health", {
      method: "GET",
    });
  }
}
```

### **4. iparams.html 최적화 패턴**

```html
<!DOCTYPE html>
<html>
  <head>
    <title>AI Assistant 설정</title>
    <meta charset="UTF-8" />
    <style>
      .form-container {
        max-width: 500px;
        margin: 20px auto;
        padding: 20px;
      }
      .form-group {
        margin-bottom: 15px;
      }
      label {
        display: block;
        margin-bottom: 5px;
        font-weight: bold;
      }
      input,
      select {
        width: 100%;
        padding: 8px;
        border: 1px solid #ddd;
        border-radius: 4px;
      }
      .help-text {
        font-size: 12px;
        color: #666;
        margin-top: 5px;
      }
      .auto-detected {
        background-color: #f0f8f0;
      }
    </style>
  </head>
  <body>
    <div class="form-container">
      <h2>🤖 AI Assistant 설정</h2>

      <!-- company_id 자동 추출 (읽기 전용) -->
      <div class="form-group">
        <label for="company_id">Company ID (자동 감지)</label>
        <input
          type="text"
          id="company_id"
          name="company_id"
          readonly
          class="auto-detected"
        />
        <div class="help-text">도메인에서 자동으로 추출됩니다</div>
      </div>

      <!-- 백엔드 URL 설정 -->
      <div class="form-group">
        <label for="backend_url">Backend URL</label>
        <input
          type="url"
          id="backend_url"
          name="backend_url"
          placeholder="https://your-backend.herokuapp.com"
          required
        />
        <div class="help-text">AI Assistant 백엔드 서버 URL을 입력하세요</div>
      </div>

      <!-- LLM 모델 선택 -->
      <div class="form-group">
        <label for="llm_model">LLM 모델</label>
        <select id="llm_model" name="llm_model">
          <option value="gpt-3.5-turbo">GPT-3.5 Turbo (권장)</option>
          <option value="gpt-4">GPT-4 (고급)</option>
          <option value="claude-3-sonnet">Claude 3 Sonnet</option>
        </select>
        <div class="help-text">추천 품질과 비용을 고려하여 선택하세요</div>
      </div>

      <!-- 추천 개수 설정 -->
      <div class="form-group">
        <label for="recommendation_limit">추천 티켓 개수</label>
        <select id="recommendation_limit" name="recommendation_limit">
          <option value="3">3개 (빠름)</option>
          <option value="5" selected>5개 (권장)</option>
          <option value="10">10개 (상세)</option>
        </select>
      </div>
    </div>

    <script>
      // ✅ Freshdesk 전용 최적화 패턴 - company_id 자동 추출
      document.addEventListener("DOMContentLoaded", function () {
        // 도메인에서 company_id 자동 추출
        const domain = window.location.hostname;
        const companyId = extractCompanyId(domain);

        // 자동 감지된 company_id 표시
        document.getElementById("company_id").value = companyId;

        // 기본 백엔드 URL 설정 (선택적)
        const backendUrlField = document.getElementById("backend_url");
        if (!backendUrlField.value) {
          backendUrlField.value = `https://${companyId}-ai-assistant.herokuapp.com`;
        }
      });

      function extractCompanyId(domain) {
        try {
          // xxx.freshdesk.com -> xxx
          const parts = domain.split(".");
          if (parts.length >= 2 && parts[1] === "freshdesk") {
            return parts[0];
          }

          // 로컬 개발 환경
          if (domain.includes("localhost") || domain.includes("127.0.0.1")) {
            return "demo";
          }

          // 기타 환경에서도 첫 번째 부분 사용
          return parts[0] || "demo";
        } catch (error) {
          console.error("Company ID 추출 오류:", error);
          return "demo";
        }
      }

      // 설정 유효성 검사
      function validateSettings() {
        const backendUrl = document.getElementById("backend_url").value;

        if (!backendUrl) {
          alert("Backend URL을 입력해주세요.");
          return false;
        }

        try {
          new URL(backendUrl);
        } catch (error) {
          alert("올바른 URL 형식을 입력해주세요.");
          return false;
        }

        return true;
      }

      // 폼 제출 시 유효성 검사
      document.querySelector("form").addEventListener("submit", function (e) {
        if (!validateSettings()) {
          e.preventDefault();
        }
      });
    </script>
  </body>
</html>
```

---

## 🔍 **FDK 디버깅 및 검증**

### **디버깅 명령어**

```bash
# 1. FDK 검증 및 상세 오류 확인
fdk validate --verbose

# 2. 로그 레벨을 높여서 상세 디버그 정보 확인
fdk run --log-level debug

# 3. 특정 포트에서 실행 (포트 충돌 해결)
fdk run --port 10001

# 4. 개발자 도구용 소스맵 활성화
fdk run --enable-source-maps
```

### **브라우저 개발자 도구 활용**

```javascript
// 브라우저 콘솔에서 디버깅 정보 확인 (중요!)
console.log("FDK Context:", window.parent.app);
console.log("Company ID:", await window.parent.app.instance.context());
console.log("Ticket Data:", await window.parent.app.data.get("ticket"));

// FDK API 상태 확인
console.log("FDK Version:", window.parent.app.version);
console.log("Platform:", window.parent.app.platform);
```

### **일반적인 FDK 오류 해결**

**1. 중괄호 매칭 오류**

```javascript
// ❌ 오류가 발생하는 코드
function processData() {
    if (condition) {
        doSomething();
    // 중괄호 누락!

// ✅ 수정된 코드
function processData() {
    if (condition) {
        doSomething();
    } // 중괄호 매칭 완료
}
```

**2. 비동기 처리 오류**

```javascript
// ❌ FDK API를 동기적으로 호출
const context = window.parent.app.instance.context(); // 오류!

// ✅ 올바른 비동기 호출
const context = await window.parent.app.instance.context();
```

**3. iparams 접근 오류**

```javascript
// ❌ 직접 접근 시도
const params = window.parent.app.iparams; // 오류!

// ✅ 올바른 접근 방법
const params = window.parent.app.iparams.get();
```

---

## ⚠️ **FDK 개발 주의사항**

### **🚨 필수 준수 사항**

1. **Node.js 버전 제한**: v14-v18만 사용 (v19+ 비호환)
2. **플랫폼 고정**: 항상 "freshdesk" (하드코딩 가능)
3. **company_id 자동 추출**: 수동 입력 대신 도메인 기반 자동 감지
4. **중괄호 매칭**: JavaScript 구문 오류 방지를 위한 꼼꼼한 검토

### **📋 FDK 개발 체크리스트**

**개발 시작 전**:

- [ ] Node.js 버전 확인 (v14-v18)
- [ ] FDK CLI 최신 버전 설치
- [ ] manifest.json 설정 확인

**개발 중**:

- [ ] `fdk validate --verbose`로 구문 검증
- [ ] 브라우저 개발자 도구에서 콘솔 오류 확인
- [ ] company_id 자동 추출 로직 테스트
- [ ] 백엔드 API 연동 테스트

**배포 전**:

- [ ] 모든 JavaScript 파일 구문 검증
- [ ] iparams.html 동작 확인
- [ ] 다양한 Freshdesk 도메인에서 테스트
- [ ] 에러 처리 로직 검증

---

## 🔗 **관련 지침서 참조**

- 🚀 `quick-reference.instructions.md` - FDK 핵심 패턴 요약
- 🐍 `backend-implementation-patterns.instructions.md` - 백엔드 API 연동
- 🚨 `error-handling-debugging.instructions.md` - 에러 처리 상세
- 📚 `global.instructions.md` - 프로젝트 공통 원칙

---

_이 지침서는 FDK 개발에 특화된 패턴과 주의사항을 포함합니다. 백엔드 구현은 관련 지침서를 참조하세요._
