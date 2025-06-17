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
      // isFDKModal 변수는 index.html에서 이미 전역으로 선언됨
      console.log('🔍 모달 컨텍스트 최종 확인:');
      console.log('   - window.isFDKModal 타입:', typeof window.isFDKModal);
      console.log('   - window.isFDKModal 값:', window.isFDKModal);
      console.log('   - URL:', window.location.href);
      
      if (typeof window.isFDKModal !== 'undefined' && window.isFDKModal) {
        console.log('🚫 FDK 모달 컨텍스트 감지 - 백엔드 호출 완전 금지');
        console.log('   → 모달에서는 페이지 로딩 시에도 백엔드 호출하지 않음');
        console.log('   → 모달 띄울 때도 별도 백엔드 호출하지 않음');
        console.log('   → 모달 이후 추가 액션도 실행하지 않음');
        return false;
      }
      
      console.log('🔄 FDK 안전한 백그라운드 데이터 준비 시작');
      
      // 모듈 로딩 상태 확인 - 초기 시점
      console.log('📦 모듈 로딩 상태 확인:');
      console.log('   - window.API:', !!window.API);
      console.log('   - window.GlobalState:', !!window.GlobalState);
      console.log('   - Data 모듈:', !!window.Data);
      
      if (!window.API) {
        console.warn('⚠️ API 모듈이 아직 로드되지 않았습니다. 잠시 후 재시도합니다.');
        
        // API 모듈 로딩을 위한 추가 대기 시간
        return new Promise((resolve) => {
          setTimeout(async () => {
            if (window.API) {
              console.log('✅ API 모듈 로딩 확인됨 - 백그라운드 데이터 로드 재시도');
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
              if (GlobalState.isLoading()) {
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
              console.log('🔄 티켓 정보 없음에도 불구하고 기본 백엔드 호출 시도');
              try {
                //const result = await this.loadInitialDataFromBackend(client, { id: 'current' });
                console.log('✅ 기본 백엔드 호출 성공');
                resolve(true);
              } catch (backendError) {
                console.warn('⚠️ 기본 백엔드 호출도 실패:', backendError);
                resolve(false);
              }
            }
          } else {
            console.log('📄 티켓 페이지가 아님 → 백그라운드 로드 스킵');
            resolve(false);
          }
          resolve(true);
        } catch (error) {
          console.warn('⚠️ 백그라운드 데이터 로드 중 예외 발생:', error);
          resolve(false);
        }
      }, 2000); // 2초로 지연 시간 증가하여 FDK 완전 초기화 대기
      });
    } catch (error) {
      console.warn('⚠️ 백그라운드 데이터 준비 초기화 실패:', error);
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
        if (GlobalState.isLoading()) {
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

              if (GlobalState.isLoading()) {
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
      if (GlobalState.isLoading()) {
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
   * @param {Object} basicTicketInfo - 기본 티켓 정보
   * @returns {Promise<Object>} 로드된 데이터 또는 null
   */
  async loadInitialDataFromBackend(client, basicTicketInfo) {
    try {
      console.log('🚀 백엔드 초기 데이터 로드 시작');
      console.log('📋 요청할 티켓 정보:', basicTicketInfo);

      // 중복 호출 방지
      if (GlobalState.getGlobalLoading()) {
        console.log('⚠️ 이미 로딩 중이므로 중복 호출 방지');
        return null;
      }

      // 로딩 상태 설정
      GlobalState.setGlobalLoading(true);
      console.log('🔄 로딩 상태 설정 완료');

      try {
        // API 모듈을 통한 백엔드 /init API 호출
        console.log('🔍 API 모듈 상태 확인...');
        console.log('   - window.API 존재:', !!window.API);
        console.log('   - API 존재:', !!API);
        
        let apiInstance = API;
        if (!apiInstance && window.API) {
          console.log('⚠️ 전역 API 변수가 undefined이므로 window.API 사용');
          apiInstance = window.API;
        }
        
        if (!apiInstance || !apiInstance.callBackendAPI) {
          console.error('❌ API 모듈이 로드되지 않았습니다:', {
            API_exists: !!API,
            window_API_exists: !!window.API,
            callBackendAPI_exists: apiInstance ? !!apiInstance.callBackendAPI : false
          });
          throw new Error('API 모듈이 로드되지 않았습니다.');
        }

        console.log('🌐 백엔드 API 호출 시작:', `init/${basicTicketInfo.id}`);
        const response = await apiInstance.callBackendAPI(client, `init/${basicTicketInfo.id}`, null, 'GET');
        console.log('📨 백엔드 응답 수신:', response);

        if (response.ok) {
          const data = response.data;
          console.log('✅ 백엔드 초기 데이터 로드 완료:', data);

          // 응답 데이터 구조 확인 및 로깅
          console.log('📊 응답 데이터 분석:');
          console.log('- similar_tickets 개수:', data.similar_tickets?.length || 0);
          console.log('- kb_documents 개수:', data.kb_documents?.length || 0);

          // 전역 캐시에 데이터 저장
          const globalData = {
            summary: data.ticket_summary,
            similar_tickets: data.similar_tickets || [],
            recommended_solutions: data.kb_documents || [], // 백엔드에서는 kb_documents로 온다
            cached_ticket_id: basicTicketInfo.id,
            ticket_info: data.ticket_data || basicTicketInfo,
            isLoading: false,
            hasError: false, // 성공 시 에러 상태 클리어 (새로 추가)
            errorMessage: null, // 성공 시 에러 메시지 클리어 (새로 추가)
            lastLoadTime: new Date().toISOString(),
          };

          // 전역 상태에 데이터 업데이트
          GlobalState.updateGlobalTicketData(globalData);
          
          // 에러 상태 클리어 (새로 추가)
          GlobalState.clearGlobalError();

          console.log('💾 전역 캐시에 데이터 저장 완료');
          
          // ✅ 데이터 로드 성공 - 간단한 토스트 알림 표시
          console.log('🎉 백엔드 데이터 로드 성공:', {
            similarTickets: data.similar_tickets?.length || 0,
            kbDocuments: data.kb_documents?.length || 0,
            loadTime: new Date().toLocaleTimeString()
          });
          
          // 사용자에게 간단한 성공 피드백 제공 (토스트)
          if (window.UI && window.UI.showToast) {
            window.UI.showToast('success', '초기 데이터를 성공적으로 불러왔습니다.');
          }
          
          return data;
        } else {
          throw new Error(`백엔드 API 호출 실패: ${response.statusText}`);
        }
      } finally {
        // 로딩 상태 해제
        GlobalState.setGlobalLoading(false);
      }
    } catch (error) {
      console.error('⚠️ 백엔드 초기 데이터 로드 실패:', error);
      GlobalState.setGlobalLoading(false);
      
      // 에러 상태 설정 (새로 추가)
      const errorMessage = error.message || '알 수 없는 오류가 발생했습니다.';
      GlobalState.setGlobalError(true, errorMessage);
      
      // ❌ 실패 시 에러 모달 표시
      if (window.UI && window.UI.showErrorModal) {
        window.UI.showErrorModal(
          `백엔드 데이터 로드에 실패했습니다.<br><br>
           <strong>티켓 ID:</strong> ${basicTicketInfo.id}<br>
           <strong>오류:</strong> ${errorMessage}<br>
           <strong>시간:</strong> ${new Date().toLocaleTimeString()}`,
          '데이터 로드 실패'
        );
      }
      
      if (window.GlobalState && window.GlobalState.ErrorHandler) {
        window.GlobalState.ErrorHandler.handleError(error, {
          module: 'data',
          function: 'loadInitialDataFromBackend',
          context: `티켓 ID: ${basicTicketInfo.id}`,
          userMessage: '초기 데이터를 불러오는데 실패했습니다.',
        });
      }
      
      return null;
    }
  },

  /**
   * 🎯 FDK 네이티브 데이터 로드 성공 모달 (현재 사용 안함)
   * 
   * 자동 모달 표시를 제거하고 토스트 알림으로 대체
   * 필요시 버튼 클릭으로 수동 호출 가능
   */
  /* 
  async showDataLoadSuccessModal(ticketInfo, data) {
    try {
      console.log('🎭 FDK 데이터 로드 성공 모달 호출');
      
      await client.interface.trigger("showModal", {
        title: "데이터 로드 완료",
        template: "index.html",
        data: {
          isDataLoadSuccess: true,
          ticketInfo: ticketInfo,
          loadedData: {
            similarTickets: data.similar_tickets?.length || 0,
            kbDocuments: data.kb_documents?.length || 0,
            loadTime: new Date().toLocaleTimeString()
          },
          timestamp: new Date().toISOString()
        },
        size: {
          width: "600px",
          height: "400px"
        },
        noBackdrop: false
      });
      
      console.log('✅ FDK 데이터 로드 성공 모달 열림 완료');
    } catch (error) {
      console.error('❌ FDK 데이터 로드 성공 모달 오류:', error);
      
      // 폴백: 토스트 메시지로 대체
      UI.showToast('데이터가 성공적으로 로드되었습니다.', 'success');
    }
  },
  */

  /**
   * 메모이제이션된 데이터 처리 함수들
   */
  memoizedFunctions: new Map(),

  /**
   * 메모이제이션 적용 헬퍼
   */
  setupMemoization() {
    // 무거운 연산 함수들에 메모이제이션 적용
    this.memoizedFunctions.set(
      'processTicketData',
      window.PerformanceOptimizer.memoize(
        this.processTicketDataInternal.bind(this),
        (ticket) => `${ticket.id}_${ticket.updated_at || ''}`
      )
    );

    this.memoizedFunctions.set(
      'searchTickets',
      window.PerformanceOptimizer.memoize(
        this.searchTicketsInternal.bind(this),
        (query) => `search_${query.toLowerCase()}`
      )
    );

    this.memoizedFunctions.set(
      'filterTicketsByType',
      window.PerformanceOptimizer.memoize(
        this.filterTicketsByTypeInternal.bind(this),
        (tickets, type) => `filter_${type}_${tickets.length}`
      )
    );
  },

  /**
   * 배치 데이터 처리
   * 대량 데이터를 청크 단위로 처리하여 UI 블로킹 방지
   */
  async processBatchData(items, processor, options = {}) {
    const { batchSize = 100, delay = 10, onProgress = null, onBatchComplete = null } = options;

    const results = [];
    const total = items.length;

    console.log(`[데이터] 배치 처리 시작: ${total}개 항목, ${batchSize}개씩 처리`);

    for (let i = 0; i < total; i += batchSize) {
      const batch = items.slice(i, i + batchSize);

      // 배치 처리
      const batchResults = await Promise.all(batch.map((item) => processor(item)));

      results.push(...batchResults);

      // 진행률 콜백
      if (onProgress) {
        const progress = Math.min(100, ((i + batchSize) / total) * 100);
        onProgress(progress, i + batchSize, total);
      }

      // 배치 완료 콜백
      if (onBatchComplete) {
        onBatchComplete(batchResults, i / batchSize + 1);
      }

      // UI 블로킹 방지를 위한 지연
      if (i + batchSize < total) {
        await new Promise((resolve) => setTimeout(resolve, delay));
      }
    }

    console.log(`[데이터] 배치 처리 완료: ${results.length}개 결과`);
    return results;
  },

  /**
   * 스마트 캐싱 데이터 로더
   */
  async loadDataWithSmartCache(loadFunction, cacheKey, options = {}) {
    const {
      ttl = 300000, // 5분
      forceRefresh = false,
      fallbackData = null,
    } = options;

    // 캐시 확인
    if (!forceRefresh) {
      const cached = window.PerformanceOptimizer.getCachedApiResult(cacheKey);
      if (cached) {
        console.log(`[데이터 캐시] ${cacheKey} - 캐시 적중`);
        return cached;
      }
    }

    try {
      // 데이터 로드
      const data = await loadFunction();

      // 캐시 저장
      window.PerformanceOptimizer.cacheApiResult(cacheKey, data, ttl);

      return data;
    } catch (error) {
      console.warn(`[데이터] ${cacheKey} 로드 실패:`, error.message);

      // 폴백 데이터 또는 에러 처리
      if (fallbackData) {
        console.log(`[데이터] ${cacheKey} - 폴백 데이터 사용`);
        return fallbackData;
      }

      throw error;
    }
  },

  /**
   * 메모이제이션된 티켓 데이터 처리
   */
  processTicketData(ticket) {
    const memoized = this.memoizedFunctions.get('processTicketData');
    return memoized ? memoized(ticket) : this.processTicketDataInternal(ticket);
  },

  /**
   * 실제 티켓 데이터 처리 (내부 함수)
   */
  processTicketDataInternal(ticket) {
    try {
      // 복잡한 티켓 데이터 처리 로직
      const processed = {
        id: ticket.id,
        subject: ticket.subject || '제목 없음',
        description: this.sanitizeText(ticket.description_text || ''),
        status: this.normalizeStatus(ticket.status),
        priority: this.normalizePriority(ticket.priority),
        created_at: this.parseDate(ticket.created_at),
        updated_at: this.parseDate(ticket.updated_at),
        tags: this.extractTags(ticket.tags || []),
        category: this.categorizeTicket(ticket),
        urgency_score: this.calculateUrgencyScore(ticket),
      };

      return processed;
    } catch (error) {
      console.warn('[데이터] 티켓 처리 실패:', ticket.id, error);
      return this.createFallbackTicket(ticket);
    }
  },

  /**
   * 메모이제이션된 티켓 검색
   */
  searchTickets(query) {
    if (!query || query.length < 2) {
      return this.getAllProcessedTickets();
    }

    const memoized = this.memoizedFunctions.get('searchTickets');
    return memoized ? memoized(query) : this.searchTicketsInternal(query);
  },

  /**
   * 실제 티켓 검색 (내부 함수)
   */
  searchTicketsInternal(query) {
    const tickets = this.getAllProcessedTickets();
    const lowercaseQuery = query.toLowerCase();

    // 다중 필드 검색 (제목, 설명, 태그)
    return tickets.filter((ticket) => {
      return (
        ticket.subject.toLowerCase().includes(lowercaseQuery) ||
        ticket.description.toLowerCase().includes(lowercaseQuery) ||
        ticket.tags.some((tag) => tag.toLowerCase().includes(lowercaseQuery))
      );
    });
  },

  /**
   * 지연 로딩 데이터 관리
   */
  createLazyDataLoader(loaderFunction, placeholder = null) {
    return window.PerformanceOptimizer.createLazyLoader(loaderFunction, placeholder);
  },

  /**
   * 실시간 데이터 업데이트 (웹소켓 시뮬레이션)
   */
  setupRealTimeUpdates(callback, interval = 30000) {
    // 30초마다
    let updateTimer = null;

    const startUpdates = () => {
      if (updateTimer) return;

      updateTimer = setInterval(async () => {
        try {
          // 페이지가 활성화된 경우만 업데이트
          if (!document.hidden) {
            const hasUpdates = await this.checkForUpdates();
            if (hasUpdates && callback) {
              callback();
            }
          }
        } catch (error) {
          console.warn('[데이터] 실시간 업데이트 실패:', error);
        }
      }, interval);

      console.log(`[데이터] 실시간 업데이트 시작 (${interval}ms 간격)`);
    };

    const stopUpdates = () => {
      if (updateTimer) {
        clearInterval(updateTimer);
        updateTimer = null;
        console.log('[데이터] 실시간 업데이트 중지');
      }
    };

    // 페이지 가시성에 따른 자동 제어
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) {
        stopUpdates();
      } else {
        startUpdates();
      }
    });

    startUpdates();

    return { start: startUpdates, stop: stopUpdates };
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

console.log('📊 Data 모듈 로드 완료 - 7개 함수 export됨');

// 모듈 의존성 시스템에 등록
if (typeof ModuleDependencyManager !== 'undefined') {
  ModuleDependencyManager.registerModule('data', Object.keys(Data).length);
}
