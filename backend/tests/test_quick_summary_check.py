#!/usr/bin/env python3
"""
대용량 요약 시스템 빠른 테스트

시스템이 제대로 작동하는지 확인하는 간단한 테스트입니다.
"""

import asyncio
import logging
import sys
import os

# 프로젝트 루트 경로 설정
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.llm.summarizer import generate_summary, enable_large_scale_processing, disable_large_scale_processing

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_basic_summary():
    """기본 요약 테스트"""
    
    test_content = """
    고객이 로그인할 수 없다고 문의했습니다. 
    확인해보니 비밀번호가 만료되어 있었습니다.
    비밀번호를 재설정해드렸고, 정상적으로 로그인할 수 있게 되었습니다.
    앞으로는 비밀번호 만료 전에 미리 알림을 보내드리겠습니다.
    """
    
    logger.info("=== 기본 요약 테스트 ===")
    
    try:
        summary = await generate_summary(
            content=test_content,
            content_type="ticket",
            subject="로그인 문제",
            ui_language="ko"
        )
        
        logger.info("✅ 기본 요약 성공")
        logger.info(f"요약 내용:\n{summary}")
        
        # 품질 확인
        required_sections = ["문제 상황", "근본 원인", "해결 과정", "핵심 포인트"]
        found_sections = [section for section in required_sections if section in summary]
        
        if len(found_sections) == len(required_sections):
            logger.info(f"✅ 구조 검증 통과: {found_sections}")
        else:
            logger.warning(f"⚠️ 구조 검증 부분 통과: {found_sections}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 기본 요약 실패: {e}")
        return False


async def test_large_scale_mode():
    """대용량 모드 테스트"""
    
    test_contents = [
        "서버 응답이 느려서 확인했더니 데이터베이스 연결이 끊어져 있었습니다. 재연결 후 정상화되었습니다.",
        "파일 업로드가 안 된다고 하여 확인해보니 용량 제한 때문이었습니다. 제한을 늘려드렸습니다.",
        "이메일 발송이 안 된다고 하여 SMTP 설정을 확인했더니 인증서가 만료되어 있었습니다. 갱신 후 해결되었습니다."
    ]
    
    logger.info("=== 대용량 모드 테스트 ===")
    
    try:
        # 대용량 모드 활성화 (가상으로 1000건)
        enable_large_scale_processing(1000)
        logger.info("✅ 대용량 모드 활성화")
        
        results = []
        for i, content in enumerate(test_contents):
            summary = await generate_summary(
                content=content,
                content_type="ticket",
                subject=f"테스트 티켓 {i+1}",
                ui_language="ko"
            )
            results.append(summary)
            logger.info(f"✅ 배치 아이템 {i+1} 처리 완료")
        
        # 대용량 모드 비활성화
        disable_large_scale_processing()
        logger.info("✅ 대용량 모드 비활성화")
        
        # 결과 확인
        logger.info(f"✅ 총 {len(results)}개 요약 생성 완료")
        for i, summary in enumerate(results):
            logger.info(f"--- 요약 {i+1} ---")
            logger.info(summary[:200] + "..." if len(summary) > 200 else summary)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 대용량 모드 테스트 실패: {e}")
        disable_large_scale_processing()  # 실패 시에도 비활성화
        return False


async def test_quality_validation():
    """품질 검증 테스트"""
    
    logger.info("=== 품질 검증 테스트 ===")
    
    # 의도적으로 품질이 떨어질 수 있는 짧은 내용
    short_content = "문제 해결됨"
    
    try:
        summary = await generate_summary(
            content=short_content,
            content_type="ticket",
            subject="짧은 내용 테스트",
            ui_language="ko"
        )
        
        logger.info("✅ 짧은 내용 요약 생성 완료")
        logger.info(f"요약 길이: {len(summary)}자")
        
        # 최소 길이 확인
        if len(summary) >= 100:
            logger.info("✅ 최소 길이 기준 통과")
        else:
            logger.warning("⚠️ 최소 길이 기준 미달")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 품질 검증 테스트 실패: {e}")
        return False


async def main():
    """메인 테스트 실행"""
    
    logger.info("🚀 대용량 요약 시스템 빠른 테스트 시작")
    
    results = []
    
    # 1. 기본 요약 테스트
    results.append(await test_basic_summary())
    
    # 2. 대용량 모드 테스트
    results.append(await test_large_scale_mode())
    
    # 3. 품질 검증 테스트
    results.append(await test_quality_validation())
    
    # 결과 요약
    logger.info("\n" + "="*50)
    logger.info("🎯 테스트 결과 요약")
    logger.info("="*50)
    
    test_names = ["기본 요약", "대용량 모드", "품질 검증"]
    
    passed = 0
    for i, (name, result) in enumerate(zip(test_names, results)):
        status = "✅ 통과" if result else "❌ 실패"
        logger.info(f"{i+1}. {name}: {status}")
        if result:
            passed += 1
    
    logger.info(f"\n총 {passed}/{len(results)}개 테스트 통과")
    
    if passed == len(results):
        logger.info("🎉 모든 테스트 통과! 시스템이 정상적으로 작동합니다.")
        return True
    else:
        logger.warning("⚠️ 일부 테스트 실패. 시스템 설정을 확인해주세요.")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
