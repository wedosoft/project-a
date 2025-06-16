/**
 * @fileoverview Global state management module for Freshdesk Custom App - Prompt Canvas
 * @description 전역 상태 관리 모듈 (Globals)
 *
 * Freshdesk Custom App - Prompt Canvas
 * 이 파일은 모든 모듈에서 공유되는 전역 변수와 상태를 중앙에서 관리합니다.
 *
 * 주요 기능:
 * - 전역 상태 안전 관리 (GlobalState 객체)
 * - 티켓 데이터 캐시 관리 및 무효화
 * - FDK 클라이언트 생명주기 관리
 * - 로딩 상태 및 에러 상태 추적
 * - 모듈 간 의존성 관리 (ModuleDependencyManager)
 * - 타입 검증 및 데이터 무결성 보장
 *
 * 사용 패턴:
 * - 모든 전역 변수는 GlobalState 객체를 통해 접근
 * - 직접 전역 변수 선언 및 접근 금지
 * - 모듈 등록을 통한 의존성 관리
 *
 * @author AI Assistant Frontend Team
 * @version 3.3.0
 * @since 1.0.0
 * @namespace GlobalState
 * @author Freshdesk Custom App Team
 * @since 1.0.0
 */

// === 전역 객체 및 변수 정의 ===

/**
 * FDK 클라이언트 객체 (앱 초기화 후 설정됨)
 * Freshdesk 플랫폼과의 통신을 담당하는 핵심 객체
 * @type {Object|null}
 */
let client = null;

/**
 * 앱 초기화 상태 플래그
 * @type {boolean}
 */
let isInitialized = false;

/**
 * 전역 티켓 데이터 캐시
 * 백엔드 API 응답 데이터를 저장하고 관리합니다.
 * @type {Object}
 */
let globalTicketData = {
  summary: null, // 티켓 요약 정보
  similar_tickets: [], // 유사 티켓 목록
  recommended_solutions: [], // 추천 솔루션 목록 (kb_documents와 매핑)
  cached_ticket_id: null, // 캐시된 티켓 ID
  ticket_info: null, // 백엔드에서 받은 완전한 티켓 정보
  isLoading: false, // 로딩 상태 플래그
  lastLoadTime: null, // 마지막 로드 시간
};

// === 전역 변수 접근자 함수들 ===

/**
 * Set the FDK client object
 * FDK 클라이언트 객체 설정
 * @param {Object} newClient - FDK client object / FDK 클라이언트 객체
 * @memberof GlobalState
 */
function setClient(newClient) {
  if (!newClient) {
    console.warn('⚠️ 유효하지 않은 클라이언트 객체입니다.');
    return;
  }
  client = newClient;
  console.log('✅ FDK 클라이언트 설정 완료');
}

/**
 * Get the FDK client object
 * FDK 클라이언트 객체 반환
 * @returns {Object|null} FDK client object or null if not initialized / FDK 클라이언트 객체 또는 초기화되지 않은 경우 null
 * @memberof GlobalState
 */
function getClient() {
  if (!client) {
    console.warn('⚠️ FDK 클라이언트가 아직 초기화되지 않았습니다.');
  }
  return client;
}

/**
 * 앱 초기화 상태 설정
 * @param {boolean} state - 초기화 상태
 */
function setInitialized(state) {
  isInitialized = Boolean(state);
  console.log(`🔄 앱 초기화 상태: ${isInitialized ? '완료' : '대기중'}`);
}

/**
 * 앱 초기화 상태 확인
 * @returns {boolean} 초기화 완료 여부
 */
function getInitialized() {
  return isInitialized;
}

/**
 * 전역 티켓 데이터 업데이트
 *
 * 특정 데이터 타입을 업데이트하거나 전체 데이터를 병합 업데이트합니다.
 * 업데이트 시간을 자동으로 기록하여 캐시 만료 확인에 사용됩니다.
 *
 * @param {Object} newData - 업데이트할 데이터
 * @param {string} dataType - 데이터 타입 ('summary', 'similar_tickets', 'recommended_solutions' 등)
 *
 * @example
 * updateGlobalTicketData(ticketSummary, 'summary');
 * updateGlobalTicketData({ summary: data, similar_tickets: tickets });
 */
function updateGlobalTicketData(newData, dataType = null) {
  if (!newData) {
    console.warn('⚠️ 업데이트할 데이터가 없습니다.');
    return;
  }

  if (dataType && dataType in globalTicketData) {
    // 특정 데이터 타입만 업데이트
    globalTicketData[dataType] = newData;
    console.log(`📊 전역 데이터 업데이트: ${dataType}`);
  } else if (typeof newData === 'object' && !dataType) {
    // 전체 데이터 객체 병합 업데이트
    globalTicketData = { ...globalTicketData, ...newData };
    console.log('📊 전역 데이터 전체 업데이트 완료');
  } else {
    console.warn('⚠️ 유효하지 않은 데이터 타입 또는 형식입니다.');
    return;
  }

  // 마지막 업데이트 시간 기록
  globalTicketData.lastLoadTime = new Date().toISOString();
}

/**
 * 전역 티켓 데이터 조회
 *
 * 특정 데이터 타입을 조회하거나 전체 데이터를 반환합니다.
 *
 * @param {string|null} dataType - 조회할 데이터 타입 (null이면 전체 반환)
 * @returns {any} 요청된 데이터
 *
 * @example
 * const summary = getGlobalTicketData('summary');
 * const allData = getGlobalTicketData();
 */
function getGlobalTicketData(dataType = null) {
  if (dataType && dataType in globalTicketData) {
    return globalTicketData[dataType];
  }
  return globalTicketData;
}

/**
 * 전역 티켓 데이터 캐시 초기화
 *
 * 새로운 티켓으로 전환하거나 데이터를 완전히 리셋할 때 사용합니다.
 * 모든 캐시 데이터를 초기 상태로 되돌리고 새로운 티켓 ID를 설정합니다.
 *
 * @param {string|null} ticketId - 새로운 티켓 ID (선택사항)
 *
 * @example
 * resetGlobalTicketCache('TICKET-123');
 * resetGlobalTicketCache(); // 전체 초기화
 */
function resetGlobalTicketCache(ticketId = null) {
  console.log('🔄 전역 티켓 캐시 초기화 시작');

  globalTicketData = {
    summary: null,
    similar_tickets: [],
    recommended_solutions: [],
    cached_ticket_id: ticketId,
    ticket_info: null,
    isLoading: false,
    lastLoadTime: null,
  };

  console.log('✅ 전역 티켓 캐시 초기화 완료');
}

/**
 * 캐시된 데이터의 유효성 검사
 * @param {number} maxAgeMinutes - 최대 캐시 유지 시간 (분)
 * @returns {boolean} 캐시 데이터 유효성 여부
 */
function isGlobalDataValid(maxAgeMinutes = 30) {
  if (!globalTicketData.lastLoadTime) {
    return false;
  }

  const lastLoad = new Date(globalTicketData.lastLoadTime);
  const now = new Date();
  const diffMinutes = (now - lastLoad) / (1000 * 60);

  return diffMinutes < maxAgeMinutes;
}

/**
 * 로딩 상태 관리
 * @param {boolean} state - 로딩 상태
 */
function setGlobalLoading(state) {
  globalTicketData.isLoading = Boolean(state);
  console.log(`🔄 전역 로딩 상태: ${globalTicketData.isLoading ? 'ON' : 'OFF'}`);
}

/**
 * 로딩 상태 확인
 * @returns {boolean} 현재 로딩 상태
 */
function getGlobalLoading() {
  return globalTicketData.isLoading;
}

// === 디버깅 및 개발 지원 함수 ===

/**
 * 전역 상태 디버깅 정보 출력
 */
function debugGlobalState() {
  console.group('🔍 전역 상태 디버깅 정보');
  console.log('📱 FDK 클라이언트:', client ? '설정됨' : '미설정');
  console.log('🔄 초기화 상태:', isInitialized);
  console.log('📊 티켓 데이터 캐시:', globalTicketData);
  console.log('⏰ 마지막 업데이트:', globalTicketData.lastLoadTime);
  console.log('🔄 로딩 상태:', globalTicketData.isLoading);
  console.groupEnd();
}

/**
 * 전역 상태 검증
 * @returns {Object} 검증 결과
 */
function validateGlobalState() {
  const validation = {
    hasClient: !!client,
    isInitialized: isInitialized,
    hasTicketData: !!globalTicketData.cached_ticket_id,
    isDataFresh: isGlobalDataValid(),
    isLoading: globalTicketData.isLoading,
  };

  validation.isHealthy = validation.hasClient && validation.isInitialized && !validation.isLoading;

  return validation;
}

// === 외부 접근 인터페이스 정의 ===

/**
 * Global state management object (GlobalState)
 * 전역 상태 관리 객체 (GlobalState)
 *
 * A unified interface for safe access to global state from other modules.
 * All global variables and state should be accessed only through this object.
 *
 * 다른 모듈에서 안전하게 전역 상태에 접근할 수 있는 통합 인터페이스입니다.
 * 모든 전역 변수와 상태는 이 객체를 통해서만 접근해야 합니다.
 *
 * Features:
 * 제공 기능:
 * - FDK client lifecycle management / FDK 클라이언트 생명주기 관리
 * - App initialization state tracking / 앱 초기화 상태 추적
 * - Ticket data cache management / 티켓 데이터 캐시 관리
 * - Loading state management / 로딩 상태 관리
 * - Data validation / 데이터 유효성 검증
 *
 * @example
 * // Client setup / 클라이언트 설정
 * GlobalState.setClient(app.client);
 *
 * // Data update / 데이터 업데이트
 * GlobalState.updateGlobalTicketData(newData, 'summary');
 *
 * // State query / 상태 조회
 * const isReady = GlobalState.getInitialized();
 *
 * @namespace GlobalState
 * @global
 */
window.GlobalState = {
  // 클라이언트 관리
  setClient,
  getClient,

  // 초기화 상태 관리
  setInitialized,
  getInitialized,

  // 티켓 데이터 관리
  updateGlobalTicketData,
  getGlobalTicketData,
  resetGlobalTicketCache,
  isGlobalDataValid,

  // 로딩 상태 관리
  setGlobalLoading,
  getGlobalLoading,

  // 디버깅 및 검증
  debugGlobalState,
  validateGlobalState,
};

// 개발 환경에서는 전역 변수도 직접 접근 가능하도록 설정
if (window.location.hostname === 'localhost' || window.location.hostname.includes('10001')) {
  window.GlobalDebug = {
    client,
    isInitialized,
    globalTicketData,
  };

  console.log('🛠️ 개발 모드: GlobalDebug 객체가 window에 등록되었습니다.');
}

console.log('✅ globals.js 모듈 로드 완료 - 전역 상태 관리 준비됨');

// 글로벌 에러 처리 시스템 개선
window.GlobalState.ErrorHandler = {
  // 에러 로그 저장소
  errorLog: [],
  maxLogSize: 50,

  /**
   * 통합 에러 처리 함수
   *
   * 모든 모듈에서 발생하는 에러를 일관된 방식으로 처리합니다.
   * 에러 정보를 수집하고, 사용자 친화적 메시지를 표시하며, 개발자 디버깅 정보를 제공합니다.
   *
   * @param {Error|string} error - 에러 객체 또는 메시지
   * @param {Object} context - 에러 발생 컨텍스트 정보
   * @param {string} context.module - 에러가 발생한 모듈명
   * @param {string} context.function - 에러가 발생한 함수명
   * @param {string} context.context - 상세 컨텍스트 정보
   * @param {string} context.userMessage - 사용자에게 표시할 메시지 (선택사항)
   * @returns {Object} 에러 정보 객체
   */
  handleError(error, context = {}) {
    const errorInfo = {
      id: `error-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      timestamp: new Date().toISOString(),
      message: error.message || error,
      stack: error.stack,
      context: {
        module: context.module || 'unknown',
        function: context.function || 'unknown',
        details: context.context || '',
        ...context,
      },
      url: window.location.href,
      userAgent: navigator.userAgent,
      appState: this.getAppStateSnapshot(),
    };

    // 에러 로그에 추가 (최신 순)
    this.errorLog.unshift(errorInfo);
    if (this.errorLog.length > this.maxLogSize) {
      this.errorLog = this.errorLog.slice(0, this.maxLogSize);
    }

    // 콘솔에 구조화된 에러 출력
    console.group(`🚨 [${context.module?.toUpperCase() || 'ERROR'}] ${errorInfo.message}`);
    console.error('📍 위치:', context.function || 'unknown function');
    console.error('🔍 상세:', context.details || 'no details');
    console.error('� 앱 상태:', errorInfo.appState);
    if (error.stack) {
      console.error('📚 스택 트레이스:', error.stack);
    }
    console.groupEnd();

    // 사용자에게 친화적인 에러 메시지 표시
    const userMessage = context.userMessage || this.getUserFriendlyMessage(error, context);
    this.showUserError(userMessage, context.severity || 'error');

    // 심각한 에러의 경우 추가 처리
    if (context.severity === 'critical') {
      this.handleCriticalError(errorInfo);
    }

    return errorInfo;
  },

  /**
   * 앱 상태 스냅샷 생성
   * 에러 발생 시점의 앱 상태를 기록하여 디버깅에 활용
   */
  getAppStateSnapshot() {
    try {
      const globalData = GlobalState.getGlobalTicketData();
      return {
        isInitialized: GlobalState.getInitialized(),
        hasClient: !!GlobalState.getClient(),
        cachedTicketId: globalData.cached_ticket_id,
        hasTicketData: !!globalData.ticket_info,
        hasSummary: !!globalData.summary,
        isLoading: globalData.isLoading,
        lastLoadTime: globalData.lastLoadTime,
        modulesLoaded: Array.from(ModuleDependencyManager.loadedModules),
      };
    } catch (err) {
      return { error: '상태 스냅샷 생성 실패', message: err.message };
    }
  },

  /**
   * 사용자 친화적 에러 메시지 변환
   *
   * 기술적인 에러 메시지를 사용자가 이해하기 쉬운 메시지로 변환합니다.
   * 컨텍스트에 따라 적절한 해결 방법을 제시합니다.
   *
   * @param {Error|string} error - 원본 에러 객체 또는 메시지
   * @param {Object} context - 에러 발생 컨텍스트 정보
   * @returns {string} 사용자 친화적 에러 메시지
   *
   * @example
   * const message = ErrorHandler.getUserFriendlyMessage(error, { type: 'api' });
   */
  getUserFriendlyMessage(error, context) {
    const errorMessage = error.message || error;

    // 모듈 관련 에러
    if (errorMessage.includes('undefined') && context.module) {
      return `${context.module} 모듈을 불러오는 중 문제가 발생했습니다. 페이지를 새로고침해 주세요.`;
    }

    // API 관련 에러
    if (context.type === 'api') {
      return '서버와의 연결에 문제가 발생했습니다. 잠시 후 다시 시도해 주세요.';
    }

    // FDK 관련 에러
    if (errorMessage.includes('EventAPI') || context.type === 'fdk') {
      return 'Freshdesk 연결에 문제가 발생했습니다. 페이지를 새로고침해 주세요.';
    }

    // 기본 에러 메시지
    return '예상치 못한 오류가 발생했습니다. 문제가 계속되면 관리자에게 문의해 주세요.';
  },

  /**
   * 심각한 에러 처리
   *
   * 앱의 기본 기능에 영향을 주는 심각한 에러에 대한 특별 처리
   *
   * @param {Object} errorInfo - 에러 정보 객체
   */
  handleCriticalError(errorInfo) {
    console.error('💥 심각한 에러 발생:', errorInfo);

    // 에러 복구 시도 (예: 앱 재초기화)
    try {
      // 전역 상태 초기화
      GlobalState.resetGlobalTicketCache();

      // 사용자에게 복구 안내
      this.showUserError(
        '심각한 오류가 발생했습니다. 앱을 다시 시작합니다. 문제가 계속되면 페이지를 새로고침해 주세요.',
        'critical'
      );

      // 일정 시간 후 앱 재시작 시도
      setTimeout(() => {
        if (typeof window.initializeApp === 'function') {
          window.initializeApp();
        }
      }, 2000);
    } catch (recoveryError) {
      console.error('💀 에러 복구 실패:', recoveryError);
      this.showUserError(
        '복구할 수 없는 오류가 발생했습니다. 페이지를 새로고침해 주세요.',
        'critical'
      );
    }
  },

  /**
   * 개선된 사용자 에러 표시
   *
   * 에러 심각도에 따라 다른 UI 스타일과 지속 시간을 적용합니다.
   *
   * @param {string} message - 표시할 메시지
   * @param {string} severity - 에러 심각도 ('info'|'warning'|'error'|'critical')
   */
  showUserError(message, severity = 'error') {
    // UI 모듈이 있으면 사용, 없으면 기본 토스트 사용
    if (typeof UI !== 'undefined' && UI.showToast) {
      const duration = severity === 'critical' ? 10000 : severity === 'error' ? 5000 : 3000;
      UI.showToast(message, severity, duration);
    } else {
      this.showToast(message, severity);
    }
  },

  // 간단한 토스트 메시지 표시
  showToast(message, type = 'info') {
    const toastId = `toast-${Date.now()}`;
    const toast = document.createElement('div');
    toast.id = toastId;
    toast.className = `error-toast toast-${type}`;
    toast.innerHTML = `
      <div class="toast-content">
        <span class="toast-icon">${type === 'error' ? '⚠️' : 'ℹ️'}</span>
        <span class="toast-message">${message}</span>
        <button class="toast-close" onclick="document.getElementById('${toastId}').remove()">×</button>
      </div>
    `;

    // 스타일 추가
    toast.style.cssText = `
      position: fixed;
      top: 20px;
      right: 20px;
      background: ${type === 'error' ? '#fee' : '#eff'};
      border: 1px solid ${type === 'error' ? '#fcc' : '#cff'};
      border-radius: 4px;
      padding: 12px;
      max-width: 300px;
      z-index: 10000;
      box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    `;

    document.body.appendChild(toast);

    // 5초 후 자동 제거
    setTimeout(() => {
      const element = document.getElementById(toastId);
      if (element) element.remove();
    }, 5000);
  },

  // 에러 로그 조회
  getErrorLog() {
    return this.errorLog;
  },

  // 에러 로그 지우기
  clearErrorLog() {
    this.errorLog = [];
    console.log('🧹 에러 로그가 지워졌습니다.');
  },

  // 개발 모드용 상세 에러 표시
  showDetailedError(error, context) {
    if (window.location.hostname === 'localhost') {
      console.group('🔍 상세 에러 정보');
      console.error('Error:', error);
      console.log('Context:', context);
      console.log('Stack:', error.stack);
      console.groupEnd();
    }
  },
};

// 글로벌 에러 핸들러 등록
window.addEventListener('error', (event) => {
  ErrorHandler.handleError(event.error, {
    type: 'javascript',
    filename: event.filename,
    lineno: event.lineno,
    colno: event.colno,
  });
});

window.addEventListener('unhandledrejection', (event) => {
  ErrorHandler.handleError(event.reason, {
    type: 'promise',
    source: 'unhandledPromise',
  });
});

console.log('🛡️ 글로벌 에러 처리 시스템 초기화 완료');

// === 모듈 의존성 검증 시스템 ===

/**
 * 모듈 의존성 관리자 (ModuleDependencyManager)
 *
 * 각 모듈의 로드 상태와 의존성을 추적하고 검증하는 시스템입니다.
 * 모듈 간 의존성을 명시적으로 관리하여 로드 순서 문제를 방지합니다.
 *
 * 의존성 구조:
 * - globals: 기초 모듈 (의존성 없음)
 * - utils: globals 의존
 * - api: globals, utils 의존
 * - data: globals, api 의존
 * - ui: globals, utils, data 의존
 * - events: globals, ui, data 의존
 * - app: 모든 모듈이 로드된 후 실행 (진입점)
 *
 * @namespace ModuleDependencyManager
 */
const ModuleDependencyManager = {
  // 로드된 모듈들 추적
  loadedModules: new Set(),

  // 모듈별 의존성 정의
  dependencies: {
    app: [], // 앱은 의존성 없음 (진입점)
    globals: [], // globals는 의존성 없음 (기초)
    utils: ['globals'], // utils는 globals에 의존
    api: ['globals', 'utils'], // api는 globals, utils에 의존
    data: ['globals', 'api'], // data는 globals, api에 의존
    ui: ['globals', 'utils', 'data'], // ui는 globals, utils, data에 의존
    events: ['globals', 'ui', 'data'], // events는 globals, ui, data에 의존
  },

  /**
   * 모듈 로드 완료 등록
   *
   * 모듈이 로드 완료되면 등록하고 의존성을 자동 검증합니다.
   * export된 함수/객체 개수를 함께 기록하여 모듈 상태를 추적합니다.
   *
   * @param {string} moduleName - 등록할 모듈명
   * @param {number} exportCount - export된 함수/객체 개수
   *
   * @example
   * ModuleDependencyManager.registerModule('utils', 5);
   */
  registerModule(moduleName, exportCount = 0) {
    this.loadedModules.add(moduleName);
    console.log(`📦 [${moduleName.toUpperCase()}] 모듈 로드 완료 (exports: ${exportCount}개)`);

    // 의존성 검증
    const dependencyCheck = this.checkDependencies(moduleName);
    if (dependencyCheck.success) {
      console.log(`✅ [${moduleName.toUpperCase()}] 의존성 검증 성공`);
    } else {
      console.warn(`⚠️ [${moduleName.toUpperCase()}] 의존성 누락:`, dependencyCheck.missing);
    }
  },

  /**
   * 특정 모듈의 의존성 검증
   * @param {string} moduleName - 검증할 모듈명
   * @returns {Object} 검증 결과
   */
  checkDependencies(moduleName) {
    const requiredDeps = this.dependencies[moduleName] || [];
    const missing = requiredDeps.filter((dep) => !this.loadedModules.has(dep));

    return {
      success: missing.length === 0,
      missing: missing,
      required: requiredDeps,
      loaded: Array.from(this.loadedModules),
    };
  },

  /**
   * 전체 모듈 상태 리포트
   */
  generateStatusReport() {
    console.group('📋 모듈 의존성 상태 리포트');

    Object.keys(this.dependencies).forEach((moduleName) => {
      const status = this.checkDependencies(moduleName);
      const isLoaded = this.loadedModules.has(moduleName);

      console.log(`${isLoaded ? '✅' : '❌'} ${moduleName}:`, {
        loaded: isLoaded,
        dependenciesOK: status.success,
        missing: status.missing,
      });
    });

    console.groupEnd();
  },

  /**
   * 모듈이 사용 가능한지 확인
   * @param {string} moduleName - 확인할 모듈명
   * @returns {boolean} 사용 가능 여부
   */
  isModuleReady(moduleName) {
    const isLoaded = this.loadedModules.has(moduleName);
    const depsOK = this.checkDependencies(moduleName).success;
    return isLoaded && depsOK;
  },

  /**
   * 모든 핵심 모듈이 준비되었는지 확인
   * @returns {boolean} 전체 시스템 준비 상태
   */
  isSystemReady() {
    const coreModules = ['globals', 'utils', 'api', 'data', 'ui', 'events'];
    return coreModules.every((module) => this.isModuleReady(module));
  },
};

// globals 모듈 자체 등록
ModuleDependencyManager.registerModule('globals', Object.keys(GlobalState).length);

console.log('🔧 모듈 의존성 검증 시스템 초기화 완료');

// === 개발자 디버깅 도구 시스템 ===

/**
 * 개발자 디버깅 도구 모음
 *
 * 개발 및 운영 환경에서 앱 상태를 모니터링하고 디버깅할 수 있는 도구들을 제공합니다.
 * 콘솔 명령어, 상태 검사, 성능 모니터링, 에러 분석 등의 기능을 포함합니다.
 *
 * @namespace DebugTools
 */
const DebugTools = {
  // 디버그 모드 플래그
  isDebugMode:
    window.location.hostname === 'localhost' || window.location.search.includes('debug=true'),

  // 성능 측정 저장소
  performanceLog: [],
  maxPerformanceEntries: 100,

  /**
   * 앱 상태 종합 검사
   *
   * 현재 앱의 전반적인 상태를 검사하고 리포트를 생성합니다.
   * 모듈 로드 상태, 데이터 캐시, 에러 로그 등을 종합적으로 분석합니다.
   *
   * @returns {Object} 상태 검사 리포트
   */
  checkAppHealth() {
    const report = {
      timestamp: new Date().toISOString(),
      overall: 'unknown',
      checks: {},
    };

    try {
      // 1. 모듈 로드 상태 검사
      report.checks.modules = this.checkModuleStatus();

      // 2. 전역 상태 검사
      report.checks.globalState = this.checkGlobalState();

      // 3. 에러 상태 검사
      report.checks.errors = this.checkErrorStatus();

      // 4. 성능 상태 검사
      report.checks.performance = this.checkPerformanceStatus();

      // 5. FDK 연결 상태 검사
      report.checks.fdk = this.checkFDKStatus();

      // 전체 상태 판정
      const healthyChecks = Object.values(report.checks).filter(
        (check) => check.status === 'healthy'
      ).length;
      const totalChecks = Object.keys(report.checks).length;

      if (healthyChecks === totalChecks) {
        report.overall = 'healthy';
      } else if (healthyChecks >= totalChecks * 0.7) {
        report.overall = 'warning';
      } else {
        report.overall = 'critical';
      }

      // 콘솔에 상태 리포트 출력
      this.printHealthReport(report);

      return report;
    } catch (error) {
      console.error('🚨 상태 검사 중 오류 발생:', error);
      report.overall = 'critical';
      report.error = error.message;
      return report;
    }
  },

  /**
   * 모듈 로드 상태 검사
   */
  checkModuleStatus() {
    const moduleStatus = {
      status: 'unknown',
      details: {},
      loadedCount: 0,
      totalCount: 0,
    };

    try {
      const expectedModules = ['globals', 'utils', 'api', 'data', 'ui', 'events', 'app'];
      moduleStatus.totalCount = expectedModules.length;

      expectedModules.forEach((moduleName) => {
        const isLoaded = ModuleDependencyManager.loadedModules.has(moduleName);
        const hasExports =
          window[moduleName.charAt(0).toUpperCase() + moduleName.slice(1)] !== undefined;

        moduleStatus.details[moduleName] = {
          loaded: isLoaded,
          hasExports: hasExports,
          status: isLoaded && hasExports ? 'ok' : 'missing',
        };

        if (isLoaded && hasExports) {
          moduleStatus.loadedCount++;
        }
      });

      const loadRatio = moduleStatus.loadedCount / moduleStatus.totalCount;
      moduleStatus.status =
        loadRatio >= 0.8 ? 'healthy' : loadRatio >= 0.5 ? 'warning' : 'critical';
    } catch (error) {
      moduleStatus.status = 'error';
      moduleStatus.error = error.message;
    }

    return moduleStatus;
  },

  /**
   * 전역 상태 검사
   */
  checkGlobalState() {
    const stateStatus = {
      status: 'unknown',
      details: {},
    };

    try {
      const globalData = GlobalState.getGlobalTicketData();

      stateStatus.details = {
        isInitialized: GlobalState.getInitialized(),
        hasClient: !!GlobalState.getClient(),
        hasTicketData: !!globalData.ticket_info,
        hasSummary: !!globalData.summary,
        cachedTicketId: globalData.cached_ticket_id,
        isLoading: globalData.isLoading,
        lastLoadTime: globalData.lastLoadTime,
        cacheAge: globalData.lastLoadTime
          ? Math.round((Date.now() - new Date(globalData.lastLoadTime).getTime()) / 1000)
          : null,
      };

      // 상태 건강도 판정
      const healthyStates = [
        stateStatus.details.isInitialized,
        stateStatus.details.hasClient,
        !stateStatus.details.isLoading,
      ].filter(Boolean).length;

      stateStatus.status = healthyStates >= 2 ? 'healthy' : 'warning';
    } catch (error) {
      stateStatus.status = 'error';
      stateStatus.error = error.message;
    }

    return stateStatus;
  },

  /**
   * 에러 상태 검사
   */
  checkErrorStatus() {
    const errorStatus = {
      status: 'unknown',
      details: {},
    };

    try {
      const errorLog = GlobalState.ErrorHandler.errorLog;
      const recentErrors = errorLog.filter((error) => {
        const errorTime = new Date(error.timestamp).getTime();
        const fiveMinutesAgo = Date.now() - 5 * 60 * 1000;
        return errorTime > fiveMinutesAgo;
      });

      const criticalErrors = errorLog.filter((error) => error.context.severity === 'critical');

      errorStatus.details = {
        totalErrors: errorLog.length,
        recentErrors: recentErrors.length,
        criticalErrors: criticalErrors.length,
        lastError: errorLog[0]
          ? {
              timestamp: errorLog[0].timestamp,
              message: errorLog[0].message,
              module: errorLog[0].context.module,
            }
          : null,
      };

      // 에러 상태 판정
      if (criticalErrors.length > 0) {
        errorStatus.status = 'critical';
      } else if (recentErrors.length > 3) {
        errorStatus.status = 'warning';
      } else {
        errorStatus.status = 'healthy';
      }
    } catch (error) {
      errorStatus.status = 'error';
      errorStatus.error = error.message;
    }

    return errorStatus;
  },

  /**
   * 성능 상태 검사
   */
  checkPerformanceStatus() {
    const perfStatus = {
      status: 'unknown',
      details: {},
    };

    try {
      const navigation = performance.getEntriesByType('navigation')[0];
      const resources = performance.getEntriesByType('resource');

      perfStatus.details = {
        pageLoadTime: navigation
          ? Math.round(navigation.loadEventEnd - navigation.fetchStart)
          : null,
        domContentLoaded: navigation
          ? Math.round(navigation.domContentLoadedEventEnd - navigation.fetchStart)
          : null,
        resourceCount: resources.length,
        memoryUsage: performance.memory
          ? {
              used: Math.round(performance.memory.usedJSHeapSize / 1024 / 1024),
              total: Math.round(performance.memory.totalJSHeapSize / 1024 / 1024),
              limit: Math.round(performance.memory.jsHeapSizeLimit / 1024 / 1024),
            }
          : null,
      };

      // 성능 상태 판정
      const loadTime = perfStatus.details.pageLoadTime;
      if (loadTime < 2000) {
        perfStatus.status = 'healthy';
      } else if (loadTime < 5000) {
        perfStatus.status = 'warning';
      } else {
        perfStatus.status = 'critical';
      }
    } catch (error) {
      perfStatus.status = 'error';
      perfStatus.error = error.message;
    }

    return perfStatus;
  },

  /**
   * FDK 연결 상태 검사
   */
  checkFDKStatus() {
    const fdkStatus = {
      status: 'unknown',
      details: {},
    };

    try {
      const hasParentApp = typeof window.parent !== 'undefined' && window.parent !== window;
      const hasAppObject = hasParentApp && typeof window.parent.app !== 'undefined';
      const client = GlobalState.getClient();

      fdkStatus.details = {
        hasParentWindow: hasParentApp,
        hasAppObject: hasAppObject,
        hasClient: !!client,
        isDevelopment: window.location.hostname === 'localhost',
        currentUrl: window.location.href,
      };

      // FDK 상태 판정
      if (fdkStatus.details.isDevelopment || (hasParentApp && hasAppObject && client)) {
        fdkStatus.status = 'healthy';
      } else if (hasParentApp) {
        fdkStatus.status = 'warning';
      } else {
        fdkStatus.status = 'critical';
      }
    } catch (error) {
      fdkStatus.status = 'error';
      fdkStatus.error = error.message;
    }

    return fdkStatus;
  },

  /**
   * 상태 리포트 콘솔 출력
   */
  printHealthReport(report) {
    const statusEmoji = {
      healthy: '✅',
      warning: '⚠️',
      critical: '🚨',
      error: '💥',
      unknown: '❓',
    };

    console.group(
      `🔍 앱 상태 검사 리포트 ${statusEmoji[report.overall]} ${report.overall.toUpperCase()}`
    );
    console.log(`🕒 검사 시간: ${report.timestamp}`);

    Object.entries(report.checks).forEach(([category, check]) => {
      console.group(`${statusEmoji[check.status]} ${category.toUpperCase()}: ${check.status}`);
      if (check.details) {
        console.table(check.details);
      }
      if (check.error) {
        console.error('오류:', check.error);
      }
      console.groupEnd();
    });

    console.groupEnd();
  },

  /**
   * 콘솔 명령어 등록
   *
   * 개발자 콘솔에서 쉽게 사용할 수 있는 디버깅 명령어들을 등록합니다.
   */
  registerConsoleCommands() {
    if (!this.isDebugMode) return;

    // 전역 디버깅 명령어들
    window.debug = {
      // 상태 검사
      health: () => this.checkAppHealth(),

      // 모듈 상태
      modules: () => {
        console.table(Array.from(ModuleDependencyManager.loadedModules));
        return ModuleDependencyManager;
      },

      // 에러 로그
      errors: () => {
        console.table(GlobalState.ErrorHandler.errorLog);
        return GlobalState.ErrorHandler.errorLog;
      },

      // 전역 상태
      state: () => {
        console.table(GlobalState.getGlobalTicketData());
        return GlobalState.getGlobalTicketData();
      },

      // 캐시 초기화
      reset: () => {
        GlobalState.resetGlobalTicketCache();
        console.log('🔄 전역 캐시가 초기화되었습니다.');
      },

      // 성능 정보
      perf: () => {
        const navigation = performance.getEntriesByType('navigation')[0];
        console.table({
          '페이지 로드': `${Math.round(navigation.loadEventEnd - navigation.fetchStart)}ms`,
          'DOM 준비': `${Math.round(navigation.domContentLoadedEventEnd - navigation.fetchStart)}ms`,
          '리소스 수': performance.getEntriesByType('resource').length,
        });
      },
    };

    console.log('🛠️ 디버깅 명령어가 등록되었습니다. window.debug 객체를 확인하세요.');
    console.log('사용 예시: debug.health(), debug.modules(), debug.errors()');
  },

  /**
   * 성능 최적화 상태 모니터링
   */
  getPerformanceReport() {
    if (!window.PerformanceOptimizer) {
      return '❌ PerformanceOptimizer를 사용할 수 없습니다.';
    }

    const memoryStats = window.PerformanceOptimizer.getMemoryStats();
    const cacheStats = memoryStats.cacheStats;

    return {
      메모리_사용량: memoryStats.memoryUsage,
      캐시_상태: {
        함수_캐시: `${memoryStats.functionCache}개`,
        결과_캐시: `${memoryStats.resultCache}개`,
        DOM_캐시: `${memoryStats.domCache}개`,
      },
      캐시_성능: {
        히트율: `${((cacheStats.hits / (cacheStats.hits + cacheStats.misses)) * 100).toFixed(1)}%`,
        전체_요청: cacheStats.hits + cacheStats.misses,
        캐시_히트: cacheStats.hits,
        캐시_미스: cacheStats.misses,
        캐시_제거: cacheStats.evictions,
      },
      최적화_권장사항: this.getOptimizationRecommendations(memoryStats),
    };
  },

  /**
   * 최적화 권장사항 생성
   */
  getOptimizationRecommendations(stats) {
    const recommendations = [];

    // 캐시 히트율 분석
    const hitRate = stats.cacheStats.hits / (stats.cacheStats.hits + stats.cacheStats.misses);
    if (hitRate < 0.6) {
      recommendations.push(
        '캐시 히트율이 낮습니다. 캐시 TTL을 늘리거나 자주 사용되는 데이터의 캐시 전략을 검토하세요.'
      );
    }

    // 메모리 사용량 분석
    if (typeof window.performance.memory !== 'undefined') {
      const memoryUsage =
        window.performance.memory.usedJSHeapSize / window.performance.memory.totalJSHeapSize;
      if (memoryUsage > 0.8) {
        recommendations.push(
          '메모리 사용량이 높습니다. 캐시 크기를 줄이거나 메모리 정리를 수행하세요.'
        );
      }
    }

    // DOM 캐시 분석
    if (stats.domCache > 50) {
      recommendations.push('DOM 캐시가 많습니다. 사용하지 않는 DOM 요소 참조를 정리하세요.');
    }

    if (recommendations.length === 0) {
      recommendations.push('성능 상태가 양호합니다. 👍');
    }

    return recommendations;
  },

  /**
   * 모든 캐시 초기화
   */
  clearAllCaches() {
    if (window.PerformanceOptimizer) {
      window.PerformanceOptimizer.clearAllCaches();
      console.log('🧹 모든 캐시가 초기화되었습니다.');
    }

    if (window.API && window.API.clearCache) {
      window.API.clearCache();
    }

    if (window.GlobalState) {
      window.GlobalState.resetGlobalTicketCache();
    }
  },

  /**
   * 성능 벤치마크 실행
   */
  async runPerformanceBenchmark() {
    console.log('🏃‍♂️ 성능 벤치마크 시작...');

    const results = {
      DOM_조작: await this.benchmarkDOMOperations(),
      API_호출: await this.benchmarkAPIOperations(),
      데이터_처리: await this.benchmarkDataProcessing(),
      캐시_성능: await this.benchmarkCachePerformance(),
    };

    console.log('📊 벤치마크 결과:', results);
    return results;
  },

  /**
   * DOM 조작 성능 테스트
   */
  async benchmarkDOMOperations() {
    const iterations = 1000;
    const container = document.createElement('div');
    document.body.appendChild(container);

    // 기본 DOM 조작 테스트
    const start1 = performance.now();
    for (let i = 0; i < iterations; i++) {
      const div = document.createElement('div');
      div.textContent = `Item ${i}`;
      container.appendChild(div);
    }
    const basicTime = performance.now() - start1;

    // 배치 DOM 업데이트 테스트
    container.innerHTML = '';
    const start2 = performance.now();

    if (window.PerformanceOptimizer) {
      const updates = Array.from({ length: iterations }, (_, i) => ({
        type: 'create',
        tag: 'div',
        properties: { textContent: `Item ${i}` },
        parent: container,
      }));
      await window.PerformanceOptimizer.batchDOMUpdates(updates);
    }

    const batchTime = performance.now() - start2;

    // 정리
    document.body.removeChild(container);

    return {
      기본_DOM_조작: `${basicTime.toFixed(2)}ms`,
      배치_DOM_업데이트: `${batchTime.toFixed(2)}ms`,
      성능_향상: `${(((basicTime - batchTime) / basicTime) * 100).toFixed(1)}%`,
    };
  },

  /**
   * API 호출 성능 테스트
   */
  async benchmarkAPIOperations() {
    if (!window.API || !window.API.healthCheck) {
      return '❌ API 모듈을 사용할 수 없습니다.';
    }

    const iterations = 5;
    const times = [];

    for (let i = 0; i < iterations; i++) {
      const start = performance.now();
      try {
        await window.API.healthCheck();
      } catch (error) {
        // 에러 무시
      }
      times.push(performance.now() - start);
    }

    const avgTime = times.reduce((a, b) => a + b, 0) / times.length;
    const minTime = Math.min(...times);
    const maxTime = Math.max(...times);

    return {
      평균_응답시간: `${avgTime.toFixed(2)}ms`,
      최소_응답시간: `${minTime.toFixed(2)}ms`,
      최대_응답시간: `${maxTime.toFixed(2)}ms`,
    };
  },

  /**
   * 데이터 처리 성능 테스트
   */
  async benchmarkDataProcessing() {
    const testData = Array.from({ length: 1000 }, (_, i) => ({
      id: i,
      title: `Test Item ${i}`,
      description: `Description for item ${i}`,
      timestamp: new Date().toISOString(),
    }));

    // 기본 처리
    const start1 = performance.now();
    const processed1 = testData.map((item) => ({
      ...item,
      processed: true,
      searchText: `${item.title} ${item.description}`.toLowerCase(),
    }));
    const basicTime = performance.now() - start1;

    // 배치 처리 (Data 모듈 사용)
    const start2 = performance.now();
    let processed2 = [];

    if (window.Data && window.Data.processBatchData) {
      processed2 = await window.Data.processBatchData(
        testData,
        (item) => ({
          ...item,
          processed: true,
          searchText: `${item.title} ${item.description}`.toLowerCase(),
        }),
        { batchSize: 100, delay: 1 }
      );
    }

    const batchTime = performance.now() - start2;

    return {
      기본_처리: `${basicTime.toFixed(2)}ms`,
      배치_처리: `${batchTime.toFixed(2)}ms`,
      처리_결과: `${processed1.length}개 항목`,
      배치_결과: `${processed2.length}개 항목`,
    };
  },

  /**
   * 캐시 성능 테스트
   */
  async benchmarkCachePerformance() {
    if (!window.PerformanceOptimizer) {
      return '❌ PerformanceOptimizer를 사용할 수 없습니다.';
    }

    // 테스트 함수 (CPU 집약적 작업 시뮬레이션)
    const heavyFunction = (n) => {
      let result = 0;
      for (let i = 0; i < n * 1000; i++) {
        result += Math.sqrt(i);
      }
      return result;
    };

    // 메모이제이션 없이 테스트
    const start1 = performance.now();
    const results1 = [];
    for (let i = 0; i < 10; i++) {
      results1.push(heavyFunction(100));
    }
    const normalTime = performance.now() - start1;

    // 메모이제이션 적용 테스트
    const memoizedFunction = window.PerformanceOptimizer.memoize(heavyFunction);
    const start2 = performance.now();
    const results2 = [];
    for (let i = 0; i < 10; i++) {
      results2.push(memoizedFunction(100)); // 동일한 파라미터로 호출
    }
    const memoizedTime = performance.now() - start2;

    return {
      일반_함수_호출: `${normalTime.toFixed(2)}ms`,
      메모이제이션_함수_호출: `${memoizedTime.toFixed(2)}ms`,
      성능_향상: `${(((normalTime - memoizedTime) / normalTime) * 100).toFixed(1)}%`,
      캐시_상태: memoizedFunction.getCacheStats(),
    };
  },
};

// 개발 모드에서 디버깅 도구 초기화
if (DebugTools.isDebugMode) {
  DebugTools.registerConsoleCommands();

  // 주기적 상태 모니터링 (5분마다)
  setInterval(() => {
    const report = DebugTools.checkAppHealth();
    if (report.overall === 'critical') {
      console.warn('🚨 앱 상태가 심각합니다! 에러 로그 및 상태를 확인하세요.');
    }
  }, 300000);
}

// === 성능 최적화 및 캐싱 시스템 ===
// 함수 메모이제이션, 스마트 캐싱, 메모리 관리 제공
class PerformanceOptimizer {
  constructor() {
    this.functionCache = new Map();
    this.resultCache = new Map();
    this.domCache = new Map();
    this.memoryThreshold = 50 * 1024 * 1024; // 50MB
    this.maxCacheSize = 100;
    this.cacheStats = {
      hits: 0,
      misses: 0,
      evictions: 0,
    };
    this.setupMemoryMonitoring();
  }

  /**
   * 함수 메모이제이션
   * 동일한 입력에 대해 결과를 캐시하여 성능 향상
   */
  memoize(fn, keyGenerator = null) {
    const cache = new Map();
    const memoizedFunction = (...args) => {
      const key = keyGenerator ? keyGenerator(...args) : JSON.stringify(args);

      if (cache.has(key)) {
        this.cacheStats.hits++;
        return cache.get(key);
      }

      this.cacheStats.misses++;
      const result = fn.apply(this, args);

      // 캐시 크기 제한
      if (cache.size >= this.maxCacheSize) {
        const firstKey = cache.keys().next().value;
        cache.delete(firstKey);
        this.cacheStats.evictions++;
      }

      cache.set(key, result);
      return result;
    };

    // 캐시 정리 메서드 추가
    memoizedFunction.clearCache = () => cache.clear();
    memoizedFunction.getCacheSize = () => cache.size;
    memoizedFunction.getCacheStats = () => ({ ...this.cacheStats });

    return memoizedFunction;
  }

  /**
   * 스마트 API 결과 캐싱
   * TTL(Time To Live) 기반 자동 만료
   */
  cacheApiResult(key, result, ttlMs = 300000) {
    // 기본 5분
    const cacheEntry = {
      data: result,
      timestamp: Date.now(),
      ttl: ttlMs,
      accessCount: 0,
    };

    this.resultCache.set(key, cacheEntry);
    this.cleanExpiredCache();
  }

  getCachedApiResult(key) {
    const entry = this.resultCache.get(key);
    if (!entry) return null;

    // TTL 확인
    if (Date.now() - entry.timestamp > entry.ttl) {
      this.resultCache.delete(key);
      return null;
    }

    entry.accessCount++;
    entry.timestamp = Date.now(); // LRU 업데이트
    return entry.data;
  }

  /**
   * DOM 요소 캐싱
   * 자주 접근하는 DOM 요소를 캐시하여 querySelector 호출 최소화
   */
  getDOMElement(selector, forceRefresh = false) {
    if (!forceRefresh && this.domCache.has(selector)) {
      const element = this.domCache.get(selector);
      // 요소가 여전히 DOM에 존재하는지 확인
      if (document.contains(element)) {
        return element;
      }
      this.domCache.delete(selector);
    }

    const element = document.querySelector(selector);
    if (element) {
      this.domCache.set(selector, element);
    }
    return element;
  }

  /**
   * 배치 DOM 업데이트
   * DOM 조작을 배치 처리하여 리플로우/리페인트 최소화
   */
  batchDOMUpdates(updates) {
    return new Promise((resolve) => {
      requestAnimationFrame(() => {
        // DocumentFragment를 사용하여 배치 업데이트
        const fragment = document.createDocumentFragment();
        const elements = [];

        updates.forEach((update) => {
          if (update.type === 'create') {
            const element = document.createElement(update.tag);
            if (update.properties) {
              Object.assign(element, update.properties);
            }
            if (update.attributes) {
              Object.entries(update.attributes).forEach(([key, value]) => {
                element.setAttribute(key, value);
              });
            }
            elements.push({ element, parent: update.parent });
          } else if (update.type === 'modify') {
            const element = update.element;
            if (update.properties) {
              Object.assign(element, update.properties);
            }
            if (update.styles) {
              Object.assign(element.style, update.styles);
            }
          }
        });

        // 실제 DOM에 적용
        elements.forEach(({ element, parent }) => {
          if (parent) {
            parent.appendChild(element);
          }
        });

        resolve();
      });
    });
  }

  /**
   * 메모리 사용량 모니터링
   */
  setupMemoryMonitoring() {
    if ('memory' in performance) {
      setInterval(() => {
        const memInfo = performance.memory;
        if (memInfo.usedJSHeapSize > this.memoryThreshold) {
          console.warn('메모리 사용량이 임계값을 초과했습니다:', {
            used: this.formatBytes(memInfo.usedJSHeapSize),
            total: this.formatBytes(memInfo.totalJSHeapSize),
            threshold: this.formatBytes(this.memoryThreshold),
          });
          this.performMemoryCleanup();
        }
      }, 30000); // 30초마다 확인
    }
  }

  /**
   * 메모리 정리
   */
  performMemoryCleanup() {
    // 만료된 캐시 정리
    this.cleanExpiredCache();

    // DOM 캐시 정리 (존재하지 않는 요소 제거)
    for (const [selector, element] of this.domCache.entries()) {
      if (!document.contains(element)) {
        this.domCache.delete(selector);
      }
    }

    // 함수 캐시 크기 제한
    if (this.functionCache.size > this.maxCacheSize) {
      const keysToDelete = Array.from(this.functionCache.keys()).slice(0, 10);
      keysToDelete.forEach((key) => this.functionCache.delete(key));
    }

    console.log('메모리 정리 완료:', this.getMemoryStats());
  }

  cleanExpiredCache() {
    const now = Date.now();
    for (const [key, entry] of this.resultCache.entries()) {
      if (now - entry.timestamp > entry.ttl) {
        this.resultCache.delete(key);
      }
    }
  }

  /**
   * 지연 로딩 지원
   */
  createLazyLoader(loadFunction, placeholder = null) {
    let loaded = false;
    let loadPromise = null;

    return {
      load: () => {
        if (loaded) return Promise.resolve();
        if (loadPromise) return loadPromise;

        loadPromise = loadFunction().then(() => {
          loaded = true;
          return true;
        });

        return loadPromise;
      },
      isLoaded: () => loaded,
      getPlaceholder: () => placeholder,
    };
  }

  /**
   * 디바운스 및 스로틀링
   */
  debounce(func, wait, immediate = false) {
    let timeout;
    return function executedFunction(...args) {
      const later = () => {
        timeout = null;
        if (!immediate) func.apply(this, args);
      };
      const callNow = immediate && !timeout;
      clearTimeout(timeout);
      timeout = setTimeout(later, wait);
      if (callNow) func.apply(this, args);
    };
  }

  throttle(func, limit) {
    let inThrottle;
    return function executedFunction(...args) {
      if (!inThrottle) {
        func.apply(this, args);
        inThrottle = true;
        setTimeout(() => (inThrottle = false), limit);
      }
    };
  }

  /**
   * 성능 메트릭 수집
   */
  measurePerformance(name, fn) {
    return (...args) => {
      const startTime = performance.now();
      const result = fn.apply(this, args);
      const endTime = performance.now();

      console.log(`[성능] ${name}: ${(endTime - startTime).toFixed(2)}ms`);
      return result;
    };
  }

  /**
   * 유틸리티 메서드들
   */
  formatBytes(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  }

  getMemoryStats() {
    return {
      functionCache: this.functionCache.size,
      resultCache: this.resultCache.size,
      domCache: this.domCache.size,
      cacheStats: { ...this.cacheStats },
      memoryUsage:
        'memory' in performance
          ? {
              used: this.formatBytes(performance.memory.usedJSHeapSize),
              total: this.formatBytes(performance.memory.totalJSHeapSize),
            }
          : 'N/A',
    };
  }

  /**
   * 캐시 상태 초기화
   */
  clearAllCaches() {
    this.functionCache.clear();
    this.resultCache.clear();
    this.domCache.clear();
    this.cacheStats = { hits: 0, misses: 0, evictions: 0 };
    console.log('모든 캐시가 초기화되었습니다.');
  }
}

// 전역 성능 최적화 인스턴스
window.PerformanceOptimizer = new PerformanceOptimizer();

// 디버깅 도구와 의존성 관리자를 전역으로 export
window.DebugTools = DebugTools;
window.ModuleDependencyManager = ModuleDependencyManager;

console.log('🚀 globals.js 전체 로드 완료 - 모든 시스템 준비됨');
