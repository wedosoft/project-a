"""
실행 스크립트 - Freshdesk 티켓 무제한 수집

이 스크립트를 실행하여 최적화된 방법으로 대용량 티켓 데이터를 제한 없이 수집하세요.
자세한 사용법은 docs/FRESHDESK_COLLECTION_GUIDE_INTEGRATED.md 문서를 참조하세요.
"""
import argparse
import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path

# backend 루트 경로를 sys.path에 추가
BACKEND_ROOT = str(Path(__file__).parent.parent)
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

# 현재 디렉토리를 Python 경로에 추가 (필요시)
sys.path.append(str(Path(__file__).parent))

from api.ingest import ingest as ingest_main
from data.data_processor import process_collected_data

from freshdesk.optimized_fetcher import OptimizedFreshdeskFetcher

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


async def full_collection_workflow(reset_vectordb: bool = False, create_backup: bool = True, skip_confirmation: bool = False):
    """전체 수집 워크플로우"""
    
    # 설정
    OUTPUT_DIR = str(Path(__file__).parent.parent / "freshdesk_full_data")  # backend/freshdesk_full_data
    START_DATE = "2015-01-01"  # 가능한 가장 오래된 날짜부터 시작
    MAX_TICKETS = None  # 무제한 수집 (None = 제한 없음)
    INCLUDE_CONVERSATIONS = True  # 대화내역 포함 여부 (시간 2배 증가)
    INCLUDE_ATTACHMENTS = True    # 첨부파일 정보 포함 여부 (메타데이터만, 실제 파일 다운로드 X)
    DAYS_PER_CHUNK = 14  # 날짜 범위 청크 크기 (기본 14일)
    ADAPTIVE_RATE = True  # 서버 응답에 따른 요청 간격 자동 조절
    
    # large_scale_config.py에서 대용량 설정 가져오기
    try:
        from large_scale_config import (
            CHUNK_SIZE,
            MAX_RETRIES,
            REQUEST_DELAY,
            SAVE_INTERVAL,
            check_system_resources,
        )

        # 날짜 범위 청크 크기도 설정 파일에서 가져오기 시도
        from large_scale_config import DAYS_PER_CHUNK as CONFIG_DAYS_PER_CHUNK
        DAYS_PER_CHUNK = CONFIG_DAYS_PER_CHUNK  # 설정 파일 값으로 덮어쓰기
        logger.info("대용량 설정 파일 로드 완료")
        
        # 벡터DB 초기화 설정 가져오기
        try:
            from large_scale_config import RESET_VECTORDB as ENV_RESET_VECTORDB
            from large_scale_config import SKIP_VECTORDB_CONFIRMATION, VECTOR_DB_CONFIG
            # CLI 옵션이 우선, 환경 설정은 그 다음, 기본값은 마지막
            RESET_VECTORDB = reset_vectordb or ENV_RESET_VECTORDB or VECTOR_DB_CONFIG.get("auto_reset_on_full_collection", False)
            CREATE_BACKUP = create_backup and VECTOR_DB_CONFIG.get("create_backup_before_reset", True)
            CONFIRM_REQUIRED = not skip_confirmation and not SKIP_VECTORDB_CONFIRMATION and VECTOR_DB_CONFIG.get("confirm_required", True)
            logger.info("벡터DB 초기화 설정 로드 완료")
        except (ImportError, AttributeError):
            RESET_VECTORDB = reset_vectordb
            CREATE_BACKUP = create_backup
            CONFIRM_REQUIRED = not skip_confirmation
            logger.warning("벡터DB 초기화 설정을 찾을 수 없습니다. 기본값을 사용합니다.")
    except ImportError:
        logger.warning("large_scale_config.py 파일을 찾을 수 없습니다. 기본 설정을 사용합니다.")
        RESET_VECTORDB = reset_vectordb
        CREATE_BACKUP = create_backup
        CONFIRM_REQUIRED = not skip_confirmation
    except AttributeError as e:
        logger.warning(f"설정 파일에서 일부 값을 찾을 수 없습니다: {e}")
        RESET_VECTORDB = reset_vectordb
        CREATE_BACKUP = create_backup
        CONFIRM_REQUIRED = not skip_confirmation

    logger.info("=== Freshdesk 전체 티켓 수집 시작 (무제한) ===")
    logger.info(f"출력 디렉토리: {OUTPUT_DIR}")
    logger.info(f"시작 날짜: {START_DATE}")
    logger.info(f"최대 티켓 수: 무제한")
    logger.info(f"대화내역 포함: {INCLUDE_CONVERSATIONS}")
    logger.info(f"첨부파일 포함: {INCLUDE_ATTACHMENTS}")
    logger.info(f"날짜 범위 청크 크기: {DAYS_PER_CHUNK}일")
    logger.info(f"적응형 속도 조절: {'활성화' if ADAPTIVE_RATE else '비활성화'}")
    logger.info(f"벡터DB 초기화: {RESET_VECTORDB}")
    if RESET_VECTORDB:
        logger.info(f"백업 생성: {CREATE_BACKUP}")
        logger.info(f"확인 필요: {CONFIRM_REQUIRED}")
        
    start_time = datetime.now()
    
    # 벡터DB 초기화 옵션이 활성화된 경우
    if RESET_VECTORDB:
        from core.vectordb import COLLECTION_NAME, FAQ_COLLECTION_NAME, QdrantAdapter
        
        # 메인 컬렉션 초기화
        try:
            # 컬렉션 정보 확인
            vector_db = QdrantAdapter(collection_name=COLLECTION_NAME)
            collection_info = vector_db.get_collection_info()
            points_count = collection_info.get("points_count", 0)
            
            logger.info(f"벡터DB 초기화 준비: 컬렉션 '{collection_info['name']}'에 {points_count:,}개 포인트 존재")
            
            # 사용자 확인 필요 시 확인 요청
            proceed_with_reset = True
            if CONFIRM_REQUIRED and points_count > 0:
                confirmation = input(f"⚠️ 경고: 벡터DB 컬렉션 '{collection_info['name']}'의 모든 데이터({points_count:,}개 포인트)가 삭제됩니다. 계속하시겠습니까? (yes/no): ")
                proceed_with_reset = confirmation.lower() in ['yes', 'y']
            
            # 초기화 진행
            if proceed_with_reset:
                logger.info("벡터DB 메인 컬렉션 초기화 시작...")
                
                # 백업 경로 설정
                backup_path = None
                if CREATE_BACKUP:
                    import os
                    
                    backup_dir = os.path.join(os.getcwd(), "backups")
                    os.makedirs(backup_dir, exist_ok=True)
                    backup_path = os.path.join(
                        backup_dir, 
                        f"{COLLECTION_NAME}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                    )
                    
                    logger.info(f"벡터DB 백업 시작: {backup_path}")
                
                # 초기화 실행
                success = vector_db.reset_collection(confirm=True, create_backup=CREATE_BACKUP, backup_path=backup_path)
                
                if success:
                    logger.info(f"✅ 벡터DB 메인 컬렉션('{COLLECTION_NAME}') 초기화 완료")
                else:
                    logger.error(f"❌ 벡터DB 메인 컬렉션('{COLLECTION_NAME}') 초기화 실패 - 진행을 중단합니다.")
                    return
            else:
                logger.info("사용자가 벡터DB 초기화를 취소했습니다. 진행을 중단합니다.")
                return
                
            # FAQ 컬렉션 초기화 (필요한 경우)
            try:
                # FAQ 컬렉션 정보 확인
                faq_db = QdrantAdapter(collection_name=FAQ_COLLECTION_NAME)
                faq_info = faq_db.get_collection_info()
                faq_count = faq_info.get("points_count", 0)
                
                if faq_count > 0:
                    logger.info(f"FAQ 컬렉션 '{FAQ_COLLECTION_NAME}'에 {faq_count:,}개 포인트 존재")
                    
                    # 사용자 확인 (이미 메인 컬렉션에서 확인했으므로 건너뛸 수 있음)
                    faq_proceed = True
                    if CONFIRM_REQUIRED and not proceed_with_reset:  # 메인 컬렉션에서 이미 확인했으면 넘어감
                        faq_confirmation = input(f"⚠️ 경고: FAQ 컬렉션 '{FAQ_COLLECTION_NAME}'의 모든 데이터({faq_count:,}개 포인트)가 삭제됩니다. 계속하시겠습니까? (yes/no): ")
                        faq_proceed = faq_confirmation.lower() in ['yes', 'y']
                    
                    if faq_proceed:
                        logger.info(f"FAQ 컬렉션 초기화 시작...")
                        
                        # 백업 경로 설정
                        faq_backup_path = None
                        if CREATE_BACKUP:
                            import os
                            
                            backup_dir = os.path.join(os.getcwd(), "backups")
                            os.makedirs(backup_dir, exist_ok=True)
                            faq_backup_path = os.path.join(
                                backup_dir, 
                                f"{FAQ_COLLECTION_NAME}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                            )
                            
                            logger.info(f"FAQ 컬렉션 백업 시작: {faq_backup_path}")
                        
                        # FAQ 컬렉션 초기화
                        faq_success = faq_db.reset_collection(confirm=True, create_backup=CREATE_BACKUP, backup_path=faq_backup_path)
                        
                        if faq_success:
                            logger.info(f"✅ FAQ 컬렉션('{FAQ_COLLECTION_NAME}') 초기화 완료")
                        else:
                            logger.error(f"❌ FAQ 컬렉션('{FAQ_COLLECTION_NAME}') 초기화 실패")
                    else:
                        logger.info("사용자가 FAQ 컬렉션 초기화를 취소했습니다.")
                else:
                    logger.info(f"FAQ 컬렉션 '{FAQ_COLLECTION_NAME}'에 데이터가 없습니다. 초기화 필요 없음.")
            except Exception as faq_e:
                logger.error(f"FAQ 컬렉션 초기화 과정에서 오류 발생: {faq_e}")
                logger.warning("FAQ 컬렉션 초기화는 실패했지만 메인 수집은 계속 진행합니다.")
            
        except Exception as e:
            logger.error(f"벡터DB 초기화 중 오류 발생: {e}")
            logger.error("벡터DB 초기화에 실패했습니다. 진행을 중단합니다.")
            return

    try:
        # 시스템 리소스 체크 기능이 있다면 주기적으로 체크
        resource_check_interval = 100  # 100개 티켓마다 체크
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
                resource_check_interval=resource_check_interval,
                days_per_chunk=DAYS_PER_CHUNK,  # 날짜 범위 청크 크기
                adaptive_rate=ADAPTIVE_RATE     # 적응형 속도 조절
            )
        
        logger.info(f"수집 완료: {stats}")
        
        # 2단계: 데이터 후처리
        logger.info("\n2단계: 데이터 후처리 시작")
        await process_collected_data(OUTPUT_DIR)

        # 3단계: 임베딩 및 Qdrant 저장
        logger.info("\n3단계: 임베딩 및 Qdrant 저장 시작")
        try:
            # 이미 import된 ingest_main 함수 사용
            logger.info(f"수집된 데이터를 Qdrant에 저장 중... (디렉토리: {OUTPUT_DIR})")
            
            # ingest 함수 호출 (기본값으로 incremental=True, purge=False 사용)
            await ingest_main(
                incremental=True, 
                purge=False, 
                process_attachments=True, 
                force_rebuild=False
            )
            
            logger.info("임베딩 및 Qdrant 저장 완료")
            
            # Qdrant 저장 성공 여부 검증
            logger.info("\n📊 Qdrant 저장 검증 중...")
            try:
                from core.vectordb import QdrantAdapter
                
                # documents 컬렉션 확인
                vector_db = QdrantAdapter(collection_name="documents")
                info = vector_db.get_collection_info()
                
                if "error" not in info:
                    points_count = info.get("points_count", 0)
                    logger.info(f"✅ 'documents' 컬렉션에 {points_count:,}개 포인트 저장 확인")
                    
                    if points_count > 0:
                        logger.info("🎉 전체 워크플로우 성공: 데이터 수집 → 임베딩 → Qdrant 저장까지 완료!")
                    else:
                        logger.warning("⚠️ 데이터가 Qdrant에 저장되지 않았습니다. 로그를 확인하세요.")
                else:
                    logger.error(f"❌ Qdrant 컬렉션 확인 실패: {info['error']}")
                    
            except Exception as ve:
                logger.error(f"❌ Qdrant 저장 검증 중 오류: {ve}")
                
        except Exception as e:
            logger.error(f"임베딩 및 Qdrant 저장 중 오류 발생: {e}")
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
    """빠른 테스트 (100개 티켓만 수집, 후처리 및 Qdrant 저장까지 전체 워크플로우 실행)"""
    logger.info("=== 빠른 테스트 모드 ===")
    OUTPUT_DIR = str(Path(__file__).parent / "freshdesk_test_data")  # backend/freshdesk/freshdesk_test_data
    try:
        # 1단계: 티켓 데이터 수집
        logger.info("\n1단계: 티켓 데이터 수집 시작 (테스트)")
        async with OptimizedFreshdeskFetcher(OUTPUT_DIR) as fetcher:
            stats = await fetcher.collect_all_tickets(
                start_date="2024-01-01",
                max_tickets=100,
                include_conversations=True,  # 모든 경우 대화 내역 포함
                include_attachments=True     # 모든 경우 첨부파일 포함
            )
        logger.info(f"수집 완료: {stats}")

        # 2단계: 데이터 후처리
        logger.info("\n2단계: 데이터 후처리 시작 (테스트)")
        await process_collected_data(OUTPUT_DIR)

        # 3단계: 임베딩 및 Qdrant 저장
        logger.info("\n3단계: 임베딩 및 Qdrant 저장 시작 (테스트)")
        try:
            # 이미 import된 ingest_main 함수 사용
            logger.info(f"수집된 데이터를 Qdrant에 저장 중... (테스트, 디렉토리: {OUTPUT_DIR})")
            
            # ingest 함수 호출 (테스트 모드에서는 로컬 데이터 사용 및 purge=True로 설정)
            await ingest_main(
                incremental=False, 
                purge=True, 
                process_attachments=True, 
                force_rebuild=False,
                local_data_dir=OUTPUT_DIR  # 🆕 로컬 데이터 디렉토리 전달
            )
            
            logger.info("임베딩 및 Qdrant 저장 완료 (테스트)")
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


def parse_args():
    """커맨드 라인 인자 파싱"""
    parser = argparse.ArgumentParser(description="Freshdesk 대용량 티켓 수집기")
    
    # 주요 작업 모드 그룹
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--full-collection", action="store_true", help="전체 수집 실행")
    mode_group.add_argument("--quick-test", action="store_true", help="빠른 테스트(100건) 실행")
    mode_group.add_argument("--resume", action="store_true", help="중단된 수집 재개")
    
    # 벡터DB 초기화 관련 옵션
    parser.add_argument("--reset-vectordb", action="store_true", help="전체 수집 시작 전 벡터DB 초기화")
    parser.add_argument("--no-backup", action="store_true", help="초기화 시 백업 생성 비활성화")
    parser.add_argument("--force", action="store_true", help="확인 없이 자동 초기화 (CI/CD용)")
    
    return parser.parse_args()


if __name__ == "__main__":
    # 커맨드 라인 인자 파싱
    args = parse_args()
    
    # 명령행 인자가 지정된 경우
    if args.full_collection or args.quick_test or args.resume:
        if args.full_collection:
            asyncio.run(full_collection_workflow(
                reset_vectordb=args.reset_vectordb, 
                create_backup=not args.no_backup, 
                skip_confirmation=args.force
            ))
        elif args.quick_test:
            asyncio.run(quick_test())
        elif args.resume:
            asyncio.run(resume_collection())
    else:
        # 인자가 없는 경우 기존 인터랙티브 모드 실행
        print("Freshdesk 대용량 티켓 수집기")
        print("=============================")
        print("1. 전체 수집 (무제한)")
        print("2. 빠른 테스트 (100건)")
        print("3. 중단된 수집 재개")
        print("4. 종료")
        
        while True:
            try:
                choice = input("\n선택하세요 (1-4): ").strip()
                
                if choice == "1":
                    # 벡터DB 초기화 여부 묻기
                    reset_db = input("벡터DB를 초기화하시겠습니까? (yes/no, 기본값: no): ").strip().lower()
                    reset_vectordb = reset_db in ["yes", "y"]
                    
                    if reset_vectordb:
                        # 백업 생성 여부 묻기
                        create_backup = input("초기화 전 백업을 생성하시겠습니까? (yes/no, 기본값: yes): ").strip().lower()
                        create_backup = create_backup != "no" and create_backup != "n"  # 기본값 yes
                        
                        asyncio.run(full_collection_workflow(reset_vectordb=True, create_backup=create_backup))
                    else:
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
