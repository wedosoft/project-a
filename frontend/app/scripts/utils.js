/**
 * utils.js
 * 유틸리티 함수 모음
 * 포맷팅, 상태 변환, 날짜 처리 등 범용 유틸리티 함수들이 포함됩니다.
 */

// 티켓 상태에 따른 CSS 클래스 반환 함수
function getStatusClass(status) {
  switch (status) {
    case 2:
      return "status-open"; // 열림
    case 3:
      return "status-pending"; // 대기중
    case 4:
      return "status-resolved"; // 해결됨
    case 5:
      return "status-closed"; // 닫힘
    default:
      return "status-default"; // 기본값
  }
}

// 텍스트 길이 제한 함수
function truncateText(text, maxLength = 100) {
  if (!text) return "";
  if (text.length <= maxLength) return text;
  return text.substring(0, maxLength) + "...";
}

// 상태 번호를 한글 텍스트로 변환하는 함수
function getStatusText(status) {
  switch (status) {
    case 2:
      return "열림";
    case 3:
      return "대기중";
    case 4:
      return "해결됨";
    case 5:
      return "닫힘";
    default:
      return "알 수 없음";
  }
}

// 우선순위 번호를 한글 텍스트로 변환하는 함수
function getPriorityText(priority) {
  switch (priority) {
    case 1:
      return "낮음";
    case 2:
      return "보통";
    case 3:
      return "높음";
    case 4:
      return "긴급";
    default:
      return "보통";
  }
}

// 우선순위에 따른 CSS 클래스 반환 함수
function getPriorityClass(priority) {
  switch (priority) {
    case 1:
      return "priority-low";
    case 2:
      return "priority-medium";
    case 3:
      return "priority-high";
    case 4:
      return "priority-urgent";
    default:
      return "priority-medium";
  }
}

// 날짜 포맷팅 함수
function formatDate(dateString) {
  if (!dateString) return "";

  try {
    const date = new Date(dateString);
    if (isNaN(date.getTime())) return "잘못된 날짜";

    // 한국 시간대로 변환하여 표시
    const options = {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      timeZone: "Asia/Seoul",
    };

    return date.toLocaleDateString("ko-KR", options);
  } catch (error) {
    console.warn("날짜 포맷팅 오류:", error);
    return "날짜 형식 오류";
  }
}

// 설명 텍스트 포맷팅 함수
function formatDescription(description) {
  if (!description) return "";

  // HTML 태그 제거 및 기본 포맷팅
  return (
    description
      .replace(/<[^>]*>/g, "") // HTML 태그 제거
      .replace(/\n\n+/g, "\n\n") // 연속된 줄바꿈 정리
      .replace(/\n/g, "<br>") // 줄바꿈을 <br>로 변환
      .substring(0, 500) + (description.length > 500 ? "..." : "")
  ); // 길이 제한
}

// 데이터 유효성 검사 함수 (캐시가 오래되었는지 확인)
function isDataStale() {
  if (!globalTicketData.lastLoadTime) return true;
  const now = Date.now();
  const fiveMinutes = 5 * 60 * 1000; // 5분
  return now - globalTicketData.lastLoadTime > fiveMinutes;
}

// 로딩 완료까지 대기하는 함수
async function waitForLoadingComplete() {
  const maxWait = 10000; // 최대 10초 대기
  const checkInterval = 100; // 100ms마다 확인
  let waited = 0;

  while (globalTicketData.isLoading && waited < maxWait) {
    await new Promise((resolve) => setTimeout(resolve, checkInterval));
    waited += checkInterval;
  }

  if (waited >= maxWait) {
    console.warn("⚠️ 로딩 완료 대기 시간 초과");
  }
}

// 모의 추천 솔루션 생성 함수
function generateMockSolutions() {
  return [
    {
      id: "mock_1",
      title: "일반적인 문제 해결 방법",
      content: "이 문제는 보통 다음과 같이 해결할 수 있습니다...",
      category: "일반",
      relevance_score: 0.8,
      source: "지식베이스",
      type: "solution",
    },
    {
      id: "mock_2",
      title: "FAQ 답변",
      content: "자주 묻는 질문에 대한 답변입니다...",
      category: "FAQ",
      relevance_score: 0.7,
      source: "FAQ",
      type: "solution",
    },
    {
      id: "mock_3",
      title: "단계별 가이드",
      content: "문제 해결을 위한 단계별 가이드입니다...",
      category: "가이드",
      relevance_score: 0.6,
      source: "사용자 매뉴얼",
      type: "solution",
    },
  ];
}

// 프론트엔드용 스마트 도메인 파싱 함수
function smartDomainParsingFrontend(inputDomain) {
  if (!inputDomain || !inputDomain.trim()) {
    throw new Error("도메인 입력값이 비어있습니다.");
  }

  let domain = inputDomain.trim().toLowerCase();

  // URL 형태인 경우 도메인 부분만 추출
  if (domain.startsWith("http://") || domain.startsWith("https://")) {
    try {
      const url = new URL(domain);
      domain = url.hostname;
    } catch (e) {
      throw new Error(`URL 파싱 실패: ${domain}`);
    }
  }

  // 이미 완전한 .freshdesk.com 도메인인 경우
  if (domain.endsWith(".freshdesk.com")) {
    const companyId = domain.replace(".freshdesk.com", "");
    if (!companyId || companyId.length < 2) {
      throw new Error(`유효하지 않은 company_id: ${companyId}`);
    }
    return domain;
  }

  // company_id만 입력된 경우
  if (domain.length < 2) {
    throw new Error(`company_id가 너무 짧습니다: ${domain}`);
  }

  // 특수문자 검증 (기본적인 체크)
  if (!/^[a-z0-9\-]+$/.test(domain)) {
    throw new Error(
      `company_id에 허용되지 않는 문자가 포함되어 있습니다: ${domain}`
    );
  }

  return `${domain}.freshdesk.com`;
}

// company_id 추출 함수 (프론트엔드용)
function extractCompanyIdFromDomain(domain) {
  try {
    const normalized = smartDomainParsingFrontend(domain);
    return normalized.replace(".freshdesk.com", "");
  } catch (error) {
    console.error("company_id 추출 실패:", error);
    return null;
  }
}

// 전역 네임스페이스로 내보내기
window.utils = {
  getStatusClass,
  truncateText,
  getStatusText,
  getPriorityText,
  getPriorityClass,
  formatDate,
  formatDescription,
  isDataStale,
  waitForLoadingComplete,
  generateMockSolutions,
  smartDomainParsingFrontend,
  extractCompanyIdFromDomain,
};
