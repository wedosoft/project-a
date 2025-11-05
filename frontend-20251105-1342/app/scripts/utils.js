/**
 * Utils Module - 공통 유틸리티 함수
 */

window.Utils = {
  // ========== DOM 헬퍼 ==========
  
  /**
   * 안전한 querySelector
   */
  querySelector(selector, parent = document) {
    try {
      return parent.querySelector(selector);
    } catch (error) {
      console.error('querySelector 오류:', selector, error);
      return null;
    }
  },
  
  /**
   * 안전한 querySelectorAll
   */
  querySelectorAll(selector, parent = document) {
    try {
      return Array.from(parent.querySelectorAll(selector));
    } catch (error) {
      console.error('querySelectorAll 오류:', selector, error);
      return [];
    }
  },
  
  /**
   * 요소 생성 헬퍼
   */
  createElement(tag, className = '', innerHTML = '') {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (innerHTML) element.innerHTML = innerHTML;
    return element;
  },
  
  /**
   * 클래스 토글
   */
  toggleClass(element, className) {
    if (element) {
      element.classList.toggle(className);
    }
  },
  
  /**
   * 요소 표시/숨김
   */
  show(element) {
    if (element) element.style.display = 'block';
  },
  
  hide(element) {
    if (element) element.style.display = 'none';
  },
  
  // ========== 문자열 처리 ==========
  
  /**
   * HTML 이스케이프
   */
  escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  },
  
  /**
   * 문자열 자르기 (말줄임표 포함)
   */
  truncate(str, length = 100) {
    if (!str) return '';
    if (str.length <= length) return str;
    return str.substring(0, length) + '...';
  },
  
  /**
   * 줄바꿈을 <br>로 변환
   */
  nl2br(str) {
    if (!str) return '';
    return str.replace(/\n/g, '<br>');
  },
  
  /**
   * URL 검증
   */
  isValidUrl(string) {
    try {
      new URL(string);
      return true;
    } catch (_) {
      return false;
    }
  },
  
  // ========== 날짜/시간 포맷팅 ==========
  
  /**
   * 날짜 포맷팅
   */
  formatDate(dateString) {
    if (!dateString) return '';
    
    try {
      const date = new Date(dateString);
      const now = new Date();
      const diff = now - date;
      
      return this._selectDateFormat(date, now, diff);
    } catch (error) {
      return dateString;
    }
  },
  
  /**
   * 시간 차이에 따른 날짜 포맷 선택
   */
  _selectDateFormat(date, now, diff) {
    if (this._isWithinHour(diff)) {
      return this._formatMinutesAgo(diff);
    }
    
    if (this._isToday(date, now)) {
      return this._formatTodayTime(date);
    }
    
    if (this._isYesterday(date, now)) {
      return '어제';
    }
    
    if (this._isThisYear(date, now)) {
      return this._formatThisYearDate(date);
    }
    
    return this._formatPreviousYearDate(date);
  },
  
  /**
   * 1시간 이내 체크
   */
  _isWithinHour(diff) {
    return diff < 3600000;
  },
  
  /**
   * 오늘 체크
   */
  _isToday(date, now) {
    return date.toDateString() === now.toDateString();
  },
  
  /**
   * 어제 체크
   */
  _isYesterday(date, now) {
    const yesterday = new Date(now);
    yesterday.setDate(yesterday.getDate() - 1);
    return date.toDateString() === yesterday.toDateString();
  },
  
  /**
   * 올해 체크
   */
  _isThisYear(date, now) {
    return date.getFullYear() === now.getFullYear();
  },
  
  /**
   * 분 단위 상대시간 포맷
   */
  _formatMinutesAgo(diff) {
    const minutes = Math.floor(diff / 60000);
    return minutes <= 1 ? '방금 전' : `${minutes}분 전`;
  },
  
  /**
   * 오늘 시간 포맷
   */
  _formatTodayTime(date) {
    return date.toLocaleTimeString('ko-KR', { 
      hour: '2-digit', 
      minute: '2-digit' 
    });
  },
  
  /**
   * 올해 날짜 포맷
   */
  _formatThisYearDate(date) {
    return date.toLocaleDateString('ko-KR', { 
      month: 'short', 
      day: 'numeric' 
    });
  },
  
  /**
   * 작년 이전 날짜 포맷
   */
  _formatPreviousYearDate(date) {
    return date.toLocaleDateString('ko-KR', { 
      year: 'numeric', 
      month: 'short', 
      day: 'numeric' 
    });
  },
  
  /**
   * 카드용 날짜 포맷 (년도/월/일 포함)
   */
  formatCardDate(dateString) {
    
    if (!dateString) {
      return 'N/A';
    }
    
    const date = new Date(dateString);
    
    if (isNaN(date.getTime())) {
      return 'N/A';
    }
    
    const locale = window.I18nManager ? window.I18nManager.getLocale() : 'ko-KR';
    const formatted = date.toLocaleDateString(locale, {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    });
    
    return formatted;
  },
  
  /**
   * 상대 시간 포맷팅
   */
  formatRelativeTime(date) {
    const now = new Date();
    const diff = now - new Date(date);
    
    const seconds = Math.floor(diff / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);
    
    if (days > 0) return `${days}일 전`;
    if (hours > 0) return `${hours}시간 전`;
    if (minutes > 0) return `${minutes}분 전`;
    return '방금 전';
  },
  
  // ========== 숫자 포맷팅 ==========
  
  /**
   * 천단위 콤마
   */
  formatNumber(num) {
    if (num === null || num === undefined) return '0';
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  },
  
  /**
   * 파일 크기 포맷팅
   */
  formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  },
  
  /**
   * 퍼센트 포맷팅
   */
  formatPercent(value, decimals = 0) {
    if (isNaN(value)) return '0%';
    return `${(value * 100).toFixed(decimals)}%`;
  },
  
  // ========== 데이터 검증 ==========
  
  /**
   * 빈 값 체크
   */
  isEmpty(value) {
    return value === null || 
           value === undefined || 
           value === '' || 
           (Array.isArray(value) && value.length === 0) ||
           (typeof value === 'object' && Object.keys(value).length === 0);
  },
  
  /**
   * 이메일 검증
   */
  isValidEmail(email) {
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(email);
  },
  
  /**
   * 전화번호 포맷팅
   */
  formatPhoneNumber(phone) {
    if (!phone) return '';
    const cleaned = phone.replace(/\D/g, '');
    if (cleaned.length === 11) {
      return cleaned.replace(/(\d{3})(\d{4})(\d{4})/, '$1-$2-$3');
    }
    return phone;
  },
  
  // ========== 배열/객체 유틸리티 ==========
  
  /**
   * 배열 중복 제거
   */
  unique(arr, key) {
    if (!Array.isArray(arr)) return [];
    
    if (key) {
      const seen = new Set();
      return arr.filter(item => {
        const k = item[key];
        if (seen.has(k)) return false;
        seen.add(k);
        return true;
      });
    }
    
    return [...new Set(arr)];
  },
  
  /**
   * 배열 그룹화
   */
  groupBy(arr, key) {
    if (!Array.isArray(arr)) return {};
    
    return arr.reduce((groups, item) => {
      const group = item[key];
      if (!groups[group]) groups[group] = [];
      groups[group].push(item);
      return groups;
    }, {});
  },
  
  /**
   * 객체 깊은 복사
   */
  deepClone(obj) {
    if (this._isPrimitive(obj)) return obj;
    if (this._isDate(obj)) return this._cloneDate(obj);
    if (this._isArray(obj)) return this._cloneArray(obj);
    if (this._isObject(obj)) return this._cloneObject(obj);
  },
  
  /**
   * 원시 타입 체크
   */
  _isPrimitive(obj) {
    return obj === null || typeof obj !== 'object';
  },
  
  /**
   * Date 객체 체크
   */
  _isDate(obj) {
    return obj instanceof Date;
  },
  
  /**
   * 배열 체크
   */
  _isArray(obj) {
    return obj instanceof Array;
  },
  
  /**
   * 일반 객체 체크
   */
  _isObject(obj) {
    return obj instanceof Object;
  },
  
  /**
   * Date 객체 복사
   */
  _cloneDate(date) {
    return new Date(date.getTime());
  },
  
  /**
   * 배열 복사
   */
  _cloneArray(arr) {
    return arr.map(item => this.deepClone(item));
  },
  
  /**
   * 객체 복사
   */
  _cloneObject(obj) {
    const clonedObj = {};
    for (const key in obj) {
      if (Object.prototype.hasOwnProperty.call(obj, key)) {
        clonedObj[key] = this.deepClone(obj[key]);
      }
    }
    return clonedObj;
  },
  
  /**
   * 객체 병합 (얕은 병합)
   */
  merge(...objects) {
    return Object.assign({}, ...objects);
  },
  
  // ========== 비동기 유틸리티 ==========
  
  /**
   * 지연 실행
   */
  delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  },
  
  /**
   * 디바운스
   */
  debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
      const later = () => {
        clearTimeout(timeout);
        func(...args);
      };
      clearTimeout(timeout);
      timeout = setTimeout(later, wait);
    };
  },
  
  /**
   * 쓰로틀
   */
  throttle(func, limit) {
    let inThrottle;
    return function(...args) {
      if (!inThrottle) {
        func.apply(this, args);
        inThrottle = true;
        setTimeout(() => inThrottle = false, limit);
      }
    };
  },
  
  /**
   * 재시도 로직
   */
  async retry(fn, retries = 3, delay = 1000) {
    for (let i = 0; i < retries; i++) {
      try {
        return await fn();
      } catch (error) {
        if (i === retries - 1) throw error;
        await this.delay(delay);
      }
    }
  },
  
  // ========== 브라우저 유틸리티 ==========
  
  /**
   * 클립보드 복사
   */
  async copyToClipboard(text) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch (error) {
      // 폴백: textarea 사용
      const textarea = document.createElement('textarea');
      textarea.value = text;
      textarea.style.position = 'fixed';
      textarea.style.opacity = '0';
      document.body.appendChild(textarea);
      textarea.select();
      
      try {
        document.execCommand('copy');
        return true;
      } catch (e) {
        console.error('복사 실패:', e);
        return false;
      } finally {
        document.body.removeChild(textarea);
      }
    }
  },
  
  /**
   * 로컬 스토리지 헬퍼
   */
  storage: {
    get(key) {
      try {
        const item = localStorage.getItem(key);
        return item ? JSON.parse(item) : null;
      } catch (error) {
        return null;
      }
    },
    
    set(key, value) {
      try {
        localStorage.setItem(key, JSON.stringify(value));
        return true;
      } catch (error) {
        return false;
      }
    },
    
    remove(key) {
      try {
        localStorage.removeItem(key);
        return true;
      } catch (error) {
        return false;
      }
    }
  },
  
  /**
   * URL 파라미터 파싱
   */
  getUrlParams() {
    const params = {};
    new URLSearchParams(window.location.search).forEach((value, key) => {
      params[key] = value;
    });
    return params;
  },
  
  /**
   * 브라우저 감지
   */
  getBrowser() {
    const userAgent = navigator.userAgent;
    if (userAgent.indexOf('Chrome') > -1) return 'Chrome';
    if (userAgent.indexOf('Safari') > -1) return 'Safari';
    if (userAgent.indexOf('Firefox') > -1) return 'Firefox';
    if (userAgent.indexOf('Edge') > -1) return 'Edge';
    return 'Unknown';
  },
  
  
  /**
   * 메모이제이션
   */
  memoize(fn) {
    const cache = new Map();
    return function(...args) {
      const key = JSON.stringify(args);
      if (cache.has(key)) {
        return cache.get(key);
      }
      const result = fn.apply(this, args);
      cache.set(key, result);
      return result;
    };
  },
  
  // ========== 타이밍 & 성능 ==========
  
  /**
   * 단순화된 requestAnimationFrame 래퍼
   */
  smoothRender(callback) {
    if (typeof callback === 'function') {
      requestAnimationFrame(callback);
    }
  },
  
  /**
   * 단순한 타이머 관리
   */
  timerManager: {
    timers: new Map(),
    
    setTimeout(name, callback, delay) {
      if (this.timers.has(name)) {
        clearTimeout(this.timers.get(name));
      }
      const timerId = setTimeout(() => {
        this.timers.delete(name);
        callback();
      }, delay);
      this.timers.set(name, timerId);
      return timerId;
    },
    
    clearTimeout(name) {
      if (this.timers.has(name)) {
        clearTimeout(this.timers.get(name));
        this.timers.delete(name);
      }
    }
  },
  
  // ========== 에러 핸들링 ==========
  
  /**
   * 전역 에러 핸들러
   */
  handleError(error, context = '') {
    console.error(`[Error${context ? ' - ' + context : ''}]:`, error);
    
    // 사용자 친화적 메시지 생성
    let userMessage = '오류가 발생했습니다.';
    
    if (error.message?.includes('timeout')) {
      userMessage = '요청 시간이 초과되었습니다. 다시 시도해주세요.';
    } else if (error.message?.includes('network')) {
      userMessage = '네트워크 연결을 확인해주세요.';
    } else if (error.message?.includes('404')) {
      userMessage = '요청한 리소스를 찾을 수 없습니다.';
    } else if (error.message?.includes('500')) {
      userMessage = '서버 오류가 발생했습니다. 잠시 후 다시 시도해주세요.';
    }
    
    return userMessage;
  },
  
  /**
   * 비동기 함수 래퍼 (에러 핸들링 포함)
   */
  asyncWrapper(fn, context = '') {
    return async (...args) => {
      try {
        return await fn(...args);
      } catch (error) {
        const message = this.handleError(error, context);
        if (window.App?.ui?.showError) {
          window.App.ui.showError(message);
        }
        throw error;
      }
    };
  }
};

/**
 * 알림 배너 시스템
 */
window.NotificationBanner = {
  currentTimer: null,

  /**
   * 배너 표시
   */
  show(message, type = 'info', duration = 4000) {
    const banner = document.getElementById('notification-banner');
    if (!banner) return;

    // 기존 타이머 클리어
    if (this.currentTimer) {
      clearTimeout(this.currentTimer);
      this.currentTimer = null;
    }

    // 아이콘 설정
    const icons = {
      success: '✅',
      warning: '⚠️',
      error: '❌',
      info: 'ℹ️'
    };

    // 배너 내용 업데이트
    const icon = banner.querySelector('.banner-icon');
    const messageEl = banner.querySelector('.banner-message');
    
    if (icon) icon.textContent = icons[type] || icons.info;
    if (messageEl) messageEl.textContent = message;

    // 타입별 클래스 설정
    banner.className = `notification-banner ${type}`;
    
    // 배너 표시
    setTimeout(() => {
      banner.classList.remove('hidden');
    }, 10);

    // 자동 숨김
    if (duration > 0) {
      this.currentTimer = setTimeout(() => {
        this.hide();
      }, duration);
    }
  },

  /**
   * 배너 숨김
   */
  hide() {
    const banner = document.getElementById('notification-banner');
    if (!banner) return;

    banner.classList.add('hidden');
    
    if (this.currentTimer) {
      clearTimeout(this.currentTimer);
      this.currentTimer = null;
    }
  },

  /**
   * 성공 메시지
   */
  success(message, duration = 3000) {
    this.show(message, 'success', duration);
  },

  /**
   * 경고 메시지
   */
  warning(message, duration = 4000) {
    this.show(message, 'warning', duration);
  },

  /**
   * 에러 메시지
   */
  error(message, duration = 5000) {
    this.show(message, 'error', duration);
  },

  /**
   * 정보 메시지
   */
  info(message, duration = 3000) {
    this.show(message, 'info', duration);
  }
};

/**
 * 전역 함수로 배너 숨김 (HTML onclick용)
 */
// eslint-disable-next-line no-unused-vars
function hideBanner() {
  window.NotificationBanner.hide();
}

/**
 * ESLint 호환 확인 대화상자
 */
window.Utils.confirmDialog = function(message) {
  const confirmFn = window.confirm || (() => true);
  return confirmFn.call(window, message);
};

/**
 * ESLint 호환 알림 대화상자  
 */
window.Utils.alertDialog = function(message) {
  const alertFn = window.alert || function() { return undefined; };
  alertFn.call(window, message);
};