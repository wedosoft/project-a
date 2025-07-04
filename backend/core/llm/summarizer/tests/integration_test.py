"""
Anthropic 프롬프트 엔지니어링 시스템 통합 테스트

이 모듈은 Anthropic 기법이 적용된 전체 시스템의 종단간 테스트를 수행합니다.
실제 환경변수를 로드하고, 모든 컴포넌트 간의 상호작용을 검증하며,
성능 벤치마킹과 다양한 시나리오에서의 오류 처리를 테스트합니다.
"""

import os
import sys
import asyncio
import time
import json
import yaml
import logging
import pytest
from pathlib import Path
from typing import Dict, Any, List, Optional
from unittest.mock import patch, Mock, AsyncMock
from datetime import datetime
import statistics

# 테스트 환경 설정
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from core.llm.summarizer.core.anthropic_summarizer import AnthropicSummarizer
from core.llm.summarizer.config.anthropic_config import AnthropicConfig
from core.llm.summarizer.config.settings import AnthropicSettings
from core.llm.summarizer.prompt.anthropic_builder import AnthropicPromptBuilder
from core.llm.summarizer.quality.anthropic_validator import AnthropicQualityValidator
from core.llm.summarizer.admin.prompt_manager import PromptManager, prompt_manager
from core.llm.summarizer.prompt.loader import PromptLoader
from core.llm.manager import LLMManager

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AnthropicIntegrationTest:
    """Anthropic 시스템 통합 테스트 클래스"""
    
    def __init__(self):
        """통합 테스트 초기화"""
        self.test_results = {
            "total_tests": 0,
            "passed_tests": 0,
            "failed_tests": 0,
            "performance_metrics": {},
            "error_logs": [],
            "start_time": None,
            "end_time": None
        }
        
        # 테스트 데이터
        self.test_scenarios = self._load_test_scenarios()
        
        # 컴포넌트 초기화
        self.summarizer = None
        self.prompt_builder = None
        self.quality_validator = None
        self.prompt_manager = None
        self.settings = None
        
        logger.info("AnthropicIntegrationTest 초기화 완료")
    
    def _load_test_scenarios(self) -> List[Dict[str, Any]]:
        """테스트 시나리오 로드"""
        return [
            {
                "name": "technical_api_error",
                "description": "기술적 API 오류 상황",
                "input_data": {
                    "subject": "결제 API 연동 실패 - 긴급",
                    "content": """
                    ABC Corporation에서 결제 API 호출 시 500 Internal Server Error 발생
                    증상:
                    - 14:30부터 모든 결제 요청 실패
                    - Error Code: PAYMENT_API_CONNECTION_FAILED
                    - 시간당 약 1000만원 매출 손실 예상
                    
                    처리 과정:
                    - 14:30 김개발자 로그 확인 시작
                    - 14:45 API 키 설정 확인 - 누락 발견
                    - 15:00 API 키 재설정 완료
                    - 15:15 서비스 정상화 확인
                    
                    고객 상태: 매우 불만족, 긴급 복구 요청
                    """,
                    "metadata": {
                        "priority": "critical",
                        "category": "technical",
                        "customer_tier": "enterprise",
                        "business_impact": "high",
                        "ticket_id": "TECH-2025-001"
                    },
                    "content_language": "ko",
                    "ui_language": "ko"
                },
                "expected_elements": [
                    "🔍 **문제 현황**",
                    "💡 **원인 분석**", 
                    "⚡ **해결 진행상황**",
                    "🎯 **중요 인사이트**",
                    "ABC Corporation",
                    "500 Internal Server Error",
                    "김개발자",
                    "API 키"
                ],
                "quality_expectations": {
                    "min_score": 0.8,
                    "constitutional_compliance": True,
                    "xml_structure_valid": True,
                    "contains_actionable_info": True
                }
            },
            {
                "name": "customer_service_billing",
                "description": "고객 서비스 결제 문제",
                "input_data": {
                    "subject": "Premium 고객 환불 처리 지연",
                    "content": """
                    Premium 등급 고객 환불 요청 후 7일째 처리 지연
                    
                    고객 정보:
                    - 고객 등급: Premium (VIP)
                    - 환불 금액: 500만원
                    - 요청일: 2025-06-27
                    
                    처리 과정:
                    - 1일차: 환불 요청 접수 (박상담원)
                    - 3일차: 재무팀 승인 대기 (이팀장)
                    - 5일차: 고객 추가 문의 (화남 상태)
                    - 7일차: 긴급 처리 요청 (현재)
                    
                    고객 반응: 매우 불만족, 서비스 해지 위협
                    """,
                    "metadata": {
                        "priority": "high",
                        "category": "billing", 
                        "customer_tier": "premium",
                        "business_impact": "medium",
                        "ticket_id": "BILL-2025-002"
                    },
                    "content_language": "ko",
                    "ui_language": "ko"
                },
                "expected_elements": [
                    "Premium",
                    "환불",
                    "7일",
                    "박상담원",
                    "이팀장",
                    "재무팀"
                ],
                "quality_expectations": {
                    "min_score": 0.75,
                    "constitutional_compliance": True,
                    "xml_structure_valid": True,
                    "contains_escalation_info": True
                }
            },
            {
                "name": "multilingual_support",
                "description": "다국어 지원 테스트 (영어)",
                "input_data": {
                    "subject": "Database Performance Issue",
                    "content": """
                    Critical database performance degradation reported by XYZ Corp
                    
                    Symptoms:
                    - Query response time increased from 100ms to 5000ms
                    - Database CPU utilization at 95%
                    - Multiple timeout errors in application logs
                    
                    Actions taken:
                    - 10:30 John Smith started investigation
                    - 10:45 Identified slow query in user_analytics table
                    - 11:00 Applied index optimization
                    - 11:15 Performance restored to normal levels
                    
                    Customer status: Satisfied with quick resolution
                    """,
                    "metadata": {
                        "priority": "high",
                        "category": "performance",
                        "customer_tier": "enterprise", 
                        "business_impact": "medium",
                        "ticket_id": "PERF-2025-003"
                    },
                    "content_language": "en",
                    "ui_language": "en"
                },
                "expected_elements": [
                    "🔍 **Problem Overview**",
                    "💡 **Root Cause Analysis**",
                    "⚡ **Resolution Progress**", 
                    "🎯 **Key Insights**",
                    "XYZ Corp",
                    "John Smith",
                    "database"
                ],
                "quality_expectations": {
                    "min_score": 0.8,
                    "constitutional_compliance": True,
                    "xml_structure_valid": True
                }
            },
            {
                "name": "security_incident",
                "description": "보안 사고 처리",
                "input_data": {
                    "subject": "의심스러운 로그인 시도 감지",
                    "content": """
                    보안팀에서 비정상적인 로그인 패턴 감지
                    
                    감지 내용:
                    - 단시간 내 여러 IP에서 로그인 시도
                    - 비정상적인 지역에서의 접속 (러시아, 중국)
                    - 일반적이지 않은 시간대 접속 (새벽 3시)
                    
                    보안 조치:
                    - 즉시 계정 임시 잠금 처리
                    - 고객에게 비밀번호 재설정 안내
                    - 2차 인증 활성화 권장
                    
                    고객 협조: 양호, 보안 중요성 인지
                    """,
                    "metadata": {
                        "priority": "critical",
                        "category": "security",
                        "customer_tier": "standard",
                        "business_impact": "low",
                        "ticket_id": "SEC-2025-004"
                    },
                    "content_language": "ko",
                    "ui_language": "ko"
                },
                "expected_elements": [
                    "보안",
                    "로그인",
                    "IP",
                    "비밀번호",
                    "2차 인증"
                ],
                "quality_expectations": {
                    "min_score": 0.8,
                    "constitutional_compliance": True,
                    "xml_structure_valid": True,
                    "no_personal_info": True
                }
            }
        ]
    
    async def setup_test_environment(self) -> bool:
        """테스트 환경 설정"""
        try:
            logger.info("=== 테스트 환경 설정 시작 ===")
            
            # 1. 환경변수 확인
            required_env_vars = [
                'ANTHROPIC_ENABLED',
                'ANTHROPIC_API_KEY', 
                'OPENAI_API_KEY'
            ]
            
            missing_vars = []
            for var in required_env_vars:
                if not os.getenv(var):
                    missing_vars.append(var)
            
            if missing_vars:
                logger.warning(f"누락된 환경변수: {missing_vars}")
                # 테스트용 Mock 설정
                with patch.dict(os.environ, {
                    'ANTHROPIC_ENABLED': 'true',
                    'ANTHROPIC_API_KEY': 'test-key',
                    'OPENAI_API_KEY': 'test-key'
                }):
                    await self._initialize_components()
            else:
                await self._initialize_components()
            
            logger.info("✅ 테스트 환경 설정 완료")
            return True
            
        except Exception as e:
            logger.error(f"❌ 테스트 환경 설정 실패: {e}")
            return False
    
    async def _initialize_components(self):
        """컴포넌트 초기화"""
        # AnthropicSettings 초기화
        self.settings = AnthropicSettings()
        
        # AnthropicConfig 초기화
        config = AnthropicConfig.from_env()
        config.enabled = True  # 테스트를 위해 강제 활성화
        
        # AnthropicSummarizer 초기화
        self.summarizer = AnthropicSummarizer(config)
        
        # AnthropicPromptBuilder 초기화
        self.prompt_builder = AnthropicPromptBuilder()
        
        # AnthropicQualityValidator 초기화
        self.quality_validator = AnthropicQualityValidator()
        
        # PromptManager 초기화
        self.prompt_manager = PromptManager()
        
        logger.info("모든 컴포넌트 초기화 완료")
    
    async def run_comprehensive_test_suite(self) -> Dict[str, Any]:
        """종합 테스트 스위트 실행"""
        try:
            self.test_results["start_time"] = datetime.now().isoformat()
            logger.info("=== Anthropic 통합 테스트 시작 ===")
            
            # 환경 설정
            if not await self.setup_test_environment():
                raise Exception("테스트 환경 설정 실패")
            
            # 테스트 실행
            test_methods = [
                self.test_environment_loading,
                self.test_template_loading_and_validation,
                self.test_constitutional_ai_compliance,
                self.test_xml_structuring,
                self.test_end_to_end_summarization,
                self.test_quality_validation_system,
                self.test_fallback_mechanisms,
                self.test_admin_prompt_management,
                self.test_realtime_summary_generation,
                self.test_attachment_selection,
                self.test_performance_benchmarking,
                self.test_error_handling_scenarios,
                self.test_multilingual_support,
                self.test_hot_reload_functionality,
                self.test_backup_and_versioning
            ]
            
            for test_method in test_methods:
                try:
                    await self._run_single_test(test_method)
                except Exception as e:
                    self._record_test_failure(test_method.__name__, str(e))
            
            # 결과 정리
            self.test_results["end_time"] = datetime.now().isoformat()
            self._generate_final_report()
            
            return self.test_results
            
        except Exception as e:
            logger.error(f"❌ 통합 테스트 실행 실패: {e}")
            self.test_results["critical_error"] = str(e)
            return self.test_results
    
    async def _run_single_test(self, test_method):
        """단일 테스트 실행"""
        test_name = test_method.__name__
        start_time = time.time()
        
        try:
            logger.info(f"\n--- {test_name} 시작 ---")
            result = await test_method()
            
            execution_time = time.time() - start_time
            
            if result.get("success", False):
                self.test_results["passed_tests"] += 1
                logger.info(f"✅ {test_name} 성공 ({execution_time:.2f}s)")
            else:
                self.test_results["failed_tests"] += 1
                logger.error(f"❌ {test_name} 실패: {result.get('error', '알 수 없는 오류')}")
                self.test_results["error_logs"].append({
                    "test": test_name,
                    "error": result.get('error', '알 수 없는 오류'),
                    "timestamp": datetime.now().isoformat()
                })
            
            self.test_results["performance_metrics"][test_name] = {
                "execution_time": execution_time,
                "success": result.get("success", False),
                "details": result.get("metrics", {})
            }
            
        except Exception as e:
            execution_time = time.time() - start_time
            self.test_results["failed_tests"] += 1
            logger.error(f"❌ {test_name} 예외 발생: {e}")
            self.test_results["error_logs"].append({
                "test": test_name,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            })
            self.test_results["performance_metrics"][test_name] = {
                "execution_time": execution_time,
                "success": False,
                "error": str(e)
            }
        
        self.test_results["total_tests"] += 1
    
    def _record_test_failure(self, test_name: str, error: str):
        """테스트 실패 기록"""
        self.test_results["failed_tests"] += 1
        self.test_results["error_logs"].append({
            "test": test_name,
            "error": error,
            "timestamp": datetime.now().isoformat()
        })
    
    # === 개별 테스트 메서드들 ===
    
    async def test_environment_loading(self) -> Dict[str, Any]:
        """환경변수 및 설정 로딩 테스트"""
        try:
            # 환경변수 검증
            anthropic_enabled = os.getenv('ANTHROPIC_ENABLED', 'false').lower() == 'true'
            
            # 설정 객체 검증
            config = self.summarizer.config
            assert config is not None, "AnthropicConfig 로드 실패"
            assert hasattr(config, 'enabled'), "enabled 속성 없음"
            assert hasattr(config, 'quality_threshold'), "quality_threshold 속성 없음"
            
            # 설정값 유효성 검증
            assert 0 <= config.quality_threshold <= 1, f"잘못된 quality_threshold: {config.quality_threshold}"
            assert config.max_retries >= 0, f"잘못된 max_retries: {config.max_retries}"
            
            return {
                "success": True,
                "message": "환경변수 및 설정 로딩 성공",
                "metrics": {
                    "anthropic_enabled": anthropic_enabled,
                    "quality_threshold": config.quality_threshold,
                    "max_retries": config.max_retries
                }
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def test_template_loading_and_validation(self) -> Dict[str, Any]:
        """템플릿 로딩 및 검증 테스트"""
        try:
            # 시스템 템플릿 로딩
            system_template = await self.prompt_manager.get_template_content(
                "anthropic_ticket_view", "system"
            )
            assert system_template is not None, "시스템 템플릿 로드 실패"
            
            # 필수 섹션 확인
            required_sections = [
                'constitutional_principles',
                'role_definition', 
                'reasoning_framework',
                'response_structure',
                'system_prompts'
            ]
            
            missing_sections = []
            for section in required_sections:
                if section not in system_template:
                    missing_sections.append(section)
            
            assert not missing_sections, f"누락된 섹션: {missing_sections}"
            
            # Constitutional AI 원칙 검증
            principles = system_template['constitutional_principles']
            assert 'helpful' in principles, "helpful 원칙 없음"
            assert 'harmless' in principles, "harmless 원칙 없음"
            assert 'honest' in principles, "honest 원칙 없음"
            
            # 사용자 템플릿 로딩
            user_template = await self.prompt_manager.get_template_content(
                "anthropic_ticket_view", "user"
            )
            
            template_count = len(await self.prompt_manager.get_available_templates())
            
            return {
                "success": True,
                "message": "템플릿 로딩 및 검증 성공",
                "metrics": {
                    "system_template_loaded": system_template is not None,
                    "user_template_loaded": user_template is not None,
                    "total_template_types": template_count,
                    "constitutional_principles_count": len(principles)
                }
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def test_constitutional_ai_compliance(self) -> Dict[str, Any]:
        """Constitutional AI 준수 테스트"""
        try:
            test_responses = [
                {
                    "content": """
                    <problem_overview>
                    🔍 **문제 현황**
                    - 고객 로그인 실패 문제 발생
                    - 비즈니스 임팩트: 업무 중단
                    </problem_overview>
                    <root_cause>💡 **원인 분석** - 2FA 설정 오류 확인</root_cause>
                    <resolution_progress>⚡ **해결 진행상황** - 설정 재구성 완료</resolution_progress>
                    <key_insights>🎯 **중요 인사이트** - 사용자 가이드 개선 필요</key_insights>
                    """,
                    "expected_compliance": True,
                    "description": "올바른 형식의 응답"
                },
                {
                    "content": """
                    고객 이메일: user@example.com
                    전화번호: 010-1234-5678
                    아마도 비밀번호 문제일 것 같습니다.
                    확실하지 않지만 추측으로는...
                    """,
                    "expected_compliance": False,
                    "description": "개인정보 포함 및 추측성 응답"
                }
            ]
            
            compliance_results = []
            
            for test_case in test_responses:
                validation_result = self.prompt_builder.validate_anthropic_compliance(
                    test_case["content"], "anthropic_ticket_view"
                )
                
                compliance_results.append({
                    "description": test_case["description"],
                    "expected": test_case["expected_compliance"],
                    "actual": validation_result["constitutional_compliance"],
                    "details": validation_result
                })
            
            # 검증
            all_correct = all(
                result["expected"] == result["actual"] 
                for result in compliance_results
            )
            
            return {
                "success": all_correct,
                "message": f"Constitutional AI 준수 테스트 {'성공' if all_correct else '실패'}",
                "metrics": {
                    "total_tests": len(test_responses),
                    "correct_detections": sum(1 for r in compliance_results if r["expected"] == r["actual"]),
                    "compliance_results": compliance_results
                }
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def test_xml_structuring(self) -> Dict[str, Any]:
        """XML 구조화 테스트"""
        try:
            # Mock LLM 응답으로 XML 구조 테스트
            mock_responses = [
                {
                    "content": """
                    <problem_overview>문제 상황</problem_overview>
                    <root_cause>원인 분석</root_cause>
                    <resolution_progress>진행 상황</resolution_progress>
                    <key_insights>핵심 인사이트</key_insights>
                    """,
                    "expected_valid": True
                },
                {
                    "content": """
                    <problem_overview>문제만 있음</problem_overview>
                    일반 텍스트 내용...
                    """,
                    "expected_valid": False
                }
            ]
            
            xml_results = []
            required_sections = {
                'problem_overview': '문제 현황',
                'root_cause': '원인 분석',
                'resolution_progress': '해결 진행상황',
                'key_insights': '중요 인사이트'
            }
            
            for test_case in mock_responses:
                validation_result = self.quality_validator.validate_xml_structure(
                    test_case["content"], required_sections
                )
                
                xml_results.append({
                    "expected_valid": test_case["expected_valid"],
                    "actual_valid": validation_result["valid_structure"],
                    "found_sections": len(validation_result["found_sections"]),
                    "missing_sections": len(validation_result["missing_sections"]),
                    "structure_score": validation_result["structure_score"]
                })
            
            all_correct = all(
                result["expected_valid"] == result["actual_valid"]
                for result in xml_results
            )
            
            return {
                "success": all_correct,
                "message": f"XML 구조화 테스트 {'성공' if all_correct else '실패'}",
                "metrics": {
                    "xml_validation_results": xml_results,
                    "average_structure_score": statistics.mean([r["structure_score"] for r in xml_results])
                }
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def test_end_to_end_summarization(self) -> Dict[str, Any]:
        """종단간 요약 생성 테스트"""
        try:
            successful_scenarios = 0
            scenario_results = []
            
            for scenario in self.test_scenarios:
                try:
                    # Mock LLM 응답 생성
                    mock_response = self._generate_mock_anthropic_response(scenario)
                    
                    with patch.object(self.summarizer, '_call_anthropic_llm', return_value=mock_response):
                        summary = await self.summarizer.generate_anthropic_summary(
                            content=scenario["input_data"]["content"],
                            content_type="ticket_view",
                            subject=scenario["input_data"]["subject"],
                            metadata=scenario["input_data"]["metadata"],
                            content_language=scenario["input_data"]["content_language"],
                            ui_language=scenario["input_data"]["ui_language"]
                        )
                    
                    # 응답 검증
                    scenario_success = self._validate_scenario_response(scenario, summary)
                    
                    if scenario_success:
                        successful_scenarios += 1
                    
                    scenario_results.append({
                        "scenario": scenario["name"],
                        "success": scenario_success,
                        "summary_length": len(summary),
                        "contains_expected_elements": self._check_expected_elements(scenario, summary)
                    })
                    
                except Exception as e:
                    scenario_results.append({
                        "scenario": scenario["name"],
                        "success": False,
                        "error": str(e)
                    })
            
            success_rate = successful_scenarios / len(self.test_scenarios)
            
            return {
                "success": success_rate >= 0.8,  # 80% 이상 성공
                "message": f"종단간 테스트 성공률: {success_rate:.2%}",
                "metrics": {
                    "total_scenarios": len(self.test_scenarios),
                    "successful_scenarios": successful_scenarios,
                    "success_rate": success_rate,
                    "scenario_results": scenario_results
                }
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _generate_mock_anthropic_response(self, scenario: Dict[str, Any]) -> Mock:
        """시나리오별 Mock LLM 응답 생성"""
        mock_response = Mock()
        mock_response.success = True
        
        # 시나리오에 맞는 구조화된 응답 생성
        if scenario["input_data"]["content_language"] == "ko":
            mock_response.content = f"""
            <problem_overview>
            🔍 **문제 현황**
            - {scenario["input_data"]["subject"]}
            - 비즈니스 임팩트: {scenario["input_data"]["metadata"].get("business_impact", "중간")}
            - 우선순위: {scenario["input_data"]["metadata"].get("priority", "보통")}
            </problem_overview>
            
            <root_cause>
            💡 **원인 분석**
            - 분석된 근본 원인
            - 기술적 세부사항 포함
            </root_cause>
            
            <resolution_progress>
            ⚡ **해결 진행상황**
            - 현재 처리 상태
            - 수행된 조치들
            </resolution_progress>
            
            <key_insights>
            🎯 **중요 인사이트**
            - 향후 처리 방향
            - 예방 조치 권장사항
            </key_insights>
            """
        else:
            mock_response.content = f"""
            <problem_overview>
            🔍 **Problem Overview**
            - {scenario["input_data"]["subject"]}
            - Business impact: {scenario["input_data"]["metadata"].get("business_impact", "medium")}
            - Priority: {scenario["input_data"]["metadata"].get("priority", "normal")}
            </problem_overview>
            
            <root_cause>
            💡 **Root Cause Analysis**
            - Identified root cause
            - Technical details included
            </root_cause>
            
            <resolution_progress>
            ⚡ **Resolution Progress**
            - Current processing status
            - Actions taken
            </resolution_progress>
            
            <key_insights>
            🎯 **Key Insights**
            - Future handling direction
            - Prevention recommendations
            </key_insights>
            """
        
        return mock_response
    
    def _validate_scenario_response(self, scenario: Dict[str, Any], summary: str) -> bool:
        """시나리오 응답 검증"""
        try:
            expectations = scenario["quality_expectations"]
            
            # XML 구조 확인
            required_sections = {
                'problem_overview': '문제 현황',
                'root_cause': '원인 분석',
                'resolution_progress': '해결 진행상황',
                'key_insights': '중요 인사이트'
            }
            
            xml_validation = self.quality_validator.validate_xml_structure(summary, required_sections)
            
            if expectations.get("xml_structure_valid") and not xml_validation["valid_structure"]:
                return False
            
            # 기대 요소 포함 확인
            expected_elements = scenario.get("expected_elements", [])
            missing_elements = [elem for elem in expected_elements if elem not in summary]
            
            if missing_elements:
                logger.warning(f"누락된 요소들: {missing_elements}")
                return False
            
            # 품질 점수 확인 (Mock이므로 구조만 확인)
            if len(summary) < 100:  # 최소 길이 확인
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"시나리오 검증 실패: {e}")
            return False
    
    def _check_expected_elements(self, scenario: Dict[str, Any], summary: str) -> Dict[str, bool]:
        """기대 요소 포함 여부 확인"""
        expected_elements = scenario.get("expected_elements", [])
        return {element: element in summary for element in expected_elements}
    
    async def test_quality_validation_system(self) -> Dict[str, Any]:
        """품질 검증 시스템 테스트"""
        try:
            test_cases = [
                {
                    "summary": """
                    <problem_overview>🔍 **문제 현황** - 상세한 문제 설명</problem_overview>
                    <root_cause>💡 **원인 분석** - 정확한 원인 분석</root_cause>
                    <resolution_progress>⚡ **해결 진행상황** - 구체적인 진행 상황</resolution_progress>
                    <key_insights>🎯 **중요 인사이트** - 실행 가능한 인사이트</key_insights>
                    """,
                    "expected_score_range": (0.8, 1.0),
                    "description": "고품질 응답"
                },
                {
                    "summary": "간단한 답변입니다.",
                    "expected_score_range": (0.0, 0.4),
                    "description": "저품질 응답"
                }
            ]
            
            validation_results = []
            
            for test_case in test_cases:
                # Mock validation results 생성
                mock_validation = {
                    'constitutional_compliance': len(test_case["summary"]) > 100,
                    'xml_structure_valid': '<problem_overview>' in test_case["summary"],
                    'factual_accuracy': 0.8,
                    'actionability_score': 0.7,
                    'information_completeness': 0.9
                }
                
                quality_score = self.quality_validator.calculate_anthropic_quality_score(
                    test_case["summary"], mock_validation
                )
                
                expected_min, expected_max = test_case["expected_score_range"]
                score_in_range = expected_min <= quality_score <= expected_max
                
                validation_results.append({
                    "description": test_case["description"],
                    "quality_score": quality_score,
                    "expected_range": test_case["expected_score_range"],
                    "score_in_range": score_in_range,
                    "validation_details": mock_validation
                })
            
            all_scores_correct = all(result["score_in_range"] for result in validation_results)
            
            return {
                "success": all_scores_correct,
                "message": f"품질 검증 시스템 {'정상 작동' if all_scores_correct else '오류 발견'}",
                "metrics": {
                    "validation_results": validation_results,
                    "average_quality_score": statistics.mean([r["quality_score"] for r in validation_results])
                }
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def test_fallback_mechanisms(self) -> Dict[str, Any]:
        """폴백 메커니즘 테스트"""
        try:
            # LLM 호출 실패 시뮬레이션
            mock_failed_response = Mock()
            mock_failed_response.success = False
            mock_failed_response.error = "API 호출 실패"
            
            with patch.object(self.summarizer, '_call_anthropic_llm', return_value=mock_failed_response):
                with patch.object(self.summarizer, '_fallback_to_standard_summary', return_value="폴백 요약") as mock_fallback:
                    
                    summary = await self.summarizer.generate_anthropic_summary(
                        content="테스트 내용",
                        content_type="ticket_view",
                        subject="테스트 제목",
                        metadata={"priority": "high"}
                    )
                    
                    # 폴백이 호출되었는지 확인
                    mock_fallback.assert_called_once()
                    assert summary == "폴백 요약", "폴백 응답이 반환되지 않음"
            
            # 품질 점수 낮을 때 폴백 테스트
            mock_low_quality_response = Mock()
            mock_low_quality_response.success = True
            mock_low_quality_response.content = "저품질 응답"
            
            with patch.object(self.summarizer, '_call_anthropic_llm', return_value=mock_low_quality_response):
                with patch.object(self.quality_validator, 'calculate_anthropic_quality_score', return_value=0.3):
                    with patch.object(self.summarizer, '_fallback_to_standard_summary', return_value="품질 폴백") as mock_fallback:
                        
                        summary = await self.summarizer.generate_anthropic_summary(
                            content="테스트 내용",
                            content_type="ticket_view",
                            subject="테스트 제목", 
                            metadata={"priority": "high"}
                        )
                        
                        # 품질이 낮아서 폴백이 호출되었는지 확인
                        mock_fallback.assert_called_once()
            
            return {
                "success": True,
                "message": "폴백 메커니즘 정상 작동",
                "metrics": {
                    "api_failure_fallback": "성공",
                    "quality_failure_fallback": "성공"
                }
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def test_admin_prompt_management(self) -> Dict[str, Any]:
        """관리자 프롬프트 관리 기능 테스트"""
        try:
            # 템플릿 목록 조회
            available_templates = await self.prompt_manager.get_available_templates()
            assert len(available_templates) > 0, "사용 가능한 템플릿이 없음"
            
            # 템플릿 내용 조회
            template_content = await self.prompt_manager.get_template_content(
                "anthropic_ticket_view", "system"
            )
            assert template_content is not None, "템플릿 내용 조회 실패"
            
            # 템플릿 미리보기 테스트
            preview_result = await self.prompt_manager.preview_template(
                "anthropic_ticket_view",
                "system", 
                template_content,
                {"subject": "테스트", "content": "테스트 내용"}
            )
            assert preview_result["success"], "미리보기 생성 실패"
            
            # 변경 이력 조회
            change_history = await self.prompt_manager.get_change_history()
            assert isinstance(change_history, list), "변경 이력이 리스트가 아님"
            
            # 시스템 상태 조회
            system_status = await self.prompt_manager.get_system_status()
            assert system_status["status"] in ["healthy", "error"], "잘못된 시스템 상태"
            
            return {
                "success": True,
                "message": "관리자 프롬프트 관리 기능 정상 작동",
                "metrics": {
                    "available_template_types": len(available_templates),
                    "template_loaded": template_content is not None,
                    "preview_working": preview_result["success"],
                    "change_history_entries": len(change_history),
                    "system_status": system_status["status"]
                }
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def test_realtime_summary_generation(self) -> Dict[str, Any]:
        """실시간 요약 생성 테스트"""
        try:
            mock_realtime_response = Mock()
            mock_realtime_response.success = True
            mock_realtime_response.content = """
            🚨 **긴급도**: 높음
            📋 **핵심 문제**: API 연동 오류
            👤 **고객 상태**: 불만족
            ⚡ **즉시 조치**: 개발팀 컨택
            💼 **비즈니스 영향**: 매출 손실
            """
            
            with patch.object(self.summarizer, '_call_fast_llm', return_value=mock_realtime_response):
                realtime_summary = await self.summarizer.generate_realtime_summary(
                    content="긴급 API 오류 발생",
                    subject="결제 시스템 중단"
                )
                
                # 실시간 요약 필수 요소 확인
                required_elements = ["🚨", "📋", "👤", "⚡", "💼"]
                missing_elements = [elem for elem in required_elements if elem not in realtime_summary]
                
                assert not missing_elements, f"실시간 요약에 누락된 요소: {missing_elements}"
                assert len(realtime_summary) > 50, "실시간 요약이 너무 짧음"
            
            return {
                "success": True,
                "message": "실시간 요약 생성 성공",
                "metrics": {
                    "summary_length": len(realtime_summary),
                    "contains_all_elements": not missing_elements,
                    "response_format": "structured"
                }
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def test_attachment_selection(self) -> Dict[str, Any]:
        """첨부파일 선별 테스트"""
        try:
            test_attachments = [
                {"filename": "error_log.txt", "file_type": "text", "size": 1024},
                {"filename": "screenshot.png", "file_type": "image", "size": 2048},
                {"filename": "config.json", "file_type": "json", "size": 512}
            ]
            
            mock_selection_result = {
                "selected_attachments": [
                    {
                        "filename": "error_log.txt",
                        "selection_reason": "문제 해결에 필요한 로그 파일",
                        "relevance_score": 0.9,
                        "priority": "high"
                    }
                ],
                "total_selected": 1,
                "selection_summary": "관련성 높은 첨부파일 1개 선별",
                "confidence_score": 0.85
            }
            
            mock_response = Mock()
            mock_response.success = True
            mock_response.content = json.dumps(mock_selection_result)
            
            with patch.object(self.summarizer, '_call_anthropic_llm', return_value=mock_response):
                selection_result = await self.summarizer.select_relevant_attachments(
                    content="시스템 오류 발생",
                    subject="로그 확인 요청",
                    attachments=test_attachments
                )
                
                assert selection_result["total_selected"] > 0, "선별된 첨부파일이 없음"
                assert "selected_attachments" in selection_result, "선별 결과에 selected_attachments 없음"
                assert selection_result["confidence_score"] > 0.5, "신뢰도 점수가 너무 낮음"
            
            return {
                "success": True,
                "message": "첨부파일 선별 기능 정상 작동",
                "metrics": {
                    "total_attachments": len(test_attachments),
                    "selected_count": selection_result["total_selected"],
                    "confidence_score": selection_result["confidence_score"]
                }
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def test_performance_benchmarking(self) -> Dict[str, Any]:
        """성능 벤치마킹 테스트"""
        try:
            performance_metrics = {
                "response_times": [],
                "memory_usage": [],
                "throughput": 0
            }
            
            # 여러 요청으로 성능 측정
            test_iterations = 5
            start_time = time.time()
            
            for i in range(test_iterations):
                iteration_start = time.time()
                
                mock_response = Mock()
                mock_response.success = True
                mock_response.content = f"Mock response {i}"
                
                with patch.object(self.summarizer, '_call_anthropic_llm', return_value=mock_response):
                    await self.summarizer.generate_anthropic_summary(
                        content=f"테스트 내용 {i}",
                        content_type="ticket_view",
                        subject=f"테스트 제목 {i}",
                        metadata={"priority": "normal"}
                    )
                
                iteration_time = time.time() - iteration_start
                performance_metrics["response_times"].append(iteration_time)
            
            total_time = time.time() - start_time
            performance_metrics["throughput"] = test_iterations / total_time
            
            # 성능 기준 확인
            avg_response_time = statistics.mean(performance_metrics["response_times"])
            max_response_time = max(performance_metrics["response_times"])
            
            # 성능 기준: 평균 응답시간 2초 이하, 최대 응답시간 5초 이하
            performance_acceptable = avg_response_time <= 2.0 and max_response_time <= 5.0
            
            return {
                "success": performance_acceptable,
                "message": f"성능 벤치마킹 {'통과' if performance_acceptable else '실패'}",
                "metrics": {
                    "avg_response_time": avg_response_time,
                    "max_response_time": max_response_time,
                    "min_response_time": min(performance_metrics["response_times"]),
                    "throughput_requests_per_second": performance_metrics["throughput"],
                    "total_iterations": test_iterations
                }
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def test_error_handling_scenarios(self) -> Dict[str, Any]:
        """오류 처리 시나리오 테스트"""
        try:
            error_scenarios = [
                {
                    "name": "API 연결 실패",
                    "mock_error": Exception("Connection timeout"),
                    "expected_fallback": True
                },
                {
                    "name": "잘못된 응답 형식",
                    "mock_response": Mock(success=True, content="Invalid JSON"),
                    "expected_fallback": True
                },
                {
                    "name": "빈 응답",
                    "mock_response": Mock(success=True, content=""),
                    "expected_fallback": True
                }
            ]
            
            error_handling_results = []
            
            for scenario in error_scenarios:
                try:
                    if "mock_error" in scenario:
                        # 예외 발생 시나리오
                        with patch.object(self.summarizer, '_call_anthropic_llm', side_effect=scenario["mock_error"]):
                            with patch.object(self.summarizer, '_fallback_to_standard_summary', return_value="폴백 응답") as mock_fallback:
                                
                                result = await self.summarizer.generate_anthropic_summary(
                                    content="테스트",
                                    content_type="ticket_view",
                                    subject="오류 테스트",
                                    metadata={}
                                )
                                
                                fallback_called = mock_fallback.called
                                
                    elif "mock_response" in scenario:
                        # 잘못된 응답 시나리오
                        with patch.object(self.summarizer, '_call_anthropic_llm', return_value=scenario["mock_response"]):
                            with patch.object(self.summarizer, '_fallback_to_standard_summary', return_value="폴백 응답") as mock_fallback:
                                
                                result = await self.summarizer.generate_anthropic_summary(
                                    content="테스트",
                                    content_type="ticket_view", 
                                    subject="오류 테스트",
                                    metadata={}
                                )
                                
                                fallback_called = mock_fallback.called
                    
                    error_handling_results.append({
                        "scenario": scenario["name"],
                        "fallback_called": fallback_called,
                        "expected_fallback": scenario["expected_fallback"],
                        "success": fallback_called == scenario["expected_fallback"]
                    })
                    
                except Exception as e:
                    error_handling_results.append({
                        "scenario": scenario["name"], 
                        "error": str(e),
                        "success": False
                    })
            
            all_scenarios_passed = all(result.get("success", False) for result in error_handling_results)
            
            return {
                "success": all_scenarios_passed,
                "message": f"오류 처리 시나리오 {'모두 통과' if all_scenarios_passed else '일부 실패'}",
                "metrics": {
                    "total_scenarios": len(error_scenarios),
                    "passed_scenarios": sum(1 for r in error_handling_results if r.get("success", False)),
                    "scenario_details": error_handling_results
                }
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def test_multilingual_support(self) -> Dict[str, Any]:
        """다국어 지원 테스트"""
        try:
            multilingual_tests = [
                {
                    "content_language": "ko",
                    "ui_language": "ko",
                    "expected_sections": ["🔍 **문제 현황**", "💡 **원인 분석**"]
                },
                {
                    "content_language": "en", 
                    "ui_language": "en",
                    "expected_sections": ["🔍 **Problem Overview**", "💡 **Root Cause Analysis**"]
                }
            ]
            
            multilingual_results = []
            
            for test_case in multilingual_tests:
                mock_response = Mock()
                mock_response.success = True
                
                if test_case["content_language"] == "ko":
                    mock_response.content = """
                    <problem_overview>🔍 **문제 현황** - 한국어 응답</problem_overview>
                    <root_cause>💡 **원인 분석** - 한국어 분석</root_cause>
                    <resolution_progress>⚡ **해결 진행상황** - 한국어 진행</resolution_progress>
                    <key_insights>🎯 **중요 인사이트** - 한국어 인사이트</key_insights>
                    """
                else:
                    mock_response.content = """
                    <problem_overview>🔍 **Problem Overview** - English response</problem_overview>
                    <root_cause>💡 **Root Cause Analysis** - English analysis</root_cause>
                    <resolution_progress>⚡ **Resolution Progress** - English progress</resolution_progress>
                    <key_insights>🎯 **Key Insights** - English insights</key_insights>
                    """
                
                with patch.object(self.summarizer, '_call_anthropic_llm', return_value=mock_response):
                    summary = await self.summarizer.generate_anthropic_summary(
                        content="Test content",
                        content_type="ticket_view",
                        subject="Test subject",
                        metadata={},
                        content_language=test_case["content_language"],
                        ui_language=test_case["ui_language"]
                    )
                    
                    # 언어별 섹션 제목 확인
                    sections_found = all(section in summary for section in test_case["expected_sections"])
                    
                    multilingual_results.append({
                        "language": test_case["content_language"],
                        "sections_found": sections_found,
                        "summary_length": len(summary)
                    })
            
            all_languages_supported = all(result["sections_found"] for result in multilingual_results)
            
            return {
                "success": all_languages_supported,
                "message": f"다국어 지원 {'정상 작동' if all_languages_supported else '오류 발견'}",
                "metrics": {
                    "supported_languages": len(multilingual_tests),
                    "language_results": multilingual_results
                }
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def test_hot_reload_functionality(self) -> Dict[str, Any]:
        """핫 리로드 기능 테스트"""
        try:
            # 현재 템플릿 내용 확인
            original_template = await self.prompt_manager.get_template_content(
                "anthropic_ticket_view", "system"
            )
            assert original_template is not None, "원본 템플릿 로드 실패"
            
            # 템플릿 수정 시뮬레이션
            modified_template = original_template.copy()
            modified_template['version'] = "1.0.1"
            modified_template['test_field'] = "hot_reload_test"
            
            # 핫 리로드 테스트 (실제 파일 수정 없이 Mock 사용)
            with patch.object(self.prompt_builder, 'reload_templates') as mock_reload:
                await self.prompt_manager._trigger_hot_reload()
                mock_reload.assert_called_once()
            
            # 설정 동적 업데이트 테스트
            new_threshold = 0.85
            update_success = await self._mock_config_update(new_threshold)
            
            return {
                "success": True,
                "message": "핫 리로드 기능 정상 작동",
                "metrics": {
                    "template_reload": "성공",
                    "config_update": "성공" if update_success else "실패",
                    "new_threshold": new_threshold
                }
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _mock_config_update(self, new_threshold: float) -> bool:
        """설정 업데이트 Mock"""
        try:
            # 실제로는 settings.update_quality_threshold() 호출
            self.summarizer.config.quality_threshold = new_threshold
            return True
        except:
            return False
    
    async def test_backup_and_versioning(self) -> Dict[str, Any]:
        """백업 및 버전 관리 테스트"""
        try:
            # 백업 목록 조회
            backup_list = await self.prompt_manager.get_backup_list()
            assert isinstance(backup_list, list), "백업 목록이 리스트가 아님"
            
            # 템플릿 내보내기 테스트
            export_result = await self.prompt_manager.export_templates()
            assert export_result["success"], "템플릿 내보내기 실패"
            assert "data" in export_result, "내보내기 데이터 없음"
            
            # 변경 이력 조회
            change_history = await self.prompt_manager.get_change_history(limit=10)
            assert isinstance(change_history, list), "변경 이력이 리스트가 아님"
            
            # Mock 백업 생성 테스트
            test_content = {"version": "1.0.0", "test": "backup"}
            backup_created = await self.prompt_manager._create_backup(
                "test_template", "system", test_content, "test"
            )
            
            return {
                "success": True,
                "message": "백업 및 버전 관리 기능 정상 작동",
                "metrics": {
                    "backup_count": len(backup_list),
                    "export_success": export_result["success"],
                    "change_history_entries": len(change_history),
                    "backup_creation": "성공" if backup_created else "실패"
                }
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _generate_final_report(self):
        """최종 테스트 리포트 생성"""
        start_time = datetime.fromisoformat(self.test_results["start_time"])
        end_time = datetime.fromisoformat(self.test_results["end_time"])
        total_duration = (end_time - start_time).total_seconds()
        
        success_rate = self.test_results["passed_tests"] / self.test_results["total_tests"] if self.test_results["total_tests"] > 0 else 0
        
        # 성능 메트릭 요약
        performance_summary = {}
        if self.test_results["performance_metrics"]:
            execution_times = [
                metrics.get("execution_time", 0) 
                for metrics in self.test_results["performance_metrics"].values()
                if isinstance(metrics, dict) and "execution_time" in metrics
            ]
            
            if execution_times:
                performance_summary = {
                    "avg_execution_time": statistics.mean(execution_times),
                    "max_execution_time": max(execution_times),
                    "min_execution_time": min(execution_times),
                    "total_execution_time": sum(execution_times)
                }
        
        self.test_results["summary"] = {
            "overall_success": success_rate >= 0.8,
            "success_rate": success_rate,
            "total_duration_seconds": total_duration,
            "performance_summary": performance_summary,
            "critical_failures": len([
                error for error in self.test_results["error_logs"]
                if "environment" in error["test"] or "template" in error["test"]
            ])
        }
        
        # 테스트 결과 로깅
        logger.info("=== 최종 테스트 결과 ===")
        logger.info(f"총 테스트: {self.test_results['total_tests']}")
        logger.info(f"성공: {self.test_results['passed_tests']}")
        logger.info(f"실패: {self.test_results['failed_tests']}")
        logger.info(f"성공률: {success_rate:.2%}")
        logger.info(f"총 소요시간: {total_duration:.2f}초")
        
        if self.test_results["error_logs"]:
            logger.error("실패한 테스트들:")
            for error in self.test_results["error_logs"]:
                logger.error(f"  - {error['test']}: {error['error']}")


# 테스트 실행 함수들

async def run_integration_tests():
    """통합 테스트 실행"""
    test_runner = AnthropicIntegrationTest()
    results = await test_runner.run_comprehensive_test_suite()
    return results


def save_test_results(results: Dict[str, Any], output_file: str = "integration_test_results.json"):
    """테스트 결과 저장"""
    try:
        output_path = Path(__file__).parent / output_file
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2, default=str)
        
        logger.info(f"테스트 결과 저장: {output_path}")
        return str(output_path)
        
    except Exception as e:
        logger.error(f"테스트 결과 저장 실패: {e}")
        return None


if __name__ == "__main__":
    # 직접 실행 시 통합 테스트 수행
    async def main():
        logger.info("Anthropic 통합 테스트 시작")
        
        results = await run_integration_tests()
        
        # 결과 저장
        saved_path = save_test_results(results)
        
        # 결과 요약 출력
        summary = results.get("summary", {})
        print("\n" + "="*60)
        print("🧪 ANTHROPIC 통합 테스트 결과")
        print("="*60)
        print(f"📊 총 테스트: {results['total_tests']}")
        print(f"✅ 성공: {results['passed_tests']}")
        print(f"❌ 실패: {results['failed_tests']}")
        print(f"📈 성공률: {summary.get('success_rate', 0):.2%}")
        print(f"⏱️  총 소요시간: {summary.get('total_duration_seconds', 0):.2f}초")
        print(f"🎯 전체 결과: {'통과' if summary.get('overall_success', False) else '실패'}")
        
        if saved_path:
            print(f"📄 상세 결과: {saved_path}")
        
        print("="*60)
        
        # 종료 코드 설정
        return 0 if summary.get('overall_success', False) else 1
    
    exit_code = asyncio.run(main())
    sys.exit(exit_code)