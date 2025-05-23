"""
실행 스크립트 - Freshdesk 티켓 무제한 수집

이 스크립트를 실행하여 최적화된 방법으로 대용량 티켓 데이터를 제한 없이 수집하세요.
자세한 사용법은 docs/FRESHDESK_COLLECTION_GUIDE_INTEGRATED.md 문서를 참조하세요.
"""
import asyncio
import logging
import sys
from pathlib import Path
from datetime import datetime

# backend 루트 경로를 sys.path에 추가
BACKEND_ROOT = str(Path(__file__).parent.parent)
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

# 현재 디렉토리를 Python 경로에 추가 (필요시)
sys.path.append(str(Path(__file__).parent))

from freshdesk.optimized_fetcher import OptimizedFreshdeskFetcher
from data.data_processor import process_collected_data

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('freshdesk_collection.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


async def full_collection_workflow():
    """전체 수집 워크플로우"""
    
    # 설정
    OUTPUT_DIR = str(Path(__file__).parent.parent / "freshdesk_full_data")  # backend/freshdesk_full_data
    START_DATE = "2015-01-01"  # 가능한 가장 오래된 날짜부터 시작
    MAX_TICKETS = None  # 무제한 수집 (None = 제한 없음)
    INCLUDE_CONVERSATIONS = True  # 대화내역 포함 여부 (시간 2배 증가)
    INCLUDE_ATTACHMENTS = False   # 첨부파일 정보 포함 여부
    
    # large_scale_config.py에서 대용량 설정 가져오기
    try:
        from large_scale_config import CHUNK_SIZE, REQUEST_DELAY, MAX_RETRIES, SAVE_INTERVAL, check_system_resources
        logger.info("대용량 설정 파일 로드 완료")
    except ImportError:
        logger.warning("large_scale_config.py 파일을 찾을 수 없습니다. 기본 설정을 사용합니다.")
    
    logger.info("=== Freshdesk 전체 티켓 수집 시작 (무제한) ===")
    logger.info(f"출력 디렉토리: {OUTPUT_DIR}")
    logger.info(f"시작 날짜: {START_DATE}")
    logger.info(f"최대 티켓 수: 무제한")
    logger.info(f"대화내역 포함: {INCLUDE_CONVERSATIONS}")
    logger.info(f"첨부파일 포함: {INCLUDE_ATTACHMENTS}")
    
    start_time = datetime.now()
    
    try:
        # 시스템 리소스 체크 기능이 있다면 주기적으로 체크
        resource_check_interval = 1000  # 1000개 티켓마다 체크
        resource_check_func = check_system_resources if 'check_system_resources' in locals() else None
        
        # 1단계: 티켓 데이터 수집
        logger.info("\n1단계: 티켓 데이터 수집 시작")
        async with OptimizedFreshdeskFetcher(OUTPUT_DIR) as fetcher:
            # 대용량 설정 적용
            if 'CHUNK_SIZE' in locals():
                fetcher.CHUNK_SIZE = CHUNK_SIZE
                logger.info(f"청크 크기 조정: {CHUNK_SIZE}")
            if 'REQUEST_DELAY' in locals():
                fetcher.REQUEST_DELAY = REQUEST_DELAY
                logger.info(f"요청 간격 조정: {REQUEST_DELAY}초")
            if 'MAX_RETRIES' in locals():
                fetcher.MAX_RETRIES = MAX_RETRIES
                logger.info(f"최대 재시도 횟수 조정: {MAX_RETRIES}회")
            if 'SAVE_INTERVAL' in locals():
                fetcher.SAVE_INTERVAL = SAVE_INTERVAL
                logger.info(f"저장 간격 조정: {SAVE_INTERVAL}개")
            
            # 무제한 수집 시작
            stats = await fetcher.collect_all_tickets(
                start_date=START_DATE,
                end_date=None,  # 현재까지
                include_conversations=INCLUDE_CONVERSATIONS,
                include_attachments=INCLUDE_ATTACHMENTS,
                max_tickets=MAX_TICKETS,  # None = 무제한
                resource_check_func=resource_check_func,
                resource_check_interval=resource_check_interval
            )
        
        logger.info(f"수집 완료: {stats}")
        
        # 2단계: 데이터 후처리
        logger.info("\n2단계: 데이터 후처리 시작")
        await process_collected_data(OUTPUT_DIR)

        # 3단계: 임베딩 및 Qdrant 저장
        logger.info("\n3단계: 임베딩 및 Qdrant 저장 시작 (ingest.py main 함수 호출)")
        try:
            # ingest.py의 main 함수 동기/비동기 모두 지원
            from api import ingest
            if hasattr(ingest, 'main'):
                main_func = ingest.main
                if asyncio.iscoroutinefunction(main_func):
                    await main_func(OUTPUT_DIR)
                else:
                    main_func(OUTPUT_DIR)
                logger.info("임베딩 및 Qdrant 저장 완료")
            else:
                logger.error("ingest.py에 main 함수가 없습니다. 수동으로 확인하세요.")
        except Exception as e:
            logger.error(f"ingest.py 실행 중 오류 발생: {e}")
            logger.error("임베딩 및 Qdrant 저장 단계에서 문제가 발생했습니다. 로그를 확인하세요.")

        # 4단계: 완료 리포트
        end_time = datetime.now()
        duration = end_time - start_time
        
        logger.info("\n=== 수집 완료 ===")
        logger.info(f"총 소요 시간: {duration}")
        logger.info(f"수집된 티켓 수: {stats['total_tickets_collected']:,}개")
        logger.info(f"생성된 청크 수: {stats['chunks_created']}개")
        logger.info(f"출력 파일들:")
        logger.info(f"  - JSON: {OUTPUT_DIR}/all_tickets.json")
        logger.info(f"  - CSV: {OUTPUT_DIR}/tickets_export.csv")
        logger.info(f"  - 리포트: {OUTPUT_DIR}/summary_report.json")
        
    except KeyboardInterrupt:
        logger.info("\n사용자에 의해 중단됨. 진행 상황이 저장되었습니다.")
        logger.info("동일한 스크립트를 다시 실행하면 중단된 지점부터 재개됩니다.")
        
    except Exception as e:
        logger.error(f"수집 중 오류 발생: {e}")
        logger.info("진행 상황이 저장되었습니다. 문제 해결 후 다시 실행하세요.")
        raise


async def quick_test():
    """빠른 테스트 (1000개 티켓만 수집, 후처리 및 Qdrant 저장까지 전체 워크플로우 실행)"""
    logger.info("=== 빠른 테스트 모드 ===")
    OUTPUT_DIR = str(Path(__file__).parent / "freshdesk_test_data")  # backend/freshdesk/freshdesk_test_data
    try:
        # 1단계: 티켓 데이터 수집
        logger.info("\n1단계: 티켓 데이터 수집 시작 (테스트)")
        async with OptimizedFreshdeskFetcher(OUTPUT_DIR) as fetcher:
            stats = await fetcher.collect_all_tickets(
                start_date="2024-01-01",
                max_tickets=1000,
                include_conversations=False,
                include_attachments=True
            )
        logger.info(f"수집 완료: {stats}")

        # 2단계: 데이터 후처리
        logger.info("\n2단계: 데이터 후처리 시작 (테스트)")
        await process_collected_data(OUTPUT_DIR)

        # 3단계: 임베딩 및 Qdrant 저장
        logger.info("\n3단계: 임베딩 및 Qdrant 저장 시작 (ingest.py main 함수 호출, 테스트)")
        try:
            from api import ingest
            if hasattr(ingest, 'main'):
                main_func = ingest.main
                if asyncio.iscoroutinefunction(main_func):
                    await main_func(OUTPUT_DIR)
                else:
                    main_func(OUTPUT_DIR)
                logger.info("임베딩 및 Qdrant 저장 완료 (테스트)")
            else:
                logger.error("ingest.py에 main 함수가 없습니다. 수동으로 확인하세요.")
        except Exception as e:
            logger.error(f"ingest.py 실행 중 오류 발생: {e}")
            logger.error("임베딩 및 Qdrant 저장 단계에서 문제가 발생했습니다. 로그를 확인하세요.")

        logger.info("\n=== 빠른 테스트 전체 완료 ===")
        logger.info(f"수집된 티켓 수: {stats['total_tickets_collected']:,}개 (테스트)")
        logger.info(f"생성된 청크 수: {stats['chunks_created']}개 (테스트)")
        logger.info(f"출력 파일: {OUTPUT_DIR}/all_tickets.json, {OUTPUT_DIR}/tickets_export.csv")
    except Exception as e:
        logger.error(f"빠른 테스트 중 오류 발생: {e}")
        raise


async def resume_collection():
    """중단된 수집 재개"""
    logger.info("=== 수집 재개 모드 ===")
    
    OUTPUT_DIR = "freshdesk_full_data"
    
    # 진행 상황 확인
    progress_file = Path(OUTPUT_DIR) / "progress.json"
    if not progress_file.exists():
        logger.error("진행 상황 파일을 찾을 수 없습니다. 새로운 수집을 시작하세요.")
        return
    
    import json
    with open(progress_file) as f:
        progress = json.load(f)
    
    logger.info(f"이전 진행 상황:")
    logger.info(f"  - 수집된 티켓 수: {progress.get('total_collected', 0):,}개")
    logger.info(f"  - 완료된 날짜 범위: {len(progress.get('completed_ranges', []))}개")
    logger.info(f"  - 마지막 업데이트: {progress.get('last_updated')}")
    
    # 수집 재개
    await full_collection_workflow()


if __name__ == "__main__":
    print("Freshdesk 대용량 티켓 수집기")
    print("=============================")
    print("1. 전체 수집 (무제한)")
    print("2. 빠른 테스트 (1000건)")
    print("3. 중단된 수집 재개")
    print("4. 종료")
    
    while True:
        try:
            choice = input("\n선택하세요 (1-4): ").strip()
            
            if choice == "1":
                asyncio.run(full_collection_workflow())
                break
            elif choice == "2":
                asyncio.run(quick_test())
                break
            elif choice == "3":
                asyncio.run(resume_collection())
                break
            elif choice == "4":
                print("종료합니다.")
                break
            else:
                print("잘못된 선택입니다. 1-4 중에서 선택하세요.")
                
        except KeyboardInterrupt:
            print("\n\n중단됩니다.")
            break
        except Exception as e:
            logger.error(f"실행 오류: {e}")
            break
