"""
실시간 티켓 요약 전용 프롬프트 로더

기존 유사티켓/지식베이스 프롬프트와 완전히 분리된 실시간 요약 전용 시스템
"""

import logging
import yaml
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class RealtimePromptLoader:
    """실시간 티켓 요약 전용 프롬프트 로더"""
    
    def __init__(self):
        """실시간 프롬프트 로더 초기화"""
        self.base_path = Path(__file__).parent / "templates"
        self.system_path = self.base_path / "system"
        self.user_path = self.base_path / "user"
        
        # 캐시
        self._system_prompt_cache = {}
        self._user_prompt_cache = {}
        
        logger.info("RealtimePromptLoader 초기화 완료")
    
    def get_system_prompt_template(self) -> Dict[str, Any]:
        """실시간 요약용 시스템 프롬프트 템플릿 로드"""
        if "ticket_view" in self._system_prompt_cache:
            return self._system_prompt_cache["ticket_view"]
        
        try:
            template_path = self.system_path / "ticket_view.yaml"
            
            if not template_path.exists():
                raise FileNotFoundError(f"실시간 시스템 프롬프트 파일이 없습니다: {template_path}")
            
            with open(template_path, 'r', encoding='utf-8') as f:
                template_data = yaml.safe_load(f)
            
            # 유효성 검증
            if template_data.get('content_type') != 'ticket_view':
                raise ValueError(f"잘못된 content_type: {template_data.get('content_type')}")
            
            if template_data.get('quality_level') != 'premium':
                logger.warning("실시간 요약이 premium 품질이 아닙니다")
            
            self._system_prompt_cache["ticket_view"] = template_data
            logger.info("조회 티켓 시스템 프롬프트 로드 완료")
            
            return template_data
            
        except Exception as e:
            logger.error(f"실시간 시스템 프롬프트 로드 실패: {e}")
            raise
    
    def get_user_prompt_template(self) -> Dict[str, Any]:
        """실시간 요약용 사용자 프롬프트 템플릿 로드"""
        if "ticket_view" in self._user_prompt_cache:
            return self._user_prompt_cache["ticket_view"]
        
        try:
            template_path = self.user_path / "ticket_view.yaml"
            
            if not template_path.exists():
                raise FileNotFoundError(f"실시간 사용자 프롬프트 파일이 없습니다: {template_path}")
            
            with open(template_path, 'r', encoding='utf-8') as f:
                template_data = yaml.safe_load(f)
            
            # 유효성 검증
            if template_data.get('content_type') != 'ticket_view':
                raise ValueError(f"잘못된 content_type: {template_data.get('content_type')}")
            
            if template_data.get('quality_level') != 'premium':
                logger.warning("실시간 요약이 premium 품질이 아닙니다")
            
            self._user_prompt_cache["ticket_view"] = template_data
            logger.info("실시간 사용자 프롬프트 로드 완료")
            
            return template_data
            
        except Exception as e:
            logger.error(f"실시간 사용자 프롬프트 로드 실패: {e}")
            raise
    
    def build_system_prompt(self, content_language: str = "ko", ui_language: str = "ko") -> str:
        """실시간 요약용 시스템 프롬프트 빌드"""
        try:
            template_data = self.get_system_prompt_template()
            
            # 기본 지시사항
            base_instruction = template_data['base_instruction'].get(
                ui_language, 
                template_data['base_instruction']['ko']
            )
            
            # 언어별 지시사항
            language_instruction = template_data['language_instructions'].get(
                content_language, 
                template_data['language_instructions']['default']
            )
            
            # 프리미엄 요구사항
            premium_reqs = '\n'.join([f"- {req}" for req in template_data['premium_requirements']])
            
            # 절대 요구사항
            absolute_reqs = '\n'.join([f"- {req}" for req in template_data['absolute_requirements']])
            
            # 실시간 특화 요구사항
            realtime_reqs = '\n'.join([f"- {req}" for req in template_data['realtime_specific_requirements']])
            
            # 금지사항
            forbidden = '\n'.join([f"- {item}" for item in template_data['strictly_forbidden']])
            
            # 포맷팅 규칙
            formatting = template_data['formatting_rules'].get(
                ui_language, 
                template_data['formatting_rules']['ko']
            )
            
            # 최종 프롬프트 조합
            system_prompt = f"""{base_instruction}

CRITICAL MISSION: {template_data['critical_mission']}

PREMIUM REQUIREMENTS (실시간 요약 전용):
{premium_reqs}

ABSOLUTE REQUIREMENTS:
{absolute_reqs}

REAL-TIME SPECIFIC REQUIREMENTS:
{realtime_reqs}

STRICTLY FORBIDDEN:
{forbidden}

FORMATTING RULES:
- {language_instruction}
{formatting}"""
            
            logger.info("실시간 시스템 프롬프트 빌드 완료")
            return system_prompt
            
        except Exception as e:
            logger.error(f"실시간 시스템 프롬프트 빌드 실패: {e}")
            # 폴백 프롬프트
            return self._get_fallback_system_prompt(content_language, ui_language)
    
    def build_user_prompt(
        self,
        content: str,
        subject: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        content_language: str = "ko",
        ui_language: str = "ko"
    ) -> str:
        """실시간 요약용 사용자 프롬프트 빌드"""
        try:
            template_data = self.get_user_prompt_template()
            
            # 메타데이터 포맷팅 (첨부파일 제외)
            metadata_formatted = ""
            if metadata:
                formatted_metadata = []
                
                # 핵심 정보만 포함 (첨부파일 제외)
                exclude_keys = [
                    'attachments', 'all_attachments', 'attachment_types', 
                    'has_attachments', 'has_image_attachments', 
                    'has_document_attachments', 'large_attachments'
                ]
                
                for k, v in metadata.items():
                    if k not in exclude_keys and v:
                        if k in ['company_name', 'customer_email', 'agent_name', 
                               'department', 'ticket_category', 'complexity_level', 
                               'product_version', 'priority', 'status', 'created_at', 
                               'escalation_count']:
                            formatted_metadata.append(f"{k}: {v}")
                
                if formatted_metadata:
                    metadata_formatted = "; ".join(formatted_metadata)
            
            # 지시사항 선택
            instruction_text = template_data['instructions'].get(
                ui_language, 
                template_data['instructions']['ko']
            )
            
            # Jinja2 스타일 템플릿 수동 렌더링 (실시간 속도 최적화)
            template = template_data['template']
            
            # 조건부 처리
            if subject:
                template = template.replace(
                    "{%- if subject %}\n  REAL-TIME TICKET ANALYSIS REQUEST (PREMIUM QUALITY)\n  TICKET SUBJECT: {{ subject }}\n  {% endif -%}",
                    f"REAL-TIME TICKET ANALYSIS REQUEST (PREMIUM QUALITY)\nTICKET SUBJECT: {subject}"
                )
            else:
                template = template.replace(
                    "{%- if subject %}\n  REAL-TIME TICKET ANALYSIS REQUEST (PREMIUM QUALITY)\n  TICKET SUBJECT: {{ subject }}\n  {% endif -%}",
                    "REAL-TIME TICKET ANALYSIS REQUEST (PREMIUM QUALITY)"
                )
            
            if metadata_formatted:
                template = template.replace(
                    "{%- if metadata_formatted %}\n  METADATA: {{ metadata_formatted }}\n  {% endif -%}",
                    f"METADATA: {metadata_formatted}"
                )
            else:
                template = template.replace(
                    "{%- if metadata_formatted %}\n  METADATA: {{ metadata_formatted }}\n  {% endif -%}",
                    ""
                )
            
            # 변수 치환
            user_prompt = template.replace("{{ content }}", content)
            user_prompt = user_prompt.replace("{{ instruction_text }}", instruction_text)
            user_prompt = user_prompt.replace('{{ "=" * 60 }}', "=" * 60)
            
            logger.info("실시간 사용자 프롬프트 빌드 완료")
            return user_prompt
            
        except Exception as e:
            logger.error(f"실시간 사용자 프롬프트 빌드 실패: {e}")
            # 폴백 프롬프트
            return self._get_fallback_user_prompt(content, subject, metadata, content_language, ui_language)
    
    def _get_fallback_system_prompt(self, content_language: str, ui_language: str) -> str:
        """폴백 시스템 프롬프트"""
        return f"""You are a premium real-time ticket analysis specialist providing the highest quality summaries when agents open tickets.

Your summaries must exceed similar ticket summaries in accuracy, detail, and actionability.

CRITICAL REQUIREMENTS:
- Preserve ALL technical details with perfect precision
- Include complete business context and stakeholder information
- Structure for 5-second agent comprehension
- Provide all information needed for immediate escalation
- Use exact terminology and quotations from original content

Language: {content_language if content_language in ['ko', 'en', 'ja', 'zh'] else 'ko'}

Format your response in the following structure:
## 🔍 문제 현황
## 💡 원인 분석  
## ⚡ 해결 진행상황
## 🎯 중요 인사이트"""
    
    def _get_fallback_user_prompt(
        self, 
        content: str, 
        subject: str, 
        metadata: Optional[Dict[str, Any]], 
        content_language: str, 
        ui_language: str
    ) -> str:
        """폴백 사용자 프롬프트"""
        prompt = "REAL-TIME TICKET ANALYSIS REQUEST (PREMIUM QUALITY)\n\n"
        
        if subject:
            prompt += f"TICKET SUBJECT: {subject}\n\n"
        
        if metadata:
            prompt += f"METADATA: {str(metadata)}\n\n"
        
        prompt += f"ORIGINAL CONTENT FOR PREMIUM REAL-TIME ANALYSIS:\n"
        prompt += "=" * 60 + "\n"
        prompt += content + "\n"
        prompt += "=" * 60 + "\n\n"
        prompt += "위 내용을 분석하여 상담원이 티켓을 열었을 때 즉시 완벽한 이해를 할 수 있는 최고 품질의 실시간 요약을 작성하세요."
        
        return prompt
    
    def get_prompt_info(self) -> Dict[str, Any]:
        """실시간 프롬프트 정보 반환"""
        try:
            system_data = self.get_system_prompt_template()
            user_data = self.get_user_prompt_template()
            
            return {
                "type": "ticket_view",
                "quality_level": "premium",
                "system_version": system_data.get("version", "unknown"),
                "user_version": user_data.get("version", "unknown"),
                "last_updated": system_data.get("last_updated", "unknown"),
                "purpose": system_data.get("purpose", "실시간 티켓 요약"),
                "features": [
                    "5초 내 이해 최적화",
                    "즉시 에스컬레이션 준비",
                    "첨부파일 처리 제외 (속도 최적화)",
                    "프리미엄 품질 보장",
                    "유사티켓 대비 우수한 품질"
                ]
            }
        except Exception as e:
            logger.error(f"프롬프트 정보 조회 실패: {e}")
            return {
                "type": "ticket_view",
                "quality_level": "premium",
                "status": "error",
                "error": str(e)
            }
