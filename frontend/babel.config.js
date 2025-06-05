/**
 * Babel 설정 파일
 * TypeScript와 React JSX를 처리하기 위한 설정
 */

module.exports = {
    presets: [
        // 최신 JavaScript 기능을 지원하기 위한 프리셋
        ['@babel/preset-env', {
            targets: {
                browsers: ['> 1%', 'last 2 versions', 'not dead']
            },
            useBuiltIns: 'usage',
            corejs: 3
        }],
        
        // React JSX 처리를 위한 프리셋
        ['@babel/preset-react', {
            runtime: 'automatic', // React 17+ 자동 JSX 런타임 사용
            development: process.env.NODE_ENV === 'development'
        }],
        
        // TypeScript 처리를 위한 프리셋
        '@babel/preset-typescript'
    ],
    
    plugins: [
        // 클래스 프로퍼티 지원
        '@babel/plugin-transform-class-properties',
        
        // 런타임 헬퍼 최적화
        ['@babel/plugin-transform-runtime', {
            corejs: false,
            helpers: true,
            regenerator: true,
            useESModules: false
        }]
    ],
    
    // 환경별 설정
    env: {
        development: {
            plugins: [
                // 개발 환경에서 React Fast Refresh 지원 (필요한 경우)
            ]
        },
        production: {
            plugins: [
                // 프로덕션 최적화 플러그인들
            ]
        }
    }
};
