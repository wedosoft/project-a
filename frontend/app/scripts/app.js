let client;

/**
 * 탭 전환 기능 초기화
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
      document.getElementById(tabId).classList.add('active');
      
      // Handle tab-specific actions
      if (tabId === 'similar-tickets') {
        // 먼저 캐시된 데이터가 있는지 확인
        if (window.ticketInitData && window.ticketInitData.similar_tickets && window.ticketInitData.similar_tickets.length > 0) {
          console.log("📋 캐시된 유사 티켓 데이터 사용");
          updateSimilarTicketsFromCache(window.ticketInitData.similar_tickets);
        } else {
          console.log("🔍 새로운 유사 티켓 검색 실행");
          fetchSimilarTickets();
        }
      } else if (tabId === 'suggested-solutions') {
        // 먼저 캐시된 지식베이스 데이터가 있는지 확인
        if (window.cachedKbDocs && window.cachedKbDocs.length > 0) {
          console.log("📚 캐시된 지식베이스 데이터 사용");
          updateSuggestedSolutionsFromCache();
        } else {
          console.log("🔍 새로운 해결책 검색 실행");
          fetchSuggestedSolutions();
        }
      }
    });
  });
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
  .then(c => {
    client = c;

    // ① 상단 네비게이션 앱 아이콘 클릭 시 모달 열기
    client.events.on("app.activated", async () => {
      try {
        const ctx = await client.instance.context();
        if (ctx.location === "ticket_top_navigation") {
          console.log("앱 아이콘 클릭 → 활성화됨");
          await showModal();
        } else {
          console.log("일반적인 앱 활성화 → 백엔드 초기화 시작");
          // 상담원이 티켓을 열자마자 백엔드 API 호출
          await initializeTicketWithBackend();
        }
      } catch (err) {
        console.error("onAppActivated 오류", err);
      }
    });

    // ② 티켓 속성 업데이트 이벤트 리스너
    client.events.on('ticket.propertiesUpdated', function() {
      // 티켓 속성 업데이트 시 백엔드 데이터 새로고침
      initializeTicketWithBackend();
    });

    // ③ DOM 이벤트 리스너 초기화
    initEventListeners();
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
 * Fetch similar tickets from FastAPI backend and update the UI
 */
async function fetchSimilarTickets() {
  try {
    // Show loading state
    document.getElementById('similar-tickets').innerHTML = '<p>Loading similar tickets...</p>';
    
    // Freshdesk 설정값 가져오기
    const iparams = await client.iparams.get();
    const freshdeskDomain = iparams.freshdesk_domain;
    const freshdeskApiKey = iparams.freshdesk_api_key;
    
    // Get current ticket data
    const data = await client.data.get('ticket');
    const ticketId = data.ticket.id;
    
    // Call FastAPI backend using request template (Freshdesk 설정값을 헤더로 전달)
    const response = await client.request.invoke('externalApi', {
      path: `/similar-tickets?ticket_id=${ticketId}`,
      method: 'GET',
      headers: {
        'X-Freshdesk-Domain': freshdeskDomain,
        'X-Freshdesk-API-Key': freshdeskApiKey
      }
    });
    
    // Parse the response
    const similarTickets = JSON.parse(response.response);
    
    // Update the UI with similar tickets
    if (similarTickets && similarTickets.length > 0) {
      // Create a data table to display similar tickets
      let tableHtml = `
        <fw-data-table id="similar-tickets-table" label="Similar Tickets">
        </fw-data-table>
      `;
      
      document.getElementById('similar-tickets').innerHTML = tableHtml;
      
      // Configure the data table
      const table = document.getElementById('similar-tickets-table');
      
      // Define columns
      const columns = [
        { key: 'id', text: 'Ticket ID' },
        { key: 'subject', text: 'Subject' },
        { key: 'status', text: 'Status' },
        { key: 'priority', text: 'Priority' },
        { key: 'similarity_score', text: 'Similarity' }
      ];
      
      // Format rows for the data table
      const rows = similarTickets.map(ticket => ({
        id: ticket.id.toString(),
        subject: ticket.subject,
        status: ticket.status,
        priority: ticket.priority,
        similarity_score: `${Math.round(ticket.similarity_score * 100)}%`
      }));
      
      // Set table data
      table.columns = columns;
      table.rows = rows;
    } else {
      document.getElementById('similar-tickets').innerHTML = '<p>No similar tickets found.</p>';
    }
  } catch (error) {
    console.error('Error fetching similar tickets:', error);
    document.getElementById('similar-tickets').innerHTML = 
      '<p>Failed to load similar tickets. Please try again.</p>';
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
 * Fetch suggested solutions from FastAPI backend and update the UI
 */
async function fetchSuggestedSolutions() {
  try {
    // Show loading state
    document.getElementById('suggested-solutions').innerHTML = '<p>Loading suggested solutions...</p>';
    
    // Get current ticket data
    const data = await client.data.get('ticket');
    const ticketId = data.ticket.id;
    
    // Call FastAPI backend using request template
    const response = await client.request.invoke('externalApi', {
      path: `/suggested-solutions?ticket_id=${ticketId}`,
      method: 'GET'
    });
    
    // Parse the response
    const suggestedSolutions = JSON.parse(response.response);
    
    // Update the UI with suggested solutions
    if (suggestedSolutions && suggestedSolutions.length > 0) {
      let solutionsHtml = `<fw-data-table id="suggested-solutions-table" label="Suggested Solutions"></fw-data-table>`;
      
      document.getElementById('suggested-solutions').innerHTML = solutionsHtml;
      
      // Configure the data table
      const table = document.getElementById('suggested-solutions-table');
      
      // Define columns
      const columns = [
        { key: 'id', text: 'ID' },
        { key: 'title', text: 'Title' },
        { key: 'description', text: 'Description' },
        { key: 'relevance_score', text: 'Relevance' },
        { key: 'solution_url', text: 'URL' }
      ];
      
      // Format rows for the data table
      const rows = suggestedSolutions.map(solution => ({
        id: solution.id.toString(),
        title: solution.title,
        description: solution.description,
        relevance_score: `${Math.round(solution.relevance_score * 100)}%`,
        solution_url: `<a href="${solution.solution_url}" target="_blank">View</a>`
      }));
      
      // Set table data
      table.columns = columns;
      table.rows = rows;
    } else {
      document.getElementById('suggested-solutions').innerHTML = '<p>No suggested solutions found.</p>';
    }
  } catch (error) {
    console.error('Error fetching suggested solutions:', error);
    document.getElementById('suggested-solutions').innerHTML = 
      '<p>Failed to load suggested solutions. Please try again.</p>';
  }
}

/**
 * 티켓 백엔드 초기화 함수
 * 상담원이 티켓을 열 때 자동으로 백엔드 /init/{ticket_id} API를 호출하여
 * 티켓 컨텍스트를 초기화하고 관련 데이터를 미리 로드합니다.
 */
async function initializeTicketWithBackend() {
  try {
    console.log("🚀 백엔드 티켓 초기화 시작");
    
    // 백엔드 상태 표시 시작
    showBackendStatus("loading", "백엔드 초기화 중...", "티켓 데이터를 분석하고 관련 정보를 로드하고 있습니다.");
    
    // Freshdesk 설정값 가져오기 (iparams에서 사용자가 입력한 값)
    const iparams = await client.iparams.get();
    const freshdeskDomain = iparams.freshdesk_domain;
    const freshdeskApiKey = iparams.freshdesk_api_key;
    
    console.log(`🔑 Freshdesk 설정 - Domain: ${freshdeskDomain}`);
    
    // 현재 티켓 데이터 가져오기
    const data = await client.data.get("ticket");
    const ticketId = data.ticket.id;
    
    if (!ticketId) {
      console.warn("티켓 ID를 찾을 수 없습니다.");
      showBackendStatus("error", "초기화 실패", "티켓 ID를 찾을 수 없습니다.");
      return;
    }
    
    console.log(`📋 티켓 ID ${ticketId} 백엔드 초기화 요청`);
    
    // 백엔드 /init/{ticket_id} API 호출 (Freshdesk 설정값을 헤더로 전달)
    const response = await client.request.invoke('externalApi', {
      path: `/init/${ticketId}?include_summary=true&include_kb_docs=true&include_similar_tickets=true`,
      method: 'GET',
      headers: {
        'X-Freshdesk-Domain': freshdeskDomain,
        'X-Freshdesk-API-Key': freshdeskApiKey
      }
    });
    
    // 응답 데이터 파싱
    const initData = JSON.parse(response.response);
    
    const statusDetails = `유사 티켓: ${initData.similar_tickets?.length || 0}개, 지식베이스: ${initData.kb_docs?.length || 0}개`;
    
    console.log("✅ 백엔드 초기화 완료:", {
      ticketId,
      summaryGenerated: !!initData.summary,
      kbDocsCount: initData.kb_docs?.length || 0,
      similarTicketsCount: initData.similar_tickets?.length || 0,
      contextId: initData.context_id
    });
    
    // 성공 상태 표시
    showBackendStatus("success", "초기화 완료", statusDetails);
    
    // 초기화된 데이터를 글로벌 변수에 저장 (다른 함수에서 활용 가능)
    window.ticketInitData = {
      ...initData,
      ticketId,
      initTimestamp: Date.now()
    };
    
    // UI 업데이트를 위해 기존 getTicketData 함수도 호출
    await getTicketData();
    
    // 미리 로드된 데이터가 있으면 해당 탭에 표시
    if (initData.similar_tickets && initData.similar_tickets.length > 0) {
      updateSimilarTicketsFromCache(initData.similar_tickets);
    }
    
    if (initData.kb_docs && initData.kb_docs.length > 0) {
      updateKnowledgeBaseFromCache(initData.kb_docs);
    }
    
    console.log("🎯 티켓 초기화 및 데이터 프리로딩 완료");
    
    // 3초 후 상태 표시 숨기기
    setTimeout(() => {
      hideBackendStatus();
    }, 3000);
    
  } catch (error) {
    console.error("❌ 백엔드 티켓 초기화 실패:", error);
    
    // 오류 상태 표시
    showBackendStatus("error", "초기화 실패", "백엔드 서비스 연결에 실패했습니다. 기본 데이터로 진행합니다.");
    
    // 백엔드 초기화 실패 시에도 기본 UI는 표시
    try {
      await getTicketData();
      console.log("🔄 백엔드 실패 후 기본 데이터로 폴백 완료");
    } catch (fallbackError) {
      console.error("❌ 폴백 데이터 로드도 실패:", fallbackError);
    }
    
    // 5초 후 오류 상태 숨기기
    setTimeout(() => {
      hideBackendStatus();
    }, 5000);
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
    const kbDocs = window.cachedKbDocs;
    if (!kbDocs || kbDocs.length === 0) return;
    
    const container = document.getElementById('suggested-solutions');
    if (!container) return;
    
    let html = '<div class="suggested-solutions-list">';
    html += '<h4>📚 관련 지식베이스 문서 (Pre-loaded)</h4>';
    
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
    
    // If the Similar Tickets tab is active, fetch similar tickets
    const similarTicketsTab = document.querySelector('.tab[data-tab="similar-tickets"]');
    if (similarTicketsTab && similarTicketsTab.classList.contains('active')) {
      fetchSimilarTickets();
    } else {
      document.getElementById('similar-tickets').innerHTML = '<p>Click on this tab to search for similar tickets.</p>';
    }
    
    // Initialize Suggested Solutions tab
    const suggestedSolutionsTab = document.querySelector('.tab[data-tab="suggested-solutions"]');
    if (suggestedSolutionsTab && suggestedSolutionsTab.classList.contains('active')) {
      fetchSuggestedSolutions();
    } else {
      document.getElementById('suggested-solutions').innerHTML = '<p>Click on this tab to view suggested solutions.</p>';
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
 * 백엔드 상태를 UI에 표시하는 함수
 * @param {string} type - 상태 타입 ('loading', 'success', 'error')
 * @param {string} message - 표시할 메시지
 * @param {string} details - 상세 정보 (선택사항)
 */
function showBackendStatus(type, message, details = '') {
  const statusDiv = document.getElementById('backend-status');
  const statusIcon = document.getElementById('status-icon');
  const statusText = document.getElementById('status-text');
  
  if (!statusDiv || !statusIcon || !statusText) return;
  
  // 아이콘 설정
  const icons = {
    loading: '🔄',
    success: '✅',
    error: '❌'
  };
  
  statusIcon.textContent = icons[type] || '🔄';
  statusText.textContent = message;
  
  // 상태 클래스 설정
  statusDiv.className = `backend-status ${type}`;
  
  // 상세 정보가 있으면 추가
  let existingDetails = statusDiv.querySelector('.status-details');
  if (details) {
    if (!existingDetails) {
      existingDetails = document.createElement('div');
      existingDetails.className = 'status-details';
      statusDiv.appendChild(existingDetails);
    }
    existingDetails.textContent = details;
  } else if (existingDetails) {
    existingDetails.remove();
  }
  
  // 표시
  statusDiv.style.display = 'block';
}

/**
 * 백엔드 상태 표시를 숨기는 함수
 */
function hideBackendStatus() {
  const statusDiv = document.getElementById('backend-status');
  if (statusDiv) {
    statusDiv.style.display = 'none';
  }
}