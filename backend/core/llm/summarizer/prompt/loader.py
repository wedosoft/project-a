"""
프롬프트 로더 - YAML 템플릿 파일 로드 및 캐싱
"""

import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from functools import lru_cache

logger = logging.getLogger(__name__)


class PromptLoader:
    """프롬프트 템플릿 로더"""
    
    def __init__(self, templates_dir: Optional[Path] = None):
        if templates_dir is None:
            self.templates_dir = Path(__file__).parent / "templates"
        else:
            self.templates_dir = Path(templates_dir)
        
        if not self.templates_dir.exists():
            raise FileNotFoundError(f"Templates directory not found: {self.templates_dir}")
    
    @lru_cache(maxsize=32)
    def load_template(self, template_type: str, template_name: str) -> Dict[str, Any]:
        """
        템플릿 파일 로드 (캐싱됨)
        
        Args:
            template_type: 템플릿 타입 (system, user, sections)
            template_name: 템플릿 파일명 (확장자 제외)
            
        Returns:
            Dict: 로드된 템플릿 데이터
        """
        template_path = self.templates_dir / template_type / f"{template_name}.yaml"
        
        if not template_path.exists():
            logger.error(f"Template file not found: {template_path}")
            raise FileNotFoundError(f"Template file not found: {template_path}")
        
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                template_data = yaml.safe_load(f)
            
            logger.debug(f"Loaded template: {template_path}")
            return template_data
            
        except Exception as e:
            logger.error(f"Failed to load template {template_path}: {e}")
            raise
    
    def get_sections(self) -> Dict[str, Any]:
        """섹션 구조 정의 로드"""
        return self.load_template("sections", "structure")
    
    def get_system_prompt_template(self, content_type: str) -> Dict[str, Any]:
        """시스템 프롬프트 템플릿 로드"""
        return self.load_template("system", content_type)
    
    def get_user_prompt_template(self, content_type: str) -> Dict[str, Any]:
        """사용자 프롬프트 템플릿 로드"""
        return self.load_template("user", content_type)
    
    def clear_cache(self):
        """캐시 클리어"""
        self.load_template.cache_clear()
        logger.info("Template cache cleared")


# 전역 로더 인스턴스
_prompt_loader = None


def get_prompt_loader() -> PromptLoader:
    """프롬프트 로더 싱글톤 인스턴스 반환"""
    global _prompt_loader
    if _prompt_loader is None:
        _prompt_loader = PromptLoader()
    return _prompt_loader
