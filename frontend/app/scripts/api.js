/**
 * api.js
 * API 호출 및 데이터 통신 관련 함수
 * 백엔드 API 호출, 데이터 가져오기 등의 함수들이 포함됩니다.
 */

// 다른 모듈의 함수 사용 (변수 중복 방지를 위해 직접 참조)
// config.js에서 필요한 변수와 함수
// utils.js에서 필요한 함수들

// 전역 데이터 캐시 (init 엔드포인트에서 받은 데이터 저장)
let globalTicketData = {
  summary: null,
  similar_tickets: [],
  recommended_solutions: [], // kb_documents와 매핑됨
  cached_ticket_id: null,
  ticket_info: null, // 백엔드에서 받은 완전한 티켓 정보
  isLoading: false, // 중복 호출 방지 플래그
  lastLoadTime: null, // 마지막 로드 시간
};

/**
 * 백엔드 API에 요청을 보내는 기본 함수 (FDK 환경)
 * @param {string} endpoint - API 엔드포인트 경로 (예: '/init/123', '/query')
 * @param {Object} options - 추가 옵션 (method, body 등)
 * @param {Object} config - API 호출 설정 (도메인, API 키 등)
 * @returns {Promise<Object>} - API 응답 데이터
 */
async function callBackendAPI(endpoint, options = {}, config = {}) {
  let requestTemplate = 'backendApi'; // 기본값으로 초기화

  try {
    const envInfo = window.config?.getEnvironmentInfo() || { environment: "unknown" };
    console.log(`🌐 FDK API 요청 시작: ${endpoint}`, {
      environment: envInfo.environment,
      isNgrokTunnel: envInfo.isNgrokTunnel,
      hostname: envInfo.hostname,
      options,
      configKeys: Object.keys(config)
    });

    // Freshdesk 클라이언트 확인
    if (!client) {
      throw new Error('Freshdesk 클라이언트가 초기화되지 않았습니다.');
    }

    // HTTP 메소드 결정
    const method = options.method || 'GET';

    // 엔드포인트에 따른 적절한 요청 템플릿 결정
    requestTemplate = method === 'POST' ? 'backendApiPost' : 'backendApi';

    // 요청 파라미터 구성
    const backendUrl = config.backendUrl || '';
    const urlObj = backendUrl ? new URL(backendUrl) : null;

    const requestOptions = {
      context: {
        path: endpoint, // 전체 경로를 path로 전달
        backend_host: urlObj ? urlObj.host : '',
        backend_protocol: urlObj ? urlObj.protocol.replace(':', '') : 'https'
      }
    };

    // 환경별 헤더 설정 처리
    const freshdeskDomain = config.domain || config.freshdesk?.domain;
    const freshdeskApiKey = config.apiKey || config.freshdesk?.apiKey;

    if (freshdeskDomain && freshdeskApiKey) {
      requestOptions.context.freshdesk_domain = freshdeskDomain;
      requestOptions.context.freshdesk_api_key = freshdeskApiKey;
      console.log("✅ Freshdesk 인증 정보 설정 완료");
    } else {
      console.warn("⚠️ Freshdesk 인증 정보 누락:", {
        domain: !!freshdeskDomain,
        apiKey: !!freshdeskApiKey
      });
    }

    // POST 데이터가 있는 경우 body에 추가
    if (options.body) {
      requestOptions.body = typeof options.body === 'string' ? options.body : JSON.stringify(options.body);
    }

    console.log(`📡 FDK request.invokeTemplate 호출:`, {
      template: requestTemplate,
      context: {
        path: requestOptions.context.path,
        freshdesk_domain: requestOptions.context.freshdesk_domain || '❌ 미설정',
        freshdesk_api_key: requestOptions.context.freshdesk_api_key ? '***설정됨***' : '❌ 미설정',
        backend_host: requestOptions.context.backend_host || '❌ 미설정'
      },
      hasBody: !!requestOptions.body
    });

    // FDK request API 호출
    const response = await client.request.invokeTemplate(
      requestTemplate,
      requestOptions
    );

    console.log(`✅ FDK API 응답 성공: ${endpoint}`, {
      status: response.status || 'no status',
      hasData: !!response,
      responseKeys: response ? Object.keys(response) : []
    });

    return response;

  } catch (error) {
    console.error(`❌ FDK API 호출 실패: ${endpoint}`, {
      error: error.message,
      template: requestTemplate,
      config: config.environment || "unknown"
    });
    throw error;
  }
}

/**
 * 티켓 초기 데이터를 로드하는 함수 (/init 엔드포인트)
 * @param {string} ticketId - 티켓 ID
 * @param {Object} config - API 호출 설정
 * @returns {Promise<Object>} - 티켓 초기 데이터
 */
async function loadTicketInitData(ticketId, config) {
  // 이미 로딩 중이면 중복 호출 방지
  if (globalTicketData.isLoading) {
    console.log("⚠️ 이미 데이터를 로딩 중입니다. 대기합니다.");
    await new Promise(resolve => {
      const checkInterval = setInterval(() => {
        if (!globalTicketData.isLoading) {
          clearInterval(checkInterval);
          resolve();
        }
      }, 100);
    });

    // 이미 같은 티켓 데이터가 로드되었는지 확인
    if (globalTicketData.cached_ticket_id === ticketId) {
      return globalTicketData;
    }
  }

  try {
    // 로딩 상태 설정
    globalTicketData.isLoading = true;

    const endpoint = `/init/${ticketId}`;

    // 도메인 정규화
    let domain = config.domain || config.freshdesk?.domain;
    if (domain && window.utils?.smartDomainParsingFrontend) {
      domain = window.utils.smartDomainParsingFrontend(domain);
    }

    const apiConfig = {
      domain: domain,
      apiKey: config.apiKey || config.freshdesk?.apiKey,
      backendUrl: config.backendUrl,
    };

    console.log(`🔍 API 호출 설정값 확인:`, {
      domain: apiConfig.domain ? '✓ ' + apiConfig.domain : '❌ 미설정',
      apiKey: apiConfig.apiKey ? '✓ ***설정됨***' : '❌ 미설정',
      backendUrl: apiConfig.backendUrl ? '✓ ' + apiConfig.backendUrl : '❌ 미설정'
    });

    // API 요청 (FDK 방식)
    const data = await callBackendAPI(endpoint, { method: 'GET' }, apiConfig);

    // 전역 데이터 캐시 업데이트
    globalTicketData = {
      ...data,
      cached_ticket_id: ticketId,
      lastLoadTime: Date.now(),
      isLoading: false,
    };

    console.log("✅ 티켓 초기 데이터 로드 완료:", globalTicketData);
    return globalTicketData;
  } catch (error) {
    console.error("❌ 티켓 초기 데이터 로드 실패:", error);
    globalTicketData.isLoading = false;
    throw error;
  }
}

/**
 * 자연어 쿼리를 처리하는 함수 (/query 엔드포인트)
 * @param {Object} queryData - 쿼리 데이터
 * @param {string} queryData.query - 사용자 자연어 질문
 * @param {string} queryData.ticket_id - 티켓 ID
 * @param {Array<string>} queryData.type - 검색할 콘텐츠 타입
 * @param {Object} config - API 호출 설정
 * @returns {Promise<Object>} - 쿼리 응답 데이터
 */
async function sendQuery(queryData, config) {
  try {
    const endpoint = `/query`;

    // 도메인 정규화
    let domain = config.domain;
    if (domain && window.utils?.smartDomainParsingFrontend) {
      domain = window.utils.smartDomainParsingFrontend(domain);
    }

    const apiConfig = {
      domain: domain,
      apiKey: config.apiKey,
      backendUrl: config.backendUrl,
    };

    // API 요청 (FDK 방식)
    const data = await callBackendAPI(
      endpoint,
      {
        method: 'POST',
        body: queryData,
      },
      apiConfig
    );

    return data;
  } catch (error) {
    console.error("❌ 쿼리 요청 실패:", error);
    throw error;
  }
}

/**
 * 추천 답변 생성 함수 (/generate_reply 엔드포인트)
 * @param {Object} requestData - 요청 데이터
 * @param {string} requestData.ticket_id - 티켓 ID
 * @param {string} requestData.context - 추가 컨텍스트
 * @param {string} requestData.tone - 답변 톤
 * @param {boolean} requestData.include_solution_steps - 해결 단계 포함 여부
 * @param {Object} config - API 호출 설정
 * @returns {Promise<Object>} - 생성된 답변 데이터
 */
async function generateReply(requestData, config) {
  try {
    const endpoint = `/generate_reply`;

    // 도메인 정규화
    let domain = config.domain;
    if (domain && window.utils?.smartDomainParsingFrontend) {
      domain = window.utils.smartDomainParsingFrontend(domain);
    }

    const apiConfig = {
      domain: domain,
      apiKey: config.apiKey,
      backendUrl: config.backendUrl,
    };

    // API 요청
    const data = await callBackendAPI(
      endpoint,
      {
        method: 'POST',
        body: requestData,
      },
      apiConfig
    );

    return data;
  } catch (error) {
    console.error("❌ 답변 생성 요청 실패:", error);
    throw error;
  }
}

/**
 * 시스템 상태 확인 함수 (/health 엔드포인트)
 * @param {Object} config - API 호출 설정
 * @returns {Promise<Object>} - 시스템 상태 데이터
 */
async function checkSystemHealth(config) {
  try {
    const endpoint = `/health`;

    // API 요청
    const data = await callBackendAPI(endpoint, { method: 'GET' }, config);

    return data;
  } catch (error) {
    console.error("❌ 시스템 상태 확인 실패:", error);
    throw error;
  }
}

/**
 * 데이터 수집 시작 함수 (/ingest 엔드포인트)
 * @param {Object} ingestData - 수집 설정 데이터
 * @param {Array<string>} ingestData.data_types - 수집할 데이터 타입
 * @param {Object} ingestData.date_range - 날짜 범위
 * @param {number} ingestData.batch_size - 배치 크기
 * @param {Object} config - API 호출 설정
 * @returns {Promise<Object>} - 수집 작업 시작 응답
 */
async function startDataIngestion(ingestData, config) {
  try {
    const endpoint = `/ingest`;

    // 도메인 정규화
    let domain = config.domain;
    if (domain && window.utils?.smartDomainParsingFrontend) {
      domain = window.utils.smartDomainParsingFrontend(domain);
    }

    const apiConfig = {
      domain: domain,
      apiKey: config.apiKey,
      backendUrl: config.backendUrl,
    };

    // API 요청
    const data = await callBackendAPI(
      endpoint,
      {
        method: 'POST',
        body: ingestData,
      },
      apiConfig
    );

    return data;
  } catch (error) {
    console.error("❌ 데이터 수집 시작 실패:", error);
    throw error;
  }
}

// 전역 데이터 캐시 가져오기
function getGlobalTicketData() {
  return { ...globalTicketData };
}

// 전역 데이터 캐시 초기화
function resetGlobalTicketData() {
  globalTicketData = {
    summary: null,
    similar_tickets: [],
    recommended_solutions: [],
    cached_ticket_id: null,
    ticket_info: null,
    isLoading: false,
    lastLoadTime: null,
  };
}

// 전역 네임스페이스로 내보내기
window.api = {
  callBackendAPI,
  loadTicketInitData,
  sendQuery,
  generateReply,
  checkSystemHealth,
  startDataIngestion,
  getGlobalTicketData,
  resetGlobalTicketData,
};
