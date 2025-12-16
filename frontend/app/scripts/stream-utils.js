/**
 * SSE 스트리밍 유틸리티
 * FDK에서 직접 fetch를 사용하여 SSE 스트림을 처리
 */

(function() {
  'use strict';

  // === 설정 상수 ===
  const CONFIG = {
    // SSE 요청 타임아웃 (밀리초)
    SSE_TIMEOUT_MS: 30000,
    
    // 폴링 설정 (단계별 백오프 - 초기엔 빠르게, 점진적으로 느리게)
    POLLING: {
      MAX_ATTEMPTS: 30,           // 최대 폴링 시도 횟수
      INITIAL_DELAY_MS: 500,      // 첫 폴링 대기 시간
      EARLY_DELAY_MS: 800,        // 초기(2-3회) 폴링 대기 시간
      MID_DELAY_MS: 1200,         // 중기(4-6회) 폴링 대기 시간
      DEFAULT_DELAY_MS: 2000,     // 이후 기본 폴링 대기 시간
      EARLY_THRESHOLD: 3,         // 초기 단계 임계값
      MID_THRESHOLD: 6            // 중기 단계 임계값
    }
  };

  // SSE 스트림 이벤트 타입
  const STREAM_EVENT_TYPES = {
    COMPLETE: 'complete',
    RESOLUTION_COMPLETE: 'resolution_complete',
    ANALYSIS_RESULT: 'analysis_result',
    ANSWER_CHUNK: 'answer_chunk',
    CHUNK: 'chunk',
    RETRIEVED_DOCUMENTS: 'retrieved_documents',
    SOURCES: 'sources',
    FILTERS: 'filters'
  };

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
    // 타임아웃 추가
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), CONFIG.SSE_TIMEOUT_MS);
    
    try {
      const response = await fetch(url, {
        ...options,
        signal: controller.signal
      });
      
      clearTimeout(timeoutId);

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
          
          // 최종 결과 저장 (여러 이벤트 타입 지원)
          const completionEvents = [
            STREAM_EVENT_TYPES.COMPLETE,
            STREAM_EVENT_TYPES.RESOLUTION_COMPLETE,
            STREAM_EVENT_TYPES.ANALYSIS_RESULT
          ];
          
          if (completionEvents.includes(data.type)) {
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
            console.log('[StreamUtils] Final result captured from', data.type, ':', result);
          }
        });
        
        return result;
      }
      
      // 일반 JSON 응답인 경우
      const jsonData = await response.json();
      return jsonData;

    } catch (error) {
      clearTimeout(timeoutId);
      
      // AbortError는 타임아웃으로 처리
      const isTimeout = error.name === 'AbortError';
      const errorMsg = isTimeout ? 'Request timeout (30s)' : error.message;
      
      console.warn(`[StreamUtils] SSE 요청 실패${isTimeout ? ' (타임아웃)' : ''}, fallback 시도:`, errorMsg);
      
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
    const startTime = Date.now();
    const url = window.BACKEND_CONFIG.getUrl('/api/assist/analyze');
    const headers = window.BACKEND_CONFIG.getHeaders();

    // SSE 스트림 모드로 요청
    const streamPayload = {
      ...payload,
      stream_progress: true,
      async_mode: false
    };

    // Fallback: 폴링 모드
    const fallbackFn = async () => {
      const elapsed = Date.now() - startTime;
      console.log(`[StreamUtils] SSE failed after ${elapsed}ms, fallback to polling mode`);
      return await pollAnalyze(payload, onProgress);
    };

    const result = await fetchWithStream(
      url,
      {
        method: 'POST',
        headers: headers,
        body: JSON.stringify(streamPayload)
      },
      onProgress,
      fallbackFn
    );
    
    const totalTime = Date.now() - startTime;
    console.log(`[StreamUtils] Analysis completed in ${totalTime}ms`);
    
    return result;
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

    // 폴링 (지수 백오프 적용으로 초기 응답 시간 단축)
    let attempts = 0;
    const maxAttempts = CONFIG.POLLING.MAX_ATTEMPTS;
    let consecutiveErrors = 0;
    
    // 지수 백오프: 처음엔 빠르게, 나중엔 느리게 폴링
    const getDelay = (attempt) => {
      if (attempt === 0) return CONFIG.POLLING.INITIAL_DELAY_MS;
      if (attempt < CONFIG.POLLING.EARLY_THRESHOLD) return CONFIG.POLLING.EARLY_DELAY_MS;
      if (attempt < CONFIG.POLLING.MID_THRESHOLD) return CONFIG.POLLING.MID_DELAY_MS;
      return CONFIG.POLLING.DEFAULT_DELAY_MS;
    };

    while (attempts < maxAttempts) {
      // 지수 백오프 적용
      const delay = getDelay(attempts);
      await new Promise(resolve => setTimeout(resolve, delay));
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

        console.log(`[PollAnalyze] Completed after ${attempts} attempts`);
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

    let fullResponse = '';
    let sources = [];
    let filters = [];
    let filterConfidence = null;
    let knownContext = {};

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
        if (data.type === STREAM_EVENT_TYPES.ANSWER_CHUNK || data.type === STREAM_EVENT_TYPES.CHUNK) {
          fullResponse += data.content || data.text || '';
          if (onChunk) {
            onChunk(fullResponse, sources, false);
          }
        } else if (data.type === STREAM_EVENT_TYPES.RETRIEVED_DOCUMENTS || data.type === STREAM_EVENT_TYPES.SOURCES) {
          sources = data.documents || data.sources || [];
        } else if (data.type === STREAM_EVENT_TYPES.FILTERS) {
          filters = data.filters || [];
          filterConfidence = data.filterConfidence;
          knownContext = data.knownContext || {};
        } else if (data.type === STREAM_EVENT_TYPES.COMPLETE) {
          if (data.text) fullResponse = data.text;
          if (data.groundingChunks) sources = data.groundingChunks;
          if (data.filters) filters = data.filters;
          if (data.filterConfidence) filterConfidence = data.filterConfidence;
          if (data.knownContext) knownContext = data.knownContext;
        }
      });

      if (onChunk) {
        onChunk(fullResponse, sources, true);
      }

      return {
        text: fullResponse,
        groundingChunks: sources,
        filters: filters,
        filterConfidence: filterConfidence,
        knownContext: knownContext
      };
    }

    // 일반 JSON 응답인 경우
    const jsonData = await response.json();
    
    if (onChunk) {
      onChunk(jsonData.text || '', jsonData.groundingChunks || [], true);
    }

    return jsonData;
  }

  // 전역 노출
  window.StreamUtils = {
    processStream,
    fetchWithStream,
    streamAnalyze,
    pollAnalyze,
    streamChat
  };

  console.log('[StreamUtils] Initialized');

})();
