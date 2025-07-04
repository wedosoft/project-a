#!/usr/bin/env python3
"""
LLM 모델 관리 CLI 도구

사용법:
    python cli_tools.py list-models [--provider PROVIDER] [--type TYPE]
    python cli_tools.py check-deprecated [--days DAYS]
    python cli_tools.py migration-plan <provider:model>
    python cli_tools.py validate-environment [--env ENV]
    python cli_tools.py switch-environment <environment>
    python cli_tools.py migration-report [--format FORMAT]
"""

import argparse
import json
import sys
import os
from typing import Dict, List, Optional, Any
from pathlib import Path

# 프로젝트 경로 추가
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from backend.core.llm.registry import get_model_registry, ModelType
from backend.core.llm.environment_manager import get_environment_manager
from backend.core.llm.deprecation_manager import get_deprecation_manager
from backend.core.llm.flexible_manager import get_flexible_llm_manager


class CLITool:
    """LLM 관리 CLI 도구"""
    
    def __init__(self):
        self.registry = get_model_registry()
        self.env_manager = get_environment_manager()
        self.deprecation_manager = get_deprecation_manager()
        self.flexible_manager = get_flexible_llm_manager()
    
    def list_models(self, provider: Optional[str] = None, 
                   model_type: Optional[str] = None,
                   include_deprecated: bool = False) -> Dict[str, Any]:
        """사용 가능한 모델 목록 출력"""
        type_filter = None
        if model_type:
            try:
                type_filter = ModelType(model_type.lower())
            except ValueError:
                print(f"❌ 잘못된 모델 타입: {model_type}")
                print(f"   사용 가능한 타입: {[t.value for t in ModelType]}")
                return {"error": "invalid_model_type"}
        
        models = self.registry.get_available_models(
            provider=provider,
            model_type=type_filter,
            include_deprecated=include_deprecated
        )
        
        if not models:
            print("📭 조건에 맞는 모델이 없습니다.")
            return {"models": []}
        
        # 제공자별로 그룹화
        by_provider = {}
        for model in models:
            if model.provider not in by_provider:
                by_provider[model.provider] = []
            by_provider[model.provider].append(model)
        
        print(f"🤖 사용 가능한 모델 ({len(models)}개)")
        print("=" * 60)
        
        for provider_name, provider_models in by_provider.items():
            print(f"\n📡 {provider_name.upper()}")
            print("-" * 40)
            
            for model in provider_models:
                status = "🔴 DEPRECATED" if model.deprecated else "🟢 ACTIVE"
                cost = f"💰 {model.cost_tier.value}"
                speed = f"⚡ {model.speed_tier.value}"
                quality = f"✨ {model.quality_tier.value}"
                
                print(f"  {model.name}")
                print(f"    {status} | {cost} | {speed} | {quality}")
                print(f"    Type: {model.type.value} | Context: {model.context_window:,} tokens")
                
                if model.deprecated and model.replacement:
                    print(f"    ➡️  Replacement: {model.replacement}")
                
                if model.capabilities:
                    print(f"    🎯 Capabilities: {', '.join(model.capabilities)}")
                
                print()
        
        return {
            "total_models": len(models),
            "by_provider": {
                provider: len(models_list) 
                for provider, models_list in by_provider.items()
            }
        }
    
    def check_deprecated(self, days_ahead: int = 30) -> Dict[str, Any]:
        """사용 중단 예정 모델들 확인"""
        alerts = self.deprecation_manager.check_deprecated_models()
        
        if not alerts:
            print("✅ 사용 중단 예정인 모델이 없습니다.")
            return {"alerts": []}
        
        print(f"⚠️  사용 중단 예정 모델 ({len(alerts)}개)")
        print("=" * 60)
        
        for alert in alerts:
            urgency_emoji = {
                "critical": "🚨",
                "high": "🔴", 
                "medium": "🟡",
                "low": "🟢"
            }
            
            emoji = urgency_emoji.get(alert.urgency.value, "ℹ️")
            
            print(f"\n{emoji} {alert.model_key}")
            print(f"   중단일: {alert.deprecation_date} ({alert.days_remaining}일 후)")
            print(f"   긴급도: {alert.urgency.value.upper()}")
            
            if alert.replacement_model:
                print(f"   대체 모델: {alert.replacement_model}")
            
            if alert.affected_use_cases:
                print(f"   영향받는 용도: {', '.join(alert.affected_use_cases)}")
            
            if alert.migration_guide:
                print(f"   마이그레이션 가이드: {alert.migration_guide}")
        
        print(f"\n📊 긴급도별 통계:")
        urgency_counts = {}
        for alert in alerts:
            urgency = alert.urgency.value
            urgency_counts[urgency] = urgency_counts.get(urgency, 0) + 1
        
        for urgency, count in urgency_counts.items():
            emoji = urgency_emoji.get(urgency, "ℹ️")
            print(f"   {emoji} {urgency.upper()}: {count}개")
        
        return {
            "total_alerts": len(alerts),
            "urgency_breakdown": urgency_counts,
            "alerts": [alert.to_dict() for alert in alerts]
        }
    
    def create_migration_plan(self, model_key: str) -> Dict[str, Any]:
        """특정 모델의 마이그레이션 계획 생성"""
        try:
            provider, model = model_key.split(':')
        except ValueError:
            print(f"❌ 잘못된 모델 키 형식: {model_key}")
            print("   올바른 형식: <provider>:<model>")
            print("   예시: openai:gpt-3.5-turbo")
            return {"error": "invalid_model_key"}
        
        plan = self.deprecation_manager.create_migration_plan(provider, model)
        
        if not plan:
            print(f"❌ {model_key}에 대한 마이그레이션 계획을 생성할 수 없습니다.")
            return {"error": "no_migration_plan"}
        
        print(f"📋 마이그레이션 계획: {model_key}")
        print("=" * 60)
        
        print(f"🎯 대상 모델: {plan.target_provider}:{plan.target_model}")
        print(f"🚨 긴급도: {plan.urgency.value.upper()}")
        print(f"💰 비용 영향: {plan.estimated_cost_impact:+.1f}%")
        print(f"⚡ 성능 영향: {plan.performance_impact}")
        print(f"🧪 테스트 필요: {'예' if plan.testing_required else '아니오'}")
        print(f"📝 사유: {plan.reason}")
        
        print(f"\n📋 마이그레이션 단계:")
        for step in plan.migration_steps:
            print(f"   {step}")
        
        print(f"\n🔄 롤백 계획:")
        for step in plan.rollback_plan:
            print(f"   {step}")
        
        return plan.to_dict()
    
    def validate_environment(self, env_name: Optional[str] = None) -> Dict[str, Any]:
        """환경 설정 유효성 검증"""
        if env_name:
            if not self.env_manager.switch_environment(env_name):
                print(f"❌ 알 수 없는 환경: {env_name}")
                return {"error": "unknown_environment"}
        
        validation = self.env_manager.validate_current_environment()
        
        print(f"🔍 환경 검증: {validation['environment']}")
        print("=" * 60)
        
        if validation['valid']:
            print("✅ 환경 설정이 유효합니다.")
        else:
            print("❌ 환경 설정에 문제가 있습니다.")
        
        if validation.get('errors'):
            print(f"\n🚨 오류:")
            for error in validation['errors']:
                print(f"   • {error}")
        
        if validation.get('warnings'):
            print(f"\n⚠️  경고:")
            for warning in validation['warnings']:
                print(f"   • {warning}")
        
        # 추가 검증: 유연한 매니저
        flexible_validation = self.flexible_manager.validate_environment_setup()
        
        if not flexible_validation['valid']:
            print(f"\n🔧 Flexible Manager 검증 결과:")
            if flexible_validation.get('errors'):
                for error in flexible_validation['errors']:
                    print(f"   🚨 {error}")
            if flexible_validation.get('warnings'):
                for warning in flexible_validation['warnings']:
                    print(f"   ⚠️  {warning}")
        
        return {
            "environment_validation": validation,
            "flexible_manager_validation": flexible_validation
        }
    
    def switch_environment(self, env_name: str) -> Dict[str, Any]:
        """환경 전환"""
        success = self.env_manager.switch_environment(env_name)
        
        if success:
            print(f"✅ 환경 전환 완료: {env_name}")
            
            # 새 환경 정보 표시
            config = self.env_manager.get_current_config()
            if config:
                print(f"\n📊 환경 정보:")
                print(f"   기본 제공자: {config.default_provider}")
                print(f"   기본 채팅 모델: {config.default_chat_model}")
                print(f"   기본 임베딩 모델: {config.default_embedding_model}")
                print(f"   비용 제한: {config.cost_limit}")
                
                if config.model_overrides:
                    print(f"   모델 오버라이드: {len(config.model_overrides)}개")
            
            return {"success": True, "environment": env_name}
        else:
            print(f"❌ 환경 전환 실패: {env_name}")
            available_envs = list(self.env_manager.configs.keys())
            print(f"   사용 가능한 환경: {', '.join(available_envs)}")
            return {"success": False, "error": "switch_failed"}
    
    def generate_migration_report(self, output_format: str = "text") -> Dict[str, Any]:
        """마이그레이션 보고서 생성"""
        report = self.deprecation_manager.generate_migration_report()
        
        if output_format.lower() == "json":
            print(json.dumps(report, indent=2, ensure_ascii=False))
            return report
        
        # 텍스트 형식 출력
        print("📊 마이그레이션 보고서")
        print("=" * 60)
        print(f"보고서 생성일: {report['report_date']}")
        print(f"현재 환경: {report['environment']}")
        
        summary = report['summary']
        print(f"\n📈 요약:")
        print(f"   사용 중단 모델: {summary['total_deprecated_models']}개")
        print(f"   긴급 마이그레이션: {summary['critical_migrations']}개")
        print(f"   높은 우선순위: {summary['high_priority_migrations']}개")
        print(f"   권장사항: {summary['total_recommendations']}개")
        
        if report['next_actions']:
            print(f"\n📋 다음 액션:")
            for action in report['next_actions']:
                print(f"   • {action}")
        
        if report['deprecation_alerts']:
            print(f"\n⚠️  사용 중단 알림:")
            for alert in report['deprecation_alerts'][:5]:  # 최대 5개만 표시
                print(f"   • {alert['model']} (D-{alert['days_remaining']})")
        
        if len(report['deprecation_alerts']) > 5:
            remaining = len(report['deprecation_alerts']) - 5
            print(f"   ... 및 {remaining}개 더")
        
        return report
    
    def show_registry_summary(self) -> Dict[str, Any]:
        """모델 레지스트리 요약 정보"""
        summary = self.registry.get_registry_summary()
        
        print("🗂️  모델 레지스트리 요약")
        print("=" * 60)
        print(f"총 모델: {summary['total_models']}개")
        print(f"활성 모델: {summary['active_models']}개")
        print(f"사용 중단 모델: {summary['deprecated_models']}개")
        print(f"제공자: {', '.join(summary['providers'])}")
        print(f"Use Cases: {', '.join(summary['use_cases'])}")
        print(f"환경: {', '.join(summary['environments'])}")
        print(f"설정 파일: {summary['config_path']}")
        print(f"마지막 로드: {summary['last_loaded']}")
        
        return summary
    
    def show_environment_summary(self) -> Dict[str, Any]:
        """환경 설정 요약 정보"""
        summary = self.env_manager.get_environment_summary()
        
        print("🌍 환경 설정 요약")
        print("=" * 60)
        print(f"현재 환경: {summary['current_environment']}")
        print(f"사용 가능한 환경: {', '.join(summary['available_environments'])}")
        print(f"기본 제공자: {summary['default_provider']}")
        print(f"기본 채팅 모델: {summary['default_chat_model']}")
        print(f"기본 임베딩 모델: {summary['default_embedding_model']}")
        print(f"비용 제한: {summary['cost_limit']}")
        print(f"모델 오버라이드: {summary['model_overrides_count']}개")
        print(f"활성 기능 플래그: {summary['feature_flags_enabled']}개")
        
        return summary


def main():
    """CLI 메인 함수"""
    parser = argparse.ArgumentParser(
        description="LLM 모델 관리 CLI 도구",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  python cli_tools.py list-models --provider openai
  python cli_tools.py check-deprecated --days 30
  python cli_tools.py migration-plan anthropic:claude-3-haiku-20240307
  python cli_tools.py validate-environment --env production
  python cli_tools.py migration-report --format json
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='사용 가능한 명령어')
    
    # list-models 명령어
    list_parser = subparsers.add_parser('list-models', help='모델 목록 조회')
    list_parser.add_argument('--provider', help='제공자 필터 (openai, anthropic, gemini)')
    list_parser.add_argument('--type', help='모델 타입 필터 (chat, embedding)')
    list_parser.add_argument('--include-deprecated', action='store_true', help='사용 중단 모델 포함')
    
    # check-deprecated 명령어
    deprecated_parser = subparsers.add_parser('check-deprecated', help='사용 중단 예정 모델 확인')
    deprecated_parser.add_argument('--days', type=int, default=30, help='확인할 일 수 (기본: 30일)')
    
    # migration-plan 명령어
    migration_parser = subparsers.add_parser('migration-plan', help='마이그레이션 계획 생성')
    migration_parser.add_argument('model_key', help='모델 키 (provider:model)')
    
    # validate-environment 명령어
    validate_parser = subparsers.add_parser('validate-environment', help='환경 설정 검증')
    validate_parser.add_argument('--env', help='검증할 환경명')
    
    # switch-environment 명령어
    switch_parser = subparsers.add_parser('switch-environment', help='환경 전환')
    switch_parser.add_argument('environment', help='전환할 환경명')
    
    # migration-report 명령어
    report_parser = subparsers.add_parser('migration-report', help='마이그레이션 보고서 생성')
    report_parser.add_argument('--format', choices=['text', 'json'], default='text', help='출력 형식')
    
    # registry-summary 명령어
    subparsers.add_parser('registry-summary', help='모델 레지스트리 요약')
    
    # environment-summary 명령어
    subparsers.add_parser('environment-summary', help='환경 설정 요약')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        cli = CLITool()
        
        if args.command == 'list-models':
            cli.list_models(
                provider=args.provider,
                model_type=args.type,
                include_deprecated=args.include_deprecated
            )
        
        elif args.command == 'check-deprecated':
            cli.check_deprecated(days_ahead=args.days)
        
        elif args.command == 'migration-plan':
            cli.create_migration_plan(args.model_key)
        
        elif args.command == 'validate-environment':
            cli.validate_environment(env_name=args.env)
        
        elif args.command == 'switch-environment':
            cli.switch_environment(args.environment)
        
        elif args.command == 'migration-report':
            cli.generate_migration_report(output_format=args.format)
        
        elif args.command == 'registry-summary':
            cli.show_registry_summary()
        
        elif args.command == 'environment-summary':
            cli.show_environment_summary()
    
    except KeyboardInterrupt:
        print("\n\n⛔ 중단되었습니다.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()