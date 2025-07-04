/**
 * 모달 데이터 렌더링 수정
 * 
 * 문제: 모달창에서 백엔드 데이터가 표시되지 않음
 * 원인: EventAPI 접근 불가 및 데이터 로드 타이밍 문제
 * 해결: 안전한 데이터 로드 및 렌더링 로직 구현
 */

// 모달 전용 데이터 렌더링 함수
window.ModalDataRenderer = {
  /**
   * 안전한 모달 데이터 렌더링
   */
  renderModalData: function() {
    console.log('🎯 모달 데이터 렌더링 시작');
    
    // GlobalState에서 캐시된 데이터 가져오기
    if (!window.GlobalState) {
      console.error('❌ GlobalState가 없음');
      this.showFallbackUI();
      return;
    }
    
    const globalData = window.GlobalState.getGlobalTicketData();
    console.log('📊 캐시된 데이터:', {
      hasData: !!globalData,
      hasSummary: !!globalData?.summary,
      hasTicketInfo: !!globalData?.ticket_info,
      similarTicketsCount: globalData?.similar_tickets?.length || 0,
      kbDocumentsCount: globalData?.kb_documents?.length || 0
    });
    
    // 데이터가 없으면 백엔드에서 로드 시도
    if (!this.hasValidData(globalData)) {
      console.log('📡 캐시된 데이터 없음 - 백엔드에서 로드 시도');
      this.loadFromBackend();
      return;
    }
    
    // 데이터 렌더링
    this.updateUI(globalData);
  },
  
  /**
   * 데이터 유효성 검사
   */
  hasValidData: function(data) {
    return data && (
      data.summary || 
      data.ticket_info || 
      (data.similar_tickets && data.similar_tickets.length > 0) ||
      (data.kb_documents && data.kb_documents.length > 0)
    );
  },
  
  /**
   * UI 업데이트
   */
  updateUI: function(data) {
    console.log('🎨 UI 업데이트 시작');
    
    // 티켓 정보 업데이트
    if (data.ticket_info) {
      this.updateTicketInfo(data.ticket_info);
    }
    
    // 요약 정보 업데이트
    if (data.summary) {
      this.updateSummary(data.summary);
    }
    
    // 유사 티켓 업데이트
    if (data.similar_tickets && data.similar_tickets.length > 0) {
      this.updateSimilarTickets(data.similar_tickets);
    }
    
    // KB 문서 업데이트
    if (data.kb_documents && data.kb_documents.length > 0) {
      this.updateKbDocuments(data.kb_documents);
    }
    
    console.log('✅ UI 업데이트 완료');
  },
  
  /**
   * 티켓 정보 업데이트
   */
  updateTicketInfo: function(ticketInfo) {
    const elements = {
      'ticket-subject': ticketInfo.subject || ticketInfo.title || 'No Subject',
      'ticket-status': ticketInfo.status || 'Unknown',
      'ticket-priority': ticketInfo.priority || 'Medium',
      'ticket-type': ticketInfo.type || 'General'
    };
    
    for (const [id, value] of Object.entries(elements)) {
      const el = document.getElementById(id);
      if (el) {
        el.textContent = value;
        el.classList.remove('loading');
      }
    }
  },
  
  /**
   * 요약 정보 업데이트
   */
  updateSummary: function(summary) {
    // 첫 번째 탭에 요약 표시
    const placeholders = document.querySelectorAll('.placeholder-text');
    if (placeholders.length > 0) {
      placeholders[0].innerHTML = `
        <div class="alert alert-info">
          <h6>📋 AI 티켓 요약</h6>
          <div style="white-space: pre-wrap;">${summary}</div>
        </div>
      `;
    }
  },
  
  /**
   * 유사 티켓 업데이트
   */
  updateSimilarTickets: function(tickets) {
    const container = document.getElementById('similar-tickets-list');
    if (!container) return;
    
    container.innerHTML = tickets.map(ticket => `
      <div class="list-item">
        <div class="list-item-header">
          <div class="list-item-title">${ticket.subject || ticket.title || 'No Subject'}</div>
          <span class="score-badge">${Math.round((ticket.score || 0) * 100)}%</span>
        </div>
        <div class="list-item-meta">
          ID: ${ticket.id} | Status: ${ticket.status || 'Unknown'}
        </div>
      </div>
    `).join('');
  },
  
  /**
   * KB 문서 업데이트
   */
  updateKbDocuments: function(documents) {
    const container = document.getElementById('suggested-solutions-list');
    if (!container) return;
    
    container.innerHTML = documents.map(doc => `
      <div class="list-item solution-card">
        <div class="list-item-header">
          <div class="list-item-title">${doc.title || 'No Title'}</div>
          <span class="score-badge">${Math.round((doc.score || 0) * 100)}%</span>
        </div>
        <div class="list-item-excerpt">
          ${doc.description || doc.content || '내용 없음'}
        </div>
      </div>
    `).join('');
  },
  
  /**
   * 백엔드에서 데이터 로드
   */
  loadFromBackend: async function() {
    console.log('🔄 백엔드에서 데이터 로드 시도');
    
    // 티켓 ID 가져오기
    const ticketId = this.getTicketId();
    if (!ticketId) {
      console.error('❌ 티켓 ID를 찾을 수 없음');
      this.showFallbackUI();
      return;
    }
    
    // 로딩 UI 표시
    this.showLoadingUI();
    
    try {
      // 백엔드 URL 구성
      const backendUrl = window.iparams?.backendUrl || 'http://localhost:8000';
      const response = await fetch(`${backendUrl}/api/init/${ticketId}`, {
        headers: {
          'X-Tenant-ID': window.iparams?.tenantId || 'default',
          'X-Platform': 'freshdesk'
        }
      });
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const data = await response.json();
      
      // GlobalState에 저장
      if (window.GlobalState) {
        window.GlobalState.updateTicketData(data);
      }
      
      // UI 업데이트
      this.updateUI(data);
      
    } catch (error) {
      console.error('❌ 백엔드 로드 실패:', error);
      this.showFallbackUI();
    }
  },
  
  /**
   * 티켓 ID 가져오기
   */
  getTicketId: function() {
    // URL에서 티켓 ID 추출
    const urlParams = new URLSearchParams(window.location.search);
    const ticketId = urlParams.get('ticket_id');
    
    if (ticketId) return ticketId;
    
    // GlobalState에서 가져오기
    if (window.GlobalState) {
      const globalData = window.GlobalState.getGlobalTicketData();
      if (globalData.cached_ticket_id) {
        return globalData.cached_ticket_id;
      }
    }
    
    return null;
  },
  
  /**
   * 로딩 UI 표시
   */
  showLoadingUI: function() {
    const loadingHTML = `
      <div class="text-center py-4">
        <div class="spinner-border text-primary" role="status">
          <span class="visually-hidden">Loading...</span>
        </div>
        <p class="mt-2">데이터를 불러오는 중...</p>
      </div>
    `;
    
    document.querySelectorAll('.placeholder-text').forEach(el => {
      el.innerHTML = loadingHTML;
    });
  },
  
  /**
   * 폴백 UI 표시
   */
  showFallbackUI: function() {
    const fallbackHTML = `
      <div class="alert alert-warning">
        <h6>⚠️ 데이터를 불러올 수 없습니다</h6>
        <p>잠시 후 다시 시도해 주세요.</p>
        <button class="btn btn-sm btn-primary" onclick="ModalDataRenderer.renderModalData()">
          다시 시도
        </button>
      </div>
    `;
    
    document.querySelectorAll('.placeholder-text').forEach(el => {
      el.innerHTML = fallbackHTML;
    });
  }
};

// 모달이 열릴 때 자동으로 데이터 렌더링
if (window.isFDKModal) {
  console.log('🎭 모달 컨텍스트 감지 - 데이터 렌더링 준비');
  
  // DOM이 준비되면 렌더링 시작
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      setTimeout(() => {
        ModalDataRenderer.renderModalData();
      }, 500);
    });
  } else {
    setTimeout(() => {
      ModalDataRenderer.renderModalData();
    }, 500);
  }
}