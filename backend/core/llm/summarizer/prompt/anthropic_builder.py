"""
Anthropic 최적화된 프롬프트 빌더

이 모듈은 Anthropic 프롬프트 엔지니어링 기법이 적용된 프롬프트 빌더를 제공합니다.
Constitutional AI, Chain-of-Thought, XML 구조화 등의 기법을 사용하여
고품질의 일관된 프롬프트를 생성합니다.
"""

import yaml
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from jinja2 import Template, Environment, FileSystemLoader
import json
import re
from datetime import datetime

from .loader import PromptLoader

logger = logging.getLogger(__name__)


class AnthropicPromptBuilder:
    """Anthropic 프롬프트 엔지니어링 기법이 적용된 프롬프트 빌더"""
    
    def __init__(self, templates_dir: Optional[Path] = None):
        """
        Args:
            templates_dir: 템플릿 디렉토리 경로. None이면 기본 경로 사용
        """
        if templates_dir is None:
            self.templates_dir = Path(__file__).parent / "templates"
        else:
            self.templates_dir = Path(templates_dir)
        
        self.prompt_loader = PromptLoader(self.templates_dir)
        self.anthropic_templates = {}
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(self.templates_dir))
        )
        
        self._load_anthropic_templates()
    
    def _load_anthropic_templates(self):
        """Anthropic 최적화 템플릿들을 로드"""
        try:
            template_files = {
                'anthropic_ticket_view': {
                    'system': 'system/anthropic_ticket_view.yaml',
                    'user': 'user/anthropic_ticket_view.yaml'
                },
                'realtime_summary': {
                    'system': 'system/realtime_summary.yaml'
                },
                'attachment_selection': {
                    'system': 'system/attachment_selection.yaml'
                },
                'ticket_analysis': {
                    'system': 'system/ticket_analysis.yaml'
                },
                'prompt_management': {
                    'admin': 'admin/prompt_management.yaml'
                }
            }
            
            for template_name, files in template_files.items():
                self.anthropic_templates[template_name] = {}
                for prompt_type, file_path in files.items():
                    full_path = self.templates_dir / file_path
                    if full_path.exists():
                        with open(full_path, 'r', encoding='utf-8') as f:
                            self.anthropic_templates[template_name][prompt_type] = yaml.safe_load(f)
                    else:
                        logger.warning(f"Anthropic 템플릿 파일 없음: {full_path}")
            
            logger.debug("Anthropic 최적화 템플릿 로드 완료")
            
        except Exception as e:
            logger.error(f"Anthropic 템플릿 로드 실패: {e}")
            raise
    
    def build_constitutional_system_prompt(self, 
                                         template_name: str = "anthropic_ticket_view",
                                         content_language: str = "ko",
                                         ui_language: str = "ko",
                                         context: Optional[Dict[str, Any]] = None) -> str:
        """
        Constitutional AI 원칙이 적용된 시스템 프롬프트 생성
        
        Args:
            template_name: 사용할 템플릿 이름
            content_language: 콘텐츠 언어
            ui_language: UI 언어
            context: 추가 컨텍스트 정보
            
        Returns:
            str: Constitutional AI 원칙이 적용된 시스템 프롬프트
        """
        try:
            template_data = self.anthropic_templates[template_name]['system']
            
            # Constitutional AI 원칙 구성
            constitutional_principles = self._format_constitutional_principles(
                template_data.get('constitutional_principles', {})
            )
            
            # Role definition 구성
            role_expertise = self._format_role_definition(
                template_data.get('role_definition', {})
            )
            
            # Chain of Thought 추론 구조
            reasoning_framework = self._format_reasoning_framework(
                template_data.get('reasoning_framework', {})
            )
            
            # 언어별 시스템 프롬프트 선택
            system_prompts = template_data.get('system_prompts', {})
            base_prompt = system_prompts.get(ui_language, system_prompts.get('ko', ''))
            
            # 컨텍스트 기반 동적 조정
            if context:
                base_prompt = self._apply_context_adjustments(base_prompt, context, template_data)
            
            return base_prompt
            
        except Exception as e:
            logger.error(f"Constitutional 시스템 프롬프트 생성 실패: {e}")
            # 폴백: 기본 프롬프트 로더 사용
            return self.prompt_loader.load_system_prompt(
                "ticket_view", content_language, ui_language
            )
    
    def build_xml_structured_user_prompt(self,
                                       template_name: str = "anthropic_ticket_view",
                                       content: str = "",
                                       subject: str = "",
                                       metadata: Optional[Dict[str, Any]] = None,
                                       content_language: str = "ko",
                                       ui_language: str = "ko",
                                       **kwargs) -> str:
        """
        XML 구조화된 사용자 프롬프트 생성
        
        Args:
            template_name: 사용할 템플릿 이름
            content: 티켓 내용
            subject: 티켓 제목
            metadata: 메타데이터
            content_language: 콘텐츠 언어
            ui_language: UI 언어
            **kwargs: 추가 템플릿 변수들
            
        Returns:
            str: XML 구조화된 사용자 프롬프트
        """
        try:
            template_data = self.anthropic_templates[template_name]['user']
            
            # 기본 템플릿 변수 준비
            template_vars = {
                'subject': subject,
                'content': content,
                'metadata_formatted': self._format_metadata(metadata or {}),
                'content_language': content_language,
                'ui_language': ui_language,
                **kwargs
            }
            
            # 첨부파일 요약 처리
            if 'attachments' in kwargs:
                template_vars['attachment_summary'] = self._format_attachments(
                    kwargs['attachments']
                )
            
            # 대화 기록 처리
            if 'conversation_history' in kwargs:
                template_vars['conversation_history'] = self._format_conversation_history(
                    kwargs['conversation_history']
                )
            
            # 동적 프롬프트 조정 적용
            dynamic_adjustments = template_data.get('dynamic_adjustments', {})
            additional_instructions = self._get_dynamic_adjustments(
                metadata or {}, dynamic_adjustments
            )
            template_vars['additional_instructions'] = additional_instructions
            
            # Jinja2 템플릿 렌더링
            if 'template' in template_data:
                template_str = template_data['template']
            else:
                # 언어별 템플릿 사용
                instructions = template_data.get('instructions', {})
                template_str = instructions.get(ui_language, instructions.get('ko', ''))
            
            template = Template(template_str)
            rendered_prompt = template.render(**template_vars)
            
            # 컨텍스트 최적화 적용
            context_optimization = template_data.get('context_optimization', {})
            if context_optimization:
                rendered_prompt = self._optimize_context(rendered_prompt, context_optimization)
            
            return rendered_prompt
            
        except Exception as e:
            logger.error(f"XML 구조화 사용자 프롬프트 생성 실패: {e}")
            # 폴백: 기본 프롬프트 로더 사용
            return self.prompt_loader.load_user_prompt(
                "ticket_view", content, subject, metadata or {}, content_language, ui_language
            )
    
    def build_realtime_summary_prompt(self,
                                    content: str,
                                    subject: str,
                                    retry_context: Optional[str] = None,
                                    ui_language: str = "ko") -> Dict[str, str]:
        """
        실시간 요약용 프롬프트 생성 (재시도 이유별 적응형)
        
        Args:
            content: 티켓 내용
            subject: 티켓 제목
            retry_context: 재시도 컨텍스트 (initial, length_retry, quality_retry, error_retry)
            ui_language: UI 언어
            
        Returns:
            Dict[str, str]: {'system': 시스템 프롬프트, 'user': 사용자 프롬프트}
        """
        try:
            template_data = self.anthropic_templates['realtime_summary']['system']
            
            # 재시도 컨텍스트에 따른 시스템 프롬프트 선택
            retry_contexts = template_data.get('retry_contexts', {})
            context_key = retry_context or 'initial'
            
            if context_key in retry_contexts:
                system_prompt = retry_contexts[context_key]['system_prompt']
            else:
                # 기본 시스템 프롬프트 사용
                system_prompts = template_data.get('system_prompts', {})
                system_prompt = system_prompts.get(ui_language, system_prompts.get('ko', ''))
            
            # 사용자 프롬프트 생성
            user_template_str = template_data.get('user_prompt_template', '')
            user_template = Template(user_template_str)
            user_prompt = user_template.render(
                subject=subject,
                content=content,
                retry_context=retry_context
            )
            
            return {
                'system': system_prompt,
                'user': user_prompt
            }
            
        except Exception as e:
            logger.error(f"실시간 요약 프롬프트 생성 실패: {e}")
            # 폴백: 간단한 프롬프트 반환
            return {
                'system': "당신은 티켓 요약 전문가입니다.",
                'user': f"제목: {subject}\n내용: {content}\n\n위 티켓을 간단히 요약하세요."
            }
    
    def build_attachment_selection_prompt(self,
                                        content: str,
                                        subject: str,
                                        attachments: List[Dict[str, Any]],
                                        metadata: Optional[Dict[str, Any]] = None,
                                        ui_language: str = "ko") -> Dict[str, str]:
        """
        첨부파일 선별용 프롬프트 생성
        
        Args:
            content: 티켓 내용
            subject: 티켓 제목
            attachments: 첨부파일 목록
            metadata: 메타데이터
            ui_language: UI 언어
            
        Returns:
            Dict[str, str]: {'system': 시스템 프롬프트, 'user': 사용자 프롬프트}
        """
        try:
            template_data = self.anthropic_templates['attachment_selection']['system']
            
            # 시스템 프롬프트 선택
            system_prompts = template_data.get('system_prompts', {})
            system_prompt = system_prompts.get(ui_language, system_prompts.get('ko', ''))
            
            # 사용자 프롬프트 생성
            user_template_str = template_data.get('user_prompt_template', '')
            user_template = Template(user_template_str)
            
            user_prompt = user_template.render(
                subject=subject,
                content=content,
                attachments=attachments,
                category=metadata.get('category', '') if metadata else '',
                priority=metadata.get('priority', '') if metadata else '',
                customer_context=metadata.get('customer_context', '') if metadata else ''
            )
            
            return {
                'system': system_prompt,
                'user': user_prompt
            }
            
        except Exception as e:
            logger.error(f"첨부파일 선별 프롬프트 생성 실패: {e}")
            return {
                'system': "You are an intelligent attachment selector.",
                'user': f"Subject: {subject}\nContent: {content}\nSelect relevant attachments."
            }
    
    def build_comprehensive_analysis_prompt(self,
                                          ticket_data: Dict[str, Any],
                                          ui_language: str = "ko") -> Dict[str, str]:
        """
        종합적인 티켓 분석용 프롬프트 생성
        
        Args:
            ticket_data: 티켓 전체 데이터
            ui_language: UI 언어
            
        Returns:
            Dict[str, str]: {'system': 시스템 프롬프트, 'user': 사용자 프롬프트}
        """
        try:
            template_data = self.anthropic_templates['ticket_analysis']['system']
            
            # 시스템 프롬프트 선택
            system_prompts = template_data.get('system_prompts', {})
            system_prompt = system_prompts.get(ui_language, system_prompts.get('ko', ''))
            
            # 사용자 프롬프트 생성
            user_template_str = template_data.get('user_prompt_template', '')
            user_template = Template(user_template_str)
            
            user_prompt = user_template.render(**ticket_data)
            
            return {
                'system': system_prompt,
                'user': user_prompt
            }
            
        except Exception as e:
            logger.error(f"종합 분석 프롬프트 생성 실패: {e}")
            return {
                'system': "You are a comprehensive ticket analysis expert.",
                'user': f"Analyze this ticket: {ticket_data}"
            }
    
    def validate_anthropic_compliance(self, generated_response: str, 
                                    template_name: str = "anthropic_ticket_view") -> Dict[str, Any]:
        """
        생성된 응답이 Anthropic 기법을 준수하는지 검증
        
        Args:
            generated_response: 생성된 응답
            template_name: 검증할 템플릿 이름
            
        Returns:
            Dict[str, Any]: 검증 결과
        """
        try:
            template_data = self.anthropic_templates[template_name]['system']
            validation_rules = template_data.get('validation_rules', {})
            
            validation_results = {
                "constitutional_compliance": self._check_constitutional_compliance(
                    generated_response, template_data.get('constitutional_principles', {})
                ),
                "xml_structure_valid": self._check_xml_structure(
                    generated_response, template_data.get('response_structure', {})
                ),
                "factual_accuracy": self._check_factual_accuracy(generated_response),
                "actionability_score": self._assess_actionability(generated_response),
                "information_completeness": self._check_information_completeness(generated_response),
                "overall_quality": 0.0
            }
            
            # 전체 품질 점수 계산
            quality_thresholds = template_data.get('quality_thresholds', {})
            scoring_criteria = quality_thresholds.get('scoring_criteria', {
                'helpfulness': 0.25,
                'harmlessness': 0.25,
                'honesty': 0.25,
                'structure': 0.25
            })
            
            validation_results['overall_quality'] = (
                validation_results['constitutional_compliance'] * scoring_criteria.get('helpfulness', 0.25) +
                validation_results['xml_structure_valid'] * scoring_criteria.get('structure', 0.25) +
                validation_results['factual_accuracy'] * scoring_criteria.get('honesty', 0.25) +
                validation_results['actionability_score'] * scoring_criteria.get('helpfulness', 0.25)
            )
            
            return validation_results
            
        except Exception as e:
            logger.error(f"Anthropic 준수 검증 실패: {e}")
            return {
                "constitutional_compliance": False,
                "xml_structure_valid": False,
                "factual_accuracy": 0.5,
                "actionability_score": 0.5,
                "overall_quality": 0.5
            }
    
    def _format_constitutional_principles(self, principles: Dict[str, List[str]]) -> str:
        """Constitutional AI 원칙을 포맷팅"""
        if not principles:
            return ""
        
        formatted = []
        for principle_type, guidelines in principles.items():
            formatted.append(f"{principle_type.upper()}:")
            for guideline in guidelines:
                formatted.append(f"- {guideline}")
            formatted.append("")
        
        return "\n".join(formatted)
    
    def _format_role_definition(self, role_def: Dict[str, Any]) -> str:
        """역할 정의를 포맷팅"""
        if not role_def:
            return ""
        
        role = role_def.get('primary_role', '')
        expertise = ", ".join(role_def.get('expertise_areas', []))
        traits = ", ".join(role_def.get('personality_traits', []))
        
        return f"""
        Primary Role: {role}
        Expertise Areas: {expertise}
        Personality Traits: {traits}
        """
    
    def _format_reasoning_framework(self, framework: Dict[str, Any]) -> str:
        """추론 프레임워크를 포맷팅"""
        if not framework:
            return ""
        
        steps = framework.get('analysis_steps', [])
        return "Analysis Steps:\n" + "\n".join([f"{i+1}. {step}" for i, step in enumerate(steps)])
    
    def _format_metadata(self, metadata: Dict[str, Any]) -> str:
        """메타데이터를 포맷팅"""
        if not metadata:
            return ""
        
        formatted_items = []
        for key, value in metadata.items():
            if value:  # 값이 있는 경우만 포함
                formatted_items.append(f"{key}: {value}")
        
        return ", ".join(formatted_items)
    
    def _format_attachments(self, attachments: List[Dict[str, Any]]) -> str:
        """첨부파일 목록을 포맷팅"""
        if not attachments:
            return ""
        
        formatted = []
        for i, attachment in enumerate(attachments, 1):
            filename = attachment.get('filename', f'첨부파일_{i}')
            file_type = attachment.get('file_type', '알 수 없음')
            size = attachment.get('size', '')
            formatted.append(f"{i}. {filename} ({file_type}) {size}")
        
        return "\n".join(formatted)
    
    def _format_conversation_history(self, history: Union[str, List[Dict[str, Any]]]) -> str:
        """대화 기록을 포맷팅"""
        if isinstance(history, str):
            return history
        
        if isinstance(history, list):
            formatted = []
            for entry in history:
                timestamp = entry.get('timestamp', '')
                author = entry.get('author', '작성자')
                content = entry.get('content', '')
                formatted.append(f"[{timestamp}] {author}: {content}")
            return "\n".join(formatted)
        
        return ""
    
    def _apply_context_adjustments(self, base_prompt: str, context: Dict[str, Any], 
                                 template_data: Dict[str, Any]) -> str:
        """컨텍스트 기반 프롬프트 동적 조정"""
        adjustments = []
        
        # 우선순위 기반 조정
        if context.get('priority') == 'high':
            adjustments.append("이 티켓은 높은 우선순위입니다. 비즈니스 임팩트와 즉시 필요한 조치를 강조해주세요.")
        
        # 고객 등급 기반 조정
        if context.get('customer_tier') == 'premium':
            adjustments.append("이 고객은 Premium 등급입니다. 특별한 주의와 신속한 처리가 필요합니다.")
        
        # 카테고리 기반 조정
        category = context.get('category', '')
        if 'technical' in category.lower():
            adjustments.append("기술적 문제입니다. 로그, 오류 코드, 시스템 상태 등 기술적 세부사항에 집중해주세요.")
        elif 'billing' in category.lower():
            adjustments.append("결제 관련 문제입니다. 금액, 거래 내역, 결제 시점 등 재무 정보에 집중해주세요.")
        
        if adjustments:
            adjustment_text = "\n".join([f"- {adj}" for adj in adjustments])
            base_prompt += f"\n\n<special_instructions>\n{adjustment_text}\n</special_instructions>"
        
        return base_prompt
    
    def _get_dynamic_adjustments(self, metadata: Dict[str, Any], 
                               adjustments_config: Dict[str, Any]) -> str:
        """동적 프롬프트 조정 생성"""
        adjustments = []
        
        for condition, instruction in adjustments_config.items():
            if self._check_condition(condition, metadata):
                if isinstance(instruction, dict) and 'additional_instruction' in instruction:
                    adjustments.append(instruction['additional_instruction'])
                else:
                    adjustments.append(str(instruction))
        
        return "\n".join(adjustments)
    
    def _check_condition(self, condition: str, metadata: Dict[str, Any]) -> bool:
        """조건 확인"""
        if condition == 'high_priority':
            return metadata.get('priority') == 'high'
        elif condition == 'premium_customer':
            return metadata.get('customer_tier') == 'premium'
        elif condition == 'technical_issue':
            category = metadata.get('category', '').lower()
            return 'technical' in category or 'api' in category
        elif condition == 'billing_issue':
            category = metadata.get('category', '').lower()
            return 'billing' in category or 'payment' in category
        
        return False
    
    def _optimize_context(self, prompt: str, optimization_config: Dict[str, Any]) -> str:
        """컨텍스트 최적화"""
        max_length = optimization_config.get('max_content_length', 8000)
        
        if len(prompt) > max_length:
            # 스마트 truncation 적용
            preserve_patterns = optimization_config.get('preserve_patterns', [])
            prompt = self._smart_truncate(prompt, max_length, preserve_patterns)
        
        return prompt
    
    def _smart_truncate(self, text: str, max_length: int, preserve_patterns: List[str]) -> str:
        """중요한 패턴을 보존하면서 텍스트 자르기"""
        if len(text) <= max_length:
            return text
        
        # 보존할 패턴들을 찾아서 표시
        preserved_segments = []
        for pattern in preserve_patterns:
            matches = re.finditer(re.escape(pattern), text, re.IGNORECASE)
            for match in matches:
                start, end = match.span()
                # 앞뒤 컨텍스트 포함
                context_start = max(0, start - 50)
                context_end = min(len(text), end + 50)
                preserved_segments.append((context_start, context_end, text[context_start:context_end]))
        
        # 중복 제거 및 정렬
        preserved_segments = sorted(list(set(preserved_segments)), key=lambda x: x[0])
        
        # 보존할 부분과 일반 텍스트 부분 구분
        if preserved_segments:
            # 보존할 부분들을 우선적으로 포함
            result = ""
            remaining_length = max_length
            
            for start, end, segment in preserved_segments:
                if remaining_length > len(segment) + 20:  # 여유 공간 확보
                    result += segment + "\n"
                    remaining_length -= len(segment) + 1
            
            # 남은 공간에 일반 텍스트 추가
            if remaining_length > 100:
                general_text = text[:remaining_length-len(result)]
                result = general_text + "\n" + result
            
            return result[:max_length]
        else:
            # 단순 자르기
            return text[:max_length]
    
    def _check_constitutional_compliance(self, response: str, 
                                       principles: Dict[str, List[str]]) -> bool:
        """Constitutional AI 원칙 준수 확인"""
        try:
            # helpful: 실행 가능한 정보 포함 확인
            helpful_indicators = ["다음 단계", "권장", "조치", "해결", "방법", "즉시", "필요"]
            has_helpful_content = any(indicator in response for indicator in helpful_indicators)
            
            # harmless: 개인정보 노출 확인
            harmful_patterns = [
                r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',  # 이메일
                r'\b\d{2,3}-\d{3,4}-\d{4}\b',  # 전화번호
                r'\b\d{3}-\d{2}-\d{4}\b',  # 주민번호 패턴
            ]
            has_harmful_content = any(re.search(pattern, response) for pattern in harmful_patterns)
            
            # honest: 불확실성 표현 확인 (적절한 경우)
            uncertainty_indicators = ["추가 확인", "불확실", "가능성", "예상", "확인 필요"]
            has_uncertainty_markers = any(indicator in response for indicator in uncertainty_indicators)
            
            return has_helpful_content and not has_harmful_content
            
        except Exception as e:
            logger.error(f"Constitutional 준수 확인 실패: {e}")
            return False
    
    def _check_xml_structure(self, response: str, structure_config: Dict[str, Any]) -> bool:
        """XML 구조 유효성 확인"""
        try:
            if not structure_config.get('use_xml_tags', False):
                return True  # XML 구조가 필수가 아님
            
            required_sections = structure_config.get('required_sections', {})
            
            for section_key, section_title in required_sections.items():
                open_tag = f"<{section_key}>"
                close_tag = f"</{section_key}>"
                
                if open_tag not in response or close_tag not in response:
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"XML 구조 확인 실패: {e}")
            return False
    
    def _check_factual_accuracy(self, response: str) -> float:
        """팩트 정확성 확인 (휴리스틱 기반)"""
        try:
            # 간단한 휴리스틱 체크
            fact_indicators = len(re.findall(r'\b\d+\b', response))  # 숫자 포함
            specific_terms = len(re.findall(r'\b[A-Z][a-z]+ [A-Z][a-z]+\b', response))  # 고유명사
            technical_terms = len(re.findall(r'\b[A-Z]{2,}\b', response))  # 기술 용어
            
            # 점수 계산 (0.0 ~ 1.0)
            score = min(1.0, (fact_indicators + specific_terms + technical_terms) / 20.0)
            return max(0.5, score)  # 최소 0.5점 보장
            
        except Exception as e:
            logger.error(f"팩트 정확성 확인 실패: {e}")
            return 0.5
    
    def _assess_actionability(self, response: str) -> float:
        """실행 가능성 평가"""
        try:
            # 실행 가능한 문구들 확인
            actionable_patterns = [
                r'다음 단계',
                r'즉시 조치',
                r'권장사항',
                r'해결 방법',
                r'확인 필요',
                r'연락.*필요',
                r'검토.*필요'
            ]
            
            actionable_count = sum(
                len(re.findall(pattern, response, re.IGNORECASE))
                for pattern in actionable_patterns
            )
            
            # 점수 계산
            score = min(1.0, actionable_count / 5.0)
            return max(0.3, score)  # 최소 0.3점 보장
            
        except Exception as e:
            logger.error(f"실행 가능성 평가 실패: {e}")
            return 0.5
    
    def _check_information_completeness(self, response: str) -> float:
        """정보 완성도 확인"""
        try:
            # 필수 정보 요소들 확인
            required_elements = [
                '문제', '원인', '해결', '인사이트',  # 한국어
                'problem', 'cause', 'solution', 'insight'  # 영어
            ]
            
            element_count = sum(
                1 for element in required_elements
                if element in response.lower()
            )
            
            # 섹션 구조 확인
            section_indicators = ['🔍', '💡', '⚡', '🎯']
            section_count = sum(
                1 for indicator in section_indicators
                if indicator in response
            )
            
            # 점수 계산
            content_score = element_count / len(required_elements)
            structure_score = min(1.0, section_count / 4.0)
            
            return (content_score + structure_score) / 2.0
            
        except Exception as e:
            logger.error(f"정보 완성도 확인 실패: {e}")
            return 0.5
    
    def get_quality_threshold(self, template_name: str = "anthropic_ticket_view") -> float:
        """품질 임계값 조회"""
        try:
            template_data = self.anthropic_templates[template_name]['system']
            quality_thresholds = template_data.get('quality_thresholds', {})
            return quality_thresholds.get('minimum_score', 0.8)
        except Exception:
            return 0.8
    
    def reload_templates(self):
        """템플릿 다시 로드 (실시간 업데이트용)"""
        try:
            self._load_anthropic_templates()
            logger.info("Anthropic 템플릿 다시 로드 완료")
        except Exception as e:
            logger.error(f"템플릿 다시 로드 실패: {e}")