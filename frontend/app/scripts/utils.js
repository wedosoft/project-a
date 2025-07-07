/**
 * 유틸리티 함수 모음 - 필수 기능만 포함
 */

const Utils = {
  // 날짜 포맷팅
  formatDate(dateString) {
    const date = new Date(dateString);
    const now = new Date();
    const diff = now - date;
    
    // 1시간 미만
    if (diff < 3600000) {
      const minutes = Math.floor(diff / 60000);
      return `${minutes}분 전`;
    }
    
    // 24시간 미만
    if (diff < 86400000) {
      const hours = Math.floor(diff / 3600000);
      return `${hours}시간 전`;
    }
    
    // 날짜 표시
    return date.toLocaleDateString('ko-KR');
  },

  // 텍스트 잘라내기
  truncateText(text, maxLength = 100) {
    if (!text || text.length <= maxLength) return text;
    return text.substring(0, maxLength) + '...';
  },

  // 안전한 DOM 조작
  safeQuerySelector(selector, parent = document) {
    try {
      return parent.querySelector(selector);
    } catch (e) {
      console.warn('선택자 오류:', selector);
      return null;
    }
  },

  // 디바운스
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

  // HTML 이스케이프
  escapeHtml(text) {
    const map = {
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
  },

  // 스크롤 하단으로
  scrollToBottom(element) {
    if (element) {
      element.scrollTop = element.scrollHeight;
    }
  },

  // 로컬 스토리지 래퍼
  storage: {
    get(key) {
      try {
        const item = localStorage.getItem(key);
        return item ? JSON.parse(item) : null;
      } catch (e) {
        return null;
      }
    },

    set(key, value) {
      try {
        localStorage.setItem(key, JSON.stringify(value));
      } catch (e) {
        console.warn('로컬 스토리지 저장 실패:', e);
      }
    },

    remove(key) {
      try {
        localStorage.removeItem(key);
      } catch (e) {
        console.warn('로컬 스토리지 삭제 실패:', e);
      }
    }
  },

  // 간단한 템플릿 함수
  template(str, data) {
    return str.replace(/\${(\w+)}/g, (match, key) => {
      return data[key] || '';
    });
  }
};

// 전역으로 노출
window.Utils = Utils;