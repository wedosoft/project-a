/**
 * Freshdesk Custom App - Simplified Version
 * 단순하고 빠른 AI 상담사 지원 시스템
 */

const App = {
  // 설정
  config: {
    baseURL: 'http://localhost:8000',
    apiKey: 'Ug9H1cKCZZtZ4haamBy',
    tenantId: 'wedosoft',
    domain: 'wedosoft.freshdesk.com'
  },

  // 현재 상태
  state: {
    ticketId: null,
    isLoading: false,
    loadingInProgress: false, // API 호출 중복 방지
    dataLoaded: false, // 초기 데이터 로드 완료 여부
    currentMode: 'smart', // 'smart' or 'free'
    client: null, // FDK 클라이언트 객체
    
    // 로드된 데이터 캐시 (탭 전환 시 사라지지 않도록)
    cachedData: {
      similarTickets: [],
      kbDocuments: [],
      summary: ''
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


    // 초기 데이터 로드 (스트리밍) - fetch + ReadableStream 사용 (중복 방지)
    async loadInitialData(ticketId) {
      // 중복 호출 방지 체크
      if (App.state.loadingInProgress || App.state.dataLoaded) {
        console.log('⚠️ 초기 데이터 로드 중복 방지 - 현재 상태:', {
          loadingInProgress: App.state.loadingInProgress,
          dataLoaded: App.state.dataLoaded
        });
        return App.state.cachedData;
      }
      
      // 로딩 상태 설정
      App.state.loadingInProgress = true;
      App.state.dataLoaded = false;
      
      const url = `${App.config.baseURL}/init/${ticketId}?stream=true`;
      console.log('🔄 백엔드 초기 데이터 로드 시작:', url);
      
      try {
        const response = await fetch(url, {
          method: 'GET',
          headers: this.getHeaders()
        });
        
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
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
          
          // SSE 형식: data: {json}\n\n 으로 구분
          const chunks = buffer.split('\n\n');
          buffer = chunks.pop(); // 마지막 불완전한 청크는 버퍼에 보관
          
          for (const chunk of chunks) {
            if (!chunk.trim()) continue;
            
            // 각 청크를 개별적으로 처리
            const lines = chunk.split('\n');
            let jsonBuffer = '';
            
            for (const line of lines) {
              if (line.startsWith('data: ')) {
                const dataStr = line.slice(6).trim();
                console.log('파싱 시도:', dataStr.substring(0, 100) + '...');
                
                if (dataStr === '[DONE]') {
                  App.state.isLoading = false;
                  App.state.loadingInProgress = false;
                  App.state.dataLoaded = true;
                  App.ui.hideLoading();
                  return { summary, similarTickets, kbDocuments };
                }
                
                // 멀티라인 JSON 처리
                if (dataStr.startsWith('{') && !dataStr.endsWith('}')) {
                  jsonBuffer = dataStr;
                  continue;
                } else if (jsonBuffer && dataStr.endsWith('}')) {
                  jsonBuffer += dataStr;
                  try {
                    const data = JSON.parse(jsonBuffer);
                    console.log('멀티라인 파싱 성공:', data.type);
                    const result = App.ui.processStreamData(data, { summary, similarTickets, kbDocuments });
                    if (result) {
                      summary = result.summary || summary;
                      similarTickets = result.similarTickets || similarTickets;
                      kbDocuments = result.kbDocuments || kbDocuments;
                      
                      if (result.shouldReturn) {
                        App.state.isLoading = false;
                        App.state.loadingInProgress = false;
                        App.state.dataLoaded = true;
                        App.ui.hideLoading();
                        return { summary, similarTickets, kbDocuments };
                      }
                    }
                    jsonBuffer = '';
                  } catch (parseError) {
                    console.error('멀티라인 JSON 파싱 실패:', parseError.message);
                    jsonBuffer = '';
                  }
                  continue;
                }
                
                try {
                  const data = JSON.parse(dataStr);
                  console.log('파싱 성공:', data.type);
                  
                  // 데이터 처리
                  const result = App.ui.processStreamData(data, { summary, similarTickets, kbDocuments });
                  if (result) {
                    summary = result.summary || summary;
                    similarTickets = result.similarTickets || similarTickets;
                    kbDocuments = result.kbDocuments || kbDocuments;
                    
                    if (result.shouldReturn) {
                      App.state.isLoading = false;
                      App.state.loadingInProgress = false;
                      App.state.dataLoaded = true;
                      App.ui.hideLoading();
                      return { summary, similarTickets, kbDocuments };
                    }
                  }
                } catch (parseError) {
                  console.warn('JSON 파싱 실패 (무시):', parseError.message);
                  console.log('실패한 데이터 (처음 50자):', dataStr.substring(0, 50));
                  // 파싱 실패는 무시하고 계속 진행
                }
              }
            }
          }
        }
        
        // 스트림이 완료되었지만 complete 이벤트가 없는 경우
        App.state.isLoading = false;
        App.state.loadingInProgress = false;
        App.state.dataLoaded = true;
        App.ui.hideLoading();
        return { summary, similarTickets, kbDocuments };
        
      } catch (error) {
        App.state.isLoading = false;
        App.state.loadingInProgress = false;
        App.state.dataLoaded = false;
        App.ui.hideLoading();
        console.error('초기 데이터 로드 실패:', error);
        App.ui.showError('백엔드 서버에 연결할 수 없습니다. 서버가 실행 중인지 확인해주세요.');
        throw error;
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
        
        // 3. 상태 레이블 가져오기 (FDK 데이터 우선 사용)
        let statusLabel = null;
        if (mergedTicketData && mergedTicketData.status) {
          // 먼저 ticket 데이터에서 status_label 확인
          statusLabel = ticketData?.ticket?.status_label || 
                       mergedTicketData.status_label;
          
          // status_label이 없으면 기본 매핑 사용 (API 호출 방지)
          if (!statusLabel) {
            const defaultLabels = {
              1: '열림',
              2: '대기중', 
              3: '해결완료',
              4: '해결완료',
              5: '종료'
            };
            statusLabel = defaultLabels[mergedTicketData.status] || '알 수 없음';
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
        App.ui.updateTicketHeader(optimizedTicketData);
        
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
    
    // 상태 레이블 가져오기 (캐시 활용)
    async getStatusLabel(client, statusId) {
      // 상태 레이블 캐시 확인
      if (this.statusLabelCache && this.statusLabelCache[statusId]) {
        return this.statusLabelCache[statusId];
      }
      
      try {
        // status_options data method 시도 (v3.0에서 사용 가능한 경우)
        const statusOptions = await client.data.get('status_options').catch(() => null);
        if (statusOptions && statusOptions.length > 0) {
          const statusOption = statusOptions.find(opt => opt.id === statusId);
          if (statusOption) {
            // 캐시에 저장
            if (!this.statusLabelCache) this.statusLabelCache = {};
            this.statusLabelCache[statusId] = statusOption.label;
            return statusOption.label;
          }
        }
        
        // 기본값 반환
        const defaultLabels = {
          1: '열림',
          2: '대기중', 
          3: '해결완료',
          4: '해결완료',
          5: '종료'
        };
        return defaultLabels[statusId] || '알 수 없음';
        
      } catch (error) {
        console.warn('⚠️ 상태 레이블 조회 실패:', error);
        return '알 수 없음';
      }
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
    updateTicketHeader(optimizedData, emotionData = null) {
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

      // 2. 우선순위 (FDK data method 우선 사용)
      let priority = '😐 보통';
      if (optimizedData?.ticket?.ticket) {
        const ticket = optimizedData.ticket.ticket;
        
        // FDK에서 priority_label이 있으면 우선 사용
        let priorityText = ticket.priority_label || ticket.priority_name;
        
        if (!priorityText && ticket.priority) {
          const priorityMap = {
            1: '낮음',
            2: '보통', 
            3: '높음',
            4: '긴급'
          };
          priorityText = priorityMap[ticket.priority] || '보통';
        }
        
        if (!priorityText) priorityText = '보통';
        
        // 텍스트에 이모지 추가
        const priorityEmoji = {
          'Low': '🔵', '낮음': '🔵',
          'Medium': '😐', '보통': '😐',
          'High': '🟡', '높음': '🟡',
          'Urgent': '🔴', '긴급': '🔴'
        };
        const emoji = priorityEmoji[priorityText] || '😐';
        priority = `${emoji} ${priorityText}`;
      }
      row1Items.push(`<span class="meta-item">${priority}</span>`);

      // 3. 진행상태 (FDK data method와 백엔드 데이터 통합)
      let status = '⚪ 알 수 없음';
      if (optimizedData?.ticket?.ticket) {
        const ticket = optimizedData.ticket.ticket;
        
        // 우선순위: FDK status_label > 최적화된 statusLabel > 기본 매핑
        let statusText = ticket.status_label || 
                        ticket.status_name ||
                        optimizedData.statusLabel;
        
        if (!statusText && ticket.status) {
          // 기본 상태 매핑
          const statusMap = {
            1: '열림',
            2: '대기중',
            3: '해결완료', 
            4: '해결완료',
            5: '종료'
          };
          statusText = statusMap[ticket.status] || '알 수 없음';
        }
        
        if (!statusText) statusText = '알 수 없음';
        
        // 상태에 이모지 추가
        const statusEmoji = {
          '열림': '🟢', 'Open': '🟢',
          '대기중': '🟡', 'Pending': '🟡', 
          '해결완료': '✅', 'Resolved': '✅',
          '종료': '⚪', 'Closed': '⚪',
          '고객 대기': '🟠',
          '제3자 대기': '🟣'
        };
        const emoji = statusEmoji[statusText] || '⚪';
        status = `${emoji} ${statusText}`;
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
    renderSimilarTickets(tickets) {
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
      const ticketCards = filteredTickets.map(ticket => {
        console.log('🎫 Processing ticket:', ticket);
        
        // 실제 데이터 구조에 맞게 필드 매핑
        const ticketId = ticket.id || 'N/A';
        // subject 필드만 사용 (title 제외)
        const ticketTitle = (ticket.subject && ticket.subject.trim() !== '') ? ticket.subject : '제목 없음';
        const ticketContent = ticket.content || ticket.description || ticket.excerpt || '내용 없음';
        const similarity = ticket.similarity_score || ticket.similarity || ticket.score || 0;
        // 유사도를 백분율로 변환 (0.77 → 77%)
        const similarityPercent = similarity > 1 ? similarity : similarity * 100;
        const createdAt = ticket.created_at || ticket.createdAt || null;
        
        const scoreClass = similarityPercent >= 80 ? 'score-high' : similarityPercent >= 60 ? 'score-medium' : 'score-low';
        const scoreIcon = similarityPercent >= 80 ? '🟢' : similarityPercent >= 60 ? '🟡' : '🔴';
        
        // 백엔드 데이터 구조에 맞게 매핑
        const ticketStatus = ticket.ticket_status || ticket.status || 'N/A';
        const ticketPriority = ticket.priority || '보통';
        const requester = ticket.requester || '미확인';
        const assignee = ticket.assignee || '미지정';
        
        const statusClass = ticketStatus === 'resolved' ? 'status-resolved' : 
                           ticketStatus === 'in_progress' ? 'status-progress' : 'status-pending';
        const priorityIcon = ticketPriority === 'high' || ticketPriority === '높음' ? '🔥' : 
                            ticketPriority === 'urgent' || ticketPriority === '긴급' ? '🚨' : 
                            ticketPriority === 'low' || ticketPriority === '낮음' ? '🔵' : '🟠';

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
              <div class="card-excerpt">
                ${ticketContent.length > 150 ? ticketContent.substring(0, 150) + '...' : ticketContent}
              </div>
              <div class="card-meta">
                <div class="meta-left">
                  <span>📅 ${createdAt ? new Date(createdAt).toLocaleDateString('ko-KR') : 'N/A'}</span>
                  <span class="status-indicator ${statusClass}">${ticketStatus}</span>
                  <span class="priority-indicator">${priorityIcon} ${ticketPriority}</span>
                  <span>👤 ${requester}</span>
                  <span>🎯 ${assignee}</span>
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
      }).join('');

      container.innerHTML = insightPanel + ticketCards;
      
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
      console.log('🚀 renderKBDocuments 함수 호출됨');
      console.log('🚀 받은 documents 파라미터:', documents);
      console.log('🚀 documents 타입:', typeof documents);
      console.log('🚀 documents 배열인가?', Array.isArray(documents));
      
      const container = document.getElementById('kbDocumentsContainer');
      if (!container) {
        console.error('❌ kbDocumentsContainer not found');
        return;
      }
      
      console.log('✅ kbDocumentsContainer 찾음:', container);
      console.log('🔍 Checking documents data:', documents);
      
      if (!documents || !documents.length) {
        console.log('⚠️ No KB documents to render');
        container.innerHTML = `
          <div class="insight-panel">
            <div class="insight-title">📚 지식베이스 검색</div>
            <div class="insight-content">관련 문서가 없습니다.</div>
          </div>
        `;
        return;
      }

      console.log('✅ Rendering KB documents:', documents.length, '건');

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
      
      // 강제로 KB 탭을 활성화해보기 (디버깅용)
      if (kbTabContent && !kbTabContent.classList.contains('active')) {
        console.log('⚠️ KB 탭이 비활성화 상태입니다. 강제 활성화를 시도합니다.');
        // 디버깅을 위해 잠시 강제 활성화
        setTimeout(() => {
          console.log('🔧 KB 탭 강제 활성화 (5초 후 자동 해제)');
          kbTabContent.classList.add('active');
          if (kbTabButton) kbTabButton.classList.add('active');
          
          // 5초 후 원래 상태로 복원
          setTimeout(() => {
            console.log('🔧 KB 탭 상태 복원');
            if (!document.querySelector('.tab-button[data-tab="kb"]').classList.contains('active')) {
              kbTabContent.classList.remove('active');
            }
          }, 5000);
        }, 1000);
      }
      
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
    async showFDKModal(ticketId, hasCachedData = false) {
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
        
        // 모달 설정 구성 (원본과 동일하게 확장)
        const modalConfig = {
          title: "Copilot Canvas - AI 상담사 지원",
          template: "index.html",
          data: {
            ticketId: ticketId,
            ticket: ticket,
            hasCachedData: hasCachedData || App.state.dataLoaded,
            timestamp: new Date().toISOString(),
            noBackendCall: App.state.dataLoaded || hasCachedData, // 데이터 로드 완료 시 백엔드 호출 안함
            usePreloadedData: App.state.dataLoaded || hasCachedData, // ✅ 미리 로드된 데이터 사용 플래그
            // 로딩 상태 정보 (원본에서 추가)
            loadingStatus: { status: 'ready' },
            globalData: {},
            streamingStatus: { is_streaming: false },
            hasError: false,
            errorMessage: null,
            // 상태별 플래그
            isLoading: App.state.isLoading || false,
            isReady: !App.state.isLoading,
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
      
      // 로딩 완료 시 탭 네비게이션과 카드 리스트 영역 표시
      const tabNavigation = document.getElementById('tabNavigation');
      const cardListArea = document.getElementById('cardListArea');
      
      if (tabNavigation) {
        tabNavigation.style.display = 'block';
        console.log('✅ 탭 네비게이션 표시');
      }
      
      if (cardListArea) {
        cardListArea.style.display = 'block';
        console.log('✅ 카드 리스트 영역 표시');
      }
      
      // 로딩 완료 후 유사티켓 탭 활성화 보장
      setTimeout(() => {
        this.ensureTicketsTabActive();
      }, 100);
    },

    // 유사티켓 탭이 활성화되도록 보장하는 함수
    ensureTicketsTabActive() {
      console.log('🔄 ensureTicketsTabActive 실행');
      
      // 현재 활성화된 탭 확인
      const activeTabContents = document.querySelectorAll('.tab-content.active');
      const activeTabButtons = document.querySelectorAll('.tab-button.active');
      
      console.log('🔍 현재 활성화된 탭 수:', {
        activeTabContents: activeTabContents.length,
        activeTabButtons: activeTabButtons.length,
        contentTabs: Array.from(activeTabContents).map(el => el.getAttribute('data-tab')),
        buttonTabs: Array.from(activeTabButtons).map(el => el.getAttribute('data-tab'))
      });
      
      // 유사티켓 탭 엘리먼트 확인
      const ticketsTabContent = document.querySelector('.tab-content[data-tab="tickets"]');
      const ticketsTabButton = document.querySelector('.tab-button[data-tab="tickets"]');
      
      if (!ticketsTabContent || !ticketsTabButton) {
        console.error('❌ 유사티켓 탭 엘리먼트를 찾을 수 없음');
        return;
      }
      
      console.log('🔄 전체 탭 상태 리셋 후 유사티켓 탭만 활성화');
      
      // 모든 탭 강제 비활성화 (중복 활성화 방지)
      document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
        console.log('🔸 탭 콘텐츠 비활성화:', content.getAttribute('data-tab'));
      });
      document.querySelectorAll('.tab-button').forEach(btn => {
        btn.classList.remove('active');
        console.log('🔸 탭 버튼 비활성화:', btn.getAttribute('data-tab'));
      });
      
      // 유사티켓 탭만 활성화
      ticketsTabContent.classList.add('active');
      ticketsTabButton.classList.add('active');
      
      // 최종 상태 확인
      const finalActiveContents = document.querySelectorAll('.tab-content.active');
      const finalActiveButtons = document.querySelectorAll('.tab-button.active');
      
      console.log('✅ 탭 활성화 완료 - 최종 상태:', {
        activeContents: finalActiveContents.length,
        activeButtons: finalActiveButtons.length,
        activeContentTab: finalActiveContents[0]?.getAttribute('data-tab'),
        activeButtonTab: finalActiveButtons[0]?.getAttribute('data-tab')
      });
      
      if (finalActiveContents.length !== 1 || finalActiveButtons.length !== 1) {
        console.error('⚠️ 비정상적인 탭 상태 감지 - 여러 탭이 활성화됨');
      }
      
      // 캐시된 데이터 복원
      App.ui.refreshTabContent('tickets');
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
    processStreamData(data, currentData) {
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
          
          // 강제로 KB 탭 카운트 업데이트
          const kbCountElement = document.getElementById('kbDocumentsCount');
          if (kbCountElement) {
            kbCountElement.textContent = currentData.kbDocuments.length;
            console.log('🔢 KB 탭 카운트 강제 업데이트:', currentData.kbDocuments.length);
            
            // KB 탭 버튼에 시각적 피드백 추가 (데이터가 있음을 알림)
            const kbTabButton = document.querySelector('.tab-button[data-tab="kb"]');
            if (kbTabButton && currentData.kbDocuments.length > 0) {
              // 잠깐 하이라이트 효과를 줘서 데이터가 로드되었음을 알림
              kbTabButton.style.animation = 'pulse 2s';
              console.log('✨ KB 탭 버튼에 데이터 로드 알림 효과 적용');
              
              setTimeout(() => {
                if (kbTabButton.style.animation === 'pulse 2s') {
                  kbTabButton.style.animation = '';
                }
              }, 2000);
            }
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
            this.updateTicketHeader(App.state.cachedTicketInfo, data);
          }
          break;
          
        case 'complete':
          // 완료 시 프로그레스 바를 100%로 설정
          App.ui.updateProgressBar(100, '분석 완료!', null, 0);
          console.log('✅ 모든 데이터 로딩 완료');
          
          // 로딩 상태 업데이트
          App.state.isLoading = false;
          App.state.loadingInProgress = false;
          App.state.dataLoaded = true;
          
          // 완료 시점에서 헤더 업데이트 (감정 데이터가 있을 수 있음)
          if (App.state.cachedTicketInfo && App.state.cachedTicketInfo.lastUpdated) {
            // data.emotion_data가 있다면 감정 분석 결과로 사용
            const emotionData = data.emotion_data || data.emotion || null;
            if (emotionData) {
              console.log('😊 완료 시점 감정 데이터 업데이트:', emotionData);
              this.updateTicketHeader(App.state.cachedTicketInfo, emotionData);
            }
          }
          
          // 데이터 로딩 완료 후 유사티켓 탭이 활성화되도록 보장
          setTimeout(() => {
            console.log('🔄 데이터 로딩 완료 후 유사티켓 탭 활성화 확인');
            this.ensureTicketsTabActive();
          }, 500);
          
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

    // 탭 전환
    handleTabSwitch(tabName) {
      console.log('🔄 탭 전환 시작:', tabName);
      
      // 현재 스크롤 위치 저장
      const mainContent = document.querySelector('.main-content');
      const currentScrollTop = mainContent ? mainContent.scrollTop : 0;
      console.log('📍 현재 스크롤 위치:', currentScrollTop);
      
      // 전환 전 현재 상태 로깅
      const beforeActiveContents = document.querySelectorAll('.tab-content.active');
      const beforeActiveButtons = document.querySelectorAll('.tab-button.active');
      console.log('🔍 전환 전 활성 탭:', {
        contentCount: beforeActiveContents.length,
        buttonCount: beforeActiveButtons.length,
        contentTabs: Array.from(beforeActiveContents).map(el => el.getAttribute('data-tab')),
        buttonTabs: Array.from(beforeActiveButtons).map(el => el.getAttribute('data-tab'))
      });
      
      // 스크롤 방지를 위한 추가 처리
      const preventScroll = (e) => {
        e.preventDefault();
        e.stopPropagation();
        return false;
      };
      
      // 임시로 스크롤 이벤트 차단
      if (mainContent) {
        mainContent.addEventListener('scroll', preventScroll, { passive: false });
      }
      
      // 모든 탭 강제 비활성화
      document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
        console.log('🔸 콘텐츠 비활성화:', content.getAttribute('data-tab'));
      });
      
      document.querySelectorAll('.tab-button').forEach(btn => {
        btn.classList.remove('active');
        console.log('🔸 버튼 비활성화:', btn.getAttribute('data-tab'));
      });
      
      // 선택된 탭 엘리먼트 찾기
      const selectedContent = document.querySelector(`.tab-content[data-tab="${tabName}"]`);
      const selectedButton = document.querySelector(`.tab-button[data-tab="${tabName}"]`);
      
      console.log('🔍 선택된 탭 엘리먼트:', {
        tabName,
        selectedContent: !!selectedContent,
        selectedButton: !!selectedButton
      });
      
      if (!selectedContent || !selectedButton) {
        console.error('❌ 탭 엘리먼트를 찾을 수 없음:', {
          tabName,
          contentFound: !!selectedContent,
          buttonFound: !!selectedButton
        });
        // 스크롤 이벤트 차단 해제
        if (mainContent) {
          mainContent.removeEventListener('scroll', preventScroll);
        }
        return;
      }
      
      // 선택된 탭만 활성화
      selectedContent.classList.add('active');
      selectedButton.classList.add('active');
      
      // 스크롤 위치 즉시 복원 및 이벤트 차단 해제
      setTimeout(() => {
        if (mainContent) {
          mainContent.scrollTop = currentScrollTop;
          console.log('📍 스크롤 위치 복원:', currentScrollTop);
          // 스크롤 이벤트 차단 해제
          mainContent.removeEventListener('scroll', preventScroll);
        }
      }, 0);
      
      // 전환 후 상태 확인
      const afterActiveContents = document.querySelectorAll('.tab-content.active');
      const afterActiveButtons = document.querySelectorAll('.tab-button.active');
      
      console.log('✅ 탭 전환 완료 - 최종 상태:', {
        targetTab: tabName,
        activeContents: afterActiveContents.length,
        activeButtons: afterActiveButtons.length,
        activeContentTab: afterActiveContents[0]?.getAttribute('data-tab'),
        activeButtonTab: afterActiveButtons[0]?.getAttribute('data-tab')
      });
      
      // 비정상 상태 감지
      if (afterActiveContents.length !== 1 || afterActiveButtons.length !== 1) {
        console.error('⚠️ 탭 전환 후 비정상 상태:', {
          expectedActiveCount: 1,
          actualContentCount: afterActiveContents.length,
          actualButtonCount: afterActiveButtons.length
        });
      }
      
      // 캐시된 데이터 복원
      App.ui.refreshTabContent(tabName);
    }
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
            console.log('📊 현재 데이터 로드 상태:', {
              dataLoaded: App.state.dataLoaded,
              loadingInProgress: App.state.loadingInProgress
            });
            
            // 데이터 로드 완료 시 캐시된 데이터 사용, 미완료 시 로딩 상태 표시
            const hasCachedData = App.state.dataLoaded;
            await App.ui.showFDKModal(currentTicketId, hasCachedData);
          } else {
            console.log('📱 예상치 못한 위치에서의 앱 활성화:', ctx.location);
            // 예상치 못한 위치에서도 데이터 로드 상태 고려
            const hasCachedData = App.state.dataLoaded;
            await App.ui.showFDKModal(App.state.ticketId, hasCachedData);
          }
        } catch (err) {
          console.error('❌ app.activated 이벤트 처리 오류:', err);
          // 오류가 발생해도 기본 모달은 표시 (백엔드 호출 없이)
          try {
            await App.ui.showFDKModal(App.state.ticketId, true);
          } catch (fallbackError) {
            console.error('❌ 폴백 모달 표시도 실패:', fallbackError);
          }
        }
      });
      
      // 초기 데이터 로드
      App.state.isLoading = true;
      App.ui.showLoading();
      
      try {
        await App.api.loadInitialData(App.state.ticketId);
        // 데이터 로드 완료 후 유사티켓 탭 활성화 보장
        setTimeout(() => {
          App.ui.ensureTicketsTabActive();
        }, 100);
      } catch (error) {
        console.error('초기 데이터 로드 실패:', error);
        App.ui.hideLoading();
        // 백엔드 연결 실패 시에도 기본 UI는 표시
        App.ui.showError('백엔드 서버 연결 실패. 일부 기능이 제한됩니다.');
        // 오류 발생 시에도 유사티켓 탭은 활성화
        setTimeout(() => {
          App.ui.ensureTicketsTabActive();
        }, 100);
      }
      
    } catch (error) {
      console.error('FDK 초기화 오류:', error);
      console.warn('FDK 없이 기본 모드로 실행합니다.');
      
      // FDK 없이도 기본 기능은 사용 가능하도록 더미 티켓 ID 설정
      App.state.ticketId = 'demo-ticket-' + Date.now();
      App.ui.showError('FDK 초기화 실패. 데모 모드로 실행됩니다.');
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
      btn.addEventListener('click', () => {
        App.events.handleTabSwitch(btn.dataset.tab);
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
          // 펴기
          section.classList.remove('collapsed');
          toggleBtn.innerHTML = '<span style="font-size: 16px;">⌃</span>';
          console.log('✅ 요약 펼치기 실행');
        } else {
          // 접기
          section.classList.add('collapsed');
          toggleBtn.innerHTML = '<span style="font-size: 16px;">⌄</span>';
          console.log('✅ 요약 접기 실행');
        }
      });
    }
  }
};

// 전역으로 노출 (디버깅용 + FDK 이벤트 처리)
window.App = App;

// Top bar navigation 이벤트 처리용 전역 함수 (중복 방지 강화)
window.showFDKModal = async function(ticketId) {
  console.log('📡 Top bar navigation에서 모달 열기 요청');
  console.log('📊 현재 데이터 로드 상태:', {
    dataLoaded: App.state.dataLoaded,
    loadingInProgress: App.state.loadingInProgress
  });
  
  if (App && App.ui && App.ui.showFDKModal) {
    // 데이터 로드 상태에 따라 캐시된 데이터 사용 여부 결정
    const hasCachedData = App.state.dataLoaded;
    await App.ui.showFDKModal(ticketId || App.state.ticketId, hasCachedData);
  } else {
    console.error('❌ App.ui.showFDKModal 함수가 준비되지 않음');
  }
};

// DOM 로드 완료 시 앱 초기화
document.addEventListener('DOMContentLoaded', () => {
  // 모달에서 전달받은 데이터 확인
  const modalData = window.modalData || {};
  
  // 강화된 탭 초기화 함수
  function forceTabReset() {
    console.log('🔄 강화된 탭 상태 초기화 실행');
    
    // 모든 탭 강제 비활성화
    document.querySelectorAll('.tab-content').forEach(content => {
      content.classList.remove('active');
      content.style.display = 'none'; // 강제로 숨김
      console.log('🔸 강제 탭 콘텐츠 비활성화:', content.getAttribute('data-tab'));
    });
    document.querySelectorAll('.tab-button').forEach(btn => {
      btn.classList.remove('active');
      console.log('🔸 강제 탭 버튼 비활성화:', btn.getAttribute('data-tab'));
    });
    
    // 유사티켓 탭만 활성화
    const ticketsTabContent = document.querySelector('.tab-content[data-tab="tickets"]');
    const ticketsTabButton = document.querySelector('.tab-button[data-tab="tickets"]');
    
    if (ticketsTabContent && ticketsTabButton) {
      ticketsTabContent.classList.add('active');
      ticketsTabContent.style.display = 'block'; // 강제로 표시
      ticketsTabButton.classList.add('active');
      console.log('✅ 유사티켓 탭 강제 활성화 완료');
    } else {
      console.error('❌ 유사티켓 탭 엘리먼트를 찾을 수 없음');
    }
  }
  
  // DOM 로드 즉시 탭 상태 강제 리셋 및 유사티켓 탭만 활성화
  console.log('🔄 DOM 로드 - 탭 상태 초기화 시작');
  forceTabReset();
  
  // 추가 보험: 여러 시점에서 탭 상태 강제 리셋
  setTimeout(() => {
    console.log('🔄 50ms 후 탭 재확인');
    forceTabReset();
  }, 50);
  
  setTimeout(() => {
    console.log('🔄 200ms 후 탭 재확인');
    forceTabReset();
  }, 200);
  
  setTimeout(() => {
    console.log('🔄 500ms 후 탭 재확인');
    forceTabReset();
    if (window.App && window.App.ui && window.App.ui.ensureTicketsTabActive) {
      window.App.ui.ensureTicketsTabActive();
    }
  }, 500);
  
  // noBackendCall 플래그 확인
  if (modalData.noBackendCall === true) {
    console.log('🚫 모달에서 noBackendCall 플래그 감지 - 백엔드 호출 생략');
    App.state.dataLoaded = true;
    App.state.loadingInProgress = false;
    
    // 캐시된 데이터가 있으면 복원
    if (modalData.hasCachedData) {
      console.log('📂 캐시된 데이터 사용 모드');
      // 기본 UI 설정만 하고 백엔드 호출 없이 진행
      App.setupEventListeners();
      
      // noBackendCall 모드에서도 탭 네비게이션 표시
      const tabNavigation = document.getElementById('tabNavigation');
      const cardListArea = document.getElementById('cardListArea');
      
      if (tabNavigation) {
        tabNavigation.style.display = 'block';
        console.log('✅ noBackendCall 모드 - 탭 네비게이션 표시');
      }
      
      if (cardListArea) {
        cardListArea.style.display = 'block';
        console.log('✅ noBackendCall 모드 - 카드 리스트 영역 표시');
      }
      
      // 캐시된 데이터 사용 시에도 유사티켓 탭 활성화
      setTimeout(() => {
        App.ui.ensureTicketsTabActive();
      }, 200);
      return;
    }
  }
  
  // FDK가 로드되었는지 확인
  if (typeof app !== 'undefined') {
    App.init().catch(error => {
      console.error('앱 초기화 중 오류:', error);
      // FDK 없이도 기본 UI는 작동하도록 이벤트 리스너 설정
      App.setupEventListeners();
      
      // 오류 시에도 탭 네비게이션 표시
      const tabNavigation = document.getElementById('tabNavigation');
      const cardListArea = document.getElementById('cardListArea');
      
      if (tabNavigation) {
        tabNavigation.style.display = 'block';
        console.log('✅ 초기화 오류 시 - 탭 네비게이션 표시');
      }
      
      if (cardListArea) {
        cardListArea.style.display = 'block';
        console.log('✅ 초기화 오류 시 - 카드 리스트 영역 표시');
      }
      
      // 오류 시에도 유사티켓 탭 활성화
      setTimeout(() => {
        App.ui.ensureTicketsTabActive();
      }, 200);
    });
  } else {
    console.warn('FDK가 로드되지 않았습니다. 기본 UI만 작동합니다.');
    // FDK 없이도 기본 UI는 작동하도록 이벤트 리스너 설정
    App.setupEventListeners();
    
    // FDK 없이도 탭 네비게이션 표시
    const tabNavigation = document.getElementById('tabNavigation');
    const cardListArea = document.getElementById('cardListArea');
    
    if (tabNavigation) {
      tabNavigation.style.display = 'block';
      console.log('✅ FDK 없음 - 탭 네비게이션 표시');
    }
    
    if (cardListArea) {
      cardListArea.style.display = 'block';
      console.log('✅ FDK 없음 - 카드 리스트 영역 표시');
    }
    
    // FDK 없이도 유사티켓 탭 활성화
    setTimeout(() => {
      App.ui.ensureTicketsTabActive();
    }, 200);
  }
});