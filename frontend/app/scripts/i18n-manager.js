/**
 * 간단한 다국어 지원 시스템
 * 하나의 JSON 파일로 모든 언어 관리
 */

class I18nManager {
    constructor() {
        this.currentLanguage = null; // 초기값 null로 설정
        this.translations = {};
        this.isLoaded = false;
    }

    /**
     * 번역 파일 로드
     */
    async loadTranslations() {
        try {
            const response = await fetch('locales/translations.json');
            this.translations = await response.json();
            this.isLoaded = true;

        } catch (error) {
            this.translations = {};
            this.isLoaded = false;
        }
    }

    /**
     * 현재 언어 설정
     */
    setLanguage(langCode) {
        if (this.translations[langCode]) {
            this.currentLanguage = langCode;
            localStorage.setItem('preferredLanguage', langCode);
            this.updateUI();
        }
    }

    /**
     * 현재 언어에 맞는 로케일 코드 반환
     */
    getLocale() {
        return this.currentLanguage === 'ko' ? 'ko-KR' : 'en-US';
    }

    /**
     * 텍스트 번역
     */
    getText(key) {
        if (!this.isLoaded || !this.currentLanguage) {
            return key;
        }

        const currentLangTexts = this.translations[this.currentLanguage];
        
        if (currentLangTexts && currentLangTexts[key]) {
            return currentLangTexts[key];
        }

        // 폴백: 영어로 시도
        if (this.currentLanguage !== 'en' && this.translations['en'] && this.translations['en'][key]) {
            return this.translations['en'][key];
        }

        // 최종 폴백: 키 그대로 반환
        return key;
    }

    /**
     * 전체 UI 업데이트
     */
    updateUI() {
        // data-i18n 속성을 가진 모든 요소 업데이트 (텍스트 콘텐츠)
        const i18nElements = document.querySelectorAll('[data-i18n]');
        
        i18nElements.forEach(element => {
            const key = element.getAttribute('data-i18n');
            const newText = this.getText(key);
            element.textContent = newText;
        });

        // data-i18n-placeholder 속성을 가진 모든 요소 업데이트 (placeholder)
        const placeholderElements = document.querySelectorAll('[data-i18n-placeholder]');
        
        placeholderElements.forEach(element => {
            const key = element.getAttribute('data-i18n-placeholder');
            element.placeholder = this.getText(key);
        });

        // 언어 토글 버튼 업데이트 (다음 언어 표시)
        const languageCodeElement = document.getElementById('currentLanguageCode');
        if (languageCodeElement) {
            const nextLanguage = this.currentLanguage === 'ko' ? 'EN' : 'KO';
            languageCodeElement.textContent = nextLanguage;
        }

        // HTML lang 속성 업데이트
        document.documentElement.lang = this.currentLanguage;
        
        // 채팅 메시지 시간 포맷 업데이트
        this.updateChatMessageTimes();
        
        // 아티클 헤더 다시 업데이트 (번역 반영)
        this.updateArticlesHeader();
        
        // 티켓 헤더 다시 업데이트 (번역 반영)
        this.updateTicketsHeader();
        
        // 카드 날짜 포맷 업데이트
        this.updateCardDates();
    }

    /**
     * 아티클 헤더 업데이트 (언어 변경 시)
     */
    updateArticlesHeader() {
        if (window.TicketUI && typeof window.TicketUI.updateArticlesHeader === 'function') {
            // 현재 아티클 데이터가 있으면 헤더 업데이트
            const articlesData = window.Core?.state?.data?.kbDocuments;
            if (articlesData && articlesData.length > 0) {
                window.TicketUI.updateArticlesHeader(articlesData);
            }
        }
    }

    /**
     * 티켓 헤더 업데이트 (언어 변경 시)
     */
    updateTicketsHeader() {
        if (window.TicketUI && typeof window.TicketUI.updateTicketsHeader === 'function') {
            // 현재 티켓 데이터가 있으면 헤더 업데이트
            const ticketsData = window.Core?.state?.data?.similarTickets;
            if (ticketsData && ticketsData.length > 0) {
                window.TicketUI.updateTicketsHeader(ticketsData);
            }
        }
    }

    /**
     * 카드 날짜 포맷 업데이트 (언어 변경 시)
     */
    updateCardDates() {
        const metaDateElements = document.querySelectorAll('.meta-item.meta-date');
        
        metaDateElements.forEach(dateElement => {
            const cardElement = dateElement.closest('.content-card');
            if (cardElement) {
                // 티켓 카드인지 아티클 카드인지 구분
                const ticketId = cardElement.getAttribute('data-ticket-id');
                if (ticketId) {
                    // 티켓 카드의 경우
                    const ticketData = window.Core?.state?.data?.similarTickets?.find(t => t.id == ticketId);
                    if (ticketData && ticketData.created_at) {
                        const formattedDate = window.Utils ? window.Utils.formatCardDate(ticketData.created_at) : 'N/A';
                        dateElement.textContent = `📅 ${formattedDate}`;
                    }
                } else {
                    // 아티클 카드의 경우 - data 속성에서 날짜 가져오기
                    const dateData = dateElement.getAttribute('data-date');
                    if (dateData) {
                        const formattedDate = window.Utils ? window.Utils.formatCardDate(dateData) : 'N/A';
                        dateElement.textContent = `📅 ${formattedDate}`;
                    }
                }
            }
        });
    }

    /**
     * 채팅 메시지 시간 포맷 업데이트 (언어 변경 시)
     */
    updateChatMessageTimes() {
        const messageTimeElements = document.querySelectorAll('.message-time');
        
        messageTimeElements.forEach(timeElement => {
            const timestamp = timeElement.getAttribute('data-timestamp');
            if (timestamp) {
                const messageTime = new Date(parseInt(timestamp));
                if (!isNaN(messageTime.getTime())) {
                    const locale = this.getLocale();
                    const formattedTime = messageTime.toLocaleString(locale, {
                        month: 'short',
                        day: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit'
                    });
                    timeElement.textContent = formattedTime;
                }
            }
        });
    }

    /**
     * 저장된 언어 설정 로드 (브라우저 언어 자동 감지)
     */
    loadSavedLanguage() {
        // 브라우저 언어 먼저 감지
        const browserLang = navigator.language || navigator.languages[0] || 'en';
        const browserDetectedLang = browserLang.startsWith('ko') ? 'ko' : 'en';
        
        // 저장된 언어 설정 확인
        const savedLanguage = localStorage.getItem('preferredLanguage');
        
        // 저장된 설정이 있고, 브라우저 언어와 다른 경우에만 저장된 설정 사용
        // 즉, 사용자가 명시적으로 변경한 경우만 유지
        if (savedLanguage && savedLanguage !== browserDetectedLang) {
            this.currentLanguage = savedLanguage;
            return savedLanguage;
        }
        
        // 그 외의 경우는 항상 브라우저 언어 사용
        this.currentLanguage = browserDetectedLang;
        
        // localStorage에 브라우저 감지 결과 저장 (다음 로드시 일관성 유지)
        localStorage.setItem('preferredLanguage', browserDetectedLang);
        
        return browserDetectedLang;
    }
}

// 전역 인스턴스 생성
window.I18nManager = new I18nManager();

/**
 * 언어 토글 함수 (HTML에서 직접 호출)
 */
window.toggleLanguage = function() {
    const currentLang = window.I18nManager.currentLanguage;
    const nextLang = currentLang === 'ko' ? 'en' : 'ko';
    window.I18nManager.setLanguage(nextLang);
};



/**
 * 간편한 번역 함수 (전역 사용)
 */
window.t = function(key) {
    return window.I18nManager.getText(key);
};

/**
 * 초기화 함수
 */
window.initializeI18n = async function() {
    // 번역 파일 먼저 로드
    await window.I18nManager.loadTranslations();
    
    // 그 다음 저장된 언어 설정 적용
    window.I18nManager.loadSavedLanguage();
    
    // UI 업데이트
    window.I18nManager.updateUI();
};

// 스크립트 로드시 즉시 초기화
(async function() {
    await window.I18nManager.loadTranslations();
    window.I18nManager.loadSavedLanguage();
    
    // DOM이 준비되면 UI 업데이트
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            window.I18nManager.updateUI();
        });
    } else {
        window.I18nManager.updateUI();
    }
})();