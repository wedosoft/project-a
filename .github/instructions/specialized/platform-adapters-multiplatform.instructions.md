---
applyTo: "**"
---

# 🔄 플랫폼 어댑터 & 멀티플랫폼 지원 지침서

_AI 참조 최적화 버전 - 확장 가능한 멀티플랫폼 어댑터 패턴_

## 🎯 플랫폼 어댑터 목표

**플랫폼 추상화를 통한 확장 가능한 데이터 수집 시스템 구축**

- **현재 지원**: Freshdesk (완전 구현)
- **공통 인터페이스**: 모든 플랫폼에 동일한 API 제공
- **멀티테넌트**: company_id 기반 완전한 데이터 격리

---

## ⚡ **TL;DR - 핵심 어댑터 패턴 요약**

### 💡 **즉시 참조용 핵심 포인트**

**어댑터 패턴 구조**:

```
BasePlatformAdapter (인터페이스)
├── FreshdeskAdapter (완전 구현)
└── ServiceNowAdapter (향후 확장)
```

**핵심 메서드**:

- `fetch_tickets()`: 티켓 데이터 청크 단위 수집
- `fetch_knowledge_base()`: 지식베이스 수집
- `normalize_ticket_data()`: 플랫폼별 데이터 정규화
- `validate_credentials()`: API 자격증명 검증

**확장 전략**:

2. **순차적 개발**: 동시 개발 금지, 하나씩 완성
3. **공통 스키마**: 모든 플랫폼 데이터를 동일한 형식으로 정규화

### 🚨 **어댑터 패턴 주의사항**

- ⚠️ 플랫폼별 하드코딩 금지 → 인터페이스 기반 추상화 필수
- ⚠️ 순차 확장 원칙 → Freshdesk 완성 전 다른 플랫폼 작업 금지
- ⚠️ 데이터 정규화 필수 → 모든 플랫폼 데이터를 공통 스키마로 변환

---

## 🏗️ **플랫폼 어댑터 기본 인터페이스**

### 📋 **BasePlatformAdapter 인터페이스**

```python
from abc import ABC, abstractmethod
from typing import List, Dict, Any, AsyncGenerator

class BasePlatformAdapter(ABC):
    """플랫폼 어댑터 기본 인터페이스"""

    def __init__(self, company_id: str, api_credentials: Dict[str, str]):
        self.company_id = company_id
        self.api_credentials = api_credentials

    @abstractmethod
    async def fetch_tickets(
        self,
        start_date: str,
        end_date: str,
        chunk_size: int = 100
    ) -> AsyncGenerator[List[Dict], None]:
        """티켓 데이터 청크 단위 수집"""
        pass

    @abstractmethod
    async def fetch_knowledge_base(self) -> List[Dict]:
        """지식베이스 수집"""
        pass

    @abstractmethod
    def get_platform_name(self) -> str:
        """플랫폼 이름 반환"""
        pass

    @abstractmethod
    async def validate_credentials(self) -> bool:
        """API 자격증명 검증"""
        pass

    @abstractmethod
    def normalize_ticket_data(self, raw_ticket: Dict) -> Dict:
        """플랫폼별 데이터를 공통 형식으로 정규화"""
        pass

    # 공통 유틸리티 메서드
    def extract_company_id_from_domain(self, domain: str) -> str:
        """도메인에서 company_id 추출 (플랫폼별 구현)"""
        return self.company_id

    async def rate_limit_delay(self, delay: float = 0.2):
        """Rate limiting을 위한 딜레이"""
        await asyncio.sleep(delay)
```

---

## 🎯 **Freshdesk 어댑터 완전 구현**

### ✅ **FreshdeskAdapter 전체 구현**

```python
import aiohttp
import asyncio
from typing import AsyncGenerator
from datetime import datetime

class FreshdeskAdapter(BasePlatformAdapter):
    """Freshdesk 완전 구현"""

    def get_platform_name(self) -> str:
        return "freshdesk"

    def extract_company_id_from_domain(self, domain: str) -> str:
        """Freshdesk 도메인에서 company_id 추출"""
        if not domain.endswith('.freshdesk.com'):
            raise ValueError(f"올바르지 않은 Freshdesk 도메인: {domain}")
        
        return domain.split('.')[0]

    async def validate_credentials(self) -> bool:
        """Freshdesk API 자격증명 검증"""
        domain = self.api_credentials.get("domain")
        api_key = self.api_credentials.get("api_key")

        if not domain or not api_key:
            return False

        async with aiohttp.ClientSession() as session:
            auth = aiohttp.BasicAuth(api_key, "X")
            url = f"https://{domain}/api/v2/tickets"

            try:
                async with session.get(url, auth=auth, params={"per_page": 1}) as response:
                    return response.status == 200
            except Exception as e:
                logger.error(f"Freshdesk credential validation failed: {e}")
                return False

    async def fetch_tickets(
        self,
        start_date: str,
        end_date: str,
        chunk_size: int = 100
    ) -> AsyncGenerator[List[Dict], None]:
        """Freshdesk 티켓 청크 단위 수집"""
        domain = self.api_credentials.get("domain")
        api_key = self.api_credentials.get("api_key")

        async with aiohttp.ClientSession() as session:
            auth = aiohttp.BasicAuth(api_key, "X")
            page = 1

            while True:
                url = f"https://{domain}/api/v2/tickets"
                params = {
                    "updated_since": start_date,
                    "per_page": chunk_size,
                    "page": page
                }

                try:
                    async with session.get(url, auth=auth, params=params) as response:
                        if response.status != 200:
                            logger.error(f"Freshdesk API error: {response.status}")
                            break

                        tickets = await response.json()
                        if not tickets:
                            break

                        # 각 티켓에 대해 상세 정보 및 대화 수집
                        enriched_tickets = []
                        for ticket in tickets:
                            # 티켓 대화 수집
                            conversations = await self._fetch_ticket_conversations(
                                session, auth, domain, ticket["id"]
                            )
                            
                            # 데이터 정규화 및 company_id 태깅
                            normalized = self.normalize_ticket_data(ticket)
                            normalized.update({
                                "company_id": self.company_id,
                                "platform": self.get_platform_name(),
                                "conversations": conversations,
                                "collected_at": datetime.utcnow().isoformat()
                            })
                            enriched_tickets.append(normalized)

                        yield enriched_tickets
                        page += 1

                        # Rate limiting
                        await self.rate_limit_delay()

                except Exception as e:
                    logger.error(f"Error fetching Freshdesk tickets: {e}")
                    break

    async def _fetch_ticket_conversations(
        self, 
        session: aiohttp.ClientSession, 
        auth: aiohttp.BasicAuth,
        domain: str, 
        ticket_id: int
    ) -> List[Dict]:
        """특정 티켓의 모든 대화 수집"""
        url = f"https://{domain}/api/v2/tickets/{ticket_id}/conversations"
        
        try:
            async with session.get(url, auth=auth) as response:
                if response.status == 200:
                    conversations = await response.json()
                    return conversations
                else:
                    logger.warning(f"Failed to fetch conversations for ticket {ticket_id}")
                    return []
        except Exception as e:
            logger.error(f"Error fetching conversations for ticket {ticket_id}: {e}")
            return []

    def normalize_ticket_data(self, raw_ticket: Dict) -> Dict:
        """Freshdesk 데이터를 공통 형식으로 정규화"""
        return {
            "ticket_id": str(raw_ticket.get("id")),
            "subject": raw_ticket.get("subject", ""),
            "description": raw_ticket.get("description_text", ""),
            "status": self._normalize_status(raw_ticket.get("status", 2)),
            "priority": self._normalize_priority(raw_ticket.get("priority", 1)),
            "requester_email": raw_ticket.get("requester", {}).get("email", ""),
            "agent_email": raw_ticket.get("responder", {}).get("email", ""),
            "tags": raw_ticket.get("tags", []),
            "created_at": raw_ticket.get("created_at"),
            "updated_at": raw_ticket.get("updated_at"),
            "resolved_at": raw_ticket.get("stats", {}).get("resolved_at"),
            "first_responded_at": raw_ticket.get("stats", {}).get("first_responded_at"),
            "original_data": raw_ticket  # 원본 데이터 보존
        }

    def _normalize_status(self, status_code: int) -> str:
        """Freshdesk 상태 코드를 공통 형식으로 변환"""
        status_map = {
            2: "open",
            3: "pending", 
            4: "resolved",
            5: "closed"
        }
        return status_map.get(status_code, "unknown")

    def _normalize_priority(self, priority_code: int) -> str:
        """Freshdesk 우선순위 코드를 공통 형식으로 변환"""
        priority_map = {
            1: "low",
            2: "medium",
            3: "high",
            4: "urgent"
        }
        return priority_map.get(priority_code, "medium")

    async def fetch_knowledge_base(self) -> List[Dict]:
        """Freshdesk 지식베이스 문서 수집"""
        domain = self.api_credentials.get("domain")
        api_key = self.api_credentials.get("api_key")

        async with aiohttp.ClientSession() as session:
            auth = aiohttp.BasicAuth(api_key, "X")
            
            # 폴더 목록 먼저 수집
            folders = await self._fetch_kb_folders(session, auth, domain)
            
            # 각 폴더의 문서들 수집
            all_articles = []
            for folder in folders:
                articles = await self._fetch_kb_articles(session, auth, domain, folder["id"])
                all_articles.extend(articles)

            return all_articles

    async def _fetch_kb_folders(self, session, auth, domain) -> List[Dict]:
        """지식베이스 폴더 목록 수집"""
        url = f"https://{domain}/api/v2/solutions/folders"
        
        try:
            async with session.get(url, auth=auth) as response:
                if response.status == 200:
                    return await response.json()
                return []
        except Exception as e:
            logger.error(f"Error fetching KB folders: {e}")
            return []

    async def _fetch_kb_articles(self, session, auth, domain, folder_id) -> List[Dict]:
        """특정 폴더의 지식베이스 문서들 수집"""
        url = f"https://{domain}/api/v2/solutions/folders/{folder_id}/articles"
        
        try:
            async with session.get(url, auth=auth) as response:
                if response.status == 200:
                    articles = await response.json()
                    # 각 문서에 company_id와 platform 정보 추가
                    for article in articles:
                        article.update({
                            "company_id": self.company_id,
                            "platform": self.get_platform_name(),
                            "folder_id": folder_id
                        })
                    return articles
                return []
        except Exception as e:
            logger.error(f"Error fetching KB articles from folder {folder_id}: {e}")
            return []
```

---



```python

    def get_platform_name(self) -> str:

    def extract_company_id_from_domain(self, domain: str) -> str:
            return domain.split('.')[0]

    async def validate_credentials(self) -> bool:
        subdomain = self.api_credentials.get("subdomain")
        email = self.api_credentials.get("email")
        api_token = self.api_credentials.get("api_token")

        if not all([subdomain, email, api_token]):
            return False

        async with aiohttp.ClientSession() as session:
            auth = aiohttp.BasicAuth(f"{email}/token", api_token)

            try:
                async with session.get(url, auth=auth, params={"per_page": 1}) as response:
                    return response.status == 200
            except Exception:
                return False

    async def fetch_tickets(
        self,
        start_date: str,
        end_date: str,
        chunk_size: int = 100
    ) -> AsyncGenerator[List[Dict], None]:

    def normalize_ticket_data(self, raw_ticket: Dict) -> Dict:

    async def fetch_knowledge_base(self) -> List[Dict]:
```

---

## 🏭 **플랫폼 어댑터 팩토리**

### 🔧 **PlatformAdapterFactory 패턴**

```python
class PlatformAdapterFactory:
    """플랫폼별 어댑터 생성 팩토리"""

    _adapters = {
        "freshdesk": FreshdeskAdapter,
        # "servicenow": ServiceNowAdapter,  # 향후 확장
    }

    @classmethod
    def create_adapter(
        cls,
        platform: str,
        company_id: str,
        api_credentials: Dict[str, str]
    ) -> BasePlatformAdapter:
        """플랫폼별 어댑터 생성"""
        if platform not in cls._adapters:
            raise ValueError(f"Unsupported platform: {platform}. Supported: {list(cls._adapters.keys())}")

        adapter_class = cls._adapters[platform]
        return adapter_class(company_id, api_credentials)

    @classmethod
    def get_supported_platforms(cls) -> List[str]:
        """지원되는 플랫폼 목록 반환"""
        return list(cls._adapters.keys())

    @classmethod
    def register_adapter(cls, platform: str, adapter_class):
        """새로운 플랫폼 어댑터 등록"""
        if not issubclass(adapter_class, BasePlatformAdapter):
            raise TypeError("Adapter must inherit from BasePlatformAdapter")
        
        cls._adapters[platform] = adapter_class

    @classmethod
    def is_platform_supported(cls, platform: str) -> bool:
        """플랫폼 지원 여부 확인"""
        return platform in cls._adapters
```

---

## 🚀 **멀티플랫폼 데이터 수집 워크플로우**

### 🔄 **통합 수집 패턴**

```python
async def collect_multi_platform_data(
    company_id: str, 
    platforms_config: Dict[str, Dict]
) -> Dict[str, Any]:
    """멀티플랫폼 데이터 수집 워크플로우"""
    
    results = {
        "success": [],
        "failed": [],
        "not_implemented": [],
        "summary": {}
    }

    for platform, config in platforms_config.items():
        try:
            # 1. 플랫폼 지원 여부 확인
            if not PlatformAdapterFactory.is_platform_supported(platform):
                results["failed"].append({
                    "platform": platform,
                    "error": f"Unsupported platform: {platform}"
                })
                continue

            # 2. 플랫폼별 어댑터 생성
            adapter = PlatformAdapterFactory.create_adapter(
                platform,
                company_id,
                config["credentials"]
            )

            # 3. 자격증명 검증
            if not await adapter.validate_credentials():
                results["failed"].append({
                    "platform": platform,
                    "error": "Invalid credentials"
                })
                continue

            # 4. 데이터 수집 실행
            platform_results = await collect_platform_data(
                adapter, 
                config.get("start_date"), 
                config.get("end_date")
            )

            results["success"].append({
                "platform": platform,
                "collected_tickets": platform_results["tickets_count"],
                "collected_kb": platform_results["kb_count"],
                "duration": platform_results["duration"]
            })

        except NotImplementedError:
            results["not_implemented"].append({
                "platform": platform,
                "message": "Platform adapter not yet implemented"
            })
            logger.warning(f"Platform {platform} not yet implemented")

        except Exception as e:
            results["failed"].append({
                "platform": platform,
                "error": str(e)
            })
            logger.error(f"Error collecting from {platform}: {e}")

    # 5. 결과 요약
    results["summary"] = {
        "total_platforms": len(platforms_config),
        "successful": len(results["success"]),
        "failed": len(results["failed"]),
        "not_implemented": len(results["not_implemented"])
    }

    return results

async def collect_platform_data(
    adapter: BasePlatformAdapter,
    start_date: str,
    end_date: str
) -> Dict[str, Any]:
    """단일 플랫폼 데이터 수집"""
    start_time = datetime.utcnow()
    tickets_count = 0
    kb_count = 0

    try:
        # 티켓 데이터 수집
        async for tickets_chunk in adapter.fetch_tickets(start_date, end_date):
            tickets_count += len(tickets_chunk)
            # 여기서 데이터 저장 처리
            await process_tickets_chunk(
                adapter.company_id, 
                adapter.get_platform_name(), 
                tickets_chunk
            )

        # 지식베이스 수집
        try:
            kb_articles = await adapter.fetch_knowledge_base()
            kb_count = len(kb_articles)
            # KB 데이터 저장 처리
            await process_kb_articles(
                adapter.company_id,
                adapter.get_platform_name(),
                kb_articles
            )
        except NotImplementedError:
            logger.info(f"KB collection not implemented for {adapter.get_platform_name()}")

    except Exception as e:
        logger.error(f"Error in platform data collection: {e}")
        raise

    duration = (datetime.utcnow() - start_time).total_seconds()

    return {
        "tickets_count": tickets_count,
        "kb_count": kb_count,
        "duration": duration
    }
```

---

## ⚠️ **플랫폼 어댑터 주의사항**

### 🚨 **구현 시 필수 준수사항**

1. **순차 확장 원칙**
   - 동시 개발 금지, 하나씩 완성하고 다음 진행

2. **공통 인터페이스 준수**
   - 모든 어댑터는 `BasePlatformAdapter` 상속 필수
   - 메서드 시그니처 변경 금지

3. **데이터 정규화 필수**
   - 플랫폼별 데이터를 공통 스키마로 변환
   - 원본 데이터는 `original_data` 필드에 보존

4. **에러 처리 표준화**
   - 구현되지 않은 기능은 `NotImplementedError` 발생
   - 모든 예외는 로깅 후 적절히 처리

5. **company_id 자동 태깅**  
   - 모든 수집 데이터에 테넌트 식별자 필수 포함
   - 플랫폼 정보도 자동으로 태깅

---

## 📚 **관련 지침서**

- **[데이터 수집 패턴](data-collection-patterns.instructions.md)**: 플랫폼별 데이터 수집 세부 구현
- **[멀티테넌트 보안](multitenant-security.instructions.md)**: company_id 기반 데이터 격리
- **[시스템 아키텍처](system-architecture.instructions.md)**: 전체 시스템 설계 패턴
- **[Quick Reference](quick-reference.instructions.md)**: 핵심 패턴 요약

**이 플랫폼 어댑터 지침서는 확장 가능한 멀티플랫폼 지원을 위한 모든 패턴과 구현 가이드를 제공합니다.**
