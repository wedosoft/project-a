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
    isLoading: false,
    BACKEND_CALLED: false, // 백엔드 호출 여부 - 한 번 호출되면 절대 다시 호출 안함
    dataLoaded: false, // 초기 데이터 로드 완료 여부
    currentMode: 'smart', // 'smart' or 'free'
    client: null, // FDK 클라이언트 객체
    
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
    originalFDKTicket: null
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
      
      App.state.BACKEND_CALLED = true;
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
                  App.state.dataLoaded = true;
                  App.ui.hideLoading();
                  return { summary, similarTickets, kbDocuments };
                }
                
                try {
                  const data = JSON.parse(dataStr);
                  const result = await App.ui.processStreamData(data, { summary, similarTickets, kbDocuments });
                  if (result) {
                    summary = result.summary || summary;
                    similarTickets = result.similarTickets || similarTickets;
                    kbDocuments = result.kbDocuments || kbDocuments;
                    
                    if (result.shouldReturn) {
                      App.state.dataLoaded = true;
                      App.ui.hideLoading();
                      return { summary, similarTickets, kbDocuments };
                    }
                  }
                } catch (parseError) {
                  // JSON 파싱 실패는 무시
                }
              }
            }
          }
        }
        
        App.state.dataLoaded = true;
        App.ui.hideLoading();
        return { summary, similarTickets, kbDocuments };
        
      } catch (error) {
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
        
        // UI 업데이트
        if (data.summary) {
          App.ui.updateSummary(data.summary);
        }
        if (data.similarTickets) {
          App.ui.renderSimilarTickets(data.similarTickets);
        }
        if (data.kbDocuments) {
          App.ui.renderKBDocuments(data.kbDocuments);
        }
        
        console.log('✅ 새로고침 완료');
        
      } catch (error) {
        console.error('새로고침 실패:', error);
        App.ui.showError('새로고침 실패. 다시 시도해주세요.');
      }
    },

    // 채팅 쿼리 전송
    async sendChatQuery(query, mode = 'smart') {
      const response = await fetch(`${App.config.baseURL}/query`, {
        method: 'POST',
        headers: this.getHeaders(),
        body: JSON.stringify({
          query: query,
          agent_mode: mode === 'smart',
          stream_response: true,
          ticket_id: App.state.ticketId
        })
      });

      if (!response.ok) {
        throw new Error(`API 오류: ${response.status}`);
      }

      // 스트리밍 응답 처리
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let messageId = Date.now();

      // 메시지 컨테이너 생성
      App.ui.addChatMessage('assistant', '', messageId);

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
              if (event.type === 'content' && event.content) {
                App.ui.updateChatMessage(messageId, event.content);
              }
            } catch (e) {
              // JSON 파싱 실패 시 무시
            }
          }
        }
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
        
        // 3. 상태 레이블 가져오기 (FDK 전용 조회)
        console.log('🚨 [CRITICAL] 상태 레이블 가져오기 시작 - 함수 호출 시점:', new Date().toISOString());
        let statusLabel = '❌ 상태 없음';
        if (mergedTicketData && mergedTicketData.status !== undefined && mergedTicketData.status !== null) {
          const statusId = parseInt(mergedTicketData.status);
          console.log('🚨 mergedTicketData.status:', mergedTicketData.status);
          console.log('🚨 statusId 변환 결과:', statusId);
          
          try {
            const statusOptionsRaw = await client.data.get('status_options').catch(() => null);
            const statusOptions = statusOptionsRaw?.status_options || statusOptionsRaw;
            
            if (!statusOptions || !Array.isArray(statusOptions) || statusOptions.length === 0) {
              statusLabel = '❌ 옵션 조회 실패';
            } else {
              // Freshdesk 숫자값으로 원본 필드에서 매칭
              const statusOption = statusOptions.find(option => {
                const optionId = parseInt(option.id || option.value || option);
                return optionId === statusId;
              });
              
              if (statusOption) {
                statusLabel = statusOption.label || statusOption.name || statusOption.toString();
              } else {
                statusLabel = `❌ 알 수 없는 상태 (${statusId})`;
              }
            }
          } catch (error) {
            console.error('FDK 상태 조회 실패:', error);
            statusLabel = '❌ 조회 실패';
          }
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
        return `Agent ${agentId}`;
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
        return `Group ${groupId}`;
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

      // 1줄: 감정상태, 우선순위, 진행상태
      
      // 1. 백엔드 감정상태 (백엔드에서 제공하지 않으므로 기본값)
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

      // 2. 우선순위 (FDK 전용 조회)
      let priority = '❌ 우선순위 없음';
      if (optimizedData?.ticket?.ticket) {
        const ticket = optimizedData.ticket.ticket;
        
        if (ticket.priority !== undefined && ticket.priority !== null) {
          const priorityId = parseInt(ticket.priority);
          
          if (!App.state.client) {
            priority = '❌ FDK 오류';
          } else {
            try {
              const priorityOptionsRaw = await App.state.client.data.get('priority_options').catch(() => null);
              const priorityOptions = priorityOptionsRaw?.priority_options || priorityOptionsRaw;
              
              if (!priorityOptions || !Array.isArray(priorityOptions) || priorityOptions.length === 0) {
                priority = '❌ 옵션 조회 실패';
              } else {
                // Freshdesk 숫자값으로 원본 필드에서 매칭
                const priorityOption = priorityOptions.find(option => {
                  const optionId = parseInt(option.id || option.value || option);
                  return optionId === priorityId;
                });
                
                if (priorityOption) {
                  const priorityText = priorityOption.label || priorityOption.name || priorityOption.toString();
                  
                  // 이모지 패턴 매칭
                  let emoji = '📊';
                  const lowerText = priorityText.toLowerCase();
                  if (lowerText.includes('low') || lowerText.includes('낮')) {
                    emoji = '🔵';
                  } else if (lowerText.includes('medium') || lowerText.includes('보통') || lowerText.includes('normal')) {
                    emoji = '😐';
                  } else if (lowerText.includes('high') || lowerText.includes('높') || lowerText.includes('중요')) {
                    emoji = '🟡';
                  } else if (lowerText.includes('urgent') || lowerText.includes('긴급') || lowerText.includes('critical')) {
                    emoji = '🔴';
                  }
                  
                  priority = `${emoji} ${priorityText}`;
                } else {
                  priority = `❌ 알 수 없는 우선순위 (${priorityId})`;
                }
              }
            } catch (error) {
              console.error('FDK 우선순위 조회 실패:', error);
              priority = '❌ 조회 실패';
            }
          }
        }
      }
      row1Items.push(`<span class="meta-item">${priority}</span>`);

      // 3. 진행상태 (FDK 전용 조회)
      let status = '❌ 상태 없음';
      if (optimizedData?.ticket?.ticket) {
        const ticket = optimizedData.ticket.ticket;
        
        if (ticket.status !== undefined && ticket.status !== null) {
          const statusId = parseInt(ticket.status);
          
          if (!App.state.client) {
            status = '❌ FDK 오류';
          } else {
            try {
              const statusOptionsRaw = await App.state.client.data.get('status_options').catch(() => null);
              const statusOptions = statusOptionsRaw?.status_options || statusOptionsRaw;
              
              if (!statusOptions || !Array.isArray(statusOptions) || statusOptions.length === 0) {
                status = '❌ 옵션 조회 실패';
              } else {
                // Freshdesk 숫자값으로 원본 필드에서 매칭
                const statusOption = statusOptions.find(option => {
                  const optionId = parseInt(option.id || option.value || option);
                  return optionId === statusId;
                });
                
                if (statusOption) {
                  const statusText = statusOption.label || statusOption.name || statusOption.toString();
                  
                  // 이모지 패턴 매칭
                  let emoji = '⚪';
                  const lowerText = statusText.toLowerCase();
                  if (lowerText.includes('open') || lowerText.includes('열림') || lowerText.includes('new')) {
                    emoji = '🟢';
                  } else if (lowerText.includes('pending') || lowerText.includes('대기') || lowerText.includes('waiting')) {
                    emoji = '🟡';
                  } else if (lowerText.includes('resolved') || lowerText.includes('해결') || lowerText.includes('completed')) {
                    emoji = '✅';
                  } else if (lowerText.includes('closed') || lowerText.includes('종료') || lowerText.includes('finished')) {
                    emoji = '⚪';
                  } else if (lowerText.includes('customer') || lowerText.includes('고객')) {
                    emoji = '🟠';
                  } else if (lowerText.includes('third') || lowerText.includes('제3자') || lowerText.includes('external')) {
                    emoji = '🟣';
                  }
                  
                  status = `${emoji} ${statusText}`;
                } else {
                  status = `❌ 알 수 없는 상태 (${statusId})`;
                }
              }
            } catch (error) {
              console.error('FDK 상태 조회 실패:', error);
              status = '❌ 조회 실패';
            }
          }
        }
      }
      row1Items.push(`<span class="meta-item">${status}</span>`);

      // 2줄: 요청자, 담당그룹, 담당자

      // 4. 요청자 (FDK contact data method 우선 사용)
      let requester = '👤 미확인';
      if (optimizedData?.contact?.contact?.name) {
        requester = `👤 ${optimizedData.contact.contact.name}`;
      } else if (optimizedData?.contact?.name) {
        requester = `👤 ${optimizedData.contact.name}`;
      } else if (optimizedData?.ticket?.ticket?.requester_name) {
        requester = `👤 ${optimizedData.ticket.ticket.requester_name}`;
      }
      row2Items.push(`<span class="meta-item">${requester}</span>`);

      // 5. 담당그룹 (FDK group data method 우선 사용)
      let group = '👥 CS팀';
      if (optimizedData?.group?.group?.name) {
        group = `👥 ${optimizedData.group.group.name}`;
      } else if (optimizedData?.group?.name) {
        group = `👥 ${optimizedData.group.name}`;
      } else if (optimizedData?.group?.group_name) {
        group = `👥 ${optimizedData.group.group_name}`;
      } else if (optimizedData?.ticket?.ticket?.group_name) {
        group = `👥 ${optimizedData.ticket.ticket.group_name}`;
      }
      row2Items.push(`<span class="meta-item">${group}</span>`);

      // 6. 담당자 (최적화된 agent 데이터 사용)
      let agent = '👤 미배정';
      if (optimizedData?.agent?.contact?.name) {
        agent = `👤 ${optimizedData.agent.contact.name}`;
      }
      row2Items.push(`<span class="meta-item">${agent}</span>`);

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
      const loadingSubtitle = document.querySelector('.loading-subtitle');
      if (loadingSubtitle && message) {
        loadingSubtitle.textContent = message;
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

      // 인사이트 패널 생성 (실제 데이터 구조에 맞게)
      const avgSimilarity = filteredTickets.reduce((sum, t) => {
        const similarity = t.similarity_score || t.similarity || t.score || 0;
        const similarityPercent = similarity > 1 ? similarity : similarity * 100;
        return sum + similarityPercent;
      }, 0) / filteredTickets.length;
      const resolvedCount = filteredTickets.filter(t => {
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
      const activeCount = filteredTickets.length - resolvedCount;
      
      const insightPanel = `
        <div class="insight-panel">
          <div class="insight-title">💡 자동 분석 결과</div>
          <div class="insight-content">
            🎯 평균 유사도: ${Math.round(avgSimilarity)}%<br>
            📊 상태 분포: ${resolvedCount}건 해결완료, ${activeCount}건 진행중<br>
            📋 검색된 티켓: ${filteredTickets.length}건의 유사 사례 발견
          </div>
        </div>
      `;

      // 티켓 카드들 생성
      const ticketCards = await Promise.all(filteredTickets.map(async ticket => {
        console.log('🎫 Processing ticket:', ticket);
        
        // 원본 데이터 구조에 맞게 필드 매핑 (있는 필드만 사용)
        const ticketId = ticket.id || 'N/A';
        const ticketTitle = ticket.subject || '제목 없음';  // subject만 사용
        const similarity = ticket.similarity_score || ticket.score || 0;
        const similarityPercent = similarity > 1 ? similarity : similarity * 100;
        const createdAt = ticket.created_at || ticket.metadata?.created_at || null;
        
        const scoreClass = similarityPercent >= 80 ? 'score-high' : similarityPercent >= 60 ? 'score-medium' : 'score-low';
        const scoreIcon = similarityPercent >= 80 ? '🟢' : similarityPercent >= 60 ? '🟡' : '🔴';
        
        // 원본 필드만 사용 (백엔드 분석 결과 기반)
        const priority = ticket.metadata?.priority || ticket.priority || 1;  // 숫자 우선순위
        const status = ticket.metadata?.status || ticket.status || '미확인';  // 티켓 상태
        const responderName = ticket.metadata?.agent_name || ticket.metadata?.responder_id || '미지정';
        
        
        // 레이블 조회 (원본 숫자값 기반)
        const ticketForLabels = {
          priority: priority,
          status: status
        };
        
        const priorityText = await TicketLabelUtils.getPriorityLabel(ticketForLabels);
        const statusLabel = await TicketLabelUtils.getStatusLabel(ticketForLabels);
        
        // 담당자 이름 가져오기 (메인티켓 방식 재활용)
        const agentId = ticket.metadata?.responder_id || ticket.metadata?.agent_id;
        let agentName = responderName;
        if (agentId && App.state.client) {
          try {
            const fetchedAgentName = await TicketLabelUtils.getAgentName(agentId);
            if (fetchedAgentName) {
              agentName = fetchedAgentName;
            }
          } catch (error) {
            console.error('Agent 이름 조회 실패:', error);
          }
        }
        
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
                  ${agentName ? `<span>👤 ${agentName}</span>` : ''}
                </div>
                <span>${ticket.relative_time || '시간 미상'}</span>
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
      }));

      container.innerHTML = insightPanel + ticketCards.join('');
      
      // 탭 카운트 업데이트
      const countElement = document.getElementById('similarTicketsCount');
      if (countElement) {
        countElement.textContent = filteredTickets.length;
        console.log('✅ 유사 티켓 탭 카운트 업데이트:', filteredTickets.length);
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
              <div class="card-excerpt">
                ${doc.description || doc.content || '내용 정보가 없습니다.'}
              </div>
              <div class="card-meta">
                <div class="meta-left">
                  <span>📅 ${createdAt ? new Date(createdAt).toLocaleDateString('ko-KR') : 'N/A'}</span>
                  <span class="status-indicator status-resolved">KB문서</span>
                  <span>📂 ${doc.category || '일반'}</span>
                </div>
                <span>URL: ${docUrl.length > 30 ? docUrl.substring(0, 30) + '...' : docUrl}</span>
              </div>
              <div class="card-actions">
                <button class="card-btn primary" onclick="viewKBSummary('${docId}')">
                  👁️ 요약보기
                </button>
                <button class="card-btn" onclick="window.open('${docUrl}', '_blank')">
                  📄 원본보기
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


    // 채팅 메시지 추가
    addChatMessage(role, content, messageId) {
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
      
      messageDiv.innerHTML = `
        <div class="message-avatar">${avatar}</div>
        <div class="message-content">
          <div class="message-text">${marked ? marked.parse(content) : content}</div>
          <div class="message-time">${timeString}</div>
        </div>
      `;
      container.appendChild(messageDiv);
      container.scrollTop = container.scrollHeight;
    },

    // 채팅 메시지 업데이트 (스트리밍)
    updateChatMessage(messageId, content) {
      const messageText = document.querySelector(`#msg-${messageId} .message-text`);
      if (messageText && marked) {
        messageText.innerHTML = marked.parse(content);
        const container = document.getElementById('chatResults');
        if (container) {
          container.scrollTop = container.scrollHeight;
        }
      }
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
        
        // 모달 설정 구성 (자동 백엔드 호출 금지, 새로고침 버튼만 허용)
        const modalConfig = {
          title: "Copilot Canvas - AI 상담사 지원",
          template: "index.html",
          data: {
            ticketId: ticketId,
            ticket: ticket,
            hasCachedData: App.state.dataLoaded,
            timestamp: new Date().toISOString(),
            noBackendCall: true, // 모달에서 자동 백엔드 호출 금지
            usePreloadedData: true, // 캐시 데이터만 사용
            // 캐시된 데이터 전달
            cachedData: App.state.cachedData,
            cachedTicketInfo: App.state.cachedTicketInfo,
            // 새로고침 버튼 허용
            allowRefresh: true,
            // 로딩 상태 정보
            loadingStatus: { status: 'ready' },
            globalData: {},
            streamingStatus: { is_streaming: false },
            hasError: false,
            errorMessage: null,
            // 상태별 플래그
            isLoading: false,
            isReady: true,
            isPartiallyLoaded: false
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
    showError(message) {
      console.error('앱 에러:', message);
      
      const errorDiv = document.createElement('div');
      errorDiv.className = 'error-toast';
      errorDiv.textContent = message;
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
        max-width: 300px;
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
          this.updateSummary(currentData.summary);
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
          this.renderSimilarTickets(currentData.similarTickets);
          
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
          this.renderKBDocuments(currentData.kbDocuments);
          
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
    async handleSendMessage() {
      const input = document.getElementById('chatInput');
      const sendButton = document.getElementById('sendButton');
      
      if (!input || !input.value.trim()) return;

      const query = input.value.trim();
      input.value = '';
      
      // 사용자 메시지 표시
      App.ui.addChatMessage('user', query, Date.now());
      
      // 버튼 비활성화
      if (sendButton) {
        sendButton.disabled = true;
      }

      try {
        await App.api.sendChatQuery(query, App.state.currentMode);
      } catch (error) {
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
      
      // 티켓 ID 먼저 가져오기
      const basicTicketData = await client.data.get('ticket');
      App.state.ticketId = basicTicketData.ticket.id;
      console.log('티켓 ID 설정:', App.state.ticketId);
      
      // 기본 티켓 데이터를 백엔드 데이터로 설정 (임시)
      App.state.backendTicketData = basicTicketData.ticket;
      
      // FDK 원본 티켓 데이터도 별도 보관
      App.state.originalFDKTicket = basicTicketData.ticket;
      
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
      
      // 초기 데이터 로드 (모달에서만 건너뛰기)
      const modalData = window.modalData || {};
      const isModal = modalData.noBackendCall === true;
      
      console.log('🔍 App.init() 호출됨 - 현재 상태:', {
        isModal,
        BACKEND_CALLED: App.state.BACKEND_CALLED,
        modalData,
        location: window.location.href,
        isFrame: window.frameElement !== null,
        isParent: window.location === window.parent.location
      });
      
      if (!isModal && !App.state.BACKEND_CALLED) {
        console.log('🔥 페이지 최초 로딩 - 백엔드 호출 실행');
        App.state.isLoading = true;
        App.ui.showLoading();
        
        try {
          await App.api.loadInitialData(App.state.ticketId);
        } catch (error) {
          console.error('초기 데이터 로드 실패:', error);
          App.ui.hideLoading();
          App.ui.showError('백엔드 서버 연결 실패. 새로고침 버튼을 눌러 다시 시도하세요.');
        }
      } else {
        console.log('🚫 백엔드 호출 건너뛰기');
        
        // 모달에서 캐시된 데이터 렌더링
        if (isModal) {
          console.log('📂 모달에서 캐시된 데이터 렌더링 시작');
          
          // 로딩 숨기기
          App.ui.hideLoading();
          
          // 모달로 전달된 캐시 데이터 사용 (DOMContentLoaded에서 처리됨)
          console.log('⏳ 모달 캐시 데이터 복원 대기 중...');
        }
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
          chatInput.style.display = (tabName === 'copilot') ? 'block' : 'none';
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
          toggleBtn.innerHTML = '<span style="font-size: 16px;">⌃</span>';
        } else {
          // 접기
          section.classList.add('collapsed');
          toggleBtn.innerHTML = '<span style="font-size: 16px;">⌄</span>';
        }
      });
    }
  }
};

// 메인티켓과 유사티켓용 통합 레이블 조회 (일관성 보장)
const TicketLabelUtils = {
  // 우선순위 레이블 가져오기 (원본 필드 조회)
  async getPriorityLabel(ticketData) {
    if (!ticketData || (ticketData.priority === undefined && ticketData.priority !== 0)) {
      return '❌ 우선순위 없음';
    }
    
    const priorityId = parseInt(ticketData.priority);
    
    if (!App.state.client) {
      return '❌ FDK 오류';
    }
    
    try {
      // 원본 필드에서 priority 옵션 조회
      const priorityOptionsRaw = await App.state.client.data.get('priority_options').catch(() => null);
      const priorityOptions = priorityOptionsRaw?.priority_options || priorityOptionsRaw;
      
      if (!priorityOptions || !Array.isArray(priorityOptions) || priorityOptions.length === 0) {
        return '❌ 옵션 조회 실패';
      }
      
      // Freshdesk 숫자값으로 매칭 (id 필드 사용)
      const priorityOption = priorityOptions.find(option => {
        const optionId = parseInt(option.id || option.value || option);
        return optionId === priorityId;
      });
      
      if (!priorityOption) {
        return '❌ 매칭 실패';
      }
      
      const priorityText = priorityOption.label || priorityOption.name || priorityOption.toString();
      
      // 이모지 패턴 매칭
      let emoji = '📊';
      const lowerText = priorityText.toLowerCase();
      if (lowerText.includes('low') || lowerText.includes('낮')) {
        emoji = '🔵';
      } else if (lowerText.includes('medium') || lowerText.includes('보통') || lowerText.includes('normal')) {
        emoji = '😐';
      } else if (lowerText.includes('high') || lowerText.includes('높') || lowerText.includes('중요')) {
        emoji = '🟡';
      } else if (lowerText.includes('urgent') || lowerText.includes('긴급') || lowerText.includes('critical')) {
        emoji = '🔴';
      }
      
      return `${emoji} ${priorityText}`;
    } catch (error) {
      console.error('FDK 우선순위 조회 실패:', error);
      return '❌ 조회 실패';
    }
  },

  // 상태 레이블 가져오기 (원본 필드 조회)
  async getStatusLabel(ticketData) {
    if (!ticketData || (ticketData.status === undefined && ticketData.status !== 0)) {
      return '❌ 상태 없음';
    }
    
    const statusId = parseInt(ticketData.status);
    
    if (!App.state.client) {
      return '❌ FDK 오류';
    }
    
    try {
      // 원본 필드에서 status 옵션 조회
      const statusOptionsRaw = await App.state.client.data.get('status_options').catch(() => null);
      const statusOptions = statusOptionsRaw?.status_options || statusOptionsRaw;
      
      if (!statusOptions || !Array.isArray(statusOptions) || statusOptions.length === 0) {
        return '❌ 옵션 조회 실패';
      }
      
      // Freshdesk 숫자값으로 매칭 (id 필드 사용)
      const statusOption = statusOptions.find(option => {
        const optionId = parseInt(option.id || option.value || option);
        return optionId === statusId;
      });
      
      if (!statusOption) {
        return '❌ 매칭 실패';
      }
      
      const statusText = statusOption.label || statusOption.name || statusOption.toString();
      
      // 이모지 패턴 매칭
      let emoji = '⚪';
      const lowerText = statusText.toLowerCase();
      if (lowerText.includes('open') || lowerText.includes('열림') || lowerText.includes('new')) {
        emoji = '🟢';
      } else if (lowerText.includes('pending') || lowerText.includes('대기') || lowerText.includes('waiting')) {
        emoji = '🟡';
      } else if (lowerText.includes('resolved') || lowerText.includes('해결') || lowerText.includes('completed')) {
        emoji = '✅';
      } else if (lowerText.includes('closed') || lowerText.includes('종료') || lowerText.includes('finished')) {
        emoji = '⚪';
      } else if (lowerText.includes('customer') || lowerText.includes('고객')) {
        emoji = '🟠';
      } else if (lowerText.includes('third') || lowerText.includes('제3자') || lowerText.includes('external')) {
        emoji = '🟣';
      }
      
      return `${emoji} ${statusText}`;
    } catch (error) {
      console.error('FDK 상태 조회 실패:', error);
      return '❌ 조회 실패';
    }
  },

  // Agent 이름 가져오기 (메인티켓 방식 재활용)
  async getAgentName(agentId) {
    if (!App.state.client || !agentId) return null;
    
    try {
      // 메인티켓에서 사용하는 방식과 동일
      const agentName = await App.ui.getAgentName(agentId, App.state.client);
      return agentName;
    } catch (error) {
      console.error('Agent 이름 조회 실패:', error);
      return null;
    }
  },

  async getGroupName(groupId) {
    if (!App.state.client || !groupId) return null;
    
    try {
      // 메인티켓에서 사용하는 방식과 동일
      const groupName = await App.ui.getGroupName(groupId, App.state.client);
      return groupName;
    } catch (error) {
      console.error('Group 이름 조회 실패:', error);
      return null;
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
document.addEventListener('DOMContentLoaded', () => {
  // 모달에서 전달받은 데이터 확인
  const modalData = window.modalData || {};
  
  // 채팅 입력창만 숨기기
  const chatInput = document.getElementById('chatInputContainer');
  if (chatInput) {
    chatInput.style.display = 'none';
  }
  
  // noBackendCall 플래그 확인
  if (modalData.noBackendCall === true) {
    console.log('🚫 모달에서 noBackendCall 플래그 감지 - 백엔드 호출 생략');
    App.state.dataLoaded = true;
    App.state.BACKEND_CALLED = true; // 백엔드 호출 상태도 true로 설정
    
    // 모달에서 캐시된 데이터 복원 시도
    if (modalData.noBackendCall === true) {
      console.log('📂 모달 모드 - 캐시된 데이터 복원 시작');
      console.log('🔍 전달받은 modalData:', modalData);
      
      // 캐시된 데이터 복원 (전달받은 데이터 우선, 없으면 기본 메시지)
      if (modalData.cachedData) {
        App.state.cachedData = modalData.cachedData;
        console.log('✅ modalData에서 캐시 데이터 복원');
      } else {
        // 기본 데이터 설정
        App.state.cachedData = {
          summary: '모달에서 캐시된 데이터를 불러오는 중입니다...',
          similarTickets: [],
          kbDocuments: []
        };
        console.log('⚠️ modalData.cachedData가 없음 - 기본 데이터 설정');
      }
      
      if (modalData.cachedTicketInfo) {
        App.state.cachedTicketInfo = modalData.cachedTicketInfo;
        console.log('✅ modalData에서 티켓 정보 복원');
      }
      
      // 기본 UI 설정
      App.setupEventListeners();
      
      // UI 데이터 복원
      setTimeout(async () => {
        // 요약 복원
        if (App.state.cachedData.summary) {
          App.ui.updateSummary(App.state.cachedData.summary);
        }
        
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
        
        console.log('✅ 모달 캐시된 데이터 복원 완료');
      }, 200);
      
      // 탭 네비게이션 표시
      const tabNavigation = document.getElementById('tabNavigation');
      const tabContentArea = document.getElementById('tabContentArea');
      
      if (tabNavigation) {
        tabNavigation.style.display = 'block';
        console.log('✅ 모달 - 탭 네비게이션 표시');
      }
      
      if (tabContentArea) {
        tabContentArea.style.display = 'block';
        console.log('✅ 모달 - 탭 콘텐츠 영역 표시');
      }
      
      return;
    }
  }
  
  // FDK가 로드되었는지 확인
  if (typeof app !== 'undefined') {
    App.init().catch(error => {
      console.error('앱 초기화 중 오류:', error);
      App.ui.showError('앱 초기화 실패. 페이지를 새로고침하세요.');
    });
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
  const status = ticket.metadata?.status || ticket.status || '미확인';
  const priority = ticket.metadata?.priority || ticket.priority || 1;
  const responderName = ticket.metadata?.agent_name || ticket.metadata?.responder_id || '미지정';
  
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
              <span class="meta-value">${createdAt ? new Date(createdAt).toLocaleDateString('ko-KR') : 'N/A'}</span>
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
                <span class="attachment-name">${attachment.name || 'Unknown'}</span>
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