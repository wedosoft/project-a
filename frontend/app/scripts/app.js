/**
 * Freshdesk Custom App - Simplified Version
 * 단순하고 빠른 AI 상담사 지원 시스템
 */

const App = {
  // 설정
  config: {
    baseURL: 'http://localhost:8000',
    apiKey: 'Ug9H1cKCZZtZ4haamBy',
    tenantId: 'wedosoft',
    domain: 'wedosoft.freshdesk.com'
  },

  // 현재 상태
  state: {
    ticketId: null,
    isLoading: false,
    currentMode: 'smart', // 'smart' or 'free'
    client: null // FDK 클라이언트 객체
  },

  // API 통신
  api: {
    // 기본 헤더 생성
    getHeaders() {
      return {
        'Content-Type': 'application/json',
        'X-Tenant-ID': App.config.tenantId,
        'X-Platform': 'freshdesk',
        'X-Domain': App.config.domain,
        'X-API-Key': App.config.apiKey
      };
    },

    // 초기 데이터 로드 (스트리밍) - fetch + ReadableStream 사용
    async loadInitialData(ticketId) {
      const url = `${App.config.baseURL}/init/${ticketId}?stream=true`;
      
      try {
        const response = await fetch(url, {
          method: 'GET',
          headers: this.getHeaders()
        });
        
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let summary = '';
        let similarTickets = [];
        let kbDocuments = [];
        
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          
          buffer += decoder.decode(value, { stream: true });
          
          // SSE 형식: data: {json}\n\n 으로 구분
          const chunks = buffer.split('\n\n');
          buffer = chunks.pop(); // 마지막 불완전한 청크는 버퍼에 보관
          
          for (const chunk of chunks) {
            if (!chunk.trim()) continue;
            
            // 각 청크를 개별적으로 처리
            const lines = chunk.split('\n');
            let jsonBuffer = '';
            
            for (const line of lines) {
              if (line.startsWith('data: ')) {
                const dataStr = line.slice(6).trim();
                console.log('파싱 시도:', dataStr.substring(0, 100) + '...');
                
                if (dataStr === '[DONE]') {
                  App.state.isLoading = false;
                  App.ui.hideLoading();
                  return { summary, similarTickets, kbDocuments };
                }
                
                // 멀티라인 JSON 처리
                if (dataStr.startsWith('{') && !dataStr.endsWith('}')) {
                  jsonBuffer = dataStr;
                  continue;
                } else if (jsonBuffer && dataStr.endsWith('}')) {
                  jsonBuffer += dataStr;
                  try {
                    const data = JSON.parse(jsonBuffer);
                    console.log('멀티라인 파싱 성공:', data.type);
                    const result = App.ui.processStreamData(data, { summary, similarTickets, kbDocuments });
                    if (result) {
                      summary = result.summary || summary;
                      similarTickets = result.similarTickets || similarTickets;
                      kbDocuments = result.kbDocuments || kbDocuments;
                      
                      if (result.shouldReturn) {
                        App.state.isLoading = false;
                        App.ui.hideLoading();
                        return { summary, similarTickets, kbDocuments };
                      }
                    }
                    jsonBuffer = '';
                  } catch (parseError) {
                    console.error('멀티라인 JSON 파싱 실패:', parseError.message);
                    jsonBuffer = '';
                  }
                  continue;
                }
                
                try {
                  const data = JSON.parse(dataStr);
                  console.log('파싱 성공:', data.type);
                  
                  // 데이터 처리
                  const result = App.ui.processStreamData(data, { summary, similarTickets, kbDocuments });
                  if (result) {
                    summary = result.summary || summary;
                    similarTickets = result.similarTickets || similarTickets;
                    kbDocuments = result.kbDocuments || kbDocuments;
                    
                    if (result.shouldReturn) {
                      App.state.isLoading = false;
                      App.ui.hideLoading();
                      return { summary, similarTickets, kbDocuments };
                    }
                  }
                } catch (parseError) {
                  console.warn('JSON 파싱 실패 (무시):', parseError.message);
                  console.log('실패한 데이터 (처음 50자):', dataStr.substring(0, 50));
                  // 파싱 실패는 무시하고 계속 진행
                }
              }
            }
          }
        }
        
        // 스트림이 완료되었지만 complete 이벤트가 없는 경우
        App.state.isLoading = false;
        App.ui.hideLoading();
        return { summary, similarTickets, kbDocuments };
        
      } catch (error) {
        App.state.isLoading = false;
        App.ui.hideLoading();
        console.error('초기 데이터 로드 실패:', error);
        App.ui.showError('백엔드 서버에 연결할 수 없습니다. 서버가 실행 중인지 확인해주세요.');
        throw error;
      }
    },

    // 채팅 쿼리 전송
    async sendChatQuery(query, mode = 'smart') {
      const response = await fetch(`${App.config.baseURL}/query`, {
        method: 'POST',
        headers: this.getHeaders(),
        body: JSON.stringify({
          query: query,
          agent_mode: mode === 'smart',
          stream_response: true,
          ticket_id: App.state.ticketId
        })
      });

      if (!response.ok) {
        throw new Error(`API 오류: ${response.status}`);
      }

      // 스트리밍 응답 처리
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let messageId = Date.now();

      // 메시지 컨테이너 생성
      App.ui.addChatMessage('assistant', '', messageId);

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop();

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6);
            if (data === '[DONE]') continue;
            
            try {
              const event = JSON.parse(data);
              if (event.type === 'content' && event.content) {
                App.ui.updateChatMessage(messageId, event.content);
              }
            } catch (e) {
              // JSON 파싱 실패 시 무시
            }
          }
        }
      }
    }
  },

  // UI 렌더링
  ui: {
    // 요약 업데이트 (스트리밍)
    updateSummary(text) {
      const element = document.getElementById('summaryText');
      if (element && marked) {
        element.innerHTML = marked.parse(text);
      } else if (element) {
        element.innerHTML = text; // marked가 없을 경우 일반 텍스트로
      }
    },

    // 유사 티켓 렌더링
    renderSimilarTickets(tickets) {
      const container = document.getElementById('similarTicketsContainer');
      if (!container || !tickets.length) return;

      container.innerHTML = tickets.map(ticket => `
        <div class="similar-ticket-item">
          <div class="ticket-header">
            <span class="ticket-id">#${ticket.id || 'N/A'}</span>
            <span class="ticket-status status-${(ticket.status || 'unknown').toLowerCase()}">${ticket.status || 'N/A'}</span>
          </div>
          <div class="ticket-subject">${ticket.subject || ticket.title || 'N/A'}</div>
          <div class="ticket-meta">
            ${ticket.created_at ? new Date(ticket.created_at).toLocaleDateString('ko-KR') : 'N/A'} • 
            ${ticket.priority || 'N/A'} 우선순위
          </div>
        </div>
      `).join('');
    },

    // KB 문서 렌더링
    renderKBDocuments(documents) {
      const container = document.getElementById('kbDocumentsContainer');
      if (!container || !documents.length) return;

      container.innerHTML = documents.map((doc, index) => `
        <div class="kb-item" data-doc-id="${doc.id}" data-doc-index="${index}">
          <div class="kb-header">
            <i class="fas fa-book"></i>
            <span class="kb-title">${doc.title || '제목 없음'}</span>
          </div>
          <div class="kb-meta">
            ${doc.category || '일반'} • 조회수 ${doc.views || 0}
          </div>
        </div>
      `).join('');
      
      // KB 문서 클릭 이벤트 (필요시 추가 기능 구현)
      container.querySelectorAll('.kb-item').forEach((item, index) => {
        item.addEventListener('click', () => {
          const docId = item.dataset.docId;
          console.log(`KB 문서 클릭: ${docId}`);
          // 필요시 추가 기능 구현
        });
      });
    },

    // 채팅 메시지 추가
    addChatMessage(role, content, messageId) {
      const container = document.getElementById('chatResults');
      if (!container) return;

      const messageDiv = document.createElement('div');
      messageDiv.className = `message ${role}`;
      messageDiv.id = `msg-${messageId}`;
      messageDiv.innerHTML = `
        <div class="message-content">
          <div class="message-text">${marked ? marked.parse(content) : content}</div>
        </div>
      `;
      container.appendChild(messageDiv);
      container.scrollTop = container.scrollHeight;
    },

    // 채팅 메시지 업데이트 (스트리밍)
    updateChatMessage(messageId, content) {
      const messageText = document.querySelector(`#msg-${messageId} .message-text`);
      if (messageText && marked) {
        messageText.innerHTML = marked.parse(content);
        const container = document.getElementById('chatResults');
        if (container) {
          container.scrollTop = container.scrollHeight;
        }
      }
    },

    // FDK 모달 표시 (원본 코드 기반)
    async showFDKModal(ticketId, hasCachedData = false) {
      try {
        console.log(`티켓 ${ticketId} 모달 열기 시도`);
        
        // FDK 클라이언트 확인
        const client = App.state.client;
        if (!client) {
          console.error('❌ FDK 클라이언트가 준비되지 않음');
          return;
        }
        
        // 티켓 데이터 가져오기
        let ticket = null;
        try {
          const ticketData = await client.data.get('ticket');
          ticket = ticketData?.ticket;
        } catch (error) {
          console.warn('티켓 데이터 가져오기 실패:', error.message);
          ticket = { id: ticketId, subject: '연결 오류' };
        }
        
        // 모달 설정 구성 (원본과 동일)
        const modalConfig = {
          title: "Copilot Canvas - AI 상담사 지원",
          template: "index.html",
          data: {
            ticketId: ticketId,
            ticket: ticket,
            hasCachedData: hasCachedData,
            timestamp: new Date().toISOString(),
            noBackendCall: true,
            usePreloadedData: true,
            isLoading: false,
            isReady: true,
            isPartiallyLoaded: false
          },
          size: {
            width: "900px",
            height: "700px"
          },
          noBackdrop: true
        };
        
        // 모달을 반드시 열어야 하므로 강화된 에러 처리
        let modalOpenSuccess = false;
        let attemptCount = 0;
        const maxAttempts = 3;
        
        while (!modalOpenSuccess && attemptCount < maxAttempts) {
          attemptCount++;
          console.log(`🎭 모달 열기 시도 ${attemptCount}/${maxAttempts}`);
          
          try {
            await client.interface.trigger("showModal", modalConfig);
            console.log('✅ FDK 모달 열기 성공');
            modalOpenSuccess = true;
          } catch (modalError) {
            console.error(`❌ FDK 모달 열기 실패 (시도 ${attemptCount}):`, modalError);
            
            if (attemptCount < maxAttempts) {
              // 재시도 전 잠시 대기
              await new Promise(resolve => setTimeout(resolve, 500));
              console.log('🔄 모달 열기 재시도 준비 중...');
            } else {
              // 최종 시도 - 오류 모드로 강제 표시
              console.log('🚨 최종 시도: 오류 모드로 모달 강제 표시');
              
              const emergencyConfig = {
                title: "Copilot Canvas - 연결 오류",
                template: "index.html",
                data: {
                  ticketId: ticketId || 'unknown',
                  ticket: ticket || { id: 'unknown', subject: '연결 오류' },
                  hasCachedData: false,
                  hasError: true,
                  errorMessage: '모달 열기 실패',
                  timestamp: new Date().toISOString()
                },
                size: {
                  width: "900px",
                  height: "700px"
                },
                noBackdrop: true
              };
              
              try {
                await client.interface.trigger("showModal", emergencyConfig);
                console.log('✅ 응급 모달 표시 성공');
                modalOpenSuccess = true;
              } catch (emergencyError) {
                console.error('❌ 응급 모달도 실패:', emergencyError);
                modalOpenSuccess = true; // 더 이상 시도하지 않음
              }
            }
          }
        }
        
      } catch (error) {
        console.error('❌ 모달 표시 오류:', error);
      }
    },

    // 로딩 표시
    showLoading() {
      const loadingOverlay = document.getElementById('loading-overlay');
      if (loadingOverlay) {
        loadingOverlay.style.display = 'flex';
      }
    },

    // 로딩 숨기기
    hideLoading() {
      const loadingOverlay = document.getElementById('loading-overlay');
      if (loadingOverlay) {
        loadingOverlay.style.display = 'none';
      }
    },

    // 에러 표시
    showError(message) {
      console.error('앱 에러:', message);
      
      const errorDiv = document.createElement('div');
      errorDiv.className = 'error-toast';
      errorDiv.textContent = message;
      errorDiv.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: #f8d7da;
        color: #721c24;
        padding: 10px 15px;
        border-radius: 4px;
        border: 1px solid #f5c6cb;
        z-index: 9999;
        max-width: 300px;
      `;
      
      if (document.body) {
        document.body.appendChild(errorDiv);
        
        setTimeout(() => {
          if (errorDiv && errorDiv.parentNode) {
            errorDiv.parentNode.removeChild(errorDiv);
          }
        }, 5000);
      } else {
        console.error('document.body가 없음:', message);
      }
    },
    
    // 스트림 데이터 처리
    processStreamData(data, currentData) {
      switch(data.type) {
        case 'summary':
          // 백엔드에서 전체 요약을 한 번에 보내므로 바로 표시
          currentData.summary = data.content || '';
          this.updateSummary(currentData.summary);
          break;
          
        case 'similar_tickets':
          currentData.similarTickets = data.content || [];
          this.renderSimilarTickets(currentData.similarTickets);
          break;
          
        case 'kb_documents':
          currentData.kbDocuments = data.content || [];
          this.renderKBDocuments(currentData.kbDocuments);
          break;
          
        case 'progress':
          // 진행률 정보 (필요시 UI에 표시)
          console.log(`진행률: ${data.progress}% - ${data.message}`);
          break;
          
        case 'complete':
          return { ...currentData, shouldReturn: true };
          
        case 'error':
          console.error('백엔드 에러:', data.message);
          this.showError(data.message || '알 수 없는 오류');
          break;
      }
      return currentData;
    }
  },

  // 이벤트 핸들러
  events: {
    // 채팅 전송
    async handleSendMessage() {
      const input = document.getElementById('chatInput');
      const sendButton = document.getElementById('sendButton');
      
      if (!input || !input.value.trim()) return;

      const query = input.value.trim();
      input.value = '';
      
      // 사용자 메시지 표시
      App.ui.addChatMessage('user', query, Date.now());
      
      // 버튼 비활성화
      if (sendButton) {
        sendButton.disabled = true;
      }

      try {
        await App.api.sendChatQuery(query, App.state.currentMode);
      } catch (error) {
        App.ui.showError('메시지 전송 실패: ' + error.message);
      } finally {
        if (sendButton) {
          sendButton.disabled = false;
        }
      }
    },

    // 모드 전환
    handleModeSwitch(mode) {
      App.state.currentMode = mode;
      
      // UI 업데이트
      document.querySelectorAll('.mode-button').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.mode === mode);
      });
    },

    // 탭 전환
    handleTabSwitch(tabName) {
      // 모든 탭 컨텐츠 숨기기
      document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
      });
      
      // 모든 탭 버튼 비활성화
      document.querySelectorAll('.tab-button').forEach(btn => {
        btn.classList.remove('active');
      });
      
      // 선택된 탭 활성화
      const selectedContent = document.getElementById(`${tabName}Tab`);
      const selectedButton = document.querySelector(`[data-tab="${tabName}"]`);
      
      if (selectedContent) selectedContent.classList.add('active');
      if (selectedButton) selectedButton.classList.add('active');
    }
  },

  // 초기화
  async init() {
    console.log('앱 초기화 시작');

    try {
      // FDK 클라이언트 초기화
      const client = await app.initialized();
      App.state.client = client; // 클라이언트 객체 저장
      
      // 티켓 정보 가져오기
      const ticketData = await client.data.get('ticket');
      App.state.ticketId = ticketData.ticket.id;
      console.log('티켓 ID 설정:', App.state.ticketId);
      
      // 초기 데이터 로드
      App.state.isLoading = true;
      App.ui.showLoading();
      
      try {
        await App.api.loadInitialData(App.state.ticketId);
      } catch (error) {
        console.error('초기 데이터 로드 실패:', error);
        App.ui.hideLoading();
        // 백엔드 연결 실패 시에도 기본 UI는 표시
        App.ui.showError('백엔드 서버 연결 실패. 일부 기능이 제한됩니다.');
      }
      
    } catch (error) {
      console.error('FDK 초기화 오류:', error);
      console.warn('FDK 없이 기본 모드로 실행합니다.');
      
      // FDK 없이도 기본 기능은 사용 가능하도록 더미 티켓 ID 설정
      App.state.ticketId = 'demo-ticket-' + Date.now();
      App.ui.showError('FDK 초기화 실패. 데모 모드로 실행됩니다.');
    }

    // 이벤트 리스너 설정
    this.setupEventListeners();
  },

  // 이벤트 리스너 설정
  setupEventListeners() {
    // 채팅 전송 버튼
    const sendButton = document.getElementById('sendButton');
    if (sendButton) {
      sendButton.addEventListener('click', () => App.events.handleSendMessage());
    }

    // 엔터키로 전송
    const chatInput = document.getElementById('chatInput');
    if (chatInput) {
      chatInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          App.events.handleSendMessage();
        }
      });
    }

    // 모드 전환 버튼
    document.querySelectorAll('.mode-button').forEach(btn => {
      btn.addEventListener('click', () => {
        App.events.handleModeSwitch(btn.dataset.mode);
      });
    });

    // 탭 전환 버튼
    document.querySelectorAll('.tab-button').forEach(btn => {
      btn.addEventListener('click', () => {
        App.events.handleTabSwitch(btn.dataset.tab);
      });
    });
  }
};

// 전역으로 노출 (디버깅용 + FDK 이벤트 처리)
window.App = App;

// Top bar navigation 이벤트 처리용 전역 함수
window.showFDKModal = async function(ticketId) {
  console.log('📡 Top bar navigation에서 모달 열기 요청');
  if (App && App.ui && App.ui.showFDKModal) {
    await App.ui.showFDKModal(ticketId || App.state.ticketId);
  } else {
    console.error('❌ App.ui.showFDKModal 함수가 준비되지 않음');
  }
};

// DOM 로드 완료 시 앱 초기화
document.addEventListener('DOMContentLoaded', () => {
  // FDK가 로드되었는지 확인
  if (typeof app !== 'undefined') {
    App.init().catch(error => {
      console.error('앱 초기화 중 오류:', error);
      // FDK 없이도 기본 UI는 작동하도록 이벤트 리스너 설정
      App.setupEventListeners();
    });
  } else {
    console.warn('FDK가 로드되지 않았습니다. 기본 UI만 작동합니다.');
    // FDK 없이도 기본 UI는 작동하도록 이벤트 리스너 설정
    App.setupEventListeners();
  }
});