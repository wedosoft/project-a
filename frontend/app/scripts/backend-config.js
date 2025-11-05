/**
 * 백    // URL 생성 함수 - 환경에 따라 적절한 베이스 URL 결정
    getUrl(path) {
        const baseUrl = this.getBaseUrl();
        // path가 이미 /로 시작하면 그대로, 아니면 /를 앞에 추가
        const cleanPath = path.startsWith('/') ? path : `/${path}`;
        return `${baseUrl}/api/v1${cleanPath}`;
    }, 이 파일은 백엔드 URL 설정을 중앙에        // 전역 설정 객체 생성
        window.BACKEND_CONFIG = {
            host: host,
            environment: environment,
            protocol: 'https',
            getUrl: function(path) {
                // path가 /로 시작하지 않으면 추가
                if (!path.startsWith('/')) {
                    path = '/' + path;
                }
                // 날것의 URL 반환 (접두사 없음)
                return `${this.protocol}://${this.host}${path}`;
            }
        };/프로덕션 환경에 따라 자동으로 적절한 URL을 선택합니다.
 */

(function () {
    'use strict';

    // 환경별 백엔드 호스트 설정
    const BACKEND_HOSTS = {
        // 프로덕션 환경
        production: 'ameer-timberless-paragogically.ngrok-free.dev',

        // 개발 환경 (필요시 localhost 사용)
        development: 'ameer-timberless-paragogically.ngrok-free.dev',

        // 테스트 환경
        test: 'ameer-timberless-paragogically.ngrok-free.dev'
    };

    // 현재 환경 감지
    function detectEnvironment() {
        const hostname = window.location.hostname;

        // 개발 환경 감지 (다른 방법으로 판단)
        if (hostname.includes('dev') || hostname.includes('staging')) {
            return 'development';
        }

        // 테스트 환경
        if (hostname.includes('test') || hostname.includes('staging')) {
            return 'test';
        }

        // 기본적으로 프로덕션
        return 'production';
    }

    // 백엔드 설정 초기화
    function initBackendConfig() {
        const environment = detectEnvironment();
        const host = BACKEND_HOSTS[environment] || BACKEND_HOSTS.production;

        // 전역 설정 객체 생성
        window.BACKEND_CONFIG = {
            host: host,
            environment: environment,
            protocol: 'https',
            getUrl: function (path) {
                // path가 /로 시작하지 않으면 추가
                if (!path.startsWith('/')) {
                    path = '/' + path;
                }
                // API prefix 추가
                return `${this.protocol}://${this.host}/api/v1${path}`;
            },
            getCommonHeaders: function () {
                // 모든 API 호출에 공통으로 사용할 헤더들
                const headers = {
                    'Content-Type': 'application/json'
                };

                // ngrok 환경에서는 브라우저 경고 스킵 헤더 추가
                if (this.host.includes('ngrok')) {
                    headers['ngrok-skip-browser-warning'] = 'true';
                }

                return headers;
            }
        };

        // 개발 환경 체크는 유지하되 로그 출력은 제거
    }

    // 설정 초기화 실행
    initBackendConfig();

})();