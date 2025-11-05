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
        domain: iparams?.freshdesk_domain
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
