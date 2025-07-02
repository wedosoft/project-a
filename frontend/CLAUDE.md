# Frontend FDK Development - CLAUDE.md

## 🎯 Context & Purpose

This is the **Frontend FDK** worktree focused on the Freshdesk Development Kit (FDK) JavaScript application for Copilot Canvas. This frontend provides the user interface for AI-powered ticket analysis within the Freshdesk platform.

**Primary Focus Areas:**
- FDK-based Freshdesk application development
- Modern JavaScript ES6+ with modular architecture
- Real-time UI updates and user interactions
- Backend API integration and state management
- Performance optimization and caching strategies

## 🏗️ Frontend Architecture

### System Overview
```
Freshdesk Platform → FDK App → Backend API → Vector/LLM Processing
     ↓                ↓              ↓
   UI Events     JavaScript     API Responses
```

### Core Modules

1. **Application Core** (`app/`)
   - Main HTML interface (`index.html`)
   - Modular JavaScript architecture
   - CSS styling with modern UI components

2. **JavaScript Modules** (`app/scripts/`)
   - **GlobalState**: Centralized state management system
   - **API**: Backend communication and caching layer
   - **UI**: User interface management and DOM manipulation
   - **Events**: Event handling and user interactions
   - **Data**: Data processing and transformation
   - **Utils**: Utility functions and helpers
   - **DebugTools**: Development and debugging utilities

3. **Configuration** (`config/`)
   - **iparams.html**: Installation parameters UI
   - **requests.json**: API endpoint definitions

### Key Design Patterns

- **Modular Architecture**: Each module has specific responsibilities
- **Event-Driven**: Clean separation between UI events and business logic
- **State Management**: Centralized state with reactive updates
- **Performance First**: Caching, lazy loading, and memory optimization
- **Error Resilience**: Graceful error handling and user feedback

## 🚀 Development Commands

### Environment Setup
```bash
# Install FDK CLI (first time only)
npm install @freshworks/cli -g

# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Start development server
fdk run
```

### Daily Development Workflow
```bash
# Start local development (auto-reload)
fdk run

# Validate app structure
fdk validate

# Package for distribution
fdk pack

# Run tests
npm test

# Generate documentation
npm run docs:generate
npm run docs:serve
```

### Development Server
```bash
# Development mode with live reload
fdk run

# The app will be available at:
# https://your-domain.freshdesk.com/a/tickets/[ticket-id]
# (with ?dev=true parameter)
```

## 📁 Directory Structure

```
frontend/
├── app/                    # Main application files
│   ├── index.html         # Main UI template
│   ├── scripts/           # JavaScript modules
│   │   ├── globals.js     # Global state & module management
│   │   ├── api.js         # Backend API communication
│   │   ├── ui.js          # UI management & DOM manipulation
│   │   ├── events.js      # Event handling system
│   │   ├── data.js        # Data processing & caching
│   │   └── utils.js       # Utility functions
│   └── styles/            # CSS stylesheets & assets
├── config/                # FDK configuration
│   ├── iparams.html      # Installation parameters UI
│   └── requests.json     # API endpoint definitions
├── tests/                # Test suites
├── docs/                 # Generated documentation
└── manifest.json         # FDK app manifest
```

## 🔧 Key Configuration

### Installation Parameters (`config/iparams.html`)
```json
{
  "backendUrl": {
    "display_name": "Backend API URL",
    "description": "URL of the backend API server",
    "type": "text",
    "required": true,
    "default_value": "http://localhost:8000"
  },
  "tenantId": {
    "display_name": "Tenant ID", 
    "description": "Your organization's tenant identifier",
    "type": "text",
    "required": true
  }
}
```

### API Endpoints (`config/requests.json`)
```json
{
  "backendApi": {
    "protocol": "https",
    "host": "<%=iparams.backendUrl%>",
    "endpoints": {
      "init": "/api/init/{{ticket.id}}",
      "query": "/api/query",
      "reply": "/api/reply",
      "search": "/api/search/agent"
    }
  }
}
```

## 🎨 JavaScript Module System

### Global State Management
```javascript
// GlobalState provides centralized state management
const ticketData = GlobalState.getGlobalTicketData();
GlobalState.updateTicketData(newData);

// Module dependency management
ModuleDependencyManager.registerModule('myModule', 5, ['globals', 'utils']);
```

### API Communication
```javascript
// Backend API calls with caching
const result = await API.callBackendAPIWithCache(client, 'init', data, 'POST', {
  useCache: true,
  cacheTTL: 300000, // 5 minutes
  loadingContext: '🎯 AI 분석 중...'
});

// Vector search integration
const searchResults = await API.performAdvancedVectorSearch(client, {
  query: searchQuery,
  filters: { date_range: [startDate, endDate] },
  limit: 20
});
```

### UI Management
```javascript
// Dynamic UI updates
UI.updateTicketSummaryCard(summaryData);
UI.showLoadingState('Analyzing ticket...');
UI.displayError('Connection failed', { retry: true });

// Modal and notification management
UI.showModal(content, { title: 'Analysis Results' });
UI.showNotification('Analysis complete!', 'success');
```

## 🔍 Common Development Tasks

### Adding New Features
```bash
# 1. Create/modify relevant script in app/scripts/
# 2. Update HTML template in app/index.html if needed
# 3. Add CSS styles in app/styles/styles.css
# 4. Register module dependencies
# 5. Test with fdk run
```

### API Integration
```javascript
// Standard pattern for new API calls
async function callNewEndpoint(client, requestData) {
  try {
    const result = await API.callBackendAPIWithCache(
      client, 
      'newEndpoint', 
      requestData, 
      'POST',
      { useCache: false, loadingContext: 'Processing...' }
    );
    
    if (result.ok) {
      UI.updateSomeSection(result.data);
      GlobalState.updateState(result.data);
    } else {
      UI.displayError(result.error);
    }
  } catch (error) {
    console.error('API call failed:', error);
    UI.displayError('Network error occurred');
  }
}
```

### Event Handling
```javascript
// Clean event handling pattern
Events.registerEventHandler('ticket.update', async (eventData) => {
  const analysis = await API.analyzeTicket(client, eventData.ticket.id);
  UI.updateAnalysisResults(analysis);
});

// FDK event integration
app.initialized().then(() => {
  app.events.on('ticket.update', Events.onTicketUpdate);
});
```

## 🎯 User Experience Features

### Real-time Analysis
- Automatic ticket analysis on load
- Progressive loading with visual indicators
- Cached results for improved performance

### Interactive UI Components
- Expandable summary cards
- Similar ticket recommendations
- AI-powered solution suggestions
- Modal dialogs for detailed views

### Performance Optimization
- Lazy loading of heavy components
- Intelligent caching strategy
- Batch API requests
- Memory-efficient DOM manipulation

## 🚨 FDK-Specific Considerations

### Platform Integration
```javascript
// Access Freshdesk data
const ticket = await client.data.get('ticket');
const contact = await client.data.get('contact');

// Trigger Freshdesk actions
await client.interface.trigger('showNotify', {
  type: 'success',
  message: 'Analysis complete!'
});
```

### Security & Permissions
- All API calls go through FDK's secure request system
- Installation parameters are encrypted
- No direct external API calls (must use backend proxy)

### Testing & Debugging
```javascript
// Debug mode detection
if (window.location.hostname === 'localhost' || window.location.search.includes('debug=true')) {
  // Enable debug features
  window.debug = {
    state: () => GlobalState.getGlobalTicketData(),
    modules: () => ModuleDependencyManager.generateStatusReport(),
    perf: () => DebugTools.runPerformanceBenchmark()
  };
}
```

## 📊 Performance Monitoring

### Built-in Performance Tools
```javascript
// Performance benchmarking
const results = await DebugTools.runPerformanceBenchmark();
console.log('Performance Results:', results);

// Memory usage tracking
const memoryReport = DebugTools.getPerformanceReport();
console.log('Memory Usage:', memoryReport);

// Cache optimization
DebugTools.clearAllCaches(); // Reset all caches
```

### Error Handling & Logging
```javascript
// Structured error handling
GlobalState.ErrorHandler.logError(error, {
  context: 'API_CALL',
  ticketId: currentTicket.id,
  userId: currentUser.id
});

// User-friendly error display
UI.displayError('Something went wrong', {
  retry: true,
  details: 'Please try again or contact support'
});
```

## 🔗 Backend Integration

### API Communication Pattern
```javascript
// Standard backend integration
const headers = {
  'X-Tenant-ID': GlobalState.getTenantId(),
  'X-Platform': 'freshdesk',
  'Content-Type': 'application/json'
};

const response = await client.request.invoke('backendApi', {
  url: '/api/endpoint',
  method: 'POST',
  headers: headers,
  body: JSON.stringify(requestData)
});
```

### Data Flow
1. **User Action** → Event handler
2. **Event Handler** → API call preparation
3. **API Module** → Backend communication
4. **Response Processing** → Data transformation
5. **UI Update** → Visual feedback to user
6. **State Management** → Global state update

## 📚 Key Files to Know

- `app/index.html` - Main UI template and structure
- `app/scripts/globals.js` - Global state and module system
- `app/scripts/api.js` - Backend communication layer
- `app/scripts/ui.js` - UI management and DOM manipulation
- `config/iparams.html` - Installation parameter configuration
- `config/requests.json` - API endpoint definitions
- `manifest.json` - FDK app manifest and metadata

## 🔄 Development Workflow

1. **Start Development**: `fdk run` (opens app in Freshdesk)
2. **Make Changes**: Edit files in `app/` directory
3. **Live Reload**: Changes automatically refresh in browser
4. **Test**: Use built-in debug tools and browser dev tools
5. **Validate**: Run `fdk validate` before deployment
6. **Package**: Use `fdk pack` to create deployment package

---

*This worktree focuses exclusively on frontend FDK development. For backend API development, switch to the backend worktree. For documentation updates, use the docs/instructions worktree.*
