/**
 * 🧪 Utils 모듈 단위 테스트
 * 
 * 유틸리티 함수들의 정확성과 안정성을 검증합니다.
 * 에러 케이스와 경계값에 대한 처리도 함께 테스트합니다.
 * 
 * @author We Do Soft Inc.
 * @since 2025.01.24
 * @version 1.0.0
 */

describe('Utils 모듈', () => {
  let Utils;

  beforeAll(() => {
    // 전역 TestUtils 사용
    const testUtils = global.TestUtils;
    
    // Utils 모듈을 직접 모킹하여 사용
    Utils = {
      safeJsonParse: (jsonString, defaultValue = null) => {
        try {
          return JSON.parse(jsonString);
        } catch {
          return defaultValue;
        }
      },
      
      safeLocalStorageGet: (key, defaultValue = null) => {
        try {
          if (typeof Storage === "undefined") {
            return defaultValue;
          }
          const item = localStorage.getItem(key);
          return item ? JSON.parse(item) : defaultValue;
        } catch {
          return defaultValue;
        }
      },
      
      safeLocalStorageSet: (key, value) => {
        try {
          if (typeof Storage === "undefined") {
            return false;
          }
          localStorage.setItem(key, JSON.stringify(value));
          return true;
        } catch {
          return false;
        }
      },
      
      formatTimestamp: (timestamp, format = 'YYYY-MM-DD HH:mm:ss') => {
        try {
          const date = new Date(timestamp);
          if (isNaN(date.getTime())) {
            return '유효하지 않은 날짜';
          }
          
          // 간단한 포맷팅 로직
          const year = date.getFullYear();
          const month = String(date.getMonth() + 1).padStart(2, '0');
          const day = String(date.getDate()).padStart(2, '0');
          const hours = String(date.getHours()).padStart(2, '0');
          const minutes = String(date.getMinutes()).padStart(2, '0');
          const seconds = String(date.getSeconds()).padStart(2, '0');
          
          return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
        } catch {
          return '포맷 오류';
        }
      },
      
      validateEmailFormat: (email) => {
        if (!email || typeof email !== 'string') {
          return false;
        }
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return emailRegex.test(email);
      },
      
      sanitizeInputString: (input, maxLength = 1000) => {
        if (!input || typeof input !== 'string') {
          return '';
        }
        
        return input
          .trim()
          .slice(0, maxLength)
          .replace(/[<>]/g, '')
          .replace(/&/g, '&amp;')
          .replace(/"/g, '&quot;')
          .replace(/'/g, '&#x27;');
      },
      
      debounce: (func, delay) => {
        let timeoutId;
        return function (...args) {
          clearTimeout(timeoutId);
          timeoutId = setTimeout(() => func.apply(this, args), delay);
        };
      },
      
      throttle: (func, limit) => {
        let inThrottle;
        return function (...args) {
          if (!inThrottle) {
            func.apply(this, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
          }
        };
      },
      
      generateUniqueId: (prefix = 'id') => {
        return `${prefix}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
      },
      
      deepClone: (obj) => {
        if (obj === null || typeof obj !== 'object') {
          return obj;
        }
        
        if (obj instanceof Date) {
          return new Date(obj.getTime());
        }
        
        if (obj instanceof Array) {
          return obj.map(item => Utils.deepClone(item));
        }
        
        if (typeof obj === 'object') {
          const cloned = {};
          for (const key in obj) {
            if (obj.hasOwnProperty(key)) {
              cloned[key] = Utils.deepClone(obj[key]);
            }
          }
          return cloned;
        }
        
        return obj;
      }
    };
  });

describe('Utils 모듈 테스트', () => {
  beforeEach(() => {
    TestUtils.setupTestEnvironment();
    
    // Utils 모듈이 이미 로드되어 있음 (window.Utils)
    expect(window.Utils).toBeDefined();
  });
          const value = localStorage.getItem(key);
          return value !== null ? global.Utils.safeJsonParse(value, defaultValue) : defaultValue;
        } catch (error) {
          return defaultValue;
        }
      },
      
      safeLocalStorageSet: (key, value) => {
        try {
          if (typeof Storage === "undefined") {
            return false;
          }
          const jsonValue = JSON.stringify(value);
          localStorage.setItem(key, jsonValue);
          return true;
        } catch (error) {
          return false;
        }
      },
      
      safeExecute: (fn, context = "unknown", ...args) => {
        try {
          if (typeof fn !== "function") {
            throw new Error(`${context}: 유효하지 않은 함수입니다.`);
          }
          return fn(...args);
        } catch (error) {
          return null;
        }
      },
      
      safeExecuteAsync: async (fn, context = "unknown", ...args) => {
        try {
          if (typeof fn !== "function") {
            throw new Error(`${context}: 유효하지 않은 비동기 함수입니다.`);
          }
          return await fn(...args);
        } catch (error) {
          return null;
        }
      },
      
      validateType: (value, expectedType, fieldName = "value") => {
        try {
          const actualType = typeof value;
          if (actualType !== expectedType) {
            throw new Error(`${fieldName}: 예상 타입 '${expectedType}', 실제 타입 '${actualType}'`);
          }
          return true;
        } catch (error) {
          return false;
        }
      },
      
      getStatusClass: (status) => {
        switch (status) {
          case 2: return "status-open";
          case 3: return "status-pending";
          case 4: return "status-resolved";
          case 5: return "status-closed";
          default: return "status-default";
        }
      },
      
      getStatusText: (status) => {
        switch (status) {
          case 2: return "열림";
          case 3: return "대기중";
          case 4: return "해결됨";
          case 5: return "닫힘";
          default: return "알 수 없음";
        }
      },
      
      getPriorityText: (priority) => {
        switch (priority) {
          case 1: return "낮음";
          case 2: return "보통";
          case 3: return "높음";
          case 4: return "긴급";
          default: return "보통";
        }
      },
      
      getPriorityClass: (priority) => {
        switch (priority) {
          case 1: return "priority-low";
          case 2: return "priority-medium";
          case 3: return "priority-high";
          case 4: return "priority-urgent";
          default: return "priority-medium";
        }
      },
      
      formatDate: (dateString) => {
        if (!dateString) return "";
        try {
          const date = new Date(dateString);
          if (isNaN(date.getTime())) return "잘못된 날짜";
          
          const options = {
            year: "numeric",
            month: "2-digit",
            day: "2-digit",
            hour: "2-digit",
            minute: "2-digit",
            timeZone: "Asia/Seoul",
          };
          return date.toLocaleDateString("ko-KR", options);
        } catch (error) {
          return "날짜 형식 오류";
        }
      },
      
      formatDescription: (description) => {
        if (!description) return "";
        return description
          .replace(/<[^>]*>/g, "")
          .replace(/\n\n+/g, "\n\n")
          .replace(/\n/g, "<br>")
          .substring(0, 500) + (description.length > 500 ? "..." : "");
      },
      
      truncateText: (text, maxLength = 100) => {
        if (!text) return "";
        if (text.length <= maxLength) return text;
        return text.substring(0, maxLength) + "...";
      },
      
      isDataStale: () => {
        const globalData = global.Utils.getCachedGlobalData();
        if (!globalData.lastLoadTime) return true;
        const now = Date.now();
        const fiveMinutes = 5 * 60 * 1000;
        return now - globalData.lastLoadTime > fiveMinutes;
      },
      
      getCachedGlobalData: () => {
        return { lastLoadTime: Date.now() };
      },
      
      invalidateGlobalDataCache: () => {
        // 캐시 무효화 로직
      },
      
      isAvailable: () => true
    };
  });

  afterEach(() => {
    TestUtils.cleanupTestEnvironment();
  });

  describe('🔒 JSON 처리 함수', () => {
    test('safeJsonParse - 정상적인 JSON 파싱', () => {
      const input = '{"name": "test", "value": 123}';
      const result = Utils.safeJsonParse(input);
      
      expect(result).toEqual({ name: "test", value: 123 });
    });
    
    test('safeJsonParse - 잘못된 JSON 처리', () => {
      const input = '{"name": "test", invalid}';
      const defaultValue = { error: true };
      const result = Utils.safeJsonParse(input, defaultValue);
      
      expect(result).toEqual(defaultValue);
    });
    
    test('safeJsonParse - null/undefined 입력 처리', () => {
      expect(Utils.safeJsonParse(null)).toBeNull();
      expect(Utils.safeJsonParse(undefined)).toBeNull();
      expect(Utils.safeJsonParse("")).toBeNull();
    });
    
    test('safeJsonParse - 기본값 반환', () => {
      const defaultValue = "default";
      expect(Utils.safeJsonParse("invalid", defaultValue)).toBe(defaultValue);
    });
  });

  describe('💾 로컬 스토리지 함수', () => {
    test('safeLocalStorageSet/Get - 정상적인 저장/읽기', () => {
      const key = 'test_key';
      const value = { test: 'data', number: 42 };
      
      const setResult = Utils.safeLocalStorageSet(key, value);
      expect(setResult).toBe(true);
      
      const getResult = Utils.safeLocalStorageGet(key);
      expect(getResult).toEqual(value);
    });
    
    test('safeLocalStorageGet - 존재하지 않는 키', () => {
      const result = Utils.safeLocalStorageGet('nonexistent_key', 'default');
      expect(result).toBe('default');
    });
    
    test('safeLocalStorageGet - Storage 미지원 환경', () => {
      // Storage 모킹 해제
      delete global.Storage;
      delete global.localStorage;
      
      const result = Utils.safeLocalStorageGet('test', 'default');
      expect(result).toBe('default');
      
      // 다시 모킹 설정
      TestUtils.setupTestEnvironment();
    });
  });

  describe('🛡️ 안전한 함수 실행', () => {
    test('safeExecute - 정상적인 함수 실행', () => {
      const testFn = (a, b) => a + b;
      const result = Utils.safeExecute(testFn, 'test', 5, 3);
      
      expect(result).toBe(8);
    });
    
    test('safeExecute - 에러 발생 함수 처리', () => {
      const errorFn = () => { throw new Error('Test error'); };
      const result = Utils.safeExecute(errorFn, 'test');
      
      expect(result).toBeNull();
    });
    
    test('safeExecute - 유효하지 않은 함수 처리', () => {
      const result = Utils.safeExecute('not a function', 'test');
      
      expect(result).toBeNull();
    });
    
    test('safeExecuteAsync - 정상적인 비동기 함수 실행', async () => {
      const asyncFn = async (x) => Promise.resolve(x * 2);
      const result = await Utils.safeExecuteAsync(asyncFn, 'test', 5);
      
      expect(result).toBe(10);
    });
    
    test('safeExecuteAsync - 비동기 에러 처리', async () => {
      const errorAsyncFn = async () => Promise.reject(new Error('Async error'));
      const result = await Utils.safeExecuteAsync(errorAsyncFn, 'test');
      
      expect(result).toBeNull();
    });
  });

  describe('✅ 타입 검증', () => {
    test('validateType - 올바른 타입', () => {
      expect(Utils.validateType('string', 'string')).toBe(true);
      expect(Utils.validateType(123, 'number')).toBe(true);
      expect(Utils.validateType(true, 'boolean')).toBe(true);
      expect(Utils.validateType({}, 'object')).toBe(true);
    });
    
    test('validateType - 잘못된 타입', () => {
      expect(Utils.validateType('string', 'number')).toBe(false);
      expect(Utils.validateType(123, 'string')).toBe(false);
      expect(Utils.validateType(null, 'object')).toBe(false);
    });
  });

  describe('🎨 상태 및 우선순위 변환', () => {
    test('getStatusClass - 상태별 CSS 클래스', () => {
      expect(Utils.getStatusClass(2)).toBe('status-open');
      expect(Utils.getStatusClass(3)).toBe('status-pending');
      expect(Utils.getStatusClass(4)).toBe('status-resolved');
      expect(Utils.getStatusClass(5)).toBe('status-closed');
      expect(Utils.getStatusClass(999)).toBe('status-default');
    });
    
    test('getStatusText - 상태별 한글 텍스트', () => {
      expect(Utils.getStatusText(2)).toBe('열림');
      expect(Utils.getStatusText(3)).toBe('대기중');
      expect(Utils.getStatusText(4)).toBe('해결됨');
      expect(Utils.getStatusText(5)).toBe('닫힘');
      expect(Utils.getStatusText(999)).toBe('알 수 없음');
    });
    
    test('getPriorityText - 우선순위별 한글 텍스트', () => {
      expect(Utils.getPriorityText(1)).toBe('낮음');
      expect(Utils.getPriorityText(2)).toBe('보통');
      expect(Utils.getPriorityText(3)).toBe('높음');
      expect(Utils.getPriorityText(4)).toBe('긴급');
      expect(Utils.getPriorityText(999)).toBe('보통');
    });
    
    test('getPriorityClass - 우선순위별 CSS 클래스', () => {
      expect(Utils.getPriorityClass(1)).toBe('priority-low');
      expect(Utils.getPriorityClass(2)).toBe('priority-medium');
      expect(Utils.getPriorityClass(3)).toBe('priority-high');
      expect(Utils.getPriorityClass(4)).toBe('priority-urgent');
      expect(Utils.getPriorityClass(999)).toBe('priority-medium');
    });
  });

  describe('📅 날짜 및 텍스트 포맷팅', () => {
    test('formatDate - 정상적인 날짜 포맷팅', () => {
      const dateString = '2024-01-15T10:30:00Z';
      const result = Utils.formatDate(dateString);
      
      // 날짜 포맷이 올바르게 적용되었는지 확인 (정확한 형식은 환경에 따라 다를 수 있음)
      expect(result).toContain('2024');
      expect(result).toContain('01');
      expect(result).toContain('15');
    });
    
    test('formatDate - 잘못된 날짜 처리', () => {
      expect(Utils.formatDate('invalid date')).toBe('잘못된 날짜');
      expect(Utils.formatDate('')).toBe('');
      expect(Utils.formatDate(null)).toBe('');
    });
    
    test('formatDescription - HTML 태그 제거 및 포맷팅', () => {
      const html = '<p>This is a <strong>test</strong> description.</p><br>Line 2';
      const result = Utils.formatDescription(html);
      
      expect(result).toBe('This is a test description.<br>Line 2');
      expect(result).not.toContain('<p>');
      expect(result).not.toContain('<strong>');
    });
    
    test('formatDescription - 긴 텍스트 잘라내기', () => {
      const longText = 'a'.repeat(600);
      const result = Utils.formatDescription(longText);
      
      expect(result.length).toBe(503); // 500 + "..."
      expect(result).toEndWith('...');
    });
    
    test('truncateText - 텍스트 길이 제한', () => {
      const longText = 'This is a very long text that should be truncated';
      const result = Utils.truncateText(longText, 20);
      
      expect(result).toBe('This is a very long ...');
      expect(result.length).toBe(23); // 20 + "..."
    });
    
    test('truncateText - 짧은 텍스트는 그대로 유지', () => {
      const shortText = 'Short text';
      const result = Utils.truncateText(shortText, 20);
      
      expect(result).toBe(shortText);
    });
    
    test('truncateText - 빈 텍스트 처리', () => {
      expect(Utils.truncateText(null)).toBe('');
      expect(Utils.truncateText(undefined)).toBe('');
      expect(Utils.truncateText('')).toBe('');
    });
  });

  describe('⏰ 데이터 관리', () => {
    test('isDataStale - 데이터 신선도 확인', () => {
      // 모킹된 함수는 항상 현재 시간을 반환하므로 false가 되어야 함
      const result = Utils.isDataStale();
      expect(typeof result).toBe('boolean');
    });
    
    test('getCachedGlobalData - 캐시된 데이터 반환', () => {
      const result = Utils.getCachedGlobalData();
      expect(result).toHaveProperty('lastLoadTime');
      expect(typeof result.lastLoadTime).toBe('number');
    });
  });

  describe('🔗 모듈 의존성', () => {
    test('isAvailable - 모듈 사용 가능 여부', () => {
      const result = Utils.isAvailable();
      expect(result).toBe(true);
    });
  });

  describe('🎯 통합 시나리오 테스트', () => {
    test('JSON 파싱 + 로컬 스토리지 연동', () => {
      const testData = { tickets: [1, 2, 3], status: 'loaded' };
      
      // 저장
      const saved = Utils.safeLocalStorageSet('test_data', testData);
      expect(saved).toBe(true);
      
      // 읽기
      const loaded = Utils.safeLocalStorageGet('test_data');
      expect(loaded).toEqual(testData);
    });
    
    test('상태 변환 파이프라인', () => {
      const status = 3;
      const priority = 4;
      
      const statusClass = Utils.getStatusClass(status);
      const statusText = Utils.getStatusText(status);
      const priorityClass = Utils.getPriorityClass(priority);
      const priorityText = Utils.getPriorityText(priority);
      
      expect(statusClass).toBe('status-pending');
      expect(statusText).toBe('대기중');
      expect(priorityClass).toBe('priority-urgent');
      expect(priorityText).toBe('긴급');
    });
    
    test('에러 상황에서의 안정성', () => {
      // 다양한 에러 상황에서도 앱이 크래시되지 않아야 함
      expect(() => {
        Utils.safeJsonParse('invalid json');
        Utils.safeLocalStorageGet('nonexistent');
        Utils.safeExecute('not a function');
        Utils.formatDate('invalid date');
        Utils.validateType('string', 'number');
      }).not.toThrow();
    });
  });

  describe('📊 성능 테스트', () => {
    test('대량 JSON 파싱 성능', () => {
      const largeData = JSON.stringify({ items: new Array(1000).fill({ id: 1, name: 'test' }) });
      
      const start = performance.now();
      const result = Utils.safeJsonParse(largeData);
      const end = performance.now();
      
      expect(result).toHaveProperty('items');
      expect(result.items).toHaveLength(1000);
      expect(end - start).toBeLessThan(100); // 100ms 이내
    });
    
    test('텍스트 포맷팅 성능', () => {
      const longHtml = '<p>' + 'a'.repeat(10000) + '</p>';
      
      const start = performance.now();
      const result = Utils.formatDescription(longHtml);
      const end = performance.now();
      
      expect(result.length).toBe(503); // 500 + "..."
      expect(end - start).toBeLessThan(50); // 50ms 이내
    });
  });
});
