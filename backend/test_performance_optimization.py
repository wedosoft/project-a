#!/usr/bin/env python3
"""
성능 최적화 검증 테스트 스크립트

/init/{ticket_id} 엔드포인트의 성능을 테스트하고 최적화 전후를 비교합니다.
목표: 24초 → 8초 이하로 개선
"""

import asyncio
import aiohttp
import time
import logging
from typing import Dict, List, Any

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class PerformanceTest:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.headers = {
            "X-Tenant-ID": "default",
            "X-Platform": "freshdesk", 
            "X-API-Key": "test-key",
            "X-Domain": "wedosoft.freshdesk.com"
        }
    
    async def test_init_endpoint(self, ticket_id: str, test_name: str = "") -> Dict[str, Any]:
        """
        /init/{ticket_id} 엔드포인트 성능 테스트
        
        Args:
            ticket_id: 테스트할 티켓 ID
            test_name: 테스트 이름
            
        Returns:
            Dict[str, Any]: 성능 메트릭
        """
        url = f"{self.base_url}/init/{ticket_id}"
        params = {
            "stream": "false",  # JSON 응답으로 테스트
            "include_summary": "true",
            "include_similar_tickets": "true", 
            "include_kb_docs": "true",
            "top_k_tickets": 3,
            "top_k_kb": 3
        }
        
        logger.info(f"🚀 [{test_name}] 테스트 시작 - 티켓 ID: {ticket_id}")
        start_time = time.time()
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, 
                    headers=self.headers,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=60)  # 60초 타임아웃
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        total_time = time.time() - start_time
                        
                        # 응답 분석
                        success = result.get("success", False)
                        execution_time = result.get("execution_time", 0)
                        similar_tickets_count = len(result.get("similar_tickets", []))
                        kb_docs_count = len(result.get("kb_documents", []))
                        has_summary = bool(result.get("summary"))
                        
                        metrics = {
                            "test_name": test_name,
                            "ticket_id": ticket_id,
                            "success": success,
                            "total_time": total_time,
                            "execution_time": execution_time,
                            "similar_tickets_count": similar_tickets_count,
                            "kb_docs_count": kb_docs_count,
                            "has_summary": has_summary,
                            "status_code": response.status
                        }
                        
                        logger.info(f"✅ [{test_name}] 완료 - 소요시간: {total_time:.2f}초 (서버: {execution_time:.2f}초)")
                        logger.info(f"   📊 결과: 유사티켓 {similar_tickets_count}개, KB문서 {kb_docs_count}개, 요약: {'✓' if has_summary else '✗'}")
                        
                        return metrics
                    else:
                        logger.error(f"❌ [{test_name}] HTTP 오류: {response.status}")
                        return {
                            "test_name": test_name,
                            "ticket_id": ticket_id,
                            "success": False,
                            "total_time": time.time() - start_time,
                            "status_code": response.status,
                            "error": f"HTTP {response.status}"
                        }
                        
        except Exception as e:
            total_time = time.time() - start_time
            logger.error(f"❌ [{test_name}] 요청 실패: {e}")
            return {
                "test_name": test_name,
                "ticket_id": ticket_id,
                "success": False,
                "total_time": total_time,
                "error": str(e)
            }
    
    async def run_performance_test(self, ticket_ids: List[str], iterations: int = 3) -> List[Dict[str, Any]]:
        """
        성능 테스트 실행
        
        Args:
            ticket_ids: 테스트할 티켓 ID 목록
            iterations: 각 티켓당 반복 횟수
            
        Returns:
            List[Dict[str, Any]]: 모든 테스트 결과
        """
        all_results = []
        
        for ticket_id in ticket_ids:
            logger.info(f"\n🎯 티켓 {ticket_id} 성능 테스트 시작 ({iterations}회 반복)")
            ticket_results = []
            
            for i in range(iterations):
                test_name = f"티켓{ticket_id}_테스트{i+1}"
                result = await self.test_init_endpoint(ticket_id, test_name)
                ticket_results.append(result)
                all_results.append(result)
                
                # 다음 테스트 전 잠시 대기 (서버 부하 분산)
                if i < iterations - 1:
                    await asyncio.sleep(2)
            
            # 티켓별 통계 출력
            successful_results = [r for r in ticket_results if r.get("success", False)]
            if successful_results:
                times = [r["total_time"] for r in successful_results]
                avg_time = sum(times) / len(times)
                min_time = min(times)
                max_time = max(times)
                
                logger.info(f"\n📈 티켓 {ticket_id} 통계:")
                logger.info(f"   평균 시간: {avg_time:.2f}초")
                logger.info(f"   최소 시간: {min_time:.2f}초")
                logger.info(f"   최대 시간: {max_time:.2f}초")
                logger.info(f"   성공률: {len(successful_results)}/{iterations} ({len(successful_results)/iterations*100:.1f}%)")
                
                # 성능 목표 달성 여부
                if avg_time <= 8.0:
                    logger.info(f"   🎉 성능 목표 달성! (평균 {avg_time:.2f}초 ≤ 8초)")
                else:
                    logger.warning(f"   ⚠️ 성능 목표 미달성 (평균 {avg_time:.2f}초 > 8초)")
            else:
                logger.error(f"   ❌ 티켓 {ticket_id} 모든 테스트 실패")
        
        return all_results
    
    def generate_report(self, results: List[Dict[str, Any]]) -> str:
        """
        성능 테스트 리포트 생성
        
        Args:
            results: 테스트 결과 목록
            
        Returns:
            str: 리포트 내용
        """
        successful_results = [r for r in results if r.get("success", False)]
        total_tests = len(results)
        success_rate = len(successful_results) / total_tests * 100 if total_tests > 0 else 0
        
        if not successful_results:
            return "❌ 성공한 테스트가 없습니다."
        
        times = [r["total_time"] for r in successful_results]
        avg_time = sum(times) / len(times)
        min_time = min(times)
        max_time = max(times)
        
        # 성능 개선 상태
        performance_status = "🎉 목표 달성" if avg_time <= 8.0 else "⚠️ 추가 최적화 필요"
        
        report = f"""
📊 성능 최적화 테스트 리포트
{'='*50}

🎯 목표: 24초 → 8초 이하 (66% 성능 향상)

📈 테스트 결과:
• 총 테스트: {total_tests}회
• 성공률: {success_rate:.1f}% ({len(successful_results)}/{total_tests})
• 평균 응답시간: {avg_time:.2f}초
• 최소 응답시간: {min_time:.2f}초  
• 최대 응답시간: {max_time:.2f}초

⚡ 성능 상태: {performance_status}

📋 최적화 내용:
✅ 벡터 검색 최적화 (단일 쿼리로 통합)
✅ 결과 포맷팅 최적화 (불필요한 루프 제거)
✅ 로깅 최적화 (상세 로그를 DEBUG 레벨로 이동)
✅ 병렬 처리 동시 실행 수 증가 (3 → 5)
✅ LLM 매니저 성능 최적화

💡 권장사항:
"""
        
        if avg_time > 8.0:
            report += f"""• 현재 평균 {avg_time:.2f}초로 목표 8초를 {avg_time-8:.2f}초 초과
• 추가 최적화 검토 필요:
  - LLM 응답 캐싱 강화
  - 벡터 검색 인덱스 최적화
  - 네트워크 지연 시간 점검
"""
        else:
            improvement = ((24 - avg_time) / 24) * 100
            report += f"""• 목표 달성! 24초 → {avg_time:.2f}초 ({improvement:.1f}% 개선)
• 성능이 안정적으로 유지되는지 모니터링 필요
"""
        
        return report

async def main():
    """메인 테스트 실행"""
    # 테스트할 티켓 ID 목록 (실제 데이터에 존재하는 ID 사용)
    test_ticket_ids = [
        "10748",  # 실제 존재하는 티켓 ID로 변경 필요
        "12345",  # 추가 테스트 티켓 ID
    ]
    
    tester = PerformanceTest()
    
    logger.info("🚀 성능 최적화 검증 테스트 시작")
    logger.info("목표: 24초 → 8초 이하 (66% 성능 향상)")
    
    try:
        # 성능 테스트 실행
        results = await tester.run_performance_test(test_ticket_ids, iterations=3)
        
        # 리포트 생성 및 출력
        report = tester.generate_report(results)
        print(report)
        
        # 결과를 파일로 저장
        with open("performance_test_report.txt", "w", encoding="utf-8") as f:
            f.write(report)
            f.write("\n\n📋 상세 결과:\n")
            for result in results:
                f.write(f"{result}\n")
        
        logger.info("📄 성능 테스트 리포트가 performance_test_report.txt에 저장되었습니다.")
        
    except Exception as e:
        logger.error(f"❌ 테스트 실행 중 오류: {e}")

if __name__ == "__main__":
    asyncio.run(main())