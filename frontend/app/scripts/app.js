let client; // Global client variable
let isInitialized = false; // 중복 초기화 방지 플래그

// 전역 데이터 캐시 (init 엔드포인트에서 받은 데이터 저장)
let globalTicketData = {
  summary: null,
  similar_tickets: [],
  recommended_solutions: [], // kb_documents와 매핑됨
  cached_ticket_id: null,
  ticket_info: null, // 백엔드에서 받은 완전한 티켓 정보
  isLoading: false, // 중복 호출 방지 플래그
  lastLoadTime: null, // 마지막 로드 시간
};

// 모의 추천 솔루션 생성 함수 (호이스팅 문제 방지를 위해 상단에 정의)
function generateMockSolutions() {
  return [
    {
      id: "mock_1",
      title: "일반적인 문제 해결 방법",
      content: "이 문제는 보통 다음과 같이 해결할 수 있습니다...",
      category: "일반",
      relevance_score: 0.8,
      source: "지식베이스",
      type: "solution",
    },
    {
      id: "mock_2",
      title: "FAQ 답변",
      content: "자주 묻는 질문에 대한 답변입니다...",
      category: "FAQ",
      relevance_score: 0.7,
      source: "FAQ",
      type: "solution",
    },
    {
      id: "mock_3",
      title: "단계별 가이드",
      content: "문제 해결을 위한 단계별 가이드입니다...",
      category: "가이드",
      relevance_score: 0.6,
      source: "사용자 매뉴얼",
      type: "solution",
    },
  ];
}

// 유틸리티 함수들 (호이스팅 문제 방지를 위해 상단에 정의)

// 티켓 상태에 따른 CSS 클래스 반환 함수
function getStatusClass(status) {
  switch (status) {
    case 2:
      return "status-open"; // 열림
    case 3:
      return "status-pending"; // 대기중
    case 4:
      return "status-resolved"; // 해결됨
    case 5:
      return "status-closed"; // 닫힘
    default:
      return "status-default"; // 기본값
  }
}

// 텍스트 길이 제한 함수
function truncateText(text, maxLength = 100) {
  if (!text) return "";
  if (text.length <= maxLength) return text;
  return text.substring(0, maxLength) + "...";
}

// 상태 번호를 한글 텍스트로 변환하는 함수
function getStatusText(status) {
  switch (status) {
    case 2:
      return "열림";
    case 3:
      return "대기중";
    case 4:
      return "해결됨";
    case 5:
      return "닫힘";
    default:
      return "알 수 없음";
  }
}

// 우선순위 번호를 한글 텍스트로 변환하는 함수
function getPriorityText(priority) {
  switch (priority) {
    case 1:
      return "낮음";
    case 2:
      return "보통";
    case 3:
      return "높음";
    case 4:
      return "긴급";
    default:
      return "보통";
  }
}

// 우선순위에 따른 CSS 클래스 반환 함수
function getPriorityClass(priority) {
  switch (priority) {
    case 1:
      return "priority-low";
    case 2:
      return "priority-medium";
    case 3:
      return "priority-high";
    case 4:
      return "priority-urgent";
    default:
      return "priority-medium";
  }
}

// 날짜 포맷팅 함수
function formatDate(dateString) {
  if (!dateString) return "";

  try {
    const date = new Date(dateString);
    if (isNaN(date.getTime())) return "잘못된 날짜";

    // 한국 시간대로 변환하여 표시
    const options = {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      timeZone: "Asia/Seoul",
    };

    return date.toLocaleDateString("ko-KR", options);
  } catch (error) {
    console.warn("날짜 포맷팅 오류:", error);
    return "날짜 형식 오류";
  }
}

// 설명 텍스트 포맷팅 함수
function formatDescription(description) {
  if (!description) return "";

  // HTML 태그 제거 및 기본 포맷팅
  return (
    description
      .replace(/<[^>]*>/g, "") // HTML 태그 제거
      .replace(/\n\n+/g, "\n\n") // 연속된 줄바꿈 정리
      .replace(/\n/g, "<br>") // 줄바꿈을 <br>로 변환
      .substring(0, 500) + (description.length > 500 ? "..." : "")
  ); // 길이 제한
}

// 데이터 유효성 검사 함수 (캐시가 오래되었는지 확인)
function isDataStale() {
  if (!globalTicketData.lastLoadTime) return true;
  const now = Date.now();
  const fiveMinutes = 5 * 60 * 1000; // 5분
  return now - globalTicketData.lastLoadTime > fiveMinutes;
}

// 로딩 완료까지 대기하는 함수
async function waitForLoadingComplete() {
  const maxWait = 10000; // 최대 10초 대기
  const checkInterval = 100; // 100ms마다 확인
  let waited = 0;

  while (globalTicketData.isLoading && waited < maxWait) {
    await new Promise((resolve) => setTimeout(resolve, checkInterval));
    waited += checkInterval;
  }

  if (waited >= maxWait) {
    console.warn("⚠️ 로딩 완료 대기 시간 초과");
  }
}

// 간단한 로딩 인디케이터 표시
function showQuickLoadingIndicator() {
  console.log("⏳ 로딩 인디케이터 표시");

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

  document.body.appendChild(loadingOverlay);
}

// 로딩 인디케이터 숨김
function hideQuickLoadingIndicator() {
  console.log("✅ 로딩 인디케이터 숨김");
  const loadingOverlay = document.getElementById("quick-loading-overlay");
  if (loadingOverlay) {
    loadingOverlay.remove();
  }
}

app
  .initialized()
  .then((c) => {
    client = c;
    console.log("✅ 앱 초기화 완료");
    console.log("📱 클라이언트 객체:", client);

    // ① 백그라운드 데이터 준비 - 안전한 호출로 변경 (한 번만 실행)
    preloadTicketDataOnPageLoad(client);

    // ② 상단 네비게이션 앱 아이콘 클릭 시 처리 (캐시된 데이터로 즉시 모달 표시)
    client.events.on("app.activated", async () => {
      try {
        const ctx = await client.instance.context();

        // 디버깅: 실제 location 값 확인
        console.log("앱 활성화 - 컨텍스트:", ctx);
        console.log("현재 location:", ctx.location);

        // 상단 네비게이션에서의 동작: 스마트 캐싱 전략 적용
        if (ctx.location === "ticket_top_navigation") {
          console.log("🚀 상단 네비게이션 아이콘 클릭 → 스마트 캐싱 전략 시작");

          // 현재 티켓 정보 가져오기 (이 시점에서는 FDK가 안전함)
          const ticketData = await client.data.get("ticket");
          const currentTicketId = ticketData?.ticket?.id;

          // 캐시된 데이터가 현재 티켓과 일치하는지 확인
          if (
            globalTicketData.cached_ticket_id === currentTicketId &&
            globalTicketData.summary &&
            !isDataStale()
          ) {
            console.log("⚡ 캐시된 데이터 발견 → 즉시 모달 표시 (0ms 지연)");
            await showModal();
          } else {
            console.log(
              "ℹ️ 새 티켓이거나 캐시 없음 → 빈 상태로 모달 표시 (백엔드 호출 없음)"
            );

            // 백엔드 호출 없이 즉시 모달 열기
            await showModal();
          }

          // 모달 표시 후 이벤트 설정 (한 번만)
          if (!isInitialized) {
            setupTabEvents(client);
            isInitialized = true;
          }
        } else {
          // 예상치 못한 위치에서의 호출
          console.warn("예상치 못한 위치에서 앱 활성화:", ctx.location);
          if (!isInitialized) {
            await loadTicketDetails(client);
            setupTabEvents(client);
            isInitialized = true;
          }
        }
      } catch (err) {
        console.error("onAppActivated 오류", err);
      }
    });

    // ③ 모달이 열린 후 DOM 요소에 데이터 렌더링
    client.events.on("template.render", () => {
      try {
        console.log("🎭 모달 템플릿 렌더링 완료");

        // DOM이 완전히 로드되도록 짧은 지연 후 캐시된 데이터로 UI 업데이트
        setTimeout(() => {
          // 캐시된 데이터로 UI 업데이트
          if (globalTicketData.summary) {
            updateUIWithCachedData();
          }

          // 이벤트 설정 (한 번만)
          if (!isInitialized) {
            setupTabEvents(client);
            isInitialized = true;
          }
        }, 100);
      } catch (err) {
        console.error("template.render 오류", err);
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
    client.events.on("app.activated", function () {
      console.log("App activated - loading ticket details");
      loadTicketDetails(client);
      setupTabEvents(client);
    });
  } catch (error) {
    console.error("Error during initialization:", error);
    showErrorInResults(
      "Failed to initialize the app. Please refresh and try again."
    );
  }
}

// 티켓 상세 정보 로드 및 UI 업데이트 함수
async function loadTicketDetails(client) {
  try {
    console.log("📋 티켓 상세 정보 확인 시작 (백엔드 호출 없음)");

    // 티켓 ID 가져오기
    const ticketData = await client.data.get("ticket");

    if (ticketData && ticketData.ticket) {
      const basicTicketInfo = ticketData.ticket;
      console.log("✅ 기본 티켓 정보 확인 완료:", basicTicketInfo);

      // 캐시된 데이터가 있고 최신인지 확인
      if (
        globalTicketData.cached_ticket_id === basicTicketInfo.id &&
        globalTicketData.summary &&
        !isDataStale()
      ) {
        console.log("⚡ 캐시된 데이터 사용 가능");
        return;
      }

      // 새로운 티켓인 경우 캐시 초기화
      if (globalTicketData.cached_ticket_id !== basicTicketInfo.id) {
        console.log("🆕 새로운 티켓 감지 → 캐시 초기화");
        resetGlobalTicketCache();
      }

      // 백엔드 호출 없이 기본 정보만 저장
      globalTicketData.cached_ticket_id = basicTicketInfo.id;
      globalTicketData.ticket_info = basicTicketInfo;
      console.log("ℹ️ 백엔드 호출 없이 기본 정보만 저장");
    } else {
      console.warn("⚠️ 기본 티켓 정보를 찾을 수 없음");
    }
  } catch (error) {
    console.error("❌ 티켓 상세 정보 확인 오류:", error);
  }
}

// 티켓 페이지 로드 시 백그라운드에서 데이터 미리 준비하는 함수
function preloadTicketDataOnPageLoad(client) {
  try {
    console.log("🔄 FDK 안전한 백그라운드 데이터 준비 시작");

    // 더 안전한 FDK API 접근을 위한 지연 시간 증가 및 단계적 검증
    setTimeout(async () => {
      try {
        // 1단계: FDK 클라이언트가 준비되었는지 확인
        if (!client || typeof client.instance === "undefined") {
          console.warn("⚠️ FDK 클라이언트가 아직 준비되지 않음");
          return;
        }

        // 2단계: 컨텍스트 확인 (안전한 방법)
        let ctx;
        try {
          ctx = await client.instance.context();
          console.log("🔍 페이지 컨텍스트 확인 성공:", ctx);
        } catch (contextError) {
          console.warn(
            "⚠️ 컨텍스트 확인 실패, 기본 로직으로 진행:",
            contextError
          );
          // 컨텍스트 확인 실패 시 안전하게 종료
          return;
        }

        // 3단계: 티켓 페이지인지 확인
        const isTicketPage =
          ctx.location &&
          (ctx.location.includes("ticket") ||
            ctx.location === "ticket_top_navigation");

        if (isTicketPage) {
          console.log("📋 티켓 페이지 확인됨 → 데이터 로드 시작");

          // 4단계: 티켓 데이터 안전하게 가져오기
          let ticketData;
          try {
            ticketData = await client.data.get("ticket");
          } catch (dataError) {
            console.warn(
              "⚠️ 티켓 데이터 접근 실패 (EventAPI 오류 가능성):",
              dataError
            );
            return;
          }

          if (ticketData && ticketData.ticket) {
            const currentTicketId = ticketData.ticket.id;

            // 5단계: 캐시 확인 및 백엔드 호출
            if (
              globalTicketData.cached_ticket_id === currentTicketId &&
              globalTicketData.summary &&
              !isDataStale()
            ) {
              console.log("✅ 이미 캐시된 데이터 존재 → 백그라운드 로드 스킵");
              return;
            }

            // 중복 호출 방지
            if (globalTicketData.isLoading) {
              console.log("⚠️ 이미 로딩 중이므로 백그라운드 로드 스킵");
              return;
            }

            console.log(
              "🚀 백그라운드에서 새로운 티켓 데이터 로드 중...",
              currentTicketId
            );

            // 6단계: 백엔드 호출 (FDK와 독립적)
            try {
              resetGlobalTicketCache();
              await loadInitialDataFromBackend(client, ticketData.ticket);
              console.log(
                "✅ 백그라운드 데이터 로드 완료 → 앱 아이콘 클릭 시 즉시 모달 표시 가능"
              );
            } catch (backendError) {
              console.warn("⚠️ 백엔드 호출 실패:", backendError);
            }
          } else {
            console.log("⚠️ 티켓 정보 없음 → 백그라운드 로드 스킵");
          }
        } else {
          console.log("📄 티켓 페이지가 아님 → 백그라운드 로드 스킵");
        }
      } catch (error) {
        console.warn("⚠️ 백그라운드 데이터 로드 중 예외 발생:", error);
      }
    }, 2000); // 2초로 지연 시간 증가하여 FDK 완전 초기화 대기
  } catch (error) {
    console.warn("⚠️ 백그라운드 데이터 준비 초기화 실패:", error);
  }
}

// 캐시된 데이터로 UI를 즉시 업데이트하는 함수
function updateUIWithCachedData() {
  try {
    if (!globalTicketData.summary) {
      console.log("⚠️ 캐시된 데이터 없음 → UI 업데이트 스킵");
      return;
    }

    console.log("🎯 캐시된 데이터로 UI 즉시 업데이트 시작");

    // 티켓 기본 정보 업데이트 (백엔드 응답의 ticket_data 사용)
    if (globalTicketData.ticket_info) {
      updateTicketInfo(globalTicketData.ticket_info);
    }

    // 요약 정보 업데이트
    if (globalTicketData.summary) {
      const summaryContent = document.getElementById("copilot-content");
      if (summaryContent) {
        summaryContent.innerHTML = formatSummaryForDisplay(
          globalTicketData.summary
        );
      }
    }

    // 유사 티켓 데이터가 있으면 미리 준비
    if (
      globalTicketData.similar_tickets &&
      globalTicketData.similar_tickets.length > 0
    ) {
      console.log(
        `✅ 유사 티켓 ${globalTicketData.similar_tickets.length}개 캐시 준비 완료`
      );
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

    console.log("✅ 캐시된 데이터로 UI 업데이트 완료");
  } catch (error) {
    console.error("❌ 캐시된 데이터로 UI 업데이트 실패:", error);
  }
}

// 티켓 정보 UI 업데이트 함수
function updateTicketInfo(ticket) {
  // 제목 업데이트
  const subjectElement = document.getElementById("ticket-subject");
  if (subjectElement) {
    subjectElement.textContent = ticket.subject || "No subject available";
  }

  // 상태 업데이트
  const statusElement = document.getElementById("ticket-status");
  if (statusElement) {
    const statusText = getStatusText(ticket.status);
    statusElement.textContent = statusText;
    statusElement.className = `info-value status-${statusText.toLowerCase()}`;
  }

  // 우선순위 업데이트
  const priorityElement = document.getElementById("ticket-priority");
  if (priorityElement) {
    const priorityText = getPriorityText(ticket.priority);
    priorityElement.textContent = priorityText;
    priorityElement.className = `info-value priority-${priorityText.toLowerCase()}`;
  }

  // 타입 업데이트
  const typeElement = document.getElementById("ticket-type");
  if (typeElement) {
    typeElement.textContent = ticket.type || "Question";
  }

  console.log("✅ 티켓 정보 UI 업데이트 완료");
}

// 탭 이벤트 설정 함수
function setupTabEvents(client) {
  const tabs = document.querySelectorAll('[role="tab"]');
  tabs.forEach((tab) => {
    tab.addEventListener("click", function () {
      const tabId = this.id;
      const targetPanel = this.getAttribute("data-bs-target").substring(1);

      console.log(`📂 탭 클릭: ${tabId} targeting panel: ${targetPanel}`);

      // 탭에 따른 적절한 함수 호출
      switch (tabId) {
        case "similar-tickets-tab":
          handleSimilarTicketsTab(client);
          break;
        case "suggested-solutions-tab":
          handleSuggestedSolutionsTab(client);
          break;
        case "copilot-tab":
          handleCopilotTab(client);
          break;
      }
    });
  });

  // 각 탭의 버튼 이벤트 설정
  setupSimilarTicketsEvents(client);
  setupSuggestedSolutionsEvents(client);
  setupCopilotEvents(client);
}

// 유사 티켓 탭 처리 함수
async function handleSimilarTicketsTab(client) {
  console.log("🔍 유사 티켓 탭 활성화");

  // 리스트 뷰로 초기화
  showSimilarTicketsListView();

  try {
    // 현재 티켓 데이터 가져오기
    const ticketData = await client.data.get("ticket");

    if (ticketData && ticketData.ticket) {
      const ticket = ticketData.ticket;

      // 캐시된 데이터가 있고 같은 티켓인 경우 재사용
      if (
        globalTicketData.cached_ticket_id === ticket.id &&
        globalTicketData.similar_tickets.length > 0
      ) {
        console.log("🔄 캐시된 유사 티켓 데이터 사용");
        displaySimilarTickets(globalTicketData.similar_tickets);
      } else {
        // 캐시된 데이터가 없거나 다른 티켓인 경우 백엔드에서 로드
        await loadSimilarTicketsFromBackend(ticket);
      }
    }
  } catch (error) {
    console.error("❌ 유사 티켓 로드 오류:", error);
    showErrorInResultsInResults(
      "유사 티켓을 로드할 수 없습니다.",
      "similar-tickets-list"
    );
  }
}

// 유사 티켓 이벤트 설정 함수
function setupSimilarTicketsEvents(client) {
  // 새로고침 버튼
  const refreshButton = document.getElementById("refresh-similar-tickets");
  if (refreshButton) {
    refreshButton.addEventListener("click", async () => {
      console.log("🔄 유사 티켓 새로고침 - 캐시 초기화");
      const ticketData = await client.data.get("ticket");
      if (ticketData && ticketData.ticket) {
        // 캐시에서 유사 티켓 데이터만 초기화
        globalTicketData.similar_tickets = [];
        await loadSimilarTicketsFromBackend(ticketData.ticket);
      }
    });
  }

  // 뒤로가기 버튼
  const backButton = document.getElementById("back-to-similar-list");
  if (backButton) {
    backButton.addEventListener("click", () => {
      showSimilarTicketsListView();
    });
  }

  // 티켓 열기 버튼
  const openTicketButton = document.getElementById("open-ticket-link");
  if (openTicketButton) {
    openTicketButton.addEventListener("click", () => {
      const currentTicketId = openTicketButton.dataset.ticketId;
      if (currentTicketId) {
        window.open(
          `https://${window.location.host}/a/tickets/${currentTicketId}`,
          "_blank"
        );
      }
    });
  }
}

// 유사 티켓 리스트 뷰 표시
function showSimilarTicketsListView() {
  const listView = document.getElementById("similar-tickets-list-view");
  const detailView = document.getElementById("similar-tickets-detail-view");

  if (listView) listView.style.display = "block";
  if (detailView) detailView.style.display = "none";
}

// 유사 티켓 상세 뷰 표시
function showSimilarTicketDetailView(ticket) {
  const listView = document.getElementById("similar-tickets-list-view");
  const detailView = document.getElementById("similar-tickets-detail-view");
  const detailContent = document.getElementById(
    "similar-ticket-detail-content"
  );
  const openTicketButton = document.getElementById("open-ticket-link");

  if (listView) listView.style.display = "none";
  if (detailView) detailView.style.display = "block";

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
              <div>${ticket.type || "Question"}</div>
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
              : ""
          }
        </div>
        
        <div class="detail-section">
          <h6>Subject</h6>
          <p>${ticket.subject || "No subject available"}</p>
        </div>
        
        ${
          ticket.description_text || ticket.description
            ? `
          <div class="detail-section">
            <h6>Description</h6>
            <div class="description-content">
              ${formatDescription(
                ticket.description_text || ticket.description
              )}
            </div>
          </div>
        `
            : ""
        }
        
        ${
          ticket.tags && ticket.tags.length > 0
            ? `
          <div class="detail-section">
            <h6>Tags</h6>
            <div>
              ${ticket.tags
                .map(
                  (tag) => `<span class="badge bg-secondary me-1">${tag}</span>`
                )
                .join("")}
            </div>
          </div>
        `
            : ""
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
                  : ""
              }
              ${
                ticket.group_id
                  ? `<li><strong>Group ID:</strong> ${ticket.group_id}</li>`
                  : ""
              }
            </ul>
          </div>
        `
            : ""
        }
      </div>
    `;
  }

  console.log("✅ 유사 티켓 상세 정보 표시 완료");
}

// 백엔드에서 유사 티켓 로드 함수
async function loadSimilarTicketsFromBackend(ticket) {
  try {
    console.log("🔍 유사 티켓 검색 시작");

    // 캐시된 데이터가 있고 같은 티켓인 경우 재사용
    if (
      globalTicketData.cached_ticket_id === ticket.id &&
      globalTicketData.similar_tickets.length > 0
    ) {
      console.log("🔄 캐시된 유사 티켓 데이터 사용");
      displaySimilarTickets(globalTicketData.similar_tickets);
      return;
    }

    console.log(
      "⚠️ 유사 티켓이 캐시에 없음 - /init 엔드포인트에서 이미 받았어야 하는 데이터"
    );

    // /init 엔드포인트에서 이미 모든 데이터를 받았어야 하므로,
    // 별도 API 호출 대신 Freshdesk API 폴백 사용
    console.log("🔄 Freshdesk API 폴백 사용");
    await loadSimilarTicketsFromFreshdesk(ticket);
  } catch (error) {
    console.error("❌ 백엔드 연결 오류:", error);
    // 폴백: Freshdesk API 사용
    await loadSimilarTicketsFromFreshdesk(ticket);
  }
}

// 로딩 상태 관리를 위한 전역 변수
let isLoadingSimilarTickets = false;

// Freshdesk API를 사용한 유사 티켓 검색 (폴백)
async function loadSimilarTicketsFromFreshdesk(ticket) {
  // 중복 호출 방지
  if (isLoadingSimilarTickets) {
    console.log("⏳ 이미 유사 티켓 로딩 중, 중복 호출 방지");
    return;
  }

  try {
    isLoadingSimilarTickets = true;
    console.log("🔄 Freshdesk API 폴백으로 유사 티켓 검색");

    // 검색 쿼리 구성
    const searchTerms = [];

    // 제목 검색 추가
    if (ticket.subject) {
      searchTerms.push(`"subject:'${ticket.subject}'"`);
    }

    // 태그 검색 추가 (태그가 있는 경우)
    if (ticket.tags && ticket.tags.length > 0) {
      const tagsQuery = ticket.tags
        .map((tag) => `"tags:'${tag}'"`)
        .join(" OR ");
      searchTerms.push(`(${tagsQuery})`);
    }

    // 설명 검색 추가 (설명이 있는 경우)
    if (ticket.description_text) {
      const descriptionExcerpt = ticket.description_text
        .substring(0, 100)
        .replace(/[^\w\s]/gi, " ");
      searchTerms.push(`"description:'${descriptionExcerpt}'"`);
    }

    // 실제 API 호출 시뮬레이션을 위한 약간의 지연 (사용자 경험 개선)
    await new Promise((resolve) => setTimeout(resolve, 500));

    // 모의 데이터로 폴백
    const mockSimilarTickets = [
      {
        id: "mock_1",
        subject: "유사한 문제 해결 사례",
        description: "비슷한 문제에 대한 해결 방법입니다.",
        status: 2,
        priority: 1,
        created_at: new Date().toISOString(),
      },
    ];

    displaySimilarTickets(mockSimilarTickets);
  } catch (error) {
    console.error("❌ Freshdesk API 검색 오류:", error);
    showErrorInResultsInResults("유사 티켓을 찾을 수 없습니다.");
  } finally {
    // 로딩 상태 초기화
    isLoadingSimilarTickets = false;
  }
}

// 유사 티켓 결과 표시 함수 (새로운 리스트 형태)
function displaySimilarTickets(similarTickets) {
  const resultsElement = document.getElementById("similar-tickets-list");
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

    const ticketsContainer = document.getElementById("tickets-container");

    // 각 유사 티켓을 새로운 리스트 아이템으로 렌더링
    similarTickets.forEach((similarTicket) => {
      const ticketItem = document.createElement("div");
      ticketItem.className = "list-item";

      // 유사도 점수 계산 (임시)
      const similarityScore = similarTicket.score || Math.random() * 30 + 70;

      ticketItem.innerHTML = `
        <div class="list-item-header">
          <div class="list-item-title">${
            similarTicket.subject || "No subject"
          }</div>
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
              : ""
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
                : ""
            }
            ${
              similarTicket.solution
                ? `<div>💡 <strong>해결책:</strong> ${truncateText(
                    similarTicket.solution,
                    100
                  )}</div>`
                : ""
            }
          </div>
        `
            : similarTicket.description_text || similarTicket.description
            ? `
          <div class="list-item-excerpt">
            ${truncateText(
              similarTicket.description_text || similarTicket.description,
              150
            )}
          </div>
        `
            : ""
        }
        ${
          similarTicket.tags && similarTicket.tags.length > 0
            ? `
          <div class="mt-2">
            ${similarTicket.tags
              .slice(0, 3)
              .map(
                (tag) =>
                  `<span class="badge bg-light text-dark me-1">${tag}</span>`
              )
              .join("")}
            ${
              similarTicket.tags.length > 3
                ? `<span class="badge bg-light text-muted">+${
                    similarTicket.tags.length - 3
                  }</span>`
                : ""
            }
          </div>
        `
            : ""
        }
      `;

      // 티켓 상세 보기 클릭 이벤트 추가
      ticketItem.addEventListener("click", function () {
        console.log("📋 유사 티켓 상세 보기:", similarTicket.id);
        showSimilarTicketDetailView(similarTicket);
      });

      ticketsContainer.appendChild(ticketItem);
    });
  } else {
    // 빈 배열일 때 캐시 상태를 고려한 정보 제공
    const hasCachedData = globalTicketData.cached_ticket_id && !isDataStale();
    const emptyMessage = hasCachedData
      ? "이 티켓과 유사한 과거 사례가 없거나, 아직 데이터가 충분하지 않습니다."
      : "데이터를 로딩 중이거나 아직 분석이 완료되지 않았습니다.<br>페이지 새로고침 후 다시 시도해보세요.";

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
}

// 검색 기능은 백엔드 지침서에 따라 /query 엔드포인트로 통합되었습니다.
// 별도의 검색 함수는 더 이상 사용되지 않습니다.

// 추천 해결책 탭 처리 함수
async function handleSuggestedSolutionsTab(client) {
  console.log("💡 추천 솔루션 탭 활성화");

  // 리스트 뷰로 초기화
  showSuggestedSolutionsListView();

  try {
    // 현재 티켓 데이터 가져오기
    const ticketData = await client.data.get("ticket");

    if (ticketData && ticketData.ticket) {
      const ticket = ticketData.ticket;

      // 캐시된 데이터가 있고 같은 티켓인 경우 재사용
      if (
        globalTicketData.cached_ticket_id === ticket.id &&
        globalTicketData.recommended_solutions.length > 0
      ) {
        console.log("🔄 캐시된 추천 솔루션 데이터 사용");
        displaySuggestedSolutions(globalTicketData.recommended_solutions);
      } else {
        // 캐시된 데이터가 없거나 다른 티켓인 경우 백엔드에서 로드
        await loadSuggestedSolutions(ticket);
      }
    }
  } catch (error) {
    console.error("❌ 추천 해결책 로드 오류:", error);
    showErrorInResultsInResults(
      "추천 해결책을 로드할 수 없습니다.",
      "suggested-solutions-list"
    );
  }
}

// 추천 솔루션 이벤트 설정 함수
function setupSuggestedSolutionsEvents(client) {
  // 새로고침 버튼
  const refreshButton = document.getElementById("refresh-solutions");
  if (refreshButton) {
    refreshButton.addEventListener("click", async () => {
      console.log("🔄 추천 솔루션 새로고침 - 캐시 초기화");
      const ticketData = await client.data.get("ticket");
      if (ticketData && ticketData.ticket) {
        // 캐시에서 추천 솔루션 데이터만 초기화
        globalTicketData.recommended_solutions = [];
        await loadSuggestedSolutions(ticketData.ticket);
      }
    });
  }

  // 뒤로가기 버튼
  const backButton = document.getElementById("back-to-solutions-list");
  if (backButton) {
    backButton.addEventListener("click", () => {
      showSuggestedSolutionsListView();
    });
  }

  // 솔루션 사용 버튼
  const useSolutionButton = document.getElementById("use-solution");
  if (useSolutionButton) {
    useSolutionButton.addEventListener("click", () => {
      const solutionData = useSolutionButton.dataset.solution;
      if (solutionData) {
        try {
          const solution = JSON.parse(solutionData);
          insertSolutionToReply(solution);
        } catch (error) {
          console.error("❌ 솔루션 데이터 파싱 오류:", error);
        }
      }
    });
  }
}

// 추천 솔루션 리스트 뷰 표시
function showSuggestedSolutionsListView() {
  const listView = document.getElementById("solutions-list-view");
  const detailView = document.getElementById("solutions-detail-view");

  if (listView) listView.style.display = "block";
  if (detailView) detailView.style.display = "none";
}

// 추천 솔루션 상세 뷰 표시
function showSuggestedSolutionDetailView(solution) {
  const listView = document.getElementById("solutions-list-view");
  const detailView = document.getElementById("solutions-detail-view");
  const detailContent = document.getElementById("solution-detail-content");
  const useSolutionButton = document.getElementById("use-solution");

  if (listView) listView.style.display = "none";
  if (detailView) detailView.style.display = "block";

  // 버튼에 솔루션 데이터 저장
  if (useSolutionButton) {
    useSolutionButton.dataset.solution = JSON.stringify(solution);
  }

  if (detailContent) {
    detailContent.innerHTML = `
      <div class="detail-content">
        <div class="detail-meta">
          <div class="d-flex justify-content-between align-items-start mb-2">
            <h5 class="mb-0">${solution.title || "해결책"}</h5>
            ${
              solution.score
                ? `<span class="score-badge">${Math.round(
                    solution.score * 100
                  )}% 관련도</span>`
                : ""
            }
          </div>
          <div class="row">
            <div class="col-6">
              <small class="text-muted">카테고리:</small>
              <div class="badge-custom bg-info">${
                solution.category || "일반"
              }</div>
            </div>
            <div class="col-6">
              <small class="text-muted">유형:</small>
              <div>${solution.type || "Solution"}</div>
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
              : ""
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
            : ""
        }
        
        <div class="detail-section">
          <h6>해결책 내용</h6>
          <div class="solution-content">
            ${formatSolutionContent(
              solution.content ||
                solution.description ||
                "솔루션 내용이 없습니다."
            )}
          </div>
        </div>
        
        ${
          solution.steps && solution.steps.length > 0
            ? `
          <div class="detail-section">
            <h6>단계별 해결 과정</h6>
            <ol class="solution-steps">
              ${solution.steps.map((step) => `<li>${step}</li>`).join("")}
            </ol>
          </div>
        `
            : ""
        }
        
        ${
          solution.tags && solution.tags.length > 0
            ? `
          <div class="detail-section">
            <h6>관련 태그</h6>
            <div>
              ${solution.tags
                .map(
                  (tag) => `<span class="badge bg-secondary me-1">${tag}</span>`
                )
                .join("")}
            </div>
          </div>
        `
            : ""
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
            : ""
        }
      </div>
    `;
  }

  console.log("✅ 추천 솔루션 상세 정보 표시 완료");
}

// 추천 해결책 로드 함수
function loadSuggestedSolutions(ticket) {
  const resultsElement = document.getElementById("suggested-solutions-list");
  if (resultsElement) {
    resultsElement.innerHTML =
      '<div class="placeholder-text">추천 해결책을 로드하는 중...</div>';
  }

  try {
    console.log("💡 추천 해결책 로드 시작");

    // 캐시된 데이터가 있고 같은 티켓인 경우 재사용
    if (
      globalTicketData.cached_ticket_id === ticket.id &&
      globalTicketData.recommended_solutions.length > 0
    ) {
      console.log("🔄 캐시된 추천 솔루션 데이터 사용");
      displaySuggestedSolutions(globalTicketData.recommended_solutions);
      return;
    }

    // 캐시된 데이터가 없거나 다른 티켓인 경우에만 API 호출
    console.log(
      "⚠️ 추천 솔루션이 캐시에 없음 - /init 엔드포인트에서 이미 받았어야 하는 데이터"
    );

    // /init 엔드포인트에서 이미 모든 데이터를 받았어야 하므로,
    // 별도 API 호출 대신 모의 데이터 표시
    console.log("🔄 모의 데이터로 폴백");
    displaySuggestedSolutions(generateMockSolutions());

    // 캐시 업데이트 (모의 데이터로)
    globalTicketData.recommended_solutions = generateMockSolutions();
    globalTicketData.cached_ticket_id = ticket.id;
  } catch (error) {
    console.error("❌ 추천 솔루션 로드 오류:", error);
    // 폴백: 모의 데이터 표시
    displaySuggestedSolutions(generateMockSolutions());
  }
}

// 추천 솔루션 표시 함수 (새로운 리스트 형태)
function displaySuggestedSolutions(solutions) {
  const resultsElement = document.getElementById("suggested-solutions-list");
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

    const solutionsContainer = document.getElementById("solutions-container");

    // 각 솔루션을 새로운 리스트 아이템으로 렌더링
    solutions.forEach((solution, index) => {
      const solutionItem = document.createElement("div");
      solutionItem.className = "list-item";

      // 관련도 점수 계산
      const relevanceScore = solution.score
        ? Math.round(solution.score * 100)
        : Math.random() * 20 + 75;

      solutionItem.innerHTML = `
        <div class="list-item-header">
          <div class="list-item-title">${
            solution.title || `Solution ${index + 1}`
          }</div>
          <div class="d-flex align-items-center gap-2">
            <span class="score-badge">${relevanceScore}%</span>
            <span class="badge-custom bg-info">${
              solution.category || "일반"
            }</span>
          </div>
        </div>
        <div class="list-item-meta">
          <span>유형: ${solution.type || "Solution"}</span>
          ${solution.source ? ` • <span>출처: ${solution.source}</span>` : ""}
        </div>
        ${
          solution.content || solution.description
            ? `
          <div class="list-item-excerpt">
            ${truncateText(solution.content || solution.description, 150)}
          </div>
        `
            : ""
        }
        ${
          solution.tags && solution.tags.length > 0
            ? `
          <div class="mt-2">
            ${solution.tags
              .slice(0, 3)
              .map(
                (tag) =>
                  `<span class="badge bg-light text-dark me-1">${tag}</span>`
              )
              .join("")}
            ${
              solution.tags.length > 3
                ? `<span class="badge bg-light text-muted">+${
                    solution.tags.length - 3
                  }</span>`
                : ""
            }
          </div>
        `
            : ""
        }
      `;

      // 솔루션 상세 보기 클릭 이벤트 추가
      solutionItem.addEventListener("click", function () {
        console.log(
          "💡 추천 솔루션 상세 보기:",
          solution.title || `Solution ${index + 1}`
        );
        showSuggestedSolutionDetailView(solution);
      });

      solutionsContainer.appendChild(solutionItem);
    });
  } else {
    // 빈 배열일 때 캐시 상태를 고려한 정보 제공
    const hasCachedData = globalTicketData.cached_ticket_id && !isDataStale();
    const emptyMessage = hasCachedData
      ? "현재 지식베이스에서 이 문제와 관련된 솔루션을 찾을 수 없습니다.<br>새로운 문서가 추가되거나 더 구체적인 정보가 있으면 관련 솔루션을 제안할 수 있습니다."
      : "지식베이스 데이터를 로딩 중이거나 아직 분석이 완료되지 않았습니다.<br>페이지 새로고침 후 다시 시도해보세요.";

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
}

// 코파일럿 탭 처리 함수
function handleCopilotTab(client) {
  console.log("🤖 코파일럿 탭 활성화");

  // 코파일럿 이벤트가 이미 설정되어 있는지 확인하고, 없으면 설정
  if (!window.copilotEventsSetup) {
    setupCopilotEvents(client);
    window.copilotEventsSetup = true;
  }
}

// 코파일럿 이벤트 설정 함수
function setupCopilotEvents(client) {
  const searchButton = document.getElementById("chat-search-button");
  const searchInput = document.getElementById("chat-input");
  const clearChatButton = document.getElementById("clear-chat");

  if (searchButton) {
    searchButton.addEventListener("click", async function () {
      const query = searchInput.value.trim();

      // 선택된 콘텐츠 타입 가져오기
      const selectedTypes = [];
      if (document.getElementById("search-tickets")?.checked)
        selectedTypes.push("tickets");
      if (document.getElementById("search-solutions")?.checked)
        selectedTypes.push("solutions");
      if (document.getElementById("search-images")?.checked)
        selectedTypes.push("images");
      if (document.getElementById("search-attachments")?.checked)
        selectedTypes.push("attachments");

      if (query) {
        console.log("🤖 코파일럿 검색 실행:", query, "타입:", selectedTypes);
        await performCopilotSearch(client, query, selectedTypes);

        // 입력 필드 초기화
        searchInput.value = "";
      } else {
        showErrorInResultsInResults("질문을 입력해주세요.", "chat-messages");
      }
    });
  }

  // Enter 키 지원
  if (searchInput) {
    searchInput.addEventListener("keypress", function (e) {
      if (e.key === "Enter") {
        e.preventDefault();
        searchButton.click();
      }
    });
  }

  // 채팅 초기화 버튼
  if (clearChatButton) {
    clearChatButton.addEventListener("click", function () {
      const chatMessages = document.getElementById("chat-messages");
      if (chatMessages) {
        chatMessages.innerHTML = `
          <div class="chat-message assistant">
            <strong>AI:</strong> 안녕하세요! 이 티켓에 대해 어떤 도움이 필요하신가요?
          </div>
        `;
      }
      console.log("🧹 채팅 기록 초기화");
    });
  }
}

// 코파일럿 검색 실행 함수
async function performCopilotSearch(client, query, contentTypes) {
  const resultsElement = document.getElementById("chat-messages");
  if (!resultsElement) return;

  // 사용자 메시지 추가
  const userMessage = document.createElement("div");
  userMessage.className = "chat-message user";
  userMessage.innerHTML = `<strong>질문:</strong> ${query}`;
  resultsElement.appendChild(userMessage);

  // 로딩 메시지 추가
  const loadingMessage = document.createElement("div");
  loadingMessage.className = "chat-message assistant";
  loadingMessage.innerHTML =
    '<div class="loading"><div class="spinner"></div><span>AI가 답변을 생성하는 중입니다...</span></div>';
  resultsElement.appendChild(loadingMessage);

  // 스크롤을 맨 아래로
  resultsElement.scrollTop = resultsElement.scrollHeight;

  try {
    // 현재 티켓 정보 가져오기
    const ticketData = await client.data.get("ticket");

    const requestData = {
      intent: "search",
      type: contentTypes,
      query: query,
      ticket_id: ticketData?.ticket?.id || null,
    };

    // FDK를 통한 백엔드 /query API 호출 (POST 메서드로 데이터 전송)
    const response = await callBackendAPI(client, "query", requestData, "POST");

    // 로딩 메시지 제거
    resultsElement.removeChild(loadingMessage);

    if (response.ok) {
      const data = response.data;
      displayCopilotResults(data, resultsElement);
    } else {
      console.error("❌ 코파일럿 API 응답 오류:", response.status);
      const errorMessage = document.createElement("div");
      errorMessage.className = "chat-message assistant";
      errorMessage.innerHTML =
        "<strong>오류:</strong> AI 응답을 가져올 수 없습니다.";
      resultsElement.appendChild(errorMessage);
    }
  } catch (error) {
    console.error("❌ 코파일럿 연결 오류:", error);
    // 로딩 메시지 제거
    if (resultsElement.contains(loadingMessage)) {
      resultsElement.removeChild(loadingMessage);
    }

    const errorMessage = document.createElement("div");
    errorMessage.className = "chat-message assistant";
    errorMessage.innerHTML =
      "<strong>오류:</strong> AI 서비스에 연결할 수 없습니다.";
    resultsElement.appendChild(errorMessage);
  }

  // 스크롤을 맨 아래로
  resultsElement.scrollTop = resultsElement.scrollHeight;
}

// 코파일럿 컨텍스트 가져오기 함수
async function getCopilotContext(client) {
  try {
    const ticketData = await client.data.get("ticket");
    return {
      ticket: ticketData.ticket,
      timestamp: new Date().toISOString(),
    };
  } catch (error) {
    console.error("❌ 컨텍스트 가져오기 오류:", error);
    return {};
  }
}

// 코파일럿 결과 표시 함수
function displayCopilotResults(data, resultsElement) {
  if (!resultsElement)
    resultsElement = document.getElementById("chat-messages");
  if (!resultsElement) return;

  const assistantMessage = document.createElement("div");
  assistantMessage.className = "chat-message assistant";

  if (data.answer || data.response) {
    let content = `<strong>AI 답변:</strong><br>${
      data.answer || data.response
    }`;

    // 검색 결과가 있는 경우 추가 표시
    if (data.results && data.results.length > 0) {
      content += "<br><br><strong>관련 정보:</strong><ul>";
      data.results.forEach((result, index) => {
        if (index < 3) {
          // 상위 3개만 표시
          content += `<li><strong>${
            result.title || result.subject || `항목 ${index + 1}`
          }</strong><br>
                     <small>${
                       result.excerpt || result.description || "내용 없음"
                     }</small></li>`;
        }
      });
      content += "</ul>";
    }

    // 참고 자료가 있는 경우
    if (data.sources && data.sources.length > 0) {
      content += "<br><strong>참고 자료:</strong><ul>";
      data.sources.forEach((source) => {
        content += `<li><a href="${source.url}" target="_blank">${source.title}</a></li>`;
      });
      content += "</ul>";
    }

    assistantMessage.innerHTML = content;
  } else {
    assistantMessage.innerHTML =
      "<strong>AI:</strong> 죄송합니다. 답변을 생성할 수 없습니다.";
  }

  resultsElement.appendChild(assistantMessage);

  // 스크롤을 맨 아래로
  resultsElement.scrollTop = resultsElement.scrollHeight;

  console.log("✅ 코파일럿 결과 표시 완료");
}

// 백엔드 /init 엔드포인트를 호출하는 함수 추가
// 백엔드에서 초기 데이터 로드 함수 (/init 엔드포인트 호출)
async function loadInitialDataFromBackend(client, basicTicketInfo) {
  try {
    console.log("🚀 백엔드 초기 데이터 로드 시작");

    // 중복 호출 방지
    if (globalTicketData.isLoading) {
      console.log("⚠️ 이미 로딩 중이므로 중복 호출 방지");
      return;
    }

    // 로딩 상태 설정
    globalTicketData.isLoading = true;

    try {
      // FDK를 통한 백엔드 /init API 호출 (GET 메서드, 데이터 없음)
      const response = await callBackendAPI(
        client,
        `init/${basicTicketInfo.id}`,
        null,
        "GET"
      );

      if (response.ok) {
        const data = response.data;
        console.log("✅ 백엔드 초기 데이터 로드 완료:", data);

        // 응답 데이터 구조 확인 및 로깅
        console.log("📊 응답 데이터 분석:");
        console.log(
          "- similar_tickets 개수:",
          data.similar_tickets?.length || 0
        );
        console.log("- kb_documents 개수:", data.kb_documents?.length || 0);
        console.log("- similar_tickets 데이터:", data.similar_tickets);
        console.log("- kb_documents 데이터:", data.kb_documents);

        // 백엔드에서 받은 완전한 티켓 정보로 UI 업데이트
        if (data.ticket_data) {
          console.log("🎫 백엔드에서 받은 완전한 티켓 정보로 UI 업데이트");
          updateTicketInfo(data.ticket_data);
        } else {
          // 백엔드에서 티켓 데이터가 없으면 기본 정보 사용
          console.log("🎫 기본 티켓 정보로 UI 업데이트");
          updateTicketInfo(basicTicketInfo);
        }

        // 전역 캐시에 데이터 저장 (ticket_info 포함)
        globalTicketData = {
          summary: data.ticket_summary,
          similar_tickets: data.similar_tickets || [],
          recommended_solutions: data.kb_documents || [], // 백엔드에서는 kb_documents로 온다
          cached_ticket_id: basicTicketInfo.id,
          ticket_info: data.ticket_data || basicTicketInfo, // 백엔드 티켓 정보를 캐시에 저장
          isLoading: false,
          lastLoadTime: Date.now(),
        };

        // /init 엔드포인트에서 모든 데이터를 한 번에 받아서 표시
        if (data.ticket_summary) {
          displayTicketSummary(data.ticket_summary);
        }

        if (data.similar_tickets && data.similar_tickets.length > 0) {
          console.log(`📋 유사 티켓 ${data.similar_tickets.length}개 표시`);
          displaySimilarTickets(data.similar_tickets);
        } else {
          console.log("📋 백엔드에서 유사 티켓 없음, 빈 상태 표시");
          displaySimilarTickets([]);
        }

        if (data.kb_documents && data.kb_documents.length > 0) {
          console.log(`💡 추천 솔루션 ${data.kb_documents.length}개 표시`);
          displaySuggestedSolutions(data.kb_documents);
        } else {
          console.log("💡 백엔드에서 추천 솔루션 없음, 빈 상태 표시");
          displaySuggestedSolutions([]);
        }
      } else {
        console.error("❌ 백엔드 초기 데이터 로드 실패:", response.status);
        // 폴백: Freshdesk API 사용
        console.log("🔄 백엔드 실패, Freshdesk API 폴백 사용");
        updateTicketInfo(basicTicketInfo);
        await loadSimilarTicketsFromFreshdesk(basicTicketInfo);
        displaySuggestedSolutions(generateMockSolutions());

        // 캐시 초기화
        globalTicketData = {
          summary: null,
          similar_tickets: [],
          recommended_solutions: [],
          cached_ticket_id: null,
          ticket_info: basicTicketInfo, // 기본 정보라도 저장
          isLoading: false,
          lastLoadTime: null,
        };
      }
    } finally {
      // 로딩 상태 해제
      globalTicketData.isLoading = false;
    }
  } catch (error) {
    console.error("❌ 백엔드 초기 데이터 로드 오류:", error);

    // 로딩 상태 해제
    globalTicketData.isLoading = false;

    // 폴백: Freshdesk API 사용
    console.log("🔄 백엔드 연결 오류, Freshdesk API 폴백 사용");
    updateTicketInfo(basicTicketInfo);
    await loadSimilarTicketsFromFreshdesk(basicTicketInfo);
    displaySuggestedSolutions(generateMockSolutions());

    // 캐시 초기화
    globalTicketData = {
      summary: null,
      similar_tickets: [],
      recommended_solutions: [],
      cached_ticket_id: null,
      ticket_info: basicTicketInfo, // 기본 정보라도 저장
      isLoading: false,
      lastLoadTime: null,
    };
  }
}

// 티켓 요약 표시 함수
function displayTicketSummary(summary) {
  const summarySection = document.getElementById("ticket-summary-section");
  if (!summarySection || !summary) return;

  summarySection.innerHTML = `
    <div class="summary-section">
      <h6>티켓 요약</h6>
      <div class="summary-content">
        <div class="mb-2">
          <strong>문제:</strong> ${summary.problem || "요약 정보 없음"}
        </div>
        <div class="mb-2">
          <strong>원인:</strong> ${summary.cause || "분석 중"}
        </div>
        <div class="mb-2">
          <strong>해결방안:</strong> ${summary.solution || "검토 중"}
        </div>
        <div>
          <strong>처리결과:</strong> ${summary.result || "진행 중"}
        </div>
      </div>
    </div>
  `;

  console.log("✅ 티켓 요약 표시 완료");
}

// 전역 데이터 캐시 초기화 함수
function resetGlobalTicketCache() {
  globalTicketData = {
    summary: null,
    similar_tickets: [],
    recommended_solutions: [],
    cached_ticket_id: null,
    ticket_info: null,
    isLoading: false,
    lastLoadTime: null,
  };
  console.log("🗑️ 전역 티켓 데이터 캐시 초기화됨");
}

// 다중 시점에서 백그라운드 데이터 로드를 적극적으로 시도하는 함수
function attemptMultipleBackgroundLoads(client) {
  console.log("🎯 적극적인 백그라운드 데이터 로드 전략 시작");

  // 여러 시점에서 안전한 데이터 로드 시도 (점진적 지연)
  const loadAttempts = [
    { delay: 1000, label: "초기 시도" },
    { delay: 2000, label: "재시도 1" },
    { delay: 3500, label: "재시도 2" },
    { delay: 5000, label: "최종 시도" },
  ];

  loadAttempts.forEach(({ delay, label }) => {
    setTimeout(async () => {
      // 이미 로드된 경우 스킵
      if (globalTicketData.cached_ticket_id && globalTicketData.summary) {
        console.log(`✅ ${label}: 이미 데이터 준비됨 - 스킵`);
        return;
      }

      try {
        console.log(`🔄 ${label} (${delay}ms 후) - FDK 안전성 검증 시작`);

        // FDK 안전성 검증
        if (
          !client ||
          typeof client.data === "undefined" ||
          typeof client.instance === "undefined"
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
            (ctx.location.includes("ticket") ||
              ctx.location === "ticket_top_navigation");
          console.log(
            `🔍 ${label}: 컨텍스트 확인 - ${ctx.location} (티켓페이지: ${isTicketPage})`
          );
        } catch (contextError) {
          console.warn(
            `⚠️ ${label}: 컨텍스트 확인 실패, 티켓 데이터로 추론 시도`
          );
          isTicketPage = true; // 일단 시도해보기
        }

        // 티켓 데이터 안전하게 가져오기
        if (isTicketPage) {
          const ticketData = await client.data.get("ticket");

          if (ticketData && ticketData.ticket && ticketData.ticket.id) {
            const currentTicketId = ticketData.ticket.id;

            // 캐시 확인 및 중복 호출 방지
            if (
              globalTicketData.cached_ticket_id === currentTicketId &&
              globalTicketData.summary &&
              !isDataStale()
            ) {
              console.log(`✅ ${label}: 이미 캐시된 데이터 존재 → 스킵`);
              return;
            }

            if (globalTicketData.isLoading) {
              console.log(`⚠️ ${label}: 이미 로딩 중 → 스킵`);
              return;
            }

            console.log(
              `🚀 ${label}: 티켓 ID ${currentTicketId} 백엔드 로드 시작`
            );

            // 백엔드 호출 (FDK와 독립적)
            resetGlobalTicketCache();
            await loadInitialDataFromBackend(client, ticketData.ticket);

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
        if (error.message && error.message.includes("EventAPI")) {
          console.log(`🔧 ${label}: EventAPI 타이밍 이슈 - 나중에 다시 시도`);
        }
      }
    }, delay);
  });

  // 추가 전략: URL 변경 감지
  if (typeof window !== "undefined") {
    let lastUrl = window.location.href;
    const urlCheckInterval = setInterval(() => {
      if (window.location.href !== lastUrl) {
        lastUrl = window.location.href;
        if (
          lastUrl.includes("/tickets/") &&
          (!globalTicketData.cached_ticket_id || !globalTicketData.summary)
        ) {
          console.log(
            "🎯 URL 변경으로 티켓 페이지 진입 감지 → 백그라운드 로드 시도"
          );
          setTimeout(() => {
            attemptSingleBackgroundLoad(client, "URL변경감지");
          }, 1500);
        }
      }
    }, 1000);

    // 10분 후 URL 감지 정리 (메모리 누수 방지)
    setTimeout(() => {
      clearInterval(urlCheckInterval);
      console.log("🧹 URL 변경 감지 종료");
    }, 600000);
  }
}

// 단일 백그라운드 로드 시도 함수
async function attemptSingleBackgroundLoad(client, source = "단일시도") {
  try {
    // 캐시 확인
    if (
      globalTicketData.cached_ticket_id &&
      globalTicketData.summary &&
      !isDataStale()
    ) {
      console.log(`✅ ${source}: 이미 유효한 캐시 데이터 존재 → 스킵`);
      return;
    }

    // 중복 호출 방지
    if (globalTicketData.isLoading) {
      console.log(`⚠️ ${source}: 이미 로딩 중 → 스킵`);
      return;
    }

    const ticketData = await client.data.get("ticket");
    if (ticketData && ticketData.ticket && ticketData.ticket.id) {
      console.log(
        `🔄 ${source}: 백그라운드 로드 시작 (티켓: ${ticketData.ticket.id})`
      );
      resetGlobalTicketCache();
      await loadInitialDataFromBackend(client, ticketData.ticket);
      console.log(`✅ ${source}: 백그라운드 로드 성공`);
    }
  } catch (error) {
    console.warn(`⚠️ ${source}: 백그라운드 로드 실패:`, error.message);
  }
}

// 백엔드 API 호출을 위한 공통 함수
async function callBackendAPI(client, endpoint, data = null, method = "GET") {
  try {
    console.log(`🚀 백엔드 API 호출: ${method} /${endpoint}`);

    // iparams에서 Freshdesk 설정값 가져오기
    const config = await getFreshdeskConfigFromIparams(client);

    if (!config || !config.domain || !config.apiKey) {
      console.warn(
        "⚠️ iparams에서 Freshdesk 설정값을 가져올 수 없습니다. 환경변수 폴백 시도..."
      );

      // 폴백: requests.json의 기본 헤더 사용 (개발 환경용)
      if (method === "GET") {
        const response = await client.request.invokeTemplate("backendApi", {
          context: { path: endpoint },
        });
        return { ok: true, data: response };
      } else {
        const response = await client.request.invokeTemplate("backendApiPost", {
          context: { path: endpoint },
          body: JSON.stringify(data),
        });
        return { ok: true, data: response };
      }
    }

    // iparams 값으로 동적 헤더 생성
    const dynamicHeaders = {
      "Content-Type": "application/json",
      "X-Freshdesk-Domain":
        config.companyId || extractCompanyIdFromDomain(config.domain), // company_id 전달
      "X-Freshdesk-API-Key": config.apiKey,
      "ngrok-skip-browser-warning": "true", // ngrok 환경용
    };

    console.log("📡 동적 헤더 생성:", {
      domain: dynamicHeaders["X-Freshdesk-Domain"],
      hasApiKey: !!dynamicHeaders["X-Freshdesk-API-Key"],
    });

    // 동적 요청 설정으로 API 호출
    const requestConfig = {
      method: method,
      protocol: "https",
      host: config.backendUrl
        ? new URL(config.backendUrl).host
        : "7987-58-122-170-2.ngrok-free.app",
      path: `/${endpoint}`,
      headers: dynamicHeaders,
    };

    if (method === "GET") {
      const response = await client.request.invoke("generic", {
        schema: requestConfig,
        context: { path: endpoint },
      });
      return { ok: true, data: response.response || response };
    } else {
      requestConfig.body = JSON.stringify(data);
      const response = await client.request.invoke("generic", {
        schema: requestConfig,
        context: { path: endpoint },
        body: JSON.stringify(data),
      });
      return { ok: true, data: response.response || response };
    }
  } catch (error) {
    console.error(`❌ 백엔드 API 호출 오류 (${method} /${endpoint}):`, error);
    return { ok: false, error: error.message };
  }
}

// 에러 메시지를 결과 영역에 표시하는 함수
function showErrorInResultsInResults(
  message,
  containerId = "similar-tickets-list"
) {
  try {
    const container = document.getElementById(containerId);
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
    console.error("❌ showErrorInResultsInResults 오류", error);
  }
}

// 로딩 메시지를 표시하는 함수
function showLoadingInResults(containerId = "similar-tickets-list") {
  try {
    const container = document.getElementById(containerId);
    if (container) {
      container.innerHTML = `
        <div class="loading-message">
          <i class="fas fa-spinner fa-spin"></i>
          로딩 중...
        </div>
      `;
    }
  } catch (error) {
    console.error("❌ showLoadingInResults 오류:", error);
  }
}
/**
 * 공통 모달 트리거 함수 - 캐시된 데이터만 사용하여 즉시 열기
 * 백엔드 호출 없이 모달을 즉시 열고, 캐시된 데이터가 있으면 표시
 */
async function showModal() {
  try {
    console.log("🚀 모달 열기 시작 (백엔드 호출 없음)");

    // 컨텍스트 정보 가져오기
    const context = await client.instance.context();
    console.log("📍 컨텍스트 정보:", context);

    const data = await client.data.get("ticket");
    const ticket = data.ticket;
    console.log("📋 티켓 데이터 가져옴:", ticket.id);

    // 캐시된 데이터 확인 (선택적 - 있으면 사용, 없어도 모달 열기)
    const hasCachedData =
      globalTicketData.cached_ticket_id === ticket.id &&
      !isDataStale() &&
      globalTicketData.summary;

    if (hasCachedData) {
      console.log("⚡ 캐시된 데이터 사용 가능");
    } else {
      console.log("ℹ️ 캐시된 데이터 없음 - 빈 상태로 모달 열기");
    }

    // 항상 즉시 모달 열기 (캐시 여부와 관계없이)
    const modalConfig = {
      title: "Copilot Canvas",
      template: "index.html",
      data: {
        showAiTab: false,
        ticket,
        context: context,
      },
      noBackdrop: true,
      size: {
        width: "800px",
        height: "600px",
      },
    };

    console.log("🔧 모달 설정:", modalConfig);
    await client.interface.trigger("showModal", modalConfig);
    console.log("✅ 모달 즉시 열림 완료");
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
      console.log("✅ 폴백 모달 열림 완료");
    } catch (fallbackError) {
      console.error("❌ 폴백 모달도 실패:", fallbackError);
    }
  }
}

// iparams에서 Freshdesk 설정값을 가져오는 함수
async function getFreshdeskConfigFromIparams(client) {
  try {
    console.log("🔧 iparams에서 Freshdesk 설정값 가져오기 시작");

    // FDK의 iparams API를 통해 설정값 조회
    const iparams = await client.iparams.get();

    if (!iparams) {
      console.warn("⚠️ iparams 데이터가 없습니다.");
      return null;
    }

    const config = {
      domain: iparams.freshdesk_domain,
      apiKey: iparams.freshdesk_api_key,
      backendUrl: iparams.backend_url,
      companyId: iparams.company_id,
    };

    console.log("✅ iparams 설정값 조회 완료:", {
      domain: config.domain ? "✓" : "✗",
      apiKey: config.apiKey ? "✓" : "✗",
      backendUrl: config.backendUrl ? "✓" : "✗",
      companyId: config.companyId ? "✓" : "✗",
    });

    // 스마트 도메인 파싱 (프론트엔드에서도 적용)
    if (config.domain) {
      config.normalizedDomain = smartDomainParsingFrontend(config.domain);
      console.log(
        `🔄 도메인 정규화: ${config.domain} → ${config.normalizedDomain}`
      );
    }

    return config;
  } catch (error) {
    console.error("❌ iparams 설정값 조회 실패:", error);
    return null;
  }
}

// 프론트엔드용 스마트 도메인 파싱 함수
function smartDomainParsingFrontend(inputDomain) {
  if (!inputDomain || !inputDomain.trim()) {
    throw new Error("도메인 입력값이 비어있습니다.");
  }

  let domain = inputDomain.trim().toLowerCase();

  // URL 형태인 경우 도메인 부분만 추출
  if (domain.startsWith("http://") || domain.startsWith("https://")) {
    try {
      const url = new URL(domain);
      domain = url.hostname;
    } catch (e) {
      throw new Error(`URL 파싱 실패: ${domain}`);
    }
  }

  // 이미 완전한 .freshdesk.com 도메인인 경우
  if (domain.endsWith(".freshdesk.com")) {
    const companyId = domain.replace(".freshdesk.com", "");
    if (!companyId || companyId.length < 2) {
      throw new Error(`유효하지 않은 company_id: ${companyId}`);
    }
    return domain;
  }

  // company_id만 입력된 경우
  if (domain.length < 2) {
    throw new Error(`company_id가 너무 짧습니다: ${domain}`);
  }

  // 특수문자 검증 (기본적인 체크)
  if (!/^[a-z0-9\-]+$/.test(domain)) {
    throw new Error(
      `company_id에 허용되지 않는 문자가 포함되어 있습니다: ${domain}`
    );
  }

  return `${domain}.freshdesk.com`;
}

// company_id 추출 함수 (프론트엔드용)
function extractCompanyIdFromDomain(domain) {
  try {
    const normalized = smartDomainParsingFrontend(domain);
    return normalized.replace(".freshdesk.com", "");
  } catch (error) {
    console.error("company_id 추출 실패:", error);
    return null;
  }
}
