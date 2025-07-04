"""
Anthropic 프롬프트 엔지니어링 기법 테스트

Constitutional AI, XML 구조화, 품질 검증 등 
Anthropic 기법들의 단위 테스트를 포함합니다.
"""

import pytest
import asyncio
import yaml
import json
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path
from datetime import datetime

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from core.llm.summarizer.prompt.anthropic_builder import AnthropicPromptBuilder
from core.llm.summarizer.core.anthropic_summarizer import AnthropicSummarizer
from core.llm.summarizer.quality.anthropic_validator import AnthropicQualityValidator
from core.llm.summarizer.config.anthropic_config import AnthropicConfig
from core.llm.summarizer.config.settings import AnthropicSettings


class TestAnthropicPromptBuilder:
    """AnthropicPromptBuilder 테스트"""
    
    def setup_method(self):
        """테스트 설정"""
        self.builder = AnthropicPromptBuilder()
        
        # 테스트용 템플릿 데이터
        self.test_system_template = {
            'constitutional_principles': {
                'helpful': ['상담원이 5초 내에 파악할 수 있도록 돕기'],
                'harmless': ['개인정보 절대 노출 금지'],
                'honest': ['불확실한 내용은 명확히 표시']
            },
            'role_definition': {
                'primary_role': 'Expert Freshdesk Ticket Analyst',
                'expertise_areas': ['customer_service_psychology', 'technical_troubleshooting'],
                'personality_traits': ['analytical_precision', 'empathetic_understanding']
            },
            'reasoning_framework': {
                'analysis_steps': [
                    'customer_context_analysis',
                    'technical_problem_assessment',
                    'resolution_priority_determination'
                ]
            },
            'response_structure': {
                'use_xml_tags': True,
                'required_sections': {
                    'problem_overview': '🔍 문제 현황',
                    'root_cause': '💡 원인 분석',
                    'resolution_progress': '⚡ 해결 진행상황',
                    'key_insights': '🎯 중요 인사이트'
                }
            },
            'system_prompts': {
                'ko': '당신은 Freshdesk 티켓 분석 전문가입니다.',
                'en': 'You are an expert Freshdesk ticket analyst.'
            }
        }
    
    def test_constitutional_prompt_structure(self):
        """Constitutional AI 프롬프트 구조 테스트"""
        # Mock 템플릿 데이터 설정
        with patch.object(self.builder, 'anthropic_templates') as mock_templates:
            mock_templates.__getitem__.return_value = {
                'system': self.test_system_template
            }
            
            system_prompt = self.builder.build_constitutional_system_prompt()
            
            # Constitutional 원칙들이 포함되어 있는지 확인
            assert "Freshdesk 티켓 분석 전문가" in system_prompt
            assert len(system_prompt) > 100  # 충분한 길이
    
    def test_xml_structured_user_prompt(self):
        """XML 구조화된 사용자 프롬프트 테스트"""
        test_user_template = {
            'template': '''
            <ticket_analysis_request>
            티켓 제목: {{ subject }}
            <ticket_content>{{ content }}</ticket_content>
            </ticket_analysis_request>
            ''',
            'dynamic_adjustments': {},
            'context_optimization': {'max_content_length': 8000}
        }
        
        with patch.object(self.builder, 'anthropic_templates') as mock_templates:
            mock_templates.__getitem__.return_value = {
                'user': test_user_template
            }
            
            user_prompt = self.builder.build_xml_structured_user_prompt(
                content="테스트 티켓 내용",
                subject="테스트 제목",
                metadata={"priority": "high", "category": "technical"}
            )
            
            assert "<ticket_analysis_request>" in user_prompt
            assert "<ticket_content>" in user_prompt
            assert "테스트 티켓 내용" in user_prompt
            assert "테스트 제목" in user_prompt
    
    def test_compliance_validation(self):
        """Anthropic 기법 준수 검증 테스트"""
        # 올바른 응답 예시
        valid_response = """
        <problem_overview>
        🔍 **문제 현황**
        - ABC회사 API 연동 오류 발생
        - 비즈니스 임팩트: 매출 손실
        </problem_overview>
        
        <root_cause>
        💡 **원인 분석**
        - 인증 토큰 만료로 확인됨
        </root_cause>
        
        <resolution_progress>
        ⚡ **해결 진행상황**
        - 김개발자가 토큰 재발급 완료 (15:30)
        - 서비스 정상화 확인 (15:45)
        </resolution_progress>
        
        <key_insights>
        🎯 **중요 인사이트**
        - 자동 토큰 갱신 시스템 도입 필요
        </key_insights>
        """
        
        with patch.object(self.builder, 'anthropic_templates') as mock_templates:
            mock_templates.__getitem__.return_value = {
                'system': self.test_system_template
            }
            
            validation_results = self.builder.validate_anthropic_compliance(
                valid_response, "anthropic_ticket_view"
            )
            
            assert validation_results["constitutional_compliance"] == True
            assert validation_results["xml_structure_valid"] == True
            assert validation_results["overall_quality"] > 0.7
    
    def test_invalid_response_detection(self):
        """잘못된 응답 감지 테스트"""
        # 개인정보가 포함된 잘못된 응답
        invalid_response = """
        문제: 로그인 실패
        고객 이메일: test@example.com
        전화번호: 010-1234-5678
        아마도 비밀번호 문제인 것 같습니다.
        """
        
        with patch.object(self.builder, 'anthropic_templates') as mock_templates:
            mock_templates.__getitem__.return_value = {
                'system': self.test_system_template
            }
            
            validation_results = self.builder.validate_anthropic_compliance(
                invalid_response, "anthropic_ticket_view"
            )
            
            assert validation_results["constitutional_compliance"] == False
            assert validation_results["xml_structure_valid"] == False
            assert validation_results["overall_quality"] < 0.5
    
    def test_metadata_formatting(self):
        """메타데이터 포맷팅 테스트"""
        metadata = {
            "priority": "high",
            "category": "technical", 
            "company": "ABC Corporation",
            "empty_field": ""
        }
        
        formatted = self.builder._format_metadata(metadata)
        
        assert "priority: high" in formatted
        assert "category: technical" in formatted
        assert "company: ABC Corporation" in formatted
        assert "empty_field" not in formatted  # 빈 값은 제외
    
    def test_smart_truncation(self):
        """스마트 truncation 테스트"""
        long_text = "A" * 10000 + " 오류 메시지 중요함 " + "B" * 5000
        preserve_patterns = ["오류 메시지"]
        
        truncated = self.builder._smart_truncate(long_text, 1000, preserve_patterns)
        
        assert len(truncated) <= 1000
        assert "오류 메시지" in truncated  # 중요한 패턴은 보존


class TestAnthropicSummarizer:
    """AnthropicSummarizer 테스트"""
    
    def setup_method(self):
        """테스트 설정"""
        # Mock config로 초기화
        mock_config = AnthropicConfig()
        mock_config.enabled = True
        mock_config.quality_threshold = 0.8
        
        self.summarizer = AnthropicSummarizer(mock_config)
    
    @pytest.mark.asyncio
    async def test_anthropic_summary_generation(self):
        """Anthropic 요약 생성 테스트"""
        # Mock LLM response
        mock_response = Mock()
        mock_response.content = """
        <problem_overview>
        🔍 **문제 현황**
        - 고객 로그인 실패 문제
        - 비즈니스 임팩트: 업무 중단
        </problem_overview>
        
        <root_cause>
        💡 **원인 분석**
        - 2FA 설정 오류로 확인
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
        
        # Mock builder와 validator
        with patch.object(self.summarizer, '_anthropic_summarizer', AsyncMock()) as mock_summarizer_attr:
            with patch.object(self.summarizer, '_call_anthropic_llm', return_value=mock_response) as mock_llm:
                with patch.object(self.summarizer.anthropic_builder, 'validate_anthropic_compliance') as mock_validate:
                    with patch.object(self.summarizer.quality_validator, 'calculate_anthropic_quality_score', return_value=0.85) as mock_quality:
                        
                        mock_validate.return_value = {
                            'constitutional_compliance': True,
                            'xml_structure_valid': True,
                            'factual_accuracy': 0.8,
                            'actionability_score': 0.9
                        }
                        
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
    
    @pytest.mark.asyncio
    async def test_quality_threshold_enforcement(self):
        """품질 임계값 적용 테스트"""
        # 낮은 품질의 Mock response
        mock_response = Mock()
        mock_response.content = "간단한 응답"
        mock_response.success = True
        
        with patch.object(self.summarizer, '_call_anthropic_llm', return_value=mock_response):
            with patch.object(self.summarizer.anthropic_builder, 'validate_anthropic_compliance') as mock_validate:
                with patch.object(self.summarizer.quality_validator, 'calculate_anthropic_quality_score', return_value=0.5) as mock_quality:
                    with patch.object(self.summarizer, '_fallback_to_standard_summary', return_value="폴백 요약") as mock_fallback:
                        
                        mock_validate.return_value = {
                            'constitutional_compliance': False,
                            'xml_structure_valid': False
                        }
                        
                        summary = await self.summarizer.generate_anthropic_summary(
                            content="테스트 내용",
                            content_type="ticket_view", 
                            subject="테스트",
                            metadata={}
                        )
                        
                        # 품질이 낮아서 폴백이 호출되어야 함
                        mock_fallback.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_realtime_summary_generation(self):
        """실시간 요약 생성 테스트"""
        test_summary = """
        🚨 **긴급도**: 높음
        📋 **핵심 문제**: API 연동 오류
        👤 **고객 상태**: ABC회사 - 불만족
        ⚡ **즉시 조치**: 개발팀 컨택 필요
        💼 **비즈니스 영향**: 매출 손실
        """
        
        with patch.object(self.summarizer.anthropic_builder, 'build_realtime_summary_prompt') as mock_builder:
            with patch.object(self.summarizer, '_call_fast_llm') as mock_llm:
                
                mock_builder.return_value = {
                    'system': '실시간 요약 시스템 프롬프트',
                    'user': '실시간 요약 사용자 프롬프트'
                }
                
                mock_response = Mock()
                mock_response.content = test_summary
                mock_response.success = True
                mock_llm.return_value = mock_response
                
                summary = await self.summarizer.generate_realtime_summary(
                    content="API 오류 발생",
                    subject="긴급 문제"
                )
                
                assert "🚨 **긴급도**" in summary
                assert "💼 **비즈니스 영향**" in summary
    
    @pytest.mark.asyncio
    async def test_attachment_selection(self):
        """첨부파일 선별 테스트"""
        test_attachments = [
            {"filename": "error_log.txt", "file_type": "text"},
            {"filename": "screenshot.png", "file_type": "image"},
            {"filename": "config.json", "file_type": "json"}
        ]
        
        mock_result = {
            "selected_attachments": [
                {
                    "filename": "error_log.txt",
                    "selection_reason": "문제 해결에 필요한 로그 파일",
                    "relevance_score": 0.9,
                    "priority": "high"
                }
            ],
            "total_selected": 1,
            "confidence_score": 0.85
        }
        
        with patch.object(self.summarizer.anthropic_builder, 'build_attachment_selection_prompt') as mock_builder:
            with patch.object(self.summarizer, '_call_anthropic_llm') as mock_llm:
                
                mock_builder.return_value = {
                    'system': '첨부파일 선별 시스템 프롬프트',
                    'user': '첨부파일 선별 사용자 프롬프트'
                }
                
                mock_response = Mock()
                mock_response.content = json.dumps(mock_result)
                mock_response.success = True
                mock_llm.return_value = mock_response
                
                result = await self.summarizer.select_relevant_attachments(
                    content="로그 오류 발생",
                    subject="시스템 오류",
                    attachments=test_attachments
                )
                
                assert result["total_selected"] == 1
                assert "error_log.txt" in result["selected_attachments"][0]["filename"]
                assert result["confidence_score"] > 0.8


class TestAnthropicQualityValidator:
    """AnthropicQualityValidator 테스트"""
    
    def setup_method(self):
        """테스트 설정"""
        self.validator = AnthropicQualityValidator()
    
    def test_constitutional_compliance_check(self):
        """Constitutional AI 준수 확인 테스트"""
        # 도움이 되는 응답
        helpful_response = """
        다음 단계로 API 키를 확인하고 권장사항을 제시드립니다.
        즉시 조치가 필요한 해결 방법을 안내하겠습니다.
        """
        
        principles = {
            'helpful': ['즉시 활용할 수 있는 정보 제공'],
            'harmless': ['개인정보 보호'],
            'honest': ['불확실성 표시']
        }
        
        result = self.validator.validate_constitutional_ai_compliance(
            helpful_response, principles
        )
        
        assert result['helpful']['score'] > 0.7
        assert result['overall_compliance'] == True
    
    def test_harmful_content_detection(self):
        """유해 콘텐츠 감지 테스트"""
        harmful_response = """
        고객 정보: test@example.com, 010-1234-5678
        추측으로는 아마도 비밀번호 문제일 것 같습니다.
        """
        
        principles = {
            'helpful': ['도움이 되는 정보'],
            'harmless': ['개인정보 보호', '추측 금지'],
            'honest': ['사실 기반']
        }
        
        result = self.validator.validate_constitutional_ai_compliance(
            harmful_response, principles
        )
        
        assert result['harmless']['score'] < 0.5
        assert result['overall_compliance'] == False
        assert len(result['violations']) > 0
    
    def test_xml_structure_validation(self):
        """XML 구조 검증 테스트"""
        valid_xml_response = """
        <problem_overview>문제 상황</problem_overview>
        <root_cause>원인 분석</root_cause>
        <resolution_progress>진행 상황</resolution_progress>
        <key_insights>핵심 인사이트</key_insights>
        """
        
        required_sections = {
            'problem_overview': '문제 현황',
            'root_cause': '원인 분석', 
            'resolution_progress': '해결 진행상황',
            'key_insights': '중요 인사이트'
        }
        
        result = self.validator.validate_xml_structure(
            valid_xml_response, required_sections
        )
        
        assert result['valid_structure'] == True
        assert len(result['found_sections']) == 4
        assert len(result['missing_sections']) == 0
        assert result['structure_score'] > 0.9
    
    def test_incomplete_xml_structure(self):
        """불완전한 XML 구조 테스트"""
        incomplete_response = """
        <problem_overview>문제만 있음</problem_overview>
        일반 텍스트...
        """
        
        required_sections = {
            'problem_overview': '문제 현황',
            'root_cause': '원인 분석',
            'resolution_progress': '해결 진행상황', 
            'key_insights': '중요 인사이트'
        }
        
        result = self.validator.validate_xml_structure(
            incomplete_response, required_sections
        )
        
        assert result['valid_structure'] == False
        assert len(result['missing_sections']) == 3
        assert result['structure_score'] < 0.5
    
    def test_actionability_assessment(self):
        """실행 가능성 평가 테스트"""
        actionable_response = """
        다음 단계로 진행하세요:
        1. 김개발자에게 즉시 연락
        2. API 키 확인 및 재설정
        3. 30분 이내 서비스 복구 완료
        추가 확인이 필요한 사항은 팀장에게 문의하세요.
        """
        
        result = self.validator.validate_actionability(actionable_response)
        
        assert result['action_items'] > 0
        assert result['specific_steps'] > 0
        assert result['responsible_parties'] > 0
        assert result['actionability_score'] > 0.7
    
    def test_quality_score_calculation(self):
        """품질 점수 계산 테스트"""
        validation_results = {
            'constitutional_compliance': {
                'helpful': {'score': 0.9},
                'harmless': {'score': 0.8},
                'honest': {'score': 0.85}
            },
            'xml_structure_valid': True,
            'factual_accuracy': 0.8,
            'actionability_score': 0.75,
            'information_completeness': 0.9
        }
        
        quality_score = self.validator.calculate_anthropic_quality_score(
            "테스트 응답", validation_results
        )
        
        assert 0.0 <= quality_score <= 1.0
        assert quality_score > 0.7  # 높은 품질 점수 예상
    
    def test_factual_accuracy_validation(self):
        """팩트 정확성 검증 테스트"""
        factual_response = """
        2024-07-04 15:30에 오류 발생
        API 응답 코드: 500
        김개발자가 확인 완료
        서버 CPU 사용률: 85%
        """
        
        result = self.validator.validate_factual_accuracy(factual_response)
        
        assert result['fact_indicators'] > 3  # 날짜, 시간, 코드, 퍼센트
        assert result['speculation_indicators'] == 0
        assert result['accuracy_score'] > 0.6


class TestAnthropicConfig:
    """AnthropicConfig 테스트"""
    
    def test_config_creation(self):
        """설정 생성 테스트"""
        config = AnthropicConfig()
        
        assert config.enabled == True
        assert config.quality_threshold == 0.8
        assert config.max_retries == 2
        assert len(config.supported_techniques) > 0
        assert 'constitutional_ai' in config.supported_techniques
    
    def test_env_loading(self):
        """환경변수 로딩 테스트"""
        with patch.dict('os.environ', {
            'ANTHROPIC_ENABLED': 'true',
            'ANTHROPIC_QUALITY_THRESHOLD': '0.9',
            'ANTHROPIC_MAX_RETRIES': '3',
            'ANTHROPIC_TEMPERATURE': '0.2'
        }):
            config = AnthropicConfig.from_env()
            
            assert config.enabled == True
            assert config.quality_threshold == 0.9
            assert config.max_retries == 3
            assert config.temperature == 0.2
    
    def test_model_config_retrieval(self):
        """모델 설정 조회 테스트"""
        config = AnthropicConfig()
        
        # 기본값 테스트
        model_config = config.get_model_config('unknown_use_case')
        assert model_config['provider'] == config.model_provider
        assert model_config['model'] == config.model_name
        
        # 특정 사용 사례 테스트
        config.use_case_models['test_case'] = {
            'provider': 'test_provider',
            'model': 'test_model'
        }
        
        model_config = config.get_model_config('test_case')
        assert model_config['provider'] == 'test_provider'
        assert model_config['model'] == 'test_model'
    
    def test_technique_management(self):
        """기법 관리 테스트"""
        config = AnthropicConfig()
        
        # 기법 활성화 확인
        assert config.is_technique_enabled('constitutional_ai') == True
        
        # 기법 비활성화
        config.disable_technique('constitutional_ai')
        assert config.is_technique_enabled('constitutional_ai') == False
        
        # 기법 재활성화
        config.enable_technique('constitutional_ai')
        assert config.is_technique_enabled('constitutional_ai') == True
    
    def test_config_validation(self):
        """설정 유효성 검증 테스트"""
        config = AnthropicConfig()
        
        # 유효한 설정
        errors = config.validate()
        assert len(errors) == 0
        
        # 무효한 설정
        config.quality_threshold = 1.5  # 범위 초과
        config.temperature = -0.1       # 음수
        
        errors = config.validate()
        assert len(errors) > 0
        assert any('품질 임계값' in error for error in errors)
        assert any('온도값' in error for error in errors)
    
    def test_constitutional_weights_update(self):
        """Constitutional AI 가중치 업데이트 테스트"""
        config = AnthropicConfig()
        
        new_weights = {'helpful': 0.5, 'harmless': 0.3, 'honest': 0.2}
        config.update_constitutional_weights(new_weights)
        
        assert config.constitutional_weights['helpful'] == 0.5
        assert config.constitutional_weights['harmless'] == 0.3
        assert config.constitutional_weights['honest'] == 0.2
        
        # 합계가 1.0인지 확인
        total = sum(config.constitutional_weights.values())
        assert abs(total - 1.0) < 0.01
    
    def test_config_serialization(self):
        """설정 직렬화 테스트"""
        config = AnthropicConfig()
        
        # 딕셔너리로 변환
        config_dict = config.to_dict()
        assert isinstance(config_dict, dict)
        assert 'enabled' in config_dict
        assert 'quality_threshold' in config_dict
        
        # 딕셔너리에서 복원
        restored_config = AnthropicConfig.from_dict(config_dict)
        assert restored_config.enabled == config.enabled
        assert restored_config.quality_threshold == config.quality_threshold


class TestAnthropicSettings:
    """AnthropicSettings 테스트"""
    
    def setup_method(self):
        """테스트 설정"""
        self.settings = AnthropicSettings()
    
    def test_config_loading(self):
        """설정 로딩 테스트"""
        config = self.settings.load_config()
        
        assert isinstance(config, AnthropicConfig)
        assert config.enabled is not None
        assert config.quality_threshold > 0
    
    def test_config_caching(self):
        """설정 캐싱 테스트"""
        # 첫 번째 로드
        config1 = self.settings.get_config()
        
        # 두 번째 로드 (캐시에서)
        config2 = self.settings.get_config()
        
        # 같은 인스턴스여야 함
        assert config1 is config2
    
    def test_dynamic_config_update(self):
        """동적 설정 업데이트 테스트"""
        original_threshold = self.settings.get_quality_threshold()
        
        # 임계값 업데이트
        new_threshold = 0.9
        success = self.settings.update_quality_threshold(new_threshold)
        
        assert success == True
        assert self.settings.get_quality_threshold() == new_threshold
        
        # 잘못된 값으로 업데이트 시도
        invalid_success = self.settings.update_config({'quality_threshold': 1.5})
        assert invalid_success == False  # 검증 실패로 업데이트 안됨
    
    def test_technique_management(self):
        """기법 관리 테스트"""
        # 기법 상태 확인
        assert self.settings.is_technique_enabled('constitutional_ai') == True
        
        # 기법 비활성화
        self.settings.disable_technique('constitutional_ai')
        assert self.settings.is_technique_enabled('constitutional_ai') == False
        
        # 기법 재활성화
        self.settings.enable_technique('constitutional_ai')
        assert self.settings.is_technique_enabled('constitutional_ai') == True
    
    def test_model_config_retrieval(self):
        """모델 설정 조회 테스트"""
        # 기본 모델 설정
        default_config = self.settings.get_model_config('unknown_use_case')
        assert 'provider' in default_config
        assert 'model' in default_config
        
        # 특정 사용 사례 설정
        ticket_view_config = self.settings.get_model_config('anthropic_ticket_view')
        assert 'provider' in ticket_view_config
        assert 'model' in ticket_view_config
    
    def test_admin_settings_retrieval(self):
        """관리자 설정 조회 테스트"""
        admin_settings = self.settings.get_admin_settings()
        
        required_keys = [
            'web_interface_enabled',
            'api_access_enabled',
            'hot_reload_enabled',
            'backup_on_change',
            'version_control_enabled'
        ]
        
        for key in required_keys:
            assert key in admin_settings
            assert isinstance(admin_settings[key], bool)
    
    def test_status_reporting(self):
        """상태 보고 테스트"""
        status = self.settings.get_status()
        
        required_keys = [
            'config_loaded',
            'validation_errors',
            'cache_enabled',
            'config_summary'
        ]
        
        for key in required_keys:
            assert key in status


# 통합 테스트
class TestAnthropicIntegration:
    """Anthropic 컴포넌트 통합 테스트"""
    
    @pytest.mark.asyncio
    async def test_end_to_end_summarization(self):
        """종단간 요약 생성 테스트"""
        # 실제 컴포넌트들을 사용하되 LLM 호출만 Mock
        config = AnthropicConfig()
        config.enabled = True
        config.quality_threshold = 0.8
        
        summarizer = AnthropicSummarizer(config)
        
        # Mock LLM 응답
        mock_response = Mock()
        mock_response.content = """
        <problem_overview>
        🔍 **문제 현황**
        - 통합 테스트용 모의 응답
        - 모든 구조 요소 포함
        </problem_overview>
        
        <root_cause>
        💡 **원인 분석**
        - 테스트 시나리오에 의한 의도적 생성
        </root_cause>
        
        <resolution_progress>
        ⚡ **해결 진행상황**
        - 테스트봇이 모의 응답 생성 완료
        </resolution_progress>
        
        <key_insights>
        🎯 **중요 인사이트**
        - 통합 테스트 성공적 수행
        </key_insights>
        """
        mock_response.success = True
        
        with patch.object(summarizer, '_call_anthropic_llm', return_value=mock_response):
            summary = await summarizer.generate_anthropic_summary(
                content="통합 테스트용 티켓 내용",
                content_type="ticket_view",
                subject="통합 테스트 티켓",
                metadata={"priority": "high", "category": "test"}
            )
            
            # 결과 검증
            assert isinstance(summary, str)
            assert len(summary) > 100
            assert "🔍 **문제 현황**" in summary
            assert "💡 **원인 분석**" in summary
            assert "⚡ **해결 진행상황**" in summary
            assert "🎯 **중요 인사이트**" in summary
    
    def test_configuration_chain(self):
        """설정 체인 테스트"""
        # 환경변수 Mock
        with patch.dict('os.environ', {
            'ANTHROPIC_ENABLED': 'true',
            'ANTHROPIC_QUALITY_THRESHOLD': '0.85',
            'ANTHROPIC_ENABLE_CONSTITUTIONAL_AI': 'true'
        }):
            # 설정 로드
            settings = AnthropicSettings()
            config = settings.get_config()
            
            # 설정 확인
            assert config.enabled == True
            assert config.quality_threshold == 0.85
            assert settings.is_technique_enabled('constitutional_ai') == True
            
            # Summarizer에 적용
            summarizer = AnthropicSummarizer(config)
            assert summarizer.config.quality_threshold == 0.85


if __name__ == "__main__":
    # 테스트 실행
    pytest.main([__file__, "-v", "--tb=short"])