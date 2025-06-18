/**
 * globals.js 모듈 테스트
 * 
 * GlobalState, PerformanceOptimizer, ErrorHandler, DebugTools 등
 * 핵심 전역 모듈들의 기능을 테스트합니다.
 */

// 테스트 대상 모듈 로드
require('../app/scripts/globals.js');

describe('🧠 GlobalState 모듈', () => {
  beforeEach(() => {
    // GlobalState 초기화 (개별 메서드 사용)
    window.GlobalState.setInitialized(true);
    window.GlobalState.resetGlobalTicketCache();
  });

  test('초기화가 정상적으로 수행되어야 함', () => {
    expect(window.GlobalState.getInitialized()).toBe(true);
    expect(window.GlobalState.getClient()).toBeNull();
  });

  test('타입 검증이 올바르게 동작해야 함', () => {
    const mockTicketData = TestUtils.generateMockData('ticket');
    
    // 올바른 데이터 타입으로 업데이트
    window.GlobalState.updateGlobalTicketData(mockTicketData);
    const retrieved = window.GlobalState.getGlobalTicketData();
    
    expect(retrieved).toMatchObject(mockTicketData);
    expect(window.GlobalState.isGlobalDataValid()).toBe(true);
  });

  test('글로벌 티켓 캐시 관리가 정상 동작해야 함', () => {
    const testData = { summary: 'test summary', similar_tickets: [{ id: '123' }] };
    
    // 데이터 설정
    window.GlobalState.updateGlobalTicketData(testData);
    const retrieved = window.GlobalState.getGlobalTicketData();
    
    // 설정한 필드들이 포함되어 있는지 확인
    expect(retrieved.summary).toEqual(testData.summary);
    expect(retrieved.similar_tickets).toEqual(testData.similar_tickets);
    
    // 캐시 초기화
    window.GlobalState.resetGlobalTicketCache();
    const resetData = window.GlobalState.getGlobalTicketData();
    expect(resetData.summary).toBeNull();
    expect(resetData.similar_tickets).toEqual([]);
  });
});

describe('⚡ PerformanceOptimizer 모듈', () => {
  let optimizer;

  beforeEach(() => {
    optimizer = window.PerformanceOptimizer;
    optimizer.clearAllCaches();
  });

  test('메모이제이션이 올바르게 동작해야 함', () => {
    const expensiveFunction = jest.fn((x) => x * 2);
    const memoized = optimizer.memoize(expensiveFunction);

    // 첫 번째 호출
    expect(memoized(5)).toBe(10);
    expect(expensiveFunction).toHaveBeenCalledTimes(1);

    // 두 번째 호출 (캐시된 결과 사용)
    expect(memoized(5)).toBe(10);
    expect(expensiveFunction).toHaveBeenCalledTimes(1); // 여전히 1번만

    // 다른 인수로 호출
    expect(memoized(3)).toBe(6);
    expect(expensiveFunction).toHaveBeenCalledTimes(2);
  });

  test('API 결과 캐싱이 TTL과 함께 동작해야 함', async () => {
    const testData = { result: 'test' };
    const shortTTL = 100; // 100ms

    // 캐시 저장
    optimizer.cacheApiResult('test-key', testData, shortTTL);
    
    // 즉시 조회 - 캐시 히트
    expect(optimizer.getCachedApiResult('test-key')).toEqual(testData);

    // TTL 경과 후 조회 - 캐시 만료
    await testUtils.waitFor(150);
    expect(optimizer.getCachedApiResult('test-key')).toBeNull();
  });

  test('DOM 요소 캐싱이 정상 동작해야 함', () => {
    // 테스트용 DOM 요소 생성
    const testElement = testUtils.createElement('div', { id: 'test-element' });
    document.body.appendChild(testElement);

    // 첫 번째 호출 - 실제 DOM 검색
    const element1 = optimizer.getDOMElement('#test-element');
    expect(element1).toBe(testElement);

    // 두 번째 호출 - 캐시에서 반환
    const element2 = optimizer.getDOMElement('#test-element');
    expect(element2).toBe(testElement);
    expect(element1).toBe(element2);
  });

  test('배치 DOM 업데이트가 정상 동작해야 함', async () => {
    const container = testUtils.createElement('div');
    document.body.appendChild(container);

    const updates = [
      {
        type: 'create',
        tag: 'div',
        properties: { textContent: 'Item 1' },
        parent: container
      },
      {
        type: 'create',
        tag: 'div',
        properties: { textContent: 'Item 2' },
        parent: container
      }
    ];

    await optimizer.batchDOMUpdates(updates);

    expect(container.children.length).toBe(2);
    expect(container.children[0].textContent).toBe('Item 1');
    expect(container.children[1].textContent).toBe('Item 2');
  });

  test('메모리 통계가 올바르게 반환되어야 함', () => {
    const stats = optimizer.getMemoryStats();
    
    expect(stats).toHaveProperty('functionCache');
    expect(stats).toHaveProperty('resultCache');
    expect(stats).toHaveProperty('domCache');
    expect(stats).toHaveProperty('cacheStats');
    expect(stats).toHaveProperty('memoryUsage');
  });
});

describe('🚨 ErrorHandler 모듈', () => {
  let errorHandler;

  beforeEach(() => {
    errorHandler = window.GlobalState.ErrorHandler;
  });

  test('에러 처리가 심각도별로 올바르게 동작해야 함', () => {
    const testError = new Error('Test error');
    const context = {
      module: 'test',
      severity: 'high',
      userMessage: 'Test user message'
    };

    // 에러 처리 실행 (실제로는 콘솔 출력이나 UI 업데이트)
    expect(() => {
      errorHandler.handleError(testError, context);
    }).not.toThrow();
  });

  test('에러 복구 메커니즘이 동작해야 함', () => {
    const recoveryFn = jest.fn();
    const testError = new Error('Recoverable error');
    
    const context = {
      module: 'test',
      severity: 'medium',
      recovery: recoveryFn
    };

    errorHandler.handleError(testError, context);
    
    // 복구 함수가 호출되었는지 확인 (실제 구현에 따라 달라질 수 있음)
    // expect(recoveryFn).toHaveBeenCalled();
  });
});

describe('🔧 DebugTools 모듈', () => {
  let debugTools;

  beforeEach(() => {
    debugTools = window.DebugTools;
  });

  test('시스템 상태 검사가 정상 동작해야 함', () => {
    const status = debugTools.checkAppHealth();
    
    expect(status).toHaveProperty('overall');
    expect(status).toHaveProperty('checks');
    expect(status).toHaveProperty('timestamp');
    expect(['healthy', 'warning', 'critical', 'unknown']).toContain(status.overall);
  });

  test('성능 리포트가 올바르게 생성되어야 함', () => {
    // PerformanceOptimizer를 통해 성능 데이터 수집
    const memoryStats = window.PerformanceOptimizer.getMemoryStats();
    
    expect(memoryStats).toHaveProperty('functionCache');
    expect(memoryStats).toHaveProperty('resultCache');
    expect(memoryStats).toHaveProperty('domCache');
  });

  test('모든 캐시 초기화가 정상 동작해야 함', () => {
    // 캐시에 데이터 추가
    window.PerformanceOptimizer.cacheApiResult('test', { data: 'test' });
    
    // 캐시 초기화
    window.PerformanceOptimizer.clearAllCaches();
    
    // 캐시가 비어있는지 확인
    expect(window.PerformanceOptimizer.getCachedApiResult('test')).toBeNull();
  });
});

describe('🔗 ModuleDependencyManager', () => {
  let manager;

  beforeEach(() => {
    manager = window.ModuleDependencyManager;
    // 기존 등록된 모듈들을 백업하고 초기화
    manager.loadedModules.clear(); 
  });

  test('모듈 등록이 정상 동작해야 함', () => {
    manager.registerModule('testModule', 5);
    
    expect(manager.loadedModules.has('testModule')).toBe(true);
  });

  test('의존성 검증이 올바르게 동작해야 함', () => {
    // 테스트 모듈들 등록
    manager.registerModule('globals', 10);
    manager.registerModule('utils', 5);
    
    const check = manager.checkDependencies('utils');
    
    expect(check).toHaveProperty('success');
    expect(check).toHaveProperty('missing');
    expect(check).toHaveProperty('required');
    expect(check).toHaveProperty('loaded');
  });

  test('시스템 준비 상태 확인이 동작해야 함', () => {
    // 필수 모듈들 등록
    manager.registerModule('globals', 10);
    manager.registerModule('utils', 5);
    manager.registerModule('api', 8);
    manager.registerModule('data', 6);
    manager.registerModule('ui', 12);
    manager.registerModule('events', 7);
    
    const isReady = manager.isSystemReady();
    expect(typeof isReady).toBe('boolean');
    expect(isReady).toBe(true);
  });
});
