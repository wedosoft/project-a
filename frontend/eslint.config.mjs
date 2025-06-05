import js from "@eslint/js";
import pluginReact from "eslint-plugin-react";
import globals from "globals";
import tseslint from "typescript-eslint";

export default [
  {
    files: ["**/*.{js,mjs,cjs,ts,mts,cts,jsx,tsx}"],
    languageOptions: {
      globals: {
        ...globals.browser,
        ...globals.node,
        // Freshdesk SDK 전역 변수들
        app: "readonly",
        client: "writable",
        // React 관련 전역 변수들  
        React: "readonly",
        ReactDOM: "readonly"
      },
      parserOptions: {
        ecmaFeatures: {
          jsx: true
        }
      }
    }
  },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  pluginReact.configs.flat.recommended,
  {
    rules: {
      // React 관련 규칙
      "react/react-in-jsx-scope": "off", // React 17+에서는 불필요
      "react/prop-types": "off", // TypeScript 사용 시 불필요
      
      // TypeScript 관련 규칙
      "@typescript-eslint/no-unused-vars": ["error", { 
        "argsIgnorePattern": "^_",
        "varsIgnorePattern": "^_" 
      }],
      "@typescript-eslint/explicit-function-return-type": "off",
      "@typescript-eslint/no-explicit-any": "warn",
      
      // 일반적인 코드 품질 규칙
      "no-console": ["warn", { "allow": ["error", "warn"] }],
      "prefer-const": "error",
      "no-var": "error"
    },
    settings: {
      react: {
        version: "detect"
      }
    }
  },
  {
    ignores: [
      "node_modules/**",
      "dist/**",
      "build/**",
      "coverage/**",
      "app/scripts/copilot-bundle.js",
      "*.config.js"
    ]
  }
];
