/**
 * Admin Console New - Main Controller
 * 관리자 콘솔의 메인 컨트롤러 (데이터 제어 기능 전용)
 * 
 * 주요 기능:
 * - 데이터 수집 관리 (data-collection-manager)
 * - 시스템 상태 모니터링
 * - 벡터DB 통계 표시
 * 
 * 비활성화된 기능:
 * - 에이전트 관리 (agent-manager)
 */
class AdminConsoleNew {
    constructor() {
        this.i18n = new I18nManager();
        this.baseUrl = null;
        this.client = null;
        this.apiKey = null;
        // 기본값은 개발 환경에서만 사용, 프로덕션에서는 자동 감지
        this.tenantId = null;
        this.platform = 'freshdesk';
        this.domain = null;
        this.isInitialized = false; // 초기화 상태 추적
        this.initializeBackendConfig();
    }

    initializeBackendConfig() {
        // backend-config.js의 getUrl 메서드 사용
        if (!window.BACKEND_CONFIG?.getUrl) {
            console.error('백엔드 설정이 초기화되지 않았습니다. backend-config.js를 확인하세요.');
            throw new Error('Backend configuration not initialized');
        }
    }

    async init() {
        try {
            // 1. 다국어 시스템 초기화
            await this.initI18n();

            // 2. FDK 클라이언트 초기화
            await this.initializeFDKClient();

            // 3. 고객 도메인 정보 로드
            await this.loadCustomerDomain();

            // 4. 시스템 건강 상태 체크
            await this.checkSystemHealth();

            // 5. 대시보드 데이터 로드
            await this.loadDashboardData();

            // 6. 이벤트 리스너 설정
            this.setupEventListeners();

            // 7. 초기화 완료 플래그 설정
            this.isInitialized = true;

            console.log('✅ Admin Console New initialized successfully');
        } catch (error) {
            console.error('❌ Admin Console initialization failed:', error);
            this.showAlert('error', `초기화 실패: ${error.message}`);
        }
    }

    async initI18n() {
        await this.i18n.loadTranslations();

        // 사용자 설정 또는 브라우저 언어에 따라 언어 설정
        const savedLanguage = localStorage.getItem('preferredLanguage');
        const browserLanguage = navigator.language.startsWith('ko') ? 'ko' : 'en';
        const defaultLanguage = savedLanguage || browserLanguage;

        this.i18n.setLanguage(defaultLanguage);

        console.log(`🌐 Language set to: ${defaultLanguage}`);
    }

    initializeFDKClient() {
        return new Promise((resolve, reject) => {
            if (typeof app === 'undefined') {
                const error = new Error('FDK 환경을 감지하지 못했습니다. Freshdesk 내에서 앱을 실행하세요.');
                console.error(error);
                reject(error);
                return;
            }

            app.initialized().then(async (client) => {
                console.log('✅ FDK Client initialized');
                this.client = client;

                try {
                    await this.loadApiKey();
                    resolve();
                } catch (error) {
                    reject(error);
                }
            }).catch(error => {
                console.error('❌ FDK initialization failed:', error);
                reject(new Error('FDK 클라이언트를 초기화할 수 없습니다.'));
            });
        });
    }

    async loadApiKey() {
        if (!this.client) {
            throw new Error('FDK 클라이언트가 준비되지 않아 API 키를 가져올 수 없습니다.');
        }

        try {
            const data = await this.client.request.invoke('getSecureParams', {});
            const responseData = data?.response || data;
            const apiKey = this.processSecureResponse(responseData);

            if (!apiKey) {
                throw new Error('API 키를 찾을 수 없습니다. Freshdesk 앱 설정을 확인하세요.');
            }

            this.apiKey = apiKey;
        } catch (error) {
            console.error('❌ API 키 로드 실패:', error);
            if (error instanceof Error) {
                throw error;
            }
            throw new Error('API 키 로드 중 알 수 없는 오류가 발생했습니다.');
        }
    }

    processSecureResponse(responseData) {
        if (responseData && responseData.freshdesk_api_key) {
            return responseData.freshdesk_api_key;
        } else if (responseData && responseData.apiKey) {
            return responseData.apiKey;
        } else if (responseData && responseData.api_key) {
            return responseData.api_key;
        } else if (responseData && responseData.error) {
            console.error('❌ 서버리스 함수 오류:', responseData.error);
            return null;
        } else {
            console.error('❌ API 키를 찾을 수 없습니다');
            return null;
        }
    }

    async loadCustomerDomain() {
        try {
            if (!this.client) {
                throw new Error('FDK 클라이언트가 준비되지 않아 도메인을 불러올 수 없습니다.');
            }

            let domain = null;

            try {
                const iparams = await this.client.iparams.get();
                const iparamDomain = iparams?.freshdesk_domain || iparams?.domain;
                if (iparamDomain) {
                    domain = this.normalizeDomain(iparamDomain);
                }
            } catch (error) {
                console.warn('⚠️ iparams에서 도메인을 가져오지 못했습니다:', error);
            }

            if (!domain && this.client && typeof this.client.context === 'function') {
                try {
                    const context = await this.client.context();
                    const subdomain = context?.account?.subdomain;
                    if (subdomain) {
                        domain = this.normalizeDomain(`${subdomain}.freshdesk.com`);
                    }
                } catch (error) {
                    console.warn('⚠️ FDK context 호출 실패:', error);
                }
            }

            if (!domain && this.client?.instance?.context) {
                try {
                    const context = await this.client.instance.context();
                    const subdomain = context?.account?.subdomain;
                    if (subdomain) {
                        domain = this.normalizeDomain(`${subdomain}.freshdesk.com`);
                    }
                } catch (error) {
                    console.warn('⚠️ FDK instance context 실패:', error);
                }
            }

            if (!domain && typeof app !== 'undefined' && typeof app.context === 'function') {
                try {
                    const context = await app.context();
                    const subdomain = context?.account?.subdomain;
                    if (subdomain) {
                        domain = this.normalizeDomain(`${subdomain}.freshdesk.com`);
                    }
                } catch (error) {
                    console.warn('⚠️ App context 실패:', error);
                }
            }

            if (!domain && window.location.hostname.includes('.freshdesk.com')) {
                domain = this.normalizeDomain(window.location.hostname);
            }

            if (!domain) {
                throw new Error('Freshdesk 도메인을 감지할 수 없습니다. 앱 설정을 확인하세요.');
            }

            const tenantId = this.extractTenantId(domain);

            this.domain = domain;
            this.tenantId = tenantId;

            const domainLabel = document.getElementById('customerDomain');
            if (domainLabel) {
                domainLabel.textContent = tenantId;
            }

        } catch (error) {
            console.error('❌ Customer domain 로드 실패:', error);
            throw error;
        }
    }
    async loadDashboardData() {
        try {
            const headers = this.getApiHeaders();
            const response = await fetch(window.BACKEND_CONFIG.getUrl('/admin/dashboard/'), {
                headers: headers
            });

            if (response.ok) {
                const data = await response.json();
                this.updateDashboard(data);
            } else {
                const errorText = await response.text();
                console.error('loadDashboardData - Error Response:', errorText);
                // API 호출 실패시 빈 데이터 표시
                this.updateDashboard({
                    system_status: 'offline',
                    vector_db_stats: { tickets_count: 0, articles_count: 0 },
                    license_info: {},
                    last_sync: null
                });
            }
        } catch (error) {
            console.warn('⚠️ Failed to load dashboard data:', error);
            // 에러시 빈 데이터 표시
            this.updateDashboard({
                system_status: 'error',
                vector_db_stats: { tickets_count: 0, articles_count: 0 },
                license_info: {},
                last_sync: null
            });
        }
    }

    async checkSystemHealth() {
        try {
            const headers = this.getApiHeaders();
            const url = window.BACKEND_CONFIG.getUrl('/admin/system/status');
            const response = await fetch(url, { headers: headers });

            if (response.ok) {
                const data = await response.json();
                this.updateSystemStatus(data);
            } else {
                const text = await response.text();
                console.error('checkSystemHealth - Error Response:', text);
                this.updateSystemStatus({ status: 'error' });
            }
        } catch (error) {
            console.warn('⚠️ System health check failed:', error);
            this.updateSystemStatus({ status: 'error' });
        }
    }

    getApiHeaders() {
        // 초기화 미완료 시 대기하거나 에러 처리
        if (!this.apiKey || !this.tenantId || !this.domain) {
            const errorMessage = `Admin Console 초기화 미완료. 다시 시도해주세요. (API키: ${!!this.apiKey}, 테넌트: ${!!this.tenantId}, 도메인: ${!!this.domain})`;
            console.warn('⚠️', errorMessage);
            throw new Error(errorMessage);
        }

        const headers = {
            ...window.BACKEND_CONFIG.getCommonHeaders(),  // 공통 헤더 사용
            'Accept': 'application/json'
        };

        if (this.apiKey) {
            headers['X-API-Key'] = this.apiKey;
        }
        if (this.tenantId) {
            headers['X-Tenant-ID'] = this.tenantId;
        }
        if (this.platform) {
            headers['X-Platform'] = this.platform;
        }
        if (this.domain) {
            headers['X-Domain'] = this.domain;
        }

        const missing = [];
        if (!headers['X-Tenant-ID']) missing.push('X-Tenant-ID');
        if (!headers['X-Domain']) missing.push('X-Domain');
        if (!headers['X-API-Key']) missing.push('X-API-Key');

        if (missing.length) {
            const errorMessage = `필수 헤더 누락: ${missing.join(', ')}. Freshdesk 앱 초기화를 확인하세요.`;
            console.error('❌', errorMessage);
            throw new Error(errorMessage);
        }

        return headers;
    }

    updateSystemStatus(healthData) {
        const systemStatusEl = document.getElementById('systemStatus');
        const statusDotEl = document.querySelector('.status-dot');

        if (systemStatusEl && statusDotEl) {
            // 항상 점을 표시하되 색상을 다르게
            statusDotEl.style.display = 'inline-block';

            // API 응답 형식에 맞게 상태 체크 (status: 'healthy' 형식)
            if (healthData.status === 'healthy') {
                systemStatusEl.textContent = '운영중';
                systemStatusEl.className = 'status-healthy';
                statusDotEl.className = 'status-dot status-success';
            } else if (healthData.status === 'offline') {
                systemStatusEl.textContent = '오프라인';
                systemStatusEl.className = 'status-offline';
                statusDotEl.className = 'status-dot status-warning';
            } else if (healthData.status === 'error') {
                systemStatusEl.textContent = '오류';
                systemStatusEl.className = 'status-error';
                statusDotEl.className = 'status-dot status-error';
            } else {
                systemStatusEl.textContent = '알 수 없음';
                systemStatusEl.className = 'status-unknown';
                statusDotEl.className = 'status-dot status-warning';
            }
        }
    }

    updateDashboard(data) {
        // 벡터DB 통계 업데이트
        const ticketCountEl = document.getElementById('ticketCount');
        if (ticketCountEl) {
            const ticketCount = data.vector_db_stats?.tickets_count || 0;
            ticketCountEl.textContent = ticketCount.toLocaleString();
        }

        const articleCountEl = document.getElementById('articleCount');
        if (articleCountEl) {
            const articleCount = data.vector_db_stats?.articles_count || 0;
            articleCountEl.textContent = articleCount.toLocaleString();
        }

        // 최종 동기화 시간 업데이트
        const lastSyncEl = document.getElementById('lastSyncTime');
        if (lastSyncEl) {
            if (data.last_sync) {
                const lastSync = new Date(data.last_sync);
                lastSyncEl.textContent = lastSync.toLocaleString('ko-KR', {
                    month: 'short',
                    day: 'numeric',
                    hour: '2-digit',
                    minute: '2-digit'
                });
            } else {
                lastSyncEl.textContent = '없음';
            }
        }
    }

    setupEventListeners() {
        // 언어 전환 (개발용 - 실제로는 설정에서 관리)
        document.addEventListener('keydown', (e) => {
            if (e.ctrlKey && e.key === 'l') {
                e.preventDefault();
                const currentLang = this.i18n.currentLanguage;
                const newLang = currentLang === 'ko' ? 'en' : 'ko';
                this.i18n.setLanguage(newLang);
                console.log(`🌐 Language switched to: ${newLang}`);
            }
        });

        // 새로고침 단축키
        document.addEventListener('keydown', (e) => {
            if (e.key === 'F5' || (e.ctrlKey && e.key === 'r')) {
                e.preventDefault();
                this.refreshDashboard();
            }
        });
    }

    async refreshDashboard() {
        console.log('🔄 Refreshing dashboard...');
        await this.loadDashboardData();
        this.showAlert('success', this.i18n.getText('dashboard_refreshed') || '대시보드가 새로고침되었습니다.');
    }

    showAlert(type, message) {
        const alertContainer = document.getElementById('alertContainer');
        if (!alertContainer) return;

        const alert = document.createElement('div');
        alert.className = `alert alert-${type} alert-dismissible fade show`;
        alert.innerHTML = `
            <span>${message}</span>
            <button type="button" class="close" onclick="this.parentElement.remove()">
                <span>&times;</span>
            </button>
        `;

        alertContainer.appendChild(alert);

        // 5초 후 자동 제거
        setTimeout(() => {
            if (alert.parentElement) {
                alert.remove();
            }
        }, 5000);
    }

    // 유틸리티 메서드들
    getText(key) {
        return this.i18n.getText(key);
    }

    getCurrentLanguage() {
        return this.i18n.currentLanguage;
    }

    normalizeDomain(domain) {
        if (!domain) {
            return null;
        }

        const trimmed = domain.trim();
        const withoutProtocol = trimmed.replace(/^https?:\/\//i, '');
        const hostname = withoutProtocol.split('/')[0];
        return hostname.toLowerCase();
    }

    extractTenantId(domain) {
        const normalized = this.normalizeDomain(domain);

        if (!normalized) {
            throw new Error('도메인 정보가 없어 테넌트 ID를 추출할 수 없습니다.');
        }

        const [tenant] = normalized.split('.');

        if (!tenant) {
            throw new Error('도메인에서 테넌트 ID를 추출할 수 없습니다.');
        }

        return tenant;
    }

    getApiKey() {
        return this.apiKey;
    }

    async makeRequest(endpoint, options = {}) {
        const url = window.BACKEND_CONFIG.getUrl(endpoint);
        const config = {
            headers: {
                ...window.BACKEND_CONFIG.getCommonHeaders(),  // 공통 헤더 사용
                ...options.headers
            },
            ...options
        };

        try {
            const response = await fetch(url, config);
            return response;
        } catch (error) {
            console.error(`Request failed: ${endpoint}`, error);
            throw error;
        }
    }
}

// 전역 인스턴스 생성 및 초기화
let adminConsole = null;

document.addEventListener('DOMContentLoaded', async () => {
    try {
        adminConsole = new AdminConsoleNew();
        await adminConsole.init();

        // Web Components에서 접근할 수 있도록 전역 설정
        window.adminConsole = adminConsole;
        window.adminConsoleNew = adminConsole; // 호환성을 위해 두 이름 모두 사용
    } catch (error) {
        console.error('❌ Failed to initialize admin console:', error);
    }
});

// Web Components에서 사용할 수 있는 유틸리티 함수들
window.adminUtils = {
    getText: (key) => adminConsole?.getText(key) || key,
    showAlert: (type, message) => adminConsole?.showAlert(type, message),
    makeRequest: (endpoint, options) => adminConsole?.makeRequest(endpoint, options),
    getCurrentLanguage: () => adminConsole?.getCurrentLanguage() || 'ko',
    getApiKey: () => adminConsole?.getApiKey() || null,
    getApiHeaders: () => {
        if (!adminConsole?.isInitialized) {
            throw new Error('Admin Console이 아직 초기화되지 않았습니다. 잠시 후 다시 시도하세요.');
        }
        return adminConsole?.getApiHeaders();
    },
    isInitialized: () => adminConsole?.isInitialized || false
};