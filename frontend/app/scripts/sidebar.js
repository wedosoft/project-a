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

function init() {
  // Event Listeners
  const analyzeBtn = document.getElementById('analyze-btn');
  if (analyzeBtn) analyzeBtn.addEventListener('click', analyzeTicket);
  
  const chatSend = document.getElementById('chat-send');
  if (chatSend) chatSend.addEventListener('click', sendChatMessage);
  
  const chatInput = document.getElementById('chat-input');
  if (chatInput) {
    chatInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') sendChatMessage();
    });
  }
}

async function analyzeTicket() {
  document.getElementById('analyze-btn').style.display = 'none';
  document.getElementById('analysis-loading').style.display = 'block';
  document.getElementById('analysis-result').style.display = 'none';

  try {
    const ticket = await getTicketDetails();
    const response = await callBackend('/api/assist/analyze', 'POST', {
      ticketId: String(ticket.id),
      subject: ticket.subject,
      description: ticket.description_text,
      priority: ticket.priority,
      status: ticket.status,
      tags: ticket.tags,
      streamProgress: false // Use sync mode for simplicity for now
    });

    displayAnalysis(response);
  } catch (error) {
    console.error('Analysis failed', error);
    showNotification('error', 'Analysis failed');
    document.getElementById('analyze-btn').style.display = 'block';
  } finally {
    document.getElementById('analysis-loading').style.display = 'none';
  }
}

function displayAnalysis(data) {
  document.getElementById('analysis-result').style.display = 'block';
  
  const proposal = data.proposal || {};
  
  document.getElementById('intent-val').innerText = proposal.intent || 'N/A';
  document.getElementById('sentiment-val').innerText = proposal.sentiment || 'N/A';
  document.getElementById('root-cause-val').innerText = proposal.summary || 'N/A'; 
  document.getElementById('solution-val').innerText = proposal.reasoning || 'N/A';

  const suggestionsContainer = document.getElementById('suggestions-container');
  suggestionsContainer.innerHTML = '';
  
  const suggestions = proposal.fieldProposals || [];
  suggestions.forEach(suggestion => {
    const card = document.createElement('div');
    card.className = 'analysis-card';
    card.innerHTML = `
      <div class="fw-flex fw-flex-column">
        <span style="font-weight: bold;">${suggestion.fieldLabel || suggestion.fieldName}</span>
        <span style="color: var(--fw-blue-500);">Suggested: ${suggestion.proposedValue}</span>
        <p style="font-size: 12px; color: #666;">${suggestion.reason}</p>
        <fw-button size="small" class="fw-mt-12 apply-btn">Apply</fw-button>
      </div>
    `;
    card.querySelector('.apply-btn').addEventListener('click', () => applySuggestion(suggestion));
    suggestionsContainer.appendChild(card);
  });
}

async function applySuggestion(suggestion) {
  try {
    await client.interface.trigger("setValue", {
      id: suggestion.fieldName,
      value: suggestion.proposedValue
    });
    showNotification('success', `Applied ${suggestion.fieldLabel}`);
  } catch (error) {
    console.error('Failed to apply suggestion', error);
    showNotification('error', `Failed to apply ${suggestion.fieldLabel}`);
  }
}

async function sendChatMessage() {
  const input = document.getElementById('chat-input');
  const message = input.value.trim();
  if (!message) return;

  appendMessage('user', message);
  input.value = '';

  try {
    const { tenantId } = await getContext();
    const response = await callBackend('/api/chat/chat', 'POST', {
      sessionId: `chat-${tenantId}-${Date.now()}`,
      query: message,
      filters: {}
    });
    
    const answer = response.answer;
    appendMessage('ai', answer);

  } catch (error) {
    console.error('Search failed', error);
    appendMessage('ai', 'Sorry, search failed.');
  }
}

function appendMessage(role, text) {
  const history = document.getElementById('chat-history');
  const msgDiv = document.createElement('div');
  msgDiv.className = `message ${role}`;
  msgDiv.innerText = text;
  history.appendChild(msgDiv);
  history.scrollTop = history.scrollHeight;
}

async function getTicketDetails() {
  const data = await client.data.get('ticket');
  return data.ticket;
}

async function getContext() {
  const iparams = await client.iparams.get();
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
  const options = { context: { path: cleanPath } };

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
