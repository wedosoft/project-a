---
applyTo: "**"
---

# 🧩 자연어 기반 상담사 지원 시스템 프론트엔드 UX 설계 지침

본 문서는 Freshdesk Custom App의 자연어 기반 AI 응답 지원 시스템에 대한 프론트엔드 기능 기획 초안을 정리한 것입니다. 주요 인터페이스 영역, 동작 조건, 상호작용 흐름을 정의합니다.

## 🎯 목적

Freshdesk Custom App에서 상담사가 자연어로 질문/요청을 할 수 있도록 지원하고, AI가 유사 티켓·추천 솔루션·이미지·첨부파일을 자동으로 추천·검색·삽입할 수 있게 합니다. **상담원이 티켓을 열 때 자동으로 백엔드 API와 연결**되어 해당 고객사의 데이터만 안전하게 처리합니다. 자연스러운 작업 흐름과 높은 상담사 UX를 목표로 합니다.

---

## 🛠️ Freshdesk FDK (Developer Kit) 환경 구성

### FDK 개발 환경 요구사항

- **Node.js 버전**: v14.x ~ v18.x (FDK는 최신 Node.js 버전과 호환성 이슈가 있을 수 있음)
- **FDK CLI**: `npm install -g @freshworks/fdk`
- **개발 서버**: `fdk run` 명령으로 로컬 개발 서버 실행
- **빌드 도구**: Webpack, Babel 등은 FDK에서 자동 처리

### FDK 프로젝트 구조

```
frontend/
├── app/                    # 메인 앱 코드
│   ├── index.html         # 앱 진입점
│   ├── app.js            # 메인 JavaScript 로직
│   ├── app.css           # 스타일시트
│   └── components/       # React/Vue 컴포넌트들
├── config/
│   └── iparams.json      # 앱 설치 시 설정 항목 정의
├── manifest.json         # 앱 메타데이터 및 권한 설정
└── app.info             # 앱 기본 정보
```

### FDK 핵심 API 활용

#### 1. Freshdesk 인스턴스 컨텍스트 획득

```javascript
// Freshdesk 도메인과 API 키 동적 추출
async function getFreshdeskConfig() {
  try {
    // FDK가 제공하는 context API 사용
    const context = await window.parent.app.instance.context();

    return {
      domain: context.account.subdomain + ".freshdesk.com",
      apiKey: context.account.apiKey,
      userId: context.user.id,
      userRole: context.user.role,
      accountId: context.account.id,
    };
  } catch (error) {
    console.error("Freshdesk 설정 추출 실패:", error);
    throw new Error("Freshdesk 연결 설정을 가져올 수 없습니다.");
  }
}
```

#### 2. 티켓 정보 실시간 획득

```javascript
// 현재 열린 티켓의 정보 가져오기
async function getCurrentTicketInfo() {
  try {
    const ticketData = await window.parent.app.data.get("ticket");
    return {
      ticketId: ticketData.ticket.id,
      subject: ticketData.ticket.subject,
      description: ticketData.ticket.description,
      status: ticketData.ticket.status,
      priority: ticketData.ticket.priority,
      requester: ticketData.ticket.requester,
      assignee: ticketData.ticket.assignee,
    };
  } catch (error) {
    console.error("티켓 정보 획득 실패:", error);
    throw new Error("현재 티켓 정보를 가져올 수 없습니다.");
  }
}
```

#### 3. FDK 이벤트 리스너 활용

```javascript
// 티켓 변경 감지 및 자동 새로고침
window.parent.app.events.on("app.activated", function () {
  console.log("앱이 활성화되었습니다.");
  initializeApp();
});

window.parent.app.events.on("ticket.propertiesUpdated", function (data) {
  console.log("티켓이 업데이트되었습니다:", data);
  refreshTicketData();
});
```

### FDK 개발 워크플로우

#### 1. 로컬 개발 환경 설정

```bash
# FDK CLI 설치 (글로벌)
npm install https://cdn.freshdev.io/fdk/latest.tgz -g

# 프로젝트 디렉토리로 이동
cd frontend/

# 로컬 개발 서버 실행 (https://localhost:10001)
fdk run

# 새 터미널에서 Freshdesk 개발 환경 접속
# https://your-domain.freshdesk.com/?dev=true
```

#### 2. FDK 빌드 및 배포

```bash
# 앱 검증 (문법, 권한, 구조 체크)
fdk validate

# 프로덕션 빌드 생성
fdk pack

# Freshworks Marketplace에 업로드 (선택사항)
fdk publish
```

#### 3. 환경별 설정 관리

```javascript
// 개발/프로덕션 환경 분기 처리
const CONFIG = {
  development: {
    BACKEND_URL: "http://localhost:8000",
    DEBUG: true,
  },
  production: {
    BACKEND_URL: "https://your-production-api.com",
    DEBUG: false,
  },
};

const currentEnv =
  window.location.hostname === "localhost" ? "development" : "production";
const config = CONFIG[currentEnv];
```

### FDK 보안 및 권한 관리

#### 1. manifest.json 권한 설정

```json
{
  "platform-version": "2.2",
  "product": {
    "freshdesk": {
      "location": {
        "ticket_sidebar": {
          "url": "index.html",
          "icon": "icon.svg"
        }
      },
      "requests": {
        "backend_api": {
          "root": "https://your-backend-api.com",
          "verifySSL": true,
          "headers": {
            "Authorization": "Bearer {{account.apiKey}}"
          }
        }
      }
    }
  }
}
```

#### 2. iparams.json 설정 항목

```json
{
  "backend_url": {
    "display_name": "백엔드 API URL",
    "description": "AI 응답 시스템의 백엔드 서버 주소",
    "type": "text",
    "required": true,
    "default_value": "https://your-backend-api.com"
  },
  "response_style": {
    "display_name": "응답 스타일",
    "description": "AI가 생성하는 응답의 톤앤매너",
    "type": "dropdown",
    "options": [
      { "value": "formal", "label": "공식적" },
      { "value": "friendly", "label": "친근함" },
      { "value": "technical", "label": "기술적" }
    ],
    "default_value": "friendly"
  }
}
```

### FDK 개발 시 주의사항

#### 1. 브라우저 호환성

- **IE 지원 불가**: 최신 브라우저 전용 API 사용 가능
- **CORS 제한**: FDK가 프록시 역할, 직접 외부 API 호출 시 제한
- **보안 정책**: CSP(Content Security Policy) 준수 필요

#### 2. 성능 최적화

```javascript
// 지연 로딩을 통한 초기 로딩 시간 단축
const LazyComponent = React.lazy(() => import("./HeavyComponent"));

// 메모이제이션을 통한 불필요한 재렌더링 방지
const MemoizedTicketSummary = React.memo(TicketSummary);

// 로컬 스토리지 캐싱 (세션 간 데이터 유지)
const cacheTicketData = (ticketId, data) => {
  localStorage.setItem(
    `ticket_${ticketId}`,
    JSON.stringify({
      data,
      timestamp: Date.now(),
      ttl: 1000 * 60 * 30, // 30분 TTL
    })
  );
};
```

#### 3. 에러 핸들링 및 로깅

```javascript
// FDK 전용 에러 처리
class FDKError extends Error {
  constructor(message, code, context) {
    super(message);
    this.name = "FDKError";
    this.code = code;
    this.context = context;
  }
}

// 구조화된 로깅
const logger = {
  info: (message, data) => {
    console.log(`[INFO] ${new Date().toISOString()}: ${message}`, data);
  },
  error: (message, error, context) => {
    console.error(`[ERROR] ${new Date().toISOString()}: ${message}`, {
      error: error.message,
      stack: error.stack,
      context,
    });
  },
};
```

#### 4. FDK 명령 옵션

Usage: fdk [global-flag] [command] [command-flags] [arguments]

The Freshworks CLI enables you to build, test and publish apps on Freshworks Developer Platform

Options:
-v, --version prints the current version
-u, --skip-update-check Skips daily check for new cli versions
-d, --app-dir <directory> directory is the path to the directory where the app will be
created. If this option is not specified, the app will be created
in the current directory.
-h, --help display help for command

Commands:
create [options] Creates a new app based on the specified options
generate Generates configuration files for the app
run [options] Runs the app on a local server for testing
validate [options] Validates the app code
pack [options] Creates the app package that can be submitted to the Marketplace or
published as a custom app
version Displays the currently installed FDK version number
search [options] [query-string] Searches our developer community for a specified post
test [options] Runs the unit tests that are saved as part of the (serverless) app
files
config [options] Allows to reconfigure local and global FDK configurations
help [command] display help for command

### FDK와 백엔드 API 연동 구현

#### 1. 앱 초기화 및 자동 연결 로직

```javascript
// app.js - 메인 앱 진입점
class AIAssistantApp {
  constructor() {
    this.config = null;
    this.ticketInfo = null;
    this.backendClient = null;
    this.isInitialized = false;
  }

  async initialize() {
    try {
      // 1. Freshdesk 설정 및 티켓 정보 병렬 로드
      const [config, ticketInfo] = await Promise.all([
        this.getFreshdeskConfig(),
        this.getCurrentTicketInfo(),
      ]);

      this.config = config;
      this.ticketInfo = ticketInfo;

      // 2. 백엔드 API 클라이언트 초기화
      this.backendClient = new BackendAPIClient(config);

      // 3. 초기 데이터 로드 (/init 호출)
      await this.loadInitialData();

      // 4. UI 렌더링
      this.renderUI();

      this.isInitialized = true;
      console.log("AI Assistant 앱 초기화 완료");
    } catch (error) {
      console.error("앱 초기화 실패:", error);
      this.renderErrorState(error);
    }
  }

  async getFreshdeskConfig() {
    const context = await window.parent.app.instance.context();
    return {
      domain: `${context.account.subdomain}.freshdesk.com`,
      apiKey: context.account.apiKey,
      userId: context.user.id,
      accountId: context.account.id,
    };
  }

  async getCurrentTicketInfo() {
    const ticketData = await window.parent.app.data.get("ticket");
    return {
      id: ticketData.ticket.id,
      subject: ticketData.ticket.subject,
      description:
        ticketData.ticket.description_text || ticketData.ticket.description,
      status: ticketData.ticket.status,
      priority: ticketData.ticket.priority,
    };
  }

  async loadInitialData() {
    // 백엔드 /init 엔드포인트 호출
    const initData = await this.backendClient.init(this.ticketInfo.id);

    // 전역 상태에 저장
    window.appState = {
      ticketSummary: initData.summary,
      similarTickets: initData.similar_tickets,
      recommendedSolutions: initData.recommended_solutions,
      lastUpdated: Date.now(),
    };
  }
}
```

#### 2. 백엔드 API 클라이언트 클래스

```javascript
// api-client.js - 백엔드 통신 전담 클래스
class BackendAPIClient {
  constructor(freshdeskConfig) {
    this.config = freshdeskConfig;
    this.baseURL = this.getBackendURL();
    this.defaultHeaders = {
      "Content-Type": "application/json",
      "X-Freshdesk-Domain": this.config.domain,
      "X-Freshdesk-API-Key": this.config.apiKey,
      "X-User-ID": this.config.userId,
      "X-Account-ID": this.config.accountId,
    };
  }

  getBackendURL() {
    // iparams에서 설정된 백엔드 URL 가져오기
    const params = new URLSearchParams(window.location.search);
    return params.get("backend_url") || "http://localhost:8000";
  }

  async makeRequest(endpoint, options = {}) {
    const url = `${this.baseURL}${endpoint}`;
    const config = {
      headers: { ...this.defaultHeaders, ...options.headers },
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
      throw new APIError(error.message, endpoint, options);
    }
  }

  // 초기 데이터 로드
  async init(ticketId) {
    return await this.makeRequest(`/init/${ticketId}`, {
      method: "POST",
    });
  }

  // 자연어 쿼리 처리
  async query(queryData) {
    return await this.makeRequest("/query", {
      method: "POST",
      body: JSON.stringify({
        ticket_id: this.getCurrentTicketId(),
        ...queryData,
      }),
    });
  }

  getCurrentTicketId() {
    return window.appState?.ticketInfo?.id || null;
  }
}
```

#### 3. 실시간 티켓 변경 감지 및 동기화

```javascript
// event-handlers.js - FDK 이벤트 처리
class EventManager {
  constructor(app) {
    this.app = app;
    this.setupEventListeners();
  }

  setupEventListeners() {
    // 앱 활성화 시 (티켓 페이지 진입)
    window.parent.app.events.on("app.activated", () => {
      console.log("앱 활성화됨");
      if (!this.app.isInitialized) {
        this.app.initialize();
      }
    });

    // 티켓 정보 변경 감지
    window.parent.app.events.on("ticket.propertiesUpdated", (event) => {
      console.log("티켓 업데이트 감지:", event);
      this.handleTicketUpdate(event);
    });

    // 앱 비활성화 시 (다른 탭으로 이동)
    window.parent.app.events.on("app.deactivated", () => {
      console.log("앱 비활성화됨");
      this.cleanup();
    });
  }

  async handleTicketUpdate(event) {
    try {
      // 변경된 티켓 정보 다시 로드
      const updatedTicketInfo = await this.app.getCurrentTicketInfo();

      // 상태 업데이트가 필요한지 확인
      if (this.shouldRefreshData(updatedTicketInfo)) {
        await this.app.loadInitialData();
        this.app.renderUI(); // UI 새로고침
      }
    } catch (error) {
      console.error("티켓 업데이트 처리 실패:", error);
    }
  }

  shouldRefreshData(newTicketInfo) {
    const currentInfo = window.appState?.ticketInfo;
    if (!currentInfo) return true;

    // 중요한 속성이 변경된 경우만 새로고침
    return (
      currentInfo.subject !== newTicketInfo.subject ||
      currentInfo.description !== newTicketInfo.description ||
      currentInfo.status !== newTicketInfo.status
    );
  }

  cleanup() {
    // 메모리 정리, 타이머 해제 등
    if (window.appState?.refreshTimer) {
      clearInterval(window.appState.refreshTimer);
    }
  }
}
```

#### 4. UI 컴포넌트와 상태 관리

```javascript
// components/app-container.js - 메인 UI 컨테이너
class AppContainer {
  constructor(app) {
    this.app = app;
    this.currentTab = "summary";
    this.render();
  }

  render() {
    const container = document.getElementById("app-root");
    container.innerHTML = `
      <div class="ai-assistant-container">
        <!-- 티켓 요약 카드 -->
        <div class="ticket-summary-card">
          ${this.renderTicketSummary()}
        </div>

        <!-- 탭 네비게이션 -->
        <div class="tab-navigation">
          <button class="tab-btn ${
            this.currentTab === "similar" ? "active" : ""
          }" 
                  onclick="appContainer.switchTab('similar')">
            유사 티켓
          </button>
          <button class="tab-btn ${
            this.currentTab === "solutions" ? "active" : ""
          }" 
                  onclick="appContainer.switchTab('solutions')">
            추천 솔루션
          </button>
          <button class="tab-btn ${this.currentTab === "chat" ? "active" : ""}" 
                  onclick="appContainer.switchTab('chat')">
            AI와 대화하기
          </button>
        </div>

        <!-- 탭 컨텐츠 -->
        <div class="tab-content">
          ${this.renderCurrentTab()}
        </div>
      </div>
    `;

    // 이벤트 리스너 재등록
    this.attachEventListeners();
  }

  renderTicketSummary() {
    const summary = window.appState?.ticketSummary;
    if (!summary) return '<div class="loading">요약 로딩 중...</div>';

    return `
      <div class="summary-content">
        <h3>티켓 요약</h3>
        <div class="summary-sections">
          <div class="section">
            <label>문제:</label>
            <p>${summary.problem || "N/A"}</p>
          </div>
          <div class="section">
            <label>원인:</label>
            <p>${summary.cause || "N/A"}</p>
          </div>
          <div class="section">
            <label>권장 조치:</label>
            <p>${summary.recommendation || "N/A"}</p>
          </div>
        </div>
      </div>
    `;
  }

  switchTab(tabName) {
    this.currentTab = tabName;
    this.render();
  }

  async handleChatQuery(query, contentTypes) {
    try {
      const response = await this.app.backendClient.query({
        intent: "search",
        type: contentTypes,
        query: query,
      });

      this.displayChatResponse(response);
    } catch (error) {
      this.displayError("검색 중 오류가 발생했습니다: " + error.message);
    }
  }
}
```

#### 5. 개발/프로덕션 환경 분기 처리

```javascript
// config/environment.js - 환경별 설정 관리
const Environment = {
  isDevelopment() {
    return (
      window.location.hostname === "localhost" ||
      window.location.search.includes("dev=true")
    );
  },

  getConfig() {
    if (this.isDevelopment()) {
      return {
        BACKEND_URL: "http://localhost:8000",
        DEBUG: true,
        LOG_LEVEL: "debug",
      };
    } else {
      return {
        BACKEND_URL: "https://your-production-api.com",
        DEBUG: false,
        LOG_LEVEL: "error",
      };
    }
  },

  // iparams 설정 오버라이드 (개발 시에만)
  getBackendURL() {
    if (this.isDevelopment()) {
      return this.getConfig().BACKEND_URL;
    }

    // 프로덕션에서는 iparams에서 설정된 값 사용
    return (
      new URLSearchParams(window.location.search).get("backend_url") ||
      this.getConfig().BACKEND_URL
    );
  },
};
```

### FDK 디버깅 및 트러블슈팅

#### 1. 로컬 개발 환경 디버깅

```javascript
// debug-utils.js - 개발 전용 디버깅 도구
const DebugUtils = {
  // 개발 모드에서만 동작하는 로거
  log(level, message, data = null) {
    if (!Environment.isDevelopment()) return;

    const timestamp = new Date().toISOString();
    const logMessage = `[${level.toUpperCase()}] ${timestamp}: ${message}`;

    console.log(logMessage);
    if (data) console.log("Data:", data);

    // 디버그 패널에도 표시 (선택사항)
    this.addToDebugPanel(level, message, data);
  },

  // Freshdesk API 응답 검증
  validateFreshdeskContext(context) {
    const required = ["account", "user"];
    const missing = required.filter((key) => !context[key]);

    if (missing.length > 0) {
      throw new Error(
        `Freshdesk context에 필수 정보가 없습니다: ${missing.join(", ")}`
      );
    }

    this.log("info", "Freshdesk context 검증 완료", context);
  },

  // 백엔드 연결 상태 체크
  async checkBackendConnection() {
    try {
      const response = await fetch(`${Environment.getBackendURL()}/health`);
      if (response.ok) {
        this.log("info", "백엔드 연결 성공");
        return true;
      } else {
        this.log("error", `백엔드 연결 실패: ${response.status}`);
        return false;
      }
    } catch (error) {
      this.log("error", "백엔드 연결 에러", error);
      return false;
    }
  },

  // 디버그 패널 UI (개발 모드에서만 표시)
  createDebugPanel() {
    if (!Environment.isDevelopment()) return;

    const panel = document.createElement("div");
    panel.id = "debug-panel";
    panel.style.cssText = `
      position: fixed;
      top: 10px;
      right: 10px;
      width: 300px;
      max-height: 200px;
      background: #f0f0f0;
      border: 1px solid #ccc;
      padding: 10px;
      font-size: 12px;
      overflow-y: auto;
      z-index: 9999;
    `;
    document.body.appendChild(panel);
  },

  addToDebugPanel(level, message, data) {
    const panel = document.getElementById("debug-panel");
    if (!panel) return;

    const entry = document.createElement("div");
    entry.style.marginBottom = "5px";
    entry.innerHTML = `<strong>[${level}]</strong> ${message}`;
    panel.appendChild(entry);

    // 최대 20개 항목만 유지
    while (panel.children.length > 20) {
      panel.removeChild(panel.firstChild);
    }
  },
};
```

#### 2. FDK 특정 에러 처리

```javascript
// error-handler.js - FDK 환경의 에러 처리
class FDKErrorHandler {
  static handle(error, context = {}) {
    const errorInfo = {
      message: error.message,
      name: error.name,
      stack: error.stack,
      context,
      timestamp: new Date().toISOString(),
      userAgent: navigator.userAgent,
      url: window.location.href,
    };

    // 개발 모드에서는 콘솔에 상세 로그
    if (Environment.isDevelopment()) {
      console.error("FDK Error Details:", errorInfo);
    }

    // 사용자에게는 친화적인 메시지 표시
    const userMessage = this.getUserFriendlyMessage(error);
    this.displayUserError(userMessage);

    // 에러 리포팅 (프로덕션에서만)
    if (!Environment.isDevelopment()) {
      this.reportError(errorInfo);
    }
  }

  static getUserFriendlyMessage(error) {
    if (error.name === "NetworkError") {
      return "네트워크 연결을 확인해주세요.";
    }
    if (error.message.includes("Freshdesk")) {
      return "Freshdesk 연결에 문제가 있습니다. 페이지를 새로고침해보세요.";
    }
    if (error.message.includes("backend") || error.message.includes("API")) {
      return "AI 서비스에 일시적인 문제가 있습니다. 잠시 후 다시 시도해주세요.";
    }
    return "예상치 못한 오류가 발생했습니다. 문제가 지속되면 관리자에게 문의하세요.";
  }

  static displayUserError(message) {
    // 기존 에러 메시지 제거
    const existingError = document.getElementById("user-error-message");
    if (existingError) {
      existingError.remove();
    }

    // 새 에러 메시지 표시
    const errorDiv = document.createElement("div");
    errorDiv.id = "user-error-message";
    errorDiv.style.cssText = `
      background: #fee;
      border: 1px solid #fcc;
      color: #c00;
      padding: 10px;
      margin: 10px 0;
      border-radius: 4px;
    `;
    errorDiv.textContent = message;

    const container = document.getElementById("app-root");
    if (container) {
      container.insertBefore(errorDiv, container.firstChild);
    }

    // 5초 후 자동 제거
    setTimeout(() => {
      if (errorDiv.parentNode) {
        errorDiv.parentNode.removeChild(errorDiv);
      }
    }, 5000);
  }

  static async reportError(errorInfo) {
    try {
      // 에러 리포팅 서비스로 전송 (예: Sentry, LogRocket 등)
      await fetch("/api/error-report", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(errorInfo),
      });
    } catch (reportingError) {
      console.error("에러 리포팅 실패:", reportingError);
    }
  }
}

// 글로벌 에러 핸들러 등록
window.addEventListener("error", (event) => {
  FDKErrorHandler.handle(event.error, { type: "javascript" });
});

window.addEventListener("unhandledrejection", (event) => {
  FDKErrorHandler.handle(event.reason, { type: "promise" });
});
```

#### 3. FDK 앱 성능 모니터링

```javascript
// performance-monitor.js - 성능 추적
class PerformanceMonitor {
  constructor() {
    this.metrics = new Map();
    this.startTime = performance.now();
  }

  startTimer(label) {
    this.metrics.set(label, { start: performance.now() });
  }

  endTimer(label) {
    const metric = this.metrics.get(label);
    if (metric) {
      metric.end = performance.now();
      metric.duration = metric.end - metric.start;

      DebugUtils.log(
        "performance",
        `${label}: ${metric.duration.toFixed(2)}ms`
      );

      // 느린 작업 경고 (개발 모드)
      if (Environment.isDevelopment() && metric.duration > 1000) {
        console.warn(
          `⚠️ 느린 작업 감지: ${label} (${metric.duration.toFixed(2)}ms)`
        );
      }
    }
  }

  getAppLoadTime() {
    return performance.now() - this.startTime;
  }

  logMetrics() {
    console.table(
      Array.from(this.metrics.entries()).map(([label, metric]) => ({
        작업: label,
        "소요시간(ms)": metric.duration?.toFixed(2) || "N/A",
      }))
    );
  }

  // 메모리 사용량 체크 (개발 모드)
  checkMemoryUsage() {
    if (Environment.isDevelopment() && "memory" in performance) {
      const memory = performance.memory;
      console.log("메모리 사용량:", {
        used: `${(memory.usedJSHeapSize / 1024 / 1024).toFixed(2)} MB`,
        total: `${(memory.totalJSHeapSize / 1024 / 1024).toFixed(2)} MB`,
        limit: `${(memory.jsHeapSizeLimit / 1024 / 1024).toFixed(2)} MB`,
      });
    }
  }
}
```

### FDK 배포 및 운영 가이드

#### 1. 프로덕션 빌드 체크리스트

```bash
# 1. 코드 검증
fdk validate

# 2. 테스트 실행 (있는 경우)
npm test

# 3. 프로덕션 설정 확인
# - iparams.json 모든 필수 필드 설정
# - manifest.json 권한 및 위치 확인
# - 환경변수 및 API 엔드포인트 검증

# 4. 빌드 생성
fdk pack

# 5. 빌드 파일 확인
ls -la dist/
```

#### 2. 배포 후 모니터링

```javascript
// monitoring.js - 운영 환경 모니터링
const ProductionMonitoring = {
  // 앱 초기화 성공률 추적
  trackInitialization(success, error = null) {
    this.sendMetric("app_initialization", {
      success,
      error: error?.message,
      timestamp: Date.now(),
    });
  },

  // API 호출 성공률 추적
  trackAPICall(endpoint, success, responseTime, error = null) {
    this.sendMetric("api_call", {
      endpoint,
      success,
      response_time_ms: responseTime,
      error: error?.message,
      timestamp: Date.now(),
    });
  },

  // 사용자 행동 추적
  trackUserAction(action, data = {}) {
    this.sendMetric("user_action", {
      action,
      ...data,
      timestamp: Date.now(),
    });
  },

  sendMetric(type, data) {
    // 실제 모니터링 서비스로 전송
    // 예: Google Analytics, Mixpanel, 자체 분석 서버 등
    if (window.gtag) {
      window.gtag("event", type, data);
    }
  },
};
```

---

## 🧩 프론트 설계 원칙

### 동적 초기화 및 자동 연결

- **자동 트리거**: 상담원이 Freshdesk에서 티켓을 열면 Custom App이 자동으로 로드되고 백엔드 연결
- **동적 Freshdesk 설정**: 현재 Freshdesk 도메인과 API 키를 헤더에 포함하여 백엔드에 전달
- **고객사별 데이터 격리**: 백엔드에서 해당 고객사의 데이터만 안전하게 처리

### 기존 원칙 유지

- 모든 API 호출은 **명시적 트리거**만 허용 (자동 요청 최소화)
- 상태관리는 `Zustand` 또는 React Context로 전역 관리
- 영역 간 데이터 공유는 store를 통한 lazy-load 방식
- 직관적이고 간결한 UI로 자연어 명령 입력의 심리적 장벽 최소화
- 백엔드 API 응답 포맷은 이해하기 쉬운 구조로 (`text`, `actions`, `suggestions`, `resources` 등)
- 응답 처리 상태를 시각적으로 명확하게 표시 (로딩, 오류, 완료 등)
- 초기 데이터는 프론트에서 **로컬 캐싱** 처리하여 사용자 경험 최적화

---

## 📐 전체 구조

2개의 주요 영역 구성:

1. **상단: 티켓 요약 카드**
2. **하단: 3가지 탭 영역**
   - 유사 티켓 탭
   - 추천 솔루션 탭
   - OO와 대화하기 탭

> 프론트는 백엔드가 필요한 데이터를 "충분히 준비된 이후" 호출됨. 각 기능은 명시적 사용자 액션에 따라 비동기적으로 백엔드 API를 호출한다.

---

## 🧾 주요 영역 기능 정의

### 1. 상단: 티켓 요약 카드

- 목적: 상담사가 전체 티켓 상황을 빠르게 이해
- **호출 시점**: 상담원이 티켓을 열면 자동으로 `/init` 호출 (1회)
- **동적 헤더 전달**: 현재 Freshdesk 도메인과 API 키를 요청 헤더에 포함
- 캐싱: `localStorage` 또는 메모리 캐시 활용
- UX 요소:
  - 문제 / 원인 / 조치 / 결과 정보 표시

---

### 2. 중단: 3가지 탭 영역

#### 2-1. 유사 티켓 탭

- `/init` 호출로 자동 로딩, 내부적으로 /similar_tickets 호출, 페이지네이션 지원
- 유사 티켓 목록 표시 (제목, 상태, 해결 방법 요약 등)
- 클릭 시 상세 정보 모달 또는 확장 패널로 표시
- 유용한 응답 선택 시 답변 에디터에 자동 삽입 기능

#### 2-2. 추천 솔루션 탭

- `/init` 호출로 자동 로딩, 내부적으로 /related_docs 호출, 페이지네이션 지원
- 추천 솔루션 또는 지식베이스 문서 목록
- 제목, 카테고리, 관련도 점수 표시
- 내용 미리보기 및 답변 에디터에 삽입 기능

#### 2-3. OO와 대화하기 탭

- 자연어 입력창 (placeholder: "질문을 입력하세요...")
- "검색할 콘텐츠" 체크박스:
  - ✅ 티켓 / ✅ 솔루션 / ✅ 이미지 / ✅ 첨부파일
- **"검색" 버튼 클릭 시**: 현재 Freshdesk 도메인/API 키 헤더와 함께 `/query` 호출
- **고객사별 안전 처리**: 백엔드에서 해당 고객사 데이터만 검색하여 응답
- 검색 결과를 동일 탭 내에서 대화형 UI로 표시
- 응답 결과 내에서 직접 '티켓 응답으로 등록' 기능 제공

---

### 2-3. OO와 대화하기 탭 (계속)

- 자연어 요청에 대한 응답은 대화하기 탭 내에서 직접 표시
- 응답 형식:
  - 질문과 답변을 대화형 UI로 표시
  - 유용한 정보는 카드 형태로 구성
  - 검색 결과는 리스트/그리드 형태로 표시
- 공유 및 피드백 기능:
  - 응답 내용 복사 버튼
  - 티켓에 응답 첨부 버튼 (바로 티켓 응답으로 등록)
  - 좋아요/싫어요 피드백 버튼

---

## 🔍 프론트 요청 흐름

### 페이지 최초 로드 (상담원이 티켓 열 때)

- **자동 트리거**: 상담원이 Freshdesk에서 티켓을 열면 Custom App 자동 로드
- **동적 헤더 구성**:
  ```javascript
  const headers = {
    "X-Freshdesk-Domain": getCurrentDomain(), // 예: customer.freshdesk.com
    "X-Freshdesk-API-Key": getCurrentApiKey(), // 현재 세션의 API 키
    "Content-Type": "application/json",
  };
  ```
- **`/init` API 호출**: 위 헤더와 함께 요약/유사 티켓/추천 솔루션 데이터 요청
- **멀티테넌트 안전성**: 백엔드에서 해당 고객사 데이터만 반환
- 초기 데이터는 프론트에서 로컬 캐싱 처리
- 요약 카드 및 초기 탭 데이터 렌더링

### 자연어 요청 처리

- "OO와 대화하기" 탭에서 자연어 입력 + 콘텐츠 선택
- **동적 헤더 포함**:
  ```javascript
  const queryHeaders = {
    "X-Freshdesk-Domain": getCurrentDomain(),
    "X-Freshdesk-API-Key": getCurrentApiKey(),
    "Content-Type": "application/json",
  };
  ```
- **`/query` API 호출**: 위 헤더와 함께 검색할 콘텐츠 타입 정보 전송
- **고객사별 안전 처리**: 백엔드에서 해당 고객사 데이터만 검색하여 응답
- 결과를 동일한 탭 내에서 대화형 UI로 표시
- 유용한 콘텐츠가 있는 경우 카드 형태로 함께 표시

### 결과 활용 흐름

- 대화하기 결과에서 '티켓에 응답으로 등록' 버튼 클릭
- Freshdesk API를 통해 티켓 응답으로 바로 등록 가능
- 성공/실패 피드백 제공

---

## ⚙️ 관리자 설정 (iparams.html)

### 동적 Freshdesk 연동 설정

- **자동 도메인 감지**: 현재 Freshdesk 인스턴스의 도메인 자동 추출
- **API 키 관리**: 각 고객사별 API 키 안전한 저장 및 관리
- **연결 상태 확인**: Freshdesk API 연결 상태 실시간 모니터링

### 기존 설정 옵션

- 인식 가능한 자연어 명령어 범위 설정
- 응답 스타일 및 문체/톤 설정
- 데이터 검색 기간 설정 (예: 1개월, 3개월, 6개월, 전체 등)

### 향후 옵션(로드맵)

- 상담사별 맞춤 자연어 명령 패턴 학습
- 자주 사용하는 명령어 템플릿화
- 응답 품질 평가 및 피드백 시스템

---

## 🛠️ 프론트 개발 핵심 지침

### 동적 Freshdesk 연동 구현

- **자동 도메인/API 키 추출**: Freshdesk FDK API를 통해 현재 인스턴스 정보 획득
- **요청 헤더 자동 구성**: 모든 백엔드 API 호출 시 동적 헤더 포함
- **에러 처리**: 도메인/API 키 추출 실패 시 적절한 에러 메시지 표시
- **보안**: API 키는 메모리에만 저장하고 로컬스토리지 저장 금지

### 기존 지침 유지

- 모든 API 호출은 **명시적 트리거**만 허용 (자동 요청 최소화)
- 상태관리는 `Zustand` 또는 React Context로 전역 관리
- 탭 간 데이터 공유는 store를 통한 lazy-load 방식
- 검색 결과/추천 항목은 페이지네이션/더보기 UX 포함
- 백엔드 API 응답 포맷은 각 탭 콘텐츠에 바로 표시 가능한 구조로 제공
- 티켓 응답으로 바로 등록할 수 있는 기능 제공

### 핵심 구현 예시

```javascript
// Freshdesk 인스턴스 정보 추출
async function getFreshdeskConfig() {
  try {
    const config = await window.parent.app.instance.context();
    return {
      domain: config.account.subdomain + ".freshdesk.com",
      apiKey: config.account.apiKey,
    };
  } catch (error) {
    console.error("Freshdesk 설정 추출 실패:", error);
    throw new Error("Freshdesk 연결 설정을 가져올 수 없습니다.");
  }
}

// 백엔드 API 호출 시 헤더 구성
async function callBackendAPI(endpoint, data = null) {
  const config = await getFreshdeskConfig();
  const headers = {
    "X-Freshdesk-Domain": config.domain,
    "X-Freshdesk-API-Key": config.apiKey,
    "Content-Type": "application/json",
  };

  return fetch(`${BACKEND_URL}${endpoint}`, {
    method: data ? "POST" : "GET",
    headers,
    body: data ? JSON.stringify(data) : null,
  });
}
```
