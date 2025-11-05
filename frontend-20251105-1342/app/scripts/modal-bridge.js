/**
 * Modal Bridge - 메인 페이지와 모달 iframe 간 통신
 * @version v0.0.26
 */

window.ModalBridge = {
  // 메인 페이지에서 실행 - 데이터를 iframe으로 전송 (새로운 캐시 시스템)
  sendDataToModal() {
    // 메인 페이지에서만 실행 가능
    if (window.Core?.state?.isModalView) {
      console.warn('⚠️ sendDataToModal은 메인 페이지에서만 실행 가능합니다.');
      return;
    }

    // 티켓 ID 획득
    const ticketId = window.Core?.state?.ticketId;
    if (!ticketId) {
      console.warn('⚠️ 티켓 ID를 찾을 수 없습니다');
      return;
    }

    // 새로운 캐시 시스템 사용
    if (!window.TicketCacheManager) {
      console.warn('⚠️ 캐시 매니저가 로드되지 않았습니다');
      return;
    }

    try {
      // 캐시 매니저 초기화 및 데이터 조회
      window.TicketCacheManager.initialize(ticketId);
      const cachedData = window.TicketCacheManager.getAllCachedData();

      const payload = {
        summary: cachedData.summary || null,
        similarTickets: cachedData.similarTickets || null,
        kbDocuments: cachedData.kbDocuments || null,
        metadata: cachedData.metadata || null,
        chatHistory: {
          rag: cachedData.chatRag?.messages || [],
          chat: cachedData.chatGeneral?.messages || []
        }
      };

      // 모달로 데이터 전송
      const iframes = document.querySelectorAll('iframe');
      iframes.forEach((iframe, index) => {
        try {
          if (iframe.src) {
            const iframeOrigin = new URL(iframe.src).origin;
            iframe.contentWindow.postMessage({
              type: 'TICKET_ANALYSIS_DATA',
              data: payload,
              source: 'main-page'
            }, iframeOrigin);
          }
        } catch (e) {
          console.error(`iframe ${index} 전송 실패:`, e);
        }
      });

      console.log('✅ 새로운 캐시 시스템으로 모달 데이터 전송 완료');
    } catch (e) {
      console.error('❌ 새로운 캐시 시스템 데이터 전송 실패:', e);
    }
  },

  // 메인 페이지에서 실행 - 스트리밍 상태를 iframe으로 전송
  sendStreamingStateToModal(streamingState) {
    // 메인 페이지에서만 실행 가능
    if (window.Core?.state?.isModalView) {
      console.warn('⚠️ sendStreamingStateToModal은 메인 페이지에서만 실행 가능합니다.');
      return;
    }

    // 모든 iframe에 스트리밍 상태 전송
    const iframes = document.querySelectorAll('iframe');
    iframes.forEach((iframe, index) => {
      try {
        if (iframe.src) {
          const iframeOrigin = new URL(iframe.src).origin;
          iframe.contentWindow.postMessage({
            type: 'STREAMING_STATE_UPDATE',
            state: streamingState,
            source: 'main-page',
            timestamp: Date.now()
          }, iframeOrigin);
        }
      } catch (e) {
        console.error(`iframe ${index} 스트리밍 상태 전송 실패:`, e);
      }
    });
  },

  // 메인 페이지에서 실행 - 부분 데이터를 iframe으로 전송 (점진적 업데이트)
  sendPartialDataToModal(dataType, content) {

    const iframes = document.querySelectorAll('iframe');
    iframes.forEach((iframe, index) => {
      try {
        if (iframe.src) {
          const iframeOrigin = new URL(iframe.src).origin;
          iframe.contentWindow.postMessage({
            type: 'PARTIAL_DATA_UPDATE',
            dataType: dataType,
            content: content,
            source: 'main-page',
            timestamp: Date.now()
          }, iframeOrigin);
        }
      } catch (e) {
        console.error(`iframe ${index} 부분 데이터 전송 실패:`, e);
      }
    });
  },

  // 모달 iframe에서 실행 - 데이터 수신
  setupReceiver() {

    window.addEventListener('message', (event) => {
      // 보안: origin 확인 (Freshdesk 도메인만 허용)
      if (!event.origin.includes('freshdesk.com')) {
        return;
      }


      // 메시지 타입별 처리
      switch (event.data.type) {
        case 'TICKET_ANALYSIS_DATA':
          this.handleCompleteData(event.data);
          break;

        case 'STREAMING_STATE_UPDATE':
          this.handleStreamingState(event.data);
          break;

        case 'PARTIAL_DATA_UPDATE':
          this.handlePartialData(event.data);
          break;

        default:
      }
    });
  },

  // 완전한 데이터 처리 (기존 로직)
  handleCompleteData(data) {

    // 통합 캐시에 저장
    window.Core.state.data = data.data;
    window.Core.saveModalData();

    // UI 렌더링 트리거
    if (window.TicketUI) {
      const ticketData = data.data;

      // 로딩 숨기기
      window.TicketUI.hideLoading();

      // 데이터 렌더링
      if (ticketData.summary) {
        // updateSummary 호출 비활성화 - API에서 이미 처리됨
        // window.TicketUI.updateSummary(ticketData.summary);
        // 요약 스켈레톤 제거
        window.TicketUI.hideSkeletonForSection('summary');
      }
      if (ticketData.similarTickets?.length > 0) {
        // SimilarTicketsManager를 통한 중앙화된 렌더링
        if (window.SimilarTicketsManager) {
          window.SimilarTicketsManager.renderTickets(ticketData.similarTickets, 'modal-bridge-init');
        } else {
          // 폴백: 직접 렌더링
          window.TicketUI.renderSimilarTickets(ticketData.similarTickets);
        }
        // 유사티켓 스켈레톤 제거
        window.TicketUI.hideSkeletonForSection('similar_tickets');
      }
      if (ticketData.kbDocuments?.length > 0) {
        window.TicketUI.renderKBDocuments(ticketData.kbDocuments);
        // KB 문서 스켈레톤 제거
        window.TicketUI.hideSkeletonForSection('kb_documents');
      }
      // 감정분석 데이터 처리 - HeaderManager 사용
      if (ticketData.emotionData || ticketData.emotion_analysis) {
        const emotionData = ticketData.emotionData || ticketData.emotion_analysis;
        // 감정 분석 직접 업데이트 (새 디자인)
        if (emotionData && emotionData.emotion && window.TicketUI) {
          window.TicketUI.updateEmotionElement(emotionData.emotion);
        } else if (window.TicketUI && window.TicketUI.updateTicketHeader) {
          // 폴백: 직접 업데이트 (안전성 체크 포함)
          window.TicketUI.updateTicketHeader(null, emotionData);
        }
      }

    } else {
      console.warn('⚠️ TicketUI가 아직 로드되지 않음');
    }
  },

  // 스트리밍 상태 처리
  handleStreamingState(data) {

    if (data.state.isStreaming && data.state.firstDataReceived) {
      // 첫 데이터가 도착했으면 즉시 로딩 오버레이 숨기고 스케일톤 표시
      if (window.TicketUI) {
        window.TicketUI.hideLoading();
        window.TicketUI.showSkeletonContent();
      }
    }

    // Core 상태 업데이트
    if (window.Core) {
      window.Core.state.streamingActive = data.state.isStreaming;
      window.Core.state.firstDataReceived = data.state.firstDataReceived;
    }
  },

  // 부분 데이터 처리 (점진적 업데이트)
  handlePartialData(data) {
    if (!this._validateTicketUI()) {
      return;
    }

    // 데이터 타입별 라우팅
    this._routePartialData(data);

    // 통합 캐시에 모든 데이터 저장
    window.Core.saveModalData();
  },

  /**
   * TicketUI 유효성 검사
   */
  _validateTicketUI() {
    if (!window.TicketUI) {
      console.warn('⚠️ TicketUI가 아직 로드되지 않음');
      return false;
    }
    return true;
  },

  /**
   * 부분 데이터 라우팅
   */
  _routePartialData(data) {
    switch (data.dataType) {
      case 'summary':
        this._handleSummaryData(data);
        break;

      case 'similar_tickets':
      case 'similarTickets':
        this._handleSimilarTicketsData(data);
        break;

      case 'kb_documents':
      case 'kbDocuments':
        this._handleKBDocumentsData(data);
        break;

      case 'emotion_analysis':
        this._handleEmotionAnalysisData(data);
        break;

      case 'headerInfo':
        this._handleHeaderInfoData(data);
        break;

      case 'ticket_summary_chunk':
        this._handleTicketSummaryChunk(data);
        break;

      case 'similar_ticket_summary_chunk':
        this._handleSimilarTicketSummaryChunk(data);
        break;

      case 'similar_ticket_summary_complete':
        this._handleSimilarTicketSummaryComplete(data);
        break;

      case 'ticket_summary_complete':
        this._handleTicketSummaryComplete(data);
        break;

      default:
        // 알 수 없는 데이터 타입
        break;
    }
  },

  /**
   * 요약 데이터 처리
   */
  _handleSummaryData(data) {
    window.Core.updateData('summary', data.content);
    window.TicketUI.hideSkeletonForSection('summary');
    window.Core.saveModalData();
  },

  /**
   * 유사 티켓 데이터 처리
   */
  _handleSimilarTicketsData(data) {
    window.Core.updateData('similarTickets', data.content);

    // 모달에서만 렌더링 (메인에서는 이미 렌더링됨)
    if (window.Core.state.isModalView) {
      this._renderSimilarTicketsInModal(data.content);
    }

    window.Core.saveModalData();
  },

  /**
   * 모달에서 유사 티켓 렌더링
   */
  _renderSimilarTicketsInModal(content) {
    if (window.SimilarTicketsManager) {
      window.SimilarTicketsManager.renderTickets(content, 'modal-bridge-partial');
    } else {
      window.TicketUI.renderSimilarTickets(content);
    }
    window.TicketUI.hideSkeletonForSection('similar_tickets');
  },

  /**
   * KB 문서 데이터 처리
   */
  _handleKBDocumentsData(data) {
    window.Core.updateData('kbDocuments', data.content);
    window.TicketUI.renderKBDocuments(data.content);
    window.TicketUI.hideSkeletonForSection('kb_documents');
    window.Core.saveModalData();
  },

  /**
   * 감정 분석 데이터 처리
   */
  _handleEmotionAnalysisData(data) {
    // 부분적 감정 분석 업데이트 (새 디자인)
    if (data.content && data.content.emotion && window.TicketUI) {
      window.TicketUI.updateEmotionElement(data.content.emotion);
    } else if (window.TicketUI && window.TicketUI.updateTicketHeader) {
      window.TicketUI.updateTicketHeader(null, data.content);
    }

    window.Core.updateData('emotionData', data.content);
    window.Core.saveModalData();
  },

  /**
   * 헤더 정보 데이터 처리 - FDK 데이터 보존 우선
   */
  _handleHeaderInfoData(data) {
    // 기존 FDK 헤더 데이터 확인 (덮어쓰기 방지)
    const existingHeaderData = window.Core.state.cachedTicketInfo;

    if (existingHeaderData && existingHeaderData.ticket && existingHeaderData.contact) {
      // FDK 데이터가 완전히 로드된 경우 백엔드 헤더 업데이트를 무시
      // 이미 완전한 FDK 헤더가 렌더링되어 있으므로 덮어쓰지 않음
      return;
    }

    // FDK 데이터가 없거나 불완전한 경우에만 백엔드 데이터 사용 (폴백)
    // 새 디자인에서는 헤더 정보 업데이트 불필요

    // Core에 저장 - FDK 데이터가 없는 경우에만
    window.Core.state.cachedTicketInfo = data.content;
    window.Core.saveModalData();
  },

  /**
   * 티켓 요약 청크 처리
   */
  _handleTicketSummaryChunk() {
    // Deprecated: 요약 스트림은 ApiService가 전담 처리
    return;
  },

  /**
   * 유사 티켓 요약 청크 처리
   */
  _handleSimilarTicketSummaryChunk(data) {
    const ticketId = data.ticket_id || data.ticketId;
    const chunk = data.content || '';
    const isFirst = data.is_first || false;

    if (ticketId && chunk) {
      this._updateSimilarTicketSummary(ticketId, chunk, true, isFirst, 'modal-bridge-summary-chunk');
    }
  },

  /**
   * 유사 티켓 요약 완료 처리
   */
  _handleSimilarTicketSummaryComplete(data) {
    const completeTicketId = data.ticket_id || data.ticketId;

    if (completeTicketId) {
      this._updateSimilarTicketSummary(completeTicketId, '', false, false, 'modal-bridge-summary-complete');
    }
  },

  /**
   * 티켓 요약 완료 처리
   */
  _handleTicketSummaryComplete(data) {
    if (data.content) {
      window.Core.updateData('summary', data.content);
      window.Core.saveModalData();
    }
  },

  /**
   * 유사 티켓 요약 업데이트 헬퍼
   */
  _updateSimilarTicketSummary(ticketId, content, isStreaming, isFirst, source) {
    if (window.SimilarTicketsManager) {
      window.SimilarTicketsManager.updateTicketSummary(ticketId, content, isStreaming, isFirst, source);
    } else if (window.TicketUI && window.TicketUI.updateSimilarTicketSummary) {
      window.TicketUI.updateSimilarTicketSummary(ticketId, content, isStreaming, isFirst);
    }
  },

  // iframe 크기 조정 요청
  requestResize() {

    // 부모 창에 크기 조정 요청
    window.parent.postMessage({
      type: 'RESIZE_IFRAME',
      width: '100%',
      height: '800px'
    }, '*');
  }
};

// 자동 설정
if (window !== window.top) {
  // iframe 내부에서 실행 중
  window.ModalBridge.setupReceiver();

  // DOM 로드 후 크기 조정 요청
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      window.ModalBridge.requestResize();

      // 부모 창에 iframe 준비 완료 알림
      window.parent.postMessage({
        type: 'IFRAME_READY',
        source: 'modal-iframe'
      }, '*');
    });
  } else {
    window.ModalBridge.requestResize();

    // 부모 창에 iframe 준비 완료 알림
    window.parent.postMessage({
      type: 'IFRAME_READY',
      source: 'modal-iframe'
    }, '*');
  }
} else {
  // 메인 페이지에서 실행 중

  // iframe 준비 완료 메시지 수신
  window.addEventListener('message', (event) => {
    if (event.data.type === 'IFRAME_READY' && event.data.source === 'modal-iframe') {

      // 데이터가 있으면 즉시 전송
      if (window.ModalBridge) {
        window.ModalBridge.sendDataToModal();

        // 현재 스트리밍 상태도 확인하여 전송
        if (window.Core?.state?.isLoading) {
          window.ModalBridge.sendStreamingStateToModal({
            isStreaming: true,
            firstDataReceived: window.Core?.state?.firstDataReceived || false
          });
        }
      }
    }
  });
}