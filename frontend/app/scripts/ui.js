/**
 * ui.js
 * UI 컴포넌트 생성 및 렌더링 함수
 * 화면에 표시되는 요소들의 생성, 업데이트, 이벤트 처리 함수들이 포함됩니다.
 */

// utils.js에서 필요한 함수들 (변수 중복 방지를 위해 직접 참조)

/**
 * 로딩 인디케이터 표시 함수
 */
function showLoadingIndicator() {
  console.log("⏳ 로딩 인디케이터 표시");

  // 기존 로딩 인디케이터가 있으면 제거
  hideLoadingIndicator();

  // 로딩 오버레이 생성
  const loadingOverlay = document.createElement("div");
  loadingOverlay.id = "loading-overlay";
  loadingOverlay.innerHTML = `
    <div class="loading-backdrop">
      <div class="loading-spinner">
        <div class="spinner"></div>
        <div class="loading-text">데이터를 불러오는 중...</div>
      </div>
    </div>
  `;

  // 로딩 오버레이를 body에 추가
  document.body.appendChild(loadingOverlay);
}

/**
 * 로딩 인디케이터 숨기기 함수
 */
function hideLoadingIndicator() {
  const existingOverlay = document.getElementById("loading-overlay");
  if (existingOverlay) {
    existingOverlay.remove();
  }
}

/**
 * 간단한 로딩 인디케이터 표시
 */
function showQuickLoadingIndicator() {
  console.log("⏳ 간단한 로딩 인디케이터 표시");

  // 기존 로딩 인디케이터가 있으면 제거
  hideQuickLoadingIndicator();

  // 로딩 오버레이 생성
  const loadingOverlay = document.createElement("div");
  loadingOverlay.id = "quick-loading-overlay";
  loadingOverlay.innerHTML = `
    <div class="loading-backdrop">
      <div class="loading-spinner">
        <div class="spinner"></div>
        <div class="loading-text">데이터를 불러오는 중...</div>
      </div>
    </div>
  `;

  // 로딩 오버레이를 body에 추가
  document.body.appendChild(loadingOverlay);
}

/**
 * 간단한 로딩 인디케이터 숨기기
 */
function hideQuickLoadingIndicator() {
  const existingOverlay = document.getElementById("quick-loading-overlay");
  if (existingOverlay) {
    existingOverlay.remove();
  }
}

/**
 * 알림 메시지 표시 함수
 * @param {string} message - 표시할 메시지 
 * @param {string} type - 알림 타입 ('success', 'error', 'warning', 'info')
 * @param {number} duration - 표시 시간 (밀리초)
 */
function showNotification(message, type = 'info', duration = 3000) {
  // 기존 알림 컨테이너 찾기 또는 생성
  let notificationContainer = document.getElementById('notification-container');
  
  if (!notificationContainer) {
    notificationContainer = document.createElement('div');
    notificationContainer.id = 'notification-container';
    document.body.appendChild(notificationContainer);
  }
  
  // 새 알림 요소 생성
  const notification = document.createElement('div');
  notification.className = `notification notification-${type}`;
  notification.innerHTML = `
    <div class="notification-content">
      <span class="notification-icon">
        ${type === 'success' ? '✅' : type === 'error' ? '❌' : type === 'warning' ? '⚠️' : 'ℹ️'}
      </span>
      <span class="notification-message">${message}</span>
    </div>
  `;
  
  // 알림 컨테이너에 추가
  notificationContainer.appendChild(notification);
  
  // 애니메이션 효과
  setTimeout(() => {
    notification.classList.add('show');
  }, 10);
  
  // 지정된 시간 후 알림 제거
  setTimeout(() => {
    notification.classList.remove('show');
    setTimeout(() => {
      notification.remove();
    }, 300); // 페이드아웃 애니메이션 시간
  }, duration);
}

/**
 * 에러 메시지 표시 함수
 * @param {string} message - 에러 메시지 
 * @param {Error} error - 에러 객체 (선택사항)
 */
function showError(message, error = null) {
  console.error(`❌ ${message}`, error);
  
  // 에러 메시지 표시
  showNotification(message, 'error', 5000);
}

/**
 * 탭 전환 함수
 * @param {string} tabId - 활성화할 탭 ID
 */
function switchTab(tabId) {
  // 모든 탭 컨텐츠 숨기기
  const tabContents = document.querySelectorAll('.tab-content');
  tabContents.forEach(tab => {
    tab.classList.remove('active');
  });
  
  // 모든 탭 버튼 비활성화
  const tabButtons = document.querySelectorAll('.tab-button');
  tabButtons.forEach(button => {
    button.classList.remove('active');
  });
  
  // 선택한 탭 컨텐츠 및 버튼 활성화
  document.getElementById(tabId).classList.add('active');
  document.querySelector(`[data-tab="${tabId}"]`).classList.add('active');
}

/**
 * 티켓 요약 카드 렌더링 함수
 * @param {Object} summary - 티켓 요약 데이터
 * @param {HTMLElement} container - 요약 카드를 렌더링할 컨테이너
 */
function renderTicketSummary(summary, container) {
  if (!summary || !container) return;
  
  console.log("🖥️ 티켓 요약 렌더링:", summary);
  
  container.innerHTML = `
    <div class="ticket-summary-card">
      <div class="ticket-summary-header">
        <h3>티켓 요약</h3>
      </div>
      <div class="ticket-summary-content">
        <p>${summary}</p>
      </div>
    </div>
  `;
}

/**
 * 유사 티켓 목록 렌더링 함수
 * @param {Array} tickets - 유사 티켓 배열
 * @param {HTMLElement} container - 유사 티켓을 렌더링할 컨테이너
 */
function renderSimilarTickets(tickets, container) {
  if (!tickets || !container) return;
  
  console.log("🖥️ 유사 티켓 렌더링:", tickets);
  
  // 유사 티켓이 없을 경우
  if (tickets.length === 0) {
    container.innerHTML = `
      <div class="no-results">
        <p>유사한 티켓을 찾을 수 없습니다.</p>
      </div>
    `;
    return;
  }
  
  // 유사 티켓 목록 렌더링
  const ticketsHtml = tickets.map(ticket => `
    <div class="similar-ticket-card" data-ticket-id="${ticket.id || ''}">
      <div class="ticket-header">
        <div class="ticket-title">${window.utils?.truncateText ? window.utils.truncateText(ticket.subject || '제목 없음', 70) : (ticket.subject || '제목 없음')}</div>
        <div class="ticket-meta">
          <span class="ticket-status ${getStatusClass(ticket.status)}">${getStatusText(ticket.status)}</span>
          <span class="ticket-priority ${getPriorityClass(ticket.priority)}">${getPriorityText(ticket.priority)}</span>
        </div>
      </div>
      <div class="ticket-content">
        <div class="ticket-description">${formatDescription(ticket.description || '')}</div>
      </div>
      <div class="ticket-footer">
        <div class="ticket-created">${window.utils?.formatDate ? window.utils.formatDate(ticket.created_at) : (ticket.created_at || '')}</div>
        <button class="btn btn-sm btn-view-details" data-ticket-id="${ticket.id || ''}">상세 보기</button>
        <button class="btn btn-sm btn-use-solution" data-ticket-id="${ticket.id || ''}">답변 사용</button>
      </div>
    </div>
  `).join('');
  
  container.innerHTML = ticketsHtml;
  
  // 상세 보기 버튼 이벤트 처리
  container.querySelectorAll('.btn-view-details').forEach(button => {
    button.addEventListener('click', (event) => {
      const ticketId = event.target.dataset.ticketId;
      showTicketDetails(ticketId, tickets.find(t => t.id == ticketId));
    });
  });
  
  // 답변 사용 버튼 이벤트 처리
  container.querySelectorAll('.btn-use-solution').forEach(button => {
    button.addEventListener('click', (event) => {
      const ticketId = event.target.dataset.ticketId;
      useTicketSolution(ticketId, tickets.find(t => t.id == ticketId));
    });
  });
}

/**
 * 추천 솔루션 목록 렌더링 함수
 * @param {Array} solutions - 추천 솔루션 배열
 * @param {HTMLElement} container - 추천 솔루션을 렌더링할 컨테이너
 */
function renderRecommendedSolutions(solutions, container) {
  if (!solutions || !container) return;
  
  console.log("🖥️ 추천 솔루션 렌더링:", solutions);
  
  // 추천 솔루션이 없을 경우
  if (solutions.length === 0) {
    container.innerHTML = `
      <div class="no-results">
        <p>추천 솔루션을 찾을 수 없습니다.</p>
      </div>
    `;
    return;
  }
  
  // 추천 솔루션 목록 렌더링
  const solutionsHtml = solutions.map(solution => `
    <div class="solution-card" data-solution-id="${solution.id || ''}">
      <div class="solution-header">
        <div class="solution-title">${window.utils?.truncateText ? window.utils.truncateText(solution.title || '제목 없음', 70) : (solution.title || '제목 없음')}</div>
        <div class="solution-meta">
          <span class="solution-category">${solution.category || '일반'}</span>
          <span class="solution-score">${(solution.relevance_score * 100).toFixed(0)}% 일치</span>
        </div>
      </div>
      <div class="solution-content">
        <div class="solution-description">${formatDescription(solution.content || '')}</div>
      </div>
      <div class="solution-footer">
        <div class="solution-source">${solution.source || '지식베이스'}</div>
        <button class="btn btn-sm btn-view-details" data-solution-id="${solution.id || ''}">상세 보기</button>
        <button class="btn btn-sm btn-use-solution" data-solution-id="${solution.id || ''}">답변 사용</button>
      </div>
    </div>
  `).join('');
  
  container.innerHTML = solutionsHtml;
  
  // 상세 보기 버튼 이벤트 처리
  container.querySelectorAll('.btn-view-details').forEach(button => {
    button.addEventListener('click', (event) => {
      const solutionId = event.target.dataset.solutionId;
      showSolutionDetails(solutionId, solutions.find(s => s.id == solutionId));
    });
  });
  
  // 답변 사용 버튼 이벤트 처리
  container.querySelectorAll('.btn-use-solution').forEach(button => {
    button.addEventListener('click', (event) => {
      const solutionId = event.target.dataset.solutionId;
      useSolution(solutionId, solutions.find(s => s.id == solutionId));
    });
  });
}

/**
 * 티켓 상세 정보 모달 표시
 * @param {string} ticketId - 티켓 ID
 * @param {Object} ticket - 티켓 상세 정보
 */
function showTicketDetails(ticketId, ticket) {
  if (!ticket) {
    showError("티켓 정보를 찾을 수 없습니다.");
    return;
  }
  
  // 모달 생성
  const modalId = `ticket-modal-${ticketId}`;
  
  // 기존 모달이 있으면 제거
  const existingModal = document.getElementById(modalId);
  if (existingModal) {
    existingModal.remove();
  }
  
  // 새 모달 생성
  const modal = document.createElement('div');
  modal.id = modalId;
  modal.className = 'modal';
  modal.innerHTML = `
    <div class="modal-backdrop"></div>
    <div class="modal-content">
      <div class="modal-header">
        <h3>${ticket.subject || '제목 없음'}</h3>
        <button class="modal-close">&times;</button>
      </div>
      <div class="modal-body">
        <div class="ticket-detail-meta">
          <div class="meta-item"><span class="label">상태:</span> <span class="value ${window.utils?.getStatusClass ? window.utils.getStatusClass(ticket.status) : ''}">${window.utils?.getStatusText ? window.utils.getStatusText(ticket.status) : (ticket.status || '')}</span></div>
          <div class="meta-item"><span class="label">우선순위:</span> <span class="value ${window.utils?.getPriorityClass ? window.utils.getPriorityClass(ticket.priority) : ''}">${window.utils?.getPriorityText ? window.utils.getPriorityText(ticket.priority) : (ticket.priority || '')}</span></div>
          <div class="meta-item"><span class="label">생성일:</span> <span class="value">${window.utils?.formatDate ? window.utils.formatDate(ticket.created_at) : (ticket.created_at || '')}</span></div>
          <div class="meta-item"><span class="label">최근 업데이트:</span> <span class="value">${window.utils?.formatDate ? window.utils.formatDate(ticket.updated_at) : (ticket.updated_at || '')}</span></div>
        </div>
        <div class="ticket-detail-content">
          <h4>티켓 내용</h4>
          <div class="content-box">${ticket.description || '내용 없음'}</div>
          
          ${ticket.notes && ticket.notes.length > 0 ? `
            <h4>노트 (${ticket.notes.length})</h4>
            <div class="notes-container">
              ${ticket.notes.map(note => `
                <div class="note-item">
                  <div class="note-header">
                    <span class="note-user">${note.user_name || '사용자'}</span>
                    <span class="note-date">${window.utils?.formatDate ? window.utils.formatDate(note.created_at) : (note.created_at || '')}</span>
                  </div>
                  <div class="note-content">${note.body || ''}</div>
                </div>
              `).join('')}
            </div>
          ` : ''}
          
          ${ticket.attachments && ticket.attachments.length > 0 ? `
            <h4>첨부파일 (${ticket.attachments.length})</h4>
            <div class="attachments-container">
              ${ticket.attachments.map(attachment => `
                <div class="attachment-item">
                  <span class="attachment-icon">📎</span>
                  <a href="${attachment.url}" target="_blank" class="attachment-link">${attachment.name || '첨부파일'}</a>
                  <span class="attachment-size">${formatFileSize(attachment.size)}</span>
                </div>
              `).join('')}
            </div>
          ` : ''}
        </div>
      </div>
      <div class="modal-footer">
        <button class="btn btn-secondary modal-close">닫기</button>
        <button class="btn btn-primary btn-use-as-reply">답변으로 사용</button>
      </div>
    </div>
  `;
  
  // 모달을 body에 추가
  document.body.appendChild(modal);
  
  // 모달 닫기 버튼 이벤트
  modal.querySelectorAll('.modal-close').forEach(button => {
    button.addEventListener('click', () => {
      modal.remove();
    });
  });
  
  // 답변으로 사용하기 버튼 이벤트
  modal.querySelector('.btn-use-as-reply').addEventListener('click', () => {
    useTicketSolution(ticketId, ticket);
    modal.remove();
  });
  
  // ESC 키로 모달 닫기
  const escHandler = (e) => {
    if (e.key === 'Escape') {
      modal.remove();
      document.removeEventListener('keydown', escHandler);
    }
  };
  document.addEventListener('keydown', escHandler);
  
  // 배경 클릭으로 모달 닫기
  modal.querySelector('.modal-backdrop').addEventListener('click', () => {
    modal.remove();
  });

  // 모달 표시 애니메이션
  setTimeout(() => {
    modal.classList.add('show');
  }, 10);
}

/**
 * 솔루션 상세 정보 모달 표시
 * @param {string} solutionId - 솔루션 ID
 * @param {Object} solution - 솔루션 상세 정보
 */
function showSolutionDetails(solutionId, solution) {
  if (!solution) {
    showError("솔루션 정보를 찾을 수 없습니다.");
    return;
  }
  
  // 모달 생성
  const modalId = `solution-modal-${solutionId}`;
  
  // 기존 모달이 있으면 제거
  const existingModal = document.getElementById(modalId);
  if (existingModal) {
    existingModal.remove();
  }
  
  // 새 모달 생성
  const modal = document.createElement('div');
  modal.id = modalId;
  modal.className = 'modal';
  modal.innerHTML = `
    <div class="modal-backdrop"></div>
    <div class="modal-content">
      <div class="modal-header">
        <h3>${solution.title || '제목 없음'}</h3>
        <button class="modal-close">&times;</button>
      </div>
      <div class="modal-body">
        <div class="solution-detail-meta">
          <div class="meta-item"><span class="label">카테고리:</span> <span class="value">${solution.category || '일반'}</span></div>
          <div class="meta-item"><span class="label">출처:</span> <span class="value">${solution.source || '지식베이스'}</span></div>
          <div class="meta-item"><span class="label">관련도:</span> <span class="value">${(solution.relevance_score * 100).toFixed(0)}%</span></div>
        </div>
        <div class="solution-detail-content">
          <h4>솔루션 내용</h4>
          <div class="content-box">${solution.content || '내용 없음'}</div>
          
          ${solution.tags && solution.tags.length > 0 ? `
            <div class="solution-tags">
              <h4>태그</h4>
              <div class="tags-container">
                ${solution.tags.map(tag => `<span class="tag">${tag}</span>`).join('')}
              </div>
            </div>
          ` : ''}
        </div>
      </div>
      <div class="modal-footer">
        <button class="btn btn-secondary modal-close">닫기</button>
        <button class="btn btn-primary btn-use-as-reply">답변으로 사용</button>
      </div>
    </div>
  `;
  
  // 모달을 body에 추가
  document.body.appendChild(modal);
  
  // 모달 닫기 버튼 이벤트
  modal.querySelectorAll('.modal-close').forEach(button => {
    button.addEventListener('click', () => {
      modal.remove();
    });
  });
  
  // 답변으로 사용하기 버튼 이벤트
  modal.querySelector('.btn-use-as-reply').addEventListener('click', () => {
    useSolution(solutionId, solution);
    modal.remove();
  });
  
  // ESC 키로 모달 닫기
  const escHandler = (e) => {
    if (e.key === 'Escape') {
      modal.remove();
      document.removeEventListener('keydown', escHandler);
    }
  };
  document.addEventListener('keydown', escHandler);
  
  // 배경 클릭으로 모달 닫기
  modal.querySelector('.modal-backdrop').addEventListener('click', () => {
    modal.remove();
  });

  // 모달 표시 애니메이션
  setTimeout(() => {
    modal.classList.add('show');
  }, 10);
}

/**
 * 티켓 솔루션을 답변으로 사용
 * @param {string} ticketId - 티켓 ID
 * @param {Object} ticket - 티켓 정보 객체
 */
function useTicketSolution(ticketId, ticket) {
  if (!ticket) {
    showError("티켓 정보를 찾을 수 없습니다.");
    return;
  }
  
  try {
    // 티켓에서 응답 템플릿 생성
    const responseTemplate = generateResponseFromTicket(ticket);
    
    // Freshdesk 리플라이 박스에 응답 삽입
    insertResponseToReplyBox(responseTemplate);
    
    showNotification("응답이 리플라이 박스에 삽입되었습니다.", "success");
  } catch (error) {
    showError("응답 생성 중 오류가 발생했습니다.", error);
  }
}

/**
 * 솔루션을 답변으로 사용
 * @param {string} solutionId - 솔루션 ID
 * @param {Object} solution - 솔루션 정보 객체
 */
function useSolution(solutionId, solution) {
  if (!solution) {
    showError("솔루션 정보를 찾을 수 없습니다.");
    return;
  }
  
  try {
    // 솔루션에서 응답 템플릿 생성
    const responseTemplate = generateResponseFromSolution(solution);
    
    // Freshdesk 리플라이 박스에 응답 삽입
    insertResponseToReplyBox(responseTemplate);
    
    showNotification("응답이 리플라이 박스에 삽입되었습니다.", "success");
  } catch (error) {
    showError("응답 생성 중 오류가 발생했습니다.", error);
  }
}

/**
 * 티켓 정보로부터 응답 템플릿 생성
 * @param {Object} ticket - 티켓 정보
 * @returns {string} - 생성된 응답 템플릿
 */
function generateResponseFromTicket(ticket) {
  // 관련 노트에서 해결 방법 찾기
  let solution = "";
  
  if (ticket.notes && ticket.notes.length > 0) {
    // 가장 최근의 비공개 노트 또는 마지막 노트 사용
    const relevantNote = ticket.notes.find(note => note.private === true) || ticket.notes[ticket.notes.length - 1];
    
    if (relevantNote) {
      solution = relevantNote.body || "";
    }
  }
  
  if (!solution && ticket.description) {
    solution = ticket.description;
  }
  
  return `안녕하세요, 

문의하신 내용과 유사한 케이스를 참고하여 해결 방법을 안내해 드립니다:

${solution}

추가 질문이 있으시면 언제든지 문의해 주세요.

감사합니다.`;
}

/**
 * 솔루션 정보로부터 응답 템플릿 생성
 * @param {Object} solution - 솔루션 정보
 * @returns {string} - 생성된 응답 템플릿
 */
function generateResponseFromSolution(solution) {
  return `안녕하세요, 

문의하신 내용에 대한 해결 방법을 안내해 드립니다:

${solution.content}

추가 질문이 있으시면 언제든지 문의해 주세요.

감사합니다.`;
}

/**
 * Freshdesk 티켓 리플라이 박스에 응답 삽입
 * @param {string} response - 삽입할 응답 텍스트
 */
function insertResponseToReplyBox(response) {
  // Freshdesk의 iFrame과 통신하여 부모 창의 리플라이 박스에 응답 삽입
  window.parent.postMessage(
    {
      action: "insertText",
      text: response,
    },
    "*"
  );
}

/**
 * 파일 크기 포맷팅 함수
 * @param {number} bytes - 바이트 크기
 * @returns {string} - 포맷팅된 파일 크기
 */
function formatFileSize(bytes) {
  if (!bytes || isNaN(bytes)) return "알 수 없음";
  
  const sizes = ["Bytes", "KB", "MB", "GB", "TB"];
  if (bytes === 0) return "0 Bytes";
  
  const i = parseInt(Math.floor(Math.log(bytes) / Math.log(1024)));
  
  return Math.round(bytes / Math.pow(1024, i)) + " " + sizes[i];
}

// 전역 네임스페이스로 내보내기
window.ui = {
  showLoadingIndicator,
  hideLoadingIndicator,
  showQuickLoadingIndicator,
  hideQuickLoadingIndicator,
  showNotification,
  showError,
  switchTab,
  renderTicketSummary,
  renderSimilarTickets,
  renderRecommendedSolutions,
  showTicketDetails,
  showSolutionDetails,
  useTicketSolution,
  useSolution,
};
