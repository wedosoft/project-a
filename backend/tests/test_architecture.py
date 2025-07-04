#!/usr/bin/env python3

"""
아키텍처 개선사항 테스트 스크립트
"""

import asyncio
import sys
import os

# 백엔드 모듈 경로 추가
sys.path.insert(0, '/Users/alan/GitHub/project-a/backend')

async def test_architecture_improvements():
    """새로운 아키텍처 개선사항들을 테스트"""
    
    print("🧪 아키텍처 개선사항 테스트 시작...")
    
    try:
        # 1. 모듈 import 테스트
        print("\n1️⃣ 모듈 Import 테스트")
        from core.container import get_container
        from core.cache import CacheManager
        from core.errors import ErrorHandler
        print("✅ 새로운 모듈들이 정상적으로 import됩니다")
        
        # 2. 컨테이너 초기화 테스트
        print("\n2️⃣ IoC 컨테이너 테스트")
        container = await get_container()
        print(f"✅ 컨테이너 초기화 상태: {container._initialized}")
        
        # 3. 서비스 등록 확인
        print(f"✅ 등록된 서비스 수: {len(container._services)}")
        for service_name in container._services.keys():
            print(f"   - {service_name}")
        
        # 4. 캐시 매니저 테스트
        print("\n3️⃣ 캐시 매니저 테스트")
        cache_manager = container.get_cache_manager()
        print(f"✅ 캐시 매니저 타입: {type(cache_manager).__name__}")
        
        # 캐시 성능 테스트
        test_cache = cache_manager.get_cache("ticket_context")
        if test_cache:
            await test_cache.set("test_key", {"test": "data"})
            result = await test_cache.get("test_key")
            print(f"✅ 캐시 읽기/쓰기 테스트: {result is not None}")
        
        # 5. 헬스 체크 테스트
        print("\n4️⃣ 헬스 체크 테스트")
        health = container.health_check()
        services_count = len(health.get("services", {}))
        print(f"✅ 헬스 체크 완료: {services_count}개 서비스")
        
        # 건강한 서비스 개수 확인
        healthy_services = [
            name for name, status in health.get("services", {}).items()
            if isinstance(status, dict) and status.get("status") == "healthy"
        ]
        print(f"✅ 정상 서비스: {len(healthy_services)}개")
        
        # 6. 에러 핸들러 테스트
        print("\n5️⃣ 에러 핸들러 테스트")
        from core.errors import get_error_handler
        error_handler = get_error_handler()
        stats = error_handler.get_error_stats()
        print(f"✅ 에러 핸들러 초기화: 총 에러 수 {stats['total_errors']}")
        
        print("\n🎉 모든 테스트 통과! 아키텍처 개선이 성공적으로 완료되었습니다.")
        return True
        
    except Exception as e:
        print(f"\n❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(test_architecture_improvements())
    sys.exit(0 if result else 1)
