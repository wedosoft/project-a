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
    showTicker('티켓 분석 중...');

    try {
      // 티켓에 실제 값이 있는 커스텀 필드 정의만 필터링
      const customFieldKeys = Object.keys(ticketData.custom_fields || {});
      const relevantTicketFields = ticketFields?.filter(f => customFieldKeys.includes(f.name)) || null;

      const result = await window.StreamUtils.fetchAnalysis(
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
        {
          include_evidence: true,
          response_tone: 'formal'
        }
      );

      hideTicker();
      setAnalysisResult(result);
      renderAnalysisResult(result);

      // Teach 탭에 analysis_id 설정
      const teachAnalysisId = document.getElementById('teachAnalysisId');
      if (teachAnalysisId && result.analysis_id) {
        teachAnalysisId.value = result.analysis_id;
      }

    } catch (error) {
      console.error('[AnalysisUI] Analysis failed:', error);
      hideTicker();
      setState(AnalysisState.ERROR);
      analysisStore.error = error.message;
      showError(`분석 실패: ${error.message}`);
    }
  }

  function renderAnalysisResult(result) {
    const placeholder = document.getElementById('analysisPlaceholder');
    const resultSection = document.getElementById('analysisResult');

    if (!placeholder || !resultSection) return;

    placeholder.classList.add('hidden');
    resultSection.classList.remove('hidden');

    const analysis = result.analysis || {};
    const meta = result.meta || {};

    // Gate Badge
    const gateBadge = document.getElementById('gateBadge');
    if (gateBadge) {
      const gateClass = {
        'CONFIRM': 'gate-confirm',
        'EDIT': 'gate-edit',
        'DECIDE': 'gate-decide',
        'TEACH': 'gate-teach'
      }[result.gate] || 'gate-teach';
      gateBadge.textContent = result.gate;
      gateBadge.className = `px-3 py-1.5 text-sm font-semibold rounded-full ${gateClass}`;
    }

    // Confidence
    const confidence = analysis.confidence || 0;
    const confidenceFill = document.getElementById('confidenceFill');
    const confidenceText = document.getElementById('confidenceText');
    if (confidenceFill) {
      confidenceFill.style.width = `${confidence * 100}%`;
      confidenceFill.className = `h-full transition-all duration-500 ${
        confidence >= 0.7 ? 'bg-green-500' : confidence >= 0.5 ? 'bg-yellow-500' : 'bg-red-500'
      }`;
    }
    if (confidenceText) {
      confidenceText.textContent = `${Math.round(confidence * 100)}%`;
    }

    // Summary
    const summaryText = document.getElementById('summaryText');
    if (summaryText) {
      summaryText.textContent = analysis.narrative?.summary || '요약 정보 없음';
    }

    // Root Cause
    const rootCauseText = document.getElementById('rootCauseText');
    const rootCauseSection = document.getElementById('rootCauseSection');
    if (rootCauseText && rootCauseSection) {
      if (analysis.root_cause) {
        rootCauseText.textContent = analysis.root_cause;
        rootCauseSection.classList.remove('hidden');
      } else {
        rootCauseSection.classList.add('hidden');
      }
    }

    // Resolution Steps
    const resolutionSteps = document.getElementById('resolutionSteps');
    const resolutionSection = document.getElementById('resolutionSection');
    if (resolutionSteps && resolutionSection) {
      const resolution = analysis.resolution || [];
      if (resolution.length > 0) {
        resolutionSteps.innerHTML = resolution.map((step, idx) => `
          <div class="flex gap-3 items-start">
            <span class="flex-shrink-0 w-6 h-6 bg-green-100 text-green-700 rounded-full flex items-center justify-center text-xs font-semibold">${step.step || idx + 1}</span>
            <div class="flex-1">
              <p class="text-sm font-medium text-app-text">${escapeHtml(step.action || '')}</p>
              ${step.rationale ? `<p class="text-xs text-app-muted mt-1">${escapeHtml(step.rationale)}</p>` : ''}
            </div>
          </div>
        `).join('');
        resolutionSection.classList.remove('hidden');
      } else {
        resolutionSection.classList.add('hidden');
      }
    }

    // Field Proposals
    const fieldProposalsList = document.getElementById('fieldProposalsList');
    const fieldProposalsSection = document.getElementById('fieldProposalsSection');
    if (fieldProposalsList && fieldProposalsSection) {
      const proposals = analysis.field_proposals || [];
      if (proposals.length > 0) {
        fieldProposalsList.innerHTML = proposals.map(p => `
          <div class="flex items-center justify-between p-2 bg-purple-50 rounded-lg">
            <div>
              <span class="text-sm font-medium text-app-text">${escapeHtml(p.field_label || p.field_name || '')}</span>
              <span class="text-xs text-app-muted ml-2">${escapeHtml(p.reason || '')}</span>
            </div>
            <span class="px-2 py-1 text-xs font-medium bg-white rounded border border-purple-200">${escapeHtml(String(p.proposed_value || ''))}</span>
          </div>
        `).join('');
        fieldProposalsSection.classList.remove('hidden');
      } else {
        fieldProposalsSection.classList.add('hidden');
      }
    }

    // Intent & Sentiment
    const intentText = document.getElementById('intentText');
    const sentimentText = document.getElementById('sentimentText');
    if (intentText) intentText.textContent = analysis.intent || '-';
    if (sentimentText) sentimentText.textContent = analysis.sentiment || '-';

    // Risk Tags
    const riskTagsList = document.getElementById('riskTagsList');
    const riskTagsSection = document.getElementById('riskTagsSection');
    if (riskTagsList && riskTagsSection) {
      const riskTags = analysis.risk_tags || [];
      if (riskTags.length > 0) {
        riskTagsList.innerHTML = riskTags.map(tag => `
          <span class="px-2 py-1 text-xs font-medium bg-red-100 text-red-700 rounded-full">${escapeHtml(tag)}</span>
        `).join('');
        riskTagsSection.classList.remove('hidden');
      } else {
        riskTagsSection.classList.add('hidden');
      }
    }

    // Meta
    const metaAnalysisId = document.getElementById('metaAnalysisId');
    const metaLatency = document.getElementById('metaLatency');
    const metaModel = document.getElementById('metaModel');
    if (metaAnalysisId) metaAnalysisId.textContent = `ID: ${result.analysis_id?.substring(0, 8) || '-'}`;
    if (metaLatency) metaLatency.textContent = `${meta.latency_ms || 0}ms`;
    if (metaModel) metaModel.textContent = meta.llm_model || '-';

    // Escalation History
    renderEscalationHistory(analysis.escalation_history);

    // Current Status
    renderCurrentStatus(analysis.current_status);

    // HITL Feedback
    showFeedbackSection(result.analysis_id);

    // Evidence 업데이트
    renderEvidence(analysis.evidence || []);
  }

  // =============================================================================
  // Escalation History
  // =============================================================================

  function renderEscalationHistory(escalation) {
    const section = document.getElementById('escalationSection');
    const content = document.getElementById('escalationContent');
    if (!section || !content) return;

    if (!escalation || !escalation.has_escalation) {
      section.classList.add('hidden');
      return;
    }

    section.classList.remove('hidden');

    const handoffs = escalation.handoffs || [];
    let html = '';

    if (handoffs.length > 0) {
      html += '<div class="space-y-3">';
      handoffs.forEach((h) => {
        html += `
          <div class="escalation-handoff pl-4 py-2">
            <div class="flex items-center gap-2 mb-1">
              <span class="px-2 py-0.5 text-xs font-medium bg-amber-100 text-amber-800 rounded">${escapeHtml(h.from || '?')}</span>
              <svg class="w-4 h-4 text-app-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14 5l7 7m0 0l-7 7m7-7H3"/>
              </svg>
              <span class="px-2 py-0.5 text-xs font-medium bg-blue-100 text-blue-800 rounded">${escapeHtml(h.to || '?')}</span>
            </div>
            ${h.reason ? `<p class="text-sm text-app-text">${escapeHtml(h.reason)}</p>` : ''}
            ${h.evidence && h.evidence.length > 0
              ? `<p class="text-xs text-app-muted mt-1">Evidence: msg #${h.evidence.join(', #')}</p>`
              : ''}
          </div>
        `;
      });
      html += '</div>';
    }

    if (escalation.notes) {
      html += `<p class="text-sm text-app-muted mt-2 italic">${escapeHtml(escalation.notes)}</p>`;
    }

    content.innerHTML = html;
  }

  // =============================================================================
  // Current Status
  // =============================================================================

  function renderCurrentStatus(status) {
    const section = document.getElementById('currentStatusSection');
    const content = document.getElementById('currentStatusContent');
    if (!section || !content) return;

    if (!status || !status.state) {
      section.classList.add('hidden');
      return;
    }

    section.classList.remove('hidden');

    const stateConfig = {
      'resolved': { label: '해결됨', class: 'status-resolved' },
      'pending': { label: '대기 중', class: 'status-pending' },
      'unresolved': { label: '미해결', class: 'status-unresolved' }
    };

    const config = stateConfig[status.state] || stateConfig['unresolved'];
    let html = `
      <div class="flex items-center gap-2 mb-2">
        <span class="px-3 py-1 text-sm font-semibold rounded-full ${config.class}">${config.label}</span>
      </div>
    `;

    const pendingItems = status.pending_items || [];
    if (pendingItems.length > 0) {
      html += '<div class="space-y-1 mt-2">';
      html += '<p class="text-xs font-medium text-app-muted uppercase">대기 항목</p>';
      pendingItems.forEach(item => {
        html += `
          <div class="flex items-center gap-2 text-sm text-app-text">
            <span class="w-1.5 h-1.5 bg-amber-400 rounded-full flex-shrink-0"></span>
            ${escapeHtml(item)}
          </div>
        `;
      });
      html += '</div>';
    }

    if (status.notes) {
      html += `<p class="text-sm text-app-muted mt-2 italic">${escapeHtml(status.notes)}</p>`;
    }

    content.innerHTML = html;
  }

  // =============================================================================
  // HITL Feedback
  // =============================================================================

  let _currentAnalysisId = null;

  function showFeedbackSection(analysisId) {
    const section = document.getElementById('feedbackSection');
    if (!section) return;

    _currentAnalysisId = analysisId;
    section.classList.remove('hidden');

    // Reset button states
    document.querySelectorAll('.feedback-btn').forEach(btn => {
      btn.classList.remove('selected-helpful', 'selected-not-helpful');
      btn.disabled = false;
    });
    const resultDiv = document.getElementById('feedbackResult');
    if (resultDiv) resultDiv.classList.add('hidden');
  }

  async function submitFeedback(eventType) {
    if (!_currentAnalysisId) return;

    const resultDiv = document.getElementById('feedbackResult');

    try {
      const url = window.BACKEND_CONFIG.getUrl('/api/assist/feedback/submit');
      const headers = window.BACKEND_CONFIG.getHeaders();

      const response = await fetch(url, {
        method: 'POST',
        headers: headers,
        body: JSON.stringify({
          analysis_id: _currentAnalysisId,
          event_type: eventType,
          rating: eventType === 'helpful' ? 5 : 1
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      await response.json();

      // Update button visual state
      document.querySelectorAll('.feedback-btn').forEach(btn => {
        btn.classList.remove('selected-helpful', 'selected-not-helpful');
      });

      if (eventType === 'helpful') {
        document.getElementById('feedbackHelpfulBtn')?.classList.add('selected-helpful');
      } else {
        document.getElementById('feedbackNotHelpfulBtn')?.classList.add('selected-not-helpful');
      }

      // Show result
      if (resultDiv) {
        resultDiv.textContent = eventType === 'helpful'
          ? '감사합니다! 피드백이 저장되었습니다.'
          : '피드백이 저장되었습니다. 수정 버튼을 눌러 더 정확한 응답을 제출할 수 있습니다.';
        resultDiv.className = `mt-3 p-3 rounded-lg text-sm ${
          eventType === 'helpful' ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'
        }`;
        resultDiv.classList.remove('hidden');
      }

    } catch (error) {
      console.error('[AnalysisUI] Feedback submit failed:', error);
      if (resultDiv) {
        resultDiv.textContent = `피드백 전송 실패: ${error.message}`;
        resultDiv.className = 'mt-3 p-3 rounded-lg text-sm bg-red-50 text-red-700';
        resultDiv.classList.remove('hidden');
      }
    }
  }

  function openEditModal() {
    const modal = document.getElementById('editModal');
    if (!modal) return;

    const analysis = analysisStore.analysisResult?.analysis || {};

    // Pre-fill form with current analysis data
    const summaryField = document.getElementById('editSummary');
    const rootCauseField = document.getElementById('editRootCause');
    const confidenceField = document.getElementById('editConfidence');

    if (summaryField) summaryField.value = analysis.narrative?.summary || '';
    if (rootCauseField) rootCauseField.value = analysis.root_cause || '';
    if (confidenceField) confidenceField.value = analysis.confidence || 0.7;

    modal.classList.remove('hidden');
  }

  function closeEditModal() {
    const modal = document.getElementById('editModal');
    if (modal) modal.classList.add('hidden');
  }

  async function saveEditedResponse() {
    if (!_currentAnalysisId) return;

    const summary = document.getElementById('editSummary')?.value || '';
    const rootCause = document.getElementById('editRootCause')?.value || '';
    const confidence = parseFloat(document.getElementById('editConfidence')?.value) || 0.7;

    const saveBtn = document.getElementById('saveEditBtn');
    if (saveBtn) saveBtn.disabled = true;

    try {
      const url = window.BACKEND_CONFIG.getUrl('/api/assist/feedback/edit');
      const headers = window.BACKEND_CONFIG.getHeaders();

      const response = await fetch(url, {
        method: 'POST',
        headers: headers,
        body: JSON.stringify({
          analysis_id: _currentAnalysisId,
          approved_response: {
            narrative: { summary: summary },
            root_cause: rootCause,
            confidence: confidence
          }
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      closeEditModal();

      // Show success in feedback area
      const resultDiv = document.getElementById('feedbackResult');
      if (resultDiv) {
        resultDiv.textContent = '수정된 응답이 저장되었습니다. 학습 데이터로 활용됩니다.';
        resultDiv.className = 'mt-3 p-3 rounded-lg text-sm bg-green-50 text-green-700';
        resultDiv.classList.remove('hidden');
      }

    } catch (error) {
      console.error('[AnalysisUI] Save edited response failed:', error);
      console.error('[AnalysisUI] Save failed:', error.message);
    } finally {
      if (saveBtn) saveBtn.disabled = false;
    }
  }

  function setupFeedbackHandlers() {
    // Helpful/Not Helpful buttons
    document.getElementById('feedbackHelpfulBtn')?.addEventListener('click', () => submitFeedback('helpful'));
    document.getElementById('feedbackNotHelpfulBtn')?.addEventListener('click', () => submitFeedback('not_helpful'));

    // Edit button → open modal
    document.getElementById('feedbackEditBtn')?.addEventListener('click', openEditModal);

    // Modal close/cancel
    document.getElementById('closeEditModalBtn')?.addEventListener('click', closeEditModal);
    document.getElementById('cancelEditBtn')?.addEventListener('click', closeEditModal);

    // Modal save
    document.getElementById('saveEditBtn')?.addEventListener('click', saveEditedResponse);

    // Close modal on backdrop click
    document.getElementById('editModal')?.addEventListener('click', (e) => {
      if (e.target.id === 'editModal') closeEditModal();
    });
  }

  // =============================================================================
  // Evidence Tab
  // =============================================================================

  function renderEvidence(evidenceList) {
    const placeholder = document.getElementById('evidencePlaceholder');
    const list = document.getElementById('evidenceList');
    const items = document.getElementById('evidenceItems');

    if (!placeholder || !list || !items) return;

    if (evidenceList.length === 0) {
      placeholder.classList.remove('hidden');
      list.classList.add('hidden');
      return;
    }

    placeholder.classList.add('hidden');
    list.classList.remove('hidden');

    // Store evidence for filtering
    window._evidenceData = evidenceList;

    renderEvidenceItems(evidenceList);
  }

  function renderEvidenceItems(evidenceList, filter = 'all') {
    const items = document.getElementById('evidenceItems');
    if (!items) return;

    const filtered = filter === 'all'
      ? evidenceList
      : evidenceList.filter(e => e.source_type === filter);

    if (filtered.length === 0) {
      items.innerHTML = '<p class="text-sm text-app-muted text-center py-4">해당하는 증거가 없습니다.</p>';
      return;
    }

    items.innerHTML = filtered.map(e => {
      const typeLabels = {
        'conversation': '대화',
        'ticket_field': '필드',
        'kb_article': 'KB',
        'similar_case': '유사 사례'
      };
      const typeLabel = typeLabels[e.source_type] || e.source_type;
      const relevancePercent = Math.round((e.relevance_score || 0) * 100);

      return `
        <div class="bg-app-card border border-app-border rounded-lg p-3">
          <div class="flex items-center justify-between mb-2">
            <span class="px-2 py-0.5 text-xs font-medium bg-gray-100 text-gray-700 rounded">${escapeHtml(typeLabel)}</span>
            <span class="text-xs text-app-muted">관련도: ${relevancePercent}%</span>
          </div>
          <p class="text-sm text-app-text">${escapeHtml(e.excerpt || '')}</p>
          ${e.source_id ? `<p class="text-xs text-app-muted mt-1">ID: ${escapeHtml(e.source_id)}</p>` : ''}
        </div>
      `;
    }).join('');
  }

  function setupEvidenceFilters() {
    document.querySelectorAll('.evidence-filter-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const filter = e.currentTarget.dataset.filter;

        // Active 상태 업데이트
        document.querySelectorAll('.evidence-filter-btn').forEach(b => b.classList.remove('active'));
        e.currentTarget.classList.add('active');

        // 필터링
        if (window._evidenceData) {
          renderEvidenceItems(window._evidenceData, filter);
        }
      });
    });
  }

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

  function showTicker(message) {
    const ticker = document.getElementById('analysisTicker');
    const tickerMessage = document.getElementById('tickerMessage');
    if (ticker) ticker.classList.remove('hidden');
    if (tickerMessage) tickerMessage.textContent = message;
  }

  function hideTicker() {
    const ticker = document.getElementById('analysisTicker');
    if (ticker) ticker.classList.add('hidden');
  }

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

    // Retry button
    document.getElementById('retryAnalyzeBtn')?.addEventListener('click', () => {
      errorDiv.remove();
      if (placeholder) placeholder.classList.remove('hidden');
      runAnalysis();
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

    // Analyze button
    const analyzeBtn = document.getElementById('analyzeBtn');
    if (analyzeBtn) {
      analyzeBtn.addEventListener('click', runAnalysis);
    }

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
    showFeedbackSection
  };

})();
