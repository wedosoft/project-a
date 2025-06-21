"""
데이터 처리 모듈

데이터 병합, 스키마 정의, 첨부파일 처리 등을 관리합니다.

통합된 기능들:
- merger.py: 데이터 병합 (구 data_merger.py)
- schemas.py: 데이터 스키마 정의
- attachment_processor.py: 첨부파일 처리 (backend/data에서 통합)
- data_processor.py: 일반 데이터 처리 (backend/data에서 통합)
"""

from .merger import *
from .schemas import *

# 새롭게 통합된 모듈들
try:
    from .attachment_processor import *
    from .data_processor import *
except ImportError:
    # 아직 임포트가 수정되지 않은 경우 무시
    pass

__all__ = [
    # 각 모듈에서 가져온 것들이 여기에 추가됩니다
]
