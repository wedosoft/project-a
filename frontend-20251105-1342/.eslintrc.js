module.exports = {
  env: {
    browser: true,
    es6: true,
    jest: true,
    node: true,
  },
  extends: [
    'eslint:recommended',
    'prettier',
  ],
  parserOptions: {
    ecmaVersion: 2020,
    sourceType: 'script',
  },
  globals: {
    // Freshdesk FDK
    app: 'readonly',
    client: 'writable',
    
    // External libraries
    marked: 'readonly',
    
    // App globals
    App: 'writable',
    Core: 'writable',
    ApiService: 'writable',
    TicketUI: 'writable',
    ChatUI: 'writable',
    Performance: 'writable',
    
    // 프로젝트 전역 객체
    GlobalState: 'readonly',
    ModuleDependencyManager: 'readonly',
    Utils: 'readonly',
    ApiModule: 'readonly',
    API: 'readonly',
    EventsModule: 'readonly',
    Events: 'readonly',
    UIModule: 'readonly',
    UI: 'readonly',
    DataModule: 'readonly',
    Data: 'readonly',
    PerformanceOptimizer: 'readonly',
    ErrorHandler: 'readonly',
    DebugTools: 'readonly',
    
    // 레거시 전역 변수들 (원본 파일용)
    globalTicketData: 'readonly',
    isDataStale: 'readonly',
    updateTicketInfo: 'readonly',
    displayTicketSummary: 'readonly',
    displaySimilarTickets: 'readonly',
    displaySuggestedSolutions: 'readonly',
    loadSimilarTicketsFromFreshdesk: 'readonly',
    loadSimilarTicketsFromBackend: 'readonly',
    generateMockSolutions: 'readonly',
    loadSuggestedSolutions: 'readonly',
    showErrorInResults: 'readonly',
    showErrorInResultsInResults: 'readonly',
    showLoadingInResults: 'readonly',
    showSimilarTicketsListView: 'readonly',
    showSuggestedSolutionsListView: 'readonly',
    callBackendAPI: 'readonly',
    performCopilotSearch: 'readonly',
    displayCopilotResults: 'readonly',
    
    // Utility 함수들
    getStatusText: 'readonly',
    getPriorityText: 'readonly',
    getStatusClass: 'readonly',
    getPriorityClass: 'readonly',
    formatDate: 'readonly',
    formatDescription: 'readonly',
    formatSolutionContent: 'readonly',
    truncateText: 'readonly',
    loadTicketDetails: 'readonly',
    
    // 탭/이벤트 핸들러들
    handleSimilarTicketsTab: 'readonly',
    handleSuggestedSolutionsTab: 'readonly',
    handleCopilotTab: 'readonly',
    setupSimilarTicketsEvents: 'readonly',
    setupSuggestedSolutionsEvents: 'readonly',
    setupCopilotEvents: 'readonly',
  },
  rules: {
    'no-unused-vars': ['warn', { argsIgnorePattern: '^_' }],
  // Disallow broad console usage in committed code (allow warn/error only)
  'no-console': ['warn', { allow: ['warn', 'error'] }],
    'no-undef': 'error',
    'prefer-const': 'warn',
    'no-var': 'warn',
    'no-dupe-keys': 'error',
    'no-global-assign': 'warn',
    'no-useless-escape': 'warn',
  },
  overrides: [
    {
      files: ['tests/**/*.js'],
      env: { jest: true },
      rules: { 'no-undef': 'off' },
    },
    {
      files: ['app/scripts/*_original.js'],
      rules: { 
        'no-undef': 'warn',
        'no-unused-vars': 'warn',
      },
    },
    {
      files: ['app/scripts/modules/**/*.js', 'app/scripts/app.js'],
      parserOptions: {
        ecmaVersion: 2020,
        sourceType: 'module',
      },
    },
    {
      // Coverage instrumented files 제외
      files: ['**/localhost:*/**/*.js', '**/coverage/**/*.js', '**/__instrumented__/**/*.js'],
      rules: {
        'no-var': 'off',
        'prefer-const': 'off',
      },
    },
  ],
};
