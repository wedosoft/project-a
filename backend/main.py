"""
AI Contact Center OS - FastAPI Backend
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.config import get_settings
from backend.routes import tickets, assist, metrics, health
from backend.middleware.tenant_middleware import TenantMiddleware
from backend.middleware.logging_middleware import LoggingMiddleware

settings = get_settings()

app = FastAPI(
    title="AI Contact Center OS",
    description="MVP Backend API with LangGraph orchestration",
    version="1.0.0"
)

# Middleware 순서 중요: 아래에서 위로 실행됨
# 1. CORS (가장 먼저)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 프로덕션에서는 제한 필요
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Logging (요청/응답 로깅)
app.add_middleware(LoggingMiddleware)

# 3. Tenant (테넌트 ID 추출 및 검증)
app.add_middleware(TenantMiddleware)

# 라우터 등록 (prefix는 각 라우터 파일에서 정의됨)
app.include_router(tickets.router)
app.include_router(assist.router)
app.include_router(metrics.router)
app.include_router(health.router)

# Admin API 라우터 추가
from backend.routes import admin
app.include_router(admin.router)

@app.get("/")
async def root():
    return {"message": "AI Contact Center OS API", "version": "1.0.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
