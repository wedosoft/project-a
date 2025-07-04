"""
첨부파일 선별 설정
"""

from dataclasses import dataclass
from typing import Dict, List, Any


@dataclass
class AttachmentConfig:
    """첨부파일 선별 설정 클래스"""
    max_selected_attachments: int = 3
    score_thresholds: Dict[str, int] = None
    extension_scores: Dict[str, List[str]] = None
    content_type_weights: Dict[str, int] = None
    file_size_preferences: Dict[str, int] = None
    important_keywords: List[str] = None
    content_keywords: List[str] = None
    
    def __post_init__(self):
        if self.score_thresholds is None:
            self.score_thresholds = {
                "direct_mention": 10,
                "high_relevance": 7,
                "medium_relevance": 5,
                "minimum_score": 3
            }
        
        if self.extension_scores is None:
            self.extension_scores = {
                "log_files": [".log", ".txt"],
                "image_files": [".png", ".jpg", ".jpeg", ".gif", ".bmp"],
                "document_files": [".pdf", ".doc", ".docx"],
                "config_files": [".json", ".xml", ".yaml", ".yml", ".csv"]
            }
        
        if self.content_type_weights is None:
            self.content_type_weights = {
                "image": 2,
                "text": 3,
                "application/json": 3
            }
        
        if self.file_size_preferences is None:
            self.file_size_preferences = {
                "optimal_min": 1024,
                "optimal_max": 5 * 1024 * 1024,
                "too_large": 20 * 1024 * 1024
            }
        
        if self.important_keywords is None:
            self.important_keywords = [
                "error", "log", "config", "setting", "screenshot",
                "에러", "로그", "설정", "스크린샷", "캡처", "오류", "문제"
            ]
        
        if self.content_keywords is None:
            self.content_keywords = [
                "오류", "에러", "문제", "설정", "로그", 
                "error", "problem", "issue", "config", "log"
            ]


# 첨부파일 선별 정책 설정
ATTACHMENT_SELECTION_CONFIG = {
    # 최대 선별 개수
    "max_selected_attachments": 3,
    
    # 점수 임계값 (성능 최적화를 위한 완화)
    "score_thresholds": {
        "direct_mention": 10,  # 직접 언급
        "high_relevance": 6,   # 높은 관련성 (8→6으로 완화)
        "medium_relevance": 4, # 중간 관련성 (6→4로 완화)
        "minimum_score": 2     # 최소 점수 (4→2로 완화)
    },
    
    # 파일 확장자별 기본 점수
    "extension_scores": {
        "log_files": [".log", ".txt"],
        "image_files": [".png", ".jpg", ".jpeg", ".gif", ".bmp"],
        "document_files": [".pdf", ".doc", ".docx"],
        "config_files": [".json", ".xml", ".yaml", ".yml", ".csv"]
    },
    
    # 콘텐츠 타입별 가중치
    "content_type_weights": {
        "image": 2,
        "text": 3,
        "application/json": 3
    },
    
    # 파일 크기 기준 (바이트)
    "file_size_preferences": {
        "optimal_min": 1024,           # 1KB 이상
        "optimal_max": 5 * 1024 * 1024, # 5MB 이하
        "too_large": 20 * 1024 * 1024   # 20MB 이상은 감점
    },
    
    # 중요 키워드 (문제 관련)
    "important_keywords": [
        "error", "log", "config", "setting", "screenshot",
        "에러", "로그", "설정", "스크린샷", "캡처", "오류", "문제"
    ],
    
    # 콘텐츠 관련 키워드 (최소 연관성 확인용)
    "content_keywords": [
        "오류", "에러", "문제", "설정", "로그", 
        "error", "problem", "issue", "config", "log"
    ]
}
