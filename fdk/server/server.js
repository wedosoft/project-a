'use strict';
/**
 * FDK Serverless Functions
 * - secure iparams(시크릿) 접근은 서버리스에서만 가능
 * - Freshdesk API 호출은 config/requests.json 템플릿(invokeTemplate)으로 통일
 */

const SCHEDULE_NAME = 'incremental_sync';

// =============================================================================
// getTicketInsights 헬퍼 함수들 (nexus-ai 출처)
// =============================================================================

function toText(htmlOrText) {
  if (!htmlOrText) return '';
  return String(htmlOrText)
    .replace(/<style[\s\S]*?<\/style>/gi, '')
    .replace(/<script[\s\S]*?<\/script>/gi, '')
    .replace(/<[^>]+>/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function normalizeDomain(domain) {
  return String(domain || '')
    .replace(/^https?:\/\//, '')
    .split('/')[0]
    .trim();
}

function toStructuredConversation({ domain, ticket, conversations, actor_agent_id }) {
  const freshdesk_domain = normalizeDomain(domain);
  const subject = ticket?.subject ?? null;
  const conversation = [];

  const firstText = toText(ticket?.description || ticket?.description_text || '');
  if (firstText) {
    conversation.push({
      id: String(ticket?.id ?? 'ticket'),
      ts: ticket?.created_at ?? null,
      author_role: 'customer',
      author_id: ticket?.requester_id ? String(ticket.requester_id) : null,
      channel: 'email',
      text: firstText
    });
  }

  for (const c of conversations || []) {
    const text = toText(c?.body_text || c?.body || '');
    if (!text) continue;

    const isAgent = Boolean(c?.user_id);
    conversation.push({
      id: c?.id ? String(c.id) : null,
      ts: c?.created_at ?? null,
      author_role: isAgent ? 'agent' : 'customer',
      author_id: (c?.user_id || c?.from_email) ? String(c.user_id || c.from_email) : null,
      channel: 'email',
      text
    });
  }

  return {
    freshdesk_domain,
    ticket_id: String(ticket?.id ?? ''),
    actor_agent_id: actor_agent_id ?? null,
    locale: 'ko-KR',
    subject,
    conversation,
    force_refresh: false
  };
}

function getTotalPages(linkHeader) {
  if (!linkHeader) return 1;
  const lastMatch = linkHeader.match(/page=(\d+)>;\s*rel="last"/);
  if (lastMatch) {
    return parseInt(lastMatch[1], 10);
  }
  return 1;
}

function getTicketInsights(args) {
  const ticket_id = args.ticket_id;
  const actor_agent_id = args.actor_agent_id || null;
  const iparams = args.iparams || {};
  const domain = iparams.freshdesk_domain;
  const api_key = iparams.freshdesk_api_key;

  if (!ticket_id) {
    renderData({ status: 400, message: 'ticket_id is required' });
    return;
  }

  if (!domain) {
    renderData({ status: 400, message: 'freshdesk_domain not configured in iparams' });
    return;
  }

  if (!api_key) {
    renderData({ status: 400, message: 'freshdesk_api_key not configured in iparams' });
    return;
  }

  const normalizedDomain = normalizeDomain(domain);

  console.log('Fetching ticket:', ticket_id);
  console.log('Using domain:', normalizedDomain);

  $request.invokeTemplate('fetchTicket', {
    context: { ticket_id: ticket_id },
    iparams: { freshdesk_domain: normalizedDomain, freshdesk_api_key: api_key }
  }).then(function(ticketData) {
    const ticket = JSON.parse(ticketData.response);
    console.log('Ticket fetched:', ticket.id);

    return $request.invokeTemplate('fetchConversations', {
      context: { ticket_id: ticket_id, page: 1 },
      iparams: { freshdesk_domain: normalizedDomain, freshdesk_api_key: api_key }
    }).then(function(firstPageData) {
      return { ticket: ticket, firstPageData: firstPageData };
    });
  }).then(function(result) {
    const ticket = result.ticket;
    const firstPageData = result.firstPageData;
    const firstPageConversations = JSON.parse(firstPageData.response);

    const linkHeader = firstPageData.headers && firstPageData.headers.link;
    const totalPages = getTotalPages(linkHeader);

    console.log('Total conversation pages:', totalPages);
    console.log('First page conversations:', firstPageConversations.length);

    if (totalPages === 1) {
      const structured = toStructuredConversation({
        domain: normalizedDomain,
        ticket: ticket,
        conversations: firstPageConversations,
        actor_agent_id: actor_agent_id
      });

      console.log('Total conversations:', structured.conversation.length);
      renderData(null, { status: 'success', data: structured });
      return;
    }

    const remainingPromises = [];
    for (let page = 2; page <= totalPages; page++) {
      remainingPromises.push(
        $request.invokeTemplate('fetchConversations', {
          context: { ticket_id: ticket_id, page: page },
          iparams: { freshdesk_domain: normalizedDomain, freshdesk_api_key: api_key }
        })
      );
    }

    return Promise.all(remainingPromises).then(function(remainingPagesData) {
      let allConversations = firstPageConversations;
      for (let i = 0; i < remainingPagesData.length; i++) {
        const pageConversations = JSON.parse(remainingPagesData[i].response);
        allConversations = allConversations.concat(pageConversations);
      }

      console.log('Total conversations fetched:', allConversations.length);

      const structured = toStructuredConversation({
        domain: normalizedDomain,
        ticket: ticket,
        conversations: allConversations,
        actor_agent_id: actor_agent_id
      });

      console.log('Total conversation messages:', structured.conversation.length);
      renderData(null, { status: 'success', data: structured });
    }, function(err) {
      console.error('Promise.all error:', err);
      renderData({ status: 500, message: 'Failed to fetch remaining pages: ' + (err.message || 'Unknown error') });
    });
  }, function(err) {
    console.error('Freshdesk API error:', err);
    renderData({ status: err.status || 500, message: 'Failed to fetch ticket and conversations: ' + (err.message || 'Unknown error') });
  });
}

// 환경별 백엔드 주소 정책
// - 운영: 코드 기본값으로 api.wedosoft.net 사용
// - 로컬 개발: BACKEND_BASE_URL 환경변수로 ngrok 등 오버라이드
const PROD_BACKEND_BASE_URL = 'https://agent-platform.fly.dev';

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
  },
  getTicketInsights: function(args) {
    return getTicketInsights(args);
  }
};
