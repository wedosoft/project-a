/**
 * 데이터 처리 및 캐시 관리 모듈 (Data)
 *
 * Freshdesk Custom App - Prompt Canvas
 * 이 파일은 모든 데이터 처리, 캐시 관리, 백엔드 통신을 담당합니다.
 *
 * 주요 기능:
 * - 티켓 데이터 로드 및 캐싱
 * - 유사 티켓 및 추천 솔루션 데이터 관리
 * - 백엔드 API 통신 및 응답 처리
 * - 프롬프트 전송 및 AI 응답 처리
 * - 전역 데이터 캐시 관리 및 무효화
 * - 모의 데이터 생성 (개발/테스트용)
 *
 * 의존성:
 * - GlobalState: 전역 상태 및 데이터 캐시
 * - API: 백엔드 API 통신
 * - Utils: 유틸리티 함수
 *
 * @namespace Data
 * @author Freshdesk Custom App Team
 * @since 1.0.0
 */

// Data 모듈 정의 - 모든 데이터 관련 함수를 하나의 객체로 관리
window.Data = {

  /**
   * 티켓 상세 정보 로드 및 UI 업데이트
   *
   * Freshdesk API에서 현재 티켓의 상세 정보를 가져와서
   * UI에 표시합니다. 백엔드 호출 없이 클라이언트 사이드에서만 처리됩니다.
   *
   * @param {Object} client - Freshdesk client 객체
   * @returns {Promise<void>} 비동기 처리 완료
   *
   * @example
   * await Data.loadTicketDetails(app.client);
   */
  async loadTicketDetails(client) {
    try {
      console.log('📋 티켓 상세 정보 확인 시작 (백엔드 호출 없음)');

      // 티켓 ID 가져오기
      const ticketData = await client.data.get('ticket');

      if (ticketData && ticketData.ticket) {
        const basicTicketInfo = ticketData.ticket;
        console.log('✅ 기본 티켓 정보 확인 완료:', basicTicketInfo);

        // 전역 상태에서 캐시된 데이터 확인
        const globalData = GlobalState.getGlobalTicketData();

        // 캐시된 데이터가 있고 최신인지 확인
        if (
          globalData.cached_ticket_id === basicTicketInfo.id &&
          globalData.summary &&
          GlobalState.isGlobalDataValid()
        ) {
          console.log('⚡ 캐시된 데이터 사용 가능');
          return;
        }

        // 새로운 티켓인 경우 캐시 초기화
        if (globalData.cached_ticket_id !== basicTicketInfo.id) {
          console.log('🆕 새로운 티켓 감지 → 캐시 초기화');
          GlobalState.resetGlobalTicketCache();
        }

        // 백엔드 호출 없이 기본 정보만 저장
        GlobalState.updateGlobalTicketData(basicTicketInfo.id, 'cached_ticket_id');
        GlobalState.updateGlobalTicketData(basicTicketInfo, 'ticket_info');
        console.log('ℹ️ 백엔드 호출 없이 기본 정보만 저장');
      } else {
        console.warn('⚠️ 기본 티켓 정보를 찾을 수 없음');
      }
    } catch (error) {
      console.error('❌ 티켓 상세 정보 확인 오류:', error);
    }
  },

  /**
   * 추천 해결책 로드
   *
   * 티켓과 관련된 추천 해결책을 로드하고 표시합니다.
   * 캐시된 데이터가 있으면 재사용하고, 없으면 모의 데이터를 사용합니다.
   *
   * @param {Object} ticket - 티켓 정보 객체
   *
   * @example
   * Data.loadSuggestedSolutions(currentTicket);
   */
  loadSuggestedSolutions(ticket) {
    const resultsElement = document.getElementById('suggested-solutions-list');
    if (resultsElement) {
      resultsElement.innerHTML = '<div class="placeholder-text">추천 해결책을 로드하는 중...</div>';
    }

    try {
      console.log('💡 추천 해결책 로드 시작');

      // 캐시된 데이터가 있고 같은 티켓인 경우 재사용
      const globalData = GlobalState.getGlobalTicketData();
      if (
        globalData.cached_ticket_id === ticket.id &&
        globalData.recommended_solutions.length > 0
      ) {
        console.log('🔄 캐시된 추천 솔루션 데이터 사용');
        this.displaySuggestedSolutions(globalData.recommended_solutions);
        return;
      }

      // 캐시된 데이터가 없거나 다른 티켓인 경우에만 API 호출
      console.log('⚠️ 추천 솔루션이 캐시에 없음 - 백엔드에서 데이터를 받지 못했습니다');
      
      // UI에 데이터 없음 상태 표시
      this.showNoDataMessage('추천 솔루션', '백엔드에서 데이터를 가져오지 못했습니다. 새로고침을 시도해주세요.');
    } catch (error) {
      console.error('❌ 추천 솔루션 로드 오류:', error);
      // 에러 메시지 표시 (더이상 모의 데이터 사용하지 않음)
      this.showNoDataMessage('추천 솔루션', '데이터 로드 중 오류가 발생했습니다: ' + error.message);
    }
  },

  // 전역 호출 플래그 - 앱 전체에서 딱 한 번만 호출되도록 보장
  _hasCalledBackendInit: false,
  
  // 티켓별 호출 상태 관리
  _ticketCallStatus: new Map(),
  
  // 현재 진행 중인 호출
  _currentInitCall: null,

  // 백엔드 호출 플래그 리셋 (모달 새로고침용)
  resetBackendCallFlag() {
    this._hasCalledBackendInit = false;
    console.log('🔄 백엔드 호출 플래그 리셋 - 모달 새로고침을 위한 재호출 허용');
    
    // 에러 상태도 초기화
    if (window.GlobalState) {
      window.GlobalState.setGlobalError(false, null);
      console.log('🔄 글로벌 에러 상태도 초기화됨');
    }
  },

  // 모달에서 새로고침 버튼 클릭 시 데이터 재로드
  async refreshModalData(client) {
    console.log('🔄 모달 데이터 새로고침 시작');
    
    // 플래그 리셋하여 재호출 허용
    this.resetBackendCallFlag();
    
    // 캐시 클리어
    if (window.GlobalState) {
      window.GlobalState.resetGlobalTicketCache();
    }
    
    // 로딩 UI 표시
    if (window.UI && window.UI.showLoadingState) {
      window.UI.showLoadingState('데이터 새로고침 중...');
    }
    
    try {
      // 백엔드 재호출
      const result = await this.preloadTicketDataOnPageLoad(client);
      
      if (result) {
        console.log('✅ 모달 데이터 새로고침 성공');
        
        // UI 업데이트
        if (window.UI && window.UI.updateUIWithCachedData) {
          const globalData = window.GlobalState.getGlobalTicketData();
          window.UI.updateUIWithCachedData(globalData);
        }
        
        // 성공 토스트
        if (window.UI && window.UI.showToast) {
          window.UI.showToast('데이터가 성공적으로 새로고침되었습니다.', 'success');
        }
      } else {
        throw new Error('데이터 새로고침 실패');
      }
    } catch (error) {
      console.error('❌ 모달 데이터 새로고침 실패:', error);
      
      // 실패 토스트
      if (window.UI && window.UI.showToast) {
        window.UI.showToast('데이터 새로고침에 실패했습니다. 다시 시도해 주세요.', 'error');
      }
    } finally {
      // 로딩 UI 숨기기
      if (window.UI && window.UI.hideLoadingState) {
        window.UI.hideLoadingState();
      }
    }
  },

  // 티켓 페이지 로드 시 백그라운드에서 데이터 미리 준비하는 함수 (딱 1번만 호출)
  async preloadTicketDataOnPageLoad(client) {
    // 🚨 절대적 중복 호출 방지 - 이미 호출되었으면 즉시 종료
    if (this._hasCalledBackendInit) {
      console.log('🚫 백엔드 호출 이미 완료됨 - 중복 호출 차단');
      return false;
    }
    
    // 🔒 이미 진행 중인 호출이 있으면 그것을 반환
    if (this._currentInitCall) {
      console.log('🔄 백엔드 호출이 이미 진행 중 - 기존 호출 대기');
      return this._currentInitCall;
    }
    
    // 🔒 호출 플래그 즉시 설정 (동시 호출 방지)
    this._hasCalledBackendInit = true;
    console.log('🔐 백엔드 초기화 호출 플래그 설정 - 이후 모든 호출 차단');

    try {
      // FDK 모달 컨텍스트 감지 - 모달에서는 백그라운드 데이터 로딩 완전 금지
      if (typeof window.isFDKModal !== 'undefined' && window.isFDKModal) {
        console.log('🎭 FDK 모달에서는 백엔드 호출 안함');
        return false;
      }
      
      // API 모듈 안전 확인
      if (!window.SAFE_MODULE_ACCESS.isAPIReady()) {
        console.error('❌ API 모듈이 아직 준비되지 않음 - 모듈 로드 대기');
        
        // 최대 5초 대기
        const ready = await window.SAFE_MODULE_ACCESS.waitForModules(5000);
        if (!ready) {
          console.error('❌ API 모듈 로드 타임아웃 - 사용자가 새로고침 필요');
          return false;
        }
      }

      // 🎯 단순화된 백엔드 호출 - 복잡한 로직 제거
      console.log('🚀 백엔드 초기화 시작 (딱 1회 호출)');
      
      // 현재 티켓 ID 가져오기 (실패해도 진행)
      let ticketId = null;
      try {
        const ticketData = await client.data.get('ticket');
        ticketId = ticketData?.ticket?.id || '12345'; // 기본값
      } catch (error) {
        console.warn('⚠️ 티켓 ID를 가져올 수 없음, 기본값 사용');
        ticketId = '12345';
      }
      
      // 백엔드 호출 시도 (딱 1번)
      try {
        console.log(`🔥 백엔드 /init/${ticketId} 호출 시도 (최초 1회)`);
        
        // 현재 호출을 저장
        this._currentInitCall = this.loadInitialDataFromBackend(client, { id: ticketId });
        const result = await this._currentInitCall;
        
        // 호출 완료 후 초기화
        this._currentInitCall = null;
        
        if (result) {
          console.log('✅ 백엔드 초기화 성공 완료');
          
          // 🎯 데이터 로드 성공 시 자동으로 UI 렌더링 호출
          const globalData = window.GlobalState.getGlobalTicketData();
          if (globalData && (globalData.summary || globalData.similar_tickets || globalData.kb_documents)) {
            console.log('🎨 백엔드 데이터 로드 완료 → 자동 UI 렌더링 시작');
            this.renderDataToUI(globalData);
          }
          
          return true;
        } else {
          console.error('❌ 백엔드 초기화 실패 - 사용자가 페이지 새로고침 필요');
          this.showUserRefreshMessage();
          return false;
        }
      } catch (error) {
        console.error('❌ 백엔드 호출 중 오류 발생:', error);
        this._currentInitCall = null;
        this.showUserRefreshMessage();
        return false;
      }
    } catch (error) {
      console.error('❌ preloadTicketDataOnPageLoad 전체 오류:', error);
      this.showUserRefreshMessage();
      return false;
    }
  },

  /**
   * 🎨 백엔드 데이터를 UI에 렌더링하는 핵심 함수
   * @param {Object} data - 백엔드에서 받은 데이터
   */
  renderDataToUI(data) {
    try {
      // 내부 필드들 필터링
      const filteredData = this.filterInternalFields(data);
      
      console.log('🎨 UI 렌더링 시작:', {
        summary: filteredData.summary ? '요약 데이터 있음' : '요약 데이터 없음',
        similar_tickets: filteredData.similar_tickets ? `유사 티켓 ${filteredData.similar_tickets.length}개` : '유사 티켓 없음',
        kb_documents: filteredData.kb_documents ? `KB 문서 ${filteredData.kb_documents.length}개` : 'KB 문서 없음'
      });
      
      // 1. 요약 데이터 렌더링
      if (filteredData.summary) {
        this.renderSummaryToUI(filteredData.summary);
      }
      
      // 2. 유사 티켓 렌더링
      if (filteredData.similar_tickets && filteredData.similar_tickets.length > 0) {
        this.renderSimilarTicketsToUI(filteredData.similar_tickets);
      }
      
      // 3. KB 문서 (추천 솔루션) 렌더링
      if (filteredData.kb_documents && filteredData.kb_documents.length > 0) {
        this.renderKBDocumentsToUI(filteredData.kb_documents);
      }
      
      // 4. 로딩 상태 해제 및 콘텐츠 표시
      this.hideLoadingAndShowContent();
      
      console.log('✅ UI 렌더링 완료');
    } catch (error) {
      console.error('❌ UI 렌더링 실패:', error);
    }
  },

  /**
   * 내부 필드들을 필터링하여 UI 렌더링용 데이터만 반환
   * @param {Object} data - 원본 데이터
   * @returns {Object} 필터링된 데이터
   */
  filterInternalFields(data) {
    const allowedFields = [
      'summary',
      'similar_tickets', 
      'kb_documents',
      'recommended_solutions',
      'ticket_info'
    ];
    
    const filtered = {};
    allowedFields.forEach(field => {
      if (data[field] !== undefined) {
        filtered[field] = data[field];
      }
    });
    
    return filtered;
  },

  /**
   * 📝 요약 데이터를 UI에 렌더링
   * @param {string} summary - 요약 텍스트
   */
  renderSummaryToUI(summary) {
    const summaryElement = document.querySelector('.summary-text');
    if (summaryElement) {
      // 마크다운을 HTML로 변환 (간단한 변환)
      const htmlSummary = this.convertMarkdownToHTML(summary);
      summaryElement.innerHTML = htmlSummary;
      
      // 요약 섹션 표시
      const summarySection = document.getElementById('summarySection');
      if (summarySection) {
        summarySection.classList.remove('collapsed');
        summarySection.classList.add('expanded');
      }
      
      console.log('📝 요약 렌더링 완료');
    } else {
      console.warn('⚠️ .summary-text 엘리먼트를 찾을 수 없음');
    }
  },

  /**
   * 🎫 유사 티켓 데이터를 UI에 렌더링
   * @param {Array} tickets - 유사 티켓 배열
   */
  renderSimilarTicketsToUI(tickets) {
    const ticketsTab = document.querySelector('[data-tab="tickets"]');
    if (!ticketsTab) {
      console.warn('⚠️ 유사 티켓 탭을 찾을 수 없음');
      return;
    }
    
    // 기존 카드들 제거 (인사이트 패널은 유지)
    const existingCards = ticketsTab.querySelectorAll('.content-card');
    existingCards.forEach(card => card.remove());
    
    // 유사 티켓 카드 생성
    tickets.forEach((ticket, index) => {
      const card = this.createTicketCard(ticket, index);
      ticketsTab.appendChild(card);
    });
    
    // 탭 카운트 업데이트
    this.updateTabCount('tickets', tickets.length);
    
    console.log(`🎫 유사 티켓 ${tickets.length}개 렌더링 완료`);
  },

  /**
   * 📚 KB 문서 데이터를 UI에 렌더링
   * @param {Array} documents - KB 문서 배열
   */
  renderKBDocumentsToUI(documents) {
    const kbTab = document.querySelector('[data-tab="kb"]');
    if (!kbTab) {
      console.warn('⚠️ KB 문서 탭을 찾을 수 없음');
      return;
    }
    
    // 기존 카드들 제거 (인사이트 패널은 유지)
    const existingCards = kbTab.querySelectorAll('.content-card');
    existingCards.forEach(card => card.remove());
    
    // KB 문서 카드 생성
    documents.forEach((doc, index) => {
      const card = this.createKBCard(doc, index);
      kbTab.appendChild(card);
    });
    
    // 탭 카운트 업데이트
    this.updateTabCount('kb', documents.length);
    
    console.log(`📚 KB 문서 ${documents.length}개 렌더링 완료`);
  },

  /**
   * 🎯 유사 티켓 카드 생성
   * @param {Object} ticket - 티켓 데이터
   * @param {number} index - 인덱스
   * @returns {HTMLElement} 생성된 카드 엘리먼트
   */
  createTicketCard(ticket, index) {
    const card = document.createElement('div');
    card.className = 'content-card';
    card.setAttribute('data-ticket-id', ticket.id || index);
    
    const relevanceScore = (ticket.relevance_score || ticket.score || 0) * 100;
    const scoreClass = relevanceScore >= 80 ? 'score-high' : 
                      relevanceScore >= 60 ? 'score-medium' : 'score-low';
    const scoreIcon = relevanceScore >= 80 ? '🟢' : 
                     relevanceScore >= 60 ? '🟡' : '🔴';
    
    card.innerHTML = `
      <div class="card-header">
        <span class="card-id">#${ticket.id || 'N/A'}</span>
        <span class="similarity-score ${scoreClass}">${scoreIcon} ${relevanceScore.toFixed(0)}%</span>
      </div>
      <div class="card-body">
        <div class="card-title">${ticket.title || ticket.subject || '제목 없음'}</div>
        <div class="card-excerpt">${this.truncateText(ticket.content || ticket.description_text || '', 150)}</div>
        <div class="card-meta">
          <span class="status-indicator">${ticket.status || 'Unknown'}</span>
          <span class="priority-indicator">${ticket.priority || 'Normal'}</span>
          ${ticket.agent_name ? `<span class="agent-name">${ticket.agent_name}</span>` : ''}
        </div>
        <div class="card-actions">
          <button onclick="Data.viewTicketSummary('${ticket.id || index}')" class="action-btn">
            👁️ 요약보기
          </button>
          <button onclick="Data.viewTicketOriginal('${ticket.id || index}')" class="action-btn">
            📄 원본보기
          </button>
        </div>
      </div>
    `;
    
    return card;
  },

  /**
   * 📚 KB 문서 카드 생성
   * @param {Object} doc - KB 문서 데이터
   * @param {number} index - 인덱스
   * @returns {HTMLElement} 생성된 카드 엘리먼트
   */
  createKBCard(doc, index) {
    const card = document.createElement('div');
    card.className = 'content-card';
    card.setAttribute('data-kb-id', doc.id || index);
    
    const relevanceScore = (doc.relevance_score || doc.score || 0) * 100;
    const scoreClass = relevanceScore >= 80 ? 'score-high' : 
                      relevanceScore >= 60 ? 'score-medium' : 'score-low';
    const scoreIcon = relevanceScore >= 80 ? '🟢' : 
                     relevanceScore >= 60 ? '🟡' : '🔴';
    
    card.innerHTML = `
      <div class="card-header">
        <span class="card-id">KB-${doc.id || index}</span>
        <span class="similarity-score ${scoreClass}">${scoreIcon} ${relevanceScore.toFixed(0)}%</span>
      </div>
      <div class="card-body">
        <div class="card-title">${doc.title || '제목 없음'}</div>
        <div class="card-excerpt">${this.truncateText(doc.content || doc.description || '', 150)}</div>
        <div class="card-meta">
          <span class="status-indicator">${doc.status || 'Published'}</span>
          ${doc.category ? `<span>📂 ${doc.category}</span>` : ''}
        </div>
        <div class="card-actions">
          <button onclick="Data.viewKBSummary('${doc.id || index}')" class="action-btn">
            👁️ 내용보기
          </button>
          <button onclick="Data.viewKBOriginal('${doc.id || index}')" class="action-btn">
            🔗 원본열기
          </button>
        </div>
      </div>
    `;
    
    return card;
  },

  // 사용자에게 새로고침 메시지 표시
  showUserRefreshMessage() {
    console.log('🔄 사용자에게 새로고침 안내 메시지 표시');
    
    // UI 토스트가 있으면 사용
    if (window.UI && window.UI.showToast) {
      window.UI.showToast(
        'AI 데이터 로드에 실패했습니다. 모달 우상단의 새로고침 버튼(🔄)을 클릭해주세요.',
        'error',
        10000 // 10초간 표시
      );
    } 
    
    // 🚨 항상 DOM 기반 경고 표시 (UI 토스트 보완)
    this.showServerDownWarning();
  },

  // 🚨 서버 다운 경고 표시 (DOM 기반 - 항상 표시됨)
  showServerDownWarning() {
    try {
      // 기존 경고 제거
      const existingWarning = document.getElementById('server-down-warning');
      if (existingWarning) {
        existingWarning.remove();
      }

      // 새 경고 메시지 생성
      const warningElement = document.createElement('div');
      warningElement.id = 'server-down-warning';
      warningElement.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        z-index: 99999;
        background: #fee2e2;
        border: 2px solid #f87171;
        color: #991b1b;
        padding: 16px 20px;
        border-radius: 8px;
        max-width: 350px;
        font-size: 14px;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        box-shadow: 0 8px 24px rgba(0,0,0,0.2);
        animation: slideInFromRight 0.3s ease-out;
      `;

      warningElement.innerHTML = `
        <div style="display: flex; align-items: flex-start; gap: 12px;">
          <div style="font-size: 20px; flex-shrink: 0;">⚠️</div>
          <div style="flex: 1;">
            <div style="font-weight: 600; margin-bottom: 6px;">서버 연결 오류</div>
            <div style="margin-bottom: 12px; line-height: 1.4;">
              AI 지원 서비스에 연결할 수 없습니다.<br>
              모달을 열어 새로고침 버튼을 클릭해주세요.
            </div>
            <div style="display: flex; gap: 8px;">
              <button onclick="this.parentElement.parentElement.parentElement.parentElement.remove();" 
                      style="background: #dc2626; color: white; border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer; font-size: 12px;">
                확인
              </button>
            </div>
          </div>
        </div>
      `;

      // CSS 애니메이션 추가
      if (!document.querySelector('#server-warning-styles')) {
        const style = document.createElement('style');
        style.id = 'server-warning-styles';
        style.textContent = `
          @keyframes slideInFromRight {
            from {
              transform: translateX(100%);
              opacity: 0;
            }
            to {
              transform: translateX(0);
              opacity: 1;
            }
          }
        `;
        document.head.appendChild(style);
      }

      document.body.appendChild(warningElement);
      console.log('🚨 서버 다운 경고 표시됨');

      // 15초 후 자동 제거
      setTimeout(() => {
        if (warningElement.parentNode) {
          warningElement.parentNode.removeChild(warningElement);
        }
      }, 15000);

    } catch (error) {
      console.error('❌ 서버 다운 경고 표시 실패:', error);
      // 최후의 수단으로 콘솔에 명시적 경고
      console.error('🆘 서버 연결 실패 - 사용자에게 알림 표시 불가');
    }
  },

  /**
   * 백그라운드 데이터 로드
   *
   * 앱이 초기화된 후 백그라운드에서 티켓 관련 데이터를 로드합니다.
   * 컨텍스트 확인, 티켓 페이지 검증, 캐시 확인 등의 단계를 거쳐
   * 필요한 경우에만 백엔드 API를 호출합니다.
   *
   * @param {Object} client - Freshdesk client 객체
   * @returns {Promise<void>} 비동기 처리 완료
   *
   * @description
   * 다음 단계를 순서대로 수행합니다:
   * 1. 클라이언트 컨텍스트 확인
   * 2. 티켓 페이지 여부 확인
   * 3. 티켓 데이터 안전 조회
   * 4. 캐시 상태 확인
   * 5. 필요시 백엔드 데이터 로드
   *
   * @example
   * Data.performBackgroundDataLoad(app.client);
   */
  async performBackgroundDataLoad(client) {
    try {
      console.log('🔄 백그라운드 데이터 로드 시작');

      // FDK 클라이언트가 준비되었는지 확인
      if (!client || typeof client.instance === 'undefined') {
        console.warn('⚠️ FDK 클라이언트가 아직 준비되지 않음');
        return;
      }

      // 컨텍스트 확인
      let ctx;
      try {
        ctx = await client.instance.context();
        console.log('🔍 페이지 컨텍스트 확인 성공:', ctx);
      } catch (contextError) {
        console.warn('⚠️ 컨텍스트 확인 실패, 기본 로직으로 진행:', contextError);
        // 기본 로직으로 진행 (티켓 페이지로 가정)
      }

      // 티켓 페이지인지 확인
      const isTicketPage =
        ctx.location &&
        (ctx.location.includes('ticket') || ctx.location === 'ticket_top_navigation');

      if (!isTicketPage) {
        console.log('📄 티켓 페이지가 아님 → 백그라운드 로드 스킵');
        return;
      }

      console.log('📋 티켓 페이지 확인됨 → 데이터 로드 시작');

      // 티켓 데이터 안전하게 가져오기
      let ticketData;
      try {
        ticketData = await client.data.get('ticket');
      } catch (dataError) {
        console.warn('⚠️ 티켓 데이터 접근 실패 (EventAPI 오류 가능성):', dataError);
        return;
      }

      if (ticketData && ticketData.ticket) {
        const currentTicketId = ticketData.ticket.id;

        // 캐시 확인 및 백엔드 호출
        const globalData = GlobalState.getGlobalTicketData();
        if (
          globalData.cached_ticket_id === currentTicketId &&
          globalData.summary &&
          !this.isDataStale()
        ) {
          console.log('✅ 이미 캐시된 데이터 존재 → 백그라운드 로드 스킵');
          return;
        }

        // 중복 호출 방지
        if (GlobalState.getGlobalLoading()) {
          console.log('⚠️ 이미 로딩 중이므로 백그라운드 로드 스킵');
          return;
        }

        console.log('🚀 백그라운드에서 새로운 티켓 데이터 로드 중...', currentTicketId);

        // 백엔드 호출 (FDK와 독립적)
        try {
          GlobalState.resetGlobalTicketCache();
          await this.loadInitialDataFromBackend(client, ticketData.ticket);
          console.log('✅ 백그라운드 데이터 로드 완료 → 앱 아이콘 클릭 시 즉시 모달 표시 가능');
        } catch (backendError) {
          console.warn('⚠️ 백엔드 호출 실패:', backendError);
        }
      } else {
        console.log('⚠️ 티켓 정보 없음 → 백그라운드 로드 스킵');
      }
    } catch (error) {
      console.warn('⚠️ 백그라운드 데이터 로드 중 예외 발생:', error);
    }
  },

  /**
   * 다단계 재시도 데이터 로드
   *
   * FDK의 불안정성을 고려하여 여러 시점에서 데이터 로드를 재시도합니다.
   * 각 시도는 점진적으로 늦어지는 지연 시간을 가지며,
   * 이미 데이터가 로드된 경우 후속 시도를 자동으로 중단합니다.
   *
   * @param {Object} client - Freshdesk client 객체
   * @returns {void}
   *
   * @description
   * 재시도 일정:
   * - 즉시 시도 (0ms)
   * - 500ms 후 재시도
   * - 1000ms 후 재시도
   * - 2000ms 후 재시도
   * - 3000ms 후 최종 시도
   *
   * @example
   * Data.retryDataLoadWithMultipleAttempts(app.client);
   */
  retryDataLoadWithMultipleAttempts(client) {
    console.log('🎯 적극적인 백그라운드 데이터 로드 전략 시작');

    // 여러 시점에서 안전한 데이터 로드 시도 (점진적 지연)
    const loadAttempts = [
      { delay: 0, label: '즉시 시도' },
      { delay: 500, label: '재시도 1' },
      { delay: 1000, label: '재시도 2' },
      { delay: 2000, label: '재시도 3' },
      { delay: 3000, label: '최종 시도' },
    ];

    loadAttempts.forEach(({ delay, label }) => {
      setTimeout(async () => {
        // 이미 로드된 경우 스킵
        const globalData = GlobalState.getGlobalTicketData();
        if (globalData.cached_ticket_id && globalData.summary) {
          console.log(`✅ ${label}: 이미 데이터 준비됨 - 스킵`);
          return;
        }

        try {
          console.log(`🔄 ${label} (${delay}ms 후) - FDK 안전성 검증 시작`);

          // FDK 안전성 검증
          if (
            !client ||
            typeof client.data === 'undefined' ||
            typeof client.instance === 'undefined'
          ) {
            console.warn(`⚠️ ${label}: FDK 아직 준비 안됨`);
            return;
          }

          // 컨텍스트 확인 (옵션, 실패해도 계속 진행)
          let isTicketPage = false;
          try {
            const ctx = await client.instance.context();
            isTicketPage =
              ctx.location &&
              (ctx.location.includes('ticket') || ctx.location === 'ticket_top_navigation');
            console.log(
              `🔍 ${label}: 컨텍스트 확인 - ${ctx.location} (티켓페이지: ${isTicketPage})`
            );
          } catch (contextError) {
            console.warn(`⚠️ ${label}: 컨텍스트 확인 실패, 티켓 데이터로 추론 시도`);
            isTicketPage = true; // 일단 시도해보기
          }

          // 티켓 데이터 안전하게 가져오기
          if (isTicketPage) {
            const ticketData = await client.data.get('ticket');

            if (ticketData && ticketData.ticket && ticketData.ticket.id) {
              const currentTicketId = ticketData.ticket.id;

              // 캐시 확인 및 중복 호출 방지
              const globalData = GlobalState.getGlobalTicketData();
              if (
                globalData.cached_ticket_id === currentTicketId &&
                globalData.summary &&
                !this.isDataStale()
              ) {
                console.log(`✅ ${label}: 이미 캐시된 데이터 존재 → 스킵`);
                return;
              }

              if (GlobalState.getGlobalLoading()) {
                console.log(`⚠️ ${label}: 이미 로딩 중 → 스킵`);
                return;
              }

              console.log(`🚀 ${label}: 티켓 ID ${currentTicketId} 백엔드 로드 시작`);

              // 백엔드 호출 (FDK와 독립적)
              GlobalState.resetGlobalTicketCache();
              await this.loadInitialDataFromBackend(client, ticketData.ticket);

              console.log(
                `✅ ${label}: 백엔드 데이터 로드 완료! 다음 앱 아이콘 클릭 시 즉시 표시됩니다.`
              );

              // 성공 시 더 이상 시도하지 않도록 플래그 설정
              return;
            } else {
              console.warn(`⚠️ ${label}: 티켓 데이터 없음`);
            }
          } else {
            console.log(`📄 ${label}: 티켓 페이지 아님 - 스킵`);
          }
        } catch (error) {
          console.warn(`⚠️ ${label}: 로드 실패 (${error.message})`);

          // EventAPI 오류는 예상된 상황이므로 덜 심각하게 처리
          if (error.message && error.message.includes('EventAPI')) {
            console.log(`🔧 ${label}: EventAPI 타이밍 이슈 - 나중에 다시 시도`);
          }
        }
      }, delay);
    });

    // 추가 전략: URL 변경 감지
    if (typeof window !== 'undefined') {
      let lastUrl = window.location.href;
      const urlCheckInterval = setInterval(() => {
        if (window.location.href !== lastUrl) {
          lastUrl = window.location.href;
          const globalData = GlobalState.getGlobalTicketData();
          if (
            lastUrl.includes('/tickets/') &&
            (!globalData.cached_ticket_id || !globalData.summary)
          ) {
            console.log('🎯 URL 변경으로 티켓 페이지 진입 감지 → 백그라운드 로드 시도');
            setTimeout(() => {
              this.attemptSingleBackgroundLoad(client, 'URL변경감지');
            }, 1500);
          }
        }
      }, 1000);

      // 10분 후 URL 감지 정리 (메모리 누수 방지)
      setTimeout(() => {
        clearInterval(urlCheckInterval);
        console.log('🧹 URL 변경 감지 종료');
      }, 600000);
    }
  },

  /**
   * 단일 백그라운드 로드 시도
   *
   * 한 번의 백그라운드 데이터 로드를 시도합니다.
   * 캐시 상태 확인, 중복 호출 방지, FDK 안전성 검증을 포함합니다.
   *
   * @param {Object} client - Freshdesk client 객체
   * @param {string} source - 로드 시도 출처 (로깅용)
   * @returns {Promise<void>} 비동기 처리 완료
   *
   * @example
   * await Data.attemptSingleBackgroundLoad(app.client, 'URL변경감지');
   */
  async attemptSingleBackgroundLoad(client, source = '단일시도') {
    try {
      // 캐시 확인
      const globalData = GlobalState.getGlobalTicketData();
      if (globalData.cached_ticket_id && globalData.summary && !this.isDataStale()) {
        console.log(`✅ ${source}: 이미 유효한 캐시 데이터 존재 → 스킵`);
        return;
      }

      // 중복 호출 방지
      if (GlobalState.getGlobalLoading()) {
        console.log(`⚠️ ${source}: 이미 로딩 중 → 스킵`);
        return;
      }

      const ticketData = await client.data.get('ticket');
      if (ticketData && ticketData.ticket && ticketData.ticket.id) {
        console.log(`🔄 ${source}: 백그라운드 로드 시작 (티켓: ${ticketData.ticket.id})`);
        GlobalState.resetGlobalTicketCache();
        await this.loadInitialDataFromBackend(client, ticketData.ticket);
        console.log(`✅ ${source}: 백그라운드 로드 성공`);
      }
    } catch (error) {
      console.warn(`⚠️ ${source}: 백그라운드 로드 실패:`, error.message);
    }
  },

  /**
   * 백엔드에서 초기 데이터를 로드하는 함수 (/init 엔드포인트 호출)
   * @param {Object} client - FDK 클라이언트 객체
   * @param {Object} ticket - 기본 티켓 정보
   * @param {string} agentLanguage - 에이전트 UI 언어 (선택사항)
   * @returns {Promise<Object>} 로드된 데이터 또는 null
   */
  loadInitialDataFromBackend(client, ticket) {
    return new Promise((resolve, reject) => {
      try {
        console.log('🚀 백엔드 스트리밍 데이터 로드 시작:', ticket.id);
        GlobalState.setGlobalLoading(true);
        GlobalState.setStreamingStatus({ is_streaming: true, last_event: null });

        if (!window.API) {
          console.error('❌ API 모듈이 로드되지 않음');
          GlobalState.setGlobalLoading(false);
          GlobalState.setStreamingStatus({ is_streaming: false });
          return reject(new Error('API module not loaded'));
        }

        const onStream = (event) => {
          try {
            GlobalState.setStreamingStatus({ is_streaming: true, last_event: event.type });
            if (event.type === 'done') {
              console.log('✅ 스트리밍 완료');
              GlobalState.setStreamingStatus({ is_streaming: false, last_event: 'done' });
              GlobalState.setGlobalLoading(false);
              resolve(true);
            } else if (event.type === 'error') {
              console.error('❌ 스트리밍 오류:', event.message);
              GlobalState.setGlobalError(true, event.message);
              GlobalState.setStreamingStatus({ is_streaming: false, last_event: 'error' });
              GlobalState.setGlobalLoading(false);
              reject(new Error(event.message));
            } else {
              // 데이터 유형에 따라 전역 상태 업데이트
              if (event.summary) {
                GlobalState.updateGlobalTicketData(event.summary, 'summary');
              }
              if (event.similar_tickets) {
                GlobalState.updateGlobalTicketData(event.similar_tickets, 'similar_tickets');
              }
              if (event.kb_documents) {
                GlobalState.updateGlobalTicketData(event.kb_documents, 'kb_documents');
              }
              // UI 점진적 업데이트
              if (window.UI && window.UI.updateUIWithCachedData) {
                window.UI.updateUIWithCachedData(GlobalState.getGlobalTicketData());
              }
            }
          } catch (streamError) {
            console.error('❌ onStream 콜백 내부 오류:', streamError);
          }
        };

        API.loadInitData(client, ticket.id, { onStream });

      } catch (error) {
        console.error('❌ 백엔드 스트리밍 데이터 로드 오류:', error);
        GlobalState.setGlobalError(true, '백엔드 연결에 실패했습니다.');
        GlobalState.setGlobalLoading(false);
        GlobalState.setStreamingStatus({ is_streaming: false });
        reject(error);
      }
    });
  },

  /**
   * 🚀 Vector DB 단독 모드 - 티켓 초기 데이터 로드
   *
   * /init 엔드포인트를 호출하여 티켓 요약, 유사 티켓, KB 문서를 한번에 가져옵니다.
   * 환경변수 ENABLE_FULL_STREAMING_MODE=true 시 Vector DB에서만 데이터를 조회합니다.
   *
   * @param {Object} client - Freshdesk client 객체
   * @param {string} ticketId - 티켓 ID
   * @returns {Promise<Object>} API 응답 결과
   */
  async loadInitDataVectorOnly(client, ticketId) {
    try {
      console.log(`🚀 Vector DB 단독 모드로 초기 데이터 로드: ${ticketId}`);

      // 캐시 확인
      const globalData = GlobalState.getGlobalTicketData();
      if (
        globalData.cached_ticket_id === ticketId &&
        globalData.summary &&
        globalData.similar_tickets &&
        globalData.kb_documents &&
        GlobalState.isGlobalDataValid()
      ) {
        console.log('⚡ 캐시된 Vector DB 데이터 사용');
        return { ok: true, data: globalData };
      }

      // /init 엔드포인트 호출 - Vector DB 단독 모드
      const response = await API.loadInitData(client, ticketId);

      if (response && response.ok && response.data) {
        const data = response.data;

        // Vector DB 단독 모드 데이터 구조 검증
        console.log('📊 Vector DB 응답 데이터 구조:', {
          hasSummary: !!data.summary,
          similarTicketsCount: data.similar_tickets?.length || 0,
          kbDocumentsCount: data.kb_documents?.length || 0,
          executionTime: data.execution_time,
          searchQualityScore: data.search_quality_score
        });

        // 전역 캐시 업데이트
        GlobalState.updateGlobalTicketData(ticketId, 'cached_ticket_id');
        GlobalState.updateGlobalTicketData(data.summary, 'summary');
        GlobalState.updateGlobalTicketData(data.similar_tickets || [], 'similar_tickets');
        GlobalState.updateGlobalTicketData(data.kb_documents || [], 'kb_documents');
        GlobalState.updateGlobalTicketData(Date.now(), 'last_updated');

        // 성능 메트릭 저장
        if (data.execution_time) {
          GlobalState.updateGlobalTicketData(data.execution_time, 'execution_time');
        }
        if (data.search_quality_score) {
          GlobalState.updateGlobalTicketData(data.search_quality_score, 'search_quality_score');
        }

        console.log('✅ Vector DB 단독 모드 데이터 로드 완료');
        return response;
      } else {
        console.error('❌ Vector DB 응답 데이터 없음');
        return { ok: false, error: 'No data received from Vector DB' };
      }
    } catch (error) {
      console.error('❌ Vector DB 단독 모드 데이터 로드 실패:', error);
      return { ok: false, error: error.message };
    }
  },

  /**
   * 🔄 하이브리드 모드 호환성 유지 (기존 로직)
   *
   * ENABLE_FULL_STREAMING_MODE=false 시 기존 하이브리드 로직을 사용합니다.
   *
   * @param {Object} client - Freshdesk client 객체
   * @param {string} ticketId - 티켓 ID
   * @returns {Promise<Object>} API 응답 결과
   */
  async loadInitDataHybrid(client, ticketId) {
    // 기존 하이브리드 로직 (100% 보존)
    return await API.loadInitData(client, ticketId);
  },

  /**
   * 🎯 통합 초기 데이터 로드 (환경변수 기반 자동 분기)
   *
   * 백엔드의 환경변수 설정에 따라 Vector DB 단독 또는 하이브리드 모드로 자동 분기됩니다.
   *
   * @param {Object} client - Freshdesk client 객체
   * @param {string} ticketId - 티켓 ID
   * @returns {Promise<Object>} API 응답 결과
   */
  async preloadTicketData(client, ticketId) {
    try {
      console.log(`🎯 통합 초기 데이터 로드 시작: ${ticketId}`);

      // 환경변수는 백엔드에서 자동으로 분기되므로 프론트엔드는 단일 API 호출
      const response = await this.loadInitDataVectorOnly(client, ticketId);

      if (response && response.ok) {
        // UI 업데이트 - 모든 데이터가 준비됨
        if (window.UI && window.UI.updateTicketSummary && response.data.summary) {
          window.UI.updateTicketSummary(response.data.summary);
        }

        // 유사 티켓 표시
        if (response.data.similar_tickets && response.data.similar_tickets.length > 0) {
          this.displaySimilarTickets(response.data.similar_tickets);
        }

        // KB 문서 표시
        if (response.data.kb_documents && response.data.kb_documents.length > 0) {
          this.displayKBDocuments(response.data.kb_documents);
        }

        console.log(`✅ 통합 초기 데이터 로드 완료: ${ticketId}`);
      }

      return response;
    } catch (error) {
      console.error('❌ 통합 초기 데이터 로드 실패:', error);
      return { ok: false, error: error.message };
    }
  },

  /**
   * 🎫 Vector DB 기반 유사 티켓 표시
   *
   * Vector DB에서 조회된 유사 티켓 데이터를 UI에 표시합니다.
   *
   * @param {Array} similarTickets - Vector DB에서 조회된 유사 티켓 배열
   */
  displaySimilarTickets(similarTickets) {
    const resultsElement = document.getElementById('similar-tickets-list');
    if (!resultsElement) {
      console.warn('⚠️ similar-tickets-list 엘리먼트를 찾을 수 없음');
      return;
    }

    if (!similarTickets || similarTickets.length === 0) {
      resultsElement.innerHTML = '<div class="no-results">유사한 티켓이 없습니다.</div>';
      return;
    }

    let html = '';
    similarTickets.forEach((ticket, index) => {
      // Vector DB 메타데이터 구조에 맞게 표시
      const metadata = ticket.metadata || ticket;
      const title = metadata.subject || metadata.title || `티켓 #${metadata.ticket_id}`;
      const status = metadata.status || 'Unknown';
      const priority = metadata.priority || 'Normal';
      const agentName = metadata.agent_name || 'Unassigned';
      const score = ticket.score || ticket.relevance_score || 0;
      const createdAt = metadata.created_at || metadata.created_date;

      html += `
        <div class="ticket-item" data-ticket-id="${metadata.ticket_id || index}">
          <div class="ticket-header">
            <h4 class="ticket-title">${title}</h4>
            <span class="confidence-score">${(score * 100).toFixed(1)}%</span>
          </div>
          <div class="ticket-metadata">
            <span class="status status-${status.toLowerCase()}">${status}</span>
            <span class="priority priority-${priority.toLowerCase()}">${priority}</span>
            <span class="agent">${agentName}</span>
          </div>
          ${createdAt ? `<div class="ticket-date">${new Date(createdAt).toLocaleDateString('ko-KR')}</div>` : ''}
          <div class="ticket-preview">
            ${(metadata.text || metadata.description_text || '').substring(0, 150)}...
          </div>
        </div>
      `;
    });

    resultsElement.innerHTML = html;
    console.log(`✅ Vector DB 유사 티켓 ${similarTickets.length}개 표시 완료`);
  },

  /**
   * 📚 Vector DB 기반 KB 문서 표시
   *
   * Vector DB에서 조회된 KB 문서 데이터를 UI에 표시합니다.
   *
   * @param {Array} kbDocuments - Vector DB에서 조회된 KB 문서 배열
   */
  displayKBDocuments(kbDocuments) {
    const resultsElement = document.getElementById('suggested-solutions-list');
    if (!resultsElement) {
      console.warn('⚠️ suggested-solutions-list 엘리먼트를 찾을 수 없음');
      return;
    }

    if (!kbDocuments || kbDocuments.length === 0) {
      resultsElement.innerHTML = '<div class="no-results">관련 지식베이스 문서가 없습니다.</div>';
      return;
    }

    let html = '';
    kbDocuments.forEach((doc, index) => {
      // Vector DB 메타데이터 구조에 맞게 표시
      const metadata = doc.metadata || doc;
      const title = metadata.title || `문서 #${index + 1}`;
      const category = metadata.category || 'General';
      const folder = metadata.folder || '';
      const status = metadata.status || 'published';
      const score = doc.score || doc.relevance_score || 0;
      const description = metadata.description || metadata.text || '';

      html += `
        <div class="kb-item" data-article-id="${metadata.article_id || index}">
          <div class="kb-header">
            <h4 class="kb-title">${title}</h4>
            <span class="confidence-score">${(score * 100).toFixed(1)}%</span>
          </div>
          <div class="kb-metadata">
            <span class="category">${category}</span>
            ${folder ? `<span class="folder">${folder}</span>` : ''}
            <span class="status status-${status.toLowerCase()}">${status}</span>
          </div>
          <div class="kb-description">
            ${description.substring(0, 200)}...
          </div>
          <div class="kb-actions">
            <button class="btn-view-kb" data-article-id="${metadata.article_id}">
              전체 보기
            </button>
          </div>
        </div>
      `;
    });

    resultsElement.innerHTML = html;

    // KB 문서 전체 보기 이벤트 리스너 추가
    resultsElement.querySelectorAll('.btn-view-kb').forEach(button => {
      button.addEventListener('click', (e) => {
        const articleId = e.target.getAttribute('data-article-id');
        this.showKBDocumentModal(articleId, kbDocuments);
      });
    });

    console.log(`✅ Vector DB KB 문서 ${kbDocuments.length}개 표시 완료`);
  },

  /**
   * 📖 KB 문서 상세 모달 표시
   *
   * KB 문서의 전체 내용을 모달로 표시합니다.
   *
   * @param {string} articleId - 문서 ID
   * @param {Array} kbDocuments - KB 문서 배열
   */
  showKBDocumentModal(articleId, kbDocuments) {
    const doc = kbDocuments.find(d => (d.metadata && d.metadata.article_id) === articleId);
    if (!doc) {
      console.warn('⚠️ KB 문서를 찾을 수 없음:', articleId);
      return;
    }

    const metadata = doc.metadata || doc;
    const modalHtml = `
      <div class="kb-modal-overlay" id="kb-modal">
        <div class="kb-modal-content">
          <div class="kb-modal-header">
            <h2>${metadata.title || '제목 없음'}</h2>
            <button class="kb-modal-close">&times;</button>
          </div>
          <div class="kb-modal-metadata">
            <span class="category">${metadata.category || 'General'}</span>
            ${metadata.folder ? `<span class="folder">${metadata.folder}</span>` : ''}
            <span class="status">${metadata.status || 'published'}</span>
          </div>
          <div class="kb-modal-body">
            ${metadata.description || metadata.text || '내용이 없습니다.'}
          </div>
        </div>
      </div>
    `;

    // 모달 HTML 추가
    document.body.insertAdjacentHTML('beforeend', modalHtml);

    // 모달 닫기 이벤트
    const modal = document.getElementById('kb-modal');
    const closeBtn = modal.querySelector('.kb-modal-close');
    
    const closeModal = () => modal.remove();
    
    closeBtn.addEventListener('click', closeModal);
    modal.addEventListener('click', (e) => {
      if (e.target === modal) closeModal();
    });

    console.log(`📖 KB 문서 모달 표시: ${metadata.title}`);
  },

  /**
   * 티켓 페이지에서 벗어날 때 데이터 초기화
   *
   * 사용자가 티켓 페이지를 떠날 때 데이터를 초기화하여
   * 다음 번에 페이지에 들어왔을 때 새로운 데이터로 로드되도록 합니다.
   *
   * @example
   * Data.resetDataOnTicketPageExit();
   */
  resetDataOnTicketPageExit() {
    console.log('🔄 티켓 페이지 이탈 감지 → 데이터 초기화');

    // 전역 상태 리셋
    GlobalState.resetGlobalTicketCache();

    // 추가적인 클린업 작업 수행 가능
    // 예: 구독 중인 이벤트 해제, 타이머 정리 등
  },

  /**
   * 데이터 압축 및 최적화
   */
  compressTicketData(tickets) {
    // 불필요한 필드 제거 및 데이터 압축
    return tickets.map((ticket) => ({
      id: ticket.id,
      s: ticket.subject,
      d: this.truncateText(ticket.description, 200),
      st: ticket.status,
      p: ticket.priority,
      ca: ticket.created_at,
      ua: ticket.updated_at,
      t: ticket.tags.slice(0, 5), // 최대 5개 태그만
      us: ticket.urgency_score,
    }));
  },

  /**
   * 압축된 데이터 복원
   */
  decompressTicketData(compressedTickets) {
    return compressedTickets.map((ticket) => ({
      id: ticket.id,
      subject: ticket.s,
      description: ticket.d,
      status: ticket.st,
      priority: ticket.p,
      created_at: ticket.ca,
      updated_at: ticket.ua,
      tags: ticket.t,
      urgency_score: ticket.us,
    }));
  },

  /**
   * 유틸리티 함수들
   */
  sanitizeText(text) {
    return text
      .replace(/<[^>]*>/g, '')
      .replace(/\s+/g, ' ')
      .trim();
  },

  truncateText(text, maxLength) {
    return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
  },

  normalizeStatus(status) {
    const statusMap = {
      2: 'open',
      3: 'pending',
      4: 'resolved',
      5: 'closed',
    };
    return statusMap[status] || 'unknown';
  },

  normalizePriority(priority) {
    const priorityMap = {
      1: 'low',
      2: 'medium',
      3: 'high',
      4: 'urgent',
    };
    return priorityMap[priority] || 'medium';
  },

  parseDate(dateString) {
    try {
      return new Date(dateString).toISOString();
    } catch {
      return new Date().toISOString();
    }
  },

  extractTags(tags) {
    return Array.isArray(tags) ? tags.filter((tag) => tag && tag.length > 0) : [];
  },

  categorizeTicket(ticket) {
    // 간단한 카테고리 분류 로직
    const subject = (ticket.subject || '').toLowerCase();
    if (subject.includes('bug') || subject.includes('error')) return 'bug';
    if (subject.includes('feature') || subject.includes('request')) return 'feature';
    if (subject.includes('question') || subject.includes('help')) return 'support';
    return 'general';
  },

  calculateUrgencyScore(ticket) {
    let score = 0;
    if (ticket.priority === 4) score += 40; // urgent
    if (ticket.priority === 3) score += 20; // high
    if (ticket.status === 2) score += 10; // open
    // 생성 후 24시간 이내면 추가 점수
    const hoursOld = (Date.now() - new Date(ticket.created_at)) / (1000 * 60 * 60);
    if (hoursOld < 24) score += 15;
    return Math.min(100, score);
  },

  createFallbackTicket(ticket) {
    return {
      id: ticket.id || 'unknown',
      subject: '데이터 오류',
      description: '티켓 데이터를 처리할 수 없습니다.',
      status: 'unknown',
      priority: 'medium',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      tags: [],
      category: 'error',
      urgency_score: 0,
    };
  },

  /**
   * 캐시된 데이터가 오래되었는지 확인
   *
   * 전역 상태에 저장된 데이터의 최종 업데이트 시간을 확인하여
   * 데이터가 오래되었는지 판단합니다.
   *
   * @returns {boolean} 데이터가 오래되었으면 true, 아니면 false
   */
  isDataStale() {
    try {
      const globalData = GlobalState.getGlobalTicketData();
      
      if (!globalData.last_updated) {
        return true; // 업데이트 시간이 없으면 오래된 데이터로 간주
      }
      
      const lastUpdated = new Date(globalData.last_updated);
      const now = new Date();
      const diffInMinutes = (now - lastUpdated) / (1000 * 60);
      
      // 10분이 지나면 오래된 데이터로 간주
      return diffInMinutes > 10;
    } catch (error) {
      console.warn('[Data] 데이터 유효성 확인 중 오류:', error);
      return true; // 오류 발생 시 오래된 데이터로 간주
    }
  },

  /**
   * 업데이트 확인 (실제 구현에서는 API 호출)
   */
  async checkForUpdates() {
    // 실제로는 서버에 업데이트 확인 요청
    // 여기서는 랜덤으로 시뮬레이션
    return await Promise.resolve(Math.random() < 0.1); // 10% 확률로 업데이트 있음
  },

  /**
   * 🔧 UI 렌더링 유틸리티 함수들
   */

  /**
   * 텍스트 길이 제한
   * @param {string} text - 원본 텍스트
   * @param {number} maxLength - 최대 길이
   * @returns {string} 제한된 텍스트
   */
  truncateText(text, maxLength) {
    if (!text || text.length <= maxLength) return text;
    return text.substring(0, maxLength) + '...';
  },

  /**
   * 마크다운을 간단한 HTML로 변환
   * @param {string} markdown - 마크다운 텍스트
   * @returns {string} 변환된 HTML
   */
  convertMarkdownToHTML(markdown) {
    if (!markdown) return '';
    
    return markdown
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')  // **bold**
      .replace(/\*(.*?)\*/g, '<em>$1</em>')              // *italic*
      .replace(/`(.*?)`/g, '<code>$1</code>')            // `code`
      .replace(/^## (.*$)/gim, '<h2>$1</h2>')            // ## heading
      .replace(/^### (.*$)/gim, '<h3>$1</h3>')           // ### heading
      .replace(/^\* (.*$)/gim, '<li>$1</li>')            // * list
      .replace(/^- (.*$)/gim, '<li>$1</li>')             // - list
      .replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>')         // wrap lists
      .replace(/\n/g, '<br>');                           // line breaks
  },

  /**
   * 탭 카운트 업데이트
   * @param {string} tabName - 탭 이름
   * @param {number} count - 카운트 수
   */
  updateTabCount(tabName, count) {
    const tabButton = document.querySelector(`[data-tab="${tabName}"]`);
    if (tabButton) {
      const countElement = tabButton.querySelector('.tab-count');
      if (countElement) {
        countElement.textContent = count;
      }
    }
  },

  /**
   * 로딩 상태 해제 및 콘텐츠 표시
   */
  hideLoadingAndShowContent() {
    // 로딩 오버레이 숨기기
    const loadingOverlay = document.querySelector('.loading-overlay');
    if (loadingOverlay) {
      loadingOverlay.style.display = 'none';
    }
    
    // 메인 콘텐츠 표시
    const mainContent = document.querySelector('.main-content');
    if (mainContent) {
      mainContent.style.opacity = '1';
    }
    
    // 탭 네비게이션 활성화
    const tabNavigation = document.querySelector('.tab-navigation');
    if (tabNavigation) {
      tabNavigation.style.pointerEvents = 'auto';
    }
  },

  /**
   * 🎫 티켓 상호작용 함수들
   */

  /**
   * 티켓 요약 보기
   * @param {string} ticketId - 티켓 ID
   */
  viewTicketSummary(ticketId) {
    try {
      console.log(`🔍 티켓 요약 보기: ${ticketId}`);
      
      // 전역 상태에서 해당 티켓 찾기
      const globalData = window.GlobalState.getGlobalTicketData();
      const ticket = globalData.similar_tickets?.find(t => t.id == ticketId || t.ticket_id == ticketId);
      
      if (ticket && ticket.ai_summary) {
        this.showSummaryModal(ticket);
      } else {
        console.warn('📝 티켓 요약을 찾을 수 없음, 원본 보기로 대체');
        this.viewTicketOriginal(ticketId);
      }
    } catch (error) {
      console.error('❌ 티켓 요약 보기 실패:', error);
    }
  },

  /**
   * 티켓 원본 보기 (새 탭)
   * @param {string} ticketId - 티켓 ID
   */
  viewTicketOriginal(ticketId) {
    try {
      console.log(`📄 티켓 원본 보기: ${ticketId}`);
      
      // Freshdesk 티켓 URL 생성 및 새 탭에서 열기
      const ticketUrl = `https://wedosoft.freshdesk.com/a/tickets/${ticketId}`;
      window.open(ticketUrl, '_blank', 'noopener,noreferrer');
    } catch (error) {
      console.error('❌ 티켓 원본 보기 실패:', error);
    }
  },

  /**
   * KB 문서 원본 보기 (새 탭)
   * @param {string} kbId - KB 문서 ID
   */
  viewKBOriginal(kbId) {
    try {
      console.log(`📚 KB 문서 원본 보기: ${kbId}`);
      
      // 전역 상태에서 해당 KB 문서 찾기
      const globalData = window.GlobalState.getGlobalTicketData();
      const kbDoc = globalData.kb_documents?.find(doc => doc.id == kbId || doc.article_id == kbId);
      
      if (kbDoc && kbDoc.source_url) {
        window.open(kbDoc.source_url, '_blank', 'noopener,noreferrer');
      } else {
        // source_url이 없으면 기본 KB URL 생성
        const kbUrl = `https://wedosoft.freshdesk.com/support/solutions/articles/${kbId}`;
        window.open(kbUrl, '_blank', 'noopener,noreferrer');
      }
    } catch (error) {
      console.error('❌ KB 문서 원본 보기 실패:', error);
    }
  },

  /**
   * 📚 KB 문서 요약 보기
   * @param {string} kbId - KB 문서 ID
   */
  viewKBSummary(kbId) {
    try {
      console.log(`👁️ KB 문서 상세 보기: ${kbId}`);
      
      // 글로벌 상태에서 KB 문서 찾기
      const globalData = window.GlobalState?.getGlobalTicketData() || {};
      const kbDocuments = globalData.kb_documents || [];
      
      const kbDoc = kbDocuments.find(doc => 
        doc.id === kbId || doc.id === String(kbId)
      );
      
      if (kbDoc) {
        // 콘텐츠 길이에 따른 처리 방식 결정
        const content = kbDoc.content || kbDoc.description || '';
        
        if (content.length > 300) {
          // 긴 콘텐츠: 모달에서 스마트 요약 표시
          this.showKBDetailModal(kbDoc, 'smart');
        } else if (content.length > 50) {
          // 중간 콘텐츠: 전체 내용 표시
          this.showKBDetailModal(kbDoc, 'full');
        } else {
          // 짧은 콘텐츠: 원본으로 바로 이동
          console.log('📝 짧은 콘텐츠 → 원본으로 이동');
          this.viewKBOriginal(kbId);
        }
      } else {
        console.warn(`⚠️ KB 문서를 찾을 수 없음: ${kbId}`);
        // 폴백: 원본 보기로 이동
        this.viewKBOriginal(kbId);
      }
    } catch (error) {
      console.error('❌ KB 문서 상세 보기 실패:', error);
    }
  },

  /**
   * 요약 모달 표시
   * @param {Object} ticket - 티켓 데이터
   */
  showSummaryModal(ticket) {
    // 간단한 모달 생성
    const modal = document.createElement('div');
    modal.className = 'summary-modal';
    modal.style.cssText = `
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background: rgba(0, 0, 0, 0.5);
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 1000;
      padding: 20px;
    `;
    
    const modalContent = document.createElement('div');
    modalContent.style.cssText = `
      background: white;
      border-radius: 12px;
      padding: 24px;
      max-width: 600px;
      max-height: 80vh;
      overflow-y: auto;
      position: relative;
    `;
    
    modalContent.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
        <h3 style="margin: 0; color: #1f2937;">티켓 #${ticket.id} 요약</h3>
        <button onclick="this.closest('.summary-modal').remove()" 
                style="background: none; border: none; font-size: 24px; cursor: pointer; color: #6b7280;">
          ×
        </button>
      </div>
      <div style="color: #374151; line-height: 1.6;">
        ${this.convertMarkdownToHTML(ticket.ai_summary)}
      </div>
      <div style="margin-top: 16px; padding-top: 16px; border-top: 1px solid #e5e7eb;">
        <button onclick="Data.viewTicketOriginal('${ticket.id}')" 
                style="background: #8B5CF6; color: white; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; margin-right: 8px;">
          📄 원본 보기
        </button>
        <button onclick="this.closest('.summary-modal').remove()" 
                style="background: #6b7280; color: white; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer;">
          닫기
        </button>
      </div>
    `;
    
    modal.appendChild(modalContent);
    document.body.appendChild(modal);
    
    // 모달 외부 클릭 시 닫기
    modal.addEventListener('click', (e) => {
      if (e.target === modal) {
        modal.remove();
      }
    });
  },

  /**
   * 📚 KB 문서 상세 모달 표시 (개선된 버전)
   * @param {Object} kbDoc - KB 문서 데이터
   * @param {string} mode - 표시 모드 ('smart', 'full', 'summary')
   */
  showKBDetailModal(kbDoc, mode = 'smart') {
    const modal = document.createElement('div');
    modal.className = 'kb-detail-modal';
    modal.style.cssText = `
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background: rgba(0, 0, 0, 0.5);
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 1000;
      padding: 20px;
    `;

    const content = kbDoc.content || kbDoc.description || '내용을 불러올 수 없습니다.';
    let displayContent = '';
    let modeLabel = '';

    // 모드에 따른 콘텐츠 처리
    switch (mode) {
      case 'smart':
        displayContent = this.createSmartSummary(content);
        modeLabel = '🤖 스마트 요약';
        break;
      case 'full':
        displayContent = this.convertMarkdownToHTML(content);
        modeLabel = '📄 전체 내용';
        break;
      default:
        displayContent = this.convertMarkdownToHTML(content);
        modeLabel = '📄 내용';
    }

    modal.innerHTML = `
      <div style="
        background: white;
        border-radius: 8px;
        padding: 24px;
        max-width: 700px;
        max-height: 85vh;
        overflow-y: auto;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
        position: relative;
      ">
        <div style="
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          margin-bottom: 16px;
          padding-bottom: 16px;
          border-bottom: 1px solid #e5e7eb;
        ">
          <div style="flex: 1;">
            <h3 style="margin: 0; color: #1f2937; font-size: 20px; font-weight: 600; line-height: 1.3;">
              📚 ${kbDoc.title || '제목 없음'}
            </h3>
            <div style="margin-top: 6px; font-size: 13px; color: #6b7280;">
              ${modeLabel}
              ${kbDoc.category ? ` • 📂 ${kbDoc.category}` : ''}
              ${kbDoc.status ? ` • ${kbDoc.status}` : ''}
            </div>
            ${content.length > 300 && mode === 'smart' ? `
              <div style="margin-top: 8px;">
                <button onclick="Data.showKBDetailModal(${JSON.stringify(kbDoc).replace(/"/g, '&quot;')}, 'full')" 
                        style="
                          background: #f3f4f6;
                          border: 1px solid #d1d5db;
                          border-radius: 4px;
                          padding: 4px 8px;
                          cursor: pointer;
                          font-size: 12px;
                          color: #374151;
                        ">📖 전체 내용 보기</button>
              </div>
            ` : ''}
          </div>
          <button onclick="this.closest('.kb-detail-modal').remove()" 
                  style="
                    background: #f3f4f6;
                    border: none;
                    border-radius: 4px;
                    padding: 8px;
                    cursor: pointer;
                    font-size: 18px;
                    color: #6b7280;
                    line-height: 1;
                    margin-left: 12px;
                  ">×</button>
        </div>
        
        <div style="
          line-height: 1.6;
          color: #374151;
          margin-bottom: 20px;
          font-size: 14px;
          max-height: 50vh;
          overflow-y: auto;
        ">${displayContent}</div>
        
        <div style="
          display: flex;
          gap: 12px;
          justify-content: flex-end;
          padding-top: 16px;
          border-top: 1px solid #e5e7eb;
        ">
          <button onclick="Data.viewKBOriginal('${kbDoc.id}')" 
                  style="
                    background: #3b82f6;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 8px 16px;
                    cursor: pointer;
                    font-size: 14px;
                    font-weight: 500;
                  ">🔗 원본에서 열기</button>
          <button onclick="this.closest('.kb-detail-modal').remove()" 
                  style="
                    background: #6b7280;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 8px 16px;
                    cursor: pointer;
                    font-size: 14px;
                    font-weight: 500;
                  ">닫기</button>
        </div>
      </div>
    `;

    document.body.appendChild(modal);

    // 모달 배경 클릭시 닫기
    modal.addEventListener('click', (e) => {
      if (e.target === modal) {
        modal.remove();
      }
    });
  },

  /**
   * 📚 KB 문서 요약 모달 표시 (기존 함수 - 호환성 유지)
   * @param {Object} kbDoc - KB 문서 데이터
   */
  showKBSummaryModal(kbDoc) {
    // KB 문서 요약 모달 생성
    const modal = document.createElement('div');
    modal.className = 'kb-summary-modal';
    modal.style.cssText = `
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background: rgba(0, 0, 0, 0.5);
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 1000;
      padding: 20px;
    `;

    const content = kbDoc.content || kbDoc.description || '내용을 불러올 수 없습니다.';
    const htmlContent = this.convertMarkdownToHTML(content);

    modal.innerHTML = `
      <div style="
        background: white;
        border-radius: 8px;
        padding: 24px;
        max-width: 600px;
        max-height: 80vh;
        overflow-y: auto;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
      ">
        <div style="
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 16px;
          padding-bottom: 16px;
          border-bottom: 1px solid #e5e7eb;
        ">
          <div>
            <h3 style="margin: 0; color: #1f2937; font-size: 20px; font-weight: 600;">
              📚 ${kbDoc.title || '제목 없음'}
            </h3>
            <div style="margin-top: 4px; font-size: 14px; color: #6b7280;">
              ${kbDoc.category ? `📂 ${kbDoc.category}` : ''}
              ${kbDoc.status ? `• ${kbDoc.status}` : ''}
            </div>
          </div>
          <button onclick="this.closest('.kb-summary-modal').remove()" 
                  style="
                    background: #f3f4f6;
                    border: none;
                    border-radius: 4px;
                    padding: 8px;
                    cursor: pointer;
                    font-size: 18px;
                    color: #6b7280;
                    line-height: 1;
                  ">×</button>
        </div>
        
        <div style="
          line-height: 1.6;
          color: #374151;
          margin-bottom: 20px;
          font-size: 14px;
        ">${htmlContent}</div>
        
        <div style="
          display: flex;
          gap: 12px;
          justify-content: flex-end;
          padding-top: 16px;
          border-top: 1px solid #e5e7eb;
        ">
          <button onclick="Data.viewKBOriginal('${kbDoc.id}')" 
                  style="
                    background: #3b82f6;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 8px 16px;
                    cursor: pointer;
                    font-size: 14px;
                    font-weight: 500;
                  ">📄 원본보기</button>
          <button onclick="this.closest('.kb-summary-modal').remove()" 
                  style="
                    background: #6b7280;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 8px 16px;
                    cursor: pointer;
                    font-size: 14px;
                    font-weight: 500;
                  ">닫기</button>
        </div>
      </div>
    `;

    document.body.appendChild(modal);

    // 모달 배경 클릭시 닫기
    modal.addEventListener('click', (e) => {
      if (e.target === modal) {
        modal.remove();
      }
    });
  },

  /**
   * 🤖 스마트 요약 생성 (클라이언트 사이드)
   * @param {string} content - 원본 콘텐츠
   * @returns {string} 요약된 HTML
   */
  createSmartSummary(content) {
    try {
      // 1. 마크다운을 일반 텍스트로 변환
      const plainText = content
        .replace(/#{1,6}\s+/g, '') // 헤더 제거
        .replace(/\*\*(.*?)\*\*/g, '$1') // 볼드 제거
        .replace(/\*(.*?)\*/g, '$1') // 이탤릭 제거
        .replace(/`(.*?)`/g, '$1') // 인라인 코드 제거
        .replace(/\[(.*?)\]\(.*?\)/g, '$1') // 링크 제거
        .replace(/\n+/g, ' ') // 줄바꿈을 공백으로
        .trim();

      // 2. 문장 단위로 분리
      const sentences = plainText.split(/[.!?]/).filter(s => s.trim().length > 10);
      
      // 3. 중요한 문장 선별 (키워드 기반)
      const importantKeywords = ['해결', '방법', '단계', '설정', '확인', '문제', '오류', '설치', '업데이트'];
      const scoredSentences = sentences.map(sentence => {
        const score = importantKeywords.reduce((acc, keyword) => {
          return acc + (sentence.includes(keyword) ? 1 : 0);
        }, 0);
        return { sentence: sentence.trim(), score };
      });

      // 4. 상위 3-4개 문장 선택
      const topSentences = scoredSentences
        .sort((a, b) => b.score - a.score)
        .slice(0, 4)
        .map(item => item.sentence)
        .filter(s => s.length > 0);

      // 5. HTML 형태로 변환
      if (topSentences.length > 0) {
        return `
          <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 12px; margin-bottom: 12px;">
            <div style="font-size: 12px; color: #64748b; margin-bottom: 8px;">🤖 AI 요약</div>
            <ul style="margin: 0; padding-left: 20px; color: #334155;">
              ${topSentences.map(sentence => `<li style="margin-bottom: 4px;">${sentence}.</li>`).join('')}
            </ul>
          </div>
          <div style="font-size: 13px; color: #64748b; font-style: italic;">
            💡 전체 내용을 보려면 "전체 내용 보기" 버튼을 클릭하세요.
          </div>
        `;
      } else {
        // 요약 실패 시 처음 300자만 표시
        const preview = plainText.length > 300 ? plainText.substring(0, 300) + '...' : plainText;
        return `
          <div style="line-height: 1.5;">${preview}</div>
          ${plainText.length > 300 ? '<div style="font-size: 13px; color: #64748b; margin-top: 8px; font-style: italic;">💡 전체 내용을 보려면 "전체 내용 보기" 버튼을 클릭하세요.</div>' : ''}
        `;
      }
    } catch (error) {
      console.error('❌ 스마트 요약 생성 실패:', error);
      // 폴백: 처음 200자만 표시
      const fallback = content.length > 200 ? content.substring(0, 200) + '...' : content;
      return `<div>${this.convertMarkdownToHTML(fallback)}</div>`;
    }
  },
};

// Data 모듈 export - 주요 함수들을 Data 네임스페이스로 노출
// (이미 Data 객체 내부에 정의되어 있으므로 별도 할당 불필요)

// 의존성 확인 함수 - 다른 모듈에서 Data 모듈 사용 가능 여부 체크
Data.isAvailable = function () {
  const hasGlobalState = typeof GlobalState !== 'undefined';
  
  // API 모듈은 선택적 의존성으로 처리 (없어도 기본 기능 동작 가능)
  const hasAPI = typeof window.API !== 'undefined' && window.API !== null;
  
  if (!hasAPI) {
    console.warn("Data: API 모듈을 찾을 수 없습니다.");
  }
  
  return hasGlobalState && hasAPI;
};

// Data 모듈 등록은 파일 끝에서 처리됨

// 모듈 의존성 시스템에 등록 (API 모듈 로드 대기)
setTimeout(() => {
  if (typeof ModuleDependencyManager !== 'undefined') {
    ModuleDependencyManager.registerModule('data', Object.keys(Data).length, ['globals', 'utils', 'api']);
  }
}, 100);
