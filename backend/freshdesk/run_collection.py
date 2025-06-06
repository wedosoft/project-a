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

# 환경변수 로드
import os

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(BACKEND_ROOT) / '.env')

# 공통 로깅 모듈 사용
from api.ingest import ingest as ingest_main
from core.logger import get_logger, setup_logging
from data.data_processor import process_collected_data

from freshdesk.optimized_fetcher import OptimizedFreshdeskFetcher

# 로깅 설정 초기화 (이미 core/logger.py에서 설정됨)
setup_logging()

logger = get_logger(__name__)


async def full_collection_workflow(
    reset_vectordb: bool = False, 
    create_backup: bool = True, 
    skip_confirmation: bool = False,
    collect_raw_details: bool = True,  # 기본값을 True로 변경
    collect_raw_conversations: bool = True,  # 기본값을 True로 변경
    collect_raw_kb: bool = True  # 기본값을 True로 변경
):
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
        
        # 적응형 속도 조절 설정도 가져오기 시도
        try:
            from large_scale_config import ADAPTIVE_RATE as CONFIG_ADAPTIVE_RATE
            ADAPTIVE_RATE = CONFIG_ADAPTIVE_RATE
        except (ImportError, AttributeError):
            pass  # 기본값 사용
            
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
    # RAW 데이터 수집 설정 로깅
    logger.info(f"RAW 티켓 상세정보 수집: {'활성화' if collect_raw_details else '비활성화'}")
    logger.info(f"RAW 대화내역 수집: {'활성화' if collect_raw_conversations else '비활성화'}")
    logger.info(f"RAW 지식베이스 수집: {'활성화' if collect_raw_kb else '비활성화'}")
    if RESET_VECTORDB:
        logger.info(f"백업 생성: {CREATE_BACKUP}")
        logger.info(f"확인 필요: {CONFIRM_REQUIRED}")
        
    start_time = datetime.now()
    
    # 벡터DB 초기화 옵션이 활성화된 경우
    if RESET_VECTORDB:
        from core.vectordb import COLLECTION_NAME, QdrantAdapter
        
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
        
        # 테스트 로직과 동일하게 단순화
        async with OptimizedFreshdeskFetcher(OUTPUT_DIR) as fetcher:
            stats = await fetcher.collect_all_tickets(
                start_date=START_DATE,
                end_date=None,  # 현재까지
                include_conversations=INCLUDE_CONVERSATIONS,
                include_attachments=INCLUDE_ATTACHMENTS,
                max_tickets=MAX_TICKETS,  # None = 무제한
                max_kb_articles=MAX_TICKETS,  # 지식베이스도 동일하게 제한(무제한)
                collect_raw_details=collect_raw_details,  # 티켓 상세정보 raw 데이터 수집
                collect_raw_conversations=collect_raw_conversations,  # 대화내역 raw 데이터 수집
                collect_raw_kb=collect_raw_kb  # 지식베이스 raw 데이터 수집
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
            
            # ingest 함수 호출 - local_data_dir을 전달하여 수집된 데이터 사용
            await ingest_main(
                incremental=False,  # 테스트 모드에서는 증분 처리하지 않음
                purge=True,  # 테스트 데이터 초기화
                process_attachments=True, 
                force_rebuild=True,  # 임베딩 데이터 새로 생성
                local_data_dir=OUTPUT_DIR,  # 수집된 로컬 데이터 디렉토리 전달
                include_kb=collect_raw_kb  # 지식베이스 데이터도 함께 처리
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


async def quick_test(
    collect_raw_details: bool = True,  # 기본값을 True로 변경
    collect_raw_conversations: bool = True,  # 기본값을 True로 변경
    collect_raw_kb: bool = True  # 기본값을 True로 변경하여 지식베이스 데이터도 수집
):
    """빠른 테스트 (100개 티켓만 수집, 후처리 및 Qdrant 저장까지 전체 워크플로우 실행)"""
    logger.info("=== 빠른 테스트 모드 ===")
    OUTPUT_DIR = str(Path(__file__).parent.parent / "freshdesk_test_data")  # backend/freshdesk_test_data
    try:
        # 1단계: 티켓 데이터 수집
        logger.info("\n1단계: 티켓 데이터 수집 시작 (테스트)")
        async with OptimizedFreshdeskFetcher(OUTPUT_DIR) as fetcher:
            stats = await fetcher.collect_all_tickets(
                start_date="2024-01-01",
                max_tickets=100,
                max_kb_articles=100,  # 지식베이스도 100건으로 제한
                include_conversations=True,  # 모든 경우 대화 내역 포함
                include_attachments=True,    # 모든 경우 첨부파일 포함
                collect_raw_details=collect_raw_details,  # 티켓 상세정보 raw 데이터 수집
                collect_raw_conversations=collect_raw_conversations,  # 대화내역 raw 데이터 수집
                collect_raw_kb=collect_raw_kb  # 지식베이스 raw 데이터 수집
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
    
    # RAW 데이터 수집 옵션 묻기
    print("\nRAW 데이터 수집 옵션 (수집 재개)")
    collect_raw_details_input = input("티켓 상세정보 원본 데이터를 수집하시겠습니까? (yes/no, 기본값: yes): ").strip().lower()
    collect_raw_details = collect_raw_details_input not in ["no", "n"]  # 기본값 yes로 변경
    
    collect_raw_conversations_input = input("티켓 대화내역 원본 데이터를 수집하시겠습니까? (yes/no, 기본값: yes): ").strip().lower()
    collect_raw_conversations = collect_raw_conversations_input not in ["no", "n"]  # 기본값 yes로 변경
    
    collect_raw_kb_input = input("지식베이스 원본 데이터를 수집하시겠습니까? (yes/no, 기본값: yes): ").strip().lower()
    collect_raw_kb = collect_raw_kb_input not in ["no", "n"]  # 기본값 yes로 변경
    
    # 수집 재개 - raw 데이터 수집 옵션 전달
    await full_collection_workflow(
        collect_raw_details=collect_raw_details,
        collect_raw_conversations=collect_raw_conversations,
        collect_raw_kb=collect_raw_kb
    )


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
    
    # RAW 데이터 수집 관련 옵션
    raw_group = parser.add_argument_group("Raw 데이터 수집 옵션")
    raw_group.add_argument("--raw-details", action="store_true", help="티켓 상세정보 원본 데이터 수집")
    raw_group.add_argument("--raw-conversations", action="store_true", help="티켓 대화내역 원본 데이터 수집")
    raw_group.add_argument("--raw-kb", action="store_true", help="지식베이스 원본 데이터 수집")
    raw_group.add_argument("--raw-all", action="store_true", help="모든 원본 데이터 수집 활성화 (위 3가지 옵션 모두 활성화)")
    
    return parser.parse_args()


if __name__ == "__main__":
    # 커맨드 라인 인자 파싱
    args = parse_args()
    
    # 명령행 인자가 지정된 경우
    if args.full_collection or args.quick_test or args.resume:
        # raw 데이터 수집 옵션 처리
        # 명시적으로 raw 데이터 플래그가 지정되지 않은 경우 기본값 True 사용
        raw_flags_specified = any([args.raw_details, args.raw_conversations, args.raw_kb, args.raw_all])
        
        if raw_flags_specified:
            # 명시적 플래그가 있는 경우 기존 로직 사용
            collect_raw_details = args.raw_details or args.raw_all
            collect_raw_conversations = args.raw_conversations or args.raw_all
            collect_raw_kb = args.raw_kb or args.raw_all
        else:
            # 명시적 플래그가 없는 경우 기본값 True 사용 (함수 기본값과 일치)
            collect_raw_details = True
            collect_raw_conversations = True
            collect_raw_kb = True
            logger.info("RAW 데이터 수집 플래그가 지정되지 않아 기본값(모두 활성화)을 사용합니다.")
        
        if args.full_collection:
            asyncio.run(full_collection_workflow(
                reset_vectordb=args.reset_vectordb, 
                create_backup=not args.no_backup, 
                skip_confirmation=args.force,
                collect_raw_details=collect_raw_details,
                collect_raw_conversations=collect_raw_conversations,
                collect_raw_kb=collect_raw_kb
            ))
        elif args.quick_test:
            # quick_test에도 raw 데이터 수집 옵션 전달
            asyncio.run(quick_test(
                collect_raw_details=collect_raw_details,
                collect_raw_conversations=collect_raw_conversations,
                collect_raw_kb=collect_raw_kb
            ))
        elif args.resume:
            # resume 모드에서도 raw 데이터 수집 옵션 전달
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
                    
                    create_backup = True
                    if reset_vectordb:
                        # 백업 생성 여부 묻기
                        create_backup_input = input("초기화 전 백업을 생성하시겠습니까? (yes/no, 기본값: yes): ").strip().lower()
                        create_backup = create_backup_input != "no" and create_backup_input != "n"  # 기본값 yes
                    
                    # RAW 데이터 수집 옵션 묻기
                    print("\nRAW 데이터 수집 옵션 (임베딩 실패 시 재수집 방지)")
                    collect_raw_details_input = input("티켓 상세정보 원본 데이터를 수집하시겠습니까? (yes/no, 기본값: no): ").strip().lower()
                    collect_raw_details = collect_raw_details_input in ["yes", "y"]
                    
                    collect_raw_conversations_input = input("티켓 대화내역 원본 데이터를 수집하시겠습니까? (yes/no, 기본값: yes): ").strip().lower()
                    collect_raw_conversations = collect_raw_conversations_input not in ["no", "n"]  # 기본값 yes로 변경
                    
                    collect_raw_kb_input = input("지식베이스 원본 데이터를 수집하시겠습니까? (yes/no, 기본값: yes): ").strip().lower()
                    collect_raw_kb = collect_raw_kb_input not in ["no", "n"]  # 기본값 yes로 변경
                    
                    # 모든 옵션이 no인데 확인 메시지
                    if not any([collect_raw_details, collect_raw_conversations, collect_raw_kb]):
                        confirm = input("모든 RAW 데이터 수집이 비활성화됩니다. 이대로 진행하시겠습니까? (yes/no, 기본값: yes): ").strip().lower()
                        if confirm in ["no", "n"]:
                            # 모든 옵션 활성화
                            all_raw = input("모든 RAW 데이터 수집을 활성화하시겠습니까? (yes/no, 기본값: no): ").strip().lower()
                            if all_raw in ["yes", "y"]:
                                collect_raw_details = True
                                collect_raw_conversations = True
                                collect_raw_kb = True
                                print("모든 RAW 데이터 수집 옵션이 활성화되었습니다.")
                    
                    asyncio.run(full_collection_workflow(
                        reset_vectordb=reset_vectordb, 
                        create_backup=create_backup,
                        collect_raw_details=collect_raw_details,
                        collect_raw_conversations=collect_raw_conversations,
                        collect_raw_kb=collect_raw_kb
                    ))
                    break
                elif choice == "2":
                    # 빠른 테스트에도 RAW 데이터 수집 옵션 묻기
                    print("\nRAW 데이터 수집 옵션 (테스트용)")
                    collect_raw_details_input = input("티켓 상세정보 원본 데이터를 수집하시겠습니까? (yes/no, 기본값: yes): ").strip().lower()
                    collect_raw_details = collect_raw_details_input not in ["no", "n"]  # 기본값 yes로 변경
                    
                    collect_raw_conversations_input = input("티켓 대화내역 원본 데이터를 수집하시겠습니까? (yes/no, 기본값: yes): ").strip().lower()
                    collect_raw_conversations = collect_raw_conversations_input not in ["no", "n"]  # 기본값 yes로 변경
                    
                    collect_raw_kb_input = input("지식베이스 원본 데이터를 수집하시겠습니까? (yes/no, 기본값: yes): ").strip().lower()
                    collect_raw_kb = collect_raw_kb_input not in ["no", "n"]  # 기본값을 yes로 변경
                    
                    asyncio.run(quick_test(
                        collect_raw_details=collect_raw_details,
                        collect_raw_conversations=collect_raw_conversations,
                        collect_raw_kb=collect_raw_kb
                    ))
                    break
                elif choice == "3":
                    # resume_collection 함수 내에서 RAW 데이터 수집 옵션을 묻기 때문에 따로 처리할 필요 없음
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
