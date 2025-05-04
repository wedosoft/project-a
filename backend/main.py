import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
import anthropic
import chromadb
from chromadb.utils import embedding_functions

# 환경 변수에서 Claude(Anthropic) API 키를 불러옵니다.
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY:
    raise RuntimeError("ANTHROPIC_API_KEY 환경 변수가 필요합니다.")

# FastAPI 앱 생성
app = FastAPI()

# 최신 Chroma 클라이언트(PersistentClient) 및 컬렉션 초기화
chroma_client = chromadb.PersistentClient(path="./chroma_db")
collection_name = "docs"
if collection_name not in [c.name for c in chroma_client.list_collections()]:
    chroma_client.create_collection(collection_name)
collection = chroma_client.get_collection(collection_name)

# OpenAI 임베딩 함수 (임베딩은 OpenAI 사용, 필요시 교체)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY 환경 변수가 필요합니다. (임베딩용)")
embed_fn = embedding_functions.OpenAIEmbeddingFunction(
    api_key=OPENAI_API_KEY,
    model_name="text-embedding-ada-002"
)

# 요청/응답 모델
class QueryRequest(BaseModel):
    query: str
    top_k: int = 3

class QueryResponse(BaseModel):
    answer: str
    context_docs: List[str]

@app.post("/query", response_model=QueryResponse)
async def query_endpoint(req: QueryRequest):
    # 1. 쿼리 임베딩
    query_embedding = embed_fn([req.query])[0]

    # 2. VectorDB에서 top_k 문서 검색
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=req.top_k
    )
    docs = results.get("documents", [[]])[0]
    if not docs:
        docs = []

    # 3. Claude 프롬프트 생성
    context = "\n".join(docs)
    prompt = f"""
다음은 고객 지원 티켓에 대한 질문입니다. 아래의 참고 문서를 바탕으로 친절하고 명확하게 답변해 주세요.

[참고 문서]
{context}

[질문]
{req.query}

[답변]"""

    # 4. Claude LLM 호출
    client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    try:
        response = await client.messages.create(
            model="claude-3-haiku-20240307",  # 필요시 claude-3-opus 등으로 변경 가능
            max_tokens=512,
            temperature=0.2,
            system="당신은 친절한 고객 지원 AI입니다.",
            messages=[{"role": "user", "content": prompt}]
        )
        answer = response.content[0].text.strip()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return QueryResponse(answer=answer, context_docs=docs) 