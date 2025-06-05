/**
 * CopilotChat 컴포넌트
 * CopilotKit을 사용하여 자연어 기반 질의응답 인터페이스를 제공합니다.
 * 벡터 DB에 저장된 티켓/지식베이스 데이터를 기반으로 AI 응답을 생성합니다.
 */

import { CopilotTextarea } from '@copilotkit/react-textarea';
import React, { useCallback, useState } from 'react';

interface QueryResponse {
    answer: string;
    sources: Array<{
        id: string;
        title: string;
        content: string;
        score: number;
        metadata: {
            type: 'ticket' | 'article';
            created_at?: string;
            ticket_id?: string;
            article_id?: string;
        };
    }>;
}

interface ConversationItem {
    type: 'user' | 'assistant';
    message: string;
    timestamp: Date;
    sources?: QueryResponse['sources'];
}

const CopilotChat: React.FC = () => {
    // 대화 히스토리 상태 관리
    const [conversation, setConversation] = useState<ConversationItem[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [inputValue, setInputValue] = useState('');

    /**
     * 사용자 질의를 백엔드로 전송하고 AI 응답을 받아옵니다.
     * @param query 사용자 질의 내용
     */
    const handleQuery = useCallback(async (query: string) => {
        if (!query.trim()) return;

        // 사용자 메시지를 대화 히스토리에 추가
        const userMessage: ConversationItem = {
            type: 'user',
            message: query,
            timestamp: new Date()
        };

        setConversation(prev => [...prev, userMessage]);
        setIsLoading(true);

        try {
            // 백엔드 API 호출 - /query 엔드포인트 사용
            const response = await fetch('http://localhost:8000/query', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    query: query,
                    company_id: 'kyexpert', // 환경에 따라 동적으로 설정 가능
                    include_sources: true,
                    max_results: 5
                })
            });

            if (!response.ok) {
                throw new Error(`API 호출 실패: ${response.status}`);
            }

            const data: QueryResponse = await response.json();

            // AI 응답을 대화 히스토리에 추가
            const assistantMessage: ConversationItem = {
                type: 'assistant',
                message: data.answer,
                timestamp: new Date(),
                sources: data.sources
            };

            setConversation(prev => [...prev, assistantMessage]);

        } catch (error) {
            console.error('Query 처리 중 오류:', error);
            
            // 에러 메시지를 대화 히스토리에 추가
            const errorMessage: ConversationItem = {
                type: 'assistant',
                message: '죄송합니다. 현재 서비스에 일시적인 문제가 발생했습니다. 잠시 후 다시 시도해 주세요.',
                timestamp: new Date()
            };

            setConversation(prev => [...prev, errorMessage]);
        } finally {
            setIsLoading(false);
        }
    }, []);

    /**
     * 응답을 티켓 응답으로 사용하는 기능
     * @param message 티켓 응답으로 사용할 메시지
     */
    const useAsTicketReply = useCallback((message: string) => {
        try {
            // Freshdesk FDK의 postMessage API 사용
            const ticketReply = {
                action: 'setTicketReply',
                content: message
            };

            // 부모 창(Freshdesk)으로 메시지 전송
            if (window.parent && window.parent !== window) {
                window.parent.postMessage(ticketReply, '*');
            }

            // 사용자에게 피드백 제공
            alert('티켓 응답으로 내용이 설정되었습니다.');
        } catch (error) {
            console.error('티켓 응답 설정 중 오류:', error);
            alert('티켓 응답 설정에 실패했습니다.');
        }
    }, []);

    /**
     * 대화 히스토리를 초기화합니다.
     */
    const clearConversation = useCallback(() => {
        setConversation([]);
    }, []);

    return (
        <div className="copilot-chat-container">
            {/* 대화 히스토리 영역 */}
            <div className="conversation-history">
                {conversation.length === 0 ? (
                    <div className="empty-state">
                        <p>안녕하세요! 무엇을 도와드릴까요?</p>
                        <p>티켓 처리와 관련된 질문을 자유롭게 해보세요.</p>
                    </div>
                ) : (
                    conversation.map((item, index) => (
                        <div key={index} className={`message ${item.type}`}>
                            <div className="message-header">
                                <span className="sender">
                                    {item.type === 'user' ? '나' : 'AI 어시스턴트'}
                                </span>
                                <span className="timestamp">
                                    {item.timestamp.toLocaleTimeString()}
                                </span>
                            </div>
                            <div className="message-content">
                                {item.message}
                            </div>
                            
                            {/* AI 응답인 경우 추가 기능 버튼들 */}
                            {item.type === 'assistant' && (
                                <div className="message-actions">
                                    <button 
                                        onClick={() => useAsTicketReply(item.message)}
                                        className="use-as-reply-btn"
                                        title="이 내용을 티켓 응답으로 사용"
                                    >
                                        티켓 응답으로 사용
                                    </button>
                                </div>
                            )}

                            {/* 참조 소스가 있는 경우 표시 */}
                            {item.sources && item.sources.length > 0 && (
                                <div className="sources-section">
                                    <details>
                                        <summary>참조 소스 ({item.sources.length}개)</summary>
                                        {item.sources.map((source, sourceIndex) => (
                                            <div key={sourceIndex} className="source-item">
                                                <div className="source-header">
                                                    <span className="source-type">
                                                        {source.metadata.type === 'ticket' ? '티켓' : '지식베이스'}
                                                    </span>
                                                    <span className="source-score">
                                                        연관도: {Math.round(source.score * 100)}%
                                                    </span>
                                                </div>
                                                <div className="source-title">{source.title}</div>
                                                <div className="source-content">
                                                    {source.content.substring(0, 200)}...
                                                </div>
                                            </div>
                                        ))}
                                    </details>
                                </div>
                            )}
                        </div>
                    ))
                )}

                {/* 로딩 표시 */}
                {isLoading && (
                    <div className="message assistant loading">
                        <div className="message-header">
                            <span className="sender">AI 어시스턴트</span>
                        </div>
                        <div className="message-content">
                            <div className="typing-indicator">
                                <span></span><span></span><span></span>
                            </div>
                        </div>
                    </div>
                )}
            </div>

            {/* 대화 제어 버튼들 */}
            <div className="conversation-controls">
                {conversation.length > 0 && (
                    <button 
                        onClick={clearConversation}
                        className="clear-btn"
                        disabled={isLoading}
                    >
                        대화 초기화
                    </button>
                )}
            </div>

            {/* 입력 영역 */}
            <div className="input-section">
                <form onSubmit={(e) => {
                    e.preventDefault();
                    if (inputValue.trim()) {
                        handleQuery(inputValue);
                        setInputValue('');
                    }
                }}>
                    <CopilotTextarea
                        value={inputValue}
                        onValueChange={(value: string) => setInputValue(value)}
                        className="copilot-textarea"
                        placeholder="질문을 입력하세요... (예: 이 문제 해결 방법은 뭔가요?)"
                        disabled={isLoading}
                        rows={3}
                        autosuggestionsConfig={{
                            textareaPurpose: "상담원이 고객 문의사항에 대한 답변을 작성하거나 관련 정보를 검색할 때 사용하는 입력창입니다. 티켓 내용과 지식베이스를 참고하여 유용한 제안을 제공해주세요.",
                            chatApiConfigs: {
                                suggestionsApiConfig: {
                                    forwardedParams: {
                                        max_tokens: 50,
                                        stop: [".", "?", "!", "\n\n"],
                                    },
                                },
                            },
                        }}
                        onKeyDown={(e) => {
                            if (e.key === 'Enter' && !e.shiftKey) {
                                e.preventDefault();
                                if (inputValue.trim()) {
                                    handleQuery(inputValue);
                                    setInputValue('');
                                }
                            }
                        }}
                    />
                    <button 
                        type="submit" 
                        className="submit-btn"
                        disabled={isLoading}
                    >
                        {isLoading ? '처리중...' : '전송'}
                    </button>
                </form>
                <div className="input-help">
                    Enter 키로 전송하거나 Shift+Enter로 줄바꿈 (AI 자동완성 지원)
                </div>
            </div>
        </div>
    );
};

export default CopilotChat;
