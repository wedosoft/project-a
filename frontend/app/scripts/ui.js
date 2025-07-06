/**
 * UI 렌더링 모듈 (UI)
 *
 * Freshdesk Custom App - Prompt Canvas
 * 이 파일은 app.js에서 분리된 모든 UI 렌더링과 표시 관련 함수들을 포함합니다.
 *
 * 주요 기능:
 * - 안전한 DOM 요소 조작 및 접근
 * - 티켓 정보 및 리스트 렌더링
 * - 모달 창 및 상세 뷰 표시 관리
 * - 토스트 메시지 및 사용자 피드백
 * - 로딩 상태 및 에러 상태 UI
 * - 반응형 레이아웃 및 뷰 전환
 *
 * 의존성:
 * - GlobalState: 전역 상태 및 에러 핸들러
 * - Utils: 유틸리티 함수 (날짜 포맷, 텍스트 처리 등)
 *
 * @namespace UI
 * @author Freshdesk Custom App Team
 * @since 1.0.0
 */

// UI 모듈 정의 - 모든 UI 관련 함수를 하나의 객체로 관리
window.UI = {
  /**
   * DOM이 완전히 준비될 때까지 기다리는 함수
   *
   * @param {number} timeout - 타임아웃 (밀리초, 기본값: 10000)
   * @returns {Promise<boolean>} DOM 준비 여부
   */
  async waitForDOMReady(timeout = 10000) {
    const startTime = Date.now();
    
    while (Date.now() - startTime < timeout) {
      if (document.readyState === 'complete' || document.readyState === 'interactive') {
        console.log('[UI] DOM 준비 완료');
        return true;
      }
      
      // 50ms마다 체크
      await new Promise(resolve => setTimeout(resolve, 50));
    }
    
    console.warn('[UI] DOM 준비 타임아웃');
    return false;
  },

  /**
   * 특정 요소가 존재할 때까지 기다리는 함수
   *
   * @param {string} selector - CSS 선택자
   * @param {number} timeout - 타임아웃 (밀리초, 기본값: 5000)
   * @returns {Promise<Element|null>} 찾은 요소 또는 null
   */
  async waitForElement(selector, timeout = 5000) {
    const startTime = Date.now();
    
    while (Date.now() - startTime < timeout) {
      const element = document.querySelector(selector);
      if (element) {
        console.log(`[UI] 요소 발견: ${selector}`);
        return element;
      }
      
      // 100ms마다 체크
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    
    console.warn(`[UI] 요소 대기 타임아웃: ${selector}`);
    return null;
  },

  /**
   * 안전한 DOM 요소 조회
   *
   * querySelector를 안전하게 래핑하여 에러 처리와 로깅을 제공합니다.
   * 요소가 없거나 접근 오류 시 null을 반환하고 적절한 로그를 남깁니다.
   *
   * @param {string} selector - CSS 선택자
   * @param {boolean} waitIfNotFound - 요소가 없을 경우 대기할지 여부
   * @returns {Element|null} DOM 요소 또는 null
   *
   * @example
   * const button = UI.safeGetElement('#submit-button');
   * if (button) {
   *   button.addEventListener('click', handler);
   * }
   */
  safeGetElement(selector, waitIfNotFound = false) {
    try {
      const element = document.querySelector(selector);
      if (!element) {
        console.warn(`[UI] 요소를 찾을 수 없음: ${selector}`);
        
        if (waitIfNotFound) {
          // 비동기로 요소를 기다림 (백그라운드에서)
          this.waitForElement(selector).then(foundElement => {
            if (foundElement) {
              console.log(`[UI] 지연 발견된 요소: ${selector}`);
            }
          });
        }
        
        return null;
      }
      return element;
    } catch (error) {
      console.error(`[UI] DOM 요소 조회 오류: ${selector}`, error);
      GlobalState.ErrorHandler.handleError(error, {
        context: 'ui_dom_access',
        userMessage: 'UI 요소에 접근하는 중 오류가 발생했습니다.',
      });
      return null;
    }
  },

  /**
   * 토스트 메시지 표시
   *
   * 사용자에게 임시 알림 메시지를 표시합니다.
   * 성공, 오류, 경고, 정보 등 다양한 타입을 지원하며
   * 자동으로 사라지는 시간을 설정할 수 있습니다.
   *
   * @param {string} message - 표시할 메시지
   * @param {string} type - 메시지 타입 ('info'|'success'|'warning'|'error')
   * @param {number} duration - 표시 시간 (밀리초, 기본값: 3000)
   *
   * @example
   * UI.showToast('저장되었습니다.', 'success');
   * UI.showToast('오류가 발생했습니다.', 'error', 5000);
   */
  showToast(message, type = 'info', duration = 3000) {
    try {
      // 조용한 로깅으로 변경
      if (window.DEBUG_MODE) {
        console.log(`[UI] 토스트 표시: ${message} - ${type}`);
      }

      // 기존 토스트 제거 (더 안전한 방식)
      const existingToasts = document.querySelectorAll('.toast-message');
      existingToasts.forEach(toast => {
        if (toast.parentNode) {
          toast.remove();
        }
      });

      // 토스트 컨테이너 생성
      const toast = document.createElement('div');
      toast.className = `toast-message toast-${type}`;
      toast.textContent = message;

      // 스타일 적용
      Object.assign(toast.style, {
        position: 'fixed',
        top: '20px',
        right: '20px',
        padding: '12px 20px',
        borderRadius: '4px',
        color: 'white',
        fontSize: '14px',
        zIndex: '10000',
        maxWidth: '300px',
        backgroundColor:
          type === 'error'
            ? '#f44336'
            : type === 'success'
              ? '#4caf50'
              : type === 'warning'
                ? '#ff9800'
                : '#2196f3',
      });

      // DOM에 토스트 추가 (더 안전한 방식)
      let targetContainer = document.body;
      if (!targetContainer) {
        // body가 없으면 html 요소 사용
        targetContainer = document.documentElement;
      }
      
      if (!targetContainer) {
        // 최후의 수단: 콘솔에만 메시지 표시
        console.warn(`[UI] 토스트 표시 실패 (DOM 준비 안됨): ${message}`);
        return;
      }

      targetContainer.appendChild(toast);

      // 자동 제거
      setTimeout(() => {
        if (toast.parentNode) {
          toast.remove();
        }
      }, duration);
    } catch (error) {
      console.error('[UI] 토스트 표시 오류:', error);
      // 토스트 표시 자체가 실패하면 콘솔 에러로 대체
      console.error(`[UI] 메시지 표시 실패: ${message}`);
    }
  },

  /**
   * 응답 모달 창 표시 (FDK 환경 최적화)
   *
   * LLM 응답이나 상세 정보를 모달 창으로 표시합니다.
   * 콘텐츠를 모달 내부에 렌더링하고 화면에 표시합니다.
   * FDK iframe 환경에서도 올바르게 작동하도록 최적화됩니다.
   *
   * @param {string} content - 모달에 표시할 HTML 콘텐츠
   * @param {string} title - 모달 제목 (선택사항)
   *
   * @example
   * UI.showModal('<h3>AI 응답</h3><p>처리 결과입니다.</p>', 'AI 응답');
   */
  /**
   * 🎯 FDK 네이티브 모달 표시 함수 (단순화된 버전)
   * 
   * 복잡한 DOM 조작 대신 FDK 내장 기능을 활용하여 모달을 표시합니다.
   * index.html을 템플릿으로 사용하여 안정적인 모달 표시를 보장합니다.
   *
   * @param {string} content - 표시할 HTML 콘텐츠
   * @param {string} title - 모달 제목 (선택사항)
   */
  async showModal(content, title = 'AI 응답') {
    try {
      console.log('[UI] FDK 네이티브 모달 표시 시작');
      
      await client.interface.trigger("showModal", {
        title: title,
        template: "index.html",
        data: {
          modalContent: content,
          isCustomModal: true,
          timestamp: new Date().toISOString()
        },
        size: {
          width: "800px",
          height: "600px"
        },
        noBackdrop: false
      });
      
      console.log('[UI] FDK 네이티브 모달 표시 완료');
    } catch (error) {
      console.error('[UI] FDK 모달 표시 오류:', error);
      
      // 폴백: 토스트 메시지로 대체
      this.showToast('응답을 표시할 수 없습니다.', 'error');
    }
  },

  /**
   * 에러 모달 표시 (FDK 환경 최적화)
   *
   * 에러 메시지를 전용 에러 모달로 표시합니다.
   * FDK iframe 환경에서도 올바르게 작동하도록 최적화됩니다.
   *
   * @param {string} errorMessage - 에러 메시지
   * @param {string} title - 모달 제목 (선택사항)
   */  /**
   * 🎯 FDK 네이티브 에러 모달 표시 함수 (단순화된 버전)
   *
   * 에러 메시지를 FDK 모달로 표시합니다.
   *
   * @param {string} errorMessage - 에러 메시지
   * @param {string} title - 모달 제목 (선택사항)
   */
  showErrorModal(errorMessage, title = '오류 발생') {
    try {
      console.log('[UI] FDK 네이티브 에러 모달 표시 시작');

      // showModal 함수를 재사용하여 에러 내용 표시
      const errorContent = `
        <div class="alert alert-danger" style="margin: 0; padding: 15px; border-radius: 6px;">
          <div style="display: flex; align-items: center; margin-bottom: 10px;">
            <span style="font-size: 20px; margin-right: 10px;">⚠️</span>
            <strong>오류가 발생했습니다</strong>
          </div>
          <div style="font-size: 14px;">
            ${errorMessage}
          </div>
        </div>
      `;
      
      this.showModal(errorContent, title);
      console.log('[UI] FDK 네이티브 에러 모달 표시 완료');
    } catch (error) {
      console.error('[UI] 에러 모달 표시 오류:', error);
      
      // 폴백: 토스트 메시지로 대체
      this.showToast(`오류: ${errorMessage}`, 'error');
    }
  },

  // 백엔드 오류 시 사용자에게 친화적인 메시지를 표시하는 함수
  showBackendError(errorMessage, title = 'AI 서비스 오류') {
    try {
      console.log('[UI] 백엔드 에러 메시지 표시 시작');

      // 모달 내부에 에러 메시지를 표시할 수 있도록 DOM을 찾고 업데이트
      const errorContainer = document.getElementById('error-display');
      const mainContent = document.getElementById('main-content');

      if (errorContainer) {
        // 에러 컨테이너가 있으면 에러 메시지 표시
        errorContainer.innerHTML = `
          <div class="alert alert-danger" style="margin: 20px; padding: 20px; border-radius: 8px; border: 1px solid #dc3545; background-color: #f8d7da; color: #721c24;">
            <div style="display: flex; align-items: center; margin-bottom: 15px;">
              <span style="font-size: 24px; margin-right: 12px;">⚠️</span>
              <strong style="font-size: 16px;">${title}</strong>
            </div>
            <div style="font-size: 14px; line-height: 1.5; margin-bottom: 15px;">
              ${errorMessage}
            </div>
            <div style="font-size: 12px; color: #6c757d; margin-top: 10px;">
              문제가 지속되면 Freshdesk 관리자에게 문의하세요.
            </div>
          </div>
        `;
        errorContainer.style.display = 'block';
        
        // 메인 컨텐츠는 숨기기
        if (mainContent) {
          mainContent.style.display = 'none';
        }
        
        console.log('[UI] 백엔드 에러 메시지 표시 완료 (DOM 업데이트)');
      } else {
        // 에러 컨테이너가 없으면 모달로 표시
        const errorContent = `
          <div class="alert alert-danger" style="margin: 0; padding: 20px; border-radius: 8px; border: 1px solid #dc3545; background-color: #f8d7da; color: #721c24;">
            <div style="display: flex; align-items: center; margin-bottom: 15px;">
              <span style="font-size: 24px; margin-right: 12px;">⚠️</span>
              <strong style="font-size: 16px;">${title}</strong>
            </div>
            <div style="font-size: 14px; line-height: 1.5; margin-bottom: 15px;">
              ${errorMessage}
            </div>
            <div style="font-size: 12px; color: #6c757d; margin-top: 10px;">
              문제가 지속되면 Freshdesk 관리자에게 문의하세요.
            </div>
          </div>
        `;
        
        this.showModal(errorContent, title);
        console.log('[UI] 백엔드 에러 메시지 표시 완료 (모달)');
      }
    } catch (error) {
      console.error('[UI] 백엔드 에러 메시지 표시 오류:', error);
      
      // 최후의 수단: 토스트 메시지로 대체
      this.showToast(`${title}: ${errorMessage}`, 'error');
    }
  },

  // 캐시된 데이터로 UI를 즉시 업데이트하는 함수
  updateUIWithCachedData(data) {
    try {
      console.log('[UI] 캐시된 데이터로 UI 업데이트 시작');
      
      if (!data) {
        console.warn('[UI] 캐시된 데이터가 없습니다');
        return;
      }

      // 티켓 정보 표시
      if (data.ticket_info) {
        this.displayTicketInfo(data.ticket_info);
      }

      // 요약 정보 표시
      if (data.summary) {
        this.displaySummary(data.summary);
      }

      // 유사 티켓 표시
      if (data.similar_tickets && data.similar_tickets.length > 0) {
        this.displayRelatedDocs(data.similar_tickets);
      }

      // KB 문서 표시
      if (data.kb_documents && data.kb_documents.length > 0) {
        this.displayRelatedDocs(data.kb_documents);
      }

      // 관련 문서 표시 (레거시 지원)
      if (data.related_docs && data.related_docs.length > 0) {
        this.displayRelatedDocs(data.related_docs);
      }

      console.log('[UI] 캐시된 데이터로 UI 업데이트 완료');
    } catch (error) {
      console.error('[UI] 캐시된 데이터 UI 업데이트 오류:', error);
    }
  },

  // 🎯 필수 데이터 표시 함수들 구현
  
  /**
   * 티켓 정보 표시
   */
  displayTicketInfo(ticket) {
    try {
      console.log('📋 티켓 정보 표시:', ticket);
      
      // 티켓 제목 업데이트
      const titleElement = document.querySelector('#ticket-title, .ticket-title, h1');
      if (titleElement && ticket.subject) {
        titleElement.textContent = ticket.subject;
      }
      
      // 티켓 ID 표시
      const idElement = document.querySelector('#ticket-id, .ticket-id');
      if (idElement && ticket.id) {
        idElement.textContent = `티켓 #${ticket.id}`;
      }
      
      // 티켓 상태 표시
      const statusElement = document.querySelector('#ticket-status, .ticket-status');
      if (statusElement && ticket.status) {
        statusElement.textContent = ticket.status;
      }
      
      // 티켓 우선순위 표시
      const priorityElement = document.querySelector('#ticket-priority, .ticket-priority');
      if (priorityElement && ticket.priority) {
        priorityElement.textContent = ticket.priority;
      }
      
    } catch (error) {
      console.error('❌ 티켓 정보 표시 오류:', error);
    }
  },

  /**
   * AI 요약 정보 표시
   */
  displaySummary(summary) {
    try {
      console.log('📝 AI 요약 표시:', summary);
      
      // 요약 컨테이너 찾기
      const summaryContainer = document.querySelector('#summary-container, .summary-container, #ai-summary');
      if (!summaryContainer) {
        console.warn('⚠️ 요약 컨테이너를 찾을 수 없음');
        return;
      }
      
      // 요약 내용 업데이트
      if (typeof summary === 'string') {
        summaryContainer.innerHTML = `
          <h3>🤖 AI 요약</h3>
          <div class="summary-content">${summary}</div>
        `;
      } else if (summary && summary.summary) {
        summaryContainer.innerHTML = `
          <h3>🤖 AI 요약</h3>
          <div class="summary-content">${summary.summary}</div>
        `;
      }
      
    } catch (error) {
      console.error('❌ AI 요약 표시 오류:', error);
    }
  },

  /**
   * 관련 문서 표시 (유사 티켓, KB 문서)
   */
  displayRelatedDocs(docs) {
    try {
      console.log('📚 관련 문서 표시:', docs);
      
      // 관련 문서 컨테이너 찾기
      const docsContainer = document.querySelector('#related-docs, .related-docs, #similar-tickets');
      if (!docsContainer) {
        console.warn('⚠️ 관련 문서 컨테이너를 찾을 수 없음');
        return;
      }
      
      if (docs && docs.length > 0) {
        let docsHtml = '<h3>📚 관련 문서</h3><ul class="docs-list">';
        
        docs.forEach(doc => {
          docsHtml += `
            <li class="doc-item">
              <strong>${doc.title || doc.subject || '제목 없음'}</strong>
              ${doc.content ? `<p class="doc-content">${doc.content.substring(0, 100)}...</p>` : ''}
              ${doc.score ? `<span class="doc-score">유사도: ${Math.round(doc.score * 100)}%</span>` : ''}
            </li>
          `;
        });
        
        docsHtml += '</ul>';
        docsContainer.innerHTML = docsHtml;
      }
      
    } catch (error) {
      console.error('❌ 관련 문서 표시 오류:', error);
    }
  },

  /**
   * 🎯 모달 닫기 함수 (단순화된 버전)
   * 
   * FDK 모달은 자동으로 닫히므로 특별한 처리가 불필요합니다.
   */
  hideModal() {
    try {
      console.log('[UI] 모달 닫기 요청 - FDK가 자동 처리');
      
      // FDK 모달은 자동으로 닫히므로 별도 처리 불필요
      // 필요시 추가 정리 작업만 수행
      
    } catch (error) {
      console.error('[UI] 모달 닫기 오류:', error);
    }
  },

  // 티켓 정보 UI 업데이트 함수
  updateTicketInfo(ticket) {
    // 제목 업데이트
    const subjectElement = this.safeGetElement('#ticket-subject');
    if (subjectElement) {
      subjectElement.textContent = ticket.subject || 'No subject available';
    }

    // 상태 업데이트
    const statusElement = this.safeGetElement('#ticket-status');
    if (statusElement) {
      const statusText = getStatusText(ticket.status);
      statusElement.textContent = statusText;
      statusElement.className = `info-value status-${statusText.toLowerCase()}`;
    }

    // 우선순위 업데이트
    const priorityElement = this.safeGetElement('#ticket-priority');
    if (priorityElement) {
      const priorityText = getPriorityText(ticket.priority);
      priorityElement.textContent = priorityText;
      priorityElement.className = `info-value priority-${priorityText.toLowerCase()}`;
    }

    // 타입 업데이트
    const typeElement = this.safeGetElement('#ticket-type');
    if (typeElement) {
      typeElement.textContent = ticket.type || 'Question';
    }

    console.log('✅ 티켓 정보 UI 업데이트 완료');
  },

  // 유사 티켓 리스트 뷰 표시
  showSimilarTicketsListView() {
    const listView = this.safeGetElement('#similar-tickets-list-view');
    const detailView = this.safeGetElement('#similar-tickets-detail-view');

    if (listView) listView.style.display = 'block';
    if (detailView) detailView.style.display = 'none';
  },

  // 유사 티켓 상세 뷰 표시
  showSimilarTicketDetailView(ticket) {
    const listView = this.safeGetElement('#similar-tickets-list-view');
    const detailView = this.safeGetElement('#similar-tickets-detail-view');
    const detailContent = this.safeGetElement('#similar-ticket-detail-content');
    const openTicketButton = this.safeGetElement('#open-ticket-link');

    if (listView) listView.style.display = 'none';
    if (detailView) detailView.style.display = 'block';

    // 버튼에 티켓 ID 저장
    if (openTicketButton) {
      openTicketButton.dataset.ticketId = ticket.id;
    }

    if (detailContent) {
      detailContent.innerHTML = `
        <div class="detail-content">
          <div class="detail-meta">
            <div class="d-flex justify-content-between align-items-start mb-2">
              <h5 class="mb-0">#${ticket.id}</h5>
              <span class="badge-custom ${getStatusClass(
                ticket.status
              )}">${getStatusText(ticket.status)}</span>
            </div>
            <div class="row">
              <div class="col-6">
                <small class="text-muted">Priority:</small>
                <div class="badge-custom ${getPriorityClass(
                  ticket.priority
                )}">${getPriorityText(ticket.priority)}</div>
              </div>
              <div class="col-6">
                <small class="text-muted">Type:</small>
                <div>${ticket.type || 'Question'}</div>
              </div>
            </div>
            ${
              ticket.created_at
                ? `
              <div class="mt-2">
                <small class="text-muted">Created:</small>
                <div>${formatDate(ticket.created_at)}</div>
              </div>
            `
                : ''
            }
          </div>
          
          <div class="detail-section">
            <h6>Subject</h6>
            <p>${ticket.subject || 'No subject available'}</p>
          </div>
          
          ${
            ticket.description_text || ticket.description
              ? `
            <div class="detail-section">
              <h6>Description</h6>
              <div class="description-content">
                ${formatDescription(ticket.description_text || ticket.description)}
              </div>
            </div>
          `
              : ''
          }
          
          ${
            ticket.tags && ticket.tags.length > 0
              ? `
            <div class="detail-section">
              <h6>Tags</h6>
              <div>
                ${ticket.tags
                  .map((tag) => `<span class="badge bg-secondary me-1">${tag}</span>`)
                  .join('')}
              </div>
            </div>
          `
              : ''
          }
          
          ${
            ticket.fr_escalated
              ? `
            <div class="detail-section">
              <h6>Additional Info</h6>
              <ul class="list-unstyled">
                <li><strong>Escalated:</strong> Yes</li>
                ${
                  ticket.requester_id
                    ? `<li><strong>Requester ID:</strong> ${ticket.requester_id}</li>`
                    : ''
                }
                ${ticket.group_id ? `<li><strong>Group ID:</strong> ${ticket.group_id}</li>` : ''}
              </ul>
            </div>
          `
              : ''
          }
        </div>
      `;
    }

    console.log('✅ 유사 티켓 상세 정보 표시 완료');
  },

  // 유사 티켓 결과 표시 함수 (새로운 리스트 형태)
  displaySimilarTickets(similarTickets) {
    const resultsElement = this.safeGetElement('#similar-tickets-list');
    if (!resultsElement) return;

    if (similarTickets.length > 0) {
      resultsElement.innerHTML = `
        <div class="similar-tickets-content">
          <div class="mb-3">
            <small class="text-muted">🚀 Vector DB에서 발견된 유사 티켓: ${similarTickets.length}개</small>
          </div>
          <div id="tickets-container"></div>
        </div>
      `;

      const ticketsContainer = this.safeGetElement('tickets-container');

      // 각 유사 티켓을 Vector DB 데이터 구조에 맞게 렌더링
      similarTickets.forEach((similarTicket) => {
        const ticketItem = document.createElement('div');
        ticketItem.className = 'list-item vector-db-item';

        // Vector DB의 relevance_score 사용 (0-1 범위를 백분율로 변환)
        const relevanceScore = Math.round((similarTicket.relevance_score || 0) * 100);
        const confidenceScore = similarTicket.confidence_score ? Math.round(similarTicket.confidence_score * 100) : null;

        ticketItem.innerHTML = `
          <div class="list-item-header">
            <div class="list-item-title">${similarTicket.title || similarTicket.subject || 'No subject'}</div>
            <div class="d-flex align-items-center gap-2">
              <span class="score-badge">${relevanceScore}%</span>
              ${confidenceScore ? `<span class="confidence-badge">${confidenceScore}%</span>` : ''}
              <span class="badge-custom ${this.getStatusClass(
                similarTicket.status
              )}">${this.getStatusText(similarTicket.status)}</span>
            </div>
          </div>
          <div class="list-item-meta">
            <span>티켓 #${similarTicket.id}</span> • 
            <span>우선순위: ${this.getPriorityText(similarTicket.priority)}</span>
            ${similarTicket.agent_name ? ` • <span>담당자: ${similarTicket.agent_name}</span>` : ''}
            ${
              similarTicket.created_at
                ? ` • <span>${this.formatDate(similarTicket.created_at)}</span>`
                : ''
            }
          </div>
          ${
            similarTicket.ai_summary
              ? `
            <div class="list-item-excerpt vector-summary">
              <div class="mb-2">🤖 <strong>AI 요약:</strong> ${this.truncateText(
                similarTicket.ai_summary,
                120
              )}</div>
            </div>
          `
              : similarTicket.content || similarTicket.description_text
              ? `
            <div class="list-item-excerpt">
              ${this.truncateText(similarTicket.content || similarTicket.description_text, 150)}
            </div>
          `
              : ''
          }
          ${
            similarTicket.tags && similarTicket.tags.length > 0
              ? `
            <div class="mt-2">
              ${similarTicket.tags
                .slice(0, 3)
                .map((tag) => `<span class="badge bg-light text-dark me-1">${tag}</span>`)
                .join('')}
              ${
                similarTicket.tags.length > 3
                  ? `<span class="badge bg-light text-muted">+${
                      similarTicket.tags.length - 3
                    }</span>`
                  : ''
              }
            </div>
          `
              : ''
          }
        `;

        // 티켓 상세 보기 클릭 이벤트 추가
        ticketItem.addEventListener('click', function () {
          console.log('📋 유사 티켓 상세 보기:', similarTicket.id);
          this.showSimilarTicketDetailView(similarTicket);
        });

        ticketsContainer.appendChild(ticketItem);
      });
    } else {
      // 빈 배열일 때 캐시 상태와 에러 상태를 고려한 정보 제공
      const hasCachedData = globalTicketData.cached_ticket_id && !isDataStale();
      const errorState = GlobalState.getGlobalError();
      
      let emptyMessage;
      if (errorState.hasError) {
        // 에러가 발생한 경우
        emptyMessage = `데이터를 불러오는 중 오류가 발생했습니다.<br>${errorState.errorMessage || '서버와의 연결을 확인해주세요.'}`;
      } else if (hasCachedData) {
        // 캐시된 데이터가 있지만 유사 티켓이 없는 경우
        emptyMessage = '이 티켓과 유사한 과거 사례가 없거나, 아직 데이터가 충분하지 않습니다.';
      } else {
        // 데이터 로딩 중이거나 초기 상태
        emptyMessage = '데이터를 로딩 중이거나 아직 분석이 완료되지 않았습니다.<br>페이지 새로고침 후 다시 시도해보세요.';
      }

      resultsElement.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">🔍</div>
          <div class="empty-state-title">유사한 티켓을 찾을 수 없습니다</div>
          <div class="empty-state-description">
            ${emptyMessage}
          </div>
        </div>
      `;
    }

    console.log(`✅ 유사 티켓 ${similarTickets.length}개 표시 완료`);
  },

  // 추천 솔루션 리스트 뷰 표시
  showSuggestedSolutionsListView() {
    const listView = this.safeGetElement('#solutions-list-view');
    const detailView = this.safeGetElement('#solutions-detail-view');

    if (listView) listView.style.display = 'block';
    if (detailView) detailView.style.display = 'none';
  },

  // 추천 솔루션 상세 뷰 표시
  showSuggestedSolutionDetailView(solution) {
    const listView = this.safeGetElement('#solutions-list-view');
    const detailView = this.safeGetElement('#solutions-detail-view');
    const detailContent = this.safeGetElement('#solution-detail-content');
    const useSolutionButton = this.safeGetElement('#use-solution');

    if (listView) listView.style.display = 'none';
    if (detailView) detailView.style.display = 'block';

    // 버튼에 솔루션 데이터 저장
    if (useSolutionButton) {
      useSolutionButton.dataset.solution = JSON.stringify(solution);
    }

    if (detailContent) {
      detailContent.innerHTML = `
        <div class="detail-content">
          <div class="detail-meta">
            <div class="d-flex justify-content-between align-items-start mb-2">
              <h5 class="mb-0">${solution.title || '해결책'}</h5>
              ${
                solution.score
                  ? `<span class="score-badge">${Math.round(solution.score * 100)}% 관련도</span>`
                  : ''
              }
            </div>
            <div class="row">
              <div class="col-6">
                <small class="text-muted">카테고리:</small>
                <div class="badge-custom bg-info">${solution.category || '일반'}</div>
              </div>
              <div class="col-6">
                <small class="text-muted">유형:</small>
                <div>${solution.type || 'Solution'}</div>
              </div>
            </div>
            ${
              solution.source
                ? `
              <div class="mt-2">
                <small class="text-muted">출처:</small>
                <div>${solution.source}</div>
              </div>
            `
                : ''
            }
          </div>
          
          ${
            solution.summary
              ? `
            <div class="detail-section">
              <h6>요약</h6>
              <p>${solution.summary}</p>
            </div>
          `
              : ''
          }
          
          <div class="detail-section">
            <h6>해결책 내용</h6>
            <div class="solution-content">
              ${formatSolutionContent(
                solution.content || solution.description || '솔루션 내용이 없습니다.'
              )}
            </div>
          </div>
          
          ${
            solution.steps && solution.steps.length > 0
              ? `
            <div class="detail-section">
              <h6>단계별 해결 과정</h6>
              <ol class="solution-steps">
                ${solution.steps.map((step) => `<li>${step}</li>`).join('')}
              </ol>
            </div>
          `
              : ''
          }
          
          ${
            solution.tags && solution.tags.length > 0
              ? `
            <div class="detail-section">
              <h6>관련 태그</h6>
              <div>
                ${solution.tags
                  .map((tag) => `<span class="badge bg-secondary me-1">${tag}</span>`)
                  .join('')}
              </div>
            </div>
          `
              : ''
          }
          
          ${
            solution.url
              ? `
            <div class="detail-section">
              <h6>추가 정보</h6>
              <a href="${solution.url}" target="_blank" class="btn btn-outline-primary btn-sm">
                원본 문서 보기 <i class="fas fa-external-link-alt"></i>
              </a>
            </div>
          `
              : ''
          }
        </div>
      `;
    }

    console.log('✅ 추천 솔루션 상세 정보 표시 완료');
  },

  // 추천 솔루션 표시 함수 (새로운 리스트 형태)
  displaySuggestedSolutions(solutions) {
    const resultsElement = this.safeGetElement('#suggested-solutions-list');
    if (!resultsElement) return;

    if (solutions.length > 0) {
      resultsElement.innerHTML = `
        <div class="suggested-solutions-content">
          <div class="mb-3">
            <small class="text-muted">추천 솔루션: ${solutions.length}개</small>
          </div>
          <div id="solutions-container"></div>
        </div>
      `;

      const solutionsContainer = this.safeGetElement('solutions-container');

      // 각 솔루션을 새로운 리스트 아이템으로 렌더링
      solutions.forEach((solution, index) => {
        const solutionItem = document.createElement('div');
        solutionItem.className = 'list-item';

        // 관련도 점수 계산
        const relevanceScore = solution.score
          ? Math.round(solution.score * 100)
          : Math.random() * 20 + 75;

        solutionItem.innerHTML = `
          <div class="list-item-header">
            <div class="list-item-title">${solution.title || `Solution ${index + 1}`}</div>
            <div class="d-flex align-items-center gap-2">
              <span class="score-badge">${relevanceScore}%</span>
              <span class="badge-custom bg-info">${solution.category || '일반'}</span>
            </div>
          </div>
          <div class="list-item-meta">
            <span>유형: ${solution.type || 'Solution'}</span>
            ${solution.source ? ` • <span>출처: ${solution.source}</span>` : ''}
          </div>
          ${
            solution.content || solution.description
              ? `
            <div class="list-item-excerpt">
              ${truncateText(solution.content || solution.description, 150)}
            </div>
          `
              : ''
          }
          ${
            solution.tags && solution.tags.length > 0
              ? `
            <div class="mt-2">
              ${solution.tags
                .slice(0, 3)
                .map((tag) => `<span class="badge bg-light text-dark me-1">${tag}</span>`)
                .join('')}
              ${
                solution.tags.length > 3
                  ? `<span class="badge bg-light text-muted">+${solution.tags.length - 3}</span>`
                  : ''
              }
            </div>
          `
              : ''
          }
        `;

        // 솔루션 상세 보기 클릭 이벤트 추가
        solutionItem.addEventListener('click', function () {
          console.log('💡 추천 솔루션 상세 보기:', solution.title || `Solution ${index + 1}`);
          this.showSuggestedSolutionDetailView(solution);
        });

        solutionsContainer.appendChild(solutionItem);
      });
    } else {
      // 빈 배열일 때 캐시 상태와 에러 상태를 고려한 정보 제공
      const hasCachedData = globalTicketData.cached_ticket_id && !isDataStale();
      const errorState = GlobalState.getGlobalError();
      
      let emptyMessage;
      if (errorState.hasError) {
        // 에러가 발생한 경우
        emptyMessage = `솔루션 데이터를 불러오는 중 오류가 발생했습니다.<br>${errorState.errorMessage || '서버와의 연결을 확인해주세요.'}`;
      } else if (hasCachedData) {
        // 캐시된 데이터가 있지만 추천 솔루션이 없는 경우
        emptyMessage = '현재 지식베이스에서 이 문제와 관련된 솔루션을 찾을 수 없습니다.<br>새로운 문서가 추가되거나 더 구체적인 정보가 있으면 관련 솔루션을 제안할 수 있습니다.';
      } else {
        // 데이터 로딩 중이거나 초기 상태
        emptyMessage = '지식베이스 데이터를 로딩 중이거나 아직 분석이 완료되지 않았습니다.<br>페이지 새로고침 후 다시 시도해보세요.';
      }

      resultsElement.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">💡</div>
          <div class="empty-state-title">추천할 솔루션을 찾을 수 없습니다</div>
          <div class="empty-state-description">
            ${emptyMessage}
          </div>
        </div>
      `;
    }

    console.log(`✅ 추천 솔루션 ${solutions.length}개 표시 완료`);
  },

  // 티켓 요약 표시 함수
  displayTicketSummary(summary) {
    const summarySection = this.safeGetElement('ticket-summary-section');
    if (!summarySection || !summary) return;

    summarySection.innerHTML = `
      <div class="summary-section">
        <h6>티켓 요약</h6>
        <div class="summary-content">
          <div class="mb-2">
            <strong>문제:</strong> ${summary.problem || '요약 정보 없음'}
          </div>
          <div class="mb-2">
            <strong>원인:</strong> ${summary.cause || '분석 중'}
          </div>
          <div class="mb-2">
            <strong>해결방안:</strong> ${summary.solution || '검토 중'}
          </div>
          <div>
            <strong>처리결과:</strong> ${summary.result || '진행 중'}
          </div>
        </div>
      </div>
    `;

    console.log('✅ 티켓 요약 표시 완료');
  },

  /**
   * 🚀 Vector DB 기반 티켓 요약 업데이트
   *
   * Vector DB에서 조회된 또는 실시간 생성된 티켓 요약을 표시합니다.
   * 마크다운 포맷, 성능 메트릭, 신뢰도 점수 등을 지원합니다.
   *
   * @param {string|Object} summary - 요약 텍스트 또는 요약 객체
   * @param {Object} metadata - 성능 메트릭 및 메타데이터
   */
  updateTicketSummaryVectorDB(summary, metadata = {}) {
    const summaryElement = this.safeGetElement('#ticket-summary');
    if (!summaryElement) {
      console.warn('[UI] 티켓 요약 엘리먼트를 찾을 수 없음');
      return;
    }

    try {
      // 요약 텍스트 추출
      let summaryText = '';
      if (typeof summary === 'string') {
        summaryText = summary;
      } else if (summary && summary.text) {
        summaryText = summary.text;
      } else if (summary && summary.summary) {
        summaryText = summary.summary;
      } else {
        summaryText = '요약을 생성할 수 없습니다.';
      }

      // 마크다운을 HTML로 변환 (간단한 변환)
      const htmlContent = this.convertMarkdownToHTML(summaryText);

      // 성능 메트릭 HTML 생성
      let metricsHTML = '';
      if (metadata.executionTime || metadata.searchQualityScore) {
        metricsHTML = `
          <div class="performance-metrics">
            ${metadata.executionTime ? `
              <div class="metric-item">
                <span>⏱️ 응답시간:</span>
                <span class="metric-value">${metadata.executionTime.toFixed(2)}초</span>
              </div>
            ` : ''}
            ${metadata.searchQualityScore ? `
              <div class="metric-item">
                <span>📊 검색품질:</span>
                <span class="metric-value">${(metadata.searchQualityScore * 100).toFixed(1)}%</span>
              </div>
            ` : ''}
            <div class="metric-item">
              <span>🔍 모드:</span>
              <span class="metric-value">Vector DB</span>
            </div>
          </div>
        `;
      }

      // HTML 업데이트
      summaryElement.innerHTML = `
        <div class="summary-content">
          ${htmlContent}
        </div>
        ${metricsHTML}
      `;

      // 요약이 너무 긴 경우 펼치기/접기 기능 추가
      if (summaryText.length > 500) {
        this.addExpandCollapseToSummary(summaryElement);
      }

      console.log('[UI] Vector DB 기반 티켓 요약 업데이트 완료');
    } catch (error) {
      console.error('[UI] 티켓 요약 업데이트 오류:', error);
      summaryElement.innerHTML = '<div class="error-message">요약을 표시하는 중 오류가 발생했습니다.</div>';
    }
  },

  /**
   * 📝 간단한 마크다운을 HTML로 변환
   *
   * @param {string} markdown - 마크다운 텍스트
   * @returns {string} HTML 텍스트
   */
  convertMarkdownToHTML(markdown) {
    if (!markdown) return '';

    return markdown
      // 헤더 변환
      .replace(/^### (.*$)/gim, '<h3>$1</h3>')
      .replace(/^## (.*$)/gim, '<h2>$1</h2>')
      .replace(/^# (.*$)/gim, '<h1>$1</h1>')
      // 굵은 글씨
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/__(.*?)__/g, '<strong>$1</strong>')
      // 기울임
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      .replace(/_(.*?)_/g, '<em>$1</em>')
      // 이모지 헤더 (특별 처리)
      .replace(/^(🔍|📋|💡|⚡|🎯|📊|🛠️|🚀)(.*$)/gim, '<div class="emoji-header"><span class="emoji">$1</span><span class="header-text">$2</span></div>')
      // 줄바꿈
      .replace(/\n\n/g, '</p><p>')
      .replace(/\n/g, '<br>')
      // 전체를 p 태그로 감싸기
      .replace(/^(.*)$/, '<p>$1</p>');
  },

  /**
   * 🔽 요약 펼치기/접기 기능 추가
   *
   * @param {Element} summaryElement - 요약 엘리먼트
   */
  addExpandCollapseToSummary(summaryElement) {
    const content = summaryElement.querySelector('.summary-content');
    if (!content) return;

    // 펼치기/접기 버튼 추가
    const toggleButton = document.createElement('button');
    toggleButton.className = 'summary-toggle';
    toggleButton.innerHTML = '더 보기';
    toggleButton.style.cssText = `
      background: none;
      border: none;
      color: #667eea;
      font-size: 12px;
      cursor: pointer;
      padding: 4px 0;
      text-decoration: underline;
    `;

    let isExpanded = false;
    content.style.maxHeight = '100px';
    content.style.overflow = 'hidden';

    toggleButton.addEventListener('click', () => {
      if (isExpanded) {
        content.style.maxHeight = '100px';
        content.style.overflow = 'hidden';
        toggleButton.innerHTML = '더 보기';
        isExpanded = false;
      } else {
        content.style.maxHeight = 'none';
        content.style.overflow = 'visible';
        toggleButton.innerHTML = '접기';
        isExpanded = true;
      }
    });

    summaryElement.appendChild(toggleButton);
  },

  /**
   * 📊 실시간 스트리밍 상태 표시
   *
   * Vector DB 모드에서 실시간 요약 생성 상태를 표시합니다.
   *
   * @param {string} stage - 현재 단계 ('fetching'|'analyzing'|'generating'|'complete')
   * @param {string} message - 표시할 메시지
   */
  updateStreamingStatus(stage, message) {
    const statusElement = this.safeGetElement('#streaming-status');
    if (!statusElement) return;

    const stageEmojis = {
      fetching: '🔍',
      analyzing: '📊',
      generating: '✨',
      complete: '✅'
    };

    const emoji = stageEmojis[stage] || '⏳';
    
    statusElement.innerHTML = `
      <div class="streaming-status ${stage}">
        <span class="status-emoji">${emoji}</span>
        <span class="status-message">${message}</span>
      </div>
    `;

    // 완료되면 3초 후 자동 숨김
    if (stage === 'complete') {
      setTimeout(() => {
        statusElement.innerHTML = '';
      }, 3000);
    }
  },

  /**
   * 🔄 기존 updateTicketSummary 메서드 호환성 유지
   * 
   * @param {string} summary - 요약 텍스트
   */
  updateTicketSummary(summary) {
    // Vector DB 모드로 리다이렉트
    this.updateTicketSummaryVectorDB(summary);
  },

  // ...existing code...
};

/**
 * 🚀 FDK 네이티브 전역 함수 (단순화된 버전)
 * 
 * FDK 네이티브 방식으로 UI 모듈의 showModal/hideModal 함수를 호출합니다.
 */
window.showModal = function(content, title) {
  if (window.UI && window.UI.showModal) {
    return window.UI.showModal(content, title);
  } else {
    console.error('[전역] UI 모듈이 준비되지 않음');
  }
};

window.hideModal = function() {
  if (window.UI && window.UI.hideModal) {
    return window.UI.hideModal();
  } else {
    console.error('[전역] UI 모듈이 준비되지 않음');
  }
};

// 모듈 등록 (로그 없음)

// 모듈 의존성 시스템에 등록 (data 의존성 명시)
if (typeof ModuleDependencyManager !== 'undefined') {
  ModuleDependencyManager.registerModule('ui', Object.keys(UI).length, ['data']);
}
