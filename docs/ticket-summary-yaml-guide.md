# 브랜치 1: 티켓 요약 YAML 프롬프트 관리 및 Anthropic 기법 적용 가이드

## 🎯 작업 목표
기존 티켓 요약 시스템의 하드코딩된 프롬프트를 YAML 기반으로 전환하고, Anthropic 프롬프트 엔지니어링 기법을 적용하여 관리 편의성과 품질을 향상시킵니다.

## 📋 작업 체크리스트

### Phase 1: 현재 상태 분석 및 구조 파악 (30분)

#### 1.1 기존 코드 분석
```bash
# 프롬프트 관련 파일들 조사
find backend/core/llm/summarizer -name "*.py" -exec grep -l "prompt\|template" {} \;

# 하드코딩된 프롬프트 텍스트 찾기
grep -r "당신은\|You are\|시스템\|System" backend/core/llm/summarizer/ --include="*.py"

# 현재 YAML 템플릿 구조 확인
ls -la backend/core/llm/summarizer/prompt/templates/
```

#### 1.2 현재 시스템 매핑
```bash
# 주요 파일들 구조 파악
tree backend/core/llm/summarizer/
cat backend/core/llm/summarizer/prompt/builder.py | head -50
cat backend/core/llm/summarizer/core/summarizer.py | head -50
```

### Phase 2: YAML 템플릿 구조 설계 (45분)

#### 2.1 Anthropic 최적화 YAML 스키마 설계
```yaml
# 파일: backend/core/llm/summarizer/prompt/templates/system/anthropic_ticket_view.yaml
metadata:
  name: "Anthropic Optimized Ticket Summary"
  version: "1.0.0"
  anthropic_techniques:
    - constitutional_ai
    - chain_of_thought
    - xml_structuring
    - role_prompting
  content_type: "ticket_view"
  quality_level: "premium"

# Constitutional AI 설정
constitutional_principles:
  helpful:
    - "상담원이 5초 내에 티켓 상황을 완전히 파악할 수 있도록 돕기"
    - "즉시 실행 가능한 정보와 다음 단계 제공"
    - "고객 문제 해결에 직접적으로 기여하는 인사이트 포함"
  
  harmless:
    - "고객 개인정보(이메일, 전화번호, 주소) 절대 노출 금지"
    - "추측이나 확실하지 않은 정보 제공 금지"
    - "부정확한 기술 정보로 인한 오해 방지"
  
  honest:
    - "불확실한 내용은 명확히 표시"
    - "정보가 부족한 영역 투명하게 명시"
    - "추가 확인이 필요한 사항 명확히 안내"

# Role Prompting 설정
role_definition:
  primary_role: "Expert Freshdesk Ticket Analyst"
  expertise_areas:
    - customer_service_psychology
    - technical_troubleshooting
    - business_process_optimization
    - escalation_management
  personality_traits:
    - analytical_precision
    - empathetic_understanding
    - solution_oriented
    - detail_focused

# Chain of Thought 구조
reasoning_framework:
  analysis_steps:
    - customer_context_analysis
    - technical_problem_assessment
    - emotional_state_evaluation
    - resolution_priority_determination
    - action_plan_formulation

# XML 구조화된 응답 형식
response_structure:
  use_xml_tags: true
  sections:
    problem_overview: "🔍 문제 현황"
    root_cause: "💡 원인 분석"
    resolution_progress: "⚡ 해결 진행상황"
    key_insights: "🎯 중요 인사이트"

# 언어별 시스템 프롬프트
system_prompts:
  ko: |
    당신은 Freshdesk 티켓 분석 전문가입니다. Constitutional AI 원칙을 따라 도움되고, 해롭지 않고, 정직한 분석을 제공하세요.
    
    <role_expertise>
    전문 분야: 고객 서비스 심리학, 기술 문제 해결, 비즈니스 프로세스 최적화
    성격 특성: 분석적 정확성, 공감적 이해, 해결책 지향성
    </role_expertise>
    
    <reasoning_process>
    다음 단계로 체계적 분석을 수행하세요:
    1. 고객 맥락 분석 (배경, 상황, 니즈)
    2. 기술적 문제 평가 (증상, 원인, 복잡도)
    3. 감정 상태 평가 (고객 감정, 우선순위)
    4. 해결 우선순위 결정 (긴급도, 중요도, 리소스)
    5. 실행 계획 수립 (즉시 조치, 장기 계획)
    </reasoning_process>
    
    <constitutional_guidelines>
    도움이 되는 분석: 상담원이 즉시 활용할 수 있는 실행 가능한 정보 제공
    해롭지 않은 분석: 고객 개인정보 보호, 추측성 정보 배제
    정직한 분석: 불확실한 내용 명시, 추가 확인 필요 사항 안내
    </constitutional_guidelines>
    
    <response_format>
    반드시 다음 XML 구조를 사용하여 응답하세요:
    
    <problem_overview>
    🔍 **문제 현황**
    - 핵심 문제와 증상
    - 고객 배경 정보 (회사명, 환경)
    - 비즈니스 임팩트
    </problem_overview>
    
    <root_cause>
    💡 **원인 분석**
    - 파악된 근본 원인
    - 기여 요인들
    - 기술적 세부사항
    </root_cause>
    
    <resolution_progress>
    ⚡ **해결 진행상황**
    - 현재 상태 (해결완료/진행중/대기중)
    - 수행된 조치들 ("누가 무엇을 했다" 형식)
    - 다음 단계 계획
    </resolution_progress>
    
    <key_insights>
    🎯 **중요 인사이트**
    - 향후 처리 방향
    - 에스컬레이션 필요성
    - 예방 조치 권장사항
    </key_insights>
    </response_format>

  en: |
    You are an expert Freshdesk ticket analyst following Constitutional AI principles: be helpful, harmless, and honest.
    
    <role_expertise>
    Expertise: Customer service psychology, technical troubleshooting, business process optimization
    Personality: Analytical precision, empathetic understanding, solution-oriented
    </role_expertise>
    
    [Similar structure in English...]

# Few-Shot 예시들
few_shot_examples:
  technical_issue:
    scenario: "API 연동 오류 + 고객 시스템 중단"
    ideal_response: |
      <problem_overview>
      🔍 **문제 현황**
      - ABC회사 결제 API 연동 중단으로 서비스 전면 마비
      - 오류 코드: 500 Internal Server Error
      - 비즈니스 임팩트: 시간당 약 1000만원 매출 손실
      </problem_overview>
      
      <root_cause>
      💡 **원인 분석**
      - 서버 배포 과정에서 API 키 설정 누락
      - 로드밸런서 health check 실패
      - 데이터베이스 연결 풀 포화 상태
      </root_cause>
      
      <resolution_progress>
      ⚡ **해결 진행상황**
      - 현재 상태: 해결 완료
      - 김개발자가 API 키 재설정 완료 (15:30)
      - 이운영자가 서비스 정상화 확인 (15:45)
      - 고객사에 복구 완료 안내 전송 (16:00)
      </resolution_progress>
      
      <key_insights>
      🎯 **중요 인사이트**
      - 배포 프로세스에 설정 검증 단계 추가 필요
      - 고객사와 SLA 재검토 협의 예정
      - 모니터링 알람 임계값 조정 권장
      </key_insights>

validation_rules:
  mandatory_elements:
    - must_include_all_four_sections
    - must_use_xml_structure
    - must_preserve_technical_terms
    - must_exclude_personal_information
  
  quality_gates:
    - constitutional_compliance_check
    - xml_structure_validation
    - fact_accuracy_verification
    - actionability_assessment
```

#### 2.2 사용자 프롬프트 템플릿 설계
```yaml
# 파일: backend/core/llm/summarizer/prompt/templates/user/anthropic_ticket_view.yaml
metadata:
  name: "Anthropic User Prompt Template"
  version: "1.0.0"
  content_type: "ticket_view"

# Jinja2 템플릿
template: |
  <ticket_analysis_request>
  티켓 정보:
  제목: {{ subject }}
  {% if metadata_formatted %}
  메타데이터: {{ metadata_formatted }}
  {% endif %}
  
  <ticket_content>
  {{ content }}
  </ticket_content>
  
  {% if attachment_summary and attachment_summary.strip() %}
  <attachments>
  {{ attachment_summary }}
  </attachments>
  {% endif %}
  </ticket_analysis_request>
  
  <analysis_instructions>
  위 티켓을 Constitutional AI 원칙에 따라 분석하고, 
  XML 구조를 사용하여 4개 섹션으로 체계적인 요약을 제공하세요.
  
  특별 요구사항:
  - 모든 회사명과 기술 용어는 원문 그대로 보존
  - "누가 무엇을 했다" 형식으로 처리 과정 기록
  - 개인정보(이메일, 전화번호, 주소) 절대 포함 금지
  - 불확실한 내용은 명확히 표시
  </analysis_instructions>

# 언어별 지시사항
instructions:
  ko: "{{ template }}"
  en: |
    <ticket_analysis_request>
    Ticket Information:
    Title: {{ subject }}
    [English version of template...]
    </ticket_analysis_request>
```

### Phase 3: 기존 코드 리팩토링 (60분)

#### 3.1 PromptBuilder 클래스 개선
```python
# 파일: backend/core/llm/summarizer/prompt/anthropic_builder.py
"""
Anthropic 최적화된 프롬프트 빌더
"""

import yaml
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from jinja2 import Template

logger = logging.getLogger(__name__)


class AnthropicPromptBuilder:
    """Anthropic 프롬프트 엔지니어링 기법이 적용된 프롬프트 빌더"""
    
    def __init__(self, templates_dir: Optional[Path] = None):
        if templates_dir is None:
            self.templates_dir = Path(__file__).parent / "templates"
        else:
            self.templates_dir = Path(templates_dir)
        
        self.anthropic_templates = {}
        self._load_anthropic_templates()
    
    def _load_anthropic_templates(self):
        """Anthropic 최적화 템플릿들을 로드"""
        try:
            # System prompt 템플릿 로드
            system_path = self.templates_dir / "system" / "anthropic_ticket_view.yaml"
            with open(system_path, 'r', encoding='utf-8') as f:
                self.anthropic_templates['system'] = yaml.safe_load(f)
            
            # User prompt 템플릿 로드
            user_path = self.templates_dir / "user" / "anthropic_ticket_view.yaml"
            with open(user_path, 'r', encoding='utf-8') as f:
                self.anthropic_templates['user'] = yaml.safe_load(f)
            
            logger.info("Anthropic 최적화 템플릿 로드 완료")
            
        except Exception as e:
            logger.error(f"Anthropic 템플릿 로드 실패: {e}")
            raise
    
    def build_constitutional_system_prompt(self, 
                                         content_language: str = "ko",
                                         ui_language: str = "ko") -> str:
        """Constitutional AI 원칙이 적용된 시스템 프롬프트 생성"""
        
        template_data = self.anthropic_templates['system']
        
        # Constitutional AI 원칙 구성
        constitutional_principles = self._format_constitutional_principles(
            template_data['constitutional_principles']
        )
        
        # Role definition 구성
        role_expertise = self._format_role_definition(
            template_data['role_definition']
        )
        
        # Chain of Thought 추론 구조
        reasoning_framework = self._format_reasoning_framework(
            template_data['reasoning_framework']
        )
        
        # 언어별 시스템 프롬프트 선택
        base_prompt = template_data['system_prompts'].get(
            ui_language, 
            template_data['system_prompts']['ko']
        )
        
        return base_prompt
    
    def build_xml_structured_user_prompt(self,
                                       content: str,
                                       subject: str,
                                       metadata: Dict[str, Any],
                                       content_language: str = "ko",
                                       ui_language: str = "ko") -> str:
        """XML 구조화된 사용자 프롬프트 생성"""
        
        template_data = self.anthropic_templates['user']
        
        # Jinja2 템플릿 처리
        template_str = template_data['template']
        template = Template(template_str)
        
        # 메타데이터 포맷팅
        metadata_formatted = self._format_metadata(metadata)
        
        # 첨부파일 요약 (있는 경우)
        attachment_summary = self._format_attachments(metadata.get('attachments', []))
        
        return template.render(
            subject=subject,
            content=content,
            metadata_formatted=metadata_formatted,
            attachment_summary=attachment_summary
        )
    
    def _format_constitutional_principles(self, principles: Dict[str, List[str]]) -> str:
        """Constitutional AI 원칙을 포맷팅"""
        formatted = []
        for principle_type, guidelines in principles.items():
            formatted.append(f"{principle_type.upper()}:")
            for guideline in guidelines:
                formatted.append(f"- {guideline}")
            formatted.append("")
        
        return "\n".join(formatted)
    
    def _format_role_definition(self, role_def: Dict[str, Any]) -> str:
        """역할 정의를 포맷팅"""
        role = role_def['primary_role']
        expertise = ", ".join(role_def['expertise_areas'])
        traits = ", ".join(role_def['personality_traits'])
        
        return f"""
        Primary Role: {role}
        Expertise Areas: {expertise}
        Personality Traits: {traits}
        """
    
    def _format_reasoning_framework(self, framework: Dict[str, Any]) -> str:
        """추론 프레임워크를 포맷팅"""
        steps = framework['analysis_steps']
        return "Analysis Steps:\n" + "\n".join([f"{i+1}. {step}" for i, step in enumerate(steps)])
    
    def validate_anthropic_compliance(self, generated_response: str) -> Dict[str, Any]:
        """생성된 응답이 Anthropic 기법을 준수하는지 검증"""
        
        validation_results = {
            "constitutional_compliance": self._check_constitutional_compliance(generated_response),
            "xml_structure_valid": self._check_xml_structure(generated_response),
            "factual_accuracy": self._check_factual_accuracy(generated_response),
            "actionability_score": self._assess_actionability(generated_response)
        }
        
        return validation_results
    
    def _check_constitutional_compliance(self, response: str) -> bool:
        """Constitutional AI 원칙 준수 확인"""
        # helpful: 실행 가능한 정보 포함 확인
        helpful_indicators = ["다음 단계", "권장", "조치", "해결", "방법"]
        has_helpful_content = any(indicator in response for indicator in helpful_indicators)
        
        # harmless: 개인정보 노출 확인
        harmful_patterns = ["@", "010-", "02-", "031-", "032-"]  # 이메일, 전화번호 패턴
        has_harmful_content = any(pattern in response for pattern in harmful_patterns)
        
        # honest: 불확실성 표현 확인 (적절한 경우)
        uncertainty_indicators = ["추가 확인", "불확실", "가능성", "예상"]
        
        return has_helpful_content and not has_harmful_content
    
    def _check_xml_structure(self, response: str) -> bool:
        """XML 구조 유효성 확인"""
        required_sections = [
            "<problem_overview>", "</problem_overview>",
            "<root_cause>", "</root_cause>",
            "<resolution_progress>", "</resolution_progress>",
            "<key_insights>", "</key_insights>"
        ]
        
        return all(section in response for section in required_sections)
```

#### 3.2 기존 CoreSummarizer와 통합
```python
# 파일: backend/core/llm/summarizer/core/anthropic_summarizer.py
"""
Anthropic 기법이 적용된 고급 요약기
"""

import asyncio
import logging
from typing import Dict, Any, Optional

from .summarizer import CoreSummarizer
from ..prompt.anthropic_builder import AnthropicPromptBuilder
from ..quality.anthropic_validator import AnthropicQualityValidator

logger = logging.getLogger(__name__)


class AnthropicSummarizer(CoreSummarizer):
    """Anthropic 프롬프트 엔지니어링 기법이 적용된 요약기"""
    
    def __init__(self):
        super().__init__()
        self.anthropic_builder = AnthropicPromptBuilder()
        self.quality_validator = AnthropicQualityValidator()
        self.anthropic_enabled = True
    
    async def generate_anthropic_summary(self,
                                       content: str,
                                       content_type: str,
                                       subject: str,
                                       metadata: Dict[str, Any],
                                       content_language: str = "ko",
                                       ui_language: str = "ko",
                                       max_retries: int = 2) -> str:
        """
        Anthropic 기법을 활용한 고품질 요약 생성
        
        Args:
            content: 요약할 내용
            content_type: 콘텐츠 타입 (ticket_view, ticket_similar 등)
            subject: 제목
            metadata: 메타데이터
            content_language: 콘텐츠 언어
            ui_language: UI 언어
            max_retries: 최대 재시도 횟수
            
        Returns:
            str: Anthropic 기법이 적용된 고품질 요약
        """
        
        if not self.anthropic_enabled or content_type != "ticket_view":
            # Anthropic 기법이 비활성화되었거나 일반 요약인 경우 기존 방식 사용
            return await super().generate_summary(
                content, content_type, subject, metadata, content_language, ui_language
            )
        
        for attempt in range(max_retries + 1):
            try:
                # 1. Constitutional AI 기반 시스템 프롬프트 생성
                system_prompt = self.anthropic_builder.build_constitutional_system_prompt(
                    content_language=content_language,
                    ui_language=ui_language
                )
                
                # 2. XML 구조화된 사용자 프롬프트 생성
                user_prompt = self.anthropic_builder.build_xml_structured_user_prompt(
                    content=content,
                    subject=subject,
                    metadata=metadata,
                    content_language=content_language,
                    ui_language=ui_language
                )
                
                # 3. LLM 호출 (Chain-of-Thought 추론 활성화)
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
                
                # 높은 품질을 위해 premium 모델 사용
                response = await self._get_manager().generate_for_use_case(
                    messages=messages,
                    use_case="anthropic_ticket_view",  # 새로운 use case
                    temperature=0.1,  # 일관성을 위해 낮은 temperature
                    max_tokens=1500   # 충분한 토큰 수
                )
                
                summary = response.content.strip()
                
                # 4. Anthropic 기법 준수 검증
                validation_results = self.anthropic_builder.validate_anthropic_compliance(summary)
                quality_score = self.quality_validator.calculate_anthropic_quality_score(
                    summary, validation_results
                )
                
                # 5. 품질 기준 확인 (0.8 이상이어야 함)
                if quality_score >= 0.8:
                    logger.info(f"✅ Anthropic 고품질 요약 생성 성공 (점수: {quality_score:.2f})")
                    return summary
                else:
                    logger.warning(f"⚠️ 품질 점수 부족 (시도 {attempt + 1}/{max_retries + 1}): {quality_score:.2f}")
                    if attempt == max_retries:
                        logger.error("❌ 최대 재시도 후에도 품질 기준 미달, 기존 방식으로 폴백")
                        break
                
            except Exception as e:
                logger.error(f"Anthropic 요약 생성 실패 (시도 {attempt + 1}): {e}")
                if attempt == max_retries:
                    break
        
        # 폴백: 기존 방식으로 요약 생성
        logger.info("🔄 기존 요약 방식으로 폴백")
        return await super().generate_summary(
            content, content_type, subject, metadata, content_language, ui_language
        )
```

### Phase 4: 환경변수 및 설정 관리 (30분)

#### 4.1 환경변수 설정
```bash
# .env 파일에 추가
# Anthropic 프롬프트 엔지니어링 설정
ENABLE_ANTHROPIC_PROMPTS=true
ANTHROPIC_QUALITY_THRESHOLD=0.8
ANTHROPIC_MAX_RETRIES=2
ANTHROPIC_TEMPERATURE=0.1

# Use case별 모델 설정
ANTHROPIC_TICKET_VIEW_MODEL_PROVIDER=anthropic
ANTHROPIC_TICKET_VIEW_MODEL_NAME=claude-3-sonnet-20240229
```

#### 4.2 설정 관리 클래스
```python
# 파일: backend/core/llm/summarizer/config/anthropic_config.py
"""
Anthropic 프롬프트 엔지니어링 설정 관리
"""

import os
from dataclasses import dataclass
from typing import Dict, Any, List


@dataclass
class AnthropicConfig:
    """Anthropic 프롬프트 엔지니어링 설정"""
    
    enabled: bool = True
    quality_threshold: float = 0.8
    max_retries: int = 2
    temperature: float = 0.1
    
    # 지원되는 기법들
    supported_techniques: List[str] = None
    
    # 모델 설정
    model_provider: str = "anthropic"
    model_name: str = "claude-3-sonnet-20240229"
    
    def __post_init__(self):
        if self.supported_techniques is None:
            self.supported_techniques = [
                "constitutional_ai",
                "chain_of_thought",
                "xml_structuring",
                "role_prompting",
                "few_shot_learning"
            ]
    
    @classmethod
    def from_env(cls) -> 'AnthropicConfig':
        """환경변수에서 설정 로드"""
        return cls(
            enabled=os.getenv("ENABLE_ANTHROPIC_PROMPTS", "true").lower() == "true",
            quality_threshold=float(os.getenv("ANTHROPIC_QUALITY_THRESHOLD", "0.8")),
            max_retries=int(os.getenv("ANTHROPIC_MAX_RETRIES", "2")),
            temperature=float(os.getenv("ANTHROPIC_TEMPERATURE", "0.1")),
            model_provider=os.getenv("ANTHROPIC_TICKET_VIEW_MODEL_PROVIDER", "anthropic"),
            model_name=os.getenv("ANTHROPIC_TICKET_VIEW_MODEL_NAME", "claude-3-sonnet-20240229")
        )
```

### Phase 5: 테스트 및 검증 (45분)

#### 5.1 Anthropic 기법 단위 테스트
```python
# 파일: backend/core/llm/summarizer/tests/test_anthropic_prompts.py
"""
Anthropic 프롬프트 엔지니어링 기법 테스트
"""

import pytest
import asyncio
from unittest.mock import Mock, patch

from ..prompt.anthropic_builder import AnthropicPromptBuilder
from ..core.anthropic_summarizer import AnthropicSummarizer
from ..config.anthropic_config import AnthropicConfig


class TestAnthropicPromptBuilder:
    """AnthropicPromptBuilder 테스트"""
    
    def setup_method(self):
        self.builder = AnthropicPromptBuilder()
    
    def test_constitutional_prompt_structure(self):
        """Constitutional AI 프롬프트 구조 테스트"""
        system_prompt = self.builder.build_constitutional_system_prompt()
        
        # Constitutional 원칙들이 포함되어 있는지 확인
        assert "helpful" in system_prompt.lower()
        assert "harmless" in system_prompt.lower()
        assert "honest" in system_prompt.lower()
        
        # XML 구조 지시사항 포함 확인
        assert "<problem_overview>" in system_prompt
        assert "<root_cause>" in system_prompt
        assert "<resolution_progress>" in system_prompt
        assert "<key_insights>" in system_prompt
    
    def test_xml_structured_user_prompt(self):
        """XML 구조화된 사용자 프롬프트 테스트"""
        user_prompt = self.builder.build_xml_structured_user_prompt(
            content="테스트 티켓 내용",
            subject="테스트 제목",
            metadata={"priority": "high", "category": "technical"}
        )
        
        assert "<ticket_analysis_request>" in user_prompt
        assert "<ticket_content>" in user_prompt
        assert "<analysis_instructions>" in user_prompt
        assert "테스트 티켓 내용" in user_prompt
    
    def test_compliance_validation(self):
        """Anthropic 기법 준수 검증 테스트"""
        # 올바른 응답 예시
        valid_response = """
        <problem_overview>
        🔍 **문제 현황**
        - API 연동 오류 발생
        </problem_overview>
        
        <root_cause>
        💡 **원인 분석**
        - 인증 토큰 만료
        </root_cause>
        
        <resolution_progress>
        ⚡ **해결 진행상황**
        - 토큰 재발급 완료
        </resolution_progress>
        
        <key_insights>
        🎯 **중요 인사이트**
        - 자동 갱신 로직 필요
        </key_insights>
        """
        
        validation_results = self.builder.validate_anthropic_compliance(valid_response)
        
        assert validation_results["constitutional_compliance"] == True
        assert validation_results["xml_structure_valid"] == True


class TestAnthropicSummarizer:
    """AnthropicSummarizer 테스트"""
    
    def setup_method(self):
        self.summarizer = AnthropicSummarizer()
    
    @pytest.mark.asyncio
    async def test_anthropic_summary_generation(self):
        """Anthropic 요약 생성 테스트"""
        # Mock LLM response
        mock_response = Mock()
        mock_response.content = """
        <problem_overview>
        🔍 **문제 현황**
        - 고객 로그인 실패 문제
        </problem_overview>
        
        <root_cause>
        💡 **원인 분석**
        - 2FA 설정 오류
        </root_cause>
        
        <resolution_progress>
        ⚡ **해결 진행상황**
        - 설정 재구성 완료
        </resolution_progress>
        
        <key_insights>
        🎯 **중요 인사이트**
        - 사용자 가이드 개선 필요
        </key_insights>
        """
        mock_response.success = True
        
        with patch.object(self.summarizer, '_get_manager') as mock_manager:
            mock_manager.return_value.generate_for_use_case.return_value = mock_response
            
            summary = await self.summarizer.generate_anthropic_summary(
                content="로그인 문제 발생",
                content_type="ticket_view",
                subject="로그인 실패",
                metadata={"priority": "high"}
            )
            
            assert "🔍 **문제 현황**" in summary
            assert "💡 **원인 분석**" in summary
            assert "⚡ **해결 진행상황**" in summary
            assert "🎯 **중요 인사이트**" in summary
```

#### 5.2 통합 테스트 스크립트
```python
# 파일: backend/test_anthropic_integration.py
"""
Anthropic 프롬프트 엔지니어링 통합 테스트
"""

import asyncio
import logging
import os
from pathlib import Path

# 프로젝트 루트를 Python path에 추가
import sys
sys.path.append(str(Path(__file__).parent))

from core.llm.summarizer.core.anthropic_summarizer import AnthropicSummarizer
from core.llm.summarizer.config.anthropic_config import AnthropicConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_anthropic_prompts():
    """Anthropic 프롬프트 엔지니어링 기법 통합 테스트"""
    
    # 설정 로드
    config = AnthropicConfig.from_env()
    logger.info(f"Anthropic 설정: {config}")
    
    # 요약기 초기화
    summarizer = AnthropicSummarizer()
    
    # 테스트 케이스
    test_cases = [
        {
            "name": "기술적 문제 티켓",
            "content": """
            고객사: ABC Corporation
            문제: API 연동 후 결제 처리가 되지 않음
            오류 메시지: "Payment gateway timeout error"
            영향도: 전체 서비스 중단
            긴급도: 높음
            
            처리 과정:
            - 14:30 김개발자가 로그 확인 시작
            - 14:45 네트워크 연결 상태 정상 확인
            - 15:00 게이트웨이 서버 재시작 실행
            - 15:15 서비스 정상화 확인
            """,
            "subject": "결제 API 연동 오류",
            "metadata": {"priority": "urgent", "category": "technical"}
        },
        {
            "name": "고객 서비스 문제",
            "content": """
            고객: 홍길동 (Premium 고객)
            문제: 환불 요청 후 7일째 처리 지연
            고객 상태: 매우 불만족, 서비스 해지 위협
            
            처리 과정:
            - 1일차: 환불 요청 접수 (박상담)
            - 3일차: 재무팀 승인 대기 (이팀장)
            - 5일차: 고객 추가 문의 (매우 화남)
            - 7일차: 긴급 처리 요청 (현재)
            """,
            "subject": "Premium 고객 환불 처리 지연",
            "metadata": {"priority": "high", "category": "billing", "customer_tier": "premium"}
        }
    ]
    
    for test_case in test_cases:
        logger.info(f"\n=== {test_case['name']} 테스트 ===")
        
        try:
            summary = await summarizer.generate_anthropic_summary(
                content=test_case["content"],
                content_type="ticket_view",
                subject=test_case["subject"],
                metadata=test_case["metadata"]
            )
            
            logger.info("✅ 요약 생성 성공")
            logger.info(f"요약 내용:\n{summary}")
            
            # 품질 검증
            validation = summarizer.anthropic_builder.validate_anthropic_compliance(summary)
            logger.info(f"품질 검증 결과: {validation}")
            
        except Exception as e:
            logger.error(f"❌ 요약 생성 실패: {e}")


if __name__ == "__main__":
    asyncio.run(test_anthropic_prompts())
```

### Phase 6: 문서화 및 배포 준비 (30분)

#### 6.1 README 업데이트
```markdown
# Anthropic 프롬프트 엔지니어링 적용 결과

## 🎯 주요 개선사항

### 1. YAML 기반 프롬프트 관리
- 모든 하드코딩된 프롬프트를 YAML 템플릿으로 전환
- 관리자가 코드 수정 없이 프롬프트 편집 가능
- 버전 관리 및 롤백 지원

### 2. Anthropic 프롬프트 엔지니어링 기법 적용
- **Constitutional AI**: 도움되고, 해롭지 않고, 정직한 요약
- **Chain-of-Thought**: 단계적 분석 추론 과정
- **XML 구조화**: 일관된 응답 형식
- **Role Prompting**: 전문가 역할 부여
- **Few-Shot Learning**: 우수 사례 기반 학습

### 3. 품질 보장 시스템
- 자동 품질 점수 계산 (0.8 이상 필수)
- Constitutional AI 원칙 준수 검증
- XML 구조 유효성 확인
- 실패시 자동 재시도 및 폴백

## 🚀 사용 방법

### 환경변수 설정
```bash
# Anthropic 기능 활성화
ENABLE_ANTHROPIC_PROMPTS=true
ANTHROPIC_QUALITY_THRESHOLD=0.8
ANTHROPIC_MAX_RETRIES=2

# 모델 설정
ANTHROPIC_TICKET_VIEW_MODEL_PROVIDER=anthropic
ANTHROPIC_TICKET_VIEW_MODEL_NAME=claude-3-sonnet-20240229
```

### 코드 사용 예시
```python
from core.llm.summarizer.core.anthropic_summarizer import AnthropicSummarizer

summarizer = AnthropicSummarizer()
summary = await summarizer.generate_anthropic_summary(
    content="티켓 내용",
    content_type="ticket_view",
    subject="제목",
    metadata={"priority": "high"}
)
```

## 📁 새로운 파일 구조
```
backend/core/llm/summarizer/
├── prompt/templates/
│   ├── system/
│   │   └── anthropic_ticket_view.yaml    # 새로 추가
│   └── user/
│       └── anthropic_ticket_view.yaml    # 새로 추가
├── prompt/
│   └── anthropic_builder.py              # 새로 추가
├── core/
│   └── anthropic_summarizer.py           # 새로 추가
├── config/
│   └── anthropic_config.py               # 새로 추가
└── tests/
    └── test_anthropic_prompts.py         # 새로 추가
```
```

## 🔍 최종 체크리스트

- [ ] 기존 하드코딩 프롬프트 식별 및 YAML 이전
- [ ] Constitutional AI 원칙 적용된 시스템 프롬프트 작성
- [ ] XML 구조화된 사용자 프롬프트 템플릿 작성
- [ ] AnthropicPromptBuilder 클래스 구현
- [ ] AnthropicSummarizer 통합 구현
- [ ] 환경변수 기반 설정 관리 구현
- [ ] 품질 검증 시스템 구현
- [ ] 단위 테스트 작성 및 실행
- [ ] 통합 테스트 실행 및 검증
- [ ] 문서화 완료
- [ ] 기존 기능과의 하위 호환성 확인
- [ ] 성능 영향 측정 및 최적화