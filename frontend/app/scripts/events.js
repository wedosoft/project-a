/**
 * 이벤트 핸들러 모듈 (Events)
 *
 * Freshdesk Custom App - Prompt Canvas
 * 이 파일은 app.js에서 분리된 모든 이벤트 핸들러와 관련 함수들을 포함합니다.
 *
 * 주요 기능:
 * - 프롬프트 전송 및 응답 처리 이벤트
 * - 모달 창 열기/닫기 이벤트
 * - 키보드 단축키 (Enter) 이벤트
 * - 버튼 상태 관리 및 UI 피드백
 * - 에러 처리 및 사용자 경험 개선
 *
 * 의존성:
 * - GlobalState: 전역 상태 및 에러 핸들러
 * - UI: UI 조작 및 피드백 표시
 * - Data: 데이터 처리 및 API 호출
 *
 * @namespace Events
 * @author Freshdesk Custom App Team
 * @since 1.0.0
 */

/**
 * 이벤트 핸들러 관련 함수들
 * Freshdesk Custom App - Prompt Canvas
 *
 * 이 파일은 app.js에서 분리된 모든 이벤트 핸들러와 관련 함수들을 포함합니다.
 * 탭 이벤트, 버튼 클릭 이벤트, 키보드 이벤트 등을 관리합니다.
 */

// Events 모듈 정의 - 모든 이벤트 관련 함수를 하나의 객체로 관리
window.Events = {
  /**
   * 프롬프트 전송 이벤트 핸들러
   *
   * 사용자가 입력한 프롬프트를 서버로 전송하고 응답을 처리합니다.
   * UI 상태 관리, 에러 처리, 사용자 피드백을 포함합니다.
   *
   * @param {Event} event - 이벤트 객체 (submit 또는 click 이벤트)
   * @returns {Promise<void>} 비동기 처리 완료
   *
   * @example
   * // 버튼 클릭 시 직접 호출
   * Events.handleSendPrompt(clickEvent);
   *
   * // Enter 키 처리 시 호출
   * Events.handleSendPrompt(keyEvent);
   */
  async handleSendPrompt(event) {
    try {
      if (event) {
        event.preventDefault();
      }

      console.log('[EVENTS] 프롬프트 전송 이벤트 처리 시작');

      const promptInput = UI.safeGetElement('#prompt-input');
      if (!promptInput) {
        throw new Error('프롬프트 입력 필드를 찾을 수 없습니다.');
      }

      const prompt = promptInput.value?.trim();
      if (!prompt) {
        UI.showToast('프롬프트를 입력해주세요.', 'warning');
        return;
      }

      // UI 비활성화
      this.setSubmitButtonState(false);
      UI.showToast('처리 중...', 'info');

      try {
        const response = await Data.sendPrompt(prompt);

        if (response && response.content) {
          UI.showModal(response.content);
          UI.showToast('응답이 생성되었습니다.', 'success');
          promptInput.value = ''; // 입력 필드 클리어
        } else {
          throw new Error('응답 데이터가 올바르지 않습니다.');
        }
      } finally {
        // UI 재활성화
        this.setSubmitButtonState(true);
      }
    } catch (error) {
      console.error('[EVENTS] 프롬프트 전송 처리 실패:', error);
      GlobalState.ErrorHandler.handleError(error, {
        module: 'events',
        function: 'handleSendPrompt',
        context: 'prompt_submission',
        severity: 'error',
        userMessage: '프롬프트 처리 중 오류가 발생했습니다. 다시 시도해 주세요.',
      });

      // UI 재활성화
      this.setSubmitButtonState(true);
    }
  },

  /**
   * 전송 버튼 상태 설정
   *
   * 프롬프트 처리 중 버튼을 비활성화하고 텍스트를 변경하여
   * 사용자에게 처리 상태를 명확히 전달합니다.
   *
   * @param {boolean} enabled - 버튼 활성화 여부 (true: 활성화, false: 비활성화)
   *
   * @example
   * // 처리 시작 시 버튼 비활성화
   * Events.setSubmitButtonState(false);
   *
   * // 처리 완료 시 버튼 재활성화
   * Events.setSubmitButtonState(true);
   */
  setSubmitButtonState(enabled) {
    try {
      const submitButton = UI.safeGetElement('#submit-prompt');
      if (submitButton) {
        submitButton.disabled = !enabled;
        submitButton.textContent = enabled ? '전송' : '처리 중...';
      }
    } catch (error) {
      console.error('[EVENTS] 버튼 상태 설정 오류:', error);
    }
  },

  /**
   * 모달 창 닫기 이벤트 핸들러
   *
   * 사용자가 모달 창을 닫기 버튼이나 배경 클릭으로 닫을 때 호출됩니다.
   * 안전한 DOM 조작과 에러 처리를 포함합니다.
   *
   * @param {Event} event - 클릭 이벤트 객체
   *
   * @example
   * // 닫기 버튼 클릭 시
   * Events.handleCloseModal(clickEvent);
   *
   * // 배경 클릭 시
   * Events.handleCloseModal(backgroundClickEvent);
   */
  handleCloseModal(event) {
    try {
      if (event) {
        event.preventDefault();
      }

      console.log('[EVENTS] 모달 닫기 이벤트 처리');

      const modal = UI.safeGetElement('#response-modal');
      if (modal) {
        modal.style.display = 'none';
        console.log('[EVENTS] 모달 닫기 완료');
      }
    } catch (error) {
      console.error('[EVENTS] 모달 닫기 처리 실패:', error);
      GlobalState.ErrorHandler.handleError(error, {
        module: 'events',
        function: 'handleCloseModal',
        context: 'modal_close',
        severity: 'warning',
        userMessage: '모달 창을 닫는 중 오류가 발생했습니다.',
      });
    }
  },

  /**
   * 모든 이벤트 리스너 등록
   *
   * 앱 초기화 시 필요한 모든 이벤트 리스너를 등록합니다.
   * 각 DOM 요소의 존재 여부를 확인하고 안전하게 이벤트를 바인딩합니다.
   *
   * 등록되는 이벤트:
   * - 프롬프트 전송 버튼 클릭
   * - 모달 닫기 버튼 클릭
   * - 모달 배경 클릭 (모달 외부 클릭으로 닫기)
   * - Enter 키 입력 (Shift+Enter는 제외, 줄바꿈 허용)
   *
   * @returns {void}
   *
   * @example
   * // 앱 초기화 시 호출
   * Events.setupEventListeners();
   */
  setupEventListeners() {
    try {
      console.log('[EVENTS] 이벤트 리스너 등록 시작');

      // 프롬프트 전송 버튼
      const submitButton = UI.safeGetElement('#submit-prompt');
      if (submitButton) {
        submitButton.addEventListener('click', (e) => this.handleSendPrompt(e));
        console.log('[EVENTS] 전송 버튼 이벤트 등록 완료');
      } else {
        console.warn('[EVENTS] 전송 버튼을 찾을 수 없음');
      }

      // 모달 닫기 버튼
      const closeButton = UI.safeGetElement('#close-modal');
      if (closeButton) {
        closeButton.addEventListener('click', (e) => this.handleCloseModal(e));
        console.log('[EVENTS] 모달 닫기 버튼 이벤트 등록 완료');
      }

      // 모달 배경 클릭
      const modal = UI.safeGetElement('#response-modal');
      if (modal) {
        modal.addEventListener('click', (e) => {
          if (e.target === modal) {
            this.handleCloseModal(e);
          }
        });
        console.log('[EVENTS] 모달 배경 클릭 이벤트 등록 완료');
      }

      // Enter 키 처리
      const promptInput = UI.safeGetElement('#prompt-input');
      if (promptInput) {
        promptInput.addEventListener('keypress', (e) => {
          if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            this.handleSendPrompt(e);
          }
        });
        console.log('[EVENTS] 프롬프트 입력 키 이벤트 등록 완료');
      }

      console.log('[EVENTS] 모든 이벤트 리스너 등록 완료');
    } catch (error) {
      console.error('[EVENTS] 이벤트 리스너 등록 실패:', error);
      GlobalState.ErrorHandler.handleError(error, {
        module: 'events',
        function: 'setupEventListeners',
        context: 'event_listener_setup',
        severity: 'critical',
        userMessage: '이벤트 처리 설정 중 오류가 발생했습니다. 페이지를 새로고침해 주세요.',
      });
    }
  },

  /**
   * 탭 이벤트 설정
   *
   * 각 탭(유사 티켓, 추천 해결책, Copilot)의 클릭 이벤트를 설정하고
   * 탭별 컨텐츠 로딩 함수를 연결합니다.
   *
   * @param {Object} client - Freshdesk client 객체
   *
   * @example
   * Events.setupTabEvents(app.client);
   */
  setupTabEvents(client) {
    const tabs = document.querySelectorAll('[role="tab"]');
    tabs.forEach((tab) => {
      tab.addEventListener('click', function () {
        const tabId = this.id;
        const targetPanel = this.getAttribute('data-bs-target').substring(1);

        console.log(`📂 탭 클릭: ${tabId} targeting panel: ${targetPanel}`);

        // 탭에 따른 적절한 함수 호출
        switch (tabId) {
          case 'similar-tickets-tab':
            this.handleSimilarTicketsTab(client);
            break;
          case 'suggested-solutions-tab':
            this.handleSuggestedSolutionsTab(client);
            break;
          case 'copilot-tab':
            this.handleCopilotTab(client);
            break;
        }
      });
    });

    // 각 탭의 버튼 이벤트 설정
    this.setupSimilarTicketsEvents(client);
    this.setupSuggestedSolutionsEvents(client);
    this.setupCopilotEvents(client);
  },

  // 유사 티켓 탭 처리 함수
  async handleSimilarTicketsTab(client) {
    console.log('🔍 유사 티켓 탭 활성화');

    // 리스트 뷰로 초기화
    showSimilarTicketsListView();

    try {
      // 현재 티켓 데이터 가져오기
      const ticketData = await client.data.get('ticket');

      if (ticketData && ticketData.ticket) {
        const ticket = ticketData.ticket;

        // 캐시된 데이터가 있고 같은 티켓인 경우 재사용
        if (
          globalTicketData.cached_ticket_id === ticket.id &&
          globalTicketData.similar_tickets.length > 0
        ) {
          console.log('🔄 캐시된 유사 티켓 데이터 사용');
          displaySimilarTickets(globalTicketData.similar_tickets);
        } else {
          // 캐시된 데이터가 없거나 다른 티켓인 경우 백엔드에서 로드
          await loadSimilarTicketsFromBackend(ticket);
        }
      }
    } catch (error) {
      console.error('❌ 유사 티켓 로드 오류:', error);
      showErrorInResultsInResults('유사 티켓을 로드할 수 없습니다.', 'similar-tickets-list');
    }
  },

  // 유사 티켓 이벤트 설정 함수
  setupSimilarTicketsEvents(client) {
    // 새로고침 버튼 - 공통 함수 사용
    this.setupRefreshButton(
      'refresh-similar-tickets',
      'similar_tickets',
      API.loadSimilarTicketsFromBackend,
      client
    );

    // 뒤로가기 버튼 - 공통 함수 사용
    this.setupBackButton('back-to-similar-list', UI.showSimilarTicketsListView);

    // 티켓 열기 버튼
    const openTicketButton = document.getElementById('open-ticket-link');
    if (openTicketButton) {
      openTicketButton.addEventListener('click', () => {
        const currentTicketId = openTicketButton.dataset.ticketId;
        if (currentTicketId) {
          window.open(`https://${window.location.host}/a/tickets/${currentTicketId}`, '_blank');
        }
      });
    }
  },

  // 추천 해결책 탭 처리 함수
  async handleSuggestedSolutionsTab(client) {
    console.log('💡 추천 솔루션 탭 활성화');

    // 리스트 뷰로 초기화
    showSuggestedSolutionsListView();

    try {
      // 현재 티켓 데이터 가져오기
      const ticketData = await client.data.get('ticket');

      if (ticketData && ticketData.ticket) {
        const ticket = ticketData.ticket;

        // 캐시된 데이터가 있고 같은 티켓인 경우 재사용
        if (
          globalTicketData.cached_ticket_id === ticket.id &&
          globalTicketData.recommended_solutions.length > 0
        ) {
          console.log('🔄 캐시된 추천 솔루션 데이터 사용');
          displaySuggestedSolutions(globalTicketData.recommended_solutions);
        } else {
          // 캐시된 데이터가 없거나 다른 티켓인 경우 백엔드에서 로드
          await loadSuggestedSolutions(ticket);
        }
      }
    } catch (error) {
      console.error('❌ 추천 해결책 로드 오류:', error);
      showErrorInResultsInResults('추천 해결책을 로드할 수 없습니다.', 'suggested-solutions-list');
    }
  },

  // 추천 솔루션 이벤트 설정 함수
  setupSuggestedSolutionsEvents(client) {
    // 새로고침 버튼 - 공통 함수 사용
    this.setupRefreshButton(
      'refresh-solutions',
      'recommended_solutions',
      Data.loadSuggestedSolutions,
      client
    );

    // 뒤로가기 버튼 - 공통 함수 사용
    this.setupBackButton('back-to-solutions-list', UI.showSuggestedSolutionsListView);

    // 솔루션 사용 버튼
    const useSolutionButton = document.getElementById('use-solution');
    if (useSolutionButton) {
      useSolutionButton.addEventListener('click', () => {
        const solutionData = useSolutionButton.dataset.solution;
        if (solutionData) {
          try {
            const solution = JSON.parse(solutionData);
            UI.insertSolutionToReply(solution);
          } catch (error) {
            console.error('❌ 솔루션 데이터 파싱 오류:', error);
          }
        }
      });
    }
  },

  // 코파일럿 탭 처리 함수
  handleCopilotTab(client) {
    console.log('🤖 코파일럿 탭 활성화');

    // 코파일럿 이벤트가 이미 설정되어 있는지 확인하고, 없으면 설정
    if (!window.copilotEventsSetup) {
      this.setupCopilotEvents(client);
      window.copilotEventsSetup = true;
    }
  },

  // 코파일럿 이벤트 설정 함수
  setupCopilotEvents(client) {
    const searchButton = document.getElementById('chat-search-button');
    const searchInput = document.getElementById('chat-input');
    const clearChatButton = document.getElementById('clear-chat');

    if (searchButton) {
      searchButton.addEventListener('click', async function () {
        const query = searchInput.value.trim();

        // 선택된 콘텐츠 타입 가져오기
        const selectedTypes = [];
        if (document.getElementById('search-tickets')?.checked) selectedTypes.push('tickets');
        if (document.getElementById('search-solutions')?.checked) selectedTypes.push('solutions');
        if (document.getElementById('search-images')?.checked) selectedTypes.push('images');
        if (document.getElementById('search-attachments')?.checked)
          selectedTypes.push('attachments');

        if (query) {
          console.log('🤖 코파일럿 검색 실행:', query, '타입:', selectedTypes);
          await performCopilotSearch(client, query, selectedTypes);

          // 입력 필드 초기화
          searchInput.value = '';
        } else {
          showErrorInResultsInResults('질문을 입력해주세요.', 'chat-messages');
        }
      });
    }

    // Enter 키 지원
    if (searchInput) {
      searchInput.addEventListener('keypress', function (e) {
        if (e.key === 'Enter') {
          e.preventDefault();
          searchButton.click();
        }
      });
    }

    // 채팅 초기화 버튼
    if (clearChatButton) {
      clearChatButton.addEventListener('click', function () {
        const chatMessages = document.getElementById('chat-messages');
        if (chatMessages) {
          chatMessages.innerHTML = `
            <div class="chat-message assistant">
              <strong>AI:</strong> 안녕하세요! 이 티켓에 대해 어떤 도움이 필요하신가요?
            </div>
          `;
        }
        console.log('🧹 채팅 기록 초기화');
      });
    }
  },

  // 코파일럿 검색 실행 함수
  async performCopilotSearch(client, query, contentTypes) {
    const resultsElement = document.getElementById('chat-messages');
    if (!resultsElement) return;

    // 사용자 메시지 추가
    const userMessage = document.createElement('div');
    userMessage.className = 'chat-message user';
    userMessage.innerHTML = `<strong>질문:</strong> ${query}`;
    resultsElement.appendChild(userMessage);

    // 로딩 메시지 추가
    const loadingMessage = document.createElement('div');
    loadingMessage.className = 'chat-message assistant';
    loadingMessage.innerHTML =
      '<div class="loading"><div class="spinner"></div><span>AI가 답변을 생성하는 중입니다...</span></div>';
    resultsElement.appendChild(loadingMessage);

    // 스크롤을 맨 아래로
    resultsElement.scrollTop = resultsElement.scrollHeight;

    try {
      // 현재 티켓 정보 가져오기
      const ticketData = await client.data.get('ticket');

      const requestData = {
        intent: 'search',
        type: contentTypes,
        query: query,
        ticket_id: ticketData?.ticket?.id || null,
      };

      // FDK를 통한 백엔드 /query API 호출 (POST 메서드로 데이터 전송)
      const response = await callBackendAPI(client, 'query', requestData, 'POST');

      // 로딩 메시지 제거
      resultsElement.removeChild(loadingMessage);

      if (response.ok) {
        const data = response.data;
        displayCopilotResults(data, resultsElement);
      } else {
        console.error('❌ 코파일럿 API 응답 오류:', response.status);
        const errorMessage = document.createElement('div');
        errorMessage.className = 'chat-message assistant';
        errorMessage.innerHTML = '<strong>오류:</strong> AI 응답을 가져올 수 없습니다.';
        resultsElement.appendChild(errorMessage);
      }
    } catch (error) {
      console.error('❌ 코파일럿 연결 오류:', error);
      // 로딩 메시지 제거
      if (resultsElement.contains(loadingMessage)) {
        resultsElement.removeChild(loadingMessage);
      }

      const errorMessage = document.createElement('div');
      errorMessage.className = 'chat-message assistant';
      errorMessage.innerHTML = '<strong>오류:</strong> AI 서비스에 연결할 수 없습니다.';
      resultsElement.appendChild(errorMessage);
    }

    // 스크롤을 맨 아래로
    resultsElement.scrollTop = resultsElement.scrollHeight;
  },

  // 코파일럿 컨텍스트 가져오기 함수
  async getCopilotContext(client) {
    try {
      const ticketData = await client.data.get('ticket');
      return {
        ticket: ticketData.ticket,
        timestamp: new Date().toISOString(),
      };
    } catch (error) {
      console.error('❌ 컨텍스트 가져오기 오류:', error);
      return {};
    }
  },

  // 코파일럿 결과 표시 함수
  displayCopilotResults(data, resultsElement) {
    if (!resultsElement) resultsElement = document.getElementById('chat-messages');
    if (!resultsElement) return;

    const assistantMessage = document.createElement('div');
    assistantMessage.className = 'chat-message assistant';

    if (data.answer || data.response) {
      let content = `<strong>AI 답변:</strong><br>${data.answer || data.response}`;

      // 검색 결과가 있는 경우 추가 표시
      if (data.results && data.results.length > 0) {
        content += '<br><br><strong>관련 정보:</strong><ul>';
        data.results.forEach((result, index) => {
          if (index < 3) {
            // 상위 3개만 표시
            content += `<li><strong>${
              result.title || result.subject || `항목 ${index + 1}`
            }</strong><br>
                     <small>${result.excerpt || result.description || '내용 없음'}</small></li>`;
          }
        });
        content += '</ul>';
      }

      // 참고 자료가 있는 경우
      if (data.sources && data.sources.length > 0) {
        content += '<br><strong>참고 자료:</strong><ul>';
        data.sources.forEach((source) => {
          content += `<li><a href="${source.url}" target="_blank">${source.title}</a></li>`;
        });
        content += '</ul>';
      }

      assistantMessage.innerHTML = content;
    } else {
      assistantMessage.innerHTML = '<strong>AI:</strong> 죄송합니다. 답변을 생성할 수 없습니다.';
    }

    resultsElement.appendChild(assistantMessage);

    // 스크롤을 맨 아래로
    resultsElement.scrollTop = resultsElement.scrollHeight;

    console.log('✅ 코파일럿 결과 표시 완료');
  },

  /**
   * 공통 새로고침 버튼 이벤트 설정
   *
   * 각 탭의 새로고침 버튼에 공통 이벤트 핸들러를 설정합니다.
   * 버튼 클릭 시 해당 데이터를 다시 로드하고 UI를 업데이트합니다.
   *
   * @param {string} buttonId - 새로고침 버튼의 DOM ID
   * @param {string} dataType - 로드할 데이터 타입 (캐시 키)
   * @param {Function} loadFunction - 데이터 로드 함수
   * @param {Object} client - Freshdesk client 객체
   */
  setupRefreshButton(buttonId, dataType, loadFunction, client) {
    const refreshButton = document.getElementById(buttonId);
    if (refreshButton) {
      refreshButton.addEventListener('click', async () => {
        console.log(`🔄 ${dataType} 새로고침 - 캐시 초기화`);

        try {
          const ticketData = await client.data.get('ticket');
          if (ticketData && ticketData.ticket) {
            // 캐시에서 해당 데이터 타입만 초기화
            const globalData = GlobalState.getGlobalTicketData();
            if (globalData[dataType]) {
              globalData[dataType] = [];
              GlobalState.updateGlobalTicketData(globalData);
            }

            // 데이터 다시 로드
            await loadFunction(ticketData.ticket);
          }
        } catch (error) {
          console.error(`❌ ${dataType} 새로고침 실패:`, error);
          GlobalState.ErrorHandler.handleError(error, {
            context: `refresh_${dataType}`,
            userMessage: '데이터 새로고침 중 오류가 발생했습니다.',
          });
        }
      });
    }
  },

  /**
   * 공통 뒤로가기 이벤트 핸들러
   * 중복되는 뒤로가기 로직을 통합하여 코드 재사용성을 높입니다.
   * @param {string} buttonId - 뒤로가기 버튼 ID
   * @param {Function} showListFunction - 목록을 보여줄 함수
   */
  setupBackButton(buttonId, showListFunction) {
    const backButton = document.getElementById(buttonId);
    if (backButton) {
      backButton.addEventListener('click', () => {
        try {
          showListFunction();
        } catch (error) {
          console.error(`❌ 뒤로가기 처리 실패 (${buttonId}):`, error);
          GlobalState.ErrorHandler.handleError(error, {
            context: 'navigation_back',
            userMessage: '화면 이동 중 오류가 발생했습니다.',
          });
        }
      });
    }
  },

  /**
   * 이벤트 리스너 최적화 관리
   */
  eventListeners: new Map(),

  /**
   * 최적화된 이벤트 리스너 추가
   * 자동 정리 및 중복 방지 기능 포함
   */
  addOptimizedEventListener(element, eventType, handler, options = {}) {
    const { debounce = false, throttle = false, once = false, passive = true } = options;

    let optimizedHandler = handler;

    // 디바운스 적용
    if (debounce) {
      const delay = typeof debounce === 'number' ? debounce : 300;
      optimizedHandler = window.PerformanceOptimizer.debounce(handler, delay);
    }

    // 스로틀 적용
    if (throttle) {
      const limit = typeof throttle === 'number' ? throttle : 100;
      optimizedHandler = window.PerformanceOptimizer.throttle(handler, limit);
    }

    const listenerKey = `${element.id || 'unnamed'}-${eventType}`;

    // 기존 리스너 제거 (중복 방지)
    if (this.eventListeners.has(listenerKey)) {
      const oldListener = this.eventListeners.get(listenerKey);
      element.removeEventListener(eventType, oldListener.handler);
    }

    // 새 리스너 등록
    const listenerOptions = { once, passive, ...options };
    element.addEventListener(eventType, optimizedHandler, listenerOptions);

    // 리스너 추적
    this.eventListeners.set(listenerKey, {
      element,
      eventType,
      handler: optimizedHandler,
      options: listenerOptions,
    });

    console.log(`[이벤트] 최적화된 리스너 등록: ${listenerKey}`);
  },

  /**
   * 모든 이벤트 리스너 정리
   */
  cleanupEventListeners() {
    for (const [key, listener] of this.eventListeners.entries()) {
      try {
        listener.element.removeEventListener(listener.eventType, listener.handler);
      } catch (error) {
        console.warn(`[이벤트] 리스너 제거 실패: ${key}`, error);
      }
    }
    this.eventListeners.clear();
    console.log('[이벤트] 모든 이벤트 리스너가 정리되었습니다.');
  },

  /**
   * 이벤트 위임 설정
   * 동적으로 추가되는 요소에 대한 효율적인 이벤트 처리
   */
  setupEventDelegation(container, selector, eventType, handler, options = {}) {
    const delegatedHandler = (e) => {
      const target = e.target.closest(selector);
      if (target) {
        handler.call(target, e);
      }
    };

    this.addOptimizedEventListener(container, eventType, delegatedHandler, options);
  },

  /**
   * 향상된 새로고침 버튼 설정
   */
  setupOptimizedRefreshButton() {
    const refreshBtn = this.getDOMElement('#refresh-btn');
    if (!refreshBtn) {
      console.warn('[이벤트] 새로고침 버튼을 찾을 수 없습니다.');
      return;
    }

    this.addOptimizedEventListener(
      refreshBtn,
      'click',
      async (e) => {
        e.preventDefault();

        try {
          // 버튼 비활성화로 중복 클릭 방지
          refreshBtn.disabled = true;
          refreshBtn.textContent = '새로고침 중...';

          // 캐시 무효화 및 데이터 갱신
          if (window.API) {
            window.API.clearCache();
          }

          // 글로벌 데이터 초기화
          window.GlobalState.resetGlobalTicketCache();

          // UI 새로고침
          if (window.UI) {
            await window.UI.refreshMainView();
          }

          console.log('[이벤트] 데이터 새로고침 완료');
        } catch (error) {
          window.ErrorHandler.handleError(error, {
            context: 'refresh_button',
            userMessage: '데이터 새로고침 중 오류가 발생했습니다.',
          });
        } finally {
          // 버튼 복원
          refreshBtn.disabled = false;
          refreshBtn.textContent = '새로고침';
        }
      },
      {
        debounce: 1000, // 1초 디바운스로 중복 클릭 방지
      }
    );
  },

  /**
   * 최적화된 검색 입력 필드 설정
   */
  setupOptimizedSearchInput() {
    const searchInput = this.getDOMElement('#search-input');
    if (!searchInput) return;

    // 스마트 검색 설정
    if (window.UI && window.UI.setupSmartSearch) {
      window.UI.setupSmartSearch(
        searchInput,
        async (query) => {
          if (window.Data && window.Data.searchTickets) {
            const results = await window.Data.searchTickets(query);
            if (window.UI && window.UI.renderOptimizedTicketList) {
              const container = this.getDOMElement('#tickets-list');
              if (container) {
                await window.UI.renderOptimizedTicketList(results, container);
              }
            }
          }
        },
        {
          debounceMs: 300,
          minLength: 2,
          placeholder: '티켓 검색... (최소 2글자)',
        }
      );
    }
  },

  /**
   * 무한 스크롤 설정
   */
  setupInfiniteScroll(container, loadMoreCallback, options = {}) {
    const { threshold = 100, batchSize = 20 } = options;

    let isLoading = false;

    const scrollHandler = window.PerformanceOptimizer.throttle(async () => {
      if (isLoading) return;

      const { scrollTop, scrollHeight, clientHeight } = container;
      const distanceToBottom = scrollHeight - scrollTop - clientHeight;

      if (distanceToBottom < threshold) {
        isLoading = true;

        try {
          const hasMore = await loadMoreCallback(batchSize);
          if (!hasMore) {
            // 더 이상 로드할 데이터가 없으면 스크롤 리스너 제거
            container.removeEventListener('scroll', scrollHandler);
          }
        } catch (error) {
          window.ErrorHandler.handleError(error, {
            context: 'infinite_scroll',
            userMessage: '추가 데이터 로드 중 오류가 발생했습니다.',
          });
        } finally {
          isLoading = false;
        }
      }
    }, 100);

    this.addOptimizedEventListener(container, 'scroll', scrollHandler, { passive: true });
  },

  /**
   * 키보드 단축키 설정
   */
  setupKeyboardShortcuts() {
    const shortcuts = {
      r: () => this.getDOMElement('#refresh-btn')?.click(), // R키로 새로고침
      '/': () => this.getDOMElement('#search-input')?.focus(), // /키로 검색 포커스
      Escape: () => {
        // ESC키로 모달 닫기 및 검색 초기화
        const searchInput = this.getDOMElement('#search-input');
        if (searchInput && document.activeElement === searchInput) {
          searchInput.value = '';
          searchInput.blur();
        }
      },
    };

    this.addOptimizedEventListener(document, 'keydown', (e) => {
      // 입력 필드에서는 단축키 비활성화
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
        if (e.key !== 'Escape') return;
      }

      const handler = shortcuts[e.key];
      if (handler) {
        e.preventDefault();
        handler();
      }
    });
  },

  /**
   * 성능 모니터링 이벤트 설정
   */
  setupPerformanceMonitoring() {
    // 페이지 가시성 변경 감지
    this.addOptimizedEventListener(document, 'visibilitychange', () => {
      if (document.hidden) {
        console.log('[성능] 페이지가 백그라운드로 이동');
        // 불필요한 작업 일시 중단
        if (window.DebugTools && window.DebugTools.pausePeriodicChecks) {
          window.DebugTools.pausePeriodicChecks();
        }
      } else {
        console.log('[성능] 페이지가 다시 활성화됨');
        // 작업 재개
        if (window.DebugTools && window.DebugTools.resumePeriodicChecks) {
          window.DebugTools.resumePeriodicChecks();
        }
      }
    });

    // 메모리 부족 경고 감지
    this.addOptimizedEventListener(window, 'beforeunload', () => {
      this.cleanupEventListeners();
      if (window.PerformanceOptimizer) {
        window.PerformanceOptimizer.performMemoryCleanup();
      }
    });
  },

  /**
   * 의존성 확인 함수
   *
   * Events 모듈이 정상적으로 사용 가능한지 확인합니다.
   * 필요한 의존성 모듈들의 로드 상태를 검사합니다.
   *
   * @returns {boolean} 모듈 사용 가능 여부
   */
  isAvailable: function () {
    try {
      const dependencies = {
        GlobalState: typeof GlobalState !== 'undefined' && !!GlobalState.ErrorHandler,
        UI: typeof UI !== 'undefined' && typeof UI.showToast === 'function',
        Data: typeof Data !== 'undefined' && typeof Data.sendPrompt === 'function',
      };

      const availableDeps = Object.entries(dependencies).filter(([, available]) => available);
      const missingDeps = Object.entries(dependencies).filter(([, available]) => !available);

      if (missingDeps.length > 0) {
        console.warn(
          '[EVENTS] 누락된 의존성:',
          missingDeps.map(([key]) => key)
        );
      }

      return availableDeps.length >= 2; // 최소 2개 이상의 의존성이 충족되어야 함
    } catch (error) {
      console.error('[EVENTS] 의존성 확인 중 오류:', error);
      return false;
    }
  },
};

console.log('🎭 Events 모듈 로드 완료 - 9개 함수 export됨');

// 모듈 의존성 시스템에 등록 (ui, data 모듈에 의존)
if (typeof ModuleDependencyManager !== 'undefined') {
  ModuleDependencyManager.registerModule('events', Object.keys(Events).length, ['ui', 'data']);
}
