/**
 * 🏗️ Copilot Canvas - 관리자 콘솔 JavaScript
 * 
 * 관리자 화면에서 백엔드 API와 연결하여 시스템 관리 기능을 제공합니다.
 * 
 * 주요 기능:
 * - 서버 상태 모니터링
 * - 데이터 수집 작업 관리 (/ingest/jobs API)
 * - 에이전트 관리 (agents 테이블 CRUD)
 * - 실시간 작업 진행률 표시
 * 
 * @author We Do Soft Inc.
 * @since 2025-07-07
 * @version 1.0.0
 */

class AdminConsole {
  constructor() {
    this.baseURL = this.getBackendURL();
    this.authHeaders = this.getAuthHeaders();
    this.refreshInterval = null;
    this.init();
  }

  /**
   * 🔗 백엔드 URL 결정 (중앙 설정 사용)
   */
  getBackendURL() {
    return window.BACKEND_CONFIG.getURL();
  }

  /**
   * 🔐 인증 헤더 설정
   */
  getAuthHeaders() {
    return {
      'Content-Type': 'application/json',
      'X-Tenant-ID': 'wedosoft',
      'X-Platform': 'freshdesk',
      'X-Domain': 'wedosoft.freshdesk.com',
      'X-API-Key': 'Ug9H1cKCZZtZ4haamBy',
      'X-Client-Version': '2.0.0-admin',
      // ngrok 헤더 추가
      'ngrok-skip-browser-warning': 'true'
    };
  }

  /**
   * 🚀 초기화
   */
  init() {
    this.setupEventListeners();
    this.loadInitialData();
    this.startAutoRefresh();
  }

  /**
   * 🎯 이벤트 리스너 설정
   */
  setupEventListeners() {
    // 데이터 수집 버튼
    document.getElementById('startIngestion')?.addEventListener('click', () => {
      this.startDataIngestion();
    });

    document.getElementById('pauseIngestion')?.addEventListener('click', () => {
      this.pauseDataIngestion();
    });

    document.getElementById('cancelIngestion')?.addEventListener('click', () => {
      this.cancelDataIngestion();
    });

    // 새로고침 버튼
    document.getElementById('refreshStatus')?.addEventListener('click', () => {
      this.refreshAllData();
    });

    // 에이전트 관리 버튼
    document.getElementById('syncAgents')?.addEventListener('click', () => {
      this.syncAgents();
    });

    document.getElementById('addAgent')?.addEventListener('click', () => {
      this.showAddAgentModal();
    });
  }

  /**
   * 📊 초기 데이터 로드
   */
  async loadInitialData() {
    try {
      this.showLoading('초기 데이터 로드 중...');
      
      await Promise.all([
        this.loadServerStatus(),
        this.loadIngestionJobs(),
        this.loadAgents(),
        this.loadSystemMetrics()
      ]);
      
      this.hideLoading();
      this.showToast('관리자 콘솔 로드 완료', 'success');
    } catch (error) {
      console.error('❌ 초기 데이터 로드 실패:', error);
      this.hideLoading();
      this.showToast('초기 데이터 로드 실패: ' + error.message, 'error');
    }
  }

  /**
   * 🏥 서버 상태 확인
   */
  async loadServerStatus() {
    try {
      const response = await fetch(`${this.baseURL}/health`, {
        method: 'GET',
        headers: this.authHeaders
      });

      const data = await response.json();
      this.updateServerStatus(response.ok ? 'healthy' : 'unhealthy', data);
    } catch (error) {
      console.error('❌ 서버 상태 확인 실패:', error);
      this.updateServerStatus('error', { error: error.message });
    }
  }

  /**
   * 📊 데이터 수집 작업 조회
   */
  async loadIngestionJobs() {
    try {
      const response = await fetch(`${this.baseURL}/ingest/jobs`, {
        method: 'GET',
        headers: this.authHeaders
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      this.updateIngestionJobsList(data.jobs || []);
    } catch (error) {
      console.error('❌ 데이터 수집 작업 조회 실패:', error);
      this.showToast('데이터 수집 작업 조회 실패: ' + error.message, 'error');
    }
  }

  /**
   * 👥 에이전트 목록 조회
   */
  async loadAgents() {
    try {
      const response = await fetch(`${this.baseURL}/agents`, {
        method: 'GET',
        headers: this.authHeaders
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      this.updateAgentsList(data.agents || []);
    } catch (error) {
      console.error('❌ 에이전트 목록 조회 실패:', error);
      this.showToast('에이전트 목록 조회 실패: ' + error.message, 'error');
    }
  }

  /**
   * 📈 시스템 메트릭 조회
   */
  async loadSystemMetrics() {
    try {
      const response = await fetch(`${this.baseURL}/admin/system/metrics`, {
        method: 'GET',
        headers: this.authHeaders
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      this.updateSystemMetrics(data);
    } catch (error) {
      console.error('❌ 시스템 메트릭 조회 실패:', error);
      // 메트릭은 선택사항이므로 에러를 표시하지 않음
    }
  }

  /**
   * 🚀 데이터 수집 시작
   */
  async startDataIngestion() {
    try {
      const options = this.getIngestionOptions();
      
      const response = await fetch(`${this.baseURL}/ingest/jobs`, {
        method: 'POST',
        headers: this.authHeaders,
        body: JSON.stringify(options)
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      await response.json(); // 응답 처리
      this.showToast('데이터 수집 작업이 시작되었습니다', 'success');
      this.loadIngestionJobs(); // 목록 새로고침
    } catch (error) {
      console.error('❌ 데이터 수집 시작 실패:', error);
      this.showToast('데이터 수집 시작 실패: ' + error.message, 'error');
    }
  }

  /**
   * ⏸️ 데이터 수집 일시정지
   */
  async pauseDataIngestion() {
    const activeJobId = this.getActiveJobId();
    if (!activeJobId) {
      this.showToast('일시정지할 작업이 없습니다', 'warning');
      return;
    }

    try {
      const response = await fetch(`${this.baseURL}/ingest/jobs/${activeJobId}/control`, {
        method: 'POST',
        headers: this.authHeaders,
        body: JSON.stringify({
          action: 'pause',
          reason: '관리자가 일시정지'
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      this.showToast('데이터 수집이 일시정지되었습니다', 'success');
      this.loadIngestionJobs();
    } catch (error) {
      console.error('❌ 데이터 수집 일시정지 실패:', error);
      this.showToast('데이터 수집 일시정지 실패: ' + error.message, 'error');
    }
  }

  /**
   * ❌ 데이터 수집 취소
   */
  async cancelDataIngestion() {
    const activeJobId = this.getActiveJobId();
    if (!activeJobId) {
      this.showToast('취소할 작업이 없습니다', 'warning');
      return;
    }

    // 사용자 확인 요청
    const confirmed = await this.showConfirmDialog('정말로 데이터 수집을 취소하시겠습니까?');
    if (!confirmed) {
      return;
    }

    try {
      const response = await fetch(`${this.baseURL}/ingest/jobs/${activeJobId}/control`, {
        method: 'POST',
        headers: this.authHeaders,
        body: JSON.stringify({
          action: 'cancel',
          reason: '관리자가 취소'
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      this.showToast('데이터 수집이 취소되었습니다', 'success');
      this.loadIngestionJobs();
    } catch (error) {
      console.error('❌ 데이터 수집 취소 실패:', error);
      this.showToast('데이터 수집 취소 실패: ' + error.message, 'error');
    }
  }

  /**
   * 🔄 에이전트 동기화
   */
  async syncAgents() {
    try {
      this.showLoading('에이전트 동기화 중...');
      
      const response = await fetch(`${this.baseURL}/agents/sync`, {
        method: 'POST',
        headers: this.authHeaders
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      this.hideLoading();
      this.showToast(`에이전트 동기화 완료: ${data.synced_count || 0}개 업데이트`, 'success');
      this.loadAgents();
    } catch (error) {
      console.error('❌ 에이전트 동기화 실패:', error);
      this.hideLoading();
      this.showToast('에이전트 동기화 실패: ' + error.message, 'error');
    }
  }

  /**
   * 🔄 전체 데이터 새로고침
   */
  async refreshAllData() {
    await this.loadInitialData();
  }

  /**
   * ⏰ 자동 새로고침 시작
   */
  startAutoRefresh() {
    // 30초마다 상태 업데이트
    this.refreshInterval = setInterval(() => {
      this.loadServerStatus();
      this.loadIngestionJobs();
    }, 30000);
  }

  /**
   * 🔧 UI 업데이트 함수들
   */

  updateServerStatus(status, data) {
    const statusElement = document.getElementById('serverStatus');
    if (!statusElement) return;

    const statusMap = {
      'healthy': { text: '정상', class: 'text-success', icon: '🟢' },
      'unhealthy': { text: '비정상', class: 'text-warning', icon: '🟡' },
      'error': { text: '오류', class: 'text-danger', icon: '🔴' }
    };

    const statusInfo = statusMap[status] || statusMap['error'];
    statusElement.innerHTML = `${statusInfo.icon} ${statusInfo.text}`;
    statusElement.className = statusInfo.class;

    // 상세 정보 업데이트
    const detailsElement = document.getElementById('serverDetails');
    if (detailsElement && data) {
      detailsElement.textContent = JSON.stringify(data, null, 2);
    }
  }

  updateIngestionJobsList(jobs) {
    const listElement = document.getElementById('ingestionJobsList');
    if (!listElement) return;

    if (jobs.length === 0) {
      listElement.innerHTML = '<div class="text-muted">진행 중인 작업이 없습니다.</div>';
      return;
    }

    const jobsHTML = jobs.map(job => `
      <div class="card mb-2">
        <div class="card-body">
          <div class="d-flex justify-content-between align-items-center">
            <div>
              <h6 class="card-title mb-1">작업 ID: ${job.job_id}</h6>
              <small class="text-muted">상태: ${this.getJobStatusBadge(job.status)}</small>
            </div>
            <div class="text-right">
              <small>진행률: ${job.progress || 0}%</small>
              <div class="progress mt-1" style="width: 100px;">
                <div class="progress-bar" style="width: ${job.progress || 0}%"></div>
              </div>
            </div>
          </div>
          ${job.error ? `<div class="text-danger mt-2"><small>오류: ${job.error}</small></div>` : ''}
        </div>
      </div>
    `).join('');

    listElement.innerHTML = jobsHTML;
  }

  updateAgentsList(agents) {
    const listElement = document.getElementById('agentsList');
    if (!listElement) return;

    if (agents.length === 0) {
      listElement.innerHTML = '<div class="text-muted">등록된 에이전트가 없습니다.</div>';
      return;
    }

    const agentsHTML = agents.map(agent => `
      <div class="card mb-2">
        <div class="card-body">
          <div class="d-flex justify-content-between align-items-center">
            <div>
              <h6 class="card-title mb-1">${agent.name || '이름 없음'}</h6>
              <small class="text-muted">ID: ${agent.id}</small>
            </div>
            <div>
              <span class="badge ${agent.is_active ? 'badge-success' : 'badge-secondary'}">
                ${agent.is_active ? '활성' : '비활성'}
              </span>
            </div>
          </div>
        </div>
      </div>
    `).join('');

    listElement.innerHTML = agentsHTML;
  }

  updateSystemMetrics(metrics) {
    // CPU 사용률
    const cpuElement = document.getElementById('cpuUsage');
    if (cpuElement && metrics.cpu_usage) {
      cpuElement.textContent = `${metrics.cpu_usage.toFixed(1)}%`;
    }

    // 메모리 사용률
    const memoryElement = document.getElementById('memoryUsage');
    if (memoryElement && metrics.memory_usage) {
      memoryElement.textContent = `${metrics.memory_usage.toFixed(1)}%`;
    }

    // 디스크 사용률
    const diskElement = document.getElementById('diskUsage');
    if (diskElement && metrics.disk_usage) {
      diskElement.textContent = `${metrics.disk_usage.toFixed(1)}%`;
    }
  }

  /**
   * 🔧 유틸리티 함수들
   */

  getIngestionOptions() {
    return {
      incremental: document.getElementById('incrementalMode')?.checked !== false,
      purge: document.getElementById('purgeMode')?.checked || false,
      process_attachments: document.getElementById('processAttachments')?.checked !== false,
      force_rebuild: document.getElementById('forceRebuild')?.checked || false,
      include_kb: document.getElementById('includeKB')?.checked !== false,
      batch_size: parseInt(document.getElementById('batchSize')?.value) || 50,
      max_retries: parseInt(document.getElementById('maxRetries')?.value) || 3,
      parallel_workers: parseInt(document.getElementById('parallelWorkers')?.value) || 4
    };
  }

  getActiveJobId() {
    // DOM에서 활성 작업 ID를 찾는 로직
    const activeJobElement = document.querySelector('[data-job-status="running"], [data-job-status="paused"]');
    return activeJobElement?.dataset.jobId || null;
  }

  getJobStatusBadge(status) {
    const statusMap = {
      'pending': '<span class="badge badge-secondary">대기중</span>',
      'running': '<span class="badge badge-primary">실행중</span>',
      'paused': '<span class="badge badge-warning">일시정지</span>',
      'completed': '<span class="badge badge-success">완료</span>',
      'failed': '<span class="badge badge-danger">실패</span>',
      'cancelled': '<span class="badge badge-dark">취소됨</span>'
    };
    return statusMap[status] || `<span class="badge badge-light">${status}</span>`;
  }

  showLoading(message = '로딩 중...') {
    // 간단한 로딩 표시
    const loadingElement = document.getElementById('loadingIndicator');
    if (loadingElement) {
      loadingElement.textContent = message;
      loadingElement.style.display = 'block';
    }
  }

  hideLoading() {
    const loadingElement = document.getElementById('loadingIndicator');
    if (loadingElement) {
      loadingElement.style.display = 'none';
    }
  }

  showToast(message, type = 'info') {
    // 간단한 토스트 알림
    const toast = document.createElement('div');
    toast.className = `alert alert-${type === 'error' ? 'danger' : type} alert-dismissible fade show`;
    toast.style.cssText = `
      position: fixed;
      top: 20px;
      right: 20px;
      z-index: 9999;
      max-width: 300px;
    `;
    toast.innerHTML = `
      ${message}
      <button type="button" class="close" onclick="this.parentElement.remove()">
        <span>&times;</span>
      </button>
    `;
    
    document.body.appendChild(toast);
    
    // 5초 후 자동 제거
    setTimeout(() => {
      if (toast.parentNode) {
        toast.parentNode.removeChild(toast);
      }
    }, 5000);
  }

  async showAddAgentModal() {
    // 에이전트 추가 모달
    const name = await this.showInputDialog('에이전트 이름을 입력하세요:');
    if (name && name.trim()) {
      this.addAgent(name.trim());
    }
  }

  async addAgent(name) {
    try {
      const response = await fetch(`${this.baseURL}/agents`, {
        method: 'POST',
        headers: this.authHeaders,
        body: JSON.stringify({
          name: name,
          is_active: true
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      this.showToast(`에이전트 '${name}'이 추가되었습니다`, 'success');
      this.loadAgents();
    } catch (error) {
      console.error('❌ 에이전트 추가 실패:', error);
      this.showToast('에이전트 추가 실패: ' + error.message, 'error');
    }
  }

  /**
   * 🔔 확인 다이얼로그 표시 (confirm 대체)
   * @param {string} message - 확인 메시지
   * @returns {boolean} 사용자 선택 결과
   */
  showConfirmDialog(message) {
    // 간단한 DOM 기반 확인 다이얼로그
    const dialog = document.createElement('div');
    dialog.style.cssText = `
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background: rgba(0, 0, 0, 0.5);
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 10000;
    `;

    dialog.innerHTML = `
      <div style="
        background: white;
        border-radius: 8px;
        padding: 24px;
        max-width: 400px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
        text-align: center;
      ">
        <div style="margin-bottom: 20px; font-size: 16px; color: #374151;">
          ${message}
        </div>
        <div style="display: flex; gap: 12px; justify-content: center;">
          <button id="confirmYes" style="
            background: #dc2626;
            color: white;
            border: none;
            border-radius: 4px;
            padding: 8px 16px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 500;
          ">확인</button>
          <button id="confirmNo" style="
            background: #6b7280;
            color: white;
            border: none;
            border-radius: 4px;
            padding: 8px 16px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 500;
          ">취소</button>
        </div>
      </div>
    `;

    document.body.appendChild(dialog);

    return new Promise((resolve) => {
      dialog.querySelector('#confirmYes').addEventListener('click', () => {
        dialog.remove();
        resolve(true);
      });
      
      dialog.querySelector('#confirmNo').addEventListener('click', () => {
        dialog.remove();
        resolve(false);
      });

      // 배경 클릭시 취소
      dialog.addEventListener('click', (e) => {
        if (e.target === dialog) {
          dialog.remove();
          resolve(false);
        }
      });
    });
  }

  /**
   * 📝 입력 다이얼로그 표시 (prompt 대체)
   * @param {string} message - 입력 요청 메시지
   * @returns {string|null} 사용자 입력값 또는 null
   */
  showInputDialog(message) {
    // 간단한 DOM 기반 입력 다이얼로그
    const dialog = document.createElement('div');
    dialog.style.cssText = `
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background: rgba(0, 0, 0, 0.5);
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 10000;
    `;

    dialog.innerHTML = `
      <div style="
        background: white;
        border-radius: 8px;
        padding: 24px;
        max-width: 400px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
      ">
        <div style="margin-bottom: 16px; font-size: 16px; color: #374151;">
          ${message}
        </div>
        <input type="text" id="inputValue" style="
          width: 100%;
          border: 1px solid #d1d5db;
          border-radius: 4px;
          padding: 8px 12px;
          font-size: 14px;
          margin-bottom: 16px;
          box-sizing: border-box;
        " placeholder="이름을 입력하세요">
        <div style="display: flex; gap: 12px; justify-content: flex-end;">
          <button id="inputOk" style="
            background: #3b82f6;
            color: white;
            border: none;
            border-radius: 4px;
            padding: 8px 16px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 500;
          ">확인</button>
          <button id="inputCancel" style="
            background: #6b7280;
            color: white;
            border: none;
            border-radius: 4px;
            padding: 8px 16px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 500;
          ">취소</button>
        </div>
      </div>
    `;

    document.body.appendChild(dialog);
    const input = dialog.querySelector('#inputValue');
    input.focus();

    return new Promise((resolve) => {
      const handleOk = () => {
        const value = input.value.trim();
        dialog.remove();
        resolve(value || null);
      };

      const handleCancel = () => {
        dialog.remove();
        resolve(null);
      };

      dialog.querySelector('#inputOk').addEventListener('click', handleOk);
      dialog.querySelector('#inputCancel').addEventListener('click', handleCancel);
      
      // Enter 키로 확인
      input.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
          handleOk();
        }
      });

      // 배경 클릭시 취소
      dialog.addEventListener('click', (e) => {
        if (e.target === dialog) {
          handleCancel();
        }
      });
    });
  }
}

// 페이지 로드 시 AdminConsole 초기화
document.addEventListener('DOMContentLoaded', function() {
  console.log('🏗️ 관리자 콘솔 초기화 시작');
  window.adminConsole = new AdminConsole();
});