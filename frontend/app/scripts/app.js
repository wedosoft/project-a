/**
 * Freshdesk Custom App - 극도로 단순화된 버전
 */

// 모듈 로드 확인 제거 - 불필요한 디버그 로그

// 현재 페이지 위치 감지를 위한 변수 (FDK 초기화 후 설정)
let isModalView = false;

// 성능 측정 시스템 제거 - 불필요한 오버헤드 제거

/**
 * 앱 전체 초기화 메인 함수
 */
async function initializeApp(client) {

  const modalViewState = await _determineModalViewState(client);

  // 메인 페이지에서는 모달 트리거만 설정
  if (!modalViewState) {
    _setupModalActivationEvent(client);
    return;
  }

  // 모달에서만 실행되는 초기화
  await _initializeCore(client, modalViewState);
  _setupStatePreservation(modalViewState);
  _setupModalEnvironment(modalViewState);
  _loadTicketData();
  _setupUIComponents();
  await _initializeTicketHeader(client);
  _finalizeInitialization();
}


/**
 * 모달 뷰 상태 결정
 */
async function _determineModalViewState(client) {
  try {
    const context = await client.instance.context();
    isModalView = context.location !== 'ticket_top_navigation';
    return isModalView;
  } catch (e) {
    console.error('❌ 컨텍스트 확인 실패:', e);
    isModalView = false;
    return false;
  }
}

/**
 * Core 모듈 초기화
 */
async function _initializeCore(client, modalViewState) {
  await window.Core.initialize(client);
  window.Core.state.isModalView = modalViewState;

  // 새로운 캐시 매니저 초기화
  if (window.TicketCacheManager) {
    try {
      // 캐시 매니저는 티켓 ID가 설정된 후 initialize() 호출됨
      console.log('✅ TicketCacheManager 준비 완료');
    } catch (e) {
      console.warn('⚠️ TicketCacheManager 초기화 실패:', e);
    }
  } else {
    console.warn('⚠️ TicketCacheManager를 찾을 수 없습니다. cache-manager.js가 로드되었는지 확인하세요.');
  }
}

/**
 * 상태 보존 시스템 설정
 */
function _setupStatePreservation(modalViewState) {
  if (modalViewState) {
    window.Core.restoreState();
    window.addEventListener('beforeunload', () => {
      window.Core.saveState();
    });
  }

  // 모든 뷰에서 페이지 떠날 때 캐시 정리 (채팅 히스토리는 보존, 티켓 데이터는 삭제)
  window.addEventListener('beforeunload', () => {
    if (window.Core && window.Core.cleanupOnPageLeave) {
      window.Core.cleanupOnPageLeave();
    }
  });
}

/**
 * 모달 환경 설정
 */
function _setupModalEnvironment(modalViewState) {
  if (modalViewState && window !== window.top) {
    const setupModalBridge = () => {
      if (window.ModalBridge && window.ModalBridge.handleCompleteData) {
        _enhanceModalBridge();
      } else {
        setTimeout(setupModalBridge, 100);
      }
    };

    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', setupModalBridge);
    } else {
      setupModalBridge();
    }
  }
}

/**
 * ModalBridge 기능 강화
 */
function _enhanceModalBridge() {
  const originalHandleCompleteData = window.ModalBridge.handleCompleteData;
  let languageInitialized = false;

  window.ModalBridge.handleCompleteData = function (data) {

    originalHandleCompleteData.call(this, data);

    // 모달이 열릴 때 언어 시스템 초기화 (한 번만)

    if (!languageInitialized && window.initializeI18n) {

      window.initializeI18n();
      languageInitialized = true;
    }

    setTimeout(() => {
      if (window.TicketUI && window.TicketUI.clearModalState) {
        window.TicketUI.clearModalState();
      }
      window.Core.applyRestoredState();
    }, 500);
  };
}

/**
 * 모달 활성화 이벤트 설정
 */
function _setupModalActivationEvent(client) {
  client.events.on("app.activated", async () => {
    await _showModal(client);
  });
}

/**
 * 모달 표시
 */
async function _showModal(client) {
  await client.interface.trigger("showModal", {
    title: "🎨 Copilot Canvas",
    template: "index.html",
    noBackdrop: "true"
  });
}


/**
 * 티켓 데이터 로드 - 캐시 우선 전략
 */
function _loadTicketData() {
  const ticketId = window.Core.state.ticketId;

  // 모달에서만 데이터 로드
  if (ticketId && window.Core.state.isModalView) {
    // 1. 캐시된 데이터부터 확인
    let hasCachedData = false;
    let hasCompleteCache = false;

    if (window.TicketCacheManager) {
      try {
        window.TicketCacheManager.initialize(ticketId);
        const cachedData = window.TicketCacheManager.getAllCachedData();

        if (cachedData && Object.keys(cachedData).length > 0) {
          console.log('✅ 캐시된 데이터 발견');

          // 완전한 캐시 여부 확인 (요약, 유사 티켓, KB 문서 모두 있는 경우)
          hasCompleteCache = !!(cachedData.summary && cachedData.similarTickets && cachedData.kbDocuments);

          // 캐시된 데이터로 즉시 UI 렌더링
          if (window.TicketUI && window.TicketUI.renderAllFromCache) {
            hasCachedData = window.TicketUI.renderAllFromCache(cachedData);
          }

          console.log(`📊 캐시 상태: 렌더링 ${hasCachedData ? '성공' : '실패'}, 완전성 ${hasCompleteCache ? '완전' : '부분'}`);
        } else {
          console.log('ℹ️ 캐시된 데이터가 없습니다');
        }
      } catch (e) {
        console.warn('⚠️ 캐시 데이터 확인 실패:', e);
      }
    }

    // 2. 완전한 캐시가 없는 경우에만 API 호출
    if (!hasCompleteCache) {
      if (window.ApiService && window.ApiService.loadTicketData) {
        console.log(`🔄 API에서 데이터 로드 시작 (캐시 불완전: ${hasCachedData ? '부분적' : '없음'})`);
        window.ApiService.loadTicketData(ticketId);
      }
    } else {
      console.log('✅ 완전한 캐시 발견 - API 호출 생략');
    }
  }
}

// 메인 페이지 관련 함수들 제거 - 모달에서만 데이터 처리


/**
 * UI 컴포넌트 설정
 */
function _setupUIComponents() {
  _setupTabEvents();
  _initializeScrollManager();
  _initializeChatUI();

  // 토글 버튼 상태 초기화
  document.querySelectorAll('.toggle-btn').forEach(btn => {
    btn.classList.remove('loading');
    btn.disabled = false;
  });
}

/**
 * 탭 이벤트 설정
 */
function _setupTabEvents() {
  setTimeout(() => {
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        _bindTabClickEvents();
      });
    });
  }, 1000);
}

/**
 * 탭 클릭 이벤트 바인딩
 */
function _bindTabClickEvents() {
  document.querySelectorAll('.tab-button').forEach(btn => {
    btn.addEventListener('click', e => {
      e.preventDefault();
      e.stopPropagation();
      e.stopImmediatePropagation();

      const tab = e.currentTarget.dataset.tab;
      e.currentTarget.blur();
      switchTab(tab);

      return false;
    });

    btn.addEventListener('focus', e => {
      e.preventDefault();
      e.currentTarget.blur();
    });
  });
}

/**
 * 스크롤 매니저 초기화
 */
function _initializeScrollManager() {
  if (window.ScrollManager) {
    window.ScrollManager.initialize();
  }
}

/**
 * 채팅 UI 초기화
 */
function _initializeChatUI() {
  if (window.ChatUI) {
    window.ChatUI.init();
  }

  // 채팅 토글 UI 초기화
  if (window.updateChatToggleUI) {
    window.updateChatToggleUI();
  }
}

/**
 * 티켓 헤더 초기화 - 개선된 조건부 실행
 */
async function _initializeTicketHeader(client) {

  if (window.Core.state.isModalView) {
    await collectTicketHeaderInfo(client);
  } else {
    // DOM 기반 모달 감지 시도
    const isInModal = window.parent !== window ||
      document.documentElement.classList.contains('modal-view') ||
      document.querySelector('.app-container')?.closest('.modal');

    if (isInModal) {
      await collectTicketHeaderInfo(client);
    }
  }
}

function _finalizeInitialization() {
  _setDefaultTab();
  _resetSummarySection();
}

/**
 * 기본 탭 설정
 */
function _setDefaultTab() {
  setTimeout(() => {
    requestAnimationFrame(() => {
      switchTab('summary');
    });
  }, 1200);
}

/**
 * 요약 섹션 초기 상태 리셋
 */
function _resetSummarySection() {
  const summarySection = document.querySelector('.summary-section');
  if (summarySection && summarySection.classList.contains('collapsed')) {
    summarySection.classList.remove('collapsed');
  }
}

// FDK 초기화
app.initialized().then(async function (client) {
  await initializeApp(client);
});

// 탭 전환 함수 (스크롤 위치 완전 고정) - 모달에서만 실행
function switchTab(tabName) {
  // 모달에서만 실행 가능
  if (!window.Core?.state?.isModalView) {
    return;
  }

  // DOM과 CSS가 완전히 준비되었는지 확인
  if (document.readyState !== 'complete') {
    // DOM 로딩 중... 탭 전환 지연
    setTimeout(() => switchTab(tabName), 100);
    return;
  }

  // CSS 스타일이 적용되었는지 확인
  const tabContent = document.querySelector('.tab-content');
  if (tabContent && getComputedStyle(tabContent).position === 'static') {
    // CSS 로딩 중... 탭 전환 지연
    setTimeout(() => switchTab(tabName), 100);
    return;
  }

  // 더 정확한 스크롤 위치 저장
  const currentScrollY = window.pageYOffset || document.documentElement.scrollTop || document.body.scrollTop || 0;
  // 탭 전환 시작

  // 부드러운 스크롤 차단 (overflow: hidden 대신 이벤트 차단만 사용)
  let isScrollBlocked = true;
  let scrollRestoreCount = 0;

  const blockScroll = (e) => {
    if (isScrollBlocked && scrollRestoreCount < 10) {
      e.preventDefault();
      e.stopPropagation();
      window.scrollTo(0, currentScrollY);
      scrollRestoreCount++;
      return false;
    }
  };

  // 스크롤 관련 이벤트만 차단 (overflow 변경 없음)
  window.addEventListener('scroll', blockScroll, { passive: false });
  document.addEventListener('wheel', blockScroll, { passive: false });
  document.addEventListener('touchmove', blockScroll, { passive: false });

  // DOM 변경 최소화를 위한 배치 처리
  const updates = [];

  document.querySelectorAll('.tab-button').forEach(b => {
    const shouldBeActive = b.dataset.tab === tabName;
    if (b.classList.contains('active') !== shouldBeActive) {
      updates.push(() => b.classList.toggle('active', shouldBeActive));
    }
  });

  document.querySelectorAll('.tab-content').forEach(c => {
    const shouldBeActive = c.dataset.tab === tabName;
    if (c.classList.contains('active') !== shouldBeActive) {
      updates.push(() => c.classList.toggle('active', shouldBeActive));
    }
  });

  // summary-section은 이제 탭 콘텐츠 내부에 있으므로 별도 제어 불필요

  // 채팅 입력창 처리 (레이아웃 변화 완전 방지)
  const chatInputContainer = document.getElementById('chatInputContainer');
  if (chatInputContainer) {
    const targetVisibility = tabName === 'copilot' ? 'visible' : 'hidden';
    if (chatInputContainer.style.visibility !== targetVisibility) {
      updates.push(() => {
        // 채팅 입력창은 항상 동일한 설정 유지
        chatInputContainer.style.display = 'flex';
        chatInputContainer.style.visibility = targetVisibility;

        // 채팅 탭으로 전환 시 추가 안정화
        if (tabName === 'copilot') {
          // DOM 변경 후 즉시 위치 고정
          setTimeout(() => {
            window.scrollTo(0, currentScrollY);
          }, 0);
        }
      });
    }
  }

  // 모든 DOM 변경을 한 번에 적용
  updates.forEach(update => update());

  // 즉시 위치 고정
  window.scrollTo(0, currentScrollY);

  // 정리 함수
  const cleanup = () => {
    // 이벤트 리스너 제거
    window.removeEventListener('scroll', blockScroll);
    document.removeEventListener('wheel', blockScroll);
    document.removeEventListener('touchmove', blockScroll);

    // 스크롤 차단 해제
    isScrollBlocked = false;

    // 최종 위치 확인 (로깅 제거됨)
    // 탭 전환 완료
  };

  // 단계적 정리
  setTimeout(() => {
    // 한 번 더 위치 고정
    window.scrollTo(0, currentScrollY);

    setTimeout(() => {
      cleanup();

      // JavaScript 클래스 관리 제거 - CSS로만 처리
    }, 30);
  }, 100);

  // 탭 전환시 자동 저장 제거 - 모달 닫을 때만 저장
}

// 헤더 정보 수집 함수
async function collectTicketHeaderInfo(client) {
  if (!client) {
    console.error('❌ collectTicketHeaderInfo: client가 null입니다');
    return;
  }

  try {

    const mapPriorityLabel = (value) => {
      if (typeof value === 'string' && value.trim() !== '') {
        return value;
      }
      const mapping = {
        1: 'Low',
        2: 'Medium',
        3: 'High',
        4: 'Urgent'
      };
      return mapping[value] || '';
    };

    const mapStatusLabel = (value) => {
      if (typeof value === 'string' && value.trim() !== '') {
        return value;
      }
      const mapping = {
        2: 'Open',
        3: 'Pending',
        4: 'Resolved',
        5: 'Closed'
      };
      return mapping[value] || '';
    };

    // 병렬로 데이터 가져오기
    const [ticketData, contactData, groupData] = await Promise.all([
      client.data.get('ticket').catch(e => {
        console.warn('⚠️ ticket 데이터 조회 실패:', e);
        return null;
      }),
      client.data.get('contact').catch(e => {
        console.warn('⚠️ contact 데이터 조회 실패:', e);
        return null;
      }),
      client.data.get('group').catch(e => {
        console.warn('⚠️ group 데이터 조회 실패:', e);
        return null;
      })
    ]);

    // 수집된 원본 데이터 로깅

    // 담당자 정보 처리 (request method 필요)
    let agentData = null;
    if (ticketData?.ticket?.responder_id) {
      try {
        const response = await client.request.invokeTemplate('getAgent', {
          context: { agentId: ticketData.ticket.responder_id }
        });

        if (response?.response) {
          const agent = JSON.parse(response.response);

          agentData = {
            contact: {
              name: agent.contact?.name || agent.name || 'Unassigned'
            },
            id: ticketData.ticket.responder_id
          };
        }
      } catch (e) {
        console.error('❌ 담당자 조회 실패:', e);
        // API 조회 실패 시에도 Unassigned로 설정
        agentData = {
          contact: { name: 'Unassigned' },
          id: null
        };
      }
    } else {
      // responder_id가 없으면 명시적으로 Unassigned 설정
      agentData = {
        contact: { name: 'Unassigned' },
        id: null
      };
    }

    // 통합된 데이터 구성
    const optimizedTicketData = {
      ticket: ticketData,
      contact: contactData,
      group: groupData,
      agent: agentData,
      lastUpdated: Date.now()
    };

    // 최종 구성된 데이터 로깅

    // Core에 상태 저장
    window.Core.state.ticketHeaderInfo = optimizedTicketData;

    // 캐시 메타데이터에 티켓 헤더 정보 저장
    if (window.TicketCacheManager && window.Core.state.ticketId) {
      try {
        window.TicketCacheManager.initialize(window.Core.state.ticketId);
        const existingMeta = window.TicketCacheManager.getTicketMetadata() || {};
        const rawTicket = ticketData?.ticket || {};
        const subject = rawTicket.subject || existingMeta.subject || '';
        const descriptionText = rawTicket.description_text || rawTicket.description || existingMeta.description_text || '';
        const priorityValue = rawTicket.priority_text || rawTicket.priority || existingMeta.priority || '';
        const statusValue = rawTicket.status_text || rawTicket.status || existingMeta.status || '';

        window.TicketCacheManager.saveTicketMetadata({
          ...existingMeta,
          headerInfo: optimizedTicketData,
          subject: subject,
          description_text: descriptionText,
          priority: mapPriorityLabel(priorityValue),
          status: mapStatusLabel(statusValue),
          requester: contactData?.contact?.name || contactData?.contact?.email || existingMeta.requester || '',
          agent: agentData?.contact?.name || existingMeta.agent || ''
        });
      } catch (cacheError) {
        console.warn('⚠️ 헤더 메타데이터 캐시 저장 실패:', cacheError);
      }
    }

    // HeaderManager를 통한 중앙화된 헤더 업데이트
    const currentEmotion = window.Core.state.data.emotionData;
    // 감정 분석만 직접 업데이트 (새 디자인)
    if (currentEmotion && currentEmotion.emotion && window.TicketUI) {
      window.TicketUI.updateEmotionElement(currentEmotion.emotion);
    } else {
      // 폴백: 직접 업데이트 (HeaderManager 로드 전)
      if (window.TicketUI?.updateTicketHeader) {
        await window.TicketUI.updateTicketHeader(optimizedTicketData, currentEmotion);
      } else {
        console.error('❌ HeaderManager와 TicketUI.updateTicketHeader 모두 사용 불가');
      }
    }

  } catch (e) {
    console.error('❌ FDK 데이터 수집 실패:', e);
  }
}

// 글로벌 함수들 - 모달에서만 실행
window.refreshData = async () => {
  // 모달에서만 새로고침 허용
  if (!window.Core?.state?.isModalView) {
    console.warn('⚠️ 새로고침은 모달에서만 가능합니다.');
    return;
  }

  const ticketId = window.Core.state.ticketId;
  if (!ticketId) return;

  // 새로운 캐시 시스템 초기화 및 정리
  if (window.TicketCacheManager) {
    window.TicketCacheManager.initialize(ticketId);
    window.TicketCacheManager.clearTicketCache();
  }

  try {
    // 사용자 새로고침
    if (window.ApiService && typeof window.ApiService.loadTicketData === 'function') {
      await window.ApiService.loadTicketData(ticketId);
    } else {
      throw new Error('ApiService를 사용할 수 없습니다');
    }
  } catch (e) {
    console.error('❌ 새로고침 실패:', e);
    window.TicketUI?.showError('error_data_load_failed');
  }
};

window.copySummary = async (e) => {
  // 모달에서만 실행 가능
  if (!window.Core?.state?.isModalView) {
    console.warn('⚠️ 요약 복사는 모달에서만 가능합니다.');
    return;
  }

  const text = document.getElementById('summaryText')?.textContent;
  if (text) {
    try {
      // 통일된 유틸 함수를 사용해 권한/폴백 처리
      await window.Utils.copyToClipboard(text);
      const btn = e?.target?.closest('.summary-action-btn');
      if (btn) {
        btn.innerHTML = '✅ 복사됨';
        setTimeout(() => btn.innerHTML = '📋 복사', 2000);
      }
    } catch (err) {
      console.error('복사 실패:', err);
      window.TicketUI?.showError('복사 기능을 사용할 수 없습니다.');
    }
  }
};

window.copyToClipboard = async (url, button) => {
  // 모달에서만 실행 가능
  if (!window.Core?.state?.isModalView) {
    console.warn('⚠️ 복사 기능은 모달에서만 가능합니다.');
    return;
  }

  if (url) {
    try {
      await window.Utils.copyToClipboard(url);
      if (button) {
        button.innerHTML = '✅';
        setTimeout(() => button.innerHTML = '📋 복사하기', 2000);
      }
    } catch (err) {
      console.error('복사 실패:', err);
      window.TicketUI?.showError('복사 기능을 사용할 수 없습니다.');
    }
  }
};

window.copySummaryToClipboard = async (button) => {
  // 모달에서만 실행 가능
  if (!window.Core?.state?.isModalView) {
    console.warn('⚠️ 복사 기능은 모달에서만 가능합니다.');
    return;
  }

  const summaryText = document.getElementById('summaryText');
  if (!summaryText) {
    console.error('요약 텍스트를 찾을 수 없습니다.');
    return;
  }

  // HTML 태그를 제거하고 순수 텍스트만 추출
  const textContent = summaryText.innerText || summaryText.textContent || '';

  if (!textContent.trim()) {
    console.warn('복사할 요약 내용이 없습니다.');
    return;
  }

  try {
    await window.Utils.copyToClipboard(textContent);
    if (button) {
      button.innerHTML = '✅ 복사됨';
      setTimeout(() => button.innerHTML = '📋 복사하기', 2000);
    }
  } catch (err) {
    console.error('요약 복사 실패:', err);
    window.TicketUI?.showError('복사 기능을 사용할 수 없습니다.');
  }
};

window.submitFeedback = async (type, e) => {
  // 모달에서만 실행 가능
  if (!window.Core?.state?.isModalView) {
    console.warn('⚠️ 피드백 제출은 모달에서만 가능합니다.');
    return;
  }

  const btn = e?.target?.closest('.feedback-btn');
  if (!btn) return;

  try {
    // 버튼 비활성화
    btn.disabled = true;
    const processingText = window.t ? window.t('feedback_processing') : 'Processing...';
    btn.innerHTML = `⏳ ${processingText}`;

    // 짧은 딜레이로 처리중 상태 보여주기
    await new Promise(resolve => setTimeout(resolve, 800));

    // 성공 메시지 표시
    if (type === 'positive') {
      const thanksText = window.t ? window.t('feedback_thanks') : 'Thank you!';
      btn.innerHTML = `👍 ${thanksText}`;
    } else {
      const improveText = window.t ? window.t('feedback_will_improve') : 'We\'ll improve!';
      btn.innerHTML = `👎 ${improveText}`;
    }

    // 다른 버튼도 비활성화
    const feedbackSection = btn.closest('.feedback-section');
    if (feedbackSection) {
      feedbackSection.querySelectorAll('.feedback-btn').forEach(b => {
        b.disabled = true;
      });
    }

    // 피드백 데이터를 로컬에 저장 (향후 백엔드 연동 시 사용)
    // const feedbackData = {
    //   feedback_type: type,
    //   timestamp: new Date().toISOString(),
    //   query: window.lastQuery || '',
    //   target_id: window.Core?.state?.ticketId || 'unknown'
    // };

    // 콘솔에 피드백 정보 로깅 (개발/디버깅용)
    // 사용자 피드백 수집 완료

  } catch (error) {
    console.error('피드백 처리 오류:', error);
    // 오류 시에도 성공한 것처럼 표시
    if (type === 'positive') {
      const thanksText = window.t ? window.t('feedback_thanks') : 'Thank you!';
      btn.innerHTML = `👍 ${thanksText}`;
    } else {
      const improveText = window.t ? window.t('feedback_will_improve') : 'We\'ll improve!';
      btn.innerHTML = `👎 ${improveText}`;
    }
    btn.disabled = true;
  }
};

window.scrollToBottom = () => {
  // 모달에서만 실행 가능
  if (!window.Core?.state?.isModalView) {
    return;
  }

  if (window.ChatUI) {
    window.ChatUI.scrollToBottom();
  }
};

// 채팅 관련 글로벌 함수들
window.handleChatKeydown = (event) => {
  if (window.ChatUI) {
    window.ChatUI.handleChatKeydown(event);
  }
};

window.adjustTextareaHeight = (textarea) => {
  if (window.ChatUI) {
    window.ChatUI.adjustTextareaHeight(textarea);
  }
};

window.handleCompositionStart = (event) => {
  if (window.ChatUI) {
    window.ChatUI.handleCompositionStart(event);
  }
};

window.handleCompositionEnd = (event) => {
  if (window.ChatUI) {
    window.ChatUI.handleCompositionEnd(event);
  }
};

window.sendMessage = () => {
  // 모달에서만 실행 가능
  if (!window.Core?.state?.isModalView) {
    return;
  }

  if (window.ChatUI && window.ChatUI.sendMessage) {
    window.ChatUI.sendMessage();
  }
};

window.toggleChatMode = () => {
  // 모달에서만 실행 가능
  if (!window.Core?.state?.isModalView) {
    return;
  }

  if (window.ChatUI) {
    window.ChatUI.toggleChatMode();
  }
};

// 헤더 관련 디버그 함수 제거 (새 디자인에서 불필요)

// SimilarTicketsManager 디버그 함수  
window.debugSimilarTickets = () => {
  if (window.SimilarTicketsManager) {
    window.SimilarTicketsManager.debug();
  } else {
    // SimilarTicketsManager가 로드되지 않음
  }
};

// 통합 디버그 함수
window.debugManagers = () => {
  // Manager Debug Info
  window.debugHeader();
  window.debugSimilarTickets();
};

// Note: isSendingMessage variable removed as it was unused

// === 채팅 히스토리 관리 기능 ===

/**
 * 채팅 히스토리 통계 표시 - 모달에서만 실행
 */
window.showChatHistoryStats = () => {
  if (!window.Core) {
    console.error('Core 모듈을 사용할 수 없습니다.');
    return;
  }

  const stats = window.Core.getChatHistoryStats();
  if (!stats) {
    console.error('현재 티켓의 채팅 히스토리 통계를 가져올 수 없습니다.');
    return;
  }

  // 다양한 구조 지원
  const currentTotal = stats.current?.total || stats.totalCount || 0;
  const currentRag = stats.current?.rag || stats.ragCount || 0;
  const currentChat = stats.current?.chat || stats.generalCount || 0;
  const persistedTotal = stats.persisted?.total || stats.totalCount || 0;

  /*const createdDate = stats.persisted.createdAt ? 
    new Date(stats.persisted.createdAt).toLocaleDateString() : 'Unknown';
  const lastAccessDate = stats.persisted.lastAccessed ? 
    new Date(stats.persisted.lastAccessed).toLocaleDateString() : 'Unknown';

  const message = [
    '📊 채팅 히스토리 통계',
    '',
    `🎯 현재 세션 메시지: ${currentTotal}개`,
    `  - RAG 모드: ${currentRag}개`,
    `  - 자유대화 모드: ${currentChat}개`,
    '',
    `💾 저장된 총 메시지: ${persistedTotal}개`,
    `📅 생성일: ${createdDate}`,
    `🕒 마지막 접근: ${lastAccessDate}`,
    `🎫 티켓 ID: ${stats.ticketId}`
  ].join('\n');
  
  console.log(message);*/

  // 배너에는 핵심 정보 표시 (가로 정렬로 높이 최소화)
  if (window.NotificationBanner) {
    const bannerTemplate = window.t ? window.t('session_stats_banner') : '📊 Current Session: {current} messages (RAG: {rag}, General: {chat}) | 💾 Total Saved: {total} messages';
    const bannerMessage = bannerTemplate
      .replace('{current}', currentTotal)
      .replace('{rag}', currentRag)
      .replace('{chat}', currentChat)
      .replace('{total}', persistedTotal);

    window.NotificationBanner.info(bannerMessage, 5000);
  }
};

/**
 * 채팅 히스토리 내보내기 - 모달에서만 실행
 */
window.exportChatHistory = () => {
  if (!window.Core) {
    console.error('Core 모듈을 사용할 수 없습니다.');
    return;
  }

  const stats = window.Core.getChatHistoryStats();

  // 다양한 구조 지원
  const totalCount = stats?.current?.total || stats?.totalCount || 0;
  const ragCount = stats?.current?.rag || stats?.ragCount || 0;
  const chatCount = stats?.current?.chat || stats?.generalCount || 0;

  if (!stats || totalCount === 0) {
    if (window.NotificationBanner) {
      window.NotificationBanner.warning(window.t ? window.t('notification_no_chat_history_to_export') : 'No chat history to export.');
    }
    return;
  }

  try {
    const chatHistory = window.Core.state.chatHistory;
    const ticketId = window.Core.state.ticketId;

    // 내보낼 데이터 구성
    const exportData = {
      metadata: {
        ticketId: ticketId,
        exportDate: new Date().toISOString(),
        totalMessages: totalCount,
        ragMessages: ragCount,
        chatMessages: chatCount
      },
      history: {
        rag: chatHistory.rag || [],
        chat: chatHistory.chat || []
      }
    };

    // JSON 문자열로 변환
    const jsonString = JSON.stringify(exportData, null, 2);

    // 파일 다운로드
    const blob = new Blob([jsonString], { type: 'application/json' });
    const url = URL.createObjectURL(blob);

    const a = document.createElement('a');
    a.href = url;
    a.download = `chat_history_${ticketId}_${new Date().toISOString().split('T')[0]}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);

    URL.revokeObjectURL(url);

    if (window.NotificationBanner) {
      const exportMessage = window.t ? window.t('notification_chat_exported') : 'Chat history has been exported.';
      window.NotificationBanner.success(`${exportMessage} (${a.download})`);
    }

  } catch (error) {
    console.error('채팅 히스토리 내보내기 실패:', error);
    if (window.NotificationBanner) {
      window.NotificationBanner.error(window.t ? window.t('notification_export_failed') : 'Failed to export chat history.');
    }
  }
};

/**
 * 삭제 확인 UI를 독립적으로 표시
 */
function showDeleteConfirmFooter(stats) {
  // 기존 확인 UI가 있다면 제거
  const existingConfirm = document.getElementById('deleteConfirmSection');
  if (existingConfirm) {
    existingConfirm.remove();
  }

  // 번역된 텍스트 가져오기
  const confirmTitle = window.t ? window.t('delete_confirm_title') : '⚠️ Delete Confirmation';
  const confirmMessage = window.t ? window.t('delete_confirm_message') : ' messages (RAG: {rag}, General: {chat}) • Cannot be undone';
  const confirmYes = window.t ? window.t('delete_confirm_yes') : 'Confirm (Y)';
  const confirmNo = window.t ? window.t('delete_confirm_no') : 'Cancel (N)';

  // 다양한 구조 지원
  const totalCount = stats.current?.total || stats.totalCount || 0;
  const ragCount = stats.current?.rag || stats.ragCount || 0;
  const chatCount = stats.current?.chat || stats.generalCount || 0;

  // 메시지 포맷팅 (플레이스홀더 치환)
  const formattedMessage = `${totalCount}${confirmMessage.replace('{rag}', ragCount).replace('{chat}', chatCount)}`;

  // 확인 메시지 HTML 생성
  const confirmHtml = `
    <div class="delete-confirm-overlay" id="deleteConfirmSection">
      <div class="delete-confirm-section">
        <div class="confirm-message">
          <div class="confirm-title">${confirmTitle}</div>
          <div class="confirm-details">
            <strong>${formattedMessage}</strong>
          </div>
        </div>
        <div class="confirm-actions">
          <button class="confirm-btn yes-btn" onclick="confirmDeleteHistory()">
            ${confirmYes}
          </button>
          <button class="confirm-btn no-btn" onclick="cancelDeleteHistory()">
            ${confirmNo}
          </button>
        </div>
      </div>
    </div>
  `;

  // body에 직접 추가 (footer와 독립적으로)
  document.body.insertAdjacentHTML('beforeend', confirmHtml);

  // 키보드 이벤트 리스너 추가
  const handleKeyDown = (e) => {
    if (e.key === 'y' || e.key === 'Y') {
      window.confirmDeleteHistory();
    } else if (e.key === 'n' || e.key === 'N' || e.key === 'Escape') {
      window.cancelDeleteHistory();
    }
  };

  document.addEventListener('keydown', handleKeyDown);

  // cleanup function
  window._deleteConfirmCleanup = () => {
    document.removeEventListener('keydown', handleKeyDown);
    delete window._deleteConfirmCleanup;
  };
}

/**
 * Footer 확인 메시지 숨기기
 */
function hideDeleteConfirmFooter() {
  const confirmSection = document.getElementById('deleteConfirmSection');

  if (confirmSection) {
    confirmSection.remove();
  }

  // cleanup
  if (window._deleteConfirmCleanup) {
    window._deleteConfirmCleanup();
  }
}

/**
 * 삭제 확인 (예 버튼)
 */
window.confirmDeleteHistory = () => {
  try {
    const success = window.Core.clearChatHistoryPersistent();
    if (success) {
      if (window.NotificationBanner) {
        window.NotificationBanner.success(window.t ? window.t('notification_chat_deleted') : 'Chat history has been deleted.');
      }
      // 채팅 UI 새로고침
      if (window.ChatUI?.clearChatDisplay) {
        window.ChatUI.clearChatDisplay();
      }
    } else {
      if (window.NotificationBanner) {
        window.NotificationBanner.error(window.t ? window.t('notification_delete_failed') : 'Failed to delete chat history.');
      }
    }
  } catch (error) {
    console.error('채팅 히스토리 삭제 실패:', error);
    if (window.NotificationBanner) {
      window.NotificationBanner.error(window.t ? window.t('notification_delete_error') : 'An error occurred while deleting chat history.');
    }
  }

  hideDeleteConfirmFooter();
};

/**
 * 삭제 취소 (아니오 버튼)
 */
window.cancelDeleteHistory = () => {
  hideDeleteConfirmFooter();
  if (window.NotificationBanner) {
    window.NotificationBanner.info(window.t ? window.t('notification_delete_cancelled') : 'Deletion was cancelled.');
  }
};



/**
 * 강제 테스트 - 채팅 히스토리가 없어도 기능 작동 테스트
 */
window.testChatFunctions = () => {


  window.showChatHistoryStats();


  window.exportChatHistory();


  window.clearChatHistoryWithConfirm();

};

/**
 * 확인 후 채팅 히스토리 삭제 - 모달에서만 실행
 */
window.clearChatHistoryWithConfirm = () => {
  if (!window.Core) {
    console.error('Core 모듈을 사용할 수 없습니다.');
    return;
  }

  const stats = window.Core.getChatHistoryStats();
  if (!stats) {
    if (window.NotificationBanner) {
      window.NotificationBanner.warning(window.t ? window.t('notification_no_chat_history_to_delete') : 'No chat history to delete.');
    }
    return;
  }

  // 다양한 구조 지원
  const totalCount = stats.current?.total || stats.totalCount || 0;

  if (totalCount === 0) {
    if (window.NotificationBanner) {
      window.NotificationBanner.warning(window.t ? window.t('notification_no_chat_history_to_delete') : 'No chat history to delete.');
    }
    return;
  }

  // Footer에 확인 메시지 표시
  showDeleteConfirmFooter(stats);
};