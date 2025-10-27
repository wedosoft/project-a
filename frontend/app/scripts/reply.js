/**
 * Reply Editor Module - AI 추천답변 에디터 (현대적 UI)
 */

window.ReplyEditor = {
  isGenerating: false,
  isEditing: false,
  currentResponse: '',
  client: null,  // FDK client 저장

  /**
   * 초기화 (FDK client 사용)
   */
  async init(client) {

    try {
      // FDK client 저장
      if (client) {
        this.client = client;
      }

      // Core 모듈 확인 및 초기화
      if (window.Core && typeof window.Core.init === 'function') {
        // Core 모듈에 client 전달하여 초기화
        if (client) {
          await window.Core.initialize(client);

          // 티켓 ID 확인
          if (!window.Core.state.ticketId) {
            console.warn('⚠️ 티켓 ID가 없습니다');
            this.showStatus('티켓 정보를 찾을 수 없습니다', 'error');
          }
        } else {
          // FDK 없이 초기화
          window.Core.init();
          this.showStatus('개발 환경 - FDK 없음', 'info');
        }
      } else {
        console.warn('⚠️ Core 모듈이 없거나 init 함수가 없습니다');
        this.showStatus('Core 모듈 없음 - 제한된 기능', 'error');
      }

      // UI 이벤트 설정
      this.setupEventListeners();

      // 디버그 정보 업데이트
      this.updateDebugInfo();

    } catch (error) {
      console.error('❌ Reply Editor 초기화 실패:', error);
      this.showStatus('초기화 실패: ' + error.message, 'error');
    }
  },


  /**
   * 이벤트 리스너 설정
   */
  setupEventListeners() {
    // 생성 버튼
    const generateButton = document.getElementById('generateButton');
    if (generateButton) {
      generateButton.addEventListener('click', () => {
        this.generateReply().catch(err => {
          console.error('❌ generateReply 실행 중 오류:', err);
          this.showStatus(`오류: ${err.message}`, 'error');
        });
      });
    } else {
      console.error('❌ generateButton 요소를 찾을 수 없습니다');
    }

    // 커서 위치에 삽입 버튼
    const insertAtCursorButton = document.getElementById('insertAtCursorButton');
    if (insertAtCursorButton) {
      insertAtCursorButton.addEventListener('click', () => this.insertToEditor(false));
    }

    // 전체 내용 교체 버튼
    const replaceContentButton = document.getElementById('replaceContentButton');
    if (replaceContentButton) {
      replaceContentButton.addEventListener('click', () => this.insertToEditor(true));
    }

    // 지우기 버튼
    const clearButton = document.getElementById('clearButton');
    if (clearButton) {
      clearButton.addEventListener('click', () => this.clearResponse());
    }

    // 텍스트 영역 변경 감지
    const previewTextarea = document.getElementById('previewTextarea');
    if (previewTextarea) {
      previewTextarea.addEventListener('input', () => this.updateWordCount());
      previewTextarea.addEventListener('focus', () => this.onTextareaFocus());
      previewTextarea.addEventListener('blur', () => this.onTextareaBlur());
    }

  },

  /**
   * AI 추천답변 생성
   */
  async generateReply() {

    if (this.isGenerating) {
      return;
    }

    // 상태 로깅 제거됨

    try {
      this.setGeneratingState(true);
      this.clearResponse();

      // 티켓 ID 획득 (FDK 또는 fallback)
      let ticketId;

      if (this.client) {
        // FDK 환경: client에서 티켓 정보 가져오기
        try {
          const ticketData = await this.client.data.get('ticket');
          ticketId = ticketData?.ticket?.id;
        } catch (error) {
          console.error('FDK 티켓 정보 가져오기 실패:', error);
          throw new Error('티켓 정보를 가져올 수 없습니다: ' + error.message);
        }
      } else {
        // 개발 환경: Core 모듈에서 티켓 ID 가져오기
        console.warn('⚠️ FDK client 없음 - Core 모듈에서 티켓 ID 확인');
        ticketId = window.Core?.state?.ticketId;

        // 티켓 ID가 없으면 명확한 에러 표시 (기본값 사용 금지)
        if (!ticketId) {
          throw new Error('FDK 환경이 아니며 티켓 ID를 찾을 수 없습니다. Freshdesk 티켓 페이지에서 앱을 실행해주세요.');
        }
      }

      if (!ticketId) {
        throw new Error('티켓 정보를 찾을 수 없습니다. Freshdesk 티켓 페이지에서 사용해주세요.');
      }

      // 기본적으로 스트리밍 모드 사용
      await this.callReplyEndpointStreaming(ticketId);

    } catch (error) {
      console.error('❌ AI 추천답변 생성 실패:', error);
      console.error('❌ 오류 상세:', error.stack);
      this.showStatus(error.message || '생성 실패', 'error');
      this.setGeneratingState(false);
    }
  },

  /**
   * 백엔드 /reply 엔드포인트 호출 (일반 모드)
   */
  async callReplyEndpoint(ticketId) {

    // ApiService 확인
    if (!window.ApiService) {
      throw new Error('ApiService가 로드되지 않았습니다');
    }

    const url = window.ApiService.getBackendUrl('reply');
    const headers = window.ApiService.getHeaders();

    const requestBody = {
      ticket_id: ticketId,
      stream_response: false  // 일반 모드에서는 스트리밍 비활성화
    };

    // 새로운 캐시 시스템에서 티켓 컨텍스트 가져오기
    if (window.TicketCacheManager) {
      try {
        window.TicketCacheManager.initialize(ticketId);
        const context = window.TicketCacheManager.createChatContext();
        if (context) {
          requestBody.ticket_context = context;
        }
      } catch (e) {
        console.warn('⚠️ 캐시 매니저 컨텍스트 생성 실패:', e);
      }
    }

    const response = await fetch(url, {
      method: 'POST',
      headers: headers,
      body: JSON.stringify(requestBody)
    });

    if (!response.ok) {
      let errorMessage = `HTTP ${response.status}: ${response.statusText}`;

      // 백엔드 에러 메시지 추출 시도
      try {
        const errorData = await response.json();
        if (errorData.detail) {
          errorMessage = errorData.detail;
        }
      } catch (e) {
        // JSON 파싱 실패 시 기본 메시지 사용
      }

      throw new Error(errorMessage);
    }

    // JSON 응답 처리 (새로운 ReplyResponse 구조)
    const result = await response.json();

    // 백엔드 응답 구조: ReplyResponse 모델
    this.currentResponse = result.content || '';

    // 메타데이터 정보 추출
    const processingTime = result.processing_time_ms || 0;

    this.setGeneratingState(false);

    // 응답을 미리보기 영역에 표시
    if (this.currentResponse.trim()) {
      this.displayResponse(this.currentResponse);
      this.showStatus(`추천답변이 생성되었습니다 (${processingTime}ms)`, 'success');

      // 처리 시간 정보는 사용자 상태 메시지에만 표시
    } else {
      this.showStatus('응답을 생성할 수 없습니다', 'error');
    }
  },

  /**
   * 백엔드 /reply 엔드포인트 호출 (스트리밍 모드)
   */
  async callReplyEndpointStreaming(ticketId) {
    this._validateApiService();
    const requestBody = this._buildStreamingRequestBody(ticketId);
    const response = await this._sendStreamingRequest(requestBody);
    await this._processStreamingResponse(response);
  },

  /**
   * ApiService 유효성 검사
   */
  _validateApiService() {
    if (!window.ApiService) {
      throw new Error('ApiService가 로드되지 않았습니다');
    }
  },

  /**
   * 스트리밍 요청 본문 구성
   */
  _buildStreamingRequestBody(ticketId) {
    const requestBody = {
      ticket_id: ticketId,
      stream_response: true
    };

    // 새로운 캐시 시스템에서 티켓 컨텍스트 가져오기
    if (window.TicketCacheManager) {
      try {
        window.TicketCacheManager.initialize(ticketId);
        const context = window.TicketCacheManager.createChatContext();
        if (context) {
          requestBody.ticket_context = context;
        }
      } catch (e) {
        console.warn('⚠️ 캐시 매니저 컨텍스트 생성 실패:', e);
      }
    }

    return requestBody;
  },

  /**
   * 스트리밍 요청 전송
   */
  async _sendStreamingRequest(requestBody) {
    const url = window.ApiService.getBackendUrl('reply');
    const headers = window.ApiService.getHeaders();

    const response = await fetch(url, {
      method: 'POST',
      headers: headers,
      body: JSON.stringify(requestBody)
    });

    if (!response.ok) {
      const errorMessage = await this._extractErrorMessage(response);
      throw new Error(errorMessage);
    }

    return response;
  },

  /**
   * 응답에서 에러 메시지 추출
   */
  async _extractErrorMessage(response) {
    let errorMessage = `HTTP ${response.status}: ${response.statusText}`;

    try {
      const errorData = await response.json();
      if (errorData.detail) {
        errorMessage = errorData.detail;
      }
    } catch (e) {
      // JSON 파싱 실패 시 기본 메시지 사용
    }

    return errorMessage;
  },

  /**
   * 스트리밍 응답 처리
   */
  async _processStreamingResponse(response) {
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    this.currentResponse = '';

    this._initializeStreamingUI();

    try {
      await this._readStreamingData(reader, decoder);
    } finally {
      this._finalizeStreaming(reader);
    }
  },

  /**
   * 스트리밍 UI 초기화
   */
  _initializeStreamingUI() {
    const previewTextarea = document.getElementById('previewTextarea');
    const previewSection = document.getElementById('previewSection');

    if (previewTextarea) {
      previewTextarea.value = '';
      previewTextarea.readOnly = true;
      previewTextarea.classList.add('fade-in');
    }

    if (previewSection) {
      previewSection.classList.add('has-content');
    }

    this.setActionButtonsState(true);
    this.showStatus('실시간으로 답변을 생성하고 있습니다...', 'info');
  },

  /**
   * 스트리밍 데이터 읽기
   */
  async _readStreamingData(reader, decoder) {
    let done = false;
    while (!done) {
      const result = await reader.read();
      done = result.done;
      const { value } = result;

      if (done) {
        break;
      }

      const chunk = decoder.decode(value, { stream: true });
      const lines = chunk.split('\n');

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const completed = this._processStreamingLine(line);
          if (completed) {
            return;
          }
        }
      }
    }
  },

  /**
   * 스트리밍 라인 처리
   */
  _processStreamingLine(line) {
    const data = line.slice(6).trim();

    if (data === '[DONE]') {
      return this._handleStreamingComplete();
    }

    try {
      const parsed = JSON.parse(data);
      if (parsed.type === 'content' && parsed.content) {
        this._updateStreamingContent(parsed.content);
      }
    } catch (e) {
      // JSON 파싱 실패는 무시 (디버그 메시지 등)
    }

    return false;
  },

  /**
   * 스트리밍 완료 처리
   */
  _handleStreamingComplete() {
    this.setGeneratingState(false);
    this.showStatus('스트리밍 답변 생성이 완료되었습니다', 'success');

    const previewTextarea = document.getElementById('previewTextarea');
    if (previewTextarea) {
      previewTextarea.readOnly = false;
    }

    return true;
  },

  /**
   * 스트리밍 콘텐츠 업데이트
   */
  _updateStreamingContent(content) {
    this.currentResponse += content;

    const previewTextarea = document.getElementById('previewTextarea');
    if (previewTextarea) {
      previewTextarea.value = this.currentResponse;
      this.updateWordCount();
      previewTextarea.scrollTop = previewTextarea.scrollHeight;
    }
  },

  /**
   * 스트리밍 마무리
   */
  _finalizeStreaming(reader) {
    reader.releaseLock();
    this.setGeneratingState(false);

    const previewTextarea = document.getElementById('previewTextarea');
    if (previewTextarea) {
      previewTextarea.readOnly = false;
    }

    if (this.currentResponse.trim()) {
      this.showStatus('스트리밍 답변 생성이 완료되었습니다', 'success');
    } else {
      this.showStatus('스트리밍 응답을 받지 못했습니다', 'error');
    }
  },

  /**
   * 응답을 미리보기 영역에 표시
   */
  displayResponse(text) {
    const previewTextarea = document.getElementById('previewTextarea');
    const previewSection = document.getElementById('previewSection');

    if (previewTextarea) {
      previewTextarea.value = text;
      previewTextarea.readOnly = false;  // 답변 생성 후에도 편집 가능
      previewTextarea.classList.add('fade-in');
      this.updateWordCount();
    }

    if (previewSection) {
      previewSection.classList.add('has-content');
    }

    // 액션 버튼들 활성화
    this.setActionButtonsState(true);

  },

  /**
   * 편집 모드 토글
   */
  toggleEditMode() {
    const previewTextarea = document.getElementById('previewTextarea');
    const editButton = document.getElementById('editButton');

    if (!previewTextarea || !editButton) return;

    this.isEditing = !this.isEditing;

    if (this.isEditing) {
      previewTextarea.readOnly = false;
      previewTextarea.focus();
      editButton.textContent = '✅ 완료';
      editButton.classList.remove('secondary');
      editButton.classList.add('primary');
      this.showStatus('편집 모드가 활성화되었습니다', 'info');
    } else {
      previewTextarea.readOnly = true;
      editButton.textContent = '✏️ 편집';
      editButton.classList.remove('primary');
      editButton.classList.add('secondary');
      // 편집된 내용을 currentResponse에 저장
      this.currentResponse = previewTextarea.value;
      this.showStatus('편집이 완료되었습니다', 'success');
    }
  },

  /**
   * Freshdesk 에디터에 텍스트 삽입
   */
  async insertToEditor(replaceAll = false) {
    const previewTextarea = document.getElementById('previewTextarea');
    if (!previewTextarea || !previewTextarea.value.trim()) {
      this.showStatus('삽입할 내용이 없습니다', 'error');
      return;
    }

    const text = previewTextarea.value.trim();

    try {

      // FDK setValue 사용 (replaceAll 파라미터 전달)
      const inserted = await this.tryFdkInsert(text, replaceAll);

      if (!inserted) {
        throw new Error('FDK setValue 실패');
      }

    } catch (error) {
      console.error('❌ 에디터 삽입 실패:', error);
      this.showStatus('에디터 삽입 실패: ' + error.message, 'error');
    }
  },

  /**
   * FDK 인터페이스를 통한 삽입 시도
   */
  async tryFdkInsert(text, replaceAll = false) {
    try {
      if (!this.client || !this.client.interface) {
        console.error('❌ FDK client가 없습니다');
        return false;
      }

      // 단순 줄바꿈을 HTML <br> 태그로 변환
      const htmlText = text.replace(/\n/g, '<br>');

      // setValue 메서드 사용 (replace 파라미터로 삽입 방식 제어)
      try {
        await this.client.interface.trigger('setValue', {
          id: 'editor',
          text: htmlText,
          replace: replaceAll  // true: 전체 교체, false: 커서 위치 삽입
        });

        if (replaceAll) {
          this.showStatus('에디터 내용이 교체되었습니다', 'success');
        } else {
          this.showStatus('커서 위치에 답변이 삽입되었습니다', 'success');
        }

        // 성공적으로 삽입된 경우 모달창 닫기 시도
        this.closeModal();

        return true;

      } catch (setValueError) {
        console.error('❌ FDK setValue 실패:', setValueError);

        // Reply 에디터가 닫혀있을 경우, 열면서 삽입 시도
        if (setValueError.message && setValueError.message.includes('closed')) {
          try {
            await this.client.interface.trigger('click', {
              id: 'reply',
              text: htmlText
            });

            this.showStatus('Reply 에디터에 답변이 추가되었습니다', 'success');

            // 성공적으로 삽입된 경우 모달창 닫기 시도
            this.closeModal();

            return true;

          } catch (clickError) {
            console.error('❌ FDK click reply 실패:', clickError);
          }
        }
      }

      throw new Error('에디터 삽입 실패');

    } catch (error) {
      console.error('❌ FDK 에디터 삽입 실패:', error);
      return false;
    }
  },


  /**
   * 응답 지우기
   */
  clearResponse() {
    const previewTextarea = document.getElementById('previewTextarea');
    const previewSection = document.getElementById('previewSection');

    if (previewTextarea) {
      previewTextarea.value = '';
      previewTextarea.readOnly = false;  // 기본적으로 편집 가능
    }

    if (previewSection) {
      previewSection.classList.remove('has-content');
    }

    this.currentResponse = '';
    this.isEditing = false;
    this.updateWordCount();
    this.setActionButtonsState(false);

    // 편집 버튼 초기화
    const editButton = document.getElementById('editButton');
    if (editButton) {
      editButton.textContent = '✏️ 편집';
      editButton.classList.remove('primary');
      editButton.classList.add('secondary');
    }

    this.showStatus('내용이 지워졌습니다', 'info');
  },

  /**
   * 글자 수 업데이트
   */
  updateWordCount() {
    const previewTextarea = document.getElementById('previewTextarea');
    const wordCount = document.getElementById('wordCount');

    if (previewTextarea && wordCount) {
      const count = previewTextarea.value.length;
      wordCount.textContent = `${count}자`;

      // 글자 수에 따른 색상 변경
      if (count === 0) {
        wordCount.style.color = '#64748b';
      } else if (count < 100) {
        wordCount.style.color = '#059669';
      } else if (count < 500) {
        wordCount.style.color = '#2563eb';
      } else {
        wordCount.style.color = '#dc2626';
      }
    }
  },

  /**
   * 텍스트 영역 포커스 이벤트
   */
  onTextareaFocus() {
    // 포커스 시 특별한 처리는 없음
  },

  /**
   * 텍스트 영역 블러 이벤트
   */
  onTextareaBlur() {
    // 블러 시 특별한 처리는 없음
  },

  /**
   * 생성 상태 설정
   */
  setGeneratingState(isGenerating) {
    this.isGenerating = isGenerating;

    const generateButton = document.getElementById('generateButton');
    const generateButtonText = document.getElementById('generateButtonText');
    const loadingSpinner = document.getElementById('loadingSpinner');

    if (generateButton) {
      generateButton.disabled = isGenerating;
    }

    if (generateButtonText) {
      generateButtonText.textContent = isGenerating ? '생성 중...' : '추천답변 생성';
    }

    if (loadingSpinner) {
      loadingSpinner.classList.toggle('hidden', !isGenerating);
    }

    // 생성 중일 때는 액션 버튼들 비활성화
    if (isGenerating) {
      this.setActionButtonsState(false);
    }

    // 디버그 정보 업데이트
    this.updateDebugInfo();
  },

  /**
   * 액션 버튼들 상태 설정
   */
  setActionButtonsState(enabled) {
    const buttons = ['insertAtCursorButton', 'replaceContentButton', 'clearButton'];

    buttons.forEach(buttonId => {
      const button = document.getElementById(buttonId);
      if (button) {
        button.disabled = !enabled;
      }
    });
  },

  /**
   * 상태 메시지 표시 (비활성화됨)
   */
  showStatus() {
    // 상태 메시지 표시를 비활성화하고 콘솔에만 로그
    // 상태 메시지 로그
    return;
  },

  /**
   * 디버그 정보 업데이트 (제거됨)
   */
  updateDebugInfo() {
    // 디버그 정보 제거됨
  },

  /**
   * 모달창 닫기
   */
  closeModal() {
    try {
      // FDK instance.close() 메서드로 모달 닫기
      if (this.client && this.client.instance) {
        this.client.instance.close()
          .catch(err => {
            console.warn('⚠️ 모달 닫기 실패:', err);
          });
      } else {
        console.warn('⚠️ FDK client.instance가 없어 모달을 닫을 수 없습니다');
      }
    } catch (error) {
      console.error('❌ 모달 닫기 중 오류:', error);
    }
  }

};

// 전역 client 변수 선언 (FDK에서 사용)
// eslint-disable-next-line no-unused-vars
let client = null;

// DOM이 로드된 후 FDK 초기화 시도
document.addEventListener('DOMContentLoaded', function () {
  // FDK app 객체가 있는지 확인
  if (typeof app !== 'undefined') {
    app.initialized()
      .then(c => {
        client = c;

        // Reply Editor 초기화
        window.ReplyEditor.init(c);
      })
      .catch(err => {
        console.error("❌ FDK 초기화 실패:", err);
        // FDK 없이도 기본 기능 작동하도록 초기화
        window.ReplyEditor.init(null);
      });
  } else {
    console.error('❌ FDK app 객체가 없습니다 - 개발 환경에서 실행 중');
    // FDK 없이도 기본 기능 작동하도록 초기화
    window.ReplyEditor.init(null);
  }
});

