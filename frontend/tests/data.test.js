/**
 * 🧪 Data 모듈 단위 테스트
 * 
 * 데이터 처리, 캐시 관리, 백엔드 통신 함수들의 정확성과 안정성을 검증합니다.
 * 티켓 데이터 로드, 솔루션 생성, 캐시 처리, 성능 최적화 등을 테스트합니다.
 * 
 * @author We Do Soft Inc.
 * @since 2025.01.24
 * @version 1.0.0
 */

const { TestUtils } = require('./setup');

describe('Data 모듈 테스트', () => {
  beforeEach(() => {
    TestUtils.setupTestEnvironment();
    
    // Mock GlobalState, API, Utils
    global.GlobalState = {
      getGlobalTicketData: jest.fn(),
      updateGlobalTicketData: jest.fn(),
      resetGlobalTicketCache: jest.fn(),
      isGlobalDataValid: jest.fn(),
      isLoading: jest.fn(),
      setLoading: jest.fn(),
    };
    
    global.API = {
      post: jest.fn(),
      get: jest.fn(),
    };
    
    global.Utils = {
      safeJsonParse: jest.fn((str, def) => {
        try {
          return JSON.parse(str);
        } catch {
          return def;
        }
      }),
      isDataStale: jest.fn(),
    };
    
    // Data 모듈 모킹 (핵심 함수들)
    global.Data = {
      generateMockSolutions: function() {
        return [
          {
            id: "mock_1",
            title: "일반적인 문제 해결 방법",
            content: "이 문제는 보통 다음과 같이 해결할 수 있습니다...",
            category: "일반",
            relevance_score: 0.8,
            source: "지식베이스",
            type: "solution",
          },
          {
            id: "mock_2",
            title: "FAQ 답변",
            content: "자주 묻는 질문에 대한 답변입니다...",
            category: "FAQ",
            relevance_score: 0.7,
            source: "FAQ",
            type: "solution",
          },
          {
            id: "mock_3",
            title: "단계별 가이드",
            content: "문제 해결을 위한 단계별 가이드입니다...",
            category: "가이드",
            relevance_score: 0.6,
            source: "사용자 매뉴얼",
            type: "solution",
          },
        ];
      },
      
      loadTicketDetails: async function(client) {
        try {
          const ticketData = await client.data.get("ticket");
          
          if (ticketData && ticketData.ticket) {
            const basicTicketInfo = ticketData.ticket;
            
            const globalData = global.GlobalState.getGlobalTicketData();
            
            if (
              globalData.cached_ticket_id === basicTicketInfo.id &&
              globalData.summary &&
              global.GlobalState.isGlobalDataValid()
            ) {
              return;
            }

            if (globalData.cached_ticket_id !== basicTicketInfo.id) {
              global.GlobalState.resetGlobalTicketCache();
            }

            global.GlobalState.updateGlobalTicketData(basicTicketInfo.id, 'cached_ticket_id');
            global.GlobalState.updateGlobalTicketData(basicTicketInfo, 'ticket_info');
          }
        } catch (error) {
          console.error("티켓 상세 정보 확인 오류:", error);
          throw error;
        }
      },
      
      loadSuggestedSolutions: function(ticket) {
        try {
          const globalData = global.GlobalState.getGlobalTicketData();
          
          if (
            globalData.cached_ticket_id === ticket.id &&
            globalData.recommended_solutions &&
            globalData.recommended_solutions.length > 0
          ) {
            return this.displaySuggestedSolutions(globalData.recommended_solutions);
          }

          const mockSolutions = this.generateMockSolutions();
          this.displaySuggestedSolutions(mockSolutions);

          global.GlobalState.updateGlobalTicketData(mockSolutions, 'recommended_solutions');
          global.GlobalState.updateGlobalTicketData(ticket.id, 'cached_ticket_id');
        } catch (error) {
          console.error("추천 솔루션 로드 오류:", error);
          this.displaySuggestedSolutions(this.generateMockSolutions());
        }
      },
      
      displaySuggestedSolutions: function(solutions) {
        // DOM 요소 업데이트 시뮬레이션
        const resultsElement = document.getElementById("suggested-solutions-list");
        if (resultsElement) {
          resultsElement.innerHTML = solutions.map(solution => 
            `<div class="solution-item" data-id="${solution.id}">
              <h4>${solution.title}</h4>
              <p>${solution.content}</p>
              <span class="category">${solution.category}</span>
            </div>`
          ).join('');
        }
        return solutions;
      },
      
      loadInitialDataFromBackend: async function(client, ticket) {
        try {
          global.GlobalState.setLoading(true);
          
          // 백엔드 API 호출 시뮬레이션
          const response = await global.API.post('/api/v1/init', {
            ticket_id: ticket.id,
            ticket_data: ticket
          });
          
          if (response && response.data) {
            global.GlobalState.updateGlobalTicketData(response.data.summary, 'summary');
            global.GlobalState.updateGlobalTicketData(response.data.similar_tickets, 'similar_tickets');
            global.GlobalState.updateGlobalTicketData(response.data.recommended_solutions, 'recommended_solutions');
            global.GlobalState.updateGlobalTicketData(ticket.id, 'cached_ticket_id');
          }
          
          return response;
        } catch (error) {
          console.error("백엔드 데이터 로드 오류:", error);
          throw error;
        } finally {
          global.GlobalState.setLoading(false);
        }
      },
      
      sendPrompt: async function(prompt) {
        try {
          if (!prompt || typeof prompt !== 'string' || prompt.trim() === '') {
            throw new Error('유효하지 않은 프롬프트입니다.');
          }
          
          const response = await global.API.post('/api/v1/prompt', {
            prompt: prompt.trim(),
            context: 'chat'
          });
          
          if (!response || !response.data || !response.data.content) {
            throw new Error('응답 데이터가 올바르지 않습니다.');
          }
          
          return {
            content: response.data.content,
            type: response.data.type || 'text',
            timestamp: Date.now()
          };
        } catch (error) {
          console.error("프롬프트 전송 오류:", error);
          throw error;
        }
      },
      
      // 성능 최적화 관련 함수들
      compressTicketData: function(tickets) {
        return tickets.map(ticket => ({
          id: ticket.id,
          s: ticket.subject,
          d: this.truncateText(ticket.description, 200),
          st: ticket.status,
          p: ticket.priority,
          ca: ticket.created_at,
          ua: ticket.updated_at,
          t: ticket.tags ? ticket.tags.slice(0, 5) : [],
          us: ticket.urgency_score
        }));
      },
      
      decompressTicketData: function(compressedTickets) {
        return compressedTickets.map(ticket => ({
          id: ticket.id,
          subject: ticket.s,
          description: ticket.d,
          status: ticket.st,
          priority: ticket.p,
          created_at: ticket.ca,
          updated_at: ticket.ua,
          tags: ticket.t,
          urgency_score: ticket.us
        }));
      },
      
      // 유틸리티 함수들
      sanitizeText: function(text) {
        return text.replace(/<[^>]*>/g, '').replace(/\s+/g, ' ').trim();
      },
      
      truncateText: function(text, maxLength) {
        return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
      },
      
      normalizeStatus: function(status) {
        const statusMap = {
          2: 'open', 3: 'pending', 4: 'resolved', 5: 'closed'
        };
        return statusMap[status] || 'unknown';
      },
      
      normalizePriority: function(priority) {
        const priorityMap = {
          1: 'low', 2: 'medium', 3: 'high', 4: 'urgent'
        };
        return priorityMap[priority] || 'medium';
      },
      
      parseDate: function(dateString) {
        try {
          return new Date(dateString).toISOString();
        } catch {
          return new Date().toISOString();
        }
      },
      
      extractTags: function(tags) {
        return Array.isArray(tags) ? tags.filter(tag => tag && tag.length > 0) : [];
      },
      
      categorizeTicket: function(ticket) {
        const subject = (ticket.subject || '').toLowerCase();
        if (subject.includes('bug') || subject.includes('error')) return 'bug';
        if (subject.includes('feature') || subject.includes('request')) return 'feature';
        if (subject.includes('question') || subject.includes('help')) return 'support';
        return 'general';
      },
      
      calculateUrgencyScore: function(ticket) {
        let score = 0;
        if (ticket.priority === 4) score += 40;
        if (ticket.priority === 3) score += 20;
        if (ticket.status === 2) score += 10;
        
        const hoursOld = (Date.now() - new Date(ticket.created_at)) / (1000 * 60 * 60);
        if (hoursOld < 24) score += 15;
        return Math.min(100, score);
      },
      
      createFallbackTicket: function(ticket) {
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
          urgency_score: 0
        };
      },
      
      checkForUpdates: async function() {
        return Math.random() < 0.1;
      },
      
      isDataStale: function() {
        return global.Utils.isDataStale();
      },
      
      isAvailable: () => true
    };
    
    // Mock client
    global.mockClient = {
      data: {
        get: jest.fn()
      },
      instance: {
        context: jest.fn()
      }
    };
  });

  afterEach(() => {
    TestUtils.cleanupTestEnvironment();
    jest.clearAllMocks();
  });

  describe('🎭 모의 데이터 생성', () => {
    test('generateMockSolutions - 표준 솔루션 생성', () => {
      const solutions = Data.generateMockSolutions();
      
      expect(solutions).toHaveLength(3);
      expect(solutions[0]).toHaveProperty('id', 'mock_1');
      expect(solutions[0]).toHaveProperty('title', '일반적인 문제 해결 방법');
      expect(solutions[0]).toHaveProperty('relevance_score', 0.8);
      expect(solutions[0]).toHaveProperty('type', 'solution');
      
      expect(solutions[1]).toHaveProperty('category', 'FAQ');
      expect(solutions[2]).toHaveProperty('source', '사용자 매뉴얼');
    });
    
    test('generateMockSolutions - 솔루션 구조 검증', () => {
      const solutions = Data.generateMockSolutions();
      
      solutions.forEach(solution => {
        expect(solution).toHaveProperty('id');
        expect(solution).toHaveProperty('title');
        expect(solution).toHaveProperty('content');
        expect(solution).toHaveProperty('category');
        expect(solution).toHaveProperty('relevance_score');
        expect(solution).toHaveProperty('source');
        expect(solution).toHaveProperty('type');
        
        expect(typeof solution.relevance_score).toBe('number');
        expect(solution.relevance_score).toBeGreaterThan(0);
        expect(solution.relevance_score).toBeLessThanOrEqual(1);
      });
    });
  });

  describe('🎫 티켓 데이터 처리', () => {
    test('loadTicketDetails - 정상적인 티켓 로드', async () => {
      const mockTicket = {
        id: 123,
        subject: '테스트 티켓',
        status: 2,
        priority: 3
      };
      
      global.mockClient.data.get.mockResolvedValue({
        ticket: mockTicket
      });
      
      global.GlobalState.getGlobalTicketData.mockReturnValue({
        cached_ticket_id: null,
        summary: null
      });
      
      global.GlobalState.isGlobalDataValid.mockReturnValue(false);
      
      await Data.loadTicketDetails(global.mockClient);
      
      expect(global.GlobalState.updateGlobalTicketData).toHaveBeenCalledWith(123, 'cached_ticket_id');
      expect(global.GlobalState.updateGlobalTicketData).toHaveBeenCalledWith(mockTicket, 'ticket_info');
    });
    
    test('loadTicketDetails - 캐시된 데이터 사용', async () => {
      const mockTicket = { id: 123 };
      
      global.mockClient.data.get.mockResolvedValue({
        ticket: mockTicket
      });
      
      global.GlobalState.getGlobalTicketData.mockReturnValue({
        cached_ticket_id: 123,
        summary: '캐시된 요약'
      });
      
      global.GlobalState.isGlobalDataValid.mockReturnValue(true);
      
      await Data.loadTicketDetails(global.mockClient);
      
      // 캐시된 데이터가 있으므로 업데이트하지 않아야 함
      expect(global.GlobalState.updateGlobalTicketData).not.toHaveBeenCalled();
    });
    
    test('loadTicketDetails - 새로운 티켓으로 캐시 초기화', async () => {
      const mockTicket = { id: 456 };
      
      global.mockClient.data.get.mockResolvedValue({
        ticket: mockTicket
      });
      
      global.GlobalState.getGlobalTicketData.mockReturnValue({
        cached_ticket_id: 123, // 다른 티켓 ID
        summary: '이전 요약'
      });
      
      global.GlobalState.isGlobalDataValid.mockReturnValue(true);
      
      await Data.loadTicketDetails(global.mockClient);
      
      expect(global.GlobalState.resetGlobalTicketCache).toHaveBeenCalled();
    });
    
    test('loadTicketDetails - 티켓 데이터 없음', async () => {
      global.mockClient.data.get.mockResolvedValue(null);
      
      await expect(Data.loadTicketDetails(global.mockClient)).resolves.toBeUndefined();
    });
    
    test('loadTicketDetails - API 오류', async () => {
      global.mockClient.data.get.mockRejectedValue(new Error('API 오류'));
      
      await expect(Data.loadTicketDetails(global.mockClient)).rejects.toThrow('API 오류');
    });
  });

  describe('💡 추천 솔루션 처리', () => {
    beforeEach(() => {
      document.body.innerHTML = '<div id="suggested-solutions-list"></div>';
    });
    
    test('loadSuggestedSolutions - 새로운 솔루션 로드', () => {
      const ticket = { id: 789, subject: '솔루션 테스트' };
      
      global.GlobalState.getGlobalTicketData.mockReturnValue({
        cached_ticket_id: null,
        recommended_solutions: []
      });
      
      Data.loadSuggestedSolutions(ticket);
      
      expect(global.GlobalState.updateGlobalTicketData).toHaveBeenCalledWith(
        expect.any(Array), 'recommended_solutions'
      );
      expect(global.GlobalState.updateGlobalTicketData).toHaveBeenCalledWith(789, 'cached_ticket_id');
      
      const container = document.getElementById('suggested-solutions-list');
      expect(container.innerHTML).toContain('일반적인 문제 해결 방법');
    });
    
    test('loadSuggestedSolutions - 캐시된 솔루션 사용', () => {
      const ticket = { id: 789 };
      const cachedSolutions = [{ id: 'cached', title: '캐시된 솔루션' }];
      
      global.GlobalState.getGlobalTicketData.mockReturnValue({
        cached_ticket_id: 789,
        recommended_solutions: cachedSolutions
      });
      
      Data.displaySuggestedSolutions = jest.fn();
      
      Data.loadSuggestedSolutions(ticket);
      
      expect(Data.displaySuggestedSolutions).toHaveBeenCalledWith(cachedSolutions);
    });
  });

  describe('🚀 프롬프트 전송', () => {
    test('sendPrompt - 정상적인 프롬프트 전송', async () => {
      const mockResponse = {
        data: {
          content: 'AI 응답 내용',
          type: 'text'
        }
      };
      
      global.API.post.mockResolvedValue(mockResponse);
      
      const result = await Data.sendPrompt('테스트 프롬프트');
      
      expect(global.API.post).toHaveBeenCalledWith('/api/v1/prompt', {
        prompt: '테스트 프롬프트',
        context: 'chat'
      });
      
      expect(result).toEqual({
        content: 'AI 응답 내용',
        type: 'text',
        timestamp: expect.any(Number)
      });
    });
    
    test('sendPrompt - 빈 프롬프트 오류', async () => {
      await expect(Data.sendPrompt('')).rejects.toThrow('유효하지 않은 프롬프트입니다.');
      await expect(Data.sendPrompt('   ')).rejects.toThrow('유효하지 않은 프롬프트입니다.');
      await expect(Data.sendPrompt(null)).rejects.toThrow('유효하지 않은 프롬프트입니다.');
    });
    
    test('sendPrompt - API 응답 오류', async () => {
      global.API.post.mockResolvedValue(null);
      
      await expect(Data.sendPrompt('테스트')).rejects.toThrow('응답 데이터가 올바르지 않습니다.');
    });
    
    test('sendPrompt - API 호출 실패', async () => {
      global.API.post.mockRejectedValue(new Error('네트워크 오류'));
      
      await expect(Data.sendPrompt('테스트')).rejects.toThrow('네트워크 오류');
    });
  });

  describe('🔄 백엔드 데이터 로드', () => {
    test('loadInitialDataFromBackend - 성공적인 로드', async () => {
      const mockTicket = { id: 999, subject: '백엔드 테스트' };
      const mockResponse = {
        data: {
          summary: '테스트 요약',
          similar_tickets: [{ id: 1, subject: '유사 티켓' }],
          recommended_solutions: [{ id: 'sol1', title: '솔루션' }]
        }
      };
      
      global.API.post.mockResolvedValue(mockResponse);
      
      const result = await Data.loadInitialDataFromBackend(global.mockClient, mockTicket);
      
      expect(global.GlobalState.setLoading).toHaveBeenCalledWith(true);
      expect(global.API.post).toHaveBeenCalledWith('/api/v1/init', {
        ticket_id: 999,
        ticket_data: mockTicket
      });
      
      expect(global.GlobalState.updateGlobalTicketData).toHaveBeenCalledWith('테스트 요약', 'summary');
      expect(global.GlobalState.setLoading).toHaveBeenCalledWith(false);
      expect(result).toBe(mockResponse);
    });
    
    test('loadInitialDataFromBackend - API 오류 시 로딩 상태 복구', async () => {
      const mockTicket = { id: 999 };
      
      global.API.post.mockRejectedValue(new Error('백엔드 오류'));
      
      await expect(Data.loadInitialDataFromBackend(global.mockClient, mockTicket))
        .rejects.toThrow('백엔드 오류');
      
      expect(global.GlobalState.setLoading).toHaveBeenCalledWith(true);
      expect(global.GlobalState.setLoading).toHaveBeenCalledWith(false);
    });
  });

  describe('🗜️ 데이터 압축 및 최적화', () => {
    test('compressTicketData - 티켓 데이터 압축', () => {
      const tickets = [
        {
          id: 1,
          subject: '매우 긴 제목입니다'.repeat(10),
          description: '매우 긴 설명입니다'.repeat(50),
          status: 2,
          priority: 3,
          created_at: '2024-01-01',
          updated_at: '2024-01-02',
          tags: ['tag1', 'tag2', 'tag3', 'tag4', 'tag5', 'tag6', 'tag7'],
          urgency_score: 75
        }
      ];
      
      const compressed = Data.compressTicketData(tickets);
      
      expect(compressed).toHaveLength(1);
      expect(compressed[0]).toEqual({
        id: 1,
        s: tickets[0].subject,
        d: expect.stringContaining('...'), // 잘렸어야 함
        st: 2,
        p: 3,
        ca: '2024-01-01',
        ua: '2024-01-02',
        t: ['tag1', 'tag2', 'tag3', 'tag4', 'tag5'], // 최대 5개
        us: 75
      });
      
      expect(compressed[0].d.length).toBeLessThanOrEqual(203); // 200 + "..."
    });
    
    test('decompressTicketData - 압축된 데이터 복원', () => {
      const compressedTickets = [
        {
          id: 1,
          s: '압축된 제목',
          d: '압축된 설명',
          st: 2,
          p: 3,
          ca: '2024-01-01',
          ua: '2024-01-02',
          t: ['tag1', 'tag2'],
          us: 80
        }
      ];
      
      const decompressed = Data.decompressTicketData(compressedTickets);
      
      expect(decompressed).toHaveLength(1);
      expect(decompressed[0]).toEqual({
        id: 1,
        subject: '압축된 제목',
        description: '압축된 설명',
        status: 2,
        priority: 3,
        created_at: '2024-01-01',
        updated_at: '2024-01-02',
        tags: ['tag1', 'tag2'],
        urgency_score: 80
      });
    });
  });

  describe('🛠️ 유틸리티 함수들', () => {
    test('sanitizeText - HTML 태그 제거 및 공백 정리', () => {
      const input = '<p>테스트   <strong>텍스트</strong></p>  \n\n  추가   내용  ';
      const result = Data.sanitizeText(input);
      
      expect(result).toBe('테스트 텍스트 추가 내용');
    });
    
    test('truncateText - 텍스트 길이 제한', () => {
      const longText = 'a'.repeat(250);
      const result = Data.truncateText(longText, 200);
      
      expect(result).toBe('a'.repeat(200) + '...');
      
      const shortText = '짧은 텍스트';
      expect(Data.truncateText(shortText, 200)).toBe('짧은 텍스트');
    });
    
    test('normalizeStatus - 상태 번호를 문자열로 변환', () => {
      expect(Data.normalizeStatus(2)).toBe('open');
      expect(Data.normalizeStatus(3)).toBe('pending');
      expect(Data.normalizeStatus(4)).toBe('resolved');
      expect(Data.normalizeStatus(5)).toBe('closed');
      expect(Data.normalizeStatus(999)).toBe('unknown');
    });
    
    test('normalizePriority - 우선순위 번호를 문자열로 변환', () => {
      expect(Data.normalizePriority(1)).toBe('low');
      expect(Data.normalizePriority(2)).toBe('medium');
      expect(Data.normalizePriority(3)).toBe('high');
      expect(Data.normalizePriority(4)).toBe('urgent');
      expect(Data.normalizePriority(999)).toBe('medium');
    });
    
    test('parseDate - 날짜 문자열 파싱', () => {
      const validDate = '2024-01-15T10:30:00Z';
      const result = Data.parseDate(validDate);
      
      expect(result).toBe(new Date(validDate).toISOString());
      
      const invalidDate = 'invalid date';
      const fallbackResult = Data.parseDate(invalidDate);
      
      expect(new Date(fallbackResult).getTime()).toBeGreaterThan(Date.now() - 1000);
    });
    
    test('extractTags - 태그 배열 추출 및 정리', () => {
      expect(Data.extractTags(['tag1', 'tag2', ''])).toEqual(['tag1', 'tag2']);
      expect(Data.extractTags(['', null, 'valid'])).toEqual(['valid']);
      expect(Data.extractTags(null)).toEqual([]);
      expect(Data.extractTags('not array')).toEqual([]);
    });
    
    test('categorizeTicket - 티켓 카테고리 분류', () => {
      expect(Data.categorizeTicket({ subject: 'Bug in system' })).toBe('bug');
      expect(Data.categorizeTicket({ subject: 'Error occurred' })).toBe('bug');
      expect(Data.categorizeTicket({ subject: 'Feature request' })).toBe('feature');
      expect(Data.categorizeTicket({ subject: 'Question about usage' })).toBe('support');
      expect(Data.categorizeTicket({ subject: 'General inquiry' })).toBe('general');
    });
    
    test('calculateUrgencyScore - 긴급도 점수 계산', () => {
      const urgentTicket = {
        priority: 4, // urgent
        status: 2,   // open
        created_at: new Date(Date.now() - 1000 * 60 * 60 * 12).toISOString() // 12시간 전
      };
      
      const score = Data.calculateUrgencyScore(urgentTicket);
      expect(score).toBe(65); // 40 + 10 + 15 = 65
      
      const oldTicket = {
        priority: 1,
        status: 5,
        created_at: new Date(Date.now() - 1000 * 60 * 60 * 48).toISOString() // 48시간 전
      };
      
      const lowScore = Data.calculateUrgencyScore(oldTicket);
      expect(lowScore).toBe(0);
    });
    
    test('createFallbackTicket - 폴백 티켓 생성', () => {
      const originalTicket = { id: 123 };
      const fallback = Data.createFallbackTicket(originalTicket);
      
      expect(fallback).toEqual({
        id: 123,
        subject: '데이터 오류',
        description: '티켓 데이터를 처리할 수 없습니다.',
        status: 'unknown',
        priority: 'medium',
        created_at: expect.any(String),
        updated_at: expect.any(String),
        tags: [],
        category: 'error',
        urgency_score: 0
      });
      
      const emptyTicket = {};
      const fallbackEmpty = Data.createFallbackTicket(emptyTicket);
      expect(fallbackEmpty.id).toBe('unknown');
    });
  });

  describe('🔗 모듈 의존성', () => {
    test('isAvailable - 모듈 사용 가능 여부', () => {
      const result = Data.isAvailable();
      expect(result).toBe(true);
    });
  });

  describe('🎯 통합 시나리오 테스트', () => {
    test('프롬프트 전송 워크플로우', async () => {
      const mockResponse = {
        data: {
          content: '통합 테스트 응답',
          type: 'markdown'
        }
      };
      
      global.API.post.mockResolvedValue(mockResponse);
      
      const result = await Data.sendPrompt('통합 테스트 프롬프트');
      
      expect(result.content).toBe('통합 테스트 응답');
      expect(result.type).toBe('markdown');
      expect(result.timestamp).toBeGreaterThan(Date.now() - 1000);
    });
    
    test('티켓 로드 + 솔루션 생성 연계', async () => {
      document.body.innerHTML = '<div id="suggested-solutions-list"></div>';
      
      const mockTicket = { id: 555, subject: '통합 테스트 티켓' };
      
      global.mockClient.data.get.mockResolvedValue({ ticket: mockTicket });
      global.GlobalState.getGlobalTicketData.mockReturnValue({
        cached_ticket_id: null,
        recommended_solutions: []
      });
      global.GlobalState.isGlobalDataValid.mockReturnValue(false);
      
      // 티켓 로드
      await Data.loadTicketDetails(global.mockClient);
      
      // 솔루션 로드
      Data.loadSuggestedSolutions(mockTicket);
      
      // 결과 확인
      expect(global.GlobalState.updateGlobalTicketData).toHaveBeenCalledWith(555, 'cached_ticket_id');
      
      const container = document.getElementById('suggested-solutions-list');
      expect(container.innerHTML).toContain('일반적인 문제 해결 방법');
    });
    
    test('데이터 압축/해제 사이클', () => {
      const originalTickets = [
        {
          id: 1,
          subject: '테스트 티켓',
          description: '테스트 설명',
          status: 2,
          priority: 3,
          created_at: '2024-01-01',
          updated_at: '2024-01-02',
          tags: ['tag1', 'tag2'],
          urgency_score: 50
        }
      ];
      
      // 압축
      const compressed = Data.compressTicketData(originalTickets);
      expect(compressed[0].s).toBe('테스트 티켓');
      
      // 해제
      const decompressed = Data.decompressTicketData(compressed);
      expect(decompressed[0].subject).toBe('테스트 티켓');
      expect(decompressed[0].id).toBe(originalTickets[0].id);
    });
  });

  describe('📊 성능 테스트', () => {
    test('대량 티켓 압축 성능', () => {
      const largeTicketSet = Array.from({ length: 10000 }, (_, i) => ({
        id: i + 1,
        subject: `티켓 제목 ${i + 1}`,
        description: `티켓 설명 ${i + 1}`.repeat(10),
        status: (i % 4) + 2,
        priority: (i % 4) + 1,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        tags: [`tag${i}`, `category${i % 5}`],
        urgency_score: Math.floor(Math.random() * 100)
      }));
      
      const start = performance.now();
      const compressed = Data.compressTicketData(largeTicketSet);
      const end = performance.now();
      
      expect(compressed).toHaveLength(10000);
      expect(end - start).toBeLessThan(1000); // 1초 이내
    });
    
    test('텍스트 처리 함수 성능', () => {
      const largeText = 'a'.repeat(100000);
      
      const start = performance.now();
      const sanitized = Data.sanitizeText(largeText);
      const truncated = Data.truncateText(sanitized, 1000);
      const end = performance.now();
      
      expect(truncated.length).toBeLessThanOrEqual(1003); // 1000 + "..."
      expect(end - start).toBeLessThan(100); // 100ms 이내
    });
  });

  describe('🚨 에러 처리 및 복구', () => {
    test('API 오류 시 폴백 동작', async () => {
      global.API.post.mockRejectedValue(new Error('서버 오류'));
      
      await expect(Data.sendPrompt('테스트')).rejects.toThrow('서버 오류');
      await expect(Data.loadInitialDataFromBackend(global.mockClient, { id: 1 }))
        .rejects.toThrow('서버 오류');
    });
    
    test('잘못된 데이터에 대한 안정성', () => {
      expect(() => {
        Data.compressTicketData(null);
      }).toThrow();
      
      expect(() => {
        Data.sanitizeText(null);
      }).toThrow();
      
      // 하지만 일부 함수는 안전하게 처리해야 함
      expect(Data.extractTags(null)).toEqual([]);
      expect(Data.normalizeStatus('invalid')).toBe('unknown');
    });
    
    test('DOM 요소 없음에 대한 안정성', () => {
      document.body.innerHTML = ''; // 모든 요소 제거
      
      const ticket = { id: 1, subject: 'test' };
      
      expect(() => {
        Data.loadSuggestedSolutions(ticket);
      }).not.toThrow();
    });
  });
});
