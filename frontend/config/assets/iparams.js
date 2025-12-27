let client = null;
const state = {
  hasSecureApiKey: false
};

const elements = {
  freshdeskDomain: () => document.getElementById('freshdesk_domain'),
  freshdeskApiKey: () => document.getElementById('freshdesk_api_key'),
  collectTickets: () => document.getElementById('collect_tickets'),
  collectArticles: () => document.getElementById('collect_articles'),
  scheduleEnabled: () => document.getElementById('schedule_enabled'),
  scheduleInterval: () => document.getElementById('schedule_interval_hours'),
  statusMessage: () => document.getElementById('status_message'),
  errorMessage: () => document.getElementById('error_message'),
  syncStatus: () => document.getElementById('sync_status')
};

function setStatus(message, type = 'neutral') {
  const el = elements.statusMessage();
  if (!el) return;
  el.textContent = message;
  el.className = `status ${type}`;
}

function setError(message) {
  const el = elements.errorMessage();
  if (!el) return;
  if (message) {
    el.textContent = message;
    el.classList.remove('hidden');
  } else {
    el.textContent = '';
    el.classList.add('hidden');
  }
}

function setSyncStatus(message, type = 'neutral') {
  const el = elements.syncStatus();
  if (!el) return;
  el.textContent = message;
  el.className = `status ${type}`;
}

function getCollectionTargets() {
  const includeTickets = elements.collectTickets()?.checked || false;
  const includeArticles = elements.collectArticles()?.checked || false;

  if (!includeTickets && !includeArticles) {
    setSyncStatus('수집 대상을 하나 이상 선택하세요.', 'error');
    return null;
  }

  return { includeTickets, includeArticles };
}

async function invokeSync(mode) {
  if (!client) {
    setSyncStatus('클라이언트 초기화가 필요합니다.', 'error');
    return;
  }

  const targets = getCollectionTargets();
  if (!targets) return;

  const payload = {
    include_tickets: targets.includeTickets,
    include_articles: targets.includeArticles,
    incremental: mode === 'incremental'
  };

  if (mode === 'full') {
    payload.purge = true;
  }
  if (mode === 'purge') {
    payload.purge = true;
    payload.purge_only = true;
  }

  try {
    setSyncStatus('수집 요청 중...', 'neutral');
    const response = await client.request.invoke('triggerSyncJob', { data: payload });
    const result = response?.response || response;

    if (response?.status && response.status >= 400) {
      const detail = result?.message || result?.detail || '수집 요청 실패';
      setSyncStatus(detail, 'error');
      return;
    }

    const jobId = result?.job_id ? ` (job_id: ${result.job_id})` : '';
    setSyncStatus(`수집이 시작되었습니다.${jobId}`, 'success');
  } catch (error) {
    setSyncStatus(error.message || '수집 요청 실패', 'error');
  }
}

function bindSyncButtons() {
  const incrementalBtn = document.getElementById('sync_incremental');
  const fullBtn = document.getElementById('sync_full');
  const purgeBtn = document.getElementById('sync_purge');

  incrementalBtn?.addEventListener('click', () => invokeSync('incremental'));
  fullBtn?.addEventListener('click', () => invokeSync('full'));
  purgeBtn?.addEventListener('click', () => invokeSync('purge'));
}

function bindScheduleToggle() {
  const checkbox = elements.scheduleEnabled();
  const interval = elements.scheduleInterval();
  if (!checkbox || !interval) return;

  const updateDisabled = () => {
    interval.disabled = !checkbox.checked;
  };

  checkbox.addEventListener('change', updateDisabled);
  updateDisabled();
}

function collectConfig() {
  const freshdeskDomain = (elements.freshdeskDomain()?.value || '').trim();
  const freshdeskApiKey = (elements.freshdeskApiKey()?.value || '').trim();

  const config = {
    freshdesk_domain: freshdeskDomain,
    collect_tickets: elements.collectTickets()?.checked || false,
    collect_articles: elements.collectArticles()?.checked || false,
    schedule_enabled: elements.scheduleEnabled()?.checked || false,
    schedule_interval_hours: Number(elements.scheduleInterval()?.value || 24),
    __meta: {
      secure: ['freshdesk_api_key']
    }
  };

  if (freshdeskApiKey) {
    config.freshdesk_api_key = freshdeskApiKey;
  }

  return config;
}

async function updateScheduleFromConfig(config) {
  if (!client) return;

  const payload = {
    enabled: config.schedule_enabled === true,
    interval_hours: Number(config.schedule_interval_hours || 24),
    include_tickets: config.collect_tickets !== false,
    include_articles: config.collect_articles !== false
  };

  await client.request.invoke('upsertIncrementalSchedule', { data: payload });
}

function validateConfig() {
  const freshdeskDomain = (elements.freshdeskDomain()?.value || '').trim();
  const freshdeskApiKey = (elements.freshdeskApiKey()?.value || '').trim();
  const scheduleEnabled = elements.scheduleEnabled()?.checked || false;
  const interval = Number(elements.scheduleInterval()?.value || 0);

  if (!freshdeskDomain) {
    setError('Freshdesk 도메인을 입력하세요.');
    return false;
  }


  if (!freshdeskApiKey && !state.hasSecureApiKey) {
    setError('Freshdesk API 키를 입력하세요.');
    return false;
  }

  if (scheduleEnabled && (!interval || interval < 1 || interval > 168)) {
    setError('정기 수집 주기는 1~168시간 범위로 설정하세요.');
    return false;
  }

  setError('');
  return true;
}

function preloadConfig(configs) {
  if (!configs) return;
  if (configs.freshdesk_domain) elements.freshdeskDomain().value = configs.freshdesk_domain;
  if (configs.collect_tickets !== undefined) elements.collectTickets().checked = configs.collect_tickets;
  if (configs.collect_articles !== undefined) elements.collectArticles().checked = configs.collect_articles;
  if (configs.schedule_enabled !== undefined) elements.scheduleEnabled().checked = configs.schedule_enabled;
  if (configs.schedule_interval_hours !== undefined) {
    elements.scheduleInterval().value = configs.schedule_interval_hours;
  }

  bindScheduleToggle();
}

async function checkSecureConfig() {
  if (!client) return;
  try {
    const data = await client.request.invoke('getSecureParams', {});
    const response = data?.response || data;
    state.hasSecureApiKey = Boolean(response?.apiKey);
  } catch (error) {
    state.hasSecureApiKey = false;
  }
}

document.addEventListener('DOMContentLoaded', () => {
  app
    .initialized()
    .then(async (_client) => {
      client = _client;
      await checkSecureConfig();
      bindSyncButtons();
      bindScheduleToggle();
      setStatus('설정이 준비되었습니다.', 'success');
      setSyncStatus('수집 실행 대기 중입니다.');
    })
    .catch(() => {
      setStatus('클라이언트를 초기화하지 못했습니다.', 'error');
    });
});

window.IParams = {
  getConfigs: function(configs) {
    preloadConfig(configs);
    setStatus('설정을 불러왔습니다.', 'success');
    setError('');
  },
  postConfigs: async function() {
    const config = collectConfig();
    try {
      await updateScheduleFromConfig(config);
    } catch (error) {
      console.error('Schedule update failed:', error);
      setStatus('스케줄 업데이트 실패. 저장 후 다시 시도하세요.', 'error');
    }
    return config;
  },
  validate: function() {
    return validateConfig();
  }
};
