/**
 * Data Collection Manager Web Component
 * 데이터 수집 관리 컴포넌트 - 시작/중지/재개/취소 제어
 */
class DataCollectionManager extends HTMLElement {
    constructor() {
        super();
        this.currentJobId = null;
        this.isRunning = false;
        this.progressInterval = null;
        this.logInterval = null;
        this.lastLoggedProgress = -1; // 마지막으로 로그에 출력한 진행률 추적

        // Job types from original admin.js
        this.JOB_TYPES = {
            INITIAL_SYNC: 'initial_sync',
            INCREMENTAL_SYNC: 'incremental_sync',
            FULL_REFRESH: 'full_refresh',
            SYNC_SUMMARIES: 'sync_summaries'
        };

        // Progress stages
        this.PROGRESS_STAGES = {
            PREPARING: { min: 0, max: 15, message: '수집 준비 중...' },
            FETCHING: { min: 15, max: 70, message: '티켓 데이터 수집 중...' },
            PROCESSING: { min: 70, max: 95, message: '데이터 처리 및 분석 중...' },
            COMPLETED: { min: 95, max: 100, message: '수집 완료' }
        };

        this.initializeBackendConfig();
    }

    initializeBackendConfig() {
        // backend-config.js의 getUrl 메서드 사용
        if (!window.BACKEND_CONFIG?.getUrl) {
            console.error('백엔드 설정이 초기화되지 않았습니다. backend-config.js를 확인하세요.');
            throw new Error('Backend configuration not initialized');
        }
    }

    connectedCallback() {
        this.render();
        this.setupEventListeners();
        this.waitForInitializationAndLoad();
        // 진행률 바 초기화는 상태 복원 후에 수행
    }

    async waitForInitializationAndLoad() {
        // Admin Console 초기화를 기다림
        let retryCount = 0;
        const maxRetries = 50; // 최대 5초 대기 (100ms * 50)

        while (retryCount < maxRetries) {
            if (window.adminUtils?.isInitialized() &&
                window.adminConsole?.apiKey &&
                window.adminConsole?.tenantId &&
                window.adminConsole?.domain) {

                await this.loadInitialState();
                return;
            }

            await new Promise(resolve => setTimeout(resolve, 100));
            retryCount++;
        }

        // 초기화 타임아웃
        const errorMsg = `Admin Console 초기화 타임아웃 (${maxRetries * 100}ms)`;
        console.error('❌', errorMsg);
        this.addLog('error', `❌ ${errorMsg} - 페이지를 새로고침해주세요.`);
        this.addLog('info', '🔄 새로고침 후에도 문제가 지속되면 Freshdesk 앱을 재설치해주세요.');
        this.initializeProgressBar();
    }

    initializeProgressBar() {
        // 진행률 바를 강제로 0%로 초기화
        setTimeout(() => {
            const progressBar = this.querySelector('#collectionProgressBar');
            const progressPercentage = this.querySelector('#progressPercentage');
            const progressDetails = this.querySelector('#progressDetails');

            if (progressBar) {
                progressBar.style.setProperty('width', '0%', 'important');
                progressBar.setAttribute('aria-valuenow', 0);
                console.log('🔄 진행률 바 초기화됨');
            }
            if (progressPercentage) {
                progressPercentage.textContent = '0%';
            }
            if (progressDetails) {
                progressDetails.textContent = '대기중...';
            }
        }, 100);
    }

    render() {
        this.innerHTML = `
            <div class="row">
                <!-- Left: Control Panel -->
                <div class="col-md-6">
                    <!-- Collection Configuration -->
                    <div class="card mb-3">
                        <div class="card-body">
                            <h5 class="mb-3">수집 설정</h5>
                            
                            <!-- Date Range -->
                            <div class="form-group">
                                <label class="form-label">수집 기간</label>
                                <div class="row">
                                    <div class="col-6">
                                        <input type="date" class="form-control" id="start_date" placeholder="시작일">
                                        <small class="form-text">시작일 (기본: 10년 전)</small>
                                    </div>
                                    <div class="col-6">
                                        <input type="date" class="form-control" id="end_date" placeholder="종료일">
                                        <small class="form-text">종료일 (기본: 오늘)</small>
                                    </div>
                                </div>
                            </div>
                            
                            <!-- Collection Target -->
                            <div class="form-group">
                                <label class="form-label">수집 대상</label>
                                <div class="row">
                                    <div class="col-6">
                                        <div class="custom-control custom-checkbox">
                                            <input type="checkbox" class="custom-control-input" id="collect_tickets" checked>
                                            <label class="custom-control-label" for="collect_tickets">
                                                티켓 수집
                                                <small class="form-text d-block">고객 문의 및 지원 티켓</small>
                                            </label>
                                        </div>
                                    </div>
                                    <div class="col-6">
                                        <div class="custom-control custom-checkbox">
                                            <input type="checkbox" class="custom-control-input" id="collect_kb" checked>
                                            <label class="custom-control-label" for="collect_kb">
                                                지식베이스 수집
                                                <small class="form-text d-block">FAQ 및 도움말 아티클</small>
                                            </label>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            
                            <!-- Collection Mode -->
                            <div class="form-group">
                                <label class="form-label">수집 방식</label>
                                <div class="custom-control custom-radio mb-2">
                                    <input type="radio" class="custom-control-input" id="quick_collection" name="collection_mode" value="incremental" checked>
                                    <label class="custom-control-label" for="quick_collection">
                                        <strong>🚀 증분 수집</strong>
                                        <small class="form-text d-block" style="color: #10b981;">최신 변경사항만 즉시 수집합니다 (기존 데이터 유지)</small>
                                    </label>
                                </div>
                                <div class="custom-control custom-radio mb-3">
                                    <input type="radio" class="custom-control-input" id="full_collection" name="collection_mode" value="initial">
                                    <label class="custom-control-label" for="full_collection">
                                        <strong>🔄 전체 수집</strong>
                                        <small class="form-text d-block" style="color: #6b7280;">
                                            현재 테넌트 데이터를 완전히 삭제하고 전체 재수집합니다<br>
                                            <span style="color: #dc2626;">⚠️ purge 옵션: 기존 데이터가 모두 삭제됩니다</span>
                                        </small>
                                    </label>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Music Player Style Controls -->
                    <div class="player-controls">
                        <button class="player-btn player-btn-primary" id="playBtn" title="시작">
                            <i class="fas fa-play"></i>
                        </button>
                        <button class="player-btn player-btn-secondary" id="pauseBtn" title="일시정지" disabled>
                            <i class="fas fa-pause"></i>
                        </button>
                        <button class="player-btn player-btn-secondary" id="stopBtn" title="중지" disabled>
                            <i class="fas fa-stop"></i>
                        </button>
                        <button class="player-btn player-btn-secondary" id="cancelBtn" title="취소" disabled>
                            <i class="fas fa-times"></i>
                        </button>
                        <div class="player-status">
                            <div class="player-status-title">현재 상태</div>
                            <div class="player-status-text" id="collectionStatus">대기중</div>
                        </div>
                    </div>
                </div>
                
                <!-- Right: Progress and Logs -->
                <div class="col-md-6">
                    <div class="card">
                        <div class="card-body" style="display: flex; flex-direction: column;">
                            <!-- Progress Section -->
                            <div class="progress-section">
                                <div class="progress-header">
                                    <div class="progress-title">수집 진행률</div>
                                    <div class="progress-percentage" id="progressPercentage">0%</div>
                                </div>
                                <div class="progress">
                                    <div class="progress-bar progress-bar-animated" id="collectionProgressBar" style="width: 0%;">
                                    </div>
                                </div>
                                <div class="text-muted" id="progressDetails">
                                    대기중...
                                </div>
                            </div>
                            
                            <!-- Log Viewer -->
                            <div class="log-viewer" id="logViewer">
                                <div class="log-entry">
                                    <span class="log-timestamp">00:00:00</span>
                                    <span class="log-level-info">INFO</span> <span data-i18n="log_system_ready">시스템 준비 완료</span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    setupEventListeners() {
        // Music Player Controls
        this.querySelector('#playBtn')?.addEventListener('click', () => this.startCollection());
        this.querySelector('#pauseBtn')?.addEventListener('click', () => this.pauseCollection());
        this.querySelector('#stopBtn')?.addEventListener('click', () => this.stopCollection());
        this.querySelector('#cancelBtn')?.addEventListener('click', () => this.cancelCollection());

        // 수동 상태 새로고침 버튼 추가
        this.querySelector('#refreshStatusBtn')?.addEventListener('click', () => this.refreshStatus());

        // Collection Target Checkboxes
        this.querySelector('#collect_tickets')?.addEventListener('change', () => this.updateControlsState());
        this.querySelector('#collect_kb')?.addEventListener('change', () => this.updateControlsState());
    }

    async loadInitialState() {
        try {
            // 기본 날짜 설정 (시작일: 10년 전, 종료일: 오늘)
            this.setDefaultDates();

            // 백엔드에서 현재 상태 확인 (실행 중인 작업이 있는지)
            await this.checkRunningJobs();

            // 상태 복원 완료 후 UI 업데이트
            this.updateControlsState();

            this.addLog('success', '데이터 수집 관리자 초기화 완료');
        } catch (error) {
            console.error('초기 상태 로드 실패:', error);
            this.addLog('error', `❌ 상태 복원 실패: ${error.message}`);
            // 실패시에도 진행률 바 초기화
            this.initializeProgressBar();
        }
    }

    setDefaultDates() {
        try {
            const today = new Date();
            const tenYearsAgo = new Date();
            tenYearsAgo.setFullYear(today.getFullYear() - 10);

            // 날짜를 YYYY-MM-DD 형식으로 변환
            const formatDate = (date) => {
                return date.toISOString().split('T')[0];
            };

            // 기본값 설정
            const startDateInput = this.querySelector('#start_date');
            const endDateInput = this.querySelector('#end_date');

            if (startDateInput && !startDateInput.value) {
                startDateInput.value = formatDate(tenYearsAgo);
            }

            if (endDateInput && !endDateInput.value) {
                endDateInput.value = formatDate(today);
            }

        } catch (error) {
            console.error('날짜 기본값 설정 실패:', error);
        }
    }

    // NOTE: checkRunningJobs는 아래(단일 구현)만 유지합니다.

    resetState(status) {
        this.currentJobId = null;
        this.isRunning = false;
        this.updateStatus(status);
        this.stopProgressPolling();
    }

    setupPageRefreshHandling() {
        // 페이지 종료 전 상태 저장 (선택적)
        window.addEventListener('beforeunload', () => {
            console.log('📄 페이지 종료 감지됨');
        });

        // 페이지 표시 시 상태 재확인 (뒤로가기/앞으로가기 대응)
        document.addEventListener('visibilitychange', () => {
            if (!document.hidden && this.isConnected) {
                console.log('👁️ 페이지 다시 표시됨 - 상태 재확인');
                setTimeout(() => {
                    this.checkRunningJobs();
                }, 1000);
            }
        });
    }

    getHeaders() {
        // adminUtils를 통해 중앙화된 헤더 관리 사용
        try {
            if (window.adminUtils && window.adminUtils.getApiHeaders) {
                return window.adminUtils.getApiHeaders();
            } else {
                throw new Error('adminUtils가 초기화되지 않았습니다. 관리자 콘솔이 완전히 로드되지 않은 상태에서는 데이터 수집을 시작할 수 없습니다.');
            }
        } catch (error) {
            console.error('🚨 헤더 구성 실패:', error.message);
            throw error; // 에러를 다시 던져서 상위에서 처리하도록 함
        }
    }

    async waitForAdminUtils(maxWaitTime = 5000) {
        // adminUtils가 준비될 때까지 최대 5초 대기
        const startTime = Date.now();
        while (!window.adminUtils?.getApiHeaders && (Date.now() - startTime) < maxWaitTime) {
            await new Promise(resolve => setTimeout(resolve, 100));
        }
        return window.adminUtils?.getApiHeaders !== undefined;
    }

    async checkRunningJobs() {
        try {
            // adminUtils가 준비될 때까지 대기
            const isReady = await this.waitForAdminUtils();
            if (!isReady) {
                console.warn('⚠️ adminUtils 초기화 대기 시간 초과. 상태 확인을 건너뜁니다.');
                this.addLog('warn', '관리자 콘솔 초기화가 완료되지 않아 작업 상태를 확인할 수 없습니다.');
                return;
            }

            // 데이터 수집 상태 API 호출
            const response = await fetch(window.BACKEND_CONFIG.getUrl('/admin/data-collection/status'), {
                headers: this.getHeaders()
            });

            if (response.ok) {
                const result = await response.json();

                // 상태에 따라 UI 복원
                if (result.is_running) {
                    // 실행 중인 작업이 있는 경우
                    const runningJob = result.recent_jobs.find(job => job.status === 'running');
                    if (runningJob) {
                        console.log('🔄 실행 중인 작업 복원:', runningJob.job_id);
                        this.currentJobId = runningJob.job_id;
                        this.isRunning = true;
                        this.updateStatus('running');
                        this.addLog('info', `🔄 실행 중인 작업 복원됨: ${runningJob.job_id}`);

                        // 현재 진행률로 UI 업데이트
                        this.updateProgress(result);
                    }
                } else if (result.is_paused) {
                    // 일시정지된 작업이 있는 경우
                    const pausedJob = result.recent_jobs.find(job => job.status === 'paused');
                    if (pausedJob) {
                        console.log('⏸️ 일시정지된 작업 복원:', pausedJob.job_id);
                        this.currentJobId = pausedJob.job_id;
                        this.isRunning = false;
                        this.updateStatus('paused');
                        this.addLog('info', `⏸️ 일시정지된 작업 복원됨: ${pausedJob.job_id}`);

                        // 현재 진행률로 UI 업데이트
                        this.updateProgress(result);
                    }
                } else {
                    // 활성 작업이 없는 경우
                    this.resetState('idle');
                    this.initializeProgressBar(); // 진행률 바 초기화

                    if (result.total_jobs === 0) {
                        this.addLog('info', '🎯 최초 사용 - 데이터 수집을 시작하세요');
                    } else {
                        this.addLog('info', '📋 대기 중 - 모든 작업 완료');
                        // 완료된 작업의 최신 상태 표시
                        this.updateProgress(result);
                    }
                }

                // 페이지 새로고침 감지를 위한 이벤트 리스너 추가
                this.setupPageRefreshHandling();

            } else {
                console.warn('상태 API 호출 실패:', response.status, response.statusText);
                this.addLog('warning', `⚠️ 상태 확인 실패: ${response.status}`);
                this.initializeProgressBar();
            }
        } catch (error) {
            console.error('실행 중인 작업 확인 실패:', error);
            this.addLog('error', `❌ 상태 복원 실패: ${error.message}`);
            this.initializeProgressBar();
        }
    }

    async startCollection() {
        // 현재 상태가 일시정지인 경우 재개 호출
        const currentStatus = this.querySelector('#collectionStatus').textContent;
        if (currentStatus === '일시정지') {
            await this.resumeCollection();
            return;
        }

        const collectTickets = this.querySelector('#collect_tickets').checked;
        const collectKb = this.querySelector('#collect_kb').checked;

        if (!collectTickets && !collectKb) {
            this.addLog('warning', 'log_select_collection_target');
            return;
        }

        try {
            // 🔧 새로운 수집 시작 전 기존 수집 중지 (안전장치)
            if (this.isRunning) {
                this.addLog('info', '🛑 기존 수집 중지 중...');
                await this.stopCollection();
                await new Promise(resolve => setTimeout(resolve, 1000)); // 1초 대기
            }

            this.updateStatus('starting');

            const collectionMode = this.querySelector('input[name="collection_mode"]:checked').value;
            const isFullCollection = collectionMode === 'initial';

            // 수집 기간 가져오기
            const startDate = this.querySelector('#start_date').value;
            const endDate = this.querySelector('#end_date').value;

            const headers = this.getHeaders();

            // 새로운 관리자 데이터 수집 API 사용
            const baseUrl = window.BACKEND_CONFIG.getUrl('/admin/data-collection/start');

            // tenant_id가 없으면 명시적으로 실패하도록 함 (기본값 사용 안함)
            if (!window.adminConsole?.tenantId) {
                throw new Error('tenant_id를 찾을 수 없습니다. 관리자 콘솔이 초기화되지 않았습니다.');
            }

            // 운영 백엔드 호환성을 위해 tenant_id를 본문에 포함
            const requestBody = {
                tenant_id: window.adminConsole.tenantId, // 기본값 제거, 없으면 실패
                config: {
                    incremental: !isFullCollection,
                    purge: isFullCollection,
                    collect_tickets: collectTickets,
                    collect_kb: collectKb,
                    max_tickets: null, // 증분수집에서는 제한 없음 (변경된 데이터만 수집)
                    max_articles: null, // 증분수집에서는 제한 없음 (변경된 데이터만 수집)
                    batch_size: 10
                }
            };

            // 날짜 범위가 설정되어 있으면 포함
            if (startDate) {
                requestBody.config.start_date = startDate;
            }
            if (endDate) {
                requestBody.config.end_date = endDate;
            }

            console.log('📅 데이터 수집 시작 요청:', requestBody);

            const response = await fetch(baseUrl, {
                method: 'POST',
                headers: headers,
                body: JSON.stringify(requestBody)
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || `데이터 수집 시작 실패`);
            }

            const result = await response.json();

            if (result.success) {
                this.currentJobId = result.job_id;
                this.isRunning = true;
                this.updateStatus('running');
                // 폴링 시작하지 않음 - 사용자가 수동으로 상태 확인

                // 데이터 수집 시작 시 콘솔 클리어하고 시작 로그 추가
                this.clearLog();
                this.lastLoggedProgress = -1; // 진행률 추적 초기화

                const dateRange = startDate && endDate ? ` (${startDate} ~ ${endDate})` : '';
                const targets = [];
                if (collectTickets) targets.push('티켓');
                if (collectKb) targets.push('지식베이스');

                this.addLog('success', `🚀 ${targets.join(', ')} 데이터 수집 시작됨${dateRange} - Job ID: ${result.job_id} (폴링 비활성화)`);
                this.addProgressLog(0, '데이터 수집 초기화 중...');
            } else {
                throw new Error(result.message || '데이터 수집 시작 실패');
            }
        } catch (error) {
            this.updateStatus('error');
            this.addLog('error', `❌ 데이터 수집 시작 실패: ${error.message}`);
        }
    }

    async pauseCollection() {
        try {
            const response = await fetch(window.BACKEND_CONFIG.getUrl('/admin/data-collection/pause'), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }  // 최소 헤더만
            });

            if (response.ok) {
                const result = await response.json();
                this.updateStatus('paused');
                this.stopProgressPolling();
                this.addLog('info', `⏸️ 데이터 수집 일시정지됨 (${result.paused_job_ids?.length || 0}개 작업)`);
            } else {
                const error = await response.json();
                throw new Error(error.detail || '일시정지 실패');
            }
        } catch (error) {
            this.addLog('error', `❌ 일시정지 실패: ${error.message}`);
        }
    } async stopCollection() {
        try {
            const response = await fetch(window.BACKEND_CONFIG.getUrl('/admin/data-collection/stop'), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }  // 최소 헤더만
            });

            if (response.ok) {
                const result = await response.json();
                this.isRunning = false;
                this.currentJobId = null;
                this.updateStatus('stopped');
                this.stopProgressPolling();
                this.addLog('warning', `🛑 데이터 수집 중지됨 (${result.stopped_job_ids?.length || 0}개 작업)`);
            } else {
                const error = await response.json();
                throw new Error(error.detail || '중지 실패');
            }
        } catch (error) {
            this.addLog('error', `❌ 중지 실패: ${error.message}`);
        }
    }

    async resumeCollection() {
        try {
            const response = await fetch(window.BACKEND_CONFIG.getUrl('/admin/data-collection/resume'), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }  // 최소 헤더만
            });

            if (response.ok) {
                const result = await response.json();
                this.isRunning = true;
                this.updateStatus('running');
                // 폴링 시작하지 않음
                this.addLog('info', `▶️ 데이터 수집 재개됨 (${result.resumed_job_ids?.length || 0}개 작업) - 폴링 비활성화`);
            } else {
                const error = await response.json();
                throw new Error(error.detail || '재개 실패');
            }
        } catch (error) {
            this.addLog('error', `❌ 재개 실패: ${error.message}`);
        }
    }

    async cancelCollection() {
        if (!window.Utils.confirmDialog('진행 중인 데이터 수집을 취소하시겠습니까? 수집된 데이터는 롤백됩니다.')) {
            return;
        }

        try {
            // 새로운 간단한 stop API 사용 (취소는 중지와 동일, job_id 불필요)
            const response = await fetch(window.BACKEND_CONFIG.getUrl('/admin/data-collection/stop'), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }  // 최소 헤더만
            });

            if (response.ok) {
                this.isRunning = false;
                this.currentJobId = null;
                this.updateStatus('cancelled');
                this.stopProgressPolling();
                this.addLog('error', 'log_collection_cancelled');
            } else {
                const error = await response.json();
                throw new Error(error.detail || '취소 실패');
            }
        } catch (error) {
            this.addLog('error', 'log_cancel_failed', error.message);
        }
    }

    updateStatus(status) {
        const statusEl = this.querySelector('#collectionStatus');
        const playBtn = this.querySelector('#playBtn');
        const pauseBtn = this.querySelector('#pauseBtn');
        const stopBtn = this.querySelector('#stopBtn');
        const cancelBtn = this.querySelector('#cancelBtn');

        switch (status) {
            case 'idle':
                statusEl.textContent = '대기중';
                playBtn.disabled = false;
                pauseBtn.disabled = true;
                stopBtn.disabled = true;
                cancelBtn.disabled = true;
                break;
            case 'starting':
                statusEl.textContent = '시작중...';
                playBtn.disabled = true;
                pauseBtn.disabled = true;
                stopBtn.disabled = true;
                cancelBtn.disabled = true;
                break;
            case 'running':
                statusEl.textContent = '수집중';
                playBtn.disabled = true;
                pauseBtn.disabled = false;
                stopBtn.disabled = false;
                cancelBtn.disabled = false;
                break;
            case 'paused':
                statusEl.textContent = '일시정지';
                playBtn.disabled = false;
                pauseBtn.disabled = true;
                stopBtn.disabled = false;
                cancelBtn.disabled = false;
                break;
            case 'stopped':
                statusEl.textContent = '중지됨';
                playBtn.disabled = false;
                pauseBtn.disabled = true;
                stopBtn.disabled = true;
                cancelBtn.disabled = true;
                break;
            case 'cancelled':
                statusEl.textContent = '취소됨';
                playBtn.disabled = false;
                pauseBtn.disabled = true;
                stopBtn.disabled = true;
                cancelBtn.disabled = true;
                break;
            case 'error':
                statusEl.textContent = '오류 발생';
                playBtn.disabled = false;
                pauseBtn.disabled = true;
                stopBtn.disabled = true;
                cancelBtn.disabled = true;
                break;
        }
    }

    updateControlsState() {
        const collectTickets = this.querySelector('#collect_tickets').checked;
        const collectKb = this.querySelector('#collect_kb').checked;
        const playBtn = this.querySelector('#playBtn');

        if (!this.isRunning) {
            playBtn.disabled = !collectTickets && !collectKb;
        }
    }

    startProgressPolling() {
        this.stopProgressPolling(); // Clear any existing interval

        console.log('🔄 Progress polling 시작됨 (15초 간격)');
        this.addLog('info', '상태 자동 갱신 시작 (15초 간격)');

        this.progressInterval = setInterval(async () => {
            if (this._isUpdatingProgress) {
                console.log('⏭️ 업데이트 중이므로 폴링 스킵');
                return;
            }

            try {
                const url = window.BACKEND_CONFIG.getUrl('/admin/data-collection/status');
                const response = await fetch(url, {
                    headers: this.getHeaders()
                });

                if (response.ok) {
                    const contentType = response.headers.get('content-type');
                    if (contentType && contentType.includes('application/json')) {
                        const data = await response.json();
                        this.updateProgress(data);
                    } else {
                        console.warn('Status API returned non-JSON response');
                    }
                } else {
                    console.warn(`Status API returned ${response.status}: ${response.statusText}`);
                }
            } catch (error) {
                console.error('Progress polling error:', error);
            }
        }, 15000); // 15초로 설정
    }

    stopProgressPolling() {
        if (this.progressInterval) {
            clearInterval(this.progressInterval);
            this.progressInterval = null;
        }
    }

    async refreshStatus() {
        try {
            this.addLog('info', '🔄 상태 수동 새로고침 중...');

            // 상태 폴링을 한 번 실행
            const url = window.BACKEND_CONFIG.getUrl('/admin/data-collection/status');
            const response = await fetch(url, {
                headers: this.getHeaders()
            });

            if (response.ok) {
                const data = await response.json();
                this.updateProgress(data);
                this.addLog('success', '✅ 상태 새로고침 완료');
            } else {
                throw new Error(`Status API error: ${response.status}`);
            }
        } catch (error) {
            console.error('Status refresh error:', error);
            this.addLog('error', '❌ 상태 새로고침 실패: ' + error.message);
        }
    }

    /**
     * 진행률 바를 점진적으로 애니메이션
     * @param {HTMLElement} progressBar - 진행률 바 요소
     * @param {number} startWidth - 시작 너비 (%)
     * @param {number} targetWidth - 목표 너비 (%)
     */
    animateProgressBar(progressBar, startWidth, targetWidth) {
        const duration = 1000; // 1초로 확장
        const fps = 60;
        const steps = Math.ceil((duration / 1000) * fps);

        let currentStep = 0;

        // CSS 전환 비활성화
        progressBar.classList.add('progress-bar-smooth');

        // 더 부드러운 easing 함수 사용
        const easeOutCubic = (t) => 1 - Math.pow(1 - t, 3);

        const animate = () => {
            currentStep++;
            const progress = currentStep / steps;
            const easedProgress = easeOutCubic(progress);

            const currentWidth = startWidth + (targetWidth - startWidth) * easedProgress;

            // CSS 변수와 직접 스타일 모두 설정
            progressBar.style.setProperty('--progress-width', `${currentWidth}%`);
            progressBar.style.setProperty('width', `${currentWidth}%`, 'important');

            // 중간 단계에서도 ARIA 업데이트
            progressBar.setAttribute('aria-valuenow', Math.round(currentWidth));

            if (currentStep < steps) {
                requestAnimationFrame(animate);
            } else {
                // 최종값으로 확실히 설정
                progressBar.style.setProperty('--progress-width', `${targetWidth}%`);
                progressBar.style.setProperty('width', `${targetWidth}%`, 'important');
                progressBar.setAttribute('aria-valuenow', Math.round(targetWidth));

                // CSS 전환 재활성화
                progressBar.classList.remove('progress-bar-smooth');

                console.log('✅ 점진적 애니메이션 완료:', {
                    startWidth: `${startWidth}%`,
                    targetWidth: `${targetWidth}%`,
                    finalWidth: progressBar.style.width,
                    currentStage: progressBar.getAttribute('data-stage')
                });
            }
        };

        console.log('🎬 점진적 애니메이션 시작:', {
            startWidth: `${startWidth}%`,
            targetWidth: `${targetWidth}%`,
            duration: `${duration}ms`,
            steps: steps,
            stage: progressBar.getAttribute('data-stage')
        });

        requestAnimationFrame(animate);
    }

    updateProgress(data) {
        // 중복 호출 방지
        if (this._isUpdatingProgress) {
            console.log('⚠️ updateProgress 중복 호출 방지됨');
            return;
        }
        this._isUpdatingProgress = true;

        const progressBar = this.querySelector('#collectionProgressBar');
        const progressPercentage = this.querySelector('#progressPercentage');
        const progressDetails = this.querySelector('#progressDetails');

        let percentage = 0;
        let message = '대기중...';
        let stage = 'idle';
        let isCompleted = false;
        let status = 'idle';

        // 백엔드 응답 구조에 맞게 처리
        if (data.is_running && data.recent_jobs && data.recent_jobs.length > 0) {
            // 실행 중인 작업이 있는 경우
            const runningJob = data.recent_jobs.find(job => job.status === 'running');

            if (runningJob && runningJob.progress) {
                percentage = Math.round(runningJob.progress.percentage || 0);
                message = runningJob.progress.current_step_name || '진행 중...';
                stage = runningJob.progress.current_stage || 'initializing';
                status = 'running';
                isCompleted = false;

                // 진행률이 100%에 도달했는지 확인
                if (percentage >= 100) {
                    isCompleted = true;
                    status = 'completed';
                    stage = 'completed';
                    message = '수집 완료';
                }
            }
        } else if (data.is_paused && data.recent_jobs && data.recent_jobs.length > 0) {
            // 일시정지된 작업이 있는 경우
            const pausedJob = data.recent_jobs.find(job => job.status === 'paused');
            if (pausedJob && pausedJob.progress) {
                percentage = pausedJob.progress.percentage || 0;
                message = `일시정지: ${pausedJob.progress.current_step_name || '진행 중...'}`;
                stage = pausedJob.progress.current_stage || 'initializing';
                status = 'paused';
                isCompleted = false;
            }
        } else {
            // 실행 중인 작업이 없는 경우
            if (data.completed_jobs > 0 && data.total_jobs > 0) {
                // 최근에 완료된 작업이 있는 경우
                percentage = 100;
                message = '데이터 수집이 완료되었습니다.';
                stage = 'completed';
                status = 'completed';
                isCompleted = true;
            } else {
                // 완전히 대기 상태
                percentage = 0;
                message = '대기중...';
                stage = 'idle';
                status = 'idle';
                isCompleted = false;
            }
        }

        // UI 업데이트
        // 진행률이 유의미하게 변경되었을 때만 로그 출력 (5% 단위 또는 상태 변경)
        const shouldLogProgress = (
            percentage !== this.lastLoggedProgress &&
            (percentage === 0 || percentage === 100 || percentage % 5 === 0 ||
                Math.abs(percentage - this.lastLoggedProgress) >= 5)
        );

        if (shouldLogProgress && status === 'running') {
            this.addProgressLog(percentage, message, stage);
            this.lastLoggedProgress = percentage;
        }

        if (progressBar) {
            const oldWidth = parseFloat(progressBar.style.width) || 0;
            const newWidth = percentage;

            // 급격한 변화 방지 (15% 이상 차이나면 점진적 업데이트)
            const widthDiff = Math.abs(newWidth - oldWidth);

            // 단계별 색상 설정
            progressBar.setAttribute('data-stage', stage);

            // 상태에 따른 애니메이션 클래스 관리
            if (status === 'running' && percentage > 0 && percentage < 100) {
                progressBar.classList.add('progress-bar-animated');
            } else {
                progressBar.classList.remove('progress-bar-animated');
            }

            if (widthDiff > 15 && status === 'running' && oldWidth > 0) {
                // 점진적 업데이트 (급격한 변화 방지)
                this.animateProgressBar(progressBar, oldWidth, newWidth);
            } else {
                // 일반적인 업데이트
                progressBar.style.setProperty('--progress-width', `${percentage}%`);
                progressBar.style.setProperty('width', `${percentage}%`, 'important');
            }

            progressBar.setAttribute('aria-valuenow', percentage);

        }
        if (progressPercentage) {
            progressPercentage.textContent = `${percentage}%`;
        }
        if (progressDetails) {
            progressDetails.textContent = message;
        }

        // 상태 변경 처리
        if (isCompleted && this.isRunning) {
            this.isRunning = false;
            this.currentJobId = null;
            this.updateStatus(status);
            this.stopProgressPolling();

            if (status === 'completed') {
                this.addLog('success', '✅ 데이터 수집이 완료되었습니다.');
            }
        } else if (data.is_running && !this.isRunning) {
            // 백엔드에서 실행 중이라고 하는데 프론트엔드에서는 아직 인식하지 못한 경우
            this.isRunning = true;
            this.updateStatus('running');
        }

        // 헤더 카운트 업데이트 (admin.html)
        this.updateHeaderCounts(data.ticket_count, data.article_count, data.last_sync_time);

        // 중복 호출 방지 플래그 해제
        setTimeout(() => {
            this._isUpdatingProgress = false;
        }, 100);
    }

    updateHeaderCounts(ticketCount, articleCount, lastSyncTime) {
        const ticketCountEl = document.getElementById('ticketCount');
        const articleCountEl = document.getElementById('articleCount');
        const lastSyncTimeEl = document.getElementById('lastSyncTime');

        if (ticketCountEl) ticketCountEl.textContent = ticketCount !== undefined ? ticketCount : '-';
        if (articleCountEl) articleCountEl.textContent = articleCount !== undefined ? articleCount : '-';
        if (lastSyncTimeEl && lastSyncTime) {
            const date = new Date(lastSyncTime);
            lastSyncTimeEl.textContent = date.toLocaleString(); // Format as local date/time
        } else if (lastSyncTimeEl) {
            lastSyncTimeEl.textContent = '-';
        }
    }

    addLog(level, messageKey, ...params) {
        const logViewer = this.querySelector('#logViewer');
        const timestamp = new Date().toLocaleTimeString();

        // 레벨별 아이콘과 색상 설정
        const levelConfig = {
            'info': { icon: 'ℹ️', label: 'INFO', color: '#10b981' },
            'success': { icon: '✅', label: 'SUCCESS', color: '#10b981' },
            'warning': { icon: '⚠️', label: 'WARNING', color: '#f59e0b' },
            'error': { icon: '❌', label: 'ERROR', color: '#dc2626' },
            'progress': { icon: '📊', label: 'PROGRESS', color: '#3b82f6' }
        };

        const config = levelConfig[level] || levelConfig['info'];

        // i18n 메시지 가져오기 (fallback으로 키 그대로 사용)
        let message;
        if (window.adminUtils && window.adminUtils.getText) {
            message = window.adminUtils.getText(messageKey);
            // 파라미터가 있으면 치환
            if (params.length > 0) {
                params.forEach((param, index) => {
                    message = message.replace(`{${index}}`, param);
                });
            }
        } else {
            message = messageKey; // fallback
        }

        const logEntry = document.createElement('div');
        logEntry.className = 'log-entry';
        logEntry.innerHTML = `
            <span class="log-timestamp" style="color: #6b7280;">${timestamp}</span>
            <span class="log-level" style="color: ${config.color}; font-weight: 600;">
                ${config.icon} ${config.label}
            </span> 
            <span class="log-message">${message}</span>
        `;

        logViewer.appendChild(logEntry);

        // 터미널처럼 자동으로 맨 아래로 스크롤
        logViewer.scrollTop = logViewer.scrollHeight;

        // 로그가 너무 많아지면 오래된 항목 제거 (성능 최적화)
        const maxLogEntries = 500;
        const logEntries = logViewer.querySelectorAll('.log-entry');
        if (logEntries.length > maxLogEntries) {
            // 오래된 항목들 제거
            const removeCount = logEntries.length - maxLogEntries;
            for (let i = 0; i < removeCount; i++) {
                logEntries[i].remove();
            }
        }

        // 콘솔에도 출력
        const consoleFn = level === 'error' ? console.error :
            level === 'warning' ? console.warn :
                console.log;
        consoleFn(`[${timestamp}] ${config.label}: ${message}`);
    }

    // 진행률과 함께 콘솔 메시지 표시하는 편의 함수
    addProgressLog(percentage, message, stage = '') {
        const progressText = stage ? `[${stage}] ${message} (${percentage.toFixed(1)}%)` : `${message} (${percentage.toFixed(1)}%)`;
        this.addLog('progress', progressText);
    }

    // 콘솔 클리어 함수
    clearLog() {
        const logViewer = this.querySelector('#logViewer');
        if (logViewer) {
            // 초기 메시지만 남기고 모두 제거
            logViewer.innerHTML = `
                <div class="log-entry">
                    <span class="log-timestamp">00:00:00</span>
                    <span class="log-level-info">INFO</span> <span data-i18n="log_system_ready">시스템 준비 완료</span>
                </div>
            `;
        }
    }

    disconnectedCallback() {
        this.stopProgressPolling();
    }
}

// Register the custom element
customElements.define('data-collection-manager', DataCollectionManager);
