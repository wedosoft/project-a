let client;

/**
 * 탭 전환 기능 초기화 (각 탭별 최초 1회만 렌더링)
 */
function initTabSwitching() {
  const tabs = document.querySelectorAll('.tab');
  const tabContents = document.querySelectorAll('.tab-content');
  
  tabs.forEach(tab => {
    tab.addEventListener('click', function() {
      const tabId = this.getAttribute('data-tab');
      
      // Remove active class from all tabs and tab contents
      tabs.forEach(tab => tab.classList.remove('active'));
      tabContents.forEach(content => content.classList.remove('active'));
      
      // Add active class to clicked tab and corresponding content
      this.classList.add('active');
      const targetContent = document.getElementById(tabId);
      if (targetContent) {
        targetContent.classList.add('active');
      }
      
      // Handle tab-specific actions using only cached data (render approach)
      if (tabId === 'similar-tickets') {
        // 캐시된 데이터만 사용하는 render 방식
        if (window.ticketInitData && window.ticketInitData.similar_tickets && window.ticketInitData.similar_tickets.length > 0) {
          console.log("📋 캐시된 유사 티켓 데이터 사용");
          updateSimilarTicketsFromCache(window.ticketInitData.similar_tickets);
        } else {
          console.log("🔍 유사 티켓 데이터 없음");
          const container = document.getElementById('similar-tickets');
          if (container) {
            container.innerHTML = '<p>유사한 티켓을 찾을 수 없습니다.</p>';
          }
        }
      } else if (tabId === 'suggested-solutions') {
        // 캐시된 지식베이스 데이터만 사용하는 render 방식
        if (window.ticketInitData && window.ticketInitData.kb_docs && window.ticketInitData.kb_docs.length > 0) {
          console.log("📚 캐시된 지식베이스 데이터 사용");
          updateKnowledgeBaseFromCache(window.ticketInitData.kb_docs);
        } else {
          console.log("🔍 추천 솔루션 데이터 없음");
          const container = document.getElementById('suggested-solutions');
          if (container) {
            container.innerHTML = '<p>관련 문서를 찾을 수 없습니다.</p>';
          }
        }
      }
    });
  });

  // Initialize active tab on page load using only cached data
  const activeTab = document.querySelector('.tab.active');
  if (activeTab) {
    const tabId = activeTab.getAttribute('data-tab');
    
    if (tabId === 'similar-tickets') {
      // 캐시된 데이터만 사용하는 render 방식으로 초기화
      if (window.ticketInitData && window.ticketInitData.similar_tickets && window.ticketInitData.similar_tickets.length > 0) {
        updateSimilarTicketsFromCache(window.ticketInitData.similar_tickets);
      } else {
        const container = document.getElementById('similar-tickets');
        if (container) {
          container.innerHTML = '<p>비슷한 티켓 데이터가 없습니다. 데이터 로딩을 기다려주세요.</p>';
        }
      }
    } else if (tabId === 'suggested-solutions') {
      // 캐시된 데이터만 사용하는 render 방식으로 초기화
      if (window.ticketInitData && window.ticketInitData.kb_docs && window.ticketInitData.kb_docs.length > 0) {
        updateKnowledgeBaseFromCache(window.ticketInitData.kb_docs);
      } else {
        const container = document.getElementById('suggested-solutions');
        if (container) {
          container.innerHTML = '<p>제안된 솔루션 데이터가 없습니다. 데이터 로딩을 기다려주세요.</p>';
        }
      }
    }
  }
}

/**
 * 필터 선택 기능 초기화
 */
function initFilterSelection() {
  const filters = document.querySelectorAll('.filter');
  filters.forEach(filter => {
    filter.addEventListener('click', function() {
      this.classList.toggle('active');
    });
  });
}

/**
 * 공통 모달 트리거 함수
 */
async function showModal() {
  try {
    const data = await client.data.get("ticket");
    const ticket = data.ticket;
    await client.interface.trigger("showModal", {
      title: "Copilot Canvas",
      template: "index.html",
      data: { showAiTab: false, ticket },
      noBackdrop: true,
      size: {
        width: "800px",
        height: "600px",
      },
    });
    console.log("Modal 열림");
  } catch (error) {
    console.error("Modal 오류", error);
  }
}

/**
 * 코파일럿 AI 응답 모달 트리거 함수
 */
async function showCopilotModal() {
  try {
    const data = await client.data.get("ticket");
    const ticket = data.ticket;
    await client.interface.trigger("showModal", {
      title: "Copilot Canvas",
      template: "modal.html",
      data: { showAiTab: true, ticket },
      noBackdrop: true,
      size: {
        width: "800px",
        height: "600px",
      },
    });
    console.log("Copilot Modal 열림");
  } catch (error) {
    console.error("Copilot Modal 오류", error);
  }
}

  // Freshdesk Custom App 초기화 - 새로운 방식
app.initialized()
  .then((c) => {
    client = c;

    // ① 상단 네비게이션 앱 아이콘 클릭 시 처리
    client.events.on("app.activated", async () => {
      try {
        const ctx = await client.instance.context();
        
        // 디버깅: 실제 location 값 확인
        console.log("앱 활성화 - 컨텍스트:", ctx);
        console.log("현재 location:", ctx.location);
        
        // 상단 네비게이션에서의 동작: 백엔드 데이터 로드 후 모달 표시
        if (ctx.location === "ticket_top_navigation") {
          console.log("상단 네비게이션 아이콘 클릭 → 백엔드 데이터 로드 후 모달 표시");
          
          // 1단계: 백엔드에서 데이터 로드 (DOM 접근 없이)
          await loadTicketDataFromBackend();
          
          // 2단계: 모달 표시
          await showModal();
        } else {
          // 예상치 못한 위치에서의 호출
          console.warn("예상치 못한 위치에서 앱 활성화:", ctx.location);
          await loadTicketDataFromBackend();
        }
      } catch (err) {
        console.error("onAppActivated 오류", err);
      }
    });

    // ② 모달이 열린 후 DOM 요소에 데이터 렌더링
    client.events.on("template.render", () => {
      try {
        console.log("🎭 모달 템플릿 렌더링 완료 - DOM 초기화 시작");
        
        // DOM이 완전히 로드되도록 짧은 지연 후 초기화
        setTimeout(async () => {
          await initializeTicketWithBackend();
          // DOM 이벤트 리스너도 함께 초기화
          initEventListeners();
        }, 100);
        
      } catch (err) {
        console.error("template.render 이벤트 처리 오류", err);
      }
    });

    // ③ 티켓 속성 업데이트 이벤트 리스너
    client.events.on('ticket.propertiesUpdated', function() {
      // 티켓 속성 업데이트 시 백엔드 데이터 새로고침
      console.log("🔄 티켓 속성 업데이트됨 - 데이터 새로고침");
      loadTicketDataFromBackend();
    });
  })
  .catch(err => console.error("SDK 초기화 실패", err));

/**
 * 모든 DOM 이벤트 리스너를 초기화하는 함수
 */
function initEventListeners() {
  // 탭 전환 기능 초기화
  initTabSwitching();
  
  // 필터 선택 기능 초기화
  initFilterSelection();
  
  // 검색 버튼 클릭 이벤트
  const searchBtn = document.querySelector('.search-btn');
  if (searchBtn) {
    searchBtn.addEventListener('click', async function() {
      try {
        await showCopilotModal();
      } catch (error) {
        console.error('검색 버튼 오류:', error);
      }
    });
  }
  
  // 상세 보기 버튼 클릭 이벤트  
  const viewDetailsBtn = document.getElementById('view-details-btn');
  if (viewDetailsBtn) {
    viewDetailsBtn.addEventListener('click', async function() {
      try {
        await showSampleModal();
      } catch (error) {
        console.error('상세 보기 버튼 오류:', error);
      }
    });
  }
}

/**
 * 유사 티켓 데이터를 캐시에서 가져와 UI에 표시 (최초 1회만 렌더링)
 */
let isSimilarTicketsRendered = false; // 이미 렌더링 여부 플래그
function renderSimilarTicketsFromCache() {
  try {
    // 이미 렌더링된 경우 재렌더링 방지
    if (isSimilarTicketsRendered) return;
    // 로딩 상태 표시
    document.getElementById('similar-tickets').innerHTML = '<p>유사 티켓을 불러오는 중입니다...</p>';
    // 캐시 데이터 확인
    if (window.ticketInitData && window.ticketInitData.similar_tickets) {
      console.log("📋 캐시된 유사 티켓 데이터 사용");
      const similarTickets = window.ticketInitData.similar_tickets;
      if (similarTickets.length > 0) {
        // updateSimilarTicketsFromCache 함수가 있다면 활용
        if (typeof updateSimilarTicketsFromCache === 'function') {
          updateSimilarTicketsFromCache(similarTickets);
        } else {
          // 직접 테이블 렌더링 (예시)
          let tableHtml = `<fw-data-table id="similar-tickets-table" label="유사 티켓"></fw-data-table>`;
          document.getElementById('similar-tickets').innerHTML = tableHtml;
          const table = document.getElementById('similar-tickets-table');
          const columns = [
            { key: 'id', text: 'ID' },
            { key: 'subject', text: '제목' },
            { key: 'status', text: '상태' },
            { key: 'priority', text: '우선순위' },
            { key: 'score', text: '유사도' }
          ];
          const rows = similarTickets.map(t => ({
            id: t.id?.toString() || '-',
            subject: t.subject || '-',
            status: t.status || '-',
            priority: t.priority || '-',
            score: t.score ? `${Math.round(t.score * 100)}%` : '-'
          }));
          table.columns = columns;
          table.rows = rows;
        }
        isSimilarTicketsRendered = true; // 렌더링 완료 플래그 설정
      } else {
        document.getElementById('similar-tickets').innerHTML = '<p>유사 티켓이 없습니다.</p>';
      }
    } else {
      document.getElementById('similar-tickets').innerHTML = '<p>유사 티켓 데이터를 불러올 수 없습니다. 새로고침 해주세요.</p>';
    }
  } catch (error) {
    document.getElementById('similar-tickets').innerHTML = '<p>유사 티켓 표시 중 오류가 발생했습니다.</p>';
    console.error('유사 티켓 렌더링 오류:', error);
  }
}

/**
 * 추천 솔루션(지식베이스) 데이터를 캐시에서 가져와 UI에 표시 (최초 1회만 렌더링)
 */
let isSuggestedSolutionsRendered = false; // 이미 렌더링 여부 플래그
function renderSuggestedSolutionsFromCache() {
  try {
    if (isSuggestedSolutionsRendered) return;
    
    console.log("📚 추천 솔루션 렌더링 시작");
    document.getElementById('suggested-solutions').innerHTML = '<p>추천 솔루션을 불러오는 중입니다...</p>';
    
    if (window.ticketInitData && window.ticketInitData.kb_docs) {
      console.log("📚 캐시된 추천 솔루션 데이터 사용");
      const kbDocs = window.ticketInitData.kb_docs;
      
      if (Array.isArray(kbDocs) && kbDocs.length > 0) {
        // updateSuggestedSolutionsFromCache 함수 호출하여 실제 렌더링 처리
        updateSuggestedSolutionsFromCache();
        isSuggestedSolutionsRendered = true;
        console.log("✅ 추천 솔루션 렌더링 완료");
      } else {
        document.getElementById('suggested-solutions').innerHTML = '<p>추천 솔루션이 없습니다.</p>';
        console.log("❌ 추천 솔루션 데이터 없음");
      }
    } else {
      document.getElementById('suggested-solutions').innerHTML = '<p>추천 솔루션 데이터를 불러올 수 없습니다. 새로고침 해주세요.</p>';
      console.log("❌ 추천 솔루션 캐시 데이터 없음");
    }
  } catch (error) {
    document.getElementById('suggested-solutions').innerHTML = '<p>추천 솔루션 표시 중 오류가 발생했습니다.</p>';
    console.error('추천 솔루션 렌더링 오류:', error);
  }
}

/**
 * Handle attachment download when the download button is clicked
 * @param {Event} event - Click event
 */
async function handleAttachmentDownload(event) {
  try {
    // Show loading state
    const downloadButton = event.currentTarget;
    const attachmentId = downloadButton.getAttribute('data-attachment-id');
    
    // Disable the button and show loading state
    downloadButton.loading = true;
    
    // Get attachment details using Data API
    const attachmentData = await client.data.get('attachment', { id: attachmentId });
    const attachment = attachmentData.attachment;
    
    if (attachment && attachment.attachment_url) {
      // Create a temporary anchor element to trigger download
      const downloadLink = document.createElement('a');
      downloadLink.href = attachment.attachment_url;
      downloadLink.download = attachment.name || 'attachment';
      downloadLink.target = '_blank';
      downloadLink.click();
      
      // Show success notification
      client.interface.trigger('showNotify', {
        type: 'success',
        message: `Downloading ${attachment.name}`
      });
    } else {
      // Show error notification if attachment URL is not available
      client.interface.trigger('showNotify', {
        type: 'danger',
        message: 'Failed to get attachment download URL'
      });
    }
  } catch (error) {
    console.error('Error downloading attachment:', error);
    client.interface.trigger('showNotify', {
      type: 'danger',
      message: 'Failed to download attachment. Please try again.'
    });
  } finally {
    // Reset button state after download attempt
    event.currentTarget.loading = false;
  }
}

/**
 * 페이지 로드 시 백엔드에서 티켓 데이터를 미리 로드하는 함수 (DOM 접근 없이)
 * 데이터는 window.ticketInitData에 저장되어 나중에 모달에서 사용됨
 */
async function loadTicketDataFromBackend() {
  try {
    console.log("🔄 백엔드 데이터 로드 시작 (DOM 접근 없이)");
    
    // 기존 데이터 초기화
    window.ticketInitData = {};
    
    // 티켓 ID 추출
    const data = await client.data.get("ticket");
    const ticketId = data.ticket.id;
    
    // iparams에서 백엔드 URL 가져오기
    const iparams = await client.iparams.get();
    let backendBaseUrl = iparams.backend_url || "https://zb19rpd2m1.execute-api.ap-northeast-2.amazonaws.com/dev";
    
    // URL 유효성 검사 및 정규화
    if (!backendBaseUrl) {
      throw new Error("Backend URL이 설정되지 않았습니다. iparams에서 backend_url을 설정해주세요.");
    }
    
    // 프로토콜이 없으면 https:// 추가
    if (!backendBaseUrl.startsWith('http://') && !backendBaseUrl.startsWith('https://')) {
      backendBaseUrl = `https://${backendBaseUrl}`;
    }
    
    // 마지막 슬래시 제거 (있다면)
    backendBaseUrl = backendBaseUrl.replace(/\/$/, '');
    
    console.log(`📋 최종 백엔드 URL: ${backendBaseUrl}`);
    
    // SSE 연결 URL 구성
    const sseUrl = `${backendBaseUrl}/init/${ticketId}`;
    console.log(`🔗 SSE 연결 시작: ${sseUrl}`);
    
    return new Promise((resolve, reject) => {
      const source = new EventSource(sseUrl);
      let receivedData = { summary: false, similar_tickets: false, solutions: false };
      
      source.onmessage = function(event) {
        try {
          const { type, data } = JSON.parse(event.data);
          console.log(`📡 SSE 수신: ${type}`, data);
          
          // DOM 접근 없이 데이터만 저장
          if (type === "summary") {
            window.ticketInitData.summary = data;
            receivedData.summary = true;
          } else if (type === "similar_tickets") {
            window.ticketInitData.similar_tickets = Array.isArray(data) ? data : (data.results || data.tickets || []);
            receivedData.similar_tickets = true;
          } else if (type === "solutions") {
            window.ticketInitData.kb_docs = Array.isArray(data) ? data : (data.results || data.documents || []);
            receivedData.solutions = true;
          }
        } catch (err) {
          console.error("SSE 데이터 파싱 오류", err);
        }
      };
      
      source.addEventListener("end", () => {
        console.log("🏁 SSE 연결 종료 - 데이터 로드 완료");
        source.close();
        
        // 데이터 수신 완료 체크
        const completed = Object.values(receivedData).filter(Boolean).length;
        console.log(`✅ 로드된 데이터 타입 수: ${completed}/3`);
        
        resolve(window.ticketInitData);
      });
      
      source.onerror = function(err) {
        console.error("SSE 연결 오류", err);
        source.close();
        reject(err);
      };
      
      // 타임아웃 설정 (30초)
      setTimeout(() => {
        if (source.readyState !== EventSource.CLOSED) {
          console.warn("SSE 연결 타임아웃");
          source.close();
          resolve(window.ticketInitData); // 부분 데이터라도 사용
        }
      }, 30000);
    });
  } catch (err) {
    console.error("백엔드 데이터 로드 오류", err);
    // 에러가 발생해도 빈 객체로 초기화하여 모달은 열리도록 함
    window.ticketInitData = {};
    throw err;
  }
}

/**
 * 모달이 열린 후 DOM 요소에 데이터를 렌더링하는 함수
 * 이미 로드된 데이터가 있으면 그것을 사용하고, 없으면 SSE로 실시간 로드
 */
async function initializeTicketWithBackend() {
  try {
    console.log("🔄 모달 내 티켓 데이터 초기화 시작");
    
    // DOM 요소 존재 확인 (안전성 체크)
    const summaryEl = document.getElementById('summary');
    const similarTicketsEl = document.getElementById('similar-tickets');
    const suggestedSolutionsEl = document.getElementById('suggested-solutions');
    
    if (!summaryEl || !similarTicketsEl || !suggestedSolutionsEl) {
      console.warn("⚠️ DOM 요소가 아직 존재하지 않음 - 모달이 완전히 로드되지 않았을 수 있음");
      // 짧은 지연 후 재시도
      setTimeout(() => initializeTicketWithBackend(), 500);
      return;
    }
    
    // 로딩 상태 표시
    summaryEl.innerHTML = '<p>요약을 불러오는 중입니다...</p>';
    similarTicketsEl.innerHTML = '<p>유사 티켓을 불러오는 중입니다...</p>';
    suggestedSolutionsEl.innerHTML = '<p>추천 솔루션을 불러오는 중입니다...</p>';
    
    // 이미 로드된 데이터가 있는지 확인
    if (window.ticketInitData && Object.keys(window.ticketInitData).length > 0) {
      console.log("✅ 이미 로드된 데이터 사용하여 즉시 렌더링");
      
      // 기존 데이터로 즉시 렌더링
      if (window.ticketInitData.summary) {
        renderSummaryFromCache();
      }
      if (window.ticketInitData.similar_tickets) {
        renderSimilarTicketsFromCache();
      }
      if (window.ticketInitData.kb_docs) {
        renderSuggestedSolutionsFromCache();
      }
      
      return;
    }
    
    // 데이터가 없으면 SSE로 실시간 로드하면서 DOM에 즉시 반영
    console.log("🔄 데이터 없음 - SSE로 실시간 로드 시작");
    
    const data = await client.data.get("ticket");
    const ticketId = data.ticket.id;
    
    // iparams에서 백엔드 URL 가져오기
    const iparams = await client.iparams.get();
    let backendBaseUrl = iparams.backend_url;
    
    // URL 유효성 검사 및 정규화
    if (!backendBaseUrl) {
      throw new Error("Backend URL이 설정되지 않았습니다. iparams에서 backend_url을 설정해주세요.");
    }
    
    // 프로토콜이 없으면 https:// 추가
    if (!backendBaseUrl.startsWith('http://') && !backendBaseUrl.startsWith('https://')) {
      backendBaseUrl = `https://${backendBaseUrl}`;
    }
    
    // 마지막 슬래시 제거 (있다면)
    backendBaseUrl = backendBaseUrl.replace(/\/$/, '');
    
    console.log(`📋 모달용 최종 백엔드 URL: ${backendBaseUrl}`);
    
    const sseUrl = `${backendBaseUrl}/init/${ticketId}`;
    console.log(`🔗 모달용 SSE 연결 시작: ${sseUrl}`);
    
    const source = new EventSource(sseUrl);
    let receivedData = { summary: false, similar_tickets: false, solutions: false };
    
    source.onmessage = function(event) {
      try {
        const { type, data } = JSON.parse(event.data);
        console.log(`📡 모달용 SSE 수신: ${type}`, data);
        
        // 데이터 저장과 동시에 DOM에 즉시 렌더링
        if (type === "summary") {
          window.ticketInitData.summary = data;
          renderSummaryFromCache(); // 즉시 렌더링
          receivedData.summary = true;
        } else if (type === "similar_tickets") {
          window.ticketInitData.similar_tickets = Array.isArray(data) ? data : (data.results || data.tickets || []);
          renderSimilarTicketsFromCache(); // 즉시 렌더링
          receivedData.similar_tickets = true;
        } else if (type === "solutions") {
          window.ticketInitData.kb_docs = Array.isArray(data) ? data : (data.results || data.documents || []);
          renderSuggestedSolutionsFromCache(); // 즉시 렌더링
          receivedData.solutions = true;
        }
      } catch (err) {
        console.error("모달용 SSE 데이터 파싱 오류", err);
      }
    };
    
    source.addEventListener("end", () => {
      console.log("🏁 모달용 SSE 연결 종료");
      source.close();
      
      const completed = Object.values(receivedData).filter(Boolean).length;
      console.log(`📊 모달 SSE 완료: ${completed}/3 데이터 타입 수신됨`);
    });
    
    source.onerror = function(err) {
      console.error("❌ 모달용 SSE 연결 오류", err);
      source.close();
      
      // 폴백 UI 표시 (DOM 안전성 체크)
      if (!receivedData.summary && document.getElementById('summary')) {
        document.getElementById('summary').innerHTML = '<p>요약을 불러올 수 없습니다. 새로고침 해주세요.</p>';
      }
      if (!receivedData.similar_tickets && document.getElementById('similar-tickets')) {
        document.getElementById('similar-tickets').innerHTML = '<p>유사 티켓을 불러올 수 없습니다. 새로고침 해주세요.</p>';
      }
      if (!receivedData.solutions && document.getElementById('suggested-solutions')) {
        document.getElementById('suggested-solutions').innerHTML = '<p>추천 솔루션을 불러올 수 없습니다. 새로고침 해주세요.</p>';
      }
    };
    
  } catch (error) {
    console.error("모달 티켓 초기화 오류", error);
    
    // DOM 안전성 체크 후 에러 메시지 표시
    if (document.getElementById('summary')) {
      document.getElementById('summary').innerHTML = '<p>데이터 로드 중 오류가 발생했습니다.</p>';
    }
    if (document.getElementById('similar-tickets')) {
      document.getElementById('similar-tickets').innerHTML = '<p>데이터 로드 중 오류가 발생했습니다.</p>';
    }
    if (document.getElementById('suggested-solutions')) {
      document.getElementById('suggested-solutions').innerHTML = '<p>데이터 로드 중 오류가 발생했습니다.</p>';
    }
  }
}

/**
 * 요약 데이터를 캐시에서 가져와 UI에 표시
 */
function renderSummaryFromCache() {
  try {
    console.log("📝 요약 데이터 렌더링 시작");
    const summaryDiv = document.getElementById('summary');
    
    // DOM 안전성 체크
    if (!summaryDiv) {
      console.warn("⚠️ summary DOM 요소를 찾을 수 없음");
      return;
    }
    
    if (window.ticketInitData && window.ticketInitData.summary) {
      const summaryData = window.ticketInitData.summary;
      
      // 요약 데이터가 문자열인 경우와 객체인 경우 모두 처리
      let summaryText = '';
      if (typeof summaryData === 'string') {
        summaryText = summaryData;
      } else if (summaryData.text || summaryData.summary) {
        summaryText = summaryData.text || summaryData.summary;
      } else {
        summaryText = JSON.stringify(summaryData);
      }
      
      summaryDiv.innerHTML = `<p>${summaryText}</p>`;
      console.log("✅ 요약 렌더링 완료");
    } else {
      summaryDiv.innerHTML = '<p>요약 데이터를 불러올 수 없습니다.</p>';
      console.log("❌ 요약 데이터 없음");
    }
  } catch (error) {
    console.error("요약 렌더링 오류", error);
    const summaryDiv = document.getElementById('summary');
    if (summaryDiv) {
      summaryDiv.innerHTML = '<p>요약 표시 중 오류가 발생했습니다.</p>';
    }
  }
}

/**
 * 캐시된 유사 티켓 데이터로 UI 업데이트
 */
function updateSimilarTicketsFromCache(similarTickets) {
  try {
    if (similarTickets && similarTickets.length > 0) {
      // 유사 티켓 탭 컨테이너 찾기
      const similarTicketsContainer = document.getElementById('similar-tickets');
      if (!similarTicketsContainer) return;
      
      // 데이터 테이블 HTML 생성
      let tableHtml = `
        <fw-data-table id="cached-similar-tickets-table" label="Similar Tickets (Pre-loaded)">
        </fw-data-table>
      `;
      
      similarTicketsContainer.innerHTML = tableHtml;
      
      // 테이블 설정
      const table = document.getElementById('cached-similar-tickets-table');
      
      // 컬럼 정의
      const columns = [
        { key: 'id', text: 'Ticket ID' },
        { key: 'subject', text: 'Subject' },
        { key: 'status', text: 'Status' },
        { key: 'priority', text: 'Priority' },
        { key: 'similarity_score', text: 'Similarity' }
      ];
      
      // 행 데이터 포맷팅
      const rows = similarTickets.map(ticket => ({
        id: ticket.id?.toString() || ticket.ticket_id?.toString() || 'N/A',
        subject: ticket.subject || ticket.title || 'No subject',
        status: ticket.status || 'Unknown',
        priority: ticket.priority || 'Unknown',
        similarity_score: ticket.similarity_score 
          ? `${Math.round(ticket.similarity_score * 100)}%` 
          : 'N/A'
      }));
      
      // 테이블 데이터 설정
      table.columns = columns;
      table.rows = rows;
      
      console.log(`✅ 캐시된 유사 티켓 ${similarTickets.length}개 UI 업데이트 완료`);
    }
  } catch (error) {
    console.error("❌ 캐시된 유사 티켓 UI 업데이트 실패:", error);
  }
}

/**
 * 캐시된 지식베이스 데이터로 UI 업데이트
 */
function updateKnowledgeBaseFromCache(kbDocs) {
  try {
    if (kbDocs && kbDocs.length > 0) {
      console.log(`📚 캐시된 지식베이스 문서 ${kbDocs.length}개 발견`);
      
      // 지식베이스 데이터를 suggested-solutions 탭에 표시할 수 있도록 글로벌 변수에 저장
      window.cachedKbDocs = kbDocs;
      
      // suggested-solutions 탭이 활성화되어 있으면 즉시 표시
      const suggestedSolutionsTab = document.querySelector('.tab[data-tab="suggested-solutions"]');
      if (suggestedSolutionsTab && suggestedSolutionsTab.classList.contains('active')) {
        updateSuggestedSolutionsFromCache();
      }
    }
  } catch (error) {
    console.error("❌ 캐시된 지식베이스 UI 업데이트 실패:", error);
  }
}

/**
 * 캐시된 지식베이스로 Suggested Solutions 탭 업데이트
 */
function updateSuggestedSolutionsFromCache() {
  try {
    // 캐시된 데이터에서 직접 가져오기
    const kbDocs = window.ticketInitData && window.ticketInitData.kb_docs;
    const container = document.getElementById('suggested-solutions');
    
    // DOM 안전성 체크
    if (!container) {
      console.warn("⚠️ suggested-solutions DOM 요소를 찾을 수 없음");
      return;
    }
    
    if (!kbDocs || !Array.isArray(kbDocs) || kbDocs.length === 0) {
      container.innerHTML = '<p>관련 문서를 찾을 수 없습니다.</p>';
      return;
    }
    
    let html = '<div class="suggested-solutions-list">';
    html += '<h4>📚 관련 지식베이스 문서 (스트리밍 로드됨)</h4>';
    
    kbDocs.slice(0, 5).forEach((doc, index) => {
      const title = doc.title || doc.subject || `문서 ${index + 1}`;
      const content = doc.content || doc.text || doc.body || 'No content available';
      const score = doc.similarity_score 
        ? `(유사도: ${Math.round(doc.similarity_score * 100)}%)` 
        : '';
      
      html += `
        <div class="solution-item" style="margin-bottom: 15px; padding: 10px; border: 1px solid #ddd; border-radius: 5px;">
          <h5 style="margin: 0 0 5px 0; color: #333;">${title} ${score}</h5>
          <p style="margin: 0; color: #666; font-size: 14px;">${content.substring(0, 200)}${content.length > 200 ? '...' : ''}</p>
        </div>
      `;
    });
    
    html += '</div>';
    container.innerHTML = html;
    
    console.log(`✅ 캐시된 지식베이스 ${kbDocs.length}개 Suggested Solutions 탭 업데이트 완료`);
  } catch (error) {
    console.error("❌ Suggested Solutions 캐시 업데이트 실패:", error);
    const container = document.getElementById('suggested-solutions');
    if (container) {
      container.innerHTML = '<p>추천 솔루션 표시 중 오류가 발생했습니다.</p>';
    }
  }
}

/**
 * Fetch ticket data using Data methods and populate UI
 */
async function getTicketData() {
  try {
    // Get ticket data from the current context
    const data = await client.data.get('ticket');
    const ticket = data.ticket;
    
    // Populate UI with ticket metadata
    document.getElementById('ticket-problem').textContent = ticket.subject || 'N/A';
    document.getElementById('ticket-cause').textContent = 'Analyzing...';
    document.getElementById('ticket-actions').textContent = 'Pending Analysis';
    document.getElementById('ticket-result').textContent = 'Pending';
    document.getElementById('ticket-status').textContent = ticket.status || 'N/A';
    document.getElementById('ticket-priority').textContent = ticket.priority || 'N/A';
    
    // Get agent data if assigned
    if (ticket.responder_id) {
      try {
        const agentData = await client.data.get('agent', { id: ticket.responder_id });
        document.getElementById('ticket-agent').textContent = agentData.agent.name || 'Unassigned';
      } catch (error) {
        document.getElementById('ticket-agent').textContent = 'Unassigned';
        console.error('Error fetching agent data:', error);
      }
    } else {
      document.getElementById('ticket-agent').textContent = 'Unassigned';
    }
    
    // Get requester data
    try {
      const requesterData = await client.data.get('requester', { id: ticket.requester_id });
      document.getElementById('ticket-requester').textContent = requesterData.requester.name || 'N/A';
    } catch (error) {
      document.getElementById('ticket-requester').textContent = 'N/A';
      console.error('Error fetching requester data:', error);
    }
    
    // Set channel info
    document.getElementById('ticket-channel').textContent = ticket.source || 'N/A';
    
    // Set tags
    const tags = ticket.tags || [];
    document.getElementById('ticket-tags').textContent = tags.length > 0 ? tags.join(', ') : 'No tags';
    
    // Set attachments
    const attachments = ticket.attachments || [];
    if (attachments.length > 0) {
      const attachmentsContainer = document.getElementById('attachments-container');
      attachmentsContainer.innerHTML = '';
      
      attachments.forEach(attachment => {
        const attachmentItem = document.createElement('div');
        attachmentItem.className = 'attachment-item';
        
        const attachmentName = document.createElement('span');
        attachmentName.textContent = attachment.name;
        
        const downloadBtn = document.createElement('fw-button');
        downloadBtn.color = 'secondary';
        downloadBtn.size = 'small';
        downloadBtn.setAttribute('data-attachment-id', attachment.id);
        downloadBtn.innerHTML = '<fw-icon name="download" size="14" slot="before-label"></fw-icon>Download';
        
        attachmentItem.appendChild(attachmentName);
        attachmentItem.appendChild(downloadBtn);
        attachmentsContainer.appendChild(attachmentItem);
        
        // Register click event on the download button
        downloadBtn.addEventListener('click', handleAttachmentDownload);
      });
      
      document.getElementById('attachments-section').style.display = 'block';
    } else {
      document.getElementById('ticket-attachments').textContent = 'None';
      document.getElementById('attachments-section').style.display = 'none';
    }
    
  } catch (error) {
    console.error('Error fetching ticket data:', error);
    // Update UI to show error state
    document.getElementById('ticket-problem').textContent = 'Error loading ticket data';
    document.getElementById('ticket-cause').textContent = 'Error';
    document.getElementById('ticket-actions').textContent = 'Error';
    document.getElementById('ticket-result').textContent = 'Error';
  }
}

/**
 * 티켓 메타데이터를 동적으로 렌더링하는 함수
 * 상태/우선순위 값에 따라 CSS 클래스를 동적으로 적용
 * @param {Object} metadata - 티켓 메타데이터 객체
 */
function renderTicketMetadata(metadata) {
    // 각 메타데이터 영역의 DOM 요소를 가져옴
    const titleEl = document.getElementById('ticket-title');
    const statusEl = document.getElementById('ticket-status');
    const priorityEl = document.getElementById('ticket-priority');
    const agentEl = document.getElementById('ticket-agent');
    const groupEl = document.getElementById('ticket-group');
    const createdAtEl = document.getElementById('ticket-created-at');
    const channelEl = document.getElementById('ticket-channel');
    const tagsEl = document.getElementById('ticket-tags');

    // 값이 존재할 때만 갱신
    if (titleEl && metadata.title) titleEl.textContent = metadata.title;
    if (statusEl && metadata.status) {
        statusEl.textContent = metadata.status;
        // 상태별 색상 강조 클래스 적용
        statusEl.className = 'metadata-value status-label ' + getStatusClass(metadata.status);
    }
    if (priorityEl && metadata.priority) {
        priorityEl.textContent = metadata.priority;
        // 우선순위별 색상 강조 클래스 적용
        priorityEl.className = 'metadata-value priority-label ' + getPriorityClass(metadata.priority);
    }
    if (agentEl && metadata.agent) agentEl.textContent = metadata.agent;
    if (groupEl && metadata.group) groupEl.textContent = metadata.group;
    if (createdAtEl && metadata.created_at) createdAtEl.textContent = metadata.created_at;
    if (channelEl && metadata.channel) channelEl.textContent = metadata.channel;
    if (tagsEl && metadata.tags) tagsEl.textContent = Array.isArray(metadata.tags) ? metadata.tags.join(', ') : metadata.tags;
}

/**
 * 상태 값에 따라 CSS 클래스를 반환
 * @param {string} status
 * @returns {string}
 */
function getStatusClass(status) {
    // Freshdesk 표준 상태명 기준, 필요시 확장
    switch (status.toLowerCase()) {
        case 'open':
        case '열림':
            return 'status-open';
        case 'pending':
        case '대기':
            return 'status-pending';
        case 'resolved':
        case '해결':
            return 'status-resolved';
        case 'closed':
        case '종료':
            return 'status-closed';
        default:
            return 'status-default';
    }
}

/**
 * 우선순위 값에 따라 CSS 클래스를 반환
 * @param {string} priority
 * @returns {string}
 */
function getPriorityClass(priority) {
    // Freshdesk 표준 우선순위명 기준, 필요시 확장
    switch (priority.toLowerCase()) {
        case 'low':
        case '낮음':
            return 'priority-low';
        case 'medium':
        case '보통':
            return 'priority-medium';
        case 'high':
        case '높음':
            return 'priority-high';
        case 'urgent':
        case '긴급':
            return 'priority-urgent';
        default:
            return 'priority-default';
    }
}

// partial 데이터 수신 시 메타데이터 영역 갱신
function handlePartialData(partial) {
    // ...기존 영역별 렌더링 로직...
    if (partial.metadata) {
        // 티켓 메타데이터가 포함된 경우 동적으로 렌더링
        renderTicketMetadata(partial.metadata);
    }
    // ...summary, similar-tickets, suggested-solutions 등 기존 렌더링...
}

// SSE 수신부에서 partial 데이터 처리 시 handlePartialData 호출하도록 연결
// 예시:
// eventSource.onmessage = function(event) {
//     const partial = JSON.parse(event.data);
//     handlePartialData(partial);
// };

/**
 * 현재 티켓 ID를 가져오는 헬퍼 함수
 */
function getCurrentTicketId() {
  // URL에서 티켓 ID 추출 시도
  const urlParams = new URLSearchParams(window.location.search);
  let ticketId = urlParams.get('ticket_id');
  
  if (!ticketId) {
    // 글로벌 변수에서 티켓 ID 찾기
    if (window.ticketInitData && window.ticketInitData.ticket_id) {
      ticketId = window.ticketInitData.ticket_id;
    }
  }
  
  if (!ticketId) {
    // Freshdesk context에서 티켓 ID 찾기 (만약 Freshdesk FDK를 사용한다면)
    try {
      if (typeof app !== 'undefined' && app.initialized) {
        // Freshdesk app context가 있는 경우
        app.get('ticket').then(function(ticketData) {
          ticketId = ticketData.ticket.id;
        });
      }
    } catch (e) {
      console.warn("Freshdesk context에서 티켓 ID를 가져올 수 없습니다:", e);
    }
  }
  
  return ticketId;
}