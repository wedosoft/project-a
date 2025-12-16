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
    const maxAttempts = 30; // 60 → 30으로 줄임 (최대 대기 시간 단축)
    let consecutiveErrors = 0;
    
    // 지수 백오프: 처음엔 빠르게, 나중엔 느리게 폴링
    const getDelay = (attempt) => {
      if (attempt === 0) return 500;   // 첫 폴링: 0.5초
      if (attempt < 3) return 800;     // 2-3번째: 0.8초
      if (attempt < 6) return 1200;    // 4-6번째: 1.2초
      return 2000;                      // 7번째 이후: 2초
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
        if (data.type === 'answer_chunk' || data.type === 'chunk') {
          fullResponse += data.content || data.text || '';
          if (onChunk) {
            onChunk(fullResponse, sources, false);
          }
        } else if (data.type === 'retrieved_documents' || data.type === 'sources') {
          sources = data.documents || data.sources || [];
        } else if (data.type === 'filters') {
          filters = data.filters || [];
          filterConfidence = data.filterConfidence;
          knownContext = data.knownContext || {};
        } else if (data.type === 'complete') {
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
