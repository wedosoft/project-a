/**
 * @fileoverview 간소화된 API 모듈 - 핵심 기능만 포함
 * @description 🚀 단순하고 안정적인 API 모듈
 */

// 전역 API 객체 즉시 정의 (의존성 오류 방지)
if (typeof window.API === 'undefined') {
  window.API = {};
}

const API = {
  // 백엔드 URL
  get baseURL() {
    return 'https://4837-58-122-170-2.ngrok-free.app';
  },

  // 초기화 상태
  _initialized: false,

  /**
   * API 모듈 초기화
   */
  init() {
    if (this._initialized) return;
    this._initialized = true;
    console.log('✅ 간소화된 API 모듈 초기화 완료');
  },

  /**
   * 기본 헤더 생성
   */
  getDefaultHeaders() {
    return {
      'Content-Type': 'application/json',
      'X-Tenant-ID': 'wedosoft',
      'X-Platform': 'freshdesk',
      'X-Domain': 'wedosoft.freshdesk.com',
      'X-API-Key': 'Ug9H1cKCZZtZ4haamBy',
      'ngrok-skip-browser-warning': 'true'
    };
  },

  /**
   * 초기 데이터 로드
   */
  async loadInitData(clientOrTicketId, ticketIdOrUndefined) {
    // 매개변수 유연성 제공
    let ticketId;
    
    if (typeof clientOrTicketId === 'string' || typeof clientOrTicketId === 'number') {
      // client 없이 호출된 경우: loadInitData(ticketId)
      ticketId = clientOrTicketId;
    } else {
      // client와 함께 호출된 경우: loadInitData(client, ticketId)
      ticketId = ticketIdOrUndefined;
    }
    try {
      console.log(`🚀 초기 데이터 로딩: ${ticketId}`);
      
      const response = await fetch(`${this.baseURL}/init/${ticketId}`, {
        method: 'GET',
        headers: this.getDefaultHeaders()
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      
      return {
        ok: true,
        status: response.status,
        data: data
      };
    } catch (error) {
      console.error('❌ 초기 데이터 로딩 실패:', error);
      throw error;
    }
  },

  /**
   * 채팅 쿼리 전송
   */
  async sendChatQuery(clientOrQueryData, queryDataOrOptions = {}, optionsOrUndefined = {}) {
    // 매개변수 유연성 제공: client 있거나 없거나 둘 다 지원
    let queryData, options;
    
    if (typeof clientOrQueryData === 'object' && clientOrQueryData.query) {
      // client 없이 호출된 경우: sendChatQuery(queryData, options)
      queryData = clientOrQueryData;
      options = queryDataOrOptions || {};
    } else {
      // client와 함께 호출된 경우: sendChatQuery(client, queryData, options)
      queryData = queryDataOrOptions;
      options = optionsOrUndefined || {};
    }
    try {
      console.log('💬 채팅 쿼리 전송:', queryData);
      
      const requestData = {
        query: queryData.query,
        agent_mode: queryData.agent_mode !== false,
        enhanced_search: !queryData.agent_mode,
        stream_response: queryData.stream_response || false,
        ticket_id: queryData.ticket_id,
        top_k: queryData.top_k || 5,
        tenant_id: 'wedosoft',
        platform: 'freshdesk'
      };

      // 스트리밍 요청인 경우
      if (requestData.stream_response && options.onStream) {
        return await this.sendStreamingQuery(requestData, options.onStream);
      }

      // 일반 요청
      const response = await fetch(`${this.baseURL}/query`, {
        method: 'POST',
        headers: this.getDefaultHeaders(),
        body: JSON.stringify(requestData)
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const result = await response.json();
      
      return {
        ok: true,
        status: response.status,
        data: result
      };
    } catch (error) {
      console.error('❌ 채팅 쿼리 실패:', error);
      throw error;
    }
  },

  /**
   * 스트리밍 쿼리 전송
   */
  async sendStreamingQuery(requestData, onStream) {
    try {
      const response = await fetch(`${this.baseURL}/query?stream=true`, {
        method: 'POST',
        headers: {
          ...this.getDefaultHeaders(),
          'Accept': 'text/event-stream'
        },
        body: JSON.stringify(requestData)
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      // 스트리밍 응답 처리
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            if (!line.trim()) continue; // 빈 줄 건너뛰기
            
            console.log('📨 수신된 라인:', line);
            
            // SSE 형식 처리
            if (line.startsWith('data: ')) {
              const dataStr = line.slice(6).trim();
              
              // 불완전한 JSON 필터링 강화
              if (dataStr === '[DONE]' || dataStr === 'done' || dataStr === 'null' || !dataStr) {
                continue;
              }
              
              // 최소 JSON 형태 확인 (중괄호나 대괄호로 시작하고 끝나는지)
              if ((dataStr.startsWith('{') && dataStr.endsWith('}')) || 
                  (dataStr.startsWith('[') && dataStr.endsWith(']'))) {
                this.processStreamData(dataStr, onStream);
              } else {
                console.warn('⚠️ 불완전한 JSON 데이터 무시:', dataStr.substring(0, 50) + '...');
              }
            } 
            // 일반 텍스트 처리 (SSE 형식이 아닌 경우)
            else if ((line.startsWith('{') && line.endsWith('}')) || 
                     (line.startsWith('[') && line.endsWith(']'))) {
              this.processStreamData(line.trim(), onStream);
            }
            // 기타 메시지 처리
            else {
              console.log('📝 비JSON 메시지:', line);
              if (onStream) {
                onStream({
                  type: 'text',
                  content: line,
                  timestamp: new Date().toISOString()
                });
              }
            }
          }
        }
      } finally {
        reader.releaseLock();
      }

      return {
        ok: true,
        streaming: true,
        status: response.status
      };
    } catch (error) {
      console.error('❌ 스트리밍 실패:', error);
      throw error;
    }
  },

  /**
   * 스트리밍 데이터 처리 (안전한 JSON 파싱)
   */
  processStreamData(dataStr, onStream) {
    try {
      // 빈 문자열이나 특수 값 체크
      if (!dataStr || dataStr === '[DONE]' || dataStr === 'done' || dataStr === 'null') {
        return;
      }

      // 기본 유효성 검사 - 최소한의 JSON 구조 확인
      const trimmedData = dataStr.trim();
      
      // 완전한 JSON 구조가 아닌 경우 무시 (강화된 검증)
      if (!trimmedData || trimmedData.length < 2) {
        return;
      }
      
      // JSON 기본 구조 검증
      const startsWithBrace = trimmedData.startsWith('{');
      const endsWithBrace = trimmedData.endsWith('}');
      const startsWithBracket = trimmedData.startsWith('[');
      const endsWithBracket = trimmedData.endsWith(']');
      
      if (!(startsWithBrace && endsWithBrace) && !(startsWithBracket && endsWithBracket)) {
        console.warn('⚠️ 불완전한 JSON 구조 무시:', trimmedData.substring(0, 30) + '...');
        return;
      }

      // 디버깅용 로그 (축약)
      console.log('🔍 처리 중:', trimmedData.substring(0, 50) + (trimmedData.length > 50 ? '...' : ''));
      
      // JSON 형태가 아닌 텍스트 직접 처리
      if (!trimmedData.startsWith('{') && !trimmedData.startsWith('[')) {
        console.log('📝 비JSON 텍스트 데이터:', trimmedData);
        if (onStream) {
          onStream({
            type: 'text',
            content: trimmedData,
            timestamp: new Date().toISOString()
          });
        }
        return;
      }

      // JSON 파싱 시도 - 강화된 오류 처리
      let eventData;
      try {
        // 추가 검증: 기본적인 JSON 문법 확인
        if (!this.isValidJsonStructure(trimmedData)) {
          console.warn('⚠️ 유효하지 않은 JSON 구조 감지, 무시:', trimmedData.substring(0, 50) + '...');
          return;
        }
        
        eventData = JSON.parse(trimmedData);
      } catch (jsonError) {
        console.warn('❌ JSON 파싱 실패:', jsonError.message, '데이터:', trimmedData.substring(0, 50) + '...');
        // JSON 파싱 실패 시 완전히 무시
        return;
      }

      // 성공적으로 파싱된 JSON 데이터 처리
      if (onStream && eventData) {
        console.log('✅ JSON 파싱 성공:', eventData);
        onStream(eventData);
      }
    } catch (error) {
      console.error('❌ processStreamData 오류:', error);
      if (onStream) {
        onStream({
          type: 'error',
          message: `데이터 처리 오류: ${error.message}`,
          raw_data: dataStr,
          timestamp: new Date().toISOString()
        });
      }
    }
  },

  /**
   * JSON 구조 유효성 검사
   */
  isValidJsonStructure(str) {
    if (!str || str.length < 2) return false;
    
    // 기본 구조 확인
    const hasValidStart = str.startsWith('{') || str.startsWith('[');
    const hasValidEnd = str.endsWith('}') || str.endsWith(']');
    
    if (!hasValidStart || !hasValidEnd) return false;
    
    // 괄호 짝 맞추기 확인
    let braceCount = 0;
    let bracketCount = 0;
    let inString = false;
    let escaped = false;
    
    for (let i = 0; i < str.length; i++) {
      const char = str[i];
      
      if (escaped) {
        escaped = false;
        continue;
      }
      
      if (char === '\\') {
        escaped = true;
        continue;
      }
      
      if (char === '"') {
        inString = !inString;
        continue;
      }
      
      if (!inString) {
        if (char === '{') braceCount++;
        else if (char === '}') braceCount--;
        else if (char === '[') bracketCount++;
        else if (char === ']') bracketCount--;
      }
    }
    
    return braceCount === 0 && bracketCount === 0;
  },

  /**
   * 백엔드 연결 확인
   */
  async checkBackendConnection() {
    try {
      const response = await fetch(`${this.baseURL}/health`, {
        method: 'GET',
        headers: this.getDefaultHeaders()
      });
      return response.ok;
    } catch (error) {
      console.warn('백엔드 연결 확인 실패:', error);
      return false;
    }
  },

  /**
   * 모듈 가용성 확인
   */
  isAvailable() {
    return true;
  }
};

// 전역으로 export (강화된 방식)
Object.assign(window.API, API);

// 즉시 초기화 시도
try {
  API.init();
  console.log('✅ API 모듈 즉시 초기화 완료');
} catch (error) {
  console.warn('⚠️ API 즉시 초기화 실패, DOM 로드 후 재시도:', error.message);
  
  // DOM 로드 완료 후 초기화
  if (document.readyState === 'complete' || document.readyState === 'interactive') {
    setTimeout(() => API.init(), 100);
  } else {
    document.addEventListener('DOMContentLoaded', () => {
      API.init();
    });
  }
}

console.log('🎯 간소화된 API 모듈 로드 완료');

// 모듈 의존성 시스템에 등록 (안전한 방식)
setTimeout(() => {
  if (typeof ModuleDependencyManager !== 'undefined') {
    ModuleDependencyManager.registerModule('api', Object.keys(API).length, ['globals', 'utils']);
    console.log('📦 [API] 모듈 의존성 등록 완료');
  } else {
    console.warn('⚠️ ModuleDependencyManager가 로드되지 않음 - API 모듈 등록 건너뛰기');
  }
}, 500);

// API 가용성 확인 함수 추가
window.API.checkAvailability = function() {
  const isReady = window.API && 
                  typeof window.API.sendChatQuery === 'function' && 
                  typeof window.API.loadInitData === 'function';
  console.log('🔍 API 모듈 가용성 확인:', isReady);
  return isReady;
};

// 디버깅용 로그
console.log('🌍 API 객체가 window.API에 등록됨:', Object.keys(window.API));
console.log('🔧 API 모듈 준비 상태:', window.API.checkAvailability());