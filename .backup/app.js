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
 * 🎯 즉시 모달 표시 함수 (Progressive Enhancement)
 * 
 * 로딩 상태와 관계없이 즉시 모달을 표시하고, 로딩 중인 경우 진행률을 실시간으로 업데이트합니다.
 * 사용자는 대기 시간 없이 즉시 모달을 볼 수 있으며, 데이터는 점진적으로 표시됩니다.
 * 
 * ✅ 즉시 모달 표시 (0초 대기)
 * ✅ 로딩 중: 실시간 진행률 표시
 * ✅ 오류 시: 명확한 에러 메시지와 재시도 옵션
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
    
    // 현재 로딩 상태 가져오기
    const loadingStatus = window.GlobalState ? window.GlobalState.getLoadingStatus() : null;
    const globalData = window.GlobalState ? window.GlobalState.getGlobalTicketData() : {};
    const errorState = window.GlobalState ? window.GlobalState.getGlobalError() : {};
    const streamingStatus = window.GlobalState ? window.GlobalState.getStreamingStatus() : {};
    
    // 로딩 상태 판단 개선
    const isCurrentlyLoading = loadingStatus?.status === 'loading' || 
                              streamingStatus.is_streaming || 
                              globalData.isLoading;
    const isDataReady = loadingStatus?.status === 'ready' || 
                       (globalData.summary && globalData.cached_ticket_id);
    
    console.log('📊 모달 열기 시 상태:', {
      loadingStatus: loadingStatus?.status,
      isStreaming: streamingStatus.is_streaming,
      hasData: !!globalData.summary,
      hasError: errorState.hasError,
      isCurrentlyLoading,
      isDataReady
    });
    
    // 모달 설정 구성 (현재 상태를 모두 전달)
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
        // 로딩 상태 정보 추가
        loadingStatus: loadingStatus,
        globalData: globalData,
        streamingStatus: streamingStatus,
        hasError: errorState.hasError && !isCurrentlyLoading, // 로딩 중이면 에러 표시 안함
        errorMessage: errorState.errorMessage,
        // 상태별 플래그
        isLoading: isCurrentlyLoading,
        isReady: isDataReady,
        isPartiallyLoaded: globalData.summary && !globalData.similar_tickets
      },
      size: {
        width: "900px",
        height: "700px"
      },
      noBackdrop: true
    };

    // 🔥 모달을 반드시 열어야 하므로 강화된 에러 처리
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
          // 최종 시도 - 오류 모드로 강제 표시
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
    
    // 🚨 어떤 상황에서도 사용자에게 상황을 알려야 함
    console.log('🚨 최후의 수단: 사용자에게 오류 상황 알림');
    
    // 최후의 수단으로 DOM에 직접 오류 알림 표시
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
}

// FDK 모달 컨텍스트 감지 (전역 변수 사용)
// isFDKModal 변수는 index.html에서 이미 선언됨

/**
 * 🚀 백그라운드 데이터 로딩 시작
 * 페이지 로드 즉시 실행되어 사용자가 아이콘을 클릭하기 전에 데이터를 준비합니다.
 * 20초의 로딩 시간을 백그라운드에서 처리하여 사용자 대기 시간을 최소화합니다.
 */
async function startBackgroundDataLoading(client) {
  try {
    console.log('🚀 백그라운드 데이터 로딩 시작 - 사용자 인터랙션 없이 자동 실행');
    
    // 로딩 상태 설정
    if (window.GlobalState) {
      window.GlobalState.setLoadingStatus({
        status: 'loading',
        startTime: Date.now(),
        estimatedTime: 20000 // 20초 예상
      });
    }
    
    // 아이콘 상태 업데이트 (로딩 중 표시)
    updateAppIconStatus('loading');
    
    // 티켓 ID 가져오기
    let ticketId = null;
    try {
      const ticketData = await client.data.get('ticket');
      ticketId = ticketData?.ticket?.id;
      
      if (ticketId) {
        console.log(`🎯 티켓 ${ticketId}에 대한 백그라운드 로딩 시작`);
        
        // 백엔드 데이터 로드 (스트리밍 지원)
        const result = await Data.preloadTicketDataOnPageLoad(client);
        
        if (result) {
          console.log('✅ 백그라운드 데이터 로딩 성공');
          updateAppIconStatus('ready');
          
          // 로딩 상태를 성공으로 업데이트
          if (window.GlobalState) {
            window.GlobalState.setLoadingStatus({
              status: 'ready',
              completedTime: Date.now()
            });
          }
        } else {
          console.warn('⚠️ 백그라운드 데이터 로딩 실패');
          updateAppIconStatus('error');
          
          // 로딩 상태를 에러로 업데이트
          if (window.GlobalState) {
            window.GlobalState.setLoadingStatus({
              status: 'error',
              completedTime: Date.now()
            });
          }
        }
      }
    } catch (error) {
      console.error('❌ 백그라운드 로딩 중 오류:', error);
      updateAppIconStatus('error');
      
      if (window.GlobalState) {
        window.GlobalState.setGlobalError(true, '백그라운드 데이터 로딩 실패');
        window.GlobalState.setLoadingStatus({
          status: 'error',
          completedTime: Date.now()
        });
      }
    }
  } catch (error) {
    console.error('❌ 백그라운드 로딩 전체 오류:', error);
  }
}

/**
 * 🎨 앱 아이콘 상태 업데이트
 * 상단 네비게이션의 아이콘에 시각적 상태를 표시합니다.
 */
function updateAppIconStatus(status) {
  try {
    // FDK API를 통한 아이콘 상태 업데이트 (가능한 경우)
    // 실제 구현은 FDK 지원 여부에 따라 달라질 수 있음
    console.log(`🎨 앱 아이콘 상태 업데이트: ${status}`);
    
    // 로컬 상태 저장
    if (window.GlobalState) {
      window.GlobalState.setAppIconStatus(status);
    }
  } catch (error) {
    console.warn('⚠️ 아이콘 상태 업데이트 실패:', error);
  }
}

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
      
      window.APP_INITIALIZED = true;
      console.log('✅ 앱 초기화 완료');

    const client = GlobalState.getClient();

    // 🚀 백그라운드 데이터 로딩 시작 (모듈 준비 후)
    // 모든 모듈이 로드된 후 안전하게 데이터 로딩 시작
    setTimeout(async () => {
      const ready = await window.SAFE_MODULE_ACCESS.waitForModules(3000);
      if (ready) {
        startBackgroundDataLoading(client);
      } else {
        console.error('❌ 모듈 로드 실패 - 백그라운드 데이터 로딩 건너뛰기');
      }
    }, 1000);

    // 🎯 상단 네비게이션 앱 아이콘 클릭 시 처리
    // 로딩 상태와 관계없이 항상 모달을 즉시 표시하고, 상태에 따라 적절한 UI 제공
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
            currentTicketId = 'unknown';
          }

          // 로딩 상태 확인
          const loadingStatus = GlobalState.getLoadingStatus();
          console.log('📊 현재 로딩 상태:', loadingStatus);
          
          // 로딩 상태와 관계없이 즉시 모달 표시
          // 로딩 중이면 진행률을 보여주고, 완료되면 데이터를 보여줌
          await showFDKModal(currentTicketId, true);

          // 모달 표시 후 이벤트 설정 (한 번만) - 새로운 중복 방지 시스템 사용
          await window.ModuleInitializationManager.safeInitialize(
            'events',
            () => Events.setupTabEvents(client)
          );
        } else {
          // 예상치 못한 위치에서의 호출
          if (!GlobalState.isInitialized()) {
            await Data.loadTicketDetails(client);
            
            // 중복 방지 시스템을 사용한 이벤트 설정
            await window.ModuleInitializationManager.safeInitialize(
              'events',
              () => Events.setupTabEvents(client)
            );
            
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
        setTimeout(async () => {
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
            console.log('ℹ️ 모달에서 캐시된 데이터 없음 - 새로고침 안내');
            
            // 🚫 모달에서는 백엔드 호출 안함 - 사용자에게 새로고침 안내
            if (typeof UI !== 'undefined' && UI.showBackendError) {
              UI.showBackendError('AI 데이터를 불러오지 못했습니다. 페이지를 새로고침(F5) 해주세요.');
            } else {
              console.error('❌ UI.showBackendError 함수를 찾을 수 없음');
            }
          }

          // 모달에서는 최소한의 이벤트 설정만 (추가 백엔드 호출 없음)
          if (!GlobalState.isInitialized()) {
            console.log('🔧 모달에서 최소 이벤트 설정 (백엔드 호출 없음)');
            
            // 중복 방지 시스템을 사용한 이벤트 설정
            await window.ModuleInitializationManager.safeInitialize(
              'modal_events',
              () => Events.setupTabEvents(client)
            );
            
            GlobalState.setInitialized(true);
          }
          
          console.log('✅ 모달 렌더링 처리 완료 - 추가 액션 없음');
        }, 100);
      } catch (err) {
        console.error('❌ template.render 오류:', err);
        
        // 모달 렌더링 중 예외 발생 시 사용자에게 친화적 메시지 표시
        if (typeof UI !== 'undefined' && UI.showBackendError) {
          UI.showBackendError('AI 지원 기능을 초기화하는 중 오류가 발생했습니다. 페이지를 새로고침 후 다시 시도해주세요.');
        } else {
          console.error('❌ UI.showBackendError 함수를 찾을 수 없음');
        }
      }
    });
  })
  .catch((error) => {
    console.error('앱 초기화 실패:', error);
  });



// 모든 모듈이 로드된 후 시스템 검증 (초기화 시 한 번만)
if (!window.MODULE_DEPENDENCY_CHECKED) {
  if (typeof ModuleDependencyManager !== 'undefined') {
    // app 모듈 등록
    setTimeout(() => {
      ModuleDependencyManager.registerModule('app', 1); // initializeApp 함수 1개
    }, 250);

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
}


// App 객체 정의 (네임스페이스 컨테이너로만 사용)
window.App = window.App || {
  initialize: function() {
    console.log('🎯 App.initialize() 호출됨 - FDK 모달에서는 실행하지 않음');
  }
};

// 표준 앱 모드에서만 실행되는 코드 블록 닫기
}