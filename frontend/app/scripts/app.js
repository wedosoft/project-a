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

    // 초기 데이터 로드 (스트리밍) - fetch + ReadableStream 사용
    async loadInitialData(ticketId) {
      const url = `${App.config.baseURL}/init/${ticketId}?stream=true`;
      
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
        App.ui.hideLoading();
        return { summary, similarTickets, kbDocuments };
        
      } catch (error) {
        App.state.isLoading = false;
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
    // 백엔드 티켓 데이터를 기반으로 추가 FDK 데이터 수집
    async collectAdditionalTicketData() {
      console.log('🔍 추가 FDK 데이터 수집 시작');
      
      if (!App.state.client) {
        console.warn('⚠️ FDK Client가 없어 추가 데이터 수집 불가');
        return;
      }
      
      // FDK 원본 티켓 데이터를 우선 사용, 없으면 백엔드 데이터 사용
      const ticketData = App.state.originalFDKTicket || App.state.backendTicketData;
      if (!ticketData) {
        console.warn('⚠️ 티켓 데이터가 없어 추가 데이터 수집 불가');
        return;
      }
      
      const client = App.state.client;
      
      try {
        // 1. Contact 데이터 (요청자 정보) - 필수
        let contactData = null;
        try {
          contactData = await client.data.get('contact');
          console.log('🔍 Contact 데이터 수집 완료:', contactData);
        } catch (e) {
          console.warn('⚠️ Contact 데이터 조회 실패:', e);
        }
        
        // 2. ticket_fields 데이터 (상태 레이블) - 필수
        let ticketFieldsData = null;
        try {
          console.log('🔍 ticket_fields API 호출 시작...');
          const response = await client.request.invoke('getTicketFields', {
            type: 'default_status'
          });
          console.log('🔍 ticket_fields API 응답:', response);
          if (response) {
            ticketFieldsData = response;
            console.log('🔍 ticket_fields 데이터 수집 완료:', ticketFieldsData);
          } else {
            console.warn('⚠️ ticket_fields 응답이 비어있음:', response);
          }
        } catch (e) {
          console.warn('⚠️ ticket_fields 조회 실패:', e);
        }
        
        // 3. Group 데이터 (담당 그룹) - 필수
        let groupData = null;
        if (ticketData.group_id) {
          try {
            console.log('🔍 Groups API 호출 시작, group_id:', ticketData.group_id);
            // 새로운 FDK API 방식으로 groups 호출
            const groupResponse = await client.request.invoke('getGroupDetails', {
              id: ticketData.group_id
            });
            console.log('🔍 Groups API 응답:', groupResponse);
            if (groupResponse && groupResponse.name) {
              console.log('🔍 그룹명:', groupResponse.name);
              groupData = { name: groupResponse.name, id: ticketData.group_id };
              console.log('🔍 Groups API로 그룹명 조회 성공:', groupData);
            } else if (ticketData.group?.name) {
              groupData = { name: ticketData.group.name, id: ticketData.group_id };
              console.log('🔍 티켓 데이터에서 그룹명 추출:', groupData);
            } else {
              console.log('🔍 그룹 ID만 있음, 그룹명 없이 ID만 저장:', ticketData.group_id);
              groupData = { name: `그룹 ID: ${ticketData.group_id}`, id: ticketData.group_id };
            }
          } catch (e) {
            console.warn('⚠️ 그룹 정보 조회 실패:', e);
            // Fallback으로 티켓 데이터 확인
            if (ticketData.group?.name) {
              groupData = { name: ticketData.group.name, id: ticketData.group_id };
            } else {
              groupData = { name: `그룹 ID: ${ticketData.group_id}`, id: ticketData.group_id };
            }
          }
        }
        
        // 4. Agent 데이터 (담당자) - 필수
        let agentData = null;
        if (ticketData.responder_id) {
          try {
            console.log('🔍 Agents API 호출 시작, responder_id:', ticketData.responder_id);
            // 새로운 FDK API 방식으로 agents 호출
            const agentResponse = await client.request.invoke('getAgentDetails', {
              id: ticketData.responder_id
            });
            console.log('🔍 Agents API 응답:', agentResponse);
            if (agentResponse && agentResponse.contact && agentResponse.contact.name) {
              console.log('🔍 에이전트명:', agentResponse.contact.name);
              agentData = { contact: { name: agentResponse.contact.name }, id: ticketData.responder_id };
              console.log('🔍 Agents API로 담당자명 조회 성공:', agentData);
            } else {
              // Fallback으로 로그인 사용자 확인
              console.log('🔍 Agents API 실패, loggedInUser로 폴백 시도...');
              const loggedInUser = await client.data.get('loggedInUser');
              console.log('🔍 loggedInUser 정보:', loggedInUser);
              if (loggedInUser && loggedInUser.contact && loggedInUser.contact.id === ticketData.responder_id) {
                agentData = { contact: { name: loggedInUser.contact.name }, id: ticketData.responder_id };
                console.log('🔍 로그인 사용자 정보에서 담당자명 추출:', agentData);
              } else if (ticketData.responder?.name) {
                agentData = { contact: { name: ticketData.responder.name }, id: ticketData.responder_id };
                console.log('🔍 티켓 데이터에서 담당자명 추출:', agentData);
              } else {
                console.log('🔍 담당자 ID만 있음, ID만 저장:', ticketData.responder_id);
                agentData = { contact: { name: `에이전트 ID: ${ticketData.responder_id}` }, id: ticketData.responder_id };
              }
            }
          } catch (e) {
            console.warn('⚠️ 담당자 정보 조회 실패:', e);
            // Fallback 처리
            if (ticketData.responder?.name) {
              agentData = { contact: { name: ticketData.responder.name }, id: ticketData.responder_id };
            } else {
              agentData = { contact: { name: `에이전트 ID: ${ticketData.responder_id}` }, id: ticketData.responder_id };
            }
          }
        } else {
          console.log('🔍 responder_id가 없음, 미배정으로 처리');
          agentData = { contact: { name: '미배정' }, id: null };
        }
        
        // 5. 모든 데이터 통합 및 저장
        const allTicketData = {
          ticket: { ticket: ticketData }, // 기존 구조 유지
          contact: contactData,
          group: groupData,
          agent: agentData,
          ticketFields: ticketFieldsData,
          lastUpdated: Date.now()
        };
        
        // 캐시에 저장
        App.state.cachedTicketInfo = allTicketData;
        console.log('🔍 모든 추가 데이터 수집 완료 및 캐시 저장');
        
        // 헤더 업데이트
        App.ui.updateTicketHeader(allTicketData);
        
      } catch (error) {
        console.error('❌ 추가 FDK 데이터 수집 실패:', error);
      }
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
          if (App.state.cachedData.kbDocuments && App.state.cachedData.kbDocuments.length > 0) {
            console.log('📚 KB 문서 데이터 복원:', App.state.cachedData.kbDocuments.length, '건');
            this.renderKBDocuments(App.state.cachedData.kbDocuments);
          } else {
            console.log('📚 KB 문서 캐시 데이터 없음');
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

    // 헤더 티켓 메타정보 업데이트 (통합 데이터 사용)
    updateTicketHeader(allTicketData, emotionData = null) {
      console.log('🔍 updateTicketHeader 호출됨 - allTicketData:', allTicketData);
      console.log('🔍 updateTicketHeader 호출됨 - emotionData:', emotionData);
      
      const metaRow1 = document.getElementById('metaRow1');
      const metaRow2 = document.getElementById('metaRow2');
      if (!metaRow1 || !metaRow2) return;

      let row1Items = [];
      let row2Items = [];

      // 1줄: 감정상태, 우선순위, 진행상태
      
      // 1. 백엔드 감정상태 (있는 경우에만)
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

      // 2. 우선순위 (FDK 또는 백엔드 ticket_fields 사용)
      let priority = '😐 보통';
      if (allTicketData?.ticket?.ticket) {
        const ticket = allTicketData.ticket.ticket;
        
        // 우선순위 - 먼저 텍스트 레이블 사용, 없으면 정수값 매핑
        let priorityText = ticket.priority_label;
        if (!priorityText) {
          const priorityMap = {
            1: '낮음',
            2: '보통', 
            3: '높음',
            4: '긴급'
          };
          priorityText = priorityMap[ticket.priority] || '보통';
        }
        
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

      // 3. 진행상태 (백엔드 ticket_fields 레이블 우선 사용)
      let status = '⚪ 알 수 없음';
      if (allTicketData?.ticket?.ticket) {
        const ticket = allTicketData.ticket.ticket;
        let statusText = null;
        
        // 백엔드에서 가져온 ticket_fields 레이블 우선 사용
        if (allTicketData.ticketFields && ticket.status) {
          try {
            const statusFields = allTicketData.ticketFields;
            // ticket_fields에서 현재 티켓 상태에 해당하는 레이블 찾기
            if (statusFields.choices && Array.isArray(statusFields.choices)) {
              const statusChoice = statusFields.choices.find(choice => choice.id === ticket.status);
              if (statusChoice) {
                statusText = statusChoice.label;
                console.log('🔍 ticket_fields에서 상태 레이블 찾음:', statusText);
              }
            }
          } catch (e) {
            console.warn('⚠️ ticket_fields에서 상태 레이블 추출 실패:', e);
          }
        }
        
        // ticket_fields에서 찾지 못한 경우 기본값
        if (!statusText) {
          statusText = '알 수 없음';
        }
        
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

      // 4. 요청자 (contact 데이터 사용)
      let requester = '👤 미확인';
      if (allTicketData?.contact?.contact?.name) {
        requester = `👤 ${allTicketData.contact.contact.name}`;
      } else if (allTicketData?.ticket?.ticket?.requester) {
        requester = `👤 ${allTicketData.ticket.ticket.requester}`;
      }
      row2Items.push(`<span class="meta-item">${requester}</span>`);

      // 5. 담당그룹 (group 데이터 사용)
      let group = '👥 CS팀';
      if (allTicketData?.group?.name) {
        group = `👥 ${allTicketData.group.name}`;
      } else if (allTicketData?.ticket?.ticket?.group?.name) {
        group = `👥 ${allTicketData.ticket.ticket.group.name}`;
      } else if (allTicketData?.ticket?.ticket?.group_name) {
        group = `👥 ${allTicketData.ticket.ticket.group_name}`;
      }
      row2Items.push(`<span class="meta-item">${group}</span>`);

      // 6. 담당자 (agent 데이터 사용)
      let agent = '👤 미배정';
      if (allTicketData?.agent?.contact?.name) {
        agent = `👤 ${allTicketData.agent.contact.name}`;
      } else if (allTicketData?.ticket?.ticket?.responder?.name) {
        agent = `👤 ${allTicketData.ticket.ticket.responder.name}`;
      } else if (allTicketData?.ticket?.ticket?.responder_name) {
        agent = `👤 ${allTicketData.ticket.ticket.responder_name}`;
      }
      row2Items.push(`<span class="meta-item">${agent}</span>`);

      // HTML 업데이트
      metaRow1.innerHTML = row1Items.join('');
      metaRow2.innerHTML = row2Items.join('');
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
      
      if (!tickets || !tickets.length) {
        console.log('⚠️ No similar tickets to render');
        container.innerHTML = `
          <div class="insight-panel">
            <div class="insight-title">🔍 유사 티켓 검색</div>
            <div class="insight-content">유사한 티켓이 없습니다.</div>
          </div>
        `;
        return;
      }

      console.log('✅ Rendering similar tickets:', tickets.length, '건');

      // 인사이트 패널 생성 (실제 데이터 구조에 맞게)
      const avgSimilarity = tickets.reduce((sum, t) => {
        const similarity = t.similarity_score || t.similarity || t.score || 0;
        const similarityPercent = similarity > 1 ? similarity : similarity * 100;
        return sum + similarityPercent;
      }, 0) / tickets.length;
      const resolvedCount = tickets.filter(t => {
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
      const activeCount = tickets.length - resolvedCount;
      
      const insightPanel = `
        <div class="insight-panel">
          <div class="insight-title">💡 자동 분석 결과</div>
          <div class="insight-content">
            🎯 평균 유사도: ${Math.round(avgSimilarity)}%<br>
            📊 상태 분포: ${resolvedCount}건 해결완료, ${activeCount}건 진행중<br>
            📋 검색된 티켓: ${tickets.length}건의 유사 사례 발견
          </div>
        </div>
      `;

      // 티켓 카드들 생성
      const ticketCards = tickets.map(ticket => {
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
        countElement.textContent = tickets.length;
      }
    },

    // KB 문서 렌더링
    renderKBDocuments(documents) {
      const container = document.getElementById('kbDocumentsContainer');
      if (!container) {
        console.error('❌ kbDocumentsContainer not found');
        return;
      }
      
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

      // 인사이트 패널 생성 (실제 데이터 구조에 맞게)
      const avgRelevance = documents.reduce((sum, d) => {
        const score = d.score || d.relevance || 0;
        // 0-1 범위의 소수점을 퍼센트로 변환
        return sum + (score * 100);
      }, 0) / documents.length;
      
      const insightPanel = `
        <div class="insight-panel">
          <div class="insight-title">📚 지식베이스 검색 결과</div>
          <div class="insight-content">
            🎯 관련도 높은 문서: ${documents.length}건<br>
            📊 평균 관련성: ${Math.round(avgRelevance)}%<br>
            📋 검색된 문서: 지식베이스에서 ${documents.length}건 발견
          </div>
        </div>
      `;

      // KB 문서 카드들 생성
      const docCards = documents.map((doc, index) => {
        console.log('📚 Processing document:', doc);
        
        // 실제 데이터 구조에 맞게 필드 매핑
        const docId = doc.id || 'KB-' + (index + 1);
        const docTitle = doc.title || '제목 없음';
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

      container.innerHTML = insightPanel + docCards;
      
      // 탭 카운트 업데이트
      const countElement = document.getElementById('kbDocumentsCount');
      if (countElement) {
        countElement.textContent = documents.length;
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

    // 캐시된 데이터로 다시 렌더링 (탭 전환 시 사용)
    refreshTabContent(tabName) {
      console.log('🔄 탭 컨텐츠 새로고침:', tabName);
      console.log('📊 현재 캐시 상태:', {
        similarTickets: App.state.cachedData.similarTickets.length,
        kbDocuments: App.state.cachedData.kbDocuments.length
      });
      
      switch(tabName) {
        case 'tickets':
          if (App.state.cachedData.similarTickets.length > 0) {
            console.log('📱 유사티켓 캐시 데이터 복원:', App.state.cachedData.similarTickets.length, '건');
            this.renderSimilarTickets(App.state.cachedData.similarTickets);
          } else {
            console.log('⚠️ 유사티켓 캐시 데이터 없음');
          }
          break;
          
        case 'kb':
          if (App.state.cachedData.kbDocuments.length > 0) {
            console.log('📚 KB문서 캐시 데이터 복원:', App.state.cachedData.kbDocuments.length, '건');
            this.renderKBDocuments(App.state.cachedData.kbDocuments);
          } else {
            console.log('⚠️ KB문서 캐시 데이터 없음');
          }
          break;
      }
    },

    // 채팅 메시지 추가
    addChatMessage(role, content, messageId) {
      const container = document.getElementById('chatMessages');
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
        const container = document.getElementById('chatMessages');
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
            hasCachedData: hasCachedData,
            timestamp: new Date().toISOString(),
            noBackendCall: true,
            usePreloadedData: true, // ✅ 미리 로드된 데이터 사용 플래그
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
            
            // 티켓 정보를 받았으면 추가 FDK 데이터 수집 시작
            this.collectAdditionalTicketData();
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
          currentData.similarTickets = data.content || data.similar_tickets || [];
          App.state.cachedData.similarTickets = currentData.similarTickets; // 캐시에 저장
          console.log('💾 유사티켓 캐시 저장 완료:', App.state.cachedData.similarTickets.length, '건');
          console.log('🎯 Processing similar tickets:', currentData.similarTickets.length, '건');
          this.renderSimilarTickets(currentData.similarTickets);
          break;
          
        case 'kb_documents':
          console.log('📦 KB documents data received:', data);
          currentData.kbDocuments = data.content || data.kb_documents || [];
          App.state.cachedData.kbDocuments = currentData.kbDocuments; // 캐시에 저장
          console.log('💾 KB문서 캐시 저장 완료:', App.state.cachedData.kbDocuments.length, '건');
          console.log('🎯 Processing KB documents:', currentData.kbDocuments.length, '건');
          this.renderKBDocuments(currentData.kbDocuments);
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
          
          // 완료 시점에서 헤더 업데이트 (감정 데이터가 있을 수 있음)
          if (App.state.cachedTicketInfo && App.state.cachedTicketInfo.lastUpdated) {
            // data.emotion_data가 있다면 감정 분석 결과로 사용
            const emotionData = data.emotion_data || data.emotion || null;
            if (emotionData) {
              console.log('😊 완료 시점 감정 데이터 업데이트:', emotionData);
              this.updateTicketHeader(App.state.cachedTicketInfo, emotionData);
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

    // 탭 전환
    handleTabSwitch(tabName) {
      console.log('🔄 탭 전환:', tabName);
      
      // 모든 탭 컨텐츠 숨기기
      document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
      });
      
      // 모든 탭 버튼 비활성화
      document.querySelectorAll('.tab-button').forEach(btn => {
        btn.classList.remove('active');
      });
      
      // 선택된 탭 활성화
      const selectedContent = document.getElementById(`${tabName}Tab`);
      const selectedButton = document.querySelector(`[data-tab="${tabName}"]`);
      
      if (selectedContent) selectedContent.classList.add('active');
      if (selectedButton) selectedButton.classList.add('active');
      
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
      await App.ui.collectAdditionalTicketData();
      
      // 백엔드에서 초기 데이터 로드 시작 (더 정확한 티켓 정보로 업데이트됨)
      console.log('🔄 백엔드 초기 데이터 로드 시작');
      App.api.loadInitialData(App.state.ticketId);
      
      // 🎯 상단 네비게이션 앱 아이콘 클릭 시 처리 (원본에서 이식)
      client.events.on('app.activated', async () => {
        try {
          console.log('📱 앱이 활성화됨 - 모달 표시 시작');
          
          // FDK context 가져오기 (안전한 호출)
          let ctx = null;
          try {
            ctx = await client.instance.context();
          } catch (contextError) {
            console.warn('⚠️ FDK context 가져오기 실패:', contextError.message);
            // context를 가져올 수 없는 경우 기본값으로 계속 진행
            ctx = { location: 'unknown' };
          }

          // 상단 네비게이션에서의 동작: 로딩 상태와 관계없이 즉시 모달 표시
          if (ctx.location === 'ticket_top_navigation') {
            // 현재 티켓 정보 가져오기 (안전한 FDK API 호출)
            let ticketData = null;
            let currentTicketId = null;
            
            try {
              ticketData = await client.data.get('ticket');
              currentTicketId = ticketData?.ticket?.id;
              console.log('✅ 앱 활성화 시 티켓 데이터 가져오기 성공');
            } catch (error) {
              console.warn('⚠️ 앱 활성화 시 티켓 데이터 가져오기 실패:', error.message);
              // EventAPI 오류가 발생해도 계속 진행
              currentTicketId = App.state.ticketId || 'unknown';
            }

            console.log('📊 상단 네비게이션에서 모달 열기 요청 - 티켓 ID:', currentTicketId);
            
            // 즉시 모달 표시
            await App.ui.showFDKModal(currentTicketId, true);
          } else {
            console.log('📱 예상치 못한 위치에서의 앱 활성화:', ctx.location);
            // 예상치 못한 위치에서의 호출도 모달 표시
            await App.ui.showFDKModal(App.state.ticketId, false);
          }
        } catch (err) {
          console.error('❌ app.activated 이벤트 처리 오류:', err);
          // 오류가 발생해도 기본 모달은 표시
          try {
            await App.ui.showFDKModal(App.state.ticketId, false);
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
      } catch (error) {
        console.error('초기 데이터 로드 실패:', error);
        App.ui.hideLoading();
        // 백엔드 연결 실패 시에도 기본 UI는 표시
        App.ui.showError('백엔드 서버 연결 실패. 일부 기능이 제한됩니다.');
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

// Top bar navigation 이벤트 처리용 전역 함수
window.showFDKModal = async function(ticketId) {
  console.log('📡 Top bar navigation에서 모달 열기 요청');
  if (App && App.ui && App.ui.showFDKModal) {
    await App.ui.showFDKModal(ticketId || App.state.ticketId);
  } else {
    console.error('❌ App.ui.showFDKModal 함수가 준비되지 않음');
  }
};

// DOM 로드 완료 시 앱 초기화
document.addEventListener('DOMContentLoaded', () => {
  // FDK가 로드되었는지 확인
  if (typeof app !== 'undefined') {
    App.init().catch(error => {
      console.error('앱 초기화 중 오류:', error);
      // FDK 없이도 기본 UI는 작동하도록 이벤트 리스너 설정
      App.setupEventListeners();
    });
  } else {
    console.warn('FDK가 로드되지 않았습니다. 기본 UI만 작동합니다.');
    // FDK 없이도 기본 UI는 작동하도록 이벤트 리스너 설정
    App.setupEventListeners();
  }
});