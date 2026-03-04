/**
 * Analysis UI Module (PR3)
 *
 * 4-Tab UI: Analyze, Evidence, Teach, History
 * State Machine: IDLE -> RUNNING -> COMPLETED | NEEDS_REVIEW | ERROR
 */

(function() {
  'use strict';

  // =============================================================================
  // State Machine
  // =============================================================================

  const AnalysisState = {
    IDLE: 'IDLE',
    RUNNING: 'RUNNING',
    COMPLETED: 'COMPLETED',
    NEEDS_REVIEW: 'NEEDS_REVIEW',
    ERROR: 'ERROR'
  };

  // =============================================================================
  // Typing Engine
  // =============================================================================

  const TYPING_SPEED_MS = 12;
  const _typingState = { timer: null, currentText: '', targetText: '', element: null };

  function _startTyping(targetText, element) {
    _stopTyping();
    _typingState.targetText = targetText;
    _typingState.currentText = '';
    _typingState.element = element;

    const cursor = document.createElement('span');
    cursor.className = 'typewriter-cursor';
    element.textContent = '';
    element.appendChild(cursor);

    _typingState.timer = setInterval(() => {
      if (_typingState.currentText.length >= _typingState.targetText.length) {
        _stopTyping();
        return;
      }
      _typingState.currentText += _typingState.targetText[_typingState.currentText.length];
      element.textContent = _typingState.currentText;
      element.appendChild(cursor);
    }, TYPING_SPEED_MS);
  }

  function _confidenceColor(value) {
    if (value >= 0.7) return 'bg-green-500';
    if (value >= 0.5) return 'bg-yellow-500';
    return 'bg-red-500';
  }

  function _stopTyping() {
    if (_typingState.timer) {
      clearInterval(_typingState.timer);
      _typingState.timer = null;
    }
    if (_typingState.element) {
      _typingState.element.textContent = _typingState.targetText || _typingState.currentText;
      const cursor = _typingState.element.querySelector('.typewriter-cursor');
      if (cursor) cursor.remove();
    }
  }

  const analysisStore = {
    state: AnalysisState.IDLE,
    currentTab: 'analyze',
    analysisResult: null,
    analysisHistory: [],
    error: null
  };

  function setState(newState) {
    console.log(`[AnalysisUI] State: ${analysisStore.state} -> ${newState}`);
    analysisStore.state = newState;
    updateStatusBadge();
  }

  function setCurrentTab(tab) {
    analysisStore.currentTab = tab;
    updateTabUI();
  }

  function setAnalysisResult(result) {
    analysisStore.analysisResult = result;
    if (result && result.gate) {
      // gate에 따라 상태 결정
      if (result.gate === 'DECIDE' || result.gate === 'TEACH') {
        setState(AnalysisState.NEEDS_REVIEW);
      } else {
        setState(AnalysisState.COMPLETED);
      }
    }
  }

  // =============================================================================
  // UI Updates
  // =============================================================================

  function updateStatusBadge() {
    const badge = document.getElementById('statusBadge');
    if (!badge) return;

    const configs = {
      [AnalysisState.IDLE]: { text: '준비', class: 'bg-gray-100 text-gray-700' },
      [AnalysisState.RUNNING]: { text: '분석 중...', class: 'bg-blue-100 text-blue-700' },
      [AnalysisState.COMPLETED]: { text: '완료', class: 'bg-green-100 text-green-700' },
      [AnalysisState.NEEDS_REVIEW]: { text: '검토 필요', class: 'bg-orange-100 text-orange-700' },
      [AnalysisState.ERROR]: { text: '오류', class: 'bg-red-100 text-red-700' }
    };

    const config = configs[analysisStore.state] || configs[AnalysisState.IDLE];
    badge.textContent = config.text;
    badge.className = `px-2 py-1 text-xs font-medium rounded-full ${config.class}`;
  }

  function updateTabUI() {
    const tabs = ['analyze', 'evidence', 'teach', 'history'];
    const tabButtons = {
      analyze: document.getElementById('tabAnalyze'),
      evidence: document.getElementById('tabEvidence'),
      teach: document.getElementById('tabTeach'),
      history: document.getElementById('tabHistory')
    };
    const sections = {
      analyze: document.getElementById('sectionAnalyze'),
      evidence: document.getElementById('sectionEvidence'),
      teach: document.getElementById('sectionTeach'),
      history: document.getElementById('sectionHistory')
    };

    tabs.forEach(tab => {
      const btn = tabButtons[tab];
      const section = sections[tab];
      if (!btn || !section) return;

      if (tab === analysisStore.currentTab) {
        btn.classList.add('active');
        section.classList.remove('section-hidden');
      } else {
        btn.classList.remove('active');
        section.classList.add('section-hidden');
      }
    });
  }

  // =============================================================================
  // Analyze Tab
  // =============================================================================

  async function runAnalysis() {
    const ticketData = window.state?.ticketData;
    const ticketFields = window.state?.ticketFields;

    if (!ticketData || !ticketData.id) {
      showError('티켓 데이터가 없습니다.');
      return;
    }

    setState(AnalysisState.RUNNING);
    showResultContainer();

    const customFieldKeys = Object.keys(ticketData.custom_fields || {});
    const relevantTicketFields = ticketFields?.filter(f => customFieldKeys.includes(f.name)) || null;
    const partialAnalysis = {};

    try {
      await window.StreamUtils.fetchAnalysisStream(
        String(ticketData.id),
        {
          subject: ticketData.subject,
          description_text: ticketData.description_text,
          priority: ticketData.priority,
          status: ticketData.status,
          source: ticketData.source,
          type: ticketData.type,
          tags: ticketData.tags,
          requester_id: ticketData.requester_id,
          responder_id: ticketData.responder_id,
          group_id: ticketData.group_id,
          custom_fields: ticketData.custom_fields,
          conversations: ticketData.conversations || [],
          ticketFields: relevantTicketFields,
          created_at: ticketData.created_at,
          updated_at: ticketData.updated_at
        },
        { include_evidence: true, response_tone: 'formal' },
        (event) => {
          if (event.type === 'progress' && event.analysis_id) {
            const teachEl = document.getElementById('teachAnalysisId');
            if (teachEl) teachEl.value = event.analysis_id;
          } else if (event.type === 'field') {
            partialAnalysis[event.name] = event.data;
            renderStreamField(event.name, event.data);
          } else if (event.type === 'complete') {
            renderGateAndMeta(event.gate, event.analysis_id, event.meta);
            showFeedbackSection(event.analysis_id);
            const fullResult = {
              analysis_id: event.analysis_id,
              gate: event.gate,
              analysis: partialAnalysis,
              meta: event.meta
            };
            setAnalysisResult(fullResult);
            setState(
              (event.gate === 'DECIDE' || event.gate === 'TEACH')
                ? AnalysisState.NEEDS_REVIEW
                : AnalysisState.COMPLETED
            );
          } else if (event.type === 'error') {
            setState(AnalysisState.ERROR);
            showError(`분석 실패: ${event.message}`);
          }
        }
      );
    } catch (error) {
      console.error('[AnalysisUI] Analysis stream failed:', error);
      setState(AnalysisState.ERROR);
      showError(`분석 실패: ${error.message}`);
    }
  }

  function showResultContainer() {
    _stopTyping();

    const placeholder = document.getElementById('analysisPlaceholder');
    const errorEl = document.getElementById('analysisError');
    const result = document.getElementById('analysisResult');

    if (placeholder) placeholder.classList.add('hidden');
    if (errorEl) errorEl.remove();

    if (result) {
      result.classList.remove('hidden');
      // 스켈레톤 표시 상태로 리셋
      const narrativeSkeleton = document.getElementById('narrativeSkeleton');
      const narrativeText = document.getElementById('narrativeText');
      const confidenceSkeleton = document.getElementById('confidenceSkeleton');
      const confidenceBar = document.getElementById('confidenceBar');
      const confidenceValue = document.getElementById('confidenceValue');
      const confidenceFill = document.getElementById('confidenceFill');

      if (narrativeSkeleton) narrativeSkeleton.classList.remove('hidden');
      if (narrativeText) { narrativeText.classList.add('hidden'); narrativeText.textContent = ''; }
      if (confidenceSkeleton) confidenceSkeleton.classList.remove('hidden');
      if (confidenceBar) confidenceBar.classList.add('hidden');
      if (confidenceValue) confidenceValue.textContent = '-';
      if (confidenceFill) confidenceFill.style.width = '0%';
    }
  }

  function showFeedbackSection() { /* 다음 단계에서 구현 */ }

  function renderStreamField(name, data) {
    if (name === 'narrative') {
      const skeleton = document.getElementById('narrativeSkeleton');
      const textEl = document.getElementById('narrativeText');
      if (skeleton) skeleton.classList.add('hidden');
      if (textEl) {
        textEl.classList.remove('hidden');
        _startTyping(data.summary || '', textEl);
      }
    } else if (name === 'confidence') {
      const skeleton = document.getElementById('confidenceSkeleton');
      const bar = document.getElementById('confidenceBar');
      const valueEl = document.getElementById('confidenceValue');
      const fill = document.getElementById('confidenceFill');

      if (skeleton) skeleton.classList.add('hidden');
      if (bar) bar.classList.remove('hidden');
      if (valueEl) valueEl.textContent = Math.round(data * 100) + '%';
      if (fill) {
        fill.style.width = (data * 100) + '%';
        fill.className = 'confidence-fill ' + _confidenceColor(data);
      }
    }
    // 그 외 필드: 무시 (다음 단계에서 추가)
  }

  function renderGateAndMeta() { /* 다음 단계에서 구현 */ }

  function renderAnalysisResult(result) {
    const placeholder = document.getElementById('analysisPlaceholder');
    const errorEl = document.getElementById('analysisError');
    const resultEl = document.getElementById('analysisResult');

    if (placeholder) placeholder.classList.add('hidden');
    if (errorEl) errorEl.remove();
    if (resultEl) resultEl.classList.remove('hidden');

    _stopTyping();

    // narrative — 즉시 표시 (타이핑 없음)
    const narrativeSkeleton = document.getElementById('narrativeSkeleton');
    const narrativeText = document.getElementById('narrativeText');
    if (narrativeSkeleton) narrativeSkeleton.classList.add('hidden');
    if (narrativeText) {
      narrativeText.classList.remove('hidden');
      narrativeText.textContent = result?.analysis?.narrative?.summary || '';
    }

    // confidence — 즉시 채움 (transition 없이)
    const confidenceSkeleton = document.getElementById('confidenceSkeleton');
    const confidenceBar = document.getElementById('confidenceBar');
    const confidenceValue = document.getElementById('confidenceValue');
    const confidenceFill = document.getElementById('confidenceFill');
    const conf = result?.analysis?.confidence;

    if (confidenceSkeleton) confidenceSkeleton.classList.add('hidden');
    if (confidenceBar) confidenceBar.classList.remove('hidden');

    if (conf !== null && conf !== undefined) {
      if (confidenceValue) confidenceValue.textContent = Math.round(conf * 100) + '%';
      if (confidenceFill) {
        confidenceFill.style.transition = 'none';
        confidenceFill.style.width = (conf * 100) + '%';
        confidenceFill.className = 'confidence-fill ' + _confidenceColor(conf);
      }
    } else {
      if (confidenceValue) confidenceValue.textContent = '-';
      if (confidenceFill) confidenceFill.style.width = '0%';
    }
  }

  // 재구성 예정
  function setupEvidenceFilters() { /* 재구성 예정 */ }
  async function submitFeedback() { /* 재구성 예정 */ }
  function openEditModal() { /* 재구성 예정 */ }
  function setupFeedbackHandlers() { /* 재구성 예정 */ }

  // =============================================================================
  // Teach Tab
  // =============================================================================

  function setupTeachForm() {
    const form = document.getElementById('teachForm');
    const resetBtn = document.getElementById('teachResetBtn');
    const resultDiv = document.getElementById('teachResult');

    if (!form) return;

    form.addEventListener('submit', async (e) => {
      e.preventDefault();

      const analysisId = document.getElementById('teachAnalysisId')?.value;
      if (!analysisId) {
        showTeachResult('먼저 분석을 실행해주세요.', false);
        return;
      }

      const lesson = {
        mistake_pattern: document.getElementById('teachMistakePattern')?.value || '',
        wrong_assumption: document.getElementById('teachWrongAssumption')?.value || '',
        corrective_heuristic: document.getElementById('teachCorrectiveHeuristic')?.value || '',
        automation_possible: document.getElementById('teachAutomationPossible')?.checked || false
      };

      // 최소 하나의 필드는 입력 필요
      if (!lesson.mistake_pattern && !lesson.wrong_assumption && !lesson.corrective_heuristic) {
        showTeachResult('최소 하나의 필드를 입력해주세요.', false);
        return;
      }

      const submitBtn = document.getElementById('teachSubmitBtn');
      if (submitBtn) submitBtn.disabled = true;

      try {
        const result = await window.StreamUtils.submitTeachFeedback(analysisId, lesson);
        showTeachResult(result.message || '교훈이 성공적으로 저장되었습니다!', true);
        form.reset();
      } catch (error) {
        showTeachResult(`제출 실패: ${error.message}`, false);
      } finally {
        if (submitBtn) submitBtn.disabled = false;
      }
    });

    if (resetBtn) {
      resetBtn.addEventListener('click', () => {
        form.reset();
        if (resultDiv) resultDiv.classList.add('hidden');
      });
    }
  }

  function showTeachResult(message, success) {
    const resultDiv = document.getElementById('teachResult');
    if (!resultDiv) return;

    resultDiv.textContent = message;
    resultDiv.className = `mt-4 p-4 rounded-lg text-sm ${
      success ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'
    }`;
    resultDiv.classList.remove('hidden');
  }

  // =============================================================================
  // History Tab
  // =============================================================================

  async function loadHistory() {
    const ticketId = window.state?.ticketData?.id;
    if (!ticketId) {
      showHistoryError('티켓 ID가 없습니다.');
      return;
    }

    const loadBtn = document.getElementById('loadHistoryBtn');
    if (loadBtn) loadBtn.disabled = true;

    try {
      const result = await window.StreamUtils.getAnalysisHistory(String(ticketId), 10);
      analysisStore.analysisHistory = result.analyses || [];
      renderHistoryList(analysisStore.analysisHistory);
    } catch (error) {
      console.error('[AnalysisUI] Failed to load history:', error);
      showHistoryError(`이력 로드 실패: ${error.message}`);
    } finally {
      if (loadBtn) loadBtn.disabled = false;
    }
  }

  function renderHistoryList(history) {
    const placeholder = document.getElementById('historyPlaceholder');
    const list = document.getElementById('historyList');

    if (!placeholder || !list) return;

    if (history.length === 0) {
      placeholder.classList.remove('hidden');
      list.classList.add('hidden');
      list.innerHTML = '<p class="text-sm text-app-muted text-center py-4">분석 이력이 없습니다.</p>';
      return;
    }

    placeholder.classList.add('hidden');
    list.classList.remove('hidden');

    list.innerHTML = history.map(item => {
      const date = new Date(item.created_at || Date.now()).toLocaleString('ko-KR');
      const gateClass = {
        'CONFIRM': 'gate-confirm',
        'EDIT': 'gate-edit',
        'DECIDE': 'gate-decide',
        'TEACH': 'gate-teach'
      }[item.gate] || 'bg-gray-100 text-gray-700';

      return `
        <div class="bg-app-card border border-app-border rounded-lg p-3 cursor-pointer hover:border-app-primary transition-colors" data-analysis-id="${escapeHtml(item.analysis_id || '')}">
          <div class="flex items-center justify-between mb-2">
            <span class="px-2 py-0.5 text-xs font-semibold rounded-full ${gateClass}">${escapeHtml(item.gate || 'N/A')}</span>
            <span class="text-xs text-app-muted">${date}</span>
          </div>
          <p class="text-sm text-app-text truncate">${escapeHtml(item.analysis?.narrative?.summary || '요약 없음')}</p>
          <p class="text-xs text-app-muted mt-1">ID: ${escapeHtml((item.analysis_id || '').substring(0, 8))}</p>
        </div>
      `;
    }).join('');

    // 클릭 이벤트 - 과거 분석 로드
    list.querySelectorAll('[data-analysis-id]').forEach(el => {
      el.addEventListener('click', () => {
        const analysisId = el.dataset.analysisId;
        loadPastAnalysis(analysisId);
      });
    });
  }

  async function loadPastAnalysis(analysisId) {
    const ticketId = window.state?.ticketData?.id;
    if (!ticketId || !analysisId) return;

    try {
      const result = await window.StreamUtils.getAnalysisById(String(ticketId), analysisId);
      setAnalysisResult(result);
      renderAnalysisResult(result);
      setCurrentTab('analyze');
    } catch (error) {
      console.error('[AnalysisUI] Failed to load past analysis:', error);
      if (window.client && window.client.interface) {
        window.client.interface.trigger('showNotify', {
          type: 'danger',
          message: `분석 로드 실패: ${error.message}`
        });
      }
    }
  }

  function showHistoryError(message) {
    const list = document.getElementById('historyList');
    if (list) {
      list.classList.remove('hidden');
      list.innerHTML = `<p class="text-sm text-red-600 text-center py-4">${escapeHtml(message)}</p>`;
    }
  }

  // =============================================================================
  // Dark Mode
  // =============================================================================

  function setupDarkMode() {
    // Restore saved preference
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme === 'dark' || (!savedTheme && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
      document.documentElement.classList.add('dark');
      updateDarkModeIcon(true);
    }

    // Toggle button
    const toggleBtn = document.getElementById('darkModeToggle');
    if (toggleBtn) {
      toggleBtn.addEventListener('click', toggleDarkMode);
    }
  }

  function toggleDarkMode() {
    const isDark = document.documentElement.classList.toggle('dark');
    localStorage.setItem('theme', isDark ? 'dark' : 'light');
    updateDarkModeIcon(isDark);
  }

  function updateDarkModeIcon(isDark) {
    const darkIcon = document.getElementById('darkModeIcon');
    const lightIcon = document.getElementById('lightModeIcon');
    if (darkIcon && lightIcon) {
      if (isDark) {
        darkIcon.classList.add('hidden');
        lightIcon.classList.remove('hidden');
      } else {
        darkIcon.classList.remove('hidden');
        lightIcon.classList.add('hidden');
      }
    }
  }

  // =============================================================================
  // Utilities
  // =============================================================================

  function showError(message) {
    const content = document.getElementById('analysisContent');
    if (!content) return;

    const errorHtml = `
      <div class="flex flex-col items-center justify-center py-12 text-center">
        <div class="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mb-4">
          <svg class="w-8 h-8 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
          </svg>
        </div>
        <h3 class="text-lg font-semibold text-red-700 mb-2">오류 발생</h3>
        <p class="text-sm text-red-600 mb-4 max-w-sm">${escapeHtml(message)}</p>
        <button id="retryAnalyzeBtn" class="px-4 py-2 text-sm font-medium text-white bg-app-primary rounded-lg hover:bg-app-primary-hover transition-colors">
          다시 시도
        </button>
      </div>
    `;

    const placeholder = document.getElementById('analysisPlaceholder');
    const result = document.getElementById('analysisResult');
    if (placeholder) placeholder.classList.add('hidden');
    if (result) result.classList.add('hidden');

    // Insert error before placeholder
    const errorDiv = document.createElement('div');
    errorDiv.id = 'analysisError';
    errorDiv.innerHTML = errorHtml;
    content.insertBefore(errorDiv, content.firstChild);

    // Retry button — app.js의 handleAnalyzeTicket()으로 통일
    document.getElementById('retryAnalyzeBtn')?.addEventListener('click', () => {
      errorDiv.remove();
      if (placeholder) placeholder.classList.remove('hidden');
      if (window.handleAnalyzeTicket) {
        window.handleAnalyzeTicket();
      }
    });
  }

  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  // =============================================================================
  // Initialization
  // =============================================================================

  function init() {
    console.log('[AnalysisUI] Initializing...');

    // Tab click handlers
    ['tabAnalyze', 'tabEvidence', 'tabTeach', 'tabHistory'].forEach(tabId => {
      const btn = document.getElementById(tabId);
      if (btn) {
        btn.addEventListener('click', () => {
          const tab = btn.dataset.tab;
          setCurrentTab(tab);
        });
      }
    });

    // Analyze button — app.js의 handleAnalyzeTicket()이 단일 핸들러로 담당
    // (이중 바인딩 방지: 여기서는 바인딩하지 않음)

    // Load History button
    const loadHistoryBtn = document.getElementById('loadHistoryBtn');
    if (loadHistoryBtn) {
      loadHistoryBtn.addEventListener('click', loadHistory);
    }

    // Evidence filters
    setupEvidenceFilters();

    // Teach form
    setupTeachForm();

    // HITL Feedback handlers
    setupFeedbackHandlers();

    // Dark mode
    setupDarkMode();

    // Initial UI state
    updateTabUI();
    updateStatusBadge();

    console.log('[AnalysisUI] Initialized');
  }

  // Initialize when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // Export for external access
  window.AnalysisUI = {
    runAnalysis,
    setState,
    setCurrentTab,
    AnalysisState,
    submitFeedback,
    openEditModal,
    toggleDarkMode,
    showFeedbackSection,
    renderAnalysisResult
  };

})();
