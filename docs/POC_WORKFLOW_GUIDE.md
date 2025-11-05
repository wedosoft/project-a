# POC 워크플로우 구현 가이드

## 개요

상담원이 Freshdesk 티켓 화면에서 AI 어시스턴트를 트리거하여 자동화된 지원을 받는 전체 플로우를 구현합니다.

**핵심 목표**:
1. ✅ 임베딩 데이터 여부에 따른 분기 처리
2. ✅ 에이전트 오케스트레이션 과정 시각화
3. ✅ 상담원 승인/반려/보완 루프
4. ✅ 티켓 필드 자동 세팅 및 응답 삽입

---

## 📋 핵심 구성 요약

### **1. 테넌트 식별 체계** 
- `tenant_id` + `platform` 조합으로 고유 식별
- 예: `demo-tenant` + `freshdesk`

### **2. 임베딩 모드 분기**
- `embedding_enabled=true`: 검색 기반 (Retriever → 유사사례 참조)
- `embedding_enabled=false`: 직접 분석 (LLM만 사용)

### **3. 스트리밍 이벤트 타입**
- `router_decision`: 라우팅 판단 (임베딩 여부 확인)
- `retriever_start`, `retriever_results`: 검색 단계
- `resolution_start`, `resolution_complete`: 솔루션 생성
- `error`: 오류

---

## 테넌트 식별 체계

### **고유 키 조합**
```
tenant_key = {tenant_id} + {platform}
```

**예시**:
```json
{
  "tenant_id": "customer-abc",
  "platform": "freshdesk"
}
```

**DB 저장**:
```sql
-- 테넌트 설정 테이블
CREATE TABLE tenant_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id TEXT NOT NULL,
    platform TEXT NOT NULL,  -- freshdesk, zendesk, intercom
    embedding_enabled BOOLEAN DEFAULT true,
    analysis_depth TEXT DEFAULT 'full',
    llm_max_tokens INTEGER DEFAULT 1500,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, platform)
);
```

---

## Phase 1: 프론트엔드 트리거 (FDK 앱)

### 📍 위치: `frontend/app/`

### **Step 1.1: 티켓 사이드바 UI**

**파일**: `frontend/app/index.html`

```html
<!DOCTYPE html>
<html>
<head>
    <title>AI Assistant</title>
    <link rel="stylesheet" href="styles/style.css">
</head>
<body>
    <!-- AI 어시스턴트 패널 -->
    <div id="ai-assistant-panel">
        <!-- 헤더 -->
        <div class="panel-header">
            <h2>🤖 AI Assistant</h2>
            <span id="status-badge" class="badge badge-info">준비</span>
        </div>

        <!-- 트리거 버튼 -->
        <div class="action-section">
            <button id="analyze-btn" class="btn btn-primary btn-lg">
                <span class="icon">🔍</span>
                티켓 분석 시작
            </button>
        </div>

        <!-- 오케스트레이션 진행 상황 -->
        <div id="orchestration-progress" class="progress-section" style="display: none;">
            <h3>🔄 분석 진행 상황</h3>
            
            <!-- 단계별 진행 -->
            <div class="step-tracker">
                <div class="step" data-step="router">
                    <div class="step-icon">1</div>
                    <div class="step-content">
                        <div class="step-title">라우팅 판단</div>
                        <div class="step-detail" id="router-detail"></div>
                    </div>
                    <div class="step-status"></div>
                </div>

                <div class="step" data-step="retriever">
                    <div class="step-icon">2</div>
                    <div class="step-content">
                        <div class="step-title">검색 수행</div>
                        <div class="step-detail" id="retriever-detail"></div>
                    </div>
                    <div class="step-status"></div>
                </div>

                <div class="step" data-step="resolution">
                    <div class="step-icon">3</div>
                    <div class="step-content">
                        <div class="step-title">솔루션 생성</div>
                        <div class="step-detail" id="resolution-detail"></div>
                    </div>
                    <div class="step-status"></div>
                </div>
            </div>
        </div>

        <!-- 검색 결과 (참조 내용) -->
        <div id="reference-section" class="reference-section" style="display: none;">
            <h3>📚 참조 내용</h3>
            
            <!-- 유사 사례 -->
            <div id="similar-cases" class="reference-group">
                <h4>유사 사례 (Top-3)</h4>
                <div id="cases-list"></div>
            </div>

            <!-- KB 문서 -->
            <div id="kb-articles" class="reference-group">
                <h4>관련 KB 문서</h4>
                <div id="kb-list"></div>
            </div>
        </div>

        <!-- AI 제안 -->
        <div id="proposal-section" class="proposal-section" style="display: none;">
            <h3>💡 AI 제안</h3>
            
            <!-- 판단 근거 -->
            <div class="reasoning-box">
                <h4>판단 근거</h4>
                <div id="reasoning-content"></div>
            </div>

            <!-- 제안 응답 -->
            <div class="response-box">
                <h4>제안 응답</h4>
                <textarea id="draft-response" rows="10"></textarea>
            </div>

            <!-- 필드 업데이트 -->
            <div class="field-updates-box">
                <h4>티켓 필드 변경</h4>
                <div id="field-updates-list"></div>
            </div>

            <!-- 신뢰도 -->
            <div class="confidence-box">
                <h4>신뢰도</h4>
                <div id="confidence-meter"></div>
            </div>
        </div>

        <!-- 승인 버튼 -->
        <div id="approval-actions" class="approval-section" style="display: none;">
            <button id="approve-btn" class="btn btn-success">
                ✅ 승인 후 적용
            </button>
            <button id="reject-btn" class="btn btn-danger">
                ❌ 거부
            </button>
            <button id="refine-btn" class="btn btn-warning">
                🔄 보완 요청
            </button>
        </div>

        <!-- 채팅 인터페이스 (보완 모드) -->
        <div id="chat-interface" class="chat-section" style="display: none;">
            <h3>💬 AI와 대화</h3>
            <div id="chat-messages" class="chat-messages"></div>
            <div class="chat-input-group">
                <textarea id="chat-input" rows="2" placeholder="보완 요청 사항을 입력하세요..."></textarea>
                <button id="chat-send-btn" class="btn btn-primary">전송</button>
            </div>
        </div>
    </div>

    <script src="https://ajax.googleapis.com/ajax/libs/jquery/3.6.0/jquery.min.js"></script>
    <script src="scripts/app.js"></script>
</body>
</html>
```

### **Step 1.2: 프론트엔드 로직**

**파일**: `frontend/app/scripts/app.js`

```javascript
/**
 * AI Assistant FDK App
 * 
 * 주요 기능:
 * 1. 티켓 분석 트리거
 * 2. 오케스트레이션 진행 상황 실시간 표시
 * 3. 참조 내용 및 제안 표시
 * 4. 승인/반려/보완 처리
 */

(function() {
    'use strict';

    let client;
    let ticketData;
    let currentProposal;

    // FDK 초기화
    app.initialized().then(function(_client) {
        client = _client;
        
        // 티켓 데이터 가져오기
        client.data.get('ticket').then(function(data) {
            ticketData = data.ticket;
            console.log('Ticket loaded:', ticketData);
        });

        // 이벤트 리스너 등록
        registerEventListeners();
    });

    function registerEventListeners() {
        // 분석 시작 버튼
        $('#analyze-btn').on('click', startAnalysis);

        // 승인 버튼
        $('#approve-btn').on('click', approveProposal);
        $('#reject-btn').on('click', rejectProposal);
        $('#refine-btn').on('click', openChatInterface);

        // 채팅 전송
        $('#chat-send-btn').on('click', sendChatMessage);
    }

    /**
     * Step 1: 티켓 분석 시작
     */
    async function startAnalysis() {
        try {
            updateStatus('분석 중...', 'info');
            $('#analyze-btn').prop('disabled', true);
            $('#orchestration-progress').show();

            // 테넌트 정보 구성
            const tenantInfo = {
                tenant_id: getTenantId(),
                platform: 'freshdesk'
            };

            // 백엔드 API 호출 (스트리밍)
            const response = await fetch(getBackendUrl('/api/v1/assist/analyze'), {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Tenant-ID': tenantInfo.tenant_id,
                    'X-Platform': tenantInfo.platform
                },
                body: JSON.stringify({
                    ticket_id: ticketData.id,
                    stream_progress: true  // 진행 상황 스트리밍 요청
                })
            });

            // 스트리밍 응답 처리
            const reader = response.body.getReader();
            const decoder = new TextDecoder();

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value);
                const events = chunk.split('\n\n').filter(e => e.trim());

                for (const event of events) {
                    if (event.startsWith('data: ')) {
                        const data = JSON.parse(event.slice(6));
                        handleStreamEvent(data);
                    }
                }
            }

        } catch (error) {
            console.error('Analysis failed:', error);
            updateStatus('분석 실패', 'danger');
            showNotification('error', '분석 중 오류가 발생했습니다.');
        }
    }

    /**
     * Step 2: 스트리밍 이벤트 처리
     */
    function handleStreamEvent(event) {
        console.log('Stream event:', event);

        switch (event.type) {
            case 'router_decision':
                updateStepStatus('router', 'progress');
                $('#router-detail').html(`
                    <div class="reasoning">
                        <strong>판단:</strong> ${event.decision}<br>
                        <strong>근거:</strong> ${event.reasoning}<br>
                        <strong>임베딩 모드:</strong> ${event.embedding_mode ? '활성화' : '비활성화'}
                    </div>
                `);
                setTimeout(() => updateStepStatus('router', 'complete'), 500);
                break;

            case 'retriever_start':
                updateStepStatus('retriever', 'progress');
                $('#retriever-detail').text(event.mode === 'embedding' 
                    ? '유사 사례 검색 중...' 
                    : 'KB 문서 검색 중...');
                break;

            case 'retriever_results':
                updateStepStatus('retriever', 'complete');
                displayReferences(event.results);
                break;

            case 'resolution_start':
                updateStepStatus('resolution', 'progress');
                $('#resolution-detail').text('솔루션 생성 중...');
                break;

            case 'resolution_complete':
                updateStepStatus('resolution', 'complete');
                displayProposal(event.proposal);
                break;

            case 'error':
                handleError(event);
                break;
        }
    }

    /**
     * Step 3: 참조 내용 표시
     */
    function displayReferences(results) {
        $('#reference-section').show();

        // 유사 사례
        if (results.similar_cases && results.similar_cases.length > 0) {
            const casesHtml = results.similar_cases.slice(0, 3).map((c, idx) => `
                <div class="reference-item">
                    <div class="ref-header">
                        <span class="ref-number">#${idx + 1}</span>
                        <span class="ref-score">유사도: ${(c.score * 100).toFixed(1)}%</span>
                    </div>
                    <div class="ref-title">
                        <a href="${c.url}" target="_blank">티켓 #${c.ticket_id}</a>
                    </div>
                    <div class="ref-summary">${c.summary}</div>
                    <div class="ref-tags">
                        ${c.tags.map(tag => `<span class="tag">${tag}</span>`).join('')}
                    </div>
                </div>
            `).join('');
            $('#cases-list').html(casesHtml);
        } else {
            $('#cases-list').html('<p class="text-muted">유사 사례가 없습니다.</p>');
        }

        // KB 문서
        if (results.kb_articles && results.kb_articles.length > 0) {
            const kbHtml = results.kb_articles.slice(0, 2).map((kb, idx) => `
                <div class="reference-item">
                    <div class="ref-header">
                        <span class="ref-number">#${idx + 1}</span>
                    </div>
                    <div class="ref-title">
                        <a href="${kb.url}" target="_blank">${kb.title}</a>
                    </div>
                    <div class="ref-summary">${kb.excerpt}</div>
                </div>
            `).join('');
            $('#kb-list').html(kbHtml);
        } else {
            $('#kb-list').html('<p class="text-muted">관련 KB 문서가 없습니다.</p>');
        }
    }

    /**
     * Step 4: AI 제안 표시
     */
    function displayProposal(proposal) {
        currentProposal = proposal;
        $('#proposal-section').show();
        $('#approval-actions').show();

        // 판단 근거
        $('#reasoning-content').html(`
            <div class="reasoning-item">
                <strong>분석 모드:</strong> ${proposal.mode === 'synthesis' ? '검색 기반' : '직접 분석'}
            </div>
            <div class="reasoning-item">
                <strong>참조한 사례:</strong> ${proposal.similar_cases ? proposal.similar_cases.length : 0}개
            </div>
            <div class="reasoning-item">
                <strong>참조한 KB:</strong> ${proposal.kb_references ? proposal.kb_references.length : 0}개
            </div>
            <div class="reasoning-item">
                <strong>분석 시간:</strong> ${proposal.analysis_time_ms}ms
            </div>
        `);

        // 제안 응답
        $('#draft-response').val(proposal.draft_response);

        // 필드 업데이트
        if (proposal.field_updates) {
            const fieldsHtml = Object.entries(proposal.field_updates).map(([field, value]) => `
                <div class="field-update-item">
                    <span class="field-name">${field}:</span>
                    <span class="field-value">${JSON.stringify(value)}</span>
                </div>
            `).join('');
            $('#field-updates-list').html(fieldsHtml);
        }

        // 신뢰도
        const confidence = proposal.confidence || 'medium';
        const confidencePercent = confidence === 'high' ? 90 : confidence === 'medium' ? 60 : 30;
        $('#confidence-meter').html(`
            <div class="progress">
                <div class="progress-bar bg-${confidence === 'high' ? 'success' : confidence === 'medium' ? 'warning' : 'danger'}" 
                     style="width: ${confidencePercent}%">
                    ${confidencePercent}%
                </div>
            </div>
        `);

        updateStatus('분석 완료', 'success');
    }

    /**
     * Step 5: 승인 처리
     */
    async function approveProposal() {
        try {
            updateStatus('적용 중...', 'info');

            // 백엔드에 승인 전송
            const response = await fetch(getBackendUrl('/api/v1/assist/approve'), {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Tenant-ID': getTenantId()
                },
                body: JSON.stringify({
                    ticket_id: ticketData.id,
                    proposal_id: currentProposal.id,
                    action: 'approve',
                    final_response: $('#draft-response').val()
                })
            });

            const result = await response.json();

            if (result.success) {
                // 1. 티켓 필드 업데이트
                await updateTicketFields(result.field_updates);

                // 2. 응답 에디터에 삽입
                await insertResponseToEditor(result.final_response);

                showNotification('success', '제안이 적용되었습니다.');
                updateStatus('적용 완료', 'success');
                
                // 패널 초기화
                setTimeout(resetPanel, 2000);
            }

        } catch (error) {
            console.error('Approval failed:', error);
            showNotification('error', '적용 중 오류가 발생했습니다.');
        }
    }

    /**
     * Step 6: 거부 처리
     */
    async function rejectProposal() {
        try {
            await fetch(getBackendUrl('/api/v1/assist/approve'), {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Tenant-ID': getTenantId()
                },
                body: JSON.stringify({
                    ticket_id: ticketData.id,
                    proposal_id: currentProposal.id,
                    action: 'reject'
                })
            });

            showNotification('info', '제안이 거부되었습니다.');
            resetPanel();

        } catch (error) {
            console.error('Rejection failed:', error);
        }
    }

    /**
     * Step 7: 보완 요청 (채팅)
     */
    function openChatInterface() {
        $('#chat-interface').show();
        $('#approval-actions').hide();
    }

    async function sendChatMessage() {
        const message = $('#chat-input').val().trim();
        if (!message) return;

        // 메시지 표시
        appendChatMessage('user', message);
        $('#chat-input').val('');

        try {
            // AI에게 보완 요청
            const response = await fetch(getBackendUrl('/api/v1/assist/refine'), {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Tenant-ID': getTenantId()
                },
                body: JSON.stringify({
                    ticket_id: ticketData.id,
                    proposal_id: currentProposal.id,
                    refinement_request: message
                })
            });

            const result = await response.json();

            // AI 응답 표시
            appendChatMessage('assistant', result.refined_response);

            // 제안 업데이트
            $('#draft-response').val(result.refined_response);

        } catch (error) {
            console.error('Chat failed:', error);
            appendChatMessage('system', '보완 요청 처리 중 오류가 발생했습니다.');
        }
    }

    /**
     * Helper: 티켓 필드 업데이트
     */
    async function updateTicketFields(fieldUpdates) {
        if (!fieldUpdates) return;

        const updates = {};
        
        if (fieldUpdates.priority) {
            updates.priority = fieldUpdates.priority;
        }
        if (fieldUpdates.status) {
            updates.status = fieldUpdates.status;
        }
        if (fieldUpdates.tags) {
            updates.tags = fieldUpdates.tags;
        }

        // Freshdesk API 호출
        return client.request.invoke('updateTicket', {
            context: { ticketId: ticketData.id },
            body: JSON.stringify(updates)
        });
    }

    /**
     * Helper: 응답 에디터에 삽입
     */
    async function insertResponseToEditor(responseText) {
        return client.interface.trigger('setValue', {
            id: 'editor',
            value: responseText
        });
    }

    /**
     * Helper: 채팅 메시지 추가
     */
    function appendChatMessage(role, content) {
        const messageHtml = `
            <div class="chat-message ${role}">
                <div class="message-content">${content}</div>
            </div>
        `;
        $('#chat-messages').append(messageHtml);
        $('#chat-messages').scrollTop($('#chat-messages')[0].scrollHeight);
    }

    /**
     * Helper: 단계 상태 업데이트
     */
    function updateStepStatus(step, status) {
        const $step = $(`.step[data-step="${step}"]`);
        $step.removeClass('pending progress complete error');
        $step.addClass(status);

        const icon = status === 'complete' ? '✓' : 
                     status === 'progress' ? '⟳' : 
                     status === 'error' ? '✗' : '';
        $step.find('.step-status').text(icon);
    }

    /**
     * Helper: 상태 배지 업데이트
     */
    function updateStatus(text, type) {
        $('#status-badge')
            .removeClass('badge-info badge-success badge-warning badge-danger')
            .addClass(`badge-${type}`)
            .text(text);
    }

    /**
     * Helper: 알림 표시
     */
    function showNotification(type, message) {
        client.interface.trigger('showNotify', {
            type: type,
            message: message
        });
    }

    /**
     * Helper: 패널 초기화
     */
    function resetPanel() {
        $('#orchestration-progress').hide();
        $('#reference-section').hide();
        $('#proposal-section').hide();
        $('#approval-actions').hide();
        $('#chat-interface').hide();
        $('#analyze-btn').prop('disabled', false);
        updateStatus('준비', 'info');
    }

    /**
     * Helper: 테넌트 ID 추출
     */
    function getTenantId() {
        // Freshdesk 도메인에서 추출
        const domain = window.location.hostname;
        return domain.split('.')[0];
    }

    /**
     * Helper: 백엔드 URL 생성
     */
    function getBackendUrl(path) {
        return window.BACKEND_CONFIG.getUrl(path);
    }

})();
```

---

## Phase 2: 백엔드 API 구현

### 📍 위치: `backend/routes/assist.py`

### **Step 2.1: 분석 API (스트리밍)**

```python
"""
AI Assistant API - 티켓 분석 및 제안
"""
from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any
import json
import asyncio

from backend.agents.orchestrator import create_workflow_graph
from backend.models.graph_state import AgentState
from backend.services.freshdesk import FreshdeskService
from backend.repositories.tenant_repository import TenantRepository
from backend.utils.logger import get_logger

router = APIRouter(prefix="/api/v1/assist", tags=["assist"])
logger = get_logger(__name__)

# 리포지토리
tenant_repo = TenantRepository()
freshdesk = FreshdeskService()


class AnalyzeRequest(BaseModel):
    """분석 요청"""
    ticket_id: str
    stream_progress: bool = True


@router.post("/analyze")
async def analyze_ticket(
    request: AnalyzeRequest,
    tenant_id: str = Header(..., alias="X-Tenant-ID"),
    platform: str = Header(..., alias="X-Platform")
):
    """
    티켓 분석 시작 (스트리밍 응답)
    
    이벤트 타입:
    - router_decision: 라우팅 판단 결과
    - retriever_start: 검색 시작
    - retriever_results: 검색 결과
    - resolution_start: 솔루션 생성 시작
    - resolution_complete: 최종 제안
    - error: 오류 발생
    """
    try:
        # 1. 테넌트 설정 조회
        tenant_config = await tenant_repo.get_config(
            tenant_id=tenant_id,
            platform=platform
        )
        
        if not tenant_config:
            raise HTTPException(status_code=404, detail="Tenant not found")
        
        # 2. 티켓 데이터 가져오기
        ticket = await freshdesk.fetch_ticket(request.ticket_id)
        conversations = await freshdesk.fetch_ticket_conversations(request.ticket_id)
        ticket['conversations'] = conversations
        
        # 3. 스트리밍 응답 생성
        async def event_stream():
            try:
                # 초기 상태 생성
                initial_state: AgentState = {
                    "ticket_context": {
                        "id": ticket['id'],
                        "subject": ticket.get('subject', ''),
                        "description": ticket.get('description_text', ''),
                        "conversations": conversations,
                        "status": ticket.get('status'),
                        "priority": ticket.get('priority'),
                        "tags": ticket.get('tags', [])
                    },
                    "embedding_mode": tenant_config.embedding_enabled,
                    "metadata": {
                        "tenant_id": tenant_id,
                        "platform": platform,
                        "max_tokens": tenant_config.llm_max_tokens,
                        "analysis_depth": tenant_config.analysis_depth
                    }
                }
                
                # 워크플로우 실행 (스트리밍 콜백)
                workflow = create_workflow_graph()
                
                async for event in stream_workflow_events(workflow, initial_state):
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                    await asyncio.sleep(0.1)  # 클라이언트 처리 시간
                
            except Exception as e:
                logger.error(f"Stream error: {e}", exc_info=True)
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        
        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no"
            }
        )
        
    except Exception as e:
        logger.error(f"Analyze failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


async def stream_workflow_events(workflow, initial_state: AgentState):
    """
    워크플로우 실행 중 이벤트 스트리밍
    """
    import time
    
    # 각 노드 실행 시 이벤트 발생
    current_node = "start"
    state = initial_state
    
    # 1. Router 이벤트
    yield {
        "type": "router_decision",
        "timestamp": time.time(),
        "decision": "retrieve_cases" if state.get("embedding_mode") else "propose_solution_direct",
        "reasoning": "임베딩 데이터 기반 유사 사례 검색" if state.get("embedding_mode") else "직접 분석 모드",
        "embedding_mode": state.get("embedding_mode", False)
    }
    
    # 2. Retriever 이벤트 (임베딩 모드인 경우)
    if state.get("embedding_mode"):
        yield {
            "type": "retriever_start",
            "timestamp": time.time(),
            "mode": "embedding"
        }
        
        # 워크플로우 실행 (검색 수행)
        from backend.agents.retriever import retrieve_cases
        state = await retrieve_cases(state)
        
        yield {
            "type": "retriever_results",
            "timestamp": time.time(),
            "results": {
                "similar_cases": state.get("search_results", {}).get("similar_cases", []),
                "kb_articles": state.get("search_results", {}).get("kb_procedures", [])
            }
        }
    
    # 3. Resolution 이벤트
    yield {
        "type": "resolution_start",
        "timestamp": time.time()
    }
    
    # 워크플로우 실행 (솔루션 생성)
    if state.get("embedding_mode"):
        from backend.agents.resolver import propose_solution
        state = await propose_solution(state)
    else:
        from backend.agents.resolver import propose_solution_direct
        state = await propose_solution_direct(state)
    
    yield {
        "type": "resolution_complete",
        "timestamp": time.time(),
        "proposal": state.get("proposed_action", {})
    }
```

### **Step 2.2: 승인 API**

```python
class ApprovalRequest(BaseModel):
    """승인 요청"""
    ticket_id: str
    proposal_id: str
    action: str  # approve | reject | refine
    final_response: Optional[str] = None
    refinement_request: Optional[str] = None


@router.post("/approve")
async def approve_proposal(
    request: ApprovalRequest,
    tenant_id: str = Header(..., alias="X-Tenant-ID")
):
    """
    AI 제안 승인/거부 처리
    """
    try:
        from backend.repositories.approval_repository import ApprovalRepository
        approval_repo = ApprovalRepository()
        
        if request.action == "approve":
            # 1. 승인 로그 저장
            await approval_repo.create(
                tenant_id=tenant_id,
                ticket_id=request.ticket_id,
                draft_response=request.final_response,
                final_response=request.final_response,
                approval_status="approved"
            )
            
            # 2. 티켓 필드 업데이트 (Freshdesk API)
            field_updates = await get_field_updates(request.proposal_id)
            if field_updates:
                await freshdesk.update_ticket(
                    request.ticket_id,
                    field_updates
                )
            
            return {
                "success": True,
                "field_updates": field_updates,
                "final_response": request.final_response
            }
            
        elif request.action == "reject":
            # 거부 로그 저장
            await approval_repo.create(
                tenant_id=tenant_id,
                ticket_id=request.ticket_id,
                approval_status="rejected"
            )
            
            return {"success": True, "action": "rejected"}
        
    except Exception as e:
        logger.error(f"Approval failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/refine")
async def refine_proposal(
    request: ApprovalRequest,
    tenant_id: str = Header(..., alias="X-Tenant-ID")
):
    """
    AI 제안 보완 (채팅)
    """
    try:
        from backend.services.llm_service import LLMService
        llm = LLMService()
        
        # 원래 제안 가져오기
        original_proposal = await get_proposal(request.proposal_id)
        
        # LLM에 보완 요청
        refined_response = await llm.refine_response(
            original_response=original_proposal['draft_response'],
            refinement_request=request.refinement_request,
            ticket_context=original_proposal['ticket_context']
        )
        
        return {
            "success": True,
            "refined_response": refined_response
        }
        
    except Exception as e:
        logger.error(f"Refinement failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
```

---

## Phase 3: 테넌트 설정 관리

### **Step 3.1: 테넌트 Repository**

**파일**: `backend/repositories/tenant_repository.py`

```python
"""
Tenant Repository - 테넌트 설정 관리
"""
from typing import Optional
from backend.config import get_settings
from backend.utils.logger import get_logger

settings = get_settings()
logger = get_logger(__name__)


class TenantConfig:
    """테넌트 설정 모델"""
    def __init__(self, data: dict):
        self.tenant_id = data['tenant_id']
        self.platform = data['platform']
        self.embedding_enabled = data.get('embedding_enabled', True)
        self.analysis_depth = data.get('analysis_depth', 'full')
        self.llm_max_tokens = data.get('llm_max_tokens', 1500)


class TenantRepository:
    """테넌트 설정 리포지토리"""
    
    def __init__(self):
        from supabase import create_client
        self.client = create_client(
            settings.supabase_url,
            settings.supabase_service_role_key
        )
    
    async def get_config(
        self,
        tenant_id: str,
        platform: str
    ) -> Optional[TenantConfig]:
        """
        테넌트 설정 조회
        """
        try:
            response = self.client.table("tenant_configs").select("*").eq(
                "tenant_id", tenant_id
            ).eq(
                "platform", platform
            ).execute()
            
            if response.data:
                return TenantConfig(response.data[0])
            
            # 기본 설정 반환
            logger.warning(f"Tenant config not found, using defaults: {tenant_id}")
            return TenantConfig({
                "tenant_id": tenant_id,
                "platform": platform,
                "embedding_enabled": True,
                "analysis_depth": "full",
                "llm_max_tokens": 1500
            })
            
        except Exception as e:
            logger.error(f"Failed to get tenant config: {e}")
            raise
```

### **Step 3.2: 마이그레이션**

**파일**: `backend/migrations/002_tenant_configs.sql`

```sql
-- 테넌트 설정 테이블
CREATE TABLE IF NOT EXISTS tenant_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id TEXT NOT NULL,
    platform TEXT NOT NULL,  -- freshdesk, zendesk, intercom
    embedding_enabled BOOLEAN DEFAULT true,
    analysis_depth TEXT DEFAULT 'full',  -- full | summary | minimal
    llm_max_tokens INTEGER DEFAULT 1500,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, platform)
);

COMMENT ON TABLE tenant_configs IS '테넌트별 AI 어시스턴트 설정';
COMMENT ON COLUMN tenant_configs.embedding_enabled IS '임베딩 데이터 수집 여부 (프라이버시)';
COMMENT ON COLUMN tenant_configs.analysis_depth IS '분석 깊이 (full=전체, summary=요약, minimal=최소)';

-- 인덱스
CREATE INDEX idx_tenant_configs_lookup 
ON tenant_configs(tenant_id, platform);

-- 샘플 데이터
INSERT INTO tenant_configs (tenant_id, platform, embedding_enabled)
VALUES 
    ('demo-tenant', 'freshdesk', true),
    ('privacy-tenant', 'freshdesk', false)
ON CONFLICT DO NOTHING;
```

---

## Phase 4: 에이전트 오케스트레이션 강화

### **Step 4.1: 직접 분석 노드 추가**

**파일**: `backend/agents/resolver.py`

```python
async def propose_solution_direct(state: AgentState) -> AgentState:
    """
    임베딩 없는 모드: 티켓 원문 직접 분석
    """
    from backend.services.llm_service import LLMService
    llm = LLMService()
    
    ticket_context = state.get("ticket_context", {})
    metadata = state.get("metadata", {})
    
    # 티켓 전문 결합
    full_content = f"""
제목: {ticket_context.get('subject')}

본문:
{ticket_context.get('description')}

대화 내역 ({len(ticket_context.get('conversations', []))}개):
"""
    
    for idx, conv in enumerate(ticket_context.get('conversations', []), 1):
        sender = conv.get('from_email', 'Unknown')
        body = conv.get('body_text', '')
        full_content += f"\n[대화 {idx}] {sender}:\n{body}\n"
    
    # LLM 직접 분석
    max_tokens = metadata.get('max_tokens', 2000)
    
    analysis = await llm.analyze_ticket_direct(
        ticket_content=full_content,
        max_tokens=max_tokens
    )
    
    # 제안 구성
    state["proposed_action"] = {
        "id": f"proposal-{ticket_context.get('id')}-{int(time.time())}",
        "draft_response": analysis['response'],
        "field_updates": analysis.get('field_updates', {}),
        "confidence": "low",  # 과거 사례 없음
        "mode": "direct",
        "similar_cases": None,
        "kb_references": None,
        "analysis_time_ms": analysis.get('time_ms', 0)
    }
    
    return state
```

---

## Phase 5: 테스트 시나리오

### **시나리오 1: 임베딩 활성화 (검색 기반)**

```bash
# 1. 테넌트 설정
INSERT INTO tenant_configs (tenant_id, platform, embedding_enabled)
VALUES ('test-customer', 'freshdesk', true);

# 2. 티켓 생성 (Freshdesk)
# 3. FDK 앱에서 "티켓 분석 시작" 클릭
# 4. 진행 상황 확인:
#    - Router: "임베딩 데이터 기반 유사 사례 검색"
#    - Retriever: 유사 사례 3개, KB 문서 2개 표시
#    - Resolution: 검색 기반 솔루션
# 5. 승인 → 티켓 필드 자동 업데이트 + 응답 삽입
```

### **시나리오 2: 임베딩 비활성화 (직접 분석)**

```bash
# 1. 테넌트 설정
INSERT INTO tenant_configs (tenant_id, platform, embedding_enabled)
VALUES ('privacy-customer', 'freshdesk', false);

# 2. 티켓 생성
# 3. "티켓 분석 시작" 클릭
# 4. 진행 상황 확인:
#    - Router: "직접 분석 모드"
#    - Resolution: 티켓 원문 기반 분석 (검색 스킵)
#    - 신뢰도: 낮음 (과거 사례 없음)
# 5. 승인 또는 보완 요청
```

### **시나리오 3: 보완 요청 (채팅)**

```bash
# 1. 분석 완료 후
# 2. "보완 요청" 클릭
# 3. 채팅창에 입력: "좀 더 친절한 톤으로 작성해주세요"
# 4. AI 응답 수신
# 5. 응답 업데이트 확인
# 6. 승인
```

---

## 체크리스트

### **프론트엔드**
- [ ] FDK 앱 UI 구현 (`frontend/app/`)
- [ ] 스트리밍 이벤트 처리
- [ ] 진행 상황 시각화
- [ ] 승인/반려/보완 버튼
- [ ] 채팅 인터페이스
- [ ] 티켓 필드 업데이트 함수
- [ ] 에디터 응답 삽입 함수

### **백엔드**
- [ ] `/api/v1/assist/analyze` (스트리밍)
- [ ] `/api/v1/assist/approve`
- [ ] `/api/v1/assist/refine`
- [ ] 테넌트 설정 Repository
- [ ] 직접 분석 노드 (`propose_solution_direct`)
- [ ] 워크플로우 이벤트 스트리밍

### **데이터베이스**
- [ ] `tenant_configs` 테이블 생성
- [ ] 샘플 테넌트 데이터 삽입
- [ ] 인덱스 최적화

### **테스트**
- [ ] 임베딩 모드 시나리오
- [ ] 직접 분석 모드 시나리오
- [ ] 보완 요청 시나리오
- [ ] 에러 핸들링

---

## 다음 단계

POC 검증 후:
1. **성능 측정**: 분석 시간, LLM 비용, 승인률
2. **피드백 수집**: 상담원 UX 개선
3. **확장 기능**: 
   - 청크 분할 (긴 티켓)
   - 재랭커 파인튜닝
   - 신뢰도 개선

---

이 가이드로 POC를 시작하시면 됩니다! 🚀
