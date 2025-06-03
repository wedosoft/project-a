let client;

/**
 * 공통 모달 트리거 함수
 */
async function showSampleModal() {
  try {
    await client.interface.trigger("showModal", {
      title: "프롬프트 캔버스",
      template: "modal.html",
      data: { showAiTab: false },
      noBackdrop:true,
      size: {
        width: "800px",
        height: "600px"
      }
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
    await client.interface.trigger("showModal", {
      title: "프롬프트 캔버스 - AI 응답 작성",
      template: "modal.html",
      data: { showAiTab: true },
      noBackdrop:true,
      size: {
        width: "800px",
        height: "600px"
      }
    });
    console.log("AI 응답 모달 열림");
  } catch (err) {
    console.error("코파일럿 모달 오류", err);
  }
}

app.initialized()
  .then(c => {
    client = c;

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
  .catch(err => console.error("SDK 초기화 실패", err));