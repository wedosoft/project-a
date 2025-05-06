"""
Freshdesk Custom App 백엔드 서비스

이 프로젝트는 Freshdesk Custom App(Prompt Canvas)을 위한 백엔드 서비스입니다.
RAG(Retrieval-Augmented Generation) 기술을 활용하여 Freshdesk 티켓과 지식베이스를 기반으로
AI 기반 응답 생성 기능을 제공합니다.

프로젝트 규칙 및 가이드라인: /PROJECT_RULES.md 참조
"""

import os
import uuid
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Union
import anthropic
from fetcher import fetch_tickets, fetch_kb_articles
from embedder import embed_documents
from retriever import retrieve_top_k_docs
import re

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
    use_blocks: bool = False  # 블록 기반 응답 포맷 사용 여부


class DocumentInfo(BaseModel):
    """검색된 문서 정보를 담는 모델"""

    title: str
    content: str
    source_id: str = ""
    source_url: str = ""
    relevance_score: float = 0.0


# 블록 기반 응답 형식을 위한 모델
class Source(BaseModel):
    """출처 정보"""

    title: str = ""
    url: str = ""


class Block(BaseModel):
    """응답 블록 기본 모델"""

    id: str = Field(default_factory=lambda: f"blk_{uuid.uuid4().hex[:6]}")
    type: str
    content: str
    source: Optional[Source] = None


class TextBlock(Block):
    """텍스트 블록"""

    type: str = "text"


class ImageBlock(Block):
    """이미지 블록"""

    type: str = "image"
    url: str
    content: str = ""  # 이미지 설명으로 사용
    description: str = ""


class BlockBasedResponse(BaseModel):
    """블록 기반 응답 모델"""

    blocks: List[Union[TextBlock, ImageBlock]]
    context_docs: List[DocumentInfo]


class QueryResponse(BaseModel):
    answer: str
    context_docs: List[DocumentInfo]
    context_images: List[dict] = []


def build_prompt(context: str, query: str, use_blocks: bool = False) -> str:
    """
    LLM에 입력할 프롬프트를 생성합니다.
    """
    base_prompt = f"""
다음은 고객 지원 티켓에 대한 질문입니다. 아래의 참고 문서를 바탕으로 친절하고 명확하게 답변해 주세요.

[참고 문서]
{context}

[질문]
{query}

[답변]"""

    if use_blocks:
        # 블록 기반 응답을 위한 확장 프롬프트
        extended_prompt = (
            base_prompt
            + """

답변은 관련 문서의 출처를 문단별로 명시해주세요. 예를 들어:

1. 첫 번째 문단 내용... (출처: 문서 제목)
2. 두 번째 문단 내용... (출처: 다른 문서 제목)

이렇게 구성하면 저는 응답을 개별 블록으로 구성할 수 있습니다."""
        )
        return extended_prompt

    return base_prompt


async def call_claude_llm(prompt: str) -> str:
    """
    Claude LLM을 호출하여 답변을 생성합니다.
    """
    client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    response = await client.messages.create(
        model="claude-3-haiku-20240307",
        max_tokens=1024,  # 512에서 1024로 증가
        temperature=0.2,
        system="당신은 친절한 고객 지원 AI입니다.",
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


def parse_llm_response_to_blocks(
    answer: str, structured_docs: List[DocumentInfo]
) -> List[Union[TextBlock, ImageBlock]]:
    """
    LLM 응답을 블록 단위로 분리하고 출처 정보를 연결합니다.
    """
    blocks = []

    # 문단별로 나누기
    paragraphs = [p for p in answer.split("\n\n") if p.strip()]

    # 문서 제목 -> 문서 정보 매핑 생성
    title_to_doc = {doc.title: doc for doc in structured_docs if doc.title}

    for i, paragraph in enumerate(paragraphs):
        # 출처 정보 추출을 위한 패턴 - "(출처: 문서 제목)" 형식 찾기
        source_match = re.search(r"\(출처:\s*([^)]+)\)", paragraph)
        source = None
        content = paragraph

        if source_match:
            source_title = source_match.group(1).strip()
            # 출처 정보 제거한 내용만 저장
            content = paragraph.replace(source_match.group(0), "").strip()

            # 출처 문서 찾기
            if source_title in title_to_doc:
                doc = title_to_doc[source_title]
                source = Source(title=doc.title, url=doc.source_url)

        # 텍스트 블록 생성
        text_block = TextBlock(content=content, source=source)
        blocks.append(text_block)

    return blocks


def convert_image_info_to_blocks(context_images: List[dict]) -> List[ImageBlock]:
    """
    이미지 정보를 이미지 블록으로 변환합니다.
    """
    image_blocks = []

    for img in context_images:
        if img.get("url"):
            image_block = ImageBlock(
                url=img["url"],
                description=img.get("name", "이미지"),
                content=img.get("title", ""),
            )
            image_blocks.append(image_block)

    return image_blocks


@app.post("/query", response_model=QueryResponse)
async def query_endpoint(req: QueryRequest):
    query_embedding = embed_documents([req.query])[0]
    results = retrieve_top_k_docs(query_embedding, req.top_k)

    # 검색된 문서와 메타데이터 추출
    docs = results["documents"]
    metadatas = results["metadatas"]
    distances = results["distances"]  # 유사도 점수 (낮을수록 관련성 높음)

    # 컨텍스트 생성
    context = "\n".join(docs)
    prompt = build_prompt(context, req.query)

    # 구조화된 문서 정보 생성
    structured_docs = []
    for i, (doc, metadata, distance) in enumerate(zip(docs, metadatas, distances)):
        # 문서에서 제목과 내용 추출
        lines = doc.split("\n", 2)  # 최대 2개의 줄바꿈으로 분리
        title = ""
        content = doc

        # 제목 형식 "제목: XXX" 추출
        if len(lines) > 0 and lines[0].startswith("제목:"):
            title = lines[0].replace("제목:", "").strip()

            # 내용 추출 (제목 이후의 모든 텍스트)
            if len(lines) > 1:
                content = "\n".join(lines[1:]).strip()
                # "설명:" 접두사 제거
                if content.startswith("설명:"):
                    content = content.replace("설명:", "", 1).strip()

        # 유사도 점수를 백분율로 변환 (1에 가까울수록 관련성 높음)
        # 코사인 거리는 0~2 범위이므로, (2-distance)/2를 계산하여 0~1 범위로 변환
        relevance_score = round(((2 - distance) / 2) * 100, 1)

        doc_info = DocumentInfo(
            title=title,
            content=content,
            source_id=metadata.get("source_id", ""),
            source_url=metadata.get("source_url", ""),
            relevance_score=relevance_score,
        )
        structured_docs.append(doc_info)

    # 이미지 정보 추출
    context_images = []
    for i, metadata in enumerate(metadatas):
        # 메타데이터에 이미지 첨부파일 정보가 있으면 추가
        image_attachments = metadata.get("image_attachments", "")
        if image_attachments:
            try:
                # 문자열로 저장된 경우 JSON 파싱
                if isinstance(image_attachments, str):
                    import json

                    image_attachments = json.loads(image_attachments)

                # 리스트인 경우 각 이미지 정보 추출
                if isinstance(image_attachments, list):
                    for img in image_attachments:
                        context_images.append(
                            {
                                "name": img.get("name", ""),
                                "url": img.get("url", ""),
                                "content_type": img.get("content_type", ""),
                                "doc_index": i,  # 어떤 문서에서 왔는지 추적
                                "source_type": img.get("source_type", ""),
                                "source_id": metadata.get("source_id", ""),
                                "title": (
                                    structured_docs[i].title
                                    if i < len(structured_docs)
                                    else ""
                                ),
                            }
                        )
            except Exception as e:
                print(f"이미지 정보 파싱 오류: {e}")

    # LLM 호출
    try:
        answer = await call_claude_llm(prompt)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return QueryResponse(
        answer=answer, context_docs=structured_docs, context_images=context_images
    )


@app.post("/query/blocks", response_model=BlockBasedResponse)
async def query_blocks_endpoint(req: QueryRequest):
    """
    블록 기반 응답 형식으로 쿼리 결과를 반환합니다.
    """
    query_embedding = embed_documents([req.query])[0]
    results = retrieve_top_k_docs(query_embedding, req.top_k)

    # 검색된 문서와 메타데이터 추출
    docs = results["documents"]
    metadatas = results["metadatas"]
    distances = results["distances"]

    # 컨텍스트 생성
    context = "\n".join(docs)
    # 블록 기반 응답을 위한 프롬프트 생성
    prompt = build_prompt(context, req.query, use_blocks=True)

    # 구조화된 문서 정보 생성 (기존 함수와 동일)
    structured_docs = []
    for i, (doc, metadata, distance) in enumerate(zip(docs, metadatas, distances)):
        lines = doc.split("\n", 2)
        title = ""
        content = doc

        if len(lines) > 0 and lines[0].startswith("제목:"):
            title = lines[0].replace("제목:", "").strip()
            if len(lines) > 1:
                content = "\n".join(lines[1:]).strip()
                if content.startswith("설명:"):
                    content = content.replace("설명:", "", 1).strip()

        relevance_score = round(((2 - distance) / 2) * 100, 1)

        doc_info = DocumentInfo(
            title=title,
            content=content,
            source_id=metadata.get("source_id", ""),
            source_url=metadata.get("source_url", ""),
            relevance_score=relevance_score,
        )
        structured_docs.append(doc_info)

    # 이미지 정보 추출 (기존 함수와 동일)
    context_images = []
    for i, metadata in enumerate(metadatas):
        image_attachments = metadata.get("image_attachments", "")
        if image_attachments:
            try:
                if isinstance(image_attachments, str):
                    import json

                    image_attachments = json.loads(image_attachments)

                if isinstance(image_attachments, list):
                    for img in image_attachments:
                        context_images.append(
                            {
                                "name": img.get("name", ""),
                                "url": img.get("url", ""),
                                "content_type": img.get("content_type", ""),
                                "doc_index": i,
                                "source_type": img.get("source_type", ""),
                                "source_id": metadata.get("source_id", ""),
                                "title": (
                                    structured_docs[i].title
                                    if i < len(structured_docs)
                                    else ""
                                ),
                            }
                        )
            except Exception as e:
                print(f"이미지 정보 파싱 오류: {e}")

    # LLM 호출
    try:
        answer = await call_claude_llm(prompt)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # 텍스트 응답을 블록으로 변환
    text_blocks = parse_llm_response_to_blocks(answer, structured_docs)

    # 이미지 정보를 이미지 블록으로 변환
    image_blocks = convert_image_info_to_blocks(context_images)

    # 모든 블록을 하나의 리스트로 합치기
    all_blocks = text_blocks + image_blocks

    return BlockBasedResponse(blocks=all_blocks, context_docs=structured_docs)
