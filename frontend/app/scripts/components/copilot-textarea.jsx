const React = require('react');
const { useState } = React;
const { CopilotKit } = require("@copilotkit/react-core");
const { CopilotTextarea } = require("@copilotkit/react-textarea");
require("@copilotkit/react-textarea/styles.css");

/**
 * AI 지원 티켓 응답 컴포넌트
 * @param {Object} props 
 * @param {Function} props.onSubmit 응답 제출 핸들러
 * @param {Object} props.ticketDetails 티켓 상세 정보
 * @returns {React.Component}
 */
function CopilotTicketReply({ onSubmit, ticketDetails = {} }) {
  const [input, setInput] = useState("");
  
  // 응답 제출 핸들러
  const handleReply = () => {
    if (input.trim()) {
      onSubmit(input);
      setInput("");
    }
  };

  // 티켓 정보로 프롬프트 생성
  const generatePrompt = () => {
    const details = ticketDetails || {};
    return `이 고객 티켓에 대한 응답을 작성하는 것을 도와드립니다.
티켓 ID: ${details.id || '알 수 없음'}
제목: ${details.subject || '알 수 없음'}
고객: ${details.requester?.name || '알 수 없음'}
우선순위: ${details.priority || '보통'}

요청 사항에 대해 친절하고 전문적인 응답을 작성해주세요.`;
  };

  return (
    <div className="copilot-container">
      <CopilotKit publicApiKey={window.COPILOT_API_KEY || 'ck_pub_2048e6d9442c1571c2edba0e4fff8415'}>
        <CopilotTextarea
          className="copilot-textarea"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="티켓 응답을 작성하세요..."
          autosuggestionsConfig={{
            textareaPurpose: generatePrompt(),
            chatApiConfigs: {}
          }}
        />
        <button 
          className="copilot-submit-button" 
          disabled={!input.trim()} 
          onClick={handleReply}
        >
          응답하기
        </button>
      </CopilotKit>
    </div>
  );
}

module.exports = {
  default: CopilotTicketReply
};
