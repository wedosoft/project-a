"""
API 키 관리 대시보드

고객 증가에 따른 API 키 사용량 모니터링 및 관리
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List
from fastapi import APIRou        # 사용률에 따른 색상 결정
        rpm_color = "usage-low" if rpm_ratio < 60 else ("usage-medium" if rpm_ratio < 80 else "usage-high")
        tpm_color = "usage-low" if tpm_ratio < 60 else ("usage-medium" if tpm_ratio < 80 else "usage-high"), HTTPException, Depends
from fastapi.responses import HTMLResponse
import json

from core.llm.scalable_key_manager import scalable_key_manager, APIKeyStrategy

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api-keys/dashboard", response_class=HTMLResponse)
async def api_keys_dashboard():
    """API 키 관리 대시보드 HTML"""
    
    stats = scalable_key_manager.get_usage_stats()
    health = await scalable_key_manager.health_check()
    
    html_content = f"""
    <!DOCTYPE html>
    <html lang="ko">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>API 키 관리 대시보드</title>
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }}
            .container {{ max-width: 1400px; margin: 0 auto; }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 10px; margin-bottom: 20px; }}
            .status-card {{ background: white; padding: 20px; border-radius: 10px; margin-bottom: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            .status-healthy {{ border-left: 5px solid #27ae60; }}
            .status-warning {{ border-left: 5px solid #f39c12; }}
            .status-error {{ border-left: 5px solid #e74c3c; }}
            .provider-section {{ background: white; padding: 20px; border-radius: 10px; margin-bottom: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            .provider-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; }}
            .provider-stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 20px; }}
            .stat-item {{ background: #f8f9fa; padding: 15px; border-radius: 8px; text-align: center; }}
            .stat-value {{ font-size: 24px; font-weight: bold; color: #2c3e50; }}
            .stat-label {{ color: #7f8c8d; font-size: 14px; }}
            .keys-table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
            .keys-table th, .keys-table td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
            .keys-table th {{ background-color: #f8f9fa; font-weight: 600; }}
            .usage-bar {{ width: 100%; height: 20px; background-color: #ecf0f1; border-radius: 10px; overflow: hidden; }}
            .usage-fill {{ height: 100%; transition: width 0.3s ease; }}
            .usage-low {{ background-color: #27ae60; }}
            .usage-medium {{ background-color: #f39c12; }}
            .usage-high {{ background-color: #e74c3c; }}
            .refresh-btn {{ background: #3498db; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; margin-left: 10px; }}
            .refresh-btn:hover {{ background: #2980b9; }}
            .timestamp {{ color: #7f8c8d; font-size: 12px; }}
        </style>
        <script>
            function refreshDashboard() {{
                location.reload();
            }}
            
            function getUsageColor(current, max) {{
                const ratio = current / max;
                if (ratio < 0.6) return 'usage-low';
                if (ratio < 0.8) return 'usage-medium';
                return 'usage-high';
            }}
            
            setInterval(refreshDashboard, 60000); // 1분마다 자동 새로고침
        </script>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🔑 API 키 관리 대시보드</h1>
                <p>실시간 API 키 사용량 모니터링 및 관리</p>
                <div class="timestamp">마지막 업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
            </div>
            
            <div class="status-card status-{health['status']}">
                <h2>시스템 상태: {health['status'].upper()}</h2>
                {_render_health_issues(health)}
                <button class="refresh-btn" onclick="refreshDashboard()">새로고침</button>
            </div>
            
            {_render_provider_sections(stats)}
        </div>
    </body>
    </html>
    """
    
    return html_content


def _render_health_issues(health: Dict[str, Any]) -> str:
    """상태 이슈 렌더링"""
    if not health.get('issues'):
        return "<p>✅ 모든 시스템이 정상 작동 중입니다.</p>"
    
    issues_html = "<h3>⚠️ 발견된 문제점:</h3><ul>"
    for issue in health['issues']:
        issues_html += f"<li>{issue}</li>"
    issues_html += "</ul>"
    
    if health.get('recommendations'):
        issues_html += "<h3>💡 권장사항:</h3><ul>"
        for rec in health['recommendations']:
            issues_html += f"<li>{rec}</li>"
        issues_html += "</ul>"
    
    return issues_html


def _render_provider_sections(stats: Dict[str, Any]) -> str:
    """제공자별 섹션 렌더링"""
    html = ""
    
    for provider, provider_stats in stats.items():
        html += f"""
        <div class="provider-section">
            <div class="provider-header">
                <h2>🤖 {provider.upper()} Provider</h2>
                <span class="status">활성 키: {provider_stats['active_keys']}/{provider_stats['total_keys']}</span>
            </div>
            
            <div class="provider-stats">
                <div class="stat-item">
                    <div class="stat-value">{provider_stats['total_rpm']}</div>
                    <div class="stat-label">현재 RPM</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">{provider_stats['total_tpm']:,}</div>
                    <div class="stat-label">현재 TPM</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">${provider_stats['total_daily_cost']:.2f}</div>
                    <div class="stat-label">일일 사용 비용</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">{provider_stats['active_keys']}</div>
                    <div class="stat-label">활성 키</div>
                </div>
            </div>
            
            <table class="keys-table">
                <thead>
                    <tr>
                        <th>키 ID</th>
                        <th>Tier</th>
                        <th>RPM 사용량</th>
                        <th>TPM 사용량</th>
                        <th>일일 비용</th>
                        <th>할당된 고객</th>
                    </tr>
                </thead>
                <tbody>
                    {_render_key_rows(provider_stats['keys'])}
                </tbody>
            </table>
        </div>
        """
    
    return html


def _render_key_rows(keys: List[Dict[str, Any]]) -> str:
    """키 테이블 행 렌더링"""
    html = ""
    
    for key in keys:
        # RPM 사용률 계산
        rpm_parts = key['rpm_usage'].split('/')
        rpm_current = int(rpm_parts[0])
        rpm_max = int(rpm_parts[1])
        rpm_ratio = (rpm_current / rpm_max) * 100 if rpm_max > 0 else 0
        
        # TPM 사용률 계산
        tpm_parts = key['tpm_usage'].split('/')
        tpm_current = int(tpm_parts[0])
        tpm_max = int(tpm_parts[1])
        tpm_ratio = (tpm_current / tpm_max) * 100 if tpm_max > 0 else 0
        
        # 사용률에 따른 색상 결정
        rpm_color = "usage-low" if rpm_ratio < 60 else ("usage-medium" if rpm_ratio < 80 else "usage-high")
        tpm_color = "usage-low" if tpm_ratio < 60 else ("usage-medium" if tmp_ratio < 80 else "usage-high")
        
        html += f"""
        <tr>
            <td><code>{key['key_id']}</code></td>
            <td><span class="tier-{key['tier']}">{key['tier']}</span></td>
            <td>
                <div>{key['rpm_usage']}</div>
                <div class="usage-bar">
                    <div class="usage-fill {rpm_color}" style="width: {rpm_ratio}%"></div>
                </div>
            </td>
            <td>
                <div>{key['tpm_usage']}</div>
                <div class="usage-bar">
                    <div class="usage-fill {tpm_color}" style="width: {tmp_ratio}%"></div>
                </div>
            </td>
            <td>{key['daily_cost']}</td>
            <td>{key['assigned_customers']}</td>
        </tr>
        """
    
    return html


@router.get("/api-keys/stats")
async def get_api_key_stats():
    """API 키 사용량 통계 JSON"""
    return scalable_key_manager.get_usage_stats()


@router.get("/api-keys/health")
async def get_api_key_health():
    """API 키 시스템 상태 체크"""
    return await scalable_key_manager.health_check()


@router.post("/api-keys/strategy")
async def update_api_key_strategy(strategy: str):
    """API 키 할당 전략 변경"""
    try:
        new_strategy = APIKeyStrategy(strategy)
        scalable_key_manager.strategy = new_strategy
        return {"status": "success", "strategy": strategy}
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid strategy: {strategy}")


@router.get("/api-keys/customer/{customer_id}")
async def get_customer_api_assignments(customer_id: str):
    """고객별 API 키 할당 현황"""
    assignments = scalable_key_manager.customer_assignments.get(customer_id, {})
    return {"customer_id": customer_id, "assignments": assignments}


# CLI 도구도 함께 제공
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="API 키 관리 CLI")
    parser.add_argument("--stats", action="store_true", help="사용량 통계 출력")
    parser.add_argument("--health", action="store_true", help="시스템 상태 확인")
    parser.add_argument("--strategy", type=str, help="키 할당 전략 변경")
    
    args = parser.parse_args()
    
    async def main():
        if args.stats:
            stats = scalable_key_manager.get_usage_stats()
            print(json.dumps(stats, indent=2, ensure_ascii=False))
        
        if args.health:
            health = await scalable_key_manager.health_check()
            print(json.dumps(health, indent=2, ensure_ascii=False))
        
        if args.strategy:
            try:
                new_strategy = APIKeyStrategy(args.strategy)
                scalable_key_manager.strategy = new_strategy
                print(f"전략이 {args.strategy}로 변경되었습니다.")
            except ValueError:
                print(f"잘못된 전략입니다: {args.strategy}")
                print("가능한 전략: round_robin, load_based, customer_dedicated, hybrid")
    
    asyncio.run(main())
