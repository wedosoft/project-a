/**
 * CopilotApp 메인 컴포넌트
 * CopilotKit Provider를 설정하고 CopilotChat 컴포넌트를 렌더링합니다.
 */

import { CopilotKit } from '@copilotkit/react-core';
import React from 'react';
import '../styles/copilot-chat.css';
import CopilotChat from './CopilotChat';

const CopilotApp: React.FC = () => {
    // 환경 설정 - 실제 환경에서는 환경변수로 관리
    const runtimeUrl = process.env.COPILOT_RUNTIME_URL || 'http://localhost:8000/copilot';
    
    return (
        <CopilotKit 
            runtimeUrl={runtimeUrl}
            // 추가 설정이 필요한 경우 여기에 설정
        >
            <div className="copilot-app">
                <CopilotChat />
            </div>
        </CopilotKit>
    );
};

export default CopilotApp;
