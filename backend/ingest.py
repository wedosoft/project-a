"""
데이터 수집 및 저장 모듈

이 모듈은 Freshdesk에서 티켓과 지식베이스 문서를 가져와 임베딩한 후,
ChromaDB 벡터 데이터베이스에 저장하는 기능을 제공합니다.

프로젝트 규칙 및 가이드라인: /PROJECT_RULES.md 참조
"""
import asyncio
import logging
import time
import sys
import shutil
import os
from datetime import datetime
from fetcher import fetch_tickets, fetch_kb_articles
from embedder import embed_documents, process_documents
from attachment_processor import process_attachments as process_attachment_files
import chromadb
from typing import List, Dict, Any

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime%s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

COLLECTION_NAME = "docs"
PROCESS_ATTACHMENTS = True  # 첨부파일 처리 여부 설정
DB_PATH = "./chroma_db"  # 데이터베이스 경로

def backup_database():
    """ChromaDB 데이터베이스를 백업합니다."""
    if os.path.exists(DB_PATH) and os.path.isdir(DB_PATH):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"{DB_PATH}_backup_{timestamp}"
        try:
            shutil.copytree(DB_PATH, backup_path)
            logger.info(f"데이터베이스 백업 완료: {backup_path}")
            return True
        except Exception as e:
            logger.error(f"데이터베이스 백업 실패: {e}")
            return False
    return False

def verify_database_integrity():
    """ChromaDB 데이터베이스의 무결성을 검증합니다."""
    try:
        client = chromadb.PersistentClient(path=DB_PATH)
        collections = client.list_collections()
        
        if not collections:
            logger.warning("데이터베이스에 컬렉션이 없습니다.")
            return False
            
        for collection in collections:
            count = collection.count()
            logger.info(f"컬렉션 '{collection.name}': {count}개 문서")
            
            # 문서 수 확인
            if count == 0:
                logger.warning(f"컬렉션 '{collection.name}'에 문서가 없습니다.")
                continue
                
            # 샘플 쿼리 실행
            try:
                result = collection.query(query_texts=["test"], n_results=1)
                if not result or not result["ids"]:
                    logger.warning(f"컬렉션 '{collection.name}'에 쿼리 실패")
                    return False
            except Exception as e:
                logger.error(f"쿼리 테스트 실패: {e}")
                return False
                
        return True
    except Exception as e:
        logger.error(f"데이터베이스 무결성 검증 실패: {e}")
        return False

async def ingest(incremental: bool = True, purge: bool = False, process_attachments: bool = PROCESS_ATTACHMENTS, force_rebuild: bool = False) -> None:
    """
    Freshdesk 티켓과 지식베이스 문서를 임베딩 후 ChromaDB에 저장합니다.
    
    Args:
        incremental: 증분 업데이트 모드 여부 (기본값: True)
                    True일 경우 기존 문서는 유지하고 새 문서만 추가합니다.
        purge: 기존 데이터 삭제 여부 (기본값: False)
               True일 경우 기존 데이터를 모두 삭제하고 새로 저장합니다.
        process_attachments: 첨부파일 처리 여부 (기본값: PROCESS_ATTACHMENTS)
                          True일 경우 첨부파일을 다운로드하여 텍스트 추출
        force_rebuild: 데이터베이스 강제 재구축 여부 (기본값: False)
                      True일 경우 기존 데이터베이스를 백업하고 새로 구축합니다.
    """
    start_time = time.time()
    logger.info("데이터 수집 프로세스 시작")
    
    try:
        # 데이터베이스 강제 재구축 옵션 처리
        if force_rebuild:
            logger.warning("데이터베이스 강제 재구축 모드")
            backup_database()
            if os.path.exists(DB_PATH):
                logger.info("기존 데이터베이스 삭제 중...")
                shutil.rmtree(DB_PATH, ignore_errors=True)
            incremental = False
            purge = False
        
        # ChromaDB 클라이언트 초기화
        chroma_client = chromadb.PersistentClient(path=DB_PATH)
        
        # 컬렉션이 없으면 생성
        collection_names = [c.name for c in chroma_client.list_collections()]
        if COLLECTION_NAME not in collection_names:
            logger.info(f"새 컬렉션 '{COLLECTION_NAME}' 생성 중...")
            collection = chroma_client.create_collection(COLLECTION_NAME)
            incremental = False  # 새 컬렉션이므로 증분 업데이트가 아님
        else:
            collection = chroma_client.get_collection(COLLECTION_NAME)
            
            # 기존 컬렉션 정보 로깅
            existing_count = collection.count()
            logger.info(f"기존 컬렉션에 {existing_count}개 문서가 있습니다.")
            
            # 무결성 검증 - 문서 수가 0개인데 DB 폴더가 큰 경우 처리
            if existing_count == 0 and os.path.exists(DB_PATH):
                folder_size = sum(os.path.getsize(os.path.join(dirpath, filename)) 
                               for dirpath, _, filenames in os.walk(DB_PATH)
                               for filename in filenames)
                folder_size_mb = folder_size / (1024 * 1024)
                
                if folder_size_mb > 10:  # 10MB 이상인데 문서가 없으면 불일치로 판단
                    logger.warning(f"데이터베이스 불일치 감지: 폴더 크기 {folder_size_mb:.2f}MB인데 문서 수 0개")
                    backup_success = backup_database()
                    if backup_success:
                        logger.info("기존 데이터베이스 삭제 후 재생성 중...")
                        shutil.rmtree(DB_PATH, ignore_errors=True)
                        chroma_client = chromadb.PersistentClient(path=DB_PATH)
                        collection = chroma_client.create_collection(COLLECTION_NAME)
                        incremental = False
                        purge = False
            
            # purge 옵션이 True인 경우 기존 데이터 삭제
            if purge:
                logger.info("기존 데이터 삭제 중...")
                # 모든 문서 ID 가져오기
                all_ids = collection.get()["ids"]
                if all_ids:
                    logger.info(f"{len(all_ids)}개 문서 삭제 중...")
                    # 배치로 삭제 처리
                    batch_size = 100
                    for i in range(0, len(all_ids), batch_size):
                        batch = all_ids[i:i+batch_size]
                        collection.delete(ids=batch)
                incremental = False  # 데이터를 삭제했으므로 증분 업데이트가 아님
        
        # 1. 데이터 수집
        logger.info("Freshdesk 데이터 수집 중...")
        
        # 티켓과 지식베이스 문서 동시에 가져오기
        tickets_task = asyncio.create_task(fetch_tickets())
        articles_task = asyncio.create_task(fetch_kb_articles())
        
        # 두 작업 완료 대기
        tickets, articles = await asyncio.gather(tickets_task, articles_task)
        
        if not tickets and not articles:
            logger.warning("Freshdesk에서 가져온 데이터가 없습니다.")
            return
            
        # 2. 삭제된 문서 감지 및 처리 (증분 업데이트 모드에서만)
        if incremental:
            # 기존 문서 ID 목록 가져오기
            existing_ids = set(collection.get()["ids"])
            logger.info(f"기존 문서 ID {len(existing_ids)}개 확인됨")
            
            # 현재 Freshdesk에 존재하는 문서 ID 목록 생성
            current_ids = set()
            for t in tickets:
                # 티켓 ID와 청크 ID 모두 포함
                base_id = f"ticket-{t.get('id')}"
                current_ids.add(base_id)
                
                # 기존에 청킹된 문서도 고려
                for existing_id in existing_ids:
                    if existing_id.startswith(f"{base_id}_chunk_"):
                        current_ids.add(existing_id)
                
            for a in articles:
                # 지식베이스 ID와 청크 ID 모두 포함
                base_id = f"kb-{a.get('id')}"
                current_ids.add(base_id)
                
                # 기존에 청킹된 문서도 고려
                for existing_id in existing_ids:
                    if existing_id.startswith(f"{base_id}_chunk_"):
                        current_ids.add(existing_id)
            
            # 삭제된 문서 식별 (기존에는 있었지만 현재는 없는 ID)
            deleted_ids = existing_ids - current_ids
            
            if deleted_ids:
                logger.info(f"{len(deleted_ids)}개 삭제된 문서 감지됨")
                # 삭제된 문서 제거
                deleted_ids_list = list(deleted_ids)
                # 배치로 처리 (ChromaDB 성능 향상을 위해)
                batch_size = 100
                for i in range(0, len(deleted_ids_list), batch_size):
                    batch = deleted_ids_list[i:i+batch_size]
                    logger.info(f"삭제된 문서 제거 중... ({i+1}~{i+len(batch)}/{len(deleted_ids_list)})")
                    collection.delete(ids=batch)
                logger.info(f"{len(deleted_ids)}개 삭제된 문서가 데이터베이스에서 제거됨")
        
        # 3. 문서 준비
        all_documents = []
        
        # 기존 문서 ID 목록 가져오기 (삭제 후 갱신)
        existing_ids = set()
        if incremental:
            existing_ids = set(collection.get()["ids"])
            logger.info(f"현재 문서 ID {len(existing_ids)}개 확인됨 (삭제 처리 후)")
        
        logger.info("티켓 데이터 처리 중...")
        for t in tickets:
            doc_id = f"ticket-{t.get('id')}"
            
            # 증분 업데이트 모드에서는 이미 있는 문서는 건너뜀
            if incremental and doc_id in existing_ids:
                continue
                
            # 첨부파일 처리
            all_attachments = t.get("all_attachments", [])
            if process_attachments and all_attachments:
                logger.info(f"티켓 {t.get('id')}의 첨부파일 {len(all_attachments)}개 처리 중...")
                processed_attachments = await process_attachment_files(all_attachments)
                t["processed_attachments"] = processed_attachments
            else:
                t["processed_attachments"] = []
                
            # 기본 티켓 정보 처리
            ticket_content = []
            ticket_content.append(f"제목: {t.get('subject', '')}")
            ticket_content.append(f"설명: {t.get('description', '')}")
            
            # 대화 내역 추가
            conversations = t.get("conversations", [])
            if conversations:
                ticket_content.append("\n===== 대화 내역 =====")
                for i, conv in enumerate(conversations):
                    ticket_content.append(f"[대화 {i+1}] - {conv.get('created_at', '')}")
                    ticket_content.append(f"작성자: {conv.get('user_id', '')} ({conv.get('source', '')})")
                    ticket_content.append(f"내용: {conv.get('body', '')}")
                    
                    # 대화의 첨부파일 정보
                    attachments = conv.get("attachments", [])
                    if attachments:
                        ticket_content.append("첨부파일:")
                        for att in attachments:
                            ticket_content.append(f"  - {att.get('name', '')} ({att.get('content_type', '')})")
            
            # 첨부파일 정보 및 추출된 텍스트 추가
            processed_attachments = t.get("processed_attachments", [])
            if processed_attachments:
                ticket_content.append("\n===== 첨부파일 내용 =====")
                for att in processed_attachments:
                    if att.get("processed", False) and att.get("extracted_text"):
                        ticket_content.append(f"파일: {att.get('name', '')}")
                        ticket_content.append(f"추출된 텍스트: {att.get('extracted_text', '')}")
            
            doc_text = "\n".join(ticket_content)
            
            if doc_text.strip():  # 빈 문서 제외
                all_documents.append({
                    "id": doc_id,
                    "text": doc_text,
                    "metadata": {
                        "type": "ticket", 
                        "id": t.get("id"),
                        "created_at": t.get("created_at"),
                        "status": t.get("status"),
                        "priority": t.get("priority"),
                        "has_attachments": len(all_attachments) > 0,
                        "has_conversations": len(conversations) > 0,
                        "processed_attachments": len(processed_attachments) > 0
                    }
                })
        
        logger.info("지식베이스 문서 처리 중...")
        for a in articles:
            doc_id = f"kb-{a.get('id')}"
            
            # 증분 업데이트 모드에서는 이미 있는 문서는 건너뜀
            if incremental and doc_id in existing_ids:
                continue
            
            # 첨부파일 처리
            attachments = a.get("attachments", [])
            if process_attachments and attachments:
                logger.info(f"지식베이스 문서 {a.get('id')}의 첨부파일 {len(attachments)}개 처리 중...")
                processed_attachments = await process_attachment_files(attachments)
                a["processed_attachments"] = processed_attachments
            else:
                a["processed_attachments"] = []
            
            # 문서 내용 준비
            article_content = []
            article_content.append(f"제목: {a.get('title', '')}")
            article_content.append(f"설명: {a.get('description', '')}")
            
            # 추출된 첨부파일 내용 추가
            processed_attachments = a.get("processed_attachments", [])
            if processed_attachments:
                article_content.append("\n===== 첨부파일 내용 =====")
                for att in processed_attachments:
                    if att.get("processed", False) and att.get("extracted_text"):
                        article_content.append(f"파일: {att.get('name', '')}")
                        article_content.append(f"추출된 텍스트: {att.get('extracted_text', '')}")
            
            doc_text = "\n".join(article_content)
                
            if doc_text.strip():  # 빈 문서 제외
                all_documents.append({
                    "id": doc_id,
                    "text": doc_text,
                    "metadata": {
                        "type": "kb", 
                        "id": a.get("id"),
                        "folder_id": a.get("folder_id"),
                        "category_id": a.get("category_id"),
                        "status": a.get("status"),
                        "has_attachments": len(attachments) > 0,
                        "processed_attachments": len(processed_attachments) > 0
                    }
                })
        
        if not all_documents and deleted_ids:
            logger.info("새 문서 추가 없이 삭제된 문서만 처리됨")
            elapsed_time = time.time() - start_time
            logger.info(f"데이터 수집 완료. {len(deleted_ids)}개 문서 삭제됨 (소요 시간: {elapsed_time:.2f}초)")
            return
        elif not all_documents:
            logger.info("처리할 새 문서가 없습니다.")
            return
        
        logger.info(f"총 {len(all_documents)}개 신규 문서 처리 중...")
        
        # 4. 문서 청킹 처리 - 긴 문서를 여러 청크로 나눔
        logger.info(f"총 {len(all_documents)}개 문서 청킹 처리 중...")
        processed_docs = process_documents(all_documents)
        logger.info(f"청킹 처리 후 {len(processed_docs)}개 문서로 분할됨")
        
        # 5. ChromaDB 저장 준비
        docs = [doc["text"] for doc in processed_docs]
        metadatas = [doc["metadata"] for doc in processed_docs]
        ids = [doc["id"] for doc in processed_docs]
            
        # 6. 임베딩
        logger.info(f"총 {len(docs)}개 문서 임베딩 시작...")
        
        # 대량의 문서를 적절한 크기로 나누어 임베딩 - 메모리 효율성 향상
        batch_size = 50
        all_embeddings = []
        
        for i in range(0, len(docs), batch_size):
            batch_docs = docs[i:i+batch_size]
            logger.info(f"문서 배치 임베딩 중... ({i+1}~{i+len(batch_docs)}/{len(docs)})")
            batch_embeddings = embed_documents(batch_docs)
            all_embeddings.extend(batch_embeddings)
            
        # 7. ChromaDB 저장
        logger.info("ChromaDB에 문서 저장 중...")
        
        # 배치 단위로 upsert 수행 - 메모리 효율성 향상
        for i in range(0, len(docs), batch_size):
            end_idx = min(i + batch_size, len(docs))
            batch_docs = docs[i:end_idx]
            batch_embeddings = all_embeddings[i:end_idx]
            batch_metadatas = metadatas[i:end_idx]
            batch_ids = ids[i:end_idx]
            
            logger.info(f"문서 배치 저장 중... ({i+1}~{end_idx}/{len(docs)})")
            collection.upsert(
                documents=batch_docs,
                embeddings=batch_embeddings,
                metadatas=batch_metadatas,
                ids=batch_ids
            )
        
        elapsed_time = time.time() - start_time
        deleted_count = len(deleted_ids) if 'deleted_ids' in locals() else 0
        logger.info(f"데이터 수집 완료. 총 {len(docs)}개 문서 임베딩 및 저장, {deleted_count}개 문서 삭제 (소요 시간: {elapsed_time:.2f}초)")
        
    except Exception as e:
        logger.error(f"데이터 수집 중 오류 발생: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    try:
        import argparse
        
        parser = argparse.ArgumentParser(description='Freshdesk 데이터 수집 및 임베딩')
        parser.add_argument('--full', action='store_true', help='전체 데이터 다시 수집 (기존 데이터 유지)')
        parser.add_argument('--purge', action='store_true', help='기존 데이터 삭제 후 전체 다시 수집')
        parser.add_argument('--no-attachments', action='store_true', help='첨부파일 처리 비활성화')
        parser.add_argument('--rebuild', action='store_true', help='데이터베이스 강제 재구축 (백업 후 처음부터 새로 시작)')
        parser.add_argument('--verify', action='store_true', help='데이터베이스 무결성만 검증하고 종료')
        args = parser.parse_args()
        
        # 무결성 검증 모드
        if args.verify:
            logger.info("데이터베이스 무결성 검증 모드")
            is_valid = verify_database_integrity()
            if is_valid:
                logger.info("데이터베이스 무결성 검증 성공")
                sys.exit(0)
            else:
                logger.error("데이터베이스 무결성 검증 실패")
                sys.exit(1)
        
        # 명령줄 인자에 따라 실행 모드 결정
        incremental_mode = not (args.full or args.purge or args.rebuild)
        purge_mode = args.purge
        rebuild_mode = args.rebuild
        process_attachments = not args.no_attachments
        
        if rebuild_mode:
            logger.info("데이터베이스 강제 재구축 모드")
        elif purge_mode:
            logger.info("기존 데이터 삭제 후 전체 다시 수집 모드")
        elif incremental_mode:
            logger.info("증분 업데이트 모드 (신규 문서만 추가)")
        else:
            logger.info("전체 데이터 다시 수집 모드 (기존 데이터 유지)")
            
        if process_attachments:
            logger.info("첨부파일 처리 활성화됨")
        else:
            logger.info("첨부파일 처리 비활성화됨")
        
        asyncio.run(ingest(incremental=incremental_mode, purge=purge_mode, 
                          process_attachments=process_attachments, force_rebuild=rebuild_mode))
    except KeyboardInterrupt:
        logger.info("사용자에 의해 프로세스가 중단되었습니다.")
    except Exception as e:
        logger.error(f"예상치 못한 오류 발생: {e}", exc_info=True)
        exit(1)