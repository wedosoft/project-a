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
      console.log(`[UI] 토스트 표시: ${type} - ${message}`);

      // 기존 토스트 제거
      const existingToast = this.safeGetElement('.toast-message');
      if (existingToast) {
        existingToast.remove();
      }

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

      document.body.appendChild(toast);

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
   * FDK 환경용 콘텐츠 표시 함수 (개선된 DOM 대기 로직)
   *
   * FDK iframe 환경에서는 별도 모달 대신 앱 컨테이너 내에서 직접 콘텐츠를 표시합니다.
   * 기존 탭 콘텐츠를 임시로 숨기고 응답 콘텐츠를 표시한 후, 닫기 버튼으로 원래 상태로 복원합니다.
   *
   * @param {string} content - 표시할 HTML 콘텐츠
   * @param {string} title - 제목 (선택사항)
   */
  async showModal(content, title = 'AI 응답') {
    try {
      console.log('[UI] FDK 환경용 콘텐츠 표시 시작');

      // DOM이 준비될 때까지 기다림
      await this.waitForDOMReady();

      // 기존 탭 콘텐츠 숨기기 (요소가 있는 경우에만)
      const tabContent = await this.waitForElement('.tab-content', 2000);
      if (tabContent) {
        tabContent.style.display = 'none';
        console.log('[UI] 탭 콘텐츠 숨김 처리 완료');
      } else {
        console.warn('[UI] 탭 콘텐츠 요소를 찾을 수 없어 fallback으로 진행');
      }

      // 응답 표시 컨테이너 생성 또는 가져오기
      let responseContainer = this.safeGetElement('#fdk-response-container');
      if (!responseContainer) {
        console.log('[UI] 응답 컨테이너가 없어서 동적 생성');
        responseContainer = document.createElement('div');
        responseContainer.id = 'fdk-response-container';
        responseContainer.style.cssText = `
          position: relative;
          background: white;
          border: 1px solid #dee2e6;
          border-radius: 8px;
          padding: 20px;
          margin: 10px 0;
          box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
          max-height: 400px;
          overflow-y: auto;
          z-index: 1000;
        `;
        
        // 탭 컨테이너 뒤에 삽입 시도, 없으면 body에 추가
        const tabContainer = this.safeGetElement('.tab-container');
        if (tabContainer) {
          tabContainer.parentNode.insertBefore(responseContainer, tabContainer.nextSibling);
          console.log('[UI] 탭 컨테이너 뒤에 응답 컨테이너 삽입');
        } else {
          // 컨테이너를 찾을 수 없으면 body 끝에 추가
          document.body.appendChild(responseContainer);
          console.log('[UI] body 끝에 응답 컨테이너 추가 (fallback)');
        }
      } else {
        console.log('[UI] 기존 응답 컨테이너 재사용');
      }

      // 헤더와 닫기 버튼 생성
      const header = document.createElement('div');
      header.style.cssText = `
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 15px;
        padding-bottom: 10px;
        border-bottom: 1px solid #dee2e6;
      `;

      const titleElement = document.createElement('h5');
      titleElement.textContent = title;
      titleElement.style.cssText = `
        margin: 0;
        color: #2c3e50;
        font-size: 16px;
        font-weight: 600;
      `;

      const closeButton = document.createElement('button');
      closeButton.innerHTML = '&times;';
      closeButton.style.cssText = `
        background: none;
        border: none;
        font-size: 24px;
        color: #6c757d;
        cursor: pointer;
        padding: 0;
        width: 30px;
        height: 30px;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 4px;
        transition: background-color 0.2s;
      `;
      closeButton.onmouseover = () => { closeButton.style.backgroundColor = '#f8f9fa'; };
      closeButton.onmouseout = () => { closeButton.style.backgroundColor = 'transparent'; };
      closeButton.onclick = () => this.hideModal();

      header.appendChild(titleElement);
      header.appendChild(closeButton);

      // 콘텐츠 영역 생성
      const contentArea = document.createElement('div');
      contentArea.innerHTML = content;
      contentArea.style.cssText = `
        line-height: 1.6;
        color: #333;
      `;

      // 컨테이너 내용 업데이트
      responseContainer.innerHTML = '';
      responseContainer.appendChild(header);
      responseContainer.appendChild(contentArea);

      // 표시
      responseContainer.style.display = 'block';

      // 스크롤하여 컨테이너가 보이도록 함
      responseContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });

      console.log('[UI] FDK 환경용 콘텐츠 표시 완료');
    } catch (error) {
      console.error('[UI] 콘텐츠 표시 오류:', error);
      this.showToast('콘텐츠를 표시하는 중 오류가 발생했습니다.', 'error');
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
   */
  /**
   * FDK 환경용 에러 표시 함수
   *
   * 에러 메시지를 앱 내에서 직접 표시합니다.
   *
   * @param {string} errorMessage - 에러 메시지
   * @param {string} title - 제목 (선택사항)
   */
  showErrorModal(errorMessage, title = '오류 발생') {
    try {
      console.log('[UI] FDK 환경용 에러 표시 시작');

      const errorContent = `
        <div class="alert alert-danger" style="margin: 0; padding: 15px; border-radius: 6px; border: 1px solid #f5c6cb; background-color: #f8d7da; color: #721c24;">
          <div style="display: flex; align-items: center; margin-bottom: 10px;">
            <span style="font-size: 20px; margin-right: 10px;">⚠️</span>
            <strong>오류가 발생했습니다</strong>
          </div>
          <div style="font-size: 14px;">
            ${errorMessage}
          </div>
        </div>
      `;

      // showModal 함수를 재사용하여 에러 내용 표시
      this.showModal(errorContent, title);

      console.log('[UI] FDK 환경용 에러 표시 완료');
    } catch (error) {
      console.error('[UI] 에러 표시 오류:', error);
      this.showToast(`오류: ${errorMessage}`, 'error');
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
      if (data.ticket) {
        this.displayTicketInfo(data.ticket);
      }

      // 관련 문서 표시
      if (data.related_docs && data.related_docs.length > 0) {
        this.displayRelatedDocs(data.related_docs);
      }

      // 요약 정보 표시
      if (data.summary) {
        this.displaySummary(data.summary);
      }

      console.log('[UI] 캐시된 데이터로 UI 업데이트 완료');
    } catch (error) {
      console.error('[UI] 캐시된 데이터 UI 업데이트 오류:', error);
    }
  },

  /**
   * 수동 모달 숨기기 함수
   */
  hideManualModal(modal, backdrop) {
    try {
      console.log('[UI] 수동 모달 숨기기');
      
      modal.style.display = 'none';
      modal.classList.remove('show');
      modal.setAttribute('aria-hidden', 'true');
      
      if (backdrop) {
        backdrop.remove();
      }
      
      document.body.classList.remove('modal-open');
      document.body.style.overflow = '';
      
    } catch (error) {
      console.error('[UI] 수동 모달 숨기기 오류:', error);
    }
  },

  /**
   * FDK 환경용 콘텐츠 숨기기 함수
   *
   * 표시된 응답 콘텐츠를 숨기고 원래 탭 콘텐츠를 복원합니다.
   */
  hideModal() {
    try {
      console.log('[UI] FDK 환경용 콘텐츠 숨기기');

      // 응답 컨테이너 숨기기
      const responseContainer = this.safeGetElement('#fdk-response-container');
      if (responseContainer) {
        responseContainer.style.display = 'none';
      }

      // 기존 탭 콘텐츠 다시 표시
      const tabContent = this.safeGetElement('.tab-content');
      if (tabContent) {
        tabContent.style.display = 'block';
      }

      console.log('[UI] 원래 UI 상태 복원 완료');
    } catch (error) {
      console.error('[UI] 콘텐츠 숨기기 오류:', error);
    }
  },

  // 캐시된 데이터로 UI를 즉시 업데이트하는 함수
  updateUIWithCachedData() {
    try {
      if (!globalTicketData.summary) {
        console.log('⚠️ 캐시된 데이터 없음 → UI 업데이트 스킵');
        return;
      }

      console.log('🎯 캐시된 데이터로 UI 즉시 업데이트 시작');

      // 티켓 기본 정보 업데이트 (백엔드 응답의 ticket_data 사용)
      if (globalTicketData.ticket_info) {
        this.updateTicketInfo(globalTicketData.ticket_info);
      }

      // 요약 정보 업데이트
      if (globalTicketData.summary) {
        const summaryContent = this.safeGetElement('#copilot-content');
        if (summaryContent) {
          summaryContent.innerHTML = this.formatSummaryForDisplay(globalTicketData.summary);
        }
      }

      // 유사 티켓 데이터가 있으면 미리 준비
      if (globalTicketData.similar_tickets && globalTicketData.similar_tickets.length > 0) {
        console.log(`✅ 유사 티켓 ${globalTicketData.similar_tickets.length}개 캐시 준비 완료`);
      }

      // 추천 솔루션 데이터가 있으면 미리 준비
      if (
        globalTicketData.recommended_solutions &&
        globalTicketData.recommended_solutions.length > 0
      ) {
        console.log(
          `✅ 추천 솔루션 ${globalTicketData.recommended_solutions.length}개 캐시 준비 완료`
        );
      }

      console.log('✅ 캐시된 데이터로 UI 업데이트 완료');
    } catch (error) {
      console.error('❌ 캐시된 데이터로 UI 업데이트 실패:', error);
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
            <small class="text-muted">발견된 유사 티켓: ${similarTickets.length}개</small>
          </div>
          <div id="tickets-container"></div>
        </div>
      `;

      const ticketsContainer = this.safeGetElement('tickets-container');

      // 각 유사 티켓을 새로운 리스트 아이템으로 렌더링
      similarTickets.forEach((similarTicket) => {
        const ticketItem = document.createElement('div');
        ticketItem.className = 'list-item';

        // 유사도 점수 계산 (임시)
        const similarityScore = similarTicket.score || Math.random() * 30 + 70;

        ticketItem.innerHTML = `
          <div class="list-item-header">
            <div class="list-item-title">${similarTicket.subject || 'No subject'}</div>
            <div class="d-flex align-items-center gap-2">
              <span class="score-badge">${Math.round(similarityScore)}%</span>
              <span class="badge-custom ${getStatusClass(
                similarTicket.status
              )}">${getStatusText(similarTicket.status)}</span>
            </div>
          </div>
          <div class="list-item-meta">
            <span>티켓 #${similarTicket.id}</span> • 
            <span>우선순위: ${getPriorityText(similarTicket.priority)}</span>
            ${
              similarTicket.created_at
                ? ` • <span>${formatDate(similarTicket.created_at)}</span>`
                : ''
            }
          </div>
          ${
            similarTicket.issue || similarTicket.solution
              ? `
            <div class="list-item-excerpt">
              ${
                similarTicket.issue
                  ? `<div class="mb-2">🔍 <strong>문제:</strong> ${truncateText(
                      similarTicket.issue,
                      100
                    )}</div>`
                  : ''
              }
              ${
                similarTicket.solution
                  ? `<div>💡 <strong>해결책:</strong> ${truncateText(
                      similarTicket.solution,
                      100
                    )}</div>`
                  : ''
              }
            </div>
          `
              : similarTicket.description_text || similarTicket.description
                ? `
            <div class="list-item-excerpt">
              ${truncateText(similarTicket.description_text || similarTicket.description, 150)}
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

  // 에러 메시지를 결과 영역에 표시하는 함수
  showErrorInResultsInResults(message, containerId = 'similar-tickets-list') {
    try {
      const container = this.safeGetElement(containerId);
      if (container) {
        container.innerHTML = `
          <div class="error-message alert alert-warning">
            <i class="fas fa-exclamation-triangle"></i>
            ${message}
          </div>
        `;
      } else {
        console.warn(`⚠️ 컨테이너를 찾을 수 없음: ${containerId}`);
      }
    } catch (error) {
      console.error('❌ showErrorInResultsInResults 오류', error);
    }
  },

  /**
   * 로딩 인디케이터 표시
   *
   * 데이터 로딩 중임을 사용자에게 시각적으로 알립니다.
   * 진행률과 설명 메시지를 함께 표시할 수 있습니다.
   *
   * @param {string} message - 로딩 중 표시할 메시지
   * @param {number} progress - 진행률 (0-100, 선택사항)
   * @param {string} containerId - 로딩을 표시할 컨테이너 ID (선택사항)
   *
   * @example
   * UI.showLoading('데이터를 불러오는 중...', 30);
   * UI.showLoading('AI 응답 생성 중...', null, 'chat-container');
   */
  showLoading(message = '로딩 중...', progress = null, containerId = null) {
    try {
      console.log(`[UI] 로딩 표시: ${message} ${progress !== null ? `(${progress}%)` : ''}`);

      // 기존 로딩 인디케이터 제거
      this.hideLoading(containerId);

      // 로딩 인디케이터 생성
      const loadingElement = document.createElement('div');
      loadingElement.className = 'loading-indicator';
      loadingElement.setAttribute('data-container', containerId || 'global');

      // 진행률 바가 있는 경우와 없는 경우 구분
      const progressBarHTML =
        progress !== null
          ? `
        <div class="progress-container">
          <div class="progress-bar">
            <div class="progress-fill" style="width: ${Math.max(0, Math.min(100, progress))}%"></div>
          </div>
          <div class="progress-text">${Math.round(progress)}%</div>
        </div>
      `
          : '';

      loadingElement.innerHTML = `
        <div class="loading-content">
          <div class="loading-spinner">
            <div class="spinner-ring"></div>
            <div class="spinner-ring"></div>
            <div class="spinner-ring"></div>
          </div>
          <div class="loading-message">${message}</div>
          ${progressBarHTML}
        </div>
      `;

      // 스타일 적용
      Object.assign(loadingElement.style, {
        position: 'absolute',
        top: '0',
        left: '0',
        right: '0',
        bottom: '0',
        background: 'rgba(255, 255, 255, 0.9)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: '9999',
        fontSize: '14px',
        fontFamily: 'system-ui, -apple-system, sans-serif',
      });

      // CSS 스타일을 head에 추가 (한 번만)
      if (!document.querySelector('#loading-styles')) {
        const style = document.createElement('style');
        style.id = 'loading-styles';
        style.textContent = `
          .loading-content {
            text-align: center;
            max-width: 300px;
            padding: 20px;
            background: white;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
          }
          .loading-spinner {
            display: inline-block;
            position: relative;
            width: 40px;
            height: 40px;
            margin-bottom: 12px;
          }
          .spinner-ring {
            position: absolute;
            border: 3px solid #f3f3f3;
            border-top: 3px solid #2196f3;
            border-radius: 50%;
            animation: spin 1s linear infinite;
          }
          .spinner-ring:nth-child(1) { width: 40px; height: 40px; }
          .spinner-ring:nth-child(2) { width: 30px; height: 30px; top: 5px; left: 5px; animation-delay: -0.3s; }
          .spinner-ring:nth-child(3) { width: 20px; height: 20px; top: 10px; left: 10px; animation-delay: -0.6s; }
          @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
          }
          .loading-message {
            color: #333;
            font-weight: 500;
            margin-bottom: 12px;
          }
          .progress-container {
            margin-top: 16px;
          }
          .progress-bar {
            width: 100%;
            height: 6px;
            background: #e0e0e0;
            border-radius: 3px;
            overflow: hidden;
          }
          .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #2196f3, #21cbf3);
            transition: width 0.3s ease;
          }
          .progress-text {
            font-size: 12px;
            color: #666;
            margin-top: 8px;
          }
        `;
        document.head.appendChild(style);
      }

      // 컨테이너 지정
      const container = containerId ? this.safeGetElement(`#${containerId}`) : document.body;
      if (container) {
        // 컨테이너가 relative position이 아니면 설정
        if (window.getComputedStyle(container).position === 'static') {
          container.style.position = 'relative';
        }
        container.appendChild(loadingElement);
      } else {
        document.body.appendChild(loadingElement);
      }

      console.log('[UI] 로딩 인디케이터 표시 완료');
    } catch (error) {
      console.error('[UI] 로딩 인디케이터 표시 오류:', error);
    }
  },

  /**
   * 로딩 인디케이터 숨기기
   *
   * 표시된 로딩 인디케이터를 제거합니다.
   *
   * @param {string} containerId - 특정 컨테이너의 로딩만 숨기기 (선택사항)
   *
   * @example
   * UI.hideLoading(); // 모든 로딩 인디케이터 숨기기
   * UI.hideLoading('chat-container'); // 특정 컨테이너의 로딩만 숨기기
   */
  hideLoading(containerId = null) {
    try {
      const selector = containerId
        ? `.loading-indicator[data-container="${containerId}"]`
        : '.loading-indicator';

      const loadingElements = document.querySelectorAll(selector);
      loadingElements.forEach((element) => {
        element.remove();
      });

      if (loadingElements.length > 0) {
        console.log(`[UI] 로딩 인디케이터 숨김 완료 (${loadingElements.length}개)`);
      }
    } catch (error) {
      console.error('[UI] 로딩 인디케이터 숨기기 오류:', error);
    }
  },

  /**
   * 로딩 진행률 업데이트
   *
   * 현재 표시된 로딩 인디케이터의 진행률을 업데이트합니다.
   *
   * @param {number} progress - 새로운 진행률 (0-100)
   * @param {string} message - 업데이트할 메시지 (선택사항)
   * @param {string} containerId - 업데이트할 컨테이너 ID (선택사항)
   *
   * @example
   * UI.updateLoadingProgress(75, '거의 완료되었습니다...');
   */
  updateLoadingProgress(progress, message = null, containerId = null) {
    try {
      const selector = containerId
        ? `.loading-indicator[data-container="${containerId}"]`
        : '.loading-indicator';

      const loadingElement = document.querySelector(selector);
      if (!loadingElement) {
        console.warn('[UI] 업데이트할 로딩 인디케이터를 찾을 수 없음');
        return;
      }

      // 진행률 바 업데이트
      const progressFill = loadingElement.querySelector('.progress-fill');
      const progressText = loadingElement.querySelector('.progress-text');

      if (progressFill) {
        progressFill.style.width = `${Math.max(0, Math.min(100, progress))}%`;
      }

      if (progressText) {
        progressText.textContent = `${Math.round(progress)}%`;
      }

      // 메시지 업데이트
      if (message) {
        const messageElement = loadingElement.querySelector('.loading-message');
        if (messageElement) {
          messageElement.textContent = message;
        }
      }

      console.log(`[UI] 로딩 진행률 업데이트: ${progress}%`);
    } catch (error) {
      console.error('[UI] 로딩 진행률 업데이트 오류:', error);
    }
  },

  /**
   * 공통 모달 트리거 함수 - 캐시된 데이터만 사용하여 즉시 열기
   * 백엔드 호출 없이 모달을 즉시 열고, 캐시된 데이터가 있으면 표시
   */
  async showMainModal() {
    try {
      console.log('🚀 모달 열기 시작 (백엔드 호출 없음)');

      // 컨텍스트 정보 가져오기
      const context = await client.instance.context();
      console.log('📍 컨텍스트 정보:', context);

      const data = await client.data.get('ticket');
      const ticket = data.ticket;
      console.log('📋 티켓 데이터 가져옴:', ticket.id);

      // 캐시된 데이터 확인 (선택적 - 있으면 사용, 없어도 모달 열기)
      const hasCachedData =
        globalTicketData.cached_ticket_id === ticket.id &&
        !isDataStale() &&
        globalTicketData.summary;

      if (hasCachedData) {
        console.log('⚡ 캐시된 데이터 사용 가능');
      } else {
        console.log('ℹ️ 캐시된 데이터 없음 - 빈 상태로 모달 열기');
      }

      // 항상 즉시 모달 열기 (캐시 여부와 관계없이)
      const modalConfig = {
        title: 'Copilot Canvas',
        template: 'index.html',
        data: {
          showAiTab: false,
          ticket,
          context: context,
        },
        noBackdrop: true,
        size: {
          width: '800px',
          height: '600px',
        },
      };

      console.log('🔧 모달 설정:', modalConfig);
      await client.interface.trigger('showModal', modalConfig);
      console.log('✅ 모달 즉시 열림 완료');
    } catch (error) {
      console.error('❌ 모달 오류:', error);
      console.error('❌ 모달 오류 스택:', error.stack);

      // 폴백: 간단한 모달로 재시도
      try {
        console.log('🔄 폴백 모달 시도');
        await client.interface.trigger('showModal', {
          title: 'Copilot Canvas',
          template: 'index.html',
        });
        console.log('✅ 폴백 모달 열림 완료');
      } catch (fallbackError) {
        console.error('❌ 폴백 모달도 실패:', fallbackError);
      }
    }
  },

  /**
   * DOM 요소 캐싱 및 최적화된 접근
   */
  getDOMElement(selector, forceRefresh = false) {
    return window.PerformanceOptimizer.getDOMElement(selector, forceRefresh);
  },

  /**
   * 배치 DOM 업데이트 처리
   * 여러 DOM 조작을 한 번에 처리하여 리플로우/리페인트 최소화
   */
  async batchDOMUpdates(updates) {
    return await window.PerformanceOptimizer.batchDOMUpdates(updates);
  },

  /**
   * 가상 스크롤링 지원 (대량 데이터 렌더링 최적화)
   */
  createVirtualList(container, items, renderItem, itemHeight = 50) {
    const virtualList = {
      container: container,
      items: items,
      renderItem: renderItem,
      itemHeight: itemHeight,
      visibleStart: 0,
      visibleEnd: 0,
      scrollTop: 0,
      containerHeight: 0,
      totalHeight: items.length * itemHeight,

      init() {
        this.containerHeight = container.clientHeight;
        this.calculateVisibleRange();
        this.render();
        this.setupScrollListener();
      },

      calculateVisibleRange() {
        const buffer = 5; // 버퍼 아이템 수
        this.visibleStart = Math.max(0, Math.floor(this.scrollTop / this.itemHeight) - buffer);
        this.visibleEnd = Math.min(
          this.items.length,
          Math.ceil((this.scrollTop + this.containerHeight) / this.itemHeight) + buffer
        );
      },

      render() {
        // 기존 내용 정리
        container.innerHTML = '';

        // 전체 높이를 위한 스페이서
        const spacer = document.createElement('div');
        spacer.style.height = `${this.totalHeight}px`;
        spacer.style.position = 'relative';
        container.appendChild(spacer);

        // 보이는 아이템들만 렌더링
        for (let i = this.visibleStart; i < this.visibleEnd; i++) {
          const item = this.items[i];
          const element = this.renderItem(item, i);
          element.style.position = 'absolute';
          element.style.top = `${i * this.itemHeight}px`;
          element.style.width = '100%';
          element.style.height = `${this.itemHeight}px`;
          spacer.appendChild(element);
        }
      },

      setupScrollListener() {
        const throttledScroll = window.PerformanceOptimizer.throttle(() => {
          const newScrollTop = container.scrollTop;
          if (Math.abs(newScrollTop - this.scrollTop) > this.itemHeight) {
            this.scrollTop = newScrollTop;
            this.calculateVisibleRange();
            this.render();
          }
        }, 16); // 60fps

        container.addEventListener('scroll', throttledScroll);
      },

      updateItems(newItems) {
        this.items = newItems;
        this.totalHeight = newItems.length * this.itemHeight;
        this.calculateVisibleRange();
        this.render();
      },
    };

    virtualList.init();
    return virtualList;
  },

  /**
   * 레이지 로딩 이미지 지원
   */
  setupLazyImages(container = document) {
    const imageObserver = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          const img = entry.target;
          if (img.dataset.src) {
            img.src = img.dataset.src;
            img.removeAttribute('data-src');
            imageObserver.unobserve(img);
          }
        }
      });
    });

    container.querySelectorAll('img[data-src]').forEach((img) => {
      imageObserver.observe(img);
    });

    return imageObserver;
  },

  /**
   * 스마트 검색 및 필터링 (디바운스 적용)
   */
  setupSmartSearch(inputElement, searchCallback, options = {}) {
    const { debounceMs = 300, minLength = 2, placeholder = '검색어를 입력하세요...' } = options;

    inputElement.placeholder = placeholder;

    const debouncedSearch = window.PerformanceOptimizer.debounce(async (query) => {
      if (query.length >= minLength) {
        try {
          this.showLoading('검색 중...', 'search-loading');
          await searchCallback(query);
        } catch (error) {
          window.ErrorHandler.handleError(error, {
            context: 'smart_search',
            userMessage: '검색 중 오류가 발생했습니다.',
          });
        } finally {
          this.hideLoading('search-loading');
        }
      } else if (query.length === 0) {
        searchCallback(''); // 전체 목록 표시
      }
    }, debounceMs);

    inputElement.addEventListener('input', (e) => {
      debouncedSearch(e.target.value.trim());
    });
  },

  /**
   * 최적화된 티켓 리스트 렌더링
   */
  async renderOptimizedTicketList(tickets, container) {
    if (!tickets || tickets.length === 0) {
      container.innerHTML = '<div class="no-data">표시할 티켓이 없습니다.</div>';
      return;
    }

    // 대량 데이터의 경우 가상 스크롤링 사용
    if (tickets.length > 100) {
      return this.createVirtualList(
        container,
        tickets,
        (ticket) => {
          const element = document.createElement('div');
          element.className = 'ticket-item';
          element.innerHTML = this.generateTicketHTML(ticket);
          return element;
        },
        80
      );
    }

    // 일반적인 경우 배치 렌더링
    const updates = tickets.map((ticket) => ({
      type: 'create',
      tag: 'div',
      properties: {
        className: 'ticket-item',
        innerHTML: this.generateTicketHTML(ticket),
      },
      parent: container,
    }));

    // 기존 내용 정리
    container.innerHTML = '';

    // 배치 업데이트 실행
    await this.batchDOMUpdates(updates);
  },

  /**
   * 최적화된 솔루션 리스트 렌더링
   */
  async renderOptimizedSolutionList(solutions, container) {
    if (!solutions || solutions.length === 0) {
      container.innerHTML = '<div class="no-data">표시할 솔루션이 없습니다.</div>';
      return;
    }

    // 배치 렌더링으로 성능 최적화
    const updates = solutions.map((solution) => ({
      type: 'create',
      tag: 'div',
      properties: {
        className: 'solution-item',
        innerHTML: this.generateSolutionHTML(solution),
      },
      parent: container,
    }));

    container.innerHTML = '';
    await this.batchDOMUpdates(updates);
  },

  // 의존성 확인 함수 - 다른 모듈에서 UI 모듈 사용 가능 여부 체크
  isAvailable: function () {
    try {
      // UI 모듈의 핵심 의존성: GlobalState, Utils, Data
      return (
        typeof GlobalState !== 'undefined' &&
        typeof Utils !== 'undefined' &&
        typeof Data !== 'undefined'
      );
    } catch (error) {
      console.error('[UI] 의존성 확인 중 오류:', error);
      return false;
    }
  },
};

// 전역 함수로 내보내기 (HTML onclick 등에서 사용)
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

console.log('🎨 UI 모듈 로드 완료 - 12개 함수 export됨');

// 모듈 의존성 시스템에 등록 (data 의존성 명시)
if (typeof ModuleDependencyManager !== 'undefined') {
  ModuleDependencyManager.registerModule('ui', Object.keys(UI).length, ['data']);
}
