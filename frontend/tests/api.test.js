/**
 * api.js 모듈 테스트
 * 
 * 최적화된 API 호출, 캐싱, 재시도 로직, 배치 처리 등
 * API 모듈의 핵심 기능들을 테스트합니다.
 */

// 테스트 대상 모듈 로드
require('../app/scripts/globals.js');
require('../app/scripts/api.js');

describe('🚀 API 모듈', () => {
  let api;

  beforeEach(() => {
    api = window.API;
    
    // 각 테스트 전에 모킹 초기화
    jest.clearAllMocks();
    
    // PerformanceOptimizer 모킹
    if (!window.PerformanceOptimizer) {
      window.PerformanceOptimizer = {
        getCachedApiResult: jest.fn(),
        cacheApiResult: jest.fn(),
        clearAllCaches: jest.fn(),
        getMemoryStats: jest.fn(() => ({
          cacheStats: { hits: 0, misses: 0 }
        }))
      };
    }
  });

  test('모듈 가용성 확인이 정상 동작해야 함', () => {
    expect(api.isAvailable()).toBe(true);
  });

  test('캐시 키 생성이 올바르게 동작해야 함', () => {
    const key1 = api.generateCacheKey('test-endpoint', null, 'GET');
    const key2 = api.generateCacheKey('test-endpoint', { param: 'value' }, 'POST');
    
    expect(key1).toContain('GET:test-endpoint');
    expect(key2).toContain('POST:test-endpoint');
    expect(key1).not.toBe(key2);
  });

  test('객체 해시 생성이 동일한 객체에 대해 동일한 해시를 생성해야 함', () => {
    const obj1 = { a: 1, b: 2 };
    const obj2 = { a: 1, b: 2 };
    const obj3 = { a: 1, b: 3 };
    
    const hash1 = api.hashObject(obj1);
    const hash2 = api.hashObject(obj2);
    const hash3 = api.hashObject(obj3);
    
    expect(hash1).toBe(hash2);
    expect(hash1).not.toBe(hash3);
  });

  test('헬스체크가 정상 동작해야 함', async () => {
    // 성공 응답 모킹
    testUtils.mockFetchResponse({ status: 'healthy' }, 200);
    
    const result = await api.healthCheck();
    expect(result).toBe(true);
    expect(fetch).toHaveBeenCalledWith('http://localhost:8000/health', {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' }
    });
  });

  test('헬스체크 실패 시 false를 반환해야 함', async () => {
    // 실패 응답 모킹
    testUtils.mockFetchError(new Error('Network error'));
    
    const result = await api.healthCheck();
    expect(result).toBe(false);
  });

  test('캐시된 API 호출이 정상 동작해야 함', async () => {
    const mockClient = global.app;
    const testData = { result: 'test' };
    
    // 캐시 미스 시나리오
    window.PerformanceOptimizer.getCachedApiResult.mockReturnValue(null);
    testUtils.mockFetchResponse(testData);
    
    const result = await api.callBackendAPIWithCache(
      mockClient, 
      'test-endpoint', 
      null, 
      'GET'
    );
    
    expect(result).toEqual(testData);
    expect(window.PerformanceOptimizer.cacheApiResult).toHaveBeenCalled();
  });

  test('캐시 히트 시 네트워크 요청 없이 결과를 반환해야 함', async () => {
    const mockClient = global.app;
    const cachedData = { result: 'cached' };
    
    // 캐시 히트 시나리오
    window.PerformanceOptimizer.getCachedApiResult.mockReturnValue(cachedData);
    
    const result = await api.callBackendAPIWithCache(
      mockClient,
      'test-endpoint',
      null,
      'GET'
    );
    
    expect(result).toEqual(cachedData);
    expect(fetch).not.toHaveBeenCalled();
  });

  test('재시도 로직이 정상 동작해야 함', async () => {
    const mockClient = global.app;
    
    // 첫 번째, 두 번째 호출은 실패, 세 번째는 성공
    fetch
      .mockRejectedValueOnce(new Error('Network error'))
      .mockRejectedValueOnce(new Error('Network error'))
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: jest.fn().mockResolvedValue({ success: true })
      });
    
    window.PerformanceOptimizer.getCachedApiResult.mockReturnValue(null);
    
    const result = await api.callBackendAPIWithCache(
      mockClient,
      'test-endpoint',
      null,
      'GET',
      { maxRetries: 2 }
    );
    
    expect(result).toEqual({ success: true });
    expect(fetch).toHaveBeenCalledTimes(3);
  });

  test('4xx 에러는 재시도하지 않아야 함', async () => {
    const mockClient = global.app;
    const error = new Error('Bad Request');
    error.status = 400;
    
    window.PerformanceOptimizer.getCachedApiResult.mockReturnValue(null);
    
    await expect(
      api.callBackendAPIWithCache(
        mockClient,
        'test-endpoint',
        null,
        'GET',
        { maxRetries: 2 }
      )
    ).rejects.toThrow();
    
    // 4xx 에러는 재시도하지 않으므로 fetch가 1번만 호출되어야 함
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  test('배치 API 호출이 정상 동작해야 함', async () => {
    const mockClient = global.app;
    const requests = [
      { endpoint: 'endpoint1', data: null, method: 'GET' },
      { endpoint: 'endpoint2', data: null, method: 'GET' },
      { endpoint: 'endpoint3', data: null, method: 'GET' }
    ];
    
    // 모든 요청이 성공하도록 모킹
    window.PerformanceOptimizer.getCachedApiResult.mockReturnValue(null);
    testUtils.mockFetchResponse({ success: true });
    testUtils.mockFetchResponse({ success: true });
    testUtils.mockFetchResponse({ success: true });
    
    const results = await api.batchAPICall(mockClient, requests, {
      concurrency: 2,
      delay: 10
    });
    
    expect(results).toHaveLength(3);
    expect(results.every(r => r.success)).toBe(true);
  });

  test('배치 API 호출에서 일부 실패 시 적절히 처리해야 함', async () => {
    const mockClient = global.app;
    const requests = [
      { endpoint: 'endpoint1', data: null, method: 'GET' },
      { endpoint: 'endpoint2', data: null, method: 'GET' }
    ];
    
    window.PerformanceOptimizer.getCachedApiResult.mockReturnValue(null);
    
    // 첫 번째는 성공, 두 번째는 실패
    testUtils.mockFetchResponse({ success: true });
    testUtils.mockFetchError(new Error('API Error'));
    
    const results = await api.batchAPICall(mockClient, requests);
    
    expect(results).toHaveLength(2);
    expect(results[0].success).toBe(true);
    expect(results[1].success).toBe(false);
  });

  test('캐시 통계 조회가 정상 동작해야 함', () => {
    const mockStats = {
      cacheStats: { hits: 10, misses: 5 },
      memoryUsage: '10 MB'
    };
    
    window.PerformanceOptimizer.getMemoryStats.mockReturnValue(mockStats);
    
    const stats = api.getCacheStats();
    expect(stats).toEqual(mockStats);
  });

  test('캐시 초기화가 정상 동작해야 함', () => {
    api.clearCache();
    expect(window.PerformanceOptimizer.clearAllCaches).toHaveBeenCalled();
  });
});

describe('🔄 API 통합 테스트', () => {
  beforeEach(() => {
    // 실제 모듈들 로드
    require('../app/scripts/globals.js');
    require('../app/scripts/api.js');
  });

  test('초기 데이터 로드 워크플로우', async () => {
    const mockClient = {
      iparams: {
        get: jest.fn().mockResolvedValue({
          freshdesk_domain: 'test.freshdesk.com',
          freshdesk_api_key: 'test-key'
        })
      }
    };
    
    const mockInitData = {
      ticket_summary: { problem: 'Test problem' },
      similar_tickets: [],
      kb_documents: []
    };
    
    testUtils.mockFetchResponse(mockInitData);
    
    const result = await window.API.loadInitData(mockClient, '12345');
    
    expect(result).toEqual(mockInitData);
    expect(fetch).toHaveBeenCalledWith(
      'http://localhost:8000/init/12345',
      expect.objectContaining({
        method: 'GET',
        headers: expect.objectContaining({
          'X-Freshdesk-Domain': 'test.freshdesk.com',
          'X-Freshdesk-API-Key': 'test-key'
        })
      })
    );
  });

  test('쿼리 실행 워크플로우', async () => {
    const mockClient = {
      iparams: {
        get: jest.fn().mockResolvedValue({
          freshdesk_domain: 'test.freshdesk.com',
          freshdesk_api_key: 'test-key'
        })
      }
    };
    
    const queryData = {
      query: '로그인 문제 해결',
      type: ['tickets', 'solutions']
    };
    
    const mockResponse = {
      results: [
        { type: 'ticket', title: 'Similar issue' }
      ]
    };
    
    testUtils.mockFetchResponse(mockResponse);
    
    const result = await window.API.executeQuery(mockClient, queryData);
    
    expect(result).toEqual(mockResponse);
    expect(fetch).toHaveBeenCalledWith(
      'http://localhost:8000/query',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify(queryData)
      })
    );
  });
});
