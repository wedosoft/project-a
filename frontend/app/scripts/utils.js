/**
 * @fileoverview Utility functions library for Freshdesk Custom App
 * @description 🛠️ 유틸리티 함수 모음 - 범용 헬퍼 함수 라이브러리
 *
 * This module provides general-purpose utility functions used throughout the app.
 * Designed with reusability and stability in mind, all functions guarantee error safety.
 *
 * 이 모듈은 앱 전반에서 사용되는 범용적인 유틸리티 함수들을 제공합니다.
 * 재사용성과 안정성을 고려하여 설계되었으며, 모든 함수는 에러 안전성을 보장합니다.
 *
 * Main feature categories:
 * 주요 기능 카테고리:
 * - JSON data processing (safe parsing, validation) / JSON 데이터 처리 (안전한 파싱, 검증)
 * - Local storage management (safe read/write) / 로컬 스토리지 관리 (안전한 읽기/쓰기)
 * - Text processing (cleaning, formatting, validation) / 텍스트 처리 (클리닝, 포맷팅, 검증)
 * - Data validation (cache state, format validation) / 데이터 유효성 검사 (캐시 상태, 형식 검증)
 * - Performance optimization (cached access, memoization) / 성능 최적화 (캐시된 접근, 메모이제이션)
 *
 * @author We Do Soft Inc.
 * @since 2025.06.16
 * @version 2.0.0 (모듈화 및 문서화 강화)
 * @namespace Utils
 */

// Utils 모듈 정의 - 모든 유틸리티 함수를 하나의 객체로 관리
window.Utils = {
  /**
   * 🔒 안전한 JSON 파싱 함수
   *
   * 잘못된 JSON 문자열로 인한 앱 크래시를 방지하는 안전한 JSON 파싱 함수입니다.
   * API 응답이나 로컬 스토리지 데이터를 파싱할 때 사용하여 안정성을 보장합니다.
   *
   * @param {string} jsonString - 파싱할 JSON 문자열
   * @param {any} defaultValue - 파싱 실패 시 반환할 기본값 (기본: null)
   * @returns {any} 파싱된 객체 또는 기본값
   *
   * @example
   * // 성공 케이스
   * const data = Utils.safeJsonParse('{"name": "test"}'); // {name: "test"}
   *
   * // 실패 케이스 (안전하게 기본값 반환)
   * const data = Utils.safeJsonParse('invalid json', {}); // {}
   */
  safeJsonParse(jsonString, defaultValue = null) {
    try {
      if (!jsonString || typeof jsonString !== 'string') {
        console.warn('[UTILS] 유효하지 않은 JSON 문자열:', jsonString);
        return defaultValue;
      }

      return JSON.parse(jsonString);
    } catch (error) {
      console.error('[UTILS] JSON 파싱 오류:', error, '원본:', jsonString);
      GlobalState.ErrorHandler.handleError(error, {
        context: 'utils_json_parse',
        userMessage: 'JSON 데이터 처리 중 오류가 발생했습니다.',
      });
      return defaultValue;
    }
  },

  /**
   * 💾 안전한 로컬 스토리지 읽기 함수
   *
   * 브라우저 호환성 문제나 스토리지 제한으로 인한 오류를 방지하는 안전한 로컬 스토리지 읽기 함수입니다.
   * 프라이빗 브라우징 모드나 스토리지 용량 부족 등의 상황에서도 안정적으로 동작합니다.
   *
   * @param {string} key - 읽어올 키 이름
   * @param {any} defaultValue - 읽기 실패 시 반환할 기본값 (기본: null)
   * @returns {any} 저장된 값 또는 기본값
   *
   * @example
   * // 캐시된 데이터 읽기
   * const cachedData = Utils.safeLocalStorageGet('ticket_cache', {});
   */
  safeLocalStorageGet(key, defaultValue = null) {
    try {
      if (typeof Storage === 'undefined') {
        console.warn('[UTILS] 로컬 스토리지가 지원되지 않음');
        return defaultValue;
      }

      const value = localStorage.getItem(key);
      return value !== null ? this.safeJsonParse(value, defaultValue) : defaultValue;
    } catch (error) {
      console.error('[UTILS] 로컬 스토리지 읽기 오류:', error);
      return defaultValue;
    }
  },

  safeLocalStorageSet(key, value) {
    try {
      if (typeof Storage === 'undefined') {
        console.warn('[UTILS] 로컬 스토리지가 지원되지 않음');
        return false;
      }

      const jsonValue = JSON.stringify(value);
      localStorage.setItem(key, jsonValue);
      return true;
    } catch (error) {
      console.error('[UTILS] 로컬 스토리지 저장 오류:', error);
      GlobalState.ErrorHandler.handleError(error, {
        context: 'utils_localstorage_set',
        userMessage: '데이터 저장 중 오류가 발생했습니다.',
      });
      return false;
    }
  },

  // 안전한 함수 실행
  safeExecute(fn, context = 'unknown', ...args) {
    try {
      if (typeof fn !== 'function') {
        throw new Error(`${context}: 유효하지 않은 함수입니다.`);
      }

      return fn(...args);
    } catch (error) {
      console.error(`[UTILS] 함수 실행 오류 (${context}):`, error);
      GlobalState.ErrorHandler.handleError(error, {
        context: `utils_safe_execute_${context}`,
        userMessage: '함수 실행 중 오류가 발생했습니다.',
      });
      return null;
    }
  },

  // 비동기 함수 안전 실행
  async safeExecuteAsync(fn, context = 'unknown', ...args) {
    try {
      if (typeof fn !== 'function') {
        throw new Error(`${context}: 유효하지 않은 비동기 함수입니다.`);
      }

      return await fn(...args);
    } catch (error) {
      console.error(`[UTILS] 비동기 함수 실행 오류 (${context}):`, error);
      GlobalState.ErrorHandler.handleError(error, {
        context: `utils_safe_execute_async_${context}`,
        userMessage: '비동기 작업 중 오류가 발생했습니다.',
      });
      return null;
    }
  },

  // 타입 검증
  validateType(value, expectedType, fieldName = 'value') {
    try {
      const actualType = typeof value;

      if (actualType !== expectedType) {
        throw new Error(`${fieldName}: 예상 타입 '${expectedType}', 실제 타입 '${actualType}'`);
      }

      return true;
    } catch (error) {
      console.error('[UTILS] 타입 검증 오류:', error);
      return false;
    }
  },

  // 티켓 상태에 따른 CSS 클래스 반환 함수
  getStatusClass(status) {
    switch (status) {
      case 2:
        return 'status-open'; // 열림
      case 3:
        return 'status-pending'; // 대기중
      case 4:
        return 'status-resolved'; // 해결됨
      case 5:
        return 'status-closed'; // 닫힘
      default:
        return 'status-default'; // 기본값
    }
  },

  // 텍스트 길이 제한 함수
  truncateText(text, maxLength = 100) {
    if (!text) return '';
    if (text.length <= maxLength) return text;
    return text.substring(0, maxLength) + '...';
  },

  // 상태 번호를 한글 텍스트로 변환하는 함수
  getStatusText(status) {
    switch (status) {
      case 2:
        return '열림';
      case 3:
        return '대기중';
      case 4:
        return '해결됨';
      case 5:
        return '닫힘';
      default:
        return '알 수 없음';
    }
  },

  // 우선순위 번호를 한글 텍스트로 변환하는 함수
  getPriorityText(priority) {
    switch (priority) {
      case 1:
        return '낮음';
      case 2:
        return '보통';
      case 3:
        return '높음';
      case 4:
        return '긴급';
      default:
        return '보통';
    }
  },

  // 우선순위에 따른 CSS 클래스 반환 함수
  getPriorityClass(priority) {
    switch (priority) {
      case 1:
        return 'priority-low';
      case 2:
        return 'priority-medium';
      case 3:
        return 'priority-high';
      case 4:
        return 'priority-urgent';
      default:
        return 'priority-medium';
    }
  },

  // 날짜 포맷팅 함수
  formatDate(dateString) {
    if (!dateString) return '';

    try {
      const date = new Date(dateString);
      if (isNaN(date.getTime())) return '잘못된 날짜';

      // 한국 시간대로 변환하여 표시
      const options = {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        timeZone: 'Asia/Seoul',
      };

      return date.toLocaleDateString('ko-KR', options);
    } catch (error) {
      console.warn('날짜 포맷팅 오류:', error);
      return '날짜 형식 오류';
    }
  },

  // 설명 텍스트 포맷팅 함수
  formatDescription(description) {
    if (!description) return '';

    // HTML 태그 제거 및 기본 포맷팅
    return (
      description
        .replace(/<[^>]*>/g, '') // HTML 태그 제거
        .replace(/\n\n+/g, '\n\n') // 연속된 줄바꿈 정리
        .replace(/\n/g, '<br>') // 줄바꿈을 <br>로 변환
        .substring(0, 500) + (description.length > 500 ? '...' : '')
    ); // 길이 제한
  },

  // 데이터 유효성 검사 함수 (캐시가 오래되었는지 확인)
  isDataStale() {
    const globalData = this.getCachedGlobalData();
    if (!globalData.lastLoadTime) return true;
    const now = Date.now();
    const fiveMinutes = 5 * 60 * 1000; // 5분
    return now - globalData.lastLoadTime > fiveMinutes;
  },

  // 로딩 완료까지 대기하는 함수
  async waitForLoadingComplete() {
    const maxWait = 10000; // 최대 10초 대기
    const checkInterval = 100; // 100ms마다 확인
    let waited = 0;

    while (GlobalState.isLoading() && waited < maxWait) {
      await new Promise((resolve) => setTimeout(resolve, checkInterval));
      waited += checkInterval;
    }

    if (waited >= maxWait) {
      console.warn('⚠️ 로딩 완료 대기 시간 초과');
    }
  },

  // 간단한 로딩 인디케이터 표시
  showQuickLoadingIndicator() {
    console.log('⏳ 로딩 인디케이터 표시');

    // 기존 로딩 인디케이터가 있으면 제거
    this.hideQuickLoadingIndicator();

    // 로딩 오버레이 생성
    const loadingOverlay = document.createElement('div');
    loadingOverlay.id = 'quick-loading-overlay';
    loadingOverlay.innerHTML = `
      <div class="loading-backdrop">
        <div class="loading-spinner">
          <div class="spinner"></div>
          <div class="loading-text">데이터를 불러오는 중...</div>
        </div>
      </div>
    `;

    document.body.appendChild(loadingOverlay);
  },

  // 로딩 인디케이터 숨김
  hideQuickLoadingIndicator() {
    console.log('✅ 로딩 인디케이터 숨김');
    const loadingOverlay = document.getElementById('quick-loading-overlay');
    if (loadingOverlay) {
      loadingOverlay.remove();
    }
  },

  /**
   * GlobalState 접근 최적화를 위한 캐시된 데이터 getter
   * 동일한 함수 호출 내에서 중복 접근을 방지합니다.
   */
  getCachedGlobalData() {
    if (!this._cachedGlobalData || this._cacheTimestamp !== Date.now()) {
      this._cachedGlobalData = GlobalState.getGlobalTicketData();
      this._cacheTimestamp = Date.now();
    }
    return this._cachedGlobalData;
  },

  /**
   * 캐시된 데이터 무효화
   * 데이터가 업데이트된 후 호출하여 다음 접근 시 새로운 데이터를 가져오도록 합니다.
   */
  invalidateGlobalDataCache() {
    this._cachedGlobalData = null;
    this._cacheTimestamp = null;
  },

  /**
   * 🔒 안전한 FDK 접근 함수
   *
   * Cross-origin 제한을 고려하여 FDK API에 안전하게 접근하는 함수입니다.
   * 개발 환경과 프로덕션 환경을 구분하여 처리합니다.
   *
   * @param {string} property - 접근하려는 FDK 속성 경로 (예: 'app.instance.context')
   * @param {any} defaultValue - 접근 실패 시 반환할 기본값
   * @returns {Promise<any>} FDK 속성값 또는 기본값
   *
   * @example
   * // FDK context 안전하게 가져오기
   * const context = await Utils.safeFDKAccess('app.instance.context', {});
   *
   * // FDK iparams 안전하게 가져오기
   * const iparams = await Utils.safeFDKAccess('app.iparams.get', {});
   */
  async safeFDKAccess(property, defaultValue = null) {
    try {
      const isDevelopment = window.location.hostname === 'localhost';
      
      if (isDevelopment) {
        console.warn('[UTILS] 개발 환경에서는 FDK 접근이 제한됩니다:', property);
        return defaultValue;
      }

      // 상위 프레임 존재 여부 확인
      if (window.parent === window) {
        console.warn('[UTILS] FDK 환경이 아닙니다 (상위 프레임 없음)');
        return defaultValue;
      }

      // 안전한 속성 접근
      const propertyPath = property.split('.');
      let current = window.parent;

      for (const prop of propertyPath) {
        if (!current || typeof current[prop] === 'undefined') {
          console.warn(`[UTILS] FDK 속성 없음: ${property}`);
          return defaultValue;
        }
        current = current[prop];
      }

      // 함수인 경우 호출, 아닌 경우 값 반환
      if (typeof current === 'function') {
        return await current();
      } else {
        return current;
      }
    } catch (error) {
      console.warn(`[UTILS] FDK 접근 실패: ${property}`, error.message);
      return defaultValue;
    }
  },

  /**
   * 🔍 FDK 환경 감지 함수
   *
   * 현재 실행 환경이 FDK 환경인지 안전하게 확인합니다.
   *
   * @returns {Object} 환경 정보 객체
   *
   * @example
   * const env = Utils.detectFDKEnvironment();
   * if (env.isFDK) {
   *   // FDK 환경 전용 로직
   * }
   */
  detectFDKEnvironment() {
    const isDevelopment = window.location.hostname === 'localhost';
    const hasParentFrame = window.parent !== window;
    let hasFDKAPI = false;
    let accessError = null;

    if (hasParentFrame && !isDevelopment) {
      try {
        hasFDKAPI = typeof window.parent.app !== 'undefined';
      } catch (error) {
        accessError = error.message;
      }
    }

    return {
      isDevelopment,
      hasParentFrame,
      hasFDKAPI,
      isFDK: hasParentFrame && (hasFDKAPI || isDevelopment),
      accessError,
      recommendation: isDevelopment 
        ? 'Freshdesk에서 ?dev=true로 접근하세요'
        : hasFDKAPI 
          ? 'FDK 환경 정상'
          : 'FDK 환경이 아닙니다'
    };
  },

  // 의존성 확인 함수 - 다른 모듈에서 Utils 모듈 사용 가능 여부 체크
  isAvailable: function () {
    return typeof GlobalState !== 'undefined';
  },
};

// 모듈 등록 (로그 없음)

// 모듈 의존성 시스템에 등록
if (typeof ModuleDependencyManager !== 'undefined') {
  ModuleDependencyManager.registerModule('utils', Object.keys(Utils).length);
}
