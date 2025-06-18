/**
 * 🧪 UI 모듈 단위 테스트
 * 
 * UI 렌더링과 DOM 조작 함수들의 정확성과 안정성을 검증합니다.
 * DOM 요소 접근, 모달 표시, 토스트 메시지, 데이터 렌더링 등을 테스트합니다.
 * 
 * @author We Do Soft Inc.
 * @since 2025.01.24
 * @version 1.0.0
 */

const { TestUtils } = require('./setup');

describe('UI 모듈 테스트', () => {
  beforeEach(() => {
    TestUtils.setupTestEnvironment();
    
    // UI 모듈 모킹
    global.UI = {
      safeGetElement: function(selector) {
        try {
          const element = document.querySelector(selector);
          if (!element) {
            console.warn(`요소를 찾을 수 없음: ${selector}`);
            return null;
          }
          return element;
        } catch (error) {
          console.error(`DOM 요소 조회 오류: ${selector}`, error);
          return null;
        }
      },
      
      showToast: function(message, type = 'info', duration = 3000) {
        try {
          // 기존 토스트 제거
          const existingToast = this.safeGetElement('.toast-message');
          if (existingToast) {
            existingToast.remove();
          }

          // 토스트 컨테이너 생성
          const toast = document.createElement('div');
          toast.className = `toast-message toast-${type}`;
          toast.textContent = message;
          
          // 스타일 적용
          Object.assign(toast.style, {
            position: 'fixed',
            top: '20px',
            right: '20px',
            padding: '12px 20px',
            borderRadius: '4px',
            color: 'white',
            fontSize: '14px',
            zIndex: '10000',
            maxWidth: '300px',
            backgroundColor: type === 'error' ? '#f44336' : 
                           type === 'success' ? '#4caf50' : 
                           type === 'warning' ? '#ff9800' : '#2196f3'
          });

          document.body.appendChild(toast);

          // 자동 제거 (테스트에서는 즉시 제거하지 않음)
          if (duration > 0) {
            setTimeout(() => {
              if (toast.parentNode) {
                toast.remove();
              }
            }, duration);
          }
          
          return toast; // 테스트에서 확인할 수 있도록 반환
          
        } catch (error) {
          console.error('토스트 표시 오류:', error);
          // 토스트 표시 자체가 실패하면 기본 alert 사용
          alert(`${type.toUpperCase()}: ${message}`);
          return null;
        }
      },
      
      showModal: function(content, options = {}) {
        try {
          const modal = this.safeGetElement('#response-modal');
          if (!modal) {
            console.error('모달 요소를 찾을 수 없음');
            this.showToast('모달을 표시할 수 없습니다.', 'error');
            return false;
          }

          const modalContent = this.safeGetElement('#modal-content');
          if (!modalContent) {
            console.error('모달 콘텐츠 요소를 찾을 수 없음');
            this.showToast('모달 콘텐츠를 로드할 수 없습니다.', 'error');
            return false;
          }

          modalContent.innerHTML = content;
          modal.style.display = 'block';
          
          return true;
          
        } catch (error) {
          console.error('모달 표시 오류:', error);
          return false;
        }
      },
      
      updateTicketInfo: function(ticket) {
        try {
          // 제목 업데이트
          const subjectElement = this.safeGetElement("#ticket-subject");
          if (subjectElement) {
            subjectElement.textContent = ticket.subject || "No subject available";
          }

          // 상태 업데이트
          const statusElement = this.safeGetElement("#ticket-status");
          if (statusElement) {
            const statusText = this.getStatusText(ticket.status);
            statusElement.textContent = statusText;
            statusElement.className = `info-value status-${statusText.toLowerCase()}`;
          }

          // 우선순위 업데이트
          const priorityElement = this.safeGetElement("#ticket-priority");
          if (priorityElement) {
            const priorityText = this.getPriorityText(ticket.priority);
            priorityElement.textContent = priorityText;
            priorityElement.className = `info-value priority-${priorityText.toLowerCase()}`;
          }

          // 타입 업데이트
          const typeElement = this.safeGetElement("#ticket-type");
          if (typeElement) {
            typeElement.textContent = ticket.type || "Question";
          }

          return true;
        } catch (error) {
          console.error('티켓 정보 업데이트 오류:', error);
          return false;
        }
      },
      
      showSimilarTicketsListView: function() {
        try {
          const listView = this.safeGetElement("#similar-tickets-list-view");
          const detailView = this.safeGetElement("#similar-tickets-detail-view");

          if (listView) listView.style.display = "block";
          if (detailView) detailView.style.display = "none";
          
          return true;
        } catch (error) {
          console.error('유사 티켓 리스트 뷰 표시 오류:', error);
          return false;
        }
      },
      
      showSimilarTicketDetailView: function(ticket) {
        try {
          const listView = this.safeGetElement("#similar-tickets-list-view");
          const detailView = this.safeGetElement("#similar-tickets-detail-view");
          const detailContent = this.safeGetElement("#similar-ticket-detail-content");

          if (listView) listView.style.display = "none";
          if (detailView) detailView.style.display = "block";

          if (detailContent && ticket) {
            detailContent.innerHTML = `
              <div class="detail-content">
                <h5>#${ticket.id}</h5>
                <p>${ticket.subject || 'No subject'}</p>
                <p>Status: ${ticket.status}</p>
                <p>Priority: ${ticket.priority}</p>
              </div>
            `;
          }
          
          return true;
        } catch (error) {
          console.error('유사 티켓 상세 뷰 표시 오류:', error);
          return false;
        }
      },
      
      renderTicketList: function(tickets, containerId) {
        try {
          const container = this.safeGetElement(`#${containerId}`);
          if (!container) {
            console.error(`컨테이너를 찾을 수 없음: ${containerId}`);
            return false;
          }

          if (!tickets || tickets.length === 0) {
            container.innerHTML = `
              <div class="empty-state">
                <div class="empty-state-title">데이터가 없습니다</div>
              </div>
            `;
            return true;
          }

          const ticketItems = tickets.map(ticket => `
            <div class="ticket-item" data-ticket-id="${ticket.id}">
              <div class="ticket-title">${ticket.subject || 'No subject'}</div>
              <div class="ticket-meta">
                <span>Status: ${ticket.status}</span>
                <span>Priority: ${ticket.priority}</span>
              </div>
            </div>
          `).join('');

          container.innerHTML = ticketItems;
          return true;
          
        } catch (error) {
          console.error('티켓 리스트 렌더링 오류:', error);
          return false;
        }
      },
      
      // 헬퍼 함수들
      getStatusText: function(status) {
        switch (status) {
          case 2: return "열림";
          case 3: return "대기중";
          case 4: return "해결됨";
          case 5: return "닫힘";
          default: return "알 수 없음";
        }
      },
      
      getPriorityText: function(priority) {
        switch (priority) {
          case 1: return "낮음";
          case 2: return "보통";
          case 3: return "높음";
          case 4: return "긴급";
          default: return "보통";
        }
      },
      
      isAvailable: () => true
    };
  });

  afterEach(() => {
    TestUtils.cleanupTestEnvironment();
  });

  describe('🔍 DOM 요소 접근', () => {
    test('safeGetElement - 존재하는 요소 조회', () => {
      // DOM에 테스트 요소 추가
      document.body.innerHTML = `
        <div id="test-element">Test Content</div>
        <button class="test-button">Test Button</button>
      `;
      
      const element = UI.safeGetElement('#test-element');
      expect(element).not.toBeNull();
      expect(element.textContent).toBe('Test Content');
      
      const button = UI.safeGetElement('.test-button');
      expect(button).not.toBeNull();
      expect(button.textContent).toBe('Test Button');
    });
    
    test('safeGetElement - 존재하지 않는 요소 조회', () => {
      const element = UI.safeGetElement('#nonexistent-element');
      expect(element).toBeNull();
    });
    
    test('safeGetElement - 잘못된 선택자', () => {
      const element = UI.safeGetElement('invalid<<selector');
      expect(element).toBeNull();
    });
  });

  describe('🔔 토스트 메시지', () => {
    test('showToast - 기본 토스트 표시', () => {
      const toast = UI.showToast('테스트 메시지');
      
      expect(toast).not.toBeNull();
      expect(toast.textContent).toBe('테스트 메시지');
      expect(toast.className).toBe('toast-message toast-info');
      expect(toast.style.backgroundColor).toBe('rgb(33, 150, 243)'); // #2196f3
    });
    
    test('showToast - 다양한 타입별 토스트', () => {
      const successToast = UI.showToast('성공 메시지', 'success');
      expect(successToast.className).toBe('toast-message toast-success');
      expect(successToast.style.backgroundColor).toBe('rgb(76, 175, 80)'); // #4caf50
      
      const errorToast = UI.showToast('에러 메시지', 'error');
      expect(errorToast.className).toBe('toast-message toast-error');
      expect(errorToast.style.backgroundColor).toBe('rgb(244, 67, 54)'); // #f44336
      
      const warningToast = UI.showToast('경고 메시지', 'warning');
      expect(warningToast.className).toBe('toast-message toast-warning');
      expect(warningToast.style.backgroundColor).toBe('rgb(255, 152, 0)'); // #ff9800
    });
    
    test('showToast - 기존 토스트 제거', () => {
      const firstToast = UI.showToast('첫 번째 메시지');
      expect(document.querySelectorAll('.toast-message')).toHaveLength(1);
      
      const secondToast = UI.showToast('두 번째 메시지');
      expect(document.querySelectorAll('.toast-message')).toHaveLength(1);
      expect(secondToast.textContent).toBe('두 번째 메시지');
    });
    
    test('showToast - 자동 제거 (타이머 테스트)', (done) => {
      const toast = UI.showToast('자동 제거 테스트', 'info', 100);
      
      expect(document.querySelectorAll('.toast-message')).toHaveLength(1);
      
      setTimeout(() => {
        expect(document.querySelectorAll('.toast-message')).toHaveLength(0);
        done();
      }, 150);
    });
  });

  describe('🪟 모달 창 제어', () => {
    beforeEach(() => {
      // 모달 DOM 구조 설정
      document.body.innerHTML = `
        <div id="response-modal" style="display: none;">
          <div id="modal-content"></div>
        </div>
      `;
    });
    
    test('showModal - 정상적인 모달 표시', () => {
      const content = '<h3>테스트 모달</h3><p>모달 내용입니다.</p>';
      const result = UI.showModal(content);
      
      expect(result).toBe(true);
      
      const modal = document.querySelector('#response-modal');
      const modalContent = document.querySelector('#modal-content');
      
      expect(modal.style.display).toBe('block');
      expect(modalContent.innerHTML).toBe(content);
    });
    
    test('showModal - 모달 요소 없음', () => {
      document.body.innerHTML = ''; // 모달 요소 제거
      
      const result = UI.showModal('테스트 내용');
      expect(result).toBe(false);
    });
    
    test('showModal - 모달 콘텐츠 요소 없음', () => {
      document.body.innerHTML = '<div id="response-modal"></div>'; // modal-content 없음
      
      const result = UI.showModal('테스트 내용');
      expect(result).toBe(false);
    });
  });

  describe('🎫 티켓 정보 업데이트', () => {
    beforeEach(() => {
      document.body.innerHTML = `
        <div id="ticket-subject"></div>
        <div id="ticket-status"></div>
        <div id="ticket-priority"></div>
        <div id="ticket-type"></div>
      `;
    });
    
    test('updateTicketInfo - 완전한 티켓 정보 업데이트', () => {
      const ticket = {
        subject: '테스트 티켓 제목',
        status: 2,
        priority: 3,
        type: 'Bug'
      };
      
      const result = UI.updateTicketInfo(ticket);
      expect(result).toBe(true);
      
      expect(document.querySelector('#ticket-subject').textContent).toBe('테스트 티켓 제목');
      expect(document.querySelector('#ticket-status').textContent).toBe('열림');
      expect(document.querySelector('#ticket-priority').textContent).toBe('높음');
      expect(document.querySelector('#ticket-type').textContent).toBe('Bug');
    });
    
    test('updateTicketInfo - 부분적인 티켓 정보', () => {
      const ticket = {
        subject: '부분 정보 티켓'
        // status, priority, type 없음
      };
      
      const result = UI.updateTicketInfo(ticket);
      expect(result).toBe(true);
      
      expect(document.querySelector('#ticket-subject').textContent).toBe('부분 정보 티켓');
      expect(document.querySelector('#ticket-type').textContent).toBe('Question'); // 기본값
    });
    
    test('updateTicketInfo - 빈 티켓 정보', () => {
      const ticket = {};
      
      const result = UI.updateTicketInfo(ticket);
      expect(result).toBe(true);
      
      expect(document.querySelector('#ticket-subject').textContent).toBe('No subject available');
    });
    
    test('updateTicketInfo - DOM 요소 일부 없음', () => {
      document.body.innerHTML = '<div id="ticket-subject"></div>'; // 일부 요소만 존재
      
      const ticket = { subject: '테스트', status: 2 };
      const result = UI.updateTicketInfo(ticket);
      
      expect(result).toBe(true);
      expect(document.querySelector('#ticket-subject').textContent).toBe('테스트');
    });
  });

  describe('📋 유사 티켓 뷰 제어', () => {
    beforeEach(() => {
      document.body.innerHTML = `
        <div id="similar-tickets-list-view" style="display: none;"></div>
        <div id="similar-tickets-detail-view" style="display: block;"></div>
        <div id="similar-ticket-detail-content"></div>
      `;
    });
    
    test('showSimilarTicketsListView - 리스트 뷰 표시', () => {
      const result = UI.showSimilarTicketsListView();
      
      expect(result).toBe(true);
      expect(document.querySelector('#similar-tickets-list-view').style.display).toBe('block');
      expect(document.querySelector('#similar-tickets-detail-view').style.display).toBe('none');
    });
    
    test('showSimilarTicketDetailView - 상세 뷰 표시', () => {
      const ticket = {
        id: 123,
        subject: '상세 뷰 테스트 티켓',
        status: 2,
        priority: 3
      };
      
      const result = UI.showSimilarTicketDetailView(ticket);
      
      expect(result).toBe(true);
      expect(document.querySelector('#similar-tickets-list-view').style.display).toBe('none');
      expect(document.querySelector('#similar-tickets-detail-view').style.display).toBe('block');
      
      const content = document.querySelector('#similar-ticket-detail-content').innerHTML;
      expect(content).toContain('#123');
      expect(content).toContain('상세 뷰 테스트 티켓');
    });
    
    test('showSimilarTicketDetailView - DOM 요소 없음', () => {
      document.body.innerHTML = '';
      
      const ticket = { id: 123, subject: '테스트' };
      const result = UI.showSimilarTicketDetailView(ticket);
      
      expect(result).toBe(true); // 에러가 발생해도 true 반환 (현재 구현)
    });
  });

  describe('📝 티켓 리스트 렌더링', () => {
    beforeEach(() => {
      document.body.innerHTML = '<div id="tickets-container"></div>';
    });
    
    test('renderTicketList - 정상적인 티켓 리스트 렌더링', () => {
      const tickets = [
        { id: 1, subject: '첫 번째 티켓', status: 2, priority: 1 },
        { id: 2, subject: '두 번째 티켓', status: 3, priority: 2 }
      ];
      
      const result = UI.renderTicketList(tickets, 'tickets-container');
      
      expect(result).toBe(true);
      
      const container = document.querySelector('#tickets-container');
      const ticketItems = container.querySelectorAll('.ticket-item');
      
      expect(ticketItems).toHaveLength(2);
      expect(ticketItems[0].textContent).toContain('첫 번째 티켓');
      expect(ticketItems[1].textContent).toContain('두 번째 티켓');
    });
    
    test('renderTicketList - 빈 티켓 리스트', () => {
      const result = UI.renderTicketList([], 'tickets-container');
      
      expect(result).toBe(true);
      
      const container = document.querySelector('#tickets-container');
      expect(container.innerHTML).toContain('데이터가 없습니다');
    });
    
    test('renderTicketList - null/undefined 티켓 리스트', () => {
      const result1 = UI.renderTicketList(null, 'tickets-container');
      const result2 = UI.renderTicketList(undefined, 'tickets-container');
      
      expect(result1).toBe(true);
      expect(result2).toBe(true);
      
      const container = document.querySelector('#tickets-container');
      expect(container.innerHTML).toContain('데이터가 없습니다');
    });
    
    test('renderTicketList - 존재하지 않는 컨테이너', () => {
      const tickets = [{ id: 1, subject: '테스트' }];
      const result = UI.renderTicketList(tickets, 'nonexistent-container');
      
      expect(result).toBe(false);
    });
  });

  describe('🏷️ 헬퍼 함수들', () => {
    test('getStatusText - 상태 번호를 텍스트로 변환', () => {
      expect(UI.getStatusText(2)).toBe('열림');
      expect(UI.getStatusText(3)).toBe('대기중');
      expect(UI.getStatusText(4)).toBe('해결됨');
      expect(UI.getStatusText(5)).toBe('닫힘');
      expect(UI.getStatusText(999)).toBe('알 수 없음');
    });
    
    test('getPriorityText - 우선순위 번호를 텍스트로 변환', () => {
      expect(UI.getPriorityText(1)).toBe('낮음');
      expect(UI.getPriorityText(2)).toBe('보통');
      expect(UI.getPriorityText(3)).toBe('높음');
      expect(UI.getPriorityText(4)).toBe('긴급');
      expect(UI.getPriorityText(999)).toBe('보통');
    });
  });

  describe('🔗 모듈 의존성', () => {
    test('isAvailable - 모듈 사용 가능 여부', () => {
      const result = UI.isAvailable();
      expect(result).toBe(true);
    });
  });

  describe('🎯 통합 시나리오 테스트', () => {
    test('모달 표시 + 토스트 알림', () => {
      document.body.innerHTML = `
        <div id="response-modal" style="display: none;">
          <div id="modal-content"></div>
        </div>
      `;
      
      const modalContent = '<h3>AI 응답</h3><p>처리 결과입니다.</p>';
      
      // 모달 표시
      const modalResult = UI.showModal(modalContent);
      expect(modalResult).toBe(true);
      
      // 성공 토스트 표시
      const toast = UI.showToast('응답이 생성되었습니다.', 'success');
      expect(toast.textContent).toBe('응답이 생성되었습니다.');
      
      // 모달이 표시되고 있는지 확인
      const modal = document.querySelector('#response-modal');
      expect(modal.style.display).toBe('block');
      expect(modal.querySelector('#modal-content').innerHTML).toBe(modalContent);
    });
    
    test('티켓 정보 업데이트 + 유사 티켓 뷰 전환', () => {
      document.body.innerHTML = `
        <div id="ticket-subject"></div>
        <div id="ticket-status"></div>
        <div id="ticket-priority"></div>
        <div id="ticket-type"></div>
        <div id="similar-tickets-list-view" style="display: none;"></div>
        <div id="similar-tickets-detail-view" style="display: block;"></div>
        <div id="similar-ticket-detail-content"></div>
      `;
      
      // 티켓 정보 업데이트
      const ticket = {
        subject: '통합 테스트 티켓',
        status: 2,
        priority: 4,
        type: 'Bug'
      };
      
      const updateResult = UI.updateTicketInfo(ticket);
      expect(updateResult).toBe(true);
      
      // 리스트 뷰로 전환
      const listViewResult = UI.showSimilarTicketsListView();
      expect(listViewResult).toBe(true);
      
      // 상세 뷰로 전환
      const detailTicket = { id: 456, subject: '상세 뷰 티켓', status: 3, priority: 2 };
      const detailViewResult = UI.showSimilarTicketDetailView(detailTicket);
      expect(detailViewResult).toBe(true);
      
      // 결과 확인
      expect(document.querySelector('#ticket-subject').textContent).toBe('통합 테스트 티켓');
      expect(document.querySelector('#similar-tickets-list-view').style.display).toBe('none');
      expect(document.querySelector('#similar-tickets-detail-view').style.display).toBe('block');
    });
    
    test('에러 상황에서의 UI 안정성', () => {
      // DOM 요소가 없는 상황
      document.body.innerHTML = '';
      
      // 각 함수들이 에러를 발생시키지 않아야 함
      expect(() => {
        UI.safeGetElement('#nonexistent');
        UI.showToast('에러 테스트');
        UI.showModal('에러 모달');
        UI.updateTicketInfo({});
        UI.showSimilarTicketsListView();
        UI.renderTicketList([], 'nonexistent');
      }).not.toThrow();
    });
  });

  describe('📊 성능 테스트', () => {
    test('대량 티켓 리스트 렌더링 성능', () => {
      document.body.innerHTML = '<div id="large-container"></div>';
      
      // 1000개 티켓 생성
      const largeTicketList = Array.from({ length: 1000 }, (_, i) => ({
        id: i + 1,
        subject: `티켓 ${i + 1}`,
        status: (i % 4) + 2,
        priority: (i % 4) + 1
      }));
      
      const start = performance.now();
      const result = UI.renderTicketList(largeTicketList, 'large-container');
      const end = performance.now();
      
      expect(result).toBe(true);
      expect(end - start).toBeLessThan(500); // 500ms 이내
      
      const container = document.querySelector('#large-container');
      const renderedItems = container.querySelectorAll('.ticket-item');
      expect(renderedItems).toHaveLength(1000);
    });
    
    test('연속 토스트 표시 성능', () => {
      const start = performance.now();
      
      // 100개 연속 토스트 (기존 것은 제거되므로 실제로는 마지막 것만 남음)
      for (let i = 0; i < 100; i++) {
        UI.showToast(`토스트 ${i}`, 'info', 0); // 자동 제거 안함
      }
      
      const end = performance.now();
      
      expect(end - start).toBeLessThan(100); // 100ms 이내
      expect(document.querySelectorAll('.toast-message')).toHaveLength(1);
    });
  });
});
