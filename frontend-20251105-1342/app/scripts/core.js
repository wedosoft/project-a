/**
 * Core Module - 단순화된 상태 및 설정 관리
 */

// Core 모듈 로드 (IIFE 패턴으로 중복 로딩 방지)

(function () {
  'use strict';

  // 중복 로딩 방지 가드
  if (window.Core && window.Core._initialized) {
    return;
  }

  window.Core = {
    // 상태 관리 (단순 객체)
    state: {
      client: null,      // FDK 클라이언트
      ticketId: null,    // 현재 티켓 ID
      isLoading: false,  // 로딩 상태
      isModalView: false,// 모달 뷰 여부
      initialContentShown: false, // 첫 번째 콘텐츠(스케일톤) 표시 여부
      data: {            // 데이터 캐시
        summary: '',
        similarTickets: [],
        kbDocuments: [],
        emotionData: null,         // 감정 분석 데이터
        summary_structural: null,  // 구조분석 캐시
        summary_temporal: null,    // 시간분석 캐시
        rendering_structural: null, // 구조분석 렌더링 정보
        rendering_temporal: null,    // 시간분석 렌더링 정보
        minQualityScore: null      // 백엔드에서 받은 최소 품질 점수
      },
      summaryType: 'structural', // 현재 요약 타입 (structural | temporal)
      chatHistory: {     // 모드별 채팅 히스토리
        rag: [],        // RAG 모드 전용 히스토리
        chat: []        // 자유대화 모드 전용 히스토리
      },
      chatMode: 'rag', // 채팅 모드 (rag: RAG 검색, chat: 자유 대화)
      sessionId: null,   // 대화 세션 ID (대화 추적용)
      cachedTicketInfo: null, // 티켓 헤더 정보 캐시
      ticketData: null,  // 전체 티켓 데이터 캐시 (추천 답변용)
      conversations: null, // 대화 내역 캐시
      progress: {
        current: 0,      // 현재 진행률 (0-100)
        stage: 'idle'    // 현재 단계
      },
      streamingCompleted: false, // 스트리밍 완료 상태
      // 상태 보존용 데이터
      savedState: {
        activeTab: 'tickets',
        scrollPosition: 0,
        chatScrollPosition: 0,
        summaryCollapsed: false,
        ticketDetailView: null,
        chatInputValue: ''
      },
      // DOM 쿼리 캐싱용 데이터 (성능 최적화)
      uiCache: {
        activeTab: 'tickets',
        scrollPosition: 0,
        chatScrollPosition: 0,
        summaryCollapsed: false,
        chatInputValue: '',
        lastCacheUpdate: 0
      }
    },

    // 설정 관리
    config: {
      domain: '',        // freshdesk_domain
      apiKey: '',        // freshdesk_api_key
      tenantId: ''       // domain에서 추출
    },

    /**
     * 초기화 (FDK 없이도 작동)
     */
    init(client = null) {
      if (client) {
        return this.initialize(client);
      }

      // FDK 없이는 초기화하지 않음
      this.state.client = null;
      this.state.ticketId = null;

      // 설정도 비워둠 (FDK 없이는 사용 불가)
      this.config.domain = '';
      this.config.tenantId = '';
      this.config.apiKey = '';
    },

    /**
     * 초기화 (FDK 포함)
     */
    async initialize(client) {
      this.state.client = client;

      await this._initializeTicketData(client);
      await this._initializeConfiguration(client);

      return this.state;
    },

    /**
     * 티켓 데이터 초기화
     */
    async _initializeTicketData(client) {
      try {
        const ticketData = await client.data.get('ticket');
        this._extractTicketId(ticketData);
        this._setupSession();
        this._renderChatHistory();
      } catch (e) {
        console.error('❌ 티켓 ID 가져오기 실패:', e);
        throw new Error('티켓 정보 로드 실패: ' + e.message);
      }
    },

    /**
     * 티켓 ID 추출
     */
    _extractTicketId(ticketData) {
      if (ticketData && ticketData.ticket && ticketData.ticket.id) {
        this.state.ticketId = ticketData.ticket.id;
      } else if (ticketData && ticketData.id) {
        this.state.ticketId = ticketData.id;
      } else {
        console.error('❌ 티켓 데이터 구조 오류:', ticketData);
        throw new Error('티켓 정보를 찾을 수 없습니다');
      }
    },

    /**
     * 세션 설정
     */
    _setupSession() {
      this.updateSessionId();

      // 새로운 캐시 시스템으로 데이터 복원
      if (window.TicketCacheManager && this.state.ticketId) {
        try {
          window.TicketCacheManager.initialize(this.state.ticketId);

          // 캐시된 데이터 복원
          const hasRestoredData = this._restoreFromNewCacheSystem();

          if (hasRestoredData) {
            console.log('✅ 캐시된 데이터로 세션 복원 완료');

            // 캐시된 데이터로 UI 즉시 렌더링
            setTimeout(() => {
              if (window.TicketUI && typeof window.TicketUI._renderFromNewCacheSystem === 'function') {
                // 캐시된 메타데이터 직접 조회
                const cachedMetadata = window.TicketCacheManager.getTicketMetadata() || {};

                const allData = {
                  summary: this.state.data.summary,
                  similarTickets: this.state.data.similarTickets,
                  kbDocuments: this.state.data.kbDocuments,
                  metadata: {
                    currentSummaryType: cachedMetadata.currentSummaryType || this.state.summaryType,
                    chatMode: cachedMetadata.chatMode || this.state.chatMode,
                    emotion: cachedMetadata.emotion || this.state.emotion
                  }
                };

                console.log('🔍 세션 복원 시 전달되는 메타데이터:', allData.metadata);
                window.TicketUI._renderFromNewCacheSystem(allData);
                console.log('✅ 캐시된 데이터로 UI 렌더링 완료');
              }
            }, 50);
          }

        } catch (e) {
          console.warn('⚠️ 새 캐시 시스템 세션 복원 실패:', e);
        }
      }

      // 세션 로드 후 토글 UI 초기화
      setTimeout(() => {
        if (window.updateToggleUI) {
          window.updateToggleUI();
        }
        if (window.updateChatToggleUI) {
          window.updateChatToggleUI();
        }
      }, 100);
    },

    /**
     * 채팅 히스토리 렌더링
     */
    _renderChatHistory() {
      if (window.ChatUI && typeof window.ChatUI.renderChatHistory === 'function') {
        window.ChatUI.renderChatHistory();
      }
    },

    /**
     * 설정 초기화
     */
    async _initializeConfiguration(client) {
      try {
        const iparams = await client.iparams.get();
        this._loadBasicConfig(iparams);

        if (!this.config.apiKey) {
          await this._loadSecureConfig(client);
        }
      } catch (e) {
        console.error('❌ iparams 로드 실패:', e);
      }
    },

    /**
     * 기본 설정 로드
     */
    _loadBasicConfig(iparams) {
      const apiKey = iparams?.freshdesk_api_key;
      const domain = iparams?.freshdesk_domain;

      this.config.domain = domain || '';
      this.config.apiKey = apiKey || '';
      this.config.tenantId = this.extractTenantId(this.config.domain);
    },

    /**
     * 보안 설정 로드
     */
    async _loadSecureConfig(client) {
      try {
        const data = await client.request.invoke('getSecureParams', {});
        const responseData = data?.response || data;

        this._processSecureResponse(responseData);
      } catch (error) {
        console.error('❌ 서버리스 함수 호출 실패:', error);
      }
    },

    /**
     * 보안 응답 처리
     */
    _processSecureResponse(responseData) {
      if (responseData && responseData.apiKey) {
        this.config.apiKey = responseData.apiKey;
        this.config.domain = responseData.domain || this.config.domain;
        this.config.tenantId = this.extractTenantId(this.config.domain);
      } else if (responseData && responseData.error) {
        console.error('❌ 서버리스 함수 오류:', responseData.error);
      } else {
        console.error('❌ 보안 파라미터를 가져올 수 없습니다');
      }
    },

    /**
     * 테넌트 ID 추출
     */
    extractTenantId(domain) {
      if (!domain) return '';
      return domain.split('.')[0];
    },

    /**
     * 상태 업데이트
     */
    updateState(updates) {
      Object.assign(this.state, updates);
    },

    /**
     * 데이터 업데이트 (새로운 캐시 시스템과 연동)
     */
    updateData(key, value) {
      if (key in this.state.data) {
        this.state.data[key] = value;

        // 새로운 캐시 시스템에 자동 저장
        if (window.TicketCacheManager && this.state.ticketId) {
          try {
            window.TicketCacheManager.initialize(this.state.ticketId);

            switch (key) {
              case 'summary':
                // 현재 요약 타입으로 저장
                const summaryType = this.state.summaryType || 'structural';

                // 기존 캐시된 요약 데이터 조회 (다른 타입의 요약 보존)
                const existingSummaries = window.TicketCacheManager.getTicketSummary() || {};

                // temporal → chronological 매핑
                const mappedType = summaryType === 'temporal' ? 'chronological' : summaryType;

                // 특정 타입의 요약으로 저장
                const summaryData = {
                  structural: existingSummaries.structural || '',
                  chronological: existingSummaries.chronological || '',
                  emotionData: existingSummaries.emotionData || null,
                  rendering: existingSummaries.rendering || {}
                };

                // 현재 타입의 요약 업데이트
                summaryData[mappedType] = value;

                // 렌더링 데이터도 함께 저장 (있는 경우)
                const renderingKey = `rendering_${summaryType}`;
                if (this.state.data[renderingKey]) {
                  summaryData.rendering[summaryType] = this.state.data[renderingKey];
                }

                console.log(`💾 ${summaryType} (${mappedType}) 요약을 캐시에 저장:`, {
                  structural: !!summaryData.structural,
                  chronological: !!summaryData.chronological,
                  rendering: Object.keys(summaryData.rendering)
                });

                window.TicketCacheManager.saveTicketSummary(summaryData);
                break;
              case 'similarTickets':
                window.TicketCacheManager.saveSimilarTickets(value);
                break;
              case 'kbDocuments':
                window.TicketCacheManager.saveKBDocuments(value);
                break;
              case 'emotionData':
              case 'minQualityScore':
                // 메타데이터로 저장
                const currentMeta = window.TicketCacheManager.getTicketMetadata() || {};
                currentMeta[key] = value;
                window.TicketCacheManager.saveTicketMetadata(currentMeta);
                break;
            }
          } catch (e) {
            console.warn('⚠️ 데이터 업데이트 시 캐시 저장 실패:', key, e);
          }
        }
      }
    },

    /**
     * 로딩 상태 설정
     */
    setLoading(isLoading) {
      this.state.isLoading = isLoading;
      if (!isLoading) {
        // 로딩이 끝나면 진행률도 리셋
        this.state.progress.current = 0;
        this.state.progress.stage = 'idle';
        // 스트리밍 완료 상태 설정
        this.state.streamingCompleted = true;
      }
    },

    /**
     * 스트리밍 시작 시 완료 상태 리셋
     */
    resetStreamingState() {
      this.state.streamingCompleted = false;
    },

    /**
     * 채팅 히스토리 추가 (모드별 분리)
     */
    addChatHistory(role, content) {
      const message = {
        role: role,
        content: content,
        timestamp: Date.now()
      };

      const currentMode = this.state.chatMode;

      // 현재 모드의 히스토리에만 추가
      if (!this.state.chatHistory[currentMode]) {
        this.state.chatHistory[currentMode] = [];
      }

      this.state.chatHistory[currentMode].push(message);

      // 각 모드별로 최대 50개로 제한
      if (this.state.chatHistory[currentMode].length > 50) {
        this.state.chatHistory[currentMode] = this.state.chatHistory[currentMode].slice(-50);
      }

      // 세션 저장 최적화 - 채팅 히스토리는 적절한 시점에만 저장
      this._debouncedSaveChatHistory();
    },

    /**
     * 데이터 초기화
     */
    resetData() {
      this.state.data = {
        summary: '',
        similarTickets: [],
        kbDocuments: [],
        minQualityScore: null,
        emotionData: null
      };
      this.state.chatHistory = {
        rag: [],
        chat: []
      };
      // 세션 ID는 유지 (같은 대화 세션 내에서)
    },

    /**
     * 새 캐시 시스템에서 채팅 히스토리 저장 (디바운스)
     */
    _debouncedSaveChatHistory() {
      // 기존 타이머 클리어
      if (this._saveChatTimer) {
        clearTimeout(this._saveChatTimer);
      }

      // 300ms 후 저장 (빈번한 저장 방지)
      this._saveChatTimer = setTimeout(() => {
        if (window.TicketCacheManager && this.state.ticketId) {
          try {
            window.TicketCacheManager.initialize(this.state.ticketId);
            window.TicketCacheManager.saveChatHistory(this.state.chatHistory);
            console.log('채팅 히스토리 캐시에 저장됨:', Object.keys(this.state.chatHistory));
          } catch (e) {
            console.warn('⚠️ 채팅 히스토리 저장 실패:', e);
          }
        }
      }, 300);
    },

    /**
     * 새로운 캐시 시스템으로 이관됨
     * TODO: TicketCacheManager 통합 완료 후 제거
     */
    saveChatHistoryPersistent() {
      // 새로운 캐시 매니저로 이관 예정
      if (window.TicketCacheManager && this.state.ticketId) {
        try {
          window.TicketCacheManager.initialize(this.state.ticketId);
          window.TicketCacheManager.saveChatHistory(this.state.chatHistory);
        } catch (e) {
          console.warn('⚠️ 새 캐시 시스템 채팅 저장 실패:', e);
        }
      }
    },

    /**
     * 채팅 메시지 총 개수 계산
     */
    _getChatMessageCount() {
      const ragCount = this.state.chatHistory.rag?.length || 0;
      const chatCount = this.state.chatHistory.chat?.length || 0;
      return ragCount + chatCount;
    },

    /**
     * 페이지 떠날 때 정리: 새 캐시 시스템으로 채팅 히스토리 보존
     */
    cleanupOnPageLeave() {
      if (!this.state.ticketId) return;

      // 새로운 캐시 매니저로 채팅 히스토리 저장
      if (window.TicketCacheManager) {
        try {
          window.TicketCacheManager.initialize(this.state.ticketId);
          window.TicketCacheManager.saveChatHistory(this.state.chatHistory);
        } catch (e) {
          console.warn('⚠️ 새 캐시 시스템 페이지 종료 저장 실패:', e);
        }
      }
    },

    /**
     * 새로운 캐시 시스템으로 이관됨
     * TODO: TicketCacheManager 통합 완료 후 제거
     */
    clearChatHistoryPersistent() {
      if (!this.state.ticketId) return;

      // 새로운 캐시 매니저로 이관
      if (window.TicketCacheManager) {
        try {
          window.TicketCacheManager.initialize(this.state.ticketId);
          window.TicketCacheManager.clearChatHistory();
        } catch (e) {
          console.warn('⚠️ 새 캐시 시스템 채팅 삭제 실패:', e);
        }
      }

      // 메모리 상의 채팅 히스토리도 초기화
      this.state.chatHistory = {
        rag: [],
        chat: []
      };

      // 채팅 UI 새로고침
      this._renderChatHistory();

      return true;
    },

    /**
     * 새로운 캐시 시스템으로 이관됨
     * TODO: TicketCacheManager 통합 완료 후 제거
     */
    getChatHistoryStats() {
      if (!this.state.ticketId) return null;

      // 새로운 캐시 매니저 사용
      if (window.TicketCacheManager) {
        try {
          window.TicketCacheManager.initialize(this.state.ticketId);
          return window.TicketCacheManager.getChatHistoryStats();
        } catch (e) {
          console.warn('⚠️ 새 캐시 시스템 통계 조회 실패:', e);
        }
      }

      // 기본 통계
      const ragCount = this.state.chatHistory.rag?.length || 0;
      const chatCount = this.state.chatHistory.chat?.length || 0;
      const totalCount = ragCount + chatCount;

      return {
        current: {
          rag: ragCount,
          chat: chatCount,
          total: totalCount
        },
        ticketId: this.state.ticketId
      };
    },

    /**
     * 새로운 캐시 시스템을 사용한 모달 데이터 복원
     */
    _restoreFromNewCacheSystem() {
      if (!this.state.ticketId) {
        return false;
      }

      let hasRestoredData = false;

      // 새로운 캐시 매니저로 모든 데이터 복원
      if (window.TicketCacheManager) {
        try {
          window.TicketCacheManager.initialize(this.state.ticketId);

          // 티켓 요약 복원
          const summary = window.TicketCacheManager.getTicketSummary();
          if (summary) {
            this.state.data.summary = summary;
            hasRestoredData = true;
          }

          // 유사 티켓 복원
          const similarTickets = window.TicketCacheManager.getSimilarTickets();
          if (similarTickets) {
            this.state.data.similarTickets = similarTickets;
            hasRestoredData = true;
          }

          // KB 문서 복원
          const kbDocuments = window.TicketCacheManager.getKBDocuments();
          if (kbDocuments) {
            this.state.data.kbDocuments = kbDocuments;
            hasRestoredData = true;
          }

          // 채팅 히스토리 복원
          const chatHistory = window.TicketCacheManager.getChatHistory();
          if (chatHistory) {
            this.state.chatHistory = chatHistory;

            // 🔍 디버깅: 채팅 히스토리 복원 상태 확인
            console.log('🔍 [DEBUG] 채팅 히스토리 캐시에서 복원:', {
              restoredHistory: chatHistory,
              ragHistoryLength: chatHistory.rag?.length || 0,
              chatHistoryLength: chatHistory.chat?.length || 0,
              currentMode: this.state.chatMode
            });

            this._renderChatHistory();
            hasRestoredData = true;
          } else {
            console.log('🔍 [DEBUG] 캐시된 채팅 히스토리 없음');
          }

          // 메타데이터 복원 (요약 타입, 채팅 모드, 감정 분석 등)
          const metadata = window.TicketCacheManager.getTicketMetadata();
          if (metadata) {
            // 요약 타입 복원
            if (metadata.currentSummaryType) {
              this.state.summaryType = metadata.currentSummaryType;
              this._updateButtonsForType(metadata.currentSummaryType);
              console.log(`캐시된 요약 타입 복원: ${metadata.currentSummaryType}`);
            }

            // 채팅 모드 복원
            if (metadata.chatMode) {
              this.state.chatMode = metadata.chatMode;
              console.log(`캐시된 채팅 모드 복원: ${metadata.chatMode}`);
            }

            // 감정 분석 데이터 복원
            if (metadata.emotion) {
              this.state.emotion = metadata.emotion;
              console.log(`캐시된 감정 분석 복원: ${metadata.emotion.emotion}`);
            }

            hasRestoredData = true;
          }

        } catch (e) {
          console.warn('⚠️ 새 캐시 시스템 모달 데이터 복원 실패:', e);
        }
      }

      return hasRestoredData;
    },

    /**
     * 새로운 캐시 시스템으로 이관됨
     * TODO: TicketCacheManager 통합 완료 후 제거
     */
    restoreTicketData() {
      // 새로운 캐시 매니저로 이관됨
      if (window.TicketCacheManager && this.state.ticketId) {
        try {
          window.TicketCacheManager.initialize(this.state.ticketId);

          // 모든 데이터를 한번에 복원
          const allData = window.TicketCacheManager.getAllCachedData();
          if (allData) {
            if (allData.ticket_summary) this.state.data.summary = allData.ticket_summary;
            if (allData.similar_tickets) this.state.data.similarTickets = allData.similar_tickets;
            if (allData.kb_documents) this.state.data.kbDocuments = allData.kb_documents;
            if (allData.ticket_metadata) {
              this.state.cachedTicketInfo = allData.ticket_metadata.headerInfo;
              this.state.chatMode = allData.ticket_metadata.currentChatMode || 'rag';
              this.state.summaryType = allData.ticket_metadata.summaryType || 'structural';
            }

            // UI 렌더링 트리거
            if (window.TicketUI && window.TicketUI.renderAllFromCache) {
              setTimeout(() => {
                window.TicketUI.renderAllFromCache(allData);
              }, 100);
            }

            return true;
          }
        } catch (e) {
          console.warn('⚠️ 새 캐시 시스템 티켓 데이터 복원 실패:', e);
        }
      }

      return false;
    },

    /**
     * 새로운 캐시 시스템으로 이관됨
     * TODO: TicketCacheManager 통합 완료 후 제거
     */
    restoreChatHistoryPersistent() {
      if (!this.state.ticketId) return false;

      // 새로운 캐시 매니저 사용
      if (window.TicketCacheManager) {
        try {
          window.TicketCacheManager.initialize(this.state.ticketId);
          const chatHistory = window.TicketCacheManager.getChatHistory();
          if (chatHistory) {
            this.state.chatHistory = chatHistory;
            this._renderChatHistory();
            return true;
          }
        } catch (e) {
          console.warn('⚠️ 새 캐시 시스템 채팅 복원 실패:', e);
        }
      }

      return false;
    },

    /**
     * 티켓 데이터 렌더링 트리거
     */
    _triggerTicketDataRendering(ticketData) {
      if (window.TicketUI && window.TicketUI.renderAllFromCache) {
        // 더 안전한 렌더링을 위해 약간의 지연
        setTimeout(() => {

          // 스트리밍이 진행 중이 아닐 때만 렌더링
          if (!this.state.isLoading && this.state.streamingCompleted) {
            window.TicketUI.renderAllFromCache(ticketData);
          }

          // 토글 UI 상태 업데이트
          if (window.updateToggleUI) {
            window.updateToggleUI();
          }
          if (window.updateChatToggleUI) {
            window.updateChatToggleUI();
          }
        }, 100);
      }
    },

    /**
     * 캐시 렌더링 수동 트리거 (외부에서 호출 가능)
     */
    triggerCacheRendering() {
      if (!this.state.ticketId) {
        return;
      }

      // 로딩 중이면 렌더링 건너뛰기 (레이스 컨디션 방지)
      if (this.state.isLoading) {
        return;
      }

      // 현재 캐시된 데이터로 렌더링 시도
      const currentData = {
        summary: this.state.data.summary || '',
        similarTickets: this.state.data.similarTickets || [],
        kbDocuments: this.state.data.kbDocuments || [],
        emotionData: this.state.data.emotionData || null,
        headerInfo: this.state.cachedTicketInfo || null,
        currentChatMode: this.state.chatMode || 'rag',
        summaryType: this.state.summaryType || 'structural',
        streamingCompleted: this.state.streamingCompleted || false,
        ticketId: this.state.ticketId,
        timestamp: Date.now()
      };

      this._triggerTicketDataRendering(currentData);
    },

    /**
     * 새로운 캐시 시스템으로 이관됨 - 디버깅 정보
     */
    debugCacheState() {
      if (window.TicketCacheManager && this.state.ticketId) {
        try {
          window.TicketCacheManager.initialize(this.state.ticketId);
          return window.TicketCacheManager.getAllCachedData();
        } catch (e) {
          console.warn('⚠️ 새 캐시 시스템 디버깅 정보 조회 실패:', e);
          return null;
        }
      }
      return null;
    },


    /**
     * 대화 히스토리 상태 확인 (디버깅용)
     */
    debugChatHistory() {
      // 모드별 히스토리 디버그 정보
      // 모드별 채팅 히스토리 관리
      return this.state.chatHistory;
    },

    /**
     * 세션 ID 업데이트 (모드별)
     */
    updateSessionId() {
      const mode = this.state.chatMode;
      const ticketId = this.state.ticketId;

      // 모드별 세션 ID 생성 또는 복원
      const sessionKey = `session_${mode}_${ticketId}`;
      const existingSession = sessionStorage.getItem(sessionKey);

      if (existingSession) {
        // 기존 세션이 있으면 복원
        const sessionData = JSON.parse(existingSession);
        this.state.sessionId = sessionData.sessionId;
      } else {
        // 새 세션 생성
        this.state.sessionId = `${mode}_session_${ticketId}_${Date.now()}`;
        const sessionData = {
          sessionId: this.state.sessionId,
          mode: mode,
          ticketId: ticketId,
          createdAt: new Date().toISOString()
        };
        sessionStorage.setItem(sessionKey, JSON.stringify(sessionData));
      }
    },

    /**
     * 현재 세션 저장
     */
    saveCurrentSession() {
      if (!this.state.ticketId) return;

      const mode = this.state.chatMode;
      const sessionKey = `chat_session_${mode}_${this.state.ticketId}`;

      const sessionData = {
        mode: mode,
        sessionId: this.state.sessionId,
        history: this.state.chatHistory[mode] || [],
        lastUpdated: new Date().toISOString()
      };

      sessionStorage.setItem(sessionKey, JSON.stringify(sessionData));
    },

    /**
     * 현재 세션 로드
     */
    loadCurrentSession() {
      if (!this.state.ticketId) return;

      const mode = this.state.chatMode;
      const sessionKey = `chat_session_${mode}_${this.state.ticketId}`;

      const sessionDataStr = sessionStorage.getItem(sessionKey);
      if (sessionDataStr) {
        try {
          const sessionData = JSON.parse(sessionDataStr);

          // 세션 ID 복원
          if (sessionData.sessionId) {
            this.state.sessionId = sessionData.sessionId;
          }
        } catch (e) {
          console.error('세션 로드 실패:', e);
        }
      }
    },

    /**
     * 현재 모드의 채팅 히스토리 가져오기
     */
    getCurrentChatHistory() {
      const currentMode = this.state.chatMode;
      return this.state.chatHistory[currentMode] || [];
    },

    /**
     * 채팅 모드 변경 (히스토리는 각 모드별로 유지)
     */
    setChatMode(mode) {
      // 새로운 캐시 매니저로 현재 모드의 세션 저장
      if (window.TicketCacheManager && this.state.ticketId) {
        try {
          window.TicketCacheManager.initialize(this.state.ticketId);
          window.TicketCacheManager.saveChatHistory(this.state.chatHistory);
        } catch (e) {
          console.warn('⚠️ 새 캐시 시스템 모드 변경 저장 실패:', e);
        }
      }

      // 모드 변경
      this.state.chatMode = mode;

      // 새 모드의 세션 ID 생성 또는 복원
      this.updateSessionId();
    },

    /**
     * 채팅 컨텍스트 생성 (백엔드 전송용)
     */
    createChatContext() {
      if (!window.TicketCacheManager || !this.state.ticketId) {
        console.warn('TicketCacheManager 또는 ticketId가 없어 컨텍스트 생성 불가');
        return {};
      }

      try {
        window.TicketCacheManager.initialize(this.state.ticketId);

        // 캐시된 티켓 요약 가져오기
        const ticketSummary = window.TicketCacheManager.getTicketSummary() || {};
        const currentSummaryType = this.state.summaryType || 'structural';

        // 🔍 디버깅: 티켓 요약 상태 확인
        console.log('🔍 [DEBUG] 티켓 요약 캐시 상태:', {
          ticketId: this.state.ticketId,
          ticketSummary: ticketSummary,
          currentSummaryType: currentSummaryType,
          summaryKeys: Object.keys(ticketSummary),
          structuralExists: !!ticketSummary.structural,
          chronologicalExists: !!ticketSummary.chronological,
          structuralContent: ticketSummary.structural?.substring(0, 100) + '...',
          chronologicalContent: ticketSummary.chronological?.substring(0, 100) + '...'
        });

        // RAG 모드에서는 두 가지 요약을 모두 제공
        let ticketSummaryData;
        if (this.state.chatMode === 'rag') {
          const structuralSummary = ticketSummary.structural || '';
          const temporalSummary = ticketSummary.chronological || '';

          ticketSummaryData = {
            current: {
              content: ticketSummary[currentSummaryType] || structuralSummary || temporalSummary,
              type: currentSummaryType
            },
            structural: {
              content: structuralSummary,
              type: 'structural'
            },
            temporal: {
              content: temporalSummary,
              type: 'temporal'
            },
            ticketNumber: this.state.ticketId
          };
        } else {
          // Chat 모드에서는 현재 선택된 요약만 제공
          const selectedSummary = ticketSummary[currentSummaryType] || ticketSummary.structural || ticketSummary.chronological || '';
          ticketSummaryData = {
            content: selectedSummary,
            type: currentSummaryType,
            ticketNumber: this.state.ticketId
          };
        }

        // 유사 티켓과 KB 문서 가져오기
        const similarTicketsRaw = window.TicketCacheManager.getSimilarTickets();
        const similarTicketsArray = Array.isArray(similarTicketsRaw)
          ? similarTicketsRaw
          : Array.isArray(similarTicketsRaw?.tickets)
            ? similarTicketsRaw.tickets
            : [];
        const kbDocumentsRaw = window.TicketCacheManager.getKBDocuments();
        const kbDocumentsArray = Array.isArray(kbDocumentsRaw)
          ? kbDocumentsRaw
          : Array.isArray(kbDocumentsRaw?.documents)
            ? kbDocumentsRaw.documents
            : [];
        const similarTicketsMetadata = similarTicketsRaw?.metadata || null;
        const kbDocumentsMetadata = kbDocumentsRaw?.metadata || null;

        // 티켓 메타데이터 가져오기
        const metadata = window.TicketCacheManager.getTicketMetadata() || {};

        // 티켓 헤더 정보 결합 (FDK 데이터 우선)
        const headerInfo = metadata.headerInfo || this.state.ticketHeaderInfo || this.state.cachedTicketInfo || null;
        const ticketDetails = headerInfo?.ticket?.ticket || headerInfo?.ticket || {};
        const requesterDetails = headerInfo?.contact?.contact || headerInfo?.contact || {};
        const agentDetails = headerInfo?.agent?.contact || headerInfo?.agent || {};

        const ticketInfo = {
          subject: ticketDetails.subject || metadata.subject || '',
          description_text: ticketDetails.description_text || ticketDetails.description || metadata.description_text || '',
          priority: ticketDetails.priority_text || ticketDetails.priority || metadata.priority || '',
          status: ticketDetails.status_text || ticketDetails.status || metadata.status || '',
          requester: requesterDetails.name || requesterDetails.email || metadata.requester || '',
          agent: agentDetails.name || metadata.agent || '',
          updated_at: ticketDetails.updated_at || metadata.updated_at || null
        };

        // 현재 모드의 채팅 히스토리 가져오기
        const currentChatHistory = this.getCurrentChatHistory();

        // 🔍 디버깅: 히스토리 상태 확인
        console.log(`🔍 [DEBUG] 채팅 히스토리 디버깅:`, {
          currentMode: this.state.chatMode,
          allHistory: this.state.chatHistory,
          currentModeHistory: currentChatHistory,
          historyLength: currentChatHistory.length,
          lastMessage: currentChatHistory.length > 0 ? currentChatHistory[currentChatHistory.length - 1] : null
        });

        const context = {
          ticketId: this.state.ticketId,
          ticketSummary: ticketSummaryData,
          similarTickets: similarTicketsArray.slice(0, 5), // 최대 5개로 제한
          kbDocuments: kbDocumentsArray.slice(0, 5), // 최대 5개로 제한
          chatHistory: currentChatHistory.slice(-10), // 최근 10개 메시지로 제한
          chatMode: this.state.chatMode,
          ticketInfo: ticketInfo,
          metadata: {
            emotionData: metadata.emotionData,
            minQualityScore: metadata.minQualityScore,
            timestamp: Date.now(),
            similarTickets: similarTicketsMetadata,
            kbDocuments: kbDocumentsMetadata,
            headerInfo: headerInfo
          }
        };

        // 🔍 디버깅: 최종 컨텍스트 상태 확인
        console.log('🔍 [DEBUG] 최종 생성된 채팅 컨텍스트:', {
          ticketId: context.ticketId,
          chatMode: context.chatMode,
          ticketSummary: context.ticketSummary,
          hasStructuralSummary: !!context.ticketSummary?.structural?.content,
          hasTemporalSummary: !!context.ticketSummary?.temporal?.content,
          structuralLength: context.ticketSummary?.structural?.content?.length || 0,
          temporalLength: context.ticketSummary?.temporal?.content?.length || 0,
          similarTicketsCount: context.similarTickets?.length || 0,
          kbDocumentsCount: context.kbDocuments?.length || 0,
          chatHistoryLength: context.chatHistory?.length || 0
        });

        const summaryInfo = this.state.chatMode === 'rag'
          ? `구조적: ${ticketSummaryData.structural.content.length}자, 시간순: ${ticketSummaryData.temporal.content.length}자`
          : `${currentSummaryType}: ${ticketSummaryData.content.length}자`;

        console.log(`채팅 컨텍스트 생성 완료 (${this.state.chatMode} 모드):`, {
          ticketId: context.ticketId,
          summaryInfo: summaryInfo,
          similarTickets: similarTicketsArray.length,
          kbDocuments: kbDocumentsArray.length,
          chatHistoryMessages: currentChatHistory.length,
          mode: this.state.chatMode
        });

        return context;
      } catch (error) {
        console.error('채팅 컨텍스트 생성 오류:', error);
        return {
          ticketId: this.state.ticketId,
          ticketSummary: { content: '', type: 'structural' },
          similarTickets: [],
          kbDocuments: [],
          chatHistory: [],
          chatMode: this.state.chatMode || 'rag',
          ticketInfo: {
            subject: '',
            description_text: '',
            priority: '',
            status: '',
            requester: '',
            agent: '',
            updated_at: null
          },
          metadata: { timestamp: Date.now() }
        };
      }
    },

    /**
     * 채팅 히스토리 삭제 (모드별)
     */
    clearChatHistory(mode = null) {
      if (mode) {
        // 특정 모드의 히스토리만 삭제
        if (this.state.chatHistory[mode]) {
          this.state.chatHistory[mode] = [];
          console.log(`${mode} 채팅 히스토리 삭제됨`);
        }
      } else {
        // 현재 모드의 히스토리 삭제
        const currentMode = this.state.chatMode;
        if (this.state.chatHistory[currentMode]) {
          this.state.chatHistory[currentMode] = [];
          console.log(`현재 모드(${currentMode}) 채팅 히스토리 삭제됨`);
        }
      }

      // 캐시에 변경사항 저장
      this._debouncedSaveChatHistory();

      // UI 업데이트
      if (window.ChatUI && typeof window.ChatUI.renderChatHistory === 'function') {
        window.ChatUI.renderChatHistory();
      }
    },


    /**
     * 새로운 캐시 시스템으로 이관됨
     * TODO: TicketCacheManager 통합 완료 후 제거
     */
    cacheTicketData(ticketData, conversations) {
      // 새로운 캐시 매니저 사용
      if (window.TicketCacheManager && this.state.ticketId) {
        try {
          window.TicketCacheManager.initialize(this.state.ticketId);
          window.TicketCacheManager.saveTicketSummary(ticketData);
          window.TicketCacheManager.saveTicketMetadata({
            conversations: conversations,
            ticketData: ticketData
          });
        } catch (e) {
          console.warn('⚠️ 새 캐시 시스템 티켓 데이터 저장 실패:', e);
        }
      }

      // 기존 메모리 캐시도 유지 (호환성)
      this.state.ticketData = ticketData;
      this.state.conversations = conversations;
    },

    /**
     * 새로운 캐시 시스템으로 이관됨
     * TODO: TicketCacheManager 통합 완료 후 제거
     */
    getCachedTicketData() {
      // 새로운 캐시 매니저 사용
      if (window.TicketCacheManager && this.state.ticketId) {
        try {
          window.TicketCacheManager.initialize(this.state.ticketId);
          const context = window.TicketCacheManager.createChatContext();
          if (context) {
            return context;
          }
        } catch (e) {
          console.warn('⚠️ 새 캐시 시스템 티켓 데이터 조회 실패:', e);
        }
      }

      // 기존 메모리 캐시 사용 (폴백)
      if (!this.state.ticketData) {
        return null;
      }

      return {
        ticket: this.state.ticketData,
        conversations: this.state.conversations,
        cached_at: Date.now()
      };
    },

    /**
     * 진행률 업데이트 (중앙집중식 관리)
     */
    updateProgress(stage, percentage) {
      // 진행률 상태 업데이트
      this.state.progress.current = percentage;
      this.state.progress.stage = stage;

      // UI 업데이트
      window.TicketUI?.updateProgress(stage, percentage);

      // 자동 로딩 관리 제거 - 스켈레톤 UI를 사용하므로 로딩 오버레이 불필요
      // 이제 각 컴포넌트에서 명시적으로 로딩 상태를 관리합니다
    },

    /**
     * 진행률 초기화
     */
    resetProgress() {
      this.updateProgress('idle', 0);
    },

    /**
     * 데이터 로드 시작
     */
    startDataLoad() {
      // 로딩 상태만 설정하고 오버레이는 표시하지 않음
      this.state.isLoading = true;
      // 스트리밍 상태 리셋
      this.resetStreamingState();
      // 진행률 추적은 유지 (UI 표시용)
      this.updateProgress('ticket', 25);

    },

    /**
     * 안전한 데이터 로드 시작 (캐시 검증 포함)
     */
    startDataLoadSafe() {
      // 캐시가 유효하면 로드를 시작하지 않음
      if (!this.needsNewStreaming()) {
        return false;
      }

      this.startDataLoad();
      return true;
    },

    /**
     * 첫 번째 콘텐츠 표시 (스켈레톤으로 전환)
     */
    showInitialContent() {
      // 첫 번째 콘텐츠 표시 - 스케일톤 모드로 전환

      // 로딩 오버레이 숨김
      window.TicketUI?.hideLoading();

      // 스켈레톤 표시는 ApiService에서 담당

      // 상태 플래그 설정
      this.state.initialContentShown = true;
    },

    /**
     * 섹션별 진행률 업데이트
     */
    updateSectionProgress(sectionType, isCompleted = true) {
      // 섹션 진행률 업데이트

      if (isCompleted) {
        // 해당 섹션의 스케일톤 숨김
        window.TicketUI?.hideSkeletonForSection(sectionType);
      }

      // 전체 진행률 계산 및 업데이트
      this._calculateOverallProgress();
    },

    /**
     * 전체 진행률 계산 (내부 함수)
     */
    _calculateOverallProgress() {
      const sections = ['summary', 'similar_tickets', 'kb_documents'];
      const completedSections = sections.filter(section => {
        switch (section) {
          case 'summary':
            return this.state.data.summary && this.state.data.summary.length > 0;
          case 'similar_tickets':
            return this.state.data.similarTickets && this.state.data.similarTickets.length > 0;
          case 'kb_documents':
            return this.state.data.kbDocuments && this.state.data.kbDocuments.length > 0;
          default:
            return false;
        }
      });

      const progressPercentage = Math.round((completedSections.length / sections.length) * 100);

      // 진행률이 100%가 되면 완전히 로딩 종료
      if (progressPercentage === 100) {
        this.setLoading(false);
        // 모든 섹션 로딩 완료
      }
    },

    /**
     * 이벤트 타입에 따른 진행률 매핑
     */
    progressByEvent: {
      'summary': 50,
      'similar_tickets': 75,
      'kb_documents': 90,
      'done': 100,
      'complete': 100
    },

    /**
     * 이벤트 기반 진행률 업데이트
     */
    handleProgressEvent(eventType) {
      const percentage = this.progressByEvent[eventType];
      if (percentage) {
        this.updateProgress(eventType === 'done' || eventType === 'complete' ? 'complete' : eventType, percentage);
      }
    },

    // ========== 상태 보존 시스템 ==========

    /**
     * 현재 상태를 SessionStorage에 저장
     */
    saveState() {
      if (!this.state.ticketId) {
        return;
      }

      try {
        const stateKey = `copilot_state_${this.state.ticketId}`;

        // UI 캐시 업데이트 (DOM 쿼리 한 번에 실행)
        this.updateUICache();

        // 현재 UI 상태 수집 (캐시 사용)
        const currentState = {
          // 활성 탭
          activeTab: this.state.uiCache.activeTab,

          // 스크롤 위치
          scrollPosition: this.state.uiCache.scrollPosition,
          chatScrollPosition: this.state.uiCache.chatScrollPosition,

          // 요약 섹션 상태
          summaryCollapsed: this.state.uiCache.summaryCollapsed,

          // 티켓 상세 뷰 상태
          ticketDetailView: this.state.ticketDetailView || null,

          // 채팅 입력 값
          chatInputValue: this.state.uiCache.chatInputValue,

          // 채팅 히스토리는 저장하지 않음 (새로고침 시 초기화 위해)
          // chatHistory: 제거됨

          // 채팅 모드
          chatMode: this.state.chatMode || 'rag',

          // 저장 시간
          savedAt: Date.now()
        };

        sessionStorage.setItem(stateKey, JSON.stringify(currentState));
        // 상태 저장 완료

      } catch (error) {
        console.error('❌ 상태 저장 실패:', error);
      }
    },

    /**
     * SessionStorage에서 상태 복원
     */
    restoreState() {

      if (!this.state.ticketId) {
        return false;
      }

      try {
        const stateKey = `copilot_state_${this.state.ticketId}`;
        const savedStateString = sessionStorage.getItem(stateKey);

        if (!savedStateString) {
          // 저장된 상태 없음
          return false;
        }

        const savedState = JSON.parse(savedStateString);

        // 저장된 시간이 1시간 이상 지났으면 삭제
        const oneHour = 60 * 60 * 1000;
        if (Date.now() - savedState.savedAt > oneHour) {
          sessionStorage.removeItem(stateKey);
          // 오래된 상태 삭제
          return false;
        }

        // 상태 복원 (채팅 관련 제외)
        this.state.savedState = savedState;

        // 채팅 모드만 복원 (히스토리는 완전 초기화됨) - 기본값을 rag로 강제 설정
        this.state.chatMode = 'rag';

        // 티켓 상세 뷰 상태 복원
        if (savedState.ticketDetailView) {
          this.state.ticketDetailView = savedState.ticketDetailView;
        }

        // 모달 데이터 자동 복원 (성능 최적화)
        this.restoreModalData();

        // 상태 복원 완료
        return true;

      } catch (error) {
        console.error('❌ 상태 복원 실패:', error);
        return false;
      }
    },

    /**
     * UI 상태를 DOM에 적용
     */
    applyRestoredState() {
      if (!this.state.savedState) {
        return;
      }

      const savedState = this.state.savedState;
      // UI 상태 적용 시작

      try {
        // 1. 활성 탭 복원
        if (savedState.activeTab) {
          this.restoreActiveTab(savedState.activeTab);
        }

        // 2. 요약 섹션 상태 복원
        if (savedState.summaryCollapsed !== undefined) {
          this.restoreSummaryState(savedState.summaryCollapsed);
        }

        // 3. 채팅 입력값 복원
        if (savedState.chatInputValue) {
          this.restoreChatInputValue(savedState.chatInputValue);
        }

        // 4. 채팅 모드 UI 복원
        if (savedState.chatMode) {
          this.restoreChatModeUI(savedState.chatMode);
        }

        // 5. 채팅 히스토리 UI 복원
        if (savedState.chatHistory && savedState.chatHistory.length > 0) {
          this.restoreChatHistory();
        }

        // 6. 스크롤 위치는 딜레이 후 복원 (DOM 렌더링 완료 후)
        setTimeout(() => {
          this.restoreScrollPositions(savedState);
        }, 1000);

        // 6. 티켓 상세 뷰 복원
        if (savedState.ticketDetailView && savedState.ticketDetailView.isDetailView) {
          setTimeout(() => {
            this.restoreTicketDetailView(savedState.ticketDetailView);
          }, 1500);
        }

        // UI 상태 적용 완룼

      } catch (error) {
        console.error('❌ UI 상태 적용 실패:', error);
      }
    },

    /**
     * UI 캐시 업데이트 (DOM 쿼리 최적화)
     */
    updateUICache() {
      const now = Date.now();
      // 100ms 이내 중복 업데이트 방지
      if (now - this.state.uiCache.lastCacheUpdate < 100) {
        return;
      }

      // DOM 쿼리 한 번에 실행
      const activeTabButton = document.querySelector('.tab-button.active');
      const summarySection = document.getElementById('summarySection');
      const chatInput = document.getElementById('chatInput');
      const chatMessages = document.querySelector('.chat-messages');

      this.state.uiCache = {
        activeTab: activeTabButton ? activeTabButton.getAttribute('data-tab') : 'tickets',
        scrollPosition: window.pageYOffset || document.documentElement.scrollTop || 0,
        chatScrollPosition: chatMessages ? chatMessages.scrollTop : 0,
        summaryCollapsed: summarySection ? summarySection.classList.contains('collapsed') : false,
        chatInputValue: chatInput ? chatInput.value : '',
        lastCacheUpdate: now
      };
    },

    /**
     * 현재 활성 탭 가져오기 (캐시 사용)
     */
    getCurrentActiveTab() {
      // 캐시가 최신이면 캐시 사용, 아니면 DOM 쿼리
      const cacheAge = Date.now() - this.state.uiCache.lastCacheUpdate;
      if (cacheAge < 500) {
        return this.state.uiCache.activeTab;
      }

      const activeTabButton = document.querySelector('.tab-button.active');
      const activeTab = activeTabButton ? activeTabButton.getAttribute('data-tab') : 'tickets';
      this.state.uiCache.activeTab = activeTab;
      this.state.uiCache.lastCacheUpdate = Date.now();
      return activeTab;
    },

    /**
     * 현재 스크롤 위치 가져오기 (캐시 사용)
     */
    getCurrentScrollPosition() {
      const cacheAge = Date.now() - this.state.uiCache.lastCacheUpdate;
      if (cacheAge < 500) {
        return this.state.uiCache.scrollPosition;
      }

      const scrollPos = window.pageYOffset || document.documentElement.scrollTop || 0;
      this.state.uiCache.scrollPosition = scrollPos;
      this.state.uiCache.lastCacheUpdate = Date.now();
      return scrollPos;
    },

    /**
     * 현재 채팅 스크롤 위치 가져오기 (캐시 사용)
     */
    getCurrentChatScrollPosition() {
      const cacheAge = Date.now() - this.state.uiCache.lastCacheUpdate;
      if (cacheAge < 500) {
        return this.state.uiCache.chatScrollPosition;
      }

      const chatMessages = document.querySelector('.chat-messages');
      const chatScrollPos = chatMessages ? chatMessages.scrollTop : 0;
      this.state.uiCache.chatScrollPosition = chatScrollPos;
      this.state.uiCache.lastCacheUpdate = Date.now();
      return chatScrollPos;
    },

    /**
     * 요약 섹션 접기 상태 가져오기 (캐시 사용)
     */
    getSummaryCollapsedState() {
      const cacheAge = Date.now() - this.state.uiCache.lastCacheUpdate;
      if (cacheAge < 500) {
        return this.state.uiCache.summaryCollapsed;
      }

      const summarySection = document.getElementById('summarySection');
      const collapsed = summarySection ? summarySection.classList.contains('collapsed') : false;
      this.state.uiCache.summaryCollapsed = collapsed;
      this.state.uiCache.lastCacheUpdate = Date.now();
      return collapsed;
    },

    /**
     * 현재 채팅 입력값 가져오기 (캐시 사용)
     */
    getCurrentChatInputValue() {
      const cacheAge = Date.now() - this.state.uiCache.lastCacheUpdate;
      if (cacheAge < 500) {
        return this.state.uiCache.chatInputValue;
      }

      const chatInput = document.getElementById('chatInput');
      const inputValue = chatInput ? chatInput.value : '';
      this.state.uiCache.chatInputValue = inputValue;
      this.state.uiCache.lastCacheUpdate = Date.now();
      return inputValue;
    },

    /**
     * 활성 탭 복원
     */
    restoreActiveTab(tabName) {
      const tabButton = document.querySelector(`[data-tab="${tabName}"]`);
      if (tabButton) {
        tabButton.click();
        // 활성 탭 복원
      }
    },

    /**
     * 요약 섹션 상태 복원
     */
    restoreSummaryState(collapsed) {
      if (window.ScrollManager && typeof window.ScrollManager.toggleSummary === 'function') {
        const summarySection = document.getElementById('summarySection');
        const isCurrentlyCollapsed = summarySection?.classList.contains('collapsed');

        if (collapsed !== isCurrentlyCollapsed) {
          window.ScrollManager.toggleSummary();
          // 요약 섹션 상태 복원
        }
      }
    },

    /**
     * 채팅 입력값 복원
     */
    restoreChatInputValue(value) {
      const chatInput = document.getElementById('chatInput');
      if (chatInput && value) {
        chatInput.value = value;
        // 채팅 입력값 복원
      }
    },

    /**
     * 채팅 모드 UI 복원
     */
    restoreChatModeUI(chatMode) {
      const toggle = document.querySelector('.ios-toggle');
      const modeIndicator = document.getElementById('modeIndicator');

      if (toggle) {
        toggle.classList.toggle('chat-mode', chatMode === 'chat');
      }

      if (modeIndicator) {
        modeIndicator.textContent = chatMode === 'chat' ? '💭 자유대화' : '🎯 스마트대화';
      }

      // 채팅 모드 UI 복원
    },

    /**
     * 채팅 히스토리 UI 복원
     */
    restoreChatHistory() {
      if (window.ChatUI && typeof window.ChatUI.renderChatHistory === 'function') {
        window.ChatUI.renderChatHistory();
        // 채팅 히스토리 복원
      }
    },

    /**
     * 스크롤 위치 복원
     */
    restoreScrollPositions(savedState) {
      // 메인 스크롤 위치 복원
      if (savedState.scrollPosition > 0) {
        window.scrollTo(0, savedState.scrollPosition);
        // 메인 스크롤 위치 복원
      }

      // 채팅 스크롤 위치 복원  
      if (savedState.chatScrollPosition > 0) {
        const chatMessages = document.querySelector('.chat-messages');
        if (chatMessages) {
          chatMessages.scrollTop = savedState.chatScrollPosition;
          // 채팅 스크롤 위치 복원
        }
      }
    },

    /**
     * 티켓 상세 뷰 복원
     */
    async restoreTicketDetailView(ticketDetailView) {
      if (window.TicketUI && typeof window.TicketUI.showTicketDetail === 'function') {
        const ticketIndex = ticketDetailView.currentTicketIndex;
        if (ticketIndex >= 0) {
          await window.TicketUI.showTicketDetail(ticketIndex);
          // 티켓 상세 뷰 복원
        }
      }
    },

    /**
     * 상태 저장을 자동으로 호출하는 메서드들
     */
    autoSaveState() {
      // 주요 상태 변경 시 자동 저장
      this.saveState();
    },

    /**
     * 모달 데이터 저장 (no-op)
     * - 이전 캐시 시스템 제거 후 남아있는 호출을 안전하게 흡수하기 위한 스텁
     * - 향후 필요 시 세션/로컬 저장 로직을 여기에서 구현
     */
    saveModalData() {
      // intentionally no-op
      return true;
    },

    /**
     * 상태 정리 (모달 종료 시)
     */
    clearSavedState() {
      if (this.state.ticketId) {
        const stateKey = `copilot_state_${this.state.ticketId}`;
        sessionStorage.removeItem(stateKey);
        // 저장된 상태 정리
      }
    },

    /**
     * 요약 타입에 대한 기본 렌더링 설정 반환
     */
    getDefaultRendering(type) {
      // 최소한의 기본값만 제공 (YAML이 우선)
      const defaultRenderings = {
        structural: {
          type: "structural",
          options: {
            add_section_breaks: true
          }
        },
        temporal: {
          type: "temporal",
          options: {
            add_section_breaks: true,
            remove_intro_text: true
          }
        }
      };

      return defaultRenderings[type] || defaultRenderings.structural;
    },

    /**
     * 요약 타입 전환 (구조적 ↔ 시간순)
     */
    async switchSummaryType(type) {
      if (!this._validateSwitchRequest(type)) {
        return;
      }

      const cachedSummary = this._checkCachedSummary(type);
      if (cachedSummary) {
        this._applyCachedSummary(type, cachedSummary);
        return;
      }

      this._initializeSwitchingState(type);

      try {
        await this._fetchNewSummary(type);
        this.state.summaryType = type;
      } catch (error) {
        this._handleSwitchError(error);
      } finally {
        this._finalizeSwitchingState();
      }
    },

    /**
     * 요약 타입 전환 요청 유효성 검사
     */
    _validateSwitchRequest(type) {
      if (!this.state.ticketId) {
        console.error('티켓 ID가 없습니다.');
        return false;
      }

      if (this.state.summaryType === type) {
        return false;
      }

      return true;
    },

    /**
     * 캐시된 요약 확인 (새 캐시 시스템 사용)
     */
    _checkCachedSummary(type) {
      if (!window.TicketCacheManager) {
        console.warn('TicketCacheManager가 사용 가능하지 않음');
        return null;
      }

      try {
        // 새 캐시 시스템에서 티켓 요약 조회
        const cachedData = window.TicketCacheManager.getTicketSummary();

        if (!cachedData) {
          console.log(`❌ 캐시된 요약 데이터 없음`);
          return null;
        }

        // 캐시 매니저의 키 매핑 헬퍼 사용
        const mappedType = window.TicketCacheManager._mapSummaryType(type);

        console.log(`🔍 캐시에서 ${type} (${mappedType}) 요약 확인 중...`);
        console.log('전체 캐시된 데이터:', cachedData);
        console.log('요청한 타입의 실제 값:', {
          value: cachedData[mappedType],
          type: typeof cachedData[mappedType],
          length: typeof cachedData[mappedType] === 'string' ? cachedData[mappedType].length : 'N/A'
        });

        // undefined, null, 빈 문자열이 아닌 경우만 유효한 캐시로 인정
        if (cachedData[mappedType] !== undefined && cachedData[mappedType] !== null && cachedData[mappedType] !== '' && cachedData[mappedType] !== ' ') {
          console.log(`✅ 캐시에서 ${type} 요약 발견 (길이: ${cachedData[mappedType].length})`);
          return cachedData[mappedType];
        }

        console.log(`❌ 캐시에서 ${type} (${mappedType}) 요약 없음 또는 빈 값`);

        // 레거시 캐시에서 폴백 체크 (호환성을 위해)
        const legacyCacheKey = `summary_${type}`;
        const legacyData = this.state.data[legacyCacheKey];

        if (legacyData) {
          console.log(`✅ 레거시 캐시에서 ${type} 요약 발견`);
          return legacyData;
        }

        return null;
      } catch (error) {
        console.error('캐시된 요약 확인 오류:', error);
        return null;
      }
    },

    /**
     * 캐시된 요약 적용 (새 캐시 시스템 통합)
     */
    _applyCachedSummary(type, cachedSummary) {
      console.log(`🔄 캐시된 ${type} 요약 적용 중...`);

      this.state.summaryType = type;
      this.state.data.summary = cachedSummary;

      // 새 캐시 시스템에 현재 선택된 타입 저장
      if (window.TicketCacheManager) {
        try {
          // 티켓 메타데이터에 현재 요약 타입 저장
          const currentMetadata = window.TicketCacheManager.getTicketMetadata() || {};
          currentMetadata.currentSummaryType = type;
          window.TicketCacheManager.saveTicketMetadata(currentMetadata);

          console.log(`✅ 요약 타입 ${type}로 변경되어 캐시에 저장됨`);
        } catch (error) {
          console.error('캐시에 요약 타입 저장 실패:', error);
        }
      }

      this._clearSummaryDisplay();
      this._renderCachedSummary(type, cachedSummary);
      this._updateButtonsForType(type);
    },

    /**
     * 요약 표시 영역 초기화
     */
    _clearSummaryDisplay() {
      const summaryText = document.getElementById('summaryText');
      if (summaryText) {
        summaryText.innerHTML = '';
      }
    },

    /**
     * 캐시된 요약 렌더링 (새 캐시 시스템 통합)
     */
    _renderCachedSummary(type, cachedSummary) {
      if (window.TicketUI) {
        window.TicketUI._summaryBuffer = null;

        // 새 캐시 시스템에서 렌더링 데이터 조회
        let cachedRendering = null;
        if (window.TicketCacheManager) {
          try {
            const ticketSummary = window.TicketCacheManager.getTicketSummary();

            // 캐시 매니저의 키 매핑 헬퍼 사용
            const mappedType = window.TicketCacheManager._mapSummaryType(type);

            if (ticketSummary && ticketSummary.rendering && ticketSummary.rendering[mappedType]) {
              cachedRendering = ticketSummary.rendering[mappedType];
              console.log(`✅ 캐시된 ${type} (${mappedType}) 렌더링 데이터 발견`);
            } else {
              console.log(`❌ 캐시된 ${type} (${mappedType}) 렌더링 데이터 없음`);
            }
          } catch (error) {
            console.error('캐시된 렌더링 데이터 조회 오류:', error);
          }
        }

        // 레거시 캐시에서 폴백 또는 기본값 사용
        if (!cachedRendering) {
          const renderingKey = `rendering_${type}`;
          cachedRendering = this.state.data[renderingKey] || this.getDefaultRendering(type);
        }

        window.TicketUI.updateSummary(cachedSummary, cachedRendering);
        console.log(`${type} 요약 렌더링 완료 (캐시 사용)`);
      }
    },

    /**
     * 지정된 타입에 대한 버튼 상태 업데이트
     */
    _updateButtonsForType(type) {
      document.querySelectorAll('.toggle-btn').forEach(btn => {
        btn.classList.remove('active');
        if (btn.dataset.type === type) {
          btn.classList.add('active');
        }
      });

      // 새로운 토글 UI 업데이트
      if (window.updateToggleUI) {
        window.updateToggleUI();
      }

      // 채팅 토글 UI 업데이트
      if (window.updateChatToggleUI) {
        window.updateChatToggleUI();
      }
    },

    /**
     * 요약 타입 전환 초기 상태 설정
     */
    _initializeSwitchingState(type) {
      this.state.isLoading = true;
      this._setButtonsLoadingState(type);
      this._showSummarySkeleton();
      this.state.summaryType = type;
    },

    /**
     * 버튼들을 로딩 상태로 설정
     */
    _setButtonsLoadingState(activeType) {
      document.querySelectorAll('.toggle-btn').forEach(btn => {
        btn.classList.remove('active');
        btn.classList.add('loading');
        btn.disabled = true;

        if (btn.dataset.type === activeType) {
          btn.classList.add('active');
        }
      });
    },

    /**
     * 요약 로딩 스켈레톤 표시
     */
    _showSummarySkeleton() {
      const summaryText = document.getElementById('summaryText');
      if (summaryText) {
        summaryText.innerHTML = '<div class="summary-skeleton"><div class="skeleton-line long"></div><div class="skeleton-line medium"></div><div class="skeleton-line long"></div></div>';
      }
    },

    /**
     * 새로운 요약 데이터 가져오기
     */
    async _fetchNewSummary(type) {
      // ApiService 경로로 위임: 통일된 스트리밍/스켈레톤 처리
      const headers = window.ApiService.getHeaders();
      await window.ApiService.loadSummary(this.state.ticketId, headers, type);
    },

    /**
     * 스트리밍 응답 처리 (더 이상 사용되지 않음)
     */
    _processStreamingResponse() {
      // Deprecated: ApiService가 담당. 남겨두되 더 이상 사용하지 않음.
      return;
    },

    /**
     * 스트림 라인 파싱 (더 이상 사용되지 않음)
     */
    _parseStreamLine() {
      // Deprecated: ApiService가 담당.
      return;
    },

    /**
     * 요약 타입 전환 오류 처리
     */
    _handleSwitchError(error) {
      console.error('요약 전환 오류:', error);

      this._restorePreviousButtonState();
      this._showErrorMessage();
    },

    /**
     * 이전 버튼 상태 복원
     */
    _restorePreviousButtonState() {
      document.querySelectorAll('.toggle-btn').forEach(btn => {
        btn.classList.remove('active');
        if (btn.dataset.type === this.state.summaryType) {
          btn.classList.add('active');
        }
      });
    },

    /**
     * 오류 메시지 표시
     */
    _showErrorMessage() {
      const summaryText = document.getElementById('summaryText');
      if (summaryText) {
        summaryText.innerHTML = '<div class="error-message">요약을 불러오는데 실패했습니다.</div>';
      }
    },

    /**
     * 요약 타입 전환 마무리 상태 설정
     */
    _finalizeSwitchingState() {
      this.state.isLoading = false;
      this._clearButtonsLoadingState();
      this._updateButtonsForType(this.state.summaryType);
    },

    /**
     * 버튼들의 로딩 상태 해제
     */
    _clearButtonsLoadingState() {
      document.querySelectorAll('.toggle-btn').forEach(btn => {
        btn.classList.remove('loading');
        btn.disabled = false;
      });
    },

    /**
     * 토글 버튼 초기화 (페이지 로드 시)
     */
    initializeToggleButtons() {
      document.querySelectorAll('.toggle-btn').forEach(btn => {
        btn.classList.remove('loading');
        btn.disabled = false;
      });
    },

    /**
     * 요약 스트림 데이터 처리 (더 이상 사용되지 않음)
     */
    handleSummaryStreamData() {
      // Deprecated: ApiService가 스트림/스켈레톤 처리 전담
      return;
    }
  };

  // Core 모듈 정의 완료

  // 초기화 완료 플래그 설정
  window.Core._initialized = true;


  // 전역 함수 정의 (HTML onclick에서 사용) - 모달에서만 실행
  window.switchSummaryType = function (type) {
    // 모달에서만 실행 가능
    if (!window.Core?.state?.isModalView) {
      return;
    }

    return window.Core.switchSummaryType(type);
  };

  window.copySummary = function (event) {
    if (event) event.preventDefault();

    const summaryText = document.getElementById('summaryText');
    if (!summaryText) {
      return;
    }

    const textContent = summaryText.textContent || summaryText.innerText || '';

    if (!textContent.trim()) {
      return;
    }

    // 클립보드에 복사 (권한/폴백 내장 유틸 사용)
    window.Utils.copyToClipboard(textContent).then(() => {
      // 클립보드 복사 완료

      // 복사 완료 시각적 피드백
      const copyBtn = event?.target;
      if (copyBtn) {
        const originalText = copyBtn.textContent;
        copyBtn.textContent = '✅ 복사됨';
        copyBtn.style.background = 'rgba(34, 197, 94, 0.2)';

        setTimeout(() => {
          copyBtn.textContent = originalText;
          copyBtn.style.background = '';
        }, 1500);
      }
    }).catch(err => {
      console.error('클립보드 복사 실패:', err);
    });
  };

  // 토글 버튼을 위한 toggleSummaryType 함수 (캐시 기반 즉시 토글)
  window.toggleSummaryType = function () {
    // 모달에서만 실행 가능
    if (!window.Core?.state?.isModalView) {
      return;
    }

    const currentType = window.Core.state.summaryType || 'structural';
    const newType = currentType === 'structural' ? 'temporal' : 'structural';

    console.log(`요약 토글 요청: ${currentType} → ${newType}`);

    // 캐시된 데이터가 있는지 확인하여 즉시 토글 가능한지 판단
    const cachedSummary = window.Core._checkCachedSummary(newType);

    if (cachedSummary) {
      // 캐시된 데이터가 있으면 즉시 토글 (API 호출 없음)
      console.log(`캐시된 ${newType} 요약 발견 - 즉시 토글`);

      // UI 토글 상태 즉시 업데이트
      const toggleSwitch = document.querySelector('.apple-toggle-switch');
      const toggleSlider = document.getElementById('summaryToggleSlider');
      const toggleState = document.getElementById('summaryToggleState');

      if (toggleSwitch && toggleSlider && toggleState) {
        toggleState.value = newType;

        if (newType === 'temporal') {
          toggleSwitch.classList.add('temporal');
        } else {
          toggleSwitch.classList.remove('temporal');
        }
      }

      // 캐시된 요약 즉시 적용
      window.Core._applyCachedSummary(newType, cachedSummary);
      return Promise.resolve();
    } else {
      // 캐시된 데이터가 없으면 기존 방식으로 API 호출
      console.log(`${newType} 요약 캐시 없음 - API 호출 필요`);

      // UI 토글 상태 업데이트
      const toggleSwitch = document.querySelector('.apple-toggle-switch');
      const toggleSlider = document.getElementById('summaryToggleSlider');
      const toggleState = document.getElementById('summaryToggleState');

      if (toggleSwitch && toggleSlider && toggleState) {
        toggleState.value = newType;

        if (newType === 'temporal') {
          toggleSwitch.classList.add('temporal');
        } else {
          toggleSwitch.classList.remove('temporal');
        }
      }

      // API를 통한 요약 타입 변경
      return window.Core.switchSummaryType(newType);
    }
  };

  // 토글 UI 상태 업데이트 함수
  window.updateToggleUI = function () {
    const currentType = window.Core?.state?.summaryType || 'structural';
    const toggleSwitch = document.querySelector('.apple-toggle-switch');
    const toggleState = document.getElementById('summaryToggleState');

    if (toggleSwitch && toggleState) {
      toggleState.value = currentType;

      if (currentType === 'temporal') {
        toggleSwitch.classList.add('temporal');
        // CSS에서 색상 관리 - 인라인 스타일 제거
      } else {
        toggleSwitch.classList.remove('temporal');
        // CSS에서 색상 관리 - 인라인 스타일 제거
      }
    }
  };

  // 채팅 모드 토글 함수
  window.toggleChatMode = function () {
    // 모달에서만 실행 가능
    if (!window.Core?.state?.isModalView) {
      return;
    }

    // 기존 ChatUI 토글 함수 호출
    if (window.ChatUI && typeof window.ChatUI.toggleChatMode === 'function') {
      window.ChatUI.toggleChatMode();
    }

    // UI 토글 상태 업데이트
    if (window.updateChatToggleUI) {
      window.updateChatToggleUI();
    }
  };

  // 채팅 토글 UI 상태 업데이트 함수
  window.updateChatToggleUI = function () {
    const currentMode = window.Core?.state?.chatMode || 'rag';
    const toggleSwitch = document.querySelector('.apple-chat-toggle');
    const toggleSlider = document.getElementById('chatToggleSlider');
    const toggleState = document.getElementById('chatToggleState');



    if (toggleSwitch && toggleSlider && toggleState) {
      // 'chat' 모드를 'general'로 매핑
      toggleState.value = currentMode === 'rag' ? 'document' : 'general';

      if (currentMode === 'chat') { // 'chat' 모드일 때 'general' 스타일 적용
        toggleSwitch.classList.add('general');
        // CSS에서 색상 관리 - 인라인 스타일 제거

      } else {
        toggleSwitch.classList.remove('general');
        // CSS에서 색상 관리 - 인라인 스타일 제거

      }
    }
  };

})(); // IIFE 닫기