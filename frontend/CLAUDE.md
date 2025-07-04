# Frontend FDK Development - CLAUDE.md

## 🎯 컨텍스트 & 목적

이 디렉토리는 **Frontend FDK**로 Copilot Canvas의 Freshdesk Development Kit (FDK) JavaScript 애플리케이션을 담당합니다. Freshdesk 플랫폼 내에서 AI 기반 티켓 분석을 위한 사용자 인터페이스를 제공합니다.

**주요 영역:**
- FDK 기반 Freshdesk 애플리케이션 개발
- 모듈화된 아키텍처를 활용한 최신 JavaScript ES6+
- 실시간 UI 업데이트 및 사용자 상호작용
- 백엔드 API 통합 및 상태 관리
- 성능 최적화 및 캐싱 전략

## 🏗️ 디렉토리 구조

```
frontend/
├── app/                   # 메인 애플리케이션
│   ├── index.html        # 메인 HTML 인터페이스
│   ├── scripts/          # JavaScript 모듈들
│   │   ├── globalstate.js    # 중앙화된 상태 관리
│   │   ├── api.js           # 백엔드 통신 레이어
│   │   ├── ui.js            # UI 관리 및 DOM 조작
│   │   ├── events.js        # 이벤트 처리
│   │   ├── data.js          # 데이터 처리 및 변환
│   │   ├── utils.js         # 유틸리티 함수들
│   │   └── debug.js         # 개발/디버깅 도구
│   └── styles/           # CSS 스타일시트
├── config/               # FDK 설정
│   ├── iparams.html     # 설치 매개변수 UI
│   └── requests.json    # API 엔드포인트 정의
├── tests/               # 테스트 스위트
└── coverage/            # 테스트 커버리지 리포트
```

## 🚀 개발 명령어

### FDK 개발 환경
```bash
# FDK 개발 서버 시작
fdk run

# 앱 검증
fdk validate

# 앱 패키징
fdk pack

# 로컬 테스트 환경
fdk run --tunnel
```

### 테스트 및 디버깅
```bash
# 테스트 실행
npm test

# 커버리지 리포트 생성
npm run coverage

# 코드 린팅
npm run lint

# 빌드 (프로덕션)
npm run build
```

## 🔧 핵심 모듈

### 1. GlobalState (`scripts/globalstate.js`)
중앙화된 상태 관리 시스템으로 애플리케이션 전반의 데이터를 관리합니다.

```javascript
// 사용 예시
import GlobalState from './globalstate.js';

// 상태 업데이트
GlobalState.setState({
    currentTicket: ticketData,
    isLoading: false,
    analysisResults: results
});

// 상태 구독
GlobalState.subscribe('currentTicket', (newTicket) => {
    UI.updateTicketDisplay(newTicket);
});
```

### 2. API (`scripts/api.js`)
백엔드와의 통신 및 캐싱을 담당합니다.

```javascript
// 사용 예시
import API from './api.js';

// 티켓 분석 요청
const analysis = await API.analyzeTicket(ticketId, {
    includeRecommendations: true,
    language: 'ko'
});

// 캐시된 데이터 확인
const cachedData = API.getCachedData(`ticket_${ticketId}`);
```

### 3. UI (`scripts/ui.js`)
사용자 인터페이스 관리 및 DOM 조작을 처리합니다.

```javascript
// 사용 예시
import UI from './ui.js';

// 로딩 상태 표시
UI.showLoading('티켓 분석 중...');

// 결과 표시
UI.displayAnalysisResults(analysisData);

// 에러 처리
UI.showError('분석 중 오류가 발생했습니다.');
```

### 4. Events (`scripts/events.js`)
이벤트 처리 및 사용자 상호작용을 관리합니다.

```javascript
// 사용 예시
import Events from './events.js';

// 이벤트 리스너 등록
Events.on('ticketSelected', (ticketData) => {
    GlobalState.setState({ currentTicket: ticketData });
});

// Freshdesk 이벤트 처리
Events.onFreshdeskEvent('ticket.updated', handleTicketUpdate);
```

## 🎯 FDK 특화 기능

### Freshdesk API 통합
```javascript
// Freshdesk 데이터 접근
const ticketData = await client.data.get('ticket');
const contactData = await client.data.get('contact');
const companyData = await client.data.get('company');

// Freshdesk UI 조작
await client.interface.trigger('showNotify', {
    type: 'success',
    message: '분석이 완료되었습니다!'
});
```

### 실시간 업데이트
```javascript
// 실시간 분석 결과 스트리밍
async function streamAnalysis(ticketId) {
    const stream = await API.streamAnalysis(ticketId);
    
    for await (const chunk of stream) {
        UI.updateAnalysisProgress(chunk);
    }
}
```

### 성능 최적화
```javascript
// 지연 로딩
const LazyComponent = {
    async load() {
        if (!this.loaded) {
            await import('./heavy-component.js');
            this.loaded = true;
        }
        return this;
    }
};

// 디바운싱
import { debounce } from './utils.js';

const debouncedSearch = debounce(async (query) => {
    const results = await API.search(query);
    UI.displaySearchResults(results);
}, 300);
```

## ⚠️ 중요 사항

### FDK 제약사항
- Content Security Policy (CSP) 준수 필요
- Freshdesk 플랫폼 내에서만 동작
- 특정 API 호출 제한 및 권한 관리
- 메모리 사용량 최적화 필수

### 성능 고려사항
- 대용량 데이터 처리 시 청킹 및 가상화 적용
- API 호출 최소화를 위한 효율적인 캐싱 전략
- DOM 조작 최적화 (DocumentFragment 활용)
- 이벤트 리스너 정리를 통한 메모리 누수 방지

### 사용자 경험
- 로딩 상태 및 진행률 표시
- 오류 상황에 대한 명확한 피드백
- 키보드 단축키 및 접근성 지원
- 반응형 디자인 (다양한 화면 크기 지원)

---

*상세한 FDK API 참조는 [Freshdesk Developer Documentation](https://developers.freshdesk.com/)을 확인하세요.*

## 🚀 Development Commands

### Environment Setup
```bash
# Install FDK CLI (first time only)
npm install @freshworks/cli -g

# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Start development server
fdk run
```

### Daily Development Workflow
```bash
# Start local development (auto-reload)
fdk run

# Validate app structure
fdk validate

# Package for distribution
fdk pack

# Run tests
npm test

# Generate documentation
npm run docs:generate
npm run docs:serve
```

### Development Server
```bash
# Development mode with live reload
fdk run

# The app will be available at:
# https://your-domain.freshdesk.com/a/tickets/[ticket-id]
# (with ?dev=true parameter)
```

## 📁 Directory Structure

```
frontend/
├── app/                    # Main application files
│   ├── index.html         # Main UI template
│   ├── scripts/           # JavaScript modules
│   │   ├── globals.js     # Global state & module management
│   │   ├── api.js         # Backend API communication
│   │   ├── ui.js          # UI management & DOM manipulation
│   │   ├── events.js      # Event handling system
│   │   ├── data.js        # Data processing & caching
│   │   └── utils.js       # Utility functions
│   └── styles/            # CSS stylesheets & assets
├── config/                # FDK configuration
│   ├── iparams.html      # Installation parameters UI
│   └── requests.json     # API endpoint definitions
├── tests/                # Test suites
├── docs/                 # Generated documentation
└── manifest.json         # FDK app manifest
```

## 🔧 Key Configuration

### Installation Parameters (`config/iparams.html`)
```json
{
  "backendUrl": {
    "display_name": "Backend API URL",
    "description": "URL of the backend API server",
    "type": "text",
    "required": true,
    "default_value": "http://localhost:8000"
  },
  "tenantId": {
    "display_name": "Tenant ID", 
    "description": "Your organization's tenant identifier",
    "type": "text",
    "required": true
  }
}
```

### API Endpoints (`config/requests.json`)
```json
{
  "backendApi": {
    "protocol": "https",
    "host": "<%=iparams.backendUrl%>",
    "endpoints": {
      "init": "/api/init/{{ticket.id}}",
      "query": "/api/query",
      "reply": "/api/reply",
      "search": "/api/search/agent"
    }
  }
}
```

## 🎨 JavaScript Module System

### Global State Management
```javascript
// GlobalState provides centralized state management
const ticketData = GlobalState.getGlobalTicketData();
GlobalState.updateTicketData(newData);

// Module dependency management
ModuleDependencyManager.registerModule('myModule', 5, ['globals', 'utils']);
```

### API Communication
```javascript
// Backend API calls with caching
const result = await API.callBackendAPIWithCache(client, 'init', data, 'POST', {
  useCache: true,
  cacheTTL: 300000, // 5 minutes
  loadingContext: '🎯 AI 분석 중...'
});

// Vector search integration
const searchResults = await API.performAdvancedVectorSearch(client, {
  query: searchQuery,
  filters: { date_range: [startDate, endDate] },
  limit: 20
});
```

### UI Management
```javascript
// Dynamic UI updates
UI.updateTicketSummaryCard(summaryData);
UI.showLoadingState('Analyzing ticket...');
UI.displayError('Connection failed', { retry: true });

// Modal and notification management
UI.showModal(content, { title: 'Analysis Results' });
UI.showNotification('Analysis complete!', 'success');
```

## 🔍 Common Development Tasks

### Adding New Features
```bash
# 1. Create/modify relevant script in app/scripts/
# 2. Update HTML template in app/index.html if needed
# 3. Add CSS styles in app/styles/styles.css
# 4. Register module dependencies
# 5. Test with fdk run
```

### API Integration
```javascript
// Standard pattern for new API calls
async function callNewEndpoint(client, requestData) {
  try {
    const result = await API.callBackendAPIWithCache(
      client, 
      'newEndpoint', 
      requestData, 
      'POST',
      { useCache: false, loadingContext: 'Processing...' }
    );
    
    if (result.ok) {
      UI.updateSomeSection(result.data);
      GlobalState.updateState(result.data);
    } else {
      UI.displayError(result.error);
    }
  } catch (error) {
    console.error('API call failed:', error);
    UI.displayError('Network error occurred');
  }
}
```

### Event Handling
```javascript
// Clean event handling pattern
Events.registerEventHandler('ticket.update', async (eventData) => {
  const analysis = await API.analyzeTicket(client, eventData.ticket.id);
  UI.updateAnalysisResults(analysis);
});

// FDK event integration
app.initialized().then(() => {
  app.events.on('ticket.update', Events.onTicketUpdate);
});
```

## 🎯 User Experience Features

### Real-time Analysis
- Automatic ticket analysis on load
- Progressive loading with visual indicators
- Cached results for improved performance

### Interactive UI Components
- Expandable summary cards
- Similar ticket recommendations
- AI-powered solution suggestions
- Modal dialogs for detailed views

### Performance Optimization
- Lazy loading of heavy components
- Intelligent caching strategy
- Batch API requests
- Memory-efficient DOM manipulation

## 🚨 FDK-Specific Considerations

### Platform Integration
```javascript
// Access Freshdesk data
const ticket = await client.data.get('ticket');
const contact = await client.data.get('contact');

// Trigger Freshdesk actions
await client.interface.trigger('showNotify', {
  type: 'success',
  message: 'Analysis complete!'
});
```

### Security & Permissions
- All API calls go through FDK's secure request system
- Installation parameters are encrypted
- No direct external API calls (must use backend proxy)

### Testing & Debugging
```javascript
// Debug mode detection
if (window.location.hostname === 'localhost' || window.location.search.includes('debug=true')) {
  // Enable debug features
  window.debug = {
    state: () => GlobalState.getGlobalTicketData(),
    modules: () => ModuleDependencyManager.generateStatusReport(),
    perf: () => DebugTools.runPerformanceBenchmark()
  };
}
```

## 📊 Performance Monitoring

### Built-in Performance Tools
```javascript
// Performance benchmarking
const results = await DebugTools.runPerformanceBenchmark();
console.log('Performance Results:', results);

// Memory usage tracking
const memoryReport = DebugTools.getPerformanceReport();
console.log('Memory Usage:', memoryReport);

// Cache optimization
DebugTools.clearAllCaches(); // Reset all caches
```

### Error Handling & Logging
```javascript
// Structured error handling
GlobalState.ErrorHandler.logError(error, {
  context: 'API_CALL',
  ticketId: currentTicket.id,
  userId: currentUser.id
});

// User-friendly error display
UI.displayError('Something went wrong', {
  retry: true,
  details: 'Please try again or contact support'
});
```

## 🔗 Backend Integration

### API Communication Pattern
```javascript
// Standard backend integration
const headers = {
  'X-Tenant-ID': GlobalState.getTenantId(),
  'X-Platform': 'freshdesk',
  'Content-Type': 'application/json'
};

const response = await client.request.invoke('backendApi', {
  url: '/api/endpoint',
  method: 'POST',
  headers: headers,
  body: JSON.stringify(requestData)
});
```

### Data Flow
1. **User Action** → Event handler
2. **Event Handler** → API call preparation
3. **API Module** → Backend communication
4. **Response Processing** → Data transformation
5. **UI Update** → Visual feedback to user
6. **State Management** → Global state update

## 📚 Key Files to Know

- `app/index.html` - Main UI template and structure
- `app/scripts/globals.js` - Global state and module system
- `app/scripts/api.js` - Backend communication layer
- `app/scripts/ui.js` - UI management and DOM manipulation
- `config/iparams.html` - Installation parameter configuration
- `config/requests.json` - API endpoint definitions
- `manifest.json` - FDK app manifest and metadata

## 🔄 Development Workflow

1. **Start Development**: `fdk run` (opens app in Freshdesk)
2. **Make Changes**: Edit files in `app/` directory
3. **Live Reload**: Changes automatically refresh in browser
4. **Test**: Use built-in debug tools and browser dev tools
5. **Validate**: Run `fdk validate` before deployment
6. **Package**: Use `fdk pack` to create deployment package

---

*This worktree focuses exclusively on frontend FDK development. For backend API development, switch to the backend worktree. For documentation updates, use the docs/instructions worktree.*
