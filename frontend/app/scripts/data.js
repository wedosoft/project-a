/**
 * 데이터 처리 및 캐시 관리 모듈 (Data)
 *
 * Freshdesk Custom App - Prompt Canvas
 * 이 파일은 모든 데이터 처리, 캐시 관리, 백엔드 통신을 담당합니다.
 *
 * 주요 기능:
 * - 티켓 데이터 로드 및 캐싱
 * - 유사 티켓 및 추천 솔루션 데이터 관리
 * - 백엔드 API 통신 및 응답 처리
 * - 프롬프트 전송 및 AI 응답 처리
 * - 전역 데이터 캐시 관리 및 무효화
 * - 모의 데이터 생성 (개발/테스트용)
 *
 * 의존성:
 * - GlobalState: 전역 상태 및 데이터 캐시
 * - API: 백엔드 API 통신
 * - Utils: 유틸리티 함수
 *
 * @namespace Data
 * @author Freshdesk Custom App Team
 * @since 1.0.0
 */

// Data 모듈 정의 - 모든 데이터 관련 함수를 하나의 객체로 관리
window.Data = {
  /**
   * 모의 추천 솔루션 생성
   *
   * 개발 및 테스트 목적으로 모의 추천 솔루션 데이터를 생성합니다.
   * 백엔드 연결이 없거나 테스트 환경에서 사용됩니다.
   *
   * @returns {Array<Object>} 모의 솔루션 배열
   *
   * @example
   * const mockSolutions = Data.generateMockSolutions();
   * console.log(mockSolutions.length); // 3
   */
  generateMockSolutions() {
    return [
      {
        id: 'mock_1',
        title: '일반적인 문제 해결 방법',
        content: '이 문제는 보통 다음과 같이 해결할 수 있습니다...',
        category: '일반',
        relevance_score: 0.8,
        source: '지식베이스',
        type: 'solution',
      },
      {
        id: 'mock_2',
        title: 'FAQ 답변',
        content: '자주 묻는 질문에 대한 답변입니다...',
        category: 'FAQ',
        relevance_score: 0.7,
        source: 'FAQ',
        type: 'solution',
      },
      {
        id: 'mock_3',
        title: '단계별 가이드',
        content: '문제 해결을 위한 단계별 가이드입니다...',
        category: '가이드',
        relevance_score: 0.6,
        source: '사용자 매뉴얼',
        type: 'solution',
      },
    ];
  },

  /**
   * 티켓 상세 정보 로드 및 UI 업데이트
   *
   * Freshdesk API에서 현재 티켓의 상세 정보를 가져와서
   * UI에 표시합니다. 백엔드 호출 없이 클라이언트 사이드에서만 처리됩니다.
   *
   * @param {Object} client - Freshdesk client 객체
   * @returns {Promise<void>} 비동기 처리 완료
   *
   * @example
   * await Data.loadTicketDetails(app.client);
   */
  async loadTicketDetails(client) {
    try {
      console.log('📋 티켓 상세 정보 확인 시작 (백엔드 호출 없음)');

      // 티켓 ID 가져오기
      const ticketData = await client.data.get('ticket');

      if (ticketData && ticketData.ticket) {
        const basicTicketInfo = ticketData.ticket;
        console.log('✅ 기본 티켓 정보 확인 완료:', basicTicketInfo);

        // 전역 상태에서 캐시된 데이터 확인
        const globalData = GlobalState.getGlobalTicketData();

        // 캐시된 데이터가 있고 최신인지 확인
        if (
          globalData.cached_ticket_id === basicTicketInfo.id &&
          globalData.summary &&
          GlobalState.isGlobalDataValid()
        ) {
          console.log('⚡ 캐시된 데이터 사용 가능');
          return;
        }

        // 새로운 티켓인 경우 캐시 초기화
        if (globalData.cached_ticket_id !== basicTicketInfo.id) {
          console.log('🆕 새로운 티켓 감지 → 캐시 초기화');
          GlobalState.resetGlobalTicketCache();
        }

        // 백엔드 호출 없이 기본 정보만 저장
        GlobalState.updateGlobalTicketData(basicTicketInfo.id, 'cached_ticket_id');
        GlobalState.updateGlobalTicketData(basicTicketInfo, 'ticket_info');
        console.log('ℹ️ 백엔드 호출 없이 기본 정보만 저장');
      } else {
        console.warn('⚠️ 기본 티켓 정보를 찾을 수 없음');
      }
    } catch (error) {
      console.error('❌ 티켓 상세 정보 확인 오류:', error);
    }
  },

  /**
   * 추천 해결책 로드
   *
   * 티켓과 관련된 추천 해결책을 로드하고 표시합니다.
   * 캐시된 데이터가 있으면 재사용하고, 없으면 모의 데이터를 사용합니다.
   *
   * @param {Object} ticket - 티켓 정보 객체
   *
   * @example
   * Data.loadSuggestedSolutions(currentTicket);
   */
  loadSuggestedSolutions(ticket) {
    const resultsElement = document.getElementById('suggested-solutions-list');
    if (resultsElement) {
      resultsElement.innerHTML = '<div class="placeholder-text">추천 해결책을 로드하는 중...</div>';
    }

    try {
      console.log('💡 추천 해결책 로드 시작');

      // 캐시된 데이터가 있고 같은 티켓인 경우 재사용
      const globalData = GlobalState.getGlobalTicketData();
      if (
        globalData.cached_ticket_id === ticket.id &&
        globalData.recommended_solutions.length > 0
      ) {
        console.log('🔄 캐시된 추천 솔루션 데이터 사용');
        this.displaySuggestedSolutions(globalData.recommended_solutions);
        return;
      }

      // 캐시된 데이터가 없거나 다른 티켓인 경우에만 API 호출
      console.log('⚠️ 추천 솔루션이 캐시에 없음 - /init 엔드포인트에서 이미 받았어야 하는 데이터');

      // /init 엔드포인트에서 이미 모든 데이터를 받았어야 하므로,
      // 별도 API 호출 대신 모의 데이터 표시
      console.log('🔄 모의 데이터로 폴백');
      this.displaySuggestedSolutions(this.generateMockSolutions());

      // 캐시 업데이트 (모의 데이터로)
      GlobalState.updateGlobalTicketData(this.generateMockSolutions(), 'recommended_solutions');
      GlobalState.updateGlobalTicketData(ticket.id, 'cached_ticket_id');
    } catch (error) {
      console.error('❌ 추천 솔루션 로드 오류:', error);
      // 폴백: 모의 데이터 표시
      this.displaySuggestedSolutions(this.generateMockSolutions());
    }
  },

  // 티켓 페이지 로드 시 백그라운드에서 데이터 미리 준비하는 함수
  async preloadTicketDataOnPageLoad(client) {
    try {
      // FDK 모달 컨텍스트 감지 - 모달에서는 백그라운드 데이터 로딩 완전 금지
      if (typeof window.isFDKModal !== 'undefined' && window.isFDKModal) {
        return false; // 모달에서는 어떤 백엔드 호출도 하지 않음
      }
      
      // 모듈 로딩 상태 확인 - 초기 시점
      if (!window.API) {
        // API 모듈 로딩을 위한 추가 대기 시간
        return new Promise((resolve) => {
          setTimeout(async () => {
            if (window.API) {
              const result = await this.preloadTicketDataOnPageLoad(client);
              resolve(result);
            } else {
              console.error('❌ API 모듈이 여전히 로드되지 않음');
              resolve(false);
            }
          }, 1000);
        });
      }

      // 더 안전한 FDK API 접근을 위한 지연 시간 증가 및 단계적 검증
      return await new Promise((resolve) => {
        setTimeout(async () => {
          try {
            // 1단계: FDK 클라이언트가 준비되었는지 확인
            if (!client || typeof client.instance === 'undefined') {
              console.warn('⚠️ FDK 클라이언트가 아직 준비되지 않음');
              resolve(false);
              return;
            }

            // 2단계: 컨텍스트 확인 (안전한 방법)
            let ctx;
            try {
              ctx = await client.instance.context();
              console.log('🔍 페이지 컨텍스트 확인 성공:', ctx);
            } catch (contextError) {
              console.warn('⚠️ 컨텍스트 확인 실패, 기본적으로 티켓 페이지로 가정하고 진행:', contextError);
              // 컨텍스트 확인 실패 시에도 티켓 페이지로 가정하고 계속 진행
              ctx = { location: 'ticket_details' }; // 기본값으로 설정
            }

          // 3단계: 티켓 페이지인지 확인 (더 관대한 조건)
          const isTicketPage =
            !ctx || // 컨텍스트가 없으면 티켓 페이지로 가정
            !ctx.location || // location이 없으면 티켓 페이지로 가정
            ctx.location.includes('ticket') || 
            ctx.location === 'ticket_top_navigation' ||
            ctx.location === 'ticket_details' ||
            ctx.location === 'cti_global_sidebar'; // 다양한 티켓 관련 위치 포함

          if (isTicketPage) {
            console.log('📋 티켓 페이지로 판단됨 → 데이터 로드 시작');

            // 4단계: 티켓 데이터 안전하게 가져오기
            let ticketData;
            try {
              ticketData = await client.data.get('ticket');
            } catch (dataError) {
              console.warn('⚠️ 티켓 데이터 접근 실패 - 재시도 또는 기본값 사용:', dataError);
              // 티켓 데이터 접근 실패 시에도 진행을 시도 (백엔드에서 티켓 정보를 다시 가져올 수 있음)
              ticketData = { ticket: { id: 'unknown' } };
            }

            if (ticketData && ticketData.ticket && ticketData.ticket.id !== 'unknown') {
              const currentTicketId = ticketData.ticket.id;

              // 5단계: 캐시 확인 및 백엔드 호출
              const globalData = GlobalState.getGlobalTicketData();
              if (
                globalData.cached_ticket_id === currentTicketId &&
                globalData.summary &&
                !this.isDataStale()
              ) {
                console.log('✅ 이미 캐시된 데이터 존재 → 백그라운드 로드 스킵');
                resolve(true);
                return;
              }

              // 중복 호출 방지
              if (GlobalState.getGlobalLoading()) {
                console.log('⚠️ 이미 로딩 중이므로 백그라운드 로드 스킵');
                resolve(true);
                return;
              }

              console.log('🚀 백그라운드에서 새로운 티켓 데이터 로드 중...', currentTicketId);

              // 6단계: 백엔드 호출 (FDK와 독립적)
              try {
                GlobalState.resetGlobalTicketCache();
                const result = await this.loadInitialDataFromBackend(client, ticketData.ticket);
                
                // 백엔드 호출 결과 확인 후 적절한 메시지 표시
                const errorState = GlobalState.getGlobalError();
                if (result && !errorState.hasError) {
                  console.log(
                    '✅ 백그라운드 데이터 로드 완료 → 앱 아이콘 클릭 시 즉시 모달 표시 가능'
                  );
                  resolve(true);
                } else {
                  console.warn('⚠️ 백엔드 데이터 로드 실패 → 모달에서 재시도 가능');
                  resolve(false);
                }
              } catch (backendError) {
                console.warn('⚠️ 백엔드 호출 실패:', backendError);
                resolve(false);
              }
            } else {
              console.log('⚠️ 티켓 정보 없음 → 백그라운드 로드 스킵');
              // 티켓 정보가 없더라도 최소한의 백엔드 호출을 시도해볼 수 있음
              console.log('🔄 백엔드 연결 상태 확인 및 호출 시도');
              try {
                // 먼저 백엔드 연결 상태 확인
                if (window.API && window.API.checkBackendConnection) {
                  const isConnected = await window.API.checkBackendConnection(client);
                  if (!isConnected) {
                    console.warn('⚠️ 백엔드 서버 연결 불가 - 오프라인 모드로 전환');
                    resolve(false);
                    return;
                  }
                }
                
                // 백엔드 연결이 가능한 경우 API 호출
                const result = await this.loadInitialDataFromBackend(client, { id: 'current' });
                resolve(result ? true : false);
              } catch (backendError) {
                console.warn('⚠️ 백엔드 호출 실패:', backendError);
                resolve(false);
              }
            }
          } else {
            // 티켓 페이지가 아닌 경우 백그라운드 로드 스킵
            resolve(false);
          }
          resolve(true);
        } catch (error) {
          resolve(false);
        }
      }, 500); // 500ms로 단축 - FDK 기본 초기화 대기
      });
    } catch (error) {
      return false;
    }
  },

  /**
   * 백그라운드 데이터 로드
   *
   * 앱이 초기화된 후 백그라운드에서 티켓 관련 데이터를 로드합니다.
   * 컨텍스트 확인, 티켓 페이지 검증, 캐시 확인 등의 단계를 거쳐
   * 필요한 경우에만 백엔드 API를 호출합니다.
   *
   * @param {Object} client - Freshdesk client 객체
   * @returns {Promise<void>} 비동기 처리 완료
   *
   * @description
   * 다음 단계를 순서대로 수행합니다:
   * 1. 클라이언트 컨텍스트 확인
   * 2. 티켓 페이지 여부 확인
   * 3. 티켓 데이터 안전 조회
   * 4. 캐시 상태 확인
   * 5. 필요시 백엔드 데이터 로드
   *
   * @example
   * Data.performBackgroundDataLoad(app.client);
   */
  async performBackgroundDataLoad(client) {
    try {
      console.log('🔄 백그라운드 데이터 로드 시작');

      // FDK 클라이언트가 준비되었는지 확인
      if (!client || typeof client.instance === 'undefined') {
        console.warn('⚠️ FDK 클라이언트가 아직 준비되지 않음');
        return;
      }

      // 컨텍스트 확인
      let ctx;
      try {
        ctx = await client.instance.context();
        console.log('🔍 페이지 컨텍스트 확인 성공:', ctx);
      } catch (contextError) {
        console.warn('⚠️ 컨텍스트 확인 실패, 기본 로직으로 진행:', contextError);
        // 기본 로직으로 진행 (티켓 페이지로 가정)
      }

      // 티켓 페이지인지 확인
      const isTicketPage =
        ctx.location &&
        (ctx.location.includes('ticket') || ctx.location === 'ticket_top_navigation');

      if (!isTicketPage) {
        console.log('📄 티켓 페이지가 아님 → 백그라운드 로드 스킵');
        return;
      }

      console.log('📋 티켓 페이지 확인됨 → 데이터 로드 시작');

      // 티켓 데이터 안전하게 가져오기
      let ticketData;
      try {
        ticketData = await client.data.get('ticket');
      } catch (dataError) {
        console.warn('⚠️ 티켓 데이터 접근 실패 (EventAPI 오류 가능성):', dataError);
        return;
      }

      if (ticketData && ticketData.ticket) {
        const currentTicketId = ticketData.ticket.id;

        // 캐시 확인 및 백엔드 호출
        const globalData = GlobalState.getGlobalTicketData();
        if (
          globalData.cached_ticket_id === currentTicketId &&
          globalData.summary &&
          !this.isDataStale()
        ) {
          console.log('✅ 이미 캐시된 데이터 존재 → 백그라운드 로드 스킵');
          return;
        }

        // 중복 호출 방지
        if (GlobalState.getGlobalLoading()) {
          console.log('⚠️ 이미 로딩 중이므로 백그라운드 로드 스킵');
          return;
        }

        console.log('🚀 백그라운드에서 새로운 티켓 데이터 로드 중...', currentTicketId);

        // 백엔드 호출 (FDK와 독립적)
        try {
          GlobalState.resetGlobalTicketCache();
          await this.loadInitialDataFromBackend(client, ticketData.ticket);
          console.log('✅ 백그라운드 데이터 로드 완료 → 앱 아이콘 클릭 시 즉시 모달 표시 가능');
        } catch (backendError) {
          console.warn('⚠️ 백엔드 호출 실패:', backendError);
        }
      } else {
        console.log('⚠️ 티켓 정보 없음 → 백그라운드 로드 스킵');
      }
    } catch (error) {
      console.warn('⚠️ 백그라운드 데이터 로드 중 예외 발생:', error);
    }
  },

  /**
   * 다단계 재시도 데이터 로드
   *
   * FDK의 불안정성을 고려하여 여러 시점에서 데이터 로드를 재시도합니다.
   * 각 시도는 점진적으로 늦어지는 지연 시간을 가지며,
   * 이미 데이터가 로드된 경우 후속 시도를 자동으로 중단합니다.
   *
   * @param {Object} client - Freshdesk client 객체
   * @returns {void}
   *
   * @description
   * 재시도 일정:
   * - 즉시 시도 (0ms)
   * - 500ms 후 재시도
   * - 1000ms 후 재시도
   * - 2000ms 후 재시도
   * - 3000ms 후 최종 시도
   *
   * @example
   * Data.retryDataLoadWithMultipleAttempts(app.client);
   */
  retryDataLoadWithMultipleAttempts(client) {
    console.log('🎯 적극적인 백그라운드 데이터 로드 전략 시작');

    // 여러 시점에서 안전한 데이터 로드 시도 (점진적 지연)
    const loadAttempts = [
      { delay: 0, label: '즉시 시도' },
      { delay: 500, label: '재시도 1' },
      { delay: 1000, label: '재시도 2' },
      { delay: 2000, label: '재시도 3' },
      { delay: 3000, label: '최종 시도' },
    ];

    loadAttempts.forEach(({ delay, label }) => {
      setTimeout(async () => {
        // 이미 로드된 경우 스킵
        const globalData = GlobalState.getGlobalTicketData();
        if (globalData.cached_ticket_id && globalData.summary) {
          console.log(`✅ ${label}: 이미 데이터 준비됨 - 스킵`);
          return;
        }

        try {
          console.log(`🔄 ${label} (${delay}ms 후) - FDK 안전성 검증 시작`);

          // FDK 안전성 검증
          if (
            !client ||
            typeof client.data === 'undefined' ||
            typeof client.instance === 'undefined'
          ) {
            console.warn(`⚠️ ${label}: FDK 아직 준비 안됨`);
            return;
          }

          // 컨텍스트 확인 (옵션, 실패해도 계속 진행)
          let isTicketPage = false;
          try {
            const ctx = await client.instance.context();
            isTicketPage =
              ctx.location &&
              (ctx.location.includes('ticket') || ctx.location === 'ticket_top_navigation');
            console.log(
              `🔍 ${label}: 컨텍스트 확인 - ${ctx.location} (티켓페이지: ${isTicketPage})`
            );
          } catch (contextError) {
            console.warn(`⚠️ ${label}: 컨텍스트 확인 실패, 티켓 데이터로 추론 시도`);
            isTicketPage = true; // 일단 시도해보기
          }

          // 티켓 데이터 안전하게 가져오기
          if (isTicketPage) {
            const ticketData = await client.data.get('ticket');

            if (ticketData && ticketData.ticket && ticketData.ticket.id) {
              const currentTicketId = ticketData.ticket.id;

              // 캐시 확인 및 중복 호출 방지
              const globalData = GlobalState.getGlobalTicketData();
              if (
                globalData.cached_ticket_id === currentTicketId &&
                globalData.summary &&
                !this.isDataStale()
              ) {
                console.log(`✅ ${label}: 이미 캐시된 데이터 존재 → 스킵`);
                return;
              }

              if (GlobalState.getGlobalLoading()) {
                console.log(`⚠️ ${label}: 이미 로딩 중 → 스킵`);
                return;
              }

              console.log(`🚀 ${label}: 티켓 ID ${currentTicketId} 백엔드 로드 시작`);

              // 백엔드 호출 (FDK와 독립적)
              GlobalState.resetGlobalTicketCache();
              await this.loadInitialDataFromBackend(client, ticketData.ticket);

              console.log(
                `✅ ${label}: 백엔드 데이터 로드 완료! 다음 앱 아이콘 클릭 시 즉시 표시됩니다.`
              );

              // 성공 시 더 이상 시도하지 않도록 플래그 설정
              return;
            } else {
              console.warn(`⚠️ ${label}: 티켓 데이터 없음`);
            }
          } else {
            console.log(`📄 ${label}: 티켓 페이지 아님 - 스킵`);
          }
        } catch (error) {
          console.warn(`⚠️ ${label}: 로드 실패 (${error.message})`);

          // EventAPI 오류는 예상된 상황이므로 덜 심각하게 처리
          if (error.message && error.message.includes('EventAPI')) {
            console.log(`🔧 ${label}: EventAPI 타이밍 이슈 - 나중에 다시 시도`);
          }
        }
      }, delay);
    });

    // 추가 전략: URL 변경 감지
    if (typeof window !== 'undefined') {
      let lastUrl = window.location.href;
      const urlCheckInterval = setInterval(() => {
        if (window.location.href !== lastUrl) {
          lastUrl = window.location.href;
          const globalData = GlobalState.getGlobalTicketData();
          if (
            lastUrl.includes('/tickets/') &&
            (!globalData.cached_ticket_id || !globalData.summary)
          ) {
            console.log('🎯 URL 변경으로 티켓 페이지 진입 감지 → 백그라운드 로드 시도');
            setTimeout(() => {
              this.attemptSingleBackgroundLoad(client, 'URL변경감지');
            }, 1500);
          }
        }
      }, 1000);

      // 10분 후 URL 감지 정리 (메모리 누수 방지)
      setTimeout(() => {
        clearInterval(urlCheckInterval);
        console.log('🧹 URL 변경 감지 종료');
      }, 600000);
    }
  },

  /**
   * 단일 백그라운드 로드 시도
   *
   * 한 번의 백그라운드 데이터 로드를 시도합니다.
   * 캐시 상태 확인, 중복 호출 방지, FDK 안전성 검증을 포함합니다.
   *
   * @param {Object} client - Freshdesk client 객체
   * @param {string} source - 로드 시도 출처 (로깅용)
   * @returns {Promise<void>} 비동기 처리 완료
   *
   * @example
   * await Data.attemptSingleBackgroundLoad(app.client, 'URL변경감지');
   */
  async attemptSingleBackgroundLoad(client, source = '단일시도') {
    try {
      // 캐시 확인
      const globalData = GlobalState.getGlobalTicketData();
      if (globalData.cached_ticket_id && globalData.summary && !this.isDataStale()) {
        console.log(`✅ ${source}: 이미 유효한 캐시 데이터 존재 → 스킵`);
        return;
      }

      // 중복 호출 방지
      if (GlobalState.getGlobalLoading()) {
        console.log(`⚠️ ${source}: 이미 로딩 중 → 스킵`);
        return;
      }

      const ticketData = await client.data.get('ticket');
      if (ticketData && ticketData.ticket && ticketData.ticket.id) {
        console.log(`🔄 ${source}: 백그라운드 로드 시작 (티켓: ${ticketData.ticket.id})`);
        GlobalState.resetGlobalTicketCache();
        await this.loadInitialDataFromBackend(client, ticketData.ticket);
        console.log(`✅ ${source}: 백그라운드 로드 성공`);
      }
    } catch (error) {
      console.warn(`⚠️ ${source}: 백그라운드 로드 실패:`, error.message);
    }
  },

  /**
   * 백엔드에서 초기 데이터를 로드하는 함수 (/init 엔드포인트 호출)
   * @param {Object} client - FDK 클라이언트 객체
   * @param {Object} ticket - 기본 티켓 정보
   * @param {string} agentLanguage - 에이전트 UI 언어 (선택사항)
   * @returns {Promise<Object>} 로드된 데이터 또는 null
   */
  async loadInitialDataFromBackend(client, ticket, agentLanguage = null) {
    try {
      console.log('🚀 백엔드 초기 데이터 로드 시작:', ticket.id);
      
      // 로딩 상태 설정
      GlobalState.setGlobalLoading(true);
      
      // API 모듈이 있는지 확인
      if (!window.API) {
        console.error('❌ API 모듈이 로드되지 않음');
        return false;
      }
      
      // 에이전트 언어가 제공되지 않은 경우 자동 감지
      if (!agentLanguage && window.API.detectAgentLanguage) {
        try {
          agentLanguage = await API.detectAgentLanguage(client);
          console.log(`🌍 에이전트 언어 자동 감지: ${agentLanguage}`);
        } catch (error) {
          console.warn('⚠️ 언어 감지 실패, 기본값 사용:', error);
          agentLanguage = 'en';
        }
      }
      
      // 백엔드 /init 엔드포인트 호출 (에이전트 언어 포함)
      const response = await API.loadInitData(client, ticket.id);
      
      console.log('🔍 백엔드 응답 상세 분석:', {
        response: response,
        type: typeof response,
        keys: response ? Object.keys(response) : null
      });
      
      // 응답 성공 여부 확인 (다양한 응답 형태 지원)
      const isSuccess = response && (
        response.success === true ||  // { success: true, data: ... }
        response.status === 'success' ||  // { status: 'success', data: ... }
        (response.data && !response.error) ||  // { data: ..., error: null }
        (!response.error && Object.keys(response).length > 0)  // 에러가 없고 데이터가 있으면
      );
      
      if (isSuccess) {
        console.log('✅ 백엔드 초기 데이터 로드 성공');
        
        // 응답 데이터 구조 정규화
        let responseData = response.data || response;  // data 필드가 없으면 전체 응답을 데이터로 사용
        
        // 전역 상태에 데이터 저장
        if (responseData) {
          GlobalState.updateGlobalTicketData(ticket.id, 'cached_ticket_id');
          
          if (responseData.summary) {
            GlobalState.updateGlobalTicketData(responseData.summary, 'summary');
          }
          
          if (responseData.similar_tickets) {
            GlobalState.updateGlobalTicketData(responseData.similar_tickets, 'similar_tickets');
          }
          
          if (responseData.recommended_solutions) {
            GlobalState.updateGlobalTicketData(responseData.recommended_solutions, 'recommended_solutions');
          }
          
          // 캐시 유효성 갱신
          GlobalState.updateGlobalTicketData(new Date().toISOString(), 'last_updated');
          
          console.log('📦 저장된 데이터:', {
            ticket_id: ticket.id,
            has_summary: !!responseData.summary,
            similar_tickets_count: responseData.similar_tickets?.length || 0,
            solutions_count: responseData.recommended_solutions?.length || 0
          });
        }
        
        return true;
      } else {
        console.warn('⚠️ 백엔드 초기 데이터 로드 실패:', response);
        
        // 응답 구조 분석을 위한 상세 로깅
        if (response) {
          console.warn('  - response.success:', response.success);
          console.warn('  - response.error:', response.error);
          console.warn('  - response.data:', response.data);
          console.warn('  - response keys:', Object.keys(response));
        } else {
          console.warn('  - 응답이 null 또는 undefined');
        }
        
        // 에러 원인별 구체적인 메시지
        let errorMessage = '알 수 없는 오류가 발생했습니다.';
        if (!response) {
          errorMessage = '서버 응답이 없습니다.';
        } else if (response.error) {
          errorMessage = response.error;
        } else if (response.message) {
          errorMessage = response.message;
        }
        
        GlobalState.setGlobalError(true, errorMessage);
        
        return false;
      }
    } catch (error) {
      console.error('❌ 백엔드 초기 데이터 로드 오류:', error);
      
      // 에러 상태 설정
      GlobalState.setGlobalError(true, '백엔드 연결에 실패했습니다.');
      
      return false;
    } finally {
      // 로딩 상태 해제
      GlobalState.setGlobalLoading(false);
    }
  },

  /**
   * 🚀 Vector DB 단독 모드 - 티켓 초기 데이터 로드
   *
   * /init 엔드포인트를 호출하여 티켓 요약, 유사 티켓, KB 문서를 한번에 가져옵니다.
   * 환경변수 ENABLE_FULL_STREAMING_MODE=true 시 Vector DB에서만 데이터를 조회합니다.
   *
   * @param {Object} client - Freshdesk client 객체
   * @param {string} ticketId - 티켓 ID
   * @returns {Promise<Object>} API 응답 결과
   */
  async loadInitDataVectorOnly(client, ticketId) {
    try {
      console.log(`🚀 Vector DB 단독 모드로 초기 데이터 로드: ${ticketId}`);

      // 캐시 확인
      const globalData = GlobalState.getGlobalTicketData();
      if (
        globalData.cached_ticket_id === ticketId &&
        globalData.summary &&
        globalData.similar_tickets &&
        globalData.kb_documents &&
        GlobalState.isGlobalDataValid()
      ) {
        console.log('⚡ 캐시된 Vector DB 데이터 사용');
        return { ok: true, data: globalData };
      }

      // /init 엔드포인트 호출 - Vector DB 단독 모드
      const response = await API.loadInitData(client, ticketId);

      if (response && response.ok && response.data) {
        const data = response.data;

        // Vector DB 단독 모드 데이터 구조 검증
        console.log('📊 Vector DB 응답 데이터 구조:', {
          hasSummary: !!data.summary,
          similarTicketsCount: data.similar_tickets?.length || 0,
          kbDocumentsCount: data.kb_documents?.length || 0,
          executionTime: data.execution_time,
          searchQualityScore: data.search_quality_score
        });

        // 전역 캐시 업데이트
        GlobalState.updateGlobalTicketData(ticketId, 'cached_ticket_id');
        GlobalState.updateGlobalTicketData(data.summary, 'summary');
        GlobalState.updateGlobalTicketData(data.similar_tickets || [], 'similar_tickets');
        GlobalState.updateGlobalTicketData(data.kb_documents || [], 'kb_documents');
        GlobalState.updateGlobalTicketData(Date.now(), 'last_updated');

        // 성능 메트릭 저장
        if (data.execution_time) {
          GlobalState.updateGlobalTicketData(data.execution_time, 'execution_time');
        }
        if (data.search_quality_score) {
          GlobalState.updateGlobalTicketData(data.search_quality_score, 'search_quality_score');
        }

        console.log('✅ Vector DB 단독 모드 데이터 로드 완료');
        return response;
      } else {
        console.error('❌ Vector DB 응답 데이터 없음');
        return { ok: false, error: 'No data received from Vector DB' };
      }
    } catch (error) {
      console.error('❌ Vector DB 단독 모드 데이터 로드 실패:', error);
      return { ok: false, error: error.message };
    }
  },

  /**
   * 🔄 하이브리드 모드 호환성 유지 (기존 로직)
   *
   * ENABLE_FULL_STREAMING_MODE=false 시 기존 하이브리드 로직을 사용합니다.
   *
   * @param {Object} client - Freshdesk client 객체
   * @param {string} ticketId - 티켓 ID
   * @returns {Promise<Object>} API 응답 결과
   */
  async loadInitDataHybrid(client, ticketId) {
    // 기존 하이브리드 로직 (100% 보존)
    return await API.loadInitData(client, ticketId);
  },

  /**
   * 🎯 통합 초기 데이터 로드 (환경변수 기반 자동 분기)
   *
   * 백엔드의 환경변수 설정에 따라 Vector DB 단독 또는 하이브리드 모드로 자동 분기됩니다.
   *
   * @param {Object} client - Freshdesk client 객체
   * @param {string} ticketId - 티켓 ID
   * @returns {Promise<Object>} API 응답 결과
   */
  async preloadTicketData(client, ticketId) {
    try {
      console.log(`🎯 통합 초기 데이터 로드 시작: ${ticketId}`);

      // 환경변수는 백엔드에서 자동으로 분기되므로 프론트엔드는 단일 API 호출
      const response = await this.loadInitDataVectorOnly(client, ticketId);

      if (response && response.ok) {
        // UI 업데이트 - 모든 데이터가 준비됨
        if (window.UI && window.UI.updateTicketSummary && response.data.summary) {
          window.UI.updateTicketSummary(response.data.summary);
        }

        // 유사 티켓 표시
        if (response.data.similar_tickets && response.data.similar_tickets.length > 0) {
          this.displaySimilarTickets(response.data.similar_tickets);
        }

        // KB 문서 표시
        if (response.data.kb_documents && response.data.kb_documents.length > 0) {
          this.displayKBDocuments(response.data.kb_documents);
        }

        console.log(`✅ 통합 초기 데이터 로드 완료: ${ticketId}`);
      }

      return response;
    } catch (error) {
      console.error('❌ 통합 초기 데이터 로드 실패:', error);
      return { ok: false, error: error.message };
    }
  },

  /**
   * 🎫 Vector DB 기반 유사 티켓 표시
   *
   * Vector DB에서 조회된 유사 티켓 데이터를 UI에 표시합니다.
   *
   * @param {Array} similarTickets - Vector DB에서 조회된 유사 티켓 배열
   */
  displaySimilarTickets(similarTickets) {
    const resultsElement = document.getElementById('similar-tickets-list');
    if (!resultsElement) {
      console.warn('⚠️ similar-tickets-list 엘리먼트를 찾을 수 없음');
      return;
    }

    if (!similarTickets || similarTickets.length === 0) {
      resultsElement.innerHTML = '<div class="no-results">유사한 티켓이 없습니다.</div>';
      return;
    }

    let html = '';
    similarTickets.forEach((ticket, index) => {
      // Vector DB 메타데이터 구조에 맞게 표시
      const metadata = ticket.metadata || ticket;
      const title = metadata.subject || metadata.title || `티켓 #${metadata.ticket_id}`;
      const status = metadata.status || 'Unknown';
      const priority = metadata.priority || 'Normal';
      const agentName = metadata.agent_name || 'Unassigned';
      const score = ticket.score || ticket.relevance_score || 0;
      const createdAt = metadata.created_at || metadata.created_date;

      html += `
        <div class="ticket-item" data-ticket-id="${metadata.ticket_id || index}">
          <div class="ticket-header">
            <h4 class="ticket-title">${title}</h4>
            <span class="confidence-score">${(score * 100).toFixed(1)}%</span>
          </div>
          <div class="ticket-metadata">
            <span class="status status-${status.toLowerCase()}">${status}</span>
            <span class="priority priority-${priority.toLowerCase()}">${priority}</span>
            <span class="agent">${agentName}</span>
          </div>
          ${createdAt ? `<div class="ticket-date">${new Date(createdAt).toLocaleDateString('ko-KR')}</div>` : ''}
          <div class="ticket-preview">
            ${(metadata.text || metadata.description_text || '').substring(0, 150)}...
          </div>
        </div>
      `;
    });

    resultsElement.innerHTML = html;
    console.log(`✅ Vector DB 유사 티켓 ${similarTickets.length}개 표시 완료`);
  },

  /**
   * 📚 Vector DB 기반 KB 문서 표시
   *
   * Vector DB에서 조회된 KB 문서 데이터를 UI에 표시합니다.
   *
   * @param {Array} kbDocuments - Vector DB에서 조회된 KB 문서 배열
   */
  displayKBDocuments(kbDocuments) {
    const resultsElement = document.getElementById('suggested-solutions-list');
    if (!resultsElement) {
      console.warn('⚠️ suggested-solutions-list 엘리먼트를 찾을 수 없음');
      return;
    }

    if (!kbDocuments || kbDocuments.length === 0) {
      resultsElement.innerHTML = '<div class="no-results">관련 지식베이스 문서가 없습니다.</div>';
      return;
    }

    let html = '';
    kbDocuments.forEach((doc, index) => {
      // Vector DB 메타데이터 구조에 맞게 표시
      const metadata = doc.metadata || doc;
      const title = metadata.title || `문서 #${index + 1}`;
      const category = metadata.category || 'General';
      const folder = metadata.folder || '';
      const status = metadata.status || 'published';
      const score = doc.score || doc.relevance_score || 0;
      const description = metadata.description || metadata.text || '';

      html += `
        <div class="kb-item" data-article-id="${metadata.article_id || index}">
          <div class="kb-header">
            <h4 class="kb-title">${title}</h4>
            <span class="confidence-score">${(score * 100).toFixed(1)}%</span>
          </div>
          <div class="kb-metadata">
            <span class="category">${category}</span>
            ${folder ? `<span class="folder">${folder}</span>` : ''}
            <span class="status status-${status.toLowerCase()}">${status}</span>
          </div>
          <div class="kb-description">
            ${description.substring(0, 200)}...
          </div>
          <div class="kb-actions">
            <button class="btn-view-kb" data-article-id="${metadata.article_id}">
              전체 보기
            </button>
          </div>
        </div>
      `;
    });

    resultsElement.innerHTML = html;

    // KB 문서 전체 보기 이벤트 리스너 추가
    resultsElement.querySelectorAll('.btn-view-kb').forEach(button => {
      button.addEventListener('click', (e) => {
        const articleId = e.target.getAttribute('data-article-id');
        this.showKBDocumentModal(articleId, kbDocuments);
      });
    });

    console.log(`✅ Vector DB KB 문서 ${kbDocuments.length}개 표시 완료`);
  },

  /**
   * 📖 KB 문서 상세 모달 표시
   *
   * KB 문서의 전체 내용을 모달로 표시합니다.
   *
   * @param {string} articleId - 문서 ID
   * @param {Array} kbDocuments - KB 문서 배열
   */
  showKBDocumentModal(articleId, kbDocuments) {
    const doc = kbDocuments.find(d => (d.metadata && d.metadata.article_id) === articleId);
    if (!doc) {
      console.warn('⚠️ KB 문서를 찾을 수 없음:', articleId);
      return;
    }

    const metadata = doc.metadata || doc;
    const modalHtml = `
      <div class="kb-modal-overlay" id="kb-modal">
        <div class="kb-modal-content">
          <div class="kb-modal-header">
            <h2>${metadata.title || '제목 없음'}</h2>
            <button class="kb-modal-close">&times;</button>
          </div>
          <div class="kb-modal-metadata">
            <span class="category">${metadata.category || 'General'}</span>
            ${metadata.folder ? `<span class="folder">${metadata.folder}</span>` : ''}
            <span class="status">${metadata.status || 'published'}</span>
          </div>
          <div class="kb-modal-body">
            ${metadata.description || metadata.text || '내용이 없습니다.'}
          </div>
        </div>
      </div>
    `;

    // 모달 HTML 추가
    document.body.insertAdjacentHTML('beforeend', modalHtml);

    // 모달 닫기 이벤트
    const modal = document.getElementById('kb-modal');
    const closeBtn = modal.querySelector('.kb-modal-close');
    
    const closeModal = () => modal.remove();
    
    closeBtn.addEventListener('click', closeModal);
    modal.addEventListener('click', (e) => {
      if (e.target === modal) closeModal();
    });

    console.log(`📖 KB 문서 모달 표시: ${metadata.title}`);
  },

  /**
   * 티켓 페이지에서 벗어날 때 데이터 초기화
   *
   * 사용자가 티켓 페이지를 떠날 때 데이터를 초기화하여
   * 다음 번에 페이지에 들어왔을 때 새로운 데이터로 로드되도록 합니다.
   *
   * @example
   * Data.resetDataOnTicketPageExit();
   */
  resetDataOnTicketPageExit() {
    console.log('🔄 티켓 페이지 이탈 감지 → 데이터 초기화');

    // 전역 상태 리셋
    GlobalState.resetGlobalTicketCache();

    // 추가적인 클린업 작업 수행 가능
    // 예: 구독 중인 이벤트 해제, 타이머 정리 등
  },

  /**
   * 데이터 압축 및 최적화
   */
  compressTicketData(tickets) {
    // 불필요한 필드 제거 및 데이터 압축
    return tickets.map((ticket) => ({
      id: ticket.id,
      s: ticket.subject,
      d: this.truncateText(ticket.description, 200),
      st: ticket.status,
      p: ticket.priority,
      ca: ticket.created_at,
      ua: ticket.updated_at,
      t: ticket.tags.slice(0, 5), // 최대 5개 태그만
      us: ticket.urgency_score,
    }));
  },

  /**
   * 압축된 데이터 복원
   */
  decompressTicketData(compressedTickets) {
    return compressedTickets.map((ticket) => ({
      id: ticket.id,
      subject: ticket.s,
      description: ticket.d,
      status: ticket.st,
      priority: ticket.p,
      created_at: ticket.ca,
      updated_at: ticket.ua,
      tags: ticket.t,
      urgency_score: ticket.us,
    }));
  },

  /**
   * 유틸리티 함수들
   */
  sanitizeText(text) {
    return text
      .replace(/<[^>]*>/g, '')
      .replace(/\s+/g, ' ')
      .trim();
  },

  truncateText(text, maxLength) {
    return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
  },

  normalizeStatus(status) {
    const statusMap = {
      2: 'open',
      3: 'pending',
      4: 'resolved',
      5: 'closed',
    };
    return statusMap[status] || 'unknown';
  },

  normalizePriority(priority) {
    const priorityMap = {
      1: 'low',
      2: 'medium',
      3: 'high',
      4: 'urgent',
    };
    return priorityMap[priority] || 'medium';
  },

  parseDate(dateString) {
    try {
      return new Date(dateString).toISOString();
    } catch {
      return new Date().toISOString();
    }
  },

  extractTags(tags) {
    return Array.isArray(tags) ? tags.filter((tag) => tag && tag.length > 0) : [];
  },

  categorizeTicket(ticket) {
    // 간단한 카테고리 분류 로직
    const subject = (ticket.subject || '').toLowerCase();
    if (subject.includes('bug') || subject.includes('error')) return 'bug';
    if (subject.includes('feature') || subject.includes('request')) return 'feature';
    if (subject.includes('question') || subject.includes('help')) return 'support';
    return 'general';
  },

  calculateUrgencyScore(ticket) {
    let score = 0;
    if (ticket.priority === 4) score += 40; // urgent
    if (ticket.priority === 3) score += 20; // high
    if (ticket.status === 2) score += 10; // open
    // 생성 후 24시간 이내면 추가 점수
    const hoursOld = (Date.now() - new Date(ticket.created_at)) / (1000 * 60 * 60);
    if (hoursOld < 24) score += 15;
    return Math.min(100, score);
  },

  createFallbackTicket(ticket) {
    return {
      id: ticket.id || 'unknown',
      subject: '데이터 오류',
      description: '티켓 데이터를 처리할 수 없습니다.',
      status: 'unknown',
      priority: 'medium',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      tags: [],
      category: 'error',
      urgency_score: 0,
    };
  },

  /**
   * 캐시된 데이터가 오래되었는지 확인
   *
   * 전역 상태에 저장된 데이터의 최종 업데이트 시간을 확인하여
   * 데이터가 오래되었는지 판단합니다.
   *
   * @returns {boolean} 데이터가 오래되었으면 true, 아니면 false
   */
  isDataStale() {
    try {
      const globalData = GlobalState.getGlobalTicketData();
      
      if (!globalData.last_updated) {
        return true; // 업데이트 시간이 없으면 오래된 데이터로 간주
      }
      
      const lastUpdated = new Date(globalData.last_updated);
      const now = new Date();
      const diffInMinutes = (now - lastUpdated) / (1000 * 60);
      
      // 10분이 지나면 오래된 데이터로 간주
      return diffInMinutes > 10;
    } catch (error) {
      console.warn('[Data] 데이터 유효성 확인 중 오류:', error);
      return true; // 오류 발생 시 오래된 데이터로 간주
    }
  },

  /**
   * 업데이트 확인 (실제 구현에서는 API 호출)
   */
  async checkForUpdates() {
    // 실제로는 서버에 업데이트 확인 요청
    // 여기서는 랜덤으로 시뮬레이션
    return await Promise.resolve(Math.random() < 0.1); // 10% 확률로 업데이트 있음
  },
};

// Data 모듈 export - 주요 함수들을 Data 네임스페이스로 노출
// (이미 Data 객체 내부에 정의되어 있으므로 별도 할당 불필요)

// 의존성 확인 함수 - 다른 모듈에서 Data 모듈 사용 가능 여부 체크
Data.isAvailable = function () {
  return typeof GlobalState !== 'undefined' && typeof API !== 'undefined';
};

// 모듈 등록 (로그 없음)

// 모듈 의존성 시스템에 등록
if (typeof ModuleDependencyManager !== 'undefined') {
  ModuleDependencyManager.registerModule('data', Object.keys(Data).length);
}
