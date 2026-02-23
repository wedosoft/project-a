/* eslint-disable */
// =============================================================================
// Store Section
// =============================================================================

const state = {
  client: null,
  ticketData: null,
  ticketFields: null,
  tenantConfig: null,
  sessionId: null,
  chatHistory: [],
  isLoading: false,
  availableSources: [],
  selectedSources: [],
  sourceLabels: {
    tickets: '🎫 티켓',
    articles: '📄 헬프센터',
    common: '📦 제품 매뉴얼'
  },
  latestFilters: [],
  knownContext: {},
  filterConfidence: null,
  // 새로운 상태
  currentTab: 'analysis', // 'analysis' | 'chat'
  modalCache: null,       // { title, content, uri }
  analysisResult: null    // 분석 결과 캐시
};

// APP_CONFIG: 보안 파라미터 저장용 전역 객체
window.APP_CONFIG = {
  apiKey: '',
  domain: '',
  tenantId: ''
};

// state를 전역으로 노출 (analysis-ui.js 등에서 window.state로 접근)
window.state = state;

function setClient(client) {
  state.client = client;
}

function setTicketData(data) {
  state.ticketData = data;
}

function setTicketFields(fields) {
  state.ticketFields = fields;
}

function setTenantConfig(config) {
  state.tenantConfig = config;
}

function setSessionId(id) {
  state.sessionId = id;
}

function setLoading(loading) {
  state.isLoading = loading;
}

function setAvailableSources(sources) {
  state.availableSources = sources;
}

function setSelectedSources(sources) {
  state.selectedSources = sources;
}

function setSourceLabels(labels) {
  state.sourceLabels = labels;
}

function toggleSource(source) {
  const index = state.selectedSources.indexOf(source);
  // 단일 선택만 허용 (0개 또는 1개)
  if (index === -1) {
    state.selectedSources = [source];
  } else {
    state.selectedSources = [];
  }
  return state.selectedSources;
}

function addChatHistory(message) {
  state.chatHistory.push(message);
}

function setLatestFilters(filters) {
  state.latestFilters = filters || [];
}

function setKnownContext(context) {
  state.knownContext = context || {};
}

function setFilterConfidence(confidence) {
  state.filterConfidence = confidence;
}

function setCurrentTab(tab) {
  state.currentTab = tab;
}

function setModalCache(cache) {
  state.modalCache = cache;
}

function setAnalysisResult(result) {
  state.analysisResult = result;
}

function getTenantSelectedFields() {
  const selected = state.tenantConfig && Array.isArray(state.tenantConfig.selected_fields)
    ? state.tenantConfig.selected_fields
    : [];

  return selected
    .map(v => (typeof v === 'string' ? v.trim() : ''))
    .filter(Boolean);
}

/**
 * 테넌트 설정(selected_fields)에 따라 특정 field_name이 허용되는지 판정
 * - selected_fields가 비어있으면: 제한 없음(모든 필드 허용)
 * - selected_fields가 있으면: 해당 필드만 허용
 * - nested_field의 경우: root가 선택되면 하위 nested_ticket_fields도 함께 허용(관리 편의)
 */
function buildTenantFieldAllowChecker() {
  const selected = getTenantSelectedFields();
  if (!selected.length) {
    return () => true;
  }

  const selectedSet = new Set(selected);
  const nestedAllowed = new Set();

  if (Array.isArray(state.ticketFields)) {
    state.ticketFields.forEach(f => {
      if (!f || typeof f !== 'object') return;
      if (f.type !== 'nested_field') return;
      if (!f.name) return;
      if (!Array.isArray(f.nested_ticket_fields)) return;

      const groupNames = [f.name];
      f.nested_ticket_fields.forEach(n => {
        if (n && typeof n === 'object' && n.name) {
          groupNames.push(n.name);
        }
      });

      // 그룹 중 하나라도 선택되어 있으면, nested 필드는 일관성 있게 업데이트되어야 하므로
      // 해당 그룹 전체를 허용 처리한다.
      const groupSelected = groupNames.some(n => selectedSet.has(n));
      if (!groupSelected) return;

      groupNames.forEach(n => nestedAllowed.add(n));
    });
  }

  return (fieldName) => {
    if (!fieldName) return false;
    return selectedSet.has(fieldName) || nestedAllowed.has(fieldName);
  };
}

// =============================================================================
// API Section
// =============================================================================

/**
 * 보안 파라미터 로드 (서버리스 함수 호출)
 */
async function loadSecureConfig() {
  const client = state.client;
  if (!client) return;

  try {
    const data = await client.request.invoke('getSecureParams', {});
    const responseData = data?.response || data;

    if (responseData && responseData.apiKey) {
      window.APP_CONFIG.apiKey = responseData.apiKey;
      window.APP_CONFIG.domain = responseData.domain;
      window.APP_CONFIG.tenantId = responseData.tenantId || responseData.domain?.split('.')[0] || '';
      console.log('[Config] 보안 파라미터 로드 완료');
    }
  } catch (error) {
    console.error('[Config] 보안 파라미터 로드 실패:', error);
  }
}

async function apiCall(method, path, body = null) {
  const client = state.client;
  if (!client) {
    throw new Error('FDK 클라이언트가 초기화되지 않았습니다.');
  }
  
  const templateName = method === 'POST' ? 'backendApiPost' : 'backendApi';
  const options = { context: { path } };
  if (body) {
    options.body = JSON.stringify(body);
  }
  
  const MAX_RETRIES = 3;
  
  for (let i = 0; i < MAX_RETRIES; i++) {
    try {
      const response = await client.request.invokeTemplate(templateName, options);
      console.log(`API ${method} ${path} (Attempt ${i + 1}):`, response.status);
      
      if (response.status >= 200 && response.status < 300) {
        const responseText = response.response;
        if (responseText && responseText.trim().startsWith('{')) {
          return JSON.parse(responseText);
        } else {
          console.error('응답이 JSON이 아님:', responseText?.substring(0, 100));
          throw new Error('서버 응답이 올바르지 않습니다.');
        }
      }
      
      if ([502, 503, 504].includes(response.status)) {
        if (i < MAX_RETRIES - 1) {
          console.warn(`서버 오류(${response.status}), ${i + 1}초 후 재시도합니다... (${i + 1}/${MAX_RETRIES})`);
          await new Promise(resolve => setTimeout(resolve, (i + 1) * 1000));
          continue;
        }
      }
      
      throw new Error(`API 오류: ${response.status}`);
    } catch (error) {
      if (i === MAX_RETRIES - 1) {
        console.error(`API 호출 최종 실패 (${method} ${path}):`, error);
        throw error;
      }
      console.warn(`API 호출 중 예외 발생, 재시도합니다... (${i + 1}/${MAX_RETRIES})`, error);
      await new Promise(resolve => setTimeout(resolve, (i + 1) * 1000));
    }
  }
}

/**
 * 관리자(Admin)에서 저장한 테넌트 설정을 로드
 * - selected_fields: AI 제안/업데이트 허용 필드
 * - response_tone 등 기타 설정
 */
async function loadTenantConfig() {
  try {
    const cfg = await apiCall('GET', 'api/admin/config');
    setTenantConfig(cfg);
    console.log('[Config] tenantConfig loaded:', {
      response_tone: cfg?.response_tone,
      selected_fields_count: Array.isArray(cfg?.selected_fields) ? cfg.selected_fields.length : 0
    });
  } catch (e) {
    console.warn('[Config] tenantConfig not available, using defaults:', e);
    setTenantConfig(null);
  }
}

// =============================================================================
// UI Section
// =============================================================================

const elements = {};

// 티커 메시지 매핑
const TICKER_MESSAGES = {
  'router_decision': '🔍 분석 방향 결정 중...',
  'retriever_start': '📚 유사 사례 검색 중...',
  'retriever_results': '✅ 검색 완료',
  'resolution_start': '🤖 AI 제안 생성 중...',
  'resolution_complete': '✨ 분석 완료!',
  // Progressive SSE (assist/analyze/stream, field-proposals/stream)
  'started': '🚀 요청 시작...',
  'searching': '📚 관련 문서 검색 중...',
  'search_result': '✅ 검색 완료',
  'analyzing': '🧠 티켓 분석 중...',
  'field_proposal': '🏷️ 필드 제안 생성 중...',
  'synthesizing': '🧩 최종 정리 중...',
  'draft_response': '✍️ 응답 생성 중...',
  'complete': '✨ 완료!',
  'error': '❌ 오류 발생',
  'polling': '⏳ 처리 중...'
};

function cacheElements() {
  elements.headerTitle = document.getElementById('headerTitle');
  elements.statusBadge = document.getElementById('statusBadge');
  // 탭 요소
  elements.tabAnalysis = document.getElementById('tabAnalysis');
  elements.tabChat = document.getElementById('tabChat');
  elements.sectionAnalysis = document.getElementById('sectionAnalysis');
  elements.sectionChat = document.getElementById('sectionChat');
  // 분석 섹션 요소
  elements.analysisTicker = document.getElementById('analysisTicker');
  elements.tickerMessage = document.getElementById('tickerMessage');
  elements.analysisContainer = document.getElementById('analysisContainer');
  elements.analysisContent = document.getElementById('analysisContent');
  elements.analysisPlaceholder = document.getElementById('analysisPlaceholder');
  elements.analyzeBtn = document.getElementById('analyzeBtn');
  elements.fieldProposalsBtn = document.getElementById('fieldProposalsBtn');
  // 채팅 섹션 요소
  elements.chatContainer = document.getElementById('chatContainer');
  elements.chatMessages = document.getElementById('chatMessages');
  elements.chatForm = document.getElementById('chatForm');
  elements.chatInput = document.getElementById('chatInput');
  elements.sendBtn = document.getElementById('sendBtn');
  elements.newChatBtn = document.getElementById('newChatBtn');
  // 공통 요소
  elements.sourceModal = document.getElementById('sourceModal');
  elements.modalTitle = document.getElementById('modalTitle');
  elements.modalContent = document.getElementById('modalContent');
  elements.closeModalBtn = document.getElementById('closeModalBtn');
  elements.sourceSelector = document.getElementById('sourceSelector');
  elements.filterDisplay = document.getElementById('filterDisplay');
  elements.filterChips = document.getElementById('filterChips');
  elements.filterConfidence = document.getElementById('filterConfidence');
}

function getElements() {
  return elements;
}

// =============================================================================
// Tab & Ticker Functions
// =============================================================================

/**
 * 탭 전환
 * @param {string} tabName - 'analysis' | 'chat'
 */
function switchTab(tabName) {
  setCurrentTab(tabName);
  
  // 탭 버튼 활성화 상태 업데이트
  if (elements.tabAnalysis && elements.tabChat) {
    elements.tabAnalysis.classList.toggle('active', tabName === 'analysis');
    elements.tabChat.classList.toggle('active', tabName === 'chat');
  }
  
  // 섹션 표시/숨김
  if (elements.sectionAnalysis && elements.sectionChat) {
    elements.sectionAnalysis.classList.toggle('section-hidden', tabName !== 'analysis');
    elements.sectionChat.classList.toggle('section-hidden', tabName !== 'chat');
  }
  
  console.log(`[Tab] Switched to: ${tabName}`);
}

/**
 * 티커 표시
 * @param {string} eventType - 이벤트 타입
 * @param {Object} data - 추가 데이터 (optional)
 */
function showTicker(eventType, data = {}) {
  if (!elements.analysisTicker || !elements.tickerMessage) return;
  
  let message = TICKER_MESSAGES[eventType] || eventType;
  
  // 동적 메시지 생성
  if (eventType === 'retriever_results' && data.similar_cases_count !== undefined) {
    message = `✅ ${data.similar_cases_count}건 유사 사례, ${data.kb_articles_count || 0}건 KB 문서 발견`;
  }
  
  // 티커 표시
  elements.analysisTicker.classList.remove('hidden');
  
  // 페이드 아웃 후 새 메시지
  elements.tickerMessage.classList.add('fade-out');
  
  setTimeout(() => {
    elements.tickerMessage.textContent = message;
    elements.tickerMessage.classList.remove('fade-out');
  }, 150);
}

/**
 * 티커 숨기기
 */
function hideTicker() {
  if (elements.analysisTicker) {
    elements.analysisTicker.classList.add('hidden');
  }
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

function setLoadingState(loading) {
  elements.sendBtn.disabled = loading || !elements.chatInput.value.trim();
  updateStatus(loading ? 'loading' : 'ready', loading ? '검색 중...' : '준비 완료');
}

function scrollToBottom() {
  elements.chatContainer.scrollTop = elements.chatContainer.scrollHeight;
}

function renderSourceSelector() {
  if (!elements.sourceSelector) return;
  
  elements.sourceSelector.innerHTML = `
    <div class="flex items-center justify-between mb-2">
      <span class="text-xs font-medium text-gray-600">검색 범위 (1개만 선택)</span>
    </div>
    <div class="flex flex-wrap gap-2" id="sourceButtons">
      ${state.availableSources.map(source => {
        const isSelected = state.selectedSources.includes(source);
        const label = state.sourceLabels[source] || source;
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
  
  document.querySelectorAll('input[name="searchSource"]').forEach(checkbox => {
    checkbox.addEventListener('change', (e) => {
      toggleSource(e.target.value);
      renderSourceSelector();
    });
  });
}

function updateFiltersDisplay() {
  if (!elements.filterDisplay) return;
  
  if (state.latestFilters.length === 0 && Object.keys(state.knownContext).length === 0) {
    elements.filterDisplay.classList.add('hidden');
    return;
  }
  
  elements.filterDisplay.classList.remove('hidden');
  
  if (elements.filterChips) {
    elements.filterChips.innerHTML = state.latestFilters.map(filter => 
      `<span class="px-2 py-1 text-xs bg-gray-100 text-gray-700 rounded-full">${filter}</span>`
    ).join('') || '<span class="text-xs text-gray-400">없음</span>';
  }
  
  if (elements.filterConfidence && state.filterConfidence) {
    const confidenceColors = {
      high: 'text-green-600',
      medium: 'text-yellow-600',
      low: 'text-red-600'
    };
    elements.filterConfidence.className = `text-xs ${confidenceColors[state.filterConfidence] || 'text-gray-500'}`;
    elements.filterConfidence.textContent = `신뢰도: ${state.filterConfidence}`;
  }
}

function addMessage(role, content, sources = []) {
  const welcome = document.getElementById('welcomeMessage');
  if (welcome) welcome.remove();
  
  const messageId = 'msg-' + Date.now();
  const messageDiv = document.createElement('div');
  messageDiv.id = messageId;
  messageDiv.className = `flex ${role === 'user' ? 'justify-end' : 'justify-start'} animate-fade-in`;

  const isUser = role === 'user';
  const bgClass = isUser ? 'bg-blue-500 text-white' : 'bg-app-card border border-app-border';
  const roundedClass = isUser ? 'rounded-2xl rounded-tr-sm' : 'rounded-2xl rounded-tl-sm';

  let sourcesHtml = '';
  if (sources && sources.length > 0) {
    sourcesHtml = `
      <div class="mt-3 pt-3 border-t border-app-border">
        <p class="text-xs text-app-muted mb-2">참조 문서</p>
        <div class="flex flex-wrap gap-2">
          ${sources.map((source, idx) => {
            const ctx = source.retrievedContext || source.web || {};
            const title = ctx.title || '참조 ' + (idx + 1);
            const text = ctx.text || '';
            const uri = ctx.uri || '';
            return `
              <button 
                class="source-chip px-2 py-1 text-xs bg-app-bg border border-app-border text-app-muted rounded-md hover:border-blue-400 hover:bg-blue-50 transition-all cursor-pointer"
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

  const chips = messageDiv.querySelectorAll('.source-chip');
  chips.forEach(chip => {
    chip.addEventListener('click', async () => {
      await openModal(chip.dataset.title, chip.dataset.text, chip.dataset.uri);
    });
  });

  return messageId;
}

function addErrorMessage(errorText) {
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

function addLoadingMessage(text = '검색 중...') {
  const messageId = 'loading-' + Date.now();
  const messageDiv = document.createElement('div');
  messageDiv.id = messageId;
  messageDiv.className = 'flex justify-start';

  messageDiv.innerHTML = `
    <div class="max-w-[85%] bg-app-card border border-app-border rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm">
      <div class="flex items-center gap-2">
        <div class="flex gap-1">
          <span class="w-2 h-2 bg-gray-300 rounded-full animate-bounce" style="animation-delay: 0ms"></span>
          <span class="w-2 h-2 bg-gray-300 rounded-full animate-bounce" style="animation-delay: 150ms"></span>
          <span class="w-2 h-2 bg-gray-300 rounded-full animate-bounce" style="animation-delay: 300ms"></span>
        </div>
        <span class="text-sm text-gray-400">${escapeHtml(text)}</span>
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

/**
 * 모달 열기 (캐시 지원)
 * @param {string} title - 제목 (없으면 캐시에서 복원)
 * @param {string} content - 내용 (없으면 캐시에서 복원)
 * @param {string} uri - URI (없으면 캐시에서 복원)
 */
function openModal(title, content, uri) {
  if (!elements.sourceModal) return;

  // 인자가 있으면 캐시 갱신
  if (title || content || uri) {
    setModalCache({ title, content, uri });
  }
  
  // 캐시에서 값 가져오기
  const cache = state.modalCache || {};
  const displayTitle = title || cache.title || '참조 문서';
  const displayContent = content || cache.content || '';
  let displayUri = uri || cache.uri || '';

  // URI 수정
  if (displayUri) {
    displayUri = displayUri.replace('http://localhost:10001', 'https://wedosoft.net');
    displayUri = displayUri.replace('localhost:10001', 'wedosoft.net');
  }

  // 헤더 렌더링
  let headerHtml = `<span class="truncate" title="${escapeAttr(displayTitle)}">${escapeHtml(displayTitle)}</span>`;
  
  if (displayUri) {
    headerHtml += `
      <a href="${escapeAttr(displayUri)}" target="_blank" rel="noopener noreferrer" 
         class="flex-shrink-0 ml-2 px-2 py-1 bg-blue-50 hover:bg-blue-100 text-blue-600 border border-blue-200 text-xs rounded flex items-center gap-1 transition-colors"
         title="새 탭에서 원문 보기">
        <span>원본 보기</span>
        <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"/>
        </svg>
      </a>
    `;
  }
  
  elements.modalTitle.className = "font-semibold text-app-text flex items-center min-w-0 flex-1 mr-4";
  elements.modalTitle.innerHTML = headerHtml;
  
  // 내용 렌더링
  let html = `
    <div class="flex items-center mb-1">
      <span class="text-xs text-gray-400">참조 내용 (발췌)</span>
      <div class="flex-grow ml-2 border-t border-gray-100"></div>
    </div>
    <div class="bg-app-bg p-3 rounded-lg border border-app-border text-sm text-app-text leading-relaxed whitespace-pre-wrap">${formatMessage(displayContent || "내용이 없습니다.")}</div>
  `;
  
  elements.modalContent.innerHTML = html;
  elements.sourceModal.classList.remove('hidden');
}

function closeModal() {
  if (elements.sourceModal) {
    elements.sourceModal.classList.add('hidden');
  }
}

function formatMessage(text) {
  if (!text) return '';
  // 객체나 배열이면 JSON 문자열로 변환
  if (typeof text !== 'string') {
    try {
      text = JSON.stringify(text, null, 2);
    } catch (e) {
      text = String(text);
    }
  }
  return text
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/`([^`]+)`/g, '<code class="px-1 py-0.5 bg-app-bg border border-app-border rounded text-xs font-mono text-app-text">$1</code>')
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

function normalizeChoices(choices) {
  if (!choices) return [];
  if (Array.isArray(choices)) {
    if (choices.length > 0 && typeof choices[0] === 'string') {
       return choices.map(c => ({ value: c, choices: [] }));
    }
    return choices.map(c => ({ value: c.value, choices: normalizeChoices(c.choices) }));
  } else if (typeof choices === 'object') {
    return Object.keys(choices).map(key => ({
      value: key,
      choices: normalizeChoices(choices[key])
    }));
  }
  return [];
}

function findPathToValue(choices, targetValue) {
    for (const c of choices) {
        if (c.value === targetValue) return [c.value];
        if (c.choices && c.choices.length > 0) {
            const path = findPathToValue(c.choices, targetValue);
            if (path) return [c.value, ...path];
        }
    }
    return null;
}

function buildValuePathMap(choices, path = [], map = {}) {
    if (!Array.isArray(choices)) return map;
    choices.forEach(choice => {
        const currentPath = [...path, choice.value];
        map[choice.value] = currentPath;
        if (choice.choices && choice.choices.length > 0) {
            buildValuePathMap(choice.choices, currentPath, map);
        }
    });
    return map;
}

function ensureLeafOptions(messageId, fieldName) {
  const choices = window[`choices-${messageId}-${fieldName}`];
  if (!choices) return [];
  const targetDepthRaw = window[`leafTargetDepth-${messageId}-${fieldName}`];
  const targetDepth = (targetDepthRaw === undefined || targetDepthRaw === null)
    ? null
    : parseInt(String(targetDepthRaw), 10);
  const minDepthRaw = window[`leafMinDepth-${messageId}-${fieldName}`];
  const minDepth = (minDepthRaw === undefined || minDepthRaw === null)
    ? null
    : parseInt(String(minDepthRaw), 10);
  let leaves = window[`leafOptions-${messageId}-${fieldName}`];
  if (!Array.isArray(leaves) || leaves.length === 0) {
    if (Number.isFinite(targetDepth) && targetDepth > 0) {
      leaves = flattenLeafOptionsAtDepth(choices, targetDepth);
    } else if (Number.isFinite(minDepth) && minDepth > 0) {
      leaves = flattenLeafOptionsMinDepth(choices, minDepth);
    } else {
      leaves = flattenLeafOptions(choices);
    }
    window[`leafOptions-${messageId}-${fieldName}`] = leaves;
  }
  return leaves;
}

function flattenLeafOptions(choices, path = [], acc = []) {
    if (!Array.isArray(choices)) return acc;
    choices.forEach(choice => {
        const currentPath = [...path, choice.value];
        if (choice.choices && choice.choices.length > 0) {
            flattenLeafOptions(choice.choices, currentPath, acc);
        } else {
            acc.push({
                value: choice.value,
                label: currentPath.join(" / ")
            });
        }
    });
    return acc;
}

// 최소 깊이(minDepth) 이상의 leaf(자식 없는 노드)만 수집
// depth: 1부터 시작 (root choices의 첫 레벨이 1)
function flattenLeafOptionsMinDepth(choices, minDepth, depth = 1, path = [], acc = []) {
  if (!Array.isArray(choices)) return acc;
  choices.forEach(choice => {
    const currentPath = [...path, choice.value];
    const hasChildren = choice.choices && choice.choices.length > 0;

    if (hasChildren) {
      flattenLeafOptionsMinDepth(choice.choices, minDepth, depth + 1, currentPath, acc);
      return;
    }

    // leaf
    if (depth >= minDepth) {
      acc.push({
        value: choice.value,
        label: currentPath.join(" / ")
      });
    }
  });
  return acc;
}

// 특정 깊이(targetDepth)의 leaf(자식 없는 노드)만 수집
// depth: 1부터 시작 (root choices의 첫 레벨이 1)
function flattenLeafOptionsAtDepth(choices, targetDepth, depth = 1, path = [], acc = []) {
  if (!Array.isArray(choices)) return acc;
  choices.forEach(choice => {
    const currentPath = [...path, choice.value];
    const hasChildren = choice.choices && choice.choices.length > 0;

    if (depth === targetDepth) {
      if (!hasChildren) {
        acc.push({
          value: choice.value,
          label: currentPath.join(" / ")
        });
      }
      return;
    }

    if (hasChildren) {
      flattenLeafOptionsAtDepth(choice.choices, targetDepth, depth + 1, currentPath, acc);
    }
  });
  return acc;
}

function findLeafByInput(leaves, input) {
    if (!input) return null;
    const key = input.trim().toLowerCase();
    let found = leaves.find(l => String(l.value).toLowerCase() === key);
    if (found) return found;
    found = leaves.find(l => l.label.toLowerCase() === key);
    if (found) return found;
    return leaves.find(l => l.label.toLowerCase().includes(key));
}

function renderFieldSuggestions(proposal) {
  const updates = proposal.field_updates || proposal.fieldUpdates || {};
  // 하드코딩 금지: 제안/업데이트 허용 범위는 tenantConfig.selected_fields가 단일 기준
  const isAllowedByTenant = buildTenantFieldAllowChecker();
  const fieldProposals = (proposal.field_proposals || []).filter(p => {
    const name = p && typeof p === 'object' ? p.field_name : null;
    return name ? isAllowedByTenant(name) : true;
  });
  const proposalMap = {};
  fieldProposals.forEach(p => { proposalMap[p.field_name] = p; });
  const renderedFields = new Set();

  const messageId = 'msg-' + Date.now();
  const messageDiv = document.createElement('div');
  messageDiv.className = 'flex justify-start message-enter';
  messageDiv.id = messageId;
  
  let html = `
    <div class="max-w-[95%] bg-app-card border border-app-border rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm">
      <div class="flex items-center justify-between mb-3">
        <h3 class="text-sm font-bold text-app-text flex items-center gap-2">
          <svg class="w-4 h-4 text-app-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"/>
          </svg>
          필드 업데이트 제안
        </h3>
        <span class="text-xs bg-blue-50 text-blue-600 px-2 py-0.5 rounded-full font-medium">AI 분석</span>
      </div>

      <div class="mb-4 overflow-x-auto">
        <table class="w-full text-sm text-left">
          <thead class="text-xs text-app-muted bg-app-bg uppercase">
            <tr>
              <th class="px-2 py-2 w-20">필드</th>
              <th class="px-2 py-2 w-24">현재 값</th>
              <th class="px-2 py-2">제안 값 (수정 가능)</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-app-border">
  `;
  
  const ticketFields = state.ticketFields;
  const ticketData = state.ticketData;

  const getFieldDefByName = (name) => {
    if (!ticketFields || !Array.isArray(ticketFields)) return null;
    return ticketFields.find(f => f && typeof f === 'object' && f.name === name) || null;
  };

  const formatCurrentValue = (fieldName, value) => {
    if (value === undefined || value === null) return '-';
    if (typeof value === 'string' && value.trim() === '') return '-';

    if (Array.isArray(value)) {
      const s = value.map(v => String(v)).filter(Boolean).join(', ');
      return s || '-';
    }

    // priority/status: 숫자 코드를 라벨로 변환
    if ((fieldName === 'priority' || fieldName === 'status') && (typeof value === 'number' || /^-?\d+$/.test(String(value).trim()))) {
      const n = typeof value === 'number' ? value : parseInt(String(value).trim(), 10);
      if (!Number.isNaN(n)) {
        const def = getFieldDefByName(fieldName);
        const choices = def ? def.choices : null;

        if (choices && typeof choices === 'object' && !Array.isArray(choices)) {
          const label = choices[String(n)] || choices[n];
          if (label) return String(label);
        }

        if (fieldName === 'priority') {
          const m = { 1: 'Low', 2: 'Medium', 3: 'High', 4: 'Urgent' };
          if (m[n]) return m[n];
        }
      }
    }

    return String(value);
  };

  const renderRow = (label, fieldName, currentVal, inputHtml, reason) => `
    <tr>
      <td class="px-2 py-2 font-medium text-app-muted">
        ${label}
        ${reason ? `<div class="group relative inline-block ml-1">
          <svg class="w-3 h-3 text-gray-400 cursor-help" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
          <div class="invisible group-hover:visible absolute z-10 w-48 p-2 mt-1 text-xs text-white bg-gray-800 rounded shadow-lg -left-2">
            ${escapeHtml(reason)}
          </div>
        </div>` : ''}
      </td>
      <td class="px-2 py-2 text-app-muted text-xs">${escapeHtml(formatCurrentValue(fieldName, currentVal))}</td>
      <td class="px-2 py-2">${inputHtml}</td>
    </tr>
  `;

  if (fieldProposals.length > 0) {
    const nestedRoot = ticketFields ? ticketFields.find(f => f.type === 'nested_field') : null;
    if (nestedRoot && nestedRoot.choices && nestedRoot.nested_ticket_fields) {
      const nestedFields = nestedRoot.nested_ticket_fields;
      const level2Name = nestedFields.find(n => n.level === 2)?.name || nestedFields[0]?.name;
      const level3Name = nestedFields.find(n => n.level === 3)?.name || nestedFields[1]?.name;
      const hasNestedProposal = [nestedRoot.name, level2Name, level3Name].some(n => proposalMap[n]);

      if (hasNestedProposal) {
        const choices = normalizeChoices(nestedRoot.choices);
        window[`choices-${messageId}-${nestedRoot.name}`] = choices;
        window[`pathMap-${messageId}-${nestedRoot.name}`] = buildValuePathMap(choices);
        // Item 후보는 leaf 중에서도 depth>=2만 노출 (카테고리-only leaf 제외, 혼합 깊이 지원)
        window[`leafMinDepth-${messageId}-${nestedRoot.name}`] = 2;
        window[`leafOptions-${messageId}-${nestedRoot.name}`] = flattenLeafOptionsMinDepth(choices, 2);
        const leafOptions = ensureLeafOptions(messageId, nestedRoot.name);

        const proposedLeaf = proposalMap[level3Name]?.proposed_value || proposalMap[level2Name]?.proposed_value || proposalMap[nestedRoot.name]?.proposed_value || '';
        const path = findPathToValue(choices, proposedLeaf) || [];
        const val1 = path[0] || proposalMap[nestedRoot.name]?.proposed_value || '';
        const val2 = path[1] || proposalMap[level2Name]?.proposed_value || '';
        // depth=2 leaf인 경우에도 검색 입력에는 leaf 값을 보여줘야 함
        const val3Display = (path.length === 2 ? path[1] : (path[2] || proposalMap[level3Name]?.proposed_value || ''));
        // 실제 level3 업데이트 값은 depth=3일 때만 사용
        const val3Hidden = (path.length >= 3 ? (path[2] || '') : '');
        const searchInputId = `leafsearch-${nestedRoot.name}-${messageId}`;
        const datalistId = `leaflist-${nestedRoot.name}-${messageId}`;

        let opts1 = '<option value="">선택하세요</option>';
        choices.forEach(c => opts1 += `<option value="${c.value}" ${c.value === val1 ? 'selected' : ''}>${c.value}</option>`);

        let opts2 = '<option value="">선택하세요</option>';
        const subChoices = val1 ? choices.find(c => c.value === val1)?.choices : [];
        if (subChoices) subChoices.forEach(c => opts2 += `<option value="${c.value}" ${c.value === val2 ? 'selected' : ''}>${c.value}</option>`);

        // NOTE: Item 셀렉트는 제거됐지만, 기존 데이터 형태 보존을 위해 itemChoices 계산은 남겨둠
        // (val3는 scope에 없으므로 val3Hidden 기준으로 비교)
        let opts3 = '<option value="">선택하세요</option>';
        const itemChoices = val2 ? subChoices?.find(c => c.value === val2)?.choices : [];
        if (itemChoices) itemChoices.forEach(c => opts3 += `<option value="${c.value}" ${c.value === val3Hidden ? 'selected' : ''}>${c.value}</option>`);

        const currentVal1 = ticketData[nestedRoot.name] !== undefined ? ticketData[nestedRoot.name] : ticketData.custom_fields?.[nestedRoot.name];
        const currentVal2 = level2Name ? (ticketData[level2Name] !== undefined ? ticketData[level2Name] : ticketData.custom_fields?.[level2Name]) : undefined;
        const currentVal3 = level3Name ? (ticketData[level3Name] !== undefined ? ticketData[level3Name] : ticketData.custom_fields?.[level3Name]) : undefined;

        html += renderRow(nestedRoot.label || 'Category', nestedRoot.name, currentVal1, `
          <select id="input-${nestedRoot.name}-${messageId}-1" data-field-name="${nestedRoot.name}" data-level="1" onchange="updateDependentFields('${messageId}', '${nestedRoot.name}', 1)" class="w-full text-sm border-gray-300 rounded-md shadow-sm focus:border-blue-500 focus:ring-blue-500 py-1">
            ${opts1}
          </select>
        `, proposalMap[nestedRoot.name]?.reason);

        if (level2Name) {
          html += renderRow('Sub Category', level2Name, currentVal2, `
            <select id="input-${nestedRoot.name}-${messageId}-2" data-field-name="${level2Name}" data-level="2" onchange="updateDependentFields('${messageId}', '${nestedRoot.name}', 2)" class="w-full text-sm border-gray-300 rounded-md shadow-sm focus:border-blue-500 focus:ring-blue-500 py-1" ${!val1 ? 'disabled' : ''}>
              ${opts2}
            </select>
          `, proposalMap[level2Name]?.reason);
        }

        if (level3Name) {
          // Item(leaf)은 전체 검색 가능하도록 datalist 기반 입력만 제공
          html += renderRow('Item', level3Name, currentVal3, `
            <div class="mt-1 flex gap-2 items-center">
              <input id="${searchInputId}" list="${datalistId}" placeholder="항목 빠른 검색 (전체)" class="flex-1 text-sm border border-gray-300 rounded-md px-2 py-1 focus:border-blue-500 focus:ring-blue-500" value="${val3Display || ''}" oninput="handleLeafSearchApply('${messageId}', '${nestedRoot.name}', '${searchInputId}')">
              <input type="hidden" id="leafhidden-${nestedRoot.name}-${messageId}" data-field-name="${level3Name}" value="${val3Hidden || ''}">
              <button type="button" class="px-3 py-1 text-xs rounded-md border border-gray-300 hover:border-blue-500" onclick="handleLeafSearchApply('${messageId}', '${nestedRoot.name}', '${searchInputId}')">적용</button>
            </div>
            <datalist id="${datalistId}">
              ${leafOptions.slice(0, 2000).map(opt => `<option value="${opt.value}" label="${opt.label}"></option>`).join('')}
            </datalist>
            `, proposalMap[level3Name]?.reason);
        }

        renderedFields.add(nestedRoot.name);
        if (level2Name) renderedFields.add(level2Name);
        if (level3Name) renderedFields.add(level3Name);
      }
    }

    fieldProposals.forEach(prop => {
      if (renderedFields.has(prop.field_name)) return;
      if (!isAllowedByTenant(prop.field_name)) return;

      const fieldName = prop.field_name;
      const fieldLabel = prop.field_label;
      const proposedValue = prop.proposed_value;
      const reason = prop.reason;
      renderedFields.add(fieldName);
      
      const fieldDef = ticketFields ? ticketFields.find(f => f.name === fieldName) : null;
      let inputHtml = '';

      const isNested = (choices) => {
          if (!choices || !Array.isArray(choices)) return false;
          return choices.some(c => c.choices && c.choices.length > 0);
      };

      if (fieldDef && (fieldDef.type === 'custom_dropdown' || fieldDef.type === 'default_status' || fieldDef.type === 'default_priority' || fieldDef.choices)) {
             const choices = normalizeChoices(fieldDef.choices);
             
             if (isNested(choices)) {
                 window[`choices-${messageId}-${fieldName}`] = choices;
                 window[`pathMap-${messageId}-${fieldName}`] = buildValuePathMap(choices);
                 window[`leafOptions-${messageId}-${fieldName}`] = flattenLeafOptions(choices);
                 const searchInputId = `leafsearch-${fieldName}-${messageId}`;
                 const datalistId = `leaflist-${fieldName}-${messageId}`;

             const path = findPathToValue(choices, proposedValue) || [];
             const val1 = path[0] || '';
             const val2 = path[1] || '';
             const val3 = path[2] || '';

             let opts1 = '<option value="">선택하세요</option>';
             choices.forEach(c => opts1 += `<option value="${c.value}" ${c.value === val1 ? 'selected' : ''}>${c.value}</option>`);
             
             let opts2 = '<option value="">선택하세요</option>';
             const subChoices = val1 ? choices.find(c => c.value === val1)?.choices : [];
             if(subChoices) subChoices.forEach(c => opts2 += `<option value="${c.value}" ${c.value === val2 ? 'selected' : ''}>${c.value}</option>`);

             let opts3 = '<option value="">선택하세요</option>';
             const itemChoices = val2 ? subChoices?.find(c => c.value === val2)?.choices : [];
             if(itemChoices) itemChoices.forEach(c => opts3 += `<option value="${c.value}" ${c.value === val3 ? 'selected' : ''}>${c.value}</option>`);

             inputHtml = `
                <div class="flex flex-col gap-2">
                    <select id="input-${fieldName}-${messageId}-1" data-field-name="${fieldName}" data-level="1" onchange="updateDependentFields('${messageId}', '${fieldName}', 1)" class="w-full text-sm border-gray-300 rounded-md shadow-sm focus:border-blue-500 focus:ring-blue-500 py-1">${opts1}</select>
                    <select id="input-${fieldName}-${messageId}-2" data-field-name="${fieldName}" data-level="2" onchange="updateDependentFields('${messageId}', '${fieldName}', 2)" class="w-full text-sm border-gray-300 rounded-md shadow-sm focus:border-blue-500 focus:ring-blue-500 py-1" ${!val1 ? 'disabled' : ''}>${opts2}</select>
                    <select id="input-${fieldName}-${messageId}-3" data-field-name="${fieldName}" data-level="3" onchange="updateParentFields('${messageId}', '${fieldName}', 3)" class="w-full text-sm border-gray-300 rounded-md shadow-sm focus:border-blue-500 focus:ring-blue-500 py-1" ${!val2 ? 'disabled' : ''}>${opts3}</select>
                    <div class="flex gap-2 items-center">
                      <input id="${searchInputId}" list="${datalistId}" placeholder="3단계 빠른 검색" class="flex-1 text-sm border border-gray-300 rounded-md px-2 py-1 focus:border-blue-500 focus:ring-blue-500" oninput="handleLeafSearchApply('${messageId}', '${fieldName}', '${searchInputId}')">
                      <button type="button" class="px-3 py-1 text-xs rounded-md border border-gray-300 hover:border-blue-500" onclick="handleLeafSearchApply('${messageId}', '${fieldName}', '${searchInputId}')">적용</button>
                    </div>
                    <datalist id="${datalistId}">
                      ${window[`leafOptions-${messageId}-${fieldName}`].slice(0, 2000).map(opt => `<option value="${opt.value}" label="${opt.label}"></option>`).join('')}
                    </datalist>
                </div>
             `;
         } else {
             let optionsHtml = '<option value="">선택하세요</option>';
             const flatOptions = [];
             function collectOptions(list) {
                list.forEach(c => {
                   flatOptions.push(c.value);
                   if (c.choices) collectOptions(c.choices);
                });
             }
             collectOptions(choices);
             
             flatOptions.forEach(val => {
                optionsHtml += `<option value="${val}" ${val === proposedValue ? 'selected' : ''}>${val}</option>`;
             });

             inputHtml = `
                <select id="input-${fieldName}-${messageId}" data-field-name="${fieldName}" class="w-full text-sm border-gray-300 rounded-md shadow-sm focus:border-blue-500 focus:ring-blue-500 py-1">
                  ${optionsHtml}
                </select>
             `;
         }
      } else {
         inputHtml = `
            <input type="text" id="input-${fieldName}-${messageId}" data-field-name="${fieldName}" value="${proposedValue || ''}" class="w-full text-sm border-gray-300 rounded-md shadow-sm focus:border-blue-500 focus:ring-blue-500 py-1">
         `;
      }

      let currentVal = ticketData[fieldName];
      if (currentVal === undefined && ticketData.custom_fields) {
         currentVal = ticketData.custom_fields[fieldName];
      }

      html += renderRow(fieldLabel, fieldName, currentVal, inputHtml, reason);
    });

  }
  
  html += `
          </tbody>
        </table>
      </div>
  `;

  const justification = proposal.justification || proposal.reasoning;
  if (justification) {
    html += `
      <div class="mb-3 px-2 py-2 bg-app-bg rounded border border-app-border">
        <p class="text-xs text-app-muted"><span class="font-semibold text-app-text">AI 근거:</span> ${justification}</p>
      </div>
    `;
  }
  
  html += `
      <button onclick="applyEditableFieldUpdates('${messageId}')" class="w-full py-2 bg-app-primary hover:bg-app-primary-hover text-white text-sm font-medium rounded-lg transition-colors flex items-center justify-center gap-2">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
        </svg>
        변경 사항 적용하기
      </button>
    </div>
  `;
  
  messageDiv.innerHTML = html;
  elements.chatMessages.appendChild(messageDiv);
  scrollToBottom();
}

// --- Global Window Handlers ---

window.updateDependentFields = function(messageId, fieldName, level) {
    const choices = window[`choices-${messageId}-${fieldName}`];
    const el1 = document.getElementById(`input-${fieldName}-${messageId}-1`);
    const el2 = document.getElementById(`input-${fieldName}-${messageId}-2`);
    // el3는 이제 검색 입력 필드와 datalist로 대체됨
    const elSearch = document.getElementById(`leafsearch-${fieldName}-${messageId}`);
    const elDatalist = document.getElementById(`leaflist-${fieldName}-${messageId}`);
    const elHiddenLeaf = document.getElementById(`leafhidden-${fieldName}-${messageId}`);
    
    const val1 = el1 ? el1.value : '';
    
    if (level === 1) {
        let opts2 = '<option value="">선택하세요</option>';
        const subChoices = val1 ? choices.find(c => c.value === val1)?.choices : [];
        if (subChoices) {
            subChoices.forEach(c => opts2 += `<option value="${c.value}">${c.value}</option>`);
            if (el2) {
                el2.innerHTML = opts2;
                el2.disabled = false;
                el2.value = '';
            }
        } else {
            if (el2) {
                el2.innerHTML = '<option value="">선택하세요</option>';
                el2.disabled = true;
                el2.value = '';
            }
        }
      // Level 1 변경 시 leaf 입력만 초기화 (datalist/leafOptions는 전체 목록 유지)
        if (elSearch) {
            elSearch.value = '';
            if (elHiddenLeaf) {
                elHiddenLeaf.value = '';
            }
        if (elDatalist) {
          const leaves = ensureLeafOptions(messageId, fieldName);
          elDatalist.innerHTML = leaves.slice(0, 2000).map(opt => `<option value="${opt.value}" label="${opt.label}"></option>`).join('');
        }
        }
    } else if (level === 2) {
        const val2 = el2 ? el2.value : '';
      // Level 2는 부모 셀렉트로만 제한하고, leaf 검색은 전체에서 가능하도록 유지
        if (elSearch) {
            elSearch.value = '';
            if (elHiddenLeaf) {
                elHiddenLeaf.value = '';
            }
        if (elDatalist) {
          const leaves = ensureLeafOptions(messageId, fieldName);
          elDatalist.innerHTML = leaves.slice(0, 2000).map(opt => `<option value="${opt.value}" label="${opt.label}"></option>`).join('');
        }
        }
    }
};

window.updateParentFields = function(messageId, fieldName, level, targetValue) {
    if (level !== 3) return;

    const choices = window[`choices-${messageId}-${fieldName}`];
    const pathMap = window[`pathMap-${messageId}-${fieldName}`];
    // el3 대신 검색 입력 필드 사용
    const elSearch = document.getElementById(`leafsearch-${fieldName}-${messageId}`);
    const elHiddenLeaf = document.getElementById(`leafhidden-${fieldName}-${messageId}`);
    const val3 = targetValue !== undefined ? targetValue : (elSearch ? elSearch.value : '');
    
    if (!val3) return;

    let path = pathMap ? pathMap[val3] : null;
    if (!path && choices) {
        path = findPathToValue(choices, val3);
    }
    
    if (path && path.length >= 3) {
        const [val1, val2] = path;
        const el1 = document.getElementById(`input-${fieldName}-${messageId}-1`);
        const el2 = document.getElementById(`input-${fieldName}-${messageId}-2`);
        
        if (el1) {
            const needUpdate = el1.value !== val1 || (el2 && (el2.disabled || el2.options.length <= 1));
            if (needUpdate) {
                el1.value = val1;
                window.updateDependentFields(messageId, fieldName, 1);
            }
        }
        
        if (el2) {
            const needUpdate = el2.value !== val2; // el3 체크 제거 (datalist는 항상 존재)
            if (needUpdate) {
                el2.value = val2;
                window.updateDependentFields(messageId, fieldName, 2);
            }
        }
        
        if (elSearch && elSearch.value !== val3) {
            elSearch.value = val3;
        }

        // depth=3 leaf: hidden(field 실제 업데이트 대상)도 세팅
        if (elHiddenLeaf) {
          elHiddenLeaf.value = val3;
        }
      } else if (path && path.length === 2) {
        // depth=2 leaf: level2에 leaf가 들어가고, level3(아이템)은 비워야 함
        const [val1, val2Leaf] = path;
        const el1 = document.getElementById(`input-${fieldName}-${messageId}-1`);
        const el2 = document.getElementById(`input-${fieldName}-${messageId}-2`);

        if (el1) {
          const needUpdate = el1.value !== val1 || (el2 && (el2.disabled || el2.options.length <= 1));
          if (needUpdate) {
            el1.value = val1;
            window.updateDependentFields(messageId, fieldName, 1);
          }
        }

        if (el2) {
          const needUpdate = el2.value !== val2Leaf;
          if (needUpdate) {
            el2.value = val2Leaf;
            window.updateDependentFields(messageId, fieldName, 2);
          }
        }

        if (elSearch && elSearch.value !== val3) {
          elSearch.value = val3;
        }

        if (elHiddenLeaf) {
          elHiddenLeaf.value = '';
        }
      } else if (path && path.length === 1) {
        // depth=1 leaf는 Item 후보에 포함하지 않지만, 방어적으로 처리
        const [val1Leaf] = path;
        const el1 = document.getElementById(`input-${fieldName}-${messageId}-1`);
        const el2 = document.getElementById(`input-${fieldName}-${messageId}-2`);
        if (el1) {
          el1.value = val1Leaf;
          window.updateDependentFields(messageId, fieldName, 1);
        }
        if (el2) {
          el2.value = '';
          el2.disabled = true;
        }
        if (elSearch) {
          elSearch.value = val3;
        }
        if (elHiddenLeaf) {
          elHiddenLeaf.value = '';
        }
    }
};

window.handleLeafSearchApply = function(messageId, fieldName, inputId) {
    const choices = window[`choices-${messageId}-${fieldName}`];
    const elInput = document.getElementById(inputId);
    if (!choices || !elInput) return;

  const leaves = ensureLeafOptions(messageId, fieldName);

    const userInput = elInput.value;
    if (!userInput) return;

    // 정확히 일치하는 값이 있는지 확인 (값 또는 라벨)
    const exactMatch = leaves.find(l => l.value === userInput || l.label === userInput);
    
    if (exactMatch) {
        // 정확히 일치하면 즉시 업데이트
        // updateParentFields는 el3 값을 읽거나 targetValue를 받음
        window.updateParentFields(messageId, fieldName, 3, exactMatch.value);
        elInput.classList.remove("ring-2", "ring-red-400");
        elInput.classList.add("ring-2", "ring-green-400");
        setTimeout(() => elInput.classList.remove("ring-2", "ring-green-400"), 1000);
    } else {
        // 일치하지 않으면 (타이핑 중) 아무것도 하지 않음 (빨간 테두리 제거)
        // 사용자가 datalist에서 선택하면 exactMatch가 됨
    }
};

window.applyEditableFieldUpdates = async function(messageId) {
  const { client, ticketData } = state;
  if (!client || !ticketData) return;

  const notify = (type, message) => {
    try {
      if (client.interface && typeof client.interface.trigger === 'function') {
        const maybePromise = client.interface.trigger('showNotify', { type, message });
        // Interface API가 존재하지만 런타임에서 사용 불가하면 Promise reject로 떨어질 수 있음
        if (maybePromise && typeof maybePromise.catch === 'function') {
          maybePromise.catch(() => {
            console.log(`[Notify:${type}] ${message}`);
          });
        }
        return;
      }
    } catch (e) {
      // ignore and fallback
    }
    // Fallback for environments where InterfaceAPI isn't available (e.g., direct localhost preview)
    console.log(`[Notify:${type}] ${message}`);
  };
  
  try {
    const messageDiv = document.getElementById(messageId);
    if (!messageDiv) throw new Error("메시지 요소를 찾을 수 없습니다.");

    const inputs = messageDiv.querySelectorAll('[data-field-name]');
    if (inputs.length === 0) {
        throw new Error("업데이트할 필드를 찾을 수 없습니다.");
    }

    const updateBody = {};
    const customFields = {};
    // 하드코딩 금지: 업데이트 허용 범위는 tenantConfig.selected_fields가 단일 기준
    const isAllowedByTenant = buildTenantFieldAllowChecker();
    const standardFields = ['status', 'priority', 'type', 'group_id', 'responder_id', 'tags']; 

    // Freshdesk ticket_fields 기반 allowlist: 존재하지 않는 필드 전송으로 인한 invalid_field를 선제 방지
    const allowedFieldNames = new Set();
    if (Array.isArray(state.ticketFields)) {
      state.ticketFields.forEach(f => {
        if (!f || typeof f !== 'object') return;
        if (f.name) allowedFieldNames.add(f.name);
        if (Array.isArray(f.nested_ticket_fields)) {
          f.nested_ticket_fields.forEach(n => {
            if (n && typeof n === 'object' && n.name) allowedFieldNames.add(n.name);
          });
        }
      });
    }
    standardFields.forEach(n => allowedFieldNames.add(n));

    const skippedUnknownFields = [];

    const extractInvalidFieldsFromError = (parsedError) => {
      const invalids = [];
      if (!parsedError || typeof parsedError !== 'object') return invalids;
      const errs = Array.isArray(parsedError.errors) ? parsedError.errors : [];

      errs.forEach(e => {
        if (!e || typeof e !== 'object') return;
        const code = e.code;
        const field = e.field;
        const msg = typeof e.message === 'string' ? e.message : '';

        if (code === 'invalid_field') {
          if (typeof field === 'string' && field.trim()) {
            invalids.push(field.trim());
          }
          // message에서 'cf_xxx' 또는 'some_field' 추출 (Freshdesk 에러 포맷 대응)
          const m = msg.match(/'([^']+)'/g);
          if (m && m.length) {
            m.forEach(token => {
              const name = token.replace(/^'+|'+$/g, '').trim();
              if (name) invalids.push(name);
            });
          }
        }
      });

      // unique
      return Array.from(new Set(invalids));
    };

    const coerceStandardNumeric = (fieldName, rawValue) => {
      const raw = rawValue === null || rawValue === undefined ? '' : String(rawValue).trim();
      if (!raw) return null;

      // already numeric
      if (/^-?\d+$/.test(raw)) {
        const n = parseInt(raw, 10);
        if (Number.isNaN(n)) {
          throw new Error(`${fieldName} 값을 숫자로 해석할 수 없습니다: ${rawValue}`);
        }
        return n;
      }

      // attempt mapping from ticket field choices (common for default_priority/default_status)
      const fieldDef = state.ticketFields ? state.ticketFields.find(f => f.name === fieldName) : null;
      const choices = fieldDef ? fieldDef.choices : null;
      const key = raw.toLowerCase();

      const tryMapFromChoices = () => {
        if (!choices) return null;

        // choices as object: { "1": "Low", "2": "Medium", ... }
        if (typeof choices === 'object' && !Array.isArray(choices)) {
          for (const [k, v] of Object.entries(choices)) {
            const kStr = String(k).trim();
            const kNum = /^-?\d+$/.test(kStr) ? parseInt(kStr, 10) : null;
            const vStr = (typeof v === 'string') ? v.trim() : '';

            if (vStr && vStr.toLowerCase() === key && kNum !== null && !Number.isNaN(kNum)) {
              return kNum;
            }
            if (kStr.toLowerCase() === key && kNum !== null && !Number.isNaN(kNum)) {
              return kNum;
            }
          }
        }

        // choices as array of objects: [{value: 1, label: 'Low'}, ...] (best-effort)
        if (Array.isArray(choices)) {
          for (const item of choices) {
            if (!item || typeof item !== 'object') continue;
            const label = (item.label || item.name || item.value || '').toString().trim();
            const value = item.value;
            if (label && label.toLowerCase() === key && /^-?\d+$/.test(String(value))) {
              const n = parseInt(String(value), 10);
              if (!Number.isNaN(n)) return n;
            }
          }
        }

        return null;
      };

      const mapped = tryMapFromChoices();
      if (mapped !== null) return mapped;

      // fallback mapping for priority labels (Freshdesk commonly uses 1..4)
      if (fieldName === 'priority') {
        const priorityMap = {
          low: 1,
          medium: 2,
          high: 3,
          urgent: 4,
          // Korean
          '낮음': 1,
          '보통': 2,
          '중간': 2,
          '높음': 3,
          '긴급': 4
        };
        if (priorityMap[key] !== undefined) return priorityMap[key];
      }

      throw new Error(`${fieldName} 값이 숫자여야 합니다. 현재 값: ${rawValue}`);
    };

    const fieldGroups = {};
    inputs.forEach(input => {
        const fieldName = input.dataset.fieldName;
        if (!fieldGroups[fieldName]) {
            fieldGroups[fieldName] = [];
        }
        fieldGroups[fieldName].push(input);
    });

    for (const [fieldName, groupInputs] of Object.entries(fieldGroups)) {
        if (!isAllowedByTenant(fieldName)) continue;
        let valueToUpdate = null;

        if (groupInputs.length > 1) {
            for (let i = groupInputs.length - 1; i >= 0; i--) {
                if (groupInputs[i].value) {
                    valueToUpdate = groupInputs[i].value;
                    break;
                }
            }
        } else {
            valueToUpdate = groupInputs[0].value;
        }

        if (valueToUpdate === '' || valueToUpdate === null || valueToUpdate === undefined) continue;

        // allowlist에 없는 필드는 전송하지 않음 (invalid_field 방지)
        if (!allowedFieldNames.has(fieldName)) {
          skippedUnknownFields.push(fieldName);
          continue;
        }

        if (standardFields.includes(fieldName)) {
          if (['priority', 'status', 'group_id', 'responder_id'].includes(fieldName)) {
            const n = coerceStandardNumeric(fieldName, valueToUpdate);
            if (n === null) continue;
            updateBody[fieldName] = n;
            } else {
                updateBody[fieldName] = valueToUpdate;
            }
        } else {
            customFields[fieldName] = valueToUpdate;
        }
    }

    if (Object.keys(customFields).length > 0) {
      updateBody.custom_fields = customFields;
    }

    if (skippedUnknownFields.length > 0) {
      console.warn('Skipped unknown fields (not in ticket_fields allowlist):', skippedUnknownFields);
    }

    console.log('Updating ticket with:', updateBody);

    if (Object.keys(updateBody).length === 0) {
      notify('warning', '변경할 필드 값이 선택되지 않았습니다.');
      return;
    }

    const invokeUpdate = async (bodyObj) => {
      return await client.request.invokeTemplate("updateTicket", {
        context: {
          ticketId: ticketData.id
        },
        body: JSON.stringify(bodyObj)
      });
    };

    let response = await invokeUpdate(updateBody);

    if (response.status === 200) {
      notify('success', '티켓이 성공적으로 업데이트되었습니다.');
    } else {
      // Try to extract validation details from Freshdesk error payload
      let detail = '';
      let parsed = null;
      try {
        parsed = JSON.parse(response.response);
        if (parsed && parsed.description) {
          detail += parsed.description;
        }
        if (parsed && Array.isArray(parsed.errors) && parsed.errors.length > 0) {
          const first = parsed.errors[0];
          const field = first.field ? `field=${first.field}` : '';
          const msg = first.message || '';
          const code = first.code ? `code=${first.code}` : '';
          const parts = [field, code].filter(Boolean).join(', ');
          detail += (detail ? ' ' : '') + [parts, msg].filter(Boolean).join(' ');
        }
      } catch (e) {
        // ignore parse errors
      }

      // invalid_field가 섞여도 가능한 필드는 적용되도록: invalid 필드 제거 후 1회 재시도
      if (parsed) {
        const invalids = extractInvalidFieldsFromError(parsed);
        if (invalids.length > 0) {
          const retryBody = { ...updateBody };
          let removed = [];

          // top-level 표준 필드 제거
          invalids.forEach(name => {
            if (Object.prototype.hasOwnProperty.call(retryBody, name)) {
              delete retryBody[name];
              removed.push(name);
            }
          });

          // custom_fields 제거
          if (retryBody.custom_fields && typeof retryBody.custom_fields === 'object') {
            const filteredCustom = { ...retryBody.custom_fields };
            invalids.forEach(name => {
              if (Object.prototype.hasOwnProperty.call(filteredCustom, name)) {
                delete filteredCustom[name];
                removed.push(name);
              }
            });
            if (Object.keys(filteredCustom).length > 0) {
              retryBody.custom_fields = filteredCustom;
            } else {
              delete retryBody.custom_fields;
            }
          }

          removed = Array.from(new Set(removed));

          if (removed.length > 0) {
            console.warn('Retrying update after removing invalid fields:', removed);
            response = await invokeUpdate(retryBody);
            if (response.status === 200) {
              notify('success', `티켓이 업데이트되었습니다. (제외된 필드: ${removed.join(', ')})`);
              return;
            }
          }
        }
      }

      const suffix = detail ? ` (${detail})` : '';
      throw new Error(`API Error: ${response.status}${suffix}`);
    }
    
  } catch (error) {
    console.error("필드 업데이트 실패:", error);
    const errorMsg = (error && error.message)
      ? error.message
      : (typeof error === 'string'
        ? error
        : (() => {
          try { return JSON.stringify(error); } catch (e) { return String(error); }
        })());
    notify('danger', '필드 업데이트 중 오류가 발생했습니다: ' + errorMsg);
  }
};

// =============================================================================
// Main Section
// =============================================================================

console.log('[AI Copilot] app.js loaded');

let isModalView = false;

document.onreadystatechange = function() {
  if (document.readyState === "complete") {
    if (typeof app !== 'undefined') {
      app.initialized().then(async function(_client) {
        setClient(_client);
        const context = await _client.instance.context();
        // context.location 체크 대신 data 파라미터 확인 (더 확실함)
        // 하지만 context.location이 'modal'인 경우도 있으므로 둘 다 체크
        isModalView = context.location === 'modal' || (context.data && context.data.isModal);
        
        console.log('[App] Context:', context, 'isModalView:', isModalView);

        // 메인 페이지: 클릭시 모달 열기
        if (!isModalView) {
          _client.events.on("app.activated", async () => {
            try {
              if (_client.interface && typeof _client.interface.trigger === 'function') {
                const p = _client.interface.trigger("showModal", {
                  title: "AI Copilot",
                  template: "index.html",
                  noBackdrop: true,
                  data: { isModal: true } // 모달임을 명시
                });
                if (p && typeof p.catch === 'function') {
                  await p;
                }
              } else {
                console.warn('[App] InterfaceAPI not available: cannot open modal');
              }
            } catch (e) {
              console.warn('[App] Failed to open modal (InterfaceAPI unavailable):', e);
            }
          });
          return;
        }

        // 모달 뷰: 비즈니스 로직 실행
        cacheElements();
        setupEventListeners();
        
        // 보안 파라미터 로드 (SSE fetch용)
        await loadSecureConfig();

        // 테넌트 설정 로드 (selected_fields 등)
        await loadTenantConfig();
        
        await loadTicketData();
        await loadTicketFields();
        await loadStatus();
        await createSession();
        
        // 기본 탭: 분석
        switchTab('analysis');
        
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

function setupEventListeners() {
  const elements = getElements();
  
  // 탭 전환 이벤트
  if (elements.tabAnalysis) {
    elements.tabAnalysis.addEventListener('click', () => switchTab('analysis'));
  }
  if (elements.tabChat) {
    elements.tabChat.addEventListener('click', () => switchTab('chat'));
  }
  
  // 채팅 이벤트
  if (elements.chatForm) {
    elements.chatForm.addEventListener('submit', handleSubmit);
  }
  if (elements.chatInput) {
    elements.chatInput.addEventListener('input', handleInputChange);
    elements.chatInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSubmit(e);
      }
    });
  }
  if (elements.newChatBtn) {
    elements.newChatBtn.addEventListener('click', handleNewChat);
  }
  
  // 분석 버튼
  if (elements.analyzeBtn) {
    elements.analyzeBtn.addEventListener('click', handleAnalyzeTicket);
  }

  // 필드 제안 버튼
  if (elements.fieldProposalsBtn) {
    elements.fieldProposalsBtn.addEventListener('click', handleProposeFieldsOnly);
  }
  
  // 모달 이벤트
  if (elements.closeModalBtn) {
    elements.closeModalBtn.addEventListener('click', closeModal);
  }
  if (elements.sourceModal) {
    elements.sourceModal.addEventListener('click', (e) => {
      if (e.target === elements.sourceModal) closeModal();
    });
  }

  // 예시 질문
  document.querySelectorAll('.example-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const question = btn.textContent.trim();
      elements.chatInput.value = question;
      handleInputChange();
      // 채팅 탭으로 전환 후 제출
      switchTab('chat');
      setTimeout(() => handleSubmit(new Event('submit')), 100);
    });
  });
}

async function handleProposeFieldsOnly() {
  if (state.isLoading || !state.ticketData) return;

  setLoading(true);
  updateStatus('loading', '필드 제안 중...');

  if (elements.analysisPlaceholder) {
    elements.analysisPlaceholder.classList.add('hidden');
  }

  showTicker('analyzing');

  try {
    const payload = {
      ticket_id: String(state.ticketData.id),
      subject: state.ticketData.subject,
      description: state.ticketData.description_text,
      ticket_fields: state.ticketFields,
      fields_only: true,
      fieldsOnly: true
    };

    const result = await window.StreamUtils.streamFieldProposals(payload, (event) => {
      const eventType = event.type || event;
      const eventData = event.data || {};
      showTicker(eventType, eventData);
      console.log('[FieldProposals] Progress:', eventType, eventData);
    });

    hideTicker();

    // result는 complete.data (proposal/analysis/search/timingMs)
    const analysis = (result && result.analysis) ? result.analysis : null;
    const proposal = (result && result.proposal) ? result.proposal : null;

    // 기존 렌더러는 proposal 형태를 기대하므로 proposal을 우선 사용
    const merged = {
      ...(analysis || {}),
      ...(proposal || {})
    };

    setAnalysisResult(merged);
    renderAnalysisResult(merged);

  } catch (error) {
    console.error('필드 제안 실패:', error);
    hideTicker();
    renderAnalysisError(`필드 제안 오류: ${error.message}`);
  } finally {
    setLoading(false);
    updateStatus('ready', '준비 완료');
  }
}

async function createSession() {
  const result = await apiCall('POST', 'api/session');
  setSessionId(result.sessionId);
  console.log('세션 생성:', result.sessionId);
}

async function loadStatus() {
  const status = await apiCall('GET', 'api/status');
  console.log('Status:', status);
  
  if (!status.availableSources || status.availableSources.length === 0) {
    throw new Error('사용 가능한 검색 소스가 없습니다.');
  }
  
  setAvailableSources(status.availableSources);
  setSelectedSources([status.availableSources[0]]);
  
  setSourceLabels({
    tickets: '🎫 티켓',
    articles: '📄 헬프센터',
    common: '📦 제품 매뉴얼'
  });
  
  renderSourceSelector();
}

async function loadTicketData() {
  const { client } = state;
  const data = await client.data.get('ticket');
  const ticketId = data.ticket.id;
  const fdkTicket = data && data.ticket ? data.ticket : null;

  const response = await client.request.invokeTemplate('getTicketWithConversations', {
    context: { ticketId }
  });

  if (response.status !== 200) {
    throw new Error(`티켓 로드 실패: ${response.status}`);
  }
  
  const ticketData = JSON.parse(response.response);

  // Freshdesk ticket API 응답에 일부 필드가 누락/비어있는 경우가 있어(FDK 컨텍스트가 더 풍부한 경우)
  // FDK ticket 값을 기준으로 보완합니다. (예: type)
  if (fdkTicket && typeof fdkTicket === 'object') {
    for (const [k, v] of Object.entries(fdkTicket)) {
      if (ticketData[k] === undefined || ticketData[k] === null || ticketData[k] === '') {
        ticketData[k] = v;
      }
    }

    if (fdkTicket.custom_fields && typeof fdkTicket.custom_fields === 'object') {
      ticketData.custom_fields = ticketData.custom_fields || {};
      for (const [k, v] of Object.entries(fdkTicket.custom_fields)) {
        if (ticketData.custom_fields[k] === undefined || ticketData.custom_fields[k] === null || ticketData.custom_fields[k] === '') {
          ticketData.custom_fields[k] = v;
        }
      }
    }
  }

  // Freshdesk 환경에 따라 type 필드명이 다를 수 있어(ticket_fields에서 ticket_type 등)
  // 서로 보완해 UI 표시/업데이트 제안에 활용한다.
  if ((ticketData.type === undefined || ticketData.type === null || ticketData.type === '') && ticketData.ticket_type) {
    ticketData.type = ticketData.ticket_type;
  }
  if ((ticketData.ticket_type === undefined || ticketData.ticket_type === null || ticketData.ticket_type === '') && ticketData.type) {
    ticketData.ticket_type = ticketData.type;
  }
  
  try {
    const allConversations = await fetchAllConversations(ticketId);
    if (allConversations.length > (ticketData.conversations?.length || 0)) {
      ticketData.conversations = allConversations;
      console.log(`전체 대화 내역 로드 완료: ${allConversations.length}개`);
    }
  } catch (error) {
    console.error('대화 내역 추가 로드 실패:', error);
  }

  setTicketData(ticketData);
  
  // 티켓 전환 시 캐시 초기화
  setModalCache(null);
  setAnalysisResult(null);
  
  const elements = getElements();
  if (elements.headerTitle) {
      elements.headerTitle.textContent = `티켓 #${ticketId}`;
  }
  console.log('티켓 로드 완료:', ticketData);
}

async function loadTicketFields() {
  const { client } = state;
  try {
    const response = await client.request.invokeTemplate("getTicketFields", {});
    
    if (response.status === 200) {
      const fields = JSON.parse(response.response);
      setTicketFields(fields);
      console.log('Ticket Fields Loaded:', fields);
    } else {
      console.error('Failed to load ticket fields:', response);
    }
  } catch (error) {
    console.error('Error loading ticket fields:', error);
  }
}

async function fetchAllConversations(ticketId) {
  const { client } = state;
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
      
      if (page > 20) hasMore = false;
      
    } catch (e) {
      console.error(`대화 페이지 ${page} 처리 중 오류:`, e);
      break;
    }
  }
  
  conversations.sort((a, b) => new Date(a.created_at) - new Date(b.created_at));
  
  return conversations;
}

async function handleSubmit(e) {
  e.preventDefault();
  
  const elements = getElements();
  const message = elements.chatInput.value.trim();
  if (!message || state.isLoading) return;

  addMessage('user', message);
  
  setTimeout(() => {
    elements.chatInput.value = '';
    handleInputChange();
  }, 0);

  setLoading(true);
  setLoadingState(true);
  
  // 스트리밍 메시지 ID 생성
  const streamingMsgId = addStreamingMessage();

  try {
    const response = await sendChatStreaming(message, (partialText, sources) => {
      // 스트리밍 중 메시지 업데이트
      updateStreamingMessage(streamingMsgId, partialText);
    });
    
    // 스트리밍 완료 - 최종 메시지로 교체
    finalizeStreamingMessage(streamingMsgId, response.text, response.groundingChunks);
    
    setLatestFilters(response.filters);
    setFilterConfidence(response.filterConfidence);
    setKnownContext(response.knownContext);
    updateFiltersDisplay();
    
    addChatHistory({ role: 'user', content: message });
    addChatHistory({ role: 'assistant', content: response.text });
    
  } catch (error) {
    console.error('채팅 실패:', error);
    removeMessage(streamingMsgId);
    addErrorMessage(`오류: ${error.message}`);
  } finally {
    setLoading(false);
    setLoadingState(false);
  }
}

/**
 * 스트리밍 메시지 추가 (타이핑 효과용)
 */
function addStreamingMessage() {
  const welcome = document.getElementById('welcomeMessage');
  if (welcome) welcome.remove();
  
  const messageId = 'streaming-' + Date.now();
  const messageDiv = document.createElement('div');
  messageDiv.id = messageId;
  messageDiv.className = 'flex justify-start animate-fade-in';

  messageDiv.innerHTML = `
    <div class="max-w-[85%] bg-app-card border border-app-border rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm">
      <div class="text-sm whitespace-pre-wrap streaming-cursor" id="${messageId}-content"></div>
    </div>
  `;

  elements.chatMessages.appendChild(messageDiv);
  scrollToBottom();
  return messageId;
}

/**
 * 스트리밍 메시지 업데이트
 */
function updateStreamingMessage(messageId, text) {
  const contentEl = document.getElementById(`${messageId}-content`);
  if (contentEl) {
    contentEl.innerHTML = formatMessage(text);
    scrollToBottom();
  }
}

/**
 * 스트리밍 완료 - 최종 메시지로 변환
 */
function finalizeStreamingMessage(messageId, text, sources = []) {
  const messageDiv = document.getElementById(messageId);
  if (!messageDiv) return;

  let sourcesHtml = '';
  if (sources && sources.length > 0) {
    sourcesHtml = `
      <div class="mt-3 pt-3 border-t border-app-border">
        <p class="text-xs text-app-muted mb-2">참조 문서</p>
        <div class="flex flex-wrap gap-2">
          ${sources.map((source, idx) => {
            const ctx = source.retrievedContext || source.web || {};
            const title = ctx.title || '참조 ' + (idx + 1);
            const sourceText = ctx.text || '';
            const uri = ctx.uri || '';
            return `
              <button 
                class="source-chip px-2 py-1 text-xs bg-app-bg border border-app-border text-app-muted rounded-md hover:border-blue-400 hover:bg-blue-50 transition-all cursor-pointer"
                data-title="${escapeAttr(title)}"
                data-text="${escapeAttr(sourceText)}"
                data-uri="${escapeAttr(uri)}"
              >📄 ${escapeHtml(title)}</button>
            `;
          }).join('')}
        </div>
      </div>
    `;
  }

  messageDiv.innerHTML = `
    <div class="max-w-[85%] bg-app-card border border-app-border rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm">
      <div class="text-sm whitespace-pre-wrap">${formatMessage(text)}</div>
      ${sourcesHtml}
    </div>
  `;

  // 참조 문서 칩 이벤트 바인딩
  const chips = messageDiv.querySelectorAll('.source-chip');
  chips.forEach(chip => {
    chip.addEventListener('click', async () => {
      await openModal(chip.dataset.title, chip.dataset.text, chip.dataset.uri);
    });
  });

  scrollToBottom();
}

/**
 * 채팅 메시지 전송 (SSE 스트리밍)
 */
async function sendChatStreaming(message, onChunk) {
  const payload = {
    query: message,
    sessionId: state.sessionId
  };
  
  if (state.selectedSources.length > 0) {
    payload.sources = state.selectedSources;
  }

  if (state.ticketData) {
    const minimalTicket = minimizeTicketData(state.ticketData);
    payload.context = {
      ticket: minimalTicket
    };
    const convCount = minimalTicket.conversations ? minimalTicket.conversations.length : 0;
    console.log(`Sending chat with ticket context: ID=${minimalTicket.id}, Conversations=${convCount}`);
  }
  
  // SSE 스트리밍 시도
  try {
    const response = await window.StreamUtils.streamChat(payload, onChunk);
    return response;
  } catch (error) {
    console.warn('[Chat] SSE 실패, fallback to invokeTemplate:', error.message);
    // Fallback: 기존 apiCall 사용
    return await apiCall('POST', 'api/chat', payload);
  }
}

function minimizeTicketData(original) {
  if (!original) return null;
  
  const minimal = {
    id: original.id,
    subject: original.subject,
    description_text: original.description_text,
    status: original.status,
    priority: original.priority,
    created_at: original.created_at,
    updated_at: original.updated_at
  };
  
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
  const elements = getElements();
  const hasText = elements.chatInput.value.trim().length > 0;
  elements.sendBtn.disabled = !hasText || state.isLoading;
  
  elements.chatInput.style.height = 'auto';
  elements.chatInput.style.height = Math.min(elements.chatInput.scrollHeight, 120) + 'px';
}

function handleNewChat() {
  setLatestFilters([]);
  setKnownContext({});
  setFilterConfidence(null);
  
  const elements = getElements();
  elements.chatMessages.innerHTML = `
    <div id="welcomeMessage" class="flex justify-start">
      <div class="max-w-[85%] bg-app-card border border-app-border rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm">
        <p class="text-sm text-app-text font-medium mb-2">안녕하세요! 👋</p>
        <p class="text-sm text-app-muted mb-3">티켓, 헬프센터 문서, 공통 문서에서 정보를 검색해드립니다.</p>
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
  
  document.querySelectorAll('.example-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const question = btn.textContent.trim();
      elements.chatInput.value = question;
      handleInputChange();
      handleSubmit(new Event('submit'));
    });
  });
  
  if (elements.filterDisplay) {
    elements.filterDisplay.classList.add('hidden');
  }
  
  createSession();
  updateStatus('ready', '새 대화 시작');
}

async function handleAnalyzeTicket() {
  if (state.isLoading || !state.ticketData) return;
  
  setLoading(true);
  updateStatus('loading', '분석 중...');
  
  // 플레이스홀더 숨기기
  if (elements.analysisPlaceholder) {
    elements.analysisPlaceholder.classList.add('hidden');
  }
  
  // 티커 표시
  showTicker('router_decision');
  
  try {
    // NOTE: 원인/해결 분석은 ticket_fields(거대 스키마)를 보내지 않아도 된다.
    //       (필드 제안은 별도 버튼/엔드포인트로 분리)
    const payload = {
      ticket_id: String(state.ticketData.id),
      subject: state.ticketData.subject,
      description: state.ticketData.description_text
    };

    // SSE 스트림으로 원인/해결 분석 요청
    const result = await window.StreamUtils.streamSolution(payload, (event) => {
      // 진행 상황 티커 업데이트
      const eventType = event.type || event;
      const eventData = event.data || {};
      
      showTicker(eventType, eventData);
      console.log('[Analyze] Progress:', eventType, eventData);

      // progressive complete가 오면 result로 처리하되,
      // 도중에 draft_response 등 일부 이벤트만 와도 티커는 갱신한다.
    });
    
    // 분석 완료
    hideTicker();
    
    // result는 complete.data (proposal/analysis/search/timingMs)
    const finalResult = result || state.analysisResult;
    console.log('[Analyze] Final Result:', finalResult);

    if (finalResult) {
      const analysis = finalResult.analysis || null;
      const proposal = finalResult.proposal || null;

      const merged = {
        ...(analysis || {}),
        ...(proposal || {})
      };

      setAnalysisResult(merged);
      renderAnalysisResult(merged);
    } else {
      renderAnalysisError('분석 결과를 받을 수 없습니다.');
    }
    
  } catch (error) {
    console.error('티켓 분석 실패:', error);
    hideTicker();
    renderAnalysisError(`분석 오류: ${error.message}`);
  } finally {
    setLoading(false);
    updateStatus('ready', '준비 완료');
  }
}

/**
 * 분석 결과 렌더링 (분석 섹션에 표시)
 */
/**
 * solution 필드를 단계별 목록으로 렌더링
 * - 문자열 배열 JSON: ["step1","step2"] → 번호 목록
 * - 객체 배열: [{action, rationale}] → 번호 목록
 * - 일반 문자열 → 텍스트 블록
 */
function renderSolutionSteps(solution) {
  let items = solution;

  // JSON 문자열이면 파싱 시도
  if (typeof solution === 'string') {
    const trimmed = solution.trim();
    if (trimmed.startsWith('[') || trimmed.startsWith('{')) {
      try { items = JSON.parse(trimmed); } catch (e) { /* 파싱 실패 시 원문 사용 */ }
    }
  }

  // 배열인 경우 → 번호 목록
  if (Array.isArray(items) && items.length > 0) {
    const listItems = items.map((item, i) => {
      const text = typeof item === 'string'
        ? item
        : (item.action || item.text || item.step || JSON.stringify(item));
      const rationale = typeof item === 'object' ? (item.rationale || '') : '';
      return `
        <li class="flex gap-2 items-start">
          <span class="flex-shrink-0 w-5 h-5 bg-green-100 text-green-700 rounded-full flex items-center justify-center text-xs font-semibold mt-0.5">${i + 1}</span>
          <div class="flex-1">
            <span class="text-app-text">${escapeHtml(text)}</span>
            ${rationale ? `<p class="text-xs text-app-muted mt-0.5">${escapeHtml(rationale)}</p>` : ''}
          </div>
        </li>`;
    }).join('');
    return `<ol class="space-y-2 list-none">${listItems}</ol>`;
  }

  // 객체인 경우 → 텍스트 추출
  if (items && typeof items === 'object' && !Array.isArray(items)) {
    const text = items.text || items.action || items.steps || JSON.stringify(items);
    return `<div class="text-app-muted bg-app-bg border border-app-border p-2 rounded whitespace-pre-wrap">${escapeHtml(String(text))}</div>`;
  }

  // 일반 텍스트
  return `<div class="text-app-muted bg-app-bg border border-app-border p-2 rounded whitespace-pre-wrap">${formatMessage(String(solution))}</div>`;
}

function renderAnalysisResult(proposal) {
  if (!elements.analysisContent) return;

  const summarySections = proposal.summary_sections || proposal.summarySections;
  const summary = proposal.summary;
  const intent = proposal.intent;
  const sentiment = proposal.sentiment;
  const cause = proposal.cause;
  const solution = proposal.solution;
  
  let html = '';
  
  // 요약 카드
  if (summary || intent || sentiment || cause || solution) {
    html += `
      <div class="bg-app-card border border-app-border rounded-xl p-4 shadow-sm">
        <div class="flex items-center gap-2 mb-3">
          <svg class="w-5 h-5 text-app-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
          </svg>
          <h3 class="text-sm font-semibold text-app-text">티켓 분석 결과</h3>
        </div>
        <div class="space-y-3 text-sm">
          ${Array.isArray(summarySections) && summarySections.length > 0 ? `
            <div>
              <p class="font-medium text-app-text mb-2">요약:</p>
              <div class="space-y-2">
                ${summarySections.slice(0, 3).map(s => {
                  const t = escapeHtml((s && s.title) ? String(s.title) : '');
                  const c = escapeHtml((s && s.content) ? String(s.content) : '');
                  if (!t && !c) return '';
                  return `<div class="bg-app-bg p-2 rounded border border-app-border">
                    ${t ? `<div class="text-app-text font-medium">${t}</div>` : ''}
                    ${c ? `<div class="text-app-muted">${c}</div>` : ''}
                  </div>`;
                }).join('')}
              </div>
            </div>
          ` : (summary ? `<p><span class="font-medium text-app-muted">요약:</span> <span class="text-app-text">${escapeHtml(summary)}</span></p>` : '')}
          ${intent ? `<p><span class="font-medium text-app-muted">의도:</span> <span class="text-app-text">${escapeHtml(intent)}</span></p>` : ''}
          ${sentiment ? `<p><span class="font-medium text-app-muted">감정:</span> <span class="text-app-text">${escapeHtml(sentiment)}</span></p>` : ''}
          ${cause ? `
            <div class="pt-2 border-t border-app-border">
              <p class="font-medium text-app-text mb-1">원인:</p>
              <p class="text-app-muted bg-app-bg border border-app-border p-2 rounded">${escapeHtml(cause)}</p>
            </div>
          ` : ''}
          ${solution ? `
            <div class="pt-2 border-t border-app-border">
              <p class="font-medium text-app-text mb-1">해결책:</p>
              ${renderSolutionSteps(solution)}
            </div>
          ` : ''}
        </div>
      </div>
    `;
  }
  
  // 필드 제안 카드
  const fieldUpdates = proposal.field_updates || proposal.fieldUpdates || {};
  const fieldProposals = proposal.field_proposals || [];
  
  if (fieldProposals.length > 0 || Object.keys(fieldUpdates).length > 0) {
    html += renderFieldSuggestionsCard(proposal);
  }
  
  // 다시 분석 버튼
  html += `
    <div class="flex justify-center pt-2">
      <button onclick="handleAnalyzeTicket()" class="px-4 py-2 text-sm text-app-muted hover:text-app-primary transition-colors flex items-center gap-1">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
        </svg>
        다시 분석
      </button>
    </div>
  `;
  
  elements.analysisContent.innerHTML = html;
}

/**
 * 필드 제안 카드 렌더링 (기존 renderFieldSuggestions 로직 재사용)
 */
function renderFieldSuggestionsCard(proposal) {
  const updates = proposal.field_updates || proposal.fieldUpdates || {};
  const isAllowedByTenant = buildTenantFieldAllowChecker();
  const fieldProposals = (proposal.field_proposals || []).filter(p => {
    const name = p && typeof p === 'object' ? p.field_name : null;
    return name ? isAllowedByTenant(name) : true;
  });
  const proposalMap = {};
  fieldProposals.forEach(p => { proposalMap[p.field_name] = p; });
  const renderedFields = new Set();
  const messageId = 'analysis-' + Date.now();

  const ticketFields = state.ticketFields;
  const ticketData = state.ticketData;

  const getFieldDefByName = (name) => {
    if (!ticketFields || !Array.isArray(ticketFields)) return null;
    return ticketFields.find(f => f && typeof f === 'object' && f.name === name) || null;
  };

  const formatCurrentValue = (fieldName, value) => {
    if (value === undefined || value === null) return '-';
    if (typeof value === 'string' && value.trim() === '') return '-';

    if (Array.isArray(value)) {
      const s = value.map(v => String(v)).filter(Boolean).join(', ');
      return s || '-';
    }

    if ((fieldName === 'priority' || fieldName === 'status') && (typeof value === 'number' || /^-?\d+$/.test(String(value).trim()))) {
      const n = typeof value === 'number' ? value : parseInt(String(value).trim(), 10);
      if (!Number.isNaN(n)) {
        const def = getFieldDefByName(fieldName);
        const choices = def ? def.choices : null;
        if (choices && typeof choices === 'object' && !Array.isArray(choices)) {
          const label = choices[String(n)] || choices[n];
          if (label) return String(label);
        }
        if (fieldName === 'priority') {
          const m = { 1: 'Low', 2: 'Medium', 3: 'High', 4: 'Urgent' };
          if (m[n]) return m[n];
        }
      }
    }

    return String(value);
  };

  const renderRow = (label, fieldName, currentVal, inputHtml, reason) => `
    <tr>
      <td class="px-2 py-2 font-medium text-app-muted">
        ${label}
        ${reason ? `<div class="group relative inline-block ml-1">
          <svg class="w-3 h-3 text-gray-400 cursor-help" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
          <div class="invisible group-hover:visible absolute z-10 w-48 p-2 mt-1 text-xs text-white bg-gray-800 rounded shadow-lg -left-2">
            ${escapeHtml(reason)}
          </div>
        </div>` : ''}
      </td>
      <td class="px-2 py-2 text-app-muted text-xs">${escapeHtml(formatCurrentValue(fieldName, currentVal))}</td>
      <td class="px-2 py-2">${inputHtml}</td>
    </tr>
  `;

  let tableRows = '';

  if (fieldProposals.length > 0) {
    // nested_field 처리 로직 (기존 코드와 동일)
    const nestedRoot = ticketFields ? ticketFields.find(f => f.type === 'nested_field') : null;
    if (nestedRoot && nestedRoot.choices && nestedRoot.nested_ticket_fields) {
      const nestedFields = nestedRoot.nested_ticket_fields;
      const level2Name = nestedFields.find(n => n.level === 2)?.name || nestedFields[0]?.name;
      const level3Name = nestedFields.find(n => n.level === 3)?.name || nestedFields[1]?.name;
      const hasNestedProposal = [nestedRoot.name, level2Name, level3Name].some(n => proposalMap[n]);

      if (hasNestedProposal) {
        const choices = normalizeChoices(nestedRoot.choices);
        window[`choices-${messageId}-${nestedRoot.name}`] = choices;
        window[`pathMap-${messageId}-${nestedRoot.name}`] = buildValuePathMap(choices);
        // Item 후보는 leaf 중에서도 depth>=2만 노출 (카테고리-only leaf 제외, 혼합 깊이 지원)
        window[`leafMinDepth-${messageId}-${nestedRoot.name}`] = 2;
        window[`leafOptions-${messageId}-${nestedRoot.name}`] = flattenLeafOptionsMinDepth(choices, 2);
        const leafOptions = ensureLeafOptions(messageId, nestedRoot.name);

        const proposedLeaf = proposalMap[level3Name]?.proposed_value || proposalMap[level2Name]?.proposed_value || proposalMap[nestedRoot.name]?.proposed_value || '';
        const path = findPathToValue(choices, proposedLeaf) || [];
        const val1 = path[0] || proposalMap[nestedRoot.name]?.proposed_value || '';
        const val2 = path[1] || proposalMap[level2Name]?.proposed_value || '';
        const val3Display = (path.length === 2 ? path[1] : (path[2] || proposalMap[level3Name]?.proposed_value || ''));
        const val3Hidden = (path.length >= 3 ? (path[2] || '') : '');

        let opts1 = '<option value="">선택하세요</option>';
        choices.forEach(c => opts1 += `<option value="${c.value}" ${c.value === val1 ? 'selected' : ''}>${c.value}</option>`);

        let opts2 = '<option value="">선택하세요</option>';
        const subChoices = val1 ? choices.find(c => c.value === val1)?.choices : [];
        if (subChoices) subChoices.forEach(c => opts2 += `<option value="${c.value}" ${c.value === val2 ? 'selected' : ''}>${c.value}</option>`);

        // NOTE: Item 셀렉트는 제거됐지만, 기존 데이터 형태 보존을 위해 itemChoices 계산은 남겨둠
        // (val3는 scope에 없으므로 val3Hidden 기준으로 비교)
        let opts3 = '<option value="">선택하세요</option>';
        const itemChoices = val2 ? subChoices?.find(c => c.value === val2)?.choices : [];
        if (itemChoices) itemChoices.forEach(c => opts3 += `<option value="${c.value}" ${c.value === val3Hidden ? 'selected' : ''}>${c.value}</option>`);

        const currentVal1 = ticketData[nestedRoot.name] !== undefined ? ticketData[nestedRoot.name] : ticketData.custom_fields?.[nestedRoot.name];
        const currentVal2 = level2Name ? (ticketData[level2Name] !== undefined ? ticketData[level2Name] : ticketData.custom_fields?.[level2Name]) : undefined;
        const currentVal3 = level3Name ? (ticketData[level3Name] !== undefined ? ticketData[level3Name] : ticketData.custom_fields?.[level3Name]) : undefined;

        tableRows += renderRow(nestedRoot.label || 'Category', nestedRoot.name, currentVal1, `
          <select id="input-${nestedRoot.name}-${messageId}-1" data-field-name="${nestedRoot.name}" data-level="1" onchange="updateDependentFields('${messageId}', '${nestedRoot.name}', 1)" class="w-full text-sm border-gray-300 rounded-md shadow-sm focus:border-blue-500 focus:ring-blue-500 py-1">
            ${opts1}
          </select>
        `, proposalMap[nestedRoot.name]?.reason);

        if (level2Name) {
          tableRows += renderRow('Sub Category', level2Name, currentVal2, `
              <select id="input-${nestedRoot.name}-${messageId}-2" data-field-name="${level2Name}" data-level="2" onchange="updateDependentFields('${messageId}', '${nestedRoot.name}', 2)" class="w-full text-sm border-gray-300 rounded-md shadow-sm focus:border-blue-500 focus:ring-blue-500 py-1" ${!val1 ? 'disabled' : ''}>
              ${opts2}
            </select>
          `, proposalMap[level2Name]?.reason);
        }

        if (level3Name) {
          const searchInputId = `leafsearch-${nestedRoot.name}-${messageId}`;
          const datalistId = `leaflist-${nestedRoot.name}-${messageId}`;
          
          // Item 필드는 검색 가능한 입력 필드로 통합 (드롭다운 제거)
          tableRows += renderRow('Item', level3Name, currentVal3, `
            <div class="relative">
              <input id="${searchInputId}" list="${datalistId}" 
                     placeholder="항목 검색 (전체 검색 가능)" 
                     class="w-full text-sm border border-gray-300 rounded-md px-2 py-1.5 focus:border-blue-500 focus:ring-blue-500 transition-colors" 
                     oninput="handleLeafSearchApply('${messageId}', '${nestedRoot.name}', '${searchInputId}')"
                     value="${val3Display || ''}">
              <input type="hidden" id="leafhidden-${nestedRoot.name}-${messageId}" data-field-name="${level3Name}" value="${val3Hidden || ''}">
              <datalist id="${datalistId}">
                ${leafOptions.slice(0, 2000).map(opt => `<option value="${opt.value}" label="${opt.label}"></option>`).join('')}
              </datalist>
              <div class="absolute inset-y-0 right-0 flex items-center pr-2 pointer-events-none">
                <svg class="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
                </svg>
              </div>
            </div>
            `, proposalMap[level3Name]?.reason);
        }

        renderedFields.add(nestedRoot.name);
        if (level2Name) renderedFields.add(level2Name);
        if (level3Name) renderedFields.add(level3Name);
      }
    }

    // 나머지 필드 처리
    fieldProposals.forEach(prop => {
      if (renderedFields.has(prop.field_name)) return;
      if (!isAllowedByTenant(prop.field_name)) return;

      const fieldName = prop.field_name;
      const fieldLabel = prop.field_label;
      const proposedValue = prop.proposed_value;
      const reason = prop.reason;
      renderedFields.add(fieldName);
      
      const fieldDef = ticketFields ? ticketFields.find(f => f.name === fieldName) : null;
      let inputHtml = '';

      if (fieldDef && (fieldDef.type === 'custom_dropdown' || fieldDef.type === 'default_status' || fieldDef.type === 'default_priority' || fieldDef.choices)) {
        const choices = normalizeChoices(fieldDef.choices);
        let optionsHtml = '<option value="">선택하세요</option>';
        const flatOptions = [];
        function collectOptions(list) {
          list.forEach(c => {
            flatOptions.push(c.value);
            if (c.choices) collectOptions(c.choices);
          });
        }
        collectOptions(choices);
        
        flatOptions.forEach(val => {
          optionsHtml += `<option value="${val}" ${val === proposedValue ? 'selected' : ''}>${val}</option>`;
        });

        inputHtml = `
          <select id="input-${fieldName}-${messageId}" data-field-name="${fieldName}" class="w-full text-sm border-gray-300 rounded-md shadow-sm focus:border-blue-500 focus:ring-blue-500 py-1">
            ${optionsHtml}
          </select>
        `;
      } else {
        inputHtml = `
          <input type="text" id="input-${fieldName}-${messageId}" data-field-name="${fieldName}" value="${proposedValue || ''}" class="w-full text-sm border-gray-300 rounded-md shadow-sm focus:border-blue-500 focus:ring-blue-500 py-1">
        `;
      }

      let currentVal = ticketData[fieldName];
      if (currentVal === undefined && ticketData.custom_fields) {
        currentVal = ticketData.custom_fields[fieldName];
      }

      tableRows += renderRow(fieldLabel, fieldName, currentVal, inputHtml, reason);
    });
  }

  const justification = proposal.justification || proposal.reasoning;

  return `
    <div id="${messageId}" class="bg-app-card border border-app-border rounded-xl p-4 shadow-sm">
      <div class="flex items-center justify-between mb-3">
        <div class="flex items-center gap-2">
          <svg class="w-5 h-5 text-app-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"/>
          </svg>
          <h3 class="text-sm font-semibold text-app-text">필드 업데이트 제안</h3>
        </div>
        <span class="text-xs bg-blue-50 text-blue-600 px-2 py-0.5 rounded-full font-medium">AI 분석</span>
      </div>

      <div class="mb-4 overflow-x-auto">
        <table class="w-full text-sm text-left">
          <thead class="text-xs text-app-muted bg-app-bg uppercase">
            <tr>
              <th class="px-2 py-2 w-20">필드</th>
              <th class="px-2 py-2 w-24">현재 값</th>
              <th class="px-2 py-2">제안 값 (수정 가능)</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-app-border">
            ${tableRows}
          </tbody>
        </table>
      </div>

      ${justification ? `
        <div class="mb-3 px-2 py-2 bg-app-bg rounded border border-app-border">
          <p class="text-xs text-app-muted"><span class="font-semibold text-app-text">AI 근거:</span> ${escapeHtml(justification)}</p>
        </div>
      ` : ''}
      
      <button onclick="applyEditableFieldUpdates('${messageId}')" class="w-full py-2 bg-app-primary hover:bg-app-primary-hover text-white text-sm font-medium rounded-lg transition-colors flex items-center justify-center gap-2">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
        </svg>
        변경 사항 적용하기
      </button>
    </div>
  `;
}

/**
 * 분석 에러 렌더링
 */
function renderAnalysisError(message) {
  if (!elements.analysisContent) return;
  
  elements.analysisContent.innerHTML = `
    <div class="flex flex-col items-center justify-center py-12 text-center">
      <div class="w-16 h-16 bg-red-50 rounded-full flex items-center justify-center mb-4">
        <svg class="w-8 h-8 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
        </svg>
      </div>
      <h3 class="text-lg font-semibold text-app-text mb-2">분석 실패</h3>
      <p class="text-sm text-red-600 mb-4">${escapeHtml(message)}</p>
      <button onclick="handleAnalyzeTicket()" class="px-4 py-2 text-sm font-medium text-white bg-app-primary rounded-lg hover:bg-app-primary-hover transition-colors flex items-center gap-2">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
        </svg>
        다시 시도
      </button>
    </div>
  `;
}

// handleAnalyzeTicket을 전역으로 노출 (onclick 용)
window.handleAnalyzeTicket = handleAnalyzeTicket;
