/**
 * 스크롤 처리 및 UI 상태 관리 - 개선된 버전
 */

window.ScrollManager = {
  // 상태
  summaryCollapsed: false,
  isModalView: false,
  
  /**
   * 초기화
   */
  initialize() {
    
    // 모달 뷰 여부 확인
    this.isModalView = window.Core?.state?.isModalView || false;
    
    const toggleBtn = document.getElementById('summaryToggleBtn');
    
    // 토글 버튼 이벤트
    if (toggleBtn) {
      toggleBtn.addEventListener('click', () => this.toggleSummary());
    }
    
    // 스크롤 이벤트 최적화
    this.setupScrollOptimization();
  },
  
  /**
   * 요약 섹션 토글 (스크롤 위치 유지하며 탭 위치 조정)
   */
  toggleSummary() {
    const elements = this._getToggleElements();
    if (!elements.summarySection || !elements.toggleBtn) return;
    
    const currentScrollY = this._saveCurrentScrollPosition();
    this.summaryCollapsed = !this.summaryCollapsed;
    
    this._updateToggleAppearance(elements, this.summaryCollapsed);
    this._restoreScrollPosition(currentScrollY);
    this._saveModalState();
  },
  
  /**
   * 토글 관련 DOM 요소 가져오기
   */
  _getToggleElements() {
    return {
      summarySection: document.getElementById('summarySection'),
      toggleBtn: document.getElementById('summaryToggleBtn')
    };
  },
  
  /**
   * 현재 스크롤 위치 저장
   */
  _saveCurrentScrollPosition() {
    return window.pageYOffset || document.documentElement.scrollTop;
  },
  
  /**
   * 토글 상태에 따른 UI 업데이트
   */
  _updateToggleAppearance(elements, isCollapsed) {
    const { summarySection, toggleBtn } = elements;
    const btnIcon = toggleBtn.querySelector('.btn-icon');
    const btnText = toggleBtn.querySelector('.btn-text');
    
    if (isCollapsed) {
      this._setCollapsedState(summarySection, toggleBtn, btnIcon, btnText);
    } else {
      this._setExpandedState(summarySection, toggleBtn, btnIcon, btnText);
    }
  },
  
  /**
   * 접힌 상태 설정
   */
  _setCollapsedState(summarySection, toggleBtn, btnIcon, btnText) {
    summarySection.classList.add('collapsed');
    if (btnIcon) btnIcon.textContent = '⌄';
    if (btnText) btnText.textContent = window.t ? window.t('copy_button') : '복사하기';
    toggleBtn.title = window.t ? window.t('copy_button') : '복사하기';
  },
  
  /**
   * 펼친 상태 설정
   */
  _setExpandedState(summarySection, toggleBtn, btnIcon, btnText) {
    summarySection.classList.remove('collapsed');
    if (btnIcon) btnIcon.textContent = '⌃';
    if (btnText) btnText.textContent = window.t ? window.t('copy_button') : '복사하기';
    toggleBtn.title = window.t ? window.t('copy_button') : '복사하기';
  },
  
  /**
   * 스크롤 위치 복원
   */
  _restoreScrollPosition(scrollY) {
    setTimeout(() => {
      window.scrollTo(0, scrollY);
    }, 0);
  },
  
  /**
   * 모달 상태 저장
   */
  _saveModalState() {
    if (this.isModalView && window.Core) {
      window.Core.autoSaveState();
    }
  },
  
  /**
   * 스크롤 최적화 설정
   */
  setupScrollOptimization() {
    // 전체 페이지 스크롤 최적화 (body 기준)
    document.body.style.scrollBehavior = 'smooth';
    
    // 채팅 메시지 스크롤 최적화
    const chatMessages = document.querySelector('.chat-messages');
    if (chatMessages) {
      chatMessages.style.scrollBehavior = 'smooth';
    }
  },
  
  /**
   * 스크롤을 특정 위치로 이동
   */
  scrollToElement(elementId, offset = 0) {
    const element = document.getElementById(elementId);
    
    if (element) {
      const elementTop = element.offsetTop - offset;
      window.scrollTo({
        top: elementTop,
        behavior: 'smooth'
      });
    }
  },
  
  /**
   * 맨 아래로 스크롤 (채팅용)
   */
  scrollToBottom() {
    const chatMessages = document.querySelector('.chat-messages');
    
    if (chatMessages) {
      chatMessages.scrollTo({
        top: chatMessages.scrollHeight,
        behavior: 'smooth'
      });
    }
  },
  
  /**
   * 스크롤 위치 복원
   */
  restoreScrollPosition(position) {
    if (typeof position === 'number') {
      window.scrollTo(0, position);
    }
  },
  
  /**
   * 현재 스크롤 위치 저장
   */
  saveScrollPosition() {
    return window.pageYOffset || document.documentElement.scrollTop;
  }
};