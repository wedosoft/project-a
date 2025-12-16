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
    const data = await client.request.invokeTemplate('getTicketFields');
    const fields = JSON.parse(data.response);
    
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
    container.innerHTML = '<p style="color: red;">Failed to load ticket fields. Check API Key.</p>';
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
  client.interface.trigger('showNotify', {
    type: type,
    message: message
  });
}
