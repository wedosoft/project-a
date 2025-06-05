let client;

/**
 * 공통 모달 트리거 함수
 */
async function showSampleModal() {
  try {
    const data = await client.data.get("ticket");
    const ticket = data.ticket;
    await client.interface.trigger("showModal", {
      title: "Copilot Canvas",
      template: "modal.html",
      data: { showAiTab: false, ticket },
      noBackdrop: true,
      size: {
        width: "800px",
        height: "600px",
      },
    });
    console.log("Modal 열림");
  } catch (err) {
    console.error("Modal 오류", err);
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
      title: "AI Copilot Canvas",
      template: "modal.html",
      data: { showAiTab: true, ticket },
      noBackdrop: true,
      size: {
        width: "800px",
        height: "600px",
      },
    });
    console.log("AI 응답 모달 열림");
  } catch (err) {
    console.error("코파일럿 모달 오류", err);
  }
}

// Get ticket details from Freshdesk using client.data.get
async function getTicketDetails() {
  try {
    const data = await client.data.get("ticket");
    const ticket = data.ticket;

    // Fetch ticket conversations
    try {
      const conversationsData = await client.request.invokeTemplate(
        "getTicketConversations",
        {
          context: {
            subdomain:
              data.iparams.fd_subdomain ||
              window.location.hostname.split(".")[0],
            ticket_id: ticket.id,
            auth: `${data.iparams.fd_api_key}:X`,
          },
        }
      );

      if (conversationsData && conversationsData.response) {
        ticket.conversations = JSON.parse(conversationsData.response);
      }
    } catch (convError) {
      console.error("Error fetching conversations:", convError);
      ticket.conversations = [];
    }

    // Populate ticket summary
    document.getElementById("ticket-subject").textContent =
      ticket.subject || "No subject";
    document.getElementById("ticket-status").textContent =
      ticket.status_name || "Unknown";
    document.getElementById("ticket-priority").textContent =
      ticket.priority_name || "Unknown";
    document.getElementById("ticket-assignee").textContent =
      ticket.agent_name || "Unassigned";

    // Show tags
    const tagsContainer = document.getElementById("ticket-tags");
    tagsContainer.innerHTML = "";

    if (ticket.tags && ticket.tags.length > 0) {
      ticket.tags.forEach(function (tag) {
        const tagEl = document.createElement("span");
        tagEl.classList.add("tag");
        tagEl.textContent = tag;
        tagsContainer.appendChild(tagEl);
      });
    } else {
      tagsContainer.textContent = "No tags";
    }

    // Show description (truncated)
    const description = ticket.description_text || "No description";
    document.getElementById("ticket-description").textContent =
      description.length > 150
        ? description.substring(0, 150) + "..."
        : description;

    // Set up view details button
    document
      .getElementById("view-details-btn")
      .addEventListener("click", function () {
        showTicketDetails(ticket);
      });
  } catch (error) {
    console.error("Error fetching ticket data:", error);
    document.getElementById("ticket-subject").textContent =
      "Error loading ticket details";
    client.interface.trigger("showNotify", {
      type: "error",
      message: "Failed to load ticket details",
    });
  }
}

// Function to insert content into ticket reply
function insertIntoTicketReply(title, description) {
  const content = `<p><strong>${title}</strong></p><p>${description}</p><hr>`;

  // Try to open reply editor and insert the content
  client.interface
    .trigger("click", { id: "reply" })
    .then(function () {
      // Insert the content into the reply editor
      setTimeout(function () {
        client.interface
          .trigger("setValue", {
            id: "reply",
            value: content,
          })
          .catch(function (error) {
            console.error("Error inserting content into reply:", error);
            client.interface.trigger("showNotify", {
              type: "warning",
              message:
                "Could not insert content into reply editor. Please try again.",
            });
          });
      }, 500); // Give time for reply editor to open
    })
    .catch(function (error) {
      console.error("Error opening reply editor:", error);
      client.interface.trigger("showNotify", {
        type: "warning",
        message:
          "Could not open reply editor. Please open it manually before inserting content.",
      });
    });
}

// Show full ticket details in a modal
function showTicketDetails(ticket) {
  client.interface
    .trigger("showModal", {
      title: "Ticket Details",
      template: "dialog.html",
      data: {
        ticket: ticket,
        conversations: ticket.conversations || [],
      },
    })
    .catch(function (error) {
      console.error("Error showing modal:", error);
      client.interface.trigger("showNotify", {
        type: "error",
        message: "Failed to open ticket details",
      });
    });
}

// Fetch similar tickets based on the current ticket's subject and description
async function fetchSimilarTickets() {
  const similarTicketsList = document.getElementById("similar-tickets-list");
  similarTicketsList.innerHTML = "<p>Loading similar tickets...</p>";

  try {
    // Get current ticket data
    const data = await client.data.get("ticket");
    const ticket = data.ticket;

    // Create search query based on subject and description
    let searchTerms = [];
    if (ticket.subject) {
      searchTerms.push(ticket.subject.trim());
    }

    if (ticket.description_text) {
      // Extract some keywords from description (first 50 words)
      const descriptionWords = ticket.description_text
        .split(" ")
        .slice(0, 50)
        .join(" ");
      searchTerms.push(descriptionWords);
    }

    // Build search query - search for tickets with similar subject or description but not the current ticket
    const searchQuery = encodeURIComponent(
      `"${searchTerms.join('" OR "')}" AND NOT ticket_id:${ticket.id}`
    );

    // Prepare auth for basic authentication (base64 encoding will be handled by the template)
    const auth = `${data.iparams.fd_api_key}:X`;

    // Call the search API using our request template
    const response = await client.request.invokeTemplate(
      "searchSimilarTickets",
      {
        context: {
          subdomain:
            data.iparams.fd_subdomain || window.location.hostname.split(".")[0],
          search_query: searchQuery,
          auth: auth,
        },
      }
    );

    // Parse response
    const responseData = JSON.parse(response.response);
    const results = responseData.results || [];

    // Display results
    if (results.length === 0) {
      similarTicketsList.innerHTML = "<p>No similar tickets found.</p>";
      return;
    }

    // Build HTML for results
    let resultsHtml = "";
    results.slice(0, 5).forEach(function (similarTicket) {
      const status = similarTicket.status_name || "Unknown";
      const priority = similarTicket.priority_name || "Unknown";
      const createdAt = new Date(similarTicket.created_at).toLocaleDateString();

      resultsHtml += `
          <div class="result-card" data-ticket-id="${similarTicket.id}">
            <div><strong>${similarTicket.subject}</strong></div>
            <div>Status: ${status} | Priority: ${priority} | Created: ${createdAt}</div>
            <div>${
              similarTicket.description_text
                ? similarTicket.description_text.substring(0, 100) + "..."
                : "No description"
            }</div>
          </div>
        `;
    });

    similarTicketsList.innerHTML = resultsHtml;

    // Add click event listeners to result cards
    document
      .querySelectorAll("#similar-tickets-list .result-card")
      .forEach(function (card) {
        card.addEventListener("click", function () {
          const ticketId = this.getAttribute("data-ticket-id");
          const cardContent = this.querySelector("strong").textContent;
          const cardDescription =
            this.querySelector("div:last-child").textContent;

          // Ask user if they want to insert the content into the reply
          client.interface
            .trigger("showConfirm", {
              title: "Insert Content",
              message: "Would you like to insert this content into your reply?",
              saveLabel: "Yes, Insert",
              cancelLabel: "No",
            })
            .then(function (result) {
              if (result.success) {
                // Insert the content into the reply editor
                insertIntoTicketReply(cardContent, cardDescription);
              } else {
                // Open the ticket in a new tab instead
                client.interface.trigger("click", {
                  id: "openTicket",
                  value: {
                    ticketId: ticketId,
                  },
                });
              }
            })
            .catch(function (error) {
              console.error("Error showing confirmation:", error);
              // Fallback to opening the ticket
              client.interface.trigger("click", {
                id: "openTicket",
                value: {
                  ticketId: ticketId,
                },
              });
            });
        });
      });
  } catch (error) {
    console.error("Error fetching similar tickets:", error);
    similarTicketsList.innerHTML =
      "<p>Error loading similar tickets. Please try again later.</p>";
  }
}

// Set up tab switching functionality
function setupTabs() {
  const tabs = document.querySelectorAll(".tab");
  //let currentTicket = null;

  tabs.forEach(function (tab) {
    tab.addEventListener("click", function () {
      const activeTab = document.querySelector(".tab.active");
      const activeContent = document.querySelector(".tab-content.active");

      // Remove active class from current tab and content
      activeTab.classList.remove("active");
      activeContent.classList.remove("active");

      // Add active class to clicked tab and its content
      const tabId = this.getAttribute("data-tab");
      this.classList.add("active");
      document.getElementById(tabId).classList.add("active");

      // Load data for the selected tab
      if (tabId === "similar-tickets") {
        // Fetch similar tickets when the tab is clicked
        fetchSimilarTickets();
      } else if (tabId === "solutions") {
        // Fetch suggested solutions when the tab is clicked
        fetchSuggestedSolutions();
      } else if (tabId === "copilot") {
        // Set up search button
        document
          .getElementById("copilot-search-btn")
          .addEventListener("click", function () {
            const query = document.getElementById("copilot-query").value;
            if (query.trim()) {
              // Will be implemented in future steps
              document.getElementById("copilot-results").innerHTML =
                "<p>Search functionality will be implemented in the next step.</p>";
            } else {
              document.getElementById("copilot-results").innerHTML =
                "<p>Please enter a search query</p>";
            }
          });
      }
    });
  });
}

app
  .initialized()
  .then((c) => {
    client = c;
    // Get the ticket details
    getTicketDetails();

    // Set up tabs
    setupTabs();

    // ① 상단 네비게이션 앱 아이콘 클릭 시 모달 열기
    client.events.on("app.activated", async () => {
      try {
        const ctx = await client.instance.context();
        if (ctx.location === "ticket_top_navigation") {
          console.log("앱 아이콘 클릭 → 활성화됨");
          await showSampleModal();
        }
      } catch (err) {
        console.error("onAppActivated 오류", err);
      }
    });

    // ② 사이드바 버튼 클릭 시 모달 열기
    const sidebarButton = document.getElementById("openModalBtn");
    if (sidebarButton) {
      sidebarButton.addEventListener("click", () => {
        console.log("사이드바 버튼 클릭 → 모달 열림");
        showSampleModal();
      });
    }

    // ③ AI 응답 버튼 클릭 시 코파일럿 모달 열기
    const copilotButton = document.getElementById("openCopilotBtn");
    if (copilotButton) {
      copilotButton.addEventListener("click", () => {
        console.log("AI 응답 버튼 클릭 → 코파일럿 모달 열림");
        showCopilotModal();
      });
    }
  })
  .catch((err) => console.error("SDK 초기화 실패", err));

// modal.html 전용 초기화
function initModalPage() {
  // Freshdesk 앱 SDK 로드 후 실행
  app.initialized().then(function(client) {
    window.client = client;
    client.instance.context().then(function(context) {
      const ticket = context.data.ticket || {};
      // Ticket Summary
      const ticketDetails = document.getElementById('ticket-details');
      if (ticketDetails) {
        ticketDetails.innerHTML = `
          <div><span class="summary-label">Title</span><span class="summary-value">${ticket.subject || 'N/A'}</span></div>
          <div><span class="summary-label">Status</span><span class="summary-value">${ticket.status_name || 'N/A'}</span></div>
          <div><span class="summary-label">Priority</span><span class="summary-value">${ticket.priority_name || 'N/A'}</span></div>
          <div><span class="summary-label">Assignee</span><span class="summary-value">${ticket.agent_name || 'Unassigned'}</span></div>
          <div><span class="summary-label">Tags</span></div>
          <div><span class="summary-label">Channel</span><span class="summary-value">${ticket.channel || 'N/A'}</span></div>
          <div><span class="summary-label">Created</span><span class="summary-value">${ticket.created_at ? new Date(ticket.created_at).toLocaleString() : 'N/A'}</span></div>
          <div><span class="summary-label">Requester</span><span class="summary-value">${ticket.requester_name || 'N/A'}</span></div>
        `;
      }
      // Tags
      const tagsContainer = document.getElementById('ticket-tags');
      if (tagsContainer) {
        tagsContainer.innerHTML = '';
        if (ticket.tags && ticket.tags.length > 0) {
          ticket.tags.forEach(function(tag) {
            const tagEl = document.createElement('span');
            tagEl.classList.add('tag');
            tagEl.textContent = tag;
            tagsContainer.appendChild(tagEl);
          });
        } else {
          tagsContainer.textContent = 'No tags';
        }
      }
      // Problem, Cause, Result (샘플)
      const problemList = document.getElementById('problem-list');
      if (problemList) problemList.innerHTML = '<li>Error message is displayed when user attempts to log in.</li>';
      const causeList = document.getElementById('cause-list');
      if (causeList) causeList.innerHTML = '<li>Authentication token expired due to browser cache issue.</li>';
      const resultList = document.getElementById('result-list');
      if (resultList) resultList.innerHTML = '<li>Verified successful login is now possible.</li>';
      // Attachment (샘플)
      const attachmentRow = document.getElementById('attachment-row');
      const attachmentName = document.getElementById('attachment-name');
      if (attachmentRow && attachmentName) {
        if (ticket.attachments && ticket.attachments.length > 0) {
          attachmentRow.style.display = '';
          attachmentName.textContent = ticket.attachments[0].name || 'error_screenshot.png';
        } else {
          attachmentRow.style.display = '';
          attachmentName.textContent = 'error_screenshot.png';
        }
      }
      // View Details 버튼
      const viewDetailsBtn = document.getElementById('view-details-btn');
      if (viewDetailsBtn) {
        viewDetailsBtn.onclick = function() {
          client.instance.close();
        };
      }
      // 탭 전환
      document.querySelectorAll('.tab').forEach(function(tab) {
        tab.addEventListener('click', function() {
          document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
          tab.classList.add('active');
          ['similar','solutions','copilot'].forEach(function(name) {
            const el = document.getElementById('tab-' + name);
            if (el) el.style.display = (tab.dataset.tab === name) ? '' : 'none';
          });
        });
      });
      // Copilot 검색 버튼(샘플)
      const copilotForm = document.querySelector('#tab-copilot form');
      if (copilotForm) {
        copilotForm.addEventListener('submit', function(e) {
          e.preventDefault();
         console.log('Copilot 검색 기능은 샘플입니다.');
        });
      }
    });
  });
}

// 페이지가 modal.html일 때만 실행
if (window.location.pathname.includes('modal.html')) {
  initModalPage();
}

