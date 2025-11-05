/**
 * UI Module - 단순화된 UI 렌더링
 */

window.TicketUI = {
  // 렌더링 안정성을 위한 플래그
  _isRenderingInProgress: false,

  /**
   * 로딩 표시
   */
  showLoading() {
    const overlay = document.getElementById('loading-overlay');
    if (overlay) {
      overlay.style.display = 'flex';
    }

    // summary-section이 collapsed 상태라면 해제
    const summarySection = document.querySelector('.summary-section');
    if (summarySection && summarySection.classList.contains('collapsed')) {
      summarySection.classList.remove('collapsed');
    }
  },

  /**
   * 항목이 실제 "티켓"인지 판별 (KB/문서 등은 제외)
   */
  _isTicketItem(item) {
    if (!item || typeof item !== 'object') return false;
    // 명시적 타입 체크 우선
    const type = item.type || item.doc_type || item.kind || item.source_type;
    if (typeof type === 'string') {
      const t = type.toLowerCase();
      if (t.includes('kb') || t.includes('knowledge') || t.includes('doc')) return false;
      if (t.includes('ticket')) return true;
    }
    // 암시적 특성: ticket_id 혹은 Freshdesk 필드들이 있으면 티켓으로 간주
    if (item.ticket_id || item.id) return true;
    // 메타데이터에 티켓 힌트
    const mt = item.metadata || item.platform_metadata || {};
    if (mt && (mt.type === 'ticket' || mt.source === 'freshdesk')) return true;
    // 기본값: status 숫자 추출 가능하면 티켓로 취급
    const s = this._extractNumericStatus(item);
    return Number.isInteger(s);
  },

  /**
   * 다양한 위치의 status에서 숫자 상태를 안정적으로 추출
   */
  _extractNumericStatus(item) {
    if (!item) return NaN;
    // 후보 경로 모음
    const candidates = [
      // 우선적으로 명시적 ID 필드들
      item.status_id,
      item.metadata?.status_id,
      item.platform_metadata?.status_id,
      item.fields?.status_id,
      // 그 다음 라벨/혼합 문자열이 올 수 있는 status
      item.status,
      item.metadata?.status,
      item.platform_metadata?.status,
      item.fields?.status,
    ];
    for (const c of candidates) {
      if (c === null || c === undefined) continue;
      const n = parseInt(c, 10);
      if (!Number.isNaN(n)) return n;
      // 문자열에 숫자 섞인 경우 (예: "5 - Closed")
      if (typeof c === 'string') {
        const m = c.match(/\d+/);
        if (m) {
          const v = parseInt(m[0], 10);
          if (!Number.isNaN(v)) return v;
        }
      }
    }
    return NaN;
  },

  /**
   * 로딩 숨기기
   */
  hideLoading() {
    const overlay = document.getElementById('loading-overlay');
    if (overlay) {
      overlay.style.display = 'none';
    }
  },

  /**
   * 감정 상태 업데이트 (새로운 헤더 디자인용)
   */
  updateEmotionElement(emotionText) {
    const emotionStatus = document.getElementById('emotionStatus');
    if (!emotionStatus) {
      console.error('❌ emotionStatus 엘리먼트를 찾을 수 없습니다');
      return;
    }
    if (!emotionText) {
      console.warn('⚠️ 감정 텍스트가 없습니다');
      return;
    }

    // 로딩 텍스트 제거하고 감정 상태 텍스트 업데이트
    emotionStatus.innerHTML = '';
    emotionStatus.textContent = emotionText;
  },

  /**
   * 스케일톤 콘텐츠 표시 (비권장)
   * @deprecated 각 API 서비스에서 showSkeletonForSection을 직접 호출하는 것을 권장
   */
  showSkeletonContent() {
    console.warn('showSkeletonContent() is deprecated. Use showSkeletonForSection() instead.');
    // this.showSkeletonForSection('summary');
    // this.showSkeletonForSection('similar_tickets');
    // this.showSkeletonForSection('kb_documents');
    // this.showSkeletonForHeader();
  },

  /**
   * 특정 섹션의 스케일톤 표시
   */
  showSkeletonForSection(sectionType) {
    switch (sectionType) {
      case 'summary':
        this._showSummarySkeleton();
        break;
      case 'similar_tickets':
        this._showSimilarTicketsSkeleton();
        break;
      case 'kb_documents':
        this._showKBDocumentsSkeleton();
        break;
    }
  },

  /**
   * 특정 섹션의 스케일톤 숨기기
   */
  hideSkeletonForSection(sectionType) {

    const skeletonSelectors = {
      'summary': '.summary-skeleton',
      'similar_tickets': '.similar-tickets-skeleton',
      'kb_documents': '.kb-documents-skeleton',
      'emotion': '.emotion-skeleton'
    };

    const selector = skeletonSelectors[sectionType];
    if (selector) {
      const skeletons = document.querySelectorAll(selector);
      skeletons.forEach(skeleton => skeleton.remove());
    }
  },

  /**
   * 모든 스케일톤 숨기기
   */
  hideAllSkeletons() {
    // 모든 섹션의 스케일톤 제거
    this.hideSkeletonForSection('summary');
    this.hideSkeletonForSection('similar_tickets');
    this.hideSkeletonForSection('kb_documents');
    this.hideSkeletonForSection('emotion');

    // 추가로 남아있을 수 있는 모든 스케일톤 요소 제거
    const allSkeletons = document.querySelectorAll('[class*="skeleton"]');
    allSkeletons.forEach(skeleton => skeleton.remove());
  },

  /**
   * 요약 섹션 스케일톤
   */
  _showSummarySkeleton() {
    const summaryText = document.getElementById('summaryText');
    if (summaryText) {
      // 이미 스켈레톤이 있거나 다른 콘텐츠가 있으면 재삽입하지 않음 (idempotent)
      const hasSkeleton = summaryText.querySelector('.summary-skeleton');
      const hasAnyContent = summaryText.children.length > 0;
      if (hasSkeleton || hasAnyContent) {
        return;
      }
      const skeleton = document.createElement('div');
      skeleton.className = 'summary-skeleton';
      skeleton.innerHTML = `
        <div class="skeleton-line long"></div>
        <div class="skeleton-line medium"></div>
        <div class="skeleton-line long"></div>
        <div class="skeleton-line short"></div>
        <div class="skeleton-line long"></div>
        <div class="skeleton-line medium"></div>
      `;
      summaryText.appendChild(skeleton);
    }
  },

  /**
   * 유사 티켓 섹션 스케일톤
   */
  _showSimilarTicketsSkeleton() {
    const container = document.getElementById('similarTicketsContainer');
    if (container) {
      const skeletonCards = Array.from({ length: 3 }, () => `
        <div class="similar-tickets-skeleton content-card">
          <div class="card-header">
            <div class="skeleton-text small"></div>
            <div class="skeleton-badge"></div>
          </div>
          <div class="card-body">
            <div class="skeleton-line medium"></div>
            <div class="skeleton-line long"></div>
            <div class="skeleton-line short"></div>
            <div class="skeleton-meta">
              <div class="skeleton-text tiny"></div>
              <div class="skeleton-text tiny"></div>
              <div class="skeleton-text tiny"></div>
            </div>
          </div>
        </div>
      `).join('');

      container.innerHTML = skeletonCards;
    }
  },

  /**
   * KB 문서 섹션 스케일톤
   */
  _showKBDocumentsSkeleton() {
    const container = document.getElementById('kbDocumentsContainer');
    if (container) {
      const skeletonCards = Array.from({ length: 3 }, () => `
        <div class="kb-documents-skeleton content-card">
          <div class="card-header">
            <div class="skeleton-text small"></div>
            <div class="skeleton-badge"></div>
          </div>
          <div class="card-body">
            <div class="skeleton-line medium"></div>
            <div class="skeleton-line long"></div>
            <div class="skeleton-line short"></div>
          </div>
        </div>
      `).join('');

      container.innerHTML = skeletonCards;
    }
  },

  /**
   * 헤더 메타데이터 표시
   * FDK 데이터(요청자, 우선순위, 담당자, 그룹, 상태) 표시
   */
  showSkeletonForHeader() {
    // 이 함수는 실제로는 사용되지 않음 - updateTicketHeader에서 직접 처리
  },

  /**
   * 진행률 업데이트 - 스트리밍 이벤트와 연동
   * @param {string} stage - 현재 진행 단계 (ticket, summary, similar, kb, insights, complete)
   * @param {number} percentage - 전체 진행률 (0-100)
   */
  updateProgress(stage, percentage) {
    const progressBar = document.getElementById('progress-bar');
    const progressText = document.getElementById('progress-percentage');

    if (progressBar) {
      progressBar.style.width = percentage + '%';
    }

    if (progressText) {
      progressText.textContent = percentage + '%';
    }

    // 모든 스테이지 요소 가져오기
    const allStages = document.querySelectorAll('.stage-item');
    const stageOrder = ['ticket', 'summary', 'similar', 'kb'];
    const currentStageIndex = stageOrder.indexOf(stage);

    // 이전 단계들은 completed로 표시
    allStages.forEach((stageEl) => {
      const stageType = stageEl.getAttribute('data-stage');
      const stageIndex = stageOrder.indexOf(stageType);

      if (stageIndex < currentStageIndex) {
        // 이전 단계: 완료됨
        stageEl.classList.remove('in-progress');
        stageEl.classList.add('completed');
        const statusIcon = stageEl.querySelector('.stage-status');
        if (statusIcon) statusIcon.textContent = '✅';
      } else if (stageIndex === currentStageIndex) {
        // 현재 단계: 진행 중
        stageEl.classList.add('in-progress');
        stageEl.classList.remove('completed');
        const statusIcon = stageEl.querySelector('.stage-status');
        if (statusIcon) statusIcon.textContent = '🔄';
      } else {
        // 다음 단계: 대기 중
        stageEl.classList.remove('in-progress', 'completed');
        const statusIcon = stageEl.querySelector('.stage-status');
        if (statusIcon) statusIcon.textContent = '⏳';
      }
    });

    // 완료 단계에서는 모든 스테이지를 completed로
    if (stage === 'complete' || percentage === 100) {
      allStages.forEach(stageEl => {
        stageEl.classList.remove('in-progress');
        stageEl.classList.add('completed');
        const statusIcon = stageEl.querySelector('.stage-status');
        if (statusIcon) statusIcon.textContent = '✅';
      });
    }
  },

  /**
   * 에러 표시
   */
  showError(message) {
    const errorDisplay = document.getElementById('error-display');
    if (errorDisplay) {
      // Check if message is a translation key
      if (message === 'error_data_load_failed') {
        errorDisplay.innerHTML = `
          <div class="error-message">
            <i>⚠️</i> <span data-i18n="error_data_load_failed">데이터를 불러오는데 실패했습니다.</span>
          </div>
        `;
        // Update translation immediately
        if (window.I18nManager) {
          window.I18nManager.updateUI(errorDisplay);
        }
      } else {
        // For other messages, show as is
        errorDisplay.innerHTML = `
          <div class="error-message">
            <i>⚠️</i> ${message}
          </div>
        `;
      }
      errorDisplay.style.display = 'block';
    }
  },

  /**
   * 특정 스테이지에서 에러 표시
   * @param {string} stage - 에러가 발생한 단계
   * @param {string} message - 에러 메시지
   */
  showErrorOnStage(stage, message) {
    // 에러가 발생한 스테이지 표시
    const stageElement = document.querySelector(`[data-stage="${stage}"]`);
    if (stageElement) {
      stageElement.classList.remove('completed', 'in-progress');
      stageElement.classList.add('error');
      const statusIcon = stageElement.querySelector('.stage-status');
      if (statusIcon) {
        statusIcon.textContent = '❌';
      }
    }

    // 로딩 오버레이에 에러 메시지 표시
    const loadingSubtitle = document.querySelector('.loading-subtitle');
    if (loadingSubtitle) {
      loadingSubtitle.textContent = message;
      loadingSubtitle.style.color = '#ef4444'; // 빨간색
    }

    // 진행률 바 색상 변경
    const progressBar = document.getElementById('progress-bar');
    if (progressBar) {
      progressBar.style.background = '#ef4444'; // 빨간색
    }
  },

  /**
   * 에러 숨기기
   */
  hideError() {
    const errorDisplay = document.getElementById('error-display');
    if (errorDisplay) {
      errorDisplay.style.display = 'none';
    }
  },

  /**
   * AI 요약 업데이트 (스트리밍 지원)
   */
  updateSummaryStream(chunk, isComplete = false, rendering = null) {
    const summaryText = document.getElementById('summaryText');
    if (!summaryText) return;

    // 첫 번째 청크인 경우 초기화
    if (!this._summaryBuffer) {
      this._summaryBuffer = '';
      summaryText.innerHTML = '';
      // 초저지연 프리뷰 모드 시작
      this._summaryFastPreview = true;
    }

    // 청크 추가
    this._summaryBuffer += chunk;

    // 1) 프리뷰: 아주 초반엔 포맷팅 없이 빠르게 그리기 (첫 120자까지)
    if (this._summaryFastPreview && this._summaryBuffer.length < 120 && !isComplete) {
      summaryText.textContent = this._summaryBuffer; // 가장 빠른 페인트
    } else {
      // 2) 본 렌더링: 포맷팅 적용으로 전환
      if (!rendering) {
        const summaryType = window.Core?.state?.summaryType || 'structural';
        rendering = window.Core?.getDefaultRendering(summaryType);
      }
      summaryText.innerHTML = this._formatSummaryContent(this._summaryBuffer, rendering);
      this._summaryFastPreview = false; // 전환 완료
    }

    // 완료 시 버퍼 초기화
    if (isComplete) {
      delete this._summaryBuffer;
      delete this._summaryFastPreview;
    }
  },


  /**
   * AI 요약 업데이트 (전체)
   */
  updateSummary(content, rendering = null) {
    // DOM이 준비되었는지 재확인
    if (document.readyState !== 'complete') {
      console.warn('⚠️ DOM이 아직 완전히 로드되지 않음. 100ms 후 재시도...');
      setTimeout(() => this.updateSummary(content, rendering), 100);
      return;
    }

    // summary-section에서 collapsed 클래스 제거
    const summarySection = document.querySelector('.summary-section');
    if (summarySection && summarySection.classList.contains('collapsed')) {
      summarySection.classList.remove('collapsed');
    }

    const summaryText = document.getElementById('summaryText');

    if (summaryText) {
      // 요소가 DOM에 실제로 연결되어 있는지 확인
      if (!summaryText.isConnected) {
        console.error('❌ summaryText 요소가 DOM에 연결되지 않음');
        return;
      }

      // 스트리밍 버퍼가 존재하는 경우 완료 처리
      if (this._summaryBuffer) {
        // 스트리밍 완료로 처리
        this.updateSummaryStream('', true, rendering);
      } else {
        // 최적화된 렌더링 처리 (완전한 새 콘텐츠)
        summaryText.innerHTML = this._formatSummaryContent(content, rendering);
      }
    } else {
      console.error('❌ summaryText 요소를 찾을 수 없음');
    }
  },

  /**
   * 요약 콘텐츠 포맷팅 - YAML 중심 동적 렌더링
   */
  _formatSummaryContent(content, rendering = null) {
    const formattingHelpers = this._createFormattingHelpers();
    content = this._preprocessContent(content, rendering);
    const sections = this._extractSections(content, rendering);
    const cleanedSections = this._cleanIntroTexts(sections, rendering);
    const formattedSections = this._formatSections(cleanedSections, formattingHelpers);

    return this._joinSections(formattedSections, rendering);
  },

  /**
   * 포맷팅 헬퍼 함수들 생성
   */
  _createFormattingHelpers() {
    const escapeMap = {
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#039;'
    };

    const escapeHtml = (text) => {
      return text.replace(/[&<>"']/g, (m) => escapeMap[m]);
    };

    const processBold = (text) => {
      const escaped = escapeHtml(text);
      return escaped.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    };

    return { escapeHtml, processBold };
  },

  /**
   * 콘텐츠 전처리
   */
  _preprocessContent(content, rendering) {
    if (rendering && rendering.type === 'temporal') {
      // 날짜 패턴을 로케일별 포맷으로 변환
      content = content.replace(/(\*\*)(\d{4})년(\d{1,2})월(\d{1,2})일(\*\*)/g, (match, prefix, year, month, day, suffix) => {
        const dateString = `${year}-${month.padStart(2, '0')}-${day.padStart(2, '0')}T00:00:00Z`;
        const formattedDate = window.Utils ? window.Utils.formatCardDate(dateString) : `${year}년 ${month}월 ${day}일`;
        return `\n${prefix}${formattedDate}${suffix}`;
      });

      // 영어 날짜 패턴도 변환
      content = content.replace(/(\*\*)([A-Z][a-z]+ \d{1,2}, \d{4})(\*\*)/g, (match, prefix, dateStr, suffix) => {
        try {
          const date = new Date(dateStr);
          const formattedDate = window.Utils ? window.Utils.formatCardDate(date.toISOString()) : dateStr;
          return `\n${prefix}${formattedDate}${suffix}`;
        } catch (e) {
          return `\n${match}`;
        }
      });

      content = content.replace(/^\n+/, '');
    }
    return content;
  },

  /**
   * 섹션 추출
   */
  _extractSections(content, rendering) {
    if (rendering && rendering.section_pattern) {
      const sectionPattern = new RegExp(rendering.section_pattern);
      return content.split(sectionPattern);
    }

    // 폴백: 기본 패턴
    return content.split(/\n(?=🔍|🎯|✅|💡|\*\*\d{4}년|\*\*[A-Z][a-z]+ \d{1,2}, \d{4})/);
  },

  /**
   * Intro 텍스트 정리
   */
  _cleanIntroTexts(sections, rendering) {
    if (rendering && rendering.options && rendering.options.remove_intro_text) {
      sections = this._removeConfiguredIntroText(sections);
    }

    return this._removeGlobalIntroPatterns(sections);
  },

  /**
   * 설정된 intro 텍스트 제거
   */
  _removeConfiguredIntroText(sections) {
    const firstSectionIndex = sections.findIndex(section =>
      section.trim() && (
        section.includes('**') ||
        /^(🔍|🎯|✅|💡|📊|📌|⚡|🔮)/.test(section.trim())
      )
    );

    return firstSectionIndex > 0 ? sections.slice(firstSectionIndex) : sections;
  },

  /**
   * 전역 intro 패턴 제거
   */
  _removeGlobalIntroPatterns(sections) {
    const introPatterns = [
      /^(이 티켓의 내용은|이 고객 문의는|이 지원 요청은|본 티켓은).*/,
      /^(Based on the Korean|Based on the English|Based on the content|Based on this ticket).*/,
      /^(This ticket|This customer|This support|This issue).*(is about|contains|describes).*/,
      /^(根据韩语|基于韩语|根据内容|基于此票据).*/,
      /^(この韓国語|この内容|このチケット).*(について|は).*/
    ];

    return sections.map(section => {
      if (!section.trim()) return section;

      const lines = section.split('\n');
      let filteredLines = [...lines];

      if (lines.length > 0) {
        const firstLine = lines[0].trim();
        for (const pattern of introPatterns) {
          if (pattern.test(firstLine)) {
            filteredLines = lines.slice(1);
            break;
          }
        }
      }

      return filteredLines.join('\n');
    }).filter(section => section.trim());
  },

  /**
   * 섹션 포맷팅
   */
  _formatSections(sections, helpers) {
    return sections.map(section => this._formatSingleSection(section, helpers));
  },

  /**
   * 단일 섹션 포맷팅
   */
  _formatSingleSection(section, helpers) {
    if (!section.trim()) return '';

    const lines = section.split('\n');
    const headerLine = lines[0];
    const contentLines = lines.slice(1);

    let html = this._formatSectionHeader(headerLine, helpers.processBold);
    const contentHtml = this._formatSectionContent(contentLines, helpers.processBold, headerLine);

    if (contentHtml) {
      html += `<div>${contentHtml}</div>`;
    }

    return html;
  },

  /**
   * 섹션 헤더 포맷팅
   */
  _formatSectionHeader(headerLine, processBold) {
    if (/^(🔍|🎯|✅|💡)/.test(headerLine)) {
      return `<h3>${processBold(headerLine)}</h3>`;
    }
    return '';
  },

  /**
   * 섹션 콘텐츠 포맷팅
   */
  _formatSectionContent(contentLines, processBold, headerLine = '') {
    // 헤더가 이모지로 시작하지 않는 경우 첫 번째 라인으로 포함
    const lines = /^(🔍|🎯|✅|💡)/.test(headerLine) ? contentLines : [headerLine, ...contentLines];

    return lines
      .filter(line => line.trim())
      .map(line => {
        const trimmedLine = line.trim();

        if (trimmedLine.startsWith('-')) {
          const listContent = trimmedLine.substring(1).trim();
          return `<div style="margin-left: 1rem;">• ${processBold(listContent)}</div>`;
        }

        return `<div>${processBold(line)}</div>`;
      })
      .join('<br>');
  },

  /**
   * 섹션 결합
   */
  _joinSections(formattedSections, rendering) {
    const separator = rendering && rendering.options && rendering.options.add_section_breaks ? '<br/>' : '';
    return formattedSections.join(separator);
  },

  /**
   * 티켓 컨테이너 요소 가져오기
   */
  _getTicketsContainer() {
    return document.getElementById('similarTicketsContainer');
  },

  /**
   * 티켓 수 업데이트
   */
  _updateTicketsCount(count) {
    const countElement = document.getElementById('similarTicketsCount');
    if (countElement) {
      countElement.textContent = count;
    }
  },

  /**
   * 인사이트 패널 숨기기
   */
  _hideInsightPanel() {
    const panel = document.getElementById('insightPanel');
    if (panel) {
      panel.style.display = 'none';
    }
  },

  /**
   * 유사 티켓 카드 렌더링 (메타데이터만, 요약은 스켈레톤)
   */
  renderSimilarTicketCards(tickets) {
    const container = this._getTicketsContainer();
    if (!container || !this._validateTickets(tickets)) {
      return;
    }

    this._storeTicketsGlobally(tickets);
    this._updateTicketsCount(tickets.length);
    this._hideInsightPanel();

    this._renderTicketCards(container, tickets);
  },

  /**
   * 티켓 유효성 검사
   */
  _validateTickets(tickets) {
    return tickets && tickets.length > 0;
  },

  /**
   * 티켓 데이터 전역 저장
   */
  _storeTicketsGlobally(tickets) {
    window.Core.state.data.similarTickets = tickets || [];
  },

  /**
   * 티켓 카드 렌더링
   */
  _renderTicketCards(container, tickets) {
    container.innerHTML = tickets.map(ticket =>
      this._renderTicketCard(ticket)
    ).join('');
  },

  /**
   * 개별 티켓 카드 렌더링
   */
  _renderTicketCard(ticket) {
    const ticketData = this._extractTicketData(ticket);
    const metaData = this._extractMetaData(ticket);

    return this._buildTicketCardHTML(ticketData, metaData);
  },

  /**
   * 티켓 기본 데이터 추출
   */
  _extractTicketData(ticket) {
    const similarity = ticket.similarity_score || ticket.score || 0;
    const similarityPercent = similarity > 1 ? similarity : similarity * 100;

    return {
      id: ticket.id,
      title: ticket.title || '',  // 백엔드는 title 필드 사용
      description: '',  // 메타데이터 전송 방식에서는 description 불필요
      similarity: similarityPercent,
      scoreClass: this._getSimilarityScoreClass(similarityPercent),
      createdAt: ticket.metadata?.created_at || null
    };
  },

  /**
   * 유사도 점수 클래스 결정
   */
  _getSimilarityScoreClass(similarityPercent) {
    return similarityPercent > 80 ? 'score-high' :
      similarityPercent > 60 ? 'score-medium' : 'score-low';
  },

  /**
   * 메타데이터 추출 (새 벡터DB 스키마 필드 기반)
   */
  _extractMetaData(ticket) {
    // 새 벡터DB 스키마 필드들을 우선적으로 사용
    // 사용자 제공 스키마 + attachments 필드 지원

    // 1. Priority (keyword)
    const priority = ticket.priority ||
      ticket.metadata?.priority ||
      'Normal';

    // 2. Status (keyword)
    const status = ticket.status ||
      ticket.metadata?.status ||
      'Open';

    // 3. Requester (벡터DB 직접 필드)
    const requestorName = ticket.requester || 'Unknown';

    // 4. Responder (벡터DB 직접 필드)
    const responder = ticket.responder || 'Unknown';
    ticket.agent_name ||  // 레거시 호환성
      ticket.metadata?.agent_name ||
      'Unassigned';

    // 5. Group (keyword) - 새 스키마
    const group = ticket.group ||
      ticket.metadata?.group ||
      ticket.group_name ||  // 레거시 호환성
      ticket.metadata?.group_name ||
      'Unknown';

    // 6. Company (keyword) - 새 스키마
    const company = ticket.company ||
      ticket.metadata?.company ||
      ticket.company_name ||  // 레거시 호환성
      ticket.metadata?.company_name ||
      'Unknown';

    // 7. Timestamps (keyword)
    const createdAt = ticket.created_at ||
      ticket.metadata?.created_at ||
      ticket.created ||
      ticket.metadata?.created ||
      null;

    const updatedAt = ticket.updated_at ||
      ticket.metadata?.updated_at ||
      ticket.updated ||
      ticket.metadata?.updated ||
      null;

    // 8. Additional fields from new schema
    const platform = ticket.platform || ticket.metadata?.platform || null;
    const source = ticket.source || ticket.metadata?.source || null;
    const product = ticket.product || ticket.metadata?.product || null;
    const tags = ticket.tags || ticket.metadata?.tags || null;
    const agent = ticket.agent || ticket.metadata?.agent || null;
    const hierarchy = ticket.hierarchy || ticket.metadata?.hierarchy || null;

    // 9. Integer fields
    const hits = ticket.hits || ticket.metadata?.hits || 0;
    const thumbsUp = ticket.thumbs_up || ticket.metadata?.thumbs_up || 0;
    const thumbsDown = ticket.thumbs_down || ticket.metadata?.thumbs_down || 0;

    return {
      // 벡터에 저장된 라벨 텍스트를 직접 사용 (ID→라벨 변환 불필요)
      priorityText: priority || 'Unknown',
      statusLabel: status || 'Unknown',
      requestorName: requestorName,
      responder: responder,
      group: group,
      company: company,

      // 새 스키마 필드들
      createdAt: createdAt,
      updatedAt: updatedAt,
      platform: platform,
      source: source,
      product: product,
      tags: tags,
      agent: agent,
      hierarchy: hierarchy,
      hits: hits,
      thumbsUp: thumbsUp,
      thumbsDown: thumbsDown,
      // 첨부파일 연계 로직 중단에 따라 제외됨
    };
  },

  /**
   * 티켓 카드 HTML 구성
   */
  _buildTicketCardHTML(ticketData, metaData) {
    const header = this._buildCardHeader(ticketData);
    const body = this._buildCardBody(ticketData, metaData);

    return `
      <div class="content-card" data-ticket-id="${ticketData.id}">
        ${header}
        ${body}
      </div>
    `;
  },

  /**
   * 카드 헤더 구성
   */
  _buildCardHeader(ticketData) {
    return `
      <div class="card-header">
        <span class="card-id">#${ticketData.id}</span>
        <span class="similarity-score ${ticketData.scoreClass}">
          ${Math.round(ticketData.similarity)}%
        </span>
      </div>
    `;
  },

  /**
   * 카드 본문 구성
   */
  _buildCardBody(ticketData, metaData) {
    const title = this._buildCardTitle(ticketData);
    const meta = this._buildCardMeta(metaData, ticketData.createdAt);
    const summary = this._buildCardSummary(ticketData.id);
    const actions = this._buildCardActions(ticketData.id);

    return `
      <div class="card-body">
        ${title}
        ${meta}
        ${summary}
        ${actions}
      </div>
    `;
  },

  /**
   * 카드 제목 구성
   */
  _buildCardTitle(ticketData) {
    return `
      <h3 class="card-title">${this._escapeHtml(ticketData.title)}</h3>
    `;
  },

  /**
   * 카드 메타정보 구성 (새 스키마 필드들 포함)
   */
  _buildCardMeta(metaData, createdAt) {
    const formattedDate = window.Utils ? window.Utils.formatCardDate(createdAt) : 'N/A';

    return `
      <div class="card-meta">
        <span class="meta-item meta-date">📅 ${formattedDate}</span>
        <span class="meta-item meta-status">${metaData.statusLabel}</span>
        <span class="meta-item meta-priority">${metaData.priorityText}</span>
        <span class="meta-item meta-requester">👤 ${metaData.requestorName}</span>
        <span class="meta-item meta-responder">👩‍💼 ${metaData.responder}</span>
        <span class="meta-item meta-group">🏢 ${metaData.group}</span>
        <span class="meta-item meta-company">🏪 ${metaData.company}</span>
      </div>
    `;
  },

  /**
   * 카드 요약 섹션 구성
   */
  _buildCardSummary(ticketId) {
    return `
      <div class="card-summary" id="summary-${ticketId}" style="margin: 8px 0; padding: 8px; background: #f8f9fa; border-radius: 4px; font-size: 13px; line-height: 1.4; color: #495057;">
        <span class="skeleton-text" style="width: 80%;"></span>
      </div>
    `;
  },

  /**
   * 카드 액션 버튼 구성
   */
  _buildCardActions(ticketId) {
    return `
      <div class="card-actions">
        <button class="card-btn primary" id="summary-btn-${ticketId}" onclick="window.TicketUI.viewSummary(${ticketId})">
          <span id="summary-btn-text-${ticketId}" data-i18n="button_summary">👁️ 요약보기</span>
          <span id="summary-loading-${ticketId}" style="display:none;">⏳ 로딩중...</span>
        </button>
        <button class="card-btn" onclick="window.TicketUI.viewOriginal(${ticketId})">
          <span data-i18n="button_original">📄 원본보기</span>
        </button>
      </div>
    `;
  },

  /**
   * 감정 타입 판단 유틸리티 (다국어 지원)
   */
  getEmotionType(emotion) {
    if (!emotion) return 'neutral';

    // LLM이 보내준 감정 데이터를 그대로 사용 (하드코딩 제거)
    // 백엔드에서 "긍정적", "부정적", "중립적"으로 보내주므로 그대로 표시
    const emotionLower = emotion.toLowerCase();

    if (emotionLower.includes('긍정') || emotionLower.includes('positive')) {
      return 'positive';
    }
    if (emotionLower.includes('부정') || emotionLower.includes('negative')) {
      return 'negative';
    }

    return 'neutral';
  },

  /**
   * 유사 티켓 요약 업데이트 (스켈레톤 → 실제 요약으로 스트리밍 교체)
   */
  updateSimilarTicketSummary(ticketId, summary, isStreaming = false, isFirst = false) {
    this._initializeStreamingState();

    if (this._shouldSkipUpdate(ticketId, isStreaming)) {
      return;
    }

    if (this._isRenderingLocked(ticketId)) {
      setTimeout(() => this.updateSimilarTicketSummary(ticketId, summary, isStreaming, isFirst), 50);
      return;
    }

    this._setRenderingLock(ticketId, true);

    try {
      const { finalSummary, shouldUpdate } = this._processSummaryData(ticketId, summary, isStreaming, isFirst);

      if (shouldUpdate && finalSummary) {
        this._updateCoreState(ticketId, finalSummary);
        this._updateSummaryElement(ticketId, finalSummary, isStreaming);
        this._updateDetailView(ticketId, summary, isStreaming, isFirst);
      }
    } finally {
      this._setRenderingLock(ticketId, false);
    }
  },

  /**
   * 스트리밍 상태 초기화
   */
  _initializeStreamingState() {
    if (!this._ticketSummaryBuffers) this._ticketSummaryBuffers = {};
    if (!this._summaryCompleted) this._summaryCompleted = {};
    if (!this._renderingLocks) this._renderingLocks = {};
  },

  /**
   * 업데이트를 건너뛸지 확인
   */
  _shouldSkipUpdate(ticketId, isStreaming) {
    const key = String(ticketId);
    return this._summaryCompleted && this._summaryCompleted[key] && isStreaming;
  },

  /**
   * 렌더링 잠금 상태 확인
   */
  _isRenderingLocked(ticketId) {
    return this._renderingLocks && this._renderingLocks[String(ticketId)];
  },

  /**
   * 렌더링 잠금 설정/해제
   */
  _setRenderingLock(ticketId, locked) {
    const key = String(ticketId);
    if (locked) {
      this._renderingLocks[key] = true;
    } else {
      delete this._renderingLocks[key];
    }
  },

  /**
   * 요약 데이터 처리
   */
  _processSummaryData(ticketId, summary, isStreaming, isFirst) {
    let finalSummary = '';
    let shouldUpdate = false;
    const key = String(ticketId);

    if (isStreaming && summary) {
      // 스트리밍 데이터 처리
      if (isFirst || !this._ticketSummaryBuffers[key]) {
        this._ticketSummaryBuffers[key] = '';
      }
      this._ticketSummaryBuffers[key] += summary;
      finalSummary = this._ticketSummaryBuffers[key];
      shouldUpdate = true;
    } else if (!isStreaming) {
      // 스트리밍 완료 처리
      finalSummary = summary || this._ticketSummaryBuffers[key];

      if (finalSummary) {
        shouldUpdate = true;
        if (!this._summaryCompleted) this._summaryCompleted = {};
        this._summaryCompleted[key] = true;
        delete this._ticketSummaryBuffers[key];
      }
    }

    return { finalSummary, shouldUpdate };
  },

  /**
   * Core 상태 업데이트
   */
  _updateCoreState(ticketId, finalSummary) {
    const key = String(ticketId);
    if (!window.Core.state.ticketSummaries) {
      window.Core.state.ticketSummaries = {};
    }
    window.Core.state.ticketSummaries[key] = finalSummary;
  },

  /**
   * 요약 엘리먼트 업데이트
   */
  _updateSummaryElement(ticketId, finalSummary, isStreaming) {
    // 카드 레벨의 요약은 카드 목록에서는 보여주지 않음.
    // 요약 업데이트는 Core 상태에만 반영하고, 실제 DOM 노출은 상세보기에서만 수행한다.
    // (detail view가 열려 있는 경우에만 detailSummaryContent가 업데이트 됨)
    clearTimeout(this._updateTimeouts?.[ticketId]);
    if (!this._updateTimeouts) this._updateTimeouts = {};

    this._updateTimeouts[ticketId] = setTimeout(() => {
      // Core 상태는 이미 _updateCoreState에서 업데이트되므로 여기서는 추가적인 DOM 변경을 최소화.
      // 다만, 상세보기가 열려있다면 해당 컨테이너를 갱신하도록 _updateDetailView를 호출한다.
      if (this._isDetailViewOpen(ticketId)) {
        this._updateDetailView(ticketId, finalSummary, isStreaming, false);
      }

      // 카드 레벨 summary 요소는 항상 숨김 상태로 유지 (CSS 인라인 스타일로 강제)
      try {
        const summaryElement = document.getElementById(`summary-${ticketId}`);
        if (summaryElement) {
          summaryElement.style.display = 'none';
        }
      } catch (e) {
        // ignore
      }

      delete this._updateTimeouts[ticketId];
    }, isStreaming ? 100 : 0);
  },

  /**
   * 상세 보기 업데이트
   */
  _updateDetailView(ticketId, summary, isStreaming, isFirst) {
    if (!this._isDetailViewOpen(ticketId)) return;

    const detailSummaryContent = document.getElementById('detailSummaryContent');
    if (!detailSummaryContent) return;

    this._removeSkeleton(detailSummaryContent, ticketId);

    if (isStreaming) {
      this._handleStreamingDetailView(detailSummaryContent, ticketId, isFirst);
    } else if (summary) {
      this._handleCompletedDetailView(detailSummaryContent, ticketId, summary);
    } else {
      this._handleEmptyDetailView(detailSummaryContent, ticketId);
    }
  },

  /**
   * 상세 보기가 열려있는지 확인
   */
  _isDetailViewOpen(ticketId) {
    return window.Core.state.ticketDetailView?.isDetailView &&
      window.Core.state.ticketDetailView?.currentTicketData?.id === ticketId;
  },

  /**
   * 스켈레톤 제거
   */
  _removeSkeleton(container, ticketId) {
    const skeleton = container.querySelector(`#summary-skeleton-${ticketId}`);
    if (skeleton) {
      skeleton.style.transition = 'opacity 0.3s ease-out';
      skeleton.style.opacity = '0';
      setTimeout(() => {
        if (skeleton && skeleton.parentNode) {
          skeleton.remove();
        }
      }, 300);
    }
  },

  /**
   * 스트리밍 상세 보기 처리
   */
  _handleStreamingDetailView(container, ticketId, isFirst) {
    if (!this._streamingElements) this._streamingElements = {};

    if (isFirst || !this._streamingElements[ticketId]) {
      this._setupStreamingContainer(container, ticketId);
    }

    const streamContainer = this._streamingElements[ticketId];
    if (streamContainer) {
      streamContainer.innerHTML = this._formatTicketSummary(
        this._ticketSummaryBuffers[ticketId]
      );
    }
  },

  /**
   * 스트리밍 컨테이너 설정
   */
  _setupStreamingContainer(container, ticketId) {
    // 스켈레톤 제거
    const hasSkeletonContent = container.querySelector('.skeleton-lines');
    if (hasSkeletonContent) {
      container.innerHTML = '';
    }

    // 기존 컨테이너 제거
    const existingContainer = container.querySelector(`#stream-container-${ticketId}`);
    if (existingContainer) {
      existingContainer.remove();
    }

    // 새 컨테이너 생성
    const streamContainer = document.createElement('div');
    streamContainer.id = `stream-container-${ticketId}`;
    container.appendChild(streamContainer);
    this._streamingElements[ticketId] = streamContainer;
  },

  /**
   * 완료된 상세 보기 처리
   */
  _handleCompletedDetailView(container, ticketId, summary) {
    // 버퍼 정리
    if (this._ticketSummaryBuffers && this._ticketSummaryBuffers[ticketId]) {
      this._updateCoreState(ticketId, this._ticketSummaryBuffers[ticketId]);
      delete this._ticketSummaryBuffers[ticketId];

      if (this._streamingElements && this._streamingElements[ticketId]) {
        delete this._streamingElements[ticketId];
      }
    }

    container.innerHTML = this._formatTicketSummary(
      summary
    );
  },

  /**
   * 빈 상세 보기 처리
   */
  _handleEmptyDetailView(container, ticketId) {
    if (this._streamingElements && this._streamingElements[ticketId]) {
      const finalContent = this._ticketSummaryBuffers[ticketId] || '';
      if (finalContent) {
        container.innerHTML = this._formatTicketSummary(
          finalContent
        );
      }
      delete this._streamingElements[ticketId];
    }
  },

  /**
   * 티켓 헤더 정보 업데이트
   */
  updateTicketsHeader(tickets) {
    try {
      const statsElement = document.getElementById('ticketsStats');
      if (!statsElement) {
        console.warn('⚠️ ticketsStats 엘리먼트를 찾을 수 없습니다');
        return;
      }

      if (!tickets || tickets.length === 0) {
        const totalText = window.t ? window.t('tickets_total').replace('{count}', '0') : '🎫 Total 0';
        statsElement.textContent = totalText;
        return;
      }

      // 집계는 '티켓' 항목만 대상으로 함 (KB/문서 제외)
      const ticketItems = tickets.filter(t => this._isTicketItem(t));

      // Freshdesk 공통 규칙: 4(Resolved), 5(Closed)만 '해결됨', 나머지는 모두 '진행중'
      const total = ticketItems.length;

      // 항목이 하나도 없으면 총계 0 처리
      if (total === 0) {
        const totalText = window.t ? window.t('tickets_total').replace('{count}', '0') : '🎫 Total 0';
        const resolvedText = window.t ? window.t('tickets_resolved').replace('{count}', '0') : '✅ Resolved: 0';
        const inProgressText = window.t ? window.t('tickets_in_progress').replace('{count}', '0') : '🔄 In Progress: 0';
        const relevanceText = window.t ? window.t('tickets_relevance_low') : '🎯 Relevance: Low';
        statsElement.textContent = `${totalText} | ${resolvedText} | ${inProgressText} | ${relevanceText}`;
        return;
      }

      const resolved = ticketItems.reduce((count, t) => {
        const idNum = this._extractNumericStatus(t);
        return count + ((idNum === 4 || idNum === 5) ? 1 : 0);
      }, 0);
      const inProgress = total - resolved;

      // 관련도 계산 (평균 유사도 점수 기반)  
      const basis = ticketItems.length > 0 ? ticketItems : tickets;
      const avgSimilarity = basis.reduce((sum, t) => {
        const score = t.relevance_score || t.similarity_score || t.score || 0;
        return sum + score;
      }, 0) / (basis.length || 1);
      let relevanceKey = 'tickets_relevance_high';
      if (avgSimilarity < 0.6) relevanceKey = 'tickets_relevance_low';
      else if (avgSimilarity < 0.8) relevanceKey = 'tickets_relevance_medium';

      // 번역된 텍스트 조합 - 디버깅 추가

      const totalText = window.t ? window.t('tickets_total').replace('{count}', total) : `🎫 Total ${total}`;
      const resolvedText = window.t ? window.t('tickets_resolved').replace('{count}', resolved) : `✅ Resolved: ${resolved}`;
      const inProgressText = window.t ? window.t('tickets_in_progress').replace('{count}', inProgress) : `🔄 In Progress: ${inProgress}`;
      const relevanceText = window.t ? window.t(relevanceKey) : '🎯 Relevance: High';


      const finalText = `${totalText} | ${resolvedText} | ${inProgressText} | ${relevanceText}`;

      statsElement.textContent = finalText;
    } catch (error) {
      console.error('❌ updateTicketsHeader 오류:', error);
      // 에러가 발생해도 계속 진행하도록 함
    }
  },

  /**
   * 유사 티켓 렌더링 (카드 먼저 렌더링, 요약은 나중에 스트리밍)
   */
  renderSimilarTickets(tickets) {
    // UI 렌더링 - 유사 티켓 로깅 제거됨

    // 새로운 티켓 로드 시 완료 플래그 초기화
    this._summaryCompleted = {};
    this._ticketSummaryBuffers = {};

    // 티켓 헤더 업데이트 (안전하게)
    if (typeof this.updateTicketsHeader === 'function') {
      this.updateTicketsHeader(tickets);
    }

    // 전역 상태에 티켓 목록을 저장하여 viewSummary 등에서 참조할 수 있게 함
    window.Core.state.data.similarTickets = tickets || [];

    const container = document.getElementById('similarTicketsContainer');

    if (!container) {
      console.error('❌ similarTicketsContainer 요소를 찾을 수 없음');
      return;
    }

    if (!tickets || tickets.length === 0) {
      // 유사 티켓이 없을 때 사용자 친화적인 메시지 표시
      const count = document.getElementById('similarTicketsCount');
      if (count) {
        count.textContent = '0';
      }

      container.innerHTML = `
        <div class="no-results-message">
          <div style="text-align: center; padding: 40px 20px; color: #6b7280;">
            <div style="font-size: 48px; margin-bottom: 16px;">🔍</div>
            <h3 style="font-size: 18px; font-weight: 600; margin-bottom: 8px; color: #374151;">
              ${window.t('no_similar_tickets_title') || '유사한 티켓을 찾을 수 없습니다'}
            </h3>
            <p style="font-size: 14px; color: #6b7280; line-height: 1.5;">
              ${(window.t('no_similar_tickets_message') || '현재 티켓과 유사도가 {percent}% 이상인 과거 티켓이 없습니다.<br>이 문제는 새로운 유형의 문의일 가능성이 있습니다.').replace('{percent}', Math.round(window.Core?.state?.data?.minQualityScore * 100))}
            </p>
            <div style="margin-top: 16px; padding: 12px; background: #f3f4f6; border-radius: 8px;">
              <p style="font-size: 13px; color: #4b5563; margin: 0;">
                ${window.t('no_similar_tickets_tip') || '💡 <strong>팁:</strong> 검색 기준이 너무 엄격할 수 있습니다.<br>더 많은 결과를 보려면 관리자에게 문의하세요.'}
              </p>
            </div>
          </div>
        </div>
      `;


      return;
    }

    const count = document.getElementById('similarTicketsCount');
    if (count) {
      count.textContent = tickets.length;
    }

    // 자동 분석 결과 계산 - 현재 사용하지 않음
    // 추후 인사이트 패널 복원 시 사용 예정

    // insight 패널 숨기기 (요청에 따라 제거)

    // 벡터 DB에 저장된 라벨 텍스트를 직접 사용 (ID → 라벨 변환 불필요)

    container.innerHTML = tickets.map(ticket => {
      const ticketId = String(ticket.id);
      // 백엔드에서 title만 전송하므로 title만 사용
      const ticketTitle = ticket.title || '제목 없음';
      // 유사도 점수 - 백엔드에서 전송된 원본 점수를 그대로 사용
      const similarity = ticket.similarity_score || ticket.score || 0;

      // created_at은 metadata 또는 최상위 레벨에서 찾기
      const createdAt = ticket.metadata?.created_at || ticket.created_at || null;

      const similarityPercent = (similarity > 1 ? similarity : similarity * 100);
      const scoreClass = similarityPercent >= 80 ? 'score-high' : similarityPercent >= 60 ? 'score-medium' : 'score-low';

      // priority와 status는 metadata 또는 최상위 레벨에서 찾기
      const priority = ticket.metadata?.priority || ticket.priority;
      const status = ticket.metadata?.status || ticket.status;

      // 벡터에 저장된 라벨 텍스트를 직접 사용 (변환 함수 호출 없음)
      const priorityText = priority || 'Unknown';
      const statusLabel = status || 'Unknown';

      // 벡터DB 직접 필드 사용
      const requestorName = ticket.requester || 'Unknown';

      // 메타데이터 전송 방식에서는 description 불필요; 빈 문자열으로 처리하여 '설명 없음' 표시를 피함
      const descriptionText = ticket.description_text || ticket.metadata?.description_text || ticket.description || '';

      return `
          <div class="content-card" data-ticket-id="${this._escapeHtml(ticketId)}">
        <div class="card-header">
          <span class="card-id">#${ticketId}</span>
          <span class="similarity-score ${scoreClass}">
            ${Math.round(similarityPercent)}%
          </span>
        </div>
        <div class="card-body">
          <h3 class="card-title">${this._escapeHtml(ticketTitle)}</h3>
          <p class="card-excerpt">${this._escapeHtml(descriptionText)}</p>
          <div class="card-meta">
            <span class="meta-item meta-date" data-date="${createdAt}">📅 ${window.Utils ? window.Utils.formatCardDate(createdAt) : 'N/A'}</span>
            <span class="meta-item meta-status">${statusLabel}</span>
            <span class="meta-item meta-priority">${priorityText}</span>
            <span class="meta-item meta-requester">👤 ${requestorName}</span>
          </div>
              <div class="card-summary" id="summary-${ticketId}" style="margin: 8px 0; padding: 8px; background: #f8f9fa; border-radius: 4px; font-size: 13px; line-height: 1.4; color: #495057;">
                <span class="skeleton-text" style="width: 80%;"></span>
              </div>
          <div class="card-actions">
            <button class="card-btn primary" id="summary-btn-${ticketId}" onclick="window.TicketUI.viewSummary('${ticketId}')">
              <span id="summary-btn-text-${ticketId}" data-i18n="button_summary">👁️ 요약보기</span>
              <span id="summary-loading-${ticketId}" style="display:none;">⏳ 로딩중...</span>
            </button>
            <button class="card-btn" onclick="window.TicketUI.viewOriginal('${ticketId}')">
              <span data-i18n="button_original">📄 원본보기</span>
            </button>
          </div>
        </div>
      </div>
      `;
    }).join('');
  },

  /**
   * Articles 헤더 정보 업데이트
   */
  updateArticlesHeader(documents) {
    try {
      const statsElement = document.getElementById('articlesStats');
      if (!statsElement) {
        console.warn('⚠️ articlesStats 엘리먼트를 찾을 수 없습니다');
        return;
      }

      if (!documents || documents.length === 0) {
        const totalText = window.t ? window.t('articles_total').replace('{count}', '0') : '📚 Total 0';
        statsElement.textContent = totalText;
        return;
      }


      const total = documents.length;

      // 관련도 계산 (평균 유사도 점수 기반)
      const avgSimilarity = documents.reduce((sum, doc) => {
        const score = doc.similarity_score || doc.score || doc.relevance_score || 0;
        return sum + score;
      }, 0) / total;
      const relevancePercent = Math.round(avgSimilarity * 100);

      // 만족도 계산 (thumbs_up, thumbs_down 기반)
      const totalRatings = documents.reduce((sum, doc) => {
        const thumbsUp = doc.thumbs_up || 0;
        const thumbsDown = doc.thumbs_down || 0;
        return sum + thumbsUp + thumbsDown;
      }, 0);

      const positiveRatings = documents.reduce((sum, doc) => {
        const thumbsUp = doc.thumbs_up || 0;
        return sum + thumbsUp;
      }, 0);

      const satisfactionPercent = totalRatings > 0 ? Math.round((positiveRatings / totalRatings) * 100) : 0;


      // 번역된 텍스트 조합 (백엔드 데이터에 맞게) - 디버깅 추가

      // 타이틀 바: 건수/관련도 평균/만족도
      const totalText = window.t ? window.t('articles_total').replace('{count}', total) : `📚 Total ${total}`;
      const relevanceText = window.t ? window.t('articles_relevance').replace('{percent}', relevancePercent) : `🎯 Relevance: ${relevancePercent}%`;
      const satisfactionText = window.t ? window.t('articles_satisfaction').replace('{percent}', satisfactionPercent) : `👍 Satisfaction: ${satisfactionPercent}%`;


      const finalText = `${totalText} | ${relevanceText} | ${satisfactionText}`;

      statsElement.textContent = finalText;
    } catch (error) {
      console.error('❌ updateArticlesHeader 오류:', error);
      // 에러가 발생해도 계속 진행하도록 함
    }
  },

  /**
   * KB 문서 렌더링
   */
  renderKBDocuments(documents) {
    // UI 렌더링 - KB 문서 로깅 제거됨

    // Articles 헤더 업데이트 (안전하게)
    if (typeof this.updateArticlesHeader === 'function') {
      this.updateArticlesHeader(documents);
    }

    const container = document.getElementById('kbDocumentsContainer');
    if (!container) {
      console.error('❌ kbDocumentsContainer 요소를 찾을 수 없음');
      return;
    }

    if (!documents || documents.length === 0) {

      // KB 문서가 없을 때 사용자 친화적인 메시지 표시
      const count = document.getElementById('kbDocumentsCount');
      if (count) {
        count.textContent = '0';
      }

      container.innerHTML = `
        <div class="no-results-message">
          <div style="text-align: center; padding: 40px 20px; color: #6b7280;">
            <div style="font-size: 48px; margin-bottom: 16px;">📚</div>
            <h3 style="font-size: 18px; font-weight: 600; margin-bottom: 8px; color: #374151;">
              ${window.t('no_kb_documents_title') || '관련 문서를 찾을 수 없습니다'}
            </h3>
            <p style="font-size: 14px; color: #6b7280; line-height: 1.5;">
              ${(window.t('no_kb_documents_message') || '현재 설정된 품질 기준({percent}%)을 만족하는 지식베이스 문서가 없습니다.<br>더 정확한 검색을 위해 품질 기준이 적용되었습니다.').replace('{percent}', Math.round(window.Core?.state?.data?.minQualityScore * 100))}
            </p>
            <div style="margin-top: 16px; padding: 12px; background: #f3f4f6; border-radius: 8px;">
              <p style="font-size: 13px; color: #4b5563; margin: 0;">
                ${window.t('no_kb_documents_tip') || '💡 <strong>팁:</strong> 이 문제가 자주 발생한다면<br>새로운 KB 문서를 작성하는 것을 고려해보세요.'}
                새로운 KB 문서를 작성하는 것을 고려해보세요.
              </p>
            </div>
          </div>
        </div>
      `;


      return;
    }


    const count = document.getElementById('kbDocumentsCount');
    if (count) {
      count.textContent = documents.length;
    }


    container.innerHTML = documents.map(doc => {
      // 카테고리/폴더 정보 조합
      // let categoryFolderInfo = '';
      if (doc.category || doc.folder_name) {
        const parts = [];
        if (doc.category) parts.push(doc.category);
        if (doc.folder_name && doc.folder_name !== doc.category) parts.push(doc.folder_name);
        // categoryFolderInfo = parts.join('/');
      } else if (doc.folder_path) {
        // 폴더 경로에서 마지막 부분만 추출
        // const pathParts = doc.folder_path.split('/');
        // categoryFolderInfo = pathParts[pathParts.length - 1] || doc.folder_path;
      }

      // 업데이트일 포맷 (년도/월/일 포함)
      const updatedDate = window.Utils ? window.Utils.formatCardDate(doc.updated_at) : 'N/A';

      // 메타정보는 이모지로 간단하게 표시
      // 아티클 ID
      const articleId = doc.id || doc.article_id || '';

      return `
      <div class="content-card">
        <div class="card-header">
          <span class="card-id">#${articleId}</span>
          <span class="similarity-score ${this._getScoreClass(doc.score)}">
            ${Math.round(doc.score * 100)}%
          </span>
        </div>
        <div class="card-body">
          <h3 class="card-title">${this._escapeHtml(doc.title)}</h3>
          <div class="card-meta">
            <span class="meta-item meta-date" data-date="${doc.updated_at || ''}">📅 ${updatedDate}</span>
            <span class="meta-item meta-views">👀 ${doc.hits || 0}</span>
            <span class="meta-item meta-thumbs-up">👍 ${doc.thumbs_up || 0}</span>
            <span class="meta-item meta-thumbs-down">👎 ${doc.thumbs_down || 0}</span>
            ${doc.folder_name ? `<span class="meta-item meta-folder">📁 ${doc.folder_name}</span>` : ''}
          </div>
          <div class="card-actions">
            <button class="card-btn primary" onclick="window.open('${doc.url}', '_blank')">
              <span data-i18n="button_original">📄 원본보기</span>
            </button>
            <button class="card-btn" onclick="window.copyToClipboard('${doc.url}', this)">
              <span data-i18n="button_copy">📋 복사하기</span>
            </button>
          </div>
        </div>
      </div>
    `}).join('');
  },

  /**
   * 티켓 상세 보기
   */
  async viewTicket(ticketId) {

    // 캐시된 유사 티켓 데이터에서 해당 티켓 찾기
    const tickets = window.Core.state.data.similarTickets;
    const ticketIndex = tickets.findIndex(t => t.id === ticketId);

    if (ticketIndex === -1) {
      console.error('티켓을 찾을 수 없습니다:', ticketId);
      return;
    }

    await this.showTicketDetail(ticketIndex);
  },

  /**
   * 해결방법 적용
   */
  applySolution() {
    // TODO: 해결방법 적용 구현
  },

  /**
   * 티켓 헤더 정보 업데이트 (새 디자인 - 감정 분석만 처리)
   * 새 디자인에서는 감정 분석만 필요하므로 대폭 간소화
   */
  updateTicketHeader(optimizedData, emotionData = null) {
    // 감정분석 데이터가 있으면 업데이트
    if (emotionData && emotionData.emotion) {
      this.updateEmotionElement(emotionData.emotion);
    }

    // 새 디자인에서는 헤더의 메타데이터(요청자, 우선순위 등)가 불필요하므로 처리 생략
    // 모든 티켓 정보는 탭 콘텐츠 영역에서 처리됨
  },

  // 헤더 관련 레거시 메소드들 제거됨 (새 디자인에서 불필요)

  // 구 updateEmotionElement 메소드는 제거됨 - 새 디자인에서는 탭 네비게이션 영역의 emotionStatus 엘리먼트 사용

  /**
   * 중복된 감정 분석 요소 제거 (강화된 버전)
   */
  removeDuplicateEmotions() {
    const metaRow1 = document.getElementById('metaRow1');
    if (!metaRow1) return;

    // 모든 감정 관련 요소 찾기 (skeleton 포함)
    const emotionElements = metaRow1.querySelectorAll('.emotion-skeleton, .meta-item.emotion-loaded, .meta-item:has(.skeleton-text)');
    if (emotionElements.length > 1) {
      // 가장 최근 것(마지막)을 제외하고 모든 감정 요소 제거
      for (let i = 0; i < emotionElements.length - 1; i++) {
        emotionElements[i].remove();
      }
    }
  },

  /**
   * 헬퍼 함수들
   */
  _escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  },

  _getScoreClass(score) {
    const normalizedScore = score > 1 ? score / 100 : score;
    if (normalizedScore > 0.8) return 'score-high';
    if (normalizedScore > 0.6) return 'score-medium';
    return 'score-low';
  },

  _getStatusClass(status) {
    const statusMap = {
      2: 'open',
      3: 'pending',
      4: 'resolved',
      5: 'closed',
      6: 'waiting-customer',
      7: 'waiting-third-party'
    };
    return statusMap[status] || 'unknown';
  },

  _getStatusLabel(status) {
    // 벡터에 저장된 라벨을 그대로 반환 (변환 불필요)
    return status || 'Unknown';
  },

  _formatDate(dateStr) {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    const now = new Date();
    const diff = now - date;

    if (diff < 86400000) {
      return '오늘';
    } else if (diff < 172800000) {
      return '어제';
    } else {
      return window.Utils ? window.Utils.formatCardDate(date) : date.toLocaleDateString('ko-KR');
    }
  },

  /**
   * 티켓 상세 정보 표시
   */
  async showTicketDetail(ticketIndex) {
    const tickets = window.Core?.state?.data?.similarTickets || [];

    if (!tickets || tickets.length === 0) {
      return;
    }

    if (ticketIndex < 0 || ticketIndex >= tickets.length) {
      return;
    }

    const ticket = tickets[ticketIndex];

    // 이전 티켓의 스트리밍 상태 정리 (원본 구현 복원)
    if (this._streamingElements) {
      // 현재 표시 중인 티켓이 아닌 다른 티켓의 스트리밍 엘리먼트 삭제
      const currentTicketId = ticket.id;
      Object.keys(this._streamingElements).forEach(ticketId => {
        if (String(ticketId) !== String(currentTicketId)) {
          delete this._streamingElements[ticketId];
        }
      });
    }

    // 상태 업데이트
    if (!window.Core.state.ticketDetailView) {
      window.Core.state.ticketDetailView = {};
    }
    window.Core.state.ticketDetailView.isDetailView = true;
    window.Core.state.ticketDetailView.currentTicketIndex = ticketIndex;
    window.Core.state.ticketDetailView.currentTicketData = ticket;

    // 상세 화면 렌더링
    await this.renderTicketDetail(ticket, ticketIndex, tickets.length);

    // 모달에서 상태 저장 (원본 구현 복원)
    if (window.Core?.state?.isModalView) {
      window.Core.autoSaveState();
    }
  },

  /**
   * 티켓 상세 화면 렌더링
   */
  async renderTicketDetail(ticket, ticketIndex, totalTickets) {
    const container = document.getElementById('similarTicketsContainer');
    let detailContainer = document.getElementById('ticketDetailContainer');

    // 상세 컨테이너가 없으면 동적으로 생성 (원본 구현 복원)
    if (!detailContainer) {
      detailContainer = document.createElement('div');
      detailContainer.id = 'ticketDetailContainer';
      detailContainer.style.display = 'none';

      // 적절한 위치에 삽입 (similarTicketsContainer 바로 다음)
      if (container && container.parentNode) {
        container.parentNode.insertBefore(detailContainer, container.nextSibling);
      } else {
        // 컨테이너가 없으면 body에 추가
        document.body.appendChild(detailContainer);
      }
    }

    // 컨테이너 전환
    const ticketsHeader = document.getElementById('ticketsHeader');
    if (ticketsHeader) {
      ticketsHeader.style.display = 'none';
    }
    if (container) container.style.display = 'none';
    detailContainer.style.display = 'block';

    // 상세 화면 HTML 구성
    const detailHTML = this._buildTicketDetailHTML(ticket, ticketIndex, totalTickets);
    detailContainer.innerHTML = detailHTML;

    // 요약 로딩 시작
    await this._loadTicketSummary(ticket);
  },

  /**
   * 티켓 상세 HTML 구성
   */
  _buildTicketDetailHTML(ticket, ticketIndex, totalTickets) {
    const ticketId = ticket.id || 'N/A';
    const ticketTitle = ticket.title || '제목 없음';
    // const similarity = ticket.score || ticket.similarity_score || 0;
    // const similarityPercent = similarity * 100;
    // const scoreClass = similarityPercent > 80 ? 'high' : similarityPercent > 60 ? 'medium' : 'low';
    const createdAt = ticket.metadata?.created_at || ticket.created_at || null;
    const status = ticket.metadata?.status || ticket.platform_metadata?.status || ticket.status;
    const priority = ticket.metadata?.priority || ticket.platform_metadata?.priority || ticket.priority;

    // 벡터에 저장된 라벨 텍스트를 직접 사용 (변환 불필요)
    const priorityText = priority || 'Unknown';
    const statusLabel = status || 'Unknown';

    // 새 스키마 필드들을 우선적으로 사용하여 요청자 정보 추출
    // 벡터DB 직접 필드 사용
    const requestorName = ticket.requester || 'Unknown';

    return `
      <div class="ticket-detail-view">
        <div class="detail-header">
          <button class="back-btn" onclick="window.TicketUI.goBackToList()">
            ← <span data-i18n="nav_list">목록</span>
          </button>
          <div class="detail-navigation">
            <button class="nav-btn primary" onclick="window.TicketUI.navigateToTicket('prev')" ${totalTickets <= 1 ? 'disabled' : ''}>
              ◀ <span data-i18n="nav_previous">이전</span>
            </button>
            <span class="nav-info">${ticketIndex + 1} / ${totalTickets}</span>
            <button class="nav-btn primary" onclick="window.TicketUI.navigateToTicket('next')" ${totalTickets <= 1 ? 'disabled' : ''}>
              <span data-i18n="nav_next">다음</span> ▶
            </button>
          </div>
        </div>
        
        <div class="detail-content">
          <div class="detail-meta">
            <div class="meta-header">
              <h2 class="detail-title">#${ticketId} ${this._escapeHtml(ticketTitle)}</h2>
            </div>
            
            <div class="card-meta">
              <span class="meta-item meta-date" data-date="${createdAt}">📅 ${window.Utils ? window.Utils.formatCardDate(createdAt) : 'N/A'}</span>
              <span class="meta-item meta-status">${statusLabel}</span>
              <span class="meta-item meta-priority">${priorityText}</span>
              <span class="meta-item meta-requester">👤 ${requestorName}</span>
            </div>
          </div>
          
          <div class="detail-summary">
            <div class="detail-summary-content" id="detailSummaryContent">
              <div id="summary-skeleton-${ticketId}" class="skeleton-lines">
                <div class="skeleton-line"></div>
                <div class="skeleton-line"></div>
                <div class="skeleton-line short"></div>
              </div>
            </div>
            <div class="card-actions" style="margin-top: 20px; padding-top: 16px; border-top: 1px solid #e5e7eb;">
              <button class="card-btn" onclick="window.TicketUI.viewOriginal(${ticketId})">
                <span data-i18n="button_original">📄 원본보기</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    `;
  },


  /**
   * 티켓 요약 로딩 (원본 구현 복원)
   */
  async _loadTicketSummary(ticket) {
    try {
      const ticketId = ticket.id;

      // 이미 저장된 요약이 있는 경우 표시
      if (window.Core?.state?.ticketSummaries?.[ticketId]) {
        this.updateSimilarTicketSummary(ticketId, window.Core.state.ticketSummaries[ticketId], false, false);
        return;
      }

      // 티켓 객체에 요약이 있는 경우 표시
      if (ticket.summary) {
        this.updateSimilarTicketSummary(ticketId, ticket.summary, false, false);
        return;
      }

      // Core 모듈의 loadSummary 메서드를 사용하여 요약 요청
      if (window.Core && window.Core.loadSummary) {
        await window.Core.loadSummary('structural');
      } else {
        // 폴백: 스켈레톤 유지 (요약이 나중에 스트리밍으로 올 수 있음)
        // debug log removed: 티켓 요약 대기 중 (스트리밍)
      }
    } catch (error) {
      console.error('❌ 티켓 요약 로딩 실패:', error);
      this._showSummaryError();
    }
  },

  /**
   * 티켓 요약 표시
   */
  _displayTicketSummary(ticketId, summary) {
    const summaryElement = document.getElementById('detailSummaryContent');
    if (summaryElement) {
      summaryElement.innerHTML = `<div class="summary-content">${this._escapeHtml(summary)}</div>`;
    }
  },

  /**
   * 요약 로딩 에러 표시
   */
  _showSummaryError() {
    const summaryElement = document.getElementById('detailSummaryContent');
    if (summaryElement) {
      summaryElement.innerHTML = `
        <div class="summary-error" style="text-align: center; padding: 20px; color: #dc2626;">
          <div style="font-size: 24px; margin-bottom: 8px;">⚠️</div>
          <div>요약을 불러올 수 없습니다.</div>
          <div style="font-size: 12px; color: #6b7280; margin-top: 4px;">네트워크 연결을 확인하거나 나중에 다시 시도해주세요.</div>
        </div>
      `;
    }
  },


  /**
   * 목록으로 돌아가기
   */
  goBackToList() {

    // 상태 리셋
    if (window.Core.state.ticketDetailView) {
      window.Core.state.ticketDetailView.isDetailView = false;
      window.Core.state.ticketDetailView.currentTicketIndex = -1;
      window.Core.state.ticketDetailView.currentTicketData = null;
    }

    // 목록 화면 복원
    const container = document.getElementById('similarTicketsContainer');
    const detailContainer = document.getElementById('ticketDetailContainer');
    const ticketsHeader = document.getElementById('ticketsHeader');

    if (container && detailContainer) {
      if (ticketsHeader) {
        ticketsHeader.style.display = 'flex';
      }
      container.style.display = 'block';
      detailContainer.style.display = 'none';
    }

    // 모달에서 상태 저장 (원본 구현 복원)
    if (window.Core?.state?.isModalView) {
      window.Core.autoSaveState();
    }
  },

  /**
   * 이전/다음 티켓으로 이동
   */
  async navigateToTicket(direction) {
    const currentIndex = window.Core.state.ticketDetailView?.currentTicketIndex || 0;
    const tickets = window.Core.state.data.similarTickets;

    if (!tickets.length) {
      return;
    }

    let newIndex;
    if (direction === 'prev') {
      newIndex = currentIndex > 0 ? currentIndex - 1 : tickets.length - 1;
    } else if (direction === 'next') {
      newIndex = currentIndex < tickets.length - 1 ? currentIndex + 1 : 0;
    }

    await this.showTicketDetail(newIndex);
  },

  /**
   * 원본 티켓 보기
   */
  viewOriginal(ticketId) {
    // Ensure ticketId is string (some IDs may be non-numeric)
    const idStr = String(ticketId).replace(/^ticket-/, '');

    // Freshdesk 티켓 URL 생성
    const domain = window.Core.config.domain;
    const ticketUrl = `https://${domain}/a/tickets/${idStr}`;

    // 새 탭에서 티켓 열기
    window.open(ticketUrl, '_blank');
  },

  /**
   * 마크다운 to HTML 변환
   */
  _markdownToHtml(text) {
    if (!text) return '';

    // marked.js 사용 가능한지 확인
    if (typeof marked !== 'undefined' && marked) {
      return marked.parse ? marked.parse(text) : marked(text);
    }

    // marked가 없을 경우 간단한 변환
    return text
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/\n/g, '<br>');
  },

  /**
   * 상세보기 요약 렌더링 (스켈레톤 지원)
   */
  _renderDetailSummary(summaryContent, ticket) {
    const ticketId = ticket.id;
    const savedSummary = window.Core?.state?.ticketSummaries?.[ticketId];

    // 저장된 요약이 있으면 사용, 없으면 스켈레톤
    // (메타데이터 전송 방식에서는 description_text 불필요)
    if (savedSummary) {
      return this._formatTicketSummary(savedSummary);
    }

    // 요약이 없으면 스켈레톤 표시
    return `
      <div class="skeleton-lines" id="summary-skeleton-${ticketId}">
        <div class="skeleton-line"></div>
        <div class="skeleton-line"></div>
        <div class="skeleton-line"></div>
        <div class="skeleton-line short"></div>
        <div class="skeleton-line"></div>
        <div class="skeleton-line medium"></div>
      </div>
    `;
  },

  /**
   * 티켓 요약 포맷팅 (참고자료 섹션 처리 포함)
   */
  _formatTicketSummary(summaryContent) {
    if (!summaryContent) return '';

    // 메인 티켓과 동일하게 원본 텍스트 유지하면서 줄바꿈만 처리
    let formattedContent = summaryContent
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');

    // 기본적인 마크다운 문법 처리
    // Bold: **텍스트** → <strong>텍스트</strong>
    formattedContent = formattedContent.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');

    // 연속된 줄바꿈(2개 이상)을 섹션 구분으로 처리
    formattedContent = formattedContent.replace(/\n\n+/g, '<br><br>');

    // 나머지 단일 줄바꿈을 <br>로 변환
    formattedContent = formattedContent.replace(/\n/g, '<br>');

    // 첨부파일 관련 링크/치환 로직은 정책에 따라 제거됨

    return formattedContent;
  },

  /**
   * 파일 타입에 따른 이모지 반환
   */
  // 첨부파일 관련 유틸 및 다운로드 기능은 중지됨


  /**
   * 유사티켓 자동분석 정보 업데이트
   */
  updateTicketsInsight(insightData) {

    const insightPanel = document.getElementById('ticketsInsight');
    const insightContent = document.getElementById('ticketsInsightContent');

    if (!insightPanel || !insightContent || !insightData) return;

    // 분석 정보가 있으면 패널 표시
    let contentHtml = '';

    if (insightData.total_tickets !== undefined) {
      contentHtml += `<div class="insight-item">📊 총 <strong>${insightData.total_tickets}개</strong> 유사 티켓 발견</div>`;
    }

    if (insightData.high_similarity_count !== undefined) {
      contentHtml += `<div class="insight-item">🔥 <strong>${insightData.high_similarity_count}개</strong> 고유사도 티켓 (80% 이상)</div>`;
    }

    if (insightData.resolved_count !== undefined) {
      contentHtml += `<div class="insight-item">✅ <strong>${insightData.resolved_count}개</strong> 해결된 티켓</div>`;
    }

    if (insightData.common_solutions && insightData.common_solutions.length > 0) {
      contentHtml += `<div class="insight-item">💡 주요 해결방법: ${insightData.common_solutions.join(', ')}</div>`;
    }

    if (contentHtml) {
      insightContent.innerHTML = contentHtml;
      insightPanel.style.display = 'block';
    }
  },

  /**
   * KB 문서 자동분석 정보 업데이트
   */
  updateKBInsight(insightData) {

    const insightPanel = document.getElementById('kbInsight');
    const insightContent = document.getElementById('kbInsightContent');

    if (!insightPanel || !insightContent || !insightData) return;

    // 분석 정보가 있으면 패널 표시
    let contentHtml = '';

    if (insightData.total_documents !== undefined) {
      contentHtml += `<div class="insight-item">📚 총 <strong>${insightData.total_documents}개</strong> 관련 문서 발견</div>`;
    }

    if (insightData.high_relevance_count !== undefined) {
      contentHtml += `<div class="insight-item">⭐ <strong>${insightData.high_relevance_count}개</strong> 고관련도 문서 (80% 이상)</div>`;
    }

    if (insightData.categories && insightData.categories.length > 0) {
      contentHtml += `<div class="insight-item">🏷️ 주요 카테고리: ${insightData.categories.join(', ')}</div>`;
    }

    if (insightData.recommended_docs && insightData.recommended_docs.length > 0) {
      contentHtml += `<div class="insight-item">📖 추천 문서: ${insightData.recommended_docs.slice(0, 2).join(', ')}</div>`;
    }

    if (contentHtml) {
      insightContent.innerHTML = contentHtml;
      insightPanel.style.display = 'block';
    }
  },

  /**
   * 전체 메트릭스 초기화 (로딩 시작 시 호출)
   */
  resetMetrics() {
    // 자동분석 패널 숨기기

    // 글로벌 캐시 초기화 (새로운 티켓 분석 시작)
    this._globalLabelCache = {
      priority: new Map(),
      status: new Map()
    };

    this._globalResponderCache = new Map();

  },

  // ========== 티켓 레이블 유틸리티 (ticket-labels.js 통합) ==========

  // 옵션 캐시 유효시간 (5분)
  LABEL_CACHE_EXPIRY_MS: 5 * 60 * 1000,

  // 이모지 매핑 (숫자 ID 기반)
  PRIORITY_EMOJIS: {
    1: '🔵',  // Low
    2: '😐',  // Medium
    3: '🟡',  // High
    4: '🔴'   // Urgent
  },

  STATUS_EMOJIS: {
    2: '🟢',  // Open
    3: '🟡',  // Pending
    4: '✅',  // Resolved
    5: '⚪',  // Closed
    6: '🟠',  // Waiting on Customer
    7: '🟣'   // Waiting on Third Party
  },

  // 캐시된 옵션 저장소
  _labelCache: {
    priorityOptions: null,
    statusOptions: null,
    lastFetched: null
  },


  /**
   * 캐시된 옵션 가져오기 (ticket_fields 우선 사용)
   */
  async getCachedLabelOptions() {
    const now = Date.now();

    // 캐시 검증 및 반환
    const cachedData = this._validateAndReturnCache(now);
    if (cachedData) {
      return cachedData;
    }

    // FDK 클라이언트 검증
    const client = window.Core?.state?.client;
    if (!client) {
      console.warn('⚠️ FDK client not available for fetching options');
      return null;
    }

    try {
      // API에서 새 데이터 가져오기
      const options = await this._fetchLabelOptions(client);

      // 캐시 업데이트 및 반환
      return this._updateCacheAndReturn(options, now);
    } catch (error) {
      console.error('❌ FDK 옵션 조회 실패:', error);
      return null;
    }
  },

  /**
   * 캐시 유효성 검사 및 반환
   */
  _validateAndReturnCache(now) {
    if (this._labelCache.lastFetched &&
      (now - this._labelCache.lastFetched) < this.LABEL_CACHE_EXPIRY_MS &&
      this._labelCache.priorityOptions && this._labelCache.priorityOptions.length > 0 &&
      this._labelCache.statusOptions && this._labelCache.statusOptions.length > 0) {

      return {
        priorityOptions: this._labelCache.priorityOptions,
        statusOptions: this._labelCache.statusOptions
      };
    }
    return null;
  },

  /**
   * 라벨 옵션 가져오기
   */
  async _fetchLabelOptions(client) {
    let priorityOptions = [];
    let statusOptions = [];

    // 1차: ticket_fields API 시도
    try {
      const apiOptions = await this._fetchFromTicketFieldsAPI(client);
      priorityOptions = apiOptions.priorityOptions;
      statusOptions = apiOptions.statusOptions;
    } catch (error) {
      console.warn('⚠️ ticket_fields API 호출 실패, fallback 시도:', error);
    }

    return { priorityOptions, statusOptions };
  },

  /**
   * Ticket Fields API에서 데이터 가져오기
   */
  async _fetchFromTicketFieldsAPI(client) {
    const [priorityFieldRaw, statusFieldRaw] = await Promise.all([
      client.request.invokeTemplate('getTicketField', {
        context: { fieldType: 'default_priority' }
      }).catch((err) => {
        console.error('❌ Priority field API 호출 실패:', err);
        return null;
      }),
      client.request.invokeTemplate('getTicketField', {
        context: { fieldType: 'default_status' }
      }).catch((err) => {
        console.error('❌ Status field API 호출 실패:', err);
        return null;
      })
    ]);

    const priorityOptions = this._parsePriorityField(priorityFieldRaw);
    const statusOptions = this._parseStatusField(statusFieldRaw);

    return { priorityOptions, statusOptions };
  },

  /**
   * Priority 필드 파싱
   */
  _parsePriorityField(priorityFieldRaw) {
    if (!priorityFieldRaw?.response) {
      return [];
    }

    try {
      const priorityFields = JSON.parse(priorityFieldRaw.response);

      if (Array.isArray(priorityFields) && priorityFields[0]?.choices) {
        const priorityField = priorityFields[0];
        return Object.entries(priorityField.choices).map(([label, id]) => ({
          id: id,
          label: label,
          value: id
        }));
      }
    } catch (err) {
      console.error('❌ Priority 파싱 실패:', err);
    }

    return [];
  },

  /**
   * Status 필드 파싱
   */
  _parseStatusField(statusFieldRaw) {
    if (!statusFieldRaw?.response) {
      return [];
    }

    try {
      const statusFields = JSON.parse(statusFieldRaw.response);

      if (Array.isArray(statusFields) && statusFields[0]?.choices) {
        const statusField = statusFields[0];
        // 백엔드가 단일 문자열 라벨을 보내지 않을 수 있음.
        // 언어 우선 로직은 제거하되, 배열 형태로 들어오면 첫번째 요소를 사용합니다.
        return Object.entries(statusField.choices).map(([id, label]) => {
          let resolvedLabel = label;
          if (Array.isArray(label) || ArrayBuffer.isView(label)) {
            // 배열이면 첫번째 요소를 사용(언어 우선 판단 없음)
            resolvedLabel = label[0];
          } else if (label && typeof label === 'object' && 'label' in label) {
            resolvedLabel = label.label;
          }
          return {
            id: parseInt(id),
            label: resolvedLabel,
            value: parseInt(id)
          };
        });
      }
    } catch (err) {
      console.error('❌ Status 파싱 실패:', err);
    }

    return [];
  },

  // Note: client.data fallback removed — label options now come only from ticket_fields API

  /**
   * 캐시 업데이트 및 결과 반환
   */
  _updateCacheAndReturn(options, now) {
    this._labelCache.priorityOptions = options.priorityOptions;
    this._labelCache.statusOptions = options.statusOptions;
    this._labelCache.lastFetched = now;

    return {
      priorityOptions: options.priorityOptions,
      statusOptions: options.statusOptions
    };
  },

  /**
   * 우선순위 레이블 가져오기
   */
  async getPriorityLabel(ticketData) {
    if (!ticketData || ticketData.priority === undefined) {
      return '정보를 가져올 수 없습니다';
    }

    const priorityId = parseInt(ticketData.priority);
    const emoji = this.PRIORITY_EMOJIS[priorityId] || '📊';

    // 캐시된 옵션 가져오기
    const cachedOptions = await this.getCachedLabelOptions();

    if (!cachedOptions?.priorityOptions?.length) {
      console.error(`❌ 우선순위 옵션 조회 실패 - Priority ID: ${priorityId}`);
      return '정보를 가져올 수 없습니다';
    }


    // ID로 매칭
    const option = cachedOptions.priorityOptions.find(opt => {
      // 다양한 옵션 구조 지원
      if (opt.id === priorityId || opt.value === priorityId) return true;

      // 문자열로 된 ID도 처리
      if (typeof opt.id === 'string' && parseInt(opt.id) === priorityId) return true;
      if (typeof opt.value === 'string' && parseInt(opt.value) === priorityId) return true;

      return false;
    });

    if (option) {
      const label = option.label || option.name || option.text;
      return `${emoji} ${label}`;
    }

    // 옵션을 찾지 못한 경우
    console.warn(`⚠️ 우선순위 레이블을 찾을 수 없음 - ID: ${priorityId}`);
    return '정보를 가져올 수 없습니다';
  },

  /**
   * 상태 레이블 가져오기
   */
  async getStatusLabel(ticketData) {
    if (!ticketData || ticketData.status === undefined) {
      return '정보를 가져올 수 없습니다';
    }

    const statusId = parseInt(ticketData.status);
    const emoji = this.STATUS_EMOJIS[statusId] || '⚪';

    // 캐시된 옵션 가져오기
    const cachedOptions = await this.getCachedLabelOptions();

    if (!cachedOptions?.statusOptions?.length) {
      console.error(`❌ 상태 옵션 조회 실패 - Status ID: ${statusId}`);
      return '정보를 가져올 수 없습니다';
    }


    // ID로 매칭
    const option = cachedOptions.statusOptions.find(opt => {
      // 다양한 옵션 구조 지원
      if (opt.id === statusId || opt.value === statusId) return true;

      // 문자열로 된 ID도 처리
      if (typeof opt.id === 'string' && parseInt(opt.id) === statusId) return true;
      if (typeof opt.value === 'string' && parseInt(opt.value) === statusId) return true;

      // 배열 형태의 choice 지원 [id, english, korean]
      if (Array.isArray(opt) && parseInt(opt[0]) === statusId) return true;

      return false;
    });

    if (option) {
      // 옵션 구조가 다양할 수 있음. 배열이면 먼저 배열 처리.
      let label = null;
      if (Array.isArray(option)) {
        // 배열 형태인 경우 첫번째 요소 사용 (언어 체크 없음)
        label = option[0] !== null ? option[0] : (option[1] !== null ? option[1] : String(option));
      } else if (option && typeof option === 'object') {
        label = option.label || option.name || option.text || option.value || String(option.id);
      } else {
        label = String(option);
      }
      return `${emoji} ${label}`;
    }

    // 옵션을 찾지 못한 경우
    console.warn(`⚠️ 상태 레이블을 찾을 수 없음 - ID: ${statusId}`);
    return '정보를 가져올 수 없습니다';
  },

  /**
   * 캐시 초기화 (새로고침시 사용)
   */
  clearLabelCache() {
    // 기존 레이블 옵션 캐시 초기화
    this._labelCache = {
      priorityOptions: null,
      statusOptions: null,
      lastFetched: null
    };

    // 글로벌 캐시 초기화 (성능 최적화)
    this._globalLabelCache = {
      priority: new Map(),
      status: new Map()
    };

    this._globalResponderCache = new Map();

  },

  /**
   * 유사 티켓 요약 보기 (스켈레톤 먼저 표시, 요약 스트리밍)
   */
  async viewSummary(ticketId) {
    // 티켓 데이터에서 인덱스 찾기 (타입 안전 비교, 여러 가능한 id 필드를 검색)
    const tickets = window.Core?.state?.data?.similarTickets || [];
    const findMatch = (ticket, idToMatch) => {
      const candidates = [
        ticket.id,
        ticket.ticket_id,
        ticket.original_id,
        ticket.metadata && ticket.metadata.original_id,
        ticket.metadata && ticket.metadata.id
      ];
      return candidates.some(c => c !== undefined && c !== null && String(c) === String(idToMatch));
    };

    const ticketIndex = tickets.findIndex(ticket => findMatch(ticket, ticketId));

    if (ticketIndex !== -1) {
      // 버튼 상태 변경 (로딩중 표시)
      const idStr = String(ticketId);
      const btnText = document.getElementById(`summary-btn-text-${idStr}`);
      const btnLoading = document.getElementById(`summary-loading-${idStr}`);
      if (btnText) btnText.style.display = 'none';
      if (btnLoading) btnLoading.style.display = 'inline';

      // 상세보기 화면으로 이동 (스켈레톤 먼저 표시)
      await this.showTicketDetail(ticketIndex);

      // 버튼 상태 복원
      setTimeout(() => {
        if (btnText) btnText.style.display = 'inline';
        if (btnLoading) btnLoading.style.display = 'none';
      }, 500);
    } else {
      console.error(`❌ 티켓 ${ticketId}를 찾을 수 없습니다.`);
      // debug log removed: 사용 가능한 티켓 ID들
      // debug log removed: 검색된 티켓 ID
    }
  },


  /**
   * 새로운 캐시 시스템으로 전체 UI 렌더링
   * @param {Object} cachedData - 기존 캐시된 데이터 (폴백용)
   */
  renderAllFromCache(cachedData = null) {
    // 새로운 캐시 매니저 우선 사용
    if (window.TicketCacheManager && window.Core?.state?.ticketId) {
      try {
        window.TicketCacheManager.initialize(window.Core.state.ticketId);
        const allData = window.TicketCacheManager.getAllCachedData();

        if (allData && Object.keys(allData).length > 0) {
          console.log('✅ 새 캐시 시스템에서 데이터 로드하여 렌더링');
          return this._renderFromNewCacheSystem(allData);
        }
      } catch (e) {
        console.warn('⚠️ 새 캐시 시스템에서 렌더링 실패:', e);
      }
    }

    // 기존 캐시 데이터 폴백
    if (!this._validateCachedData(cachedData)) {
      console.warn('⚠️ 렌더링할 캐시 데이터가 없습니다');
      return false;
    }

    // 중복 렌더링 방지
    if (this._isRenderingInProgress) {
      console.warn('⚠️ 이미 렌더링 진행 중 - 중복 방지');
      return false;
    }

    this._isRenderingInProgress = true;

    try {
      // 기존 캐시 데이터로 렌더링 (폴백)
      console.log('🔄 기존 캐시 데이터로 폴백 렌더링');
      this._renderCachedSummary(cachedData);
      this._renderCachedSimilarTickets(cachedData);
      this._renderCachedKBDocuments(cachedData);
      this._renderCachedHeader(cachedData);

      return true;
    } catch (error) {
      console.error('❌ 기존 캐시 렌더링 중 오류:', error);
      return false;
    } finally {
      setTimeout(() => {
        this._isRenderingInProgress = false;
      }, 100);
    }
  },

  /**
   * 새로운 캐시 시스템으로 렌더링
   */
  _renderFromNewCacheSystem(allData) {
    if (this._isRenderingInProgress) {
      console.warn('⚠️ 이미 렌더링 진행 중 - 중복 방지');
      return false;
    }

    this._isRenderingInProgress = true;

    try {
      // 1. 티켓 요약 렌더링
      if (allData.summary) {
        const summaryData = allData.summary;

        // 현재 요약 타입 결정 (메타데이터에서 복원 또는 기본값)
        const currentType = allData.metadata?.currentSummaryType || window.Core?.state?.summaryType || 'structural';

        // 캐시 매니저의 키 매핑 헬퍼 사용
        const mappedType = window.TicketCacheManager?._mapSummaryType(currentType) || currentType;

        // 해당 타입의 요약 데이터 조회
        let summaryContent = '';
        if (summaryData[mappedType]) {
          summaryContent = summaryData[mappedType];
        } else if (summaryData.structural) {
          summaryContent = summaryData.structural;
          window.Core.state.summaryType = 'structural';
        } else if (summaryData.chronological) {
          summaryContent = summaryData.chronological;
          window.Core.state.summaryType = 'temporal';
        }

        if (summaryContent) {
          // rendering 데이터도 매핑된 타입으로 조회
          const rendering = summaryData.rendering?.[mappedType] || null;
          this.updateSummary(summaryContent, rendering);
          window.Core.state.summaryType = currentType;

          // 토글 UI 업데이트
          if (window.updateToggleUI) {
            window.updateToggleUI();
          }

          console.log(`✅ ${currentType} (${mappedType}) 요약 캐시 렌더링 완료 - rendering 데이터: ${rendering ? '있음' : '없음'}`);
        }

        this.hideSkeletonForSection('summary');
      }

      // 2. 유사 티켓 렌더링
      if (allData.similarTickets?.tickets && Array.isArray(allData.similarTickets.tickets)) {
        this.renderSimilarTickets(allData.similarTickets.tickets);
        this.hideSkeletonForSection('similar_tickets');
        console.log(`✅ 유사 티켓 ${allData.similarTickets.tickets.length}개 캐시 렌더링 완료`);
      }

      // 3. KB 문서 렌더링
      if (allData.kbDocuments?.documents && Array.isArray(allData.kbDocuments.documents)) {
        this.renderKBDocuments(allData.kbDocuments.documents);
        this.hideSkeletonForSection('kb_documents');
        console.log(`✅ KB 문서 ${allData.kbDocuments.documents.length}개 캐시 렌더링 완료`);
      }

      // 4. 메타데이터 렌더링
      if (allData.metadata) {
        this._renderTicketMetadata(allData.metadata);
        console.log('✅ 메타데이터 캐시 렌더링 완료');
      }

      // 5. 채팅 기록 복원 (필요시)
      if (allData.chatRag?.messages || allData.chatGeneral?.messages) {
        console.log('📝 채팅 기록 복원:', {
          rag: allData.chatRag?.messages?.length || 0,
          general: allData.chatGeneral?.messages?.length || 0
        });
      }

      console.log('✅ 새 캐시 시스템 전체 렌더링 완료');
      return true;
    } catch (error) {
      console.error('❌ 새 캐시 시스템 렌더링 중 오류:', error);
      return false;
    } finally {
      setTimeout(() => {
        this._isRenderingInProgress = false;
      }, 100);
    }
  },

  /**
   * 티켓 메타데이터 렌더링
   */
  _renderTicketMetadata(metadata) {
    try {
      // 1. 감정 분석 데이터 복원
      if (metadata.emotionData) {
        this.updateEmotionElement(metadata.emotionData);
        console.log('✅ 감정 분석 데이터 복원');
      }

      // 2. 헤더 정보 복원
      if (metadata.headerInfo) {
        window.Core.state.cachedTicketInfo = metadata.headerInfo;
        console.log('✅ 헤더 정보 복원');
      }

      // 3. 채팅 모드 복원
      if (metadata.currentChatMode) {
        window.Core.state.chatMode = metadata.currentChatMode;
        if (window.updateChatToggleUI) {
          window.updateChatToggleUI();
        }
        console.log(`✅ 채팅 모드 복원: ${metadata.currentChatMode}`);
      }

      // 4. 요약 타입 복원
      if (metadata.currentSummaryType) {
        window.Core.state.summaryType = metadata.currentSummaryType;
        if (window.updateToggleUI) {
          window.updateToggleUI();
        }
        console.log(`✅ 요약 타입 복원: ${metadata.currentSummaryType}`);
      }

      // 5. 기타 사용자 상태 복원
      if (metadata.lastActiveTab) {
        // 마지막 활성 탭 정보가 있다면 복원 (필요시 구현)
        console.log(`ℹ️ 마지막 활성 탭: ${metadata.lastActiveTab}`);
      }

    } catch (e) {
      console.warn('⚠️ 메타데이터 렌더링 실패:', e);
    }
  },

  /**
   * 캐시 데이터 유효성 검사
   */
  _validateCachedData(cachedData) {

    if (!cachedData) {
      console.error('❌ 렌더링할 캐시 데이터가 없습니다');
      return false;
    }

    // 캐시 데이터 구조 확인

    // 기본적으로 유효한 것으로 처리 (빈 데이터도 허용)
    return true;
  },

  /**
   * 캐시된 요약 렌더링
   */
  _renderCachedSummary(cachedData) {

    if (cachedData.summary) {
      this.updateSummary(cachedData.summary);
      this.hideSkeletonForSection('summary');
    }
  },

  /**
   * 캐시된 유사 티켓 렌더링 처리
   */
  _renderCachedSimilarTickets(cachedData) {

    if (cachedData.similarTickets && cachedData.similarTickets.length > 0) {

      // SimilarTicketsManager를 통한 렌더링
      if (window.SimilarTicketsManager) {
        window.SimilarTicketsManager.renderTickets(cachedData.similarTickets, 'cache-render');
      } else {
        // 폴백: 직접 렌더링
        this.renderSimilarTickets(cachedData.similarTickets);
      }

      this.hideSkeletonForSection('similar_tickets');
    }
  },

  /**
   * 캐시된 KB 문서 렌더링
   */
  _renderCachedKBDocuments(cachedData) {

    if (cachedData.kbDocuments && cachedData.kbDocuments.length > 0) {
      this.renderKBDocuments(cachedData.kbDocuments);
      this.hideSkeletonForSection('kb_documents');
    }
  },

  /**
   * 캐시된 헤더 및 감정 분석 렌더링
   */
  _renderCachedHeader(cachedData) {

    if (cachedData.headerInfo || cachedData.emotionData) {
      this._updateHeaderWithManager(cachedData);
      this._handleEmotionSkeletonRemoval(cachedData);
    }
  },

  /**
   * HeaderManager를 통한 헤더 업데이트
   */
  _updateHeaderWithManager(cachedData) {
    // 기존 HeaderManager 로직을 그대로 사용 (안전성만 추가)
    if (window.HeaderManager) {
      // 기존 로직 그대로 유지
      window.HeaderManager.updateHeader(
        cachedData.headerInfo || null,
        cachedData.emotionData || null,
        'ui-cache-render'
      );
    } else {
      // 기존 폴백 로직 그대로 유지  
      this.updateTicketHeader(cachedData.headerInfo || null, cachedData.emotionData || null);
    }
  },

  /**
   * 감정 분석 스켈레톤 제거 처리
   */
  _handleEmotionSkeletonRemoval(cachedData) {
    if (cachedData.emotionData && cachedData.emotionData.emotion) {
      this.hideSkeletonForSection('emotion');
    }
  },

  /**
   * 현재 렌더링된 유사티켓 ID들 조회
   */
  _getCurrentRenderedTicketIds() {
    const ticketCards = document.querySelectorAll('.ticket-card[data-ticket-id]');
    return new Set(Array.from(ticketCards).map(card => card.getAttribute('data-ticket-id')));
  },

  /**
   * 두 Set이 동일한지 확인
   */
  _areSetsEqual(setA, setB) {
    if (setA.size !== setB.size) return false;
    for (const item of setA) {
      if (!setB.has(item)) return false;
    }
    return true;
  }
};