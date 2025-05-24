#!/usr/bin/env python
"""
테스트 및 전체 수집 모드의 출력 디렉토리 구분 테스트 스크립트

이 스크립트는 테스트 데이터가 freshdesk_test_data 폴더에,
전체 수집 데이터가 freshdesk_full_data 폴더에 저장되는지 확인합니다.
"""
import asyncio
import logging
from pathlib import Path

# 로컬 모듈 임포트
from optimized_fetcher import OptimizedFreshdeskFetcher, test_collection_limit, main

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def test_directory_paths():
    """출력 디렉토리 경로 테스트"""
    logger.info("=== 출력 디렉토리 경로 테스트 시작 ===")
    
    # 1. 기본 생성자 테스트
    fetcher = OptimizedFreshdeskFetcher()
    default_path = fetcher.output_dir
    logger.info(f"기본 디렉토리 경로: {default_path}")
    expected_default = Path(__file__).parent.parent / "freshdesk_data"
    assert default_path.resolve() == expected_default.resolve(), "기본 디렉토리 경로 불일치"
    
    # 2. 테스트 모드 디렉토리
    fetcher_test = OptimizedFreshdeskFetcher("freshdesk_test_data")
    test_path = fetcher_test.output_dir
    logger.info(f"테스트 디렉토리 경로: {test_path}")
    expected_test = Path(__file__).parent.parent / "freshdesk_test_data"
    assert test_path.resolve() == expected_test.resolve(), "테스트 디렉토리 경로 불일치"
    
    # 3. 전체 모드 디렉토리
    fetcher_full = OptimizedFreshdeskFetcher("freshdesk_full_data")
    full_path = fetcher_full.output_dir
    logger.info(f"전체 디렉토리 경로: {full_path}")
    expected_full = Path(__file__).parent.parent / "freshdesk_full_data"
    assert full_path.resolve() == expected_full.resolve(), "전체 디렉토리 경로 불일치"
    
    logger.info("=== 출력 디렉토리 경로 테스트 성공 ===")
    return True


async def verify_all_tests():
    """전체 테스트 실행"""
    # 경로 테스트 수행
    path_test_success = await test_directory_paths()
    
    # 함수 확인
    from inspect import getsource
    
    # test_collection_limit 함수에서 freshdesk_test_data 사용 확인
    test_src = getsource(test_collection_limit)
    assert 'output_dir = "freshdesk_test_data"' in test_src, "test_collection_limit 함수가 freshdesk_test_data를 사용하지 않음"
    logger.info("test_collection_limit 함수가 freshdesk_test_data 디렉토리를 사용함: 확인 완료")
    
    # main 함수에서 freshdesk_full_data 사용 확인
    main_src = getsource(main)
    assert 'output_dir = "freshdesk_full_data"' in main_src, "main 함수가 freshdesk_full_data를 사용하지 않음"
    logger.info("main 함수가 freshdesk_full_data 디렉토리를 사용함: 확인 완료")
    
    if path_test_success:
        logger.info("✅ 모든 테스트 통과: 테스트 모드와 전체 수집 모드의 디렉토리 설정이 올바르게 구분됨")
        return True
    else:
        logger.error("❌ 테스트 실패: 디렉토리 설정에 문제가 있습니다.")
        return False


if __name__ == "__main__":
    try:
        success = asyncio.run(verify_all_tests())
        if success:
            print("\n✅ 디렉토리 설정 테스트 전체 통과")
            print("- 테스트 모드: freshdesk_test_data")
            print("- 전체 수집 모드: freshdesk_full_data")
        else:
            print("\n❌ 디렉토리 설정 테스트 실패")
    except Exception as e:
        logger.error(f"테스트 중 오류 발생: {e}")
        print(f"\n❌ 오류 발생: {e}")