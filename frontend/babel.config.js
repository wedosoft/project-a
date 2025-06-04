module.exports = {
  presets: [
    ['@babel/preset-env', {
      targets: {
        browsers: [
          'ie 11', // IE11 호환성을 위해 ES5 형식 코드 생성
          'ie 10', // 더 오래된 브라우저 호환성 추가
          'last 2 versions',
          'not dead',
          'not < 2%'
        ]
      },
      useBuiltIns: 'usage',
      corejs: 3,
      // 모든 ES6+ 기능 변환 강제
      forceAllTransforms: true
    }],
    ['@babel/preset-react', {
      // 자동 런타임 대신 클래식 JSX 변환 사용
      runtime: 'classic'
    }]
  ],
  plugins: [
    "@babel/plugin-transform-class-properties",
    "@babel/plugin-transform-arrow-functions",
    "@babel/plugin-transform-template-literals",
    "@babel/plugin-transform-destructuring",
    "@babel/plugin-transform-spread"
  ]
};
