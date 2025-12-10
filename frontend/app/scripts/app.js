/**
 * AI Copilot - FDK File Search App
 * 
 * google-file-search-tool 기능을 FDK 앱으로 구현
 * - 티켓/아티클/공통문서 검색
 * - 문맥 검색 + 필터링
 */

// =============================================================================
// Global State
// =============================================================================

let client = null;
let ticketData = null;
let sessionId = null;
let chatHistory = [];
let isLoading = false;

// 소스 관련 상태
let availableSources = [];
let selectedSources = [];
let sourceLabels = {};

// 필터 상태
let latestFilters = [];
let knownContext = {};
let filterConfidence = null;

// =============================================================================
// DOM Elements
// =============================================================================

const elements = {};

// =============================================================================
// FDK Initialization (기존 방식)
// =============================================================================

let isModalView = false;

document.onreadystatechange = function() {
  if (document.readyState === "complete") {
    if (typeof app !== 'undefined') {
      app.initialized().then(async function(_client) {
        client = _client;
        const context = await client.instance.context();
        isModalView = context.location !== 'ticket_top_navigation';

        // 메인 페이지: 클릭시 모달 열기
        if (!isModalView) {
          client.events.on("app.activated", async () => {
            await client.interface.trigger("showModal", {
              title: "AI Copilot",
              template: "index.html",
              noBackdrop: true
            });
          });
          return;
        }

        // 모달 뷰: 비즈니스 로직 실행
        cacheElements();
        setupEventListeners();
        await loadTicketData();
        await loadStatus();
        await createSession();
        updateStatus('ready', '준비 완료');
      }).catch(function(error) {
        console.error("FDK 초기화 실패:", error);
        updateStatus('error', '초기화 실패: ' + error.message);
      });
    } else {
      console.error("FDK app 객체가 없습니다.");
      updateStatus('error', 'FDK 환경 필요');
    }
  }
};

function cacheElements() {
  elements.headerTitle = document.getElementById('headerTitle');
  elements.statusBadge = document.getElementById('statusBadge');
  elements.chatContainer = document.getElementById('chatContainer');
  elements.chatMessages = document.getElementById('chatMessages');
  elements.chatForm = document.getElementById('chatForm');
  elements.chatInput = document.getElementById('chatInput');
  elements.sendBtn = document.getElementById('sendBtn');
  elements.newChatBtn = document.getElementById('newChatBtn');
  elements.sourceModal = document.getElementById('sourceModal');
  elements.modalTitle = document.getElementById('modalTitle');
  elements.modalContent = document.getElementById('modalContent');
  elements.closeModalBtn = document.getElementById('closeModalBtn');
  elements.sourceSelector = document.getElementById('sourceSelector');
  elements.filterDisplay = document.getElementById('filterDisplay');
  elements.filterChips = document.getElementById('filterChips');
  elements.filterConfidence = document.getElementById('filterConfidence');
}

function setupEventListeners() {
  elements.chatForm.addEventListener('submit', handleSubmit);
  elements.chatInput.addEventListener('input', handleInputChange);
  elements.chatInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  });
  elements.newChatBtn.addEventListener('click', handleNewChat);
  elements.closeModalBtn.addEventListener('click', closeModal);
  elements.sourceModal.addEventListener('click', (e) => {
    if (e.target === elements.sourceModal) closeModal();
  });

  // 예시 질문
  document.querySelectorAll('.example-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const question = btn.textContent.trim();
      elements.chatInput.value = question;
      handleInputChange();
      handleSubmit(new Event('submit'));
    });
  });
}

// =============================================================================
// API Calls
// =============================================================================

async function apiCall(method, path, body = null) {
  if (!client) {
    throw new Error('FDK 클라이언트가 초기화되지 않았습니다.');
  }
  
  const templateName = method === 'POST' ? 'backendApiPost' : 'backendApi';
  const options = { context: { path } };
  if (body) {
    options.body = JSON.stringify(body);
  }
  
  try {
    const response = await client.request.invokeTemplate(templateName, options);
    console.log(`API ${method} ${path}:`, response.status);
    
    if (response.status >= 200 && response.status < 300) {
      // 응답이 JSON인지 확인
      const responseText = response.response;
      if (responseText && responseText.trim().startsWith('{')) {
        return JSON.parse(responseText);
      } else {
        console.error('응답이 JSON이 아님:', responseText?.substring(0, 100));
        throw new Error('서버 응답이 올바르지 않습니다.');
      }
    }
    throw new Error(`API 오류: ${response.status}`);
  } catch (error) {
    console.error(`API 호출 실패 (${method} ${path}):`, error);
    throw error;
  }
}

// =============================================================================
// Session & Status
// =============================================================================

async function createSession() {
  const result = await apiCall('POST', 'api/session');
  sessionId = result.sessionId;
  console.log('세션 생성:', sessionId);
}

async function loadStatus() {
  const status = await apiCall('GET', 'api/status');
  console.log('Status:', status);
  
  // 사용 가능한 소스 설정
  if (!status.availableSources || status.availableSources.length === 0) {
    throw new Error('사용 가능한 검색 소스가 없습니다.');
  }
  
  availableSources = status.availableSources;
  selectedSources = [availableSources[0]];
  
  // 소스 라벨 매핑
  sourceLabels = {
    tickets: '🎫 티켓',
    articles: '📄 헬프센터',
    common: '📦 제품 매뉴얼'
  };
  
  renderSourceSelector();
}

// =============================================================================
// Ticket Data
// =============================================================================

async function loadTicketData() {
  const data = await client.data.get('ticket');
  const ticketId = data.ticket.id;

  const response = await client.request.invokeTemplate('getTicketWithConversations', {
    context: { ticketId }
  });

  if (response.status !== 200) {
    throw new Error(`티켓 로드 실패: ${response.status}`);
  }
  
  ticketData = JSON.parse(response.response);
  
  // 대화 내역 페이지네이션 처리 (30개 이상일 경우)
  try {
    const allConversations = await fetchAllConversations(ticketId);
    // 기존 conversations(첫 페이지)보다 많이 가져왔다면 교체
    if (allConversations.length > (ticketData.conversations?.length || 0)) {
      ticketData.conversations = allConversations;
      console.log(`전체 대화 내역 로드 완료: ${allConversations.length}개`);
    }
  } catch (error) {
    console.error('대화 내역 추가 로드 실패:', error);
    // 실패해도 기본 로드된 데이터(첫 페이지)는 유지
  }

  elements.headerTitle.textContent = `티켓 #${ticketId}`;
  console.log('티켓 로드 완료:', ticketData);
}

async function fetchAllConversations(ticketId) {
  let conversations = [];
  let page = 1;
  let hasMore = true;
  const PER_PAGE = 30;

  while (hasMore) {
    try {
      console.log(`Fetching conversations page ${page}...`);
      const response = await client.request.invokeTemplate('getTicketConversations', {
        context: { 
          ticketId: String(ticketId), 
          page: String(page) 
        }
      });

      if (response.status !== 200) {
        console.warn(`대화 페이지 ${page} 로드 실패: ${response.status}`, response);
        // 404나 400이면 더 이상 없는 것으로 간주하고 중단
        if (response.status === 404 || response.status === 400) {
            hasMore = false;
        }
        break;
      }

      const data = JSON.parse(response.response);
      if (Array.isArray(data) && data.length > 0) {
        console.log(`Page ${page} loaded: ${data.length} conversations`);
        conversations = conversations.concat(data);
        
        if (data.length < PER_PAGE) {
          hasMore = false;
        } else {
          page++;
        }
      } else {
        hasMore = false;
      }
      
      // 안전장치: 최대 20페이지 (600개)
      if (page > 20) hasMore = false;
      
    } catch (e) {
      console.error(`대화 페이지 ${page} 처리 중 오류:`, e);
      try {
        // 에러 객체 상세 출력
        const errorDetails = {};
        Object.getOwnPropertyNames(e).forEach(key => {
            errorDetails[key] = e[key];
        });
        console.error('Error details:', JSON.stringify(errorDetails, null, 2));
      } catch (jsonError) {
        console.error('Error stringify failed', jsonError);
      }
      break;
    }
  }
  
  // 날짜순 정렬 (오래된 순) - 맥락 파악을 위해 시간순 정렬 필수
  conversations.sort((a, b) => new Date(a.created_at) - new Date(b.created_at));
  
  return conversations;
}

// =============================================================================
// Source Selector
// =============================================================================

function renderSourceSelector() {
  if (!elements.sourceSelector) return;
  
  // 선택된 소스가 없으면 첫 번째 소스 선택 (기본값)
  if (!selectedSources.length && availableSources.length) {
    selectedSources = [availableSources[0]];
  }
  
  elements.sourceSelector.innerHTML = `
    <div class="flex items-center justify-between mb-2">
      <span class="text-xs font-medium text-gray-600">검색 범위 (다중 선택 가능)</span>
    </div>
    <div class="flex flex-wrap gap-2" id="sourceButtons">
      ${availableSources.map(source => {
        const isSelected = selectedSources.includes(source);
        const label = sourceLabels[source] || source;
        return `
          <label class="cursor-pointer select-none">
            <input type="checkbox" name="searchSource" value="${source}" ${isSelected ? 'checked' : ''} class="sr-only">
            <span class="source-btn px-3 py-1.5 text-xs rounded-full border transition-all inline-flex items-center gap-1 ${
              isSelected 
                ? 'bg-blue-500 text-white border-blue-500 shadow-sm' 
                : 'bg-white text-gray-600 border-gray-300 hover:border-blue-400 hover:bg-gray-50'
            }">
              ${isSelected ? '<svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7"></path></svg>' : ''}
              ${label}
            </span>
          </label>
        `;
      }).join('')}
    </div>
  `;
  
  // 체크박스 이벤트 연결
  document.querySelectorAll('input[name="searchSource"]').forEach(checkbox => {
    checkbox.addEventListener('change', (e) => {
      toggleSource(e.target.value);
    });
  });
}

function toggleSource(source) {
  const index = selectedSources.indexOf(source);
  if (index === -1) {
    selectedSources.push(source);
  } else {
    // 최소 1개는 선택되어야 함
    if (selectedSources.length > 1) {
      selectedSources.splice(index, 1);
    } else {
      // 마지막 하나는 해제 불가 (알림 또는 무시)
      // UI 재렌더링으로 체크박스 상태 복구
      renderSourceSelector();
      return;
    }
  }
  renderSourceSelector();
}

// =============================================================================
// Chat Functions
// =============================================================================

async function handleSubmit(e) {
  e.preventDefault();
  
  const message = elements.chatInput.value.trim();
  if (!message || isLoading) return;

  // 사용자 메시지 추가
  addMessage('user', message);
  
  // 한글 입력 시 마지막 글자 중복 문제 해결 (IME Composition)
  // 이벤트 루프가 끝난 후 입력창을 비워야 브라우저의 IME 확정 동작과 충돌하지 않음
  setTimeout(() => {
    elements.chatInput.value = '';
    handleInputChange();
  }, 0);

  // 로딩 표시
  setLoading(true);
  const loadingId = addLoadingMessage();

  try {
    const response = await sendChat(message);
    removeMessage(loadingId);
    
    // AI 응답 추가
    addMessage('assistant', response.text, response.groundingChunks);
    
    // 필터 업데이트
    updateFilters(response.filters, response.filterConfidence, response.knownContext);
    
  } catch (error) {
    console.error('채팅 실패:', error);
    removeMessage(loadingId);
    addErrorMessage(`오류: ${error.message}`);
  } finally {
    setLoading(false);
  }
}

async function sendChat(message) {
  const payload = {
    query: message,
    sessionId: sessionId
  };
  
  // 선택된 소스 추가
  if (selectedSources.length > 0) {
    payload.sources = selectedSources;
  }

  // 티켓 컨텍스트 추가
  if (ticketData) {
    // 페이로드 크기 최적화를 위해 필수 데이터만 추출
    const minimalTicket = minimizeTicketData(ticketData);
    payload.context = {
      ticket: minimalTicket
    };
    const convCount = minimalTicket.conversations ? minimalTicket.conversations.length : 0;
    console.log(`Sending chat with ticket context: ID=${minimalTicket.id}, Conversations=${convCount}`);
  }
  
  return await apiCall('POST', 'api/chat', payload);
}

function minimizeTicketData(original) {
  if (!original) return null;
  
  // 필수 필드만 추출
  const minimal = {
    id: original.id,
    subject: original.subject,
    description_text: original.description_text,
    status: original.status,
    priority: original.priority,
    created_at: original.created_at,
    updated_at: original.updated_at
  };
  
  // 대화 내역 최소화 (HTML 태그 제거 등은 백엔드에서 처리하더라도, 불필요한 메타데이터는 여기서 제거)
  if (original.conversations && Array.isArray(original.conversations)) {
    minimal.conversations = original.conversations.map(c => ({
      body_text: c.body_text,
      incoming: c.incoming,
      private: c.private,
      created_at: c.created_at,
      user_id: c.user_id
    }));
  }
  
  return minimal;
}

function handleInputChange() {
  const hasText = elements.chatInput.value.trim().length > 0;
  elements.sendBtn.disabled = !hasText || isLoading;
  
  elements.chatInput.style.height = 'auto';
  elements.chatInput.style.height = Math.min(elements.chatInput.scrollHeight, 120) + 'px';
}

function handleNewChat() {
  chatHistory = [];
  latestFilters = [];
  knownContext = {};
  filterConfidence = null;
  
  // 채팅 초기화
  elements.chatMessages.innerHTML = `
    <div id="welcomeMessage" class="flex justify-start">
      <div class="max-w-[85%] bg-white border border-gray-200 rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm">
        <p class="text-sm text-gray-800 font-medium mb-2">안녕하세요! 👋</p>
        <p class="text-sm text-gray-600 mb-3">티켓, 헬프센터 문서, 공통 문서에서 정보를 검색해드립니다.</p>
        <div class="flex flex-wrap gap-2">
          <button class="example-btn px-3 py-1.5 text-xs bg-blue-50 text-blue-700 rounded-full hover:bg-blue-100 transition-all">
            비밀번호 재설정 방법
          </button>
          <button class="example-btn px-3 py-1.5 text-xs bg-blue-50 text-blue-700 rounded-full hover:bg-blue-100 transition-all">
            환불 정책 안내
          </button>
          <button class="example-btn px-3 py-1.5 text-xs bg-blue-50 text-blue-700 rounded-full hover:bg-blue-100 transition-all">
            API 연동 가이드
          </button>
        </div>
      </div>
    </div>
  `;
  
  // 예시 질문 이벤트 재연결
  document.querySelectorAll('.example-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const question = btn.textContent.trim();
      elements.chatInput.value = question;
      handleInputChange();
      handleSubmit(new Event('submit'));
    });
  });
  
  // 필터 숨기기
  if (elements.filterDisplay) {
    elements.filterDisplay.classList.add('hidden');
  }
  
  // 새 세션 생성
  createSession();
  updateStatus('ready', '새 대화 시작');
}

// =============================================================================
// Filter Display
// =============================================================================

function updateFilters(filters, confidence, context) {
  latestFilters = filters || [];
  filterConfidence = confidence;
  knownContext = context || {};
  
  if (!elements.filterDisplay) return;
  
  if (latestFilters.length === 0 && Object.keys(knownContext).length === 0) {
    elements.filterDisplay.classList.add('hidden');
    return;
  }
  
  elements.filterDisplay.classList.remove('hidden');
  
  // 필터 칩
  if (elements.filterChips) {
    elements.filterChips.innerHTML = latestFilters.map(filter => 
      `<span class="px-2 py-1 text-xs bg-gray-100 text-gray-700 rounded-full">${filter}</span>`
    ).join('') || '<span class="text-xs text-gray-400">없음</span>';
  }
  
  // 신뢰도
  if (elements.filterConfidence && filterConfidence) {
    const confidenceColors = {
      high: 'text-green-600',
      medium: 'text-yellow-600',
      low: 'text-red-600'
    };
    elements.filterConfidence.className = `text-xs ${confidenceColors[filterConfidence] || 'text-gray-500'}`;
    elements.filterConfidence.textContent = `신뢰도: ${filterConfidence}`;
  }
}

// =============================================================================
// Message Rendering
// =============================================================================

function addMessage(role, content, sources = []) {
  // 웰컴 메시지 제거
  const welcome = document.getElementById('welcomeMessage');
  if (welcome) welcome.remove();
  
  const messageId = 'msg-' + Date.now();
  const messageDiv = document.createElement('div');
  messageDiv.id = messageId;
  messageDiv.className = `flex ${role === 'user' ? 'justify-end' : 'justify-start'} animate-fade-in`;

  const isUser = role === 'user';
  const bgClass = isUser ? 'bg-blue-500 text-white' : 'bg-white border border-gray-200';
  const roundedClass = isUser ? 'rounded-2xl rounded-tr-sm' : 'rounded-2xl rounded-tl-sm';

  let sourcesHtml = '';
  if (sources && sources.length > 0) {
    sourcesHtml = `
      <div class="mt-3 pt-3 border-t border-gray-100">
        <p class="text-xs text-gray-400 mb-2">참조 문서</p>
        <div class="flex flex-wrap gap-2">
          ${sources.map((source, idx) => {
            const ctx = source.retrievedContext || source.web || {};
            const title = ctx.title || '참조 ' + (idx + 1);
            const text = ctx.text || '';
            const uri = ctx.uri || '';
            return `
              <button 
                class="source-chip px-2 py-1 text-xs bg-gray-50 border border-gray-200 rounded-md hover:border-blue-400 hover:bg-blue-50 transition-all cursor-pointer"
                data-title="${escapeAttr(title)}"
                data-text="${escapeAttr(text)}"
                data-uri="${escapeAttr(uri)}"
              >📄 ${escapeHtml(title)}</button>
            `;
          }).join('')}
        </div>
      </div>
    `;
  }

  messageDiv.innerHTML = `
    <div class="max-w-[85%] ${bgClass} ${roundedClass} px-4 py-3 shadow-sm">
      <div class="text-sm whitespace-pre-wrap">${formatMessage(content)}</div>
      ${sourcesHtml}
    </div>
  `;

  elements.chatMessages.appendChild(messageDiv);
  scrollToBottom();

  // 소스 클릭 이벤트
  const chips = messageDiv.querySelectorAll('.source-chip');
  console.log('소스 칩 개수:', chips.length);
  chips.forEach(chip => {
    chip.addEventListener('click', async () => {
      console.log('소스 칩 클릭:', chip.dataset.title);
      await openModal(chip.dataset.title, chip.dataset.text, chip.dataset.uri);
    });
  });

  chatHistory.push({ role, content });
  return messageId;
}

function addErrorMessage(errorText) {
  // 웰컴 메시지 제거
  const welcome = document.getElementById('welcomeMessage');
  if (welcome) welcome.remove();
  
  const messageId = 'error-' + Date.now();
  const messageDiv = document.createElement('div');
  messageDiv.id = messageId;
  messageDiv.className = 'flex justify-start animate-fade-in';

  messageDiv.innerHTML = `
    <div class="max-w-[85%] bg-red-50 border border-red-200 rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm">
      <div class="text-sm text-red-600">
        <span class="font-medium">⚠️ ${escapeHtml(errorText)}</span>
      </div>
    </div>
  `;

  elements.chatMessages.appendChild(messageDiv);
  scrollToBottom();
  return messageId;
}

function addLoadingMessage() {
  const messageId = 'loading-' + Date.now();
  const messageDiv = document.createElement('div');
  messageDiv.id = messageId;
  messageDiv.className = 'flex justify-start';

  messageDiv.innerHTML = `
    <div class="max-w-[85%] bg-white border border-gray-200 rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm">
      <div class="flex items-center gap-2">
        <div class="flex gap-1">
          <span class="w-2 h-2 bg-gray-300 rounded-full animate-bounce" style="animation-delay: 0ms"></span>
          <span class="w-2 h-2 bg-gray-300 rounded-full animate-bounce" style="animation-delay: 150ms"></span>
          <span class="w-2 h-2 bg-gray-300 rounded-full animate-bounce" style="animation-delay: 300ms"></span>
        </div>
        <span class="text-sm text-gray-400">검색 중...</span>
      </div>
    </div>
  `;

  elements.chatMessages.appendChild(messageDiv);
  scrollToBottom();
  return messageId;
}

function removeMessage(messageId) {
  const message = document.getElementById(messageId);
  if (message) message.remove();
}

function formatMessage(text) {
  if (!text) return '';
  return text
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/`([^`]+)`/g, '<code class="px-1 py-0.5 bg-gray-100 rounded text-xs font-mono">$1</code>')
    .replace(/\n/g, '<br>');
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text || '';
  return div.innerHTML;
}

function escapeAttr(text) {
  return (text || '').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

// =============================================================================
// UI Helpers
// =============================================================================

function setLoading(loading) {
  isLoading = loading;
  elements.sendBtn.disabled = loading || !elements.chatInput.value.trim();
  updateStatus(loading ? 'loading' : 'ready', loading ? '검색 중...' : '준비 완료');
}

function updateStatus(status, text) {
  if (!elements.statusBadge) return;
  
  elements.statusBadge.textContent = text;
  elements.statusBadge.className = 'px-2 py-1 text-xs font-medium rounded-full ';
  
  const colors = {
    ready: 'bg-green-100 text-green-700',
    loading: 'bg-blue-100 text-blue-700',
    error: 'bg-red-100 text-red-700'
  };
  elements.statusBadge.className += colors[status] || 'bg-gray-100 text-gray-700';
}

function scrollToBottom() {
  elements.chatContainer.scrollTop = elements.chatContainer.scrollHeight;
}

// =============================================================================
// Modal - Custom Implementation (FDK showModal 대체)
// =============================================================================

function openModal(title, content, uri) {
  console.log('openModal 호출:', { title, content, uri });
  
  if (!elements.sourceModal || !elements.modalTitle || !elements.modalContent) {
    console.error('모달 엘리먼트를 찾을 수 없습니다.');
    return;
  }

  // 1. URL Fix (localhost -> wedosoft.net)
  let fixedUri = uri;
  if (fixedUri) {
    fixedUri = fixedUri.replace('http://localhost:10001', 'https://wedosoft.net');
    fixedUri = fixedUri.replace('localhost:10001', 'wedosoft.net');
  }

  // 2. Header (Title + Button side-by-side)
  const titleText = title || "참조 문서";
  
  // 제목과 버튼을 헤더에 함께 배치
  let headerHtml = `<span class="truncate" title="${escapeAttr(titleText)}">${escapeHtml(titleText)}</span>`;
  
  if (fixedUri) {
    headerHtml += `
      <a href="${escapeAttr(fixedUri)}" target="_blank" rel="noopener noreferrer" 
         class="flex-shrink-0 ml-2 px-2 py-1 bg-blue-50 hover:bg-blue-100 text-blue-600 border border-blue-200 text-xs rounded flex items-center gap-1 transition-colors"
         title="새 탭에서 원문 보기">
        <span>원본 보기</span>
        <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"/>
        </svg>
      </a>
    `;
  }
  
  // 헤더 스타일 조정 (Flex)
  elements.modalTitle.className = "font-semibold text-app-text flex items-center min-w-0 flex-1 mr-4";
  elements.modalTitle.innerHTML = headerHtml;
  
  // 3. Body Content (Compact)
  let html = '';
  
  // 구분선 및 라벨 (여백 최소화)
  html += `
    <div class="flex items-center mb-1">
      <span class="text-xs text-gray-400">참조 내용 (발췌)</span>
      <div class="flex-grow ml-2 border-t border-gray-100"></div>
    </div>
  `;
  
  // 본문 내용
  html += `
    <div class="bg-gray-50 p-3 rounded-lg border border-gray-200 text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">${formatMessage(content || "내용이 없습니다.")}</div>
  `;
  
  elements.modalContent.innerHTML = html;
  
  // 모달 표시
  elements.sourceModal.classList.remove('hidden');
}

function closeModal() {
  if (elements.sourceModal) {
    elements.sourceModal.classList.add('hidden');
  }
}
