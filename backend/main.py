"""
Freshdesk Custom App 백엔드 서비스

이 프로젝트는 Freshdesk Custom App(Prompt Canvas)을 위한 백엔드 서비스입니다.
RAG(Retrieval-Augmented Generation) 기술을 활용하여 Freshdesk 티켓과 지식베이스를 기반으로 
AI 기반 응답 생성 기능을 제공합니다.

프로젝트 규칙 및 가이드라인: /PROJECT_RULES.md 참조
"""
import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
import anthropic
from fetcher import fetch_tickets, fetch_kb_articles
from embedder import embed_documents
from retriever import retrieve_top_k_docs

# 환경 변수에서 Claude(Anthropic) API 키를 불러옵니다.
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY:
    raise RuntimeError("ANTHROPIC_API_KEY 환경 변수가 필요합니다.")

# FastAPI 앱 생성
app = FastAPI()

# 요청/응답 모델
class QueryRequest(BaseModel):
    query: str
    top_k: int = 3

class QueryResponse(BaseModel):
    answer: str
    context_docs: List[str]

def build_prompt(context: str, query: str) -> str:
    """
    LLM에 입력할 프롬프트를 생성합니다.
    """
    return f"""
다음은 고객 지원 티켓에 대한 질문입니다. 아래의 참고 문서를 바탕으로 친절하고 명확하게 답변해 주세요.

[참고 문서]
{context}

[질문]
{query}

[답변]"""

async def call_claude_llm(prompt: str) -> str:
    """
    Claude LLM을 호출하여 답변을 생성합니다.
    """
    client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    response = await client.messages.create(
        model="claude-3-haiku-20240307",
        max_tokens=512,
        temperature=0.2,
        system="당신은 친절한 고객 지원 AI입니다.",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text.strip()

@app.post("/query", response_model=QueryResponse)
async def query_endpoint(req: QueryRequest):
    query_embedding = embed_documents([req.query])[0]
    docs = retrieve_top_k_docs(query_embedding, req.top_k)
    context = "\n".join(docs)
    prompt = build_prompt(context, req.query)
    try:
        answer = await call_claude_llm(prompt)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return QueryResponse(answer=answer, context_docs=docs)