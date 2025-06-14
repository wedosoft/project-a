/**
 * app.js
 * 메인 앱 로직
 * 앱의 핵심 기능과 초기화, 이벤트 처리 등을 담당합니다.
 */

// 각 모듈의 함수/변수를 가져오기 (변수 중복 방지를 위해 직접 참조)
// config.js에서 가져오기
// api.js에서 가져오기
// ui.js에서 가져오기
// utils.js에서 가져오기

// 글로벌 변수
let client; // Freshdesk 앱 클라이언트
let isInitialized = false; // 중복 초기화 방지 플래그
let appConfig = null; // 앱 설정 객체

/**
 * 앱 초기화 함수
 * 페이지 로딩 시 자동으로 백엔드 데이터를 호출하고 캐싱합니다.
 */
async function initializeApp() {
  console.log("🎯 앱 초기화 시작");

  // 환경 정보 로깅 (디버깅용)
  if (typeof window.config?.getEnvironmentInfo === 'function') {
    const envInfo = window.config.getEnvironmentInfo();
    console.log("🌍 환경 정보:", envInfo);
  }

  if (isInitialized) {
    console.log("⚠️ 앱이 이미 초기화되었습니다.");
    return;
  }

  try {

    // Freshdesk 클라이언트 초기화
    console.log("🔗 Freshdesk 클라이언트 초기화");
    if (typeof app === 'undefined') {
      throw new Error("Freshdesk app 객체를 찾을 수 없습니다. FDK 환경에서 실행 중인지 확인해주세요.");
    }

    client = await app.initialized();
    console.log("✅ Freshdesk 앱 클라이언트 초기화 완료");

    // 앱 설정 초기화 (환경별 설정 처리)
    if (typeof window.config?.initializeConfig === 'function') {
      appConfig = await window.config.initializeConfig(client);
      console.log("✅ 앱 설정 초기화 완료:", {
        environment: appConfig?.environment || "unknown",
        domain: appConfig?.domain ? "✓ " + appConfig.domain : "✗ 미설정",
        backendUrl: appConfig?.backendUrl ? "✓ " + appConfig.backendUrl : "✗ 미설정"
      });
    } else {
      throw new Error("앱 설정을 초기화할 수 없습니다. config.js 파일을 확인해주세요.");
    }

    // 설정 검증
    if (!appConfig || !appConfig.backendUrl) {
      throw new Error("백엔드 URL이 설정되지 않았습니다. 관리자 설정을 확인해주세요.");
    }

    // DOM 요소 초기화
    setupDomElements();

    // 이벤트 리스너 등록
    registerEventListeners();

    // 백엔드 데이터 로드
    console.log("📊 백엔드 데이터 로드 시작");
    const ticketData = await loadCurrentTicketData();
    console.log("✅ 백엔드 데이터 로드 완료");

    // 티켓 정보 렌더링
    renderTicketInfo(ticketData);

    // 탭 데이터 프리로딩
    preloadAllTabData(ticketData);

    // 초기화 완료
    isInitialized = true;
    console.log("✅ 앱 초기화 완료");

    // 성공 알림
    if (typeof window.ui?.showNotification === 'function') {
      window.ui.showNotification("AI 지원 시스템이 준비되었습니다.", "success");
    }

  } catch (error) {
    console.error("❌ 앱 초기화 실패:", error);

    if (typeof window.ui?.showGlobalError === 'function') {
      window.ui.showGlobalError('데이터 로딩 오류: 페이지를 새로고침해 주세요.');
    } else if (typeof window.ui?.showError === 'function') {
      window.ui.showError('데이터 로딩 오류: 페이지를 새로고침해 주세요.');
    }
  }
}

/**
 * DOM 요소 설정 함수
 * 모든 DOM 요소와 이벤트 리스너를 설정합니다.
 */
function setupDomElements() {
  console.log("🔧 DOM 요소 초기화 중...");

  // 탭 클릭 이벤트 설정 (Bootstrap 탭 이벤트)
  const tabs = document.querySelectorAll('[data-bs-toggle="tab"]');
  tabs.forEach(tab => {
    tab.addEventListener('shown.bs.tab', function(e) {
      const targetPaneId = e.target.getAttribute('data-bs-target');
      console.log(`🔄 탭 전환됨: ${targetPaneId}`);
      handleTabSwitch(targetPaneId);
    });
  });

  // 유사 티켓 탭 버튼 이벤트
  const refreshSimilarTicketsBtn = document.getElementById('refresh-similar-tickets');
  if (refreshSimilarTicketsBtn) {
    refreshSimilarTicketsBtn.addEventListener('click', async () => {
      console.log("🔄 유사 티켓 새로고침 버튼 클릭");
      await refreshSimilarTicketsData();
    });
  }

  // 추천 솔루션 탭 버튼 이벤트
  const refreshSolutionsBtn = document.getElementById('refresh-solutions');
  if (refreshSolutionsBtn) {
    refreshSolutionsBtn.addEventListener('click', async () => {
      console.log("🔄 추천 솔루션 새로고침 버튼 클릭");
      await refreshSolutionsData();
    });
  }

  // 채팅 관련 이벤트
  const chatSearchButton = document.getElementById('chat-search-button');
  const chatInput = document.getElementById('chat-input');
  const clearChatBtn = document.getElementById('clear-chat');

  if (chatSearchButton && chatInput) {
    chatSearchButton.addEventListener('click', async () => {
      await handleChatQuery();
    });

    chatInput.addEventListener('keypress', async (e) => {
      if (e.key === 'Enter') {
        await handleChatQuery();
      }
    });
  }

  if (clearChatBtn) {
    clearChatBtn.addEventListener('click', () => {
      clearChatHistory();
    });
  }

  // 백 버튼 이벤트
  const backToSimilarListBtn = document.getElementById('back-to-similar-list');
  const backToSolutionsListBtn = document.getElementById('back-to-solutions-list');

  if (backToSimilarListBtn) {
    backToSimilarListBtn.addEventListener('click', () => {
      document.getElementById('similar-tickets-detail-view').style.display = 'none';
      document.getElementById('similar-tickets-list-view').style.display = 'block';
    });
  }

  if (backToSolutionsListBtn) {
    backToSolutionsListBtn.addEventListener('click', () => {
      document.getElementById('solutions-detail-view').style.display = 'none';
      document.getElementById('solutions-list-view').style.display = 'block';
    });
  }

  console.log("✅ DOM 요소 초기화 완료");
}

/**
 * 이벤트 리스너 등록 함수
 * Freshdesk 앱 이벤트만 등록합니다.
 */
function registerEventListeners() {
  console.log("🔧 Freshdesk 이벤트 리스너 등록 중...");

  // Freshdesk 앱 이벤트 리스너
  client.events.on('app.activated', () => {
    console.log("🔄 앱 활성화 이벤트 발생 (재호출 없음)");
  });

  client.events.on('ticket.propertiesUpdated', () => {
    console.log("🔄 티켓 속성 변경 이벤트 발생 (재호출 없음)");
  });

  console.log("✅ Freshdesk 이벤트 리스너 등록 완료");
}

/**
 * 전체 데이터 새로고침 함수
 */
async function refreshAllData() {
  console.log("🔄 전체 데이터 새로고침 중...");

  try {
    showQuickLoadingIndicator();

    // 백엔드에서 최신 데이터 가져오기
    const ticketData = await loadCurrentTicketData();

    // 티켓 정보 업데이트
    renderTicketInfo(ticketData);

    // 현재 활성 탭에 따라 해당 데이터만 업데이트
    const activeTab = document.querySelector('.nav-link.active');
    if (activeTab) {
      const targetPaneId = activeTab.getAttribute('data-bs-target');
      handleTabSwitch(targetPaneId);
    }

    showNotification("데이터가 새로고침되었습니다.", "success");
  } catch (error) {
    console.error("❌ 전체 데이터 새로고침 실패:", error);
    showError("데이터 새로고침 중 오류가 발생했습니다.");
  } finally {
    hideQuickLoadingIndicator();
  }
}

/**
 * 현재 티켓 정보 로드 함수
 * @returns {Promise<Object>} - 티켓 데이터
 */
async function loadCurrentTicketData() {
  console.log("⏳ 현재 티켓 정보 로드 중...");

  try {
    // 현재 티켓 ID 가져오기
    const context = await client.data.get("ticket");
    const ticketId = context.ticket.id;
    console.log("🎫 현재 티켓 ID:", ticketId);

    // 백엔드에서 티켓 데이터 가져오기
    const ticketData = await loadTicketInitData(ticketId, appConfig);
    return ticketData;
  } catch (error) {
    console.error("❌ 티켓 정보 로드 실패:", error);
    throw error;
  }
}

/**
 * 티켓 정보 렌더링 함수 (상단 카드만)
 * @param {Object} ticketData - 백엔드에서 받은 티켓 데이터
 */
function renderTicketInfo(ticketData) {
  console.log("🎨 티켓 정보 렌더링 중...");

  if (!ticketData || !ticketData.ticket_info) {
    console.warn("⚠️ 렌더링할 티켓 정보가 없습니다.");
    return;
  }

  const ticketInfo = ticketData.ticket_info;

  // 상단 티켓 정보 카드 업데이트
  const subjectElement = document.getElementById('ticket-subject');
  const statusElement = document.getElementById('ticket-status');
  const priorityElement = document.getElementById('ticket-priority');
  const typeElement = document.getElementById('ticket-type');

  if (subjectElement) subjectElement.textContent = ticketInfo.subject || '제목 없음';
  if (statusElement) statusElement.textContent = getStatusText(ticketInfo.status) || '상태 정보 없음';
  if (priorityElement) priorityElement.textContent = getPriorityText(ticketInfo.priority) || '우선순위 정보 없음';
  if (typeElement) typeElement.textContent = ticketInfo.type || '유형 정보 없음';

  console.log("✅ 티켓 정보 렌더링 완료");
}

/**
 * 모든 탭 데이터 미리 로드 함수
 * 모달 창을 열기 전에 모든 데이터를 미리 준비해둡니다.
 * @param {Object} ticketData - 백엔드에서 받은 전체 티켓 데이터
 */
function preloadAllTabData(ticketData) {
  console.log("📦 모든 탭 데이터 사전 로딩 중...");

  try {
    // 유사 티켓 데이터 준비
    if (ticketData.similar_tickets && ticketData.similar_tickets.length > 0) {
      console.log(`✅ 유사 티켓 ${ticketData.similar_tickets.length}개 준비 완료`);
      // 실제 렌더링은 탭이 활성화될 때 수행
      // 여기서는 데이터가 준비되었다는 것만 확인
    } else {
      console.log("⚠️ 유사 티켓 데이터가 없습니다.");
    }

    // 추천 솔루션 데이터 준비
    if (ticketData.recommended_solutions && ticketData.recommended_solutions.length > 0) {
      console.log(`✅ 추천 솔루션 ${ticketData.recommended_solutions.length}개 준비 완료`);
    } else {
      console.log("⚠️ 추천 솔루션 데이터가 없습니다.");
    }

    // 채팅 탭 초기화 (웰컴 메시지 등)
    initializeChatTab();

    console.log("✅ 모든 탭 데이터 사전 로딩 완료");
  } catch (error) {
    console.error("❌ 탭 데이터 사전 로딩 실패:", error);
  }
}

/**
 * 탭 전환 핸들러
 * 이미 로드된 데이터를 사용하여 즉시 렌더링합니다.
 * @param {string} targetPaneId - 활성화된 탭 패널 ID
 */
function handleTabSwitch(targetPaneId) {
  console.log(`🔄 탭 전환 처리: ${targetPaneId}`);

  const ticketData = getGlobalTicketData();

  switch (targetPaneId) {
    case '#similar-tickets':
      if (ticketData && ticketData.similar_tickets) {
        renderSimilarTickets(ticketData.similar_tickets);
      } else {
        console.warn("⚠️ 유사 티켓 데이터가 없습니다.");
        document.getElementById('similar-tickets-list').innerHTML =
          '<div class="placeholder-text">유사 티켓 데이터가 없습니다.</div>';
      }
      break;

    case '#suggested-solutions':
      if (ticketData && ticketData.recommended_solutions) {
        renderRecommendedSolutions(ticketData.recommended_solutions);
      } else {
        console.warn("⚠️ 추천 솔루션 데이터가 없습니다.");
        document.getElementById('suggested-solutions-list').innerHTML =
          '<div class="placeholder-text">추천 솔루션 데이터가 없습니다.</div>';
      }
      break;

    case '#copilot':
      // 채팅 탭은 이미 초기화되어 있음
      console.log("💬 채팅 탭 활성화");
      break;

    default:
      console.log(`🔄 알 수 없는 탭: ${targetPaneId}`);
  }
}

/**
 * 유사 티켓 데이터 새로고침 함수
 */
async function refreshSimilarTicketsData() {
  console.log("🔄 유사 티켓 데이터 새로고침 중...");

  try {
    showQuickLoadingIndicator();

    // 현재 티켓 데이터 다시 로드
    const ticketData = await loadCurrentTicketData();

    // 유사 티켓만 다시 렌더링
    if (ticketData && ticketData.similar_tickets) {
      renderSimilarTickets(ticketData.similar_tickets);
      showNotification("유사 티켓이 새로고침되었습니다.", "success");
    }
  } catch (error) {
    console.error("❌ 유사 티켓 새로고침 실패:", error);
    showError("유사 티켓 새로고침 중 오류가 발생했습니다.");
  } finally {
    hideQuickLoadingIndicator();
  }
}

/**
 * 추천 솔루션 데이터 새로고침 함수
 */
async function refreshSolutionsData() {
  console.log("🔄 추천 솔루션 데이터 새로고침 중...");

  try {
    showQuickLoadingIndicator();

    // 현재 티켓 데이터 다시 로드
    const ticketData = await loadCurrentTicketData();

    // 추천 솔루션만 다시 렌더링
    if (ticketData && ticketData.recommended_solutions) {
      renderRecommendedSolutions(ticketData.recommended_solutions);
      showNotification("추천 솔루션이 새로고침되었습니다.", "success");
    }
  } catch (error) {
    console.error("❌ 추천 솔루션 새로고침 실패:", error);
    showError("추천 솔루션 새로고침 중 오류가 발생했습니다.");
  } finally {
    hideQuickLoadingIndicator();
  }
}

/**
 * 채팅 쿼리 처리 함수
 */
async function handleChatQuery() {
  const chatInput = document.getElementById('chat-input');
  const query = chatInput.value.trim();

  if (!query) {
    showNotification("질문을 입력해 주세요.", "warning");
    return;
  }

  console.log("💬 채팅 쿼리 처리:", query);

  try {
    // 사용자 메시지 추가
    addChatMessage(query, 'user');

    // 입력창 초기화
    chatInput.value = '';

    // 로딩 메시지 추가
    const loadingMsgId = addChatMessage("답변을 생성하고 있습니다...", 'assistant', true);

    // 선택된 검색 옵션 가져오기
    const searchTypes = getSelectedSearchTypes();

    // 백엔드 쿼리 API 호출
    const response = await sendQuery({
      query: query,
      content_types: searchTypes,
      ticket_context: getTicketContext()
    }, appConfig);

    // 로딩 메시지 제거
    removeChatMessage(loadingMsgId);

    // AI 응답 추가
    addChatMessage(response.message || "답변을 생성할 수 없습니다.", 'assistant');

  } catch (error) {
    console.error("❌ 채팅 쿼리 처리 실패:", error);
    addChatMessage("죄송합니다. 오류가 발생했습니다.", 'assistant');
  }
}

/**
 * 선택된 검색 타입 가져오기
 */
function getSelectedSearchTypes() {
  const searchTypes = [];

  if (document.getElementById('search-tickets').checked) searchTypes.push('tickets');
  if (document.getElementById('search-solutions').checked) searchTypes.push('solutions');
  if (document.getElementById('search-images').checked) searchTypes.push('images');
  if (document.getElementById('search-attachments').checked) searchTypes.push('attachments');

  return searchTypes;
}

/**
 * 채팅 메시지 추가 함수
 */
function addChatMessage(message, sender, isLoading = false) {
  const chatContainer = document.getElementById('chat-messages');
  const messageId = `msg-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

  const messageElement = document.createElement('div');
  messageElement.className = `chat-message ${sender}`;
  messageElement.id = messageId;

  if (isLoading) {
    messageElement.classList.add('loading-message');
  }

  messageElement.innerHTML = `<strong>${sender === 'user' ? '상담원' : 'AI'}:</strong> ${message}`;

  chatContainer.appendChild(messageElement);
  chatContainer.scrollTop = chatContainer.scrollHeight;

  return messageId;
}

/**
 * 채팅 메시지 제거 함수
 */
function removeChatMessage(messageId) {
  const messageElement = document.getElementById(messageId);
  if (messageElement) {
    messageElement.remove();
  }
}

/**
 * 채팅 히스토리 초기화 함수
 */
function clearChatHistory() {
  const chatContainer = document.getElementById('chat-messages');
  chatContainer.innerHTML = '';

  // 초기 안내 메시지 다시 추가
  addChatMessage("안녕하세요! 이 티켓에 대해 어떤 도움이 필요하신가요?", 'assistant');

  showNotification("채팅 기록이 초기화되었습니다.", "info");
}

/**
 * 채팅 탭 초기화 함수
 */
function initializeChatTab() {
  console.log("� 채팅 탭 초기화 중...");

  const chatContainer = document.getElementById('chat-messages');
  if (!chatContainer) {
    console.warn("⚠️ 채팅 컨테이너를 찾을 수 없습니다.");
    return;
  }

  // 채팅 기록 초기화
  chatContainer.innerHTML = '';

  // 초기 안내 메시지 추가
  addChatMessage("안녕하세요! 이 티켓에 대해 어떤 도움이 필요하신가요?", 'assistant');

  console.log("✅ 채팅 탭 초기화 완료");
}

/**
 * 티켓 컨텍스트 가져오기 (API 요청 시 사용)
 * @returns {Object} 티켓 컨텍스트
 */
function getTicketContext() {
  const ticketData = getGlobalTicketData();

  if (!ticketData) {
    console.warn("⚠️ 글로벌 티켓 데이터가 없습니다.");
    return {
      ticket_id: '',
      ticket_subject: '',
      ticket_description: '',
      include_context: true
    };
  }

  // 필요한 티켓 정보만 추출하여 반환
  return {
    ticket_id: ticketData.cached_ticket_id || '',
    ticket_subject: ticketData.ticket_info?.subject || '',
    ticket_description: ticketData.ticket_info?.description || '',
    include_context: true
  };
}

// 디버깅을 위한 로그
console.log("📄 app.js 스크립트 로드됨");
console.log("🌍 현재 환경:", {
  hostname: window.location.hostname,
  pathname: window.location.pathname,
  protocol: window.location.protocol,
  userAgent: navigator.userAgent.substring(0, 100) + "..."
});

// DOM 로딩 상태 체크 및 단일 초기화
function attemptInitialization() {
  if (document.readyState === 'interactive' || document.readyState === 'complete') {
    console.log("🎯 DOM 로드 완료 (interactive 또는 complete), 앱 초기화 시도");
    if (!window.isAppInitialized) { // 중복 실행 방지 플래그
        window.initializeApp();
        window.isAppInitialized = true; // 초기화 플래그 설정
    }
  } else {
    console.log("📋 DOM 아직 로딩 중, 대기...");
  }
}

document.addEventListener('DOMContentLoaded', function() {
  console.log("🎯 DOMContentLoaded 이벤트 발생, 앱 초기화 시도");
  if (!window.isAppInitialized) { // 중복 실행 방지 플래그
    window.initializeApp();
    window.isAppInitialized = true; // 초기화 플래그 설정
  }
});

// 스크립트 로드 시점에도 체크 (DOMContentLoaded가 이미 발생했을 수 있음)
attemptInitialization();

// 앱 초기화 함수를 글로벌 스코프에 노출
window.initializeApp = initializeApp;

// 수동 초기화를 위한 글로벌 함수 (개발용)
window.debugInitialize = function() {
  console.log("🛠️ 수동 초기화 실행");
  isInitialized = false; // app.js 내부의 isInitialized 플래그도 리셋
  window.isAppInitialized = false; // 글로벌 플래그도 리셋
  initializeApp();
  window.isAppInitialized = true;
};
