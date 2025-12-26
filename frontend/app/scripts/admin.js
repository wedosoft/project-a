function getClient() {
  if (!window.client) {
    throw new Error('FDK client is not initialized');
  }
  return window.client;
}

// app.js와 동일한 방식으로 서버리스에서 보안 파라미터를 로드
window.APP_CONFIG = window.APP_CONFIG || {
  apiKey: '',
  domain: '',
  tenantId: ''
};

document.addEventListener('DOMContentLoaded', function () {
  app
    .initialized()
    .then(function (_client) {
      window.client = _client;
      init();
    })
    .catch(function (err) {
      console.error('App initialization failed', err);
      renderInitError('앱 초기화에 실패했습니다. 새로고침 후 다시 시도해 주세요.');
    });
});

function renderInitError(message) {
  const banner = document.createElement('div');
  banner.textContent = message;
  banner.style.background = '#fdecea';
  banner.style.color = '#611a15';
  banner.style.padding = '12px';
  banner.style.fontSize = '14px';
  banner.style.border = '1px solid #f5c6cb';
  banner.style.borderRadius = '4px';
  banner.style.margin = '12px';
  document.body.prepend(banner);
}

async function init() {
  try {
    // secure iparams는 프론트에서 직접 접근하지 않고, 서버리스 함수로만 가져온다.
    await loadSecureConfig();

    // Load current config
    const config = await fetchConfig();
    if (config) {
      const toneSelect = document.getElementById('response-tone');
      if (toneSelect) toneSelect.value = config.response_tone || 'formal';
      await loadTicketFields(config.selected_fields || []);
    } else {
      await loadTicketFields([]);
    }

    // Event Listeners
    document.getElementById('save-general').addEventListener('click', saveGeneralConfig);
    document.getElementById('save-fields').addEventListener('click', saveFieldsConfig);
    document.getElementById('sync-tickets').addEventListener('click', () => triggerSync('tickets'));
    document.getElementById('sync-articles').addEventListener('click', () => triggerSync('articles'));

  } catch (error) {
    console.error('Initialization failed', error);
    showNotification('error', 'Failed to initialize admin app');
  }
}

/**
 * 보안 파라미터 로드 (서버리스 함수 호출)
 * - Freshdesk API key는 secure iparams이므로 프론트에서 iparams.get()로 직접 접근하지 않는다.
 */
async function loadSecureConfig() {
  const client = getClient();
  if (!client.request || typeof client.request.invoke !== 'function') {
    throw new Error('FDK Request invoke API is not available');
  }

  const data = await client.request.invoke('getSecureParams', {});
  const responseData = data?.response || data;
  if (!responseData || !responseData.apiKey || !responseData.domain) {
    throw new Error('Secure params not configured');
  }

  window.APP_CONFIG.apiKey = responseData.apiKey;
  window.APP_CONFIG.domain = responseData.domain;
  window.APP_CONFIG.tenantId = responseData.tenantId || responseData.domain.split('.')[0] || '';
}

async function fetchConfig() {
  try {
    return await callBackend('/api/admin/config', 'GET');
  } catch (error) {
    console.warn('Config not found or error fetching, using defaults', error);
    return null;
  }
}

async function loadTicketFields(selectedFields) {
  const container = document.getElementById('fields-container');
  container.innerHTML = '<fw-spinner size="medium"></fw-spinner>';

  try {
    const client = getClient();

    if (!client.request || typeof client.request.invokeTemplate !== 'function') {
      throw new Error('FDK Request invokeTemplate API is not available');
    }

    const response = await client.request.invokeTemplate('getTicketFields', {});
    const status = response && (response.status || response.statusCode);
    if (!(status >= 200 && status < 300)) {
      throw new Error((response && response.response) ? String(response.response) : 'Failed to load ticket fields');
    }

    if (!response || typeof response.response !== 'string') {
      throw new Error('Empty response from template');
    }

    let fields;
    try {
      fields = JSON.parse(response.response);
    } catch (e) {
      throw new Error('Failed to parse ticket_fields response');
    }

    if (!Array.isArray(fields)) throw new Error('Unexpected ticket_fields response');
    
    container.innerHTML = '';
    fields.forEach(field => {
      const checkbox = document.createElement('fw-checkbox');
      checkbox.value = field.name;
      checkbox.checked = selectedFields.includes(field.name);
      checkbox.innerText = field.label;
      container.appendChild(checkbox);
    });
  } catch (error) {
    console.error('Error loading fields', error);
    const msg = (error && error.message) ? error.message : String(error);
    container.innerHTML = `<p style="color: red;">Failed to load ticket fields. ${msg}</p>`;
  }
}

async function saveGeneralConfig() {
  const tone = document.getElementById('response-tone').value;
  await updateConfig({ response_tone: tone });
}

async function saveFieldsConfig() {
  const checkboxes = document.querySelectorAll('#fields-container fw-checkbox');
  const selected = Array.from(checkboxes).filter(cb => cb.checked).map(cb => cb.value);
  await updateConfig({ selected_fields: selected });
}

async function updateConfig(updates) {
  try {
    const current = await fetchConfig() || {};
    const newConfig = { ...current, ...updates };
    await callBackend('/api/admin/config', 'PUT', newConfig);
    showNotification('success', 'Configuration saved');
  } catch (error) {
    console.error('Error saving config', error);
    showNotification('error', 'Failed to save configuration');
  }
}

async function triggerSync(source) {
  try {
    await callBackend('/api/admin/sync', 'POST', { sources: [source] });
    showNotification('success', `Sync started for ${source}`);
  } catch (error) {
    console.error('Error triggering sync', error);
    showNotification('error', 'Failed to trigger sync');
  }
}

// Helper functions
async function getContext() {
  const iparams = await client.iparams.get();
  // Use freshdesk_domain as tenantId for now
  return { tenantId: iparams.freshdesk_domain, ...iparams };
}

async function callBackend(path, method, body) {
  const methodUpper = method.toUpperCase();
  const templateMap = {
    GET: 'backendApi',
    POST: 'backendApiPost',
    PUT: 'backendApiPut'
  };
  const templateName = templateMap[methodUpper];
  if (!templateName) throw new Error(`Unsupported method: ${method}`);

  const cleanPath = path.replace(/^\//, '');
  const options = {
    context: { path: cleanPath }
  };

  if (body) {
    options.body = JSON.stringify(body);
  }

  const response = await client.request.invokeTemplate(templateName, options);
  const status = response.status || response.statusCode;

  if (status >= 200 && status < 300) {
    return JSON.parse(response.response);
  }
  throw new Error(response.response || 'Request failed');
}

function showNotification(type, message) {
  const client = getClient();
  client.interface.trigger('showNotify', {
    type: type,
    message: message
  });
}
