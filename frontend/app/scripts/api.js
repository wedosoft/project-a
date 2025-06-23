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

/**
 * 🔗 iparams에서 Freshdesk 설정값을 가져오는 함수
 * 고객사별로 다른 도메인과 API 키를 동적으로 로드하여 멀티테넌트 환경 지원
 */
async function getFreshdeskConfigFromIparams(client) {
  try {
    console.log('📋 iparams에서 Freshdesk 설정값 로드 중...');

    const iparams = await client.iparams.get();

    if (iparams && iparams.freshdesk_domain && iparams.freshdesk_api_key) {
      console.log(`✅ iparams 로드 성공: 도메인 ${iparams.freshdesk_domain}`);
      return {
        domain: iparams.freshdesk_domain,
        apiKey: iparams.freshdesk_api_key,
      };
    }

    console.warn('⚠️ iparams에서 필수 설정값이 누락됨');
    return null;
  } catch (error) {
    console.error('❌ iparams 로드 실패:', error);
    return null;
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
        'X-Company-ID': await API.getCompanyId(),
      };

      // 동적 Freshdesk 설정 추가
      if (domain) headers['X-Freshdesk-Domain'] = domain;
      if (apiKey) headers['X-Freshdesk-API-Key'] = apiKey;

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
          'X-Company-ID': await API.getCompanyId(),
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
          'X-Company-ID': await API.getCompanyId(),
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
          'X-Company-ID': await API.getCompanyId(),
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
          'X-Company-ID': await API.getCompanyId(),
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
        'X-Company-ID': await API.getCompanyId(),
      };

      // 동적 Freshdesk 설정 추가
      if (domain) headers['X-Freshdesk-Domain'] = domain;
      if (apiKey) headers['X-Freshdesk-API-Key'] = apiKey;

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
  /**
   * 모듈 가용성 확인
   */
  isAvailable() {
    const dependencies = ['GlobalState', 'PerformanceOptimizer'];
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
            domain: 'wedosoft.freshdesk.com', // 개발용 기본값
            apiKey: 'Ug9H1cKCZZtZ4haamBy', // 개발용 기본값
          };
          console.log('🛠️ 개발 환경: 기본 Freshdesk 설정 사용');
        }
      }

      // 요청 설정
      const requestOptions = {
        method: method,
        headers: {
          'Content-Type': 'application/json',
          ...(finalConfig?.domain && { 'X-Freshdesk-Domain': finalConfig.domain }),
          ...(finalConfig?.apiKey && { 'X-Freshdesk-API-Key': finalConfig.apiKey }),
        },
        ...(data && { body: JSON.stringify(data) }),
      };

      // 헤더 로깅 (개발용)
      if (window.location.hostname === 'localhost') {
        console.log('📤 전송할 헤더:', {
          'X-Freshdesk-Domain': finalConfig?.domain,
          'X-Freshdesk-API-Key': finalConfig?.apiKey ? '***' + finalConfig.apiKey.slice(-4) : 'none',
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
   * @param {string} agentLanguage - 에이전트 UI 언어 (선택사항)
   */
  async loadInitData(client, ticketId, agentLanguage = null) {
    try {
      // 에이전트 언어가 제공되지 않은 경우 자동 감지
      if (!agentLanguage) {
        agentLanguage = await this.detectAgentLanguage(client);
      }
      
      console.log(`[API] 초기 데이터 로드 - 티켓: ${ticketId}, 언어: ${agentLanguage}`);
      
      // agent_language 쿼리 매개변수를 포함하여 API 호출
      const endpoint = `init/${ticketId}?agent_language=${agentLanguage}`;
      
      return await this.callBackendAPIWithCache(client, endpoint, null, 'GET', {
        cacheTTL: 600000, // 10분 캐시
        loadingContext: '초기 데이터 로드',
      });
    } catch (error) {
      console.error('[API] 초기 데이터 로드 중 오류:', error);
      throw error;
    }
  },

  /**
   * 자연어 쿼리 실행
   */
  async executeQuery(client, queryData) {
    return await this.callBackendAPIWithCache(client, 'query', queryData, 'POST', {
      useCache: false, // POST 요청은 기본적으로 캐시하지 않음
      loadingContext: '쿼리 실행',
    });
  },

  /**
   * 모든 티켓 목록 가져오기
   */
  async getAllTickets(client) {
    return await this.callBackendAPIWithCache(client, 'tickets/all', null, 'GET', {
      cacheTTL: 900000, // 15분 캐시
      loadingContext: '티켓 목록 조회',
    });
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

if (window.location.hostname === 'localhost') {
  console.log('📡 최적화된 API 모듈 로드 완료 - 향상된 성능 및 캐싱 지원');
}

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
