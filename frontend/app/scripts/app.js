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

// Fields we don't want to propose/update in this task (focus on nested field correctness)
const EXCLUDED_PROPOSAL_FIELDS = new Set([
  // exclude fields that are either not stable across tenants or not in scope
  'status', 'product', 'source', 'group', 'agent', 'group_id', 'responder_id'
]);
const EXCLUDED_UPDATE_FIELDS = new Set([
  'status', 'product', 'source', 'group', 'agent', 'group_id', 'responder_id'
]);

// Only keep these flat (non-nested) fields in UI for now
const ALLOWED_FLAT_FIELDS = new Set(['ticket_type', 'priority']);

// Some Freshdesk Ticket Fields API names differ from Ticket Update payload keys
const FIELD_NAME_ALIASES = {
  ticket_type: 'type'
};

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

function coerceNumericChoiceValue(rawValue, choices) {
  // If already numeric-ish
  const asNum = parseInt(String(rawValue), 10);
  if (Number.isFinite(asNum)) return asNum;

  if (!choices || !Array.isArray(choices)) return null;

  const needle = String(rawValue).trim().toLowerCase();
  const match = choices.find(c => {
    if (typeof c === 'object' && c) {
      const label = (c.label ?? c.value ?? c.name ?? '').toString().trim().toLowerCase();
      const value = (c.value ?? c.id ?? '').toString().trim().toLowerCase();
      return label === needle || value === needle;
    }
    return String(c).trim().toLowerCase() === needle;
  });

  if (!match) return null;

  if (typeof match === 'object' && match) {
    const cand = match.id ?? match.value;
    const n = parseInt(String(cand), 10);
    return Number.isFinite(n) ? n : null;
  }

  const n = parseInt(String(match), 10);
  return Number.isFinite(n) ? n : null;
}

function normalizeChoiceOptions(choices) {
  // Convert various Freshdesk choices shapes into [{ value, label }]
  // - Array: ['A', 'B'] or [{label, value}]
  // - Object map:
  //   - { Low: 1 }  => label=Low, value=1
  //   - { '2': ['Open', 'desc'] } => label=Open, value=2
  if (!choices) return [];

  if (Array.isArray(choices)) {
    return choices.map(c => {
      if (typeof c === 'object' && c) {
        const label = c.label ?? c.value ?? c.name ?? '';
        const value = c.value ?? c.id ?? c.name ?? label;
        return { value: String(value), label: String(label) };
      }
      return { value: String(c), label: String(c) };
    });
  }

  if (typeof choices === 'object') {
    return Object.entries(choices).map(([k, v]) => {
      if (Array.isArray(v)) {
        // status-like: { '2': ['Open', '...'] }
        return { value: String(k), label: String(v[0] ?? k) };
      }
      // priority/group-like: { 'High': 3 } or { 'Sales': 123 }
      return { value: String(v), label: String(k) };
    });
  }

  return [];
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
    const btn3 = document.getElementById(`btn-${fieldName}-${messageId}-3`);

    // Update Level 2 options
    const level2Choices = val1 ? this.getChoicesForLevel(choices, 2, [val1]) : [];
    const hasLevel2 = level2Choices && level2Choices.length > 0;
    if (el2) {
      el2.innerHTML = this.buildSelectOptions(level2Choices);
      el2.disabled = !val1 || !hasLevel2;
      el2.value = '';
    }

    // Reset / disable Level 3 input when Level 2 is not available
    if (el3) {
      el3.disabled = !hasLevel2;
      el3.value = '';
    }

    // "목록" 버튼은 L3 사용 가능 여부에 맞춰 비활성화/활성화해야 함
    if (btn3) {
      btn3.disabled = true;
    }

    // Also hide dropdown list if present
    const dropdown = document.getElementById(`dropdown-${fieldName}-${messageId}-3`);
    if (dropdown) dropdown.classList.add('hidden');
  },

  /**
   * Sync from Level 2 change (forward direction)
   */
  syncFromLevel2(messageId, fieldName, val1, val2) {
    const cache = this.getCache(messageId, fieldName);
    if (!cache) return;

    const { choices } = cache;
    const el3 = document.getElementById(`input-${fieldName}-${messageId}-3`);
    const btn3 = document.getElementById(`btn-${fieldName}-${messageId}-3`);

    // If this branch ends at Level 2, disable Level 3.
    const level3Choices = val2 ? this.getChoicesForLevel(choices, 3, [val1, val2]) : [];
    const hasLevel3 = level3Choices && level3Choices.length > 0;

    if (el3) {
      el3.disabled = !val2 || !hasLevel3;
      el3.value = '';
    }

    if (btn3) {
      btn3.disabled = !val2 || !hasLevel3;
    }

    const dropdown = document.getElementById(`dropdown-${fieldName}-${messageId}-3`);
    if (dropdown) dropdown.classList.add('hidden');
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

    // Only sync when user selected an exact leaf value.
    // For partial typing, do nothing silently.
    if (!path || path.length < 1) {
      return;
    }

    const targetVal1 = path[0] || '';
    const targetVal2 = path[1] || '';
    const targetVal3 = path[2] || '';

    const el1 = document.getElementById(`input-${fieldName}-${messageId}-1`);
    const el2 = document.getElementById(`input-${fieldName}-${messageId}-2`);
    const el3 = document.getElementById(`input-${fieldName}-${messageId}-3`);
    const btn3 = document.getElementById(`btn-${fieldName}-${messageId}-3`);

    // Always set Level 1
    if (el1) el1.value = targetVal1;

    // Rebuild Level 2 options
    const level2Choices = targetVal1 ? this.getChoicesForLevel(choices, 2, [targetVal1]) : [];
    const hasLevel2 = level2Choices && level2Choices.length > 0;
    if (el2) {
      el2.innerHTML = this.buildSelectOptions(level2Choices);
      el2.disabled = !hasLevel2;
      el2.value = targetVal2 || '';
    }

    // Handle branch depths:
    // - leaf at level1: disable level2 + level3
    // - leaf at level2: disable level3
    // - leaf at level3: enable level3
    const level3Choices = (targetVal1 && targetVal2)
      ? this.getChoicesForLevel(choices, 3, [targetVal1, targetVal2])
      : [];
    const hasLevel3 = level3Choices && level3Choices.length > 0;

    if (el3) {
      // Level3 input is only meaningful when there are level3 choices.
      el3.disabled = !hasLevel3;
      // Keep the typed value so user sees what they chose.
      // If the path is only 1 or 2 deep, val3 will be empty.
      el3.value = val3;
    }

    if (btn3) {
      btn3.disabled = !hasLevel3;
    }

    // If the selected leaf ends at level1 or level2, clear deeper fields explicitly.
    if (path.length === 1) {
      if (el2) el2.value = '';
      if (el3) el3.value = val3; // leaf label is shown in level3 box
    }
    if (path.length === 2) {
      if (el3) el3.value = val3;
    }

    // Hide dropdown list if present
    const dropdown = document.getElementById(`dropdown-${fieldName}-${messageId}-3`);
    if (dropdown) dropdown.classList.add('hidden');
  },

  onLevel3Input(messageId, fieldName, value) {
    // Only sync when an exact option is selected/typed.
    const cache = this.getCache(messageId, fieldName);
    if (!cache) return;
    if (cache.pathMap?.[value]) {
      this.syncFromLevel3(messageId, fieldName, value);
    }
  },

  toggleLevel3Dropdown(messageId, fieldName) {
    const dropdown = document.getElementById(`dropdown-${fieldName}-${messageId}-3`);
    if (!dropdown) return;
    dropdown.classList.toggle('hidden');
  },

  applyLevel3FromDropdown(messageId, fieldName, value) {
    const input = document.getElementById(`input-${fieldName}-${messageId}-3`);
    if (input) input.value = value;
    this.syncFromLevel3(messageId, fieldName, value);
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

    // IDs are rooted by the nested root fieldName (not each nested field name)
    for (const nf of nestedFields) {
      const el = document.getElementById(`input-${fieldName}-${messageId}-${nf.level}`);
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

    const datalistId = `datalist-${fieldName}-${messageId}-level3`;

    return `
      <div class="nested-field-container space-y-2">
        <!-- Level 1 -->
        <div>
          <label class="text-xs text-gray-500">${escapeHtml(level1Field?.label || 'Level 1')}</label>
          <select
            id="input-${fieldName}-${messageId}-1"
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
            id="input-${fieldName}-${messageId}-2"
            data-field-name="${escapeHtml(level2Field?.name || fieldName)}"
            data-level="2"
            onchange="NestedFieldManager.syncFromLevel2('${messageId}', '${fieldName}',
              document.getElementById('input-${fieldName}-${messageId}-1').value, this.value)"
            class="w-full px-2 py-1 text-sm border rounded"
            ${!val1 ? 'disabled' : ''}
          >
            ${this.buildSelectOptions(level2Choices)}
          </select>
        </div>

        <!-- Level 3 -->
        <div>
          <label class="text-xs text-gray-500">${escapeHtml(level3Field?.label || 'Level 3')}</label>
          <!--
            Make Level 3 searchable via datalist on the field itself (no extra search + apply UI).
            On selection, immediately sync Level 1/2.
          -->
          <div class="flex gap-2">
            <input
              id="input-${fieldName}-${messageId}-3"
              data-field-name="${escapeHtml(level3Field?.name || fieldName)}"
              data-level="3"
              list="${datalistId}"
              value="${escapeHtml(val3)}"
              placeholder="키워드로 검색/선택"
              oninput="NestedFieldManager.onLevel3Input('${messageId}', '${fieldName}', this.value)"
              onchange="NestedFieldManager.onLevel3Input('${messageId}', '${fieldName}', this.value)"
              class="flex-1 px-2 py-1 text-sm border rounded"
              ${!val2 ? 'disabled' : ''}
            />
            <button
              type="button"
              id="btn-${fieldName}-${messageId}-3"
              onclick="NestedFieldManager.toggleLevel3Dropdown('${messageId}', '${fieldName}')"
              class="px-3 py-1 text-sm bg-gray-200 rounded hover:bg-gray-300"
              ${(!val2 || !level3Choices || level3Choices.length === 0) ? 'disabled' : ''}
            >목록</button>
          </div>
          <datalist id="${datalistId}">
            ${(leafOptions || []).slice(0, 2000).map(opt =>
              `<option value="${escapeHtml(opt.value)}" label="${escapeHtml(opt.label)}"></option>`
            ).join('')}
          </datalist>

          <select
            id="dropdown-${fieldName}-${messageId}-3"
            class="mt-2 w-full px-2 py-1 text-sm border rounded hidden"
            size="8"
            onchange="NestedFieldManager.applyLevel3FromDropdown('${messageId}', '${fieldName}', this.value)"
          >
            <option value="">전체 목록에서 선택</option>
            ${(leafOptions || []).slice(0, 2000).map(opt =>
              `<option value="${escapeHtml(opt.value)}">${escapeHtml(opt.label)}</option>`
            ).join('')}
          </select>
        </div>
      </div>
    `;
  }
};

// Global reference for inline handlers
window.NestedFieldManager = NestedFieldManager;

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
    const filteredFields = (ticketFields || []).filter(f => {
      if (f?.type === 'nested_field') return true;
      if (f?.name === 'ticket_type') return true;
      if (f?.name === 'priority') return true;
      return false;
    });

    const payload = {
      ticket_id: String(ticketData.id),
      subject: ticketData.subject || '',
      description: ticketData.description_text || ticketData.description || '',
      priority: ticketData.priority,
      status: ticketData.status,
      tags: ticketData.tags || [],
      ticket_fields: filteredFields,
      fields_only: true
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

  ensureBasicFieldsCard(messageId) {
    const container = document.getElementById(`${messageId}-fields`);
    if (!container) return;

    const cardId = `basic-fields-${messageId}`;
    if (document.getElementById(cardId)) return;

    const typeDef = state.ticketFields?.find(f => f.name === 'ticket_type');
    const prioDef = state.ticketFields?.find(f => f.name === 'priority');

    const typeOptions = normalizeChoiceOptions(typeDef?.choices);
    const prioOptions = normalizeChoiceOptions(prioDef?.choices);

    const cardHtml = `
      <div id="${cardId}" class="field-proposal p-3 bg-gray-50 rounded border-l-4 border-blue-500 animate-fade-in">
        <div class="font-medium text-sm">기본 필드</div>
        <div class="text-xs text-gray-500 mt-1">Type / Priority</div>
        <div class="mt-2 grid grid-cols-2 gap-2">
          <div>
            <label class="text-xs text-gray-500">${escapeHtml(typeDef?.label || 'Type')}</label>
            <select
              id="input-ticket_type-${messageId}"
              data-field-name="ticket_type"
              class="w-full px-2 py-1 text-sm border rounded"
            >
              <option value="">선택하세요</option>
              ${typeOptions.map(opt => `<option value="${escapeHtml(opt.value)}">${escapeHtml(opt.label)}</option>`).join('')}
            </select>
          </div>
          <div>
            <label class="text-xs text-gray-500">${escapeHtml(prioDef?.label || 'Priority')}</label>
            <select
              id="input-priority-${messageId}"
              data-field-name="priority"
              class="w-full px-2 py-1 text-sm border rounded"
            >
              <option value="">선택하세요</option>
              ${prioOptions.map(opt => `<option value="${escapeHtml(opt.value)}">${escapeHtml(opt.label)}</option>`).join('')}
            </select>
          </div>
        </div>
      </div>
    `;

    // Remove placeholder on first real content
    const placeholder = container.querySelector('.text-gray-500');
    if (placeholder) placeholder.remove();

    container.insertAdjacentHTML('beforeend', cardHtml);
  },

  setBasicFieldValue(messageId, fieldName, proposedValue) {
    const el = document.getElementById(`input-${fieldName}-${messageId}`);
    if (!el) return;
    if (proposedValue === undefined || proposedValue === null) return;
    el.value = String(proposedValue);
  },

  /**
   * Apply a proposed value into the existing nested 3-level widget.
   * - If proposed value is a leaf(Level 3): reverse-sync Level 1/2
   * - If proposed value matches Level 1/2: forward-sync
   */
  applyNestedProposal(messageId, nestedRootName, proposedValue, explicitLevel) {
    if (!proposedValue) return;

    const cache = NestedFieldManager.getCache(messageId, nestedRootName);
    if (!cache) return;

    const { choices, pathMap } = cache;

    const el1 = document.getElementById(`input-${nestedRootName}-${messageId}-1`);
    const el2 = document.getElementById(`input-${nestedRootName}-${messageId}-2`);

    // 1) Explicit level from field definition (when proposal is for a specific nested field)
    if (explicitLevel === 1) {
      if (el1) {
        el1.value = proposedValue;
        NestedFieldManager.syncFromLevel1(messageId, nestedRootName, proposedValue);
      }
      return;
    }
    if (explicitLevel === 2) {
      // Find parent Level1 uniquely
      const parentVal1 = choices
        ?.find(l1 => (l1.choices || []).some(l2 => l2.value === proposedValue))
        ?.value;
      if (parentVal1 && el1) {
        el1.value = parentVal1;
        NestedFieldManager.syncFromLevel1(messageId, nestedRootName, parentVal1);
      }
      if (parentVal1 && el2) {
        el2.value = proposedValue;
        NestedFieldManager.syncFromLevel2(messageId, nestedRootName, parentVal1, proposedValue);
      }
      return;
    }
    if (explicitLevel === 3) {
      // If it's not a leaf, fall through to auto-detect instead of warning.
      if (pathMap?.[proposedValue]) {
        NestedFieldManager.syncFromLevel3(messageId, nestedRootName, proposedValue);
        return;
      }
    }

    // 2) Auto-detect by value
    if (pathMap?.[proposedValue]) {
      NestedFieldManager.syncFromLevel3(messageId, nestedRootName, proposedValue);
      return;
    }

    // Level 1 direct match
    if (choices?.some(l1 => l1.value === proposedValue)) {
      if (el1) {
        el1.value = proposedValue;
        NestedFieldManager.syncFromLevel1(messageId, nestedRootName, proposedValue);
      }
      return;
    }

    // Level 2 match (try to find a unique parent)
    const matches = [];
    for (const l1 of choices || []) {
      for (const l2 of l1.choices || []) {
        if (l2.value === proposedValue) matches.push({ parentVal1: l1.value });
      }
    }

    if (matches.length === 1) {
      const parentVal1 = matches[0].parentVal1;
      if (el1) {
        el1.value = parentVal1;
        NestedFieldManager.syncFromLevel1(messageId, nestedRootName, parentVal1);
      }
      if (el2) {
        el2.value = proposedValue;
        NestedFieldManager.syncFromLevel2(messageId, nestedRootName, parentVal1, proposedValue);
      }
      return;
    }

    console.warn('Nested proposal value not found in choices:', proposedValue);
  },

  /**
   * Cache DOM elements
   */
  cacheElements() {
    this.elements = {
      chatContainer: document.getElementById('chatContainer'),
      chatInput: document.getElementById('chatInput'),
      sendButton: document.getElementById('sendBtn'),
      analyzeButton: document.getElementById('analyzeBtn'),
      loadingIndicator: document.getElementById('loading-indicator'),
      headerTitle: document.getElementById('headerTitle'),
      statusBadge: document.getElementById('statusBadge'),
      statusText: document.getElementById('statusText')
    };
  },

  setReady(ticketData) {
    const subject = ticketData?.subject ? `- ${ticketData.subject}` : '';
    if (this.elements.headerTitle) {
      this.elements.headerTitle.textContent = `티켓 준비됨 ${subject}`.trim();
    }
    if (this.elements.statusBadge) {
      this.elements.statusBadge.textContent = '준비 완료';
      this.elements.statusBadge.className = 'px-2 py-1 text-xs font-medium rounded-full bg-green-100 text-green-700';
    }
    if (this.elements.statusText) {
      this.elements.statusText.textContent = '준비 완료. “티켓 분석”을 눌러 진행하세요.';
    }
  },

  setLoading(text = '분석 중...') {
    if (this.elements.headerTitle) {
      this.elements.headerTitle.textContent = '티켓 분석 중...';
    }
    if (this.elements.statusBadge) {
      this.elements.statusBadge.textContent = text;
      this.elements.statusBadge.className = 'px-2 py-1 text-xs font-medium rounded-full bg-yellow-100 text-yellow-700';
    }
    if (this.elements.statusText) {
      this.elements.statusText.textContent = '분석을 진행 중입니다...';
    }
  },

  setError(text = '오류') {
    if (this.elements.statusBadge) {
      this.elements.statusBadge.textContent = text;
      this.elements.statusBadge.className = 'px-2 py-1 text-xs font-medium rounded-full bg-red-100 text-red-700';
    }
    if (this.elements.statusText) {
      this.elements.statusText.textContent = '오류가 발생했습니다. 콘솔 로그를 확인해주세요.';
    }
  },

  /**
   * Show loading state
   */
  showLoading(message = '분석 중...') {
    state.isLoading = true;
    this.setLoading(message);
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

        <!-- Field Update Button (single action) -->
        <div id="${messageId}-actions" class="actions mt-4 hidden">
          <button
            onclick="applyFieldUpdates('${messageId}')"
            class="w-full py-2 bg-green-600 text-white rounded hover:bg-green-700"
          >
            필드 업데이트
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

    // Focus this task on nested field correctness: skip status/product proposals.
    if (EXCLUDED_PROPOSAL_FIELDS.has(fieldName)) {
      return;
    }

    // Check if this is a nested field
    const nestedRoot = state.ticketFields?.find(f => f.type === 'nested_field');
    const nestedRootName = nestedRoot?.name;
    const nestedLevelDef = nestedRoot?.nested_ticket_fields?.find(nf => nf.name === fieldName);
    const isNestedField = Boolean(nestedRoot && (
      nestedRootName === fieldName ||
      nestedLevelDef
    ));

    let inputHtml;

    if (isNestedField) {
      // Render nested selector ONCE per analysis message to avoid duplicate 3-level UIs.
      const nestedBlockId = `nested-proposal-${nestedRootName}-${messageId}`;
      const existingBlock = document.getElementById(nestedBlockId);

      // If the block already exists, we just update its selections and skip inserting a new proposal card.
      if (existingBlock) {
        // Apply proposal into existing widget (best-effort by level)
        setTimeout(() => {
          this.applyNestedProposal(messageId, nestedRootName, proposedValue, nestedLevelDef?.level);
        }, 0);

        return;
      }

      // First time: render the widget and insert a single card
      inputHtml = NestedFieldManager.render(messageId, nestedRootName, nestedRoot, {});

      const fieldHtml = `
        <div id="${nestedBlockId}" class="field-proposal p-3 bg-gray-50 rounded border-l-4 border-blue-500 animate-fade-in">
          <div class="flex justify-between items-start">
            <div class="flex-1">
              <div class="font-medium text-sm">${escapeHtml(nestedRoot?.label || '카테고리(3단계)')}</div>
              <div class="text-xs text-gray-500 mt-1">${escapeHtml(reason || '')}</div>
            </div>
          </div>
          <div class="mt-2">
            ${inputHtml}
          </div>
        </div>
      `;

      container.insertAdjacentHTML('beforeend', fieldHtml);

      // Apply initial proposal (if it's a leaf, reverse-sync parents)
      setTimeout(() => {
        this.applyNestedProposal(messageId, nestedRootName, proposedValue, nestedLevelDef?.level);
      }, 50);

      return;
    } else {
      // For this task: keep only Type + Priority (dropdowns) and render them in one row.
      if (!ALLOWED_FLAT_FIELDS.has(fieldName)) {
        return;
      }

      this.ensureBasicFieldsCard(messageId);

      // Proposed values from LLM may be labels; for priority, our select values are numeric.
      if (fieldName === 'priority') {
        const fieldDef = state.ticketFields?.find(f => f.name === 'priority');
        const opts = normalizeChoiceOptions(fieldDef?.choices);
        const needle = String(proposedValue ?? '').trim().toLowerCase();
        const match = opts.find(o => String(o.label).trim().toLowerCase() === needle || String(o.value).trim().toLowerCase() === needle);
        if (match) {
          this.setBasicFieldValue(messageId, 'priority', match.value);
        }
      } else {
        this.setBasicFieldValue(messageId, fieldName, proposedValue);
      }

      this.showActions(messageId);
      return;
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

    // Once we have at least one proposal, allow user to apply updates.
    this.showActions(messageId);
  },

  /**
   * Render draft response
   */
  renderDraftResponse(messageId, text) {
    // (후순위) 응답 초안/요약 기능은 다음 태스크에서 다시 활성화
    return;
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

    // 1) Handle nested field as a coherent group (and clear missing levels)
    if (nestedRoot) {
      const cache = NestedFieldManager.getCache(messageId, nestedRoot.name);
      if (cache) {
        const values = NestedFieldManager.collectValues(messageId, nestedRoot.name);

        // Root value (level1) may not exist in nested_ticket_fields; capture it explicitly.
        const rootEl = document.getElementById(`input-${nestedRoot.name}-${messageId}-1`);
        customFields[nestedRoot.name] = rootEl?.value ?? null;

        for (const nf of (nestedRoot.nested_ticket_fields || [])) {
          // If a level is not selected, clear it to prevent inconsistent combinations.
          customFields[nf.name] = values[nf.name] ?? null;
        }
      }
    }

    // Collect regular field values
    const inputs = container.querySelectorAll('[data-field-name]');
    const processedFields = new Set();

    inputs.forEach(input => {
      const fieldName = input.dataset.fieldName;
      const level = input.dataset.level;

      const updateFieldName = FIELD_NAME_ALIASES[fieldName] || fieldName;

      if (EXCLUDED_UPDATE_FIELDS.has(fieldName) || EXCLUDED_UPDATE_FIELDS.has(updateFieldName)) return;

      // Skip if already processed or nested field (handled separately)
      if (processedFields.has(updateFieldName) && !level) return;

      const value = input.value;
      if (!value) return;

      if (nestedFieldNames.has(fieldName) && level) {
        // Nested field handled above as a group (includes clearing). Skip here.
        return;
      } else if (STANDARD_FIELDS.includes(updateFieldName)) {
        // Standard field
        if (NUMERIC_FIELDS.includes(updateFieldName)) {
          const fieldDef = ticketFields?.find(f => f.name === fieldName || f.name === updateFieldName);
          const coerced = coerceNumericChoiceValue(value, fieldDef?.choices);
          if (coerced !== null) {
            updateBody[updateFieldName] = coerced;
          }
        } else {
          updateBody[updateFieldName] = value;
        }
      } else {
        // Custom field
        customFields[updateFieldName] = value;
      }

      processedFields.add(updateFieldName);
    });

    // Never send NaN numeric fields
    for (const k of Object.keys(updateBody)) {
      if (NUMERIC_FIELDS.includes(k) && !Number.isFinite(updateBody[k])) {
        delete updateBody[k];
      }
    }

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
      let details = '';
      try {
        const parsed = JSON.parse(response.response);
        details = parsed?.description || parsed?.message || JSON.stringify(parsed);
      } catch (e) {
        details = response.response || '';
      }
      throw new Error(`API Error: ${response.status}${details ? ` - ${details}` : ''}`);
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
        // (후순위) 응답 초안/요약 기능은 다음 태스크에서 다시 활성화
        return;
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
    // In modal view, ticket data may not be immediately available.
    // Retry a few times to avoid half-loaded state.
    let data;
    for (let attempt = 0; attempt < 5; attempt++) {
      data = await client.data.get('ticket');
      if (data?.ticket?.id) break;
      await new Promise(r => setTimeout(r, 200));
    }

    state.ticketData = data.ticket;

    // Load conversations
    // NOTE:
    // - client.data.get('ticket.conversations') can throw "잘못된 특성 입력됨" in some contexts.
    // - Freshdesk conversations API is paginated (max 30 per page).
    // Use request templates (config/requests.json) and paginate.
    // Load in background so modal can become ready immediately.
    state.ticketData.conversations = [];
    const ticketId = state.ticketData?.id;
    if (ticketId) {
      (async () => {
        try {
          const all = await loadAllConversations(client, ticketId);
          state.ticketData.conversations = all;
          console.log('Ticket conversations loaded:', all.length);
        } catch (e) {
          console.warn('Could not load conversations:', e);
        }
      })();
    }

    console.log('Ticket data loaded:', state.ticketData.id);
    return state.ticketData;
  } catch (error) {
    console.error('Failed to load ticket data:', error);
    throw error;
  }
}

async function loadAllConversations(client, ticketId) {
  const perPage = 30;
  // Hard cap to avoid excessive load in very long threads.
  const maxPages = 20; // up to 600 conversations
  const all = [];

  for (let page = 1; page <= maxPages; page++) {
    const resp = await client.request.invokeTemplate('getTicketConversations', {
      context: { ticketId, page }
    });

    let parsed;
    try {
      parsed = JSON.parse(resp.response);
    } catch (e) {
      console.warn('Failed to parse conversations response:', e);
      break;
    }

    const conversations = Array.isArray(parsed) ? parsed : (parsed?.conversations || []);
    if (!Array.isArray(conversations) || conversations.length === 0) {
      break;
    }

    all.push(...conversations);

    if (conversations.length < perPage) {
      break;
    }
  }

  return all;
}

async function loadTicketFields(client) {
  try {
    // 1) Prefer backend-cached schema (Supabase) to avoid hitting Freshdesk every modal open
    try {
      const resp = await fetch(`${API_BASE}/api/assist/ticket-fields`, {
        method: 'GET',
        headers: {
          ...getHeaders(),
          'ngrok-skip-browser-warning': 'true'
        }
      });

      if (resp.ok) {
        const data = await resp.json();
        const fields = Array.isArray(data) ? data : (data?.ticket_fields || []);
        if (Array.isArray(fields) && fields.length > 0) {
          state.ticketFields = fields;
          console.log('Ticket fields loaded (backend cache):', fields.length);
          return fields;
        }
      } else {
        console.warn('Backend ticket-fields returned non-OK:', resp.status);
      }
    } catch (e) {
      console.warn('Backend ticket-fields fetch failed, falling back to Freshdesk:', e);
    }

    // 2) Fallback: Freshdesk API via FDK request template
    const response = await client.request.invokeTemplate('getTicketFields', {});
    const fields = JSON.parse(response.response);
    state.ticketFields = fields;
    console.log('Ticket fields loaded (freshdesk fallback):', fields.length);
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
            console.log('[AI Copilot] app.activated fired — attempting to open modal');
            try {
              const res = await _client.interface.trigger("showModal", {
                title: "AI Copilot",
                template: "index.html",
                noBackdrop: true
              });
              console.log('[AI Copilot] showModal resolved:', res);
            } catch (err) {
              console.error('[AI Copilot] showModal failed:', err);
              showNotify('danger', '모달을 열지 못했습니다: ' + (err?.message || err));
            }
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

        // Mark UI as ready (default texts in index.html are placeholders)
        UIRenderer.setReady(state.ticketData);

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
        try { UIRenderer.setError('초기화 실패'); } catch (e) {}
      });
    } else {
      console.error("[AI Copilot] FDK app 객체가 없습니다.");
    }
  }
};
