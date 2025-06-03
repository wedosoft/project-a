let client;

/**
 * 공통 모달 트리거 함수
 */
async function showSampleModal() {
  try {
    await client.interface.trigger("showModal", {
      title: "Sample App Form",
      template: "modal.html",
      noBackdrop: true
    });
    console.log("Modal 열림");
  } catch (err) {
    console.error("Modal 오류", err);
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
  })
  .catch(err => console.error("SDK 초기화 실패", err));