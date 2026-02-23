'use strict';
/**
 * FDK Serverless Functions
 * - secure iparams(시크릿) 접근은 서버리스에서만 가능
 * - Freshdesk API 호출은 config/requests.json 템플릿(invokeTemplate)으로 통일
 */

const SCHEDULE_NAME = 'incremental_sync';

// 환경별 백엔드 주소 정책
// - 운영: 코드 기본값으로 api.wedosoft.net 사용
// - 로컬 개발: BACKEND_BASE_URL 환경변수로 ngrok 등 오버라이드
const PROD_BACKEND_BASE_URL = 'https://api.wedosoft.net';

function logWarn(...args) {
  if (console && typeof console.warn === 'function') {
    console.warn(...args);
    return;
  }
  if (console && typeof console.log === 'function') {
    console.log(...args);
  }
}

function buildTenantHeaders(iparams) {
  const domain = iparams?.freshdesk_domain || '';
  const apiKey = iparams?.freshdesk_api_key || '';
  const tenantId = domain.split('.')[0] || '';

  return {
    domain,
    apiKey,
    tenantId,
    headers: {
      'Content-Type': 'application/json',
      'X-Tenant-ID': tenantId,
      'X-Platform': 'freshdesk',
      'X-API-Key': apiKey,
      'X-Domain': domain
    }
  };
}

function resolveBackendBaseUrl() {
  const env = process.env || {};

  // 로컬 개발 환경은 환경변수로만 오버라이드 (ngrok URL 하드코딩 금지)
  if (env.BACKEND_BASE_URL) {
    return env.BACKEND_BASE_URL;
  }

  // 운영 기본값
  return PROD_BACKEND_BASE_URL;
}

async function callSyncEndpoint(iparams, payload) {
  let backendUrl;
  try {
    backendUrl = resolveBackendBaseUrl().replace(/\/+$/, '');
  } catch (error) {
    return { ok: false, message: error.message || 'Backend URL not configured' };
  }

  const { headers, domain, apiKey } = buildTenantHeaders(iparams);
  if (!domain || !apiKey) {
    return { ok: false, message: 'Freshdesk API key or domain not configured' };
  }

  const url = `${backendUrl}/api/sync/trigger`;
  const response = await fetch(url, {
    method: 'POST',
    headers,
    body: JSON.stringify(payload)
  });

  const responseText = await response.text();
  let responseData = responseText;
  try {
    responseData = responseText ? JSON.parse(responseText) : {};
  } catch (error) {
    responseData = { raw: responseText };
  }

  if (!response.ok) {
    const detail = responseData?.detail || responseData?.message || responseText;
    return { ok: false, status: response.status, message: detail || 'Sync request failed' };
  }

  return { ok: true, status: response.status, data: responseData };
}

/**
 * 보안 파라미터 (API 키 등) 가져오기
 * 프론트엔드에서 직접 접근할 수 없는 secure iparams를 서버사이드에서 접근
 */
function getSecureParams(args) {
  try {
    const { iparams } = args;

    const secureData = {
      apiKey: iparams?.freshdesk_api_key,
      domain: iparams?.freshdesk_domain,
      // 테넌트 ID는 도메인에서 추출 (예: company.freshdesk.com → company)
      tenantId: iparams?.freshdesk_domain?.split('.')[0] || ''
    };

    if (!secureData.apiKey) {
      console.error('❌ 서버리스: API 키가 설정되지 않았습니다');
      renderData({ message: 'API key not configured' });
      return;
    }

    renderData(null, secureData);
  } catch (error) {
    console.error('❌ 서버리스 오류:', error);
    renderData({ message: error.message || 'Failed to retrieve secure parameters' });
  }
}

/**
 * 수동 수집 트리거
 */
async function triggerSyncJob(args) {
  try {
    const { iparams, data } = args;
    const payload = {
      include_tickets: data?.include_tickets !== false,
      include_articles: data?.include_articles !== false,
      incremental: data?.incremental === true,
      batch_size: data?.batch_size || 10,
      max_concurrency: data?.max_concurrency || 5
    };

    if (data?.purge !== undefined) {
      payload.purge = data.purge;
    }
    if (data?.purge_only !== undefined) {
      payload.purge_only = data.purge_only;
    }

    const result = await callSyncEndpoint(iparams, payload);
    if (!result.ok) {
      renderData({ message: result.message || 'Sync trigger failed' });
      return;
    }
    renderData(null, result.data || {});
  } catch (error) {
    console.error('❌ 서버리스 오류:', error);
    renderData({ message: error.message || 'Failed to trigger sync' });
  }
}

/**
 * 정기 증분 수집 스케줄 생성/갱신/삭제
 */
async function upsertIncrementalSchedule(args) {
  try {
    const { data } = args;
    const enabled = data?.enabled === true;

    if (!enabled) {
      try {
        await $schedule.delete({ name: SCHEDULE_NAME });
      } catch (error) {
        logWarn('⚠️ 기존 스케줄이 없어 삭제를 건너뜁니다.');
      }
      renderData(null, { status: 'deleted' });
      return;
    }

    const frequencyHours = Number(data?.interval_hours || 24);
    const scheduleAt = new Date(Date.now() + 60 * 1000).toISOString();
    const scheduleData = {
      include_tickets: data?.include_tickets !== false,
      include_articles: data?.include_articles !== false
    };

    const scheduleConfig = {
      name: SCHEDULE_NAME,
      schedule_at: scheduleAt,
      repeat: {
        time_unit: 'hours',
        frequency: frequencyHours
      },
      data: scheduleData
    };

    try {
      await $schedule.update(scheduleConfig);
      renderData(null, { status: 'updated', interval_hours: frequencyHours });
    } catch (error) {
      await $schedule.create(scheduleConfig);
      renderData(null, { status: 'scheduled', interval_hours: frequencyHours });
    }
  } catch (error) {
    console.error('❌ 스케줄 설정 실패:', error);
    renderData({ message: error.message || 'Failed to update schedule' });
  }
}

/**
 * 정기 증분 수집 스케줄 핸들러
 */
async function onIncrementalSyncSchedule(payload) {
  try {
    const iparams = payload?.iparams || {};
    const data = payload?.data || {};
    const payloadBody = {
      include_tickets: data.include_tickets !== false,
      include_articles: data.include_articles !== false,
      incremental: true,
      batch_size: 10,
      max_concurrency: 5
    };

    const result = await callSyncEndpoint(iparams, payloadBody);
    if (!result.ok) {
      console.error('❌ 스케줄 수집 실패:', result.message);
    } else {
      console.log('✅ 스케줄 수집 시작됨:', result.data?.job_id || 'scheduled');
    }
  } catch (error) {
    console.error('❌ 스케줄 핸들러 오류:', error);
  }
}

// Freshworks FDK(serverless) 파서가 인식하는 exports 섹션
exports = {
  // NOTE: FDK 파서 호환성을 위해 exports 섹션에서 직접 function 표현식을 선언
  getSecureParams: function(args) {
    return getSecureParams(args);
  },
  triggerSyncJob: async function(args) {
    return await triggerSyncJob(args);
  },
  upsertIncrementalSchedule: async function(args) {
    return await upsertIncrementalSchedule(args);
  },
  onIncrementalSyncSchedule: async function(payload) {
    return await onIncrementalSyncSchedule(payload);
  }
};
