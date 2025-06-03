// CopilotKit 번들 - CDN 없이 사용
(function() {
  'use strict';
  
  console.log('CopilotKit Bundle Loading...');
  
  // React가 이미 로드되어 있다고 가정하고 바로 초기화
  // (modal.html에서 React를 미리 로드하는 방식)
  if (typeof React !== 'undefined' && typeof ReactDOM !== 'undefined') {
    initializeCopilotKit();
  } else {
    console.error('React와 ReactDOM이 로드되지 않았습니다. modal.html에서 React를 먼저 로드해주세요.');
  }
  
  function initializeCopilotKit() {
    // CopilotTicketReply 컴포넌트 정의
    window.CopilotTicketReply = {
      default: function(props) {
        const { onSubmit, ticketDetails } = props;
        const [replyText, setReplyText] = React.useState('');
        const [suggestions, setSuggestions] = React.useState('');
        const [showSuggestion, setShowSuggestion] = React.useState(false);
        
        // 텍스트 입력 시 AI 제안 시뮬레이션
        const handleTextChange = (e) => {
          const text = e.target.value;
          setReplyText(text);
          
          // 간단한 자동완성 시뮬레이션
          if (text.length > 5 && text.endsWith(' ')) {
            // 실제로는 API 호출이 필요하지만, 테스트를 위해 시뮬레이션
            const mockSuggestions = {
              '안녕하세요 ': '고객님, 문의 주셔서 감사합니다.',
              '죄송합니다 ': '불편을 드려 대단히 죄송합니다.',
              '감사합니다 ': '소중한 의견 감사드립니다.',
              '확인해 ': '보겠습니다. 잠시만 기다려 주세요.',
              '도움이 ': '필요하신 부분이 있으시면 언제든 말씀해 주세요.'
            };
            
            const lastWords = text.trim().split(' ').slice(-2).join(' ') + ' ';
            const suggestion = mockSuggestions[lastWords];
            
            if (suggestion) {
              setSuggestions(suggestion);
              setShowSuggestion(true);
            } else {
              setShowSuggestion(false);
            }
          } else {
            setShowSuggestion(false);
          }
        };
        
        // Tab 키로 제안 수락
        const handleKeyDown = (e) => {
          if (e.key === 'Tab' && showSuggestion) {
            e.preventDefault();
            setReplyText(replyText + suggestions);
            setShowSuggestion(false);
            setSuggestions('');
          }
        };
        
        // 전송 처리
        const handleSubmit = () => {
          if (replyText.trim() && onSubmit) {
            onSubmit(replyText);
            setReplyText('');
          }
        };
        
        return React.createElement('div', { className: 'copilot-container' },
          React.createElement('div', { style: { marginBottom: '10px', fontSize: '14px', color: '#666' } },
            `티켓: ${ticketDetails.subject} (ID: ${ticketDetails.id})`
          ),
          React.createElement('div', { style: { position: 'relative' } },
            React.createElement('textarea', {
              className: 'copilot-textarea',
              value: replyText,
              onChange: handleTextChange,
              onKeyDown: handleKeyDown,
              placeholder: '고객에게 보낼 응답을 작성하세요... (자동완성을 위해 "안녕하세요 ", "죄송합니다 ", "감사합니다 " 등을 입력해보세요)',
              style: { width: '100%', minHeight: '150px' }
            }),
            showSuggestion && React.createElement('div', {
              style: {
                position: 'absolute',
                top: '100%',
                left: '0',
                right: '0',
                background: '#f0f0f0',
                padding: '8px 12px',
                border: '1px solid #ddd',
                borderTop: 'none',
                fontSize: '14px',
                color: '#666',
                borderRadius: '0 0 4px 4px'
              }
            }, 
              React.createElement('span', { style: { color: '#1E88E5' } }, '💡 제안: '),
              suggestions,
              React.createElement('span', { style: { marginLeft: '10px', fontSize: '12px' } }, '(Tab 키로 수락)')
            )
          ),
          React.createElement('div', { style: { marginTop: '15px', textAlign: 'right' } },
            React.createElement('button', {
              className: 'copilot-submit-button',
              onClick: handleSubmit,
              disabled: !replyText.trim()
            }, '응답 전송')
          )
        );
      }
    };
    
    console.log('CopilotKit initialized successfully');
  }
})();
