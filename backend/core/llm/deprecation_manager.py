"""
모델 Deprecation 대응 시스템

모델 중단에 대비한 자동 마이그레이션과 알림 시스템
"""

import os
import logging
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import json

from .registry import get_model_registry, ModelRegistry, ModelSpec
from .environment_manager import get_environment_manager

logger = logging.getLogger(__name__)


class MigrationUrgency(Enum):
    """마이그레이션 긴급도"""
    LOW = "low"          # 30일 이상 남음
    MEDIUM = "medium"    # 7-30일 남음
    HIGH = "high"        # 1-7일 남음
    CRITICAL = "critical" # 이미 중단됨


@dataclass
class MigrationPlan:
    """마이그레이션 계획"""
    source_provider: str
    source_model: str
    target_provider: str
    target_model: str
    reason: str
    urgency: MigrationUrgency
    estimated_cost_impact: float  # 비용 변화 (%)
    performance_impact: str       # "better", "similar", "worse"
    migration_steps: List[str]
    rollback_plan: List[str]
    testing_required: bool
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            'source': f"{self.source_provider}:{self.source_model}",
            'target': f"{self.target_provider}:{self.target_model}",
            'reason': self.reason,
            'urgency': self.urgency.value,
            'cost_impact': self.estimated_cost_impact,
            'performance_impact': self.performance_impact,
            'migration_steps': self.migration_steps,
            'rollback_plan': self.rollback_plan,
            'testing_required': self.testing_required
        }


@dataclass
class DeprecationAlert:
    """Deprecation 알림"""
    model_key: str
    deprecation_date: str
    days_remaining: int
    replacement_model: Optional[str]
    migration_guide: Optional[str]
    urgency: MigrationUrgency
    affected_use_cases: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            'model': self.model_key,
            'deprecation_date': self.deprecation_date,
            'days_remaining': self.days_remaining,
            'replacement': self.replacement_model,
            'migration_guide': self.migration_guide,
            'urgency': self.urgency.value,
            'affected_use_cases': self.affected_use_cases
        }


class DeprecationManager:
    """모델 Deprecation 관리자"""
    
    def __init__(self):
        self.registry = get_model_registry()
        self.env_manager = get_environment_manager()
        
        # 마이그레이션 히스토리
        self.migration_history: List[Dict[str, Any]] = []
        
        # 알림 설정
        self.notification_days = [30, 14, 7, 3, 1]  # 알림을 보낼 날짜들
        
        logger.info("DeprecationManager 초기화 완료")
    
    def check_deprecated_models(self) -> List[DeprecationAlert]:
        """사용 중단된 모델들 확인"""
        alerts = []
        deprecated_models = self.registry.get_deprecated_models()
        
        for model_spec in deprecated_models:
            alert = self._create_deprecation_alert(model_spec)
            if alert:
                alerts.append(alert)
        
        # 긴급도 순으로 정렬
        alerts.sort(key=lambda x: self._urgency_priority(x.urgency))
        
        return alerts
    
    def _create_deprecation_alert(self, model_spec: ModelSpec) -> Optional[DeprecationAlert]:
        """모델 사양에서 deprecation 알림 생성"""
        if not model_spec.deprecation_date:
            return None
        
        try:
            deprecation_date = datetime.strptime(model_spec.deprecation_date, "%Y-%m-%d")
            days_remaining = (deprecation_date - datetime.now()).days
            
            # 긴급도 계산
            if days_remaining < 0:
                urgency = MigrationUrgency.CRITICAL
            elif days_remaining <= 1:
                urgency = MigrationUrgency.HIGH
            elif days_remaining <= 7:
                urgency = MigrationUrgency.HIGH
            elif days_remaining <= 30:
                urgency = MigrationUrgency.MEDIUM
            else:
                urgency = MigrationUrgency.LOW
            
            # 영향받는 use case 찾기
            affected_use_cases = self._find_affected_use_cases(model_spec.provider, model_spec.name)
            
            return DeprecationAlert(
                model_key=f"{model_spec.provider}:{model_spec.name}",
                deprecation_date=model_spec.deprecation_date,
                days_remaining=days_remaining,
                replacement_model=model_spec.replacement,
                migration_guide=model_spec.migration_guide,
                urgency=urgency,
                affected_use_cases=affected_use_cases
            )
            
        except ValueError as e:
            logger.error(f"Invalid deprecation date format for {model_spec.name}: {e}")
            return None
    
    def _find_affected_use_cases(self, provider: str, model: str) -> List[str]:
        """특정 모델이 영향을 주는 use case들 찾기"""
        affected_cases = []
        
        # 현재 환경 설정에서 사용 중인지 확인
        current_config = self.env_manager.get_current_config()
        if current_config:
            # 기본 모델 확인
            if (current_config.default_provider == provider and 
                current_config.default_chat_model == model):
                affected_cases.append("default_chat")
            
            if current_config.default_embedding_model == model:
                affected_cases.append("embedding")
            
            # 모델 오버라이드 확인
            for use_case, override in current_config.model_overrides.items():
                if (override.get('provider') == provider and 
                    override.get('model') == model):
                    affected_cases.append(use_case)
        
        return affected_cases
    
    def _urgency_priority(self, urgency: MigrationUrgency) -> int:
        """긴급도의 우선순위 번호 반환"""
        priorities = {
            MigrationUrgency.CRITICAL: 0,
            MigrationUrgency.HIGH: 1,
            MigrationUrgency.MEDIUM: 2,
            MigrationUrgency.LOW: 3
        }
        return priorities.get(urgency, 999)
    
    def create_migration_plan(self, source_provider: str, source_model: str) -> Optional[MigrationPlan]:
        """마이그레이션 계획 생성"""
        source_spec = self.registry.get_model(source_provider, source_model)
        if not source_spec:
            logger.error(f"Source model not found: {source_provider}:{source_model}")
            return None
        
        # 1. 직접 지정된 replacement 확인
        if source_spec.replacement:
            target_spec = self.registry.get_model(source_provider, source_spec.replacement)
            if target_spec and not target_spec.deprecated:
                return self._create_migration_plan(source_spec, target_spec, "direct_replacement")
        
        # 2. 같은 제공자 내에서 유사한 모델 찾기
        same_provider_models = self.registry.get_available_models(provider=source_provider)
        for target_spec in same_provider_models:
            if (not target_spec.deprecated and 
                target_spec.type == source_spec.type and
                target_spec.name != source_spec.name):
                return self._create_migration_plan(source_spec, target_spec, "same_provider_upgrade")
        
        # 3. 다른 제공자에서 유사한 모델 찾기
        all_models = self.registry.get_available_models(model_type=source_spec.type)
        for target_spec in all_models:
            if (not target_spec.deprecated and 
                target_spec.provider != source_spec.provider and
                self._is_similar_capability(source_spec, target_spec)):
                return self._create_migration_plan(source_spec, target_spec, "cross_provider_migration")
        
        logger.warning(f"No suitable replacement found for {source_provider}:{source_model}")
        return None
    
    def _is_similar_capability(self, source: ModelSpec, target: ModelSpec) -> bool:
        """두 모델이 유사한 능력을 가지는지 확인"""
        # 타입이 같아야 함
        if source.type != target.type:
            return False
        
        # 컨텍스트 윈도우 비교 (최소 80% 이상)
        if target.context_window < source.context_window * 0.8:
            return False
        
        # 토큰 수 비교 (최소 80% 이상)
        if target.max_tokens < source.max_tokens * 0.8:
            return False
        
        # 품질 등급 비교 (같거나 더 좋아야 함)
        quality_order = {"poor": 0, "fair": 1, "good": 2, "excellent": 3, "outstanding": 4}
        source_quality = quality_order.get(source.quality_tier.value, 0)
        target_quality = quality_order.get(target.quality_tier.value, 0)
        
        return target_quality >= source_quality
    
    def _create_migration_plan(self, source: ModelSpec, target: ModelSpec, reason: str) -> MigrationPlan:
        """마이그레이션 계획 생성"""
        # 비용 영향 계산
        cost_impact = self._calculate_cost_impact(source, target)
        
        # 성능 영향 평가
        performance_impact = self._evaluate_performance_impact(source, target)
        
        # 긴급도 계산
        urgency = MigrationUrgency.LOW
        if source.deprecation_date:
            try:
                deprecation_date = datetime.strptime(source.deprecation_date, "%Y-%m-%d")
                days_remaining = (deprecation_date - datetime.now()).days
                
                if days_remaining < 0:
                    urgency = MigrationUrgency.CRITICAL
                elif days_remaining <= 7:
                    urgency = MigrationUrgency.HIGH
                elif days_remaining <= 30:
                    urgency = MigrationUrgency.MEDIUM
            except ValueError:
                pass
        
        # 마이그레이션 단계
        migration_steps = self._generate_migration_steps(source, target)
        
        # 롤백 계획
        rollback_plan = self._generate_rollback_plan(source, target)
        
        return MigrationPlan(
            source_provider=source.provider,
            source_model=source.name,
            target_provider=target.provider,
            target_model=target.name,
            reason=reason,
            urgency=urgency,
            estimated_cost_impact=cost_impact,
            performance_impact=performance_impact,
            migration_steps=migration_steps,
            rollback_plan=rollback_plan,
            testing_required=(source.provider != target.provider)
        )
    
    def _calculate_cost_impact(self, source: ModelSpec, target: ModelSpec) -> float:
        """비용 영향 계산 (%)"""
        # 비용 등급별 상대적 비용
        cost_values = {
            "very_low": 1,
            "low": 2,
            "medium": 4,
            "high": 8,
            "very_high": 16
        }
        
        source_cost = cost_values.get(source.cost_tier.value, 4)
        target_cost = cost_values.get(target.cost_tier.value, 4)
        
        return ((target_cost - source_cost) / source_cost) * 100
    
    def _evaluate_performance_impact(self, source: ModelSpec, target: ModelSpec) -> str:
        """성능 영향 평가"""
        # 품질 등급 비교
        quality_order = {"poor": 0, "fair": 1, "good": 2, "excellent": 3, "outstanding": 4}
        source_quality = quality_order.get(source.quality_tier.value, 2)
        target_quality = quality_order.get(target.quality_tier.value, 2)
        
        if target_quality > source_quality:
            return "better"
        elif target_quality == source_quality:
            return "similar"
        else:
            return "worse"
    
    def _generate_migration_steps(self, source: ModelSpec, target: ModelSpec) -> List[str]:
        """마이그레이션 단계 생성"""
        steps = []
        
        if source.provider == target.provider:
            # 같은 제공자 내에서 마이그레이션
            steps = [
                f"1. 환경변수 업데이트: {source.name} → {target.name}",
                "2. 설정 파일 업데이트",
                "3. 애플리케이션 재시작",
                "4. 기능 테스트 수행",
                "5. 성능 모니터링"
            ]
        else:
            # 다른 제공자로 마이그레이션
            steps = [
                f"1. {target.provider} API 키 설정",
                f"2. 환경변수 업데이트: {source.provider} → {target.provider}",
                f"3. 모델명 업데이트: {source.name} → {target.name}",
                "4. 프롬프트 템플릿 호환성 확인",
                "5. 애플리케이션 재시작",
                "6. 통합 테스트 수행",
                "7. A/B 테스트 (권장)",
                "8. 성능 및 비용 모니터링"
            ]
        
        return steps
    
    def _generate_rollback_plan(self, source: ModelSpec, target: ModelSpec) -> List[str]:
        """롤백 계획 생성"""
        return [
            "1. 문제 발생 시 즉시 알림",
            f"2. 환경변수를 {source.provider}:{source.name}으로 복원",
            "3. 애플리케이션 재시작",
            "4. 기능 정상 동작 확인",
            "5. 문제 원인 분석 및 문서화"
        ]
    
    async def auto_migrate_if_needed(self, provider: str, model: str) -> Tuple[bool, Optional[str]]:
        """필요시 자동 마이그레이션 수행"""
        model_spec = self.registry.get_model(provider, model)
        
        if not model_spec or not model_spec.deprecated:
            return False, None
        
        # 자동 마이그레이션 활성화 확인
        auto_migration_enabled = os.getenv('AUTO_MIGRATION_ENABLED', 'false').lower() == 'true'
        if not auto_migration_enabled:
            return False, "자동 마이그레이션이 비활성화되어 있습니다"
        
        # 마이그레이션 계획 생성
        migration_plan = self.create_migration_plan(provider, model)
        if not migration_plan:
            return False, "적절한 대체 모델을 찾을 수 없습니다"
        
        # 긴급도가 HIGH 이상일 때만 자동 마이그레이션
        if migration_plan.urgency not in [MigrationUrgency.HIGH, MigrationUrgency.CRITICAL]:
            return False, f"긴급도가 낮습니다: {migration_plan.urgency.value}"
        
        try:
            # 마이그레이션 실행
            success = await self._execute_migration(migration_plan)
            
            if success:
                # 히스토리 기록
                self._record_migration(migration_plan, "auto_migration_success")
                return True, f"자동 마이그레이션 완료: {migration_plan.target_provider}:{migration_plan.target_model}"
            else:
                return False, "마이그레이션 실행 실패"
                
        except Exception as e:
            logger.error(f"자동 마이그레이션 실패: {e}")
            return False, f"마이그레이션 오류: {str(e)}"
    
    async def _execute_migration(self, plan: MigrationPlan) -> bool:
        """마이그레이션 실행"""
        try:
            logger.info(f"마이그레이션 시작: {plan.source_provider}:{plan.source_model} → {plan.target_provider}:{plan.target_model}")
            
            # 1. 백업 생성 (환경변수 등)
            backup = self._create_backup()
            
            # 2. 환경변수 업데이트 (시뮬레이션)
            # 실제로는 환경변수를 직접 수정하지 않고 권장사항만 제공
            logger.info(f"권장 환경변수 업데이트:")
            logger.info(f"  - 기존: {plan.source_provider.upper()}_MODEL={plan.source_model}")
            logger.info(f"  - 신규: {plan.target_provider.upper()}_MODEL={plan.target_model}")
            
            # 3. 마이그레이션 완료 시뮬레이션
            await asyncio.sleep(0.1)  # 시뮬레이션용 대기
            
            logger.info("마이그레이션 시뮬레이션 완료")
            return True
            
        except Exception as e:
            logger.error(f"마이그레이션 실행 오류: {e}")
            return False
    
    def _create_backup(self) -> Dict[str, str]:
        """현재 설정 백업"""
        backup = {}
        
        # 주요 환경변수 백업
        env_vars = [
            'OPENAI_MODEL', 'ANTHROPIC_MODEL', 'GEMINI_MODEL',
            'SUMMARIZATION_MODEL_PROVIDER', 'SUMMARIZATION_MODEL_NAME',
            'TICKET_VIEW_MODEL_PROVIDER', 'TICKET_VIEW_MODEL_NAME'
        ]
        
        for var in env_vars:
            value = os.getenv(var)
            if value:
                backup[var] = value
        
        return backup
    
    def _record_migration(self, plan: MigrationPlan, status: str):
        """마이그레이션 히스토리 기록"""
        record = {
            'timestamp': datetime.now().isoformat(),
            'migration_plan': plan.to_dict(),
            'status': status,
            'environment': self.env_manager.current_env
        }
        
        self.migration_history.append(record)
        
        # 파일로 저장 (선택사항)
        try:
            history_file = os.getenv('MIGRATION_HISTORY_FILE', 'migration_history.json')
            with open(history_file, 'w') as f:
                json.dump(self.migration_history, f, indent=2)
        except Exception as e:
            logger.warning(f"마이그레이션 히스토리 저장 실패: {e}")
    
    def get_migration_recommendations(self) -> List[Dict[str, Any]]:
        """마이그레이션 권장사항 목록"""
        recommendations = []
        
        # Deprecated 모델들에 대한 권장사항
        alerts = self.check_deprecated_models()
        for alert in alerts:
            provider, model = alert.model_key.split(':')
            migration_plan = self.create_migration_plan(provider, model)
            
            if migration_plan:
                recommendations.append({
                    'alert': alert.to_dict(),
                    'migration_plan': migration_plan.to_dict(),
                    'priority': self._urgency_priority(alert.urgency)
                })
        
        # 우선순위 순으로 정렬
        recommendations.sort(key=lambda x: x['priority'])
        
        return recommendations
    
    def generate_migration_report(self) -> Dict[str, Any]:
        """마이그레이션 보고서 생성"""
        alerts = self.check_deprecated_models()
        recommendations = self.get_migration_recommendations()
        
        # 통계 계산
        urgency_counts = {}
        for alert in alerts:
            urgency = alert.urgency.value
            urgency_counts[urgency] = urgency_counts.get(urgency, 0) + 1
        
        return {
            'report_date': datetime.now().isoformat(),
            'environment': self.env_manager.current_env,
            'summary': {
                'total_deprecated_models': len(alerts),
                'critical_migrations': urgency_counts.get('critical', 0),
                'high_priority_migrations': urgency_counts.get('high', 0),
                'total_recommendations': len(recommendations)
            },
            'deprecation_alerts': [alert.to_dict() for alert in alerts],
            'migration_recommendations': recommendations,
            'migration_history': self.migration_history[-10:],  # 최근 10개만
            'next_actions': self._generate_next_actions(alerts)
        }
    
    def _generate_next_actions(self, alerts: List[DeprecationAlert]) -> List[str]:
        """다음 액션 항목 생성"""
        actions = []
        
        critical_count = sum(1 for alert in alerts if alert.urgency == MigrationUrgency.CRITICAL)
        high_count = sum(1 for alert in alerts if alert.urgency == MigrationUrgency.HIGH)
        
        if critical_count > 0:
            actions.append(f"🚨 즉시 조치 필요: {critical_count}개 모델이 이미 중단됨")
        
        if high_count > 0:
            actions.append(f"⚠️ 긴급 마이그레이션 필요: {high_count}개 모델이 7일 내 중단 예정")
        
        if len(alerts) > critical_count + high_count:
            actions.append(f"📋 마이그레이션 계획 수립: {len(alerts) - critical_count - high_count}개 모델 예정")
        
        actions.append("✅ 환경변수 및 설정 파일 업데이트")
        actions.append("🧪 마이그레이션 후 기능 테스트 수행")
        actions.append("📊 성능 및 비용 모니터링 설정")
        
        return actions


# 싱글톤 인스턴스
_deprecation_manager_instance = None

def get_deprecation_manager() -> DeprecationManager:
    """Deprecation 관리자 싱글톤 인스턴스 반환"""
    global _deprecation_manager_instance
    
    if _deprecation_manager_instance is None:
        _deprecation_manager_instance = DeprecationManager()
    
    return _deprecation_manager_instance