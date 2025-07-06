/**
 * 🎯 Freshdesk Custom App - AI 기반 상담사 지원 시스템
 *
 * 이 파일은 앱의 메인 진입점으로, Freshdesk 환경에서 상담사가 티켓을 처리할 때
 * AI의 도움을 받을 수 있도록 지원하는 시스템의 핵심 초기화 로직을 담고 있습니다.
 *
 * 주요 기능:
 * - FDK(Freshdesk Developer Kit) 앱 초기화 및 이벤트 처리
 * - 백그라운드 데이터 미리 로딩 (성능 최적화)
 * - 모달 표시 및 사용자 상호작용 관리
 * - 모듈 간 의존성 검증 및 시스템 안정성 보장
 *
 * @author We Do Soft Inc.
 * @since 2025.06.16
 * @version 2.0.0 (모듈화 완료)
 */

// 전역 변수는 globals.js에서 중앙 관리됨
// GlobalState 객체를 통해 안전하게 접근

// 모의 추천 솔루션 생성 함수는 data.js로 분리됨

// 유틸리티 함수들은 utils.js로 분리됨

/**
 * 🚀 앱 초기화 시작점
 *
 * Freshdesk 앱이 로드되면 자동으로 실행되는 메인 초기화 로직입니다.
 * FDK가 제공하는 initialized() 이벤트를 통해 앱이 준비되었을 때 실행됩니다.
 *
 * 주요 처리 과정:
 * 1. FDK 클라이언트 객체를 전역 상태에 저장
 * 2. 백그라운드 데이터 미리 로딩 시작 (성능 최적화)
 * 3. 앱 활성화 이벤트 리스너 등록
 * 4. 렌더링 완료 후 이벤트 핸들러 설정
 */

// 중복 초기화 방지 플래그 (window 레벨에서 관리)
if (typeof window.APP_INITIALIZED === 'undefined') {
  window.APP_INITIALIZED = false;
}

/**
 * 🎯 FDK 네이티브 모달 호출 함수 (백엔드 호출 없는 버전)
 * 
 * 복잡한 DOM 조작이나 백엔드 API 호출 없이 FDK 내장 기능만 활용하여 모달을 표시합니다.
 * index.html을 템플릿으로 사용하여 안정적인 모달 표시를 보장합니다.
 * 
 * ✅ 페이지 로딩 시: 1회만 백엔드 호출 (백그라운드에서)
 * 🚫 모달 띄울 때: 별도 백엔드 호출 금지 (캐시된 데이터만 사용)
 * 🚫 모달 이후: 불필요한 액션 제거
 */
async function showFDKModal(ticketId, hasCachedData = false) {
  try {
    // 클라이언트 준비 확인
    const client = GlobalState.getClient();
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
        
        // 캐시된 티켓 정보 가져오기
        if (window.GlobalState) {
          const globalData = window.GlobalState.getGlobalTicketData();
          if (globalData.ticket_info) {
            ticket = globalData.ticket_info;
            console.log('✅ 캐시된 티켓 데이터 사용:', ticket);
          }
        }
      } else {
        // 일반 컨텍스트에서는 정상적으로 EventAPI 사용
        ticketData = await client.data.get('ticket');
        ticket = ticketData?.ticket;
        console.log('✅ 티켓 데이터 가져오기 성공');
      }
    } catch (error) {
      console.warn('⚠️ 티켓 데이터 가져오기 실패:', error.message);
      
      // EventAPI 실패 시 폴백: 캐시된 데이터 사용
      if (window.GlobalState) {
        const globalData = window.GlobalState.getGlobalTicketData();
        if (globalData.ticket_info) {
          ticket = globalData.ticket_info;
          console.log('🔄 폴백: 캐시된 티켓 데이터 사용');
        }
      }
    }
    
    // 모달 설정 구성 (백엔드 호출 없이 캐시된 데이터만 전달)
    const modalConfig = {
      title: "Copilot Canvas - AI 상담사 지원",
      template: "index.html", // 기본 index.html 사용
      data: {
        ticketId: ticketId,
        ticket: ticket,
        hasCachedData: hasCachedData,
        timestamp: new Date().toISOString(),
        // 백엔드 호출 금지 플래그 추가
        noBackendCall: true
      },
      size: {
        width: "900px",
        height: "700px"
      },
      noBackdrop: true
    };

    await client.interface.trigger("showModal", modalConfig);
    
  } catch (error) {
    console.error('❌ FDK 모달 오류:', error);
    
    // 사용자에게 친화적인 에러 메시지 표시
    if (window.UI && window.UI.showErrorWithRetry) {
      // 재시도 콜백 함수 정의
      const retryCallback = async () => {
        await showFDKModal(ticketId, hasCachedData);
      };
      
      window.UI.showErrorWithRetry(
        error, 
        retryCallback, 
        'AI 지원 모달 열기'
      );
    } else {
      // UI 모듈이 없는 경우 폴백: 간단한 알림으로 대체
      try {
        const client = GlobalState.getClient();
        if (client) {
          await client.interface.trigger("showNotify", {
            type: "warning",
            message: "AI 지원 기능을 불러오는 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."
          });
        }
      } catch (notifyError) {
        console.error('❌ 알림도 실패:', notifyError);
        // 최후의 수단: 브라우저 콘솔에 에러 메시지만 기록
        console.error('🚨 UI 초기화 실패: AI 지원 기능을 불러올 수 없습니다.');
      }
    }
  }
}

// FDK 모달 컨텍스트 감지 (전역 변수 사용)
// isFDKModal 변수는 index.html에서 이미 선언됨

// FDK 모달에서는 EventAPI 오류를 방지하기 위해 앱 초기화 건너뛰기
if (typeof window.isFDKModal !== 'undefined' && window.isFDKModal) {
  console.log('🎭 FDK 모달 컨텍스트 감지 - EventAPI 오류 방지를 위해 앱 초기화 건너뛰기');
  console.log('📋 모달 데이터 렌더링은 index.html의 handleFDKModalMode()에서 처리됩니다');
  // 모달에서는 app.initialized()를 호출하지 않음 (EventAPI 오류 방지)
} else {
  // 표준 앱 모드에서만 전체 초기화 실행
  app
    .initialized()
    .then((c) => {
      // 중복 초기화 방지 - window 레벨에서 체크
      if (window.APP_INITIALIZED) {
        return; // 이미 초기화됨 - 완전히 건너뛰기
      }
      
      console.log('🚀 앱 초기화 시작 (최초 1회)');
      
      // 전역 상태 관리 시스템 초기화 (한 번만 실행)
      if (typeof GlobalState !== 'undefined') {
        GlobalState.init(); // 내부적으로 중복 체크됨
        GlobalState.setClient(c);
        GlobalState.setInitialized(true);
      }
      
      // API 모듈 초기화 (백엔드 연결 설정)
      if (typeof API !== 'undefined' && API.initialize) {
        API.initialize(c).then((isConnected) => {
          if (isConnected) {
            console.log('✅ API 모듈 초기화 완료 - 백엔드 연결 정상');
          } else {
            console.warn('⚠️ API 모듈 초기화 완료 - 백엔드 연결 실패 (폴백 모드)');
          }
        }).catch((error) => {
          console.error('❌ API 모듈 초기화 실패:', error);
        });
      }
      
      window.APP_INITIALIZED = true;
      console.log('✅ 앱 초기화 완료');

    const client = GlobalState.getClient();

    // ① 사이드바 컨텍스트 감지 및 스트리밍 시작
    // manifest.json의 ticket_sidebar에서 로드된 경우 스트리밍 진행률 표시
    client.instance.context().then(async (ctx) => {
      console.log(`📍 현재 컨텍스트: ${ctx.location}`);
      
      if (ctx.location === 'ticket_sidebar') {
        console.log('📊 사이드바 컨텍스트 감지 - 간단한 로딩 표시 시작');
        
        // 사이드바 컴포넌트 초기화 (에러 무시)
        try {
          if (typeof SidebarProgress !== 'undefined') {
            SidebarProgress.init();
          }
        } catch (sidebarError) {
          console.warn('⚠️ 사이드바 컴포넌트 초기화 실패 (무시):', sidebarError.message);
        }
        
        // 현재 티켓 ID 가져오기 (안전한 방식)
        let ticketId = null;
        try {
          const ticketData = await client.data.get('ticket');
          ticketId = ticketData?.ticket?.id;
          
          if (ticketId) {
            console.log(`🎯 티켓 ${ticketId}에 대한 간단한 로딩 표시 시작`);
            
            // 간단한 사이드바 로딩 표시
            if (typeof API !== 'undefined' && API.showSimpleLoadingInSidebar) {
              const loadingSuccess = await API.showSimpleLoadingInSidebar(client, ticketId);
              
              if (!loadingSuccess) {
                console.warn('⚠️ 사이드바 로딩 표시 실패');
              }
            } else {
              console.warn('⚠️ 간단한 로딩 API가 아직 로드되지 않음 - 기존 방식 사용');
              await Data.preloadTicketDataOnPageLoad(client);
            }
          } else {
            console.warn('⚠️ 티켓 ID를 가져올 수 없음 - 폴백 시도');
            
            // 폴백: 캐시된 데이터에서 티켓 ID 가져오기
            if (window.GlobalState) {
              const globalData = window.GlobalState.getGlobalTicketData();
              ticketId = globalData.cached_ticket_id;
              if (ticketId) {
                console.log(`🔄 폴백: 캐시된 티켓 ID 사용 - ${ticketId}`);
              }
            }
          }
        } catch (error) {
          console.error('❌ 사이드바에서 티켓 데이터 가져오기 실패:', error);
          
          // 폴백: 캐시된 데이터에서 티켓 ID 가져오기
          if (window.GlobalState) {
            const globalData = window.GlobalState.getGlobalTicketData();
            ticketId = globalData.cached_ticket_id;
            if (ticketId) {
              console.log(`🔄 폴백: 캐시된 티켓 ID 사용 - ${ticketId}`);
            } else {
              // 최후의 폴백: 기존 방식으로 데이터 로드
              await Data.preloadTicketDataOnPageLoad(client);
            }
          }
        }
        
      } else {
        console.log('📍 사이드바가 아닌 컨텍스트 - 기존 방식으로 백그라운드 로딩');
        
        // ② 백그라운드 데이터 준비 - 안전한 호출로 변경 (한 번만 실행)
        // 사용자가 모달을 열기 전에 미리 데이터를 로드하여 응답 속도를 향상시킵니다
        Data.preloadTicketDataOnPageLoad(client).then((result) => {
          if (result) {
            console.log('✅ 페이지 로딩 시 백엔드 호출 성공 완료');
          } else {
            console.warn('⚠️ 페이지 로딩 시 백엔드 호출 실패 또는 스킵됨');
            
            // 백엔드 호출 실패 시 사용자에게 알림 (토스트 메시지) - 지연 호출
            setTimeout(() => {
              if (window.UI && window.UI.showToast) {
                window.UI.showToast(
                  'AI 데이터 로드에 실패했습니다. 앱 아이콘을 클릭하여 다시 시도할 수 있습니다.',
                  'warning',
                  5000 // 5초간 표시
                );
              } else {
                console.warn('[APP] UI 모듈이 아직 준비되지 않아 토스트 메시지를 표시할 수 없습니다.');
              }
            }, 1000); // 1초 지연 후 토스트 표시
          }
        }).catch((error) => {
          console.error('❌ 페이지 로딩 시 백엔드 호출 중 예외 발생:', error);
          
          // 예외 발생 시 사용자에게 에러 알림 - 지연 호출
          setTimeout(() => {
            if (window.UI && window.UI.showToast) {
              window.UI.showToast(
                '서버 연결에 문제가 있습니다. 잠시 후 다시 시도해 주세요.',
                'error',
                7000 // 7초간 표시
              );
            } else {
              console.warn('[APP] UI 모듈이 아직 준비되지 않아 에러 토스트를 표시할 수 없습니다.');
            }
          }, 1000); // 1초 지연 후 토스트 표시
        });
      }
    }).catch((contextError) => {
      console.warn('⚠️ 컨텍스트 가져오기 실패 - 기본 백그라운드 로딩 진행:', contextError.message);
      
      // EventAPI 오류가 발생해도 앱이 동작하도록 안전한 폴백 제공
      if (contextError.message && contextError.message.includes('EventAPI')) {
        console.log('🔄 EventAPI 오류 감지 - 캐시된 데이터 기반으로 동작');
        
        // 캐시된 데이터가 있으면 그것을 사용
        if (window.GlobalState) {
          const globalData = window.GlobalState.getGlobalTicketData();
          if (globalData.summary || globalData.ticket_info) {
            console.log('✅ 캐시된 데이터 발견 - 정상 동작 가능');
            return; // 추가 처리 없이 종료
          }
        }
      }
      
      // 컨텍스트를 알 수 없는 경우 기본 방식으로 진행
      Data.preloadTicketDataOnPageLoad(client);
    });

    // ② 상단 네비게이션 앱 아이콘 클릭 시 처리 (캐시된 데이터로 즉시 모달 표시)
    // Freshdesk 상단 네비게이션의 앱 아이콘을 클릭했을 때 실행되는 이벤트 핸들러
    client.events.on('app.activated', async () => {
      try {
        // FDK context 가져오기 (안전한 호출)
        let ctx = null;
        try {
          ctx = await client.instance.context();
        } catch (contextError) {
          console.warn('⚠️ FDK context 가져오기 실패:', contextError.message);
          // context를 가져올 수 없는 경우 기본값으로 계속 진행
          ctx = { location: 'unknown' };
        }

        // 상단 네비게이션에서의 동작: 스마트 캐싱 전략 적용
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
            currentTicketId = 'unknown';
          }

          // 전역 상태에서 캐시된 데이터 확인
          const globalData = GlobalState.getGlobalTicketData();

          // 캐시된 데이터가 현재 티켓과 일치하는지 확인
          if (
            globalData.cached_ticket_id === currentTicketId &&
            globalData.summary &&
            GlobalState.isGlobalDataValid()
          ) {
            await showFDKModal(currentTicketId, true);
          } else {
            await showFDKModal(currentTicketId, false);
          }

          // 모달 표시 후 이벤트 설정 (한 번만)
          if (!Events.isInitialized) {
            Events.setupTabEvents(client);
            Events.isInitialized = true;
          }
        } else {
          // 예상치 못한 위치에서의 호출
          if (!GlobalState.isInitialized()) {
            await Data.loadTicketDetails(client);
            Events.setupTabEvents(client);
            GlobalState.setInitialized(true);
          }
        }
      } catch (err) {
        console.error('onAppActivated 오류', err);
      }
    });

    // ③ 모달이 열린 후 DOM 요소에 데이터 렌더링 (백엔드 호출 완전 금지)
    client.events.on('template.render', () => {
      try {
        console.log('🎭 모달 템플릿 렌더링 완료');

        // FDK 모달에서는 백엔드 호출이나 복잡한 로직 완전 금지
        setTimeout(() => {
          console.log('🚫 모달에서 백엔드 호출 금지 - 캐시된 데이터만 사용');
          
          // 캐시된 데이터만 사용하여 간단한 UI 업데이트 (백엔드 호출 없음)
          const globalData = GlobalState.getGlobalTicketData();
          console.log('📋 모달 렌더링 - 캐시된 데이터 확인:', {
            hasSummary: !!globalData.summary,
            hasTicketInfo: !!globalData.ticket_info,
            hasSimilarTickets: globalData.similar_tickets?.length || 0,
            hasKbDocuments: globalData.kb_documents?.length || 0
          });
          
          if (globalData.summary || globalData.ticket_info) {
            console.log('📋 모달에서 캐시된 데이터로 UI 업데이트 시작');
            
            // UI 모듈이 있는지 확인 후 데이터 전달
            if (typeof UI !== 'undefined' && UI.updateUIWithCachedData) {
              UI.updateUIWithCachedData(globalData);
            } else {
              console.error('❌ UI 모듈 또는 updateUIWithCachedData 함수를 찾을 수 없음');
            }
          } else {
            console.log('ℹ️ 모달에서 캐시된 데이터 없음 - 기본 상태 유지');
            
            // 데이터가 없으면 백엔드에서 다시 로드 시도
            if (typeof Data !== 'undefined' && Data.preloadTicketDataOnPageLoad) {
              console.log('🔄 모달에서 데이터 재로드 시도');
              Data.preloadTicketDataOnPageLoad(client).then((result) => {
                if (result) {
                  const newGlobalData = GlobalState.getGlobalTicketData();
                  if (typeof UI !== 'undefined' && UI.updateUIWithCachedData) {
                    UI.updateUIWithCachedData(newGlobalData);
                  }
                }
              });
            }
          }

          // 모달에서는 최소한의 이벤트 설정만 (추가 백엔드 호출 없음)
          if (!GlobalState.isInitialized()) {
            console.log('🔧 모달에서 최소 이벤트 설정 (백엔드 호출 없음)');
            Events.setupTabEvents(client);
            GlobalState.setInitialized(true);
          }
          
          console.log('✅ 모달 렌더링 처리 완료 - 추가 액션 없음');
        }, 100);
      } catch (err) {
        console.error('template.render 오류', err);
      }
    });
  })
  .catch((error) => {
    console.error('앱 초기화 실패:', error);
  });

// 전역 상태는 app.initialized() 콜백에서 한 번만 초기화됨
// 중복 초기화 방지를 위해 여기서의 GlobalState.init() 호출 제거됨

/**
 * 🎯 메인 앱 초기화 함수
 *
 * 모듈 의존성 검증이 완료된 후 실행되는 실제 앱 초기화 로직입니다.
 * 이 함수는 앱의 핵심 기능들을 순차적으로 초기화하여 사용자가 이용할 수 있는
 * 상태로 만드는 역할을 담당합니다.
 *
 * 주요 초기화 작업:
 * - FDK 클라이언트 설정 및 상태 관리
 * - 전역 에러 핸들러 등록
 * - UI 컴포넌트 초기화
 * - 이벤트 리스너 설정
 * - 백그라운드 데이터 로딩 시작
 *
 * @returns {Promise<void>} 초기화 완료를 나타내는 Promise
 * @throws {Error} 초기화 과정에서 오류 발생 시
 */
/**
 * 📅 FDK 기반 앱 초기화 완료
 *
 * DOM 로드 이벤트 핸들러는 제거되었습니다.
 * 모든 초기화는 app.initialized() 이벤트를 통해 수행됩니다.
 * 
 * 이는 Freshdesk FDK의 표준 패턴입니다.
 */

// 모든 모듈이 로드된 후 시스템 검증 (초기화 시 한 번만)
if (!window.MODULE_DEPENDENCY_CHECKED) {
  setTimeout(() => {
    if (typeof ModuleDependencyManager !== 'undefined') {
      // app 모듈 등록
      ModuleDependencyManager.registerModule('app', 1); // initializeApp 함수 1개

      // 시스템 준비 상태 확인 (리포트는 localhost에서만)
      if (ModuleDependencyManager.isSystemReady()) {
        console.log('✅ 모든 모듈 시스템 준비 완료');
      } else {
        console.warn('⚠️ 일부 모듈에서 의존성 문제 발견');
        
        // 개발 환경에서만 상세 리포트 표시
        if (window.location.hostname === 'localhost') {
          ModuleDependencyManager.generateStatusReport();
        }
      }
      
      window.MODULE_DEPENDENCY_CHECKED = true;
    }
  }, 500); // 모든 모듈 로드 후 실행
}

// 레거시 init() 함수는 제거됨 (메인 초기화는 app.initialized()로 통합)

// loadTicketDetails 함수는 data.js로 분리됨

// preloadTicketDataOnPageLoad 함수는 data.js로 분리됨

// 캐시된 데이터로 UI를 즉시 업데이트하는 함수는 ui.js로 분리됨

// 티켓 정보 UI 업데이트 함수는 ui.js로 분리됨

// 탭 이벤트 설정 함수는 events.js로 분리됨

// 유사 티켓 탭 처리 함수는 events.js로 분리됨

// 유사 티켓 이벤트 설정 함수는 events.js로 분리됨

// 유사 티켓 리스트 뷰 표시 함수는 ui.js로 분리됨

// 유사 티켓 상세 뷰 표시 함수는 ui.js로 분리됨

// loadSimilarTicketsFromBackend 함수는 api-client.js로 분리됨

// loadSimilarTicketsFromFreshdesk 함수는 api-client.js로 분리됨

// 유사 티켓 관련 코드는 events.js와 ui.js로 분리됨

// 유사 티켓 결과 표시 함수는 ui.js로 분리됨

// 검색 기능은 백엔드 지침서에 따라 /query 엔드포인트로 통합되었습니다.
// 별도의 검색 함수는 더 이상 사용되지 않습니다.

// 추천 해결책 탭 처리 함수는 events.js로 분리됨

// 추천 솔루션 이벤트 설정 함수는 events.js로 분리됨

// 추천 솔루션 리스트 뷰 표시 함수는 ui.js로 분리됨

// 추천 솔루션 상세 뷰 표시 함수는 ui.js로 분리됨

// loadSuggestedSolutions 함수는 data.js로 분리됨

// 추천 솔루션 표시 함수는 ui.js로 분리됨

// 코파일럿 탭 처리 함수는 events.js로 분리됨

// 코파일럿 이벤트 설정 함수는 events.js로 분리됨

// 코파일럿 검색 실행 함수는 events.js로 분리됨

// 코파일럿 컨텍스트 가져오기 함수는 events.js로 분리됨

// 코파일럿 결과 표시 함수는 events.js로 분리됨

// loadInitialDataFromBackend 함수는 api-client.js로 분리됨

// 티켓 요약 표시 함수는 ui.js로 분리됨

// resetGlobalTicketCache 함수는 data.js로 분리됨

// attemptMultipleBackgroundLoads 및 attemptSingleBackgroundLoad 함수는 data.js로 분리됨

// API 클라이언트 함수들은 api-client.js로 분리됨

// 에러 메시지 표시 함수는 ui.js로 분리됨

// 로딩 메시지 표시 함수는 ui.js로 분리됨
// 모달 표시 함수는 ui.js로 분리됨

// getFreshdeskConfigFromIparams 함수는 api-client.js로 분리됨

// smartDomainParsingFrontend 및 extractCompanyIdFromDomain 함수들은 api-client.js로 분리됨

// App 객체 정의 (네임스페이스 컨테이너로만 사용)
window.App = window.App || {
  initialize: function() {
    console.log('🎯 App.initialize() 호출됨 - FDK 모달에서는 실행하지 않음');
  }
};

// 표준 앱 모드에서만 실행되는 코드 블록 닫기
}