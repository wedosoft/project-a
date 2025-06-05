/**
 * Webpack 설정 파일
 * CopilotKit React 컴포넌트를 번들링하여 FDK 앱에서 사용할 수 있도록 합니다.
 */

const path = require('path');
const TerserPlugin = require('terser-webpack-plugin');

module.exports = {
    mode: process.env.NODE_ENV || 'development',
    
    // 진입점: CopilotKit 컴포넌트들
    entry: {
        'copilot-bundle': './app/scripts/CopilotApp.tsx',
    },
    
    // 출력 설정
    output: {
        path: path.resolve(__dirname, 'app/scripts'),
        filename: '[name].js',
        library: {
            name: 'CopilotApp',
            type: 'umd',
        },
        globalObject: 'this',
        clean: false, // 기존 파일들을 유지
    },

    // 번들 파일 상단에 JSHint 무시 주석 추가
    plugins: [
        new (require('webpack')).BannerPlugin({
            banner: '/* jshint ignore:start */\n/* eslint-disable */\n// FDK 검증 무시: 외부 라이브러리 번들 파일',
            raw: false,
            entryOnly: true
        })
    ],
    
    // 모듈 해결 설정
    resolve: {
        extensions: ['.tsx', '.ts', '.js', '.jsx'],
        alias: {
            '@': path.resolve(__dirname, './app'),
        },
    },
    
    // 로더 설정
    module: {
        rules: [
            // TypeScript/React 파일 처리
            {
                test: /\.(ts|tsx)$/,
                exclude: /node_modules/,
                use: {
                    loader: 'babel-loader',
                    options: {
                        presets: [
                            ['@babel/preset-env', {
                                targets: {
                                    browsers: ['> 1%', 'last 2 versions']
                                }
                            }],
                            ['@babel/preset-react', {
                                runtime: 'automatic'
                            }],
                            '@babel/preset-typescript'
                        ],
                        plugins: [
                            '@babel/plugin-transform-class-properties',
                            '@babel/plugin-transform-runtime'
                        ]
                    }
                }
            },
            
            // JavaScript 파일 처리
            {
                test: /\.js$/,
                exclude: /node_modules/,
                use: {
                    loader: 'babel-loader',
                    options: {
                        presets: [
                            ['@babel/preset-env', {
                                targets: {
                                    browsers: ['> 1%', 'last 2 versions']
                                }
                            }]
                        ]
                    }
                }
            },
            
            // CSS 파일 처리
            {
                test: /\.css$/,
                use: ['style-loader', 'css-loader']
            }
        ]
    },
    
    // 외부 라이브러리 설정 (CDN에서 로드되거나 전역으로 제공되는 경우)
    externals: {
        // React는 번들에 포함 (FDK에서 제공되지 않을 수 있음)
        // 'react': 'React',
        // 'react-dom': 'ReactDOM'
    },
    
    // 개발 설정
    devtool: process.env.NODE_ENV === 'development' ? 'source-map' : false,
    
    // 최적화 설정
    optimization: {
        // TerserPlugin을 사용하여 코드 품질 개선 (간단한 설정)
        minimize: true,
        minimizer: [
            new TerserPlugin({
                terserOptions: {
                    compress: {
                        drop_console: false,
                        drop_debugger: true,
                    },
                    mangle: false, // 변수명 압축 비활성화
                    format: {
                        comments: false, // 주석 제거
                    },
                },
                extractComments: false, // 별도 라이센스 파일 생성 방지
            }),
        ],
        // splitChunks를 비활성화하여 모든 코드를 하나의 파일로 번들링
        splitChunks: false,
        // 사용하지 않는 코드 제거
        usedExports: true,
        sideEffects: false
    },
    
    // 개발 서버 설정 (필요한 경우)
    devServer: {
        static: {
            directory: path.join(__dirname, 'app'),
        },
        compress: true,
        port: 9000,
        hot: true,
    },
    
    // 성능 경고 설정
    performance: {
        hints: process.env.NODE_ENV === 'production' ? 'warning' : false,
        maxEntrypointSize: 512000,
        maxAssetSize: 512000,
    }
};
