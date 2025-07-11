/**
 * Freshdesk Custom App - Simplified Version
 * 단순하고 빠른 AI 상담사 지원 시스템
 */

const App = {
  // 설정 (환경변수 또는 런타임에서 설정)
  config: {
    baseURL: window.APP_CONFIG?.baseURL || 'http://localhost:8000',
    apiKey: window.APP_CONFIG?.apiKey || '',
    tenantId: window.APP_CONFIG?.tenantId || '',
    domain: window.APP_CONFIG?.domain || ''
  },

  // 현재 상태
  state: {
    ticketId: null,
    
    // 데이터 로딩 상태 (세분화)
    loadingState: 'idle', // 'idle', 'loading', 'success', 'error'
    isLoading: false, // 하위 호환성을 위해 유지
    BACKEND_CALLED: false, // 백엔드 호출 여부 - 한 번 호출되면 절대 다시 호출 안함
    dataLoaded: false, // 초기 데이터 로드 완료 여부
    loadingError: null, // 로딩 에러 정보
    
    currentMode: 'smart', // 'smart' or 'free'
    client: null, // FDK 클라이언트 객체
    
    // 대화 히스토리 (맥락 유지용)
    chatHistory: [],
    
    // 로드된 데이터 캐시 (탭 전환 시 사라지지 않도록)
    cachedData: {
      similarTickets: [],
      kbDocuments: [],
      summary: ''
    },
    
    // 유사 티켓 상세 보기 상태
    ticketDetailView: {
      isDetailView: false,
      currentTicketIndex: -1,
      currentTicketData: null
    },
    
    // 티켓 정보 캐시 (헤더 표시용)
    cachedTicketInfo: {
      ticket: null,
      contact: null,
      group: null,
      agent: null,
      ticketFields: null,
      lastUpdated: null
    },
    
    // 백엔드에서 받은 티켓 데이터
    backendTicketData: null,
    
    // FDK에서 받은 원본 티켓 데이터 (추가 정보 수집용)
    originalFDKTicket: null,
    
    // FDK 옵션 캐시 (성능 최적화)
    fdkOptionsCache: {
      priorityOptions: null,
      statusOptions: null,
      lastFetched: null
    },
    
    // 메타데이터 서비스 인스턴스
    metadataService: null
  },

  // API 통신
  api: {
    // 기본 헤더 생성
    getHeaders() {
      return {
        'Content-Type': 'application/json',
        'X-Tenant-ID': App.config.tenantId,
        'X-Platform': 'freshdesk',
        'X-Domain': App.config.domain,
        'X-API-Key': App.config.apiKey
      };
    },


    // 초기 데이터 로드 - 페이지 최초 로딩 시에만 호출
    async loadInitialData(ticketId) {
      // 이미 호출했으면 캐시 반환
      if (App.state.BACKEND_CALLED) {
        console.log('🚫 백엔드 이미 호출됨 - 캐시 반환');
        return App.state.cachedData;
      }
      
      // 로딩 상태 시작
      App.state.BACKEND_CALLED = true;
      App.state.loadingState = 'loading';
      App.state.loadingError = null;
      console.log('🔥 페이지 최초 로딩 - 백엔드 호출 시작');
      
      const url = `${App.config.baseURL}/init/${ticketId}?stream=true`;
      
      try {
        const response = await fetch(url, {
          method: 'GET',
          headers: this.getHeaders()
        });
        
        if (!response.ok) {
          throw new Error(`백엔드 서버 오류: ${response.status}`);
        }
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let summary = '';
        let similarTickets = [];
        let kbDocuments = [];
        
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          
          buffer += decoder.decode(value, { stream: true });
          const chunks = buffer.split('\n\n');
          buffer = chunks.pop();
          
          for (const chunk of chunks) {
            if (!chunk.trim()) continue;
            
            const lines = chunk.split('\n');
            for (const line of lines) {
              if (line.startsWith('data: ')) {
                const dataStr = line.slice(6).trim();
                
                if (dataStr === '[DONE]') {
                  const finalData = { summary, similarTickets, kbDocuments };
                  App.state.cachedData = finalData; // 캐시에 저장
                  App.state.dataLoaded = true;
                  App.state.loadingState = 'success';
                  App.ui.hideLoading();
                  return finalData;
                }
                
                try {
                  const data = JSON.parse(dataStr);
                  const result = await App.ui.processStreamData(data, { summary, similarTickets, kbDocuments });
                  if (result) {
                    summary = result.summary || summary;
                    similarTickets = result.similarTickets || similarTickets;
                    kbDocuments = result.kbDocuments || kbDocuments;
                    
                    if (result.shouldReturn) {
                      const finalData = { summary, similarTickets, kbDocuments };
                      App.state.cachedData = finalData; // 캐시에 저장
                      App.state.dataLoaded = true;
                      App.state.loadingState = 'success';
                      App.ui.hideLoading();
                      return finalData;
                    }
                  }
                } catch (parseError) {
                  // JSON 파싱 실패는 무시
                }
              }
            }
          }
        }
        
        const finalData = { summary, similarTickets, kbDocuments };
        App.state.cachedData = finalData; // 캐시에 저장
        App.state.dataLoaded = true;
        App.state.loadingState = 'success';
        App.ui.hideLoading();
        return finalData;
        
      } catch (error) {
        // 에러 상태 설정
        App.state.loadingState = 'error';
        App.state.loadingError = error.message || '백엔드 서버 연결 실패';
        App.ui.hideLoading();
        console.error('백엔드 호출 실패:', error);
        App.ui.showError('백엔드 서버 연결 실패. 새로고침 버튼을 눌러 다시 시도하세요.');
        throw error;
      }
    },

    // 데이터 새로고침 (사용자 버튼 클릭 시)
    async refreshData() {
      console.log('🔄 사용자 새로고침 버튼 클릭 - 백엔드 재호출');
      
      // 강제로 백엔드 호출 플래그 리셋
      App.state.BACKEND_CALLED = false;
      App.state.dataLoaded = false;
      
      // 로딩 표시
      App.state.isLoading = true;
      App.ui.showLoading();
      
      try {
        const data = await this.loadInitialData(App.state.ticketId);
        
        // 캐시 업데이트
        App.state.cachedData = data;
        
        // UI 업데이트 (순차적 안전 렌더링)
        console.log('🔄 UI 순차 렌더링 시작...');
        
        // 1. 요약 업데이트
        if (data.summary) {
          try {
            App.ui.updateSummary(data.summary);
            console.log('✅ 요약 렌더링 완료');
          } catch (error) {
            console.error('❌ 요약 렌더링 실패:', error);
            App.ui.showRenderError('summaryContainer', '요약을 표시하는 중 오류가 발생했습니다.');
          }
        }
        
        // 2. 유사 티켓 렌더링
        if (data.similarTickets) {
          try {
            await App.ui.renderSimilarTickets(data.similarTickets);
            console.log('✅ 유사 티켓 렌더링 완료');
          } catch (error) {
            console.error('❌ 유사 티켓 렌더링 실패:', error);
            App.ui.showRenderError('similarTicketsContainer', '유사 티켓을 표시하는 중 오류가 발생했습니다.');
          }
        }
        
        // 3. KB 문서 렌더링
        if (data.kbDocuments) {
          try {
            App.ui.renderKBDocuments(data.kbDocuments);
            console.log('✅ KB 문서 렌더링 완료');
          } catch (error) {
            console.error('❌ KB 문서 렌더링 실패:', error);
            App.ui.showRenderError('kbDocumentsContainer', 'KB 문서를 표시하는 중 오류가 발생했습니다.');
          }
        }
        
        console.log('✅ UI 순차 렌더링 완료');
        
        console.log('✅ 새로고침 완료');
        
      } catch (error) {
        console.error('새로고침 실패:', error);
        App.ui.showError('새로고침 실패. 다시 시도해주세요.');
      }
    },

    // 채팅 쿼리 전송
    async sendChatQuery(query, mode = 'smart') {
      // 최근 10개의 대화만 전송 (성능 최적화)
      const recentHistory = App.state.chatHistory.slice(-10);
      
      let requestBody;
      
      // 자유 모드일 때는 간단한 LLM 직접 응답 요청
      if (mode === 'free') {
        requestBody = {
          query: query,
          agent_mode: true,
          stream_response: true,
          chat_history: recentHistory,
          force_intent: 'general',  // 자유 모드 명시
          // 자유 모드를 위한 최소 설정
          ticket_id: null,
          top_k: 0,  // 검색 비활성화
          search_types: [],  // 검색 타입 없음
          use_hybrid_search: false,
          enable_intent_analysis: false,
          enable_llm_enrichment: false,
          rerank_results: false
        };
        
        console.log('💭 자유 모드 요청 전송:', requestBody);
      } else {
        // 스마트 모드일 때는 기존 방식대로 RAG 검색 포함
        requestBody = {
          query: query,
          ticket_id: App.state.ticketId ? String(App.state.ticketId) : null,
          top_k: 3,
          type: ["tickets", "solutions", "images", "attachments"],
          intent: "answer",
          search_types: ["ticket", "kb"],
          min_similarity: 0.5,
          agent_mode: true,
          stream_response: true,
          chat_history: recentHistory,
          use_hybrid_search: true,
          enable_intent_analysis: true,
          enable_llm_enrichment: true,
          rerank_results: true,
          agent_context: {
            ticket: App.state.backendTicketData,
            mode: 'smart'
          }
        };
        
        console.log('🎯 스마트 모드 요청 전송:', requestBody);
      }
      
      console.log('📡 현재 모드:', mode, 'RAG 검색:', mode === 'smart');
      console.log('💬 대화 히스토리:', recentHistory.length, '개');
      
      const response = await fetch(`${App.config.baseURL}/query?stream=true`, {
        method: 'POST',
        headers: this.getHeaders(),
        body: JSON.stringify(requestBody)
      });

      if (!response.ok) {
        throw new Error(`API 오류: ${response.status}`);
      }

      // 타임아웃 설정 (30초)
      let timeoutId = null;
      const setupTimeout = () => {
        timeoutId = setTimeout(() => {
          App.ui.hideTypingIndicator();
          App.ui.addChatMessage('assistant', '응답 시간이 초과되었습니다. 다시 시도해주세요.', Date.now());
        }, 30000);
      };
      
      // 응답이 스트리밍인지 일반 JSON인지 확인
      const contentType = response.headers.get('content-type');
      
      if (contentType && contentType.includes('event-stream')) {
        // 스트리밍 응답 처리
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let messageId = Date.now();
        let fullContent = '';
        let messageCreated = false;

        // 즉시 타이핑 인디케이터 표시
        App.ui.showTypingIndicator();
        
        // 타임아웃 설정
        setupTimeout();

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop();

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const data = line.slice(6);
              if (data === '[DONE]') continue;
              
              try {
                const event = JSON.parse(data);
                console.log('📨 SSE 이벤트 수신:', event);
                
                // progress 이벤트는 무시
                if (event.type === 'progress') {
                  continue;
                }
                
                // 실제 컨텐츠가 있는지 확인
                const hasContent = (
                  (event.type === 'content' && event.content) ||
                  (event.type === 'message' && event.message) ||
                  (event.content && !event.type)
                );
                
                // 처음 컨텐츠가 오면 타이핑 인디케이터 제거하고 메시지 생성
                if (!messageCreated && hasContent) {
                  App.ui.hideTypingIndicator();
                  App.ui.addChatMessage('assistant', '', messageId);
                  messageCreated = true;
                }
                
                // 다양한 이벤트 타입 처리
                if (event.type === 'content' && event.content) {
                  fullContent += event.content;
                  if (messageCreated) {
                    App.ui.updateChatMessage(messageId, fullContent, false);
                  }
                } else if (event.type === 'message' && event.message) {
                  // 백엔드가 message 타입으로 보낼 수도 있음
                  fullContent += event.message;
                  if (messageCreated) {
                    App.ui.updateChatMessage(messageId, fullContent, false);
                  }
                } else if (event.type === 'complete') {
                  // complete 이벤트 처리 - ai_summary만 사용
                  if (event.data?.ai_summary) {
                    fullContent = event.data.ai_summary;
                    if (messageCreated) {
                      App.ui.updateChatMessage(messageId, fullContent, false);
                    }
                  }
                  // message는 무시 (백엔드의 불필요한 메시지 방지)
                } else if (event.content) {
                  // type 없이 content만 있는 경우
                  fullContent += event.content;
                  if (messageCreated) {
                    App.ui.updateChatMessage(messageId, fullContent, false);
                  }
                }
              } catch (e) {
                console.error('SSE 파싱 오류:', e, 'data:', data);
              }
            }
          }
        }
        
        // 타임아웃 취소
        if (timeoutId) clearTimeout(timeoutId);
        
        // 메시지가 생성되지 않았거나 컨텐츠가 없는 경우 처리
        if (!messageCreated) {
          App.ui.hideTypingIndicator();
          App.ui.addChatMessage('assistant', '응답을 받을 수 없습니다.', messageId);
          App.state.chatHistory.push({ role: 'assistant', content: '응답을 받을 수 없습니다.' });
        } else if (!fullContent) {
          App.ui.updateChatMessage(messageId, '응답이 비어있습니다.', true);
          App.state.chatHistory.push({ role: 'assistant', content: '응답이 비어있습니다.' });
        } else {
          // 정상적인 응답을 히스토리에 추가
          App.state.chatHistory.push({ role: 'assistant', content: fullContent });
        }
        
        // 스트리밍 완료 후 확실하게 하단으로 스크롤
        App.ui.scrollToBottom(true);
        
        // iframe 환경에서 추가 보장
        setTimeout(() => App.ui.scrollToBottom(true), 100);
        setTimeout(() => App.ui.scrollToBottom(true), 300);
        setTimeout(() => App.ui.scrollToBottom(true), 500);
      } else {
        // 즉시 타이핑 인디케이터 표시
        App.ui.showTypingIndicator();
        
        // 타임아웃 설정
        setupTimeout();
        
        // 일반 JSON 응답 처리
        const result = await response.json();
        const messageId = Date.now();
        
        // 타이핑 인디케이터 제거
        App.ui.hideTypingIndicator();
        
        // 타임아웃 취소
        if (timeoutId) clearTimeout(timeoutId);
        
        if (result.answer) {
          // 스트리밍 효과를 위해 천천히 타이핑
          App.ui.addChatMessage('assistant', '', messageId, true);
          await App.ui.typeMessage(messageId, result.answer);
          App.ui.updateChatMessage(messageId, result.answer, true);
          // 히스토리에 추가
          App.state.chatHistory.push({ role: 'assistant', content: result.answer });
        } else {
          App.ui.addChatMessage('assistant', '응답을 받을 수 없습니다.', messageId);
          App.state.chatHistory.push({ role: 'assistant', content: '응답을 받을 수 없습니다.' });
        }
        
        // 응답 완료 후 확실하게 하단으로 스크롤
        App.ui.scrollToBottom(true);
        
        // iframe 환경에서 추가 보장
        setTimeout(() => App.ui.scrollToBottom(true), 100);
        setTimeout(() => App.ui.scrollToBottom(true), 300);
        setTimeout(() => App.ui.scrollToBottom(true), 500);
      }
    }
  },

  // UI 렌더링
  ui: {
    // 최적화된 FDK 데이터 수집 (data method 활용)
    async collectOptimizedTicketData() {
      console.log('🔍 최적화된 FDK 데이터 수집 시작');
      
      if (!App.state.client) {
        console.warn('⚠️ FDK Client가 없어 데이터 수집 불가');
        return;
      }
      
      const client = App.state.client;
      
      try {
        // 1. 기본 FDK data method로 필요한 모든 정보 한 번에 수집
        console.log('🔍 FDK data method로 기본 데이터 수집 시작...');
        
        const [ticketData, contactData, groupData, loggedInUser] = await Promise.all([
          client.data.get('ticket').catch(e => {
            console.warn('⚠️ ticket 데이터 조회 실패:', e);
            return null;
          }),
          client.data.get('contact').catch(e => {
            console.warn('⚠️ contact 데이터 조회 실패:', e);
            return null;
          }),
          client.data.get('group').catch(e => {
            console.warn('⚠️ group 데이터 조회 실패:', e);
            return null;
          }),
          client.data.get('loggedInUser').catch(e => {
            console.warn('⚠️ loggedInUser 데이터 조회 실패:', e);
            return null;
          })
        ]);
        
        console.log('✅ FDK 기본 데이터 수집 완료');
        console.log('🎫 Ticket 데이터:', ticketData);
        console.log('👤 Contact 데이터:', contactData);
        console.log('👥 Group 데이터:', groupData);
        console.log('🏢 LoggedInUser 데이터:', loggedInUser);
        
        // 2. 백엔드 데이터와 FDK 데이터 통합
        const mergedTicketData = this.mergeTicketData(
          App.state.backendTicketData,
          ticketData?.ticket,
          App.state.originalFDKTicket
        );
        
        // 3. 상태 레이블 가져오기 (통합 유틸리티 사용)
        console.log('🚨 [CRITICAL] 상태 레이블 가져오기 시작 - 함수 호출 시점:', new Date().toISOString());
        let statusLabel = '❌ 상태 없음';
        if (mergedTicketData && mergedTicketData.status !== undefined && mergedTicketData.status !== null) {
          console.log('🚨 mergedTicketData.status:', mergedTicketData.status);
          console.log('🚨 TicketLabelUtils 사용하여 상태 레이블 가져오기');
          
          // 통합 유틸리티 사용 (캐싱 및 fallback 포함)
          statusLabel = await TicketLabelUtils.getStatusLabel(mergedTicketData);
          console.log('✅ 상태 레이블 결과:', statusLabel);
        }
        
        // 4. 에이전트 정보 처리 (API 호출 필요)
        let agentData = await this.processAgentData(mergedTicketData, loggedInUser, client);
        
        // 5. 통합된 데이터 구성
        const optimizedTicketData = {
          ticket: { ticket: mergedTicketData },
          contact: contactData,
          group: groupData || this.extractGroupFromTicket(mergedTicketData),
          agent: agentData,
          statusLabel: statusLabel,
          lastUpdated: Date.now()
        };
        
        // 6. 캐시에 저장
        App.state.cachedTicketInfo = optimizedTicketData;
        console.log('✅ 최적화된 데이터 수집 완료 및 캐시 저장');
        
        // 7. 헤더 업데이트
        await App.ui.updateTicketHeader(optimizedTicketData);
        
      } catch (error) {
        console.error('❌ 최적화된 FDK 데이터 수집 실패:', error);
      }
    },
    
    // 백엔드, FDK, 원본 티켓 데이터 통합
    mergeTicketData(backendData, fdkData, originalData) {
      console.log('🔄 티켓 데이터 통합 시작');
      
      // 우선순위: 백엔드 > FDK > 원본
      const merged = {
        ...(originalData || {}),
        ...(fdkData || {}),
        ...(backendData || {})
      };
      
      console.log('✅ 티켓 데이터 통합 완료:', merged);
      return merged;
    },
    
    
    // 에이전트 이름 캐시 (성능 최적화)
    agentNameCache: {},
    
    // 에이전트 이름 가져오기 (초간단 버전)
    async getAgentName(agentId, client) {
      console.log('🔍 getAgentName 호출 시작, agentId:', agentId);
      
      try {
        console.log('🔍 invokeTemplate 시도 중...');
        const response = await client.request.invokeTemplate('getAgent', {
          context: { agentId: agentId }
        });
        
        console.log('✅ invokeTemplate 성공, response:', response);
        
        const agent = JSON.parse(response.response);
        console.log('✅ 에이전트 파싱 성공:', agent);
        
        if (agent && agent.contact && agent.contact.name) {
          console.log('✅ 에이전트 이름 반환:', agent.contact.name);
          return agent.contact.name;
        } else {
          console.warn('⚠️ 에이전트 응답 구조 이상:', agent);
          return `Agent ${agentId}`;
        }
        
      } catch (error) {
        console.error('❌ getAgentName 오류:', error);
        console.error('❌ 오류 상세:', error.message);
        return 'Unassigned';
      }
    },

    // 그룹 이름 가져오기
    async getGroupName(groupId, client) {
      console.log('🔍 getGroupName 호출 시작, groupId:', groupId);
      
      try {
        console.log('🔍 getGroup invokeTemplate 시도 중...');
        const response = await client.request.invokeTemplate('getGroup', {
          context: { groupId: groupId }
        });
        
        console.log('✅ getGroup invokeTemplate 성공, response:', response);
        
        const group = JSON.parse(response.response);
        console.log('✅ 그룹 파싱 성공:', group);
        
        if (group && group.name) {
          console.log('✅ 그룹 이름 반환:', group.name);
          return group.name;
        } else {
          console.warn('⚠️ 그룹 응답 구조 이상:', group);
          return `Group ${groupId}`;
        }
      } catch (error) {
        console.error('🔴 getGroup invokeTemplate 오류:', error);
        return 'Unassigned';
      }
    },
    
    // 에이전트 정보 처리 (단순화된 버전)
    async processAgentData(ticketData, loggedInUser, client) {
      if (!ticketData || !ticketData.responder_id) {
        return { contact: { name: '미배정' }, id: null };
      }
      
      const agentName = await this.getAgentName(ticketData.responder_id, client);
      
      return {
        contact: { name: agentName },
        id: ticketData.responder_id
      };
    },
    
    // 티켓에서 그룹 정보 추출
    extractGroupFromTicket(ticketData) {
      if (!ticketData) return null;
      
      if (ticketData.group_name) {
        return {
          name: ticketData.group_name,
          id: ticketData.group_id
        };
      }
      
      if (ticketData.group && ticketData.group.name) {
        return {
          name: ticketData.group.name,
          id: ticketData.group_id || ticketData.group.id
        };
      }
      
      if (ticketData.group_id) {
        return {
          name: `그룹 ID: ${ticketData.group_id}`,
          id: ticketData.group_id
        };
      }
      
      return null;
    },


    // 추가 FDK 데이터 가져오기 (그룹/담당자 정보)
    async getAdditionalTicketData(client, groupId, responderId) {
      let groupName = 'CS팀';
      let agentName = '미배정';
      
      try {
        // 그룹 정보가 ID만 있는 경우 추가 조회
        if (groupId && !isNaN(groupId)) {
          console.log('🔍 그룹 정보 추가 조회 시도:', groupId);
          // FDK를 통해 그룹 정보 조회 가능한지 확인
          // (실제 사용 가능 여부는 FDK 버전에 따라 다름)
        }
        
        // 담당자 정보가 ID만 있는 경우 loggedInUser나 contact 정보 활용
        if (responderId && !isNaN(responderId)) {
          console.log('🔍 담당자 정보 추가 조회 시도:', responderId);
          
          // 현재 로그인한 사용자 정보 확인
          const loggedInUser = await client.data.get('loggedInUser');
          console.log('🔍 loggedInUser:', loggedInUser);
          
          if (loggedInUser && loggedInUser.contact && loggedInUser.contact.id === responderId) {
            agentName = loggedInUser.contact.name || agentName;
          }
        }
      } catch (error) {
        console.warn('⚠️ 추가 FDK 데이터 조회 실패:', error);
      }
      
      return { groupName, agentName };
    },

    // 탭 콘텐츠 새로고침 (캐시된 데이터 복원)
    refreshTabContent(tabName) {
      console.log('🔄 refreshTabContent 호출됨:', tabName);
      
      switch(tabName) {
        case 'tickets':
          // 유사 티켓 데이터 복원
          if (App.state.cachedData.similarTickets && App.state.cachedData.similarTickets.length > 0) {
            console.log('📱 유사 티켓 데이터 복원:', App.state.cachedData.similarTickets.length, '건');
            this.renderSimilarTickets(App.state.cachedData.similarTickets);
          } else {
            console.log('📱 유사 티켓 캐시 데이터 없음');
          }
          break;
          
        case 'kb':
          // KB 문서 데이터 복원
          console.log('📚 KB 탭으로 전환 - 캐시 데이터 확인 중...');
          console.log('📚 캐시된 KB 문서 데이터:', App.state.cachedData.kbDocuments);
          if (App.state.cachedData.kbDocuments && App.state.cachedData.kbDocuments.length > 0) {
            console.log('📚 KB 문서 데이터 복원 시작:', App.state.cachedData.kbDocuments.length, '건');
            this.renderKBDocuments(App.state.cachedData.kbDocuments);
            console.log('📚 KB 문서 데이터 복원 완료');
          } else {
            console.log('📚 KB 문서 캐시 데이터 없음 - 빈 상태 표시');
            // 빈 상태도 명시적으로 렌더링
            this.renderKBDocuments([]);
          }
          break;
          
        case 'copilot':
          // Copilot 탭은 별도 처리 불필요 (채팅 메시지는 DOM에 유지됨)
          console.log('🤖 Copilot 탭 활성화');
          break;
          
        default:
          console.log('❓ 알 수 없는 탭:', tabName);
      }
    },

    // 최적화된 헤더 업데이트 (data method 결과 활용)
    async updateTicketHeader(optimizedData, emotionData = null) {
      console.log('🔍 updateTicketHeader 호출됨 - optimizedData:', optimizedData);
      console.log('🔍 updateTicketHeader 호출됨 - emotionData:', emotionData);
      
      const metaRow1 = document.getElementById('metaRow1');
      const metaRow2 = document.getElementById('metaRow2');
      if (!metaRow1 || !metaRow2) return;

      let row1Items = [];
      let row2Items = [];

      // 1줄: 요청자, 감정상태, 우선순위
      
      // 1. 요청자 (FDK contact data method 우선 사용)
      let requester = null;
      if (optimizedData?.contact?.contact?.name) {
        requester = `👤 ${optimizedData.contact.contact.name}`;
      } else if (optimizedData?.contact?.name) {
        requester = `👤 ${optimizedData.contact.name}`;
      } else if (optimizedData?.ticket?.ticket?.requester_name) {
        requester = `👤 ${optimizedData.ticket.ticket.requester_name}`;
      }
      if (requester) {
        row1Items.push(`<span class="meta-item">${requester}</span>`);
      }

      // 2. 백엔드 감정상태 (백엔드에서 제공하지 않으므로 기본값)
      if (emotionData && emotionData.emotion) {
        const emotionMap = {
          'positive': '😊 긍정',
          'negative': '😔 부정', 
          'neutral': '😐 보통',
          'angry': '😡 화남',
          'frustrated': '😤 짜증',
          'satisfied': '😌 만족',
          'confused': '😕 혼란'
        };
        const emotion = emotionMap[emotionData.emotion] || `😐 ${emotionData.emotion}`;
        row1Items.push(`<span class="meta-item">${emotion}</span>`);
      } else {
        row1Items.push('<span class="meta-item">😐 보통</span>');
      }

      // 3. 우선순위 (통합 유틸리티 사용)
      let priority = null;
      if (optimizedData?.ticket?.ticket) {
        const ticket = optimizedData.ticket.ticket;
        console.log('🔍 메인 티켓 우선순위 처리 - 티켓 데이터:', ticket);
        try {
          priority = await TicketLabelUtils.getPriorityLabel(ticket);
          console.log('✅ 메인 티켓 우선순위 결과:', priority);
        } catch (error) {
          console.error('⚠️ 우선순위 조회 실패:', error);
          priority = '📊 우선순위';
        }
      }
      if (priority) {
        row1Items.push(`<span class="meta-item">${priority}</span>`);
      }

      // 2줄: 담당자, 담당그룹, 상태

      // 4. 담당자 (최적화된 agent 데이터 사용)
      let agent = null;
      if (optimizedData?.agent?.contact?.name) {
        agent = `👤 ${optimizedData.agent.contact.name}`;
      } else {
        agent = '👤 Unassigned';
      }
      row2Items.push(`<span class="meta-item">${agent}</span>`);

      // 5. 담당그룹 (FDK group data method 우선 사용)
      let group = null;
      if (optimizedData?.group?.group?.name) {
        group = `👥 ${optimizedData.group.group.name}`;
      } else if (optimizedData?.group?.name) {
        group = `👥 ${optimizedData.group.name}`;
      } else if (optimizedData?.group?.group_name) {
        group = `👥 ${optimizedData.group.group_name}`;
      } else if (optimizedData?.ticket?.ticket?.group_name) {
        group = `👥 ${optimizedData.ticket.ticket.group_name}`;
      } else {
        group = '👥 Unassigned';
      }
      row2Items.push(`<span class="meta-item">${group}</span>`);

      // 6. 진행상태 (통합 유틸리티 사용)
      let status = null;
      if (optimizedData?.ticket?.ticket) {
        const ticket = optimizedData.ticket.ticket;
        console.log('🔍 메인 티켓 상태 처리 - 티켓 데이터:', ticket);
        try {
          status = await TicketLabelUtils.getStatusLabel(ticket);
          console.log('✅ 메인 티켓 상태 결과:', status);
        } catch (error) {
          console.error('⚠️ 상태 조회 실패:', error);
          status = '⚪ 상태';
        }
      }
      if (status) {
        row2Items.push(`<span class="meta-item">${status}</span>`);
      }

      // HTML 업데이트
      metaRow1.innerHTML = row1Items.join('');
      metaRow2.innerHTML = row2Items.join('');
      
      console.log('✅ 최적화된 헤더 업데이트 완료');
    },

    // 요약 업데이트 (개선된 마크다운 렌더링)
    updateSummary(text) {
      const element = document.getElementById('summaryText');
      if (!element) return;

      console.log('🔍 updateSummary 호출됨, text 길이:', text.length);
      console.log('🔍 marked 사용 가능:', typeof marked !== 'undefined' && marked);

      try {
        // 먼저 XML 태그 제거
        const cleanText = text.replace(/<[^>]+>/g, '');
        
        // marked.js 사용 가능한지 확인
        if (typeof marked !== 'undefined' && marked && typeof marked.parse === 'function') {
          console.log('✅ marked.js 사용하여 파싱');
          element.innerHTML = marked.parse(cleanText);
        } else if (typeof marked !== 'undefined' && marked && typeof marked === 'function') {
          // 구버전 marked.js 대응
          console.log('✅ 구버전 marked.js 사용하여 파싱');
          element.innerHTML = marked(cleanText);
        } else {
          console.log('⚠️ marked.js 없음, 수동 변환 사용');
          // marked가 없을 경우 향상된 수동 HTML 변환
          console.log('🔍 원본 텍스트:', text.substring(0, 200) + '...');
          
          const htmlText = cleanText
            // 마크다운 변환
            .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
            .replace(/\*([^*]+)\*/g, '<em>$1</em>')
            .replace(/^### (.+)$/gm, '<h3>$1</h3>')
            .replace(/^## (.+)$/gm, '<h2>$1</h2>')
            .replace(/^# (.+)$/gm, '<h1>$1</h1>')
            .replace(/^- (.+)$/gm, '• $1')
            .replace(/\n\n/g, '<br><br>')
            .replace(/\n/g, '<br>');
          
          console.log('🔍 변환된 HTML:', htmlText.substring(0, 200) + '...');
          element.innerHTML = htmlText;
        }
        
        console.log('✅ 요약 업데이트 완료');
      } catch (error) {
        console.error('❌ 마크다운 파싱 오류:', error);
        // 오류 발생 시 플레인 텍스트로 표시
        element.textContent = text;
      }
    },

    // 프로그레스 바 업데이트
    updateProgressBar(percentage, message, stage, remainingTime) {
      // 진행률 바 업데이트
      const progressBar = document.getElementById('progress-bar');
      const progressPercentage = document.getElementById('progress-percentage');
      const progressTime = document.getElementById('progress-time');
      
      if (progressBar) {
        progressBar.style.width = `${percentage}%`;
        console.log('✅ 프로그레스 바 업데이트:', percentage + '%');
      }
      
      if (progressPercentage) {
        progressPercentage.textContent = `${Math.round(percentage)}%`;
      }
      
      if (progressTime && typeof remainingTime === 'number') {
        const seconds = Math.max(0, Math.round(remainingTime));
        progressTime.textContent = seconds > 0 ? `예상 시간: ${seconds}초` : '곧 완료됩니다';
      }
      
      // 단계별 상태 업데이트
      if (stage) {
        this.updateProgressStage(stage);
      }
      
      // 로딩 메시지 업데이트
      this.updateLoadingMessage(message);
    },

    // 로딩 메시지 업데이트
    updateLoadingMessage(message) {
      const loadingSubtitle = document.querySelector('.loading-subtitle');
      if (loadingSubtitle && message) {
        loadingSubtitle.textContent = message;
        console.log('📝 로딩 메시지 업데이트:', message);
      }
    },

    // 단계별 진행 상황 업데이트
    updateProgressStage(stage) {
      // 모든 단계 요소 가져오기
      const stageItems = document.querySelectorAll('.stage-item');
      
      // 단계 매핑 (백엔드 stage와 HTML data-stage 매핑)
      const stageMapping = {
        'ticket_fetch': 'ticket',
        'analysis': 'summary', 
        'analysis_complete': 'summary',
        'similar_tickets': 'similar',
        'similar_processing': 'similar',
        'kb_documents': 'kb'
      };
      
      const mappedStage = stageMapping[stage] || stage;
      
      stageItems.forEach(item => {
        const stageData = item.getAttribute('data-stage');
        const statusElement = item.querySelector('.stage-status');
        
        if (stageData === mappedStage && statusElement) {
          statusElement.textContent = '✅'; // 완료 표시
          item.classList.add('completed');
          console.log('✅ 단계 완료:', stage, '->', mappedStage);
        } else if (statusElement && !item.classList.contains('completed')) {
          statusElement.textContent = '⏳'; // 대기 표시
        }
      });
    },

    // 유사 티켓 렌더링
    async renderSimilarTickets(tickets) {
      const container = document.getElementById('similarTicketsContainer');
      if (!container) {
        console.error('❌ similarTicketsContainer not found');
        return;
      }
      
      console.log('🔍 Checking tickets data:', tickets);
      
      // Filter out any KB documents/articles that might have been mixed in
      const filteredTickets = tickets.filter(item => {
        // KB documents typically have 'url', 'title', or are marked as KB documents
        // Tickets typically have 'subject' and ticket IDs
        const hasUrl = item.url || item.URL;
        const hasTitle = item.title && !item.subject; // KB docs have title, tickets have subject
        const isKBDoc = item.category || item.type === 'kb_document' || hasUrl;
        const hasKBLabel = item.description && item.description.includes('KB문서');
        
        const isTicket = !hasUrl && !isKBDoc && !hasKBLabel && !hasTitle;
        
        if (!isTicket) {
          console.log('🚫 Filtering out non-ticket item (KB doc/article):', {
            id: item.id,
            hasUrl: !!hasUrl,
            hasTitle: !!hasTitle,
            isKBDoc: !!isKBDoc,
            hasKBLabel: !!hasKBLabel,
            item: item
          });
        }
        
        return isTicket;
      });
      
      console.log('🔍 Filtered tickets count:', filteredTickets.length, 'out of', tickets.length);
      
      if (!filteredTickets || !filteredTickets.length) {
        console.log('⚠️ No similar tickets to render');
        container.innerHTML = `
          <div class="insight-panel">
            <div class="insight-title">🔍 유사 티켓 검색</div>
            <div class="insight-content">유사한 티켓이 없습니다.</div>
          </div>
        `;
        return;
      }

      console.log('✅ Rendering similar tickets:', filteredTickets.length, '건');
      
      // 메타데이터 일괄 조회
      let enrichedTickets = filteredTickets;
      if (App.state.metadataService) {
        try {
          enrichedTickets = await App.state.metadataService.enrichSimilarTickets(filteredTickets);
          console.log('✅ 티켓 메타데이터 인리치 완료');
        } catch (error) {
          console.error('⚠️ 메타데이터 일괄 조회 실패:', error);
        }
      }

      // 인사이트 패널 생성 (실제 데이터 구조에 맞게)
      const avgSimilarity = enrichedTickets.reduce((sum, t) => {
        const similarity = t.similarity_score || t.similarity || t.score || 0;
        const similarityPercent = similarity > 1 ? similarity : similarity * 100;
        return sum + similarityPercent;
      }, 0) / enrichedTickets.length;
      const resolvedCount = enrichedTickets.filter(t => {
        // Freshdesk 상태 ID 기반 체크 (4 = resolved)
        const statusId = t.status_id || t.status;
        const statusLabel = t.ticket_status || '';
        
        // 상태 ID가 4이거나, 상태 라벨에 해결 관련 단어가 포함된 경우
        return statusId === 4 || 
               statusLabel === 'resolved' || 
               statusLabel === '해결완료' || 
               statusLabel.toLowerCase().includes('resolved') ||
               statusLabel.toLowerCase().includes('해결');
      }).length;
      const activeCount = enrichedTickets.length - resolvedCount;
      
      const insightPanel = `
        <div class="insight-panel">
          <div class="insight-title">💡 자동 분석 결과</div>
          <div class="insight-content">
            🎯 평균 유사도: ${Math.round(avgSimilarity)}%<br>
            📊 상태 분포: ${resolvedCount}건 해결완료, ${activeCount}건 진행중<br>
            📋 검색된 티켓: ${enrichedTickets.length}건의 유사 사례 발견
          </div>
        </div>
      `;

      // 레이블 일괄 조회 최적화
      console.log('🔄 레이블 일괄 조회 시작...');
      
      // 1단계: 모든 티켓의 priority와 status 값 수집
      const priorityIds = new Set();
      const statusIds = new Set();
      
      enrichedTickets.forEach(ticket => {
        const priority = ticket.metadata?.priority || ticket.priority;
        const status = ticket.metadata?.status || ticket.status;
        
        if (priority !== undefined && priority !== null) {
          priorityIds.add(parseInt(priority));
        }
        if (status !== undefined && status !== null) {
          statusIds.add(parseInt(status));
        }
      });
      
      console.log(`🔍 수집된 고유 ID - Priority: ${Array.from(priorityIds)}, Status: ${Array.from(statusIds)}`);
      
      // 2단계: 레이블 일괄 조회 및 캐싱
      const labelCache = {
        priority: new Map(),
        status: new Map()
      };
      
      // Priority 레이블 일괄 조회
      for (const priorityId of priorityIds) {
        const priorityText = await TicketLabelUtils.getPriorityLabel({ priority: priorityId });
        labelCache.priority.set(priorityId, priorityText);
      }
      
      // Status 레이블 일괄 조회
      for (const statusId of statusIds) {
        const statusText = await TicketLabelUtils.getStatusLabel({ status: statusId });
        labelCache.status.set(statusId, statusText);
      }
      
      console.log(`✅ 레이블 캐싱 완료 - Priority: ${labelCache.priority.size}개, Status: ${labelCache.status.size}개`);
      
      // 티켓 카드들 생성 (캐시된 레이블 사용)
      const ticketCards = enrichedTickets.map(ticket => {
        console.log('🎫 Processing ticket:', ticket);
        
        // 원본 데이터 구조에 맞게 필드 매핑 (있는 필드만 사용)
        const ticketId = ticket.id;
        const ticketTitle = ticket.subject || '제목 없음';  // subject만 사용
        const similarity = ticket.similarity_score || ticket.score || 0;
        const similarityPercent = similarity > 1 ? similarity : similarity * 100;
        const createdAt = ticket.created_at || ticket.metadata?.created_at || null;
        
        const scoreClass = similarityPercent >= 80 ? 'score-high' : similarityPercent >= 60 ? 'score-medium' : 'score-low';
        const scoreIcon = similarityPercent >= 80 ? '🟢' : similarityPercent >= 60 ? '🟡' : '🔴';
        
        // 원본 필드만 사용 (백엔드 분석 결과 기반)
        const priority = ticket.metadata?.priority || ticket.priority;
        const status = ticket.metadata?.status || ticket.status;
        const responderName = ticket.metadata?.agent_name || ticket.metadata?.responder_id;
        
        // 캐시된 레이블 사용 (API 호출 없음)
        const priorityText = labelCache.priority.get(parseInt(priority)) || '❌ 우선순위 없음';
        const statusLabel = labelCache.status.get(parseInt(status)) || '❌ 상태 없음';
        
        // 일괄 조회된 담당자/요청자 이름 사용
        const agentName = ticket.responderName || responderName || null;
        
        const statusClass = (status === 'resolved' || status === 4) ? 'status-resolved' : 
                           (status === 'in_progress' || status === 2) ? 'status-progress' : 'status-pending';

        return `
          <div class="content-card">
            <div class="card-header">
              <span class="card-id">#${ticketId}</span>
              <span class="similarity-score ${scoreClass}">${scoreIcon} ${Math.round(similarityPercent)}%</span>
            </div>
            <div class="card-body">
              <div class="card-title">
                ${ticketTitle}
              </div>
              <div class="card-meta">
                <div class="meta-left">
                  <span>📅 ${createdAt ? new Date(createdAt).toLocaleDateString('ko-KR') : ''}</span>
                  <span class="status-indicator ${statusClass}">${statusLabel}</span>
                  <span class="priority-indicator">${priorityText}</span>
                  <span>👨‍💼 ${agentName || 'Unassigned'}</span>
                </div>
                ${ticket.relative_time ? `<span>${ticket.relative_time}</span>` : ''}
              </div>
              <div class="card-actions">
                <button class="card-btn primary" onclick="viewSummary('#${ticketId}')">
                  👁️ 요약보기
                </button>
                <button class="card-btn" onclick="viewOriginal('#${ticketId}')">
                  📄 원본보기
                </button>
              </div>
            </div>
          </div>
        `;
      });

      container.innerHTML = insightPanel + ticketCards.join('');
      
      // 탭 카운트 업데이트
      const countElement = document.getElementById('similarTicketsCount');
      if (countElement) {
        countElement.textContent = enrichedTickets.length;
        console.log('✅ 유사 티켓 탭 카운트 업데이트:', enrichedTickets.length);
      } else {
        console.error('❌ similarTicketsCount 엘리먼트를 찾을 수 없음');
      }
    },

    // KB 문서 렌더링
    renderKBDocuments(documents) {
      const container = document.getElementById('kbDocumentsContainer');
      if (!container) {
        return;
      }
      
      if (!documents || !documents.length) {
        container.innerHTML = `
          <div class="insight-panel">
            <div class="insight-title">📚 지식베이스 검색</div>
            <div class="insight-content">관련 문서가 없습니다.</div>
          </div>
        `;
        return;
      }

      // KB 문서 자동 분석 결과 표시
      const kbInsight = document.getElementById('kbInsight');
      const kbInsightContent = document.getElementById('kbInsightContent');
      
      if (kbInsight && kbInsightContent && documents.length > 0) {
        const totalDocs = documents.length;
        const highRelevanceDocs = documents.filter(doc => (doc.score || doc.relevance || 0) >= 0.8).length;
        const mediumRelevanceDocs = documents.filter(doc => {
          const score = doc.score || doc.relevance || 0;
          return score >= 0.6 && score < 0.8;
        }).length;
        
        kbInsightContent.innerHTML = `
          🎯 평균 유사도: ${Math.round(documents.reduce((sum, doc) => sum + (doc.score || doc.relevance || 0), 0) / totalDocs * 100)}%<br>
          📊 상태 분포: ${highRelevanceDocs}건 고관련도, ${mediumRelevanceDocs}건 중관련도<br>
          📚 검색된 문서: ${totalDocs}건의 관련 문서 발견
        `;
        kbInsight.style.display = 'block';
      }

      // KB 문서 카드들 생성
      const docCards = documents.map((doc, index) => {
        console.log('📚 Processing document:', doc);
        
        // 실제 데이터 구조에 맞게 필드 매핑
        const docId = doc.id || 'KB-' + (index + 1);
        const docTitle = doc.title || '제목 없음';
        
        // 백엔드에서 올바른 형식의 URL을 받아서 그대로 사용
        const docUrl = doc.url || '#';
        
        const relevance = doc.score || doc.relevance || 0;
        const createdAt = doc.created_at || doc.createdAt || null;
        
        // 0-1 범위의 소수점을 퍼센트로 변환
        const displayScore = Math.round(relevance * 100);
        const scoreClass = displayScore >= 80 ? 'score-high' : displayScore >= 60 ? 'score-medium' : 'score-low';
        const scoreIcon = displayScore >= 80 ? '🟢' : displayScore >= 60 ? '🟡' : '🔴';

        return `
          <div class="content-card" data-doc-id="${docId}" data-doc-index="${index}">
            <div class="card-header">
              <span class="card-id">${docId}</span>
              <span class="similarity-score ${scoreClass}">${scoreIcon} ${displayScore}%</span>
            </div>
            <div class="card-body">
              <div class="card-title">
                ${docTitle}
              </div>
              <div class="card-meta">
                <div class="meta-left">
                  <span>📅 ${createdAt ? new Date(createdAt).toLocaleDateString('ko-KR') : '날짜 없음'}</span>
                  <span class="status-indicator status-resolved">KB문서</span>
                  <span>📂 ${doc.category || doc.folder_path || doc.path || '일반'}</span>
                </div>
              </div>
              <div class="card-actions">
                <button class="card-btn primary" onclick="window.open('${docUrl}', '_blank')">
                  📄 원본보기
                </button>
                <button class="card-btn" onclick="copyToClipboard('${docUrl}', this)">
                  📋 복사하기
                </button>
              </div>
            </div>
          </div>
        `;
      }).join('');

      container.innerHTML = docCards;
      console.log('✅ KB 문서 HTML 업데이트 완료, 생성된 카드 수:', documents.length);
      console.log('✅ container.innerHTML 길이:', container.innerHTML.length);
      
      // KB 탭 현재 상태 확인
      const kbTabContent = container.closest('.tab-content');
      const kbTabButton = document.querySelector('.tab-button[data-tab="kb"]');
      
      console.log('🔍 KB 탭 컨테이너 상태 검사:');
      console.log('  - kbTabContent 존재:', !!kbTabContent);
      console.log('  - kbTabContent active 클래스:', kbTabContent?.classList.contains('active'));
      console.log('  - kbTabContent display 스타일:', kbTabContent ? window.getComputedStyle(kbTabContent).display : 'N/A');
      console.log('  - kbTabButton 존재:', !!kbTabButton);
      console.log('  - kbTabButton active 클래스:', kbTabButton?.classList.contains('active'));
      
      // 컨테이너의 실제 가시성 확인
      console.log('🔍 container 가시성:');
      console.log('  - container.offsetHeight:', container.offsetHeight);
      console.log('  - container.offsetWidth:', container.offsetWidth);
      console.log('  - container.style.display:', container.style.display);
      
      
      // 탭 카운트 업데이트
      const countElement = document.getElementById('kbDocumentsCount');
      if (countElement) {
        countElement.textContent = documents.length;
        console.log('✅ KB 문서 탭 카운트 업데이트 완료:', documents.length);
      } else {
        console.error('❌ kbDocumentsCount 엘리먼트를 찾을 수 없음');
      }
      
      // KB 문서 클릭 이벤트 (필요시 추가 기능 구현)
      container.querySelectorAll('.content-card').forEach((item) => {
        item.addEventListener('click', () => {
          const docId = item.dataset.docId;
          console.log(`KB 문서 클릭: ${docId}`);
          // 필요시 추가 기능 구현
        });
      });
    },


    // 채팅 메시지 추가 (스트리밍 지원)
    addChatMessage(role, content, messageId, isStreaming = false) {
      const container = document.getElementById('chatResults');
      if (!container) return;

      const messageDiv = document.createElement('div');
      messageDiv.className = `chat-message ${role}`;
      messageDiv.id = `msg-${messageId}`;
      
      const avatar = role === 'user' ? '👤' : '🤖';
      const now = new Date();
      const timeString = now.toLocaleTimeString('ko-KR', { 
        hour: '2-digit', 
        minute: '2-digit' 
      });
      
      const messageTextClass = isStreaming ? 'message-text streaming' : 'message-text';
      
      messageDiv.innerHTML = `
        <div class="message-avatar">${avatar}</div>
        <div class="message-content">
          <div class="${messageTextClass}">${marked ? marked.parse(content) : content}</div>
          <div class="message-time">${timeString}</div>
        </div>
      `;
      // 하단 여백 요소를 찾아서 메시지 앞에 삽입
      const spacer = container.querySelector('div[style*="height: 100px"]');
      if (spacer) {
        container.insertBefore(messageDiv, spacer);
      } else {
        container.appendChild(messageDiv);
      }
      
      // 강제 스크롤 (새 메시지 추가시)
      this.scrollToBottom(true);
      
      // iframe 환경에서 추가 보장
      setTimeout(() => this.scrollToBottom(true), 100);
      setTimeout(() => this.scrollToBottom(true), 300);
    },

    // 채팅 메시지 업데이트 (스트리밍)
    updateChatMessage(messageId, content, isComplete = false) {
      const messageText = document.querySelector(`#msg-${messageId} .message-text`);
      if (messageText) {
        // 내용 업데이트
        if (marked) {
          messageText.innerHTML = marked.parse(content);
        } else {
          messageText.textContent = content;
        }
        
        // 스트리밍 완료시 클래스 제거
        if (isComplete) {
          messageText.classList.remove('streaming');
        }
        
        // 스트리밍 중에는 하단에 있을 때만 스크롤
        const container = document.getElementById('chatResults');
        if (container) {
          const scrollHeight = container.scrollHeight;
          const scrollTop = container.scrollTop;
          const clientHeight = container.clientHeight;
          const isNearBottom = scrollHeight - scrollTop - clientHeight < 150;
          
          // 사용자가 하단 근처에 있을 때만 자동 스크롤
          if (isNearBottom) {
            this.scrollToBottom();
          }
        }
      }
    },

    // 타이핑 인디케이터 표시
    showTypingIndicator() {
      const container = document.getElementById('chatResults');
      if (!container) return;
      
      // 이미 타이핑 인디케이터가 있으면 제거
      this.hideTypingIndicator();
      
      const typingDiv = document.createElement('div');
      typingDiv.className = 'typing-indicator';
      typingDiv.id = 'typingIndicator';
      typingDiv.innerHTML = `
        <div class="message-avatar">🤖</div>
        <div class="typing-dots">
          <div class="typing-dot"></div>
          <div class="typing-dot"></div>
          <div class="typing-dot"></div>
        </div>
      `;
      container.appendChild(typingDiv);
      
      // 타이핑 인디케이터가 보이도록 스크롤
      this.scrollToBottom();
    },

    // 타이핑 인디케이터 제거
    hideTypingIndicator() {
      const typingDiv = document.getElementById('typingIndicator');
      if (typingDiv) {
        typingDiv.remove();
      }
    },

    // 메시지 타이핑 효과
    async typeMessage(messageId, text, speed = 30) {
      const messageText = document.querySelector(`#msg-${messageId} .message-text`);
      if (!messageText) return;
      
      let currentText = '';
      const chars = text.split('');
      
      for (let i = 0; i < chars.length; i++) {
        currentText += chars[i];
        messageText.innerHTML = marked ? marked.parse(currentText) : currentText;
        
        const container = document.getElementById('chatResults');
        if (container) {
          container.scrollTop = container.scrollHeight;
        }
        
        // 다음 문자까지 짧은 대기
        await new Promise(resolve => setTimeout(resolve, speed));
      }
    },

    // iframe 환경에 최적화된 강력한 스크롤 시스템
    scrollToBottom(force = false) {
      const container = document.getElementById('chatResults');
      if (!container) return;
      
      // 스크롤 실행 함수
      const performScroll = () => {
        // 방법 1: 최대값으로 직접 설정
        container.scrollTop = 999999;
        
        // 방법 2: scrollHeight 사용
        container.scrollTop = container.scrollHeight;
        
        // 방법 3: scrollTo 사용
        if (container.scrollTo) {
          container.scrollTo(0, 999999);
        }
        
        // 방법 4: 마지막 요소로 스크롤
        const messages = container.querySelectorAll('.chat-message');
        if (messages.length > 0) {
          const lastMessage = messages[messages.length - 1];
          lastMessage.scrollIntoView({ block: 'end', behavior: 'auto' });
        }
      };
      
      // 즉시 실행
      performScroll();
      
      // 강제 스크롤인 경우 여러 번 실행
      if (force) {
        // 브라우저 렌더링 후 재실행
        requestAnimationFrame(() => {
          performScroll();
          requestAnimationFrame(performScroll);
        });
        
        // 다양한 타이밍으로 재실행
        [0, 10, 50, 100, 200, 500].forEach(delay => {
          setTimeout(performScroll, delay);
        });
      }
    },
    
    // 스크롤 관찰자 초기화 (MutationObserver 사용)
    initScrollObserver() {
      const container = document.getElementById('chatResults');
      if (!container) return;
      
      // 자동 스크롤 여부 추적
      let shouldAutoScroll = true;
      let userScrollTimeout = null;
      
      // 스크롤 이벤트 리스너
      container.addEventListener('scroll', () => {
        const scrollHeight = container.scrollHeight;
        const scrollTop = container.scrollTop;
        const clientHeight = container.clientHeight;
        const distanceFromBottom = scrollHeight - scrollTop - clientHeight;
        const isNearBottom = distanceFromBottom < 100;
        
        // 스크롤 투 바텀 버튼 표시/숨김
        const scrollBtn = document.getElementById('scrollToBottomBtn');
        if (scrollBtn) {
          // 스크롤이 가능한 경우에만 버튼 표시
          if (scrollHeight > clientHeight && !isNearBottom) {
            scrollBtn.style.display = 'flex';
          } else {
            scrollBtn.style.display = 'none';
          }
        }
        
        // 사용자가 위로 스크롤했는지 감지
        if (!isNearBottom) {
          shouldAutoScroll = false;
          clearTimeout(userScrollTimeout);
          
          // 3초 후 자동 스크롤 다시 활성화
          userScrollTimeout = setTimeout(() => {
            if (distanceFromBottom < 200) {
              shouldAutoScroll = true;
            }
          }, 3000);
        } else {
          shouldAutoScroll = true;
        }
      });
      
      // DOM 변경 감지하여 자동 스크롤
      const observer = new MutationObserver((mutations) => {
        // 채팅 컨테이너에 변경사항이 있는지 확인
        let hasRelevantChange = false;
        
        for (const mutation of mutations) {
          // 새 노드가 추가되었거나
          if (mutation.type === 'childList' && mutation.addedNodes.length > 0) {
            hasRelevantChange = true;
            break;
          }
          // 텍스트 내용이 변경되었을 때
          if (mutation.type === 'characterData') {
            hasRelevantChange = true;
            break;
          }
        }
        
        if (!hasRelevantChange) return;
        
        // AI 응답 중이거나 shouldAutoScroll이 true일 때만 자동 스크롤
        const isAIResponding = container.querySelector('.typing-indicator') !== null ||
                             container.querySelector('.message-text.streaming') !== null;
        
        if (shouldAutoScroll || isAIResponding) {
          // 즉시 스크롤
          this.scrollToBottom(true);
        }
      });
      
      // 채팅 컨테이너의 변경사항 관찰
      observer.observe(container, {
        childList: true,
        subtree: true,
        characterData: true,
        attributes: true // 속성 변경도 감지
      });
      
      // 전역 observer 저장 (cleanup용)
      this.scrollObserver = observer;
    },

    // FDK 모달 표시 (원본의 강화된 로직 적용)
    async showFDKModal(ticketId) {
      try {
        console.log(`🎭 티켓 ${ticketId} 모달 열기 시도`);
        
        // FDK 클라이언트 확인
        const client = App.state.client;
        if (!client) {
          console.error('❌ FDK 클라이언트가 준비되지 않음');
          return;
        }
        
        // 티켓 데이터 가져오기 (안전한 FDK API 호출)
        let ticketData = null;
        let ticket = null;
        
        try {
          // 모달 컨텍스트인지 확인
          const context = await client.instance.context();
          if (context.location === 'modal') {
            console.log('🎭 모달 컨텍스트에서는 EventAPI 사용 불가 - 캐시된 데이터 사용');
            
            // 캐시된 티켓 정보 가져오기 (실제 캐시 시스템이 있다면)
            ticket = { id: ticketId, subject: 'Modal Context' };
          } else {
            // 일반 컨텍스트에서는 정상적으로 EventAPI 사용
            ticketData = await client.data.get('ticket');
            ticket = ticketData?.ticket;
            console.log('✅ 티켓 데이터 가져오기 성공');
          }
        } catch (error) {
          console.warn('⚠️ 티켓 데이터 가져오기 실패:', error.message);
          
          // EventAPI 실패 시 폴백: 기본 티켓 정보 사용
          ticket = { 
            id: ticketId || 'unknown', 
            subject: 'API 연결 실패' 
          };
        }
        
        // 현재 로딩 상태에 따른 모달 데이터 구성
        const currentLoadingState = App.state.loadingState;
        const isLoading = currentLoadingState === 'loading';
        const isSuccess = currentLoadingState === 'success';
        const isError = currentLoadingState === 'error';
        const hasData = App.state.dataLoaded && App.state.cachedData;
        
        console.log(`🎭 모달 데이터 준비 - 로딩상태: ${currentLoadingState}, 데이터있음: ${hasData}`);
        
        // 모달 설정 구성 (로딩 상태에 따른 적절한 UI 표시)
        const modalConfig = {
          title: "Copilot Canvas - AI 상담사 지원",
          template: "index.html",
          data: {
            ticketId: ticketId,
            ticket: ticket,
            timestamp: new Date().toISOString(),
            // 성공 상태일 때만 백엔드 호출 금지, 나머지는 허용
            noBackendCall: isSuccess && hasData,
            
            // 로딩 상태 정보 (세분화)
            loadingState: currentLoadingState,
            hasCachedData: hasData,
            
            // 캐시된 데이터 전달 (상태에 따라)
            cachedData: isSuccess && hasData ? App.state.cachedData : { similarTickets: [], kbDocuments: [], summary: '' },
            cachedTicketInfo: App.state.cachedTicketInfo,
            
            // 에러 정보
            loadingError: App.state.loadingError,
            
            // UI 상태 플래그
            isLoading: isLoading,
            isSuccess: isSuccess,
            isError: isError,
            isReady: isSuccess && hasData,
            
            // 새로고침 허용 (에러 시에만)
            allowRefresh: isError,
            
            // 레거시 호환
            loadingStatus: { status: isSuccess ? 'ready' : isLoading ? 'loading' : 'error' },
            globalData: {},
            streamingStatus: { is_streaming: isLoading },
            hasError: isError,
            errorMessage: isError ? App.state.loadingError : null
          },
          size: {
            width: "900px",
            height: "700px"
          },
          noBackdrop: true
        };

        // 🔥 모달을 반드시 열어야 하므로 강화된 에러 처리 (원본 로직)
        let modalOpenSuccess = false;
        let attemptCount = 0;
        const maxAttempts = 3;
        
        while (!modalOpenSuccess && attemptCount < maxAttempts) {
          attemptCount++;
          console.log(`🎭 모달 열기 시도 ${attemptCount}/${maxAttempts}`);
          
          try {
            await client.interface.trigger("showModal", modalConfig);
            console.log('✅ FDK 모달 열기 성공');
            modalOpenSuccess = true;
          } catch (modalError) {
            console.error(`❌ FDK 모달 열기 실패 (시도 ${attemptCount}):`, modalError);
            
            if (attemptCount < maxAttempts) {
              // 재시도 전 잠시 대기
              await new Promise(resolve => setTimeout(resolve, 500));
              console.log('🔄 모달 열기 재시도 준비 중...');
            } else {
              // 최종 시도 - 오류 모드로 강제 표시 (원본 로직)
              console.log('🚨 최종 시도: 오류 모드로 모달 강제 표시');
              
              const emergencyConfig = {
                title: "Copilot Canvas - 연결 오류",
                template: "index.html",
                data: {
                  ticketId: ticketId || 'unknown',
                  ticket: ticket || { id: 'unknown', subject: '연결 오류' },
                  hasCachedData: false,
                  timestamp: new Date().toISOString(),
                  noBackendCall: true,
                  errorMode: true,
                  serverDown: true, // 서버 다운 플래그
                  errorMessage: "서버 연결에 실패했습니다. 새로고침 버튼을 클릭하여 다시 시도해주세요.",
                  // 에러 상태에서도 로딩 상태 정보 전달
                  hasError: true,
                  isLoading: false,
                  isReady: false
                },
                size: {
                  width: "900px", 
                  height: "700px"
                },
                noBackdrop: true
              };
              
              try {
                await client.interface.trigger("showModal", emergencyConfig);
                console.log('✅ 응급 모달 표시 성공');
                modalOpenSuccess = true;
              } catch (emergencyError) {
                console.error('❌ 응급 모달도 실패:', emergencyError);
                // 이 경우에도 오류를 던지지 않고 계속 진행
                modalOpenSuccess = true; // 더 이상 시도하지 않음
              }
            }
          }
        }
        
      } catch (error) {
        console.error('❌ FDK 모달 전체 오류:', error);
        
        // 🚨 어떤 상황에서도 사용자에게 상황을 알려야 함 (원본 로직)
        console.log('🚨 최후의 수단: 사용자에게 오류 상황 알림');
        
        // 최후의 수단으로 DOM에 직접 오류 알림 표시 (원본 로직)
        try {
          const emergencyAlert = document.createElement('div');
          emergencyAlert.style.cssText = `
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: #fee2e2;
            border: 2px solid #f87171;
            color: #991b1b;
            padding: 20px;
            border-radius: 8px;
            z-index: 99999;
            max-width: 400px;
            font-size: 14px;
            box-shadow: 0 8px 24px rgba(0,0,0,0.3);
            text-align: center;
          `;
          
          emergencyAlert.innerHTML = `
            <div style="font-size: 24px; margin-bottom: 12px;">🚨</div>
            <div style="font-weight: 600; margin-bottom: 8px;">AI 지원 기능 오류</div>
            <div style="margin-bottom: 12px;">
              서버 연결에 문제가 있어 AI 기능을 사용할 수 없습니다.
            </div>
            <div style="font-size: 12px; opacity: 0.8; margin-bottom: 16px;">
              오류: ${error.message || '알 수 없는 오류'}
            </div>
            <button onclick="this.parentElement.remove(); location.reload();" 
                    style="background: #dc2626; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer;">
              페이지 새로고침
            </button>
            <button onclick="this.parentElement.remove();" 
                    style="background: transparent; color: #991b1b; border: 1px solid #f87171; padding: 8px 16px; border-radius: 4px; cursor: pointer; margin-left: 8px;">
              닫기
            </button>
          `;
          
          document.body.appendChild(emergencyAlert);
          console.log('🚨 응급 오류 알림 표시됨');
          
          // 10초 후 자동 제거
          setTimeout(() => {
            if (emergencyAlert.parentNode) {
              emergencyAlert.parentNode.removeChild(emergencyAlert);
            }
          }, 10000);
          
        } catch (domError) {
          console.error('❌ 응급 DOM 조작마저 실패:', domError);
          // 정말 마지막 수단
          console.error('🆘 모든 UI 표시 방법 실패 - 콘솔 로그만 남김');
        }
      }
    },

    // 로딩 표시
    showLoading() {
      const loadingOverlay = document.getElementById('loading-overlay');
      if (loadingOverlay) {
        loadingOverlay.style.display = 'flex';
      }
      
      // 프로그레스 바 초기화
      this.initializeProgressBar();
    },

    // 프로그레스 바 초기화
    initializeProgressBar() {
      // 프로그레스 바를 0%로 리셋
      const progressBar = document.getElementById('progress-bar');
      const progressPercentage = document.getElementById('progress-percentage');
      const progressTime = document.getElementById('progress-time');
      
      if (progressBar) {
        progressBar.style.width = '0%';
      }
      
      if (progressPercentage) {
        progressPercentage.textContent = '0%';
      }
      
      if (progressTime) {
        progressTime.textContent = '예상 시간: 20초';
      }
      
      // 모든 단계를 대기 상태로 리셋
      const stageItems = document.querySelectorAll('.stage-item');
      stageItems.forEach(item => {
        const statusElement = item.querySelector('.stage-status');
        if (statusElement) {
          statusElement.textContent = '⏳';
        }
        item.classList.remove('completed');
      });
      
      console.log('🔄 프로그레스 바 초기화 완료');
    },

    // 로딩 숨기기
    hideLoading() {
      const loadingOverlay = document.getElementById('loading-overlay');
      if (loadingOverlay) {
        loadingOverlay.style.display = 'none';
      }
      
      // 로딩 완료 시 탭 네비게이션과 탭 콘텐츠 영역 표시
      const tabNavigation = document.getElementById('tabNavigation');
      const tabContentArea = document.getElementById('tabContentArea');
      
      if (tabNavigation) {
        tabNavigation.style.display = 'block';
        console.log('✅ 탭 네비게이션 표시');
      }
      
      if (tabContentArea) {
        tabContentArea.style.display = 'block';
        console.log('✅ 탭 콘텐츠 영역 표시');
      }
      
    },


    // 에러 표시
    showError(message, isPermantError = false) {
      console.error('앱 에러:', message);
      
      const errorDiv = document.createElement('div');
      errorDiv.className = 'error-toast';
      
      // 새로고침 버튼 추가
      const refreshButton = isPermantError ? '' : '<button onclick="refreshData()" style="margin-left: 10px; padding: 2px 8px; background: #721c24; color: white; border: none; border-radius: 3px; cursor: pointer;">새로고침</button>';
      
      errorDiv.innerHTML = `
        <div style="display: flex; align-items: center; justify-content: space-between;">
          <span>${message}</span>
          ${refreshButton}
        </div>
      `;
      
      errorDiv.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: #f8d7da;
        color: #721c24;
        padding: 10px 15px;
        border-radius: 4px;
        border: 1px solid #f5c6cb;
        z-index: 9999;
        max-width: 400px;
      `;
      
      if (document.body) {
        document.body.appendChild(errorDiv);
        
        setTimeout(() => {
          if (errorDiv && errorDiv.parentNode) {
            errorDiv.parentNode.removeChild(errorDiv);
          }
        }, 5000);
      } else {
        console.error('document.body가 없음:', message);
      }
    },

    // 렌더링 에러 표시 (특정 컨테이너에)
    showRenderError(containerId, message) {
      console.error(`렌더링 에러 (${containerId}):`, message);
      
      const container = document.getElementById(containerId);
      if (!container) {
        console.error(`❌ 컨테이너를 찾을 수 없음: ${containerId}`);
        return;
      }
      
      container.innerHTML = `
        <div class="error-panel">
          <div class="error-icon">❌</div>
          <div class="error-title">렌더링 오류</div>
          <div class="error-message">${message}</div>
          <button class="error-retry-btn" onclick="App.api.refreshData()">다시 시도</button>
        </div>
      `;
      
      // 에러 패널 스타일 적용
      const errorPanel = container.querySelector('.error-panel');
      if (errorPanel) {
        errorPanel.style.cssText = `
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          padding: 40px 20px;
          text-align: center;
          background: #f8f9fa;
          border: 1px solid #dee2e6;
          border-radius: 8px;
          color: #6c757d;
        `;
        
        const errorIcon = errorPanel.querySelector('.error-icon');
        if (errorIcon) {
          errorIcon.style.cssText = `
            font-size: 48px;
            margin-bottom: 16px;
          `;
        }
        
        const errorTitle = errorPanel.querySelector('.error-title');
        if (errorTitle) {
          errorTitle.style.cssText = `
            font-size: 18px;
            font-weight: 600;
            margin-bottom: 8px;
            color: #dc3545;
          `;
        }
        
        const errorMessage = errorPanel.querySelector('.error-message');
        if (errorMessage) {
          errorMessage.style.cssText = `
            font-size: 14px;
            margin-bottom: 20px;
            line-height: 1.5;
          `;
        }
        
        const retryBtn = errorPanel.querySelector('.error-retry-btn');
        if (retryBtn) {
          retryBtn.style.cssText = `
            background: #007bff;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
            transition: background-color 0.2s;
          `;
          retryBtn.onmouseover = () => retryBtn.style.background = '#0056b3';
          retryBtn.onmouseout = () => retryBtn.style.background = '#007bff';
        }
      }
    },
    
    // 스트림 데이터 처리
    async processStreamData(data, currentData) {
      console.log('🔄 Processing stream data:', data.type, data);
      switch(data.type) {
        case 'ticket_info':
          // 백엔드에서 티켓 정보 수신 시 저장
          console.log('🎫 티켓 정보 수신:', data);
          if (data.ticket) {
            App.state.backendTicketData = data.ticket;
            console.log('💾 백엔드 티켓 데이터 저장 완료');
            
            // 티켓 정보를 받았으면 최적화된 FDK 데이터 수집 시작
            this.collectOptimizedTicketData();
          }
          break;
          
        case 'summary':
          // 백엔드에서 전체 요약을 한 번에 보내므로 바로 표시
          currentData.summary = data.content || '';
          App.state.cachedData.summary = currentData.summary; // 캐시에 저장
          
          // 안전한 렌더링 (에러 격리)
          try {
            this.updateSummary(currentData.summary);
            console.log('✅ 요약 업데이트 완료');
          } catch (error) {
            console.error('❌ 요약 업데이트 실패:', error);
            this.showRenderError('summaryContainer', '티켓 요약을 표시하는 중 오류가 발생했습니다.');
          }
          break;
          
        case 'similar_tickets':
          console.log('📦 Similar tickets data received:', data);
          console.log('🔍 Raw similar tickets data structure:', data);
          const rawTickets = data.content || data.similar_tickets || [];
          console.log('🔍 Raw tickets array:', rawTickets);
          
          // Separate tickets from KB documents that may have been mixed in
          const actualTickets = [];
          const mixedInKBDocs = [];
          
          rawTickets.forEach((item, index) => {
            const hasUrl = !!(item.url || item.URL);
            const hasTitle = !!item.title;
            const hasSubject = !!item.subject;
            const hasCategory = !!item.category;
            const hasKBLabel = item.description && item.description.includes('KB문서');
            
            console.log(`🔍 Item ${index}:`, {
              id: item.id,
              hasUrl: hasUrl,
              hasTitle: hasTitle,
              hasSubject: hasSubject,
              hasCategory: hasCategory,
              hasKBLabel: hasKBLabel,
              item: item
            });
            
            // If it has URL or is marked as KB document, it's probably a KB doc
            if (hasUrl || hasKBLabel || (hasTitle && !hasSubject)) {
              console.log(`🚫 Moving item ${index} to KB documents (was in similar_tickets)`);
              mixedInKBDocs.push(item);
            } else {
              actualTickets.push(item);
            }
          });
          
          console.log(`🔄 Data separation complete: ${actualTickets.length} tickets, ${mixedInKBDocs.length} KB docs`);
          
          // Store only actual tickets
          currentData.similarTickets = actualTickets;
          App.state.cachedData.similarTickets = currentData.similarTickets;
          console.log('💾 유사티켓 캐시 저장 완료:', App.state.cachedData.similarTickets.length, '건');
          console.log('🎯 Processing similar tickets:', currentData.similarTickets.length, '건');
          
          // 안전한 렌더링 (에러 격리)
          try {
            await this.renderSimilarTickets(currentData.similarTickets);
            console.log('✅ 유사 티켓 렌더링 완료');
          } catch (error) {
            console.error('❌ 유사 티켓 렌더링 실패:', error);
            this.showRenderError('similarTicketsContainer', '유사 티켓을 표시하는 중 오류가 발생했습니다.');
          }
          
          // If we found KB docs mixed in, add them to KB documents
          if (mixedInKBDocs.length > 0) {
            console.log('📚 Adding mixed-in KB documents to KB documents cache');
            if (!currentData.kbDocuments) currentData.kbDocuments = [];
            if (!App.state.cachedData.kbDocuments) App.state.cachedData.kbDocuments = [];
            
            currentData.kbDocuments = [...(currentData.kbDocuments || []), ...mixedInKBDocs];
            App.state.cachedData.kbDocuments = [...(App.state.cachedData.kbDocuments || []), ...mixedInKBDocs];
            
            console.log('📚 Updated KB documents cache with mixed-in docs:', App.state.cachedData.kbDocuments.length);
            
            // Update KB tab count
            const kbCountElement = document.getElementById('kbDocumentsCount');
            if (kbCountElement) {
              kbCountElement.textContent = App.state.cachedData.kbDocuments.length;
            }
          }
          break;
          
        case 'kb_documents':
          console.log('📦 KB documents data received:', data);
          console.log('📦 Raw KB data content:', data.content);
          currentData.kbDocuments = data.content || data.kb_documents || [];
          App.state.cachedData.kbDocuments = currentData.kbDocuments; // 캐시에 저장
          console.log('💾 KB문서 캐시 저장 완료:', App.state.cachedData.kbDocuments.length, '건');
          console.log('🎯 Processing KB documents:', currentData.kbDocuments.length, '건');
          console.log('🎯 KB 문서 데이터 상세:', currentData.kbDocuments);
          
          // 안전한 렌더링 (에러 격리)
          try {
            this.renderKBDocuments(currentData.kbDocuments);
            console.log('✅ KB 문서 렌더링 완료');
          } catch (error) {
            console.error('❌ KB 문서 렌더링 실패:', error);
            this.showRenderError('kbDocumentsContainer', 'KB 문서를 표시하는 중 오류가 발생했습니다.');
          }
          
          // KB 탭 카운트 업데이트
          const kbCountElement = document.getElementById('kbDocumentsCount');
          if (kbCountElement) {
            kbCountElement.textContent = currentData.kbDocuments.length;
          }
          break;
          
        case 'progress':
          // 진행률 정보 업데이트
          console.log(`진행률: ${data.progress}% - ${data.message}`);
          App.ui.updateProgressBar(data.progress, data.message, data.stage, data.remaining_time);
          break;
          
        case 'emotion_analysis':
          // 감정 분석 결과 처리
          console.log('😊 감정 분석 데이터 수신:', data);
          if (App.state.cachedTicketInfo && App.state.cachedTicketInfo.lastUpdated) {
            // 캐시된 티켓 데이터와 함께 헤더 업데이트
            await this.updateTicketHeader(App.state.cachedTicketInfo, data);
          }
          break;
          
        case 'complete':
          // 완료 시 프로그레스 바를 100%로 설정
          App.ui.updateProgressBar(100, '분석 완료!', null, 0);
          console.log('✅ 모든 데이터 로딩 완료');
          
          // 로딩 상태 업데이트
          App.state.isLoading = false;
          App.state.dataLoaded = true;
          
          // 완료 시점에서 헤더 업데이트 (감정 데이터가 있을 수 있음)
          if (App.state.cachedTicketInfo && App.state.cachedTicketInfo.lastUpdated) {
            // data.emotion_data가 있다면 감정 분석 결과로 사용
            const emotionData = data.emotion_data || data.emotion || null;
            if (emotionData) {
              console.log('😊 완료 시점 감정 데이터 업데이트:', emotionData);
              await this.updateTicketHeader(App.state.cachedTicketInfo, emotionData);
            }
          }
          
          
          return { ...currentData, shouldReturn: true };
          
        case 'error':
          console.error('백엔드 에러:', data.message);
          this.showError(data.message || '알 수 없는 오류');
          break;
      }
      return currentData;
    }
  },

  // 이벤트 핸들러
  events: {
    // 채팅 전송
    async handleSendMessage(queryText) {
      const input = document.getElementById('chatInput');
      const sendButton = document.getElementById('sendButton');
      
      // queryText가 전달되면 사용, 아니면 input에서 가져오기
      const query = queryText || (input ? input.value.trim() : '');
      
      if (!query) return;

      // 입력창 비우기
      if (input) {
        input.value = '';
        input.style.height = 'auto';
      }
      
      // 사용자 메시지 표시
      App.ui.addChatMessage('user', query, Date.now());
      
      // 대화 히스토리에 추가
      App.state.chatHistory.push({ role: 'user', content: query });
      
      // 버튼 비활성화
      if (sendButton) {
        sendButton.disabled = true;
      }

      try {
        await App.api.sendChatQuery(query, App.state.currentMode);
      } catch (error) {
        console.error('채팅 전송 오류:', error);
        App.ui.hideTypingIndicator();
        App.ui.showError('메시지 전송 실패: ' + error.message);
      } finally {
        if (sendButton) {
          sendButton.disabled = false;
        }
      }
    },

    // 모드 전환
    handleModeSwitch(mode) {
      App.state.currentMode = mode;
      
      // UI 업데이트
      document.querySelectorAll('.mode-button').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.mode === mode);
      });
    },

  },

  // 초기화
  async init() {
    console.log('앱 초기화 시작');

    try {
      // FDK 클라이언트 초기화
      const client = await app.initialized();
      App.state.client = client; // 클라이언트 객체 저장
      
      // 메타데이터 서비스 초기화
      App.state.metadataService = new TicketMetadataService(client);
      
      // 티켓 ID 먼저 가져오기
      const basicTicketData = await client.data.get('ticket');
      App.state.ticketId = basicTicketData.ticket.id;
      console.log('티켓 ID 설정:', App.state.ticketId);
      
      // 기본 티켓 데이터를 백엔드 데이터로 설정 (임시)
      App.state.backendTicketData = basicTicketData.ticket;
      
      // FDK 원본 티켓 데이터도 별도 보관
      App.state.originalFDKTicket = basicTicketData.ticket;
      
      // FDK 옵션 미리 가져오기 (캐싱) - 실패 시에도 계속 진행
      console.log('🔄 Pre-fetching FDK options for better performance...');
      try {
        await TicketLabelUtils.getCachedOptions();
        console.log('✅ FDK 옵션 캐싱 성공');
      } catch (error) {
        console.error('⚠️ FDK 옵션 조회 실패:', error);
        // 실패해도 계속 진행
      }
      
      // 기본 헤더 업데이트 (최소한의 정보라도 표시)
      await App.ui.collectOptimizedTicketData();
      
      // 백엔드에서 초기 데이터 로드는 아래에서 await로 처리됨
      
      // 🎯 상단 네비게이션 앱 아이콘 클릭 시 처리 (최적화된 버전)
      client.events.on('app.activated', async () => {
        try {
          console.log('📱 앱이 활성화됨 - 모달 표시 시작');
          
          // FDK context 가져오기 (안전한 호출)
          let ctx = null;
          try {
            ctx = await client.instance.context();
          } catch (contextError) {
            console.warn('⚠️ FDK context 가져오기 실패:', contextError.message);
            ctx = { location: 'unknown' };
          }

          // 상단 네비게이션에서의 동작: 데이터 로드 상태에 따라 처리
          if (ctx.location === 'ticket_top_navigation') {
            let currentTicketId = null;
            
            try {
              const ticketData = await client.data.get('ticket');
              currentTicketId = ticketData?.ticket?.id;
              console.log('✅ 앱 활성화 시 티켓 데이터 가져오기 성공');
            } catch (error) {
              console.warn('⚠️ 앱 활성화 시 티켓 데이터 가져오기 실패:', error.message);
              currentTicketId = App.state.ticketId || 'unknown';
            }

            console.log('📊 상단 네비게이션에서 모달 열기 요청 - 티켓 ID:', currentTicketId);
            console.log('🚫 자동 백엔드 호출 금지 - 캐시 데이터만 사용');
            
            // 캐시 데이터만 사용, 새로고침은 사용자가 직접
            await App.ui.showFDKModal(currentTicketId, true);
          } else {
            console.log('📱 예상치 못한 위치에서의 앱 활성화:', ctx.location);
            // 캐시 데이터만 사용
            await App.ui.showFDKModal(App.state.ticketId, true);
          }
        } catch (err) {
          console.error('❌ app.activated 이벤트 처리 오류:', err);
          App.ui.showError('모달 열기 실패. 새로고침 버튼을 눌러 다시 시도하세요.');
        }
      });
      
      // 초기 데이터 로드 여부 결정
      let isModal = false;
      
      try {
        // FDK 컨텍스트 확인
        const ctx = await client.instance.context();
        isModal = ctx.location === 'modal' && ctx.data?.noBackendCall === true;
        
        console.log('🔍 App.init() 호출됨 - 현재 상태:', {
          isModal,
          context: ctx.location,
          BACKEND_CALLED: App.state.BACKEND_CALLED,
          hasData: !!ctx.data,
          location: window.location.href
        });
      } catch (contextError) {
        console.log('⚠️ 컨텍스트 확인 실패, 일반 페이지로 간주');
        isModal = false;
      }
      
      if (!isModal && !App.state.BACKEND_CALLED) {
        console.log('🔥 페이지 최초 로딩 - 백엔드 호출 실행');
        App.state.isLoading = true;
        App.ui.showLoading();
        
        try {
          await App.api.loadInitialData(App.state.ticketId);
          
          // 데이터가 성공적으로 로드되면 캐시에 저장됨 (loadInitialData 내부에서 처리)
          console.log('✅ 초기 데이터 로드 완료');
          
        } catch (error) {
          console.error('초기 데이터 로드 실패:', error);
          App.ui.hideLoading();
          App.ui.showError('백엔드 서버 연결 실패. 새로고침 버튼을 눌러 다시 시도하세요.');
        }
      } else if (isModal) {
        console.log('🚫 모달 컨텍스트 - 백엔드 호출 건너뛰기');
        
        // 모달에서는 DOMContentLoaded에서 데이터 복원 처리
        App.ui.hideLoading();
        console.log('⏳ 모달 데이터 복원은 DOMContentLoaded에서 처리됨');
      } else {
        console.log('📊 이미 백엔드 호출됨 - 캐시된 데이터 사용');
        App.ui.hideLoading();
      }
      
    } catch (error) {
      console.error('FDK 초기화 오류:', error);
      App.ui.showError('FDK 초기화 실패. 페이지를 새로고침하세요.');
    }

    // 이벤트 리스너 설정
    this.setupEventListeners();
  },

  // 이벤트 리스너 설정
  setupEventListeners() {
    // 채팅 전송 버튼
    const sendButton = document.getElementById('sendButton');
    if (sendButton) {
      sendButton.addEventListener('click', () => App.events.handleSendMessage());
    }

    // 엔터키로 전송
    const chatInput = document.getElementById('chatInput');
    if (chatInput) {
      chatInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          App.events.handleSendMessage();
        }
      });
    }

    // 모드 전환 버튼
    document.querySelectorAll('.mode-button').forEach(btn => {
      btn.addEventListener('click', () => {
        App.events.handleModeSwitch(btn.dataset.mode);
      });
    });

    // 탭 전환 버튼
    document.querySelectorAll('.tab-button').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.preventDefault(); // 기본 동작 방지
        e.stopPropagation(); // 이벤트 버블링 방지
        
        const tabName = btn.dataset.tab;
        
        // 현재 스크롤 위치 저장
        const scrollPosition = document.querySelector('.app-main').scrollTop;
        
        // 모든 탭 강제 비활성화
        document.querySelectorAll('.tab-content').forEach(content => {
          content.classList.remove('active');
          content.style.display = 'none';
        });
        document.querySelectorAll('.tab-button').forEach(button => {
          button.classList.remove('active');
        });
        
        // 선택된 탭만 활성화
        const selectedContent = document.querySelector(`.tab-content[data-tab="${tabName}"]`);
        if (selectedContent) {
          selectedContent.classList.add('active');
          selectedContent.style.display = 'block';
        }
        btn.classList.add('active');
        
        // Copilot 탭일 때만 채팅 입력창 표시
        const chatInput = document.getElementById('chatInputContainer');
        if (chatInput) {
          chatInput.style.display = (tabName === 'copilot') ? 'flex' : 'none';
        }
        
        // 스크롤 위치 복원 (더 안정적)
        setTimeout(() => {
          document.querySelector('.app-main').scrollTop = scrollPosition;
        }, 0);
      });
    });

    // 요약 접기/펼치기 버튼
    const summaryToggleBtn = document.getElementById('summaryToggleBtn');
    if (summaryToggleBtn) {
      summaryToggleBtn.addEventListener('click', () => {
        const section = document.getElementById('summarySection');
        const toggleBtn = document.getElementById('summaryToggleBtn');
        
        if (!section || !toggleBtn) {
          console.error('Summary section or toggle button not found');
          return;
        }
        
        if (section.classList.contains('collapsed')) {
          // 펼치기
          section.classList.remove('collapsed');
          toggleBtn.textContent = '⌃';
          toggleBtn.title = '요약 접기';
        } else {
          // 접기
          section.classList.add('collapsed');
          toggleBtn.textContent = '⌄';
          toggleBtn.title = '요약 펼치기';
        }
      });
    }
  }
};

// 티켓 메타데이터 일괄 조회 서비스
class TicketMetadataService {
  constructor(client) {
    this.client = client;
    this.cache = new Map();
  }

  // 사용자 ID들을 일괄로 조회
  async batchFetchUsers(userIds) {
    if (!userIds || userIds.length === 0) return {};
    
    const uniqueIds = [...new Set(userIds.filter(id => id))];
    const results = {};
    const toFetch = [];
    
    // 캐시 확인
    for (const id of uniqueIds) {
      const cached = this.cache.get(`user_${id}`);
      if (cached) {
        results[id] = cached;
      } else {
        toFetch.push(id);
      }
    }
    
    // 캐시에 없는 것들만 조회
    if (toFetch.length > 0) {
      console.log(`🔍 사용자 ${toFetch.length}명 일괄 조회 시작`);
      
      // 병렬 조회
      const fetchPromises = toFetch.map(async (userId) => {
        try {
          const response = await this.client.request.invokeTemplate('getAgent', {
            context: { agentId: userId }
          });
          const agent = JSON.parse(response.response);
          const name = agent?.contact?.name || null;
          
          if (name) {
            this.cache.set(`user_${userId}`, name);
            results[userId] = name;
          }
        } catch (error) {
          console.error(`⚠️ 사용자 ${userId} 조회 실패:`, error);
        }
      });
      
      await Promise.all(fetchPromises);
    }
    
    return results;
  }
  
  // 그룹 ID들을 일괄로 조회
  async batchFetchGroups(groupIds) {
    if (!groupIds || groupIds.length === 0) return {};
    
    const uniqueIds = [...new Set(groupIds.filter(id => id))];
    const results = {};
    const toFetch = [];
    
    // 캐시 확인
    for (const id of uniqueIds) {
      const cached = this.cache.get(`group_${id}`);
      if (cached) {
        results[id] = cached;
      } else {
        toFetch.push(id);
      }
    }
    
    // 캐시에 없는 것들만 조회
    if (toFetch.length > 0) {
      console.log(`🔍 그룹 ${toFetch.length}개 일괄 조회 시작`);
      
      // 병렬 조회
      const fetchPromises = toFetch.map(async (groupId) => {
        try {
          const response = await this.client.request.invokeTemplate('getGroup', {
            context: { groupId: groupId }
          });
          const group = JSON.parse(response.response);
          const name = group?.name || null;
          
          if (name) {
            this.cache.set(`group_${groupId}`, name);
            results[groupId] = name;
          }
        } catch (error) {
          console.error(`⚠️ 그룹 ${groupId} 조회 실패:`, error);
        }
      });
      
      await Promise.all(fetchPromises);
    }
    
    return results;
  }
  
  // 유사 티켓들의 모든 메타데이터 일괄 조회
  async enrichSimilarTickets(tickets) {
    if (!tickets || tickets.length === 0) return tickets;
    
    console.log(`🚀 유사 티켓 ${tickets.length}건 메타데이터 일괄 조회 시작`);
    
    // 모든 ID 수집
    const userIds = [];
    const groupIds = [];
    
    tickets.forEach(ticket => {
      const responderId = ticket.metadata?.responder_id || ticket.metadata?.agent_id;
      const groupId = ticket.metadata?.group_id;
      
      if (responderId) userIds.push(responderId);
      if (groupId) groupIds.push(groupId);
    });
    
    // 일괄 조회
    const [userNames, groupNames] = await Promise.all([
      this.batchFetchUsers(userIds),
      this.batchFetchGroups(groupIds)
    ]);
    
    console.log(`✅ 메타데이터 조회 완료 - 사용자: ${Object.keys(userNames).length}, 그룹: ${Object.keys(groupNames).length}`);
    
    // 티켓에 메타데이터 추가
    return tickets.map(ticket => {
      const enriched = { ...ticket };
      
      const responderId = ticket.metadata?.responder_id || ticket.metadata?.agent_id;
      const groupId = ticket.metadata?.group_id;
      
      if (responderId && userNames[responderId]) {
        enriched.responderName = userNames[responderId];
      }
      
      if (groupId && groupNames[groupId]) {
        enriched.groupName = groupNames[groupId];
      }
      
      return enriched;
    });
  }
  
  // 캐시 초기화
  clearCache() {
    this.cache.clear();
  }
}

// 메인티켓과 유사티켓용 통합 레이블 조회 (일관성 보장)
const TicketLabelUtils = {
  // 옵션 캐시 유효시간 (5분)
  CACHE_EXPIRY_MS: 5 * 60 * 1000,
  
  // 이모지 매핑 (숫자 ID 기반)
  PRIORITY_EMOJIS: {
    1: '🔵',  // Low
    2: '😐',  // Medium
    3: '🟡',  // High
    4: '🔴'   // Urgent
  },
  
  STATUS_EMOJIS: {
    2: '🟢',  // Open
    3: '🟡',  // Pending
    4: '✅',  // Resolved
    5: '⚪',  // Closed
    6: '🟠',  // Waiting on Customer
    7: '🟣'   // Waiting on Third Party
  },
  
  // 캐시된 옵션 가져오기 (ticket_fields 우선 사용)
  async getCachedOptions() {
    const cache = App.state.fdkOptionsCache;
    const now = Date.now();
    
    // 캐시가 유효한 경우
    if (cache.lastFetched && (now - cache.lastFetched) < this.CACHE_EXPIRY_MS) {
      console.log('✅ Using cached FDK options (age:', Math.round((now - cache.lastFetched) / 1000), 'seconds)');
      return {
        priorityOptions: cache.priorityOptions,
        statusOptions: cache.statusOptions
      };
    }
    
    // 캐시가 없거나 만료된 경우 새로 가져오기
    if (!App.state.client) {
      console.warn('⚠️ FDK client not available for fetching options');
      return null;
    }
    
    try {
      console.log('🔄 Fetching fresh FDK options (trying ticket_fields first)...');
      
      // ticket_fields를 먼저 시도 (더 상세한 레이블 정보 포함)
      let priorityOptions = [];
      let statusOptions = [];
      
      try {
        // API 직접 호출로 한국어 레이블 가져오기
        const [priorityFieldRaw, statusFieldRaw] = await Promise.all([
          App.state.client.request.invokeTemplate('getTicketField', {
            context: { fieldType: 'default_priority' }
          }).catch(() => null),
          App.state.client.request.invokeTemplate('getTicketField', {
            context: { fieldType: 'default_status' }
          }).catch(() => null)
        ]);
        
        console.log('🔍 Priority field API 응답:', priorityFieldRaw);
        console.log('🔍 Status field API 응답:', statusFieldRaw);
        
        // Priority 옵션 파싱
        if (priorityFieldRaw && priorityFieldRaw.response) {
          const priorityField = JSON.parse(priorityFieldRaw.response);
          if (priorityField && priorityField.choices) {
            // choices는 {"Low": 1, "Medium": 2, "High": 3, "Urgent": 4} 형태
            priorityOptions = Object.entries(priorityField.choices).map(([label, id]) => ({
              id: id,
              label: label,
              value: id
            }));
            console.log('✅ Found priority options from API:', priorityOptions);
          }
        }
        
        // Status 옵션 파싱
        if (statusFieldRaw && statusFieldRaw.response) {
          const statusField = JSON.parse(statusFieldRaw.response);
          if (statusField && statusField.choices) {
            // choices는 배열 형태로 각 항목이 [id, "English", "한국어"] 구조
            statusOptions = statusField.choices.map(choice => {
              const [id, english, korean] = choice;
              return {
                id: parseInt(id),
                label: korean || english, // 한국어 우선, 없으면 영어
                english: english,
                korean: korean,
                value: parseInt(id)
              };
            });
            console.log('✅ Found status options from API:', statusOptions);
          }
        }
      } catch (error) {
        console.warn('⚠️ API 직접 호출 실패, ticket_fields로 fallback:', error);
        
        // Fallback: 기존 ticket_fields 방식
        try {
          const ticketFieldsRaw = await App.state.client.data.get('ticket_fields').catch(() => null);
          console.log('🔍 ticket_fields 응답:', ticketFieldsRaw);
          
          if (ticketFieldsRaw && ticketFieldsRaw.ticket_fields) {
            const fields = ticketFieldsRaw.ticket_fields;
            
            // priority 필드 찾기
            const priorityField = fields.find(field => field.name === 'priority' || field.label === 'Priority');
            if (priorityField && priorityField.choices && priorityOptions.length === 0) {
              priorityOptions = priorityField.choices;
              console.log('✅ Found priority options from ticket_fields:', priorityOptions);
            }
            
            // status 필드 찾기  
            const statusField = fields.find(field => field.name === 'status' || field.label === 'Status');
            if (statusField && statusField.choices && statusOptions.length === 0) {
              statusOptions = statusField.choices;
              console.log('✅ Found status options from ticket_fields:', statusOptions);
            }
          }
        } catch (fallbackError) {
          console.warn('⚠️ ticket_fields 조회도 실패:', fallbackError);
        }
      }
      
      // ticket_fields에서 못 가져온 경우 기존 방식 사용
      if (priorityOptions.length === 0 || statusOptions.length === 0) {
        console.log('🔄 Fallback to priority_options and status_options...');
        const [priorityOptionsRaw, statusOptionsRaw] = await Promise.all([
          App.state.client.data.get('priority_options').catch(err => {
            console.error('❌ Priority options fetch error:', err);
            return null;
          }),
          App.state.client.data.get('status_options').catch(err => {
            console.error('❌ Status options fetch error:', err);
            return null;
          })
        ]);
        
        if (priorityOptions.length === 0) {
          priorityOptions = priorityOptionsRaw?.priority_options || priorityOptionsRaw || [];
        }
        if (statusOptions.length === 0) {
          statusOptions = statusOptionsRaw?.status_options || statusOptionsRaw || [];
        }
      }
      
      // 캐시 업데이트
      cache.priorityOptions = priorityOptions;
      cache.statusOptions = statusOptions;
      cache.lastFetched = now;
      
      console.log('✅ FDK options cached successfully');
      console.log('📊 Priority options count:', cache.priorityOptions.length);
      console.log('📊 Status options count:', cache.statusOptions.length);
      
      // 디버그: 실제 옵션 내용 확인
      if (cache.priorityOptions.length > 0) {
        console.log('🔍 Sample priority option:', cache.priorityOptions[0]);
      }
      if (cache.statusOptions.length > 0) {
        console.log('🔍 Sample status option:', cache.statusOptions[0]);
      }
      
      return {
        priorityOptions: cache.priorityOptions,
        statusOptions: cache.statusOptions
      };
    } catch (error) {
      console.error('❌ Failed to fetch FDK options:', error);
      return null;
    }
  },
  
  // 우선순위 레이블 가져오기 (개선된 ID 매칭 방식)
  async getPriorityLabel(ticketData) {
    if (!ticketData || (ticketData.priority === undefined && ticketData.priority !== 0)) {
      return '❌ 우선순위 정보 없음';
    }
    
    const priorityId = parseInt(ticketData.priority);
    const emoji = this.PRIORITY_EMOJIS[priorityId] || '📊';
    
    // 캐시된 옵션 가져오기
    const cachedOptions = await this.getCachedOptions();
    
    if (!cachedOptions || !cachedOptions.priorityOptions || !Array.isArray(cachedOptions.priorityOptions) || cachedOptions.priorityOptions.length === 0) {
      // FDK 조회 실패 시 명확한 에러 메시지
      console.error(`❌ FDK 우선순위 옵션 조회 실패 - Priority ID: ${priorityId}`);
      return `❌ 우선순위 조회 실패 (ID: ${priorityId})`;
    }
    
    console.log(`🔍 우선순위 레이블 조회 - ID: ${priorityId}, 옵션 수: ${cachedOptions.priorityOptions.length}`);
    
    // ID 기반 매칭 (배열 인덱스 대신 실제 ID로 매칭)
    let priorityOption = null;
    let priorityText = null;
    
    // 다양한 형태의 옵션 구조 지원
    for (const option of cachedOptions.priorityOptions) {
      if (typeof option === 'string') {
        // 단순 문자열 배열인 경우 인덱스 기반 매칭 (기존 방식 유지)
        const index = cachedOptions.priorityOptions.indexOf(option);
        if (index === priorityId - 1) {  // Freshdesk priority는 1부터 시작
          priorityOption = option;
          priorityText = option;
          break;
        }
      } else if (option && typeof option === 'object') {
        // 객체 형태인 경우 ID 또는 value로 매칭
        if (option.id === priorityId || option.value === priorityId) {
          priorityOption = option;
          priorityText = option.label || option.name || option.korean || option.english || option.toString();
          break;
        }
      }
    }
    
    // 매칭 실패 시 명확한 에러 메시지
    if (!priorityOption || !priorityText) {
      console.error(`❌ 우선순위 ID ${priorityId}에 해당하는 옵션을 찾을 수 없음`);
      console.error('🔍 사용 가능한 옵션:', cachedOptions.priorityOptions);
      return `❌ 우선순위 매칭 실패 (ID: ${priorityId})`;
    }
    
    console.log(`✅ 우선순위 레이블 찾음 - ID: ${priorityId} → ${priorityText}`);
    return `${emoji} ${priorityText}`;
  },

  // 상태 레이블 가져오기 (개선된 ID 매칭 방식)
  async getStatusLabel(ticketData) {
    if (!ticketData || (ticketData.status === undefined && ticketData.status !== 0)) {
      return '❌ 상태 정보 없음';
    }
    
    const statusId = parseInt(ticketData.status);
    const emoji = this.STATUS_EMOJIS[statusId] || '⚪';
    
    // 캐시된 옵션 가져오기
    const cachedOptions = await this.getCachedOptions();
    
    if (!cachedOptions || !cachedOptions.statusOptions || !Array.isArray(cachedOptions.statusOptions) || cachedOptions.statusOptions.length === 0) {
      // FDK 조회 실패 시 명확한 에러 메시지
      console.error(`❌ FDK 상태 옵션 조회 실패 - Status ID: ${statusId}`);
      return `❌ 상태 조회 실패 (ID: ${statusId})`;
    }
    
    console.log(`🔍 상태 레이블 조회 - ID: ${statusId}, 옵션 수: ${cachedOptions.statusOptions.length}`);
    
    // ID 기반 매칭 (배열 인덱스 대신 실제 ID로 매칭)
    let statusOption = null;
    let statusText = null;
    
    // 다양한 형태의 옵션 구조 지원
    for (const option of cachedOptions.statusOptions) {
      if (typeof option === 'string') {
        // 단순 문자열 배열인 경우 인덱스 기반 매칭 (기존 방식 유지)
        const index = cachedOptions.statusOptions.indexOf(option);
        if (index === statusId - 2) {  // Freshdesk status는 보통 2부터 시작
          statusOption = option;
          statusText = option;
          break;
        }
      } else if (option && typeof option === 'object') {
        // 객체 형태인 경우 ID 또는 value로 매칭
        if (option.id === statusId || option.value === statusId) {
          statusOption = option;
          // 한국어 우선, 없으면 영어, 최후에 다른 필드들
          statusText = option.korean || option.label || option.name || option.english || option.toString();
          break;
        }
      } else if (Array.isArray(option)) {
        // [id, "English", "한국어"] 배열 형태인 경우
        const [id, english, korean] = option;
        if (parseInt(id) === statusId) {
          statusOption = option;
          statusText = korean || english || id.toString();
          break;
        }
      }
    }
    
    // 매칭 실패 시 명확한 에러 메시지
    if (!statusOption || !statusText) {
      console.error(`❌ 상태 ID ${statusId}에 해당하는 옵션을 찾을 수 없음`);
      console.error('🔍 사용 가능한 옵션:', cachedOptions.statusOptions);
      return `❌ 상태 매칭 실패 (ID: ${statusId})`;
    }
    
    console.log(`✅ 상태 레이블 찾음 - ID: ${statusId} → ${statusText}`);
    return `${emoji} ${statusText}`;
  },

  // Agent 이름 가져오기 (에러 처리 개선)
  async getAgentName(agentId) {
    if (!App.state.client) {
      console.error('❌ FDK 클라이언트가 준비되지 않음');
      return '❌ FDK 클라이언트 없음';
    }
    
    if (!agentId) {
      return '❌ 담당자 정보 없음';
    }
    
    try {
      // 메인티켓에서 사용하는 방식과 동일
      const agentName = await App.ui.getAgentName(agentId, App.state.client);
      
      if (!agentName) {
        console.error(`❌ 담당자 ID ${agentId}에 대한 이름 조회 실패`);
        return `❌ 담당자 조회 실패 (ID: ${agentId})`;
      }
      
      return agentName;
    } catch (error) {
      console.error(`❌ 담당자 이름 조회 중 오류 - ID: ${agentId}`, error);
      return `❌ 담당자 조회 오류 (ID: ${agentId})`;
    }
  },

  async getGroupName(groupId) {
    if (!App.state.client) {
      console.error('❌ FDK 클라이언트가 준비되지 않음');
      return '❌ FDK 클라이언트 없음';
    }
    
    if (!groupId) {
      return '❌ 그룹 정보 없음';
    }
    
    try {
      // 메인티켓에서 사용하는 방식과 동일
      const groupName = await App.ui.getGroupName(groupId, App.state.client);
      
      if (!groupName) {
        console.error(`❌ 그룹 ID ${groupId}에 대한 이름 조회 실패`);
        return `❌ 그룹 조회 실패 (ID: ${groupId})`;
      }
      
      return groupName;
    } catch (error) {
      console.error(`❌ 그룹 이름 조회 중 오류 - ID: ${groupId}`, error);
      return `❌ 그룹 조회 오류 (ID: ${groupId})`;
    }
  }
};

// 하위 호환성을 위한 별칭
const SimilarTicketUtils = TicketLabelUtils;

// 전역으로 노출 (디버깅용 + FDK 이벤트 처리)
window.App = App;

// 전역 함수들 (HTML에서 호출용)
window.showFDKModal = async function(ticketId) {
  console.log('📡 Top bar navigation에서 모달 열기 요청');
  console.log('📊 현재 데이터 로드 상태:', {
    dataLoaded: App.state.dataLoaded,
    BACKEND_CALLED: App.state.BACKEND_CALLED
  });
  
  if (App && App.ui && App.ui.showFDKModal) {
    // 캐시 데이터만 사용
    await App.ui.showFDKModal(ticketId || App.state.ticketId, true);
  } else {
    console.error('❌ App.ui.showFDKModal 함수가 준비되지 않음');
  }
};

// 새로고침 버튼용 전역 함수
window.refreshData = async function() {
  console.log('🔄 HTML 새로고침 버튼 클릭');
  
  if (App && App.api && App.api.refreshData) {
    await App.api.refreshData();
  } else {
    console.error('❌ App.api.refreshData 함수가 준비되지 않음');
  }
};

// DOM 로드 완료 시 앱 초기화
document.addEventListener('DOMContentLoaded', async () => {
  // 채팅 입력창만 숨기기
  const chatInput = document.getElementById('chatInputContainer');
  if (chatInput) {
    chatInput.style.display = 'none';
  }
  
  // 스크롤 관찰자 초기화
  App.ui.initScrollObserver();
  
  // iframe 환경 감지 및 특별 처리
  if (window.self !== window.top) {
    console.log('🌐 iframe 환경 감지 - 스크롤 최적화 활성화');
    
    // iframe에서 focus 이벤트와 함께 스크롤 처리
    window.addEventListener('focus', () => {
      setTimeout(() => {
        const container = document.getElementById('chatResults');
        if (container) {
          App.ui.scrollToBottom(true);
        }
      }, 100);
    });
    
    // visibility change 이벤트 처리
    document.addEventListener('visibilitychange', () => {
      if (!document.hidden) {
        const container = document.getElementById('chatResults');
        if (container) {
          App.ui.scrollToBottom(true);
        }
      }
    });
  }
  
  // FDK가 로드되었는지 확인
  if (typeof app !== 'undefined') {
    try {
      // FDK 초기화 및 컨텍스트 확인
      const client = await app.initialized();
      const context = await client.instance.context();
      
      console.log('🔍 FDK 컨텍스트:', context);
      
      // 모달 컨텍스트에서 실행 중인지 확인
      if (context.location === 'modal' && context.data) {
        console.log('🎭 모달 컨텍스트 감지 - 전달된 데이터:', context.data);
        
        // 모달로 전달된 데이터 처리
        const modalData = context.data;
        
        // 티켓 ID 복원
        if (modalData.ticketId) {
          App.state.ticketId = modalData.ticketId;
          console.log('✅ 모달에서 티켓 ID 복원:', App.state.ticketId);
        }
        
        if (modalData.noBackendCall === true) {
          console.log('🚫 모달에서 noBackendCall 플래그 감지 - 백엔드 호출 생략');
          
          // 전달받은 로딩 상태 정보 복원
          App.state.loadingState = modalData.loadingState || 'idle';
          App.state.loadingError = modalData.loadingError || null;
          App.state.dataLoaded = modalData.hasCachedData || false;
          App.state.BACKEND_CALLED = true;
          
          console.log(`🎭 모달 상태 복원 - loadingState: ${App.state.loadingState}, dataLoaded: ${App.state.dataLoaded}`);
          
          // 캐시된 데이터 복원 또는 상태에 따른 메시지 설정
          if (modalData.cachedData && App.state.loadingState === 'success') {
            App.state.cachedData = modalData.cachedData;
            console.log('✅ 모달 데이터에서 캐시 복원:', App.state.cachedData);
          } else {
            // 로딩 상태에 따른 메시지 설정
            let statusMessage = '';
            
            switch (App.state.loadingState) {
              case 'loading':
                statusMessage = '🤖 **AI 분석 진행 중...**\n\n현재 티켓 데이터를 분석하고 있습니다.\n잠시만 기다려주세요.\n\n📊 분석 중인 항목:\n- 티켓 내용 분석\n- 유사 티켓 검색\n- 관련 지식베이스 검색';
                break;
              case 'error':
                statusMessage = `❌ **데이터 로딩 실패**\n\n${App.state.loadingError || '백엔드 서버 연결에 실패했습니다.'}\n\n🔄 상단의 새로고침 버튼을 클릭하여 다시 시도하세요.`;
                break;
              case 'idle':
              default:
                statusMessage = '📌 **AI 분석 준비 완료**\n\n상단의 새로고침 버튼(🔄)을 클릭하여 티켓 분석을 시작하세요.\n\n분석이 완료되면:\n- 티켓 요약\n- 유사한 해결된 티켓\n- 관련 지식베이스 문서\n\n위 정보들을 확인하실 수 있습니다.';
                break;
            }
            
            App.state.cachedData = {
              summary: statusMessage,
              similarTickets: [],
              kbDocuments: []
            };
            console.log(`🎭 모달 상태별 메시지 설정 (${App.state.loadingState}):`, statusMessage.substring(0, 50) + '...');
          }
          
          if (modalData.cachedTicketInfo) {
            App.state.cachedTicketInfo = modalData.cachedTicketInfo;
            console.log('✅ 티켓 정보 복원');
          }
          
          // 기본 UI 설정 - 모달에서는 App.init()이 호출되지 않으므로 수동으로 호출
          App.setupEventListeners();
          
          // 로딩 상태에 따른 UI 처리
          setTimeout(async () => {
            // 로딩 중인 경우 로딩 모달 표시
            if (App.state.loadingState === 'loading') {
              App.ui.showLoading();
              App.ui.updateLoadingMessage('AI 분석이 진행 중입니다...');
            } else {
              App.ui.hideLoading();
            }
            
            // 요약 항상 표시 (상태 메시지 포함)
            if (App.state.cachedData.summary) {
              App.ui.updateSummary(App.state.cachedData.summary);
            }
            
            // 성공 상태일 때만 실제 데이터 렌더링
            if (App.state.loadingState === 'success') {
              // 유사 티켓 복원
              if (App.state.cachedData.similarTickets && App.state.cachedData.similarTickets.length > 0) {
                App.ui.renderSimilarTickets(App.state.cachedData.similarTickets);
              }
              
              // KB 문서 복원
              if (App.state.cachedData.kbDocuments && App.state.cachedData.kbDocuments.length > 0) {
                App.ui.renderKBDocuments(App.state.cachedData.kbDocuments);
              }
              
              // 헤더 정보 복원
              if (App.state.cachedTicketInfo && App.state.cachedTicketInfo.lastUpdated) {
                await App.ui.updateTicketHeader(App.state.cachedTicketInfo);
              }
            }
            
            console.log(`🎭 모달 UI 복원 완료 - 상태: ${App.state.loadingState}`);
            
            console.log('✅ 모달 캐시된 데이터 복원 완료');
          }, 200);
          
          // 탭 네비게이션 표시
          const tabNavigation = document.getElementById('tabNavigation');
          const tabContentArea = document.getElementById('tabContentArea');
          
          if (tabNavigation) {
            tabNavigation.style.display = 'block';
          }
          
          if (tabContentArea) {
            tabContentArea.style.display = 'block';
          }
          
          return; // 모달에서는 App.init()을 호출하지 않음
        }
      }
      
      // 일반 페이지 로드 - App.init() 호출
      App.init().catch(error => {
        console.error('앱 초기화 중 오류:', error);
        App.ui.showError('앱 초기화 실패. 페이지를 새로고침하세요.');
      });
      
    } catch (error) {
      console.error('FDK 초기화 중 오류:', error);
      // 일반 페이지로 간주하고 App.init() 호출
      App.init().catch(initError => {
        console.error('앱 초기화 중 오류:', initError);
        App.ui.showError('앱 초기화 실패. 페이지를 새로고침하세요.');
      });
    }
  } else {
    console.error('FDK가 로드되지 않았습니다.');
    App.ui.showError('FDK 로드 실패. 페이지를 새로고침하세요.');
  }
});

// ========== 유사 티켓 상세 보기 함수들 ==========

// 티켓 요약 보기
async function viewSummary(ticketId) {
  console.log('🔍 요약 보기 클릭:', ticketId);
  
  // 티켓 ID에서 # 제거
  const cleanTicketId = ticketId.replace('#', '');
  
  // 캐시된 유사 티켓 데이터에서 해당 티켓 찾기
  const tickets = App.state.cachedData.similarTickets;
  const ticketIndex = tickets.findIndex(ticket => ticket.id == cleanTicketId);
  
  if (ticketIndex === -1) {
    console.error('티켓을 찾을 수 없습니다:', cleanTicketId);
    return;
  }
  
  await showTicketDetail(ticketIndex);
}

// 티켓 원본 보기
function viewOriginal(ticketId) {
  console.log('📄 원본 보기 클릭:', ticketId);
  
  // 티켓 ID에서 # 제거
  const cleanTicketId = ticketId.replace('#', '');
  
  // Freshdesk 티켓 URL 생성
  const ticketUrl = `https://${App.config.domain}/a/tickets/${cleanTicketId}`;
  
  // 새 탭에서 티켓 열기
  window.open(ticketUrl, '_blank');
}

// 티켓 상세 정보 표시
async function showTicketDetail(ticketIndex) {
  const tickets = App.state.cachedData.similarTickets;
  
  if (ticketIndex < 0 || ticketIndex >= tickets.length) {
    console.error('잘못된 티켓 인덱스:', ticketIndex);
    return;
  }
  
  const ticket = tickets[ticketIndex];
  console.log('🎫 티켓 상세 표시:', ticket);
  
  // 상태 업데이트
  App.state.ticketDetailView.isDetailView = true;
  App.state.ticketDetailView.currentTicketIndex = ticketIndex;
  App.state.ticketDetailView.currentTicketData = ticket;
  
  // 상세 화면 렌더링
  await renderTicketDetail(ticket, ticketIndex, tickets.length);
}

// 목록으로 돌아가기
function goBackToList() {
  console.log('🔙 목록으로 돌아가기');
  
  // 상태 리셋
  App.state.ticketDetailView.isDetailView = false;
  App.state.ticketDetailView.currentTicketIndex = -1;
  App.state.ticketDetailView.currentTicketData = null;
  
  // 목록 화면 복원
  const container = document.getElementById('similarTicketsContainer');
  const detailContainer = document.getElementById('ticketDetailContainer');
  
  if (container && detailContainer) {
    container.style.display = 'block';
    detailContainer.style.display = 'none';
  }
}

// 이전/다음 티켓으로 이동
async function navigateToTicket(direction) {
  const currentIndex = App.state.ticketDetailView.currentTicketIndex;
  const tickets = App.state.cachedData.similarTickets;
  
  if (currentIndex === -1 || !tickets.length) {
    return;
  }
  
  let newIndex;
  if (direction === 'prev') {
    newIndex = currentIndex > 0 ? currentIndex - 1 : tickets.length - 1;
  } else if (direction === 'next') {
    newIndex = currentIndex < tickets.length - 1 ? currentIndex + 1 : 0;
  }
  
  console.log('🔄 티켓 이동:', direction, currentIndex, '->', newIndex);
  await showTicketDetail(newIndex);
}

// 티켓 상세 화면 렌더링
async function renderTicketDetail(ticket, currentIndex, totalCount) {
  const container = document.getElementById('similarTicketsContainer');
  let detailContainer = document.getElementById('ticketDetailContainer');
  
  // 상세 컨테이너가 없으면 생성
  if (!detailContainer) {
    detailContainer = document.createElement('div');
    detailContainer.id = 'ticketDetailContainer';
    container.parentNode.appendChild(detailContainer);
  }
  
  // 기존 목록 숨기기
  container.style.display = 'none';
  detailContainer.style.display = 'block';
  
  // 티켓 정보 추출 (원본 필드만 사용)
  const ticketId = ticket.id || 'N/A';
  const ticketTitle = ticket.subject || '제목 없음';
  const ticketContent = ticket.content || '내용 없음';
  const similarity = ticket.score || ticket.similarity_score || 0;
  const similarityPercent = similarity > 1 ? similarity : similarity * 100;
  const createdAt = ticket.metadata?.created_at || ticket.created_at || null;
  const status = ticket.metadata?.status || ticket.status;
  const priority = ticket.metadata?.priority || ticket.priority;
  const responderName = ticket.metadata?.agent_name || ticket.metadata?.responder_id;
  
  // 레이블 조회 (원본 숫자값 기반)
  const ticketForLabels = {
    priority: priority,
    status: status
  };
  
  const priorityText = await TicketLabelUtils.getPriorityLabel(ticketForLabels);
  const statusLabel = await TicketLabelUtils.getStatusLabel(ticketForLabels);
  const agentId = ticket.metadata?.responder_id || ticket.metadata?.agent_id;
  let agentName = null;
  if (agentId && App.state.client) {
    try {
      agentName = await TicketLabelUtils.getAgentName(agentId);
    } catch (error) {
      console.error('Agent 이름 조회 실패:', error);
    }
  }
  
  // 첨부파일 정보
  const hasAttachments = ticket.has_attachments || false;
  const attachmentCount = ticket.attachment_count || 0;
  const attachments = ticket.metadata?.relevant_attachments || [];
  
  // 상세 화면 HTML 생성
  const detailHTML = `
    <div class="ticket-detail-view">
      <div class="detail-header">
        <button class="back-btn" onclick="goBackToList()">
          ← 뒤로가기
        </button>
        <div class="detail-navigation">
          <button class="nav-btn" onclick="navigateToTicket('prev')" ${totalCount <= 1 ? 'disabled' : ''}>
            ◀ 이전
          </button>
          <span class="nav-info">${currentIndex + 1} / ${totalCount}</span>
          <button class="nav-btn" onclick="navigateToTicket('next')" ${totalCount <= 1 ? 'disabled' : ''}>
            다음 ▶
          </button>
        </div>
      </div>
      
      <div class="detail-content">
        <div class="detail-meta">
          <div class="meta-header">
            <h2 class="detail-title">#${ticketId} ${ticketTitle}</h2>
            <div class="similarity-badge ${similarityPercent >= 80 ? 'high' : similarityPercent >= 60 ? 'medium' : 'low'}">
              ${similarityPercent >= 80 ? '🟢' : similarityPercent >= 60 ? '🟡' : '🔴'} ${Math.round(similarityPercent)}% 유사
            </div>
          </div>
          
          <div class="meta-grid">
            <div class="meta-item">
              <span class="meta-label">📅 생성일:</span>
              <span class="meta-value">${createdAt ? new Date(createdAt).toLocaleDateString('ko-KR') : '정보 없음'}</span>
            </div>
            <div class="meta-item">
              <span class="meta-label">📊 상태:</span>
              <span class="meta-value status-${status}">${statusLabel}</span>
            </div>
            <div class="meta-item">
              <span class="meta-label">🔥 우선순위:</span>
              <span class="meta-value">${priorityText}</span>
            </div>
            <div class="meta-item">
              <span class="meta-label">🎯 담당자:</span>
              <span class="meta-value">${agentName || responderName}</span>
            </div>
            ${hasAttachments ? `<div class="meta-item">
              <span class="meta-label">📎 첨부파일:</span>
              <span class="meta-value">${attachmentCount}개</span>
            </div>` : ''}
          </div>
        </div>
        
        <div class="detail-summary">
          <h3>📝 티켓 요약</h3>
          <div class="summary-content">
            ${markdownToHtml(ticketContent)}
          </div>
        </div>
        
        ${attachments.length > 0 ? `
        <div class="detail-attachments">
          <h3>📎 첨부파일</h3>
          <div class="attachments-list">
            ${attachments.map(attachment => `
              <div class="attachment-item">
                <span class="attachment-icon">📄</span>
                <span class="attachment-name">${attachment.name || '파일명 없음'}</span>
                <span class="attachment-size">${attachment.size ? `(${Math.round(attachment.size/1024)}KB)` : ''}</span>
                ${attachment.url ? `<a href="${attachment.url}" target="_blank" class="attachment-download">다운로드</a>` : ''}
              </div>
            `).join('')}
          </div>
        </div>
        ` : ''}
        
        <div class="detail-actions">
          <button class="action-btn primary" onclick="viewOriginal('#${ticketId}')">
            📄 원본 티켓 보기
          </button>
          <button class="action-btn" onclick="goBackToList()">
            📋 목록으로 돌아가기
          </button>
        </div>
      </div>
    </div>
  `;
  
  detailContainer.innerHTML = detailHTML;
}

// 마크다운 to HTML 변환 함수 (updateSummary 로직 재사용)
function markdownToHtml(text) {
  if (!text) return '';
  
  try {
    // XML 태그 제거
    const cleanText = text.replace(/<[^>]+>/g, '');
    
    // marked.js 사용 가능한지 확인
    if (typeof marked !== 'undefined' && marked && typeof marked.parse === 'function') {
      return marked.parse(cleanText);
    } else if (typeof marked !== 'undefined' && marked && typeof marked === 'function') {
      // 구버전 marked.js 대응
      return marked(cleanText);
    } else {
      // marked가 없을 경우 수동 HTML 변환
      const htmlText = cleanText
        // 마크다운 변환
        .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
        .replace(/\*([^*]+)\*/g, '<em>$1</em>')
        .replace(/^### (.+)$/gm, '<h3>$1</h3>')
        .replace(/^## (.+)$/gm, '<h2>$1</h2>')
        .replace(/^# (.+)$/gm, '<h1>$1</h1>')
        .replace(/^- (.+)$/gm, '• $1')
        .replace(/\n\n/g, '<br><br>')
        .replace(/\n/g, '<br>');
      
      return htmlText;
    }
  } catch (error) {
    console.error('❌ 마크다운 파싱 오류:', error);
    return text; // 오류 발생 시 원본 텍스트 반환
  }
}

// 키보드 이벤트 리스너
document.addEventListener('keydown', function(event) {
  // 상세 보기 모드일 때만 키보드 단축키 활성화
  if (!App.state.ticketDetailView.isDetailView) {
    return;
  }
  
  switch(event.key) {
    case 'Escape':
      goBackToList();
      break;
    case 'ArrowLeft':
      navigateToTicket('prev');
      break;
    case 'ArrowRight':
      navigateToTicket('next');
      break;
  }
});