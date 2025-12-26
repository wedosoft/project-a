/**
 * FDK Serverless Functions
 * - secure iparams(시크릿) 접근은 서버리스에서만 가능
 * - Freshdesk API 호출은 config/requests.json 템플릿(invokeTemplate)으로 통일
 */

exports = {
  /**
   * 보안 파라미터 (API 키 등) 가져오기
   * 프론트엔드에서 직접 접근할 수 없는 secure iparams를 서버사이드에서 접근
   */
  getSecureParams: function(args) {
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

};
