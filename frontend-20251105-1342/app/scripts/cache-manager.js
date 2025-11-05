/**
 * 새로운 통합 캐시 매니저
 * 모든 티켓 관련 데이터를 체계적으로 관리
 */

class TicketCacheManager {
    constructor() {
        this.version = '2.0.0';
        this.sessionPrefix = 'tcm_session_';
        this.localPrefix = 'tcm_local_';

        // 캐시 키 정의
        this.CACHE_KEYS = {
            // 세션 스토리지 (탭 닫으면 삭제)
            TICKET_SUMMARY: 'ticket_summary',      // 메인 티켓 요약 (구조적/시간순)
            SIMILAR_TICKETS: 'similar_tickets',    // 유사 티켓 검색 결과
            KB_DOCUMENTS: 'kb_documents',          // KB 문서 검색 결과
            TICKET_METADATA: 'ticket_metadata',    // 티켓 헤더 정보

            // 로컬 스토리지 (영구 보관)
            CHAT_RAG: 'chat_rag',                  // RAG 채팅 기록
            CHAT_GENERAL: 'chat_general',          // 일반 채팅 기록
            USER_PREFERENCES: 'user_preferences'   // 사용자 설정
        };

        this.currentTicketId = null;
        this.initialized = false;
    }

    /**
     * 요약 타입 키 매핑 헬퍼 (일관된 키 사용)
     * temporal(시간순) → chronological
     * structural(구조적) → structural
     */
    _mapSummaryType(type) {
        const mapping = {
            'temporal': 'chronological',
            'chronological': 'chronological',
            'structural': 'structural'
        };

        const mappedType = mapping[type] || type;
        console.log(`🔑 요약 타입 매핑: ${type} → ${mappedType}`);
        return mappedType;
    }

    /**
     * 역방향 매핑 (저장된 키에서 UI 타입으로)
     */
    _unmapSummaryType(storageType) {
        const reverseMapping = {
            'chronological': 'temporal',
            'structural': 'structural'
        };

        return reverseMapping[storageType] || storageType;
    }

    /**
     * 캐시 매니저 초기화
     */
    initialize(ticketId) {
        if (!ticketId) {
            throw new Error('❌ 티켓 ID가 필요합니다');
        }

        this.currentTicketId = ticketId;
        this.initialized = true;

        console.log(`✅ 캐시 매니저 초기화 완료 - 티켓 ${ticketId}`);

        // 기존 버전 호환성 체크 및 마이그레이션
        this._checkVersionCompatibility();

        return this;
    }

    /**
     * 버전 호환성 체크 및 기존 캐시 정리
     */
    _checkVersionCompatibility() {
        const versionKey = `${this.localPrefix}cache_version`;
        const currentVersion = localStorage.getItem(versionKey);

        if (!currentVersion || currentVersion !== this.version) {
            console.log('🔄 캐시 시스템 업그레이드 - 기존 캐시 정리 중...');
            this._cleanupLegacyCache();
            localStorage.setItem(versionKey, this.version);
        }
    }

    /**
     * 기존 레거시 캐시 완전 정리
     */
    _cleanupLegacyCache() {
        const keysToRemove = [];

        // sessionStorage 정리
        for (let i = 0; i < sessionStorage.length; i++) {
            const key = sessionStorage.key(i);
            if (key && (
                key.startsWith('backend_ticket_') ||
                key.startsWith('ticket_data_') ||
                key.includes('cache_') ||
                key.includes('modal_')
            )) {
                keysToRemove.push(key);
            }
        }

        keysToRemove.forEach(key => sessionStorage.removeItem(key));

        // localStorage에서 채팅 기록 외 정리
        const localKeysToRemove = [];
        for (let i = 0; i < localStorage.length; i++) {
            const key = localStorage.key(i);
            if (key && key.includes('chat_history_') && !key.includes(this.localPrefix)) {
                // 기존 채팅 기록은 새 형식으로 마이그레이션
                this._migrateChatHistory(key);
                localKeysToRemove.push(key);
            }
        }

        localKeysToRemove.forEach(key => localStorage.removeItem(key));

        console.log(`🧹 레거시 캐시 정리 완료: ${keysToRemove.length + localKeysToRemove.length}개 항목`);
    }

    /**
     * 기존 채팅 기록 마이그레이션
     */
    _migrateChatHistory(oldKey) {
        try {
            const oldData = localStorage.getItem(oldKey);
            if (!oldData) return;

            const parsed = JSON.parse(oldData);
            const ticketId = oldKey.replace('chat_history_', '');

            if (parsed.chatHistory) {
                // RAG 채팅
                if (parsed.chatHistory.rag) {
                    this._setLocalStorage(ticketId, this.CACHE_KEYS.CHAT_RAG, parsed.chatHistory.rag);
                }

                // 일반 채팅
                if (parsed.chatHistory.chat) {
                    this._setLocalStorage(ticketId, this.CACHE_KEYS.CHAT_GENERAL, parsed.chatHistory.chat);
                }
            }
        } catch (e) {
            console.warn('⚠️ 채팅 기록 마이그레이션 실패:', e);
        }
    }

    /**
     * 티켓 요약 저장 (구조적 + 시간순)
     */
    saveTicketSummary(summaryData) {
        this._ensureInitialized();

        // 기존 캐시 데이터 조회
        const existingData = this._getSessionStorage(this.currentTicketId, this.CACHE_KEYS.TICKET_SUMMARY) || {};

        // 새 데이터와 기존 데이터 병합
        const data = {
            structural: summaryData.structural || existingData.structural || summaryData.summary || '',
            chronological: summaryData.chronological || existingData.chronological || '',
            emotionData: summaryData.emotionData || existingData.emotionData || null,
            rendering: {
                ...(existingData.rendering || {}),
                ...(summaryData.rendering || {})
            },
            metadata: {
                ticketId: this.currentTicketId,
                lastUpdated: Date.now(),
                hasChronological: !!(summaryData.chronological || existingData.chronological),
                hasStructural: !!(summaryData.structural || existingData.structural || summaryData.summary)
            }
        };

        this._setSessionStorage(this.currentTicketId, this.CACHE_KEYS.TICKET_SUMMARY, data);
        console.log('💾 티켓 요약 저장 완료:', {
            structural: !!data.structural,
            chronological: !!data.chronological,
            rendering: Object.keys(data.rendering || {})
        });

        return this;
    }

    /**
     * 티켓 요약 조회
     */
    getTicketSummary() {
        this._ensureInitialized();
        return this._getSessionStorage(this.currentTicketId, this.CACHE_KEYS.TICKET_SUMMARY);
    }

    /**
     * 유사 티켓 저장
     */
    saveSimilarTickets(tickets) {
        this._ensureInitialized();

        const data = {
            tickets: tickets || [],
            metadata: {
                lastUpdated: Date.now(),
                count: tickets?.length || 0
            }
        };

        this._setSessionStorage(this.currentTicketId, this.CACHE_KEYS.SIMILAR_TICKETS, data);
        console.log(`💾 유사 티켓 저장 완료: ${data.metadata.count}개`);

        return this;
    }

    /**
     * 유사 티켓 조회
     */
    getSimilarTickets() {
        this._ensureInitialized();
        return this._getSessionStorage(this.currentTicketId, this.CACHE_KEYS.SIMILAR_TICKETS);
    }

    /**
     * KB 문서 저장
     */
    saveKBDocuments(documents) {
        this._ensureInitialized();

        const data = {
            documents: documents || [],
            metadata: {
                lastUpdated: Date.now(),
                count: documents?.length || 0
            }
        };

        this._setSessionStorage(this.currentTicketId, this.CACHE_KEYS.KB_DOCUMENTS, data);
        console.log(`💾 KB 문서 저장 완료: ${data.metadata.count}개`);

        return this;
    }

    /**
     * KB 문서 조회
     */
    getKBDocuments() {
        this._ensureInitialized();
        return this._getSessionStorage(this.currentTicketId, this.CACHE_KEYS.KB_DOCUMENTS);
    }

    /**
     * 티켓 메타데이터 저장
     */
    saveTicketMetadata(metadata) {
        this._ensureInitialized();

        const data = {
            ...metadata,
            lastUpdated: Date.now()
        };

        this._setSessionStorage(this.currentTicketId, this.CACHE_KEYS.TICKET_METADATA, data);
        console.log('💾 티켓 메타데이터 저장 완료');

        return this;
    }

    /**
     * 티켓 메타데이터 조회
     */
    getTicketMetadata() {
        this._ensureInitialized();
        return this._getSessionStorage(this.currentTicketId, this.CACHE_KEYS.TICKET_METADATA);
    }

    /**
     * RAG 채팅 기록 저장
     */
    saveRagChatHistory(chatHistory) {
        this._ensureInitialized();

        const data = {
            messages: chatHistory || [],
            metadata: {
                lastUpdated: Date.now(),
                messageCount: chatHistory?.length || 0
            }
        };

        this._setLocalStorage(this.currentTicketId, this.CACHE_KEYS.CHAT_RAG, data);
        console.log(`💾 RAG 채팅 기록 저장: ${data.metadata.messageCount}개 메시지`);

        return this;
    }

    /**
     * RAG 채팅 기록 조회
     */
    getRagChatHistory() {
        this._ensureInitialized();
        return this._getLocalStorage(this.currentTicketId, this.CACHE_KEYS.CHAT_RAG);
    }

    /**
     * 일반 채팅 기록 저장
     */
    saveGeneralChatHistory(chatHistory) {
        this._ensureInitialized();

        const data = {
            messages: chatHistory || [],
            metadata: {
                lastUpdated: Date.now(),
                messageCount: chatHistory?.length || 0
            }
        };

        this._setLocalStorage(this.currentTicketId, this.CACHE_KEYS.CHAT_GENERAL, data);
        console.log(`💾 일반 채팅 기록 저장: ${data.metadata.messageCount}개 메시지`);

        return this;
    }

    /**
     * 일반 채팅 기록 조회
     */
    getGeneralChatHistory() {
        this._ensureInitialized();
        return this._getLocalStorage(this.currentTicketId, this.CACHE_KEYS.CHAT_GENERAL);
    }

    /**
     * 채팅 기록 조회 (구버전 호환성)
     * RAG와 일반 채팅을 통합하여 반환
     */
    getChatHistory() {
        this._ensureInitialized();

        const ragHistory = this.getRagChatHistory();
        const generalHistory = this.getGeneralChatHistory();

        return {
            rag: ragHistory?.messages || [],
            chat: generalHistory?.messages || [],
            metadata: {
                ragCount: ragHistory?.metadata?.messageCount || 0,
                generalCount: generalHistory?.metadata?.messageCount || 0,
                lastUpdated: Math.max(
                    ragHistory?.metadata?.lastUpdated || 0,
                    generalHistory?.metadata?.lastUpdated || 0
                )
            }
        };
    }

    /**
     * 채팅 기록 통계 조회 (구버전 호환성)
     */
    getChatHistoryStats() {
        this._ensureInitialized();

        const chatHistory = this.getChatHistory();

        return {
            current: {
                rag: chatHistory.metadata.ragCount,
                chat: chatHistory.metadata.generalCount,
                total: chatHistory.metadata.ragCount + chatHistory.metadata.generalCount
            },
            ragCount: chatHistory.metadata.ragCount,
            generalCount: chatHistory.metadata.generalCount,
            totalCount: chatHistory.metadata.ragCount + chatHistory.metadata.generalCount,
            lastUpdated: chatHistory.metadata.lastUpdated,
            ticketId: this.ticketId
        };
    }

    /**
     * 통합 채팅 히스토리 저장 (core.js에서 호출되는 함수)
     */
    saveChatHistory(chatHistoryObject) {
        this._ensureInitialized();

        // 🔍 디버깅: 채팅 히스토리 저장 확인
        console.log('🔍 [DEBUG] TicketCacheManager 채팅 히스토리 저장:', {
            ragMessages: chatHistoryObject?.rag?.length || 0,
            chatMessages: chatHistoryObject?.chat?.length || 0,
            inputData: chatHistoryObject
        });

        if (chatHistoryObject) {
            // RAG 모드 히스토리 저장
            if (chatHistoryObject.rag && Array.isArray(chatHistoryObject.rag)) {
                this.saveRagChatHistory(chatHistoryObject.rag);
            }

            // Chat 모드 히스토리 저장  
            if (chatHistoryObject.chat && Array.isArray(chatHistoryObject.chat)) {
                this.saveGeneralChatHistory(chatHistoryObject.chat);
            }
        }
    }

    /**
     * 채팅 컨텍스트 생성 (백엔드 전송용)
     */
    createChatContext() {
        this._ensureInitialized();

        const summary = this.getTicketSummary();
        const metadata = this.getTicketMetadata();

        if (!summary) {
            console.warn('⚠️ 티켓 요약이 없어 컨텍스트 생성 불가');
            return null;
        }

        return {
            ticketId: this.currentTicketId,
            summary: {
                structural: summary.structural,
                chronological: summary.chronological,
                hasChronological: summary.metadata?.hasChronological || false
            },
            emotionData: summary.emotionData,
            metadata: {
                ticketId: this.currentTicketId,
                lastUpdated: summary.metadata?.lastUpdated,
                ...metadata
            }
        };
    }

    /**
     * 사용자 채팅 기록 삭제
     */
    clearChatHistory(chatType = 'all') {
        this._ensureInitialized();

        if (chatType === 'all' || chatType === 'rag') {
            this._removeLocalStorage(this.currentTicketId, this.CACHE_KEYS.CHAT_RAG);
            console.log('🗑️ RAG 채팅 기록 삭제');
        }

        if (chatType === 'all' || chatType === 'general') {
            this._removeLocalStorage(this.currentTicketId, this.CACHE_KEYS.CHAT_GENERAL);
            console.log('🗑️ 일반 채팅 기록 삭제');
        }

        return this;
    }

    /**
     * 특정 티켓의 모든 캐시 데이터 조회
     */
    getAllCachedData() {
        this._ensureInitialized();

        return {
            summary: this.getTicketSummary(),
            similarTickets: this.getSimilarTickets(),
            kbDocuments: this.getKBDocuments(),
            metadata: this.getTicketMetadata(),
            chatRag: this.getRagChatHistory(),
            chatGeneral: this.getGeneralChatHistory()
        };
    }

    /**
     * 캐시 상태 확인
     */
    getCacheStatus() {
        this._ensureInitialized();

        const data = this.getAllCachedData();

        return {
            ticketId: this.currentTicketId,
            summary: !!data.summary,
            similarTickets: data.similarTickets?.metadata?.count || 0,
            kbDocuments: data.kbDocuments?.metadata?.count || 0,
            chatRag: data.chatRag?.metadata?.messageCount || 0,
            chatGeneral: data.chatGeneral?.metadata?.messageCount || 0,
            lastUpdated: Math.max(
                data.summary?.metadata?.lastUpdated || 0,
                data.similarTickets?.metadata?.lastUpdated || 0,
                data.kbDocuments?.metadata?.lastUpdated || 0
            )
        };
    }

    /**
     * 특정 티켓 캐시 완전 삭제
     */
    clearTicketCache(ticketId = null) {
        const targetTicketId = ticketId || this.currentTicketId;

        if (!targetTicketId) {
            console.warn('⚠️ 삭제할 티켓 ID가 없습니다');
            return this;
        }

        // 세션 스토리지 정리
        Object.values(this.CACHE_KEYS).forEach(key => {
            if (key !== this.CACHE_KEYS.CHAT_RAG && key !== this.CACHE_KEYS.CHAT_GENERAL) {
                this._removeSessionStorage(targetTicketId, key);
            }
        });

        console.log(`🗑️ 티켓 ${targetTicketId} 캐시 삭제 완료 (채팅 기록 제외)`);

        return this;
    }

    // === 내부 헬퍼 메서드들 ===

    _ensureInitialized() {
        if (!this.initialized || !this.currentTicketId) {
            throw new Error('❌ 캐시 매니저가 초기화되지 않았습니다. initialize(ticketId)를 먼저 호출하세요.');
        }
    }

    _getSessionKey(ticketId, cacheKey) {
        return `${this.sessionPrefix}${ticketId}_${cacheKey}`;
    }

    _getLocalKey(ticketId, cacheKey) {
        return `${this.localPrefix}${ticketId}_${cacheKey}`;
    }

    _setSessionStorage(ticketId, cacheKey, data) {
        try {
            const key = this._getSessionKey(ticketId, cacheKey);
            sessionStorage.setItem(key, JSON.stringify(data));
        } catch (e) {
            console.error('❌ 세션 스토리지 저장 실패:', e);
        }
    }

    _getSessionStorage(ticketId, cacheKey) {
        try {
            const key = this._getSessionKey(ticketId, cacheKey);
            const data = sessionStorage.getItem(key);
            return data ? JSON.parse(data) : null;
        } catch (e) {
            console.error('❌ 세션 스토리지 조회 실패:', e);
            return null;
        }
    }

    _removeSessionStorage(ticketId, cacheKey) {
        try {
            const key = this._getSessionKey(ticketId, cacheKey);
            sessionStorage.removeItem(key);
        } catch (e) {
            console.error('❌ 세션 스토리지 삭제 실패:', e);
        }
    }

    _setLocalStorage(ticketId, cacheKey, data) {
        try {
            const key = this._getLocalKey(ticketId, cacheKey);
            localStorage.setItem(key, JSON.stringify(data));
        } catch (e) {
            console.error('❌ 로컬 스토리지 저장 실패:', e);
        }
    }

    _getLocalStorage(ticketId, cacheKey) {
        try {
            const key = this._getLocalKey(ticketId, cacheKey);
            const data = localStorage.getItem(key);
            return data ? JSON.parse(data) : null;
        } catch (e) {
            console.error('❌ 로컬 스토리지 조회 실패:', e);
            return null;
        }
    }

    _removeLocalStorage(ticketId, cacheKey) {
        try {
            const key = this._getLocalKey(ticketId, cacheKey);
            localStorage.removeItem(key);
        } catch (e) {
            console.error('❌ 로컬 스토리지 삭제 실패:', e);
        }
    }
}

// 전역 인스턴스 생성
window.TicketCacheManager = new TicketCacheManager();

// 디버깅용 헬퍼
window.debugCache = {
    status: () => window.TicketCacheManager.getCacheStatus(),
    data: () => window.TicketCacheManager.getAllCachedData(),
    summary: () => window.TicketCacheManager.getTicketSummary(),
    clear: (ticketId) => window.TicketCacheManager.clearTicketCache(ticketId),
    clearChat: (type) => window.TicketCacheManager.clearChatHistory(type),

    // 요약 토글 테스트용
    testToggle: (type) => {
        const summary = window.TicketCacheManager.getTicketSummary();
        const mappedType = window.TicketCacheManager._mapSummaryType(type);
        console.log(`🔍 ${type} (${mappedType}) 캐시 확인:`, {
            cached: !!summary,
            hasType: summary ? !!summary[mappedType] : false,
            content: summary ? summary[mappedType] : 'null',
            allKeys: summary ? Object.keys(summary) : [],
            renderingKeys: summary?.rendering ? Object.keys(summary.rendering) : []
        });
        return summary ? summary[mappedType] : null;
    },

    // 세션 복원 테스트용
    testSessionRestore: () => {
        const allData = window.TicketCacheManager.getAllCachedData();
        const metadata = window.TicketCacheManager.getTicketMetadata();

        console.log('🔍 세션 복원 테스트:', {
            hasSummary: !!allData?.summary,
            hasSimilarTickets: !!allData?.similarTickets,
            hasKBDocuments: !!allData?.kbDocuments,
            hasMetadata: !!metadata,
            summaryType: metadata?.currentSummaryType,
            chatMode: metadata?.chatMode,
            emotion: metadata?.emotion?.emotion,
            totalCacheSize: JSON.stringify(allData).length
        });

        // UI 렌더링 시뮬레이션
        if (window.TicketUI && window.TicketUI._renderFromNewCacheSystem) {
            console.log('🚀 UI 렌더링 시뮬레이션 시작...');
            const renderData = {
                summary: allData?.summary,
                similarTickets: allData?.similarTickets,
                kbDocuments: allData?.kbDocuments,
                metadata: metadata
            };
            window.TicketUI._renderFromNewCacheSystem(renderData);
        }

        return allData;
    },

    // 메타데이터 상세 확인
    testMetadata: () => {
        const metadata = window.TicketCacheManager.getTicketMetadata();
        console.log('🔍 메타데이터 상세:', metadata);
        return metadata;
    },

    // 키 매핑 테스트용
    testKeyMapping: () => {
        console.log('🔑 키 매핑 테스트:');
        const testTypes = ['structural', 'temporal', 'chronological'];
        testTypes.forEach(type => {
            const mapped = window.TicketCacheManager._mapSummaryType(type);
            const unmapped = window.TicketCacheManager._unmapSummaryType(mapped);
            console.log(`  ${type} → ${mapped} → ${unmapped}`);
        });

        const summary = window.TicketCacheManager.getTicketSummary();
        if (summary) {
            console.log('📦 실제 캐시 키:', Object.keys(summary));
            console.log('🎨 렌더링 키:', summary.rendering ? Object.keys(summary.rendering) : []);
        }
    },

    // 완전한 캐시 상태 확인
    checkCompleteCache: () => {
        const allData = window.TicketCacheManager.getAllCachedData();
        const isComplete = !!(allData?.summary && allData?.similarTickets && allData?.kbDocuments);

        console.log('🔍 완전한 캐시 상태 확인:', {
            hasComplete: isComplete,
            summary: !!allData?.summary,
            similarTickets: !!allData?.similarTickets,
            kbDocuments: !!allData?.kbDocuments,
            metadata: !!window.TicketCacheManager.getTicketMetadata(),
            chatHistory: !!window.TicketCacheManager.getChatHistory()
        });

        return isComplete;
    },

    // 세션 복원 시뮬레이션
    simulateModalReopen: () => {
        console.log('🚪 모달 재오픈 시뮬레이션 시작...');

        // 1. 완전한 캐시 확인
        const isComplete = window.debugCache.checkCompleteCache();

        // 2. Core 상태 복원 시뮬레이션
        if (window.Core?._restoreFromNewCacheSystem) {
            const restored = window.Core._restoreFromNewCacheSystem();
            console.log(`📋 Core 데이터 복원: ${restored ? '성공' : '실패'}`);
        }

        // 3. UI 렌더링 시뮬레이션
        if (window.TicketUI?._renderFromNewCacheSystem) {
            const allData = window.TicketCacheManager.getAllCachedData();
            const metadata = window.TicketCacheManager.getTicketMetadata();

            const renderData = {
                summary: allData?.summary,
                similarTickets: allData?.similarTickets,
                kbDocuments: allData?.kbDocuments,
                metadata: metadata
            };

            const rendered = window.TicketUI._renderFromNewCacheSystem(renderData);
            console.log(`🎨 UI 렌더링: ${rendered ? '성공' : '실패'}`);
        }

        // 4. API 호출 예상 여부
        console.log(`🌐 API 호출 예상: ${isComplete ? '없음 (캐시 완전)' : '있음 (캐시 불완전)'}`);

        return isComplete;
    }
};

console.log('✅ 새로운 캐시 매니저 로드 완료 - debugCache.simulateModalReopen()으로 모달 재오픈 테스트 가능');