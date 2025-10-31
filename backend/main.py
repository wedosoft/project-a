"""
AI Contact Center OS - FastAPI Backend
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.config import get_settings
from backend.routes import tickets, assist, metrics

settings = get_settings()

app = FastAPI(
    title="AI Contact Center OS",
    description="MVP Backend API with LangGraph orchestration",
    version="1.0.0"
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 프로덕션에서는 제한 필요
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(tickets.router, prefix="/api/tickets", tags=["tickets"])
app.include_router(assist.router, prefix="/api/assist", tags=["assist"])
app.include_router(metrics.router, prefix="/api/metrics", tags=["metrics"])

@app.get("/")
async def root():
    return {"message": "AI Contact Center OS API", "version": "1.0.0"}

@app.get("/health")
async def health():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
