/**
 * API Service - 단순화된 백엔드 통신
 */

window.ApiService = {
  getHeaders() {
    const config = window.Core?.config || {};
    return {
      'Content-Type': 'application/json',
      'X-Tenant-ID': config.tenantId || '',
      'X-Platform': 'freshdesk',
      'X-Domain': config.domain || '',
      'X-API-Key': config.apiKey || '',
      'ngrok-skip-browser-warning': 'true',
    };
  },

  getBackendUrl(path) {
    if (!window.BACKEND_CONFIG?.getUrl) {
      console.error('백엔드 설정이 초기화되지 않았습니다. window.BACKEND_CONFIG.getUrl을 확인하세요.');
      throw new Error('Backend configuration not initialized');
    }
    return window.BACKEND_CONFIG.getUrl(path);
  },

  async processStream(response, onData) {
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let isProcessing = false;
    let firstEventDelivered = false;

    const processBuffer = () => {
      if (buffer.length === 0) {
        isProcessing = false;
        return;
      }

      const lines = buffer.split('\n');
      buffer = lines.pop() || ''; // 마지막 불완전한 라인은 남김

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const dataStr = line.slice(6);
          if (dataStr === '[DONE]') continue;
          try {
            const data = JSON.parse(dataStr);
            if (onData) onData(data);
          } catch (e) {
            console.error('❌ JSON 파싱 실패:', e, 'Raw data:', dataStr);
          }
        }
      }

      requestAnimationFrame(processBuffer);
    };

    const startProcessing = () => {
      if (!isProcessing) {
        isProcessing = true;
        requestAnimationFrame(processBuffer);
      }
    };

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) {
          if (buffer.length > 0) {
            startProcessing();
          }
          break;
        }
        const chunkText = decoder.decode(value, { stream: true });
        buffer += chunkText;

        // 첫 완전한 이벤트는 즉시 파싱해 전달 (rAF 지연 없음)
        if (!firstEventDelivered) {
          const newlineIdx = buffer.indexOf('\n');
          if (newlineIdx !== -1) {
            const line = buffer.slice(0, newlineIdx);
            const rest = buffer.slice(newlineIdx + 1);
            if (line.startsWith('data: ')) {
              const dataStr = line.slice(6);
              if (dataStr !== '[DONE]') {
                try {
                  const data = JSON.parse(dataStr);
                  if (onData) onData(data);
                } catch (e) {
                  console.error('❌ JSON 파싱 실패(첫 이벤트):', e, 'Raw data:', dataStr);
                }
              }
              firstEventDelivered = true;
              buffer = rest; // 나머지는 일반 배치 경로로
            }
          }
        }
        startProcessing();
      }
    } catch (error) {
      console.error('스트림 읽기 오류:', error);
    } finally {
      reader.releaseLock();
    }
  },

  async loadTicketData(ticketId) {
    if (!window.Core?.state?.isModalView) return;

    // 중복 호출 방지
    if (window.Core.state.isLoading) {
      console.warn('⚠️ 이미 데이터 로딩이 진행 중입니다.');
      return;
    }
    window.Core.setLoading(true);
    window.Core.state.isSummaryStreamingStarted = false; // 스트리밍 시작 플래그 초기화

    window.TicketUI?.hideLoading();

    // 캐시 데이터 존재 여부 확인 후 스켈레톤 표시 결정
    let hasCachedData = false;
    if (window.TicketCacheManager) {
      try {
        window.TicketCacheManager.initialize(ticketId);
        const cachedData = window.TicketCacheManager.getAllCachedData();
        hasCachedData = cachedData && Object.keys(cachedData).length > 0;
      } catch (e) {
        console.warn('⚠️ 캐시 확인 실패:', e);
      }
    }

    // 캐시된 데이터가 없는 경우에만 스켈레톤 표시
    if (!hasCachedData) {
      console.log('📱 캐시 없음 - 스켈레톤 표시');
      window.TicketUI?.showSkeletonForSection('summary');
      window.TicketUI?.showSkeletonForSection('similar_tickets');
      window.TicketUI?.showSkeletonForSection('kb_documents');
    } else {
      console.log('⚡ 캐시 있음 - 스켈레톤 건너뛰기');
    }

    try {
      const headers = this.getHeaders();

      // 두 API 호출을 병렬로 실행
      const summaryPromise = this.loadSummary(ticketId, headers, window.Core?.state?.summaryType || 'structural');
      const contextPromise = this.loadContext(ticketId, headers);

      // 두 작업이 모두 완료될 때까지 기다림
      await Promise.all([summaryPromise, contextPromise]);

    } catch (error) {
      console.error('❌ 데이터 로딩 중 오류 발생:', error);
      window.TicketUI?.showError('error_data_load_failed');
    } finally {
      // 모든 작업이 끝나면 로딩 상태 해제
      window.Core.setLoading(false);
      window.TicketUI?.hideAllSkeletons?.();
    }
  },

  async loadSummary(ticketId, headers, type) {
    const summaryType = type || (window.Core?.state?.summaryType) || 'structural';
    let url = this.getBackendUrl(`init/${ticketId}/summary`);
    // 요약 타입을 쿼리로 전달 (structural | temporal)
    url += `?type=${encodeURIComponent(summaryType)}`;

    // 캐시 데이터 확인 후 스켈레톤 표시 결정
    let hasCachedSummary = false;
    if (window.TicketCacheManager) {
      try {
        window.TicketCacheManager.initialize(ticketId);
        const cachedSummary = window.TicketCacheManager.getTicketSummary();
        hasCachedSummary = !!cachedSummary;
      } catch (e) {
        console.warn('⚠️ 요약 캐시 확인 실패:', e);
      }
    }

    // 캐시가 없는 경우에만 스켈레톤 표시
    if (!hasCachedSummary) {
      window.TicketUI?.showSkeletonForSection('summary');
    }

    const response = await fetch(url, { method: 'GET', headers });
    if (!response.ok) {
      window.TicketUI?.showErrorOnStage('summary', '요약 정보를 불러오지 못했습니다.');
      window.TicketUI?.hideSkeletonForSection('summary');
      throw new Error(`Summary 로드 실패: ${response.status}`);
    }
    await this.processStream(response, this._handleLoadTicketStreamData.bind(this));
  },

  _handleLoadTicketStreamData(data) {
    const handlers = {
      'ticket_summary_chunk': () => {
        // 첫 스트리밍 청크 도착 시 즉시 스켈레톤 제거
        if (!window.Core.state.isSummaryStreamingStarted) {
          window.TicketUI?.hideSkeletonForSection('summary');
          window.Core.state.isSummaryStreamingStarted = true;
        }
        window.TicketUI?.updateSummaryStream(data.content, false);
      },
      'ticket_summary_complete': () => {
        window.Core.updateData('summary', data.content);
        window.TicketUI?.updateSummary(data.content, data.rendering);

        // 새로운 캐시 시스템에 자동 저장
        if (window.TicketCacheManager && window.Core?.state?.ticketId) {
          try {
            window.TicketCacheManager.initialize(window.Core.state.ticketId);

            // 현재 요약 타입에 따라 올바른 필드에 저장
            const currentType = window.Core?.state?.summaryType || 'structural';
            const summaryData = {};

            // 캐시 매니저의 키 매핑 헬퍼 사용
            const mappedType = window.TicketCacheManager._mapSummaryType(currentType);
            summaryData[mappedType] = data.content;

            // 렌더링 데이터도 포함 (매핑된 타입으로 저장)
            if (data.rendering) {
              summaryData.rendering = summaryData.rendering || {};
              summaryData.rendering[mappedType] = data.rendering;
            }

            console.log(`💾 ${currentType} (${mappedType}) 요약을 캐시에 저장:`, summaryData);
            window.TicketCacheManager.saveTicketSummary(summaryData);
          } catch (e) {
            console.warn('⚠️ 요약 데이터 캐시 저장 실패:', e);
          }
        }
      },
      'emotion_analysis': () => window.TicketUI?.updateEmotionElement(data.content.emotion),
      // 백엔드가 첫 청크 도착을 progress 이벤트로 알릴 때 스켈레톤을 즉시 숨김
      'progress': () => {
        try {
          if (
            typeof data.message === 'string' &&
            data.message.includes('첫 요약 청크 도착') &&
            !window.Core.state.isSummaryStreamingStarted
          ) {
            window.TicketUI?.hideSkeletonForSection('summary');
            window.Core.state.isSummaryStreamingStarted = true;
          }
        } catch (e) {
          // no-op
        }
      },
      // 'complete' 이벤트는 loadTicketData의 finally 블록에서 중앙 관리되므로 제거
      'error': () => window.TicketUI?.showError(data.message || 'error_data_load_failed'),
    };
    const handler = handlers[data.type];
    if (handler) handler();
  },

  async loadContext(ticketId, headers) {
    // 캐시 데이터 확인 후 스켈레톤 표시 결정
    let hasCachedSimilarTickets = false;
    let hasCachedKBDocuments = false;

    if (window.TicketCacheManager) {
      try {
        window.TicketCacheManager.initialize(ticketId);
        const similarTickets = window.TicketCacheManager.getSimilarTickets();
        const kbDocuments = window.TicketCacheManager.getKBDocuments();
        hasCachedSimilarTickets = !!(similarTickets && similarTickets.length > 0);
        hasCachedKBDocuments = !!(kbDocuments && kbDocuments.length > 0);
      } catch (e) {
        console.warn('⚠️ 컨텍스트 캐시 확인 실패:', e);
      }
    }

    // 캐시가 없는 경우에만 스켈레톤 표시
    if (!hasCachedSimilarTickets) {
      window.TicketUI?.showSkeletonForSection('similar_tickets');
    }
    if (!hasCachedKBDocuments) {
      window.TicketUI?.showSkeletonForSection('kb_documents');
    }

    const url = this.getBackendUrl(`init/${ticketId}/context`);
    const response = await fetch(url, { method: 'GET', headers });
    if (!response.ok) {
      window.TicketUI?.showErrorOnStage('context', '관련 정보를 불러오지 못했습니다.');
      window.TicketUI?.hideSkeletonForSection('similar_tickets');
      window.TicketUI?.hideSkeletonForSection('kb_documents');
      throw new Error(`Context 로드 실패: ${response.status}`);
    }
    await this.processStream(response, (data) => {
      switch (data.type) {
        case 'search_metadata':
          if (data.content.min_quality_score) {
            window.Core.updateData('minQualityScore', data.content.min_quality_score);
          }
          if (data.content.similar_tickets) {
            // UI 렌더링
            window.TicketUI?.renderSimilarTickets(data.content.similar_tickets);
            // 새로운 캐시 시스템에 저장
            window.Core.updateData('similarTickets', data.content.similar_tickets);
          }
          if (data.content.kb_documents) {
            // UI 렌더링  
            window.TicketUI?.renderKBDocuments(data.content.kb_documents);
            // 새로운 캐시 시스템에 저장
            window.Core.updateData('kbDocuments', data.content.kb_documents);
          }
          break;
        case 'similar_ticket_summary_chunk':
          window.TicketUI?.updateSimilarTicketSummary(data.ticket_id, data.content, true, data.is_first);
          break;
        case 'similar_ticket_summary_error':
          // 서버가 LLM 실패를 명시적으로 알렸을 때 카드와 상세뷰에 오류 표시
          try {
            const errMsg = data.message || '요약을 생성할 수 없습니다.';
            // 마감 처리: 스트리밍이 아닌 최종 상태로 표시
            window.TicketUI?.updateSimilarTicketSummary(data.ticket_id, `[오류] ${errMsg}`, false, false);
            // 옵션: 스테이지 레벨 에러 강조
            window.TicketUI?.showErrorOnStage('similar', `[티켓 ${data.ticket_id}] ${errMsg}`);
          } catch (e) {
            console.error('Error handling similar_ticket_summary_error:', e);
          }
          break;
        case 'similar_ticket_summary_complete':
          window.TicketUI?.updateSimilarTicketSummary(data.ticket_id, null, false, false);
          break;
        case 'similar_ticket_full':
          if (window.Core?.state?.ticketSummaries) {
            window.Core.state.ticketSummaries[data.content.id] = data.content.summary;
          }
          break;
        case 'similar_tickets':
          // 백엔드에서 직접 similar_tickets 타입으로 보내는 경우
          if (data.content && Array.isArray(data.content)) {
            // UI 렌더링
            window.TicketUI?.renderSimilarTickets(data.content);
            // 새로운 캐시 시스템에 저장
            window.Core.updateData('similarTickets', data.content);
          }
          break;
      }
    });
  },

  // eslint-disable-next-line no-unused-vars
  async sendChatQuery(ticketId, query, mode = 'rag') {
    const requestBody = this._buildChatRequestBody(ticketId, query, mode);
    const response = await this._sendChatRequest(requestBody);
    return await this._processStreamingChatResponse(response);
  },

  _buildChatRequestBody(ticketId, query, mode) {
    const baseFields = this._buildBaseChatFields(ticketId, query, mode);
    const historyFields = this._buildChatHistoryFields();

    return {
      ...baseFields,
      ...historyFields,
      mode: mode,
    };
  },

  _buildBaseChatFields(ticketId, query, mode) {
    const config = window.Core?.config || {};
    return {
      query: query,
      stream_response: true,
      mode: mode,
      session_id: window.Core.state.sessionId || `session-${window.Core.state.ticketId}-${Date.now()}`,
      tenant_id: config.tenantId || '',
      platform: 'freshdesk',
      ticket_id: String(ticketId),
    };
  },

  _buildChatHistoryFields() {
    // 새 캐시 시스템의 createChatContext() 사용
    if (window.Core && typeof window.Core.createChatContext === 'function') {
      try {
        const context = window.Core.createChatContext();
        console.log('채팅 컨텍스트를 API 요청에 포함:', context);

        // RAG 모드와 Chat 모드에 따라 다른 구조로 전송
        const baseFields = {
          chat_history: context.chatHistory?.map(msg => ({ role: msg.role, content: msg.content })) || [],
          chat_mode: context.chatMode || 'rag',
          metadata: context.metadata || {}
        };

        // 🔍 디버깅: 백엔드로 전송되는 히스토리 확인
        console.log('🔍 [DEBUG] 백엔드로 전송되는 채팅 히스토리:', {
          mode: context.chatMode,
          historyCount: baseFields.chat_history.length,
          history: baseFields.chat_history,
          lastMessages: baseFields.chat_history.slice(-3) // 마지막 3개 메시지만 표시
        });

        if (context.chatMode === 'rag') {
          // RAG 모드: 풍부한 티켓 컨텍스트 제공
          return {
            ...baseFields,
            ticket_context: {
              ticket_number: context.ticketId,
              structural_summary: context.ticketSummary?.structural?.content || '',
              temporal_summary: context.ticketSummary?.temporal?.content || '',
              current_summary_type: context.ticketSummary?.current?.type || 'structural',
              subject: context.ticketInfo?.subject || context.metadata?.headerInfo?.ticket?.ticket?.subject || '',
              description_text: context.ticketInfo?.description_text || '',
              priority: context.ticketInfo?.priority || '',
              status: context.ticketInfo?.status || '',
              requester: context.ticketInfo?.requester || '',
              agent: context.ticketInfo?.agent || ''
            },
            similar_tickets: context.similarTickets || [],
            kb_documents: context.kbDocuments || []
          };
        } else {
          // Chat 모드: 기본 티켓 정보만 제공
          return {
            ...baseFields,
            ticket_context: {
              ticket_number: context.ticketId,
              summary: context.ticketSummary?.content || '',
              summary_type: context.ticketSummary?.type || 'structural',
              subject: context.ticketInfo?.subject || context.metadata?.headerInfo?.ticket?.ticket?.subject || '',
              description_text: context.ticketInfo?.description_text || '',
              priority: context.ticketInfo?.priority || '',
              status: context.ticketInfo?.status || ''
            }
          };
        }
      } catch (error) {
        console.error('채팅 컨텍스트 생성 실패, 레거시 방식 사용:', error);
      }
    }

    // 레거시 방식 (폴백)
    const currentHistory = window.Core?.getCurrentChatHistory() || [];
    const recentHistory = currentHistory.slice(-10);
    return {
      chat_history: recentHistory.map(msg => ({ role: msg.role, content: msg.content })),
    };
  },

  async _sendChatRequest(requestBody) {
    const url = this.getBackendUrl('query');
    const headers = this.getHeaders();
    const response = await fetch(url, {
      method: 'POST',
      headers: headers,
      body: JSON.stringify(requestBody),
    });
    if (!response.ok) {
      const errorText = await response.text();
      console.error('❌ 백엔드 응답 오류:', { status: response.status, body: errorText });
      throw new Error(`Query error: ${response.status} - ${errorText}`);
    }
    return response;
  },

  async _processStreamingChatResponse(response) {
    const streamState = { fullResponse: '', searchResults: null, isFirstMessage: true, messageId: null };
    await this.processStream(response, (data) => {
      if (data.type === 'retrieved_documents') {
        streamState.searchResults = data.documents;
      } else if (data.type === 'answer_chunk') {
        if (streamState.isFirstMessage) {
          window.ChatUI?.hideTypingIndicator();
          streamState.messageId = window.ChatUI?.addMessage('', 'assistant');
          streamState.isFirstMessage = false;
        }
        if (data.content) {
          streamState.fullResponse += data.content;
        }
        if (streamState.messageId) {
          window.ChatUI?.updateStreamingMessage(streamState.fullResponse, streamState.searchResults);
        }
      } else if (data.type === 'error') {
        window.ChatUI?.hideTypingIndicator();
        const errorMessageTemplate = window.t ? window.t('error_chat_generic') : "Sorry, an error occurred. (Error: {message})";
        const errorMessage = errorMessageTemplate.replace('{message}', data.message || 'Unknown');

        if (streamState.isFirstMessage) {
          window.ChatUI?.addMessage(errorMessage, 'assistant');
        } else if (streamState.messageId) {
          window.ChatUI?.updateMessage(streamState.messageId, errorMessage, true);
        }
      } else if (data.type === 'complete') {
        window.ChatUI?.hideTypingIndicator();
        if (streamState.messageId) {
          window.ChatUI?.finalizeMessage(streamState.messageId);
        }
      }
    });
    return streamState.fullResponse;
  },
};

window.API = window.ApiService;
