/* eslint-disable */
/**
 * Freshdesk AI Copilot - Ticket Field Analysis App
 *
 * SSE Streaming Architecture for real-time progressive rendering
 * CommonJS structure (FDK requirement)
 *
 * @version 2.0.0
 */

// =============================================================================
// [1] CONSTANTS & CONFIG
// =============================================================================

const API_BASE = 'https://ameer-timberless-paragogically.ngrok-free.dev';

const STANDARD_FIELDS = [
  'status', 'priority', 'type', 'group_id', 'responder_id',
  'description', 'subject', 'source', 'tags'
];

const NUMERIC_FIELDS = ['priority', 'status', 'group_id', 'responder_id', 'source'];

// =============================================================================
// [2] STATE MANAGEMENT
// =============================================================================

const state = {
  client: null,
  ticketData: null,
  ticketFields: null,
  sessionId: null,
  isLoading: false,
  currentProposalId: null,
  // Nested field caches (per messageId)
  nestedFieldCache: {}
};

// =============================================================================
// [3] UTILITY FUNCTIONS
// =============================================================================

function generateMessageId() {
  return 'msg-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);
}

function escapeHtml(text) {
  if (!text) return '';
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function getHeaders() {
  const iparam = state.client?.iparams || {};
  return {
    'Content-Type': 'application/json',
    'X-Tenant-ID': iparam.freshdesk_domain?.split('.')[0] || '',
    'X-Platform': 'freshdesk',
    'X-Freshdesk-Domain': iparam.freshdesk_domain || '',
    'X-Freshdesk-API-Key': iparam.freshdesk_api_key || ''
  };
}

function showNotify(type, message) {
  if (state.client) {
    state.client.interface.trigger('showNotify', { type, message });
  } else {
    console.log(`[${type}] ${message}`);
  }
}

// =============================================================================
// [4] NESTED FIELD MANAGER
// =============================================================================

const NestedFieldManager = {
  /**
   * Initialize nested field data for a specific message
   */
  init(messageId, fieldName, rawChoices, nestedFields) {
    const normalized = this.normalizeChoices(rawChoices);
    const pathMap = this.buildPathMap(normalized);
    const leafOptions = this.flattenLeafOptions(normalized);

    state.nestedFieldCache[messageId] = state.nestedFieldCache[messageId] || {};
    state.nestedFieldCache[messageId][fieldName] = {
      choices: normalized,
      pathMap: pathMap,
      leafOptions: leafOptions,
      nestedFields: nestedFields
    };

    return { normalized, pathMap, leafOptions };
  },

  /**
   * Get cached data for a nested field
   */
  getCache(messageId, fieldName) {
    return state.nestedFieldCache[messageId]?.[fieldName];
  },

  /**
   * Normalize choices from Freshdesk format to tree structure
   * Input: { "Cat1": { "Sub1": ["Item1", "Item2"] } }
   * Output: [{ value: "Cat1", choices: [{ value: "Sub1", choices: [...] }] }]
   */
  normalizeChoices(choices) {
    if (!choices) return [];

    // Already normalized array
    if (Array.isArray(choices)) {
      return choices.map(item => {
        if (typeof item === 'string') {
          return { value: item, choices: [] };
        }
        if (item.value !== undefined) {
          return {
            value: item.value,
            choices: this.normalizeChoices(item.choices)
          };
        }
        return { value: String(item), choices: [] };
      });
    }

    // Object format { key: value }
    if (typeof choices === 'object') {
      return Object.entries(choices).map(([key, val]) => ({
        value: key,
        choices: this.normalizeChoices(val)
      }));
    }

    return [];
  },

  /**
   * Build value -> path mapping for reverse lookup
   * Returns: { "Item1": ["Cat1", "Sub1", "Item1"], ... }
   */
  buildPathMap(choices, path = [], map = {}) {
    for (const item of choices) {
      const currentPath = [...path, item.value];

      if (!item.choices || item.choices.length === 0) {
        // Leaf node - store full path
        map[item.value] = currentPath;
      } else {
        // Non-leaf - recurse
        this.buildPathMap(item.choices, currentPath, map);
      }
    }
    return map;
  },

  /**
   * Flatten all leaf options for search
   * Returns: [{ value: "Item1", label: "Cat1 / Sub1 / Item1" }, ...]
   */
  flattenLeafOptions(choices, path = [], acc = []) {
    for (const item of choices) {
      const currentPath = [...path, item.value];

      if (!item.choices || item.choices.length === 0) {
        acc.push({
          value: item.value,
          label: currentPath.join(' / ')
        });
      } else {
        this.flattenLeafOptions(item.choices, currentPath, acc);
      }
    }
    return acc;
  },

  /**
   * Get choices for a specific level
   */
  getChoicesForLevel(choices, level, parentValues = []) {
    if (level === 1) return choices;

    let current = choices;
    for (let i = 0; i < parentValues.length && i < level - 1; i++) {
      const parent = current.find(c => c.value === parentValues[i]);
      current = parent?.choices || [];
    }
    return current;
  },

  /**
   * Sync from Level 1 change (forward direction)
   */
  syncFromLevel1(messageId, fieldName, val1) {
    const cache = this.getCache(messageId, fieldName);
    if (!cache) return;

    const { choices } = cache;
    const el2 = document.getElementById(`input-${fieldName}-${messageId}-2`);
    const el3 = document.getElementById(`input-${fieldName}-${messageId}-3`);

    // Update Level 2 options
    const level2Choices = this.getChoicesForLevel(choices, 2, [val1]);
    if (el2) {
      el2.innerHTML = this.buildSelectOptions(level2Choices);
      el2.disabled = !val1;
      el2.value = '';
    }

    // Reset Level 3
    if (el3) {
      el3.innerHTML = '<option value="">선택하세요</option>';
      el3.disabled = true;
      el3.value = '';
    }
  },

  /**
   * Sync from Level 2 change (forward direction)
   */
  syncFromLevel2(messageId, fieldName, val1, val2) {
    const cache = this.getCache(messageId, fieldName);
    if (!cache) return;

    const { choices } = cache;
    const el3 = document.getElementById(`input-${fieldName}-${messageId}-3`);

    // Update Level 3 options
    const level3Choices = this.getChoicesForLevel(choices, 3, [val1, val2]);
    if (el3) {
      el3.innerHTML = this.buildSelectOptions(level3Choices);
      el3.disabled = !val2;
      el3.value = '';
    }
  },

  /**
   * Sync from Level 3 selection (reverse direction)
   * This is the KEY fix: directly set innerHTML then value
   */
  syncFromLevel3(messageId, fieldName, val3) {
    const cache = this.getCache(messageId, fieldName);
    if (!cache) return;

    const { choices, pathMap } = cache;
    const path = pathMap[val3];

    if (!path || path.length < 3) {
      console.warn('Path not found for value:', val3);
      return;
    }

    const [targetVal1, targetVal2, targetVal3] = path;

    const el1 = document.getElementById(`input-${fieldName}-${messageId}-1`);
    const el2 = document.getElementById(`input-${fieldName}-${messageId}-2`);
    const el3 = document.getElementById(`input-${fieldName}-${messageId}-3`);

    // Step 1: Set Level 1 and regenerate Level 2 options
    if (el1) {
      el1.value = targetVal1;

      // Regenerate Level 2 options
      const level2Choices = this.getChoicesForLevel(choices, 2, [targetVal1]);
      if (el2) {
        el2.innerHTML = this.buildSelectOptions(level2Choices);
        el2.disabled = false;
        el2.value = targetVal2;

        // Regenerate Level 3 options
        const level3Choices = this.getChoicesForLevel(choices, 3, [targetVal1, targetVal2]);
        if (el3) {
          el3.innerHTML = this.buildSelectOptions(level3Choices);
          el3.disabled = false;
          el3.value = targetVal3;
        }
      }
    }
  },

  /**
   * Build select options HTML
   */
  buildSelectOptions(choices) {
    let html = '<option value="">선택하세요</option>';
    for (const item of choices) {
      html += `<option value="${escapeHtml(item.value)}">${escapeHtml(item.value)}</option>`;
    }
    return html;
  },

  /**
   * Collect values from nested field selects
   */
  collectValues(messageId, fieldName) {
    const cache = this.getCache(messageId, fieldName);
    if (!cache) return {};

    const { nestedFields } = cache;
    const values = {};

    for (const nf of nestedFields) {
      const el = document.getElementById(`input-${nf.name}-${messageId}-${nf.level}`);
      if (el && el.value) {
        values[nf.name] = el.value;
      }
    }

    return values;
  },

  /**
   * Render nested field UI (3 selects + search)
   */
  render(messageId, fieldName, nestedRoot, initialValues = {}) {
    const { choices, nested_ticket_fields } = nestedRoot;
    const { normalized, pathMap, leafOptions } = this.init(
      messageId, fieldName, choices, nested_ticket_fields
    );

    const level1Field = nested_ticket_fields?.find(f => f.level === 1);
    const level2Field = nested_ticket_fields?.find(f => f.level === 2);
    const level3Field = nested_ticket_fields?.find(f => f.level === 3);

    const val1 = initialValues[level1Field?.name] || '';
    const val2 = initialValues[level2Field?.name] || '';
    const val3 = initialValues[level3Field?.name] || '';

    const level1Choices = this.getChoicesForLevel(normalized, 1, []);
    const level2Choices = val1 ? this.getChoicesForLevel(normalized, 2, [val1]) : [];
    const level3Choices = val2 ? this.getChoicesForLevel(normalized, 3, [val1, val2]) : [];

    const searchInputId = `search-${fieldName}-${messageId}`;
    const datalistId = `datalist-${fieldName}-${messageId}`;

    return `
      <div class="nested-field-container space-y-2">
        <!-- Level 1 -->
        <div>
          <label class="text-xs text-gray-500">${escapeHtml(level1Field?.label || 'Level 1')}</label>
          <select
            id="input-${level1Field?.name || fieldName}-${messageId}-1"
            data-field-name="${escapeHtml(level1Field?.name || fieldName)}"
            data-level="1"
            onchange="NestedFieldManager.syncFromLevel1('${messageId}', '${fieldName}', this.value)"
            class="w-full px-2 py-1 text-sm border rounded"
          >
            ${this.buildSelectOptions(level1Choices)}
          </select>
        </div>

        <!-- Level 2 -->
        <div>
          <label class="text-xs text-gray-500">${escapeHtml(level2Field?.label || 'Level 2')}</label>
          <select
            id="input-${level2Field?.name || fieldName}-${messageId}-2"
            data-field-name="${escapeHtml(level2Field?.name || fieldName)}"
            data-level="2"
            onchange="NestedFieldManager.syncFromLevel2('${messageId}', '${fieldName}',
              document.getElementById('input-${level1Field?.name || fieldName}-${messageId}-1').value, this.value)"
            class="w-full px-2 py-1 text-sm border rounded"
            ${!val1 ? 'disabled' : ''}
          >
            ${this.buildSelectOptions(level2Choices)}
          </select>
        </div>

        <!-- Level 3 -->
        <div>
          <label class="text-xs text-gray-500">${escapeHtml(level3Field?.label || 'Level 3')}</label>
          <select
            id="input-${level3Field?.name || fieldName}-${messageId}-3"
            data-field-name="${escapeHtml(level3Field?.name || fieldName)}"
            data-level="3"
            onchange="NestedFieldManager.syncFromLevel3('${messageId}', '${fieldName}', this.value)"
            class="w-full px-2 py-1 text-sm border rounded"
            ${!val2 ? 'disabled' : ''}
          >
            ${this.buildSelectOptions(level3Choices)}
          </select>
        </div>

        <!-- Quick Search -->
        <div class="flex gap-2 mt-2">
          <input
            type="text"
            id="${searchInputId}"
            list="${datalistId}"
            placeholder="3단계 빠른 검색..."
            class="flex-1 px-2 py-1 text-sm border rounded"
          />
          <button
            type="button"
            onclick="handleLeafSearch('${messageId}', '${fieldName}', '${searchInputId}')"
            class="px-3 py-1 text-sm bg-blue-500 text-white rounded hover:bg-blue-600"
          >적용</button>
          <datalist id="${datalistId}">
            ${leafOptions.slice(0, 500).map(opt =>
              `<option value="${escapeHtml(opt.value)}" label="${escapeHtml(opt.label)}"></option>`
            ).join('')}
          </datalist>
        </div>
      </div>
    `;
  }
};

// Global reference for onclick handlers
window.NestedFieldManager = NestedFieldManager;

/**
 * Handle leaf search apply button
 */
function handleLeafSearch(messageId, fieldName, inputId) {
  const cache = NestedFieldManager.getCache(messageId, fieldName);
  if (!cache) return;

  const input = document.getElementById(inputId);
  if (!input) return;

  const userInput = input.value.trim();
  const { leafOptions } = cache;

  // Find exact match
  const match = leafOptions.find(opt =>
    opt.value === userInput || opt.label.toLowerCase().includes(userInput.toLowerCase())
  );

  if (!match) {
    input.classList.add('ring-2', 'ring-red-400');
    setTimeout(() => input.classList.remove('ring-2', 'ring-red-400'), 800);
    return;
  }

  // Apply reverse sync
  NestedFieldManager.syncFromLevel3(messageId, fieldName, match.value);
  input.classList.remove('ring-2', 'ring-red-400');
  input.value = match.value;
}

window.handleLeafSearch = handleLeafSearch;

// =============================================================================
// [5] STREAM CLIENT (Fetch + ReadableStream)
// =============================================================================

const StreamClient = {
  /**
   * Process SSE stream from fetch response (based on project-a pattern)
   */
  async processStream(response, onData) {
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let isProcessing = false;
    let firstEventDelivered = false;

    const processBuffer = () => {
      if (buffer.length === 0) {
        isProcessing = false;
        return;
      }

      const lines = buffer.split('\n');
      buffer = lines.pop() || ''; // Keep incomplete line

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const dataStr = line.slice(6);
          if (dataStr === '[DONE]') continue;
          try {
            const data = JSON.parse(dataStr);
            if (onData) onData(data);
          } catch (e) {
            console.error('❌ JSON parse error:', e, 'Raw data:', dataStr);
          }
        }
      }

      requestAnimationFrame(processBuffer);
    };

    const startProcessing = () => {
      if (!isProcessing) {
        isProcessing = true;
        requestAnimationFrame(processBuffer);
      }
    };

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) {
          if (buffer.length > 0) {
            startProcessing();
          }
          break;
        }
        const chunkText = decoder.decode(value, { stream: true });
        buffer += chunkText;

        // First complete event is parsed immediately (no rAF delay)
        if (!firstEventDelivered) {
          const newlineIdx = buffer.indexOf('\n');
          if (newlineIdx !== -1) {
            const line = buffer.slice(0, newlineIdx);
            const rest = buffer.slice(newlineIdx + 1);
            if (line.startsWith('data: ')) {
              const dataStr = line.slice(6);
              if (dataStr !== '[DONE]') {
                try {
                  const data = JSON.parse(dataStr);
                  if (onData) onData(data);
                } catch (e) {
                  console.error('❌ JSON parse error (first event):', e, 'Raw data:', dataStr);
                }
              }
              firstEventDelivered = true;
              buffer = rest; // Rest goes to normal batch path
            }
          }
        }
        startProcessing();
      }
    } catch (error) {
      console.error('Stream read error:', error);
    } finally {
      reader.releaseLock();
    }
  },

  /**
   * Analyze ticket with SSE streaming using fetch (real streaming)
   */
  async analyzeTicket(ticketData, ticketFields, handlers) {
    const payload = {
      ticket_id: String(ticketData.id),
      subject: ticketData.subject || '',
      description: ticketData.description_text || ticketData.description || '',
      priority: ticketData.priority,
      status: ticketData.status,
      tags: ticketData.tags || [],
      ticket_fields: ticketFields || []
    };

    console.log('[StreamClient] Starting SSE stream with payload:', payload);

    try {
      const iparam = state.client?.iparams || {};
      const response = await fetch(`${API_BASE}/api/assist/analyze/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Tenant-ID': iparam.freshdesk_domain?.split('.')[0] || '',
          'X-Platform': 'freshdesk',
          'X-Freshdesk-Domain': iparam.freshdesk_domain || '',
          'X-Freshdesk-API-Key': iparam.freshdesk_api_key || '',
          'ngrok-skip-browser-warning': 'true'  // Skip ngrok browser warning
        },
        body: JSON.stringify(payload)
      });

      console.log('[StreamClient] Response status:', response.status);

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      // Use the processStream method for real streaming
      await this.processStream(response, (data) => {
        console.log('[StreamClient] Event:', data.type);

        switch (data.type) {
          case 'started':
            state.currentProposalId = data.data?.proposalId;
            handlers.onStarted?.(data.data);
            break;
          case 'searching':
            handlers.onSearching?.(data.data);
            break;
          case 'search_result':
            handlers.onSearchResult?.(data.data);
            break;
          case 'analyzing':
            handlers.onAnalyzing?.(data.data);
            break;
          case 'field_proposal':
            handlers.onFieldProposal?.(data.data);
            break;
          case 'synthesizing':
            handlers.onSynthesizing?.(data.data);
            break;
          case 'draft_response':
            handlers.onDraftResponse?.(data.data);
            break;
          case 'complete':
            handlers.onComplete?.(data.data);
            break;
          case 'error':
            handlers.onError?.(data.data);
            break;
          default:
            console.log('[StreamClient] Unknown event type:', data.type, data);
        }
      });

    } catch (error) {
      console.error('[StreamClient] Stream error:', error);
      handlers.onError?.({ message: error.message || String(error) });
    }
  }
};

// =============================================================================
// [6] UI RENDERERS
// =============================================================================

const UIRenderer = {
  elements: {},

  /**
   * Cache DOM elements
   */
  cacheElements() {
    this.elements = {
      chatContainer: document.getElementById('chatContainer'),
      chatInput: document.getElementById('chatInput'),
      sendButton: document.getElementById('sendBtn'),
      analyzeButton: document.getElementById('analyzeBtn'),
      loadingIndicator: document.getElementById('loading-indicator')
    };
  },

  /**
   * Show loading state
   */
  showLoading(message = '분석 중...') {
    state.isLoading = true;
    if (this.elements.analyzeButton) {
      this.elements.analyzeButton.disabled = true;
      this.elements.analyzeButton.textContent = message;
    }
    if (this.elements.loadingIndicator) {
      this.elements.loadingIndicator.classList.remove('hidden');
    }
  },

  /**
   * Hide loading state
   */
  hideLoading() {
    state.isLoading = false;
    if (this.elements.analyzeButton) {
      this.elements.analyzeButton.disabled = false;
      this.elements.analyzeButton.textContent = '티켓 분석';
    }
    if (this.elements.loadingIndicator) {
      this.elements.loadingIndicator.classList.add('hidden');
    }
  },

  /**
   * Add message to chat container
   */
  addMessage(html, type = 'assistant') {
    const container = this.elements.chatContainer;
    if (!container) return null;

    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}-message mb-4`;
    messageDiv.innerHTML = html;
    container.appendChild(messageDiv);
    container.scrollTop = container.scrollHeight;

    return messageDiv;
  },

  /**
   * Create analysis progress UI
   */
  createAnalysisContainer(messageId) {
    return `
      <div id="${messageId}" class="analysis-container bg-white rounded-lg shadow p-4">
        <div class="analysis-header flex items-center justify-between mb-4">
          <h3 class="text-lg font-semibold">🔍 티켓 분석</h3>
          <span id="${messageId}-status" class="text-sm text-gray-500">시작 중...</span>
        </div>

        <!-- Progress Steps -->
        <div id="${messageId}-progress" class="progress-steps mb-4">
          <div class="flex items-center space-x-2 text-sm text-gray-400">
            <span id="${messageId}-step-search" class="step">📄 검색</span>
            <span>→</span>
            <span id="${messageId}-step-analyze" class="step">🧠 분석</span>
            <span>→</span>
            <span id="${messageId}-step-synthesize" class="step">✨ 생성</span>
          </div>
        </div>

        <!-- Field Proposals Container -->
        <div id="${messageId}-fields" class="field-proposals space-y-2">
          <div class="text-sm text-gray-500">필드 제안 대기 중...</div>
        </div>

        <!-- Draft Response Container -->
        <div id="${messageId}-response" class="draft-response mt-4 hidden">
          <h4 class="text-sm font-medium text-gray-700 mb-2">📝 응답 초안</h4>
          <div id="${messageId}-response-text" class="p-3 bg-gray-50 rounded text-sm"></div>
        </div>

        <!-- Apply Button -->
        <div id="${messageId}-actions" class="actions mt-4 hidden">
          <button
            onclick="applyFieldUpdates('${messageId}')"
            class="w-full py-2 bg-green-600 text-white rounded hover:bg-green-700"
          >
            변경 사항 적용하기
          </button>
        </div>
      </div>
    `;
  },

  /**
   * Update progress step
   */
  updateProgressStep(messageId, step, status = 'active') {
    const stepEl = document.getElementById(`${messageId}-step-${step}`);
    if (stepEl) {
      stepEl.classList.remove('text-gray-400', 'text-blue-500', 'text-green-500');
      if (status === 'active') {
        stepEl.classList.add('text-blue-500');
        stepEl.innerHTML = stepEl.innerHTML.replace(/^[^\s]+/, '⏳');
      } else if (status === 'complete') {
        stepEl.classList.add('text-green-500');
        stepEl.innerHTML = stepEl.innerHTML.replace(/^[^\s]+/, '✅');
      }
    }
  },

  /**
   * Update status text
   */
  updateStatus(messageId, text) {
    const statusEl = document.getElementById(`${messageId}-status`);
    if (statusEl) {
      statusEl.textContent = text;
    }
  },

  /**
   * Render single field proposal (called progressively)
   */
  renderFieldProposal(messageId, fieldData) {
    const container = document.getElementById(`${messageId}-fields`);
    if (!container) return;

    // Remove placeholder on first field
    const placeholder = container.querySelector('.text-gray-500');
    if (placeholder) {
      placeholder.remove();
    }

    const { fieldName, fieldLabel, proposedValue, reason } = fieldData;

    // Check if this is a nested field
    const nestedRoot = state.ticketFields?.find(f => f.type === 'nested_field');
    const isNestedField = nestedRoot && (
      nestedRoot.name === fieldName ||
      nestedRoot.nested_ticket_fields?.some(nf => nf.name === fieldName)
    );

    let inputHtml;

    if (isNestedField) {
      // Render nested field with initial value
      const initialValues = {};
      const level3Field = nestedRoot.nested_ticket_fields?.find(f => f.level === 3);
      if (level3Field) {
        initialValues[level3Field.name] = proposedValue;
      }
      inputHtml = NestedFieldManager.render(messageId, nestedRoot.name, nestedRoot, initialValues);

      // Trigger reverse sync after render
      setTimeout(() => {
        if (proposedValue) {
          NestedFieldManager.syncFromLevel3(messageId, nestedRoot.name, proposedValue);
        }
      }, 100);
    } else {
      // Check for dropdown choices
      const fieldDef = state.ticketFields?.find(f => f.name === fieldName);
      const choices = fieldDef?.choices;

      if (choices && Array.isArray(choices)) {
        // Dropdown
        inputHtml = `
          <select
            id="input-${fieldName}-${messageId}"
            data-field-name="${escapeHtml(fieldName)}"
            class="w-full px-2 py-1 text-sm border rounded"
          >
            <option value="">선택하세요</option>
            ${choices.map(c => {
              const val = typeof c === 'object' ? c.value || c.id : c;
              const label = typeof c === 'object' ? c.label || c.value : c;
              const selected = String(val) === String(proposedValue) ? 'selected' : '';
              return `<option value="${escapeHtml(val)}" ${selected}>${escapeHtml(label)}</option>`;
            }).join('')}
          </select>
        `;
      } else {
        // Text input
        inputHtml = `
          <input
            type="text"
            id="input-${fieldName}-${messageId}"
            data-field-name="${escapeHtml(fieldName)}"
            value="${escapeHtml(proposedValue || '')}"
            class="w-full px-2 py-1 text-sm border rounded"
          />
        `;
      }
    }

    const fieldHtml = `
      <div class="field-proposal p-3 bg-gray-50 rounded border-l-4 border-blue-500 animate-fade-in">
        <div class="flex justify-between items-start">
          <div class="flex-1">
            <div class="font-medium text-sm">${escapeHtml(fieldLabel || fieldName)}</div>
            <div class="text-xs text-gray-500 mt-1">${escapeHtml(reason || '')}</div>
          </div>
        </div>
        <div class="mt-2">
          ${inputHtml}
        </div>
      </div>
    `;

    container.insertAdjacentHTML('beforeend', fieldHtml);
  },

  /**
   * Render draft response
   */
  renderDraftResponse(messageId, text) {
    const container = document.getElementById(`${messageId}-response`);
    const textEl = document.getElementById(`${messageId}-response-text`);

    if (container && textEl) {
      container.classList.remove('hidden');
      textEl.textContent = text;
    }
  },

  /**
   * Show action buttons
   */
  showActions(messageId) {
    const actions = document.getElementById(`${messageId}-actions`);
    if (actions) {
      actions.classList.remove('hidden');
    }
  }
};

// =============================================================================
// [7] FIELD APPLICATOR
// =============================================================================

async function applyFieldUpdates(messageId) {
  const { client, ticketData, ticketFields } = state;
  if (!client || !ticketData) {
    showNotify('danger', 'FDK 클라이언트가 초기화되지 않았습니다.');
    return;
  }

  try {
    const container = document.getElementById(messageId);
    if (!container) {
      throw new Error('메시지 컨테이너를 찾을 수 없습니다.');
    }

    // Get nested field info
    const nestedRoot = ticketFields?.find(f => f.type === 'nested_field');
    const nestedFieldNames = new Set();
    if (nestedRoot) {
      nestedFieldNames.add(nestedRoot.name);
      (nestedRoot.nested_ticket_fields || []).forEach(nf => nestedFieldNames.add(nf.name));
    }

    const updateBody = {};
    const customFields = {};

    // Collect regular field values
    const inputs = container.querySelectorAll('[data-field-name]');
    const processedFields = new Set();

    inputs.forEach(input => {
      const fieldName = input.dataset.fieldName;
      const level = input.dataset.level;

      // Skip if already processed or nested field (handled separately)
      if (processedFields.has(fieldName) && !level) return;

      const value = input.value;
      if (!value) return;

      if (nestedFieldNames.has(fieldName) && level) {
        // Nested field - always goes to custom_fields
        customFields[fieldName] = value;
      } else if (STANDARD_FIELDS.includes(fieldName)) {
        // Standard field
        if (NUMERIC_FIELDS.includes(fieldName)) {
          updateBody[fieldName] = parseInt(value, 10);
        } else {
          updateBody[fieldName] = value;
        }
      } else {
        // Custom field
        customFields[fieldName] = value;
      }

      processedFields.add(fieldName);
    });

    if (Object.keys(customFields).length > 0) {
      updateBody.custom_fields = customFields;
    }

    if (Object.keys(updateBody).length === 0) {
      showNotify('warning', '변경할 필드 값이 없습니다.');
      return;
    }

    console.log('Updating ticket with:', updateBody);

    // Call Freshdesk API via FDK
    const response = await client.request.invokeTemplate('updateTicket', {
      context: { ticketId: ticketData.id },
      body: JSON.stringify(updateBody)
    });

    if (response.status === 200) {
      showNotify('success', '티켓이 성공적으로 업데이트되었습니다.');

      // Disable button after success
      const button = container.querySelector('button[onclick*="applyFieldUpdates"]');
      if (button) {
        button.disabled = true;
        button.textContent = '✅ 적용 완료';
        button.classList.remove('bg-green-600', 'hover:bg-green-700');
        button.classList.add('bg-gray-400', 'cursor-not-allowed');
      }
    } else {
      throw new Error(`API Error: ${response.status}`);
    }

  } catch (error) {
    console.error('필드 업데이트 실패:', error);
    showNotify('danger', '필드 업데이트 중 오류가 발생했습니다: ' + error.message);
  }
}

window.applyFieldUpdates = applyFieldUpdates;

// =============================================================================
// [8] ANALYSIS HANDLER
// =============================================================================

async function handleAnalyzeTicket() {
  console.log('🔥 [handleAnalyzeTicket] Function called');
  console.log('🔥 [handleAnalyzeTicket] isLoading:', state.isLoading);
  console.log('🔥 [handleAnalyzeTicket] ticketData:', state.ticketData ? 'Present' : 'Missing');

  if (state.isLoading) return;

  const { ticketData, ticketFields } = state;
  if (!ticketData) {
    showNotify('warning', '티켓 데이터가 없습니다.');
    return;
  }

  const messageId = generateMessageId();

  UIRenderer.showLoading('분석 중...');

  // Create analysis container
  const containerHtml = UIRenderer.createAnalysisContainer(messageId);
  UIRenderer.addMessage(containerHtml, 'assistant');

  try {
    await StreamClient.analyzeTicket(ticketData, ticketFields, {
      onStarted: (data) => {
        UIRenderer.updateStatus(messageId, `분석 시작 (ID: ${data.proposalId?.slice(0, 8)}...)`);
      },

      onSearching: (data) => {
        UIRenderer.updateStatus(messageId, data.message);
        UIRenderer.updateProgressStep(messageId, 'search', 'active');
      },

      onSearchResult: (data) => {
        UIRenderer.updateProgressStep(messageId, 'search', 'complete');
        console.log('Search results:', data);
      },

      onAnalyzing: (data) => {
        UIRenderer.updateStatus(messageId, data.message);
        UIRenderer.updateProgressStep(messageId, 'analyze', 'active');
      },

      onFieldProposal: (data) => {
        UIRenderer.renderFieldProposal(messageId, data);
      },

      onSynthesizing: (data) => {
        UIRenderer.updateStatus(messageId, data.message);
        UIRenderer.updateProgressStep(messageId, 'analyze', 'complete');
        UIRenderer.updateProgressStep(messageId, 'synthesize', 'active');
      },

      onDraftResponse: (data) => {
        UIRenderer.renderDraftResponse(messageId, data.text);
      },

      onComplete: (data) => {
        UIRenderer.updateProgressStep(messageId, 'synthesize', 'complete');
        UIRenderer.updateStatus(messageId, '✅ 분석 완료');
        UIRenderer.showActions(messageId);
        UIRenderer.hideLoading();
      },

      onError: (data) => {
        UIRenderer.updateStatus(messageId, `❌ 오류: ${data.message}`);
        UIRenderer.hideLoading();
        showNotify('danger', '분석 중 오류가 발생했습니다: ' + data.message);
      }
    });

  } catch (error) {
    console.error('Analysis error:', error);
    UIRenderer.updateStatus(messageId, `❌ 오류: ${error.message}`);
    UIRenderer.hideLoading();
    showNotify('danger', '분석 중 오류가 발생했습니다.');
  }
}

window.handleAnalyzeTicket = handleAnalyzeTicket;

// =============================================================================
// [9] INITIALIZATION
// =============================================================================

async function loadTicketData(client) {
  try {
    const data = await client.data.get('ticket');
    state.ticketData = data.ticket;

    // Load conversations
    try {
      const convData = await client.data.get('ticket.conversations');
      state.ticketData.conversations = convData.conversations || [];
    } catch (e) {
      console.warn('Could not load conversations:', e);
    }

    console.log('Ticket data loaded:', state.ticketData.id);
    return state.ticketData;
  } catch (error) {
    console.error('Failed to load ticket data:', error);
    throw error;
  }
}

async function loadTicketFields(client) {
  try {
    const response = await client.request.invokeTemplate('getTicketFields', {});
    const fields = JSON.parse(response.response);
    state.ticketFields = fields;
    console.log('Ticket fields loaded:', fields.length);
    return fields;
  } catch (error) {
    console.error('Failed to load ticket fields:', error);
    return [];
  }
}

console.log('[AI Copilot] app.js loaded (v2.0.0 - SSE Streaming)');

let isModalView = false;

document.onreadystatechange = function() {
  if (document.readyState === "complete") {
    if (typeof app !== 'undefined') {
      app.initialized().then(async function(_client) {
        state.client = _client;
        const context = await _client.instance.context();
        isModalView = context.location !== 'ticket_top_navigation';

        console.log('[AI Copilot] Initialized at:', context.location, 'isModalView:', isModalView);

        // 메인 페이지: 클릭시 모달 열기
        if (!isModalView) {
          _client.events.on("app.activated", async () => {
            console.log('[AI Copilot] Opening modal...');
            await _client.interface.trigger("showModal", {
              title: "AI Copilot",
              template: "index.html",
              noBackdrop: true
            });
          });
          return;
        }

        // 모달 뷰: 비즈니스 로직 실행
        console.log('[AI Copilot] Initializing modal view...');

        UIRenderer.cacheElements();

        // Load data
        console.log('[AI Copilot] Loading ticket data...');
        await loadTicketData(_client);
        console.log('[AI Copilot] Ticket data loaded:', state.ticketData?.id);

        console.log('[AI Copilot] Loading ticket fields...');
        await loadTicketFields(_client);
        console.log('[AI Copilot] Ticket fields loaded:', state.ticketFields?.length, 'fields');

        // Setup event listeners
        const analyzeButton = document.getElementById('analyzeBtn');
        if (analyzeButton) {
          analyzeButton.addEventListener('click', handleAnalyzeTicket);
          console.log('[AI Copilot] Analyze button handler attached');
        } else {
          console.error('[AI Copilot] Analyze button not found!');
        }

        console.log('[AI Copilot] Modal initialization complete');

      }).catch(function(error) {
        console.error("[AI Copilot] FDK 초기화 실패:", error);
      });
    } else {
      console.error("[AI Copilot] FDK app 객체가 없습니다.");
    }
  }
};
