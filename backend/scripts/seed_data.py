#!/usr/bin/env python3
"""
실제 Freshdesk 데이터로 벡터 DB 초기화 스크립트

사용법:
    python backend/scripts/seed_data.py --tickets 50 --kb 20
    python backend/scripts/seed_data.py --tickets 100 --skip-kb
"""

import asyncio
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import argparse

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "backend"))

from dotenv import load_dotenv
load_dotenv()

from backend.services.freshdesk import FreshdeskClient
from backend.services.extractor import IssueBlockExtractor
from backend.services.vector_search import VectorSearchService
from backend.services.qdrant_service import QdrantService
from backend.repositories.issue_repository import IssueRepository
from backend.repositories.kb_repository import KBRepository
from backend.models.schemas import IssueBlock, IssueBlockCreate, KBBlock, KBBlockCreate
from tqdm import tqdm


class DataSeeder:
    """실제 Freshdesk 데이터로 DB 시딩"""

    def __init__(self):
        self.freshdesk = FreshdeskClient()
        self.extractor = IssueBlockExtractor()
        self.vector_search = VectorSearchService()
        self.qdrant = QdrantService()
        self.issue_repo = IssueRepository()
        self.kb_repo = KBRepository()

    async def seed_tickets(self, count: int, tenant_id: str = "default"):
        """티켓 데이터 시딩"""
        print(f"\n🎫 Freshdesk에서 티켓 {count}개 가져오는 중...")

        # 최근 180일 이내 업데이트된 티켓 가져오기 (30일→180일로 확장)
        updated_since = datetime.now() - timedelta(days=180)
        tickets = await self.freshdesk.fetch_tickets(
            updated_since=updated_since,
            per_page=100,
            max_tickets=count  # 정확히 count개만 가져오기
        )

        if not tickets:
            print("❌ 티켓을 가져올 수 없습니다. Freshdesk API 설정을 확인하세요.")
            print("💡 최근 180일 내 업데이트된 티켓이 없습니다. 날짜 범위를 확장하거나 Freshdesk에 티켓을 추가하세요.")
            return []

        print(f"✅ {len(tickets)}개 티켓 가져옴 (요청: {count}개)")

        print("\n🤖 LLM으로 Issue Block 추출 중...")
        issue_blocks = []

        for ticket in tqdm(tickets, desc="티켓 처리"):
            try:
                # 티켓 대화 가져오기
                conversations = await self.freshdesk.fetch_ticket_conversations(
                    ticket['id']
                )

                # 티켓 딕셔너리에 대화 내역 추가
                ticket['conversations'] = conversations

                # LLM 추출 (extract_from_ticket은 ticket 전체 딕셔너리를 받음)
                extracted = await self.extractor.extract_from_ticket(ticket)

                if extracted:
                    # 티켓 메타데이터
                    ticket_meta = {
                        'subject': ticket.get('subject', ''),
                        'priority': ticket.get('priority', 1),
                        'status': ticket.get('status', 2),
                        'category': ticket.get('category', ''),
                        'tags': ticket.get('tags', [])
                    }

                    # 3개의 IssueBlock 생성 (symptom, cause, resolution 각각)
                    from backend.models.schemas import BlockType

                    # Symptom block
                    symptom_text = extracted.get('symptom', '')
                    if symptom_text and len(symptom_text) >= 10:
                        symptom_block = IssueBlock(
                            tenant_id=tenant_id,
                            ticket_id=str(ticket['id']),
                            block_type=BlockType.SYMPTOM,
                            content=symptom_text,
                            meta=ticket_meta
                        )
                        issue_blocks.append(symptom_block)

                    # Cause block
                    cause_text = extracted.get('cause', '')
                    if cause_text and len(cause_text) >= 20:
                        cause_block = IssueBlock(
                            tenant_id=tenant_id,
                            ticket_id=str(ticket['id']),
                            block_type=BlockType.CAUSE,
                            content=cause_text,
                            meta=ticket_meta
                        )
                        issue_blocks.append(cause_block)

                    # Resolution block
                    resolution_text = extracted.get('resolution', '')
                    if resolution_text and len(resolution_text) >= 30:
                        resolution_block = IssueBlock(
                            tenant_id=tenant_id,
                            ticket_id=str(ticket['id']),
                            block_type=BlockType.RESOLUTION,
                            content=resolution_text,
                            meta=ticket_meta
                        )
                        issue_blocks.append(resolution_block)

            except Exception as e:
                print(f"⚠️  티켓 {ticket.get('id')} 처리 실패: {e}")
                continue

        print(f"✅ {len(issue_blocks)}개 Issue Block 추출 완료")

        # Supabase에 저장
        print("\n💾 Supabase에 저장 중...")
        saved_count = 0
        for block in tqdm(issue_blocks, desc="DB 저장"):
            try:
                # IssueBlock → IssueBlockCreate 변환
                block_create = IssueBlockCreate(
                    tenant_id=block.tenant_id,
                    ticket_id=block.ticket_id,
                    block_type=block.block_type,
                    content=block.content,
                    product=block.product,
                    component=block.component,
                    error_code=block.error_code,
                    meta=block.meta
                )
                # create()는 synchronous이므로 await 제거
                self.issue_repo.create(tenant_id, block_create)
                saved_count += 1
            except Exception as e:
                print(f"⚠️  저장 실패: {e}")

        print(f"✅ Supabase에 {saved_count}개 저장 완료")

        # Qdrant에 임베딩 저장
        print("\n🔍 Qdrant에 임베딩 저장 중...")
        try:
            # Collection 생성 (없으면)
            self.vector_search.create_collection(
                collection_name="issue_embeddings",
                vector_names=["content_vec"]
            )

            # 임베딩 생성 및 저장
            points = []
            for idx, block in enumerate(issue_blocks):
                # 각 block의 content 임베딩 생성
                content_emb = self.vector_search.generate_embeddings([block.content])[0].tolist()

                # Qdrant Point ID는 integer만 허용
                points.append({
                    "id": idx,  # simple integer ID
                    "vectors": {
                        "content_vec": content_emb
                    },
                    "payload": {
                        "ticket_id": block.ticket_id,
                        "tenant_id": block.tenant_id,
                        "block_type": block.block_type.value,
                        "content": block.content,
                        "meta": block.meta
                    }
                })

            # Qdrant에 upsert
            self.vector_search.upsert_vectors("issue_embeddings", points)
            print(f"✅ Qdrant에 {len(issue_blocks)}개 임베딩 저장 완료")
        except Exception as e:
            print(f"❌ Qdrant 저장 실패: {e}")

        return issue_blocks

    async def seed_kb_articles(self, count: int, tenant_id: str = "default"):
        """KB 아티클 데이터 시딩"""
        print(f"\n📚 Freshdesk에서 KB 아티클 {count}개 가져오는 중...")

        # KB 아티클도 페이지네이션 지원 (폴더별로 순회하며 가져옴)
        updated_since = datetime.now() - timedelta(days=365)  # 90일→365일로 확장
        articles = await self.freshdesk.fetch_kb_articles(
            updated_since=updated_since,
            per_page=100,
            max_articles=count  # 정확히 count개만 가져오기
        )

        if not articles:
            print("❌ KB 아티클을 가져올 수 없습니다.")
            print("💡 최근 365일 내 업데이트된 KB 아티클이 없거나 폴더가 비어있습니다.")
            return []

        print(f"✅ {len(articles)}개 아티클 가져옴 (요청: {count}개)")

        print("\n🤖 LLM으로 KB Block 추출 중...")
        kb_blocks = []

        for article in tqdm(articles, desc="아티클 처리"):
            try:
                # KB는 간단한 파싱으로 처리 (LLM 없이)
                # 실제 프로덕션에서는 별도 KB extractor 구현 필요
                extracted = {
                    'intent': article.get('title', ''),
                    'step': article.get('description_text', ''),
                    'constraint': None,
                    'example': None
                }

                if extracted:
                    # KBBlock 생성 (full model with defaults)
                    kb_block = KBBlock(
                        tenant_id=tenant_id,
                        article_id=str(article['id']),
                        intent=extracted.get('intent', ''),
                        step=extracted.get('step', ''),
                        constraint=extracted.get('constraint'),
                        example=extracted.get('example'),
                        meta={
                            'title': article.get('title', ''),
                            'category': article.get('category_id', 0),
                            'tags': article.get('tags', [])
                        }
                    )
                    kb_blocks.append(kb_block)

            except Exception as e:
                print(f"⚠️  아티클 {article.get('id')} 처리 실패: {e}")
                continue

        print(f"✅ {len(kb_blocks)}개 KB Block 추출 완료")

        # Supabase에 저장
        print("\n💾 Supabase에 저장 중...")
        saved_count = 0
        for block in tqdm(kb_blocks, desc="DB 저장"):
            try:
                # KBBlock → KBBlockCreate 변환
                block_create = KBBlockCreate(
                    tenant_id=block.tenant_id,
                    article_id=block.article_id,
                    intent=block.intent,
                    step=block.step,
                    constraint=block.constraint,
                    example=block.example,
                    meta=block.meta
                )
                # create()는 synchronous이므로 await 제거
                self.kb_repo.create(tenant_id, block_create)
                saved_count += 1
            except Exception as e:
                print(f"⚠️  저장 실패: {e}")

        print(f"✅ Supabase에 {saved_count}개 저장 완료")

        # Qdrant에 임베딩 저장
        print("\n🔍 Qdrant에 임베딩 저장 중...")
        try:
            # Collection 생성 (없으면)
            self.vector_search.create_collection(
                collection_name="kb_embeddings",
                vector_names=["intent_vec", "procedure_vec"]
            )

            # 임베딩 생성 및 저장
            points = []
            for idx, block in enumerate(kb_blocks):
                # 각 필드 임베딩 생성
                intent_emb = self.vector_search.generate_embeddings([block.intent or ""])[0].tolist()
                step_emb = self.vector_search.generate_embeddings([block.step or ""])[0].tolist()

                points.append({
                    "id": idx,
                    "vectors": {
                        "intent_vec": intent_emb,
                        "procedure_vec": step_emb  # 벡터 이름은 procedure_vec 유지 (Qdrant collection 설정과 일치)
                    },
                    "payload": {
                        "article_id": block.article_id,
                        "tenant_id": block.tenant_id,
                        "intent": block.intent,
                        "step": block.step
                    }
                })

            # Qdrant에 upsert
            self.vector_search.upsert_vectors("kb_embeddings", points)
            print(f"✅ Qdrant에 {len(kb_blocks)}개 임베딩 저장 완료")
        except Exception as e:
            print(f"❌ Qdrant 저장 실패: {e}")

        return kb_blocks

    async def verify_data(self):
        """저장된 데이터 검증"""
        print("\n🔍 데이터 검증 중...")

        # Supabase 카운트
        try:
            issue_count = await self.issue_repo.count_async(tenant_id="default")
            kb_count = await self.kb_repo.count_async(tenant_id="default")
            print(f"✅ Supabase: Issue {issue_count}개, KB {kb_count}개")
        except Exception as e:
            print(f"❌ Supabase 검증 실패: {e}")

        # Qdrant 카운트
        try:
            issue_info = self.vector_search.get_collection_info("issue_embeddings")
            print(f"✅ Qdrant issue_embeddings: {issue_info.get('points_count', 0)}개")

            kb_info = self.vector_search.get_collection_info("kb_embeddings")
            print(f"✅ Qdrant kb_embeddings: {kb_info.get('points_count', 0)}개")
        except Exception as e:
            print(f"❌ Qdrant 검증 실패: {e}")

        # 샘플 검색 테스트
        print("\n🧪 샘플 검색 테스트...")
        try:
            results = await self.vector_search.search(
                collection_name="issue_embeddings",
                query="로그인 문제",
                top_k=5,
                filters={"tenant_id": "default"},
                vector_name="content_vec"
            )
            print(f"✅ 검색 결과: {len(results)}개 반환")
            if results:
                first_result = results[0].get('payload', {})
                print(f"   첫 번째 결과: {first_result.get('content', '')[:50]}...")
        except Exception as e:
            print(f"❌ 검색 테스트 실패: {e}")


async def main():
    parser = argparse.ArgumentParser(description="Freshdesk 실데이터로 DB 시딩")
    parser.add_argument("--tickets", type=int, default=50, help="가져올 티켓 수 (기본: 50)")
    parser.add_argument("--kb", type=int, default=20, help="가져올 KB 아티클 수 (기본: 20)")
    parser.add_argument("--skip-kb", action="store_true", help="KB 아티클 건너뛰기")
    parser.add_argument("--tenant-id", type=str, default="default", help="테넌트 ID")

    args = parser.parse_args()

    print("=" * 60)
    print("🌱 Freshdesk 실데이터 시딩 시작")
    print("=" * 60)
    print(f"티켓: {args.tickets}개")
    print(f"KB 아티클: {args.kb if not args.skip_kb else '건너뛰기'}")
    print(f"테넌트 ID: {args.tenant_id}")
    print("=" * 60)

    seeder = DataSeeder()

    try:
        # 티켓 시딩
        if args.tickets > 0:
            await seeder.seed_tickets(args.tickets, args.tenant_id)

        # KB 시딩
        if not args.skip_kb and args.kb > 0:
            await seeder.seed_kb_articles(args.kb, args.tenant_id)

        # 검증
        await seeder.verify_data()

        print("\n" + "=" * 60)
        print("✅ 시딩 완료!")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
