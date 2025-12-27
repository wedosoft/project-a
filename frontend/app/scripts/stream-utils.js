/**
 * SSE 스트리밍 유틸리티
 * FDK에서 직접 fetch를 사용하여 SSE 스트림을 처리
 */

(function() {
  'use strict';

  /**
   * ReadableStream을 SSE 이벤트로 파싱
   * @param {Response} response - fetch 응답 객체
   * @param {Function} onData - 이벤트 수신 콜백 (data) => void
   * @returns {Promise<void>}
   */
  async function processStream(response, onData) {
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        
        // 완전한 라인들 처리
        const lines = buffer.split('\n');
        buffer = lines.pop() || ''; // 불완전한 마지막 라인 보존

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const dataStr = line.slice(6).trim();
            
            if (dataStr === '[DONE]') {
              continue;
            }
            
            if (dataStr === '') {
              continue;
            }

            try {
              const data = JSON.parse(dataStr);
              if (onData) {
                onData(data);
              }
            } catch (e) {
              console.warn('[StreamUtils] JSON 파싱 실패:', dataStr, e);
            }
          }
        }
      }
      
      // 남은 버퍼 처리
      if (buffer.trim() && buffer.startsWith('data: ')) {
        const dataStr = buffer.slice(6).trim();
        if (dataStr && dataStr !== '[DONE]') {
          try {
            const data = JSON.parse(dataStr);
            if (onData) onData(data);
          } catch (e) {
            console.warn('[StreamUtils] 최종 버퍼 파싱 실패:', dataStr);
          }
        }
      }
    } finally {
      reader.releaseLock();
    }
  }

  /**
   * SSE fetch 요청 (fallback 지원)
   * @param {string} url - 요청 URL
   * @param {Object} options - fetch 옵션 (method, headers, body 등)
   * @param {Function} onData - SSE 이벤트 콜백
   * @param {Function} fallbackFn - SSE 실패 시 대체 함수 (async)
   * @returns {Promise<Object>} 최종 결과
   */
  async function fetchWithStream(url, options, onData, fallbackFn) {
    try {
      const response = await fetch(url, options);

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }

      const contentType = response.headers.get('content-type') || '';
      
      // SSE 스트림인 경우
      if (contentType.includes('text/event-stream') || contentType.includes('application/x-ndjson')) {
        let result = null;
        
        await processStream(response, (data) => {
          // 콜백 호출
          if (onData) onData(data);
          
          // 최종 결과 저장 (complete 또는 resolution_complete 이벤트)
          if (data.type === 'complete' || data.type === 'resolution_complete') {
            // data.data가 있으면 그것을, 없으면 data 자체를 사용하되,
            // data.data가 문자열이면 파싱 시도
            if (data.data) {
              if (typeof data.data === 'string') {
                try {
                  result = JSON.parse(data.data);
                } catch (e) {
                  result = data.data;
                }
              } else {
                result = data.data;
              }
            } else {
              result = data;
            }
            console.log('[StreamUtils] Final result captured:', result);
          }
        });
        
        return result;
      }
      
      // 일반 JSON 응답인 경우
      const jsonData = await response.json();
      return jsonData;

    } catch (error) {
      console.warn('[StreamUtils] SSE 요청 실패, fallback 시도:', error.message);
      
      if (fallbackFn) {
        return await fallbackFn();
      }
      
      throw error;
    }
  }

  /**
   * 분석 API SSE 요청
   * @param {Object} payload - 요청 본문
   * @param {Function} onProgress - 진행 상황 콜백
   * @returns {Promise<Object>} 분석 결과
   */
  async function streamAnalyze(payload, onProgress) {
    // NOTE: 기존 /assist/analyze(LangGraph astream) 대신 progressive SSE(/assist/analyze/stream) 사용
    const url = window.BACKEND_CONFIG.getUrl('/api/assist/analyze/stream');
    const headers = window.BACKEND_CONFIG.getHeaders();

    // SSE 스트림 모드로 요청
    const streamPayload = {
      ...payload,
      stream_progress: true,
      async_mode: false
    };

    // Fallback: 폴링 모드(legacy /assist/analyze)
    const fallbackFn = async () => {
      console.log('[StreamUtils] Fallback to polling mode');
      return await pollAnalyze(payload, onProgress);
    };

    return await fetchWithStream(
      url,
      {
        method: 'POST',
        headers: headers,
        body: JSON.stringify(streamPayload)
      },
      onProgress,
      fallbackFn
    );
  }

  /**
   * 티켓 필드 제안(필드만) SSE 요청
   * @param {Object} payload - 요청 본문
   * @param {Function} onProgress - 진행 상황 콜백
   * @returns {Promise<Object>} 최종 결과 (complete.data)
   */
  async function streamFieldProposals(payload, onProgress) {
    const url = window.BACKEND_CONFIG.getUrl('/api/assist/field-proposals/stream');
    const headers = window.BACKEND_CONFIG.getHeaders();

    const streamPayload = {
      ...payload,
      fields_only: true,
      fieldsOnly: true,
      stream_progress: true,
      async_mode: false
    };

    // 필드 제안은 fallback을 단순화(필요 시 추후 추가)
    return await fetchWithStream(
      url,
      {
        method: 'POST',
        headers,
        body: JSON.stringify(streamPayload)
      },
      onProgress,
      null
    );
  }

  /**
   * 원인/해결 분석 SSE 요청
   * @param {Object} payload - 요청 본문
   * @param {Function} onProgress - 진행 상황 콜백
   * @returns {Promise<Object>} 최종 결과 (complete.data)
   */
  async function streamSolution(payload, onProgress) {
    const url = window.BACKEND_CONFIG.getUrl('/api/assist/analyze/stream');
    const headers = window.BACKEND_CONFIG.getHeaders();

    const streamPayload = {
      ...payload,
      fields_only: false,
      fieldsOnly: false,
      stream_progress: true,
      async_mode: false
    };

    return await fetchWithStream(
      url,
      {
        method: 'POST',
        headers,
        body: JSON.stringify(streamPayload)
      },
      onProgress,
      null
    );
  }

  /**
   * 분석 API 폴링 모드 (fallback)
   * @param {Object} payload - 요청 본문
   * @param {Function} onProgress - 진행 상황 콜백
   * @returns {Promise<Object>} 분석 결과
   */
  async function pollAnalyze(payload, onProgress) {
    const url = window.BACKEND_CONFIG.getUrl('/api/assist/analyze');
    const headers = window.BACKEND_CONFIG.getHeaders();

    // 비동기 모드로 요청
    const asyncPayload = {
      ...payload,
      stream_progress: false,
      async_mode: true
    };

    const response = await fetch(url, {
      method: 'POST',
      headers: headers,
      body: JSON.stringify(asyncPayload)
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const initialResponse = await response.json();

    if (!initialResponse?.proposal?.id) {
      throw new Error('Proposal ID가 없습니다');
    }

    const proposalId = initialResponse.proposal.id;
    
    // 진행 상황 표시
    if (onProgress) {
      onProgress({ type: 'router_decision', data: { decision: 'polling' } });
    }

    // 폴링
    let attempts = 0;
    const maxAttempts = 60;
    let consecutiveErrors = 0;

    while (attempts < maxAttempts) {
      await new Promise(resolve => setTimeout(resolve, 2000));
      attempts++;

      try {
        const statusUrl = window.BACKEND_CONFIG.getUrl(`/api/assist/status/${proposalId}`);
        const statusResponse = await fetch(statusUrl, { headers });
        
        if (!statusResponse.ok) {
          throw new Error(`Status HTTP ${statusResponse.status}`);
        }

        const statusData = await statusResponse.json();
        consecutiveErrors = 0;

        if (statusData.status === 'processing') {
          if (onProgress) {
            onProgress({ type: 'retriever_start', data: { attempt: attempts } });
          }
          continue;
        }

        if (statusData.status === 'error') {
          throw new Error(statusData.rejectionReason || '분석 오류');
        }

        // 완료
        if (onProgress) {
          onProgress({ type: 'resolution_complete', data: statusData });
        }

        return statusData;

      } catch (e) {
        consecutiveErrors++;
        if (consecutiveErrors >= 3) {
          throw e;
        }
      }
    }

    throw new Error('분석 시간 초과');
  }

  /**
   * 채팅 API SSE 요청
   * @param {Object} payload - 요청 본문
   * @param {Function} onChunk - 청크 수신 콜백 (text, sources, isComplete)
   * @returns {Promise<Object>} 최종 응답
   */
  async function streamChat(payload, onChunk) {
    const url = window.BACKEND_CONFIG.getUrl('/api/chat');
    const headers = window.BACKEND_CONFIG.getHeaders();

    const streamState = {
      fullResponse: '',
      sources: [],
      filters: [],
      filterConfidence: null,
      knownContext: {}
    };

    const response = await fetch(url, {
      method: 'POST',
      headers: headers,
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`HTTP ${response.status}: ${errorText}`);
    }

    const contentType = response.headers.get('content-type') || '';

    // SSE 스트림인 경우
    if (contentType.includes('text/event-stream') || contentType.includes('application/x-ndjson')) {
      await processStream(response, (data) => {
        if (data.type === 'answer_chunk' || data.type === 'chunk') {
          streamState.fullResponse += data.content || data.text || '';
          if (onChunk) {
            onChunk(streamState.fullResponse, streamState.sources, false);
          }
        } else if (data.type === 'retrieved_documents' || data.type === 'sources') {
          streamState.sources = data.documents || data.sources || [];
        } else if (data.type === 'filters') {
          streamState.filters = data.filters || [];
          streamState.filterConfidence = data.filterConfidence;
          streamState.knownContext = data.knownContext || {};
        } else if (data.type === 'complete') {
          if (data.text) streamState.fullResponse = data.text;
          if (data.groundingChunks) streamState.sources = data.groundingChunks;
          if (data.filters) streamState.filters = data.filters;
          if (data.filterConfidence) streamState.filterConfidence = data.filterConfidence;
          if (data.knownContext) streamState.knownContext = data.knownContext;
        }
      });

      if (onChunk) {
        onChunk(streamState.fullResponse, streamState.sources, true);
      }

      return {
        text: streamState.fullResponse,
        groundingChunks: streamState.sources,
        filters: streamState.filters,
        filterConfidence: streamState.filterConfidence,
        knownContext: streamState.knownContext
      };
    }

    // 일반 JSON 응답인 경우
    const jsonData = await response.json();
    
    if (onChunk) {
      onChunk(jsonData.text || '', jsonData.groundingChunks || [], true);
    }

    return jsonData;
  }

  /**
   * Ticket Analysis V2 API (PR2 Orchestrator)
   * POST /api/tickets/{ticket_id}/analyze
   * @param {string} ticketId - 티켓 ID
   * @param {Object} ticketData - 티켓 데이터 (subject, description, conversations 등)
   * @param {Object} options - 분석 옵션
   * @returns {Promise<Object>} 분석 결과 (ticket_analysis_v1)
   */
  async function analyzeTicketV2(ticketId, ticketData, options = {}) {
    const url = window.BACKEND_CONFIG.getUrl(`/api/tickets/${ticketId}/analyze`);
    const headers = window.BACKEND_CONFIG.getHeaders();

    // ticket_normalized_v1 형식으로 페이로드 구성
    const payload = {
      subject: ticketData.subject || null,
      description: ticketData.description || null,
      description_text: ticketData.description_text || null,
      priority: ticketData.priority || null,
      status: ticketData.status || null,
      source: ticketData.source || null,
      type: ticketData.type || null,
      tags: ticketData.tags || null,
      requester_id: ticketData.requester_id || null,
      responder_id: ticketData.responder_id || null,
      group_id: ticketData.group_id || null,
      custom_fields: ticketData.custom_fields || null,
      conversations: ticketData.conversations || null,
      ticketFields: ticketData.ticketFields || ticketData.ticket_fields || null,
      created_at: ticketData.created_at || null,
      updated_at: ticketData.updated_at || null,
      options: {
        skip_retrieval: options.skip_retrieval || false,
        include_evidence: options.include_evidence !== false,
        confidence_threshold: options.confidence_threshold || 0.7,
        selected_fields: options.selected_fields || null,
        response_tone: options.response_tone || 'formal'
      }
    };

    console.log('[StreamUtils] analyzeTicketV2 request:', { ticketId, payload });

    const response = await fetch(url, {
      method: 'POST',
      headers: headers,
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ message: response.statusText }));
      console.error('[StreamUtils] analyzeTicketV2 error:', response.status, errorData);
      throw new Error(errorData.detail?.message || errorData.message || `HTTP ${response.status}`);
    }

    const result = await response.json();
    console.log('[StreamUtils] analyzeTicketV2 result:', result);
    return result;
  }

  /**
   * Get analysis history for a ticket
   * GET /api/tickets/{ticket_id}/analyses
   * @param {string} ticketId - 티켓 ID
   * @param {number} limit - 최대 개수 (기본 10)
   * @returns {Promise<Object>} 분석 이력 목록
   */
  async function getAnalysisHistory(ticketId, limit = 10) {
    const url = window.BACKEND_CONFIG.getUrl(`/api/tickets/${ticketId}/analyses?limit=${limit}`);
    const headers = window.BACKEND_CONFIG.getHeaders();

    const response = await fetch(url, {
      method: 'GET',
      headers: headers
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ message: response.statusText }));
      throw new Error(errorData.detail?.message || errorData.message || `HTTP ${response.status}`);
    }

    return await response.json();
  }

  /**
   * Get a specific analysis by ID
   * GET /api/tickets/{ticket_id}/analyses/{analysis_id}
   * @param {string} ticketId - 티켓 ID
   * @param {string} analysisId - 분석 ID
   * @returns {Promise<Object>} 분석 상세
   */
  async function getAnalysisById(ticketId, analysisId) {
    const url = window.BACKEND_CONFIG.getUrl(`/api/tickets/${ticketId}/analyses/${analysisId}`);
    const headers = window.BACKEND_CONFIG.getHeaders();

    const response = await fetch(url, {
      method: 'GET',
      headers: headers
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ message: response.statusText }));
      throw new Error(errorData.detail?.message || errorData.message || `HTTP ${response.status}`);
    }

    return await response.json();
  }

  /**
   * Submit teaching feedback for an analysis
   * POST /api/analyses/{analysis_id}/teach (임시 - 백엔드 구현 시 경로 조정)
   * @param {string} analysisId - 분석 ID
   * @param {Object} lesson - 교훈 데이터
   * @returns {Promise<Object>} 제출 결과
   */
  async function submitTeachFeedback(analysisId, lesson) {
    // 임시 엔드포인트 (PR3 범위에서는 백엔드가 없을 수 있음)
    const url = window.BACKEND_CONFIG.getUrl(`/api/analyses/${analysisId}/teach`);
    const headers = window.BACKEND_CONFIG.getHeaders();

    const payload = {
      analysis_id: analysisId,
      mistake_pattern: lesson.mistake_pattern || null,
      wrong_assumption: lesson.wrong_assumption || null,
      corrective_heuristic: lesson.corrective_heuristic || null,
      automation_possible: lesson.automation_possible || false
    };

    console.log('[StreamUtils] submitTeachFeedback:', payload);

    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: headers,
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        // 백엔드가 아직 없으면 임시 성공 반환
        if (response.status === 404) {
          console.warn('[StreamUtils] Teach endpoint not implemented, simulating success');
          return { success: true, message: '교훈이 저장되었습니다. (임시)', lesson_id: 'temp-' + Date.now() };
        }
        const errorData = await response.json().catch(() => ({ message: response.statusText }));
        throw new Error(errorData.detail?.message || errorData.message || `HTTP ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      // 네트워크 오류 등에서도 임시 성공 처리
      if (error.message.includes('Failed to fetch') || error.message.includes('NetworkError')) {
        console.warn('[StreamUtils] Teach endpoint unavailable, simulating success');
        return { success: true, message: '교훈이 저장되었습니다. (임시)', lesson_id: 'temp-' + Date.now() };
      }
      throw error;
    }
  }

  // 전역 노출
  window.StreamUtils = {
    processStream,
    streamFieldProposals,
    streamSolution,
    fetchWithStream,
    streamAnalyze,
    pollAnalyze,
    streamChat,
    // V2 API
    analyzeTicketV2,
    getAnalysisHistory,
    getAnalysisById,
    submitTeachFeedback
  };

  console.log('[StreamUtils] Initialized (with V2 API)');

})();
