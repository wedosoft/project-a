#!/usr/bin/env python3
"""
설정 동기화 및 검증 도구

이 도구는 다음 기능을 제공합니다:
1. 로컬 YAML 파일과 클라우드 설정 간의 동기화 상태 확인
2. 환경별 설정 일관성 검증
3. 설정 변경 사항 자동 감지 및 알림
4. 설정 백업 및 복원
"""

import os
import json
import yaml
import hashlib
import asyncio
import argparse
import logging
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum

# 클라우드 제공자별 클라이언트 import (선택적)
try:
    import boto3
    HAS_AWS = True
except ImportError:
    HAS_AWS = False

try:
    from kubernetes import client, config as k8s_config
    HAS_KUBERNETES = True
except ImportError:
    HAS_KUBERNETES = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ConfigSource(Enum):
    """설정 소스 타입"""
    LOCAL_YAML = "local_yaml"
    AWS_SECRETS = "aws_secrets"
    AWS_PARAMETER = "aws_parameter"
    K8S_CONFIGMAP = "k8s_configmap"
    K8S_SECRET = "k8s_secret"
    ENVIRONMENT_VAR = "environment_var"


class SyncStatus(Enum):
    """동기화 상태"""
    IN_SYNC = "in_sync"
    OUT_OF_SYNC = "out_of_sync"
    SOURCE_MISSING = "source_missing"
    TARGET_MISSING = "target_missing"
    ERROR = "error"


@dataclass
class ConfigItem:
    """설정 항목"""
    key: str
    source: ConfigSource
    content: Dict[str, Any]
    checksum: str
    last_modified: str
    size: int


@dataclass
class SyncResult:
    """동기화 결과"""
    key: str
    source: ConfigSource
    target: ConfigSource
    status: SyncStatus
    local_checksum: Optional[str]
    remote_checksum: Optional[str]
    diff_summary: Optional[str]
    error_message: Optional[str]


class ConfigSyncValidator:
    """설정 동기화 및 검증 도구"""
    
    def __init__(self, environment: str = "dev"):
        self.environment = environment
        self.config_dir = Path(__file__).parent.parent / "backend/core/llm/config/centralized"
        
        # 클라우드 클라이언트들
        self.aws_secrets_client = None
        self.aws_parameter_client = None
        self.k8s_core_v1 = None
        
        # 결과 저장
        self.sync_results: List[SyncResult] = []
        self.validation_errors: List[str] = []
        
        self._initialize_clients()
    
    def _initialize_clients(self):
        """클라우드 클라이언트들 초기화"""
        # AWS 클라이언트
        if HAS_AWS and os.getenv('AWS_REGION'):
            try:
                region = os.getenv('AWS_REGION', 'us-east-1')
                self.aws_secrets_client = boto3.client('secretsmanager', region_name=region)
                self.aws_parameter_client = boto3.client('ssm', region_name=region)
                logger.info(f"AWS 클라이언트 초기화 완료 - 리전: {region}")
            except Exception as e:
                logger.warning(f"AWS 클라이언트 초기화 실패: {e}")
        
        # Kubernetes 클라이언트
        if HAS_KUBERNETES:
            try:
                # 클러스터 내부/외부 설정 자동 감지
                try:
                    k8s_config.load_incluster_config()
                except k8s_config.ConfigException:
                    k8s_config.load_kube_config()
                
                self.k8s_core_v1 = client.CoreV1Api()
                logger.info("Kubernetes 클라이언트 초기화 완료")
            except Exception as e:
                logger.warning(f"Kubernetes 클라이언트 초기화 실패: {e}")
    
    def _calculate_checksum(self, data: Dict[str, Any]) -> str:
        """설정 데이터의 체크섬 계산"""
        # 딕셔너리를 정렬된 JSON 문자열로 변환 후 해시
        json_str = json.dumps(data, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(json_str.encode('utf-8')).hexdigest()[:16]
    
    def _deep_diff(self, dict1: Dict[str, Any], dict2: Dict[str, Any]) -> List[str]:
        """두 딕셔너리 간의 차이점 찾기"""
        differences = []
        
        def _compare_recursive(d1, d2, path=""):
            if isinstance(d1, dict) and isinstance(d2, dict):
                # 키 비교
                all_keys = set(d1.keys()) | set(d2.keys())
                for key in all_keys:
                    current_path = f"{path}.{key}" if path else key
                    if key not in d1:
                        differences.append(f"Missing in source: {current_path}")
                    elif key not in d2:
                        differences.append(f"Missing in target: {current_path}")
                    else:
                        _compare_recursive(d1[key], d2[key], current_path)
            elif d1 != d2:
                differences.append(f"Value differs at {path}: {d1} != {d2}")
        
        _compare_recursive(dict1, dict2)
        return differences
    
    async def load_local_configs(self) -> Dict[str, ConfigItem]:
        """로컬 YAML 설정 파일들 로드"""
        local_configs = {}
        
        config_files = [
            "model_registry.yaml",
            "environment_configs.yaml",
            "secrets_template.yaml"
        ]
        
        for config_file in config_files:
            file_path = self.config_dir / config_file
            if file_path.exists():
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = yaml.safe_load(f)
                    
                    stat = file_path.stat()
                    config_item = ConfigItem(
                        key=config_file.replace('.yaml', ''),
                        source=ConfigSource.LOCAL_YAML,
                        content=content,
                        checksum=self._calculate_checksum(content),
                        last_modified=datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        size=stat.st_size
                    )
                    
                    local_configs[config_item.key] = config_item
                    logger.info(f"로컬 설정 로드: {config_file} (체크섬: {config_item.checksum})")
                    
                except Exception as e:
                    logger.error(f"로컬 설정 로드 실패 {config_file}: {e}")
        
        return local_configs
    
    async def load_aws_configs(self) -> Dict[str, ConfigItem]:
        """AWS에서 설정들 로드"""
        aws_configs = {}
        
        if not self.aws_secrets_client:
            return aws_configs
        
        config_keys = ["model_registry", "environment_configs", "secrets_template"]
        
        for config_key in config_keys:
            # Secrets Manager에서 로드
            secret_name = f"llm/{self.environment}/{config_key}"
            try:
                response = self.aws_secrets_client.get_secret_value(SecretId=secret_name)
                content = json.loads(response['SecretString'])
                
                config_item = ConfigItem(
                    key=config_key,
                    source=ConfigSource.AWS_SECRETS,
                    content=content,
                    checksum=self._calculate_checksum(content),
                    last_modified=response['CreatedDate'].isoformat(),
                    size=len(response['SecretString'])
                )
                
                aws_configs[f"{config_key}_secrets"] = config_item
                logger.info(f"AWS Secrets 로드: {secret_name} (체크섬: {config_item.checksum})")
                
            except Exception as e:
                logger.warning(f"AWS Secrets 로드 실패 {secret_name}: {e}")
            
            # Parameter Store에서 로드 (비민감 정보만)
            if config_key in ["model_registry", "environment_configs"]:
                parameter_name = f"/llm/{self.environment}/{config_key}"
                try:
                    response = self.aws_parameter_client.get_parameter(Name=parameter_name)
                    content = json.loads(response['Parameter']['Value'])
                    
                    config_item = ConfigItem(
                        key=config_key,
                        source=ConfigSource.AWS_PARAMETER,
                        content=content,
                        checksum=self._calculate_checksum(content),
                        last_modified=response['Parameter']['LastModifiedDate'].isoformat(),
                        size=len(response['Parameter']['Value'])
                    )
                    
                    aws_configs[f"{config_key}_parameter"] = config_item
                    logger.info(f"AWS Parameter 로드: {parameter_name} (체크섬: {config_item.checksum})")
                    
                except Exception as e:
                    logger.warning(f"AWS Parameter 로드 실패 {parameter_name}: {e}")
        
        return aws_configs
    
    async def load_k8s_configs(self) -> Dict[str, ConfigItem]:
        """Kubernetes에서 설정들 로드"""
        k8s_configs = {}
        
        if not self.k8s_core_v1:
            return k8s_configs
        
        namespace = os.getenv('K8S_NAMESPACE', 'default')
        
        # ConfigMap에서 로드
        configmap_names = [
            f"llm-model-registry-{self.environment}",
            f"llm-environment-configs-{self.environment}"
        ]
        
        for configmap_name in configmap_names:
            try:
                configmap = self.k8s_core_v1.read_namespaced_config_map(
                    name=configmap_name,
                    namespace=namespace
                )
                
                # YAML 데이터 파싱
                config_key = configmap_name.split('-')[1]  # model, environment 등
                yaml_content = configmap.data.get(f"{config_key}_registry.yaml") or configmap.data.get(f"{config_key}_configs.yaml")
                
                if yaml_content:
                    content = yaml.safe_load(yaml_content)
                    
                    config_item = ConfigItem(
                        key=config_key,
                        source=ConfigSource.K8S_CONFIGMAP,
                        content=content,
                        checksum=self._calculate_checksum(content),
                        last_modified=configmap.metadata.creation_timestamp.isoformat(),
                        size=len(yaml_content)
                    )
                    
                    k8s_configs[f"{config_key}_configmap"] = config_item
                    logger.info(f"K8s ConfigMap 로드: {configmap_name} (체크섬: {config_item.checksum})")
                    
            except Exception as e:
                logger.warning(f"K8s ConfigMap 로드 실패 {configmap_name}: {e}")
        
        # Secret에서 로드
        secret_names = [
            f"llm-secrets-template-{self.environment}"
        ]
        
        for secret_name in secret_names:
            try:
                secret = self.k8s_core_v1.read_namespaced_secret(
                    name=secret_name,
                    namespace=namespace
                )
                
                # base64 디코딩 후 YAML 파싱
                yaml_content = base64.b64decode(secret.data['secrets_template.yaml']).decode('utf-8')
                content = yaml.safe_load(yaml_content)
                
                config_item = ConfigItem(
                    key="secrets_template",
                    source=ConfigSource.K8S_SECRET,
                    content=content,
                    checksum=self._calculate_checksum(content),
                    last_modified=secret.metadata.creation_timestamp.isoformat(),
                    size=len(yaml_content)
                )
                
                k8s_configs["secrets_template_secret"] = config_item
                logger.info(f"K8s Secret 로드: {secret_name} (체크섬: {config_item.checksum})")
                
            except Exception as e:
                logger.warning(f"K8s Secret 로드 실패 {secret_name}: {e}")
        
        return k8s_configs
    
    async def compare_configs(self, local_configs: Dict[str, ConfigItem], 
                            remote_configs: Dict[str, ConfigItem]) -> List[SyncResult]:
        """로컬과 원격 설정 비교"""
        sync_results = []
        
        # 로컬 설정 기준으로 비교
        for local_key, local_config in local_configs.items():
            # 원격에서 매칭되는 설정 찾기
            matching_remotes = [
                (remote_key, remote_config) 
                for remote_key, remote_config in remote_configs.items()
                if remote_config.key == local_config.key
            ]
            
            if not matching_remotes:
                # 원격에 해당 설정이 없음
                sync_result = SyncResult(
                    key=local_key,
                    source=local_config.source,
                    target=ConfigSource.LOCAL_YAML,  # 더미값
                    status=SyncStatus.TARGET_MISSING,
                    local_checksum=local_config.checksum,
                    remote_checksum=None,
                    diff_summary="원격에 설정이 없음",
                    error_message=None
                )
                sync_results.append(sync_result)
                continue
            
            # 각 원격 설정과 비교
            for remote_key, remote_config in matching_remotes:
                if local_config.checksum == remote_config.checksum:
                    status = SyncStatus.IN_SYNC
                    diff_summary = None
                else:
                    status = SyncStatus.OUT_OF_SYNC
                    differences = self._deep_diff(local_config.content, remote_config.content)
                    diff_summary = f"{len(differences)}개 차이점: " + "; ".join(differences[:3])
                    if len(differences) > 3:
                        diff_summary += f" (및 {len(differences) - 3}개 더)"
                
                sync_result = SyncResult(
                    key=local_key,
                    source=local_config.source,
                    target=remote_config.source,
                    status=status,
                    local_checksum=local_config.checksum,
                    remote_checksum=remote_config.checksum,
                    diff_summary=diff_summary,
                    error_message=None
                )
                sync_results.append(sync_result)
        
        return sync_results
    
    async def validate_config_consistency(self, all_configs: Dict[str, ConfigItem]) -> List[str]:
        """설정 일관성 검증"""
        validation_errors = []
        
        # 같은 키를 가진 설정들을 그룹화
        config_groups = {}
        for config_key, config_item in all_configs.items():
            base_key = config_item.key
            if base_key not in config_groups:
                config_groups[base_key] = []
            config_groups[base_key].append(config_item)
        
        # 각 그룹 내에서 일관성 검증
        for base_key, configs in config_groups.items():
            if len(configs) < 2:
                continue
            
            # 체크섬 비교
            checksums = [config.checksum for config in configs]
            if len(set(checksums)) > 1:
                sources = [config.source.value for config in configs]
                validation_errors.append(
                    f"설정 불일치 감지: {base_key} - 소스들: {sources} - 체크섬들: {checksums}"
                )
            
            # 필수 필드 검증
            for config in configs:
                if base_key == "model_registry":
                    if "providers" not in config.content:
                        validation_errors.append(f"{config.source.value}의 {base_key}에 'providers' 필드가 없음")
                
                elif base_key == "environment_configs":
                    if "deployment_environments" not in config.content:
                        validation_errors.append(f"{config.source.value}의 {base_key}에 'deployment_environments' 필드가 없음")
                
                elif base_key == "secrets_template":
                    if "api_keys" not in config.content:
                        validation_errors.append(f"{config.source.value}의 {base_key}에 'api_keys' 필드가 없음")
        
        return validation_errors
    
    async def create_backup(self, configs: Dict[str, ConfigItem], backup_dir: str) -> str:
        """설정 백업 생성"""
        backup_path = Path(backup_dir)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"config_backup_{self.environment}_{timestamp}"
        full_backup_path = backup_path / backup_name
        
        full_backup_path.mkdir(parents=True, exist_ok=True)
        
        # 설정 파일들 백업
        for config_key, config_item in configs.items():
            # YAML 형태로 저장
            yaml_file = full_backup_path / f"{config_key}.yaml"
            with open(yaml_file, 'w', encoding='utf-8') as f:
                yaml.dump(config_item.content, f, default_flow_style=False, allow_unicode=True)
            
            # 메타데이터 저장
            metadata_file = full_backup_path / f"{config_key}_metadata.json"
            with open(metadata_file, 'w', encoding='utf-8') as f:
                metadata = asdict(config_item)
                metadata['content'] = f"See {config_key}.yaml"  # 중복 저장 방지
                json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        # 백업 요약 정보 저장
        summary_file = full_backup_path / "backup_summary.json"
        summary = {
            "backup_date": datetime.now().isoformat(),
            "environment": self.environment,
            "total_configs": len(configs),
            "config_keys": list(configs.keys()),
            "backup_tool_version": "1.0.0"
        }
        
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        logger.info(f"백업 생성 완료: {full_backup_path}")
        return str(full_backup_path)
    
    async def run_full_validation(self) -> Dict[str, Any]:
        """전체 검증 프로세스 실행"""
        logger.info(f"설정 동기화 검증 시작 - 환경: {self.environment}")
        
        # 1. 모든 소스에서 설정 로드
        local_configs = await self.load_local_configs()
        aws_configs = await self.load_aws_configs()
        k8s_configs = await self.load_k8s_configs()
        
        # 2. 전체 설정 통합
        all_configs = {**local_configs, **aws_configs, **k8s_configs}
        
        # 3. 동기화 상태 비교
        sync_results = await self.compare_configs(local_configs, {**aws_configs, **k8s_configs})
        
        # 4. 일관성 검증
        validation_errors = await self.validate_config_consistency(all_configs)
        
        # 5. 통계 계산
        total_configs = len(all_configs)
        in_sync_count = len([r for r in sync_results if r.status == SyncStatus.IN_SYNC])
        out_of_sync_count = len([r for r in sync_results if r.status == SyncStatus.OUT_OF_SYNC])
        missing_count = len([r for r in sync_results if r.status == SyncStatus.TARGET_MISSING])
        
        return {
            "validation_date": datetime.now().isoformat(),
            "environment": self.environment,
            "summary": {
                "total_configs": total_configs,
                "local_configs": len(local_configs),
                "aws_configs": len(aws_configs),
                "k8s_configs": len(k8s_configs),
                "in_sync": in_sync_count,
                "out_of_sync": out_of_sync_count,
                "missing": missing_count,
                "validation_errors": len(validation_errors)
            },
            "sync_results": [asdict(result) for result in sync_results],
            "validation_errors": validation_errors,
            "config_inventory": {
                config_key: {
                    "source": config_item.source.value,
                    "checksum": config_item.checksum,
                    "last_modified": config_item.last_modified,
                    "size": config_item.size
                }
                for config_key, config_item in all_configs.items()
            }
        }


def print_validation_report(report: Dict[str, Any]):
    """검증 보고서 출력"""
    print("🔍 설정 동기화 검증 보고서")
    print("=" * 60)
    print(f"검증 일시: {report['validation_date']}")
    print(f"환경: {report['environment']}")
    
    summary = report['summary']
    print(f"\n📊 요약:")
    print(f"  총 설정: {summary['total_configs']}개")
    print(f"  로컬 설정: {summary['local_configs']}개")
    print(f"  AWS 설정: {summary['aws_configs']}개")
    print(f"  K8s 설정: {summary['k8s_configs']}개")
    
    print(f"\n🔄 동기화 상태:")
    print(f"  ✅ 동기화됨: {summary['in_sync']}개")
    print(f"  ❌ 불일치: {summary['out_of_sync']}개")
    print(f"  ⚠️  누락: {summary['missing']}개")
    print(f"  🚨 검증 오류: {summary['validation_errors']}개")
    
    # 동기화 결과 상세
    if report['sync_results']:
        print(f"\n📋 동기화 결과 상세:")
        for result in report['sync_results']:
            status_emoji = {
                "in_sync": "✅",
                "out_of_sync": "❌",
                "target_missing": "⚠️",
                "source_missing": "🔍",
                "error": "🚨"
            }
            emoji = status_emoji.get(result['status'], "❓")
            
            print(f"  {emoji} {result['key']}: {result['source']} → {result['target']}")
            if result['diff_summary']:
                print(f"     차이점: {result['diff_summary']}")
    
    # 검증 오류
    if report['validation_errors']:
        print(f"\n🚨 검증 오류:")
        for error in report['validation_errors']:
            print(f"  • {error}")


async def main():
    parser = argparse.ArgumentParser(description="설정 동기화 및 검증 도구")
    parser.add_argument("--environment", default="dev", help="검증할 환경")
    parser.add_argument("--backup-dir", help="백업 저장 디렉토리")
    parser.add_argument("--output-file", help="결과를 JSON 파일로 저장")
    parser.add_argument("--watch", action="store_true", help="지속적인 모니터링 모드")
    parser.add_argument("--watch-interval", type=int, default=300, help="모니터링 간격 (초)")
    
    args = parser.parse_args()
    
    validator = ConfigSyncValidator(environment=args.environment)
    
    if args.watch:
        # 지속적인 모니터링
        print(f"🔄 지속적인 모니터링 시작 (간격: {args.watch_interval}초)")
        while True:
            try:
                report = await validator.run_full_validation()
                
                # 문제가 있으면 알림
                summary = report['summary']
                if summary['out_of_sync'] > 0 or summary['validation_errors'] > 0:
                    print(f"\n⚠️  {datetime.now().strftime('%H:%M:%S')} - 설정 문제 감지!")
                    print_validation_report(report)
                else:
                    print(f"✅ {datetime.now().strftime('%H:%M:%S')} - 모든 설정이 동기화됨")
                
                await asyncio.sleep(args.watch_interval)
                
            except KeyboardInterrupt:
                print("\n모니터링 중단됨")
                break
            except Exception as e:
                print(f"❌ 모니터링 오류: {e}")
                await asyncio.sleep(args.watch_interval)
    else:
        # 일회성 검증
        report = await validator.run_full_validation()
        
        # 백업 생성
        if args.backup_dir:
            all_configs = {}
            local_configs = await validator.load_local_configs()
            aws_configs = await validator.load_aws_configs()
            k8s_configs = await validator.load_k8s_configs()
            all_configs.update(local_configs)
            all_configs.update(aws_configs)
            all_configs.update(k8s_configs)
            
            backup_path = await validator.create_backup(all_configs, args.backup_dir)
            print(f"📁 백업 저장: {backup_path}")
        
        # 결과 출력
        print_validation_report(report)
        
        # JSON 파일로 저장
        if args.output_file:
            with open(args.output_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            print(f"📄 결과 저장: {args.output_file}")
        
        # 종료 코드 설정
        summary = report['summary']
        if summary['out_of_sync'] > 0 or summary['validation_errors'] > 0:
            exit(1)  # 문제가 있으면 오류 코드로 종료
        else:
            exit(0)  # 모든 것이 정상이면 정상 종료


if __name__ == "__main__":
    asyncio.run(main())