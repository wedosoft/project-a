/**
 * Chat UI Module - 단순화된 채팅 인터페이스
 */

window.ChatUI = {
  isComposing: false,
  // 스크롤 상태 관리
  scrollState: {
    userScrolledUp: false,
    lastScrollTop: 0,
    scrollCheckTimer: null,
    isFirstStreamChunk: false
  },

  /**
   * 초기화
   */
  init() {
    this.setupEventListeners();
    this.setupScrollButton();

    // 초기 UI 설정
    const currentMode = window.Core?.state?.chatMode || 'rag';
    this.updateModeUI(currentMode);
    this.updateInputPlaceholder(currentMode);
  },

  /**
   * 이벤트 리스너 설정
   */
  setupEventListeners() {
    const chatInput = document.getElementById('chatInput');
    const sendButton = document.getElementById('sendButton');
    const chatResults = document.getElementById('chatResults');

    if (chatInput) {
      chatInput.addEventListener('keydown', (e) => this.handleChatKeydown(e));
      chatInput.addEventListener('input', (e) => this.adjustTextareaHeight(e.target));
      chatInput.addEventListener('compositionstart', () => this.handleCompositionStart());
      chatInput.addEventListener('compositionend', () => this.handleCompositionEnd());
    }

    if (sendButton) {
      sendButton.addEventListener('click', () => this.sendMessage());
    }

    // 채팅 컨테이너 스크롤 이벤트 리스너
    if (chatResults) {
      chatResults.addEventListener('scroll', (e) => this.handleScrollEvent(e));
    }
  },

  /**
   * 스크롤 버튼 설정
   */
  setupScrollButton() {
    const container = document.getElementById('chatResults');
    const scrollBtn = document.getElementById('scrollToBottomBtn');

    if (container && scrollBtn) {
      container.addEventListener('scroll', () => {
        const isAtBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 100;
        scrollBtn.style.display = isAtBottom ? 'none' : 'flex';
      });
    }
  },

  /**
   * 메시지 추가
   */
  addMessage(content, role) {
    const container = document.getElementById('chatResults');
    if (!container) return;

    // 통합 캐시에 저장
    window.Core.saveModalData();

    const messageId = `msg-${Date.now()}-${role}`;
    const messageHtml = `
      <div class="chat-message ${role}" id="${messageId}">
        <div class="message-avatar">${role === 'user' ? '👤' : '🤖'}</div>
        <div class="message-content">
          <div class="message-text">${this._parseContent(content)}</div>
          <div class="message-time" data-timestamp="${Date.now()}">${this._formatTime()}</div>
        </div>
      </div>
    `;

    container.insertAdjacentHTML('beforeend', messageHtml);

    // DOM 업데이트 완료 후 부드러운 스크롤
    requestAnimationFrame(() => {
      this.scrollToBottom();
    });

    return messageId;
  },

  /**
   * 검색 결과 카드 렌더링
   */
  renderSearchCards(results) {
    const container = document.getElementById('chatResults');
    if (!container || !results || results.length === 0) return;

    const cardsHtml = `
      <div class="chat-message assistant">
        <div class="message-avatar">🤖</div>
        <div class="message-content">
          <div class="search-cards">
            ${results.map(item => this._createSearchCard(item)).join('')}
          </div>
          <div class="message-time" data-timestamp="${Date.now()}">${this._formatTime()}</div>
        </div>
      </div>
    `;

    container.insertAdjacentHTML('beforeend', cardsHtml);
    this.scrollToBottom();
  },

  /**
   * 개별 검색 카드 생성 (심플한 바 형태)
   */
  _createSearchCard(item) {
    // 백엔드 데이터 구조 지원: payload 기반 데이터 추출
    const payload = item.payload || item;
    const metadata = item.metadata || {};

    // 타입 결정
    const docType = payload.doc_type || payload.type || metadata.doc_type || 'document';
    const icon = docType === 'ticket' ? '🎫' : '📄';

    // ID 추출 (여러 소스에서 시도) - original_id 우선
    const ticketId = payload.original_id || item.original_id || payload.id || item.id || 'UNKNOWN';

    // 제목 추출 (여러 필드에서 시도) - 더 많은 필드 확인
    const title = payload.title || payload.subject || item.title || item.subject ||
      payload.description || item.description ||
      payload.content || item.content || '제목 없음';

    // 스코어 변환 (0~1 범위를 0~100%로)
    const rawScore = item.score || item.relevance_score || 0;
    const score = Math.round(rawScore * 100);

    // URL 생성 또는 추출
    let url = payload.url || item.url || '#';
    if (docType === 'ticket' && ticketId && url === '#') {
      url = `/a/tickets/${ticketId}`;
    } else if (docType === 'ticket' && url.includes('/tickets/') && !url.includes('/a/tickets/')) {
      url = url.replace('/tickets/', '/a/tickets/');
    }

    return `
      <a href="${url}" target="_blank" class="search-result-bar">
        <span class="result-icon">${icon}</span>
        <span class="result-id">#${ticketId}</span>
        <span class="result-title">${title}</span>
        <span class="result-score">${score}%</span>
      </a>
    `;
  },

  /**
   * 참고자료 카드 생성 (얇은 카드 형식)
   */
  _createReferenceCard(item) {
    const icon = item.type === 'ticket' ? '🎫' : '📄';
    const itemId = this._extractItemId(item);
    const title = this._extractItemTitle(item);
    const url = this._buildItemUrl(item, itemId);
    const displayText = this._formatDisplayText(item, itemId, title);

    return `
      <a href="${url}" target="_blank" class="reference-card-link">
        <div class="reference-card-simple">
          <span class="ref-icon">${icon}</span>
          <span class="ref-text">${displayText}</span>
        </div>
      </a>
    `;
  },

  /**
   * 아이템 ID 추출
   */
  _extractItemId(item) {
    if (item.type === 'ticket') {
      return this._extractTicketId(item);
    } else {
      return this._extractKbId(item);
    }
  },

  /**
   * 티켓 ID 추출
   */
  _extractTicketId(item) {
    return this._extractOriginalId(item) ||
      this._extractFromMetadata(item) ||
      this._extractFromPlatformMetadata(item) ||
      this._extractFromUrl(item) ||
      this._extractFromTitle(item) ||
      '티켓';
  },

  /**
   * original_id에서 티켓 ID 추출
   */
  _extractOriginalId(item) {
    if (item.original_id && !isNaN(item.original_id)) {
      return `#${item.original_id}`;
    }
    return null;
  },

  /**
   * metadata에서 티켓 ID 추출
   */
  _extractFromMetadata(item) {
    if (!item.metadata) {
      return null;
    }

    const ticketId = this._findTicketIdInObject(item.metadata);
    return this._formatTicketId(ticketId);
  },

  /**
   * 객체에서 티켓 ID 찾기
   */
  _findTicketIdInObject(obj) {
    const idFields = ['original_id', 'ticket_id', 'id', 'ticket_number', 'number'];

    for (const field of idFields) {
      if (obj[field]) {
        return obj[field];
      }
    }

    return null;
  },

  /**
   * 티켓 ID 포맷팅
   */
  _formatTicketId(ticketId) {
    if (ticketId && !isNaN(ticketId)) {
      return `#${ticketId}`;
    }
    return null;
  },

  /**
   * platform_metadata에서 티켓 ID 추출
   */
  _extractFromPlatformMetadata(item) {
    if (!item.platform_metadata) {
      return null;
    }

    const ticketId = this._findTicketIdInObject(item.platform_metadata);
    return this._formatTicketId(ticketId);
  },

  /**
   * URL에서 티켓 ID 추출
   */
  _extractFromUrl(item) {
    if (!item.url) {
      return null;
    }

    const match = item.url.match(/tickets\/(\d+)/);
    if (match) {
      return `#${match[1]}`;
    }

    return null;
  },

  /**
   * 제목에서 티켓 ID 추출
   */
  _extractFromTitle(item) {
    const titleText = item.title || item.metadata?.subject || '';
    const match = titleText.match(/#(\d+)/);

    if (match) {
      return `#${match[1]}`;
    }

    return null;
  },

  /**
   * KB 문서 ID 추출
   */
  _extractKbId(item) {
    // 1. id 필드 확인
    if (item.id && !isNaN(item.id)) {
      return `#${item.id}`;
    }

    // 2. metadata에서 찾기
    if (item.metadata) {
      const articleId = item.metadata.article_id ||
        item.metadata.id ||
        item.metadata.solution_id ||
        item.metadata.kb_id ||
        item.metadata.number;
      if (articleId && !isNaN(articleId)) {
        return `#${articleId}`;
      }
    }

    // 3. URL에서 추출
    if (item.url) {
      const patterns = [
        /articles\/(\d+)/,
        /solutions\/(\d+)/,
        /kb\/(\d+)/,
        /knowledge-base\/(\d+)/
      ];

      for (const pattern of patterns) {
        const match = item.url.match(pattern);
        if (match) {
          return `#${match[1]}`;
        }
      }
    }

    return '아티클';
  },

  /**
   * 아이템 제목 추출
   */
  _extractItemTitle(item) {
    let title;

    if (item.type === 'ticket') {
      title = item.title || item.metadata?.subject || item.metadata?.title || '제목 없음';

      // 불필요한 prefix 제거
      title = title
        .replace(/^설명:\s*/i, '')
        .replace(/^Ticket\s*/i, '')
        .replace(/^문의\s*/i, '')
        .replace(/^제목:\s*/i, '')
        .trim();
    } else {
      title = item.title || item.metadata?.title || '문서';
    }

    return title;
  },

  /**
   * 아이템 URL 생성
   */
  _buildItemUrl(item, itemId) {
    // 기본 URL
    let url = item.url || '#';

    // 티켓의 경우 Freshdesk URL 생성
    if (item.type === 'ticket' && itemId && itemId !== '티켓') {
      const ticketId = itemId.replace('#', '');
      const domain = window.Core?.config?.domain || '';
      if (domain && ticketId) {
        url = `https://${domain}/a/tickets/${ticketId}`;
      }
    }

    return url;
  },

  /**
   * 표시 텍스트 포맷팅
   */
  _formatDisplayText(item, itemId, title) {
    if (item.type === 'ticket') {
      // 티켓번호와 제목을 함께 표시
      if (itemId && itemId !== '티켓' && title && title !== '제목 없음') {
        return `${itemId}, ${title}`;
      } else if (itemId && itemId !== '티켓') {
        return itemId;
      } else if (title && title !== '제목 없음') {
        return `티켓, ${title}`;
      } else {
        return '티켓';
      }
    } else {
      // KB 문서는 제목만 표시
      return title;
    }
  },

  /**
   * 메시지 업데이트 (스트리밍)
   */
  updateMessage(messageId, content, isComplete = false) {
    const messageText = document.querySelector(`#${messageId} .message-text`);
    if (!messageText) return;

    messageText.innerHTML = this._parseContent(content);

    if (!isComplete) {
      messageText.classList.add('streaming');
    } else {
      messageText.classList.remove('streaming');
    }
  },

  /**
   * 스트리밍 메시지 업데이트 - 검색 결과 통합 (상세 카드 형식)
   */
  updateStreamingMessage(content, searchResults = null) {
    // 검색 결과 확인

    const messages = document.querySelectorAll('.chat-message.assistant');
    const lastMessage = messages[messages.length - 1];

    if (lastMessage) {
      const messageContent = lastMessage.querySelector('.message-content');
      if (messageContent) {
        let html = '';

        // 검색 결과가 있으면 상세 카드 형식으로 표시
        if (searchResults && searchResults.length > 0) {
          html += `<div class="search-cards">
            ${searchResults.map(item => this._createSearchCard(item)).join('')}
          </div>`;
        }

        // AI 응답 표시
        html += `<div class="message-text streaming">${this._parseContent(content)}</div>`;
        html += `<div class="message-time" data-timestamp="${Date.now()}">${this._formatTime()}</div>`;

        messageContent.innerHTML = html;

        // 스트리밍 중 자동 스크롤 (DOM 업데이트 완료 후)
        requestAnimationFrame(() => {
          this.autoScrollDuringStreaming();
        });
      }
    }
  },

  /**
   * 메시지 완료 처리
   */
  finalizeMessage(messageId) {
    const selector = messageId ? `#${messageId} .message-text.streaming` : '.message-text.streaming';
    const messages = document.querySelectorAll(selector);
    messages.forEach(msg => msg.classList.remove('streaming'));
  },

  /**
   * 메시지 전송
   */
  async sendMessage() {
    const input = document.getElementById('chatInput');
    const query = input.value.trim();

    if (!query) return;

    // 입력창 초기화
    input.value = '';
    this.adjustTextareaHeight(input);

    // 메시지 처리
    await this.handleSendMessage(query);
  },

  /**
   * 타이핑 인디케이터 표시
   */
  showTypingIndicator() {
    const container = document.getElementById('chatResults');
    if (!container) return;

    const typingHtml = `
      <div class="typing-indicator" id="typingIndicator">
        <div class="message-avatar">🤖</div>
        <div class="typing-dots">
          <span class="typing-dot"></span>
          <span class="typing-dot"></span>
          <span class="typing-dot"></span>
        </div>
      </div>
    `;

    container.insertAdjacentHTML('beforeend', typingHtml);

    // DOM 업데이트 완료 후 부드러운 스크롤
    requestAnimationFrame(() => {
      this.scrollToBottom();
    });
  },

  /**
   * 타이핑 인디케이터 숨김
   */
  hideTypingIndicator() {
    const indicator = document.getElementById('typingIndicator');
    if (indicator) {
      indicator.remove();
    }
  },

  /**
   * 메시지 전송 처리
   */
  async handleSendMessage(query) {
    // 사용자 메시지 추가
    this.addMessage(query, 'user');
    window.Core.addChatHistory('user', query);

    // 메시지 카운트 업데이트
    this.updateModeUI(window.Core.state.chatMode);

    // 타이핑 인디케이터 표시
    this.showTypingIndicator();

    // 스트리밍 시작 상태 초기화
    this.onStreamingStart();

    try {
      const ticketId = window.Core.state.ticketId;
      const mode = window.Core.state.chatMode;


      const fullResponse = await window.ApiService.sendChatQuery(ticketId, query, mode);

      // 스트리밍이 완료되면 히스토리에만 추가 (UI는 이미 업데이트됨)
      window.Core.addChatHistory('assistant', fullResponse);

      // 메시지 카운트 업데이트
      this.updateModeUI(mode);

      // 모달에서 채팅 완료 시 상태 저장
      if (window.Core?.state?.isModalView) {
        window.Core.autoSaveState();
      }

    } catch (error) {
      console.error('채팅 오류:', error);
      // 사용자에게 알림 표시
      if (window.NotificationBanner) {
        window.NotificationBanner.error(window.t ? window.t('error_chat_processing') : 'An error occurred while processing chat.');
      }
      // 타이핑 인디케이터 제거
      this.hideTypingIndicator();
      // 에러 메시지 추가 (다국어 지원)
      this.addMessage(window.t ? window.t('error_message') : '죄송합니다. 오류가 발생했습니다.', 'assistant');
    }
  },


  /**
   * 스크롤 최하단으로
   */
  scrollToBottom() {
    const container = document.getElementById('chatResults');
    if (container) {
      // 부드러운 스크롤로 최하단 이동
      container.scrollTo({
        top: container.scrollHeight,
        behavior: 'smooth'
      });

      // 스크롤 상태 업데이트
      this.scrollState.lastScrollTop = container.scrollHeight;
      this.scrollState.userScrolledUp = false;
    }
  },

  /**
   * 스크롤 이벤트 핸들러 - 사용자 스크롤 의도 감지
   */
  handleScrollEvent(event) {
    const container = event.target;
    const currentScrollTop = container.scrollTop;
    const maxScrollTop = container.scrollHeight - container.clientHeight;
    const isAtBottom = maxScrollTop - currentScrollTop < 10;

    // 사용자가 수동으로 위로 스크롤했는지 감지
    if (currentScrollTop < this.scrollState.lastScrollTop - 5) {
      this.scrollState.userScrolledUp = true;
      // 사용자가 위로 스크롤함 - 자동 스크롤 일시 정지
    }
    // 사용자가 하단으로 돌아왔으면 자동 스크롤 재개
    else if (isAtBottom && this.scrollState.userScrolledUp) {
      this.scrollState.userScrolledUp = false;
      // 사용자가 하단으로 복귀 - 자동 스크롤 재개
    }

    this.scrollState.lastScrollTop = currentScrollTop;
  },

  /**
   * 사용자 스크롤 의도 감지
   */
  detectUserScrollIntent() {
    return this.scrollState.userScrolledUp;
  },

  /**
   * 스트리밍 중 강제 자동 스크롤 (항상 최신 응답 표시)
   * 사용자 요청에 따라 항상 자동 스크롤하도록 개선
   */
  autoScrollDuringStreaming() {
    const container = document.getElementById('chatResults');
    if (!container) return;

    // 컨테이너 높이가 변경되었는지 확인
    const newScrollHeight = container.scrollHeight;
    const currentScrollTop = container.scrollTop;
    const containerHeight = container.clientHeight;

    // 이미 최하단에 있거나 스트리밍 중이면 자동 스크롤
    const isNearBottom = (newScrollHeight - currentScrollTop - containerHeight) < 100;
    const shouldAutoScroll = this.scrollState.isFirstStreamChunk || isNearBottom || !this.scrollState.userScrolledUp;

    if (shouldAutoScroll) {
      // 부드러운 스크롤로 최하단으로 이동
      container.scrollTo({
        top: newScrollHeight,
        behavior: 'smooth'
      });

      // 스크롤 상태 업데이트
      this.scrollState.lastScrollTop = newScrollHeight;
      this.scrollState.userScrolledUp = false;
    }

    // 첫 번째 청크 플래그 해제
    this.scrollState.isFirstStreamChunk = false;
  },

  /**
   * 스트리밍 시작 시 호출 - 첫 번째 청크 플래그 설정
   */
  onStreamingStart() {
    this.scrollState.isFirstStreamChunk = true;
    this.scrollState.userScrolledUp = false;
  },

  /**
   * 텍스트 영역 높이 조정
   */
  adjustTextareaHeight(textarea) {
    textarea.style.height = 'auto';
    textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
  },

  /**
   * 키보드 이벤트 처리
   */
  handleChatKeydown(event) {
    if (event.key === 'Enter' && !event.shiftKey && !this.isComposing) {
      event.preventDefault();
      this.sendMessage();
    }
  },

  /**
   * IME 입력 시작
   */
  handleCompositionStart() {
    this.isComposing = true;
  },

  /**
   * IME 입력 종료
   */
  handleCompositionEnd() {
    this.isComposing = false;
  },

  /**
   * 채팅 모드 전환
   */
  toggleChatMode() {
    const currentMode = window.Core.state.chatMode;
    const newMode = currentMode === 'rag' ? 'chat' : 'rag';

    // 채팅 모드 토글

    // 모드 전환 (세션 저장/복원 포함)
    window.Core.setChatMode(newMode);

    // UI 업데이트
    this.updateModeUI(newMode);

    // 토글 애니메이션 업데이트
    if (window.updateChatToggleUI) {
      window.updateChatToggleUI();
    }

    // 모드 전환 시 해당 모드의 히스토리 렌더링 (토글 효과)
    this.renderChatHistory();

    // 언어 설정 다시 적용 (인사말 번역을 위해)
    if (window.I18nManager && window.I18nManager.updateUI) {
      window.I18nManager.updateUI();
    }

    // 입력창 플레이스홀더 업데이트
    this.updateInputPlaceholder(newMode);

    // 모달에서 채팅 모드 변경 시 상태 저장
    if (window.Core?.state?.isModalView) {
      window.Core.autoSaveState();
    }

    // 모드 토글 완료
  },

  /**
   * 모드 UI 업데이트 (레이블 및 메시지 카운트 표시)
   */
  updateModeUI(mode) {
    const toggle = document.querySelector('.ios-toggle');
    const modeIndicator = document.getElementById('modeIndicator');

    if (toggle) {
      toggle.classList.toggle('chat-mode', mode === 'chat');
    }

    if (modeIndicator) {
      // 각 모드의 메시지 수 가져오기
      const ragCount = window.Core.state.chatHistory.rag?.length || 0;
      const chatCount = window.Core.state.chatHistory.chat?.length || 0;

      // 모드 레이블과 메시지 카운트 표시
      if (mode === 'chat') {
        modeIndicator.innerHTML = `💬 일반 대화 ${chatCount > 0 ? `<span style="font-size: 0.8em; opacity: 0.7">(${chatCount})</span>` : ''}`;
      } else {
        modeIndicator.innerHTML = `📚 문서 검색 ${ragCount > 0 ? `<span style="font-size: 0.8em; opacity: 0.7">(${ragCount})</span>` : ''}`;
      }
    }
  },

  /**
   * 입력창 플레이스홀더 업데이트
   */
  updateInputPlaceholder(mode) {
    const chatInput = document.getElementById('chatInput');
    if (chatInput) {
      if (mode === 'chat') {
        const placeholder = window.t ? window.t('chat_placeholder_general') : 'Chat freely with AI...';
        chatInput.placeholder = placeholder;
      } else {
        const placeholder = window.t ? window.t('chat_placeholder_document') : 'Enter what you want to search in documents...';
        chatInput.placeholder = placeholder;
      }
    }
  },

  /**
   * 헬퍼 함수들
   */
  _parseContent(content) {
    if (typeof marked !== 'undefined') {
      try {
        return marked.parse(content);
      } catch (e) {
        console.error('Markdown 파싱 오류:', e);
      }
    }
    return content;
  },

  _formatTime() {
    const now = new Date();
    const locale = window.I18nManager ? window.I18nManager.getLocale() : 'ko-KR';
    return now.toLocaleTimeString(locale, {
      hour: '2-digit',
      minute: '2-digit'
    });
  },

  /**
   * 채팅 히스토리 UI 복원 (상태 보존 시스템용 - 모드별 분리)
   */
  renderChatHistory() {
    const container = document.getElementById('chatResults');
    if (!container) {
      console.error('❌ 채팅 컨테이너를 찾을 수 없음');
      if (window.NotificationBanner) {
        window.NotificationBanner.error(window.t ? window.t('error_chat_init_failed') : 'Cannot initialize chat interface.');
      }
      return;
    }

    // 기존 채팅 내용 항상 정리 (모드 토글을 위해 필수)
    container.innerHTML = '';
    // 채팅 화면 클리어 완료

    // 현재 모드의 히스토리만 가져오기
    const currentMode = window.Core?.state?.chatMode || 'rag';
    const currentHistory = window.Core?.getCurrentChatHistory();

    // 🔍 디버깅: 채팅 히스토리 렌더링 상태 확인
    console.log('🔍 [DEBUG] 채팅 히스토리 렌더링:', {
      currentMode: currentMode,
      historyLength: currentHistory?.length || 0,
      allChatHistory: window.Core?.state?.chatHistory,
      currentHistory: currentHistory
    });

    // 히스토리 로드

    // 히스토리가 없으면 모드별 초기 메시지 표시
    if (!currentHistory || currentHistory.length === 0) {
      // 표시할 메시지 없음

      // 각 모드별 첫 방문 시 인사 메시지 표시
      if (currentMode === 'rag') {
        // RAG 모드 인사 메시지
        this._addGreetingMessage('chat_welcome_rag', currentMode);
      } else if (currentMode === 'chat') {
        // Chat 모드 인사 메시지
        this._addGreetingMessage('chat_welcome_chat', currentMode);
      }
      return;
    }

    // 모드 히스토리 복원

    // 현재 모드의 히스토리만 렌더링
    for (const message of currentHistory) {
      const messageId = `msg-${Date.now()}-${Math.random().toString(36).substr(2, 9)}-${message.role}`;

      // 메시지 HTML 생성
      const messageHtml = `
        <div class="chat-message ${message.role}" id="${messageId}">
          <div class="message-avatar">${message.role === 'user' ? '👤' : '🤖'}</div>
          <div class="message-content">
            <div class="message-text">${this._parseContent(message.content)}</div>
            <div class="message-time" data-timestamp="${message.timestamp}">${this._formatMessageTime(message.timestamp)}</div>
          </div>
        </div>
      `;

      // 컨테이너에 추가
      container.insertAdjacentHTML('beforeend', messageHtml);
    }

    // 복원 완료 후 스크롤을 최하단으로
    setTimeout(() => {
      this.scrollToBottom();
    }, 100);

  },

  /**
   * 인사 메시지 표시 (모드별 초기 메시지)
   */
  _addGreetingMessage(i18nKey) {
    const container = document.getElementById('chatResults');
    if (!container) {
      console.error('❌ 채팅 컨테이너를 찾을 수 없음');
      if (window.NotificationBanner) {
        window.NotificationBanner.error(window.t ? window.t('error_chat_init_failed') : 'Cannot initialize chat interface.');
      }
      return;
    }

    const messageId = `greeting-msg-${Date.now()}`;
    const messageHtml = `
      <div class="chat-message assistant" id="${messageId}">
        <div class="message-avatar">🤖</div>
        <div class="message-content">
          <div class="message-text" data-i18n="${i18nKey}"></div>
          <div class="message-time" data-i18n="time_now"></div>
        </div>
      </div>
    `;

    // 컨테이너에 추가
    container.insertAdjacentHTML('beforeend', messageHtml);

    // 추가된 메시지에 번역 적용
    if (window.I18nManager) {
      const addedMessage = document.getElementById(messageId);
      if (addedMessage) {
        const i18nElements = addedMessage.querySelectorAll('[data-i18n]');
        i18nElements.forEach(element => {
          const key = element.getAttribute('data-i18n');
          element.textContent = window.I18nManager.getText(key);
        });
      }
    }

    // 스크롤을 최하단으로
    setTimeout(() => {
      this.scrollToBottom();
    }, 100);

    // 인사 메시지 표시 완료
  },

  /**
   * 메시지 시간 포맷팅 (히스토리용)
   */
  _formatMessageTime(timestamp) {
    if (!timestamp) return this._formatTime();

    // timestamp가 숫자(밀리초)인지 문자열인지 확인하여 적절히 처리
    let messageTime;
    if (typeof timestamp === 'number') {
      messageTime = new Date(timestamp);
    } else {
      // 기존 Date 객체 문자열 처리
      messageTime = new Date(timestamp);
    }

    // 유효한 날짜인지 확인
    if (isNaN(messageTime.getTime())) {
      return this._formatTime(); // 현재 시간으로 폴백
    }

    const locale = window.I18nManager ? window.I18nManager.getLocale() : 'ko-KR';

    // 항상 월, 일, 시간, 분을 모두 표시
    return messageTime.toLocaleString(locale, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  },

  /**
   * 채팅 화면 지우기 (히스토리 삭제 후 UI 새로고침)
   */
  clearChatDisplay() {
    const chatResults = document.getElementById('chatResults');
    if (!chatResults) return;

    // 기존 메시지들 제거 (초기 환영 메시지만 남기기)
    chatResults.innerHTML = `
      <div class="chat-message assistant">
        <div class="message-avatar">🤖</div>
        <div class="message-content">
          <div class="message-text" data-i18n="chat_welcome_rag">
            안녕하세요! AI 어시스턴트입니다. 현재 티켓에 대해 궁금한 점이나 도움이 필요한 사항을 말씀해 주세요.
          </div>
          <div class="message-time" data-i18n="time_now" data-timestamp="${Date.now()}">방금 전</div>
        </div>
      </div>
      <!-- 스크롤 공간 확보를 위한 빈 요소 -->
      <div style="height: 20px; flex-shrink: 0;"></div>
    `;

    // 모드 UI 업데이트 (메시지 카운트 0으로 리셋)
    const currentMode = window.Core?.state?.chatMode || 'rag';
    this.updateModeUI(currentMode);

    // 스크롤을 맨 아래로
    chatResults.scrollTop = chatResults.scrollHeight;

  },

  /**
   * 대화 히스토리 테스트 (개발자 콘솔용)
   */
  testChatHistory() {

    // 현재 히스토리 상태 확인
    window.Core.debugChatHistory();

    // 테스트 메시지 추가
    window.Core.addChatHistory('user', '테스트 질문입니다.');
    window.Core.addChatHistory('assistant', '테스트 답변입니다.');

    // 업데이트된 히스토리 확인
    window.Core.debugChatHistory();

    return '테스트 완료 - 콘솔에서 결과를 확인하세요.';
  },


};

/**
 * GitHub Copilot 스타일 채팅 도구 메뉴 관리
 */

// 채팅 도구 메뉴 토글
window.toggleChatToolsMenu = function () {
  const menu = document.getElementById('chatToolsDropdown');
  const button = document.getElementById('chatToolsMenu');

  if (!menu || !button) return;

  const isVisible = menu.style.display === 'block';

  if (isVisible) {
    // 메뉴 닫기
    menu.style.display = 'none';
    button.setAttribute('aria-expanded', 'false');
    document.removeEventListener('click', handleOutsideClick);
    document.removeEventListener('keydown', handleEscapeKey);
  } else {
    // 메뉴 열기
    menu.style.display = 'block';
    button.setAttribute('aria-expanded', 'true');

    // 첫 번째 메뉴 항목에 포커스
    setTimeout(() => {
      const firstMenuItem = menu.querySelector('button:not(.danger)');
      if (firstMenuItem) {
        firstMenuItem.focus();
      }

      document.addEventListener('click', handleOutsideClick);
      document.addEventListener('keydown', handleEscapeKey);
    }, 0);
  }
};

// 채팅 도구 메뉴 닫기
window.closeChatToolsMenu = function () {
  const menu = document.getElementById('chatToolsDropdown');
  const button = document.getElementById('chatToolsMenu');

  if (menu && menu.style.display === 'block') {
    menu.style.display = 'none';
    if (button) {
      button.setAttribute('aria-expanded', 'false');
    }
    document.removeEventListener('click', handleOutsideClick);
    document.removeEventListener('keydown', handleEscapeKey);
  }
};

// 외부 클릭 처리
function handleOutsideClick(event) {
  const menu = document.getElementById('chatToolsDropdown');
  const button = document.getElementById('chatToolsMenu');

  if (menu && button &&
    !menu.contains(event.target) &&
    !button.contains(event.target)) {
    window.closeChatToolsMenu();
  }
}

// ESC 키 처리
function handleEscapeKey(event) {
  if (event.key === 'Escape') {
    window.closeChatToolsMenu();
  }
}

/**
 * Week 2: 전역 함수들 (HTML에서 직접 호출)
 */

// 메시지 전송 (HTML에서 호출)
window.sendMessage = function () {
  if (window.ChatUI && typeof window.ChatUI.sendMessage === 'function') {
    window.ChatUI.sendMessage();
  }
};

// 채팅 입력 처리 함수들
window.handleChatKeydown = function (event) {
  if (window.ChatUI && typeof window.ChatUI.handleChatKeydown === 'function') {
    return window.ChatUI.handleChatKeydown(event);
  }
};

window.adjustTextareaHeight = function (textarea) {
  if (window.ChatUI && typeof window.ChatUI.adjustTextareaHeight === 'function') {
    return window.ChatUI.adjustTextareaHeight(textarea);
  }
};

window.handleCompositionStart = function (event) {
  if (window.ChatUI && typeof window.ChatUI.handleCompositionStart === 'function') {
    return window.ChatUI.handleCompositionStart(event);
  }
};

window.handleCompositionEnd = function (event) {
  if (window.ChatUI && typeof window.ChatUI.handleCompositionEnd === 'function') {
    return window.ChatUI.handleCompositionEnd(event);
  }
};

// 전역 변수
window.isSendingMessage = false;