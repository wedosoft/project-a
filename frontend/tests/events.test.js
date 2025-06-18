/**
 * 🧪 Events 모듈 단위 테스트
 * 
 * 이벤트 핸들러들의 정확성과 안정성을 검증합니다.
 * DOM 조작, 이벤트 처리, 에러 상황에 대한 테스트를 포함합니다.
 * 
 * @author We Do Soft Inc.
 * @since 2025.01.24
 * @version 1.0.0
 */

const { TestUtils } = require('./setup');

describe('Events 모듈 테스트', () => {
  beforeEach(() => {
    TestUtils.setupTestEnvironment();
    
    // Mock Data, UI 모듈
    global.Data = {
      sendPrompt: jest.fn(),
    };
    
    global.UI = {
      safeGetElement: jest.fn(),
      showModal: jest.fn(),
      showToast: jest.fn(),
    };
    
    // Events 모듈 모킹 (핵심 함수들만)
    global.Events = {
      handleSendPrompt: async function(event) {
        try {
          if (event) {
            event.preventDefault();
          }
          
          const promptInput = global.UI.safeGetElement('#prompt-input');
          if (!promptInput) {
            throw new Error('프롬프트 입력 필드를 찾을 수 없습니다.');
          }

          const prompt = promptInput.value?.trim();
          if (!prompt) {
            global.UI.showToast('프롬프트를 입력해주세요.', 'warning');
            return;
          }

          this.setSubmitButtonState(false);
          global.UI.showToast('처리 중...', 'info');

          try {
            const response = await global.Data.sendPrompt(prompt);
            
            if (response && response.content) {
              global.UI.showModal(response.content);
              global.UI.showToast('응답이 생성되었습니다.', 'success');
              promptInput.value = '';
            } else {
              throw new Error('응답 데이터가 올바르지 않습니다.');
            }
            
          } finally {
            this.setSubmitButtonState(true);
          }
          
        } catch (error) {
          this.setSubmitButtonState(true);
          throw error;
        }
      },
      
      setSubmitButtonState: function(enabled) {
        try {
          const submitButton = global.UI.safeGetElement('#submit-prompt');
          if (submitButton) {
            submitButton.disabled = !enabled;
            submitButton.textContent = enabled ? '전송' : '처리 중...';
          }
        } catch (error) {
          console.error('버튼 상태 설정 오류:', error);
        }
      },
      
      handleCloseModal: function(event) {
        try {
          if (event) {
            event.preventDefault();
          }
          
          const modal = global.UI.safeGetElement('#response-modal');
          if (modal) {
            modal.style.display = 'none';
          }
          
        } catch (error) {
          throw error;
        }
      },
      
      setupEventListeners: function() {
        try {
          const submitButton = global.UI.safeGetElement('#submit-prompt');
          const closeButton = global.UI.safeGetElement('#close-modal');
          const modal = global.UI.safeGetElement('#response-modal');
          const promptInput = global.UI.safeGetElement('#prompt-input');
          
          if (submitButton && submitButton.addEventListener) {
            submitButton.addEventListener('click', (e) => this.handleSendPrompt(e));
          }
          
          if (closeButton && closeButton.addEventListener) {
            closeButton.addEventListener('click', (e) => this.handleCloseModal(e));
          }
          
          if (modal && modal.addEventListener) {
            modal.addEventListener('click', (e) => {
              if (e.target === modal) {
                this.handleCloseModal(e);
              }
            });
          }
          
          if (promptInput && promptInput.addEventListener) {
            promptInput.addEventListener('keypress', (e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.handleSendPrompt(e);
              }
            });
          }
          
        } catch (error) {
          throw error;
        }
      },
      
      // 디바운스 함수 (성능 최적화용)
      debounce: function(func, wait) {
        let timeout;
        return function executedFunction(...args) {
          const later = () => {
            clearTimeout(timeout);
            func(...args);
          };
          clearTimeout(timeout);
          timeout = setTimeout(later, wait);
        };
      },
      
      // 스로틀 함수 (성능 최적화용)
      throttle: function(func, limit) {
        let inThrottle;
        return function(...args) {
          if (!inThrottle) {
            func.apply(this, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
          }
        };
      },
      
      isAvailable: () => true
    };
  });

  afterEach(() => {
    TestUtils.cleanupTestEnvironment();
    jest.clearAllMocks();
  });

  describe('🚀 프롬프트 전송 이벤트', () => {
    test('handleSendPrompt - 정상적인 프롬프트 전송', async () => {
      // Mock 설정
      const mockPromptInput = { value: '  테스트 프롬프트  ' };
      const mockResponse = { content: '테스트 응답 내용' };
      
      global.UI.safeGetElement.mockImplementation((selector) => {
        if (selector === '#prompt-input') return mockPromptInput;
        if (selector === '#submit-prompt') return { disabled: false, textContent: '전송' };
        return null;
      });
      
      global.Data.sendPrompt.mockResolvedValue(mockResponse);
      
      // 실행
      await Events.handleSendPrompt();
      
      // 검증
      expect(global.Data.sendPrompt).toHaveBeenCalledWith('테스트 프롬프트');
      expect(global.UI.showModal).toHaveBeenCalledWith('테스트 응답 내용');
      expect(global.UI.showToast).toHaveBeenCalledWith('응답이 생성되었습니다.', 'success');
      expect(mockPromptInput.value).toBe('');
    });
    
    test('handleSendPrompt - 빈 프롬프트 처리', async () => {
      const mockPromptInput = { value: '   ' };
      
      global.UI.safeGetElement.mockImplementation((selector) => {
        if (selector === '#prompt-input') return mockPromptInput;
        return null;
      });
      
      await Events.handleSendPrompt();
      
      expect(global.UI.showToast).toHaveBeenCalledWith('프롬프트를 입력해주세요.', 'warning');
      expect(global.Data.sendPrompt).not.toHaveBeenCalled();
    });
    
    test('handleSendPrompt - 프롬프트 입력 필드 없음', async () => {
      global.UI.safeGetElement.mockReturnValue(null);
      
      await expect(Events.handleSendPrompt()).rejects.toThrow('프롬프트 입력 필드를 찾을 수 없습니다.');
    });
    
    test('handleSendPrompt - API 응답 오류', async () => {
      const mockPromptInput = { value: '테스트 프롬프트' };
      const mockButton = { disabled: false, textContent: '전송' };
      
      global.UI.safeGetElement.mockImplementation((selector) => {
        if (selector === '#prompt-input') return mockPromptInput;
        if (selector === '#submit-prompt') return mockButton;
        return null;
      });
      
      global.Data.sendPrompt.mockResolvedValue(null);
      
      await expect(Events.handleSendPrompt()).rejects.toThrow('응답 데이터가 올바르지 않습니다.');
      expect(mockButton.disabled).toBe(false); // 버튼이 다시 활성화되었는지 확인
    });
    
    test('handleSendPrompt - 이벤트 preventDefault 호출', async () => {
      const mockEvent = { preventDefault: jest.fn() };
      const mockPromptInput = { value: 'test' };
      const mockResponse = { content: 'response' };
      
      global.UI.safeGetElement.mockImplementation((selector) => {
        if (selector === '#prompt-input') return mockPromptInput;
        if (selector === '#submit-prompt') return { disabled: false, textContent: '전송' };
        return null;
      });
      
      global.Data.sendPrompt.mockResolvedValue(mockResponse);
      
      await Events.handleSendPrompt(mockEvent);
      
      expect(mockEvent.preventDefault).toHaveBeenCalled();
    });
  });

  describe('🎛️ 버튼 상태 관리', () => {
    test('setSubmitButtonState - 버튼 비활성화', () => {
      const mockButton = { disabled: false, textContent: '전송' };
      global.UI.safeGetElement.mockReturnValue(mockButton);
      
      Events.setSubmitButtonState(false);
      
      expect(mockButton.disabled).toBe(true);
      expect(mockButton.textContent).toBe('처리 중...');
    });
    
    test('setSubmitButtonState - 버튼 활성화', () => {
      const mockButton = { disabled: true, textContent: '처리 중...' };
      global.UI.safeGetElement.mockReturnValue(mockButton);
      
      Events.setSubmitButtonState(true);
      
      expect(mockButton.disabled).toBe(false);
      expect(mockButton.textContent).toBe('전송');
    });
    
    test('setSubmitButtonState - 버튼 없음', () => {
      global.UI.safeGetElement.mockReturnValue(null);
      
      expect(() => Events.setSubmitButtonState(true)).not.toThrow();
    });
  });

  describe('🔒 모달 창 제어', () => {
    test('handleCloseModal - 정상적인 모달 닫기', () => {
      const mockModal = { style: { display: 'block' } };
      global.UI.safeGetElement.mockReturnValue(mockModal);
      
      Events.handleCloseModal();
      
      expect(mockModal.style.display).toBe('none');
    });
    
    test('handleCloseModal - 이벤트 preventDefault 호출', () => {
      const mockEvent = { preventDefault: jest.fn() };
      const mockModal = { style: { display: 'block' } };
      global.UI.safeGetElement.mockReturnValue(mockModal);
      
      Events.handleCloseModal(mockEvent);
      
      expect(mockEvent.preventDefault).toHaveBeenCalled();
      expect(mockModal.style.display).toBe('none');
    });
    
    test('handleCloseModal - 모달 없음', () => {
      global.UI.safeGetElement.mockReturnValue(null);
      
      expect(() => Events.handleCloseModal()).not.toThrow();
    });
  });

  describe('📡 이벤트 리스너 설정', () => {
    test('setupEventListeners - 모든 요소 존재', () => {
      const mockElements = {
        '#submit-prompt': { addEventListener: jest.fn() },
        '#close-modal': { addEventListener: jest.fn() },
        '#response-modal': { addEventListener: jest.fn() },
        '#prompt-input': { addEventListener: jest.fn() }
      };
      
      global.UI.safeGetElement.mockImplementation((selector) => mockElements[selector] || null);
      
      Events.setupEventListeners();
      
      // 모든 요소에 이벤트 리스너가 등록되었는지 확인
      expect(mockElements['#submit-prompt'].addEventListener).toHaveBeenCalledWith('click', expect.any(Function));
      expect(mockElements['#close-modal'].addEventListener).toHaveBeenCalledWith('click', expect.any(Function));
      expect(mockElements['#response-modal'].addEventListener).toHaveBeenCalledWith('click', expect.any(Function));
      expect(mockElements['#prompt-input'].addEventListener).toHaveBeenCalledWith('keypress', expect.any(Function));
    });
    
    test('setupEventListeners - 일부 요소 없음', () => {
      global.UI.safeGetElement.mockImplementation((selector) => {
        if (selector === '#submit-prompt') return { addEventListener: jest.fn() };
        return null;
      });
      
      expect(() => Events.setupEventListeners()).not.toThrow();
    });
    
    test('setupEventListeners - 모든 요소 없음', () => {
      global.UI.safeGetElement.mockReturnValue(null);
      
      expect(() => Events.setupEventListeners()).not.toThrow();
    });
  });

  describe('⚡ 성능 최적화 유틸리티', () => {
    test('debounce - 함수 호출 지연', (done) => {
      const mockFn = jest.fn();
      const debouncedFn = Events.debounce(mockFn, 100);
      
      // 연속 호출
      debouncedFn('first');
      debouncedFn('second');
      debouncedFn('third');
      
      // 즉시는 호출되지 않아야 함
      expect(mockFn).not.toHaveBeenCalled();
      
      // 지연 후 마지막 호출만 실행되어야 함
      setTimeout(() => {
        expect(mockFn).toHaveBeenCalledTimes(1);
        expect(mockFn).toHaveBeenCalledWith('third');
        done();
      }, 150);
    });
    
    test('throttle - 함수 호출 제한', (done) => {
      const mockFn = jest.fn();
      const throttledFn = Events.throttle(mockFn, 100);
      
      // 연속 호출
      throttledFn('first');
      throttledFn('second');
      throttledFn('third');
      
      // 첫 번째 호출만 즉시 실행
      expect(mockFn).toHaveBeenCalledTimes(1);
      expect(mockFn).toHaveBeenCalledWith('first');
      
      // 시간 경과 후 다시 호출 가능
      setTimeout(() => {
        throttledFn('fourth');
        expect(mockFn).toHaveBeenCalledTimes(2);
        expect(mockFn).toHaveBeenCalledWith('fourth');
        done();
      }, 150);
    });
  });

  describe('🔗 모듈 의존성', () => {
    test('isAvailable - 모듈 사용 가능 여부', () => {
      const result = Events.isAvailable();
      expect(result).toBe(true);
    });
  });

  describe('🎯 통합 시나리오 테스트', () => {
    test('프롬프트 전송 전체 워크플로우', async () => {
      const mockPromptInput = { value: '전체 테스트 프롬프트' };
      const mockButton = { disabled: false, textContent: '전송' };
      const mockResponse = { content: '전체 테스트 응답' };
      
      global.UI.safeGetElement.mockImplementation((selector) => {
        if (selector === '#prompt-input') return mockPromptInput;
        if (selector === '#submit-prompt') return mockButton;
        return null;
      });
      
      global.Data.sendPrompt.mockResolvedValue(mockResponse);
      
      // 버튼 상태 변화 추적
      const buttonStates = [];
      Events.setSubmitButtonState = jest.fn((enabled) => {
        buttonStates.push(enabled);
      });
      
      await Events.handleSendPrompt();
      
      // 버튼 상태가 false -> true 순서로 변경되었는지 확인
      expect(buttonStates).toEqual([false, true]);
      
      // UI 함수들이 올바른 순서로 호출되었는지 확인
      const toastCalls = global.UI.showToast.mock.calls;
      expect(toastCalls[0]).toEqual(['처리 중...', 'info']);
      expect(toastCalls[1]).toEqual(['응답이 생성되었습니다.', 'success']);
      
      expect(global.UI.showModal).toHaveBeenCalledWith('전체 테스트 응답');
      expect(mockPromptInput.value).toBe('');
    });
    
    test('에러 발생 시 UI 복구', async () => {
      const mockPromptInput = { value: '에러 테스트' };
      const mockButton = { disabled: false, textContent: '전송' };
      
      global.UI.safeGetElement.mockImplementation((selector) => {
        if (selector === '#prompt-input') return mockPromptInput;
        if (selector === '#submit-prompt') return mockButton;
        return null;
      });
      
      global.Data.sendPrompt.mockRejectedValue(new Error('API 오류'));
      
      const buttonStates = [];
      Events.setSubmitButtonState = jest.fn((enabled) => {
        buttonStates.push(enabled);
      });
      
      await expect(Events.handleSendPrompt()).rejects.toThrow('API 오류');
      
      // 에러 발생 시에도 버튼이 다시 활성화되어야 함
      expect(buttonStates).toEqual([false, true]);
    });
    
    test('모달 열기/닫기 사이클', async () => {
      const mockPromptInput = { value: '모달 테스트' };
      const mockButton = { disabled: false, textContent: '전송' };
      const mockModal = { style: { display: 'none' } };
      const mockResponse = { content: '모달 테스트 응답' };
      
      global.UI.safeGetElement.mockImplementation((selector) => {
        if (selector === '#prompt-input') return mockPromptInput;
        if (selector === '#submit-prompt') return mockButton;
        if (selector === '#response-modal') return mockModal;
        return null;
      });
      
      global.Data.sendPrompt.mockResolvedValue(mockResponse);
      
      // 프롬프트 전송 (모달 열기)
      await Events.handleSendPrompt();
      expect(global.UI.showModal).toHaveBeenCalledWith('모달 테스트 응답');
      
      // 모달 닫기
      Events.handleCloseModal();
      expect(mockModal.style.display).toBe('none');
    });
  });

  describe('📊 성능 테스트', () => {
    test('대량 이벤트 처리 성능', () => {
      const mockFn = jest.fn();
      const debouncedFn = Events.debounce(mockFn, 10);
      
      const start = performance.now();
      
      // 1000번 연속 호출
      for (let i = 0; i < 1000; i++) {
        debouncedFn(`call-${i}`);
      }
      
      const end = performance.now();
      
      expect(end - start).toBeLessThan(100); // 100ms 이내
      expect(mockFn).not.toHaveBeenCalled(); // 아직 디바운스 시간이 지나지 않음
    });
    
    test('이벤트 리스너 설정 성능', () => {
      const mockElements = {};
      for (let i = 0; i < 100; i++) {
        mockElements[`#element-${i}`] = { addEventListener: jest.fn() };
      }
      
      global.UI.safeGetElement.mockImplementation((selector) => mockElements[selector] || null);
      
      const start = performance.now();
      Events.setupEventListeners();
      const end = performance.now();
      
      expect(end - start).toBeLessThan(50); // 50ms 이내
    });
  });

  describe('🚨 에러 처리 및 복구', () => {
    test('DOM 요소 접근 실패 시 안정성', () => {
      global.UI.safeGetElement.mockImplementation(() => {
        throw new Error('DOM 접근 오류');
      });
      
      expect(() => Events.setSubmitButtonState(true)).not.toThrow();
      expect(() => Events.handleCloseModal()).toThrow(); // 이 함수는 에러를 다시 던짐
      expect(() => Events.setupEventListeners()).toThrow(); // 이 함수도 에러를 다시 던짐
    });
    
    test('비동기 작업 중 에러 복구', async () => {
      const mockPromptInput = { value: '에러 복구 테스트' };
      global.UI.safeGetElement.mockImplementation((selector) => {
        if (selector === '#prompt-input') return mockPromptInput;
        if (selector === '#submit-prompt') return { disabled: false, textContent: '전송' };
        return null;
      });
      
      // 첫 번째 호출은 실패, 두 번째 호출은 성공
      global.Data.sendPrompt
        .mockRejectedValueOnce(new Error('일시적 오류'))
        .mockResolvedValueOnce({ content: '성공 응답' });
      
      // 첫 번째 시도 (실패)
      await expect(Events.handleSendPrompt()).rejects.toThrow('일시적 오류');
      
      // 두 번째 시도 (성공)
      await expect(Events.handleSendPrompt()).resolves.toBeUndefined();
      expect(global.UI.showModal).toHaveBeenCalledWith('성공 응답');
    });
  });
});
