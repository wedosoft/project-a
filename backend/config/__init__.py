"""
Config 패키지

환경별 설정과 데이터 설정 파일들을 관리합니다.

구조:
- settings/: Python 환경별 설정 파일들
  - base.py: 기본 설정
  - development.py: 개발 환경 설정
  - production.py: 프로덕션 환경 설정
  - testing.py: 테스트 환경 설정
- data/: JSON/YAML 등 데이터 설정 파일들
  - conversation_keywords_ko.json: 한국어 대화 키워드
  - multilingual_keywords.json: 다국어 키워드
"""

from .settings import get_settings, get_config_data_path

__all__ = [
    "get_settings",
    "get_config_data_path"
]
