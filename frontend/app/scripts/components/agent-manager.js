/**
 * Agent Manager Web Component
 * 에이전트 관리 컴포넌트 - 에이전트 동기화 및 라이선스 관리
 */
class AgentManager extends HTMLElement {
    constructor() {
        super();
        this.agents = [];
        this.syncInProgress = false;
        this.progressInterval = null;
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
        this.loadAgentData();
    }
    
    render() {
        this.innerHTML = `
            <div class="row">
                <!-- Left: Agent Sync -->
                <div class="col-lg-6 mb-4">
                    <div class="card h-100">
                        <div class="card-body">
                            <h5 class="card-title mb-4">
                                <i class="fas fa-users text-primary"></i> 
                                <span data-i18n="agent_sync_title">에이전트 정보 동기화</span>
                            </h5>
                            <p class="text-muted mb-3" data-i18n="agent_sync_desc">
                                Freshdesk에서 에이전트 정보를 가져와 데이터베이스에 동기화합니다.
                            </p>
                            
                            <div class="mb-3">
                                <label class="text-muted small" data-i18n="agent_current_count">현재 에이전트 수</label>
                                <div class="font-weight-bold" id="currentAgentCount">-</div>
                            </div>
                            
                            <div class="mb-3">
                                <label class="text-muted small" data-i18n="agent_last_sync">마지막 동기화</label>
                                <div class="font-weight-bold" id="lastAgentSync">-</div>
                            </div>
                            
                            <button id="syncAgentsBtn" class="btn btn-primary">
                                <i class="fas fa-sync-alt"></i> 
                                <span data-i18n="agent_sync_button">에이전트 동기화</span>
                            </button>
                        </div>
                    </div>
                </div>
                
                <!-- Right: Sync Status -->
                <div class="col-lg-6 mb-4">
                    <div class="card h-100">
                        <div class="card-body">
                            <h5 class="card-title mb-4">
                                <i class="fas fa-info-circle text-info"></i> 
                                <span data-i18n="agent_sync_status_title">동기화 상태</span>
                            </h5>
                            
                            <div id="agentSyncStatus" style="display: none;">
                                <div class="mb-3">
                                    <label class="text-muted small" data-i18n="agent_progress_status">진행 상태</label>
                                    <div class="progress" style="height: 20px;">
                                        <div id="agentSyncProgress" class="progress-bar progress-bar-striped progress-bar-animated" role="progressbar" style="width: 0%;">
                                            0%
                                        </div>
                                    </div>
                                </div>
                                
                                <div class="mb-3">
                                    <label class="text-muted small" data-i18n="agent_status_message">상태 메시지</label>
                                    <div id="agentSyncMessage" class="font-weight-bold">준비 중...</div>
                                </div>
                                
                                <div class="row">
                                    <div class="col-6">
                                        <label class="text-muted small" data-i18n="agent_synced">동기화된 에이전트</label>
                                        <div id="syncedAgents" class="font-weight-bold">0</div>
                                    </div>
                                    <div class="col-6">
                                        <label class="text-muted small" data-i18n="agent_failed">실패한 에이전트</label>
                                        <div id="failedAgents" class="font-weight-bold text-danger">0</div>
                                    </div>
                                </div>
                            </div>
                            
                            <div id="agentSyncIdle" class="text-center text-muted py-4">
                                <i class="fas fa-info-circle fa-3x mb-3"></i>
                                <p data-i18n="agent_sync_idle">동기화를 시작하려면 왼쪽의 '에이전트 동기화' 버튼을 클릭하세요.</p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Agent List -->
            <div class="row">
                <div class="col-12">
                    <div class="card">
                        <div class="card-body">
                            <h5 class="card-title mb-3">
                                <i class="fas fa-list text-secondary"></i> 
                                <span data-i18n="agent_list_title">에이전트 목록</span>
                            </h5>
                            
                            <div class="table-responsive">
                                <table class="table table-sm">
                                    <thead>
                                        <tr>
                                            <th data-i18n="agent_table_name">이름</th>
                                            <th data-i18n="agent_table_email">이메일</th>
                                            <th data-i18n="agent_table_role">역할</th>
                                            <th data-i18n="agent_table_status">상태</th>
                                            <th data-i18n="agent_table_last_active">마지막 활동</th>
                                            <th data-i18n="agent_table_license">라이선스</th>
                                        </tr>
                                    </thead>
                                    <tbody id="agentTableBody">
                                        <tr>
                                            <td colspan="6" class="text-center text-muted">
                                                <span data-i18n="loading">로딩 중...</span>
                                            </td>
                                        </tr>
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- License Management -->
            <div class="row mt-4">
                <div class="col-12">
                    <div class="card">
                        <div class="card-body">
                            <h5 class="card-title mb-4">
                                <i class="fas fa-key text-warning"></i> 
                                <span data-i18n="agent_license_title">라이선스 관리</span>
                            </h5>
                            
                            <p class="text-muted mb-4" data-i18n="agent_license_desc">
                                에이전트 라이선스 할당 및 관리
                            </p>
                            
                            <div class="row">
                                <div class="col-md-4 mb-3">
                                    <div class="text-center">
                                        <div class="h2 text-primary" id="totalLicenses">-</div>
                                        <div class="text-muted" data-i18n="agent_license_total">총 라이선스</div>
                                    </div>
                                </div>
                                <div class="col-md-4 mb-3">
                                    <div class="text-center">
                                        <div class="h2 text-success" id="usedLicenses">-</div>
                                        <div class="text-muted" data-i18n="agent_license_used">사용 중</div>
                                    </div>
                                </div>
                                <div class="col-md-4 mb-3">
                                    <div class="text-center">
                                        <div class="h2 text-info" id="availableLicenses">-</div>
                                        <div class="text-muted" data-i18n="agent_license_available">사용 가능</div>
                                    </div>
                                </div>
                            </div>
                            
                            <div class="progress mb-3" style="height: 10px;">
                                <div class="progress-bar" id="licenseUsageBar" style="width: 0%;"></div>
                            </div>
                            
                            <div class="alert alert-info">
                                <i class="fas fa-info-circle"></i>
                                <strong data-i18n="license_info_title">라이선스 정보:</strong>
                                <span data-i18n="license_info_desc">라이선스는 활성 에이전트에게 자동으로 할당됩니다. 비활성 에이전트의 라이선스는 자동으로 회수됩니다.</span>
                            </div>
                            
                            <div class="d-flex justify-content-between align-items-center mt-3">
                                <div>
                                    <small class="text-muted">라이선스 관리 작업</small>
                                </div>
                                <div class="btn-group btn-group-sm">
                                    <button class="btn btn-outline-warning" onclick="this.closest('agent-manager').triggerAutoReclaim()" title="비활성 에이전트 라이선스 자동 회수">
                                        <i class="fas fa-recycle"></i> 자동 회수
                                    </button>
                                    <button class="btn btn-outline-info" onclick="this.closest('agent-manager').viewLicenseStats()" title="상세 통계 보기">
                                        <i class="fas fa-chart-bar"></i> 통계
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }
    
    setupEventListeners() {
        // Agent sync button
        this.querySelector('#syncAgentsBtn').addEventListener('click', () => {
            this.startAgentSync();
        });
    }
    
    async loadAgentData() {
        try {
            // 라이선스 정보 로드
                        const licenseResponse = await window.adminUtils.apiCall('GET', window.BACKEND_CONFIG.getUrl('/admin/agents/licenses/pool'));
            const agentsResponse = await window.adminUtils.apiCall('GET', window.BACKEND_CONFIG.getUrl('/admin/agents/licenses'));
            
            if (licenseResponse.success && agentsResponse.success) {
                this.agents = agentsResponse.data || [];
                this.updateAgentTable();
                this.updateAgentCount();
                this.updateLastSync(new Date().toISOString()); // Mock last sync
                this.updateLicenseInfo(licenseResponse.data);
            } else {
                // Development fallback
                this.loadMockData();
            }
        } catch (error) {
            console.error('Agent data loading error:', error);
            this.loadMockData();
        }
    }
    
    loadMockData() {
        // Mock data for development
        this.agents = [
            {
                id: 1,
                name: "Admin User",
                email: "admin@example.com",
                role: "Administrator",
                status: "active",
                last_active: new Date().toISOString(),
                has_license: true
            },
            {
                id: 2,
                name: "Agent Smith",
                email: "agent@example.com", 
                role: "Agent",
                status: "active",
                last_active: new Date(Date.now() - 3600000).toISOString(),
                has_license: true
            }
        ];
        
        this.updateAgentTable();
        this.updateAgentCount();
        this.updateLastSync(new Date().toISOString());
        this.updateLicenseInfo({
            total: 10,
            used: 2,
            available: 8
        });
    }
    
    updateAgentTable() {
        const tbody = this.querySelector('#agentTableBody');
        
        if (this.agents.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="6" class="text-center text-muted">
                        ${this.getText('no_agents')}
                    </td>
                </tr>
            `;
            return;
        }
        
        tbody.innerHTML = this.agents.map(agent => `
            <tr>
                <td>${agent.agent_name || agent.name}</td>
                <td>${agent.agent_email || agent.email}</td>
                <td>
                    <span class="badge badge-${this.getRoleBadgeColor(agent.role || 'Agent')}">${agent.role || 'Agent'}</span>
                </td>
                <td>
                    <span class="badge badge-${this.getLicenseStatusColor(agent.license_status)}">${agent.license_status}</span>
                </td>
                <td>${this.formatDate(agent.last_activity)}</td>
                <td>
                    <div class="btn-group btn-group-sm">
                        ${agent.license_status === 'active' 
                            ? `<button class="btn btn-outline-warning btn-xs" onclick="this.closest('agent-manager').reclaimLicense(${agent.agent_id})" title="라이선스 회수">
                                <i class="fas fa-minus"></i>
                            </button>`
                            : `<button class="btn btn-outline-success btn-xs" onclick="this.closest('agent-manager').assignLicense(${agent.agent_id})" title="라이선스 할당">
                                <i class="fas fa-plus"></i>
                            </button>`
                        }
                        <button class="btn btn-outline-info btn-xs" onclick="this.closest('agent-manager').viewLicenseHistory(${agent.agent_id})" title="히스토리">
                            <i class="fas fa-history"></i>
                        </button>
                    </div>
                </td>
            </tr>
        `).join('');
    }
    
    updateAgentCount() {
        const countEl = this.querySelector('#currentAgentCount');
        if (countEl) {
            countEl.textContent = this.agents.length;
        }
    }
    
    updateLastSync(lastSync) {
        const syncEl = this.querySelector('#lastAgentSync');
        if (syncEl && lastSync) {
            const date = new Date(lastSync);
            syncEl.textContent = date.toLocaleString();
        }
    }
    
    updateLicenseInfo(licenseInfo) {
        if (!licenseInfo) return;
        
        const totalEl = this.querySelector('#totalLicenses');
        const usedEl = this.querySelector('#usedLicenses');
        const availableEl = this.querySelector('#availableLicenses');
        const usageBarEl = this.querySelector('#licenseUsageBar');
        
        // API 응답 형식에 맞게 수정
        const total = licenseInfo.total_licenses || licenseInfo.total || 0;
        const used = licenseInfo.used_licenses || licenseInfo.used || 0;
        const available = licenseInfo.available_licenses || licenseInfo.available || 0;
        
        if (totalEl) totalEl.textContent = total;
        if (usedEl) usedEl.textContent = used;
        if (availableEl) availableEl.textContent = available;
        
        if (usageBarEl && total > 0) {
            const percentage = (used / total) * 100;
            usageBarEl.style.width = `${percentage}%`;
            usageBarEl.className = `progress-bar ${this.getUsageBarColor(percentage)}`;
        }
    }
    
    async startAgentSync() {
        if (this.syncInProgress) return;
        
        try {
            this.syncInProgress = true;
            this.updateSyncUI('starting');
            
            const response = await fetch(window.BACKEND_CONFIG.getUrl('/admin/agents/sync'), {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'ngrok-skip-browser-warning': 'true'
                }
            });
            
            if (response.ok) {
                const result = await response.json();
                this.startProgressPolling(result.job_id);
                this.showSuccess(this.getText('success_agent_sync_started') || '에이전트 동기화가 시작되었습니다');
            } else {
                const error = await response.json();
                throw new Error(error.detail || 'Agent sync failed');
            }
        } catch (error) {
            this.syncInProgress = false;
            this.updateSyncUI('error');
            this.showError(`Agent sync failed: ${error.message}`);
        }
    }
    
    startProgressPolling(jobId) {
        this.updateSyncUI('running');
        
        this.progressInterval = setInterval(async () => {
            try {
                const response = await fetch(window.BACKEND_CONFIG.getUrl(`/admin/agents/sync/status/${jobId}`));
                if (response.ok) {
                    const progress = await response.json();
                    this.updateProgress(progress);
                    
                    if (progress.completed) {
                        clearInterval(this.progressInterval);
                        this.syncInProgress = false;
                        this.updateSyncUI('completed');
                        await this.loadAgentData();
                        this.showSuccess(this.getText('success_agent_sync_completed') || '에이전트 동기화가 완료되었습니다');
                    }
                }
            } catch (error) {
                console.error('Progress polling error:', error);
            }
        }, 2000);
    }
    
    updateProgress(progress) {
        const progressBar = this.querySelector('#agentSyncProgress');
        const messageEl = this.querySelector('#agentSyncMessage');
        const syncedEl = this.querySelector('#syncedAgents');
        const failedEl = this.querySelector('#failedAgents');
        
        if (progressBar) {
            const percentage = Math.round(progress.percentage || 0);
            progressBar.style.width = `${percentage}%`;
            progressBar.textContent = `${percentage}%`;
        }
        
        if (messageEl) {
            messageEl.textContent = progress.current_stage || '진행 중...';
        }
        
        if (syncedEl) {
            syncedEl.textContent = progress.synced_count || 0;
        }
        
        if (failedEl) {
            failedEl.textContent = progress.failed_count || 0;
        }
    }
    
    updateSyncUI(status) {
        const statusDiv = this.querySelector('#agentSyncStatus');
        const idleDiv = this.querySelector('#agentSyncIdle');
        const syncBtn = this.querySelector('#syncAgentsBtn');
        
        switch (status) {
            case 'starting':
            case 'running':
                statusDiv.style.display = 'block';
                idleDiv.style.display = 'none';
                syncBtn.disabled = true;
                syncBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 동기화 중...';
                break;
            case 'completed':
            case 'error':
                statusDiv.style.display = 'none';
                idleDiv.style.display = 'block';
                syncBtn.disabled = false;
                syncBtn.innerHTML = '<i class="fas fa-sync-alt"></i> 에이전트 동기화';
                break;
        }
    }
    
    getRoleBadgeColor(role) {
        const colors = {
            'Administrator': 'danger',
            'Agent': 'primary',
            'Supervisor': 'warning',
            'Observer': 'secondary'
        };
        return colors[role] || 'secondary';
    }
    
    getStatusBadgeColor(status) {
        const colors = {
            'active': 'success',
            'inactive': 'secondary',
            'suspended': 'warning',
            'deleted': 'danger'
        };
        return colors[status] || 'secondary';
    }
    
    getLicenseStatusColor(status) {
        const colors = {
            'active': 'success',
            'expired': 'warning',
            'revoked': 'danger',
            'none': 'secondary'
        };
        return colors[status] || 'secondary';
    }

    getUsageBarColor(percentage) {
        if (percentage >= 90) return 'bg-danger';
        if (percentage >= 75) return 'bg-warning';
        return 'bg-success';
    }

    async assignLicense(agentId) {
        if (!window.Utils.confirmDialog('이 에이전트에게 라이선스를 할당하시겠습니까?')) {
            return;
        }

        try {
            const response = await window.adminUtils.apiCall('POST', `${this.baseUrl}/api/admin/license/assign`, {
                agent_id: agentId,
                reason: '수동 할당',
                expires_at: null
            });

            if (response.success) {
                this.showSuccess(`라이선스가 할당되었습니다`);
                await this.loadAgentData();
            } else {
                this.showError(`라이선스 할당 실패: ${response.message}`);
            }
        } catch (error) {
            console.error('라이선스 할당 오류:', error);
            this.showError(`라이선스 할당 오류: ${error.message}`);
        }
    }

    async reclaimLicense(agentId) {
        if (!window.Utils.confirmDialog('이 에이전트의 라이선스를 회수하시겠습니까?')) {
            return;
        }

        try {
            const response = await window.adminUtils.apiCall('POST', window.BACKEND_CONFIG.getUrl('/admin/agents/licenses/reclaim'), {
                agent_ids: [agentId],
                reason: '수동 회수'
            });

            if (response.success) {
                this.showSuccess(`라이선스가 회수되었습니다`);
                await this.loadAgentData();
            } else {
                this.showError(`라이선스 회수 실패: ${response.message}`);
            }
        } catch (error) {
            console.error('라이선스 회수 오류:', error);
            this.showError(`라이선스 회수 오류: ${error.message}`);
        }
    }

    viewLicenseHistory(agentId) {
        // 라이선스 히스토리 모달 표시 (추후 구현)
        window.Utils.alertDialog(`에이전트 ID ${agentId}의 라이선스 히스토리 조회 기능은 추후 구현 예정입니다.`);
    }

    async triggerAutoReclaim() {
        if (!window.Utils.confirmDialog('비활성 에이전트의 라이선스를 자동 회수하시겠습니까?')) {
            return;
        }

        try {
            const response = await window.adminUtils.apiCall('POST', window.BACKEND_CONFIG.getUrl('/admin/agents/licenses/auto-reclaim'));

            if (response.success) {
                const reclaimedCount = response.data?.reclaimed_count || 0;
                this.showSuccess(`${reclaimedCount}개의 라이선스가 자동 회수되었습니다`);
                await this.loadAgentData();
            } else {
                this.showError(`자동 회수 실패: ${response.message}`);
            }
        } catch (error) {
            console.error('자동 회수 오류:', error);
            this.showError(`자동 회수 오류: ${error.message}`);
        }
    }

    async viewLicenseStats() {
        try {
            const response = await window.adminUtils.apiCall('GET', window.BACKEND_CONFIG.getUrl('/admin/agents/licenses/stats'));

            if (response.success) {
                this.showLicenseStatsModal(response.data);
            } else {
                this.showError(`통계 조회 실패: ${response.message}`);
            }
        } catch (error) {
            console.error('통계 조회 오류:', error);
            this.showError(`통계 조회 오류: ${error.message}`);
        }
    }

    showLicenseStatsModal(stats) {
        const modalContent = `
            <div class="modal-overlay" id="licenseStatsModal" style="display: flex;">
                <div class="modal-content" style="max-width: 800px; width: 90%;">
                    <div class="modal-header">
                        <h4>📊 라이선스 통계</h4>
                        <button class="modal-close" onclick="document.getElementById('licenseStatsModal').remove()">&times;</button>
                    </div>
                    
                    <div class="modal-body">
                        <div class="row mb-4">
                            <div class="col-md-6">
                                <h6>📈 라이선스 배포 현황</h6>
                                <div class="table-responsive">
                                    <table class="table table-sm">
                                        <tbody>
                                            ${Object.entries(stats.license_distribution).map(([status, count]) => `
                                                <tr>
                                                    <td><span class="badge badge-${this.getLicenseStatusColor(status)}">${status}</span></td>
                                                    <td>${count}개</td>
                                                </tr>
                                            `).join('')}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                            <div class="col-md-6">
                                <h6>📊 활동 통계</h6>
                                <div class="table-responsive">
                                    <table class="table table-sm">
                                        <tbody>
                                            <tr>
                                                <td>최근 7일 활동</td>
                                                <td><span class="badge badge-success">${stats.activity_stats.active_last_7_days || 0}</span></td>
                                            </tr>
                                            <tr>
                                                <td>30일 이상 비활성</td>
                                                <td><span class="badge badge-warning">${stats.activity_stats.inactive_30_days || 0}</span></td>
                                            </tr>
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        </div>
                        
                        ${stats.expiration_alerts && stats.expiration_alerts.length > 0 ? `
                            <div class="mb-4">
                                <h6>⚠️ 만료 예정 라이선스</h6>
                                <div class="table-responsive">
                                    <table class="table table-sm">
                                        <thead>
                                            <tr>
                                                <th>에이전트</th>
                                                <th>이메일</th>
                                                <th>만료일</th>
                                                <th>남은 일수</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            ${stats.expiration_alerts.map(alert => `
                                                <tr>
                                                    <td>${alert.agent_name}</td>
                                                    <td>${alert.agent_email}</td>
                                                    <td>${new Date(alert.expires_at).toLocaleDateString()}</td>
                                                    <td><span class="badge badge-warning">${alert.days_remaining}일</span></td>
                                                </tr>
                                            `).join('')}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        ` : ''}
                        
                        ${stats.recommendations && stats.recommendations.length > 0 ? `
                            <div class="mb-4">
                                <h6>💡 권장사항</h6>
                                <ul class="list-group">
                                    ${stats.recommendations.map(rec => `
                                        <li class="list-group-item">
                                            <i class="fas fa-lightbulb text-warning"></i> ${rec}
                                        </li>
                                    `).join('')}
                                </ul>
                            </div>
                        ` : ''}
                    </div>
                    
                    <div class="modal-actions">
                        <button class="btn btn-secondary" onclick="document.getElementById('licenseStatsModal').remove()">닫기</button>
                    </div>
                </div>
            </div>
        `;
        
        // 모달을 body에 추가
        document.body.insertAdjacentHTML('beforeend', modalContent);
    }
    
    formatDate(dateString) {
        if (!dateString) return '-';
        const date = new Date(dateString);
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        
        if (diffMins < 1) return this.getText('time_now') || '방금 전';
        if (diffMins < 60) return `${diffMins}${this.getText('time_minute_ago') || '분 전'}`;
        if (diffMins < 1440) return `${Math.floor(diffMins / 60)}${this.getText('time_hour_ago') || '시간 전'}`;
        return `${Math.floor(diffMins / 1440)}${this.getText('time_day_ago') || '일 전'}`;
    }
    
    getText(key) {
        return window.adminUtils?.getText(key) || key;
    }
    
    showSuccess(message) {
        window.adminUtils?.showAlert('success', message);
    }
    
    showError(message) {
        window.adminUtils?.showAlert('danger', message);
    }
    
    disconnectedCallback() {
        if (this.progressInterval) {
            clearInterval(this.progressInterval);
        }
    }
}

// Register the custom element
customElements.define('agent-manager', AgentManager);