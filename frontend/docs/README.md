# 📚 Copilot Canvas - API Documentation

## 🎯 Overview

This project provides comprehensive API documentation for Copilot Canvas frontend modules. The documentation is automatically generated using JSDoc and includes both English and Korean descriptions.

## 🚀 Quick Start

### View Documentation

#### Option 1: Local Server (Recommended)
```bash
cd frontend
npm run docs:serve
```
Then open: http://localhost:8080

#### Option 2: Direct File Access
```bash
open frontend/docs/api/index.html
```

### Generate Documentation
```bash
cd frontend
npm run docs:generate
```

## 📁 Module Structure

- **GlobalState**: Global state management system
- **Utils**: Utility functions library  
- **API**: Backend communication module
- **Events**: Event handling system
- **UI**: User interface management
- **Data**: Data processing and caching
- **DebugTools**: Development and debugging utilities

## 🛠️ Development

### Adding JSDoc Comments
```javascript
/**
 * @description Function description
 * @param {string} param1 - Parameter description
 * @returns {boolean} Return value description
 * @memberof ModuleName
 * @example
 * ModuleName.functionName('example');
 */
function functionName(param1) {
  // implementation
}
```

### Update Documentation
After code changes, regenerate documentation:
```bash
npm run docs:build
```

## 📖 Documentation Features

- ✅ Bilingual support (English/Korean)
- ✅ Interactive navigation
- ✅ Source code viewer
- ✅ Search functionality
- ✅ Type information
- ✅ Usage examples

---

Generated with JSDoc 4.0.4 | Last updated: 2025-06-16
