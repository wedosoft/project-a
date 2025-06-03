const path = require('path');

module.exports = {
  entry: './app/scripts/copilot-app.js',
  output: {
    filename: 'copilot-bundle.js',
    path: path.resolve(__dirname, 'app/scripts'),
    libraryTarget: 'umd',
    environment: {
      // ES5 호환성을 위한 모든 ES6+ 기능 비활성화
      arrowFunction: false,
      bigIntLiteral: false,
      const: false,
      destructuring: false,
      dynamicImport: false,
      forOf: false,
      module: false
    }
  },
  mode: 'production',
  // eval 완전 제거
  devtool: false,
  // 프로덕션 번들 최적화
  optimization: {
    minimize: true,
  },
  module: {
    rules: [
      {
        test: /\.(js|jsx)$/,
        exclude: /node_modules/,
        use: {
          loader: 'babel-loader',
          options: {
            presets: ['@babel/preset-env', '@babel/preset-react']
          }
        }
      },
      {
        test: /\.css$/,
        use: ['style-loader', 'css-loader']
      }
    ]
  },
  resolve: {
    extensions: ['.js', '.jsx']
  }
};
