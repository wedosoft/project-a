#!/usr/bin/env python3
"""
FastAPI 백엔드 통합 테스트 스크립트

사용법:
    # 기본 테스트 (헬스체크 + 제안 생성)
    python backend/scripts/test_api.py

    # 특정 티켓으로 테스트
    python backend/scripts/test_api.py --ticket-id 12345

    # 전체 파이프라인 테스트
    python backend/scripts/test_api.py --full-pipeline
"""

import asyncio
import sys
import os
from pathlib import Path
import argparse
import json
from typing import Dict, Any, Optional
import httpx
from datetime import datetime

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

# API 설정
API_BASE_URL = os.getenv("FASTAPI_HOST", "http://localhost:8000")
TENANT_ID = "default"


class APITester:
    """FastAPI 백엔드 통합 테스트"""

    def __init__(self, base_url: str = API_BASE_URL):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=60.0)

    async def close(self):
        await self.client.aclose()

    def print_section(self, title: str):
        """섹션 헤더 출력"""
        print(f"\n{'=' * 60}")
        print(f"📋 {title}")
        print('=' * 60)

    def print_result(self, success: bool, message: str, data: Any = None):
        """결과 출력"""
        icon = "✅" if success else "❌"
        print(f"{icon} {message}")
        if data and isinstance(data, dict):
            print(json.dumps(data, indent=2, ensure_ascii=False))

    async def test_health(self) -> bool:
        """헬스체크 테스트"""
        self.print_section("헬스체크")

        try:
            response = await self.client.get(f"{self.base_url}/api/health")
            success = response.status_code == 200
            data = response.json() if success else None

            self.print_result(
                success,
                f"API 상태: {response.status_code}",
                data
            )

            if success:
                # 의존성 체크
                deps_response = await self.client.get(
                    f"{self.base_url}/api/health/dependencies"
                )
                deps_data = deps_response.json() if deps_response.status_code == 200 else None

                if deps_data:
                    print("\n의존성 상태:")
                    for service, status in deps_data.items():
                        icon = "✅" if status.get("status") == "healthy" else "❌"
                        print(f"  {icon} {service}: {status.get('status', 'unknown')}")

            return success

        except Exception as e:
            self.print_result(False, f"헬스체크 실패: {e}")
            return False

    async def test_suggest(self, ticket_id: Optional[str] = None) -> bool:
        """AI 제안 생성 테스트"""
        self.print_section("AI 제안 생성 테스트")

        # 테스트 티켓 데이터
        if not ticket_id:
            # 실제 티켓 ID가 없으면 샘플 컨텍스트 사용
            ticket_context = {
                "ticket_id": "test-001",
                "subject": "로그인이 안 돼요",
                "description": "회원가입은 했는데 로그인을 하려고 하면 '비밀번호가 틀렸습니다'라고 나옵니다. 비밀번호를 3번 확인했는데도 같은 오류가 나요.",
                "customer_email": "test@example.com",
                "priority": 2,
                "status": 2,
                "category": "로그인/인증",
                "tags": ["로그인", "비밀번호"],
                "requester_name": "테스트 고객"
            }
        else:
            ticket_context = {
                "ticket_id": ticket_id,
                "subject": "실제 티켓 테스트",
                "description": "실제 Freshdesk 티켓으로 테스트",
                "customer_email": "real@example.com"
            }

        try:
            response = await self.client.post(
                f"{self.base_url}/api/assist/{ticket_context['ticket_id']}/suggest",
                json=ticket_context,
                headers={"X-Tenant-ID": TENANT_ID}
            )

            success = response.status_code == 200
            data = response.json() if success else None

            if success:
                print(f"✅ 제안 생성 성공 (응답 시간: {response.elapsed.total_seconds():.2f}초)")
                print("\n📊 응답 데이터:")

                if data:
                    # 유사사례
                    similar_cases = data.get('similar_cases', [])
                    print(f"\n🔍 유사사례: {len(similar_cases)}개")
                    for i, case in enumerate(similar_cases[:3], 1):
                        print(f"  {i}. [티켓#{case.get('ticket_id')}] {case.get('symptom', '')[:50]}...")
                        print(f"     점수: {case.get('score', 0):.3f}")

                    # KB 제안
                    kb_suggestions = data.get('kb_suggestions', [])
                    print(f"\n📚 KB 제안: {len(kb_suggestions)}개")
                    for i, kb in enumerate(kb_suggestions[:2], 1):
                        print(f"  {i}. {kb.get('intent', '')[:50]}...")

                    # 필드 제안
                    field_updates = data.get('proposed_field_updates', {})
                    if field_updates:
                        print(f"\n🏷️  필드 업데이트 제안:")
                        for field, value in field_updates.items():
                            print(f"  • {field}: {value}")

                    # 응답 초안
                    draft = data.get('draft_response', '')
                    if draft:
                        print(f"\n💬 응답 초안:")
                        print(f"  {draft[:150]}...")
            else:
                self.print_result(False, f"제안 생성 실패: {response.status_code}", data)

            return success

        except Exception as e:
            self.print_result(False, f"제안 생성 오류: {e}")
            return False

    async def test_approve(self, ticket_id: str = "test-001") -> bool:
        """승인 프로세스 테스트"""
        self.print_section("승인 프로세스 테스트")

        approval_request = {
            "action": "approved",
            "modified_response": None,
            "modified_fields": None,
            "feedback": "AI 제안이 정확했습니다.",
            "agent_id": "test-agent"
        }

        try:
            response = await self.client.post(
                f"{self.base_url}/api/assist/{ticket_id}/approve",
                json=approval_request,
                headers={"X-Tenant-ID": TENANT_ID}
            )

            success = response.status_code == 200
            data = response.json() if success else None

            self.print_result(
                success,
                f"승인 처리: {response.status_code}",
                data
            )

            return success

        except Exception as e:
            self.print_result(False, f"승인 처리 오류: {e}")
            return False

    async def test_sync(self) -> bool:
        """동기화 테스트"""
        self.print_section("Freshdesk 동기화 테스트")

        sync_request = {
            "limit": 10,
            "updated_since": (datetime.now().isoformat())
        }

        try:
            response = await self.client.post(
                f"{self.base_url}/api/sync/tickets",
                json=sync_request,
                headers={"X-Tenant-ID": TENANT_ID}
            )

            success = response.status_code == 200
            data = response.json() if success else None

            if success:
                synced = data.get('synced_count', 0)
                print(f"✅ 동기화 완료: {synced}개 티켓")
            else:
                self.print_result(False, f"동기화 실패: {response.status_code}", data)

            return success

        except Exception as e:
            self.print_result(False, f"동기화 오류: {e}")
            return False

    async def test_full_pipeline(self, ticket_id: Optional[str] = None) -> bool:
        """전체 파이프라인 통합 테스트"""
        self.print_section("전체 파이프라인 테스트")

        results = {
            "health": False,
            "sync": False,
            "suggest": False,
            "approve": False
        }

        # 1. 헬스체크
        results["health"] = await self.test_health()
        if not results["health"]:
            print("\n❌ 헬스체크 실패, 테스트 중단")
            return False

        await asyncio.sleep(1)

        # 2. 동기화 (선택)
        # results["sync"] = await self.test_sync()
        # await asyncio.sleep(2)

        # 3. 제안 생성
        results["suggest"] = await self.test_suggest(ticket_id)
        await asyncio.sleep(1)

        # 4. 승인 처리
        if results["suggest"]:
            test_ticket = ticket_id or "test-001"
            results["approve"] = await self.test_approve(test_ticket)

        # 결과 요약
        self.print_section("테스트 결과 요약")
        total = len(results)
        passed = sum(1 for v in results.values() if v)

        for test_name, passed in results.items():
            icon = "✅" if passed else "❌"
            print(f"{icon} {test_name}: {'통과' if passed else '실패'}")

        print(f"\n📊 총 {passed}/{total} 테스트 통과 ({passed/total*100:.0f}%)")

        return all(results.values())


async def main():
    parser = argparse.ArgumentParser(description="FastAPI 백엔드 통합 테스트")
    parser.add_argument("--ticket-id", type=str, help="테스트할 티켓 ID")
    parser.add_argument("--full-pipeline", action="store_true", help="전체 파이프라인 테스트")
    parser.add_argument("--base-url", type=str, default=API_BASE_URL, help="API 기본 URL")

    args = parser.parse_args()

    print("=" * 60)
    print("🧪 FastAPI 백엔드 통합 테스트")
    print("=" * 60)
    print(f"API URL: {args.base_url}")
    if args.ticket_id:
        print(f"티켓 ID: {args.ticket_id}")
    print("=" * 60)

    tester = APITester(args.base_url)

    try:
        if args.full_pipeline:
            success = await tester.test_full_pipeline(args.ticket_id)
        else:
            # 기본: 헬스체크 + 제안 생성
            health_ok = await tester.test_health()
            if health_ok:
                await asyncio.sleep(1)
                success = await tester.test_suggest(args.ticket_id)
            else:
                success = False

        sys.exit(0 if success else 1)

    except KeyboardInterrupt:
        print("\n\n⚠️  테스트 중단됨")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        await tester.close()


if __name__ == "__main__":
    asyncio.run(main())
