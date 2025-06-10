let client; // Global client variable

app
  .initialized()
  .then((c) => {
    client = c;
    console.log("✅ 앱 초기화 완료");
    console.log("📱 클라이언트 객체:", client);
    
    // ① 상단 네비게이션 앱 아이콘 클릭 시 처리
    client.events.on("app.activated", async () => {
      try {
        const ctx = await client.instance.context();

        // 디버깅: 실제 location 값 확인
        console.log("앱 활성화 - 컨텍스트:", ctx);
        console.log("현재 location:", ctx.location);

        // 상단 네비게이션에서의 동작: 백엔드 데이터 로드 후 모달 표시
        if (ctx.location === "ticket_top_navigation") {
          console.log(
            "상단 네비게이션 아이콘 클릭 → 백엔드 데이터 로드 후 모달 표시"
          );

          // 1단계: 백엔드에서 데이터 로드 (DOM 접근 없이)
          //await loadTicketDataFromBackend();

          // 2단계: 모달 표시
          await showModal();
        } else {
          // 예상치 못한 위치에서의 호출
          console.warn("예상치 못한 위치에서 앱 활성화:", ctx.location);
          //await loadTicketDataFromBackend();
          // Load ticket details for other locations
          //await loadTicketDetails(client);
          setupTabEvents(client);
          setupSearchButton(client);
        }
      } catch (err) {
        console.error("onAppActivated 오류", err);
      }
    });
  })
  .catch((error) => {
    console.error("앱 초기화 실패:", error);
  });
/*
document.addEventListener("DOMContentLoaded", function() {
  init();
});
*/

async function init() {
  try {
    const client = await app.initialized();
    console.log("App initialized");
    
    // Register event for ticket details when app is activated
    client.events.on('app.activated', function() {
      console.log("App activated - loading ticket details");
      loadTicketDetails(client);
      setupTabEvents(client);
      setupSearchButton(client);
    });
  } catch (error) {
    console.error("Error during initialization:", error);
    showError("Failed to initialize the app. Please refresh and try again.");
  }
}

function setupTabEvents(client) {
  const tabs = document.querySelectorAll('[role="tab"]');
  
  tabs.forEach(tab => {
    tab.addEventListener('click', function() {
      const tabId = this.id;
      const targetPanel = this.getAttribute('data-bs-target').substring(1);
      
      console.log(`Tab clicked: ${tabId} targeting panel: ${targetPanel}`);
      
      // Call appropriate function based on which tab was clicked
      switch(tabId) {
        case 'similar-tickets-tab':
          handleSimilarTicketsTab(client, targetPanel);
          break;
        case 'suggested-solutions-tab':
          handleSuggestedSolutionsTab(client, targetPanel);
          break;
        case 'copilot-tab':
          handleCopilotTab(client, targetPanel);
          break;
      }
    });
  });
}

function setupSearchButton(client) {
  const searchButton = document.getElementById('search-button');
  
  searchButton.addEventListener('click', async function() {
    const searchInput = document.getElementById('search-input').value.trim();
    const searchResultsContainer = document.getElementById('search-results');
    
    // Check if search input is empty
    if (!searchInput) {
      searchResultsContainer.innerHTML = '<div class="placeholder-text">Please enter search text</div>';
      return;
    }

    // Collect selected search options
    const searchSubject = document.getElementById('search-subject').checked;
    const searchDescription = document.getElementById('search-description').checked;
    const searchTags = document.getElementById('search-tags').checked;
    
    // Build search query based on selected options
    let searchQuery = "";
    const searchTerms = [];
    
    if (searchSubject) {
      searchTerms.push(`"subject:'${searchInput}'"`);
    }
    
    if (searchDescription) {
      searchTerms.push(`"description:'${searchInput}'"`);
    }
    
    if (searchTags) {
      searchTerms.push(`"tags:'${searchInput}'"`);
    }
    
    // If no search options are selected, default to searching subject
    if (searchTerms.length === 0) {
      searchQuery = `"subject:'${searchInput}'"`;
    } else {
      searchQuery = searchTerms.join(" OR ");
    }
    
    // Show loading state
    searchResultsContainer.innerHTML = '<div class="placeholder-text">Searching tickets...</div>';
    
    try {
      const result = await client.request.invokeTemplate("searchTickets", {
        context: {
          searchQuery: searchQuery
        }
      });
      
      const response = JSON.parse(result.response);
      displaySearchResults(response, searchResultsContainer);
      
    } catch (error) {
      console.error("Error searching tickets:", error);
      searchResultsContainer.innerHTML = '<div class="placeholder-text text-danger">Error searching tickets. Please try again.</div>';
    }
  });
}

function displaySearchResults(response, container) {
  if (!response.results || response.results.length === 0) {
    container.innerHTML = '<div class="placeholder-text">No matching tickets found</div>';
    return;
  }
  
  // Clear previous results
  container.innerHTML = '';
  
  // Create results header
  const resultsHeader = document.createElement('div');
  resultsHeader.className = 'mb-3';
  resultsHeader.innerHTML = `<h6>Found ${response.results.length} matching tickets</h6>`;
  container.appendChild(resultsHeader);
  
  // Create results list
  response.results.forEach(ticket => {
    const ticketCard = document.createElement('div');
    ticketCard.className = 'ticket-card';
    
    // Get status class and text
    const statusText = getStatusText(ticket.status);
    const statusClass = `status-${statusText.toLowerCase()}`;
    
    ticketCard.innerHTML = `
      <div class="ticket-card-header">
        <span class="ticket-card-id">#${ticket.id}</span>
        <span class="ticket-card-status ${statusClass}">${statusText}</span>
      </div>
      <div class="ticket-card-title mt-1 mb-1">
        <strong>${ticket.subject || 'No subject'}</strong>
      </div>
      <div class="ticket-card-meta">
        <small>Priority: ${getPriorityText(ticket.priority)}</small>
      </div>
    `;
    
    // Add click event to open ticket
    ticketCard.addEventListener('click', function() {
      window.open(`https://${window.location.host}/a/tickets/${ticket.id}`, '_blank');
    });
    
    container.appendChild(ticketCard);
  });
}

async function handleSimilarTicketsTab(client, panelId) {
  const panel = document.getElementById(panelId);
  panel.innerHTML = '<div class="placeholder-text">Loading similar tickets...</div>';
  
  try {
    // Get current ticket data
    const ticketData = await client.data.get('ticket');
    
    if (ticketData && ticketData.ticket) {
      const ticket = ticketData.ticket;
      
      // Build search query based on current ticket subject, tags, and description
      let searchTerms = [];
      
      // Add subject search
      if (ticket.subject) {
        searchTerms.push(`"subject:'${ticket.subject}'"`);
      }
      
      // Add tags search if tags exist
      if (ticket.tags && ticket.tags.length > 0) {
        // Join tags with OR for searching
        const tagsQuery = ticket.tags.map(tag => `"tags:'${tag}'"`).join(" OR ");
        searchTerms.push(`(${tagsQuery})`);
      }
      
      // Add description search if description exists
      if (ticket.description_text) {
        // Extract meaningful keywords from description (first 100 chars to avoid too long queries)
        const descriptionExcerpt = ticket.description_text.substring(0, 100).replace(/[^\w\s]/gi, ' ');
        searchTerms.push(`"description:'${descriptionExcerpt}'"`);
      }
      
      // Combine search terms with OR
      const searchQuery = searchTerms.join(" OR ");
      
      console.log("Searching for similar tickets with query:", searchQuery);
      
      // Show searching message
      panel.innerHTML = '<div class="placeholder-text">Finding similar tickets...</div>';
      
      // Fetch similar tickets using the search API
      const result = await client.request.invokeTemplate("searchTickets", {
        context: {
          searchQuery: searchQuery
        }
      });
      
      const response = JSON.parse(result.response);
      
      // Filter out the current ticket from results
      const similarTickets = response.results ? response.results.filter(t => t.id != ticket.id) : [];
      
      // Display similar tickets
      if (similarTickets.length > 0) {
        panel.innerHTML = `
          <div class="similar-tickets-content">
            <div class="mb-3">
              <h6>Found ${similarTickets.length} similar tickets</h6>
            </div>
            <div id="similar-tickets-list"></div>
          </div>
        `;
        
        const ticketsList = document.getElementById('similar-tickets-list');
        
        // Render each similar ticket
        similarTickets.forEach(similarTicket => {
          const ticketCard = document.createElement('div');
          ticketCard.className = 'ticket-card';
          
          // Get status class and text
          const statusText = getStatusText(similarTicket.status);
          const statusClass = `status-${statusText.toLowerCase()}`;
          
          ticketCard.innerHTML = `
            <div class="ticket-card-header">
              <span class="ticket-card-id">#${similarTicket.id}</span>
              <span class="ticket-card-status ${statusClass}">${statusText}</span>
            </div>
            <div class="ticket-card-title mt-1 mb-1">
              <strong>${similarTicket.subject || 'No subject'}</strong>
            </div>
            <div class="ticket-card-meta">
              <small>Priority: ${getPriorityText(similarTicket.priority)}</small>
              ${similarTicket.tags && similarTicket.tags.length > 0 ? 
                `<div class="mt-1"><small>Tags: ${similarTicket.tags.join(', ')}</small></div>` : ''}
            </div>
          `;
          
          // Add click event to open ticket
          ticketCard.addEventListener('click', function() {
            window.open(`https://${window.location.host}/a/tickets/${similarTicket.id}`, '_blank');
          });
          
          ticketsList.appendChild(ticketCard);
        });
      } else {
        panel.innerHTML = '<div class="placeholder-text">No similar tickets found</div>';
      }
    } else {
      panel.innerHTML = '<div class="placeholder-text">Could not fetch ticket details to find similar tickets</div>';
    }
  } catch (error) {
    console.error("Error finding similar tickets:", error);
    panel.innerHTML = '<div class="placeholder-text text-danger">Error loading similar tickets</div>';
  }
}

async function handleSuggestedSolutionsTab(client, panelId) {
  const panel = document.getElementById(panelId);
  panel.innerHTML = '<div class="placeholder-text">Loading suggested solutions...</div>';
  
  try {
    const ticketData = await client.data.get('ticket');
    
    if (ticketData && ticketData.ticket) {
      const ticket = ticketData.ticket;
      
      // Extract search terms from ticket subject and description
      let searchTerms = [];
      
      // Use the ticket subject as primary search term
      if (ticket.subject) {
        searchTerms.push(ticket.subject);
      }
      
      // Extract meaningful keywords from description (if available)
      if (ticket.description_text) {
        // Take first 100 chars of description to avoid too long queries
        const descriptionExcerpt = ticket.description_text.substring(0, 100)
          .replace(/[^\w\s]/gi, ' ')  // Replace non-alphanumeric chars with space
          .split(/\s+/)               // Split by whitespace
          .filter(word => word.length > 3)  // Filter out short words
          .slice(0, 5)                // Take max 5 keywords
          .join(' ');
        
        if (descriptionExcerpt) {
          searchTerms.push(descriptionExcerpt);
        }
      }
      
      // Join search terms with space
      const searchTerm = searchTerms.join(' ').trim();
      
      console.log("Searching for solution articles with term:", searchTerm);
      
      if (!searchTerm) {
        panel.innerHTML = '<div class="placeholder-text">Not enough information in ticket to find solutions</div>';
        return;
      }
      
      // Show searching message
      panel.innerHTML = '<div class="placeholder-text">Finding relevant solutions...</div>';
      
      // Fetch solution articles using the search API
      const result = await client.request.invokeTemplate("searchSolutions", {
        context: {
          searchTerm: searchTerm
        }
      });
      
      const response = JSON.parse(result.response);
      
      // Display solution articles
      if (response && response.length > 0) {
        panel.innerHTML = `
          <div class="suggested-solutions-content">
            <div class="mb-3">
              <h6>Found ${response.length} relevant solution articles</h6>
            </div>
            <div id="suggested-solutions-list"></div>
          </div>
        `;
        
        const solutionsList = document.getElementById('suggested-solutions-list');
        
        // Render each solution article
        response.forEach(solution => {
          const solutionCard = document.createElement('div');
          solutionCard.className = 'ticket-card solution-card';
          
          // Generate HTML snippet for solution article
          solutionCard.innerHTML = `
            <div class="ticket-card-title mt-1 mb-1">
              <strong>${solution.title || 'No title'}</strong>
            </div>
            <div class="ticket-card-meta">
              <small>Category: ${solution.category_name || 'Uncategorized'}</small>
              ${solution.folder_name ? `<div><small>Folder: ${solution.folder_name}</small></div>` : ''}
            </div>
            <div class="mt-2 solution-excerpt">
              ${solution.description ? 
                `<small>${solution.description.substring(0, 100)}${solution.description.length > 100 ? '...' : ''}</small>` : 
                '<small>No description available</small>'}
            </div>
          `;
          
          // Add clickevent to open solution article
          solutionCard.addEventListener('click', function() {
            window.open(`https://${window.location.host}/solution/articles/${solution.id}`, '_blank');
          });
          
          solutionsList.appendChild(solutionCard);
        });
      } else {
        panel.innerHTML = '<div class="placeholder-text">No relevant solution articles found</div>';
      }
    } else {
      panel.innerHTML = '<div class="placeholder-text">Could not fetch ticket details to find solutions</div>';
    }
  } catch (error) {
    console.error("Error in suggested solutions tab:", error);
    panel.innerHTML = '<div class="placeholder-text text-danger">Error loading suggested solutions</div>';
  }
}

async function handleCopilotTab(client, panelId) {
  const panel = document.getElementById(panelId);
  panel.innerHTML = '<div class="placeholder-text">Loading copilot assistance...</div>';
  
  try {
    const ticketData = await client.data.get('ticket');
    
    if (ticketData && ticketData.ticket) {
      const ticket = ticketData.ticket;
      // In a real application, we would provide AI-powered assistance
      // For now, we'll just show a placeholder message
      panel.innerHTML = `
        <div class="copilot-content">
          <p>Copilot assistance for: "${ticket.subject}"</p>
          <div class="placeholder-text">Copilot suggestions will be displayed here once implemented</div>
        </div>
      `;
    } else {
      panel.innerHTML = '<div class="placeholder-text">Could not fetch ticket details for copilot</div>';
    }
  } catch (error) {
    console.error("Error in copilot tab:", error);
    panel.innerHTML = '<div class="placeholder-text text-danger">Error loading copilot assistance</div>';
  }
}

async function loadTicketDetails(client) {
  try {
    const ticketData = await client.data.get('ticket');
    
    if (ticketData && ticketData.ticket) {
      const ticket = ticketData.ticket;
      
      // Update ticket information in the UI
      document.getElementById('ticket-subject').textContent = ticket.subject || 'N/A';
      document.getElementById('ticket-status').textContent = getStatusText(ticket.status) || 'N/A';
      document.getElementById('ticket-priority').textContent = getPriorityText(ticket.priority) || 'N/A';
      document.getElementById('ticket-type').textContent = ticket.type || 'N/A';
    } else {
      showError("Could not fetch ticket details");
    }
  } catch (error) {
    console.error("Error loading ticket details:", error);
    showError("Failed to load ticket information");
  }
}

function getStatusText(statusId) {
  const statuses = {
    2: 'Open',
    3: 'Pending',
    4: 'Resolved',
    5: 'Closed'
  };
  return statuses[statusId] || 'Unknown';
}

function getPriorityText(priorityId) {
  const priorities = {
    1: 'Low',
    2: 'Medium',
    3: 'High',
    4: 'Urgent'
  };
  return priorities[priorityId] || 'Unknown';
}

function showError(message) {
  const elements = [
    'ticket-subject', 
    'ticket-status', 
    'ticket-priority', 
    'ticket-type'
  ];
  
  elements.forEach(id => {
    const element = document.getElementById(id);
    if (element) {
      element.textContent = 'Error loading data';
      element.style.color = 'red';
    }
  });
  console.error(message);
}

/* 공통 모달 트리거 함수
 */
async function showModal() {
  try {
    console.log("🚀 모달 열기 시작");

    // 컨텍스트 정보 가져오기
    const context = await client.instance.context();
    console.log("📍 컨텍스트 정보:", context);

    const data = await client.data.get("ticket");
    const ticket = data.ticket;
    console.log("📋 티켓 데이터 가져옴:", ticket.id);

    // 모달 생성 시 instanceId 포함
    const modalConfig = {
      title: "Copilot Canvas",
      template: "index.html",
      data: {
        showAiTab: false,
        ticket,
        context: context, // 컨텍스트 정보 추가
      },
      noBackdrop: true,
      size: {
        width: "800px",
        height: "600px",
      },
    };

    console.log("🔧 모달 설정:", modalConfig);
    await client.interface.trigger("showModal", modalConfig);
    console.log("✅ 모달 열림 완료");
  } catch (error) {
    console.error("❌ 모달 오류:", error);
    console.error("❌ 모달 오류 스택:", error.stack);

    // 폴백: 간단한 모달로 재시도
    try {
      console.log("🔄 폴백 모달 시도");
      await client.interface.trigger("showModal", {
        title: "Copilot Canvas",
        template: "index.html",
      });
    } catch (fallbackError) {
      console.error("❌ 폴백 모달도 실패:", fallbackError);
    }
  }
}