/**
 * FDK Serverless Functions
 * 보안 iparams에 접근하여 프론트엔드에 전달
 */

exports = {
  /**
   * 보안 파라미터 (API 키 등) 가져오기
   * 프론트엔드에서 직접 접근할 수 없는 secure iparams를 서버사이드에서 접근
   */
  getSecureParams: function(args) {
    try {
      // FDK v3.0에서 iparams 접근
      const { iparams } = args;

      // 필요한 파라미터만 추출하여 반환
      const secureData = {
        apiKey: iparams?.freshdesk_api_key,
        domain: iparams?.freshdesk_domain,
        // 테넌트 ID는 도메인에서 추출 (예: company.freshdesk.com → company)
        tenantId: iparams?.freshdesk_domain?.split('.')[0] || ''
      };

      // API 키 존재 여부 확인
      if (!secureData.apiKey) {
        console.error('❌ 서버리스: API 키가 설정되지 않았습니다');
        renderData({ message: 'API key not configured' });
        return;
      }

      // renderData를 사용하여 데이터 반환
      renderData(null, secureData);

    } catch (error) {
      console.error('❌ 서버리스 오류:', error);

      // 오류 발생 시 renderData로 오류 반환
      renderData({ message: error.message || 'Failed to retrieve secure parameters' });
    }
  },

  /**
   * Freshdesk 티켓 필드 목록 가져오기
   * - 프론트에서 외부 호출은 'Route not allowed'로 차단될 수 있으므로 서버리스에서 호출한다.
   * - secure iparams(api key)는 서버리스에서만 접근한다.
   */
  getTicketFields: function(args) {
    try {
      const { iparams } = args;

      const apiKey = iparams?.freshdesk_api_key;
      const domain = iparams?.freshdesk_domain;

      if (!apiKey || !domain) {
        renderData({ message: 'Freshdesk domain/api key not configured' });
        return;
      }

      // FDK serverless runtime에서 request 모듈 사용
      // eslint-disable-next-line global-require
      const request = require('request');

      const url = `https://${domain}/api/v2/ticket_fields`;
      const auth = Buffer.from(`${apiKey}:X`).toString('base64');

      const options = {
        url,
        method: 'GET',
        headers: {
          Authorization: `Basic ${auth}`,
          'Content-Type': 'application/json'
        }
      };

      request(options, function(err, res, body) {
        if (err) {
          renderData({ message: err.message || 'Request failed' });
          return;
        }

        const status = res && (res.statusCode || res.status);
        if (status >= 200 && status < 300) {
          try {
            const parsed = typeof body === 'string' ? JSON.parse(body) : body;
            renderData(null, parsed);
          } catch (e) {
            renderData({ message: 'Failed to parse Freshdesk response' });
          }
          return;
        }

        // non-2xx
        let detail = '';
        try {
          const parsedErr = typeof body === 'string' ? JSON.parse(body) : body;
          detail = parsedErr?.message || parsedErr?.description || '';
        } catch (e) {
          // ignore
        }
        renderData({ message: `Freshdesk API error: ${status}${detail ? ` - ${detail}` : ''}` });
      });
    } catch (error) {
      renderData({ message: error.message || 'Failed to retrieve ticket fields' });
    }
  },

  /**
   * 티켓 생성 이벤트 핸들러
   */
  onTicketCreateHandler: function() {
    // 여기에 티켓 생성 시 실행할 로직 추가
    // 예: 백엔드에 알림, 초기 데이터 수집 등

    return {
      success: true,
      message: 'Ticket create event handled'
    };
  },

  /**
   * 티켓 업데이트 이벤트 핸들러
   */
  onTicketUpdateHandler: function() {
    // 여기에 티켓 업데이트 시 실행할 로직 추가
    // 예: 변경사항 감지, 데이터 재수집 등

    return {
      success: true,
      message: 'Ticket update event handled'
    };
  }
};
