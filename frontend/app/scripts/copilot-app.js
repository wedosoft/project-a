const React = require('react');
const ReactDOM = require('react-dom/client');
const CopilotTicketReply = require('./components/copilot-textarea').default;

// 글로벌 API 키 설정 (실제 환경에서는 환경 설정에서 가져와야 함)
window.COPILOT_API_KEY = 'ck_pub_2048e6d9442c1571c2edba0e4fff8415';

// Freshdesk SDK 클라이언트
let client;

/**
 * 티켓 응답 처리 함수
 * @param {string} replyText 
 */
const handleTicketReply = async (replyText) => {
  try {
    console.log('티켓 응답 처리:', replyText);
    
    // POC 단계에서는 실제 API 호출 대신 알림만 표시
    await client.interface.trigger("showNotify", {
      type: "success",
      message: "응답이 성공적으로 등록되었습니다."
    });
    
    // 실제 구현시 아래와 같이 티켓 API를 호출
    /*
    await client.request.invoke('createReply', {
      body: replyText,
      ticketId: ticketData.ticket.id
    });
    */
    
    // 모달 닫기
    setTimeout(() => {
      client.instance.close();
    }, 1500);
    
  } catch (error) {
    console.error("응답 등록 실패:", error);
    await client.interface.trigger("showNotify", {
      type: "danger",
      message: "응답 등록에 실패했습니다: " + error.message
    });
  }
};

/**
 * 앱 초기화 및 마운트 함수
 */
const initCopilotApp = () => {
  app.initialized().then((appClient) => {
    client = appClient;
    
    // DOM 로드 완료 후 React 앱 마운트
    document.addEventListener('DOMContentLoaded', () => {
      const container = document.getElementById('copilot-root');
      
      if (!container) {
        console.error('copilot-root 요소를 찾을 수 없습니다');
        return;
      }
      
      // 티켓 데이터 가져오기 (실제 구현시)
      let ticketData = { id: '001', subject: 'POC 테스트', priority: '중간' };
      
      client.data.get("ticket").then((data) => {
        ticketData = data.ticket;
        console.log('티켓 데이터:', ticketData);
      }).catch(err => {
        console.warn("티켓 데이터 조회 실패 (테스트 데이터 사용):", err);
      }).finally(() => {
        // React 앱 렌더링
        const root = ReactDOM.createRoot(container);
        root.render(
          React.createElement(CopilotTicketReply, {
            onSubmit: handleTicketReply,
            ticketDetails: ticketData
          })
        );
      });
    });
  }).catch(err => {
    console.error('앱 초기화 실패:', err);
  });
};

// 앱 초기화 실행
initCopilotApp();
