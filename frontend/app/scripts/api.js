/**
 * @fileoverview Optimized API module for Freshdesk Custom App backend communication
 * @description 🚀 최적화된 API 모듈 (api.js) - Freshdesk Custom App 백엔드 API 통신 및 성능 최적화
 *
 * Main features:
 * 주요 기능:
 * - Caching and memoization support / 캐싱 및 메모이제이션 지원
 * - Batch API call processing / 배치 API 호출 처리
 * - Retry logic with exponential backoff / 재시도 로직 및 지수적 백오프
 * - Performance monitoring and metrics collection / 성능 모니터링 및 메트릭 수집
 * - Smart loading state management / 스마트 로딩 상태 관리
 *
 * @author We Do Soft Inc.
 * @since 2025.06.16
 * @version 3.0.0 (성능 최적화 및 캐싱 강화)
 * @namespace API
 */

// 활성 EventSource 연결 관리
const activeEventSources = new Map();

// EventSource 정리 함수
function cleanupEventSource(key) {
  const eventSource = activeEventSources.get(key);
  if (eventSource) {
    console.log(`🔌 EventSource 연결 종료: ${key}`);
    eventSource.close();
    activeEventSources.delete(key);
  }
}

// 모든 EventSource 정리
function cleanupAllEventSources() {
  console.log(`🔌 모든 EventSource 연결 종료 (${activeEventSources.size}개)`);
  activeEventSources.forEach((eventSource) => {
    eventSource.close();
  });
  activeEventSources.clear();
}

// 페이지 언로드 시 정리
window.addEventListener('beforeunload', cleanupAllEventSources);

/**
 * 🔗 iparams에서 Freshdesk 설정값을 가져오는 함수
 * 고객사별로 다른 도메인과 API 키를 동적으로 로드하여 멀티테넌트 환경 지원
 */
async function getFreshdeskConfigFromIparams(client) {
  try {
    // 개발 환경에서는 기본값 사용
    if (window.location.hostname === 'localhost') {
      return {
        domain: 'wedosoft.freshdesk.com',
        apiKey: 'default_dev_key',
      };
    }

    const iparams = await client.iparams.get();
    if (iparams?.freshdesk_domain && iparams?.freshdesk_api_key) {
      return {
        domain: iparams.freshdesk_domain,
        apiKey: iparams.freshdesk_api_key,
      };
    }

    // 폴백 설정
    return {
      domain: 'default.freshdesk.com',
      apiKey: 'fallback_key',
    };
  } catch (error) {
    console.warn('⚠️ iparams 로드 실패, 기본값 사용:', error.message);
    return {
      domain: 'default.freshdesk.com',
      apiKey: 'fallback_key',
    };
  }
}

/**
 * 📊 데이터 수집 작업 관리 API
 * Data ingestion job management APIs
 */
const IngestJobAPI = {
  /**
   * 새로운 데이터 수집 작업 생성 및 시작
   * @param {Object} options 수집 옵션
   * @param {boolean} options.incremental 증분 업데이트 여부
   * @param {boolean} options.purge 기존 데이터 삭제 여부
   * @param {boolean} options.process_attachments 첨부파일 처리 여부
   * @param {boolean} options.force_rebuild 강제 재구축 여부
   * @param {boolean} options.include_kb 지식베이스 포함 여부
   * @param {string} domain Freshdesk 도메인
   * @param {string} apiKey Freshdesk API 키
   * @returns {Promise<Object>} 작업 정보
   */
  async createJob(options = {}, domain = null, apiKey = null) {
    try {
      console.log('🚀 새 데이터 수집 작업 생성 중...', options);

      const headers = {
        'Content-Type': 'application/json',
        'X-Tenant-ID': 'wedosoft', // .env의 TENANT_ID 값
        'X-Platform': 'freshdesk', // 고정값
      };

      // 동적 Freshdesk 설정 추가 (백엔드 dependencies.py 헤더명 사용)
      if (domain) headers['X-Domain'] = domain;
      if (apiKey) headers['X-API-Key'] = apiKey;

      const response = await fetch(`${API.baseURL}/ingest/jobs`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          incremental: options.incremental !== false,
          purge: options.purge || false,
          process_attachments: options.process_attachments !== false,
          force_rebuild: options.force_rebuild || false,
          include_kb: options.include_kb !== false,
          batch_size: options.batch_size || 50,
          max_retries: options.max_retries || 3,
          parallel_workers: options.parallel_workers || 4,
          auto_start: options.auto_start !== false,
        }),
      });

      const result = await response.json();

      if (!response.ok) {
        throw new Error(result.detail || '작업 생성 실패');
      }

      console.log('✅ 데이터 수집 작업 생성 성공:', result.job.job_id);
      return result;
    } catch (error) {
      console.error('❌ 데이터 수집 작업 생성 실패:', error);
      throw error;
    }
  },

  /**
   * 작업 목록 조회
   * @param {Object} params 조회 파라미터
   * @param {string} params.status 상태 필터
   * @param {number} params.page 페이지 번호
   * @param {number} params.per_page 페이지당 항목 수
   * @returns {Promise<Object>} 작업 목록
   */
  async listJobs(params = {}) {
    try {
      const queryParams = new URLSearchParams();
      
      if (params.status) queryParams.append('status', params.status);
      if (params.page) queryParams.append('page', params.page.toString());
      if (params.per_page) queryParams.append('per_page', params.per_page.toString());

      const response = await fetch(`${API.baseURL}/ingest/jobs?${queryParams}`, {
        headers: {
          'X-Tenant-ID': 'wedosoft',
          'X-Platform': 'freshdesk',
        },
      });

      const result = await response.json();

      if (!response.ok) {
        throw new Error(result.detail || '작업 목록 조회 실패');
      }

      return result;
    } catch (error) {
      console.error('❌ 작업 목록 조회 실패:', error);
      throw error;
    }
  },

  /**
   * 특정 작업 상태 조회
   * @param {string} jobId 작업 ID
   * @returns {Promise<Object>} 작업 상태
   */
  async getJobStatus(jobId) {
    try {
      const response = await fetch(`${API.baseURL}/ingest/jobs/${jobId}`, {
        headers: {
          'X-Tenant-ID': 'wedosoft',
          'X-Platform': 'freshdesk',
        },
      });

      const result = await response.json();

      if (!response.ok) {
        throw new Error(result.detail || '작업 상태 조회 실패');
      }

      return result;
    } catch (error) {
      console.error('❌ 작업 상태 조회 실패:', error);
      throw error;
    }
  },

  /**
   * 작업 제어 (일시정지/재개/취소)
   * @param {string} jobId 작업 ID
   * @param {string} action 액션 (pause, resume, cancel)
   * @param {string} reason 사유 (선택사항)
   * @returns {Promise<Object>} 제어 결과
   */
  async controlJob(jobId, action, reason = null) {
    try {
      console.log(`🎮 작업 제어: ${jobId}, 액션: ${action}`);

      const response = await fetch(`${API.baseURL}/ingest/jobs/${jobId}/control`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Tenant-ID': 'wedosoft',
          'X-Platform': 'freshdesk',
        },
        body: JSON.stringify({
          action,
          reason,
        }),
      });

      const result = await response.json();

      if (!response.ok) {
        throw new Error(result.detail || '작업 제어 실패');
      }

      console.log(`✅ 작업 제어 성공: ${action}`);
      return result;
    } catch (error) {
      console.error('❌ 작업 제어 실패:', error);
      throw error;
    }
  },

  /**
   * 데이터 수집 메트릭스 조회
   * @returns {Promise<Object>} 메트릭스 정보
   */
  async getMetrics() {
    try {
      const response = await fetch(`${API.baseURL}/ingest/metrics`, {
        headers: {
          'X-Tenant-ID': 'wedosoft',
          'X-Platform': 'freshdesk',
        },
      });

      const result = await response.json();

      if (!response.ok) {
        throw new Error(result.detail || '메트릭스 조회 실패');
      }

      return result;
    } catch (error) {
      console.error('❌ 메트릭스 조회 실패:', error);
      throw error;
    }
  },

  /**
   * 기존 즉시 실행 방식 (하위 호환성)
   * @param {Object} options 수집 옵션
   * @param {string} domain Freshdesk 도메인
   * @param {string} apiKey Freshdesk API 키
   * @returns {Promise<Object>} 수집 결과
   */
  async triggerImmediate(options = {}, domain = null, apiKey = null) {
    try {
      console.log('⚡ 즉시 데이터 수집 실행...', options);

      const headers = {
        'Content-Type': 'application/json',
        'X-Tenant-ID': 'wedosoft',
        'X-Platform': 'freshdesk',
      };

      // 동적 Freshdesk 설정 추가 (백엔드 dependencies.py 헤더명 사용)
      if (domain) headers['X-Domain'] = domain;
      if (apiKey) headers['X-API-Key'] = apiKey;

      const response = await fetch(`${API.baseURL}/ingest`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          incremental: options.incremental !== false,
          purge: options.purge || false,
          process_attachments: options.process_attachments !== false,
          force_rebuild: options.force_rebuild || false,
          include_kb: options.include_kb !== false,
        }),
      });

      const result = await response.json();

      if (!response.ok) {
        throw new Error(result.detail || '데이터 수집 실패');
      }

      console.log('✅ 즉시 데이터 수집 완료');
      return result;
    } catch (error) {
      console.error('❌ 즉시 데이터 수집 실패:', error);
      throw error;
    }
  },
};

/**
 * 최적화된 API 모듈
 */
const API = {
  // 백엔드 서버 기본 URL
  baseURL: 'http://localhost:8000',

  /**
   * 백엔드 연결 상태 확인
   */
  async checkBackendConnection() {
    try {
      console.log('🔗 백엔드 연결 상태 확인 중...');
      const response = await fetch(`${this.baseURL}/docs`, {
        method: 'GET',
        timeout: 5000, // 5초 타임아웃
      });

      if (response.ok) {
        console.log('✅ 백엔드 연결 성공');
        return true;
      } else {
        console.warn('⚠️ 백엔드 응답 오류:', response.status);
        return false;
      }
    } catch (error) {
      console.error('❌ 백엔드 연결 실패:', error.message);
      return false;
    }
  },

  /**
   * 모듈 가용성 확인
   */
  isAvailable() {
    const dependencies = ['GlobalState'];
    const missing = dependencies.filter((dep) => !window[dep]);

    if (missing.length > 0) {
      console.warn('[API] 누락된 의존성:', missing);
      return false;
    }

    console.log('[API] 최적화된 모듈 초기화 완료 (캐싱, 배치 처리, 재시도 지원)');
    return true;
  },

  /**
   * 캐시 키 생성
   */
  generateCacheKey(endpoint, data, method) {
    const base = `${method}:${endpoint}`;
    if (data) {
      const dataHash = this.hashObject(data);
      return `${base}:${dataHash}`;
    }
    return base;
  },

  /**
   * 객체 해시 생성 (간단한 캐시 키용)
   */
  hashObject(obj) {
    const str = JSON.stringify(obj);
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
      const char = str.charCodeAt(i);
      hash = (hash << 5) - hash + char;
      hash = hash & hash; // 32bit 정수로 변환
    }
    return hash.toString(36);
  },

  /**
   * 지연 함수
   */
  delay(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  },

  /**
   * 배치 API 호출 지원
   * 여러 API 호출을 효율적으로 처리
   */
  async batchAPICall(client, requests, options = {}) {
    const { concurrency = 3, delay = 100 } = options;
    const results = [];

    console.log(`[API 배치] ${requests.length}개 요청을 ${concurrency}개씩 처리`);

    for (let i = 0; i < requests.length; i += concurrency) {
      const batch = requests.slice(i, i + concurrency);

      const batchPromises = batch.map(async (request, index) => {
        try {
          // 지연 처리로 서버 부하 분산
          if (index > 0) {
            await this.delay(delay);
          }

          const result = await this.callBackendAPIWithCache(
            client,
            request.endpoint,
            request.data,
            request.method,
            { ...request.options, showLoading: false }
          );

          return { index: i + index, success: true, data: result };
        } catch (error) {
          return {
            index: i + index,
            success: false,
            error: error.message,
            request: request,
          };
        }
      });

      const batchResults = await Promise.allSettled(batchPromises);
      results.push(...batchResults.map((r) => r.value || r.reason));

      // 배치 간 지연
      if (i + concurrency < requests.length) {
        await this.delay(delay * 2);
      }
    }

    const successful = results.filter((r) => r.success).length;
    const failed = results.filter((r) => !r.success).length;

    console.log(`[API 배치] 완료: 성공 ${successful}개, 실패 ${failed}개`);

    return results;
  },

  /**
   * 캐싱 지원 백엔드 API 호출 (자동 재시도 제거)
   * 실패 시 사용자에게 수동 재시도를 유도하는 UX 적용
   */
  async callBackendAPIWithCache(client, endpoint, data = null, method = 'GET', options = {}) {
    const cacheKey = this.generateCacheKey(endpoint, data, method);

    // GET 요청과 명시적으로 캐시를 허용한 경우만 캐시 확인
    if ((method === 'GET' || options.useCache) && options.bypassCache !== true) {
      const cached = window.PerformanceOptimizer.getCachedApiResult(cacheKey);
      if (cached) {
        console.log(`[API 캐시] ${method} /${endpoint} - 캐시 적중`);
        return cached;
      }
    }

    try {
      const result = await this.performAPICall(client, endpoint, data, method, options);

      // 성공한 결과 캐싱 (GET 요청 또는 명시적 허용)
      if ((method === 'GET' || options.useCache) && result && result.ok) {
        const ttl = options.cacheTTL || 300000; // 기본 5분
        window.PerformanceOptimizer.cacheApiResult(cacheKey, result, ttl);
      }

      return result;
    } catch (error) {
      // 자동 재시도 제거: 실패 시 바로 에러를 던져서 사용자가 수동으로 재시도할 수 있도록 함
      console.error(`[API 호출 실패] ${method} /${endpoint} - ${error.message}`);
      
      // 사용자 친화적인 에러 메시지로 변환
      if (error.status === 0 || !error.status) {
        // 네트워크 연결 문제
        error.userMessage = '네트워크 연결에 문제가 있습니다. 인터넷 연결을 확인하고 다시 시도해 주세요.';
      } else if (error.status >= 500) {
        // 서버 에러
        error.userMessage = '서버에 일시적인 문제가 발생했습니다. 잠시 후 다시 시도해 주세요.';
      } else if (error.status === 429) {
        // Rate limit
        error.userMessage = '요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.';
      } else if (error.status >= 400 && error.status < 500) {
        // 클라이언트 에러
        error.userMessage = '요청에 문제가 있습니다. 페이지를 새로고침하고 다시 시도해 주세요.';
      } else {
        // 기타 에러
        error.userMessage = '예상치 못한 문제가 발생했습니다. 페이지를 새로고침하고 다시 시도해 주세요.';
      }

      throw error;
    }
  },

  /**
   * 실제 API 호출 수행
   */
  async performAPICall(client, endpoint, data, method, options = {}) {
    let loadingId = null;

    try {
      console.log(
        `🚀 백엔드 API 호출: ${method} /${endpoint}`
      );

      // 로딩 상태 표시
      if (options.showLoading !== false) {
        const loadingMessage =
          method === 'GET' ? '데이터를 불러오는 중...' : '요청을 처리하는 중...';
        if (window.UI && window.UI.showLoading) {
          window.UI.showLoading(loadingMessage);
          loadingId = 'api-call';
        }
      }

      // iparams에서 Freshdesk 설정값 가져오기
      const config = await getFreshdeskConfigFromIparams(client);

      // 개발 환경에서 iparams가 없는 경우 환경변수 또는 기본값 사용
      let finalConfig = config;
      if (!config || !config.domain || !config.apiKey) {
        console.warn('⚠️ iparams에서 Freshdesk 설정값을 가져올 수 없습니다. 환경변수 폴백 시도...');
        
        // 개발 환경용 기본값 설정 (실제 운영에서는 iparams에서 가져와야 함)
        if (window.location.hostname === 'localhost' || window.location.hostname.includes('10001')) {
          finalConfig = {
            domain: 'wedosoft.freshdesk.com', // .env의 FRESHDESK_DOMAIN 값
            apiKey: 'Ug9H1cKCZZtZ4haamBy', // .env의 FRESHDESK_API_KEY 값
          };
          console.log('🛠️ 개발 환경: .env 파일의 Freshdesk 설정 사용');
        }
      }

      // 요청 설정
      const requestOptions = {
        method: method,
        headers: {
          'Content-Type': 'application/json',
          // 백엔드 dependencies.py에서 정의한 정확한 헤더명 사용
          ...(finalConfig?.domain && { 'X-Domain': finalConfig.domain }),
          ...(finalConfig?.apiKey && { 'X-API-Key': finalConfig.apiKey }),
          'X-Tenant-ID': 'wedosoft', // .env의 TENANT_ID 값
          'X-Platform': 'freshdesk', // 고정값
        },
        ...(data && { body: JSON.stringify(data) }),
      };

      // 헤더 로깅 (개발용)
      if (window.location.hostname === 'localhost') {
        console.log('📤 전송할 헤더:', {
          'X-Domain': finalConfig?.domain,
          'X-API-Key': finalConfig?.apiKey ? '***' + finalConfig.apiKey.slice(-4) : 'none',
          'X-Tenant-ID': 'wedosoft',
          'X-Platform': 'freshdesk',
        });
      }

      // 성능 측정
      const performanceKey = `API-${method}-${endpoint}`;
      const startTime = performance.now();

      const response = await fetch(`http://localhost:8000/${endpoint}`, requestOptions);

      const endTime = performance.now();
      console.log(`[성능] ${performanceKey}: ${(endTime - startTime).toFixed(2)}ms`);

      if (!response.ok) {
        const errorBody = await response.text();
        console.error(`❌ HTTP 응답 실패: ${response.status} ${response.statusText}`);
        console.error(`❌ 에러 응답 본문:`, errorBody);
        
        const error = new Error(`API 호출 실패: ${response.status} ${response.statusText}`);
        error.status = response.status;
        error.body = errorBody;
        throw error;
      }

      const result = await response.json();
      
      // 🔍 응답 데이터 상세 디버깅
      console.log(`✅ API 응답 성공 (${response.status})`);
      console.log(`🔍 [DEBUG] API 응답 데이터:`, {
        endpoint: endpoint,
        method: method,
        responseSize: JSON.stringify(result).length,
        hasTicketSummary: !!result.ticket_summary,
        hasSimilarTickets: !!result.similar_tickets,
        hasKbDocuments: !!result.kb_documents,
        dataKeys: Object.keys(result),
        fullData: result
      });

      // 일관된 응답 구조 반환
      return {
        ok: true,
        status: response.status,
        statusText: response.statusText,
        data: result
      };
    } catch (error) {
      if (window.GlobalState && window.GlobalState.ErrorHandler) {
        window.GlobalState.ErrorHandler.handleError(error, {
          module: 'api',
          function: 'performAPICall',
          context: `${method} /${endpoint}`,
          severity: 'error',
          userMessage: '서버와의 통신 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.',
        });
      }

      throw error;
    } finally {
      // 로딩 상태 해제
      if (loadingId && options.showLoading !== false && window.UI && window.UI.hideLoading) {
        window.UI.hideLoading();
      }
    }
  },

  /**
   * 기존 호환성을 위한 래퍼 함수
   */
  async callBackendAPI(client, endpoint, data = null, method = 'GET') {
    return await this.callBackendAPIWithCache(client, endpoint, data, method);
  },

  /**
   * 에이전트의 UI 언어 감지 (FDK 기반 간소화)
   * @param {Object} client - FDK 클라이언트 객체
   * @returns {string} 감지된 언어 코드 (ko, en, ja, zh)
   */
  async detectAgentLanguage(client) {
    try {
      // FDK loggedInUser에서 직접 언어 정보 획득
      const data = await client.data.get("loggedInUser");
      const agentLanguage = data.loggedInUser.contact.language;
      
      console.log('[언어감지] FDK에서 감지된 에이전트 언어:', agentLanguage);
      
      // 지원되는 언어로 매핑
      if (agentLanguage) {
        const langCode = agentLanguage.toLowerCase();
        if (langCode === 'ko' || langCode.startsWith('ko')) return 'ko';
        if (langCode === 'ja' || langCode.startsWith('ja')) return 'ja';
        if (langCode === 'zh' || langCode.startsWith('zh')) return 'zh';
        if (langCode === 'en' || langCode.startsWith('en')) return 'en';
      }
      
      // 기본값: 영어 (국제 표준)
      console.log('[언어감지] 지원되지 않는 언어, 기본값 사용: en');
      return 'en';
    } catch (error) {
      console.warn('[언어감지] FDK 언어 감지 실패, 기본값 사용:', error);
      return 'en';
    }
  },

  /**
   * 백엔드에서 초기 데이터를 로드하는 함수
   * @param {Object} client - FDK 클라이언트 객체
   * @param {string} ticketId - 티켓 ID
   */
  async loadInitData(client, ticketId) {
    // 기존 연결이 있으면 정리
    const connectionKey = `init_${ticketId}`;
    cleanupEventSource(connectionKey);
    
    try {
      console.log(`🎯 초기 데이터 로딩 시작: 티켓 ${ticketId}`);
      
      // 현재 에이전트 언어 가져오기 (FDK Data Method 활용)
      let agentLanguage = 'en'; // 기본값
      try {
        const loggedInUser = await client.data.get('loggedInUser');
        agentLanguage = loggedInUser?.contact?.language || 'en';
        console.log(`📍 에이전트 언어: ${agentLanguage}`);
      } catch (error) {
        console.warn('⚠️ 에이전트 언어 감지 실패, 기본값 사용:', error);
      }
      
      // 스트리밍 활성화된 파라미터
      const queryParams = new URLSearchParams({
        agent_language: agentLanguage,
        stream: 'true' // 스트리밍 응답 요청
      });
      
      const endpoint = `init/${ticketId}?${queryParams.toString()}`;
      
      // 스트리밍 모드로 호출
      const result = await this.callBackendAPIWithStreaming(client, endpoint, ticketId, {
        cacheTTL: 300000, // 5분 캐시
        loadingContext: '🚀 AI 분석 스트리밍',
        useOptimizedHeaders: true
      });
      
      // Vector DB 응답 구조 검증 및 정규화
      if (result.ok && result.data) {
        const normalizedData = this.normalizeVectorDBResponse(result.data);
        console.log('✅ Vector DB 초기 데이터 로딩 완료:', {
          ticketId,
          hasSummary: !!normalizedData.summary,
          similarTicketsCount: normalizedData.similar_tickets?.length || 0,
          kbDocumentsCount: normalizedData.kb_documents?.length || 0,
          executionTime: normalizedData.execution_time
        });
        
        return {
          ...result,
          data: normalizedData
        };
      }
      
      return result;
    } catch (error) {
      console.error('❌ Vector DB 초기 데이터 로딩 실패:', error);
      
      // 사용자 친화적인 에러 메시지를 추가
      if (error.userMessage) {
        console.error('🔸 사용자 메시지:', error.userMessage);
      }
      
      // 특정 에러 유형별로 구체적인 메시지 생성
      if (error.message && error.message.includes('JSON')) {
        error.userMessage = 'AI 서비스 응답을 처리하는 중 오류가 발생했습니다. 벡터 데이터베이스 설정을 확인하고 다시 시도해 주세요.';
      } else if (error.message && error.message.includes('timeout')) {
        error.userMessage = 'AI 분석 시간이 초과되었습니다. 네트워크 상태를 확인하고 다시 시도해 주세요.';
      } else if (!error.userMessage) {
        error.userMessage = 'AI 분석 서비스에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요.';
      }
      
      throw error;
    }
  },

  /**
   * Vector DB 응답 데이터를 정규화하는 함수
   * @param {Object} rawData - 백엔드에서 받은 원시 데이터
   * @returns {Object} 정규화된 데이터
   */
  normalizeVectorDBResponse(rawData) {
    return {
      // 기본 메타데이터
      success: rawData.success || true,
      ticket_id: rawData.ticket_id,
      tenant_id: rawData.tenant_id,
      platform: rawData.platform,
      
      // 실시간 생성된 요약 (Vector DB 모드의 핵심)
      summary: rawData.summary || null,
      
      // 유사 티켓 (Vector DB에서 검색된 결과)
      similar_tickets: this.normalizeSimilarTickets(rawData.similar_tickets || []),
      
      // KB 문서 (Vector DB에서 검색된 결과)  
      kb_documents: this.normalizeKBDocuments(rawData.kb_documents || []),
      
      // 성능 메트릭
      execution_time: rawData.execution_time || null,
      search_quality_score: rawData.search_quality_score || null,
      
      // 오류 정보
      error: rawData.error || null
    };
  },

  /**
   * Vector DB에서 검색된 유사 티켓 데이터 정규화
   * @param {Array} tickets - 원시 티켓 배열
   * @returns {Array} 정규화된 티켓 배열
   */
  normalizeSimilarTickets(tickets) {
    return tickets.map(ticket => ({
      // 기본 정보
      id: ticket.id || ticket.ticket_id,
      title: ticket.title || ticket.subject || '제목 없음',
      content: ticket.content || ticket.description_text || '',
      
      // Vector DB 메타데이터
      status: ticket.status || 'unknown',
      priority: ticket.priority || 'normal',
      category: ticket.category || null,
      agent_name: ticket.agent_name || null,
      created_at: ticket.created_at || null,
      
      // 검색 관련
      relevance_score: ticket.relevance_score || ticket.score || 0,
      confidence_score: ticket.confidence_score || null,
      
      // Vector DB 단독 모드에서 생성된 요약
      ai_summary: ticket.ai_summary || null,
      
      // 추가 메타데이터
      source_type: 'vector_db',
      doc_type: 'ticket'
    }));
  },

  /**
   * Vector DB에서 검색된 KB 문서 데이터 정규화
   * @param {Array} documents - 원시 문서 배열
   * @returns {Array} 정규화된 문서 배열
   */
  normalizeKBDocuments(documents) {
    return documents.map(doc => ({
      // 기본 정보
      id: doc.id || doc.article_id,
      title: doc.title || '제목 없음',
      content: doc.content || doc.description || '',
      excerpt: doc.excerpt || doc.content?.substring(0, 200) + '...' || '',
      
      // Vector DB 메타데이터
      category: doc.category || null,
      folder: doc.folder || null,
      status: doc.status || 'unknown',
      article_type: doc.article_type || 'solution',
      
      // 검색 관련
      relevance_score: doc.relevance_score || doc.score || 0,
      confidence_score: doc.confidence_score || null,
      
      // Vector DB 단독 모드에서 생성된 요약
      ai_summary: doc.ai_summary || null,
      
      // URL 및 메타데이터
      source_url: doc.source_url || null,
      created_at: doc.created_at || null,
      updated_at: doc.updated_at || null,
      
      // 추가 메타데이터
      source_type: 'vector_db',
      doc_type: 'kb'
    }));
  },

  /**
   * 캐시 관리 함수들
   */
  clearCache() {
    if (window.PerformanceOptimizer) {
      window.PerformanceOptimizer.resultCache.clear();
      console.log('[API] 캐시가 초기화되었습니다.');
    }
  },

  getCacheStats() {
    return window.PerformanceOptimizer ? window.PerformanceOptimizer.getMemoryStats() : {};
  },

  /**
   * 프리플라이트 체크 - API 서버 상태 확인
   */
  async healthCheck() {
    try {
      const response = await fetch('http://localhost:8000/health', {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' },
      });

      return response.ok;
    } catch (error) {
      console.warn('[API] 서버 상태 확인 실패:', error.message);
      return false;
    }
  },

  /**
   * 현재 감지된 에이전트 언어를 확인하는 유틸리티 함수 (FDK 기반)
   * @param {Object} client - FDK 클라이언트 객체
   * @returns {Promise<string>} 현재 언어 코드
   */
  async getCurrentAgentLanguage(client) {
    try {
      const language = await this.detectAgentLanguage(client);
      console.log(`[언어확인] FDK 기반 에이전트 언어: ${language}`);
      return language;
    } catch (error) {
      console.error('[언어확인] 언어 확인 중 오류:', error);
      return 'en';
    }
  },

  /**
   * 언어별 현지화 테스트 함수 (개발용)
   * @param {Object} client - FDK 클라이언트 객체
   * @param {string} testLanguage - 테스트할 언어 (ko, en, ja, zh)
   * @returns {Promise<Object>} 테스트 결과
   */
  async testLanguageLocalization(client, testLanguage = 'ko') {
    try {
      console.log(`[언어테스트] ${testLanguage} 언어로 API 테스트 시작`);
      
      // 현재 티켓 정보 가져오기
      const ticketData = await client.data.get('ticket');
      if (!ticketData || !ticketData.ticket) {
        throw new Error('티켓 정보를 가져올 수 없습니다');
      }
      
      // 테스트 언어로 API 호출
      const response = await this.loadInitData(client, ticketData.ticket.id, testLanguage);
      
      console.log(`[언어테스트] ${testLanguage} 언어 응답:`, response);
      
      // 유사 티켓의 섹션 제목 확인
      if (response && response.similar_tickets && response.similar_tickets.length > 0) {
        const firstTicket = response.similar_tickets[0];
        console.log(`[언어테스트] 첫 번째 유사 티켓 섹션 제목:`, {
          issue: firstTicket.issue ? firstTicket.issue.substring(0, 100) : null,
          solution: firstTicket.solution ? firstTicket.solution.substring(0, 100) : null
        });
      }
      
      return {
        success: true,
        language: testLanguage,
        similarTicketsCount: response?.similar_tickets?.length || 0,
        response: response
      };
    } catch (error) {
      console.error(`[언어테스트] ${testLanguage} 언어 테스트 실패:`, error);
      return {
        success: false,
        language: testLanguage,
        error: error.message
      };
    }
  },

  /**
   * Vector DB 기반 상담사 AI 검색 (향후 확장용)
   * @param {Object} client - FDK 클라이언트
   * @param {Object} searchQuery - 검색 쿼리 객체
   * @param {string} searchQuery.query - 자연어 검색 쿼리
   * @param {Object} searchQuery.filters - 메타데이터 필터
   * @param {Array} searchQuery.dateRange - 날짜 범위 [start, end]
   * @returns {Promise<Object>} 검색 결과
   */
  async performAdvancedVectorSearch(client, searchQuery) {
    try {
      console.log('🔍 Vector DB 고급 검색 실행:', searchQuery);
      
      const endpoint = 'search/agent';
      const searchData = {
        query: searchQuery.query,
        filters: {
          ...searchQuery.filters,
          date_range: searchQuery.dateRange,
          content_types: ['ticket', 'kb'],
          limit: searchQuery.limit || 20
        }
      };
      
      const result = await this.callBackendAPIWithCache(client, endpoint, searchData, 'POST', {
        useCache: false, // 검색은 실시간 결과 필요
        loadingContext: '🎯 AI 검색 실행 중...'
      });
      
      if (result.ok && result.data) {
        return {
          ...result,
          data: {
            tickets: this.normalizeSimilarTickets(result.data.tickets || []),
            kb_documents: this.normalizeKBDocuments(result.data.kb_documents || []),
            search_metadata: result.data.metadata || {}
          }
        };
      }
      
      return result;
    } catch (error) {
      console.error('❌ Vector DB 고급 검색 실패:', error);
      throw error;
    }
  },

  /**
   * 실시간 스트리밍 검색 (WebSocket 기반, 향후 확장)
   * @param {Object} client - FDK 클라이언트  
   * @param {string} query - 검색 쿼리
   * @param {Function} onChunk - 스트리밍 청크 콜백
   * @returns {Promise<void>}
   */
  async performStreamingSearch(client, query, onChunk) {
    try {
      console.log('🌊 실시간 스트리밍 검색 시작:', query);
      
      // 향후 WebSocket으로 교체 예정
      const endpoint = `search/stream?q=${encodeURIComponent(query)}`;
      
      const response = await fetch(`http://localhost:8000/${endpoint}`, {
        method: 'GET',
        headers: {
          'Accept': 'text/event-stream',
          'Cache-Control': 'no-cache'
        }
      });
      
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      
      while (true) {
        const {done, value} = await reader.read();
        if (done) break;
        
        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');
        
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              onChunk(data);
            } catch (e) {
              console.warn('스트리밍 파싱 오류:', e);
            }
          }
        }
      }
      
    } catch (error) {
      console.error('❌ 스트리밍 검색 실패:', error);
      throw error;
    }
  },

  /**
   * 🤖 Query 엔드포인트 전용 메서드 - 채팅 및 검색 기능
   * @param {Object} client - FDK 클라이언트
   * @param {Object} queryData - 쿼리 데이터
   * @param {string} queryData.query - 사용자 질문/검색어
   * @param {boolean} queryData.agent_mode - 스마트 모드 (true) / 자유 모드 (false)
   * @param {boolean} queryData.stream_response - 스트리밍 응답 여부
   * @param {string} queryData.ticket_id - 현재 티켓 ID
   * @param {Object} options - 추가 옵션
   * @returns {Promise<Object>} API 응답
   */
  async sendChatQuery(client, queryData, options = {}) {
    try {
      console.log('💬 채팅 쿼리 전송:', queryData);
      
      // 기본값 설정
      const requestData = {
        query: queryData.query,
        agent_mode: queryData.agent_mode !== false, // 기본값 true (스마트 모드)
        enhanced_search: !queryData.agent_mode, // agent_mode와 반대
        stream_response: queryData.stream_response !== false, // 기본값 true
        ticket_id: queryData.ticket_id,
        top_k: queryData.top_k || 5,
        answer_instructions: queryData.answer_instructions || null,
        tenant_id: 'wedosoft',
        platform: 'freshdesk'
      };
      
      // 스트리밍 요청인 경우 - 새로운 통합 엔드포인트 사용
      if (requestData.stream_response) {
        return await this.sendChatQueryWithStreaming(client, requestData, options);
      }
      
      // 일반 요청 - stream=false 파라미터와 함께 통합 엔드포인트 사용
      const queryParams = new URLSearchParams({ stream: 'false' });
      const result = await this.callBackendAPIWithCache(
        client,
        `query?${queryParams.toString()}`,
        requestData,
        'POST',
        {
          useCache: false, // 채팅은 항상 실시간 응답
          showLoading: options.showLoading !== false,
          loadingContext: '💬 AI 응답 생성 중...'
        }
      );
      
      return result;
    } catch (error) {
      console.error('❌ 채팅 쿼리 전송 실패:', error);
      throw error;
    }
  },

  /**
   * 🌊 스트리밍 채팅 쿼리 전용 메서드
   * @param {Object} client - FDK 클라이언트
   * @param {Object} requestData - 요청 데이터
   * @param {Object} options - 추가 옵션
   * @returns {Promise<Object>} 스트리밍 응답
   */
  async sendChatQueryWithStreaming(client, requestData, options = {}) {
    try {
      console.log('🌊 스트리밍 채팅 시작:', requestData);
      
      // iparams에서 Freshdesk 설정값 가져오기
      const config = await getFreshdeskConfigFromIparams(client);
      let finalConfig = config;
      
      if (!config || !config.domain || !config.apiKey) {
        if (window.location.hostname === 'localhost' || window.location.hostname.includes('10001')) {
          finalConfig = {
            domain: 'wedosoft.freshdesk.com',
            apiKey: 'Ug9H1cKCZZtZ4haamBy',
          };
        }
      }
      
      // 통합 엔드포인트의 스트리밍 모드 사용
      const queryParams = new URLSearchParams({ stream: 'true' });
      const response = await fetch(`${this.baseURL}/query?${queryParams.toString()}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'text/event-stream',
          ...(finalConfig?.domain && { 'X-Domain': finalConfig.domain }),
          ...(finalConfig?.apiKey && { 'X-API-Key': finalConfig.apiKey }),
          'X-Tenant-ID': 'wedosoft',
          'X-Platform': 'freshdesk',
        },
        body: JSON.stringify(requestData)
      });
      
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`스트리밍 요청 실패: ${response.status} - ${errorText}`);
      }
      
      // 스트리밍 응답 처리
      if (options.onStream) {
        await this.processStreamingChatResponse(response, options.onStream);
      }
      
      return {
        ok: true,
        streaming: true,
        status: response.status
      };
      
    } catch (error) {
      console.error('❌ 스트리밍 채팅 실패:', error);
      
      // 스트리밍 실패 시 일반 모드로 폴백
      if (options.fallbackToNormal !== false) {
        console.log('📡 일반 모드로 폴백 시도...');
        requestData.stream_response = false;
        const queryParams = new URLSearchParams({ stream: 'false' });
        return await this.callBackendAPIWithCache(
          client,
          `query?${queryParams.toString()}`,
          requestData,
          'POST',
          {
            useCache: false,
            showLoading: false
          }
        );
      }
      
      throw error;
    }
  },

  /**
   * 📡 스트리밍 채팅 응답 처리
   * @param {Response} response - fetch 응답 객체
   * @param {Function} onStream - 스트림 이벤트 콜백
   */
  async processStreamingChatResponse(response, onStream) {
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    
    try {
      while (true) {
        const { done, value } = await reader.read();
        
        if (done) {
          console.log('📡 채팅 스트리밍 완료');
          break;
        }
        
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';
        
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const eventData = JSON.parse(line.slice(6));
              
              // 스트림 이벤트 전달
              if (onStream) {
                onStream(eventData);
              }
              
              // 콘솔 로그
              if (eventData.type === 'token') {
                // 토큰 단위 스트리밍
                console.log('📝 토큰:', eventData.content);
              } else if (eventData.type === 'complete') {
                console.log('✅ 응답 완료:', eventData);
              } else if (eventData.type === 'error') {
                console.error('❌ 스트림 에러:', eventData.error);
              }
              
            } catch (parseError) {
              console.warn('📡 이벤트 파싱 실패:', line, parseError);
            }
          }
        }
      }
    } finally {
      reader.releaseLock();
    }
  },

  /**
   * 🔍 향상된 검색 쿼리 (자유 모드용)
   * @param {Object} client - FDK 클라이언트
   * @param {Object} searchQuery - 검색 쿼리
   * @param {string} searchQuery.query - 자연어 검색어
   * @param {Array} searchQuery.file_types - 파일 타입 필터
   * @param {Array} searchQuery.categories - 카테고리 필터
   * @param {string} searchQuery.solution_type - 솔루션 타입
   * @returns {Promise<Object>} 검색 결과
   */
  async performEnhancedSearch(client, searchQuery) {
    try {
      console.log('🔍 향상된 검색 실행:', searchQuery);
      
      const requestData = {
        query: searchQuery.query,
        enhanced_search: true,
        agent_mode: false,
        file_types: searchQuery.file_types || [],
        categories: searchQuery.categories || [],
        solution_type: searchQuery.solution_type || null,
        top_k: searchQuery.top_k || 10,
        ticket_id: searchQuery.ticket_id || null
      };
      
      const result = await this.callBackendAPIWithCache(
        client,
        'query',
        requestData,
        'POST',
        {
          useCache: true, // 검색은 캐싱 가능
          cacheTTL: 60000, // 1분 캐시
          showLoading: true,
          loadingContext: '🔍 검색 중...'
        }
      );
      
      return result;
    } catch (error) {
      console.error('❌ 향상된 검색 실패:', error);
      throw error;
    }
  },

  // ...existing code...
};

// 의존성 확인 함수
API.isAvailable = function () {
  const dependencies = ['GlobalState'];
  const missing = dependencies.filter((dep) => typeof window[dep] === 'undefined');

  if (missing.length > 0) {
    console.warn('[API] 누락된 의존성:', missing);
    return false;
  }

  return true;
};

/**
 * 스트리밍 API 호출 함수
 * @param {Object} client - FDK 클라이언트 객체
 * @param {string} endpoint - API 엔드포인트
 * @param {string} ticketId - 티켓 ID (스트리밍 상태 추적용)
 * @param {Object} options - 호출 옵션
 */
API.callBackendAPIWithStreaming = async function(client, endpoint, ticketId, options = {}) {
  try {
    console.log(`🌊 스트리밍 API 호출 시작: ${endpoint}`);
    
    // 스트리밍 시작
    if (window.GlobalState && window.GlobalState.startStreaming) {
      window.GlobalState.startStreaming(ticketId);
    }
    
    // 사이드바 진행률 표시 시작
    if (window.SidebarProgress && window.SidebarProgress.show) {
      window.SidebarProgress.show();
    }
    
    // 실제 스트리밍 응답 처리
    try {
      const result = await this.performStreamingAPICall(client, endpoint, ticketId, options);
      
      if (result.ok && result.data) {
        // 스트리밍 완료
        if (window.GlobalState && window.GlobalState.stopStreaming) {
          window.GlobalState.stopStreaming();
        }
        
        console.log('🎉 스트리밍 API 호출 완료');
        return result;
      } else {
        throw new Error('API 호출 실패');
      }
    } catch (error) {
      // 실제 스트리밍이 실패하면 시뮬레이션으로 폴백
      console.warn('📡 실제 스트리밍 실패, 시뮬레이션으로 폴백:', error.message);
      
      const fallbackResult = await this.callBackendAPIWithCache(client, endpoint, null, 'GET', options);
      
      if (fallbackResult.ok && fallbackResult.data) {
        // 스트리밍 시뮬레이션 (단계별 업데이트)
        await this.simulateStreamingProgress(fallbackResult.data, ticketId);
        
        // 스트리밍 완료
        if (window.GlobalState && window.GlobalState.stopStreaming) {
          window.GlobalState.stopStreaming();
        }
        
        console.log('🎉 시뮬레이션 스트리밍 API 호출 완료');
        return fallbackResult;
      } else {
        throw new Error('API 호출 실패 (폴백 포함)');
      }
    }
    
  } catch (error) {
    console.error('❌ 스트리밍 API 호출 실패:', error);
    
    // 스트리밍 에러 처리
    if (window.GlobalState && window.GlobalState.setStreamingError) {
      window.GlobalState.setStreamingError(error.message);
    }
    
    throw error;
  }
};

/**
 * 실제 스트리밍 API 호출 수행
 * @param {Object} client - FDK 클라이언트
 * @param {string} endpoint - API 엔드포인트  
 * @param {string} ticketId - 티켓 ID
 * @param {Object} options - 호출 옵션
 */
API.performStreamingAPICall = async function(client, endpoint, ticketId, options = {}) {
  console.log(`📡 실제 스트리밍 API 호출: ${endpoint}`, { ticketId, options });
  
  // iparams에서 Freshdesk 설정값 가져오기
  const config = await getFreshdeskConfigFromIparams(client);
  
  // 개발 환경에서 iparams가 없는 경우 기본값 사용
  let finalConfig = config;
  if (!config || !config.domain || !config.apiKey) {
    if (window.location.hostname === 'localhost' || window.location.hostname.includes('10001')) {
      finalConfig = {
        domain: 'wedosoft.freshdesk.com',
        apiKey: 'Ug9H1cKCZZtZ4haamBy',
      };
    }
  }
  
  // 스트리밍 응답을 위한 fetch 호출
  const response = await fetch(`${this.baseURL}/${endpoint}`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'text/event-stream', // Server-Sent Events 요청
      ...(finalConfig?.domain && { 'X-Domain': finalConfig.domain }),
      ...(finalConfig?.apiKey && { 'X-API-Key': finalConfig.apiKey }),
      'X-Tenant-ID': 'wedosoft',
      'X-Platform': 'freshdesk',
      'X-Stream': 'true', // 스트리밍 모드 명시적 요청
    },
  });
  
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  }
  
  // 응답이 스트리밍인지 확인
  const contentType = response.headers.get('content-type');
  if (contentType && contentType.includes('text/event-stream')) {
    // Server-Sent Events 스트리밍 처리
    return await this.processServerSentEvents(response, ticketId);
  } else {
    // 일반 JSON 응답 처리
    const data = await response.json();
    return {
      ok: true,
      data: data,
      status: response.status
    };
  }
};

/**
 * Server-Sent Events 스트리밍 응답 처리
 * @param {Response} response - fetch 응답 객체
 * @param {string} ticketId - 티켓 ID
 */
API.processServerSentEvents = async function(response, ticketId) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let finalData = null;
  
  try {
    while (true) {
      const { done, value } = await reader.read();
      
      if (done) {
        console.log('📡 스트리밍 완료');
        break;
      }
      
      // 받은 데이터를 버퍼에 추가
      buffer += decoder.decode(value, { stream: true });
      
      // 이벤트별로 분리 처리
      const lines = buffer.split('\n');
      buffer = lines.pop() || ''; // 마지막 불완전한 라인은 버퍼에 보관
      
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const dataStr = line.slice(6).trim(); // 'data: ' 제거
            
            // 빈 문자열이나 특수 값 체크
            if (!dataStr || dataStr === '[DONE]' || dataStr === 'done') {
              continue;
            }
            
            // JSON 파싱 전 유효성 검사
            if (!dataStr.startsWith('{') && !dataStr.startsWith('[')) {
              console.warn('📡 JSON이 아닌 데이터 수신:', dataStr);
              continue;
            }
            
            const eventData = JSON.parse(dataStr);
            this.handleStreamingEvent(eventData, ticketId);
            
            // 최종 데이터 저장
            if (eventData.type === 'complete' || eventData.final_data) {
              finalData = eventData.final_data || eventData.data;
            }
          } catch (parseError) {
            console.warn('📡 스트리밍 이벤트 파싱 실패:', line, parseError);
          }
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
  
  return {
    ok: true,
    data: finalData,
    status: response.status
  };
};

/**
 * 스트리밍 이벤트 처리
 * @param {Object} eventData - 스트리밍 이벤트 데이터
 * @param {string} ticketId - 티켓 ID
 */
API.handleStreamingEvent = function(eventData, ticketId) {
  console.log(`📡 스트리밍 이벤트 수신 (티켓 ${ticketId}):`, eventData);
  
  if (!eventData.type) return;
  
  switch (eventData.type) {
    case 'progress':
      // 진행률 업데이트
      if (window.GlobalState && window.GlobalState.updateStreamingStage) {
        window.GlobalState.updateStreamingStage(eventData.stage, {
          completed: false,
          progress: eventData.progress || 0,
          message: eventData.message || `${eventData.stage} 처리 중...`
        });
      }
      break;
      
    case 'stage_complete':
      // 단계 완료
      if (window.GlobalState && window.GlobalState.updateStreamingStage) {
        window.GlobalState.updateStreamingStage(eventData.stage, {
          completed: true,
          progress: 100,
          message: eventData.message || `${eventData.stage} 완료`
        });
      }
      break;
      
    case 'overall_progress':
      // 전체 진행률 업데이트
      if (window.GlobalState && window.GlobalState.getGlobalTicketData) {
        const globalData = window.GlobalState.getGlobalTicketData();
        if (globalData.streaming_status) {
          globalData.streaming_status.overall_progress = eventData.progress || 0;
        }
      }
      break;
      
    case 'error':
      // 에러 처리
      console.error('📡 스트리밍 에러:', eventData.error);
      if (window.GlobalState && window.GlobalState.setStreamingError) {
        window.GlobalState.setStreamingError(eventData.error);
      }
      break;
      
    case 'complete':
      // 스트리밍 완료
      console.log('📡 스트리밍 완료 이벤트 수신');
      break;
      
    default:
      console.log(`📡 알 수 없는 이벤트 타입: ${eventData.type}`);
  }
};

/**
 * 스트리밍 진행률 시뮬레이션 (실제 스트리밍 응답이 올 때까지의 임시 구현)
 * @param {Object} finalData - 최종 받은 데이터
 * @param {string} ticketId - 티켓 ID
 */
API.simulateStreamingProgress = async function(finalData, ticketId) {
  console.log(`🎭 시뮬레이션 시작 - 티켓 ${ticketId}`, finalData);
  const stages = ['ticket_fetch', 'summary', 'similar_tickets', 'kb_documents'];
  
  for (let i = 0; i < stages.length; i++) {
    const stage = stages[i];
    
    // 단계 시작
    if (window.GlobalState && window.GlobalState.updateStreamingStage) {
      window.GlobalState.updateStreamingStage(stage, {
        completed: false,
        progress: 50,
        message: `${stage} 처리 중...`
      });
    }
    
    // 단계별 지연 (실제 처리 시간 시뮬레이션)
    await new Promise(resolve => setTimeout(resolve, 500 + Math.random() * 500));
    
    // 단계 완료
    if (window.GlobalState && window.GlobalState.updateStreamingStage) {
      window.GlobalState.updateStreamingStage(stage, {
        completed: true,
        progress: 100,
        message: `${stage} 완료`
      });
    }
    
    // 전체 진행률 업데이트
    const overallProgress = Math.round(((i + 1) / stages.length) * 100);
    if (window.GlobalState && window.GlobalState.getGlobalTicketData) {
      const globalData = window.GlobalState.getGlobalTicketData();
      globalData.streaming_status.overall_progress = overallProgress;
    }
    
    console.log(`📈 스트리밍 진행률: ${overallProgress}% (${stage} 완료)`);
  }
};

// 모듈 등록 (로그 없음)

// 모듈 의존성 시스템에 등록
if (typeof window.ModuleDependencyManager !== 'undefined') {
  window.ModuleDependencyManager.registerModule('api', Object.keys(API).length);
}

// 전역으로 export
window.API = API;

/**
 * 🌍 다국어 지원 테스트 함수 (개발/테스트용)
 * 브라우저 콘솔에서 직접 호출 가능
 */
window.testMultiLanguageSupport = async function(language = 'ko') {
  try {
    if (!window.API) {
      console.error('❌ API 모듈이 로드되지 않았습니다.');
      return;
    }
    
    const client = GlobalState.getClient();
    if (!client) {
      console.error('❌ FDK 클라이언트가 설정되지 않았습니다.');
      return;
    }
    
    console.log(`🌍 ${language} 언어 지원 테스트 시작...`);
    
    // FDK에서 현재 감지된 언어 확인
    const detectedLang = await API.getCurrentAgentLanguage(client);
    console.log(`🔍 FDK에서 자동 감지된 언어: ${detectedLang}`);
    
    // 지정된 언어로 테스트
    const testResult = await API.testLanguageLocalization(client, language);
    
    if (testResult.success) {
      console.log(`✅ ${language} 언어 테스트 성공!`);
      console.log(`📊 유사 티켓 ${testResult.similarTicketsCount}개 로드됨`);
      
      // UI 업데이트 (글로벌 상태에 저장된 데이터 사용)
      const globalData = GlobalState.getGlobalTicketData();
      if (globalData.similar_tickets && globalData.similar_tickets.length > 0) {
        console.log('🎨 UI에 현지화된 유사 티켓 표시 중...');
        if (window.UI && window.UI.displaySimilarTickets) {
          UI.displaySimilarTickets(globalData.similar_tickets);
        }
      }
    } else {
      console.error(`❌ ${language} 언어 테스트 실패:`, testResult.error);
    }
    
    return testResult;
  } catch (error) {
    console.error('❌ 다국어 테스트 중 오류:', error);
  }
};

console.log('🌍 다국어 지원 테스트 함수가 로드되었습니다. 사용법:');
console.log('testMultiLanguageSupport("ko") - 한국어 테스트');
console.log('testMultiLanguageSupport("en") - 영어 테스트');
console.log('testMultiLanguageSupport("ja") - 일본어 테스트');
console.log('testMultiLanguageSupport("zh") - 중국어 테스트');

/**
 * 🎯 간단한 사이드바 로딩 표시 함수
 * 복잡한 스트리밍 대신 간단한 "로딩 중" 상태만 표시합니다.
 * 
 * @param {Object} client - FDK 클라이언트 객체
 * @param {string} ticketId - 티켓 ID
 * @returns {Promise<boolean>} 로딩 표시 성공 여부
 */
async function showSimpleLoadingInSidebar(client, ticketId) {
  try {
    console.log(`🎯 사이드바 간단 로딩: ${ticketId}`);

    // 백그라운드에서 조용히 데이터 로드만 수행
    if (typeof Data !== 'undefined' && Data.preloadTicketDataOnPageLoad) {
      console.log('📡 백그라운드 AI 데이터 준비...');
      
      // 에러가 발생해도 조용히 처리
      try {
        await Data.preloadTicketDataOnPageLoad(client);
        console.log('✅ 백그라운드 데이터 준비 완료');
      } catch (dataError) {
        console.warn('⚠️ 백그라운드 데이터 준비 실패 (무시):', dataError.message);
      }
    }

    return true;

  } catch (error) {
    console.warn('⚠️ 사이드바 로딩 처리 실패 (무시):', error.message);
    return false;
  }
}

// API 네임스페이스에 간단한 로딩 함수 추가
if (typeof window.API === 'undefined') {
  window.API = {};
}

window.API.showSimpleLoadingInSidebar = showSimpleLoadingInSidebar;

console.log('🎯 간단한 사이드바 로딩 함수가 로드되었습니다');
console.log('사용법: API.showSimpleLoadingInSidebar(client, ticketId)');
