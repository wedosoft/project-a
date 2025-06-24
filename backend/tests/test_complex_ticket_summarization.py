#!/usr/bin/env python3
"""
복잡한 티켓 요약 테스트 스크립트

실제 복잡한 티켓 시나리오로 현재 요약 엔진의 성능과 품질을 테스트합니다.
"""

import asyncio
import logging
import os
import sys
import json
from datetime import datetime

# 프로젝트 루트 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.llm.optimized_summarizer import generate_optimized_summary
from core.database.database import get_database

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# 복잡한 티켓 테스트 케이스들
COMPLEX_TICKET_CASES = [
    {
        "id": "complex_ticket_1",
        "subject": "웹사이트 로그인 불가 및 데이터베이스 연결 오류 - 긴급",
        "description": """
        안녕하세요. 저희 회사 웹사이트에 심각한 문제가 발생했습니다.
        
        **문제 상황:**
        1. 고객들이 로그인을 할 수 없습니다
        2. 관리자 페이지도 접근이 안 됩니다
        3. 오류 메시지: "Database connection timeout"
        4. 서버 로그에 "Connection pool exhausted" 에러가 반복적으로 나타남
        
        **발생 시점:** 오늘 오전 9시경부터
        **영향 범위:** 전체 사용자 (약 5,000명)
        **비즈니스 영향:** 
        - 온라인 주문이 불가능한 상태
        - 고객 지원 요청이 급증
        - 예상 매출 손실: 시간당 약 500만원
        
        **시도한 해결책:**
        1. 웹서버 재시작 → 일시적 개선 후 재발
        2. 데이터베이스 재시작 → 효과 없음
        3. 네트워크 연결 확인 → 정상
        4. 방화벽 설정 확인 → 변경사항 없음
        
        **서버 환경:**
        - 웹서버: Apache 2.4.41 (Ubuntu 20.04)
        - 데이터베이스: MySQL 8.0.25
        - 애플리케이션: PHP 7.4
        - 클라우드: AWS EC2 t3.large
        
        **추가 정보:**
        - 어제 밤 시스템 업데이트를 진행했음
        - 새로운 결제 모듈을 배포했음
        - CPU 사용률: 85% (평소 30%)
        - 메모리 사용률: 92% (평소 60%)
        - 디스크 I/O: 높음
        
        **긴급 요청사항:**
        1. 즉시 서비스 복구
        2. 근본 원인 분석
        3. 재발 방지 대책 수립
        4. 고객 공지사항 작성 지원
        
        연락처: 010-1234-5678 (24시간 대기)
        담당자: 김철수 (IT팀장)
        """,
        "conversations": [
            {
                "user": "support_agent",
                "content": "안녕하세요. 긴급 티켓 접수 확인했습니다. 즉시 1차 대응을 시작하겠습니다.",
                "timestamp": "2024-06-24 09:15:00"
            },
            {
                "user": "customer",
                "content": "감사합니다. 현재 고객 문의가 폭주하고 있어서 매우 급합니다.",
                "timestamp": "2024-06-24 09:16:00"
            },
            {
                "user": "tech_support",
                "content": """1차 분석 결과:
                - 데이터베이스 커넥션 풀이 고갈된 상태
                - 어제 배포한 결제 모듈에서 커넥션 누수 의심
                - 애플리케이션 로그에서 PreparedStatement 관련 오류 다수 발견
                
                즉시 조치사항:
                1. 결제 모듈 일시 비활성화
                2. 데이터베이스 커넥션 풀 크기 임시 증가
                3. 애플리케이션 재시작""",
                "timestamp": "2024-06-24 09:30:00"
            },
            {
                "user": "customer", 
                "content": "결제 모듈 비활성화하면 결제는 어떻게 처리하나요?",
                "timestamp": "2024-06-24 09:32:00"
            },
            {
                "user": "tech_support",
                "content": """결제 관련 대안:
                1. 기존 결제 시스템으로 롤백 (30분 소요)
                2. 수동 결제 접수 (임시방편)
                3. 고객 공지 후 오후에 결제 재개
                
                권장사항: 1번 롤백 진행하겠습니다.""",
                "timestamp": "2024-06-24 09:35:00"
            },
            {
                "user": "customer",
                "content": "네, 롤백 진행해주세요. 예상 복구 시간을 알려주세요.",
                "timestamp": "2024-06-24 09:36:00"
            },
            {
                "user": "tech_support",
                "content": """복구 계획:
                - 1단계: 결제 모듈 롤백 (진행중, 15분 남음)
                - 2단계: 서비스 정상화 확인 (10분)
                - 3단계: 부하 테스트 (15분)
                
                예상 완전 복구: 오전 10:15경
                부분 서비스 재개: 오전 10:00경""",
                "timestamp": "2024-06-24 09:45:00"
            }
        ],
        "expected_summary_points": [
            "웹사이트 로그인 불가 및 데이터베이스 연결 오류",
            "전체 사용자 5,000명 영향",
            "시간당 500만원 매출 손실",
            "결제 모듈 배포 후 발생",
            "데이터베이스 커넥션 풀 고갈이 원인",
            "결제 모듈 롤백으로 해결"
        ]
    },
    {
        "id": "complex_ticket_2", 
        "subject": "API 응답 지연 및 타임아웃 오류 다발 발생",
        "description": """
        API 서비스에 심각한 성능 저하가 발생하고 있습니다.
        
        **문제 증상:**
        - API 응답시간이 평소 200ms에서 5-10초로 증가
        - 타임아웃 오류율이 0.1%에서 15%로 급증
        - 특정 엔드포인트(/api/search, /api/orders)에서 집중 발생
        
        **모니터링 데이터:**
        - 평균 응답시간: 8.5초 (SLA: 2초 이하)
        - 오류율: 15.3% (SLA: 1% 이하)
        - 처리량: 50 req/sec (평소 200 req/sec)
        - 큐 대기시간: 30초+
        
        **사용자 영향:**
        - 모바일 앱에서 검색 불가
        - 웹사이트 장바구니 기능 마비
        - 파트너사 연동 API 실패
        - 고객 불만 접수 급증
        """,
        "conversations": [
            {
                "user": "monitoring_system",
                "content": "🚨 ALERT: API 응답시간 SLA 위반 - 평균 8.5초 (임계값: 2초)",
                "timestamp": "2024-06-24 14:30:00"
            },
            {
                "user": "devops_team", 
                "content": """즉시 조사 시작:
                - 서버 리소스 확인: CPU 95%, Memory 87%
                - 데이터베이스 커넥션: 90/100 사용중
                - 캐시 적중률: 45% (평소 85%)
                - 로드밸런서 상태: 2/4 서버 응답불가""",
                "timestamp": "2024-06-24 14:35:00"
            },
            {
                "user": "database_admin",
                "content": """DB 분석 결과:
                - Slow query 다수 발견 (/api/search 관련)
                - 인덱스 스캔 비율 증가
                - 임시 테이블 생성 과다
                - 최근 데이터 증가로 쿼리 플랜 변경 추정""",
                "timestamp": "2024-06-24 14:45:00"
            }
        ]
    },
    {
        "id": "complex_ticket_3",
        "subject": "대용량 파일 업로드 실패 및 스토리지 용량 부족",
        "description": """
        **긴급상황:** 고객사의 중요한 프레젠테이션 파일(500MB+) 업로드가 계속 실패하고 있습니다.
        
        **문제 상세:**
        1. 100MB 이상 파일 업로드 시 99%에서 실패
        2. 오류 메시지: "Storage quota exceeded" 
        3. 스토리지 사용량: 98% (4.9TB/5TB)
        4. 임시 파일이 정리되지 않아 누적됨
        
        **비즈니스 임팩트:**
        - VIP 고객사 프레젠테이션 준비 차질
        - 내일 오전 중요 미팅에 필요한 자료
        - 계약 갱신과 직결된 상황
        
        **기술적 이슈:**
        - PHP max_upload_size: 1GB (충분함)
        - Nginx client_max_body_size: 1GB (충분함) 
        - AWS S3 버킷 용량: 거의 가득참
        - CloudFront 캐시 정책 문제 의심
        """,
        "conversations": [
            {
                "user": "vip_customer",
                "content": "내일 오전 9시 중요한 프레젠테이션이 있는데 파일을 올릴 수가 없습니다. 매우 급합니다!",
                "timestamp": "2024-06-24 16:00:00"
            },
            {
                "user": "senior_support",
                "content": "VIP 고객 긴급 이슈로 확인했습니다. 즉시 엔지니어팀에 에스컬레이션하겠습니다.",
                "timestamp": "2024-06-24 16:02:00"
            },
            {
                "user": "infrastructure_team",
                "content": """즉시 조치사항:
                1. 임시 스토리지 확장 (1TB 추가)
                2. 오래된 임시파일 정리 스크립트 실행
                3. VIP 고객 전용 업로드 경로 생성
                4. 대용량 파일 분할 업로드 기능 임시 활성화""",
                "timestamp": "2024-06-24 16:10:00"
            }
        ]
    }
]


async def test_single_ticket(ticket_case: dict, ui_language: str = "ko") -> dict:
    """단일 티켓 요약 테스트"""
    
    logger.info(f"=== 티켓 요약 테스트: {ticket_case['id']} ===")
    logger.info(f"제목: {ticket_case['subject']}")
    
    # 티켓 내용 구성
    full_content = f"""제목: {ticket_case['subject']}

설명:
{ticket_case['description']}

대화 내역:
"""
    
    # 대화 내역 추가
    for i, conv in enumerate(ticket_case.get('conversations', [])):
        timestamp = conv.get('timestamp', '')
        user = conv.get('user', 'unknown')
        content = conv.get('content', '')
        full_content += f"\n[{timestamp}] {user}:\n{content}\n"
    
    try:
        start_time = datetime.now()
        
        # 요약 생성
        summary = await generate_optimized_summary(
            content=full_content,
            content_type="ticket",
            subject=ticket_case['subject'],
            ui_language=ui_language
        )
        
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        
        logger.info("✅ 요약 생성 성공")
        logger.info(f"⏱️ 처리 시간: {processing_time:.2f}초")
        logger.info("📄 생성된 요약:")
        print("-" * 60)
        print(summary)
        print("-" * 60)
        
        # 품질 평가
        quality_score = evaluate_summary_quality(
            summary, 
            ticket_case.get('expected_summary_points', [])
        )
        
        return {
            "ticket_id": ticket_case['id'],
            "success": True,
            "processing_time": processing_time,
            "summary": summary,
            "quality_score": quality_score,
            "content_length": len(full_content),
            "summary_length": len(summary)
        }
        
    except Exception as e:
        logger.error(f"❌ 요약 생성 실패: {e}")
        return {
            "ticket_id": ticket_case['id'],
            "success": False,
            "error": str(e),
            "content_length": len(full_content)
        }


def evaluate_summary_quality(summary: str, expected_points: list) -> dict:
    """요약 품질 평가"""
    
    if not expected_points:
        return {"score": 0, "reason": "평가 기준 없음"}
    
    # 기대하는 포인트들이 요약에 포함되어 있는지 확인
    points_found = 0
    found_points = []
    missing_points = []
    
    for point in expected_points:
        # 간단한 키워드 매칭 (실제로는 더 정교한 평가 필요)
        keywords = point.split()
        matches = sum(1 for keyword in keywords if keyword in summary)
        
        if matches >= len(keywords) * 0.5:  # 50% 이상 키워드 매칭
            points_found += 1
            found_points.append(point)
        else:
            missing_points.append(point)
    
    score = (points_found / len(expected_points)) * 100
    
    return {
        "score": round(score, 1),
        "points_found": points_found,
        "total_points": len(expected_points),
        "found_points": found_points,
        "missing_points": missing_points
    }


async def test_all_complex_tickets():
    """모든 복잡한 티켓 테스트 실행"""
    
    logger.info("🚀 복잡한 티켓 요약 엔진 테스트 시작")
    logger.info(f"📋 테스트 케이스 수: {len(COMPLEX_TICKET_CASES)}")
    
    results = []
    total_processing_time = 0
    
    for i, ticket_case in enumerate(COMPLEX_TICKET_CASES, 1):
        logger.info(f"\n🎯 테스트 {i}/{len(COMPLEX_TICKET_CASES)} 시작")
        
        result = await test_single_ticket(ticket_case)
        results.append(result)
        
        if result['success']:
            total_processing_time += result['processing_time']
        
        # 테스트 간 간격
        await asyncio.sleep(1)
    
    # 결과 요약
    logger.info("\n" + "="*80)
    logger.info("🎯 테스트 결과 요약")
    logger.info("="*80)
    
    successful_tests = [r for r in results if r['success']]
    failed_tests = [r for r in results if not r['success']]
    
    logger.info(f"✅ 성공: {len(successful_tests)}/{len(results)}")
    logger.info(f"❌ 실패: {len(failed_tests)}/{len(results)}")
    logger.info(f"⏱️ 총 처리 시간: {total_processing_time:.2f}초")
    
    if successful_tests:
        avg_processing_time = total_processing_time / len(successful_tests)
        logger.info(f"📊 평균 처리 시간: {avg_processing_time:.2f}초")
        
        # 품질 점수 통계
        quality_scores = [r.get('quality_score', {}).get('score', 0) for r in successful_tests if 'quality_score' in r]
        if quality_scores:
            avg_quality = sum(quality_scores) / len(quality_scores)
            logger.info(f"📈 평균 품질 점수: {avg_quality:.1f}/100")
    
    # 개별 결과 상세
    logger.info("\n📝 개별 테스트 결과:")
    for result in results:
        status = "✅" if result['success'] else "❌"
        ticket_id = result['ticket_id']
        
        if result['success']:
            time_taken = result['processing_time']
            quality = result.get('quality_score', {}).get('score', 0)
            logger.info(f"  {status} {ticket_id}: {time_taken:.2f}초, 품질 {quality:.1f}/100")
        else:
            error = result.get('error', 'Unknown error')
            logger.info(f"  {status} {ticket_id}: 실패 - {error}")
    
    # 실패한 테스트가 있으면 상세 정보
    if failed_tests:
        logger.info("\n❌ 실패한 테스트 상세:")
        for result in failed_tests:
            logger.error(f"  - {result['ticket_id']}: {result.get('error', 'Unknown error')}")
    
    return results


async def test_specific_ticket(ticket_id: str):
    """특정 티켓만 테스트"""
    
    ticket_case = next((t for t in COMPLEX_TICKET_CASES if t['id'] == ticket_id), None)
    if not ticket_case:
        logger.error(f"티켓 ID '{ticket_id}'를 찾을 수 없습니다.")
        logger.info(f"사용 가능한 티켓 ID: {[t['id'] for t in COMPLEX_TICKET_CASES]}")
        return
    
    result = await test_single_ticket(ticket_case)
    
    if result['success']:
        logger.info(f"\n🎉 테스트 완료: {result['processing_time']:.2f}초")
        if 'quality_score' in result:
            quality = result['quality_score']
            logger.info(f"📊 품질 점수: {quality['score']}/100")
            logger.info(f"📝 포함된 포인트: {quality['points_found']}/{quality['total_points']}")
    
    return result


async def get_real_ticket_from_db(ticket_id: str, company_id: str = "wedosoft", platform: str = "freshdesk") -> dict:
    """실제 데이터베이스에서 티켓 정보를 가져옴"""
    
    try:
        logger.info(f"DB에서 티켓 조회 중: ticket_id={ticket_id}, company_id={company_id}")
        
        # 데이터베이스 연결
        db = get_database(company_id, platform)
        
        # 티켓 정보 조회
        cursor = db.connection.cursor()
        cursor.execute("""
            SELECT 
                original_id,
                subject,
                description,
                description_text,
                status,
                priority,
                created_at,
                updated_at,
                raw_data
            FROM tickets 
            WHERE original_id = ? AND company_id = ? AND platform = ?
        """, (str(ticket_id), company_id, platform))
        
        ticket_row = cursor.fetchone()
        if not ticket_row:
            logger.error(f"티켓 {ticket_id}를 찾을 수 없습니다.")
            return None
        
        # 딕셔너리로 변환
        ticket = dict(ticket_row)
        
        # 대화 내역 조회
        cursor.execute("""
            SELECT 
                original_id,
                user_id,
                body,
                body_text,
                incoming,
                private,
                created_at,
                from_email,
                to_emails
            FROM conversations 
            WHERE ticket_original_id = ? AND company_id = ? AND platform = ?
            ORDER BY created_at ASC
        """, (str(ticket_id), company_id, platform))
        
        conversations = [dict(row) for row in cursor.fetchall()]
        
        logger.info(f"티켓 조회 완료: 제목='{ticket['subject']}', 대화수={len(conversations)}")
        
        return {
            "ticket": ticket,
            "conversations": conversations
        }
        
    except Exception as e:
        logger.error(f"DB 조회 중 오류: {e}")
        return None


async def test_real_ticket(ticket_id: str, company_id: str = "wedosoft", platform: str = "freshdesk", ui_language: str = "ko") -> dict:
    """실제 DB 티켓으로 요약 테스트"""
    
    logger.info(f"=== 실제 티켓 요약 테스트: {ticket_id} ===")
    
    # DB에서 티켓 조회
    ticket_data = await get_real_ticket_from_db(ticket_id, company_id, platform)
    if not ticket_data:
        return {
            "ticket_id": ticket_id,
            "success": False,
            "error": "티켓을 찾을 수 없습니다"
        }
    
    ticket = ticket_data["ticket"]
    conversations = ticket_data["conversations"]
    
    # 티켓 내용 구성
    full_content = f"""제목: {ticket['subject']}

설명:
{ticket.get('description_text') or ticket.get('description', '')}

상태: {ticket.get('status', 'Unknown')}
우선순위: {ticket.get('priority', 'Unknown')}
생성일: {ticket.get('created_at', 'Unknown')}
"""
    
    # 대화 내역 추가
    if conversations:
        full_content += "\n대화 내역:\n"
        for i, conv in enumerate(conversations):
            timestamp = conv.get('created_at', '')
            user_info = f"사용자 {conv.get('user_id', 'Unknown')}"
            if conv.get('from_email'):
                user_info += f" ({conv.get('from_email')})"
            
            content = conv.get('body_text') or conv.get('body', '')
            if content:
                full_content += f"\n[{timestamp}] {user_info}:\n{content}\n"
    
    try:
        start_time = datetime.now()
        
        # 요약 생성
        summary = await generate_optimized_summary(
            content=full_content,
            content_type="ticket",
            subject=ticket['subject'],
            ui_language=ui_language
        )
        
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        
        logger.info("✅ 요약 생성 성공")
        logger.info(f"⏱️ 처리 시간: {processing_time:.2f}초")
        logger.info("📄 생성된 요약:")
        print("=" * 80)
        print(f"티켓 ID: {ticket_id}")
        print(f"제목: {ticket['subject']}")
        print("-" * 80)
        print(summary)
        print("=" * 80)
        
        return {
            "ticket_id": ticket_id,
            "success": True,
            "processing_time": processing_time,
            "summary": summary,
            "original_subject": ticket['subject'],
            "content_length": len(full_content),
            "summary_length": len(summary),
            "conversations_count": len(conversations),
            "ticket_status": ticket.get('status'),
            "ticket_priority": ticket.get('priority')
        }
        
    except Exception as e:
        logger.error(f"❌ 요약 생성 실패: {e}")
        return {
            "ticket_id": ticket_id,
            "success": False,
            "error": str(e),
            "content_length": len(full_content)
        }


async def test_multiple_real_tickets(ticket_ids: list, company_id: str = "wedosoft", platform: str = "freshdesk"):
    """여러 실제 티켓 테스트"""
    
    logger.info(f"🚀 실제 티켓 다중 요약 테스트 시작")
    logger.info(f"📋 테스트 티켓 수: {len(ticket_ids)}")
    logger.info(f"🎯 티켓 ID들: {ticket_ids}")
    
    results = []
    total_processing_time = 0
    
    for i, ticket_id in enumerate(ticket_ids, 1):
        logger.info(f"\n🎯 테스트 {i}/{len(ticket_ids)} 시작 - 티켓 {ticket_id}")
        
        result = await test_real_ticket(ticket_id, company_id, platform)
        results.append(result)
        
        if result['success']:
            total_processing_time += result['processing_time']
        
        # 테스트 간 간격
        await asyncio.sleep(2)
    
    # 결과 요약
    logger.info("\n" + "="*80)
    logger.info("🎯 실제 티켓 테스트 결과 요약")
    logger.info("="*80)
    
    successful_tests = [r for r in results if r['success']]
    failed_tests = [r for r in results if not r['success']]
    
    logger.info(f"✅ 성공: {len(successful_tests)}/{len(results)}")
    logger.info(f"❌ 실패: {len(failed_tests)}/{len(results)}")
    logger.info(f"⏱️ 총 처리 시간: {total_processing_time:.2f}초")
    
    if successful_tests:
        avg_processing_time = total_processing_time / len(successful_tests)
        logger.info(f"📊 평균 처리 시간: {avg_processing_time:.2f}초")
        
        # 내용 길이 통계
        content_lengths = [r['content_length'] for r in successful_tests]
        summary_lengths = [r['summary_length'] for r in successful_tests]
        
        avg_content_length = sum(content_lengths) / len(content_lengths)
        avg_summary_length = sum(summary_lengths) / len(summary_lengths)
        compression_ratio = (avg_summary_length / avg_content_length) * 100
        
        logger.info(f"📝 평균 원본 길이: {avg_content_length:.0f}자")
        logger.info(f"📄 평균 요약 길이: {avg_summary_length:.0f}자")
        logger.info(f"🗜️ 압축률: {compression_ratio:.1f}%")
    
    # 개별 결과 상세
    logger.info("\n📝 개별 테스트 결과:")
    for result in results:
        status = "✅" if result['success'] else "❌"
        ticket_id = result['ticket_id']
        
        if result['success']:
            time_taken = result['processing_time']
            subject = result.get('original_subject', 'N/A')[:50]
            logger.info(f"  {status} 티켓 {ticket_id}: {time_taken:.2f}초")
            logger.info(f"      제목: {subject}...")
        else:
            error = result.get('error', 'Unknown error')
            logger.info(f"  {status} 티켓 {ticket_id}: 실패 - {error}")
    
    return results


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="복잡한 티켓 요약 테스트")
    parser.add_argument("--ticket", help="특정 티켓 ID만 테스트 (예: complex_ticket_1)")
    parser.add_argument("--real-tickets", nargs='+', help="실제 DB 티켓 ID들 (예: --real-tickets 12791 11925 12643)")
    parser.add_argument("--company", default="wedosoft", help="회사 ID (기본값: wedosoft)")
    parser.add_argument("--platform", default="freshdesk", help="플랫폼 (기본값: freshdesk)")
    parser.add_argument("--language", default="ko", help="UI 언어 (ko/en)")
    
    args = parser.parse_args()
    
    if args.real_tickets:
        # 실제 DB 티켓 테스트
        asyncio.run(test_multiple_real_tickets(args.real_tickets, args.company, args.platform))
    elif args.ticket:
        # 가상 티켓 테스트
        asyncio.run(test_specific_ticket(args.ticket))
    else:
        # 모든 가상 티켓 테스트
        asyncio.run(test_all_complex_tickets())
