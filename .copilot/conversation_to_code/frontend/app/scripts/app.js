/**
 * AI Assistant POC - FDK Client
 *
 * Features:
 * - Real-time ticket analysis with SSE streaming
 * - AI proposal display with chat-based refinement
 * - Approval/rejection workflow
 * - Clean UX for support agents
 *
 * Author: AI Assistant POC
 * Date: 2025-11-05
 */

// Global variables
let client;
let ticketData = null;
let currentProposal = null;
let chatHistory = [];
let analysisStartTime = null;
let isModalView = false;

// UI Elements
const elements = {
  progressSection: null,
  proposalSection: null,
  chatSection: null,
  resultSection: null,
  errorSection: null,

  progressText: null,
  step1: null,
  step2: null,
  step3: null,

  confidenceBadge: null,
  modeBadge: null,
  analysisTime: null,
  proposalResponse: null,
  fieldList: null,
  referenceList: null,
  refCount: null,

  approveBtn: null,
  refineBtn: null,
  rejectBtn: null,

  chatMessages: null,
  chatInput: null,
  sendChatBtn: null,
  closeChatBtn: null,

  resultMessage: null,
  errorMessage: null
};

// FDK 초기화 - document 로딩 완료 후 실행
document.onreadystatechange = function () {
  if (document.readyState === "complete") {
    if (typeof app !== 'undefined') {
      app.initialized().then(async function (_client) {
        var client = _client;

        // top bar navigation 버튼 클릭 시 모달 열기
        client.events.on("app.activated", async () => {
          await client.interface.trigger("showModal", {
            title: "🎨 Copilot Canvas",
            template: "modal.html",
            noBackdrop: true
          });
        });

        // Load ticket data
        async function loadTicketData() {
          try {
            // Get basic ticket info from FDK
            const data = await client.data.get('ticket');
            const ticketId = data.ticket.id;

            // Get full ticket with conversations from Freshdesk API
            const response = await client.request.invoke('getTicketWithConversations', {
              context: {
                ticketId: ticketId
              }
            });

            if (response.status === 200) {
              ticketData = JSON.parse(response.response);
              console.log('Ticket data loaded with conversations:', ticketData);
              console.log('Conversations:', ticketData.conversations);
            } else {
              throw new Error(`Failed to load ticket: ${response.status}`);
            }
          } catch (error) {
            console.error('Failed to load ticket data:', error);
            showError('티켓 데이터를 불러올 수 없습니다.');
          }
        }

        // Call loadTicketData function
        loadTicketData();

      }).catch(function(error) {
        console.error("Error during app initialization", error);
      });
    } else {
      console.error("app is not defined");
    }
  }
};

/**
 * Cache UI elements for performance
 */
function cacheElements() {
  elements.progressSection = document.getElementById('progressSection');
  elements.proposalSection = document.getElementById('proposalSection');
  elements.chatSection = document.getElementById('chatSection');
  elements.resultSection = document.getElementById('resultSection');
  elements.errorSection = document.getElementById('errorSection');

  elements.progressText = document.getElementById('progressText');
  elements.step1 = document.getElementById('step1');
  elements.step2 = document.getElementById('step2');
  elements.step3 = document.getElementById('step3');

  elements.confidenceBadge = document.getElementById('confidenceBadge');
  elements.modeBadge = document.getElementById('modeBadge');
  elements.analysisTime = document.getElementById('analysisTime');
  elements.proposalResponse = document.getElementById('proposalResponse');
  elements.fieldList = document.getElementById('fieldList');
  elements.referenceList = document.getElementById('referenceList');
  elements.refCount = document.getElementById('refCount');

  elements.approveBtn = document.getElementById('approveBtn');
  elements.refineBtn = document.getElementById('refineBtn');
  elements.rejectBtn = document.getElementById('rejectBtn');

  elements.chatMessages = document.getElementById('chatMessages');
  elements.chatInput = document.getElementById('chatInput');
  elements.sendChatBtn = document.getElementById('sendChatBtn');
  elements.closeChatBtn = document.getElementById('closeChatBtn');

  elements.resultMessage = document.getElementById('resultMessage');
  elements.errorMessage = document.getElementById('errorMessage');
}

/**
 * Setup event listeners for modal view
 */
function setupEventListeners() {
  elements.approveBtn.addEventListener('click', approveProposal);
  elements.refineBtn.addEventListener('click', openChat);
  elements.rejectBtn.addEventListener('click', rejectProposal);
  elements.sendChatBtn.addEventListener('click', sendRefinementRequest);
  elements.closeChatBtn.addEventListener('click', closeChat);

  // Enter key in chat
  elements.chatInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendRefinementRequest();
    }
  });
}

/**
 * Load ticket data with conversations from Freshdesk API
 */
async function loadTicketData() {
  try {
    // Get basic ticket info from FDK
    const data = await client.data.get('ticket');
    const ticketId = data.ticket.id;

    // Get full ticket with conversations from Freshdesk API
    const response = await client.request.invoke('getTicketWithConversations', {
      context: {
        ticketId: ticketId
      }
    });

    if (response.status === 200) {
      ticketData = JSON.parse(response.response);
      console.log('Ticket data loaded with conversations:', ticketData);
      console.log('Conversations:', ticketData.conversations);
    } else {
      throw new Error(`Failed to load ticket: ${response.status}`);
    }
  } catch (error) {
    console.error('Failed to load ticket data:', error);
    showError('티켓 데이터를 불러올 수 없습니다.');
  }
}

/**
 * Start ticket analysis with streaming
 */
async function analyzeTicket() {
  if (!ticketData) {
    showError('티켓 데이터가 없습니다.');
    return;
  }

  try {
    hideAll();
    showProgress();
    updateProgress(0, '분석 시작 중...');

    analysisStartTime = Date.now();

    // Start SSE streaming (tenant ID is already in request headers via template)
    await startSSEStreaming(ticketData);

  } catch (error) {
    console.error('Analysis failed:', error);
    showError(`분석 중 오류가 발생했습니다: ${error.message}`);
  }
}

/**
 * Start SSE streaming with fetch API (supports headers)
 */
async function startSSEStreaming(ticket) {
  try {
    // Use backendApiPost with streaming
    const response = await client.request.invoke('backendApiPost', {
      context: {
        path: 'api/v1/assist/analyze'
      },
      body: JSON.stringify({
        ticket_id: ticket.id,
        subject: ticket.subject,
        description: ticket.description,
        priority: ticket.priority,
        status: ticket.status,
        tags: ticket.tags || [],
        stream_progress: true
      })
    });

    // Parse response
    if (response.status === 200) {
      const result = JSON.parse(response.response);

      // Check if streaming or direct response
      if (result.proposal) {
        // Direct response (no streaming)
        handleDirectResponse(result);
      } else if (result.stream_url) {
        // Streaming URL provided
        handleSSEStream(result.stream_url);
      } else {
        throw new Error('Invalid response format');
      }
    } else {
      throw new Error(`Backend returned status ${response.status}`);
    }

  } catch (error) {
    console.error('SSE streaming failed:', error);
    showError(`스트리밍 연결 실패: ${error.message}`);
  }
}

/**
 * Handle SSE stream from URL
 */
function handleSSEStream(streamUrl) {
  const eventSource = new EventSource(streamUrl);

  eventSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      handleSSEEvent(data);
    } catch (error) {
      console.error('Failed to parse SSE event:', error);
    }
  };

  eventSource.onerror = (error) => {
    console.error('SSE connection error:', error);
    eventSource.close();

    // Fallback to direct analysis
    analyzeTicketDirect();
  };
}

/**
 * Fallback to direct analysis (no streaming)
 */
async function analyzeTicketDirect() {
  try {
    updateProgress(1, '직접 분석 모드로 전환...');

    const response = await client.request.invoke('backendApiPost', {
      context: {
        path: 'api/v1/assist/analyze'
      },
      body: JSON.stringify({
        ticket_id: ticketData.id,
        subject: ticketData.subject,
        description: ticketData.description,
        priority: ticketData.priority,
        status: ticketData.status,
        tags: ticketData.tags || [],
        stream_progress: false
      })
    });

    if (response.status === 200) {
      const result = JSON.parse(response.response);
      handleDirectResponse(result);
    } else {
      throw new Error(`분석 실패: ${response.status}`);
    }

  } catch (error) {
    console.error('Direct analysis failed:', error);
    showError(`분석 실패: ${error.message}`);
  }
}

/**
 * Handle direct response (no streaming)
 */
function handleDirectResponse(result) {
  updateProgress(3, '분석 완료!', true);

  setTimeout(() => {
    currentProposal = result.proposal;
    showProposal(result.proposal);
  }, 500);
}

/**
 * Handle SSE events
 */
function handleSSEEvent(event) {
  console.log('SSE Event:', event);

  switch (event.type) {
    case 'router_decision':
      updateProgress(1, `라우팅: ${event.decision}`);
      break;

    case 'retriever_start':
      updateProgress(1, '유사 사례 검색 중...', true);
      break;

    case 'retriever_results':
      const totalResults = event.total_results || 0;
      updateProgress(2, `검색 완료: ${totalResults}개 발견`, true);
      break;

    case 'resolution_start':
      updateProgress(2, 'AI 솔루션 생성 중...', true);
      break;

    case 'resolution_complete':
      updateProgress(3, '분석 완료!', true);

      // Load proposal details
      currentProposal = {
        id: event.proposal_id,
        confidence: event.confidence,
        mode: event.mode,
        analysis_time_ms: event.analysis_time_ms,
        ticket_id: ticketData.id
      };

      setTimeout(() => {
        loadProposalDetails(event.proposal_id);
      }, 500);
      break;

    case 'error':
      showError(event.message);
      break;

    default:
      console.log('Unknown event type:', event.type);
  }
}

/**
 * Update progress display
 */
function updateProgress(step, message, completed = false) {
  elements.progressText.textContent = message;

  // Update step icons
  const steps = [elements.step1, elements.step2, elements.step3];

  for (let i = 0; i < steps.length; i++) {
    const stepEl = steps[i];
    const icon = stepEl.querySelector('.step-icon');

    if (i < step) {
      stepEl.classList.add('completed');
      stepEl.classList.remove('active');
      icon.textContent = '✅';
    } else if (i === step) {
      stepEl.classList.add('active');
      stepEl.classList.remove('completed');
      icon.textContent = completed ? '✅' : '⏳';
    } else {
      stepEl.classList.remove('active', 'completed');
      icon.textContent = '⏳';
    }
  }
}

/**
 * Load proposal details from backend
 */
async function loadProposalDetails(proposalId) {
  try {
    const response = await client.request.invoke('backendApi', {
      context: {
        path: `api/v1/proposals/${proposalId}`
      }
    });

    if (response.status === 200) {
      const proposal = JSON.parse(response.response);
      currentProposal = proposal;
      showProposal(proposal);
    } else {
      throw new Error(`Failed to load proposal: ${response.status}`);
    }

  } catch (error) {
    console.error('Failed to load proposal details:', error);

    // Show with existing data
    showProposal(currentProposal);
  }
}

/**
 * Display proposal to user
 */
function showProposal(proposal) {
  hideAll();
  elements.proposalSection.classList.remove('hidden');

  // Confidence badge
  const confidence = proposal.confidence || 'medium';
  elements.confidenceBadge.textContent = confidence === 'high' ? '높은 신뢰도' :
                                         confidence === 'low' ? '낮은 신뢰도' : '중간 신뢰도';
  elements.confidenceBadge.className = `confidence-badge ${confidence}`;

  // Mode badge
  const mode = proposal.mode || 'direct';
  elements.modeBadge.textContent = mode === 'synthesis' ? '검색 기반 분석' : '직접 분석';

  // Analysis time
  const analysisTime = proposal.analysis_time_ms ||
                      (analysisStartTime ? Date.now() - analysisStartTime : 0);
  elements.analysisTime.textContent = `분석 시간: ${(analysisTime / 1000).toFixed(1)}초`;

  // Draft response
  elements.proposalResponse.textContent = proposal.draft_response ||
                                          proposal.proposed_action?.draft_response ||
                                          '응답 초안을 생성할 수 없습니다.';

  // Field updates
  displayFieldUpdates(proposal.field_updates || proposal.proposed_action?.proposed_field_updates || {});

  // References
  displayReferences(
    proposal.similar_cases || proposal.proposed_action?.similar_cases || [],
    proposal.kb_references || proposal.proposed_action?.kb_references || []
  );
}

/**
 * Display field updates
 */
function displayFieldUpdates(fieldUpdates) {
  elements.fieldList.innerHTML = '';

  const updates = [
    { label: '우선순위', key: 'priority', value: fieldUpdates.priority },
    { label: '상태', key: 'status', value: fieldUpdates.status },
    { label: '태그', key: 'tags', value: fieldUpdates.tags ? fieldUpdates.tags.join(', ') : null }
  ];

  updates.forEach(update => {
    if (update.value) {
      const item = document.createElement('div');
      item.className = 'field-item';
      item.innerHTML = `
        <span class="field-label">${update.label}</span>
        <span class="field-value">${update.value}</span>
      `;
      elements.fieldList.appendChild(item);
    }
  });

  if (elements.fieldList.children.length === 0) {
    elements.fieldList.innerHTML = '<div class="field-item">업데이트 제안 없음</div>';
  }
}

/**
 * Display references (similar cases + KB articles)
 */
function displayReferences(similarCases, kbReferences) {
  elements.referenceList.innerHTML = '';

  const totalRefs = (similarCases?.length || 0) + (kbReferences?.length || 0);
  elements.refCount.textContent = totalRefs;

  // Similar cases
  if (similarCases && similarCases.length > 0) {
    const casesHeader = document.createElement('h5');
    casesHeader.textContent = '유사 사례';
    elements.referenceList.appendChild(casesHeader);

    similarCases.forEach(caseItem => {
      const item = document.createElement('div');
      item.className = 'reference-item';
      item.innerHTML = `
        <div class="reference-title">티켓 #${caseItem.ticket_id || 'N/A'}</div>
        <div class="reference-excerpt">${caseItem.content || caseItem.excerpt || ''}</div>
        <span class="reference-score">유사도: ${((caseItem.score || 0) * 100).toFixed(0)}%</span>
      `;
      elements.referenceList.appendChild(item);
    });
  }

  // KB articles
  if (kbReferences && kbReferences.length > 0) {
    const kbHeader = document.createElement('h5');
    kbHeader.textContent = '지식베이스';
    kbHeader.style.marginTop = '16px';
    elements.referenceList.appendChild(kbHeader);

    kbReferences.forEach(article => {
      const item = document.createElement('div');
      item.className = 'reference-item';
      item.innerHTML = `
        <div class="reference-title">${article.title || 'KB 문서'}</div>
        <div class="reference-excerpt">${article.content || article.excerpt || ''}</div>
        <span class="reference-score">유사도: ${((article.score || 0) * 100).toFixed(0)}%</span>
      `;
      elements.referenceList.appendChild(item);
    });
  }

  if (totalRefs === 0) {
    elements.referenceList.innerHTML = '<div class="reference-item">참조 정보 없음</div>';
  }
}

/**
 * Approve proposal and apply to ticket
 */
async function approveProposal() {
  if (!currentProposal) {
    showError('승인할 제안이 없습니다.');
    return;
  }

  try {
    elements.approveBtn.disabled = true;
    elements.approveBtn.textContent = '승인 중...';

    const response = await client.request.invoke('backendApiPost', {
      context: {
        path: 'api/v1/assist/approve'
      },
      body: JSON.stringify({
        ticket_id: ticketData.id,
        proposal_id: currentProposal.id,
        action: 'approve'
      })
    });

    if (response.status === 200) {
      const result = JSON.parse(response.response);

      // Apply to ticket
      await applyProposalToTicket(result);

      showResult('✅ 제안이 승인되어 티켓에 적용되었습니다!');
    } else {
      throw new Error(`승인 실패: ${response.status}`);
    }

  } catch (error) {
    console.error('Approval failed:', error);
    showError(`승인 실패: ${error.message}`);
  } finally {
    elements.approveBtn.disabled = false;
    elements.approveBtn.innerHTML = '<span class="btn-icon">✅</span><span>승인 및 적용</span>';
  }
}

/**
 * Apply proposal changes to ticket
 */
async function applyProposalToTicket(data) {
  try {
    // Update reply editor
    if (data.final_response) {
      await client.interface.trigger('setValue', {
        id: 'reply',
        value: data.final_response
      });
    }

    // Update ticket fields
    if (data.field_updates) {
      const updates = data.field_updates;

      if (updates.priority) {
        await client.data.set('ticket.priority', updates.priority);
      }

      if (updates.status) {
        await client.data.set('ticket.status', updates.status);
      }

      if (updates.tags) {
        await client.data.set('ticket.tags', updates.tags);
      }
    }

    console.log('Proposal applied to ticket successfully');

  } catch (error) {
    console.error('Failed to apply proposal:', error);
    throw error;
  }
}

/**
 * Reject proposal
 */
async function rejectProposal() {
  if (!currentProposal) {
    showError('거부할 제안이 없습니다.');
    return;
  }

  try {
    elements.rejectBtn.disabled = true;

    await client.request.invoke('backendApiPost', {
      context: {
        path: 'api/v1/assist/reject'
      },
      body: JSON.stringify({
        ticket_id: ticketData.id,
        proposal_id: currentProposal.id,
        action: 'reject',
        feedback: ''
      })
    });

    showResult('❌ 제안이 거부되었습니다.');

  } catch (error) {
    console.error('Rejection failed:', error);
    showError(`거부 실패: ${error.message}`);
  } finally {
    elements.rejectBtn.disabled = false;
  }
}

/**
 * Open chat interface for refinement
 */
function openChat() {
  chatHistory = [];
  elements.chatMessages.innerHTML = `
    <div class="chat-message assistant">
      <div class="message-content">
        어떻게 수정해드릴까요? 구체적으로 말씀해주시면 AI가 다시 생성합니다.
      </div>
    </div>
  `;
  elements.chatInput.value = '';
  elements.chatSection.classList.remove('hidden');
  elements.chatInput.focus();
}

/**
 * Close chat interface
 */
function closeChat() {
  elements.chatSection.classList.add('hidden');
}

/**
 * Send refinement request via chat
 */
async function sendRefinementRequest() {
  const message = elements.chatInput.value.trim();

  if (!message) return;

  if (!currentProposal) {
    showError('수정할 제안이 없습니다.');
    return;
  }

  try {
    // Add user message
    addChatMessage('user', message);
    elements.chatInput.value = '';

    elements.sendChatBtn.disabled = true;
    elements.sendChatBtn.textContent = '처리 중...';

    const response = await client.request.invoke('backendApiPost', {
      context: {
        path: 'api/v1/assist/refine'
      },
      body: JSON.stringify({
        ticket_id: ticketData.id,
        proposal_id: currentProposal.id,
        refinement_request: message
      })
    });

    if (response.status === 200) {
      const result = JSON.parse(response.response);

      // Update current proposal
      currentProposal.id = result.proposal.id;

      // Add assistant response
      addChatMessage('assistant', `수정이 완료되었습니다! (버전 ${result.version})`);

      // Reload proposal details
      loadProposalDetails(result.proposal.id);

      // Close chat after delay
      setTimeout(() => {
        closeChat();
      }, 2000);
    } else {
      throw new Error(`수정 실패: ${response.status}`);
    }

  } catch (error) {
    console.error('Refinement failed:', error);
    addChatMessage('assistant', '죄송합니다. 수정 처리 중 오류가 발생했습니다.');
  } finally {
    elements.sendChatBtn.disabled = false;
    elements.sendChatBtn.textContent = '전송';
  }
}

/**
 * Add message to chat history
 */
function addChatMessage(role, content) {
  const messageDiv = document.createElement('div');
  messageDiv.className = `chat-message ${role}`;
  messageDiv.innerHTML = `
    <div class="message-content">${content}</div>
  `;

  elements.chatMessages.appendChild(messageDiv);
  elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;

  chatHistory.push({ role, content });
}

/**
 * UI State Management
 */
function hideAll() {
  elements.progressSection.classList.add('hidden');
  elements.proposalSection.classList.add('hidden');
  elements.chatSection.classList.add('hidden');
  elements.resultSection.classList.add('hidden');
  elements.errorSection.classList.add('hidden');
}

function showProgress() {
  elements.progressSection.classList.remove('hidden');

  // Reset progress
  [elements.step1, elements.step2, elements.step3].forEach(step => {
    step.classList.remove('active', 'completed');
    step.querySelector('.step-icon').textContent = '⏳';
  });
}

function showResult(message) {
  hideAll();
  elements.resultSection.classList.remove('hidden');
  elements.resultMessage.textContent = message;
}

function showError(message) {
  hideAll();
  elements.errorSection.classList.remove('hidden');
  elements.errorMessage.textContent = message;

  // Auto-hide after 5 seconds and show progress section
  setTimeout(() => {
    elements.errorSection.classList.add('hidden');
    elements.progressSection.classList.remove('hidden');
  }, 5000);
}
