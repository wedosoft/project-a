/**
 * Jest 테스트 환경 설정
 * 
 * 이 파일은 모든 테스트 실행 전에 로드되어 테스트 환경을 준비합니다.
 * FDK 환경과 브라우저 환경을 시뮬레이션하고, 전역 객체들을 모킹합니다.
 */

// 전역 테스트 설정
global.console = {
  ...console,
  // 테스트 중 불필요한 로그 출력 제어
  log: jest.fn(),
  debug: jest.fn(),
  info: jest.fn(),
  warn: jest.fn(),
  error: jest.fn(),
};

// 실제 globals.js 파일 로드
const fs = require('fs');
const path = require('path');

// globals.js 파일 읽기 및 실행
const globalsPath = path.join(__dirname, '..', 'app', 'scripts', 'globals.js');
const globalsCode = fs.readFileSync(globalsPath, 'utf8');

// globals.js 코드를 전역 컨텍스트에서 실행
eval(globalsCode);

// FDK 환경 모킹
global.app = {
  initialized: jest.fn().mockResolvedValue({
    iparams: {
      get: jest.fn().mockResolvedValue({
        freshdesk_domain: 'test.freshdesk.com',
        freshdesk_api_key: 'test-api-key',
        backend_url: 'http://localhost:8000'
      })
    },
    context: {
      get: jest.fn().mockResolvedValue({
        ticket: {
          id: '12345',
          subject: 'Test Ticket',
          description: 'Test Description'
        }
      })
    },
    data: {
      get: jest.fn().mockResolvedValue({
        id: '12345',
        subject: 'Test Ticket'
      })
    },
    events: {
      on: jest.fn(),
      off: jest.fn()
    }
  })
};

// 브라우저 API 모킹
global.fetch = jest.fn();
global.localStorage = {
  getItem: jest.fn(),
  setItem: jest.fn(),
  removeItem: jest.fn(),
  clear: jest.fn()
};

global.sessionStorage = {
  getItem: jest.fn(),
  setItem: jest.fn(),
  removeItem: jest.fn(),
  clear: jest.fn()
};

// Performance API 모킹
global.performance = {
  now: jest.fn(() => Date.now()),
  memory: {
    usedJSHeapSize: 1024 * 1024 * 10, // 10MB
    totalJSHeapSize: 1024 * 1024 * 50, // 50MB
    jsHeapSizeLimit: 1024 * 1024 * 100 // 100MB
  },
  mark: jest.fn(),
  measure: jest.fn(),
  getEntriesByType: jest.fn(() => [])
};

// IntersectionObserver 모킹
global.IntersectionObserver = jest.fn().mockImplementation((callback) => ({
  observe: jest.fn(),
  unobserve: jest.fn(),
  disconnect: jest.fn()
}));

// requestAnimationFrame 모킹
global.requestAnimationFrame = jest.fn((cb) => setTimeout(cb, 16));
global.cancelAnimationFrame = jest.fn(clearTimeout);

// DOM 환경 확장
Object.defineProperty(window, 'location', {
  value: {
    hostname: 'localhost',
    href: 'https://localhost:10001'
  },
  writable: true
});

// ResizeObserver 모킹
global.ResizeObserver = jest.fn().mockImplementation(() => ({
  observe: jest.fn(),
  unobserve: jest.fn(),
  disconnect: jest.fn()
}));

// 테스트 유틸리티 함수들
global.testUtils = {
  /**
   * 비동기 작업 완료 대기
   */
  waitFor: (ms = 0) => new Promise(resolve => setTimeout(resolve, ms)),
  
  /**
   * DOM 요소 생성 헬퍼
   */
  createElement: (tag, attributes = {}, innerHTML = '') => {
    const element = document.createElement(tag);
    Object.assign(element, attributes);
    if (innerHTML) element.innerHTML = innerHTML;
    return element;
  },
  
  /**
   * 모킹된 fetch 응답 설정
   */
  mockFetchResponse: (data, status = 200) => {
    global.fetch.mockResolvedValueOnce({
      ok: status >= 200 && status < 300,
      status,
      json: jest.fn().mockResolvedValue(data),
      text: jest.fn().mockResolvedValue(JSON.stringify(data))
    });
  },
  
  /**
   * 모킹된 fetch 에러 설정
   */
  mockFetchError: (error) => {
    global.fetch.mockRejectedValueOnce(error);
  },
  
  /**
   * 콘솔 로그 캡처
   */
  captureConsole: () => {
    const logs = [];
    const originalLog = console.log;
    console.log = (...args) => logs.push(args);
    return {
      logs,
      restore: () => { console.log = originalLog; }
    };
  }
};

// 각 테스트 전후 정리
beforeEach(() => {
  // 모든 모킹 초기화
  jest.clearAllMocks();
  
  // DOM 정리
  document.body.innerHTML = '';
  
  // 전역 상태 초기화
  if (global.window && global.window.GlobalState) {
    global.window.GlobalState.isInitialized = false;
    global.window.GlobalState.globalTicketData = null;
  }
});

afterEach(() => {
  // 타이머 정리
  jest.clearAllTimers();
});

// 전역 에러 핸들러
process.on('unhandledRejection', (reason, promise) => {
  console.error('Unhandled Rejection at:', promise, 'reason:', reason);
});

console.log('🧪 Jest 테스트 환경이 설정되었습니다.');

/**
 * 테스트 유틸리티 객체
 * 모든 테스트에서 공통으로 사용하는 유틸리티 함수들을 제공합니다.
 */
global.TestUtils = {
  /**
   * 테스트 환경 설정
   * 각 테스트 전에 호출하여 깨끗한 환경을 구성합니다.
   */
  setupTestEnvironment() {
    // DOM 초기화
    document.body.innerHTML = '';
    
    // localStorage 초기화
    localStorage.clear();
    
    // sessionStorage 초기화  
    sessionStorage.clear();
    
    // 전역 상태 초기화
    if (global.GlobalState) {
      global.GlobalState.reset();
    }
    
    // 타이머 초기화
    jest.clearAllTimers();
    
    // 모든 모킹 초기화
    jest.clearAllMocks();
  },

  /**
   * 테스트 환경 정리
   * 각 테스트 후에 호출하여 환경을 정리합니다.
   */
  cleanupTestEnvironment() {
    // DOM 정리
    document.body.innerHTML = '';
    
    // 이벤트 리스너 정리
    const elements = document.querySelectorAll('*');
    elements.forEach(element => {
      element.removeEventListener?.();
    });
    
    // 타이머 정리
    jest.clearAllTimers();
    
    // 모킹 정리
    jest.restoreAllMocks();
  },

  /**
   * DOM 요소 생성 헬퍼
   */
  createElement(tag, attributes = {}, textContent = '') {
    const element = document.createElement(tag);
    
    Object.entries(attributes).forEach(([key, value]) => {
      if (key === 'className') {
        element.className = value;
      } else {
        element.setAttribute(key, value);
      }
    });
    
    if (textContent) {
      element.textContent = textContent;
    }
    
    return element;
  },

  /**
   * 비동기 함수 테스트 헬퍼
   */
  async waitFor(callback, timeout = 1000) {
    return new Promise((resolve, reject) => {
      const startTime = Date.now();
      
      const check = () => {
        try {
          const result = callback();
          if (result) {
            resolve(result);
          } else if (Date.now() - startTime > timeout) {
            reject(new Error('Timeout waiting for condition'));
          } else {
            setTimeout(check, 10);
          }
        } catch (error) {
          reject(error);
        }
      };
      
      check();
    });
  },

  /**
   * 이벤트 시뮬레이션 헬퍼
   */
  simulateEvent(element, eventType, eventData = {}) {
    const event = new Event(eventType, { bubbles: true, cancelable: true });
    Object.assign(event, eventData);
    element.dispatchEvent(event);
    return event;
  },

  /**
   * 모킹 데이터 생성 헬퍼
   */
  generateMockData(type, count = 1) {
    const generators = {
      ticket: () => ({
        id: Math.random().toString(36).substr(2, 9),
        subject: `Test Ticket ${Math.floor(Math.random() * 1000)}`,
        description: 'Test description',
        status: 'open',
        priority: 'medium',
        created_at: new Date().toISOString()
      }),
      
      response: () => ({
        id: Math.random().toString(36).substr(2, 9),
        content: `Test response ${Math.floor(Math.random() * 1000)}`,
        blocks: [],
        timestamp: new Date().toISOString()
      })
    };
    
    const generator = generators[type];
    if (!generator) {
      throw new Error(`Unknown mock data type: ${type}`);
    }
    
    return count === 1 ? generator() : Array.from({ length: count }, generator);
  }
};

// TestUtils를 전역 객체에 등록 (다른 테스트 파일에서 접근 가능)
global.TestUtils = TestUtils;

// 콘솔에 TestUtils 로드 확인
console.log('🔧 TestUtils가 전역으로 설정되었습니다.');
