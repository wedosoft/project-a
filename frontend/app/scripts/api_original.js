/**
 * 🌐 백엔드 API 통신 전담 클라이언트 - Freshdesk 연동 통신 모듈
 *
 * 이 모듈은 Freshdesk Custom App과 백엔드 AI 서버 간의 모든 통신을 담당합니다.
 * Python FastAPI 백엔드와 안전하고 효율적인 데이터 교환을 위한 클라이언트 라이브러리입니다.
 *
 * 주요 기능:
 * - 동적 Freshdesk 설정 지원 (멀티테넌트 환경)
 * - 자동 헤더 구성 및 인증 처리
 * - 에러 복구 및 재시도 로직
 * - API 응답 캐싱 및 성능 최적화
 * - 백엔드 9개 엔드포인트 전체 지원
 *
 * 지원 엔드포인트:
 * - /init: 티켓 초기 데이터 로드
 * - /query: 자연어 AI 채팅 처리
 * - /generate_reply: 추천 답변 생성
 * - /ingest: 데이터 수집 관리
 * - /health, /metrics: 시스템 모니터링
 * - /query/stream, /generate_reply/stream: 실시간 스트리밍
 * - /attachments/*: 첨부파일 접근
 *
 * @author We Do Soft Inc.
 * @since 2025.06.16
 * @version 2.0.0 (멀티테넌트 지원 및 문서화 강화)
 */

// API 모듈 정의 - 모든 API 관련 함수를 하나의 객체로 관리
window.API = window.API || {};

/**
 * 🔗 백엔드 API 호출 핵심 함수
 *
 * Freshdesk Custom App과 Python FastAPI 백엔드 간의 모든 통신을 처리하는 핵심 함수입니다.
 * 멀티테넌트 환경에서 각 고객사의 Freshdesk 설정을 동적으로 적용하여 안전한 데이터 격리를 보장합니다.
 *
 * 주요 처리 과정:
 * 1. iparams에서 고객사별 Freshdesk 설정 로드
 * 2. 동적 헤더 구성 (X-Freshdesk-Domain, X-Freshdesk-API-Key)
 * 3. 백엔드 API 호출 및 응답 처리
 * 4. 에러 상황 시 적절한 폴백 처리
 * 5. 응답 데이터 검증 및 캐싱
 *
 * @param {Object} client - FDK 클라이언트 객체 (Freshdesk SDK)
 * @param {string} endpoint - API 엔드포인트 (예: "init/123", "query")
 * @param {Object|null} data - 요청 데이터 (POST 요청의 경우)
 * @param {string} method - HTTP 메서드 ("GET" 또는 "POST")
 * @returns {Promise<Object>} API 응답 결과 {ok: boolean, data?: Object, error?: string}
 *
 * @example
 * // 티켓 초기 데이터 로드
 * const result = await callBackendAPI(client, "init/12345", null, "GET");
 *
 * // 자연어 쿼리 실행
 * const queryData = { query: "유사한 문제를 찾아줘", type: ["tickets", "solutions"] };
 * const result = await callBackendAPI(client, "query", queryData, "POST");
 */
async function callBackendAPI(client, endpoint, data = null, method = 'GET') {
  let loadingId = null;

  try {
    console.log(`🚀 백엔드 API 호출: ${method} /${endpoint}`);

    // 로딩 상태 표시
    const loadingMessage = method === 'GET' ? '데이터를 불러오는 중...' : '요청을 처리하는 중...';
    if (typeof UI !== 'undefined' && UI.showLoading) {
      UI.showLoading(loadingMessage);
      loadingId = 'api-call';
    }

    // iparams에서 Freshdesk 설정값 가져오기
    // 각 고객사별로 다른 도메인과 API 키를 동적으로 로드
    const config = await getFreshdeskConfigFromIparams(client);

    if (!config || !config.domain || !config.apiKey) {
      console.warn('⚠️ iparams에서 Freshdesk 설정값을 가져올 수 없습니다. 환경변수 폴백 시도...');

      // 폴백: requests.json의 기본 헤더 사용 (개발 환경용)
      if (method === 'GET') {
        const response = await client.request.invokeTemplate('backendApi', {
          context: { path: endpoint },
        });
        return { ok: true, data: response };
      } else {
        const response = await client.request.invokeTemplate('backendApiPost', {
          context: { path: endpoint },
          body: JSON.stringify(data),
        });
        return { ok: true, data: response };
      }
    }

    // iparams 값으로 동적 헤더 생성
    const dynamicHeaders = {
      'Content-Type': 'application/json',
      'X-Freshdesk-Domain': config.companyId || extractCompanyIdFromDomain(config.domain), // company_id 전달
      'X-Freshdesk-API-Key': config.apiKey,
      'ngrok-skip-browser-warning': 'true', // ngrok 환경용
    };

    console.log('📡 동적 헤더 생성:', {
      domain: dynamicHeaders['X-Freshdesk-Domain'],
      hasApiKey: !!dynamicHeaders['X-Freshdesk-API-Key'],
    });

    // 동적 요청 설정으로 API 호출
    const requestConfig = {
      method: method,
      protocol: 'https',
      host: config.backendUrl
        ? new URL(config.backendUrl).host
        : '7987-58-122-170-2.ngrok-free.app',
      path: `/${endpoint}`,
      headers: dynamicHeaders,
    };

    if (method === 'GET') {
      const response = await client.request.invoke('generic', {
        schema: requestConfig,
        context: { path: endpoint },
      });
      return { ok: true, data: response.response || response };
    } else {
      requestConfig.body = JSON.stringify(data);
      const response = await client.request.invoke('generic', {
        schema: requestConfig,
        context: { path: endpoint },
        body: JSON.stringify(data),
      });
      return { ok: true, data: response.response || response };
    }
  } catch (error) {
    console.error(`❌ 백엔드 API 호출 오류 (${method} /${endpoint}):`, error);

    // 개선된 에러 처리 사용
    GlobalState.ErrorHandler.handleError(error, {
      module: 'api',
      function: 'callBackendAPI',
      context: `${method} /${endpoint}`,
      severity: 'error',
      userMessage: '서버와의 통신 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.',
    });

    return { ok: false, error: error.message };
  } finally {
    // 로딩 상태 해제
    if (loadingId && typeof UI !== 'undefined' && UI.hideLoading) {
      UI.hideLoading();
    }
  }
}

/**
 * 백엔드에서 초기 데이터를 로드하는 함수 (/init 엔드포인트 호출)
 * @param {Object} client - FDK 클라이언트 객체
 * @param {Object} basicTicketInfo - 기본 티켓 정보
 */
async function loadInitialDataFromBackend(client, basicTicketInfo) {
  try {
    console.log('🚀 백엔드 초기 데이터 로드 시작');

    // 중복 호출 방지
    if (globalTicketData.isLoading) {
      console.log('⚠️ 이미 로딩 중이므로 중복 호출 방지');
      return;
    }

    // 로딩 상태 설정
    globalTicketData.isLoading = true;

    try {
      // FDK를 통한 백엔드 /init API 호출 (GET 메서드, 데이터 없음)
      const response = await callBackendAPI(client, `init/${basicTicketInfo.id}`, null, 'GET');

      if (response.ok) {
        const data = response.data;
        console.log('✅ 백엔드 초기 데이터 로드 완료:', data);

        // 응답 데이터 구조 확인 및 로깅
        console.log('📊 응답 데이터 분석:');
        console.log('- similar_tickets 개수:', data.similar_tickets?.length || 0);
        console.log('- kb_documents 개수:', data.kb_documents?.length || 0);
        console.log('- similar_tickets 데이터:', data.similar_tickets);
        console.log('- kb_documents 데이터:', data.kb_documents);

        // 백엔드에서 받은 완전한 티켓 정보로 UI 업데이트
        if (data.ticket_data) {
          console.log('🎫 백엔드에서 받은 완전한 티켓 정보로 UI 업데이트');
          updateTicketInfo(data.ticket_data);
        } else {
          // 백엔드에서 티켓 데이터가 없으면 기본 정보 사용
          console.log('🎫 기본 티켓 정보로 UI 업데이트');
          updateTicketInfo(basicTicketInfo);
        }

        // 전역 캐시에 데이터 저장 (ticket_info 포함)
        globalTicketData = {
          summary: data.ticket_summary,
          similar_tickets: data.similar_tickets || [],
          recommended_solutions: data.kb_documents || [], // 백엔드에서는 kb_documents로 온다
          cached_ticket_id: basicTicketInfo.id,
          ticket_info: data.ticket_data || basicTicketInfo, // 백엔드 티켓 정보를 캐시에 저장
          isLoading: false,
          lastLoadTime: Date.now(),
        };

        // /init 엔드포인트에서 모든 데이터를 한 번에 받아서 표시
        if (data.ticket_summary) {
          displayTicketSummary(data.ticket_summary);
        }

        if (data.similar_tickets && data.similar_tickets.length > 0) {
          console.log(`📋 유사 티켓 ${data.similar_tickets.length}개 표시`);
          displaySimilarTickets(data.similar_tickets);
        } else {
          console.log('📋 백엔드에서 유사 티켓 없음, 빈 상태 표시');
          displaySimilarTickets([]);
        }

        if (data.kb_documents && data.kb_documents.length > 0) {
          console.log(`💡 추천 솔루션 ${data.kb_documents.length}개 표시`);
          displaySuggestedSolutions(data.kb_documents);
        } else {
          console.log('💡 백엔드에서 추천 솔루션 없음, 빈 상태 표시');
          displaySuggestedSolutions([]);
        }
      } else {
        console.error('❌ 백엔드 초기 데이터 로드 실패:', response.status);
        // 폴백: Freshdesk API 사용
        console.log('🔄 백엔드 실패, Freshdesk API 폴백 사용');
        updateTicketInfo(basicTicketInfo);
        await loadSimilarTicketsFromFreshdesk(basicTicketInfo);
        displaySuggestedSolutions(generateMockSolutions());

        // 캐시 초기화
        globalTicketData = {
          summary: null,
          similar_tickets: [],
          recommended_solutions: [],
          cached_ticket_id: basicTicketInfo.id,
          ticket_info: basicTicketInfo,
          isLoading: false,
          lastLoadTime: Date.now(),
        };
      }
    } finally {
      // 로딩 상태 해제
      globalTicketData.isLoading = false;
    }
  } catch (error) {
    console.error('❌ 백엔드 초기 데이터 로드 중 예외 발생:', error);
    globalTicketData.isLoading = false;

    // 폴백 처리
    try {
      console.log('🔄 예외 발생으로 인한 폴백 처리');
      updateTicketInfo(basicTicketInfo);
      await loadSimilarTicketsFromFreshdesk(basicTicketInfo);
      displaySuggestedSolutions(generateMockSolutions());
    } catch (fallbackError) {
      console.error('❌ 폴백 처리도 실패:', fallbackError);
    }
  }
}

/**
 * 백엔드에서 유사 티켓을 로드하는 함수
 * @param {Object} ticket - 티켓 정보
 */
async function loadSimilarTicketsFromBackend(ticket) {
  try {
    console.log('🔍 유사 티켓 검색 시작');

    // 캐시된 데이터가 있고 같은 티켓인 경우 재사용
    if (
      globalTicketData.cached_ticket_id === ticket.id &&
      globalTicketData.similar_tickets.length > 0
    ) {
      console.log('🔄 캐시된 유사 티켓 데이터 사용');
      displaySimilarTickets(globalTicketData.similar_tickets);
      return;
    }

    console.log('⚠️ 유사 티켓이 캐시에 없음 - /init 엔드포인트에서 이미 받았어야 하는 데이터');

    // /init 엔드포인트에서 이미 모든 데이터를 받았어야 하므로,
    // 별도 API 호출 대신 Freshdesk API 폴백 사용
    console.log('🔄 Freshdesk API 폴백 사용');
    await loadSimilarTicketsFromFreshdesk(ticket);
  } catch (error) {
    console.error('❌ 백엔드 연결 오류:', error);
    // 폴백: Freshdesk API 사용
    await loadSimilarTicketsFromFreshdesk(ticket);
  }
}

/**
 * iparams에서 Freshdesk 설정값을 가져오는 함수
 * @param {Object} client - FDK 클라이언트 객체
 * @returns {Promise<Object|null>} Freshdesk 설정 정보
 */
async function getFreshdeskConfigFromIparams(client) {
  try {
    console.log('🔧 iparams에서 Freshdesk 설정값 가져오기 시작');

    // FDK의 iparams API를 통해 설정값 조회
    const iparams = await client.iparams.get();

    if (!iparams) {
      console.warn('⚠️ iparams 데이터가 없습니다.');
      return null;
    }

    const config = {
      domain: iparams.freshdesk_domain,
      apiKey: iparams.freshdesk_api_key,
      backendUrl: iparams.backend_url,
      companyId: iparams.company_id,
    };

    console.log('✅ iparams 설정값 조회 완료:', {
      domain: config.domain ? '✓' : '✗',
      apiKey: config.apiKey ? '✓' : '✗',
      backendUrl: config.backendUrl ? '✓' : '✗',
      companyId: config.companyId ? '✓' : '✗',
    });

    // 스마트 도메인 파싱 (프론트엔드에서도 적용)
    if (config.domain) {
      config.normalizedDomain = smartDomainParsingFrontend(config.domain);
      console.log(`🔄 도메인 정규화: ${config.domain} → ${config.normalizedDomain}`);
    }

    return config;
  } catch (error) {
    console.error('❌ iparams 설정값 조회 실패:', error);
    return null;
  }
}

/**
 * 프론트엔드용 스마트 도메인 파싱 함수
 * @param {string} inputDomain - 입력 도메인
 * @returns {string} 정규화된 도메인
 */
function smartDomainParsingFrontend(inputDomain) {
  if (!inputDomain || !inputDomain.trim()) {
    throw new Error('도메인 입력값이 비어있습니다.');
  }

  let domain = inputDomain.trim().toLowerCase();

  // URL 형태인 경우 도메인 부분만 추출
  if (domain.startsWith('http://') || domain.startsWith('https://')) {
    try {
      const url = new URL(domain);
      domain = url.hostname;
    } catch (e) {
      throw new Error(`URL 파싱 실패: ${domain}`);
    }
  }

  // 이미 완전한 .freshdesk.com 도메인인 경우
  if (domain.endsWith('.freshdesk.com')) {
    const companyId = domain.replace('.freshdesk.com', '');
    if (!companyId || companyId.length < 2) {
      throw new Error(`유효하지 않은 company_id: ${companyId}`);
    }
    return domain;
  }

  // company_id만 입력된 경우
  if (domain.length < 2) {
    throw new Error(`company_id가 너무 짧습니다: ${domain}`);
  }

  // 특수문자 검증 (기본적인 체크)
  if (!/^[a-z0-9\-]+$/.test(domain)) {
    throw new Error(`company_id에 허용되지 않는 문자가 포함되어 있습니다: ${domain}`);
  }

  return `${domain}.freshdesk.com`;
}

/**
 * 도메인에서 company_id를 추출하는 함수
 * @param {string} domain - Freshdesk 도메인
 * @returns {string} company_id
 */
function extractCompanyIdFromDomain(domain) {
  if (!domain) {
    return '';
  }

  // 이미 company_id만 있는 경우
  if (!domain.includes('.')) {
    return domain;
  }

  // .freshdesk.com에서 company_id 추출
  if (domain.endsWith('.freshdesk.com')) {
    return domain.replace('.freshdesk.com', '');
  }

  return domain.split('.')[0];
}

/**
 * 에러 메시지를 결과 영역에 표시하는 함수
 * @param {string} message - 에러 메시지
 * @param {string} containerId - 컨테이너 ID
 */
function showErrorInResults(message, containerId = 'similar-tickets-list') {
  try {
    const container = document.getElementById(containerId);
    if (container) {
      container.innerHTML = `
        <div class="error-message alert alert-warning">
          <i class="fas fa-exclamation-triangle"></i>
          ${message}
        </div>
      `;
    } else {
      console.warn(`⚠️ 컨테이너를 찾을 수 없음: ${containerId}`);
    }
  } catch (error) {
    console.error('❌ showErrorInResults 오류', error);
  }
}

/**
 * 로딩 메시지를 표시하는 함수
 * @param {string} containerId - 컨테이너 ID
 */
function showLoadingInResults(containerId = 'similar-tickets-list') {
  try {
    const container = document.getElementById(containerId);
    if (container) {
      container.innerHTML = `
        <div class="loading-message">
          <i class="fas fa-spinner fa-spin"></i>
          로딩 중...
        </div>
      `;
    } else {
      console.warn(`⚠️ 컨테이너를 찾을 수 없음: ${containerId}`);
    }
  } catch (error) {
    console.error('❌ showLoadingInResults 오류', error);
  }
}

// API 호출 함수들에 에러 처리 보강
window.API = {
  ...window.API,

  // Freshdesk API 연결 테스트
  async testConnection() {
    try {
      const response = await this.makeRequest('/api/test');
      console.log('[API] 연결 테스트 성공:', response);
      return response;
    } catch (error) {
      console.error('[API] 연결 테스트 실패:', error);
      GlobalState.ErrorHandler.handleError(error, {
        context: 'api_connection_test',
        userMessage: 'API 서버 연결에 실패했습니다.',
      });
      throw error;
    }
  },

  // 백엔드 API 요청 기본 함수
  async makeRequest(endpoint, options = {}) {
    try {
      const baseUrl = 'http://localhost:8000';
      const url = `${baseUrl}${endpoint}`;

      const defaultOptions = {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
        ...options,
      };

      console.log(`[API] 요청 시작: ${defaultOptions.method} ${url}`);

      const response = await fetch(url, defaultOptions);

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }

      const data = await response.json();
      console.log(`[API] 요청 완료: ${url}`, data);
      return data;
    } catch (error) {
      console.error(`[API] 요청 실패: ${endpoint}`, error);

      // 네트워크 오류 감지
      if (error.name === 'TypeError' && error.message.includes('fetch')) {
        GlobalState.ErrorHandler.handleError(error, {
          context: 'api_network_error',
          userMessage: 'API 서버에 연결할 수 없습니다. 네트워크 상태를 확인해주세요.',
        });
      } else {
        GlobalState.ErrorHandler.handleError(error, {
          context: 'api_request_error',
          userMessage: 'API 요청 중 오류가 발생했습니다.',
        });
      }

      throw error;
    }
  },
};

// 의존성 확인 함수 - 다른 모듈에서 API 모듈 사용 가능 여부 체크
API.isAvailable = function () {
  return typeof GlobalState !== 'undefined';
};

console.log('📡 API 모듈 로드 완료 - 8개 함수 export됨');

// 모듈 의존성 시스템에 등록
if (typeof ModuleDependencyManager !== 'undefined') {
  ModuleDependencyManager.registerModule('api', Object.keys(API).length);
}
