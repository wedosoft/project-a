"""
FAQ 로딩 스크립트

이 스크립트는 CSV 또는 JSON 형식의 FAQ 파일을 읽어 Qdrant 데이터베이스에 로드합니다.
FAQ 질문은 임베딩되어 저장되며, 답변 및 기타 메타데이터와 함께 FAQ 컬렉션에 저장됩니다.

사용 예시:
python scripts/load_faqs.py --file_path /path/to/your/faqs.csv --company_id your_company_id
python scripts/load_faqs.py --file_path /path/to/your/faqs.json --company_id your_company_id --file_type json

CSV 파일 형식:
question,answer,category,source_doc_id
"질문1","답변1","카테고리1","doc1"
"질문2","답변2","카테고리2","doc2"

JSON 파일 형식:
[
  {
    "question": "질문1",
    "answer": "답변1",
    "category": "카테고리1",
    "source_doc_id": "doc1"
  },
  {
    "question": "질문2",
    "answer": "답변2",
    "category": "카테고리2",
    "source_doc_id": "doc2"
  }
]

주의:
- `company_id`는 필수 인자입니다.
- CSV 파일은 UTF-8 인코딩이어야 합니다.
- JSON 파일은 객체 리스트 형태여야 합니다.
- 스크립트 실행 전에 Qdrant 서버가 실행 중이어야 하며,
  `backend` 디렉토리의 `vectordb.py`와 `embedder.py`가 올바르게 설정되어 있어야 합니다.
- `PYTHONPATH` 환경 변수에 `backend` 디렉토리의 부모 디렉토리가 포함되어 있어야
  `from backend.vectordb import QdrantAdapter` 와 같은 import가 가능합니다.
  예: export PYTHONPATH=$PYTHONPATH:/Users/alan/GitHub/project-a
"""
import argparse
import csv
import json
import logging
import os
import sys
from datetime import datetime
from typing import List, Dict, Any, Optional
import uuid

# 프로젝트 루트 경로를 sys.path에 추가하여 backend 모듈을 임포트할 수 있도록 함
# 현재 스크립트(scripts/load_faqs.py)의 부모 디렉토리(project-a)를 기준으로 backend 경로 설정
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.append(PROJECT_ROOT)

try:
    from backend.vectordb import QdrantAdapter, FAQ_COLLECTION_NAME
    from backend.embedder import embed_documents # embed_documents 함수 사용
    # from backend.main import FAQEntry # Pydantic 모델, 여기서는 dict로 처리
except ImportError as e:
    print(f"모듈 임포트 오류: {e}")
    print("PYTHONPATH 환경 변수에 프로젝트 루트 디렉토리가 올바르게 설정되었는지 확인하세요.")
    print(f"현재 sys.path: {sys.path}")
    sys.exit(1)

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def load_faqs_from_csv(file_path: str) -> List[Dict[str, Any]]:
    """CSV 파일에서 FAQ 데이터를 로드합니다."""
    faqs = []
    try:
        with open(file_path, mode='r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                faqs.append(dict(row))
        logger.info(f"'{file_path}'에서 {len(faqs)}개의 FAQ를 로드했습니다.")
    except FileNotFoundError:
        logger.error(f"파일을 찾을 수 없습니다: {file_path}")
        raise
    except Exception as e:
        logger.error(f"CSV 파일 로드 중 오류 발생: {e}")
        raise
    return faqs

def load_faqs_from_json(file_path: str) -> List[Dict[str, Any]]:
    """JSON 파일에서 FAQ 데이터를 로드합니다."""
    faqs = []
    try:
        with open(file_path, mode='r', encoding='utf-8') as file:
            faqs = json.load(file)
        logger.info(f"'{file_path}'에서 {len(faqs)}개의 FAQ를 로드했습니다.")
    except FileNotFoundError:
        logger.error(f"파일을 찾을 수 없습니다: {file_path}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"JSON 파일 파싱 중 오류 발생: {e}")
        raise
    except Exception as e:
        logger.error(f"JSON 파일 로드 중 오류 발생: {e}")
        raise
    return faqs

def validate_faq_data(faq_data: Dict[str, Any], company_id: str) -> Optional[Dict[str, Any]]:
    """
    개별 FAQ 데이터의 유효성을 검사하고 Qdrant에 저장할 형태로 변환합니다.
    필수 필드: question, answer
    """
    if not faq_data.get("question") or not faq_data.get("answer"):
        logger.warning(f"필수 필드(question, answer) 누락으로 FAQ 항목 건너뜀: {faq_data}")
        return None

    return {
        "id": faq_data.get("id") or str(uuid.uuid4()), # ID가 없으면 생성
        "question": faq_data["question"],
        "answer": faq_data["answer"],
        "category": faq_data.get("category"),
        "source_doc_id": faq_data.get("source_doc_id"),
        "company_id": company_id, # 인자로 받은 company_id 사용
        "last_updated": datetime.utcnow().isoformat(),
        # "embedding" 필드는 이 함수 이후에 추가됨
    }

def main():
    parser = argparse.ArgumentParser(description="FAQ 데이터를 Qdrant에 로드하는 스크립트")
    parser.add_argument("--file_path", type=str, required=True, help="FAQ 데이터 파일 경로 (CSV 또는 JSON)")
    parser.add_argument("--company_id", type=str, required=True, help="FAQ가 속한 회사 ID")
    parser.add_argument("--file_type", type=str, choices=['csv', 'json'], default='csv', help="파일 유형 (csv 또는 json, 기본값: csv)")
    # Qdrant 연결 정보는 환경 변수(QDRANT_HOST, QDRANT_PORT)를 사용하므로 인자에서 제외

    args = parser.parse_args()

    logger.info(f"FAQ 로딩 시작: 파일='{args.file_path}', 회사 ID='{args.company_id}', 파일 유형='{args.file_type}'")

    try:
        if args.file_type == 'csv':
            raw_faqs = load_faqs_from_csv(args.file_path)
        else: # json
            raw_faqs = load_faqs_from_json(args.file_path)
    except Exception:
        logger.error("FAQ 데이터 파일 로드에 실패하여 스크립트를 종료합니다.")
        sys.exit(1)

    if not raw_faqs:
        logger.info("로드할 FAQ 데이터가 없습니다.")
        sys.exit(0)

    # 데이터 유효성 검사 및 Qdrant 저장 형태로 변환
    validated_faqs_to_embed: List[Dict[str, Any]] = []
    questions_to_embed: List[str] = []

    for faq_item in raw_faqs:
        validated_item = validate_faq_data(faq_item, args.company_id)
        if validated_item:
            validated_faqs_to_embed.append(validated_item)
            questions_to_embed.append(validated_item["question"])

    if not validated_faqs_to_embed:
        logger.info("유효한 FAQ 데이터가 없어 임베딩 및 저장을 진행하지 않습니다.")
        sys.exit(0)

    # 질문 임베딩
    logger.info(f"{len(questions_to_embed)}개의 질문에 대한 임베딩을 시작합니다...")
    try:
        question_embeddings = embed_documents(questions_to_embed)
        logger.info("질문 임베딩 완료.")
    except Exception as e:
        logger.error(f"질문 임베딩 중 오류 발생: {e}")
        sys.exit(1)

    # 임베딩 결과를 FAQ 데이터에 추가
    faqs_for_qdrant: List[Dict[str, Any]] = []
    for faq_data, embedding in zip(validated_faqs_to_embed, question_embeddings):
        faq_data["embedding"] = embedding
        faqs_for_qdrant.append(faq_data)

    # Qdrant 어댑터 초기화 (FAQ 컬렉션 사용 명시)
    try:
        # QdrantAdapter 생성 시 collection_name을 FAQ_COLLECTION_NAME으로 지정해야 하지만,
        # 현재 QdrantAdapter는 __init__에서 기본 컬렉션과 FAQ 컬렉션을 모두 _ensure_collection_exists로 생성하므로
        # 별도의 FAQ용 어댑터 인스턴스화는 필요하지 않음.
        # add_faq_entries 메서드가 내부적으로 FAQ_COLLECTION_NAME을 사용함.
        qdrant_adapter = QdrantAdapter() # 기본 문서 컬렉션으로 초기화되지만, FAQ 메서드는 FAQ 컬렉션을 타겟함
        logger.info("Qdrant 어댑터 초기화 완료.")
    except Exception as e:
        logger.error(f"Qdrant 어댑터 초기화 실패: {e}")
        sys.exit(1)

    # Qdrant에 FAQ 데이터 추가/업데이트
    logger.info(f"{len(faqs_for_qdrant)}개의 FAQ 항목을 Qdrant에 추가/업데이트합니다...")
    try:
        success = qdrant_adapter.add_faq_entries(faqs_for_qdrant)
        if success:
            logger.info("Qdrant에 FAQ 데이터 추가/업데이트 완료.")
        else:
            logger.error("Qdrant에 FAQ 데이터 추가/업데이트 실패.")
            sys.exit(1)
    except Exception as e:
        logger.error(f"Qdrant에 FAQ 데이터 저장 중 오류 발생: {e}")
        sys.exit(1)

    logger.info("FAQ 로딩 스크립트 실행 완료.")

if __name__ == "__main__":
    # 스크립트 실행 예시 (실제 실행 시에는 터미널에서 인자와 함께 호출)
    # main()

    # 로컬 테스트용 예시 (실제 사용 시 주석 처리 또는 삭제)
    # 다음은 스크립트를 직접 실행하여 테스트할 때 사용할 수 있는 코드입니다.
    # 테스트용 CSV/JSON 파일을 생성하고 아래 경로를 맞게 수정해야 합니다.
    # if PROJECT_ROOT not in sys.path:
    #     sys.path.append(PROJECT_ROOT)
    #
    # # 테스트용 임시 FAQ 데이터 파일 생성 (예시)
    # test_csv_file = os.path.join(SCRIPT_DIR, "test_faqs.csv")
    # test_json_file = os.path.join(SCRIPT_DIR, "test_faqs.json")
    # test_company_id = "test_company_123"
    #
    # # CSV 테스트 데이터
    # csv_data = [
    #     {"id": "faq_1", "question": "테스트 질문 1 (CSV)?", "answer": "테스트 답변 1입니다.", "category": "테스트"},
    #     {"question": "테스트 질문 2 (CSV)는 무엇인가요?", "answer": "테스트 답변 2입니다.", "category": "일반", "source_doc_id": "doc_test_1"},
    # ]
    # with open(test_csv_file, mode='w', encoding='utf-8', newline='') as f:
    #     writer = csv.DictWriter(f, fieldnames=["id", "question", "answer", "category", "source_doc_id"])
    #     writer.writeheader()
    #     writer.writerows(csv_data)
    #
    # # JSON 테스트 데이터
    # json_data = [
    #     {"id": "faq_3", "question": "Test Question 3 (JSON)?", "answer": "This is test answer 3.", "category": "Test"},
    #     {"question": "What is Test Question 4 (JSON)?", "answer": "This is test answer 4.", "category": "General", "source_doc_id": "doc_test_2"},
    # ]
    # with open(test_json_file, mode='w', encoding='utf-8') as f:
    #     json.dump(json_data, f, indent=2)
    #
    # print(f"테스트용 CSV 파일 생성: {test_csv_file}")
    # print(f"테스트용 JSON 파일 생성: {test_json_file}")
    #
    # # CSV 로드 테스트
    # print("\n--- CSV 로드 테스트 시작 ---")
    # sys.argv = ['load_faqs.py', '--file_path', test_csv_file, '--company_id', test_company_id, '--file_type', 'csv']
    # main()
    # print("--- CSV 로드 테스트 완료 ---")
    #
    # # JSON 로드 테스트
    # print("\n--- JSON 로드 테스트 시작 ---")
    # sys.argv = ['load_faqs.py', '--file_path', test_json_file, '--company_id', test_company_id, '--file_type', 'json']
    # main()
    # print("--- JSON 로드 테스트 완료 ---")
    pass
