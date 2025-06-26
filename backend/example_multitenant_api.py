"""
멀티테넌트 API 예시
테넌트별 설정을 사용하여 데이터를 수집하고 처리하는 API 예시
"""

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.base import BaseHTTPMiddleware
import logging

from core.database.tenant_context import (
    tenant_context, 
    get_current_tenant, 
    get_current_freshdesk_config,
    create_freshdesk_client,
    tenant_middleware,
    extract_tenant_from_request,
    with_tenant_context
)

logger = logging.getLogger(__name__)

app = FastAPI(title="멀티테넌트 SaaS API")

# 테넌트 미들웨어 추가
app.add_middleware(BaseHTTPMiddleware, dispatch=tenant_middleware)

# =====================================================
# API 엔드포인트들
# =====================================================

@app.get("/api/v1/tenant/info")
async def get_tenant_info():
    """현재 테넌트 정보 반환"""
    current_tenant = get_current_tenant()
    
    if not current_tenant:
        raise HTTPException(
            status_code=400,
            detail="테넌트 컨텍스트가 설정되지 않았습니다. 헤더에 X-Company-ID를 포함하세요."
        )
    
    return {
        "company_id": current_tenant.company_id,
        "platform": current_tenant.platform,
        "company_name": current_tenant.get_setting("company_name", "Unknown"),
        "timezone": current_tenant.get_setting("timezone", "UTC"),
        "features": current_tenant.get_setting("features", {})
    }

@app.get("/api/v1/tenant/config")
async def get_tenant_config():
    """현재 테넌트의 설정 반환 (민감한 정보 제외)"""
    current_tenant = get_current_tenant()
    
    if not current_tenant:
        raise HTTPException(status_code=400, detail="테넌트 컨텍스트 없음")
    
    # 플랫폼 설정 (API 키 마스킹)
    platform_config = current_tenant.get_platform_config()
    if 'api_key' in platform_config:
        platform_config['api_key'] = platform_config['api_key'][:10] + "***"
    
    return {
        "platform_config": platform_config,
        "features": current_tenant.get_setting("features", {}),
        "settings": {
            "timezone": current_tenant.get_setting("timezone"),
            "company_name": current_tenant.get_setting("company_name")
        }
    }

@app.post("/api/v1/data/collect")
async def collect_data(request: Request):
    """테넌트별 설정을 사용하여 데이터 수집"""
    current_tenant = get_current_tenant()
    
    if not current_tenant:
        raise HTTPException(status_code=400, detail="테넌트 컨텍스트 없음")
    
    try:
        # 현재 테넌트의 Freshdesk 설정 가져오기
        freshdesk_config = get_current_freshdesk_config()
        
        # 설정 검증
        if not freshdesk_config.get('domain') or not freshdesk_config.get('api_key'):
            raise HTTPException(
                status_code=400,
                detail="Freshdesk 설정이 완전하지 않습니다. 관리자에게 문의하세요."
            )
        
        # Freshdesk 클라이언트 생성
        client_config = create_freshdesk_client()
        
        # 실제 데이터 수집 시뮬레이션
        collection_result = {
            "status": "success",
            "tenant": {
                "company_id": current_tenant.company_id,
                "company_name": current_tenant.get_setting("company_name"),
                "platform": current_tenant.platform
            },
            "config_used": {
                "domain": freshdesk_config['domain'],
                "rate_limit": freshdesk_config['rate_limit'],
                "collect_attachments": freshdesk_config.get('collect_attachments', True)
            },
            "collected": {
                "tickets": 150,  # 시뮬레이션 데이터
                "conversations": 450,
                "attachments": 23 if freshdesk_config.get('collect_attachments') else 0
            },
            "message": f"{freshdesk_config['domain']}에서 데이터 수집 완료"
        }
        
        return collection_result
        
    except Exception as e:
        logger.error(f"데이터 수집 실패: {e}")
        raise HTTPException(status_code=500, detail=f"데이터 수집 실패: {str(e)}")

@app.get("/api/v1/data/tickets")
async def get_tickets():
    """현재 테넌트의 티켓 목록 반환"""
    current_tenant = get_current_tenant()
    
    if not current_tenant:
        raise HTTPException(status_code=400, detail="테넌트 컨텍스트 없음")
    
    # 실제로는 데이터베이스에서 해당 테넌트의 티켓을 조회
    # 여기서는 시뮬레이션
    company_name = current_tenant.get_setting("company_name", "Unknown")
    
    return {
        "company_id": current_tenant.company_id,
        "company_name": company_name,
        "tickets": [
            {
                "id": f"{current_tenant.company_id}_001",
                "subject": f"{company_name} - 첫 번째 티켓",
                "status": "open",
                "platform": current_tenant.platform
            },
            {
                "id": f"{current_tenant.company_id}_002", 
                "subject": f"{company_name} - 두 번째 티켓",
                "status": "pending",
                "platform": current_tenant.platform
            }
        ],
        "total": 2
    }

# =====================================================
# 수동 테넌트 지정 API (관리자용)
# =====================================================

@app.post("/api/v1/admin/collect/{company_id}")
@with_tenant_context(company_id_param='company_id')
async def admin_collect_data(company_id: int, platform: str = "freshdesk"):
    """관리자가 특정 테넌트의 데이터를 수집 (데코레이터 사용)"""
    current_tenant = get_current_tenant()
    
    freshdesk_config = get_current_freshdesk_config()
    company_name = current_tenant.get_setting("company_name", "Unknown")
    
    return {
        "message": f"관리자 요청으로 {company_name}(ID: {company_id}) 데이터 수집 시작",
        "tenant_config": {
            "domain": freshdesk_config.get('domain', 'N/A'),
            "has_api_key": bool(freshdesk_config.get('api_key')),
            "rate_limit": freshdesk_config.get('rate_limit', 100)
        }
    }

@app.get("/api/v1/admin/tenants/{company_id}/stats")
async def get_tenant_stats(company_id: int, platform: str = "freshdesk"):
    """특정 테넌트의 통계 조회 (수동 컨텍스트 설정)"""
    
    # 수동으로 테넌트 컨텍스트 설정
    with tenant_context(company_id, platform):
        current_tenant = get_current_tenant()
        
        company_name = current_tenant.get_setting("company_name", "Unknown")
        features = current_tenant.get_setting("features", {})
        
        # 실제로는 데이터베이스에서 통계 조회
        return {
            "company_id": company_id,
            "company_name": company_name,
            "platform": platform,
            "features": features,
            "stats": {
                "total_tickets": 150,
                "total_conversations": 450,
                "total_attachments": 23,
                "last_collection": "2025-06-26T12:00:00Z"
            }
        }

# =====================================================
# 헬스체크 및 시스템 API (테넌트 무관)
# =====================================================

@app.get("/health")
async def health_check():
    """시스템 헬스체크 (테넌트 컨텍스트 불필요)"""
    return {"status": "healthy", "timestamp": "2025-06-26T12:00:00Z"}

@app.get("/api/v1/system/supported-platforms")
async def get_supported_platforms():
    """지원하는 플랫폼 목록 (시스템 레벨)"""
    return {
        "platforms": ["freshdesk", "zendesk", "servicenow"],
        "default": "freshdesk"
    }

# =====================================================
# 에러 핸들러
# =====================================================

@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return {
        "error": "validation_error",
        "detail": str(exc),
        "hint": "헤더에 X-Company-ID와 X-Platform을 포함하거나 URL 파라미터를 사용하세요."
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")
