"""
첨부파일 처리 모듈

이 모듈은 Freshdesk에서 가져온 첨부파일을 스트리밍 방식으로 처리하는 기능을 제공합니다.
이미지 OCR, 문서 텍스트 추출 등 다양한 첨부파일 처리를 지원하며, 디스크 공간을 최소화합니다.

프로젝트 규칙 및 가이드라인: /PROJECT_RULES.md 참조
"""

import asyncio
import hashlib
import io
import json
import logging
import mimetypes
import os
import re
import sys
import tempfile
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import httpx
from PIL import Image, ImageEnhance, ImageFilter

# 설정 로드
try:
    from ..core.config import get_settings

    settings = get_settings()
except ImportError:
    # 테스트 환경에서는 기본값 사용
    class DefaultSettings:
        MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB
        IMAGE_MIN_SIZE = 1000
        CONTRAST_ENHANCEMENT = 2.0
        OCR_THRESHOLD = 150

    settings = DefaultSettings()

# 추가 라이브러리 - 필요시 설치 필요
try:
    import pytesseract  # OCR용

    HAS_TESSERACT = True
    # Tesseract 설치 경로 설정 (Windows의 경우 필요)
    if sys.platform.startswith("win"):
        pytesseract.pytesseract.tesseract_cmd = (
            r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        )
except ImportError:
    HAS_TESSERACT = False

try:
    import PyPDF2  # PDF 처리용

    HAS_PYPDF = True
except ImportError:
    HAS_PYPDF = False

try:
    import docx  # Word 문서 처리용

    HAS_DOCX = True
except ImportError:
    HAS_DOCX = False

# 로깅 설정
logger = logging.getLogger(__name__)

# 캐시 디렉토리 설정 - 결과만 저장
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "attachment_cache")
# 디렉토리가 없으면 생성
os.makedirs(CACHE_DIR, exist_ok=True)

# 처리할 수 있는 파일 타입 정의
IMAGE_TYPES = ["image/jpeg", "image/png", "image/gif", "image/bmp", "image/tiff"]
DOCUMENT_TYPES = [
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "text/plain",
    "text/csv",
    "application/vnd.ms-excel",
]
PROCESSABLE_TYPES = IMAGE_TYPES + DOCUMENT_TYPES

# 최대 처리 파일 크기 (환경변수 또는 기본값 사용)
MAX_FILE_SIZE = getattr(settings, "MAX_FILE_SIZE", 20 * 1024 * 1024)


# 처리 결과 캐싱
def get_cache_key(attachment: Dict[str, Any]) -> str:
    """
    첨부파일의 캐시 키를 생성합니다.

    Args:
        attachment: 첨부파일 정보

    Returns:
        캐시 키 문자열
    """
    # 고유한 ID와 업데이트 시간으로 캐시 키 생성
    att_id = str(attachment.get("id", ""))
    att_updated = str(attachment.get("updated_at", ""))
    key_str = f"{att_id}_{att_updated}"
    return hashlib.md5(key_str.encode()).hexdigest()


def get_cached_result(cache_key: str) -> Optional[Dict[str, Any]]:
    """
    캐시된 처리 결과를 가져옵니다.

    Args:
        cache_key: 캐시 키

    Returns:
        캐시된 결과 또는 None (캐시 미스 시)
    """
    cache_file = os.path.join(CACHE_DIR, f"{cache_key}.json")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"캐시 파일 읽기 오류: {e}")
    return None


def save_to_cache(cache_key: str, result: Dict[str, Any]) -> None:
    """
    처리 결과를 캐시에 저장합니다.
    (pre-signed URL은 저장하지 않고, id/메타데이터만 저장)

    Args:
        cache_key: 캐시 키
        result: 저장할 결과 (id, name, content_type, size, updated_at 등 메타데이터 + 추출 텍스트)
    """
    try:
        cache_file = os.path.join(CACHE_DIR, f"{cache_key}.json")
        # 메타데이터만 저장 (URL 저장 금지)
        cache_data = {
            "id": result.get("id"),
            "name": result.get("name"),
            "content_type": result.get("content_type"),
            "size": result.get("size"),
            "updated_at": result.get("updated_at"),
            "extracted_text": result.get("extracted_text", ""),
            "processed": result.get("processed", False),
            "cached_at": datetime.now().isoformat(),
        }
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"캐시 파일 저장 오류: {e}")


def preprocess_image_for_ocr(img: Image.Image) -> Image.Image:
    """
    OCR 성능 향상을 위해 이미지를 전처리합니다.

    Args:
        img: 원본 이미지

    Returns:
        전처리된 이미지
    """
    try:
        # 그레이스케일 변환
        if img.mode != "L":
            img = img.convert("L")

        # 이미지 크기 조정 (너무 작은 경우 확대)
        width, height = img.size
        if width < settings.IMAGE_MIN_SIZE or height < settings.IMAGE_MIN_SIZE:
            ratio = max(
                settings.IMAGE_MIN_SIZE / width, settings.IMAGE_MIN_SIZE / height
            )
            new_width = int(width * ratio)
            new_height = int(height * ratio)
            img = img.resize((new_width, new_height), Image.LANCZOS)

        # 이미지 선명도 향상
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(settings.CONTRAST_ENHANCEMENT)  # 대비 증가

        # 노이즈 제거
        img = img.filter(ImageFilter.MedianFilter(size=3))

        # 이진화 (흑백)
        threshold = settings.OCR_THRESHOLD
        img = img.point(lambda p: 255 if p > threshold else 0)

        return img
    except Exception as e:
        logger.warning(f"이미지 전처리 오류: {e} - 원본 이미지로 계속 진행합니다")
        return img


async def process_image_stream(client: httpx.AsyncClient, url: str) -> Dict[str, Any]:
    """
    이미지 URL에서 직접 스트리밍하여 OCR 처리하고 이미지 정보 반환

    Args:
        client: HTTP 클라이언트
        url: 이미지 URL

    Returns:
        추출된 텍스트와 이미지 정보를 포함한 딕셔너리
    """
    if not HAS_TESSERACT:
        logger.warning("Tesseract OCR이 설치되지 않았습니다. 텍스트 추출을 건너뜁니다.")
        return {
            "text": "[Tesseract OCR이 설치되지 않아 이미지 텍스트 추출이 불가능합니다]",
            "image_url": url,  # 이미지 URL 보존
            "ocr_success": False,
        }

    try:
        # 이미지 스트리밍 다운로드
        resp = await client.get(url)
        resp.raise_for_status()

        # 임시 메모리에서 이미지 처리
        img_data = resp.content
        img = Image.open(io.BytesIO(img_data))

        # 이미지 전처리
        processed_img = preprocess_image_for_ocr(img)

        # OCR 처리 (다양한 언어 지원 및 고급 설정)
        try:
            # 한국어+영어 OCR 시도
            text = pytesseract.image_to_string(
                processed_img,
                lang="kor+eng",  # 한국어+영어 인식
                config="--psm 1 --oem 3",  # 자동 페이지 분할 및 최신 OCR 엔진 사용
            )
        except Exception as ocr_err:
            logger.warning(f"한국어+영어 OCR 실패, 영어만 시도: {ocr_err}")
            # 영어만 OCR 시도 (fallback)
            text = pytesseract.image_to_string(processed_img, config="--psm 1 --oem 3")

        # 텍스트 후처리 (줄바꿈 정리, 불필요한 공백 제거)
        if text:
            # 여러 개의 줄바꿈 통합
            text = re.sub(r"\n{3,}", "\n\n", text)
            # 불필요한 공백 제거
            text = re.sub(r" {2,}", " ", text)
            return {"text": text.strip(), "image_url": url, "ocr_success": True}
        else:
            return {
                "text": "[이미지에서 텍스트를 추출할 수 없습니다]",
                "image_url": url,
                "ocr_success": False,
            }

    except (httpx.HTTPError, httpx.TimeoutException) as http_err:
        logger.error(f"이미지 다운로드 오류: {http_err}")
        return {
            "text": f"[이미지 다운로드 오류: {str(http_err)}]",
            "image_url": url,
            "ocr_success": False,
        }
    except Image.UnidentifiedImageError:
        logger.error("지원되지 않는 이미지 형식")
        return {
            "text": "[지원되지 않는 이미지 형식]",
            "image_url": url,
            "ocr_success": False,
        }
    except Exception as e:
        logger.error(f"이미지 처리 오류: {e}")
        return {"text": "[이미지 처리 오류]", "image_url": url, "ocr_success": False}


async def process_pdf_stream(client: httpx.AsyncClient, url: str) -> str:
    """
    PDF URL에서 직접 스트리밍하여 텍스트 추출합니다.

    Args:
        client: HTTP 클라이언트
        url: PDF URL

    Returns:
        추출된 텍스트
    """
    if not HAS_PYPDF:
        logger.warning("PyPDF2가 설치되지 않았습니다. PDF 텍스트 추출을 건너뜁니다.")
        return "[PDF 텍스트 추출이 지원되지 않습니다]"

    try:
        # PDF 스트리밍 다운로드
        resp = await client.get(url)
        resp.raise_for_status()

        # 임시 메모리에서 PDF 처리
        pdf_data = io.BytesIO(resp.content)
        reader = PyPDF2.PdfReader(pdf_data)

        # 텍스트 추출
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text.strip() or "[PDF에서 추출된 텍스트 없음]"
    except Exception as e:
        logger.error(f"PDF 처리 오류: {e}")
        return "[PDF 처리 오류]"


async def process_docx_stream(client: httpx.AsyncClient, url: str) -> str:
    """
    Word 문서 URL에서 직접 스트리밍하여 텍스트 추출합니다.
    (Word 문서는 임시 파일 사용이 필요합니다)

    Args:
        client: HTTP 클라이언트
        url: Word 문서 URL

    Returns:
        추출된 텍스트
    """
    if not HAS_DOCX:
        logger.warning(
            "python-docx가 설치되지 않았습니다. Word 텍스트 추출을 건너뜁니다."
        )
        return "[Word 문서 텍스트 추출이 지원되지 않습니다]"

    try:
        # Word 문서 스트리밍 다운로드
        resp = await client.get(url)
        resp.raise_for_status()

        # docx는 임시 파일로 저장 필요 (메모리에서 직접 처리 불가)
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=True) as temp_file:
            temp_file.write(resp.content)
            temp_file.flush()

            # 문서 처리
            doc = docx.Document(temp_file.name)
            text = "\n".join([paragraph.text for paragraph in doc.paragraphs])

        return text.strip() or "[Word 문서에서 추출된 텍스트 없음]"
    except Exception as e:
        logger.error(f"Word 문서 처리 오류: {e}")
        return "[Word 문서 처리 오류]"


async def process_text_stream(client: httpx.AsyncClient, url: str) -> str:
    """
    텍스트 파일 URL에서 직접 스트리밍하여 텍스트 추출합니다.

    Args:
        client: HTTP 클라이언트
        url: 텍스트 파일 URL

    Returns:
        추출된 텍스트
    """
    try:
        # 텍스트 파일 스트리밍 다운로드
        resp = await client.get(url)
        resp.raise_for_status()

        # 텍스트 디코딩
        text = resp.text
        return text.strip() or "[빈 텍스트 파일]"
    except Exception as e:
        logger.error(f"텍스트 파일 처리 오류: {e}")
        return "[텍스트 파일 처리 오류]"


async def process_attachment_stream(
    client: httpx.AsyncClient, attachment: Dict[str, Any]
) -> Dict[str, Any]:
    """
    첨부파일을 스트리밍 방식으로 처리하여 콘텐츠를 추출합니다.
    (pre-signed URL은 저장하지 않고, id/메타데이터만 반환)

    Args:
        client: HTTP 클라이언트
        attachment: 첨부파일 정보

    Returns:
        처리된 첨부파일 정보 (id, name, content_type, size, updated_at 등 메타데이터 + 추출된 텍스트)
        ※ pre-signed URL(attachment_url)은 저장하지 않음. 이미지는 표시 시점에 API로 최신 URL을 발급받아야 함.
    """
    # 메타데이터만 추출
    result = {
        "id": attachment.get("id"),
        "name": attachment.get("name"),
        "content_type": attachment.get("content_type"),
        "size": attachment.get("size"),
        "updated_at": attachment.get("updated_at"),
        # URL은 저장하지 않음
    }

    # 캐시 확인 (캐시도 메타데이터만 저장)
    cache_key = get_cache_key(attachment)
    cached_result = get_cached_result(cache_key)
    if cached_result:
        logger.info(f"캐시에서 첨부파일 처리 결과 로드: {attachment.get('name', '')}")
        result["extracted_text"] = cached_result.get("extracted_text", "")
        result["processed"] = cached_result.get("processed", False)
        result["from_cache"] = True
        return result

    # 처리 가능한 파일 유형인지 확인
    content_type = attachment.get("content_type", "")
    if content_type not in PROCESSABLE_TYPES:
        logger.info(f"처리할 수 없는 파일 유형 건너뜀: {content_type}")
        result["extracted_text"] = ""
        result["processed"] = False
        return result

    # 파일 크기 확인
    file_size = attachment.get("size", 0)
    if file_size and file_size > MAX_FILE_SIZE:
        logger.warning(f"파일 크기 제한 초과: {file_size} > {MAX_FILE_SIZE} bytes")
        result["extracted_text"] = (
            f"[파일 크기 제한 초과: {file_size/(1024*1024):.2f} MB]"
        )
        result["processed"] = False
        return result

    # URL 확인 (실제 다운로드/처리에는 사용하지만, 저장은 하지 않음)
    url = attachment.get("attachment_url")
    if not url:
        logger.warning(f"첨부파일 URL이 없습니다: {attachment.get('name')}")
        result["extracted_text"] = ""
        result["processed"] = False
        return result

    # 파일 유형에 따라 적절한 처리 방법 선택
    extracted_text = ""
    try:
        if content_type in IMAGE_TYPES:
            extracted_text = await process_image_stream(client, url)
        elif content_type == "application/pdf":
            extracted_text = await process_pdf_stream(client, url)
        elif content_type in [
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/msword",
        ]:
            extracted_text = await process_docx_stream(client, url)
        elif content_type.startswith("text/"):
            extracted_text = await process_text_stream(client, url)

        result["extracted_text"] = extracted_text
        result["processed"] = True

        # 결과 캐싱 (메타데이터만 저장)
        save_to_cache(cache_key, result)

        return result
    except Exception as e:
        logger.error(f"첨부파일 처리 오류: {e}")
        result["extracted_text"] = f"[처리 오류: {str(e)}]"
        result["processed"] = False
        return result


async def process_attachments(
    attachments: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    여러 첨부파일을 병렬로 처리합니다.

    Args:
        attachments: 첨부파일 목록

    Returns:
        처리된 첨부파일 목록
    """
    if not attachments:
        return []

    logger.info(f"{len(attachments)}개 첨부파일 처리 시작")

    # 처리할 첨부파일 필터링 (중복 제거, 크기 제한 등)
    filtered_attachments = []
    seen_ids = set()

    for att in attachments:
        att_id = att.get("id")
        if att_id in seen_ids:
            continue

        seen_ids.add(att_id)
        filtered_attachments.append(att)

    logger.info(f"{len(filtered_attachments)}개 고유 첨부파일 처리 예정")

    async with httpx.AsyncClient() as client:
        tasks = [
            process_attachment_stream(client, attachment)
            for attachment in filtered_attachments
        ]
        processed = await asyncio.gather(*tasks)

    logger.info(f"{len(processed)}개 첨부파일 처리 완료")
    return processed
