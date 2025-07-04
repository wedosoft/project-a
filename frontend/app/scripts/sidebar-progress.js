/**
 * @fileoverview Sidebar Progress UI Component for Streaming Data Loading
 * @description 사이드바 진행률 UI 컴포넌트 - 스트리밍 데이터 로딩 시각화
 *
 * 이 컴포넌트는 티켓 사이드바에서 백그라운드 데이터 로딩 진행률을 표시합니다.
 * 사용자가 모달을 열기 전에 데이터 준비 상태를 미리 확인할 수 있도록 도와줍니다.
 *
 * 주요 기능:
 * - 단계별 진행률 표시 (티켓 조회, 요약 생성, 유사 티켓 검색, KB 문서 검색)
 * - 실시간 진행률 업데이트
 * - 완료 시 자동 숨김 또는 최소화
 * - 에러 상태 표시
 * - 컴팩트한 사이드바 친화적 디자인
 *
 * @namespace SidebarProgress
 * @version 1.0.0
 * @since 2025-07-03
 */

/**
 * 사이드바 진행률 컴포넌트
 */
const SidebarProgress = {
  // 컴포넌트 상태
  isInitialized: false,
  isVisible: false,
  containerId: 'sidebar-progress-container',
  
  // 단계별 아이콘 정의
  stageIcons: {
    ticket_fetch: '📋',
    summary: '🎯', 
    similar_tickets: '🔍',
    kb_documents: '📚'
  },
  
  // 단계별 한국어 라벨
  stageLabels: {
    ticket_fetch: '티켓 정보',
    summary: 'AI 요약 생성', 
    similar_tickets: '유사 티켓 검색',
    kb_documents: 'KB 문서 검색'
  },

  /**
   * 컴포넌트 초기화
   * 사이드바에 진행률 컨테이너를 생성하고 초기 상태를 설정합니다.
   */
  init() {
    if (this.isInitialized) {
      console.log('⚠️ SidebarProgress가 이미 초기화됨');
      return;
    }

    try {
      this.createProgressContainer();
      this.attachEventListeners();
      this.isInitialized = true;
      console.log('✅ SidebarProgress 초기화 완료');
    } catch (error) {
      console.error('❌ SidebarProgress 초기화 실패:', error);
    }
  },

  /**
   * 진행률 컨테이너 생성
   * 사이드바에 진행률을 표시할 HTML 구조를 생성합니다.
   */
  createProgressContainer() {
    // 기존 컨테이너 제거
    const existingContainer = document.getElementById(this.containerId);
    if (existingContainer) {
      existingContainer.remove();
    }

    // 새 컨테이너 생성
    const container = document.createElement('div');
    container.id = this.containerId;
    container.className = 'sidebar-progress-container hidden';
    
    container.innerHTML = `
      <div class="sidebar-progress-header">
        <div class="sidebar-progress-title">
          <span class="sidebar-progress-icon">🤖</span>
          <span class="sidebar-progress-text">AI 데이터 준비 중...</span>
        </div>
        <div class="sidebar-progress-percent">0%</div>
      </div>
      
      <div class="sidebar-progress-bar-container">
        <div class="sidebar-progress-bar">
          <div class="sidebar-progress-fill"></div>
        </div>
      </div>
      
      <div class="sidebar-progress-stages">
        ${Object.entries(this.stageLabels).map(([stageKey, label]) => `
          <div class="sidebar-progress-stage" data-stage="${stageKey}">
            <span class="stage-icon">${this.stageIcons[stageKey]}</span>
            <span class="stage-label">${label}</span>
            <span class="stage-status">⏳</span>
          </div>
        `).join('')}
      </div>
      
      <div class="sidebar-progress-actions">
        <button class="sidebar-progress-minimize" title="최소화">−</button>
        <button class="sidebar-progress-close" title="닫기">×</button>
      </div>
    `;

    // 사이드바 또는 body에 추가
    const sidebarElement = this.findSidebarElement();
    if (sidebarElement) {
      // 사이드바 최상단에 추가
      sidebarElement.insertBefore(container, sidebarElement.firstChild);
    } else {
      // 사이드바를 찾을 수 없으면 body 우측 상단에 고정
      container.classList.add('fixed-position');
      document.body.appendChild(container);
    }

    console.log('📊 진행률 컨테이너 생성 완료');
  },

  /**
   * 사이드바 요소 찾기
   * Freshdesk의 사이드바 구조에서 적절한 부모 요소를 찾습니다.
   */
  findSidebarElement() {
    // Freshdesk 사이드바 가능한 선택자들
    const sidebarSelectors = [
      '.sidebar',
      '#sidebar', 
      '.ticket-sidebar',
      '.right-sidebar',
      '.custom-app-sidebar',
      '[class*="sidebar"]'
    ];

    for (const selector of sidebarSelectors) {
      const element = document.querySelector(selector);
      if (element) {
        console.log(`📍 사이드바 요소 발견: ${selector}`);
        return element;
      }
    }

    console.warn('⚠️ 사이드바 요소를 찾을 수 없음 - 고정 위치 사용');
    return null;
  },

  /**
   * 이벤트 리스너 연결
   * 최소화, 닫기 버튼 및 글로벌 상태 변화 감지
   */
  attachEventListeners() {
    // 컨테이너 내 버튼 이벤트
    document.addEventListener('click', (event) => {
      if (event.target.matches('.sidebar-progress-minimize')) {
        this.toggleMinimize();
      } else if (event.target.matches('.sidebar-progress-close')) {
        this.hide();
      }
    });

    // 전역 상태 변화 감지 (폴링 방식)
    this.startStatusPolling();
  },

  /**
   * 상태 폴링 시작 (실시간 스트리밍 모니터링 강화)
   * GlobalState의 스트리밍 상태를 주기적으로 확인하여 UI 업데이트
   */
  startStatusPolling() {
    if (this.pollingInterval) {
      clearInterval(this.pollingInterval);
    }

    this.pollingInterval = setInterval(() => {
      if (typeof GlobalState !== 'undefined' && this.isVisible) {
        const streamingStatus = GlobalState.getStreamingStatus();
        
        // 스트리밍 중이면 실시간 진행률 업데이트
        if (streamingStatus.is_streaming) {
          this.updateProgress(streamingStatus);
          console.log(`📈 실시간 진행률: ${streamingStatus.overall_progress}%`);
        }
        
        // 스트리밍이 완료되면 완료 상태 표시
        if (!streamingStatus.is_streaming && streamingStatus.overall_progress === 100) {
          console.log('🎉 스트리밍 완료 감지 - 완료 UI 표시');
          
          const container = document.getElementById(this.containerId);
          if (container) {
            this.showCompletion(container);
          }
          
          // 5초 후 자동 최소화 (완료 메시지를 충분히 보여준 후)
          setTimeout(() => {
            this.minimize();
            console.log('📊 스트리밍 완료 - 사이드바 진행률 최소화됨');
          }, 5000);
        }
        
        // 스트리밍 에러가 있으면 에러 표시
        if (streamingStatus.error) {
          const container = document.getElementById(this.containerId);
          if (container) {
            this.showError(container, streamingStatus.error);
          }
        }
      }
    }, 500); // 0.5초마다 확인 (부드러운 실시간 업데이트)
    
    console.log('📊 실시간 스트리밍 모니터링 시작 (500ms 간격)');
  },

  /**
   * 진행률 표시 시작
   */
  show() {
    const container = document.getElementById(this.containerId);
    if (!container) {
      console.error('❌ 진행률 컨테이너를 찾을 수 없음');
      return;
    }

    container.classList.remove('hidden');
    this.isVisible = true;

    // 초기 상태로 리셋
    this.resetProgress();

    console.log('📊 사이드바 진행률 표시 시작');
  },

  /**
   * 간단한 로딩 표시
   * 복잡한 진행률 대신 단순한 "로딩 중" 상태만 표시
   */
  showSimpleLoading() {
    const container = document.getElementById(this.containerId);
    if (!container) {
      console.error('❌ 진행률 컨테이너를 찾을 수 없음');
      return;
    }

    // 간단한 로딩 UI로 교체
    container.innerHTML = `
      <div class="sidebar-simple-loading">
        <div class="loading-icon">🤖</div>
        <div class="loading-text">AI 데이터 준비 중...</div>
        <div class="loading-spinner"></div>
        <button class="sidebar-progress-close" title="닫기">×</button>
      </div>
    `;

    container.classList.remove('hidden');
    this.isVisible = true;

    console.log('🎯 사이드바 간단 로딩 표시 시작');
  },

  /**
   * 진행률 숨김
   */
  hide() {
    const container = document.getElementById(this.containerId);
    if (container) {
      container.classList.add('hidden');
    }
    
    this.isVisible = false;

    // 폴링 중지
    if (this.pollingInterval) {
      clearInterval(this.pollingInterval);
      this.pollingInterval = null;
    }

    console.log('📊 사이드바 진행률 숨김');
  },

  /**
   * 최소화/최대화 토글
   */
  toggleMinimize() {
    const container = document.getElementById(this.containerId);
    if (container) {
      container.classList.toggle('minimized');
      
      const minimizeBtn = container.querySelector('.sidebar-progress-minimize');
      if (minimizeBtn) {
        minimizeBtn.textContent = container.classList.contains('minimized') ? '+' : '−';
      }
    }
  },

  /**
   * 진행률 업데이트
   * @param {Object} streamingStatus - GlobalState에서 가져온 스트리밍 상태
   */
  updateProgress(streamingStatus) {
    if (!this.isVisible) return;

    const container = document.getElementById(this.containerId);
    if (!container) return;

    try {
      // 전체 진행률 업데이트
      this.updateOverallProgress(container, streamingStatus.overall_progress);

      // 단계별 상태 업데이트  
      Object.entries(streamingStatus.stages).forEach(([stageKey, stageData]) => {
        this.updateStageStatus(container, stageKey, stageData);
      });

      // 에러 상태 처리
      if (streamingStatus.error) {
        this.showError(container, streamingStatus.error);
      }

      // 완료 상태 처리
      if (!streamingStatus.is_streaming && streamingStatus.overall_progress === 100) {
        this.showCompletion(container);
      }

    } catch (error) {
      console.error('❌ 진행률 업데이트 실패:', error);
    }
  },

  /**
   * 전체 진행률 업데이트
   * @param {HTMLElement} container - 컨테이너 요소
   * @param {number} progress - 진행률 (0-100)
   */
  updateOverallProgress(container, progress) {
    const percentElement = container.querySelector('.sidebar-progress-percent');
    const fillElement = container.querySelector('.sidebar-progress-fill');

    if (percentElement) {
      percentElement.textContent = `${progress}%`;
    }

    if (fillElement) {
      fillElement.style.width = `${progress}%`;
    }
  },

  /**
   * 단계별 상태 업데이트
   * @param {HTMLElement} container - 컨테이너 요소
   * @param {string} stageKey - 단계 키
   * @param {Object} stageData - 단계 데이터
   */
  updateStageStatus(container, stageKey, stageData) {
    const stageElement = container.querySelector(`[data-stage="${stageKey}"]`);
    if (!stageElement) return;

    const statusElement = stageElement.querySelector('.stage-status');
    if (!statusElement) return;

    if (stageData.completed) {
      statusElement.textContent = '✅';
      stageElement.classList.add('completed');
    } else if (stageData.progress > 0) {
      statusElement.textContent = '⟳';
      stageElement.classList.add('in-progress');
    } else {
      statusElement.textContent = '⏳';
      stageElement.classList.remove('completed', 'in-progress');
    }

    // 진행률 메시지 표시 (툴팁)
    if (stageData.message) {
      stageElement.title = stageData.message;
    }
  },

  /**
   * 에러 상태 표시
   * @param {HTMLElement} container - 컨테이너 요소  
   * @param {string} error - 에러 메시지
   */
  showError(container, error) {
    const headerElement = container.querySelector('.sidebar-progress-header');
    if (headerElement) {
      headerElement.classList.add('error');
      
      const textElement = container.querySelector('.sidebar-progress-text');
      if (textElement) {
        textElement.textContent = '오류 발생';
      }
      
      const iconElement = container.querySelector('.sidebar-progress-icon');
      if (iconElement) {
        iconElement.textContent = '⚠️';
      }
    }
    
    console.error('📊 스트리밍 에러:', error);
  },

  /**
   * 완료 상태 표시 (예쁘게 데코레이션)
   * @param {HTMLElement} container - 컨테이너 요소
   */
  showCompletion(container) {
    const headerElement = container.querySelector('.sidebar-progress-header');
    if (headerElement) {
      headerElement.classList.add('completed');
      
      // 애니메이션 효과와 함께 완료 메시지 표시
      headerElement.style.transition = 'all 0.3s ease';
      headerElement.style.background = 'linear-gradient(135deg, #28a745, #20c997)';
      headerElement.style.color = 'white';
      headerElement.style.borderRadius = '8px';
      headerElement.style.padding = '8px 12px';
      headerElement.style.transform = 'scale(1.02)';
      
      const textElement = container.querySelector('.sidebar-progress-text');
      if (textElement) {
        textElement.innerHTML = '<strong>🎉 AI 분석 완료!</strong>';
        textElement.style.fontSize = '13px';
        textElement.style.fontWeight = 'bold';
      }
      
      const iconElement = container.querySelector('.sidebar-progress-icon');
      if (iconElement) {
        iconElement.innerHTML = '✨';
        iconElement.style.fontSize = '16px';
      }
      
      // 3초 후 부드럽게 최소화
      setTimeout(() => {
        if (headerElement) {
          headerElement.style.transform = 'scale(0.95)';
          headerElement.style.opacity = '0.8';
          if (textElement) {
            textElement.innerHTML = '💫 준비됨';
            textElement.style.fontSize = '11px';
          }
        }
      }, 3000);
    }
    
    console.log('🎉 스트리밍 완료 - 모든 데이터 준비됨! 사용자가 모달을 열 수 있습니다.');
  },

  /**
   * 진행률 초기화
   */
  resetProgress() {
    const container = document.getElementById(this.containerId);
    if (!container) return;

    // 전체 진행률 초기화
    const percentElement = container.querySelector('.sidebar-progress-percent');
    const fillElement = container.querySelector('.sidebar-progress-fill');
    
    if (percentElement) percentElement.textContent = '0%';
    if (fillElement) fillElement.style.width = '0%';

    // 헤더 상태 초기화
    const headerElement = container.querySelector('.sidebar-progress-header');
    if (headerElement) {
      headerElement.classList.remove('error', 'completed');
    }

    const textElement = container.querySelector('.sidebar-progress-text');
    if (textElement) {
      textElement.textContent = 'AI 데이터 준비 중...';
    }

    const iconElement = container.querySelector('.sidebar-progress-icon');
    if (iconElement) {
      iconElement.textContent = '🤖';
    }

    // 모든 단계 초기화
    const stageElements = container.querySelectorAll('.sidebar-progress-stage');
    stageElements.forEach(stageElement => {
      stageElement.classList.remove('completed', 'in-progress');
      const statusElement = stageElement.querySelector('.stage-status');
      if (statusElement) {
        statusElement.textContent = '⏳';
      }
    });
  },

  /**
   * 컴포넌트 정리
   * 메모리 누수 방지를 위한 리소스 정리
   */
  destroy() {
    this.hide();
    
    const container = document.getElementById(this.containerId);
    if (container) {
      container.remove();
    }

    if (this.pollingInterval) {
      clearInterval(this.pollingInterval);
      this.pollingInterval = null;
    }

    this.isInitialized = false;
    this.isVisible = false;

    console.log('🧹 SidebarProgress 정리 완료');
  },

  /**
   * 컴포넌트 가용성 확인
   * @returns {boolean} 사용 가능 여부
   */
  isAvailable() {
    const dependencies = ['GlobalState'];
    const missing = dependencies.filter(dep => typeof window[dep] === 'undefined');

    if (missing.length > 0) {
      console.warn('[SidebarProgress] 누락된 의존성:', missing);
      return false;
    }

    return true;
  }
};

// 모듈 가용성 확인
if (!SidebarProgress.isAvailable()) {
  console.warn('⚠️ SidebarProgress: 필수 의존성이 없어 비활성화됨');
} else {
  // 전역으로 export
  window.SidebarProgress = SidebarProgress;
  
  // 모듈 의존성 시스템에 등록
  if (typeof window.ModuleDependencyManager !== 'undefined') {
    window.ModuleDependencyManager.registerModule('sidebar-progress', Object.keys(SidebarProgress).length, ['globals']);
  }

  // 모듈 등록 (로그 없음)
}